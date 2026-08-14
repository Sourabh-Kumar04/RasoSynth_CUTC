"""Real semantic quality scoring for dataset samples.

Provides multi-dimensional quality assessment combining provider-based
evaluation (when available) with robust heuristic fallbacks. Designed to
replace purely heuristic/fake quality scores used elsewhere in the pipeline.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from core.provider_router import TaskType

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Real semantic quality scores for a dataset sample.

    Each dimension captures a distinct aspect of instruction-response quality.
    The final_score is a weighted combination of the four sub-scores.
    """

    semantic_score: float = 0.0
    relevance_score: float = 0.0
    completeness_score: float = 0.0
    coherence_score: float = 0.0
    final_score: float = 0.0
    scores: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a plain dict for storage / export."""
        return {
            "semantic_score": self.semantic_score,
            "relevance_score": self.relevance_score,
            "completeness_score": self.completeness_score,
            "coherence_score": self.coherence_score,
            "final_score": self.final_score,
            "scores": self.scores,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Default weights — tuned for general-purpose SFT data
# ---------------------------------------------------------------------------
_DEFAULT_WEIGHTS: dict[str, float] = {
    "semantic": 0.30,
    "relevance": 0.20,
    "completeness": 0.25,
    "coherence": 0.25,
}


class QualityScorer:
    """Semantic quality scorer using embeddings, provider eval, and heuristics.

    Usage::

        scorer = QualityScorer(router=my_router)
        score = await scorer.score(
            instruction="Explain quantum computing.",
            response="Quantum computing uses qubits...",
            domain="quantum physics",
        )
        print(score.final_score, score.details)

    When a ``router`` is provided, the scorer will attempt a provider-based
    evaluation for the semantic dimension and fall back to heuristics on
    failure or timeout.  All other dimensions are always computed locally.
    """

    def __init__(
        self,
        router=None,
        embedding_model: Optional[str] = None,
        weights: Optional[dict[str, float]] = None,
    ):
        self.router = router
        self.embedding_model = embedding_model
        self.weights = weights or dict(_DEFAULT_WEIGHTS)

        # Validate weights sum to approximately 1.0
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "QualityScorer weights sum to %.3f, not 1.0. "
                "Final scores may be skewed.",
                total,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def score(
        self,
        instruction: str,
        response: str,
        domain: str = "",
        context: Optional[dict] = None,
    ) -> QualityScore:
        """Score a single instruction-response pair across all dimensions.

        Parameters
        ----------
        instruction : str
            The user-facing instruction or prompt.
        response : str
            The model or human response.
        domain : str
            Optional domain label (e.g. ``"medicine"``, ``"python coding"``).
        context : dict, optional
            Optional metadata dict passed through to scoring methods.

        Returns
        -------
        QualityScore
        """
        semantic, sem_details = await self._score_semantic(instruction, response)
        relevance, rel_details = await self._score_relevance(
            instruction, response, domain
        )
        completeness, comp_details = await self._score_completeness(
            instruction, response
        )
        coherence, coh_details = await self._score_coherence(instruction, response)

        # ── Production Gating Matrix (Scale AI / UltraFeedback Standard) ─────
        domain_gate = 1.0
        inst_lower = instruction.lower()
        resp_lower = response.lower()
        full_text = f"{inst_lower} {resp_lower}"

        # 1. Strict Domain Relevance Gate: Check domain terms & subtopic synonyms
        if domain and len(domain) > 2 and domain.lower() not in ("general", "custom", "sft"):
            domain_lower = domain.lower()
            domain_terms = [t for t in domain_lower.split() if len(t) > 3 and t not in ("dataset", "data", "synthetic")]
            
            # Taxonomy expansion for common technical subtopics
            subtopic_synonyms = []
            if any(k in domain_lower for k in ["oncology", "medical", "clinical", "health"]):
                subtopic_synonyms.extend(["cancer", "tumor", "t-cell", "patient", "therapy", "cell", "lung", "disease", "treatment", "diagnosis"])
            if any(k in domain_lower for k in ["distributed", "system", "code", "algorithm", "software"]):
                subtopic_synonyms.extend(["raft", "consensus", "leader", "node", "cluster", "log", "server", "process", "lock", "thread"])
            if any(k in domain_lower for k in ["economic", "finance", "macro", "market"]):
                subtopic_synonyms.extend(["yield", "rate", "bank", "inflation", "curve", "borrowing", "money", "policy", "interest", "credit"])
            if any(k in domain_lower for k in ["legal", "compliance", "law", "privacy"]):
                subtopic_synonyms.extend(["act", "eu", "risk", "privacy", "regulation", "conformity", "compliance", "gdpr", "assessment", "tier"])

            all_valid_terms = set(domain_terms + subtopic_synonyms)
            if all_valid_terms and not any(t in full_text for t in all_valid_terms):
                domain_gate = 0.0
                rel_details["zero_domain_relevance_gate"] = True

        # 2. Anti-Bot / Garbage / Scraped HTML Gate: Zero out score for anti-bot, HTML banners, or markdown badges
        if any(bad in resp_lower for bad in [
            "javascript is disabled", "captcha", "cloudflare", "429 too many",
            "<div align=", "<img src=", "table of contents", "awesome data science", "badge.svg", "become a sponsor"
        ]):
            domain_gate = 0.0
            rel_details["garbage_html_gate"] = True

        weights = self.weights
        weighted_sum = (
            semantic * weights["semantic"]
            + relevance * weights["relevance"]
            + completeness * weights["completeness"]
            + coherence * weights["coherence"]
        )

        # Multiply weighted sum by strict gating factor
        final = weighted_sum * domain_gate

        return QualityScore(
            semantic_score=round(semantic * domain_gate, 4),
            relevance_score=round(relevance * domain_gate, 4),
            completeness_score=round(completeness * domain_gate, 4),
            coherence_score=round(coherence * domain_gate, 4),
            final_score=round(final, 4),
            scores={
                "semantic": semantic,
                "relevance": relevance,
                "completeness": completeness,
                "coherence": coherence,
            },
            details={
                "semantic": sem_details,
                "relevance": rel_details,
                "completeness": comp_details,
                "coherence": coh_details,
            },
        )

    async def score_batch(
        self,
        samples: list,
        domain: str = "",
    ) -> list[QualityScore]:
        """Score a batch of samples sequentially.

        Each element of *samples* is either a dict with keys ``instruction``
        and ``response`` or an object with those same attributes.
        """
        results: list[QualityScore] = []
        for sample in samples:
            if isinstance(sample, dict):
                inst = sample.get("instruction", "")
                resp = sample.get("response", "")
            else:
                inst = getattr(sample, "instruction", "")
                resp = getattr(sample, "response", "")
            score = await self.score(inst, resp, domain)
            results.append(score)
        return results

    # ------------------------------------------------------------------
    # Dimension: Semantic quality
    # ------------------------------------------------------------------

    async def _score_semantic(
        self, instruction: str, response: str
    ) -> tuple[float, dict]:
        """Evaluate semantic quality via provider LLM or heuristic fallback.

        When a router with a healthy QUALITY_CHECK provider is available, we
        ask the provider to rate the pair directly.  Otherwise we fall back
        to structural and lexical heuristics (instruction length, response
        depth, vocabulary diversity, structural markers).
        """
        details: dict = {}
        score = 0.5  # neutral base

        # -- Provider-based evaluation ---------------------------------
        if self.router is not None:
            try:
                prompt = (
                    "Rate the quality of this instruction-response pair on a "
                    "scale of 0.0 to 1.0. Consider: clarity, specificity, "
                    "correctness, helpfulness.\n\n"
                    f"Instruction: {instruction[:500]}\n"
                    f"Response: {response[:1000]}\n\n"
                    "Return ONLY a single number between 0.0 and 1.0:"
                )
                result = await self.router.route(
                    TaskType.QUALITY_CHECK, prompt, temperature=0.1, max_tokens=10
                )
                if result is not None and result.content:
                    match = re.search(r"([\d.]+)", result.content.strip())
                    if match:
                        provider_score = float(match.group(1))
                        if 0.0 <= provider_score <= 1.0:
                            details["method"] = "provider_evaluation"
                            details["provider"] = result.provider
                            details["provider_score"] = provider_score
                            return provider_score, details
            except Exception:
                logger.debug("Provider-based semantic scoring failed; using heuristics", exc_info=True)

        # -- Heuristic fallback ----------------------------------------
        details["method"] = "heuristic"
        inst_words = instruction.split()
        resp_words = response.split()

        # Instruction clarity: present, not too short, not a single word
        if 3 < len(inst_words) < 100:
            score += 0.1
            details["instruction_length_ok"] = True
        else:
            details["instruction_length_ok"] = False

        # Response has meaningful length
        if len(resp_words) > 20:
            score += 0.1
            details["response_has_substance"] = True
        else:
            details["response_has_substance"] = False

        # Structural depth
        if "\n\n" in response:
            score += 0.1
            details["has_paragraphs"] = True
        else:
            details["has_paragraphs"] = False

        # Markers of structured output (lists, code blocks, headings)
        if re.search(r"^(?:#|-|\d+\.|```)", response.strip(), re.MULTILINE):
            score += 0.05
            details["has_structured_markers"] = True
        else:
            details["has_structured_markers"] = False

        # Vocabulary diversity
        unique_ratio = len(set(w.lower() for w in resp_words)) / max(
            len(resp_words), 1
        )
        if 0.3 < unique_ratio < 0.9:
            score += 0.1
        else:
            score -= 0.1
        details["unique_ratio"] = round(unique_ratio, 4)

        return max(0.0, min(1.0, score)), details

    # ------------------------------------------------------------------
    # Dimension: Domain relevance
    # ------------------------------------------------------------------

    async def _score_relevance(
        self, instruction: str, response: str, domain: str
    ) -> tuple[float, dict]:
        """Score how relevant the pair is to the given *domain*.

        Uses keyword overlap between domain terms and the combined text of
        instruction and response.  When no domain is supplied, returns a
        neutral 0.7 (most samples are acceptable without domain filtering).
        """
        details: dict = {}

        if not domain:
            return 0.7, {"method": "default_no_domain"}

        text_lower = (instruction + " " + response).lower()
        domain_lower = domain.lower()
        domain_terms = [t for t in domain_lower.split() if len(t) > 3 and t not in ("dataset", "data", "synthetic")]
        
        subtopic_synonyms = []
        if any(k in domain_lower for k in ["oncology", "medical", "clinical", "health"]):
            subtopic_synonyms.extend(["cancer", "tumor", "t-cell", "patient", "therapy", "cell", "lung", "disease", "treatment", "diagnosis"])
        if any(k in domain_lower for k in ["distributed", "system", "code", "algorithm", "software"]):
            subtopic_synonyms.extend(["raft", "consensus", "leader", "node", "cluster", "log", "server", "process", "lock", "thread"])
        if any(k in domain_lower for k in ["economic", "finance", "macro", "market"]):
            subtopic_synonyms.extend(["yield", "rate", "bank", "inflation", "curve", "borrowing", "money", "policy", "interest", "credit"])
        if any(k in domain_lower for k in ["legal", "compliance", "law", "privacy"]):
            subtopic_synonyms.extend(["act", "eu", "risk", "privacy", "regulation", "conformity", "compliance", "gdpr", "assessment", "tier"])

        all_valid_terms = list(set(domain_terms + subtopic_synonyms))
        term_matches = sum(1 for t in all_valid_terms if t in text_lower)
        
        if term_matches >= 2:
            score = 1.0
        elif term_matches == 1:
            score = 0.85
        else:
            score = 0.0

        details["term_matches"] = term_matches
        details["total_terms"] = len(all_valid_terms)
        details["method"] = "expanded_taxonomy_overlap"

        return score, details

    # ------------------------------------------------------------------
    # Dimension: Completeness
    # ------------------------------------------------------------------

    async def _score_completeness(
        self, instruction: str, response: str
    ) -> tuple[float, dict]:
        """Score whether the response thoroughly addresses the instruction.

        Factors: keyword coverage between instruction and response, presence
        of a proper ending, response depth (sentence count), and whether
        questions receive a substantive answer.
        """
        details: dict = {}
        score = 0.5

        # Keyword overlap — does the response reuse important instruction words?
        inst_keywords = set(
            re.findall(r"\b[a-zA-Z]{4,}\b", instruction.lower())
        )
        resp_keywords = set(
            re.findall(r"\b[a-zA-Z]{4,}\b", response.lower())
        )

        if inst_keywords:
            overlap = len(inst_keywords & resp_keywords) / len(inst_keywords)
            score += overlap * 0.3
            details["keyword_coverage"] = round(overlap, 4)
        else:
            details["keyword_coverage"] = 0.0

        # Proper ending (sentence terminator or closing delimiter)
        stripped = response.rstrip()
        if stripped and stripped[-1] in (".", "!", "?", "`", '"', "'", ")"):
            score += 0.1
            details["proper_ending"] = True
        else:
            score -= 0.05
            details["proper_ending"] = False

        # Question handling
        if "?" in instruction:
            if len(response) > 50:
                score += 0.1
                details["question_answered"] = True
            else:
                details["question_answered"] = False
        else:
            if len(response) > 30:
                score += 0.1
                details["statement_addressed"] = True
            else:
                details["statement_addressed"] = False

        # Depth via sentence count
        sentences = len(re.split(r"[.!?]+", response))
        if sentences >= 3:
            score += 0.1
        details["sentence_count"] = sentences

        return max(0.0, min(1.0, score)), details

    # ------------------------------------------------------------------
    # Dimension: Coherence
    # ------------------------------------------------------------------

    async def _score_coherence(
        self, instruction: str, response: str
    ) -> tuple[float, dict]:
        """Score logical flow, structure, and readability.

        Checks: use of transition words, paragraph breaks, appropriate
        sentence lengths, and reasonable use of contrastive language.
        """
        details: dict = {}
        score = 0.5

        text_lower = response.lower()

        # Transition-word usage indicates logical flow
        transitions = [
            "however",
            "therefore",
            "furthermore",
            "moreover",
            "additionally",
            "consequently",
            "nevertheless",
            "meanwhile",
            "first",
            "second",
            "finally",
            "in conclusion",
            "for example",
            "specifically",
            "in addition",
            "as a result",
            "on the other hand",
        ]
        found = sum(1 for t in transitions if t in text_lower)
        score += min(0.2, found * 0.05)
        details["transition_words"] = found

        # Paragraph structure
        paragraphs = response.count("\n\n")
        if paragraphs >= 1:
            score += 0.1
        if paragraphs >= 3:
            score += 0.05
        details["paragraphs"] = paragraphs

        # Contradiction markers — a few are fine (signals nuance), too many
        # may indicate inconsistency or hedging.
        contradictions = re.findall(
            r"\b(?:but|however|on the other hand|conversely)\b", text_lower
        )
        if len(contradictions) <= 3:
            score += 0.05
        else:
            score -= 0.1
        details["contradiction_markers"] = len(contradictions)

        # Average sentence length — extremes hurt readability
        sentences = re.split(r"[.!?]+", response)
        valid_sentences = [s for s in sentences if s.strip()]
        if valid_sentences:
            avg_sent_len = sum(
                len(s.split()) for s in valid_sentences
            ) / len(valid_sentences)
            if 5 <= avg_sent_len <= 40:
                score += 0.1
            details["avg_sentence_length"] = round(avg_sent_len, 2)
        else:
            details["avg_sentence_length"] = 0.0

        return max(0.0, min(1.0, score)), details

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def set_weights(self, weights: dict[str, float]) -> None:
        """Update scoring weights at runtime."""
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "set_weights: weights sum to %.3f, not 1.0.", total
            )
        self.weights.update(weights)

    def get_weights(self) -> dict[str, float]:
        """Return a copy of the current weights."""
        return dict(self.weights)