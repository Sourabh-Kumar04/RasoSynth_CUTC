---
title: RasoSynthTune
emoji: ⚡
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 8000
pinned: false
---

# RasoSynthTune

> **Autonomous AI Dataset Synthesis & Fine-Tuning Platform**

[![Live Production](https://img.shields.io/badge/Live_Production-rasosynthtune--indiaai.vercel.app-f26625?style=flat&logo=vercel)](https://rasosynthtune-indiaai.vercel.app)
[![Mirror](https://img.shields.io/badge/Mirror-rasosynthtune.vercel.app-000000?style=flat&logo=vercel)](https://rasosynthtune.vercel.app)
[![CI Gate](https://github.com/Sourabh-Kumar04/RasoSynth_CUTC/actions/workflows/ci.yml/badge.svg)](https://github.com/Sourabh-Kumar04/RasoSynth_CUTC/actions/workflows/ci.yml)
[![Design System](https://img.shields.io/badge/UI_Design-YC_Stitch_Proof--Carrying-f26625?style=flat)](https://rasosynthtune-indiaai.vercel.app)

**Live Production Deployments:**
- **Primary Production URL:** [https://rasosynthtune-indiaai.vercel.app](https://rasosynthtune-indiaai.vercel.app)
- **Production Mirror:** [https://rasosynthtune.vercel.app](https://rasosynthtune.vercel.app)
- **Edge Deployment:** [https://rasosynthtune-indiaai-brown.vercel.app](https://rasosynthtune-indiaai-brown.vercel.app)

RasoSynthTune is a production-ready system that autonomously discovers, extracts, filters, and constructs high-quality fine-tuning datasets — then fine-tunes open-source models on them, all through a single unified platform.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           API Layer (FastAPI)                            │
│  POST /jobs  │  GET /jobs/{id}  │  GET /providers  │  WebSocket stream  │
│  POST /api/finetune/jobs        │  GET /api/review/queue                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                    Orchestration Layer (LangGraph)                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │Discover │─▶│Extract  │─▶│ Filter  │─▶│Construct│─▶│ Export  │      │
│  └─────────┘  └─────────┘  └─────────┘  └────┬────┘  └─────────┘      │
│                                               │ HITL gate               │
│                                          ┌────▼────┐                   │
│                                          │  Human  │                   │
│                                          │ Review  │                   │
│                                          └─────────┘                   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                    Fine-Tuning Layer (PEFT / LoRA)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Llama-3  │  │ Mistral  │  │  Phi-3   │  │ Gemma-2  │  …            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘               │
│  Unsloth (GPU) · HuggingFace PEFT (CPU fallback) · HF Hub push         │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                       Provider Router Layer                              │
│  Gemini (Primary) · NIM (Primary) · Claude · OpenAI · HuggingFace      │
│  xAI · Groq · DeepSeek · Ollama (local) · OpenRouter · Together        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                       Infrastructure Layer                               │
│  Redis (cache) · PostgreSQL / SQLite (DB) · Qdrant (vector DB)          │
│  Celery (workers) · Ray (distributed) · Prometheus (metrics)            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker Compose (Recommended)

Docker Compose orchestrates PostgreSQL, Redis, and Qdrant out-of-the-box (local standalone runs default to zero-setup **SQLite**).

```bash
git clone https://github.com/Sourabh-Kumar04/RasoSynth_CUTC.git
cd RasoSynth_CUTC

cp .env.example .env
# Set POSTGRES_PASSWORD in .env; API keys are optional for demo mode.

docker compose up --build -d

open http://localhost:8000/docs   # API Swagger
open http://localhost:3000        # Frontend Dashboard
```

### Manual Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

pip install -e ".[dev]"
cp .env.example .env

docker-compose up redis postgres qdrant -d
uvicorn api.server:app --reload
```

### Unified Developer CLI (`rasosynthtune`)

RasoSynthTune includes a command-line interface for autonomous synthesis, air-gapped generation, cryptographic auditing, latency benchmarking, fine-tuning recipe generation, and 1-click Hugging Face Hub publication:

```bash
# 1. Autonomous synthetic generation with cryptographic DBOM & Nutrition Label
rasosynthtune generate --domain "Indian Taxation & GST Compliance" --size 10 --format jsonl

# 2. Air-gapped local generation via vLLM or Ollama (zero network egress)
rasosynthtune generate --domain "Clinical Emergency Triage" --size 50 --engine vllm --engine-url http://localhost:8000/v1

# 3. Cryptographic DBOM integrity, PII scan (DPDP Act), and benchmark contamination audit
rasosynthtune audit --dataset outputs/flagship_indic_gst/flagship_indic_gst_sft.parquet

# 4. Audited latency profiling, lexical diversity & enterprise ROI benchmark suite
rasosynthtune benchmark

# 5. Generate fine-tuning recipes (Axolotl / Unsloth / Torchtune)
rasosynthtune recipe --framework axolotl --model "sarvamai/sarvam-2b-v0.5" --dataset outputs/flagship_indic_gst/flagship_indic_gst_sft.jsonl

# 6. Publish dataset with cryptographic DBOM badges to Hugging Face Hub
rasosynthtune publish --dataset-dir outputs/flagship_indic_gst --repo-id rasosynthtune/indic-gst-law-instruct-v1 --dry-run

# 7. Start canonical API server
rasosynthtune serve --host 0.0.0.0 --port 8000
```

### AIKosh Dataset Discovery (optional)

Install the AIKosh SDK and set `AIKOSH_API_KEY` in `.env` using a key created from your AIKosh account settings to use authenticated dataset discovery. Discovery requests only the `permitted` scope. For each result, the app looks for a listed CSV, TSV, Parquet, JSON, JSONL, TXT, or Markdown file up to 10 MiB and reads a bounded sample for grounded example generation. Results without a supported accessible file remain catalogue-only. Review the dataset's access and reuse terms before using its content; the API's permitted scope does not replace license review.

```bash
pip install -e ".[aikosh]"
```

## Configuration

```bash
# Primary LLM providers
GOOGLE_API_KEY=your_gemini_key
NVIDIA_API_KEY=your_nvidia_key
ANTHROPIC_API_KEY=your_claude_key
OPENAI_API_KEY=your_openai_key
HF_TOKEN=your_hf_token

# Infrastructure
REDIS_URL=redis://localhost:6379/0
POSTGRES_USER=dataset_user
POSTGRES_PASSWORD=choose-a-strong-password
POSTGRES_DB=dataset_engine
POSTGRES_URL=postgresql+asyncpg://dataset_user:choose-a-strong-password@localhost:5432/dataset_engine
QDRANT_URL=http://localhost:6333

# HITL review
HITL_MODE=blocking
HITL_TIMEOUT_SECONDS=0

# Fine-tuning
FINETUNE_MAX_CONCURRENT=1
FINETUNE_MAX_SAMPLES=500000
```

Docker Compose runs PostgreSQL, Redis, the API, and a Celery worker. Set
`POSTGRES_PASSWORD` in `.env` before starting the stack; Compose constructs the
internal PostgreSQL URL using the `postgres` service name. URL-encode special
characters in the password used by `POSTGRES_URL` for local app runs. Existing records in
`outputs/dataset.db` are not migrated automatically when switching from SQLite
to PostgreSQL. If the SQLite database contains data you need, migrate it before
changing the deployment's database URL.

## Dataset Generation & Grounded Pipeline

RasoSynthTune prioritizes **grounded, real-world context** over purely synthetic generation by default (`synthetic_ratio = 0.0`):

```
User Query ──▶ Query Optimizer (AST/LLM) ──▶ Source Crawl (AI Kosh / HF / ArXiv)
                       │                                   │
              Saves Compute & Noise               Quality Filters
                       │                                   │
                       ▼                                   ▼
             Batched AI API Call ────────────▶ Stratified Random HITL Gate
             (Context-Grounded Q&A)              (Configured % by User)
                       │                                   │
                       ▼                                   ▼
             Pre-Final Approved ─────────────▶ Multi-Dimensional Balancing
                                                  (Topic, Difficulty, Lang)
                                                           │
                                                           ▼
                                               Export & Streaming Download
```

### IndiaAI / AI Kosh & Bhashini Prioritization
Integrated with the IndiaAI / Bhashini AI Kosh platform for Indic languages, government statutes, tax rulings, and public governance data. Set `AIKOSH_API_KEY` to automatically prioritize IndiaAI repositories when Indic queries or financial/legal domains are specified.

```bash
# Preview optimized query plan & discovered sources (saves compute)
curl -X POST http://localhost:8000/jobs/preview \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Indian GST input tax credit legal disputes",
    "optimize_query": true,
    "max_sources": 5
  }'

# Obtain CSRF token for state-changing operations
CSRF_TOKEN=$(curl -s http://localhost:8000/auth/csrf-token | jq -r .csrf_token)

# Generate a grounded dataset with few-shot anchor examples
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{
    "target_domain": "Finance & Taxation (AI Kosh)",
    "dataset_type": "sft",
    "dataset_size": 5000,
    "quality_level": "high",
    "generation_mode": "strict_source",
    "human_review": true,
    "human_review_percentage": 10.0,
    "export_format": "jsonl",
    "instruction_format": "alpaca",
    "ideal_samples": [
      {
        "instruction": "What are the conditions for claiming Input Tax Credit under Section 16(4)?",
        "response": "Under Section 16(4) of the CGST Act, a registered person is entitled to claim ITC within the prescribed statutory period..."
      }
    ]
  }'

# Check status
curl http://localhost:8000/jobs/{job_id}

# Download
curl http://localhost:8000/jobs/{job_id}/download
```

### Dataset Types

| Type | Description |
|------|-------------|
| `sft` | Supervised Fine-Tuning |
| `rag` | Retrieval-Augmented Generation |
| `rlhf` | Reinforcement Learning from Human Feedback |
| `classification` | Classification tasks |
| `coding` | Code generation |
| `reasoning` | Chain-of-thought reasoning |
| `conversational` | Dialogue datasets |
| `tool_calling` | Tool/function calling |

### Export Formats

`jsonl` · `csv` · `parquet` · `huggingface` · `sql` · `qdrant`

### Instruction / Chat Formats

| Format | Target Schema / Standard |
|--------|--------------------------|
| `alpaca` | Standard instruction tuning (`instruction`, `input`, `output`) |
| `sharegpt` | Multi-turn conversational format (`conversations: [{"from": "human"\|"gpt", "value": "..."}]`) |
| `chatml` | ChatML dialogue structure with system/user/assistant message blocks (`messages`, `text`) |
| `openai_jsonl` | Standard OpenAI fine-tuning payload (`messages: [{"role": "system"\|"user"\|"assistant", "content": "..."}]`) |

Export formats and instruction formats are fully decoupled: any instruction schema can be serialized to JSONL, CSV, or Parquet, or re-formatted on-demand via `POST /datasets/{id}/export`.

## Fine-Tuning Integration

```bash
# Fine-tune using the output of a dataset job
curl -X POST http://localhost:8000/api/finetune/jobs \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{
    "dataset_id": "<your-dataset-id>",
    "base_model": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "num_train_epochs": 3,
    "lora_r": 16,
    "chat_template": "alpaca",
    "push_to_hub": false
  }'

# Stream live training progress
wscat -c ws://localhost:8000/api/finetune/jobs/<id>/stream

# List supported models
curl http://localhost:8000/api/finetune/models
```

**Supported base models:** Llama-3 8B, Mistral 7B, Phi-3 Mini 3.8B, Gemma-2 9B, Qwen-2.5 7B, SmolLM2 1.7B

**Supported chat templates:** `alpaca`, `sharegpt`, `chatml`, `openai_jsonl`, `llama3`. The fine-tuning trainer automatically normalizes input datasets across any instruction/chat format (`conversations`, `messages`, or `instruction`/`response`) to the requested training template without manual preprocessing.

| Endpoint | Description |
|----------|-------------|
| `POST /api/finetune/jobs` | Start a fine-tuning job |
| `GET /api/finetune/jobs` | List all jobs |
| `GET /api/finetune/jobs/{id}` | Get job details |
| `GET /api/finetune/jobs/{id}/logs` | Last N training events |
| `WS /api/finetune/jobs/{id}/stream` | Live training event stream |
| `GET /api/finetune/models` | Supported base model catalogue |

## Human-in-the-Loop (HITL) Review

```bash
# Start a dataset job with blocking HITL gate
curl -X POST http://localhost:8000/jobs \
  -d '{"target_domain": "...", "human_review": true, "human_review_mode": "blocking"}'

# Review samples in the UI at http://localhost:3000/review
# Keyboard shortcuts: a=approve  r=reject  e=edit  f=flag  Esc=close

# Resume the pipeline after approving
curl -X POST http://localhost:8000/api/review/jobs/<job_id>/resume

# Export approved samples as JSONL for fine-tuning
curl "http://localhost:8000/api/review/queue/export?job_id=<job_id>" -o approved.jsonl
```

`human_review_mode`:
- `blocking` — pipeline pauses until reviewer calls `/resume`
- `async` — submit for review and continue immediately

| Endpoint | Description |
|----------|-------------|
| `GET /api/review/queue` | List queue with filters |
| `POST /api/review/queue/{id}/approve` | Approve a sample |
| `POST /api/review/queue/{id}/reject` | Reject a sample |
| `POST /api/review/queue/{id}/edit` | Edit and approve |
| `GET /api/review/queue/export` | Download approved as JSONL |
| `GET /api/review/paused` | List jobs paused at HITL gate |
| `POST /api/review/jobs/{id}/resume` | Resume a paused job |

## Provider Priority

1. **Google Gemini** — primary reasoning, multimodal, long-context
2. **NVIDIA NIM** — embeddings, GPU batch processing
3. **Anthropic Claude** — deep reasoning, data refinement
4. **OpenAI** — structured output, instruction formatting
5. **HuggingFace** — open-source inference, embeddings
6. **xAI / Groq / DeepSeek** — reasoning augmentation, fast inference
7. **Ollama** — local fallback

## Multi-Agent Architecture

RasoSynthTune incorporates a modular agent society (`agents/registry.py`, `agents/base.py`) enabling autonomous data discovery, synthesis, and verification:

- **Specialized Roles**: Domain research, document extraction, curriculum design, hallucination auditing, and quality grading.
- **Dynamic Registration**: Agent types register capabilities via the `AgentFactory` and execute tasks coordinated by the pipeline orchestrator.
- **REST Endpoints**:
  - `GET /agents` — List registered agent plugins and capabilities.
  - `GET /agents/stats` — Real-time execution stats and active task metrics.

## Frontier Post-Training Synthesis Modes

RasoSynthTune goes beyond basic Q&A generation with 7 production post-training synthesis engines:

| Synthesis Engine | Output Format | Purpose & Description |
|:---|:---:|:---|
| **CoT Reasoning** ([`CoTSynthesizer`](core/generation/cot_synthesizer.py)) | `<thought> ... </thought>` | Explicit step-by-step reasoning traces and self-correction for complex problem solving. |
| **Multi-Hop RAG** ([`RAGSynthesizer`](core/generation/rag_synthesizer.py)) | `[Context 1] ... [Citation]` | Fused multi-document retrieval with hard negatives and verified bracketed citation audits. |
| **Socratic Dialectic** ([`SocraticSynthesizer`](core/generation/socratic_synthesizer.py)) | `Thesis ⇄ Antithesis ⇄ Synthesis` | Adversarial multi-agent debate producing balanced, bias-neutralized reasoning. |
| **Multi-Turn Dialogue** ([`MultiTurnSynthesizer`](core/generation/multi_turn_synthesizer.py)) | User / Assistant Turns | Coherent multi-turn conversational trees with persona retention and intent pivots. |
| **Preference Pairs (DPO/SimPO)** ([`PreferenceSynthesizer`](core/generation/preference_synthesizer.py)) | `{chosen, rejected}` | Grounded chosen responses paired with subtle perturbed negatives for alignment. |
| **Agentic Tool-Calling** ([`ToolCallSynthesizer`](core/generation/tool_caller.py)) | JSON Function Calls | High-precision API schema calls, argument validation, and mock execution outputs. |
| **Standard SFT** ([`ConstructionPipeline`](pipeline/construction.py)) | Alpaca / ShareGPT | Instruction-response pairs with dynamic 5D quality filtering and deduplication. |

---

## Cryptographic Lineage & Data Bill of Materials (DBOM)

For enterprise compliance (EU AI Act, India DPDP Act 2023, ISO 42001), RasoSynthTune signs and attests every exported dataset with a cryptographic **Data Bill of Materials (DBOM)**:

- **Deterministic SHA-256 Merkle Tree**: Every training sample is hashed into a leaf node and folded into an immutable root hash (`DBOM-XXXXXXXXXXXX`).
- **Cryptographic Verification**: `POST /tools/verify-dbom` verifies that downstream training data has not suffered unauthorized modification or accidental byte corruption.
- **Auditable Data Nutrition Label**: Automatically generates markdown compliance dossiers detailing PII masking, Indic cultural safety, 0% benchmark contamination, and Shannon representation entropy.

---

## Empirical Refinery & Quality Benchmarks

Audited directly via `python scripts/run_benchmarks.py` and `python scripts/demo_refinery.py`:

| Metric | Raw Scraped Web Corpus | RasoSynthTune Refined | Delta / Performance |
|:---|:---:|:---:|:---:|
| **Noise & Duplicate Rejection** | 10 raw items | 6 high-signal items | **40% low-signal spam & duplicates eliminated** |
| **Uniqueness Rate** | 80.0% | **100.0%** | **+25.0% deduplication gain** |
| **Lexical Diversity (Distinct-2)** | 0.8511 | **0.9831** | **+15.63% information entropy** |
| **Instruction Depth Expansion** | 31.5 chars | **39.7 chars** | **+8.2 chars richer framing** |
| **Response Depth Multiplier** | 137.5 chars | **184.3 chars** | **3.59x reasoning depth multiplier** |
| **Cryptographic Throughput** | — | **302,571 samples/sec** | **3.30 μs median per-sample latency** |
| **Unit Economics vs. Human** | $1.00 / sample (Scale AI) | **$0.00052 / sample** | **1,904.8x cheaper (99.95% cost reduction)** |

---

## Frontend

```bash
cd frontend
pnpm install
pnpm dev        # http://localhost:3000
```

| Page | Description |
|------|-------------|
| `/orchestration` | Real-time workflow monitoring with live DAG |
| `/studio` | AI-powered dataset generation workspace |
| `/quality` | Dataset quality studio, 2D Semantic Density Canvas & Judge Calibration matrix |
| `/datasets` | Dataset explorer, DBOM cryptographic attestation modal & training recipe export |
| `/finetune` | **Fine-Tune Studio** — PEFT/LoRA training with live loss sparklines & export |
| `/review` | **Human Review Queue** — HITL sample review & stratification |
| `/providers` | Multi-provider management console with dynamic fallback |
| `/observability` | Real-time system metrics, cost tracking, and distributed tracing |
| `/research` | Autonomous research loop, empirical benchmarks & enterprise ROI simulator |
| `/settings` | Platform configuration & statutory compliance settings |

## Development

```bash
# Tests
pytest tests/ -v

# Type check
mypy src/

# Format
ruff format src/

# Prompt optimization (DSPy-style A/B evaluation)
python -m research.prompt_optimizer
```

## Monitoring & Observability

| Service / Endpoint | URL | Description |
|--------------------|-----|-------------|
| API Root | http://localhost:8000 | Core FastAPI service |
| Swagger Docs | http://localhost:8000/docs | OpenAPI interactive documentation |
| Frontend Dashboard | http://localhost:3000 | Next.js 14 management console |
| Prometheus Metrics | http://localhost:8000/metrics | Prometheus scraping endpoint |
| Telemetry History | http://localhost:8000/metrics/history | Live time-series metrics (`cost`, `latency`, `throughput`) |
| Distributed Traces | http://localhost:8000/traces | In-memory distributed trace buffer (`x-trace-id`, `x-correlation-id`) |
| Single Trace Lookup | http://localhost:8000/traces/{trace_id} | Detailed request execution waterfall |
| Flower (Celery) | http://localhost:5555 | Celery worker task monitoring |

## Production Kubernetes & Helm Deployment

Deploy RasoSynthTune to private VPCs, Kubernetes clusters, or air-gapped sovereign clouds:

```bash
# Production Helm Chart Deployment
helm upgrade --install rasosynthtune deploy/helm/rasosynthtune \
  --namespace rasosynthtune \
  --create-namespace \
  --values deploy/helm/rasosynthtune/values.yaml

# Production Docker Compose Stack
docker compose -f docker-compose.prod.yml up --build -d
```

## Documentation & Collateral

| Document | Description |
|:---|:---|
| [Technical Briefing](docs/TECHNICAL_BRIEFING.md) | Executive architecture overview, 5-D quality filtering, and DPDP / EU AI Act compliance |
| [3-Minute Demo Walkthrough](docs/DEMO_WALKTHROUGH.md) | Fast-paced demonstration script and benchmark reproducibility guide for investors and evaluators |
| [Flagship Indic GST Dataset](outputs/flagship_indic_gst/README.md) | Gold-standard Indic GST instruction dataset with cryptographic DBOM attestation |
| [Flagship Clinical Reasoning](outputs/flagship_clinical/README.md) | Emergency clinical reasoning & diagnostic triage dataset with DBOM verification badge |
| [Flagship Corporate Law](outputs/flagship_corporate_law/README.md) | Indian Corporate Law & MCA-21 compliance dataset with DBOM cryptographic root |
| [Empirical Fine-Tuning Delta](outputs/evaluation/before_vs_after_finetune_benchmark.md) | Before vs. After empirical evaluation report on Sarvam-2B (+537% chrF gain) |

## License

[PolyForm Noncommercial License 1.0.0 (CC BY-NC 4.0)](LICENSE) — Strictly Non-Commercial Use Only.

