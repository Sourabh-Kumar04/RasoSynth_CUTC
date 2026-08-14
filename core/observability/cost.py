"""
Cost Observability & Optimization

Tracks API costs, GPU costs, storage costs, and provides
cost optimization recommendations.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio


class CostCategory(Enum):
    """Cost categories."""
    API_CALLS = "api_calls"
    GPU_COMPUTE = "gpu_compute"
    STORAGE = "storage"
    BANDWIDTH = "bandwidth"
    EMBEDDINGS = "embeddings"
    SYNTHETIC = "synthetic"


@dataclass
class CostEntry:
    """Individual cost entry."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    category: CostCategory = CostCategory.API_CALLS
    provider: str = ""
    amount: float = 0.0
    model: str = ""
    unit: str = "usd"
    quantity: float = 0.0
    quantity_unit: str = "tokens"
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """Tracks costs across all categories."""

    def __init__(self):
        self._costs: List[CostEntry] = []
        self._provider_costs: Dict[str, float] = {}
        self._category_costs: Dict[str, float] = {}
        self._daily_costs: Dict[str, float] = {}
        self._max_history = 100000

    def record(
        self,
        category: CostCategory,
        provider: str,
        amount: float,
        model: str = "",
        quantity: float = 0.0,
        quantity_unit: str = "tokens",
        metadata: Optional[Dict] = None
    ) -> None:
        """Record a cost entry."""
        entry = CostEntry(
            timestamp=datetime.utcnow(),
            category=category,
            provider=provider,
            model=model,
            amount=amount,
            quantity=quantity,
            quantity_unit=quantity_unit,
            metadata=metadata or {}
        )

        self._costs.append(entry)
        if len(self._costs) > self._max_history:
            self._costs = self._costs[-self._max_history:]

        # Update aggregations
        self._provider_costs[provider] = self._provider_costs.get(provider, 0) + amount

        cat_name = category.value if isinstance(category, CostCategory) else str(category)
        self._category_costs[cat_name] = self._category_costs.get(cat_name, 0) + amount

        date_key = datetime.utcnow().strftime("%Y-%m-%d")
        self._daily_costs[date_key] = self._daily_costs.get(date_key, 0) + amount

    def get_total_cost(self, since: Optional[datetime] = None) -> float:
        """Get total cost since a date."""
        if since is None:
            return sum(e.amount for e in self._costs)

        return sum(e.amount for e in self._costs if e.timestamp >= since)

    def get_cost_by_provider(self) -> Dict[str, float]:
        """Get costs by provider."""
        return dict(self._provider_costs)

    def get_cost_by_category(self) -> Dict[str, float]:
        """Get costs by category."""
        return dict(self._category_costs)

    def get_daily_costs(self, days: int = 7) -> Dict[str, float]:
        """Get daily costs for last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        daily = {}

        for entry in self._costs:
            if entry.timestamp >= cutoff:
                date_key = entry.timestamp.strftime("%Y-%m-%d")
                daily[date_key] = daily.get(date_key, 0) + entry.amount

        return daily

    def get_provider_comparison(self) -> List[Dict]:
        """Compare costs across providers."""
        comparison = []
        for provider, cost in self._provider_costs.items():
            entries = [e for e in self._costs if e.provider == provider]
            total_quantity = sum(e.quantity for e in entries)

            comparison.append({
                "provider": provider,
                "total_cost_usd": cost,
                "total_quantity": total_quantity,
                "cost_per_unit": cost / max(total_quantity, 1),
                "entry_count": len(entries)
            })

        return sorted(comparison, key=lambda x: x["total_cost_usd"], reverse=True)


class CostAnalyzer:
    """Analyzes cost patterns and provides optimization insights."""

    def __init__(self, tracker: CostTracker):
        self.tracker = tracker

    def find_cost_anomalies(
        self,
        window_hours: int = 24,
        threshold_std: float = 2.0
    ) -> List[Dict]:
        """Find cost anomalies."""
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent_costs = [e.amount for e in self.tracker._costs if e.timestamp >= cutoff]

        if len(recent_costs) < 10:
            return []

        avg = sum(recent_costs) / len(recent_costs)
        variance = sum((c - avg) ** 2 for c in recent_costs) / len(recent_costs)
        std = variance ** 0.5

        anomalies = []
        for entry in self.tracker._costs:
            if entry.timestamp >= cutoff and entry.amount > avg + threshold_std * std:
                anomalies.append({
                    "timestamp": entry.timestamp.isoformat(),
                    "provider": entry.provider,
                    "amount": entry.amount,
                    "avg": avg,
                    "std": std,
                    "z_score": (entry.amount - avg) / max(std, 0.001)
                })

        return anomalies

    def get_expensive_workflows(self, limit: int = 10) -> List[Dict]:
        """Find most expensive workflows."""
        workflow_costs: Dict[str, float] = {}

        for entry in self.tracker._costs:
            workflow_id = entry.metadata.get("workflow_id")
            if workflow_id:
                workflow_costs[workflow_id] = workflow_costs.get(workflow_id, 0) + entry.amount

        sorted_workflows = sorted(
            workflow_costs.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {"workflow_id": wf_id, "cost_usd": cost}
            for wf_id, cost in sorted_workflows[:limit]
        ]

    def get_cost_breakdown(self) -> Dict[str, Any]:
        """Get detailed cost breakdown."""
        return {
            "total_cost": self.tracker.get_total_cost(),
            "by_provider": self.tracker.get_cost_by_provider(),
            "by_category": self.tracker.get_cost_by_category(),
            "daily_costs": self.tracker.get_daily_costs(7),
            "provider_comparison": self.tracker.get_provider_comparison()
        }


class ProviderCostComparison:
    """Compares costs across LLM providers."""

    def __init__(self):
        self._provider_rates: Dict[str, Dict] = {}

    def set_rate(
        self,
        provider: str,
        model: str,
        input_cost_per_1k: float,
        output_cost_per_1k: float
    ) -> None:
        """Set provider pricing rates."""
        if provider not in self._provider_rates:
            self._provider_rates[provider] = {}

        self._provider_rates[provider][model] = {
            "input_cost_per_1k": input_cost_per_1k,
            "output_cost_per_1k": output_cost_per_1k
        }

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Estimate cost for a request."""
        rates = self._provider_rates.get(provider, {}).get(model)
        if not rates:
            return 0.0

        input_cost = (input_tokens / 1000) * rates["input_cost_per_1k"]
        output_cost = (output_tokens / 1000) * rates["output_cost_per_1k"]

        return input_cost + output_cost

    def find_cheapest_provider(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> Optional[Dict]:
        """Find cheapest provider for a request."""
        options = []

        for provider, models in self._provider_rates.items():
            if model in models:
                cost = self.estimate_cost(provider, model, input_tokens, output_tokens)
                options.append({"provider": provider, "model": model, "estimated_cost": cost})

        if not options:
            return None

        return min(options, key=lambda x: x["estimated_cost"])

    def get_all_rates(self) -> Dict[str, Dict]:
        """Get all provider rates."""
        return dict(self._provider_rates)


class BudgetMonitor:
    """Monitors budget limits."""

    def __init__(
        self,
        daily_limit_usd: float,
        monthly_limit_usd: float
    ):
        self.daily_limit = daily_limit_usd
        self.monthly_limit = monthly_limit_usd

        self._daily_spent = 0.0
        self._monthly_spent = 0.0
        self._alerts: List[Dict] = []

    def update_spending(self, cost: float) -> Dict[str, Any]:
        """Update spending and check limits."""
        self._daily_spent += cost
        self._monthly_spent += cost

        status = {
            "daily_spent": self._daily_spent,
            "daily_limit": self.daily_limit,
            "daily_remaining": self.daily_limit - self._daily_spent,
            "daily_percent": (self._daily_spent / self.daily_limit) * 100 if self.daily_limit > 0 else 0,
            "monthly_spent": self._monthly_spent,
            "monthly_limit": self.monthly_limit,
            "monthly_remaining": self.monthly_limit - self._monthly_spent,
        }

        # Check for alerts
        if status["daily_percent"] > 90:
            self._alerts.append({
                "type": "daily_budget_warning",
                "message": f"Daily budget at {status['daily_percent']:.1f}%",
                "timestamp": datetime.utcnow().isoformat()
            })

        return status

    def get_alerts(self) -> List[Dict]:
        """Get budget alerts."""
        return list(self._alerts)

    def reset_daily(self) -> None:
        """Reset daily counter."""
        self._daily_spent = 0.0

    def reset_monthly(self) -> None:
        """Reset monthly counter."""
        self._monthly_spent = 0.0


class CostOptimizationEngine:
    """Provides cost optimization recommendations."""

    def __init__(self, tracker: CostTracker, comparison: ProviderCostComparison):
        self.tracker = tracker
        self.comparison = comparison

    def get_recommendations(self) -> List[Dict]:
        """Get cost optimization recommendations."""
        recommendations = []

        # Check for expensive providers
        provider_costs = self.tracker.get_cost_by_provider()
        if provider_costs:
            max_provider = max(provider_costs.items(), key=lambda x: x[1])
            if len(provider_costs) > 1:
                min_provider = min(provider_costs.items(), key=lambda x: x[1])

                if max_provider[1] > min_provider[1] * 2:
                    recommendations.append({
                        "type": "provider_switch",
                        "message": f"Consider switching from {max_provider[0]} to {min_provider[0]}",
                        "potential_savings": max_provider[1] - min_provider[1],
                        "priority": "high"
                    })

        # Check for high-cost workflows
        expensive = self.tracker.get_cost_by_category()
        if "api_calls" in expensive and expensive["api_calls"] > 100:
            recommendations.append({
                "type": "caching",
                "message": "Enable semantic caching to reduce API calls",
                "potential_savings": expensive["api_calls"] * 0.3,
                "priority": "medium"
            })

        return recommendations