"""Together AI Provider Adapter

Production-grade Together API integration with:
- 100+ open models
- Fast inference
- Competitive pricing
- Streaming support
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


# Together AI model configurations
TOGETHER_MODELS = {
    "Meta-Llama-3.3-70B-Instruct": ModelMetadata(
        model_id="Meta-Llama-3.3-70B-Instruct",
        provider="together",
        display_name="Llama 3.3 70B Instruct",
        description="Meta's latest instruction-tuned model",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=128000,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=False,
        avg_latency_ms=400,
        throughput_tps=100,
        cost_per_1k_input=0.00033,
        cost_per_1k_output=0.00035,
        reasoning_quality=0.85,
        coding_quality=0.80,
        multilingual_quality=0.85,
    ),
    "Meta-Llama-3.1-405B-Instruct": ModelMetadata(
        model_id="Meta-Llama-3.1-405B-Instruct",
        provider="together",
        display_name="Llama 3.1 405B Instruct",
        description="Large Meta model for complex tasks",
        modalities=[Modality.TEXT],
        max_tokens=4096,
        context_window=128000,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=False,
        avg_latency_ms=800,
        throughput_tps=30,
        cost_per_1k_input=0.00088,
        cost_per_1k_output=0.00088,
        reasoning_quality=0.90,
        coding_quality=0.85,
        multilingual_quality=0.88,
    ),
    "Qwen/Qwen2.5-72B-Instruct": ModelMetadata(
        model_id="Qwen/Qwen2.5-72B-Instruct",
        provider="together",
        display_name="Qwen 2.5 72B Instruct",
        description="Alibaba's powerful open model",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=32768,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=False,
        avg_latency_ms=350,
        throughput_tps=120,
        cost_per_1k_input=0.00030,
        cost_per_1k_output=0.00030,
        reasoning_quality=0.82,
        coding_quality=0.78,
        multilingual_quality=0.90,
    ),
    "mistralai/Mixtral-8x22B-Instruct-v0.1": ModelMetadata(
        model_id="mistralai/Mixtral-8x22B-Instruct-v0.1",
        provider="together",
        display_name="Mixtral 8x22B",
        description="Mistral's mixture of experts",
        modalities=[Modality.TEXT],
        max_tokens=65536,
        context_window=65536,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=False,
        avg_latency_ms=500,
        throughput_tps=80,
        cost_per_1k_input=0.00060,
        cost_per_1k_output=0.00060,
        reasoning_quality=0.80,
        coding_quality=0.75,
        multilingual_quality=0.85,
    ),
    "deepseek-ai/DeepSeek-V3": ModelMetadata(
        model_id="deepseek-ai/DeepSeek-V3",
        provider="together",
        display_name="DeepSeek V3",
        description="DeepSeek's latest model",
        modalities=[Modality.TEXT],
        max_tokens=4096,
        context_window=64000,
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=False,
        avg_latency_ms=450,
        throughput_tps=90,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00025,
        reasoning_quality=0.88,
        coding_quality=0.82,
        multilingual_quality=0.80,
    ),
}


@dataclass
class TogetherConfig(ProviderConfig):
    """Together AI-specific configuration."""
    api_base: str = "https://api.together.xyz/v1"


@PluginRegistry.register("together")
class TogetherProvider(AbstractProviderPlugin):
    """Together AI provider plugin with competitive pricing."""

    provider_id = "together"
    display_name = "Together AI"

    MODELS = TOGETHER_MODELS

    CAPABILITIES = [
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.LONG_CONTEXT,
    ]

    def __init__(self, config: TogetherConfig, model: str = "Meta-Llama-3.3-70B-Instruct"):
        super().__init__(config, model)
        self.together_config = config
        self.base_url = config.base_url or config.api_base
        self._client = None

    async def initialize(self) -> None:
        """Initialize Together AI client."""
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
            logger.info(f"Together AI provider initialized with model {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Together AI client: {e}")
            raise

    async def close(self) -> None:
        """Close Together AI client."""
        if self._client:
            await self._client.aclose()

    @property
    def capabilities(self) -> list[ProviderCapability]:
        """Return provider capabilities."""
        caps = [ProviderCapability.TEXT_GENERATION]
        model_meta = self.MODELS.get(self.model)
        if model_meta and model_meta.context_window > 32000:
            caps.append(ProviderCapability.LONG_CONTEXT)
        return caps

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """Generate text using Together AI API."""
        if not self._client:
            await self.initialize()

        import time
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Together AI uses different format
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": False,
        }

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
                provider="together",
                finish_reason=data["choices"][0].get("finish_reason"),
            )

        except Exception as e:
            logger.error(f"Together AI generation failed: {e}")
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
            logger.error(f"Together AI streaming failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Together AI API health."""
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


__all__ = ["TogetherProvider", "TogetherConfig", "TOGETHER_MODELS"]