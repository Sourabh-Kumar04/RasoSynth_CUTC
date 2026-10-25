#!/usr/bin/env python3
"""
Seed script to populate RasoSynthTune with realistic demo datasets,
fine-tuning runs, and cryptographic DBOM certificates for offline presentations.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_settings
from core.export.dbom_attestor import compute_sample_hash, compute_merkle_root
from core.export.huggingface_exporter import generate_hf_dataset_card


DEMO_DATASETS = [
    {
        "job_id": "job-demo-tax-cot-01",
        "domain": "Finance & Indian Taxation",
        "synthesis_mode": "cot",
        "sample_count": 5000,
        "language": "en",
        "script": "latin",
        "samples": [
            {
                "instruction": "Explain conditions for claiming Input Tax Credit under Section 16(2) of CGST Act.",
                "response": "<thought>Section 16(2) prescribes 4 mandatory cumulative conditions: tax invoice possession, goods receipt, tax payment to Govt, return filing.</thought>Under Section 16(2), registered persons must satisfy all four statutory conditions...",
            },
            {
                "instruction": "How is reverse charge mechanism (RCM) calculated for legal advisory services under GST?",
                "response": "<thought>Services provided by advocates/law firms to business entities with turnover > threshold fall under 100% RCM.</thought>The recipient business entity pays 18% GST directly to the government...",
            },
        ],
    },
    {
        "job_id": "job-demo-clinical-triage-02",
        "domain": "Emergency Medicine Triage",
        "synthesis_mode": "socratic",
        "sample_count": 2500,
        "language": "en",
        "script": "latin",
        "samples": [
            {
                "instruction": "Patient presents with acute retrosternal chest pressure and diaphoresis.",
                "response": "What is the onset timeline? Does the pain radiate to the left mandible or arm? Obtain an immediate 12-lead ECG within 10 minutes to rule out STEMI.",
            },
        ],
    },
    {
        "job_id": "job-demo-agent-tool-03",
        "domain": "Autonomous Tool Calling",
        "synthesis_mode": "tool_calling",
        "sample_count": 3000,
        "language": "en",
        "script": "latin",
        "samples": [
            {
                "instruction": "Fetch currency exchange rate from USD to INR for invoice calculation.",
                "response": "```json\n{\"tool\": \"get_exchange_rate\", \"parameters\": {\"from\": \"USD\", \"to\": \"INR\"}}\n```",
            },
        ],
    },
]


def seed_demo_artifacts(output_base: str = "outputs/demo_seed") -> Dict[str, Any]:
    """Generate demo JSONL files and Hugging Face README cards on disk."""
    base_path = Path(output_base)
    base_path.mkdir(parents=True, exist_ok=True)

    summary = []
    for item in DEMO_DATASETS:
        d_dir = base_path / item["job_id"]
        d_dir.mkdir(parents=True, exist_ok=True)

        # Write samples to jsonl
        jsonl_file = d_dir / "dataset.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for s in item["samples"]:
                f.write(json.dumps(s) + "\n")

        # Compute Merkle DBOM
        leaves = [compute_sample_hash(s) for s in item["samples"]]
        merkle_root = compute_merkle_root(leaves)
        cert_id = f"DBOM-DEMO-{merkle_root[:8].upper()}"

        # Write metadata.dbom.json
        dbom_file = d_dir / "metadata.dbom.json"
        dbom_data = {
            "job_id": item["job_id"],
            "domain": item["domain"],
            "synthesis_mode": item["synthesis_mode"],
            "sample_count": item["sample_count"],
            "merkle_root_hash": merkle_root,
            "certificate_id": cert_id,
        }
        dbom_file.write_text(json.dumps(dbom_data, indent=2), encoding="utf-8")

        # Write README.md card
        readme_file = d_dir / "README.md"
        card_content = generate_hf_dataset_card(
            dataset_name=f"{item['domain'].replace(' ', '-')}-Instruct",
            domain=item["domain"],
            sample_count=item["sample_count"],
            language=item["language"],
            script_mode=item["script"],
            dataset_type="sft",
            license_type="apache-2.0",
            has_dpo=False,
            has_tool_calling=(item["synthesis_mode"] == "tool_calling"),
            has_bitext=False,
            tokenizer_savings_pct=22.5,
            synthesis_mode=item["synthesis_mode"],
            merkle_root=merkle_root,
            certificate_id=cert_id,
        )
        readme_file.write_text(card_content, encoding="utf-8")

        summary.append({
            "job_id": item["job_id"],
            "domain": item["domain"],
            "merkle_root": merkle_root,
            "certificate_id": cert_id,
            "directory": str(d_dir),
        })

    return {
        "status": "seeded",
        "datasets_created": len(summary),
        "details": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed RasoSynthTune demo artifacts & DBOMs")
    parser.add_argument("--output-dir", default="outputs/demo_seed", help="Target output directory")
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args()

    res = seed_demo_artifacts(args.output_dir)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print("=" * 72)
        print("  RasoSynthTune: Demo Data & Cryptographic DBOM Seeder")
        print("=" * 72)
        print(f"Total Datasets Seeded: {res['datasets_created']}")
        print("-" * 72)
        for d in res["details"]:
            print(f"  • {d['domain']}")
            print(f"    - Job ID:       {d['job_id']}")
            print(f"    - Merkle Root:  {d['merkle_root']}")
            print(f"    - Certificate:  {d['certificate_id']}")
            print(f"    - Directory:    {d['directory']}")
        print("=" * 72)


if __name__ == "__main__":
    main()
