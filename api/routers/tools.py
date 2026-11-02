"""Developer tools, evaluation utilities, and benchmark endpoints for RasoSynthTune."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from api.auth import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tools"])


def _tool_float(value: Any, field: str, default: float) -> float:
    """Parse a float tool field; a bad cast is a 400, never a 500."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Field '{field}' must be a number")


def _tool_int(value: Any, field: str, default: int) -> int:
    """Parse an int tool field; a bad cast is a 400, never a 500."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Field '{field}' must be an integer")


def _tool_list(value: Any, field: str) -> list:
    """Require a list tool field (a string is not a list of records)."""
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail=f"Field '{field}' must be a list")
    return value


def _tool_dict(value: Any, field: str) -> dict:
    """Require a dict tool field."""
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail=f"Field '{field}' must be an object")
    return value


@router.post("/tools/mask-pii")
async def tool_mask_pii(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Detect and mask Indian statutory identifiers (Aadhaar, PAN, GSTIN, UPI, Mobile)."""
    from core.validation.indian_pii import detect_indian_pii, mask_indian_pii

    text = str(request.get("text", ""))
    mode = str(request.get("mode", "redact"))
    detected = detect_indian_pii(text)
    masked_text = mask_indian_pii(text, replacement_mode=mode)
    return {
        "masked": masked_text,
        "detected_types": {k: len(v) for k, v in detected.items()},
        "pii_count": sum(len(v) for v in detected.values()),
    }


@router.post("/tools/speech-normalize")
async def tool_speech_normalize(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Verbalize numbers, abbreviations, and currencies for Voice AI pipelines."""
    from core.normalization.indian_numerical import verbalize_for_speech

    text = str(request.get("text", ""))
    lang = str(request.get("language", "hi"))
    return {
        "original": text,
        "verbalized": verbalize_for_speech(text, language=lang),
    }


@router.post("/tools/evaluate-fidelity")
async def tool_evaluate_fidelity(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Calculate cross-lingual semantic fidelity and chrF++ score."""
    from core.metrics.fidelity import evaluate_fidelity

    hyp = str(request.get("hypothesis", ""))
    ref = str(request.get("reference", ""))
    return evaluate_fidelity(original_text=ref, back_translated_text=hyp)


@router.post("/tools/evaluate-rubric")
async def tool_evaluate_rubric(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Evaluate synthetic sample against 5-dimensional LLM-as-a-Judge quality rubric."""
    from core.evaluation.heuristic_rubric import evaluate_sample_rubric

    inst = str(request.get("instruction", ""))
    resp = str(request.get("response", ""))
    ref = request.get("reference_context")
    lang = str(request.get("language", "en"))
    reg = str(request.get("formality_register", "formal"))
    return evaluate_sample_rubric(
        instruction=inst,
        response=resp,
        reference_context=ref,
        language=lang,
        formality_register=reg,
    )


@router.post("/tools/generate-adversarial-probes")
async def tool_generate_adversarial_probes(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Generate domain-specific adversarial stress test probes."""
    from core.safety.adversarial_generator import generate_adversarial_probes

    domain = str(request.get("domain", "taxation"))
    categories = request.get("categories")
    language = str(request.get("language", "hinglish"))
    sample_count = _tool_int(request.get("sample_count", 5), "sample_count", 5)

    probes = generate_adversarial_probes(
        domain=domain,
        categories=categories,
        language=language,
        sample_count=sample_count,
    )
    return {
        "domain": domain,
        "probe_count": len(probes),
        "probes": probes,
    }


@router.post("/tools/audit-contamination")
async def tool_audit_contamination(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Audit dataset samples against standard Indic & global LLM evaluation benchmarks."""
    from core.evaluation.contamination_checker import check_dataset_contamination

    samples = _tool_list(request.get("samples") or [], "samples")
    benchmarks = request.get("benchmarks")
    threshold = _tool_float(request.get("similarity_threshold", 0.50), "similarity_threshold", 0.50)

    if not samples:
        raise HTTPException(status_code=400, detail="Field 'samples' must be a non-empty list of records.")

    report = check_dataset_contamination(
        samples=samples,
        benchmarks=benchmarks,
        similarity_threshold=threshold,
    )
    return report


@router.post("/tools/evaluate-rag")
async def tool_evaluate_rag(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Evaluate grounding faithfulness, attribution, and citation coverage of a RAG response."""
    from core.generation.rag_synthesizer import evaluate_rag_faithfulness

    response = str(request.get("response", ""))
    positive_contexts = request.get("positive_contexts") or []
    if not isinstance(positive_contexts, list):
        positive_contexts = [str(positive_contexts)]
    return evaluate_rag_faithfulness(
        response=response,
        positive_contexts=[str(c) for c in positive_contexts],
    )


@router.post("/tools/semantic-density")
async def tool_semantic_density(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Analyze dataset semantic density, 2D topic clusters, entropy, and outliers."""
    from core.curation.diversity_mapper import analyze_semantic_diversity

    samples = _tool_list(request.get("samples") or [], "samples")
    k_clusters = _tool_int(request.get("k_clusters", 4), "k_clusters", 4)
    if not samples:
        raise HTTPException(status_code=400, detail="Field 'samples' must be a non-empty list of records.")
    return analyze_semantic_diversity(samples=samples, k_clusters=k_clusters)


@router.post("/tools/evaluate-dialogue")
async def tool_evaluate_dialogue(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Evaluate structural integrity, alternation, and turn balance of a dialogue."""
    from core.generation.multi_turn_synthesizer import evaluate_dialogue_coherence

    turns = request.get("turns") or []
    if not isinstance(turns, list):
        raise HTTPException(status_code=400, detail="Field 'turns' must be a list of turn objects.")
    return evaluate_dialogue_coherence(turns=turns)


@router.post("/tools/best-of-n")
async def tool_best_of_n(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Perform Best-of-N rejection sampling and consensus filtering."""
    from core.curation.best_of_n import filter_best_of_n

    instruction = str(request.get("instruction", ""))
    candidates = _tool_list(request.get("candidates") or [], "candidates")
    ref_ans = request.get("reference_answer")
    domain = request.get("domain")
    if not candidates:
        raise HTTPException(status_code=400, detail="Field 'candidates' must be a non-empty list of candidate strings.")
    return filter_best_of_n(
        instruction=instruction,
        candidates=[str(c) for c in candidates],
        reference_answer=str(ref_ans) if ref_ans else None,
        domain=str(domain) if domain else None,
    )


@router.post("/tools/audit-representation")
async def tool_audit_representation(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Audit geographic distribution, urbanicity balance, and demographic parity."""
    from core.curation.representation_balancer import audit_dataset_representation

    samples = _tool_list(request.get("samples") or [], "samples")
    if not samples:
        raise HTTPException(status_code=400, detail="Field 'samples' must be a non-empty list of records.")
    return audit_dataset_representation(samples=samples)


@router.post("/tools/verify-dbom")
async def tool_verify_dbom(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Cryptographically verify dataset against its DBOM certificate."""
    from core.export.dbom_attestor import verify_dataset_dbom

    samples = _tool_list(request.get("samples") or [], "samples")
    certificate = _tool_dict(request.get("dbom_certificate") or {}, "dbom_certificate")
    if not samples or not certificate:
        raise HTTPException(status_code=400, detail="Fields 'samples' and 'dbom_certificate' are required.")
    return verify_dataset_dbom(samples=samples, dbom_certificate=certificate)


@router.post("/tools/generate-contrastive-pair")
async def tool_generate_contrastive_pair(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Synthesize contrastive factual perturbation and critique pair."""
    from core.generation.contrastive_generator import synthesize_contrastive_pair

    inst = str(request.get("instruction", ""))
    resp = str(request.get("grounded_response", ""))
    domain = request.get("domain")
    if not inst or not resp:
        raise HTTPException(status_code=400, detail="Fields 'instruction' and 'grounded_response' are required.")
    return synthesize_contrastive_pair(
        instruction=inst,
        grounded_response=resp,
        domain=str(domain) if domain else None,
    )


@router.post("/tools/rebalance-dataset")
async def tool_rebalance_dataset(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Formulate targeted prompt mutations and quotas to bridge representation deficits."""
    from core.curation.active_balancer import plan_active_rebalancing

    audit_report = _tool_dict(request.get("audit_report") or {}, "audit_report")
    target_pool = _tool_int(request.get("target_sample_pool", 100), "target_sample_pool", 100)
    domain = request.get("domain")
    if not audit_report:
        raise HTTPException(status_code=400, detail="Field 'audit_report' is required.")
    return plan_active_rebalancing(
        audit_report=audit_report,
        target_sample_pool=target_pool,
        domain=str(domain) if domain else None,
    )


@router.post("/tools/generate-dialectic")
async def tool_generate_dialectic(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Synthesize structured multi-agent dialectic debate sample."""
    from core.generation.socratic_synthesizer import evaluate_dialectic_coherence, format_dialectic_sample

    topic = str(request.get("topic", ""))
    debate_rounds = _tool_list(request.get("debate_rounds") or [], "debate_rounds")
    verdict = str(request.get("verdict", ""))
    domain = request.get("domain")
    personas = request.get("personas")
    if not topic or not debate_rounds or not verdict:
        raise HTTPException(status_code=400, detail="Fields 'topic', 'debate_rounds', and 'verdict' are required.")

    coherence = evaluate_dialectic_coherence(debate_rounds, verdict)
    sample = format_dialectic_sample(
        topic=topic,
        debate_rounds=debate_rounds,
        verdict=verdict,
        domain=str(domain) if domain else None,
        personas=personas,
    )
    return {
        "sample": sample,
        "coherence": coherence,
    }


@router.post("/tools/calibrate-judge")
async def tool_calibrate_judge(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Calibrate LLM Judge alignment against human reviewer decisions and compute Cohen's Kappa."""
    from core.evaluation.judge_calibrator import calibrate_judge_alignment

    evaluations = _tool_list(request.get("evaluations") or [], "evaluations")
    threshold = _tool_float(request.get("default_threshold", 0.70), "default_threshold", 0.70)
    if not evaluations:
        raise HTTPException(
            status_code=400,
            detail="Field 'evaluations' must be a non-empty list of {human_decision, judge_score}.",
        )
    return calibrate_judge_alignment(evaluations=evaluations, default_threshold=threshold)


@router.post("/tools/evaluate-benchmark")
async def tool_evaluate_benchmark(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Directly evaluate model outputs against a synthetic test benchmark."""
    from core.evaluation.benchmark_evaluator import evaluate_benchmark_split

    pairs = _tool_list(request.get("evaluation_pairs") or [], "evaluation_pairs")
    name = str(request.get("benchmark_name", "Synthetic Indic QA"))
    target = str(request.get("target_model", "Candidate LLM"))
    if not pairs:
        raise HTTPException(
            status_code=400,
            detail="Field 'evaluation_pairs' must be a non-empty list of {prediction, reference}.",
        )
    return evaluate_benchmark_split(
        evaluation_pairs=pairs,
        benchmark_name=name,
        target_model=target,
    )


@router.post("/tools/shard-dataset")
async def tool_shard_dataset(
    request: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Partition dataset samples into standard Hugging Face/PyTorch sharded chunks."""
    from core.export.streaming_sharder import shard_dataset_records

    samples = _tool_list(request.get("samples") or [], "samples")
    shard_size = _tool_int(request.get("shard_size", 1000), "shard_size", 1000)
    prefix = str(request.get("prefix", "train"))
    compress = bool(request.get("compress", False))
    if not samples:
        raise HTTPException(status_code=400, detail="Field 'samples' must be a non-empty list of records.")
    return shard_dataset_records(
        samples=samples,
        shard_size=shard_size,
        prefix=prefix,
        compress=compress,
    )


@router.get("/benchmarks/quality", tags=["Research"])
async def get_quality_benchmarks(current_user: User = Depends(get_current_user)):
    """Run comprehensive quality, throughput latency, and unit economic benchmarks."""
    from research.quality_benchmark import QualityBenchmark

    benchmark = QualityBenchmark()
    results = await benchmark.run_all()
    markdown_report = benchmark.generate_report(results)
    return {
        "benchmark_data": results,
        "markdown_report": markdown_report,
    }


@router.get("/benchmarks/evaluation", tags=["Research"])
async def get_finetune_evaluation_benchmark(current_user: User = Depends(get_current_user)):
    """Return illustrative before vs. after fine-tuning benchmark demonstration deltas."""
    data = None
    eval_file = Path("outputs/evaluation/before_vs_after_finetune_benchmark.json")
    if eval_file.exists():
        try:
            with open(eval_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    if data is None:
        from scripts.demo_finetune_eval import run_finetune_eval_benchmark

        data = run_finetune_eval_benchmark()

    if isinstance(data, dict):
        data["evaluation_type"] = "demo"
    return data
