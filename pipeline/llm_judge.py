"""Real LLM Judge for quality evaluation.

Provides actual LLM-based evaluation of instruction-response pairs,
replacing the heuristic-only placeholder implementation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any

logger = logging.getLogger(__name__)


class JudgeDimension(str, Enum):
    """Evaluation dimensions for the LLM judge."""
    ACCURACY = "accuracy"
    REASONING = "reasoning"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    HELPFULNESS = "helpfulness"
    GROUNDING = "grounding"


# Provider priority order (default)
DEFAULT_PROVIDERS = [
    "nvidia_nim",
    "openai",
    "anthropic",
    "gemini",
    "openrouter",
]


@dataclass(frozen=True)
class JudgeResult:
    """Immutable result from LLM judge evaluation."""
    instruction: str
    response: str
    scores: dict[str, float]  # dimension -> score (0.0 - 1.0)
    overall: float
    provider: str
    model: str
    latency_ms: float
    cached: bool = False
    raw_response: Optional[str] = None

    @property
    def reasoning_score(self) -> float:
        """Get reasoning dimension score."""
        return self.scores.get(JudgeDimension.REASONING.value, 0.5)

    @property
    def accuracy_score(self) -> float:
        """Get accuracy dimension score."""
        return self.scores.get(JudgeDimension.ACCURACY.value, 0.5)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict."""
        return {
            "instruction": self.instruction[:100] + "..." if len(self.instruction) > 100 else self.instruction,
            "response": self.response[:200] + "..." if len(self.response) > 200 else self.response,
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "overall": round(self.overall, 4),
            "provider": self.provider,
            "model": self.model,
            "latency_ms": round(self.latency_ms, 2),
            "cached": self.cached,
        }


# Evaluation prompt template
JUDGE_PROMPT_TEMPLATE = """You are an expert evaluator of training data for large language models.

Rate the following instruction-response pair on the specified dimensions using a 0.0 to 1.0 scale (with one decimal place).

<dimensions>
1. **Accuracy**: Is the information in the response factually correct?
2. **Reasoning**: Does the response show sound logical reasoning?
3. **Completeness**: Does the response fully address the instruction?
4. **Consistency**: Is the response internally consistent (no contradictions)?
5. **Helpfulness**: Would this response be useful to a user?
6. **Grounding**: If source material is provided, is the response grounded in it?
</dimensions>

<scoring_guide>
- 0.0-0.3: Poor - Major issues, unusable
- 0.4-0.6: Fair - Some issues, partially usable
- 0.7-0.8: Good - Minor issues, mostly usable
- 0.9-1.0: Excellent - No issues, high quality
</scoring_guide>

<example>
<instruction>Explain the difference between TCP and UDP.</instruction>
<source_block></source_block>
<response>TCP stands for Transmission Control Protocol. UDP stands for User Datagram Protocol. TCP is connection-oriented, ensuring reliable delivery, while UDP is connectionless and faster but doesn't guarantee delivery.</response>
<output>
{{
  "accuracy": 1.0,
  "reasoning": 0.9,
  "completeness": 0.9,
  "consistency": 1.0,
  "helpfulness": 1.0,
  "grounding": 0.0,
  "explanation": "The response is factually accurate, clearly compares connection-oriented vs connectionless delivery, and is highly helpful."
}}
</example>

<instruction>{instruction}</instruction>

{source_block}

<response>{response}</response>

Return ONLY valid JSON in this exact format (no markdown wrappers, no explanation outside the JSON):
{{
  "accuracy": 0.0,
  "reasoning": 0.0,
  "completeness": 0.0,
  "consistency": 0.0,
  "helpfulness": 0.0,
  "grounding": 0.0,
  "explanation": "One sentence justification"
}}
"""



class JudgeCache:
    """Two-tier cache: memory (hot) → Redis (warm)."""

    def __init__(self, redis_client=None, ttl_seconds: int = 86400):
        self._memory: dict[str, tuple[float, dict]] = {}
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _key(self, instruction: str, response: str, source: str = "") -> str:
        """Content-addressed cache key."""
        content = f"{instruction}\n{response}\n{source}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    async def get(
        self, instruction: str, response: str, source: str = ""
    ) -> Optional[JudgeResult]:
        """Try to get cached result."""
        key = self._key(instruction, response, source)
        now = time.time()

        # Tier 1: Memory cache
        if key in self._memory:
            ts, data = self._memory[key]
            if now - ts < self._ttl:
                self._hits += 1
                data["cached"] = True
                return JudgeResult(**data)
            else:
                del self._memory[key]

        # Tier 2: Redis cache
        if self._redis:
            try:
                cached = await self._redis.get(f"llm_judge:{key}")
                if cached:
                    data = json.loads(cached)
                    self._memory[key] = (now, data)
                    self._hits += 1
                    data["cached"] = True
                    return JudgeResult(**data)
            except Exception as e:
                logger.warning(f"Redis cache get failed: {e}")

        self._misses += 1
        return None

    async def set(self, key: str, result: JudgeResult) -> None:
        """Cache a result."""
        now = time.time()
        data = {
            "instruction": result.instruction,
            "response": result.response,
            "scores": result.scores,
            "overall": result.overall,
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "cached": False,
        }
        self._memory[key] = (now, data)

        if self._redis:
            try:
                await self._redis.setex(
                    f"llm_judge:{key}", self._ttl, json.dumps(data)
                )
            except Exception as e:
                logger.warning(f"Redis cache set failed: {e}")

    def get_stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "memory_keys": len(self._memory),
        }


class LLMJudge:
    """Real LLM-based quality judge with caching and fallback.

    Usage::

        judge = LLMJudge(router=my_router)
        result = await judge.judge(instruction, response, source)
        print(f"Overall: {result.overall}, Reasoning: {result.reasoning_score}")
    """

    def __init__(
        self,
        router=None,
        cache: Optional[JudgeCache] = None,
        providers: Optional[list[str]] = None,
        max_retries: int = 3,
    ):
        self.router = router
        self.cache = cache or JudgeCache()
        self.providers = providers or DEFAULT_PROVIDERS
        self.max_retries = max_retries
        self._costs: dict[str, float] = {p: 0.0 for p in self.providers}
        self._calls: dict[str, int] = {p: 0 for p in self.providers}

    async def judge(
        self,
        instruction: str,
        response: str,
        source: str = "",
        domain: str = "",
    ) -> JudgeResult:
        """Evaluate an instruction-response pair.

        Checks cache first, then tries providers in priority order.
        """
        # Skip evaluation for very short responses
        if len(response) < 20:
            return self._fallback_result(
                instruction, response, "too_short_for_evaluation"
            )

        # Check cache
        cached = await self.cache.get(instruction, response, source)
        if cached:
            return cached

        # Build prompt
        source_block = f"Source material:\n{source}\n\n" if source else ""
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            instruction=instruction[:1500],
            source_block=source_block,
            response=response[:2000],
        )

        # Try providers in order
        for provider_name in self.providers:
            for attempt in range(self.max_retries):
                try:
                    result = await self._call_provider(
                        provider_name, prompt, instruction, response
                    )
                    # Cache and return
                    key = self.cache._key(instruction, response, source)
                    await self.cache.set(key, result)
                    self._costs[provider_name] += result.latency_ms
                    self._calls[provider_name] += 1
                    return result
                except Exception as e:
                    logger.warning(
                        f"Provider {provider_name} attempt {attempt + 1} failed: {e}"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All providers failed - return fallback
        return self._fallback_result(instruction, response, "all_providers_failed")

    async def _call_provider(
        self, provider_name: str, prompt: str, instruction: str, response: str
    ) -> JudgeResult:
        """Call a specific provider and parse the result."""
        start_time = time.time()

        if not self.router:
            raise RuntimeError("No router configured")

        # Route to provider
        result = await self.router.route(
            TaskType.QUALITY_CHECK,
            prompt,
            temperature=0.1,  # Low temperature for consistency
            max_tokens=200,
            response_format={"type": "json_object"},  # Force JSON output
        )

        # Parse JSON response
        content = result.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        try:
            scores_data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract numbers from the response
            scores_data = self._heuristic_parse(content)

        # Extract dimension scores
        scores = {}
        for dim in JudgeDimension:
            scores[dim.value] = self._extract_score(scores_data, dim.value)

        # Calculate overall (weighted average)
        weights = {
            "accuracy": 0.20,
            "reasoning": 0.20,
            "completeness": 0.20,
            "consistency": 0.15,
            "helpfulness": 0.15,
            "grounding": 0.10,
        }
        overall = sum(scores[k] * w for k, w in weights.items())

        latency_ms = (time.time() - start_time) * 1000

        return JudgeResult(
            instruction=instruction,
            response=response,
            scores=scores,
            overall=overall,
            provider=provider_name,
            model=getattr(result, "model", "unknown"),
            latency_ms=latency_ms,
            raw_response=content,
        )

    def _extract_score(self, data: dict, dimension: str) -> float:
        """Extract a score value from parsed JSON."""
        if dimension in data:
            val = data[dimension]
            if isinstance(val, (int, float)):
                return max(0.0, min(1.0, float(val)))
        return 0.5  # Default neutral score

    def _heuristic_parse(self, content: str) -> dict:
        """Try to extract scores from non-JSON response."""
        import re

        scores = {}
        for dim in JudgeDimension:
            # Look for patterns like "accuracy: 0.8" or "accuracy - 0.8"
            pattern = rf'{dim.value}[:\s-]+([0-9.]+)'
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    scores[dim.value] = float(match.group(1))
                except ValueError:
                    pass
        return scores

    def _fallback_result(
        self, instruction: str, response: str, reason: str
    ) -> JudgeResult:
        """Return a fallback result when evaluation is not possible."""
        scores = {dim.value: 0.5 for dim in JudgeDimension}
        return JudgeResult(
            instruction=instruction,
            response=response,
            scores=scores,
            overall=0.5,
            provider="fallback",
            model="none",
            latency_ms=0.0,
            raw_response=reason,
        )

    def get_stats(self) -> dict:
        """Return judge statistics."""
        return {
            "cache": self.cache.get_stats(),
            "provider_costs": dict(self._costs),
            "provider_calls": dict(self._calls),
        }


# Import at end to avoid circular imports
try:
    from core.provider_router import TaskType
    import asyncio
except ImportError:
    TaskType = None
    asyncio = None