"""Transliteration noise and chat/SMS shorthand augmentation for Hinglish and Indian conversational data.

Injects realistic texting patterns (e.g., 'kya kr rhe ho', 'aapka' -> 'apka', 'hai' -> 'h', 'nhi')
to train models robust against informal WhatsApp, SMS, and telephony customer queries.
"""

import random
import re
from typing import Any, Dict, List

_CHAT_REPLACEMENTS: Dict[str, List[str]] = {
    r"\baapka\b": ["apka", "apk"],
    r"\baapki\b": ["apki"],
    r"\baapke\b": ["apke"],
    r"\bhai\b": ["h", "hy", "he"],
    r"\bhain\b": ["hn", "h"],
    r"\bnahi\b": ["nhi", "ni", "nh"],
    r"\bnahin\b": ["nhi", "nh"],
    r"\bkar\b": ["kr"],
    r"\brahe\b": ["rhe"],
    r"\braha\b": ["rha"],
    r"\brahi\b": ["rhi"],
    r"\bbhi\b": ["b"],
    r"\btheek\b": ["thk", "tik"],
    r"\bkya\b": ["kia", "kya"],
    r"\bkyun\b": ["qun", "q"],
    r"\bkyu\b": ["q", "kyu"],
    r"\bkaise\b": ["kese", "kse"],
    r"\bkaisey\b": ["kese"],
    r"\bplease\b": ["pls", "plz"],
    r"\bthanks\b": ["thx", "ty", "tq"],
    r"\bthank you\b": ["tq", "thnx"],
    r"\bbecause\b": ["bcoz", "coz"],
    r"\bmessage\b": ["msg"],
    r"\btomorrow\b": ["tmrw"],
    r"\byou\b": ["u"],
    r"\byour\b": ["ur"],
    r"\bwith\b": ["w/"],
    r"\bwithout\b": ["w/o"],
    r"\babout\b": ["abt"],
    r"\bpeople\b": ["ppl"],
}


def inject_chat_noise(text: str, noise_level: float = 0.2, seed: int | None = None) -> str:
    """
    Augment Romanized Hindi / Hinglish text with realistic texting shorthands and phonetic noise.

    Args:
        text: Input text.
        noise_level: Probability between 0.0 and 1.0 of applying replacements to matching words.
        seed: Optional RNG seed for deterministic augmentation.

    Returns:
        Augmented noisy text.
    """
    if not text or noise_level <= 0.0:
        return text

    rng = random.Random(seed)
    augmented = text

    for pattern, options in _CHAT_REPLACEMENTS.items():
        compiled = re.compile(pattern, re.IGNORECASE)

        def _replace_match(match: re.Match) -> str:
            if rng.random() < noise_level:
                chosen = rng.choice(options)
                # Preserve capitalization
                original = match.group(0)
                if original.isupper():
                    return chosen.upper()
                if original[0].isupper():
                    return chosen.capitalize()
                return chosen
            return match.group(0)

        augmented = compiled.sub(_replace_match, augmented)

    return augmented


def inject_chat_noise_with_provenance(text: str, noise_level: float = 0.2, seed: int | None = None) -> Dict[str, Any]:
    """Augment text and return a record carrying a provenance flag.

    ``inject_chat_noise`` returns a bare string, so augmented text produced
    through it is indistinguishable from original text downstream. Use this
    helper when the record (not just the string) is stored: it keeps the
    original alongside the augmented form and flags the output as synthetic
    augmentation, not source text.
    """
    augmented = inject_chat_noise(text, noise_level=noise_level, seed=seed)
    return {
        "original_text": text,
        "augmented_text": augmented,
        "changed": augmented != text,
        "provenance": "synthetic_augmentation_transliteration_noise",
        "method": "chat_shorthand_replacement",
        "noise_level": noise_level,
        "verified": False,
    }
