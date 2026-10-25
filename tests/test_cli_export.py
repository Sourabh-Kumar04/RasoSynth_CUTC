import json
import pytest
from pathlib import Path
from scripts.publish_to_huggingface import publish_dataset_to_hub


def test_cli_publish_dry_run_generates_dbom_card(tmp_path):
    """Verify publish_dataset_to_hub in dry_run mode generates README.md with DBOM attestation."""
    # Create sample jsonl file
    sample_file = tmp_path / "train.jsonl"
    sample_file.write_text(
        json.dumps({"instruction": "Define GST", "response": "Goods and Services Tax"}) + "\n"
    )

    # Create dummy DBOM file
    dbom_file = tmp_path / "metadata.dbom.json"
    dbom_data = {
        "merkle_root_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
        "certificate_id": "DBOM-CERT-GST-9999",
        "sample_count": 1,
        "synthesis_mode": "cot",
    }
    dbom_file.write_text(json.dumps(dbom_data))

    res = publish_dataset_to_hub(
        dataset_dir=tmp_path,
        repo_id="testuser/gst-dataset",
        dry_run=True,
    )

    assert res["status"] == "dry_run_success"
    assert res["merkle_root"] == "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    assert res["certificate_id"] == "DBOM-CERT-GST-9999"

    # Verify generated README.md
    readme_path = tmp_path / "README.md"
    assert readme_path.exists()
    content = readme_path.read_text()
    assert "Cryptographic DBOM Attestation & Data Nutrition Label" in content
    assert "DBOM-CERT-GST-9999" in content
    assert "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90" in content
