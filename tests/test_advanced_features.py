"""Tests for advanced features: Preference synthesizer, quantization exporter, and crawler telemetry."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


def test_preference_synthesizer_single_pair(tmp_path):
    """Verify PreferenceDatasetSynthesizer generates valid pair and exports to JSONL."""
    from pipeline.preference_pipeline import PreferenceDatasetSynthesizer

    synth = PreferenceDatasetSynthesizer(domain="legal", max_length_ratio=2.5)
    ctx = "Under the Companies Act, corporate disclosures must be attested by a certified director."
    pair = synth.synthesize_pair_from_context(ctx)

    assert pair.prompt != ""
    assert pair.chosen != ""
    assert pair.rejected != ""
    assert pair.chosen != pair.rejected
    assert pair.domain == "legal"
    assert pair.margin_score >= 0.5

    data = pair.to_dict()
    assert "metadata" in data
    assert "length_ratio" in data["metadata"]

    out_file = tmp_path / "prefs.jsonl"
    synth.export_jsonl([pair], out_file)
    assert out_file.exists()
    lines = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["prompt"] == pair.prompt


def test_preference_synthesizer_multi_turn():
    """Verify multi-turn dialog preference generation and filtering."""
    from pipeline.preference_pipeline import PreferenceDatasetSynthesizer

    synth = PreferenceDatasetSynthesizer()
    pair = synth.synthesize_multi_turn_pair("Kubernetes Ingress")
    assert pair.multi_turn is True
    assert pair.turns is not None
    assert len(pair.turns) >= 3

    valid = synth.validate_and_filter([pair])
    assert len(valid) == 1


def test_quantization_exporter_plan_and_bundle(tmp_path):
    """Verify QuantizationExporter creates GGUF and AWQ recipes with valid VRAM savings."""
    from finetuning.export_quant import QuantizationExporter

    plan_gguf = QuantizationExporter.generate_plan(
        model_name="sarvam-2b",
        output_dir=tmp_path,
        target_format="gguf",
        quant_type="q4_k_m",
    )
    assert plan_gguf.reduction_pct > 50.0
    assert plan_gguf.quant_vram_gb < plan_gguf.fp16_vram_gb
    assert "llama.cpp" in plan_gguf.conversion_command
    assert "llama-server" in plan_gguf.serving_command

    bundle = QuantizationExporter.write_conversion_bundle(
        model_name="sarvam-2b",
        output_dir=tmp_path,
        target_format="gguf",
        quant_type="q4_k_m",
    )
    assert Path(bundle["script_path"]).exists()
    assert Path(bundle["manifest_path"]).exists()

    plan_awq = QuantizationExporter.generate_plan(
        model_name="sarvam-2b",
        output_dir=tmp_path,
        target_format="awq",
        quant_type="awq_4bit",
    )
    assert "autoawq" in plan_awq.conversion_command
    assert "vllm serve" in plan_awq.serving_command


def test_api_export_quant_endpoint(test_client, auth_headers, tmp_path):
    """Verify POST /api/finetune/jobs/{id}/export-quant produces recipe bundle."""
    mock_job = MagicMock()
    mock_job.to_dict.return_value = {
        "id": "job-quant-789",
        "owner": "admin",
        "config": {
            "output_dir": str(tmp_path),
            "output_model_name": "quant-test-model",
        },
    }
    mock_job.config = mock_job.to_dict.return_value["config"]

    mock_mgr = AsyncMock()
    mock_mgr.get_job.return_value = mock_job
    test_client.app.state.ft_manager = mock_mgr

    payload = {"target_format": "gguf", "quant_type": "q4_k_m"}
    resp = test_client.post("/api/finetune/jobs/job-quant-789/export-quant", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "job-quant-789"
    assert data["format"] == "gguf"
    assert "plan" in data
    assert data["plan"]["reduction_pct"] > 50.0


def test_api_synthesize_preference_endpoint(test_client, auth_headers):
    """Verify POST /api/datasets/synthesize-preference returns valid pairs."""
    payload = {
        "domain": "finance",
        "contexts": [
            "GST invoicing requires IRN generation on the designated portal within 30 days of supply.",
        ],
    }
    resp = test_client.post("/api/datasets/synthesize-preference", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["domain"] == "finance"
    assert data["total_valid"] >= 1
    assert "chosen" in data["pairs"][0]
    assert "rejected" in data["pairs"][0]


def test_api_crawler_telemetry_endpoint(test_client, auth_headers):
    """Verify GET /api/observability/crawler-telemetry returns cluster metrics."""
    resp = test_client.get("/observability/crawler-telemetry", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "shared_memory" in data
    assert "circuit_breakers" in data
    assert len(data["circuit_breakers"]) >= 1
    assert "challenges_mitigated" in data
    assert "proxy_pool" in data
