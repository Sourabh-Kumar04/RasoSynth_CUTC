"""PromptBreeder — Self-referential Evolutionary Prompt Optimization.

Inspired by DeepMind's PromptBreeder algorithm for evolving task prompts and mutation prompts
to continuously improve synthetic dataset quality, grounding, and domain alignment.
"""

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from core.provider_router import ProviderRouter, TaskType

logger = logging.getLogger(__name__)

# Standard PromptBreeder Mutation Operators
MUTATION_PROMPTS = [
    "Make the prompt more specific to the target domain, focusing on technical depth and domain terminology.",
    "Add explicit anti-hallucination constraints and XML tag boundaries to enforce strict factual grounding.",
    "Inject few-shot examples illustrating the exact desired output format and structure.",
    "Rephrase the instruction to encourage step-by-step reasoning and detailed explanations.",
    "Simplify the constraints to prevent instruction conflict while maintaining high response quality.",
]


@dataclass
class Individual:
    """An individual in the PromptBreeder population."""
    task_prompt: str
    mutation_prompt: str
    fitness_score: float = 0.0
    generation: int = 0
    metrics: Dict[str, float] = field(default_factory=dict)


class PromptBreeder:
    """Self-referential evolutionary prompt optimizer implementing PromptBreeder."""

    def __init__(self, router: Optional[ProviderRouter] = None, config: Optional[dict] = None):
        self.router = router
        self.config = config or {}
        self.population_size = self.config.get("promptbreeder_pop_size", 4)
        self.max_generations = self.config.get("promptbreeder_generations", 3)

    async def evolve_prompt(
        self,
        base_prompt: str,
        target_domain: str = "general",
        dataset_type: str = "sft",
        generations: Optional[int] = None
    ) -> str:
        """Evolve an optimal task prompt starting from a base prompt.
        
        Runs evolutionary loops: Mutation -> Fitness Evaluation -> Selection.
        """
        generations = generations or self.max_generations
        logger.info(f"Starting PromptBreeder evolution for domain '{target_domain}' ({generations} generations)")

        # Initialize Population
        population: List[Individual] = [
            Individual(task_prompt=base_prompt, mutation_prompt=random.choice(MUTATION_PROMPTS), generation=0)
        ]

        # Populate initial generation with mutated variants
        for i in range(1, self.population_size):
            mutated_prompt = await self._mutate_prompt(base_prompt, target_domain, random.choice(MUTATION_PROMPTS))
            population.append(
                Individual(task_prompt=mutated_prompt, mutation_prompt=random.choice(MUTATION_PROMPTS), generation=0)
            )

        # Evaluate Initial Population
        for ind in population:
            ind.fitness_score = await self._evaluate_fitness(ind.task_prompt, target_domain)

        # Evolutionary Loop
        for gen in range(1, generations + 1):
            logger.info(f"PromptBreeder Generation {gen}/{generations}")

            # Sort population by fitness descending
            population.sort(key=lambda x: x.fitness_score, reverse=True)
            elites = population[:2]  # Retain top 2 elite individuals

            new_population: List[Individual] = list(elites)

            # Generate offspring
            while len(new_population) < self.population_size:
                parent = random.choice(elites)
                # First-order or zero-order mutation
                mutator = parent.mutation_prompt
                offspring_prompt = await self._mutate_prompt(parent.task_prompt, target_domain, mutator)
                offspring_mutator = await self._mutate_mutation_prompt(mutator)

                offspring = Individual(
                    task_prompt=offspring_prompt,
                    mutation_prompt=offspring_mutator,
                    generation=gen
                )
                offspring.fitness_score = await self._evaluate_fitness(offspring.task_prompt, target_domain)
                new_population.append(offspring)

            population = new_population

        # Select Best Prompt
        population.sort(key=lambda x: x.fitness_score, reverse=True)
        best_individual = population[0]
        logger.info(f"PromptBreeder evolution completed. Best fitness: {best_individual.fitness_score:.4f}")

        return best_individual.task_prompt

    async def _mutate_prompt(self, task_prompt: str, domain: str, mutator_prompt: str) -> str:
        """Mutate a task prompt using an LLM according to a mutation operator."""
        if not self.router:
            # Fallback heuristic mutation if LLM router is unattached
            return self._heuristic_mutation(task_prompt, domain)

        meta_prompt = (
            f"You are a Prompt Engineering Expert specializing in the '{domain}' domain.\n"
            f"Original Prompt:\n{task_prompt}\n\n"
            f"Mutation Directive:\n{mutator_prompt}\n\n"
            "Task: Rewrite the Original Prompt into an improved, highly effective prompt following the Mutation Directive.\n"
            "Output ONLY the improved prompt, without markdown formatting or introductory explanations."
        )

        try:
            response = await self.router.route(
                TaskType.TEXT_GENERATION,
                prompt=meta_prompt,
                system_prompt="You output only the refined prompt text.",
                temperature=0.7
            )
            if response and response.content:
                refined = response.content.strip()
                if len(refined) > 20:
                    return refined
        except Exception as e:
            logger.warning(f"PromptBreeder LLM mutation failed: {e}. Using heuristic fallback.")

        return self._heuristic_mutation(task_prompt, domain)

    async def _mutate_mutation_prompt(self, mutator_prompt: str) -> str:
        """Mutate the mutation operator prompt itself (Self-referential evolution)."""
        variations = [
            f"Focus on increasing domain precision: {mutator_prompt}",
            f"Focus on factual accuracy and grounding: {mutator_prompt}",
            f"Focus on instruction clarity and format compliance: {mutator_prompt}",
        ]
        return random.choice(variations)

    def _heuristic_mutation(self, prompt: str, domain: str) -> str:
        """Rule-based heuristic mutation when LLM is unavailable."""
        mutations = [
            f"{prompt}\n\n<rules>\n- Ensure all responses are strictly grounded in '{domain}' principles.\n- Provide clear step-by-step reasoning.\n</rules>",
            f"You are an expert AI specialized in {domain}.\n{prompt}\n\nOutput strictly in structured JSON format.",
            f"{prompt}\n\n<constraint>\nDo NOT hallucinate or reference off-topic domains.\n</constraint>",
        ]
        return random.choice(mutations)

    async def _evaluate_fitness(self, prompt: str, domain: str) -> float:
        """Evaluate the fitness of a task prompt across key dimensions."""
        score = 0.5

        # Heuristic scoring signals
        if "<rules>" in prompt or "<constraints>" in prompt or "<xml>" in prompt.lower():
            score += 0.15
        if "json" in prompt.lower():
            score += 0.10
        if "step-by-step" in prompt.lower() or "reasoning" in prompt.lower():
            score += 0.10
        if domain.lower() in prompt.lower():
            score += 0.15

        # Bound score between 0.0 and 1.0
        return min(1.0, max(0.0, score + random.uniform(-0.02, 0.02)))
