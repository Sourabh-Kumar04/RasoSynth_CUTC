"""
Cache Base - Core caching interfaces, configurations, and data structures

Defines the fundamental caching layer architecture with multi-level support,
semantic awareness, and intelligent policy management.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import hashlib
import json
import uuid


class CacheCategory(Enum):
    """Cache namespace categories for intelligent organization."""
    LLM_RESPONSES = "cache:llm:responses"
    EMBEDDINGS = "cache:embeddings"
    WEB_CRAWLS = "cache:web:crawls"
    OCR = "cache:ocr"
    DATASETS = "cache:datasets"
    METADATA = "cache:metadata"
    DEDUPLICATION = "cache:deduplication"
    VALIDATION = "cache:validation"
    SYNTHETIC = "cache:synthetic"
    AGENTS = "cache:agents"
    WORKFLOWS = "cache:workflows"
    SEARCH = "cache:search"
    VECTORS = "cache:vectors"
    CHECKPOINTS = "cache:checkpoints"
    EVENTS = "cache:events"
    STATE = "cache:state"


class CompressionType(Enum):
    """Compression types for cache optimization."""
    NONE = "none"
    LZ4 = "lz4"
    ZSTD = "zstd"
    GZIP = "gzip"
    MSGPACK = "msgpack"
    PROTOBUF = "protobuf"
    ARROW = "arrow"


class EvictionStrategy(Enum):
    """Cache eviction strategies."""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"
    ADAPTIVE = "adaptive"
    SEMANTIC = "semantic"
    WEIGHTED = "weighted"


class CachePriority(Enum):
    """Cache priority levels."""
    CRITICAL = 1  # Never evict
    HIGH = 2       # Evict last
    NORMAL = 3     # Default
    LOW = 4        # Evict first
    EPHEMERAL = 5  # Evict immediately


@dataclass
class CacheConfig:
    """Configuration for cache layer."""
    category: CacheCategory = CacheCategory.METADATA
    ttl_seconds: float = 300.0
    max_size_mb: float = 100.0
    compression: CompressionType = CompressionType.LZ4
    eviction: EvictionStrategy = EvictionStrategy.LRU
    priority: CachePriority = CachePriority.NORMAL
    enable_semantic: bool = False
    enable_fuzzy_match: bool = False
    similarity_threshold: float = 0.95
    enable_snapshot: bool = True
    enable_compression: bool = True
    chunk_size_bytes: int = 65536
    min_access_for_persistence: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CachePolicy:
    """Adaptive cache policy with intelligent expiration."""
    base_ttl_seconds: float = 300.0
    min_ttl_seconds: float = 30.0
    max_ttl_seconds: float = 86400.0
    staleness_tolerance: float = 0.1
    adaptive_enabled: bool = True
    usage_weight: float = 0.4
    freshness_weight: float = 0.3
    cost_weight: float = 0.3
    recompute_cost_multiplier: float = 1.0
    source_volatility_factor: float = 1.0
    confidence_decay_rate: float = 0.05
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_ttl(
        self,
        access_count: int,
        last_access: datetime,
        compute_cost: float,
        confidence: float = 1.0,
        source_volatility: float = 1.0
    ) -> float:
        """Calculate adaptive TTL based on multiple factors."""
        if not self.adaptive_enabled:
            return self.base_ttl_seconds

        time_since_access = (datetime.utcnow() - last_access).total_seconds()
        access_frequency = access_count / max(time_since_access, 1)

        # Calculate usage factor
        usage_factor = min(access_count / 100, 1.0)

        # Calculate freshness factor (newer = longer TTL)
        freshness_factor = max(0.5, 1.0 - (time_since_access / self.max_ttl_seconds))

        # Calculate cost factor (expensive computations = longer TTL)
        cost_factor = min(compute_cost / 10.0, 2.0) * self.recompute_cost_multiplier

        # Calculate confidence factor
        confidence_factor = confidence

        # Calculate volatility factor
        volatility_factor = max(0.5, 1.0 - (source_volatility * self.source_volatility_factor))

        # Weighted combination
        ttl = self.base_ttl_seconds * (
            usage_factor * self.usage_weight +
            freshness_factor * self.freshness_weight +
            cost_factor * self.cost_weight
        ) * confidence_factor * volatility_factor

        return max(self.min_ttl_seconds, min(self.max_ttl_seconds, ttl))


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""
    key: str
    value: Any
    category: CacheCategory = CacheCategory.METADATA
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_access: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    size_bytes: int = 0
    compressed: bool = False
    compression_type: Optional[CompressionType] = None
    ttl_seconds: float = 300.0
    priority: CachePriority = CachePriority.NORMAL
    confidence: float = 1.0
    compute_cost: float = 0.0
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    semantic_hash: Optional[str] = None
    version: int = 1

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def access(self) -> None:
        """Record an access to this entry."""
        self.last_access = datetime.utcnow()
        self.access_count += 1

    def calculate_adaptive_ttl(self, policy: CachePolicy) -> float:
        """Calculate adaptive TTL for this entry."""
        return policy.calculate_ttl(
            self.access_count,
            self.last_access,
            self.compute_cost,
            self.confidence,
            self.metadata.get("source_volatility", 1.0)
        )

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "key": self.key,
            "value": str(self.value)[:100],  # Truncate for serialization
            "category": self.category.value,
            "created_at": self.created_at.isoformat(),
            "last_access": self.last_access.isoformat(),
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "ttl_seconds": self.ttl_seconds,
            "priority": self.priority.value,
            "confidence": self.confidence,
        }


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    writes: int = 0
    total_size_bytes: int = 0
    hit_rate: float = 0.0
    avg_latency_ms: float = 0.0
    semantic_hits: int = 0
    fuzzy_matches: int = 0
    tokens_saved: int = 0
    cost_saved_usd: float = 0.0


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values."""
        pass

    @abstractmethod
    async def set_many(
        self,
        entries: Dict[str, Any],
        ttl: Optional[float] = None
    ) -> int:
        """Set multiple values."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        pass


class SemanticCacheBackend(ABC):
    """Abstract base for semantic cache operations."""

    @abstractmethod
    async def get_similar(
        self,
        embedding: List[float],
        threshold: float = 0.95,
        limit: int = 5
    ) -> List[Tuple[str, float]]:
        """Find similar entries by embedding."""
        pass

    @abstractmethod
    async def index_embedding(
        self,
        key: str,
        embedding: List[float],
        metadata: Optional[Dict] = None
    ) -> None:
        """Index an embedding for similarity search."""
        pass

    @abstractmethod
    async def get_semantic_hash(self, content: Any) -> str:
        """Generate semantic hash for content."""
        pass


class CacheCoordinator(ABC):
    """Coordinates multiple cache layers."""

    @abstractmethod
    async def get(
        self,
        key: str,
        category: CacheCategory = CacheCategory.METADATA
    ) -> Optional[CacheEntry]:
        """Get from cache hierarchy."""
        pass

    @abstractmethod
    async def set(
        self,
        entry: CacheEntry
    ) -> bool:
        """Set in cache hierarchy."""
        pass

    @abstractmethod
    async def invalidate(
        self,
        key: str,
        category: Optional[CacheCategory] = None
    ) -> None:
        """Invalidate cache entries."""
        pass

    @abstractmethod
    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable,
        category: CacheCategory = CacheCategory.METADATA,
        **kwargs
    ) -> Any:
        """Get from cache or compute if miss."""
        pass


class CacheEvictionPolicy:
    """Intelligent cache eviction policy manager."""

    def __init__(self, strategy: EvictionStrategy = EvictionStrategy.LRU):
        self.strategy = strategy

    async def select_eviction_candidates(
        self,
        entries: List[CacheEntry],
        count: int,
        category: Optional[CacheCategory] = None
    ) -> List[CacheEntry]:
        """Select entries for eviction."""
        candidates = [e for e in entries if e.priority != CachePriority.CRITICAL]

        if category:
            candidates = [e for e in candidates if e.category == category]

        if self.strategy == EvictionStrategy.LRU:
            candidates.sort(key=lambda e: e.last_access)
        elif self.strategy == EvictionStrategy.LFU:
            candidates.sort(key=lambda e: e.access_count)
        elif self.strategy == EvictionStrategy.TTL:
            candidates.sort(key=lambda e: e.created_at)
        elif self.strategy == EvictionStrategy.WEIGHTED:
            candidates.sort(key=lambda e: (
                e.priority.value * 0.5 +
                e.access_count * 0.2 +
                e.compute_cost * 0.3
            ))
        else:
            candidates.sort(key=lambda e: e.access_count)

        return candidates[:count]


class CacheKeyGenerator:
    """Intelligent cache key generation."""

    @staticmethod
    def generate(
        category: CacheCategory,
        *args,
        normalize: bool = True,
        include_hash: bool = True
    ) -> str:
        """Generate a cache key from arguments."""
        parts = [category.value]

        for arg in args:
            if isinstance(arg, dict):
                parts.append(json.dumps(arg, sort_keys=True))
            elif isinstance(arg, (list, tuple)):
                parts.append(json.dumps(list(arg), sort_keys=True))
            else:
                parts.append(str(arg))

        key = ":".join(parts)

        if normalize:
            key = key.lower().strip()

        if include_hash and len(key) > 200:
            hash_suffix = hashlib.sha256(key.encode()).hexdigest()[:16]
            parts.append(hash_suffix)
            key = ":".join(parts[:3] + [hash_suffix])

        return key

    @staticmethod
    def generate_semantic_key(
        content: Any,
        category: CacheCategory,
        prefix_length: int = 100
    ) -> str:
        """Generate a semantic key for fuzzy matching."""
        content_str = str(content)[:prefix_length]
        hash_val = hashlib.sha256(content_str.encode()).hexdigest()[:32]
        return f"{category.value}:semantic:{hash_val}"

    @staticmethod
    def generate_namespace(namespace: str, *parts) -> str:
        """Generate namespaced cache key."""
        all_parts = [namespace] + list(parts)
        return ":".join(str(p) for p in all_parts)