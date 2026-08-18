import json
import logging
import re
import math
from typing import Optional
from pipeline.construction import ConstructedSample
from pipeline.planner import DatasetPlan
from core.provider_router import ProviderRouter, TaskType

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
        # Strip punctuation, lowercase, keep first ~60 chars
        key = re.sub(r'[^\w\s]', '', instruction.lower()).strip()
        key = re.sub(r'\s+', ' ', key)
        return key[:60]

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
            "4. Do not include markdown wrappers, fences, or text outside the JSON."
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
                    temperature=0.7,
                    bypass_cache=True,
                )

                if response and response.content:
                    data = _extract_json_object(response.content)
                    instruction = data.get("instruction", "").strip()
                    resp_text = data.get("response", "").strip()

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
                    return ConstructedSample(
                        instruction=instruction,
                        response=resp_text,
                        input=data.get("input"),
                        metadata={**cell, "type": "synthetic_seedless"},
                        difficulty_tier=tier,      # Fix #2
                        curriculum_order=0,
                    )

            except Exception as e:
                logger.warning("SFT sample generation failed (attempt %d): %s", attempt + 1, e)

        return ConstructedSample(
            instruction="",
            response="",
            input=None,
            metadata={**cell, "type": "synthetic_seedless_failed"},
            difficulty_tier=tier,
            curriculum_order=0,
        )

    # ── Conversational multi-turn ─────────────────────────────────────────────

    async def _generate_conversational(
        self, plan: DatasetPlan, cell: dict, tier: int
    ) -> ConstructedSample:
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
            "Do NOT include markdown wrappers, fences, or text outside the JSON."
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
                    first_turn = conversation[0].get("content", "")
                    full_dialogue = "\n\n".join(
                        f"{t.get('role', '').capitalize()}: {t.get('content', '')}"
                        for t in conversation
                    )
                    return ConstructedSample(
                        instruction=first_turn,
                        response=full_dialogue,
                        input=None,
                        conversation=conversation,
                        metadata={**cell, "type": "synthetic_seedless"},
                        difficulty_tier=tier,
                        curriculum_order=0,
                    )
        except Exception as e:
            logger.warning("Conversational sample generation failed: %s", e)

        return ConstructedSample(
            instruction="", response="", input=None, conversation=[],
            metadata={**cell, "type": "synthetic_seedless_failed"},
            difficulty_tier=tier, curriculum_order=0,
        )
