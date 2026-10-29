from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient

import api.server as server_module
from api.server import app


def test_job_websocket_stream_receives_status_and_merkle_root():
    """Verify WebSocket endpoint /ws/jobs/{job_id} streams job progress and terminates on completed."""
    # Setup mock db
    mock_db = MagicMock()
    mock_db.get_job_status = AsyncMock(return_value={
        "job_id": "job-stream-test-456",
        "status": "completed",
        "progress": 1.0,
        "stage": "completed",
        "synthesis_mode": "cot",
        "merkle_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "certificate_id": "DBOM-STREAM-TEST",
    })

    original_db = server_module.db
    server_module.db = mock_db

    try:
        client = TestClient(app)
        from api.auth import UserRole, get_auth_manager
        jwt = get_auth_manager().create_token("admin-001", "testadmin", UserRole.ADMIN)
        with client.websocket_connect(f"/ws/jobs/job-stream-test-456?token={jwt}") as websocket:
            data = websocket.receive_json()
            assert data["job_id"] == "job-stream-test-456"
            assert data["status"] == "completed"
            assert data["progress"] == 1.0
            assert data["synthesis_mode"] == "cot"
            assert data["merkle_root"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            assert data["certificate_id"] == "DBOM-STREAM-TEST"
    finally:
        server_module.db = original_db


def test_job_stream_legacy_path_alias():
    """Verify legacy path /jobs/{job_id}/stream works identically to /ws/jobs/{job_id}."""
    mock_db = MagicMock()
    mock_db.get_job_status = AsyncMock(return_value={
        "job_id": "job-stream-legacy-789",
        "status": "completed",
        "progress": 1.0,
        "stage": "packaging",
    })

    original_db = server_module.db
    server_module.db = mock_db

    try:
        client = TestClient(app)
        from api.auth import UserRole, get_auth_manager
        jwt = get_auth_manager().create_token("admin-001", "testadmin", UserRole.ADMIN)
        with client.websocket_connect(f"/jobs/job-stream-legacy-789/stream?token={jwt}") as websocket:
            data = websocket.receive_json()
            assert data["job_id"] == "job-stream-legacy-789"
            assert data["status"] == "completed"
    finally:
        server_module.db = original_db
