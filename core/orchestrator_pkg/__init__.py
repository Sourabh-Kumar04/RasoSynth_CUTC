"""Orchestrator package with modular nodes, checkpoints, and resume support.

Decomposed modular architecture:
- `core.orchestrator_pkg.state`: AgentState, Job, JobStatus, ConstraintAnalysis
- `core.orchestrator_pkg.constraint_analyzer`: ConstraintAnalyzer
- `core.orchestrator_pkg.nodes`: Preview, Discovery, Synthesis, Evaluation, Export, Resilience mixins
- `core.orchestrator_pkg.orchestrator`: DatasetOrchestrator
- `core.orchestrator_pkg.checkpoints`: Checkpoint management
- `core.orchestrator_pkg.resume`: Crash-safe resume and streaming recovery
"""
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
from core.orchestrator_pkg.checkpoints import (
    Checkpoint,
    CheckpointStage,
    ProviderContext,
    CheckpointStore,
    CheckpointManager,
)
from core.orchestrator_pkg.resume import (
    ResumeStrategy,
    ResumeContext,
    WorkflowResumer,
    MultiProviderContinuation,
    StreamingRecoveryManager,
    RecoveryOrchestrator,
)

__all__ = [
    "DatasetOrchestrator",
    "AgentState",
    "Job",
    "JobStatus",
    "ConstraintAnalysis",
    "ConstraintAnalyzer",
    "_sanitize_metadata",
    "_json_safe",
    "Checkpoint",
    "CheckpointStage",
    "ProviderContext",
    "CheckpointStore",
    "CheckpointManager",
    "ResumeStrategy",
    "ResumeContext",
    "WorkflowResumer",
    "MultiProviderContinuation",
    "StreamingRecoveryManager",
    "RecoveryOrchestrator",
]
