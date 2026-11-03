# Cloud Computing Mini Project: Knowledge Distillation and Local Cloud Deployment

**Course**: Cloud Computing (CS3081)  
**Roll Number**: 230101078  
**GitHub Repository**: [https://github.com/rajeetvk/cloud-distillation_CS3081](https://github.com/rajeetvk/cloud-distillation_CS3081)  
**Final Submission Tag**: `final`

---

## 1. Project Overview

This project implements end-to-end sequence-level knowledge distillation of a natural language command parser, compressing a 3.8-billion parameter teacher model (`Phi-3.5-mini-instruct`) into a 70-million parameter causal language model (`EleutherAI/pythia-70m`), and deploying it as a containerized, autoscaling microservice on a local `k3d` Kubernetes cluster backed by SeaweedFS S3-compatible object storage.

### Supported Intent & Slot Schema
The parser accepts an English voice utterance and returns a strict 4-key JSON object:
```json
{
  "intent": "alarm_set | alarm_query | calendar_set | calendar_query | calendar_remove | weather_query | datetime_query | recommendation_events",
  "date": "string or null",
  "time": "string or null",
  "place": "string or null"
}
```

---

## 2. Directory Structure

```text
├── cluster/
│   ├── k3d.yaml                  # Local k3d cluster config (ports 8080, 8333)
│   ├── seaweedfs.yaml            # SeaweedFS deployment, service, PVC in data namespace
│   ├── pipeline-workers.yaml     # Parallel teacher labeling jobs in pipeline namespace
│   └── app.yaml                  # Inference service deployment, service, ingress, HPA in app
├── data/
│   ├── commands_pool.jsonl       # 3,000 unlabelled training command pool
│   ├── validation.jsonl          # 100 gold validation commands (evaluation only)
│   ├── schema.json               # Canonical 4-key JSON schema & intent definitions
│   └── rate_card.json            # Hypothetical cloud billing rates for cost estimation
├── datasets/
│   ├── teacher/                  # Sharded raw teacher outputs (shard-0.jsonl, shard-1.jsonl)
│   └── v1/                       # Cleaned training data (train.jsonl) & checksum (train.sha256)
├── models/
│   ├── v1/                       # Trained Pythia-70M student model v1 & model.sha256
│   └── v2/                       # Trained Pythia-70M student model v2 & model.sha256
├── network/
│   ├── subnets.md                # 10.20.0.0/16 subnetting calculation & NACL reasoning
│   ├── nacl.json                 # Stateless NACL rules for public load balancer subnet
│   └── packets_sample.jsonl      # Test packet traces for nacl_sim.py validation
├── prompts/
│   └── teacher_prompt.txt        # System prompt enforcing strict 4-key JSON schema
├── report/
│   ├── report.tex                # LaTeX source for mini project report
│   └── report.pdf                # Compiled report (<= 8 pages)
├── results/
│   ├── teacher_validation.json   # Teacher model accuracy and score report
│   ├── untrained_pythia_validation.json # Baseline untrained Pythia-70M score report
│   ├── student_v1_validation.json       # Distilled student v1 score report
│   ├── student_v2_validation.json       # Distilled student v2 score report
│   ├── benchmark_50_requests.json       # Sequential 50-request container benchmark
│   └── loadtest_stats.csv        # Locust load test metrics (p50, p95, throughput)
├── service/
│   ├── main.py                   # FastAPI service with /parse, /healthz, /readyz, headers
│   ├── Dockerfile                # CPU-only PyTorch image (< 2 GB, pinned versions)
│   └── requirements.txt          # Pinned runtime dependencies
├── tests/
│   └── test_service.py           # Unit tests (schema validation, health checks, fault injection)
├── tools/
│   ├── score.py                  # Official evaluation and accuracy scoring script
│   ├── locustfile.py             # Locust load test with replica and version header tracking
│   ├── nacl_sim.py               # Stateless NACL simulator
│   └── benchmark_service.py      # Automated 50-request performance benchmark
├── training/
│   ├── config.yaml               # Mandatory training hyperparameters & environment versions
│   ├── train.py                  # PyTorch CPU distillation training script
│   ├── evaluate.py               # Model evaluation script against validation.jsonl
│   └── loss.csv                  # Recorded per-epoch training loss
├── .github/workflows/
│   └── ci.yml                    # CI pipeline (gitleaks, lint, unit tests, eval, quality gate)
├── AI_USE.md                     # Declaration of AI tool usage and verification protocols
├── Makefile                      # Standard build & deployment targets (train, up, down, test)
└── make.bat                      # Windows CLI wrapper for Makefile targets
```

---

## 3. Quick Start & Execution Commands

### Prerequisites
- Python 3.11+
- Docker Desktop with WSL2 backend
- `kubectl` and `k3d`
- Ollama with `phi3.5` model pulled (`ollama run phi3.5`)

### Step 1: Cluster Setup & Storage
```bash
# Provision k3d cluster with port forwarding (8080 for Ingress, 8333 for SeaweedFS)
make up
# Or directly:
k3d cluster create cloud-cluster --config cluster/k3d.yaml
kubectl apply -f cluster/seaweedfs.yaml
```

### Step 2: Parallel Teacher Labelling & Data Cleaning (Task 1)
```bash
# Deploy parallel labeling workers in pipeline namespace
kubectl apply -f cluster/pipeline-workers.yaml

# Clean and validate sharded outputs
python worker/clean.py
```

### Step 3: Student Training (Task 2)
```bash
# Test training on 50-example subset (verification)
make train SUBSET=50

# Train student model v1 on CPU (3 epochs)
make train

# Train student model v2 on CPU (4 epochs, for rolling update)
python training/train.py --epochs 4 --output_dir models/v2

# Evaluate all models against validation.jsonl
python training/evaluate.py --mode teacher
python training/evaluate.py --mode untrained
python training/evaluate.py --mode student --model-path models/v1 --output-prefix student_v1
```

### Step 4: Build & Benchmark Container Service (Task 3)
```bash
# Build lightweight CPU container image (< 2 GB)
docker build -t cloud-service:v1 ./service

# Import image into k3d
k3d image import cloud-service:v1 -c cloud-cluster

# Run 50 sequential requests benchmark under 1 CPU / 1 GiB limits
python tools/benchmark_service.py
```

### Step 5: Kubernetes Deployment & Testing (Task 4)
```bash
# Deploy inference service, Ingress, and HPA to namespace app
kubectl apply -f cluster/app.yaml

# Run Locust load test (4 users, 2 minutes)
locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/loadtest
```

### Step 6: Network Subnetting & NACL Simulation (Task 5)
```bash
# Verify NACL rules against packet sample traces
python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check
```

### Step 7: Run Unit Tests & Linting (Task 6)
```bash
# Execute unit tests
python -m unittest discover -s tests -p "test_*.py"

# Run linter
flake8 service training worker tools
```

### Step 8: Cluster Teardown
```bash
make down
# Or directly:
k3d cluster delete cloud-cluster
```
