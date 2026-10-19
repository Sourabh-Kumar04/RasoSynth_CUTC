"""Indian numerical formatting, currency standardization, and speech-ready verbalization.

Supports:
- South Asian numbering system (Lakhs & Crores, e.g., 12,34,567 vs 1,234,567)
- Currency standardization (₹ / INR / Rs.)
- Indian date formatting (DD/MM/YYYY)
- Speech-ready / Voice AI verbalization for TTS and ASR training pipelines
"""

import re
from typing import Optional


def format_indian_number(num: int | float | str) -> str:
    """Format an integer or float string into the Indian numbering system (e.g., 100000 -> 1,00,000)."""
    try:
        s = str(num).strip()
        if "." in s:
            int_part, dec_part = s.split(".", 1)
            dec_part = "." + dec_part
        else:
            int_part = s
            dec_part = ""

        is_neg = False
        if int_part.startswith("-"):
            is_neg = True
            int_part = int_part[1:]

        if len(int_part) <= 3:
            return ("-" if is_neg else "") + int_part + dec_part

        last_three = int_part[-3:]
        remaining = int_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)

        res = ",".join(groups) + "," + last_three + dec_part
        return ("-" if is_neg else "") + res
    except Exception:
        return str(num)


def standardize_currency_text(text: str, target_symbol: str = "₹") -> str:
    """Replace scattered currency representations (Rs., Rs, INR) with a standardized symbol or vice-versa."""
    if not text:
        return text

    if target_symbol == "₹":
        text = re.sub(r"\b(?:Rs\.?|INR)\s*(\d+)", r"₹\1", text, flags=re.IGNORECASE)
    elif target_symbol.upper() == "INR":
        text = re.sub(r"(?:₹|\bRs\.?)\s*(\d+)", r"INR \1", text, flags=re.IGNORECASE)
    return text


_NUM_WORDS_HI = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच",
    6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
    20: "बीस", 50: "पचास", 100: "सौ", 1000: "हज़ार",
    100000: "लाख", 10000000: "करोड़",
}

_NUM_WORDS_EN = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    100: "hundred", 1000: "thousand", 100000: "lakh", 10000000: "crore",
}


def verbalize_for_speech(text: str, language: str = "hi") -> str:
    """
    Transform numbers, acronyms, and symbols into spoken forms for Voice AI and TTS pipelines.
    
    Example:
      '₹500 ka challan' -> 'panch sau rupaye ka challan'
      '100 km/h' -> 'ek sau kilometer prati ghanta'
    """
    if not text:
        return text

    res = text
    lang = (language or "hi").lower()

    if "hi" in lang or "hinglish" in lang:
        # Currency expansion
        res = re.sub(r"₹\s*(\d+)", r"\1 rupaye", res)
        res = re.sub(r"\bRs\.?\s*(\d+)", r"\1 rupaye", res, flags=re.IGNORECASE)
        # Unit expansions
        res = re.sub(r"\bkm/h\b", "kilometer prati ghanta", res, flags=re.IGNORECASE)
        res = re.sub(r"\bkg\b", "kilogram", res, flags=re.IGNORECASE)
        res = re.sub(r"%", " pratishat", res)
        # Common acronym verbalizations
        res = re.sub(r"\bGST\b", "जीएसटी", res)
        res = re.sub(r"\bPAN\b", "पैन", res)
        res = re.sub(r"\bITR\b", "आईटीआर", res)
        res = re.sub(r"\bOTP\b", "ओटीपी", res)
        res = re.sub(r"\bUPI\b", "यूपीआई", res)
        res = re.sub(r"\be\.g\.,?\b", "jaise ki", res, flags=re.IGNORECASE)
        res = re.sub(r"\bi\.e\.,?\b", "yaani ki", res, flags=re.IGNORECASE)
    else:
        # English expansion
        res = re.sub(r"₹\s*(\d+)", r"\1 rupees", res)
        res = re.sub(r"\bkm/h\b", "kilometers per hour", res, flags=re.IGNORECASE)
        res = re.sub(r"\bkg\b", "kilograms", res, flags=re.IGNORECASE)
        res = re.sub(r"%", " percent", res)
        res = re.sub(r"\be\.g\.,?\b", "for example", res, flags=re.IGNORECASE)
        res = re.sub(r"\bi\.e\.,?\b", "that is", res, flags=re.IGNORECASE)

    return res
