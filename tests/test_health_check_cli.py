import pytest
from scripts.health_check import run_diagnostics


@pytest.mark.asyncio
async def test_run_diagnostics_reports_components():
    """Verify health diagnostic returns all critical architecture components."""
    diag = await run_diagnostics()
    assert "timestamp" in diag
    assert "status" in diag
    assert "components" in diag

    comps = diag["components"]
    assert "filesystem" in comps
    assert "database" in comps
    assert "redis" in comps
    assert "cloud_compute" in comps
    assert "llm_providers" in comps

    cc = comps["cloud_compute"]
    assert "modal_serverless" in cc
    assert "runpod_workers" in cc
    assert "huggingface_hub" in cc
