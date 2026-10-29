# RasoSynthTune: Executive Technical Briefing & Architecture Overview

> **Version**: 2.0.0 Enterprise  
> **Platform**: Autonomous Domain-Specific Synthetic Data Refinery, Cryptographic Attestation & Fine-Tuning Engine  
> **Classification**: Technical Due Diligence Briefing  

---

## 1. Executive Summary

As frontier foundation models hit data walls on public web crawls, the decisive competitive advantage in enterprise AI shifts toward **high-precision, compliant, domain-specialized synthetic training data**. Generic crawls contain up to 40% duplicate content, unmasked statutory PII, and benchmark test-set contamination.

**RasoSynthTune** solves this through an autonomous synthetic data refinery that:
1. **Curates & Synthesizes Domain Data**: Generates multi-turn, multi-difficulty reasoning datasets with four specialized post-training modes (Instruction Distillation, Agentic Chain-of-Thought, Contrastive DPO/RLHF Pairs, and Self-Correcting Reflection).
2. **Enforces Cryptographic Provenance (DBOM)**: Computes deterministic SHA-256 Merkle root trees over dataset samples, issuing tamper-evident Data Bill of Materials certificates and auditable Data Nutrition Labels. No certification or compliance claim under the EU AI Act, India DPDP Act 2023, or ISO 42001 is made — compliance status is unverified.
3. **Validates Quality & Prevents Benchmark Leakage**: Uses 5-dimensional heuristic filtering, MinHash de-duplication, statutory PII masking (Aadhaar, PAN, GSTIN, UPI), and n-gram canary audit against MMLU, GSM8K, IndicGLUE, and ARC.
4. **Unit economics**: no cost-reduction multiple is claimed here. The previously quoted $1.00 vs $0.00052 per-sample figures and the 1,904x multiple were not traced to a measured run and have been removed.

---

## 2. Core Architecture & Pipeline

```
 ┌────────────────────────────────────────────────────────┐
 │            1. DOMAIN INTENT & SYNTHESIS               │
 │  Target Constraints • Indic Alignment • Post-Training │
 └──────────────────────────┬─────────────────────────────┘
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │           2. 5-DIMENSIONAL QUALITY REFINERY            │
 │  • MinHash Deduplication (Jaccard > 0.85 Rejection)    │
 │  • DPDP Statutory PII Redaction (Aadhaar/PAN/GSTIN)    │
 │  • Benchmark Contamination Audit (Canary Leakage 0%)   │
 │  • Multi-Tier Difficulty Curriculum (Tiers 1 to 5)     │
 └──────────────────────────┬─────────────────────────────┘
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │     3. CRYPTOGRAPHIC DATA BILL OF MATERIALS (DBOM)     │
 │  • Deterministic SHA-256 Leaf Hashing                  │
 │  • Cryptographic Merkle Root Verification              │
 │  • Auditable Data Nutrition Label (Markdown / JSON)    │
 └──────────────────────────┬─────────────────────────────┘
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │       4. MULTI-FORMAT EXPORT & TRAINING RECIPES        │
 │  • Parquet (Arrow) • JSONL • SQLite/PG • Qdrant Vector │
 │  • Unsloth (QLoRA) • Axolotl (YAML) • Torchtune        │
 └────────────────────────────────────────────────────────┘
```

---

## 3. Audited Benchmarks & Empirical Validation

Metrics in section A are from a single recorded pilot run of **n=5** evaluation pairs (`outputs/evaluation/before_vs_after_finetune_benchmark.json`, 2026-10-20). They are a small-sample pilot, not production proof, and the recorded rating is `acceptable_requires_tuning`.

### A. Model Fine-Tuning Accuracy Delta (`sarvamai/sarvam-2b-v0.5`)
Evaluated on held-out statutory evaluation pairs covering the Central Goods and Services Tax (CGST) Act 2017:

| Metric | Pretrained Baseline | Post-RasoSynthTune SFT | Empirical Gain |
| :--- | :---: | :---: | :---: |
| **chrF Character Overlap** | 14.80 | **94.33** | **+537.4% Relative Gain** |
| **Mean Token-F1** | 0.191 | **0.739** | **+286.9% Relative Gain** |
| **Exact Match (EM)** | 0.0% | **40.0%** | **+40.0% Absolute Delta** |
| **Citation Grounding** | 100.0% | **100.0%** | **100% Statutory Citations** |
| **Composite Quality Score** | 10.6 | **64.4** | **+53.8 pts (recorded rating: `acceptable_requires_tuning` — not production-ready)** |

### B. High-Throughput Cryptographic Engine (unverified — no recorded run in this repo reproduces these figures; treat as unconfirmed, not measured)
* **Throughput**: **~302,570 samples/second** on multi-threaded SHA-256 leaf and Merkle node hashing.
* **Latency Profile**: **3.4 μs** p50 per-sample hashing latency.
* **Contamination Rate**: **0.0%** across standard evaluation canary signatures — a canary spot-check, not a leakage guarantee.

### C. Enterprise Unit Economics — removed
The previously quoted vendor-vs-refinery per-sample figures and the 1,904x cost-reduction multiple were not traced to a measured run and are no longer claimed.

---

## 4. Developer Interface & Operational Tooling

RasoSynthTune provides a developer-first interface accessible via CLI, REST API, Python SDK, and Web Dashboard:

```bash
# Generate datasets with cryptographic DBOM & Nutrition Label
rasosynthtune generate --domain "Indian Taxation & GST Compliance" --size 1000 --format jsonl

# Audit dataset for PII leakage, contamination, and Merkle root integrity
rasosynthtune audit --dataset outputs/<dataset-id>/dataset_sft.jsonl

# Run live latency, quality, and ROI benchmark suite
rasosynthtune benchmark

# Generate production training recipes for target models
rasosynthtune recipe --framework axolotl --model "sarvamai/sarvam-2b-v0.5"

# Launch high-concurrency canonical API server
rasosynthtune serve --host 0.0.0.0 --port 8000
```

---

## 5. Security & Regulatory Posture (unverified — no certification claimed)

The platform provides features intended to support governance documentation — statutory-identifier masking, tamper-evident cryptographic provenance, and auditable Data Nutrition Labels. It does **not** claim certification or verified compliance with the India DPDP Act 2023, the EU AI Act, or ISO 42001; "zero unmasked records" is not asserted, since masking coverage has not been independently measured.
