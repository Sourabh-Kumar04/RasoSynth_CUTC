"""
Synthetic Generation Agents - Synthetic data generation and validation

Agents for generating synthetic training data and validating generated
content for quality and safety.
"""

from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime, timezone

from agents.base import Agent, AgentConfig, AgentType, AgentState, TaskResult, AgentContext


class SyntheticGenerationAgent(Agent):
    """Agent for generating synthetic training data."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._generation_stats: Dict[str, Any] = {}
        self._generation_history: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the synthetic generation agent."""
        self.update_state(AgentState.IDLE)
        self._generation_stats = {
            "total_generated": 0,
            "successful": 0,
            "failed": 0,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute synthetic data generation."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"config": task}
            config = {**task_input.get("config", {}), **task_input}
            count = config.get("count", 100)
            template = config.get("template", {})
            domain = config.get("domain", "general")
            generator = config.get("generator")

            generated = await self._generate_synthetic(count, template, domain, generator, context)

            self._generation_stats["total_generated"] += len(generated)
            self._generation_history.append({
                "count": len(generated),
                "domain": domain,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "generated_samples": generated,
                    "count": len(generated),
                    "quality_metrics": await self._assess_quality(generated),
                },
                confidence=0.82 if generated else 0.0,
                execution_time_ms=execution_time,
                artifacts={"synthetic_samples": generated},
                metrics={
                    "generated_count": len(generated),
                    "success_rate": len(generated) / max(count, 1),
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _generate_synthetic(
        self,
        count: int,
        template: Dict,
        domain: str,
        generator: Optional[Callable[..., Awaitable[List[Dict[str, Any]]]]],
        context: AgentContext,
    ) -> List[Dict[str, Any]]:
        """Delegate generation to a configured provider; never fabricate samples.

        The application pipeline owns the model/router invocation.  This role
        enforces the agent contract and records provenance around that real
        output.  It intentionally returns no samples when no generator is
        supplied, so an unavailable provider cannot look like a successful run.
        """
        if not callable(generator):
            return []

        generated = await generator(
            count=min(max(int(count), 0), 1000),
            template=template,
            domain=domain,
            context=context,
        )
        samples = [sample for sample in (generated or []) if isinstance(sample, dict)]
        for sample in samples:
            metadata = sample.setdefault("metadata", {})
            metadata.setdefault("source", "synthetic")
            metadata.setdefault("domain", domain)
            metadata.setdefault("generated_at", datetime.now(timezone.utc).isoformat())

        self._generation_stats["successful"] += len(samples)
        return samples

    async def _assess_quality(self, samples: List[Dict]) -> Dict[str, float]:
        """Assess quality of generated samples."""
        if not samples:
            return {"diversity_score": 0.0, "coherence_score": 0.0, "novelty_score": 0.0, "safety_score": 0.0}
        unique = len({str(sample.get("content") or sample.get("instruction") or sample) for sample in samples})
        complete = sum(bool(sample.get("instruction") or sample.get("content")) and bool(sample.get("response") or sample.get("output")) for sample in samples)
        return {
            "diversity_score": round(unique / len(samples), 3),
            "coherence_score": round(complete / len(samples), 3),
            "novelty_score": 0.0,  # Requires a reference corpus; do not invent it.
            "safety_score": 0.0,  # Requires the configured safety reviewer.
        }

    async def cleanup(self) -> None:
        """Cleanup synthetic generation agent resources."""
        self._generation_stats.clear()
        self._generation_history.clear()
        self.update_state(AgentState.TERMINATED)


class ValidationAgent(Agent):
    """Agent for validating synthetic data quality and safety."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._validation_results: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the validation agent."""
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute validation on synthetic data."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"samples": task}
            samples = task_input.get("samples", [])
            validation_types = task_input.get("validation_types", ["quality", "safety", "consistency"])

            results = await self._validate_samples(samples, validation_types)

            self._validation_results.append({
                "samples_count": len(samples),
                "passed": results["passed"],
                "failed": results["failed"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "validation_results": results,
                    "passed_samples": results["passed"],
                    "failed_samples": results["failed"],
                    "recommendations": results["recommendations"],
                },
                confidence=0.88,
                execution_time_ms=execution_time,
                metrics={
                    "samples_validated": len(samples),
                    "pass_rate": results["passed"] / max(len(samples), 1),
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _validate_samples(
        self,
        samples: List[Any],
        validation_types: List[str]
    ) -> Dict[str, Any]:
        """Validate samples against multiple criteria."""
        results = {
            "quality": {"passed": 0, "failed": 0},
            "safety": {"passed": 0, "failed": 0},
            "consistency": {"passed": 0, "failed": 0},
        }
        recommendations = []

        for sample in samples[:1000]:
            metadata = sample.get("metadata", {}) if isinstance(sample, dict) else {}
            for vtype in validation_types:
                if vtype == "quality":
                    score = 1.0 if isinstance(sample, dict) and (sample.get("instruction") or sample.get("input")) and (sample.get("response") or sample.get("output")) else 0.0
                elif vtype == "safety":
                    # Safety is passable only when a real upstream review has
                    # left an explicit result.  Unknown is not silently safe.
                    score = float(metadata.get("safety_score", 0.0) or 0.0)
                elif vtype == "consistency":
                    score = float(metadata.get("quality_score", 0.0) or 0.0)
                else:
                    score = 0.0

                if score >= 0.7:
                    results[vtype]["passed"] += 1
                else:
                    results[vtype]["failed"] += 1

        total = len(samples) * len(validation_types)
        total_passed = sum(r["passed"] for r in results.values())

        if total_passed / max(total, 1) < 0.8:
            recommendations.append("Consider regenerating low-quality samples")
        if results["safety"]["failed"] > 10:
            recommendations.append("Review safety filtering thresholds")

        return {
            **results,
            "passed": sum(r["passed"] for r in results.values()),
            "failed": sum(r["failed"] for r in results.values()),
            "recommendations": recommendations,
        }

    async def cleanup(self) -> None:
        """Cleanup validation agent resources."""
        self._validation_results.clear()
        self.update_state(AgentState.TERMINATED)


class ConsensusAgent(Agent):
    """Agent for multi-model consensus validation."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._consensus_rounds: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the consensus agent."""
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute consensus validation with multiple models."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"samples": task}
            samples = task_input.get("samples", [])
            num_models = task_input.get("num_models", 3)
            threshold = task_input.get("agreement_threshold", 0.66)

            results = await self._reach_consensus(samples, num_models, threshold)

            self._consensus_rounds.append({
                "samples": len(samples),
                "models": num_models,
                "agreement_rate": results["agreement_rate"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "consensus_results": results["agreed"],
                    "disagreements": results["disagreed"],
                    "agreement_rate": results["agreement_rate"],
                },
                confidence=0.9,
                execution_time_ms=execution_time,
                metrics={
                    "consensus_rate": results["agreement_rate"],
                    "agreed_samples": len(results["agreed"]),
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _reach_consensus(
        self,
        samples: List[Any],
        num_models: int,
        threshold: float
    ) -> Dict[str, Any]:
        """Reach consensus on sample classifications."""
        agreed = []
        disagreed = []

        for i, sample in enumerate(samples[:1000]):
            metadata = sample.get("metadata", {}) if isinstance(sample, dict) else {}
            votes = metadata.get("review_votes") or (sample.get("review_votes") if isinstance(sample, dict) else None)
            votes = [int(bool(vote)) for vote in (votes or [])]
            # Missing independent votes is a disagreement requiring review, not
            # a fabricated consensus.
            if len(votes) < num_models:
                disagreed.append({
                    "sample_id": i,
                    "votes": votes,
                    "disagreement_level": 1.0,
                    "reason": "insufficient_independent_votes",
                })
                continue
            agreement = votes.count(1) / len(votes)

            if agreement >= threshold or (1 - agreement) >= threshold:
                agreed.append({
                    "sample_id": i,
                    "classification": 1 if agreement >= threshold else 0,
                    "agreement": max(agreement, 1 - agreement),
                    "votes": votes,
                })
            else:
                disagreed.append({
                    "sample_id": i,
                    "votes": votes,
                    "disagreement_level": abs(agreement - 0.5) * 2,
                })

        return {
            "agreed": agreed,
            "disagreed": disagreed,
            "agreement_rate": len(agreed) / max(len(samples), 1),
        }

    async def cleanup(self) -> None:
        """Cleanup consensus agent resources."""
        self._consensus_rounds.clear()
        self.update_state(AgentState.TERMINATED)
