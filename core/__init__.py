"""Core module exports with enterprise reliability patterns."""
from __future__ import annotations

import importlib
from typing import Any

_ATTR_TO_MODULE = {
    # Config
    "Settings": "core.config",
    "get_settings": "core.config",
    "SecurityError": "core.config",
    # Router
    "ProviderRouter": "core.provider_router",
    "TaskType": "core.provider_router",
    "RouterConfig": "core.provider_router",
    "RouterStats": "core.provider_router",
    # Orchestration
    "DatasetOrchestrator": "core.orchestrator_core",
    "AgentState": "core.orchestrator_core",
    "Job": "core.orchestrator_core",
    "JobStatus": "core.orchestrator_core",
    "ConstraintAnalysis": "core.orchestrator_core",
    # Database
    "AsyncDB": "core.db",
    "DatabaseManager": "core.db",
    # Cache
    "CacheManager": "core.cache",
    "ProviderCache": "core.cache",
    # Observability
    "ObservabilityManager": "core.observability_manager",
    "ResearchLoop": "core.research_loop",
    "TechniqueIntegrator": "core.research_loop",
}

_review_service_instance = None
RESILIENCE_AVAILABLE = True
PAGINATION_AVAILABLE = True

__all__ = list(_ATTR_TO_MODULE.keys())


def __getattr__(name: str) -> Any:
    if name in _ATTR_TO_MODULE:
        mod = importlib.import_module(_ATTR_TO_MODULE[name])
        val = getattr(mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
