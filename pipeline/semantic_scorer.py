"""Semantic quality scorer using BGE embeddings.

Provides embedding-based semantic quality measurement for instruction-response pairs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Default embedding model (can be overridden)
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class SemanticScoreResult:
    """Immutable semantic scoring result."""
    relevance: float          # Instruction-response alignment
    completeness: float       # Coverage of instruction concepts
    consistency: float        # Internal consistency (no contradictions)
    diversity: float          # Vocabulary/structural variety
    overall: float            # Weighted combination
    method: str               # "embedding" or "heuristic"
    details: dict[str, Any]   # Diagnostic information

    def to_dict(self) -> dict[str, Any]:
        return {
            "relevance": round(self.relevance, 4),
            "completeness": round(self.completeness, 4),
            "consistency": round(self.consistency, 4),
            "diversity": round(self.diversity, 4),
            "overall": round(self.overall, 4),
            "method": self.method,
            "details": self.details,
        }


class SemanticQualityScorer:
    """Semantic quality scorer using embeddings and heuristics.

    When a router with embedding capability is available, uses BGE-style
    embedding similarity. Falls back to lexical heuristics otherwise.

    Usage::

        scorer = SemanticQualityScorer(router=my_router)
        result = await scorer.score(instruction, response)
        print(f"Semantic quality: {result.overall}")
    """

    def __init__(
        self,
        router=None,
        model_name: Optional[str] = None,
        cache_embeddings: bool = True,
    ):
        self.router = router
        self.model_name = model_name or DEFAULT_MODEL
        self._cache: dict[str, list[float]] = {} if cache_embeddings else None
        self._model = None  # Lazy-loaded

    async def score(
        self,
        instruction: str,
        response: str,
        source: str = "",
    ) -> SemanticScoreResult:
        """Score semantic quality of an instruction-response pair."""
        # Try embedding-based scoring if router available
        if self.router:
            try:
                return await self._score_embeddings(instruction, response, source)
            except Exception as e:
                logger.warning(f"Embedding scoring failed: {e}, falling back to heuristics")

        # Fallback to heuristics
        return self._score_heuristic(instruction, response, source)

    async def _score_embeddings(
        self,
        instruction: str,
        response: str,
        source: str = "",
    ) -> SemanticScoreResult:
        """Embedding-based semantic scoring."""
        details: dict[str, Any] = {}

        # Get embeddings
        inst_emb = await self._get_embedding(instruction)
        resp_emb = await self._get_embedding(response)

        # Compute cosine similarity for relevance
        relevance = self._cosine_similarity(inst_emb, resp_emb)
        details["embedding_relevance"] = round(relevance, 4)

        # Completeness: check instruction concept coverage in response
        completeness = self._embedding_coverage(instruction, response, inst_emb, resp_emb)
        details["embedding_coverage"] = round(completeness, 4)

        # Consistency: check for contradictions (heuristic + embedding)
        consistency = self._check_consistency(response)
        details["consistency_score"] = round(consistency, 4)

        # Diversity: vocabulary variety
        diversity = self._lexical_diversity(response)
        details["lexical_diversity"] = round(diversity, 4)

        # Weighted overall
        overall = (
            relevance * 0.30 +
            completeness * 0.30 +
            consistency * 0.20 +
            diversity * 0.20
        )

        return SemanticScoreResult(
            relevance=relevance,
            completeness=completeness,
            consistency=consistency,
            diversity=diversity,
            overall=overall,
            method="embedding",
            details=details,
        )

    def _score_heuristic(
        self,
        instruction: str,
        response: str,
        source: str = "",
    ) -> SemanticScoreResult:
        """Heuristic semantic scoring (fallback when no embeddings)."""
        details: dict[str, Any] = {}

        # Relevance: keyword overlap
        relevance = self._keyword_overlap(instruction, response)
        details["keyword_overlap"] = round(relevance, 4)

        # Completeness: response length vs instruction
        completeness = self._length_completeness(instruction, response)
        details["length_completeness"] = round(completeness, 4)

        # Consistency: contradiction markers
        consistency = self._check_consistency(response)
        details["consistency_score"] = round(consistency, 4)

        # Diversity: vocabulary variety
        diversity = self._lexical_diversity(response)
        details["lexical_diversity"] = round(diversity, 4)

        # Weighted overall
        overall = (
            relevance * 0.30 +
            completeness * 0.30 +
            consistency * 0.20 +
            diversity * 0.20
        )

        return SemanticScoreResult(
            relevance=relevance,
            completeness=completeness,
            consistency=consistency,
            diversity=diversity,
            overall=overall,
            method="heuristic",
            details=details,
        )

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text, with caching."""
        # Check cache
        if self._cache is not None and text in self._cache:
            return self._cache[text]

        # Get from router
        if not self.router:
            raise RuntimeError("No router configured")

        emb_response = await self.router.embed(text[:512])
        embedding = emb_response.embedding

        # Cache it
        if self._cache is not None:
            self._cache[text] = embedding
            # Limit cache size
            if len(self._cache) > 1000:
                # Remove oldest (first) item
                self._cache.pop(next(iter(self._cache)))

        return embedding

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _embedding_coverage(
        self,
        instruction: str,
        response: str,
        inst_emb: list[float],
        resp_emb: list[float],
    ) -> float:
        """Estimate how well response covers instruction concepts.

        Uses sentence-level embedding comparison.
        """
        # Split instruction into key concepts (sentences/phrases)
        inst_parts = re.split(r'[,.:;?!]', instruction)
        inst_parts = [p.strip() for p in inst_parts if len(p.strip()) > 3]

        if not inst_parts:
            return 0.5  # Neutral

        # Check coverage of each part
        coverages = []
        for part in inst_parts[:5]:  # Limit to 5 parts
            try:
                part_emb = self._cache.get(part)
                if part_emb is None:
                    continue
                sim = self._cosine_similarity(part_emb, resp_emb)
                coverages.append(sim)
            except Exception:
                pass

        if not coverages:
            # Fallback to overall similarity
            return self._cosine_similarity(inst_emb, resp_emb)

        return sum(coverages) / len(coverages)

    def _keyword_overlap(self, text1: str, text2: str) -> float:
        """Compute keyword overlap between two texts."""
        # Extract significant words (4+ chars, alphabetic)
        pattern = r'\b[a-zA-Z]{4,}\b'
        words1 = set(re.findall(pattern, text1.lower()))
        words2 = set(re.findall(pattern, text2.lower()))

        if not words1:
            return 0.5  # Neutral

        overlap = len(words1 & words2)
        return min(1.0, overlap / len(words1))

    def _length_completeness(self, instruction: str, response: str) -> float:
        """Estimate completeness based on response length vs instruction."""
        inst_len = len(instruction.split())
        resp_len = len(response.split())

        if inst_len == 0:
            return 0.5

        ratio = resp_len / inst_len

        # Ideal: response is 2-10x instruction length
        if 2 <= ratio <= 10:
            return 1.0
        elif ratio < 2:
            return min(1.0, ratio / 2)
        else:
            return max(0.0, 1.0 - (ratio - 10) / 20)

    def _check_consistency(self, text: str) -> float:
        """Check for internal contradictions."""
        text_lower = text.lower()

        # Contradiction markers
        contradiction_patterns = [
            ("but", "however"),
            ("although", "yet"),
            ("on one hand", "on the other"),
            ("while", "nevertheless"),
            ("despite", "however"),
        ]

        contradictions_found = 0
        for pat1, pat2 in contradiction_patterns:
            if pat1 in text_lower and pat2 in text_lower:
                contradictions_found += 1

        # Penalize multiple contradictions
        if contradictions_found == 0:
            return 1.0
        elif contradictions_found == 1:
            return 0.8
        elif contradictions_found == 2:
            return 0.6
        else:
            return 0.4

    def _lexical_diversity(self, text: str) -> float:
        """Compute vocabulary diversity (type-token ratio)."""
        words = text.lower().split()
        if len(words) < 5:
            return 0.5  # Not enough data

        unique = len(set(words))
        ttr = unique / len(words)

        # Normalize to 0-1 scale (TTR naturally decreases with length)
        # Expected TTR for good text: 0.4-0.8
        if ttr < 0.3:
            return 0.2
        elif ttr > 0.9:
            return 0.8  # Suspiciously high
        else:
            return ttr

    def get_cache_stats(self) -> dict:
        """Return embedding cache statistics."""
        if self._cache is None:
            return {"enabled": False}
        return {
            "enabled": True,
            "size": len(self._cache),
        }


# Optional: Direct BGE model loading (if sentence-transformers installed)
def load_bge_model(model_name: str = "BAAI/bge-large-en-v1.5"):
    """Load BGE model directly (requires sentence-transformers).

    This is an alternative to using the router's embedding capability.
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        return model
    except ImportError:
        logger.warning("sentence-transformers not installed")
        return None
    except Exception as e:
        logger.warning(f"Failed to load BGE model: {e}")
        return None