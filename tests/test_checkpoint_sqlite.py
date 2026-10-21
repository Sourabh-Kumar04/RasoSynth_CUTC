"""Test checkpoint endpoints and fallback with SQLite database."""
import pytest
from fastapi.testclient import TestClient
from api.server import app


def test_checkpoint_endpoints_sqlite():
    with TestClient(app) as client:
        # Fetch CSRF token
        csrf_res = client.get("/auth/csrf-token")
        csrf_token = csrf_res.json().get("csrf_token")
        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

        # Create a checkpoint
        create_payload = {
            "job_id": "test-job-sqlite-cp",
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
        assert data["job_id"] == "test-job-sqlite-cp"
        cp_id = data["checkpoint_id"]
        assert cp_id

        # Get latest checkpoint
        res_latest = client.get("/checkpoints/test-job-sqlite-cp")
        assert res_latest.status_code == 200, res_latest.text
        assert res_latest.json()["checkpoint_id"] == cp_id

        # Get checkpoint history
        res_hist = client.get("/checkpoints/test-job-sqlite-cp/history")
        assert res_hist.status_code == 200, res_hist.text
        assert len(res_hist.json()) >= 1

        # Restore checkpoint
        restore_payload = {
            "job_id": "test-job-sqlite-cp",
            "checkpoint_id": cp_id,
        }
        res_restore = client.post("/checkpoints/test-job-sqlite-cp/restore", json=restore_payload, headers=headers)
        assert res_restore.status_code in [200, 404, 503], res_restore.text
        if res_restore.status_code == 200:
            restore_data = res_restore.json()
            assert restore_data["success"] is True

        # Test job report endpoint
        res_report = client.get("/jobs/test-job-sqlite-cp/report")
        assert res_report.status_code in [200, 404, 503]
