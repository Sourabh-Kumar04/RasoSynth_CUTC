# Changelog

The version source of truth is `pyproject.toml` (currently `2.0.0`).
This changelog starts at "Unreleased" and moves forward only.
No past releases are backfilled here, and no historical release
is invented: if a past release is not recorded in git history with
evidence, it does not appear below.

## Unreleased

### Added

- Docs-only rewrite on `optimize/industry-standard`: evidence-led
  `README.md` with a plain-language "Current limitations / known
  gaps" section; `CONTRIBUTING.md`; `docs/CAPABILITY_VS_ROADMAP.md`,
  `docs/ARCHITECTURE.md`, `docs/DATASET_CONTRACT.md`,
  `docs/FINE_TUNING.md`, and `docs/README.md` (docs index).
- Honesty labels carried into docs: live-site fine-tuning is
  simulated (demo placeholders, not GPU-trained weights); library
  quality was shown as a status constant with multiple numbers for
  one dataset; old certified datasets contained many duplicates;
  Merkle API roots recompute exactly but the verification UI is
  decorative; provider badges showed zero requests; the deployment
  is standalone/in-memory, not distributed; site cost figures do
  not trace to a real provider bill.
- `.env.example` completed with example entries (placeholders only,
  never real secrets) for variables the app reads that were missing.

### Removed

- Benchmark table from the previous `README.md` (uniqueness,
  diversity, cost-per-sample, throughput). The figures were not
  re-traced to a current run during this docs rewrite, so they were
  removed rather than repeated. Re-add a benchmark only with the
  script, commit, and run output it came from.

### Notes

- No code, CI, license, dependency, visibility, or deployment
  changes are part of this docs workstream.

