"""Best-of-N Rejection Sampling & Consensus Filter.

Performs automated self-consistency verification across N candidate reasoning trajectories:
1. Canonical answer extraction and equivalence normalization.
2. Majority voting to identify the high-confidence consensus answer.
3. Selection of the optimal 'chosen' reasoning trajectory (cleanest derivation, best step structure).
4. Automated generation of DPO/SimPO/KTO preference pairs from rejected trajectories.

Honesty rule: a preference pair is emitted ONLY when at least one candidate
genuinely dissents from the consensus answer. When all candidates agree, no
"rejected" example exists, so ``preference_pair`` is ``None`` and
``rejected_responses`` is empty — an agreeing trajectory is never presented
as a rejected example. Emitted pairs carry a ``provenance`` flag: they are
synthetic, model-generated trajectories whose correctness was NOT verified
beyond canonical-answer agreement.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional
from core.generation.cot_synthesizer import extract_thought_and_solution


def normalize_canonical_answer(answer_str: str) -> str:
    """Normalize raw answer text for robust mathematical and statutory equivalence matching."""
    text = answer_str.strip().lower()
    # Remove comma grouping in numbers (e.g. 45,000 -> 45000)
    text = text.replace(",", "")
    # Strip common currency prefixes and symbols
    text = re.sub(r"(?:rs\.|inr|rupees|₹|\$)\s*", "", text)
    # Extract standalone numerical value if present
    num_match = re.search(r"\b\d+(?:\.\d+)?\b", text)
    if num_match:
        val = num_match.group(0)
        try:
            f = float(val)
            if f.is_integer():
                return str(int(f))
            return f"{f:.2f}"
        except ValueError:
            return val
    # Otherwise return cleaned lower text
    return re.sub(r"[^\w\s]", "", text).strip()


def score_reasoning_trajectory(thought: str, solution: str) -> float:
    """Score the clarity, structure, and conciseness of a reasoning trace."""
    score = 0.50
    words = len(thought.split())
    if 25 <= words <= 400:
        score += 0.25
    elif words > 400:
        score += 0.10  # verbosity penalty

    # Step markers
    step_markers = len(re.findall(r"(?:step\s*\d|pehle|first|then|phir|therefore|isliye)", thought.lower()))
    if step_markers >= 2:
        score += 0.15

    # Structured formula or arithmetic
    if any(op in thought for op in ["=", "+", "*", "-", "/", "%"]):
        score += 0.10

    return min(1.0, round(score, 2))


def filter_best_of_n(
    instruction: str,
    candidates: List[str],
    reference_answer: Optional[str] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform Best-of-N rejection sampling and consensus filtering."""
    if not candidates:
        return {
            "instruction": instruction,
            "status": "no_candidates",
            "consensus_rate": 0.0,
            "chosen_response": "",
            "rejected_responses": [],
            "rejected_note": "no_candidates",
            "preference_pair": None,
        }

    parsed_candidates = []
    canonical_answers = []

    for idx, cand in enumerate(candidates):
        thought_opt, solution = extract_thought_and_solution(cand)
        thought = thought_opt or ""

        # Extract last line or concise statement as answer
        ans_lines = [ln.strip() for ln in solution.split("\n") if ln.strip()]
        last_line = ans_lines[-1] if ans_lines else solution
        canon = normalize_canonical_answer(last_line)
        canonical_answers.append(canon)

        trajectory_score = score_reasoning_trajectory(thought, solution)

        parsed_candidates.append({
            "candidate_id": idx + 1,
            "full_text": cand,
            "thought": thought,
            "solution": solution,
            "canonical_answer": canon,
            "trajectory_score": trajectory_score,
        })

    # Majority voting
    counter = Counter(canonical_answers)
    if reference_answer:
        target_answer = normalize_canonical_answer(reference_answer)
    else:
        target_answer = counter.most_common(1)[0][0]

    votes_for_target = counter.get(target_answer, 0)
    consensus_rate = round(votes_for_target / len(candidates), 3)

    # Separate matching candidates (consensus) from dissenting candidates
    agreeing = [c for c in parsed_candidates if c["canonical_answer"] == target_answer]
    disagreeing = [c for c in parsed_candidates if c["canonical_answer"] != target_answer]

    if agreeing:
        # Pick agreeing candidate with highest trajectory score
        agreeing.sort(key=lambda x: x["trajectory_score"], reverse=True)
        chosen = agreeing[0]
    else:
        # Fallback to candidate with best trajectory if no consensus target matches
        parsed_candidates.sort(key=lambda x: x["trajectory_score"], reverse=True)
        chosen = parsed_candidates[0]

    # Rejected examples must genuinely dissent. When every candidate agrees
    # there is no rejected example: emitting the weakest agreeing trajectory
    # as "rejected" would teach the model to disprefer a correct answer.
    rejected_list = [c["full_text"] for c in disagreeing]
    rejected_note = None
    if not rejected_list:
        rejected_note = "all_candidates_agree_no_dissenting_rejected_example"

    chosen_full = chosen["full_text"]
    rejected_top = rejected_list[0] if rejected_list else ""

    preference_pair = None
    if rejected_top and rejected_top != chosen_full:
        preference_pair = {
            "instruction": instruction,
            "chosen": chosen_full,
            "rejected": rejected_top,
            "metadata": {
                "consensus_rate": consensus_rate,
                "domain": domain or "general",
                "target_answer": target_answer,
                "provenance": "synthetic_best_of_n_unverified",
                "rejected_is_dissenting": True,
            }
        }

    return {
        "instruction": instruction,
        "status": "consensus_reached" if consensus_rate >= 0.50 else "weak_consensus",
        "consensus_rate": consensus_rate,
        "total_candidates": len(candidates),
        "target_answer": target_answer,
        "chosen_response": chosen_full,
        "chosen_trajectory_score": chosen["trajectory_score"],
        "rejected_responses": rejected_list,
        "rejected_note": rejected_note,
        "preference_pair": preference_pair,
        "provenance": "synthetic_cot_trajectories_unverified",
        "candidate_summary": [
            {
                "id": c["candidate_id"],
                "canonical_answer": c["canonical_answer"],
                "trajectory_score": c["trajectory_score"],
                "is_chosen": c["candidate_id"] == chosen["candidate_id"],
            }
            for c in parsed_candidates
        ]
    }
