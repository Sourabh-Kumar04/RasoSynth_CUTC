"""OpenAI provider implementation."""
import asyncio

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from providers.base_provider import (
    BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse, StreamChunk
)
from providers.core_lib.base import (
    LLMRequest, LLMResponse, TokenUsage, ProviderHealth, TaskType, ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry


@PluginRegistry.register("openai")
class OpenAIProvider(BaseProvider):
    """OpenAI API provider."""

    SUPPORTED_MODELS = {
        "gpt-4o": {"max_tokens": 4096, "cost": 0.0025},
        "gpt-4o-mini": {"max_tokens": 4096, "cost": 0.00015},
        "gpt-4-turbo": {"max_tokens": 4096, "cost": 0.01},
        "gpt-4": {"max_tokens": 4096, "cost": 0.03},
        "gpt-3.5-turbo": {"max_tokens": 4096, "cost": 0.0005},
    }

    EMBEDDING_MODELS = {
        "text-embedding-3-small": {"dimensions": 1536, "cost": 0.00002},
        "text-embedding-3-large": {"dimensions": 3072, "cost": 0.00013},
        "text-embedding-ada-002": {"dimensions": 1536, "cost": 0.0001},
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

        super().__init__(provider_config, "openai")
        self.default_model = "gpt-4o-mini"
        self.default_embedding_model = "text-embedding-3-small"
        self.client = None

        if provider_config.api_key and OPENAI_AVAILABLE:
            self.client = AsyncOpenAI(api_key=provider_config.api_key, timeout=provider_config.timeout)

    async def initialize(self, config: dict) -> None:
        """Initialize provider with configuration dict (called by ProviderRouter)."""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai not installed. Run: pip install openai")

        provider_config = ProviderConfig(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        self.client = AsyncOpenAI(api_key=provider_config.api_key, timeout=provider_config.timeout)

    async def _execute_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        response_format: dict | None = None,
        **kwargs
    ) -> ModelResponse:
        """Internal: Generate text using OpenAI. Renamed from original generate()."""
        import time
        start_time = time.time()

        model_name = model or self.default_model
        model_info = self.SUPPORTED_MODELS.get(model_name, {})

        if max_tokens is None:
            max_tokens = model_info.get("max_tokens", 4096)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            extra_kwargs = {}
            if response_format:
                extra_kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra_kwargs,
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
                metadata={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")

    async def generate(self, prompt_or_request, system_prompt=None, temperature=0.7, max_tokens=None, model=None, response_format=None, **kwargs):
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
                    prompt_tokens=response.metadata.get("prompt_tokens", 0) if hasattr(response, 'metadata') and isinstance(response.metadata, dict) else 0,
                    completion_tokens=response.metadata.get("completion_tokens", 0) if hasattr(response, 'metadata') and isinstance(response.metadata, dict) else 0,
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
                response_format=response_format,
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
        """Generate text with streaming using OpenAI."""
        if isinstance(prompt_or_request, LLMRequest):
            request = prompt_or_request
            prompt = request.input if isinstance(request.input, str) else str(request.input)
            system_prompt = request.system_prompt or None
            temperature = request.temperature
            max_tokens = request.max_tokens
        else:
            prompt = prompt_or_request

        import time

        model_name = model or self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        chunks = []
        full_content = ""

        stream = await self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                full_content += chunk.choices[0].delta.content
                chunks.append(StreamChunk(
                    content=full_content,
                    delta=chunk.choices[0].delta.content,
                    is_complete=False
                ))

        if chunks:
            chunks[-1].is_complete = True

        return chunks

    async def _execute_embed(self, text: str, model: str | None = None) -> EmbeddingResponse:
        """Internal: Generate embeddings using OpenAI."""
        import time
        start_time = time.time()

        model_name = model or self.default_embedding_model

        try:
            response = await self.client.embeddings.create(
                model=model_name,
                input=text,
                encoding_format="float"
            )

            embedding = response.data[0].embedding
            tokens = response.usage.total_tokens
            latency_ms = (time.time() - start_time) * 1000

            return EmbeddingResponse(
                embedding=embedding,
                model=model_name,
                tokens_used=tokens,
                provider=self.name
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding failed: {e}")

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
            ProviderCapability.VISION,
            ProviderCapability.FUNCTION_CALLING,
        ]

    async def health_check(self) -> ProviderHealth:
        """Check if OpenAI API is accessible. Returns ProviderHealth for PluginRegistry compat."""
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