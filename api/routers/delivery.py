"""Delivery and packaging endpoints (ADR-002) for RasoSynthTune."""
from __future__ import annotations

import logging
import os
import sys

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth import User, UserRole, enforce_owner, get_current_user, require_role
from api.legacy_schemas import DeliveryRequestSchema, DeliveryResponseSchema
from core.storage.base import DeliveryRequest, DeliveryStrategy, StorageProviderType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Storage & Delivery"])

MAX_SAMPLE_LOAD_LIMIT = int(os.getenv("MAX_SAMPLE_LOAD_LIMIT", "10000"))


def _get_server_module():
    return sys.modules.get("api.server")


def _get_db(req: Request):
    server_mod = _get_server_module()
    return getattr(req.app.state, "db", None) or (
        getattr(server_mod, "db", None) if server_mod else None
    )


def _get_delivery_manager(req: Request):
    server_mod = _get_server_module()
    return getattr(req.app.state, "delivery_manager", None) or (
        getattr(server_mod, "delivery_manager", None) if server_mod else None
    )


@router.post("/datasets/{dataset_id}/deliver", response_model=DeliveryResponseSchema)
async def deliver_dataset(
    dataset_id: str,
    request: DeliveryRequestSchema,
    req: Request,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
):
    """Trigger ADR-002 packaging and delivery of a dataset."""
    delivery_manager = _get_delivery_manager(req)
    if not delivery_manager:
        raise HTTPException(status_code=503, detail="DeliveryManager is not initialized")
    db = _get_db(req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    dataset = await db.get_dataset(dataset_id)
    if not dataset:
        datasets_for_job = await db.get_datasets_by_job(dataset_id)
        if datasets_for_job:
            dataset = datasets_for_job[0]
    enforce_owner(dataset, current_user, resource_name="Dataset")

    samples = await db.get_samples(dataset_id, limit=MAX_SAMPLE_LOAD_LIMIT)
    if not samples:
        raise HTTPException(status_code=404, detail=f"No samples found for dataset {dataset_id}")

    dest_map = {
        "local": StorageProviderType.LOCAL if hasattr(StorageProviderType, "LOCAL") else StorageProviderType.HUGGINGFACE,
        "huggingface": StorageProviderType.HUGGINGFACE,
        "aws_s3": StorageProviderType.AWS_S3,
        "kaggle": StorageProviderType.KAGGLE,
    }
    destination = dest_map.get(request.destination.lower(), StorageProviderType.HUGGINGFACE)
    strat_map = {
        "direct": DeliveryStrategy.DIRECT,
        "streaming": DeliveryStrategy.STREAMING,
        "tiered": DeliveryStrategy.TIERED,
    }
    strategy = strat_map.get(request.strategy.lower(), DeliveryStrategy.DIRECT)

    deliv_req = DeliveryRequest(
        dataset_id=dataset_id,
        dataset_name=request.dataset_name or f"dataset_{dataset_id}",
        destination=destination,
        strategy=strategy,
        compression=request.compression,
    )

    try:
        delivery_info = await delivery_manager.deliver(deliv_req, samples)
        return DeliveryResponseSchema(
            delivery_id=delivery_info.delivery_id,
            dataset_id=delivery_info.dataset_id,
            dataset_name=delivery_info.dataset_name,
            status=delivery_info.status.value,
            download_url=delivery_info.download_url,
            signed_url=delivery_info.signed_url,
            created_at=delivery_info.created_at.isoformat(),
            manifest_chunks=delivery_info.manifest.chunk_count if delivery_info.manifest else 0,
            compression=request.compression,
        )
    except Exception as exc:
        logger.error("Delivery failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Delivery failed")


@router.get("/deliveries/{delivery_id}", response_model=DeliveryResponseSchema)
async def get_delivery_status(
    delivery_id: str,
    req: Request,
    current_user: User = Depends(get_current_user),
):
    """Get delivery operation status and download URLs."""
    delivery_manager = _get_delivery_manager(req)
    if not delivery_manager:
        raise HTTPException(status_code=503, detail="DeliveryManager is not initialized")
    delivery_info = delivery_manager.get_delivery(delivery_id)
    if not delivery_info:
        raise HTTPException(status_code=404, detail=f"Delivery {delivery_id} not found")

    return DeliveryResponseSchema(
        delivery_id=delivery_info.delivery_id,
        dataset_id=delivery_info.dataset_id,
        dataset_name=delivery_info.dataset_name,
        status=delivery_info.status.value,
        download_url=delivery_info.download_url,
        signed_url=delivery_info.signed_url,
        created_at=delivery_info.created_at.isoformat(),
        manifest_chunks=delivery_info.manifest.chunk_count if delivery_info.manifest else 0,
        compression=delivery_info.manifest.compression if delivery_info.manifest else "tar.zstd",
    )
