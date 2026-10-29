"""Cryptographic Data Bill of Materials (DBOM) & Provenance Attestor.

Generates Merkle-tree SHA-256 provenance records over dataset samples and
renders them as Data Nutrition Labels. This is integrity provenance ONLY:
it does not certify compliance with the EU AI Act, India DPDP Act 2023,
ISO 42001, or any other regulation, and no label may claim otherwise.
Compliance fields are fail-closed: anything not explicitly measured and
passed in is reported as "not verified" / "not measured", never defaulted
to certified, clean, or 0%.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def compute_sample_hash(sample: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 leaf hash for a dataset record."""
    canonical = {
        "instruction": str(sample.get("instruction", "")).strip(),
        "response": str(sample.get("response", "")).strip(),
        "input": str(sample.get("input", "")).strip() if sample.get("input") else "",
    }
    dumped = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def compute_merkle_root(leaf_hashes: List[str]) -> str:
    """Compute Merkle Tree root hash from list of leaf SHA-256 hashes."""
    if not leaf_hashes:
        return hashlib.sha256(b"empty_dataset").hexdigest()

    current_level = leaf_hashes.copy()
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            combined = hashlib.sha256(f"{left}:{right}".encode("utf-8")).hexdigest()
            next_level.append(combined)
        current_level = next_level

    return current_level[0]


def generate_dbom_attestation(
    dataset_name: str,
    samples: List[Dict[str, Any]],
    domain: Optional[str] = None,
    language: str = "en",
    license_type: str = "Apache-2.0",
    compliance_flags: Optional[Dict[str, Any]] = None,
    synthesis_mode: Optional[str] = "standard",
) -> Dict[str, Any]:
    """Generate tamper-evident cryptographic DBOM certificate for a dataset."""
    leaf_hashes = [compute_sample_hash(s) for s in samples]
    merkle_root = compute_merkle_root(leaf_hashes)

    flags = compliance_flags or {}
    now_iso = datetime.now(timezone.utc).isoformat()

    pii_masked = flags.get("pii_masked")
    if pii_masked is None:
        try:
            from core.validation.indian_pii import detect_indian_pii
            found_pii = False
            for s in samples:
                full_text = f"{s.get('instruction', '')} {s.get('input', '')} {s.get('response', '')}"
                detected = detect_indian_pii(full_text)
                if any(len(matches) > 0 for matches in detected.values()):
                    found_pii = True
                    break
            pii_masked = not found_pii
        except Exception:
            # Fail closed: a detector error means "unknown", never "clean".
            pii_masked = None

    certificate_id = f"DBOM-{merkle_root[:12].upper()}"

    dbom = {
        "dbom_version": "1.0.0",
        "certificate_id": certificate_id,
        "dataset_name": dataset_name,
        "domain": domain or "general",
        "language": language,
        "synthesis_mode": synthesis_mode or "standard",
        "total_samples": len(samples),
        "issued_at": now_iso,
        "merkle_root_hash": merkle_root,
        "compliance_audit": {
            # Fail closed: unmeasured fields are None (rendered as
            # "not verified" / "not measured"), never certified-by-default.
            "pii_masked": pii_masked,
            "cultural_safety_certified": flags.get("cultural_safety_certified"),
            "benchmark_contamination_rate_pct": flags.get("contamination_rate_pct"),
            "diversity_entropy": flags.get("diversity_entropy"),
            "statutory_compliance_act": flags.get("statutory_compliance_act"),
        },
        "provenance": {
            "engine": "RasoSynthTune 2.0.0 Enterprise",
            "synthesis_mode": synthesis_mode or "standard",
            "license": license_type,
            "synthetic_pipeline": "deterministic_seedless_coverage",
            "tamper_verification_algorithm": "SHA-256 Merkle Tree",
        },
    }
    return dbom


def verify_dataset_dbom(
    samples: List[Dict[str, Any]],
    dbom_certificate: Dict[str, Any],
) -> Dict[str, Any]:
    """Verify integrity and tamper resistance of dataset against its DBOM certificate."""
    expected_root = dbom_certificate.get("merkle_root_hash")
    if not expected_root:
        return {
            "is_valid": False,
            "reason": "Missing 'merkle_root_hash' in DBOM certificate.",
            "computed_root": "",
        }

    leaf_hashes = [compute_sample_hash(s) for s in samples]
    computed_root = compute_merkle_root(leaf_hashes)

    is_valid = computed_root == expected_root

    return {
        "is_valid": is_valid,
        "certificate_id": dbom_certificate.get("certificate_id"),
        "expected_root": expected_root,
        "computed_root": computed_root,
        "total_samples_verified": len(samples),
        "status": "cryptographically_verified" if is_valid else "tampering_or_mismatch_detected",
    }


def generate_nutrition_label_markdown(dbom: Dict[str, Any]) -> str:
    """Format DBOM certificate into a clean, GitHub-flavored Data Nutrition Label."""
    audit = dbom.get("compliance_audit", {})
    prov = dbom.get("provenance", {})

    return f"""# 🥗 Data Nutrition & Provenance Label (DBOM)

> **Certificate ID**: `{dbom.get('certificate_id')}`  
> **Merkle Root Hash**: `{dbom.get('merkle_root_hash')}`  
> **Issued At**: `{dbom.get('issued_at')}`  
> **Status**: Cryptographically Sealed (Merkle root recorded; re-verify against the samples to confirm)

---

### 📊 Dataset Demographics
| Attribute | Specification |
|:---|:---|
| **Dataset Name** | {dbom.get('dataset_name')} |
| **Domain** | {dbom.get('domain')} |
| **Synthesis Mode** | `{dbom.get('synthesis_mode', 'standard')}` |
| **Primary Language** | {dbom.get('language')} |
| **Total Samples** | {dbom.get('total_samples'):,} records |
| **License** | {prov.get('license', 'Apache-2.0')} |
| **Pipeline Engine** | {prov.get('engine')} |

---

### Compliance & Safety (unverified unless explicitly measured)
| Security Check | Status | Standard / Regulation |
|:---|:---:|:---|
| **PII Scrubbing** | {'Verified Clean' if audit.get('pii_masked') is True else 'Flagged' if audit.get('pii_masked') is False else 'Not verified'} | Indian IT Act 2000 & Aadhaar Masking (claimed framework only) |
| **Indic Cultural Safety** | {'Certified Safe' if audit.get('cultural_safety_certified') is True else 'Flagged' if audit.get('cultural_safety_certified') is False else 'Not verified'} | Hate Speech & Communal Sensitivity Guardrails (claimed framework only) |
| **Contamination Leakage** | {f"{audit.get('benchmark_contamination_rate_pct')}%" if audit.get('benchmark_contamination_rate_pct') is not None else 'Not measured'} | Canary spot-check only - not a leakage guarantee |
| **Topic Representation Entropy** | {audit.get('diversity_entropy') if audit.get('diversity_entropy') is not None else 'Not measured'} | Shannon Multi-Cluster Coverage |
| **Statutory Compliance** | Not verified | {audit.get('statutory_compliance_act') or 'No framework claimed'} |

---
*Generated autonomously by RasoSynthTune Cryptographic DBOM Attestor.*
"""
