#!/usr/bin/env python3
"""
Example: End-to-End Grounded Synthetic Dataset Synthesis for Indian Legal & Tax Compliance.
Demonstrates:
1. ConstructionPipeline with Chain-of-Thought (CoT) reasoning engine.
2. Cryptographic SHA-256 Merkle DBOM leaf and root computation.
3. Automated Hugging Face README dataset card generation with embedded Data Nutrition Facts.
4. Export to certified JSONL artifact.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.intent import UserIntent
from core.export.dbom_attestor import compute_sample_hash, compute_merkle_root
from core.export.huggingface_exporter import generate_hf_dataset_card
from pipeline.construction import ConstructionPipeline


class GroundedLawSample:
    """Mock ground-truth reference seed extracted from CGST Act statutory gazette."""
    def __init__(self, content: str):
        self.content = content
        self.metadata = {
            "source_type": "statute",
            "statute_title": "Central Goods and Services Tax Act, 2017",
            "section": "Section 16",
        }


async def main():
    print("=" * 72)
    print("  RasoSynthTune SDK: Indic Legal CoT Synthesis & DBOM Packaging")
    print("=" * 72)

    # 1. User Intent Specification
    intent = UserIntent(
        raw_input="Synthesize high-fidelity legal reasoning pairs on Indian CGST Act input tax credits.",
        domain="Legal & Tax",
        primary_task="statutory_reasoning",
        modality="text",
        anti_domains=["entertainment", "sports"],
        key_entities=["CGST Act", "Input Tax Credit", "Section 16(2)", "Tax Invoice"],
        specialized_queries=["CGST Act Section 16 eligibility criteria for ITC"],
        constraints={"language": "en", "depth": "advanced"},
        output_format="jsonl",
        confidence=0.98,
    )

    # 2. Initialize Cognitive Synthesis Pipeline
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "cot",
        "language": "en",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    print(f"[1/4] Pipeline initialized with '{pipeline.synthesis_mode}' cognitive engine.")

    # 3. Grounded Seed Corpus
    raw_seed = (
        "Under Section 16(2) of the CGST Act 2017, no registered person shall be entitled "
        "to the credit of any input tax in respect of any supply of goods or services or both to him "
        "unless: (a) he is in possession of a tax invoice or debit note issued by a supplier, "
        "(b) he has received the goods or services or both, (c) subject to the provisions of section 41, "
        "the tax charged in respect of such supply has been actually paid to the Government, and "
        "(d) he has furnished the return under section 39."
    )
    seed_sample = GroundedLawSample(raw_seed)

    # 4. Synthesize Samples
    synthesized_items = []
    print("[2/4] Synthesizing reasoning pairs with cognitive rationale validation...")
    async for item in pipeline.construct(seed_sample, intent):
        synthesized_items.append({
            "instruction": item.instruction,
            "response": item.response,
            "source_statute": seed_sample.metadata["statute_title"],
            "section": seed_sample.metadata["section"],
        })

    print(f"      Generated {len(synthesized_items)} certified samples.")

    # 5. Cryptographic DBOM Attestation
    print("[3/4] Computing SHA-256 Merkle Provenance Tree...")
    leaves = [compute_sample_hash(s) for s in synthesized_items]
    merkle_root = compute_merkle_root(leaves)
    cert_id = f"DBOM-CERT-LEGAL-{merkle_root[:8].upper()}"
    print(f"      Merkle Root SHA-256: {merkle_root}")
    print(f"      Attestation ID:      {cert_id}")

    # 6. Generate Hugging Face Dataset Card
    print("[4/4] Generating Hugging Face Hub Dataset Card...")
    card_markdown = generate_hf_dataset_card(
        dataset_name="Indic-CGST-Statutory-Reasoning-v1",
        domain="Legal & Taxation",
        sample_count=len(synthesized_items),
        language="en",
        script_mode="latin",
        dataset_type="sft",
        license_type="apache-2.0",
        has_dpo=False,
        has_tool_calling=False,
        has_bitext=False,
        tokenizer_savings_pct=19.4,
        synthesis_mode="cot",
        merkle_root=merkle_root,
        certificate_id=cert_id,
    )

    # 7. Write to outputs directory
    out_dir = Path("outputs/example_indic_legal")
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / "dataset.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for item in synthesized_items:
            f.write(json.dumps(item) + "\n")

    readme_path = out_dir / "README.md"
    readme_path.write_text(card_markdown, encoding="utf-8")

    print("-" * 72)
    print(f"[OK] Synthesis complete. Artifacts packaged at: {out_dir}/")
    print(f"     • Samples:  {jsonl_path}")
    print(f"     • Card:     {readme_path}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
