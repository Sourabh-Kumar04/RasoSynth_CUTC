"""Tests for Canary Quality Gate, Multimodal Table Extraction, and KTO/SimPO alignment."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from finetuning.trainer import FineTuneConfig, generate_hf_model_card
from pipeline.multimodal import ExtractedTable, MultimodalDocumentExtractor
from core.evaluation.canary_gate import CanaryQualityGate


def test_canary_quality_gate_approvals():
    """Verify CanaryQualityGate approves healthy checkpoints and blocks low win rates."""
    healthy_job = {"final_train_loss": 0.35, "model_seal": "a" * 32}
    decision = CanaryQualityGate.evaluate(healthy_job, benchmark_result={"win_rate_pct": 82.0})
    assert decision.passed is True
    assert decision.verdict == "APPROVED_FOR_RELEASE"
    assert "Canary_Gate-PASSED" in decision.badges_markdown
    assert decision.dbom_verified is True

    # Low win rate should be blocked
    failing_job = {"final_train_loss": 0.35, "model_seal": "a" * 32}
    fail_decision = CanaryQualityGate.evaluate(failing_job, benchmark_result={"win_rate_pct": 55.0})
    assert fail_decision.passed is False
    assert fail_decision.verdict == "BLOCKED_LOW_WIN_RATE"
    assert "Canary_Gate-BLOCKED" in fail_decision.badges_markdown


def test_multimodal_table_extraction():
    """Verify MultimodalDocumentExtractor parses grid tables into Markdown and QA pairs."""
    table_text = """
    Tax Slab\tRate (%)\tTurnover Threshold
    Slab A\t5%\tUp to 5 Lakhs
    Slab B\t12%\t5 to 10 Lakhs
    Slab C\t18%\tAbove 10 Lakhs
    """
    tables = MultimodalDocumentExtractor.parse_text_table_grid(table_text, title="GST Schedule")
    assert len(tables) == 1
    t = tables[0]
    assert t.title == "GST Schedule"
    assert len(t.headers) == 3
    assert len(t.rows) == 3

    md = t.to_markdown()
    assert "| Tax Slab |" in md
    assert "| Slab A |" in md

    qa_pairs = MultimodalDocumentExtractor.synthesize_vision_qa_pairs(t, domain="taxation")
    assert len(qa_pairs) >= 2
    assert "Tax Slab" in qa_pairs[0]["table_markdown"]
    assert qa_pairs[0]["modality"] == "multimodal_table"


def test_kto_and_simpo_model_card_generation(tmp_path):
    """Verify generate_hf_model_card generates accurate YAML and badges for KTO and SimPO."""
    # KTO config
    cfg_kto = FineTuneConfig(
        base_model="sarvamai/sarvam-2b-v0.5",
        output_model_name="sarvam-kto-model",
        training_method="kto",
        dpo_beta=0.12,
    )
    card_kto = generate_hf_model_card(cfg_kto, tmp_path)
    content_kto = Path(card_kto).read_text(encoding="utf-8")
    assert "- kto" in content_kto
    assert "KTO (Kahneman-Tversky) Alignment Configuration" in content_kto
    assert "Canary_Gate-PASSED" in content_kto

    # SimPO config
    cfg_simpo = FineTuneConfig(
        base_model="sarvamai/sarvam-2b-v0.5",
        output_model_name="sarvam-simpo-model",
        training_method="simpo",
        dpo_beta=0.05,
    )
    card_simpo = generate_hf_model_card(cfg_simpo, tmp_path)
    content_simpo = Path(card_simpo).read_text(encoding="utf-8")
    assert "- simpo" in content_simpo
    assert "SIMPO Alignment Configuration" in content_simpo
    assert "DPO Loss Type**: `simpo`" in content_simpo


def test_playground_endpoint(test_client):
    """Verify /playground and / HTML negotiation serve the playground."""
    resp = test_client.get("/playground")
    assert resp.status_code == 200
    assert "RasoSynthTune" in resp.text
    assert "Live Interactive Engine Playground" in resp.text

    # Root endpoint HTML negotiation
    resp_root_html = test_client.get("/", headers={"Accept": "text/html"})
    assert resp_root_html.status_code == 200
    assert "RasoSynthTune" in resp_root_html.text

    # Root endpoint JSON negotiation
    resp_root_json = test_client.get("/", headers={"Accept": "application/json"})
    assert resp_root_json.status_code == 200
    data = resp_root_json.json()
    assert data["name"] == "RasoSynthTune"
    assert "playground" in data
