# RasoSynthTune (Engine v2.0.0)

> **License up front:** RasoSynthTune is licensed under the
> [PolyForm Noncommercial License 1.0.0](LICENSE) — non-commercial use only.
> PolyForm Noncommercial is **not** an OSI-approved open-source license.
> Do not describe this project as open source without that qualification.

**What it is.** RasoSynthTune is an enterprise-grade synthetic dataset engineering and model adaptation engine. It orchestrates the full data-to-model lifecycle: statutory knowledge discovery, curriculum-driven synthetic generation (SFT, DPO, SimPO, KTO, CoT), cryptographic Data Bill of Materials (DBOM) attestation, automated 5D jury curation, and hardware-accelerated LoRA/QLoRA fine-tuning for open-weight models across local GPUs and serverless cloud clusters.

**Long-term direction (vision, not built state).** The mission is to democratise sovereign AI development: an autonomous, open, efficient platform turning raw domain material and statutory acts into verified training datasets and domain-specialised models, starting with underserved languages and high-compliance domains (Indian legal, taxation, healthcare, and governance).

> "Don't just use AI. Build the systems that make better AI possible."

Review [docs/CAPABILITY_VS_ROADMAP.md](docs/CAPABILITY_VS_ROADMAP.md) for the verified accounting of built capabilities versus roadmap aspirations.

- Demo: <https://rasosynthtune-indiaai.vercel.app>
- Colab fine-tuning notebook: <https://colab.research.google.com/github/Sourabh-Kumar04/RasoSynth_CUTC/blob/master/finetuning/RasoSynthTune_FineTuning_Colab.ipynb>
- CI / Automated Test Harness: <https://github.com/Sourabh-Kumar04/RasoSynth_CUTC/actions/workflows/ci.yml>

---

## Engine v2.0.0 Core Capabilities

| Capability | Status | Implementation Details |
| :--- | :--- | :--- |
| **Primary Datastore** | Built (v2.0.0) | Managed Supabase PostgreSQL via `asyncpg`. Configured with `NullPool` for transaction poolers (port 6543 / PgBouncer), automated SSL handshake (`ssl=require`), transactional retries with exponential backoff and jitter, and fail-fast startup (no silent SQLite fallback when PostgreSQL is configured). |
| **Cloud GPU Fine-Tuning** | Built (v2.0.0) | Dedicated serverless NVIDIA A10G GPU execution via Modal (`finetuning/modal_trainer.py`). Real remote QLoRA/DPO training, streaming loss metrics, automated LoRA adapter packaging, 4-bit GGUF quantization, and Ollama Modelfile export. |
| **Dynamic Statutory Discovery** | Built (v2.0.0) | LLM-driven statutory authority discovery in `pipeline/planner.py`. Synthesizes curriculum plans with 35/45/20 difficulty splits and extracts verified government portals (`authoritative_sources`) and regulatory acts without hardcoded dictionary limitations. |
| **5D Quality Jury & Elo Arena** | Built (v2.0.0) | 5-Dimensional automated jury (`topic_fidelity`, `source_grounding`, `instruction_clarity`, `response_completeness`, `domain_correctness` with an 85% threshold gate). Head-to-head Blinded Pairwise Elo Arena tracking model win/loss/tie records and Elo rating updates. |
| **Cryptographic DBOM Attestation** | Built (v2.0.0) | Cryptographic Data Bill of Materials using deterministic SHA-256 Merkle trees over canonical sample records (`core/export/dbom_attestor.py`). Generates In-Toto provenance statements signed with ECDSA SECP256R1 and real-time verification badges (`/api/dbom/badge`). |
| **Post-Training Alignment** | Built (v2.0.0) | Reference-free SimPO (length-normalized reward margins), KTO (unpaired binary utility), and DPO preference synthesizers (`pipeline/preference_pipeline.py`). |
| **Statutory PII Sanitization** | Built (v2.0.0) | Real-time streaming de-identification (`/api/quality/redact/stream`) scrubbing Indian statutory identifiers (Aadhaar with Verhoeff checksum validation, PAN, GSTIN, vehicle plates, IFSC, and UPI IDs). |
| **Multi-Provider Routing** | Built (v2.0.0) | Resilient provider router (`core/provider_router.py`) supporting Google Gemini, NVIDIA NIM, Anthropic Claude, OpenAI, Fireworks AI, Featherless, Groq, Ollama, and local vLLM with health telemetry and automatic fallback. |

---

## Quickstart

### Prerequisites
- Python 3.11+ (Python 3.12 recommended in CI)
- Node.js 18+ (for Next.js 14 dashboard)
- PostgreSQL (Supabase or self-hosted) with pgvector extension

### Local Development Setup

```bash
git clone https://github.com/Sourabh-Kumar04/RasoSynth_CUTC.git
cd RasoSynth_CUTC
cp .env.example .env   # Configure database credentials and API keys
pip install -e ".[dev]"

# Start backend API (serves on http://127.0.0.1:8000)
python main.py --host 127.0.0.1 --port 8000

# Health check & OpenAPI documentation:
# curl http://127.0.0.1:8000/health
# http://127.0.0.1:8000/docs
# http://127.0.0.1:8000/playground

# Run full backend test suite
pytest tests/ -q

# Start frontend dashboard (from repo root)
npm run dev --prefix frontend
```

### Docker Compose Multi-Service Stack

```bash
cp .env.example .env
docker compose up --build -d
```

- **Dashboard:** <http://localhost:3001>
- **API Docs:** <http://localhost:8000/docs>
- **Worker Monitor:** <http://localhost:5555> (with `--profile monitoring`)
- **Reverse Proxy:** <http://localhost:80>

---

## Command Line Interface (`rasosynthtune`)

```bash
# 1. Synthesize domain dataset with cryptographic DBOM attestation
rasosynthtune generate --domain "Indian GST & Corporate Tax Compliance" --size 50 --format jsonl

# 2. Cryptographically audit dataset integrity (Merkle tree DBOM, PII, contamination)
rasosynthtune audit --dataset outputs/<dataset-id>/dataset.parquet

# 3. Sign In-Toto supply-chain provenance statement with ECDSA SECP256R1
rasosynthtune attest --dataset outputs/<dataset-id>/dataset.jsonl

# 4. Verify cryptographic signature of an In-Toto attestation bundle
rasosynthtune verify-attestation --attestation outputs/<dataset-id>/dataset.jsonl.attestation.json

# 5. Run automated Blinded LLM-as-a-Judge A/B evaluation between candidate models
rasosynthtune judge --base-model meta-llama/Llama-3.2-1B-Instruct --aligned-model sarvamai/sarvam-2b-v0.5

# 6. Generate edge model quantization recipe (GGUF 4-bit/8-bit with Ollama Modelfile)
rasosynthtune quantize --model-path outputs/model --quantization-format gguf --bits 4

# 7. Execute end-to-end headless data synthesis, DPO preference pair generation, and quantization
rasosynthtune pipeline --domain "Indic Healthcare Diagnostics" --size 100 --synthesis-mode cot
```

---

## Python SDK (`rasosynth`)

```python
from rasosynthtune import RasoSynthClient

client = RasoSynthClient(api_key="YOUR_API_KEY", base_url="http://localhost:8000")

# 1. Dispatch curriculum dataset generation
job = client.synthesize(
    domain="Electric Vehicle Subsidies & AIS Standards",
    target_tokens=50000,
    quality_threshold=0.85,
    export_format="parquet",
    synthesis_mode="cot",
    language="en",
    wait=True,
)
print(f"Job Status: {job.status} | Quality Score: {job.quality_score}")

# 2. Cryptographic DBOM Merkle verification
is_valid = client.verify_dbom(
    dataset_id=job.dataset_id,
    merkle_root=job.merkle_root
)
print(f"DBOM Cryptographic Integrity Verified: {is_valid}")
```

---

## Project Structure

```text
api/               FastAPI backend (endpoints, schemas, auth, DBOM, quality, finetune)
core/              Core engine logic
  generation/      Synthesizers (CoT, Socratic, RAG, tool-calling, multi-turn)
  curation/        5D Jury validation, deduplication, quality heuristics
  crawler/         Anti-bot stealth scraper, TLS JA3/JA4 fingerprint evasion
  export/          DBOM Merkle generator, In-Toto ECDSA signer, HF exporter
  db.py            Database models (Job, Dataset, Sample), asyncpg session management
pipeline/          Planner (LLM statutory discovery), preference pipeline (DPO/SimPO)
finetuning/        Modal A10G runner, local PEFT/Unsloth trainer, GGUF/Ollama exporter
frontend/          Next.js 14 dashboard (Studio, Quality, Review, Arena, DBOM, Pipelines)
main.py            Canonical entry point and CLI command router
workers/           Celery distributed background execution tasks
```

---

## Operational Verification & Limitations

- **Database Resilience:** If `POSTGRES_URL` or `DATABASE_URL` is set, the API strictly enforces PostgreSQL availability. Silent fallback to SQLite is explicitly disabled in production mode to avoid split-brain state.
- **Serverless GPU Requirements:** Remote Modal A10G fine-tuning requires valid `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` environment variables. When unconfigured, fine-tuning gracefully routes to local CUDA/PEFT or local accelerated simulation.
- **Regulatory Clarification:** The DBOM cryptographic attestation confirms byte-level sample integrity and provenance tracking via SHA-256 Merkle roots. It provides evidence for compliance audits but does not constitute legal certification under the EU AI Act or DPDP Act 2023.

---

## Documentation Index

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Comprehensive technical architecture
- [docs/CAPABILITY_VS_ROADMAP.md](docs/CAPABILITY_VS_ROADMAP.md) — Verified capabilities vs roadmap
- [docs/DATASET_CONTRACT.md](docs/DATASET_CONTRACT.md) — Certified dataset quality contracts
- [docs/FINE_TUNING.md](docs/FINE_TUNING.md) — Local PEFT, Modal A10G, and Colab training guides
- [CHANGELOG.md](CHANGELOG.md) — Engine release history

---

## License

[PolyForm Noncommercial License 1.0.0](LICENSE) — strictly non-commercial use only. Not OSI-approved.
