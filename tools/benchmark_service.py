"""Benchmark script for Task 3:
Sends 50 requests one after another to the container running with 1 CPU and 1 GiB memory limit.
Measures latency, verifies status 200, checks response headers, and records peak memory.
"""

import os
import sys
import time
import json
import socket
import urllib.request
import urllib.error
import subprocess

try:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

VALIDATION_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "validation.jsonl")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def benchmark_service(endpoint="http://127.0.0.1:8000", container_name="test-service", num_requests=50):
    print(f"Running Task 3 Benchmark: {num_requests} sequential requests to {endpoint}...")
    
    # Read commands from validation set
    texts = []
    with open(VALIDATION_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                texts.append(json.loads(line)["text"])

    latencies = []
    success_count = 0
    headers_seen = []

    # Send 50 sequential requests
    for i in range(num_requests):
        cmd_text = texts[i % len(texts)]
        payload = json.dumps({"text": cmd_text}).encode("utf-8")
        req = urllib.request.Request(
            f"{endpoint}/parse",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                body = json.loads(resp.read().decode("utf-8"))
                x_model_ver = resp.headers.get("X-Model-Version")
                x_served_by = resp.headers.get("X-Served-By")
                headers_seen.append({"version": x_model_ver, "served_by": x_served_by})
                t1 = time.time()
                latencies.append((t1 - t0) * 1000)
                if status == 200 and isinstance(body, dict):
                    success_count += 1
        except Exception as e:
            print(f"Request {i+1} failed: {e}")

        if (i + 1) % 10 == 0:
            print(f"  Processed {i+1}/{num_requests} requests...")

    # Query docker stats for container memory
    peak_mem_str = "N/A"
    try:
        res = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container_name],
            capture_output=True,
            text=True
        )
        if res.returncode == 0 and res.stdout.strip():
            peak_mem_str = res.stdout.strip()
    except Exception as e:
        print(f"Could not retrieve docker stats: {e}")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p50_latency = sorted(latencies)[len(latencies)//2] if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0

    benchmark_summary = {
        "requests_total": num_requests,
        "requests_successful": success_count,
        "success_rate_percent": round(100.0 * success_count / num_requests, 2),
        "peak_memory_usage": peak_mem_str,
        "latency_ms": {
            "avg": round(avg_latency, 2),
            "p50": round(p50_latency, 2),
            "p95": round(p95_latency, 2),
            "min": round(min(latencies), 2) if latencies else 0,
            "max": round(max(latencies), 2) if latencies else 0
        },
        "sample_headers": headers_seen[:3]
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_file = os.path.join(RESULTS_DIR, "benchmark_50_requests.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)

    print("\n" + "="*50)
    print("        TASK 3 SERVICE BENCHMARK RESULTS         ")
    print("="*50)
    print(f"Total Requests:     {num_requests}")
    print(f"Successful:         {success_count} ({benchmark_summary['success_rate_percent']}%)")
    print(f"Peak Memory:        {peak_mem_str}")
    print(f"p50 Latency:        {p50_latency:.2f} ms")
    print(f"p95 Latency:        {p95_latency:.2f} ms")
    print(f"Results saved to:   {out_file}")
    print("="*50 + "\n")


if __name__ == "__main__":
    benchmark_service()
