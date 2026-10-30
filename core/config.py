"""Configuration management with Pydantic Settings with secure defaults."""
import os
from typing import Optional
from functools import lru_cache

from pydantic import Field, field_validator, model_validator, AliasChoices
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
    google_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("google_api_key", "gemini_api_key", "google_gemini_api_key")
    )

    # NVIDIA NIM
    nvidia_api_key: Optional[str] = Field(default=None)
    nvidia_nim_base_url: str = Field(default="https://integrate.api.nvidia.com/v1")

    # Anthropic Claude
    anthropic_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("anthropic_api_key", "anthropic_claude_api_key")
    )

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None)

    # Hugging Face
    hf_token: Optional[str] = Field(default=None)

    # AIKosh dataset catalogue API (optional; requires an account API key)
    aikosh_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("aikosh_api_key", "ai_kosh_api_key")
    )

    # XAI (Grok)
    xai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("xai_api_key", "grok_api_key")
    )

    # Groq
    groq_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("groq_api_key", "grop_api_key")
    )

    # DeepSeek
    deepseek_api_key: Optional[str] = Field(default=None)

    # OpenRouter
    openrouter_api_key: Optional[str] = Field(default=None)

    # Together AI
    together_api_key: Optional[str] = Field(default=None)

    # Featherless
    featherless_api_key: Optional[str] = Field(default=None)
    featherless_base_url: Optional[str] = Field(default="https://api.featherless.ai/v1")

    # Fireworks AI
    fireworks_api_key: Optional[str] = Field(default=None)
    fireworks_base_url: Optional[str] = Field(default="https://api.fireworks.ai/inference/v1")

    # Local Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")

    # Cloud GPU Serverless Training (Modal, RunPod)
    modal_token_id: Optional[str] = Field(default=None)
    modal_token_secret: Optional[str] = Field(default=None)
    runpod_api_key: Optional[str] = Field(default=None)

    # Infrastructure - No defaults for credentials!
    redis_url: str = Field(default="redis://redis:6379/0")
    postgres_url: str = Field(
        default="",
        validation_alias=AliasChoices("postgres_url", "database_url")
    )

    @field_validator("postgres_url", mode="before")
    @classmethod
    def normalize_postgres_url(cls, v: Optional[str]) -> str:
        if not v:
            return ""
        val = str(v).strip()
        # Automatically upgrade standard connection URIs (e.g. Neon, Supabase) to asyncpg
        if val.startswith("postgres://"):
            val = val.replace("postgres://", "postgresql+asyncpg://", 1)
        elif val.startswith("postgresql://") and not val.startswith("postgresql+asyncpg://"):
            val = val.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg requires ?ssl=... instead of ?sslmode=...
        if "sslmode=" in val:
            val = val.replace("sslmode=", "ssl=")
        return val
    # JWT Secret (required for security)
    jwt_secret: str = Field(default="")  # No default: JWT_SECRET env is required (see validate_production_secrets).
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
    max_job_queue_size: int = Field(default=50, ge=0, le=10000)
    token_budget_usd: float = Field(default=100.0)
    synthesis_concurrency: int = Field(default=8, ge=1, le=32)

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
    generation_mode: str = Field(default="strict_source")  # strict_source | hybrid | synthetic
    allow_seedless_generation: bool = Field(default=False)
    require_reference_sources: bool = Field(default=False)
    minimum_reference_documents: int = Field(default=1)
    planner_enabled: bool = Field(default=True)
    coverage_planner_enabled: bool = Field(default=True)
    validation_strictness: str = Field(default="standard")  # relaxed | standard | strict
    regeneration_attempts: int = Field(default=3)

    # Export Settings
    output_dir: str = Field(default="outputs")

    @field_validator("output_dir", mode="before")
    @classmethod
    def detect_persistent_output_dir(cls, v: Optional[str]) -> str:
        if v and v != "outputs":
            return v
        # Detect Hugging Face Spaces persistent volume mounted at /data
        if os.path.isdir("/data") and os.access("/data", os.W_OK):
            persistent_out = "/data/outputs"
            os.makedirs(persistent_out, exist_ok=True)
            return persistent_out
        return v or "outputs"

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

    # Environment validation (canonical: ENVIRONMENT, alias: AI_DATASET_ENVIRONMENT)
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("environment", "ai_dataset_environment")
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Fail-fast if required secrets are missing.

        The JWT/postgres checks below fire in EVERY environment, not only in
        production: there is no safe default for these values, so an unset or
        known-public-default value is a configuration error anywhere.
        """
        # Unconditional: a JWT secret must be configured (AuthManager also
        # enforces >=32 chars and rejects weak patterns at auth time).
        if not self.jwt_secret:
            raise SecurityError(
                "JWT_SECRET is required. Set a cryptographically random 32+ character "
                "value via the JWT_SECRET environment variable."
            )
        if len(self.jwt_secret) < 32:
            raise SecurityError("JWT_SECRET must be at least 32 characters.")
        if "rasosynthtune-sovereign" in self.jwt_secret.lower():
            raise SecurityError(
                "JWT_SECRET uses the removed public default value. Set a unique secret."
            )
        # Unconditional: the old public postgres credentials must never reappear,
        # whether from a default or from the environment.
        pg = self.postgres_url or ""
        if "dataset_user" in pg and "dataset_pass" in pg:
            raise SecurityError(
                "postgres_url uses the removed public default credentials. "
                "Set POSTGRES_URL with real credentials."
            )

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
        return super().model_dump(**kwargs)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
