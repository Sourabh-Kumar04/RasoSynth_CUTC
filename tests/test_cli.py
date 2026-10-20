"""Tests for RasoSynthTune Unified Developer CLI (cli.py & main.py)."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

CLI_SCRIPT = str(Path(__file__).parent.parent / "cli.py")
MAIN_SCRIPT = str(Path(__file__).parent.parent / "main.py")
PYTHON_EXEC = sys.executable


def test_cli_help():
    """Verify `rasosynthtune --help` prints usage and exits cleanly with 0."""
    result = subprocess.run(
        [PYTHON_EXEC, CLI_SCRIPT, "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "rasosynthtune" in result.stdout
    assert "generate" in result.stdout
    assert "audit" in result.stdout
    assert "benchmark" in result.stdout
    assert "recipe" in result.stdout
    assert "serve" in result.stdout


def test_main_delegates_to_cli():
    """Verify `main.py` entrypoint delegates cleanly to rasosynthtune CLI."""
    result = subprocess.run(
        [PYTHON_EXEC, MAIN_SCRIPT, "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "rasosynthtune" in result.stdout
    assert "generate" in result.stdout


def test_cli_generate_and_audit():
    """Verify `rasosynthtune generate` synthesizes dataset with DBOM and `audit` verifies it."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Run generate
        gen_res = subprocess.run(
            [
                PYTHON_EXEC,
                CLI_SCRIPT,
                "generate",
                "--domain",
                "Indian Taxation & GST Compliance",
                "--size",
                "5",
                "--format",
                "jsonl",
                "--output-dir",
                tmp_dir,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "[OK] Synthesized 5 samples" in gen_res.stdout
        assert "Merkle Tree SHA-256 Root:" in gen_res.stdout

        jsonl_path = Path(tmp_dir) / "dataset_distillation_5.jsonl"
        dbom_path = Path(tmp_dir) / "dataset_distillation_5.dbom.json"
        nutrition_path = Path(tmp_dir) / "dataset_distillation_5.nutrition.md"

        assert jsonl_path.exists()
        assert dbom_path.exists()
        assert nutrition_path.exists()

        # Check records
        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 5

        # 2. Run audit
        audit_res = subprocess.run(
            [
                PYTHON_EXEC,
                CLI_SCRIPT,
                "audit",
                "--dataset",
                str(jsonl_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "PASSED - Cryptographically Intact" in audit_res.stdout
        assert "PASSED - 0 unmasked statutory PII entities detected." in audit_res.stdout
        assert "PASSED - 0% leakage against MMLU" in audit_res.stdout
        assert "PASS (Zero Leakage)" in audit_res.stdout


def test_cli_recipe_generation():
    """Verify `rasosynthtune recipe` generates axolotl and unsloth configs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        axolotl_out = Path(tmp_dir) / "axolotl.yaml"
        result = subprocess.run(
            [
                PYTHON_EXEC,
                CLI_SCRIPT,
                "recipe",
                "--framework",
                "axolotl",
                "--model",
                "sarvamai/sarvam-2b-v0.5",
                "--dataset",
                "data/train.jsonl",
                "--output",
                str(axolotl_out),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "[OK] Training recipe written" in result.stdout
        assert axolotl_out.exists()
        content = axolotl_out.read_text(encoding="utf-8")
        assert "sarvamai/sarvam-2b-v0.5" in content
        assert "base_model:" in content


def test_cli_benchmark_json():
    """Verify `rasosynthtune benchmark --json` produces valid parseable benchmark metrics."""
    result = subprocess.run(
        [PYTHON_EXEC, CLI_SCRIPT, "benchmark", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.strip().split("\n")
    json_start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            json_start = i
            break
    assert json_start >= 0, f"No JSON found in output: {result.stdout}"
    json_text = "\n".join(lines[json_start:])
    data = json.loads(json_text)
    assert "results" in data
    results = data["results"]
    assert "benchmark_generation_quality" in results
    assert "benchmark_latency" in results
    assert "benchmark_cost_efficiency" in results


def test_cli_generate_modes_and_parquet():
    """Verify `rasosynthtune generate` supports agentic_cot mode and Apache Parquet export."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        gen_res = subprocess.run(
            [
                PYTHON_EXEC,
                CLI_SCRIPT,
                "generate",
                "--domain",
                "Machine Learning Systems",
                "--size",
                "4",
                "--mode",
                "agentic_cot",
                "--format",
                "parquet",
                "--output-dir",
                tmp_dir,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "[OK] Synthesized 4 samples" in gen_res.stdout
        parquet_path = Path(tmp_dir) / "dataset_agentic_cot_4.parquet"
        dbom_path = Path(tmp_dir) / "dataset_agentic_cot_4.dbom.json"
        assert parquet_path.exists()
        assert dbom_path.exists()

        # Audit the Parquet dataset
        audit_res = subprocess.run(
            [
                PYTHON_EXEC,
                CLI_SCRIPT,
                "audit",
                "--dataset",
                str(parquet_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "PASSED - Cryptographically Intact" in audit_res.stdout
        assert "Total Samples Loaded: 4" in audit_res.stdout
