"""
Agent Coordination - Hierarchical planning and task delegation

Supervisor, hierarchical planner, task delegator, and consensus resolver for
multi-agent coordination with fault tolerance and dynamic load balancing.
"""

from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid


class Priority(Enum):
    """Task priorities."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class TaskStatus(Enum):
    """Status of a delegated task."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class TaskSpec:
    """Specification for a delegatable task."""
    task_id: str
    task_type: str
    description: str
    priority: Priority = Priority.NORMAL
    required_capabilities: Set[str] = field(default_factory=set)
    input_data: Any = None
    timeout_seconds: float = 300.0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "priority": self.priority.value,
            "capabilities": list(self.required_capabilities),
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
        }


@dataclass
class DelegatedTask:
    """A task delegated to an agent."""
    spec: TaskSpec
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    progress: float = 0.0
    checkpoints: List[Dict] = field(default_factory=list)


@dataclass
class ConsensusVote:
    """Vote in consensus resolution."""
    voter_id: str
    value: Any
    confidence: float = 1.0
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PlanningDecision:
    """A planning decision made by the hierarchical planner."""
    decision_id: str
    level: int  # Hierarchy level (0 = highest)
    decision_type: str
    options: List[Any]
    selected_option: Any
    reasoning: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class Supervisor:
    """Supervises agent execution with health monitoring and recovery."""

    def __init__(self, supervisor_id: Optional[str] = None):
        self.supervisor_id = supervisor_id or str(uuid.uuid4())
        self._agents: Dict[str, Dict] = {}
        self._tasks: Dict[str, DelegatedTask] = {}
        self._health_history: Dict[str, List[Dict]] = {}
        self._failed_agents: Set[str] = set()
        self._max_health_history = 100

    async def register_agent(
        self,
        agent_id: str,
        capabilities: Set[str],
        health_check_interval: float = 30.0
    ) -> None:
        """Register an agent with the supervisor."""
        self._agents[agent_id] = {
            "capabilities": capabilities,
            "health_check_interval": health_check_interval,
            "last_health_check": datetime.utcnow(),
            "status": "active",
            "assigned_tasks": [],
            "completed_tasks": 0,
            "failed_tasks": 0,
        }

    async def deregister_agent(self, agent_id: str) -> bool:
        """Deregister an agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    async def assign_task(
        self,
        task: TaskSpec,
        preferred_agent: Optional[str] = None
    ) -> DelegatedTask:
        """Assign a task to an agent."""
        delegated = DelegatedTask(spec=task)

        # Find best agent
        agent_id = preferred_agent or self._select_agent(task)
        if not agent_id:
            delegated.status = TaskStatus.FAILED
            delegated.error = "No suitable agent available"
            return delegated

        delegated.assigned_agent = agent_id
        delegated.status = TaskStatus.ASSIGNED

        if agent_id in self._agents:
            self._agents[agent_id]["assigned_tasks"].append(task.task_id)

        self._tasks[task.task_id] = delegated
        return delegated

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: float = 0.0,
        result: Any = None,
        error: Optional[str] = None
    ) -> None:
        """Update task status."""
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]
        task.status = status
        task.progress = progress

        if status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = datetime.utcnow()

        if result is not None:
            task.result = result

        if error:
            task.error = error

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.utcnow()
            if task.assigned_agent and task.assigned_agent in self._agents:
                agent = self._agents[task.assigned_agent]
                if status == TaskStatus.COMPLETED:
                    agent["completed_tasks"] += 1
                else:
                    agent["failed_tasks"] += 1

    async def health_check(self, agent_id: str) -> Dict[str, Any]:
        """Perform health check on an agent."""
        now = datetime.utcnow()
        agent_info = self._agents.get(agent_id)

        if not agent_info:
            return {"status": "unknown", "agent_id": agent_id}

        last_check = agent_info["last_health_check"]
        time_since = (now - last_check).total_seconds()
        interval = agent_info["health_check_interval"]

        healthy = time_since < interval * 3

        health_record = {
            "timestamp": now,
            "healthy": healthy,
            "time_since_check": time_since,
        }

        if agent_id not in self._health_history:
            self._health_history[agent_id] = []
        self._health_history[agent_id].append(health_record)

        # Trim history
        if len(self._health_history[agent_id]) > self._max_health_history:
            self._health_history[agent_id] = self._health_history[agent_id][-self._max_health_history:]

        agent_info["last_health_check"] = now
        agent_info["status"] = "active" if healthy else "degraded"

        return health_record

    def _select_agent(self, task: TaskSpec) -> Optional[str]:
        """Select the best agent for a task."""
        candidates = []

        for agent_id, info in self._agents.items():
            if agent_id in self._failed_agents:
                continue

            # Check capabilities
            if not task.required_capabilities.issubset(info["capabilities"]):
                continue

            # Check capacity (max 5 concurrent tasks)
            if len(info["assigned_tasks"]) >= 5:
                continue

            # Score based on load and success rate
            completed = info["completed_tasks"]
            failed = info["failed_tasks"]
            success_rate = completed / max(completed + failed, 1)

            score = success_rate - (len(info["assigned_tasks"]) * 0.1)
            candidates.append((agent_id, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def get_supervisor_stats(self) -> Dict[str, Any]:
        """Get supervisor statistics."""
        total_tasks = len(self._tasks)
        completed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)

        return {
            "supervisor_id": self.supervisor_id,
            "registered_agents": len(self._agents),
            "total_tasks": total_tasks,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "success_rate": completed / max(total_tasks, 1),
        }


class HierarchicalPlanner:
    """Hierarchical planning with multi-level decision making."""

    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self._plans: Dict[str, List[PlanningDecision]] = {}
        self._decision_cache: Dict[str, PlanningDecision] = {}

    async def create_plan(
        self,
        objective: str,
        context: Dict[str, Any],
        level: int = 0
    ) -> List[PlanningDecision]:
        """Create a hierarchical plan."""
        plan_id = str(uuid.uuid4())
        decisions = []

        # Decompose objective
        options = await self._decompose(objective, context, level)

        for option in options:
            decision = PlanningDecision(
                decision_id=str(uuid.uuid4()),
                level=level,
                decision_type="decomposition",
                options=options,
                selected_option=option,
                reasoning=await self._reason_about(option, context),
                confidence=0.9,
            )
            decisions.append(decision)

            # Recurse for sub-objectives
            if level < self.max_depth:
                sub_decisions = await self.create_plan(
                    option["description"],
                    {**context, "parent": decision.decision_id},
                    level + 1
                )
                decisions.extend(sub_decisions)

        self._plans[plan_id] = decisions
        return decisions

    async def _decompose(
        self,
        objective: str,
        context: Dict[str, Any],
        level: int
    ) -> List[Dict]:
        """Decompose objective into sub-objectives."""
        # Simplified decomposition
        if level == 0:
            return [
                {"description": f"Research: {objective}", "priority": Priority.HIGH},
                {"description": f"Plan execution for: {objective}", "priority": Priority.NORMAL},
                {"description": f"Execute: {objective}", "priority": Priority.NORMAL},
            ]
        return [{"description": objective, "priority": Priority.NORMAL}]

    async def _reason_about(self, option: Dict, context: Dict) -> str:
        """Generate reasoning for an option."""
        return f"Option selected based on priority {option.get('priority', Priority.NORMAL).value}"

    def get_plan(self, plan_id: str) -> Optional[List[PlanningDecision]]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def optimize_plan(self, plan: List[PlanningDecision]) -> List[PlanningDecision]:
        """Optimize plan by reordering and consolidating decisions."""
        # Sort by level and priority
        sorted_plan = sorted(
            plan,
            key=lambda d: (d.level, -d.confidence)
        )

        # Remove redundant decisions
        seen = set()
        optimized = []
        for decision in sorted_plan:
            key = (decision.decision_type, decision.level)
            if key not in seen:
                seen.add(key)
                optimized.append(decision)

        return optimized


class TaskDelegator:
    """Delegates tasks to agents based on capabilities and load."""

    def __init__(self, supervisor: Supervisor):
        self.supervisor = supervisor
        self._delegation_history: List[Dict] = []

    async def delegate(
        self,
        task: TaskSpec,
        strategy: str = "capability_match"
    ) -> DelegatedTask:
        """Delegate a task to an appropriate agent."""
        agent_id = None

        if strategy == "capability_match":
            agent_id = self._match_by_capability(task)
        elif strategy == "load_balancing":
            agent_id = self._match_by_load(task)
        elif strategy == "random":
            agent_id = self._random_match(task)

        delegated = await self.supervisor.assign_task(task, agent_id)

        self._delegation_history.append({
            "task_id": task.task_id,
            "agent_id": agent_id,
            "strategy": strategy,
            "timestamp": datetime.utcnow(),
        })

        return delegated

    def _match_by_capability(self, task: TaskSpec) -> Optional[str]:
        """Match task to agent with exact capability match."""
        return self.supervisor._select_agent(task)

    def _match_by_load(self, task: TaskSpec) -> Optional[str]:
        """Match task to least loaded agent."""
        candidates = []

        for agent_id, info in self.supervisor._agents.items():
            if not task.required_capabilities.issubset(info["capabilities"]):
                continue

            load = len(info["assigned_tasks"])
            candidates.append((agent_id, -load))  # Negative for sorting

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def _random_match(self, task: TaskSpec) -> Optional[str]:
        """Randomly match to a capable agent."""
        import random

        candidates = [
            agent_id for agent_id, info in self.supervisor._agents.items()
            if task.required_capabilities.issubset(info["capabilities"])
        ]

        return random.choice(candidates) if candidates else None

    def get_delegation_stats(self) -> Dict[str, Any]:
        """Get delegation statistics."""
        return {
            "total_delegations": len(self._delegation_history),
            "strategies_used": list(set(d["strategy"] for d in self._delegation_history)),
        }


class ConsensusResolver:
    """Resolves conflicts through agent consensus."""

    def __init__(self, required_agreement: float = 0.7):
        self.required_agreement = required_agreement
        self._consensus_rounds: Dict[str, List[List[ConsensusVote]]] = {}

    async def reach_consensus(
        self,
        topic: str,
        agents: List[str],
        initial_values: Dict[str, Any]
    ) -> Optional[Any]:
        """Attempt to reach consensus among agents."""
        round_id = str(uuid.uuid4())
        self._consensus_rounds[round_id] = []

        votes = [
            ConsensusVote(voter_id=aid, value=initial_values.get(aid))
            for aid in agents
        ]
        self._consensus_rounds[round_id].append(votes)

        # Count votes
        value_counts: Dict[Any, int] = {}
        total_confidence = 0.0

        for vote in votes:
            if vote.value not in value_counts:
                value_counts[vote.value] = 0
            value_counts[vote.value] += 1
            total_confidence += vote.confidence

        # Check agreement
        if value_counts:
            max_count = max(value_counts.values())
            agreement = max_count / len(votes)

            if agreement >= self.required_agreement:
                # Consensus reached
                for vote in votes:
                    if vote.value == max(value_counts, key=value_counts.get):
                        return vote.value

        return None

    async def weighted_consensus(
        self,
        topic: str,
        votes: List[ConsensusVote]
    ) -> Any:
        """Calculate weighted consensus."""
        if not votes:
            return None

        # Group by value
        value_weights: Dict[Any, float] = {}
        for vote in votes:
            if vote.value not in value_weights:
                value_weights[vote.value] = 0.0
            value_weights[vote.value] += vote.confidence

        # Return value with highest weight
        return max(value_weights, key=value_weights.get)

    def get_consensus_stats(self, round_id: str) -> Dict[str, Any]:
        """Get statistics for a consensus round."""
        if round_id not in self._consensus_rounds:
            return {}

        rounds = self._consensus_rounds[round_id]
        return {
            "round_id": round_id,
            "total_rounds": len(rounds),
            "total_votes": sum(len(r) for r in rounds),
        }