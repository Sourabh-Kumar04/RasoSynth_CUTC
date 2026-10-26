"""Celery worker tasks for distributed pipeline execution."""
import os
from celery import Celery, chain, group, chord
from celery.signals import worker_ready, worker_shutdown
import asyncio

from core.provider_router import ProviderRouter

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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
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

# Beat enqueues durable Celery tasks; it never owns a background thread in the
# API process. Run it separately with `celery -A workers.celery_app beat`.
celery_app.conf.beat_schedule = {
    "reviewer-calibration-daily": {
        "task": "workers.tasks.calibrate_reviewers",
        "schedule": 24 * 60 * 60,
    },
    "workflow-schedule-dispatch": {
        "task": "workers.tasks.dispatch_due_schedules",
        "schedule": 60.0,
    },
}


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


@celery_app.task(
    name="workers.tasks.run_pipeline",
    ignore_result=True,
    time_limit=None,
    soft_time_limit=None,
)
def run_pipeline_task(job_id: str, config: dict, schedule_run_id: str | None = None):
    """Run the production orchestrator in a worker-owned service lifespan.

    Dataset jobs use the same LangGraph pipeline, persistence, websocket, and
    review queue as the API path. The older stage-task chord is retained for
    explicit stage-level use, but is not the production job runner.
    """
    from api.legacy_schemas import JobRequest
    from api.server import app, lifespan, run_pipeline

    async def execute():
        request = JobRequest.model_validate(config)
        async with lifespan(app):
            try:
                await run_pipeline(job_id, request)
                if schedule_run_id and getattr(app.state, "db", None):
                    status = await app.state.db.get_job_status(job_id)
                    final_status = "completed" if status and status.get("status") == "completed" else "failed"
                    await app.state.db.finish_workflow_schedule_run(
                        schedule_run_id, final_status, {"job_id": job_id, "job_status": status or {}},
                    )
            except Exception as exc:
                if schedule_run_id and getattr(app.state, "db", None):
                    await app.state.db.finish_workflow_schedule_run(
                        schedule_run_id, "failed", {"job_id": job_id, "error": str(exc)},
                    )
                raise

    asyncio.run(execute())


@celery_app.task(name="workers.tasks.dispatch_due_schedules")
def dispatch_due_schedules_task() -> dict:
    """Claim durable schedule occurrences and dispatch their concrete work.

    Schedule definitions and runs live in PostgreSQL/SQLite, not Celery Beat,
    so changing a cadence or auditing an execution survives worker restarts.
    """
    async def run() -> dict:
        from api.server import app, lifespan

        dispatched, failures = [], []
        async with lifespan(app):
            db = getattr(app.state, "db", None)
            if db is None:
                return {"status": "skipped", "reason": "database unavailable"}
            for schedule in await db.claim_due_workflow_schedules(limit=20):
                config = dict(schedule.get("workflow_config") or {})
                workflow_type = schedule.get("workflow_type")
                try:
                    if workflow_type not in {"recrawl", "refresh", "retrain"}:
                        raise ValueError(f"unsupported workflow type: {workflow_type}")
                    if workflow_type == "retrain":
                        version_id = str(config.get("dataset_version_id") or "")
                        version = await db.get_dataset_version(version_id)
                        if not version or version.get("status") != "approved":
                            raise ValueError("retraining requires an approved immutable dataset version")
                        dataset_path = str(version.get("output_path") or "")
                        if not dataset_path or not os.path.isfile(dataset_path):
                            raise ValueError("immutable dataset artifact is unavailable")
                        config["dataset_id"] = version_id
                        config["dataset_version_id"] = version_id
                        config["dataset_path"] = dataset_path
                        run_record = await db.create_workflow_schedule_run(
                            schedule["id"], None, {"workflow_type": workflow_type, "config": config},
                        )
                        run_scheduled_retrain_task.delay(run_record["id"], config)
                        dispatched.append({"schedule_id": schedule["id"], "run_id": run_record["id"], "dataset_version_id": version_id})
                        continue
                    config["scheduled_workflow_type"] = workflow_type
                    config["scheduled_from_id"] = schedule["id"]
                    job = await db.create_job(config)
                    run_record = await db.create_workflow_schedule_run(
                        schedule["id"], job["id"], {"workflow_type": workflow_type, "config": config},
                    )
                    run_pipeline_task.delay(job["id"], config, run_record["id"])
                    dispatched.append({"schedule_id": schedule["id"], "run_id": run_record["id"], "job_id": job["id"]})
                except Exception as exc:
                    run_record = await db.create_workflow_schedule_run(
                        schedule["id"], None, {"workflow_type": workflow_type, "error": str(exc)},
                    )
                    await db.finish_workflow_schedule_run(run_record["id"], "blocked", run_record["detail"])
                    failures.append({"schedule_id": schedule["id"], "error": str(exc)})
        return {"status": "completed", "dispatched": dispatched, "failures": failures}

    return asyncio.run(run())


@celery_app.task(name="workers.tasks.run_scheduled_retrain")
def run_scheduled_retrain_task(schedule_run_id: str, config: dict) -> dict:
    """Run a gated fine-tune schedule against its immutable dataset version."""
    async def run() -> dict:
        from api.server import app, lifespan

        async with lifespan(app):
            db = getattr(app.state, "db", None)
            manager = getattr(app.state, "ft_manager", None)
            if db is None or manager is None:
                raise RuntimeError("fine-tune manager or database unavailable")
            try:
                fine_tune_job = await manager.create_job(config)
                fine_tune_job_id = fine_tune_job["id"]
                active_task = getattr(manager, "_tasks", {}).get(fine_tune_job_id)
                if active_task is not None:
                    await active_task
                final = await manager.get_job(fine_tune_job_id)
                final_status = final.get("status", "failed") if final else "failed"
                await db.finish_workflow_schedule_run(
                    schedule_run_id,
                    "completed" if final_status == "completed" else "failed",
                    {"finetune_job_id": fine_tune_job_id, "finetune_status": final_status},
                )
                return {"status": final_status, "finetune_job_id": fine_tune_job_id}
            except Exception as exc:
                await db.finish_workflow_schedule_run(schedule_run_id, "failed", {"error": str(exc)})
                raise

    return asyncio.run(run())


@celery_app.task(name="workers.tasks.calibrate_reviewers")
def calibrate_reviewers_task() -> dict:
    """Measure automated-review agreement against completed human decisions.

    This is intentionally read-only. Its report is suitable for alerting and
    threshold changes, while human decisions remain the dataset authority.
    """
    from core.evaluation.judge_calibrator import calibrate_judge_alignment

    async def run() -> dict:
        # Reuse the canonical lifespan to get the same database configuration
        # and fallback behavior as the API, not a second worker-only database.
        from api.server import app, lifespan

        async with lifespan(app):
            service = getattr(app.state, "review_service", None)
            if service is None:
                return {"status": "skipped", "reason": "review service unavailable"}

            queue = await service.get_queue(page=1, page_size=500)
            items = list(queue.get("items", []))
            for page in range(2, queue.get("total_pages", 1) + 1):
                next_page = await service.get_queue(page=page, page_size=500)
                items.extend(next_page.get("items", []))

            evaluations = []
            for item in items:
                status = item.get("review_status")
                if status not in {"approved", "rejected"}:
                    continue
                ensemble = (item.get("metadata") or {}).get("review_ensemble", {})
                score = ensemble.get("score")
                if isinstance(score, (int, float)):
                    evaluations.append({"human_decision": status, "judge_score": score})

            report = calibrate_judge_alignment(evaluations)
            database = getattr(app.state, "db", None)
            saved = None
            if database and hasattr(database, "create_review_calibration_report"):
                saved = await database.create_review_calibration_report(report)
            return {"status": "completed", "report": report, "report_id": (saved or {}).get("id")}

    return asyncio.run(run())


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
