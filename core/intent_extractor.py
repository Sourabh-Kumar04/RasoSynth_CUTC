"""Extract a structured UserIntent from raw user text using the LLM."""
import hashlib
import json
import logging
import os
import re
from typing import List, Optional, Any

from core.intent import IntentExtractionError, UserIntent
from core.provider_router import ProviderRouter, TaskType

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = float(os.getenv("INTENT_MIN_CONFIDENCE", "0.6"))
_MAX_QUERY_LEN = int(os.getenv("INTENT_MAX_QUERY_LEN", "200"))
_MAX_ANTI_DOMAINS = int(os.getenv("INTENT_MAX_ANTI_DOMAINS", "15"))
_CACHE_TTL = int(os.getenv("INTENT_CACHE_TTL", "3600"))
_FALLBACK_ON_ERROR = os.getenv("INTENT_FALLBACK_ON_ERROR", "false").lower() == "true"

_REQUIRED_FIELDS = {
    "primary_task", "domain", "modality", "anti_domains",
    "key_entities", "specialized_queries", "constraints",
    "output_format", "confidence"
}

INTENT_SYSTEM_PROMPT = """
You are an expert ML/AI dataset researcher. Your job is to understand exactly
what kind of dataset a user needs and output a precise structured description
of their intent.

Output ONLY a valid JSON object. No explanation. No markdown fences. No preamble.
Just the raw JSON.

Required fields:
{
  "primary_task": "the core ML/AI task being requested",
  "domain": "the field this task belongs to",
  "modality": "one of: text | image | audio | code | tabular | video | multimodal",
  "anti_domains": ["topics this request is NOT about — max 15 items"],
  "key_entities": ["known benchmarks, datasets, or model names relevant to this task"],
  "specialized_queries": ["6-10 expert search queries to find this dataset online"],
  "constraints": ["explicit constraints from the user's input, or empty list"],
  "output_format": "one of: jsonl | csv | parquet | huggingface | sql | qdrant | unknown",
  "confidence": 0.85
}

Rules for specialized_queries:
- Write queries a domain expert would type into Google Scholar, Hugging Face,
  Papers With Code, or Kaggle
- Include specific benchmark names, language pairs, task variants, known corpora
- Do NOT use generic suffixes like "dataset training data examples"
- Each query must be under 200 characters
- No duplicates
Good example for "speech recognition dataset":
  ["LibriSpeech ASR corpus", "Common Voice Mozilla dataset",
   "TED-LIUM benchmark speech", "VoxPopuli multilingual ASR",
   "AISHELL Mandarin speech corpus", "WER evaluation speech benchmark"]
Good example for "code translation Python to C dataset":
  ["CodeNet parallel corpus Python C", "AVATAR code translation benchmark",
   "MultiPL-E Python C translation pairs", "TransCoder evaluation dataset",
   "HumanEval-X Python C pairs", "code migration Python C parallel corpus"]

Rules for anti_domains:
- These must be topics that share vocabulary with this request but are
  completely unrelated fields
- Lower-case all items
- Max 15 items
Good example for "sentiment analysis":
  ["financial market sentiment index", "chemistry analysis", "geological survey"]
Good example for "image segmentation":
  ["market segmentation", "customer segmentation", "geographic boundary"]

Set confidence below 0.6 only if the request is too vague to generate reliable
specialized queries (e.g., a single ambiguous word with no context).
"""


async def extract_intent(
    raw_input: str,
    provider_router: ProviderRouter,
    redis_client: Optional[Any] = None,
) -> UserIntent:
    """
    Call the LLM to extract structured intent from raw user input.
    Robustly handles formatting errors, low confidence, and truncations by falling back gracefully.
    Never returns None.
    """
    cache_key = f"intent:{hashlib.sha256(raw_input.strip().lower().encode()).hexdigest()}"

    # --- Cache read ---
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.info(f"Intent cache hit for input: '{raw_input[:60]}...'")
                data = json.loads(cached)
                return UserIntent(**data, raw_input=raw_input)
        except Exception as cache_err:
            logger.warning(f"Redis read failed (non-fatal): {cache_err}")

    # --- LLM call ---
    try:
        response_obj = await provider_router.route(
            task=TaskType.TEXT_GENERATION,
            prompt=f'User request: "{raw_input}"',
            system_prompt=INTENT_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=1024,  # Increased to prevent JSON truncation
        )
    except Exception as llm_err:
        if not _FALLBACK_ON_ERROR:
            raise IntentExtractionError(
                f"LLM call failed during intent extraction: {llm_err}")
        logger.warning(f"LLM call failed during intent extraction: {llm_err}. Using fallback intent.")
        response_obj = None

    if response_obj is None:
        if not _FALLBACK_ON_ERROR:
            raise IntentExtractionError("All providers failed to respond")
        # Fall back to raw input search immediately
        return UserIntent(
            primary_task="unknown",
            domain="unknown",
            modality="text",
            anti_domains=[],
            key_entities=[],
            specialized_queries=[raw_input.strip()],
            constraints=[],
            output_format="unknown",
            confidence=_MIN_CONFIDENCE,
            raw_input=raw_input,
        )

    response_text = response_obj.content

    # --- Parse ---
    clean = response_text.strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        clean = clean[start:end+1]
    else:
        clean = clean.lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as parse_err:
        if not _FALLBACK_ON_ERROR:
            raise IntentExtractionError(
                f"LLM returned non-JSON response for intent extraction: {parse_err}\n"
                f"Raw response: {response_text[:300]}"
            ) from parse_err
        logger.warning(
            f"LLM returned non-JSON response: {parse_err}. Falling back to raw input query.\n"
            f"Raw response: {response_text[:300]}"
        )
        data = {
            "primary_task": "unknown",
            "domain": "unknown",
            "modality": "text",
            "anti_domains": [],
            "key_entities": [],
            "specialized_queries": [raw_input.strip()],
            "constraints": [],
            "output_format": "unknown",
            "confidence": _MIN_CONFIDENCE
        }

    # --- Validate required fields ---
    missing = _REQUIRED_FIELDS - data.keys()
    if missing:
        if not _FALLBACK_ON_ERROR:
            raise IntentExtractionError(
                f"Intent JSON missing required fields: {missing}"
            )
        logger.warning(f"Intent JSON missing required fields: {missing}. Filling in defaults.")
        for field in missing:
            if field in ("anti_domains", "key_entities", "specialized_queries", "constraints"):
                data[field] = []
            elif field == "confidence":
                data[field] = _MIN_CONFIDENCE
            else:
                data[field] = "unknown"

        if not data.get("specialized_queries"):
            data["specialized_queries"] = [raw_input.strip()]

    # --- Validate confidence ---
    if float(data["confidence"]) < _MIN_CONFIDENCE:
        if not _FALLBACK_ON_ERROR:
            raise IntentExtractionError(
                f"Low confidence ({data['confidence']}) for input: '{raw_input}' — "
                f"request may be too vague. Please provide more detail."
            )
        logger.warning(
            f"Low confidence ({data['confidence']}) for input: '{raw_input}' — "
            "Falling back to basic intent query extraction using raw input."
        )
        fallback_queries = list(dict.fromkeys([q.strip() for q in data.get("specialized_queries", []) if q.strip()]))
        if not fallback_queries:
            fallback_queries = [raw_input.strip()]
        data["confidence"] = _MIN_CONFIDENCE
        data["specialized_queries"] = fallback_queries

    # --- Post-process: clean up lists ---
    anti_domains = [a.lower().strip() for a in data.get("anti_domains", [])][:_MAX_ANTI_DOMAINS]
    anti_domains = list(dict.fromkeys(anti_domains))  # deduplicate, preserve order

    queries = [q.strip() for q in data.get("specialized_queries", []) if q.strip()]
    if _FALLBACK_ON_ERROR:
        queries = [q[:_MAX_QUERY_LEN].strip() for q in queries]  # Truncate cleanly
    else:
        queries = [q for q in queries if len(q) <= _MAX_QUERY_LEN]  # Discard as per default test expectations
    queries = list(dict.fromkeys(queries))  # deduplicate
    # Remove any query that contains an anti-domain term (self-sabotage guard)
    queries = [
        q for q in queries
        if not any(anti in q.lower() for anti in anti_domains)
    ]
    if not queries:
        if not _FALLBACK_ON_ERROR:
            raise IntentExtractionError(
                f"No valid specialized queries after validation for input: '{raw_input}'"
            )
        queries = [raw_input.strip()]

    intent = UserIntent(
        primary_task=data["primary_task"].strip(),
        domain=data["domain"].strip(),
        modality=data["modality"].strip(),
        anti_domains=anti_domains,
        key_entities=[e.strip() for e in data.get("key_entities", [])],
        specialized_queries=queries,
        constraints=[c.strip() for c in data.get("constraints", [])],
        output_format=data.get("output_format", "unknown").strip(),
        confidence=float(data["confidence"]),
        raw_input=raw_input,
    )

    logger.info(
        f"Intent extracted | task='{intent.primary_task}' | domain='{intent.domain}' | "
        f"modality='{intent.modality}' | queries={len(intent.specialized_queries)} | "
        f"anti_domains={intent.anti_domains} | confidence={intent.confidence}"
    )

    # --- Cache write ---
    if redis_client:
        try:
            payload = {k: v for k, v in intent.__dict__.items() if k != "raw_input"}
            await redis_client.setex(cache_key, _CACHE_TTL, json.dumps(payload))
        except Exception as cache_err:
            logger.warning(f"Redis write failed (non-fatal): {cache_err}")

    return intent