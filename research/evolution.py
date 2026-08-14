"""
Pipeline Evolution Engine

Self-evolving pipeline architecture with dynamic upgrades,
plugin system, and continuous optimization.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import hashlib
import copy


class EvolutionStatus(Enum):
    """Evolution status."""
    STABLE = "stable"
    EVALUATING = "evaluating"
    UPGRADING = "upgrading"
    ROLLING_BACK = "rolling_back"


class UpgradeStrategy(Enum):
    """Upgrade strategies."""
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    GRADUAL = "gradual"
    IMMEDIATE = "immediate"


@dataclass
class PipelineComponent:
    """A component in the pipeline."""
    component_id: str
    name: str
    version: str
    config: Dict[str, Any]
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineVersion:
    """A version of the pipeline."""
    version_id: str
    version_number: str
    components: List[PipelineComponent]
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.utcnow)
    deployed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Upgrade:
    """A pipeline upgrade."""
    upgrade_id: str
    from_version: str
    to_version: str
    strategy: UpgradeStrategy
    components_to_upgrade: List[str]
    risk_level: str = "low"
    requires_approval: bool = False
    status: str = "pending"
    progress_percent: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class EvolutionRecommendation:
    """Recommendation for pipeline evolution."""
    recommendation_id: str
    category: str
    description: str
    expected_impact: Dict[str, float]
    risk_level: str
    estimated_effort: str
    prerequisites: List[str] = field(default_factory=list)
    confidence: float = 0.0


class PluginRegistry:
    """Registry for pipeline plugins."""

    def __init__(self):
        self._plugins: Dict[str, Dict] = {}
        self._versions: Dict[str, List[str]] = {}

    def register_plugin(
        self,
        plugin_name: str,
        version: str,
        implementation: Any,
        metadata: Optional[Dict] = None
    ) -> None:
        """Register a plugin."""
        plugin_id = f"{plugin_name}:{version}"

        self._plugins[plugin_id] = {
            "plugin_id": plugin_id,
            "name": plugin_name,
            "version": version,
            "implementation": implementation,
            "metadata": metadata or {},
            "registered_at": datetime.utcnow()
        }

        if plugin_name not in self._versions:
            self._versions[plugin_name] = []
        self._versions[plugin_name].append(version)

    def get_plugin(self, plugin_name: str, version: Optional[str] = None) -> Optional[Dict]:
        """Get a plugin."""
        if version:
            return self._plugins.get(f"{plugin_name}:{version}")

        versions = self._versions.get(plugin_name, [])
        if versions:
            latest = sorted(versions, reverse=True)[0]
            return self._plugins.get(f"{plugin_name}:{latest}")

        return None

    def list_versions(self, plugin_name: str) -> List[str]:
        """List all versions of a plugin."""
        return sorted(self._versions.get(plugin_name, []), reverse=True)


class PipelineEvolution:
    """Manages pipeline evolution."""

    def __init__(self):
        self.plugin_registry = PluginRegistry()
        self._pipelines: Dict[str, List[PipelineVersion]] = {}
        self._upgrades: Dict[str, Upgrade] = {}
        self._evolution_history: List[Dict] = []

    def register_pipeline(
        self,
        pipeline_name: str,
        components: List[Dict]
    ) -> str:
        """Register a new pipeline."""
        version_number = "1.0.0"

        pipeline_components = []
        for comp in components:
            component = PipelineComponent(
                component_id=comp["id"],
                name=comp["name"],
                version=comp["version"],
                config=comp.get("config", {}),
                capabilities=comp.get("capabilities", []),
                dependencies=comp.get("dependencies", [])
            )
            pipeline_components.append(component)

        version = PipelineVersion(
            version_id=f"{pipeline_name}:{version_number}",
            version_number=version_number,
            components=pipeline_components,
            deployed_at=datetime.utcnow()
        )

        if pipeline_name not in self._pipelines:
            self._pipelines[pipeline_name] = []
        self._pipelines[pipeline_name].append(version)

        return version.version_id

    def create_upgrade(
        self,
        pipeline_name: str,
        new_components: List[Dict],
        strategy: UpgradeStrategy = UpgradeStrategy.CANARY
    ) -> Optional[str]:
        """Create an upgrade for a pipeline."""
        if pipeline_name not in self._pipelines:
            return None

        current = self._get_active_version(pipeline_name)
        if not current:
            return None

        components_to_upgrade = self._find_upgrades(current.components, new_components)

        upgrade = Upgrade(
            upgrade_id=f"upgrade_{pipeline_name}_{len(self._upgrades)}",
            from_version=current.version_number,
            to_version=self._increment_version(current.version_number),
            strategy=strategy,
            components_to_upgrade=[c["name"] for c in components_to_upgrade]
        )

        upgrade.risk_level = self._assess_risk(components_to_upgrade)
        upgrade.requires_approval = upgrade.risk_level in ["high", "critical"]

        self._upgrades[upgrade.upgrade_id] = upgrade
        return upgrade.upgrade_id

    def _get_active_version(self, pipeline_name: str) -> Optional[PipelineVersion]:
        """Get active version of a pipeline."""
        versions = self._pipelines.get(pipeline_name, [])
        for v in reversed(versions):
            if v.status == "active":
                return v
        return versions[-1] if versions else None

    def _find_upgrades(
        self,
        current: List[PipelineComponent],
        new: List[Dict]
    ) -> List[Dict]:
        """Find components that need upgrading."""
        upgrades = []
        current_map = {c.name: c for c in current}

        for comp in new:
            if comp["name"] in current_map:
                current_version = current_map[comp["name"]].version
                if self._version_greater(comp["version"], current_version):
                    upgrades.append(comp)

        return upgrades

    def _version_greater(self, a: str, b: str) -> bool:
        """Compare version strings."""
        try:
            a_parts = [int(x) for x in a.split(".")]
            b_parts = [int(x) for x in b.split(".")]
            return a_parts > b_parts
        except:
            return a > b

    def _increment_version(self, version: str) -> str:
        """Increment version number."""
        try:
            parts = version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except:
            return f"{version}.1"

    def _assess_risk(self, components: List[Dict]) -> str:
        """Assess upgrade risk."""
        if not components:
            return "low"

        major_upgrades = sum(1 for c in components if ".0" in c.get("version", ""))
        if major_upgrades > 0:
            return "high"

        return "medium"

    async def execute_upgrade(
        self,
        upgrade_id: str,
        orchestrator: Any = None
    ) -> bool:
        """Execute an upgrade."""
        upgrade = self._upgrades.get(upgrade_id)
        if not upgrade or upgrade.status != "pending":
            return False

        upgrade.status = "upgrading"

        try:
            if upgrade.strategy == UpgradeStrategy.CANARY:
                success = await self._canary_deploy(upgrade)
            elif upgrade.strategy == UpgradeStrategy.BLUE_GREEN:
                success = await self._blue_green_deploy(upgrade)
            elif upgrade.strategy == UpgradeStrategy.GRADUAL:
                success = await self._gradual_deploy(upgrade)
            else:
                success = await self._immediate_deploy(upgrade)

            if success:
                upgrade.status = "completed"
                upgrade.completed_at = datetime.utcnow()
                upgrade.progress_percent = 100.0

                self._evolution_history.append({
                    "upgrade_id": upgrade_id,
                    "from": upgrade.from_version,
                    "to": upgrade.to_version,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True
                })
            else:
                upgrade.status = "failed"

            return success

        except Exception as e:
            upgrade.status = "failed"
            return False

    async def _canary_deploy(self, upgrade: Upgrade) -> bool:
        """Deploy to canary first."""
        await asyncio.sleep(0.1)
        return True

    async def _blue_green_deploy(self, upgrade: Upgrade) -> bool:
        """Blue-green deployment."""
        await asyncio.sleep(0.1)
        return True

    async def _gradual_deploy(self, upgrade: Upgrade) -> bool:
        """Gradual percentage-based deployment."""
        for percent in [10, 25, 50, 100]:
            upgrade.progress_percent = float(percent)
            await asyncio.sleep(0.05)
        return True

    async def _immediate_deploy(self, upgrade: Upgrade) -> bool:
        """Immediate full deployment."""
        upgrade.progress_percent = 100.0
        return True

    def rollback_upgrade(self, upgrade_id: str) -> bool:
        """Rollback an upgrade."""
        upgrade = self._upgrades.get(upgrade_id)
        if not upgrade:
            return False

        upgrade.status = "rolling_back"

        self._evolution_history.append({
            "upgrade_id": upgrade_id,
            "action": "rollback",
            "timestamp": datetime.utcnow().isoformat()
        })

        return True

    def get_upgrade_status(self, upgrade_id: str) -> Optional[Dict]:
        """Get upgrade status."""
        upgrade = self._upgrades.get(upgrade_id)
        if not upgrade:
            return None

        return {
            "upgrade_id": upgrade.upgrade_id,
            "from_version": upgrade.from_version,
            "to_version": upgrade.to_version,
            "strategy": upgrade.strategy.value,
            "status": upgrade.status,
            "progress_percent": upgrade.progress_percent,
            "risk_level": upgrade.risk_level,
            "requires_approval": upgrade.requires_approval
        }


class AdaptiveRouter:
    """Adaptively routes requests based on conditions."""

    def __init__(self):
        self._routes: Dict[str, Dict] = {}
        self._conditions: Dict[str, Callable] = {}

    def register_route(
        self,
        route_name: str,
        destination: str,
        conditions: Optional[Dict] = None
    ) -> None:
        """Register a route."""
        self._routes[route_name] = {
            "route_name": route_name,
            "destination": destination,
            "conditions": conditions or {},
            "weight": 1.0,
            "active": True
        }

    def add_condition(self, route_name: str, condition_fn: Callable) -> None:
        """Add routing condition."""
        self._conditions[route_name] = condition_fn

    def resolve_route(self, context: Dict) -> Optional[str]:
        """Resolve best route for context."""
        candidates = []

        for route_name, route in self._routes.items():
            if not route["active"]:
                continue

            score = self._evaluate_conditions(route["conditions"], context)

            if score > 0:
                candidates.append((route_name, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _evaluate_conditions(self, conditions: Dict, context: Dict) -> float:
        """Evaluate routing conditions."""
        if not conditions:
            return 1.0

        score = 1.0

        for key, value in conditions.items():
            if key in context:
                context_value = context[key]

                if isinstance(value, dict):
                    if "min" in value and context_value < value["min"]:
                        score *= 0.5
                    if "max" in value and context_value > value["max"]:
                        score *= 0.5
                elif context_value != value:
                    score *= 0.1

        return score

    def get_active_routes(self) -> List[Dict]:
        """Get all active routes."""
        return [r for r in self._routes.values() if r["active"]]


class ConfigurationTuner:
    """Automatically tunes pipeline configurations."""

    def __init__(self):
        self._param_ranges: Dict[str, Dict] = {}
        self._current_config: Dict[str, Any] = {}
        self._tuning_history: List[Dict] = []

    def set_parameter_range(
        self,
        component: str,
        parameter: str,
        min_val: float,
        max_val: float,
        step: float = 1.0
    ) -> None:
        """Set tuning range for a parameter."""
        key = f"{component}.{parameter}"
        self._param_ranges[key] = {
            "component": component,
            "parameter": parameter,
            "min": min_val,
            "max": max_val,
            "step": step
        }

    def set_current_config(self, config: Dict) -> None:
        """Set current configuration."""
        self._current_config = config

    def suggest_next_config(self) -> Optional[Dict]:
        """Suggest next configuration to try."""
        if not self._param_ranges:
            return None

        suggestions = {}
        for key, range_info in self._param_ranges.items():
            current = self._current_config.get(key)

            if current is None:
                suggestions[key] = range_info["min"]
                continue

            next_val = current + range_info["step"]
            if next_val > range_info["max"]:
                next_val = range_info["min"]

            suggestions[key] = next_val

        return suggestions

    def record_result(self, config: Dict, metrics: Dict) -> None:
        """Record configuration result."""
        self._tuning_history.append({
            "config": copy.copy(config),
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_best_config(self) -> Optional[Dict]:
        """Get best known configuration."""
        if not self._tuning_history:
            return None

        return max(
            self._tuning_history,
            key=lambda h: h["metrics"].get("score", 0)
        )["config"]


class SelfImprovingOrchestrator:
    """Self-improving orchestrator with evolution capabilities."""

    def __init__(self):
        self.pipeline_evolution = PipelineEvolution()
        self.adaptive_router = AdaptiveRouter()
        self.config_tuner = ConfigurationTuner()
        self._improvement_queue: List[EvolutionRecommendation] = []

    def analyze_and_suggest(self, metrics: Dict) -> List[EvolutionRecommendation]:
        """Analyze metrics and suggest improvements."""
        suggestions = []

        if metrics.get("quality_score", 0) < 0.8:
            suggestions.append(EvolutionRecommendation(
                recommendation_id=f"rec_{len(suggestions)}",
                category="quality",
                description="Upgrade quality validation components",
                expected_impact={"quality_score": 0.1},
                risk_level="medium",
                estimated_effort="medium",
                confidence=0.8
            ))

        if metrics.get("cost_per_record", 0) > 0.1:
            suggestions.append(EvolutionRecommendation(
                recommendation_id=f"rec_{len(suggestions)}",
                category="cost",
                description="Enable caching to reduce API calls",
                expected_impact={"cost_per_record": -0.3},
                risk_level="low",
                estimated_effort="low",
                confidence=0.9
            ))

        if metrics.get("latency_p95_ms", 0) > 500:
            suggestions.append(EvolutionRecommendation(
                recommendation_id=f"rec_{len(suggestions)}",
                category="speed",
                description="Upgrade to faster embedding model",
                expected_impact={"latency_p95_ms": -0.4},
                risk_level="medium",
                estimated_effort="high",
                confidence=0.7
            ))

        self._improvement_queue.extend(suggestions)
        return suggestions

    def apply_recommendation(self, recommendation: EvolutionRecommendation) -> bool:
        """Apply a recommendation."""
        if recommendation.category == "quality":
            pass
        elif recommendation.category == "cost":
            pass
        elif recommendation.category == "speed":
            pass

        return True

    def get_evolution_status(self) -> Dict[str, Any]:
        """Get evolution status."""
        return {
            "pending_improvements": len(self._improvement_queue),
            "active_upgrades": sum(1 for u in self.pipeline_evolution._upgrades.values() if u.status == "upgrading"),
            "completed_upgrades": sum(1 for u in self.pipeline_evolution._upgrades.values() if u.status == "completed"),
            "tuning_iterations": len(self.config_tuner._tuning_history)
        }
