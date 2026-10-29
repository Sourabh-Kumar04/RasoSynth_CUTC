# 🚀 RasoSynthTune: 3-Minute Live Demo & Investor Walkthrough Script

> **Product**: RasoSynthTune 2.0.0 Enterprise  
> **Audience**: Investors, Venture Partners (YC, a16z), AI Engineers & Enterprise Clients  
> **Target Run Time**: 3 Minutes  

---

## ⏱️ Minute 1: The Sovereign AI & Data Wall Problem (0:00 - 1:00)

### The Hook & Problem Statement
* "Every major enterprise and nation building Sovereign AI has hit the **public data wall**. Generic web crawls are 40% duplicate noise, contaminated with benchmark test sets, and laden with unmasked statutory PII (PAN, GSTIN, Aadhaar).
* If you train a base foundation model like Sarvam-2B on raw crawls, it hallucinates statutory tax thresholds, confuses CGST with IGST, and drops into vague generalizations.
* Traditional human labeling through Scale AI or Surge AI costs **$1.00+ per instruction pair**, requiring weeks of latency and millions in budget."

### Visual Demonstration
1. Open the **Engineering Command Center** (`http://localhost:3000`).
2. Point to the **Natural Language Intent & Compute-Saving Query Optimizer** bar.
3. Show the active **5-Dimensional Quality Filter** rejecting web spam and MinHash near-duplicates live.

---

## ⏱️ Minute 2: Autonomous Refinery & Cryptographic DBOM (1:00 - 2:00)

### The Solution: Post-Training Synthesis & Cryptographic Provenance
* "RasoSynthTune introduces an autonomous data refinery with four specialized post-training synthesis modes:
  1. **Instruction Distillation**: Seedless coverage expanding complex statutory concepts.
  2. **Agentic Chain-of-Thought**: Multi-step deductive legal reasoning with AST verification.
  3. **Contrastive Pairs (DPO/RLHF)**: Preferred vs. rejected statutory responses for direct preference tuning.
  4. **Self-Correcting Reflection**: Iterative multi-turn self-critique.
* Crucially, every dataset produced carries a **Cryptographic Data Bill of Materials (DBOM)**. We compute a recursive SHA-256 Merkle tree root over every sample. Any tampering or downstream token alteration invalidates the certificate."

### Live CLI Demonstration (Run in terminal):
```bash
# 1. Synthesize 5 GST instruction pairs with cryptographic DBOM
rasosynthtune generate --domain "Indian Taxation & GST Compliance" --size 5 --format jsonl

# 2. Verify Merkle root integrity, DPDP statutory PII compliance, and 0% benchmark leakage
rasosynthtune audit --dataset outputs/dataset_distillation_5.jsonl
```
* **Key result to show the audience**: The Terminal Audit Scorecard displaying `PASSED - Cryptographically Intact`, `0 statutory PII entities`, and `0% contamination against MMLU, GSM8K, IndicGLUE, ARC` — where the contamination figure is a canary spot-check, not a leakage guarantee.

---

## ⏱️ Minute 3: Empirical Validation — small-sample pilot (2:00 - 3:00)

### Empirical Accuracy Delta (small-sample pilot — n=5, recorded 2026-10-20; not production proof):
* "We put our synthetic datasets to the test on `sarvamai/sarvam-2b-v0.5`. Evaluating on held-out statutory evaluation pairs (n=5):
  * **chrF Character Overlap**: Improved from `14.80` to **`94.33`** (**+537.4% Relative Gain**).
  * **Mean Token-F1**: Improved from `0.191` to **`0.739`** (**+286.9% Relative Gain**).
  * **Exact Match (EM)**: Smashed from `0.0%` to **`40.0%`** (**+40.0% Absolute Delta**).
  * **Citation Grounding**: **100% Grounded** in CGST Act statutory provisions."

### Unit Economics Simulator:
* The unit-economics figures previously shown here were untraced to any measured run and have been removed. Do not present a cost-reduction multiple in the demo until a traced run exists.

---

## 🚀 Quick Reproducibility Commands for Judges & Evaluators

```bash
# Clone and enter workspace
git clone https://github.com/Sourabh-Kumar04/RasoSynth_CUTC.git
cd RasoSynth_CUTC

# Inspect CLI help surface
python cli.py --help

# Run empirical model fine-tuning evaluation runner
python scripts/demo_finetune_eval.py

# Run live latency & throughput benchmark suite
python scripts/run_benchmarks.py

# Inspect user-generated output directory
ls -lh outputs/<dataset-id>/
```
