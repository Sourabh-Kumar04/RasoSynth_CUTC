"""xAI (Grok) provider implementation."""
import asyncio
from typing import Optional

try:
    from openai import AsyncOpenAI
    XAI_AVAILABLE = True
except ImportError:
    XAI_AVAILABLE = False

from providers.base_provider import (
    BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse
)
from providers.core_lib.base import (
    LLMRequest, LLMResponse, TokenUsage, ProviderHealth, TaskType, ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry


@PluginRegistry.register("xai")
class XAIProvider(BaseProvider):
    """xAI Grok API provider."""

    SUPPORTED_MODELS = {
        "grok-2": {"max_tokens": 8192, "cost": 0.002},
        "grok-2-mini": {"max_tokens": 8192, "cost": 0.001},
        "grok-1": {"max_tokens": 8192, "cost": 0.002},
        "grok-1.5": {"max_tokens": 8192, "cost": 0.001},
    }

    def __init__(self, config=None):
        """Initialize with optional config (dict, ProviderConfig, or None).

        Supports no-arg construction for PluginRegistry compatibility.
        """
        if isinstance(config, dict):
            provider_config = ProviderConfig(
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url"),
                timeout=config.get("timeout", 120),
            )
        elif config is None:
            provider_config = ProviderConfig()
        else:
            provider_config = config

        super().__init__(provider_config, "xai")
        self.default_model = "grok-2"
        self.client = None

        if provider_config.api_key and XAI_AVAILABLE:
            self.client = AsyncOpenAI(
                api_key=provider_config.api_key,
                base_url="https://api.x.ai/v1",
                timeout=provider_config.timeout
            )

    async def initialize(self, config: dict) -> None:
        """Initialize provider with configuration dict (called by ProviderRouter)."""
        if not XAI_AVAILABLE:
            raise ImportError("openai not installed. Run: pip install openai")

        provider_config = ProviderConfig(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        if not provider_config.api_key:
            raise ValueError("xAI API key is required")

        self.client = AsyncOpenAI(
            api_key=provider_config.api_key,
            base_url="https://api.x.ai/v1",
            timeout=provider_config.timeout
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
        """Internal: Generate text using xAI Grok. Renamed from original generate()."""
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
            tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
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
            raise RuntimeError(f"xAI generation failed: {e}")

    async def generate(self, prompt_or_request, system_prompt=None, temperature=0.7, max_tokens=None, model=None, **kwargs):
        """Generate text. Supports both LLMRequest (bridge) and legacy parameter modes.

        Bridge mode (called by ProviderRouter):
            provider.generate(request: LLMRequest) -> LLMResponse
        Legacy mode (called directly):
            provider.generate(prompt, system_prompt=..., ...) -> ModelResponse
        """
        if isinstance(prompt_or_request, LLMRequest):
            # Bridge mode — called by ProviderRouter via AbstractProviderPlugin interface
            request = prompt_or_request
            prompt = request.input if isinstance(request.input, str) else str(request.input)
            system_prompt = request.system_prompt or None
            temperature = request.temperature
            max_tokens = request.max_tokens

            response = await self._execute_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
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
            # Legacy mode
            return await self._execute_generate(
                prompt=prompt_or_request,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
                **kwargs
            )

    async def _execute_embed(self, text: str, **kwargs) -> EmbeddingResponse:
        """Internal: xAI doesn't support standalone embeddings."""
        return EmbeddingResponse(
            embedding=[0.0] * 1536,
            model="grok-embedding-unsupported",
            tokens_used=self._estimate_tokens(text),
            provider=self.name
        )

    async def embed(self, text: str, model: str | None = None):
        """Generate embeddings. Returns embedding vector list for AbstractProviderPlugin compat."""
        response = await self._execute_embed(text)
        return response.embedding

    def get_capabilities(self) -> list:
        """Return provider capabilities."""
        from providers.core_lib.base import ProviderCapability
        return [
            ProviderCapability.TEXT_GENERATION,
        ]

    async def health_check(self) -> ProviderHealth:
        """Check if xAI API is accessible. Returns ProviderHealth for PluginRegistry compat."""
        try:
            response = await self._execute_generate("Hello", max_tokens=5)
            is_healthy = len(response.content) > 0
            return ProviderHealth(
                provider=self.name,
                is_healthy=is_healthy,
                success_rate=1.0 if is_healthy else 0.0,
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.name,
                is_healthy=False,
                success_rate=0.0,
                last_error=str(e),
            )

    def list_models(self) -> list[ModelMetadata]:
        """List available models."""
        models = []
        for model_id, info in self.SUPPORTED_MODELS.items():
            models.append(ModelMetadata(
                model_id=model_id,
                provider=self.name,
                display_name=model_id,
                max_tokens=info.get("max_tokens", 4096),
            ))
        return models