"""
Multi-Agent Workflow Observability

Monitors agent execution, coordination, communication patterns,
and multi-agent graph visualization.
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio


class AgentExecutionStatus(Enum):
    """Agent execution status."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentExecution:
    """Agent execution record."""
    agent_id: str
    agent_type: str
    task_id: str
    status: AgentExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    confidence: float = 0.0
    error: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCommunication:
    """Inter-agent communication record."""
    sender_id: str
    receiver_id: str
    message_type: str
    timestamp: datetime
    latency_ms: float = 0.0
    success: bool = True


class AgentWorkflowObserver:
    """Observes multi-agent workflows."""

    def __init__(self):
        self._executions: Dict[str, AgentExecution] = {}
        self._communications: List[AgentCommunication] = {}
        self._task_graph: Dict[str, Set[str]] = {}
        self._max_history = 10000

    async def record_execution(self, execution: AgentExecution) -> None:
        """Record agent execution."""
        key = f"{execution.agent_id}:{execution.task_id}"
        self._executions[key] = execution

        # Update task graph
        if execution.task_id not in self._task_graph:
            self._task_graph[execution.task_id] = set()
        for child in execution.children:
            self._task_graph[execution.task_id].add(child)

    async def record_communication(self, comm: AgentCommunication) -> None:
        """Record inter-agent communication."""
        key = f"{comm.sender_id}:{comm.receiver_id}:{comm.timestamp.isoformat()}"
        self._communications[key] = comm

    def get_agent_executions(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AgentExecution]:
        """Get agent executions."""
        executions = list(self._executions.values())

        if agent_id:
            executions = [e for e in executions if e.agent_id == agent_id]

        executions.sort(key=lambda x: x.start_time, reverse=True)
        return executions[:limit]

    def get_agent_timeline(self, agent_id: str) -> List[Dict]:
        """Get agent execution timeline."""
        executions = self.get_agent_executions(agent_id, limit=1000)

        timeline = []
        for exec in executions:
            timeline.append({
                "task_id": exec.task_id,
                "status": exec.status.value,
                "start": exec.start_time.isoformat(),
                "end": exec.end_time.isoformat() if exec.end_time else None,
                "duration_ms": exec.duration_ms,
                "cost_usd": exec.cost_usd
            })

        return timeline

    def get_task_graph(self, task_id: str) -> Dict[str, Any]:
        """Get task execution graph."""
        children = self._task_graph.get(task_id, set())

        nodes = [{"id": task_id, "type": "task"}]
        edges = []

        for child in children:
            nodes.append({"id": child, "type": "subtask"})
            edges.append({"source": task_id, "target": child})

        return {"nodes": nodes, "edges": edges}

    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get statistics for an agent."""
        executions = self.get_agent_executions(agent_id, limit=1000)

        if not executions:
            return {}

        total_duration = sum(e.duration_ms for e in executions)
        total_cost = sum(e.cost_usd for e in executions)
        completed = sum(1 for e in executions if e.status == AgentExecutionStatus.COMPLETED)
        failed = sum(1 for e in executions if e.status == AgentExecutionStatus.FAILED)

        return {
            "agent_id": agent_id,
            "total_executions": len(executions),
            "completed": completed,
            "failed": failed,
            "success_rate": completed / max(len(executions), 1),
            "avg_duration_ms": total_duration / max(len(executions), 1),
            "total_cost_usd": total_cost,
            "avg_confidence": sum(e.confidence for e in executions) / max(len(executions), 1)
        }


class AgentCoordinationTracker:
    """Tracks agent coordination patterns."""

    def __init__(self):
        self._coordination_events: List[Dict] = []
        self._consensus_rounds: Dict[str, List] = {}
        self._deadlocks: List[Dict] = {}

    async def record_delegation(
        self,
        supervisor_id: str,
        agent_id: str,
        task_id: str
    ) -> None:
        """Record task delegation."""
        self._coordination_events.append({
            "type": "delegation",
            "supervisor_id": supervisor_id,
            "agent_id": agent_id,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def record_consensus(
        self,
        round_id: str,
        votes: Dict[str, Any]
    ) -> None:
        """Record consensus round."""
        if round_id not in self._consensus_rounds:
            self._consensus_rounds[round_id] = []
        self._consensus_rounds[round_id].append(votes)

    async def record_retry(
        self,
        agent_id: str,
        task_id: str,
        attempt: int
    ) -> None:
        """Record task retry."""
        self._coordination_events.append({
            "type": "retry",
            "agent_id": agent_id,
            "task_id": task_id,
            "attempt": attempt,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def record_deadlock(
        self,
        agents: List[str],
        task_id: str,
        resolution: Optional[str] = None
    ) -> None:
        """Record deadlock detection."""
        self._deadlocks[f"{task_id}:{len(self._deadlocks)}"] = {
            "agents": agents,
            "task_id": task_id,
            "detected_at": datetime.utcnow().isoformat(),
            "resolution": resolution
        }

    def get_coordination_summary(self) -> Dict[str, Any]:
        """Get coordination summary."""
        delegations = [e for e in self._coordination_events if e.get("type") == "delegation"]
        retries = [e for e in self._coordination_events if e.get("type") == "retry"]

        return {
            "total_delegations": len(delegations),
            "total_retries": len(retries),
            "deadlock_count": len(self._deadlocks),
            "consensus_rounds": len(self._consensus_rounds)
        }


class MultiAgentGraphVisualizer:
    """Visualizes multi-agent execution graphs."""

    def __init__(self, observer: AgentWorkflowObserver):
        self.observer = observer

    def generate_execution_graph(
        self,
        workflow_id: str,
        agent_ids: List[str]
    ) -> Dict[str, Any]:
        """Generate execution graph visualization data."""
        nodes = []
        edges = []

        for agent_id in agent_ids:
            stats = self.observer.get_agent_stats(agent_id)

            nodes.append({
                "id": agent_id,
                "type": "agent",
                "status": self._get_latest_status(agent_id),
                "executions": stats.get("total_executions", 0),
                "success_rate": stats.get("success_rate", 0)
            })

            # Add edges for communication
            timeline = self.observer.get_agent_timeline(agent_id)
            for event in timeline[:10]:
                if "children" in event:
                    for child in event["children"]:
                        edges.append({
                            "source": agent_id,
                            "target": child,
                            "type": "delegation"
                        })

        return {
            "workflow_id": workflow_id,
            "nodes": nodes,
            "edges": edges
        }

    def _get_latest_status(self, agent_id: str) -> str:
        """Get latest agent status."""
        executions = self.observer.get_agent_executions(agent_id, limit=1)
        if executions:
            return executions[0].status.value
        return "unknown"

    def generate_heatmap(
        self,
        agent_ids: List[str],
        time_window: timedelta = timedelta(hours=1)
    ) -> Dict[str, Any]:
        """Generate execution heatmap."""
        heatmap = {}

        for agent_id in agent_ids:
            executions = self.observer.get_agent_executions(agent_id, limit=1000)

            # Count executions in time window
            cutoff = datetime.utcnow() - time_window
            recent = [e for e in executions if e.start_time > cutoff]

            heatmap[agent_id] = {
                "execution_count": len(recent),
                "avg_duration_ms": sum(e.duration_ms for e in recent) / max(len(recent), 1) if recent else 0,
                "cost_usd": sum(e.cost_usd for e in recent)
            }

        return heatmap

    def generate_coordination_map(
        self,
        agent_ids: List[str]
    ) -> Dict[str, Any]:
        """Generate coordination map."""
        connections = {}

        for agent_id in agent_ids:
            executions = self.observer.get_agent_executions(agent_id, limit=100)

            connections[agent_id] = {
                "delegated_to": set(),
                "received_from": set()
            }

            for exec in executions:
                for child in exec.children:
                    connections[agent_id]["delegated_to"].add(child)

        return connections