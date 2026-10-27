import json
import logging
import re
import math
from typing import Optional
from pipeline.construction import ConstructedSample
from pipeline.planner import DatasetPlan
from core.provider_router import ProviderRouter, TaskType
from core.validation.indian_pii import detect_indian_pii, mask_indian_pii
from core.normalization.indian_numerical import format_indian_number, standardize_currency_text, verbalize_for_speech
from core.augmentation.transliteration_noise import inject_chat_noise
from core.metrics.fidelity import evaluate_fidelity
from core.generation.cot_synthesizer import build_cot_prompt_directive, extract_thought_and_solution
from core.generation.tool_caller import build_tool_calling_system_prompt, DEFAULT_FINANCE_TOOLS
from core.generation.preference_synthesizer import build_preference_directive
from core.generation.rag_synthesizer import build_rag_prompt_directive, format_rag_sample, evaluate_rag_faithfulness
from core.generation.multi_turn_synthesizer import build_multi_turn_directive, format_multi_turn_sample, evaluate_dialogue_coherence
from core.generation.socratic_synthesizer import build_dialectic_prompt_directive, format_dialectic_sample, evaluate_dialectic_coherence
from core.curriculum.curriculum_sorter import sort_by_curriculum

logger = logging.getLogger(__name__)

# ── Difficulty tier mapping ───────────────────────────────────────────────────
# Maps cell-level text difficulty attributes → integer tier (1–5)
_DIFFICULTY_MAP = {
    "very easy": 1, "beginner": 1, "easy": 2, "simple": 2,
    "medium": 3, "intermediate": 3, "standard": 3,
    "hard": 4, "advanced": 4, "difficult": 4,
    "very hard": 5, "expert": 5, "complex": 5,
}

# Known time-sensitive / factual answer types that should be rejected
_TEMPORAL_PATTERNS = [
    r"¿qué hora es",
    r"what time is it",
    r"what is the current (time|date|weather|temperature|price|stock|score)",
    r"¿cuál es (la hora|el tiempo|el clima|la temperatura|el precio) actual",
    r"what.*today.*weather",
    r"dame la hora",
    r"current (price|rate|value|score|ranking)",
]
_TEMPORAL_RE = re.compile("|".join(_TEMPORAL_PATTERNS), re.IGNORECASE)


def _is_temporal_hallucination(instruction: str) -> bool:
    """Return True if the instruction asks for live/time-sensitive data."""
    return bool(_TEMPORAL_RE.search(instruction))


def _extract_json_object(raw_text: str) -> dict:
    """Robustly extract a JSON object containing instruction/response keys."""
    if not raw_text:
        return {}

    cleaned = re.sub(r'```(?:json)?\s*', '', raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and ("instruction" in data or "response" in data):
            return data
    except Exception:
        pass

    match = re.search(r'\{\s*"instruction"\s*:.*?"response"\s*:.*?\}', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    match_outer = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match_outer:
        try:
            return json.loads(match_outer.group(0))
        except Exception:
            pass

    return {}


def _resolve_difficulty_tier(cell: dict, cell_index: int, total_cells: int) -> int:
    """
    Fix #2: Derive a varied difficulty tier (1–5) from the cell attributes.

    Priority order:
      1. Explicit 'difficulty' key in cell (mapped via _DIFFICULTY_MAP)
      2. 'text_length': short→2, medium→3, long→4
      3. Cyclic fallback spread evenly across 1–5
    """
    # 1. Explicit difficulty in cell
    raw = str(cell.get("difficulty", cell.get("complexity", ""))).lower().strip()
    if raw in _DIFFICULTY_MAP:
        return _DIFFICULTY_MAP[raw]

    # 2. text_length proxy
    length = str(cell.get("text_length", "")).lower()
    if length == "short":
        return 2
    if length == "long":
        return 4
    if length == "medium":
        return 3

    # 3. Cyclic spread: distributes tiers evenly across cells
    return (cell_index % 5) + 1


def _build_language_instruction(
    language: str,
    script_mode: str = "native",
    formality_register: str = "formal",
    code_switch_intensity: str = "balanced",
    preserved_terms: list[str] | None = None,
    parallel_bilingual: bool = False,
    regional_dialect: str = "standard",
    number_formatting: str = "indian_lakhs",
    generate_dpo_refusal_pairs: bool = False,
    speech_normalization: bool = False,
    turn_language_drift: bool = False,
    enable_cot_reasoning: bool = False,
) -> str:
    """Build comprehensive language, script, register, glossary, dialect, and numerical rules for synthetic prompt generation."""
    lang = (language or "en").lower().strip()
    script = (script_mode or "native").lower().strip()
    register = (formality_register or "formal").lower().strip()
    intensity = (code_switch_intensity or "balanced").lower().strip()

    # 1. Base language & script
    if lang in ("en", "english"):
        base_rule = "5. Generate the instruction and response strictly in English."
    elif script == "romanized":
        if lang in ("hi", "hindi"):
            base_rule = (
                "5. Generate the instruction and response in Hindi written phonetically in Latin / Romanized script "
                "(e.g., 'Namaste, main aapki kya sahayata kar sakta hoon?'). Do NOT use Devanagari script."
            )
        else:
            base_rule = f"5. Generate the instruction and response in {language} written phonetically in Latin / Romanized script."
    elif script == "dual":
        base_rule = (
            f"5. Generate the instruction and response in {language} with dual script output: "
            "provide standard native script in 'instruction' and 'response', and include 'instruction_romanized' "
            "and 'response_romanized' in phonetic Latin script."
        )
    elif lang in ("hi", "hindi"):
        base_rule = "5. Generate the instruction and response strictly in Hindi (हिन्दी) using Devanagari script."
    elif lang in ("hinglish", "hi-en", "en-hi"):
        intensity_notes = {
            "light": "predominantly Hindi (80%) with English only for technical loanwords (code-switched)",
            "balanced": "natural 50/50 conversational Hindi and English code-switched dialogue",
            "heavy": "predominantly English (80%) accented with natural Hindi discourse markers (code-switched)",
        }.get(intensity, "natural conversational Hindi and English code-switched dialogue")
        base_rule = (
            f"5. Generate the instruction and response in Hinglish ({intensity_notes}) "
            "written primarily in Latin script with standard technical terminology."
        )
    elif lang in ("indic_multilingual", "indic"):
        base_rule = (
            "5. Generate the instruction and response in an Indic language (e.g., Hindi, Tamil, Telugu, "
            "Bengali, Marathi), or natural Indic-English code-switched dialogue."
        )
    elif lang in ("bn", "bengali"):
        base_rule = "5. Generate the instruction and response strictly in Bengali (বাংলা) script."
    elif lang in ("ta", "tamil"):
        base_rule = "5. Generate the instruction and response strictly in Tamil (தமிழ்) script."
    elif lang in ("te", "telugu"):
        base_rule = "5. Generate the instruction and response strictly in Telugu (తెలుగు) script."
    elif lang in ("mr", "marathi"):
        base_rule = "5. Generate the instruction and response strictly in Marathi (मराठी) using Devanagari script."
    elif lang in ("gu", "gujarati"):
        base_rule = "5. Generate the instruction and response strictly in Gujarati (ગુજરાતી) script."
    elif lang in ("kn", "kannada"):
        base_rule = "5. Generate the instruction and response strictly in Kannada (ಕನ್ನಡ) script."
    elif lang in ("ml", "malayalam"):
        base_rule = "5. Generate the instruction and response strictly in Malayalam (മലയാളം) script."
    elif lang in ("pa", "punjabi"):
        base_rule = "5. Generate the instruction and response strictly in Punjabi (ਪੰਜਾਬੀ) using Gurmukhi script."
    elif lang in ("es", "spanish"):
        base_rule = "5. Generate the instruction and response strictly in Spanish (Español)."
    elif lang in ("fr", "french"):
        base_rule = "5. Generate the instruction and response strictly in French (Français)."
    elif lang in ("de", "german"):
        base_rule = "5. Generate the instruction and response strictly in German (Deutsch)."
    elif lang in ("zh", "chinese"):
        base_rule = "5. Generate the instruction and response strictly in Simplified Chinese (中文)."
    elif lang in ("ja", "japanese"):
        base_rule = "5. Generate the instruction and response strictly in Japanese (日本語)."
    elif lang in ("ar", "arabic"):
        base_rule = "5. Generate the instruction and response strictly in Arabic (العربية)."
    else:
        base_rule = f"5. Generate the instruction and response strictly in {language}."

    rules = [base_rule]

    # 2. Formality Register
    if register == "formal":
        rules.append(
            "6. Register & Honorifics: Use a formal, respectful, and professional register. "
            "In Hindi/Indic dialogue, address the user with honorifics ('आप' / 'आपण' / 'நீங்கள்') and polite verbal forms."
        )
    elif register == "casual":
        rules.append(
            "6. Register & Honorifics: Use a friendly, colloquial, peer-to-peer register ('तुम' / casual conversational tone)."
        )
    elif register == "neutral":
        rules.append(
            "6. Register & Honorifics: Use an objective, standard professional register without overly casual or archaic language."
        )

    # 3. Preserved Glossary Terms
    if preserved_terms:
        clean_terms = [f"'{t.strip()}'" for t in preserved_terms if t and t.strip()]
        if clean_terms:
            rules.append(
                f"7. Preserved Glossary: Keep the following domain terms and acronyms verbatim without translation or alteration: {', '.join(clean_terms)}."
            )

    # 4. Parallel Bilingual Bitext
    if parallel_bilingual:
        rules.append(
            "8. Parallel Bilingual Mode: Include accurate parallel English translations in the JSON under "
            "keys 'instruction_en' and 'response_en'."
        )

    # 5. Regional Dialect & Localization
    dialect = (regional_dialect or "standard").lower().strip()
    if dialect == "bambaiya":
        rules.append(
            "9. Regional Dialect: Infuse conversational Bambaiya/Mumbai slang and cadence ('apun', 'bindaas', 'boss', 'tension mat le') where natural."
        )
    elif dialect in ("bhojpuri_influenced", "bhojpuri"):
        rules.append(
            "9. Regional Dialect: Infuse Eastern Hindi / Bhojpuri-influenced syntactic markers and polite regional phrasing ('hum/humar', 'ka ho', 'baat samjhi')."
        )
    elif dialect in ("chennai", "tanglish"):
        rules.append(
            "9. Regional Dialect: Infuse Chennai colloquial Tanglish discourse markers ('da', 'machi', 'pa', 'super ji') where appropriate."
        )
    elif dialect in ("indian_english", "in_en"):
        rules.append(
            "9. Regional Dialect: Use authentic Indian English expressions and syntax ('do the needful', 'prepone', 'revert back', 'itself')."
        )
    elif dialect != "standard":
        rules.append(f"9. Regional Dialect: Follow the {regional_dialect} dialectal nuances.")

    # 6. Numbering & Currency Standardization
    num_fmt = (number_formatting or "indian_lakhs").lower().strip()
    if num_fmt == "indian_lakhs":
        rules.append(
            "10. Numbering & Currency: Use the Indian numbering system (Lakhs and Crores, e.g. 1,50,000 / 1,20,00,000) and currency symbol '₹' (INR). Do NOT use Western Millions or Billions."
        )
    elif num_fmt == "western_millions":
        rules.append(
            "10. Numbering & Currency: Use Western decimal numbering (e.g. 150,000 / millions / billions)."
        )

    # 7. Voice AI Speech-Ready Normalization
    if speech_normalization:
        rules.append(
            "11. Voice AI Speech Normalization: Verbalize numbers, currencies, and technical acronyms into spoken phonetic words suitable for TTS and ASR training (e.g., '₹500' -> 'panch sau rupaye', 'GST' -> 'जीएसटी')."
        )

    # 8. Multi-Turn Language Drift
    if turn_language_drift:
        rules.append(
            "12. Conversational Language Drift: In multi-turn dialogue, simulate realistic language drift where initial turns start in one language/code-mix (e.g., English or light Hinglish) and evolve into vernacular over progressive turns."
        )

    # 9. DPO Alignment & Refusal Pairs
    if generate_dpo_refusal_pairs:
        rules.append(
            "13. DPO Contrastive Pair: Output a JSON with 'instruction', 'response' (chosen helpful response with statutory disclaimers), and 'rejected_response' (flawed, hallucinated, or ungrounded response lacking required safety disclaimers)."
        )

    # 10. Chain-of-Thought (CoT) Reasoning Directive
    if enable_cot_reasoning:
        rules.append(f"14. {build_cot_prompt_directive(language=language)}")

    return "\n".join(rules)


class SeedlessGenerator:
    def __init__(self, router: ProviderRouter, config: dict):
        self.router = router
        self.config = config
        from pipeline.prompt_breeder import PromptBreeder
        self.prompt_breeder = PromptBreeder(router=router, config=config)
        self.use_optimization = config.get("enable_prompt_optimization", True)
        # Fix #5: track generated topics to avoid duplicates
        self._seen_topics: set[str] = set()

    def reset_seen_topics(self) -> None:
        """Call this at the start of a new generation batch."""
        self._seen_topics = set()

    def _topic_key(self, instruction: str) -> str:
        """Normalise an instruction to a canonical topic key for dedup."""
        # Strip punctuation, lowercase, keep normalized text up to 240 chars for dedup
        key = re.sub(r'[^\w\s]', '', instruction.lower()).strip()
        key = re.sub(r'\s+', ' ', key)
        return key[:240]

    async def generate_sample(
        self,
        plan: DatasetPlan,
        cell: dict,
        cell_index: int = 0,
        total_cells: int = 1,
    ) -> ConstructedSample:
        """
        Generate a single sample.

        Fixes applied:
          #2 — difficulty_tier varied based on cell attributes
          #4 — temporal/live-data instructions are rejected and regenerated
          #5 — duplicate topics tracked and rejected
        """
        dataset_type = str(self.config.get("dataset_type", "sft")).lower()
        tier = _resolve_difficulty_tier(cell, cell_index, total_cells)

        if "conversational" in dataset_type:
            return await self._generate_conversational(plan, cell, tier)
        else:
            return await self._generate_sft(plan, cell, tier)

    # ── SFT single-turn ───────────────────────────────────────────────────────

    async def _generate_sft(
        self, plan: DatasetPlan, cell: dict, tier: int
    ) -> ConstructedSample:
        lang_rule = _build_language_instruction(
            language=self.config.get("language", "en"),
            script_mode=self.config.get("script_mode", "native"),
            formality_register=self.config.get("formality_register", "formal"),
            code_switch_intensity=self.config.get("code_switch_intensity", "balanced"),
            preserved_terms=self.config.get("preserved_terms", []),
            parallel_bilingual=self.config.get("parallel_bilingual", False),
            regional_dialect=self.config.get("regional_dialect", "standard"),
            number_formatting=self.config.get("number_formatting", "indian_lakhs"),
            generate_dpo_refusal_pairs=self.config.get("generate_dpo_refusal_pairs", False),
            speech_normalization=self.config.get("speech_normalization", False),
            turn_language_drift=self.config.get("turn_language_drift", False),
            enable_cot_reasoning=self.config.get("enable_cot_reasoning", False),
        )

        tool_prompt = ""
        ds_type = str(self.config.get("dataset_type", "")).lower()
        if ds_type == "tool_calling":
            tools = self.config.get("tools_definition") or DEFAULT_FINANCE_TOOLS
            tool_prompt = "\n" + build_tool_calling_system_prompt(tools)

        pref_prompt = ""
        if ds_type in ("kto", "simpo"):
            pref_prompt = "\n" + build_preference_directive(ds_type)

        rag_prompt = ""
        if ds_type == "rag":
            rag_prompt = "\n" + build_rag_prompt_directive(include_hard_negatives=True)

        multi_turn_prompt = ""
        if ds_type == "multi_turn":
            multi_turn_prompt = "\n" + build_multi_turn_directive(num_turns=4, language=lang)

        dialectic_prompt = ""
        if ds_type == "dialectic":
            dialectic_prompt = "\n" + build_dialectic_prompt_directive(domain=plan.domain, rounds=2)

        system_prompt = (
            f"You are an expert dataset generator specializing in the '{plan.domain}' domain. "
            f"Your objective: {plan.objective}.\n"
            f"Roles involved: {', '.join(plan.roles)}.\n"
            f"Constraints to follow:\n" + "\n".join(f"- {c}" for c in plan.constraints) + "\n\n"
            "IMPORTANT RULES:\n"
            "1. Do NOT generate questions about the current time, today's date, live weather, "
            "   current prices, stock values, or any other real-time data.\n"
            "2. Generate timeless, factual, or creative instruction-response pairs only.\n"
            "3. Output ONLY a JSON object with keys: instruction, response, input (null).\n"
            "4. Do not include markdown wrappers, fences, or text outside the JSON.\n"
            f"{lang_rule}"
            f"{tool_prompt}"
            f"{pref_prompt}"
            f"{rag_prompt}"
            f"{multi_turn_prompt}"
            f"{dialectic_prompt}"
        )

        user_message = (
            f"Generate a high-quality training sample targeting these attributes:\n"
            f"{json.dumps(cell, indent=2)}\n\n"
            "Output target JSON:"
        )

        max_attempts = self.config.get("regeneration_attempts", 3)

        for attempt in range(max_attempts):
            try:
                response = await self.router.route(
                    TaskType.TEXT_GENERATION,
                    prompt=user_message,
                    system_prompt=system_prompt,
                    temperature=min(0.95, 0.7 + (attempt * 0.1)),
                    bypass_cache=True,
                )

                if response and response.content:
                    data = _extract_json_object(response.content)
                    raw_inst = data.get("instruction", "")
                    raw_resp = data.get("response", "")

                    if isinstance(raw_inst, (dict, list)):
                        instruction = json.dumps(raw_inst, ensure_ascii=False)
                    else:
                        instruction = str(raw_inst or "").strip()

                    if isinstance(raw_resp, (dict, list)):
                        resp_text = json.dumps(raw_resp, ensure_ascii=False)
                    else:
                        resp_text = str(raw_resp or "").strip()

                    if not instruction or not resp_text:
                        logger.warning("Empty instruction/response on attempt %d", attempt + 1)
                        continue

                    # Fix #4: reject temporal hallucination questions
                    if _is_temporal_hallucination(instruction):
                        logger.warning(
                            "Rejected temporal hallucination instruction (attempt %d): %s",
                            attempt + 1, instruction[:80],
                        )
                        continue

                    # Fix #5: reject duplicate topics
                    topic_key = self._topic_key(instruction)
                    if topic_key in self._seen_topics:
                        logger.warning(
                            "Rejected duplicate topic (attempt %d): %s", attempt + 1, topic_key
                        )
                        continue

                    self._seen_topics.add(topic_key)

                    # 1. Indian PII detection & masking
                    pii_found = {}
                    if self.config.get("mask_indian_pii", True):
                        pii_found = {
                            **detect_indian_pii(instruction),
                            **detect_indian_pii(resp_text),
                        }
                        instruction = mask_indian_pii(instruction, replacement_mode="redact")
                        resp_text = mask_indian_pii(resp_text, replacement_mode="redact")

                    # 2. Chat noise / transliteration shorthand augmentation on instruction
                    chat_noise_level = float(self.config.get("chat_noise_level", 0.0) or 0.0)
                    if chat_noise_level > 0.0:
                        instruction = inject_chat_noise(instruction, noise_level=chat_noise_level)

                    # 3. Voice AI verbalized speech normalization
                    if self.config.get("speech_normalization", False):
                        resp_text = verbalize_for_speech(resp_text, language=self.config.get("language", "hi"))

                    # 4. Currency standardization
                    if self.config.get("number_formatting", "indian_lakhs") == "indian_lakhs":
                        resp_text = standardize_currency_text(resp_text, target_symbol="₹")

                    meta = {
                        **cell,
                        "type": "synthetic_seedless",
                        "language": self.config.get("language", "en"),
                        "script_mode": self.config.get("script_mode", "native"),
                        "formality_register": self.config.get("formality_register", "formal"),
                        "code_switch_intensity": self.config.get("code_switch_intensity", "balanced"),
                        "preserved_terms": self.config.get("preserved_terms", []),
                        "parallel_bilingual": self.config.get("parallel_bilingual", False),
                        "regional_dialect": self.config.get("regional_dialect", "standard"),
                        "number_formatting": self.config.get("number_formatting", "indian_lakhs"),
                        "chat_noise_level": chat_noise_level,
                        "speech_normalization": self.config.get("speech_normalization", False),
                        "mask_indian_pii": self.config.get("mask_indian_pii", True),
                        "generate_dpo_refusal_pairs": self.config.get("generate_dpo_refusal_pairs", False),
                        "turn_language_drift": self.config.get("turn_language_drift", False),
                        "enable_cot_reasoning": self.config.get("enable_cot_reasoning", False),
                        "curriculum_sort": self.config.get("curriculum_sort", "none"),
                        "pii_detected": pii_found,
                    }

                    thought_trace, _ = extract_thought_and_solution(resp_text)
                    if thought_trace:
                        meta["thought_trajectory"] = thought_trace

                    if data.get("tool_calls"):
                        meta["tool_calls"] = data.get("tool_calls")

                    if data.get("rejected_response"):
                        rejected_text = str(data.get("rejected_response"))
                        if self.config.get("mask_indian_pii", True):
                            rejected_text = mask_indian_pii(rejected_text, replacement_mode="redact")
                        meta["rejected_response"] = rejected_text

                    if ds_type == "kto":
                        meta["kto"] = {
                            "label": data.get("kto_label", True),
                            "feedback_reason": data.get("feedback_reason", "Statutory accuracy and alignment"),
                        }
                    elif ds_type == "simpo":
                        c_len = len(resp_text.split())
                        rej = str(data.get("rejected_response", "") or "")
                        r_len = len(rej.split())
                        meta["simpo"] = {
                            "target_margin": 0.5,
                            "chosen_word_count": c_len,
                            "rejected_word_count": r_len,
                            "length_ratio": round(c_len / max(r_len, 1), 2),
                        }
                    elif ds_type == "rag":
                        pos_ctx = data.get("positive_contexts") or []
                        neg_ctx = data.get("hard_negatives") or []
                        citations = data.get("citations") or []
                        meta["rag"] = {
                            "positive_contexts": pos_ctx,
                            "hard_negatives": neg_ctx,
                            "citations": citations,
                        }
                    elif ds_type == "multi_turn":
                        raw_turns = data.get("turns") or []
                        coherence = evaluate_dialogue_coherence(raw_turns)
                        meta["multi_turn"] = {
                            "turn_count": len(raw_turns),
                            "coherence": coherence,
                            "turns": raw_turns,
                        }
                    elif ds_type == "dialectic":
                        rounds = data.get("debate_rounds") or []
                        verdict = str(data.get("verdict", ""))
                        coherence = evaluate_dialectic_coherence(rounds, verdict)
                        meta["dialectic"] = {
                            "rounds_count": len(rounds),
                            "coherence": coherence,
                            "verdict": verdict,
                            "personas": data.get("personas", []),
                        }

                    if data.get("instruction_en") and data.get("response_en"):
                        meta["parallel_en"] = {
                            "instruction": data.get("instruction_en"),
                            "response": data.get("response_en"),
                        }
                        fidelity = evaluate_fidelity(data.get("instruction_en"), instruction)
                        meta["fidelity_metrics"] = fidelity

                    if data.get("instruction_romanized") and data.get("response_romanized"):
                        meta["romanized"] = {
                            "instruction": data.get("instruction_romanized"),
                            "response": data.get("response_romanized"),
                        }

                    return ConstructedSample(
                        instruction=instruction,
                        response=resp_text,
                        input=data.get("input"),
                        metadata=meta,
                        difficulty_tier=tier,      # Fix #2
                        curriculum_order=0,
                    )

            except Exception as e:
                logger.warning("SFT sample generation failed (attempt %d): %s", attempt + 1, e)

        return ConstructedSample(
            instruction="",
            response="",
            input=None,
            metadata={
                **cell,
                "type": "synthetic_seedless_failed",
                "language": self.config.get("language", "en"),
                "script_mode": self.config.get("script_mode", "native"),
                "formality_register": self.config.get("formality_register", "formal"),
                "code_switch_intensity": self.config.get("code_switch_intensity", "balanced"),
                "preserved_terms": self.config.get("preserved_terms", []),
                "parallel_bilingual": self.config.get("parallel_bilingual", False),
                "regional_dialect": self.config.get("regional_dialect", "standard"),
                "number_formatting": self.config.get("number_formatting", "indian_lakhs"),
                "chat_noise_level": float(self.config.get("chat_noise_level", 0.0) or 0.0),
                "speech_normalization": self.config.get("speech_normalization", False),
                "mask_indian_pii": self.config.get("mask_indian_pii", True),
                "generate_dpo_refusal_pairs": self.config.get("generate_dpo_refusal_pairs", False),
                "turn_language_drift": self.config.get("turn_language_drift", False),
            },
            difficulty_tier=tier,
            curriculum_order=0,
        )

    # ── Conversational multi-turn ─────────────────────────────────────────────

    async def _generate_conversational(
        self, plan: DatasetPlan, cell: dict, tier: int
    ) -> ConstructedSample:
        lang_rule = _build_language_instruction(
            language=self.config.get("language", "en"),
            script_mode=self.config.get("script_mode", "native"),
            formality_register=self.config.get("formality_register", "formal"),
            code_switch_intensity=self.config.get("code_switch_intensity", "balanced"),
            preserved_terms=self.config.get("preserved_terms", []),
            parallel_bilingual=self.config.get("parallel_bilingual", False),
            regional_dialect=self.config.get("regional_dialect", "standard"),
            number_formatting=self.config.get("number_formatting", "indian_lakhs"),
            generate_dpo_refusal_pairs=self.config.get("generate_dpo_refusal_pairs", False),
            speech_normalization=self.config.get("speech_normalization", False),
            turn_language_drift=self.config.get("turn_language_drift", False),
        )
        system_prompt = (
            f"You are an expert conversational dataset generator specializing in the '{plan.domain}' domain. "
            f"Your objective: {plan.objective}.\n"
            f"Roles involved: {', '.join(plan.roles)}.\n"
            f"Constraints to follow:\n" + "\n".join(f"- {c}" for c in plan.constraints) + "\n\n"
            "You MUST output exactly a JSON object matching this schema:\n"
            "{\n"
            "  \"conversation\": [\n"
            "    {\"role\": \"patient\", \"content\": \"...\"},\n"
            "    {\"role\": \"doctor\", \"content\": \"...\"},\n"
            "    ...\n"
            "  ]\n"
            "}\n"
            "IMPORTANT: Do NOT include questions about current time, live weather, or real-time data.\n"
            "Do NOT include markdown wrappers, fences, or text outside the JSON.\n"
            f"{lang_rule}"
        )

        user_message = (
            f"Generate a high-quality multi-turn clinical conversation targeting these attributes:\n"
            f"{json.dumps(cell, indent=2)}\n\nOutput target JSON:"
        )

        try:
            response = await self.router.route(
                TaskType.TEXT_GENERATION,
                prompt=user_message,
                system_prompt=system_prompt,
                temperature=0.7,
                bypass_cache=True,
            )

            if response and response.content:
                clean = response.content.strip()
                if clean.startswith("```"):
                    lines = clean.split("\n")
                    lines = lines[1:] if lines[0].startswith("```") else lines
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean = "\n".join(lines).strip()

                try:
                    data = json.loads(clean)
                except json.JSONDecodeError:
                    m = re.search(r"\{.*\}", clean, re.DOTALL)
                    data = json.loads(m.group(0)) if m else {}

                conversation = data.get("conversation", [])
                if isinstance(conversation, list) and len(conversation) > 0:
                    chat_noise_level = float(self.config.get("chat_noise_level", 0.0) or 0.0)
                    mask_pii = self.config.get("mask_indian_pii", True)
                    speech_norm = self.config.get("speech_normalization", False)
                    pii_found = {}

                    processed_conv = []
                    for t in conversation:
                        role = t.get("role", "")
                        text = t.get("content", "")
                        if mask_pii:
                            found = detect_indian_pii(text)
                            if found:
                                pii_found.update(found)
                            text = mask_indian_pii(text, replacement_mode="redact")

                        # If user or patient turn, inject chat noise if enabled
                        if role.lower() in ("patient", "user", "human") and chat_noise_level > 0.0:
                            text = inject_chat_noise(text, noise_level=chat_noise_level)
                        elif role.lower() in ("doctor", "assistant", "bot") and speech_norm:
                            text = verbalize_for_speech(text, language=self.config.get("language", "hi"))

                        processed_conv.append({"role": role, "content": text})

                    first_turn = processed_conv[0].get("content", "")
                    full_dialogue = "\n\n".join(
                        f"{t.get('role', '').capitalize()}: {t.get('content', '')}"
                        for t in processed_conv
                    )
                    return ConstructedSample(
                        instruction=first_turn,
                        response=full_dialogue,
                        input=None,
                        conversation=processed_conv,
                        metadata={
                            **cell,
                            "type": "synthetic_seedless",
                            "language": self.config.get("language", "en"),
                            "script_mode": self.config.get("script_mode", "native"),
                            "formality_register": self.config.get("formality_register", "formal"),
                            "code_switch_intensity": self.config.get("code_switch_intensity", "balanced"),
                            "preserved_terms": self.config.get("preserved_terms", []),
                            "parallel_bilingual": self.config.get("parallel_bilingual", False),
                            "regional_dialect": self.config.get("regional_dialect", "standard"),
                            "number_formatting": self.config.get("number_formatting", "indian_lakhs"),
                            "chat_noise_level": chat_noise_level,
                            "speech_normalization": speech_norm,
                            "mask_indian_pii": mask_pii,
                            "generate_dpo_refusal_pairs": self.config.get("generate_dpo_refusal_pairs", False),
                            "turn_language_drift": self.config.get("turn_language_drift", False),
                            "pii_detected": pii_found,
                        },
                        difficulty_tier=tier,
                        curriculum_order=0,
                    )
        except Exception as e:
            logger.warning("Conversational sample generation failed: %s", e)

        return ConstructedSample(
            instruction="", response="", input=None, conversation=[],
            metadata={
                **cell,
                "type": "synthetic_seedless_failed",
                "language": self.config.get("language", "en"),
                "script_mode": self.config.get("script_mode", "native"),
                "formality_register": self.config.get("formality_register", "formal"),
                "code_switch_intensity": self.config.get("code_switch_intensity", "balanced"),
                "preserved_terms": self.config.get("preserved_terms", []),
                "parallel_bilingual": self.config.get("parallel_bilingual", False),
                "regional_dialect": self.config.get("regional_dialect", "standard"),
                "number_formatting": self.config.get("number_formatting", "indian_lakhs"),
                "chat_noise_level": float(self.config.get("chat_noise_level", 0.0) or 0.0),
                "speech_normalization": self.config.get("speech_normalization", False),
                "mask_indian_pii": self.config.get("mask_indian_pii", True),
                "generate_dpo_refusal_pairs": self.config.get("generate_dpo_refusal_pairs", False),
                "turn_language_drift": self.config.get("turn_language_drift", False),
            },
            difficulty_tier=tier, curriculum_order=0,
        )
