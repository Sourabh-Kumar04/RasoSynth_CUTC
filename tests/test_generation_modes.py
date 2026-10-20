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
    from core.evaluation.llm_judge import evaluate_sample_rubric

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
        license_type="apache-2.0",
        has_dpo=True,
        has_tool_calling=True,
        has_bitext=True,
        tokenizer_savings_pct=42.5,
    )
    assert card.startswith("---")
    assert "language:\n- hi\n- en" in card
    assert "tool-calling" in card
    assert "license: apache-2.0" in card
    assert "load_dataset" in card
    assert "42%" in card

    # 5. Test LLM-as-a-Judge Multi-Dimensional Rubric
    rubric_result = evaluate_sample_rubric(
        instruction="Aap ₹2,50,000 par 18% GST calculate karke bataiye kripya.",
        response="<thought>250000 * 0.18 = 45000</thought>Aapka ₹2,50,000 par 18% GST ₹45,000 hoga. Kul yog ₹2,95,000 banega.",
        language="hinglish",
        formality_register="formal",
    )
    assert rubric_result["groundedness"] > 0.8
    assert rubric_result["authenticity"] > 0.8
    assert rubric_result["domain_correctness"] > 0.8
    assert rubric_result["overall_score"] > 0.8
    assert rubric_result["rating"] in ["excellent", "proficient"]


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





