#!/usr/bin/env python3
"""Unit and security tests for presigned ephemeral tokens and dataset streaming authorization."""

import os
import sys
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure JWT secret is set
os.environ.setdefault("JWT_SECRET", "super-secret-test-key-32-chars-length!!")

from fastapi.testclient import TestClient
from api.server import app, _sign_download_token, _verify_download_token


def test_sign_and_verify_token():
    """Verify HMAC signature generation and validation logic."""
    job_id = "test-job-uuid-1234"
    now = int(time.time())
    expires_at = now + 3600

    token = _sign_download_token(job_id, expires_at)
    assert isinstance(token, str)
    assert len(token) == 64  # SHA256 hex is 64 chars

    # Valid token should verify
    assert _verify_download_token(job_id, token, expires_at) is True

    # Tampered token should fail
    assert _verify_download_token(job_id, token[:-2] + "ff", expires_at) is False

    # Tampered job_id should fail (cannot reuse token on another dataset)
    assert _verify_download_token("another-job-id", token, expires_at) is False

    # Expired token (>60s past expiry) should fail
    expired_time = now - 120
    expired_token = _sign_download_token(job_id, expired_time)
    assert _verify_download_token(job_id, expired_token, expired_time) is False


def test_signed_url_generation_endpoints():
    """Test POST and GET /jobs/{id}/signed-url."""
    client = TestClient(app)
    job_id = "job-secure-5678"

    # GET signed URL
    resp_get = client.get(f"/jobs/{job_id}/signed-url?ttl_seconds=1800&format=csv")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["job_id"] == job_id
    assert data_get["format"] == "csv"
    assert data_get["expires_in_seconds"] == 1800
    assert "token" in data_get
    assert f"/jobs/{job_id}/download?token=" in data_get["download_url"]

    # POST signed URL
    resp_post = client.post(
        f"/jobs/{job_id}/signed-url",
        json={"ttl_seconds": 7200, "format": "parquet"}
    )
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["job_id"] == job_id
    assert data_post["format"] == "parquet"
    assert data_post["expires_in_seconds"] == 7200


def test_download_authorization_enforcement():
    """Test that unauthorized access to private dataset is blocked with 403."""
    client = TestClient(app)
    job_id = "private-research-dataset-9999"

    # 1. Unauthenticated direct download -> 403 Forbidden
    resp_unauth = client.get(f"/jobs/{job_id}/download")
    assert resp_unauth.status_code == 403
    assert "Unauthorized dataset access" in resp_unauth.json()["detail"]

    # 2. Forged / invalid token -> 403 Forbidden
    resp_forged = client.get(f"/jobs/{job_id}/download?token=invalidtoken123&expires={int(time.time()) + 3600}")
    assert resp_forged.status_code == 403
    assert "Invalid or expired download token" in resp_forged.json()["detail"]

    # 3. Missing expires or token parameter -> 403 Forbidden
    resp_partial = client.get(f"/jobs/{job_id}/download?token=some_token")
    assert resp_partial.status_code == 403

    # 5. Valid signed token should pass authorization (status != 403)
    valid_exp = int(time.time()) + 3600
    valid_token = _sign_download_token(job_id, valid_exp)
    with patch("api.server._resolve_dynamic_disk_dataset") as mock_disk:
        mock_disk.return_value = None
        with patch("api.server.db") as mock_db:
            from unittest.mock import AsyncMock
            mock_db.get_dataset = AsyncMock(return_value=None)
            mock_db.get_job_status = AsyncMock(return_value=None)
            mock_db.get_datasets = AsyncMock(return_value=[])
            resp_valid = client.get(f"/jobs/{job_id}/download?token={valid_token}&expires={valid_exp}")
            assert resp_valid.status_code == 404  # Successfully authenticated! Proceeded to lookup.


if __name__ == "__main__":
    test_sign_and_verify_token()
    test_signed_url_generation_endpoints()
    test_download_authorization_enforcement()
    print("All signed download tests passed!")
