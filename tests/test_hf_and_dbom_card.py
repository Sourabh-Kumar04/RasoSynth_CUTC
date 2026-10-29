import pytest
from core.export.huggingface_exporter import generate_hf_dataset_card
from core.export.hf_hub_publisher import publish_dataset_to_hf_hub


def test_generate_hf_dataset_card_with_dbom_attestation():
    card = generate_hf_dataset_card(
        dataset_name="GST-Tax-CoT-Reasoning",
        domain="Finance & Taxation",
        sample_count=10000,
        language="hi",
        script_mode="native",
        dataset_type="sft",
        license_type="apache-2.0",
        has_dpo=True,
        has_tool_calling=False,
        has_bitext=True,
        tokenizer_savings_pct=24.5,
        synthesis_mode="cot",
        merkle_root="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        certificate_id="DBOM-2026-TAX-01",
    )

    assert "---" in card
    assert "license: apache-2.0" in card
    assert "dpo" in card
    assert "COT" in card
    assert "Cryptographic DBOM Attestation & Data Nutrition Label" in card
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in card
    assert "DBOM-2026-TAX-01" in card
    # P0 honesty: no DPDP compliance is claimed; the card states that explicitly.
    assert "DPDP Act Compliance" not in card
    assert "no DPDP Act compliance is claimed or verified" in card


def test_publish_dataset_to_hf_hub_requires_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Hugging Face Hub token is required"):
        publish_dataset_to_hf_hub(
            repo_id="user/test-dataset",
            readme_content="# Test",
            samples=[{"instruction": "q", "response": "a"}],
            hf_token="",
        )


def test_publish_dataset_to_hf_hub_validates_repo_format():
    with pytest.raises(ValueError, match="Invalid repo_id format"):
        publish_dataset_to_hf_hub(
            repo_id="invalid-repo-without-slash",
            readme_content="# Test",
            samples=[{"instruction": "q", "response": "a"}],
            hf_token="hf_mock_token_12345",
        )
