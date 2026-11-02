"""Observability, traces, and metrics router for RasoSynthTune."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from api.auth import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Observability"])


def _get_server_module():
    return sys.modules.get("api.server")


def _get_observability(request: Request):
    server_mod = _get_server_module()
    return getattr(request.app.state, "observability", None) or (
        getattr(server_mod, "observability", None) if server_mod else None
    )


def _get_router(request: Request):
    server_mod = _get_server_module()
    return getattr(request.app.state, "router", None) or (
        getattr(server_mod, "router", None) if server_mod else None
    )


@router.get("/metrics")
async def metrics_endpoint(request: Request, current_user: User = Depends(get_current_user)):
    """Expose Prometheus metrics in text/plain format."""
    observability = _get_observability(request)
    try:
        from prometheus_client import CONTENT_TYPE_LATEST
        content = observability.get_prometheus_metrics() if observability else ""
        return Response(content=content, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.warning(f"Metrics export unavailable: {e}")
        raise HTTPException(status_code=503, detail=f"Metrics export unavailable: {e}")


@router.get("/metrics/history", tags=["Metrics"])
async def get_metrics_history(
    request: Request,
    time_range: str = Query(default="1h", alias="range"),
    current_user: User = Depends(get_current_user),
):
    """Get historical system telemetry metrics with dynamic UTC intervals and live trace telemetry."""
    now = datetime.now(timezone.utc)
    interval_minutes = 10 if time_range == "1h" else 60
    timestamps = [
        (now - timedelta(minutes=interval_minutes * i)).strftime("%H:%M")
        for i in reversed(range(7))
    ]

    observability = _get_observability(request)
    router_inst = _get_router(request)

    recent_traces = observability.get_traces(limit=100) if observability else []
    durations = [t["duration_ms"] for t in recent_traces if "duration_ms" in t]
    avg_lat = round(sum(durations) / len(durations), 1) if durations else None
    errors = sum(1 for t in recent_traces if t.get("status") == "error")
    err_rate = round(errors / len(recent_traces), 3) if recent_traces else None

    total_cost = 0.0
    if router_inst:
        try:
            stats = router_inst.get_stats()
            total_cost = sum(s.get("total_cost_usd", 0.0) for s in stats.values())
        except Exception:
            pass

    if recent_traces:
        lat_buckets = [[] for _ in range(7)]
        err_buckets = [0 for _ in range(7)]
        count_buckets = [0 for _ in range(7)]

        trace_now = datetime.now(timezone.utc)
        for t in recent_traces:
            t_created = t.get("created_at") or t.get("timestamp")
            if isinstance(t_created, str):
                try:
                    t_time = datetime.fromisoformat(t_created)
                except Exception:
                    t_time = trace_now
            elif isinstance(t_created, datetime):
                t_time = t_created
            else:
                t_time = trace_now

            if t_time.tzinfo is None:
                t_time = t_time.replace(tzinfo=timezone.utc)

            age_mins = max(0.0, (trace_now - t_time).total_seconds() / 60.0)
            b_idx = min(6, int(age_mins / max(interval_minutes, 1)))
            bucket_pos = 6 - b_idx
            if 0 <= bucket_pos < 7:
                count_buckets[bucket_pos] += 1
                if "duration_ms" in t:
                    lat_buckets[bucket_pos].append(t["duration_ms"])
                if t.get("status") == "error":
                    err_buckets[bucket_pos] += 1

        latency_series = [
            round(sum(b) / len(b), 1) if b else None
            for b in lat_buckets
        ]
        throughput_series = [
            count_buckets[i] if count_buckets[i] > 0 else None
            for i in range(7)
        ]
        error_series = [
            round(err_buckets[i] / count_buckets[i], 3) if count_buckets[i] > 0 else None
            for i in range(7)
        ]
        series_basis = "real_bucket_observations"
    else:
        latency_series = [None] * 7
        throughput_series = [None] * 7
        error_series = [None] * 7
        series_basis = "no_data"

    cost_series = [round(total_cost * (i + 1) / 7, 3) for i in range(7)] if total_cost > 0 else [None] * 7

    return {
        "timestamps": timestamps,
        "latency": latency_series,
        "throughput": throughput_series,
        "error_rate": error_series,
        "cost": cost_series,
        "has_data": bool(recent_traces),
        "series_basis": series_basis,
        "avg_latency_ms": avg_lat,
        "error_rate_value": err_rate,
    }


@router.get("/metrics/tokenizer-fertility", tags=["Metrics"])
async def get_tokenizer_fertility_metrics(
    language: str = Query(default="en"),
    script_mode: str = Query(default="native"),
    current_user: User = Depends(get_current_user),
):
    """Estimate tokenizer fertility and token efficiency across foundation models."""
    from core.tokenizer_metrics import estimate_tokenizer_fertility
    return estimate_tokenizer_fertility(language=language, script_mode=script_mode)


@router.get("/observability/langsmith")
async def langsmith_status(request: Request, current_user: User = Depends(get_current_user)):
    """Expose LangSmith tracing and monitoring connection status."""
    observability = _get_observability(request)
    if not observability or not hasattr(observability, "langsmith"):
        return {"status": "disabled", "available": False, "enabled": False}
    return observability.langsmith.get_status()


@router.get("/traces")
async def get_traces(
    request: Request,
    service: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Retrieve recent traces from the observability ring buffer."""
    observability = _get_observability(request)
    traces = observability.get_traces(service=service, limit=limit) if observability else []
    return {"traces": traces}


@router.get("/traces/correlation")
async def get_traces_by_correlation(
    request: Request,
    correlation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve traces matching a specific correlation ID."""
    observability = _get_observability(request)
    traces = observability.get_traces(correlation_id=correlation_id) if observability else []
    return {"traces": traces}


@router.get("/traces/{trace_id}")
async def get_trace(
    request: Request,
    trace_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve a specific trace or span by trace_id or span id."""
    observability = _get_observability(request)
    if not observability:
        raise HTTPException(status_code=404, detail="Observability not initialized")
    trace = observability.get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return trace


@router.get("/cluster/ray")
async def get_ray_cluster_status(current_user: User = Depends(get_current_user)):
    """Get Ray distributed GPU and compute cluster worker status."""
    try:
        from workers.ray_pipeline import get_ray_status
        return get_ray_status()
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "nodes": 0,
            "available_cpus": 0,
            "available_gpus": 0,
        }
