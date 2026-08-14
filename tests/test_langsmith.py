import pytest
from core.langsmith_tracer import LangSmithTracer

def test_langsmith_tracer_initialization():
    tracer = LangSmithTracer(project_name="TestProject", enabled=False)
    status = tracer.get_status()
    assert status["available"] is True
    assert status["project_name"] == "TestProject"

def test_langsmith_tracing_fallback():
    tracer = LangSmithTracer(project_name="TestProject", enabled=False)
    # Ensure safe execution without throwing unhandled exceptions
    tracer.trace_job_start("job-123", "prompt", "news", {})
    tracer.trace_stage("job-123", "filter", {"url": "http://example.com"}, {"passed": True}, 15.0)
    tracer.trace_job_complete("job-123", 10, 0.95, {})
