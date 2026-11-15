# Production Deployment Guide: RasoSynthTune

This document outlines deployment procedures for the RasoSynthTune dataset engineering pipeline, audit engine, and fine-tuning control plane.

```
┌──────────────────────────────────────┐
│       Next.js 14 Frontend            │  Vercel Edge Platform
│  https://rasosynthtune-indiaai.      │  Static & Dynamic SSR, React Query,
│             vercel.app               │  WebSocket Stream Client
└──────────────────┬───────────────────┘
                   │ HTTPS / WSS (`NEXT_PUBLIC_API_URL`)
                   ▼
┌──────────────────────────────────────┐
│       Backend API Server             │  Render Web Service (Docker Runtime)
│     `rasosynthtune-api`              │  • FastAPI Application Server
│                                      │  • MinHash LSH Deduplication Engine
│                                      │  • Cryptographic DBOM Audit Ledger
│                                      │  • SQLAlchemy 2.0 AsyncPG Engine
└──────────┬───────────────────┬───────┘
           │                   │
           ▼                   ▼
┌──────────────────────┐  ┌────────────────────────────────────┐
│ Supabase PostgreSQL  │  │   Modal Serverless Compute         │
│ Transaction Pooler   │  │   • NVIDIA A10G Cloud GPU          │
│ (Port 6543, SSL Req) │  │   • QLoRA / DPO / SimPO / KTO      │
└──────────────────────┘  └────────────────────────────────────┘
```

---

## 1. Managed PostgreSQL Setup (Supabase / RDS / Neon)

Production environments require a dedicated PostgreSQL 15+ database with the `uuid-ossp` and `pgvector` extensions enabled.

### 1.1 Connection Strings & Normalization
Configure the database connection via either `POSTGRES_URL` or `DATABASE_URL`. The backend automatically parses, normalizes, and validates the connection URI:
- Upgrades URI prefixes `postgres://` and `postgresql://` to `postgresql+asyncpg://`.
- Converts `sslmode=require` query parameters to `ssl=require` for `asyncpg` driver compatibility.
- Strips PgBouncer parameters (`pgbouncer=true`, `supa=true`) that are invalid in direct asyncpg connection strings.

### 1.2 Supabase Transaction Pooler (Port 6543) Handling
When connecting through Supabase's transaction pooler (`pooler.supabase.com` on port `6543` or when `pgbouncer=true` is used), client-side connection pooling and prepared statement caches must be disabled to prevent connection collisions:

- **Pool Class**: Automatically switches from `QueuePool` to `NullPool`.
- **Prepared Statement Cache**: Automatically forces `statement_cache_size=0` and `prepared_statement_cache_size=0`.
- **Direct Connection Alternative (Port 5432)**: Direct connections utilize `QueuePool` with `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, and `pool_recycle=3600`.

Example configuration in environment:
```env
POSTGRES_URL=postgresql://postgres.projectref:password@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require
```

---

## 2. Deploying Backend API to Render

The backend control plane executes API orchestration, synthesis task routing, data validation, and Modal dispatching.

### 2.1 Blueprint Deployment (`render.yaml`)
1. Link your repository in the [Render Dashboard](https://dashboard.render.com/).
2. Select **New > Blueprint** and choose the repository. Render reads `render.yaml` and sets up the service:
   - **Service Name**: `rasosynthtune-api`
   - **Runtime**: `docker` (`./Dockerfile`)
   - **Region**: `oregon`
   - **Plan**: `free` or standard compute
   - **Health Check Path**: `/health`

### 2.2 Environment Variables Matrix

| Variable | Category | Required | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | Networking | Yes | Set to `8000` |
| `ENVIRONMENT` | Runtime | Yes | Set to `production` |
| `AIR_GAPPED_MODE` | Runtime | Yes | Set to `false` for cloud API routing |
| `WORKERS` | Runtime | Yes | Set to `1` (single-process event loop) |
| `MALLOC_ARENA_MAX`| Memory | Yes | Set to `2` to prevent memory fragmentation |
| `JWT_SECRET` | Security | Yes | 64-character cryptographically secure string |
| `DOWNLOAD_SIGNING_SECRET` | Security | Yes | 32+ character dedicated secret for presigned URLs |
| `POSTGRES_URL` | Database | Yes | Supabase or PostgreSQL connection string |
| `MODAL_TOKEN_ID` | Fine-Tuning | Optional | Modal API Token ID for serverless GPU jobs |
| `MODAL_TOKEN_SECRET` | Fine-Tuning | Optional | Modal API Token Secret |
| `GEMINI_API_KEY` | Model Provider | Optional | Google Gemini API Key |
| `GROQ_API_KEY` | Model Provider | Optional | Groq High-Speed Inference API Key |
| `NVIDIA_API_KEY` | Model Provider | Optional | NVIDIA NIM API Key |
| `SARVAM_API_KEY` | Model Provider | Optional | Sarvam AI Indic Model API Key |
| `HF_TOKEN` | Model Provider | Optional | Hugging Face Hub Access Token |

---

## 3. Deploying Next.js 14 Frontend to Vercel

The frontend is built on Next.js 14 App Router, Radix UI, TanStack Query, and Tailwind CSS.

### 3.1 Vercel Deployment Configuration
1. Import the repository into the [Vercel Dashboard](https://vercel.com/).
2. Set the **Root Directory** to `frontend`.
3. Framework Preset: **Next.js**.
4. Configure Environment Variables:
   - `NEXT_PUBLIC_API_URL`: The deployed Render backend URL (e.g., `https://rasosynthtune-api.onrender.com`).
5. Click **Deploy**.

### 3.2 Real-Time Communication Architecture
- **WebSockets**: The client opens WebSocket connections to `NEXT_PUBLIC_API_URL/ws/jobs/{id}` and `/api/finetune/jobs/{id}/stream` for sub-second telemetry, step execution, and live training loss streaming.
- **Asynchronous Decoupling**: Dataset generation and fine-tuning tasks run asynchronously in the background. Vercel serverless function timeouts do not interrupt long-running generation or training runs.

---

## 4. Serverless GPU Execution on Modal

To run QLoRA training without provisioning static GPU servers:

1. Create a Modal account at [modal.com](https://modal.com).
2. Generate API tokens:
   ```bash
   pip install modal
   modal setup
   ```
3. Set `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` in the Render environment variables.
4. When a fine-tuning job is initiated via the API (`POST /api/finetune/jobs`) or UI, the backend provisions an on-demand NVIDIA A10G container, executes training, streams loss updates via WebSockets, and retrieves adapter weights back to the API server.

---

## 5. Verification & Health Monitoring

Execute automated health verification against your deployment:

```bash
# 1. Health check and dependency status
curl -i https://rasosynthtune-api.onrender.com/health

# Expected response:
# HTTP/1.1 200 OK
# {"status":"healthy","database":"connected","version":"1.0.0"}

# 2. Verify active model providers
curl -s https://rasosynthtune-api.onrender.com/providers | jq .

# 3. Test dataset generation pipeline
curl -X POST https://rasosynthtune-api.onrender.com/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"target_domain": "Healthcare Claims", "num_samples": 5}'
```

---

## 6. Security & Operational Hardening

- **Database Connection Fail-Closed**: In `production` mode, the application fails at startup if `POSTGRES_URL` cannot establish an active connection; it will not silently revert to an ephemeral SQLite database.
- **Presigned Download URLs**: Dataset downloads require HMAC-SHA256 signatures generated via `DOWNLOAD_SIGNING_SECRET`. Requests with expired or missing signatures return `403 Forbidden`.
- **Credential Storage**: Database credentials, LLM API tokens, and Modal secrets must never be committed to repository files. Use secret managers or hosting environment panels exclusively.
