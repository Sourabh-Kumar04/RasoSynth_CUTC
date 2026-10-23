"""Structured representation of the user's request."""
from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class UserIntent:
    """The core ML/AI task being requested (e.g. "code_translation", "medical_qa")."""
    primary_task: str

    """The field this task belongs to (e.g. "software_engineering", "diabetes_management")."""
    domain: str

    """Modality of the data: text | image | audio | code | tabular | video | multimodal."""
    modality: str

    """Topics this request is explicitly NOT about (max 15 items, lower‑cased)."""
    anti_domains: List[str]

    """Known benchmarks, dataset names, model names, or formats relevant to this task."""
    key_entities: List[str]

    """6‑10 expert search strings a domain expert would type into Google Scholar,
    Hugging Face, Papers With Code, or Kaggle.
    These are the ONLY queries sent to the discovery stage."""
    specialized_queries: List[str]

    """Explicit constraints extracted from the user's raw input (may be empty)."""
    constraints: List[str]

    """Requested export format: jsonl | csv | parquet | huggingface | sql | qdrant | unknown."""
    output_format: str

    """Confidence of the extraction (0.0‑1.0). Below 0.6 → IntentExtractionError is raised."""
    confidence: float

    """Original user string – kept for logging and error messages."""
    raw_input: str

    """Optional few-shot ideal examples provided by the user to anchor crawling and generation."""
    ideal_samples: List[dict] = field(default_factory=list)

    """Instruction/chat schema format: alpaca | sharegpt | chatml | openai_jsonl."""
    instruction_format: str = "alpaca"

    def model_dump(self) -> dict:
        """Serialize for agents / APIs (Pydantic-compatible name)."""
        return asdict(self)

    @classmethod
    def from_fallback(
        cls,
        raw_input: Optional[str] = None,
        *,
        primary_task: str = "dataset_generation",
        confidence: float = 0.5,
    ) -> "UserIntent":
        """Build a complete UserIntent when LLM extraction fails."""
        raw = (raw_input or "").strip() or "general"
        return cls(
            primary_task=primary_task,
            domain=raw,
            modality="text",
            anti_domains=[],
            key_entities=[raw] if raw != "general" else [],
            specialized_queries=[raw],
            constraints=[],
            output_format="jsonl",
            confidence=confidence,
            raw_input=raw,
        )


class IntentExtractionError(Exception):
    """Raised when the LLM cannot produce a valid, confident intent."""
    pass