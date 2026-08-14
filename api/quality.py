"""
Quality Dashboard API — endpoints for dataset quality metrics.
"""
import logging
from fastapi import APIRouter, Query
from datetime import datetime, timedelta
from typing import Optional

from core.review_service import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quality", tags=["quality"])

_quality_history: list[dict] = []
_job_quality: dict[str, dict] = {}


@router.get("/overview")
async def quality_overview():
    """Get overall quality metrics overview."""
    svc = ReviewService()
    review_stats = svc.get_stats() if hasattr(svc, "_items") else {}

    quality_scores = [e.get("avg_quality", 0) for e in _quality_history if "avg_quality" in e]
    avg_quality = sum(quality_scores) / max(len(quality_scores), 1) if quality_scores else 0

    return {
        "average_quality": round(avg_quality, 3),
        "total_jobs": len(_job_quality),
        "total_samples_reviewed": review_stats.get("total", 0),
        "approval_rate": review_stats.get("approval_rate", 0),
        "rejection_rate": review_stats.get("rejection_rate", 0),
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.get("/by-job/{job_id}")
async def job_quality(job_id: str):
    """Get quality metrics for a specific job."""
    job_data = _job_quality.get(job_id)
    if not job_data:
        return {"job_id": job_id, "error": "No quality data for this job yet", "samples_count": 0}
    return {"job_id": job_id, **job_data}


@router.get("/trends")
async def quality_trends(days: int = Query(7, ge=1, le=90)):
    """Get quality trends over time."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = [e for e in _quality_history if e.get("timestamp", cutoff) >= cutoff]

    return {
        "period_days": days,
        "data_points": len(recent),
        "trends": recent[-50:] if recent else [],
        "avg_quality": sum(e.get("avg_quality", 0) for e in recent) / max(len(recent), 1) if recent else 0,
        "min_quality": min((e.get("min_quality", 0) for e in recent), default=0),
        "max_quality": max((e.get("max_quality", 0) for e in recent), default=0),
    }


@router.get("/distributions")
async def quality_distributions():
    """Get quality score distributions."""
    all_scores = []
    for job_data in _job_quality.values():
        all_scores.extend(job_data.get("quality_scores", []))

    if not all_scores:
        return {"total_scores": 0, "distribution": {}, "histogram": []}

    buckets = [0] * 10
    for s in all_scores:
        idx = min(9, int(s * 10))
        buckets[idx] += 1

    return {
        "total_scores": len(all_scores),
        "mean": sum(all_scores) / len(all_scores),
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
        return get_mock_segmented_metrics()

    from core.db import Sample, Dataset
    from sqlalchemy import select

    try:
        async with db_mgr.db.session_maker() as session:
            # Join Sample and Dataset to get quality scores and metadata
            stmt = select(Sample.quality_score, Sample.instruction, Sample.metadata_, Dataset.type).join(Dataset)
            result = await session.execute(stmt)
            samples = result.all()

            if not samples:
                return get_mock_segmented_metrics()

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
        return get_mock_segmented_metrics()


def get_mock_segmented_metrics():
    return {
        "dataset_types": {
            "sft": {"avg": 0.825, "count": 450},
            "rag": {"avg": 0.885, "count": 320},
            "coding": {"avg": 0.795, "count": 210},
            "reasoning": {"avg": 0.865, "count": 180},
            "conversational": {"avg": 0.840, "count": 80}
        },
        "prompt_lengths": {
            "short": {"avg": 0.812, "count": 340},
            "medium": {"avg": 0.854, "count": 680},
            "long": {"avg": 0.835, "count": 220}
        },
        "domains": {
            "medicine": {"avg": 0.875, "count": 150},
            "finance": {"avg": 0.862, "count": 200},
            "coding": {"avg": 0.795, "count": 210},
            "physics": {"avg": 0.890, "count": 100},
            "general": {"avg": 0.832, "count": 580}
        }
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