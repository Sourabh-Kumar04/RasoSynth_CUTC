"""
Multi-level deduplication system for AI dataset construction.

Implements four levels of duplicate detection:
1. Exact match (SHA-256 hash cache)
2. Fuzzy match (MinHash with character/word n-grams)
3. Semantic match (embedding cosine similarity via provider router)
4. Cluster match (online centroid-based clustering)
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class DuplicateResult:
    """Result of a duplicate check against any level of the deduplication system.

    Attributes:
        is_duplicate: Whether the sample is considered a duplicate.
        duplicate_score: Overall duplicate confidence score in [0.0, 1.0].
                         1.0 means exact duplicate.
        match_type: The level that matched: ``exact``, ``fuzzy``,
                    ``embedding``, ``cluster``, or ``none``.
        matched_id: The sample ID of the existing duplicate, if found.
        similarity: The similarity value that triggered the match.
        cluster_id: The cluster ID assigned (only for cluster-level matches).
    """

    is_duplicate: bool = False
    duplicate_score: float = 0.0
    match_type: str = "none"
    matched_id: str | None = None
    similarity: float = 0.0
    cluster_id: str | None = None


# =============================================================================
# Deduplication Engine
# =============================================================================


class DeduplicationEngine:
    """Multi-level deduplication engine with exact, fuzzy, embedding, and
    cluster-based detection strategies.

    The engine checks samples against four levels in order of increasing cost:

    1. **Exact** -- constant-time SHA-256 hash lookup.
    2. **Fuzzy** -- MinHash Jaccard similarity over n-gram signatures.
    3. **Embedding** -- cosine similarity against a sliding window of recent
       embeddings (requires a configured provider router).
    4. **Cluster** -- cosine similarity against evolving cluster centroids.

    Parameters
    ----------
    router : ProviderRouter or None
        An optional ``ProviderRouter`` instance that provides an ``embed()``
        method returning ``list[float] | None``. Required for embedding and
        cluster-level checks.
    config : dict or None
        Configuration dictionary with the following optional keys:

        - ``exact_threshold`` (float, default ``1.0``): similarity at or above
          which an exact match is declared.
        - ``fuzzy_threshold`` (float, default ``0.85``): MinHash Jaccard
          threshold for fuzzy matching.
        - ``embedding_threshold`` (float, default ``0.92``): cosine similarity
          threshold for embedding-level matching.
        - ``cluster_threshold`` (float, default ``0.85``): cosine similarity
          threshold for cluster-level matching.
        - ``num_permutations`` (int, default ``128``): number of hash
          permutations for MinHash signatures.
        - ``minhash_seed`` (int, default ``42``): seed for MinHash
          fingerprinting.
        - ``embedding_buffer_max`` (int, default ``1000``): maximum number of
          recent embedding vectors kept in the sliding buffer.
    """

    def __init__(self, router=None, config: dict[str, Any] | None = None):
        config = config or {}

        # Thresholds
        self.exact_threshold = config.get("exact_threshold", 1.0)
        self.fuzzy_threshold = config.get("fuzzy_threshold", 0.85)
        self.embedding_threshold = config.get("embedding_threshold", 0.92)
        self.cluster_threshold = config.get("cluster_threshold", 0.85)

        # MinHash settings
        self._num_permutations = config.get("num_permutations", 128)
        self._minhash_seed = config.get("minhash_seed", 42)

        # Level 1: Exact-match cache (text_hash -> sample_id)
        self._exact_cache: dict[str, str] = {}

        # Level 2: MinHash signature cache
        #   sig_hash (MD5 of sorted signature) -> (signature set, sample_id)
        self._minhash_cache: dict[str, tuple[frozenset[str], str]] = {}

        # Level 3: Embedding sliding buffer
        #   Each entry: (sample_id, embedding_vector, text_hash)
        self._embedding_buffer: list[tuple[str, list[float], str]] = []
        self._embedding_buffer_max = config.get("embedding_buffer_max", 1000)

        # Level 4: Online cluster centroids
        #   cluster_id -> {"centroid": list[float], "count": int}
        self._clusters: dict[str, dict[str, Any]] = {}
        self._next_cluster_id: int = 0

        # Provider router (required for levels 3 and 4)
        self.router = router

        # Internal statistics
        self._stats: dict[str, float | int] = {
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "embedding_matches": 0,
            "cluster_matches": 0,
            "total_checks": 0,
        }

    # =========================================================================
    # Public API
    # =========================================================================

    async def check(self, text: str, sample_id: str = "") -> DuplicateResult:
        """Check *text* against all four deduplication levels.

        Levels are evaluated in order of increasing cost. The result of the
        **first** matching level is returned immediately.
        """
        self._stats["total_checks"] += 1  # type: ignore[operator]

        # Level 1: Exact (O(1) hash lookup)
        match_result = self._check_exact(text)
        if match_result[0]:
            self._stats["exact_matches"] += 1  # type: ignore[operator]
            _, score, matched_id = match_result
            return DuplicateResult(
                is_duplicate=True,
                duplicate_score=score,
                match_type="exact",
                matched_id=matched_id,
                similarity=score,
            )

        # Level 2: Fuzzy (MinHash Jaccard)
        match_result = self._check_fuzzy(text)
        if match_result[0]:
            self._stats["fuzzy_matches"] += 1  # type: ignore[operator]
            _, score, matched_id, sim = match_result
            return DuplicateResult(
                is_duplicate=True,
                duplicate_score=score,
                match_type="fuzzy",
                matched_id=matched_id,
                similarity=sim,
            )

        # Level 3: Embedding (cosine similarity via router)
        match_result = await self._check_embedding(text)
        if match_result[0]:
            self._stats["embedding_matches"] += 1  # type: ignore[operator]
            _, score, matched_id, sim = match_result
            return DuplicateResult(
                is_duplicate=True,
                duplicate_score=score,
                match_type="embedding",
                matched_id=matched_id,
                similarity=sim,
            )

        # Level 4: Cluster (centroid cosine similarity)
        match_result = await self._check_cluster(text)
        if match_result[0]:
            self._stats["cluster_matches"] += 1  # type: ignore[operator]
            _, score, matched_id, sim, cid = match_result
            return DuplicateResult(
                is_duplicate=True,
                duplicate_score=score,
                match_type="cluster",
                matched_id=matched_id,
                similarity=sim,
                cluster_id=cid,
            )

        return DuplicateResult(
            is_duplicate=False,
            duplicate_score=0.0,
            match_type="none",
            matched_id=None,
            similarity=0.0,
        )

    async def add(self, text: str, sample_id: str) -> None:
        """Register *text* in all deduplication indexes.

        Must be called after a sample passes dedup (i.e., was not flagged as a
        duplicate) so that future samples can be compared against it.
        """
        text_hash = self._compute_hash(text)

        # Level 1: Exact cache
        self._exact_cache[text_hash] = sample_id

        # Level 2: MinHash signature
        sig = self._compute_minhash(text)
        sig_hash = hashlib.md5(
            str(sorted(sig)).encode(), usedforsecurity=False
        ).hexdigest()
        self._minhash_cache[sig_hash] = (frozenset(sig), sample_id)

        # Level 3: Embedding buffer
        if self.router is not None:
            try:
                embedding = await self.router.embed(text[:1000])
                if embedding is not None:
                    self._embedding_buffer.append((sample_id, embedding, text_hash))
                    if len(self._embedding_buffer) > self._embedding_buffer_max:
                        self._embedding_buffer.pop(0)
            except Exception:
                logger.debug("Embedding generation failed during add()", exc_info=True)

    async def check_and_add(
        self, text: str, sample_id: str = ""
    ) -> DuplicateResult:
        """Atomically check *text* for duplicates and, if it is not a
        duplicate, add it to all indexes.

        This is the recommended entry point for single-sample deduplication.
        """
        result = await self.check(text, sample_id=sample_id)
        if not result.is_duplicate:
            await self.add(text, sample_id)
        return result

    # =========================================================================
    # Batch Processing
    # =========================================================================

    async def scan_batch(self, samples: list[dict]) -> list[DuplicateResult]:
        """Scan a list of sample dictionaries for internal duplicates.

        Each dict should contain at least one of the keys ``content``,
        ``instruction``, or ``response``. An optional ``id`` key is used as the
        sample identifier; otherwise a positional ID is generated.

        This method calls ``check_and_add`` for each sample sequentially so
        that later samples are compared against earlier (already-indexed) ones.
        """
        results: list[DuplicateResult] = []
        for i, sample in enumerate(samples):
            text = (
                sample.get("content", "")
                or sample.get("instruction", "")
                or sample.get("response", "")
            )
            sample_id = sample.get("id", f"sample_{i}")
            result = await self.check_and_add(text, sample_id=sample_id)
            if result.is_duplicate and result.matched_id is None:
                result.matched_id = f"sample_{i - 1}"
            results.append(result)
        return results

    # =========================================================================
    # Level 1: Exact Match
    # =========================================================================

    @staticmethod
    def _compute_hash(text: str) -> str:
        """Return a SHA-256 digest (first 32 hex chars) of the normalized
        text. Normalization strips leading/trailing whitespace, collapses
        internal whitespace runs, lowercases, and applies NFKC Unicode
        normalisation.
        """
        normalized = re.sub(r"\s+", " ", text.lower().strip())
        normalized = unicodedata.normalize("NFKC", normalized)
        return hashlib.sha256(normalized.encode(), usedforsecurity=False).hexdigest()[
            :32
        ]

    def _check_exact(self, text: str) -> tuple[bool, float, str | None]:
        """Check for an exact (hash-based) duplicate.

        Returns a 3-tuple ``(is_duplicate, score, matched_id)``.
        """
        h = self._compute_hash(text)
        if h in self._exact_cache:
            return True, 1.0, self._exact_cache[h]
        return False, 0.0, None

    # =========================================================================
    # Level 2: Fuzzy Match (MinHash)
    # =========================================================================

    def _compute_minhash(self, text: str, ngram_size: int = 5) -> set[str]:
        """Compute a MinHash signature as a set of n-gram hashes.

        For short texts (<= 2000 characters after normalisation), character
        n-grams of length *ngram_size* are used.  For longer texts, word
        tri-grams are used instead and the result is capped at
        ``num_permutations`` entries.
        """
        normalized = re.sub(r"\s+", " ", text.lower().strip())

        if len(normalized) > 2000:
            # Word tri-grams for long texts
            words = normalized.split()
            hashes: set[str] = set()
            for i in range(len(words) - 2):
                ng = " ".join(words[i : i + 3])
                hashes.add(
                    hashlib.md5(ng.encode(), usedforsecurity=False).hexdigest()[:8]
                )
            # Subsample to the configured number of permutations
            return set(list(hashes)[: self._num_permutations])

        # Character n-grams for shorter texts
        ngrams: set[str] = set()
        for i in range(len(normalized) - ngram_size + 1):
            ng = normalized[i : i + ngram_size]
            ngrams.add(
                hashlib.md5(ng.encode(), usedforsecurity=False).hexdigest()[:8]
            )
        return ngrams

    def _check_fuzzy(
        self, text: str
    ) -> tuple[bool, float, str | None, float]:
        """Check for a fuzzy (MinHash Jaccard) duplicate.

        Returns a 4-tuple
        ``(is_duplicate, duplicate_score, matched_id, similarity)``.
        """
        sig = self._compute_minhash(text)
        for cached_sig, cached_id in self._minhash_cache.values():
            jaccard = len(sig & cached_sig) / max(len(sig | cached_sig), 1)
            if jaccard >= self.fuzzy_threshold:
                return True, jaccard, cached_id, jaccard
        return False, 0.0, None, 0.0

    # =========================================================================
    # Level 3: Embedding Match
    # =========================================================================

    async def _check_embedding(
        self, text: str
    ) -> tuple[bool, float, str | None, float]:
        """Check for a semantic duplicate via embedding cosine similarity.

        Only checks against the sliding buffer of recent embeddings.

        Returns a 4-tuple
        ``(is_duplicate, duplicate_score, matched_id, similarity)``.
        """
        if self.router is None or not self._embedding_buffer:
            return False, 0.0, None, 0.0

        try:
            emb = await self.router.embed(text[:1000])
            if emb is None:
                return False, 0.0, None, 0.0
        except Exception:
            logger.debug("Embedding generation failed during check", exc_info=True)
            return False, 0.0, None, 0.0

        for sample_id, cached_emb, _ in self._embedding_buffer:
            sim = self._cosine_similarity(emb, cached_emb)
            if sim >= self.embedding_threshold:
                return True, sim, sample_id, sim

        return False, 0.0, None, 0.0

    # =========================================================================
    # Level 4: Cluster Match
    # =========================================================================

    async def _check_cluster(
        self, text: str
    ) -> tuple[bool, float, str | None, float, str | None]:
        """Check for a duplicate via cluster centroid similarity.

        If the text does not match any existing cluster, a new cluster is
        created with this sample as its centroid.

        Returns a 5-tuple
        ``(is_duplicate, duplicate_score, matched_id, similarity, cluster_id)``.
        """
        if self.router is None:
            return False, 0.0, None, 0.0, None

        try:
            emb = await self.router.embed(text[:1000])
            if emb is None:
                return False, 0.0, None, 0.0, None
        except Exception:
            logger.debug("Embedding generation failed during cluster check", exc_info=True)
            return False, 0.0, None, 0.0, None

        # Find the closest existing cluster
        best_cluster: str | None = None
        best_sim = 0.0
        for cid, cdata in self._clusters.items():
            sim = self._cosine_similarity(emb, cdata["centroid"])
            if sim > best_sim:
                best_sim = sim
                best_cluster = cid

        if best_cluster is not None and best_sim >= self.cluster_threshold:
            return True, best_sim, f"cluster_{best_cluster}", best_sim, best_cluster

        # No match -- create a new cluster seeded with this embedding
        cid = str(self._next_cluster_id)
        self._next_cluster_id += 1
        self._clusters[cid] = {"centroid": emb, "count": 1}
        return False, 0.0, None, 0.0, None

    # =========================================================================
    # Similarity Utilities
    # =========================================================================

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute the cosine similarity between two vectors *a* and *b*.

        Returns a value in ``[0.0, 1.0]``.  Zero vectors produce ``0.0``.
        """
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na * nb == 0:
            return 0.0
        return dot / (na * nb)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Return a snapshot of internal deduplication statistics and cache
        sizes.
        """
        return {
            **self._stats,
            "clusters": len(self._clusters),
            "exact_cache_size": len(self._exact_cache),
            "minhash_cache_size": len(self._minhash_cache),
            "embedding_buffer_size": len(self._embedding_buffer),
        }

    def reset(self) -> None:
        """Clear all internal state (cache, buffer, clusters, stats)."""
        self._exact_cache.clear()
        self._minhash_cache.clear()
        self._embedding_buffer.clear()
        self._clusters.clear()
        self._next_cluster_id = 0
        self._stats = {
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "embedding_matches": 0,
            "cluster_matches": 0,
            "total_checks": 0,
        }