"""Grounding and citation verification system.

Detects hallucinations by verifying claims against source material
and checking citation coverage.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroundingScore:
    """Immutable grounding and citation metrics."""
    score: float                    # 0.0-1.0 overall grounding
    citation_coverage: float        # 0.0-1.0 % of claims with citations
    claim_support_ratio: float      # 0.0-1.0 % of cited claims verified
    unsupported_claims: list[str] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "grounding_score": round(self.score, 4),
            "citation_coverage": round(self.citation_coverage, 4),
            "claim_support_ratio": round(self.claim_support_ratio, 4),
            "unsupported_claims": self.unsupported_claims[:5],
            "missing_citations": self.missing_citations[:5],
            "details": self.details,
        }


class ClaimExtractor:
    """Extract factual claims from text."""

    # Claim patterns (regex)
    PATTERNS = [
        # "X is Y" statements
        r'([A-Z][^;.]{10,150})\s+is\s+([^;.]{5,150})',
        # Numerical/factual claims
        r'([A-Z][^;.]{0,100})\s+(\d+[\d\s%,.]+)\s*([^;.]{5,100})',
        # "According to X" claims
        r'(according to [^,.;]{5,100})',
        # Date-based claims
        r'(in \d{4}[^;.]{10,150})',
        # Definitive statements
        r'(the fact that [^;.]{10,150})',
        # Research/study claims
        r'((?:studies?|research) (?:show|indicate|find|suggest)[^.]{10,150})',
    ]

    def extract(self, text: str) -> list[str]:
        """Extract factual claims from text."""
        claims = []

        for pattern in self.PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    claim = ' '.join(str(m) for m in match if m)
                else:
                    claim = str(match)
                # Clean and normalize
                claim = ' '.join(claim.split())
                if len(claim) >= 15 and len(claim) <= 300:
                    claims.append(claim)

        # Deduplicate similar claims
        claims = self._deduplicate(claims)
        return claims

    def _deduplicate(self, claims: list[str]) -> list[str]:
        """Remove near-duplicate claims."""
        if len(claims) <= 1:
            return claims

        unique = []
        for claim in claims:
            is_dup = False
            for existing in unique:
                if self._similar(claim, existing):
                    is_dup = True
                    break
            if not is_dup:
                unique.append(claim)

        return unique

    def _similar(self, a: str, b: str) -> bool:
        """Check if two claims are similar."""
        # Simple word overlap check
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
        return overlap > 0.7


class CitationExtractor:
    """Extract and normalize citations."""

    PATTERNS = [
        # Numbered citations: [1], [23]
        (r'\[(\d+)\]', 'numbered'),
        # Parenthetical citations: (Smith et al., 2020)
        (r'\(([^)]+\d{4}[^)]*)\)', 'parenthetical'),
        # URLs
        (r'https?://\S+', 'url'),
        # Quoted text
        (r'"([^"]{10,200})"', 'quote'),
    ]

    def extract(self, text: str) -> list[dict[str, str]]:
        """Extract citations from text."""
        citations = []

        for pattern, cite_type in self.PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                citations.append({
                    "text": str(match),
                    "type": cite_type,
                })

        return citations


class SourceMatcher:
    """Match claims against source text."""

    def __init__(self, router=None, embedding_cache: Optional[dict] = None):
        self.router = router
        self._embedding_cache = embedding_cache or {}

    def verify_claim(self, claim: str, source: str) -> float:
        """Return 0.0-1.0 score for claim support by source."""
        if not source:
            return 0.5  # Neutral if no source

        # Level 1: Direct text containment
        if self._direct_contains(claim, source):
            return 1.0

        # Level 2: Keyword overlap
        kw_score = self._keyword_overlap(claim, source)

        # Level 3: Semantic similarity (if embeddings available)
        semantic_score = self._semantic_similarity(claim, source)

        # Combine scores
        if semantic_score is not None:
            return 0.4 * kw_score + 0.6 * semantic_score
        return kw_score

    def _direct_contains(self, claim: str, source: str) -> bool:
        """Check if claim appears verbatim in source."""
        claim_lower = claim.lower()
        source_lower = source.lower()

        # Full claim containment
        if claim_lower in source_lower:
            return True

        # Key phrase containment (3+ words)
        words = claim_lower.split()
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i+3])
            if phrase in source_lower:
                return True

        return False

    def _keyword_overlap(self, claim: str, source: str) -> float:
        """Jaccard-like keyword overlap."""
        claim_words = set(re.findall(r'\b\w{3,}\b', claim.lower()))
        source_words = set(re.findall(r'\b\w{3,}\b', source.lower()))

        if not claim_words:
            return 0.0

        overlap = len(claim_words & source_words)
        return overlap / len(claim_words)

    def _semantic_similarity(self, claim: str, source: str) -> Optional[float]:
        """Embedding-based semantic similarity."""
        if not self.router:
            return None

        try:
            # Get embeddings
            claim_key = f"claim:{claim[:200]}"
            source_key = f"source:{source[:500]}"

            if claim_key not in self._embedding_cache:
                emb = self.router.embed(claim[:512])
                self._embedding_cache[claim_key] = emb.embedding

            if source_key not in self._embedding_cache:
                emb = self.router.embed(source[:512])
                self._embedding_cache[source_key] = emb.embedding

            c_emb = self._embedding_cache[claim_key]
            s_emb = self._embedding_cache[source_key]

            # Cosine similarity
            dot = sum(a * b for a, b in zip(c_emb, s_emb))
            norm_c = sum(x * x for x in c_emb) ** 0.5
            norm_s = sum(x * x for x in s_emb) ** 0.5

            if norm_c == 0 or norm_s == 0:
                return 0.5

            return dot / (norm_c * norm_s)

        except Exception as e:
            logger.debug(f"Semantic similarity failed: {e}")
            return None


class GroundingScoreCalculator:
    """Calculate grounding and citation scores."""

    def __init__(
        self,
        router=None,
        claim_extractor: Optional[ClaimExtractor] = None,
        citation_extractor: Optional[CitationExtractor] = None,
        source_matcher: Optional[SourceMatcher] = None,
    ):
        self.router = router
        self.claim_extractor = claim_extractor or ClaimExtractor()
        self.citation_extractor = citation_extractor or CitationExtractor()
        self.source_matcher = source_matcher or SourceMatcher(router=router)

    def calculate(
        self,
        text: str,
        source: str = "",
    ) -> GroundingScore:
        """Calculate grounding metrics for a text."""
        details: dict[str, Any] = {}

        # Extract claims and citations
        claims = self.claim_extractor.extract(text)
        citations = self.citation_extractor.extract(text)

        details["total_claims"] = len(claims)
        details["total_citations"] = len(citations)
        details["has_source"] = bool(source)

        # No claims = neutral score
        if not claims:
            return GroundingScore(
                score=0.5,
                citation_coverage=0.5,
                claim_support_ratio=0.5,
                details=details,
            )

        # 1. Citation Coverage: % of claims near citations
        cited_claims = self._match_claims_to_citations(claims, citations, text)
        citation_coverage = len(cited_claims) / len(claims)

        # 2. Claim Support Ratio: % of claims verified against source
        unsupported = []
        supported_count = 0

        if source:
            for claim in claims:
                support_score = self.source_matcher.verify_claim(claim, source)
                if support_score >= 0.6:
                    supported_count += 1
                else:
                    unsupported.append(claim)
        else:
            # No source to verify against
            unsupported = claims

        claim_support_ratio = supported_count / len(claims)

        # 3. Overall Grounding Score
        if source:
            # Weight: 30% citation coverage, 70% actual support
            score = citation_coverage * 0.3 + claim_support_ratio * 0.7
        else:
            # No source = rely on citation presence alone
            score = citation_coverage * 0.5 + 0.25

        return GroundingScore(
            score=round(score, 4),
            citation_coverage=round(citation_coverage, 4),
            claim_support_ratio=round(claim_support_ratio, 4),
            unsupported_claims=unsupported[:10],
            missing_citations=[c for c in claims if c not in cited_claims][:10],
            details=details,
        )

    def _match_claims_to_citations(
        self,
        claims: list[str],
        citations: list[dict],
        text: str,
    ) -> list[str]:
        """Match claims to nearby citations."""
        cited = []

        for claim in claims:
            claim_pos = text.find(claim[:50])
            if claim_pos == -1:
                continue

            # Check if any citation is within 200 chars
            for cite in citations:
                cite_pos = text.find(cite["text"])
                if cite_pos == -1:
                    continue

                if abs(claim_pos - cite_pos) < 200:
                    cited.append(claim)
                    break

        return cited


class HallucinationDetector:
    """Detect potential hallucinations in text.

    Combines grounding verification with pattern-based detection.
    """

    # Hallucination indicator patterns
    HALLUCINATION_PATTERNS = [
        # False certainty markers
        (r'\b(definitely|certainly|absolutely|undoubtedly)\b', 0.1),
        # Unverifiable superlatives
        (r'\b(best|worst|first|only|never|always)\b', 0.05),
        # Specific numbers without context
        (r'\b(\d+(?:\.\d+)?%)\b', 0.05),
        # Fake authority appeals
        (r'\b(experts|scientists|studies)\b.*\b(show|prove|confirm)\b', 0.1),
    ]

    def __init__(self, router=None):
        self.router = router
        self.grounding_calculator = GroundingScoreCalculator(router=router)

    async def detect(
        self,
        text: str,
        source: str = "",
    ) -> dict[str, Any]:
        """Detect hallucination risk in text."""
        # Get grounding score
        grounding = self.grounding_calculator.calculate(text, source)

        # Pattern-based risk
        pattern_risk = self._pattern_risk(text)

        # Combined risk score
        # Low grounding + high pattern risk = high hallucination risk
        grounding_risk = 1.0 - grounding.score
        combined_risk = grounding_risk * 0.7 + pattern_risk * 0.3

        return {
            "hallucination_risk": round(combined_risk, 4),
            "grounding_score": grounding.score,
            "citation_coverage": grounding.citation_coverage,
            "claim_support_ratio": grounding.claim_support_ratio,
            "pattern_risk": round(pattern_risk, 4),
            "unsupported_claims": grounding.unsupported_claims,
            "risk_level": self._risk_level(combined_risk),
        }

    def _pattern_risk(self, text: str) -> float:
        """Calculate pattern-based hallucination risk."""
        risk = 0.0

        for pattern, weight in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            risk += min(weight * len(matches), weight * 5)  # Cap per pattern

        return min(1.0, risk)

    def _risk_level(self, risk: float) -> str:
        """Convert risk score to level."""
        if risk >= 0.7:
            return "critical"
        elif risk >= 0.5:
            return "high"
        elif risk >= 0.3:
            return "medium"
        else:
            return "low"


# Convenience function
async def calculate_grounding(
    text: str,
    source: str = "",
    router=None,
) -> GroundingScore:
    """Calculate grounding score for text."""
    calc = GroundingScoreCalculator(router=router)
    return calc.calculate(text, source)


async def detect_hallucination(
    text: str,
    source: str = "",
    router=None,
) -> dict[str, Any]:
    """Detect hallucination risk in text."""
    detector = HallucinationDetector(router=router)
    return await detector.detect(text, source)