#!/usr/bin/env python3
"""
Training script for Sequence-Level Knowledge Distillation (Task 2).
Fine-tunes EleutherAI/pythia-70m on CPU using teacher-generated labels.
"""

import os
import sys
import socket
import argparse
import random
import json
import csv
import hashlib
import yaml
import numpy as np

# Enforce IPv4 to avoid broken IPv6 handshakes in Windows environment
try:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForCausalLM, get_linear_schedule_with_warmup
import urllib.request

class CommandDataset(Dataset):
    def __init__(self, data_records, tokenizer, max_length=128):
        self.examples = []
        for rec in data_records:
            text = rec["text"]
            # Teacher target: exactly the 4-key JSON string
            target_json = json.dumps({
                "intent": rec["intent"],
                "date": rec["date"],
                "time": rec["time"],
                "place": rec["place"]
            }, ensure_ascii=False)

            prompt = f"Command: {text.strip()}\nJSON: "
            prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
            target_ids = tokenizer.encode(target_json, add_special_tokens=False) + [tokenizer.eos_token_id]

            input_ids = prompt_ids + target_ids
            labels = [-100] * len(prompt_ids) + target_ids

            if len(input_ids) > max_length:
                input_ids = input_ids[:max_length]
                labels = labels[:max_length]

            pad_len = max_length - len(input_ids)
            attention_mask = [1] * len(input_ids) + [0] * pad_len
            input_ids = input_ids + [tokenizer.pad_token_id] * pad_len
            labels = labels + [-100] * pad_len

            self.examples.append({
                "input_ids": torch.tensor(input_ids, dtype=torch.long),
                "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
                "labels": torch.tensor(labels, dtype=torch.long)
            })

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def compute_dir_sha256(directory_path, output_checksum_path):
    """
    Computes SHA-256 for all model files in directory in sorted order.
    """
    files = sorted([f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f)) and f != "model.sha256"])
    h = hashlib.sha256()
    with open(output_checksum_path, "w", encoding="utf-8") as out_f:
        for fname in files:
            fpath = os.path.join(directory_path, fname)
            file_hash = hashlib.sha256()
            with open(fpath, "rb") as bf:
                while chunk := bf.read(65536):
                    file_hash.update(chunk)
                    h.update(chunk)
            out_f.write(f"{file_hash.hexdigest()}  {fname}\n")
    return h.hexdigest()

def upload_folder_to_s3(s3_endpoint, bucket, s3_prefix, local_dir):
    """
    Uploads all files in local directory to SeaweedFS S3 bucket.
    """
    print(f"Uploading artifacts from {local_dir} to s3://{bucket}/{s3_prefix}...", flush=True)
    for fname in os.listdir(local_dir):
        fpath = os.path.join(local_dir, fname)
        if os.path.isfile(fpath):
            s3_url = f"{s3_endpoint.rstrip('/')}/{bucket}/{s3_prefix.strip('/')}/{fname}"
            with open(fpath, "rb") as f:
                data = f.read()
            req = urllib.request.Request(s3_url, data=data, method="PUT")
            try:
                with urllib.request.urlopen(req, timeout=2) as resp:
                    print(f"  Uploaded {fname} -> HTTP {resp.status}", flush=True)
            except Exception as e:
                print(f"  Warning: failed to upload {fname} to S3 ({e})", flush=True)

def train():
    parser = argparse.ArgumentParser(description="Train Pythia-70M on sequence distillation")
    parser.add_argument("--config", default="training/config.yaml", help="Path to config.yaml")
    parser.add_argument("--data", default="datasets/v1/train.jsonl", help="Path to cleaned dataset")
    parser.add_argument("--subset", type=int, default=None, help="Train on first N examples only")
    parser.add_argument("--output_dir", default="models/v1", help="Directory to save model")
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs count")
    parser.add_argument("--seed", type=int, default=None, help="Override random seed")
    parser.add_argument("--s3_endpoint", default=os.environ.get("S3_ENDPOINT", "http://127.0.0.1:8333"))
    args = parser.parse_args()

    # Check environment variable SUBSET if not passed as CLI argument
    if args.subset is None and "SUBSET" in os.environ:
        args.subset = int(os.environ["SUBSET"])

    # Load configuration
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    model_name = cfg["model"]["name"]
    max_seq_len = cfg["model"].get("max_sequence_length", 128)
    seed = args.seed if args.seed is not None else cfg["training"]["seed"]
    lr = float(cfg["training"]["learning_rate"])
    batch_size = int(cfg["training"]["batch_size"])
    epochs = args.epochs if args.epochs is not None else int(cfg["training"]["epochs"])
    weight_decay = float(cfg["training"].get("weight_decay", 0.01))

    set_seed(seed)
    device = torch.device("cpu")
    print(f"Using device: {device} (as mandated by assignment requirements)", flush=True)
    print(f"Config loaded: seed={seed}, lr={lr}, batch_size={batch_size}, epochs={epochs}", flush=True)

    # Load dataset
    if not os.path.exists(args.data):
        print(f"Error: Dataset not found at {args.data}", file=sys.stderr)
        sys.exit(1)

    records = []
    with open(args.data, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Apply limits: maximum 1500 records or subset
    train_limit = min(len(records), 1500)
    if args.subset:
        train_limit = min(train_limit, args.subset)
    train_records = records[:train_limit]
    print(f"Training on {len(train_records)} records (subset: {args.subset})", flush=True)

    # Initialize Tokenizer and Model
    print(f"Loading {model_name}...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.to(device)

    dataset = CommandDataset(train_records, tokenizer, max_length=max_seq_len)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    total_steps = len(dataloader) * epochs
    warmup_steps = int(total_steps * cfg["training"].get("warmup_ratio", 0.05))
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps)

    os.makedirs("training", exist_ok=True)
    loss_csv_path = "training/loss.csv"
    epoch_losses = []

    print("\nStarting Training Loop...", flush=True)
    model.train()
    for ep in range(1, epochs + 1):
        running_loss = 0.0
        for step, batch in enumerate(dataloader, 1):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            running_loss += loss.item()

        avg_epoch_loss = running_loss / len(dataloader)
        epoch_losses.append((ep, avg_epoch_loss))
        print(f"Epoch {ep}/{epochs} - Average Loss: {avg_epoch_loss:.4f}", flush=True)

    # Save training/loss.csv (one value per epoch)
    with open(loss_csv_path, "w", newline="", encoding="utf-8") as lf:
        writer = csv.writer(lf)
        writer.writerow(["epoch", "loss"])
        for ep, l_val in epoch_losses:
            writer.writerow([ep, f"{l_val:.6f}"])
    print(f"Saved epoch loss log to {loss_csv_path}", flush=True)

    # Save model and tokenizer
    os.makedirs(args.output_dir, exist_ok=True)
    print(f"Saving model and tokenizer to {args.output_dir}...", flush=True)
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    # Compute checksum
    checksum_file = os.path.join(args.output_dir, "model.sha256")
    total_sha = compute_dir_sha256(args.output_dir, checksum_file)
    print(f"Model artifacts checksum saved to {checksum_file}", flush=True)

    # Upload to SeaweedFS S3
    version_tag = os.path.basename(args.output_dir.rstrip("/\\"))
    upload_folder_to_s3(args.s3_endpoint, "models", version_tag, args.output_dir)
    print("Training and artifact upload complete!\n", flush=True)

if __name__ == "__main__":
    train()
