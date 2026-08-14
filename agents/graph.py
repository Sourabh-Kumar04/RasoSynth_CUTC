"""
Agent Graph - DAG-based execution graph for multi-agent orchestration

Dynamic execution graph with agent nodes, weighted edges, and topological execution.
"""

from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import asyncio


class NodeStatus(Enum):
    """Status of a graph node."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EdgeType(Enum):
    """Types of edges between nodes."""
    SEQUENTIAL = "sequential"  # Must execute after
    CONDITIONAL = "conditional"  # Execute if condition met
    PARALLEL = "parallel"       # Can execute concurrently
    FEEDBACK = "feedback"       # Results feed back
    FALLBACK = "fallback"       # Execute if upstream fails


@dataclass
class GraphNode:
    """A node in the agent execution graph."""
    node_id: str
    agent_type: str
    agent_config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    input_schema: Optional[Dict] = None
    output_schema: Optional[Dict] = None
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def execution_time_ms(self) -> float:
        """Calculate execution time."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0


@dataclass
class GraphEdge:
    """An edge connecting nodes in the graph."""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType = EdgeType.SEQUENTIAL
    weight: float = 1.0
    condition: Optional[Callable] = None
    transform: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def can_traverse(self, source_result: Any = None) -> bool:
        """Check if edge can be traversed."""
        if self.edge_type == EdgeType.SEQUENTIAL:
            return True
        if self.condition and source_result is not None:
            return self.condition(source_result)
        return True


@dataclass
class ExecutionPlan:
    """Planned execution order for the graph."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    graph_id: str = ""
    node_order: List[str] = field(default_factory=list)
    parallel_groups: List[List[str]] = field(default_factory=list)
    estimated_duration_ms: float = 0.0
    required_capabilities: Set[str] = field(default_factory=set)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_next_ready_nodes(self, completed: Set[str]) -> List[str]:
        """Get nodes that are ready to execute based on completed nodes."""
        ready = []
        for node_id in self.node_order:
            if node_id in completed:
                continue
            if self._is_ready(node_id, completed):
                ready.append(node_id)
        return ready

    def _is_ready(self, node_id: str, completed: Set[str]) -> bool:
        """Check if node is ready to execute."""
        return True  # Simplified - would check dependencies


@dataclass
class GraphState:
    """State of the execution graph."""
    graph_id: str
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: Dict[str, GraphEdge] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)
    completed_nodes: Set[str] = field(default_factory=set)
    failed_nodes: Set[str] = field(default_factory=set)
    current_node: Optional[str] = None
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)


class AgentGraph:
    """DAG-based execution graph for agent orchestration."""

    def __init__(self, graph_id: Optional[str] = None):
        self.graph_id = graph_id or str(uuid.uuid4())
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._node_inputs: Dict[str, Any] = {}
        self._node_outputs: Dict[str, Any] = {}
        self.state = GraphState(graph_id=self.graph_id)

    def add_node(
        self,
        node_id: str,
        agent_type: str,
        agent_config: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        conditions: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> GraphNode:
        """Add a node to the graph."""
        node = GraphNode(
            node_id=node_id,
            agent_type=agent_type,
            agent_config=agent_config or {},
            dependencies=dependencies or [],
            conditions=conditions or {},
            **kwargs
        )
        self.nodes[node_id] = node
        self.state.nodes[node_id] = node
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = EdgeType.SEQUENTIAL,
        weight: float = 1.0,
        condition: Optional[Callable] = None,
        transform: Optional[Callable] = None
    ) -> GraphEdge:
        """Add an edge between nodes."""
        if source_id not in self.nodes:
            raise ValueError(f"Source node {source_id} not found")
        if target_id not in self.nodes:
            raise ValueError(f"Target node {target_id} not found")

        edge = GraphEdge(
            edge_id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            condition=condition,
            transform=transform
        )
        self.edges.append(edge)
        self.state.edges[edge.edge_id] = edge
        return edge

    def get_execution_order(self) -> List[str]:
        """Get topologically sorted execution order."""
        in_degree = {node_id: 0 for node_id in self.nodes}
        adjacency = {node_id: [] for node_id in self.nodes}

        for edge in self.edges:
            in_degree[edge.target_id] += 1
            adjacency[edge.source_id].append(edge.target_id)

        queue = [n for n, d in in_degree.items() if d == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def get_parallel_groups(self) -> List[List[str]]:
        """Get nodes that can execute in parallel."""
        order = self.get_execution_order()
        groups = []
        processed = set()

        while len(processed) < len(self.nodes):
            ready = []
            for node_id in order:
                if node_id in processed:
                    continue
                deps = self.nodes[node_id].dependencies
                if all(d in processed for d in deps):
                    ready.append(node_id)

            if ready:
                groups.append(ready)
                processed.update(ready)
            else:
                break

        return groups

    def create_execution_plan(self) -> ExecutionPlan:
        """Create an optimized execution plan."""
        order = self.get_execution_order()
        parallel_groups = self.get_parallel_groups()

        plan = ExecutionPlan(
            graph_id=self.graph_id,
            node_order=order,
            parallel_groups=parallel_groups
        )

        # Estimate duration
        total_weight = sum(
            edge.weight for edge in self.edges
        )
        plan.estimated_duration_ms = total_weight * 1000

        # Collect required capabilities
        for node in self.nodes.values():
            caps = node.agent_config.get("capabilities", [])
            plan.required_capabilities.update(caps)

        return plan

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Get all dependencies of a node (transitive)."""
        deps = set(self.nodes[node_id].dependencies)
        to_process = list(deps)

        while to_process:
            node_id = to_process.pop()
            if node_id in self.nodes:
                for dep in self.nodes[node_id].dependencies:
                    if dep not in deps:
                        deps.add(dep)
                        to_process.append(dep)

        return deps

    def get_dependents(self, node_id: str) -> Set[str]:
        """Get all nodes that depend on this node (transitive)."""
        dependents = set()
        to_check = [node_id]

        while to_check:
            current = to_check.pop()
            for edge in self.edges:
                if edge.source_id == current and edge.target_id not in dependents:
                    dependents.add(edge.target_id)
                    to_check.append(edge.target_id)

        return dependents

    def can_execute(self, node_id: str, completed: Set[str]) -> bool:
        """Check if a node can be executed."""
        if node_id not in self.nodes:
            return False
        if node_id in completed:
            return False

        deps = self.get_dependencies(node_id)
        return deps.issubset(completed)

    def set_input(self, node_id: str, data: Any) -> None:
        """Set input data for a node."""
        self._node_inputs[node_id] = data

    def get_input(self, node_id: str) -> Any:
        """Get input data for a node."""
        return self._node_inputs.get(node_id)

    def set_output(self, node_id: str, data: Any) -> None:
        """Set output data for a node."""
        self._node_outputs[node_id] = data

    def get_output(self, node_id: str) -> Any:
        """Get output data for a node."""
        return self._node_outputs.get(node_id)

    def to_dict(self) -> dict:
        """Serialize graph to dict."""
        return {
            "graph_id": self.graph_id,
            "nodes": {
                node_id: {
                    "agent_type": node.agent_type,
                    "status": node.status.value,
                    "dependencies": node.dependencies,
                }
                for node_id, node in self.nodes.items()
            },
            "edges": [
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type.value,
                }
                for edge in self.edges
            ],
            "execution_order": self.get_execution_order(),
        }


class GraphExecutor:
    """Executes agent graphs with parallel execution support."""

    def __init__(self, max_parallel: int = 4):
        self.max_parallel = max_parallel
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, Any] = {}

    async def execute(
        self,
        graph: AgentGraph,
        executor_func: Callable[[str, Any], Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute the graph."""
        plan = graph.create_execution_plan()
        results = {}
        completed = set()

        for group in plan.parallel_groups:
            tasks = []
            for node_id in group:
                if graph.can_execute(node_id, completed):
                    input_data = graph.get_input(node_id) or context
                    task = self._execute_node(
                        node_id,
                        executor_func,
                        input_data,
                        graph
                    )
                    tasks.append(task)

            if tasks:
                group_results = await asyncio.gather(*tasks, return_exceptions=True)
                for node_id, result in zip(group, group_results):
                    if isinstance(result, Exception):
                        results[node_id] = {"error": str(result)}
                    else:
                        results[node_id] = result
                    completed.add(node_id)

        return results

    async def _execute_node(
        self,
        node_id: str,
        executor_func: Callable,
        input_data: Any,
        graph: AgentGraph
    ) -> Any:
        """Execute a single node."""
        node = graph.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")

        node.status = NodeStatus.RUNNING
        node.start_time = datetime.utcnow()

        try:
            result = await executor_func(node_id, input_data)
            node.status = NodeStatus.COMPLETED
            node.result = result
            graph.set_output(node_id, result)
            return result
        except Exception as e:
            node.status = NodeStatus.FAILED
            node.error = str(e)
            raise
        finally:
            node.end_time = datetime.utcnow()

    def cancel(self, node_id: str) -> bool:
        """Cancel a running node."""
        if node_id in self._active_tasks:
            self._active_tasks[node_id].cancel()
            return True
        return False

    def cancel_all(self) -> None:
        """Cancel all running tasks."""
        for task in self._active_tasks.values():
            task.cancel()
        self._active_tasks.clear()