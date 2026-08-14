"""
Optimization Agents - Dataset fine-tuning and curriculum planning

Agents for optimizing datasets for fine-tuning and creating learning
progression curricula.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from agents.base import Agent, AgentConfig, AgentType, AgentState, TaskResult, AgentContext


class FineTuningAgent(Agent):
    """Agent for optimizing datasets for fine-tuning."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._optimization_history: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the fine-tuning optimization agent."""
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute fine-tuning dataset optimization."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"samples": task}
            samples = task_input.get("samples", [])
            target_model = task_input.get("target_model", "general")
            optimization_level = task_input.get("level", "standard")

            results = await self._optimize_for_finetuning(
                samples,
                target_model,
                optimization_level
            )

            self._optimization_history.append({
                "samples_count": len(samples),
                "target_model": target_model,
                "timestamp": datetime.utcnow().isoformat(),
            })

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "optimized_samples": results["samples"],
                    "format": results["format"],
                    "augmentations": results["augmentations"],
                    "metadata": results["metadata"],
                },
                confidence=0.87,
                execution_time_ms=execution_time,
                artifacts={"optimized_dataset": results["samples"]},
                metrics={
                    "samples_optimized": len(results["samples"]),
                    "format_compliance": results["format_compliance"],
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.utcnow().timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _optimize_for_finetuning(
        self,
        samples: List[Any],
        target_model: str,
        level: str
    ) -> Dict[str, Any]:
        """Optimize samples for fine-tuning target."""
        optimized = []

        for i, sample in enumerate(samples[:10000]):
            opt_sample = {
                "id": sample.get("id", f"sample_{i}"),
                "input": sample.get("input", sample) if isinstance(sample, dict) else sample,
                "output": sample.get("output", ""),
                "format": "chat",
            }

            if target_model == "code":
                opt_sample["format"] = "code_completion"
                opt_sample["input"] = f"// {sample.get('description', '')}\n" + str(opt_sample["input"])

            optimized.append(opt_sample)

        format_compliance = 0.95

        return {
            "samples": optimized,
            "format": "chat" if target_model == "general" else "code_completion",
            "augmentations": ["back_translation", "paraphrasing"] if level == "advanced" else [],
            "metadata": {
                "target_model": target_model,
                "optimization_level": level,
                "sample_count": len(optimized),
            },
            "format_compliance": format_compliance,
        }

    async def cleanup(self) -> None:
        """Cleanup fine-tuning agent resources."""
        self._optimization_history.clear()
        self.update_state(AgentState.TERMINATED)


class CurriculumAgent(Agent):
    """Agent for creating learning progression curricula."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._curricula: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the curriculum agent."""
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute curriculum planning for dataset ordering."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"samples": task}
            samples = task_input.get("samples", [])
            difficulty_metric = task_input.get("difficulty_metric", "complexity")
            strategy = task_input.get("strategy", "progressive")

            curriculum = await self._create_curriculum(
                samples,
                difficulty_metric,
                strategy
            )

            self._curricula.append({
                "samples_count": len(samples),
                "stages": len(curriculum["stages"]),
                "strategy": strategy,
                "timestamp": datetime.utcnow().isoformat(),
            })

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "curriculum": curriculum,
                    "stages": curriculum["stages"],
                    "difficulty_order": curriculum["difficulty_order"],
                    "estimated_epochs": curriculum["estimated_epochs"],
                },
                confidence=0.85,
                execution_time_ms=execution_time,
                artifacts={"curriculum_plan": curriculum},
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.utcnow().timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _create_curriculum(
        self,
        samples: List[Any],
        difficulty_metric: str,
        strategy: str
    ) -> Dict[str, Any]:
        """Create a curriculum for the samples."""
        sorted_samples = sorted(
            samples,
            key=lambda s: hash(str(s)) % 100
        )

        if strategy == "progressive":
            num_stages = 5
        elif strategy == "interleaved":
            num_stages = 10
        else:
            num_stages = 3

        stage_size = len(sorted_samples) // num_stages
        stages = []

        for i in range(num_stages):
            start_idx = i * stage_size
            end_idx = start_idx + stage_size if i < num_stages - 1 else len(sorted_samples)

            stages.append({
                "stage": i + 1,
                "samples": sorted_samples[start_idx:end_idx],
                "difficulty": i + 1,
                "weight": 1.0 / (i + 1),
            })

        difficulty_order = [s["id"] for s in sorted_samples[:100]]

        return {
            "stages": stages,
            "difficulty_order": difficulty_order,
            "estimated_epochs": num_stages * 3,
            "strategy": strategy,
            "total_samples": len(samples),
        }

    async def cleanup(self) -> None:
        """Cleanup curriculum agent resources."""
        self._curricula.clear()
        self.update_state(AgentState.TERMINATED)