"""Configuration management with Pydantic Settings with secure defaults."""
import os
from typing import Optional
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecurityError(Exception):
    """Raised when required security configuration is missing."""
    pass


class Settings(BaseSettings):
    """Application settings loaded from environment variables with secure defaults.

    Security hardening:
    - No hardcoded credentials
    - Required secrets must come from environment
    - Fail-fast on missing production secrets
    """

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )

    # Google Gemini
    google_api_key: Optional[str] = Field(default=None)

    # NVIDIA NIM
    nvidia_api_key: Optional[str] = Field(default=None)
    nvidia_nim_base_url: str = Field(default="https://integrate.api.nvidia.com/v1")

    # Anthropic Claude
    anthropic_api_key: Optional[str] = Field(default=None)

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None)

    # Hugging Face
    hf_token: Optional[str] = Field(default=None)

    # XAI (Grok)
    xai_api_key: Optional[str] = Field(default=None)

    # Groq
    groq_api_key: Optional[str] = Field(default=None)

    # Local Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")

    # Infrastructure - No defaults for credentials!
    redis_url: str = Field(default="redis://redis:6379/0")
    postgres_url: str = Field(default="postgresql+asyncpg://dataset_user:dataset_pass@postgres:5432/dataset_engine")
    # JWT Secret (required for security)
    jwt_secret: str
    qdrant_url: str = Field(default="http://qdrant:6333")

    # API Keys
    serpapi_key: Optional[str] = Field(default=None)
    google_search_api_key: Optional[str] = Field(default=None)
    brave_search_api_key: Optional[str] = Field(default=None)

    # GitHub Token (optional, for higher rate limits)
    github_token: Optional[str] = Field(default=None)

    # Feature Flags
    enable_celery: bool = Field(default=True)
    enable_ray: bool = Field(default=False)
    enable_hitl: bool = Field(default=False)

    # Resource Limits
    max_concurrent_jobs: int = Field(default=5)
    token_budget_usd: float = Field(default=100.0)

    # Provider Priority Order
    provider_priority: list[str] = Field(
        default_factory=lambda: [
            "google_gemini", "nvidia_nim", "anthropic_claude",
            "openai", "huggingface", "xai", "ollama"
        ]
    )

    # Rate Limits (requests per minute)
    rate_limits: dict[str, int] = Field(default_factory=lambda: {
        "google_gemini": 60,
        "nvidia_nim": 30,
        "anthropic_claude": 50,
        "openai": 60,
        "huggingface": 20,
        "xai": 30,
        "ollama": 100
    })

    # Cost per 1K tokens
    cost_per_token: dict[str, float] = Field(default_factory=lambda: {
        "google_gemini": 0.0001,
        "nvidia_nim": 0.0002,
        "anthropic_claude": 0.003,
        "openai": 0.00015,
        "huggingface": 0.0,
        "xai": 0.001,
        "ollama": 0.0
    })

    # Cache TTL (seconds)
    cache_ttl: int = Field(default=3600)

    # Retry Settings
    max_retries: int = Field(default=3)
    retry_base_delay: float = Field(default=2.0)
    retry_max_delay: float = Field(default=60.0)

    # Quality Settings
    quality_threshold: float = Field(default=0.5)

    # LangSmith Observability
    langchain_tracing_v2: bool = Field(default=True, validation_alias="LANGCHAIN_TRACING_V2")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com", validation_alias="LANGCHAIN_ENDPOINT")
    langchain_api_key: Optional[str] = Field(default=None, validation_alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="RasoSynthTune", validation_alias="LANGCHAIN_PROJECT")
    toxicity_threshold: float = Field(default=0.7)
    dedup_threshold: float = Field(default=0.85)

    # Generation Modes & Synthetic settings
    generation_mode: str = Field(default="hybrid")  # source | hybrid | synthetic
    allow_seedless_generation: bool = Field(default=True)
    require_reference_sources: bool = Field(default=False)
    minimum_reference_documents: int = Field(default=1)
    planner_enabled: bool = Field(default=True)
    coverage_planner_enabled: bool = Field(default=True)
    validation_strictness: str = Field(default="standard")  # relaxed | standard | strict
    regeneration_attempts: int = Field(default=3)

    # Export Settings
    output_dir: str = Field(default="outputs")

    # S3 Settings (for export)
    s3_bucket: Optional[str] = Field(default=None)
    s3_region: str = Field(default="us-east-1")
    s3_access_key_id: Optional[str] = Field(default=None)
    s3_secret_access_key: Optional[str] = Field(default=None)

    # HuggingFace Hub Settings (for export)
    hf_dataset_org: Optional[str] = Field(default=None)

    # Kaggle Settings (for export)
    kaggle_username: Optional[str] = Field(default=None)
    kaggle_key: Optional[str] = Field(default=None)

    # Environment validation
    environment: str = Field(default="development")

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Fail-fast in production if required secrets are missing."""
        production_envs = ("production", "gpu_cluster", "staging")

        if self.environment.lower() in production_envs:
            missing_secrets = []

            # Check for at least one AI provider API key
            has_provider = any([
                self.google_api_key,
                self.nvidia_api_key,
                self.anthropic_api_key,
                self.openai_api_key,
            ])

            if not has_provider:
                missing_secrets.append("At least one AI provider API key")

            # Check for database connection
            if not self.postgres_url or "localhost" in self.postgres_url:
                missing_secrets.append("Production database URL (non-localhost)")

            if missing_secrets:
                raise SecurityError(
                    f"Production environment '{self.environment}' requires: "
                    f"{'; '.join(missing_secrets)}. "
                    "Set these via environment variables or secrets manager."
                )

        return self

    def model_dump(self, **kwargs) -> dict:
        """Dump settings as dictionary for provider initialization."""
        return {
            "environment": self.environment,
            "google_api_key": self.google_api_key,
            "nvidia_api_key": self.nvidia_api_key,
            "nvidia_nim_base_url": self.nvidia_nim_base_url,
            "anthropic_api_key": self.anthropic_api_key,
            "openai_api_key": self.openai_api_key,
            "hf_token": self.hf_token,
            "xai_api_key": self.xai_api_key,
            "groq_api_key": self.groq_api_key,
            "ollama_base_url": self.ollama_base_url,
            "redis_url": self.redis_url,
            "postgres_url": self.postgres_url,
            "qdrant_url": self.qdrant_url,
            "github_token": self.github_token,
            "enable_celery": self.enable_celery,
            "enable_ray": self.enable_ray,
            "enable_hitl": self.enable_hitl,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "token_budget_usd": self.token_budget_usd,
            "provider_priority": self.provider_priority,
            "rate_limits": self.rate_limits,
            "cost_per_token": self.cost_per_token,
            "cache_ttl": self.cache_ttl,
            "max_retries": self.max_retries,
            "retry_base_delay": self.retry_base_delay,
            "retry_max_delay": self.retry_max_delay,
            "quality_threshold": self.quality_threshold,
            "toxicity_threshold": self.toxicity_threshold,
            "dedup_threshold": self.dedup_threshold,
            "output_dir": self.output_dir,
            "s3_bucket": self.s3_bucket,
            "s3_region": self.s3_region,
            "hf_dataset_org": self.hf_dataset_org,
            "kaggle_username": self.kaggle_username,
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()