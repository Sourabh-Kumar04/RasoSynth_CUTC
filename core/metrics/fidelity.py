"""Cross-lingual semantic fidelity and quality scoring.

Implements chrF++ (character n-gram F-score with word 2-grams) and lexical semantic retention,
the gold standard for morphologically rich and Indic machine translation and synthetic text evaluation.
"""

from collections import Counter
import re
from typing import Dict, List, Tuple


def _extract_char_ngrams(s: str, n: int) -> Counter:
    """Extract character n-grams from a token sequence."""
    ngrams = Counter()
    for i in range(len(s) - n + 1):
        ngrams[s[i:i + n]] += 1
    return ngrams


def _extract_word_ngrams(tokens: List[str], n: int) -> Counter:
    """Extract word n-grams from a list of tokens."""
    ngrams = Counter()
    for i in range(len(tokens) - n + 1):
        ngrams[tuple(tokens[i:i + n])] += 1
    return ngrams


def compute_chrf_score(
    hypothesis: str,
    reference: str,
    char_order: int = 6,
    word_order: int = 2,
    beta: float = 2.0,
) -> float:
    """
    Compute chrF++ score between a generated hypothesis and a reference translation.
    
    Returns a score between 0.0 and 100.0.
    """
    if not hypothesis or not reference:
        return 0.0

    hyp_clean = hypothesis.strip()
    ref_clean = reference.strip()

    if hyp_clean.lower() == ref_clean.lower():
        return 100.0

    # Character n-grams
    char_precisions = []
    char_recalls = []

    for n in range(1, char_order + 1):
        hyp_ngrams = _extract_char_ngrams(hyp_clean, n)
        ref_ngrams = _extract_char_ngrams(ref_clean, n)

        total_hyp = sum(hyp_ngrams.values())
        total_ref = sum(ref_ngrams.values())

        if total_hyp == 0 or total_ref == 0:
            continue

        overlap = sum((hyp_ngrams & ref_ngrams).values())
        char_precisions.append(overlap / total_hyp)
        char_recalls.append(overlap / total_ref)

    # Word n-grams
    hyp_words = re.findall(r"\w+", hyp_clean.lower())
    ref_words = re.findall(r"\w+", ref_clean.lower())

    for n in range(1, word_order + 1):
        hyp_w_ngrams = _extract_word_ngrams(hyp_words, n)
        ref_w_ngrams = _extract_word_ngrams(ref_words, n)

        total_hyp_w = sum(hyp_w_ngrams.values())
        total_ref_w = sum(ref_w_ngrams.values())

        if total_hyp_w == 0 or total_ref_w == 0:
            continue

        overlap_w = sum((hyp_w_ngrams & ref_w_ngrams).values())
        char_precisions.append(overlap_w / total_hyp_w)
        char_recalls.append(overlap_w / total_ref_w)

    if not char_precisions or not char_recalls:
        return 0.0

    avg_precision = sum(char_precisions) / len(char_precisions)
    avg_recall = sum(char_recalls) / len(char_recalls)

    if avg_precision + avg_recall == 0:
        return 0.0

    # F-beta score (beta=2 places higher weight on recall)
    b2 = beta ** 2
    f_score = ((1 + b2) * avg_precision * avg_recall) / ((b2 * avg_precision) + avg_recall)
    return round(f_score * 100.0, 2)


def evaluate_fidelity(
    original_text: str,
    back_translated_text: str,
    threshold: float = 40.0,
) -> Dict[str, object]:
    """
    Evaluate semantic fidelity of back-translation or parallel pair.

    Returns:
        Dict with chrf_score, is_faithful (bool), and confidence rating.
    """
    score = compute_chrf_score(back_translated_text, original_text)
    is_faithful = score >= threshold

    rating = "high" if score >= 70.0 else "moderate" if score >= 45.0 else "low"

    return {
        "chrf_score": score,
        "is_faithful": is_faithful,
        "quality_tier": rating,
    }
