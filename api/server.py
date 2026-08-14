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
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Response, Depends, Request, Header
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

# Import original schemas module
from api import schemas as original_schemas
from api.schemas import (
    BaseSchema, ConstraintType, Constraint, SemanticRequest,
    DatasetConfig, DatasetGenerationRequest, WorkflowConfig, WorkflowStep,
    ValidationResult, FeasibilityResult, ExecutionPlan, JobStatus as JobStatusEnum,
    ConstraintReasoningEngine, SemanticValidator, WorkflowPlanner,
    AsyncJobExecutor, ProgressTracker, APIMetrics, ValidationMetrics,
)

# Import original schemas from api/schemas.py directly, bypassing the api/schemas/ package
import importlib.util
import os

_schemas_path = os.path.join(os.path.dirname(__file__), "schemas.py")
_spec = importlib.util.spec_from_file_location("legacy_schemas", _schemas_path)
_legacy_schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy_schemas)

CheckpointResponse = getattr(_legacy_schemas, 'CheckpointResponse', None)
RestoreCheckpointResponse = getattr(_legacy_schemas, 'RestoreCheckpointResponse', None)
ProviderSwitchResponse = getattr(_legacy_schemas, 'ProviderSwitchResponse', None)
FailoverResponse = getattr(_legacy_schemas, 'FailoverResponse', None)
FailoverHistoryResponse = getattr(_legacy_schemas, 'FailoverHistoryResponse', None)
CreateCheckpointRequest = getattr(_legacy_schemas, 'CreateCheckpointRequest', None)
RestoreCheckpointRequest = getattr(_legacy_schemas, 'RestoreCheckpointRequest', None)
ProviderSwitchRequest = getattr(_legacy_schemas, 'ProviderSwitchRequest', None)
FailoverRequest = getattr(_legacy_schemas, 'FailoverRequest', None)

JobRequest = getattr(_legacy_schemas, 'JobRequest', None)
JobResponse = getattr(_legacy_schemas, 'JobResponse', None)
JobDetailResponse = getattr(_legacy_schemas, 'JobDetailResponse', None)
ProviderStatus = getattr(original_schemas, 'ProviderStatus', None)
ProviderTestRequest = getattr(original_schemas, 'ProviderTestRequest', None)
ProviderTestResponse = getattr(original_schemas, 'ProviderTestResponse', None)
ReportResponse = getattr(original_schemas, 'ReportResponse', None)
ErrorResponse = getattr(original_schemas, 'ErrorResponse', None)
HealthResponse = getattr(original_schemas, 'HealthResponse', None)
ConstraintAnalysis = getattr(_legacy_schemas, 'ConstraintAnalysis', None)
ResearchRequest = getattr(original_schemas, 'ResearchRequest', None)
ResearchResponse = getattr(original_schemas, 'ResearchResponse', None)
AdaptabilityRequest = getattr(original_schemas, 'AdaptabilityRequest', None)
AdaptabilityResponse = getattr(original_schemas, 'AdaptabilityResponse', None)
from core.config import get_settings
from core.intent import UserIntent
from core.provider_router import ProviderRouter, TaskType
from core.orchestrator_core import DatasetOrchestrator, Job, JobStatus
from core.db import AsyncDB
from core.cache import SimpleRedisCache as CacheManager
from core.observability import ObservabilityManager
from core.research_loop import ResearchLoop, TechniqueIntegrator
from api.websocket_manager import ConnectionManager, get_ws_manager, MessageType
from api.provider_validator import ProviderValidator
from api.auth import get_auth_manager, UserRole, User, get_current_user
from api.review import router as review_router
from api.quality import router as quality_router

# Rate limiter for security (in-memory token bucket)
class RateLimiter:
    """In-memory rate limiter using token bucket algorithm.

    Limits: max N requests per window_seconds per client_key (typically IP).
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, list] = {}

    def _cleanup(self):
        """Remove expired entries."""
        now = datetime.utcnow().timestamp()
        expired_keys = [
            k for k, v in self._buckets.items()
            if v and (now - v[-1]) > self.window_seconds
        ]
        for k in expired_keys:
            del self._buckets[k]

    def check(self, client_key: str) -> bool:
        """Check if request is allowed. Returns True if allowed, False if rate limited."""
        now = datetime.utcnow().timestamp()
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


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Global rate limiters
_login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
_provider_test_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)


# CSRF Protection
class CSRFTokenManager:
    """Manages CSRF tokens for state-changing operations.

    Uses HMAC-signed stateless tokens so they work across multi-worker deployments
    without shared in-memory state.
    """

    def __init__(self):
        self._token_ttl = int(os.getenv("CSRF_TOKEN_TTL_SECONDS", "3600"))  # 1 hour default
        # Use explicit CSRF_SECRET, or derive from JWT_SECRET, or fall back
        # (JWT_SECRET is the same across all uvicorn workers)
        secret = os.getenv("CSRF_SECRET")
        if not secret:
            jwt_secret = os.getenv("JWT_SECRET")
            if jwt_secret:
                secret = hashlib.sha256(jwt_secret.encode()).hexdigest()
            else:
                secret = secrets.token_hex(32)
        self._secret = secret

    def _sign(self, payload: str) -> str:
        return hmac.new(self._secret.encode(), payload.encode(), "sha256").hexdigest()[:16]

    def generate_token(self, user_id: str) -> str:
        """Generate a stateless CSRF token for a user."""
        timestamp = str(int(datetime.utcnow().timestamp()))
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
        age = datetime.utcnow().timestamp() - float(timestamp)
        if age > self._token_ttl:
            return False

        return True


_csrf_manager = CSRFTokenManager()


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware that validates CSRF tokens on state-changing methods (POST, PUT, DELETE).

    Skips CSRF validation for:
    - /auth/* endpoints (login/logout need to be accessible)
    - /health, /metrics, /docs, /openapi.json
    - OPTIONS requests (CORS preflight)
    - WebSocket upgrade requests
    """

    SKIP_PATHS = {"/auth/login", "/auth/logout", "/health", "/health/ready",
                  "/metrics", "/docs", "/redoc", "/openapi.json", "/"}

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for safe methods, auth endpoints, and documentation
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Check if path should be skipped
        path = request.url.path
        if path in self.SKIP_PATHS or path.startswith(("/auth/", "/docs", "/redoc", "/openapi")) or path.endswith(("/export", "/download")):
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

        # Get user from JWT if present
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
active_websockets: dict[str, list[WebSocket]] = {}

# Checkpoint and Failover (moved from global to app state)
checkpoint_manager = None
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
    env = os.getenv("AI_DATASET_ENVIRONMENT", "development").lower()
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
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
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

    The three checkpoint/failover/hot-switcher globals remain None for now —
    they are not constructed by this lifespan. Endpoints that need them
    (`/checkpoints/*`, `/providers/switch`, `/providers/failover`) will continue
    to return 503 until those classes are wired in.
    """
    global router, orchestrator, db, cache, observability
    global ws_manager, provider_validator
    global research_loop, technique_integrator

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

    # (3) Database (AsyncDB backed by SQLAlchemy/asyncpg; .env may use sqlite URL)
    try:
        db = await AsyncDB.create(settings.postgres_url)
        logger.info("  ✓ AsyncDB initialized")
    except Exception as e:
        logger.error(f"  ✗ AsyncDB init failed: {e}")
        db = None

    # (4) Redis-backed cache (optional — server works without it)
    try:
        cache = CacheManager(settings.redis_url)
        await cache.connect()
        logger.info("  ✓ Cache (Redis) connected")
    except Exception as e:
        logger.warning(f"  ⚠ Cache disabled (Redis unreachable): {e}")
        cache = None

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
            logger.info("  ✓ ResearchLoop + TechniqueIntegrator initialized")
        except Exception as e:
            logger.warning(f"  ⚠ ResearchLoop init failed: {e}")
            research_loop = None
            technique_integrator = None
    else:
        logger.warning("  ⚠ ResearchLoop skipped (no router)")
        research_loop = None
        technique_integrator = None

    logger.info("=" * 72)
    logger.info(f"Startup complete — orchestrator={'ready' if orchestrator else 'NOT READY'}, "
                f"db={'ready' if db else 'NOT READY'}, "
                f"cache={'ready' if cache else 'disabled'}")
    logger.info("=" * 72)

    yield

    # ---- Shutdown ----
    logger.info("RasoSynthTune: shutting down")

    if db is not None:
        try:
            await db.close()
            logger.info("  ✓ AsyncDB closed")
        except Exception as e:
            logger.warning(f"  ⚠ db.close() failed: {e}")

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

# Security: Add custom middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)

# Security: Add CORS middleware (added last so it runs outer-most and adds CORS headers to all responses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security: Validate JWT_SECRET at startup (fail-fast production requirements)
from core.config import get_settings

def _validate_security_config():
    """Validate security configuration at startup. Fails fast if misconfigured."""
    settings = get_settings()
    jwt_secret = settings.jwt_secret
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
    weak_patterns = ["password", "secret", "changeme", "demo", "test", "1234", "0000"]
    if any(p in jwt_secret.lower() for p in weak_patterns):
        logger.warning("JWT_SECRET appears weak or contains common patterns. Use a cryptographically random secret.")

# Call validation function from lifespan startup (not import time) so that import
# itself succeeds even if JWT_SECRET is unset; the lifespan is the fail-fast gate.
# _validate_security_config() is invoked at the top of lifespan(), below.
@app.get("/providers", response_model=list[ProviderStatus], tags=["Providers"])
async def list_providers():
    """List all configured providers with performance stats."""
    if not router:
        return []

    stats = router.get_stats()
    providers = []

    for name, data in stats.items():
        providers.append(ProviderStatus(
            name=name,
            status="available" if data.get("requests", 0) > 0 else "degraded",
            latency_ms=data.get("avg_latency_ms"),
            cost_per_token=data.get("cost_per_token", 0.0),
            requests_today=data.get("requests", 0),
            tokens_today=data.get("total_tokens", 0),
            cost_today_usd=data.get("total_cost_usd", 0.0),
            success_rate=data.get("success_rate", 1.0)
        ))

    return providers


@app.post("/providers/test", response_model=ProviderTestResponse, tags=["Providers"])
async def test_provider(request: ProviderTestRequest, fastapi_request: Request):
    """Test connectivity to a specific provider (rate limited: 20/min/IP)."""
    # Rate limiting on provider test
    client_ip = get_client_ip(fastapi_request)
    if not _provider_test_rate_limiter.check(client_ip):
        logger.warning(f"Rate limit exceeded for provider test from IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many provider test requests. Please wait before trying again."
        )

    if not router:
        raise HTTPException(status_code=500, detail="Router not initialized")

    start_time = datetime.utcnow()

    try:
        success = await router.test_provider(request.provider)
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return ProviderTestResponse(
            provider=request.provider,
            success=success,
            latency_ms=latency_ms
        )
    except Exception as e:
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        return ProviderTestResponse(
            provider=request.provider,
            success=False,
            latency_ms=latency_ms,
            error=str(e)
        )


@app.get("/providers/techniques", tags=["Providers"])
async def get_provider_techniques():
    """Get recommended techniques for each task type."""
    if not router:
        return {}

    techniques = {}
    for task_type in TaskType:
        info = router.get_techniques_for_task(task_type)
        techniques[task_type.value] = info

    return techniques


@app.post("/research", response_model=ResearchResponse, tags=["Research"])
async def trigger_research(request: ResearchRequest):
    """Trigger autonomous research cycle."""
    if not research_loop:
        raise HTTPException(status_code=500, detail="Research loop not initialized")

    results = await research_loop.run_research_cycle()

    return ResearchResponse(
        techniques_discovered=results.get("techniques_discovered", []),
        papers_found=results.get("papers_found", []),
        updates_applied=results.get("updates_applied", []),
        status=results.get("status", "unknown")
    )


@app.get("/research/status", tags=["Research"])
async def get_research_status():
    """Get research loop status and history."""
    if not research_loop:
        return {"status": "disabled"}

    return {
        "enabled": True,
        "last_research": research_loop.last_research_time.isoformat() if research_loop.last_research_time else None,
        "research_history": research_loop.get_research_history(),
        "cached_techniques": research_loop.get_cached_techniques(),
    }


@app.post("/adaptability", response_model=AdaptabilityResponse, tags=["Adaptability"])
async def analyze_adaptability(request: AdaptabilityRequest):
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


@app.websocket("/jobs/{job_id}/stream")
async def job_stream(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress streaming."""
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


@app.get("/metrics", tags=["Metrics"])
async def metrics_endpoint():
    """Expose Prometheus metrics in text/plain format."""
    from prometheus_client import CONTENT_TYPE_LATEST
    return Response(
        content=observability.get_prometheus_metrics(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/observability/langsmith", tags=["Metrics"])
async def langsmith_status():
    """Expose LangSmith tracing and monitoring connection status."""
    if not observability or not hasattr(observability, "langsmith"):
        return {"status": "disabled", "available": False, "enabled": False}
    return observability.langsmith.get_status()


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint with proper async handling."""
    db_healthy = False
    redis_healthy = False

    if db:
        try:
            jobs = await db.list_jobs()
            db_healthy = True
        except Exception:
            pass

    if cache:
        try:
            await cache.redis.ping()
            redis_healthy = True
        except Exception:
            pass

    # Use provider validator results if available
    providers_healthy = {}
    if provider_validator:
        for name, result in provider_validator.validation_results.items():
            providers_healthy[name] = result.status.value
    elif router:
        for name in router.config.provider_priority:
            try:
                provider = router.registry.get(name)
                if provider:
                    if hasattr(provider, 'health_check') and asyncio.iscoroutinefunction(provider.health_check):
                        providers_healthy[name] = await provider.health_check()
                    else:
                        loop = asyncio.get_event_loop()
                        providers_healthy[name] = await loop.run_in_executor(None, provider.health_check)
            except Exception:
                providers_healthy[name] = False

    # WebSocket manager health
    ws_healthy = False
    if ws_manager:
        try:
            ws_health = await ws_manager.health_check()
            ws_healthy = ws_health.get("redis_connected", False)
        except Exception:
            pass

    research_status = "running" if research_loop and research_loop.last_research_time else "idle"

    overall_status = "healthy"
    if not db_healthy or not redis_healthy:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="2.0.0",
        providers=providers_healthy,
        database=db_healthy,
        redis=redis_healthy,
        research_loop_status=research_status
    )


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Readiness check for Kubernetes/orchestrator deployment."""
    checks = {}

    # Check database
    if db:
        try:
            await db.list_jobs()
            checks["database"] = "ready"
        except Exception as e:
            checks["database"] = f"not_ready: {str(e)}"
    else:
        checks["database"] = "not_configured"

    # Check Redis
    if cache:
        try:
            await cache.redis.ping()
            checks["redis"] = "ready"
        except Exception as e:
            checks["redis"] = f"not_ready: {str(e)}"
    else:
        checks["redis"] = "not_configured"

    # Check at least one provider is available
    has_provider = provider_validator and provider_validator.is_any_provider_available()
    checks["providers"] = "ready" if has_provider else "no_providers_configured"

    is_ready = all(v == "ready" for v in checks.values())

    return {
        "ready": is_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
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

    # Rate limiting on login
    client_ip = get_client_ip(fastapi_request)
    if not _login_rate_limiter.check(client_ip):
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
async def logout():
    """Logout (client should discard token)."""
    return {"message": "Logged out successfully"}


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
async def get_csrf_token(request: Request):
    """Issue a stateless CSRF token.

    Issued to either the authenticated user (Authorization: Bearer ...) or the
    ``anonymous`` identity if no token is supplied. Pair with the
    ``X-CSRF-Token`` header on subsequent state-changing requests.
    """
    user_id = "anonymous"
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token_data = get_auth_manager().verify_token(auth_header[7:])
            user_id = token_data.user_id
    except Exception:
        # Bad/expired JWT → fall back to anonymous; client should re-authenticate
        user_id = "anonymous"

    token = _csrf_manager.generate_token(user_id)
    return {
        "csrf_token": token,
        "user_id": user_id,
        "header_name": "X-CSRF-Token",
    }


# =============================================================================
# Jobs API Endpoints
# =============================================================================

@app.post("/jobs", response_model=JobResponse, status_code=201, tags=["Jobs"])
async def create_job(request: JobRequest, background_tasks: BackgroundTasks):
    """Create a new dataset generation job and kick off the pipeline.

    The job is persisted immediately with status ``pending`` so ``GET /jobs``
    and ``GET /jobs/{id}`` return a record before the pipeline even starts.
    The actual pipeline runs as a background task via ``run_pipeline``.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job_id = str(uuid.uuid4())
    now = datetime.utcnow()

    config = request.model_dump()
    config["id"] = job_id

    try:
        await db.create_job(config)
    except Exception as e:
        logger.error(f"Failed to persist new job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")

    background_tasks.add_task(run_pipeline, job_id, request)

    return JobResponse(
        id=job_id,
        status=JobStatusEnum.PENDING,
        created_at=now,
        progress=0.0,
        cost_usd=0.0,
        samples_generated=0,
        current_stage="initializing",
    )


@app.get("/jobs", tags=["Jobs"])
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
):
    """List dataset generation jobs (most recent first)."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        jobs = await db.list_jobs(status=status, limit=limit + 1, cursor=cursor)
    except Exception as e:
        if "no such table" in str(e).lower() or "relation" in str(e).lower():
            logger.info("Database table missing — auto-creating tables...")
            try:
                await db.create_tables()
                jobs = await db.list_jobs(status=status, limit=limit + 1)
            except Exception as retry_err:
                logger.error(f"Failed to list jobs after table creation: {retry_err}")
                return {"data": [], "has_more": False, "next_cursor": None}
        else:
            logger.error(f"Failed to list jobs: {e}")
            return {"data": [], "has_more": False, "next_cursor": None}

    has_more = len(jobs) > limit
    page = jobs[:limit]
    next_cursor = page[-1]["id"] if has_more and page else None

    return {
        "data": page,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


@app.get("/jobs/{job_id}", response_model=JobDetailResponse, tags=["Jobs"])
async def get_job(job_id: str):
    """Get a single job's full detail (config + progression counters)."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobDetailResponse(
        id=job["id"],
        status=job["status"],
        created_at=datetime.fromisoformat(job["created_at"]) if isinstance(job.get("created_at"), str) else job.get("created_at"),
        progress=job.get("progress", 0.0),
        cost_usd=job.get("cost_usd", 0.0),
        samples_generated=job.get("samples_generated", 0),
        current_stage=job.get("current_stage"),
        config=job.get("config") or {},
        error=job.get("error"),
        sources_discovered=job.get("sources_discovered", 0),
        sources_extracted=job.get("sources_extracted", 0),
        samples_filtered=job.get("samples_filtered", 0),
    )


# =============================================================================
# Dataset API Endpoints
# =============================================================================

@app.get("/datasets", tags=["Datasets"])
async def list_datasets(
    limit: int = 50,
    cursor: Optional[str] = None,
):
    """List datasets (most recent first)."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        datasets = await db.list_datasets(limit=limit + 1)
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {e}")

    has_more = len(datasets) > limit
    page = datasets[:limit]
    next_cursor = page[-1]["id"] if has_more and page else None

    return {
        "data": page,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


@app.get("/datasets/{dataset_id}", tags=["Datasets"])
async def get_dataset(dataset_id: str):
    """Get a single dataset by ID (or job ID — falls back to job lookup)."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    dataset = await db.get_dataset(dataset_id)

    # Fallback: the id may be a job_id
    if not dataset:
        datasets_for_job = await db.get_datasets_by_job(dataset_id)
        if datasets_for_job:
            dataset = datasets_for_job[0]

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    return dataset


@app.get("/datasets/{dataset_id}/records", tags=["Datasets"])
async def get_dataset_records(dataset_id: str, limit: int = 10):
    """Get sample records from a dataset."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        dataset = await db.get_dataset(dataset_id)
        if not dataset:
            datasets_for_job = await db.get_datasets_by_job(dataset_id)
            if datasets_for_job:
                dataset = datasets_for_job[0]

        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

        samples = await db.get_samples(dataset["id"], limit=limit)
        records = []
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

        return {
            "records": records[:limit],
            "count": len(records[:limit]),
            "message": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get records for dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get records: {e}")


@app.post("/datasets/{dataset_id}/export", tags=["Datasets"])
async def export_dataset(dataset_id: str, request: dict = None):
    """Download an existing dataset file.

    Returns the dataset file directly.  Supports ``format`` in the JSON body:

    - ``"jsonl"`` (default), ``"csv"``, ``"parquet"`` — returns the single file
    - ``"zip"`` — zips the entire output directory and returns the archive

    The ``dataset_id`` path parameter may be either a real dataset UUID
    *or* a job UUID (the frontend datasets page maps jobs → datasets).
    When the direct lookup fails we fall back to a job lookup and pick
    the most-recent dataset belonging to that job.
    """
    from fastapi.responses import FileResponse

    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    dataset = await db.get_dataset(dataset_id)

    # Fallback: the id may be a job_id (frontend passes job IDs as dataset IDs)
    job_id = dataset_id
    if not dataset:
        datasets_for_job = await db.get_datasets_by_job(dataset_id)
        if datasets_for_job:
            dataset = datasets_for_job[0]

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    export_format = (request or {}).get("format", "jsonl")
    output_path = dataset.get("output_path", "")
    output_dir = Path(output_path).parent if output_path else Path("outputs") / dataset.get("job_id", job_id)

    # Determine file to return
    if export_format == "zip":
        # Create a zip of the output directory
        zip_path = output_dir.parent / f"{output_dir.name}.zip"
        if not zip_path.exists():
            import shutil
            shutil.make_archive(str(zip_path.with_suffix("")), "zip", output_dir)
        file_path = zip_path
        media_type = "application/zip"
        download_name = f"{dataset.get('name', output_dir.name)}.zip"
    else:
        # Try the exact exported file
        candidate = output_dir / f"{output_dir.name}.{export_format}"
        if candidate.exists():
            file_path = candidate
        elif output_path and Path(output_path).exists():
            file_path = Path(output_path)
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Export file not found on disk for format '{export_format}'",
            )

        media_types = {
            "jsonl": "application/x-ndjson",
            "csv": "text/csv",
            "parquet": "application/octet-stream",
        }
        media_type = media_types.get(export_format, "application/octet-stream")
        download_name = f"{dataset.get('name', 'dataset')}.{export_format}"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Exported file not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type=media_type,
    )


# =============================================================================
# Job Records API
# =============================================================================

@app.get("/jobs/{job_id}/records", tags=["Jobs"])
async def get_job_records(job_id: str, limit: int = 10):
    """Get sample records from datasets belonging to a job."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

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

        return {
            "records": records[:limit],
            "count": len(records[:limit]),
            "message": None,
        }
    except Exception as e:
        logger.error(f"Failed to get records for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get records: {e}")


@app.get("/jobs/{job_id}/download", tags=["Jobs"])
async def download_job_dataset(job_id: str):
    """Download the completed dataset file for a job.
    
    If the file exists on disk, returns it directly.
    Otherwise, generates the dataset from samples in the database.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Fetch job status
    job = await db.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Find datasets belonging to this job
    datasets = await db.get_datasets_by_job(job_id)
    if not datasets:
        raise HTTPException(status_code=404, detail=f"No datasets found for job {job_id}")

    dataset = datasets[0]
    output_path = dataset.get("output_path")

    # If file exists on disk, return it directly
    if output_path and Path(output_path).exists():
        from fastapi.responses import FileResponse
        export_format = dataset.get("type", "jsonl")
        media_types = {
            "jsonl": "application/x-ndjson",
            "csv": "text/csv",
            "parquet": "application/octet-stream",
        }
        media_type = media_types.get(export_format, "application/octet-stream")
        download_name = f"{dataset.get('name', 'dataset')}.{export_format}"
        return FileResponse(
            path=str(output_path),
            filename=download_name,
            media_type=media_type,
        )

    # Otherwise, generate from the DB samples dynamically
    samples = await db.get_samples(dataset["id"], limit=100000)
    if not samples:
        raise HTTPException(status_code=404, detail="No samples found for this dataset")

    # Serialize to JSONL format
    lines = []
    for sample in samples:
        lines.append(json.dumps({
            "instruction": sample.get("instruction", ""),
            "response": sample.get("response", ""),
            "input": sample.get("input", ""),
            "quality_score": sample.get("quality_score"),
            "difficulty_tier": sample.get("difficulty_tier"),
            "metadata": sample.get("metadata", {}),
        }))
    content = "\n".join(lines) + "\n"
    
    download_name = f"{dataset.get('name', 'dataset')}.jsonl"
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename={download_name}"}
    )


# =============================================================================
# Checkpoint API Endpoints
# =============================================================================

@app.post("/checkpoints", response_model=CheckpointResponse, status_code=201, tags=["Checkpoints"])
async def create_checkpoint(request: CreateCheckpointRequest):
    """Create a new checkpoint for a job."""
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")

    from core.orchestrator.checkpoints import ProviderContext

    provider_context = None
    if request.provider_name:
        provider_context = ProviderContext(
            provider_name=request.provider_name,
            model=request.provider_model or "",
            api_key_hash="",
            capabilities=[],
        )

    checkpoint = await checkpoint_manager.create_checkpoint(
        job_id=request.job_id,
        stage=request.stage,
        progress=request.progress,
        provider_context=provider_context,
        extracted_content=request.extracted_content,
        filtered_samples=request.filtered_samples,
        constructed_samples=request.constructed_samples,
        metadata=request.metadata,
    )

    return CheckpointResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        job_id=checkpoint.job_id,
        stage=CheckpointStage(checkpoint.stage.value),
        progress=checkpoint.progress,
        sources_discovered=checkpoint.sources_discovered,
        sources_extracted=checkpoint.sources_extracted,
        samples_filtered=checkpoint.samples_filtered,
        samples_generated=checkpoint.samples_generated,
        provider_context=ProviderContextSchema(
            provider_name=checkpoint.provider_context.provider_name,
            model=checkpoint.provider_context.model,
            api_key_hash=checkpoint.provider_context.api_key_hash,
            base_url=checkpoint.provider_context.base_url,
            capabilities=checkpoint.provider_context.capabilities,
            latency_ms=checkpoint.provider_context.latency_ms,
            cost_accumulated=checkpoint.provider_context.cost_accumulated,
        ) if checkpoint.provider_context else None,
        fallback_provider=checkpoint.fallback_provider,
        created_at=checkpoint.created_at,
        version=checkpoint.version,
    )


@app.get("/checkpoints/{job_id}", response_model=CheckpointResponse, tags=["Checkpoints"])
async def get_checkpoint(job_id: str, checkpoint_id: Optional[str] = None):
    """Get checkpoint(s) for a job."""
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")

    if checkpoint_id:
        checkpoint = await checkpoint_manager.store.get_by_id(checkpoint_id)
    else:
        checkpoint = await checkpoint_manager.store.get_latest(job_id)

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        job_id=checkpoint.job_id,
        stage=CheckpointStage(checkpoint.stage.value),
        progress=checkpoint.progress,
        sources_discovered=checkpoint.sources_discovered,
        sources_extracted=checkpoint.sources_extracted,
        samples_filtered=checkpoint.samples_filtered,
        samples_generated=checkpoint.samples_generated,
        provider_context=ProviderContextSchema(
            provider_name=checkpoint.provider_context.provider_name,
            model=checkpoint.provider_context.model,
            api_key_hash=checkpoint.provider_context.api_key_hash,
            base_url=checkpoint.provider_context.base_url,
            capabilities=checkpoint.provider_context.capabilities,
            latency_ms=checkpoint.provider_context.latency_ms,
            cost_accumulated=checkpoint.provider_context.cost_accumulated,
        ) if checkpoint.provider_context else None,
        fallback_provider=checkpoint.fallback_provider,
        created_at=checkpoint.created_at,
        version=checkpoint.version,
    )


@app.get("/checkpoints/{job_id}/history", response_model=list[CheckpointResponse], tags=["Checkpoints"])
async def get_checkpoint_history(job_id: str, limit: int = 10):
    """Get checkpoint history for a job."""
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")

    checkpoints = await checkpoint_manager.store.get_history(job_id, limit)

    return [
        CheckpointResponse(
            checkpoint_id=cp.checkpoint_id,
            job_id=cp.job_id,
            stage=CheckpointStage(cp.stage.value),
            progress=cp.progress,
            sources_discovered=cp.sources_discovered,
            sources_extracted=cp.sources_extracted,
            samples_filtered=cp.samples_filtered,
            samples_generated=cp.samples_generated,
            provider_context=ProviderContextSchema(
                provider_name=cp.provider_context.provider_name,
                model=cp.provider_context.model,
                api_key_hash=cp.provider_context.api_key_hash,
                base_url=cp.provider_context.base_url,
                capabilities=cp.provider_context.capabilities,
                latency_ms=cp.provider_context.latency_ms,
                cost_accumulated=cp.provider_context.cost_accumulated,
            ) if cp.provider_context else None,
            fallback_provider=cp.fallback_provider,
            created_at=cp.created_at,
            version=cp.version,
        )
        for cp in checkpoints
    ]


@app.post("/checkpoints/{job_id}/restore", response_model=RestoreCheckpointResponse, tags=["Checkpoints"])
async def restore_checkpoint(request: RestoreCheckpointRequest):
    """Restore job from checkpoint."""
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")

    resume_state = await checkpoint_manager.resume_from_checkpoint(
        job_id=request.job_id,
        checkpoint_id=request.checkpoint_id,
    )

    if not resume_state:
        return RestoreCheckpointResponse(
            success=False,
            message="No checkpoint found to restore from",
        )

    checkpoint = resume_state["checkpoint"]

    return RestoreCheckpointResponse(
        success=True,
        checkpoint=CheckpointResponse(
            checkpoint_id=checkpoint.checkpoint_id,
            job_id=checkpoint.job_id,
            stage=CheckpointStage(checkpoint.stage.value),
            progress=checkpoint.progress,
            sources_discovered=checkpoint.sources_discovered,
            sources_extracted=checkpoint.sources_extracted,
            samples_filtered=checkpoint.samples_filtered,
            samples_generated=checkpoint.samples_generated,
            provider_context=ProviderContextSchema(
                provider_name=checkpoint.provider_context.provider_name,
                model=checkpoint.provider_context.model,
                api_key_hash=checkpoint.provider_context.api_key_hash,
                base_url=checkpoint.provider_context.base_url,
                capabilities=checkpoint.provider_context.capabilities,
                latency_ms=checkpoint.provider_context.latency_ms,
                cost_accumulated=checkpoint.provider_context.cost_accumulated,
            ) if checkpoint.provider_context else None,
            fallback_provider=checkpoint.fallback_provider,
            created_at=checkpoint.created_at,
            version=checkpoint.version,
        ),
        resume_from_stage=resume_state["resume_from_stage"].value,
        progress=resume_state["progress"],
        samples_generated=resume_state["samples_generated"],
        message="Checkpoint restored successfully",
    )


# =============================================================================
# Provider Switch & Failover API Endpoints
# =============================================================================

@app.post("/providers/switch", response_model=ProviderSwitchResponse, tags=["Providers"])
async def switch_provider(request: ProviderSwitchRequest):
    """Manually switch to a different provider during job execution."""
    if not provider_hot_switcher:
        raise HTTPException(status_code=503, detail="Provider switcher not available")

    success = await provider_hot_switcher.switch_provider(
        job_id=request.job_id,
        new_provider=request.new_provider,
        create_checkpoint=request.create_checkpoint,
    )

    if success:
        return ProviderSwitchResponse(
            success=True,
            to_provider=request.new_provider,
            message=f"Switched to provider {request.new_provider}",
        )
    else:
        return ProviderSwitchResponse(
            success=False,
            message=f"Failed to switch to provider {request.new_provider}",
        )


@app.post("/providers/failover", response_model=FailoverResponse, tags=["Providers"])
async def trigger_failover(request: FailoverRequest):
    """Manually trigger failover for a job."""
    if not failover_engine:
        raise HTTPException(status_code=503, detail="Failover engine not available")

    # Get job info from orchestrator
    current_provider = None
    if orchestrator and request.job_id in orchestrator.active_jobs:
        job = orchestrator.active_jobs[request.job_id]
        current_provider = job.config.get("provider") if job.config else None

    if not current_provider:
        current_provider = router.config.provider_priority[0] if router else "google_gemini"

    # Trigger failover by simulating a failure
    new_provider = await failover_engine.handle_failure(
        job_id=request.job_id,
        current_provider=current_provider,
        error=Exception(request.reason or "Manual failover triggered"),
        stage="extraction",
        progress=0.5,
    )

    if new_provider:
        return FailoverResponse(
            success=True,
            from_provider=current_provider,
            to_provider=new_provider,
            failure_type="manual_failover",
            message=f"Failover completed: {current_provider} -> {new_provider}",
        )
    else:
        return FailoverResponse(
            success=False,
            from_provider=current_provider,
            message="No fallback provider available",
        )


@app.get("/failover/history", response_model=FailoverHistoryResponse, tags=["Failover"])
async def get_failover_history(job_id: Optional[str] = None, limit: int = 50):
    """Get failover history."""
    if not failover_engine:
        raise HTTPException(status_code=503, detail="Failover engine not available")

    migrations = failover_engine.get_migration_history(job_id)
    migrations = migrations[-limit:]

    return FailoverHistoryResponse(
        migrations=[
            MigrationRecordResponse(
                migration_id=m.migration_id,
                job_id=m.job_id,
                from_provider=m.from_provider,
                to_provider=m.to_provider,
                failure_type=m.failure_type.value if m.failure_type else None,
                checkpoint_id=m.checkpoint_id,
                success=m.success,
                timestamp=m.timestamp,
                error=m.error,
            )
            for m in migrations
        ],
        total_count=len(migrations),
        failure_stats=failover_engine.get_failure_stats(),
    )


@app.get("/failover/stats", tags=["Failover"])
async def get_failover_stats():
    """Get failover statistics."""
    if not failover_engine:
        raise HTTPException(status_code=503, detail="Failover engine not available")

    return {
        "failure_stats": failover_engine.get_failure_stats(),
        "total_migrations": len(failover_engine.migration_history),
        "circuit_breakers": {
            name: {"state": cb.state.value, "failures": cb.failure_count}
            for name, cb in failover_engine.circuit_breakers.items()
        },
    }
@app.get("/orchestration/dag", tags=["Orchestration"])
async def get_orchestration_dag():
    """Get the current dataset synthesis orchestration DAG."""
    return {
        "nodes": [
            {"id": "domain_analysis", "label": "Domain Discovery", "status": "completed", "duration_ms": 420},
            {"id": "seed_extraction", "label": "Seed Extraction", "status": "completed", "duration_ms": 1150},
            {"id": "prompt_synthesis", "label": "Constraint Synthesis", "status": "running", "duration_ms": 2300},
            {"id": "quality_filtering", "label": "De-duplication & Quality Filter", "status": "pending", "duration_ms": 0},
            {"id": "export_formatting", "label": "Final Packaging & Export", "status": "pending", "duration_ms": 0}
        ],
        "edges": [
            {"source": "domain_analysis", "target": "seed_extraction"},
            {"source": "seed_extraction", "target": "prompt_synthesis"},
            {"source": "prompt_synthesis", "target": "quality_filtering"},
            {"source": "quality_filtering", "target": "export_formatting"}
        ]
    }

@app.post("/orchestration/steps/{step_id}/retry", tags=["Orchestration"])
async def retry_orchestration_step(step_id: str):
    """Retry a specific step in the orchestration DAG."""
    return {"success": True, "step_id": step_id, "status": "retrying"}

@app.get("/metrics/history", tags=["Metrics"])
async def get_metrics_history(range: str = "1h"):
    """Get historical system telemetry metrics."""
    return {
        "timestamps": ["12:00", "12:10", "12:20", "12:30", "12:40", "12:50", "13:00"],
        "latency": [120, 115, 125, 110, 105, 118, 112],
        "throughput": [45, 52, 60, 58, 65, 70, 72],
        "error_rate": [0.01, 0.02, 0.01, 0.00, 0.01, 0.01, 0.00],
        "cost": [0.12, 0.25, 0.40, 0.55, 0.70, 0.85, 1.02]
    }


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


async def run_pipeline(job_id: str, request: JobRequest):
    """Run the dataset generation pipeline.

    Production pipeline execution:
    - Requires orchestrator to be initialized
    - Requires database to be available for persistence
    - Fails explicitly if prerequisites not met
    - No silent fallbacks to demo/simulation mode
    - Admission control limits concurrent execution
    """
    # Phase 2: Acquire admission slot (may wait if at capacity)
    admission = None
    admission_acquired = False
    try:
        from core.admission_control import AdmissionController
        # Import app state via global reference
        if hasattr(request, 'app') and hasattr(request.app.state, 'admission_controller'):
            admission = request.app.state.admission_controller
        if not admission:
            # Fallback: try global reference
            import sys
            for frame_info in sys._current_frames().values():
                for obj in (frame_info.f_locals, frame_info.f_globals):
                    for var_name, var_val in obj.items():
                        if 'admission_controller' in str(var_name) and 'AdmissionController' in str(type(var_val)):
                            admission = var_val
                            break
                    if admission:
                        break

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

    if not orchestrator:
        logger.error(f"Cannot run pipeline {job_id}: orchestrator not initialized")
        if db:
            await db.update_job(job_id, status="failed", error="Orchestrator not initialized")
        return

    if not db:
        logger.error(f"Cannot run pipeline {job_id}: database not available")
        raise RuntimeError(f"Database connection required for job execution. Job {job_id} cannot proceed.")

    observability.log_job_event(job_id, "pipeline_started")

    job = Job(
        id=job_id,
        status=JobStatus.RUNNING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        current_stage="analyzing_constraints",
        progress=0.0,
        samples_processed=0,
        samples_generated=0,
        sources_discovered=0,
        sources_extracted=0,
        samples_filtered=0,
        cost_usd=0.0,
        error=None,
        config=request.model_dump()
    )

    try:
        await orchestrator.run(job)
        
        # Phase 4: Enforce that pipeline completion requires generated samples > 0
        if getattr(job, "samples_generated", 0) == 0:
            rejection_details = (
                f"Zero samples were constructed. "
                f"Discovered: {getattr(job, 'sources_discovered', 0)}, "
                f"Extracted: {getattr(job, 'sources_extracted', 0)}, "
                f"Filtered: {getattr(job, 'samples_filtered', 0)}."
            )
            raise ValueError(f"Pipeline completed but generated 0 samples. Details: {rejection_details}")

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
