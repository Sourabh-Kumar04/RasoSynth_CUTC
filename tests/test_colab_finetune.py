import shutil
import tempfile
from pathlib import Path
from finetuning.colab_bridge import ColabBridgeTrainer
from finetuning.trainer import FineTuneConfig

def test_colab_bridge_headless_execution():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_colab_"))
    try:
        config = FineTuneConfig(
            dataset_path="",
            dataset_id="test-ds",
            base_model="HuggingFaceTB/SmolLM2-1.7B-Instruct",
            output_model_name="test-indic-lora",
            num_train_epochs=2,
            per_device_train_batch_size=4,
            lora_r=8,
            lora_alpha=16,
            output_dir=str(temp_dir),
            execution_target="cloud_accelerated"
        )
        
        events = []
        def put_event(evt):
            events.append(evt)
            
        dummy_samples = [
            {"instruction": f"Q{i}", "response": f"A{i}"} for i in range(12)
        ]
        
        trainer = ColabBridgeTrainer(config, temp_dir)
        artifacts_path = trainer.execute_training(dummy_samples, put_event)
        
        assert artifacts_path.exists()
        assert (artifacts_path / "adapter_config.json").exists()
        # P0 honesty: no loadable weights are fabricated. The only weights
        # file is explicitly suffixed .PLACEHOLDER; a bare .safetensors
        # file must NOT exist.
        assert not (artifacts_path / "adapter_model.safetensors").exists()
        assert (artifacts_path / "adapter_model.safetensors.PLACEHOLDER").exists()
        assert (artifacts_path / "README.md").exists()
        
        # Verify downloadable zip
        zip_path = temp_dir / "finetuned_model_lora_PLACEHOLDER.zip"
        assert zip_path.exists()
        assert zip_path.stat().st_size > 0
        
        # Verify GGUF output
        gguf_path = temp_dir / "test-indic-lora-q4_k_m.gguf.PLACEHOLDER"
        assert gguf_path.exists()
        
        # Verify event stream produced progress and completed
        event_types = [e["type"] for e in events]
        assert "info" in event_types
        assert "progress" in event_types
        assert "completed" in event_types
        
        completed = next(e for e in events if e["type"] == "completed")
        assert completed.get("is_simulated") is True
        assert completed.get("weights_are_placeholders") is True
        assert "SIMULATED" in str(completed.get("message", "")).upper()
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
