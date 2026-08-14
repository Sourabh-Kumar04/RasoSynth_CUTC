"""Provider health validation at startup and runtime."""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderHealth(str, Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNCONFIGURED = "unconfigured"


@dataclass
class ProviderValidationResult:
    """Result of provider validation."""
    provider: str
    status: ProviderHealth
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    validated_at: datetime = field(default_factory=datetime.utcnow)


class ProviderValidator:
    """Validates provider configurations and health at startup."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_results: Dict[str, ProviderValidationResult] = {}

    async def validate_all_providers(self) -> Dict[str, ProviderValidationResult]:
        """Validate all configured providers."""
        results = {}

        # Check each provider configuration
        providers_to_check = [
            ("google_gemini", "google_api_key", "GOOGLE_API_KEY", self._validate_gemini),
            ("anthropic", "anthropic_api_key", "ANTHROPIC_API_KEY", self._validate_anthropic),
            ("openai", "openai_api_key", "OPENAI_API_KEY", self._validate_openai),
            ("nvidia", "nvidia_api_key", "NVIDIA_API_KEY", self._validate_nvidia),
            ("huggingface", "hf_token", "HF_TOKEN", self._validate_huggingface),
            ("ollama", "ollama_base_url", "OLLAMA_BASE_URL", self._validate_ollama),
        ]

        for provider_name, config_key, env_var, validator in providers_to_check:
            api_key = self.config.get(config_key)
            base_url = self.config.get(f"{provider_name}_base_url")

            if not api_key:
                results[provider_name] = ProviderValidationResult(
                    provider=provider_name,
                    status=ProviderHealth.UNCONFIGURED,
                    error=f"{env_var} not set in config"
                )
                logger.warning(f"Provider {provider_name}: {env_var} not configured")
                continue

            try:
                result = await asyncio.wait_for(
                    validator(api_key, base_url),
                    timeout=10.0
                )
                results[provider_name] = result
                logger.info(f"Provider {provider_name}: {result.status.value}")
            except asyncio.TimeoutError:
                results[provider_name] = ProviderValidationResult(
                    provider=provider_name,
                    status=ProviderHealth.UNAVAILABLE,
                    error="Validation timed out"
                )
                logger.error(f"Provider {provider_name}: validation timed out")
            except Exception as e:
                results[provider_name] = ProviderValidationResult(
                    provider=provider_name,
                    status=ProviderHealth.UNAVAILABLE,
                    error=str(e)
                )
                logger.error(f"Provider {provider_name}: validation failed - {e}")

        self.validation_results = results
        return results

    async def _validate_gemini(self, api_key: str, base_url: Optional[str]) -> ProviderValidationResult:
        """Validate Google Gemini configuration."""
        import time
        import random
        start = time.time()

        try:
            import google.genai as genai

            # Stagger to avoid 429 when multiple workers validate at once
            await asyncio.sleep(random.uniform(0, 2))

            client = genai.Client(api_key=api_key)
            client.models.generate_content(
                model="gemini-2.0-flash",
                contents="hi",
                config=genai.types.GenerateContentConfig(max_output_tokens=1),
            )
            latency_ms = (time.time() - start) * 1000

            return ProviderValidationResult(
                provider="google_gemini",
                status=ProviderHealth.HEALTHY,
                latency_ms=latency_ms
            )
        except Exception as e:
            error_str = str(e)
            status = ProviderHealth.DEGRADED if "429" in error_str or "Too Many Requests" in error_str else ProviderHealth.UNAVAILABLE
            return ProviderValidationResult(
                provider="google_gemini",
                status=status,
                error=error_str
            )

    async def _validate_anthropic(self, api_key: str, base_url: Optional[str]) -> ProviderValidationResult:
        """Validate Anthropic Claude configuration."""
        import time
        start = time.time()

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)

            # Quick test - minimal request
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}]
            )
            latency_ms = (time.time() - start) * 1000

            return ProviderValidationResult(
                provider="anthropic",
                status=ProviderHealth.HEALTHY,
                latency_ms=latency_ms
            )
        except Exception as e:
            return ProviderValidationResult(
                provider="anthropic",
                status=ProviderHealth.UNAVAILABLE,
                error=str(e)
            )

    async def _validate_openai(self, api_key: str, base_url: Optional[str]) -> ProviderValidationResult:
        """Validate OpenAI configuration."""
        import time
        start = time.time()

        try:
            import openai
            client = openai.OpenAI(api_key=api_key)

            # Quick test
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}]
            )
            latency_ms = (time.time() - start) * 1000

            return ProviderValidationResult(
                provider="openai",
                status=ProviderHealth.HEALTHY,
                latency_ms=latency_ms
            )
        except Exception as e:
            return ProviderValidationResult(
                provider="openai",
                status=ProviderHealth.UNAVAILABLE,
                error=str(e)
            )

    async def _validate_nvidia(self, api_key: str, base_url: Optional[str]) -> ProviderValidationResult:
        """Validate NVIDIA NIM configuration."""
        import time
        start = time.time()

        try:
            import httpx
            base = base_url or "https://integrate.api.nvidia.com/v1"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "meta/llama-3.1-8b-instruct",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1
                    },
                    timeout=10.0
                )
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    return ProviderValidationResult(
                        provider="nvidia",
                        status=ProviderHealth.HEALTHY,
                        latency_ms=latency_ms
                    )
                else:
                    return ProviderValidationResult(
                        provider="nvidia",
                        status=ProviderHealth.DEGRADED,
                        error=f"Status {response.status_code}"
                    )
        except Exception as e:
            return ProviderValidationResult(
                provider="nvidia",
                status=ProviderHealth.UNAVAILABLE,
                error=str(e)
            )

    async def _validate_huggingface(self, token: str, base_url: Optional[str]) -> ProviderValidationResult:
        """Validate HuggingFace configuration."""
        import time
        start = time.time()

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://huggingface.co/api/whoami-v2",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    return ProviderValidationResult(
                        provider="huggingface",
                        status=ProviderHealth.HEALTHY,
                        latency_ms=latency_ms
                    )
                else:
                    return ProviderValidationResult(
                        provider="huggingface",
                        status=ProviderHealth.DEGRADED,
                        error=f"Status {response.status_code}"
                    )
        except Exception as e:
            return ProviderValidationResult(
                provider="huggingface",
                status=ProviderHealth.UNAVAILABLE,
                error=str(e)
            )

    async def _validate_ollama(self, api_key: str, base_url: Optional[str]) -> ProviderValidationResult:
        """Validate Ollama local configuration."""
        import time
        start = time.time()

        try:
            import httpx
            base = base_url or "http://localhost:11434"

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base}/api/tags", timeout=5.0)
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    return ProviderValidationResult(
                        provider="ollama",
                        status=ProviderHealth.HEALTHY,
                        latency_ms=latency_ms
                    )
                else:
                    return ProviderValidationResult(
                        provider="ollama",
                        status=ProviderHealth.DEGRADED,
                        error=f"Status {response.status_code}"
                    )
        except Exception as e:
            return ProviderValidationResult(
                provider="ollama",
                status=ProviderHealth.UNAVAILABLE,
                error=f"Ollama not running at {base_url or 'localhost:11434'}"
            )

    def get_healthy_providers(self) -> List[str]:
        """Get list of healthy provider names."""
        return [
            name for name, result in self.validation_results.items()
            if result.status == ProviderHealth.HEALTHY
        ]

    def get_provider_status(self) -> Dict[str, str]:
        """Get status of all providers."""
        return {
            name: result.status.value
            for name, result in self.validation_results.items()
        }

    def is_any_provider_available(self) -> bool:
        """Check if at least one provider is available."""
        return any(
            result.status in [ProviderHealth.HEALTHY, ProviderHealth.DEGRADED]
            for result in self.validation_results.values()
        )