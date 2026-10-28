# Docs index

Start here. The status claims in these docs override older docs,
README copies, and site copy where they disagree.

- [CAPABILITY_VS_ROADMAP.md](CAPABILITY_VS_ROADMAP.md) — **single
  source of truth** for what is Built / Partial / Simulated /
  Roadmap across Stages 1–4. Stages 3–4 are Roadmap only.
- [ARCHITECTURE.md](ARCHITECTURE.md) — existing components only;
  no invented services. Notes where the demo topology differs from
  local Docker Compose.
- [DATASET_CONTRACT.md](DATASET_CONTRACT.md) — one definition each
  for certified / validated / ready, plus the current-implementation
  gaps (UI flags derived from job completion).
- [FINE_TUNING.md](FINE_TUNING.md) — real vs simulated vs template
  numbers for fine-tuning. Live-site fine-tuning is simulated.
- [TECHNICAL_BRIEFING.md](TECHNICAL_BRIEFING.md) — prior technical
  briefing (pre-existing; check it against CAPABILITY_VS_ROADMAP
  before quoting status claims from it).
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) — prior deployment
  guide (pre-existing).
- [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) — prior demo walkthrough
  (pre-existing; demo output must still be labelled demo, not real
  inference).
- [BRANCHING.md](BRANCHING.md), [RELEASE.md](RELEASE.md),
  [DELETION_LOG.md](DELETION_LOG.md),
  [OPEN_DATA_REPOSITORIES.md](OPEN_DATA_REPOSITORIES.md),
  [YC_APPLICATION.md](YC_APPLICATION.md) — pre-existing docs.
- [adr/](adr/) — architecture decision records.
- [runbooks/](runbooks/) — production runbooks.

Project-level docs: [../README.md](../README.md),
[../CONTRIBUTING.md](../CONTRIBUTING.md),
[../CHANGELOG.md](../CHANGELOG.md) (from "Unreleased" forward only;
version source of truth is `pyproject.toml`, currently `2.0.0`).

