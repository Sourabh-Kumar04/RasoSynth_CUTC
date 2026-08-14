"""Hugging Face provider implementation."""
import asyncio
from typing import Optional

try:
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

from providers.base_provider import (
    BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse
)
from providers.core_lib.base import (
    LLMRequest, LLMResponse, TokenUsage, ProviderHealth, TaskType, ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry


@PluginRegistry.register("huggingface")
class HuggingFaceProvider(BaseProvider):
    """Hugging Face Inference API provider."""

    SUPPORTED_MODELS = {
        "meta-llama/Llama-3.1-8B-Instruct": {"cost": 0.0},
        "mistralai/Mistral-7B-Instruct-v0.3": {"cost": 0.0},
        "Qwen/Qwen2.5-7B-Instruct": {"cost": 0.0},
        "microsoft/Phi-3-mini-128k-instruct": {"cost": 0.0},
        "stability-ai/stable-diffusion-3-medium": {"cost": 0.0},
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

        super().__init__(provider_config, "huggingface")
        self.default_model = "meta-llama/Llama-3.1-8B-Instruct"
        self.client = None

        if HF_AVAILABLE:
            token = provider_config.api_key or provider_config.base_url or ""
            self.client = InferenceClient(token=token)

    async def initialize(self, config: dict) -> None:
        """Initialize provider with configuration dict (called by ProviderRouter)."""
        if not HF_AVAILABLE:
            raise ImportError("huggingface-hub not installed. Run: pip install huggingface-hub")

        provider_config = ProviderConfig(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        token = provider_config.api_key or provider_config.base_url or ""
        self.client = InferenceClient(token=token)

    async def _execute_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs
    ) -> ModelResponse:
        """Internal: Generate text using Hugging Face Inference API."""
        import time
        start_time = time.time()

        model_name = model or self.default_model

        if system_prompt:
            full_prompt = f"System: {system_prompt}\nUser: {prompt}\nAssistant:"
        else:
            full_prompt = prompt

        try:
            completion = self.client.chat_completion(
                model=model_name,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=temperature,
                max_tokens=max_tokens or 512,
                **kwargs
            )

            content = completion.choices[0].message.content or ""
            tokens = self._estimate_tokens(full_prompt + content)
            latency_ms = (time.time() - start_time) * 1000

            return ModelResponse(
                content=content,
                model=model_name,
                tokens_used=tokens,
                latency_ms=latency_ms,
                cost=0.0,  # HF inference is free
                provider=self.name,
            )
        except Exception as e:
            raise RuntimeError(f"HuggingFace generation failed: {e}")

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

    async def _execute_embed(self, text: str, model: str | None = None) -> EmbeddingResponse:
        """Internal: Generate embeddings using Hugging Face sentence transformers."""
        import time
        start_time = time.time()

        model_name = model or "sentence-transformers/all-MiniLM-L6-v2"

        try:
            embedding = self.client.feature_extraction(
                model=model_name,
                text=text
            )

            if isinstance(embedding, list):
                embedding = embedding[0] if len(embedding) > 0 else embedding

            tokens = self._estimate_tokens(text)
            latency_ms = (time.time() - start_time) * 1000

            return EmbeddingResponse(
                embedding=embedding if isinstance(embedding, list) else list(embedding),
                model=model_name,
                tokens_used=tokens,
                provider=self.name
            )
        except Exception as e:
            raise RuntimeError(f"HuggingFace embedding failed: {e}")

    async def embed(self, text: str, model: str | None = None):
        """Generate embeddings. Returns embedding vector list for AbstractProviderPlugin compat."""
        response = await self._execute_embed(text, model)
        return response.embedding

    def get_capabilities(self) -> list:
        """Return provider capabilities."""
        from providers.core_lib.base import ProviderCapability
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.TEXT_EMBEDDING,
        ]

    def _estimate_tokens(self, text: str) -> int:
        """Helper: Estimate token count based on string length (approx. 4 chars per token)."""
        return len(text) // 4

    async def health_check(self) -> ProviderHealth:
        """Check if HuggingFace API is accessible. Returns ProviderHealth for PluginRegistry compat."""
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
            ))
        return models