import json
import logging
import re
from typing import Optional
from pipeline.construction import ConstructedSample
from pipeline.planner import DatasetPlan
from core.provider_router import ProviderRouter, TaskType

logger = logging.getLogger(__name__)


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

    # Non-greedy search for instruction/response JSON block
    match = re.search(r'\{\s*"instruction"\s*:.*?"response"\s*:.*?\}', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    # Fallback to outer braces if non-greedy failed
    match_outer = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match_outer:
        try:
            return json.loads(match_outer.group(0))
        except Exception:
            pass

    return {}


class SeedlessGenerator:
    def __init__(self, router: ProviderRouter, config: dict):
        self.router = router
        self.config = config
        from pipeline.prompt_breeder import PromptBreeder
        from pipeline.dspy_optimizer import DSPySignature, SignatureField
        self.prompt_breeder = PromptBreeder(router=router, config=config)
        self.use_optimization = config.get("enable_prompt_optimization", True)

    async def generate_sample(self, plan: DatasetPlan, cell: dict) -> ConstructedSample:
        """Generate a single sample based on the dataset plan and a target coverage cell."""
        dataset_type = str(self.config.get("dataset_type", "sft")).lower()

        if "conversational" in dataset_type:
            # Multi-turn conversational prompt
            system_prompt = (
                f"You are an expert conversational dataset generator specializing in the '{plan.domain}' domain. "
                f"Your objective: {plan.objective}.\n"
                f"Roles involved: {', '.join(plan.roles)}.\n"
                f"Constraints to follow:\n" + "\n".join(f"- {c}" for c in plan.constraints) + "\n\n"
                "You MUST output exactly a JSON object matching this schema:\n"
                "{\n"
                "  \"conversation\": [\n"
                "    {\"role\": \"patient\", \"content\": \"patient's dialogue segment\"},\n"
                "    {\"role\": \"doctor\", \"content\": \"doctor's response segment\"},\n"
                "    ...\n"
                "  ]\n"
                "}\n"
                "Guidelines for realistic multi-turn consultations:\n"
                "1. Generate a complete diagnostic consultation workflow: chief complaint, follow-up questions from the doctor, medical history details, physical exam findings, differential diagnosis discussion, final diagnosis, treatment plan, patient questions, and follow-up plan.\n"
                "2. Ensure the dialogue is rich, detailed, and realistic (10 to 40 turns of alternating messages between patient and doctor).\n"
                "3. Ensure the doctor considers multiple differential diagnoses and explains the clinical reasoning behind them before reaching a final diagnosis.\n"
                "4. All patient details (age, occupation, health literacy, history) must be clinically consistent with the specialty and disease (e.g. no 75-year-old pregnant patient, no retired student, no pediatric patient who is 75).\n"
                "5. Do NOT include markdown wrappers, fences, or text outside the JSON."
            )

            user_message = (
                f"Generate a high-quality multi-turn clinical conversation targeting these attributes:\n"
                f"{json.dumps(cell, indent=2)}\n\n"
                "Ensure that the dialogue features roles strictly alternating and matches all the metadata attributes above.\n"
                "Output target JSON:"
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
                    clean_json = response.content.strip()
                    if clean_json.startswith("```"):
                        lines = clean_json.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines[-1].strip() == "```":
                            lines = lines[:-1]
                        clean_json = "\n".join(lines).strip()

                    try:
                        data = json.loads(clean_json)
                    except json.JSONDecodeError:
                        match = re.search(r"\{.*\}", clean_json, re.DOTALL)
                        if match:
                            data = json.loads(match.group(0))
                        else:
                            raise ValueError("No JSON block found")

                    conversation = data.get("conversation", [])
                    if not isinstance(conversation, list) or len(conversation) == 0:
                        raise ValueError("Conversation must be a non-empty list")

                    first_turn = conversation[0].get("content", "")
                    full_dialogue = "\n\n".join(f"{turn.get('role').capitalize()}: {turn.get('content')}" for turn in conversation)

                    return ConstructedSample(
                        instruction=first_turn,
                        response=full_dialogue,
                        input=None,
                        conversation=conversation,
                        metadata={**cell, "type": "synthetic_seedless"},
                        difficulty_tier=3,
                        curriculum_order=0
                    )
            except Exception as e:
                logger.warning(f"Failed to generate conversational sample or parse output: {e}")

            return ConstructedSample(
                instruction="",
                response="",
                input=None,
                conversation=[],
                metadata={**cell, "type": "synthetic_seedless_failed"},
                difficulty_tier=3,
                curriculum_order=0
            )

        else:
            # Single-turn SFT instruction/response prompt
            system_prompt = (
                f"You are an expert dataset generator specializing in the '{plan.domain}' domain. "
                f"Your objective: {plan.objective}.\n"
                f"Roles involved: {', '.join(plan.roles)}.\n"
                f"Constraints to follow:\n" + "\n".join(f"- {c}" for c in plan.constraints) + "\n\n"
                "You MUST output exactly a JSON object matching this schema:\n"
                "{\n"
                "  \"instruction\": \"The instruction, question, user prompt, or clinical description.\",\n"
                "  \"response\": \"The target response, answer, assistant advice, or dialogue continuation.\",\n"
                "  \"input\": null\n"
                "}\n"
                "Do not include markdown wrappers, fences, or text outside the JSON."
            )

            user_message = (
                f"Generate a high-quality training sample targeting these attributes:\n"
                f"{json.dumps(cell, indent=2)}\n\n"
                "Output target JSON:"
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
                    data = _extract_json_object(response.content)
                    if data and data.get("instruction") and data.get("response"):
                        return ConstructedSample(
                            instruction=data.get("instruction", ""),
                            response=data.get("response", ""),
                            input=data.get("input"),
                            metadata={**cell, "type": "synthetic_seedless"},
                            difficulty_tier=3,
                            curriculum_order=0
                        )
            except Exception as e:
                logger.warning(f"Failed to generate seedless sample or parse output: {e}")

            return ConstructedSample(
                instruction="",
                response="",
                input=None,
                metadata={**cell, "type": "synthetic_seedless_failed"},
                difficulty_tier=3,
                curriculum_order=0
            )
