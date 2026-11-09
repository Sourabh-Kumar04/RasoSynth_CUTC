import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from core.orchestrator_pkg.orchestrator import DatasetOrchestrator
from api.review import TriggerDpoFinetuneRequest, trigger_dpo_finetune_endpoint
from api.auth import User, UserRole


@pytest.mark.asyncio
async def test_orchestrator_trigger_dpo_finetune(tmp_path):
    mock_db = MagicMock()
    orch = DatasetOrchestrator(config={}, router=MagicMock(), db=mock_db)

    mock_review_svc = AsyncMock()
    mock_review_svc.export_dpo_pairs.return_value = [
        {
            "prompt": "Evaluate cardiac arrhythmia treatment protocols.",
            "chosen": "Administer amiodarone and monitor ECG telemetry.",
            "rejected": "No intervention required.",
            "source_review_id": "rev-1",
        }
    ]

    with patch("core.orchestrator_pkg.orchestrator.Path") as mock_path:
        mock_path.return_value = tmp_path
        res = await orch.trigger_dpo_finetune(
            job_id="job-dpo-123",
            base_model="sarvamai/sarvam-2b-v0.5",
            review_service=mock_review_svc,
        )

    assert res["status"] == "dataset_prepared"
    assert res["job_id"] == "job-dpo-123"
    assert res["preference_pairs_count"] == 1
    assert "dpo-aligned-job-dpo-" in res["output_model_name"]


@pytest.mark.asyncio
async def test_api_trigger_dpo_finetune_endpoint(tmp_path):
    mock_svc = AsyncMock()
    mock_svc.export_dpo_pairs.return_value = [
        {
            "prompt": "What is the recommended dosage for paracetamol?",
            "chosen": "500mg every 4 to 6 hours up to 4g maximum daily.",
            "rejected": "10g all at once.",
            "source_review_id": "rev-2",
        }
    ]

    mock_req = MagicMock()
    mock_req.app.state.ft_manager = AsyncMock()
    mock_req.app.state.ft_manager.create_job.return_value = {
        "id": "ft-job-999",
        "status": "pending",
        "output_model_name": "dpo-aligned-test",
    }

    user = User(user_id="usr-1", username="doctor-alice", role=UserRole.USER)
    req_body = TriggerDpoFinetuneRequest(
        base_model="sarvamai/sarvam-2b-v0.5",
        training_method="dpo",
        output_model_name="dpo-aligned-test",
    )

    with patch("api.review.Path") as mock_path:
        mock_path.return_value = tmp_path
        res = await trigger_dpo_finetune_endpoint(
            job_id="job-test-777",
            request=mock_req,
            body=req_body,
            current_user=user,
            svc=mock_svc,
        )

    assert res["status"] == "launched"
    assert res["finetune_job_id"] == "ft-job-999"
    assert res["preference_pairs_count"] == 1
