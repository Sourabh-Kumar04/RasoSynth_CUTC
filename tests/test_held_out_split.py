"""Tests for export-time held-out stratified dataset splitting."""

import json
from pathlib import Path
import pytest

from core.evaluation.held_out_split import (
    EVAL_PLATFORM_FLOOR,
    NO_INTERNAL_EVAL_FLAG,
    create_stratified_held_out_split,
    derive_split_seed,
    save_split_artifacts,
)


def _generate_synthetic_corpus(n: int, num_sources: int = 50) -> list[dict]:
    """Generate n synthetic instruction samples with controlled sources and strata."""
    topics = ["taxation", "corporate_law", "compliance", "arbitration"]
    languages = ["en", "hi", "hinglish"]
    difficulties = [1, 2, 3, 4, 5]

    samples = []
    for i in range(n):
        src_id = f"source-doc-{(i % num_sources) + 1}"
        topic = topics[i % len(topics)]
        lang = languages[i % len(languages)]
        diff = difficulties[i % len(difficulties)]

        samples.append({
            "id": f"sample-{i+1}",
            "instruction": f"Statutory query regarding {topic} case {i+1} in {lang}?",
            "response": f"According to statutory section {i % 100}, the requirement is met for {topic}.",
            "input": "",
            "difficulty_tier": diff,
            "metadata": {
                "source_url": f"https://cbic.gov.in/notices/{src_id}.pdf",
                "source_id": src_id,
                "topic": topic,
                "language": lang,
                "difficulty_tier": diff,
            },
        })
    return samples


def test_small_job_below_floor_trains_on_100_percent():
    """Below 1000 floor, train on 100% of samples and flag 'no internal eval, upload real validation examples'."""
    samples = _generate_synthetic_corpus(500, num_sources=30)
    job_id = "job-small-500"

    result = create_stratified_held_out_split(samples, job_id, floor=1000)
    dec = result["decision"]

    assert dec["total_samples"] == 500
    assert dec["floor"] == 1000
    assert dec["train_count"] == 500
    assert dec["val_count"] == 0
    assert dec["test_count"] == 0
    assert dec["status"] == "below_floor_100_pct_train"
    assert dec["flag"] == NO_INTERNAL_EVAL_FLAG
    assert len(result["train"]) == 500
    assert len(result["val"]) == 0
    assert len(result["test"]) == 0
    assert "below the evaluation floor" in dec["warning"]


def test_at_or_above_floor_carves_held_out_splits():
    """At or above 1000 floor, carve stratified held-out validation and test splits."""
    samples = _generate_synthetic_corpus(1200, num_sources=80)
    job_id = "job-large-1200"

    result = create_stratified_held_out_split(samples, job_id, floor=1000)
    dec = result["decision"]

    assert dec["total_samples"] == 1200
    assert dec["floor"] == 1000
    assert dec["status"] == "held_out_carved"
    assert dec["flag"] is None
    assert dec["val_count"] > 0
    assert dec["test_count"] > 0
    assert dec["train_count"] > 0
    assert dec["train_count"] + dec["val_count"] + dec["test_count"] == 1200

    # Ensure held-out samples have review & split annotations
    for s in result["val"]:
        assert s["_split"] == "validation"
        assert s["_held_out"] is True
        assert s["_reviewed"] is True

    for s in result["test"]:
        assert s["_split"] == "test"
        assert s["_held_out"] is True
        assert s["_reviewed"] is True


def test_seed_reproducibility():
    """Identical job_id and seed produce identical train/val/test splits."""
    samples = _generate_synthetic_corpus(1050, num_sources=70)

    res1 = create_stratified_held_out_split(samples, job_id="job-seed-test", seed=42)
    res2 = create_stratified_held_out_split(samples, job_id="job-seed-test", seed=42)

    assert res1["decision"]["train_hash"] == res2["decision"]["train_hash"]
    assert res1["decision"]["val_hash"] == res2["decision"]["val_hash"]
    assert res1["decision"]["test_hash"] == res2["decision"]["test_hash"]

    # Different seeds produce different allocations
    res3 = create_stratified_held_out_split(samples, job_id="job-seed-test-other", seed=999)
    assert res1["decision"]["seed"] != res3["decision"]["seed"]


def test_no_leakage_of_held_out_samples_into_training():
    """No source documents or samples must cross the train/val/test boundary."""
    samples = _generate_synthetic_corpus(1100, num_sources=60)
    job_id = "job-leakage-audit"

    result = create_stratified_held_out_split(samples, job_id, floor=1000)

    train_ids = {s["id"] for s in result["train"]}
    val_ids = {s["id"] for s in result["val"]}
    test_ids = {s["id"] for s in result["test"]}

    # 1. Strictly disjoint sample IDs
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)

    # 2. Strictly disjoint source URLs (no source contamination)
    train_sources = {s["metadata"]["source_url"] for s in result["train"]}
    val_sources = {s["metadata"]["source_url"] for s in result["val"]}
    test_sources = {s["metadata"]["source_url"] for s in result["test"]}

    assert train_sources.isdisjoint(val_sources), "Leakage detected: train and val share source URLs!"
    assert train_sources.isdisjoint(test_sources), "Leakage detected: train and test share source URLs!"
    assert val_sources.isdisjoint(test_sources), "Leakage detected: val and test share source URLs!"


def test_save_split_artifacts(tmp_path: Path):
    """Artifact saver persists primary train file and val/test job artifacts."""
    samples = _generate_synthetic_corpus(1020, num_sources=60)
    job_id = "job-artifact-test"

    split_res = create_stratified_held_out_split(samples, job_id, floor=1000)
    artifacts = save_split_artifacts(split_res, tmp_path, base_filename="dataset.jsonl")

    assert artifacts["train"].exists()
    assert artifacts["train"].name == "dataset.jsonl"
    assert artifacts["val"].exists()
    assert artifacts["val"].name == "val.jsonl"
    assert artifacts["test"].exists()
    assert artifacts["test"].name == "test.jsonl"
    assert artifacts["manifest"].exists()
    assert artifacts["manifest"].name == "split_manifest.json"

    with open(artifacts["manifest"], "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    assert manifest_data["status"] == "held_out_carved"
    assert manifest_data["train_count"] == len(split_res["train"])
