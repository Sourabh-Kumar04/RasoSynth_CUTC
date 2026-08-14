"""
Cache Optimization - Compression, memory management, and adaptive policies

Intelligent cache optimization with compression, memory-aware eviction,
and adaptive expiration strategies.
"""

from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import gzip
import pickle
import hashlib
import json

# Optional compression libraries
try:
    import zstandard
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

try:
    import lz4.frame
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False


class CacheOptimizer:
    """Intelligent cache optimization manager."""

    def __init__(
        self,
        redis_client: Any,
        max_memory_percent: float = 80.0,
        eviction_batch_size: int = 100
    ):
        self.redis = redis_client
        self.max_memory_percent = max_memory_percent
        self.eviction_batch_size = eviction_batch_size

        self._optimization_rules: Dict[str, Callable] = {}
        self._compression_threshold_bytes = 1024  # Only compress > 1KB

    async def optimize(self) -> Dict[str, Any]:
        """Run cache optimization."""
        results = {
            "compressions": 0,
            "evictions": 0,
            "memory_freed_bytes": 0,
            "errors": []
        }

        try:
            # Check memory usage
            memory_info = await self._get_memory_info()
            memory_percent = memory_info.get("used_percent", 0)

            if memory_percent > self.max_memory_percent:
                # Need to evict
                to_evict = await self._calculate_eviction_candidates()
                for key in to_evict:
                    if await self.redis.delete(key):
                        results["evictions"] += 1

        except Exception as e:
            results["errors"].append(str(e))

        return results

    async def _get_memory_info(self) -> Dict:
        """Get Redis memory info."""
        try:
            info = await self.redis.info("memory")
            return dict(info)
        except Exception:
            return {}

    async def _calculate_eviction_candidates(self) -> List[str]:
        """Calculate which keys to evict."""
        candidates = []

        async for key in self.redis.scan_iter(count=self.eviction_batch_size):
            ttl = await self.redis.ttl(key)
            access_count = await self.redis.get(f"{key}:access_count")

            # Score based on TTL and access
            score = (ttl or 0) * 0.5 + (int(access_count) if access_count else 0) * 0.5
            candidates.append((key, score))

        candidates.sort(key=lambda x: x[1])
        return [k for k, _ in candidates[:self.eviction_batch_size]]


class CompressionManager:
    """Manages cache entry compression."""

    def __init__(
        self,
        default_compression: str = "lz4",
        min_size_bytes: int = 1024
    ):
        self.default_compression = default_compression
        self.min_size_bytes = min_size_bytes
        self._compression_stats: Dict[str, Dict] = {}

    async def compress(
        self,
        data: Any,
        compression_type: Optional[str] = None
    ) -> Tuple[bytes, str]:
        """Compress data."""
        compression_type = compression_type or self.default_compression

        if isinstance(data, str):
            data = data.encode()
        elif not isinstance(data, bytes):
            data = pickle.dumps(data)

        original_size = len(data)

        if compression_type == "lz4":
            if LZ4_AVAILABLE:
                compressed = lz4.frame.compress(data)
            else:
                compressed = data
        elif compression_type == "zstd":
            if ZSTD_AVAILABLE:
                cctx = zstandard.ZstdCompressor()
                compressed = cctx.compress(data)
            else:
                compressed = data
        elif compression_type == "gzip":
            compressed = gzip.compress(data)
        else:
            compressed = data

        compressed_size = len(compressed)
        ratio = original_size / max(compressed_size, 1)

        # Track stats
        if compression_type not in self._compression_stats:
            self._compression_stats[compression_type] = {
                "total_original": 0,
                "total_compressed": 0,
                "count": 0
            }

        self._compression_stats[compression_type]["total_original"] += original_size
        self._compression_stats[compression_type]["total_compressed"] += compressed_size
        self._compression_stats[compression_type]["count"] += 1

        return compressed, compression_type

    async def decompress(
        self,
        data: bytes,
        compression_type: str
    ) -> Any:
        """Decompress data."""
        if compression_type == "lz4":
            if LZ4_AVAILABLE:
                return lz4.frame.decompress(data)
            return data
        elif compression_type == "zstd":
            if ZSTD_AVAILABLE:
                dctx = zstandard.ZstdDecompressor()
                return dctx.decompress(data)
            return data
        elif compression_type == "gzip":
            return gzip.decompress(data)
        else:
            return data

    async def should_compress(self, data: Any) -> bool:
        """Determine if data should be compressed."""
        size = len(pickle.dumps(data)) if not isinstance(data, (str, bytes)) else len(str(data))
        return size >= self.min_size_bytes

    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        stats = {}
        for comp_type, data in self._compression_stats.items():
            original = data["total_original"]
            compressed = data["total_compressed"]
            stats[comp_type] = {
                "count": data["count"],
                "original_bytes": original,
                "compressed_bytes": compressed,
                "compression_ratio": original / max(compressed, 1)
            }
        return stats


class MemoryManager:
    """Memory-aware cache management."""

    def __init__(
        self,
        redis_client: Any,
        max_memory_bytes: Optional[int] = None,
        eviction_policy: str = "allkeys-lru"
    ):
        self.redis = redis_client
        self.max_memory_bytes = max_memory_bytes
        self.eviction_policy = eviction_policy

    async def configure(self) -> None:
        """Configure Redis memory settings."""
        if self.max_memory_bytes:
            await self.redis.config_set("maxmemory", str(self.max_memory_bytes))

        await self.redis.config_set("maxmemory-policy", self.eviction_policy)

    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics."""
        try:
            info = await self.redis.info("memory")
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_peak": info.get("used_memory_peak", 0),
                "used_memory_rss": info.get("used_memory_rss", 0),
                "maxmemory": info.get("maxmemory", 0),
                "used_memory_percent": info.get("used_memory_percent", 0),
                "fragmentation_ratio": info.get("mem_fragmentation_ratio", 0)
            }
        except Exception:
            return {}

    async def get_fragmentation_ratio(self) -> float:
        """Get memory fragmentation ratio."""
        try:
            info = await self.redis.info("memory")
            return float(info.get("mem_fragmentation_ratio", 0))
        except Exception:
            return 0.0

    async def defragment_memory(self) -> bool:
        """Trigger memory defragmentation."""
        try:
            await self.redis.memory_purge()
            return True
        except Exception:
            return False

    async def get_top_keys(self, count: int = 10) -> List[Dict]:
        """Get largest keys by memory usage."""
        keys = []
        async for key in self.redis.scan_iter(count=1000):
            key_memory = await self.redis.memory_usage(key)
            if key_memory:
                keys.append({
                    "key": key,
                    "memory_bytes": key_memory
                })

        keys.sort(key=lambda x: x["memory_bytes"], reverse=True)
        return keys[:count]


class AdaptiveExpirationManager:
    """Adaptive cache expiration based on usage patterns."""

    def __init__(
        self,
        redis_client: Any,
        base_policy: Optional[Dict] = None
    ):
        self.redis = redis_client
        self.base_policy = base_policy or {
            "relevance_ttl": 86400,      # 24 hours
            "web_results_ttl": 3600,      # 1 hour
            "llm_responses_ttl": 7200,     # 2 hours
            "embeddings_ttl": 604800,      # 7 days
            "ocr_results_ttl": 2592000,    # 30 days
            "metadata_ttl": 43200,         # 12 hours
        }

        self._usage_patterns: Dict[str, List[datetime]] = {}
        self._access_frequencies: Dict[str, float] = {}

    async def calculate_ttl(
        self,
        key: str,
        category: str,
        access_count: int,
        last_access: datetime,
        compute_cost: float = 1.0,
        confidence: float = 1.0
    ) -> float:
        """Calculate adaptive TTL based on usage patterns."""
        base_ttl = self.base_policy.get(category, 3600)

        # Update usage patterns
        self._track_access(key)

        # Calculate frequency factor
        frequency = self._calculate_frequency(key)

        # Calculate adaptive multiplier
        min_ttl = base_ttl * 0.1
        max_ttl = base_ttl * 10

        # Higher frequency = longer TTL
        frequency_factor = min(2.0, 0.5 + frequency * 0.5)

        # Higher compute cost = longer TTL
        cost_factor = min(3.0, 0.5 + compute_cost * 0.5)

        # Confidence decay
        confidence_factor = confidence

        ttl = base_ttl * frequency_factor * cost_factor * confidence_factor

        return max(min_ttl, min(max_ttl, ttl))

    def _track_access(self, key: str) -> None:
        """Track access pattern for key."""
        now = datetime.utcnow()

        if key not in self._usage_patterns:
            self._usage_patterns[key] = []

        self._usage_patterns[key].append(now)

        # Keep only recent accesses (last hour)
        cutoff = now - timedelta(hours=1)
        self._usage_patterns[key] = [
            t for t in self._usage_patterns[key] if t > cutoff
        ]

    def _calculate_frequency(self, key: str) -> float:
        """Calculate access frequency."""
        if key not in self._usage_patterns:
            return 0.0

        accesses = self._usage_patterns[key]
        if not accesses:
            return 0.0

        time_span = (datetime.utcnow() - accesses[0]).total_seconds()
        if time_span == 0:
            return len(accesses)

        return len(accesses) / (time_span / 3600)  # accesses per hour

    async def set_adaptive_ttl(
        self,
        key: str,
        category: str,
        compute_cost: float = 1.0,
        confidence: float = 1.0
    ) -> float:
        """Set adaptive TTL for a key."""
        access_count = await self._get_access_count(key)
        last_access = await self._get_last_access(key)

        ttl = await self.calculate_ttl(
            key, category, access_count, last_access,
            compute_cost, confidence
        )

        await self.redis.expire(key, int(ttl))
        return ttl

    async def _get_access_count(self, key: str) -> int:
        """Get access count for key."""
        count = await self.redis.get(f"{key}:access_count")
        return int(count) if count else 0

    async def _get_last_access(self, key: str) -> datetime:
        """Get last access time for key."""
        timestamp = await self.redis.get(f"{key}:last_access")
        if timestamp:
            return datetime.fromisoformat(timestamp.decode())
        return datetime.utcnow()

    async def increment_access(self, key: str) -> None:
        """Increment access count for key."""
        pipe = self.redis.pipeline()
        pipe.incr(f"{key}:access_count")
        pipe.set(f"{key}:last_access", datetime.utcnow().isoformat())
        await pipe.execute()


class ChunkedStorageManager:
    """Manages chunked storage for large objects."""

    def __init__(
        self,
        redis_client: Any,
        chunk_size: int = 65536
    ):
        self.redis = redis_client
        self.chunk_size = chunk_size

    async def store_chunked(
        self,
        key: str,
        data: Any,
        ttl: float = 300.0
    ) -> int:
        """Store large object in chunks."""
        if isinstance(data, str):
            data = data.encode()
        elif not isinstance(data, bytes):
            data = pickle.dumps(data)

        total_chunks = (len(data) + self.chunk_size - 1) // self.chunk_size

        # Store metadata
        await self.redis.hset(key, "metadata", json.dumps({
            "total_chunks": total_chunks,
            "total_size": len(data),
            "created_at": datetime.utcnow().isoformat()
        }))

        # Store chunks
        for i in range(total_chunks):
            start = i * self.chunk_size
            chunk = data[start:start + self.chunk_size]
            await self.redis.hset(key, f"chunk_{i}", chunk)

        # Set TTL
        await self.redis.expire(key, int(ttl))

        return total_chunks

    async def get_chunked(self, key: str) -> Optional[Any]:
        """Retrieve chunked object."""
        metadata = await self.redis.hget(key, "metadata")
        if not metadata:
            return None

        info = json.loads(metadata)
        total_chunks = info["total_chunks"]

        chunks = []
        for i in range(total_chunks):
            chunk = await self.redis.hget(key, f"chunk_{i}")
            if chunk:
                chunks.append(chunk)
            else:
                return None

        data = b"".join(chunks)
        return data

    async def delete_chunked(self, key: str) -> bool:
        """Delete chunked object."""
        keys_to_delete = [key]
        async for k in self.redis.scan_iter(match=f"{key}:chunk_*"):
            keys_to_delete.append(k)

        if keys_to_delete:
            await self.redis.delete(*keys_to_delete)
            return True
        return False


class CacheMetricsCollector:
    """Collects cache metrics for observability."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._counters: Dict[str, int] = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "evictions": 0,
            "errors": 0
        }
        self._timers: Dict[str, List[float]] = {}

    async def record_hit(self, category: str = "default") -> None:
        """Record a cache hit."""
        self._counters["hits"] += 1
        await self.redis.incr(f"cache:metrics:hits:{category}")

    async def record_miss(self, category: str = "default") -> None:
        """Record a cache miss."""
        self._counters["misses"] += 1
        await self.redis.incr(f"cache:metrics:misses:{category}")

    async def record_write(self, category: str = "default") -> None:
        """Record a cache write."""
        self._counters["writes"] += 1
        await self.redis.incr(f"cache:metrics:writes:{category}")

    async def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record operation latency."""
        if operation not in self._timers:
            self._timers[operation] = []
        self._timers[operation].append(latency_ms)

    async def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        total = self._counters["hits"] + self._counters["misses"]
        hit_rate = self._counters["hits"] / max(total, 1)

        latencies = {}
        for op, times in self._timers.items():
            if times:
                latencies[op] = {
                    "avg_ms": sum(times) / len(times),
                    "min_ms": min(times),
                    "max_ms": max(times),
                    "count": len(times)
                }

        return {
            "hits": self._counters["hits"],
            "misses": self._counters["misses"],
            "writes": self._counters["writes"],
            "evictions": self._counters["evictions"],
            "hit_rate": hit_rate,
            "latencies": latencies
        }

    def reset(self) -> None:
        """Reset metrics."""
        for key in self._counters:
            self._counters[key] = 0
        self._timers.clear()