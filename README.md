# RasoSynthTune

> **Autonomous AI Dataset Synthesis & Fine-Tuning Platform**

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

Uses **SQLite** by default — zero PostgreSQL setup required.

```bash
git clone https://github.com/Sourabh-Kumar04/RasoSynth_CUTC.git
cd RasoSynth_CUTC/ai-dataset-engineer

cp .env.example .env
# Edit .env with your API keys (optional — Demo Mode works without them)

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

### Fine-Tuning Dependencies (optional)

```bash
pip install -e ".[finetuning]"   # peft, trl, transformers, accelerate
pip install unsloth              # optional: 2-4× GPU speedup
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
POSTGRES_URL=sqlite+aiosqlite:///outputs/dataset.db   # SQLite (default)
# POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/rasosynthtune
QDRANT_URL=http://localhost:6333

# HITL review
HITL_MODE=blocking
HITL_TIMEOUT_SECONDS=0

# Fine-tuning
FINETUNE_MAX_CONCURRENT=1
FINETUNE_MAX_SAMPLES=500000
```

## Dataset Generation

```bash
# Generate a dataset
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "target_domain": "machine learning",
    "dataset_type": "sft",
    "dataset_size": 1000,
    "quality_level": "standard",
    "export_format": "huggingface"
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

## Fine-Tuning Integration

```bash
# Fine-tune using the output of a dataset job
curl -X POST http://localhost:8000/api/finetune/jobs \
  -H "Content-Type: application/json" \
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
| `/quality` | Dataset quality dashboard |
| `/datasets` | Dataset explorer and validation |
| `/finetune` | **Fine-Tune Studio** — PEFT/LoRA training with live logs |
| `/review` | **Human Review Queue** — HITL sample review |
| `/providers` | Multi-provider management console |
| `/observability` | System metrics and tracing |
| `/research` | Provider benchmarking |
| `/settings` | Platform configuration |

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

## Monitoring

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Prometheus Metrics | http://localhost:8000/metrics |
| Flower (Celery) | http://localhost:5555 |

## License

[PolyForm Noncommercial License 1.0.0 (CC BY-NC 4.0)](LICENSE) — Strictly Non-Commercial Use Only.

