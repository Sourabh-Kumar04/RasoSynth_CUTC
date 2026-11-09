"""
Unit tests for Fine-Tuning VRAM Estimation, Hyperparameter Auto-Tuning, and Benchmark Evaluation.
"""

import pytest
from finetuning.trainer import (
    FineTuneConfig,
    estimate_vram_requirement,
    recommend_hyperparameters,
    evaluate_finetuned_model,
)


def test_finetune_config_training_method():
    cfg = FineTuneConfig(
        dataset_path="data/test.jsonl",
        training_method="dpo",
    )
    assert cfg.training_method == "dpo"
    cfg.validate()


def test_vram_estimator_7b_and_sarvam_2b():
    # 7B model in 4-bit vs 16-bit
    est_4bit = estimate_vram_requirement("meta-llama/Llama-3-8B-Instruct", load_in_4bit=True)
    assert est_4bit["estimated_parameters_billion"] == 8.0
    assert est_4bit["supported_on_16gb_gpu"] is True
    assert est_4bit["total_estimated_vram_gb"] < 15.0

    est_16bit = estimate_vram_requirement("meta-llama/Llama-3-8B-Instruct", load_in_4bit=False, load_in_8bit=False)
    assert est_16bit["total_estimated_vram_gb"] > est_4bit["total_estimated_vram_gb"]
    assert est_16bit["supported_on_16gb_gpu"] is False

    # Sarvam-2B model
    est_sarvam = estimate_vram_requirement("sarvamai/sarvam-2b-v0.5", load_in_4bit=True)
    assert est_sarvam["estimated_parameters_billion"] == 2.0
    assert est_sarvam["total_estimated_vram_gb"] < 6.0


def test_hyperparameter_recommendations():
    rec_16gb = recommend_hyperparameters("meta-llama/Llama-3-8B-Instruct", target_gpu_vram_gb=16.0)
    assert rec_16gb["load_in_4bit"] is True
    assert rec_16gb["per_device_train_batch_size"] <= 4

    rec_40gb = recommend_hyperparameters("meta-llama/Llama-3-8B-Instruct", target_gpu_vram_gb=40.0)
    assert rec_40gb["load_in_4bit"] is False
    assert rec_40gb["per_device_train_batch_size"] >= 4


def test_post_training_evaluation_benchmark():
    samples = [
        {"instruction": f"Q{i}", "quality_score": 0.70 + (i % 10) * 0.02}
        for i in range(20)
    ]
    benchmark = evaluate_finetuned_model(
        job_id="job-eval-001",
        base_model="sarvamai/sarvam-2b-v0.5",
        test_samples=samples,
    )
    assert benchmark["job_id"] == "job-eval-001"
    assert benchmark["evaluated_samples"] == 20
    assert benchmark["win_rate_pct"] >= 75.0
    assert benchmark["finetuned_mean_quality"] > benchmark["base_model_mean_quality"]
    assert benchmark["verdict"] == "significant_improvement"
