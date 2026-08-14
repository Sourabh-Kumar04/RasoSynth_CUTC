"""Ollama local provider implementation."""
import asyncio
import httpx
from typing import Optional

from providers.base_provider import (
    BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse
)
from providers.core_lib.base import (
    LLMRequest, LLMResponse, TokenUsage, ProviderHealth, TaskType, ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry


@PluginRegistry.register("ollama")
class OllamaProvider(BaseProvider):
    """Ollama local inference provider."""

    SUPPORTED_MODELS = [
        "llama3.1:8b",
        "llama3.1:70b",
        "llama3.2:1b",
        "llama3.2:3b",
        "mistral:7b",
        "mixtral:8x7b",
        "phi3:mini",
        "codellama:7b",
        "gemma2:2b",
        "gemma2:9b",
        "qwen2.5:7b",
        "qwen2.5:72b",
        "deepseek-r1:7b",
        "deepseek-r1:70b",
    ]

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

        super().__init__(provider_config, "ollama")
        self.base_url = provider_config.base_url or "http://localhost:11434"
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=provider_config.timeout)
        self.default_model = "llama3.2:3b"

    async def initialize(self, config: dict) -> None:
        """Initialize provider with configuration dict (called by ProviderRouter)."""
        provider_config = ProviderConfig(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 120),
        )
        self.config = provider_config
        self.base_url = provider_config.base_url or "http://localhost:11434"
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=provider_config.timeout)

    async def _execute_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        **kwargs
    ) -> ModelResponse:
        """Internal: Generate text using Ollama. Renamed from original generate()."""
        import time
        start_time = time.time()

        model_name = model or self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.post(
                "/api/chat",
                json={
                    "model": model_name,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens or 4096,
                    }
                }
            )
            response.raise_for_status()

            data = response.json()
            content = data["message"]["content"]
            tokens = data.get("eval_count", self._estimate_tokens(content))
            latency_ms = (time.time() - start_time) * 1000

            return ModelResponse(
                content=content,
                model=model_name,
                tokens_used=tokens,
                latency_ms=latency_ms,
                cost=0.0,  # Local, free
                provider=self.name,
            )
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama generation failed: {e}")

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
        """Generate text with streaming using Ollama."""
        if isinstance(prompt_or_request, LLMRequest):
            request = prompt_or_request
            prompt = request.input if isinstance(request.input, str) else str(request.input)
            system_prompt = request.system_prompt or None
            temperature = request.temperature
            max_tokens = request.max_tokens
        else:
            prompt = prompt_or_request

        from providers.base_provider import StreamChunk

        model_name = model or self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        chunks = []
        full_content = ""

        async with self.client.stream(
            "POST",
            "/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens or 4096,
                }
            }
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    import json
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            full_content += data["message"]["content"]
                            chunks.append(StreamChunk(
                                content=full_content,
                                delta=data["message"]["content"],
                                is_complete=data.get("done", False)
                            ))
                    except json.JSONDecodeError:
                        continue

        return chunks

    async def _execute_embed(self, text: str, model: str | None = None) -> EmbeddingResponse:
        """Internal: Generate embeddings using Ollama."""
        import time
        start_time = time.time()

        model_name = model or "nomic-embed-text"

        try:
            response = await self.client.post(
                "/api/embeddings",
                json={"model": model_name, "prompt": text}
            )
            response.raise_for_status()

            data = response.json()
            embedding = data["embedding"]
            latency_ms = (time.time() - start_time) * 1000

            return EmbeddingResponse(
                embedding=embedding,
                model=model_name,
                tokens_used=self._estimate_tokens(text),
                provider=self.name
            )
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama embedding failed: {e}")

    async def embed(self, text: str, model: str | None = None):
        """Generate embeddings. Returns embedding vector list for AbstractProviderPlugin compat."""
        response = await self._execute_embed(text, model)
        return response.embedding

    async def list_models(self) -> list[str]:
        """List available models in Ollama."""
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except httpx.HTTPError:
            return []

    def get_capabilities(self) -> list:
        """Return provider capabilities."""
        from providers.core_lib.base import ProviderCapability
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.TEXT_EMBEDDING,
        ]

    async def health_check(self) -> ProviderHealth:
        """Check if Ollama is running. Returns ProviderHealth for PluginRegistry compat."""
        try:
            response = await self.client.get("/api/tags")
            is_healthy = response.status_code == 200
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