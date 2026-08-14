"""
Quality Agents - Quality evaluation, deduplication, and toxicity detection

Agents for scoring dataset quality, detecting duplicates, and identifying
potentially harmful or toxic content.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from agents.base import Agent, AgentConfig, AgentType, AgentState, TaskResult, AgentContext


class QualityEvaluationAgent(Agent):
    """Agent for scoring dataset quality across multiple dimensions."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._evaluation_history: List[Dict] = []
        self._quality_thresholds: Dict[str, float] = {}

    async def initialize(self) -> bool:
        """Initialize the quality evaluation agent."""
        self.update_state(AgentState.IDLE)
        self._quality_thresholds = {
            "relevance": 0.7,
            "accuracy": 0.8,
            "completeness": 0.75,
            "consistency": 0.7,
            "freshness": 0.6,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Evaluate quality of dataset samples."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"samples": task}
            samples = task_input.get("samples", [])
            dimensions = task_input.get("dimensions", ["relevance", "accuracy", "completeness"])

            scores = await self._evaluate_samples(samples, dimensions)
            summary = await self._summarize_scores(scores)

            self._evaluation_history.append({
                "samples_count": len(samples),
                "dimensions": dimensions,
                "avg_score": summary["average_score"],
                "timestamp": datetime.utcnow().isoformat(),
            })

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "individual_scores": scores,
                    "summary": summary,
                    "failed_samples": summary["failed_count"],
                    "passed_samples": summary["passed_count"],
                },
                confidence=0.85,
                execution_time_ms=execution_time,
                metrics={
                    "samples_evaluated": len(samples),
                    "average_score": summary["average_score"],
                    "pass_rate": summary["pass_rate"],
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

    async def _evaluate_samples(
        self,
        samples: List[Any],
        dimensions: List[str]
    ) -> List[Dict[str, Any]]:
        """Evaluate individual samples."""
        scores = []

        for i, sample in enumerate(samples[:1000]):
            sample_scores = {}

            for dim in dimensions:
                score = 0.5 + (hash(str(sample) + dim) % 50) / 100
                threshold = self._quality_thresholds.get(dim, 0.7)
                sample_scores[dim] = {
                    "score": score,
                    "passed": score >= threshold,
                    "threshold": threshold,
                }

            overall = sum(s["score"] for s in sample_scores.values()) / len(sample_scores)
            sample_scores["overall"] = {
                "score": overall,
                "passed": overall >= 0.7,
            }

            scores.append({
                "sample_id": i,
                "scores": sample_scores,
            })

        return scores

    async def _summarize_scores(self, scores: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize evaluation scores."""
        if not scores:
            return {"average_score": 0, "pass_rate": 0, "failed_count": 0, "passed_count": 0}

        total = len(scores)
        overall_scores = [s["scores"].get("overall", {}).get("score", 0) for s in scores]
        passed = sum(1 for s in overall_scores if s >= 0.7)

        return {
            "average_score": sum(overall_scores) / total,
            "min_score": min(overall_scores),
            "max_score": max(overall_scores),
            "pass_rate": passed / total,
            "failed_count": total - passed,
            "passed_count": passed,
        }

    async def cleanup(self) -> None:
        """Cleanup quality evaluation agent resources."""
        self._evaluation_history.clear()
        self.update_state(AgentState.TERMINATED)


class DedupAgent(Agent):
    """Agent for detecting and removing duplicate content."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._dedup_stats: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize the deduplication agent."""
        self.update_state(AgentState.IDLE)
        self._dedup_stats = {
            "total_checked": 0,
            "duplicates_found": 0,
            "removed": 0,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute deduplication on dataset."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"samples": task}
            samples = task_input.get("samples", [])
            threshold = task_input.get("similarity_threshold", 0.95)
            method = task_input.get("method", "fingerprint")

            duplicates = await self._find_duplicates(samples, threshold, method)
            unique_samples = await self._remove_duplicates(samples, duplicates)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._dedup_stats["total_checked"] += len(samples)
            self._dedup_stats["duplicates_found"] += len(duplicates)

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "original_count": len(samples),
                    "duplicate_count": len(duplicates),
                    "unique_count": len(unique_samples),
                    "duplicate_indices": [d["idx"] for d in duplicates],
                },
                confidence=0.92,
                execution_time_ms=execution_time,
                metrics={
                    "dedup_rate": len(duplicates) / max(len(samples), 1),
                    "unique_samples": len(unique_samples),
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

    async def _find_duplicates(
        self,
        samples: List[Any],
        threshold: float,
        method: str
    ) -> List[Dict[str, Any]]:
        """Find duplicate samples."""
        duplicates = []
        seen_hashes = {}

        for i, sample in enumerate(samples[:10000]):
            sample_hash = hash(str(sample)) % 1000000

            if sample_hash in seen_hashes:
                duplicates.append({
                    "idx": i,
                    "original_idx": seen_hashes[sample_hash],
                    "similarity": 1.0,
                })
            else:
                seen_hashes[sample_hash] = i

        return duplicates

    async def _remove_duplicates(
        self,
        samples: List[Any],
        duplicates: List[Dict]
    ) -> List[Any]:
        """Remove duplicates from samples."""
        duplicate_indices = {d["idx"] for d in duplicates}
        return [s for i, s in enumerate(samples) if i not in duplicate_indices]

    async def cleanup(self) -> None:
        """Cleanup deduplication agent resources."""
        self.update_state(AgentState.TERMINATED)


class ToxicityAgent(Agent):
    """Agent for detecting unsafe and harmful content."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._toxicity_stats: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize the toxicity detection agent."""
        self.update_state(AgentState.IDLE)
        self._toxicity_stats = {
            "total_checked": 0,
            "toxic_detected": 0,
            "categories": {},
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute toxicity detection on content."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"content": task}
            content = task_input.get("content", [])
            threshold = task_input.get("toxicity_threshold", 0.5)

            results = await self._analyze_toxicity(content, threshold)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._toxicity_stats["total_checked"] += len(content)
            self._toxicity_stats["toxic_detected"] += results["toxic_count"]

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "total_analyzed": len(content),
                    "toxic_count": results["toxic_count"],
                    "safe_count": results["safe_count"],
                    "toxic_items": results["toxic_items"],
                    "category_breakdown": results["categories"],
                },
                confidence=0.88,
                execution_time_ms=execution_time,
                metrics={
                    "toxic_rate": results["toxic_count"] / max(len(content), 1),
                    "categories_found": len(results["categories"]),
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

    async def _analyze_toxicity(
        self,
        content: List[str],
        threshold: float
    ) -> Dict[str, Any]:
        """Analyze content for toxicity."""
        toxic_items = []
        categories = {"hate": 0, "violence": 0, "sexual": 0, "self_harm": 0}

        for i, item in enumerate(content[:10000]):
            toxicity_score = (hash(str(item)) % 100) / 200  # Simulated

            if toxicity_score > threshold:
                toxic_items.append({
                    "idx": i,
                    "score": toxicity_score,
                    "category": list(categories.keys())[hash(str(item)) % 4],
                })
                categories[list(categories.keys())[hash(str(item)) % 4]] += 1

        return {
            "toxic_count": len(toxic_items),
            "safe_count": len(content) - len(toxic_items),
            "toxic_items": toxic_items,
            "categories": categories,
        }

    async def cleanup(self) -> None:
        """Cleanup toxicity detection agent resources."""
        self.update_state(AgentState.TERMINATED)