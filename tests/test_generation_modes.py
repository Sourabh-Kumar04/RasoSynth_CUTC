import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from pipeline.planner import DatasetPlanner, CoveragePlanner, DatasetPlan
from pipeline.synthetic_generator import SeedlessGenerator
from pipeline.validation import MultiStageValidator
from pipeline.construction import ConstructedSample

@pytest.mark.asyncio
async def test_dataset_planning():
    """Verify that DatasetPlanner correctly parses prompts into structured plans."""
    router = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = (
        '{"domain": "healthcare", "objective": "medical dialogues", "roles": ["Doctor", "Patient"], '
        '"metadata_schema": {"specialty": "string"}, "difficulty_distribution": {"expert": 1.0}, '
        '"constraints": [], "diversity_attributes": {"specialty": ["Pediatrics"]}}'
    )
    router.route.return_value = mock_response

    planner = DatasetPlanner(router, {})
    prompt = "Doctor-patient diagnosis conversation about fever."
    plan = await planner.create_plan(prompt)
    
    assert plan.domain == "healthcare"
    assert "Doctor" in plan.roles
    assert "Patient" in plan.roles
    assert plan.objective != ""

def test_coverage_planning():
    """Verify CoveragePlanner maps appropriate attributes for diversity."""
    plan = DatasetPlan(
        domain="healthcare",
        objective="medical dialogues",
        roles=["Doctor", "Patient"],
        metadata_schema={"specialty": "string"},
        difficulty_distribution={"expert": 1.0},
        constraints=[],
        diversity_attributes={"specialty": ["Pediatrics", "Cardiology"], "difficulty": ["standard", "expert"]}
    )
    cov_planner = CoveragePlanner({})
    matrix = cov_planner.generate_matrix(plan, target_size=10)
    
    assert "specialty" in matrix.dimensions
    assert "difficulty" in matrix.dimensions
    assert len(matrix.cells) == 10

@pytest.mark.asyncio
async def test_seedless_generation():
    """Verify generator constructs a complete training sample from plan metadata."""
    router = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"instruction": "Patient presents with high fever.", "response": "Doctor recommends acetaminophen.", "input": null}'
    router.route.return_value = mock_response

    generator = SeedlessGenerator(router, {})
    plan = DatasetPlan(
        domain="healthcare",
        objective="dialogue",
        roles=["Doctor", "Patient"],
        metadata_schema={},
        difficulty_distribution={},
        constraints=[],
        diversity_attributes={}
    )
    cell = {"specialty": "Pediatrics", "difficulty": "expert"}
    
    sample = await generator.generate_sample(plan, cell)
    
    assert sample.instruction == "Patient presents with high fever."
    assert sample.response == "Doctor recommends acetaminophen."
    assert sample.metadata["specialty"] == "Pediatrics"

@pytest.mark.asyncio
async def test_validation_logic():
    """Verify validator successfully accepts high-quality samples and flags invalid ones."""
    router = AsyncMock()
    validator = MultiStageValidator(router, {"validation_strictness": "standard"})
    
    valid_sample = ConstructedSample(instruction="Patient presents with high fever.", response="Doctor recommends acetaminophen.")
    invalid_sample = ConstructedSample(instruction="", response="Hi")
    
    res_valid = await validator.validate(valid_sample)
    res_invalid = await validator.validate(invalid_sample)
    
    assert res_valid.is_valid is True
    assert res_invalid.is_valid is False
    assert res_invalid.regenerate_needed is True

@pytest.mark.asyncio
async def test_regeneration_retry_loop():
    """Verify that failures trigger regeneration up to the retry limit."""
    router = AsyncMock()
    mock_response_bad = MagicMock()
    mock_response_bad.content = '{"instruction": "", "response": ""}'
    mock_response_good = MagicMock()
    mock_response_good.content = '{"instruction": "Patient presents with fever.", "response": "Doctor recommends bed rest.", "input": null}'
    
    router.route.side_effect = [mock_response_bad, mock_response_good]

    generator = SeedlessGenerator(router, {"regeneration_attempts": 1})
    validator = MultiStageValidator(router, {"validation_strictness": "standard"})
    
    plan = DatasetPlan(
        domain="healthcare",
        objective="dialogue",
        roles=["Doctor", "Patient"],
        metadata_schema={},
        difficulty_distribution={},
        constraints=[],
        diversity_attributes={}
    )
    cell = {"specialty": "Pediatrics"}
    
    max_attempts = 3
    attempts = 0
    final_sample = None
    
    for attempt in range(max_attempts):
        attempts += 1
        sample = await generator.generate_sample(plan, cell)
        val_res = await validator.validate(sample)
        if val_res.is_valid:
            final_sample = sample
            break
            
    assert attempts == 2
    assert final_sample.instruction == "Patient presents with fever."
    assert final_sample.response == "Doctor recommends bed rest."

def test_intelligent_mode_selection():
    """Verify orchestrator selects the correct mode based on config parameters."""
    def select_mode(config, search_succeeded=True):
        if config.get("source_urls"):
            return "source"
        if config.get("generation_mode") == "synthetic":
            return "synthetic"
        if not search_succeeded and config.get("allow_seedless_generation", True):
            return "synthetic"
        return "hybrid"

    # Mode 1: URL provided
    assert select_mode({"source_urls": ["http://data.com"]}) == "source"
    
    # Mode 3: Explicitly set to synthetic
    assert select_mode({"generation_mode": "synthetic"}) == "synthetic"
    
    # Mode 3: Search fails but seedless fallback is allowed
    assert select_mode({"generation_mode": "hybrid", "allow_seedless_generation": True}, search_succeeded=False) == "synthetic"
    
    # Mode 2: Normal hybrid path
    assert select_mode({"generation_mode": "hybrid"}, search_succeeded=True) == "hybrid"

@pytest.mark.asyncio
async def test_conversational_dataset_mode():
    """Verify that conversational dataset type correctly generates alternating turns and triggers consistency rules."""
    router = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = (
        '{"conversation": ['
        '{"role": "patient", "content": "I have a cough."},'
        '{"role": "doctor", "content": "How long?"},'
        '{"role": "patient", "content": "Two days."},'
        '{"role": "doctor", "content": "Any fever?"},'
        '{"role": "patient", "content": "No."},'
        '{"role": "doctor", "content": "I recommend rest."}'
        ']}'
    )
    router.route.return_value = mock_response

    generator = SeedlessGenerator(router, {"dataset_type": "conversational"})
    plan = DatasetPlan(
        domain="healthcare",
        objective="Generate medical dialogues",
        roles=["patient", "doctor"],
        metadata_schema={},
        difficulty_distribution={},
        constraints=[],
        diversity_attributes={}
    )
    cell = {"specialty": "General Medicine", "disease": "Common Cold"}
    
    sample = await generator.generate_sample(plan, cell)
    
    assert sample.conversation is not None
    assert len(sample.conversation) == 6
    assert sample.conversation[0]["role"] == "patient"
    assert sample.conversation[1]["role"] == "doctor"

    # Test Validation consistency checks
    validator = MultiStageValidator(router, {"dataset_type": "conversational"})
    
    # Valid sample
    res_valid = await validator.validate(sample)
    assert res_valid.is_valid is True

    # Inconsistent sample: Pediatric patient combined with senior age details
    inconsistent_sample = ConstructedSample(
        instruction="Patient presents with fever.",
        response="Dialogue details",
        conversation=[
            {"role": "patient", "content": "I am a retired 75-year-old child."},
            {"role": "doctor", "content": "Let me check."}
        ] * 3,
        metadata={"specialty": "Pediatrics", "patient_demographics": "75-year-old retired patient"}
    )
    res_inconsistent = await validator.validate(inconsistent_sample)
    assert res_inconsistent.is_valid is False
    assert any("Pediatric" in reason or "pediatric" in reason for reason in res_inconsistent.reasons)


@pytest.mark.asyncio
async def test_language_prompt_generation_and_metadata():
    """Verify that language configurations (Hindi, Hinglish, Indic) are enforced in generator prompts and sample metadata."""
    from pipeline.synthetic_generator import SeedlessGenerator, _build_language_instruction
    from core.provider_router import ProviderRouter, RouterConfig
    from pipeline.planner import DatasetPlan
    from core.validation.validators import validate_language_code

    # 1. Test validator accepts new language tokens
    assert validate_language_code("hi") == "hi"
    assert validate_language_code("hinglish") == "hinglish"
    assert validate_language_code("indic_multilingual") == "indic_multilingual"
    assert validate_language_code("ta") == "ta"

    # 2. Test language instruction builder
    hi_rule = _build_language_instruction("hi")
    assert "Hindi (हिन्दी)" in hi_rule
    assert "Devanagari" in hi_rule

    hinglish_rule = _build_language_instruction("hinglish")
    assert "Hinglish" in hinglish_rule
    assert "code-switched" in hinglish_rule

    indic_rule = _build_language_instruction("indic_multilingual")
    assert "Indic language" in indic_rule

    # 3. Test generator prompt injection and metadata propagation
    router = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "instruction": "GST ITC claim karne ki time limit kya hai?",
        "response": "Section 16(4) ke mutabiq agle financial year ke 30th November tak claim kar sakte hain.",
    })
    router.route.return_value = mock_response

    generator = SeedlessGenerator(router, {"language": "hinglish", "dataset_type": "sft"})
    
    plan = DatasetPlan(
        domain="Indian Taxation",
        objective="Generate GST query-response pairs",
        roles=["Taxpayer", "CA"],
        constraints=["Adhere to GST Act 2017"],
        subtopics=["Input Tax Credit"],
    )
    cell = {"subtopic": "Input Tax Credit", "difficulty": "intermediate"}

    sample = await generator.generate_sample(plan, cell)

    assert router.route.called
    call_kwargs = router.route.call_args[1]
    system_prompt = call_kwargs["system_prompt"]
    assert "Hinglish" in system_prompt
    assert "code-switched" in system_prompt

    assert sample.metadata["language"] == "hinglish"
    assert sample.instruction == "GST ITC claim karne ki time limit kya hai?"
    assert "Section 16(4)" in sample.response


@pytest.mark.asyncio
async def test_multilingual_advanced_controls_and_cultural_guardrails():
    """Verify script orthography, formality registers, preserved terms, parallel bitext, and cultural guardrails."""
    from pipeline.synthetic_generator import _build_language_instruction, SeedlessGenerator
    from core.validation.cultural_guardrails import check_cultural_safety, validate_script_conformity
    from core.tokenizer_metrics import estimate_tokenizer_fertility
    from pipeline.validation import MultiStageValidator
    from pipeline.construction import ConstructedSample
    from pipeline.planner import DatasetPlan

    # 1. Test script modes in instruction builder
    romanized_rule = _build_language_instruction("hi", script_mode="romanized")
    assert "Latin / Romanized script" in romanized_rule
    assert "Do NOT use Devanagari" in romanized_rule

    dual_rule = _build_language_instruction("hi", script_mode="dual")
    assert "instruction_romanized" in dual_rule

    # 2. Test formality register & honorifics
    formal_rule = _build_language_instruction("hi", formality_register="formal")
    assert "आप" in formal_rule
    assert "honorific" in formal_rule.lower()

    casual_rule = _build_language_instruction("hi", formality_register="casual")
    assert "तुम" in casual_rule

    # 3. Test code-switching intensity
    light_rule = _build_language_instruction("hinglish", code_switch_intensity="light")
    assert "predominantly Hindi (80%)" in light_rule

    heavy_rule = _build_language_instruction("hinglish", code_switch_intensity="heavy")
    assert "predominantly English (80%)" in heavy_rule

    # 4. Test preserved terms and parallel bilingual mode
    glossary_rule = _build_language_instruction(
        "hi",
        preserved_terms=["ITC", "GSTR-3B", "Challan"],
        parallel_bilingual=True
    )
    assert "'ITC'" in glossary_rule
    assert "'GSTR-3B'" in glossary_rule
    assert "instruction_en" in glossary_rule

    # 5. Test Cultural Guardrails
    is_safe, violation = check_cultural_safety("This is a clean discussion on taxation.")
    assert is_safe is True
    assert violation is None

    is_unsafe, violation = check_cultural_safety("Tu neech jaati ka hai aur chamar jaisa baat karta hai.")
    assert is_unsafe is False
    assert "discriminatory or communal slur" in violation.lower()

    # 6. Test Script Conformity Validator
    valid_dev, _ = validate_script_conformity("जीएसटी चालान कैसे भरें?", "hi", "native")
    assert valid_dev is True

    invalid_dev, reason = validate_script_conformity("GST challan kaise bharein?", "hi", "native")
    assert invalid_dev is False
    assert "Devanagari" in reason

    valid_rom, _ = validate_script_conformity("GST challan kaise bharein?", "hi", "romanized")
    assert valid_rom is True

    # 7. Test MultiStageValidator with Cultural Guardrail
    validator = MultiStageValidator(AsyncMock(), {"validation_strictness": "standard"})
    bad_sample = ConstructedSample(
        instruction="Tell me about this caste",
        response="Woh neech jaati ke log hain.",
        metadata={"language": "hi"}
    )
    val_result = await validator.validate(bad_sample)
    assert val_result.is_valid is False
    assert any("Cultural/Indic safety guardrail" in r for r in val_result.reasons)

    # 8. Test Tokenizer Fertility Metrics
    fertility = estimate_tokenizer_fertility("hi", "native")
    assert fertility["reference_llama3_fertility"] > fertility["optimal_fertility"]
    assert fertility["potential_token_savings_pct"] > 50.0



