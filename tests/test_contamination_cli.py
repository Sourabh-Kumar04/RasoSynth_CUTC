import json
from scripts.check_contamination import load_dataset_samples, run_audit


def test_contamination_audit_clean_dataset(tmp_path):
    """Verify clean dataset records produce zero contamination."""
    clean_file = tmp_path / "clean_dataset.jsonl"
    clean_samples = [
        {
            "instruction": "Explain the concept of Input Tax Credit under Section 16 CGST Act.",
            "response": "ITC allows registered taxpayers to set off taxes paid on inputs against output tax liability.",
        },
        {
            "instruction": "Discuss the applicability of Section 479 of the Bharatiya Nagarik Suraksha Sanhita 2023.",
            "response": "Section 479 of BNSS provides statutory relief for undertrial prisoners who have completed one-half or one-third of the maximum sentence.",
        },
    ]

    with open(clean_file, "w", encoding="utf-8") as f:
        for s in clean_samples:
            f.write(json.dumps(s) + "\n")

    loaded = load_dataset_samples(clean_file)
    assert len(loaded) == 2

    report = run_audit(loaded)
    assert report["status"] == "clean"
    assert report["total_samples_audited"] == 2
    assert report["clean_samples_count"] == 2
    assert report["contaminated_samples_count"] == 0
    assert report["contamination_rate_pct"] == 0.0
    assert "CONTAM-AUDIT-" in report["audit_certificate_id"]


def test_contamination_audit_detects_probe():
    """Verify contamination detection on known benchmark canary strings."""
    probe_samples = [
        {
            "instruction": "Solve: natalia sold clips to 48 of her friends in april how many did she sell?",
            "response": "She sold 48 clips.",
        }
    ]

    report = run_audit(probe_samples, benchmarks=["gsm8k"])
    assert report["status"] == "contamination_detected"
    assert report["contaminated_samples_count"] == 1
    assert len(report["contaminated_records"]) == 1
    assert report["contaminated_records"][0]["matches"][0]["benchmark"] == "gsm8k"
