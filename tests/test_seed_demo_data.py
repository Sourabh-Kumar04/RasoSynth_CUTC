from pathlib import Path
from scripts.seed_demo_data import seed_demo_artifacts


def test_seed_demo_artifacts(tmp_path):
    """Verify demo seeder outputs datasets, metadata.dbom.json, and verified README.md."""
    target_dir = tmp_path / "demo_output"
    res = seed_demo_artifacts(str(target_dir))

    assert res["status"] == "seeded"
    assert res["datasets_created"] == 3
    assert len(res["details"]) == 3

    for item in res["details"]:
        d_path = Path(item["directory"])
        assert d_path.exists()
        assert (d_path / "dataset.jsonl").exists()
        assert (d_path / "metadata.dbom.json").exists()
        assert (d_path / "README.md").exists()

        readme_content = (d_path / "README.md").read_text()
        assert "Cryptographic DBOM Attestation & Data Nutrition Label" in readme_content
        assert item["merkle_root"] in readme_content
        assert item["certificate_id"] in readme_content
