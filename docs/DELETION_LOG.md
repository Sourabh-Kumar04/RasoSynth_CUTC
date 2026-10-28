# Deletion Log — Repo Hygiene (optimize/industry-standard)

Date: 2026-10-28. Branch: `optimize/industry-standard` (HEAD `c176382` at audit time).
Scope: repo hygiene only. No directories restructured, no functional code moved,
no behaviour changed, no README/CONTRIBUTING/CI edits.

## Result: NO files deleted

No tracked file met the bar for deletion (clearly dead, duplicate, or generated,
with grep evidence of zero references and no test/script/config/doc referencing it).
Per the workstream rule — if use is uncertain, KEEP — every candidate below was kept.
Nothing was deleted on assumption, and no history was rewritten.

## Checks run (all via git on the PC checkout)

- `git branch --show-current`, `git rev-parse HEAD`, `git status --porcelain`:
  branch `optimize/industry-standard`, HEAD `c17638206c5b021e49faffa0157a1eca089e36f3`,
  working tree clean before any change.
- Tracked-vs-ignored status (`git ls-files`, `git check-ignore -v`,
  `git status --ignored --porcelain`) for `outputs/`, `.venv/`, `.pytest_cache/`,
  `__pycache__/`, `.env`, `.env.example`:
  - `.env`: 0 tracked files, ignored (`.gitignore:4`), present on disk but untracked.
    NOT deleted, NOT read, NOT removed from history (it was never tracked).
  - `.env.example`: 1 tracked file, kept (template, not a secret).
    Also tracked: `frontend/.env.local.example`.
  - `.venv/`, `.pytest_cache/`, `__pycache__/`: 0 tracked files, all ignored on disk.
  - `outputs/`: 2 tracked files, both under the deliberate `outputs/evaluation/`
    exception in `.gitignore` (see below). All other `outputs/*` content is ignored.
- Tracked-file scan for generated/junk patterns
  (`*.pyc/*.pyo/*.log/*.bak/*.backup/*.orig/*.old/*.swp/*.swo/*.db/*.sqlite*`,
  `node_modules`, `/.next/`, `*.egg-info`, `__pycache__`, `.pytest_cache`,
  `.coverage`, `.DS_Store`, `Thumbs.db`, `*.pem`, `*.key`, `credentials`, `secret`,
  trailing `.env`): exactly one hit, `core/secrets.py` — see "Kept" below.
- Duplicate-content scan: md5sum over all tracked files excluding `__init__.py`
  and `.gitkeep` — no duplicate hashes found.
- Empty tracked files: exactly one, `tests/load/__init__.py` — see "Kept" below.
- Largest tracked files are source or lockfiles, not generated blobs:
  `uv.lock` (985,145 bytes), `frontend/package-lock.json` (505,916),
  `api/server.py` (204,580), `core/orchestrator_core.py` (193,508),
  `frontend/pnpm-lock.yaml` (193,029). All kept.
- Total tracked files at audit time: 457.

## Candidates examined and KEPT (with evidence)

- `outputs/evaluation/before_vs_after_finetune_benchmark.json` and
  `outputs/evaluation/before_vs_after_finetune_benchmark.md` — tracked by design:
  `.gitignore` explicitly re-includes `outputs/evaluation/` (`!outputs/evaluation/`
  and `!outputs/evaluation/**`). Benchmark documentation, not stray run output.
- `core/secrets.py` — functional source, not secret material: defines
  `SecretBackend`, `SecretsManager`, `EnvironmentSecretsProvider`,
  `VaultSecretsProvider`, `AWSSecretsProvider`, `get_secrets_manager()`.
  No secret values were read or printed during this audit.
- `tests/load/__init__.py` — empty, but a package marker for the `tests/load`
  package (`tests/load/load_test_framework.py`, `tests/load/test_real_load.py`).
  Deleting it could break test collection; kept.
- `rasosynthtune/client.py` — intentional re-export shim, not a duplicate:
  its docstring says "Re-export of rasosynth.client" and its body is
  `from rasosynth.client import RasoSynthClient, JobResult, DBOMAttestation`.
  The full SDK lives in `rasosynth/client.py` (307 lines). Both kept.
- `agents/agents/*.py` (`research`, `planning`, `discovery`, `extraction`,
  `quality`, `synthetic`, `optimization`, `curation`, `infrastructure`) — actively
  imported by `agents/__init__.py` and `agents/registry.py`
  (e.g. `from agents.agents.research import ResearchAgent`). Not a stray copy.
- Repeated basenames — normal per-package/per-app files, not duplicates:
  `__init__.py` (28 packages), Next.js `page.tsx`/`layout.tsx` (12 each),
  root vs `frontend/` pairs of `vercel.json`, `tsconfig.json`, `package.json`,
  and two `favicon.svg` (root + frontend). All kept.
- `scripts/backup.py`, `scripts/backup.sh`, `scripts/schedule_backups.py` —
  named "backup" but they are backup tooling scripts, not backup artifacts.
  No evidence of deadness; kept.
- `docs/YC_APPLICATION.md` — present on disk but ignored via the `*YC*`/`*yc*`
  gitignore rules and NOT tracked. Out of scope for this workstream; untouched.

## Changes shipped alongside this log (same commit)

- `.gitignore` hardened only: `.env.*` with `!.env.example` / `!.env.*.example`
  negations, `*.token`, `*.secret`, `service-account*.json`, `id_rsa*`, `.aws/`,
  `.tox/`, `.nox/`, `.hypothesis/`, `coverage.xml`, `frontend/.vercel/`.
  Verified: zero tracked files match the new patterns, and the example env files
  remain un-ignored. No functional source, doc, or config ignore rules added.
- Test collection before changes: 541 tests (`pytest --collect-only -q`,
  `-p no:cacheprovider`). Collection after changes is recorded in the
  workstream report; the full suite was NOT re-run here (a baseline full run
  was already in progress on the PC).
