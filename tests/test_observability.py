"""Tests for observability with correlation IDs and tracing."""
import pytest
import logging

from core.observability import (
    ObservabilityManager,
    correlation_id_var,
    trace_id_var,
    span_id_var,
    TraceContext,
    set_trace_context,
    generate_trace_id,
    generate_span_id,
    generate_correlation_id,
    traced,
    timed,
    MetricsCollector,
    AuditLogger,
    get_audit_logger,
    HealthChecker,
    get_health_checker,
)
from core.config import Settings


class TestCorrelationIDs:
    """Test correlation ID functionality."""

    def test_generate_correlation_id(self) -> None:
        """Test generating a new correlation ID."""
        cid = generate_correlation_id()
        assert cid is not None
        assert len(cid) > 0

    def test_set_trace_context(self) -> None:
        """Test setting trace context."""
        trace_id = generate_trace_id()
        span_id = generate_span_id()
        correlation_id = generate_correlation_id()

        ctx = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            correlation_id=correlation_id,
        )
        set_trace_context(ctx)

        assert trace_id_var.get() == trace_id
        assert span_id_var.get() == span_id
        assert correlation_id_var.get() == correlation_id


class TestTraceContext:
    """Test TraceContext dataclass."""

    def test_create_trace_context(self) -> None:
        """Test creating a TraceContext."""
        ctx = TraceContext(
            trace_id="trace-123",
            span_id="span-456",
            correlation_id="corr-789",
        )
        assert ctx.trace_id == "trace-123"
        assert ctx.span_id == "span-456"
        assert ctx.correlation_id == "corr-789"


class TestAuditLogger:
    """Test AuditLogger."""

    def test_create_audit_logger(self) -> None:
        """Test creating an AuditLogger."""
        logger = AuditLogger("test-service")
        assert logger is not None


class TestHealthChecker:
    """Test HealthChecker."""

    def test_get_health_checker(self) -> None:
        """Test getting health checker."""
        hc = get_health_checker()
        assert hc is not None


class TestMetricsCollector:
    """Test MetricsCollector."""

    def test_metrics_collector(self) -> None:
        """Test creating a MetricsCollector."""
        from core.observability import MetricsCollector
        assert MetricsCollector is not None


class TestObservabilityTraces:
    """Test trace recording, ring buffer, and query capabilities."""

    def test_record_and_retrieve_traces(self) -> None:
        settings = Settings()
        obs = ObservabilityManager(settings)

        entry = obs.record_trace(
            operation="test_op",
            duration_ms=45.2,
            status="ok",
            service="test_svc",
            correlation_id="corr-12345",
        )
        assert entry["operation"] == "test_op"
        assert entry["status"] == "ok"
        assert entry["service"] == "test_svc"
        assert entry["correlation_id"] == "corr-12345"

        traces = obs.get_traces(service="test_svc")
        assert len(traces) >= 1
        assert traces[0]["operation"] == "test_op"

        by_corr = obs.get_traces(correlation_id="corr-12345")
        assert len(by_corr) >= 1

        fetched = obs.get_trace_by_id(entry["trace_id"])
        assert fetched is not None
        assert fetched["trace_id"] == entry["trace_id"]

    def test_trace_ring_buffer_limit(self) -> None:
        settings = Settings()
        obs = ObservabilityManager(settings)
        obs._max_trace_buffer_size = 5

        for i in range(10):
            obs.record_trace(operation=f"op_{i}", duration_ms=10.0)

        assert len(obs._trace_buffer) == 5
        # The most recent should be at the head
        assert obs._trace_buffer[0]["operation"] == "op_9"


class TestTraceEndpointsAndMiddleware:
    """Test /traces API endpoints and TracingMiddleware header propagation."""

    def test_tracing_endpoints_and_headers(self, auth_headers) -> None:
        import os
        from fastapi.testclient import TestClient
        os.environ.setdefault("JWT_SECRET", "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A")
        import api.server as server_mod

        # Ensure server_mod.observability is instantiated for test
        server_mod.observability = ObservabilityManager(Settings())

        client = TestClient(server_mod.app)

        # Make a request with custom correlation ID
        custom_corr = "corr-test-custom-999"
        resp = client.get("/health", headers={"x-correlation-id": custom_corr})
        assert "x-trace-id" in resp.headers
        assert resp.headers.get("x-correlation-id") == custom_corr

        # Verify /traces endpoint returns recorded traces
        traces_resp = client.get("/traces?limit=10", headers=auth_headers)
        assert traces_resp.status_code == 200
        data = traces_resp.json()
        assert "traces" in data
        assert len(data["traces"]) > 0

        # Query by correlation ID
        corr_resp = client.get(f"/traces/correlation?correlation_id={custom_corr}", headers=auth_headers)
        assert corr_resp.status_code == 200
        corr_data = corr_resp.json()
        assert any(t["correlation_id"] == custom_corr for t in corr_data["traces"])

        # Query single trace by ID
        target_trace = data["traces"][0]
        single_resp = client.get(f"/traces/{target_trace['trace_id']}", headers=auth_headers)
        assert single_resp.status_code == 200
        assert single_resp.json()["trace_id"] == target_trace["trace_id"]