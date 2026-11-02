"""Agents endpoints for RasoSynthTune multi-agent society and domain discovery."""
from __future__ import annotations

import logging
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agents"])


class DomainAnalysisRequest(BaseModel):
    """Payload for autonomous domain discovery."""
    prompt: str = Field(..., min_length=3, description="User prompt describing the dataset task")
    target_domain: Optional[str] = Field(default=None, description="Optional seed domain")
    language: Optional[str] = Field(default="en", description="Target language code")


def _get_server_module():
    return sys.modules.get("api.server")


@router.get("/agents")
async def list_registered_agents(current_user: User = Depends(get_current_user)):
    """List all registered agent types and capabilities in the multi-agent society."""
    try:
        from agents.registry import AgentRegistry
        registrations = AgentRegistry.list_registrations()
        return {
            "agents": [
                {
                    "type": r.agent_type.value,
                    "name": r.name,
                    "description": r.description,
                    "capabilities": [c.value for c in r.capabilities],
                    "version": r.version,
                    "author": r.author,
                }
                for r in registrations
            ],
            "total": len(registrations),
        }
    except Exception as exc:
        logger.error("Failed to query agent registry: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to query agent registry")


@router.get("/agents/stats")
async def get_agent_stats(current_user: User = Depends(get_current_user)):
    """Get statistics on registered and active agent instances."""
    try:
        from agents.registry import AgentRegistry
        return AgentRegistry.get_stats()
    except Exception as exc:
        logger.error("Failed to query agent stats: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to query agent stats")


@router.post("/agent/analyze-domain")
@router.post("/api/agent/analyze-domain")
async def agent_analyze_domain(
    request: DomainAnalysisRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Autonomous Semantic Discovery Agent:
    Discovers canonical domain, preserved terms (syntactic invariants), and anti-domains
    directly from user instructions.
    """
    from core.domain_agent import analyze_dataset_domain, heuristic_domain_refinement

    server_mod = _get_server_module()
    orch = getattr(req.app.state, "orchestrator", None) or (
        getattr(server_mod, "orchestrator", None) if server_mod else None
    )
    router_inst = (
        getattr(orch, "router", None)
        if orch
        else getattr(req.app.state, "router", None)
        or (getattr(server_mod, "router", None) if server_mod else None)
    )
    cache = getattr(req.app.state, "cache", None) or (
        getattr(server_mod, "cache", None) if server_mod else None
    )
    redis_client = getattr(cache, "redis", None) if cache else None

    try:
        result = await analyze_dataset_domain(
            prompt=request.prompt,
            target_domain=request.target_domain,
            provider_router=router_inst,
            redis_client=redis_client,
        )
        return result
    except Exception as e:
        logger.exception("Domain analysis agent failed: %s", e)
        return heuristic_domain_refinement(request.prompt, request.target_domain)
