"""
Multi-Level Cache Layers - L1-L4 cache hierarchy implementation

Implements in-memory (L1), Redis distributed (L2), persistent (L3),
and semantic vector (L4) cache layers with intelligent routing.
"""

from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import hashlib
import pickle
import gzip
import os
import json

# Import base types from same package
try:
    from core.cache.base import CacheEntry, CacheCategory, CachePriority, CachePolicy, CompressionType
except ImportError:
    # Forward declarations if base not yet loaded
    pass

# Optional compression libraries
try:
    import lz4.frame
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False

try:
    import zstandard
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False


class CacheLayer(Enum):
    """Cache layer levels."""
    L1_MEMORY = "l1_memory"      # In-process memory
    L2_REDIS = "l2_redis"        # Redis distributed
    L3_PERSISTENT = "l3_persistent"  # Persistent storage
    L4_SEMANTIC = "l4_semantic"  # Vector semantic cache


@dataclass
class LayerStats:
    """Statistics for a cache layer."""
    layer: CacheLayer
    hits: int = 0
    misses: int = 0
    writes: int = 0
    evictions: int = 0
    avg_latency_ms: float = 0.0
    size_bytes: int = 0
    capacity_bytes: int = 0


class InMemoryCache:
    """L1 in-memory cache with LRU eviction."""

    def __init__(
        self,
        max_size_mb: float = 100.0,
        eviction: str = "lru"
    ):
        self._cache: Dict[str, 'CacheEntry'] = {}
        self._access_order: List[str] = []
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.current_size_bytes = 0
        self.eviction_policy = eviction
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._cleanup_task: Optional[asyncio.Task] = None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from in-memory cache."""
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                entry.access()
                self._update_access_order(key)
                self._hits += 1
                return entry.value
            else:
                await self.delete(key)
        self._misses += 1
        return None

    async def _evict_expired(self) -> int:
        """Evict all expired entries. Returns count of evicted entries."""
        evicted_count = 0
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            await self.delete(key)
            evicted_count += 1
        return evicted_count

    def _start_cleanup_task(self) -> None:
        """Start periodic cleanup of expired entries."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                pass  # Wait for cancellation to complete if needed
            except asyncio.CancelledError:
                pass

        async def _cleanup_loop():
            while True:
                await asyncio.sleep(60)
                try:
                    removed = await self._evict_expired()
                    if removed > 0:
                        logger.debug(f"Evicted {removed} expired cache entries")
                except Exception:
                    pass

        self._cleanup_task = asyncio.create_task(_cleanup_loop())

    async def set(
        self,
        key: str,
        value: Any,
        ttl: float = 300.0,
        priority: CachePriority = CachePriority.NORMAL,
        **metadata
    ) -> bool:
        """Set value in in-memory cache."""
        size = self._estimate_size(value)

        # Evict if necessary
        while self.current_size_bytes + size > self.max_size_bytes and self._cache:
            await self._evict_one()

        if key in self._cache:
            old_entry = self._cache[key]
            self.current_size_bytes -= old_entry.size_bytes

        entry = CacheEntry(
            key=key,
            value=value,
            size_bytes=size,
            ttl_seconds=ttl,
            priority=priority,
            **metadata
        )

        self._cache[key] = entry
        self.current_size_bytes += size
        self._access_order.append(key)

        return True

    async def delete(self, key: str) -> bool:
        """Delete from in-memory cache."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self.current_size_bytes -= entry.size_bytes
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    async def clear(self) -> None:
        """Clear all entries."""
        self._cache.clear()
        self._access_order.clear()
        self.current_size_bytes = 0

    def get_stats(self) -> LayerStats:
        """Get layer statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / max(total, 1)

        return LayerStats(
            layer=CacheLayer.L1_MEMORY,
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            size_bytes=self.current_size_bytes,
            capacity_bytes=self.max_size_bytes,
            avg_latency_ms=0.1  # Very fast in-memory
        )

    async def _evict_one(self) -> None:
        """Evict one entry based on policy."""
        if not self._access_order:
            return

        if self.eviction_policy == "lru":
            key_to_evict = self._access_order[0]
        else:
            key_to_evict = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )

        await self.delete(key_to_evict)
        self._evictions += 1

    def _update_access_order(self, key: str) -> None:
        """Update access order for LRU."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _estimate_size(self, value: Any) -> int:
        """Estimate size of value."""
        try:
            return len(pickle.dumps(value))
        except:
            return len(str(value).encode())


class RedisCache:
    """L2 Redis distributed cache with compression support."""

    def __init__(
        self,
        redis_client: Any,
        compression: CompressionType = CompressionType.LZ4,
        enable_snapshot: bool = True
    ):
        self.redis = redis_client
        self.compression = compression
        self.enable_snapshot = enable_snapshot
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        try:
            data = await self.redis.get(key)
            if data is None:
                self._misses += 1
                return None

            self._hits += 1
            return await self._decompress(data)

        except Exception:
            self._misses += 1
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: float = 300.0,
        compress: bool = True,
        **metadata
    ) -> bool:
        """Set value in Redis."""
        try:
            data = await self._compress(value) if compress else value

            if self.enable_snapshot:
                await self.redis.setex(key, ttl, data)
            else:
                await self.redis.set(key, data, ex=ttl)

            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete from Redis."""
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception:
            return False

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values."""
        results = {}
        if not keys:
            return results

        try:
            values = await self.redis.mget(keys)
            for key, value in zip(keys, values):
                if value is not None:
                    results[key] = await self._decompress(value)
                    self._hits += 1
                else:
                    self._misses += 1
        except Exception:
            pass

        return results

    async def set_many(
        self,
        entries: Dict[str, Any],
        ttl: float = 300.0
    ) -> int:
        """Set multiple values."""
        success = 0
        pipe = self.redis.pipeline()

        for key, value in entries.items():
            try:
                data = await self._compress(value) if self.compression != CompressionType.NONE else value
                pipe.setex(key, ttl, data)
                success += 1
            except Exception:
                pass

        await pipe.execute()
        return success

    async def clear_category(self, category: str) -> int:
        """Clear all keys in a category."""
        pattern = f"{category}:*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def get_stats(self) -> LayerStats:
        """Get layer statistics."""
        return LayerStats(
            layer=CacheLayer.L2_REDIS,
            hits=self._hits,
            misses=self._misses,
            avg_latency_ms=1.0
        )

    async def _compress(self, data: Any) -> bytes:
        """Compress data."""
        if isinstance(data, str):
            data = data.encode()

        if self.compression == CompressionType.LZ4:
            if LZ4_AVAILABLE:
                return lz4.frame.compress(data)
            return data
        elif self.compression == CompressionType.ZSTD:
            if ZSTD_AVAILABLE:
                cctx = zstandard.ZstdCompressor()
                return cctx.compress(data)
            return data
        elif self.compression == CompressionType.GZIP:
            return gzip.compress(data)
        else:
            return data

    async def _decompress(self, data: bytes) -> Any:
        """Decompress data."""
        if self.compression == CompressionType.LZ4:
            if LZ4_AVAILABLE:
                return lz4.frame.decompress(data)
            return data
        elif self.compression == CompressionType.ZSTD:
            if ZSTD_AVAILABLE:
                dctx = zstandard.ZstdDecompressor()
                return dctx.decompress(data)
            return data
        elif self.compression == CompressionType.GZIP:
            return gzip.decompress(data)
        else:
            return data


class PersistentCache:
    """L3 Persistent cache with object storage."""

    def __init__(
        self,
        storage_path: str,
        max_size_gb: float = 10.0,
        compression: CompressionType = CompressionType.ZSTD
    ):
        self.storage_path = storage_path
        self.max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
        self.compression = compression
        self._index: Dict[str, Dict] = {}
        self._current_size = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get from persistent cache."""
        if key not in self._index:
            return None

        metadata = self._index[key]
        if self._is_expired(metadata):
            await self.delete(key)
            return None

        file_path = self._get_file_path(key)
        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            if self.compression != CompressionType.NONE:
                data = await self._decompress(data)

            return pickle.loads(data)
        except Exception:
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: float = 86400.0,
        **metadata
    ) -> bool:
        """Set in persistent cache."""
        try:
            data = pickle.dumps(value)

            if self.compression != CompressionType.NONE:
                data = await self._compress(data)

            file_path = self._get_file_path(key)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'wb') as f:
                f.write(data)

            self._index[key] = {
                "created_at": datetime.utcnow().isoformat(),
                "ttl_seconds": ttl,
                "size_bytes": len(data),
                **metadata
            }

            self._current_size += len(data)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete from persistent cache."""
        if key in self._index:
            file_path = self._get_file_path(key)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

            del self._index[key]
            return True
        return False

    def _get_file_path(self, key: str) -> str:
        """Get file path for key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return os.path.join(
            self.storage_path,
            key_hash[:2],
            f"{key_hash}.cache"
        )

    def _is_expired(self, metadata: Dict) -> bool:
        """Check if entry is expired."""
        created = datetime.fromisoformat(metadata["created_at"])
        ttl = metadata.get("ttl_seconds", 86400)
        return (datetime.utcnow() - created).total_seconds() > ttl

    async def _compress(self, data: bytes) -> bytes:
        """Compress data."""
        if self.compression == CompressionType.ZSTD:
            if ZSTD_AVAILABLE:
                cctx = zstandard.ZstdCompressor()
                return cctx.compress(data)
        return data

    async def _decompress(self, data: bytes) -> bytes:
        """Decompress data."""
        if self.compression == CompressionType.ZSTD:
            if ZSTD_AVAILABLE:
                dctx = zstandard.ZstdDecompressor()
                return dctx.decompress(data)
        return data


class SemanticCache:
    """L4 Semantic cache with vector similarity."""

    def __init__(
        self,
        vector_dim: int = 384,
        similarity_threshold: float = 0.95
    ):
        self.vector_dim = vector_dim
        self.similarity_threshold = similarity_threshold
        self._vectors: Dict[str, List[float]] = {}
        self._entries: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    async def get_similar(
        self,
        embedding: List[float],
        threshold: float = 0.95,
        limit: int = 5
    ) -> List[Tuple[str, float]]:
        """Find similar entries by embedding."""
        results = []

        for key, stored_embedding in self._vectors.items():
            similarity = self._cosine_similarity(embedding, stored_embedding)
            if similarity >= threshold:
                results.append((key, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def index_embedding(
        self,
        key: str,
        embedding: List[float],
        value: Any,
        ttl: float = 86400.0,
        **metadata
    ) -> None:
        """Index an embedding."""
        self._vectors[key] = embedding

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl,
            embedding=embedding,
            **metadata
        )
        self._entries[key] = entry

    async def get(self, key: str) -> Optional[Any]:
        """Get value by exact key."""
        if key in self._entries:
            entry = self._entries[key]
            if not entry.is_expired():
                entry.access()
                return entry.value
        return None

    async def delete(self, key: str) -> bool:
        """Delete entry."""
        if key in self._vectors:
            del self._vectors[key]
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)


class MultiLevelCache:
    """Multi-level cache coordinator with intelligent routing."""

    def __init__(
        self,
        l1_config: Optional[Dict] = None,
        l2_redis: Optional[Any] = None,
        l3_config: Optional[Dict] = None,
        l4_config: Optional[Dict] = None
    ):
        self.l1 = InMemoryCache(**(l1_config or {"max_size_mb": 100}))
        self.l2 = RedisCache(l2_redis) if l2_redis else None
        self.l3 = PersistentCache(**(l3_config or {})) if l3_config else None
        self.l4 = SemanticCache() if l4_config else None

        self.layer_stats: Dict[CacheLayer, LayerStats] = {}
        self._hit_chain = 0
        self._miss_chain = 0

    async def get(
        self,
        key: str,
        layers: List[CacheLayer] = None,
        category: CacheCategory = CacheCategory.METADATA
    ) -> Optional[Any]:
        """Get from cache hierarchy."""
        if layers is None:
            layers = [CacheLayer.L1_MEMORY, CacheLayer.L2_REDIS]

        # L1: In-memory
        if CacheLayer.L1_MEMORY in layers:
            value = await self.l1.get(key)
            if value is not None:
                self._hit_chain += 1
                self.layer_stats[CacheLayer.L1_MEMORY].hits += 1
                return value

        # L2: Redis
        if self.l2 and CacheLayer.L2_REDIS in layers:
            value = await self.l2.get(key)
            if value is not None:
                self._hit_chain += 1
                self.layer_stats[CacheLayer.L2_REDIS].hits += 1
                # Promote to L1
                await self.l1.set(key, value)
                return value

        # L3: Persistent
        if self.l3 and CacheLayer.L3_PERSISTENT in layers:
            value = await self.l3.get(key)
            if value is not None:
                self._hit_chain += 1
                # Promote through layers
                if self.l2:
                    await self.l2.set(key, value)
                await self.l1.set(key, value)
                return value

        # L4: Semantic
        if self.l4 and CacheLayer.L4_SEMANTIC in layers:
            embedding = await self._generate_embedding(key)
            similar = await self.l4.get_similar(embedding, threshold=0.95)
            if similar:
                key, score = similar[0]
                value = await self.l4.get(key)
                if value:
                    self.layer_stats[CacheLayer.L4_SEMANTIC].hits += 1
                    return value

        self._miss_chain += 1
        return None

    async def set(
        self,
        key: str,
        value: Any,
        category: CacheCategory = CacheCategory.METADATA,
        layers: List[CacheLayer] = None,
        ttl: float = 300.0,
        embedding: Optional[List[float]] = None,
        **metadata
    ) -> bool:
        """Set in cache hierarchy."""
        if layers is None:
            layers = [
                CacheLayer.L1_MEMORY,
                CacheLayer.L2_REDIS,
                CacheLayer.L3_PERSISTENT
            ]

        success = True

        if CacheLayer.L1_MEMORY in layers:
            await self.l1.set(key, value, ttl, **metadata)

        if self.l2 and CacheLayer.L2_REDIS in layers:
            await self.l2.set(key, value, ttl, **metadata)

        if self.l3 and CacheLayer.L3_PERSISTENT in layers:
            await self.l3.set(key, value, ttl, **metadata)

        if self.l4 and embedding and CacheLayer.L4_SEMANTIC in layers:
            await self.l4.index_embedding(key, embedding, value, ttl, **metadata)

        return success

    async def invalidate(
        self,
        key: str,
        layers: List[CacheLayer] = None
    ) -> None:
        """Invalidate cache entry across layers."""
        if layers is None:
            layers = [
                CacheLayer.L1_MEMORY,
                CacheLayer.L2_REDIS,
                CacheLayer.L3_PERSISTENT,
                CacheLayer.L4_SEMANTIC
            ]

        if CacheLayer.L1_MEMORY in layers:
            await self.l1.delete(key)
        if self.l2 and CacheLayer.L2_REDIS in layers:
            await self.l2.delete(key)
        if self.l3 and CacheLayer.L3_PERSISTENT in layers:
            await self.l3.delete(key)
        if self.l4 and CacheLayer.L4_SEMANTIC in layers:
            await self.l4.delete(key)

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable,
        category: CacheCategory = CacheCategory.METADATA,
        ttl: float = 300.0,
        **kwargs
    ) -> Any:
        """Get from cache or compute if miss."""
        value = await self.get(key, category=category)
        if value is not None:
            return value

        # Compute
        value = await compute_fn(**kwargs)
        await self.set(key, value, category, ttl=ttl)
        return value

    async def get_all_stats(self) -> Dict[str, LayerStats]:
        """Get statistics for all layers."""
        return {
            "l1_memory": self.l1.get_stats(),
            "l2_redis": self.l2.get_stats() if self.l2 else None,
            "l3_persistent": self.l3.get_stats() if self.l3 else None,
            "l4_semantic": self.l4.get_stats() if self.l4 else None,
        }

    async def _generate_embedding(self, key: str) -> List[float]:
        """Generate embedding for semantic cache."""
        import hashlib
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return [
            (hash_val >> (i * 8) & 0xFF) / 255.0
            for i in range(min(self.l4.vector_dim, 64))
        ] + [0.0] * max(0, self.l4.vector_dim - 64)