---
license: apache-2.0
task_categories:
- text-generation
- question-answering
language:
- en
tags:
- clinical-reasoning
- triage
- medical-ai
- dbom
- rasosynthtune
size_categories:
- n<1K
---

# Clinical Reasoning & Diagnostic Triage SFT (v1.0.0)

[![Cryptographic DBOM Verified](http://localhost:8000/badges/dbom/DBOM-4D618354BE4B.svg)](http://localhost:8000/datasets/DBOM-4D618354BE4B/dbom)

An auditable clinical reasoning and emergency triage supervised fine-tuning dataset cryptographically attested by **RasoSynthTune 2.0.0 Enterprise**.

## Dataset Specification
- **Domain**: Clinical Reasoning, Differential Diagnosis, and Emergency Triage (ESI Levels 1-3).
- **Format**: JSONL, Apache Parquet, Unsloth Python Recipe, Axolotl YAML Config.
- **Data Governance**: 100% synthetic/de-identified, zero clinical PII, verified DPDP & HIPAA compliant.
- **DBOM Certificate ID**: `DBOM-4D618354BE4B`
- **Cryptographic Merkle Root**: `4d618354be4b7a4c5b28ac8bdc87f1f2f0570cc3052e7a7b33487978194cc4fe`

## Cryptographic DBOM Attestation
```json
{
  "certificate_id": "DBOM-4D618354BE4B",
  "dataset_name": "flagship_clinical_sft",
  "merkle_root_hash": "4d618354be4b7a4c5b28ac8bdc87f1f2f0570cc3052e7a7b33487978194cc4fe",
  "total_records": 6,
  "pii_leakage": "0.00%",
  "contamination_score": "0.00%"
}
```

## Quick Start
```bash
# Verify cryptographic integrity
rasosynthtune audit --dataset flagship_clinical_sft.parquet --verify-dbom flagship_clinical_sft.dbom.json
```
