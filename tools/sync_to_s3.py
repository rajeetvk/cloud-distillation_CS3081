import os
import sys
import socket
import boto3
from botocore.config import Config

try:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

ENDPOINT = os.environ.get("S3_ENDPOINT", "http://127.0.0.1:8334")

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id="any",
    aws_secret_access_key="any",
    config=Config(signature_version="s3v4")
)

def upload_folder(bucket, prefix, local_dir):
    print(f"Uploading {local_dir} -> s3://{bucket}/{prefix}...")
    for root, _, files in os.walk(local_dir):
        for fname in files:
            local_path = os.path.join(root, fname)
            rel_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
            s3_key = f"{prefix.strip('/')}/{rel_path}" if prefix else rel_path
            print(f"  Uploading {fname} ({os.path.getsize(local_path)} bytes) to s3://{bucket}/{s3_key}...")
            s3.upload_file(local_path, bucket, s3_key)
    print(f"Done uploading {local_dir} to s3://{bucket}/{prefix}!\n")

if __name__ == "__main__":
    upload_folder("models", "v1", "models/v1")
    upload_folder("models", "v2", "models/v2")
    upload_folder("datasets", "v1", "datasets/v1")
    print("All uploads completed successfully!")
