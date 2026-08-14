"""Redis caching layer for API responses."""
import redis.asyncio as aioredis
import hashlib
import json
from typing import Any, Optional
from datetime import timedelta
import time


class SimpleRedisCache:
    """Async Redis cache manager."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        self.default_ttl = 3600

    @property
    def redis(self) -> aioredis.Redis:
        """Exposed for health checks and direct access."""
        return self._redis

    async def connect(self):
        """Connect to Redis."""
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def _ensure_connection(self) -> aioredis.Redis:
        """Ensure Redis connection exists."""
        if self._redis is None:
            await self.connect()
        return self._redis

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        hash_str = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_str}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        redis = await self._ensure_connection()
        value = await redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        redis = await self._ensure_connection()
        ttl = ttl or self.default_ttl

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        await redis.setex(key, ttl, value)
        return True

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        redis = await self._ensure_connection()
        result = await redis.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        redis = await self._ensure_connection()
        return await redis.exists(key) > 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        redis = await self._ensure_connection()
        return await redis.incrby(key, amount)

    async def get_ttl(self, key: str) -> int:
        """Get TTL of a key."""
        redis = await self._ensure_connection()
        return await redis.ttl(key)

    async def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        redis = await self._ensure_connection()

        hits = await redis.get("cache:hits")
        misses = await redis.get("cache:misses")

        hits = int(hits) if hits else 0
        misses = int(misses) if misses else 0

        total = hits + misses
        if total == 0:
            return 0.0

        return hits / total

    async def record_hit(self):
        """Record a cache hit."""
        await self.increment("cache:hits")

    async def record_miss(self):
        """Record a cache miss."""
        await self.increment("cache:misses")

    async def clear(self):
        """Clear all cache entries."""
        redis = await self._ensure_connection()
        await redis.flushdb()

    async def keys(self, pattern: str = "*") -> list[str]:
        """Get all keys matching pattern."""
        redis = await self._ensure_connection()
        return await redis.keys(pattern)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key."""
        redis = await self._ensure_connection()
        return await redis.expire(key, seconds)


class ProviderCache:
    """Cache specific to provider responses."""

    def __init__(self, cache: SimpleRedisCache):
        self.cache = cache
        self.prefix = "provider"

    def _provider_key(self, provider: str, prompt: str, **kwargs) -> str:
        """Generate cache key for provider request."""
        return self.cache._generate_key(f"{self.prefix}:{provider}", prompt, **kwargs)

    async def get_response(
        self,
        provider: str,
        prompt: str,
        **kwargs
    ) -> Optional[dict]:
        """Get cached provider response."""
        key = self._provider_key(provider, prompt, **kwargs)
        result = await self.cache.get(key)
        if result:
            await self.cache.record_hit()
        else:
            await self.cache.record_miss()
        return result

    async def cache_response(
        self,
        provider: str,
        prompt: str,
        response: dict,
        ttl: int = 3600
    ):
        """Cache a provider response."""
        key = self._provider_key(provider, prompt)
        await self.cache.set(key, response, ttl)

    async def invalidate_provider(self, provider: str):
        """Invalidate all cache entries for a provider."""
        keys = await self.cache.keys(f"{self.prefix}:{provider}:*")
        for key in keys:
            await self.cache.delete(key)


class JobCache:
    """Cache for job state and progress."""

    def __init__(self, cache: SimpleRedisCache):
        self.cache = cache
        self.prefix = "job"

    def _job_key(self, job_id: str, field: str) -> str:
        """Generate cache key for job."""
        return f"{self.prefix}:{job_id}:{field}"

    async def set_progress(self, job_id: str, progress: float):
        """Set job progress."""
        key = self._job_key(job_id, "progress")
        await self.cache.set(key, progress, ttl=3600)

    async def get_progress(self, job_id: str) -> Optional[float]:
        """Get job progress."""
        key = self._job_key(job_id, "progress")
        return await self.cache.get(key)

    async def set_status(self, job_id: str, status: str):
        """Set job status."""
        key = self._job_key(job_id, "status")
        await self.cache.set(key, status, ttl=3600)

    async def get_status(self, job_id: str) -> Optional[str]:
        """Get job status."""
        key = self._job_key(job_id, "status")
        return await self.cache.get(key)

    async def set_stage(self, job_id: str, stage: str):
        """Set current pipeline stage."""
        key = self._job_key(job_id, "stage")
        await self.cache.set(key, stage, ttl=3600)

    async def get_stage(self, job_id: str) -> Optional[str]:
        """Get current pipeline stage."""
        key = self._job_key(job_id, "stage")
        return await self.cache.get(key)

    async def cleanup_job(self, job_id: str):
        """Remove all cached job data."""
        keys = await self.cache.keys(f"{self.prefix}:{job_id}:*")
        for key in keys:
            await self.cache.delete(key)