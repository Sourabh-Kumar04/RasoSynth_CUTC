"""Google Gemini provider implementation."""
import asyncio
from typing import Any

try:
    import google.genai as genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from providers.base_provider import (
    BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse, StreamChunk
)
from providers.core_lib.base import (
    LLMRequest, LLMResponse, TokenUsage, ProviderHealth, TaskType, ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry


@PluginRegistry.register("google_gemini")
class GoogleGeminiProvider(BaseProvider):
    """Google Gemini AI provider."""

    SUPPORTED_MODELS = {
        "gemini-2.0-flash": {"max_tokens": 8192, "cost": 0.0001},
        "gemini-1.5-flash": {"max_tokens": 8192, "cost": 0.000075},
        "gemini-1.5-pro": {"max_tokens": 32768, "cost": 0.00125},
        "gemini-1.0-pro": {"max_tokens": 30720, "cost": 0.0005},
    }

    EMBEDDING_MODELS = {
        "text-embedding-004": {"cost": 0.0001},
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

        super().__init__(provider_config, "google_gemini")
        self.default_model = "gemini-2.0-flash"
        self.default_embedding_model = "text-embedding-004"
        self._client = None

        if provider_config.api_key and GEMINI_AVAILABLE:
            self._client = genai.Client(api_key=provider_config.api_key)

    async def initialize(self, config: dict) -> None:
        """Initialize provider with configuration dict (called by ProviderRouter)."""
        if not GEMINI_AVAILABLE:
            raise ImportError("google-genai not installed. Run: pip install google-genai")

        provider_config = ProviderConfig(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        self._client = genai.Client(api_key=provider_config.api_key)

    async def _execute_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs
    ) -> ModelResponse:
        """Internal: Generate text using Gemini with 429 exponential-backoff retry."""
        import time
        import random
        start_time = time.time()

        model_name = model or self.default_model
        model_info = self.SUPPORTED_MODELS.get(model_name, {})

        if max_tokens is None:
            max_tokens = model_info.get("max_tokens", 8192)

        if not self._client:
            raise RuntimeError("Gemini client not initialized. Call initialize() first.")

        # ── Retry loop: up to 5 attempts with exponential backoff + jitter ──
        max_retries = 5
        base_delay = 2.0
        last_exception = None

        for attempt in range(max_retries):
            try:
                generation_config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    system_instruction=system_prompt if system_prompt else None,
                )

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=generation_config,
                    )
                )

                content = response.text or ""
                tokens = self._estimate_tokens(content)
                latency_ms = (time.time() - start_time) * 1000

                return ModelResponse(
                    content=content,
                    model=model_name,
                    tokens_used=tokens,
                    latency_ms=latency_ms,
                    cost=self._estimate_cost(tokens),
                    provider=self.name,
                    finish_reason=str(response.finish_reason) if hasattr(response, 'finish_reason') else None,
                )

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                # 429 / rate limit / quota exhausted → backoff and retry
                if any(marker in error_str for marker in ("429", "rate limit", "quota", "too many requests", "resource_exhausted")):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
                        continue
                # Non-retryable error → raise immediately
                raise RuntimeError(f"Gemini generation failed: {e}")

        raise RuntimeError(f"Gemini generation failed after {max_retries} retries: {last_exception}")

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

    async def generate_stream(
        self,
        prompt_or_request=None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs
    ):
        """Generate text with streaming using Gemini."""
        if isinstance(prompt_or_request, LLMRequest):
            request = prompt_or_request
            prompt = request.input if isinstance(request.input, str) else str(request.input)
            system_prompt = request.system_prompt or None
            temperature = request.temperature
            max_tokens = request.max_tokens
        else:
            prompt = prompt_or_request

        if not self._client:
            raise RuntimeError("Gemini client not initialized. Call initialize() first.")

        import time
        start_time = time.time()

        model_name = model or self.default_model

        try:
            generation_config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens or 8192,
                system_instruction=system_prompt if system_prompt else None,
            )

            chunks = []
            loop = asyncio.get_event_loop()

            def generate():
                return self._client.models.generate_content_stream(
                    model=model_name,
                    contents=prompt,
                    config=generation_config,
                )

            stream = await loop.run_in_executor(None, generate)

            full_content = ""
            for chunk in stream:
                delta = chunk.text or ""
                full_content += delta
                chunks.append(StreamChunk(
                    content=full_content,
                    delta=delta,
                    is_complete=False
                ))

            if chunks:
                chunks[-1].is_complete = True

            return chunks
        except Exception as e:
            raise RuntimeError(f"Gemini streaming failed: {e}")

    async def _stream_async(self, stream):
        """Convert sync iterator to async."""
        for item in stream:
            yield item

    async def _execute_embed(self, text: str, model: str | None = None) -> EmbeddingResponse:
        """Internal: Generate embeddings using Gemini."""
        if not self._client:
            raise RuntimeError("Gemini client not initialized. Call initialize() first.")

        import time
        start_time = time.time()

        model_name = model or self.default_embedding_model

        try:
            loop = asyncio.get_event_loop()

            def get_embedding():
                result = self._client.models.embed_content(
                    model=model_name,
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT"
                    ),
                )
                return result.embeddings[0].values if result.embeddings else []

            embedding = await loop.run_in_executor(None, get_embedding)
            tokens = self._estimate_tokens(text)
            latency_ms = (time.time() - start_time) * 1000

            return EmbeddingResponse(
                embedding=embedding,
                model=model_name,
                tokens_used=tokens,
                provider=self.name
            )
        except Exception as e:
            raise RuntimeError(f"Gemini embedding failed: {e}")

    async def embed(self, text: str, model: str | None = None):
        """Generate embeddings. Returns embedding vector list for AbstractProviderPlugin compat."""
        response = await self._execute_embed(text, model)
        return response.embedding

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 4 chars per token)."""
        return max(1, len(text) // 4)

    def get_capabilities(self) -> list:
        """Return provider capabilities."""
        from providers.core_lib.base import ProviderCapability
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.TEXT_EMBEDDING,
            ProviderCapability.VISION,
            ProviderCapability.LONG_CONTEXT,
        ]

    async def health_check(self) -> ProviderHealth:
        """Check if Gemini API is accessible. Returns ProviderHealth for PluginRegistry compat."""
        try:
            response = await self._execute_generate("Hi", max_tokens=5)
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