"""Featherless AI provider implementation (OpenAI-compatible)."""
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


@PluginRegistry.register("featherless")
class FeatherlessProvider(BaseProvider):
    """Featherless AI provider (runs any open-source model via OpenAI-compatible API)."""

    DEFAULT_BASE_URL = "https://api.featherless.ai/v1"

    SUPPORTED_MODELS = {
        "meta-llama/Meta-Llama-3.1-8B-Instruct": {"max_tokens": 8192, "cost": 0.0002},
        "meta-llama/Meta-Llama-3.1-70B-Instruct": {"max_tokens": 8192, "cost": 0.0008},
        "mistralai/Mistral-7B-Instruct-v0.3": {"max_tokens": 8192, "cost": 0.0002},
        "Qwen/Qwen2.5-7B-Instruct": {"max_tokens": 8192, "cost": 0.0002},
        "Qwen/Qwen2.5-72B-Instruct": {"max_tokens": 8192, "cost": 0.0008},
    }

    def __init__(self, config=None):
        """Initialize with optional config (dict, ProviderConfig, or None)."""
        if isinstance(config, dict):
            provider_config = ProviderConfig(
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url") or os.environ.get("FEATHERLESS_BASE_URL", self.DEFAULT_BASE_URL),
                timeout=config.get("timeout", 120),
            )
        elif config is None:
            provider_config = ProviderConfig(
                api_key=os.environ.get("FEATHERLESS_API_KEY", ""),
                base_url=os.environ.get("FEATHERLESS_BASE_URL", self.DEFAULT_BASE_URL),
            )
        else:
            provider_config = config

        super().__init__(provider_config, "featherless")
        self.default_model = "meta-llama/Meta-Llama-3.1-8B-Instruct"
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

        base_url = config.get("base_url") or os.environ.get("FEATHERLESS_BASE_URL", self.DEFAULT_BASE_URL)
        provider_config = ProviderConfig(
            api_key=config.get("api_key", "") or os.environ.get("FEATHERLESS_API_KEY", ""),
            base_url=base_url,
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        if not provider_config.api_key:
            raise ValueError("Featherless API key is required")

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
        """Internal: Generate text using Featherless OpenAI-compatible endpoint with automatic model fallback."""
        import time
        start_time = time.time()

        if not self.client:
            api_key = self.config.api_key or os.environ.get("FEATHERLESS_API_KEY", "")
            if api_key and OPENAI_AVAILABLE:
                self.client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=self.config.base_url or os.environ.get("FEATHERLESS_BASE_URL", self.DEFAULT_BASE_URL),
                    timeout=self.config.timeout or 120,
                )
            else:
                raise RuntimeError("Featherless client not initialized. Set FEATHERLESS_API_KEY environment variable.")

        candidate_models = []
        if model:
            candidate_models.append(model)
        env_model = os.environ.get("FEATHERLESS_MODEL")
        if env_model and env_model not in candidate_models:
            candidate_models.append(env_model)
        fallbacks = [
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
            "Qwen/Qwen2.5-7B-Instruct",
        ]
        for fb in fallbacks:
            if fb not in candidate_models:
                candidate_models.append(fb)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_err = None
        for cand_model in candidate_models:
            try:
                response = await self.client.chat.completions.create(
                    model=cand_model,
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

                self.default_model = cand_model

                return ModelResponse(
                    content=content,
                    model=cand_model,
                    tokens_used=tokens,
                    latency_ms=latency_ms,
                    cost=self._estimate_cost(tokens),
                    provider=self.name,
                    finish_reason=choice.finish_reason,
                )
            except Exception as e:
                err_str = str(e)
                if "404" in err_str or "not found" in err_str.lower() or "not deployed" in err_str.lower():
                    last_err = e
                    continue
                raise RuntimeError(f"Featherless AI generation failed: {e}")

        raise RuntimeError(f"Featherless AI generation failed: {last_err}")

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
        raise NotImplementedError(
            "Featherless AI does not support text embeddings via this provider interface. Route to OpenAI/Ollama/Gemini."
        )

    async def embed(self, text: str, model: str | None = None):
        raise NotImplementedError(
            "Featherless AI does not support text embeddings via this provider interface. Route to OpenAI/Ollama/Gemini."
        )

    def get_capabilities(self) -> list:
        from providers.core_lib.base import ProviderCapability
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.FAST_INFERENCE,
        ]

    async def health_check(self) -> ProviderHealth:
        try:
            if not self.client:
                return ProviderHealth(provider=self.name, is_healthy=False, last_error="Not initialized")
            import time
            start = time.time()
            models = await self.client.models.list()
            latency = (time.time() - start) * 1000
            return ProviderHealth(provider=self.name, is_healthy=True, avg_latency_ms=latency)
        except Exception as e:
            return ProviderHealth(provider=self.name, is_healthy=False, last_error=str(e))

    def _estimate_cost(self, tokens: int) -> float:
        return (tokens / 1000) * 0.0002

    def get_models(self) -> list[ModelMetadata]:
        from providers.core_lib.base import Modality
        return [
            ModelMetadata(
                model_id=m_id,
                provider=self.name,
                display_name=m_id.split("/")[-1],
                description=f"Featherless AI model: {m_id}",
                modalities=[Modality.TEXT],
                max_tokens=info["max_tokens"],
                context_window=128000,
                cost_per_1k_input=info["cost"],
                cost_per_1k_output=info["cost"],
            )
            for m_id, info in self.SUPPORTED_MODELS.items()
        ]
