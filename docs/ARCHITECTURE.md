# Technical Architecture — Engine v2.0.0

This document outlines the architectural implementation of RasoSynthTune Engine v2.0.0. It documents the active components, data flows, storage layers, and execution backends present in the codebase.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Client & Presentation Layer                           │
│  Next.js 14 Dashboard  │  CLI (`rasosynthtune`)  │  Python SDK (`rasosynth`)    │
│  (Studio, Quality Jury, Review, Blinded Elo Arena, DBOM Verification, Telemetry)│
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ HTTP / JSON / SSE / WebSockets
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                        FastAPI Backend Engine (`api/`)                         │
│  - JWT Auth & Ownership Isolation       - OWASP Security & CSRF Token Guard     │
│  - Dynamic Disk & DB Resolvers          - Observability & Distributed Tracing   │
└───────────┬─────────────────────────────────────────────────────────────┬───────┘
            │                                                             │
┌───────────▼───────────────────────────┐     ┌───────────────────────────▼───────┐
│     Planning & Synthesis Pipeline     │     │   Model Adaptation & Fine-Tuning  │
│  - `pipeline/planner.py`:             │     │  - `finetuning/modal_trainer.py`: │
│    Dynamic LLM Statutory Discovery    │     │    Serverless Modal NVIDIA A10G   │
│  - `core/generation/`:                │     │  - `finetuning/trainer.py`:       │
│    CoT, Socratic, RAG, Tool-Calling   │     │    Local PEFT/Unsloth QLoRA       │
│  - `pipeline/preference_pipeline.py`: │     │  - `finetuning/export_quant.py`:  │
│    SimPO, KTO, and DPO Perturbation   │     │    GGUF (Q4_K_M) & Ollama Export  │
└───────────┬───────────────────────────┘     └───────────────────────────┬───────┘
            │                                                             │
┌───────────▼───────────────────────────┐     ┌───────────────────────────▼───────┐
│      Verification & Provenance        │     │       Primary Storage Layer       │
│  - 5D Quality Jury (85% Gate)         │     │  - Supabase PostgreSQL (asyncpg)  │
│  - Blinded Pairwise Elo Arena         │     │    `NullPool` on Port 6543, SSL   │
│  - `core/export/dbom_attestor.py`:    │     │    JSONB with GIN, pgvector HNSW  │
│    SHA-256 Merkle Root DBOM           │     │  - No Silent SQLite Fallback      │
│  - In-Toto ECDSA SECP256R1 Signatures │     │  - Exponential Backoff Jitter     │
└───────────────────────────────────────┘     └───────────────────────────────────┘
```

---

## 1. Storage & Persistence Tier

### Supabase PostgreSQL Primary Datastore
RasoSynthTune Engine v2.0.0 uses PostgreSQL (hosted on Supabase or self-hosted) as its canonical state store via SQLAlchemy 2.0 and `asyncpg`:

- **Connection Pooler Architecture:** For Supabase transaction pooling on port `6543` (PgBouncer / `pooler.supabase.com`), the engine automatically binds `sqlalchemy.pool.NullPool` to prevent prepared-statement collisions and pooler deadlocks. Direct connections (port `5432`) utilize pooled connections (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`).
- **SSL Enforcement:** SSL handshakes are normalized (`ssl="require"`) for all remote Supabase endpoints.
- **Fail-Fast Boundary (No Silent Fallback):** As implemented in `api/server.py` (`lifespan`), when `POSTGRES_URL` or `DATABASE_URL` is configured, connection failures trigger a 5-attempt exponential retry loop. If PostgreSQL remains unreachable, the server raises a fatal `RuntimeError` and terminates. Silent fallback to SQLite is strictly disabled to prevent split-brain datasets and data loss.
- **Resilient Transactions:** All write transactions execute via `_commit_with_retry` with exponential backoff and randomized jitter to handle transient pooler disconnects.
- **Data Models:**
  - `jobs`: Generation job parameters, curriculum stage, progress, quality scores, and root Merkle hashes.
  - `datasets`: Materialized datasets, record sizes, formats, and JSONB metadata with GIN indexing (`ix_datasets_metadata_gin`).
  - `samples`: Individual instruction-response pairs with 1536-dimensional vector embeddings (`PG_VECTOR`) for HNSW cosine similarity search.
  - `finetune_jobs`: Training runs, base model tags, hyperparameters, loss metrics, and cloud/local target tags.
  - `review_queue`: HITL review queue items with conflict resolution, audit trails, and version increments.

---

## 2. Planning & Statutory Discovery Tier

### Dynamic LLM-Driven Statutory Discovery (`pipeline/planner.py`)
Static, hardcoded topic dictionaries are replaced with a dynamic, LLM-orchestrated planning stage:

- **Dynamic Domain Architecture:** `DatasetPlanner.create_plan` passes the user prompt to an LLM planner via `TaskType.TEXT_GENERATION` at low temperature (`0.2`).
- **Statutory Authority Extraction:** The planner extracts real statutory acts and guidelines (`statutory_frameworks`, e.g., *Central Goods and Services Tax Act 2017*, *Digital Personal Data Protection Act 2023*, *AIS 156/038 EV Standards*) and identifies authoritative government portal domains (`authoritative_sources`, e.g., `https://cbic.gov.in`, `https://heavyindustries.gov.in`, `https://pmjay.gov.in`).
- **Pedagogical Curriculum:** Structures the generation matrix into enterprise difficulty distributions (35% beginner / foundational, 45% intermediate / procedural, 20% advanced / statutory edge-cases) with anti-domain boundary constraints.
- **Diversity Attributes:** Dynamically parameterizes roles, subtopics, and constraints while preventing unintended cross-lingual drift when a specific target language is selected.

---

## 3. Fine-Tuning & Cloud Acceleration Tier

### Serverless Modal NVIDIA A10G Execution (`finetuning/modal_trainer.py`)
Model fine-tuning natively supports serverless cloud GPU execution alongside local PEFT/Unsloth:

- **Automated Execution Target Routing:** `api/finetune.py` checks for `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`. When present, jobs route to `execution_target="modal"` by default.
- **Container Environment:** Modal instances execute inside a custom Debian Slim container with CUDA, PyTorch, Hugging Face `transformers`, `peft`, `trl`, `bitsandbytes`, and `unsloth` pre-installed.
- **Remote QLoRA / DPO Execution:** `train_remote` executes 4-bit NF4 quantized LoRA adaptation on dedicated NVIDIA A10G GPUs (24GB VRAM), streaming live training loss back to the manager.
- **Artifact Packaging:** Post-training hooks package the PEFT adapter into a base64 ZIP bundle, generate Hugging Face model cards, write 4-bit quantized GGUF weights (`model-q4_k_m.gguf`), and generate Ollama `Modelfile` definitions for zero-dependency edge serving.
- **Local Fallback:** When Modal credentials are absent, the engine falls back to local GPU training (`finetuning/trainer.py`) or local accelerated execution without halting the orchestration pipeline.

---

## 4. Evaluation & Quality Governance Tier

### 5D Quality Jury
Quality evaluation enforces a 5-Dimensional objective jury rubric across all generated samples (`api/quality.py`, `frontend/app/(dashboard)/quality/page.tsx`):

1. **Topic Fidelity:** Instruction accurately reflects the target domain and curriculum objective.
2. **Source Grounding:** Verification that responses cite and strictly reflect statutory provisions without hallucination.
3. **Instruction Clarity:** Semantic coherence, absence of template corruption, and syntactic cleanliness.
4. **Response Completeness:** Depth, actionable statutory reasoning, and compliance with structural invariants.
5. **Domain Correctness:** Legal and procedural accuracy under applicable regulatory guidelines.

*Gate Threshold:* A dataset requires an arithmetic composite score and individual dimension scores $\ge 85\%$ to pass the canary gate.

### Blinded Pairwise Elo Arena
A double-blind comparative evaluation harness (`core/evaluation/alignment_judge.py`, `frontend/app/(dashboard)/research/page.tsx`, `cli.py`):
- Randomizes candidate model outputs (Candidate A vs Candidate B) to eliminate model name bias.
- Evaluates instruction-following, coherence, conciseness, and safety deltas.
- Dynamically updates Bradley-Terry Elo ratings and records win/loss/tie outcomes across model checkpoints.

---

## 5. Cryptographic Supply-Chain Provenance (DBOM)

### SHA-256 Merkle Root Attestation & In-Toto Signatures
`core/export/dbom_attestor.py` and `core/export/attestation.py` guarantee dataset integrity:

- **Deterministic Leaf Hashing:** Each dataset record is canonicalized (instruction, response, input, and sorted metadata) and hashed via SHA-256. Storage-specific IDs and volatile timestamps are excluded to ensure deterministic recomputation.
- **Merkle Tree Aggregation:** Hashes are recursively paired and hashed to produce a unique, tamper-evident 64-character SHA-256 Merkle root.
- **In-Toto Provenance Statements:** Dataset metadata, source URIs, license terms, and Merkle digests are packaged into an In-Toto v0.1 compliant statement.
- **ECDSA Digital Signatures:** `DatasetAttestationSigner` signs the statement using an asymmetric ECDSA SECP256R1 keypair. Any modification of a single byte in any sample invalidates the signature and Merkle root.
- **Dynamic Verification Badges:** The `/api/dbom/badge` endpoint generates real-time SVG status badges for integration into model repositories and data catalogs.

---

## 6. Client & Interface Surfaces

- **FastAPI Core (`api/`):** REST API with JWT authentication, role-based access control (Admin/User), CSRF protection, OWASP security headers, and WebSocket log streaming.
- **Developer CLI (`rasosynthtune`):** Unified CLI covering `generate`, `audit`, `attest`, `verify-attestation`, `judge`, `pipeline`, `quantize`, `scrape`, and `serve`.
- **Python SDK (`rasosynth` / `rasosynthtune`):** Programmatic SDK providing client classes for headless synthesis, fine-tuning, and DBOM validation.
- **Next.js 14 Dashboard (`frontend/`):** Enterprise interface featuring the Studio, Dataset Repository, Quality Inspector, HITL Review Queue, Pipelines, Model Manager, and Research Arena.
