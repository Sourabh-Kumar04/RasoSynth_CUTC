import pytest
from rasosynth import RasoSynthClient, JobResult, DBOMAttestation


def test_sdk_client_initialization():
    client = RasoSynthClient(api_key="rs_live_test_12345", base_url="http://localhost:8000")
    assert client.api_key == "rs_live_test_12345"
    assert client.base_url == "http://localhost:8000"
    headers = client._headers()
    assert headers["Authorization"] == "Bearer rs_live_test_12345"
    assert "RasoSynth-Python-SDK" in headers["User-Agent"]


def test_sdk_job_result_properties():
    res = JobResult(
        job_id="test-job-123",
        status="completed",
        progress=1.0,
        samples_generated=10,
        dbom=DBOMAttestation(
            certificate_id="DBOM-TEST",
            merkle_root="abc123def456",
            total_samples=10,
        ),
    )
    assert res.is_completed is True
    assert res.is_failed is False
    assert res.dbom.merkle_root == "abc123def456"
    assert res.dbom.certificate_id == "DBOM-TEST"


def test_dbom_attestation_from_dict():
    data = {
        "certificate_id": "DBOM-A1B2C3",
        "merkle_root_hash": "deadbeef12345678",
        "issued_at": "2026-10-26T12:00:00Z",
        "domain": "GST Compliance",
        "language": "hi",
        "total_samples": 42,
    }
    attestation = DBOMAttestation.from_dict(data)
    assert attestation.certificate_id == "DBOM-A1B2C3"
    assert attestation.merkle_root == "deadbeef12345678"
    assert attestation.total_samples == 42
    assert attestation.domain == "GST Compliance"
