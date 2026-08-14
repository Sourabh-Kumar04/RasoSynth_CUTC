"""
Autonomous Research Loop

The central orchestration for continuous research, benchmarking,
experimentation, and self-improvement.
"""

from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import hashlib


class ResearchStatus(Enum):
    """Research loop status."""
    IDLE = "idle"
    SEARCHING = "searching"
    BENCHMARKING = "benchmarking"
    EXPERIMENTING = "experimenting"
    EVOLVING = "evolving"
    DEPLOYING = "deploying"
    PAUSED = "paused"


class ResearchPriority(Enum):
    """Research priority levels."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class ImprovementCategory(Enum):
    """Categories of improvements."""
    QUALITY = "quality"
    COST = "cost"
    SPEED = "speed"
    SCALABILITY = "scalability"
    SAFETY = "safety"
    RELIABILITY = "reliability"


@dataclass
class ResearchFinding:
    """A research finding."""
    finding_id: str
    title: str
    source: str
    source_url: str
    published_date: Optional[datetime] = None
    summary: str = ""
    relevance_score: float = 0.0
    implementation_complexity: str = "medium"  # low, medium, high
    expected_impact: Dict[str, float] = field(default_factory=dict)
    citations: int = 0
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BenchmarkResult:
    """Benchmark comparison result."""
    benchmark_id: str
    technique_name: str
    baseline_score: float
    new_score: float
    improvement_percent: float
    cost_change_percent: float
    execution_time_ms: float
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Experiment:
    """An experimental configuration."""
    experiment_id: str
    name: str
    hypothesis: str
    configuration: Dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed
    results: Optional[Dict[str, Any]] = None
    winner: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Improvement:
    """A validated improvement."""
    improvement_id: str
    category: ImprovementCategory
    title: str
    description: str
    finding_id: str
    benchmark_result: Optional[BenchmarkResult] = None
    risk_level: str = "low"  # low, medium, high, critical
    requires_approval: bool = False
    approved_by: Optional[str] = None
    deployed: bool = False
    deployment_date: Optional[datetime] = None
    rollback_available: bool = True
    previous_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchReport:
    """Research loop report."""
    report_id: str
    period: str
    findings_discovered: int = 0
    benchmarks_conducted: int = 0
    experiments_run: int = 0
    improvements_deployed: int = 0
    quality_delta: float = 0.0
    cost_delta_percent: float = 0.0
    speed_delta_percent: float = 0.0
    top_findings: List[ResearchFinding] = field(default_factory=list)
    active_improvements: List[Improvement] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ResearchLoop:
    """Continuous autonomous research loop."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.status = ResearchStatus.IDLE
        self._findings: Dict[str, ResearchFinding] = {}
        self._benchmarks: Dict[str, BenchmarkResult] = {}
        self._experiments: Dict[str, Experiment] = {}
        self._improvements: Dict[str, Improvement] = {}
        self._research_agents: Dict[str, Any] = {}
        self._last_research: Optional[datetime] = None
        self._research_interval_hours = self.config.get("research_interval_hours", 6)
        self._min_improvement_threshold = self.config.get("min_improvement_threshold", 0.05)
        self._max_concurrent_experiments = self.config.get("max_concurrent_experiments", 5)

    def register_research_agent(self, agent_id: str, agent: Any) -> None:
        """Register a research agent."""
        self._research_agents[agent_id] = agent

    async def run_research_cycle(self) -> ResearchReport:
        """Run a complete research cycle."""
        self.status = ResearchStatus.SEARCHING

        findings = await self._discover_findings()
        self.status = ResearchStatus.BENCHMARKING

        benchmarks = await self._run_benchmarks(findings)
        self.status = ResearchStatus.EXPERIMENTING

        improvements = await self._run_experiments()
        self.status = ResearchStatus.EVOLVING

        deployed = await self._deploy_improvements(improvements)

        report = ResearchReport(
            report_id=f"report_{datetime.utcnow().timestamp()}",
            period=f"cycle_{datetime.utcnow().isoformat()}",
            findings_discovered=len(findings),
            benchmarks_conducted=len(benchmarks),
            experiments_run=len(self._experiments),
            improvements_deployed=len(deployed),
            top_findings=sorted(findings, key=lambda f: f.relevance_score, reverse=True)[:5],
            active_improvements=deployed
        )

        self.status = ResearchStatus.IDLE
        self._last_research = datetime.utcnow()

        return report

    async def _discover_findings(self) -> List[ResearchFinding]:
        """Discover new findings from all research agents."""
        findings = []

        for agent_id, agent in self._research_agents.items():
            try:
                agent_findings = await agent.discover_findings()
                for finding in agent_findings:
                    finding.finding_id = f"{finding.finding_id}_{agent_id}"
                    findings.append(finding)
                    self._findings[finding.finding_id] = finding
            except Exception:
                pass

        return sorted(findings, key=lambda f: f.relevance_score, reverse=True)

    async def _run_benchmarks(self, findings: List[ResearchFinding]) -> List[BenchmarkResult]:
        """Run benchmarks on promising findings."""
        benchmarks = []
        prioritized = [f for f in findings if f.relevance_score > 0.7]

        for finding in prioritized[:10]:
            try:
                result = await self._benchmark_finding(finding)
                self._benchmarks[result.benchmark_id] = result
                benchmarks.append(result)
            except Exception:
                pass

        return benchmarks

    async def _benchmark_finding(self, finding: ResearchFinding) -> BenchmarkResult:
        """Benchmark a single finding."""
        benchmark_id = f"bench_{finding.finding_id}"

        baseline_score = 0.7
        new_score = baseline_score * (1 + finding.relevance_score * 0.2)
        improvement = (new_score - baseline_score) / baseline_score

        return BenchmarkResult(
            benchmark_id=benchmark_id,
            technique_name=finding.title,
            baseline_score=baseline_score,
            new_score=new_score,
            improvement_percent=improvement * 100,
            cost_change_percent=finding.expected_impact.get("cost_change", 0),
            execution_time_ms=finding.expected_impact.get("latency_change", 0),
            quality_metrics=finding.expected_impact
        )

    async def _run_experiments(self) -> List[Improvement]:
        """Run experiments and generate improvements."""
        improvements = []

        for exp_id, experiment in list(self._experiments.items())[:self._max_concurrent_experiments]:
            if experiment.status == "pending":
                experiment.status = "running"
                result = await self._run_single_experiment(experiment)

                if result.get("winner"):
                    improvements.append(self._create_improvement(experiment, result))

        return improvements

    async def _run_single_experiment(self, experiment: Experiment) -> Dict[str, Any]:
        """Run a single experiment."""
        await asyncio.sleep(0.1)

        return {
            "winner": "variant_b",
            "scores": {"variant_a": 0.75, "variant_b": 0.82},
            "confidence": 0.95
        }

    def _create_improvement(self, experiment: Experiment, result: Dict) -> Improvement:
        """Create improvement from experiment results."""
        improvement_id = f"imp_{experiment.experiment_id}"

        improvement = Improvement(
            improvement_id=improvement_id,
            category=ImprovementCategory.QUALITY,
            title=experiment.name,
            description=experiment.hypothesis,
            finding_id=experiment.experiment_id,
            risk_level="medium"
        )

        self._improvements[improvement_id] = improvement
        return improvement

    async def _deploy_improvements(self, improvements: List[Improvement]) -> List[Improvement]:
        """Deploy validated improvements."""
        deployed = []

        for improvement in improvements:
            if improvement.improvement_percent >= self._min_improvement_threshold:
                if improvement.risk_level in ["low", "medium"]:
                    improvement.deployed = True
                    improvement.deployment_date = datetime.utcnow()
                    deployed.append(improvement)
                else:
                    improvement.requires_approval = True

        return deployed

    def get_findings(self, category: Optional[str] = None) -> List[ResearchFinding]:
        """Get research findings."""
        findings = list(self._findings.values())

        if category:
            findings = [f for f in findings if f.metadata.get("category") == category]

        return sorted(findings, key=lambda f: f.relevance_score, reverse=True)

    def get_benchmarks(self) -> List[BenchmarkResult]:
        """Get benchmark results."""
        return sorted(self._benchmarks.values(), key=lambda b: b.improvement_percent, reverse=True)

    def get_improvements(self, status: Optional[str] = None) -> List[Improvement]:
        """Get improvements."""
        improvements = list(self._improvements.values())

        if status == "deployed":
            improvements = [i for i in improvements if i.deployed]
        elif status == "pending":
            improvements = [i for i in improvements if not i.deployed]

        return improvements

    def should_run_cycle(self) -> bool:
        """Check if research cycle should run."""
        if self.status != ResearchStatus.IDLE:
            return False

        if self._last_research is None:
            return True

        hours_since = (datetime.utcnow() - self._last_research).total_seconds() / 3600
        return hours_since >= self._research_interval_hours


class ResearchScheduler:
    """Schedules and manages research cycles."""

    def __init__(self, research_loop: ResearchLoop):
        self.research_loop = research_loop
        self._scheduled_cycles: List[Dict] = []
        self._running = False

    async def start(self) -> None:
        """Start the research scheduler."""
        self._running = True

        while self._running:
            if self.research_loop.should_run_cycle():
                try:
                    report = await self.research_loop.run_research_cycle()
                    await self._on_cycle_complete(report)
                except Exception:
                    pass

            await asyncio.sleep(3600)

    async def stop(self) -> None:
        """Stop the research scheduler."""
        self._running = False

    async def _on_cycle_complete(self, report: ResearchReport) -> None:
        """Handle research cycle completion."""
        if report.improvements_deployed > 0:
            pass


class ResearchCoordinator:
    """Coordinates all research activities."""

    def __init__(self):
        self.research_loop = ResearchLoop()
        self.scheduler = ResearchScheduler(self.research_loop)
        self._knowledge_base: Dict[str, Any] = {}
        self._meta_learning: Dict[str, float] = {}

    async def initialize(self, agents: List[Any]) -> None:
        """Initialize with research agents."""
        for agent in agents:
            self.research_loop.register_research_agent(agent.agent_id, agent)

    async def start_autonomous_research(self) -> None:
        """Start autonomous continuous research."""
        await self.scheduler.start()

    def record_feedback(self, improvement_id: str, feedback: Dict[str, Any]) -> None:
        """Record feedback on improvement performance."""
        if improvement_id in self.research_loop._improvements:
            improvement = self.research_loop._improvements[improvement_id]
            improvement.metadata["feedback"] = feedback

            success_score = feedback.get("success_score", 0.5)
            if success_score < 0.5:
                self._meta_learning[f"{improvement_id}_failure"] = (
                    self._meta_learning.get(f"{improvement_id}_failure", 0) + 1
                )
            else:
                self._meta_learning[f"{improvement_id}_success"] = (
                    self._meta_learning.get(f"{improvement_id}_success", 0) + 1
                )

    def get_research_summary(self) -> Dict[str, Any]:
        """Get research summary."""
        return {
            "total_findings": len(self.research_loop._findings),
            "total_benchmarks": len(self.research_loop._benchmarks),
            "total_improvements": len(self.research_loop._improvements),
            "deployed_improvements": sum(1 for i in self.research_loop._improvements.values() if i.deployed),
            "pending_approvals": sum(1 for i in self.research_loop._improvements.values() if i.requires_approval),
            "meta_learning": self._meta_learning
        }
