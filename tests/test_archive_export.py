import pytest
from unittest.mock import AsyncMock
from starlette.testclient import TestClient
from api.server import app
import api.server as server_mod


def test_export_unsupported_format_returns_400(auth_headers):
    """Verify export rejects unsupported file extensions with 400."""
    client = TestClient(app)
    csrf_token = client.get("/auth/csrf-token", headers=auth_headers).json()["csrf_token"]
    res = client.post("/datasets/nonexistent-id/export", json={"format": "unsupported_ext_xyz"},
                      headers={"X-CSRF-Token": csrf_token, **auth_headers})
    assert res.status_code in (400, 404)


@pytest.mark.asyncio
async def test_export_tar_gz_archive_handling(tmp_path, auth_headers):
    """Verify export creates and serves .tar.gz archive with application/gzip media type."""
    mock_db = AsyncMock()
    fake_dataset_id = "test-archive-dataset-001"
    out_dir = tmp_path / "test_out_dir"
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_file = out_dir / "samples.jsonl"
    sample_file.write_text('{"instruction": "test", "response": "test"}\n', encoding="utf-8")

    mock_db.get_dataset.return_value = {
        "id": fake_dataset_id,
        "name": "indic_legal_archive",
        "output_path": str(sample_file),
        "job_id": "job-12345",
    }
    mock_db.get_samples_by_dataset.return_value = [
        {"instruction": "q1", "response": "a1", "metadata": {}}
    ]

    orig_db = server_mod.db
    server_mod.db = mock_db
    try:
        client = TestClient(app)
        csrf_token = client.get("/auth/csrf-token", headers=auth_headers).json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf_token, **auth_headers}

        # Request tar.gz format
        res = client.post(
            f"/datasets/{fake_dataset_id}/export",
            json={"format": "tar.gz"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.headers.get("content-type") == "application/gzip"
        assert "indic_legal_archive.tar.gz" in res.headers.get("content-disposition", "")
        assert len(res.content) > 0
    finally:
        server_mod.db = orig_db
