"""Test checkpoint endpoints and fallback with SQLite/PostgreSQL database."""
import uuid
from fastapi.testclient import TestClient
from api.server import app


def test_checkpoint_endpoints_sqlite():
    test_job_id = str(uuid.uuid4())
    with TestClient(app) as client:
        # Fetch CSRF token
        csrf_res = client.get("/auth/csrf-token")
        csrf_token = csrf_res.json().get("csrf_token")
        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

        # Create a checkpoint
        create_payload = {
            "job_id": test_job_id,
            "stage": "discovery",
            "progress": 0.2,
            "sources_discovered": 5,
            "sources_extracted": 0,
            "samples_filtered": 0,
            "samples_generated": 0,
            "provider_name": "google_gemini",
            "provider_model": "gemini-1.5-flash",
        }
        res = client.post("/checkpoints", json=create_payload, headers=headers)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["job_id"] == test_job_id
        cp_id = data["checkpoint_id"]
        assert cp_id

        # Get latest checkpoint
        res_latest = client.get(f"/checkpoints/{test_job_id}")
        assert res_latest.status_code == 200, res_latest.text
        assert res_latest.json()["checkpoint_id"] == cp_id

        # Get checkpoint history
        res_hist = client.get(f"/checkpoints/{test_job_id}/history")
        assert res_hist.status_code == 200, res_hist.text
        assert len(res_hist.json()) >= 1

        # Restore checkpoint
        restore_payload = {
            "job_id": test_job_id,
            "checkpoint_id": cp_id,
        }
        res_restore = client.post(f"/checkpoints/{test_job_id}/restore", json=restore_payload, headers=headers)
        assert res_restore.status_code in [200, 404, 503], res_restore.text
        if res_restore.status_code == 200:
            restore_data = res_restore.json()
            assert restore_data["success"] is True

        # Test job report endpoint
        res_report = client.get(f"/jobs/{test_job_id}/report")
        assert res_report.status_code in [200, 404, 503]
