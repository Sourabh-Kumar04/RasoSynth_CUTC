"""Enhanced API schemas with constraint analysis and advanced features."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Any
from datetime import datetime
from enum import Enum


class DatasetType(str, Enum):
    SFT = "sft"
    RAG = "rag"
    RLHF = "rlhf"
    CLASSIFICATION = "classification"
    CODING = "coding"
    REASONING = "reasoning"
    CONVERSATIONAL = "conversational"
    TOOL_CALLING = "tool_calling"
    MULTIMODAL = "multimodal"
    GRAPH = "graph"
    TRAJECTORY = "trajectory"
    CUSTOM = "custom"


class QualityLevel(str, Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    HIGH = "high"
    RESEARCH = "research"


class LicenseRequirement(str, Enum):
    ANY = "any"
    CC_ONLY = "cc_only"
    PUBLIC_DOMAIN = "public_domain"
    APACHE = "apache"
    MIT = "mit"
    GPL = "gpl"


class ExportFormat(str, Enum):
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"
    HUGGINGFACE = "huggingface"
    S3 = "s3"
    HF_HUB = "hf_hub"
    KAGGLE = "kaggle"
    SQL = "sql"
    QDRANT = "qdrant"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEGOTIATING = "negotiating"


class ConstraintAnalysis(BaseModel):
    """Analysis of data collection constraints."""
    feasibility_score: float = Field(description="Estimated feasibility (0.0-1.0)")
    estimated_sources: int = Field(description="Estimated discoverable sources")
    estimated_samples: int = Field(description="Estimated final samples")
    estimated_cost: float = Field(description="Estimated cost in USD")
    warnings: list[str] = Field(default_factory=list)
    fallback_strategies: list[str] = Field(default_factory=list)
    constraint_conflicts: list[str] = Field(default_factory=list)


class JobRequest(BaseModel):
    target_domain: str = Field(..., min_length=1, description="Target domain for dataset generation")
    dataset_type: DatasetType = Field(default=DatasetType.SFT)

    @field_validator("dataset_type", mode="before")
    @classmethod
    def normalize_dataset_type(cls, v):
        """Accept case-insensitive dataset type values."""
        if isinstance(v, str):
            return v.lower()
        return v
    output_schema: Optional[dict] = Field(default=None, description="Custom output schema")
    dataset_size: int = Field(default=1000, ge=1, le=100000, description="Target number of samples")
    quality_level: QualityLevel = Field(default=QualityLevel.STANDARD)
    language: str = Field(default="en", description="Primary language code")
    secondary_languages: list[str] = Field(default_factory=list, description="Additional languages")
    region_restrictions: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    licensing_requirements: LicenseRequirement = Field(default=LicenseRequirement.ANY)
    toxicity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    dedup_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    preferred_providers: list[str] = Field(default_factory=list)
    cost_budget_usd: float = Field(default=50.0, ge=0.0)
    speed_vs_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    synthetic_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    export_format: ExportFormat = Field(default=ExportFormat.JSONL)
    metadata_fields: list[str] = Field(default_factory=list)
    time_period: Optional[str] = Field(default=None, description="Historical time period (e.g., '2000-2020')")
    enable_research_loop: bool = Field(default=True, description="Enable autonomous research")
    streaming_export: bool = Field(default=False, description="Enable streaming export for large datasets")
    generation_mode: str = Field(default="hybrid", description="Dataset generation mode: source | hybrid | synthetic")
    allow_seedless_generation: bool = Field(default=True)
    require_reference_sources: bool = Field(default=False)
    minimum_reference_documents: int = Field(default=1)
    planner_enabled: bool = Field(default=True)
    coverage_planner_enabled: bool = Field(default=True)
    validation_strictness: str = Field(default="standard")
    regeneration_attempts: int = Field(default=3)


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    progress: float
    cost_usd: float
    samples_generated: int
    current_stage: Optional[str] = None
    constraint_analysis: Optional[ConstraintAnalysis] = None


class JobDetailResponse(JobResponse):
    config: dict
    error: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    sources_discovered: int = 0
    sources_extracted: int = 0
    samples_filtered: int = 0
    warnings: list[str] = []
    adaptation_notes: list[str] = []


class ProviderStatus(BaseModel):
    name: str
    status: Literal["available", "degraded", "unavailable"]
    latency_ms: Optional[float] = None
    cost_per_token: float
    requests_today: int
    tokens_today: int
    cost_today_usd: float
    success_rate: float = 1.0


class ProviderTestRequest(BaseModel):
    provider: str = Field(..., description="Provider name to test")


class ProviderTestResponse(BaseModel):
    provider: str
    success: bool
    latency_ms: float
    error: Optional[str] = None


class ReportResponse(BaseModel):
    quality_metrics: dict
    lineage_report: dict
    bias_analysis: dict
    license_report: dict


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: str


class HealthResponse(BaseModel):
    status: str
    version: str
    providers: dict[str, str]
    database: bool
    redis: bool
    research_loop_status: Optional[str] = None


class ResearchRequest(BaseModel):
    force_refresh: bool = Field(default=False, description="Force research cycle even if not due")


class ResearchResponse(BaseModel):
    techniques_discovered: list[str]
    papers_found: list[dict]
    updates_applied: list[str]
    status: str


class TechniqueInfo(BaseModel):
    category: str
    techniques: list[str]
    benchmarks: list[str]


class AdaptabilityRequest(BaseModel):
    target_domain: str
    constraints: dict


class AdaptabilityResponse(BaseModel):
    recommended_strategies: list[str]
    estimated_feasibility: float
    warnings: list[str]
    fallback_options: list[str]


class SourceResponse(BaseModel):
    url: str
    source_type: str
    title: str
    description: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    language: Optional[str] = None
    confidence: float = 1.0


class SampleResponse(BaseModel):
    instruction: str
    response: str
    input: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    difficulty_tier: int
    quality_score: Optional[float] = None
    warnings: list[str] = []


# =============================================================================
# Checkpoint & Failover Schemas
# =============================================================================

class CheckpointStage(str, Enum):
    """Orchestration stages that can be checkpointed."""
    DISCOVERY = "discovery"
    EXTRACTION = "extraction"
    FILTERING = "filtering"
    CONSTRUCTION = "construction"
    EXPORT = "export"
    COMPLETED = "completed"


class ProviderContextSchema(BaseModel):
    """Provider state at checkpoint time."""
    provider_name: str
    model: str
    api_key_hash: str
    base_url: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    cost_accumulated: float = 0.0


class CheckpointResponse(BaseModel):
    """Response for checkpoint data."""
    checkpoint_id: str
    job_id: str
    stage: CheckpointStage
    progress: float
    sources_discovered: int = 0
    sources_extracted: int = 0
    samples_filtered: int = 0
    samples_generated: int = 0
    provider_context: Optional[ProviderContextSchema] = None
    fallback_provider: Optional[str] = None
    created_at: datetime
    version: int = 1


class CreateCheckpointRequest(BaseModel):
    """Request to create a checkpoint."""
    job_id: str
    stage: CheckpointStage
    progress: float = Field(ge=0.0, le=1.0)
    sources_discovered: int = 0
    sources_extracted: int = 0
    samples_filtered: int = 0
    samples_generated: int = 0
    provider_name: Optional[str] = None
    provider_model: Optional[str] = None
    extracted_content: list[Any] = Field(default_factory=list)
    filtered_samples: list[Any] = Field(default_factory=list)
    constructed_samples: list[Any] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class RestoreCheckpointRequest(BaseModel):
    """Request to restore from checkpoint."""
    job_id: str
    checkpoint_id: Optional[str] = None  # If None, uses latest
    resume_from_stage: Optional[CheckpointStage] = None


class RestoreCheckpointResponse(BaseModel):
    """Response from checkpoint restore."""
    success: bool
    checkpoint: Optional[CheckpointResponse] = None
    resume_from_stage: Optional[str] = None
    progress: float = 0.0
    samples_generated: int = 0
    message: str


class ProviderSwitchRequest(BaseModel):
    """Request to manually switch provider."""
    job_id: str
    new_provider: str
    create_checkpoint: bool = True


class ProviderSwitchResponse(BaseModel):
    """Response from provider switch."""
    success: bool
    from_provider: Optional[str] = None
    to_provider: Optional[str] = None
    checkpoint_id: Optional[str] = None
    message: str


class FailoverRequest(BaseModel):
    """Request to manually trigger failover."""
    job_id: str
    reason: Optional[str] = None


class FailoverResponse(BaseModel):
    """Response from failover operation."""
    success: bool
    from_provider: Optional[str] = None
    to_provider: Optional[str] = None
    failure_type: Optional[str] = None
    checkpoint_id: Optional[str] = None
    message: str


class FailureTypeSchema(str, Enum):
    """Types of failures that trigger failover."""
    RATE_LIMIT = "rate_limit"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTH_FAILURE = "auth_failure"
    PROVIDER_DOWN = "provider_down"
    LATENCY_SPIKE = "latency_spike"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    TIMEOUT = "timeout"
    STREAMING_DISCONNECT = "streaming_disconnect"
    UNKNOWN_ERROR = "unknown_error"


class MigrationRecordResponse(BaseModel):
    """Record of provider migration."""
    migration_id: str
    job_id: str
    from_provider: str
    to_provider: str
    failure_type: Optional[str] = None
    checkpoint_id: Optional[str] = None
    success: bool = True
    timestamp: datetime
    error: Optional[str] = None


class FailoverHistoryResponse(BaseModel):
    """Response for failover history."""
    migrations: list[MigrationRecordResponse]
    total_count: int
    failure_stats: dict[str, dict[str, int]] = Field(default_factory=dict)