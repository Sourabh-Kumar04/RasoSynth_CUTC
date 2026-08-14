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

class CoverageMatrix(BaseModel):
    dimensions: Dict[str, List[Any]] = Field(default_factory=dict, description="Dimensions and their corresponding values")
    cells: List[Dict[str, Any]] = Field(default_factory=list, description="Complete generated coverage matrix combinations")

class DatasetPlanner:
    def __init__(self, router: ProviderRouter, config: dict):
        self.router = router
        self.config = config

    async def create_plan(self, prompt: str) -> DatasetPlan:
        """Analyze user prompt and extract a structured plan using the LLM."""
        system_prompt = (
            "You are an expert ML/AI data architect. Analyze the user prompt to build a comprehensive, structured plan for generating a high-quality dataset. "
            "Output ONLY a valid JSON object matching the schema: "
            "{\n"
            "  \"domain\": \"string\",\n"
            "  \"objective\": \"string\",\n"
            "  \"roles\": [\"string\"],\n"
            "  \"metadata_schema\": {\"field_name\": \"type_description\"},\n"
            "  \"difficulty_distribution\": {\"beginner\": 0.3, \"intermediate\": 0.4, \"advanced\": 0.3},\n"
            "  \"constraints\": [\"string\"],\n"
            "  \"diversity_attributes\": {\"attribute_name\": [\"value1\", \"value2\"]}\n"
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
                    data["diversity_attributes"] = sanitized_attrs

                return DatasetPlan(**data)

        except Exception as e:
            logger.warning(f"Failed to generate structured plan via LLM: {e}. Falling back to domain-specific default plan.")

        # --- Dynamic Domain-Specific Fallback Logic ---
        domain = "general"
        objective = "General instruction following dataset"
        roles = ["User", "Assistant"]
        diversity_attributes = {"topic": ["general_q_a"]}
        
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ["patient", "doctor", "medical", "clinical", "consultation", "diagnosis", "health"]):
            domain = "healthcare"
            objective = "Generate realistic, medically accurate doctor-patient diagnosis and consultation dialogues"
            roles = ["Patient", "Doctor"]
            diversity_attributes = {
                "doctor_specialty": ["General Medicine", "Cardiology", "Neurology", "Dermatology", "Pediatrics"],
                "patient_condition": ["Hypertension", "Diabetes", "Asthma", "Migraine", "Common Cold"]
            }
        elif any(w in prompt_lower for w in ["code", "software", "programming", "python", "developer", "bug"]):
            domain = "software_engineering"
            objective = "Generate high-quality software engineering instruction-response pairs, bug fixes, and code samples"
            roles = ["User", "Developer"]
            diversity_attributes = {
                "language": ["Python", "JavaScript", "Go", "Rust", "C++"],
                "difficulty": ["junior", "mid", "senior"]
            }
        elif any(w in prompt_lower for w in ["finance", "stock", "market", "economy", "investment", "portfolio"]):
            domain = "finance"
            objective = "Generate financial market analysis, investment consulting conversations, and economic advice dialogues"
            roles = ["Client", "Financial Advisor"]
            diversity_attributes = {
                "asset_class": ["Equities", "Fixed Income", "Real Estate", "Crypto"],
                "risk_profile": ["Conservative", "Moderate", "Aggressive"]
            }

        return DatasetPlan(
            domain=domain,
            objective=objective,
            roles=roles,
            metadata_schema={"difficulty": "string"},
            difficulty_distribution={"standard": 1.0},
            constraints=[],
            diversity_attributes=diversity_attributes
        )

class CoveragePlanner:
    def __init__(self, config: dict):
        self.config = config

    def generate_matrix(self, plan: DatasetPlan, target_size: int = 100) -> CoverageMatrix:
        """Generate a coverage matrix by Cartesian combination of diversity attributes."""
        dims = plan.diversity_attributes
        if not dims:
            dims = {"category": ["general_instruction"]}

        import itertools
        import random
        keys = list(dims.keys())
        values = [dims[k] for k in keys]
        
        combinations = list(itertools.product(*values))
        
        # Shuffle combinations to distribute slowest-varying attributes evenly
        rng = random.Random(42)
        rng.shuffle(combinations)
        
        cells = []
        
        # Build balanced cells to match the target size
        for i in range(target_size):
            combo = combinations[i % len(combinations)]
            cell = {keys[j]: combo[j] for j in range(len(keys))}
            cells.append(cell)

        return CoverageMatrix(dimensions=dims, cells=cells)
