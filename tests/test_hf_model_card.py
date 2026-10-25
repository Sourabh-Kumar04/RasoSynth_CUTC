import pytest
from core.export.huggingface_exporter import generate_hf_model_card


def test_generate_hf_model_card_structure():
    """Verify Hugging Face LoRA adapter Model Card generation and YAML frontmatter."""
    card = generate_hf_model_card(
        model_name="Llama-3-8B-IndicLegal-LoRA",
        base_model="meta-llama/Meta-Llama-3-8B-Instruct",
        dataset_name="IndicLegal-BNS-2023",
        sample_count=20000,
        epochs=3,
        learning_rate=2e-4,
        lora_r=16,
        lora_alpha=32,
        train_loss=0.8421,
        eval_loss=0.9120,
        merkle_root="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        certificate_id="DBOM-2026-CERT-LEGAL",
        domain="Indian Law & Constitutional Jurisprudence",
    )

    # Frontmatter assertions
    assert card.startswith("---")
    assert "base_model: meta-llama/Meta-Llama-3-8B-Instruct" in card
    assert "library_name: peft" in card
    assert "pipeline_tag: text-generation" in card
    assert "rasosynthtune" in card

    # Content assertions
    assert "# Model Card for Llama-3-8B-IndicLegal-LoRA" in card
    assert "IndicLegal-BNS-2023" in card
    assert "20,000 synthetic instruction samples" in card
    assert "| **LoRA Rank (r)** | `16` |" in card
    assert "- **Final Train Loss**: `0.8421`" in card

    # DBOM assertions
    assert "DBOM-2026-CERT-LEGAL" in card
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in card

    # Inference snippet assertions
    assert "from peft import PeftModel" in card
    assert "from transformers import AutoModelForCausalLM" in card
