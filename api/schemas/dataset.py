"""
Dataset Schemas

Schemas for dataset configuration, generation requests,
quality constraints, and metadata management.
"""

from typing import Dict, List, Optional, Any, Set, Union, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, computed_field, model_validator
from api.schemas.base import BaseSchema, Constraint, ConstraintType, SemanticRequest


class DataModality(str, Enum):
    """Supported data modalities."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    PDF = "pdf"
    TABLE = "table"
    CODE = "code"
    GRAPH = "graph"
    MULTIMODAL = "multimodal"
    REASONING_TRACE = "reasoning_trace"
    TOOL_CALL = "tool_call"
    SCIENTIFIC_SYMBOLIC = "scientific_symbolic"


class DatasetFormat(str, Enum):
    """Export format for datasets."""
    JSONL = "jsonl"
    JSON = "json"
    PARQUET = "parquet"
    CSV = "csv"
    ARROW = "arrow"
    HF_DATASET = "hf_dataset"
    TF_RECORD = "tf_record"


class QualityLevel(str, Enum):
    """Quality level for datasets."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    HIGH = "high"
    PREMIUM = "premium"
    RESEARCH = "research"


class DatasetType(str, Enum):
    """Type of dataset generation."""
    SYNTHETIC = "synthetic"
    FILTERED = "filtered"
    AUGMENTED = "augmented"
    EXTRACTED = "extracted"
    HYBRID = "hybrid"
    MULTIMODAL = "multimodal"
    REASONING = "reasoning"
    TOOL_USAGE = "tool_usage"


class QualityConstraints(BaseModel):
    """Quality constraint specifications."""
    min_quality_score: float = 0.7
    max_toxicity_score: float = 0.05
    min_diversity_score: float = 0.6

    min_length_chars: Optional[int] = None
    max_length_chars: Optional[int] = None

    min_tokens: Optional[int] = None
    max_tokens: Optional[int] = None

    require_annotations: bool = False
    annotation_types: List[str] = Field(default_factory=list)

    validate_schema: bool = True
    validate_consistency: bool = True

    deduplication_enabled: bool = True
    deduplication_threshold: float = 0.95

    filtering_enabled: bool = True
    filter_outliers: bool = True
    outlier_threshold: float = 3.0

    human_review_required: bool = False
    human_review_sample_size: Optional[int] = None


class DataConstraints(BaseModel):
    """Data size and schema constraints."""
    min_samples: int = 100
    max_samples: int = 1000000

    min_size_mb: Optional[float] = None
    max_size_mb: Optional[float] = None

    data_schema: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    required_fields: List[str] = Field(default_factory=list)
    optional_fields: List[str] = Field(default_factory=list)

    schema_strict: bool = False

    field_types: Dict[str, str] = Field(default_factory=dict)

    @field_validator("min_samples", "max_samples")
    @classmethod
    def validate_sample_counts(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Sample count must be positive")
        return v

    @model_validator(mode="after")
    def validate_size_constraints(self) -> "DataConstraints":
        if self.min_size_mb and self.max_size_mb:
            if self.min_size_mb > self.max_size_mb:
                raise ValueError("min_size_mb cannot exceed max_size_mb")
        if self.min_samples > self.max_samples:
            raise ValueError("min_samples cannot exceed max_samples")
        return self


class SyntheticDataConfig(BaseModel):
    """Configuration for synthetic data generation."""
    generation_ratio: float = 0.5
    augmentation_ratio: float = 0.3
    real_data_ratio: float = 0.2

    allowed_synthetic_sources: List[str] = Field(default_factory=lambda: [
        "llm_generated", "augmented", "transformed"
    ])

    disallowed_synthetic_sources: List[str] = Field(default_factory=lambda: [
        "web_scraped", "copyrighted"
    ])

    preserve_real_data_ratio: bool = True
    allow_copyrighted_augmentation: bool = False

    temperature_range: tuple[float, float] = (0.7, 1.2)
    top_p_range: tuple[float, float] = (0.9, 1.0)

    seed: Optional[int] = None
    deterministic: bool = False

    diversity_enforcement: bool = True
    diversity_penalty: float = 0.1


class DatasetMetadata(BaseSchema):
    """Dataset metadata information."""
    name: str
    description: Optional[str] = None

    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    domain: str
    task_type: str
    language: str = "en"

    modality: List[DataModality] = Field(default_factory=list)
    format: DatasetFormat = DatasetFormat.JSONL

    sample_count: int = 0
    size_bytes: int = 0

    quality_level: QualityLevel = QualityLevel.STANDARD
    dataset_type: DatasetType = DatasetType.SYNTHETIC

    tags: List[str] = Field(default_factory=list)
    license: Optional[str] = None

    source_urls: List[str] = Field(default_factory=list)
    citation: Optional[str] = None

    lineage: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    statistics: Dict[str, Any] = Field(default_factory=dict)
    schema_definition: Dict[str, Any] = Field(default_factory=dict)


class DatasetConfig(BaseSchema):
    """Complete dataset configuration."""
    name: str
    description: str = ""

    dataset_type: DatasetType = DatasetType.SYNTHETIC
    modality: List[DataModality] = Field(default_factory=list)

    data_constraints: DataConstraints = Field(default_factory=DataConstraints)
    quality_constraints: QualityConstraints = Field(default_factory=QualityConstraints)
    synthetic_config: Optional[SyntheticDataConfig] = None

    domain: str = "general"
    language: str = "en"
    task_type: str = "general"

    output_format: DatasetFormat = DatasetFormat.JSONL
    output_path: Optional[str] = None

    compression_enabled: bool = True
    chunk_size_mb: int = 100

    versioning_enabled: bool = True
    versioning_format: str = "v{major}.{minor}.{patch}"

    anonymization_enabled: bool = False
    anonymization_level: Literal["none", "basic", "full"] = "basic"

    def get_constraints(self) -> List[Constraint]:
        """Extract all constraints from configuration."""
        constraints = []

        constraints.append(Constraint(
            type=ConstraintType.DATA_SIZE,
            value=self.data_constraints.min_samples,
            description="Minimum sample count"
        ))

        constraints.append(Constraint(
            type=ConstraintType.DATA_SIZE,
            value=self.data_constraints.max_samples,
            description="Maximum sample count"
        ))

        for modality in self.modality:
            constraints.append(Constraint(
                type=ConstraintType.DATA_MODALITY,
                value=modality.value,
                description="Required modality"
            ))

        constraints.append(Constraint(
            type=ConstraintType.QUALITY_ACCURACY,
            value=self.quality_constraints.min_quality_score,
            description="Minimum quality score"
        ))

        if self.synthetic_config:
            constraints.append(Constraint(
                type=ConstraintType.SYNTHETIC_RATIO,
                value=self.synthetic_config.generation_ratio,
                description="Synthetic data ratio"
            ))

        return constraints


class DatasetGenerationRequest(BaseSchema):
    """Request for dataset generation."""
    config: DatasetConfig

    priority: Literal["low", "normal", "high", "urgent"] = "normal"

    workflow_id: Optional[str] = None
    parent_job_id: Optional[str] = None

    callback_url: Optional[str] = None
    webhook_events: List[str] = Field(default_factory=lambda: ["complete", "failed"])

    execution_strategy: Optional[Literal["auto", "sequential", "parallel", "distributed"]] = None

    max_cost_usd: Optional[float] = None
    max_duration_seconds: Optional[int] = None

    resume_from_checkpoint: bool = False
    checkpoint_id: Optional[str] = None

    validation_level: Literal["basic", "strict", "comprehensive"] = "strict"

    enable_monitoring: bool = True
    monitoring_interval_seconds: int = 60

    @field_validator("max_cost_usd")
    @classmethod
    def validate_max_cost(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("max_cost_usd must be positive")
        return v

    def get_semantic_context(self) -> SemanticRequest:
        """Get semantic context for constraint analysis."""
        semantic = SemanticRequest(
            raw_request=f"Generate {self.config.dataset_type.value} dataset: {self.config.description}",
            constraints=self.config.get_constraints(),
            inferred_context={
                "domain": self.config.domain,
                "modality": [m.value for m in self.config.modality],
                "quality_level": self.config.quality_level.value,
                "task_type": self.config.task_type
            }
        )

        if self.semantic_context:
            semantic.intent = self.semantic_context.intent or semantic.raw_request
            semantic.ambiguity_score = self.semantic_context.ambiguity_score

        return semantic


class DatasetExportRequest(BaseSchema):
    """Request to export a dataset."""
    dataset_id: str
    format: DatasetFormat = DatasetFormat.JSONL

    compression: bool = True
    include_metadata: bool = True
    include_lineage: bool = True

    sample_limit: Optional[int] = None
    shuffle: bool = False
    seed: Optional[int] = None

    output_path: Optional[str] = None


class DatasetFilter(BaseSchema):
    """Filter criteria for dataset queries."""
    domain: Optional[List[str]] = None
    modality: Optional[List[DataModality]] = None
    dataset_type: Optional[List[DatasetType]] = None
    quality_level: Optional[List[QualityLevel]] = None

    min_samples: Optional[int] = None
    max_samples: Optional[int] = None

    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    tags: Optional[List[str]] = None
    exclude_tags: Optional[List[str]] = None

    license_type: Optional[List[str]] = None

    search_query: Optional[str] = None

    sort_by: str = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"

    page: int = 1
    page_size: int = 20