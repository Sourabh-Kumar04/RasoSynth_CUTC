"""
Unified LLM Abstraction Layer - Core Interfaces

This module defines the standardized contracts that all LLM providers must implement.
The architecture ensures:
- Provider agnostic business logic
- Easy addition of new providers
- Centralized capability routing
- Consistent error handling
- Unified monitoring
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional
from enum import Enum
from datetime import datetime
import asyncio
import time
from typing import Protocol


# =============================================================================
# Core Data Structures
# =============================================================================

class TaskType(Enum):
    """Standardized task types for intelligent routing."""
    # Text generation tasks
    TEXT_GENERATION = "text_generation"
    SUMMARIZATION = "summarization"
    PARAPHRASING = "paraphrasing"
    TRANSLATION = "translation"

    # Reasoning tasks
    REASONING = "reasoning"
    CODE_GENERATION = "code_generation"
    MATHEMATICAL = "mathematical"
    ANALYSIS = "analysis"

    # Quality & validation
    QUALITY_CHECK = "quality_check"
    HALLUCINATION_DETECTION = "hallucination_detection"
    TOXICITY_CHECK = "toxicity_check"
    FACT_CHECK = "fact_check"

    # Embedding & retrieval
    EMBEDDING = "embedding"
    SEMANTIC_SEARCH = "semantic_search"
    RERANKING = "reranking"

    # Multimodal
    MULTIMODAL = "multimodal"
    VISION = "vision"
    IMAGE_CAPTIONING = "image_captioning"
    MULTIMODAL_REASONING = "multimodal_reasoning"

    # Tool & structured output
    TOOL_CALLING = "tool_calling"
    FUNCTION_CALLING = "function_calling"
    STRUCTURED_OUTPUT = "structured_output"

    # Synthetic & augmentation
    SYNTHETIC_GENERATION = "synthetic_generation"
    AUGMENTATION = "augmentation"
    DATA_GENERATION = "data_generation"

    # Specialized
    OCR_CORRECTION = "ocr_correction"
    ENTITY_EXTRACTION = "entity_extraction"
    SCHEMA_INFERENCE = "schema_inference"
    NORMALIZATION = "normalization"

    # Orchestration
    ORCHESTRATION = "orchestration"
    ROUTING = "routing"


class Modality(Enum):
    """Content modalities supported by models."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    CODE = "code"


class ProviderCapability(Enum):
    """Capabilities that providers can have."""
    TEXT_GENERATION = "text_generation"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    LONG_CONTEXT = "long_context"
    REASONING = "reasoning"
    CODE = "code"
    MULTILINGUAL = "multilingual"
    FUNCTION_CALLING = "function_calling"
    FAST_INFERENCE = "fast_inference"


@dataclass
class ModelMetadata:
    """Metadata for a specific model."""
    model_id: str
    provider: str
    display_name: str
    description: str = ""

    # Capabilities
    modalities: list[Modality] = field(default_factory=list)
    max_tokens: int = 4096
    context_window: int = 8192
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_structured_output: bool = False

    # Performance characteristics
    avg_latency_ms: float = 1000.0
    throughput_tps: float = 10.0
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0

    # Quality characteristics
    reasoning_quality: float = 0.5  # 0.0-1.0
    coding_quality: float = 0.5
    multilingual_quality: float = 0.5

    # Task suitability scores (0.0-1.0)
    task_scores: dict[str, float] = field(default_factory=dict)

    # Technical details
    supports_batching: bool = False
    supports_vision: bool = False
    training_cutoff: str = ""

    # Status
    is_available: bool = True
    is_deprecated: bool = False
    deprecation_warning: str = ""


@dataclass
class LLMRequest:
    """Standardized internal request structure."""
    # Core content
    task_type: TaskType = TaskType.TEXT_GENERATION
    input: str | list[dict] = ""
    system_prompt: str = ""

    # Configuration
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    stop_sequences: list[str] = field(default_factory=list)

    # Modality
    modalities: list[Modality] = field(default_factory=lambda: [Modality.TEXT])

    # Tools & structured output
    tools: list[dict] = field(default_factory=list)
    output_schema: dict | None = None

    # Routing hints
    preferred_provider: str | None = None
    preferred_model: str | None = None
    excluded_providers: list[str] = field(default_factory=list)

    # Constraints
    max_latency_ms: float = 30000.0
    max_cost_usd: float = 1.0
    require_reasoning: bool = False
    require_multimodal: bool = False

    # Metadata
    request_id: str = ""
    parent_request_id: str | None = None
    metadata: dict = field(default_factory=dict)

    # Context
    context_window: int | None = None
    conversation_history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.request_id:
            import uuid
            self.request_id = str(uuid.uuid4())


@dataclass
class TokenUsage:
    """Token usage breakdown."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def input_cost(self) -> float:
        return self.prompt_tokens / 1000

    @property
    def output_cost(self) -> float:
        return self.completion_tokens / 1000


@dataclass
class LLMResponse:
    """Standardized internal response structure."""
    # Content
    content: str = ""
    structured_output: dict | None = None

    # Attribution
    provider: str = ""
    model: str = ""

    # Performance
    latency_ms: float = 0.0
    tokens_used: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)

    # Quality
    confidence: float = 1.0
    finish_reason: str = ""

    # Reasoning trace (if applicable)
    reasoning_trace: str | None = None
    reasoning_steps: list[str] = field(default_factory=list)

    # Metadata
    request_id: str = ""
    cached: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Provider-specific metadata
    raw_response: Any = None
    provider_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "confidence": self.confidence,
            "cached": self.cached,
        }


@dataclass
class StreamChunk:
    """Streaming response chunk."""
    content: str
    delta: str = ""
    index: int = 0
    is_complete: bool = False
    tokens_so_far: int = 0


@dataclass
class ProviderHealth:
    """Health status of a provider."""
    provider: str
    is_healthy: bool
    success_rate: float = 1.0
    avg_latency_ms: float = 0.0
    rate_limit_remaining: int = 0
    last_error: str | None = None
    last_check: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Provider Plugin Interface
# =============================================================================

class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.

    Implement this interface to add a new provider. The framework handles:
    - Authentication
    - Rate limiting
    - Retry logic
    - Error normalization
    - Response standardization
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        pass

    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Initialize the provider with configuration."""
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check provider health status."""
        pass

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the given request."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        request: LLMRequest
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response."""
        pass

    @abstractmethod
    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Generate embeddings for text."""
        pass

    @abstractmethod
    def list_models(self) -> list[ModelMetadata]:
        """List all available models for this provider."""
        pass

    @abstractmethod
    def get_model(self, model_id: str) -> ModelMetadata | None:
        """Get metadata for a specific model."""
        pass

    @abstractmethod
    async def validate_config(self, config: dict) -> bool:
        """Validate provider configuration."""
        pass

    def get_capabilities(self) -> list[ProviderCapability]:
        """Return provider capabilities."""
        return [ProviderCapability.TEXT_GENERATION]

    async def cleanup(self) -> None:
        """Cleanup resources."""
        pass


# =============================================================================
# Provider Registry
# =============================================================================

class ProviderRegistry:
    """
    Central registry for all LLM providers.

    Handles:
    - Provider registration
    - Model catalog
    - Capability lookup
    - Health monitoring
    """

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._models: dict[str, ModelMetadata] = {}
        self._health: dict[str, ProviderHealth] = {}
        self._init_lock = asyncio.Lock()

    def register(self, provider: LLMProvider) -> None:
        """Register a provider and its models."""
        self._providers[provider.provider_id] = provider

        # Register models
        for model in provider.list_models():
            self._models[f"{provider.provider_id}/{model.model_id}"] = model

        # Initialize health
        self._health[provider.provider_id] = ProviderHealth(
            provider=provider.provider_id,
            is_healthy=False
        )

    def unregister(self, provider_id: str) -> None:
        """Unregister a provider."""
        if provider_id in self._providers:
            del self._providers[provider_id]

        # Remove models
        to_remove = [k for k in self._models if k.startswith(f"{provider_id}/")]
        for k in to_remove:
            del self._models[k]

    def get(self, provider_id: str) -> LLMProvider | None:
        """Get a provider by ID."""
        return self._providers.get(provider_id)

    def list_providers(self) -> list[str]:
        """List all registered provider IDs."""
        return list(self._providers.keys())

    def list_models(
        self,
        provider_id: str | None = None,
        modality: Modality | None = None,
        task: TaskType | None = None
    ) -> list[ModelMetadata]:
        """List models with optional filtering."""
        models = list(self._models.values())

        if provider_id:
            models = [m for m in models if m.provider == provider_id]

        if modality:
            models = [m for m in models if modality in m.modalities]

        if task:
            models = sorted(
                models,
                key=lambda m: m.task_scores.get(task.value, 0.5),
                reverse=True
            )

        return models

    def get_model(self, provider: str, model_id: str) -> ModelMetadata | None:
        """Get a specific model."""
        return self._models.get(f"{provider}/{model_id}")

    def find_best_model(
        self,
        task: TaskType,
        modalities: list[Modality] | None = None,
        max_cost: float | None = None,
        max_latency: float | None = None,
        require_reasoning: bool = False
    ) -> ModelMetadata | None:
        """Find the best model for a task based on criteria."""
        candidates = self.list_models(task=task)

        if modalities:
            for modality in modalities:
                candidates = [m for m in candidates if modality in m.modalities]

        if require_reasoning:
            candidates = [m for m in candidates if m.reasoning_quality >= 0.7]

        if max_cost:
            candidates = [
                m for m in candidates
                if (m.cost_per_1k_input + m.cost_per_1k_output) <= max_cost
            ]

        if max_latency:
            candidates = [
                m for m in candidates
                if m.avg_latency_ms <= max_latency
            ]

        # Return best scoring model
        if candidates:
            return max(candidates, key=lambda m: m.task_scores.get(task.value, 0.5))

        return None

    def update_health(self, health: ProviderHealth) -> None:
        """Update provider health status."""
        self._health[health.provider] = health

    def get_healthy_providers(self) -> list[str]:
        """Get list of healthy providers."""
        return [
            p for p, h in self._health.items()
            if h.is_healthy and h.success_rate >= 0.8
        ]

    def get_stats(self) -> dict:
        """Get registry statistics."""
        return {
            "total_providers": len(self._providers),
            "total_models": len(self._models),
            "healthy_providers": len(self.get_healthy_providers()),
            "providers": {
                pid: {"models": len([m for m in self._models.values() if m.provider == pid])}
                for pid in self._providers
            }
        }


# =============================================================================
# Unified LLM Interface
# =============================================================================

class UnifiedLLM:
    """
    Unified interface for all LLM operations.

    This is the main entry point for the rest of the system.
    Handles routing, fallback, caching, and orchestration.
    """

    def __init__(self, registry: ProviderRegistry, config: dict):
        self.registry = registry
        self.config = config
        self._defaults = config.get("defaults", {})
        self._fallback_order = config.get("fallback_order", [])

        # Components
        self._cache = None  # Will be injected
        self._rate_limiter = RateLimiter()
        self._circuit_breaker = CircuitBreaker()

    async def generate(
        self,
        task: TaskType,
        input: str | list[dict],
        system_prompt: str = "",
        provider: str | None = None,
        model: str | None = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response using optimal provider selection.

        Args:
            task: Type of task to perform
            input: Input text or messages
            system_prompt: System instructions
            provider: Specific provider (or "auto" for automatic)
            model: Specific model (or "auto" for automatic)
            **kwargs: Additional request parameters

        Returns:
            LLMResponse with standardized structure
        """
        # Build request
        request = LLMRequest(
            task_type=task,
            input=input,
            system_prompt=system_prompt,
            preferred_provider=provider,
            preferred_model=model,
            **kwargs
        )

        # Determine provider chain
        provider_chain = self._get_provider_chain(task, provider)

        # Try each provider in order
        last_error = None
        for prov_id in provider_chain:
            prov = self.registry.get(prov_id)
            if not prov or not self._is_provider_usable(prov):
                continue

            # Check rate limits
            if not await self._rate_limiter.check(prov_id):
                continue

            # Check circuit breaker
            if self._circuit_breaker.is_open(prov_id):
                continue

            try:
                self._rate_limiter.record_request(prov_id)
                response = await prov.generate(request)

                # Record success
                self._circuit_breaker.record_success(prov_id)
                self._rate_limiter.record_success(prov_id, response.latency_ms)

                return response

            except Exception as e:
                last_error = e
                self._circuit_breaker.record_failure(prov_id)
                self._rate_limiter.record_failure(prov_id)
                continue

        # All providers failed
        return LLMResponse(
            content="",
            errors=[str(last_error)] if last_error else ["All providers failed"],
            warnings=["Fallback chain exhausted"]
        )

    async def generate_stream(
        self,
        task: TaskType,
        input: str | list[dict],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response."""
        request = LLMRequest(
            task_type=task,
            input=input,
            **kwargs
        )

        provider_chain = self._get_provider_chain(task, request.preferred_provider)

        for prov_id in provider_chain:
            prov = self.registry.get(prov_id)
            if not prov or not self._is_provider_usable(prov):
                continue

            try:
                async for chunk in prov.generate_stream(request):
                    yield chunk
                return
            except Exception:
                continue

    async def embed(self, text: str, provider: str | None = None) -> list[float]:
        """Generate embeddings."""
        providers = self._get_provider_chain(TaskType.EMBEDDING, provider)

        for prov_id in providers:
            prov = self.registry.get(prov_id)
            if not prov:
                continue

            try:
                return await prov.embed(text)
            except Exception:
                continue

        return []

    def _get_provider_chain(
        self,
        task: TaskType,
        preferred: str | None
    ) -> list[str]:
        """Determine provider chain for task."""
        if preferred and preferred != "auto":
            chain = [preferred] + self._fallback_order
        else:
            # Get default for task
            default = self._defaults.get(task.value, {})
            primary = default.get("provider")
            chain = ([primary] if primary else []) + self._fallback_order

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for p in chain:
            if p not in seen and p in self.registry.list_providers():
                seen.add(p)
                result.append(p)

        return result

    def _is_provider_usable(self, provider: LLMProvider) -> bool:
        """Check if provider is usable."""
        health = self.registry._health.get(provider.provider_id)
        return health and health.is_healthy and health.success_rate >= 0.5


# =============================================================================
# Reliability Components
# =============================================================================

class RateLimiter:
    """Token bucket rate limiter for providers."""

    def __init__(self):
        self._limits: dict[str, dict] = {}
        self._windows: dict[str, list[float]] = {}

    async def check(self, provider: str) -> bool:
        """Check if request is allowed under rate limits."""
        if provider not in self._limits:
            return True

        limit = self._limits[provider]
        now = time.time()

        # Clean old entries
        window = self._windows.get(provider, [])
        self._windows[provider] = [t for t in window if now - t < 60]

        # Check limit
        return len(self._windows.get(provider, [])) < limit.get("rpm", 60)

    def set_limit(self, provider: str, rpm: int) -> None:
        """Set rate limit for provider."""
        self._limits[provider] = {"rpm": rpm}

    def record_request(self, provider: str) -> None:
        """Record a request."""
        if provider not in self._windows:
            self._windows[provider] = []
        self._windows[provider].append(time.time())

    def record_success(self, provider: str, latency_ms: float) -> None:
        """Record successful request."""
        pass

    def record_failure(self, provider: str) -> None:
        """Record failed request."""
        pass


class CircuitBreaker:
    """Circuit breaker for provider failure handling."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self._failures: dict[str, int] = {}
        self._last_failure: dict[str, float] = {}
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout

    def is_open(self, provider: str) -> bool:
        """Check if circuit is open (too many failures)."""
        if provider not in self._failures:
            return False

        failures = self._failures[provider]
        last = self._last_failure.get(provider, 0)

        if failures >= self._failure_threshold:
            if time.time() - last < self._reset_timeout:
                return True
            else:
                # Reset after timeout
                self._failures[provider] = 0

        return False

    def record_success(self, provider: str) -> None:
        """Record successful request."""
        self._failures[provider] = 0

    def record_failure(self, provider: str) -> None:
        """Record failed request."""
        self._failures[provider] = self._failures.get(provider, 0) + 1
        self._last_failure[provider] = time.time()


# =============================================================================
# Plugin Loader
# =============================================================================

class PluginLoader:
    """Dynamically loads provider plugins."""

    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    async def load_from_config(self, config: dict) -> None:
        """Load all configured providers."""
        providers = config.get("providers", {})

        for provider_id, provider_config in providers.items():
            if not provider_config.get("enabled", True):
                continue

            try:
                provider = await self._load_provider(provider_id, provider_config)
                if provider:
                    await provider.initialize(provider_config)
                    self.registry.register(provider)
            except Exception as e:
                print(f"Failed to load provider {provider_id}: {e}")

    async def _load_provider(self, provider_id: str, config: dict) -> LLMProvider | None:
        """Load a specific provider plugin."""
        # Import based on provider ID
        if provider_id == "google_gemini":
            from providers.google.gemini_provider import GeminiProvider
            return GeminiProvider()
        elif provider_id == "openai":
            from providers.openai.openai_provider import OpenAIProvider
            return OpenAIProvider()
        elif provider_id == "anthropic":
            from providers.anthropic.anthropic_provider import AnthropicProvider
            return AnthropicProvider()
        elif provider_id == "nvidia_nim":
            from providers.nvidia.nvidia_provider import NVIDIAProvider
            return NVIDIAProvider()
        elif provider_id == "huggingface":
            from providers.huggingface.huggingface_provider import HuggingFaceProvider
            return HuggingFaceProvider()
        elif provider_id == "ollama":
            from providers.ollama.ollama_provider import OllamaProvider
            return OllamaProvider()
        elif provider_id == "vllm":
            from providers.vllm.vllm_provider import VLLMProvider
            return VLLMProvider()
        else:
            # Try dynamic import
            try:
                module = __import__(f"providers.{provider_id}", fromlist=["Provider"])
                return getattr(module, "Provider", None)()
            except ImportError:
                return None