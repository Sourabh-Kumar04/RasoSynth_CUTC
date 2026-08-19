"""
Distributed Execution & GPU-Accelerated Pipeline Architecture

A distributed system for large-scale AI dataset processing
combining Ray (GPU/compute) and Celery (orchestration).

Architecture:
- Ray: GPU-accelerated compute, distributed inference, parallel processing
- Celery: Workflow orchestration, task queues, retry handling
- Hybrid design with clear separation of concerns
"""

from workers.distributed.base import (
    DistributedConfig,
    WorkerNode,
    ResourceRequirement,
    ExecutionResult,
)
from workers.distributed.ray_executor import (
    RayExecutor,
    RayGPUManager,
    RayActorPool,
    ModelActor,
    EmbeddingActor,
    InferenceWorker,
)
from workers.distributed.celery_tasks import (
    TaskRouter,
    PipelineTask,
    CrawlTask,
    ExtractTask,
    FilterTask,
    TransformTask,
    ValidateTask,
    PackageTask,
    DeliveryTask,
)
from workers.distributed.pipeline import (
    PipelineGraph,
    PipelineStage,
    StageDependency,
    ExecutionNode,
    PipelineMonitor,
)
from workers.distributed.scheduler import (
    GPUScheduler,
    WorkloadBalancer,
    ResourceAllocator,
    PriorityQueue,
)
from workers.distributed.fault_tolerance import (
    CheckpointManager,
    RecoveryManager,
    DeadLetterQueue,
    TaskRetryPolicy,
)
from workers.distributed.observability import (
    MetricsCollector,
    WorkerMonitor,
    GPUMonitor,
    PipelineTracer,
)

__all__ = [
    # Base
    "DistributedConfig",
    "WorkerNode",
    "ResourceRequirement",
    "ExecutionResult",

    # Ray
    "RayExecutor",
    "RayGPUManager",
    "RayActorPool",
    "ModelActor",
    "EmbeddingActor",
    "InferenceWorker",

    # Celery
    "TaskRouter",
    "PipelineTask",
    "CrawlTask",
    "ExtractTask",
    "FilterTask",
    "TransformTask",
    "ValidateTask",
    "PackageTask",
    "DeliveryTask",

    # Pipeline
    "PipelineGraph",
    "PipelineStage",
    "StageDependency",
    "ExecutionNode",
    "PipelineMonitor",

    # Scheduler
    "GPUScheduler",
    "WorkloadBalancer",
    "ResourceAllocator",
    "PriorityQueue",

    # Fault Tolerance
    "CheckpointManager",
    "RecoveryManager",
    "DeadLetterQueue",
    "TaskRetryPolicy",

    # Observability
    "MetricsCollector",
    "WorkerMonitor",
    "GPUMonitor",
    "PipelineTracer",
]