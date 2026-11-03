"""Checkpoints module compatibility proxy."""
from core.orchestrator_pkg.checkpoints import (
    CheckpointStage,
    ProviderContext,
    Checkpoint,
    CheckpointStore,
    CheckpointManager,
)

# CheckpointStore provides persistence with local and database support
SQLiteCheckpointStore = CheckpointStore

__all__ = [
    "CheckpointStage",
    "ProviderContext",
    "Checkpoint",
    "CheckpointStore",
    "SQLiteCheckpointStore",
    "CheckpointManager",
]
