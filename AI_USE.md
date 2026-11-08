# AI Use

This project was built with AI assistance, as the handout permits ("You'll be using AI and no
one can stop you. But do use it with your eyes wide open."). This file records what was used,
for what, and how the output was checked.

## Tools used
- **An AI coding assistant (Google Antigravity)** — to scaffold the repository, write initial
  Python implementations, Dockerfiles, Kubernetes manifests, the NACL rules and subnet plan,
  the CI workflow, and the first drafts of the report and documentation.
- **Ollama + phi3.5** — the *fixed teacher model* required by the handout (not a coding aid):
  used to label the command pool with temperature 0, seed 42, and strict JSON formatting.

## What AI was used for
| Area | AI's role | My role |
|------|-----------|---------|
| Teacher prompt (`prompts/teacher_prompt.txt`) | Drafted instructions and few-shot examples for the 4-key schema | Reviewed against Section 4 slot extraction rules; tested locally via Ollama and verified JSON structure |
| Worker + `clean.py` (Task 1) | Wrote modulo sharding worker and cleaning validation logic | Ran parallel workers, verified the mathematical sum check ($0 + 1 + 14 + 74 + 50 + 2,861 = 3,000$), and verified the SHA-256 checksum |
| Training / eval scripts (Task 2) | Drafted PyTorch sequence-level distillation script and evaluation routines | Diagnosed GPT-NeoX subword tokenizer space-prefix bugs, ran CPU training for 3 and 4 epochs, verified `loss.csv`, and evaluated checkpoints with `tools/score.py` |
| Service + Dockerfile (Task 3) | Wrote FastAPI service endpoints and CPU-only Dockerfile | Identified and fixed the critical asyncio event-loop blocking issue by converting `async def parse` to synchronous `def parse`, verified health probes (`/healthz`, `/readyz`), tested `FAULT_INJECT=1`, and benchmarked 50 sequential requests |
| K8s manifests (Task 4) | Wrote Deployment, Service, Ingress, and HPA configurations | Diagnosed SeaweedFS volume exhaustion and added `-volume.max=100`; injected `preStop` hook (`sleep 5`) to prevent connection drops during rolling update; executed and measured cold start, Locust load balancing, and self-healing recovery |
| NACL + subnets (Task 5) | Suggested CIDR subnet boundaries and drafted `nacl.json` rules | Re-calculated usable IP ranges, broadcast addresses, and host capacities by hand; verified stateless bidirectional rule logic using `tools/nacl_sim.py` (6/6 sample vectors passed) |
| CI + Makefile (Task 6) | Drafted GitHub Actions `ci.yml`, `Makefile`, and `make.bat` | Tested the 5-stage pipeline, verified Gitleaks secret scanning, and proved quality gate enforcement by verifying a deliberately failing run with untrained Pythia-70M |
| Report / README (Task 7) | Drafted document outline and architectural descriptions | Replaced all placeholders with measured empirical results from `results/`; calculated exact cost model and SLO error budget; formatted report in LaTeX |

## How I checked what the AI gave me
- **Ran everything myself.** No result in the report is copied from the AI; every measured number
  (scores, latency, memory, cold-start, cost) comes from actual execution runs on my laptop and
  the verifiable log outputs preserved in `results/`.
- **Used the provided checkers.** I validated implementations against the official ground-truth tools:
  `tools/nacl_sim.py` for stateless NACL evaluation, `tools/score.py` for model prediction accuracy,
  and Locust for cluster load testing.
- **Unit testing and linting.** I executed the test suite in `tests/` covering schema validation,
  readiness probes, and fault injection, and enforced PEP8 compliance with Flake8 in CI.
- **Read and debugged the code.** Where the AI generated suboptimal or flawed code, I identified
  the root cause, debugged it, and made necessary architectural changes (detailed below).

## Limitations I am aware of
- **Model capacity limitations**: A 70M parameter student model trained on ~1,500 noisy teacher labels
  cannot achieve full generalization across ambiguous utterances. The validation results in our report
  (99% validity and 30% full-frame accuracy for Student v1; 100% validity and 34% full-frame accuracy
  for Student v2) reflect these real-world trade-offs honestly.
- **AI hallucinations and runtime oversights**: The AI assistant generated plausible-looking implementations
  that failed during real-world runtime execution:
  1. *FastAPI Event-Loop Starvation*: The AI originally drafted the inference handler as `async def parse()`.
     During PyTorch CPU inference, this blocked Python's main asyncio event loop for 5 seconds, starving
     the Kubernetes `/healthz` probe and causing CrashLoopBackOff restarts. I caught this by inspecting
     `kubectl describe pod` and resolved it by changing the route to synchronous `def parse()`, allowing
     FastAPI to dispatch inference to a background worker threadpool.
  2. *SeaweedFS Volume Exhaustion*: The default SeaweedFS master config capped writable volumes at 5, causing
     S3 bucket creation to fail silently. I fixed this by passing `-volume.max=100` in `cluster/seaweedfs.yaml`.
  3. *Tokenizer Boundary Merge*: The AI initially used naive string slicing for prompt masking, which split
     GPT-NeoX subword tokens like ` {"`. I resolved this by tokenizing the prompt and JSON target separately
     before concatenating token ID arrays.
  Running the code locally and verifying it with the provided evaluation tools was essential to discovering
  and fixing these defects.
