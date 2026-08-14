"""Core module exports with enterprise reliability patterns."""

from core.config import Settings, get_settings, SecurityError
from core.provider_router import ProviderRouter, TaskType, RouterConfig, RouterStats
# Import from core/orchestrator.py (file, not package)
from core.orchestrator_core import DatasetOrchestrator, AgentState, Job, JobStatus, ConstraintAnalysis
from core.db import AsyncDB, DatabaseManager
from core.cache import CacheManager, ProviderCache
from core.observability_manager import ObservabilityManager
from core.research_loop import ResearchLoop, TechniqueIntegrator

# Resilience Patterns
try:
    from core.resilience import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitState,
        CircuitBreakerOpenError,
        CircuitBreakerManager,
        get_circuit_breaker_manager,
        RetryPolicy,
        get_retry_decorator,
        Bulkhead,
        BulkheadConfig,
        BulkheadRejectedError,
        BulkheadManager,
        get_bulkhead_manager,
        ConnectionPool,
        PoolConfig,
        PooledConnection,
        PoolExhaustedError,
    )
    RESILIENCE_AVAILABLE = True
except ImportError:
    RESILIENCE_AVAILABLE = False

# Pagination & Streaming
try:
    from core.pagination import (
        Cursor,
        PaginationResult,
        StreamProgress,
        BackpressureIterator,
        BatchedAsyncIterator,
        chunked_async_iter,
        paginated_async_iter,
        concurrency_limited_iter,
        create_cursor,
        calculate_pagination,
    )
    PAGINATION_AVAILABLE = True
except ImportError:
    PAGINATION_AVAILABLE = False

__all__ = [
    # Config
    "Settings",
    "get_settings",
    "SecurityError",

    # Router
    "ProviderRouter",
    "TaskType",
    "RouterConfig",
    "RouterStats",

    # Orchestration
    "DatasetOrchestrator",
    "AgentState",
    "Job",
    "JobStatus",
    "ConstraintAnalysis",

    # Database
    "AsyncDB",
    "DatabaseManager",

    # Cache
    "CacheManager",
    "ProviderCache",

    # Observability
    "ObservabilityManager",
    "ResearchLoop",
    "TechniqueIntegrator",
]