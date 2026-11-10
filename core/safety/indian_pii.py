"""
Statutory Indian PII Redactor & De-Identification Engine.

Implements high-precision detection and pseudonymous masking for:
- Aadhaar Numbers (12-digit UID with Verhoeff dihedral D5 checksum verification)
- Permanent Account Numbers (PAN cards, statutory 10-char format)
- Goods and Services Tax Identification Numbers (GSTIN, 15-char format)
- Indian Mobile Numbers (+91 / 10 digits starting with 6-9)
- Bank IFSC Codes (RBI 11-char statutory standard)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# Verhoeff algorithm lookup tables for UIDAI Aadhaar checksum validation
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def validate_verhoeff(number_str: str) -> bool:
    """Validate 12-digit string checksum using Verhoeff Dihedral D5 algorithm."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) != 12:
        return False
    c = 0
    reversed_digits = digits[::-1]
    for i, item in enumerate(reversed_digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][item]]
    return c == 0


@dataclass
class PIIMatch:
    category: str
    original: str
    redacted: str
    start: int
    end: int


@dataclass
class RedactionResult:
    clean_text: str
    matches_found: List[PIIMatch] = field(default_factory=list)
    has_pii: bool = False


class IndianPIIRedactor:
    """Detects and masks sensitive Indian identifiers."""

    # Statutory regex patterns
    PAN_REGEX = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
    GSTIN_REGEX = re.compile(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b")
    MOBILE_REGEX = re.compile(r"\b(?:\+91[\-\s]?)?([6-9]\d{9})\b")
    IFSC_REGEX = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
    AADHAAR_CANDIDATE = re.compile(r"\b([2-9][0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4})\b")

    def redact(self, text: str) -> RedactionResult:
        """Scan text and replace PII with pseudonymous tokens."""
        if not text:
            return RedactionResult(clean_text="", has_pii=False)

        matches: List[PIIMatch] = []
        clean = text

        # 1. Aadhaar (Verhoeff checksum checked)
        for m in list(self.AADHAAR_CANDIDATE.finditer(clean)):
            raw_val = m.group(1)
            digits_only = re.sub(r"[\s\-]", "", raw_val)
            if validate_verhoeff(digits_only):
                token = "[AADHAAR_REDACTED]"
                clean = clean.replace(raw_val, token)
                matches.append(PIIMatch("aadhaar", raw_val, token, m.start(), m.end()))

        # 1. GSTIN (Process before PAN since 15-char GSTIN embeds 10-char PAN)
        for m in list(self.GSTIN_REGEX.finditer(clean)):
            val = m.group(1)
            token = "[GSTIN_REDACTED]"
            clean = clean.replace(val, token)
            matches.append(PIIMatch("gstin", val, token, m.start(), m.end()))

        # 2. PAN Card
        for m in list(self.PAN_REGEX.finditer(clean)):
            val = m.group(1)
            token = "[PAN_REDACTED]"
            clean = clean.replace(val, token)
            matches.append(PIIMatch("pan", val, token, m.start(), m.end()))

        # 4. Bank IFSC
        for m in list(self.IFSC_REGEX.finditer(clean)):
            val = m.group(1)
            token = "[IFSC_REDACTED]"
            clean = clean.replace(val, token)
            matches.append(PIIMatch("ifsc", val, token, m.start(), m.end()))

        # 5. Mobile Number
        for m in list(self.MOBILE_REGEX.finditer(clean)):
            val = m.group(0)
            token = "[PHONE_REDACTED]"
            clean = clean.replace(val, token)
            matches.append(PIIMatch("mobile", val, token, m.start(), m.end()))

        return RedactionResult(
            clean_text=clean,
            matches_found=matches,
            has_pii=len(matches) > 0,
        )
