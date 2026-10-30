"""Negative authentication tests: unauthenticated / unauthorized API access.

Auth is enforced in tests (see tests/conftest.py: AUTH_DISABLED=false with
real JWT fixtures). These tests pin the P0 auth behaviour: data routes and
mutating routes reject requests without a valid token, and a role without
permission gets 403 rather than access.
"""

import pytest


def test_unauthenticated_data_route_rejected(test_client):
    resp = test_client.get("/api/quality/overview")
    assert resp.status_code == 401


def test_unauthenticated_review_queue_rejected(test_client):
    resp = test_client.get("/api/review/queue")
    assert resp.status_code == 401


def test_unauthenticated_mutating_route_rejected(test_client):
    # No CSRF token and no Authorization header: the CSRF middleware
    # rejects the state-changing request with 403 before route auth
    # runs (tokens are issued to authenticated users only, so an
    # unauthenticated caller cannot obtain one).
    resp = test_client.post(
        "/api/review/queue",
        json={
            "instruction": "Test instruction",
            "response": "Test response",
            "job_id": "job-neg-auth",
        },
        headers={},
    )
    assert resp.status_code == 403



def test_invalid_token_rejected(test_client):
    resp = test_client.get(
        "/api/quality/overview",
        headers={"Authorization": "Bearer this-is-not-a-valid-token"},
    )
    assert resp.status_code == 401


def test_authenticated_data_route_ok(test_client, auth_headers):
    resp = test_client.get("/api/quality/overview", headers=auth_headers)
    assert resp.status_code == 200
    assert "average_quality" in resp.json()


def test_viewer_cannot_submit_for_review(test_client):
    from api.auth import UserRole, get_auth_manager

    manager = get_auth_manager()
    manager.create_user("testviewer-neg", "viewer-pass-7k2m", UserRole.VIEWER)
    token = manager.create_token("viewer-neg-001", "testviewer-neg", UserRole.VIEWER)
    csrf = test_client.get("/auth/csrf-token", headers={"Authorization": f"Bearer {token}"}).json().get("csrf_token")
    headers = {"Authorization": f"Bearer {token}"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    resp = test_client.post(
        "/api/review/queue",
        json={
            "instruction": "Test instruction",
            "response": "Test response",
            "job_id": "job-neg-auth-viewer",
        },
        headers=headers,
    )
    assert resp.status_code == 403
