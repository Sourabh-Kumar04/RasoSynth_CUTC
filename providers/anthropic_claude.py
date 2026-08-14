"""Anthropic Claude provider implementation."""
import asyncio
from typing import Any

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from providers.base_provider import (
    BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse, StreamChunk
)
from providers.core_lib.base import (
    LLMRequest, LLMResponse, TokenUsage, ProviderHealth, TaskType, ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry


@PluginRegistry.register("anthropic")
class AnthropicClaudeProvider(BaseProvider):
    """Anthropic Claude AI provider."""

    SUPPORTED_MODELS = {
        "claude-opus-4-20250514": {"max_tokens": 4096, "cost": 0.015},
        "claude-sonnet-4-20250514": {"max_tokens": 4096, "cost": 0.003},
        "claude-haiku-4-5-20250620": {"max_tokens": 4096, "cost": 0.0008},
        "claude-3-5-sonnet-20241022": {"max_tokens": 8192, "cost": 0.003},
        "claude-3-opus-20240229": {"max_tokens": 4096, "cost": 0.015},
        "claude-3-sonnet-20240229": {"max_tokens": 4096, "cost": 0.003},
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

        super().__init__(provider_config, "anthropic_claude")
        self.default_model = "claude-sonnet-4-20250514"
        self.client = None

        if provider_config.api_key and ANTHROPIC_AVAILABLE:
            self.client = AsyncAnthropic(api_key=provider_config.api_key, timeout=provider_config.timeout)

    async def initialize(self, config: dict) -> None:
        """Initialize provider with configuration dict (called by ProviderRouter)."""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic not installed. Run: pip install anthropic")

        provider_config = ProviderConfig(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        self.client = AsyncAnthropic(api_key=provider_config.api_key, timeout=provider_config.timeout)

    async def _execute_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        thinking: dict | None = None,
        **kwargs
    ) -> ModelResponse:
        """Internal: Generate text using Claude. Renamed from original generate()."""
        import time
        start_time = time.time()

        model_name = model or self.default_model
        model_info = self.SUPPORTED_MODELS.get(model_name, {})

        if max_tokens is None:
            max_tokens = model_info.get("max_tokens", 4096)

        try:
            extra_kwargs = {}
            if thinking:
                extra_kwargs["thinking"] = thinking

            response = await self.client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                **extra_kwargs,
                **kwargs
            )

            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text

            usage = response.usage
            tokens = usage.input_tokens + usage.output_tokens
            latency_ms = (time.time() - start_time) * 1000

            return ModelResponse(
                content=content,
                model=model_name,
                tokens_used=tokens,
                latency_ms=latency_ms,
                cost=self._estimate_cost(tokens),
                provider=self.name,
                finish_reason=response.stop_reason if hasattr(response, 'stop_reason') else None,
                metadata={
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "thinking_tokens": getattr(usage, 'thinking_tokens', 0) if hasattr(usage, 'thinking_tokens') else 0
                }
            )
        except Exception as e:
            raise RuntimeError(f"Claude generation failed: {e}")

    async def generate(self, prompt_or_request, system_prompt=None, temperature=0.7, max_tokens=None, model=None, thinking=None, **kwargs):
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
                    prompt_tokens=response.metadata.get("input_tokens", 0) if hasattr(response, 'metadata') and isinstance(response.metadata, dict) else 0,
                    completion_tokens=response.metadata.get("output_tokens", 0) if hasattr(response, 'metadata') and isinstance(response.metadata, dict) else 0,
                    total_tokens=response.tokens_used,
                ),
                latency_ms=response.latency_ms,
                finish_reason=response.finish_reason or "end_turn",
            )
        else:
            # Legacy mode
            return await self._execute_generate(
                prompt=prompt_or_request,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
                thinking=thinking,
                **kwargs
            )

    async def generate_stream(
        self,
        prompt_or_request=None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs
    ):
        """Generate text with streaming using Claude."""
        if isinstance(prompt_or_request, LLMRequest):
            request = prompt_or_request
            prompt = request.input if isinstance(request.input, str) else str(request.input)
            system_prompt = request.system_prompt or None
            temperature = request.temperature
            max_tokens = request.max_tokens
        else:
            prompt = prompt_or_request

        import time
        start_time = time.time()

        model_name = model or self.default_model

        chunks = []
        full_content = ""

        async with self.client.messages.stream(
            model=model_name,
            max_tokens=max_tokens or 4096,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            **kwargs
        ) as stream:
            async for event in stream:
                if hasattr(event, 'content_block') and hasattr(event.content_block, 'text'):
                    full_content += event.content_block.text
                    chunks.append(StreamChunk(
                        content=full_content,
                        delta=event.content_block.text,
                        is_complete=False
                    ))

        if chunks:
            chunks[-1].is_complete = True

        return chunks

    async def _execute_embed(self, text: str, **kwargs) -> EmbeddingResponse:
        """Internal: Claude doesn't support embeddings - returns zero vector."""
        import time
        start_time = time.time()

        return EmbeddingResponse(
            embedding=[0.0] * 1536,  # Placeholder zero vector
            model="claude-embedding-unsupported",
            tokens_used=len(text) // 4,
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
            ProviderCapability.FUNCTION_CALLING,
            ProviderCapability.LONG_CONTEXT,
        ]

    async def health_check(self) -> ProviderHealth:
        """Check if Claude API is accessible. Returns ProviderHealth for PluginRegistry compat."""
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