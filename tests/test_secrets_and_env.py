import pytest
import os
from core.environment import get_current_environment, is_production
from core.security import SecretManager, get_rbac_manager
from core.storage.providers.cloud import MinIOProvider
from core.storage.base import StorageConfig, StorageProviderType

def test_canonical_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AI_DATASET_ENVIRONMENT", raising=False)
    assert get_current_environment() == "production"
    assert is_production() is True

def test_deprecated_environment_alias(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("AI_DATASET_ENVIRONMENT", "staging")
    assert get_current_environment() == "staging"
    assert is_production() is True

def test_ephemeral_fernet_key_fails_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValueError, match="ENCRYPTION_KEY environment variable is required in production"):
        SecretManager()

def test_jwt_secret_dormant_fallback_fails():
    import core.security as sec
    sec._rbac_manager = None
    # Empty secret in dev
    old_sec = os.environ.get("JWT_SECRET")
    try:
        os.environ["JWT_SECRET"] = ""
        os.environ["ENVIRONMENT"] = "development"
        with pytest.raises(ValueError, match="JWT_SECRET must be configured"):
            get_rbac_manager()
    finally:
        sec._rbac_manager = None
        if old_sec is not None:
            os.environ["JWT_SECRET"] = old_sec

def test_minio_fails_closed_without_credentials():
    config = StorageConfig(
        provider_type=StorageProviderType.MINIO,
        bucket="test-bucket",
        credentials={}
    )
    provider = MinIOProvider(config)
    import pytest
    import asyncio
    with pytest.raises(ValueError, match="MinIO storage provider requires explicit access_key"):
        asyncio.run(provider.initialize())
