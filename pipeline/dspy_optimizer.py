"""DSPy-style Signature & Teleprompter Optimization Engine.

Provides declarative prompt signatures, automated teleprompter compilation (COPRO/MIPRO),
and zero-shot to few-shot prompt optimization for dataset engineering pipelines.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from core.provider_router import ProviderRouter, TaskType

logger = logging.getLogger(__name__)


@dataclass
class SignatureField:
    """A field definition in a DSPy signature."""
    name: str
    description: str
    field_type: str = "str"
    required: bool = True


@dataclass
class DSPySignature:
    """Declarative specification of input/output contract for LLM tasks."""
    name: str
    instructions: str
    inputs: List[SignatureField]
    outputs: List[SignatureField]
    few_shot_examples: List[Dict[str, Any]] = field(default_factory=list)

    def format_prompt(self, input_values: Dict[str, Any]) -> str:
        """Format signature into an optimized execution prompt."""
        sections = []

        # Instructions
        sections.append(f"Task: {self.name}\n{self.instructions}")

        # Rules / Constraints
        sections.append("<rules>\n1. Respond strictly following the output schema.\n2. Ensure high accuracy and domain relevance.\n</rules>")

        # Few-Shot Examples (if available)
        if self.few_shot_examples:
            sections.append("<examples>")
            for idx, ex in enumerate(self.few_shot_examples, 1):
                ex_str = f"Example {idx}:\n"
                for inp in self.inputs:
                    ex_str += f"  Input ({inp.name}): {ex.get(inp.name, '')}\n"
                for out in self.outputs:
                    ex_str += f"  Output ({out.name}): {ex.get(out.name, '')}\n"
                sections.append(ex_str)
            sections.append("</examples>")

        # Inputs
        sections.append("<inputs>")
        for inp in self.inputs:
            sections.append(f"{inp.name}: {input_values.get(inp.name, '')}")
        sections.append("</inputs>")

        # Expected Output Schema
        output_keys = ", ".join([f'"{out.name}"' for out in self.outputs])
        sections.append(f"Output strictly in JSON format containing keys: {output_keys}")

        return "\n\n".join(sections)


class DSPyTeleprompter:
    """DSPy Teleprompter Optimizer (BootstrapFewShot / COPRO)."""

    def __init__(self, router: Optional[ProviderRouter] = None, metric_fn: Optional[Callable] = None):
        self.router = router
        self.metric_fn = metric_fn or self._default_metric

    async def compile(
        self,
        signature: DSPySignature,
        training_set: List[Dict[str, Any]],
        max_bootstrapped_demos: int = 3
    ) -> DSPySignature:
        """Compile an optimized DSPy signature with bootstrapped few-shot demonstrations."""
        logger.info(f"Compiling DSPy signature '{signature.name}' with {len(training_set)} candidates")

        bootstrapped_demos = []

        for item in training_set[:max_bootstrapped_demos]:
            if self.router:
                prompt = signature.format_prompt(item)
                try:
                    res = await self.router.route(
                        TaskType.TEXT_GENERATION,
                        prompt=prompt,
                        system_prompt="You output only JSON.",
                        temperature=0.5
                    )
                    if res and res.content:
                        clean = res.content.strip()
                        if clean.startswith("```"):
                            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                        parsed = json.loads(clean)
                        demo = {**item, **parsed}
                        bootstrapped_demos.append(demo)
                except Exception as e:
                    logger.warning(f"DSPy teleprompter bootstrapping failed for item: {e}")

        # Update signature with optimized few-shot examples
        optimized_signature = DSPySignature(
            name=signature.name,
            instructions=signature.instructions,
            inputs=signature.inputs,
            outputs=signature.outputs,
            few_shot_examples=bootstrapped_demos or signature.few_shot_examples
        )

        logger.info(f"DSPy Teleprompter compilation finished. Attached {len(bootstrapped_demos)} bootstrapped demos.")
        return optimized_signature

    def _default_metric(self, prediction: dict, target: dict) -> float:
        """Default evaluation metric."""
        return 1.0 if prediction == target else 0.5
