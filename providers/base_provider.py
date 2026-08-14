"""Base provider interface for all AI providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional
from enum import Enum
import time
import asyncio
import logging

# Import from core_lib to avoid duplicate enum issues
from providers.core_lib.base import ProviderCapability


@dataclass
class ProviderConfig:
    """Configuration for a provider."""
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 4096
    timeout: int = 120
    max_retries: int = 3
    rate_limit_rpm: int = 60
    cost_per_token: float = 0.0
    redis_url: Optional[str] = None


@dataclass
class ModelResponse:
    """Response from a text generation model."""
    content: str
    model: str
    tokens_used: int
    latency_ms: float
    cost: float
    provider: str
    finish_reason: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    """Response from an embedding model."""
    embedding: list[float]
    model: str
    tokens_used: int
    provider: str


@dataclass
class StreamChunk:
    """Chunk from a streaming response."""
    content: str
    delta: str
    is_complete: bool = False


class BaseProvider(ABC):
    """Abstract base class for all AI providers."""

    def __init__(self, config: ProviderConfig, name: str):
        self.config = config
        self.name = name
        self._request_times: list[float] = []
        self._token_counts: list[int] = []
        self._total_cost: float = 0.0
        self._total_latency: float = 0.0
        self._request_count: int = 0

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs
    ) -> ModelResponse:
        """Generate text from a prompt."""
        pass

    @abstractmethod
    async def embed(self, text: str, **kwargs) -> EmbeddingResponse:
        """Generate embeddings for text."""
        pass

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Generate text with streaming."""
        response = await self.generate(prompt, system_prompt, temperature, max_tokens, **kwargs)
        yield StreamChunk(content=response.content, delta=response.content, is_complete=True)

    def get_capabilities(self) -> list[ProviderCapability]:
        """Return list of provider capabilities."""
        return [ProviderCapability.TEXT_GENERATION]

    async def _rate_limit_check(self):
        """Check and enforce rate limits (async-safe)."""
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= self.config.rate_limit_rpm:
            sleep_time = 60 - (now - self._request_times[0])
            if sleep_time > 0:
                # Use async sleep instead of blocking sleep
                await asyncio.sleep(sleep_time)
        self._request_times.append(now)

    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost for token usage."""
        return tokens * self.config.cost_per_token

    def get_stats(self) -> dict:
        """Return provider statistics."""
        return {
            "name": self.name,
            "request_count": self._request_count,
            "total_cost": self._total_cost,
            "avg_latency_ms": self._total_latency / max(self._request_count, 1),
        }

    async def health_check(self) -> bool:
        """Check if the provider is healthy."""
        try:
            response = await self.generate("Hello", max_tokens=5)
            return len(response.content) > 0
        except Exception:
            return False


class ProviderRegistry:
    """Registry for managing provider instances."""

    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}

    def register(self, name: str, provider: BaseProvider):
        """Register a provider."""
        self._providers[name] = provider

    def get(self, name: str) -> BaseProvider | None:
        """Get a provider by name."""
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def get_stats(self) -> dict[str, dict]:
        """Get statistics for all providers."""
        return {name: p.get_stats() for name, p in self._providers.items()}