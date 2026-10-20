---
license: apache-2.0
task_categories:
- text-generation
- question-answering
language:
- en
tags:
- corporate-law
- companies-act
- mca-21
- nclt
- dbom
- rasosynthtune
size_categories:
- n<1K
---

# Indian Corporate Law & MCA-21 Instruct SFT (v1.0.0)

[![Cryptographic DBOM Verified](http://localhost:8000/badges/dbom/DBOM-29BBC5134393.svg)](http://localhost:8000/datasets/DBOM-29BBC5134393/dbom)

An auditable corporate legal reasoning and regulatory compliance dataset cryptographically attested by **RasoSynthTune 2.0.0 Enterprise**.

## Dataset Specification
- **Domain**: Companies Act 2013, NCLT Adjudication, MCA-21 Filings, IBC 2016, SEBI LODR.
- **Format**: JSONL, Apache Parquet, Unsloth Python Recipe, Axolotl YAML Config.
- **Data Governance**: 100% synthetic/de-identified, zero statutory PII, DPDP Act compliant.
- **DBOM Certificate ID**: `DBOM-29BBC5134393`
- **Cryptographic Merkle Root**: `29bbc51343935d09c379ef248f27af2305b136b4e91f4a1d76e97682b7d8a122`

## Cryptographic DBOM Attestation
```json
{
  "certificate_id": "DBOM-29BBC5134393",
  "dataset_name": "flagship_corporate_law_sft",
  "merkle_root_hash": "29bbc51343935d09c379ef248f27af2305b136b4e91f4a1d76e97682b7d8a122",
  "total_records": 5,
  "pii_leakage": "0.00%",
  "contamination_score": "0.00%"
}
```

## Quick Start
```bash
# Verify cryptographic integrity
rasosynthtune audit --dataset flagship_corporate_law_sft.parquet --verify-dbom flagship_corporate_law_sft.dbom.json
```
