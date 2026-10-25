"""Tests for DBOM attestation synthesis_mode, WorkflowPlanner, and non-heuristic quality filtering."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.export.dbom_attestor import generate_dbom_attestation, verify_dataset_dbom, generate_nutrition_label_markdown
from api.planning.planner import WorkflowPlanner
from api.schemas.dataset import DatasetConfig
from pipeline.filtering import FilteringPipeline
from pipeline.quality_scorer import QualityScorer


def test_dbom_attestation_with_synthesis_mode():
    samples = [
        {"instruction": "Calculate GST rate under Section 9.", "response": "GST rate is 18% with SGST and CGST equal split."},
        {"instruction": "Define ITC under Section 16.", "response": "Input tax credit allows claiming tax paid on inward supplies."},
    ]
    cert = generate_dbom_attestation(
        dataset_name="GST Compliance SFT",
        samples=samples,
        domain="taxation",
        language="en",
        synthesis_mode="cot",
    )
    assert cert["synthesis_mode"] == "cot"
    assert cert["provenance"]["synthesis_mode"] == "cot"
    assert cert["certificate_id"].startswith("DBOM-")
    assert cert["total_samples"] == 2

    label_md = generate_nutrition_label_markdown(cert)
    assert "Synthesis Mode" in label_md
    assert "`cot`" in label_md

    # Verification passes
    verification = verify_dataset_dbom(samples, cert)
    assert verification["is_valid"] is True


@pytest.mark.asyncio
async def test_workflow_planner_creates_plan():
    cfg = DatasetConfig(
        name="Corporate Law Dataset",
        domain="corporate_law",
        target_size=500,
        synthesis_mode="socratic",
        language="en",
    )
    planner = WorkflowPlanner()
    plan = await planner.create_plan(cfg)
    assert plan is not None
    assert plan.plan_id.startswith("plan_")
    assert len(plan.steps) > 0
    assert plan.total_estimated_cost_usd >= 0.0
    assert plan.total_estimated_duration_seconds >= 0


@pytest.mark.asyncio
async def test_filtering_pipeline_indic_script_not_penalized():
    """Verify that valid Indic text is not penalized by removed naive low_ascii_ratio heuristic."""
    pipeline = FilteringPipeline(router=None, config={})
    # Real Hindi / Indic Devanagari text
    indic_sample = "वस्तु एवं सेवा कर (जीएसटी) एक अप्रत्यक्ष कर है जिसे भारत में वस्तुओं और सेवाओं की आपूर्ति पर लगाया जाता है।"
    
    score, issues = pipeline._signal_quality(indic_sample)
    # The old naive heuristic flagged 'low_ascii_ratio' and subtracted 0.2
    assert "low_ascii_ratio" not in issues
    assert "corrupted_binary_or_control_characters" not in issues
    assert score >= 0.7


@pytest.mark.asyncio
async def test_quality_scorer_with_mock_embedding_router():
    """Verify QualityScorer computes cosine similarity using neural router embeddings rather than heuristics."""
    mock_router = MagicMock()
    # Mock embedding return: 128-dim vector
    vec_inst = [0.1] * 128
    vec_resp = [0.1] * 128  # Identical direction -> cosine similarity ~ 1.0

    mock_inst_resp = MagicMock(embedding=vec_inst)
    mock_resp_resp = MagicMock(embedding=vec_resp)

    mock_router.embed = AsyncMock(side_effect=[mock_inst_resp, mock_resp_resp])
    scorer = QualityScorer(router=mock_router)

    score = await scorer.score(
        instruction="Explain quantum entanglement.",
        response="Quantum entanglement is a phenomenon where entangled particles remain connected.",
        domain="physics"
    )

    assert score.details["semantic"]["method"] == "embedding_similarity"
    assert "cosine_similarity" in score.details["semantic"]
    assert score.details["semantic"]["cosine_similarity"] > 0.9


def test_ray_cluster_status_and_workers():
    """Verify Ray status reporting function and worker initialization."""
    from workers.ray_pipeline import get_ray_status
    status = get_ray_status()
    assert isinstance(status, dict)
    assert "available" in status
    assert "nodes" in status
    assert "available_cpus" in status


@pytest.mark.asyncio
async def test_plan_job_endpoint_returns_coverage_matrix():
    """Verify plan_job endpoint generates both the workflow plan and topic coverage matrix."""
    from api.server import plan_job, JobRequest

    req = JobRequest(
        target_domain="taxation",
        dataset_size=20,
        synthesis_mode="cot",
        language="en",
    )
    result = await plan_job(req)
    assert "plan_id" in result
    assert "steps" in result
    assert len(result["steps"]) > 0
    assert "coverage_matrix" in result
    cov = result["coverage_matrix"]
    assert "cells" in cov
    assert len(cov["cells"]) > 0

