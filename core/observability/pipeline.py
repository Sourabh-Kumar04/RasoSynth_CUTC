"""
Dataset Lineage & Pipeline Telemetry

Complete dataset provenance tracking, transformation history,
and quality metrics throughout the pipeline.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import hashlib


class TransformationType(Enum):
    """Types of data transformations."""
    EXTRACTION = "extraction"
    FILTERING = "filtering"
    AUGMENTATION = "augmentation"
    SYNTHETIC = "synthetic"
    VALIDATION = "validation"
    DEDUPLICATION = "deduplication"
    NORMALIZATION = "normalization"
    ENCODING = "encoding"


@dataclass
class DataSource:
    """Data source information."""
    source_id: str
    source_type: str  # web, api, database, synthetic
    url: str = ""
    provider: str = ""
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    records_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Transformation:
    """Data transformation record."""
    transformation_id: str
    transformation_type: TransformationType
    timestamp: datetime
    agent_id: str = ""
    input_records: int = 0
    output_records: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineStage:
    """Pipeline stage record."""
    stage_id: str
    stage_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "pending"
    input_count: int = 0
    output_count: int = 0
    quality_score: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatasetVersion:
    """Dataset version record."""
    version_id: str
    dataset_id: str
    version_number: str
    created_at: datetime
    record_count: int = 0
    quality_score: float = 0.0
    size_bytes: int = 0
    lineage_hash: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)


class DatasetLineageTracker:
    """Tracks dataset lineage and provenance."""

    def __init__(self):
        self._datasets: Dict[str, Dict] = {}
        self._sources: Dict[str, DataSource] = {}
        self._transformations: List[Transformation] = {}
        self._lineage_graph: Dict[str, List[str]] = {}
        self._max_history = 10000

    def track_dataset(
        self,
        dataset_id: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Track a new dataset."""
        self._datasets[dataset_id] = {
            "dataset_id": dataset_id,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "sources": [],
            "transformations": []
        }

    def add_source(
        self,
        dataset_id: str,
        source: DataSource
    ) -> None:
        """Add data source to dataset."""
        if dataset_id in self._datasets:
            self._datasets[dataset_id]["sources"].append({
                "source_id": source.source_id,
                "source_type": source.source_type,
                "url": source.url,
                "accessed_at": source.accessed_at.isoformat(),
                "records_count": source.records_count
            })

            self._sources[source.source_id] = source

    def add_transformation(
        self,
        dataset_id: str,
        transformation: Transformation
    ) -> None:
        """Add transformation to dataset lineage."""
        if dataset_id not in self._transformations:
            self._transformations[dataset_id] = []

        self._transformations[dataset_id].append(transformation)
        self._datasets[dataset_id]["transformations"].append({
            "transformation_id": transformation.transformation_id,
            "type": transformation.transformation_type.value,
            "timestamp": transformation.timestamp.isoformat()
        })

        # Update lineage graph
        if dataset_id not in self._lineage_graph:
            self._lineage_graph[dataset_id] = []
        self._lineage_graph[dataset_id].append(transformation.transformation_id)

    def get_lineage(
        self,
        dataset_id: str
    ) -> Dict[str, Any]:
        """Get complete lineage for dataset."""
        dataset = self._datasets.get(dataset_id, {})
        transformations = self._transformations.get(dataset_id, [])
        sources = dataset.get("sources", [])

        return {
            "dataset_id": dataset_id,
            "created_at": dataset.get("created_at"),
            "sources": sources,
            "transformations": [
                {
                    "id": t.transformation_id,
                    "type": t.transformation_type.value,
                    "timestamp": t.timestamp.isoformat(),
                    "agent_id": t.agent_id,
                    "input_records": t.input_records,
                    "output_records": t.output_records,
                    "quality_score": t.quality_score
                }
                for t in transformations
            ],
            "lineage_hash": self._calculate_lineage_hash(dataset_id)
        }

    def _calculate_lineage_hash(self, dataset_id: str) -> str:
        """Calculate lineage hash for reproducibility."""
        lineage = self.get_lineage(dataset_id)
        lineage_str = json.dumps(lineage, sort_keys=True)
        return hashlib.sha256(lineage_str.encode()).hexdigest()[:16]

    def get_provenance_chain(
        self,
        dataset_id: str
    ) -> List[Dict]:
        """Get provenance chain as ordered list."""
        lineage = self.get_lineage(dataset_id)
        chain = []

        # Add sources
        for source in lineage.get("sources", []):
            chain.append({
                "type": "source",
                "id": source["source_id"],
                "timestamp": source["accessed_at"]
            })

        # Add transformations
        for trans in lineage.get("transformations", []):
            chain.append({
                "type": "transformation",
                "id": trans["id"],
                "transformation_type": trans["type"],
                "timestamp": trans["timestamp"]
            })

        return chain


class ProvenanceGraph:
    """Graph-based provenance tracking."""

    def __init__(self):
        self._nodes: Dict[str, Dict] = {}
        self._edges: List[Dict] = {}

    def add_node(
        self,
        node_id: str,
        node_type: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Add a node to provenance graph."""
        self._nodes[node_id] = {
            "node_id": node_id,
            "node_type": node_type,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat()
        }

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Add an edge to provenance graph."""
        edge_id = f"{source_id}->{target_id}"
        self._edges[edge_id] = {
            "edge_id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "metadata": metadata or {}
        }

    def get_upstream(self, node_id: str) -> List[str]:
        """Get upstream nodes."""
        upstream = []
        for edge_id, edge in self._edges.items():
            if edge["target_id"] == node_id:
                upstream.append(edge["source_id"])
        return upstream

    def get_downstream(self, node_id: str) -> List[str]:
        """Get downstream nodes."""
        downstream = []
        for edge_id, edge in self._edges.items():
            if edge["source_id"] == node_id:
                downstream.append(edge["target_id"])
        return downstream

    def get_path(self, source_id: str, target_id: str) -> List[str]:
        """Find path between two nodes."""
        visited = set()
        path = []

        def dfs(node_id: str) -> bool:
            if node_id == target_id:
                path.append(node_id)
                return True
            if node_id in visited:
                return False

            visited.add(node_id)
            path.append(node_id)

            for downstream in self.get_downstream(node_id):
                if dfs(downstream):
                    return True

            path.pop()
            return False

        dfs(source_id)
        return path

    def to_json(self) -> Dict:
        """Export graph as JSON."""
        return {
            "nodes": list(self._nodes.values()),
            "edges": list(self._edges.values())
        }


class QualityTracker:
    """Tracks data quality throughout pipeline."""

    def __init__(self):
        self._quality_records: Dict[str, List[Dict]] = {}
        self._thresholds = {
            "relevance": 0.7,
            "accuracy": 0.8,
            "completeness": 0.75,
            "consistency": 0.7
        }

    def record_quality(
        self,
        dataset_id: str,
        stage: str,
        scores: Dict[str, float]
    ) -> None:
        """Record quality scores."""
        if dataset_id not in self._quality_records:
            self._quality_records[dataset_id] = []

        self._quality_records[dataset_id].append({
            "stage": stage,
            "timestamp": datetime.utcnow().isoformat(),
            "scores": scores,
            "overall_score": sum(scores.values()) / max(len(scores), 1)
        })

    def get_quality_trend(
        self,
        dataset_id: str
    ) -> Dict[str, Any]:
        """Get quality trend for dataset."""
        records = self._quality_records.get(dataset_id, [])
        if not records:
            return {}

        latest = records[-1]
        earliest = records[0] if len(records) > 1 else latest

        return {
            "dataset_id": dataset_id,
            "record_count": len(records),
            "latest_scores": latest["scores"],
            "latest_overall": latest["overall_score"],
            "initial_overall": earliest.get("overall_score", 0),
            "improvement": latest["overall_score"] - earliest.get("overall_score", 0)
        }

    def get_failing_quality(self) -> List[Dict]:
        """Get records failing quality thresholds."""
        failing = []

        for dataset_id, records in self._quality_records.items():
            for record in records:
                failing_checks = []
                for metric, score in record["scores"].items():
                    threshold = self._thresholds.get(metric, 0.7)
                    if score < threshold:
                        failing_checks.append({
                            "metric": metric,
                            "score": score,
                            "threshold": threshold
                        })

                if failing_checks:
                    failing.append({
                        "dataset_id": dataset_id,
                        "stage": record["stage"],
                        "failing_checks": failing_checks
                    })

        return failing


class PipelineTelemetry:
    """Comprehensive pipeline telemetry."""

    def __init__(
        self,
        lineage_tracker: DatasetLineageTracker,
        provenance_graph: ProvenanceGraph,
        quality_tracker: QualityTracker
    ):
        self.lineage = lineage_tracker
        self.provenance = provenance_graph
        self.quality = quality_tracker

        self._stages: Dict[str, PipelineStage] = {}
        self._active_pipelines: Dict[str, List[PipelineStage]] = {}

    async def start_pipeline(
        self,
        pipeline_id: str,
        stages: List[str]
    ) -> None:
        """Start pipeline execution tracking."""
        self._active_pipelines[pipeline_id] = []

        for i, stage_name in enumerate(stages):
            stage = PipelineStage(
                stage_id=f"{pipeline_id}:stage_{i}",
                stage_name=stage_name,
                start_time=datetime.utcnow()
            )
            self._stages[stage.stage_id] = stage
            self._active_pipelines[pipeline_id].append(stage)

    async def start_stage(self, stage_id: str) -> None:
        """Mark stage as started."""
        if stage_id in self._stages:
            self._stages[stage_id].status = "running"

    async def complete_stage(
        self,
        stage_id: str,
        output_count: int,
        quality_score: float = 0.0
    ) -> None:
        """Mark stage as completed."""
        if stage_id in self._stages:
            stage = self._stages[stage_id]
            stage.end_time = datetime.utcnow()
            stage.status = "completed"
            stage.output_count = output_count
            stage.quality_score = quality_score

    async def fail_stage(
        self,
        stage_id: str,
        error: str
    ) -> None:
        """Mark stage as failed."""
        if stage_id in self._stages:
            stage = self._stages[stage_id]
            stage.end_time = datetime.utcnow()
            stage.status = "failed"
            stage.error = error

    def get_pipeline_status(self, pipeline_id: str) -> Dict[str, Any]:
        """Get pipeline execution status."""
        stages = self._active_pipelines.get(pipeline_id, [])

        if not stages:
            return {"status": "unknown"}

        completed = sum(1 for s in stages if s.status == "completed")
        failed = sum(1 for s in stages if s.status == "failed")
        running = sum(1 for s in stages if s.status == "running")

        total_duration = 0.0
        for stage in stages:
            if stage.end_time:
                total_duration += (stage.end_time - stage.start_time).total_seconds() * 1000

        return {
            "pipeline_id": pipeline_id,
            "total_stages": len(stages),
            "completed": completed,
            "failed": failed,
            "running": running,
            "status": "completed" if completed == len(stages) else "running" if running > 0 else "failed" if failed > 0 else "pending",
            "total_duration_ms": total_duration,
            "stages": [
                {
                    "name": s.stage_name,
                    "status": s.status,
                    "duration_ms": (s.end_time - s.start_time).total_seconds() * 1000 if s.end_time else 0,
                    "quality_score": s.quality_score,
                    "error": s.error
                }
                for s in stages
            ]
        }

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Get overall telemetry summary."""
        all_stages = list(self._stages.values())

        return {
            "total_pipelines": len(self._active_pipelines),
            "total_stages": len(all_stages),
            "completed_stages": sum(1 for s in all_stages if s.status == "completed"),
            "failed_stages": sum(1 for s in all_stages if s.status == "failed"),
            "avg_quality_score": sum(s.quality_score for s in all_stages) / max(len(all_stages), 1),
            "active_pipelines": list(self._active_pipelines.keys())
        }