"""
AI-Native Analytics & Telemetry

AI-specific observability including hallucination detection,
reasoning quality monitoring, confidence tracking, and semantic drift detection.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio


class ReasoningQuality(Enum):
    """Reasoning quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILED = "failed"


@dataclass
class HallucinationDetection:
    """Hallucination detection result."""
    text: str
    is_hallucinated: bool
    confidence: float
    flagged_spans: List[Dict] = field(default_factory=list)
    detector_type: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConfidenceMetric:
    """Confidence score metric."""
    sample_id: str
    confidence: float
    reasoning_depth: int
    validation_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SemanticDrift:
    """Semantic drift detection."""
    metric_name: str
    baseline_value: float
    current_value: float
    drift_percent: float
    severity: str = "normal"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AIAnalyticsEngine:
    """Comprehensive AI analytics engine."""

    def __init__(self):
        self._quality_scores: Dict[str, List[float]] = {}
        self._confidence_history: List[ConfidenceMetric] = []
        self._hallucination_history: List[HallucinationDetection] = []
        self._semantic_drift: Dict[str, SemanticDrift] = {}
        self._model_disagreements: List[Dict] = []
        self._max_history = 10000

    def record_quality_score(
        self,
        task_type: str,
        score: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record quality score for a task type."""
        if task_type not in self._quality_scores:
            self._quality_scores[task_type] = []

        self._quality_scores[task_type].append(score)
        if len(self._quality_scores[task_type]) > self._max_history:
            self._quality_scores[task_type] = self._quality_scores[task_type][-self._max_history:]

    def get_quality_trend(self, task_type: str, window: int = 100) -> Dict[str, Any]:
        """Get quality trend for task type."""
        scores = self._quality_scores.get(task_type, [])
        if not scores:
            return {}

        recent = scores[-window:]
        return {
            "task_type": task_type,
            "current_score": recent[-1],
            "avg_score": sum(recent) / len(recent),
            "min_score": min(recent),
            "max_score": max(recent),
            "sample_count": len(recent)
        }

    def record_confidence(self, metric: ConfidenceMetric) -> None:
        """Record confidence metric."""
        self._confidence_history.append(metric)
        if len(self._confidence_history) > self._max_history:
            self._confidence_history = self._confidence_history[-self._max_history:]

    def get_confidence_distribution(self, window: int = 1000) -> Dict[str, Any]:
        """Get confidence score distribution."""
        recent = self._confidence_history[-window:]
        if not recent:
            return {}

        confidences = [m.confidence for m in recent]
        return {
            "avg_confidence": sum(confidences) / len(confidences),
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "low_confidence_count": sum(1 for c in confidences if c < 0.7),
            "high_confidence_count": sum(1 for c in confidences if c >= 0.9),
        }

    def record_hallucination(self, detection: HallucinationDetection) -> None:
        """Record hallucination detection."""
        self._hallucination_history.append(detection)
        if len(self._hallucination_history) > self._max_history:
            self._hallucination_history = self._hallucination_history[-self._max_history:]

    def get_hallucination_rate(self, window: int = 1000) -> Dict[str, Any]:
        """Get hallucination rate."""
        recent = self._hallucination_history[-window:]
        if not recent:
            return {}

        total = len(recent)
        hallucinated = sum(1 for h in recent if h.is_hallucinated)

        return {
            "total_samples": total,
            "hallucinated_count": hallucinated,
            "hallucination_rate": hallucinated / max(total, 1),
            "avg_confidence_when_hallucinated": sum(
                h.confidence for h in recent if h.is_hallucinated
            ) / max(hallucinated, 1) if hallucinated > 0 else 0
        }

    def record_semantic_drift(self, drift: SemanticDrift) -> None:
        """Record semantic drift."""
        self._semantic_drift[drift.metric_name] = drift

    def detect_drift(
        self,
        metric_name: str,
        current_values: List[float],
        baseline_values: List[float]
    ) -> Optional[SemanticDrift]:
        """Detect semantic drift between current and baseline."""
        if len(current_values) != len(baseline_values) or not current_values:
            return None

        current_avg = sum(current_values) / len(current_values)
        baseline_avg = sum(baseline_values) / len(baseline_values)

        if baseline_avg == 0:
            return None

        drift_percent = ((current_avg - baseline_avg) / baseline_avg) * 100

        severity = "normal"
        if abs(drift_percent) > 20:
            severity = "high"
        elif abs(drift_percent) > 10:
            severity = "medium"

        drift = SemanticDrift(
            metric_name=metric_name,
            baseline_value=baseline_avg,
            current_value=current_avg,
            drift_percent=drift_percent,
            severity=severity
        )

        self.record_semantic_drift(drift)
        return drift

    def record_model_disagreement(
        self,
        sample_id: str,
        model1: str,
        model2: str,
        agreement: float
    ) -> None:
        """Record model disagreement."""
        self._model_disagreements.append({
            "sample_id": sample_id,
            "model1": model1,
            "model2": model2,
            "agreement": agreement,
            "timestamp": datetime.utcnow().isoformat()
        })

        if len(self._model_disagreements) > self._max_history:
            self._model_disagreements = self._model_disagreements[-self._max_history:]

    def get_disagreement_rate(self) -> Dict[str, Any]:
        """Get model disagreement rate."""
        if not self._model_disagreements:
            return {}

        agreements = [d["agreement"] for d in self._model_disagreements[-1000:]]
        return {
            "avg_agreement": sum(agreements) / len(agreements),
            "disagreement_rate": sum(1 for a in agreements if a < 0.8) / max(len(agreements), 1)
        }

    def get_ai_health_summary(self) -> Dict[str, Any]:
        """Get AI health summary."""
        return {
            "quality_trends": {
                task_type: self.get_quality_trend(task_type)
                for task_type in self._quality_scores.keys()
            },
            "confidence_distribution": self.get_confidence_distribution(),
            "hallucination_rate": self.get_hallucination_rate(),
            "semantic_drift": [
                {"metric": k, "drift_percent": v.drift_percent, "severity": v.severity}
                for k, v in self._semantic_drift.items()
            ],
            "model_disagreement": self.get_disagreement_rate()
        }


class ReasoningQualityMonitor:
    """Monitors reasoning quality."""

    def __init__(self, analytics: AIAnalyticsEngine):
        self.analytics = analytics

    async def evaluate_reasoning(
        self,
        prompt: str,
        response: str,
        expected_output: Optional[str] = None
    ) -> Dict[str, Any]:
        """Evaluate reasoning quality."""
        quality = self._assess_quality(response)
        reasoning_depth = self._estimate_reasoning_depth(response)

        result = {
            "quality": quality,
            "reasoning_depth": reasoning_depth,
            "response_length": len(response),
            "has_uncertainty_markers": self._has_uncertainty_markers(response),
            "has_qualifiers": self._has_qualifiers(response),
        }

        self.analytics.record_quality_score("reasoning", quality, result)
        return result

    def _assess_quality(self, response: str) -> float:
        """Assess response quality."""
        # Simplified quality assessment
        score = 0.7

        # Length factor
        if len(response) < 50:
            score -= 0.1
        elif len(response) > 500:
            score += 0.1

        # Structure factor
        if "." in response:
            score += 0.1

        return min(1.0, max(0.0, score))

    def _estimate_reasoning_depth(self, response: str) -> int:
        """Estimate reasoning depth."""
        depth = 1
        if "because" in response.lower():
            depth += 1
        if "therefore" in response.lower():
            depth += 1
        if "first" in response.lower() and "second" in response.lower():
            depth += 1
        return depth

    def _has_uncertainty_markers(self, response: str) -> bool:
        """Check for uncertainty markers."""
        markers = ["maybe", "perhaps", "possibly", "might", "could be", "uncertain"]
        return any(m in response.lower() for m in markers)

    def _has_qualifiers(self, response: str) -> bool:
        """Check for qualifiers."""
        qualifiers = ["generally", "typically", "usually", "often", "sometimes"]
        return any(q in response.lower() for q in qualifiers)


class HallucinationDetector:
    """Detects hallucinations in AI responses."""

    def __init__(self):
        self._confidence_threshold = 0.5
        self._patterns: List[str] = []

    async def detect(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> HallucinationDetection:
        """Detect hallucinations in text."""
        flagged = []

        # Simple pattern-based detection
        patterns = [
            r"I am not sure",
            r"as of my knowledge",
            r"might be",
            r"could be",
            r"according to",
        ]

        for pattern in patterns:
            import re
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                flagged.append({
                    "span": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "reason": "Potential hallucination pattern"
                })

        is_hallucinated = len(flagged) > 2

        return HallucinationDetection(
            text=text,
            is_hallucinated=is_hallucinated,
            confidence=1.0 - (len(flagged) * 0.1),
            flagged_spans=flagged,
            detector_type="pattern_matching"
        )


class ConfidenceTracker:
    """Tracks confidence scores."""

    def __init__(self):
        self._scores: Dict[str, List[float]] = {}
        self._thresholds = {"low": 0.5, "high": 0.9}

    def track(
        self,
        sample_id: str,
        confidence: float,
        reasoning_depth: int = 1
    ) -> ConfidenceMetric:
        """Track confidence for a sample."""
        metric = ConfidenceMetric(
            sample_id=sample_id,
            confidence=confidence,
            reasoning_depth=reasoning_depth
        )

        if sample_id not in self._scores:
            self._scores[sample_id] = []
        self._scores[sample_id].append(confidence)

        return metric

    def get_sample_confidence(self, sample_id: str) -> Optional[float]:
        """Get average confidence for sample."""
        scores = self._scores.get(sample_id, [])
        return sum(scores) / len(scores) if scores else None

    def get_confidence_alerts(self) -> List[Dict]:
        """Get low confidence alerts."""
        alerts = []
        for sample_id, scores in self._scores.items():
            avg = sum(scores) / len(scores)
            if avg < self._thresholds["low"]:
                alerts.append({
                    "sample_id": sample_id,
                    "avg_confidence": avg,
                    "sample_count": len(scores)
                })
        return alerts


class SemanticDriftDetector:
    """Detects semantic drift over time."""

    def __init__(self):
        self._baselines: Dict[str, List[float]] = {}
        self._current: Dict[str, List[float]] = {}
        self._window_size = 1000

    def update_baseline(self, metric_name: str, values: List[float]) -> None:
        """Update baseline values."""
        self._baselines[metric_name] = values[-self._window_size:]

    def update_current(self, metric_name: str, values: List[float]) -> None:
        """Update current values."""
        if metric_name not in self._current:
            self._current[metric_name] = []
        self._current[metric_name].extend(values)

        # Trim to window
        if len(self._current[metric_name]) > self._window_size:
            self._current[metric_name] = self._current[metric_name][-self._window_size:]

    def detect(self, metric_name: str) -> Optional[SemanticDrift]:
        """Detect drift for a metric."""
        baseline = self._baselines.get(metric_name, [])
        current = self._current.get(metric_name, [])

        if len(baseline) < 10 or len(current) < 10:
            return None

        baseline_avg = sum(baseline) / len(baseline)
        current_avg = sum(current) / len(current)

        if baseline_avg == 0:
            return None

        drift_percent = ((current_avg - baseline_avg) / baseline_avg) * 100

        severity = "normal"
        if abs(drift_percent) > 30:
            severity = "critical"
        elif abs(drift_percent) > 20:
            severity = "high"
        elif abs(drift_percent) > 10:
            severity = "medium"

        return SemanticDrift(
            metric_name=metric_name,
            baseline_value=baseline_avg,
            current_value=current_avg,
            drift_percent=drift_percent,
            severity=severity
        )