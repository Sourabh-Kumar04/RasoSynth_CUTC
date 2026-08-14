import pytest
from pipeline.prompt_breeder import PromptBreeder
from pipeline.dspy_optimizer import DSPySignature, SignatureField, DSPyTeleprompter

@pytest.mark.asyncio
async def test_prompt_breeder_evolution():
    breeder = PromptBreeder(router=None, config={"promptbreeder_generations": 2, "promptbreeder_pop_size": 3})
    base = "Generate news dataset samples."
    evolved = await breeder.evolve_prompt(base, target_domain="news", generations=2)
    assert isinstance(evolved, str)
    assert len(evolved) > 0

@pytest.mark.asyncio
async def test_dspy_signature_formatting():
    sig = DSPySignature(
        name="NewsSummarization",
        instructions="Summarize news articles accurately.",
        inputs=[SignatureField("article", "Full news text")],
        outputs=[SignatureField("summary", "Concise summary")]
    )
    formatted = sig.format_prompt({"article": "Breaking news content."})
    assert "NewsSummarization" in formatted
    assert "article: Breaking news content." in formatted
    assert "summary" in formatted
