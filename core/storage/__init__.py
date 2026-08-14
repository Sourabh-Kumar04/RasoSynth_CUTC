"""
Dataset Output & Distribution System

A comprehensive, scalable framework for handling large dataset delivery
across multiple storage providers and formats.

Architecture:
- Storage abstraction layer for multiple providers
- Intelligent packaging and compression
- Streaming and chunked transfers
- Secure access control
- Versioning and incremental updates
- Multi-platform distribution
"""

from core.storage.base import (
    StorageProvider,
    StorageConfig,
    StorageResult,
    StorageMetadata,
    DeliveryStrategy,
)
from core.storage.providers import (
    # Cloud Providers
    S3StorageProvider,
    GCSStorageProvider,
    R2StorageProvider,
    AzureBlobProvider,
    B2StorageProvider,
    MinIOProvider,
    # Consumer Cloud
    GoogleDriveProvider,
    DropboxProvider,
    OneDriveProvider,
    MegaProvider,
    # AI Platforms
    HuggingFaceProvider,
    KaggleProvider,
    GitHubReleasesProvider,
    DVCProvider,
    # Messaging
    TelegramProvider,
    DiscordProvider,
    SlackProvider,
    EmailProvider,
    WebhookProvider,
)
from core.storage.packaging import (
    DatasetPackager,
    CompressionType,
    PartitionStrategy,
    ShardStrategy,
)
from core.storage.streaming import (
    StreamManager,
    ChunkIterator,
    RangeRequestHandler,
)
from core.storage.delivery import (
    DeliveryManager,
    DeliveryStatus,
    ProgressTracker,
)
from core.storage.security import (
    AccessController,
    EncryptionManager,
    SignedURLGenerator,
)
from core.storage.versioning import (
    DatasetVersionManager,
    IncrementalUpdater,
)
from core.storage.strategy import (
    DeliveryStrategySelector,
    SmartRouter,
)

__all__ = [
    # Base
    "StorageProvider",
    "StorageConfig",
    "StorageResult",
    "StorageMetadata",
    "DeliveryStrategy",

    # Providers
    "S3StorageProvider",
    "GCSStorageProvider",
    "R2StorageProvider",
    "AzureBlobProvider",
    "B2StorageProvider",
    "MinIOProvider",
    "GoogleDriveProvider",
    "DropboxProvider",
    "OneDriveProvider",
    "MegaProvider",
    "HuggingFaceProvider",
    "KaggleProvider",
    "GitHubReleasesProvider",
    "DVCProvider",
    "TelegramProvider",
    "DiscordProvider",
    "SlackProvider",
    "EmailProvider",
    "WebhookProvider",

    # Packaging
    "DatasetPackager",
    "CompressionType",
    "PartitionStrategy",
    "ShardStrategy",

    # Streaming
    "StreamManager",
    "ChunkIterator",
    "RangeRequestHandler",

    # Delivery
    "DeliveryManager",
    "DeliveryStatus",
    "ProgressTracker",

    # Security
    "AccessController",
    "EncryptionManager",
    "SignedURLGenerator",

    # Versioning
    "DatasetVersionManager",
    "IncrementalUpdater",

    # Strategy
    "DeliveryStrategySelector",
    "SmartRouter",
]