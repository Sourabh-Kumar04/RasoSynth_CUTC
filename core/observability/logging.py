"""
Structured Logging System

Machine-readable JSON logs with schema enforcement, correlation tracking,
and distributed system observability.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio
import uuid
from contextvars import ContextVar


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogSchema:
    """Schema for structured log entries."""
    timestamp: str
    level: str
    trace_id: str
    span_id: str = ""
    agent_id: str = ""
    workflow_id: str = ""
    job_id: str = ""
    dataset_id: str = ""
    provider: str = ""
    model: str = ""
    task_type: str = ""
    latency_ms: float = 0.0
    gpu_id: str = ""
    token_usage: int = 0
    cost_usd: float = 0.0
    confidence: float = 0.0
    status: str = "success"
    message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), default=str)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "agent_id": self.agent_id,
            "workflow_id": self.workflow_id,
            "job_id": self.job_id,
            "dataset_id": self.dataset_id,
            "provider": self.provider,
            "model": self.model,
            "task_type": self.task_type,
            "latency_ms": self.latency_ms,
            "gpu_id": self.gpu_id,
            "token_usage": self.token_usage,
            "cost_usd": self.cost_usd,
            "confidence": self.confidence,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'LogSchema':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class LogContext:
    """Context for log correlation."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = ""
    agent_id: str = ""
    workflow_id: str = ""
    job_id: str = ""
    dataset_id: str = ""
    parent_trace_id: str = ""
    correlation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def child_span(self) -> 'LogContext':
        """Create a child span context."""
        return LogContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            workflow_id=self.workflow_id,
            job_id=self.job_id,
            dataset_id=self.dataset_id,
            parent_trace_id=self.trace_id,
            correlation_id=self.correlation_id,
            metadata=dict(self.metadata),
        )


# Context variable for request-scoped logging
_log_context: ContextVar[Optional[LogContext]] = ContextVar('log_context', default=None)


class StructuredLogger:
    """Production-grade structured logger."""

    def __init__(
        self,
        name: str,
        output_handler: Optional[Callable] = None,
        min_level: LogLevel = LogLevel.INFO
    ):
        self.name = name
        self.output_handler = output_handler or self._default_handler
        self.min_level = min_level
        self._handlers: List[Callable] = []
        self._filters: List[Callable] = []
        self._log_history: List[LogSchema] = []
        self._max_history = 10000

    def add_handler(self, handler: Callable) -> None:
        """Add a log handler."""
        self._handlers.append(handler)

    def add_filter(self, filter_fn: Callable) -> None:
        """Add a log filter."""
        self._filters.append(filter_fn)

    async def log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[LogContext] = None,
        **kwargs
    ) -> LogSchema:
        """Log a structured message."""
        if level.value < self.min_level.value:
            return None

        # Get context from variable if not provided
        if context is None:
            context = _log_context.get() or LogContext()

        schema = LogSchema(
            timestamp=datetime.utcnow().isoformat(),
            level=level.name,
            trace_id=context.trace_id,
            span_id=context.span_id,
            agent_id=context.agent_id,
            workflow_id=context.workflow_id,
            job_id=context.job_id,
            dataset_id=context.dataset_id,
            message=message,
            **kwargs
        )

        # Apply filters
        for filter_fn in self._filters:
            if not filter_fn(schema):
                return None

        # Store in history
        self._log_history.append(schema)
        if len(self._log_history) > self._max_history:
            self._log_history = self._log_history[-self._max_history:]

        # Invoke handlers
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(schema)
                else:
                    handler(schema)
            except Exception:
                pass

        await self.output_handler(schema)
        return schema

    async def debug(self, message: str, context: Optional[LogContext] = None, **kwargs) -> None:
        """Log debug message."""
        await self.log(LogLevel.DEBUG, message, context, **kwargs)

    async def info(self, message: str, context: Optional[LogContext] = None, **kwargs) -> None:
        """Log info message."""
        await self.log(LogLevel.INFO, message, context, **kwargs)

    async def warning(self, message: str, context: Optional[LogContext] = None, **kwargs) -> None:
        """Log warning message."""
        await self.log(LogLevel.WARNING, message, context, **kwargs)

    async def error(self, message: str, context: Optional[LogContext] = None, error: Optional[str] = None, **kwargs) -> None:
        """Log error message."""
        await self.log(LogLevel.ERROR, message, context, error=error, **kwargs)

    async def critical(self, message: str, context: Optional[LogContext] = None, error: Optional[str] = None, **kwargs) -> None:
        """Log critical message."""
        await self.log(LogLevel.CRITICAL, message, context, error=error, status="critical", **kwargs)

    async def _default_handler(self, schema: LogSchema) -> None:
        """Default output handler - prints JSON."""
        print(schema.to_json())

    def get_history(
        self,
        trace_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        level: Optional[LogLevel] = None,
        limit: int = 100
    ) -> List[LogSchema]:
        """Query log history."""
        results = self._log_history

        if trace_id:
            results = [r for r in results if r.trace_id == trace_id]
        if agent_id:
            results = [r for r in results if r.agent_id == agent_id]
        if level:
            results = [r for r in results if r.level == level.name]

        return results[-limit:]

    def set_context(self, context: LogContext) -> None:
        """Set the current log context."""
        _log_context.set(context)

    def clear_context(self) -> None:
        """Clear the current log context."""
        _log_context.set(None)

    def get_stats(self) -> Dict[str, Any]:
        """Get logger statistics."""
        by_level = {}
        for log in self._log_history:
            by_level[log.level] = by_level.get(log.level, 0) + 1

        return {
            "total_logs": len(self._log_history),
            "by_level": by_level,
            "handlers_count": len(self._handlers),
            "filters_count": len(self._filters),
        }


class CorrelationManager:
    """Manages correlation IDs across distributed systems."""

    def __init__(self):
        self._correlations: Dict[str, Dict] = {}
        self._parent_child_map: Dict[str, List[str]] = {}

    def create_correlation(
        self,
        trace_id: str,
        parent_trace_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> LogContext:
        """Create a new correlation context."""
        context = LogContext(
            trace_id=trace_id,
            correlation_id=trace_id,
            metadata=metadata or {}
        )

        self._correlations[trace_id] = {
            "created_at": datetime.utcnow(),
            "parent_trace_id": parent_trace_id,
            "metadata": metadata or {},
            "spans": []
        }

        if parent_trace_id and parent_trace_id in self._parent_child_map:
            self._parent_child_map[parent_trace_id].append(trace_id)
        elif parent_trace_id:
            self._parent_child_map[parent_trace_id] = [trace_id]

        return context

    def link_spans(self, parent_span_id: str, child_span_id: str) -> None:
        """Link parent and child spans."""
        if parent_span_id not in self._correlations:
            self._correlations[parent_span_id] = {"spans": []}
        self._correlations[parent_span_id]["spans"].append(child_span_id)

    def get_trace_tree(self, trace_id: str) -> Dict:
        """Get the trace tree for a trace."""
        def build_tree(tid: str, depth: int = 0) -> Dict:
            data = self._correlations.get(tid, {})
            children = self._parent_child_map.get(tid, [])
            return {
                "trace_id": tid,
                "depth": depth,
                "children": [build_tree(cid, depth + 1) for cid in children],
                "spans": data.get("spans", []),
                "metadata": data.get("metadata", {})
            }

        return build_tree(trace_id)

    def get_duration(self, trace_id: str) -> float:
        """Calculate total trace duration."""
        trace = self.get_trace_tree(trace_id)
        return self._calculate_tree_duration(trace)

    def _calculate_tree_duration(self, tree: Dict) -> float:
        """Calculate duration of trace tree."""
        max_duration = 0
        for child in tree.get("children", []):
            child_duration = self._calculate_tree_duration(child)
            max_duration = max(max_duration, child_duration)
        return max_duration


class MultiLayerLogger:
    """Logger that writes to multiple outputs."""

    def __init__(self):
        self._loggers: Dict[str, StructuredLogger] = {}
        self._writers: List[Callable] = []

    def create_logger(self, name: str, **kwargs) -> StructuredLogger:
        """Create a named logger."""
        logger = StructuredLogger(name, **kwargs)
        self._loggers[name] = logger
        return logger

    def get_logger(self, name: str) -> Optional[StructuredLogger]:
        """Get logger by name."""
        return self._loggers.get(name)

    def add_writer(self, writer: Callable) -> None:
        """Add a multi-logger writer."""
        self._writers.append(writer)

    async def log_all(
        self,
        level: LogLevel,
        message: str,
        context: Optional[LogContext] = None,
        **kwargs
    ) -> None:
        """Log to all registered loggers."""
        for logger in self._loggers.values():
            await logger.log(level, message, context, **kwargs)


# Global logger instance
_global_logger: Optional[MultiLayerLogger] = None


def get_global_logger() -> MultiLayerLogger:
    """Get the global logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = MultiLayerLogger()
    return _global_logger