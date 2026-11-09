"""
Tests for Advanced DPO Fine-Tuning & Alignment Engine.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from finetuning.trainer import (
    FineTuneConfig,
    estimate_vram_requirement,
    export_to_ollama,
)


def test_finetune_config_dpo_and_ollama():
    """Verify FineTuneConfig supports DPO, packing, and Ollama export parameters."""
    cfg = FineTuneConfig(
        dataset_path="data/dpo_pairs.jsonl",
        base_model="sarvamai/sarvam-2b-v0.5",
        training_method="dpo",
        dpo_beta=0.08,
        dpo_loss_type="sigmoid",
        max_prompt_length=256,
        packing=True,
        export_ollama=True,
        system_prompt="You are a helpful assistant.",
    )
    cfg.validate()
    d = cfg.to_dict()
    assert d["training_method"] == "dpo"
    assert d["dpo_beta"] == 0.08
    assert d["dpo_loss_type"] == "sigmoid"
    assert d["max_prompt_length"] == 256
    assert d["packing"] is True
    assert d["export_ollama"] is True
    assert d["system_prompt"] == "You are a helpful assistant."


def test_estimate_vram_dpo_footprint():
    """Verify that DPO VRAM estimation factors in dual-sequence forward pass memory."""
    sft_est = estimate_vram_requirement(
        base_model="sarvamai/sarvam-2b-v0.5",
        max_seq_length=2048,
        per_device_train_batch_size=4,
        training_method="sft",
    )
    dpo_est = estimate_vram_requirement(
        base_model="sarvamai/sarvam-2b-v0.5",
        max_seq_length=2048,
        per_device_train_batch_size=4,
        training_method="dpo",
    )

    # DPO activations should be larger due to simultaneous chosen + rejected evaluations
    assert dpo_est["training_method"] == "dpo"
    assert dpo_est["activation_memory_gb"] > sft_est["activation_memory_gb"]
    assert dpo_est["total_estimated_vram_gb"] > sft_est["total_estimated_vram_gb"]
    assert dpo_est["supported_on_16gb_gpu"] is True


def test_export_to_ollama(tmp_path):
    """Verify generation of valid Ollama Modelfile and export manifest."""
    model_dir = tmp_path / "model_out"
    manifest = export_to_ollama(
        model_dir=model_dir,
        output_name="custom-dpo-model",
        template="chatml",
        system_prompt="Custom alignment system prompt",
    )

    assert manifest["model_name"] == "custom-dpo-model"
    assert "ollama create custom-dpo-model" in manifest["cli_command"]

    modelfile = Path(manifest["modelfile_path"])
    assert modelfile.exists()
    content = modelfile.read_text(encoding="utf-8")

    assert "FROM " in content
    assert "<|im_start|>" in content
    assert "Custom alignment system prompt" in content
    assert "PARAMETER temperature 0.7" in content

    manifest_file = model_dir / "ollama_manifest.json"
    assert manifest_file.exists()
    saved_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert saved_data["model_name"] == "custom-dpo-model"


def test_api_estimate_vram_endpoint(test_client, auth_headers):
    """Verify API POST /api/finetune/estimate-vram handles training_method='dpo'."""
    payload = {
        "base_model": "sarvamai/sarvam-2b-v0.5",
        "max_seq_length": 2048,
        "per_device_train_batch_size": 2,
        "training_method": "dpo",
    }
    resp = test_client.post("/api/finetune/estimate-vram", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "breakdown" in data
    assert data["breakdown"]["training_method"] == "dpo"
    assert "recommended_hyperparameters" in data


def test_api_export_ollama_endpoint(test_client, auth_headers, tmp_path, monkeypatch):
    """Verify API POST /api/finetune/jobs/{id}/export-ollama generates Modelfile."""
    mock_job = MagicMock()
    mock_job.to_dict.return_value = {
        "id": "job-dpo-123",
        "owner": "admin",
        "config": {
            "output_dir": str(tmp_path),
            "output_model_name": "test-aligned-model",
            "chat_template": "alpaca",
            "system_prompt": "Helpful AI",
        },
    }
    mock_job.config = mock_job.to_dict.return_value["config"]

    mock_mgr = AsyncMock()
    mock_mgr.get_job.return_value = mock_job
    test_client.app.state.ft_manager = mock_mgr

    payload = {
        "chat_template": "alpaca",
        "system_prompt": "Helpful AI",
    }
    resp = test_client.post("/api/finetune/jobs/job-dpo-123/export-ollama", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["job_id"] == "job-dpo-123"
    assert "Modelfile" in res_data["modelfile"]
    assert "ollama create" in res_data["cli_command"]
    assert "### Instruction:" in res_data["modelfile_content"]
