# RasoSynthTune

> **License up front:** RasoSynthTune is licensed under the
> [PolyForm Noncommercial License 1.0.0](LICENSE) — non-commercial use only.
> PolyForm Noncommercial is **not** an OSI-approved open-source license.
> Do not describe this project as open source without that qualification.

**What it is.** RasoSynthTune turns raw domain material and ideas into
instruction datasets for training specialised models, and provides
fine-tuning paths for open-weight models. It is a dataset-engineering and
fine-tuning toolkit with a dashboard, a CLI, and a Python SDK — not a
finished autonomous AI engineer.

**Long-term direction (vision, not built state).** The direction is to
democratise AI development: an autonomous, open, efficient platform that
turns raw data and ideas into high-quality training datasets and
specialised models, starting with underserved languages and domains
(Indian languages first). The mission is to automate the data-to-model
lifecycle — discover, synthesise, verify, curate, and optimise datasets;
fine-tune open-weight models (LoRA/QLoRA, including resource-constrained
hardware); evaluate; and improve continuously via feedback.

> "Don't just use AI. Build the systems that make better AI possible."

That vision is the destination. The table in
[docs/CAPABILITY_VS_ROADMAP.md](docs/CAPABILITY_VS_ROADMAP.md) is the
honest record of what is built, partial, simulated, or roadmap-only.
In particular, Stages 3 (Autonomous Optimisation) and 4 (Autonomous AI
Engineering) are **roadmap only**. This project is not "fully
autonomous" and is not claimed production-ready here.

Live demo (already linked before this rewrite; deployment is
standalone/in-memory, see Limitations below):

- Demo: <https://rasosynthtune-indiaai.vercel.app>
- Colab fine-tuning notebook:
  <https://colab.research.google.com/github/Sourabh-Kumar04/RasoSynth_CUTC/blob/master/finetuning/RasoSynthTune_FineTuning_Colab.ipynb>
- CI: <https://github.com/Sourabh-Kumar04/RasoSynth_CUTC/actions/workflows/ci.yml>

## Current capabilities

| Capability | Status | Notes |
| --- | --- | --- |
| Dataset synthesis (SFT, DPO/SimPO pairs, multi-turn, tool-calling, RAG-grounded, CoT, Socratic) | Built (pipeline code + CLI/SDK) | Engines live under `core/generation/` and `pipeline/`; see `docs/ARCHITECTURE.md`. Output quality is not guaranteed — see Limitations. |
| DBOM cryptographic provenance (SHA-256 Merkle root over exported samples) | Built at the API level | API roots recompute exactly from exported data. The dashboard verification UI is decorative — see Limitations. |
| Human-in-the-loop (HITL) review | Built, with a default-on queue | Review pauses jobs awaiting a reviewer; the queue size shown in the UI has not always matched the configured fraction — verify on a fresh job. |
| LoRA/QLoRA fine-tuning paths | Real local path + simulated cloud paths | `execution_target=local` runs real PEFT/Unsloth training. Colab/Modal/RunPod paths on the live site are simulated — see `docs/FINE_TUNING.md`. |
| CLI (`rasosynthtune`) and Python SDK (`rasosynth`) | Built | See Quickstart below. |
| Next.js dashboard | Built | Dataset library, job views, review queue, fine-tuning views. Some displayed values are constants or derived from job status, not measured — see Limitations. |
| PII redaction (Aadhaar, PAN, GSTIN, UPI, vehicle numbers) | Built (code) | Claimed by the pipeline; treat as a code capability, not a compliance certification. Nothing here certifies DPDP Act 2023 or EU AI Act compliance. |
| Provider routing (Gemini, NVIDIA NIM, Anthropic, OpenAI, Fireworks, Featherless, Ollama/vLLM, plus others in the router) | Built (code) | Live-site provider badges have shown zero requests — a badge is not evidence of live provider traffic. |

## Quickstart

Prerequisites: Python 3.11+ (3.12 in CI), Node.js for the dashboard,
Docker + Docker Compose for the full stack. PostgreSQL, Redis, and
Qdrant are used by the Compose stack; the deployed demo runs
standalone/in-memory instead (see Limitations).

```bash
git clone https://github.com/Sourabh-Kumar04/RasoSynth_CUTC.git
cd RasoSynth_CUTC
cp .env.example .env   # fill in real values; never commit .env
pip install -e ".[dev]"

# Backend API server (from the repo root; serves the API on port 8000)
python main.py --host 127.0.0.1 --port 8000
# Verify it is up: curl http://127.0.0.1:8000/health
# API docs: http://127.0.0.1:8000/docs

# Backend tests (full collection; run the suite before a PR)
pytest --collect-only -q
pytest tests/ -q

# Lint / type checks (dev extras)
# CI gates on RUF100 only; the full ruff rule set and mypy have known
# backlogs and are not gates, so do not expect a bare ruff or mypy run
# to pass until those backlogs are cleared.
ruff check --select RUF100 .

# Dashboard (from the repo root)
npm run dev --prefix frontend   # or: cd frontend && npm run dev
```

### Docker Compose stack

```bash
cp .env.example .env
docker compose up --build -d
# Celery worker monitor only: docker compose --profile monitoring up -d
```

- Web dashboard: <http://localhost:3001> (override with FRONTEND_PORT)
- API docs: <http://localhost:8000/docs>
- Celery worker monitor: <http://localhost:5555> (monitoring profile only)
- Reverse proxy: <http://localhost:80> (routes / to the dashboard, API paths to the backend)

Note: the Compose files were path-checked against the current tree, but a
full docker compose up --build was not run in the packaging pass (no
Docker daemon was reachable from the environment used), so treat the first
build on a Docker host as unverified until it succeeds there. The backend
image build also requires uv.lock to be in sync with pyproject.toml
(uv sync --frozen fails on a stale lockfile) — re-run uv lock before
building if dependency metadata has changed since the last lock.

### Python SDK

```python
from rasosynthtune import RasoSynthClient

client = RasoSynthClient(api_key="YOUR_API_KEY")
job = client.synthesize(
    domain="Indian GST & Corporate Tax Compliance",
    target_tokens=100000,
    quality_threshold=0.85,
    export_format="parquet",
    synthesis_mode="cot",
    language="en",
    wait=True,
)
print(f"Status: {job.status}")
```

### CLI

```bash
# Synthesis with DBOM certificate
rasosynthtune generate --domain "Indian Taxation & GST Compliance" --size 10 --format jsonl

# Local generation via Ollama / vLLM
rasosynthtune generate --domain "Clinical Emergency Triage" --size 20 --engine ollama

# Audit an exported dataset (DBOM, PII scan, contamination audit)
rasosynthtune audit --dataset outputs/<dataset-id>/dataset.parquet

# Fine-tuning recipes (Axolotl / Unsloth / Torchtune)
rasosynthtune recipe --framework unsloth --model "sarvamai/sarvam-2b-v0.5" --dataset outputs/<dataset-id>/dataset.jsonl
```

## Project structure

```text
api/          FastAPI backend (jobs, fine-tuning, review, quality, schemas)
agents/       Multi-agent system (graph, registry, specialized agents)
core/         Orchestration, generation engines, DBOM, review, validation, storage
pipeline/     Dataset construction pipeline
providers/    Provider router and provider clients
finetuning/   Local trainer, Colab bridge, simulated cloud stubs
rasosynth/    Python SDK (also: rasosynthtune/ package)
frontend/     Next.js 14 dashboard (app/, components/, lib/)
main.py       Canonical entry point (console script: rasosynthtune;
              serves the API by default; subcommands live in cli.py)
workers/      Celery app (workers.celery_app.celery_app)
tests/        Backend test suite (pytest)
docs/         Documentation index: docs/README.md
scripts/      Benchmark/demo/runner scripts (see note below)
Dockerfile, docker-compose.yml
              Backend image and full-stack Compose services (repo root)
deploy/       Deployment extras (Helm, Hugging Face) — not the Docker files
```

## Current limitations / known gaps

Read this before quoting any number from the site or this repo. These
findings come from a live-site regression check on 2026-10-28 and are
stated plainly on purpose:

- **Fine-tuning on the live site is simulated.** Logs for live-site
  fine-tuning runs say demo placeholders, not GPU-trained weights.
  Loss curves and adapter/GGUF files from those runs are placeholders.
  Label every such run "simulated". Real training requires
  `execution_target=local` (PEFT/Unsloth) or a real Colab GPU run of
  the notebook. See `docs/FINE_TUNING.md`.
- **Library quality numbers are not one trustworthy score.** Quality
  was shown as a status constant in the library, and one dataset had
  multiple different quality numbers in different places. Do not quote
  a single library quality percentage as measured until one scoring
  function is enforced end to end.
- **Old certified datasets contained many duplicate records.** Some
  previously certified datasets were heavily duplicated. "Certified"
  in the UI has historically been derived from job completion, not
  from an independent audit — see `docs/DATASET_CONTRACT.md`. Do not
  silently rewrite old certified datasets; re-certify or mark them
  legacy.
- **Merkle verification UI is decorative.** The DBOM API roots
  recompute exactly from exported data, but the dashboard Verify
  control does not perform that recomputation. Verify a DBOM by
  recomputing the root from the exported JSONL yourself until the UI
  is fixed.
- **Provider badges showed zero requests.** A "Live/Healthy" badge on
  the site is not evidence of provider traffic. Do not cite badge
  state as usage.
- **Deployment is standalone/in-memory, not distributed.** The live
  demo does not run the distributed Celery/PostgreSQL/Qdrant stack
  described for local Docker Compose. Do not describe the demo as a
  distributed production deployment.
- **Cost figures on the site do not trace to a real provider bill.**
  Do not quote site cost figures as spend. If a figure cannot be
  traced to a run, a commit, or a bill, delete it or label it
  simulated/template.
- **Benchmark figures removed.** The previous README carried a
  benchmark table (uniqueness, diversity, cost-per-sample, throughput).
  Those figures were not re-traced to a current run during this docs
  rewrite, so they were removed rather than repeated. Re-add a
  benchmark only with the script, commit, and run output it came from.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: user author only on
commits (no agent co-authors), tests before a PR, and every
simulated/template value must be labelled as such.

## Docs

- [docs/README.md](docs/README.md) — docs index
- [docs/CAPABILITY_VS_ROADMAP.md](docs/CAPABILITY_VS_ROADMAP.md) — built vs simulated vs roadmap
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — existing components only
- [docs/DATASET_CONTRACT.md](docs/DATASET_CONTRACT.md) — certified / validated / ready
- [docs/FINE_TUNING.md](docs/FINE_TUNING.md) — real vs simulated vs template numbers
- [CHANGELOG.md](CHANGELOG.md) — changes from "Unreleased" forward

## License

[PolyForm Noncommercial License 1.0.0](LICENSE) —
strictly non-commercial use only. Not OSI-approved.

