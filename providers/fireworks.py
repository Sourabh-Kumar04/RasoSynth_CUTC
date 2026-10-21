"""Fireworks AI provider implementation (OpenAI-compatible)."""
import asyncio
import os
from typing import Optional

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from providers.base_provider import (
    BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse
)
from providers.core_lib.base import (
    LLMRequest, LLMResponse, TokenUsage, ProviderHealth, TaskType, ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry


@PluginRegistry.register("fireworks")
class FireworksProvider(BaseProvider):
    """Fireworks AI provider (high-performance OpenAI-compatible inference)."""

    DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"

    SUPPORTED_MODELS = {
        "accounts/fireworks/models/llama-v3p1-8b-instruct": {"max_tokens": 8192, "cost": 0.0002},
        "accounts/fireworks/models/llama-v3p1-70b-instruct": {"max_tokens": 8192, "cost": 0.0009},
        "accounts/fireworks/models/qwen2p5-72b-instruct": {"max_tokens": 8192, "cost": 0.0009},
        "accounts/fireworks/models/mixtral-8x7b-instruct": {"max_tokens": 4096, "cost": 0.0005},
        "accounts/fireworks/models/deepseek-v3": {"max_tokens": 8192, "cost": 0.0009},
    }

    def __init__(self, config=None):
        """Initialize with optional config (dict, ProviderConfig, or None)."""
        if isinstance(config, dict):
            provider_config = ProviderConfig(
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url") or os.environ.get("FIREWORKS_BASE_URL", self.DEFAULT_BASE_URL),
                timeout=config.get("timeout", 120),
            )
        elif config is None:
            provider_config = ProviderConfig(
                api_key=os.environ.get("FIREWORKS_API_KEY", ""),
                base_url=os.environ.get("FIREWORKS_BASE_URL", self.DEFAULT_BASE_URL),
            )
        else:
            provider_config = config

        super().__init__(provider_config, "fireworks")
        self.default_model = "accounts/fireworks/models/llama-v3p1-8b-instruct"
        self.client = None

        if provider_config.api_key and OPENAI_AVAILABLE:
            self.client = AsyncOpenAI(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url or self.DEFAULT_BASE_URL,
                timeout=provider_config.timeout,
            )

    async def initialize(self, config: dict) -> None:
        """Initialize provider with configuration dict (called by ProviderRouter)."""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")

        base_url = config.get("base_url") or os.environ.get("FIREWORKS_BASE_URL", self.DEFAULT_BASE_URL)
        provider_config = ProviderConfig(
            api_key=config.get("api_key", "") or os.environ.get("FIREWORKS_API_KEY", ""),
            base_url=base_url,
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        if not provider_config.api_key:
            raise ValueError("Fireworks API key is required")

        self.client = AsyncOpenAI(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url,
            timeout=provider_config.timeout,
        )

    async def _execute_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs
    ) -> ModelResponse:
        """Internal: Generate text using Fireworks OpenAI-compatible endpoint."""
        import time
        start_time = time.time()

        model_name = model or self.default_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 4096,
                **kwargs
            )

            choice = response.choices[0]
            content = choice.message.content or ""
            usage = response.usage
            tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0) if usage else 0
            latency_ms = (time.time() - start_time) * 1000

            return ModelResponse(
                content=content,
                model=model_name,
                tokens_used=tokens,
                latency_ms=latency_ms,
                cost=self._estimate_cost(tokens),
                provider=self.name,
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            raise RuntimeError(f"Fireworks AI generation failed: {e}")

    async def generate(self, prompt_or_request, system_prompt=None, temperature=0.7, max_tokens=None, model=None, **kwargs):
        """Generate text. Supports both LLMRequest (bridge) and legacy parameter modes."""
        if isinstance(prompt_or_request, LLMRequest):
            request = prompt_or_request
            prompt = request.input if isinstance(request.input, str) else str(request.input)
            response = await self._execute_generate(
                prompt=prompt,
                system_prompt=request.system_prompt or None,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                model=request.model if hasattr(request, "model") and request.model else None,
            )
            return LLMResponse(
                content=response.content,
                provider=self.name,
                model=response.model,
                tokens_used=response.tokens_used,
                token_usage=TokenUsage(
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=response.tokens_used,
                ),
                latency_ms=response.latency_ms,
                finish_reason=response.finish_reason or "stop",
            )
        else:
            return await self._execute_generate(
                prompt=prompt_or_request,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
                **kwargs
            )

    async def _execute_embed(self, text: str, **kwargs) -> EmbeddingResponse:
        return EmbeddingResponse(
            embedding=[0.0] * 1536,
            model="fireworks-embed-unsupported",
            tokens_used=len(text) // 4,
            provider=self.name,
        )

    async def embed(self, text: str, model: str | None = None):
        response = await self._execute_embed(text)
        return response.embedding

    def get_capabilities(self) -> list:
        from providers.core_lib.base import ProviderCapability
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.FAST_INFERENCE,
        ]

    async def health_check(self) -> ProviderHealth:
        try:
            if not self.client:
                return ProviderHealth(is_healthy=False, latency_ms=0, last_error="Not initialized")
            import time
            start = time.time()
            models = await self.client.models.list()
            latency = (time.time() - start) * 1000
            return ProviderHealth(is_healthy=True, latency_ms=latency, active_models=len(models.data) if hasattr(models, "data") else 1)
        except Exception as e:
            return ProviderHealth(is_healthy=False, latency_ms=0, last_error=str(e))

    def _estimate_cost(self, tokens: int) -> float:
        return (tokens / 1000) * 0.0002

    def get_models(self) -> list[ModelMetadata]:
        from providers.core_lib.base import Modality
        return [
            ModelMetadata(
                model_id=m_id,
                provider=self.name,
                display_name=m_id.split("/")[-1],
                description=f"Fireworks AI model: {m_id}",
                modalities=[Modality.TEXT],
                max_tokens=info["max_tokens"],
                context_window=128000,
                cost_per_1k_input=info["cost"],
                cost_per_1k_output=info["cost"],
            )
            for m_id, info in self.SUPPORTED_MODELS.items()
        ]
