---
namRasoDataset-Agent — Comprehensive Engineering Audit June 2026

## System Overview

RasoDataset-Agent is an autonomous AI dataset generation system using multi-provider orchestration via LangGraph. It discovers, extracts, filters, and constructs high-quality fine-tuning datasets through a multi-agent pipeline. The system is production-deployed with Docker Compose on a remote VM (216.128.153.159).

## Architecture (5-Layer)

```
FastAPI (api/server.py) — API Layer
  → LangGraph Orchestration (core/orchestrator_core.py) — Orchestration
    → Pipeline Stages (pipeline/) — discovery → extraction → filtering → construction → export
      → Provider Router (core/provider_router.py → providers/) — Provider Selection
        → Infrastructure (Redis, PostgreSQL, Qdrant, Celery, Ray)
```

## Components

| Layer | Canonical File | Technology |
|-------|----------------|-----------|
| API Layer | `api/server.py` | FastAPI, Uvicorn |
| Auth | `api/auth.py` | JWT Bearer |
| WebSocket | `api/websocket_manager.py` | Real-time streaming |
| Orchestration | `core/orchestrator_core.py` | LangGraph, DatasetOrchestrator |
| Pipeline | `pipeline/*.py` | Async generators (5 stages) |
| Providers | `providers/base_provider.py` | 11 provider implementations |
| Router | `core/provider_router.py` | Waterfall failover |
| Database | `core/db.py` | PostgreSQL (asyncpg/SQLAlchemy) |
| Cache | `core/cache/` | Multi-layer: memory → Redis → semantic |
| Observability | `core/observability/` | OpenTelemetry, Prometheus, structlog |
| DI | `core/di/` | Container + Factory |
| Auto-Resume | `core/auto_resume.py` | LangGraph checkpoint recovery |
| Frontend | `frontend/` | Next.js 14, React, TypeScript, Tailwind |

## Provider Priority (Waterfall)

1. Google Gemini (degraded - 429 rate limiting)
2. NVIDIA NIM (healthy)
3. Anthropic Claude (unconfigured)
4. OpenAI (unconfigured)
5. HuggingFace (healthy)
6. xAI/Grok (unconfigured)
7. Ollama (local, unconfigured)
8. DeepSeek, Groq, OpenRouter, Together (registered, fallback)

## Dataset Types

`sft`, `rag`, `rlhf`, `classification`, `coding`, `reasoning`, `conversational`, `tool_calling`

## Export Formats

`jsonl`, `csv`, `parquet`, `huggingface`, `sql`, `qdrant`

## Deployment Model

- Docker Compose with 5 services
- Next.js 14 frontend on port 3000
- FastAPI backend on port 8000
- PostgreSQL on port 5432 (now bound to 127.0.0.1)
- Redis on port 6379 (now bound to 127.0.0.1)
- Qdrant on port 6333 (no healthcheck - curl unavailable)

## Security Model

- JWT Bearer token authentication
- CSRF protection with X-CSRF-Token header
- CORS environment-aware configuration
- Rate limiting (token bucket, per-IP)
- Non-root container execution
- UFW firewall with port 8000, 3000, 22 open
