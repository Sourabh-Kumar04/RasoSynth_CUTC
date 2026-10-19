"""Indic & Regional Cultural Safety Guardrails.

Provides safety checks for regional hate speech, caste-based slurs prohibited
under statutory frameworks (e.g., SC/ST Prevention of Atrocities Act), communal
incitement tropes, and script conformity validation for Indian languages.
"""

import re
from typing import Tuple, Optional

# Prohibited casteist, communal, and regional hate slurs (Latin & Devanagari patterns)
_PROHIBITED_CULTURAL_PATTERNS = [
    # Casteist slurs & discriminatory epithets
    r"\bchamar\b",
    r"\bchura\b",
    r"\bbhangi\b",
    r"\bchandal\b",
    r"\bmehtar\b",
    r"\bneech\s+jaati\b",
    r"चमार",
    r"भंगी",
    r"चूड़ा",
    r"नीच\s*जाति",
    # Communal & derogatory religious epithets
    r"\bkatwa\b",
    r"\bkatuva\b",
    r"\bkafir\s+ko\s+maro\b",
    r"\blandya\b",
    r"\bmulla\s+aatankwadi\b",
    r"कटवा",
    r"कतुआ",
    # Ethnic & regional slurs
    r"\bchinki\b",
    r"\bchin-ki\b",
    r"\byadav\s+raaj\s+hatao\b",
    r"चिंकी",
]

_CULTURAL_SAFETY_REGEX = re.compile(
    "|".join(_PROHIBITED_CULTURAL_PATTERNS),
    re.IGNORECASE | re.UNICODE,
)


def check_cultural_safety(text: str) -> Tuple[bool, Optional[str]]:
    """Check text against Indic cultural safety, communal, and caste guardrails.

    Returns:
        (is_safe, violation_reason)
    """
    if not text:
        return True, None

    match = _CULTURAL_SAFETY_REGEX.search(text)
    if match:
        matched_term = match.group(0)
        return False, f"Prohibited discriminatory or communal slur detected: '{matched_term}'"

    return True, None


def validate_script_conformity(text: str, language: str, script_mode: str = "native") -> Tuple[bool, Optional[str]]:
    """Verify that generated text conforms to the requested script orthography.

    Args:
        text: Text to evaluate.
        language: Language code (e.g. 'hi', 'hinglish', 'ta').
        script_mode: 'native' | 'romanized' | 'dual'

    Returns:
        (is_conforming, reason)
    """
    if not text or not text.strip():
        return True, None

    lang = (language or "en").lower().strip()
    mode = (script_mode or "native").lower().strip()

    # Hindi / Marathi in Native script -> Must contain Devanagari chars (\u0900-\u097F)
    if lang in ("hi", "hindi", "mr", "marathi") and mode == "native":
        devanagari_count = sum(1 for c in text if '\u0900' <= c <= '\u097f')
        if devanagari_count == 0:
            return False, f"Expected native Devanagari script for {lang}, but none was found."

    # Indic in Romanized script -> Must NOT be dominated by native Indic Unicode points
    elif mode == "romanized" and lang in ("hi", "hindi", "mr", "ta", "te", "bn", "gu", "kn", "ml", "pa"):
        indic_count = sum(1 for c in text if '\u0900' <= c <= '\u0d7f')
        if indic_count > len(text) * 0.25:
            return False, f"Expected Romanized (Latin) script for {lang}, but native Indic script characters dominated ({indic_count} chars)."

    return True, None
