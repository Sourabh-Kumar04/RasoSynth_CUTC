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


# Script Unicode ranges for orthography verification
_SCRIPT_SPECS: dict[tuple[str, ...], tuple[str, list[tuple[str, str]]]] = {
    # Devanagari: Hindi, Marathi, Nepali, Sanskrit
    ("hi", "hindi", "mr", "marathi", "ne", "nepali", "sa", "sanskrit"): (
        "Devanagari",
        [('\u0900', '\u097f')],
    ),
    # Bengali & Assamese
    ("bn", "bengali", "as", "assamese"): (
        "Bengali",
        [('\u0980', '\u09ff')],
    ),
    # Gurmukhi / Punjabi
    ("pa", "punjabi", "panjabi"): (
        "Gurmukhi",
        [('\u0a00', '\u0a7f')],
    ),
    # Gujarati
    ("gu", "gujarati"): (
        "Gujarati",
        [('\u0a80', '\u0aff')],
    ),
    # Odia / Oriya
    ("or", "odia", "oriya"): (
        "Odia",
        [('\u0b00', '\u0b7f')],
    ),
    # Tamil
    ("ta", "tamil"): (
        "Tamil",
        [('\u0b80', '\u0bff')],
    ),
    # Telugu
    ("te", "telugu"): (
        "Telugu",
        [('\u0c00', '\u0c7f')],
    ),
    # Kannada
    ("kn", "kannada"): (
        "Kannada",
        [('\u0c80', '\u0cff')],
    ),
    # Malayalam
    ("ml", "malayalam"): (
        "Malayalam",
        [('\u0d00', '\u0d7f')],
    ),
    # Arabic / Urdu
    ("ar", "arabic", "ur", "urdu"): (
        "Arabic",
        [('\u0600', '\u06ff'), ('\u0750', '\u077f'), ('\u08a0', '\u08ff')],
    ),
    # Chinese (Hanzi)
    ("zh", "chinese", "mandarin"): (
        "Chinese",
        [('\u4e00', '\u9fff')],
    ),
    # Japanese (Hiragana, Katakana, Kanji)
    ("ja", "japanese"): (
        "Japanese",
        [('\u3040', '\u309f'), ('\u30a0', '\u30ff'), ('\u4e00', '\u9fff')],
    ),
    # Korean (Hangul)
    ("ko", "korean"): (
        "Hangul",
        [('\uac00', '\ud7af'), ('\u1100', '\u11ff')],
    ),
    # Cyrillic: Russian, Ukrainian
    ("ru", "russian", "uk", "ukrainian"): (
        "Cyrillic",
        [('\u0400', '\u04ff')],
    ),
}


def validate_script_conformity(text: str, language: str, script_mode: str = "native") -> Tuple[bool, Optional[str]]:
    """Verify that generated text conforms to the requested script orthography.

    Args:
        text: Text to evaluate.
        language: Language code (e.g. 'hi', 'hinglish', 'ta', 'te', 'bn').
        script_mode: 'native' | 'romanized' | 'dual'

    Returns:
        (is_conforming, reason)
    """
    if not text or not text.strip():
        return True, None

    lang = (language or "en").lower().strip()
    mode = (script_mode or "native").lower().strip()

    # Look up script specification for target language
    spec = None
    for aliases, target_spec in _SCRIPT_SPECS.items():
        if lang in aliases or any(lang.startswith(a) for a in aliases if len(a) > 2):
            spec = target_spec
            break

    if spec:
        script_name, ranges = spec
        native_count = sum(1 for c in text if any(start <= c <= end for start, end in ranges))

        if mode == "native":
            if native_count == 0:
                return False, f"Expected native {script_name} script for {lang}, but none was found."

            non_ws = sum(1 for c in text if not c.isspace())
            latin_count = sum(1 for c in text if ('a' <= c.lower() <= 'z'))

            # If sample has enough characters, verify native script isn't drowned out by English
            if non_ws >= 30 and (native_count / non_ws < 0.20 or native_count < latin_count * 0.25):
                return False, (
                    f"Expected native {script_name} script for {lang}, but text is dominated by Latin characters "
                    f"({native_count} {script_name} vs {latin_count} Latin chars)."
                )

        elif mode == "romanized":
            if native_count > len(text) * 0.25:
                return False, (
                    f"Expected Romanized (Latin) script for {lang}, but native {script_name} script "
                    f"characters dominated ({native_count} chars)."
                )

    return True, None
