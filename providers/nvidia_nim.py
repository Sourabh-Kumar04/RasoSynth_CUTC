"""NVIDIA NIM provider implementation."""
import asyncio
import os
from typing import Any

try:
    from openai import OpenAI
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


@PluginRegistry.register("nvidia_nim")
class NVIDIANIMProvider(BaseProvider):
    """NVIDIA NIM API provider (NVIDIA's managed inference endpoints)."""

    SUPPORTED_MODELS = {
        "nvidia/llama-3.1-nemotron-70b-instruct": {"max_tokens": 4096, "cost": 0.00015},
        "nvidia/llama-3.1-nemotron-80b-instruct": {"max_tokens": 4096, "cost": 0.0002},
        "nvidia/mistral-nemo-12b-instruct": {"max_tokens": 4096, "cost": 0.0001},
        "nvidia/phi-4-mini-instruct": {"max_tokens": 2048, "cost": 0.00005},
        "meta/llama-3.1-405b-instruct": {"max_tokens": 4096, "cost": 0.0003},
        "meta/llama-3.1-70b-instruct": {"max_tokens": 4096, "cost": 0.0002},
        "meta/llama-3.1-8b-instruct": {"max_tokens": 4096, "cost": 0.0001},
    }

    EMBEDDING_MODELS = {
        "nvidia/nv-embed-v1": {"cost": 0.0001},
        "nvidia/llama-3.2-nv-embedqa-1b-v1": {"cost": 0.0001},
        "nvidia/nemotron-3-embedding": {"cost": 0.0001},
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

        super().__init__(provider_config, "nvidia_nim")
        self.default_model = "meta/llama-3.1-8b-instruct"
        # NV-Embed-QA was retired from integrate.api.nvidia.com; current
        # catalog uses nvidia/nv-embed-v1 as the canonical embedding model.
        self.default_embedding_model = "nvidia/nv-embed-v1"
        self.client = None

        if provider_config.api_key and OPENAI_AVAILABLE:
            base_url = provider_config.base_url or "https://integrate.api.nvidia.com/v1"
            self.client = OpenAI(
                api_key=provider_config.api_key,
                base_url=base_url,
                timeout=provider_config.timeout
            )

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
        base_url = provider_config.base_url or "https://integrate.api.nvidia.com/v1"
        self.client = OpenAI(
            api_key=provider_config.api_key,
            base_url=base_url,
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
        """Internal: Generate text using NVIDIA NIM with 404/429 retry and endpoint fallback."""
        import time
        import random
        start_time = time.time()

        model_name = model or self.default_model
        model_info = self.SUPPORTED_MODELS.get(model_name, {})

        if max_tokens is None:
            max_tokens = model_info.get("max_tokens", 4096)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # ── Candidate base URLs (primary + fallback) ──────────────────────
        base_urls = [
            self.config.base_url,
            "https://integrate.api.nvidia.com/v1",
            "https://api.nvidia.com/v1",
        ]
        # Remove duplicates while keeping order
        seen = set()
        base_urls = [u for u in base_urls if u and not (u in seen or seen.add(u))]

        # ── Candidate models (requested + known fallbacks) ────────────────
        candidate_models = [model_name]
        for fallback in self.SUPPORTED_MODELS:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_exception = None
        loop = asyncio.get_event_loop()

        for base_url in base_urls:
            for cand_model in candidate_models:
                for attempt in range(3):  # 3 retries per base_url/model combo
                    try:
                        # Lazily create client per base_url
                        from openai import OpenAI
                        client = OpenAI(
                            api_key=self.config.api_key,
                            base_url=base_url,
                            timeout=self.config.timeout
                        )

                        response = await loop.run_in_executor(
                            None,
                            lambda: client.chat.completions.create(
                                model=cand_model,
                                messages=messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )
                        )

                        choice = response.choices[0]
                        content = choice.message.content or ""

                        usage = response.usage
                        tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
                        latency_ms = (time.time() - start_time) * 1000

                        return ModelResponse(
                            content=content,
                            model=cand_model,
                            tokens_used=tokens,
                            latency_ms=latency_ms,
                            cost=self._estimate_cost(tokens),
                            provider=self.name,
                            finish_reason=choice.finish_reason,
                            metadata={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens, "base_url": base_url}
                        )

                    except Exception as e:
                        last_exception = e
                        err_str = str(e).lower()

                        # 429 → exponential backoff and retry same endpoint/model
                        if any(marker in err_str for marker in ("429", "rate limit", "too many requests")):
                            if attempt < 2:
                                delay = 2.0 * (2 ** attempt) + random.uniform(0, 1)
                                await asyncio.sleep(delay)
                                continue
                            else:
                                break  # Try next base_url or model

                        # 404 → likely model not found at this endpoint, try next model or base_url
                        if any(marker in err_str for marker in ("404", "not_found", "model_not_found", "not found")):
                            break  # Try next candidate model or base_url

                        # Auth/network errors → re-raise immediately
                        if any(marker in err_str for marker in ("401", "403", "invalid api", "authentication")):
                            raise RuntimeError(f"NVIDIA NIM authentication failed: {e}")

                        # Other errors → try next combination
                        break

        raise RuntimeError(f"NVIDIA NIM generation failed after all fallbacks: {last_exception}")

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
                **kwargs
            )

    async def _execute_embed(self, text: str, model: str | None = None) -> EmbeddingResponse:
        """Internal: Generate embeddings using NVIDIA NIM embedding models."""
        import time
        start_time = time.time()

        # Try the requested model first, then fall back to known-working models
        # (the NIM catalog rotates and old model IDs return 404).
        candidate_models = []
        if model:
            candidate_models.append(model)
        candidate_models.append(self.default_embedding_model)
        for fallback in self.EMBEDDING_MODELS:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_error: Exception | None = None
        for model_name in candidate_models:
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda mn=model_name: self.client.embeddings.create(
                        model=mn,
                        input=text,
                        encoding_format="float"
                    )
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
                last_error = e
                # 404 means the model is no longer in the catalog; try the next
                # one. Other errors (auth, network) are re-raised immediately.
                err_str = str(e)
                if "404" not in err_str and "NotFound" not in err_str and "model_not_found" not in err_str:
                    raise RuntimeError(f"NVIDIA NIM embedding failed: {e}")
                continue

        raise RuntimeError(
            f"NVIDIA NIM embedding failed: none of the candidate models "
            f"({candidate_models}) are available. Last error: {last_error}"
        )

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

    async def health_check(self) -> ProviderHealth:
        """Check if NVIDIA NIM API is accessible. Returns ProviderHealth for PluginRegistry compat."""
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