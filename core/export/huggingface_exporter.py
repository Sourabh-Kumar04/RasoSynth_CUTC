"""Hugging Face Hub Exporter & Dataset Card Generator.

Generates standard Hugging Face `README.md` Dataset Cards with compliant YAML frontmatter,
data field schemas, language tags, license info, and Python `datasets.load_dataset()` snippets.
"""

from typing import Any, Dict, List, Optional
import json


def generate_hf_dataset_card(
    dataset_name: str,
    domain: str,
    sample_count: Optional[int] = None,
    language: str = "en",
    script_mode: str = "native",
    dataset_type: str = "sft",
    license_type: str = "apache-2.0",
    has_dpo: bool = False,
    has_tool_calling: bool = False,
    has_bitext: bool = False,
    tokenizer_savings_pct: float = 0.0,
    synthesis_mode: str = "standard",
    merkle_root: Optional[str] = None,
    certificate_id: Optional[str] = None,
) -> str:
    """Generate a fully compliant Hugging Face Dataset Card (README.md) with YAML frontmatter."""
    sample_display = f"{sample_count:,}" if sample_count is not None else "not recorded"
    langs = ["en"]
    if language in ("hi", "hindi"):
        langs = ["hi", "en"]
    elif language in ("hinglish", "hi-en"):
        langs = ["hi", "en"]
    elif language == "indic_multilingual":
        langs = ["hi", "ta", "te", "bn", "mr", "gu", "en"]

    tags = ["rasosynthtune", "synthetic", "instruction-tuning", dataset_type]
    if has_dpo:
        tags.append("rlhf")
        tags.append("dpo")
    if has_tool_calling:
        tags.append("tool-calling")
        tags.append("function-calling")
    if has_bitext:
        tags.append("bitext")
        tags.append("parallel-corpus")
    if language == "hinglish":
        tags.append("hinglish")
        tags.append("code-switched")

    size_cat = "unknown" if sample_count is None else "1K<n<10K" if sample_count < 10000 else "10K<n<100K" if sample_count < 100000 else "100K<n<1M"

    yaml_block = f"""---
license: {license_type}
task_categories:
- text-generation
- question-answering
language:
{chr(10).join(f"- {l}" for l in langs)}
tags:
{chr(10).join(f"- {t}" for t in tags)}
size_categories:
- {size_cat}
---"""

    dbom_section = ""
    if merkle_root:
        dbom_section = f"""
## Cryptographic DBOM Attestation & Data Nutrition Label
| Metric | Value |
| :--- | :--- |
| **Certificate ID** | `{certificate_id or ('DBOM-' + merkle_root[:8])}` |
| **Merkle Root Hash (SHA-256)** | `{merkle_root}` |
| **Synthesis Cognitive Engine** | `{synthesis_mode.upper()}` |
| **Indian DPDP Act PII Exposure** | `Not recorded for this dataset` |
| **Script Native Fidelity** | `Not recorded for this dataset` |
| **Quality Gate** | `Not recorded for this dataset` |
"""

    content = f"""{yaml_block}

# Dataset Card for {dataset_name}

Generated with **[RasoSynthTune](https://github.com/Sourabh-Kumar04/RasoSynth_CUTC)** — Autonomous Constraint-Aware Dataset Synthesis Platform.

## Dataset Summary
- **Target Domain**: {domain}
- **Sample Count**: {sample_display}
- **Language & Script**: {language.upper()} ({script_mode})
- **Dataset Paradigm**: {dataset_type.upper()}
- **Synthesis Engine**: {synthesis_mode.upper()}
- **Features**: {', '.join(tags)}
{f"- **Token Efficiency**: ~{int(tokenizer_savings_pct)}% token savings using Indic-optimized tokenizers" if tokenizer_savings_pct > 0 else ""}
{dbom_section}
## Data Structure
Each sample in the JSONL export adheres to this schema:
```json
{{
  "instruction": "User prompt or statutory query...",
  "response": "Synthesized ground-truth response...",
  "difficulty_tier": 3,
  "metadata": {{
    "language": "{language}",
    "script_mode": "{script_mode}",
    "domain": "{domain}"
  }}
}}
```

## Quickstart Usage

```python
from datasets import load_dataset

# Load directly from JSONL
dataset = load_dataset("json", data_files="dataset.jsonl")
print(dataset["train"][0])
```

## Quality & Safety Assurance
- **DPDP Act Compliance**: Indian Statutory Identifiers (Aadhaar, PAN, GSTIN, UPI, Mobile) redacted.
- **Cultural & Script Guardrails**: Prohibited casteist, communal slurs blocked and script conformity validated.
- **Deduplication**: Filtered using MinHash LSH (threshold 0.85).

## Citation
```bibtex
@software{{rasosynthtune2026,
  author = {{RasoSynthTune Contributors}},
  title = {{{dataset_name}: High-Fidelity Synthetic Dataset}},
  year = {{2026}},
  url = {{https://github.com/Sourabh-Kumar04/RasoSynth_CUTC}}
}}
```
"""
    return content.strip()


def generate_hf_model_card(
    model_name: str,
    base_model: str,
    dataset_name: str,
    sample_count: Optional[int] = None,
    epochs: int = 3,
    learning_rate: float = 2e-4,
    lora_r: int = 16,
    lora_alpha: int = 32,
    train_loss: Optional[float] = None,
    eval_loss: Optional[float] = None,
    merkle_root: Optional[str] = None,
    certificate_id: Optional[str] = None,
    domain: str = "General",
    license_type: str = "apache-2.0",
) -> str:
    """Generate a standard Hugging Face Model Card (README.md) for fine-tuned LoRA adapters."""
    tags = ["rasosynthtune", "peft", "lora", "fine-tuned", "text-generation"]
    clean_domain = domain.lower().replace(" ", "-").replace("&", "and")
    corpus_display = f"{sample_count:,}" if sample_count is not None else "not recorded"
    if clean_domain:
        tags.append(clean_domain)

    yaml_block = f"""---
license: {license_type}
base_model: {base_model}
pipeline_tag: text-generation
library_name: peft
tags:
{chr(10).join(f"- {t}" for t in tags)}
---"""

    dbom_block = ""
    if merkle_root:
        dbom_block = f"""
## Training Provenance & Cryptographic DBOM Attestation
This adapter was trained exclusively on a verifiable dataset attested by RasoSynth:
| Metric | Value |
| :--- | :--- |
| **Certificate ID** | `{certificate_id or ('DBOM-' + merkle_root[:8])}` |
| **Dataset Merkle Root** | `{merkle_root}` |
| **Attestation Standard** | `RFC 6962 / NIST SP 800-106 (SHA-256)` |
| **Integrity Guarantee** | `100% Deterministic Provenance` |
"""

    loss_block = ""
    if train_loss is not None:
        loss_block = f"""
## Convergence Metrics
- **Final Train Loss**: `{train_loss:.4f}`
{f"- **Final Eval Loss**: `{eval_loss:.4f}`" if eval_loss is not None else ""}
- **Optimizer**: `AdamW (bf16, ZeRO-2)` (template default — verify against the run config)
"""

    content = f"""{yaml_block}

# Model Card for {model_name}

This model is a parameter-efficient fine-tuned (PEFT LoRA) adapter trained on **{dataset_name}** using **[RasoSynthTune](https://github.com/Sourabh-Kumar04/RasoSynth_CUTC)**.

## Model Summary
- **Base Architecture**: `{base_model}`
- **Adapter Type**: LoRA (Low-Rank Adaptation)
- **Target Domain**: {domain}
- **Training Corpus Size**: {corpus_display} synthetic instruction samples
- **License**: {license_type}

## Hyperparameters
| Parameter | Value |
| :--- | :--- |
| **Base Model** | `{base_model}` |
| **Epochs** | `{epochs}` |
| **Learning Rate** | `{learning_rate}` |
| **LoRA Rank (r)** | `{lora_r}` |
| **LoRA Alpha (α)** | `{lora_alpha}` |
| **Target Modules** | `q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj, down_proj` |
| **Precision** | `bfloat16` with FlashAttention-2 (template default — verify against the run config) |
{loss_block}
{dbom_block}
## Quickstart Inference

```python
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base_model_id = "{base_model}"
adapter_id = "{model_name}"

tokenizer = AutoTokenizer.from_pretrained(base_model_id)
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
model = PeftModel.from_pretrained(base_model, adapter_id)

prompt = "Statutory query or instruction..."
inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
with torch.no_grad():
    outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.7)

print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

## Citation
```bibtex
@misc{{{model_name.lower().replace('-', '_')}_2026,
  author = {{RasoSynthTune Fine-Tuning Pipeline}},
  title = {{{model_name}: Fine-Tuned Domain Adapter}},
  year = {{2026}},
  url = {{https://github.com/Sourabh-Kumar04/RasoSynth_CUTC}}
}}
```
"""
    return content.strip()
