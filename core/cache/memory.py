"""
Distributed Agent Shared Memory

Redis-based shared memory layer for multi-agent coordination, state sharing,
workflow synchronization, and distributed computation coordination.
"""

from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import uuid


class MemoryRegion(Enum):
    """Memory region types for agent isolation."""
    SHARED = "shared"
    AGENT_PRIVATE = "agent_private"
    WORKFLOW = "workflow"
    PIPELINE = "pipeline"
    RESULTS = "results"


@dataclass
class SharedMemoryEntry:
    """Entry in shared memory."""
    key: str
    value: Any
    region: MemoryRegion
    owner: str  # Agent ID
    created_at: datetime
    ttl_seconds: float = 300.0
    readers: Set[str] = field(default_factory=set)
    writers: Set[str] = field(default_factory=set)
    locked: bool = False
    lock_holder: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl_seconds


class AgentSharedMemory:
    """Shared memory for distributed agents."""

    def __init__(
        self,
        redis_client: Any,
        enable_events: bool = True
    ):
        self.redis = redis_client
        self.enable_events = enable_events
        self._local_cache: Dict[str, SharedMemoryEntry] = {}
        self._subscriptions: Dict[str, Set[str]] = {}

    async def put(
        self,
        key: str,
        value: Any,
        region: MemoryRegion = MemoryRegion.SHARED,
        owner: str = "",
        ttl: float = 300.0,
        metadata: Optional[Dict] = None
    ) -> None:
        """Put value in shared memory."""
        entry = SharedMemoryEntry(
            key=key,
            value=value,
            region=region,
            owner=owner,
            created_at=datetime.utcnow(),
            ttl_seconds=ttl,
            metadata=metadata or {}
        )

        # Store in Redis
        serialized = json.dumps({
            "key": key,
            "value": value,
            "region": region.value,
            "owner": owner,
            "created_at": entry.created_at.isoformat(),
            "metadata": entry.metadata
        }, default=str)

        await self.redis.setex(
            self._make_key(region, key),
            ttl,
            serialized
        )

        # Update local cache
        self._local_cache[key] = entry

        # Publish event if enabled
        if self.enable_events:
            await self._publish_event("memory_write", key, region, value)

    async def get(
        self,
        key: str,
        region: MemoryRegion = MemoryRegion.SHARED,
        default: Any = None
    ) -> Any:
        """Get value from shared memory."""
        cache_key = self._make_key(region, key)

        # Check local cache first
        if key in self._local_cache:
            entry = self._local_cache[key]
            if not entry.is_expired():
                return entry.value

        # Fetch from Redis
        data = await self.redis.get(cache_key)
        if data:
            parsed = json.loads(data)
            return parsed.get("value", default)
        return default

    async def delete(
        self,
        key: str,
        region: MemoryRegion = MemoryRegion.SHARED
    ) -> bool:
        """Delete from shared memory."""
        cache_key = self._make_key(region, key)

        if key in self._local_cache:
            del self._local_cache[key]

        result = await self.redis.delete(cache_key)
        return result > 0

    async def get_many(
        self,
        keys: List[str],
        region: MemoryRegion = MemoryRegion.SHARED
    ) -> Dict[str, Any]:
        """Get multiple values."""
        results = {}
        for key in keys:
            value = await self.get(key, region)
            if value is not None:
                results[key] = value
        return results

    async def put_many(
        self,
        entries: Dict[str, Any],
        region: MemoryRegion = MemoryRegion.SHARED,
        owner: str = "",
        ttl: float = 300.0
    ) -> None:
        """Put multiple values."""
        for key, value in entries.items():
            await self.put(key, value, region, owner, ttl)

    async def subscribe(
        self,
        agent_id: str,
        key_pattern: str,
        callback: Callable
    ) -> None:
        """Subscribe to memory changes."""
        if agent_id not in self._subscriptions:
            self._subscriptions[agent_id] = set()
        self._subscriptions[agent_id].add(key_pattern)

    async def _publish_event(
        self,
        event_type: str,
        key: str,
        region: MemoryRegion,
        value: Any
    ) -> None:
        """Publish memory event."""
        channel = f"memory:{region.value}:{event_type}"
        message = json.dumps({
            "event_type": event_type,
            "key": key,
            "region": region.value,
            "timestamp": datetime.utcnow().isoformat()
        })
        await self.redis.publish(channel, message)

    def _make_key(self, region: MemoryRegion, key: str) -> str:
        """Make Redis key."""
        return f"memory:{region.value}:{key}"


class DistributedStateManager:
    """Manages distributed state across agents."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._states: Dict[str, Dict] = {}
        self._versions: Dict[str, int] = {}

    async def create_state(
        self,
        state_id: str,
        initial: Any,
        agents: List[str],
        ttl: float = 3600.0
    ) -> None:
        """Create a new distributed state."""
        state_data = {
            "state_id": state_id,
            "data": initial,
            "agents": agents,
            "created_at": datetime.utcnow().isoformat(),
            "version": 1
        }

        await self.redis.setex(
            f"state:{state_id}",
            ttl,
            json.dumps(state_data, default=str)
        )

        self._states[state_id] = state_data
        self._versions[state_id] = 1

    async def update_state(
        self,
        state_id: str,
        updates: Dict,
        agent_id: str,
        expected_version: Optional[int] = None
    ) -> bool:
        """Update distributed state with optimistic locking."""
        current = await self.get_state(state_id)
        if current is None:
            return False

        # Check version if provided
        if expected_version is not None:
            if self._versions.get(state_id) != expected_version:
                return False

        # Apply updates
        if isinstance(current["data"], dict):
            current["data"].update(updates)
        else:
            current["data"] = updates

        current["version"] += 1
        current["last_update_agent"] = agent_id
        current["last_updated"] = datetime.utcnow().isoformat()

        await self.redis.set(
            f"state:{state_id}",
            json.dumps(current, default=str)
        )

        self._versions[state_id] = current["version"]
        return True

    async def get_state(self, state_id: str) -> Optional[Dict]:
        """Get current state."""
        if state_id in self._states:
            return self._states[state_id]

        data = await self.redis.get(f"state:{state_id}")
        if data:
            state = json.loads(data)
            self._states[state_id] = state
            self._versions[state_id] = state.get("version", 1)
            return state
        return None

    async def delete_state(self, state_id: str) -> bool:
        """Delete a state."""
        self._states.pop(state_id, None)
        self._versions.pop(state_id, None)
        result = await self.redis.delete(f"state:{state_id}")
        return result > 0

    async def compare_and_swap(
        self,
        state_id: str,
        expected: Any,
        new_value: Any,
        agent_id: str
    ) -> bool:
        """Atomic compare-and-swap operation."""
        current = await self.get_state(state_id)
        if current is None:
            return False

        if current["data"] != expected:
            return False

        return await self.update_state(state_id, new_value, agent_id)

    async def increment_counter(
        self,
        counter_name: str,
        delta: int = 1
    ) -> int:
        """Atomically increment a counter."""
        key = f"counter:{counter_name}"
        return await self.redis.incrby(key, delta)

    async def get_counter(self, counter_name: str) -> int:
        """Get counter value."""
        key = f"counter:{counter_name}"
        value = await self.redis.get(key)
        return int(value) if value else 0


class WorkflowCoordinator:
    """Coordinates workflow execution across agents."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._workflows: Dict[str, Dict] = {}
        self._checkpoints: Dict[str, Dict] = {}

    async def create_workflow(
        self,
        workflow_id: str,
        steps: List[Dict],
        participants: List[str]
    ) -> Dict:
        """Create a new workflow."""
        workflow = {
            "workflow_id": workflow_id,
            "steps": steps,
            "participants": participants,
            "status": "created",
            "current_step": 0,
            "created_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "results": {}
        }

        await self.redis.setex(
            f"workflow:{workflow_id}",
            86400,  # 24 hour TTL
            json.dumps(workflow, default=str)
        )

        self._workflows[workflow_id] = workflow
        return workflow

    async def start_workflow(self, workflow_id: str) -> bool:
        """Start a workflow."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow or workflow["status"] != "created":
            return False

        workflow["status"] = "running"
        workflow["started_at"] = datetime.utcnow().isoformat()

        await self._save_workflow(workflow)
        return True

    async def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow details."""
        if workflow_id in self._workflows:
            return self._workflows[workflow_id]

        data = await self.redis.get(f"workflow:{workflow_id}")
        if data:
            workflow = json.loads(data)
            self._workflows[workflow_id] = workflow
            return workflow
        return None

    async def update_step(
        self,
        workflow_id: str,
        step_index: int,
        result: Any,
        agent_id: str
    ) -> bool:
        """Update workflow step result."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return False

        if step_index < len(workflow["steps"]):
            workflow["steps"][step_index]["result"] = result
            workflow["steps"][step_index]["completed_by"] = agent_id
            workflow["steps"][step_index]["completed_at"] = datetime.utcnow().isoformat()

        workflow["results"][f"step_{step_index}"] = result
        workflow["current_step"] = step_index + 1

        await self._save_workflow(workflow)
        return True

    async def complete_workflow(
        self,
        workflow_id: str,
        final_result: Any
    ) -> bool:
        """Mark workflow as completed."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return False

        workflow["status"] = "completed"
        workflow["completed_at"] = datetime.utcnow().isoformat()
        workflow["final_result"] = final_result

        await self._save_workflow(workflow)
        return True

    async def _save_workflow(self, workflow: Dict) -> None:
        """Save workflow to Redis."""
        self._workflows[workflow["workflow_id"]] = workflow
        await self.redis.setex(
            f"workflow:{workflow['workflow_id']}",
            86400,
            json.dumps(workflow, default=str)
        )


class PipelineCheckpointManager:
    """Manages pipeline checkpoints for fault tolerance."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._checkpoints: Dict[str, Dict] = {}

    async def create_checkpoint(
        self,
        pipeline_id: str,
        stage: str,
        data: Any,
        metadata: Optional[Dict] = None
    ) -> str:
        """Create a pipeline checkpoint."""
        checkpoint_id = str(uuid.uuid4())

        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "pipeline_id": pipeline_id,
            "stage": stage,
            "data": data,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        # Store checkpoint
        key = f"checkpoint:{pipeline_id}:{stage}:{checkpoint_id}"
        await self.redis.setex(key, 604800, json.dumps(checkpoint, default=str))  # 7 day TTL

        # Track latest checkpoint for pipeline
        await self.redis.setex(
            f"checkpoint:latest:{pipeline_id}",
            604800,
            checkpoint_id
        )

        self._checkpoints[checkpoint_id] = checkpoint
        return checkpoint_id

    async def get_latest_checkpoint(
        self,
        pipeline_id: str
    ) -> Optional[Dict]:
        """Get the latest checkpoint for a pipeline."""
        checkpoint_id = await self.redis.get(f"checkpoint:latest:{pipeline_id}")
        if not checkpoint_id:
            return None

        keys = []
        async for key in self.redis.scan_iter(match=f"checkpoint:{pipeline_id}:*"):
            keys.append(key)

        for key in keys:
            if checkpoint_id in key:
                data = await self.redis.get(key)
                if data:
                    return json.loads(data)

        return None

    async def get_checkpoint(
        self,
        pipeline_id: str,
        stage: str
    ) -> Optional[Dict]:
        """Get checkpoint for specific stage."""
        pattern = f"checkpoint:{pipeline_id}:{stage}:*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append((key, await self.redis.get(key)))

        if keys:
            # Return most recent
            keys.sort(key=lambda x: x[0])
            _, data = keys[-1]
            return json.loads(data) if data else None

        return None

    async def delete_old_checkpoints(
        self,
        pipeline_id: str,
        keep_count: int = 5
    ) -> int:
        """Delete old checkpoints, keeping most recent."""
        pattern = f"checkpoint:{pipeline_id}:*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if len(keys) <= keep_count:
            return 0

        # Sort by timestamp (older first)
        key_data = []
        for key in keys:
            data = await self.redis.get(key)
            if data:
                try:
                    checkpoint = json.loads(data)
                    key_data.append((key, checkpoint.get("created_at", "")))
                except:
                    pass

        key_data.sort(key=lambda x: x[1])
        to_delete = key_data[:-keep_count]

        deleted = 0
        for key, _ in to_delete:
            if await self.redis.delete(key):
                deleted += 1

        return deleted

    async def list_checkpoints(
        self,
        pipeline_id: str
    ) -> List[Dict]:
        """List all checkpoints for a pipeline."""
        pattern = f"checkpoint:{pipeline_id}:*"
        checkpoints = []

        async for key in self.redis.scan_iter(match=pattern):
            data = await self.redis.get(key)
            if data:
                try:
                    checkpoints.append(json.loads(data))
                except:
                    pass

        checkpoints.sort(key=lambda x: x.get("created_at", ""))
        return checkpoints