# UI text removals — RasoSynthTune post-P0 step 2

Branch: `optimize/industry-standard`. Base: `efe1eac` (P0s complete).
Rule applied on every page: remove redundant marketing fluff, duplicated
headings, placeholder paragraphs and repeated explanations. Keep functional
labels, CTAs, navigation, and ALL honest labels (simulated / demo / unknown /
estimated, disclaimers, compliance wording, limitations). Where a removal was
in doubt, the text was kept.

## Route inventory (verified from the frontend tree)

12 page files: `/` (root landing) plus 10 dashboard routes
(`/datasets`, `/finetune`, `/observability`, `/orchestration`, `/providers`,
`/quality`, `/research`, `/review`, `/settings`, `/studio`) plus
`/studio/new` (redirect only, no display text).

## Removals, per route

### `/` — frontend/app/page.tsx
- Removed: "Non-linear state machine executing discovery, multi-engine
  cognitive loops, neural validation, and cryptographic attestation."
  (under "Autonomous 4-Stage Synthesis Pipeline" — restated the heading).
- Shortened DBOM paragraph: removed "Every synthesized batch is
  cryptographically anchored into a SHA-256 Merkle tree." Kept:
  "Certificates attest to zero PII leakage and statutory fidelity."
- Shortened quality paragraph: removed "Every sample is filtered against
  neural cosine embeddings and graded by our pure LLM Judge rubric before
  admission into the dataset." Kept the honesty sentence in full: "The
  figures in this section are reference values, not measured per-dataset
  results."
- Removed: "Trigger autonomous dataset pipelines programmatically from
  your training workflows and CI/CD runs." (under "Synthesize Directly
  via API or Python SDK" — restated the heading).
- Removed footer paragraph: "Autonomous dataset synthesis and evaluation
  orchestration platform for frontier AI models." (restated the brand name).

### `/datasets` — frontend/app/(dashboard)/datasets/page.tsx
- Removed page subtitle: "Browse certified synthetic datasets,
  cryptographic provenance seals, and download production archives"
  (heading "Data Library & Exports" already states the purpose; the word
  "certified" was also an unverified claim).
- Shortened empty state: "Describe the dataset you need in the Studio.
  Discover authentic source repositories, review grounded samples, and
  export to multi-destination targets." → "Describe the dataset you need
  in the Studio." (the longer text restated Studio features).

### `/observability` — frontend/app/(dashboard)/observability/page.tsx
- Removed page subtitle: "Real-time pipeline metrics, provider latency,
  execution traces & autonomous self-correction analytics" (heading
  "System Insights & Telemetry" already states the purpose).

### `/orchestration` — frontend/app/(dashboard)/orchestration/page.tsx
- Removed page subtitle: "Real-time stage node telemetry, automated
  checkpoint recovery, and multi-agent synthesis workflows".
- Removed research-loop paragraph: "Continuously reads arXiv publications,
  mines GitHub repos, and dynamically injects active heuristics into
  synthesis."

### `/providers` — frontend/app/(dashboard)/providers/page.tsx
- Removed page subtitle: "Multi-provider health monitoring, token cost
  tracking, circuit breaker states & live session migration".

### `/quality` — frontend/app/(dashboard)/quality/page.tsx
- Removed page subtitle: "Automated AI evaluation, hallucination
  resistance scoring, semantic diversity, and benchmark decontamination".

### `/research` — frontend/app/(dashboard)/research/page.tsx
- Removed page subtitle: "Automated model evaluations, accuracy gain
  tracking, technique discovery & inference efficiency".

### `/settings` — frontend/app/(dashboard)/settings/page.tsx
- Removed page subtitle: "Platform runtime configuration, API provider
  keys, ADR architecture standards & resource boundaries".

### `/studio` — frontend/app/(dashboard)/studio/page.tsx
- Removed page subtitle: "Curate and synthesize fine-tuning datasets
  with automated provenance and quality validation".

## No removals (deliberately kept)

- `/finetune`: no marketing subtitle found; page is functional
  (notebook generation). Nothing removed.
- `/review`: subtitle carries keyboard shortcuts (a/r/e/f) — functional
  instructions, kept.
- `/studio/new`: redirect only, no display text.
- Every honest label found on these pages (simulated / demo / unknown /
  estimated, disclaimers, the quality "reference values" sentence above,
  footer demo-guard note) was kept. No honest label was removed in this
  pass. The removals above are subtitle/paragraph deletions only; no
  functional label, CTA, navigation item, or data field was removed.

## Verification note

This pass changed display text only. Typecheck and build results for the
commit that carries this file are reported in the job's final report.


## Follow-up (same pass, found by grep after the first commit)

- "/datasets" metadata description in
  frontend/app/(dashboard)/datasets/layout.tsx still read "Browse
  certified synthetic datasets ..." after the display subtitle was
  removed. The word "certified" was removed there too, so the metadata
  now reads "Browse synthetic datasets, DBOM provenance seals, and
  download production archives." No other layout metadata contained a
  removed string (checked by grep).
