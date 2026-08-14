"""Tests for provider health monitoring framework."""
import pytest
import asyncio
from datetime import datetime

from core.health import (
    ProviderHealthMonitor,
    ProviderHealthCheckResult,
    ProviderMetrics,
    HealthStatus,
    HealthCheckEndpoints,
)


class TestProviderHealthMonitor:
    """Test provider health monitoring."""

    @pytest.fixture
    def settings(self) -> 'Settings':
        """Create test settings."""
        from core.config import Settings
        return Settings(
            provider_priority=["google_gemini", "nvidia_nim", "anthropic_claude"],
            redis_url="redis://localhost:6379/0",
        )

    @pytest.fixture
    def monitor(self, settings: 'Settings') -> ProviderHealthMonitor:
        """Create health monitor."""
        return ProviderHealthMonitor(settings)

    @pytest.mark.asyncio
    async def test_start_stop(self, monitor: ProviderHealthMonitor) -> None:
        """Test starting and stopping monitor."""
        await monitor.start()
        assert monitor._running is True

        await monitor.stop()
        assert monitor._running is False

    def test_initial_state(self, monitor: ProviderHealthMonitor) -> None:
        """Test initial state."""
        status = monitor.get_health_status()
        assert status == {}

        metrics = monitor.get_metrics()
        assert metrics == {}

    @pytest.mark.asyncio
    async def test_update_health_status(self, monitor: ProviderHealthMonitor) -> None:
        """Test updating health status."""
        result = ProviderHealthCheckResult(
            provider="google_gemini",
            status=HealthStatus.HEALTHY,
            latency_ms=150.0
        )

        monitor._update_health_status("google_gemini", result)

        status = monitor.get_health_status()
        assert "google_gemini" in status
        assert status["google_gemini"].status == HealthStatus.HEALTHY

    def test_circuit_breaker_state(self, monitor: ProviderHealthMonitor) -> None:
        """Test circuit breaker state tracking."""
        # Initial state should be closed
        state = monitor.get_circuit_breaker_state()
        # No providers yet

        # After failures, should be open
        monitor._circuit_breaker_state["test"] = "open"
        state = monitor.get_circuit_breaker_state()
        assert state["test"] == "open"

    def test_record_request(self, monitor: ProviderHealthMonitor) -> None:
        """Test recording request metrics."""
        monitor.record_request(
            provider="google_gemini",
            success=True,
            latency_ms=150.0,
            cost_usd=0.01
        )

        metrics = monitor.get_metrics()
        assert "google_gemini" in metrics
        assert metrics["google_gemini"].total_requests == 1
        assert metrics["google_gemini"].successful_requests == 1
        assert metrics["google_gemini"].total_cost_usd == 0.01

    def test_record_fallback(self, monitor: ProviderHealthMonitor) -> None:
        """Test recording fallback events."""
        monitor.record_request("google_gemini", True, 100.0, 0.01)
        monitor.record_fallback("google_gemini", "anthropic_claude")

        metrics = monitor.get_metrics()
        assert metrics["google_gemini"].fallback_count == 1


class TestProviderMetrics:
    """Test provider metrics calculations."""

    def test_success_rate(self) -> None:
        """Test success rate calculation."""
        metrics = ProviderMetrics(provider="test")
        metrics.total_requests = 10
        metrics.successful_requests = 8

        assert metrics.success_rate == 0.8

    def test_success_rate_zero_requests(self) -> None:
        """Test success rate with no requests."""
        metrics = ProviderMetrics(provider="test")
        assert metrics.success_rate == 0.0

    def test_avg_latency(self) -> None:
        """Test average latency calculation."""
        metrics = ProviderMetrics(provider="test")
        metrics.total_requests = 3
        metrics.total_latency_ms = 300.0

        assert metrics.avg_latency_ms == 100.0


class TestHealthCheckEndpoints:
    """Test health check endpoints."""

    @pytest.fixture
    def endpoints(self, mock_settings: 'Settings') -> HealthCheckEndpoints:
        """Create health check endpoints."""
        monitor = ProviderHealthMonitor(mock_settings)
        return HealthCheckEndpoints(monitor)

    @pytest.mark.asyncio
    async def test_liveness(self, endpoints: HealthCheckEndpoints) -> None:
        """Test liveness endpoint."""
        result = await endpoints.liveness()
        assert result["status"] == "alive"

    @pytest.mark.asyncio
    async def test_readiness_no_providers(self, endpoints: HealthCheckEndpoints) -> None:
        """Test readiness with no providers."""
        result = await endpoints.readiness()
        assert result["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_metrics_empty(self, endpoints: HealthCheckEndpoints) -> None:
        """Test metrics endpoint."""
        result = await endpoints.metrics()
        assert "metrics" in result