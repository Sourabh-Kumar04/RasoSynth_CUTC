import json

import pytest

from pipeline.review_ensemble import ReviewEnsemble


class _Response:
    model = "review-model"

    def __init__(self, score: float):
        self.content = json.dumps({
            "accuracy": score,
            "reasoning": score,
            "completeness": score,
            "consistency": score,
            "helpfulness": score,
            "grounding": score,
        })


class _Router:
    def __init__(self, scores):
        self.scores = scores
        self.calls = []

    async def route(self, _task, _prompt, **kwargs):
        provider = kwargs["preferred_providers"][0]
        self.calls.append(provider)
        return _Response(self.scores[provider])


@pytest.mark.asyncio
async def test_ensemble_uses_distinct_provider_votes():
    router = _Router({"alpha": 0.9, "beta": 0.7})
    verdict = await ReviewEnsemble(router, providers=["alpha", "beta"]).review(
        "Explain an evidence-backed claim.", "A sufficiently detailed, grounded response.", source="source"
    )

    assert sorted(router.calls) == ["alpha", "beta"]
    assert verdict.score == 0.8
    assert verdict.consensus == 0.8
    assert verdict.needs_human_review is False


@pytest.mark.asyncio
async def test_ensemble_escalates_low_confidence_to_humans():
    router = _Router({"alpha": 0.6, "beta": 0.6})
    verdict = await ReviewEnsemble(router, providers=["alpha", "beta"]).review(
        "Question", "A sufficiently detailed answer for scoring."
    )

    assert verdict.needs_human_review is True
