"""Enterprise-grade observability with OpenTelemetry, correlation IDs, and structured logging."""
import asyncio
import uuid
import logging
import os
from contextvars import ContextVar
from typing import Optional, Any, Dict, Callable
from datetime import datetime
from functools import wraps
from enum import Enum

import structlog

# Optional OpenTelemetry imports - wrap in try/except
try:
    from opentelemetry import trace, context
    from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = context = TracerProvider = SpanProcessor = None
    BatchSpanProcessor = ConsoleSpanExporter = SimpleSpanProcessor = None
    Resource = SERVICE_NAME = OTLPSpanExporter = HTTPExporter = None
    SpanKind = Status = StatusCode = TraceContextTextMapPropagator = None
    MeterProvider = PeriodicExportingMetricReader = None

try:
    from prometheus_client import REGISTRY
    from prometheus_client import Counter, Histogram, Gauge
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from prometheus_client import CONTENT_TYPE_LATEST as PROMETHEUS_CONTENT_TYPE
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    REGISTRY = None
    Counter = Histogram = Gauge = None
    generate_latest = CONTENT_TYPE_LATEST = None
    PROMETHEUS_CONTENT_TYPE = None

from core.config import Settings

logger = logging.getLogger(__name__)

# Correlation ID context variable
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


class ObservabilityManager:
    """
    Enterprise-grade observability manager.

    Features:
    - OpenTelemetry distributed tracing
    - Correlation ID propagation across async boundaries
    - Structured JSON logging with correlation context
    - Prometheus metrics
    - Span exporters (console, OTLP)
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._tracer = None
        self._meter_provider = None
        self._is_initialized = False
        self._resource = None

        # Prometheus metrics
        self._metrics: Dict[str, Any] = {}

        # LangSmith Tracer
        from core.langsmith_tracer import LangSmithTracer
        api_key = getattr(settings, "langchain_api_key", None) or os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
        project = getattr(settings, "langchain_project", None) or os.getenv("LANGCHAIN_PROJECT") or "RasoSynthTune"
        self.langsmith = LangSmithTracer(
            api_key=api_key,
            project_name=project
        )

        if PROMETHEUS_AVAILABLE:
            self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Setup Prometheus metrics. Idempotent: skips names already registered.

        Uses module-level Counter/Gauge/Histogram/REGISTRY (imports happen once
        at module load).
        """

        def _existing(name: str):
            """Return the metric already registered under ``name`` if any, else None."""
            if REGISTRY is None:
                return None
            for collector, names in REGISTRY._collector_to_names.items():
                if name in names:
                    return collector
            return None

        def _counter(name, doc, labels):
            existing = _existing(name)
            if existing is not None:
                return existing
            return Counter(name, doc, labels)

        def _gauge(name, doc, labels=None):
            existing = _existing(name)
            if existing is not None:
                return existing
            if labels is None:
                return Gauge(name, doc)
            return Gauge(name, doc, labels)

        def _histogram(name, doc, labels, **kw):
            existing = _existing(name)
            if existing is not None:
                return existing
            if kw:
                return Histogram(name, doc, labels, **kw)
            return Histogram(name, doc, labels)

        self._metrics = {
            "requests_total": _counter(
                "dataset_engine_requests_total",
                "Total requests",
                ["method", "endpoint", "status"],
            ),
            "request_duration": _histogram(
                "dataset_engine_request_duration_seconds",
                "Request duration",
                ["method", "endpoint"],
            ),
            "active_jobs": _gauge(
                "dataset_engine_active_jobs",
                "Active jobs",
            ),
            "tokens_total": _counter(
                "dataset_engine_tokens_total",
                "Token usage",
                ["provider", "type"],
            ),
            "cost_usd": _counter(
                "dataset_engine_cost_usd",
                "Total cost in USD",
                ["provider"],
            ),
            "cache_hit_rate": _gauge(
                "dataset_engine_cache_hit_rate",
                "Cache hit rate",
            ),
            "provider_latency": _histogram(
                "dataset_engine_provider_latency_seconds",
                "Provider latency",
                ["provider", "operation"],
            ),
            "fallback_count": _counter(
                "dataset_engine_fallback_total",
                "Total fallback occurrences",
                ["from_provider", "to_provider"],
            ),
            "circuit_breaker_state": _gauge(
                "dataset_engine_circuit_breaker_state",
                "Circuit breaker state (0=closed, 1=open, 2=half-open)",
                ["provider"],
            ),
            "stage_latency": _histogram(
                "dataset_engine_stage_duration_seconds",
                "Duration of pipeline stages",
                ["stage"],
            ),
            "filter_rejections": _counter(
                "dataset_engine_filter_rejections_total",
                "Total rejected samples by reason",
                ["reason"],
            ),
            "pipeline_runs": _counter(
                "dataset_engine_pipeline_runs_total",
                "Total pipeline runs by status",
                ["status"],
            ),
            "ws_connections_active": _gauge(
                "dataset_engine_ws_connections_active",
                "Active WebSocket connections",
                ["job_id"],
            ),
            "ws_messages_total": _counter(
                "dataset_engine_ws_messages_total",
                "Total WebSocket messages sent",
                ["event_type"],
            ),
            "queue_depth": _gauge(
                "dataset_engine_queue_depth",
                "Current queue depth",
                ["queue_name"],
            ),
            "provider_cache_size": _gauge(
                "dataset_engine_provider_cache_size",
                "Provider router cache entry count",
                ["provider"],
            ),
            "rejected_jobs": _counter(
                "dataset_engine_rejected_jobs_total",
                "Total jobs rejected by admission control",
                ["reason"],
            ),
            "admission_wait_seconds": _histogram(
                "dataset_engine_admission_wait_seconds",
                "Time jobs spent waiting in admission queue",
                ["priority"],
                buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
            ),
            "job_recovery_attempts": _counter(
                "dataset_engine_job_recovery_attempts_total",
                "Total auto-resume recovery attempts",
                ["outcome"],
            ),
            "backup_duration_seconds": _histogram(
                "dataset_engine_backup_duration_seconds",
                "Duration of backup operations",
                ["backup_type"],
                buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
            ),
            "backup_size_bytes": _gauge(
                "dataset_engine_backup_size_bytes",
                "Size of last backup in bytes",
            ),
        }

    async def initialize(self) -> None:
        """Initialize observability components."""
        if self._is_initialized:
            return

        # Setup structured logging
        self._setup_structured_logging()

        # Setup tracing
        self._setup_tracing()

        # Setup metrics
        self._setup_metrics_export()

        self._is_initialized = True
        logging.getLogger(__name__).info("Observability initialized")

    def _setup_structured_logging(self) -> None:
        """Configure enterprise-grade structured logging."""
        log_level = os.getenv("LOG_LEVEL", "INFO")

        # Custom renderer that includes correlation IDs
        def add_correlation_fields(
            logger: logging.Logger,
            method_name: str,
            event_dict: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Add correlation and trace context to log output."""
            # Get correlation IDs from context
            correlation_id = correlation_id_var.get()
            trace_id = trace_id_var.get()
            span_id = span_id_var.get()

            if correlation_id:
                event_dict["correlation_id"] = correlation_id
            if trace_id:
                event_dict["trace_id"] = trace_id
            if span_id:
                event_dict["span_id"] = span_id

            # Add service info
            event_dict["service"] = "ai-dataset-engineer"
            event_dict["environment"] = os.getenv("AI_DATASET_ENVIRONMENT", "development")

            return event_dict

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                add_correlation_fields,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    def _setup_tracing(self) -> None:
        """Configure OpenTelemetry tracing."""
        if not OPENTELEMETRY_AVAILABLE:
            logging.getLogger(__name__).debug("OpenTelemetry not available — skipping tracing setup")
            return

        # Create resource with service info
        self._resource = Resource.create({
            SERVICE_NAME: "ai-dataset-engineer",
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("AI_DATASET_ENVIRONMENT", "development"),
        })

        # Create tracer provider
        provider = TracerProvider(resource=self._resource)

        # Add console exporter for development
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Add OTLP exporter if configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            try:
                if otlp_endpoint.startswith("http"):
                    otlp_exporter = HTTPExporter(endpoint=otlp_endpoint)
                else:
                    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            except Exception as e:
                logging.getLogger(__name__).warning(f"OTLP exporter unavailable: {e}")

        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("ai-dataset-engineer")

    def _setup_metrics_export(self) -> None:
        """Setup metrics export."""
        # Prometheus is used via /metrics endpoint
        pass

    def add_span_exporter(self, exporter_type: str) -> None:
        """Add a span exporter."""
        provider = trace.get_tracer_provider()

        if exporter_type == "console":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        elif exporter_type == "otlp":
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            if otlp_endpoint:
                provider.add_span_processor(BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=otlp_endpoint)
                ))

    def get_tracer(self) -> Any:
        """Get the tracer instance."""
        if not OPENTELEMETRY_AVAILABLE:
            return None
        if self._tracer is None:
            self._tracer = trace.get_tracer("ai-dataset-engineer")
        return self._tracer

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics dictionary."""
        return self._metrics

    def log_event(self, event_type: str, message: str, metadata: Dict[str, Any] = None) -> None:
        """Log an event with correlation context."""
        extra = {"event_type": event_type, "metadata": metadata or {}}
        logger.info(message, extra=extra)

    def log_job_event(self, job_id: str, event: str, data: Dict[str, Any] = None) -> None:
        """Log a job event."""
        self.log_event(f"job_{event}", f"Job {job_id}: {event}", data)
        if event in ["pipeline_started", "pipeline_completed", "pipeline_failed"]:
            status_tag = event.replace("pipeline_", "")
            self.record_pipeline_run(status_tag)

    def record_stage_latency(self, stage: str, duration: float) -> None:
        """Record the execution latency of a pipeline stage in Prometheus."""
        if PROMETHEUS_AVAILABLE and "stage_latency" in self._metrics:
            try:
                self._metrics["stage_latency"].labels(stage=stage).observe(duration)
            except Exception as e:
                logger.debug(f"Failed to record stage latency metric: {e}")

    def record_filter_rejection(self, reason: str) -> None:
        """Record a filter rejection count in Prometheus."""
        if PROMETHEUS_AVAILABLE and "filter_rejections" in self._metrics:
            try:
                self._metrics["filter_rejections"].labels(reason=reason).inc()
            except Exception as e:
                logger.debug(f"Failed to record filter rejection metric: {e}")

    def record_pipeline_run(self, status: str) -> None:
        """Record a pipeline run state metric in Prometheus."""
        if PROMETHEUS_AVAILABLE and "pipeline_runs" in self._metrics:
            try:
                self._metrics["pipeline_runs"].labels(status=status).inc()
            except Exception as e:
                logger.debug(f"Failed to record pipeline run metric: {e}")

    def log_pipeline_stage(
        self,
        job_id: str,
        stage: str,
        source_url: str,
        duration_ms: float,
        decision: str,
        quality_score: float = 0.0,
        threshold: float = 0.0,
        issues: list = None,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Log structured telemetry details for a specific pipeline stage execution."""
        # Calculate gap to threshold and determine rejection reason
        gap_to_threshold = quality_score - threshold if threshold > 0 else 0.0
        rejection_reason = None
        if decision == "rejected" and issues:
            rejection_reason = issues[0] if issues else "unknown"
        elif decision == "failed":
            rejection_reason = "processing_error"
        elif decision == "passed":
            rejection_reason = None

        log_payload = {
            "job_id": job_id,
            "stage": stage,
            "source_url": source_url,
            "duration_ms": duration_ms,
            "decision": decision,
            "quality_score": quality_score,
            "threshold": threshold,
            "gap_to_threshold": gap_to_threshold,
            "rejection_reason": rejection_reason,
            "issues": issues or [],
            # ↓ NEW: top-level error field for log aggregators
            "error": issues[0] if issues and decision in ("failed", "rejected") else None,
            "issue_count": len(issues) if issues else 0,
            "timestamp": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        self.log_event(f"pipeline_{stage}", f"Job {job_id} stage {stage}: {decision}", log_payload)

        # Forward stage trace to LangSmith
        if hasattr(self, "langsmith") and self.langsmith:
            self.langsmith.trace_stage(
                job_id=job_id,
                stage_name=stage,
                inputs={"source_url": source_url, "threshold": threshold},
                outputs={"decision": decision, "quality_score": quality_score, "issues": issues},
                duration_ms=duration_ms,
                error=log_payload.get("error")
            )

        # Automatically stream structured telemetry details directly into Prometheus Histograms and Counters
        self.record_stage_latency(stage, duration_ms / 1000.0)
        if stage == "filter" and decision != "passed" and issues:
            for issue in issues:
                self.record_filter_rejection(issue)

    def get_prometheus_metrics(self) -> bytes:
        """Generate and return the latest Prometheus metrics in text format."""
        if PROMETHEUS_AVAILABLE:
            try:
                return generate_latest()
            except Exception as e:
                logger.error(f"Failed to generate Prometheus metrics: {e}")
        return b""

    async def shutdown(self) -> None:
        """Shutdown observability components."""
        if hasattr(trace.get_tracer_provider(), 'shutdown'):
            trace.get_tracer_provider().shutdown()


# Decorator for automatic correlation and tracing
def traced(
    operation_name: str,
    kind: Any = None,
    attributes: Optional[Dict[str, str]] = None
):
    # Use default kind if not provided
    if kind is None:
        kind = SpanKind.INTERNAL if SpanKind else 0
    """Decorator to add tracing to async functions."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get or create correlation ID
            correlation_id = correlation_id_var.get()
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
                correlation_id_var.set(correlation_id)

            # Get tracer
            obs = ObservabilityManager.__new__(ObservabilityManager)
            obs._tracer = None
            tracer = obs.get_tracer()

            # Create span
            with tracer.start_as_current_span(
                operation_name,
                kind=kind,
                attributes={
                    "correlation_id": correlation_id,
                    "operation": operation_name,
                    **(attributes or {})
                }
            ) as span:
                try:
                    # Set trace context for downstream
                    trace_id = format(span.context.trace_id, '032x')
                    span_id = format(span.context.span_id, '016x')
                    trace_id_var.set(trace_id)
                    span_id_var.set(span_id)

                    result = await func(*args, **kwargs)
                    if StatusCode:
                        span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    if StatusCode:
                        span.set_status(Status(StatusCode.ERROR), str(e))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


# Context manager for manual tracing
class TracingContext:
    """Context manager for manual span creation."""

    def __init__(self, name: str, kind: Any = None, attributes: Dict[str, Any] = None):
        self.name = name
        self.kind = kind if kind is not None else (SpanKind.INTERNAL if SpanKind else 0)
        self.attributes = attributes or {}

    async def __aenter__(self):
        obs = ObservabilityManager.__new__(ObservabilityManager)
        obs._tracer = None
        self._tracer = obs.get_tracer()

        self._correlation_id = correlation_id_var.get() or str(uuid.uuid4())
        correlation_id_var.set(self._correlation_id)
        self.attributes["correlation_id"] = self._correlation_id

        self._span = self._tracer.start_span(
            self.name,
            kind=self.kind,
            attributes=self.attributes
        )

        trace_id = format(self._span.context.trace_id, '032x')
        span_id = format(self._span.context.span_id, '016x')
        trace_id_var.set(trace_id)
        span_id_var.set(span_id)

        return self._span

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and StatusCode:
            self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            self._span.record_exception(exc_val)
        self._span.end()


def get_correlation_id() -> str:
    """Get current correlation ID, creating one if not set."""
    correlation_id = correlation_id_var.get()
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
    return correlation_id


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(correlation_id)


def get_trace_context() -> Dict[str, Optional[str]]:
    """Get current trace context."""
    return {
        "correlation_id": correlation_id_var.get(),
        "trace_id": trace_id_var.get(),
        "span_id": span_id_var.get(),
    }


# Convenience function for creating logger with correlation context
def get_logger(name: str) -> logging.Logger:
    """Get a structured logger with correlation context."""
    return structlog.get_logger(name)