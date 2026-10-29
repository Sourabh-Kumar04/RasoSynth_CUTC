# 📈 Empirical Model Evaluation: Before vs. After RasoSynthTune Fine-Tuning

> **⚠️ Small-sample pilot — not production proof.** All figures below come from a single recorded run of **n=5** evaluation pairs (`samples_evaluated: 5` in the companion `before_vs_after_finetune_benchmark.json`, 2026-10-20). Do not quote these deltas as production accuracy, and do not upgrade the recorded rating: the JSON record's rating is `acceptable_requires_tuning`, **not** production-ready.
>
> **Sample size**: n=5
> **Target Domain**: Indian Taxation & GST Statutory Compliance  
> **Base Architecture**: `sarvamai/sarvam-2b-v0.5`  
> **Evaluation Engine**: `RasoSynthTune BenchmarkEvaluator`  
> **Timestamp**: 2026-10-20T13:16:17.929793+00:00  

---

## 1. Executive Summary: Accuracy & Fidelity Delta

| Metric | Pretrained Baseline | Post-RasoSynthTune SFT | Absolute Delta | Relative Gain |
| :--- | :---: | :---: | :---: | :---: |
| **Exact Match (EM)** | 0.0% | **40.0%** | `+40.0%` | — |
| **Mean Token-F1** | 0.191 | **0.739** | `+0.548` | **`+286.9%`** |
| **chrF Character Overlap** | 14.8 | **94.33** | `+79.53` | **`+537.4%`** |
| **Citation Accuracy** | 100.0% | **100.0%** | `+0.0%` | 100% Grounded |
| **Composite Quality Score** | 10.6 | **64.4** | `+53.8 pts` | — (n=5 pilot; no grade claimed) |
| **Operational Rating** | `suboptimal_hallucination_prone` | **`acceptable_requires_tuning`** | — | As recorded (not production-ready) |

---

## 2. Qualitative Error Analysis

1. **Statutory Hallucination Elimination**:
   - *Baseline*: Missed CBIC e-invoicing threshold of ₹5 Crore (hallucinated 20–50 Cr).
   - *RasoSynthTune Refined*: Correctly cited CBIC notifications and the exact ₹5 Cr statutory turnover threshold.
2. **Vernacular & Hinglish Accuracy**:
   - *Baseline*: Failed to handle Hinglish tax prompts; reverted to vague English approximations.
   - *RasoSynthTune Refined*: Maintained bilingual Hinglish legal precision without code-mixing confusion.
3. **Statutory Citation Grounding**:
   - *Baseline*: Vague references to "tax laws".
   - *RasoSynthTune Refined*: Grounded in Section 16(2), Section 29(2), and Section 47 of the CGST Act 2017.
