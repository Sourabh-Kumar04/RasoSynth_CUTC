"""Pipeline module for data processing stages."""
from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "DiscoveryPipeline", "DiscoveredSource", "SourceType",
    "ExtractionPipeline", "ExtractedContent",
    "FilteringPipeline", "FilteredSample",
    "ConstructionPipeline", "ConstructedSample", "DatasetType",
    "ExportPipeline", "ExportConfig",
    "QualityScorer", "QualityScore",
    "DeduplicationEngine", "DuplicateResult",
    "DatasetDiversityAnalyzer", "DiversityMetrics",
    "HallucinationDetector", "HallucinationResult",
]

_ATTR_TO_MODULE = {
    "DiscoveryPipeline": "pipeline.discovery",
    "DiscoveredSource": "pipeline.discovery",
    "SourceType": "pipeline.discovery",
    "ExtractionPipeline": "pipeline.extraction",
    "ExtractedContent": "pipeline.extraction",
    "FilteringPipeline": "pipeline.filtering",
    "FilteredSample": "pipeline.filtering",
    "ConstructionPipeline": "pipeline.construction",
    "ConstructedSample": "pipeline.construction",
    "DatasetType": "pipeline.construction",
    "ExportPipeline": "pipeline.export",
    "ExportConfig": "pipeline.export",
    "QualityScorer": "pipeline.quality_scorer",
    "QualityScore": "pipeline.quality_scorer",
    "DeduplicationEngine": "pipeline.deduplication",
    "DuplicateResult": "pipeline.deduplication",
    "DatasetDiversityAnalyzer": "pipeline.diversity",
    "DiversityMetrics": "pipeline.diversity",
    "HallucinationDetector": "pipeline.hallucination_detector",
    "HallucinationResult": "pipeline.hallucination_detector",
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_TO_MODULE:
        mod = importlib.import_module(_ATTR_TO_MODULE[name])
        val = getattr(mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
