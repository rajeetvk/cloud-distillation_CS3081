FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_URI=models/v1 \
    MODEL_VERSION=v1 \
    S3_ENDPOINT=http://seaweedfs.data.svc.cluster.local:8333 \
    MAX_NEW_TOKENS=64 \
    FAULT_INJECT=0

# Install CPU-only PyTorch first to avoid massive CUDA binaries and keep image < 2GB
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service application code and schema (model weights are excluded and downloaded at startup)
COPY schema.json /app/schema.json
COPY main.py /app/main.py

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
