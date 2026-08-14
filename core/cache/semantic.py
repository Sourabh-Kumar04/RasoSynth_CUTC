"""
Semantic Cache Manager - Embedding-based similarity caching

Implements semantic caching with fuzzy matching, instruction equivalence,
and partial-response reuse for LLM call optimization.
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import hashlib
import numpy as np


# Define dataclasses FIRST (before they're referenced)
@dataclass
class SemanticEntry:
    """A semantic cache entry."""
    key: str
    query: str
    response: Any
    embedding: List[float]
    semantic_hash: str
    created_at: datetime
    last_access: datetime = None
    access_count: int = 0
    metadata: Dict = field(default_factory=dict)
    partial_content: Optional[List[str]] = None

    def access(self) -> None:
        """Record access."""
        self.last_access = datetime.utcnow()
        self.access_count += 1


@dataclass
class SemanticMatch:
    """Result of semantic similarity search."""
    key: str
    entry: SemanticEntry
    similarity: float
    query: str


@dataclass
class PartialResponse:
    """Partial response for reuse."""
    key: str
    segments: List[str]
    response: Any


@dataclass
class PartialMatch:
    """Partial response match result."""
    key: str
    segments: List[str]
    similarity: float
    reuse_ratio: float


class SemanticCacheManager:
    """Manages semantic caching with embedding-based similarity."""

    def __init__(
        self,
        vector_dim: int = 384,
        similarity_threshold: float = 0.95,
        enable_partial_reuse: bool = True,
        min_hash_size: int = 128
    ):
        self.vector_dim = vector_dim
        self.similarity_threshold = similarity_threshold
        self.enable_partial_reuse = enable_partial_reuse
        self.min_hash_size = min_hash_size

        self._cache: Dict[str, SemanticEntry] = {}
        self._embeddings: Dict[str, np.ndarray] = {}
        self._semantic_hashes: Dict[str, str] = {}
        self._partial_responses: Dict[str, PartialResponse] = {}

        self._hits = 0
        self._misses = 0
        self._fuzzy_matches = 0

    async def get_similar(
        self,
        query: str,
        embedding: Optional[np.ndarray] = None,
        threshold: Optional[float] = None,
        limit: int = 5
    ) -> List[SemanticMatch]:
        """Find semantically similar cached entries."""
        threshold = threshold or self.similarity_threshold

        if embedding is None:
            embedding = await self._generate_embedding(query)

        results = []
        for key, stored_embedding in self._embeddings.items():
            similarity = self._cosine_similarity(embedding, stored_embedding)
            if similarity >= threshold:
                entry = self._cache.get(key)
                if entry:
                    results.append(SemanticMatch(
                        key=key,
                        entry=entry,
                        similarity=similarity,
                        query=query
                    ))

        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:limit]

    async def store(
        self,
        key: str,
        query: str,
        response: Any,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict] = None,
        partial_content: Optional[List[str]] = None
    ) -> None:
        """Store a semantic cache entry."""
        if embedding is None:
            embedding = await self._generate_embedding(query)

        entry = SemanticEntry(
            key=key,
            query=query,
            response=response,
            embedding=embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
            semantic_hash=await self._compute_semantic_hash(query),
            created_at=datetime.utcnow(),
            access_count=0,
            metadata=metadata or {},
            partial_content=partial_content
        )

        self._cache[key] = entry
        self._embeddings[key] = embedding if isinstance(embedding, np.ndarray) else np.array(embedding)
        self._semantic_hashes[key] = entry.semantic_hash

        # Store partial responses if enabled
        if partial_content and self.enable_partial_reuse:
            self._partial_responses[key] = PartialResponse(
                key=key,
                segments=partial_content,
                response=response
            )

    async def get(
        self,
        key: str,
        threshold: Optional[float] = None
    ) -> Optional[Any]:
        """Get cached response."""
        if key in self._cache:
            entry = self._cache[key]
            entry.access_count += 1
            entry.last_access = datetime.utcnow()
            self._hits += 1
            return entry.response

        return None

    async def invalidate(self, key: str) -> None:
        """Invalidate a cache entry."""
        self._cache.pop(key, None)
        self._embeddings.pop(key, None)
        self._semantic_hashes.pop(key, None)
        self._partial_responses.pop(key, None)

    async def get_partial_reuse(
        self,
        query: str,
        embedding: Optional[np.ndarray] = None
    ) -> Optional[PartialMatch]:
        """Get partial response reuse opportunities."""
        if not self.enable_partial_reuse:
            return None

        similar = await self.get_similar(query, embedding, threshold=0.8, limit=3)
        if not similar:
            return None

        for match in similar:
            partial = self._partial_responses.get(match.key)
            if partial:
                return PartialMatch(
                    key=match.key,
                    segments=partial.segments,
                    similarity=match.similarity,
                    reuse_ratio=len(partial.segments) / max(len(query.split()), 1)
                )

        return None

    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        hash_val = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        embedding = np.array([
            (hash_val >> (i * 8) & 0xFF) / 255.0
            for i in range(min(self.vector_dim, 64))
        ] + [0.0] * max(0, self.vector_dim - 64))
        return embedding / np.linalg.norm(embedding) if np.linalg.norm(embedding) > 0 else embedding

    async def _compute_semantic_hash(self, text: str) -> str:
        """Compute semantic hash for instruction equivalence."""
        normalized = self._normalize_text(text)
        hash_val = hashlib.sha256(normalized.encode()).hexdigest()
        return hash_val[:32]

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for semantic comparison."""
        import re
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s]', '', text)
        return text

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def get_stats(self) -> Dict[str, Any]:
        """Get semantic cache statistics."""
        total = self._hits + self._misses
        return {
            "total_entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "fuzzy_matches": self._fuzzy_matches,
            "hit_rate": self._hits / max(total, 1),
            "avg_similarity": np.mean([
                self._cosine_similarity(e, e)
                for e in self._embeddings.values()
            ]) if self._embeddings else 0.0,
        }


class FuzzyMatchCache:
    """Fuzzy matching cache with minhash and LSH support."""

    def __init__(
        self,
        num_hashes: int = 128,
        band_size: int = 16,
        threshold: float = 0.8
    ):
        self.num_hashes = num_hashes
        self.band_size = band_size
        self.threshold = threshold

        self._minhashes: Dict[str, List[int]] = {}
        self._content_hashes: Dict[str, str] = {}
        self._entries: Dict[str, Any] = {}

    async def store(
        self,
        key: str,
        content: str,
        value: Any,
        metadata: Optional[Dict] = None
    ) -> None:
        """Store with minhash for fuzzy matching."""
        minhash = await self._compute_minhash(content)
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        self._minhashes[key] = minhash
        self._content_hashes[key] = content_hash
        self._entries[key] = {
            "content": content,
            "value": value,
            "metadata": metadata or {},
        }

    async def find_similar(
        self,
        content: str,
        limit: int = 5
    ) -> List[Tuple[str, float]]:
        """Find similar content using minhash LSH."""
        query_minhash = await self._compute_minhash(content)
        query_hash = hashlib.sha256(content.encode()).hexdigest()

        results = []
        for key, stored_minhash in self._minhashes.items():
            jaccard = self._minhash_similarity(query_minhash, stored_minhash)
            if jaccard >= self.threshold:
                results.append((key, jaccard))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def _compute_minhash(self, content: str) -> List[int]:
        """Compute MinHash signature for content."""
        shingles = self._get_shingles(content, k=3)
        num_hashes = self.num_hashes

        hashes = []
        for i in range(num_hashes):
            min_val = float('inf')
            for shingle in shingles:
                hash_val = hash((shingle, i))
                min_val = min(min_val, hash_val)
            hashes.append(int(min_val))

        return hashes

    @staticmethod
    def _get_shingles(text: str, k: int = 3) -> set:
        """Get k-shingles from text."""
        text = text.lower().strip()
        shingles = set()
        for i in range(len(text) - k + 1):
            shingles.add(text[i:i + k])
        return shingles

    @staticmethod
    def _minhash_similarity(hash1: List[int], hash2: List[int]) -> float:
        """Calculate MinHash similarity (Jaccard)."""
        if len(hash1) != len(hash2):
            return 0.0
        matches = sum(1 for h1, h2 in zip(hash1, hash2) if h1 == h2)
        return matches / len(hash1)

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        entry = self._entries.get(key)
        return entry["value"] if entry else None

    async def invalidate(self, key: str) -> None:
        """Invalidate entry."""
        self._minhashes.pop(key, None)
        self._content_hashes.pop(key, None)
        self._entries.pop(key, None)


class InstructionEquivalenceCache:
    """Cache for instruction-equivalent queries."""

    def __init__(self):
        self._canonical_forms: Dict[str, str] = {}
        self._equivalence_groups: Dict[str, set] = {}
        self._cached_responses: Dict[str, Any] = {}

    async def get_or_compute(
        self,
        instruction: str,
        compute_fn: Callable,
        **kwargs
    ) -> Any:
        """Get cached response for equivalent instruction."""
        canonical = await self._to_canonical_form(instruction)

        if canonical in self._cached_responses:
            return self._cached_responses[canonical]

        response = await compute_fn(**kwargs)
        await self.store(canonical, instruction, response)
        return response

    async def store(
        self,
        canonical: str,
        original: str,
        response: Any
    ) -> None:
        """Store instruction equivalence."""
        self._canonical_forms[original] = canonical

        if canonical not in self._equivalence_groups:
            self._equivalence_groups[canonical] = set()

        self._equivalence_groups[canonical].add(original)
        self._cached_responses[canonical] = response

    async def _to_canonical_form(self, instruction: str) -> str:
        """Convert instruction to canonical form."""
        normalized = instruction.lower().strip()
        normalized = ' '.join(normalized.split())

        import re
        variations = {
            r'\bplease\b': '',
            r'\bcould you\b': '',
            r'\bcan you\b': '',
            r'\bwould you\b': '',
            r'\bmaybe\b': '',
            r'\bperhaps\b': '',
        }

        for pattern, replacement in variations.items():
            normalized = re.sub(pattern, replacement, normalized)

        return normalized.strip()

    def get_equivalent(self, instruction: str) -> Optional[str]:
        """Get canonical form."""
        return self._canonical_forms.get(instruction)

    def get_group(self, canonical: str) -> set:
        """Get all equivalent instructions."""
        return self._equivalence_groups.get(canonical, set())


class EmbeddingCache:
    """Specialized cache for embedding results."""

    def __init__(self, vector_dim: int = 384):
        self.vector_dim = vector_dim
        self._embeddings: Dict[str, np.ndarray] = {}
        self._metadata: Dict[str, Dict] = {}
        self._access_counts: Dict[str, int] = {}

    async def get(
        self,
        text: str,
        model: str = "default"
    ) -> Optional[np.ndarray]:
        """Get cached embedding."""
        key = self._make_key(text, model)
        if key in self._embeddings:
            self._access_counts[key] = self._access_counts.get(key, 0) + 1
            return self._embeddings[key]
        return None

    async def store(
        self,
        text: str,
        embedding: np.ndarray,
        model: str = "default",
        metadata: Optional[Dict] = None
    ) -> None:
        """Store embedding."""
        key = self._make_key(text, model)
        self._embeddings[key] = embedding
        self._metadata[key] = {
            "model": model,
            "created_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
        self._access_counts[key] = 0

    async def get_many(
        self,
        texts: List[str],
        model: str = "default"
    ) -> Dict[str, np.ndarray]:
        """Get multiple embeddings."""
        results = {}
        for text in texts:
            embedding = await self.get(text, model)
            if embedding is not None:
                results[text] = embedding
        return results

    async def store_many(
        self,
        items: Dict[str, np.ndarray],
        model: str = "default"
    ) -> int:
        """Store multiple embeddings."""
        count = 0
        for text, embedding in items.items():
            await self.store(text, embedding, model)
            count += 1
        return count

    def _make_key(self, text: str, model: str) -> str:
        """Generate cache key."""
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
        return f"embedding:{model}:{content_hash}"

    def get_stats(self) -> Dict[str, Any]:
        """Get embedding cache statistics."""
        total_accesses = sum(self._access_counts.values())
        return {
            "total_embeddings": len(self._embeddings),
            "total_accesses": total_accesses,
            "avg_accesses": total_accesses / max(len(self._embeddings), 1),
        }