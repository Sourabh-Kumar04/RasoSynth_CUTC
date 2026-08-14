"""
Provider Plugin System - Extensible Architecture

This module provides the infrastructure for adding new LLM providers
with minimal code changes. Each provider is a self-contained plugin.
"""

import asyncio
import time
from typing import Any, AsyncIterator, Optional
from abc import ABC, abstractmethod

from providers.core_lib.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    StreamChunk,
    ProviderHealth,
    ModelMetadata,
    TokenUsage,
    Modality,
    ProviderCapability,
    TaskType,
)


# =============================================================================
# Base Provider Implementation Utilities
# =============================================================================

class ProviderConfig:
    """Standardized provider configuration."""

    def __init__(self, config: dict):
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.timeout = config.get("timeout", 120)
        self.max_retries = config.get("max_retries", 3)
        self.rate_limit_rpm = config.get("rate_limit_rpm", 60)
        self.custom_params = config.get("custom_params", {})


class RetryStrategy:
    """Configurable retry strategy with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    async def execute(self, func, *args, **kwargs):
        """Execute function with retries."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt < self.max_retries - 1:
                    delay = min(
                        self.base_delay * (2 ** attempt),
                        self.max_delay
                    )
                    if self.jitter:
                        delay *= (0.5 + time.time() % 1)

                    await asyncio.sleep(delay)

        raise last_error


class TokenCounter:
    """Estimate token counts for various models."""

    @staticmethod
    def count_tokens(text: str, model_type: str = "default") -> int:
        """Estimate token count (rough approximation)."""
        if not text:
            return 0

        # Use word-based approximation (rough)
        words = text.split()
        if model_type in ["gpt", "claude"]:
            # ~1.3 tokens per word for English
            return int(len(words) * 1.3)
        elif model_type in ["gemini"]:
            # Gemini uses sentence piece
            return int(len(text) / 4)
        else:
            return int(len(text) / 4)

    @staticmethod
    def count_messages(messages: list[dict]) -> int:
        """Count tokens in message list."""
        total = 0
        for msg in messages:
            total += TokenCounter.count_tokens(msg.get("content", ""))
            total += 4  # Overhead per message
        return total


# =============================================================================
# Abstract Provider Plugin Template
# =============================================================================

class AbstractProviderPlugin(ABC):
    """
    Template for implementing LLM providers.

    Subclass this to implement a new provider with:
    - Standard authentication
    - Request/response mapping
    - Error handling
    - Rate limiting
    - Retry logic
    """

    provider_id: str = ""
    display_name: str = ""

    def __init__(self):
        self.config: ProviderConfig | None = None
        self._retry_strategy = RetryStrategy()
        self._health_status: ProviderHealth | None = None

    @abstractmethod
    async def _make_request(self, request: LLMRequest) -> dict:
        """Make the actual API request. Override in subclass."""
        pass

    @abstractmethod
    def _parse_response(self, raw_response: dict, request: LLMRequest) -> LLMResponse:
        """Parse API response to standard format. Override in subclass."""
        pass

    @abstractmethod
    def _get_api_headers(self) -> dict:
        """Get headers for API request. Override in subclass."""
        pass

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get base URL for API. Override in subclass."""
        pass

    async def initialize(self, config: dict) -> None:
        """Initialize provider with config."""
        self.config = ProviderConfig(config)
        self._retry_strategy.max_retries = config.get("max_retries", 3)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response with retry logic."""
        start_time = time.time()

        try:
            raw_response = await self._retry_strategy.execute(
                self._make_request,
                request
            )

            response = self._parse_response(raw_response, request)
            response.latency_ms = (time.time() - start_time) * 1000

            self._update_health(success=True)
            return response

        except Exception as e:
            self._update_health(success=False, error=str(e))
            return LLMResponse(
                content="",
                errors=[str(e)],
                provider=self.provider_id,
            )

    async def generate_stream(
        self,
        request: LLMRequest
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming response."""
        # Default implementation - override for actual streaming
        response = await self.generate(request)
        yield StreamChunk(
            content=response.content,
            delta=response.content,
            is_complete=True,
            tokens_so_far=response.tokens_used
        )

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Generate embeddings."""
        raise NotImplementedError(f"{self.provider_id} does not support embeddings")

    def _update_health(self, success: bool, error: str | None = None):
        """Update health status."""
        now = datetime.utcnow()

        if self._health_status is None:
            self._health_status = ProviderHealth(
                provider=self.provider_id,
                is_healthy=True,
                success_rate=1.0
            )

        if success:
            # Update success rate
            current = self._health_status.success_rate
            self._health_status.success_rate = current * 0.9 + 0.1
            self._health_status.is_healthy = True
            self._health_status.last_error = None
        else:
            # Update failure rate
            current = self._health_status.success_rate
            self._health_status.success_rate = current * 0.8
            self._health_status.last_error = error

            if self._health_status.success_rate < 0.5:
                self._health_status.is_healthy = False

        self._health_status.last_check = now

    async def health_check(self) -> ProviderHealth:
        """Check provider health."""
        try:
            # Make a simple test request
            test_request = LLMRequest(
                input="test",
                task_type=TaskType.TEXT_GENERATION
            )
            await self.generate(test_request)

            return ProviderHealth(
                provider=self.provider_id,
                is_healthy=True,
                success_rate=self._health_status.success_rate if self._health_status else 1.0
            )
        except Exception:
            return ProviderHealth(
                provider=self.provider_id,
                is_healthy=False,
                success_rate=0.0,
                last_error="Health check failed"
            )

    def list_models(self) -> list[ModelMetadata]:
        """List available models."""
        return []

    def get_model(self, model_id: str) -> ModelMetadata | None:
        """Get model metadata."""
        for model in self.list_models():
            if model.model_id == model_id:
                return model
        return None

    async def validate_config(self, config: dict) -> bool:
        """Validate provider configuration."""
        return bool(config.get("api_key"))

    async def cleanup(self) -> None:
        """Cleanup resources."""
        pass


# =============================================================================
# Plugin Registration System
# =============================================================================

class PluginRegistry:
    """Registry for provider plugins."""

    _plugins: dict[str, type] = {}
    _instances: dict[str, LLMProvider] = {}

    @classmethod
    def register(cls, provider_id: str):
        """Decorator to register a provider plugin."""
        def decorator(plugin_class):
            cls._plugins[provider_id] = plugin_class
            return plugin_class
        return decorator

    @classmethod
    def create(cls, provider_id: str, config: dict) -> LLMProvider | None:
        """Create a provider instance.

        NOTE: This is a sync factory. Async initialization (initialize()) must be called
        separately via await, e.g. in an async lifespan handler.
        The config is stored on the instance as _pending_config for deferred init.
        """
        if provider_id in cls._instances:
            return cls._instances[provider_id]

        plugin_class = cls._plugins.get(provider_id)
        if not plugin_class:
            return None

        instance = plugin_class()
        # Store config for later async initialization — do NOT call asyncio.run() here
        # because this may be invoked from within a running event loop (e.g. uvicorn).
        instance._pending_config = config

        cls._instances[provider_id] = instance
        return instance

    @classmethod
    async def initialize_instance(cls, provider_id: str, config: dict) -> bool:
        """Async-safe initialization of a provider instance. Call this from an async context."""
        instance = cls._instances.get(provider_id)
        if instance and hasattr(instance, 'initialize'):
            try:
                await instance.initialize(config)
                return True
            except Exception:
                return False
        return False

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered providers."""
        return list(cls._plugins.keys())

    @classmethod
    def get(cls, provider_id: str) -> type | None:
        """Get a provider class by ID."""
        return cls._plugins.get(provider_id)

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered plugins."""
        return list(cls._plugins.keys())

    @classmethod
    def get_instance(cls, provider_id: str) -> LLMProvider | None:
        """Get existing provider instance."""
        return cls._instances.get(provider_id)

    @classmethod
    def clear(cls) -> None:
        """Clear all instances (for testing)."""
        cls._instances.clear()


# =============================================================================
# Provider Mixins
# =============================================================================

class StreamingMixin:
    """Mixin for providers that support streaming."""

    async def generate_stream(
        self,
        request: LLMRequest
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming response."""
        chunk_index = 0
        accumulated_content = ""

        async for chunk in self._stream_request(request):
            accumulated_content += chunk
            chunk_index += 1

            yield StreamChunk(
                content=accumulated_content,
                delta=chunk,
                index=chunk_index,
                is_complete=False,
                tokens_so_far=TokenCounter.count_tokens(accumulated_content)
            )

        yield StreamChunk(
            content=accumulated_content,
            delta="",
            index=chunk_index,
            is_complete=True,
            tokens_so_far=TokenCounter.count_tokens(accumulated_content)
        )

    @abstractmethod
    async def _stream_request(self, request: LLMRequest) -> AsyncIterator[str]:
        """Override to implement streaming."""
        pass


class EmbeddingMixin:
    """Mixin for providers that support embeddings."""

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Generate embeddings."""
        return await self._generate_embeddings(text, model)

    @abstractmethod
    async def _generate_embeddings(self, text: str, model: str | None) -> list[float]:
        """Override to implement embeddings."""
        pass


class ToolCallingMixin:
    """Mixin for providers that support tool calling."""

    def supports_tools(self) -> bool:
        return True

    async def generate_with_tools(
        self,
        request: LLMRequest,
        tools: list[dict]
    ) -> LLMResponse:
        """Generate response with tool definitions."""
        request.tools = tools
        return await self.generate(request)


class VisionMixin:
    """Mixin for providers that support vision."""

    async def generate_with_images(
        self,
        request: LLMRequest,
        images: list[bytes]
    ) -> LLMResponse:
        """Generate response with image inputs."""
        request.modalities = [Modality.IMAGE, Modality.TEXT]
        request.metadata["images"] = images
        return await self.generate(request)


# =============================================================================
# Model Capability Registry
# =============================================================================

CAPABILITY_REGISTRY: dict[str, dict[str, ModelMetadata]] = {}


def register_model(
    provider_id: str,
    model_metadata: ModelMetadata
) -> None:
    """Register a model in the capability registry."""
    if provider_id not in CAPABILITY_REGISTRY:
        CAPABILITY_REGISTRY[provider_id] = {}

    CAPABILITY_REGISTRY[provider_id][model_metadata.model_id] = model_metadata


def get_model_capabilities(provider_id: str, model_id: str) -> ModelMetadata | None:
    """Get model capabilities from registry."""
    return CAPABILITY_REGISTRY.get(provider_id, {}).get(model_id)


def find_models_by_capability(capability: ProviderCapability) -> list[ModelMetadata]:
    """Find all models with a specific capability."""
    results = []

    for provider_models in CAPABILITY_REGISTRY.values():
        for model in provider_models.values():
            if capability in model.modalities or capability.value in str(model.capabilities):
                results.append(model)

    return results


# Import datetime for health check
from datetime import datetime