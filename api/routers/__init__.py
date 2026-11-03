"""Modular API routers for RasoSynthTune."""
from api.routers.agents import router as agents_router
from api.routers.auth import router as auth_router
from api.routers.checkpoints import router as checkpoints_router
from api.routers.datasets import router as datasets_router
from api.routers.delivery import router as delivery_router
from api.routers.failover import router as failover_router
from api.routers.health import router as health_router
from api.routers.jobs import router as jobs_router
from api.routers.observability import router as observability_router
from api.routers.orchestration import router as orchestration_router
from api.routers.providers import router as providers_router
from api.routers.research import router as research_router
from api.routers.tools import router as tools_router
from api.routers.validation import router as validation_router

__all__ = [
    "agents_router",
    "auth_router",
    "checkpoints_router",
    "datasets_router",
    "delivery_router",
    "failover_router",
    "health_router",
    "jobs_router",
    "observability_router",
    "orchestration_router",
    "providers_router",
    "research_router",
    "tools_router",
    "validation_router",
]
