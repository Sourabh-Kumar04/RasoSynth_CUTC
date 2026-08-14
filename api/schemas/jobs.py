"""
Job Schemas

Schemas for async job management, progress tracking,
webhooks, and job cancellation.
"""

from typing import Dict, List, Optional, Any, Set, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from api.schemas.base import BaseSchema


class JobStatus(str, Enum):
    """Status of async job."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class JobEvent(str, Enum):
    """Job lifecycle events."""
    CREATED = "created"
    QUEUED = "queued"
    STARTED = "started"
    PROGRESS = "progress"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CHECKPOINT = "checkpoint"


class WebhookEvent(BaseModel):
    """Webhook event payload."""
    event: JobEvent
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    job_id: str
    job_status: JobStatus

    payload: Dict[str, Any] = Field(default_factory=dict)

    retry_count: int = 0


class WebhookConfig(BaseSchema):
    """Webhook configuration for job notifications."""
    enabled: bool = True
    url: str

    events: List[JobEvent] = Field(default_factory=lambda: [
        JobEvent.COMPLETED, JobEvent.FAILED
    ])

    secret: Optional[str] = None
    signature_header: str = "X-Webhook-Signature"

    retry_policy: Dict[str, Any] = Field(default_factory=lambda: {
        "max_retries": 3,
        "backoff_factor": 2.0,
        "retry_on": [408, 429, 500, 502, 503, 504]
    })

    timeout_seconds: int = 30
    include_payload: bool = True


class JobProgress(BaseSchema):
    """Job progress tracking."""
    job_id: str

    status: JobStatus

    progress_percentage: float = 0.0
    samples_processed: int = 0
    samples_total: int = 0

    current_step: Optional[str] = None
    current_phase: Optional[str] = None

    estimated_remaining_seconds: Optional[int] = None

    checkpoints: List[Dict[str, Any]] = Field(default_factory=list)

    metrics: Dict[str, float] = Field(default_factory=dict)

    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobResult(BaseSchema):
    """Job completion result."""
    job_id: str

    status: JobStatus

    output: Optional[Dict[str, Any]] = None

    dataset_id: Optional[str] = None
    dataset_url: Optional[str] = None

    metrics: Dict[str, Any] = Field(default_factory=dict)

    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0

    quality_metrics: Dict[str, float] = Field(default_factory=dict)

    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    completed_at: datetime = Field(default_factory=datetime.utcnow)


class JobCancellation(BaseSchema):
    """Job cancellation request."""
    job_id: str
    reason: str = ""

    force: bool = False

    cleanup_resources: bool = True
    preserve_checkpoints: bool = True

    notification_enabled: bool = True


class JobQuery(BaseSchema):
    """Job query parameters."""
    status: Optional[List[JobStatus]] = None

    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    completed_after: Optional[datetime] = None
    completed_before: Optional[datetime] = None

    workflow_id: Optional[str] = None
    dataset_id: Optional[str] = None

    min_cost: Optional[float] = None
    max_cost: Optional[float] = None

    tags: Optional[List[str]] = None

    sort_by: Literal["created_at", "updated_at", "status", "cost"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"

    page: int = 1
    page_size: int = 20


class JobEventLog(BaseSchema):
    """Job event log entry."""
    job_id: str
    event: JobEvent

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    details: Dict[str, Any] = Field(default_factory=dict)

    source: Optional[str] = None
    correlation_id: Optional[str] = None


class JobMetadata(BaseSchema):
    """Additional job metadata."""
    job_id: str

    workflow_name: Optional[str] = None
    workflow_version: Optional[str] = None

    user_id: Optional[str] = None
    tenant_id: Optional[str] = None

    priority: Literal["low", "normal", "high", "urgent"] = "normal"

    tags: List[str] = Field(default_factory=list)

    constraints_summary: Dict[str, Any] = Field(default_factory=dict)

    parent_job_id: Optional[str] = None
    root_job_id: Optional[str] = None


class JobSummary(BaseSchema):
    """Job summary for list views."""
    job_id: str
    status: JobStatus

    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    progress_percentage: float = 0.0
    samples_processed: int = 0
    samples_total: int = 0

    workflow_name: Optional[str] = None

    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0

    error_summary: Optional[str] = None