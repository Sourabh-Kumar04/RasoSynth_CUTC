"""CANONICAL ORCHESTRATOR FACADE - Backward compatibility layer.

This module re-exports the modular components from `core.orchestrator_pkg`.
The monolithic orchestrator has been decomposed into modular submodules under `core/orchestrator_pkg/`:
- `core.orchestrator_pkg.state`: State definitions (AgentState, Job, JobStatus, ConstraintAnalysis)
- `core.orchestrator_pkg.constraint_analyzer`: ConstraintAnalyzer
- `core.orchestrator_pkg.nodes`: Node mixins (preview, discovery, synthesis, evaluation, export, resilience)
- `core.orchestrator_pkg.orchestrator`: DatasetOrchestrator
- `core.orchestrator_pkg.checkpoints`: Checkpoint management
- `core.orchestrator_pkg.resume`: Crash-safe resume and streaming recovery
"""
from __future__ import annotations

import logging
from typing import Any

from core.orchestrator_pkg.state import (
    AgentState,
    Job,
    JobStatus,
    ConstraintAnalysis,
    _sanitize_metadata,
    _json_safe,
)
from core.orchestrator_pkg.constraint_analyzer import ConstraintAnalyzer
from core.orchestrator_pkg.orchestrator import DatasetOrchestrator
from core.orchestrator_pkg.nodes import (
    PreviewNodeMixin,
    DiscoveryNodeMixin,
    SynthesisNodeMixin,
    EvaluationNodeMixin,
    ExportNodeMixin,
    ResilienceNodeMixin,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DatasetOrchestrator",
    "AgentState",
    "Job",
    "JobStatus",
    "ConstraintAnalysis",
    "ConstraintAnalyzer",
    "_sanitize_metadata",
    "_json_safe",
    "PreviewNodeMixin",
    "DiscoveryNodeMixin",
    "SynthesisNodeMixin",
    "EvaluationNodeMixin",
    "ExportNodeMixin",
    "ResilienceNodeMixin",
]


def __getattr__(name: str) -> Any:
    """PEP 562 dynamic attribute lookup fallback to core.orchestrator_pkg."""
    import core.orchestrator_pkg as _pkg
    if hasattr(_pkg, name):
        return getattr(_pkg, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(__all__))
