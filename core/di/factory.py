"""Application factory for environment-aware initialization."""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, Callable
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import Settings, get_settings
from core.di.container import ServiceContainer, create_container
from core.observability import ObservabilityManager

logger = logging.getLogger(__name__)


class AppFactory:
    """
    Application factory for creating FastAPI app with proper lifecycle management.

    Features:
    - Environment-aware configuration
    - Async resource bootstrapping
    - Graceful shutdown handling
    - Service container integration
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings
        self._container: Optional[ServiceContainer] = None

    @property
    def settings(self) -> Settings:
        """Get settings, loading from environment if not provided."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_cors_origins(self) -> list[str]:
        """Get CORS origins based on environment."""
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

    async def _initialize_services(self, app: FastAPI) -> None:
        """Initialize all services."""
        logger.info("Initializing services...")

        # Create and configure container
        self._container = await create_container(self.settings)

        # Get observability manager
        observability: ObservabilityManager = await self._container.resolve(ObservabilityManager)
        await observability.initialize()
        observability.add_span_exporter("console")

        logger.info("Services initialized successfully")

    async def _cleanup_services(self) -> None:
        """Cleanup all services on shutdown."""
        logger.info("Cleaning up services...")

        if self._container:
            await self._container.shutdown()

        logger.info("Services cleaned up successfully")

    def create_app(
        self,
        title: str = "RasoSynthTune",
        description: str = "Autonomous AI dataset generation platform",
        version: str = "1.0.0",
        include_health_check: bool = True,
        include_metrics: bool = True,
    ) -> FastAPI:
        """
        Create FastAPI application with proper lifecycle.

        Args:
            title: Application title
            description: Application description
            version: API version
            include_health_check: Add /health endpoint
            include_metrics: Add /metrics endpoint

        Returns:
            Configured FastAPI application
        """

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan handler."""
            # Startup
            await self._initialize_services(app)
            logger.info(f"Application started: {title} v{version}")

            yield

            # Shutdown
            await self._cleanup_services()
            logger.info("Application shutdown complete")

        app = FastAPI(
            title=title,
            description=description,
            version=version,
            lifespan=lifespan,
        )

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self._get_cors_origins(),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Include health check if requested
        if include_health_check:
            self._add_health_endpoints(app)

        return app

    def _add_health_endpoints(self, app: FastAPI) -> None:
        """Add health check endpoints."""

        @app.get("/health")
        async def health_check():
            """Liveness check."""
            return {"status": "healthy", "service": "ai-dataset-engineer"}

        @app.get("/health/ready")
        async def readiness_check():
            """Readiness check."""
            checks = {
                "container": self._container is not None,
            }

            all_ready = all(checks.values())

            return {
                "status": "ready" if all_ready else "not_ready",
                "checks": checks,
            }


# Global factory instance
_factory: Optional[AppFactory] = None


def get_app_factory() -> AppFactory:
    """Get the global application factory."""
    global _factory
    if _factory is None:
        _factory = AppFactory()
    return _factory


def create_prod_app() -> FastAPI:
    """Create production application."""
    factory = AppFactory()
    return factory.create_app(
        title="RasoSynthTune",
        description="Enterprise-grade autonomous AI dataset generation platform",
        version="1.0.0",
    )


def create_test_app() -> FastAPI:
    """Create test application."""
    factory = AppFactory()
    return factory.create_app(
        title="RasoSynthTune (Test)",
        description="Test instance",
        version="0.0.0",
    )