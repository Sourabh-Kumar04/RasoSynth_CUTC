"""Tokenizer Fertility and Token Efficiency Metrics.

Empirical tokenizer fertility metrics (tokens-per-word) and efficiency estimates
across popular foundation model tokenizer families (Llama-3, Gemma-2, Sarvam-Indic,
Mistral, Qwen-2.5) for multilingual and Indic text.

NOTE: The fertility values below are estimated and unsourced heuristics (no published
corpus or empirical benchmark run date is cited). Consumers should treat these ratios as
indicative guidelines rather than precise ground-truth tokenizer measurements.
"""

from typing import Any, Dict, Optional


# Estimated/unsourced fertility table: tokens per word across language, script, and model architecture
_FERTILITY_INDEX: Dict[str, Dict[str, Dict[str, float]]] = {
    "en": {
        "all": {
            "llama3": 1.25,
            "gemma2": 1.22,
            "sarvam_indic": 1.24,
            "mistral": 1.25,
            "qwen25": 1.23,
        }
    },
    "hi": {
        "native": {
            "llama3": 3.65,
            "gemma2": 1.42,
            "sarvam_indic": 1.28,
            "mistral": 3.80,
            "qwen25": 1.35,
        },
        "romanized": {
            "llama3": 1.55,
            "gemma2": 1.45,
            "sarvam_indic": 1.35,
            "mistral": 1.58,
            "qwen25": 1.40,
        },
        "dual": {
            "llama3": 2.60,
            "gemma2": 1.43,
            "sarvam_indic": 1.31,
            "mistral": 2.69,
            "qwen25": 1.37,
        },
    },
    "hinglish": {
        "all": {
            "llama3": 1.55,
            "gemma2": 1.45,
            "sarvam_indic": 1.32,
            "mistral": 1.58,
            "qwen25": 1.40,
        }
    },
    "indic_multilingual": {
        "native": {
            "llama3": 4.10,
            "gemma2": 1.58,
            "sarvam_indic": 1.34,
            "mistral": 4.25,
            "qwen25": 1.45,
        },
        "romanized": {
            "llama3": 1.60,
            "gemma2": 1.48,
            "sarvam_indic": 1.36,
            "mistral": 1.62,
            "qwen25": 1.42,
        },
        "dual": {
            "llama3": 2.85,
            "gemma2": 1.53,
            "sarvam_indic": 1.35,
            "mistral": 2.93,
            "qwen25": 1.43,
        },
    },
    "ta": {
        "native": {"llama3": 4.35, "gemma2": 1.62, "sarvam_indic": 1.35, "mistral": 4.50, "qwen25": 1.48},
        "romanized": {"llama3": 1.62, "gemma2": 1.49, "sarvam_indic": 1.37, "mistral": 1.65, "qwen25": 1.43},
    },
    "te": {
        "native": {"llama3": 4.25, "gemma2": 1.60, "sarvam_indic": 1.35, "mistral": 4.40, "qwen25": 1.46},
        "romanized": {"llama3": 1.60, "gemma2": 1.48, "sarvam_indic": 1.36, "mistral": 1.63, "qwen25": 1.42},
    },
    "bn": {
        "native": {"llama3": 3.85, "gemma2": 1.48, "sarvam_indic": 1.30, "mistral": 4.00, "qwen25": 1.40},
        "romanized": {"llama3": 1.58, "gemma2": 1.46, "sarvam_indic": 1.35, "mistral": 1.60, "qwen25": 1.41},
    },
    "mr": {
        "native": {"llama3": 3.70, "gemma2": 1.44, "sarvam_indic": 1.29, "mistral": 3.85, "qwen25": 1.36},
        "romanized": {"llama3": 1.56, "gemma2": 1.45, "sarvam_indic": 1.35, "mistral": 1.59, "qwen25": 1.40},
    },
}


def estimate_tokenizer_fertility(language: str, script_mode: str = "native") -> Dict[str, Any]:
    """Calculate token fertility multipliers and optimal foundation models.

    Args:
        language: Language code (e.g. 'en', 'hi', 'hinglish', 'ta').
        script_mode: 'native' | 'romanized' | 'dual'

    Returns:
        Dict with fertility rates per model, recommended model, savings percentage,
        and explicit source/unsupported language markers.
    """
    lang = (language or "en").lower().strip()
    mode = (script_mode or "native").lower().strip()

    is_unsupported = lang not in _FERTILITY_INDEX
    lang_data = _FERTILITY_INDEX.get(lang, _FERTILITY_INDEX["en"])
    model_fertilities = lang_data.get(mode) or lang_data.get("all") or next(iter(lang_data.values()))

    # Find the most token-efficient tokenizer architecture
    best_model = min(model_fertilities.items(), key=lambda x: x[1])
    worst_model = max(model_fertilities.items(), key=lambda x: x[1])

    savings_vs_worst = 0.0
    if worst_model[1] > 0:
        savings_vs_worst = round((1.0 - (best_model[1] / worst_model[1])) * 100, 1)

    result: Dict[str, Any] = {
        "language": lang,
        "script_mode": mode,
        "source": None,
        "source_status": "estimated_unsourced",
        "fertility_tokens_per_word": model_fertilities,
        "optimal_model": best_model[0],
        "optimal_fertility": best_model[1],
        "reference_llama3_fertility": model_fertilities.get("llama3", 1.25),
        "potential_token_savings_pct": savings_vs_worst,
        "summary": (
            f"{best_model[0].replace('_', ' ').title()} is most token-efficient "
            f"({best_model[1]} tok/word, saving ~{savings_vs_worst}% tokens vs {worst_model[0]})."
        ),
    }

    if is_unsupported:
        result["unsupported_language"] = True
        result["language_fallback_marker"] = "unsupported_language_english_fertilities_shown"
        result["note"] = f"Language '{lang}' is unsupported. English fertilities shown as placeholder; not empirical for '{lang}'."

    return result
