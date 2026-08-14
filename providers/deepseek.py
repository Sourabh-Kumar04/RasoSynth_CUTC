"""DeepSeek Provider Adapter

Production-grade DeepSeek API integration with:
- Text generation
- Streaming support
- Tool calling (via function calling)
- Checkpoint migration support
- Provider failover integration
"""
import asyncio
import logging
from typing import Any, AsyncIterator, Optional, Dict
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


# DeepSeek model configurations
DEEPSEEK_MODELS = {
    "deepseek-chat": ModelMetadata(
        model_id="deepseek-chat",
        provider="deepseek",
        display_name="DeepSeek Chat",
        description="General purpose chat model",
        modalities=[Modality.TEXT],
        max_tokens=4096,
        context_window=64000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=800,
        throughput_tps=30,
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        reasoning_quality=0.75,
        coding_quality=0.70,
        multilingual_quality=0.80,
    ),
    "deepseek-coder": ModelMetadata(
        model_id="deepseek-coder",
        provider="deepseek",
        display_name="DeepSeek Coder",
        description="Code-specialized model",
        modalities=[Modality.TEXT],
        max_tokens=4096,
        context_window=64000,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=900,
        throughput_tps=25,
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        reasoning_quality=0.80,
        coding_quality=0.90,
        multilingual_quality=0.70,
    ),
    "deepseek-reasoner": ModelMetadata(
        model_id="deepseek-reasoner",
        provider="deepseek",
        display_name="DeepSeek Reasoner",
        description="Advanced reasoning model",
        modalities=[Modality.TEXT],
        max_tokens=4096,
        context_window=64000,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=False,
        avg_latency_ms=2000,
        throughput_tps=10,
        cost_per_1k_input=0.00055,
        cost_per_1k_output=0.00110,
        reasoning_quality=0.95,
        coding_quality=0.75,
        multilingual_quality=0.75,
    ),
}


@dataclass
class DeepSeekConfig(ProviderConfig):
    """DeepSeek-specific configuration."""
    api_base: str = "https://api.deepseek.com"
    organization: Optional[str] = None


@PluginRegistry.register("deepseek")
class DeepSeekProvider(AbstractProviderPlugin):
    """DeepSeek AI provider plugin with full production support."""

    provider_id = "deepseek"
    display_name = "DeepSeek"

    MODELS = DEEPSEEK_MODELS

    CAPABILITIES = [
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.FUNCTION_CALLING,
    ]

    def __init__(self, config: DeepSeekConfig, model: str = "deepseek-chat"):
        super().__init__(config, model)
        self.deepseek_config = config
        self.base_url = config.base_url or config.api_base
        self._client = None

    async def initialize(self) -> None:
        """Initialize DeepSeek client."""
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
            logger.info(f"DeepSeek provider initialized with model {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize DeepSeek client: {e}")
            raise

    async def close(self) -> None:
        """Close DeepSeek client."""
        if self._client:
            await self._client.aclose()

    @property
    def capabilities(self) -> list[ProviderCapability]:
        """Return provider capabilities."""
        model_meta = self.MODELS.get(self.model)
        caps = [ProviderCapability.TEXT_GENERATION]
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
        """Generate text using DeepSeek API."""
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

        # Add tool calling if requested
        if kwargs.get("tools"):
            payload["tools"] = kwargs["tools"]

        try:
            response = await self._client.post("/v1/chat/completions", json=payload)
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
                provider="deepseek",
                finish_reason=data["choices"][0].get("finish_reason"),
            )

        except Exception as e:
            logger.error(f"DeepSeek generation failed: {e}")
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
            async with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
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
            logger.error(f"DeepSeek streaming failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check DeepSeek API health."""
        try:
            if not self._client:
                await self.initialize()

            response = await self._client.get("/v1/models")
            return response.status_code == 200
        except Exception:
            return False

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        # DeepSeek pricing (approximate)
        input_cost_per_1k = 0.00014
        output_cost_per_1k = 0.00028

        return (input_tokens / 1000 * input_cost_per_1k) + (output_tokens / 1000 * output_cost_per_1k)

    # For provider registry compatibility
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


# Export for provider registry
__all__ = ["DeepSeekProvider", "DeepSeekConfig", "DEEPSEEK_MODELS"]