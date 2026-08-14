"""
Response Schemas

Standard API response schemas for success, errors,
and validation feedback.
"""

from typing import Dict, List, Optional, Any, Generic, TypeVar, Union, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from api.schemas.base import BaseSchema

T = TypeVar("T")


class ResponseStatus(str, Enum):
    """Response status codes."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PARTIAL = "partial"


class ErrorCode(str, Enum):
    """Standard error codes."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    CONFLICT = "CONFLICT"
    UNPROCESSABLE_ENTITY = "UNPROCESSABLE_ENTITY"


class ValidationError(BaseSchema):
    """Individual validation error."""
    field: str
    message: str
    code: Optional[str] = None
    suggestion: Optional[str] = None

    value: Optional[Any] = None
    constraint: Optional[Dict[str, Any]] = None


class ErrorDetail(BaseSchema):
    """Error detail information."""
    code: ErrorCode
    message: str
    details: Optional[str] = None

    field_errors: List[ValidationError] = Field(default_factory=list)

    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    help_url: Optional[str] = None
    documentation_url: Optional[str] = None


class ErrorResponse(BaseSchema):
    """Standard error response."""
    status: ResponseStatus = ResponseStatus.ERROR
    error: ErrorDetail

    trace_id: Optional[str] = None

    @classmethod
    def from_exception(
        cls,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        request_id: Optional[str] = None
    ) -> "ErrorResponse":
        """Create error response from exception."""
        return cls(
            error=ErrorDetail(
                code=code,
                message=message,
                request_id=request_id
            )
        )

    @classmethod
    def validation_error(
        cls,
        errors: List[ValidationError],
        message: str = "Validation failed",
        request_id: Optional[str] = None
    ) -> "ErrorResponse":
        """Create validation error response."""
        return cls(
            error=ErrorDetail(
                code=ErrorCode.VALIDATION_ERROR,
                message=message,
                field_errors=errors,
                request_id=request_id
            )
        )


class WarningDetail(BaseSchema):
    """Warning detail information."""
    code: str
    message: str
    field: Optional[str] = None

    suggestion: Optional[str] = None


class PaginationMeta(BaseSchema):
    """Pagination metadata."""
    page: int = 1
    page_size: int = 20
    total_items: int = 0
    total_pages: int = 0

    has_next: bool = False
    has_previous: bool = False

    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None


class MetaInfo(BaseSchema):
    """Response metadata."""
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    version: str = "1.0.0"

    pagination: Optional[PaginationMeta] = None

    warnings: List[WarningDetail] = Field(default_factory=list)

    execution_time_ms: Optional[float] = None

    rate_limit_remaining: Optional[int] = None
    rate_limit_reset_at: Optional[datetime] = None


class APIResponse(BaseSchema, Generic[T]):
    """Standard API response wrapper."""
    status: ResponseStatus = ResponseStatus.SUCCESS
    data: Optional[T] = None
    meta: MetaInfo = Field(default_factory=MetaInfo)

    @classmethod
    def success(
        cls,
        data: T,
        request_id: Optional[str] = None,
        warnings: Optional[List[WarningDetail]] = None
    ) -> "APIResponse[T]":
        """Create success response."""
        meta = MetaInfo(request_id=request_id)
        if warnings:
            meta.warnings = warnings

        return cls(
            status=ResponseStatus.SUCCESS,
            data=data,
            meta=meta
        )

    @classmethod
    def paginated(
        cls,
        data: List[Any],
        pagination: PaginationMeta,
        request_id: Optional[str] = None
    ) -> "APIResponse[List[Any]]":
        """Create paginated response."""
        meta = MetaInfo(
            request_id=request_id,
            pagination=pagination
        )

        return cls(
            status=ResponseStatus.SUCCESS,
            data=data,
            meta=meta
        )


class SuccessResponse(BaseSchema):
    """Simple success response."""
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: str
    data: Optional[Dict[str, Any]] = None

    @classmethod
    def created(
        cls,
        resource_id: str,
        message: str = "Resource created successfully",
        **kwargs
    ) -> "SuccessResponse":
        """Create resource created response."""
        return cls(
            status=ResponseStatus.SUCCESS,
            message=message,
            data={"id": resource_id, **kwargs}
        )

    @classmethod
    def updated(
        cls,
        resource_id: str,
        message: str = "Resource updated successfully",
        **kwargs
    ) -> "SuccessResponse":
        """Create resource updated response."""
        return cls(
            status=ResponseStatus.SUCCESS,
            message=message,
            data={"id": resource_id, **kwargs}
        )

    @classmethod
    def deleted(
        cls,
        resource_id: str,
        message: str = "Resource deleted successfully"
    ) -> "SuccessResponse":
        """Create resource deleted response."""
        return cls(
            status=ResponseStatus.SUCCESS,
            message=message,
            data={"id": resource_id}
        )


class HealthResponse(BaseSchema):
    """Health check response."""
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"

    version: str = "1.0.0"
    uptime_seconds: float = 0.0

    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatusResponse(BaseSchema):
    """Generic status response."""
    status: Literal["ok", "error", "warning"] = "ok"
    message: Optional[str] = None

    details: Dict[str, Any] = Field(default_factory=dict)


class BatchResponse(BaseSchema):
    """Batch operation response."""
    total: int
    successful: int
    failed: int

    results: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total == 0:
            return 0.0
        return self.successful / self.total


class StreamResponse(BaseSchema):
    """Streaming response chunk."""
    event: str = "message"
    data: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None
    retry: int = 3000