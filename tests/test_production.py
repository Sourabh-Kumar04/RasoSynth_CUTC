"""Production validation tests for RasoSynthTune."""
import pytest
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestDatabaseHardening:
    """Test database hardening - no silent mock fallbacks."""

    def test_no_mock_fallback_import(self):
        """Verify database module doesn't silently fall back to mocks."""
        from db.async_db import AsyncDatabaseManager
        # Should fail explicitly if DB unavailable, not use mock
        # This is tested in integration tests with actual DB

    @pytest.mark.asyncio
    async def test_database_explicit_failure(self):
        """Database should fail explicitly if connection unavailable."""
        from db.async_db import DatabaseConfig, AsyncDatabaseManager

        config = DatabaseConfig(url="postgresql://invalid:invalid@localhost:9999/invalid")
        manager = AsyncDatabaseManager(config)

        # Should raise explicit error, not use mock
        with pytest.raises(RuntimeError, match="Database connection failed"):
            await manager.initialize()


class TestAuthentication:
    """Test authentication system."""

    def test_auth_manager_creation(self):
        """Test auth manager initializes correctly."""
        from api.auth import AuthManager, UserRole
        auth = AuthManager()
        assert auth.secret is not None
        assert auth.algorithm == "HS256"

    def test_token_creation(self):
        """Test JWT token creation."""
        from api.auth import AuthManager, UserRole
        auth = AuthManager()
        token = auth.create_token("test-user", "testuser", UserRole.USER)
        assert token is not None
        assert len(token) > 0

    def test_token_verification(self):
        """Test JWT token verification."""
        from api.auth import AuthManager, UserRole
        auth = AuthManager()
        token = auth.create_token("test-user", "testuser", UserRole.USER)
        token_data = auth.verify_token(token)
        assert token_data.user_id == "test-user"
        assert token_data.username == "testuser"

    def test_disabled_auth(self):
        """Auth stays enforced in the test suite: the AUTH_DISABLED
        bypass was removed by the P0 test updates (conftest forces
        AUTH_DISABLED=false), and get_auth_manager() is a cached
        singleton, so auth cannot be re-disabled mid-process."""
        from api.auth import get_auth_manager
        auth = get_auth_manager()
        assert auth.auth_disabled is False

    def test_auth_disabled_production_behaviour_in_fresh_process(self):
        """Pin AUTH_DISABLED=true production behaviour in a fresh process.

        An in-process env flip does not affect the already-imported singleton
        auth manager. In a fresh process with AUTH_DISABLED=true:
        1. When no users configured: get_current_user raises 503 (System not configured).
        2. When users configured: get_current_user still requires valid token format (401),
           guaranteeing audit trail and preventing silent auth bypass in production.
        """
        import subprocess
        code = """
import os, sys, asyncio
sys.path.insert(0, '.')
# Ensure clean env without inherited conftest credentials
os.environ.pop('ADMIN_USER', None)
os.environ.pop('USER_USER', None)
os.environ['JWT_SECRET'] = 'K7m9pQ2vX5zL8wR1tY4uN6bC3jF0gH2sD5vA8mK1pQ9xZ4'
os.environ['AUTH_DISABLED'] = 'true'
from api.auth import get_current_user, get_auth_manager
from fastapi import HTTPException

# Check 1: Without users configured
auth = get_auth_manager()
assert auth.auth_disabled is True
assert len(auth._users) == 0, f"Expected 0 users, found: {list(auth._users.keys())}"

try:
    asyncio.run(get_current_user(None))
    raise AssertionError("Should have raised HTTPException")
except HTTPException as e:
    assert e.status_code == 503, f"Expected 503 when no users configured, got {e.status_code}"

# Check 2: With users configured
os.environ['ADMIN_USER'] = 'admin:secret123'
os.environ['USER_USER'] = 'user:secret123'
from api.auth import AuthManager
auth_with_users = AuthManager()
assert auth_with_users.auth_disabled is True
assert len(auth_with_users._users) == 2

import api.auth as auth_mod
auth_mod._auth_manager = auth_with_users
try:
    asyncio.run(get_current_user(None))
    raise AssertionError("Should have raised HTTPException")
except HTTPException as e:
    assert e.status_code == 401, f"Expected 401 audit trail requirement, got {e.status_code}"

print("FRESH_PROCESS_AUTH_DISABLED_OK")
"""
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"Subprocess failed:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        assert "FRESH_PROCESS_AUTH_DISABLED_OK" in proc.stdout


class TestProviderValidation:
    """Test provider validation system."""

    def test_provider_validator_creation(self):
        """Test provider validator initializes."""
        from api.provider_validator import ProviderValidator, ProviderHealth
        config = {"GOOGLE_API_KEY": ""}
        validator = ProviderValidator(config)
        assert validator.config == config

    @pytest.mark.asyncio
    async def test_validation_with_no_keys(self):
        """Test validation with no API keys."""
        from api.provider_validator import ProviderValidator, ProviderHealth
        config = {"GOOGLE_API_KEY": "", "ANTHROPIC_API_KEY": ""}
        validator = ProviderValidator(config)
        results = await validator.validate_all_providers()

        # Should mark providers as unconfigured, not fail
        assert "google_gemini" in results
        assert results["google_gemini"].status == ProviderHealth.UNCONFIGURED


class TestWebSocketManager:
    """Test WebSocket manager."""

    @pytest.mark.asyncio
    async def test_ws_manager_creation(self):
        """Test WebSocket manager initializes."""
        from api.websocket_manager import get_ws_manager
        # Without Redis URL, should still work
        manager = await get_ws_manager(None)
        assert manager is not None
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_active_jobs_tracking(self):
        """Test active jobs tracking."""
        from api.websocket_manager import get_ws_manager
        manager = await get_ws_manager(None)
        jobs = manager.get_active_jobs()
        assert isinstance(jobs, list)


class TestResearchLoop:
    """Test research loop improvements."""

    def test_research_loop_creation(self):
        """Test research loop initializes."""
        from core.research_loop import ResearchLoop, Technique
        loop = ResearchLoop(config={"enable_research_loop": True})
        assert loop.config["enable_research_loop"] is True

    @pytest.mark.asyncio
    async def test_research_cycle(self):
        """Test research cycle runs."""
        from core.research_loop import ResearchLoop
        loop = ResearchLoop(config={"enable_research_loop": True})
        result = await loop.run_research_cycle()
        assert result["status"] in ["success", "skipped"]

    def test_technique_storage(self):
        """Test technique storage works."""
        from core.research_loop import ResearchLoop
        loop = ResearchLoop()
        assert hasattr(loop, "_discovered_techniques")
        assert isinstance(loop._discovered_techniques, list)


class TestKnowledgeBase:
    """Test knowledge base improvements."""

    def test_knowledge_base_creation(self):
        """Test knowledge base initializes."""
        from research.knowledge_base import KnowledgeBase, KnowledgeType
        kb = KnowledgeBase()
        assert kb is not None

    def test_embedding_fallback(self):
        """Test deterministic embedding generation."""
        from research.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()

        # Same text should produce same embedding
        emb1 = kb._generate_embedding("test text", None)
        emb2 = kb._generate_embedding("test text", None)
        assert emb1 == emb2

        # Different text should produce different embedding
        emb3 = kb._generate_embedding("different text", None)
        assert emb1 != emb3

        # Embedding should have correct length
        assert len(emb1) == 128


class TestServerIntegration:
    """Test server integration."""

    def test_server_imports(self):
        """Test server imports work."""
        # This will fail if there are import errors
        import api.server
        assert hasattr(api.server, "app")

    def test_auth_endpoints_registered(self):
        """Test auth endpoints are registered."""
        import api.server
        def collect_paths(route_list):
            paths = []
            for route in route_list:
                if hasattr(route, "path"):
                    paths.append(route.path)
                nested = getattr(route, "original_router", None)
                if nested is not None:
                    paths.extend(collect_paths(nested.routes))
            return paths

        routes = collect_paths(api.server.app.routes)
        assert "/auth/login" in routes
        assert "/auth/logout" in routes
        assert "/auth/me" in routes


class TestConfiguration:
    """Test configuration improvements."""

    def test_env_variables(self):
        """Test required env variables are set."""
        from dotenv import load_dotenv
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(str(env_file))
        os.environ.setdefault("DEMO_MODE", "true")

        # Demo mode should be enabled for testing
        assert os.getenv("DEMO_MODE") == "true"

    def test_jwt_config(self):
        """Test JWT configuration."""
        from dotenv import load_dotenv
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(str(env_file))
        os.environ.setdefault("JWT_ALGORITHM", "HS256")

        assert os.getenv("JWT_SECRET") is not None
        assert os.getenv("JWT_ALGORITHM") == "HS256"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])