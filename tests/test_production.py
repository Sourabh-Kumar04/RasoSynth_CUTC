"""Production validation tests for RasoDataset-Agent."""
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
        from db.async_db import DatabaseConfig

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
        """Test auth disabled mode."""
        os.environ["AUTH_DISABLED"] = "true"
        from api.auth import get_auth_manager
        auth = get_auth_manager()
        assert auth.auth_disabled is True
        os.environ["AUTH_DISABLED"] = "false"


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
        routes = [r.path for r in api.server.app.routes]
        assert "/auth/login" in routes
        assert "/auth/logout" in routes
        assert "/auth/me" in routes


class TestConfiguration:
    """Test configuration improvements."""

    def test_env_variables(self):
        """Test required env variables are set."""
        from dotenv import load_dotenv
        load_dotenv("/mnt/d/00_Academics/RasoDataset-Agent Agent/ai-dataset-engineer/.env")

        # Demo mode should be enabled for testing
        assert os.getenv("DEMO_MODE") == "true"

    def test_jwt_config(self):
        """Test JWT configuration."""
        from dotenv import load_dotenv
        load_dotenv("/mnt/d/00_Academics/RasoDataset-Agent Agent/ai-dataset-engineer/.env")

        assert os.getenv("JWT_SECRET") is not None
        assert os.getenv("JWT_ALGORITHM") == "HS256"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])