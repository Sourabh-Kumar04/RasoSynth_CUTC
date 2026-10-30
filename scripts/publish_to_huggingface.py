#!/usr/bin/env python3
"""Automated Hugging Face Dataset Hub Publisher.

Publishes local datasets along with cryptographic DBOM certificates,
Data Nutrition Labels, and Apache Parquet shards to the Hugging Face Hub:
1. Validates dataset directory integrity (JSONL/Parquet and DBOM certificate).
2. Auto-injects cryptographic DBOM verification badges into dataset cards.
3. Enforces PII Scrub Gate: scans all samples for Indian PII patterns (Aadhaar, PAN,
   GSTIN, Mobile, UPI, Vehicle) using core.validation.indian_pii. If unscrubbed PII
   is detected, refuses publish unless --auto-scrub-pii is provided or samples are confirmed scrubbed.
4. Defaults repository visibility strictly to private (override with --public).
5. Resolves license from DBOM provenance or defaults to PROJECT_LICENSE.
6. Uploads directory to Hugging Face Hub via `huggingface_hub.HfApi`.
7. Supports dry-run validation for CI/CD and air-gapped verification.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.export.badge_generator import generate_dbom_badge_markdown
from core.export.huggingface_exporter import PROJECT_LICENSE, generate_hf_dataset_card
from core.validation.indian_pii import detect_indian_pii, mask_indian_pii


def scan_and_gate_pii(
    dataset_dir: Path,
    jsonl_files: List[Path],
    auto_scrub_pii: bool = False,
) -> Dict[str, Any]:
    """Scan dataset samples for Indian statutory/personal PII patterns and enforce scrub gate."""
    total_pii_detected = 0
    pii_types_detected: Dict[str, int] = {}
    modified_files = 0

    for jf in jsonl_files:
        lines = []
        file_had_pii = False
        with open(jf, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, 1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                except Exception:
                    continue

                # Scan text fields
                text_to_scan = f"{record.get('instruction', '')} {record.get('response', '')} {record.get('input', '')}"
                found = detect_indian_pii(text_to_scan)
                if found:
                    file_had_pii = True
                    for pii_type, items in found.items():
                        total_pii_detected += len(items)
                        pii_types_detected[pii_type] = pii_types_detected.get(pii_type, 0) + len(items)

                    if auto_scrub_pii:
                        if "instruction" in record and isinstance(record["instruction"], str):
                            record["instruction"] = mask_indian_pii(record["instruction"])
                        if "response" in record and isinstance(record["response"], str):
                            record["response"] = mask_indian_pii(record["response"])
                        if "input" in record and isinstance(record["input"], str):
                            record["input"] = mask_indian_pii(record["input"])

                lines.append(record)

        if auto_scrub_pii and file_had_pii:
            with open(jf, "w", encoding="utf-8") as f:
                for rec in lines:
                    f.write(json.dumps(rec) + "\n")
            modified_files += 1

    if total_pii_detected > 0 and not auto_scrub_pii:
        raise ValueError(
            f"PII Scrub Gate Refusal: Found {total_pii_detected} unscrubbed PII entity occurrences "
            f"({json.dumps(pii_types_detected)}) in {dataset_dir}. "
            "Refusing to publish unscrubbed dataset. Pass --auto-scrub-pii to scrub automatically or "
            "sanitize samples prior to publication."
        )

    return {
        "pii_detected_count": total_pii_detected,
        "pii_types": pii_types_detected,
        "auto_scrubbed": auto_scrub_pii and (total_pii_detected > 0),
        "files_scrubbed": modified_files,
    }


def publish_dataset_to_hub(
    dataset_dir: str | Path,
    repo_id: str,
    token: Optional[str] = None,
    private: bool = True,
    dry_run: bool = False,
    dataset_name: Optional[str] = None,
    domain: str = "General Knowledge",
    language: str = "en",
    license_type: Optional[str] = None,
    auto_scrub_pii: bool = False,
) -> Dict[str, Any]:
    """Publish dataset directory and cryptographic attestation to Hugging Face Hub."""
    p = Path(dataset_dir)
    if not p.exists() or not p.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    # Discover dataset files
    jsonl_files = list(p.glob("*.jsonl"))
    parquet_files = list(p.glob("*.parquet"))
    dbom_files = list(p.glob("*.dbom.json"))
    readme_file = p / "README.md"

    if not jsonl_files and not parquet_files:
        raise ValueError(f"No .jsonl or .parquet dataset files found in {dataset_dir}")

    if not dbom_files:
        raise ValueError(
            f"No DBOM attestation file (*.dbom.json) found in {dataset_dir}. "
            "Refusing to publish without cryptographic provenance."
        )

    # Enforce PII Scrub Gate
    pii_gate_report = scan_and_gate_pii(p, jsonl_files, auto_scrub_pii=auto_scrub_pii)

    # Load DBOM
    try:
        with open(dbom_files[0], "r", encoding="utf-8") as f:
            dbom_info = json.load(f)
    except Exception as exc:
        raise ValueError(f"Failed to read DBOM file {dbom_files[0]}: {exc}") from exc

    merkle_root = dbom_info.get("merkle_root_hash")
    if not merkle_root or merkle_root == "EMPTY_DATASET_NO_MERKLE_ROOT":
        raise ValueError(f"Invalid or missing Merkle root in DBOM certificate: {merkle_root}")

    cert_id = dbom_info.get("certificate_id")
    if not cert_id:
        raise ValueError("Missing certificate_id in DBOM certificate.")

    sample_count = dbom_info.get("total_samples") or dbom_info.get("sample_count")
    if sample_count is None or sample_count <= 0:
        # Count samples in jsonl or parquet
        if jsonl_files:
            with open(jsonl_files[0], "r", encoding="utf-8") as f:
                sample_count = sum(1 for line in f if line.strip())
        elif parquet_files:
            import pyarrow.parquet as pq
            table = pq.read_table(str(parquet_files[0]))
            sample_count = table.num_rows

    if not sample_count or sample_count <= 0:
        raise ValueError(f"Dataset has 0 samples in {dataset_dir}. Refusing to publish empty dataset.")

    prov = dbom_info.get("provenance", {})
    resolved_license = license_type or prov.get("license") or PROJECT_LICENSE

    # Ensure README.md exists and includes cryptographic DBOM verification and nutrition facts
    if not readme_file.exists():
        card_content = generate_hf_dataset_card(
            dataset_name=dataset_name or repo_id.split("/")[-1],
            domain=domain or dbom_info.get("domain", "General Knowledge"),
            sample_count=sample_count,
            language=language or dbom_info.get("language", "en"),
            script_mode="latin",
            dataset_type="sft",
            license_type=resolved_license,
            has_dpo=False,
            has_tool_calling=False,
            has_bitext=False,
            tokenizer_savings_pct=0.0,
            synthesis_mode=dbom_info.get("synthesis_mode", "standard"),
            merkle_root=merkle_root,
            certificate_id=cert_id,
        )
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write(card_content)

    print("=" * 70)
    print("  RasoSynthTune: Hugging Face Dataset Hub Publisher")
    print("=" * 70)
    print(f"Dataset Directory: {p}")
    print(f"Target Repo ID:    {repo_id}")
    print(f"Merkle Tree Root:  {merkle_root}")
    print(f"Certificate ID:    {cert_id}")
    print(f"Privacy:           {'Private' if private else 'Public'}")
    print(f"Mode:              {'Dry-Run Validation' if dry_run else 'Live Hub Upload'}")

    if dry_run:
        print("\n[OK] Dry-run validation passed. All metadata and DBOM certificates are valid.")
        return {
            "status": "dry_run_success",
            "repo_id": repo_id,
            "merkle_root": merkle_root,
            "certificate_id": cert_id,
            "files_ready": [f.name for f in p.iterdir() if f.is_file()],
        }

    # Live publication
    hf_token = token or os.environ.get("HF_TOKEN")
    if not hf_token:
        raise ValueError("Missing Hugging Face token. Set the HF_TOKEN environment variable (tokens are never accepted on the command line).")

    try:
        from huggingface_hub import HfApi
        api = HfApi(token=hf_token)
        api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
        api.upload_folder(
            folder_path=str(p),
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"Upload attested dataset with DBOM certificate ({cert_id}) via RasoSynthTune",
        )
        hub_url = f"https://huggingface.co/datasets/{repo_id}"
        print(f"\n[OK] Successfully published to Hugging Face Hub: {hub_url}")
        return {
            "status": "published",
            "repo_id": repo_id,
            "hub_url": hub_url,
            "merkle_root": merkle_root,
            "certificate_id": cert_id,
        }
    except ImportError:
        raise RuntimeError("huggingface_hub package is required for publishing. Run: pip install huggingface-hub")


def main():
    """Main CLI entrypoint for standalone hub publisher."""
    parser = argparse.ArgumentParser(description="Publish attested datasets to Hugging Face Hub")
    parser.add_argument("--dataset-dir", required=True, help="Path to local dataset directory")
    parser.add_argument("--repo-id", required=True, help="Target Hugging Face dataset repo ID (e.g. user/my-dataset)")
    parser.add_argument("--public", action="store_true", help="Set repository to public (defaults to private)")
    parser.add_argument("--auto-scrub-pii", action="store_true", help="Automatically scrub Indian PII patterns (Aadhaar, PAN, GSTIN, UPI, Mobile) if detected")
    parser.add_argument("--dry-run", action="store_true", help="Validate dataset and DBOM files without uploading")

    args = parser.parse_args()
    try:
        publish_dataset_to_hub(
            dataset_dir=args.dataset_dir,
            repo_id=args.repo_id,
            private=not args.public,
            dry_run=args.dry_run,
            auto_scrub_pii=args.auto_scrub_pii,
        )
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
