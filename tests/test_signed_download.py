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


def test_signed_url_generation_endpoints(auth_headers):
    """Test POST and GET /jobs/{id}/signed-url for an UNKNOWN job (expect 404 per P0-5)."""
    client = TestClient(app)
    job_id = "job-secure-5678"
    csrf_token = client.get("/auth/csrf-token", headers=auth_headers).json()["csrf_token"]

    # P0-5 requires job/dataset existence before minting a token, so an
    # unknown job must 404 instead of minting a token for nothing (the old
    # expectation of 200 for job-secure-5678, which exists nowhere).
    # NOTE: the handler only enforces existence when api.server.db is set;
    # with db=None it mints unconditionally. Pin db to an empty mock so
    # this test asserts the existence behaviour deterministically,
    # regardless of which earlier test did or did not initialise the app DB.
    from unittest.mock import AsyncMock
    mock_db = AsyncMock()
    mock_db.get_job_status.return_value = None
    mock_db.get_dataset.return_value = None
    mock_db.get_datasets_by_job.return_value = []
    with patch("api.server.db", mock_db):
        # GET signed URL for unknown job -> 404
        resp_get = client.get(f"/jobs/{job_id}/signed-url?ttl_seconds=1800&format=csv", headers=auth_headers)
        assert resp_get.status_code == 404

        # POST signed URL for unknown job -> 404
        resp_post = client.post(
            f"/jobs/{job_id}/signed-url",
            json={"ttl_seconds": 7200, "format": "parquet"},
            headers={"X-CSRF-Token": csrf_token, **auth_headers}
        )
        assert resp_post.status_code == 404


def test_download_authorization_enforcement(auth_headers):
    """Test that unauthorized access to private dataset is blocked."""
    client = TestClient(app)
    job_id = "private-research-dataset-9999"

    # 1. Unauthenticated direct download (no Bearer, no token) -> 401
    resp_unauth = client.get(f"/jobs/{job_id}/download")
    assert resp_unauth.status_code == 401
    assert "Authentication required" in resp_unauth.json()["detail"]

    # 2. Forged / invalid presigned token with no Bearer -> 403 Forbidden
    resp_forged = client.get(f"/jobs/{job_id}/download?token=invalidtoken123&expires={int(time.time()) + 3600}")
    assert resp_forged.status_code == 403
    assert "Invalid or expired download token" in resp_forged.json()["detail"]

    # 3. Missing expires or token parameter (no Bearer) -> 403 Forbidden
    resp_partial = client.get(f"/jobs/{job_id}/download?token=some_token")
    assert resp_partial.status_code == 403

    # 4. Valid signed token with NO Bearer header should succeed to route authorization
    valid_exp = int(time.time()) + 3600
    valid_token = _sign_download_token(job_id, valid_exp, user="", format="jsonl")
    with patch("api.server._resolve_dynamic_disk_dataset") as mock_disk:
        mock_disk.return_value = None
        with patch("api.server.db") as mock_db:
            from unittest.mock import AsyncMock
            mock_db.get_dataset = AsyncMock(return_value=None)
            mock_db.get_job_status = AsyncMock(return_value=None)
            mock_db.get_datasets = AsyncMock(return_value=[])
            resp_valid_presigned_only = client.get(f"/jobs/{job_id}/download?token={valid_token}&expires={valid_exp}&format=jsonl")
            assert resp_valid_presigned_only.status_code == 404  # Passes auth! Proceeded to data lookup.

    # 5. Valid Bearer token + bad/forged query token: Bearer must NOT be defeated by bad query token!
    with patch("api.server._resolve_dynamic_disk_dataset") as mock_disk:
        mock_disk.return_value = None
        with patch("api.server.db") as mock_db:
            from unittest.mock import AsyncMock
            mock_db.get_dataset = AsyncMock(return_value=None)
            mock_db.get_job_status = AsyncMock(return_value=None)
            mock_db.get_datasets = AsyncMock(return_value=[])
            resp_bearer_plus_bad_token = client.get(
                f"/jobs/{job_id}/download?token=badtoken999&expires={valid_exp}",
                headers=auth_headers
            )
            assert resp_bearer_plus_bad_token.status_code == 404  # Passes auth via Bearer!

    # 6. Cross-user / cross-format token reuse rejection
    token_user_a = _sign_download_token(job_id, valid_exp, user="user_a", format="jsonl")
    assert _verify_download_token(job_id, token_user_a, valid_exp, user="user_b", format="jsonl") is False
    assert _verify_download_token(job_id, token_user_a, valid_exp, user="user_a", format="parquet") is False


def test_download_completion_and_exact_match(auth_headers):
    """Regression test for incomplete job 409 and exact identifier matching."""
    client = TestClient(app)
    from unittest.mock import AsyncMock

    # 1. Incomplete job check -> 409
    job_id = "job-running-1234"
    with patch("api.server.db") as mock_db:
        mock_db.get_job_status = AsyncMock(return_value={"id": job_id, "status": "running", "owner": "admin"})
        mock_db.get_dataset = AsyncMock(return_value=None)
        resp = client.get(f"/jobs/{job_id}/download", headers=auth_headers)
        assert resp.status_code == 409
        assert "is not complete" in resp.json()["detail"]

    # 2. Strict exact match: substring match must be rejected (no short identifier returning wrong dataset)
    from api.server import _resolve_dynamic_disk_dataset
    # Substring of non-exact should not match
    match = _resolve_dynamic_disk_dataset("nonexistent_sub_id")
    assert match is None


if __name__ == "__main__":
    test_sign_and_verify_token()
    test_signed_url_generation_endpoints()
    test_download_authorization_enforcement()
    print("All signed download tests passed!")
