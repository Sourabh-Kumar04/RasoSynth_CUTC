import json
import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from core.provider_router import ProviderRouter, TaskType

logger = logging.getLogger(__name__)

class DatasetPlan(BaseModel):
    domain: str = Field(..., description="Target domain of the dataset")
    objective: str = Field(..., description="Primary objective / goal of the dataset")
    roles: List[str] = Field(default_factory=list, description="Participant roles or personas involved")
    metadata_schema: Dict[str, Any] = Field(default_factory=dict, description="Metadata schema fields and types")
    difficulty_distribution: Dict[str, Any] = Field(default_factory=dict, description="Target proportion of difficulty tiers")
    constraints: List[str] = Field(default_factory=list, description="Extracted constraints and guidelines")
    diversity_attributes: Dict[str, List[Any]] = Field(default_factory=dict, description="Attributes to vary for diversity planning")
    authoritative_sources: List[str] = Field(
        default_factory=list,
        description="Top 2-4 official government, regulatory, or primary statutory portal URLs for this exact topic, e.g. https://heavyindustries.gov.in, https://e-amrit.niti.gov.in for EV, https://pmjay.gov.in for Ayushman Bharat, https://incometaxindia.gov.in for Tax, etc."
    )
    statutory_frameworks: List[str] = Field(
        default_factory=list,
        description="Official statutory acts, regulations, schemes or circular names relevant to this topic"
    )

class CoverageMatrix(BaseModel):
    dimensions: Dict[str, List[Any]] = Field(default_factory=dict, description="Dimensions and their corresponding values")
    cells: List[Dict[str, Any]] = Field(default_factory=list, description="Complete generated coverage matrix combinations")

class DatasetPlanner:
    def __init__(self, router: ProviderRouter, config: dict):
        self.router = router
        self.config = config

    async def create_plan(self, prompt: str) -> DatasetPlan:
        """Analyze user prompt and extract a structured plan using the LLM."""
        target_lang = str(self.config.get("language", "en")).lower().strip()
        lang_directive = (
            f" The target language is strictly '{target_lang}'. Do NOT vary languages or propose non-{target_lang} languages in diversity_attributes."
            if target_lang
            else ""
        )
        system_prompt = (
            "You are an expert ML/AI data architect. Analyze the user prompt to build a comprehensive, structured plan for generating a high-quality dataset "
            "following enterprise curriculum design (Domain, 35/45/20 difficulty split, Structural Invariants, and Anti-Domain boundaries). "
            "Identify the exact official government portal domains/URLs (authoritative_sources) and statutory schemes or acts (statutory_frameworks) governing the topic. "
            f"{lang_directive} "
            "Output ONLY a valid JSON object matching the schema: "
            "{\n"
            "  \"domain\": \"string\",\n"
            "  \"objective\": \"string\",\n"
            "  \"roles\": [\"string\"],\n"
            "  \"metadata_schema\": {\"field_name\": \"type_description\"},\n"
            "  \"difficulty_distribution\": {\"beginner\": 0.35, \"intermediate\": 0.45, \"advanced\": 0.20},\n"
            "  \"constraints\": [\"string\"],\n"
            "  \"diversity_attributes\": {\"attribute_name\": [\"value1\", \"value2\"]},\n"
            "  \"authoritative_sources\": [\"https://official-government-or-regulatory-portal.gov...\"],\n"
            "  \"statutory_frameworks\": [\"Official Statutory Act / Scheme / Regulation\"]\n"
            "}\n"
            "Do not include markdown wrappers, fences, or text outside the JSON."
        )

        user_message = f"User Prompt:\n{prompt}\n\nGenerate the structured DatasetPlan JSON:"

        try:
            response = await self.router.route(
                TaskType.TEXT_GENERATION,
                prompt=user_message,
                system_prompt=system_prompt,
                temperature=0.2,
            )

            if response and response.content:
                clean_json = response.content.strip()
                # Clean up any potential markdown wraps
                if clean_json.startswith("```"):
                    lines = clean_json.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean_json = "\n".join(lines).strip()
                
                # Robust regex JSON extractor fallback if raw parsing fails
                try:
                    data = json.loads(clean_json)
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", clean_json, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                    else:
                        raise ValueError("No JSON block found in response")

                # Sanitize list-of-lists or non-list values in diversity_attributes
                if "diversity_attributes" in data and isinstance(data["diversity_attributes"], dict):
                    sanitized_attrs = {}
                    for k, v in data["diversity_attributes"].items():
                        if isinstance(v, list):
                            sanitized_attrs[k] = v
                        else:
                            sanitized_attrs[k] = [str(v)]
                    
                    # Strictly prevent language drift if target language is specified
                    if target_lang in ("en", "english"):
                        if "language" in sanitized_attrs:
                            sanitized_attrs["language"] = ["English"]
                    elif target_lang:
                        if "language" in sanitized_attrs:
                            sanitized_attrs["language"] = [target_lang]

                    data["diversity_attributes"] = sanitized_attrs

                # Sanitize authoritative_sources and statutory_frameworks
                if "authoritative_sources" in data:
                    if isinstance(data["authoritative_sources"], list):
                        data["authoritative_sources"] = [str(s).strip() for s in data["authoritative_sources"] if s]
                    elif isinstance(data["authoritative_sources"], str):
                        data["authoritative_sources"] = [data["authoritative_sources"].strip()]
                    else:
                        data["authoritative_sources"] = []
                else:
                    data["authoritative_sources"] = []

                if "statutory_frameworks" in data:
                    if isinstance(data["statutory_frameworks"], list):
                        data["statutory_frameworks"] = [str(s).strip() for s in data["statutory_frameworks"] if s]
                    elif isinstance(data["statutory_frameworks"], str):
                        data["statutory_frameworks"] = [data["statutory_frameworks"].strip()]
                    else:
                        data["statutory_frameworks"] = []
                else:
                    data["statutory_frameworks"] = []

                return DatasetPlan(**data)

        except Exception as e:
            logger.warning(f"Failed to generate structured plan via LLM: {e}. Falling back to domain-specific default plan.")

        # --- Dynamic Domain-Specific Fallback Logic ---
        domain = "general"
        objective = "General instruction following dataset"
        roles = ["User", "Assistant"]
        diversity_attributes = {"topic": ["general_q_a"]}
        authoritative_sources = ["https://data.gov.in"]
        statutory_frameworks = ["Digital Personal Data Protection Act", "Right to Information Act"]
        
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ["ev", "electric vehicle", "fame", "charging", "battery", "e-mobility"]):
            domain = "electric_vehicles"
            objective = "Generate comprehensive instruction-response pairs covering EV adoption, subsidies, charging infrastructure, and standards"
            roles = ["Consumer", "EV Specialist"]
            diversity_attributes = {
                "subtopic": ["FAME / PM E-DRIVE Subsidies", "Charging Standards", "Battery Safety", "Vehicle Registration"],
                "vehicle_type": ["2W", "3W", "4W", "Commercial Bus"]
            }
            authoritative_sources = ["https://heavyindustries.gov.in", "https://e-amrit.niti.gov.in", "https://beeindia.gov.in"]
            statutory_frameworks = ["FAME II / PM E-DRIVE Scheme Guidelines", "Central Motor Vehicles Rules (CMVR)", "AIS 156 / AIS 038 Standards"]
        elif any(w in prompt_lower for w in ["patient", "doctor", "medical", "clinical", "consultation", "diagnosis", "health", "ayushman", "pmjay"]):
            domain = "healthcare"
            objective = "Generate realistic, medically accurate doctor-patient diagnosis and consultation dialogues"
            roles = ["Patient", "Doctor"]
            diversity_attributes = {
                "doctor_specialty": ["General Medicine", "Cardiology", "Neurology", "Dermatology", "Pediatrics"],
                "patient_condition": ["Hypertension", "Diabetes", "Asthma", "Migraine", "Common Cold"]
            }
            authoritative_sources = ["https://pmjay.gov.in", "https://mohfw.gov.in", "https://abdm.gov.in"]
            statutory_frameworks = ["Ayushman Bharat Pradhan Mantri Jan Arogya Yojana Guidelines", "Clinical Establishments Act"]
        elif any(w in prompt_lower for w in ["tax", "gst", "itr", "income tax"]):
            domain = "taxation"
            objective = "Generate accurate taxation guidance, compliance instructions, and filing procedures"
            roles = ["Taxpayer", "Tax Consultant"]
            diversity_attributes = {
                "tax_type": ["Income Tax", "GST", "TDS", "Corporate Tax"],
                "difficulty": ["standard", "complex"]
            }
            authoritative_sources = ["https://incometaxindia.gov.in", "https://cbic.gov.in", "https://gst.gov.in"]
            statutory_frameworks = ["Income Tax Act 1961", "Central Goods and Services Tax Act 2017"]
        elif any(w in prompt_lower for w in ["code", "software", "programming", "python", "developer", "bug"]):
            domain = "software_engineering"
            objective = "Generate high-quality software engineering instruction-response pairs, bug fixes, and code samples"
            roles = ["User", "Developer"]
            diversity_attributes = {
                "language": ["Python", "JavaScript", "Go", "Rust", "C++"],
                "difficulty": ["junior", "mid", "senior"]
            }
            authoritative_sources = ["https://docs.python.org", "https://developer.mozilla.org"]
            statutory_frameworks = ["ISO/IEC 25010 Software Engineering Standards", "Open Source Standards"]
        elif any(w in prompt_lower for w in ["finance", "stock", "market", "economy", "investment", "portfolio", "sebi"]):
            domain = "finance"
            objective = "Generate financial market analysis, investment consulting conversations, and economic advice dialogues"
            roles = ["Client", "Financial Advisor"]
            diversity_attributes = {
                "asset_class": ["Equities", "Fixed Income", "Real Estate", "Crypto"],
                "risk_profile": ["Conservative", "Moderate", "Aggressive"]
            }
            authoritative_sources = ["https://www.sebi.gov.in", "https://www.nseindia.com", "https://www.rbi.org.in"]
            statutory_frameworks = ["Securities and Exchange Board of India Act", "RBI Master Directions"]

        return DatasetPlan(
            domain=domain,
            objective=objective,
            roles=roles,
            metadata_schema={"difficulty": "string"},
            difficulty_distribution={"standard": 1.0},
            constraints=[],
            diversity_attributes=diversity_attributes,
            authoritative_sources=authoritative_sources,
            statutory_frameworks=statutory_frameworks,
        )

class CoveragePlanner:
    def __init__(self, config: dict):
        self.config = config

    def generate_matrix(self, plan: DatasetPlan, target_size: int = 100) -> CoverageMatrix:
        """
        Generate a coverage matrix of exactly `target_size` cells.

        Fix #1: cells list is hard-capped at target_size — no overshoot.
        Fix #3: when 'language' is a dimension with multiple values, cells are
                distributed as evenly as possible across all language values so
                each language gets exactly ceil(target_size / n_languages) slots
                before cycling, guaranteeing balance.
        """
        dims = plan.diversity_attributes
        if not dims:
            dims = {"category": ["general_instruction"]}

        import itertools
        import random

        keys = [k for k in dims.keys() if dims[k]]
        if not keys:
            keys = ["category"]
            values = [["general_instruction"]]
        else:
            values = [dims[k] for k in keys]

        combinations = list(itertools.product(*values))
        if not combinations:
            combinations = [tuple("default" for _ in keys)]

        rng = random.Random(42)
        rng.shuffle(combinations)

        # Fix #3: balanced language distribution
        # If 'language' is one of the dimensions, interleave combinations so
        # each language appears in a round-robin order rather than in blocks.
        lang_idx = keys.index("language") if "language" in keys else None
        if lang_idx is not None:
            lang_values = dims["language"]
            n_langs = len(lang_values)
            # Bucket combinations by language
            buckets: dict[str, list] = {lv: [] for lv in lang_values}
            for combo in combinations:
                lang = combo[lang_idx]
                if lang in buckets:
                    buckets[lang].append(combo)
            # Interleave round-robin across languages safely without infinite loops
            active_langs = [lv for lv in lang_values if buckets.get(lv)]
            if active_langs:
                cycle_iters = [itertools.cycle(buckets[lv]) for lv in active_langs]
                interleaved: list = []
                while len(interleaved) < target_size:
                    for it in cycle_iters:
                        interleaved.append(next(it))
                        if len(interleaved) >= target_size:
                            break
                combinations = interleaved

        # Fix #1: build exactly target_size cells — no more, no less
        cells = []
        for i in range(target_size):
            combo = combinations[i % len(combinations)]
            cell = {keys[j]: combo[j] for j in range(len(keys))}
            cells.append(cell)

        return CoverageMatrix(dimensions=dims, cells=cells)
