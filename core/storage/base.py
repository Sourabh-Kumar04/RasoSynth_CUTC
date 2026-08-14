"""
Storage Provider Base Infrastructure

Defines the core abstractions for the distributed storage system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional
from datetime import datetime
import hashlib
import json


class DeliveryStrategy(Enum):
    """Delivery strategy based on dataset characteristics."""
    DIRECT_DOWNLOAD = "direct_download"  # <1GB
    COMPRESSED_ARCHIVE = "compressed_archive"  # 1-20GB
    CLOUD_STORAGE = "cloud_storage"  # 20GB-1TB
    DISTRIBUTED_STREAM = "distributed_stream"  # >1TB
    REGISTRY_SYNC = "registry_sync"  # Continuously updated
    MULTI_DESTINATION = "multi_destination"  # Multiple destinations


class StorageProviderType(Enum):
    """Types of storage providers."""
    # Cloud
    AWS_S3 = "aws_s3"
    GOOGLE_GCS = "google_gcs"
    CLOUDFLARE_R2 = "cloudflare_r2"
    AZURE_BLOB = "azure_blob"
    BACKBLAZE_B2 = "backblaze_b2"
    MINIO = "minio"

    # Consumer
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    MEGA = "mega"

    # AI Platforms
    HUGGINGFACE = "huggingface"
    KAGGLE = "kaggle"
    GITHUB = "github"
    DVC = "dvc"

    # Messaging
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass
class StorageConfig:
    """Configuration for storage providers."""
    provider_type: StorageProviderType
    credentials: dict[str, str] = field(default_factory=dict)
    region: str = "us-east-1"
    bucket: str = ""
    endpoint: str = ""
    encryption: str = "AES256"
    storage_class: str = "STANDARD"
    metadata: dict[str, str] = field(default_factory=dict)
    # Performance settings
    max_connections: int = 10
    chunk_size_mb: int = 50
    multipart_threshold_mb: int = 100
    multipart_chunk_mb: int = 50
    # Retry settings
    max_retries: int = 5
    retry_delay_seconds: float = 1.0


@dataclass
class StorageMetadata:
    """Metadata for stored objects."""
    key: str
    size_bytes: int
    content_type: str
    created_at: datetime
    modified_at: datetime
    checksum: str
    storage_class: str
    region: str
    bucket: str
    version_id: Optional[str] = None
    encryption: str = "AES256"
    custom_metadata: dict[str, str] = field(default_factory=dict)
    # Distribution metadata
    download_count: int = 0
    last_accessed: Optional[datetime] = None
    access_level: str = "private"


@dataclass
class StorageResult:
    """Result of storage operations."""
    success: bool
    location: str
    metadata: Optional[StorageMetadata] = None
    size_bytes: int = 0
    duration_ms: float = 0.0
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # For multipart operations
    parts_completed: int = 0
    total_parts: int = 0
    resume_token: Optional[str] = None


@dataclass
class DatasetPackage:
    """Packaged dataset for delivery."""
    format: str
    compression: str
    total_size_bytes: int
    compressed_size_bytes: int
    chunk_count: int
    chunk_size_bytes: int
    checksum: str
    manifest: dict
    archive_path: str
    estimated_download_time_minutes: float


@dataclass
class DeliveryRequest:
    """Request for dataset delivery."""
    dataset_id: str
    dataset_name: str
    destination: StorageProviderType
    destination_config: dict
    format: str
    compression: str = "zstd"
    strategy: DeliveryStrategy = DeliveryStrategy.CLOUD_STORAGE
    include_metadata: bool = True
    include_documentation: bool = True
    encryption_enabled: bool = False
    access_level: str = "private"
    expiration_hours: Optional[int] = None
    notify_on_complete: bool = True
    webhook_url: Optional[str] = None


@dataclass
class DeliveryProgress:
    """Progress tracking for deliveries."""
    delivery_id: str
    status: str  # "preparing", "uploading", "verifying", "completed", "failed"
    progress_percent: float
    bytes_uploaded: int
    total_bytes: int
    upload_speed_mbps: float
    estimated_time_remaining_seconds: float
    current_chunk: int
    total_chunks: int
    started_at: datetime
    updated_at: datetime
    errors: list[str] = field(default_factory=list)


class ProgressTracker:
    """Track progress of storage operations."""

    def __init__(self):
        self._tracking: dict[str, DeliveryProgress] = {}

    def start(self, delivery_id: str, total_bytes: int) -> DeliveryProgress:
        """Start tracking a delivery."""
        progress = DeliveryProgress(
            delivery_id=delivery_id,
            status="preparing",
            progress_percent=0.0,
            bytes_uploaded=0,
            total_bytes=total_bytes,
            upload_speed_mbps=0.0,
            estimated_time_remaining_seconds=0.0,
            current_chunk=0,
            total_chunks=0,
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._tracking[delivery_id] = progress
        return progress

    def update(
        self,
        delivery_id: str,
        bytes_uploaded: int,
        current_chunk: int = 0,
        speed_mbps: float = 0.0
    ) -> DeliveryProgress:
        """Update progress."""
        if delivery_id in self._tracking:
            progress = self._tracking[delivery_id]
            progress.bytes_uploaded = bytes_uploaded
            progress.current_chunk = current_chunk
            progress.upload_speed_mbps = speed_mbps
            progress.progress_percent = (bytes_uploaded / max(progress.total_bytes, 1)) * 100
            progress.updated_at = datetime.utcnow()

            remaining = progress.total_bytes - bytes_uploaded
            if speed_mbps > 0:
                progress.estimated_time_remaining_seconds = (remaining / (speed_mbps * 1024 * 1024))

        return self._tracking.get(delivery_id)

    def complete(self, delivery_id: str) -> DeliveryProgress:
        """Mark delivery as complete."""
        if delivery_id in self._tracking:
            self._tracking[delivery_id].status = "completed"
            self._tracking[delivery_id].progress_percent = 100.0
            self._tracking[delivery_id].updated_at = datetime.utcnow()
        return self._tracking.get(delivery_id)

    def fail(self, delivery_id: str, error: str) -> DeliveryProgress:
        """Mark delivery as failed."""
        if delivery_id in self._tracking:
            self._tracking[delivery_id].status = "failed"
            self._tracking[delivery_id].errors.append(error)
            self._tracking[delivery_id].updated_at = datetime.utcnow()
        return self._tracking.get(delivery_id)

    def get(self, delivery_id: str) -> Optional[DeliveryProgress]:
        """Get progress."""
        return self._tracking.get(delivery_id)

    def list_active(self) -> list[DeliveryProgress]:
        """List active deliveries."""
        return [p for p in self._tracking.values() if p.status in ["preparing", "uploading", "verifying"]]


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    provider_type: StorageProviderType = StorageProviderType.AWS_S3

    def __init__(self, config: StorageConfig):
        self.config = config
        self.progress_tracker = ProgressTracker()

    @abstractmethod
    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload data to storage."""
        pass

    @abstractmethod
    async def download(
        self,
        source: str,
        destination_path: Optional[str] = None
    ) -> StorageResult:
        """Download data from storage."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete data from storage."""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if path exists."""
        pass

    @abstractmethod
    async def get_metadata(self, path: str) -> Optional[StorageMetadata]:
        """Get metadata for path."""
        pass

    @abstractmethod
    async def list_objects(self, prefix: str = "") -> list[str]:
        """List objects with prefix."""
        pass

    async def generate_signed_url(
        self,
        path: str,
        expiration_seconds: int = 3600
    ) -> Optional[str]:
        """Generate a signed URL for temporary access."""
        return None

    async def multipart_upload(
        self,
        file_path: str,
        destination: str,
        progress_callback: Optional[callable] = None
    ) -> StorageResult:
        """Upload a file using multipart upload."""
        pass

    async def resume_upload(
        self,
        resume_token: str
    ) -> StorageResult:
        """Resume an interrupted multipart upload."""
        pass

    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate SHA256 checksum."""
        return hashlib.sha256(data).hexdigest()

    def _estimate_cost(self, size_bytes: int, storage_class: str = "STANDARD") -> float:
        """Estimate storage cost."""
        # Simplified pricing (per GB per month)
        pricing = {
            "STANDARD": 0.023,
            "INTELLIGENT_TIERING": 0.012,
            "GLACIER": 0.004,
            "DEEP_ARCHIVE": 0.00099,
        }
        price_per_gb = pricing.get(storage_class, 0.023)
        return (size_bytes / (1024**3)) * price_per_gb