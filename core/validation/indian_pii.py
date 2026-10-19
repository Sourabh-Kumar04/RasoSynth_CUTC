"""Indian PII detection, masking, and synthetic replacement under DPDP Act compliance.

Covers:
- Aadhaar Numbers (12 digits, often formatted as 4-4-4)
- Permanent Account Numbers (PAN: 5 uppercase letters, 4 digits, 1 uppercase letter)
- Goods and Services Tax Identification Number (GSTIN: 15 alphanumeric characters)
- Unified Payments Interface (UPI IDs: user@bank)
- Indian Mobile Numbers (+91 or 0 prefix followed by 10 digits starting with 6-9)
- Indian Vehicle Registration Numbers (e.g., DL-01-AB-1234 or MH12DE1432)
"""

import re
from typing import Dict, List, Tuple

# Regex patterns for Indian statutory and personal identifiers
_AADHAAR_PATTERN = re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b")
_PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_GSTIN_PATTERN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b", re.IGNORECASE)
_UPI_PATTERN = re.compile(r"\b[a-zA-Z0-9.\-_]{2,256}@(okaxis|okhdfcbank|okicici|oksbi|paytm|ybl|apl|upi)\b", re.IGNORECASE)
_INDIAN_MOBILE_PATTERN = re.compile(r"(?:(?:\+91|91|0)[ -]?)?[6-9]\d{4}[ -]?\d{5}\b")
_VEHICLE_NO_PATTERN = re.compile(r"\b[A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,3}[ -]?[0-9]{4}\b", re.IGNORECASE)


def detect_indian_pii(text: str) -> Dict[str, List[str]]:
    """Scan text and return dictionary of identified Indian PII entities."""
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

    upi = _UPI_PATTERN.findall(text)
    if upi:
        found["upi"] = [u if isinstance(u, str) else u[0] for u in upi]

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
      - 'synthetic': Replaces with compliant dummy placeholders (e.g. 98200XXXXX).
    """
    if not text:
        return text

    masked = text

    if replacement_mode == "synthetic":
        masked = _AADHAAR_PATTERN.sub("XXXX-XXXX-0000", masked)
        masked = _PAN_PATTERN.sub("ABCDE1234F", masked)
        masked = _GSTIN_PATTERN.sub("27ABCDE1234F1Z5", masked)
        masked = _UPI_PATTERN.sub("user@okhdfcbank", masked)
        masked = _INDIAN_MOBILE_PATTERN.sub("+91 98000 00000", masked)
        masked = _VEHICLE_NO_PATTERN.sub("DL-01-AB-0000", masked)
    else:
        masked = _AADHAAR_PATTERN.sub("[AADHAAR_REDACTED]", masked)
        masked = _PAN_PATTERN.sub("[PAN_REDACTED]", masked)
        masked = _GSTIN_PATTERN.sub("[GSTIN_REDACTED]", masked)
        masked = _UPI_PATTERN.sub("[UPI_REDACTED]", masked)
        masked = _INDIAN_MOBILE_PATTERN.sub("[PHONE_REDACTED]", masked)
        masked = _VEHICLE_NO_PATTERN.sub("[VEHICLE_REDACTED]", masked)

    return masked
