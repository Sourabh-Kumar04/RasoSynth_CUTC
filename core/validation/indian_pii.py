"""Indian PII detection, masking, and synthetic replacement.

Covers:
- Aadhaar Numbers (12 digits, often formatted as 4-4-4)
- Permanent Account Numbers (PAN: 5 uppercase letters, 4 digits, 1 uppercase letter)
- Goods and Services Tax Identification Number (GSTIN: 15 alphanumeric characters)
- Unified Payments Interface (UPI IDs: user@bank)
- Indian Mobile Numbers (+91 or 0 prefix followed by 10 digits starting with 6-9)
- Indian Vehicle Registration Numbers (e.g., DL-01-AB-1234 or MH12DE1432)

BOUNDARY: detection here is a PATTERN SCREEN, not a compliance
determination under the DPDP Act or any other statute, and a pattern match
is not proof that an identifier is real. Checksum/structural validation is
available separately via :func:`validate_indian_pii` (Verhoeff for Aadhaar,
holder-category structure for PAN, mod-36 check digit for GSTIN). The UPI
handle list is a list of COMMON PSP handles, not an exhaustive registry:
an unknown handle is simply not detected. Synthetic replacements are
bracketed tokens that detectors do not re-match, by design, so masked
output re-scans clean.
"""

import re
from typing import Dict, List, Tuple

# Regex patterns for Indian statutory and personal identifiers
_AADHAAR_PATTERN = re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b")
_PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_GSTIN_PATTERN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b", re.IGNORECASE)
# Common PSP/bank UPI handles (not exhaustive — new PSPs are not detected).
_UPI_HANDLES = (
    "okhdfcbank", "okbizaxis", "okbaroda", "okpunjab", "okcanara", "okkotak",
    "okaxis", "okicici", "oksbi",
    "axisbank", "barodampay", "hdfcbank", "icici", "sbi",
    "kotak", "indus", "ybl", "paytm", "apl", "upi",
)
_UPI_PATTERN = re.compile(r"\b[a-zA-Z0-9.\-_]{2,256}@(" + "|".join(_UPI_HANDLES) + r")\b", re.IGNORECASE)
# Bounded mobile matching: (?<!\d) / (?!\d) prevent matching a substring of
# a longer digit run (the old pattern had no leading boundary at all).
_INDIAN_MOBILE_PATTERN = re.compile(r"(?<!\d)(?:(?:\+91|91|0)[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)")
_VEHICLE_NO_PATTERN = re.compile(r"\b[A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,3}[ -]?[0-9]{4}\b", re.IGNORECASE)


# --- Checksum / structural validation -------------------------------------

# Verhoeff tables (standard) for Aadhaar check-digit validation.
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
    [8, 0, 1, 3, 2, 4, 9, 6, 7, 5],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

# PAN 4th character: holder category (P individual, C company, H HUF,
# F firm, A AOP, T trust, B body of individuals, L local authority,
# J artificial juridical person, G government).
_PAN_CATEGORIES = set("PCHFTABLGJ")

_GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def aadhaar_verhoeff_valid(aadhaar: str) -> bool:
    """Return True if a 12-digit Aadhaar passes the Verhoeff checksum.

    Digits are processed left to right with permutation index i % 8
    (i = 0 at the leftmost digit) — the standard Verhoeff convention.
    """
    digits = re.sub(r"[ -]", "", aadhaar or "")
    if len(digits) != 12 or not digits.isdigit():
        return False
    c = 0
    for i, ch in enumerate(digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def aadhaar_check_digit(first_11_digits: str) -> str:
    """Compute the Verhoeff check digit for the first 11 Aadhaar digits.

    The check digit sits at position 11 (permutation row 11 % 8 = 3): it is
    the digit x with D[c][P[3][x]] == 0, where c is the state after the
    first 11 digits. Both D rows and P rows are permutations, so x is
    unique. (The classic example holds: check digit of "236" is "3".)
    """
    if len(first_11_digits) != 11 or not first_11_digits.isdigit():
        raise ValueError("first_11_digits must be 11 digits")
    c = 0
    for i, ch in enumerate(first_11_digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    target_column = _VERHOEFF_D[c].index(0)
    return str(_VERHOEFF_P[11 % 8].index(target_column))


def pan_structurally_valid(pan: str) -> bool:
    """Return True if a PAN matches the format AND its 4th letter is a known holder category."""
    value = (pan or "").upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value):
        return False
    return value[3] in _PAN_CATEGORIES


def gstin_check_digit(first_14_chars: str) -> str:
    """Compute the GSTIN mod-36 check digit for the first 14 characters.

    Luhn-mod-36 over the base-36 values of the characters (0-9, A-Z),
    alternating factor 2/1 from the left, summing base-36 digits of each
    product. NOTE: this implements the published mod-36 scheme; no
    independently verified real GSTIN was available in-repo to cross-check
    the variant against, so treat GSTIN checksum results as scheme-checked,
    not authority-verified.
    """
    value = (first_14_chars or "").upper()
    if len(value) != 14 or any(ch not in _GSTIN_ALPHABET for ch in value):
        raise ValueError("first_14_chars must be 14 GSTIN alphabet characters")
    total = 0
    for i, ch in enumerate(value):
        code = _GSTIN_ALPHABET.index(ch)
        product = code * (2 if i % 2 == 0 else 1)
        total += product // 36 + product % 36
    check = (36 - (total % 36)) % 36
    return _GSTIN_ALPHABET[check]


def gstin_checksum_valid(gstin: str) -> bool:
    """Return True if a 15-character GSTIN's last character matches its mod-36 check digit."""
    value = (gstin or "").upper()
    if len(value) != 15:
        return False
    try:
        return gstin_check_digit(value[:14]) == value[14]
    except ValueError:
        return False


def validate_indian_pii(text: str) -> Dict[str, List[Dict[str, object]]]:
    """Pattern-detect Indian PII and annotate each hit with validation results.

    ``structurally_valid`` / ``checksum_valid`` are False for hits that only
    match the pattern (e.g. the illustrative PAN "ABCDE1234F", whose 4th
    letter is not a holder category). Types with no checksum scheme report
    ``checksum_valid`` as None. Detection itself still uses
    :func:`detect_indian_pii` (pattern recall is preserved); this function
    adds the validation layer on top.
    """
    if not text:
        return {}
    detected = detect_indian_pii(text)
    out: Dict[str, List[Dict[str, object]]] = {}
    for kind, values in detected.items():
        entries = []
        for value in values:
            if kind == "aadhaar":
                entries.append({"value": value, "structurally_valid": True, "checksum_valid": aadhaar_verhoeff_valid(value)})
            elif kind == "pan":
                entries.append({"value": value, "structurally_valid": pan_structurally_valid(value), "checksum_valid": None})
            elif kind == "gstin":
                entries.append({"value": value, "structurally_valid": True, "checksum_valid": gstin_checksum_valid(value)})
            else:
                entries.append({"value": value, "structurally_valid": None, "checksum_valid": None})
        out[kind] = entries
    return out


def detect_indian_pii(text: str) -> Dict[str, List[str]]:
    """Scan text and return dictionary of identified Indian PII entities.

    Pattern screen only: a hit means the text matches the identifier's
    shape, not that the identifier is real or valid. Use
    :func:`validate_indian_pii` for checksum/structural validation.
    """
    if not text:
        return {}

    found: Dict[str, List[str]] = {}

    aadhaar = _AADHAAR_PATTERN.findall(text)
    if aadhaar:
        found["aadhaar"] = aadhaar

    pan = _PAN_PATTERN.findall(text)
    if pan:
        found["pan"] = pan

    gstin = _GSTIN_PATTERN.findall(text)
    if gstin:
        found["gstin"] = gstin

    # finditer (not findall): the pattern has a capture group for the handle,
    # and findall would return only the handle instead of the full UPI id.
    upi = [m.group(0) for m in _UPI_PATTERN.finditer(text)]
    if upi:
        found["upi"] = upi

    mobile = _INDIAN_MOBILE_PATTERN.findall(text)
    if mobile:
        found["mobile"] = mobile

    vehicle = _VEHICLE_NO_PATTERN.findall(text)
    if vehicle:
        found["vehicle"] = vehicle

    return found


def mask_indian_pii(text: str, replacement_mode: str = "redact") -> str:
    """
    Mask or synthetically replace Indian statutory and personal identifiers.

    Modes:
      - 'redact': Replaces with clean tokens like [AADHAAR_REDACTED], [PAN_REDACTED].
      - 'synthetic': Replaces with bracketed synthetic tokens (e.g.
        [SYNTHETIC_PAN]) that detectors do NOT re-match, so masked output
        re-scans clean. Realistic-looking dummy numbers are deliberately
        NOT used: they would re-match the detectors and be indistinguishable
        from real identifiers.
    """
    if not text:
        return text

    masked = text

    if replacement_mode == "synthetic":
        masked = _AADHAAR_PATTERN.sub("XXXX-XXXX-0000", masked)
        masked = _PAN_PATTERN.sub("[SYNTHETIC_PAN]", masked)
        masked = _GSTIN_PATTERN.sub("[SYNTHETIC_GSTIN]", masked)
        masked = _UPI_PATTERN.sub("[SYNTHETIC_UPI]", masked)
        masked = _INDIAN_MOBILE_PATTERN.sub("[SYNTHETIC_MOBILE]", masked)
        masked = _VEHICLE_NO_PATTERN.sub("[SYNTHETIC_VEHICLE]", masked)
    else:
        masked = _AADHAAR_PATTERN.sub("[AADHAAR_REDACTED]", masked)
        masked = _PAN_PATTERN.sub("[PAN_REDACTED]", masked)
        masked = _GSTIN_PATTERN.sub("[GSTIN_REDACTED]", masked)
        masked = _UPI_PATTERN.sub("[UPI_REDACTED]", masked)
        masked = _INDIAN_MOBILE_PATTERN.sub("[PHONE_REDACTED]", masked)
        masked = _VEHICLE_NO_PATTERN.sub("[VEHICLE_REDACTED]", masked)

    return masked
