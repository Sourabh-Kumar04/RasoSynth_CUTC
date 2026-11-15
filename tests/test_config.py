"""Tests for configuration module."""
import os
# Undo .env override so we test actual defaults
_original_env = os.environ.get("redis_url") or os.environ.get("REDIS_URL")
if "REDIS_URL" in os.environ:
    del os.environ["REDIS_URL"]
if "redis_url" in os.environ:
    del os.environ["redis_url"]

from core.config import Settings, get_settings


def test_settings_defaults():
    """Test settings have correct defaults."""
    settings = Settings()

    # These are class-level defaults that don't come from .env
    assert settings.max_concurrent_jobs == 5
    assert settings.token_budget_usd == 100.0
    assert settings.cache_ttl == 3600
    assert len(settings.provider_priority) == 7
    # redis_url is loaded from .env so check it's a valid URL string
    assert settings.redis_url.startswith("redis://")


def test_settings_env_override():
    """Test environment variable override."""
    settings = Settings(
        google_api_key="test-key",
        max_concurrent_jobs=10
    )

    assert settings.google_api_key == "test-key"
    assert settings.max_concurrent_jobs == 10


def test_get_settings_cached():
    """Test get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2


def test_model_dump():
    """Test model_dump returns all configuration."""
    settings = Settings(
        google_api_key="test",
        nvidia_api_key="nvidia-test",
    )

    dump = settings.model_dump()

    assert "google_api_key" in dump
    assert "nvidia_api_key" in dump
    assert "deepseek_api_key" in dump
    assert "openrouter_api_key" in dump
    assert "together_api_key" in dump
    assert "featherless_api_key" in dump
    assert "provider_priority" in dump
    assert "rate_limits" in dump


def test_supabase_postgres_url_normalization():
    """Verify Supabase PostgreSQL URLs with pooler params and sslmode normalize correctly."""
    from core.db import DatabaseManager
    # 1. Direct connection
    s1 = Settings(postgres_url="postgresql://postgres:secret@db.projectref.supabase.co:5432/postgres?sslmode=require")
    assert s1.postgres_url.startswith("postgresql+asyncpg://")
    assert "sslmode=" not in s1.postgres_url

    # 2. Transaction pooler with pgbouncer
    s2 = Settings(postgres_url="postgresql://postgres.projectref:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require&pgbouncer=true")
    assert s2.postgres_url.startswith("postgresql+asyncpg://")
    assert "pgbouncer" not in s2.postgres_url

    # 3. DatabaseManager engine instantiation
    mgr = DatabaseManager(s2.postgres_url)
    assert mgr.is_postgresql is True
    assert mgr.engine.url.drivername == "postgresql+asyncpg"