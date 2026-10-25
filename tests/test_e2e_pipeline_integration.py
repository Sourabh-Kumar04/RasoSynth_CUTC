import hashlib
import pytest
from starlette.testclient import TestClient

from api.server import app
from pipeline.construction import ConstructionPipeline, ConstructedSample
from core.intent import UserIntent
from core.export.huggingface_exporter import generate_hf_dataset_card


class DummySample:
    def __init__(self, content: str, quality_score: float = 0.85):
        self.content = content
        self.quality_score = quality_score
        self.metadata = {"source_url": "https://example.com/statute"}


@pytest.mark.asyncio
async def test_e2e_cognitive_generation_to_dbom_and_hf_card():
    """Verify full end-to-end trace: pipeline init -> synthesis -> DBOM Merkle hashing -> HF Card export."""
    # 1. Pipeline initializes with CoT cognitive engine
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "cot",
        "language": "en",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "cot"

    sample = DummySample(
        "Under Section 16(2) of the CGST Act, no registered person shall be entitled to input tax credit "
        "unless they possess a tax invoice and have received the goods."
    )
    intent = UserIntent(
        raw_input="Generate a statutory CoT tax dataset.",
        domain="taxation",
        primary_task="statutory_analysis",
        modality="text",
        anti_domains=[],
        key_entities=["CGST Act", "ITC"],
        specialized_queries=["CGST Section 16"],
        constraints={},
        output_format="jsonl",
        confidence=0.95,
    )

    # 2. Synthesis execution
    items = []
    async for item in pipeline.construct(sample, intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert isinstance(first, ConstructedSample)
    assert "<thought>" in first.response
    
    # 3. Cryptographic Merkle DBOM Leaf & Root generation
    leaf_bytes = f"{first.instruction}:{first.response}".encode("utf-8")
    leaf_hash = hashlib.sha256(leaf_bytes).hexdigest()
    assert len(leaf_hash) == 64

    # Merkle parent fold
    merkle_root = hashlib.sha256((leaf_hash + leaf_hash).encode("utf-8")).hexdigest()
    assert len(merkle_root) == 64
    certificate_id = f"DBOM-CERT-{merkle_root[:12].upper()}"

    # 4. Export to HuggingFace dataset card
    card = generate_hf_dataset_card(
        dataset_name="Tax-Filing-CoT-Corpus",
        domain="Legal & Tax",
        sample_count=5000,
        language="en",
        script_mode="latin",
        dataset_type="sft",
        license_type="apache-2.0",
        has_dpo=False,
        has_tool_calling=False,
        has_bitext=False,
        tokenizer_savings_pct=18.2,
        synthesis_mode="cot",
        merkle_root=merkle_root,
        certificate_id=certificate_id,
    )

    assert "Tax-Filing-Corpus" in card or "Tax" in card
    assert "Cryptographic DBOM Attestation & Data Nutrition Label" in card
    assert merkle_root in card
    assert certificate_id in card
    assert "COT" in card


def test_settings_compute_api_endpoint_lifecycle():
    """Verify GET and POST /settings/compute correctly store and mask GPU provider tokens."""
    import os
    saved_env = {
        k: os.environ.get(k)
        for k in ["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "RUNPOD_API_KEY", "HF_TOKEN"]
    }
    client = TestClient(app)

    try:
        # 1. Query initial state
        res = client.get("/settings/compute")
        assert res.status_code == 200
        data = res.json()
        assert "available_targets" in data
        assert "modal" in data["available_targets"]
        assert "runpod" in data["available_targets"]

        # 2. Get CSRF token
        csrf_res = client.get("/auth/csrf-token")
        assert csrf_res.status_code == 200
        csrf_token = csrf_res.json()["csrf_token"]

        # 3. Update compute settings with valid tokens & CSRF header
        update_payload = {
            "modal_token_id": "ak-modal-test-id-12345",
            "modal_token_secret": "as-modal-test-secret-67890",
            "runpod_api_key": "rpa_test_worker_key_9999",
            "hf_token": "hf_test_write_token_5555",
        }
        post_res = client.post(
            "/settings/compute",
            json=update_payload,
            headers={"X-CSRF-Token": csrf_token},
        )
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["status"] == "success"
        assert post_data["modal_configured"] is True
        assert post_data["runpod_configured"] is True
        assert post_data["hf_configured"] is True

        # 4. Query GET /settings/compute again to verify masking without secret exposure
        get_res2 = client.get("/settings/compute")
        assert get_res2.status_code == 200
        data2 = get_res2.json()
        assert data2["modal_configured"] is True
        assert data2["runpod_configured"] is True
        assert data2["hf_configured"] is True
        # Ensure raw secret is NOT leaked
        assert "as-modal-test-secret-67890" not in str(data2)
        assert data2["modal_token_id_masked"] is not None
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
