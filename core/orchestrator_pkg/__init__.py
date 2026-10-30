"""Orchestrator package with checkpoint and resume support.

Canonical home of DatasetOrchestrator and orchestrator state is
core.orchestrator_core; this package re-exports the identical objects alongside
checkpoint and resume management.
"""
from core.orchestrator_core import (
    DatasetOrchestrator,
    AgentState,
    Job,
    JobStatus,
    ConstraintAnalysis,
)

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
    # Canonical home: core.orchestrator_core
    "DatasetOrchestrator",
    "AgentState",
    "Job",
    "JobStatus",
    "ConstraintAnalysis",
    # Checkpoint: core.orchestrator_pkg.checkpoints
    "Checkpoint",
    "CheckpointStage",
    "ProviderContext",
    "CheckpointStore",
    "CheckpointManager",
    # Resume: core.orchestrator_pkg.resume
    "ResumeStrategy",
    "ResumeContext",
    "WorkflowResumer",
    "MultiProviderContinuation",
    "StreamingRecoveryManager",
    "RecoveryOrchestrator",
]