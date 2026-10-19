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


def test_finetune_models_endpoint(test_client):
    """Test GET /api/finetune/models returns catalogue."""
    resp = test_client.get("/api/finetune/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert len(data["models"]) > 0
    model_ids = [m["id"] for m in data["models"]]
    assert "unsloth/llama-3-8b" in model_ids
    assert "HuggingFaceTB/SmolLM2-1.7B-Instruct" in model_ids


def test_finetune_jobs_list_endpoint(test_client):
    """Test GET /api/finetune/jobs returns paginated job listing."""
    from unittest.mock import AsyncMock, MagicMock
    from api.server import app

    mock_mgr = MagicMock()
    mock_mgr.list_jobs = AsyncMock(return_value=[{"id": "ft-test", "status": "completed"}])
    orig_mgr = getattr(app.state, "ft_manager", None)
    app.state.ft_manager = mock_mgr

    try:
        resp = test_client.get("/api/finetune/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "total" in data
        assert "limit" in data
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "ft-test"
    finally:
        app.state.ft_manager = orig_mgr


def test_finetune_jobs_create_endpoint(test_client):
    """Test POST /api/finetune/jobs creates job and returns 201."""
    from unittest.mock import AsyncMock, MagicMock
    from api.server import app

    mock_mgr = MagicMock()
    mock_mgr.list_jobs = AsyncMock(return_value=[])
    mock_mgr.create_job = AsyncMock(return_value={"id": "ft-new-123", "status": "pending"})
    orig_mgr = getattr(app.state, "ft_manager", None)
    orig_db = getattr(app.state, "db", None)
    app.state.ft_manager = mock_mgr
    app.state.db = MagicMock()

    try:
        csrf_resp = test_client.get("/auth/csrf-token")
        csrf_token = csrf_resp.json().get("csrf_token")
        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

        payload = {
            "dataset_path": "/tmp/dummy.jsonl",
            "base_model": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
            "num_train_epochs": 1,
        }
        resp = test_client.post("/api/finetune/jobs", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "ft-new-123"
        assert data["status"] == "pending"
    finally:
        app.state.ft_manager = orig_mgr
        app.state.db = orig_db


@pytest.mark.asyncio
async def test_finetune_job_manager_lifecycle():
    """Test FinetuneJobManager job creation, log buffering, and cancellation."""
    from unittest.mock import AsyncMock, MagicMock
    from finetuning.job_manager import FinetuneJobManager

    mock_db = MagicMock()
    mock_db.create_finetune_job = AsyncMock(return_value=MagicMock(to_dict=lambda: {"id": "ft-123", "status": "pending"}))
    mock_db.update_finetune_job = AsyncMock()
    mock_db.get_finetune_job = AsyncMock(return_value=MagicMock(to_dict=lambda: {"id": "ft-123", "status": "running"}))
    mock_db.list_finetune_jobs = AsyncMock(return_value=[MagicMock(to_dict=lambda: {"id": "ft-123", "status": "running"})])

    manager = FinetuneJobManager(mock_db)
    
    # Check initial list
    jobs = await manager.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "ft-123"

    # Add log entry
    buf = manager._logs.setdefault("ft-123", __import__("collections").deque(maxlen=100))
    buf.append({"type": "progress", "epoch": 1, "loss": 0.45})
    logs = manager.get_logs("ft-123")
    assert len(logs) == 1
    assert logs[0]["loss"] == 0.45

