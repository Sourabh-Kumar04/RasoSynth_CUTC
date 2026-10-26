"""
Quality Agents - Quality evaluation, deduplication, and toxicity detection

Agents for scoring dataset quality, detecting duplicates, and identifying
potentially harmful or toxic content.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import hashlib
import json
import re

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
        start_time = datetime.now(timezone.utc)
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
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
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
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

            text = self._sample_text(sample)
            metadata = sample.get("metadata", {}) if isinstance(sample, dict) else {}
            provenance = metadata.get("provenance", {}) if isinstance(metadata, dict) else {}
            for dim in dimensions:
                score = self._score_dimension(dim, text, sample, provenance)
                threshold = self._quality_thresholds.get(dim, 0.7)
                sample_scores[dim] = {
                    "score": score,
                    "passed": score >= threshold,
                    "threshold": threshold,
                }

            overall = sum(s["score"] for s in sample_scores.values()) / max(len(sample_scores), 1)
            sample_scores["overall"] = {
                "score": overall,
                "passed": overall >= 0.7,
            }

            scores.append({
                "sample_id": i,
                "scores": sample_scores,
            })

        return scores

    @staticmethod
    def _sample_text(sample: Any) -> str:
        if isinstance(sample, dict):
            return " ".join(str(sample.get(key, "")) for key in ("instruction", "input", "output", "response", "content"))
        return str(sample)

    @staticmethod
    def _score_dimension(dim: str, text: str, sample: Any, provenance: Dict[str, Any]) -> float:
        """A deterministic, explainable pre-screen—not a claim of LLM judgment."""
        normalized = " ".join(text.split())
        length_score = min(len(normalized) / 240, 1.0)
        if dim == "completeness":
            return round(length_score, 3)
        if dim == "accuracy":
            return 0.9 if provenance.get("source_url") else 0.45
        if dim == "freshness":
            return 0.8 if provenance.get("retrieved_at") else 0.5
        if dim == "consistency":
            return 0.9 if isinstance(sample, dict) and any(sample.get(k) for k in ("output", "response")) else 0.5
        return round(0.4 + 0.6 * length_score, 3)

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
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"samples": task}
            samples = task_input.get("samples", [])
            threshold = task_input.get("similarity_threshold", 0.95)
            method = task_input.get("method", "fingerprint")

            duplicates = await self._find_duplicates(samples, threshold, method)
            unique_samples = await self._remove_duplicates(samples, duplicates)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            self._dedup_stats["total_checked"] += len(samples)
            self._dedup_stats["duplicates_found"] += len(duplicates)

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
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
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
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
            canonical = json.dumps(sample, sort_keys=True, ensure_ascii=False, default=str) if isinstance(sample, dict) else str(sample)
            sample_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

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
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"content": task}
            content = task_input.get("content", [])
            threshold = task_input.get("toxicity_threshold", 0.5)

            results = await self._analyze_toxicity(content, threshold)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            self._toxicity_stats["total_checked"] += len(content)
            self._toxicity_stats["toxic_detected"] += results["toxic_count"]

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
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
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
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

        patterns = {
            "hate": re.compile(r"\b(?:racial slur|ethnic cleansing)\b", re.IGNORECASE),
            "violence": re.compile(r"\b(?:how to kill|build a bomb|mass shooting)\b", re.IGNORECASE),
            "sexual": re.compile(r"\b(?:sexual assault|child sexual)\b", re.IGNORECASE),
            "self_harm": re.compile(r"\b(?:how to suicide|kill myself)\b", re.IGNORECASE),
        }
        for i, item in enumerate(content[:10000]):
            text = str(item)
            matched = [name for name, pattern in patterns.items() if pattern.search(text)]
            # This is a conservative keyword safety screen.  A score of 1 is
            # used only for an explicit match; ambiguous content remains for
            # the configured model/human review instead of being fabricated.
            if matched and 1.0 > threshold:
                category = matched[0]
                toxic_items.append({"idx": i, "score": 1.0, "category": category})
                categories[category] += 1

        return {
            "toxic_count": len(toxic_items),
            "safe_count": len(content) - len(toxic_items),
            "toxic_items": toxic_items,
            "categories": categories,
        }

    async def cleanup(self) -> None:
        """Cleanup toxicity detection agent resources."""
        self.update_state(AgentState.TERMINATED)
