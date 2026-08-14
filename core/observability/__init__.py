"""
Observability, Telemetry & Intelligence Layer

Production-grade observability infrastructure for distributed AI systems
with structured logging, distributed tracing, metrics, and AI-native analytics.
"""

# Import ObservabilityManager from the renamed module file
from core.observability_manager import ObservabilityManager

from core.observability.logging import (
    StructuredLogger,
    LogSchema,
    LogLevel,
    LogContext,
    CorrelationManager,
)
from core.observability.tracing import (
    Trace,
    Span,
    TraceContext,
    DistributedTracer,
    AgentTraceAnalyzer,
)
from core.observability.metrics import (
    MetricsCollector,
    MetricTypes,
    GaugeMetrics,
    CounterMetrics,
    HistogramMetrics,
)
from core.observability.gpu import (
    GPUMonitor,
    GPUCollector,
    VRAMTracker,
    InferenceMetrics,
)
from core.observability.ai_analytics import (
    AIAnalyticsEngine,
    ReasoningQualityMonitor,
    HallucinationDetector,
    ConfidenceTracker,
    SemanticDriftDetector,
)
from core.observability.agents import (
    AgentWorkflowObserver,
    AgentCoordinationTracker,
    MultiAgentGraphVisualizer,
)
# Telemetry & correlation
from core.observability.telemetry import (
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
    RequestContextMiddleware,
    AuditLogger,
    get_audit_logger,
    HealthChecker,
    get_health_checker,
    TelemetrySetup,
    get_telemetry,
    setup_structured_logging,
    MetricsCollector,
)
from core.observability.cost import (
    CostTracker,
    CostAnalyzer,
    ProviderCostComparison,
    BudgetMonitor,
)
from core.observability.dashboards import (
    DashboardManager,
    GrafanaExporter,
    PrometheusMetricsServer,
    RealTimeMetricsStream,
    AlertManager,
    AlertRule,
    AlertSeverity,
    NotificationChannel,
    IncidentTracker,
)
from core.observability.pipeline import (
    PipelineTelemetry,
    DatasetLineageTracker,
    ProvenanceGraph,
    QualityTracker,
)

__all__ = [
    # Main
    "ObservabilityManager",

    # Logging
    "StructuredLogger",
    "LogSchema",
    "LogLevel",
    "LogContext",
    "CorrelationManager",

    # Tracing
    "TraceManager",
    "Span",
    "TraceContext",
    "DistributedTracer",
    "AgentTraceAnalyzer",

    # Metrics
    "MetricsCollector",
    "MetricTypes",
    "GaugeMetrics",
    "CounterMetrics",
    "HistogramMetrics",

    # GPU
    "GPUMonitor",
    "GPUCollector",
    "VRAMTracker",
    "InferenceMetrics",

    # AI Analytics
    "AIAnalyticsEngine",
    "ReasoningQualityMonitor",
    "HallucinationDetector",
    "ConfidenceTracker",
    "SemanticDriftDetector",

    # Agent Observability
    "AgentWorkflowObserver",
    "AgentCoordinationTracker",
    "MultiAgentGraphVisualizer",

    # Cost
    "CostTracker",
    "CostAnalyzer",
    "ProviderCostComparison",
    "BudgetMonitor",

    # Dashboards
    "DashboardManager",
    "GrafanaExporter",
    "PrometheusMetricsServer",
    "RealTimeMetricsStream",

    # Alerts
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "NotificationChannel",
    "IncidentTracker",

    # Pipeline
    "PipelineTelemetry",
    "DatasetLineageTracker",
    "ProvenanceGraph",
    "QualityTracker",
]