"""
Enterprise Observability with OpenTelemetry

Distributed tracing, metrics collection, and structured logging
for AI infrastructure observability.
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from contextvars import ContextVar
import asyncio
import logging
import time
import uuid
import json
from functools import wraps

# OpenTelemetry imports
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
    from opentelemetry.trace import Status, StatusCode, SpanKind
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.context import attach, set_value, get_current
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    metrics = None


logger = logging.getLogger(__name__)


# ============================================================================
# Correlation & Trace Context
# ============================================================================

# Context variables for correlation IDs
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


@dataclass
class TraceContext:
    """Container for distributed trace context."""
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    service_name: str = "ai-dataset-engineer"

    @classmethod
    def from_current(cls) -> "TraceContext":
        """Create TraceContext from current execution context."""
        return cls(
            trace_id=trace_id_var.get(),
            span_id=span_id_var.get(),
            correlation_id=correlation_id_var.get(),
        )

    def to_dict(self) -> Dict[str, str]:
        """Export as dict for propagation."""
        return {
            "trace_id": self.trace_id or "",
            "span_id": self.span_id or "",
            "correlation_id": self.correlation_id or "",
        }

    @classmethod
    def new(cls, service_name: str = "ai-dataset-engineer") -> "TraceContext":
        """Create new trace context with generated IDs."""
        return cls(
            trace_id=generate_trace_id(),
            span_id=generate_span_id(),
            correlation_id=generate_correlation_id(),
            service_name=service_name,
        )


def generate_trace_id() -> str:
    """Generate a 32-character trace ID."""
    return uuid.uuid4().hex[:32]


def generate_span_id() -> str:
    """Generate a 16-character span ID."""
    return uuid.uuid4().hex[:16]


def generate_correlation_id() -> str:
    """Generate a correlation ID for request tracking."""
    return f"corr_{uuid.uuid4().hex[:16]}"


def set_trace_context(context: TraceContext) -> None:
    """Set trace context in current execution context."""
    if context.trace_id:
        trace_id_var.set(context.trace_id)
    if context.span_id:
        span_id_var.set(context.span_id)
    if context.correlation_id:
        correlation_id_var.set(context.correlation_id)


# ============================================================================
# OpenTelemetry Setup
# ============================================================================

class TelemetrySetup:
    """Configures OpenTelemetry tracing and metrics."""

    _instance: Optional["TelemetrySetup"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not TelemetrySetup._initialized and OTEL_AVAILABLE:
            self._setup_tracing()
            self._setup_metrics()
            TelemetrySetup._initialized = True

    def _setup_tracing(self) -> None:
        """Configure distributed tracing."""
        if not OTEL_AVAILABLE:
            logger.warning("OpenTelemetry not available - tracing disabled")
            return

        # Create tracer provider
        provider = TracerProvider()

        # Add console exporter for development
        if logger.level <= logging.DEBUG:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        # Set global provider
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("ai-dataset-engineer")

    def _setup_metrics(self) -> None:
        """Configure metrics collection."""
        if not OTEL_AVAILABLE:
            return

        # Create meter provider with console exporter
        reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(),
            export_interval_millis=60000,
        )
        provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(provider)
        self._meter = metrics.get_meter("ai-dataset-engineer")

    @property
    def tracer(self):
        """Get tracer instance."""
        if OTEL_AVAILABLE and hasattr(self, "_tracer"):
            return self._tracer
        return NoOpTracer()

    @property
    def meter(self):
        """Get meter instance."""
        if OTEL_AVAILABLE and hasattr(self, "_meter"):
            return self._meter
        return NoOpMeter()


class NoOpSpan:
    """No-op span for when OpenTelemetry is unavailable."""
    def __init__(self): pass
    def set_attribute(self, key, value): pass
    def add_event(self, name, attributes=None): pass
    def set_status(self, status): pass
    def record_exception(self, exception): pass
    def end(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


class NoOpTracer:
    """No-op tracer when OpenTelemetry unavailable."""
    def start_span(self, name, kind=None, context=None): return NoOpSpan()
    def start_as_current_span(self, name, kind=None, context=None):
        return NoOpSpan()


class NoOpCounter:
    """No-op counter."""
    def add(self, amount, attributes=None): pass


class NoOpHistogram:
    """No-op histogram."""
    def record(self, amount, attributes=None): pass


class NoOpMeter:
    """No-op meter when OpenTelemetry unavailable."""
    def create_counter(self, name, unit=None, description=None):
        return NoOpCounter()
    def create_histogram(self, name, unit=None, description=None):
        return NoOpHistogram()


# Global telemetry setup
_telemetry: Optional[TelemetrySetup] = None


def get_telemetry() -> TelemetrySetup:
    """Get global telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetrySetup()
    return _telemetry


# ============================================================================
# Structured Logging
# ============================================================================

class StructuredFormatter(logging.Formatter):
    """JSON-structured logging formatter for observability platforms."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace context if available
        ctx = TraceContext.from_current()
        if ctx.trace_id:
            log_data["trace_id"] = ctx.trace_id
        if ctx.correlation_id:
            log_data["correlation_id"] = ctx.correlation_id

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add any structured data in record.__dict__
        for key, value in record.__dict__.items():
            if key not in ("name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "lineno", "module", "msecs", "pathname",
                          "process", "processName", "relativeCreated", "thread",
                          "threadName", "exc_info", "exc_text", "stack_info",
                          "message", "extra_fields"):
                if not key.startswith("_"):
                    log_data[key] = value

        return json.dumps(log_data, default=str)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configure structured JSON logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


# ============================================================================
# Metrics Collection
# ============================================================================

class MetricsCollector:
    """Collects and exposes application metrics."""

    def __init__(self):
        self.telemetry = get_telemetry()
        self._counters: Dict[str, Any] = {}
        self._histograms: Dict[str, Any] = {}
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize standard metrics."""
        meter = self.telemetry.meter

        # Request metrics
        self.request_count = meter.create_counter(
            "http_requests_total",
            unit="1",
            description="Total HTTP requests"
        )
        self.request_duration = meter.create_histogram(
            "http_request_duration_seconds",
            unit="s",
            description="HTTP request duration"
        )

        # Provider metrics
        self.provider_requests = meter.create_counter(
            "provider_requests_total",
            unit="1",
            description="Total provider API requests"
        )
        self.provider_latency = meter.create_histogram(
            "provider_latency_seconds",
            unit="s",
            description="Provider API latency"
        )
        self.provider_errors = meter.create_counter(
            "provider_errors_total",
            unit="1",
            description="Total provider errors"
        )

        # Orchestration metrics
        self.job_count = meter.create_counter(
            "jobs_total",
            unit="1",
            description="Total jobs processed"
        )
        self.job_duration = meter.create_histogram(
            "job_duration_seconds",
            unit="s",
            description="Job processing duration"
        )

        # Cache metrics
        self.cache_hits = meter.create_counter(
            "cache_hits_total",
            unit="1",
            description="Cache hits"
        )
        self.cache_misses = meter.create_counter(
            "cache_misses_total",
            unit="1",
            description="Cache misses"
        )

        # Retry metrics
        self.retry_count = meter.create_counter(
            "retries_total",
            unit="1",
            description="Total retry attempts"
        )

    def record_request(self, method: str, path: str, status: int, duration: float) -> None:
        """Record HTTP request metrics."""
        self.request_count.add(1, {"method": method, "path": path, "status": str(status)})
        self.request_duration.record(duration, {"method": method, "path": path})

    def record_provider_call(
        self,
        provider: str,
        model: str,
        success: bool,
        duration: float,
        tokens: int = 0
    ) -> None:
        """Record provider API call metrics."""
        status = "success" if success else "error"
        self.provider_requests.add(1, {"provider": provider, "model": model, "status": status})
        self.provider_latency.record(duration, {"provider": provider, "model": model})
        if not success:
            self.provider_errors.add(1, {"provider": provider, "model": model})
        if tokens > 0:
            self.provider_requests.add(tokens, {"provider": provider, "type": "tokens"})

    def record_job(self, job_type: str, status: str, duration: float) -> None:
        """Record job processing metrics."""
        self.job_count.add(1, {"type": job_type, "status": status})
        self.job_duration.record(duration, {"type": job_type})

    def record_cache(self, hit: bool) -> None:
        """Record cache hit/miss."""
        if hit:
            self.cache_hits.add(1)
        else:
            self.cache_misses.add(1)

    def record_retry(self, attempt: int, provider: str) -> None:
        """Record retry attempt."""
        self.retry_count.add(1, {"attempt": str(attempt), "provider": provider})

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "requests": {"count": 0, "avg_duration": 0},
                "providers": {},
                "jobs": {},
                "cache": {"hits": 0, "misses": 0, "hit_rate": 0},
            }
        }


# ============================================================================
# Span Decorators
# ============================================================================

def traced(
    name: Optional[str] = None,
    kind: str = "internal",
    attributes: Optional[Dict[str, str]] = None
):
    """Decorator to add tracing to async functions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_telemetry().tracer
            span_name = name or f"{func.__module__}.{func.__name__}"

            with tracer.start_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper
    return decorator


def timed(counter: Optional[Callable] = None, histogram: Optional[Callable] = None):
    """Decorator to time function execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if counter:
                    counter(1)
                if histogram:
                    histogram(duration)

        return wrapper
    return decorator


# ============================================================================
# Request Context Middleware
# ============================================================================

class RequestContextMiddleware:
    """FastAPI middleware for request tracing context."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate trace context
        headers = dict(scope.get("headers", []))
        incoming_trace = headers.get(b"x-trace-id", b"").decode()

        ctx = TraceContext.new()
        if incoming_trace:
            ctx.trace_id = incoming_trace
        else:
            ctx.trace_id = generate_trace_id()

        ctx.correlation_id = headers.get(b"x-correlation-id", b"").decode() or ctx.correlation_id

        # Set in context
        set_trace_context(ctx)

        # Add trace headers to response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message["headers"].extend([
                    (b"x-trace-id", ctx.trace_id.encode()),
                    (b"x-correlation-id", ctx.correlation_id.encode()),
                ])
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ============================================================================
# Audit Logger
# ============================================================================

class AuditLogger:
    """Structured audit logging for compliance and security."""

    def __init__(self, service_name: str = "ai-dataset-engineer"):
        self.service_name = service_name
        self.logger = logging.getLogger(f"audit.{service_name}")

    def log_authentication(
        self,
        user_id: str,
        success: bool,
        method: str,
        ip_address: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log authentication event."""
        self.logger.info(
            "Authentication attempt",
            extra={
                "event_type": "authentication",
                "user_id": user_id,
                "success": success,
                "method": method,
                "ip_address": ip_address,
                **kwargs
            }
        )

    def log_credential_access(
        self,
        user_id: str,
        provider: str,
        action: str,
        success: bool,
        **kwargs
    ) -> None:
        """Log provider credential access."""
        self.logger.info(
            "Credential access",
            extra={
                "event_type": "credential_access",
                "user_id": user_id,
                "provider": provider,
                "action": action,
                "success": success,
                **kwargs
            }
        )

    def log_config_change(
        self,
        user_id: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        **kwargs
    ) -> None:
        """Log configuration change."""
        self.logger.info(
            "Configuration changed",
            extra={
                "event_type": "config_change",
                "user_id": user_id,
                "config_key": config_key,
                "old_value": str(old_value)[:100],
                "new_value": str(new_value)[:100],
                **kwargs
            }
        )

    def log_security_violation(
        self,
        violation_type: str,
        details: str,
        severity: str = "high",
        **kwargs
    ) -> None:
        """Log security violation."""
        self.logger.warning(
            f"Security violation: {violation_type}",
            extra={
                "event_type": "security_violation",
                "violation_type": violation_type,
                "details": details,
                "severity": severity,
                **kwargs
            }
        )

    def log_orchestration_failure(
        self,
        job_id: str,
        stage: str,
        error: str,
        **kwargs
    ) -> None:
        """Log orchestration failure."""
        self.logger.error(
            f"Orchestration failed: {job_id}",
            extra={
                "event_type": "orchestration_failure",
                "job_id": job_id,
                "stage": stage,
                "error": error,
                **kwargs
            }
        )


# Global audit logger
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# ============================================================================
# Health Checks
# ============================================================================

class HealthChecker:
    """Comprehensive health checking for all system components."""

    def __init__(self):
        self._checks: Dict[str, Callable] = {}

    def register_check(self, name: str, check: Callable) -> None:
        """Register a health check."""
        self._checks[name] = check

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        all_healthy = True

        for name, check in self._checks.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    result = await check()
                else:
                    result = check()

                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "healthy": result,
                }
                if not result:
                    all_healthy = False
            except Exception as e:
                results[name] = {
                    "status": "unhealthy",
                    "healthy": False,
                    "error": str(e),
                }
                all_healthy = False

        return {
            "healthy": all_healthy,
            "checks": results,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global health checker
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


# Re-export all public symbols
__all__ = [
    # Trace Context
    "TraceContext",
    "trace_id_var",
    "span_id_var",
    "correlation_id_var",
    "generate_trace_id",
    "generate_span_id",
    "generate_correlation_id",
    "set_trace_context",

    # Setup
    "TelemetrySetup",
    "get_telemetry",
    "setup_structured_logging",

    # Metrics
    "MetricsCollector",

    # Decorators
    "traced",
    "timed",

    # Middleware
    "RequestContextMiddleware",

    # Audit
    "AuditLogger",
    "get_audit_logger",

    # Health
    "HealthChecker",
    "get_health_checker",
]