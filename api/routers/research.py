"""Autonomous research loop endpoints for RasoSynthTune."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth import User, get_current_user
from api.legacy_schemas import ResearchRequest, ResearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Research"])


def _research_cycle_status(results: dict) -> str:
    """One status rule for both research trigger endpoints."""
    return results.get("status") or "completed"


@router.post("/research", response_model=ResearchResponse)
async def trigger_research(
    request: ResearchRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Trigger autonomous research cycle."""
    research_loop = getattr(fastapi_request.app.state, "research_loop", None)
    if not research_loop:
        raise HTTPException(status_code=500, detail="Research loop not initialized")

    results = await research_loop.run_research_cycle()
    return ResearchResponse(
        techniques_discovered=results.get("techniques_discovered", []),
        papers_found=results.get("papers_found", []),
        updates_applied=results.get("updates_applied", []),
        status=_research_cycle_status(results),
    )


@router.get("/research/status")
async def get_research_status(
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get research loop status and history."""
    research_loop = getattr(fastapi_request.app.state, "research_loop", None)
    technique_integrator = getattr(fastapi_request.app.state, "technique_integrator", None)
    if not research_loop:
        return {"status": "disabled"}

    return {
        "enabled": True,
        "last_research": research_loop.last_research_time.isoformat() if research_loop.last_research_time else None,
        "research_history": research_loop.get_research_history(),
        "cached_techniques": research_loop.get_cached_techniques(),
        "applied_techniques": technique_integrator.get_applied_techniques() if technique_integrator else {},
        "active_heuristics": technique_integrator.get_active_heuristics() if technique_integrator else {},
    }


@router.post("/research/cycle", response_model=ResearchResponse)
async def trigger_research_cycle(
    fastapi_request: Request,
    request: Optional[ResearchRequest] = None,
    current_user: User = Depends(get_current_user),
):
    """Trigger an autonomous research cycle across ArXiv and Hugging Face."""
    research_loop = getattr(fastapi_request.app.state, "research_loop", None)
    if not research_loop:
        raise HTTPException(status_code=500, detail="Research loop not initialized")
    results = await research_loop.run_research_cycle()
    return ResearchResponse(
        techniques_discovered=results.get("techniques_discovered", []),
        papers_found=results.get("papers_found", []),
        updates_applied=results.get("updates_applied", []),
        status=_research_cycle_status(results),
    )


@router.get("/research/techniques")
async def get_research_techniques(
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get discovered and cached research techniques."""
    research_loop = getattr(fastapi_request.app.state, "research_loop", None)
    if not research_loop:
        return {"techniques": {}}
    return {
        "cached_techniques": research_loop.get_cached_techniques(),
        "history": research_loop.get_research_history(),
    }


@router.get("/research/heuristics")
async def get_research_heuristics(
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get active pipeline heuristics updated by the research loop."""
    technique_integrator = getattr(fastapi_request.app.state, "technique_integrator", None)
    if not technique_integrator:
        return {"heuristics": {}}
    return {
        "active_heuristics": technique_integrator.get_active_heuristics(),
        "applied_techniques": technique_integrator.get_applied_techniques(),
    }
