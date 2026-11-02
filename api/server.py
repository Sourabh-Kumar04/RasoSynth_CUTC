"""FastAPI server with enhanced constraint handling and research capabilities."""
from __future__ import annotations

import asyncio
import json
import uuid
import logging
import os
import secrets
import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Response, Depends, Request, Header, Body, Query
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

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

# Rate limiter for security (distributed Redis-backed with in-memory fallback)
class RateLimiter:
    """Rate limiter supporting distributed Redis-backed coordination and in-memory fallback.

    Ensures rate limits apply uniformly across multi-worker (Uvicorn --workers N) deployments.
    Limits: max N requests per window_seconds per client_key (typically IP).
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60, prefix: str = "general"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.prefix = prefix
        self._buckets: Dict[str, list] = {}

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            k for k, v in self._buckets.items()
            if v and (now - v[-1]) > self.window_seconds
        ]
        for k in expired_keys:
            del self._buckets[k]

    def _check_memory(self, client_key: str) -> bool:
        now = time.time()
        self._cleanup()

        if client_key not in self._buckets:
            self._buckets[client_key] = []

        # Remove timestamps outside the window
        cutoff = now - self.window_seconds
        self._buckets[client_key] = [t for t in self._buckets[client_key] if t > cutoff]

        if len(self._buckets[client_key]) >= self.max_requests:
            return False

        self._buckets[client_key].append(now)
        return True

    async def check_async(self, client_key: str, redis_client=None) -> bool:
        """Asynchronously check rate limit, coordinating across workers via Redis if available."""
        if redis_client is not None:
            try:
                now = time.time()
                bucket_window = int(now // self.window_seconds)
                redis_key = f"ratelimit:{self.prefix}:{client_key}:{bucket_window}"
                count = await redis_client.incr(redis_key)
                if count == 1:
                    await redis_client.expire(redis_key, self.window_seconds + 5)
                if count > self.max_requests:
                    return False
                return True
            except Exception as e:
                logger.debug(f"Redis rate limiter fallback to memory: {e}")
        return self._check_memory(client_key)

    def check(self, client_key: str) -> bool:
        """Synchronous check using in-memory state."""
        return self._check_memory(client_key)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request.

    X-Forwarded-For is trusted ONLY when TRUST_PROXY=true (i.e. the app
    really sits behind a trusted proxy that sets it). By default it is
    ignored, because any client can forge it and login/provider-test
    rate limits keyed on a forged IP are trivially bypassed.
    """
    if os.getenv("TRUST_PROXY", "false").lower() in ("true", "1", "yes"):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Global constants
MAX_SAMPLE_LOAD_LIMIT = int(os.getenv("MAX_SAMPLE_LOAD_LIMIT", "10000"))

# Global rate limiters (multi-worker safe)
_login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60, prefix="login")
_provider_test_rate_limiter = RateLimiter(max_requests=20, window_seconds=60, prefix="provider_test")


# CSRF Protection
class CSRFTokenManager:
    """Manages CSRF tokens for state-changing operations.

    Uses HMAC-signed stateless tokens so they work across multi-worker deployments
    without shared in-memory state.
    """

    def __init__(self):
        self._token_ttl = int(os.getenv("CSRF_TOKEN_TTL_SECONDS", "3600"))  # 1 hour default
        # Use an explicit CSRF_SECRET, or an ephemeral per-process secret.
        # The CSRF secret must NEVER be derived from JWT_SECRET: key reuse
        # across purposes means a CSRF-token forgery path and a JWT path
        # share one secret. Ephemeral tokens do not survive a restart and
        # do not validate across workers; set CSRF_SECRET for multi-worker
        # deployments.
        secret = os.getenv("CSRF_SECRET")
        if not secret:
            import secrets as _secrets
            secret = _secrets.token_hex(32)
            logger.warning(
                "CSRF_SECRET is unset; using an ephemeral CSRF secret "
                "(tokens will not survive a restart or validate across "
                "workers). Set CSRF_SECRET."
            )
        self._secret = secret

    def _sign(self, payload: str) -> str:
        return hmac.new(self._secret.encode(), payload.encode(), "sha256").hexdigest()[:16]

    def generate_token(self, user_id: str) -> str:
        """Generate a stateless CSRF token for a user."""
        timestamp = str(int(time.time()))
        raw = f"{user_id}:{timestamp}"
        sig = self._sign(raw)
        return f"{sig}:{timestamp}:{user_id}"

    def validate_token(self, token: str, user_id: str) -> bool:
        """Validate a CSRF token. Returns True if valid."""
        parts = token.split(":", 2)
        if len(parts) != 3:
            return False

        expected_sig, timestamp, token_user_id = parts

        # Verify user_id matches
        if token_user_id != user_id:
            return False

        # Verify signature
        raw = f"{user_id}:{timestamp}"
        expected = self._sign(raw)
        if not hmac.compare_digest(expected_sig, expected):
            return False

        # Check expiry
        age = time.time() - float(timestamp)
        if age > self._token_ttl:
            return False

        return True


_csrf_manager = CSRFTokenManager()


def _sign_approved_examples(query: str, examples: list[dict]) -> str:
    """Sign server-generated preview examples so jobs cannot inject records."""
    payload = json.dumps(
        {"query": query, "examples": examples},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    # Prefer configured shared secrets so a preview request handled by one API
    # worker can be submitted to another worker in a multi-process deployment.
    from core.config import get_settings
    shared_secret = os.getenv("CSRF_SECRET") or get_settings().jwt_secret or _csrf_manager._secret
    return hmac.new(shared_secret.encode(), payload.encode(), "sha256").hexdigest()


def _get_download_signing_secret() -> str:
    """Resolve dedicated signing secret for download and preview URLs.

    Fails closed when absent: no fallback to JWT_SECRET or CSRF secret.
    """
    from core.config import get_settings
    secret = (
        os.getenv("DOWNLOAD_SIGNING_SECRET")
        or os.getenv("PREVIEW_SIGNING_SECRET")
        or getattr(get_settings(), "download_signing_secret", None)
    )
    if not secret:
        raise RuntimeError(
            "Dedicated download signing secret (DOWNLOAD_SIGNING_SECRET) is not configured; "
            "presigned URL signing fails closed without JWT_SECRET fallback."
        )
    return str(secret).strip()


def _sign_download_token(job_id: str, expires_at: int, user: str = "", format: str = "") -> str:
    """Generate an HMAC-SHA256 signature for presigned dataset downloads.

    Binds user, format, expiry, and single-purpose ("download") in the HMAC.
    Uses dedicated signing secret; fails closed if absent.
    """
    signing_secret = _get_download_signing_secret()
    payload = f"dataset_download:{job_id}:{user}:{format}:{expires_at}"
    return hmac.new(signing_secret.encode("utf-8"), payload.encode("utf-8"), "sha256").hexdigest()


def _verify_download_token(job_id: str, token: Optional[str], expires_at: Optional[int], user: str = "", format: str = "") -> bool:
    """Verify an ephemeral download token against expiration and HMAC signature.

    Fails closed if dedicated signing secret is not configured or token is invalid.
    No fallback to JWT_SECRET.
    """
    if not token or expires_at is None:
        return False
    try:
        expires_int = int(expires_at)
    except (ValueError, TypeError):
        return False

    # Check expiration (with 60-second grace window for clock drift)
    if time.time() > (expires_int + 60):
        return False

    try:
        expected_sig = _sign_download_token(job_id, expires_int, user=user, format=format)
    except Exception:
        # Fail closed on missing signing secret
        return False

    return hmac.compare_digest(expected_sig, str(token).strip())


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware that validates CSRF tokens on state-changing methods (POST, PUT, DELETE).

    Skips CSRF validation for:
    - /auth/* endpoints (login/logout need to be accessible)
    - /health, /metrics, /docs, /openapi.json
    - OPTIONS requests (CORS preflight)
    - WebSocket upgrade requests
    """

    SKIP_PATHS = {"/auth/login", "/auth/logout", "/health", "/health/ready", "/health/live",
                  "/metrics", "/docs", "/redoc", "/openapi.json", "/"}

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for safe methods, auth endpoints, and documentation
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Check if path should be skipped
        path = request.url.path
        if path in self.SKIP_PATHS or path.startswith(("/auth/", "/docs", "/redoc", "/openapi")):
            return await call_next(request)

        # Machine-to-machine API requests with an Authorization: Bearer header are immune to CSRF
        # (a Bearer header value is not ambient like a cookie; a bare X-API-Key header is NOT
        # accepted here because no X-API-Key credential is validated anywhere).
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        # Check for WebSocket upgrade
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Validate CSRF token for state-changing requests
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
active_websockets: dict[str, list[WebSocket]] = {}

# Checkpoint and Failover (moved from global to app state)
checkpoint_manager = None
checkpoint_store = None
failover_engine = None
provider_hot_switcher = None


# Security: Environment-aware CORS configuration
def _get_cors_origins() -> list[str]:
    """Get CORS origins based on environment.

    Production: Strict allowlist from environment variable
    Development: Allows localhost variants

    For non-localhost deployments (private IPs, LAN, etc.), set
    ``CORS_ALLOWED_ORIGINS`` to a comma-separated list of origins — this works
    in any environment, dev or production. The dev fallback below covers only
    loopback origins so we never bake a private IP into source control.
    """
    from core.environment import get_current_environment
    env = get_current_environment()
    cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")

    if cors_origins:
        return [o.strip() for o in cors_origins.split(",") if o.strip()]

    if env in ("production", "gpu_cluster"):
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS must be explicitly set in production. "
            "Set CORS_ALLOWED_ORIGINS environment variable."
        )

    return [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]


# Security: Security headers middleware (OWASP-recommended)
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

    # Paths that need larger body limits (e.g., dataset downloads)
    LARGE_BODY_PATHS = {"/jobs", "/datasets", "/providers"}

    # Default max body size: 10MB
    MAX_BODY_SIZE = int(os.getenv("MAX_REQUEST_BODY_SIZE", "10485760"))

    async def dispatch(self, request: Request, call_next):
        # Read content-length if present
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum size is {self.MAX_BODY_SIZE} bytes."}
            )

        response = await call_next(request)

        # Add security headers
        for header_name, header_value in self.SECURITY_HEADERS.items():
            response.headers[header_name] = header_value

        # Prevent clickjacking
        response.headers["X-Content-Type-Options"] = "nosniff"

        return response


class TracingMiddleware(BaseHTTPMiddleware):
    """Distributed tracing and request context propagation middleware."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Extract or generate correlation and trace IDs
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

        # Propagate to contextvars
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
            if observability is not None:
                try:
                    observability.record_trace(
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
    """FastAPI lifespan: wires the module-global services (router, db, orchestrator, ...).

    Tokens flow in this order — each step is wrapped so one failure doesn't
    poison the rest:

        1. Security config  (fail-fast; missing JWT_SECRET raises here, not at import)
        2. Observability    (structured logging + spans for the rest)
        3. AsyncDB          (uses settings.postgres_url — sqlite fallback supported)
        4. Cache            (Redis; degrades gracefully if unreachable)
        5. WebSocket manager (Redis-backed; degrades gracefully if unreachable)
        6. ProviderRouter   (loads API keys + provider plugins)
        7. ProviderValidator(router-aware config validation)
        8. DatasetOrchestrator(config, router, db, observability, ws_manager)
        9. ResearchLoop + TechniqueIntegrator  (router-driven research)
        10. AutomaticFailoverEngine + ProviderHotSwitcher (runtime failover & hot-switching)

    Checkpoint CRUD uses its persistent store. Provider switching and failover
    are managed via AutomaticFailoverEngine and ProviderHotSwitcher.
    """
    global router, orchestrator, db, cache, observability
    global ws_manager, provider_validator
    global research_loop, technique_integrator, admission_controller
    global checkpoint_store, checkpoint_manager
    global failover_engine, provider_hot_switcher

    settings = get_settings()

    # (1) Security — fail fast on missing/weak JWT_SECRET
    _validate_security_config()

    # Snapshot settings once so every downstream constructor sees the same view
    # (and we don't pay four model_dump() calls).
    config = settings.model_dump()

    logger.info("=" * 72)
    logger.info("RasoSynthTune: starting up")
    logger.info("=" * 72)

    # (2) Observability
    try:
        observability = ObservabilityManager(settings)
        await observability.initialize()
        logger.info("  ✓ ObservabilityManager initialized")
    except Exception as e:
        logger.error(f"  ✗ ObservabilityManager init failed: {e}")
        observability = None

    # (3) Database (AsyncDB backed by SQLAlchemy/asyncpg; falls back to SQLite if Postgres unreachable)
    db = None
    try:
        db = await AsyncDB.create(settings.postgres_url)
        logger.info(f"  ✓ AsyncDB initialized (PostgreSQL: {settings.postgres_url})")
    except Exception as e:
        # If running outside container network, try localhost fallback for docker-exposed postgres
        if "@postgres:" in settings.postgres_url:
            local_pg_url = settings.postgres_url.replace("@postgres:", "@localhost:", 1)
            try:
                db = await AsyncDB.create(local_pg_url)
                logger.info(f"  ✓ AsyncDB initialized (PostgreSQL on host fallback: {local_pg_url})")
            except Exception as e_local:
                logger.warning(f"  ⚠ PostgreSQL connection failed (docker net: {e}, host: {e_local}). Falling back to SQLite...")
        else:
            logger.warning(f"  ⚠ PostgreSQL connection failed ({e}). Falling back to SQLite...")

    if db is None:
        try:
            persistent_base = "/data" if os.path.isdir("/data") and os.access("/data", os.W_OK) else os.getenv("PERSISTENT_STORAGE_PATH", "outputs")
            os.makedirs(persistent_base, exist_ok=True)
            db_path = os.path.abspath(os.path.join(persistent_base, "rasosynthtune.db"))
            sqlite_url = f"sqlite+aiosqlite:///{db_path}"
            db = await AsyncDB.create(sqlite_url)
            logger.info(f"  ✓ AsyncDB initialized with SQLite fallback ({sqlite_url})")
        except Exception as sqle:
            if "already exists" in str(sqle).lower():
                try:
                    from core.db import DatabaseManager
                    db_manager = DatabaseManager(sqlite_url)
                    db = AsyncDB(db_manager)
                    logger.info(f"  ✓ AsyncDB attached to existing SQLite schema ({sqlite_url})")
                except Exception as attach_err:
                    logger.error(f"  ✗ AsyncDB SQLite attach failed: {attach_err}")
                    db = None
            else:
                logger.error(f"  ✗ AsyncDB SQLite fallback failed: {sqle}")
                db = None

    # (3b) Process-local job admission control. API and Celery worker processes
    # each enforce their own configured concurrency limit.
    try:
        from core.admission_control import AdmissionController
        admission_controller = AdmissionController(
            max_concurrent_jobs=settings.max_concurrent_jobs,
            max_queue_size=settings.max_job_queue_size,
            db=db,
            observability=observability,
        )
        await admission_controller.start()
        app.state.admission_controller = admission_controller
        logger.info("  ✓ AdmissionController initialized (max_concurrent=%d)", settings.max_concurrent_jobs)
    except Exception as e:
        admission_controller = None
        app.state.admission_controller = None
        logger.warning("  ⚠ AdmissionController unavailable: %s", e)

    # (4) Redis-backed cache (optional — server works without it)
    try:
        cache = CacheManager(settings.redis_url)
        await cache.connect()
        logger.info("  ✓ Cache (Redis) connected")
    except Exception as e:
        logger.warning(f"  ⚠ Cache disabled (Redis unreachable): {e}")
        cache = None

    multi_level_cache = None
    try:
        from core.cache.layers import MultiLevelCache
        multi_level_cache = MultiLevelCache(
            l1_config={"max_size_mb": 100},
            l2_redis=cache.redis if cache is not None else None,
        )
        app.state.multi_level_cache = multi_level_cache
        logger.info("  ✓ MultiLevelCache (L1 Memory + L2 Redis) initialized")
    except Exception as mlc_err:
        logger.warning(f"  ⚠ MultiLevelCache init skipped: {mlc_err}")

    # (4b) Persistent API checkpoints. CheckpointStore uses PostgreSQL if available,
    # or its built-in memory/Redis fallback mode when running on SQLite.
    checkpoint_manager = None
    checkpoint_store = None
    try:
        from core.orchestrator_pkg.checkpoints import CheckpointManager, CheckpointStore
        checkpoint_store = CheckpointStore(settings.postgres_url, settings.redis_url)
        await checkpoint_store.connect()
        checkpoint_manager = CheckpointManager(checkpoint_store)
        app.state.checkpoint_manager = checkpoint_manager
        app.state.checkpoint_store = checkpoint_store
        logger.info("  ✓ Checkpoint store initialized")
    except Exception as e:
        checkpoint_store = None
        checkpoint_manager = None
        logger.warning("  ⚠ Checkpoint store unavailable: %s", e)

    # (5) WebSocket manager (optional — used by /jobs/{id}/stream). The
    # ``connect()`` method on ConnectionManager is per-connection and takes
    # (websocket, job_id); we just instantiate the manager here.
    try:
        ws_manager = ConnectionManager(redis_url=settings.redis_url)
        logger.info("  ✓ WebSocket manager initialized")
    except Exception as e:
        logger.warning(f"  ⚠ WebSocket manager init failed: {e}")
        ws_manager = None

    # (6) ProviderRouter — loads API keys + plugin registry
    try:
        router = ProviderRouter(config)
        await router.initialize()
        logger.info("  ✓ ProviderRouter initialized")
    except Exception as e:
        logger.error(f"  ✗ ProviderRouter init failed: {e}")
        router = None

    # (7) ProviderValidator — needs config (router optional)
    try:
        provider_validator = ProviderValidator(config)
        logger.info("  ✓ ProviderValidator initialized")
    except Exception as e:
        logger.warning(f"  ⚠ ProviderValidator init failed: {e}")
        provider_validator = None

    # (8) DatasetOrchestrator — requires router + db (config + observability
    # + ws_manager optional). Skip if router or db failed.
    if router is not None or db is not None:
        try:
            orchestrator = DatasetOrchestrator(
                config=config,
                router=router,
                db=db,
                observability=observability,
                ws_manager=ws_manager,
                redis_client=cache.redis if cache is not None else None,
                checkpoint_manager=checkpoint_manager,
            )
            logger.info("  ✓ DatasetOrchestrator initialized")
        except Exception as e:
            logger.error(f"  ✗ DatasetOrchestrator init failed: {e}")
            orchestrator = None
    else:
        logger.warning("  ⚠ DatasetOrchestrator skipped (no router + no db)")
        orchestrator = None

    # (9) ResearchLoop + TechniqueIntegrator (router-driven)
    if router is not None:
        try:
            research_loop = ResearchLoop(router=router, config=config)
            technique_integrator = TechniqueIntegrator(router=router)
            if orchestrator is not None:
                orchestrator.technique_integrator = technique_integrator
            logger.info("  ✓ ResearchLoop + TechniqueIntegrator initialized")
        except Exception as e:
            logger.warning(f"  ⚠ ResearchLoop init failed: {e}")
            research_loop = None
            technique_integrator = None
    else:
        logger.warning("  ⚠ ResearchLoop skipped (no router)")
        research_loop = None
        technique_integrator = None

    # (9.5) AutomaticFailoverEngine & ProviderHotSwitcher
    if router is not None:
        try:
            from providers.failover import AutomaticFailoverEngine, ProviderHotSwitcher
            failover_engine = AutomaticFailoverEngine(
                provider_registry=router,
                checkpoint_manager=checkpoint_manager,
                config=config,
            )
            provider_hot_switcher = ProviderHotSwitcher(
                failover_engine=failover_engine,
                provider_router=router,
            )
            router.set_failover_engine(failover_engine)
            app.state.failover_engine = failover_engine
            app.state.provider_hot_switcher = provider_hot_switcher
            logger.info("  ✓ AutomaticFailoverEngine & ProviderHotSwitcher initialized")
        except Exception as e:
            failover_engine = None
            provider_hot_switcher = None
            logger.warning(f"  ⚠ Failover engine init failed: {e}")
    else:
        failover_engine = None
        provider_hot_switcher = None

    logger.info("=" * 72)
    logger.info(f"Startup complete — orchestrator={'ready' if orchestrator else 'NOT READY'}, "
                f"db={'ready' if db else 'NOT READY'}, "
                f"cache={'ready' if cache else 'disabled'}")
    logger.info("=" * 72)

    # (10) ReviewService — DB-backed human review queue
    review_service = None
    if db is not None:
        try:
            from core.review_service import ReviewService as _ReviewService
            review_service = _ReviewService(db.db)
            await review_service.recover_paused_jobs()
            app.state.review_service = review_service
            # Make the singleton available for the orchestrator's HITL node
            import core as _core_pkg
            _core_pkg._review_service_instance = review_service
            logger.info("  ✓ ReviewService (DB-backed) initialized")
        except Exception as e:
            logger.warning(f"  ⚠ ReviewService init failed: {e}")
    else:
        logger.warning("  ⚠ ReviewService skipped (no db)")

    # Recover interrupted in-process jobs after every service they depend on is
    # ready. Celery deployments keep task delivery in the broker, so this
    # process-level recovery is only safe when the API owns execution.
    app.state.auto_resume_manager = None
    if db is not None and orchestrator is not None and not settings.enable_celery:
        try:
            from core.auto_resume import AutoResumeManager
            auto_resume_manager = AutoResumeManager(
                db,
                orchestrator,
                checkpoint_manager=checkpoint_manager,
                job_runner=run_pipeline,
            )
            app.state.auto_resume_manager = auto_resume_manager
            recovery = await auto_resume_manager.recover_all()
            logger.info(
                "  ✓ Startup recovery checked %d jobs (%d queued)",
                recovery["total"],
                recovery["recovered"],
            )
        except Exception as e:
            logger.warning("  ⚠ Startup recovery unavailable: %s", e)
    elif settings.enable_celery:
        logger.info("  • Startup recovery delegated to Celery task delivery")

    # (11) FinetuneJobManager
    ft_manager = None
    if db is not None:
        try:
            from finetuning.job_manager import FinetuneJobManager as _FTManager
            ft_manager = _FTManager(db.db)
            app.state.ft_manager = ft_manager
            logger.info("  ✓ FinetuneJobManager initialized")
        except Exception as e:
            logger.warning(f"  ⚠ FinetuneJobManager init failed: {e}")
    else:
        logger.warning("  ⚠ FinetuneJobManager skipped (no db)")

    # Also expose core services on app.state for route dependencies
    app.state.db = db
    app.state.router = router
    app.state.orchestrator = orchestrator
    app.state.cache = cache
    app.state.observability = observability

    # (12) ADR-003 Centralized Dependency Injection Container
    app.state.container = None
    try:
        from core.di.container import ServiceContainer
        container = ServiceContainer(settings)
        if db is not None:
            container.register_instance(type(db), db)
        if router is not None:
            container.register_instance(type(router), router)
        if orchestrator is not None:
            container.register_instance(type(orchestrator), orchestrator)
        if checkpoint_manager is not None:
            container.register_instance(type(checkpoint_manager), checkpoint_manager)
        if failover_engine is not None:
            container.register_instance(type(failover_engine), failover_engine)
        if provider_hot_switcher is not None:
            container.register_instance(type(provider_hot_switcher), provider_hot_switcher)
        if review_service is not None:
            container.register_instance(type(review_service), review_service)
        if ft_manager is not None:
            container.register_instance(type(ft_manager), ft_manager)
        if multi_level_cache is not None:
            container.register_instance(type(multi_level_cache), multi_level_cache)
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
            logger.info("  ✓ AgentRegistry (multi-agent society) initialized with builtin agents")
        except Exception as agent_err:
            logger.debug(f"AgentRegistry initialization skipped: {agent_err}")
        app.state.container = container
        logger.info("  ✓ ServiceContainer (ADR-003) initialized and attached to app.state.container")
    except Exception as e:
        logger.warning(f"  ⚠ ServiceContainer initialization skipped: {e}")

    logger.info("=" * 72)
    logger.info(
        f"Startup complete — orchestrator={'ready' if orchestrator else 'NOT READY'}, "
        f"db={'ready' if db else 'NOT READY'}, "
        f"review={'ready' if review_service else 'disabled'}, "
        f"finetune={'ready' if ft_manager else 'disabled'}"
    )
    logger.info("=" * 72)

    yield

    # ---- Shutdown ----
    logger.info("RasoSynthTune: shutting down")

    if getattr(app.state, "container", None) is not None:
        try:
            await app.state.container.shutdown()
            logger.info("  ✓ ServiceContainer shut down")
        except Exception as e:
            logger.warning(f"  ⚠ ServiceContainer shutdown failed: {e}")

    if admission_controller is not None:
        try:
            await admission_controller.stop()
            logger.info("  ✓ AdmissionController stopped")
        except Exception as e:
            logger.warning("  ⚠ AdmissionController stop failed: %s", e)
        admission_controller = None
        app.state.admission_controller = None

    if db is not None:
        try:
            await db.close()
            logger.info("  ✓ AsyncDB closed")
        except Exception as e:
            logger.warning(f"  ⚠ db.close() failed: {e}")

    if checkpoint_store is not None:
        try:
            await checkpoint_store.close()
            logger.info("  ✓ Checkpoint store closed")
        except Exception as e:
            logger.warning("  ⚠ checkpoint store close failed: %s", e)

    if cache is not None:
        try:
            await cache.disconnect()
            logger.info("  ✓ Cache disconnected")
        except Exception as e:
            logger.warning(f"  ⚠ cache.disconnect() failed: {e}")

    # ConnectionManager.disconnect() is per-connection — no global cleanup needed.
    # If the manager ever grows a global disconnect, gate it on the right signature.

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

# Observability & Security: Add custom middleware
app.add_middleware(TracingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)

# Security: Add CORS middleware (added last so it runs outer-most and adds CORS headers to all responses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-trace-id", "x-correlation-id", "X-Trace-ID", "X-Correlation-ID"],
)

# Security: Validate JWT_SECRET at startup (fail-fast production requirements)
from core.config import get_settings

def _validate_security_config():
    """Validate security configuration at startup. Fails fast if misconfigured."""
    settings = get_settings()
    jwt_secret = settings.jwt_secret

    # Hugging Face Space or auto-generation mode:
    # If deployed on Hugging Face Spaces and no custom JWT_SECRET is provided in Space secrets,
    # generate an ephemeral, cryptographically secure token shared across all workers
    # instead of crashing the Space container in an infinite reboot loop.
    is_hf_space = bool(
        os.getenv("SPACE_ID")
        or os.getenv("SPACE_HOST")
        or os.getenv("HF_SPACE")
        or os.getenv("AUTO_GENERATE_JWT_SECRET", "").lower() in ("true", "1")
    )
    if is_hf_space and not jwt_secret:
        import secrets
        from pathlib import Path
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

        # Update CSRF manager secret if not explicitly configured
        # CSRF secret is intentionally NOT overwritten from JWT_SECRET here:
        # the manager keeps its explicit CSRF_SECRET or ephemeral secret.

        logger.warning(
            "SECURITY NOTICE [HuggingFace Spaces]: No custom JWT_SECRET was configured in Space Secrets. "
            "An ephemeral cryptographically secure secret (64-byte urlsafe) has been automatically generated for this container instance. "
            "All uvicorn worker processes will share this secret via /tmp/.rasosynth_jwt_secret. "
            "To persist authentication sessions across Space restarts, configure JWT_SECRET in Space Secrets."
        )

    if not jwt_secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is required. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    if len(jwt_secret) < 32:
        raise RuntimeError(
            f"JWT_SECRET is only {len(jwt_secret)} characters. "
            "Must be at least 32 characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

    # Warn if using default/weak secret
    weak_patterns = ["password", "changeme", "demo", "test1234", "000000"]
    if any(p in jwt_secret.lower() for p in weak_patterns):
        logger.warning("JWT_SECRET appears weak or contains common patterns. Use a cryptographically random secret.")

# _validate_security_config() is invoked at the top of lifespan(), below.
# Note: Settings() itself now requires JWT_SECRET (no default), so importing
# this module also requires JWT_SECRET to be set; the lifespan check remains
# the fail-fast gate for short/weak values.
# Note: Agent, Delivery, Checkpoint, Failover, Tools, Provider, and Research
# endpoints are registered via api.routers sub-routers.


@app.post("/adaptability", response_model=AdaptabilityResponse, tags=["Adaptability"])
async def analyze_adaptability(request: AdaptabilityRequest,
    current_user: User = Depends(get_current_user)):
    """Analyze dataset feasibility under given constraints."""
    from core.orchestrator_core import ConstraintAnalyzer

    analyzer = ConstraintAnalyzer(settings.model_dump())
    analysis = await analyzer.analyze(request.constraints)

    return AdaptabilityResponse(
        recommended_strategies=analysis.fallback_strategies,
        estimated_feasibility=analysis.feasibility_score,
        warnings=analysis.warnings,
        fallback_options=analysis.fallback_strategies
    )



async def _authenticate_websocket(websocket: WebSocket):
    """Verify a WebSocket caller before accept.

    Browsers cannot set an Authorization header on a WebSocket handshake, so a
    JWT is accepted either as an Authorization Bearer header or as the
    ``?token=`` query parameter. Returns the authenticated User, or None after
    closing the socket with 4401 when the token is missing/invalid.
    Job ownership cannot be enforced per-user yet: jobs carry no owner column;
    callers must at least be authenticated and the job must exist.
    """
    token = None
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return None
    try:
        auth_mgr = get_auth_manager()
        token_data = auth_mgr.verify_token(token)
        user = auth_mgr.get_user(token_data.username)
    except Exception:
        await websocket.close(code=4401)
        return None
    if not user:
        await websocket.close(code=4401)
        return None
    return user


@app.websocket("/jobs/{job_id}/stream")
@app.websocket("/ws/jobs/{job_id}")
async def job_stream(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress streaming."""
    if await _authenticate_websocket(websocket) is None:
        return
    if db is not None:
        try:
            existing = await db.get_job_status(job_id)
        except Exception:
            existing = None
        if not existing and not (orchestrator and job_id in getattr(orchestrator, "active_jobs", {})):
            await websocket.close(code=4404)
            return
    await websocket.accept()

    if job_id not in active_websockets:
        active_websockets[job_id] = []
    active_websockets[job_id].append(websocket)

    try:
        while True:
            if db:
                job = await db.get_job_status(job_id)
                if job:
                    # Add constraint analysis if available
                    if job_id in (orchestrator.active_jobs if orchestrator else {}):
                        job_obj = orchestrator.active_jobs[job_id]
                        if job_obj.constraint_analysis:
                            job["constraint_analysis"] = {
                                "feasibility_score": job_obj.constraint_analysis.feasibility_score,
                                "warnings": job_obj.constraint_analysis.warnings,
                            }

                    await websocket.send_json(job)

                    if job.get("status") in ["completed", "failed", "cancelled"]:
                        break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        if job_id in active_websockets:
            try:
                active_websockets[job_id].remove(websocket)
                if not active_websockets[job_id]:
                    del active_websockets[job_id]
            except Exception:
                pass


@app.websocket("/ws/jobs")
async def jobs_list_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time jobs list streaming."""
    if await _authenticate_websocket(websocket) is None:
        return
    await websocket.accept()
    list_key = "__jobs_list__"
    if list_key not in active_websockets:
        active_websockets[list_key] = []
    active_websockets[list_key].append(websocket)

    try:
        while True:
            if db:
                try:
                    jobs = await db.list_jobs(limit=25)
                    await websocket.send_json({"jobs": jobs})
                except Exception:
                    pass
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        if list_key in active_websockets:
            try:
                active_websockets[list_key].remove(websocket)
                if not active_websockets[list_key]:
                    del active_websockets[list_key]
            except Exception:
                pass


# Note: Metrics, Observability, and Health endpoints are registered via
# api.routers.observability and api.routers.health sub-routers.


@app.get("/settings/compute", tags=["Settings"])
async def get_compute_settings(current_user: User = Depends(get_current_user)):
    """Return cloud GPU provider configuration status (without exposing raw secrets).

    Credential fragments (first/last 4 chars) are admin-only: any
    authenticated user gets only the boolean configured flags, never
    fragments an attacker could use to confirm or brute-force a secret.
    """
    cfg = get_settings()
    m_id = os.getenv("MODAL_TOKEN_ID") or cfg.modal_token_id
    m_sec = os.getenv("MODAL_TOKEN_SECRET") or cfg.modal_token_secret
    r_key = os.getenv("RUNPOD_API_KEY") or cfg.runpod_api_key
    h_tok = os.getenv("HF_TOKEN") or cfg.hf_token

    result: dict = {
        "modal_configured": bool(m_id and m_sec),
        "runpod_configured": bool(r_key),
        "hf_configured": bool(h_tok),
        "available_targets": ["local", "modal", "runpod", "serverless"],
    }
    if current_user.role == UserRole.ADMIN:
        result.update({
            "modal_token_id_masked": f"{m_id[:4]}...{m_id[-4:]}" if m_id and len(m_id) > 8 else ("configured" if m_id else None),
            "runpod_key_masked": f"{r_key[:4]}...{r_key[-4:]}" if r_key and len(r_key) > 8 else ("configured" if r_key else None),
            "hf_token_masked": f"{h_tok[:4]}...{h_tok[-4:]}" if h_tok and len(h_tok) > 8 else ("configured" if h_tok else None),
        })
    return result


class UpdateComputeSettingsRequest(BaseModel):
    modal_token_id: Optional[str] = None
    modal_token_secret: Optional[str] = None
    runpod_api_key: Optional[str] = None
    hf_token: Optional[str] = None


@app.post("/settings/compute", tags=["Settings"])
async def update_compute_settings(payload: UpdateComputeSettingsRequest,
    admin_user: User = Depends(require_role([UserRole.ADMIN]))):
    """Update runtime cloud compute and HuggingFace tokens."""
    cfg = get_settings()
    if payload.modal_token_id:
        os.environ["MODAL_TOKEN_ID"] = payload.modal_token_id
        cfg.modal_token_id = payload.modal_token_id
    if payload.modal_token_secret:
        os.environ["MODAL_TOKEN_SECRET"] = payload.modal_token_secret
        cfg.modal_token_secret = payload.modal_token_secret
    if payload.runpod_api_key:
        os.environ["RUNPOD_API_KEY"] = payload.runpod_api_key
        cfg.runpod_api_key = payload.runpod_api_key
    if payload.hf_token:
        os.environ["HF_TOKEN"] = payload.hf_token
        cfg.hf_token = payload.hf_token
    return {
        "status": "success",
        "message": "Compute settings successfully updated in runtime memory.",
        "modal_configured": bool(os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET")),
        "runpod_configured": bool(os.getenv("RUNPOD_API_KEY")),
        "hf_configured": bool(os.getenv("HF_TOKEN")),
    }


@app.post("/validate", tags=["Validation"])
@app.post("/validate/dataset", tags=["Validation"])
async def validate_dataset_request(payload: dict = Body(default_factory=dict),
    current_user: User = Depends(get_current_user)):
    """Validate dataset generation request configuration prior to pipeline execution."""
    errors = []
    warnings = []

    query = payload.get("query") or (payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}).get("query")
    if not query or not str(query).strip():
        errors.append("Dataset query prompt is required and cannot be empty.")
    elif len(str(query).strip()) < 3:
        errors.append("Query prompt must be at least 3 characters long.")
    elif len(str(query).strip()) > 5000:
        errors.append("Query prompt exceeds 5000 character maximum limit.")

    samples = payload.get("target_samples") or (payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}).get("target_samples")
    if samples is not None:
        try:
            samples_num = int(samples)
            if samples_num <= 0:
                errors.append("target_samples must be a positive integer.")
            elif samples_num > 50000:
                warnings.append("Generating >50,000 samples may require distributed Ray/Celery worker pools.")
        except (ValueError, TypeError):
            errors.append("target_samples must be a valid integer.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# =============================================================================
# Authentication Endpoints
# =============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


@app.post("/auth/login", tags=["Authentication"])
async def login(request: LoginRequest, fastapi_request: Request):
    """Authenticate user and return JWT token.

    Production requirements:
    - Users must be configured via ADMIN_USER and USER_USER env vars
    - AUTH_DISABLED must be false for production
    - No demo/fallback authentication
    - Rate limited: 5 attempts per minute per IP
    """
    auth = get_auth_manager()

    # Rate limiting on login (distributed Redis-backed with in-memory fallback)
    client_ip = get_client_ip(fastapi_request)
    redis_client = getattr(cache, "redis", None) if cache is not None else None
    if not await _login_rate_limiter.check_async(client_ip, redis_client=redis_client):
        logger.warning(f"Rate limit exceeded for login from IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please wait before trying again."
        )

    if auth.auth_disabled:
        # In production, this should never happen with proper configuration
        # But if it does, require proper user configuration
        if not auth._users:
            raise HTTPException(
                status_code=503,
                detail="Authentication not configured. Please set ADMIN_USER and USER_USER environment variables."
            )
        # If users exist but auth is disabled, still require credentials for audit
        user_data = auth.authenticate(request.username, request.password)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        # Normal authentication
        user_data = auth.authenticate(request.username, request.password)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth.create_token(user_data["user_id"], user_data["username"], UserRole(user_data["role"]))

    return LoginResponse(
        access_token=token,
        expires_in=auth.expiration_hours * 3600,
        user={
            "user_id": user_data["user_id"],
            "username": user_data["username"],
            "role": user_data["role"]
        }
    )


@app.post("/auth/logout", tags=["Authentication"])
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    """Logout: revoke the presented token server-side.

    Revocation is in-memory for this process (see api/auth.py); tokens
    also expire automatically after the configured JWT lifetime, which
    is the fallback revocation story if a process restarts. Clients
    must still discard the token.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        get_auth_manager().revoke_token(auth_header[7:])
    return {
        "message": "Logged out successfully",
        "revocation": "token_revoked",
        "note": "Revocation is in-memory for this process; tokens also expire automatically.",
    }


@app.get("/auth/me", tags=["Authentication"])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role.value,
        "email": current_user.email
    }


@app.get("/auth/csrf-token", tags=["Authentication"])
async def get_csrf_token(current_user: User = Depends(get_current_user)):
    """Issue a stateless CSRF token bound to the authenticated user.

    Unauthenticated requests are rejected (401): tokens are never
    issued for the ``anonymous`` identity, because the CSRF middleware
    would otherwise accept an attacker-minted anonymous token on
    state-changing requests. Pair with the ``X-CSRF-Token`` header.
    """
    token = _csrf_manager.generate_token(current_user.user_id)
    return {
        "csrf_token": token,
        "user_id": current_user.user_id,
        "header_name": "X-CSRF-Token",
    }


# =============================================================================
# Jobs API Endpoints
# =============================================================================

class SourcePreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    optimize_query: bool = True
    override_query: Optional[str] = None
    query_plan: Optional[dict] = None
    language: str = "en"
    region_restrictions: list[str] = Field(default_factory=list)
    max_sources: int = 8

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Describe the dataset you want")
        return value


class ExampleBatchPreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    sources: list[dict] = Field(min_length=1, max_length=5)
    carry_forward_examples: list[dict] = Field(default_factory=list, max_length=3)
    carry_forward_indices: Optional[list[int]] = Field(default=None, max_length=3)
    carry_forward_token: Optional[str] = None
    query_plan: Optional[dict] = None
    dataset_type: str = "sft"
    language: str = "en"
    max_examples: int = Field(default=3, ge=1, le=3)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Describe the dataset you want")
        return value


@app.post("/jobs/preview", tags=["Jobs"])
async def preview_job_sources(request: SourcePreviewRequest,
    current_user: User = Depends(get_current_user)):
    """Build an improved search plan and fetch a small source-only preview."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Discovery pipeline is not available")
    from core.intent_extractor import extract_intent
    from pipeline.discovery import DiscoveryPipeline

    intent = None
    if request.query_plan:
        try:
            intent = UserIntent(
                primary_task=request.query_plan.get("primary_task", "custom dataset generation"),
                domain=request.query_plan.get("domain") or request.query.strip(),
                modality=request.query_plan.get("modality", "text"),
                anti_domains=request.query_plan.get("anti_domains", []),
                key_entities=request.query_plan.get("key_entities", []),
                specialized_queries=request.query_plan.get("specialized_queries", []),
                constraints=request.query_plan.get("constraints", []),
                output_format=request.query_plan.get("output_format", "jsonl"),
                confidence=float(request.query_plan.get("confidence", 0.5)),
                raw_input=request.query,
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Ignoring invalid saved query plan: %s", exc)
    if intent is None and request.optimize_query and orchestrator.router:
        try:
            intent = await extract_intent(
                request.query,
                orchestrator.router,
                redis_client=cache.redis if cache is not None else None,
            )
        except Exception as exc:
            logger.warning("Query planning failed; previewing the original request: %s", exc)

    specialized = list(getattr(intent, "specialized_queries", []) or [])
    improved_query = (request.override_query or "").strip() or (specialized[0] if specialized else request.query.strip())
    if request.override_query and request.override_query.strip():
        planned_queries = [improved_query] + [query for query in specialized if query != improved_query][:9]
    else:
        planned_queries = specialized[:10] or [improved_query]
    preview_queries = planned_queries[:2]
    query_plan = ({
        "primary_task": intent.primary_task,
        "domain": intent.domain,
        "modality": intent.modality,
        "anti_domains": intent.anti_domains,
        "key_entities": intent.key_entities,
        "specialized_queries": planned_queries,
        "constraints": intent.constraints,
        "output_format": intent.output_format,
        "confidence": intent.confidence,
    } if intent else {
        "primary_task": "custom dataset generation",
        "domain": request.query.strip(),
        "modality": "text",
        "anti_domains": [],
        "key_entities": [],
        "specialized_queries": planned_queries,
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.5,
    })
    config = {
        "target_domain": getattr(intent, "domain", "") or improved_query,
        "language": request.language,
        "region_restrictions": request.region_restrictions,
        "aikosh_api_key": get_settings().aikosh_api_key,
        "max_results": max(1, min(request.max_sources, 20)),
        "health_check_enabled": False,
        "quality_min_score": 0.0,
    }
    source_config = {**config, "target_domain": request.query}
    source_types = orchestrator._determine_source_types(source_config)[:8]
    from pipeline.discovery import SourceType
    for st in (SourceType.WIKIPEDIA, SourceType.BOOKS, SourceType.BLOG):
        if st not in source_types:
            source_types.append(st)
    discovery = DiscoveryPipeline(config, router=orchestrator.router)
    sources = []
    seen = set()
    for query in preview_queries:
        async for source in discovery.discover(
            query, config["target_domain"], source_types,
            preview=True, query_is_optimized=True,
        ):
            if source.url in seen:
                continue
            if orchestrator and hasattr(orchestrator, "_is_source_relevant") and not orchestrator._is_source_relevant(source, intent):
                continue
            seen.add(source.url)
            metadata = source.metadata or {}
            reported_license = source.license or metadata.get("license") or metadata.get("license_title")
            reported_language = getattr(source, "language", None) or metadata.get("language") or metadata.get("languages")
            if isinstance(reported_license, dict):
                reported_license = reported_license.get("name") or reported_license.get("id") or reported_license.get("spdx_id")
            if isinstance(reported_language, dict):
                reported_language = reported_language.get("name") or reported_language.get("code")
            if isinstance(reported_language, list):
                reported_language = [str(value) for value in reported_language if value]
            elif reported_language is not None:
                reported_language = str(reported_language)
            sources.append({
                "url": source.url,
                "title": source.title,
                "description": source.description,
                "source_type": source.source_type.value,
                "quality_score": source.quality_score,
                "license": str(reported_license) if reported_license else None,
                "license_status": metadata.get("license_status") or ("verify_access_and_terms" if metadata.get("catalogue_only") else ("reported" if reported_license else "not_provided")),
                "language": reported_language,
                "metadata": metadata,
            })
            if len(sources) >= max(1, min(request.max_sources, 20)):
                break
        if len(sources) >= max(1, min(request.max_sources, 20)):
            break
    return {
        "original_query": request.query,
        "improved_query": improved_query,
        "specialized_queries": planned_queries,
        "preview_queries": preview_queries,
        "query_plan": query_plan,
        "sources": sources,
        "source_count": len(sources),
        "preview_only": True,
        "notice": "AIKosh files are discovered from the permitted API scope. Review each dataset's access and reuse terms before using its content.",
    }


@app.post("/jobs/preview/batch", tags=["Jobs"])
async def preview_job_example_batch(request: ExampleBatchPreviewRequest,
    current_user: User = Depends(get_current_user)):
    """Extract, filter, and generate a tiny grounded example batch for approval."""
    if not orchestrator or not orchestrator.router:
        raise HTTPException(status_code=503, detail="A configured AI provider is required to generate example records")

    if request.carry_forward_examples:
        expected_token = _sign_approved_examples(request.query, request.carry_forward_examples)
        if not request.carry_forward_token or not hmac.compare_digest(request.carry_forward_token, expected_token):
            raise HTTPException(status_code=400, detail="Previously reviewed examples are invalid. Generate a fresh preview batch.")
        indices = request.carry_forward_indices
        if indices is None:
            indices = list(range(len(request.carry_forward_examples)))
        if not indices or len(set(indices)) != len(indices) or any(index < 0 or index >= len(request.carry_forward_examples) for index in indices):
            raise HTTPException(status_code=400, detail="Select valid examples to keep before requesting replacements.")
    elif request.carry_forward_indices is not None or request.carry_forward_token:
        raise HTTPException(status_code=400, detail="Carry-forward approval data is incomplete.")
    else:
        indices = []

    from types import SimpleNamespace
    from core.intent import UserIntent
    from pipeline.construction import ConstructionPipeline, DatasetType
    from pipeline.extraction import ExtractionPipeline, _is_safe_url
    from pipeline.filtering import FilteringPipeline
    from pipeline.discovery import SourceType

    plan = request.query_plan or {}
    intent = UserIntent(
        primary_task=plan.get("primary_task", "custom dataset generation"),
        domain=plan.get("domain") or request.query.strip(),
        modality=plan.get("modality", "text"),
        anti_domains=plan.get("anti_domains", []),
        key_entities=plan.get("key_entities", []),
        specialized_queries=plan.get("specialized_queries", [request.query.strip()]),
        constraints=plan.get("constraints", []),
        output_format=plan.get("output_format", "jsonl"),
        confidence=float(plan.get("confidence", 0.5)),
        raw_input=request.query,
    )
    config = {
        "target_domain": intent.domain,
        "dataset_type": request.dataset_type,
        "language": request.language,
        "quality_level": "high",
        "quality_threshold": 0.55,
        "timeout": 20,
        "min_length": 80,
        "max_length": 20000,
        "synthetic_ratio": 0.0,
        "aikosh_api_key": orchestrator.config.get("aikosh_api_key") or get_settings().aikosh_api_key,
    }
    try:
        dataset_type = DatasetType(request.dataset_type)
    except ValueError:
        dataset_type = DatasetType.SFT

    extractor = ExtractionPipeline(config, router=orchestrator.router)
    filtering = FilteringPipeline(orchestrator.router, config)
    construction = ConstructionPipeline(orchestrator.router, config)
    examples = [request.carry_forward_examples[index] for index in indices]
    existing_example_keys = {
        (" ".join(str(example.get("instruction", "")).casefold().split()),
         " ".join(str(example.get("response", "")).casefold().split()))
        for example in request.carry_forward_examples
    }
    warnings = []
    sources_processed = 0

    for source_data in request.sources:
        metadata = source_data.get("metadata") or {}
        if metadata.get("catalogue_only"):
            warnings.append("Skipped an AIKosh catalogue page; choose a dataset download you can access and whose license you have verified.")
            continue
        url = str(source_data.get("url", ""))
        is_safe, reason = _is_safe_url(url)
        if not is_safe:
            warnings.append(f"Skipped unsafe source URL: {reason}")
            continue
        try:
            source_type = SourceType(source_data.get("source_type", SourceType.WEB_PAGE.value))
        except ValueError:
            source_type = SourceType.WEB_PAGE
        source = SimpleNamespace(
            url=url,
            source_type=source_type,
            title=source_data.get("title", ""),
            description=source_data.get("description", ""),
            license=source_data.get("license"),
            metadata=metadata,
            metadata__=metadata,
        )

        try:
            extracted = None
            async with asyncio.timeout(120):
                async for content in extractor.extract(source):
                    if content.content and content.content_type != "error":
                        extracted = content
                        break
            if extracted is None:
                warnings.append(f"Could not extract usable text from {source.title or url}")
                continue
            sources_processed += 1

            provenance = {
                "source_url": url,
                "source_type": source_type.value,
                "source_title": source.title,
                "license": source.license,
                "language": extracted.language or request.language,
            }
            extracted.metadata = {**(extracted.metadata or {}), **{k: v for k, v in provenance.items() if v}}
            filtered = await asyncio.wait_for(filtering.filter(extracted, intent), timeout=60)
            if not filtered:
                warnings.append(f"Source text did not pass quality checks: {source.title or url}")
                continue

            filtered.metadata = {**(filtered.metadata or {}), **{k: v for k, v in provenance.items() if v}}
            previous_count = len(examples)
            async with asyncio.timeout(120):
                async for constructed in construction.construct(filtered, intent, dataset_type=dataset_type):
                    example_key = (
                        " ".join(str(constructed.instruction or "").casefold().split()),
                        " ".join(str(constructed.response or "").casefold().split()),
                    )
                    if example_key in existing_example_keys:
                        continue
                    existing_example_keys.add(example_key)
                    examples.append({
                        "instruction": constructed.instruction,
                        "response": constructed.response,
                        "input": constructed.input,
                        "source_text": filtered.content[:2000],
                        "quality_score": filtered.quality_score,
                        "difficulty_tier": constructed.difficulty_tier,
                        "source_url": url,
                        "source_title": source.title,
                        "source_type": source_type.value,
                        "metadata": {**(constructed.metadata or {}), **provenance},
                    })
                    if len(examples) >= request.max_examples:
                        break
            if len(examples) == previous_count:
                warnings.append(f"No valid examples were returned for {source.title or url}")
        except Exception as exc:
            logger.warning("Example batch preview failed for %s: %s", url, exc)
            warnings.append(f"Could not build examples from {source.title or url}: {exc}")
        if len(examples) >= request.max_examples:
            break

    final_examples = examples[:request.max_examples]
    return {
        "examples": final_examples,
        "example_count": len(final_examples),
        "approved_examples_token": _sign_approved_examples(request.query, final_examples),
        "sources_processed": sources_processed,
        "warnings": warnings,
        "preview_only": True,
    }

@app.post("/jobs/estimate", tags=["Jobs"])
async def estimate_job(request: JobRequest,
    current_user: User = Depends(get_current_user)):
    """Estimate feasibility and flag a planning-budget mismatch before a job starts."""
    from core.orchestrator_core import ConstraintAnalyzer

    analysis = await ConstraintAnalyzer(settings.model_dump()).analyze(request.model_dump())
    return {
        "estimated_sources": analysis.estimated_sources,
        "estimated_samples": analysis.estimated_samples,
        "estimated_cost_usd": analysis.estimated_cost,
        "planning_budget_usd": request.cost_budget_usd,
        "within_budget": analysis.estimated_cost <= request.cost_budget_usd,
        "warnings": analysis.warnings,
        "suggested_adjustments": analysis.fallback_strategies,
    }


@app.post("/jobs/plan", tags=["Jobs"])
async def plan_job(request: JobRequest,
    current_user: User = Depends(get_current_user)):
    """Generate an execution plan with resource allocation, step costs, and workflow optimization."""
    try:
        from api.planning.planner import WorkflowPlanner
        from api.schemas.dataset import DatasetConfig
        from pipeline.planner import DatasetPlanner, CoveragePlanner

        domain_val = getattr(request, "target_domain", None) or getattr(request, "domain", "general")
        size_val = int(getattr(request, "dataset_size", None) or getattr(request, "target_size", 20))
        output_fmt = getattr(request, "output_format", getattr(request, "export_format", "jsonl"))
        config = DatasetConfig(
            name=request.dataset_name or domain_val or "dataset",
            domain=domain_val,
            synthesis_mode=getattr(request, "synthesis_mode", "standard"),
            language=request.language,
            output_format=output_fmt,
        )
        planner = WorkflowPlanner()
        plan = await planner.create_plan(config)

        # Generate topic and diversity coverage matrix for UI visualization
        cov_matrix_dict = {}
        try:
            dp = DatasetPlanner(orchestrator.router if orchestrator else None, config.model_dump())
            dplan = await dp.create_plan(domain_val or "general")
            cov_planner = CoveragePlanner(config.model_dump())
            cov_matrix = cov_planner.generate_matrix(dplan, target_size=min(size_val, 50))
            cov_matrix_dict = {
                "dimensions": cov_matrix.dimensions,
                "cells": cov_matrix.cells[:30],
                "total_cells": len(cov_matrix.cells),
            }
        except Exception as cov_err:
            logger.debug("CoveragePlanner skipped in /jobs/plan: %s", cov_err)

        return {
            "plan_id": plan.plan_id,
            "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
            "estimated_cost": plan.total_estimated_cost_usd,
            "estimated_duration_seconds": plan.total_estimated_duration_seconds,
            "is_estimate": True,
            "template_estimate": True,
            "efficiency_score": plan.efficiency_score,
            "confidence_score": 0.85,
            "confidence_score_is_estimate": True,
            "orchestration_mode": plan.orchestration_mode,
            "execution_strategy": plan.execution_strategy,
            "steps": [step.model_dump() for step in plan.steps],
            "total_gpu_hours": plan.total_gpu_hours,
            "coverage_matrix": cov_matrix_dict,
        }
    except Exception as exc:
        logger.error(f"Planning failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate workflow plan")


def _enforce_owner(resource: Optional[dict], current_user: User, resource_name: str = "Resource"):
    """Enforce owner check: Admin can access any row; non-admin can only access own rows.
    
    Rows with owner=None (legacy single-tenant rows) are visible only to ADMIN.
    Returns 404 (Not Found) on mismatch to prevent existence leakage.
    """
    if not resource:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")
    if current_user.role == UserRole.ADMIN:
        return
    owner = resource.get("owner")
    if not owner or owner != current_user.username:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")


from collections import OrderedDict
_idempotency_cache: OrderedDict[str, dict] = OrderedDict()
_IDEMPOTENCY_CACHE_MAX_SIZE = 1000
_IDEMPOTENCY_TTL_SECONDS = 300.0  # 5 minutes TTL for explicit keys; 30s for fingerprint keys

def _get_idempotent_entry(key: str) -> Optional[dict]:
    now_ts = time.time()
    entry = _idempotency_cache.get(key)
    if not entry:
        return None
    # Expire entries exceeding their TTL
    ttl = entry.get("ttl", _IDEMPOTENCY_TTL_SECONDS)
    if now_ts - entry.get("timestamp", 0) > ttl:
        _idempotency_cache.pop(key, None)
        return None
    # Move to end (LRU hit)
    _idempotency_cache.move_to_end(key)
    return entry

def _set_idempotent_entry(key: str, response_data: dict, ttl: float = _IDEMPOTENCY_TTL_SECONDS) -> None:
    now_ts = time.time()
    _idempotency_cache[key] = {
        "timestamp": now_ts,
        "ttl": ttl,
        "response": response_data,
    }
    _idempotency_cache.move_to_end(key)
    while len(_idempotency_cache) > _IDEMPOTENCY_CACHE_MAX_SIZE:
        _idempotency_cache.popitem(last=False)


@app.post("/jobs", response_model=JobResponse, status_code=201, tags=["Jobs"])
async def create_job(
    request: JobRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    """Create a new dataset generation job and kick off the pipeline.

    Supports idempotent dispatches via 'Idempotency-Key' header or configuration fingerprint.
    The job is persisted immediately with status ``pending`` so ``GET /jobs``
    and ``GET /jobs/{id}`` return a record before the pipeline even starts.
    The actual pipeline runs as a background task via ``run_pipeline``.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Idempotency check: per-user, bounded, TTL-expired cache
    user_prefix = current_user.username or "anonymous"
    raw_cfg_key = f"{request.target_domain}:{request.dataset_size}:{getattr(request, 'language', 'en')}:{getattr(request, 'raw_input', '')[:100]}"
    fingerprint = hashlib.sha256(raw_cfg_key.encode("utf-8")).hexdigest()
    dedup_key = f"{user_prefix}:{idempotency_key}" if idempotency_key else f"{user_prefix}:{fingerprint}"
    is_explicit_key = bool(idempotency_key)

    cached = _get_idempotent_entry(dedup_key)
    if cached:
        logger.info("Idempotent create_job hit for key %s -> returning existing job %s", dedup_key, cached["response"]["id"])
        return JobResponse(**cached["response"])

    if request.approved_examples:
        expected_token = _sign_approved_examples(request.target_domain, request.approved_examples)
        if not request.approved_examples_token or not hmac.compare_digest(request.approved_examples_token, expected_token):
            raise HTTPException(status_code=400, detail="Example batch is invalid or no longer matches this query. Preview the examples again.")
        if request.approved_example_indices is not None:
            indices = request.approved_example_indices
            if not indices or len(set(indices)) != len(indices) or any(index < 0 or index >= len(request.approved_examples) for index in indices):
                raise HTTPException(status_code=400, detail="Select at least one valid example from the reviewed preview batch.")

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    config = request.model_dump()
    if request.approved_examples and request.approved_example_indices is not None:
        config["approved_examples"] = [request.approved_examples[index] for index in request.approved_example_indices]
    config["id"] = job_id
    config["owner"] = current_user.username

    try:
        await db.create_job(config)
    except Exception as e:
        logger.error(f"Failed to persist new job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create job")

    queued = False
    if get_settings().enable_celery:
        try:
            from workers.celery_app import run_pipeline_task
            run_pipeline_task.apply_async(
                args=[job_id, config],
                retry=False,
            )
            queued = True
            logger.info("Queued dataset job %s with Celery", job_id)
        except Exception as dispatch_error:
            logger.warning(
                "Celery dispatch failed for job %s; using in-process fallback: %s",
                job_id,
                dispatch_error,
            )

    if not queued:
        background_tasks.add_task(run_pipeline, job_id, request)

    resp = JobResponse(
        id=job_id,
        status=JobStatusEnum.PENDING,
        created_at=now,
        progress=0.0,
        cost_usd=0.0,
        samples_generated=0,
        current_stage="initializing",
    )
    _set_idempotent_entry(
        dedup_key,
        resp.model_dump(),
        ttl=300.0 if is_explicit_key else 30.0,
    )
    return resp


@app.get("/jobs", tags=["Jobs"])
async def list_jobs(
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user)):
    """List dataset generation jobs (most recent first)."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    try:
        jobs = await db.list_jobs(status=status, limit=limit + 1, cursor=cursor, owner=owner_filter)
    except Exception as e:
        if "no such table" in str(e).lower() or "relation" in str(e).lower():
            logger.info("Database table missing — auto-creating tables...")
            try:
                await db.create_tables()
                jobs = await db.list_jobs(status=status, limit=limit + 1, owner=owner_filter)
            except Exception as retry_err:
                logger.error(f"Failed to list jobs after table creation: {retry_err}")
                raise HTTPException(status_code=500, detail="Failed to list jobs after table creation")
        else:
            logger.error(f"Failed to list jobs: {e}")
            raise HTTPException(status_code=500, detail="Database query error while listing jobs")

    has_more = len(jobs) > limit
    page = jobs[:limit]
    next_cursor = page[-1]["id"] if has_more and page else None

    return {
        "data": page,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


@app.get("/jobs/{job_id}", response_model=JobDetailResponse, tags=["Jobs"])
async def get_job(job_id: str,
    current_user: User = Depends(get_current_user)):
    """Get a single job's full detail (config + progression counters)."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    # Resolve quality score and simulated flag
    job_cfg = job.get("config") or {}
    job_meta = job.get("metadata") or {}
    quality_score = job.get("quality_score")
    if quality_score is None:
        quality_score = job_meta.get("quality_score") or (job_meta.get("quality_breakdown") or {}).get("composite")
    is_simulated = bool(job_cfg.get("is_simulated") or job.get("is_simulated") or job.get("execution_mode") == "simulated")

    raw_created = job.get("created_at")
    parsed_created = None
    if isinstance(raw_created, str):
        try:
            parsed_created = datetime.fromisoformat(raw_created)
        except (ValueError, TypeError):
            parsed_created = None
    elif isinstance(raw_created, datetime):
        parsed_created = raw_created

    return JobDetailResponse(
        id=job["id"],
        status=job["status"],
        created_at=parsed_created,
        progress=job.get("progress", 0.0),
        cost_usd=job.get("cost_usd", 0.0),
        samples_generated=job.get("samples_generated", 0),
        current_stage=job.get("current_stage"),
        config=job_cfg,
        error=job.get("error"),
        sources_discovered=job.get("sources_discovered", 0),
        sources_extracted=job.get("sources_extracted", 0),
        samples_filtered=job.get("samples_filtered", 0),
        quality_score=quality_score,
        metadata=job_meta,
        is_simulated=is_simulated,
        execution_mode="simulated" if is_simulated else "live",
    )


@app.post("/jobs/{job_id}/cancel", tags=["Jobs"])
async def cancel_job(job_id: str,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    """Cancel an active or pending dataset generation job."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    status = (job.get("status") or "").lower()
    if status in {"cancelled", "completed", "failed"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel job in '{status}' state")

    # Cancel orchestrator in-memory active task if running
    if orchestrator and hasattr(orchestrator, "active_jobs") and job_id in orchestrator.active_jobs:
        active_task = orchestrator.active_jobs.get(job_id)
        if hasattr(active_task, "cancel") and callable(active_task.cancel):
            try:
                active_task.cancel()
            except Exception:
                pass

    await db.update_job_status(job_id, {"status": "cancelled", "error": "Cancelled by user request"})

    # Broadcast status change to websockets
    if job_id in active_websockets:
        updated_job = await db.get_job_status(job_id)
        for ws in list(active_websockets[job_id]):
            try:
                await ws.send_json(updated_job)
            except Exception:
                pass

    return {"status": "cancelled", "job_id": job_id, "message": "Job cancelled successfully"}


@app.delete("/jobs/{job_id}", tags=["Jobs"])
async def delete_job_endpoint(job_id: str,
    admin_user: User = Depends(require_role([UserRole.ADMIN]))):
    """Delete a job, all associated datasets/samples, and output files."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Cancel if running
    if orchestrator and hasattr(orchestrator, "active_jobs") and job_id in orchestrator.active_jobs:
        active_task = orchestrator.active_jobs.get(job_id)
        if hasattr(active_task, "cancel") and callable(active_task.cancel):
            try:
                active_task.cancel()
            except Exception:
                pass

    # Clean up output artifacts on disk
    try:
        output_dir = Path("outputs")
        if output_dir.exists():
            for f in output_dir.glob(f"*{job_id}*"):
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass

    success = await db.delete_job(job_id)
    return {"success": success, "message": f"Job {job_id} and associated data deleted"}


class AcceptPreviewRequest(BaseModel):
    edited_samples: Optional[list[dict]] = None


class RejectPreviewRequest(BaseModel):
    updated_prompt: Optional[str] = None
    notes: Optional[str] = None


@app.get("/jobs/{job_id}/preview_samples", tags=["Jobs"])
async def get_job_preview_samples(job_id: str,
    current_user: User = Depends(get_current_user)):
    """Retrieve early dataset preview samples generated for a job."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")
    config = job.get("config") or {}
    preview_samples = config.get("preview_samples", [])
    return {
        "job_id": job_id,
        "status": job["status"],
        "samples": preview_samples,
        "sample_count": len(preview_samples)
    }


@app.post("/jobs/{job_id}/accept_preview", tags=["Jobs"])
async def accept_job_preview(job_id: str, payload: AcceptPreviewRequest = Body(default_factory=AcceptPreviewRequest),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    """Accept early preview samples, optionally with user edits, and advance pipeline with full capabilities."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    status = (job.get("status") or "").lower()
    stage = (job.get("current_stage") or "").lower()
    if status not in {"awaiting_preview_approval", "pending", "running"} and "preview" not in stage:
        raise HTTPException(status_code=409, detail=f"Job {job_id} is in state '{status}' (stage '{stage}') and not awaiting preview approval")

    if orchestrator and hasattr(orchestrator, "accept_preview"):
        success = orchestrator.accept_preview(job_id, edited_samples=payload.edited_samples)
        if success:
            return {"success": True, "message": f"Preview accepted for job {job_id}. Advancing pipeline."}
    if db:
        await db.update_job_status(job_id, {"status": "running", "current_stage": "discover"})
        return {"success": True, "message": f"Job {job_id} resumed."}
    raise HTTPException(status_code=404, detail="Job not found or not awaiting preview")


@app.post("/jobs/{job_id}/reject_preview", tags=["Jobs"])
async def reject_job_preview(job_id: str, payload: RejectPreviewRequest = Body(default_factory=RejectPreviewRequest),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    """Reject early preview samples, optionally supply updated prompt, and re-generate preview."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    status = (job.get("status") or "").lower()
    stage = (job.get("current_stage") or "").lower()
    if status not in {"awaiting_preview_approval", "pending", "running"} and "preview" not in stage:
        raise HTTPException(status_code=409, detail=f"Job {job_id} is in state '{status}' (stage '{stage}') and not awaiting preview approval")

    if orchestrator and hasattr(orchestrator, "reject_preview"):
        success = orchestrator.reject_preview(job_id, updated_prompt=payload.updated_prompt)
        if success:
            return {"success": True, "message": "Preview rejected. Re-optimizing query and generating fresh samples."}
    if db:
        status_update: dict[str, Any] = {"status": "running", "current_stage": "query_optimizer"}
        if payload.updated_prompt:
            cfg = job.get("config") or {}
            cfg["target_domain"] = payload.updated_prompt
            status_update["config"] = cfg
        await db.update_job_status(job_id, status_update)
        return {"success": True, "message": "Job updated for regeneration."}
    raise HTTPException(status_code=404, detail="Job not found or not awaiting preview")





# =============================================================================
# Job Records API
# =============================================================================

@app.get("/jobs/{job_id}/records", tags=["Jobs"])
async def get_job_records(job_id: str, limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user)):
    """Get sample records from datasets belonging to a job."""
    from pathlib import Path
    import json

    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    # Dynamic resolution from disk datasets if matching output exists
    disk_info = _resolve_dynamic_disk_dataset(job_id)
    if disk_info and Path(disk_info["output_path"]).exists() and disk_info["output_path"].endswith(".jsonl"):
        disk_records = []
        with open(disk_info["output_path"], "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if line.strip():
                    item = json.loads(line)
                    disk_records.append({
                        "id": f"{job_id}-{idx}",
                        "dataset_id": job_id,
                        "instruction": item.get("instruction", ""),
                        "response": item.get("response", ""),
                        "input": item.get("input", ""),
                        "quality_score": item.get("quality_score"),
                        "difficulty_tier": item.get("difficulty_tier"),
                        "created_at": item.get("created_at"),
                    })
                if len(disk_records) >= limit:
                    break
        return {
            "records": disk_records,
            "count": len(disk_records),
            "message": None,
        }

    try:
        # Find datasets for this job, then fetch their samples
        datasets = await db.get_datasets_by_job(job_id)
        records: list[dict] = []
        for ds in datasets:
            samples = await db.get_samples(ds["id"], limit=limit)
            for sample in samples:
                records.append({
                    "id": sample["id"],
                    "dataset_id": sample["dataset_id"],
                    "instruction": sample.get("instruction", ""),
                    "response": sample.get("response", ""),
                    "input": sample.get("input", ""),
                    "quality_score": sample.get("quality_score"),
                    "difficulty_tier": sample.get("difficulty_tier"),
                    "created_at": sample.get("created_at"),
                })
                if len(records) >= limit:
                    break
            if len(records) >= limit:
                break

        # Fallback to early preview samples if export has not completed yet
        if not records:
            if job and job.get("config"):
                cfg = job["config"]
                preview_samples = cfg.get("preview_samples") or []
                for idx, ps in enumerate(preview_samples[:limit]):
                    records.append({
                        "id": f"preview-{idx}",
                        "dataset_id": job_id,
                        "instruction": ps.get("instruction", ""),
                        "response": ps.get("response", ""),
                        "input": ps.get("input", ""),
                        "quality_score": ps.get("metadata", {}).get("quality_score"),
                        "difficulty_tier": ps.get("metadata", {}).get("difficulty_tier"),
                        "created_at": job.get("created_at"),
                    })

        return {
            "records": records[:limit],
            "count": len(records[:limit]),
            "message": None,
        }
    except Exception as e:
        logger.error(f"Failed to get records for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get records")


@app.get("/jobs/{job_id}/summary", tags=["Jobs"])
async def get_job_dataset_summary(job_id: str,
    current_user: User = Depends(get_current_user)):
    """Return persisted quality, provenance, balance, and review coverage for a job."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    datasets = await db.get_datasets_by_job(job_id)
    config = job.get("config") or {}
    review_enabled = bool(config.get("human_review"))
    review = {
        "enabled": review_enabled,
        "requested_percentage": float(config.get("human_review_percentage", 10.0)) if review_enabled else 0.0,
        "total": 0,
        "approved": 0,
        "rejected": 0,
        "pending": 0,
        "flagged": 0,
    }
    review_service = getattr(app.state, "review_service", None)
    if review["enabled"] and review_service:
        queue = await review_service.get_queue(job_id=job_id, page=1, page_size=1)
        review["total"] = queue.get("total", 0)
        for st in ("approved", "rejected", "pending", "flagged"):
            status_queue = await review_service.get_queue(status=st, job_id=job_id, page=1, page_size=1)
            review[st] += status_queue.get("total", 0)

    if not datasets:
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "sample_count": job.get("samples_generated", 0),
            "sample_cap": 10000,
            "balance_report": None,
            "provenance": None,
            "quality": {"mean": job.get("quality_score"), "scored_samples": 0},
            "sources": {},
            "languages": {},
            "topics": {},
            "human_review": review,
            "sampled_records": 0,
        }

    from collections import Counter
    dataset = datasets[0]
    dataset_meta = dataset.get("metadata") or {}
    stored = await db.get_samples(dataset["id"], limit=10000)
    sources, languages, topics = Counter(), Counter(), Counter()
    scores = []
    for sample in stored:
        metadata = sample.get("metadata") or {}
        for counter, key in ((sources, "source_type"), (languages, "language"), (topics, "topic")):
            value = metadata.get(key)
            if value:
                counter[str(value)] += 1
        score = sample.get("quality_score")
        if isinstance(score, (int, float)):
            scores.append(float(score))

    config = job.get("config") or {}
    review_enabled = bool(config.get("human_review"))
    review = {
        "enabled": review_enabled,
        "requested_percentage": float(config.get("human_review_percentage", 10.0)) if review_enabled else 0.0,
        "total": 0,
        "approved": 0,
        "rejected": 0,
        "pending": 0,
        "flagged": 0,
    }
    review_service = getattr(app.state, "review_service", None)
    if review["enabled"] and review_service:
        queue = await review_service.get_queue(job_id=job_id, page=1, page_size=1)
        review["total"] = queue.get("total", 0)
        for status in ("approved", "rejected", "pending", "flagged"):
            status_queue = await review_service.get_queue(status=status, job_id=job_id, page=1, page_size=1)
            review[status] += status_queue.get("total", 0)

    job_quality = job.get("quality_score") if isinstance(job, dict) else getattr(job, "quality_score", None)
    if job_quality is None and isinstance(job, dict):
        job_quality = (job.get("metadata") or {}).get("quality_score") or ((job.get("metadata") or {}).get("quality_breakdown") or {}).get("composite")
    if job_quality is None:
        job_quality = dataset_meta.get("quality_score") or (dataset_meta.get("quality_breakdown") or {}).get("composite")
    canonical_mean = job_quality if job_quality is not None else (round(sum(scores) / len(scores), 4) if scores else None)

    return {
        "job_id": job_id,
        "dataset_id": dataset["id"],
        "status": job.get("status"),
        "sample_count": dataset.get("size", len(stored)),
        "sample_cap": 10000,
        "balance_report": dataset_meta.get("balance_report"),
        "provenance": dataset_meta.get("provenance"),
        "quality": {"mean": canonical_mean, "scored_samples": len(scores)},
        "sources": dict(sources),
        "languages": dict(languages),
        "topics": dict(topics),
        "human_review": review,
        "sampled_records": len(stored),
    }


@app.get("/jobs/{job_id}/report", tags=["Jobs"])
async def get_job_report(job_id: str,
    current_user: User = Depends(get_current_user)):
    """Return comprehensive analytical and execution report for a job."""
    summary = await get_job_dataset_summary(job_id, current_user)
    job = await db.get_job_status(job_id) if db else None
    config = (job.get("config") or {}) if job else {}
    return {
        "job_id": job_id,
        "status": job.get("status") if job else summary.get("status"),
        "created_at": job.get("created_at") if job else None,
        "completed_at": job.get("completed_at") if job else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "summary": summary,
        "error": job.get("error") if job else None,
    }


from api.disk_resolver import resolve_dynamic_disk_dataset, _resolve_dynamic_disk_dataset



class SignedUrlRequest(BaseModel):
    ttl_seconds: int = Field(3600, ge=60, le=86400, description="Token validity duration in seconds (60 to 86400)")
    format: Optional[str] = Field("jsonl", description="Target export format: jsonl, csv, xml, parquet, json")


class SignedUrlResponse(BaseModel):
    job_id: str
    token: str
    expires_at: int
    expires_in_seconds: int
    format: str
    download_url: str


@app.post("/jobs/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Jobs"])
@app.post("/datasets/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Datasets"])
@app.get("/jobs/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Jobs"])
@app.get("/datasets/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Datasets"])
async def create_presigned_download_url(
    job_id: str,
    request: Request,
    ttl_seconds: int = Query(3600, description="Token validity in seconds (default 3600)"),
    format: Optional[str] = Query(None, description="Dataset format: jsonl, csv, xml, parquet, json"),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    """Generate an ephemeral HMAC-SHA256 presigned token for streaming private datasets."""
    # Verify existence and ownership of target job or dataset
    if db:
        target_obj = await db.get_job_status(job_id)
        if not target_obj:
            target_obj = await db.get_dataset(job_id)
        if not target_obj:
            datasets_for_job = await db.get_datasets_by_job(job_id)
            if datasets_for_job:
                target_obj = datasets_for_job[0]
        if not target_obj:
            raise HTTPException(status_code=404, detail=f"Job or Dataset '{job_id}' not found")
        _enforce_owner(target_obj, current_user, resource_name="Job/Dataset")

    parsed_req = None
    if request.method == "POST":
        try:
            raw_body = await request.body()
            if raw_body:
                body_data = json.loads(raw_body)
                try:
                    parsed_req = SignedUrlRequest(**body_data)
                except Exception as val_err:
                    raise HTTPException(status_code=400, detail=f"Invalid SignedUrlRequest: {val_err}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Malformed request body: {e}")

    if parsed_req:
        final_ttl = parsed_req.ttl_seconds
        final_format = (parsed_req.format or "jsonl").lower().strip()
    else:
        # Check Query parameter TTL bounds strictly (no silent clamping)
        if ttl_seconds < 60 or ttl_seconds > 86400:
            raise HTTPException(status_code=400, detail="ttl_seconds must be between 60 and 86400 seconds")
        final_ttl = ttl_seconds
        final_format = (format or "jsonl").lower().strip()

    valid_formats = {"jsonl", "csv", "xml", "parquet", "json"}
    if final_format not in valid_formats:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{final_format}'. Allowed: {sorted(valid_formats)}")

    expires_at = int(time.time()) + final_ttl
    user_binding = current_user.username if current_user else ""
    try:
        token = _sign_download_token(job_id, expires_at, user=user_binding, format=final_format)
    except RuntimeError as sec_err:
        raise HTTPException(status_code=503, detail=str(sec_err))
    download_path = f"/jobs/{job_id}/download?token={token}&expires={expires_at}&format={final_format}"

    return SignedUrlResponse(
        job_id=job_id,
        token=token,
        expires_at=expires_at,
        expires_in_seconds=final_ttl,
        format=final_format,
        download_url=download_path,
    )


@app.get("/jobs/{job_id}/download", tags=["Jobs"])
@app.get("/datasets/{job_id}/download", tags=["Datasets"])
async def download_job_dataset(
    job_id: str,
    format: Optional[str] = Query(None, description="Export format: jsonl, csv, xml, parquet, json"),
    token: Optional[str] = Query(None, description="Ephemeral HMAC-SHA256 presigned token"),
    expires: Optional[int] = Query(None, description="Unix timestamp expiration of signed token"),
    request: Request = None,
    current_user: Optional[User] = Depends(get_current_user_optional)):
    """Download the completed dataset file for a job or dataset ID.
    
    Dynamically negotiates formats (JSONL, CSV, XML, Parquet, JSON) and resolves
    data from local storage or dynamically streams from the database.
    Requires an ephemeral presigned token or a Bearer JWT.
    """
    # 1. Content negotiation for requested format
    req_format = (format or "").lower().strip()
    if not req_format and request:
        accept = request.headers.get("accept", "").lower()
        if "text/csv" in accept:
            req_format = "csv"
        elif "application/xml" in accept or "text/xml" in accept:
            req_format = "xml"
        elif "parquet" in accept:
            req_format = "parquet"
        elif "application/json" in accept and "x-ndjson" not in accept:
            req_format = "json"
        elif "x-ndjson" in accept:
            req_format = "jsonl"

    if req_format not in {"jsonl", "csv", "xml", "parquet", "json"}:
        req_format = "jsonl"

    # 0. Authorization check: Ephemeral Presigned Token or Bearer Auth
    # A valid Bearer must NOT be defeated by a bad query token.
    authorized = False
    auth_user = current_user

    # First check Bearer auth
    if auth_user:
        authorized = True
        if auth_user.role != UserRole.ADMIN and db:
            target_res = await db.get_job_status(job_id)
            if not target_res:
                target_res = await db.get_dataset(job_id)
            if not target_res:
                datasets_for_job = await db.get_datasets_by_job(job_id)
                if datasets_for_job:
                    target_res = datasets_for_job[0]
            if not target_res:
                raise HTTPException(status_code=404, detail="Resource not found")
            owner = target_res.get("owner")
            if owner and owner != auth_user.username:
                raise HTTPException(status_code=404, detail="Resource not found")

    # If no valid Bearer auth, evaluate presigned token
    if not authorized:
        if token and expires is not None:
            # Validate token against requested job_id, expires, format
            # We check with empty user or bound user
            if _verify_download_token(job_id, token, expires, format=req_format):
                authorized = True
            else:
                # Try finding if token is valid for any owner bound to target object
                verified_with_target = False
                if db:
                    target_res = await db.get_job_status(job_id)
                    if not target_res:
                        target_res = await db.get_dataset(job_id)
                    if not target_res:
                        datasets_for_job = await db.get_datasets_by_job(job_id)
                        if datasets_for_job:
                            target_res = datasets_for_job[0]
                    if target_res:
                        res_owner = target_res.get("owner") or ""
                        if _verify_download_token(job_id, token, expires, user=res_owner, format=req_format):
                            authorized = True
                            verified_with_target = True
                if not verified_with_target:
                    raise HTTPException(
                        status_code=403,
                        detail="Invalid or expired download token. Please request a new signed URL via POST /jobs/{job_id}/signed-url."
                    )
        elif token or expires is not None:
            raise HTTPException(
                status_code=403,
                detail="Both 'token' and 'expires' parameters are required for presigned dataset access."
            )
        else:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Provide a valid Bearer token or presigned download URL (?token=...&expires=...)."
            )

    if not authorized:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Unauthorized dataset access for '{job_id}'. "
                "Private dataset streaming requires a valid HMAC-SHA256 presigned token "
                "(?token=...&expires=...) or Bearer token header. "
                "Generate an ephemeral signed URL via POST /jobs/{job_id}/signed-url."
            ),
        )

    # Completion check: if job status exists, it must be 'completed'
    if db:
        job_status_obj = await db.get_job_status(job_id)
        if job_status_obj:
            status_val = job_status_obj.get("status") if isinstance(job_status_obj, dict) else getattr(job_status_obj, "status", None)
            if status_val and status_val != "completed":
                raise HTTPException(status_code=409, detail=f"Job '{job_id}' is not complete (current status: {status_val})")

    media_types = {
        "jsonl": "application/x-ndjson",
        "csv": "text/csv; charset=utf-8",
        "xml": "application/xml; charset=utf-8",
        "parquet": "application/vnd.apache.parquet",
        "json": "application/json; charset=utf-8",
    }

    # 2. Check dynamic filesystem discovery
    disk_match = _resolve_dynamic_disk_dataset(job_id)
    if disk_match:
        # Check if requested format file already exists in directory
        disk_dir = disk_match.get("dir")
        if disk_dir and Path(disk_dir).is_dir():
            target_format_files = list(Path(disk_dir).glob(f"*.{req_format}"))
            if target_format_files:
                from fastapi.responses import FileResponse
                chosen_file = target_format_files[0]
                return FileResponse(
                    path=str(chosen_file),
                    filename=chosen_file.name,
                    media_type=media_types.get(req_format, "application/octet-stream"),
                )
        if disk_match.get("type") == req_format and Path(disk_match.get("output_path", "")).exists():
            from fastapi.responses import FileResponse
            return FileResponse(
                path=disk_match["output_path"],
                filename=Path(disk_match["output_path"]).name,
                media_type=media_types.get(req_format, "application/octet-stream"),
            )

    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # 3. Dynamic Database Resolution (Strictly EXACT IDs only, no substring matching)
    dataset = await db.get_dataset(job_id) if hasattr(db, "get_dataset") else None
    if not dataset:
        job = await db.get_job_status(job_id)
        if job:
            datasets = await db.get_datasets_by_job(job_id)
            if datasets:
                dataset = datasets[0]

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset or Job '{job_id}' not found")

    output_path = dataset.get("output_path")

    # If requested format file already exists on disk, return it directly
    if output_path:
        cand_p = Path(output_path).with_suffix(f".{req_format}")
        if cand_p.exists():
            from fastapi.responses import FileResponse
            return FileResponse(
                path=str(cand_p),
                filename=cand_p.name,
                media_type=media_types.get(req_format, "application/octet-stream"),
            )

    # 4. Dynamic Multi-Format Streaming from Database
    page_size = 1000
    first_page = await db.get_samples(dataset["id"], limit=page_size, offset=0)
    if not first_page:
        raise HTTPException(status_code=404, detail="No samples found for this dataset")

    download_name = f"{dataset.get('name', 'dataset')}.{req_format}"

    # Parquet format: chunked Arrow table
    if req_format == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            import io
            all_samples = await db.get_samples(dataset["id"], limit=MAX_SAMPLE_LOAD_LIMIT)
            rows = []
            for s in all_samples:
                rows.append({
                    "instruction": str(s.get("instruction", "")),
                    "input": str(s.get("input", "")),
                    "response": str(s.get("response", "")),
                    "quality_score": float(s.get("quality_score", 0.0) or 0.0),
                    "difficulty_tier": int(s.get("difficulty_tier", 1) or 1),
                })
            table = pa.Table.from_pylist(rows)
            buf = io.BytesIO()
            pq.write_table(table, buf)
            buf.seek(0)
            from fastapi.responses import Response
            return Response(
                content=buf.getvalue(),
                media_type="application/vnd.apache.parquet",
                headers={"Content-Disposition": f"attachment; filename={download_name}"},
            )
        except Exception as e:
            logger.warning("Parquet dynamic export failed, falling back to JSONL: %s", e)
            req_format = "jsonl"
            download_name = f"{dataset.get('name', 'dataset')}.jsonl"

    from fastapi.responses import StreamingResponse

    # XML Streaming Generator
    if req_format == "xml":
        import xml.sax.saxutils as xml_escape

        async def xml_generator():
            yield '<?xml version="1.0" encoding="UTF-8"?>\n<dataset>\n'
            offset = 0
            page = first_page
            while page:
                for sample in page:
                    inst = xml_escape.escape(str(sample.get("instruction", "")))
                    inp = xml_escape.escape(str(sample.get("input", "")))
                    resp = xml_escape.escape(str(sample.get("response", "")))
                    score = sample.get("quality_score", "")
                    tier = sample.get("difficulty_tier", "")
                    yield f'  <sample>\n    <instruction>{inst}</instruction>\n    <input>{inp}</input>\n    <response>{resp}</response>\n    <quality_score>{score}</quality_score>\n    <difficulty_tier>{tier}</difficulty_tier>\n  </sample>\n'
                offset += len(page)
                if len(page) < page_size:
                    break
                page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)
            yield '</dataset>\n'

        return StreamingResponse(
            xml_generator(),
            media_type="application/xml; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={download_name}"},
        )

    # CSV Streaming Generator
    if req_format == "csv":
        import csv
        import io

        async def csv_generator():
            s_io = io.StringIO()
            writer = csv.writer(s_io)
            writer.writerow(["instruction", "input", "response", "quality_score", "difficulty_tier"])
            yield s_io.getvalue()
            s_io.seek(0)
            s_io.truncate(0)

            offset = 0
            page = first_page
            while page:
                for sample in page:
                    writer.writerow([
                        sample.get("instruction", ""),
                        sample.get("input", ""),
                        sample.get("response", ""),
                        sample.get("quality_score", ""),
                        sample.get("difficulty_tier", ""),
                    ])
                    yield s_io.getvalue()
                    s_io.seek(0)
                    s_io.truncate(0)
                offset += len(page)
                if len(page) < page_size:
                    break
                page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)

        return StreamingResponse(
            csv_generator(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={download_name}"},
        )

    # Standard JSON Array Generator
    if req_format == "json":
        async def json_array_generator():
            yield "[\n"
            first_item = True
            offset = 0
            page = first_page
            while page:
                for sample in page:
                    item = {
                        "instruction": sample.get("instruction", ""),
                        "response": sample.get("response", ""),
                        "input": sample.get("input", ""),
                        "quality_score": sample.get("quality_score"),
                        "difficulty_tier": sample.get("difficulty_tier"),
                    }
                    prefix = "" if first_item else ",\n"
                    first_item = False
                    yield prefix + "  " + json.dumps(item, ensure_ascii=False)
                offset += len(page)
                if len(page) < page_size:
                    break
                page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)
            yield "\n]\n"

        return StreamingResponse(
            json_array_generator(),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={download_name}"},
        )

    # Default JSONL Streaming Generator
    async def jsonl_generator():
        offset = 0
        page = first_page
        while page:
            for sample in page:
                item = {
                    "instruction": sample.get("instruction", ""),
                    "response": sample.get("response", ""),
                    "input": sample.get("input", ""),
                    "quality_score": sample.get("quality_score"),
                    "difficulty_tier": sample.get("difficulty_tier"),
                    "metadata": sample.get("metadata", {}),
                }
                yield json.dumps(item, ensure_ascii=False) + "\n"
            offset += len(page)
            if len(page) < page_size:
                break
            page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)

    return StreamingResponse(
        jsonl_generator(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )





@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": "RasoSynthTune",
        "version": "2.0.0",
        "description": "Advanced autonomous dataset generation with constraint-aware intelligence",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "features": [
            "Constraint-aware data discovery",
            "Multilingual processing",
            "Low-resource domain handling",
            "Adaptive quality filtering",
            "Self-improving research loop",
            "Streaming export for large datasets",
        ]
    }


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def get_favicon():
    """Serve brand SVG favicon."""
    fav_svg = Path("frontend/public/favicon.svg")
    if fav_svg.exists():
        return Response(content=fav_svg.read_bytes(), media_type="image/svg+xml")
    # Inline fallback
    inline_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <!-- C1 Original, light-background version: ink R dots, stone field dots, orange final point. -->
  <!-- Field dots (r 2.6, stone #d8d2c4) -->
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
  <!-- R dots (r 3.6, ink #1b1b18) -->
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
  <!-- Final point (r 3.6, orange #f26625); leg steps diagonally (42,42) -> (52,52) -->
  <circle cx="52" cy="52" r="3.6" fill="#f26625"/>
</svg>"""
    return Response(content=inline_svg.encode("utf-8"), media_type="image/svg+xml")


async def run_pipeline(job_id: str, request: JobRequest | dict, resume_state: Optional[dict] = None):
    """Run the dataset generation pipeline.

    Production pipeline execution:
    - Requires orchestrator to be initialized
    - Requires database to be available for persistence
    - Fails explicitly if prerequisites not met
    - No silent fallbacks to demo/simulation mode
    - Admission control limits concurrent execution
    """
    if not orchestrator:
        logger.error(f"Cannot run pipeline {job_id}: orchestrator not initialized")
        if db:
            await db.update_job(job_id, status="failed", error="Orchestrator not initialized")
        return

    if not db:
        logger.error(f"Cannot run pipeline {job_id}: database not available")
        raise RuntimeError(f"Database connection required for job execution. Job {job_id} cannot proceed.")

    # Phase 2: Acquire admission slot (may wait if at capacity)
    admission = None
    admission_acquired = False
    try:
        admission = admission_controller
        if admission:
            admission_acquired = await admission.acquire(job_id)
            if not admission_acquired:
                logger.error(f"Cannot run pipeline {job_id}: admission rejected (queue full)")
                if db:
                    await db.update_job(job_id, status="failed",
                                        error="Admission rejected: server at capacity")
                return
    except Exception as e:
        logger.warning(f"Admission control check failed for {job_id}: {e}")

    if observability is not None:
        observability.log_job_event(job_id, "pipeline_started")

    job = Job(
        id=job_id,
        status=JobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        current_stage="analyzing_constraints",
        progress=0.0,
        samples_processed=0,
        samples_generated=0,
        sources_discovered=0,
        sources_extracted=0,
        samples_filtered=0,
        cost_usd=0.0,
        error=None,
        config=request.model_dump() if hasattr(request, "model_dump") else dict(request)
    )

    try:
        await orchestrator.run(job, resume_state=resume_state)
        
        # Phase 4: Enforce that pipeline completion requires generated samples > 0
        if getattr(job, "samples_generated", 0) == 0:
            rejection_details = (
                f"Zero samples were constructed. "
                f"Discovered: {getattr(job, 'sources_discovered', 0)}, "
                f"Extracted: {getattr(job, 'sources_extracted', 0)}, "
                f"Filtered: {getattr(job, 'samples_filtered', 0)}."
            )
            raise ValueError(f"Pipeline completed but generated 0 samples. Details: {rejection_details}")

        if observability is not None:
            observability.log_job_event(job_id, "pipeline_completed")
        # Persist completed status and final progress to DB
        try:
            await db.update_job(
                job_id,
                status="completed",
                progress=1.0,
                current_stage="export",
                samples_generated=job.samples_generated,
                samples_processed=job.samples_processed,
                sources_discovered=getattr(job, "sources_discovered", 0),
                sources_extracted=getattr(job, "sources_extracted", 0),
                samples_filtered=getattr(job, "samples_filtered", 0),
            )
        except Exception as db_error:
            logger.error(f"Failed to update completed job status in DB: {db_error}")
    except Exception as e:
        logger.error(f"Pipeline {job_id} failed: {e}")
        if observability is not None:
            observability.log_job_event(job_id, "pipeline_failed", {"error": str(e)})
        # Update job status in database
        try:
            await db.update_job(job_id, status="failed", error=str(e), current_stage=job.current_stage)
        except Exception as db_error:
            logger.error(f"Failed to update job status in DB: {db_error}")
    finally:
        # Release admission control slot (always — even on failure)
        if admission and admission_acquired:
            try:
                admission.release(job_id)
            except Exception as release_err:
                logger.warning(f"Failed to release admission slot for {job_id}: {release_err}")

    if job_id in active_websockets:
        for ws in active_websockets[job_id]:
            try:
                await ws.send_json({"status": job.status.value, "job_id": job_id})
            except Exception:
                pass
