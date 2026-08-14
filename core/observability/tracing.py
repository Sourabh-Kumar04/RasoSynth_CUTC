"""
Distributed Tracing System

End-to-end distributed tracing with OpenTelemetry support, span management,
and AI workflow introspection.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import uuid
from contextvars import ContextVar


class SpanStatus(Enum):
    """Span execution status."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class Span:
    """A trace span."""
    span_id: str
    trace_id: str
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    parent_span_id: Optional[str] = None
    span_type: str = ""
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)
    links: List[Dict] = field(default_factory=list)
    resource: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.span_id:
            self.span_id = str(uuid.uuid4())

    def duration_ms(self) -> float:
        """Calculate span duration."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.utcnow() - self.start_time).total_seconds() * 1000

    def add_attribute(self, key: str, value: Any) -> None:
        """Add an attribute to the span."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict] = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {}
        })

    def set_status(self, status: SpanStatus, message: str = "") -> None:
        """Set span status."""
        self.status = status
        if message:
            self.attributes["status_message"] = message

    def finish(self) -> None:
        """Finish the span."""
        self.end_time = datetime.utcnow()
        if self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "parent_span_id": self.parent_span_id,
            "span_type": self.span_type,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": self.events,
            "links": self.links,
            "resource": self.resource,
            "duration_ms": self.duration_ms(),
        }


@dataclass
class TraceContext:
    """Context for distributed tracing."""
    trace_id: str
    span_id: str = ""
    trace_flags: int = 1
    trace_state: Dict[str, str] = field(default_factory=dict)
    baggage: Dict[str, str] = field(default_factory=dict)

    def child(self) -> 'TraceContext':
        """Create a child context."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            trace_flags=self.trace_flags,
            trace_state=dict(self.trace_state),
            baggage=dict(self.baggage)
        )


@dataclass
class Trace:
    """A complete trace."""
    trace_id: str
    spans: List[Span] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def total_duration_ms(self) -> float:
        """Calculate total trace duration."""
        if not self.spans:
            return 0.0

        start = min(s.start_time for s in self.spans)
        end = max(s.end_time or datetime.utcnow() for s in self.spans)
        return (end - start).total_seconds() * 1000

    def get_span(self, span_id: str) -> Optional[Span]:
        """Get span by ID."""
        for span in self.spans:
            if span.span_id == span_id:
                return span
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.total_duration_ms(),
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }


# Context variable for tracing
_trace_context: ContextVar[Optional[TraceContext]] = ContextVar('trace_context', default=None)


class DistributedTracer:
    """Distributed tracing manager."""

    def __init__(self, service_name: str = "ai-dataset-engineer"):
        self.service_name = service_name
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}
        self._exporters: List[Callable] = []
        self._samplers: List[Callable] = []
        self._max_traces = 1000

    def add_exporter(self, exporter: Callable) -> None:
        """Add a trace exporter."""
        self._exporters.append(exporter)

    def add_sampler(self, sampler: Callable) -> None:
        """Add a sampler."""
        self._samplers.append(sampler)

    def should_sample(self, trace_id: str) -> bool:
        """Check if trace should be sampled."""
        for sampler in self._samplers:
            if not sampler(trace_id):
                return False
        return True

    def start_trace(self, trace_id: Optional[str] = None) -> str:
        """Start a new trace."""
        trace_id = trace_id or str(uuid.uuid4())

        trace = Trace(trace_id=trace_id)
        self._traces[trace_id] = trace

        # Clean up old traces
        if len(self._traces) > self._max_traces:
            oldest = min(self._traces.keys())
            del self._traces[oldest]

        return trace_id

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        span_type: str = "",
        attributes: Optional[Dict] = None
    ) -> Span:
        """Start a new span."""
        trace_id = trace_id or _trace_context.get() and _trace_context.get().trace_id or str(uuid.uuid4())

        # Create trace if doesn't exist
        if trace_id not in self._traces:
            self._traces[trace_id] = Trace(trace_id=trace_id)

        span = Span(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            name=name,
            start_time=datetime.utcnow(),
            parent_span_id=parent_span_id,
            span_type=span_type,
            attributes=attributes or {},
            resource={"service.name": self.service_name}
        )

        self._traces[trace_id].spans.append(span)
        self._active_spans[span.span_id] = span

        return span

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK) -> None:
        """End a span."""
        span.finish()
        span.set_status(status)

        if span.span_id in self._active_spans:
            del self._active_spans[span.span_id]

        # Export trace
        for exporter in self._exporters:
            try:
                if asyncio.iscoroutinefunction(exporter):
                    asyncio.create_task(exporter(span))
                else:
                    exporter(span)
            except Exception:
                pass

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get trace by ID."""
        return self._traces.get(trace_id)

    def get_span_tree(self, trace_id: str) -> Dict:
        """Get trace as a tree structure."""
        trace = self._traces.get(trace_id)
        if not trace:
            return {}

        # Build span tree
        span_map = {s.span_id: s for s in trace.spans}
        children_map: Dict[str, List] = {}

        for span in trace.spans:
            if span.parent_span_id:
                if span.parent_span_id not in children_map:
                    children_map[span.parent_span_id] = []
                children_map[span.parent_span_id].append(span)

        def build_tree(span_id: str, depth: int = 0) -> Dict:
            span = span_map.get(span_id)
            if not span:
                return {}
            return {
                "span_id": span_id,
                "name": span.name,
                "type": span.span_type,
                "duration_ms": span.duration_ms(),
                "depth": depth,
                "status": span.status.value,
                "children": [build_tree(s.span_id, depth + 1) for s in children_map.get(span_id, [])]
            }

        root_spans = [s for s in trace.spans if not s.parent_span_id]
        return {
            "trace_id": trace_id,
            "total_spans": len(trace.spans),
            "duration_ms": trace.total_duration_ms(),
            "roots": [build_tree(s.span_id) for s in root_spans]
        }

    def link_traces(self, parent_trace_id: str, child_trace_id: str) -> None:
        """Link parent and child traces."""
        parent = self._traces.get(parent_trace_id)
        child = self._traces.get(child_trace_id)

        if parent and child:
            parent.metadata["child_traces"] = parent.metadata.get("child_traces", []) + [child_trace_id]
            child.metadata["parent_trace"] = parent_trace_id


class AgentTraceAnalyzer:
    """Analyzes agent execution traces."""

    def __init__(self, tracer: DistributedTracer):
        self.tracer = tracer

    def analyze_agent_execution(self, trace_id: str) -> Dict[str, Any]:
        """Analyze agent execution trace."""
        trace = self.tracer.get_trace(trace_id)
        if not trace:
            return {}

        spans_by_type: Dict[str, List[Span]] = {}
        for span in trace.spans:
            span_type = span.span_type or "unknown"
            if span_type not in spans_by_type:
                spans_by_type[span_type] = []
            spans_by_type[span_type].append(span)

        analysis = {
            "trace_id": trace_id,
            "total_spans": len(trace.spans),
            "total_duration_ms": trace.total_duration_ms(),
            "by_type": {}
        }

        for span_type, spans in spans_by_type.items():
            durations = [s.duration_ms() for s in spans]
            analysis["by_type"][span_type] = {
                "count": len(spans),
                "avg_duration_ms": sum(durations) / max(len(durations), 1),
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
            }

        return analysis

    def find_bottlenecks(self, trace_id: str, threshold_ms: float = 1000) -> List[Dict]:
        """Find execution bottlenecks."""
        trace = self.tracer.get_trace(trace_id)
        if not trace:
            return []

        bottlenecks = []
        for span in trace.spans:
            if span.duration_ms() > threshold_ms:
                bottlenecks.append({
                    "span_id": span.span_id,
                    "name": span.name,
                    "type": span.span_type,
                    "duration_ms": span.duration_ms(),
                    "attributes": span.attributes
                })

        return sorted(bottlenecks, key=lambda x: x["duration_ms"], reverse=True)

    def get_agent_timeline(self, trace_id: str, agent_id: str) -> List[Dict]:
        """Get agent execution timeline."""
        trace = self.tracer.get_trace(trace_id)
        if not trace:
            return []

        timeline = []
        for span in trace.spans:
            if span.attributes.get("agent_id") == agent_id:
                timeline.append({
                    "span_id": span.span_id,
                    "name": span.name,
                    "start": span.start_time.isoformat(),
                    "end": span.end_time.isoformat() if span.end_time else None,
                    "duration_ms": span.duration_ms(),
                    "status": span.status.value
                })

        return sorted(timeline, key=lambda x: x["start"])


class OpenTelemetryIntegration:
    """OpenTelemetry compatibility layer."""

    def __init__(self, service_name: str = "ai-dataset-engineer"):
        self.service_name = service_name
        self.tracer = DistributedTracer(service_name)

    async def export_to_otel(self, trace: Trace) -> Dict:
        """Export trace in OpenTelemetry format."""
        return {
            "resourceSpans": [{
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": self.service_name}}
                    ]
                },
                "scopeSpans": [{
                    "spans": [self._span_to_otel(s) for s in trace.spans]
                }]
            }]
        }

    def _span_to_otel(self, span: Span) -> Dict:
        """Convert span to OpenTelemetry format."""
        return {
            "traceId": span.trace_id,
            "spanId": span.span_id,
            "parentSpanId": span.parent_span_id or "",
            "name": span.name,
            "kind": "SPAN_KIND_INTERNAL",
            "startTimeUnixNano": int(span.start_time.timestamp() * 1e9),
            "endTimeUnixNano": int(span.end_time.timestamp() * 1e9) if span.end_time else 0,
            "attributes": [
                {"key": k, "value": {"stringValue": str(v)}}
                for k, v in span.attributes.items()
            ],
            "status": {"code": span.status.value.upper()},
        }