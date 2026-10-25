"""Groq Provider Adapter

Groq API integration with:
- Ultra-low latency inference
- Streaming support
- Fast inference optimization
- Checkpoint migration support
"""
import asyncio
import logging
from typing import Any, AsyncIterator, Optional
from dataclasses import dataclass

from providers.base_provider import (
    BaseProvider,
    ProviderConfig,
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
    ProviderCapability,
)
from providers.core_lib.plugin import (
    AbstractProviderPlugin,
    PluginRegistry,
)

logger = logging.getLogger(__name__)


# Deprecated free/dev-tier models (shutdown 2026-08-16) → current replacements
_DEPRECATED_GROQ_MODELS = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama3-70b-8192": "openai/gpt-oss-120b",
    "llama3-8b-8192": "openai/gpt-oss-20b",
    "mixtral-8x7b-32768": "openai/gpt-oss-20b",
    "gemma2-9b-it": "openai/gpt-oss-20b",
}


def _resolve_groq_model(model: str) -> str:
    """Map shut-down Groq model IDs to current free/dev replacements."""
    resolved = _DEPRECATED_GROQ_MODELS.get(model, model)
    if resolved != model:
        logger.warning("Groq model %s is deprecated; using %s instead", model, resolved)
    return resolved


# Groq model configurations (verified active Oct 2026).
# llama-3.1-8b-instant / llama-3.3-70b-versatile shut down for free/dev tiers 2026-08-16.
GROQ_MODELS = {
    "openai/gpt-oss-20b": ModelMetadata(
        model_id="openai/gpt-oss-20b",
        provider="groq",
        display_name="GPT OSS 20B (via Groq)",
        description="Primary Groq chat model — fast, structured-output capable",
        modalities=[Modality.TEXT],
        max_tokens=65536,
        context_window=131072,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=100,
        throughput_tps=1000,
        cost_per_1k_input=0.000075,
        cost_per_1k_output=0.00030,
        reasoning_quality=0.78,
        coding_quality=0.75,
        multilingual_quality=0.78,
    ),
    "openai/gpt-oss-120b": ModelMetadata(
        model_id="openai/gpt-oss-120b",
        provider="groq",
        display_name="GPT OSS 120B (via Groq)",
        description="Larger Groq chat model for harder reasoning tasks",
        modalities=[Modality.TEXT],
        max_tokens=65536,
        context_window=131072,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=300,
        throughput_tps=500,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.00060,
        reasoning_quality=0.90,
        coding_quality=0.88,
        multilingual_quality=0.88,
    ),
    "qwen/qwen3.8-27b": ModelMetadata(
        model_id="qwen/qwen3.8-27b",
        provider="groq",
        display_name="Qwen3.8 27B (via Groq)",
        description="Qwen 27B on Groq — strong multilingual / coding fallback",
        modalities=[Modality.TEXT],
        max_tokens=8192,
        context_window=131072,
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        avg_latency_ms=200,
        throughput_tps=200,
        cost_per_1k_input=0.00080,
        cost_per_1k_output=0.00400,
        reasoning_quality=0.85,
        coding_quality=0.88,
        multilingual_quality=0.92,
    ),
}


@dataclass
class GroqConfig(ProviderConfig):
    """Groq-specific configuration."""
    api_base: str = "https://api.groq.com/openai/v1"


@PluginRegistry.register("groq")
class GroqProvider(BaseProvider):
    """Groq AI provider plugin with ultra-low latency support."""

    provider_id = "groq"
    display_name = "Groq"

    MODELS = GROQ_MODELS

    CAPABILITIES = [
        ProviderCapability.TEXT_GENERATION,
        ProviderCapability.FAST_INFERENCE,
    ]

    def __init__(self, config: Optional[Any] = None, model: str = "openai/gpt-oss-120b"):  # noqa: E501
        import os
        if isinstance(config, dict):
            provider_config = ProviderConfig(
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url") or "https://api.groq.com/openai/v1",
                timeout=config.get("timeout", 60),
            )
            model = config.get("model") or model
        elif config is None:
            provider_config = ProviderConfig(
                api_key=os.environ.get("GROQ_API_KEY", ""),
                base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            )
            model = os.environ.get("GROQ_MODEL") or model
        else:
            provider_config = config
            model = getattr(config, "model", None) or os.environ.get("GROQ_MODEL") or model
        model = _resolve_groq_model(model)
        super().__init__(provider_config, "groq")
        self.groq_config = provider_config
        self.base_url = getattr(provider_config, "base_url", "https://api.groq.com/openai/v1")
        self.model = model
        self.default_model = model
        self._client = None

    async def initialize(self, config: Optional[dict] = None) -> None:
        """Initialize Groq client."""
        if config and isinstance(config, dict):
            api_key = config.get("api_key") or self.config.api_key
            base_url = config.get("base_url") or self.base_url
            if api_key:
                self.config.api_key = api_key
            if base_url:
                self.base_url = base_url
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
            logger.info(f"Groq provider initialized with model {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise

    async def close(self) -> None:
        """Close Groq client."""
        if self._client:
            await self._client.aclose()

    @property
    def capabilities(self) -> list[ProviderCapability]:
        """Return provider capabilities."""
        caps = [ProviderCapability.TEXT_GENERATION, ProviderCapability.FAST_INFERENCE]
        model_meta = self.MODELS.get(self.model)
        if model_meta and model_meta.supports_tools:
            caps.append(ProviderCapability.FUNCTION_CALLING)
        return caps

    async def _execute_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """Internal text generation using Groq API with candidate model fallbacks."""
        if not self._client:
            import os
            api_key = (
                getattr(self.config, "api_key", None)
                or os.environ.get("GROQ_API_KEY")
                or os.environ.get("GROP_API_KEY")
                or ""
            )
            if api_key:
                import httpx
                self.config.api_key = api_key.strip()
                self._client = httpx.AsyncClient(
                    base_url=self.base_url.rstrip("/"),
                    timeout=getattr(self.config, "timeout", 60),
                    headers={
                        "Authorization": f"Bearer {api_key.strip()}",
                        "Content-Type": "application/json",
                    }
                )
            else:
                raise RuntimeError("Groq client not initialized. Set GROQ_API_KEY environment variable.")

        import time
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        candidate_models = []
        if model:
            candidate_models.append(_resolve_groq_model(model))
        # Fallback chain — production models available on free/dev tiers (Oct 2026)
        for m in (self.model, "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"):
            m = _resolve_groq_model(m)
            if m not in candidate_models:
                candidate_models.append(m)

        last_error = None
        for cand_model in candidate_models:
            payload = {
                "model": cand_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or getattr(self.config, "max_tokens", 4096),
                "stream": False,
            }
            if kwargs.get("tools"):
                payload["tools"] = kwargs["tools"]
            if kwargs.get("response_format"):
                payload["response_format"] = kwargs["response_format"]
            # Keep reasoning models from burning tokens on chain-of-thought for JSON tasks
            if kwargs.get("reasoning_effort"):
                payload["reasoning_effort"] = kwargs["reasoning_effort"]
            elif "gpt-oss" in cand_model and kwargs.get("response_format"):
                payload["reasoning_effort"] = "low"

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

                self.model = cand_model
                self.default_model = cand_model

                return ModelResponse(
                    content=content,
                    model=cand_model,
                    tokens_used=usage.get("total_tokens", 0),
                    latency_ms=latency_ms,
                    cost=cost,
                    provider="groq",
                    finish_reason=data["choices"][0].get("finish_reason"),
                )
            except Exception as e:
                last_error = e
                logger.warning(f"Groq candidate model {cand_model} failed: {e}")
                continue

        raise RuntimeError(f"Groq generation failed after all candidate models: {last_error}")

    async def generate(
        self,
        prompt_or_request: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Generate text using Groq API. Supports both LLMRequest and legacy parameter modes."""
        from providers.core_lib.base import LLMRequest, LLMResponse, TokenUsage
        if isinstance(prompt_or_request, LLMRequest):
            req = prompt_or_request
            prompt_str = req.input if isinstance(req.input, str) else str(req.input)
            # Prefer explicit kwargs; fall back to LLMRequest.output_schema as json_object
            if "response_format" not in kwargs and getattr(req, "output_schema", None):
                kwargs = {**kwargs, "response_format": {"type": "json_object"}}
            if "tools" not in kwargs and getattr(req, "tools", None):
                kwargs = {**kwargs, "tools": req.tools}
            model_resp = await self._execute_generate(
                prompt=prompt_str,
                system_prompt=req.system_prompt,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                model=model or getattr(req, "preferred_model", None),
                **kwargs
            )
            return LLMResponse(
                content=model_resp.content,
                provider=self.name,
                model=model_resp.model,
                tokens_used=model_resp.tokens_used,
                token_usage=TokenUsage(
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=model_resp.tokens_used,
                ),
                latency_ms=model_resp.latency_ms,
                finish_reason=model_resp.finish_reason or "stop",
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
            logger.error(f"Groq streaming failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Groq API health."""
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

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Groq does not offer native embeddings; fallback representation."""
        return [0.0] * 1536

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


__all__ = ["GroqProvider", "GroqConfig", "GROQ_MODELS"]