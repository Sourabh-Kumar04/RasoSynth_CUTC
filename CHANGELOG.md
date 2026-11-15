# Changelog

All notable changes to RasoSynthTune are documented in this file.
The version source of truth is `pyproject.toml` (currently `2.0.0`).
This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-11-15

### Added

#### 1. Dynamic Statutory Grounding & LLM Authority Planning
- **Intent Extraction Engine (`core/intent.py`)**: Structured `UserIntent` extraction parser with semantic anti-domain invariants, domain constraint enforcement, and zero-shot fallback handling.
- **Gazette & Regulatory Authority Retrieval (`pipeline/discovery.py`)**: Rate-limited token-bucket discovery engine targeting official legal registries (CBIC, ITAT, AI Kosh) with per-domain concurrency semaphores.
- **7 Autonomous Synthesis Engines (`core/generation/`)**:
  - `cot`: Chain-of-Thought multi-step deductive legal reasoning with AST verification.
  - `socratic`: Socratic dialectic questioning surfacing latent boundary assumptions.
  - `preference`: Paired contrastive instruction generation for DPO and SimPO.
  - `tool_calling`: Structured JSON function signatures with Pydantic v2 validation.
  - `curriculum`: Pedagogical 4-tier difficulty sequencing.
  - `multimodal`: Scanned document and tabular OCR extraction into Markdown.
  - `rag`: Statutory citation anchoring against official gazettes.

#### 2. Supabase PostgreSQL Primary Database with Resilient Connection Pooling
- **SQLAlchemy 2.0 Async Core (`core/db.py`)**: Asynchronous database abstraction (`AsyncDB`) supporting both PostgreSQL (via `asyncpg`) and SQLite WAL mode.
- **Native NoSQL Document Storage**: Uses native PostgreSQL `JSONB` with GIN indexing (`ix_samples_metadata_gin`) for fast schema-less metadata queries.
- **Resilient Connection Pooling**:
  - Automatic detection of Supabase transaction poolers (port `6543`) and PgBouncer, seamlessly applying `NullPool` to prevent prepared statement conflicts.
  - Configured `statement_cache_size = 0` and `prepared_statement_cache_size = 0` for transaction-pooled asyncpg connections.
  - Standard connection pooling with `pool_size = 10`, `max_overflow = 20`, `pool_pre_ping = True`, and `pool_recycle = 3600`.
  - Non-destructive automated database migrations on engine initialization (`create_tables`).

#### 3. Serverless Modal A10G Cloud GPU Fine-Tuning & SafeTensors Generation
- **Serverless Cloud GPU Trainer (`finetuning/modal_trainer.py`)**:
  - Modal app deployment (`rasosynthtune-finetune`) executing on dedicated NVIDIA A10G GPUs (24GB VRAM).
  - Multi-paradigm alignment: Supervised Fine-Tuning (SFT), Direct Preference Optimization (DPO), Simple Preference Optimization (SimPO), and Kahneman-Tversky Optimization (KTO) via Hugging Face `trl`.
  - Unsloth FastLanguageModel integration for accelerated 4-bit QLoRA loading and gradient checkpointing.
  - Authentic `SafeTensors` adapter weight packaging (`adapter_model.safetensors`, `adapter_config.json`) returned as an in-memory compressed archive.

#### 4. Blinded Arena Evaluation & Dynamic Elo Rating Calibration
- **Blinded Pairwise Arena (`frontend/app/(dashboard)/research/page.tsx`)**: Double-blind head-to-head model comparison studio for evaluating candidate model answers on complex legal prompts.
- **Dynamic Elo Recalibration**: Real-time Elo scoring update rule ($K=32$) computing expected win probabilities and updating model standings upon user votes.
- **Benchmark Contamination Quarantine**: 13-gram exact match quarantine scanner preventing training sample contamination against MMLU, GSM8K, and IndicGLUE benchmark splits.

#### 5. Merkle Tree Provenance Attestation & Data Nutrition Labels
- **Cryptographic DBOM Generator (`core/dbom/` & `frontend/components/dbom/merkle-tree-graph.tsx`)**:
  - Recursive SHA-256 Merkle tree calculation over sample content hashes.
  - Exportable Data Bill of Materials (`dbom.json`) manifest containing root hashes, leaf counts, and transform signatures.
- **Statutory PII Masking Engine**:
  - Dihedral group $D_5$ **Verhoeff checksum algorithm** implementation for validating and masking 12-digit Indian Aadhaar identification numbers.
  - Automated regex and checksum masking for PAN, GSTIN, UPI, and vehicle registration numbers.
- **Data Nutrition Cards**: Visual compliance reporting for DPDP Act 2023 and EU AI Act Article 10 readiness.

#### 6. Human Review Queue & Workflow State Machine
- **Persistent Review Queue (`api/review.py`, `core/db.py`)**: Database-backed review table (`review_queue`) supporting multi-stage state transitions (`pending`, `in_review`, `approved`, `rejected`, `flagged`).
- **Grounding Diff Inspector (`frontend/components/review/grounding-diff-modal.tsx`)**: Visual side-by-side diffing comparing synthetic training text against raw statutory gazette excerpts.
- **Inline Editor**: Allows reviewers to correct statutory citations directly in the browser, triggering an automated hash recalculation.

---

### Changed
- Replaced previous mock-mode fine-tuning placeholders with authentic execution targets: local PyTorch/PEFT training and remote Modal A10G execution.
- Updated documentation across `docs/` to explicitly document all system limitations, license boundaries (PolyForm Noncommercial 1.0.0), and small-sample pilot caveats.
- Unified canonical CLI entry points under `main.py` and `cli.py` for headless operations (`generate`, `audit`, `recipe`, `quantize`, `judge`, `pipeline`).

---

### Removed
- Removed ungrounded unit economics multiple claims from documentation until traced execution billing benchmarks are established.
- Removed legacy unindexed metadata queries in favor of PostgreSQL GIN-indexed JSONB document structures.
