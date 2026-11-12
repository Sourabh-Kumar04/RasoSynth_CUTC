"""FastAPI server with enhanced constraint handling and research capabilities."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import time
from typing import Optional
import uuid

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from api.schemas import (
    BaseSchema, ConstraintType, Constraint, SemanticRequest,
    DatasetConfig, DatasetGenerationRequest, WorkflowConfig, WorkflowStep,
    ValidationResult, FeasibilityResult, ExecutionPlan, JobStatus as JobStatusEnum,
    ConstraintReasoningEngine, SemanticValidator, WorkflowPlanner,
    APIMetrics, ValidationMetrics,
)

from api.legacy_schemas import (
    AdaptabilityRequest,
    AdaptabilityResponse,
    CheckpointResponse,
    CheckpointStage,
    ConstraintAnalysis,
    CreateCheckpointRequest,
    DeliveryRequestSchema,
    DeliveryResponseSchema,
    ErrorResponse,
    FailoverHistoryResponse,
    FailoverRequest,
    FailoverResponse,
    HealthResponse,
    JobDetailResponse,
    JobRequest,
    JobResponse,
    ProviderContextSchema,
    ProviderStatus,
    ProviderSwitchRequest,
    ProviderSwitchResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    ReportResponse,
    ResearchRequest,
    ResearchResponse,
    RestoreCheckpointRequest,
    RestoreCheckpointResponse,
)
from core.config import get_settings
from core.intent import UserIntent
from core.provider_router import ProviderRouter, TaskType
from core.orchestrator_core import DatasetOrchestrator, Job, JobStatus
from core.db import AsyncDB
from core.cache import SimpleRedisCache as CacheManager
from core.observability import ObservabilityManager, correlation_id_var, trace_id_var
from core.research_loop import ResearchLoop, TechniqueIntegrator
from api.websocket_manager import ConnectionManager, get_ws_manager, MessageType
from api.provider_validator import ProviderValidator
from api.auth import get_auth_manager, UserRole, User, get_current_user, get_current_user_optional, require_role
from api.review import router as review_router
from api.quality import router as quality_router
from api.finetune import router as finetune_router
from api.schedules import router as schedules_router

# Security, CSRF, and Rate Limiting
from api.security import (
    RateLimiter,
    get_client_ip,
    CSRFTokenManager,
    _csrf_manager,
    _login_rate_limiter,
    _provider_test_rate_limiter,
    _sign_approved_examples,
    _get_download_signing_secret,
    _sign_download_token,
    _verify_download_token,
    _enforce_owner,
)
from api.disk_resolver import resolve_dynamic_disk_dataset, _resolve_dynamic_disk_dataset


# Global constants
MAX_SAMPLE_LOAD_LIMIT = int(os.getenv("MAX_SAMPLE_LOAD_LIMIT", "10000"))


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware that validates CSRF tokens on state-changing methods (POST, PUT, DELETE).

    Skips CSRF validation for:
    - /auth/* endpoints (login/logout need to be accessible)
    - /health, /metrics, /docs, /openapi.json
    - OPTIONS requests (CORS preflight)
    - WebSocket upgrade requests
    """

    SKIP_PATHS = {
        "/auth/login", "/auth/logout", "/health", "/health/ready", "/health/live",
        "/metrics", "/docs", "/redoc", "/openapi.json", "/"
    }

    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        path = request.url.path
        if path in self.SKIP_PATHS or path.startswith(("/auth/", "/docs", "/redoc", "/openapi")):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            logger.warning(f"CSRF token missing on {request.method} {path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token required. Include X-CSRF-Token header. "
                         "Fetch a token from GET /auth/csrf-token."}
            )

        # Get user from JWT if present. A token bound to "anonymous"
        # is never accepted: CSRF tokens are only issued to authenticated
        # users (GET /auth/csrf-token), so an anonymous token on a
        # state-changing request is rejected here even if it was minted
        # before this fix and is still within its TTL.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                auth_mgr = get_auth_manager()
                token_data = auth_mgr.verify_token(auth_header[7:])
                user_id = token_data.user_id
            except Exception:
                user_id = "anonymous"
        else:
            user_id = "anonymous"

        if user_id == "anonymous":
            logger.warning(f"CSRF token presented without an authenticated user on {request.method} {path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token requires an authenticated user. "
                         "Fetch a token from GET /auth/csrf-token with a valid Authorization header."}
            )

        if not _csrf_manager.validate_token(csrf_token, user_id):
            logger.warning(f"Invalid/expired CSRF token on {request.method} {path} for user {user_id}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid or expired CSRF token. Fetch a new token from GET /auth/csrf-token."}
            )

        return await call_next(request)


settings = get_settings()

router: Optional[ProviderRouter] = None
orchestrator: Optional[DatasetOrchestrator] = None
db: Optional[AsyncDB] = None
cache: Optional[CacheManager] = None
observability: Optional[ObservabilityManager] = None
research_loop: Optional[ResearchLoop] = None
technique_integrator: Optional[TechniqueIntegrator] = None
ws_manager: Optional[ConnectionManager] = None
provider_validator: Optional[ProviderValidator] = None
admission_controller = None

checkpoint_manager = None
checkpoint_store = None
failover_engine = None
provider_hot_switcher = None


def _get_cors_origins() -> list[str]:
    """Get CORS origins based on environment."""
    from core.environment import get_current_environment
    env = get_current_environment()
    cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")

    if cors_origins:
        return [o.strip() for o in cors_origins.split(",") if o.strip()]

    if env in ("production", "gpu_cluster"):
        # If CORS_ALLOWED_ORIGINS is not explicitly configured, default to the official production frontend
        default_prod_origins = [
            "https://rasosynthtune-indiaai.vercel.app",
            "https://sourabh-kumar04-rasosynthtune.hf.space",
        ]
        logger.info(f"CORS_ALLOWED_ORIGINS unset in {env}; defaulting to {default_prod_origins}")
        return default_prod_origins

    return [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to all responses."""

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none';",
    }

    LARGE_BODY_PATHS = {"/jobs", "/datasets", "/providers"}
    MAX_BODY_SIZE = int(os.getenv("MAX_REQUEST_BODY_SIZE", "10485760"))

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum size is {self.MAX_BODY_SIZE} bytes."}
            )

        response = await call_next(request)

        for header_name, header_value in self.SECURITY_HEADERS.items():
            response.headers[header_name] = header_value

        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


class TracingMiddleware(BaseHTTPMiddleware):
    """Distributed tracing and request context propagation middleware."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        correlation_id = (
            request.headers.get("x-correlation-id")
            or request.headers.get("X-Correlation-ID")
            or f"corr-{uuid.uuid4().hex[:12]}"
        )
        trace_id = (
            request.headers.get("x-trace-id")
            or request.headers.get("X-Trace-ID")
            or f"tr-{uuid.uuid4().hex[:16]}"
        )

        correlation_id_var.set(correlation_id)
        trace_id_var.set(trace_id)

        status = "ok"
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                status = "error"
            response.headers["x-trace-id"] = trace_id
            response.headers["x-correlation-id"] = correlation_id
            return response
        except Exception:
            status = "error"
            raise
        finally:
            elapsed_ms = (time.time() - start_time) * 1000.0
            obs = getattr(request.app.state, "observability", None) or observability
            if obs is not None:
                try:
                    obs.record_trace(
                        operation=f"{request.method} {request.url.path}",
                        duration_ms=elapsed_ms,
                        status=status,
                        service="api",
                        trace_id=trace_id,
                        correlation_id=correlation_id,
                        details={"status_code": status_code},
                    )
                except Exception as trace_err:
                    logger.debug("Failed to record trace in middleware: %s", trace_err)


# ---- Lifespan: initialize global services on startup, clean up on shutdown ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: wires the module-global services."""
    global router, orchestrator, db, cache, observability
    global research_loop, technique_integrator, ws_manager, provider_validator
    global admission_controller
    global checkpoint_manager, checkpoint_store, failover_engine, provider_hot_switcher

    # 1. Security check first
    _validate_security_config()

    # 2. Observability
    try:
        observability = ObservabilityManager(service_name="rasosynth-api")
        app.state.observability = observability
        logger.info("  ✓ ObservabilityManager initialized")
    except Exception as e:
        logger.warning(f"  ⚠ ObservabilityManager failed to initialize: {e}")

    # 3. Database
    try:
        db = AsyncDB()
        await db.connect()
        app.state.db = db
        logger.info("  ✓ AsyncDB connected")
    except Exception as e:
        logger.warning(f"  ⚠ AsyncDB failed to connect (using in-memory fallback where possible): {e}")

    # 4. Cache
    try:
        cache = CacheManager()
        await cache.connect()
        app.state.cache = cache
        logger.info("  ✓ Cache connected")
    except Exception as e:
        logger.warning(f"  ⚠ Cache failed to connect (degrading gracefully): {e}")

    # 5. WebSocket ConnectionManager
    try:
        ws_manager = await get_ws_manager()
        app.state.ws_manager = ws_manager
        logger.info("  ✓ WebSocket ConnectionManager initialized")
    except Exception as e:
        logger.warning(f"  ⚠ WebSocket manager initialization: {e}")

    # 6. ProviderRouter
    try:
        router = ProviderRouter()
        app.state.router = router
        app.state.provider_router = router
        logger.info(f"  ✓ ProviderRouter initialized with {len(router.get_available_providers())} provider(s)")
    except Exception as e:
        logger.warning(f"  ⚠ ProviderRouter failed to initialize: {e}")

    # 7. ProviderValidator
    try:
        provider_validator = ProviderValidator(router=router)
        app.state.provider_validator = provider_validator
        logger.info("  ✓ ProviderValidator initialized")
    except Exception as e:
        logger.warning(f"  ⚠ ProviderValidator failed to initialize: {e}")

    # 8. Admission Controller
    try:
        from core.admission_control import AdmissionController
        admission_controller = AdmissionController(
            max_concurrent_jobs=int(os.getenv("MAX_CONCURRENT_JOBS", "4")),
            max_queue_size=int(os.getenv("MAX_JOB_QUEUE_DEPTH", "64")),
        )
        app.state.admission_controller = admission_controller
        logger.info("  ✓ AdmissionController initialized (max_concurrent=%d)", admission_controller._max_concurrent)
    except Exception as e:
        logger.warning("  ⚠ AdmissionController failed to initialize: %s", e)

    # 9. DatasetOrchestrator
    try:
        orchestrator_config = {
            "max_concurrent_jobs": int(os.getenv("MAX_CONCURRENT_JOBS", "4")),
            "quality_threshold": float(os.getenv("DEFAULT_QUALITY_THRESHOLD", "0.7")),
            "aikosh_api_key": settings.aikosh_api_key,
        }
        orchestrator = DatasetOrchestrator(
            config=orchestrator_config,
            router=router,
            db=db,
            observability=observability,
            ws_manager=ws_manager,
        )
        app.state.orchestrator = orchestrator
        logger.info("  ✓ DatasetOrchestrator initialized")
    except Exception as e:
        logger.warning(f"  ⚠ DatasetOrchestrator failed to initialize: {e}")

    # 10. ResearchLoop and TechniqueIntegrator
    try:
        research_loop = ResearchLoop(router=router)
        technique_integrator = TechniqueIntegrator(router=router)
        app.state.research_loop = research_loop
        app.state.technique_integrator = technique_integrator
        logger.info("  ✓ ResearchLoop and TechniqueIntegrator initialized")
    except Exception as e:
        logger.warning(f"  ⚠ ResearchLoop failed to initialize: {e}")

    # 11. Checkpoint Manager & Store
    try:
        from core.checkpoints import CheckpointManager, SQLiteCheckpointStore
        checkpoint_store = SQLiteCheckpointStore()
        await checkpoint_store.initialize()
        checkpoint_manager = CheckpointManager(store=checkpoint_store, db=db)
        app.state.checkpoint_manager = checkpoint_manager
        app.state.checkpoint_store = checkpoint_store
        logger.info("  ✓ CheckpointManager and SQLiteCheckpointStore initialized")
    except Exception as e:
        logger.warning(f"  ⚠ CheckpointManager failed to initialize: {e}")

    # 12. Failover Engine and Hot Switcher
    try:
        from providers.failover import AutomaticFailoverEngine, ProviderHotSwitcher
        failover_engine = AutomaticFailoverEngine(
            provider_registry=router,
            checkpoint_manager=checkpoint_manager,
        )
        provider_hot_switcher = ProviderHotSwitcher(
            failover_engine=failover_engine,
            provider_router=router,
        )
        app.state.failover_engine = failover_engine
        app.state.provider_hot_switcher = provider_hot_switcher
        logger.info("  ✓ AutomaticFailoverEngine and ProviderHotSwitcher initialized")
    except Exception as e:
        logger.warning(f"  ⚠ FailoverEngine failed to initialize: {e}")

    # 13. Service Container (ADR-003)
    try:
        from core.di.container import ServiceContainer
        container = ServiceContainer(settings=settings)
        if db is not None:
            container.register_instance(type(db), db)
        if cache is not None:
            container.register_instance(type(cache), cache)
        if router is not None:
            container.register_instance(type(router), router)
        if orchestrator is not None:
            container.register_instance(type(orchestrator), orchestrator)
        if observability is not None:
            container.register_instance(type(observability), observability)
        if failover_engine is not None:
            container.register_instance(type(failover_engine), failover_engine)
        if provider_hot_switcher is not None:
            container.register_instance(type(provider_hot_switcher), provider_hot_switcher)
        try:
            from core.storage.delivery import DeliveryManager
            delivery_manager = DeliveryManager()
            container.register_instance(DeliveryManager, delivery_manager)
            app.state.delivery_manager = delivery_manager
            if orchestrator is not None:
                orchestrator.delivery_manager = delivery_manager
        except Exception as dm_err:
            logger.debug(f"DeliveryManager registration skipped: {dm_err}")
        try:
            from agents.registry import AgentRegistry, AgentRegistryInitializer
            AgentRegistryInitializer.initialize()
            app.state.agent_registry = AgentRegistry
            container.register_instance(AgentRegistry, AgentRegistry.get_instance())
            logger.info("  ✓ AgentRegistry initialized with builtin agents")
        except Exception as agent_err:
            logger.debug(f"AgentRegistry initialization skipped: {agent_err}")
        app.state.container = container
        logger.info("  ✓ ServiceContainer initialized")
    except Exception as e:
        logger.warning(f"  ⚠ ServiceContainer initialization skipped: {e}")

    yield

    # ---- Shutdown ----
    logger.info("RasoSynthTune: shutting down")
    if getattr(app.state, "container", None) is not None:
        try:
            await app.state.container.shutdown()
        except Exception as e:
            logger.warning(f"  ⚠ ServiceContainer shutdown failed: {e}")

    if admission_controller is not None:
        try:
            await admission_controller.stop()
        except Exception as e:
            logger.warning("  ⚠ AdmissionController stop failed: %s", e)
        admission_controller = None
        app.state.admission_controller = None

    if db is not None:
        try:
            await db.close()
        except Exception as e:
            logger.warning(f"  ⚠ db.close() failed: {e}")

    if checkpoint_store is not None:
        try:
            await checkpoint_store.close()
        except Exception as e:
            logger.warning("  ⚠ checkpoint store close failed: %s", e)

    if cache is not None:
        try:
            await cache.disconnect()
        except Exception as e:
            logger.warning(f"  ⚠ cache.disconnect() failed: {e}")

    logger.info("Shutdown complete")


app = FastAPI(lifespan=lifespan)

# ── Sub-routers ────────────────────────────────────────────────────────────────
app.include_router(review_router)
app.include_router(quality_router)
app.include_router(finetune_router)
app.include_router(schedules_router)

from api.routers.health import router as health_router
from api.routers.providers import router as providers_router
from api.routers.observability import router as observability_router
from api.routers.research import router as research_router, _research_cycle_status
from api.routers.agents import router as agents_router
from api.routers.delivery import router as delivery_router
from api.routers.checkpoints import router as checkpoints_router
from api.routers.failover import router as failover_router
from api.routers.tools import router as tools_router
from api.routers.orchestration import router as orchestration_router
from api.routers.datasets import router as datasets_router
from api.routers.validation import router as validation_router
from api.routers.auth import router as auth_router
from api.routers.jobs import router as jobs_router

app.include_router(health_router)
app.include_router(providers_router)
app.include_router(observability_router)
app.include_router(research_router)
app.include_router(agents_router)
app.include_router(delivery_router)
app.include_router(checkpoints_router)
app.include_router(failover_router)
app.include_router(tools_router)
app.include_router(orchestration_router)
app.include_router(datasets_router)
app.include_router(validation_router)
app.include_router(auth_router)
app.include_router(jobs_router)

# Observability & Security Middleware
app.add_middleware(TracingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-trace-id", "x-correlation-id", "X-Trace-ID", "X-Correlation-ID"],
)


def _validate_security_config():
    """Validate security configuration at startup. Fails fast if misconfigured."""
    settings = get_settings()
    jwt_secret = settings.jwt_secret

    is_hf_space = bool(
        os.getenv("SPACE_ID")
        or os.getenv("SPACE_HOST")
        or os.getenv("HF_SPACE")
        or os.getenv("AUTO_GENERATE_JWT_SECRET", "").lower() in ("true", "1")
    )
    if is_hf_space and not jwt_secret:
        import tempfile
        secret_path = Path(tempfile.gettempdir()) / ".rasosynth_jwt_secret"
        generated_token = None
        if secret_path.exists():
            try:
                cached = secret_path.read_text(encoding="utf-8").strip()
                if len(cached) >= 32:
                    generated_token = cached
            except Exception:
                pass

        if not generated_token:
            new_secret = secrets.token_urlsafe(64)
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                fd = os.open(str(secret_path), flags, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(new_secret)
                generated_token = new_secret
            except FileExistsError:
                try:
                    generated_token = secret_path.read_text(encoding="utf-8").strip()
                except Exception:
                    generated_token = new_secret
            except Exception:
                generated_token = new_secret

        os.environ["JWT_SECRET"] = generated_token
        settings.jwt_secret = generated_token
        jwt_secret = generated_token
        get_settings.cache_clear()

    if not jwt_secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is required. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    if len(jwt_secret) < 32:
        raise RuntimeError(
            f"JWT_SECRET is only {len(jwt_secret)} characters. "
            "Must be at least 32 characters."
        )

    weak_patterns = ["password", "changeme", "demo", "test1234", "000000"]
    if any(p in jwt_secret.lower() for p in weak_patterns):
        logger.warning("JWT_SECRET appears weak or contains common patterns.")


# ── Root Endpoints ────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root(req: Request):
    """Root endpoint. Serves live interactive playground for browser users, or API metadata for JSON clients."""
    accept = req.headers.get("accept", "")
    if "text/html" in accept and not req.query_params.get("format") == "json":
        from api.playground_html import get_playground_html
        return HTMLResponse(content=get_playground_html())

    return {
        "name": "RasoSynthTune",
        "version": "2.0.0",
        "description": "Advanced autonomous dataset generation with constraint-aware intelligence",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "playground": "/playground",
        "features": [
            "Constraint-aware data discovery",
            "Multilingual processing",
            "Low-resource domain handling",
            "Adaptive quality filtering",
            "Self-improving research loop",
            "Streaming export for large datasets",
        ]
    }


@app.get("/playground", tags=["Root"], include_in_schema=False)
@app.get("/ui", tags=["Root"], include_in_schema=False)
async def playground_endpoint():
    """Direct route to interactive RasoSynthTune playground."""
    from api.playground_html import get_playground_html
    return HTMLResponse(content=get_playground_html())



@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def get_favicon():
    """Serve brand SVG favicon."""
    fav_svg = Path("frontend/public/favicon.svg")
    if fav_svg.exists():
        return Response(content=fav_svg.read_bytes(), media_type="image/svg+xml")
    inline_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <circle cx="52" cy="12" r="2.6" fill="#d8d2c4"/>
  <circle cx="22" cy="22" r="2.6" fill="#d8d2c4"/>
  <circle cx="32" cy="22" r="2.6" fill="#d8d2c4"/>
  <circle cx="52" cy="22" r="2.6" fill="#d8d2c4"/>
  <circle cx="52" cy="32" r="2.6" fill="#d8d2c4"/>
  <circle cx="22" cy="42" r="2.6" fill="#d8d2c4"/>
  <circle cx="32" cy="42" r="2.6" fill="#d8d2c4"/>
  <circle cx="52" cy="42" r="2.6" fill="#d8d2c4"/>
  <circle cx="22" cy="52" r="2.6" fill="#d8d2c4"/>
  <circle cx="32" cy="52" r="2.6" fill="#d8d2c4"/>
  <circle cx="42" cy="52" r="2.6" fill="#d8d2c4"/>
  <circle cx="12" cy="12" r="3.6" fill="#1b1b18"/>
  <circle cx="22" cy="12" r="3.6" fill="#1b1b18"/>
  <circle cx="32" cy="12" r="3.6" fill="#1b1b18"/>
  <circle cx="42" cy="12" r="3.6" fill="#1b1b18"/>
  <circle cx="12" cy="22" r="3.6" fill="#1b1b18"/>
  <circle cx="42" cy="22" r="3.6" fill="#1b1b18"/>
  <circle cx="12" cy="32" r="3.6" fill="#1b1b18"/>
  <circle cx="22" cy="32" r="3.6" fill="#1b1b18"/>
  <circle cx="32" cy="32" r="3.6" fill="#1b1b18"/>
  <circle cx="42" cy="32" r="3.6" fill="#1b1b18"/>
  <circle cx="12" cy="42" r="3.6" fill="#1b1b18"/>
  <circle cx="42" cy="42" r="3.6" fill="#1b1b18"/>
  <circle cx="12" cy="52" r="3.6" fill="#1b1b18"/>
  <circle cx="52" cy="52" r="3.6" fill="#f26625"/>
</svg>"""
    return Response(content=inline_svg.encode("utf-8"), media_type="image/svg+xml")


# ── Backwards Compatibility Re-Exports ────────────────────────────────────────
from api.routers.jobs import (
    active_websockets,
    plan_job,
    run_pipeline,
    create_job,
    list_jobs,
    get_job,
    cancel_job,
    delete_job_endpoint,
    get_job_records,
    get_job_dataset_summary,
    get_job_report,
    create_presigned_download_url,
    download_job_dataset,
    _authenticate_websocket,
)
