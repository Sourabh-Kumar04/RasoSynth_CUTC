# Capability vs Roadmap — single source of truth

**Rule:** if a capability is not marked **Built** here with evidence,
do not describe it as built anywhere else (README, deck, site copy,
or PR description). Status labels:

- **Built** — code exists and is exercised by tests or a verified run.
- **Partial** — code exists but a known gap breaks the claim end to end.
- **Simulated** — the code path produces placeholder/demo output, not
  the real result. Must be labelled simulated wherever shown.
- **Roadmap** — direction only. No code claim is made.

Version source of truth: `pyproject.toml` (`2.0.0`).
Evidence date for the live-site findings: 2026-10-28 regression check.

## The four stages

### Stage 1 — Dataset Engineering

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Multi-engine synthesis (SFT, CoT, RAG, Socratic, DPO/SimPO, tool-calling, multi-turn) | Built | `core/generation/`, `pipeline/`; CLI `rasosynthtune generate` |
| Discovery / crawling / extraction | Built | Pipeline stages in `core/`; provider/router code |
| Dedup, filtering, PII redaction | Built (code) / Partial (outcome) | Dedup exists, yet old certified datasets contained many duplicates — dedup was not enforced end to end on those datasets |
| Quality scoring + LLM judge | Partial | Scoring exists, but one dataset showed multiple quality numbers and the library showed a status constant — no single enforced score |
| HITL review gate | Built | Review queue pauses jobs; the fraction shown in the UI has not always matched the configured fraction — verify on a fresh job |
| DBOM Merkle provenance + export (JSONL/CSV/Parquet/HF) | Partial | API roots recompute exactly from exported data (verified); dashboard verification UI is decorative (not a recomputation) |
| Dataset library / dashboard | Partial | Library renders, but status/quality values are partly constant or derived from job status, not measured |

### Stage 2 — End-to-End Fine-Tuning

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Local LoRA/QLoRA training (PEFT/Unsloth, `execution_target=local`) | Built | `finetuning/trainer.py`; real local path, not the simulator |
| Colab GPU notebook (1-click) | Built (notebook) | `finetuning/RasoSynthTune_FineTuning_Colab.ipynb`; real GPU training only when actually run on a GPU |
| Fine-tuning on the live site (Colab/Modal/RunPod paths) | Simulated | `finetuning/colab_bridge.py` and the Modal stub in `finetuning/trainer.py` emit `is_simulated: true`, placeholder adapters, and demo loss curves — not GPU-trained weights |
| Model cards / training telemetry | Partial | Cards are generated, but simulated runs must carry the simulated disclosure (the code appends it; the UI must not strip it) |
| Evaluation of fine-tuned models | Partial | Evaluation code exists under `core/evaluation/`; no evaluated-vs-baseline claim is made here without a traced run |

### Stage 3 — Autonomous Optimisation

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Self-improving dataset/model loop driven by feedback | Roadmap | Direction only. No autonomous optimisation loop is claimed as built. Existing retry/adaptive paths inside synthesis are pipeline mechanics, not Stage 3. |

### Stage 4 — Autonomous AI Engineering

| Capability | Status | Evidence / gap |
| --- | --- | --- |
| Autonomous end-to-end AI engineering (system designs, builds, and improves models itself) | Roadmap | Vision only. Nothing in this repo is presented as Stage 4. |

## Long-term vision (not a status claim)

Democratising AI development: an autonomous, open, efficient platform
turning raw data and ideas into high-quality training datasets and
specialised models, starting with underserved languages/domains
(Indian languages first); automating discover → synthesise → verify →
curate → optimise → fine-tune → evaluate → improve. Philosophy:
"Don't just use AI. Build the systems that make better AI possible."

## Known gaps that change a status (2026-10-28, do not soften)

- Live-site fine-tuning is simulated; label it simulated.
- Library quality was a status constant; one dataset, multiple numbers.
- Old certified datasets held many duplicate records.
- Merkle API roots recompute exactly; verification UI is decorative.
- Provider badges showed zero requests.
- Deployment is standalone/in-memory, not distributed.
- Site cost figures do not trace to a real provider bill.
- Previous README benchmark figures were removed in this docs pass
  because they were not re-traced to a current run.

When a gap above is fixed, update this file first, with the fresh
job/run evidence, then update the README and site copy to match.

