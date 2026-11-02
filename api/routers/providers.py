"""Providers routing and status endpoints for RasoSynthTune."""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from api.auth import User, UserRole, get_current_user, require_role
from api.legacy_schemas import ProviderStatus, ProviderTestRequest, ProviderTestResponse
from providers.core_lib.base import TaskType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Providers"])


@router.get("/providers", response_model=list[ProviderStatus])
async def list_providers(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """List all configured providers with performance stats."""
    router_inst = getattr(request.app.state, "router", None)
    if not router_inst:
        raise HTTPException(status_code=503, detail="Router not initialized")

    try:
        stats = router_inst.get_stats()
        providers = []

        for name, data in stats.items():
            reqs = int(data.get("requests", 0))
            providers.append(
                ProviderStatus(
                    name=name,
                    status=(
                        "available"
                        if data.get("available") is True
                        else "degraded"
                        if data.get("available") is False
                        else "unknown"
                    ),
                    latency_ms=data.get("avg_latency_ms"),
                    cost_per_token=data.get("cost_per_token", 0.0),
                    requests_today=reqs,
                    tokens_today=int(data.get("total_tokens", 0)),
                    cost_today_usd=float(data.get("total_cost_usd", 0.0)),
                    success_rate=(
                        float(data["success_rate"])
                        if reqs > 0 and data.get("success_rate") is not None
                        else None
                    ),
                )
            )

        return providers
    except Exception as e:
        logger.error(f"Failed to fetch provider stats: {e}")
        raise HTTPException(status_code=503, detail="Provider stats unavailable")


@router.get("/providers/techniques")
async def get_provider_techniques(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get recommended techniques for each task type."""
    router_inst = getattr(request.app.state, "router", None)
    if not router_inst:
        return {}

    techniques = {}
    for task_type in TaskType:
        info = router_inst.get_techniques_for_task(task_type)
        techniques[task_type.value] = info

    return techniques


@router.get("/health/circuit-breakers", tags=["Health"])
@router.get("/providers/circuit-breakers")
async def get_circuit_breakers_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get circuit breaker statuses for configured providers."""
    failover_engine = getattr(request.app.state, "failover_engine", None)
    if not failover_engine or not hasattr(failover_engine, "circuit_breakers"):
        return {}
    return {
        name: cb.state.value if hasattr(cb.state, "value") else str(cb.state)
        for name, cb in failover_engine.circuit_breakers.items()
    }


@router.get("/providers/{provider_name}", response_model=ProviderStatus)
async def get_provider(
    provider_name: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get single provider status and performance statistics."""
    router_inst = getattr(request.app.state, "router", None)
    if not router_inst:
        raise HTTPException(status_code=503, detail="Router not initialized")
    stats = router_inst.get_stats()
    resolved = router_inst._resolve_alias(provider_name) if hasattr(router_inst, "_resolve_alias") else provider_name
    data = stats.get(provider_name) or stats.get(resolved)
    if not data:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    return ProviderStatus(
        name=provider_name,
        status=(
            "available"
            if data.get("available") is True
            else "degraded"
            if data.get("available") is False
            else "unknown"
        ),
        latency_ms=data.get("avg_latency_ms"),
        cost_per_token=data.get("cost_per_token", 0.0),
        requests_today=data.get("requests", 0),
        tokens_today=data.get("total_tokens", 0),
        cost_today_usd=data.get("total_cost_usd", 0.0),
        success_rate=(data.get("success_rate") if data.get("requests", 0) > 0 else None),
    )


@router.get("/providers/{provider_name}/metrics")
async def get_provider_metrics(
    provider_name: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get granular performance metrics for a specific provider."""
    router_inst = getattr(request.app.state, "router", None)
    failover_engine = getattr(request.app.state, "failover_engine", None)
    if not router_inst:
        raise HTTPException(status_code=503, detail="Router not initialized")
    stats = router_inst.get_stats()
    resolved = router_inst._resolve_alias(provider_name) if hasattr(router_inst, "_resolve_alias") else provider_name
    data = stats.get(provider_name) or stats.get(resolved)
    if not data:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
    cb_state = "unknown"
    if failover_engine and hasattr(failover_engine, "circuit_breakers") and resolved in failover_engine.circuit_breakers:
        cb = failover_engine.circuit_breakers[resolved]
        cb_state = cb.state.value if hasattr(cb.state, "value") else str(cb.state)
    return {
        "provider": provider_name,
        "metrics": data,
        "circuit_breaker": cb_state,
    }


@router.patch("/providers/{provider_name}")
async def update_provider(
    provider_name: str,
    request: Request,
    payload: dict = Body(...),
    admin_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Replace the router's provider priority order."""
    router_inst = getattr(request.app.state, "router", None)
    if not router_inst:
        raise HTTPException(status_code=503, detail="Router not initialized")
    resolved = router_inst._resolve_alias(provider_name) if hasattr(router_inst, "_resolve_alias") else provider_name
    if resolved not in router_inst._providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    priority = payload.get("priority")
    if not isinstance(priority, list) or not priority or not all(isinstance(n, str) for n in priority):
        raise HTTPException(status_code=400, detail="payload.priority must be a non-empty list of provider names")
    unknown = [n for n in priority if n not in router_inst._providers]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown provider(s) in priority list: {unknown}")
    router_inst.config.provider_priority = list(priority)
    logger.info("Updated provider priority order to %s (requested via provider %s)", priority, provider_name)
    return {"status": "updated", "provider": provider_name, "provider_priority": list(priority)}


@router.post("/providers/test", response_model=ProviderTestResponse)
async def test_provider(
    test_req: ProviderTestRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Test connectivity to a specific provider."""
    router_inst = getattr(fastapi_request.app.state, "router", None)
    if not router_inst:
        raise HTTPException(status_code=500, detail="Router not initialized")

    start_time = time.perf_counter()
    try:
        success = await router_inst.test_provider(test_req.provider)
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ProviderTestResponse(
            provider=test_req.provider,
            success=success,
            latency_ms=latency_ms,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ProviderTestResponse(
            provider=test_req.provider,
            success=False,
            latency_ms=latency_ms,
            error=str(e),
        )
