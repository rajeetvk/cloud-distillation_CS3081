#!/usr/bin/env python3
"""
Cleaner script for Task 1:
Reads raw shard outputs, validates, filters bad records, removes duplicates,
and produces datasets/v1/train.jsonl and datasets/v1/train.sha256.
"""

import os
import sys
import glob
import json
import hashlib

VALID_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events"
}

REQUIRED_KEYS = {"intent", "date", "time", "place"}

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def clean_shards(shard_pattern="datasets/teacher/shard-*.jsonl",
                 output_path="datasets/v1/train.jsonl",
                 checksum_path="datasets/v1/train.sha256"):
    
    shard_files = sorted(glob.glob(shard_pattern))
    if not shard_files:
        print(f"Error: No shard files found matching pattern: {shard_pattern}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(shard_files)} shard file(s): {', '.join(shard_files)}")

    all_raw_records = []
    for s_file in shard_files:
        with open(s_file, "r", encoding="utf-8-sig") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    all_raw_records.append(json.loads(line))
                except Exception as e:
                    print(f"Warning: Corrupt line {line_no} in {s_file}: {e}")

    total_input = len(all_raw_records)

    # Sort all input records primarily by id
    all_raw_records.sort(key=lambda x: str(x.get("id", "")))

    rejected_a = 0  # not valid JSON
    rejected_b = 0  # keys not exactly intent, date, time, place
    rejected_c = 0  # intent not in 8
    rejected_d = 0  # slot not null and not appearing in command text
    duplicates = 0  # duplicate commands
    kept_records = []

    seen_commands = set()

    for item in all_raw_records:
        cid = item.get("id")
        text = item.get("text", "")
        raw_reply = item.get("teacher_raw", "")

        # (a) Replies that are not valid JSON
        try:
            parsed = json.loads(str(raw_reply).strip())
            if not isinstance(parsed, dict):
                rejected_a += 1
                continue
        except Exception:
            rejected_a += 1
            continue

        # (b) Replies whose keys are not exactly intent, date, time, and place
        if set(parsed.keys()) != REQUIRED_KEYS:
            rejected_b += 1
            continue

        # (c) Replies whose intent is not one of the eight
        intent = parsed.get("intent")
        if intent not in VALID_INTENTS:
            rejected_c += 1
            continue

        # (d) Replies with a slot value that is neither null nor text that appears in command
        cmd_text_lower = text.lower()
        bad_slot = False
        for slot in ["date", "time", "place"]:
            val = parsed.get(slot)
            if val is not None:
                if not isinstance(val, str) or val.strip().lower() not in cmd_text_lower:
                    bad_slot = True
                    break
        if bad_slot:
            rejected_d += 1
            continue

        # (e) Duplicate commands (keep the one with the smallest id)
        # Note: we sorted by id first, so the first occurrence is the smallest id
        normalized_cmd = " ".join(cmd_text_lower.split())
        if normalized_cmd in seen_commands:
            duplicates += 1
            continue
        seen_commands.add(normalized_cmd)

        # Kept record
        clean_record = {
            "id": cid,
            "text": text,
            "intent": intent,
            "date": parsed.get("date"),
            "time": parsed.get("time"),
            "place": parsed.get("place")
        }
        kept_records.append(clean_record)

    # Sort final kept records by id
    kept_records.sort(key=lambda x: str(x["id"]))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out_f:
        for rec in kept_records:
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Generate sha256
    checksum = compute_sha256(output_path)
    with open(checksum_path, "w", encoding="utf-8") as cs_f:
        cs_f.write(checksum + "\n")

    # Verification: total_input == (a) + (b) + (c) + (d) + duplicates + kept
    sum_check = rejected_a + rejected_b + rejected_c + rejected_d + duplicates + len(kept_records)

    print("\n" + "="*50)
    print("           DATASET CLEANING SUMMARY TABLE         ")
    print("="*50)
    print(f"Total input records:               {total_input}")
    print(f"Rejected (a) Not valid JSON:       {rejected_a}")
    print(f"Rejected (b) Invalid keys:         {rejected_b}")
    print(f"Rejected (c) Invalid intent:       {rejected_c}")
    print(f"Rejected (d) Hallucinated slots:   {rejected_d}")
    print(f"Duplicates (e) Duplicate text:     {duplicates}")
    print(f"Records kept:                      {len(kept_records)}")
    print("-"*50)
    print(f"Sum of parts:                      {sum_check}")
    print(f"Formula check (input == sum):      {'PASS' if sum_check == total_input else 'FAIL'}")
    print(f"Output saved to:                   {output_path}")
    print(f"SHA-256 Checksum:                  {checksum}")
    print(f"Checksum saved to:                 {checksum_path}")
    print("="*50 + "\n")

if __name__ == "__main__":
    clean_shards()
