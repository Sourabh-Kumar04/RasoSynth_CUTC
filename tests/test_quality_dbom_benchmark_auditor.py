"""
Comprehensive test suite verifying Quality evaluation, LLM-as-a-judge, DBOM cryptographic verification,
and benchmark evaluation systems (core.dbom, core.evaluator, api.dbom, api.quality, research.quality_benchmark).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# 1. Test core.dbom and core.export.dbom_attestor
from core.dbom import (
    compute_sample_hash,
    compute_merkle_root,
    generate_dbom_attestation,
    verify_dataset_dbom,
    generate_nutrition_label_markdown,
    DatasetAttestationSigner,
    SignedAttestationBundle,
    generate_dbom_badge_svg,
)


def test_dbom_merkle_cryptographic_integrity():
    """Verify that Merkle tree produces deterministic SHA-256 root and detects single-bit tampering."""
    samples = [
        {"instruction": "Explain Section 9 of CGST Act.", "response": "Levy and collection of GST on intra-state supplies."},
        {"instruction": "Define Input Tax Credit.", "response": "Credit of input tax charged on supply of goods or services."},
        {"instruction": "What is an e-way bill?", "response": "Electronic document generated for movement of goods exceeding threshold."},
    ]
    leaf_hashes = [compute_sample_hash(s) for s in samples]
    root = compute_merkle_root(leaf_hashes)

    assert len(root) == 64
    assert all(len(h) == 64 for h in leaf_hashes)

    # Verification passes
    dbom = generate_dbom_attestation("GST Test", samples, domain="taxation")
    assert dbom["merkle_root_hash"] == root
    assert dbom["certificate_id"] == f"DBOM-{root[:12].upper()}"

    res = verify_dataset_dbom(samples, dbom)
    assert res["is_valid"] is True
    assert res["status"] == "cryptographically_verified"

    # Single-bit tampering detection
    tampered_samples = list(samples)
    tampered_samples[1] = {"instruction": "Define Input Tax Credit.", "response": "Credit of tax charged on inward supply of goods or services."}
    tampered_res = verify_dataset_dbom(tampered_samples, dbom)
    assert tampered_res["is_valid"] is False
    assert tampered_res["status"] == "tampering_or_mismatch_detected"


def test_dbom_attestation_kwargs_robustness():
    """Verify generate_dbom_attestation accepts extra kwargs without TypeError."""
    samples = [
        {"instruction": "Compute TDS rate.", "response": "TDS rate under Section 194C is 1% for individual/HUF and 2% for others."}
    ]
    dbom = generate_dbom_attestation(
        dataset_name="TDS SFT",
        samples=samples,
        domain="taxation",
        language="en",
        license_type="PolyForm-Noncommercial-1.0.0",
        dataset_id="job-custom-123",
        sources=[{"name": "Gov Tax Portal", "type": "web"}],
        sample_count=1,
        pii_entity_counts={"pan": 0},
        contamination_score=0.00,
        pipeline_version="2.0.0",
    )
    assert dbom["dataset_id"] == "job-custom-123"
    assert dbom["provenance"]["sources"] == [{"name": "Gov Tax Portal", "type": "web"}]
    assert dbom["total_samples"] == 1


def test_dbom_ecdsa_asymmetric_signatures():
    """Verify In-Toto statement generation and ECDSA SECP256R1 digital signing & verification."""
    signer = DatasetAttestationSigner()
    merkle_root = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    bundle = signer.sign_attestation(
        dataset_name="Secured Dataset",
        merkle_root=merkle_root,
        sample_count=500,
    )
    assert isinstance(bundle, SignedAttestationBundle)
    assert bundle.merkle_root == merkle_root
    assert len(bundle.signature) > 32
    assert "BEGIN PUBLIC KEY" in bundle.public_key_pem

    # Verify signature
    is_valid = DatasetAttestationSigner.verify_attestation(
        statement=bundle.statement,
        merkle_root=bundle.merkle_root,
        signature_hex=bundle.signature,
        public_key_pem=bundle.public_key_pem,
    )
    assert is_valid is True

    # Tampered statement verification fails
    tampered_stmt = dict(bundle.statement)
    tampered_stmt["subject"] = [{"name": "Hacked", "digest": {"sha256": "0000"}}]
    assert DatasetAttestationSigner.verify_attestation(
        statement=tampered_stmt,
        merkle_root=bundle.merkle_root,
        signature_hex=bundle.signature,
        public_key_pem=bundle.public_key_pem,
    ) is False


def test_dbom_badge_generator():
    """Verify dynamic DBOM SVG badge generation with Merkle and certificate id."""
    cert_id = "DBOM-ABCD1234EF56"
    merkle_root = "abcd1234ef567890abcdef1234567890abcdef12"
    svg = generate_dbom_badge_svg(certificate_id=cert_id, merkle_root=merkle_root, status="verified", verified=True)
    assert "<svg" in svg
    assert "DBOM" in svg
    assert "Verified" in svg


# 2. Test core.evaluator and LLM-as-a-judge
from core.evaluator import (
    evaluate_benchmark_split,
    compute_token_f1,
    AlignmentJudge,
    evaluate_finetuned_model,
    evaluate_sample_rubric,
    check_format_compliance,
)


def test_evaluator_benchmark_split_real_metrics():
    """Verify evaluate_benchmark_split computes exact match, token F1, and chrF accurately."""
    pairs = [
        {"id": "p1", "prediction": "Section 16 permits ITC.", "reference": "Section 16 permits ITC."},
        {"id": "p2", "prediction": "Turnover above 5 crore requires e-invoicing.", "reference": "CBIC mandates e-invoicing for turnover over 5 crore."},
        {"id": "p3", "prediction": "GST rate is 18 percent.", "reference": "Applicable GST rate is 18 percent."},
    ]
    res = evaluate_benchmark_split(pairs, benchmark_name="Test QA", held_out=True)
    assert res["total_samples"] == 3
    assert res["exact_match_pct"] == 33.3  # Only p1 is exact match
    assert res["mean_token_f1"] > 0.50
    assert res["mean_chrf_score"] > 30.0
    assert res["composite_score"] > 40.0
    assert "rating" in res


def test_alignment_judge_objective_evaluation_no_hardcoded_bias():
    """Verify AlignmentJudge evaluates text objectively without simulator bias."""
    prompt = "How does LoRA work?"
    # High quality, direct, structured answer
    chosen = "LoRA freezes pretrained model weights and injects trainable low-rank decomposition matrices."
    # Generic unspecialized response
    generic = "Based on general principles regarding LoRA, applicable technical documentation should be consulted."

    score_chosen, breakdown_chosen = AlignmentJudge.evaluate_response_quality(prompt, chosen)
    score_generic, breakdown_generic = AlignmentJudge.evaluate_response_quality(prompt, generic)

    # Chosen response should score higher due to content keyword coverage and directness
    assert score_chosen > score_generic
    assert breakdown_chosen["safety_and_alignment"] >= 0.90
    assert breakdown_generic["instruction_following"] < breakdown_chosen["instruction_following"]

    # Comparative model evaluation over prompt suite
    prompts = [
        {"prompt": "Explain LoRA.", "aligned_response": chosen, "base_response": generic},
        {"prompt": "Define DPO.", "aligned_response": "Direct Preference Optimization trains on preference pairs without RL reward modeling.", "base_response": "DPO is a machine learning technique."},
    ]
    comp = AlignmentJudge.compare_models("job-judge-eval", prompts)
    assert comp.total_evaluated == 2
    assert comp.aligned_win_count >= 1
    assert comp.win_rate_pct >= 50.0
    assert comp.verdict in ("SIGNIFICANT_IMPROVEMENT", "MODERATE_IMPROVEMENT", "NEGLIGIBLE_DELTA")


def test_evaluate_finetuned_model_real_grounding_and_format():
    """Verify evaluate_finetuned_model computes real format compliance and grounding."""
    samples = [
        {
            "instruction": "What is the limitation period under Section 73?",
            "response": "The limitation period for issuing show cause notice under Section 73 is 3 years from due date of annual return.",
            "base_response": "Notice should be issued within reasonable time.",
            "quality_score": 0.88,
            "base_quality_score": 0.62,
        },
        {
            "instruction": "Explain reverse charge mechanism (RCM).",
            "response": "Under RCM Section 9(3), the recipient of goods or services is liable to pay GST directly to the Government.",
            "base_response": "RCM is when tax is paid differently.",
            "quality_score": 0.90,
            "base_quality_score": 0.65,
        },
    ]
    res = evaluate_finetuned_model("job-eval-789", "sarvam-2b", samples)
    assert res["job_id"] == "job-eval-789"
    assert res["evaluated_samples"] == 2
    assert res["win_rate_pct"] == 100.0
    assert res["finetuned_mean_quality"] == 0.89
    assert res["base_model_mean_quality"] < 0.70
    assert res["quality_delta"] > 0.15
    assert res["format_compliance"] == 1.0  # Both responses are valid compliant sentences
    assert res["grounding_faithfulness"] >= 0.70  # Real computed lexical/reference overlap


# 3. Test api.dbom endpoints
@pytest.mark.asyncio
async def test_api_dbom_endpoints_attest_and_verify():
    """Test api.dbom functions directly."""
    from api.dbom import (
        create_dbom_attestation_endpoint,
        verify_dbom_endpoint,
        sign_attestation_endpoint,
        verify_signature_endpoint,
    )

    samples = [
        {"instruction": "Calculate GST rate under Section 9.", "response": "GST rate is 18% with SGST and CGST equal split."},
        {"instruction": "Define ITC under Section 16.", "response": "Input tax credit allows claiming tax paid on inward supplies."},
    ]

    # 1. Attest endpoint
    attest_payload = {
        "dataset_name": "GST SFT",
        "domain": "taxation",
        "samples": samples,
    }
    attest_res = await create_dbom_attestation_endpoint(payload=attest_payload)
    assert "dbom_certificate" in attest_res
    cert = attest_res["dbom_certificate"]
    assert cert["total_samples"] == 2
    assert cert["merkle_root_hash"] is not None

    # 2. Verify endpoint
    verify_payload = {
        "samples": samples,
        "dbom_certificate": cert,
    }
    verify_res = await verify_dbom_endpoint(payload=verify_payload)
    assert verify_res["is_valid"] is True
    assert verify_res["status"] == "cryptographically_verified"

    # 3. Sign endpoint
    sign_payload = {
        "dataset_name": "GST SFT",
        "merkle_root": cert["merkle_root_hash"],
        "sample_count": 2,
    }
    sign_res = await sign_attestation_endpoint(payload=sign_payload)
    assert "signature" in sign_res
    assert "public_key_pem" in sign_res

    # 4. Verify signature endpoint
    verify_sig_payload = {
        "statement": sign_res["statement"],
        "merkle_root": sign_res["merkle_root"],
        "signature": sign_res["signature"],
        "public_key_pem": sign_res["public_key_pem"],
    }
    verify_sig_res = await verify_signature_endpoint(payload=verify_sig_payload)
    assert verify_sig_res["is_valid"] is True


# 4. Test api.routers.datasets dbom endpoint call pattern
def test_dataset_router_dbom_attestation_signature_alignment():
    """Verify generate_dbom_attestation succeeds with the exact arguments passed by datasets router."""
    from core.export.dbom_attestor import generate_dbom_attestation

    domain = "Taxation"
    samples = [
        {"instruction": "Q1", "response": "A1", "quality_score": 0.85},
        {"instruction": "Q2", "response": "A2", "quality_score": 0.88},
    ]
    sources = [{"name": "Indic Web Repositories", "type": "web", "verified": True}]
    pii_counts = {"aadhaar": 0, "pan": 0, "gstin": 0}
    config = {"language": "en", "license": "PolyForm-Noncommercial-1.0.0"}
    job_id = "test-job-999"

    dbom = generate_dbom_attestation(
        dataset_name=domain,
        samples=samples,
        domain=domain,
        language=config.get("language", "en"),
        license_type=config.get("license", "PolyForm-Noncommercial-1.0.0"),
        compliance_flags={
            "pii_entity_counts": pii_counts,
            "statutory_compliance_act": config.get("statutory_compliance_act"),
            "contamination_rate_pct": config.get("contamination_rate_pct"),
            "diversity_entropy": config.get("diversity_entropy"),
        },
        synthesis_mode=config.get("synthesis_mode", "standard"),
        dataset_id=job_id,
        sources=sources,
    )

    assert dbom["certificate_id"].startswith("DBOM-")
    assert dbom["total_samples"] == 2
    assert dbom["dataset_id"] == job_id
    assert dbom["provenance"]["sources"] == sources
