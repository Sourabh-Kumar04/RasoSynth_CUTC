"""
Pipeline Checkpointing - Fault tolerance and resumable execution

Distributed pipeline checkpointing for fault tolerance, partial workflow
recovery, and resumable execution across distributed agents.
"""

from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import uuid
import pickle


class CheckpointType(Enum):
    """Types of checkpoints."""
    STAGE_COMPLETE = "stage_complete"
    INTERMEDIATE = "intermediate"
    FINAL = "final"
    ERROR_RECOVERY = "error_recovery"


@dataclass
class PipelineCheckpoint:
    """A pipeline execution checkpoint."""
    checkpoint_id: str
    pipeline_id: str
    stage: str
    step_index: int
    checkpoint_type: CheckpointType
    created_at: datetime
    expires_at: datetime
    data: Any
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if checkpoint has expired."""
        return datetime.utcnow() > self.expires_at


@dataclass
class DAGCheckpoint:
    """Checkpoint for DAG-based pipeline execution."""
    dag_id: str
    execution_id: str
    completed_nodes: List[str] = field(default_factory=list)
    pending_nodes: List[str] = field(default_factory=list)
    node_results: Dict[str, Any] = field(default_factory=dict)
    node_states: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    checkpoint_interval_seconds: float = 60.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DAGCheckpointManager:
    """Manages checkpoints for DAG-based pipeline execution."""

    def __init__(
        self,
        redis_client: Any,
        default_ttl_seconds: float = 604800,  # 7 days
        max_checkpoints_per_dag: int = 100
    ):
        self.redis = redis_client
        self.default_ttl = default_ttl_seconds
        self.max_checkpoints = max_checkpoints_per_dag

        self._active_checkpoints: Dict[str, DAGCheckpoint] = {}

    async def create_checkpoint(
        self,
        dag_id: str,
        execution_id: str,
        node_id: str,
        result: Any,
        state: str = "completed"
    ) -> str:
        """Create a checkpoint for DAG node."""
        checkpoint_id = str(uuid.uuid4())

        # Get or create DAG checkpoint
        dag_checkpoint = await self.get_dag_checkpoint(dag_id, execution_id)
        if not dag_checkpoint:
            dag_checkpoint = DAGCheckpoint(
                dag_id=dag_id,
                execution_id=execution_id,
                completed_nodes=[],
                pending_nodes=[]
            )

        # Update checkpoint
        dag_checkpoint.completed_nodes.append(node_id)
        dag_checkpoint.node_results[node_id] = result
        dag_checkpoint.node_states[node_id] = state

        # Save checkpoint
        await self._save_dag_checkpoint(dag_checkpoint)

        # Store individual node result
        result_key = f"checkpoint:dag:{dag_id}:{execution_id}:node:{node_id}"
        await self.redis.setex(
            result_key,
            self.default_ttl,
            pickle.dumps(result)
        )

        return checkpoint_id

    async def get_dag_checkpoint(
        self,
        dag_id: str,
        execution_id: str
    ) -> Optional[DAGCheckpoint]:
        """Get current DAG checkpoint."""
        key = f"checkpoint:dag:{dag_id}:{execution_id}"
        data = await self.redis.get(key)

        if data:
            parsed = json.loads(data)
            return DAGCheckpoint(
                dag_id=parsed["dag_id"],
                execution_id=parsed["execution_id"],
                completed_nodes=parsed.get("completed_nodes", []),
                pending_nodes=parsed.get("pending_nodes", []),
                node_results=parsed.get("node_results", {}),
                node_states=parsed.get("node_states", {}),
                created_at=datetime.fromisoformat(parsed.get("created_at", datetime.utcnow().isoformat())),
                metadata=parsed.get("metadata", {})
            )

        return None

    async def _save_dag_checkpoint(self, checkpoint: DAGCheckpoint) -> None:
        """Save DAG checkpoint to Redis."""
        key = f"checkpoint:dag:{checkpoint.dag_id}:{checkpoint.execution_id}"

        data = {
            "dag_id": checkpoint.dag_id,
            "execution_id": checkpoint.execution_id,
            "completed_nodes": checkpoint.completed_nodes,
            "pending_nodes": checkpoint.pending_nodes,
            "node_results": checkpoint.node_results,
            "node_states": checkpoint.node_states,
            "created_at": checkpoint.created_at.isoformat(),
            "metadata": checkpoint.metadata
        }

        await self.redis.setex(key, self.default_ttl, json.dumps(data, default=str))
        self._active_checkpoints[f"{checkpoint.dag_id}:{checkpoint.execution_id}"] = checkpoint

    async def restore_from_checkpoint(
        self,
        dag_id: str,
        execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Restore execution state from checkpoint."""
        checkpoint = await self.get_dag_checkpoint(dag_id, execution_id)
        if not checkpoint:
            return None

        # Restore node results
        results = {}
        for node_id in checkpoint.completed_nodes:
            result_key = f"checkpoint:dag:{dag_id}:{execution_id}:node:{node_id}"
            result_data = await self.redis.get(result_key)
            if result_data:
                try:
                    results[node_id] = pickle.loads(result_data)
                except Exception:
                    results[node_id] = None

        return {
            "completed_nodes": checkpoint.completed_nodes,
            "pending_nodes": checkpoint.pending_nodes,
            "node_results": results,
            "node_states": checkpoint.node_states
        }

    async def cleanup_old_checkpoints(self, dag_id: str, keep_count: int = 5) -> int:
        """Clean up old checkpoints for a DAG."""
        pattern = f"checkpoint:dag:{dag_id}:*"
        executions = set()

        async for key in self.redis.scan_iter(match=pattern):
            parts = key.decode().split(":")
            if len(parts) >= 4:
                exec_id = parts[3]
                if "node:" not in exec_id:
                    executions.add(exec_id)

        if len(executions) <= keep_count:
            return 0

        # Get checkpoint times
        exec_times = []
        for exec_id in executions:
            checkpoint = await self.get_dag_checkpoint(dag_id, exec_id)
            if checkpoint:
                exec_times.append((exec_id, checkpoint.created_at))

        exec_times.sort(key=lambda x: x[1])

        # Delete old ones
        to_delete = exec_times[:-keep_count]
        deleted = 0

        for exec_id, _ in to_delete:
            if await self.delete_dag_checkpoint(dag_id, exec_id):
                deleted += 1

        return deleted

    async def delete_dag_checkpoint(self, dag_id: str, execution_id: str) -> bool:
        """Delete a DAG checkpoint and its node results."""
        # Delete main checkpoint
        main_key = f"checkpoint:dag:{dag_id}:{execution_id}"
        await self.redis.delete(main_key)

        # Delete node results
        pattern = f"checkpoint:dag:{dag_id}:{execution_id}:node:*"
        deleted = 0

        async for key in self.redis.scan_iter(match=pattern):
            if await self.redis.delete(key):
                deleted += 1

        key = f"{dag_id}:{execution_id}"
        self._active_checkpoints.pop(key, None)

        return deleted > 0


class ResumableExecutionManager:
    """Manages resumable execution for long-running pipelines."""

    def __init__(
        self,
        redis_client: Any,
        default_checkpoint_interval: float = 60.0
    ):
        self.redis = redis_client
        self.checkpoint_interval = default_checkpoint_interval

        self._executions: Dict[str, Dict] = {}
        self._checkpoints: Dict[str, List[PipelineCheckpoint]] = {}

    async def start_execution(
        self,
        execution_id: str,
        pipeline_id: str,
        initial_data: Any,
        config: Optional[Dict] = None
    ) -> None:
        """Start a new resumable execution."""
        execution = {
            "execution_id": execution_id,
            "pipeline_id": pipeline_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "current_stage": 0,
            "stages_completed": [],
            "metadata": config or {}
        }

        await self.redis.setex(
            f"execution:{execution_id}",
            604800,  # 7 days
            json.dumps(execution, default=str)
        )

        self._executions[execution_id] = execution

        # Store initial data checkpoint
        await self.create_checkpoint(
            execution_id=execution_id,
            stage="init",
            checkpoint_type=CheckpointType.INTERMEDIATE,
            data=initial_data
        )

    async def create_checkpoint(
        self,
        execution_id: str,
        stage: str,
        checkpoint_type: CheckpointType,
        data: Any,
        artifacts: Optional[Dict] = None,
        ttl_seconds: Optional[float] = None
    ) -> str:
        """Create a checkpoint for execution."""
        checkpoint_id = str(uuid.uuid4())

        checkpoint = PipelineCheckpoint(
            checkpoint_id=checkpoint_id,
            pipeline_id="",  # Would be set by caller
            stage=stage,
            step_index=len(self._checkpoints.get(execution_id, [])),
            checkpoint_type=checkpoint_type,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds or 604800),
            data=data,
            artifacts=artifacts or {}
        )

        # Store checkpoint
        key = f"checkpoint:execution:{execution_id}:{stage}:{checkpoint_id}"
        await self.redis.setex(
            key,
            ttl_seconds or 604800,
            pickle.dumps(checkpoint)
        )

        # Track in list
        if execution_id not in self._checkpoints:
            self._checkpoints[execution_id] = []
        self._checkpoints[execution_id].append(checkpoint)

        # Update execution metadata
        await self._update_execution_progress(execution_id, stage)

        return checkpoint_id

    async def _update_execution_progress(
        self,
        execution_id: str,
        stage: str
    ) -> None:
        """Update execution progress."""
        execution = await self.redis.get(f"execution:{execution_id}")
        if execution:
            data = json.loads(execution)
            if stage not in data.get("stages_completed", []):
                if "stages_completed" not in data:
                    data["stages_completed"] = []
                data["stages_completed"].append(stage)
                data["current_stage"] = len(data["stages_completed"])
                await self.redis.setex(
                    f"execution:{execution_id}",
                    604800,
                    json.dumps(data, default=str)
                )

    async def get_latest_checkpoint(
        self,
        execution_id: str
    ) -> Optional[PipelineCheckpoint]:
        """Get the latest checkpoint for an execution."""
        checkpoints = self._checkpoints.get(execution_id, [])
        if checkpoints:
            return checkpoints[-1]

        # Look up in Redis
        pattern = f"checkpoint:execution:{execution_id}:*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            keys.sort()
            data = await self.redis.get(keys[-1])
            if data:
                return pickle.loads(data)

        return None

    async def resume_execution(
        self,
        execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Resume execution from latest checkpoint."""
        checkpoint = await self.get_latest_checkpoint(execution_id)
        if not checkpoint:
            return None

        execution = await self.redis.get(f"execution:{execution_id}")
        if not execution:
            return None

        data = json.loads(execution)
        data["status"] = "resumed"
        data["resumed_from"] = checkpoint.stage

        await self.redis.setex(
            f"execution:{execution_id}",
            604800,
            json.dumps(data, default=str)
        )

        return {
            "execution_id": execution_id,
            "checkpoint": checkpoint,
            "stage": checkpoint.stage,
            "data": checkpoint.data,
            "artifacts": checkpoint.artifacts
        }

    async def complete_execution(
        self,
        execution_id: str,
        final_result: Any
    ) -> bool:
        """Mark execution as completed."""
        execution = await self.redis.get(f"execution:{execution_id}")
        if not execution:
            return False

        data = json.loads(execution)
        data["status"] = "completed"
        data["completed_at"] = datetime.utcnow().isoformat()
        data["final_result"] = str(final_result)[:1000]  # Truncate

        await self.redis.setex(
            f"execution:{execution_id}",
            604800,
            json.dumps(data, default=str)
        )

        # Clean up checkpoints
        await self._cleanup_checkpoints(execution_id)

        return True

    async def fail_execution(
        self,
        execution_id: str,
        error: str
    ) -> bool:
        """Mark execution as failed."""
        execution = await self.redis.get(f"execution:{execution_id}")
        if not execution:
            return False

        data = json.loads(execution)
        data["status"] = "failed"
        data["failed_at"] = datetime.utcnow().isoformat()
        data["error"] = error

        await self.redis.setex(
            f"execution:{execution_id}",
            604800,
            json.dumps(data, default=str)
        )

        return True

    async def get_execution_status(self, execution_id: str) -> Optional[Dict]:
        """Get execution status."""
        execution = await self.redis.get(f"execution:{execution_id}")
        if execution:
            return json.loads(execution)
        return None

    async def _cleanup_checkpoints(self, execution_id: str) -> None:
        """Clean up checkpoints after execution completion."""
        pattern = f"checkpoint:execution:{execution_id}:*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            await self.redis.delete(*keys)

        self._checkpoints.pop(execution_id, None)

    async def list_executions(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """List executions."""
        executions = []

        async for key in self.redis.scan_iter(match="execution:*", count=limit):
            data = await self.redis.get(key)
            if data:
                try:
                    exec_data = json.loads(data)
                    if status is None or exec_data.get("status") == status:
                        executions.append(exec_data)
                except Exception:
                    pass

        executions.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return executions[:limit]


class CheckpointPruner:
    """Prunes old checkpoints based on policies."""

    def __init__(
        self,
        redis_client: Any,
        max_age_days: int = 7,
        max_checkpoints_per_pipeline: int = 50
    ):
        self.redis = redis_client
        self.max_age_days = max_age_days
        self.max_checkpoints = max_checkpoints_per_pipeline

    async def prune(self) -> Dict[str, int]:
        """Prune old checkpoints."""
        results = {
            "checkpoints_deleted": 0,
            "pipelines_cleaned": set()
        }

        cutoff = datetime.utcnow() - timedelta(days=self.max_age_days)

        # Find old checkpoints
        async for key in self.redis.scan_iter(match="checkpoint:*"):
            try:
                data = await self.redis.get(key)
                if data and key.decode().startswith("checkpoint:execution:"):
                    checkpoint = pickle.loads(data)
                    if checkpoint.created_at < cutoff:
                        await self.redis.delete(key)
                        results["checkpoints_deleted"] += 1
                        results["pipelines_cleaned"].add(checkpoint.pipeline_id)
            except Exception:
                pass

        results["pipelines_cleaned"] = len(results["pipelines_cleaned"])
        return results