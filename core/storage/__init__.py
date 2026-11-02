"""
Dataset Output & Distribution System

A scalable framework for handling dataset delivery across multiple storage providers.
"""
from __future__ import annotations

import importlib
from typing import Any

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

_ATTR_TO_MODULE = {
    # Base
    "StorageProvider": "core.storage.base",
    "StorageConfig": "core.storage.base",
    "StorageResult": "core.storage.base",
    "StorageMetadata": "core.storage.base",
    "DeliveryStrategy": "core.storage.base",

    # Packaging
    "DatasetPackager": "core.storage.packaging",
    "CompressionType": "core.storage.packaging",
    "PartitionStrategy": "core.storage.packaging",
    "ShardStrategy": "core.storage.packaging",

    # Streaming
    "StreamManager": "core.storage.streaming",
    "ChunkIterator": "core.storage.streaming",
    "RangeRequestHandler": "core.storage.streaming",

    # Delivery
    "DeliveryManager": "core.storage.delivery",
    "DeliveryStatus": "core.storage.delivery",
    "ProgressTracker": "core.storage.delivery",

    # Security
    "AccessController": "core.storage.security",
    "EncryptionManager": "core.storage.security",
    "SignedURLGenerator": "core.storage.security",

    # Versioning
    "DatasetVersionManager": "core.storage.versioning",
    "IncrementalUpdater": "core.storage.versioning",

    # Strategy
    "DeliveryStrategySelector": "core.storage.strategy",
    "SmartRouter": "core.storage.strategy",
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_TO_MODULE:
        mod = importlib.import_module(_ATTR_TO_MODULE[name])
        val = getattr(mod, name)
        globals()[name] = val
        return val
    # Fallback for cloud providers
    try:
        providers_mod = importlib.import_module("core.storage.providers")
        if hasattr(providers_mod, name):
            val = getattr(providers_mod, name)
            globals()[name] = val
            return val
    except Exception:
        pass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
