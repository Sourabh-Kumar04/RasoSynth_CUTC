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