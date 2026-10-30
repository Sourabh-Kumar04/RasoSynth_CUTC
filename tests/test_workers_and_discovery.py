import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from enum import Enum

from pipeline.discovery import DiscoveredSource, SourceType
from finetuning.job_manager import FinetuneJobManager
from finetuning.trainer import FineTuneConfig

def test_discovered_source_metadata_field():
    src = DiscoveredSource(
        url="https://example.com/data",
        source_type=SourceType.WEB_PAGE,
        title="Example",
        metadata={"foo": "bar"}
    )
    assert src.metadata == {"foo": "bar"}
    assert not hasattr(src, "metadata_")

def test_celery_and_ray_discovery_source_dict():
    # Simulates what workers/celery_app.py and workers/ray_pipeline.py build
    src = DiscoveredSource(
        url="https://example.com",
        source_type=SourceType.WEB_PAGE,
        title="Test Page",
        metadata={"key": "val"}
    )
    record = {
        "url": src.url,
        "source_type": src.source_type.value,
        "title": src.title,
        "metadata": src.metadata,
    }
    assert record["metadata"] == {"key": "val"}

@pytest.mark.asyncio
async def test_simulated_webhook_silence():
    mock_db = MagicMock()
    mock_db.update_finetune_job = AsyncMock()
    manager = FinetuneJobManager(mock_db)
    
    config = FineTuneConfig(
        base_model="test-model",
        execution_target="modal",
        webhook_url="https://hooks.slack.com/services/T00/B00/X00"
    )
    
    event = {
        "type": "completed",
        "is_simulated": True,
        "loss": 0.42,
        "output_path": "/path/to/mock",
    }
    
    with patch.object(manager, "_dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
        await manager._dispatch_webhook(config.webhook_url, "job-123", "completed", event, config)

    # Directly check dispatch logic payload formatting
    with patch("finetuning.job_manager._webhook_allowed_and_safe", return_value=(True, "")):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            await manager._dispatch_webhook(config.webhook_url, "job-123", "completed", event, config)
            assert mock_post.called
            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            assert "SIMULATED" in payload["embeds"][0]["title"]
            assert "N/A (Simulated)" in payload["loss"]
            assert "No real model artifacts" in payload["text"]

def test_cli_local_engine_offline_rejection():
    from cli import handle_generate
    import argparse
    
    args = argparse.Namespace(
        domain="taxation",
        size=1,
        engine="vllm",
        engine_url="http://localhost:99999/v1",
        model_name="mock-model",
        output=None,
        output_dir="outputs/test_cli",
        format="jsonl",
        mode="synthetic"
    )
    with pytest.raises(RuntimeError, match="offline or unavailable"):
        handle_generate(args)
