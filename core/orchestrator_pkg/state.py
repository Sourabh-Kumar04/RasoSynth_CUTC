"""State models, Enums, and TypedDicts for DatasetOrchestrator."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from operator import add as _list_add_reducer
from typing import Annotated, Any, Optional, TypedDict

from core.intent import UserIntent


def _sanitize_metadata(meta: dict) -> dict:
    """JSON round-trip to guarantee all values are serializable."""
    try:
        return json.loads(json.dumps(meta, default=str))
    except Exception:
        return {}


def _json_safe(value: Any) -> Any:
    """Convert graph values to JSON-safe data for persistent checkpoints."""
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return [] if isinstance(value, list) else {}


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEGOTIATING = "negotiating"          # When constraints are difficult
    AWAITING_REVIEW = "awaiting_review"  # Paused at HITL gate


@dataclass
class ConstraintAnalysis:
    """Analysis of data collection constraints."""
    target_domain: str
    constraints: dict
    feasibility_score: float = 1.0
    estimated_sources: int = 0
    estimated_samples: int = 0
    estimated_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)
    fallback_strategies: list[str] = field(default_factory=list)
    constraint_conflicts: list[str] = field(default_factory=list)


@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    current_stage: str = "initialized"
    progress: float = 0.0
    samples_processed: int = 0
    samples_generated: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    config: dict = field(default_factory=dict)
    sources_discovered: int = 0
    sources_extracted: int = 0
    samples_filtered: int = 0
    constraint_analysis: ConstraintAnalysis | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_stage": self.current_stage,
            "progress": self.progress,
            "samples_processed": self.samples_processed,
            "samples_generated": self.samples_generated,
            "sources_discovered": self.sources_discovered,
            "sources_extracted": self.sources_extracted,
            "samples_filtered": self.samples_filtered,
            "cost_usd": self.cost_usd,
            "error": self.error,
            "config": self.config,
            "constraint_analysis": self.constraint_analysis.__dict__ if self.constraint_analysis else None,
        }


class AgentState(TypedDict):
    """Enhanced state for the orchestration.

    List-typed fields use ``Annotated[list, operator.add]`` reducers so that
    if two parallel nodes (or a retry that re-enters a node in the same
    super-step) try to write to the same key, LangGraph concatenates the
    values instead of raising ``INVALID_CONCURRENT_GRAPH_UPDATE``. Scalars
    are still last-write-wins.
    """
    job: dict
    sources: list
    extracted_content: list
    filtered_samples: list
    constructed_samples: list
    errors: Annotated[list[str], _list_add_reducer]
    warnings: Annotated[list[str], _list_add_reducer]
    should_retry: bool
    human_approval_needed: bool
    human_approved: bool
    messages: Annotated[list[str], _list_add_reducer]
    current_stage: str
    progress: float
    constraint_analysis: dict | None
    low_resource_mode: bool
    multilingual_mode: bool
    adaptation_notes: Annotated[list[str], _list_add_reducer]
    filter_retry_count: int
    dataset_plan: dict | None
    coverage_matrix: dict | None
    balance_report: dict | None
    intent: UserIntent | None
    resume_from_stage: str | None
    quality_score: float | None
    quality_eval_passed: bool | None
    quality_breakdown: dict | None
    agent_artifacts: dict
    synthesis_retries: int
    missing_reference_count: int
    evidence_context: list
