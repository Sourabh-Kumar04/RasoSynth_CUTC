"""Celery worker tasks for distributed pipeline execution."""
import os
from celery import Celery, chain, group, chord
from celery.signals import worker_ready, worker_shutdown
import asyncio

celery_app = Celery(
    "dataset_engine",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    task_routes={
        "workers.tasks.discovery": {"queue": "high"},
        "workers.tasks.extraction": {"queue": "high"},
        "workers.tasks.filtering": {"queue": "medium"},
        "workers.tasks.construction": {"queue": "medium"},
        "workers.tasks.export": {"queue": "low"},
    },
    task_annotations={
        "workers.tasks.discovery": {"rate_limit": "10/m"},
        "workers.tasks.export": {"rate_limit": "5/m"},
    }
)


@celery_app.task(bind=True, name="workers.tasks.discovery")
def discover_task(self, job_id: str, query: str, domain: str, config: dict):
    """Discovery task - find data sources.

    Uses asyncio.run() for proper async execution - no manual event loop management.
    """
    from pipeline.discovery import DiscoveryPipeline, SourceType

    try:
        discovery = DiscoveryPipeline(config)
        sources = []

        async def run():
            async for source in discovery.discover(query, domain):
                sources.append({
                    "url": source.url,
                    "source_type": source.source_type.value,
                    "title": source.title,
                    "metadata": source.metadata_,
                })

        # Use asyncio.run() - proper way to run async in sync context
        asyncio.run(run())

        return {"job_id": job_id, "sources": sources, "count": len(sources)}

    except Exception as e:
        return {"job_id": job_id, "error": str(e), "sources": []}


@celery_app.task(bind=True, name="workers.tasks.extraction")
def extract_task(self, job_id: str, sources: list[dict], config: dict):
    """Extraction task - extract content from sources."""
    from pipeline.extraction import ExtractionPipeline

    try:
        extraction = ExtractionPipeline(config)
        extracted = []

        async def run():
            for source in sources:
                url = source.get("url", "")
                try:
                    async for content in extraction.extract_from_url(url):
                        extracted.append({
                            "content": content.content,
                            "content_type": content.content_type,
                            "url": content.url,
                            "metadata": content.metadata,
                        })
                except Exception:
                    continue

        asyncio.run(run())

        return {"job_id": job_id, "extracted": extracted, "count": len(extracted)}

    except Exception as e:
        return {"job_id": job_id, "error": str(e), "extracted": []}


@celery_app.task(bind=True, name="workers.tasks.filtering")
def filter_task(self, job_id: str, content: list[dict], config: dict):
    """Filtering task - filter and validate content."""
    from pipeline.filtering import FilteringPipeline
    from core.config import get_settings
    import asyncio

    try:
        settings = get_settings()
        router = ProviderRouter(settings.model_dump())
        filtering = FilteringPipeline(router, config)

        filtered = []

        async def run():
            for item in content:
                sample = type('Content', (), item)()
                result = await filtering.filter(sample, config.get("target_domain", ""))
                if result and result.quality_score > config.get("quality_threshold", 0.5):
                    filtered.append({
                        "content": result.content,
                        "quality_score": result.quality_score,
                        "relevance_score": result.relevance_score,
                    })

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())
        loop.close()

        return {"job_id": job_id, "filtered": filtered, "count": len(filtered)}

    except Exception as e:
        return {"job_id": job_id, "error": str(e), "filtered": []}


@celery_app.task(bind=True, name="workers.tasks.construction")
def construct_task(self, job_id: str, filtered: list[dict], config: dict):
    """Construction task - build training samples."""
    from pipeline.construction import ConstructionPipeline, ConstructedSample
    from core.config import get_settings
    import asyncio

    try:
        settings = get_settings()
        router = ProviderRouter(settings.model_dump())
        construction = ConstructionPipeline(router, config)

        samples = []

        async def run():
            for item in filtered:
                sample = type('Sample', (), {
                    "content": item["content"],
                    "quality_score": item.get("quality_score", 0.5),
                })()

                async for constructed in construction.construct(sample, config.get("target_domain", "")):
                    samples.append({
                        "instruction": constructed.instruction,
                        "response": constructed.response,
                        "metadata": constructed.metadata,
                        "difficulty_tier": constructed.difficulty_tier,
                    })

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())
        loop.close()

        return {"job_id": job_id, "samples": samples, "count": len(samples)}

    except Exception as e:
        return {"job_id": job_id, "error": str(e), "samples": []}


@celery_app.task(bind=True, name="workers.tasks.export")
def export_task(self, job_id: str, samples: list[dict], format: str, config: dict):
    """Export task - export dataset in configured format."""
    from pipeline.export import ExportPipeline, ExportConfig
    from pathlib import Path
    import asyncio

    try:
        export_config = ExportConfig(
            format=format,
            output_dir=config.get("output_dir", "outputs"),
            dataset_name=f"dataset_{job_id}",
        )

        exporter = ExportPipeline(export_config)

        constructed_samples = []
        for item in samples:
            constructed_samples.append(type('Sample', (), {
                "instruction": item["instruction"],
                "response": item["response"],
                "input": item.get("input"),
                "metadata": item.get("metadata", {}),
                "difficulty_tier": item.get("difficulty_tier", 3),
                "curriculum_order": item.get("curriculum_order", 0),
            })())

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(exporter.export(constructed_samples, job_id))
        loop.close()

        return {"job_id": job_id, "output": str(result), "count": len(samples)}

    except Exception as e:
        return {"job_id": job_id, "error": str(e)}


@celery_app.task(name="workers.tasks.run_pipeline")
def run_pipeline_task(job_id: str, config: dict):
    """Run the complete pipeline as a chord."""
    query = config.get("target_domain", "")
    domain = config.get("target_domain", "")
    export_format = config.get("export_format", "jsonl")

    return chord(
        discover_task.s(job_id, query, domain, config),
        extract_task.s(config),
        filter_task.s(config),
        construct_task.s(config),
        export_task.s(export_format, config)
    )()


@celery_app.task(name="workers.tasks.refresh_dataset")
def refresh_dataset_task(dataset_id: str):
    """Periodic task for dataset refresh."""
    return {"dataset_id": dataset_id, "refreshed": True}


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Handle worker ready signal."""
    print("Celery worker is ready")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Handle worker shutdown signal."""
    print("Celery worker is shutting down")


if __name__ == "__main__":
    celery_app.start()