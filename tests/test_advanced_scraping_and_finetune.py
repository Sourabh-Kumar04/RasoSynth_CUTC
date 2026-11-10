"""
Comprehensive tests for advanced scraping and fine-tuning engine upgrades.
"""

import asyncio
import os
import tempfile
from pathlib import Path
import pytest

from core.crawler.tls_stealth import BrowserImpersonation, StealthHTTPClient, get_default_tls_profiles
from core.crawler.proxy_pool import ProxyHealthOrchestrator, ProxyHealthRecord
from pipeline.domain_extractors.regulatory import IndianRegulatoryExtractor
from pipeline.pdf_stream import StreamingPDFExtractor
from pipeline.preference_pipeline import PreferenceDatasetSynthesizer, PreferencePair
from finetuning.trainer import discover_lora_target_modules, get_optimal_attn_implementation
from finetuning.distributed import build_deepspeed_config, build_fsdp_config
from finetuning.checkpoint_manager import AtomicCheckpointManager, CheckpointState
from finetuning.export_quant import QuantizationExporter


def test_tls_stealth_profiles():
    profiles = get_default_tls_profiles()
    assert BrowserImpersonation.CHROME_124 in profiles
    assert BrowserImpersonation.SAFARI_17 in profiles

    chrome_prof = profiles[BrowserImpersonation.CHROME_124]
    assert chrome_prof.ja3_hash != ""
    assert "h2" in chrome_prof.alpn_protocols
    assert "Sec-Ch-Ua" in chrome_prof.headers


@pytest.mark.asyncio
async def test_proxy_health_orchestrator():
    orchestrator = ProxyHealthOrchestrator(
        proxies=["http://proxy1.internal:8080", "http://proxy2.internal:8080"],
        max_consecutive_failures=2,
        quarantine_duration_sec=10.0,
    )

    # Healthiest proxy chosen
    p1 = await orchestrator.get_proxy("https://gst.gov.in/news")
    assert p1 in ("http://proxy1.internal:8080", "http://proxy2.internal:8080")

    # Sticky routing matches same domain
    p2 = await orchestrator.get_proxy("https://gst.gov.in/circulars")
    assert p1 == p2

    # Quarantine proxy on consecutive failures
    await orchestrator.record_result(p1, success=False, is_blocked=True)
    rec = orchestrator._records[p1]
    assert rec.is_quarantined is True

    # Next proxy selection falls back to the healthy one
    p_fallback = await orchestrator.get_proxy("https://incometax.gov.in")
    assert p_fallback != p1


def test_indian_regulatory_extractor():
    sample_text = """
    CBIC Circular No. 210/4/2024-GST
    F. No. CBIC-190354/12/2024-TRU
    Government of India
    Ministry of Finance, Department of Revenue
    Central Board of Indirect Taxes and Customs
    Dated: 15th July, 2024

    Subject: Clarification on valuation of supply of services under Section 15(3) of the CGST Act, 2017.

    Representations have been received seeking clarification regarding tax treatment under Rule 28 of the CGST Rules, 2017.
    """
    extractor = IndianRegulatoryExtractor()
    doc = extractor.extract(sample_text)

    assert doc.circular_id == "210/4/2024-GST"
    assert "Central Board of Indirect Taxes and Customs" in doc.issuing_authority
    assert doc.date_issued == "15th July, 2024"
    assert "valuation of supply of services" in doc.subject.lower()
    assert len(doc.statutory_references) > 0
    assert len(doc.qa_pairs) == 1
    assert "210/4/2024-GST" in doc.qa_pairs[0]["instruction"]


def test_streaming_pdf_extractor():
    extractor = StreamingPDFExtractor(scanned_threshold_chars=40)

    # Text PDF simulation
    dense_text = "This is a detailed statutory clause.\nIt contains multiple lines of regulatory instructions."
    pages = extractor._process_page_text(1, dense_text)
    assert pages.is_scanned is False
    assert pages.char_count > 40

    # Scanned PDF simulation (very few characters)
    sparse_text = "Img-01"
    scanned_page = extractor._process_page_text(2, sparse_text)
    assert scanned_page.is_scanned is True
    assert "Scanned page 2 detected" in scanned_page.text


def test_contrastive_preference_synthesizer():
    synth = PreferenceDatasetSynthesizer(domain="tax_compliance")
    pair = synth.synthesize_contrastive_from_sample(
        instruction="What are the conditions for claiming Input Tax Credit (ITC)?",
        golden_response="Taxpayers must possess a valid tax invoice and the supplier must have filed GSTR-1.",
        perturbation_type="hallucination",
    )
    assert pair.chosen != pair.rejected
    assert "tax invoice" in pair.chosen
    assert pair.margin_score >= 0.7

    kto_records = pair.to_kto_records()
    assert len(kto_records) == 2
    assert kto_records[0]["label"] is True
    assert kto_records[1]["label"] is False


def test_discover_lora_target_modules():
    class DummyLayer:
        pass

    class DummyModel:
        def named_modules(self):
            return [
                ("model.layers.0.self_attn.q_proj", DummyLayer()),
                ("model.layers.0.self_attn.v_proj", DummyLayer()),
                ("model.layers.0.mlp.gate_proj", DummyLayer()),
            ]

    targets = discover_lora_target_modules(DummyModel())
    assert "q_proj" in targets
    assert "v_proj" in targets
    assert "gate_proj" in targets

    attn_impl = get_optimal_attn_implementation()
    assert attn_impl in ("flash_attention_2", "sdpa", "eager")


def test_distributed_configs():
    ds_config = build_deepspeed_config(
        batch_size=2,
        grad_accum_steps=8,
        learning_rate=1e-4,
        zero_stage=3,
        cpu_offload=True,
        bf16=True,
    )
    assert ds_config["zero_optimization"]["stage"] == 3
    assert ds_config["zero_optimization"]["offload_optimizer"]["device"] == "cpu"
    assert ds_config["bf16"]["enabled"] is True

    fsdp_config = build_fsdp_config(sharding_strategy="HYBRID_SHARD", cpu_offload=False)
    assert fsdp_config["fsdp"] == "hybrid_shard"
    assert fsdp_config["fsdp_config"]["fsdp_activation_checkpointing"] is True


def test_atomic_checkpoint_manager():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = AtomicCheckpointManager(checkpoint_dir=tmp_dir, max_keep=2)

        state1 = CheckpointState(job_id="job_123", step=100, epoch=1, train_loss=1.85, learning_rate=2e-4)
        path1 = mgr.save_checkpoint(state1, model_artifacts={"adapter_weights.bin": b"fake_weights_step_100"})
        assert path1.exists()

        state2 = CheckpointState(job_id="job_123", step=200, epoch=2, train_loss=1.20, learning_rate=1e-4)
        path2 = mgr.save_checkpoint(state2, model_artifacts={"adapter_weights.bin": b"fake_weights_step_200"})
        assert path2.exists()

        latest = mgr.get_latest_checkpoint()
        assert latest is not None
        latest_path, latest_state = latest
        assert latest_state.step == 200
        assert latest_state.train_loss == 1.20


def test_ollama_modelfile_exporter():
    modelfile = QuantizationExporter.generate_ollama_modelfile(
        model_name="sarvam-2b-indic",
        gguf_file="sarvam-2b-indic-Q4_K_M.gguf",
        system_prompt="You are an expert Indic legal assistant.",
        temperature=0.4,
    )
    assert "FROM ./sarvam-2b-indic-Q4_K_M.gguf" in modelfile
    assert "PARAMETER temperature 0.4" in modelfile
    assert "You are an expert Indic legal assistant." in modelfile
