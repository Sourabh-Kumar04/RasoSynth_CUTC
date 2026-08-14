"""Tests for provider failover and checkpoint system."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from providers.failover import (
    FailureType,
    FailureEvent,
    MigrationRecord,
    FailureDetectionService,
    AutomaticFailoverEngine,
    ProviderHotSwitcher,
)
from core.orchestrator_pkg.checkpoints import (
    CheckpointStage,
    ProviderContext,
    Checkpoint,
)


class TestFailureDetectionService:
    """Test failure type detection."""

    def test_detect_rate_limit(self):
        """Test rate limit detection."""
        service = FailureDetectionService()

        # Test via status code
        result = service.detect_failure(
            "test_provider",
            Exception("Rate limit exceeded"),
            status_code=429
        )
        assert result == FailureType.RATE_LIMIT

        # Test via error message
        result = service.detect_failure(
            "test_provider",
            Exception("Too many requests")
        )
        assert result == FailureType.RATE_LIMIT

    def test_detect_quota_exhausted(self):
        """Test quota exhaustion detection."""
        service = FailureDetectionService()

        result = service.detect_failure(
            "test_provider",
            Exception("Inufficient credits")
        )
        assert result == FailureType.QUOTA_EXHAUSTED

    def test_detect_auth_failure(self):
        """Test authentication failure detection."""
        service = FailureDetectionService()

        result = service.detect_failure(
            "test_provider",
            Exception("Unauthorized"),
            status_code=401
        )
        assert result == FailureType.AUTH_FAILURE

    def test_detect_latency_spike(self):
        """Test latency spike detection."""
        service = FailureDetectionService()

        result = service.detect_failure(
            "test_provider",
            Exception("Success"),
            latency_ms=10000  # Above 5 second threshold
        )
        assert result == FailureType.LATENCY_SPIKE


class TestAutomaticFailoverEngine:
    """Test automatic failover engine."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock provider registry."""
        registry = Mock()
        registry.get_available_providers = AsyncMock(return_value=[
            "google_gemini", "anthropic_claude", "ollama"
        ])
        return registry

    @pytest.fixture
    def mock_checkpoint_manager(self):
        """Create mock checkpoint manager."""
        manager = Mock()
        manager.create_checkpoint = AsyncMock()
        return manager

    @pytest.fixture
    def failover_engine(self, mock_registry, mock_checkpoint_manager):
        """Create failover engine."""
        engine = AutomaticFailoverEngine(
            provider_registry=mock_registry,
            checkpoint_manager=mock_checkpoint_manager,
        )
        return engine

    def test_set_fallback_chain(self, failover_engine):
        """Test fallback chain setting."""
        chain = ["anthropic_claude", "ollama"]
        failover_engine.set_fallback_chain("google_gemini", chain)

        assert failover_engine._fallback_chains["google_gemini"] == chain

    @pytest.mark.asyncio
    async def test_handle_rate_limit_failure(self, failover_engine, mock_registry):
        """Test handling rate limit failure triggers failover."""
        # Set fallback chain
        failover_engine.set_fallback_chain("google_gemini", ["anthropic_claude"])

        # Mock provider availability
        mock_registry.get_available_providers = AsyncMock(return_value=[
            "google_gemini", "anthropic_claude"
        ])

        # Handle failure
        new_provider = await failover_engine.handle_failure(
            job_id="job-123",
            current_provider="google_gemini",
            error=Exception("Rate limit"),
            stage="extraction",
            progress=0.5,
        )

        # Should switch to fallback
        assert new_provider == "anthropic_claude"

    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers_failover(self, failover_engine):
        """Test circuit breaker open triggers immediate failover."""
        # Add a circuit breaker in open state
        from core.resilience import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_provider")
        cb._state = CircuitState.OPEN  # Manually set to open
        failover_engine.circuit_breakers["test_provider"] = cb

        # Should detect circuit breaker open failure
        result = await failover_engine.handle_failure(
            job_id="job-123",
            current_provider="test_provider",
            error=Exception("Circuit open"),
            stage="extraction",
            progress=0.3,
        )

        # Should return a fallback provider
        assert result is not None

    def test_migration_history(self, failover_engine):
        """Test migration history tracking."""
        # Record a migration
        migration = MigrationRecord(
            job_id="job-123",
            from_provider="google_gemini",
            to_provider="anthropic_claude",
            failure_type=FailureType.RATE_LIMIT,
            success=True,
        )
        failover_engine.migration_history.append(migration)

        # Get history
        history = failover_engine.get_migration_history("job-123")

        assert len(history) == 1
        assert history[0].from_provider == "google_gemini"

    def test_failure_stats(self, failover_engine):
        """Test failure statistics."""
        # Record some failures
        for i in range(3):
            event = FailureEvent(
                provider="test_provider",
                failure_type=FailureType.RATE_LIMIT,
            )
            failover_engine._record_failure("test_provider", event)

        event = FailureEvent(
            provider="test_provider",
            failure_type=FailureType.LATENCY_SPIKE,
        )
        failover_engine._record_failure("test_provider", event)

        # Get stats
        stats = failover_engine.get_failure_stats()

        assert "test_provider" in stats
        assert stats["test_provider"]["total"] == 4
        assert stats["test_provider"]["rate_limit"] == 3


class TestCheckpoint:
    """Test checkpoint serialization."""

    def test_checkpoint_to_dict(self):
        """Test checkpoint serialization to dict."""
        checkpoint = Checkpoint(
            job_id="job-123",
            stage=CheckpointStage.EXTRACTION,
            progress=0.5,
            samples_generated=100,
            provider_context=ProviderContext(
                provider_name="google_gemini",
                model="gemini-pro",
                api_key_hash="abc123",
            ),
        )

        data = checkpoint.to_dict()

        assert data["job_id"] == "job-123"
        assert data["stage"] == "extraction"
        assert data["progress"] == 0.5
        assert data["provider_context"]["provider_name"] == "google_gemini"

    def test_checkpoint_from_dict(self):
        """Test checkpoint deserialization."""
        data = {
            "checkpoint_id": "cp-123",
            "job_id": "job-123",
            "stage": "extraction",
            "progress": 0.5,
            "samples_generated": 100,
            "provider_context": {
                "provider_name": "google_gemini",
                "model": "gemini-pro",
                "api_key_hash": "abc123",
                "capabilities": [],
                "latency_ms": 0.0,
                "cost_accumulated": 0.0,
            },
            "extracted_content": [],
            "filtered_samples": [],
            "constructed_samples": [],
            "metadata": {},
            "created_at": "2024-01-01T00:00:00",
            "version": 1,
        }

        checkpoint = Checkpoint.from_dict(data)

        assert checkpoint.job_id == "job-123"
        assert checkpoint.stage == CheckpointStage.EXTRACTION
        assert checkpoint.provider_context.provider_name == "google_gemini"


class TestProviderHotSwitcher:
    """Test manual provider switching."""

    @pytest.fixture
    def mock_failover_engine(self):
        """Create mock failover engine."""
        engine = Mock()
        engine._get_available_providers = AsyncMock(return_value=[
            "google_gemini", "anthropic_claude"
        ])
        return engine

    @pytest.fixture
    def mock_router(self):
        """Create mock provider router."""
        router = Mock()
        router.set_active_provider = AsyncMock()
        return router

    @pytest.mark.asyncio
    async def test_switch_provider(self, mock_failover_engine, mock_router):
        """Test manual provider switch."""
        switcher = ProviderHotSwitcher(mock_failover_engine, mock_router)

        result = await switcher.switch_provider(
            job_id="job-123",
            new_provider="anthropic_claude",
        )

        assert result is True
        mock_router.set_active_provider.assert_called_once_with("anthropic_claude")

    @pytest.mark.asyncio
    async def test_switch_to_unavailable_provider(self, mock_failover_engine, mock_router):
        """Test switching to unavailable provider fails."""
        mock_failover_engine._get_available_providers = AsyncMock(return_value=[
            "google_gemini"  # Only gemini available
        ])

        switcher = ProviderHotSwitcher(mock_failover_engine, mock_router)

        result = await switcher.switch_provider(
            job_id="job-123",
            new_provider="anthropic_claude",
        )

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])