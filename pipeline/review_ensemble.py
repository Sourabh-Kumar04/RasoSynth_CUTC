"""Independent LLM review with an explicit human-escalation policy.

Reviewers only receive a candidate and its evidence; they cannot rewrite data.
That keeps every vote auditable and prevents a failed reviewer from silently
changing a training example.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable

from pipeline.llm_judge import DEFAULT_PROVIDERS, JudgeCache, JudgeResult, LLMJudge


@dataclass(frozen=True)
class EnsembleVerdict:
    """A compact, serializable decision from independent automated reviewers."""

    score: float
    consensus: float
    reviewers: tuple[dict[str, Any], ...]
    needs_human_review: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "consensus": self.consensus,
            "reviewers": list(self.reviewers),
            "needs_human_review": self.needs_human_review,
            "reason": self.reason,
        }


class ReviewEnsemble:
    """Run one judge per provider and escalate uncertain candidates to people."""

    def __init__(
        self,
        router: Any,
        providers: Iterable[str] | None = None,
        *,
        approval_threshold: float = 0.75,
        minimum_consensus: float = 0.80,
        max_concurrency: int = 3,
    ) -> None:
        self.router = router
        self.providers = tuple(dict.fromkeys(providers or DEFAULT_PROVIDERS))
        self.approval_threshold = approval_threshold
        self.minimum_consensus = minimum_consensus
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._cache = JudgeCache()

    async def review(
        self,
        instruction: str,
        response: str,
        *,
        source: str = "",
        domain: str = "",
    ) -> EnsembleVerdict:
        async def ask(provider: str) -> JudgeResult:
            async with self._semaphore:
                judge = LLMJudge(
                    router=self.router,
                    cache=self._cache,
                    providers=[provider],
                    max_retries=1,
                )
                return await judge.judge(instruction, response, source, domain)

        results = await asyncio.gather(
            *(ask(provider) for provider in self.providers), return_exceptions=True
        )
        votes = [result for result in results if isinstance(result, JudgeResult) and result.provider != "fallback"]
        reviewer_records = tuple(result.to_dict() for result in votes)

        if not votes:
            return EnsembleVerdict(
                score=0.0,
                consensus=0.0,
                reviewers=reviewer_records,
                needs_human_review=True,
                reason="No configured LLM reviewer returned a usable verdict.",
            )

        scores = [result.overall for result in votes]
        aggregate = float(median(scores))
        # 1.0 represents unanimous reviewers. Range behaves predictably for
        # a two-reviewer panel as well as a larger panel.
        consensus = round(max(0.0, 1.0 - (max(scores) - min(scores))), 4)
        needs_human_review = (
            len(votes) < 2
            or consensus < self.minimum_consensus
            or aggregate < self.approval_threshold
        )
        reason = (
            "Reviewer disagreement or low confidence requires human arbitration."
            if needs_human_review
            else "Independent reviewers reached the configured quality consensus."
        )
        return EnsembleVerdict(
            score=round(aggregate, 4),
            consensus=consensus,
            reviewers=reviewer_records,
            needs_human_review=needs_human_review,
            reason=reason,
        )
