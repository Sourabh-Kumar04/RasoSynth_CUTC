"""Curriculum Learning & Training Sequence Sorter.

Organizes dataset samples into calibrated pedagogical difficulty stages (Tier 1-2 -> 3-4 -> 5)
with optional anti-catastrophic forgetting replay buffer interleaving.
"""

from typing import Any, Dict, List, Literal


def sort_by_curriculum(
    samples: List[Dict[str, Any]],
    mode: Literal["ascending", "staged_curriculum", "replay_interleaved"] = "staged_curriculum",
    replay_ratio: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    Sort or partition dataset samples according to curriculum learning principles.

    Args:
        samples: List of sample dictionaries containing 'difficulty_tier' (1-5).
        mode:
          - 'ascending': Strictly ordered from Tier 1 up to Tier 5.
          - 'staged_curriculum': Partitioned into Stage 1 (Foundations), Stage 2 (Applied Reasoning), Stage 3 (Edge/DPO).
          - 'replay_interleaved': Staged curriculum with replay buffer interleaving to prevent catastrophic forgetting.
        replay_ratio: Fraction of foundational samples to replay into later stages.

    Returns:
        Curriculum-sequenced list of samples.
    """
    if not samples:
        return []

    def get_tier(s: Dict[str, Any]) -> int:
        tier = s.get("difficulty_tier")
        if tier is None and isinstance(s.get("metadata"), dict):
            tier = s["metadata"].get("difficulty_tier")
        try:
            return int(tier) if tier is not None else 3
        except (ValueError, TypeError):
            return 3

    if mode == "ascending":
        return sorted(samples, key=get_tier)

    # Group by tiers
    foundations = [s for s in samples if get_tier(s) <= 2]
    intermediate = [s for s in samples if get_tier(s) in (3, 4)]
    advanced = [s for s in samples if get_tier(s) >= 5]

    if mode == "staged_curriculum":
        return foundations + intermediate + advanced

    # Replay interleaved mode
    res = list(foundations)
    replay_pool = list(foundations)

    if replay_pool and replay_ratio > 0:
        inter_chunk = []
        for i, s in enumerate(intermediate):
            inter_chunk.append(s)
            if (i + 1) % int(1.0 / replay_ratio) == 0:
                inter_chunk.append(replay_pool[i % len(replay_pool)])
        res.extend(inter_chunk)

        adv_chunk = []
        for i, s in enumerate(advanced):
            adv_chunk.append(s)
            if (i + 1) % int(1.0 / replay_ratio) == 0:
                adv_chunk.append(replay_pool[i % len(replay_pool)])
        res.extend(adv_chunk)
    else:
        res.extend(intermediate)
    return res


def estimate_sample_complexity(sample: Dict[str, Any]) -> float:
    """Estimate a numerical complexity score (1.0 - 5.0) for a dataset sample.

    Considers explicit difficulty tiers, presence of thought reasoning traces,
    instruction/response length, and structural tokens.
    """
    tier = sample.get("difficulty_tier")
    if tier is None and isinstance(sample.get("metadata"), dict):
        tier = sample["metadata"].get("difficulty_tier")
    if tier is not None:
        try:
            return float(tier)
        except (ValueError, TypeError):
            pass

    text = f"{sample.get('instruction', '')} {sample.get('response', '')}"
    base_score = 2.0
    if "<thought>" in text:
        base_score += 1.5
    if len(text.split()) > 100:
        base_score += 1.0
    elif len(text.split()) > 40:
        base_score += 0.5
    return min(5.0, max(1.0, base_score))
