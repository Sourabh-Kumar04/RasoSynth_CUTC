"""
Comprehensive regression test suite for all RasoSynthTune CLI subcommands.
"""

import json
import sys
import tempfile
from pathlib import Path
import pytest

from cli import main, build_parser
from agents.refinement_loop import SelfRefinementLoop
from core.safety.indian_pii import IndianPIIRedactor, validate_verhoeff
from core.export.attestation import DatasetAttestationSigner
from pipeline.curriculum_sampler import CurriculumSampler
from core.evaluation.arena import ComparativeEloArena


def test_cli_parser_all_subcommands():
    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions
        if action.dest == "command"
    )
    expected = {
        "generate", "audit", "benchmark", "recipe", "serve",
        "publish", "quantize", "judge", "pipeline", "scrape", "preference"
    }
    assert expected.issubset(set(subparsers_action.choices.keys()))


def test_self_refinement_loop():
    loop = SelfRefinementLoop(target_score=0.8, max_iterations=2)
    prompt = "Explain Section 16(4) of the CGST Act 2017."
    context = "Section 16(4) specifies the statutory time limit for claiming input tax credit."
    initial_draft = "ITC must be claimed on time."

    res = loop.refine(prompt=prompt, initial_draft=initial_draft, context=context)
    assert res.iterations_used >= 1
    assert res.final_score >= res.initial_score
    assert len(res.history) >= 1
    assert "statutory" in res.final_output.lower() or "compliance" in res.final_output.lower()


def test_indian_pii_redactor():
    redactor = IndianPIIRedactor()

    # Valid Aadhaar with Verhoeff checksum: 234567890124
    assert validate_verhoeff("234567890124") is True
    assert validate_verhoeff("234567890125") is False  # Single digit tampering fails check
    test_text = (
        "Taxpayer details: PAN: ABCDE1234F, GSTIN: 27ABCDE1234F1Z5, "
        "Contact: +91 9876543210, Bank IFSC: SBIN0001234."
    )
    result = redactor.redact(test_text)
    assert result.has_pii is True
    assert "[PAN_REDACTED]" in result.clean_text
    assert "[GSTIN_REDACTED]" in result.clean_text
    assert "[PHONE_REDACTED]" in result.clean_text
    assert "[IFSC_REDACTED]" in result.clean_text
    assert "ABCDE1234F" not in result.clean_text


def test_dataset_attestation_signer():
    signer = DatasetAttestationSigner()
    merkle_root = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    bundle = signer.sign_attestation(
        dataset_name="indic-gst-corpus-v1",
        merkle_root=merkle_root,
        sample_count=1000,
    )

    assert bundle.merkle_root == merkle_root
    assert bundle.signature != ""
    assert "BEGIN PUBLIC KEY" in bundle.public_key_pem

    is_valid = signer.verify_attestation(
        statement=bundle.statement,
        merkle_root=bundle.merkle_root,
        signature_hex=bundle.signature,
        public_key_pem=bundle.public_key_pem,
    )
    assert is_valid is True


def test_curriculum_sampler():
    sampler = CurriculumSampler()
    samples = [
        {
            "instruction": "What is the penalty for late GSTR-3B filing?",
            "response": "Under Section 47 of the CGST Act, late fees of ₹50 per day (₹20 for nil returns) apply subject to statutory maximum caps.",
        },
        {
            "instruction": "bad bad bad",
            "response": "bad bad bad bad bad bad bad bad bad bad bad bad bad bad bad",
        },
    ]
    results = sampler.filter_and_tier_dataset(samples)
    assert results["total_evaluated"] == 2
    assert results["retained_count"] == 1
    assert results["discarded_count"] == 1
    assert results["samples"][0]["difficulty_tier"] in (1, 2, 3)


def test_comparative_elo_arena():
    arena = ComparativeEloArena(k_factor=32.0, default_elo=1200.0)

    # Match 1: Model A beats Model B
    elo_a, elo_b = arena.record_match(
        match_id="m1",
        prompt="Explain quantum entanglement",
        model_a="Model-A-Aligned",
        model_b="Model-B-Base",
        winner="model_a",
    )
    assert elo_a > 1200.0
    assert elo_b < 1200.0

    # Match 2: Model A beats Model C
    arena.record_match(
        match_id="m2",
        prompt="Explain relativity",
        model_a="Model-A-Aligned",
        model_b="Model-C-Base",
        winner="model_a",
    )

    lb = arena.get_leaderboard()
    assert len(lb) == 3
    assert lb[0]["model_name"] == "Model-A-Aligned"
    assert lb[0]["rank"] == 1
    assert lb[0]["matches"] == 2
    assert lb[0]["win_rate"] == 1.0


def test_cli_recipe_and_quantize_handlers():
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_recipe = Path(tmp_dir) / "unsloth_recipe.py"
        old_argv = sys.argv
        try:
            sys.argv = [
                "cli.py", "recipe",
                "--framework", "unsloth",
                "--model", "sarvamai/sarvam-2b-v0.5",
                "--dataset", "data.jsonl",
                "--output", str(out_recipe),
            ]
            code = main()
            assert code == 0
            assert out_recipe.exists()

            # Test quantize command
            out_quant = Path(tmp_dir) / "quant_output"
            sys.argv = [
                "cli.py", "quantize",
                "--model-name", "sarvamai/sarvam-2b-v0.5",
                "--format", "gguf",
                "--quant-type", "q4_k_m",
                "--output-dir", str(out_quant),
            ]
            code_q = main()
            assert code_q == 0
            assert (out_quant / "run_quantization.sh").exists()
            assert (out_quant / "Modelfile").exists()
        finally:
            sys.argv = old_argv
