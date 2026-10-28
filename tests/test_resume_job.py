from scripts.resume_job import resume_pipeline_job


def test_resume_pipeline_job_dry_run():
    """Verify resume_pipeline_job dry-run mode validates input without network calls."""
    res = resume_pipeline_job(
        job_id="job-resume-test-001",
        dry_run=True,
    )
    assert res["success"] is True
    assert res["job_id"] == "job-resume-test-001"
    assert res["dry_run"] is True
