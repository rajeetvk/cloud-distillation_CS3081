#!/usr/bin/env python3
"""
Worker for parallel teacher labelling using Sequence-Level Knowledge Distillation.
Part of Cloud Computing Mini Project (Task 1).
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

def fetch_commands(input_path, s3_endpoint):
    """
    Fetch commands from local file if exists, or from SeaweedFS S3 bucket.
    """
    if os.path.exists(input_path):
        print(f"Reading input commands from local file: {input_path}", flush=True)
        with open(input_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    # Fallback to S3
    s3_url = f"{s3_endpoint.rstrip('/')}/datasets/commands_pool.jsonl"
    print(f"Fetching input commands from S3: {s3_url}", flush=True)
    req = urllib.request.Request(s3_url)
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8")
        return [json.loads(line) for line in content.splitlines() if line.strip()]

def get_teacher_prompt(prompt_path):
    """
    Load prompt template from file or fallback to default.
    """
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise FileNotFoundError(f"Teacher prompt file not found at: {prompt_path}")

def call_teacher(teacher_url, prompt_text, retries=5, backoff=2):
    """
    Call Ollama teacher model with temperature=0 and seed=42.
    """
    payload = {
        "model": "phi3.5",
        "prompt": prompt_text,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0,
            "seed": 42
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{teacher_url.rstrip('/')}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", "")
        except Exception as e:
            if attempt < retries - 1:
                wait_time = backoff * (2 ** attempt)
                print(f"Warning: Teacher call failed ({e}), retrying in {wait_time}s...", flush=True)
                time.sleep(wait_time)
            else:
                raise e

def upload_to_s3(s3_endpoint, bucket, key, local_filepath):
    """
    Upload file to SeaweedFS S3.
    """
    url = f"{s3_endpoint.rstrip('/')}/{bucket}/{key}"
    print(f"Uploading {local_filepath} to {url}...", flush=True)
    with open(local_filepath, "rb") as f:
        data = f.read()
    req = urllib.request.Request(url, data=data, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Successfully uploaded to {url} (HTTP {resp.status})", flush=True)
    except Exception as e:
        print(f"Warning: Failed to upload to S3 ({e})", flush=True)

def main():
    shard_index = int(os.environ.get("SHARD_INDEX", "0"))
    shard_count = int(os.environ.get("SHARD_COUNT", "2"))
    teacher_url = os.environ.get("TEACHER_URL", "http://host.k3d.internal:11434")
    s3_endpoint = os.environ.get("S3_ENDPOINT", "http://seaweedfs.data.svc.cluster.local:8333")
    input_path = os.environ.get("INPUT_PATH", "data/commands_pool.jsonl")
    prompt_path = os.environ.get("PROMPT_PATH", "prompts/teacher_prompt.txt")
    output_dir = os.environ.get("OUTPUT_DIR", "datasets/teacher")

    print(f"Starting Worker Shard {shard_index}/{shard_count}", flush=True)
    print(f"Teacher URL: {teacher_url}", flush=True)
    print(f"S3 Endpoint: {s3_endpoint}", flush=True)

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"shard-{shard_index}.jsonl")

    prompt_template = get_teacher_prompt(prompt_path)
    commands = fetch_commands(input_path, s3_endpoint)
    total_commands = len(commands)
    print(f"Loaded {total_commands} total commands.", flush=True)

    # Filter assigned commands based on modulo sharding
    my_tasks = []
    for line_idx, item in enumerate(commands):
        if line_idx % shard_count == shard_index:
            my_tasks.append((line_idx, item))

    print(f"Worker {shard_index} assigned {len(my_tasks)} commands.", flush=True)

    # Resume support if file exists
    done_ids = set()
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    done_ids.add(rec["id"])
        print(f"Resuming: {len(done_ids)} commands already processed in {output_file}.", flush=True)

    start_time = time.time()
    processed_count = len(done_ids)

    with open(output_file, "a", encoding="utf-8") as out_f:
        for idx, (line_idx, item) in enumerate(my_tasks):
            cid = item["id"]
            if cid in done_ids:
                continue

            text = item["text"]
            prompt = prompt_template.replace("{command}", text)

            raw_reply = call_teacher(teacher_url, prompt)
            
            record = {
                "id": cid,
                "text": text,
                "teacher_raw": raw_reply
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            done_ids.add(cid)
            processed_count += 1

            if processed_count % 25 == 0 or processed_count == len(my_tasks):
                elapsed = time.time() - start_time
                avg_speed = elapsed / max(1, (processed_count - (len(done_ids) - (idx + 1))))
                print(f"[Worker {shard_index}] Progress: {processed_count}/{len(my_tasks)} "
                      f"({(processed_count/len(my_tasks))*100:.1f}%) | Elapsed: {elapsed:.1f}s", flush=True)

    print(f"[Worker {shard_index}] Completed all {len(my_tasks)} commands in {time.time()-start_time:.1f}s!", flush=True)

    # Upload shard output to SeaweedFS S3
    upload_to_s3(s3_endpoint, "datasets", f"teacher/shard-{shard_index}.jsonl", output_file)

if __name__ == "__main__":
    main()
