"""Tests for post-training base-vs-fine-tuned evaluation and model card binding."""

import json
from pathlib import Path
import pytest

from core.evaluation.inference_harness import (
    append_eval_to_model_card,
    check_format_compliance,
    compute_directory_hash,
    compute_pseudo_perplexity,
    evaluate_base_vs_finetuned,
)
from core.export.huggingface_exporter import generate_hf_model_card


def _sample_held_out_pairs():
    return [
        {
            "id": f"eval-{i+1}",
            "instruction": f"What is the statutory limitation period for filing notice under Section {i+1}?",
            "response": f"Under Section {i+1} of the CGST Act 2017, the proper officer must issue notice within {i+3} years [1].",
            "metadata": {"topic": "Taxation" if i % 2 == 0 else "Corporate Law"},
        }
        for i in range(12)
    ]


def test_format_compliance_checker():
    """Verify format compliance detection."""
    assert check_format_compliance("A valid, compliant statutory response.") is True
    assert check_format_compliance("") is False
    assert check_format_compliance("abc") is False  # too short
    assert check_format_compliance("<|im_start|>user\nFailed template leak") is False
    assert check_format_compliance("### Instruction:\nPrompt leaking into generation") is False


def test_pseudo_perplexity_sanity():
    """Verify held-out perplexity sanity check."""
    texts = ["Statutory provision under section 16 of the Act."] * 5
    ppl = compute_pseudo_perplexity(texts)
    assert ppl >= 1.10
    assert ppl <= 100.0


def test_base_vs_finetuned_evaluation_headline_and_measures(tmp_path: Path):
    """Verify base vs fine-tuned comparative evaluation measures."""
    samples = _sample_held_out_pairs()
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text('{"r": 16}', encoding="utf-8")

    report = evaluate_base_vs_finetuned(
        base_model_id="sarvamai/sarvam-2b-v0.5",
        adapter_path=str(adapter_dir),
        held_out_samples=samples,
        job_id="job-eval-run-1",
        regression_policy="warn",
    )

    assert report["job_id"] == "job-eval-run-1"
    assert report["total_samples"] == 12
    assert "win_rate_pct" in report
    assert report["win_rate_pct"] >= 50.0
    assert report["headline_composite_delta"] >= 0.0
    assert report["format_compliance_pct"] == 100.0
    assert "per_segment_breakdown" in report
    assert "Taxation" in report["per_segment_breakdown"]
    assert "held_out_perplexity_sanity" in report
    assert len(report["side_by_side_samples"]) >= 5
    assert len(report["side_by_side_samples"]) <= 10
    assert "validation_disclaimer" in report
    assert "process check only" in report["validation_disclaimer"].lower()
    assert "hashes" in report
    assert "model_hash" in report["hashes"]
    assert "dataset_hash" in report["hashes"]
    assert "eval_hash" in report["hashes"]


def test_regression_policy_block_vs_warn(tmp_path: Path):
    """Ensure regression policy blocks completion when configured as 'block', and warns loudly when 'warn'."""
    samples = _sample_held_out_pairs()
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text('{"r": 16}', encoding="utf-8")

    # Custom generator simulating a regressing model (tuned model gives worse outputs than base)
    def regressing_generator(model_target: str, is_tuned: bool, sample: dict) -> str:
        if is_tuned:
            return "garbled bad output lacking all keywords"
        return str(sample.get("response", ""))

    # 1. Under policy='block': regression blocks job completion
    report_block = evaluate_base_vs_finetuned(
        base_model_id="sarvamai/sarvam-2b-v0.5",
        adapter_path=str(adapter_dir),
        held_out_samples=samples,
        job_id="job-regress-block",
        regression_policy="block",
        custom_generator=regressing_generator,
    )
    assert report_block["is_regression"] is True
    assert report_block["regression_policy"] == "block"
    assert report_block["blocks_completion"] is True
    assert report_block["headline_composite_delta"] < 0.0

    # 2. Under policy='warn': regression warns loudly but blocks_completion is False
    report_warn = evaluate_base_vs_finetuned(
        base_model_id="sarvamai/sarvam-2b-v0.5",
        adapter_path=str(adapter_dir),
        held_out_samples=samples,
        job_id="job-regress-warn",
        regression_policy="warn",
        custom_generator=regressing_generator,
    )
    assert report_warn["is_regression"] is True
    assert report_warn["regression_policy"] == "warn"
    assert report_warn["blocks_completion"] is False
    assert report_warn["headline_composite_delta"] < 0.0


def test_model_card_json_binding_and_sections(tmp_path: Path):
    """Verify model card README includes holdout decision table, side-by-side table, and bound JSON."""
    samples = _sample_held_out_pairs()
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir(exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text('{"r": 16}', encoding="utf-8")

    report = evaluate_base_vs_finetuned(
        base_model_id="sarvamai/sarvam-2b-v0.5",
        adapter_path=str(adapter_dir),
        held_out_samples=samples,
        job_id="job-card-binding",
        regression_policy="warn",
    )

    holdout_decision = {
        "floor": 1000,
        "total_samples": 1200,
        "train_count": 960,
        "val_count": 120,
        "test_count": 120,
        "status": "held_out_carved",
        "flag": None,
    }

    base_card = generate_hf_model_card(
        model_name="sarvam-2b-tax-lora",
        base_model="sarvamai/sarvam-2b-v0.5",
        dataset_name="indic-gst-corpus",
        sample_count=1200,
        holdout_decision=holdout_decision,
        eval_report=report,
    )

    # 1. Check holdout decision table
    assert "Dataset Split & Floor Decision" in base_card
    assert "| **Evaluation Platform Floor** | `1000` samples |" in base_card
    assert "| **Training Split (Carved)** | `960` samples |" in base_card
    assert "| **Validation Split (Job Artifact)** | `120` samples |" in base_card

    # 2. Check headline metrics
    assert "Headline Comparative Metrics" in base_card
    assert "Win Rate vs Base" in base_card
    assert "Composite Score Delta" in base_card

    # 3. Check side-by-side generations
    assert "Side-by-Side Qualitative Generations (Held-out Prompts)" in base_card
    assert "| eval-1 |" in base_card

    # 4. Check validation process disclaimer
    assert "Synthetic holdout evaluation is a process check only" in base_card
    assert "Real-world validation on domain practitioner queries is the required next stage" in base_card
    assert "Existing legacy models cannot be retroactively evaluated" in base_card

    # 5. Check cryptographic hash binding block
    assert "Cryptographic Evaluation Provenance Binding" in base_card
    assert f'"job_id": "{report["job_id"]}"' in base_card
    assert f'"model_hash": "{report["hashes"]["model_hash"]}"' in base_card
    assert f'"eval_hash": "{report["hashes"]["eval_hash"]}"' in base_card


def test_model_card_small_job_flag():
    """Verify model card marks below-floor small jobs without internal eval."""
    holdout_decision = {
        "floor": 1000,
        "total_samples": 450,
        "train_count": 450,
        "val_count": 0,
        "test_count": 0,
        "status": "below_floor_100_pct_train",
        "flag": "no internal eval, upload real validation examples",
    }

    card = generate_hf_model_card(
        model_name="sarvam-2b-small-lora",
        base_model="sarvamai/sarvam-2b-v0.5",
        dataset_name="small-sample-corpus",
        sample_count=450,
        holdout_decision=holdout_decision,
    )

    assert "Holdout Flag" in card
    assert "no internal eval, upload real validation examples" in card
    assert "below the platform floor (1000)" in card
    assert "| **Training Split (Carved)** | `450` samples |" in card


@pytest.mark.asyncio
async def test_job_manager_post_training_eval_integration(tmp_path: Path):
    """Verify job manager runs post-training evaluation and writes model card and eval JSON."""
    from unittest.mock import AsyncMock
    from finetuning.job_manager import FinetuneJobManager
    from finetuning.trainer import FineTuneConfig

    mock_db = AsyncMock()
    manager = FinetuneJobManager(mock_db)

    out_dir = tmp_path / "model_job"
    out_dir.mkdir()
    (out_dir / "val.jsonl").write_text(
        json.dumps({"id": "v1", "instruction": "Test statutory Q", "response": "Test statutory A"}) + "\n",
        encoding="utf-8",
    )

    config = FineTuneConfig(
        base_model="sarvamai/sarvam-2b-v0.5",
        output_dir=str(out_dir),
        dataset_path=str(out_dir / "val.jsonl"),
    )

    should_cont, err, report = await manager._run_post_training_eval(
        job_id="test-job-eval-int",
        config=config,
        event={"output_path": str(out_dir)},
    )
    assert should_cont is True
    assert err is None
    assert report is not None
    assert (out_dir / "eval_report.json").exists()
    assert (out_dir / "README.md").exists()
    readme_content = (out_dir / "README.md").read_text(encoding="utf-8")
    assert "Post-Training Empirical Benchmark Evaluation" in readme_content
