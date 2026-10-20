"""Chain-of-Thought (CoT) Reasoning Trajectory Synthesizer.

Generates explicit step-by-step reasoning traces enclosed in `<thought>...</thought>` tags
(DeepSeek-R1 / OpenAI o1 style) in English, Hindi, or Hinglish before producing the final response.
"""

import re
from typing import Dict, Optional, Tuple


def build_cot_prompt_directive(language: str = "en") -> str:
    """Build instruction directing the LLM to output explicit Chain-of-Thought reasoning traces."""
    lang = (language or "en").lower().strip()
    
    if "hi" in lang or "hinglish" in lang:
        reasoning_lang_note = "Reasoning can be in natural analytical Hinglish or Hindi matching the domain complexity."
    else:
        reasoning_lang_note = "Reasoning should be analytical and structured in clear logical steps."

    return (
        "Chain-of-Thought Reasoning Directive:\n"
        "Your 'response' MUST begin with an explicit step-by-step reasoning trajectory enclosed within "
        "<thought>...</thought> tags, followed by the definitive final answer outside the tags.\n"
        f"- {reasoning_lang_note}\n"
        "- In the <thought> block: deconstruct the user prompt, verify statutory or technical constraints, "
        "check for edge cases, calculate values if needed, and deliberate on the best explanation.\n"
        "- Outside the <thought> block: provide the polished, structured final answer for the user."
    )


def extract_thought_and_solution(text: str) -> Tuple[Optional[str], str]:
    """
    Separate <thought>...</thought> reasoning trace from the final solution.

    Returns:
        Tuple of (thought_text or None, final_solution_text).
    """
    if not text:
        return None, ""

    match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL | re.IGNORECASE)
    if match:
        thought = match.group(1).strip()
        solution = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        return thought, solution

    # Check alternative tag: <reasoning>...</reasoning>
    match_r = re.search(r"<reasoning>(.*?)</reasoning>", text, re.DOTALL | re.IGNORECASE)
    if match_r:
        thought = match_r.group(1).strip()
        solution = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        return thought, solution

    return None, text.strip()


def wrap_with_thought(thought: str, solution: str) -> str:
    """Combine thought and solution into canonical DeepSeek-R1 format."""
    clean_thought = (thought or "").strip()
    clean_sol = (solution or "").strip()
    if clean_thought:
        return f"<thought>\n{clean_thought}\n</thought>\n\n{clean_sol}"
    return clean_sol
