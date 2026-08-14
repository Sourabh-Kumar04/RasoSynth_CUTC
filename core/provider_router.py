"""Provider router with intelligent routing, self-improvement, and latest 2026 techniques."""
import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Optional, Any
from dataclasses import dataclass, field


from providers.core_lib.base import (
    TaskType,
    ProviderHealth,
    ModelMetadata,
)
from providers.core_lib.plugin import PluginRegistry, AbstractProviderPlugin


@dataclass
class RouterConfig:
    """Router configuration with self-improvement settings."""
    provider_priority: list[str] = field(default_factory=lambda: [
        "huggingface", "google_gemini", "anthropic", "groq", "nvidia_nim", "ollama", "vllm"
    ])
    max_retries: int = 1
    retry_base_delay: float = 2.0
    retry_max_delay: float = 60.0
    cache_ttl: int = 3600
    enable_caching: bool = True
    enable_self_improvement: bool = True
    health_reset_after_seconds: int = 300  # 5 minutes


@dataclass
class RouterStats:
    """Comprehensive router statistics."""
    provider: str
    requests: int = 0
    failures: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    success_rate: float = 1.0


class TechniqueKnowledge:
    """Knowledge base of latest techniques for self-improvement."""

    LATEST_2026_TECHNIQUES = {
        "deduplication": [
            "MinHash with LSH for scalable semantic dedup",
            "SimHash for near-duplicate detection at scale",
            "Neural embeddings for semantic dedup",
            "Multi-stage dedup: exact -> ngram -> semantic"
        ],
        "quality_filtering": [
            "Perplexity-based quality scoring",
            "LLM-based quality assessment with reasoning",
            "Multi-dimensional quality vectors",
            "Adaptive threshold learning from data distribution"
        ],
        "synthetic_augmentation": [
            "Self-instruct for instruction generation",
            "Back-translation for multilingual augmentation",
            "Evolutionary prompting for diverse synthetics",
            "Quality-weighted synthetic sample selection"
        ],
        "multilingual": [
            "Cross-lingual embedding alignment",
            "Code-switching detection and handling",
            "Historical text normalization",
            "OCR artifact correction with language models"
        ],
        "data_selection": [
            "Diversity-aware sampling",
            "Curriculum learning ordering",
            "Active learning for quality improvement",
            "Difficulty-based stratification"
        ],
        "evaluation": [
            "LLM-as-judge for quality assessment",
            "Benchmark-based model selection",
            "Cross-validation for dataset quality",
            "Statistical significance testing"
        ]
    }

    BENCHMARKS = {
        "quality": "MMLU, HellaSwag, TruthfulQA",
        "reasoning": "GSM8K, MATH, ARC-Challenge",
        "coding": "HumanEval, MBPP, BigCodeBench",
        "multilingual": "XGLUE, XTREME, Flores-200"
    }

    def get_technique_for_task(self, task: TaskType) -> list[str]:
        """Get relevant techniques for a task."""
        mapping = {
            TaskType.QUALITY_CHECK: "quality_filtering",
            TaskType.HALLUCINATION_DETECTION: "quality_filtering",
            TaskType.EMBEDDING: "deduplication",
            TaskType.SYNTHETIC_GENERATION: "synthetic_augmentation",
            TaskType.TRANSLATION: "multilingual",
            TaskType.OCR_CORRECTION: "multilingual",
            TaskType.SEMANTIC_SEARCH: "data_selection",
        }
        category = mapping.get(task, "data_selection")
        return self.LATEST_2026_TECHNIQUES.get(category, [])


class ProviderRouter:
    """Intelligent provider router with self-improvement and research capabilities."""

    # Enhanced task-provider mapping with optimal routing
    TASK_PROVIDER_MAPPING = {
        TaskType.TEXT_GENERATION: ["huggingface", "nvidia_nim", "google_gemini", "ollama"],
        TaskType.EMBEDDING: ["huggingface", "nvidia_nim", "ollama"],
        TaskType.QUALITY_CHECK: ["huggingface", "google_gemini"],
        TaskType.HALLUCINATION_DETECTION: ["huggingface", "google_gemini"],
        TaskType.TOXICITY_CHECK: ["huggingface", "google_gemini"],
        TaskType.SUMMARIZATION: ["huggingface", "google_gemini"],
        TaskType.PARAPHRASING: ["huggingface", "google_gemini"],
        TaskType.CODE_GENERATION: ["huggingface", "google_gemini"],
        TaskType.REASONING: ["huggingface", "google_gemini"],
        TaskType.MULTIMODAL: ["google_gemini", "huggingface"],
        TaskType.OCR_CORRECTION: ["huggingface", "google_gemini"],
        TaskType.TRANSLATION: ["huggingface", "google_gemini"],
        TaskType.SCHEMA_INFERENCE: ["huggingface", "google_gemini"],
        TaskType.SYNTHETIC_GENERATION: ["huggingface", "google_gemini"],
        TaskType.NORMALIZATION: ["huggingface", "google_gemini"],
        TaskType.ENTITY_EXTRACTION: ["huggingface", "google_gemini"],
    }

    def __init__(self, config: dict[str, Any]):
        self.config = RouterConfig()
        self.stats: dict[str, RouterStats] = {}
        self.cache: OrderedDict = OrderedDict()
        self.cache_max_size = 10000
        self.cache_hits: dict[str, int] = {}
        self.cache_misses: dict[str, int] = {}
        self.knowledge = TechniqueKnowledge()
        self._providers: dict[str, AbstractProviderPlugin] = {}
        self._provider_configs: dict[str, dict] = {}
        self._success_rates: dict[str, list[bool]] = {}
        # Synchronously register providers without awaiting initialize().
        # Call await router.initialize() from the async lifespan handler.
        self._provider_last_failure: dict[str, float] = {}
        self._register_providers(config)

    def _register_providers(self, config: dict[str, Any]):
        """Instantiate provider objects and store their configs — no I/O performed here."""
        from providers import PluginRegistry

        # Map config keys to provider IDs
        provider_keys = {
            "google_api_key": "google_gemini",
            "nvidia_api_key": "nvidia_nim",
            "anthropic_api_key": "anthropic",
            "openai_api_key": "openai",
            "hf_token": "huggingface",
            "ollama_base_url": "ollama",
            "vllm_base_url": "vllm",
            "xai_api_key": "xai",
            "groq_api_key": "groq",
            "featherless_api_key": "featherless",
        }

        for key, provider_id in provider_keys.items():
            api_key = config.get(key, "")
            if api_key:
                try:
                    provider_class = PluginRegistry.get(provider_id)
                    if provider_class:
                        provider = provider_class()
                        self._providers[provider_id] = provider
                        self._provider_configs[provider_id] = {
                            "api_key": api_key,
                            "base_url": config.get(f"{provider_id}_base_url"),
                            "timeout": config.get("timeout", 60),
                        }
                        self.stats[provider_id] = RouterStats(provider=provider_id)
                        self._success_rates[provider_id] = []
                except Exception as e:
                    print(f"Failed to register {provider_id}: {e}")

        # Register unconfigured providers so they appear in the registry
        for provider_id in PluginRegistry.list_providers():
            if provider_id not in self._providers:
                try:
                    provider_class = PluginRegistry.get(provider_id)
                    if provider_class:
                        provider = provider_class()
                        self._providers[provider_id] = provider
                        self.stats[provider_id] = RouterStats(provider=provider_id)
                        self._success_rates[provider_id] = []
                except Exception:
                    pass

    async def initialize(self):
        """Async provider initialization — must be awaited from the app lifespan."""
        import logging
        _log = logging.getLogger(__name__)
        failed: list[str] = []
        for provider_id, provider in list(self._providers.items()):
            provider_config = self._provider_configs.get(provider_id)
            if not provider_config:
                continue  # unconfigured stubs — skip
            try:
                await provider.initialize(provider_config)
            except Exception as e:
                _log.warning(f"Failed to initialize provider '{provider_id}': {e}")
                failed.append(provider_id)
        return {"initialized": list(self._provider_configs.keys()), "failed": failed}

    def _get_cache_key(self, provider: str, prompt: str, **kwargs) -> str:
        """Generate cache key."""
        data = json.dumps({"provider": provider, "prompt": prompt, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def _get_cached(self, cache_key: str, provider_name: str = "") -> Optional[Any]:
        """Get cached response if valid."""
        if not self.config.enable_caching:
            return None

        if cache_key in self.cache:
            timestamp, response = self.cache[cache_key]
            if time.time() - timestamp < self.config.cache_ttl:
                # Cache hit — bump to end (most recently used)
                self.cache.move_to_end(cache_key)
                if provider_name:
                    self.cache_hits[provider_name] = self.cache_hits.get(provider_name, 0) + 1
                return response
            else:
                del self.cache[cache_key]
        if provider_name:
            self.cache_misses[provider_name] = self.cache_misses.get(provider_name, 0) + 1
        return None

    def _set_cached(self, cache_key: str, response: Any):
        """Cache a response with LRU eviction."""
        if self.config.enable_caching:
            if len(self.cache) >= self.cache_max_size:
                self.cache.popitem(last=False)  # Remove oldest (LRU)
            self.cache[cache_key] = (time.time(), response)

    async def route(
        self,
        task: TaskType,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        preferred_providers: list[str] | None = None,
        context: dict | None = None,
        **kwargs
    ) -> Optional[Any]:
        """Route request with intelligent selection and fallback."""
        from providers.core_lib.base import LLMRequest

        providers = preferred_providers or self.TASK_PROVIDER_MAPPING.get(
            task, self.config.provider_priority
        )

        last_error = None
        logger = logging.getLogger(__name__)
        logger.info("Routing task %s. Preferred: %s. Providers list: %s", task, preferred_providers, providers)
        bypass_cache = kwargs.pop("bypass_cache", False)

        for provider_name in providers:
            provider = self._providers.get(provider_name)
            if not provider:
                continue
            # Circuit breaker: skip unhealthy providers (with health reset after time)
            health = self._success_rates.get(provider_name, [])
            if len(health) >= 3:
                recent_failures = sum(1 for s in health[-10:] if not s)
                if recent_failures >= 7:  # 70% failure rate threshold
                    # Check if enough time has passed since last failure to reset health
                    if hasattr(self, '_provider_last_failure'):
                        last_failure_time = self._provider_last_failure.get(provider_name, 0)
                        if time.time() - last_failure_time < self.config.health_reset_after_seconds:
                            logger.warning(
                                "Skipping unhealthy provider %s: %d/%d recent failures",
                                provider_name, recent_failures, min(len(health), 10),
                            )
                            continue
                        else:
                            # Health reset: clear failure history
                            logger.info(
                                "Provider %s: health reset after %d seconds",
                                provider_name, self.config.health_reset_after_seconds
                            )
                            self._success_rates[provider_name] = []
                    else:
                        # Initialize failure tracking for this provider
                        self._provider_last_failure[provider_name] = 0
                        # Proceed with this request - we have no failure history to judge yet
                    self._provider_last_failure[provider_name] = 0
                    # Proceed with this request - we have no failure history to judge yet

            cache_key = None
            cached = None
            if not bypass_cache:
                cache_key = self._get_cache_key(
                    provider_name, prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                cached = self._get_cached(cache_key, provider_name=provider_name)
            if cached:
                return cached

            for attempt in range(self.config.max_retries):
                try:
                    start_time = time.time()

                    request = LLMRequest(
                        input=prompt,
                        task_type=task,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens or 4096,
                    )

                    response = await provider.generate(request)

                    latency = (time.time() - start_time) * 1000
                    self._update_stats(provider_name, response, latency, success=True)
                    self._record_success(provider_name, True)
                    if not bypass_cache and cache_key:
                        self._set_cached(cache_key, response)
                    return response

                except Exception as e:
                    logger.warning("Provider %s failed with exception: %s", provider_name, e, exc_info=True)
                    last_error = e
                    self._record_success(provider_name, False)

                    if attempt < self.config.max_retries - 1:
                        delay = min(
                            self.config.retry_base_delay ** attempt,
                            self.config.retry_max_delay
                        )
                        await asyncio.sleep(delay + (time.time() % 1))
                        
                    continue
                    
        return None
    async def embed(
        self,
        text: str,
        provider_hint: str | None = None,
        task_type: TaskType = TaskType.EMBEDDING
    ) -> Optional[list[float]]:
        """Route embedding request to optimal provider."""
        providers = ["nvidia_nim", "openai", "huggingface", "ollama"]
        if provider_hint:
            providers = [provider_hint] + [p for p in providers if p != provider_hint]

        for provider_name in providers:
            provider = self._providers.get(provider_name)
            if not provider:
                continue

            try:
                if hasattr(provider, 'embed'):
                    return await provider.embed(text)
            except Exception:
                continue

        return None

    def _update_stats(self, provider_name: str, response: Any, latency: float, success: bool):
        """Update router statistics."""
        if provider_name in self.stats:
            stats = self.stats[provider_name]
            stats.requests += 1
            stats.total_latency_ms += latency
            stats.avg_latency_ms = stats.total_latency_ms / stats.requests

            if hasattr(response, 'tokens_used'):
                stats.total_tokens += response.tokens_used
            if hasattr(response, 'token_usage'):
                if hasattr(response.token_usage, 'total_tokens'):
                    stats.total_cost += (response.token_usage.total_tokens / 1000) * 0.0001

    def _record_success(self, provider_name: str, success: bool):
        """Record success/failure for adaptive routing."""
        if provider_name not in self._success_rates:
            self._success_rates[provider_name] = []
            self._provider_last_failure[provider_name] = 0

        self._success_rates[provider_name].append(success)

        # Track failure timestamps for health reset
        if not success:
            self._provider_last_failure[provider_name] = time.time()

        if len(self._success_rates[provider_name]) > 100:
            self._success_rates[provider_name] = self._success_rates[provider_name][-100:]

        if provider_name in self.stats:
            recent = self._success_rates[provider_name]
            self.stats[provider_name].success_rate = sum(recent) / len(recent)

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive router statistics."""
        return {
            name: {
                "requests": s.requests,
                "failures": len([r for r in self._success_rates.get(name, []) if not r]),
                "total_tokens": s.total_tokens,
                "total_cost_usd": s.total_cost,
                "avg_latency_ms": s.avg_latency_ms,
                "success_rate": s.success_rate,
                "cache_hit_rate": s.cache_hits / max(s.cache_hits + s.cache_misses, 1),
            }
            for name, s in self.stats.items()
        }

    def get_healthy_providers(self) -> list[str]:
        """Get list of healthy providers based on recent success rate."""
        healthy = []
        for name in self.config.provider_priority:
            if name in self._success_rates:
                recent = self._success_rates[name][-10:]
                success_rate = sum(recent) / len(recent) if recent else 0
                if success_rate >= 0.7:
                    healthy.append(name)
            else:
                provider = self._providers.get(name)
                if provider:
                    healthy.append(name)

        return healthy

    async def test_provider(self, provider_name: str) -> bool:
        """Test a specific provider."""
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not found")

        try:
            from providers.core_lib.base import LLMRequest
            request = LLMRequest(input="Hello", task_type=TaskType.TEXT_GENERATION, max_tokens=5)
            response = await provider.generate(request)
            self._record_success(provider_name, len(response.content) > 0)
            return len(response.content) > 0
        except Exception:
            self._record_success(provider_name, False)
            return False

    def get_techniques_for_task(self, task: TaskType) -> dict:
        """Get latest techniques for a task type."""
        return {
            "techniques": self.knowledge.get_technique_for_task(task),
            "benchmarks": self.knowledge.BENCHMARKS,
        }

    def suggest_pipeline_optimization(self, task_type: TaskType, stats: dict) -> dict:
        """Suggest pipeline optimizations based on task and stats."""
        suggestions = []

        for provider, p_stats in stats.items():
            if p_stats.get("success_rate", 1) < 0.8:
                suggestions.append(f"Provider {provider} has low success rate - consider fallback")

            if p_stats.get("avg_latency_ms", 0) > 2000:
                suggestions.append(f"Provider {provider} has high latency - consider optimization")

        if task_type == TaskType.EMBEDDING:
            if stats.get("nvidia_nim", {}).get("avg_latency_ms", 0) > 500:
                suggestions.append("Consider using smaller embedding model for speed")

        if task_type == TaskType.QUALITY_CHECK:
            if stats.get("anthropic", {}).get("total_cost_usd", 0) > 10:
                suggestions.append("Quality checks are expensive - consider batching")

        return {
            "suggestions": suggestions,
            "recommended_techniques": self.knowledge.get_technique_for_task(task_type),
        }

    def get_learning_summary(self) -> dict:
        """Get learning summary from self-improvement."""
        provider_health = {}
        for name in self._success_rates:
            recent = self._success_rates[name][-20:]
            provider_health[name] = {
                "success_rate": sum(recent) / len(recent) if recent else 0,
                "requests": len(recent),
                "status": "healthy" if sum(recent) / len(recent) > 0.7 else "degraded" if recent else "unknown"
            }

        return {
            "provider_health": provider_health,
            "techniques_learned": sum(len(v) for v in self.knowledge.LATEST_2026_TECHNIQUES.values()),
            "cache_size": len(self.cache),
        }

    def list_providers(self) -> list[str]:
        """List all registered providers."""
        return list(self._providers.keys())

    def get_provider(self, name: str) -> AbstractProviderPlugin | None:
        """Get a provider by name."""
        return self._providers.get(name)