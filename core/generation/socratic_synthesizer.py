"""Multi-Agent Dialectic Debate & Socratic Synthesizer.

Synthesizes multi-persona dialectic trajectories where two fictional
personas debate ambiguous statutory, regulatory, or architectural edge
cases before reaching a synthesis.

The personas are FICTIONAL characters, not real experts, auditors, or
lawyers, and the output is a fictional debate synthesis — NOT an
adjudication, NOT a consensus verdict, and NOT legal advice. Nothing here
is grounded in, or verified against, any statute.
"""

from typing import Any, Dict, List, Optional


DEFAULT_PERSONAS = {
    "taxation": [
        {"name": "Auditor Sharma", "role": "Strict Statutory Compliance & Revenue Protection", "fictional": True},
        {"name": "CFO Mehra", "role": "Commercial Optimization & Legitimate Business Deduction", "fictional": True},
    ],
    "legal": [
        {"name": "Counsel Verma", "role": "Prosecution / Statutory Non-Compliance Officer", "fictional": True},
        {"name": "Advocate Iyer", "role": "Defense / Constitutional Due Process Counsel", "fictional": True},
    ],
    "healthcare": [
        {"name": "Dr. Sen", "role": "Conservative Evidence-Based Diagnostic Reviewer", "fictional": True},
        {"name": "Dr. Reddy", "role": "Interventional Clinical Specialist", "fictional": True},
    ],
    "general": [
        {"name": "Agent Alpha", "role": "Statutory / Formal Constraints Analyst", "fictional": True},
        {"name": "Agent Beta", "role": "Pragmatic / Operational Feasibility Advocate", "fictional": True},
    ],
}


def build_dialectic_prompt_directive(domain: str = "taxation", rounds: int = 2) -> str:
    """Return prompt directive for multi-agent dialectic debate dataset generation."""
    personas = DEFAULT_PERSONAS.get(domain.lower(), DEFAULT_PERSONAS["general"])
    p1 = personas[0]
    p2 = personas[1]

    return (
        f"MULTI-AGENT DIALECTIC DEBATE SPECIFICATION:\n"
        f"1. Generate a structured Socratic debate between two fictional expert personas (these are invented characters, not real people):\n"
        f"   - Persona 1 ({p1['name']}, fictional): Focus on {p1['role']}.\n"
        f"   - Persona 2 ({p2['name']}, fictional): Focus on {p2['role']}.\n"
        f"2. Conduct {rounds} rounds of debate: Initial thesis, antithesis, and rebuttal.\n"
        f"3. Provide a final synthesis of the debate, explicitly labelled as a fictional debate synthesis — NOT a legal adjudication, NOT a consensus verdict, and NOT a verified resolution.\n"
        f"4. Output valid JSON with keys:\n"
        f"   - 'topic': Ambiguous statutory/domain inquiry\n"
        f"   - 'personas': List of fictional persona profiles (each flagged fictional)\n"
        f"   - 'debate_rounds': List of turns containing 'speaker', 'stance', and 'argument'\n"
        f"   - 'verdict': Debate synthesis with rationale (a fictional synthesis, not a legal verdict or adjudication)\n"
    )


def format_dialectic_sample(
    topic: str,
    debate_rounds: List[Dict[str, Any]],
    verdict: str,
    domain: Optional[str] = None,
    personas: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Format dialectic debate into structured SFT and conversational chat formats."""
    clean_rounds = []
    formatted_transcript = []

    for idx, r in enumerate(debate_rounds):
        spk = r.get("speaker", f"Expert {idx+1}")
        arg = r.get("argument", "").strip()
        stance = r.get("stance", "neutral")
        clean_rounds.append({"round": idx + 1, "speaker": spk, "stance": stance, "argument": arg})
        formatted_transcript.append(f"**[{spk}]**: {arg}")

    full_dialogue_text = "\n\n".join(formatted_transcript)
    full_response = f"{full_dialogue_text}\n\n### Synthesis (fictional debate — not an adjudication)\n{verdict.strip()}"

    raw_pers = personas or DEFAULT_PERSONAS.get((domain or "general").lower(), DEFAULT_PERSONAS["general"])
    pers = [dict(p, fictional=True) for p in raw_pers]

    return {
        "instruction": f"Debate and resolve: {topic.strip()}",
        "response": full_response,
        "topic": topic.strip(),
        "personas": pers,
        "debate_rounds": clean_rounds,
        "verdict": verdict.strip(),
        "synthesis": verdict.strip(),
        "metadata": {
            "type": "dialectic_debate",
            "provenance": "synthetic_fictional_debate_unverified",
            "personas_fictional": True,
            "domain": domain or "general",
            "total_rounds": len(clean_rounds),
        }
    }


def evaluate_dialectic_coherence(debate_rounds: List[Dict[str, Any]], verdict: str) -> Dict[str, Any]:
    """Evaluate debate balance, argumentation depth, and resolution synthesis.

    NOTE: the score is a length/structure heuristic (speaker count, words
    per round, verdict length). It does not measure argument quality,
    correctness, or legal soundness.
    """
    if not debate_rounds or len(debate_rounds) < 2:
        return {
            "is_valid": False,
            "coherence_score": 0.0,
            "method": "length_and_structure_heuristic_not_argument_quality",
            "issues": ["Dialectic debate requires at least 2 debate rounds."],
        }

    issues = []
    speakers = set()
    total_words = 0

    for idx, r in enumerate(debate_rounds):
        spk = r.get("speaker", "").strip()
        arg = r.get("argument", "").strip()
        words = len(arg.split())
        total_words += words
        speakers.add(spk)

        if words < 8:
            issues.append(f"Round {idx+1} argument is too brief ({words} words)")

    if len(speakers) < 2:
        issues.append("Debate must involve at least 2 distinct speaker personas.")

    verdict_words = len(verdict.strip().split())
    if verdict_words < 10:
        issues.append(f"Verdict is too brief ({verdict_words} words). Requires comprehensive statutory rationale.")

    has_multi_speaker = len(speakers) >= 2
    avg_words_per_round = total_words / max(len(debate_rounds), 1)
    substantive_arguments = avg_words_per_round >= 15

    score = round(
        (0.40 if has_multi_speaker else 0.10) +
        (0.30 if substantive_arguments else 0.15) +
        (0.30 if verdict_words >= 15 else 0.10),
        2
    )

    return {
        "is_valid": len(issues) == 0 and score >= 0.70,
        "coherence_score": score,
        "method": "length_and_structure_heuristic_not_argument_quality",
        "distinct_speakers": len(speakers),
        "total_rounds": len(debate_rounds),
        "issues": issues,
    }
