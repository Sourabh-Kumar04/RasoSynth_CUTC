"""
Resumable Workflow Runtime

Provides workflow resumption from checkpoints,
multi-provider continuation, and partial replay.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class ResumeStrategy(str, Enum):
    """Strategies for resuming workflow."""
    LATEST_CHECKPOINT = "latest_checkpoint"
    SPECIFIC_CHECKPOINT = "specific_checkpoint"
    FROM_STAGE = "from_stage"
    PARTIAL_REPLAY = "partial_replay"


@dataclass
class ResumeContext:
    """Context for resuming a workflow."""
    job_id: str
    strategy: ResumeStrategy
    checkpoint_id: Optional[str] = None
    stage: Optional[str] = None
    from_task: Optional[int] = None
    to_task: Optional[int] = None


class WorkflowResumer:
    """
    Resumes workflows from checkpoints with full state restoration.
    """

    def __init__(
        self,
        checkpoint_manager,  # CheckpointManager
        provider_router,     # ProviderRouter
    ):
        self.checkpoint_manager = checkpoint_manager
        self.provider_router = provider_router

    async def resume_from_checkpoint(
        self,
        job_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resume workflow from checkpoint.

        Returns:
            Dictionary with:
            - provider to use
            - stage to continue from
            - state data
            - samples to continue from
        """

        # Get checkpoint to resume from
        if checkpoint_id:
            checkpoint = await self.checkpoint_manager.store.get_by_id(checkpoint_id)
        else:
            checkpoint = await self.checkpoint_manager.get_resume_checkpoint(job_id)

        if not checkpoint:
            logger.warning(f"No checkpoint found for job {job_id}")
            return None

        # Restore provider context
        provider_context = checkpoint.provider_context
        if provider_context:
            # Configure router to use the checkpoint's provider
            if hasattr(self.provider_router, 'set_active_provider'):
                await self.provider_router.set_active_provider(provider_context.provider_name)

        # Determine resume point based on stage
        resume_stage = self._get_resume_stage(checkpoint.stage)

        logger.info(
            f"Resuming job {job_id} from checkpoint {checkpoint.checkpoint_id} "
            f"at stage {resume_stage} with {checkpoint.samples_generated} samples"
        )

        return {
            "checkpoint_id": checkpoint.checkpoint_id,
            "resume_stage": resume_stage,
            "progress": checkpoint.progress,
            "samples_generated": checkpoint.samples_generated,
            "provider_name": provider_context.provider_name if provider_context else None,
            "extracted_content": checkpoint.extracted_content,
            "filtered_samples": checkpoint.filtered_samples,
            "constructed_samples": checkpoint.constructed_samples,
            "metadata": checkpoint.metadata,
        }

    def _get_resume_stage(self, checkpoint_stage: str) -> str:
        """Map checkpoint stage to execution stage."""
        stage_map = {
            "discovery": "continue_extraction",
            "extraction": "continue_filtering",
            "filtering": "continue_construction",
            "construction": "continue_export",
            "export": "finalize",
            "completed": "complete",
        }
        return stage_map.get(checkpoint_stage, "start")

    async def resume_from_stage(
        self,
        job_id: str,
        stage: str,
    ) -> Optional[Dict[str, Any]]:
        """Resume from a specific stage (not checkpoint)."""

        checkpoint = await self.checkpoint_manager.get_resume_checkpoint(job_id)
        if not checkpoint:
            return None

        # Find closest checkpoint to requested stage
        # For simplicity, return the latest checkpoint but note the stage

        return {
            "resume_stage": stage,
            "checkpoint_id": checkpoint.checkpoint_id,
            "samples_to_replay": checkpoint.samples_generated,
            "continue_from_samples": checkpoint.samples_generated,
        }

    async def replay_partial(
        self,
        job_id: str,
        from_task: int,
        to_task: int,
    ) -> Optional[Dict[str, Any]]:
        """Replay specific tasks in the workflow."""

        checkpoint = await self.checkpoint_manager.get_resume_checkpoint(job_id)
        if not checkpoint:
            return None

        # Get tasks in range
        # This would typically load task list and filter

        return {
            "resume_stage": "partial_replay",
            "from_task": from_task,
            "to_task": to_task,
            "checkpoint_id": checkpoint.checkpoint_id,
            "replay_samples": checkpoint.extracted_content[from_task:to_task],
        }


class MultiProviderContinuation:
    """
    Handles continuation across multiple providers.

    Example: Gemini -> Claude -> DeepSeek -> Ollama
    Preserves outputs and adapts between providers.
    """

    def __init__(self, provider_registry, migration_adapter):
        self.provider_registry = provider_registry
        self.migration_adapter = migration_adapter

        # Track provider chain used for each job
        self.provider_chains: Dict[str, List[str]] = {}

    async def continue_with_provider(
        self,
        job_id: str,
        current_provider: str,
        new_provider: str,
        existing_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Continue execution with a new provider, adapting outputs.

        Returns:
            Adapted context for the new provider
        """

        # Record chain
        if job_id not in self.provider_chains:
            self.provider_chains[job_id] = []
        self.provider_chains[job_id].append(new_provider)

        # Check provider capabilities
        new_capabilities = await self._get_provider_capabilities(new_provider)

        # Adapt outputs based on new provider's capabilities
        adapted_outputs = await self.migration_adapter.adapt_outputs(
            existing_outputs,
            current_provider,
            new_provider,
        )

        logger.info(
            f"Provider continuation: {job_id} using {new_provider} "
            f"(chain: {self.provider_chains[job_id]})"
        )

        return {
            "new_provider": new_provider,
            "adapted_outputs": adapted_outputs,
            "capabilities": new_capabilities,
            "chain": self.provider_chains[job_id],
        }

    async def _get_provider_capabilities(self, provider: str) -> List[str]:
        """Get capabilities of a provider."""
        # Would query provider registry
        return []

    def get_provider_chain(self, job_id: str) -> List[str]:
        """Get provider chain used for a job."""
        return self.provider_chains.get(job_id, [])


class StreamingRecoveryManager:
    """
    Manages recovery for streaming/SSE workflows.

    Handles:
    - Stream disconnection and reconnection
    - Event offset tracking
    - Deduplication on replay
    - Partial chunk handling
    """

    def __init__(self):
        # Track streaming state per job
        self.stream_states: Dict[str, Dict[str, Any]] = {}

    async def track_event(
        self,
        job_id: str,
        event_index: int,
        event_data: Dict[str, Any],
    ) -> None:
        """Track streaming event for potential recovery."""

        if job_id not in self.stream_states:
            self.stream_states[job_id] = {
                "events": [],
                "last_index": -1,
                "last_timestamp": None,
            }

        state = self.stream_states[job_id]
        state["events"].append({
            "index": event_index,
            "data": event_data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        state["last_index"] = event_index
        state["last_timestamp"] = datetime.utcnow()

    async def get_last_event_index(self, job_id: str) -> int:
        """Get index of last processed event."""
        state = self.stream_states.get(job_id)
        if state:
            return state["last_index"]
        return -1

    async def reconnect(
        self,
        job_id: str,
        last_processed_index: int,
    ) -> Optional[int]:
        """
        Handle reconnection after disconnect.

        Returns: index to resume from
        """

        state = self.stream_states.get(job_id)
        if not state:
            return 0

        # Resume from last processed + 1
        resume_index = last_processed_index + 1

        # Check if we have buffered events
        if len(state["events"]) > resume_index:
            logger.info(f"Reconnecting job {job_id} from buffered event {resume_index}")
            return resume_index

        # Otherwise, request replay from server
        return resume_index

    async def deduplicate_events(
        self,
        job_id: str,
        new_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Remove duplicate events after replay."""

        state = self.stream_states.get(job_id)
        if not state:
            return new_events

        existing_indices = {e["index"] for e in state["events"]}
        return [e for e in new_events if e.get("index", 0) not in existing_indices]

    async def handle_partial_chunk(
        self,
        job_id: str,
        chunk: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle partially received chunk."""

        # Store incomplete chunk
        if job_id not in self.stream_states:
            self.stream_states[job_id] = {"partial_chunks": []}

        self.stream_states[job_id]["partial_chunks"].append(chunk)

        # Check if chunk is now complete
        if chunk.get("is_complete"):
            # Combine partial chunks
            combined = self._combine_partial_chunks(job_id)
            return combined

        return None

    def _combine_partial_chunks(self, job_id: str) -> Dict[str, Any]:
        """Combine stored partial chunks into complete event."""
        state = self.stream_states.get(job_id, {})
        chunks = state.get("partial_chunks", [])

        combined = {
            "content": "".join(c.get("content", "") for c in chunks),
            "is_complete": True,
        }

        # Clear partial chunks
        state["partial_chunks"] = []

        return combined


class RecoveryOrchestrator:
    """
    High-level recovery orchestration.

    Coordinates:
    - Checkpoint-based resumption
    - Provider hot-switching
    - Streaming recovery
    - Multi-provider continuation
    """

    def __init__(
        self,
        checkpoint_manager,
        provider_router,
        failover_engine,
    ):
        self.checkpoint_manager = checkpoint_manager
        self.provider_router = provider_router
        self.failover_engine = failover_engine

        self.resumer = WorkflowResumer(checkpoint_manager, provider_router)
        self.streaming_recovery = StreamingRecoveryManager()

    async def recover_job(
        self,
        job_id: str,
        reason: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Main recovery entry point.

        Handles various recovery scenarios:
        - Provider failure
        - Quota exhaustion
        - Manual restart
        - Streaming disconnect
        """

        logger.info(f"Starting recovery for job {job_id}, reason: {reason}")

        # Determine recovery strategy
        if reason == "streaming_disconnect":
            # Handle streaming recovery
            resume_data = await self._recover_streaming(job_id)
        elif checkpoint_id or reason in ["provider_failover", "quota_exhausted"]:
            # Use checkpoint-based recovery
            resume_data = await self.resumer.resume_from_checkpoint(job_id, checkpoint_id)
        else:
            # Default: try latest checkpoint
            resume_data = await self.resumer.resume_from_checkpoint(job_id)

        if resume_data:
            logger.info(f"Recovery successful for job {job_id}")
            return resume_data
        else:
            logger.warning(f"No recovery path for job {job_id}")
            return None

    async def _recover_streaming(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Handle streaming-specific recovery."""
        last_index = await self.streaming_recovery.get_last_event_index(job_id)
        resume_index = await self.streaming_recovery.reconnect(job_id, last_index)

        return {
            "resume_stage": "streaming",
            "resume_from_event": resume_index,
            "stream_state": self.streaming_recovery.stream_states.get(job_id),
        }

    async def get_recovery_status(self, job_id: str) -> Dict[str, Any]:
        """Get current recovery status for a job."""

        # Get checkpoint
        checkpoint = await self.checkpoint_manager.get_resume_checkpoint(job_id)

        # Get migration history
        migrations = self.failover_engine.get_migration_history(job_id)

        return {
            "has_checkpoint": checkpoint is not None,
            "checkpoint_id": checkpoint.checkpoint_id if checkpoint else None,
            "progress": checkpoint.progress if checkpoint else 0,
            "migration_count": len(migrations),
            "migrations": [
                {
                    "from": m.from_provider,
                    "to": m.to_provider,
                    "timestamp": m.timestamp.isoformat(),
                    "success": m.success,
                }
                for m in migrations[-5:]  # Last 5 migrations
            ],
        }