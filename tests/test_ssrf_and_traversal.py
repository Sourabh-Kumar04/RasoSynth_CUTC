import pytest
import os
import tempfile
from pathlib import Path
from fastapi import HTTPException

from core.storage.traversal import validate_identifier, sanitize_filename, ensure_contained_path
from core.migration_safety import quote_identifier, add_column, create_index
from pipeline.extraction import _is_safe_url
from pipeline.discovery import DiscoveryPipeline

def test_validate_identifier():
    assert validate_identifier("valid_job-123.abc") == "valid_job-123.abc"
    with pytest.raises(ValueError, match="Path traversal"):
        validate_identifier("../etc/passwd")
    with pytest.raises(ValueError, match="Path traversal"):
        validate_identifier("job/subjob")
    with pytest.raises(ValueError, match="invalid characters"):
        validate_identifier("job$123")

def test_sanitize_filename():
    assert sanitize_filename("../test.jsonl") == "test.jsonl"
    assert sanitize_filename("foo/bar/baz.csv") == "baz.csv"

def test_ensure_contained_path():
    root = tempfile.mkdtemp()
    safe_child = os.path.join(root, "safe.txt")
    with open(safe_child, "w") as f:
        f.write("hello")
    assert ensure_contained_path(safe_child, root) == Path(safe_child).resolve()
    
    with pytest.raises(ValueError, match="Path traversal detected"):
        ensure_contained_path("/etc/passwd", root)

def test_quote_identifier():
    assert quote_identifier("users") == '"users"'
    assert quote_identifier("col_name_1") == '"col_name_1"'
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        quote_identifier("users; DROP TABLE users;--")

def test_migration_step_quoted():
    step = add_column("users", "email", "VARCHAR(255)")
    assert 'ALTER TABLE "users" ADD COLUMN "email"' in step.sql
    assert 'ALTER TABLE "users" DROP COLUMN "email"' in step.rollback_sql

def test_ssrf_port_check():
    # Loopback or private IPs should fail
    safe, reason = _is_safe_url("http://127.0.0.1:8000")
    assert not safe
    
    # Unusual port should fail
    safe, reason = _is_safe_url("http://google.com:22")
    assert not safe
    assert "Disallowed port" in reason

def test_discovery_suffix_allowlist():
    pipe = DiscoveryPipeline({})
    pipe.domain_allowlist = ["example.com"]
    
    # Exact match and subdomain match should pass
    assert pipe._is_domain_allowed("https://example.com/data")
    assert pipe._is_domain_allowed("https://sub.example.com/data")
    
    # Substring spoofing should be rejected
    assert not pipe._is_domain_allowed("https://spoofedexample.com/data")
    assert not pipe._is_domain_allowed("https://example.com.attacker.com/data")

@pytest.mark.asyncio
async def test_finetune_dataset_path_escape_rejected():
    from api.finetune import create_finetune_job, CreateFineTuneJobRequest
    from api.auth import User, UserRole
    from unittest.mock import MagicMock
    
    req = CreateFineTuneJobRequest(
        dataset_path="/etc/shadow",
        base_model="sarvamai/sarvam-2b-v0.5"
    )
    user = User(user_id="u123", username="testuser", role=UserRole.USER)
    with pytest.raises(HTTPException) as exc:
        await create_finetune_job(
            body=req,
            request=MagicMock(),
            manager=MagicMock(),
            db=MagicMock(),
            current_user=user
        )
    assert exc.value.status_code == 400
    assert "escapes allowed dataset root" in exc.value.detail
