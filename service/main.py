import os
import sys
import json
import socket
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import boto3
from botocore.config import Config
import jsonschema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("inference_service")

# Required environment variables
MODEL_URI = os.environ.get("MODEL_URI", "models/v1")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:8333")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "64"))
FAULT_INJECT = os.environ.get("FAULT_INJECT", "0")

# Kubernetes Pod name / Hostname
POD_NAME = os.environ.get("HOSTNAME", socket.gethostname())

# Load schema.json
SCHEMA_PATHS = [
    os.path.join(os.path.dirname(__file__), "schema.json"),
    os.path.join(os.path.dirname(__file__), "..", "data", "schema.json"),
    "/app/schema.json"
]
JSON_SCHEMA = None
for sp in SCHEMA_PATHS:
    if os.path.exists(sp):
        try:
            with open(sp, "r", encoding="utf-8") as sf:
                s_data = json.load(sf)
                JSON_SCHEMA = s_data.get("json_schema")
                logger.info(f"Loaded schema from {sp}")
                break
        except Exception as e:
            logger.warning(f"Failed to read schema from {sp}: {e}")

# Allowed intents according to schema
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
VALID_KEYS = {"intent", "date", "time", "place"}

# Global model and tokenizer
tokenizer = None
model = None
is_ready = False


def download_model_from_s3(model_uri: str, target_dir: str):
    """Download model files from S3/SeaweedFS."""
    logger.info(f"Downloading model from S3 URI: {model_uri} using endpoint: {S3_ENDPOINT}")
    os.makedirs(target_dir, exist_ok=True)
    
    # Strip s3:// if present
    uri = model_uri[5:] if model_uri.startswith("s3://") else model_uri
    parts = uri.strip("/").split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""

    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "any")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "any")

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4")
    )

    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel_path = os.path.relpath(key, prefix) if prefix else key
            local_path = os.path.join(target_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            logger.info(f"Downloading s3://{bucket}/{key} -> {local_path}")
            s3.download_file(bucket, key, local_path)
            count += 1

    if count == 0:
        raise RuntimeError(f"No files downloaded from s3://{bucket}/{prefix}")
    logger.info(f"Successfully downloaded {count} files from S3.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tokenizer, model, is_ready
    logger.info("Initializing inference service...")
    local_dir = os.path.join("/tmp", "model_cache", MODEL_VERSION)
    
    # Check if local model directory already exists or needs S3 download
    if os.path.exists(MODEL_URI) and os.path.isdir(MODEL_URI):
        model_path = MODEL_URI
        logger.info(f"Loading model directly from local directory: {model_path}")
    else:
        download_model_from_s3(MODEL_URI, local_dir)
        model_path = local_dir

    logger.info(f"Loading tokenizer and model from {model_path} onto CPU...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float32
    )
    model.eval()
    is_ready = True
    logger.info("Model loaded successfully. Service is ready to serve traffic.")
    yield
    logger.info("Shutting down service...")


app = FastAPI(title="Command Parser Inference Service", lifespan=lifespan)


class ParseRequest(BaseModel):
    text: str


def validate_output(raw_text: str) -> Optional[Dict[str, Any]]:
    """Validate that raw_text conforms strictly to the schema."""
    try:
        data = json.loads(raw_text.strip())
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    if JSON_SCHEMA:
        try:
            jsonschema.validate(instance=data, schema=JSON_SCHEMA)
            return data
        except jsonschema.ValidationError:
            return None

    if set(data.keys()) != VALID_KEYS:
        return None

    if data.get("intent") not in VALID_INTENTS:
        return None

    for slot in ("date", "time", "place"):
        val = data.get(slot)
        if val is not None and not isinstance(val, str):
            return None

    return data


@app.get("/healthz")
async def healthz():
    """Liveness probe endpoint."""
    return Response(content="OK", status_code=200, media_type="text/plain")


@app.get("/readyz")
async def readyz():
    """Readiness probe endpoint."""
    if not is_ready:
        return Response(content="Model not loaded", status_code=503, media_type="text/plain")
    return Response(content="Ready", status_code=200, media_type="text/plain")


@app.post("/parse")
def parse(req: ParseRequest):
    """Command parsing endpoint."""
    headers = {
        "X-Model-Version": MODEL_VERSION,
        "X-Served-By": POD_NAME
    }

    if not is_ready:
        return JSONResponse(
            status_code=503,
            content={"error": "service_not_ready"},
            headers=headers
        )

    # Prompt format used in sequence-level distillation
    prompt = f"Command: {req.text.strip()}\nJSON: "
    inputs = tokenizer(prompt, return_tensors="pt")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    # Extract only the generated tokens after prompt
    generated_ids = output_ids[0][inputs.input_ids.shape[1]:]
    raw_output = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    # Fault injection for testing validation
    if os.environ.get("FAULT_INJECT", FAULT_INJECT) == "1":
        raw_output = "not json"

    # In case model outputs multiple lines or trailing text, find first valid JSON block
    # Check if raw_output itself validates
    validated = validate_output(raw_output)
    if not validated:
        # Fallback: check if the first line or a substring is valid JSON
        first_line = raw_output.split("\n")[0].strip()
        validated = validate_output(first_line)

    if validated is None:
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_model_output"},
            headers=headers
        )

    return JSONResponse(
        status_code=200,
        content=validated,
        headers=headers
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
