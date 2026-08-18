"""
Dataset Diversity Engine — measures diversity across 5 dimensions.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DiversityMetrics:
    """Diversity metrics across all dimensions."""
    topic_diversity: float = 0.0
    source_diversity: float = 0.0
    instruction_diversity: float = 0.0
    response_diversity: float = 0.0
    domain_diversity: float = 0.0
    overall_diversity: float = 0.0
    entropies: dict = field(default_factory=dict)
    distributions: dict = field(default_factory=dict)


class DatasetDiversityAnalyzer:
    """Analyzes dataset diversity across multiple dimensions."""

    # Weights for overall score
    DIMENSION_WEIGHTS = {
        "topic": 0.25,
        "source": 0.20,
        "instruction": 0.20,
        "response": 0.15,
        "domain": 0.20,
    }

    def __init__(self, router=None):
        self.router = router

    async def analyze(
        self, samples: list, domains: list[str] = None
    ) -> DiversityMetrics:
        """
        Analyze diversity across all dimensions.
        samples can be list of ConstructedSample objects or dicts with
        instruction/response/metadata keys.
        """
        texts = []
        sources = []
        instructions = []
        responses = []

        for s in samples:
            if isinstance(s, dict):
                texts.append(
                    s.get("content", "")
                    or s.get("instruction", "")
                    or s.get("response", "")
                )
                sources.append(
                    s.get("source_url", "")
                    or s.get("metadata", {}).get("source_url", "")
                )
                instructions.append(s.get("instruction", ""))
                responses.append(s.get("response", ""))
            else:
                texts.append(
                    getattr(s, "content", "")
                    or getattr(s, "instruction", "")
                )
                sources.append(
                    getattr(s, "source_url", "")
                    or getattr(s, "metadata", {}).get("source_url", "")
                )
                instructions.append(getattr(s, "instruction", ""))
                responses.append(getattr(s, "response", ""))

        # Compute all dimensions
        topic_div, topic_dist = await self._topic_diversity(texts)
        source_div, source_dist = self._source_diversity(sources)
        instr_div, instr_dist = self._instruction_diversity(instructions)
        resp_div, resp_dist = self._response_diversity(responses)
        dom_div, dom_dist = self._domain_diversity(texts, domains)

        overall = (
            topic_div * self.DIMENSION_WEIGHTS["topic"]
            + source_div * self.DIMENSION_WEIGHTS["source"]
            + instr_div * self.DIMENSION_WEIGHTS["instruction"]
            + resp_div * self.DIMENSION_WEIGHTS["response"]
            + dom_div * self.DIMENSION_WEIGHTS["domain"]
        )

        return DiversityMetrics(
            topic_diversity=topic_div,
            source_diversity=source_div,
            instruction_diversity=instr_div,
            response_diversity=resp_div,
            domain_diversity=dom_div,
            overall_diversity=overall,
            entropies={
                "topic": self._shannon_entropy(topic_dist) if topic_dist else 0,
                "source": self._shannon_entropy(source_dist) if source_dist else 0,
                "instruction": (
                    self._shannon_entropy(instr_dist) if instr_dist else 0
                ),
                "response": self._shannon_entropy(resp_dist) if resp_dist else 0,
            },
            distributions={
                "topic": topic_dist,
                "source": source_dist,
                "instruction": instr_dist,
                "response": resp_dist,
            },
        )

    async def _topic_diversity(
        self, texts: list[str]
    ) -> tuple[float, dict]:
        """Measure topic diversity.

        Uses keyword-based topic extraction + TF-IDF style clustering.
        Extracts topic-relevant keywords and groups into clusters.
        """
        if not texts:
            return 0.0, {}

        # Extract topic keywords from each text
        all_words = []
        for text in texts:
            words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
            # Filter common stopwords
            stopwords = {
                "this",
                "that",
                "with",
                "from",
                "have",
                "been",
                "were",
                "they",
                "their",
                "what",
                "which",
                "when",
                "where",
                "about",
                "into",
                "than",
                "then",
                "some",
                "also",
                "more",
                "these",
                "would",
                "could",
                "should",
            }
            content_words = [
                w for w in words if w not in stopwords and len(w) > 3
            ]
            all_words.extend(content_words)

        # Count word frequencies (topic signal)
        word_freq = Counter(all_words)
        if not word_freq:
            return 0.5, {"note": "insufficient_words"}

        # Compute topic entropy based on word distribution
        total = sum(word_freq.values())
        entropy = self._shannon_entropy(word_freq)
        max_entropy = (
            math.log2(len(word_freq)) if len(word_freq) > 1 else 1
        )
        normalized_entropy = (
            entropy / max_entropy if max_entropy > 0 else 0.5
        )

        # Penalize if too few unique topics
        if len(word_freq) < 5:
            normalized_entropy *= 0.5

        return normalized_entropy, dict(word_freq.most_common(50))

    def _source_diversity(
        self, sources: list[str]
    ) -> tuple[float, dict]:
        """Measure source diversity using domain distribution."""
        from urllib.parse import urlparse

        if not sources or all(s == "" for s in sources):
            return 0.5, {"note": "no_sources"}

        domains = []
        for url in sources:
            try:
                domain = urlparse(url).netloc
                if domain:
                    domains.append(domain)
            except Exception:
                domains.append("unknown")

        if not domains:
            return 0.3, {"note": "no_valid_domains"}

        domain_counts = Counter(domains)
        entropy = self._shannon_entropy(domain_counts)
        max_entropy = (
            math.log2(len(domain_counts)) if len(domain_counts) > 1 else 1
        )
        normalized = entropy / max_entropy if max_entropy > 0 else 0

        # Bonus for more sources
        source_bonus = min(0.2, len(domain_counts) * 0.02)

        return (
            min(1.0, normalized * 0.8 + source_bonus),
            dict(domain_counts.most_common(20)),
        )

    def _instruction_diversity(
        self, instructions: list[str]
    ) -> tuple[float, dict]:
        """Measure instruction diversity."""
        if not instructions:
            return 0.0, {}

        # Classify by first verb/task type
        task_types = Counter()
        lengths = []

        for inst in instructions:
            inst_lower = inst.lower().strip()

            # Classify instruction type
            if inst_lower.startswith(
                ("what", "who", "when", "where", "which")
            ):
                task_types["factual_question"] += 1
            elif inst_lower.startswith(
                ("why", "how", "explain", "describe")
            ):
                task_types["explanatory"] += 1
            elif inst_lower.startswith(
                ("write", "generate", "create", "produce", "compose")
            ):
                task_types["generative"] += 1
            elif inst_lower.startswith(
                ("summarize", "summarise", "condense")
            ):
                task_types["summarization"] += 1
            elif inst_lower.startswith(
                ("classify", "categorize", "label", "tag")
            ):
                task_types["classification"] += 1
            elif inst_lower.startswith(
                ("compare", "contrast", "differentiate")
            ):
                task_types["comparison"] += 1
            elif inst_lower.startswith(
                ("list", "enumerate", "give", "provide", "find")
            ):
                task_types["listing"] += 1
            elif inst_lower.startswith(
                ("translate", "convert", "transform")
            ):
                task_types["translation"] += 1
            elif inst_lower.startswith(
                ("analyze", "evaluate", "assess", "critique")
            ):
                task_types["analysis"] += 1
            elif inst_lower.startswith(
                ("code", "implement", "program", "debug", "refactor")
            ):
                task_types["coding"] += 1
            else:
                task_types["other"] += 1

            lengths.append(len(inst.split()))

        if not task_types:
            return 0.3, {"note": "unclassifiable"}

        # Entropy of type distribution
        entropy = self._shannon_entropy(task_types)
        max_entropy = (
            math.log2(len(task_types)) if len(task_types) > 1 else 1
        )
        type_diversity = entropy / max_entropy if max_entropy > 0 else 0

        # Length diversity
        if lengths:
            length_counts = Counter(
                [l // 10 * 10 for l in lengths]
            )  # Bucket by 10s
            len_entropy = self._shannon_entropy(length_counts)
            len_max = (
                math.log2(len(length_counts))
                if len(length_counts) > 1
                else 1
            )
            len_diversity = len_entropy / len_max if len_max > 0 else 0.5
        else:
            len_diversity = 0.5

        score = type_diversity * 0.7 + len_diversity * 0.3
        return score, {
            "task_types": dict(task_types),
            "length_diversity": len_diversity,
        }

    def _response_diversity(
        self, responses: list[str]
    ) -> tuple[float, dict]:
        """Measure response diversity."""
        if not responses:
            return 0.0, {}

        format_types = Counter()
        lengths = []

        for resp in responses:
            # Detect format
            if resp.strip().startswith("```"):
                format_types["code_block"] += 1
            elif "|" in resp and "\n|" in resp:
                format_types["table"] += 1
            elif resp.count("\n") > 5:
                format_types["long_form"] += 1
            elif resp.strip().startswith(("-", "*", "•", "1.")):
                format_types["list"] += 1
            elif len(resp) < 100:
                format_types["short"] += 1
            else:
                format_types["paragraph"] += 1

            lengths.append(len(resp.split()))

        # Format entropy
        entropy = self._shannon_entropy(format_types)
        max_entropy = (
            math.log2(len(format_types)) if len(format_types) > 1 else 1
        )
        format_diversity = entropy / max_entropy if max_entropy > 0 else 0

        # Length distribution
        if lengths:
            length_counts = Counter()
            for l in lengths:
                if l < 20:
                    length_counts["very_short"] += 1
                elif l < 50:
                    length_counts["short"] += 1
                elif l < 150:
                    length_counts["medium"] += 1
                elif l < 500:
                    length_counts["long"] += 1
                else:
                    length_counts["very_long"] += 1

            len_entropy = self._shannon_entropy(length_counts)
            len_max = (
                math.log2(len(length_counts))
                if len(length_counts) > 1
                else 1
            )
            length_diversity = len_entropy / len_max if len_max > 0 else 0.5
        else:
            length_diversity = 0.5

        score = format_diversity * 0.6 + length_diversity * 0.4
        return score, {
            "formats": dict(format_types),
            "length_diversity": length_diversity,
        }

    def _domain_diversity(
        self, texts: list[str], domains: list[str] = None
    ) -> tuple[float, dict]:
        """Measure domain coverage."""
        if domains:
            domain_counts = Counter(domains)
            entropy = self._shannon_entropy(domain_counts)
            max_entropy = (
                math.log2(len(domain_counts))
                if len(domain_counts) > 1
                else 1
            )
            return (
                entropy / max_entropy if max_entropy > 0 else 0.5,
                dict(domain_counts),
            )

        if not texts:
            return 0.0, {}

        # Infer domains from keyword analysis
        domain_keywords = {
            "technology": [
                "software",
                "code",
                "api",
                "database",
                "server",
                "cloud",
                "computer",
                "algorithm",
                "programming",
                "web",
            ],
            "science": [
                "research",
                "study",
                "analysis",
                "experiment",
                "data",
                "scientific",
                "methodology",
                "hypothesis",
            ],
            "business": [
                "market",
                "strategy",
                "management",
                "revenue",
                "customer",
                "product",
                "startup",
                "investment",
            ],
            "education": [
                "learning",
                "teaching",
                "curriculum",
                "student",
                "course",
                "training",
                "education",
                "knowledge",
            ],
            "health": [
                "medical",
                "health",
                "patient",
                "treatment",
                "disease",
                "clinical",
                "therapy",
                "diagnosis",
            ],
            "finance": [
                "financial",
                "banking",
                "investment",
                "stock",
                "trading",
                "asset",
                "portfolio",
                "risk",
            ],
            "creative": [
                "design",
                "art",
                "creative",
                "writing",
                "content",
                "media",
                "video",
                "audio",
            ],
            "legal": [
                "law",
                "legal",
                "regulation",
                "compliance",
                "policy",
                "rights",
                "contract",
                "patent",
            ],
        }

        domain_scores = {k: 0 for k in domain_keywords}
        for text in texts:
            text_lower = text.lower()
            for domain, keywords in domain_keywords.items():
                for kw in keywords:
                    if kw in text_lower:
                        domain_scores[domain] += 1

        total = sum(domain_scores.values()) or 1
        domain_dist = {
            k: v / total for k, v in domain_scores.items() if v > 0
        }

        if not domain_dist:
            return 0.3, {"note": "no_domains_detected"}

        entropy = self._shannon_entropy(domain_dist)
        max_entropy = (
            math.log2(len(domain_dist)) if len(domain_dist) > 1 else 1
        )
        return (
            entropy / max_entropy if max_entropy > 0 else 0.5,
            domain_dist,
        )

    def _shannon_entropy(self, counts: dict) -> float:
        """Compute Shannon entropy from a count or probability distribution."""
        # Filter to only numeric values — dict may contain sentinel strings or nested dicts
        numeric = {k: v for k, v in counts.items() if isinstance(v, (int, float))}
        total = sum(numeric.values()) if numeric else 0
        if total == 0:
            return 0.0
        entropy = 0.0
        for count in numeric.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        return entropy

    def get_report(self, metrics: DiversityMetrics) -> dict:
        """Generate a human-readable diversity report."""
        return {
            "overall_diversity": round(metrics.overall_diversity, 3),
            "dimensions": {
                "topic": {
                    "score": round(metrics.topic_diversity, 3),
                    "rating": self._rating(metrics.topic_diversity),
                },
                "source": {
                    "score": round(metrics.source_diversity, 3),
                    "rating": self._rating(metrics.source_diversity),
                },
                "instruction": {
                    "score": round(metrics.instruction_diversity, 3),
                    "rating": self._rating(metrics.instruction_diversity),
                },
                "response": {
                    "score": round(metrics.response_diversity, 3),
                    "rating": self._rating(metrics.response_diversity),
                },
                "domain": {
                    "score": round(metrics.domain_diversity, 3),
                    "rating": self._rating(metrics.domain_diversity),
                },
            },
            "interpretation": {
                "very_high": "0.8-1.0: Excellent diversity, well-balanced dataset",
                "high": "0.6-0.8: Good diversity, minor imbalances",
                "medium": "0.4-0.6: Moderate diversity, consider augmentation",
                "low": "0.2-0.4: Low diversity, needs more variety",
                "very_low": "0.0-0.2: Very low diversity, significant augmentation needed",
            },
            "entropies": metrics.entropies,
        }

    def _rating(self, score: float) -> str:
        if score >= 0.8:
            return "very_high"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.2:
            return "low"
        return "very_low"