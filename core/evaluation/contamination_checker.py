"""Benchmark canary spot-check (NOT a leakage audit).

Compares samples against a small hand-written list of canary phrases
associated with MMLU, IndicGLUE, GSM8K, and ARC. It does NOT check the
benchmark test sets themselves, so a "clean" result is NOT a guarantee of
zero test leakage — it only means none of these canary phrases matched.
Every report carries method="canary_spot_check" and this scope note.
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple


# Known benchmark canary strings and distinctive n-grams from standard evaluation sets
BENCHMARK_SIGNATURES: Dict[str, List[str]] = {
    "mmlu_hindi": [
        "pratham vishva yuddha kab shuru hua tha",
        "bharat ka samvidhan kis varsh lagu hua tha",
        "prakash sanshleshan mein kaun si gas mukta hoti hai",
        "kendra sarkar ka mukhya kanooni salahkar kaun hota hai",
    ],
    "gsm8k": [
        "natalia sold clips to 48 of her friends in april",
        "weng earns $12 an hour for babysitting yesterday she worked 50 minutes",
        "betty is saving money for a new wallet which costs $100",
        "james writes a 3-page letter to 2 different friends twice a week",
    ],
    "indicglue": [
        "kya yeh vakya doosre vakya ka anukaran karta hai",
        "nirdharit kijiye ki kathan satya hai ya asatya",
        "diye gaye gadyansh ke aadhar par prashna ka uttar dejiye",
    ],
    "arc_challenge": [
        "which property is a characteristic of all minerals",
        "which statement best describes how a plant responds to light",
        "which of the following is an example of an inherited trait in a human",
    ],
}


def _get_ngrams(text: str, n: int = 8) -> Set[str]:
    """Extract character or word n-grams from normalized text."""
    words = re.findall(r"\w+", text.lower())
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def check_dataset_contamination(
    samples: List[Dict[str, Any]],
    benchmarks: Optional[List[str]] = None,
    ngram_size: int = 8,
    similarity_threshold: float = 0.50,
) -> Dict[str, Any]:
    """
    Spot-check dataset samples against hand-written benchmark canary phrases
    (NOT the benchmark test sets — see module docstring).

    Args:
        samples: List of dataset sample records (dict with 'instruction', 'response')
        benchmarks: List of benchmark names to check against (defaults to all supported)
        ngram_size: Word n-gram length for matching (1 to 8, default 8)
        similarity_threshold: Overlap threshold with any canary phrase to flag as contaminated.

    Returns:
        Audit report containing summary statistics, contaminated items, and verification hash.
    """
    if ngram_size < 1 or ngram_size > 8:
        raise ValueError(f"ngram_size must be between 1 and 8, got {ngram_size}")

    targets = benchmarks or list(BENCHMARK_SIGNATURES.keys())
    # Pre-extract n-grams per individual canary phrase
    active_canary_phrases: Dict[str, List[Set[str]]] = {}
    for b in targets:
        if b in BENCHMARK_SIGNATURES:
            active_canary_phrases[b] = [
                _get_ngrams(text, ngram_size) for text in BENCHMARK_SIGNATURES[b]
            ]

    contaminated_records = []
    clean_samples = []

    content_hasher = hashlib.sha256()

    for idx, sample in enumerate(samples):
        inst = str(sample.get("instruction", "") or sample.get("prompt", ""))
        resp = str(sample.get("response", "") or sample.get("completion", ""))
        full_text = f"{inst} {resp}".lower()
        sample_ngrams = _get_ngrams(full_text, ngram_size)

        content_hasher.update(full_text.encode("utf-8"))

        matched_benchmarks = []
        for b_name, phrase_sets in active_canary_phrases.items():
            if not sample_ngrams:
                continue
            for phrase_ngrams in phrase_sets:
                if not phrase_ngrams:
                    continue
                intersection = sample_ngrams & phrase_ngrams
                if intersection:
                    overlap_ratio = len(intersection) / len(phrase_ngrams)
                    # Apply documented similarity_threshold strictly without bypass rule
                    if overlap_ratio >= similarity_threshold:
                        matched_benchmarks.append({
                            "benchmark": b_name,
                            "overlap_score": round(overlap_ratio, 3),
                            "matched_ngrams": list(intersection)[:3],
                        })
                        break  # Found match for this benchmark

        if matched_benchmarks:
            contaminated_records.append({
                "sample_index": idx,
                "instruction": inst[:120] + "..." if len(inst) > 120 else inst,
                "matches": matched_benchmarks,
            })
        else:
            clean_samples.append(sample)

    total_count = len(samples)
    contam_count = len(contaminated_records)
    contamination_rate = round((contam_count / max(total_count, 1)) * 100, 2)

    # Cryptographic certificate hash of audit result incorporating actual content
    audit_hash = content_hasher.hexdigest()[:16]

    return {
        "method": "canary_spot_check",
        "scope_note": "Hand-written canary phrases only; a clean result is not a leakage guarantee.",
        "status": "clean" if contam_count == 0 else "contamination_detected",
        "total_samples_audited": total_count,
        "clean_samples_count": len(clean_samples),
        "contaminated_samples_count": contam_count,
        "contamination_rate_pct": contamination_rate,
        "benchmarks_checked": targets,
        "audit_certificate_id": f"CONTAM-AUDIT-{audit_hash}",
        "contaminated_records": contaminated_records,
    }
