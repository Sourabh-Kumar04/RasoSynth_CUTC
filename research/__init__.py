"""
Autonomous Research & Continuous Self-Improvement

Continuous research, benchmarking, experimentation, and self-improvement
framework using latest 2026 techniques.
"""

from research.research_loop import (
    ResearchLoop,
    ResearchScheduler,
    ResearchCoordinator,
    ResearchStatus,
    ResearchPriority,
    ResearchFinding,
    BenchmarkResult,
    Experiment,
    Improvement,
    ImprovementCategory,
    ResearchReport,
)
from research.agents import (
    ResearchAgent,
    ResearchAgentSwarm,
    PaperAnalysisAgent,
    BenchmarkAgent,
    LLMEvaluationAgent,
    OCRResearchAgent,
    RetrievalAgent,
    FilteringAgent,
    CostOptimizationAgent,
    SafetyAgent,
    SyntheticDataAgent,
    ResearchDomain,
)
from research.benchmarking import (
    BenchmarkRunner,
    QualityBenchmark,
    CostBenchmark,
    SpeedBenchmark,
    ScalabilityBenchmark,
    BenchmarkAggregator,
    BenchmarkCategory,
    BenchmarkConfig,
    MetricResult,
)
from research.experimentation import (
    ExperimentRunner,
    ABTestPipeline,
    MultiVariantOptimizer,
    ExperimentScheduler,
    Experiment,
    ExperimentType,
    Variant,
)
from research.knowledge_base import (
    KnowledgeBase,
    ResearchKnowledgeBase,
    SemanticMemory,
    KnowledgeEntry,
    KnowledgeType,
)
from research.evolution import (
    PipelineEvolution,
    PluginRegistry,
    AdaptiveRouter,
    ConfigurationTuner,
    SelfImprovingOrchestrator,
    EvolutionStatus,
    Upgrade,
    PipelineComponent,
)

__all__ = [
    # Research Loop
    "ResearchLoop",
    "ResearchScheduler",
    "ResearchCoordinator",
    "ResearchStatus",
    "ResearchPriority",
    "ResearchFinding",
    "BenchmarkResult",
    "Experiment",
    "Improvement",
    "ImprovementCategory",
    "ResearchReport",

    # Research Agents
    "ResearchAgent",
    "ResearchAgentSwarm",
    "PaperAnalysisAgent",
    "BenchmarkAgent",
    "LLMEvaluationAgent",
    "OCRResearchAgent",
    "RetrievalAgent",
    "FilteringAgent",
    "CostOptimizationAgent",
    "SafetyAgent",
    "SyntheticDataAgent",
    "ResearchDomain",

    # Benchmarking
    "BenchmarkRunner",
    "QualityBenchmark",
    "CostBenchmark",
    "SpeedBenchmark",
    "ScalabilityBenchmark",
    "BenchmarkAggregator",
    "BenchmarkCategory",
    "BenchmarkConfig",
    "MetricResult",

    # Experimentation
    "ExperimentRunner",
    "ABTestPipeline",
    "MultiVariantOptimizer",
    "ExperimentScheduler",
    "Experiment",
    "ExperimentType",
    "Variant",

    # Knowledge Base
    "KnowledgeBase",
    "ResearchKnowledgeBase",
    "SemanticMemory",
    "KnowledgeEntry",
    "KnowledgeType",

    # Evolution
    "PipelineEvolution",
    "PluginRegistry",
    "AdaptiveRouter",
    "ConfigurationTuner",
    "SelfImprovingOrchestrator",
    "EvolutionStatus",
    "Upgrade",
    "PipelineComponent",
]
