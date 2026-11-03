FROM python:3.11-slim

WORKDIR /app

# Copy worker script, prompt, and data
COPY worker/worker.py /app/worker.py
COPY prompts/teacher_prompt.txt /app/prompts/teacher_prompt.txt
COPY data/commands_pool.jsonl /app/data/commands_pool.jsonl

ENV PYTHONUNBUFFERED=1
ENV TEACHER_URL="http://host.k3d.internal:11434"
ENV S3_ENDPOINT="http://seaweedfs.data.svc.cluster.local:8333"
ENV INPUT_PATH="/app/data/commands_pool.jsonl"
ENV PROMPT_PATH="/app/prompts/teacher_prompt.txt"
ENV OUTPUT_DIR="/app/datasets/teacher"

CMD ["python", "-u", "/app/worker.py"]
