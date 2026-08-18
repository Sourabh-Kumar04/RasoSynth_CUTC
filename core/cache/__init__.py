"""
Redis-Based Intelligent Distributed Caching Layer

Multi-level caching architecture with semantic awareness, distributed coordination,
and adaptive optimization for the RasoSynthTune ecosystem.
"""

from core.cache.base import (
    CacheConfig,
    CacheCategory,
    CacheEntry,
    CachePolicy,
    CompressionType,
    EvictionStrategy,
)
from core.cache.layers import (
    MultiLevelCache,
    InMemoryCache,
    RedisCache,
    SemanticCache,
    PersistentCache,
)
from core.cache.simple import (
    SimpleRedisCache,
    ProviderCache,
    JobCache,
)
from core.cache.semantic import (
    SemanticCacheManager,
    EmbeddingCache,
    FuzzyMatchCache,
    InstructionEquivalenceCache,
)
from core.cache.memory import (
    AgentSharedMemory,
    DistributedStateManager,
    WorkflowCoordinator,
    PipelineCheckpointManager,
)
from core.cache.coordinator import (
    EventBus,
    PubSubManager,
    StreamProcessor,
    DistributedLockManager,
    RateLimitProtector,
)
from core.cache.optimizer import (
    CacheOptimizer,
    CompressionManager,
    MemoryManager,
    AdaptiveExpirationManager,
)
from core.cache.checkpoint import (
    PipelineCheckpoint,
    DAGCheckpointManager,
    ResumableExecutionManager,
)
from core.cache.monitor import (
    CacheMetricsCollector,
    CacheObservabilityManager,
    PrometheusExporter,
)
from core.cache.categories import (
    LLMCache,
    EmbeddingCache as CatEmbeddingCache,
    WebCache,
    OCRCache,
    DeduplicationCache,
    ValidationCache,
    SyntheticCache,
    AgentStateCache,
    WorkflowCache,
    SearchCache,
)

# Aliases for backward compatibility
CacheManager = MultiLevelCache
# NOTE: overwrites ProviderCache import from core.cache.simple above,
# but no callers depend on the simple variant.
ProviderCache = LLMCache

__all__ = [
    # Base
    "CacheConfig",
    "CacheCategory",
    "CacheEntry",
    "CachePolicy",
    "CompressionType",
    "EvictionStrategy",

    # Simple Redis Cache
    "SimpleRedisCache",
    "JobCache",

    # Aliases for backward compatibility
    "CacheManager",
    "ProviderCache",

    # Multi-level cache
    "MultiLevelCache",
    "InMemoryCache",
    "RedisCache",
    "SemanticCache",
    "PersistentCache",

    # Semantic caching
    "SemanticCacheManager",
    "EmbeddingCache",
    "FuzzyMatchCache",
    "InstructionEquivalenceCache",

    # Shared memory
    "AgentSharedMemory",
    "DistributedStateManager",
    "WorkflowCoordinator",
    "PipelineCheckpointManager",

    # Coordination
    "EventBus",
    "PubSubManager",
    "StreamProcessor",
    "DistributedLockManager",
    "RateLimitProtector",

    # Optimization
    "CacheOptimizer",
    "CompressionManager",
    "MemoryManager",
    "AdaptiveExpirationManager",

    # Checkpointing
    "PipelineCheckpoint",
    "DAGCheckpointManager",
    "ResumableExecutionManager",

    # Observability
    "CacheMetricsCollector",
    "CacheObservabilityManager",
    "PrometheusExporter",

    # Category-specific caches
    "LLMCache",
    "EmbeddingCache",
    "WebCache",
    "OCRCache",
    "DeduplicationCache",
    "ValidationCache",
    "SyntheticCache",
    "AgentStateCache",
    "WorkflowCache",
    "SearchCache",
]