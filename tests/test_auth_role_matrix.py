"""Authentication, Role Matrix, and Cross-User Isolation Tests.

Covers:
- Unauthenticated (401) across route families
- VIEWER role read vs write permissions (403 for writes, 200/404 for reads)
- Cross-user isolation: User A cannot read, mutate, or download User B's resources (404 Not Found to prevent existence leakage)
- Checkpoint validation: path vs body job_id mismatch (400), unknown job (404), checkpoint job mismatch (404)
- Job cancellation & preview validation: wrong state returns 409 Conflict
"""

import os
import pytest
from api.auth import UserRole, get_auth_manager


@pytest.fixture(scope="module")
def auth_tokens():
    """Create test tokens for Admin, User A, User B, and Viewer."""
    manager = get_auth_manager()

    manager.create_user("matrix_admin", "admin_pass_9201", UserRole.ADMIN)
    admin_token = manager.create_token("admin_01", "matrix_admin", UserRole.ADMIN)

    manager.create_user("user_a", "user_a_pass_9201", UserRole.USER)
    user_a_token = manager.create_token("user_a_01", "user_a", UserRole.USER)

    manager.create_user("user_b", "user_b_pass_9201", UserRole.USER)
    user_b_token = manager.create_token("user_b_01", "user_b", UserRole.USER)

    manager.create_user("viewer_user", "viewer_pass_9201", UserRole.VIEWER)
    viewer_token = manager.create_token("viewer_01", "viewer_user", UserRole.VIEWER)

    return {
        "admin": {"Authorization": f"Bearer {admin_token}"},
        "user_a": {"Authorization": f"Bearer {user_a_token}"},
        "user_b": {"Authorization": f"Bearer {user_b_token}"},
        "viewer": {"Authorization": f"Bearer {viewer_token}"},
        "admin_token": admin_token,
        "user_a_token": user_a_token,
        "user_b_token": user_b_token,
        "viewer_token": viewer_token,
    }


def _csrf(test_client, headers):
    csrf = test_client.get("/auth/csrf-token", headers=headers).json().get("csrf_token")
    h = dict(headers)
    if csrf:
        h["X-CSRF-Token"] = csrf
    return h


# ==============================================================================
# 1. Unauthenticated (401) across route families
# ==============================================================================

@pytest.mark.parametrize(
    "method,endpoint,json_body",
    [
        ("get", "/jobs", None),
        ("get", "/jobs/test-job-id", None),
        ("post", "/jobs", {"target_domain": "test", "dataset_size": 10}),
        ("post", "/jobs/test-job-id/cancel", None),
        ("get", "/datasets", None),
        ("get", "/datasets/test-dataset-id", None),
        ("get", "/datasets/test-dataset-id/records", None),
        ("post", "/datasets/test-dataset-id/export", {"format": "jsonl"}),
        ("get", "/jobs/test-job-id/records", None),
        ("get", "/jobs/test-job-id/summary", None),
        ("get", "/jobs/test-job-id/report", None),
        ("post", "/jobs/test-job-id/signed-url", {}),
        ("get", "/checkpoints/test-job-id", None),
        ("get", "/checkpoints/test-job-id/history", None),
        ("post", "/checkpoints", {"job_id": "test-job-id", "stage": "discovery", "progress": 0.1}),
        ("post", "/checkpoints/test-job-id/restore", {"job_id": "test-job-id"}),
        ("get", "/api/finetune/jobs", None),
        ("post", "/api/finetune/jobs", {"dataset_path": "/tmp/dummy.jsonl"}),
        ("get", "/api/review/queue", None),
        ("post", "/api/review/queue", {"instruction": "Q", "response": "A", "job_id": "j1"}),
        ("get", "/settings/compute", None),
        ("get", "/providers", None),
        ("get", "/agents", None),
        ("get", "/traces", None),
    ],
)
def test_unauthenticated_requests_return_401(test_client, method, endpoint, json_body):
    # CSRF tokens are issued to authenticated users only, so an
    # unauthenticated caller cannot obtain one: GETs reach route auth
    # (401); POSTs are rejected by the CSRF middleware first (403).
    # Either way the request is rejected, never served.
    if method == "get":
        resp = test_client.get(endpoint, headers={})
        expected = 401
    elif method == "post":
        resp = test_client.post(endpoint, json=json_body, headers={})
        expected = 403
    else:
        raise AssertionError(f"unexpected method {method}")
    # A 503 must NEVER count as a pass
    assert resp.status_code == expected, f"Expected {expected} for unauthenticated {method.upper()} {endpoint}, got {resp.status_code}: {resp.text}"



def test_viewer_reads_open(test_client, auth_tokens):
    """VIEWER can read open non-mutating routes."""
    headers = auth_tokens["viewer"]
    # GET /jobs
    resp = test_client.get("/jobs", headers=headers)
    assert resp.status_code == 200
    assert "data" in resp.json()

    # GET /datasets
    resp = test_client.get("/datasets", headers=headers)
    assert resp.status_code == 200
    assert "data" in resp.json()

    # GET /api/finetune/jobs
    resp = test_client.get("/api/finetune/jobs", headers=headers)
    assert resp.status_code == 200
    assert "jobs" in resp.json()

    # GET /api/review/queue
    resp = test_client.get("/api/review/queue", headers=headers)
    assert resp.status_code == 200

    # GET /settings/compute
    resp = test_client.get("/settings/compute", headers=headers)
    assert resp.status_code == 200


def test_viewer_writes_rejected(test_client, auth_tokens):
    """VIEWER role receives 403 Forbidden on write operations."""
    headers = _csrf(test_client, auth_tokens["viewer"])

    # POST /jobs
    resp = test_client.post("/jobs", json={"target_domain": "test", "dataset_size": 10}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER POST /jobs, got {resp.status_code}"

    # POST /jobs/{id}/cancel
    resp = test_client.post("/jobs/dummy-id/cancel", headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER cancel, got {resp.status_code}"

    # POST /checkpoints
    resp = test_client.post("/checkpoints", json={"job_id": "dummy-id", "stage": "discovery", "progress": 0.1}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER POST /checkpoints, got {resp.status_code}"

    # POST /api/finetune/jobs
    resp = test_client.post("/api/finetune/jobs", json={"dataset_path": "/tmp/dummy.jsonl"}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER create finetune job, got {resp.status_code}"

    # DELETE /api/finetune/jobs/{id}
    resp = test_client.delete("/api/finetune/jobs/dummy-id", headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER cancel finetune job, got {resp.status_code}"

    # POST /datasets/{id}/export
    resp = test_client.post("/datasets/dummy-id/export", json={"format": "jsonl"}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER export dataset, got {resp.status_code}"

    # POST /datasets/{id}/deliver
    resp = test_client.post("/datasets/dummy-id/deliver", json={"destination": "local"}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER deliver dataset, got {resp.status_code}"

    # POST /jobs/{id}/signed-url
    resp = test_client.post("/jobs/dummy-id/signed-url", json={"ttl_seconds": 3600}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER signed-url, got {resp.status_code}"

    # POST /jobs/{id}/accept_preview
    resp = test_client.post("/jobs/dummy-id/accept_preview", json={}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER accept_preview, got {resp.status_code}"

    # POST /jobs/{id}/reject_preview
    resp = test_client.post("/jobs/dummy-id/reject_preview", json={}, headers=headers)
    assert resp.status_code == 403, f"Expected 403 for VIEWER reject_preview, got {resp.status_code}"


# ==============================================================================
# 3. Cross-User Isolation (User A vs User B -> 404 Not Found)
# ==============================================================================

def test_cross_user_isolation(test_client, auth_tokens, monkeypatch):
    monkeypatch.setattr("api.server.run_pipeline", lambda *args, **kwargs: None)
    """User A's resources cannot be seen, mutated, or downloaded by User B (returns 404). Admin can access."""
    # 1. Create a job for user_a via API
    headers_a = _csrf(test_client, auth_tokens["user_a"])
    job_resp = test_client.post(
        "/jobs",
        json={"target_domain": "medical NLP", "dataset_size": 5},
        headers=headers_a,
    )
    assert job_resp.status_code == 201, f"Failed to create job: {job_resp.text}"
    job_a_id = job_resp.json()["id"]

    # User A can get their job
    resp = test_client.get(f"/jobs/{job_a_id}", headers=auth_tokens["user_a"])
    assert resp.status_code == 200
    assert resp.json()["id"] == job_a_id

    # User B querying User A's job gets 404 Not Found (NEVER 403 existence leakage, NEVER 503)
    resp_b = test_client.get(f"/jobs/{job_a_id}", headers=auth_tokens["user_b"])
    assert resp_b.status_code == 404, f"Expected 404 for User B reading User A job, got {resp_b.status_code}"

    # User B attempting to read records of User A's job gets 404
    resp_b_records = test_client.get(f"/jobs/{job_a_id}/records", headers=auth_tokens["user_b"])
    assert resp_b_records.status_code == 404

    # User B attempting to read summary of User A's job gets 404
    resp_b_summary = test_client.get(f"/jobs/{job_a_id}/summary", headers=auth_tokens["user_b"])
    assert resp_b_summary.status_code == 404

    # User B attempting to read report of User A's job gets 404
    resp_b_report = test_client.get(f"/jobs/{job_a_id}/report", headers=auth_tokens["user_b"])
    assert resp_b_report.status_code == 404

    # User B attempting to create signed URL for User A's job gets 404
    headers_b = _csrf(test_client, auth_tokens["user_b"])
    resp_b_signed = test_client.post(f"/jobs/{job_a_id}/signed-url", json={"ttl_seconds": 600}, headers=headers_b)
    assert resp_b_signed.status_code == 404

    # User B attempting to cancel User A's job gets 404
    resp_b_cancel = test_client.post(f"/jobs/{job_a_id}/cancel", headers=headers_b)
    assert resp_b_cancel.status_code == 404

    # User B attempting to get preview samples gets 404
    resp_b_prev = test_client.get(f"/jobs/{job_a_id}/preview_samples", headers=auth_tokens["user_b"])
    assert resp_b_prev.status_code == 404

    # User B attempting to accept preview gets 404
    resp_b_accept = test_client.post(f"/jobs/{job_a_id}/accept_preview", json={}, headers=headers_b)
    assert resp_b_accept.status_code == 404

    # User B attempting to get quality by job gets 404
    resp_b_quality = test_client.get(f"/api/quality/by-job/{job_a_id}", headers=auth_tokens["user_b"])
    assert resp_b_quality.status_code == 404

    # Admin CAN access User A's job
    resp_admin = test_client.get(f"/jobs/{job_a_id}", headers=auth_tokens["admin"])
    assert resp_admin.status_code == 200

    # User A cancels their job
    resp_a_cancel = test_client.post(f"/jobs/{job_a_id}/cancel", headers=headers_a)
    assert resp_a_cancel.status_code == 200

    # Cancelling again returns 409 Conflict (invalid state)
    resp_a_cancel_again = test_client.post(f"/jobs/{job_a_id}/cancel", headers=headers_a)
    assert resp_a_cancel_again.status_code == 409


# ==============================================================================
# 4. Checkpoints Validation & Ownership
# ==============================================================================

def test_checkpoint_security_and_validation(test_client, auth_tokens, monkeypatch):
    monkeypatch.setattr("api.server.run_pipeline", lambda *args, **kwargs: None)
    """Checkpoints require existing job, verify job ownership, check path/body match, and check checkpoint-to-job belonging."""
    headers_a = _csrf(test_client, auth_tokens["user_a"])
    headers_b = _csrf(test_client, auth_tokens["user_b"])
    headers_admin = _csrf(test_client, auth_tokens["admin"])

    # 1. POST /checkpoints for non-existent job -> 404
    resp = test_client.post(
        "/checkpoints",
        json={"job_id": "nonexistent-job-uuid", "stage": "discovery", "progress": 0.2},
        headers=headers_a,
    )
    assert resp.status_code == 404, f"Expected 404 for unknown job in POST /checkpoints, got {resp.status_code}"

    # 2. Create job for User A
    job_resp = test_client.post(
        "/jobs",
        json={"target_domain": "finance", "dataset_size": 5},
        headers=headers_a,
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # 3. User B attempting to create checkpoint for User A's job -> 404
    resp = test_client.post(
        "/checkpoints",
        json={"job_id": job_id, "stage": "discovery", "progress": 0.2},
        headers=headers_b,
    )
    assert resp.status_code == 404

    # 4. User A creating checkpoint succeeds
    resp_cp = test_client.post(
        "/checkpoints",
        json={"job_id": job_id, "stage": "discovery", "progress": 0.2},
        headers=headers_a,
    )
    assert resp_cp.status_code == 201
    cp_id = resp_cp.json()["checkpoint_id"]

    # 5. User B getting checkpoint -> 404
    resp = test_client.get(f"/checkpoints/{job_id}", headers=auth_tokens["user_b"])
    assert resp.status_code == 404

    # 6. User B getting checkpoint history -> 404
    resp = test_client.get(f"/checkpoints/{job_id}/history", headers=auth_tokens["user_b"])
    assert resp.status_code == 404

    # 7. Checkpoint restore: path job_id vs body job_id mismatch -> 400 Bad Request
    resp = test_client.post(
        f"/checkpoints/{job_id}/restore",
        json={"job_id": "different-job-id", "checkpoint_id": cp_id},
        headers=headers_admin,
    )
    assert resp.status_code == 400, f"Expected 400 on job_id mismatch, got {resp.status_code}"

    # 8. Checkpoint restore: foreign checkpoint ID not belonging to job -> 404
    resp = test_client.post(
        f"/checkpoints/{job_id}/restore",
        json={"job_id": job_id, "checkpoint_id": "unrelated-cp-id"},
        headers=headers_admin,
    )
    assert resp.status_code == 404


# ==============================================================================
# 5. Fine-Tune & Review Isolation
# ==============================================================================

def test_review_queue_isolation(test_client, auth_tokens):
    """Review items are isolated by owner and non-admins get 404 for other's items."""
    headers_a = _csrf(test_client, auth_tokens["user_a"])
    headers_b = _csrf(test_client, auth_tokens["user_b"])

    # User A submits a review item
    submit_resp = test_client.post(
        "/api/review/queue",
        json={
            "instruction": "Explain quantum computing",
            "response": "Quantum computing uses qubits...",
            "job_id": "job_user_a",
        },
        headers=headers_a,
    )
    assert submit_resp.status_code == 201
    item_id = submit_resp.json()["id"]

    # User A can get item
    resp_a = test_client.get(f"/api/review/queue/{item_id}", headers=auth_tokens["user_a"])
    assert resp_a.status_code == 200

    # User B gets 404
    resp_b = test_client.get(f"/api/review/queue/{item_id}", headers=auth_tokens["user_b"])
    assert resp_b.status_code == 404

    # User B attempting to approve User A item gets 404
    resp_b_app = test_client.post(
        f"/api/review/queue/{item_id}/approve",
        json={"notes": "looks good"},
        headers=headers_b,
    )
    assert resp_b_app.status_code == 404

    # User B attempting to reject User A item gets 404
    resp_b_rej = test_client.post(
        f"/api/review/queue/{item_id}/reject",
        json={"notes": "no good"},
        headers=headers_b,
    )
    assert resp_b_rej.status_code == 404
