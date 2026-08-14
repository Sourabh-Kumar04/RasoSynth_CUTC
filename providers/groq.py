"""Groq Provider Adapter

Production-grade Groq API integration with:
- Ultra-low latency inference
- Streaming support
- Fast inference optimization
- Checkpoint migration support
"""
import asyncio
import logging
from typing import Any, AsyncIterator, Optional
from dataclasses import dataclass

from providers.base_provider import (
    BaseProvider,
    ProviderConfig,
    ModelResponse,
    StreamChunk,
)
from providers.core_lib.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderHealth,
    ModelMetadata,
    TaskType,
    Modality,
    ProviderCapability,
)
from providers.core_lib.plugin import (
    AbstractProviderPlugin,
    PluginRegistry,
)

logger = logging.getLogger(__name__)


# Groq model configurations
GROQ_MODELS = {
    "llama-3.3-70b-versatile": ModelMetadata(
        model_id="llama-3.3-70b-versatile",
        provider="groq",
        display_name="Llama 3.3 70B Versatile",
        description="Fast versatile model for general tasks",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=128000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=200,
        throughput_tps=200,
        cost_per_1k_input=0.00036,
        cost_per_1k_output=0.00040,
        reasoning_quality=0.85,
        coding_quality=0.80,
        multilingual_quality=0.85,
    ),
    "llama-3.1-70b-versatile": ModelMetadata(
        model_id="llama-3.1-70b-versatile",
        provider="groq",
        display_name="Llama 3.1 70B",
        description="Previous generation fast model",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=128000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=250,
        throughput_tps=150,
        cost_per_1k_input=0.00035,
        cost_per_1k_output=0.00040,
        reasoning_quality=0.82,
        coding_quality=0.78,
        multilingual_quality=0.82,
    ),
    "llama-3.1-8b-instant": ModelMetadata(
        model_id="llama-3.1-8b-instant",
        provider="groq",
        display_name="Llama 3.1 8B Instant",
        description="Ultra-fast small model",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=128000,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=True,
        avg_latency_ms=50,
        throughput_tps=500,
        cost_per_1k_input=0.00005,
        cost_per_1k_output=0.00008,
        reasoning_quality=0.65,
        coding_quality=0.60,
        multilingual_quality=0.70,
    ),
    "mixtral-8x7b-32768": ModelMetadata(
        model_id="mixtral-8x7b-32768",
        provider="groq",
        display_name="Mixtral 8x7B",
        description="Mixture of experts fast model",
        modalities=[Modality.TEXT],
        max_tokens=32768,
        context_window=32768,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=True,
        avg_latency_ms=150,
        throughput_tps=250,
        cost_per_1k_input=0.00024,
        cost_per_1k_output=0.00024,
        reasoning_quality=0.75,
        coding_quality=0.72,
        multilingual_quality=0.78,
    ),
}


@dataclass
class GroqConfig(ProviderConfig):
    """Groq-specific configuration."""
    api_base: str = "https://api.groq.com/openai/v1"


@PluginRegistry.register("groq")
class GroqProvider(AbstractProviderPlugin):
    """Groq AI provider plugin with ultra-low latency support."""

    provider_id = "groq"
    display_name = "Groq"

    MODELS = GROQ_MODELS

    CAPABILITIES = [
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.FAST_INFERENCE,
    ]

    def __init__(self, config: GroqConfig, model: str = "llama-3.3-70b-versatile"):
        super().__init__(config, model)
        self.groq_config = config
        self.base_url = config.base_url or config.api_base
        self._client = None

    async def initialize(self) -> None:
        """Initialize Groq client."""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                }
            )
            logger.info(f"Groq provider initialized with model {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise

    async def close(self) -> None:
        """Close Groq client."""
        if self._client:
            await self._client.aclose()

    @property
    def capabilities(self) -> list[ProviderCapability]:
        """Return provider capabilities."""
        caps = [ProviderCapability.TEXT_GENERATION, ProviderCapability.FAST_INFERENCE]
        model_meta = self.MODELS.get(self.model)
        if model_meta and model_meta.supports_tools:
            caps.append(ProviderCapability.FUNCTION_CALLING)
        return caps

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """Generate text using Groq API."""
        if not self._client:
            await self.initialize()

        import time
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": False,
        }

        if kwargs.get("tools"):
            payload["tools"] = kwargs["tools"]

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            latency_ms = (time.time() - start_time) * 1000
            cost = self._calculate_cost(
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0)
            )

            return ModelResponse(
                content=content,
                model=self.model,
                tokens_used=usage.get("total_tokens", 0),
                latency_ms=latency_ms,
                cost=cost,
                provider="groq",
                finish_reason=data["choices"][0].get("finish_reason"),
            )

        except Exception as e:
            logger.error(f"Groq generation failed: {e}")
            raise

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Stream text generation."""
        if not self._client:
            await self.initialize()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": True,
        }

        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        import json
                        chunk_data = json.loads(data)
                        delta = chunk_data["choices"][0].get("delta", {}).get("content", "")

                        yield StreamChunk(
                            content=delta,
                            delta=delta,
                            is_complete=False
                        )

            yield StreamChunk(content="", delta="", is_complete=True)

        except Exception as e:
            logger.error(f"Groq streaming failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Groq API health."""
        try:
            if not self._client:
                await self.initialize()

            response = await self._client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        model_meta = self.MODELS.get(self.model)
        if not model_meta:
            return 0.0

        return (input_tokens / 1000 * model_meta.cost_per_1k_input) + \
               (output_tokens / 1000 * model_meta.cost_per_1k_output)

    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response for LLMRequest."""
        response = await self.generate(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return LLMResponse(
            content=response.content,
            model=response.model,
            finish_reason=response.finish_reason or "stop",
            tokens_used=response.tokens_used,
            latency_ms=response.latency_ms,
            cost=response.cost,
        )

    async def stream_response(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Stream response for LLMRequest."""
        async for chunk in self.stream_generate(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ):
            yield chunk


__all__ = ["GroqProvider", "GroqConfig", "GROQ_MODELS"]