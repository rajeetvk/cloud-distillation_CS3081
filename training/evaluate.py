"""Evaluation utility for Teacher, Untrained Pythia-70M, and Trained Student models."""

import os
import sys
import json
import socket
import urllib.request
import urllib.error
import argparse
import subprocess

# Enforce IPv4 to avoid broken IPv6 handshakes in Windows environment
try:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

PROMPT_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "teacher_prompt.txt")
VALIDATION_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "validation.jsonl")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def evaluate_ollama_teacher(endpoint="http://localhost:11434"):
    """Evaluate teacher (phi3.5) on validation.jsonl."""
    print("Evaluating Teacher (Phi-3.5) via Ollama...")
    with open(PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    predictions = []
    with open(VALIDATION_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            item = json.loads(line)
            cid = item["id"]
            text = item["text"]

            payload = {
                "model": "phi3.5",
                "prompt": f"{system_prompt}\n\nCommand: \"{text}\"\nJSON:",
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "seed": 42
                }
            }

            req = urllib.request.Request(
                f"{endpoint}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    raw_reply = resp_data.get("response", "").strip()
            except Exception as e:
                print(f"Error querying teacher for {cid}: {e}")
                raw_reply = ""

            predictions.append({"id": cid, "prediction": raw_reply})
            if idx % 20 == 0:
                print(f"Teacher evaluated: {idx}/100")

    pred_path = os.path.join(RESULTS_DIR, "teacher_predictions.jsonl")
    report_path = os.path.join(RESULTS_DIR, "teacher_validation.json")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(pred_path, "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p) + "\n")

    subprocess.run([
        sys.executable,
        os.path.join("tools", "score.py"),
        pred_path,
        VALIDATION_PATH,
        "--out",
        report_path
    ], check=True)
    print(f"Teacher report saved to {report_path}")


def evaluate_pythia(model_path="EleutherAI/pythia-70m", output_prefix="untrained_pythia"):
    """Evaluate Pythia model (untrained or fine-tuned) on validation.jsonl."""
    print(f"Evaluating Pythia model from '{model_path}'...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float32)
    model.eval()

    predictions = []
    with open(VALIDATION_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            item = json.loads(line)
            cid = item["id"]
            text = item["text"]

            prompt = f"Command: {text.strip()}\nJSON: "
            inputs = tokenizer(prompt, return_tensors="pt")

            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=64,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id
                )

            gen = tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
            # First line or JSON block
            first_line = gen.split("\n")[0].strip()
            predictions.append({"id": cid, "prediction": first_line})
            if idx % 25 == 0:
                print(f"Pythia evaluated: {idx}/100")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    pred_path = os.path.join(RESULTS_DIR, f"{output_prefix}_predictions.jsonl")
    report_path = os.path.join(RESULTS_DIR, f"{output_prefix}_validation.json")

    with open(pred_path, "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p) + "\n")

    subprocess.run([
        sys.executable,
        os.path.join("tools", "score.py"),
        pred_path,
        VALIDATION_PATH,
        "--out",
        report_path
    ])
    print(f"Pythia report saved to {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["teacher", "untrained", "student"], required=True)
    parser.add_argument("--model-path", default="EleutherAI/pythia-70m")
    parser.add_argument("--output-prefix", default=None)
    args = parser.parse_args()

    if args.mode == "teacher":
        evaluate_ollama_teacher()
    elif args.mode == "untrained":
        evaluate_pythia("EleutherAI/pythia-70m", "untrained_pythia")
    elif args.mode == "student":
        prefix = args.output_prefix or "student_validation"
        evaluate_pythia(args.model_path, prefix)
