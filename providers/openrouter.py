"""OpenRouter Provider Adapter

Production-grade OpenRouter API integration with:
- Unified access to 100+ models
- Automatic provider fallback
- Streaming support
- Cost optimization
"""
import asyncio
import logging
from typing import Any, AsyncIterator, Optional
from dataclasses import dataclass

from providers.base_provider import (
    BaseProvider,
    ProviderConfig,
    ProviderCapability,
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
)
from providers.core_lib.plugin import (
    AbstractProviderPlugin,
    PluginRegistry,
)

logger = logging.getLogger(__name__)


# OpenRouter model configurations (popular ones)
OPENROUTER_MODELS = {
    "anthropic/claude-3.5-sonnet": ModelMetadata(
        model_id="anthropic/claude-3.5-sonnet",
        provider="openrouter",
        display_name="Claude 3.5 Sonnet (via OpenRouter)",
        description="Latest Anthropic model via OpenRouter",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=200000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=600,
        throughput_tps=50,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        reasoning_quality=0.95,
        coding_quality=0.90,
        multilingual_quality=0.90,
    ),
    "google/gemini-2.0-flash-exp": ModelMetadata(
        model_id="google/gemini-2.0-flash-exp",
        provider="openrouter",
        display_name="Gemini 2.0 Flash (via OpenRouter)",
        description="Google's latest model via OpenRouter",
        modalities=[Modality.TEXT, Modality.IMAGE],
        max_tokens=8192,
        context_window=1000000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=400,
        throughput_tps=100,
        cost_per_1k_input=0.0000,  # Free
        cost_per_1k_output=0.0000,
        reasoning_quality=0.88,
        coding_quality=0.82,
        multilingual_quality=0.95,
    ),
    "openai/gpt-4o": ModelMetadata(
        model_id="openai/gpt-4o",
        provider="openrouter",
        display_name="GPT-4o (via OpenRouter)",
        description="OpenAI's flagship model via OpenRouter",
        modalities=[Modality.TEXT, Modality.IMAGE],
        max_tokens=16384,
        context_window=128000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=500,
        throughput_tps=80,
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.01,
        reasoning_quality=0.90,
        coding_quality=0.88,
        multilingual_quality=0.85,
    ),
    "meta-llama/llama-3.3-70b-instruct": ModelMetadata(
        model_id="meta-llama/llama-3.3-70b-instruct",
        provider="openrouter",
        display_name="Llama 3.3 70B (via OpenRouter)",
        description="Meta's latest open model via OpenRouter",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=128000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=300,
        throughput_tps=150,
        cost_per_1k_input=0.00035,
        cost_per_1k_output=0.00040,
        reasoning_quality=0.85,
        coding_quality=0.80,
        multilingual_quality=0.85,
    ),
    "deepseek/deepseek-chat": ModelMetadata(
        model_id="deepseek/deepseek-chat",
        provider="openrouter",
        display_name="DeepSeek Chat (via OpenRouter)",
        description="DeepSeek model via OpenRouter",
        modalities=[Modality.TEXT],
        max_tokens=4096,
        context_window=64000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=600,
        throughput_tps=40,
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        reasoning_quality=0.75,
        coding_quality=0.70,
        multilingual_quality=0.80,
    ),
}


@dataclass
class OpenRouterConfig(ProviderConfig):
    """OpenRouter-specific configuration."""
    api_base: str = "https://openrouter.ai/api/v1"
    referrer: str = "https://github.com/ai-dataset-engineer"
    title: Optional[str] = None


@PluginRegistry.register("openrouter")
class OpenRouterProvider(AbstractProviderPlugin):
    """OpenRouter provider plugin with unified model access."""

    provider_id = "openrouter"
    display_name = "OpenRouter"

    MODELS = OPENROUTER_MODELS

    CAPABILITIES = [
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.VISION,
    ]

    def __init__(self, config: OpenRouterConfig, model: str = "anthropic/claude-3.5-sonnet"):
        super().__init__(config, model)
        self.openrouter_config = config
        self.base_url = config.base_url or config.api_base
        self._client = None

    async def initialize(self) -> None:
        """Initialize OpenRouter client."""
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.openrouter_config.referrer,
            }
            if self.openrouter_config.title:
                headers["X-Title"] = self.openrouter_config.title

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.config.timeout,
                headers=headers
            )
            logger.info(f"OpenRouter provider initialized with model {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {e}")
            raise

    async def close(self) -> None:
        """Close OpenRouter client."""
        if self._client:
            await self._client.aclose()

    @property
    def capabilities(self) -> list[ProviderCapability]:
        """Return provider capabilities."""
        caps = [ProviderCapability.TEXT_GENERATION]
        model_meta = self.MODELS.get(self.model)
        if model_meta and Modality.IMAGE in model_meta.modalities:
            caps.append(ProviderCapability.VISION)
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
        """Generate text using OpenRouter API."""
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
                provider="openrouter",
                finish_reason=data["choices"][0].get("finish_reason"),
            )

        except Exception as e:
            logger.error(f"OpenRouter generation failed: {e}")
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
            logger.error(f"OpenRouter streaming failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check OpenRouter API health."""
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


__all__ = ["OpenRouterProvider", "OpenRouterConfig", "OPENROUTER_MODELS"]