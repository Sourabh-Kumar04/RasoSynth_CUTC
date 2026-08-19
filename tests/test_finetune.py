import pytest
from finetuning.trainer import FineTuneConfig

def test_finetune_config_validation():
    """Test default values and validation of FineTuneConfig."""
    config = FineTuneConfig()
    assert config.base_model == "unsloth/llama-3-8b"
    assert config.learning_rate > 0
    assert config.num_train_epochs >= 1
    assert config.load_in_4bit is True

def test_finetune_config_custom_values():
    """Test custom configuration serialization."""
    custom = FineTuneConfig(
        base_model="Qwen/Qwen2.5-7B-Instruct",
        learning_rate=1e-4,
        num_train_epochs=5,
        load_in_4bit=True,
    )
    d = custom.to_dict()
    assert d["base_model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert d["learning_rate"] == 1e-4
    assert d["num_train_epochs"] == 5

    restored = FineTuneConfig.from_dict(d)
    assert restored.base_model == custom.base_model
    assert restored.num_train_epochs == custom.num_train_epochs
