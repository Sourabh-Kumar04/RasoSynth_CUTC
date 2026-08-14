"""
ARCHITECTURE CONSOLIDATION

Canonical server: api/server.py (started by main.py)
Deprecated references (NOT for production):
  - api/server_v2.py           (CORS security vulnerability)
  - api/server_production.py   (reference only, uses stub orchestrator)
  - api/server_standalone.py   (standalone, not for production deployment)

AI-Native API System

Intelligent API layer with constraint-aware validation,
semantic request understanding, dynamic schema generation,
and distributed orchestration integration.
"""

from typing import Optional
from fastapi import FastAPI

# Import schema modules (from package, not the file)
from api.schemas import (
    # Base Schemas
    BaseSchema,
    ConstraintType,
    ConstraintScope,
    Constraint,
    ConstraintGroup,
    SemanticRequest,
    RequestPriority,
    RetryPolicy,
    TimeoutConfig,

    # Dataset Schemas
    DataModality,
    DatasetFormat,
    QualityLevel,
    DatasetType,
    QualityConstraints,
    DataConstraints,
    SyntheticDataConfig,
    DatasetMetadata,
    DatasetConfig,
    DatasetGenerationRequest,
    DatasetExportRequest,
    DatasetFilter,

    # Workflow Schemas
    OrchestrationMode,
    ExecutionStrategy,
    StepStatus,
    StepType,
    StepDependency,
    StepResourceAllocation,
    WorkflowStep,
    WorkflowConfig,
    WorkflowPlan,
    WorkflowExecution,
    WorkflowTemplate,
    WorkflowSearch,

    # Orchestration Schemas
    TaskStatus,
    TaskPriority,
    TaskNode,
    TaskGraph,
    GPUAllocation,
    ProviderRouting,
    DistributedExecution,
    OrchestrationRequest,
    ExecutionMetrics,
    WorkerState,
    ShardingConfig,

    # Multimodal Schemas
    MultimodalModality,
    ProcessingPriority,
    MultimodalInput,
    ImageConfig,
    VideoConfig,
    AudioConfig,
    OCRConfig,
    PDFConfig,
    CodeConfig,
    TableConfig,
    ProcessingConfig,
    MultimodalFusion,
    ModalityRequirements,
    MultimodalRequest,
    ProcessingResult,
    ModalityCapability,

    # Validation Schemas
    ValidationStatus,
    ValidationSeverity,
    FeasibilityLevel,
    ConflictDetection,
    OptimizationSuggestion,
    ConstraintAnalysis,
    FeasibilityResult,
    ValidationIssue,
    ValidationResult,
    SemanticAnalysis,
    CostAnalysis,
    ResourceAnalysis,
    ScalabilityAssessment,
    ValidationSummary,

    # Planning Schemas
    PlanStatus,
    PlanStep,
    ExecutionPlan,
    CostEstimate,
    StorageEstimate,
    PlanningResourceAllocation,
    ProviderRecommendation,
    PlanOptimization,
    WorkflowOptimization,

    # Job Schemas
    JobStatus,
    JobEvent,
    WebhookEvent,
    WebhookConfig,
    JobProgress,
    JobResult,
    JobCancellation,
    JobQuery,
    JobEventLog,
    JobMetadata,
    JobSummary,

    # Provider Schemas
    ProviderConstraint,
    ModelConstraint,
    CostBudget,
    RoutingPolicy,
    ModelSelection,
    ProviderMetrics,
    ProviderHealth,
    ProviderConfigUpdate,

    # Security Schemas
    RBACPermission,
    RoleType,
    UserContext,
    TenantContext,
    RateLimitConfig,
    SecurityPolicy,
    AuditLogEntry,
    APIKey,
    PolicyEvaluation,

    # Response Schemas
    ResponseStatus,
    ErrorCode,
    ValidationError,
    ErrorDetail,
    ErrorResponse,
    WarningDetail,
    PaginationMeta,
    MetaInfo,
    APIResponse,
    SuccessResponse,
    HealthResponse,
    StatusResponse,
    BatchResponse,
    StreamResponse,
)

# Import validation engine
from api.validation import (
    ConstraintReasoningEngine,
    SemanticValidator,
    ConstraintAnalyzer,
    DynamicSchemaGenerator,
    SchemaPlugin,
    SchemaRegistry,
)

# Import planning
from api.planning import (
    WorkflowPlanner,
    CostEstimator,
    ResourcePlanner,
    ExecutionOptimizer,
)

# Import execution
from api.execution import (
    JobState,
    JobCheckpoint,
    ProgressTracker,
    ResumableWorkflow,
    AsyncJobExecutor,
    WebhookNotifier,
)

# Observability
from api.observability.metrics import (
    APIMetrics,
    ValidationMetrics,
    OrchestrationMetrics,
    MetricsCollector,
)


# ============================================================================
# Application Factory Pattern (No Circular Imports)
# ============================================================================

class ApplicationFactory:
    """
    Factory for creating properly initialized application instances.

    This eliminates circular lazy imports by deferring app creation
    to a factory method that can be called after all modules are loaded.
    """

    _instance: Optional["ApplicationFactory"] = None

    def __init__(self):
        self._app: Optional[FastAPI] = None
        self._initialized: bool = False

    @classmethod
    def get_instance(cls) -> "ApplicationFactory":
        """Get singleton factory instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_app(
        self,
        include_server: bool = True,
        include_middleware: bool = True,
    ) -> FastAPI:
        """
        Create application with proper dependency injection.

        Args:
            include_server: Include server endpoints
            include_middleware: Include standard middleware

        Returns:
            Fully initialized FastAPI application
        """
        # Import here to avoid circular dependency
        from fastapi import FastAPI
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Initialize components on startup
            yield
            # Cleanup on shutdown

        app = FastAPI(
            title="RasoSynthTune",
            description="Autonomous dataset generation with constraint-aware intelligence",
            version="2.0.0",
            lifespan=lifespan,
        )

        # Add middleware if requested
        if include_middleware:
            from fastapi.middleware.cors import CORSMiddleware

            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Configure for production
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # Include routers if server is included
        if include_server:
            self._register_routes(app)

        self._app = app
        self._initialized = True
        return app

    def _register_routes(self, app: FastAPI) -> None:
        """Register all API routes."""
        # Import routers lazily to avoid circular imports
        try:
            from api.routes import jobs, datasets, providers, research, health
            app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
            app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["Datasets"])
            app.include_router(providers.router, prefix="/api/v1/providers", tags=["Providers"])
            app.include_router(research.router, prefix="/api/v1/research", tags=["Research"])
            app.include_router(health.router, prefix="/health", tags=["Health"])
        except ImportError:
            # Routes module not yet created - skip
            pass

    def get_app(self) -> Optional[FastAPI]:
        """Get existing app instance or None."""
        return self._app

    @property
    def is_initialized(self) -> bool:
        return self._initialized


def get_app_factory() -> ApplicationFactory:
    """Get application factory instance."""
    return ApplicationFactory.get_instance()


def create_app() -> FastAPI:
    """Create new application instance."""
    return get_app_factory().create_app()


# Backwards compatibility - lazy import for existing code
_app = None

def get_app():
    """Lazy import of FastAPI app (backwards compatibility)."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


def __getattr__(name):
    if name == "app":
        return get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Factory
    "ApplicationFactory",
    "get_app_factory",
    "create_app",

    # Legacy (backwards compatible)
    "app",
    "get_app",

    # Base Schemas
    "BaseSchema",
    "ConstraintType",
    "ConstraintScope",
    "Constraint",
    "ConstraintGroup",
    "SemanticRequest",
    "RequestPriority",
    "RetryPolicy",
    "TimeoutConfig",

    # Dataset Schemas
    "DataModality",
    "DatasetFormat",
    "QualityLevel",
    "DatasetType",
    "QualityConstraints",
    "DataConstraints",
    "SyntheticDataConfig",
    "DatasetMetadata",
    "DatasetConfig",
    "DatasetGenerationRequest",
    "DatasetExportRequest",
    "DatasetFilter",

    # Workflow Schemas
    "OrchestrationMode",
    "ExecutionStrategy",
    "StepStatus",
    "StepType",
    "StepDependency",
    "StepResourceAllocation",
    "WorkflowStep",
    "WorkflowConfig",
    "WorkflowPlan",
    "WorkflowExecution",
    "WorkflowTemplate",
    "WorkflowSearch",

    # Orchestration Schemas
    "TaskStatus",
    "TaskPriority",
    "TaskNode",
    "TaskGraph",
    "GPUAllocation",
    "ProviderRouting",
    "DistributedExecution",
    "OrchestrationRequest",
    "ExecutionMetrics",
    "WorkerState",
    "ShardingConfig",

    # Multimodal Schemas
    "MultimodalModality",
    "ProcessingPriority",
    "MultimodalInput",
    "ImageConfig",
    "VideoConfig",
    "AudioConfig",
    "OCRConfig",
    "PDFConfig",
    "CodeConfig",
    "TableConfig",
    "ProcessingConfig",
    "MultimodalFusion",
    "ModalityRequirements",
    "MultimodalRequest",
    "ProcessingResult",
    "ModalityCapability",

    # Validation Schemas
    "ValidationStatus",
    "ValidationSeverity",
    "FeasibilityLevel",
    "ConflictDetection",
    "OptimizationSuggestion",
    "ConstraintAnalysis",
    "FeasibilityResult",
    "ValidationIssue",
    "ValidationResult",
    "SemanticAnalysis",
    "CostAnalysis",
    "ResourceAnalysis",
    "ScalabilityAssessment",
    "ValidationSummary",

    # Planning Schemas
    "PlanStatus",
    "PlanStep",
    "ExecutionPlan",
    "CostEstimate",
    "StorageEstimate",
    "PlanningResourceAllocation",
    "ProviderRecommendation",
    "PlanOptimization",
    "WorkflowOptimization",

    # Job Schemas
    "JobStatus",
    "JobEvent",
    "WebhookEvent",
    "WebhookConfig",
    "JobProgress",
    "JobResult",
    "JobCancellation",
    "JobQuery",
    "JobEventLog",
    "JobMetadata",
    "JobSummary",

    # Provider Schemas
    "ProviderConstraint",
    "ModelConstraint",
    "CostBudget",
    "RoutingPolicy",
    "ModelSelection",
    "ProviderMetrics",
    "ProviderHealth",
    "ProviderConfigUpdate",

    # Security Schemas
    "RBACPermission",
    "RoleType",
    "UserContext",
    "TenantContext",
    "RateLimitConfig",
    "SecurityPolicy",
    "AuditLogEntry",
    "APIKey",
    "PolicyEvaluation",

    # Response Schemas
    "ResponseStatus",
    "ErrorCode",
    "ValidationError",
    "ErrorDetail",
    "ErrorResponse",
    "WarningDetail",
    "PaginationMeta",
    "MetaInfo",
    "APIResponse",
    "SuccessResponse",
    "HealthResponse",
    "StatusResponse",
    "BatchResponse",
    "StreamResponse",

    # Validation Engine
    "ConstraintReasoningEngine",
    "SemanticValidator",
    "ConstraintAnalyzer",
    "DynamicSchemaGenerator",
    "SchemaPlugin",
    "SchemaRegistry",

    # Planning
    "WorkflowPlanner",
    "CostEstimator",
    "ResourcePlanner",
    "ExecutionOptimizer",

    # Execution
    "JobState",
    "JobCheckpoint",
    "ProgressTracker",
    "ResumableWorkflow",
    "AsyncJobExecutor",
    "WebhookNotifier",

    # Observability
    "APIMetrics",
    "ValidationMetrics",
    "OrchestrationMetrics",
    "MetricsCollector",
]