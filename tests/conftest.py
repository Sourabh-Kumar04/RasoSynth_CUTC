"""Pytest configuration and fixtures for RasoDataset-Agent tests."""
import asyncio
import os
import sys
from datetime import datetime

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Security: ensure JWT_SECRET is set for all tests
os.environ.setdefault(
    "JWT_SECRET",
    os.getenv("JWT_SECRET") or "test-jwt-secret-for-testing-only-min32chars"
)
os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("AI_DATASET_ENVIRONMENT", "development")


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def _clean_db_file():
    """Remove test DB file once at session start/end to avoid stale SQLite file
    being deleted while session-scoped test_client holds an open connection."""
    import os
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "app.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    yield
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
async def db():
    """Create a fresh test database for each test."""
    from core.db import AsyncDB
    from core.config import Settings

    settings = Settings()
    db = await AsyncDB.create(settings.postgres_url)

    # Clear any existing data
    try:
        await db.clear_all_jobs()
    except Exception:
        pass

    yield db

    # Cleanup
    try:
        await db.clear_all_jobs()
    except Exception:
        pass


@pytest.fixture
def mock_router():
    """Create a mock provider router."""
    from unittest.mock import Mock, AsyncMock

    router = Mock()
    router.initialize = AsyncMock(return_value={"initialized": [], "failed": []})
    return router


@pytest.fixture
async def orchestrator(mock_router, db):
    """Create an orchestrator with test database.

    Patches _setup_metrics to prevent Prometheus duplicate registration
    when tests run in sequence within the same pytest session.
    """
    import unittest.mock as mock
    with mock.patch("core.observability_manager.ObservabilityManager._setup_metrics"):
        from core.config import Settings
        from core.orchestrator_core import DatasetOrchestrator

        settings = Settings()
        config = settings.model_dump()
        return DatasetOrchestrator(config, mock_router, db=db)


@pytest.fixture
def mock_settings():
    """Create test settings."""
    from core.config import Settings
    return Settings()


@pytest.fixture(scope="session")
def test_client():
    """Create a single FastAPI TestClient shared across all tests to avoid lifespan repetition."""
    from fastapi.testclient import TestClient
    from api.server import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_sample():
    """Create a mock sample object."""
    class MockSample:
        def __init__(
            self,
            instruction="Test instruction",
            response="Test response",
            input_="",
            metadata=None,
            quality_score=0.85,
            difficulty_tier=3,
        ):
            self.instruction = instruction
            self.response = response
            self.input = input_
            self.metadata_ = metadata or {}
            self.quality_score = quality_score
            self.difficulty_tier = difficulty_tier

    return MockSample()


@pytest.fixture
async def test_job(db):
    """Create a test job in the database."""
    job = await db.create_job({
        "config": {
            "target_domain": "test domain",
            "dataset_size": 10,
            "export_format": "jsonl",
            "cost_budget_usd": 1.0,
        },
        "status": "pending",
    })
    return job


@pytest.fixture
async def test_dataset(db, test_job):
    """Create a test dataset linked to the test job."""
    ds = await db.create_dataset(
        job_id=test_job["id"],
        name="test_dataset",
        type="jsonl",
        size=2,
        metadata={"test": True},
        output_path="/tmp/test.jsonl",
    )

    # Add samples
    await db.create_samples(ds["id"], [
        {
            "instruction": "Q1",
            "response": "A1",
            "input": "",
            "metadata": {},
            "quality_score": 0.9,
            "difficulty_tier": 3,
        },
        {
            "instruction": "Q2",
            "response": "A2",
            "input": "",
            "metadata": {},
            "quality_score": 0.8,
            "difficulty_tier": 2,
        },
    ])

    return ds