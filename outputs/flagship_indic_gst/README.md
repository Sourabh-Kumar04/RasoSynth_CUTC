---
license: apache-2.0
task_categories:
- question-answering
- text-generation
language:
- en
- hi
tags:
- taxation
- gst
- legal
- synthetic-data
- dbom
- rasosynthtune
- indic
size_categories:
- n<1K
---

# 🇮🇳 Flagship Indic GST & Tax Statutory SFT Dataset

Curated and cryptographically attested by **RasoSynthTune 2.0.0 Enterprise**.

## Overview
This flagship open-access dataset provides gold-standard statutory instruction-tuning pairs covering the **Central Goods and Services Tax (CGST) Act 2017**, **Integrated GST (IGST) Act**, and **CBIC statutory circulars**.

## Cryptographic Provenance (DBOM)
- **Certificate ID**: `DBOM-D91E915C92C4`
- **Merkle Tree Root SHA-256**: `d91e915c92c40ce71418e4c1a1ce577122cc9707af2c1463998b5174b9dc8c26`
- **PII Scrubbing**: Verified Clean (India Digital Personal Data Protection Act 2023)
- **Benchmark Contamination**: 0.0% leakage against MMLU, GSM8K, IndicGLUE, ARC

## Quickstart Fine-Tuning
```bash
# Fine-tune with Unsloth (5x faster)
python train_unsloth.py

# Or launch with Axolotl
accelerate launch -m axolotl.cli.train axolotl_config.yaml
```
