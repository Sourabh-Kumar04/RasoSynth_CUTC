"""
Enterprise Secrets Management Integration

Supports:
- HashiCorp Vault
- AWS Secrets Manager
- GCP Secret Manager
- Azure Key Vault
- Kubernetes Secrets
- Environment variables (development)
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from functools import lru_cache


logger = logging.getLogger(__name__)


class SecretBackend(str, Enum):
    """Supported secret backends."""
    ENVIRONMENT = "environment"
    HASHICORP_VAULT = "hashicorp_vault"
    AWS_SECRETS = "aws_secrets"
    GCP_SECRETS = "gcp_secrets"
    AZURE_KEYVAULT = "azure_keyvault"
    KUBERNETES = "kubernetes"


@dataclass
class SecretMetadata:
    """Metadata for a secret."""
    name: str
    backend: SecretBackend
    path: str
    version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SecretValue:
    """Container for retrieved secret value."""
    value: str
    metadata: SecretMetadata
    cached: bool = False
    cache_ttl_seconds: int = 3600


class SecretsProvider(ABC):
    """Abstract base class for secrets providers."""

    @abstractmethod
    async def get(self, path: str, version: Optional[str] = None) -> SecretValue:
        """Get a secret value."""
        pass

    @abstractmethod
    async def set(self, path: str, value: str, metadata: Optional[Dict] = None) -> SecretMetadata:
        """Set a secret value."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a secret."""
        pass

    @abstractmethod
    async def list(self, path: str) -> List[str]:
        """List secrets at a path."""
        pass

    @abstractmethod
    async def rotate(self, path: str) -> SecretMetadata:
        """Rotate a secret."""
        pass

    async def health_check(self) -> bool:
        """Check if provider is healthy."""
        try:
            await self.get("__health_check__")
            return True
        except Exception:
            return False


class InMemorySecretCache:
    """Thread-safe in-memory cache for secrets."""

    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, SecretValue] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[SecretValue]:
        """Get cached value if not expired."""
        async with self._lock:
            if key in self._cache:
                secret = self._cache[key]
                # Check expiration
                if secret.metadata.expires_at and datetime.utcnow() > secret.metadata.expires_at:
                    del self._cache[key]
                    return None
                secret.cached = True
                return secret
            return None

    async def set(self, key: str, value: SecretValue) -> None:
        """Cache a value."""
        async with self._lock:
            if len(self._cache) >= self._max_size:
                # Remove oldest entry
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].metadata.updated_at or datetime.min)
                del self._cache[oldest_key]
            self._cache[key] = value

    async def invalidate(self, key: str) -> None:
        """Invalidate a cached value."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cached values."""
        async with self._lock:
            self._cache.clear()


class EnvironmentSecretsProvider(SecretsProvider):
    """Secrets from environment variables (for development)."""

    def __init__(self, prefix: str = "AI_DATASET_"):
        self.prefix = prefix

    async def get(self, path: str, version: Optional[str] = None) -> SecretValue:
        """Get secret from environment variable."""
        env_key = f"{self.prefix}{path.upper().replace('/', '_').replace('-', '_')}"
        value = os.getenv(env_key)

        if value is None:
            raise KeyError(f"Secret not found: {path}")

        return SecretValue(
            value=value,
            metadata=SecretMetadata(
                name=path,
                backend=SecretBackend.ENVIRONMENT,
                path=path,
            )
        )

    async def set(self, path: str, value: str, metadata: Optional[Dict] = None) -> SecretMetadata:
        """Set environment variable (development only)."""
        if os.getenv("ENVIRONMENT") == "production":
            raise PermissionError("Cannot set secrets via environment in production")
        env_key = f"{self.prefix}{path.upper().replace('/', '_')}"
        os.environ[env_key] = value
        return SecretMetadata(
            name=path,
            backend=SecretBackend.ENVIRONMENT,
            path=path,
        )

    async def delete(self, path: str) -> bool:
        """Delete environment variable."""
        env_key = f"{self.prefix}{path.upper().replace('/', '_')}"
        if env_key in os.environ:
            del os.environ[env_key]
            return True
        return False

    async def list(self, path: str) -> List[str]:
        """List environment variables with prefix."""
        prefix = f"{self.prefix}{path.upper().replace('/', '_')}"
        return [k[len(self.prefix):] for k in os.environ.keys() if k.startswith(prefix)]

    async def rotate(self, path: str) -> SecretMetadata:
        """Environment secrets cannot be rotated."""
        raise NotImplementedError("Environment secrets cannot be rotated")


class VaultSecretsProvider(SecretsProvider):
    """HashiCorp Vault secrets provider."""

    def __init__(
        self,
        url: str,
        token: Optional[str] = None,
        mount_point: str = "secret",
        cache_ttl: int = 3600,
    ):
        self.url = url
        self.token = token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self.cache_ttl = cache_ttl
        self._cache = InMemorySecretCache()

    async def get(self, path: str, version: Optional[str] = None) -> SecretValue:
        """Get secret from Vault."""
        cache_key = f"vault:{path}:{version}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        try:
            import hvac
            client = hvac.Client(url=self.url, token=self.token)

            secret = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
                version=version,
            )

            # Get the latest version's data
            data = secret["data"]["data"]
            value = json.dumps(data) if isinstance(data, dict) else str(data)

            metadata = SecretMetadata(
                name=path,
                backend=SecretBackend.HASHICORP_VAULT,
                path=f"{self.mount_point}/{path}",
                version=secret["data"]["metadata"]["version"],
                created_at=datetime.fromisoformat(secret["data"]["metadata"]["created_time"]),
                updated_at=datetime.fromisoformat(secret["data"]["metadata"]["updated_time"]),
            )

            result = SecretValue(
                value=value,
                metadata=metadata,
                cache_ttl_seconds=self.cache_ttl,
            )
            result.metadata.expires_at = datetime.utcnow() + timedelta(seconds=self.cache_ttl)

            await self._cache.set(cache_key, result)
            return result

        except ImportError:
            logger.warning("hvac not installed, Vault support disabled")
            raise
        except Exception as e:
            logger.error(f"Vault get failed for {path}: {e}")
            raise

    async def set(self, path: str, value: str, metadata: Optional[Dict] = None) -> SecretMetadata:
        """Set secret in Vault."""
        import hvac
        client = hvac.Client(url=self.url, token=self.token)

        # Parse JSON value
        try:
            secret_data = json.loads(value)
        except json.JSONDecodeError:
            secret_data = {"value": value}

        if metadata:
            secret_data.update(metadata)

        client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=secret_data,
            mount_point=self.mount_point,
        )

        await self._cache.invalidate(f"vault:{path}")

        return SecretMetadata(
            name=path,
            backend=SecretBackend.HASHICORP_VAULT,
            path=f"{self.mount_point}/{path}",
        )

    async def delete(self, path: str) -> bool:
        """Delete secret from Vault."""
        import hvac
        client = hvac.Client(url=self.url, token=self.token)

        try:
            client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self.mount_point,
            )
            await self._cache.invalidate(f"vault:{path}")
            return True
        except Exception:
            return False

    async def list(self, path: str) -> List[str]:
        """List secrets in Vault."""
        import hvac
        client = hvac.Client(url=self.url, token=self.token)

        try:
            secrets = client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self.mount_point,
            )
            return secrets.get("data", {}).get("keys", [])
        except Exception:
            return []

    async def rotate(self, path: str) -> SecretMetadata:
        """Trigger secret rotation in Vault."""
        # For KV secrets, this creates a new version
        current = await self.get(path)
        await self.set(path, current.value)
        await self._cache.invalidate(f"vault:{path}")
        return current.metadata


class AWSSecretsProvider(SecretsProvider):
    """AWS Secrets Manager provider."""

    def __init__(
        self,
        region: str = "us-east-1",
        cache_ttl: int = 3600,
    ):
        self.region = region
        self.cache_ttl = cache_ttl
        self._cache = InMemorySecretCache()

    async def get(self, path: str, version: Optional[str] = None) -> SecretValue:
        """Get secret from AWS Secrets Manager."""
        cache_key = f"aws:{path}:{version}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        try:
            import boto3
            client = boto3.client("secretsmanager", region_name=self.region)

            kwargs = {"SecretId": path}
            if version:
                kwargs["VersionId"] = version

            response = client.get_secret_value(**kwargs)
            value = response.get("SecretString", "")

            metadata = SecretMetadata(
                name=path,
                backend=SecretBackend.AWS_SECRETS,
                path=path,
                version=response.get("VersionId"),
                updated_at=datetime.fromisoformat(response.get("LastChangedDate", datetime.utcnow().isoformat())),
            )

            result = SecretValue(
                value=value,
                metadata=metadata,
                cache_ttl_seconds=self.cache_ttl,
            )
            result.metadata.expires_at = datetime.utcnow() + timedelta(seconds=self.cache_ttl)

            await self._cache.set(cache_key, result)
            return result

        except ImportError:
            logger.warning("boto3 not installed, AWS Secrets support disabled")
            raise
        except Exception as e:
            logger.error(f"AWS Secrets get failed for {path}: {e}")
            raise

    async def set(self, path: str, value: str, metadata: Optional[Dict] = None) -> SecretMetadata:
        """Set secret in AWS Secrets Manager."""
        import boto3
        client = boto3.client("secretsmanager", region_name=self.region)

        client.put_secret_value(SecretId=path, SecretString=value)
        await self._cache.invalidate(f"aws:{path}")

        return SecretMetadata(
            name=path,
            backend=SecretBackend.AWS_SECRETS,
            path=path,
        )

    async def delete(self, path: str) -> bool:
        """Delete secret from AWS Secrets Manager."""
        import boto3
        client = boto3.client("secretsmanager", region_name=self.region)

        try:
            client.delete_secret(SecretId=path, ForceDeleteWithoutRecovery=True)
            await self._cache.invalidate(f"aws:{path}")
            return True
        except Exception:
            return False

    async def list(self, path: str) -> List[str]:
        """List secrets in AWS."""
        import boto3
        client = boto3.client("secretsmanager", region_name=self.region)

        try:
            response = client.list_secrets(Filters=[{"Key": "name", "Values": [path]}])
            return [s["Name"] for s in response.get("SecretList", [])]
        except Exception:
            return []

    async def rotate(self, path: str) -> SecretMetadata:
        """Trigger AWS secret rotation."""
        import boto3
        client = boto3.client("secretsmanager", region_name=self.region)

        client.start_secret_rotation(SecretId=path)
        await self._cache.invalidate(f"aws:{path}")
        return await self.get(path).metadata


class SecretsManager:
    """Unified secrets management across multiple backends."""

    def __init__(self):
        self._providers: Dict[SecretBackend, SecretsProvider] = {}
        self._cache = InMemorySecretCache(max_size=200)
        self._lock = asyncio.Lock()

    def register_provider(self, backend: SecretBackend, provider: SecretsProvider) -> None:
        """Register a secrets provider."""
        self._providers[backend] = provider
        logger.info(f"Registered secrets provider: {backend.value}")

    def get_provider(self, backend: Optional[SecretBackend] = None) -> SecretsProvider:
        """Get the appropriate provider for the backend."""
        if backend is None:
            backend = self._detect_backend()

        provider = self._providers.get(backend)
        if provider is None:
            # Fall back to environment
            provider = self._providers.get(SecretBackend.ENVIRONMENT)

        if provider is None:
            raise ValueError(f"No secrets provider registered for {backend}")

        return provider

    def _detect_backend(self) -> SecretBackend:
        """Detect which backend to use based on environment."""
        if os.getenv("VAULT_ADDR"):
            return SecretBackend.HASHICORP_VAULT
        elif os.getenv("AWS_REGION"):
            return SecretBackend.AWS_SECRETS
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            return SecretBackend.GCP_SECRETS
        elif os.getenv("AZURE_KEY_VAULT_URI"):
            return SecretBackend.AZURE_KEYVAULT
        elif os.getenv("KUBERNETES_SERVICE_HOST"):
            return SecretBackend.KUBERNETES
        else:
            return SecretBackend.ENVIRONMENT

    async def get(
        self,
        path: str,
        backend: Optional[SecretBackend] = None,
        use_cache: bool = True,
    ) -> SecretValue:
        """Get a secret value."""
        cache_key = f"{backend or 'auto'}:{path}"

        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return cached

        provider = self.get_provider(backend)
        result = await provider.get(path)
        result.cached = False

        if use_cache:
            await self._cache.set(cache_key, result)

        return result

    async def get_many(
        self,
        paths: List[str],
        backend: Optional[SecretBackend] = None,
    ) -> Dict[str, SecretValue]:
        """Get multiple secrets."""
        results = {}
        for path in paths:
            try:
                results[path] = await self.get(path, backend)
            except Exception as e:
                logger.warning(f"Failed to get secret {path}: {e}")
                results[path] = None
        return results

    async def set(
        self,
        path: str,
        value: str,
        backend: Optional[SecretBackend] = None,
        metadata: Optional[Dict] = None,
    ) -> SecretMetadata:
        """Set a secret value."""
        provider = self.get_provider(backend)
        metadata = await provider.set(path, value, metadata)
        await self._cache.invalidate(f"{backend}:{path}")
        return metadata

    async def rotate(self, path: str, backend: Optional[SecretBackend] = None) -> SecretMetadata:
        """Rotate a secret."""
        provider = self.get_provider(backend)
        metadata = await provider.rotate(path)
        await self._cache.invalidate(f"{backend}:{path}")
        return metadata

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all registered providers."""
        results = {}
        for backend, provider in self._providers.items():
            try:
                results[backend.value] = await provider.health_check()
            except Exception:
                results[backend.value] = False
        return results


# Global secrets manager
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
        _initialize_providers(_secrets_manager)
    return _secrets_manager


def _initialize_providers(manager: SecretsManager) -> None:
    """Initialize secrets providers based on environment."""
    # Always register environment provider as fallback
    manager.register_provider(SecretBackend.ENVIRONMENT, EnvironmentSecretsProvider())

    # Vault provider
    if os.getenv("VAULT_ADDR"):
        try:
            manager.register_provider(
                SecretBackend.HASHICORP_VAULT,
                VaultSecretsProvider(
                    url=os.getenv("VAULT_ADDR"),
                    token=os.getenv("VAULT_TOKEN"),
                    mount_point=os.getenv("VAULT_MOUNT_POINT", "secret"),
                )
            )
            logger.info("Vault secrets provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Vault provider: {e}")

    # AWS provider
    if os.getenv("AWS_REGION"):
        try:
            manager.register_provider(
                SecretBackend.AWS_SECRETS,
                AWSSecretsProvider(region=os.getenv("AWS_REGION", "us-east-1"))
            )
            logger.info("AWS Secrets provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize AWS provider: {e}")


# Decorator for secret injection
def secret(path: str, backend: Optional[SecretBackend] = None, default: Optional[str] = None):
    """Decorator to inject secret values into settings."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                secrets = get_secrets_manager()
                secret_value = await secrets.get(path, backend)
                return secret_value.value
            except Exception:
                if default is not None:
                    return default
                raise
        return wrapper
    return decorator


# Example usage:
"""
# Initialize secrets manager
secrets = get_secrets_manager()

# Get a secret
api_key = await secrets.get("providers/google/api_key")
print(f"API Key: {api_key.value}")

# Get multiple secrets
secrets = await secrets.get_many([
    "providers/google/api_key",
    "providers/anthropic/api_key",
    "database/password",
])

# Rotate a secret
await secrets.rotate("providers/google/api_key")
"""