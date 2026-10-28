# Architecture — existing components only

This page describes components that exist in the repository. No
service, queue, or deployment topology is described unless it is in
the tree or in the Compose files. The deployed demo is
standalone/in-memory; the Compose stack below is the local
multi-service topology, not a description of the demo.

## Topology (local Docker Compose)

- **Frontend** — Next.js 14 dashboard (`frontend/`: `app/`,
  `components/`, `lib/`). Talks to the FastAPI backend.
- **API** — FastAPI backend (`api/`: `server.py`, `finetune.py`,
  `review.py`, `quality.py`, `auth.py`, `schemas/`, `validation/`,
  `execution/`, `planning/`, `observability/`, `websocket_manager.py`).
- **Workers** — Celery workers (Compose service; monitor on :5555).
  Feature-flagged (`ENABLE_CELERY`); Ray is optional/flagged off by
  default in `.env.example` (`ENABLE_RAY=false`).
- **Data** — PostgreSQL (Compose, `dataset_engine`), Redis, Qdrant.
  The deployed demo does **not** run this stack; it runs
  standalone/in-memory. Do not cite Compose as the demo topology.
- **Storage/export** — dataset exports in JSONL/CSV/Parquet/HF
  formats (`core/export/`, `pipeline/`).

## Backend modules (`api/`, `core/`)

- **Orchestration** — `core/orchestrator_core.py`,
  `core/agent_graph.py` (LangGraph DAG), `core/domain_agent.py`,
  `core/intent.py`, `core/intent_extractor.py`.
- **Generation** — `core/generation/` (CoT, RAG, Socratic,
  multi-turn, preference/DPO, tool-calling synthesizers) and
  `pipeline/construction.py` (standard SFT construction).
- **Quality / validation** — `core/validation/`, `core/curation/`,
  `core/normalization/`, `api/quality.py`, `api/validation/`.
  Note: scoring exists, but there is no single enforced quality
  function end to end yet (see `docs/DATASET_CONTRACT.md`).
- **Provenance (DBOM)** — Merkle-tree code under `core/` (DBOM
  merkle-tree-graph module) producing a SHA-256 Merkle root over
  exported samples. The API root recomputes exactly; the dashboard
  Verify control does not recompute (decorative).
- **Review (HITL)** — `core/review_service.py`, `api/review.py`.
  Jobs pause for reviewer action; the queue fraction shown in the UI
  has not always matched configuration.
- **Provider routing** — `providers/` + `core/provider_router.py`.
  Multi-provider routing with fallback; a "Live/Healthy" badge is
  not evidence of requests (badges showed zero requests on 2026-10-28).
- **Fine-tuning** — `finetuning/trainer.py` (real local PEFT/Unsloth
  path; simulated Modal stub), `finetuning/colab_bridge.py`
  (simulated bridge), `api/finetune.py`. See `docs/FINE_TUNING.md`.
- **Config / secrets** — `core/config.py`, `core/secrets.py`.
  Configuration comes from environment variables; see `.env.example`
  (placeholders only). Never commit `.env`.
- **Observability** — `api/observability/`,
  `core/observability_manager.py`, Prometheus alerts config
  (`config/prometheus_alerts.yml`). Observability existing does not
  make the demo a production deployment.

## Client surfaces

- **CLI** — `cli.py` / `main.py`; console script `rasosynthtune`
  (`generate`, `audit`, `recipe`, `publish`).
- **Python SDK** — `rasosynth/` (`RasoSynthClient`: `synthesize`,
  `verify_dbom`).
- **Dashboard** — Next.js app under `frontend/app/(dashboard)/`
  (datasets, fine-tune, orchestration, home pages).

## What is deliberately NOT in this diagram

No distributed production cluster, no managed GPU fleet, no
autonomous optimisation loop, and no autonomous AI-engineering
service — those are roadmap (Stages 3–4) or, for the GPU fleet,
simulated stubs. Adding any of them here requires code in the tree
first.

