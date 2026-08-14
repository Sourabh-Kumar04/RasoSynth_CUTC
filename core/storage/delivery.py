"""
Dataset Delivery Management System

Orchestrates the complete delivery pipeline from packaging to notification.
"""

import asyncio
import json
import time
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from core.storage.base import (
    StorageProvider,
    StorageConfig,
    StorageResult,
    StorageProviderType,
    DeliveryStrategy,
    DeliveryRequest,
    ProgressTracker,
    DeliveryProgress,
)
from core.storage.packaging import DatasetPackager, PackagingConfig, PackageManifest
from core.storage.streaming import StreamManager, StreamConfig, StreamingDataset
from core.storage.security import SignedURLGenerator, AccessController


class DeliveryStatus(Enum):
    """Status of delivery operations."""
    PENDING = "pending"
    PREPARING = "preparing"
    PACKAGING = "packaging"
    UPLOADING = "uploading"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DeliveryInfo:
    """Complete delivery information."""
    delivery_id: str
    dataset_id: str
    dataset_name: str
    status: DeliveryStatus
    strategy: DeliveryStrategy
    destination_type: StorageProviderType
    destination_location: Optional[str] = None
    download_url: Optional[str] = None
    signed_url: Optional[str] = None
    manifest: Optional[PackageManifest] = None
    progress: Optional[DeliveryProgress] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DeliveryManager:
    """Complete dataset delivery orchestration."""

    def __init__(
        self,
        config: dict = None,
        progress_tracker: ProgressTracker = None
    ):
        self.config = config or {}
        self.progress_tracker = progress_tracker or ProgressTracker()
        self.packager = DatasetPackager(PackagingConfig())
        self.stream_manager = StreamManager()
        self.access_controller = AccessController()
        self.signed_url_generator = SignedURLGenerator()
        self._deliveries: dict[str, DeliveryInfo] = {}
        self._providers: dict[StorageProviderType, StorageProvider] = {}

    def register_provider(self, provider: StorageProvider) -> None:
        """Register a storage provider."""
        self._providers[provider.provider_type] = provider

    def get_provider(self, provider_type: StorageProviderType) -> Optional[StorageProvider]:
        """Get a registered provider."""
        return self._providers.get(provider_type)

    async def deliver(
        self,
        request: DeliveryRequest,
        dataset: list[dict] | StreamingDataset
    ) -> DeliveryInfo:
        """Execute complete delivery pipeline."""
        import uuid

        delivery_id = str(uuid.uuid4())
        info = DeliveryInfo(
            delivery_id=delivery_id,
            dataset_id=request.dataset_id,
            dataset_name=request.dataset_name,
            status=DeliveryStatus.PENDING,
            strategy=request.strategy,
            destination_type=request.destination,
            metadata=request.__dict__,
        )

        self._deliveries[delivery_id] = info

        try:
            # Phase 1: Prepare
            info.status = DeliveryStatus.PREPARING
            self._update_progress(delivery_id, 0.0)

            # Phase 2: Package
            info.status = DeliveryStatus.PACKAGING
            manifest = await self._package_dataset(dataset, request)
            info.manifest = manifest

            # Phase 3: Upload
            info.status = DeliveryStatus.UPLOADING
            result = await self._upload_package(manifest, request)
            info.destination_location = result.location

            # Phase 4: Post-processing
            info.status = DeliveryStatus.VERIFYING

            # Generate download URL
            if request.destination_config.get("generate_link", True):
                info.download_url = result.location
                info.signed_url = await self._generate_access_link(
                    result.location,
                    request.destination,
                    request.expiration_hours
                )

            # Phase 5: Notify
            if request.notify_on_complete and request.webhook_url:
                await self._send_notification(request, info)

            info.status = DeliveryStatus.COMPLETED
            info.completed_at = datetime.utcnow()
            self._update_progress(delivery_id, 100.0)

        except Exception as e:
            info.status = DeliveryStatus.FAILED
            info.errors.append(str(e))

        return info

    async def deliver_streaming(
        self,
        request: DeliveryRequest,
        stream: AsyncIterator[dict]
    ) -> DeliveryInfo:
        """Deliver dataset from streaming source."""
        import uuid

        delivery_id = str(uuid.uuid4())
        info = DeliveryInfo(
            delivery_id=delivery_id,
            dataset_id=request.dataset_id,
            dataset_name=request.dataset_name,
            status=DeliveryStatus.PREPARING,
            strategy=request.strategy,
            destination_type=request.destination,
        )

        self._deliveries[delivery_id] = info

        try:
            info.status = DeliveryStatus.PACKAGING

            # Stream package
            stream_gen, manifest = await self.packager.package_streaming(
                stream,
                request.dataset_name
            )
            info.manifest = manifest

            info.status = DeliveryStatus.UPLOADING
            result = await self._upload_stream(stream_gen, request)

            info.destination_location = result.location
            info.download_url = result.location

            if request.expiration_hours:
                info.signed_url = await self._generate_access_link(
                    result.location,
                    request.destination,
                    request.expiration_hours
                )

            info.status = DeliveryStatus.COMPLETED
            info.completed_at = datetime.utcnow()

        except Exception as e:
            info.status = DeliveryStatus.FAILED
            info.errors.append(str(e))

        return info

    async def deliver_multipart(
        self,
        request: DeliveryRequest,
        dataset: list[dict]
    ) -> DeliveryInfo:
        """Deliver large dataset using multipart upload."""
        import uuid

        delivery_id = str(uuid.uuid4())
        info = DeliveryInfo(
            delivery_id=delivery_id,
            dataset_id=request.dataset_id,
            dataset_name=request.dataset_name,
            status=DeliveryStatus.PREPARING,
            strategy=DeliveryStrategy.CLOUD_STORAGE,
            destination_type=request.destination,
        )

        self._deliveries[delivery_id] = info

        try:
            info.status = DeliveryStatus.PACKAGING

            # Create sharded dataset
            shard_paths = await self.packager.create_sharded_dataset(
                dataset,
                shard_size_mb=self.config.get("shard_size_mb", 500)
            )

            # Upload each shard
            total_shards = len(shard_paths)
            for i, shard_path in enumerate(shard_paths):
                provider = self.get_provider(request.destination)
                if not provider:
                    raise Exception(f"Provider {request.destination} not registered")

                destination = f"{request.dataset_name}/shards/{shard_path.split('/')[-1]}"

                result = await provider.multipart_upload(
                    shard_path,
                    destination,
                    progress_callback=lambda uploaded, total: self._update_progress(
                        delivery_id,
                        ((i + uploaded/total) / total_shards) * 100
                    )
                )

                if not result.success:
                    raise Exception(f"Shard {i} upload failed: {result.errors}")

            info.status = DeliveryStatus.COMPLETED
            info.completed_at = datetime.utcnow()
            info.metadata["shard_count"] = total_shards

        except Exception as e:
            info.status = DeliveryStatus.FAILED
            info.errors.append(str(e))

        return info

    async def _package_dataset(
        self,
        dataset: list[dict] | StreamingDataset,
        request: DeliveryRequest
    ) -> PackageManifest:
        """Package dataset for delivery."""
        if isinstance(dataset, StreamingDataset):
            # Already packaged
            return PackageManifest(
                package_id="streaming",
                created_at=datetime.utcnow(),
                dataset_name=request.dataset_name,
                version="1.0.0",
                total_size_bytes=0,
                compressed_size_bytes=0,
                compression_ratio=0,
                file_count=0,
                chunk_count=0,
                shard_count=0,
                checksum="",
                compression=request.compression,
                partitioning="streaming",
            )
        else:
            return await self.packager.package(
                dataset,
                request.dataset_name,
                version="1.0.0"
            )

    async def _upload_package(
        self,
        manifest: PackageManifest,
        request: DeliveryRequest
    ) -> StorageResult:
        """Upload packaged dataset."""
        provider = self.get_provider(request.destination)
        if not provider:
            raise Exception(f"Provider {request.destination} not configured")

        # Read archive file
        with open(manifest.archive_path, 'rb') as f:
            data = f.read()

        destination = f"{request.dataset_name}/{manifest.package_id}"

        return await provider.upload(
            data,
            destination,
            metadata={
                "dataset_name": request.dataset_name,
                "manifest_id": manifest.package_id,
                "compression": manifest.compression,
            }
        )

    async def _upload_stream(
        self,
        stream: AsyncIterator[bytes],
        request: DeliveryRequest
    ) -> StorageResult:
        """Upload from stream."""
        provider = self.get_provider(request.destination)
        if not provider:
            raise Exception(f"Provider {request.destination} not configured")

        return await provider.upload(
            stream,
            request.dataset_name,
            metadata={"streaming": "true"}
        )

    async def _generate_access_link(
        self,
        location: str,
        provider_type: StorageProviderType,
        expiration_hours: Optional[int]
    ) -> Optional[str]:
        """Generate access link for download."""
        provider = self.get_provider(provider_type)
        if not provider or not hasattr(provider, 'generate_signed_url'):
            return location

        expiration = expiration_hours or 24
        return await provider.generate_signed_url(location, expiration * 3600)

    async def _send_notification(
        self,
        request: DeliveryRequest,
        info: DeliveryInfo
    ) -> None:
        """Send delivery notification."""
        from core.storage.providers.messaging import WebhookProvider

        webhook = WebhookProvider(StorageConfig(
            provider_type=StorageProviderType.WEBHOOK,
            credentials={"webhook_url": request.webhook_url}
        ))

        await webhook.send_delivery_notification(
            webhook_url=request.webhook_url,
            dataset_id=request.dataset_id,
            status=info.status.value,
            download_url=info.signed_url or info.download_url,
            error=info.errors[0] if info.errors else None
        )

    def _update_progress(self, delivery_id: str, progress: float) -> None:
        """Update delivery progress."""
        if delivery_id in self._deliveries:
            info = self._deliveries[delivery_id]
            if info.progress is None:
                info.progress = DeliveryProgress(
                    delivery_id=delivery_id,
                    status=info.status.value,
                    progress_percent=progress,
                    bytes_uploaded=0,
                    total_bytes=0,
                    upload_speed_mbps=0,
                    estimated_time_remaining_seconds=0,
                    current_chunk=0,
                    total_chunks=0,
                    started_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            else:
                info.progress.progress_percent = progress
                info.progress.updated_at = datetime.utcnow()

    def get_delivery(self, delivery_id: str) -> Optional[DeliveryInfo]:
        """Get delivery information."""
        return self._deliveries.get(delivery_id)

    def list_deliveries(self, status: Optional[DeliveryStatus] = None) -> list[DeliveryInfo]:
        """List all deliveries."""
        if status:
            return [d for d in self._deliveries.values() if d.status == status]
        return list(self._deliveries.values())

    async def cancel_delivery(self, delivery_id: str) -> bool:
        """Cancel a delivery."""
        if delivery_id in self._deliveries:
            self._deliveries[delivery_id].status = DeliveryStatus.CANCELLED
            return True
        return False


class MultiDestinationDelivery:
    """Deliver to multiple destinations simultaneously."""

    def __init__(self, delivery_manager: DeliveryManager):
        self.delivery_manager = delivery_manager

    async def deliver_to_all(
        self,
        dataset: list[dict],
        request: DeliveryRequest,
        destinations: list[StorageProviderType]
    ) -> dict[StorageProviderType, DeliveryInfo]:
        """Deliver dataset to multiple destinations."""
        results = {}

        # Create tasks for parallel delivery
        tasks = []
        for dest in destinations:
            dest_request = DeliveryRequest(
                dataset_id=request.dataset_id,
                dataset_name=request.dataset_name,
                destination=dest,
                destination_config=request.destination_config,
                format=request.format,
                compression=request.compression,
                strategy=request.strategy,
            )

            task = self.delivery_manager.deliver(dest_request, dataset)
            tasks.append((dest, task))

        # Execute in parallel
        for dest, task in tasks:
            try:
                results[dest] = await task
            except Exception as e:
                results[dest] = DeliveryInfo(
                    delivery_id="",
                    dataset_id=request.dataset_id,
                    dataset_name=request.dataset_name,
                    status=DeliveryStatus.FAILED,
                    strategy=request.strategy,
                    destination_type=dest,
                    errors=[str(e)]
                )

        return results