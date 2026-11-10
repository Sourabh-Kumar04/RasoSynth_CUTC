"""
Curriculum Sampling & Information Entropy Filter.

Provides:
- EntropyMetrics: Information density, Shannon entropy, and vocabulary ratio.
- CurriculumSampler: Ranks and filters instruction-response pairs into
  difficulty tiers (Foundational, Intermediate, Boundary/Hard) to optimize
  fine-tuning sample efficiency.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class CurriculumSample:
    instruction: str
    response: str
    entropy: float
    info_density: float
    difficulty_tier: int  # 1 (Foundational), 2 (Intermediate), 3 (Complex)
    keep: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class CurriculumSampler:
    """Ranks and filters datasets based on token entropy and lexical complexity."""

    def __init__(
        self,
        min_entropy: float = 2.5,
        max_entropy: float = 7.5,
        min_info_density: float = 0.35,
    ):
        self.min_entropy = min_entropy
        self.max_entropy = max_entropy
        self.min_info_density = min_info_density

    @staticmethod
    def calculate_shannon_entropy(text: str) -> float:
        """Compute Shannon entropy H(X) in bits per token."""
        tokens = text.lower().split()
        if not tokens:
            return 0.0
        counts = Counter(tokens)
        total = len(tokens)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return round(entropy, 3)

    @staticmethod
    def calculate_info_density(text: str) -> float:
        """Ratio of unique non-stopword tokens to total tokens."""
        tokens = [t for t in text.lower().split() if len(t) > 2]
        if not tokens:
            return 0.0
        unique = len(set(tokens))
        return round(unique / len(tokens), 3)

    def evaluate_sample(self, instruction: str, response: str) -> CurriculumSample:
        """Analyze information density and assign difficulty tier."""
        combined = f"{instruction} {response}"
        entropy = self.calculate_shannon_entropy(combined)
        density = self.calculate_info_density(combined)

        # Discard degenerate repetitive text (e.g. loops, template garbage)
        keep = (entropy >= self.min_entropy) and (density >= self.min_info_density)

        # Tier classification
        token_len = len(combined.split())
        if entropy > 5.0 and density > 0.65 and token_len > 60:
            tier = 3  # High-complexity / boundary case
        elif entropy > 3.8 and token_len > 30:
            tier = 2  # Intermediate
        else:
            tier = 1  # Foundational

        return CurriculumSample(
            instruction=instruction,
            response=response,
            entropy=entropy,
            info_density=density,
            difficulty_tier=tier,
            keep=keep,
        )

    def filter_and_tier_dataset(
        self,
        samples: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Process a list of samples, discarding degenerates and tiering the rest."""
        retained: List[CurriculumSample] = []
        discarded: int = 0
        tier_counts = {1: 0, 2: 0, 3: 0}

        for s in samples:
            inst = s.get("instruction") or s.get("prompt") or ""
            resp = s.get("response") or s.get("output") or ""
            if not inst or not resp:
                discarded += 1
                continue

            evaluated = self.evaluate_sample(inst, resp)
            if evaluated.keep:
                retained.append(evaluated)
                tier_counts[evaluated.difficulty_tier] += 1
            else:
                discarded += 1

        return {
            "total_evaluated": len(samples),
            "retained_count": len(retained),
            "discarded_count": discarded,
            "retention_rate": round(len(retained) / max(len(samples), 1), 3),
            "tier_distribution": tier_counts,
            "samples": [
                {
                    "instruction": cs.instruction,
                    "response": cs.response,
                    "entropy": cs.entropy,
                    "difficulty_tier": cs.difficulty_tier,
                }
                for cs in retained
            ],
        }
