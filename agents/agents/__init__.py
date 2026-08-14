"""
Specialized Agents Package

Contains all specialized agent implementations for the multi-agent system:
- Research: Domain understanding and objective analysis
- Planning: Execution planning and workflow optimization
- Discovery: Source discovery and search optimization
- Extraction: Web crawling, OCR, and multimodal extraction
- Quality: Quality evaluation, deduplication, and toxicity detection
- Synthetic: Synthetic generation and validation
- Optimization: Fine-tuning and curriculum planning
- Infrastructure: GPU scheduling, storage, and distribution
"""

from agents.agents.research import ResearchAgent
from agents.agents.planning import StrategyAgent
from agents.agents.discovery import SourceDiscoveryAgent, SearchOptimizationAgent
from agents.agents.extraction import WebCrawlerAgent, OCRAgent, MultimodalAgent
from agents.agents.quality import QualityEvaluationAgent, DedupAgent, ToxicityAgent
from agents.agents.synthetic import SyntheticGenerationAgent, ValidationAgent, ConsensusAgent
from agents.agents.optimization import FineTuningAgent, CurriculumAgent
from agents.agents.infrastructure import GPUSchedulingAgent, StorageOptimizationAgent, DistributionAgent

__all__ = [
    "ResearchAgent",
    "StrategyAgent",
    "SourceDiscoveryAgent",
    "SearchOptimizationAgent",
    "WebCrawlerAgent",
    "OCRAgent",
    "MultimodalAgent",
    "QualityEvaluationAgent",
    "DedupAgent",
    "ToxicityAgent",
    "SyntheticGenerationAgent",
    "ValidationAgent",
    "ConsensusAgent",
    "FineTuningAgent",
    "CurriculumAgent",
    "GPUSchedulingAgent",
    "StorageOptimizationAgent",
    "DistributionAgent",
]