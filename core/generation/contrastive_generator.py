"""Contrastive Factual Perturbation & Critique Pair Synthesizer.

Synthesizes high-precision contrastive training pairs for reward modeling,
hallucination detection, and self-correction:
1. Systematic factual perturbation (numerical flips, statutory condition inversions, section swaps).
2. Automated critique generation explaining the exact discrepancy.
3. Formatted preference pairs (chosen vs. perturbed rejected) for alignment.
"""

import re
from typing import Any, Dict, List, Optional


def build_contrastive_prompt_directive() -> str:
    """Return system prompt directive for contrastive hallucination pair synthesis."""
    return (
        "CONTRASTIVE FACTUAL CRITIQUE SPECIFICATION:\n"
        "1. 'instruction': A user question requiring factual accuracy (taxation, healthcare, legal).\n"
        "2. 'grounded_response': A fully factual, grounded correct answer.\n"
        "3. 'perturbed_negative': A subtle hallucinated variation containing an intentional factual error "
        "(swapped statutory section, wrong arithmetic rate, or inverted condition).\n"
        "4. 'critique': A concise explanation pointing out the exact error in the perturbed negative.\n"
        "5. Output valid JSON with keys: 'instruction', 'grounded_response', 'perturbed_negative', 'perturbation_type', 'critique'.\n"
    )


def perturb_factual_statement(response: str) -> Dict[str, Any]:
    """Rule-based heuristic perturbation generator for creating contrastive negatives."""
    text = response.strip()

    # 1. Numerical percentage flip
    pct_match = re.search(r"(\b(?:5|12|18|28)\s*%)", text)
    if pct_match:
        original = pct_match.group(1)
        flipped = "28%" if "18%" in original else "18%" if "12%" in original else "12%"
        perturbed = text[:pct_match.start()] + flipped + text[pct_match.end():]
        return {
            "perturbed_text": perturbed,
            "perturbation_type": "numerical_rate_flip",
            "critique": f"Incorrect statutory rate applied: stated '{flipped}' instead of authentic rate '{original}'.",
        }

    # 2. Statutory condition inversion
    inversions = [
        ("mandatory", "optional"),
        ("compulsory", "voluntary"),
        ("exempted", "taxable"),
        ("allowed", "disallowed"),
        ("eligible", "ineligible"),
        ("jaruri hai", "optional hai"),
        ("anivarya", "aichhik"),
    ]
    for orig, inv in inversions:
        pattern = re.compile(rf"\b{orig}\b", re.IGNORECASE)
        if pattern.search(text):
            perturbed = pattern.sub(inv, text, count=1)
            return {
                "perturbed_text": perturbed,
                "perturbation_type": "statutory_condition_inversion",
                "critique": f"Inverted statutory obligation: stated '{inv}' when the law prescribes '{orig}'.",
            }

    # 3. Section swap
    sec_match = re.search(r"(?:Section|Dhara)\s*([0-9]{1,3}[A-Z]?)", text, re.IGNORECASE)
    if sec_match:
        orig_sec = sec_match.group(1)
        fake_sec = "80D" if orig_sec == "80C" else "47" if orig_sec == "16" else "99X"
        perturbed = text[:sec_match.start(1)] + fake_sec + text[sec_match.end(1):]
        return {
            "perturbed_text": perturbed,
            "perturbation_type": "section_misattribution",
            "critique": f"Misattributed statutory section: cited Section {fake_sec} instead of Section {orig_sec}.",
        }

    # Fallback negation insertion
    perturbed = "Contrary to standard regulations, " + text[0].lower() + text[1:]
    return {
        "perturbed_text": perturbed,
        "perturbation_type": "regulatory_contradiction",
        "critique": "Inserted contradiction disputing authentic statutory guidelines.",
    }


def synthesize_contrastive_pair(
    instruction: str,
    grounded_response: str,
    domain: Optional[str] = None,
    perturbation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a structured contrastive training pair with automated critique."""
    pert = perturbation or perturb_factual_statement(grounded_response)

    return {
        "instruction": instruction.strip(),
        "grounded_response": grounded_response.strip(),
        "perturbed_negative": pert["perturbed_text"].strip(),
        "perturbation_type": pert["perturbation_type"],
        "critique": pert["critique"],
        "preference_pair": {
            "instruction": instruction.strip(),
            "chosen": grounded_response.strip(),
            "rejected": pert["perturbed_text"].strip(),
            "metadata": {
                "domain": domain or "general",
                "perturbation_type": pert["perturbation_type"],
            }
        }
    }
