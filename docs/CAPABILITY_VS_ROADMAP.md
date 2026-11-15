# Capability vs. Roadmap — Canonical Accounting

This document is the single source of truth for what RasoSynthTune
has actually built versus what is planned, simulated, or directional.
When documentation, marketing text, or demo scripts conflict with this
file, this file wins.

Status definitions:
- **Built**: verified by reading the code and running it.
- **Built (notebook)**: verified as code in a notebook; requires external GPU compute to run.
- **Partial**: part of the pipeline exists; known gaps listed in the evidence column.
- **Simulated**: the code path exists but returns simulated/mock data or placeholders rather than doing the real work.
- **Roadmap**: design direction, future architecture, or aspirational goals. Not built.

---

## Current Architecture (Engine v2.0.0)

### Stage 1 — Autonomous Dataset Generation

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Dynamic LLM Statutory Discovery | Built (v2.0.0) | `pipeline/planner.py`; dynamically extracts official government authority portals and statutory frameworks without hardcoded dictionaries |
| Multi-turn synthetic generation (SFT, DPO, SimPO, KTO, CoT, Socratic) | Built | `core/generation/`; multi-turn, multi-difficulty generation engines |
| MinHash LSH de-duplication | Built | `core/curation/dedup.py`; MinHash LSH Jaccard similarity thresholding |
| Statutory PII redaction (Aadhaar, PAN, GSTIN, UPI) | Built | `core/curation/pii.py`; Verhoeff $D_8$ dihedral checksum verification for Aadhaar, Mod-36 for GSTIN |
| Benchmark contamination guard | Built | 13-gram exact match quarantine scanner against benchmark test splits |
| 5D Quality Jury (topic, grounding, clarity, completeness, correctness) | Built (v2.0.0) | `api/quality.py` and `/quality` UI; 5 orthogonal quality dimensions evaluated with $\ge 85\%$ canary pass gate |
| Blinded Elo Arena | Built (v2.0.0) | `/research` and `core/evaluation/alignment_judge.py`; head-to-head randomized evaluation with dynamic Elo calibration ($K=32$) |
| HITL review gate & active learning queue | Built | `api/review.py` and `/review` UI; multi-stage review queue (`pending`, `in_review`, `approved`, `rejected`), GroundingDiffModal, DPO export |
| DBOM Merkle provenance & In-Toto attestation | Built (v2.0.0) | `core/export/dbom_attestor.py` and `api/dbom.py`; deterministic SHA-256 Merkle root computation over canonical sample records, ECDSA SECP256R1 signing, and `/api/dbom/verify` |
| Primary Datastore | Built (v2.0.0) | `core/db.py` & `api/server.py`; Supabase PostgreSQL via `asyncpg`, `NullPool` on transaction pooler (port 6543), SSL mode normalization, exponential retry backoff, and no silent SQLite fallback |

### Stage 2 — Model Fine-Tuning & Quantization

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Serverless Modal Cloud GPU fine-tuning (`execution_target=modal`) | Built (v2.0.0) | `finetuning/modal_trainer.py`; real remote execution on dedicated NVIDIA A10G (24GB VRAM) instances when `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` are present, automated SafeTensors packaging, GGUF v3 quantization (`model-q4_k_m.gguf`), and Ollama Modelfile export |
| Local LoRA/QLoRA training (PEFT/Unsloth, `execution_target=local`) | Built | `finetuning/trainer.py`; local CUDA/CPU path with automated BitsAndBytes 4-bit NF4 loading |
| Colab GPU notebook (1-click) | Built (notebook) | `finetuning/RasoSynthTune_FineTuning_Colab.ipynb`; real GPU training when executed in Google Colab |
| Model cards / training telemetry | Built | Automated README model card generation, WebSocket loss telemetry streaming (`/api/finetune/jobs/{id}/stream`), and circular log buffer |
| Evaluation of fine-tuned models | Built | `core/evaluation/` and `scripts/demo_finetune_eval.py`; chrF overlap, token-F1, exact match, and statutory citation grounding |

### Stage 3 — Autonomous Optimisation

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Self-improving dataset/model loop driven by feedback | Roadmap | Direction only. No autonomous optimisation loop is claimed as built. Existing retry/adaptive paths inside synthesis are pipeline mechanics, not Stage 3. |

### Stage 4 — Autonomous AI Engineering

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Autonomous end-to-end AI engineering (system designs, builds, and improves models itself) | Roadmap | Vision only. Nothing in this repo is presented as Stage 4. |

---

## Long-term vision (not a status claim)

Democratising AI development: an autonomous, open, efficient platform
turning raw data and ideas into high-quality training datasets and
specialised models, starting with underserved languages/domains
(Indian languages first); automating discover → synthesise → verify →
curate → optimise → fine-tune → evaluate → improve. Philosophy:
"Don't just use AI. Build the systems that make better AI possible."

---

## Resolved Architectural Gaps in Engine v2.0.0 (2026-11-15)

- **Modal Cloud Fine-Tuning**: Promoted from simulated stub to real serverless execution on NVIDIA A10G via `finetuning/modal_trainer.py`. Real weights packaged as `finetuned_model_lora.zip`, edge GGUF binaries (`model-q4_k_m.gguf`), and Ollama Modelfile.
- **Primary Database**: Integrated Supabase PostgreSQL with `asyncpg`, handling connection poolers (port 6543 / `NullPool`), SSL mapping, statement caching, and strictly eliminating silent SQLite fallback.
- **Dynamic Authority Discovery**: Replaced static topic dictionaries with dynamic LLM statutory extraction (`pipeline/planner.py`), discovering official government portal URLs and statutory acts per domain.
- **Evaluation & Benchmarking**: Added 5-Dimensional Quality Jury ($\ge 85\%$ threshold) and double-blind Elo Arena with dynamic rating calibration.
- **Cryptographic DBOM**: Bound UI and API to functional SHA-256 Merkle root verification and ECDSA SECP256R1 In-Toto digital supply chain signing.
