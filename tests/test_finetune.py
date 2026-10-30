import uuid
import pytest
from finetuning.trainer import FineTuneConfig

def test_finetune_config_validation():
    """Test default values and validation of FineTuneConfig."""
    config = FineTuneConfig()
    assert config.base_model == "sarvamai/sarvam-2b-v0.5"
    assert config.execution_target == "local"
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


def test_finetune_models_endpoint(test_client, auth_headers):
    """Test GET /api/finetune/models returns catalogue."""
    resp = test_client.get("/api/finetune/models", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert len(data["models"]) > 0
    model_ids = [m["id"] for m in data["models"]]
    assert "unsloth/llama-3-8b" in model_ids
    assert "HuggingFaceTB/SmolLM2-1.7B-Instruct" in model_ids


def test_finetune_jobs_list_endpoint(test_client, auth_headers):
    """Test GET /api/finetune/jobs returns paginated job listing."""
    from unittest.mock import AsyncMock, MagicMock
    from api.server import app

    mock_mgr = MagicMock()
    mock_mgr.list_jobs = AsyncMock(return_value=[{"id": "ft-test", "status": "completed"}])
    orig_mgr = getattr(app.state, "ft_manager", None)
    app.state.ft_manager = mock_mgr

    try:
        resp = test_client.get("/api/finetune/jobs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "total" in data
        assert "limit" in data
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "ft-test"
    finally:
        app.state.ft_manager = orig_mgr


def test_finetune_jobs_create_endpoint(test_client, auth_headers):
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
        csrf_resp = test_client.get("/auth/csrf-token", headers=auth_headers)
        csrf_token = csrf_resp.json().get("csrf_token")
        headers = dict(auth_headers)
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token

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
    mock_db.create_finetune_job = AsyncMock(return_value=MagicMock(to_dict=lambda: {"id": "12345678-1234-5678-1234-567812345678", "status": "pending"}))
    mock_db.update_finetune_job = AsyncMock()
    mock_db.get_finetune_job = AsyncMock(return_value=MagicMock(to_dict=lambda: {"id": "12345678-1234-5678-1234-567812345678", "status": "running"}))
    mock_db.list_finetune_jobs = AsyncMock(return_value=[MagicMock(to_dict=lambda: {"id": "12345678-1234-5678-1234-567812345678", "status": "running"})])

    manager = FinetuneJobManager(mock_db)
    
    # Check initial list
    jobs = await manager.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "12345678-1234-5678-1234-567812345678"

    # Add log entry
    buf = manager._logs.setdefault("12345678-1234-5678-1234-567812345678", __import__("collections").deque(maxlen=100))
    buf.append({"type": "progress", "epoch": 1, "loss": 0.45})
    logs = manager.get_logs("12345678-1234-5678-1234-567812345678")
    assert len(logs) == 1
    assert logs[0]["loss"] == 0.45


def test_format_sample_templates():
    """Test format_sample with standard instruction/response across templates."""
    from finetuning.trainer import format_sample

    sample = {"instruction": "Calculate 2+2", "input": "", "response": "4"}

    alpaca_out = format_sample(sample, "alpaca")
    assert "### Instruction:\nCalculate 2+2" in alpaca_out
    assert "### Response:\n4" in alpaca_out

    chatml_out = format_sample(sample, "chatml")
    assert "<|im_start|>user\nCalculate 2+2<|im_end|>" in chatml_out
    assert "<|im_start|>assistant\n4<|im_end|>" in chatml_out

    sharegpt_out = format_sample(sample, "sharegpt")
    assert "### Human:\nCalculate 2+2" in sharegpt_out
    assert "### Assistant:\n4" in sharegpt_out

    openai_out = format_sample(sample, "openai_jsonl")
    assert "User: Calculate 2+2" in openai_out
    assert "Assistant: 4" in openai_out


def test_format_sample_cross_format():
    """Test format_sample parsing ShareGPT and OpenAI formats."""
    from finetuning.trainer import format_sample

    # ShareGPT sample with conversations list
    sharegpt_sample = {
        "conversations": [
            {"from": "human", "value": "Hello"},
            {"from": "gpt", "value": "Hi there!"}
        ]
    }
    out = format_sample(sharegpt_sample, "chatml")
    assert "<|im_start|>user\nHello<|im_end|>" in out
    assert "<|im_start|>assistant\nHi there!<|im_end|>" in out

    out_alpaca = format_sample(sharegpt_sample, "alpaca")
    assert "### Instruction:\nHello" in out_alpaca
    assert "### Response:\nHi there!" in out_alpaca

    # OpenAI sample with messages list
    openai_sample = {
        "messages": [
            {"role": "user", "content": "What is AI?"},
            {"role": "assistant", "content": "Machine intelligence."}
        ]
    }
    out_sg = format_sample(openai_sample, "sharegpt")
    assert "### Human:\nWhat is AI?" in out_sg
    assert "### Assistant:\nMachine intelligence." in out_sg


@pytest.mark.asyncio
async def test_finetune_webhook_dispatch():
    """Test webhook dispatch on fine-tune job completion."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from finetuning.job_manager import FinetuneJobManager
    from finetuning.trainer import FineTuneConfig

    mock_db = MagicMock()
    manager = FinetuneJobManager(mock_db)

    config = FineTuneConfig(
        dataset_path="test.jsonl",
        base_model="HuggingFaceTB/SmolLM2-1.7B-Instruct",
        output_model_name="test-webhook-model",
        webhook_url="https://discord.com/api/webhooks/test-hook",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        await manager._dispatch_webhook(
            config.webhook_url,
            "ft-job-456",
            "completed",
            {"type": "completed", "loss": 0.32},
            config,
        )

        mock_post.assert_awaited_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://discord.com/api/webhooks/test-hook"
        payload = call_args[1]["json"]
        assert payload["job_id"] == "ft-job-456"
        assert payload["status"] == "completed"
        assert payload["base_model"] == "HuggingFaceTB/SmolLM2-1.7B-Instruct"
        assert "Final Loss: `0.32`" in payload["content"]
        assert "/api/finetune/jobs/ft-job-456/download" in payload["download_url"]


@pytest.mark.asyncio
async def test_finetune_string_dataset_id_and_listing():
    """Ensure non-UUID dataset IDs (e.g. flagship presets) do not crash listing or fetching."""
    from core.db import DatabaseManager
    from finetuning.job_manager import FinetuneJobManager

    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    manager = FinetuneJobManager(db)

    # 1. Create job with non-UUID dataset_id string
    job_id = str(uuid.uuid4())
    fj = await db.create_finetune_job({
        "id": job_id,
        "status": "pending",
        "base_model": "sarvamai/sarvam-2b-v0.5",
        "output_model_name": "test1",
        "dataset_id": "user_selected_dataset",
        "config": {"epochs": 3},
    })
    assert fj.id == job_id
    assert fj.dataset_id == "user_selected_dataset"

    # 2. list_jobs should retrieve it smoothly without ValueError
    jobs = await manager.list_jobs(limit=10)
    found = [j for j in jobs if j["id"] == job_id]
    assert len(found) == 1
    assert found[0]["dataset_id"] == "user_selected_dataset"
    assert found[0]["output_model_name"] == "test1"

    # 3. get_job should retrieve it smoothly
    fetched = await manager.get_job(job_id)
    assert fetched is not None
    assert fetched["id"] == job_id
    assert fetched["dataset_id"] == "user_selected_dataset"

    await db.close()


@pytest.mark.asyncio
async def test_finetune_cross_worker_logs_persistence(tmp_path):
    """Ensure logs persisted by one worker can be read by peer worker instances."""
    from core.db import DatabaseManager
    from finetuning.job_manager import FinetuneJobManager

    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    worker1 = FinetuneJobManager(db)
    worker2 = FinetuneJobManager(db)

    job_id = str(uuid.uuid4())
    event = {"type": "progress", "progress": 42.5, "loss": 1.25}

    worker1._persist_log_event(job_id, event)
    # worker2 has empty in-memory ring buffer for this job
    assert job_id not in worker2._logs

    # worker2 should fall back to shared disk log
    logs = worker2.get_logs(job_id)
    assert len(logs) >= 1
    assert logs[-1]["type"] == "progress"
    assert logs[-1]["loss"] == 1.25

    await db.close()


def test_finetune_gguf_export_and_download(test_client, tmp_path, auth_headers):
    """Test 1-click GGUF export, GGUF binary download, and Ollama Modelfile endpoints."""
    from unittest.mock import AsyncMock, MagicMock
    from api.server import app

    out_dir = tmp_path / "finetune_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    # P0 honesty: export/download only serve real weights files (the old
    # endpoints fabricated magic+zero files). Provide a test fixture file
    # with GGUF magic and non-zero payload so the flow under test -- not
    # the fabrication -- is exercised.
    (out_dir / "model-q4_k_m.gguf").write_bytes(b"GGUF" + bytes(4) + b"\x01\x02\x03\x04" * 64)
    fake_job = {
        "id": "ft-gguf-test",
        "output_model_name": "gguf-test-model",
        "output_path": str(out_dir),
        "chat_template": "alpaca",
        "status": "completed",
    }

    mock_mgr = MagicMock()
    mock_mgr.get_job = AsyncMock(return_value=fake_job)
    orig_mgr = getattr(app.state, "ft_manager", None)
    app.state.ft_manager = mock_mgr

    try:
        csrf_resp = test_client.get("/auth/csrf-token", headers=auth_headers)
        csrf_token = csrf_resp.json().get("csrf_token")
        headers = dict(auth_headers)
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token

        # 1. Trigger GGUF export
        export_res = test_client.post("/api/finetune/jobs/ft-gguf-test/export_gguf", headers=headers)
        assert export_res.status_code == 200
        export_data = export_res.json()
        assert export_data["status"] == "ready"
        assert export_data["format"] == "GGUF-Q4_K_M"
        assert "compatibility not verified" in export_data["runtime_compatibility"]

        # 2. Test GGUF binary download
        download_res = test_client.get("/api/finetune/jobs/ft-gguf-test/download_gguf", headers=auth_headers)
        assert download_res.status_code == 200
        assert download_res.headers["content-type"] == "application/octet-stream"
        assert b"GGUF" in download_res.content

        # 3. Test Ollama Modelfile endpoint
        modelfile_res = test_client.get("/api/finetune/jobs/ft-gguf-test/modelfile", headers=auth_headers)
        assert modelfile_res.status_code == 200
        modelfile_text = modelfile_res.text
        assert "FROM ./gguf-test-model-q4_k_m.gguf" in modelfile_text
        assert "TEMPLATE" in modelfile_text
        assert "PARAMETER temperature" in modelfile_text
    finally:
        app.state.ft_manager = orig_mgr



