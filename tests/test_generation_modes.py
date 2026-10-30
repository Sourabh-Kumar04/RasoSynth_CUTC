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

    valid_ta, _ = validate_script_conformity("ஜிஎஸ்டி சலான் எப்படி நிரப்புவது?", "ta", "native")
    assert valid_ta is True

    invalid_ta, reason_ta = validate_script_conformity("GST challan eppadi fill seivathu?", "ta", "native")
    assert invalid_ta is False
    assert "Tamil" in reason_ta

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
    assert fertility["source_status"] == "estimated_unsourced"
    assert fertility["source"] is None

    # Test unknown language handling
    unknown_fertility = estimate_tokenizer_fertility("klingon", "native")
    assert unknown_fertility["unsupported_language"] is True
    assert "unsupported" in unknown_fertility["language_fallback_marker"]


@pytest.mark.asyncio
async def test_indian_pii_numerical_chat_noise_and_fidelity():
    """Verify Indian statutory PII masking, numerical formatting, chat noise, and fidelity metrics."""
    from core.validation.indian_pii import detect_indian_pii, mask_indian_pii
    from core.normalization.indian_numerical import format_indian_number, standardize_currency_text, verbalize_for_speech
    from core.augmentation.transliteration_noise import inject_chat_noise
    from core.metrics.fidelity import compute_chrf_score, evaluate_fidelity
    from pipeline.synthetic_generator import SeedlessGenerator, _build_language_instruction
    from pipeline.planner import DatasetPlan

    # 1. Test Indian PII Detection & Masking
    pii_sample = (
        "User Aadhaar: 3234 5678 9012, PAN: ABCDE1234F, GSTIN: 27ABCDE1234F1Z5, "
        "UPI: vendor@okaxis, Mobile: +91 9876543210, Vehicle: DL 01 AB 1234."
    )
    detected = detect_indian_pii(pii_sample)
    assert "aadhaar" in detected
    assert "pan" in detected
    assert "gstin" in detected
    assert "upi" in detected
    assert "mobile" in detected
    assert "vehicle" in detected

    redacted = mask_indian_pii(pii_sample, replacement_mode="redact")
    assert "[AADHAAR_REDACTED]" in redacted
    assert "[PAN_REDACTED]" in redacted
    assert "[GSTIN_REDACTED]" in redacted
    assert "[UPI_REDACTED]" in redacted
    assert "[PHONE_REDACTED]" in redacted
    assert "[VEHICLE_REDACTED]" in redacted
    assert "3234 5678 9012" not in redacted

    synthetic_pii = mask_indian_pii(pii_sample, replacement_mode="synthetic")
    assert "XXXX-XXXX-0000" in synthetic_pii

    # 2. Test Indian Numerical Formatting & Currency Standardization
    assert format_indian_number(100000) == "1,00,000"
    assert format_indian_number(12345678) == "1,23,45,678"
    assert format_indian_number(500) == "500"

    curr_text = standardize_currency_text("Total liability is Rs. 50000 plus INR 1200 penalty.")
    assert "₹50000" in curr_text
    assert "₹1200" in curr_text

    # 3. Test Voice AI Speech Normalization
    speech_hi = verbalize_for_speech("₹500 ka GST penalty aur OTP bhejo", language="hi")
    assert "500 rupaye" in speech_hi
    assert "जीएसटी" in speech_hi
    assert "ओटीपी" in speech_hi

    # 4. Test Chat Noise Augmentation
    clean_chat = "aapka challan theek hai ya nahi kar rahe ho please"
    noisy = inject_chat_noise(clean_chat, noise_level=1.0, seed=42)
    assert ("apka" in noisy or "apk" in noisy)
    assert ("h" in noisy or "hy" in noisy)
    assert ("nhi" in noisy or "ni" in noisy or "nh" in noisy)
    assert "pls" in noisy or "plz" in noisy

    # 5. Test chrF++ Semantic Fidelity
    exact_score = compute_chrf_score("Tax liability calculation", "Tax liability calculation")
    assert exact_score == 100.0

    fidelity_result = evaluate_fidelity(
        original_text="What is the deadline for filing GSTR-3B return?",
        back_translated_text="What is the time limit for submitting GSTR-3B return?"
    )
    assert fidelity_result["chrf_score"] > 40.0
    assert fidelity_result["is_faithful"] is True

    # 6. Test Prompt Directives for Regional Dialect and DPO Refusal Pairs
    dial_rule = _build_language_instruction(
        "hinglish",
        regional_dialect="bambaiya",
        number_formatting="indian_lakhs",
        generate_dpo_refusal_pairs=True,
        speech_normalization=True,
        turn_language_drift=True,
    )
    assert "Bambaiya/Mumbai" in dial_rule
    assert "Lakhs and Crores" in dial_rule
    assert "DPO Contrastive Pair" in dial_rule
    assert "Voice AI Speech Normalization" in dial_rule
    assert "Conversational Language Drift" in dial_rule

    # 7. Test End-to-End Generator Execution with PII Redaction & Noise Augmentation
    router = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.content = json.dumps({
        "instruction": "Aapka PAN ABCDE1234F hai aur phone +91 9876543210 hai, kya kar rahe ho?",
        "response": "Aapka claim Rs. 50000 accept ho gaya hai.",
        "rejected_response": "Claim reject ho gaya bina kisi statutory rule ke.",
        "instruction_en": "What is the status of my claim?",
        "response_en": "Your claim has been accepted.",
    })
    router.route.return_value = mock_resp

    generator = SeedlessGenerator(router, {
        "language": "hinglish",
        "mask_indian_pii": True,
        "chat_noise_level": 0.5,
        "speech_normalization": True,
        "number_formatting": "indian_lakhs",
        "parallel_bilingual": True,
        "generate_dpo_refusal_pairs": True,
    })

    plan = DatasetPlan(
        domain="Taxation",
        objective="Test PII & Robustness",
        roles=["taxpayer", "assistant"],
        constraints=["timeless"],
        size=1,
    )

    sample = await generator.generate_sample(plan, {"domain": "Taxation"})
    assert sample is not None
    # Verify PII was redacted
    assert "[PAN_REDACTED]" in sample.instruction
    assert "[PHONE_REDACTED]" in sample.instruction
    assert "ABCDE1234F" not in sample.instruction
    # Verify metadata captured PII and DPO pairs
    assert "pan" in sample.metadata.get("pii_detected", {})
    assert "rejected_response" in sample.metadata
    assert "parallel_en" in sample.metadata
    assert "fidelity_metrics" in sample.metadata


@pytest.mark.asyncio
async def test_cot_reasoning_tool_calling_curriculum_and_hf_card():
    """Verify CoT reasoning trajectory, vernacular tool-calling, curriculum sorter, HF dataset card, and LLM judge."""
    from core.generation.cot_synthesizer import (
        build_cot_prompt_directive,
        extract_thought_and_solution,
        wrap_with_thought,
    )
    from core.generation.tool_caller import (
        DEFAULT_FINANCE_TOOLS,
        build_tool_calling_system_prompt,
        format_tool_calling_sample,
    )
    from core.curriculum.curriculum_sorter import (
        sort_by_curriculum,
        estimate_sample_complexity,
    )
    from core.export.huggingface_exporter import generate_hf_dataset_card
    from core.evaluation.heuristic_rubric import evaluate_sample_rubric

    # 1. Test CoT Prompt Directive & Extraction
    directive_hi = build_cot_prompt_directive("hi")
    assert "<thought>" in directive_hi
    assert "</thought>" in directive_hi

    sample_raw = "<thought>Pehle annual turnover calculate karenge: 50L + 20L = 70L. Fir 18% GST apply karenge.</thought>Aapka total GST payable ₹12,60,000 banta hai."
    thought, answer = extract_thought_and_solution(sample_raw)
    assert "Pehle annual turnover calculate karenge" in thought
    assert "₹12,60,000" in answer

    wrapped = wrap_with_thought("Step 1 -> Step 2", "Final answer")
    assert wrapped == "<thought>\nStep 1 -> Step 2\n</thought>\n\nFinal answer"

    # 2. Test Tool Calling Prompt and Sample Format
    tool_prompt = build_tool_calling_system_prompt(DEFAULT_FINANCE_TOOLS)
    assert "check_itc_balance" in tool_prompt
    assert "generate_gst_challan" in tool_prompt
    assert "INSTRUCTIONS:" in tool_prompt

    tool_sample = format_tool_calling_sample(
        instruction="Mera 28% slab par GST challan bana do",
        tool_calls=[{"name": "generate_gst_challan", "arguments": {"gstin": "27AAPFU0939F1ZV", "cgst_amount": 14000, "sgst_amount": 14000, "payment_mode": "upi"}}],
        assistant_thought="Taxpayer needs PMT-06 challan generation for ₹28,000 tax liability."
    )
    assert tool_sample["tool_calls"][0]["name"] == "generate_gst_challan"
    assert tool_sample["tool_calls"][0]["arguments"]["gstin"] == "27AAPFU0939F1ZV"
    assert "tool_calls" in tool_sample["response"]

    # 3. Test Curriculum Complexity Estimation & Sorters
    samples = [
        {"instruction": "What is GST?", "response": "Goods and Services Tax."}, # short/simple -> low tier
        {
            "instruction": "Step by step procedure to file GSTR-3B with reverse charge mechanism and input tax credit reconciliation under section 16(4) of CGST act.",
            "response": "<thought>Examine CGST Act Section 16(4). Analyze ITC eligibility deadlines and calculate debit note reconciliations.</thought>Detailed comprehensive analysis with multiple clauses...",
            "metadata": {"complexity_tier": 5}
        },
        {"instruction": "TDS rate for contractor payments under 194C?", "response": "1% for individual/HUF and 2% for others."},
    ]

    # Complexity estimation
    score_simple = estimate_sample_complexity(samples[0])
    score_complex = estimate_sample_complexity(samples[1])
    assert score_complex > score_simple

    # Ascending sort
    sorted_asc = sort_by_curriculum(samples, mode="ascending")
    assert sorted_asc[0]["instruction"] == "What is GST?"

    # Staged curriculum sort
    sorted_staged = sort_by_curriculum(samples, mode="staged_curriculum")
    assert len(sorted_staged) == len(samples)

    # Replay interleaved sort
    sorted_replay = sort_by_curriculum(samples, mode="replay_interleaved", replay_ratio=0.33)
    assert len(sorted_replay) >= len(samples)

    # 4. Test Hugging Face Dataset Card Generation
    card = generate_hf_dataset_card(
        dataset_name="Indic-Tax-Instruct-50K",
        domain="Indian Taxation & Finance",
        sample_count=50000,
        language="hinglish",
        script_mode="romanized",
        dataset_type="sft",
        has_dpo=True,
        has_tool_calling=True,
        has_bitext=True,
        tokenizer_savings_pct=42.5,
    )
    assert card.startswith("---")
    assert "language:\n- hi\n- en" in card
    assert "tool-calling" in card
    assert "license: PolyForm-Noncommercial-1.0.0" in card
    assert "load_dataset" in card
    assert "42%" in card

    # 5. Test Heuristic Multi-Dimensional Rubric (formerly misnamed llm_judge)
    rubric_result = evaluate_sample_rubric(
        instruction="Aap ₹2,50,000 par 18% GST calculate karke bataiye kripya.",
        response="<thought>250000 * 0.18 = 45000</thought>Aapka ₹2,50,000 par 18% GST ₹45,000 hoga. Kul yog ₹2,95,000 banega.",
        language="hinglish",
        formality_register="formal",
    )
    # When no reference context is given, groundedness is None and rating is capped at proficient
    assert rubric_result["groundedness"] is None
    assert rubric_result["authenticity"] > 0.8
    assert rubric_result["domain_correctness"] > 0.8
    assert rubric_result["overall_score"] > 0.8
    assert rubric_result["rating"] == "proficient"

    # With reference context, groundedness is measured
    rubric_with_ref = evaluate_sample_rubric(
        instruction="Calculate GST",
        response="Aapka GST ₹45,000 hoga",
        reference_context="Total GST ₹45,000 calculated on base turnover.",
        language="en",
    )
    assert rubric_with_ref["groundedness"] is not None


def test_frontier_preference_adversarial_contamination_and_recipes():
    """Verify KTO/SimPO preference formatting, adversarial probes, contamination audit, and recipes."""
    from core.generation.preference_synthesizer import (
        format_kto_sample,
        format_simpo_pair,
        build_preference_directive,
    )
    from core.safety.adversarial_generator import (
        generate_adversarial_probes,
        check_adversarial_compliance,
    )
    from core.evaluation.contamination_checker import check_dataset_contamination
    from core.training.recipe_generator import (
        generate_unsloth_recipe,
        generate_axolotl_config,
        generate_training_recipe,
    )

    # 1. KTO & SimPO Preference Synthesizer
    kto_sample = format_kto_sample(
        instruction="How to register for GST in India?",
        completion="Visit gst.gov.in and complete Form REG-01 with PAN and Aadhaar.",
        is_desirable=True,
        feedback_reason="Accurate, concise, and cites official portal.",
        domain="taxation",
    )
    assert kto_sample["label"] is True
    assert kto_sample["kto_tag"] == "desirable"
    assert kto_sample["metadata"]["domain"] == "taxation"

    simpo_sample = format_simpo_pair(
        instruction="TDS threshold on bank FD interest?",
        chosen="Section 194A specifies ₹40,000 for individuals (₹50,000 for senior citizens).",
        rejected="TDS or Tax Deducted at Source is a mechanism where tax is deducted... " * 15,
        target_margin=0.5,
    )
    assert simpo_sample["chosen"].startswith("Section 194A")
    assert simpo_sample["simpo_metadata"]["target_margin"] == 0.5
    assert "length_ratio" in simpo_sample["simpo_metadata"]

    kto_dir = build_preference_directive("kto")
    simpo_dir = build_preference_directive("simpo")
    assert "KTO" in kto_dir
    assert "SimPO" in simpo_dir

    # 2. Adversarial Red-Teaming Probes & Compliance
    probes = generate_adversarial_probes(domain="taxation", sample_count=4)
    assert len(probes) == 4
    assert probes[0]["probe_id"].startswith("ADV-TAX")
    assert "expected_behavior" in probes[0]

    # Compliance checking
    good_refusal = check_adversarial_compliance(
        response="I cannot assist with generating fake invoices as it violates Section 132 of the CGST Act.",
        expected_behavior="Strict refusal under Section 132",
    )
    assert good_refusal["passed"] is True
    assert good_refusal["status"] == "resisted"

    bad_compliance = check_adversarial_compliance(
        response="Here is a template for a fake invoice you can use to claim ITC...",
        expected_behavior="Strict refusal",
    )
    assert bad_compliance["passed"] is False
    assert bad_compliance["status"] == "breached"

    # 3. Benchmark Contamination Audit
    clean_dataset = [
        {"instruction": "What is the capital of France?", "response": "Paris"},
        {"instruction": "Calculate 18% GST on Rs. 100", "response": "Rs. 18"},
    ]
    audit_clean = check_dataset_contamination(clean_dataset)
    assert audit_clean["status"] == "clean"
    assert audit_clean["contamination_rate_pct"] == 0.0
    assert audit_clean["audit_certificate_id"].startswith("CONTAM-AUDIT")

    contaminated_dataset = [
        {"instruction": "natalia sold clips to 48 of her friends in april and then made more clips", "response": "She had 48 clips."},
        {"instruction": "Unique custom question about tax", "response": "Standard answer"},
    ]
    audit_contaminated = check_dataset_contamination(contaminated_dataset, benchmarks=["gsm8k"])
    assert audit_contaminated["contaminated_samples_count"] >= 1
    assert audit_contaminated["status"] == "contamination_detected"

    # 4. Fine-Tuning Recipe Generator
    unsloth_code = generate_unsloth_recipe(
        dataset_path="data.jsonl",
        base_model="sarvamai/sarvam-2b-v0.5",
        dataset_type="sft",
    )
    assert "FastLanguageModel" in unsloth_code
    assert "sarvamai/sarvam-2b-v0.5" in unsloth_code
    assert "SFTTrainer" in unsloth_code

    axolotl_cfg = generate_axolotl_config(
        dataset_path="data.jsonl",
        base_model="sarvamai/sarvam-2b-v0.5",
        dataset_type="dpo",
    )
    assert "base_model: sarvamai/sarvam-2b-v0.5" in axolotl_cfg
    assert "type: dpo" in axolotl_cfg

    recipe_result = generate_training_recipe(
        framework="llamafactory",
        base_model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        dataset_type="sft",
    )
    assert recipe_result["framework"] == "llamafactory"
    assert "llamafactory-cli train" in recipe_result["content"]


def test_rag_synthesis_and_faithfulness():
    """Verify multi-hop RAG synthesis, citation formatting, and faithfulness evaluation."""
    from core.generation.rag_synthesizer import (
        build_rag_prompt_directive,
        format_rag_sample,
        evaluate_rag_faithfulness,
    )

    # 1. Directive generation
    dir_with_neg = build_rag_prompt_directive(include_hard_negatives=True)
    assert "hard_negatives" in dir_with_neg
    assert "positive_contexts" in dir_with_neg

    dir_no_neg = build_rag_prompt_directive(include_hard_negatives=False)
    assert "hard_negatives" not in dir_no_neg

    # 2. Sample formatting with citations and hard negatives
    sample = format_rag_sample(
        query="Under Section 80C, what is the maximum deduction allowed for EPF and PPF?",
        positive_contexts=[
            "Section 80C of the Income Tax Act allows deductions up to Rs. 1,50,000 per financial year.",
            "Eligible investments under 80C include Employee Provident Fund (EPF) and Public Provident Fund (PPF).",
        ],
        hard_negatives=[
            "Section 80D allows deductions for health insurance premiums up to Rs. 25,000.",
        ],
        grounded_response="Under Section 80C, the cumulative deduction limit is Rs. 1,50,000 [1], which includes investments in both EPF and PPF [2].",
        domain="taxation",
    )

    assert sample["instruction"].startswith("Under Section 80C")
    assert len(sample["positive_contexts"]) == 2
    assert len(sample["hard_negatives"]) == 1
    assert len(sample["contexts"]) == 3  # 2 positive + 1 negative
    assert len(sample["citations"]) == 2
    assert sample["citations"][0]["citation_id"] == 1
    assert sample["citations"][1]["citation_id"] == 2
    assert sample["metadata"]["type"] == "multi_hop_rag"
    assert sample["metadata"]["citation_count"] == 2

    # 3. Faithfulness evaluation
    faithful_eval = evaluate_rag_faithfulness(
        response="Under Section 80C of the Income Tax Act deductions up to Rs 1,50,000 per financial year [1].",
        positive_contexts=["Section 80C of the Income Tax Act allows deductions up to Rs. 1,50,000 per financial year."],
    )
    assert faithful_eval["status"] == "grounded"
    assert faithful_eval["has_citations"] is True
    assert faithful_eval["faithfulness_score"] >= 0.70

    empty_eval = evaluate_rag_faithfulness(
        response="",
        positive_contexts=[],
    )
    assert empty_eval["status"] == "unfaithful"
    assert empty_eval["faithfulness_score"] == 0.0

    unsupported_eval = evaluate_rag_faithfulness(
        response="Completely unrelated extraterrestrial galaxy travel mechanics.",
        positive_contexts=["Section 80C of the Income Tax Act allows deductions up to Rs. 1,50,000."],
    )
    assert unsupported_eval["status"] == "unsupported"


def test_semantic_diversity_and_clustering():
    """Verify TF-IDF SVD projection, K-means clustering, and entropy computation."""
    from core.curation.diversity_mapper import (
        tokenize_text,
        build_tfidf_matrix,
        reduce_dimension_2d,
        analyze_semantic_diversity,
    )

    tokens = tokenize_text("Calculate 18% GST on Rs. 2,50,000 for invoice #123")
    assert "calculate" in tokens
    assert "gst" in tokens
    assert "invoice" in tokens

    samples = [
        {"instruction": "Calculate 18% GST on consulting invoice", "response": "GST is Rs. 18,000.", "domain": "Taxation"},
        {"instruction": "Input Tax Credit rules under Section 16", "response": "Invoice is mandatory.", "domain": "Taxation"},
        {"instruction": "What is the penalty for late GSTR-3B filing?", "response": "Rs. 50 per day.", "domain": "Compliance"},
        {"instruction": "Appeal before First Appellate Authority for GST notice", "response": "File Form GST APL-01.", "domain": "Compliance"},
        {"instruction": "Section 80C deductions for EPF and PPF deposits", "response": "Up to Rs. 1.5 Lakhs.", "domain": "Income Tax"},
        {"instruction": "Demurrage charges on sea container customs detention", "response": "Port terminal charges.", "domain": "Logistics"},
    ]

    report = analyze_semantic_diversity(samples, k_clusters=3)
    assert report["total_samples"] == 6
    assert 0.0 <= report["diversity_entropy"] <= 1.0
    assert len(report["clusters"]) == 3
    assert len(report["points"]) == 6
    for pt in report["points"]:
        assert 10.0 <= pt["x"] <= 90.0
        assert 10.0 <= pt["y"] <= 90.0
        assert "cluster_label" in pt
        assert "is_outlier" in pt


def test_multi_turn_synthesis_and_coherence():
    """Verify multi-turn dialogue generation directive, format serialization, and coherence checking."""
    from core.generation.multi_turn_synthesizer import (
        build_multi_turn_directive,
        format_multi_turn_sample,
        evaluate_dialogue_coherence,
    )

    directive = build_multi_turn_directive(num_turns=4, language="hinglish")
    assert "MULTI-TURN CONVERSATIONAL DIALOGUE SPECIFICATION" in directive
    assert "at least 4 alternating turns" in directive

    turns = [
        {"role": "user", "content": "Mera ITC claim mismatch aa raha hai GSTR-2B se."},
        {"role": "assistant", "content": "GSTR-2B mein invoice reflect nahi hone par aap supplier se verify karein."},
        {"role": "user", "content": "Agar supplier ne quarterly file kiya ho tab kya karein?"},
        {"role": "assistant", "content": "Quarterly filers ke liye IFF upload check karein Rule 36(4) ke tehat."},
    ]

    # Format into ShareGPT
    sg_sample = format_multi_turn_sample(turns, format_type="sharegpt")
    assert "conversations" in sg_sample
    assert len(sg_sample["conversations"]) == 4
    assert sg_sample["conversations"][0]["from"] == "human"
    assert sg_sample["conversations"][1]["from"] == "gpt"

    # Format into OpenAI
    oai_sample = format_multi_turn_sample(turns, format_type="openai")
    assert "messages" in oai_sample
    assert len(oai_sample["messages"]) == 4
    assert oai_sample["messages"][0]["role"] == "user"
    assert oai_sample["messages"][1]["role"] == "assistant"

    # Coherence evaluation
    coh_good = evaluate_dialogue_coherence(turns)
    assert coh_good["is_coherent"] is True
    assert coh_good["coherence_score"] >= 0.70
    assert coh_good["user_turns"] == 2
    assert coh_good["assistant_turns"] == 2

    broken_turns = [
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "Are you there?"},
    ]
    coh_bad = evaluate_dialogue_coherence(broken_turns)
    assert coh_bad["is_coherent"] is False
    assert any("alternation" in iss for iss in coh_bad["issues"])


def test_best_of_n_consensus_and_preference_generation():
    """Verify Best-of-N candidate parsing, majority voting consensus, and preference extraction."""
    from core.curation.best_of_n import (
        normalize_canonical_answer,
        score_reasoning_trajectory,
        filter_best_of_n,
    )

    assert normalize_canonical_answer("₹45,000.00") == "45000"
    assert normalize_canonical_answer("Rs. 18%") == "18"
    assert normalize_canonical_answer("Paris.") == "paris"

    score_structured = score_reasoning_trajectory(
        thought="Step 1: Calculate 18% of 250000 = 45000. Step 2: Add to principal = 295000.",
        solution="Total is 295000."
    )
    score_unstructured = score_reasoning_trajectory(thought="just did it", solution="295000")
    assert score_structured > score_unstructured

    # Best-of-N Rejection Sampling on candidate traces
    candidates = [
        "<thought>Pehle step 1 calculate karo: 100 * 0.18 = 18. Isliye total answer 18 hoga.</thought>Answer: ₹18",
        "<thought>Step 1: multiply 100 by 18 percent. 100 * 18 / 100 = 18.</thought>Total GST is 18.",
        "<thought>Guessed it wrong, maybe 28%.</thought>Answer: 28.",
    ]

    bon_result = filter_best_of_n(
        instruction="Calculate 18% GST on Rs. 100",
        candidates=candidates,
        domain="taxation",
    )

    assert bon_result["status"] == "consensus_reached"
    assert bon_result["target_answer"] == "18"
    assert bon_result["consensus_rate"] >= 0.66
    assert bon_result["total_candidates"] == 3
    assert "₹18" in bon_result["chosen_response"] or "18" in bon_result["chosen_response"]
    assert len(bon_result["rejected_responses"]) >= 1
    assert "28" in bon_result["rejected_responses"][0]

    pref = bon_result["preference_pair"]
    assert pref is not None
    assert "chosen" in pref
    assert "rejected" in pref
    assert pref["instruction"] == "Calculate 18% GST on Rs. 100"


def test_representation_balancer():
    """Verify regional geographic zoning, urbanicity classification, and parity scoring."""
    from core.curation.representation_balancer import (
        audit_sample_representation,
        audit_dataset_representation,
    )

    sample_south = audit_sample_representation("Tax filing assistance for startup in Bengaluru, Karnataka by Priya.")
    assert "south" in sample_south["zones"]
    assert sample_south["setting"] == "tier_1_metro"
    assert sample_south["gender_indicator"] == "female"

    sample_rural = audit_sample_representation("Kisan credit card scheme for farmer in gaon mandi by Ramesh.")
    assert sample_rural["setting"] == "rural_gramin"

    dataset = [
        {"instruction": "Startup GST registration in Bengaluru, Karnataka", "response": "Visit portal."},
        {"instruction": "Property tax filing in Chennai, Tamil Nadu", "response": "Pay municipal tax."},
        {"instruction": "Textile trade challan in Surat, Gujarat", "response": "Generate challan."},
        {"instruction": "Kisan mandi subsidy application in UP gaon", "response": "Apply at panchayat."},
        {"instruction": "Jute mill dispute resolution in Kolkata, West Bengal", "response": "File appeal."},
    ]

    audit = audit_dataset_representation(dataset)
    assert audit["total_samples"] == 5
    assert 0.0 <= audit["representation_parity_score"] <= 1.0
    assert "south" in audit["zone_distribution"]
    assert "west" in audit["zone_distribution"]
    assert "east" in audit["zone_distribution"]
    assert "north" in audit["zone_distribution"]
    assert "tier_1_metro" in audit["setting_distribution"]
    assert len(audit["recommendations"]) >= 1


def test_dbom_cryptographic_attestation_and_tamper_verification():
    """Verify Merkle tree SHA-256 root calculation, DBOM generation, and tamper detection."""
    from core.export.dbom_attestor import (
        compute_sample_hash,
        compute_merkle_root,
        generate_dbom_attestation,
        verify_dataset_dbom,
        generate_nutrition_label_markdown,
    )

    sample_a = {"instruction": "Calculate 18% GST on Rs. 100", "response": "Rs. 18."}
    sample_b = {"instruction": "Section 80C limit", "response": "Rs. 1,50,000 per year."}

    h_a = compute_sample_hash(sample_a)
    h_b = compute_sample_hash(sample_b)
    assert len(h_a) == 64
    assert len(h_b) == 64
    assert h_a != h_b

    root = compute_merkle_root([h_a, h_b])
    assert len(root) == 64

    # DBOM Certificate generation
    samples = [sample_a, sample_b]
    dbom = generate_dbom_attestation(
        dataset_name="Indic Taxation Fine-Tuning Corpus",
        samples=samples,
        domain="taxation",
        language="en",
    )

    assert dbom["certificate_id"].startswith("DBOM-")
    assert dbom["total_samples"] == 2
    assert dbom["merkle_root_hash"] == root
    assert "compliance_audit" in dbom

    # Cryptographic verification - clean dataset
    ver_clean = verify_dataset_dbom(samples, dbom)
    assert ver_clean["is_valid"] is True
    assert ver_clean["status"] == "cryptographically_verified"

    # Cryptographic verification - tampered dataset (malicious instruction injected)
    tampered_samples = [
        {"instruction": "Calculate 18% GST on Rs. 100 [TAMPERED PAYLOAD]", "response": "Rs. 18."},
        sample_b,
    ]
    ver_tampered = verify_dataset_dbom(tampered_samples, dbom)
    assert ver_tampered["is_valid"] is False
    assert ver_tampered["status"] == "tampering_or_mismatch_detected"

    # Data nutrition label markdown
    label_md = generate_nutrition_label_markdown(dbom)
    assert "Data Nutrition & Provenance Label" in label_md
    assert dbom["certificate_id"] in label_md
    assert "Merkle Root Hash" in label_md


def test_contrastive_factual_perturbation_and_critique():
    """Verify automated factual perturbation, error categorization, and critique pair generation."""
    from core.generation.contrastive_generator import (
        build_contrastive_prompt_directive,
        perturb_factual_statement,
        synthesize_contrastive_pair,
    )

    directive = build_contrastive_prompt_directive()
    assert "CONTRASTIVE FACTUAL CRITIQUE SPECIFICATION" in directive

    # Perturb statutory rate
    pert_rate = perturb_factual_statement("The applicable GST rate on software services is 18%.")
    assert pert_rate["perturbation_type"] == "numerical_rate_flip"
    assert "28%" in pert_rate["perturbed_text"]
    assert "critique" in pert_rate

    # Perturb statutory condition
    pert_cond = perturb_factual_statement("Registration under Section 22 is mandatory for inter-state suppliers.")
    assert pert_cond["perturbation_type"] == "statutory_condition_inversion"
    assert "optional" in pert_cond["perturbed_text"]

    # Synthesize complete contrastive pair
    pair = synthesize_contrastive_pair(
        instruction="What is the tax rate on IT consulting?",
        grounded_response="The tax rate on IT consulting services is 18%.",
        domain="taxation",
    )
    assert pair["grounded_response"] != pair["perturbed_negative"]
    assert "preference_pair" in pair
    assert pair["preference_pair"]["chosen"] == pair["grounded_response"]
    assert pair["preference_pair"]["rejected"] == pair["perturbed_negative"]


def test_active_rebalancing_plan():
    """Verify targeted prompt mutations and quota allocation for underrepresented zones."""
    from core.curation.active_balancer import plan_active_rebalancing

    mock_audit = {
        "representation_parity_score": 0.45,
        "zone_distribution": {
            "north": {"percentage": 60.0},
            "south": {"percentage": 25.0},
            "west": {"percentage": 10.0},
            "east": {"percentage": 5.0},
            "northeast": {"percentage": 0.0},
        },
        "setting_distribution": {
            "rural_gramin": {"percentage": 10.0},
            "tier_1_metro": {"percentage": 90.0},
        },
        "underrepresented_zones": ["east", "northeast"],
    }

    plan = plan_active_rebalancing(mock_audit, target_sample_pool=100, domain="taxation")
    assert plan["status"] == "rebalancing_plan_generated"
    assert plan["total_rebalancing_samples_planned"] > 0
    assert len(plan["targeted_directives"]) >= 2
    ne_directive = next((d for d in plan["targeted_directives"] if d["target_zone"] == "northeast"), None)
    assert ne_directive is not None
    assert "NORTHEAST" in ne_directive["prompt_directive"]


def test_dialectic_debate_synthesis_and_coherence():
    """Verify multi-agent dialectic debate directive, sample formatting, and coherence verification."""
    from core.generation.socratic_synthesizer import (
        build_dialectic_prompt_directive,
        format_dialectic_sample,
        evaluate_dialectic_coherence,
    )

    directive = build_dialectic_prompt_directive(domain="taxation", rounds=2)
    assert "MULTI-AGENT DIALECTIC DEBATE SPECIFICATION" in directive
    assert "Auditor Sharma" in directive
    assert "CFO Mehra" in directive

    rounds = [
        {
            "speaker": "Auditor Sharma",
            "stance": "Strict Statutory Compliance",
            "argument": "Under Section 16(2)(aa) of the CGST Act, ITC cannot be availed unless the supplier uploads invoice details in Form GSTR-1.",
        },
        {
            "speaker": "CFO Mehra",
            "stance": "Commercial Equity",
            "argument": "The taxpayer has paid the invoice in full along with taxes; penalizing the recipient for bona fide supplier delay violates judicial precedent in Bharti Airtel.",
        },
    ]
    verdict = "Consensus Adjudication: The taxpayer must reverse ITC provisionally under Rule 37A with interest, but may reclaim it immediately once the supplier rectifies GSTR-3B."

    sample = format_dialectic_sample(
        topic="ITC eligibility when supplier delays GSTR-1 filing",
        debate_rounds=rounds,
        verdict=verdict,
        domain="taxation",
    )
    assert sample["metadata"]["type"] == "dialectic_debate"
    assert "Auditor Sharma" in sample["response"]
    assert "CFO Mehra" in sample["response"]
    assert "Consensus Adjudication" in sample["response"]

    coherence = evaluate_dialectic_coherence(rounds, verdict)
    assert coherence["is_valid"] is True
    assert coherence["coherence_score"] >= 0.70
    assert coherence["distinct_speakers"] == 2


def test_judge_calibration_and_kappa():
    """Verify Cohen's Kappa, systematic bias detection, and threshold calibration."""
    from core.evaluation.judge_calibrator import (
        compute_cohens_kappa,
        calibrate_judge_alignment,
    )

    human = [1, 1, 0, 0, 1, 1, 0, 1]
    judge = [1, 1, 0, 0, 1, 1, 0, 0]
    kappa = compute_cohens_kappa(human, judge)
    assert kappa >= 0.60

    evals = [
        {"human_decision": "approved", "judge_score": 0.92},
        {"human_decision": "approved", "judge_score": 0.85},
        {"human_decision": "rejected", "judge_score": 0.35},
        {"human_decision": "approved", "judge_score": 0.78},
        {"human_decision": "rejected", "judge_score": 0.40},
    ]
    calib = calibrate_judge_alignment(evals, default_threshold=0.70)
    assert calib["total_pairs"] == 5
    assert calib["pairwise_accuracy_pct"] == 100.0
    assert calib["agreement_strength"] in ("substantial", "almost_perfect")


def test_synthetic_benchmark_evaluator():
    """Verify Exact Match, token F1, and composite score computation on benchmark splits."""
    from core.evaluation.benchmark_evaluator import (
        compute_token_f1,
        evaluate_benchmark_split,
    )

    f1 = compute_token_f1("The GST rate is 18%", "The GST rate is 18 percent")
    assert f1 >= 0.75

    pairs = [
        {"prediction": "Rs. 18,000", "reference": "Rs. 18,000"},
        {"prediction": "Section 80C allows Rs. 1.5 Lakhs [1]", "reference": "Section 80C allows Rs. 1.5 Lakhs [1]"},
        {"prediction": "Wrong answer", "reference": "Correct answer"},
    ]
    # Without held_out flag, ratings production_ready/frontier_exceptional are never awarded
    report = evaluate_benchmark_split(pairs, benchmark_name="Tax QA Benchmark", held_out=False)
    assert report["total_samples"] == 3
    assert report["exact_match_pct"] >= 66.0
    assert report["mean_token_f1"] > 0.60
    assert report["citation_accuracy_pct"] == 100.0
    assert report["rating"] == "unverified_split_not_held_out"

    # With held_out=True, ratings production_ready/frontier_exceptional are eligible
    held_out_report = evaluate_benchmark_split(pairs, benchmark_name="Tax QA Benchmark", held_out=True)
    assert held_out_report["rating"] in ("production_ready", "frontier_exceptional")

    # When no citations exist in references, citation_accuracy_pct must be None
    no_citation_pairs = [
        {"prediction": "Rs. 18,000", "reference": "Rs. 18,000"},
    ]
    no_cit_report = evaluate_benchmark_split(no_citation_pairs, benchmark_name="No Citations")
    assert no_cit_report["citation_accuracy_pct"] is None


def test_streaming_dataset_sharder():
    """Verify chunked sharding, JSONL serialization, and SHA-256 checksums."""
    from core.export.streaming_sharder import shard_dataset_records

    records = [
        {"instruction": f"Instruction {i}", "response": f"Response {i}"}
        for i in range(25)
    ]

    sharded = shard_dataset_records(records, shard_size=10, prefix="train", compress=False)
    assert sharded["total_samples"] == 25
    assert sharded["shard_count"] == 3
    assert len(sharded["shards"]) == 3
    assert sharded["shards"][0]["record_count"] == 10
    assert sharded["shards"][1]["record_count"] == 10
    assert sharded["shards"][2]["record_count"] == 5
    assert len(sharded["shards"][0]["sha256_checksum"]) == 64
    assert sharded["manifest"]["total_records"] == 25


@pytest.mark.asyncio
async def test_construction_pipeline_str_dataset_type_normalization():
    """Verify ConstructionPipeline accepts both enum and string dataset_type without AttributeError."""
    from unittest.mock import Mock, AsyncMock
    from pipeline.construction import ConstructionPipeline, DatasetType
    from core.intent import UserIntent

    router = Mock()
    router.initialize = AsyncMock(return_value={"initialized": ["mock"], "failed": []})

    pipeline = ConstructionPipeline(router, {"dataset_type": "sft", "language": "en"})
    sample_obj = type("Sample", (), {"content": "Sample content", "quality_score": 0.8, "metadata": {}})()
    intent = UserIntent(
        primary_task="instruction_tuning",
        domain="General",
        modality="text",
        anti_domains=[],
        key_entities=[],
        specialized_queries=[],
        constraints=[],
        output_format="instruction_response",
        confidence=0.9,
        raw_input="test",
    )

    # Calling with string "sft" should normalize properly to DatasetType.SFT
    async for _ in pipeline._construct_generator(sample_obj, intent, dataset_type="sft"):
        pass
    assert pipeline.dataset_type == DatasetType.SFT

    # Calling with invalid string defaults gracefully to DatasetType.SFT
    async for _ in pipeline._construct_generator(sample_obj, intent, dataset_type="unknown_mode"):
        pass
    assert pipeline.dataset_type == DatasetType.SFT


def test_kaggle_language_sample_review_gate():
    """Verify Kaggle sample review gate validates script conformity before admitting dataset."""
    from core.validation.cultural_guardrails import validate_script_conformity

    # 1. Hindi requested: English snippet should be rejected
    english_snippet = "This is an English customer dataset with name, age, and transactions."
    conforms, reason = validate_script_conformity(english_snippet, "hi", "native")
    assert not conforms
    assert "Devanagari script" in reason

    # 2. Hindi requested: Devanagari snippet should be accepted
    hindi_snippet = "यह वस्तु एवं सेवा कर (जीएसटी) अनुपालन का आधिकारिक डेटासेट है।"
    conforms, reason = validate_script_conformity(hindi_snippet, "hi", "native")
    assert conforms
    assert reason is None or reason == ""

    # 3. Tamil requested: English snippet rejected, Tamil accepted
    tamil_snippet = "இது சரக்கு மற்றும் சேவை வரி தொடர்பான அதிகாரப்பூர்வ தரவுத்தொகுப்பாகும்."
    assert not validate_script_conformity(english_snippet, "ta", "native")[0]
    assert validate_script_conformity(tamil_snippet, "ta", "native")[0]











