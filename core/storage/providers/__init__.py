"""
Storage Provider Exports
"""

from core.storage.providers.cloud import (
    S3StorageProvider,
    GCSStorageProvider,
    R2StorageProvider,
    AzureBlobProvider,
    B2StorageProvider,
    MinIOProvider,
)
from core.storage.providers.consumer import (
    GoogleDriveProvider,
    DropboxProvider,
    OneDriveProvider,
    MegaProvider,
)
from core.storage.providers.ai_platforms import (
    HuggingFaceProvider,
    KaggleProvider,
    GitHubReleasesProvider,
    DVCProvider,
)
from core.storage.providers.messaging import (
    TelegramProvider,
    DiscordProvider,
    SlackProvider,
    EmailProvider,
    WebhookProvider,
)

__all__ = [
    # Cloud
    "S3StorageProvider",
    "GCSStorageProvider",
    "R2StorageProvider",
    "AzureBlobProvider",
    "B2StorageProvider",
    "MinIOProvider",
    # Consumer
    "GoogleDriveProvider",
    "DropboxProvider",
    "OneDriveProvider",
    "MegaProvider",
    # AI Platforms
    "HuggingFaceProvider",
    "KaggleProvider",
    "GitHubReleasesProvider",
    "DVCProvider",
    # Messaging
    "TelegramProvider",
    "DiscordProvider",
    "SlackProvider",
    "EmailProvider",
    "WebhookProvider",
]