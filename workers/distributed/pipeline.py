"""
Distributed Pipeline Graph Execution

DAG-based execution with checkpointing and fault tolerance.
"""

import asyncio
from typing import Optional, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


class NodeType(Enum):
    """Types of execution nodes."""
    TASK = "task"
    CONDITION = "condition"
    MERGE = "merge"
    SPLIT = "split"
    MAP = "map"
    REDUCE = "reduce"


@dataclass
class StageDependency:
    """Dependency between pipeline stages."""
    from_stage: str
    to_stage: str
    condition: Optional[Callable] = None
    data_flow: str = "default"  # default, errors, results


@dataclass
class PipelineStage:
    """Represents a stage in the pipeline."""
    name: str
    stage_type: str
    function: Optional[Callable] = None
    resources: dict = field(default_factory=lambda: {"cpu": 1, "gpu": 0})
    timeout_seconds: float = 3600
    retry_count: int = 3
    retry_delay: float = 30.0
    dependencies: List[str] = field(default_factory=list)
    # Execution options
    parallel: bool = False
    max_parallelism: int = 1
    # Checkpointing
    checkpoint_enabled: bool = True
    checkpoint_interval: float = 60.0


@dataclass
class ExecutionNode:
    """An executing node in the pipeline."""
    stage: PipelineStage
    node_id: str
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    retry_attempt: int = 0
    checkpoint_data: dict = field(default_factory=dict)


@dataclass
class PipelineMetrics:
    """Metrics for pipeline execution."""
    total_stages: int = 0
    completed_stages: int = 0
    failed_stages: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_duration_seconds: float = 0.0
    avg_stage_duration_seconds: float = 0.0
    gpu_utilization_percent: float = 0.0
    cpu_utilization_percent: float = 0.0


class PipelineGraph:
    """DAG-based pipeline execution graph."""

    def __init__(self, pipeline_id: str, name: str = ""):
        self.pipeline_id = pipeline_id
        self.name = name
        self._stages: dict[str, PipelineStage] = {}
        self._dependencies: List[StageDependency] = []
        self._execution_order: List[str] = []
        self._stage_results: dict[str, Any] = {}

    def add_stage(self, stage: PipelineStage) -> None:
        """Add a stage to the pipeline."""
        self._stages[stage.name] = stage

        # Update execution order based on dependencies
        self._update_execution_order()

    def add_dependency(
        self,
        from_stage: str,
        to_stage: str,
        condition: Optional[Callable] = None,
        data_flow: str = "default"
    ) -> None:
        """Add a dependency between stages."""
        dep = StageDependency(from_stage, to_stage, condition, data_flow)
        self._dependencies.append(dep)
        self._update_execution_order()

    def _update_execution_order(self) -> None:
        """Calculate topological order of stages."""
        # Simple topological sort
        in_degree = {name: 0 for name in self._stages}
        adjacency = {name: [] for name in self._stages}

        for dep in self._dependencies:
            if dep.from_stage in self._stages and dep.to_stage in self._stages:
                adjacency[dep.from_stage].append(dep.to_stage)
                in_degree[dep.to_stage] += 1

        # Kahn's algorithm
        queue = [name for name, deg in in_degree.items() if deg == 0]
        self._execution_order = []

        while queue:
            node = queue.pop(0)
            self._execution_order.append(node)

            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

    def get_ready_stages(self) -> List[str]:
        """Get stages that are ready to execute."""
        ready = []
        for name in self._execution_order:
            if self._stage_results.get(name) is not None:
                continue

            stage = self._stages[name]
            deps_met = all(
                self._stage_results.get(dep) is not None
                for dep in stage.dependencies
            )

            if deps_met:
                ready.append(name)

        return ready

    def is_complete(self) -> bool:
        """Check if pipeline is complete."""
        return all(
            self._stage_results.get(name) is not None
            for name in self._stages
        )

    def get_stage(self, name: str) -> Optional[PipelineStage]:
        """Get a stage by name."""
        return self._stages.get(name)


class PipelineExecutor:
    """Executes a pipeline graph with fault tolerance."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._pipelines: dict[str, PipelineGraph] = {}
        self._executing_nodes: dict[str, ExecutionNode] = {}
        self._completed_nodes: dict[str, ExecutionNode] = {}
        self._failed_nodes: dict[str, ExecutionNode] = {}

    def create_pipeline(self, pipeline_id: str, name: str = "") -> PipelineGraph:
        """Create a new pipeline."""
        pipeline = PipelineGraph(pipeline_id, name)
        self._pipelines[pipeline_id] = pipeline
        return pipeline

    async def execute(
        self,
        pipeline: PipelineGraph,
        initial_data: Any = None,
        context: dict = None
    ) -> dict:
        """Execute a pipeline with fault tolerance."""
        context = context or {}
        results = {}
        failed_stages = []

        # Sort stages for execution
        execution_order = pipeline._execution_order.copy()

        for stage_name in execution_order:
            stage = pipeline._stages[stage_name]

            try:
                # Check if dependencies are met
                deps_met = all(
                    dep in results
                    for dep in stage.dependencies
                )

                if not deps_met:
                    failed_stages.append(stage_name)
                    continue

                # Get input data
                if stage.dependencies:
                    input_data = results[stage.dependencies[0]]
                else:
                    input_data = initial_data

                # Execute stage
                result = await self._execute_stage(
                    stage,
                    input_data,
                    context
                )

                results[stage_name] = result

            except Exception as e:
                # Handle failure with retry
                for retry in range(stage.retry_count):
                    try:
                        await asyncio.sleep(stage.retry_delay * (retry + 1))
                        result = await self._execute_stage(
                            stage,
                            input_data,
                            context
                        )
                        results[stage_name] = result
                        break
                    except Exception:
                        continue

                results[stage_name] = {"error": str(e)}
                failed_stages.append(stage_name)

        return {
            "pipeline_id": pipeline.pipeline_id,
            "status": "completed" if not failed_stages else "failed",
            "results": results,
            "failed_stages": failed_stages,
        }

    async def _execute_stage(
        self,
        stage: PipelineStage,
        input_data: Any,
        context: dict
    ) -> Any:
        """Execute a single stage."""
        if stage.function:
            return await stage.function(input_data, context)
        else:
            # Mock execution
            return {"stage": stage.name, "status": "completed"}


class PipelineMonitor:
    """Monitors pipeline execution."""

    def __init__(self):
        self._active_pipelines: dict[str, dict] = {}
        self._history: List[dict] = []

    def start_pipeline(self, pipeline_id: str, total_stages: int) -> None:
        """Start tracking a pipeline."""
        self._active_pipelines[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "status": "running",
            "total_stages": total_stages,
            "completed_stages": 0,
            "failed_stages": 0,
            "started_at": datetime.utcnow(),
            "current_stage": "",
            "progress_percent": 0.0,
        }

    def update_stage(
        self,
        pipeline_id: str,
        stage_name: str,
        status: StageStatus,
        result: Any = None,
        error: str = None
    ) -> None:
        """Update stage status."""
        if pipeline_id in self._active_pipelines:
            pipeline = self._active_pipelines[pipeline_id]
            pipeline["current_stage"] = stage_name

            if status == StageStatus.COMPLETED:
                pipeline["completed_stages"] += 1
            elif status == StageStatus.FAILED:
                pipeline["failed_stages"] += 1

            pipeline["progress_percent"] = (
                pipeline["completed_stages"] / pipeline["total_stages"] * 100
            )

            if pipeline["completed_stages"] + pipeline["failed_stages"] >= pipeline["total_stages"]:
                pipeline["status"] = "completed"
                pipeline["completed_at"] = datetime.utcnow()

    def get_pipeline_status(self, pipeline_id: str) -> Optional[dict]:
        """Get current status of a pipeline."""
        return self._active_pipelines.get(pipeline_id)

    def get_all_status(self) -> List[dict]:
        """Get status of all active pipelines."""
        return list(self._active_pipelines.values())


# Predefined pipeline templates
class PipelineTemplates:
    """Predefined pipeline templates."""

    @staticmethod
    def web_crawl_pipeline() -> List[PipelineStage]:
        """Pipeline for web crawling and extraction."""
        return [
            PipelineStage(
                name="crawl",
                stage_type="crawl",
                resources={"cpu": 4, "gpu": 0},
                dependencies=[]
            ),
            PipelineStage(
                name="extract",
                stage_type="extract",
                resources={"cpu": 2, "gpu": 0},
                dependencies=["crawl"]
            ),
            PipelineStage(
                name="filter",
                stage_type="filter",
                resources={"cpu": 2, "gpu": 1},
                dependencies=["extract"]
            ),
            PipelineStage(
                name="transform",
                stage_type="transform",
                resources={"cpu": 2, "gpu": 1},
                dependencies=["filter"]
            ),
            PipelineStage(
                name="validate",
                stage_type="validate",
                resources={"cpu": 2, "gpu": 0},
                dependencies=["transform"]
            ),
            PipelineStage(
                name="package",
                stage_type="package",
                resources={"cpu": 1, "gpu": 0},
                dependencies=["validate"]
            ),
        ]

    @staticmethod
    def gpu_inference_pipeline() -> List[PipelineStage]:
        """Pipeline for GPU-accelerated inference."""
        return [
            PipelineStage(
                name="preprocess",
                stage_type="preprocess",
                resources={"cpu": 2, "gpu": 0},
            ),
            PipelineStage(
                name="inference",
                stage_type="inference",
                resources={"cpu": 1, "gpu": 1},
                dependencies=["preprocess"]
            ),
            PipelineStage(
                name="postprocess",
                stage_type="postprocess",
                resources={"cpu": 2, "gpu": 0},
                dependencies=["inference"]
            ),
            PipelineStage(
                name="aggregate",
                stage_type="aggregate",
                resources={"cpu": 1, "gpu": 0},
                dependencies=["postprocess"]
            ),
        ]

    @staticmethod
    def multimodal_pipeline() -> List[PipelineStage]:
        """Pipeline for multimodal data processing."""
        return [
            PipelineStage(
                name="fetch_text",
                stage_type="fetch_text",
                resources={"cpu": 2, "gpu": 0},
            ),
            PipelineStage(
                name="fetch_images",
                stage_type="fetch_images",
                resources={"cpu": 2, "gpu": 0},
            ),
            PipelineStage(
                name="ocr",
                stage_type="ocr",
                resources={"cpu": 1, "gpu": 1},
                dependencies=["fetch_images"]
            ),
            PipelineStage(
                name="embed_text",
                stage_type="embed_text",
                resources={"cpu": 1, "gpu": 1},
                dependencies=["fetch_text", "ocr"]
            ),
            PipelineStage(
                name="embed_images",
                stage_type="embed_images",
                resources={"cpu": 1, "gpu": 1},
                dependencies=["fetch_images"]
            ),
            PipelineStage(
                name="fuse",
                stage_type="fuse",
                resources={"cpu": 2, "gpu": 1},
                dependencies=["embed_text", "embed_images"]
            ),
        ]