"""
Quality Dashboard API — endpoints for dataset quality metrics.
"""
import logging
from fastapi import APIRouter, Query, Request
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quality", tags=["quality"])

# In-memory ring buffers (populated by record_quality_snapshot)
_quality_history: list[dict] = []
_job_quality: dict[str, dict] = {}


def _get_review_service(request: Request = None):
    """Return the shared ReviewService from app state, or None if unavailable."""
    try:
        if request is not None:
            svc = getattr(request.app.state, "review_service", None)
            if svc is not None:
                return svc
        # Fallback: module-level singleton set by lifespan
        import core as _core
        return getattr(_core, "_review_service_instance", None)
    except Exception:
        return None


@router.get("/overview")
async def quality_overview(request: Request):
    """Get overall quality metrics overview from real dataset samples in DB."""
    import api.server as server
    db_mgr = getattr(server, "db", None)

    avg_quality = 0.0
    total_jobs = 0
    total_samples = 0

    if db_mgr and db_mgr.db:
        from core.db import Sample, Dataset
        from sqlalchemy import select, func
        try:
            async with db_mgr.db.session_maker() as session:
                job_res = await session.execute(select(func.count(Dataset.id)))
                total_jobs = job_res.scalar() or 0

                sample_res = await session.execute(
                    select(func.count(Sample.id), func.avg(Sample.quality_score))
                )
                row = sample_res.one_or_none()
                if row:
                    total_samples = row[0] or 0
                    avg_quality = float(row[1] or 0.0)
        except Exception as e:
            logger.error("Error querying quality overview from DB: %s", e)

    # Use shared ReviewService from app state
    svc = _get_review_service(request)
    review_stats: dict = {}
    if svc is not None:
        try:
            review_stats = await svc.get_stats()
        except Exception:
            pass

    return {
        "average_quality": round(avg_quality, 3),
        "total_jobs": total_jobs,
        "total_samples_reviewed": total_samples or review_stats.get("total", 0),
        "approval_rate": review_stats.get("approval_rate", 0.0),
        "rejection_rate": review_stats.get("rejection_rate", 0.0),
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.get("/by-job/{job_id}")
async def job_quality(job_id: str):
    """Get quality metrics for a specific job from DB."""
    import api.server as server
    db_mgr = getattr(server, "db", None)
    if db_mgr and db_mgr.db:
        from core.db import Sample
        from sqlalchemy import select, func
        try:
            async with db_mgr.db.session_maker() as session:
                stmt = select(func.count(Sample.id), func.avg(Sample.quality_score)).where(Sample.dataset_id == job_id)
                res = await session.execute(stmt)
                row = res.one_or_none()
                if row and row[0] > 0:
                    return {
                        "job_id": job_id,
                        "samples_count": row[0],
                        "avg_quality": round(float(row[1] or 0.0), 3)
                    }
        except Exception as e:
            logger.error(f"Error fetching job quality: {e}")

    job_data = _job_quality.get(job_id)
    if not job_data:
        return {"job_id": job_id, "error": "No quality data for this job yet", "samples_count": 0}
    return {"job_id": job_id, **job_data}


@router.get("/trends")
async def quality_trends(days: int = Query(7, ge=1, le=90)):
    """Get quality trends over time from DB."""
    import api.server as server
    db_mgr = getattr(server, "db", None)
    
    recent = []
    if db_mgr and db_mgr.db:
        from core.db import Sample
        from sqlalchemy import select
        try:
            async with db_mgr.db.session_maker() as session:
                stmt = select(Sample.quality_score, Sample.created_at).order_by(Sample.created_at.desc()).limit(100)
                res = await session.execute(stmt)
                for score, created_at in res.all():
                    if score is not None:
                        recent.append({"avg_quality": score, "timestamp": created_at.isoformat() if created_at else ""})
        except Exception as e:
            logger.error(f"Error querying quality trends: {e}")

    return {
        "period_days": days,
        "data_points": len(recent),
        "trends": recent,
        "avg_quality": round(sum(e["avg_quality"] for e in recent) / len(recent), 3) if recent else 0.0,
        "min_quality": round(min((e["avg_quality"] for e in recent), default=0.0), 3),
        "max_quality": round(max((e["avg_quality"] for e in recent), default=0.0), 3),
    }


@router.get("/distributions")
async def quality_distributions():
    """Get quality score distributions directly from DB samples."""
    all_scores = []
    import api.server as server
    db_mgr = getattr(server, "db", None)
    if db_mgr and db_mgr.db:
        from core.db import Sample
        from sqlalchemy import select
        try:
            async with db_mgr.db.session_maker() as session:
                res = await session.execute(select(Sample.quality_score))
                all_scores = [r for (r,) in res.all() if r is not None]
        except Exception as e:
            logger.error(f"Error querying score distribution: {e}")

    if not all_scores:
        for job_data in _job_quality.values():
            all_scores.extend(job_data.get("quality_scores", []))

    if not all_scores:
        return {"total_scores": 0, "distribution": {"excellent": 0, "good": 0, "fair": 0, "poor": 0}, "histogram": [0] * 10}

    buckets = [0] * 10
    for s in all_scores:
        idx = min(9, int(s * 10))
        buckets[idx] += 1

    return {
        "total_scores": len(all_scores),
        "mean": round(sum(all_scores) / len(all_scores), 3),
        "distribution": {
            "excellent": sum(1 for s in all_scores if s >= 0.9),
            "good": sum(1 for s in all_scores if 0.7 <= s < 0.9),
            "fair": sum(1 for s in all_scores if 0.5 <= s < 0.7),
            "poor": sum(1 for s in all_scores if s < 0.5),
        },
        "histogram": buckets,
    }


@router.get("/sources")
async def source_quality():
    """Get source quality breakdown."""
    segmented = await segmented_quality()
    sources_data = []
    for domain, stats in segmented.get("domains", {}).items():
        sources_data.append({
            "source": domain,
            "avg_quality": stats["avg"],
            "samples_count": stats["count"]
        })
    return {
        "total_unique_sources": len(sources_data),
        "sources": sources_data
    }


@router.get("/segmented")
async def segmented_quality():
    """Get quality metrics segmented by dataset type, prompt length, and domain."""
    import api.server as server
    db_mgr = getattr(server, "db", None)
    if not db_mgr or not db_mgr.db:
        return get_empty_segmented_metrics()

    from core.db import Sample, Dataset
    from sqlalchemy import select

    try:
        async with db_mgr.db.session_maker() as session:
            # Join Sample and Dataset to get quality scores and metadata
            stmt = select(Sample.quality_score, Sample.instruction, Sample.metadata_, Dataset.type).join(Dataset)
            result = await session.execute(stmt)
            samples = result.all()

            if not samples:
                return get_empty_segmented_metrics()

            by_type = {}
            by_length = {"short": [], "medium": [], "long": []}
            by_domain = {}

            for quality, inst, meta, dtype in samples:
                q = quality or 0.0
                inst_len = len(inst) if inst else 0
                meta = meta or {}
                domain = meta.get("domain", "general")

                # 1. By Dataset Type
                dtype = dtype or "sft"
                if dtype not in by_type:
                    by_type[dtype] = []
                by_type[dtype].append(q)

                # 2. By Prompt Length
                if inst_len < 150:
                    by_length["short"].append(q)
                elif inst_len <= 500:
                    by_length["medium"].append(q)
                else:
                    by_length["long"].append(q)

                # 3. By Domain
                if domain not in by_domain:
                    by_domain[domain] = []
                by_domain[domain].append(q)

            return {
                "dataset_types": {
                    t: {
                        "avg": round(sum(v) / len(v), 3),
                        "count": len(v)
                    } for t, v in by_type.items()
                },
                "prompt_lengths": {
                    l: {
                        "avg": round(sum(v) / len(v), 3) if v else 0.0,
                        "count": len(v)
                    } for l, v in by_length.items()
                },
                "domains": {
                    d: {
                        "avg": round(sum(v) / len(v), 3),
                        "count": len(v)
                    } for d, v in by_domain.items()
                }
            }
    except Exception as e:
        logger.error(f"Error querying segmented metrics: {e}")
        return get_empty_segmented_metrics()


def get_empty_segmented_metrics():
    return {
        "dataset_types": {},
        "prompt_lengths": {
            "short": {"avg": 0.0, "count": 0},
            "medium": {"avg": 0.0, "count": 0},
            "long": {"avg": 0.0, "count": 0}
        },
        "domains": {}
    }


def record_quality_snapshot(
    avg_quality: float,
    min_quality: float,
    max_quality: float,
    samples_count: int,
    job_id: str = "",
):
    """Record a quality snapshot for trend tracking."""
    entry = {
        "timestamp": datetime.utcnow(),
        "avg_quality": avg_quality,
        "min_quality": min_quality,
        "max_quality": max_quality,
        "samples_count": samples_count,
    }
    _quality_history.append(entry)
    while len(_quality_history) > 1000:
        _quality_history.pop(0)

    if job_id:
        if job_id not in _job_quality:
            _job_quality[job_id] = {"quality_scores": []}
        _job_quality[job_id]["quality_scores"].append(avg_quality)
        _job_quality[job_id]["last_updated"] = datetime.utcnow().isoformat()