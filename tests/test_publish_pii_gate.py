import json
import pytest
from pathlib import Path
from scripts.publish_to_huggingface import scan_and_gate_pii, publish_dataset_to_hub
from core.export.huggingface_exporter import PROJECT_LICENSE


def test_pii_scrub_gate_refuses_unscrubbed_data(tmp_path: Path):
    d = tmp_path / "dataset"
    d.mkdir()
    jsonl = d / "samples.jsonl"
    dbom = d / "test.dbom.json"
    
    # Write sample containing an Indian PAN card
    sample = {
        "instruction": "Verify PAN card ABCDE1234F for tax deduction.",
        "response": "PAN ABCDE1234F is registered.",
    }
    jsonl.write_text(json.dumps(sample) + "\n", encoding="utf-8")
    dbom.write_text(json.dumps({
        "certificate_id": "DBOM-TEST-1234",
        "merkle_root_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "sample_count": 1,
    }), encoding="utf-8")

    # Gating should raise ValueError
    with pytest.raises(ValueError, match="PII Scrub Gate Refusal"):
        publish_dataset_to_hub(
            dataset_dir=d,
            repo_id="test/pan-dataset",
            dry_run=True,
            auto_scrub_pii=False,
        )


def test_pii_scrub_gate_auto_scrub_succeeds(tmp_path: Path):
    d = tmp_path / "dataset"
    d.mkdir()
    jsonl = d / "samples.jsonl"
    dbom = d / "test.dbom.json"
    
    sample = {
        "instruction": "Verify PAN card ABCDE1234F for tax deduction.",
        "response": "PAN ABCDE1234F is registered.",
    }
    jsonl.write_text(json.dumps(sample) + "\n", encoding="utf-8")
    dbom.write_text(json.dumps({
        "certificate_id": "DBOM-TEST-1234",
        "merkle_root_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "sample_count": 1,
    }), encoding="utf-8")

    result = publish_dataset_to_hub(
        dataset_dir=d,
        repo_id="test/pan-dataset",
        dry_run=True,
        auto_scrub_pii=True,
    )
    assert result["status"] == "dry_run_success"
    
    # Verify file content was scrubbed
    updated_content = jsonl.read_text(encoding="utf-8")
    assert "ABCDE1234F" not in updated_content
    assert "[PAN_REDACTED]" in updated_content
