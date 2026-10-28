# Contributing to RasoSynthTune

One page. If a rule here conflicts with an older doc, this page and
`docs/CAPABILITY_VS_ROADMAP.md` win for status claims.

## Setup

```bash
git clone https://github.com/Sourabh-Kumar04/RasoSynth_CUTC.git
cd RasoSynth_CUTC
cp .env.example .env   # placeholders only; never commit a real secret
pip install -e ".[dev]"
```

For the dashboard: `npm install --prefix frontend` (or `cd frontend &&
npm install`), then `npm run dev --prefix frontend`.

## Test / lint commands

Run these before opening a PR. The full backend suite is the gate;
a passing subset is not a pass.

```bash
pytest --collect-only -q   # collection check (541 tests at last docs pass)
pytest tests/ -q           # full backend suite
ruff check .
mypy .
npm run type-check --prefix frontend
npm run build --prefix frontend
```

If a test needs a provider key, skip it honestly (record the skip in
the PR) rather than faking a key or a result.

## PR process

1. Work on a feature branch, never directly on `master`.
2. Keep the change scoped: one PR, one purpose. Docs-only PRs must not
   touch code, CI, license, or dependency versions, and vice versa.
3. Describe what ran (commands + result), what is local-only, what is
   committed, and what is still unverified. Do not claim a change is
   live on the deployed site until it is verified there.
4. If you touch anything the dashboard displays as a number, say where
   the number comes from (run, commit, or bill) or label it
   simulated/template. See "Honesty rule" below.
5. Do not approve, resume, delete, or restart any live job or dataset
   from a PR or script unless the task explicitly authorises it.
   Do not silently rewrite old certified datasets; re-certify them or
   mark them legacy.

## Commit authorship rule

**Commits are authored only by the user (the repository owner).**
No agent, assistant, or tool is ever listed as an author or
co-author. Specifically:

- No `Co-Authored-By:` lines for Raso, Muse, Antigravity, or any agent.
- No agent name in the author or committer fields.
- Use the repository's configured git identity and verify with
  `git log --format='%an %ae' -1` before pushing.

If a commit lands with the wrong author, say so plainly and fix it
with the owner — do not quietly rewrite shared history.

## Honesty rule (non-negotiable)

- Simulated, template, placeholder, and demo values must be labelled
  as such wherever they appear: code, UI copy, docs, decks, and PRs.
- One number, one source. If a metric appears in two places with two
  values, that is a bug: fix the source, do not pick the nicer one.
- Never present demo output as real inference, a simulated training
  run as GPU-trained weights, a badge as usage, or a roadmap stage as
  built. When in doubt, label it and link the evidence.
- The version source of truth is `pyproject.toml` (`2.0.0` at the
  time of writing). Do not invent releases in `CHANGELOG.md`.

## License note for contributors

Contributions are under the project's PolyForm Noncommercial
License 1.0.0 (non-commercial, not OSI-approved). By contributing you
agree your work is distributed under that license.

