"""
Hallucination Detector — checks whether generated samples remain grounded in extracted sources.
"""
import re
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HallucinationResult:
    """Result of hallucination evaluation for a single sample."""
    source_grounding_score: float = 0.0    # 0-1: How well-grounded in source
    citation_match_score: float = 0.0      # 0-1: Citations match actual content
    hallucination_risk_score: float = 0.0  # 0-1: Risk (inverse of grounding)
    risk_level: str = "unknown"            # low, medium, high, critical
    details: dict = field(default_factory=dict)
    flagged_patterns: list[str] = field(default_factory=list)


class HallucinationDetector:
    """Detects hallucinations by comparing generated samples to source content."""

    def __init__(self, router=None, config: dict = None):
        self.router = router
        config = config or {}
        self.grounding_weight = config.get("grounding_weight", 0.6)
        self.citation_weight = config.get("citation_weight", 0.4)
        self.min_grounding_threshold = config.get("min_grounding_threshold", 0.3)

    async def evaluate(
        self,
        instruction: str,
        response: str,
        source_text: str,
        source_url: str = "",
    ) -> HallucinationResult:
        """Evaluate a generated sample against its source for hallucination risk."""
        grounding_score, grounding_details = await self._source_grounding_score(
            response, source_text
        )
        citation_score, citation_details = await self._citation_match_score(
            response, source_text
        )
        risk_score, flagged = await self._compute_hallucination_risk(
            grounding_score, citation_score, response, source_text
        )

        if risk_score < 0.3:
            risk_level = "low"
        elif risk_score < 0.5:
            risk_level = "medium"
        elif risk_score < 0.8:
            risk_level = "high"
        else:
            risk_level = "critical"

        return HallucinationResult(
            source_grounding_score=grounding_score,
            citation_match_score=citation_score,
            hallucination_risk_score=risk_score,
            risk_level=risk_level,
            details={
                "grounding": grounding_details,
                "citation": citation_details,
                "flagged": flagged,
            },
            flagged_patterns=flagged,
        )

    async def _source_grounding_score(
        self, response: str, source_text: str
    ) -> tuple[float, dict]:
        """Score how well the response is grounded in the source.

        Uses NER overlap, noun phrase overlap, and claim verification.
        """
        details = {}

        if not source_text or not response:
            return 0.0, {"error": "missing_source_or_response"}

        # 1. Extract entities from response
        resp_entities = self._extract_entities(response)
        source_entities = self._extract_entities(source_text)

        # 2. Entity overlap score
        if resp_entities:
            matched_entities = resp_entities & source_entities
            entity_overlap = len(matched_entities) / max(len(resp_entities), 1)
            details["entity_overlap"] = entity_overlap
            details["resp_entities"] = len(resp_entities)
            details["matched_entities"] = len(matched_entities)
        else:
            entity_overlap = 0.5  # Neutral if no entities found
            details["entity_overlap"] = entity_overlap

        # 3. Noun phrase overlap (key concepts)
        resp_phrases = self._extract_noun_phrases(response)
        source_phrases = self._extract_noun_phrases(source_text)

        if resp_phrases:
            phrase_overlap = (
                sum(1 for p in resp_phrases if p.lower() in source_text.lower())
                / max(len(resp_phrases), 1)
            )
            details["phrase_overlap"] = phrase_overlap
        else:
            phrase_overlap = 0.0

        # 4. Claim verification
        claims = self._extract_claims(response)
        verifiable = 0
        for claim in claims:
            if claim.lower() in source_text.lower():
                verifiable += 1

        if claims:
            claim_ratio = verifiable / len(claims)
            details["claims_verifiable"] = claim_ratio
            details["total_claims"] = len(claims)
        else:
            claim_ratio = 0.5

        # 5. Longest common substring ratio (simple text reuse detection)
        lcs_ratio = self._longest_common_substring_ratio(
            response[:2000].lower(), source_text[:5000].lower()
        )
        details["text_reuse_ratio"] = lcs_ratio

        # Weighted combination
        score = (
            entity_overlap * 0.30
            + phrase_overlap * 0.25
            + claim_ratio * 0.30
            + lcs_ratio * 0.15
        )

        # If source is very short, be conservative
        if len(source_text) < 50:
            details["short_source_warning"] = True
            score *= 0.5

        return max(0.0, min(1.0, score)), details

    async def _citation_match_score(
        self, response: str, source_text: str
    ) -> tuple[float, dict]:
        """Score how well citations in response match the source."""
        details = {}

        citations = self._extract_citations(response)

        if not citations:
            # No citations found — not necessarily a problem
            return 0.5, {"note": "no_citations_found", "citation_count": 0}

        verified = 0
        for citation in citations:
            # Check if cited text/source appears in source_text
            if citation.get("text", "").lower() in source_text.lower():
                verified += 1
            elif citation.get("name", "").lower() in source_text.lower():
                verified += 1

        score = verified / len(citations) if citations else 0.5
        details["verified_citations"] = verified
        details["total_citations"] = len(citations)

        return score, details

    async def _compute_hallucination_risk(
        self,
        grounding: float,
        citation: float,
        response: str,
        source_text: str,
    ) -> tuple[float, list[str]]:
        """Compute final hallucination risk and flag specific patterns."""
        risk = 1.0 - (
            grounding * self.grounding_weight + citation * self.citation_weight
        )

        flagged = []

        # Pattern: numerical/specific claims without source support
        numbers = re.findall(
            r"\b\d+[%x]\b|\b\d+\.\d+\b|\b(?:over|more than|less than|approximately|about)\s+\d+\b",
            response,
            re.IGNORECASE,
        )
        if numbers:
            unsupported_numbers = [
                n for n in numbers if n.lower() not in source_text.lower()
            ]
            if unsupported_numbers:
                flagged.append(
                    f"unsupported_numerical_claims: {len(unsupported_numbers)}"
                )

        # Pattern: absolute language
        absolutes = re.findall(
            r"\b(always|never|everyone|nobody|all|none|every|absolutely|certainly)\b",
            response,
            re.IGNORECASE,
        )
        if absolutes:
            flagged.append(f"absolute_language: {len(absolutes)}")

        # Pattern: named entities not in source
        resp_entities = self._extract_entities(response)
        source_entities = self._extract_entities(source_text)
        missing_entities = resp_entities - source_entities
        if missing_entities:
            flagged.append(
                f"entities_not_in_source: {', '.join(list(missing_entities)[:5])}"
            )

        # Pattern: specific temporal claims
        dates = re.findall(
            r"\b(?:January|February|March|April|May|June|"
            r"July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4}\b",
            response,
        )
        if dates:
            unsupported_dates = [d for d in dates if d not in source_text]
            if unsupported_dates:
                flagged.append(f"unsupported_dates: {len(unsupported_dates)}")

        return max(0.0, min(1.0, risk)), flagged

    def _extract_entities(self, text: str) -> set[str]:
        """Extract named entities using regex patterns."""
        entities = set()

        # Capitalized multi-word sequences (potential entities)
        matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
        entities.update(matches)

        # Single capitalized words (excluding start of sentence)
        sentences = re.split(r"[.!?]+\s+", text)
        for sent in sentences:
            # Skip first word of each sentence
            words = sent.split()
            for w in words[1:]:
                if w and w[0].isupper() and w.lower() not in (
                    "the", "a", "an", "this", "that", "these", "those",
                    "it", "its", "we", "they",
                ):
                    entities.add(w.rstrip(",.;:!?"))

        # Technical terms (all-caps or mixed case with digits)
        tech_terms = re.findall(r"\b[A-Z]{2,}\b|\b[A-Z][a-z]+\d+\b", text)
        entities.update(tech_terms)

        return entities

    def _extract_noun_phrases(self, text: str) -> list[str]:
        """Extract noun phrases using regex."""
        phrases = []
        # Adj+Noun pattern
        matches = re.findall(r"\b(?:[A-Z][a-z]+\s+)+[a-z]+\b", text)
        phrases.extend(matches)
        return phrases

    def _extract_claims(self, text: str) -> list[str]:
        """Extract factual claims from text."""
        claims = []
        sentences = re.split(r"[.!?]+", text)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            # Declarative sentences that make claims
            if sent[0].isupper() and any(
                w in sent.lower()
                for w in [
                    " is ", " are ", " was ", " were ",
                    " has ", " have ", " will ", " can ",
                    " may ", " must ", " should ",
                ]
            ):
                if len(sent) > 20:
                    claims.append(sent)
        return claims

    def _extract_citations(self, text: str) -> list[dict]:
        """Extract citation patterns from text."""
        citations = []

        # [1], [2,3], [1-4] style
        bracket_refs = re.findall(r"\[(\d+(?:[-,]\d+)*)\]", text)
        for ref in bracket_refs:
            citations.append(
                {"type": "bracket", "text": f"[{ref}]", "name": ref}
            )

        # (Author, Year) style
        author_refs = re.findall(
            r"\(([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4})\)", text
        )
        for ref in author_refs:
            citations.append(
                {
                    "type": "author_year",
                    "text": f"({ref})",
                    "name": ref.split(",")[0],
                }
            )

        # "According to X" pattern
        according_to = re.findall(
            r"According to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text
        )
        for ref in according_to:
            citations.append(
                {
                    "type": "attribution",
                    "text": f"According to {ref}",
                    "name": ref,
                }
            )

        return citations

    def _longest_common_substring_ratio(self, s1: str, s2: str) -> float:
        """Compute LCS ratio between two strings."""
        if not s1 or not s2:
            return 0.0

        m, n = len(s1), len(s2)
        if m * n > 1_000_000:  # Too expensive for very long strings
            # Sample approach: check overlapping substrings
            overlap = 0
            for i in range(0, len(s1), 100):
                chunk = s1[i : i + 100]
                if chunk in s2:
                    overlap += len(chunk)
            return min(1.0, overlap / len(s1))

        dp = [[0] * (n + 1) for _ in range(m + 1)]
        max_len = 0
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                    max_len = max(max_len, dp[i][j])

        return max_len / max(len(s1), 1)

    async def evaluate_batch(
        self, samples: list[dict]
    ) -> list[HallucinationResult]:
        """Batch evaluation for efficiency."""
        results = []
        for sample in samples:
            result = await self.evaluate(
                sample.get("instruction", ""),
                sample.get("response", ""),
                sample.get("source_text", ""),
                sample.get("source_url", ""),
            )
            results.append(result)
        return results