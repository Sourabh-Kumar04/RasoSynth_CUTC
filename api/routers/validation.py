"""Validation, adaptability, and compute settings endpoints for RasoSynthTune."""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel

from api.auth import User, UserRole, get_current_user, require_role
from api.legacy_schemas import AdaptabilityRequest, AdaptabilityResponse
from core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateComputeSettingsRequest(BaseModel):
    modal_token_id: Optional[str] = None
    modal_token_secret: Optional[str] = None
    runpod_api_key: Optional[str] = None
    hf_token: Optional[str] = None


@router.post("/adaptability", response_model=AdaptabilityResponse, tags=["Adaptability"])
async def analyze_adaptability(
    request: AdaptabilityRequest,
    current_user: User = Depends(get_current_user),
):
    """Analyze dataset feasibility under given constraints."""
    from core.orchestrator_core import ConstraintAnalyzer

    settings = get_settings()
    analyzer = ConstraintAnalyzer(settings.model_dump())
    analysis = await analyzer.analyze(request.constraints)

    return AdaptabilityResponse(
        recommended_strategies=analysis.fallback_strategies,
        estimated_feasibility=analysis.feasibility_score,
        warnings=analysis.warnings,
        fallback_options=analysis.fallback_strategies,
    )


@router.get("/settings/compute", tags=["Settings"])
async def get_compute_settings(current_user: User = Depends(get_current_user)):
    """Return cloud GPU provider configuration status (without exposing raw secrets)."""
    cfg = get_settings()
    m_id = os.getenv("MODAL_TOKEN_ID") or cfg.modal_token_id
    m_sec = os.getenv("MODAL_TOKEN_SECRET") or cfg.modal_token_secret
    r_key = os.getenv("RUNPOD_API_KEY") or cfg.runpod_api_key
    h_tok = os.getenv("HF_TOKEN") or cfg.hf_token

    result: dict = {
        "modal_configured": bool(m_id and m_sec),
        "runpod_configured": bool(r_key),
        "hf_configured": bool(h_tok),
        "available_targets": ["local", "modal", "runpod", "serverless"],
    }
    if current_user.role == UserRole.ADMIN:
        result.update({
            "modal_token_id_masked": f"{m_id[:4]}...{m_id[-4:]}" if m_id and len(m_id) > 8 else ("configured" if m_id else None),
            "runpod_key_masked": f"{r_key[:4]}...{r_key[-4:]}" if r_key and len(r_key) > 8 else ("configured" if r_key else None),
            "hf_token_masked": f"{h_tok[:4]}...{h_tok[-4:]}" if h_tok and len(h_tok) > 8 else ("configured" if h_tok else None),
        })
    return result


@router.post("/settings/compute", tags=["Settings"])
async def update_compute_settings(
    payload: UpdateComputeSettingsRequest,
    admin_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Update runtime cloud compute and HuggingFace tokens."""
    cfg = get_settings()
    if payload.modal_token_id:
        os.environ["MODAL_TOKEN_ID"] = payload.modal_token_id
        cfg.modal_token_id = payload.modal_token_id
    if payload.modal_token_secret:
        os.environ["MODAL_TOKEN_SECRET"] = payload.modal_token_secret
        cfg.modal_token_secret = payload.modal_token_secret
    if payload.runpod_api_key:
        os.environ["RUNPOD_API_KEY"] = payload.runpod_api_key
        cfg.runpod_api_key = payload.runpod_api_key
    if payload.hf_token:
        os.environ["HF_TOKEN"] = payload.hf_token
        cfg.hf_token = payload.hf_token
    return {
        "status": "success",
        "message": "Compute settings successfully updated in runtime memory.",
        "modal_configured": bool(os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET")),
        "runpod_configured": bool(os.getenv("RUNPOD_API_KEY")),
        "hf_configured": bool(os.getenv("HF_TOKEN")),
    }


@router.post("/validate", tags=["Validation"])
@router.post("/validate/dataset", tags=["Validation"])
async def validate_dataset_request(
    payload: dict = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),
):
    """Validate dataset generation request configuration prior to pipeline execution."""
    errors = []
    warnings = []

    query = payload.get("query") or (payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}).get("query")
    if not query or not str(query).strip():
        errors.append("Dataset query prompt is required and cannot be empty.")
    elif len(str(query).strip()) < 3:
        errors.append("Query prompt must be at least 3 characters long.")
    elif len(str(query).strip()) > 5000:
        errors.append("Query prompt exceeds 5000 character maximum limit.")

    samples = payload.get("target_samples") or (payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}).get("target_samples")
    if samples is not None:
        try:
            samples_num = int(samples)
            if samples_num <= 0:
                errors.append("target_samples must be a positive integer.")
            elif samples_num > 50000:
                warnings.append("Generating >50,000 samples may require distributed Ray/Celery worker pools.")
        except (ValueError, TypeError):
            errors.append("target_samples must be a valid integer.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
