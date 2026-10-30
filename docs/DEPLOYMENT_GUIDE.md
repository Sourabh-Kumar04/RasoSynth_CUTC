# Production Deployment Guide: RasoSynthTune

Complete guide to deploying the **Autonomous Dataset Generation Pipeline** and **Fine-Tuning Studio**.

---

## Architecture Overview

```
┌─────────────────────────────────┐
│     Live Frontend (Vercel)      │  Next.js 14 App Router, YC Stitch Theme
│ https://rasosynthtune-indiaai.  │  (Zero-serverless timeout limits on browser)
│           vercel.app            │
└────────────────┬────────────────┘
                 │ HTTP / WebSocket (NEXT_PUBLIC_API_URL)
                 ▼
┌─────────────────────────────────┐
│       Backend API Server        │  FastAPI, LangGraph Orchestrator
│   (Render / Railway / Fly.io)   │  • Autonomous Discovery & Scraping
│                                 │  • Extraction & Deduplication (MinHash)
│                                 │  • Synthetic Generator (Gemini/OpenAI/Groq)
│                                 │  • Cryptographic DBOM Audit (SHA-256)
│                                 │  • SQLite / Postgres Auto-fallback
└────────────────┬────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌──────────────┐     ┌──────────────┐
│  Free Cloud  │     │ Dedicated GPU│
│  Colab / GPU │     │ Celery Worker│
│ (Unsloth/LoRA│     │(NVIDIA Docker│
│   Notebook)  │     │  Compose)    │
└──────────────┘     └──────────────┘
```

---

## 1. Deploy the Backend API (Complete Pipeline)

The backend runs the complete dataset generation pipeline, DBOM signing, quality scoring, and job management. It requires **no GPU** because synthetic generation uses external API providers (Gemini, Groq, OpenAI, Anthropic).

### Option A: 1-Click Deploy on Render
1. Push your repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com/), select **New > Blueprint**.
3. Select this repository. Render automatically reads `render.yaml` and provisions:
   - Web Service: `rasosynthtune-api`
   - Postgres Database: `rasosynthtune-db` (or runs SQLite fallback automatically)
4. Set your LLM API Keys in the Render dashboard:
   - `GEMINI_API_KEY` (or `OPENAI_API_KEY`, `GROQ_API_KEY`)
5. Your API URL will be: `https://rasosynthtune-api.onrender.com`.

### Option B: 1-Click Deploy on Railway
1. In [Railway](https://railway.app/), click **New Project > Deploy from GitHub repo**.
2. Select this repository. Railway detects `railway.json` and builds via `Dockerfile`.
3. Add Environment Variables:
   - `GEMINI_API_KEY` or `OPENAI_API_KEY`
   - `PORT=8000`
4. Generate a domain (e.g., `https://rasosynthtune-production.up.railway.app`).

### Option C: Fly.io Deployment
```bash
fly launch --config fly.toml
fly secrets set GEMINI_API_KEY="your-key" OPENAI_API_KEY="your-key"
fly deploy
```

### Option D: Docker Compose on VPS / EC2
```bash
cp .env.example .env
# Edit .env and paste your API keys
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 2. Connect the Live Vercel Frontend

The frontend is already live at:
**`https://rasosynthtune-indiaai.vercel.app`**

To connect it to your newly deployed backend:
1. Open your Vercel Dashboard for `rasosynthtune-indiaai`.
2. Navigate to **Settings > Environment Variables**.
3. Add or update:
   - **Key**: `NEXT_PUBLIC_API_URL`
   - **Value**: `https://your-api-domain.com` (e.g. `https://rasosynthtune-api.onrender.com`)
4. Trigger a **Redeploy** from the Deployments tab.
5. All live requests from the studio, visualizer, telemetry, and review queue now stream directly to your deployed backend.

---

## 3. Fine-Tuning Execution

Training 1.7B–8B models requires an **NVIDIA GPU with 16GB–24GB VRAM**. You have 3 options:

### Option 1: 1-Click Google Colab (Free GPU — Zero Infrastructure Cost)
The platform includes an end-to-end Unsloth fine-tuning notebook:
1. Click the **Open in Colab (Free GPU)** button on the `/finetune` dashboard, or open:
   [`finetuning/RasoSynthTune_FineTuning_Colab.ipynb`](file:///mnt/d/Sourabh_Workspace/00_Academics/RasoSynth_CUTC/finetuning/RasoSynthTune_FineTuning_Colab.ipynb)
2. Select **Runtime > Change runtime type > T4 GPU**.
3. Enter your generated dataset URL (or upload `dataset.jsonl`).
4. Run all cells: it applies QLoRA (4-bit), trains in 15–20 minutes with Unsloth (2x-5x faster), and saves your adapter weights or pushes them directly to Hugging Face Hub.

### Option 2: Serverless GPU with Modal
Run serverless QLoRA on a cloud NVIDIA A10G with zero server setup:
```bash
pip install modal
modal setup
modal run finetuning/modal_trainer.py --dataset-content "$(cat outputs/my_dataset.jsonl)" --base-model unsloth/llama-3-8b-Instruct
```

### Option 3: Dedicated GPU Celery Worker (In-Cluster)
If deploying on a machine with an NVIDIA GPU (e.g., RunPod, Lambda Labs, AWS G5/G6):
1. Install NVIDIA Container Toolkit on host.
2. Ensure GPU driver is enabled in `docker-compose.yml`:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: all
             capabilities: [gpu]
   ```
3. Install fine-tuning dependencies:
   ```bash
   uv pip install -e ".[finetuning]"
   ```
4. Jobs created in the Fine-Tune Studio will execute directly on local GPU hardware and stream training metrics over WebSockets.

---

## Verification & Health Check

After deploying:
```bash
# Check API health
curl https://your-api-domain.com/health

# Verify provider connectivity
curl https://your-api-domain.com/providers

# Test dataset creation
curl -X POST https://your-api-domain.com/jobs \
  -H "Content-Type: application/json" \
  -d '{"target_domain": "Healthcare Claims", "num_samples": 5}'
```

---

## Production Security & Operational Configuration

- **Download Signing Secret (`DOWNLOAD_SIGNING_SECRET`)**: Mandatory dedicated 32+ character secret for presigned dataset downloads and previews. Presigned URL minting fails closed when absent (no fallback to `JWT_SECRET`).
- **Token Revocation & Expiry**: Tokens are revoked in-memory on logout (`/auth/logout`) for single-process deployments. Configure short `JWT_EXPIRATION_HOURS` (e.g. 1–24 hours) as the boundary against process restarts.
- **Account Lockout Policy**: 5 failed login attempts in 15 minutes lock an account for 15 minutes. Admin credentials are gated by default; use `unlock_user()` or process restart if escape is needed.
- **Orchestration Retry Semantics**: Step retry (`POST /orchestration/steps/{step_id}/retry`) relaunches the complete pipeline from the stored job configuration. Targeted stage resume is handled via `POST /checkpoints/{checkpoint_id}/restore`.
