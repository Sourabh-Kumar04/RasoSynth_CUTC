"""
Multi-Agent Orchestrator - Dynamic agent lifecycle and workflow management

Orchestrates multi-agent workflows with intelligent scheduling, load balancing,
and adaptive execution strategies.
"""

from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
import json


class OrchestrationStrategy(Enum):
    """Strategies for orchestrating agents."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"
    ADAPTIVE = "adaptive"


@dataclass
class WorkflowSpec:
    """Specification for a multi-agent workflow."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    strategy: OrchestrationStrategy = OrchestrationStrategy.PIPELINE
    stages: List[Dict[str, Any]] = field(default_factory=list)
    max_parallel: int = 4
    timeout_seconds: float = 3600.0
    retry_on_failure: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Execution state for a workflow."""
    workflow_id: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    current_stage: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stage_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict] = field(default_factory=list)
    agent_assignments: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """Metrics for an agent's performance."""
    agent_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_execution_time_ms: float = 0.0
    current_load: float = 0.0
    success_rate: float = 1.0
    last_used: Optional[datetime] = None


class AgentScheduler:
    """Schedules agent tasks with priority and load awareness."""

    def __init__(self):
        self._scheduled_tasks: Dict[str, Dict] = {}
        self._task_queue: List[Dict] = []
        self._priority_levels = 5

    async def schedule(
        self,
        task: Dict[str, Any],
        agent_id: str,
        priority: int = 3,
        scheduled_at: Optional[datetime] = None
    ) -> str:
        """Schedule a task for execution."""
        task_id = str(uuid.uuid4())

        scheduled_task = {
            "task_id": task_id,
            "agent_id": agent_id,
            "task": task,
            "priority": priority,
            "scheduled_at": scheduled_at or datetime.utcnow(),
            "status": "scheduled",
        }

        self._scheduled_tasks[task_id] = scheduled_task
        self._add_to_queue(scheduled_task)

        return task_id

    async def schedule_batch(
        self,
        tasks: List[Dict[str, Any]],
        agent_id: str,
        priority: int = 3
    ) -> List[str]:
        """Schedule multiple tasks."""
        task_ids = []
        for task in tasks:
            task_id = await self.schedule(task, agent_id, priority)
            task_ids.append(task_id)
        return task_ids

    async def get_next_task(self, agent_id: str) -> Optional[Dict]:
        """Get next available task for an agent."""
        for task in self._task_queue:
            if task["agent_id"] == agent_id and task["status"] == "scheduled":
                task["status"] = "assigned"
                return task
        return None

    async def complete_task(self, task_id: str, result: Any) -> bool:
        """Mark a task as completed."""
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id]["status"] = "completed"
            self._scheduled_tasks[task_id]["result"] = result
            self._scheduled_tasks[task_id]["completed_at"] = datetime.utcnow()
            self._remove_from_queue(task_id)
            return True
        return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id]["status"] = "cancelled"
            self._remove_from_queue(task_id)
            return True
        return False

    def _add_to_queue(self, task: Dict) -> None:
        """Add task to priority queue."""
        self._task_queue.append(task)
        self._task_queue.sort(key=lambda t: t["priority"])

    def _remove_from_queue(self, task_id: str) -> None:
        """Remove task from queue."""
        self._task_queue = [t for t in self._task_queue if t["task_id"] != task_id]

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return len([t for t in self._task_queue if t["status"] == "scheduled"])

    def get_pending_tasks(self, agent_id: Optional[str] = None) -> List[Dict]:
        """Get pending tasks."""
        tasks = [t for t in self._task_queue if t["status"] == "scheduled"]
        if agent_id:
            tasks = [t for t in tasks if t["agent_id"] == agent_id]
        return tasks


class LoadBalancer:
    """Distributes work across agents based on capacity and load."""

    def __init__(self, strategy: str = "least_loaded"):
        self.strategy = strategy
        self._agent_loads: Dict[str, float] = {}
        self._agent_capacities: Dict[str, int] = {}

    def register_agent(self, agent_id: str, capacity: int = 5) -> None:
        """Register an agent with capacity."""
        self._agent_capacities[agent_id] = capacity
        if agent_id not in self._agent_loads:
            self._agent_loads[agent_id] = 0.0

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        self._agent_loads.pop(agent_id, None)
        self._agent_capacities.pop(agent_id, None)

    async def select_agent(
        self,
        required_capabilities: Set[str],
        preferred_agent: Optional[str] = None
    ) -> Optional[str]:
        """Select the best agent for a task."""
        if preferred_agent and self._is_available(preferred_agent):
            return preferred_agent

        candidates = []
        for agent_id, capacity in self._agent_capacities.items():
            load = self._agent_loads.get(agent_id, 0.0)
            if load < capacity:
                candidates.append((agent_id, load))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def _is_available(self, agent_id: str) -> bool:
        """Check if agent is available."""
        if agent_id not in self._agent_capacities:
            return False
        load = self._agent_loads.get(agent_id, 0.0)
        return load < self._agent_capacities[agent_id]

    async def assign_task(self, agent_id: str) -> None:
        """Assign a task to an agent, increasing load."""
        if agent_id in self._agent_loads:
            self._agent_loads[agent_id] += 1.0

    async def release_task(self, agent_id: str) -> None:
        """Release a task from an agent, decreasing load."""
        if agent_id in self._agent_loads:
            self._agent_loads[agent_id] = max(0.0, self._agent_loads[agent_id] - 1.0)

    def get_load_distribution(self) -> Dict[str, float]:
        """Get current load distribution."""
        return dict(self._agent_loads)

    def get_idle_agents(self) -> List[str]:
        """Get agents with no current load."""
        return [aid for aid, load in self._agent_loads.items() if load == 0.0]


class MultiAgentOrchestrator:
    """Orchestrates multi-agent workflows with adaptive execution."""

    def __init__(self):
        self.workflows: Dict[str, WorkflowSpec] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.scheduler = AgentScheduler()
        self.load_balancer = LoadBalancer()
        self._active_agents: Dict[str, Any] = {}
        self._execution_history: List[WorkflowExecution] = []

    async def register_workflow(self, workflow: WorkflowSpec) -> str:
        """Register a workflow specification."""
        self.workflows[workflow.workflow_id] = workflow
        return workflow.workflow_id

    async def execute_workflow(
        self,
        workflow_id: str,
        input_data: Any,
        agent_factory: Callable
    ) -> WorkflowExecution:
        """Execute a workflow with given input."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self.workflows[workflow_id]
        execution = WorkflowExecution(workflow_id=workflow_id)
        self.executions[execution.execution_id] = execution

        execution.started_at = datetime.utcnow()
        execution.status = "running"

        try:
            if workflow.strategy == OrchestrationStrategy.SEQUENTIAL:
                result = await self._execute_sequential(workflow, input_data, agent_factory, execution)
            elif workflow.strategy == OrchestrationStrategy.PARALLEL:
                result = await self._execute_parallel(workflow, input_data, agent_factory, execution)
            elif workflow.strategy == OrchestrationStrategy.PIPELINE:
                result = await self._execute_pipeline(workflow, input_data, agent_factory, execution)
            elif workflow.strategy == OrchestrationStrategy.FAN_OUT:
                result = await self._execute_fan_out(workflow, input_data, agent_factory, execution)
            else:
                result = await self._execute_adaptive(workflow, input_data, agent_factory, execution)

            execution.stage_results = result
            execution.status = "completed"

        except Exception as e:
            execution.status = "failed"
            execution.errors.append({
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })

        execution.completed_at = datetime.utcnow()
        self._execution_history.append(execution)
        return execution

    async def _execute_sequential(
        self,
        workflow: WorkflowSpec,
        input_data: Any,
        agent_factory: Callable,
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Execute workflow stages sequentially."""
        result = input_data
        for i, stage in enumerate(workflow.stages):
            execution.current_stage = i
            agent_type = stage.get("agent_type")
            agent = agent_factory(agent_type)

            stage_result = await self._run_agent(agent, stage, result)
            execution.stage_results[stage.get("name", f"stage_{i}")] = stage_result
            result = stage_result

        return result

    async def _execute_parallel(
        self,
        workflow: WorkflowSpec,
        input_data: Any,
        agent_factory: Callable,
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Execute workflow stages in parallel."""
        tasks = []
        for i, stage in enumerate(workflow.stages):
            agent_type = stage.get("agent_type")
            agent = agent_factory(agent_type)
            task = self._run_agent(agent, stage, input_data)
            tasks.append((stage.get("name", f"stage_{i}"), task))

        results = await asyncio.gather(*[t[1] for t in tasks])
        return {name: result for name, result in zip([t[0] for t in tasks], results)}

    async def _execute_pipeline(
        self,
        workflow: WorkflowSpec,
        input_data: Any,
        agent_factory: Callable,
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Execute workflow as a pipeline with streaming results."""
        result = input_data
        for i, stage in enumerate(workflow.stages):
            execution.current_stage = i
            agent_type = stage.get("agent_type")
            agent = agent_factory(agent_type)

            stage_config = stage.get("config", {})
            batch_size = stage_config.get("batch_size", 10)

            if isinstance(result, list):
                stage_results = []
                for batch in self._chunk_list(result, batch_size):
                    batch_result = await self._run_agent(agent, stage, batch)
                    stage_results.append(batch_result)
                    execution.stage_results[f"{stage.get('name', f'stage_{i}')}_batch_{len(stage_results)}"] = batch_result
                result = stage_results
            else:
                stage_result = await self._run_agent(agent, stage, result)
                execution.stage_results[stage.get("name", f"stage_{i}")] = stage_result
                result = stage_result

        return result

    async def _execute_fan_out(
        self,
        workflow: WorkflowSpec,
        input_data: Any,
        agent_factory: Callable,
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Execute workflow with fan-out pattern."""
        if not workflow.stages:
            return input_data

        first_stage = workflow.stages[0]
        agent_type = first_stage.get("agent_type")
        agent = agent_factory(agent_type)

        # Fan out over input items
        if isinstance(input_data, list):
            fan_out_count = min(len(input_data), workflow.max_parallel)
            chunks = self._chunk_list(input_data, fan_out_count)

            tasks = [self._run_agent(agent, first_stage, chunk) for chunk in chunks]
            results = await asyncio.gather(*tasks)

            execution.stage_results["fan_out"] = results

            # Continue with remaining stages sequentially
            result = results
            for i, stage in enumerate(workflow.stages[1:], 1):
                agent_type = stage.get("agent_type")
                agent = agent_factory(agent_type)
                stage_result = await self._run_agent(agent, stage, result)
                execution.stage_results[stage.get("name", f"stage_{i}")] = stage_result
                result = stage_result

            return result

        return await self._run_agent(agent, first_stage, input_data)

    async def _execute_adaptive(
        self,
        workflow: WorkflowSpec,
        input_data: Any,
        agent_factory: Callable,
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Execute workflow with adaptive strategy selection."""
        # Analyze input to select best strategy
        if isinstance(input_data, list):
            if len(input_data) > 100:
                return await self._execute_pipeline(workflow, input_data, agent_factory, execution)
            else:
                return await self._execute_parallel(workflow, input_data, agent_factory, execution)
        else:
            return await self._execute_sequential(workflow, input_data, agent_factory, execution)

    async def _run_agent(
        self,
        agent: Any,
        stage: Dict[str, Any],
        input_data: Any
    ) -> Any:
        """Run an agent with given input."""
        from agents.base import AgentContext

        context = AgentContext(
            job_id=str(uuid.uuid4()),
            dataset_id="",
            metadata=stage.get("metadata", {})
        )

        return await agent.execute(input_data, context)

    def _chunk_list(self, lst: List, chunk_size: int) -> List[List]:
        """Split list into chunks."""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        if execution_id in self.executions:
            self.executions[execution_id].status = "cancelled"
            self.executions[execution_id].completed_at = datetime.utcnow()
            return True
        return False

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        return self.executions.get(execution_id)

    def get_workflow_stats(self) -> Dict[str, Any]:
        """Get statistics for all workflows."""
        total = len(self._execution_history)
        completed = sum(1 for e in self._execution_history if e.status == "completed")
        failed = sum(1 for e in self._execution_history if e.status == "failed")

        return {
            "total_workflows": len(self.workflows),
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / max(total, 1),
            "active_executions": len([e for e in self.executions.values() if e.status == "running"]),
            "scheduled_tasks": self.scheduler.get_queue_size(),
        }