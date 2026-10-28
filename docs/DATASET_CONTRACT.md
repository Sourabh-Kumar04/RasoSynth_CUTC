# Dataset contract — certified / validated / ready

One definition each. These are the intended meanings. The
"Current implementation" note under each term states what the code
actually does today, because the two have diverged — and that
divergence is itself a known gap.

## Certified

**Definition:** a dataset that has passed the full pipeline —
synthesis, dedup, quality gates, and human review where required —
and has been sealed with a DBOM Merkle root over its exact exported
samples, so any later change to the samples invalidates the seal.

**Current implementation (gap):** in the dashboard, "Certified"
labels have been derived from job completion rather than from an
independent certification audit, and some previously certified
datasets contained many duplicate records. Until dedup is enforced
end to end and certification is a separate audited step, do not
treat the UI "Certified" badge as proof of uniqueness or quality.
Old certified datasets must be re-certified or marked legacy — never
silently rewritten.

## Validated

**Definition:** a dataset whose samples have passed automated
validation: schema conformance (e.g. Alpaca
instruction/input/response), quality thresholds, dedup checks, and
PII-redaction scans, with the results recorded per dataset.

**Current implementation (gap):** the dashboard computes
`validated` from job completion (`job.status === 'completed'`, in
`frontend/app/(dashboard)/datasets/page.tsx`), not from recorded
per-dataset validation results. A "Validated" flag therefore means
"the job finished", not "validation evidence exists". Validation
results must be recorded and displayed before the flag is quoted as
evidence.

## Ready

**Definition:** a dataset that is validated (per the definition
above), sealed, and exported in a consumable format (JSONL, CSV,
Parquet, or Hugging Face dataset) so it can be used for training
without further processing.

**Current implementation (gap):** the dashboard maps a completed job
to status `ready` (`job.status === 'completed' ? 'ready' : ...`, same
file) and shows "Certified Ready" for ready datasets. "Ready" today
is a status derivation, not a check that validation + sealing +
export all happened. A dataset counts as ready under this contract
only when all three are true and evidenced.

## Rules

1. One dataset, one quality score, from one function. If two screens
   disagree, the dataset is not certified until the discrepancy is
   fixed at the source.
2. A DBOM seal covers the exact exported bytes. Re-exporting or
   editing samples requires a new seal; the old seal must not be
   carried over.
3. Quality, uniqueness, and dedup figures quoted anywhere must trace
   to a run or a commit. Otherwise label them simulated/template or
   delete them.
4. Verification means recomputing the Merkle root from the exported
   JSONL over all samples and comparing it to the API root. The
   dashboard Verify control does not do this today (decorative) —
   verify out of band until it is fixed.

