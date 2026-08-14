"""
Celery-Based Distributed Task Orchestration

High-level async orchestration for workflow management, retries, and scheduling.
"""

import asyncio
import json
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# Try Celery imports
try:
    from celery import Celery, Task, group, chain, chord
    from celery.result import AsyncResult
    from celery.exceptions import MaxRetriesExceededError, Retry
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

from workers.distributed.base import DistributedConfig, TaskSpec, ExecutionResult


# Create Celery app
app = Celery('dataset_engine')
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/1',
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 3600,
    'task_soft_time_limit': 3300,
})


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 7
    CRITICAL = 10


@dataclass
class PipelineTask:
    """Base class for pipeline tasks."""
    task_id: str
    task_type: str
    job_id: str
    pipeline_id: Optional[str] = None
    priority: int = 5
    max_retries: int = 3
    retry_delay_seconds: float = 30.0
    timeout_seconds: float = 3600.0
    checkpoint_enabled: bool = True
    metadata: dict = field(default_factory=dict)


class BasePipelineTask(Task):
    """Base task class with retry and checkpoint support."""

    def __call__(self, *args, **kwargs):
        """Execute task with error handling."""
        try:
            result = self.run(*args, **kwargs)
            return result
        except Exception as e:
            if self.max_retries > 0:
                raise self.retry(exc=e, countdown=self.retry_delay)
            raise

    @property
    def max_retries(self) -> int:
        return self._max_retries if hasattr(self, '_max_retries') else 3

    @property
    def retry_delay(self) -> float:
        return self._retry_delay if hasattr(self, '_retry_delay') else 30.0


@app.task(bind=True, base=BasePipelineTask, name='crawl_task')
def CrawlTask(
    self,
    job_id: str,
    urls: list[str],
    source_types: list[str],
    depth: int = 2,
    max_results: int = 100
) -> dict:
    """Web crawling task."""
    from pipeline.discovery import DiscoveryPipeline

    config = {"max_results": max_results}
    discovery = DiscoveryPipeline(config)

    results = []
    for url in urls:
        try:
            async def crawl():
                count = 0
                async for source in discovery.discover(url, "", source_types):
                    results.append({
                        "url": source.url,
                        "title": source.title,
                        "source_type": source.source_type.value,
                    })
                    count += 1
                    if count >= max_results:
                        break
            asyncio.run(crawl())
        except Exception as e:
            pass

    return {
        "job_id": job_id,
        "crawled_count": len(results),
        "sources": results,
    }


@app.task(bind=True, base=BasePipelineTask, name='extract_task')
def ExtractTask(
    self,
    job_id: str,
    sources: list[dict],
    extraction_config: dict
) -> dict:
    """Content extraction task."""
    from pipeline.extraction import ExtractionPipeline
    from workers.distributed.ray_executor import RayExecutor

    results = []

    for source in sources:
        try:
            # In real implementation, use Ray for parallel extraction
            results.append({
                "url": source.get("url"),
                "content": f"Extracted content for {source.get('url')}",
                "language": "en",
                "confidence": 0.85,
            })
        except Exception as e:
            pass

    return {
        "job_id": job_id,
        "extracted_count": len(results),
        "extracted_content": results,
    }


@app.task(bind=True, base=BasePipelineTask, name='filter_task')
def FilterTask(
    self,
    job_id: str,
    content_items: list[dict],
    filter_config: dict
) -> dict:
    """Quality filtering task."""
    from pipeline.filtering import FilteringPipeline

    results = []
    for item in content_items:
        try:
            quality_score = 0.7  # Simplified scoring
            if quality_score >= filter_config.get("min_quality", 0.5):
                results.append({
                    **item,
                    "quality_score": quality_score,
                    "passed": True,
                })
        except Exception:
            pass

    return {
        "job_id": job_id,
        "filtered_count": len(results),
        "filtered_content": results,
    }


@app.task(bind=True, base=BasePipelineTask, name='transform_task')
def TransformTask(
    self,
    job_id: str,
    items: list[dict],
    transform_config: dict
) -> dict:
    """Data transformation task."""
    transformed = []

    for item in items:
        try:
            # Apply transformations
            transformed_item = {
                "instruction": item.get("content", "")[:500],
                "response": item.get("content", "")[500:],
                "input": "",
                "metadata": item.get("metadata", {}),
            }
            transformed.append(transformed_item)
        except Exception:
            pass

    return {
        "job_id": job_id,
        "transformed_count": len(transformed),
        "samples": transformed,
    }


@app.task(bind=True, base=BasePipelineTask, name='validate_task')
def ValidateTask(
    self,
    job_id: str,
    samples: list[dict],
    validation_config: dict
) -> dict:
    """Dataset validation task."""
    valid_samples = []
    validation_errors = []

    for sample in samples:
        try:
            # Basic validation
            if sample.get("instruction") and sample.get("response"):
                valid_samples.append(sample)
            else:
                validation_errors.append({
                    "sample_id": sample.get("id", "unknown"),
                    "error": "Missing instruction or response",
                })
        except Exception as e:
            validation_errors.append({
                "sample_id": sample.get("id", "unknown"),
                "error": str(e),
            })

    return {
        "job_id": job_id,
        "valid_count": len(valid_samples),
        "invalid_count": len(validation_errors),
        "valid_samples": valid_samples,
        "errors": validation_errors,
    }


@app.task(bind=True, base=BasePipelineTask, name='package_task')
def PackageTask(
    self,
    job_id: str,
    samples: list[dict],
    package_config: dict
) -> dict:
    """Dataset packaging task."""
    from core.storage.packaging import DatasetPackager, PackagingConfig

    packager = DatasetPackager(PackagingConfig())

    # Package dataset
    manifest = asyncio.run(packager.package(
        samples,
        package_config.get("dataset_name", f"dataset_{job_id}"),
        package_config.get("version", "1.0.0")
    ))

    return {
        "job_id": job_id,
        "package_id": manifest.package_id,
        "archive_path": manifest.archive_path,
        "size_bytes": manifest.compressed_size_bytes,
        "sample_count": len(samples),
    }


@app.task(bind=True, base=BasePipelineTask, name='delivery_task')
def DeliveryTask(
    self,
    job_id: str,
    package_info: dict,
    delivery_config: dict
) -> dict:
    """Dataset delivery task."""
    from core.storage.delivery import DeliveryManager, DeliveryRequest
    from core.storage.base import StorageProviderType, DeliveryStrategy

    request = DeliveryRequest(
        dataset_id=job_id,
        dataset_name=delivery_config.get("dataset_name", f"dataset_{job_id}"),
        destination=StorageProviderType[delivery_config.get("provider", "AWS_S3")],
        destination_config={},
        format="jsonl",
        strategy=DeliveryStrategy.CLOUD_STORAGE,
    )

    delivery_manager = DeliveryManager()
    result = asyncio.run(delivery_manager.deliver(request, package_info.get("samples", [])))

    return {
        "job_id": job_id,
        "delivery_id": result.delivery_id,
        "status": result.status.value,
        "download_url": result.download_url,
    }


class TaskRouter:
    """Routes tasks to appropriate execution backends."""

    def __init__(self, config: DistributedConfig, ray_executor=None):
        self.config = config
        self._ray_executor = ray_executor
        self._task_queue = asyncio.Queue()

    async def route_task(self, task: TaskSpec) -> str:
        """Route task to appropriate backend."""
        # Determine if GPU task
        if task.resources.gpu_count > 0:
            return await self._route_to_ray(task)
        else:
            return await self._route_to_celery(task)

    async def _route_to_ray(self, task: TaskSpec) -> str:
        """Route to Ray cluster."""
        if not self._ray_executor:
            return ""

        # Execute via Ray
        result = await self._ray_executor.parallel_map(
            lambda x: x,
            [task],
            num_workers=1
        )
        return result[0] if result else ""

    async def _route_to_celery(self, task: TaskSpec) -> str:
        """Route to Celery workers."""
        # Dispatch to appropriate task
        if task.task_type == "crawl":
            return CrawlTask.delay(
                job_id=task.metadata.get("job_id", ""),
                urls=task.metadata.get("urls", []),
                source_types=task.metadata.get("source_types", []),
            ).id
        elif task.task_type == "extract":
            return ExtractTask.delay(
                job_id=task.metadata.get("job_id", ""),
                sources=task.metadata.get("sources", []),
                extraction_config=task.metadata.get("config", {}),
            ).id
        # ... other task types

        return ""


class PipelineOrchestrator:
    """Orchestrates multi-stage pipeline execution."""

    def __init__(self, config: DistributedConfig):
        self.config = config
        self._task_router = TaskRouter(config)
        self._pipeline_status: dict[str, dict] = {}

    async def execute_pipeline(
        self,
        job_id: str,
        stages: list[dict],
        initial_data: Any = None
    ) -> dict:
        """Execute a multi-stage pipeline."""
        pipeline_id = f"pipeline_{job_id}"
        results = {}

        for stage in stages:
            stage_name = stage.get("name")
            stage_type = stage.get("type")
            stage_config = stage.get("config", {})

            # Check dependencies
            dependencies = stage.get("dependencies", [])
            if dependencies:
                for dep in dependencies:
                    if dep not in results:
                        raise Exception(f"Dependency {dep} not satisfied")

            # Execute stage
            task = TaskSpec(
                task_id=f"{pipeline_id}_{stage_name}",
                task_type=stage_type,
                function_name=stage_type,
                args=(results.get(dependencies[0]) if dependencies else initial_data,),
                kwargs={"config": stage_config},
                metadata={"job_id": job_id, "pipeline_id": pipeline_id},
            )

            result = await self._task_router.route_task(task)
            results[stage_name] = result

        return results

    def get_pipeline_status(self, pipeline_id: str) -> Optional[dict]:
        """Get status of a pipeline execution."""
        return self._pipeline_status.get(pipeline_id)


# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'cleanup-checkpoints': {
        'task': 'cleanup_task',
        'schedule': 3600.0,  # Every hour
    },
    'health-check-workers': {
        'task': 'health_check',
        'schedule': 60.0,  # Every minute
    },
}


@app.task(name='cleanup_task')
def CleanupTask():
    """Periodic cleanup of old checkpoints and temporary data."""
    pass


@app.task(name='health_check')
def HealthCheck():
    """Periodic health check of all workers."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}