# AI Usage Declaration (`AI_USE.md`)

This document records the artificial intelligence tools utilized during the design, implementation, and evaluation of the Cloud Computing (CS3081) Mini Project, in adherence to academic integrity and project guidelines.

---

## 1. AI Tools Utilized

| Tool / Model | Provider / Version | Role / Context in Project |
| :--- | :--- | :--- |
| **Phi-3.5-mini-instruct** | Microsoft / Ollama (3.8B parameters) | **Teacher Model** (Task 1): Generated sequence-level synthetic JSON labels for 3,000 voice commands from `commands_pool.jsonl`. Ran locally on GPU with strict parameters: `temperature=0`, `seed=42`, `format="json"`. |
| **Antigravity AI Assistant** | Google DeepMind | **Coding & DevOps Assistant**: Assisted in drafting Kubernetes manifests (`k3d.yaml`, `seaweedfs.yaml`, `pipeline-workers.yaml`, `app.yaml`), FastAPI scaffolding, network subnetting calculations, and CI workflow configurations. |

---

## 2. Tasks and Scope of AI Usage

1. **Teacher Dataset Generation (Task 1)**:
   - Used Ollama running Microsoft's `phi3.5:latest` locally to parse natural language commands into a strict 4-key schema (`intent`, `date`, `time`, `place`).
   - Temperature was set to `0` and seed fixed at `42` to ensure reproducible, deterministic outputs across all parallel worker shards.

2. **Code Implementation & DevOps (Tasks 1–6)**:
   - Drafting Kubernetes manifests including StorageClass, SeaweedFS Deployment, HPA, and Traefik Ingress.
   - Structuring modular training script `training/train.py` with CausalLM sequence-level distillation on CPU.
   - Designing unit test suites (`tests/test_service.py`) and CI/CD GitHub Actions pipelines (`.github/workflows/ci.yml`).

3. **Subnetting & Network Simulation (Task 5)**:
   - Validating host address math and subnet masks for address block `10.20.0.0/16`.
   - Designing stateless NACL rule hierarchy for `network/nacl.json`.

---

## 3. Verification and Quality Control Protocols

Every piece of AI-generated output and assistance was subjected to strict verification:

1. **Dataset Integrity (`clean.py`)**:
   - The teacher model's outputs were strictly audited against the project rubric using automated validation rules (a–e):
     - Valid JSON structure.
     - Exact four keys (`intent`, `date`, `time`, `place`).
     - Allowed 8 canonical intents.
     - Strict slot grounding (slot values must be exact substrings of the input command or `null`).
     - Duplicate command deduplication retaining the lowest ID.
   - Exact mathematical reconciliation was verified:
     $$\text{Total Input} = (a) + (b) + (c) + (d) + \text{duplicates} + \text{kept}$$
   - Checksum verified via SHA-256 (`train.sha256`).

2. **Network Rules Verification (`tools/nacl_sim.py`)**:
   - The NACL configuration (`network/nacl.json`) was tested directly against `network/packets_sample.jsonl` using the provided simulator script:
     ```bash
     python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check
     ```
   - Achieved 100% accuracy (6/6 sample packets passed).

3. **Model & Code Validation**:
   - Unit tests run with Python `unittest` (`Ran 6 tests in 0.001s, OK`).
   - Scoring tool `tools/score.py` evaluated student and teacher predictions against `data/validation.jsonl`.
   - CI quality gate configured with `--min-validity 95`.

4. **Secret Scanning**:
   - Ensured zero credentials, private keys, or passwords were committed anywhere in the repository.
