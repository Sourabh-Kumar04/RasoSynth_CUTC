"""Regression tests for step-5 P1 items 14/15 (API fake-success + hygiene).

Covers, per sub-item:
- retry launches work or errors (terminal / already-running / no orchestrator)
- research-cycle status default is unified (missing -> "completed", loop
  values pass through)
- mask-pii never returns raw matched PII values
- tools endpoints return 400 (not 500) on bad casts / wrong types
- GET /providers is 503 on outage and never defaults "available" to True
- settings-compute credential fragments are admin-only
- /health reports key presence as "configured", never "healthy", and
  never falls back to a hardcoded commit hash
- /health/ready never embeds raw exception strings
- /auth/csrf-token never issues tokens for "anonymous"
- login/provider-test rate-limit keys do not trust X-Forwarded-For
  unless TRUST_PROXY is set
- JWT weak-pattern rejection does not reject long random secrets that
  merely contain a substring like "test"
- legacy-hash login really re-hashes; lockout after 5 failures;
  logout revokes the token
"""
import os

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------- auth unit
def _manager_with_secret(monkeypatch, secret):
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("ADMIN_USER", "")
    monkeypatch.setenv("USER_USER", "")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    from api.auth import AuthManager

    return AuthManager()


def test_jwt_random_secret_containing_test_substring_accepted(monkeypatch):
    # 68 chars, high diversity, contains "test" by construction.
    base = "Ab3dE5fG7hJ9kM2nP4qR6sT8vW1xY0zC"
    secret = "test" + base * 2
    assert len(secret) >= 48 and len(set(secret)) >= 16
    mgr = _manager_with_secret(monkeypatch, secret)
    assert mgr.secret == secret


def test_jwt_short_weak_secret_still_rejected(monkeypatch):
    with pytest.raises(ValueError):
        _manager_with_secret(monkeypatch, "test-password-1234567890abcdef")


def test_legacy_hash_login_rehashes_to_bcrypt(monkeypatch):
    from api.auth import UserRole

    mgr = _manager_with_secret(monkeypatch, "L8mQ2xZ9vN4wR7tY1uI5oP3aS6dF0gHjK9mN2bV")
    mgr._users["legacy-user"] = {
        "user_id": "legacy-001",
        "username": "legacy-user",
        "password_hash": "plain-legacy-pass-123",
        "role": UserRole.USER,
        "email": None,
    }
    assert mgr.authenticate("legacy-user", "plain-legacy-pass-123") is not None
    # Upgraded to the preferred form: bcrypt when available, else PBKDF2.
    upgraded = mgr._users["legacy-user"]["password_hash"]
    assert upgraded != "plain-legacy-pass-123"
    assert upgraded.startswith("$2b$") or upgraded.startswith("$pbkdf2-sha256$")
    # Still authenticates after the upgrade.
    assert mgr.authenticate("legacy-user", "plain-legacy-pass-123") is not None


def test_password_policy_and_lockout(monkeypatch):
    from api.auth import UserRole

    mgr = _manager_with_secret(monkeypatch, "L8mQ2xZ9vN4wR7tY1uI5oP3aS6dF0gHjK9mN2bV")
    with pytest.raises(ValueError):
        mgr.create_user("short-user", "short", UserRole.USER)
    mgr.create_user("lock-user", "correct-password-123", UserRole.USER)
    for _ in range(5):
        assert mgr.authenticate("lock-user", "wrong-password-123") is None
    # Locked: even the correct password fails until the window passes.
    assert mgr.authenticate("lock-user", "correct-password-123") is None


def test_logout_revocation(monkeypatch):
    from api.auth import UserRole

    mgr = _manager_with_secret(monkeypatch, "L8mQ2xZ9vN4wR7tY1uI5oP3aS6dF0gHjK9mN2bV")
    mgr.create_user("rev-user", "revoke-password-123", UserRole.USER)
    token = mgr.create_token("rev-001", "rev-user", UserRole.USER)
    assert mgr.verify_token(token).username == "rev-user"
    mgr.revoke_token(token)
    with pytest.raises(HTTPException) as exc:
        mgr.verify_token(token)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------- csrf / xff
def test_csrf_token_anonymous_rejected(test_client):
    assert test_client.get("/auth/csrf-token").status_code == 401


def test_csrf_token_authenticated_bound_to_user(test_client, auth_headers):
    resp = test_client.get("/auth/csrf-token", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["csrf_token"]
    assert data["user_id"] != "anonymous"


def test_get_client_ip_ignores_forwarded_header_by_default(monkeypatch):
    from starlette.requests import Request

    from api.server import get_client_ip

    monkeypatch.delenv("TRUST_PROXY", raising=False)
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"x-forwarded-for", b"9.9.9.9")],
        "client": ("1.2.3.4", 5000),
    }
    assert get_client_ip(Request(scope)) == "1.2.3.4"
    monkeypatch.setenv("TRUST_PROXY", "true")
    assert get_client_ip(Request(scope)) == "9.9.9.9"


# ---------------------------------------------------------------- providers
def test_providers_outage_is_503_not_empty_list(test_client, auth_headers, monkeypatch):
    import api.server as server_mod

    monkeypatch.setattr(server_mod, "router", None)
    resp = test_client.get("/providers", headers=auth_headers)
    assert resp.status_code == 503


def test_provider_available_not_defaulted_true(test_client, auth_headers, monkeypatch):
    import api.server as server_mod

    class FakeRouter:
        def get_stats(self):
            return {
                "demo-prov": {
                    "requests": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "cost_per_token": 0.0,
                    "avg_latency_ms": None,
                    "success_rate": None,
                    # NOTE: no "available" key at all.
                }
            }

    monkeypatch.setattr(server_mod, "router", FakeRouter())
    resp = test_client.get("/providers", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "unknown"
    single = test_client.get("/providers/demo-prov", headers=auth_headers)
    assert single.status_code == 200
    assert single.json()["status"] == "unknown"


# ---------------------------------------------------------------- settings
def test_settings_compute_fragments_admin_only(test_client, auth_headers, user_auth_headers):
    user_resp = test_client.get("/settings/compute", headers=user_auth_headers)
    assert user_resp.status_code == 200
    user_data = user_resp.json()
    assert "modal_token_id_masked" not in user_data
    assert "runpod_key_masked" not in user_data
    assert "hf_token_masked" not in user_data
    assert "modal_configured" in user_data
    admin_resp = test_client.get("/settings/compute", headers=auth_headers)
    assert admin_resp.status_code == 200
    assert "modal_token_id_masked" in admin_resp.json()


# ---------------------------------------------------------------- health
def test_health_key_presence_is_configured_not_healthy(test_client, auth_headers, monkeypatch):
    import api.server as server_mod

    class FakeRouter:
        _provider_configs = {"prov": {"api_key": "x"}}

    monkeypatch.setattr(server_mod, "router", FakeRouter())
    monkeypatch.setattr(server_mod, "provider_validator", None)
    resp = test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["providers"]["prov"] == "configured"
    assert data["status"] in ("degraded", "unhealthy")
    assert data["commit_hash"] != "8e41824"


def test_ready_does_not_embed_raw_exceptions(test_client, monkeypatch):
    import api.server as server_mod

    class BadDB:
        async def list_jobs(self):
            raise RuntimeError("SENTINEL_DB_FAILURE_MESSAGE")

    monkeypatch.setattr(server_mod, "db", BadDB())
    monkeypatch.setattr(server_mod, "cache", None)
    resp = test_client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["database"] == "not_ready"
    assert "SENTINEL_DB_FAILURE_MESSAGE" not in resp.text


# ---------------------------------------------------------------- research
def test_research_cycle_status_unified():
    from api.server import _research_cycle_status

    assert _research_cycle_status({}) == "completed"
    assert _research_cycle_status({"status": None}) == "completed"
    assert _research_cycle_status({"status": "success"}) == "success"
    assert _research_cycle_status({"status": "skipped"}) == "skipped"


# ---------------------------------------------------------------- mask-pii / tools
def test_mask_pii_returns_no_raw_values(test_client, auth_headers):
    resp = test_client.post(
        "/tools/mask-pii",
        json={"text": "Aadhaar is 2345 6789 0123"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.text
    assert "2345" not in body
    data = resp.json()
    assert "detected" not in data
    assert data["detected_types"].get("aadhaar", 0) >= 1
    assert "[AADHAAR_REDACTED]" in data["masked"]


def test_tools_bad_casts_are_400_not_500(test_client, auth_headers):
    resp = test_client.post(
        "/tools/generate-adversarial-probes",
        json={"sample_count": "not-a-number"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    resp = test_client.post(
        "/tools/shard-dataset",
        json={"samples": [{"instruction": "q", "response": "a"}], "shard_size": "xx"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    resp = test_client.post(
        "/tools/semantic-density",
        json={"samples": "not-a-list"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------- retry (item 14)
def _fake_db(job):
    from unittest.mock import AsyncMock

    db = AsyncMock()
    db.get_job_status.return_value = job
    return db


def test_retry_terminal_job_is_409(test_client, auth_headers, monkeypatch):
    import api.server as server_mod

    monkeypatch.setattr(server_mod, "db", _fake_db({"status": "completed", "config": {}}))
    monkeypatch.setattr(server_mod, "orchestrator", None)
    resp = test_client.post(
        "/orchestration/steps/quality_eval/retry",
        params={"job_id": "job-1"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_retry_without_orchestrator_is_503(test_client, auth_headers, monkeypatch):
    import api.server as server_mod

    monkeypatch.setattr(server_mod, "db", _fake_db({"status": "failed", "config": {}}))
    monkeypatch.setattr(server_mod, "orchestrator", None)
    resp = test_client.post(
        "/orchestration/steps/quality_eval/retry",
        params={"job_id": "job-1"},
        headers=auth_headers,
    )
    assert resp.status_code == 503


def test_retry_launches_pipeline(test_client, auth_headers, monkeypatch):
    import asyncio
    import time

    import api.server as server_mod

    calls = []

    async def fake_run_pipeline(job_id, config, resume_state=None):
        calls.append((job_id, config))

    class FakeOrch:
        active_jobs = {}

    monkeypatch.setattr(server_mod, "db", _fake_db({"status": "failed", "config": {"target_domain": "x"}}))
    monkeypatch.setattr(server_mod, "orchestrator", FakeOrch())
    monkeypatch.setattr(server_mod, "run_pipeline", fake_run_pipeline)
    resp = test_client.post(
        "/orchestration/steps/quality_eval/retry",
        params={"job_id": "job-1"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "retrying"
    assert resp.json()["relaunched"] is True
    # Background task runs on the TestClient portal loop.
    for _ in range(50):
        if calls:
            break
        time.sleep(0.1)
    assert calls and calls[0][0] == "job-1"
    assert asyncio.iscoroutinefunction(fake_run_pipeline)

