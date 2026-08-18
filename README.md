# RasoDataset-Agent

A production-ready autonomous AI dataset generation system that discovers, extracts, filters, and constructs high-quality fine-tuning datasets using multi-provider AI orchestration.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐

│                           API Layer (FastAPI)                            │
│  POST /jobs  │  GET /jobs/{id}  │  GET /providers  │  WebSocket stream  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                    Orchestration Layer (LangGraph)                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  │Discover │───▶│Extract │───▶│ Filter  │───▶│Construct│───▶│ Export  │ │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│       │              │              │              │                    │
│       └──────────────┴──────────────┴──────────────┘                    │
│                         Multi-Agent Graph                               │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                       Provider Router Layer                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │  Gemini    │  │  NIM       │  │  Claude    │  │  OpenAI    │        │
│  │  (Primary) │  │  (Primary) │  │  (Fallback)│  │  (Fallback)│        │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │  Hugging   │  │  xAI       │  │  Ollama    │  │  vLLM      │        │
│  │  Face      │  │            │  │  (Local)   │  │            │        │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                       Infrastructure Layer                               │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐    │
│  │  Redis  │  │PostgreSQL│  │ Qdrant  │  │ Celery   │  │   Ray     │    │
│  │ (Cache) │  │   (DB)   │  │ (VecDB) │  │(Workers)│  │(Cluster)  │    │
│  └─────────┘  └──────────┘  └─────────┘  └─────────┘  └────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Using Docker Compose (Recommended)

The project is pre-configured to use **SQLite** as its default database, providing a **single-command launch** experience with zero PostgreSQL setup. 

We also support a **Demo Mode (Simulated Backend)** that lets you test the entire frontend dashboard (including job runs, real-time WebSocket progress, provider failover, and metrics panels) completely offline.

```bash
# Clone and start
git clone <repo>
cd ai-dataset-engineer

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys (optional if running in Demo Mode!)

# Start all services
docker compose up --build -d

# Access the API Swagger Docs
open http://localhost:8000/docs

# Access the Frontend Control Center Dashboard
open http://localhost:3000
```

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env

# Start infrastructure
docker-compose up redis postgres qdrant -d

# Run the application
uvicorn api.server:app --reload
```

## Configuration

Configure API keys in `.env`:

```bash
# Primary providers
GOOGLE_API_KEY=your_gemini_key
NVIDIA_API_KEY=your_nvidia_key

# Fallback providers
ANTHROPIC_API_KEY=your_claude_key
OPENAI_API_KEY=your_openai_key
HF_TOKEN=your_hf_token
XAI_API_KEY=your_xai_key

# Infrastructure
REDIS_URL=redis://localhost:6379/0
# PostgreSQL (Production)
# POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/dataset_engine
# SQLite (Local Dev / Hackathon Default)
POSTGRES_URL=sqlite+aiosqlite:///outputs/dataset.db
QDRANT_URL=http://localhost:6333
```

## API Usage

### Create a Dataset Generation Job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "target_domain": "machine learning",
    "dataset_type": "sft",
    "dataset_size": 1000,
    "quality_level": "standard",
    "export_format": "huggingface"
  }'
```

### Check Job Status

```bash
curl http://localhost:8000/jobs/{job_id}
```

### Download Dataset

```bash
curl http://localhost:8000/jobs/{job_id}/download
```

### List Providers

```bash
curl http://localhost:8000/providers
```

## Provider Priority

Default provider priority (configurable in `.env`):

1. **Google Gemini** - Primary for reasoning, multimodal, long-context
2. **NVIDIA NIM** - Primary for embeddings, GPU batch processing
3. **Anthropic Claude** - Fallback for deep reasoning, data refinement
4. **OpenAI** - Fallback for structured output, instruction formatting
5. **Hugging Face** - Open-source inference, embeddings
6. **xAI** - Reasoning augmentation
7. **Ollama** - Local fallback model

## Dataset Types Supported

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

## Export Formats

- `jsonl` - JSON Lines
- `csv` - Comma-separated values
- `parquet` - Apache Parquet
- `huggingface` - HuggingFace Dataset format
- `sql` - PostgreSQL
- `qdrant` - Vector DB ingestion

## Development

### Prompt Optimization & Evaluation (DSPy-style)

You can run our programmatically driven A/B prompt evaluation engine. It tests prompt variants, performs factual consistency checks, and evaluates performance using t-test statistical significance:

```bash
python -m research.prompt_optimizer
```

### Run Tests

```bash
pytest tests/ -v
```

### Type Checking

```bash
mypy src/
```

### Code Formatting

```bash
ruff format src/
```

## Frontend Platform

A production-grade React/Next.js frontend is included for visual workflow management.

```bash
cd frontend
pnpm install
pnpm dev
```

Access the frontend at http://localhost:3000

### Frontend Features

| Page | Description |
|------|-------------|
| `/orchestration` | Real-time workflow monitoring dashboard with pulsing step nodes |
| `/studio` | AI-powered dataset generation workspace |
| `/quality` | Dataset quality dashboard with dynamic **Strategic Segmentation** |
| `/datasets` | Dataset explorer and validation |
| `/providers` | Multi-provider management console |
| `/finetune` | **Fine-Tune Studio** — PEFT/LoRA fine-tuning with live training logs |
| `/review` | **Human Review Queue** — HITL sample review with keyboard shortcuts |
| `/observability` | System metrics and tracing |
| `/research` | Provider benchmarking |
| `/settings` | Platform configuration |

See [frontend/README.md](frontend/README.md) for details.

## Fine-Tuning Integration

After generating a dataset you can fine-tune an open-source model directly:

```bash
# Start a fine-tuning job (uses the JSONL output of a dataset job)
curl -X POST http://localhost:8000/api/finetune/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "<your-dataset-id>",
    "base_model": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "num_train_epochs": 3,
    "lora_r": 16,
    "chat_template": "alpaca"
  }'

# Stream live training progress
wscat -c ws://localhost:8000/api/finetune/jobs/<id>/stream

# List supported base models
curl http://localhost:8000/api/finetune/models
```

Supported base models: Llama-3 8B, Mistral 7B, Phi-3 Mini, Gemma-2 9B, Qwen-2.5 7B, SmolLM2 1.7B.

Uses [Unsloth](https://github.com/unslothai/unsloth) for 2-4× GPU speedup when available; falls back to plain HuggingFace PEFT on CPU.

Install fine-tuning dependencies:

```bash
pip install -e ".[finetuning]"
# Optional GPU acceleration:
pip install unsloth
```

## Human-in-the-Loop (HITL) Review

Enable reviewer approval gates in the dataset generation pipeline:

```bash
# Start a job with blocking HITL (pipeline pauses after construction)
curl -X POST http://localhost:8000/jobs \
  -d '{"target_domain": "...", "human_review": true, "human_review_mode": "blocking"}'

# Review samples at http://localhost:3000/review
# Then resume the pipeline:
curl -X POST http://localhost:8000/api/review/jobs/<job_id>/resume

# Export approved samples as JSONL for fine-tuning:
curl http://localhost:8000/api/review/queue/export?job_id=<job_id> -o approved.jsonl
```

`human_review_mode` options:
- `blocking` — pipeline pauses and waits for reviewer to call `/resume`
- `async` — samples submitted for review, pipeline continues immediately

| Endpoint | Description |
|----------|-------------|
| `GET /api/review/queue` | List review queue with filters |
| `POST /api/review/queue/{id}/approve` | Approve a sample |
| `POST /api/review/queue/{id}/reject` | Reject a sample |
| `POST /api/review/queue/{id}/edit` | Edit and approve |
| `GET /api/review/queue/export` | Download approved as JSONL |
| `GET /api/review/paused` | List jobs paused at HITL gate |
| `POST /api/review/jobs/{id}/resume` | Resume a paused job |

## Monitoring

- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **Prometheus Metrics**: http://localhost:8000/metrics
- **Flower**: http://localhost:5555

## License

MIT