"""Provider health check framework for enterprise reliability."""
import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import uuid

from core.config import Settings

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealthCheckResult:
    """Result of a provider health check."""
    provider: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    capabilities: Dict[str, bool] = field(default_factory=dict)
    quota_remaining: Optional[int] = None
    consecutive_failures: int = 0


@dataclass
class ProviderMetrics:
    """Provider performance metrics."""
    provider: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    last_request_at: Optional[datetime] = None
    fallback_count: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests


class HealthChecker(ABC):
    """Abstract base class for health checkers."""

    @abstractmethod
    async def check(self) -> ProviderHealthCheckResult:
        """Run health check."""
        pass

    @abstractmethod
    async def check_capabilities(self) -> Dict[str, bool]:
        """Check provider capabilities."""
        pass


class ProviderHealthMonitor:
    """
    Enterprise-grade provider health monitoring.

    Features:
    - Periodic health checks
    - Latency tracking
    - Circuit breaker state management
    - Quota monitoring
    - Fallback tracking
    """

    def __init__(
        self,
        settings: Settings,
        check_interval_seconds: int = 60,
        failure_threshold: int = 3,
        recovery_timeout_seconds: int = 300,
    ):
        self._settings = settings
        self._check_interval = check_interval_seconds
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_seconds

        # Health state
        self._health_status: Dict[str, ProviderHealthCheckResult] = {}
        self._metrics: Dict[str, ProviderMetrics] = {}
        self._circuit_breaker_state: Dict[str, str] = {}  # closed, open, half-open
        self._consecutive_failures: Dict[str, int] = {}
        self._last_check: Dict[str, datetime] = {}

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start health monitoring."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Provider health monitoring started")

    async def stop(self) -> None:
        """Stop health monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Provider health monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry

    async def _run_health_checks(self) -> None:
        """Run health checks for all configured providers."""
        for provider_name in self._settings.provider_priority:
            try:
                result = await self._check_provider(provider_name)
                self._update_health_status(provider_name, result)
            except Exception as e:
                logger.warning(f"Health check failed for {provider_name}: {e}")

    async def _check_provider(self, provider: str) -> ProviderHealthCheckResult:
        """Check health of a single provider."""
        # This would call the actual provider
        # For now, return unknown status
        return ProviderHealthCheckResult(
            provider=provider,
            status=HealthStatus.UNKNOWN,
            error="Health check not implemented"
        )

    def _update_health_status(
        self,
        provider: str,
        result: ProviderHealthCheckResult
    ) -> None:
        """Update health status and handle circuit breaker."""
        self._health_status[provider] = result
        self._last_check[provider] = datetime.utcnow()

        # Update circuit breaker based on result
        if result.status == HealthStatus.UNHEALTHY:
            failures = self._consecutive_failures.get(provider, 0) + 1
            self._consecutive_failures[provider] = failures

            if failures >= self._failure_threshold:
                self._circuit_breaker_state[provider] = "open"
                logger.warning(f"Circuit breaker opened for {provider}")
        else:
            # Reset failures on success
            self._consecutive_failures[provider] = 0

            # Check if we can transition from open to half-open
            if self._circuit_breaker_state.get(provider) == "open":
                last_failure = self._last_check.get(provider)
                if last_failure and (datetime.utcnow() - last_failure).seconds > self._recovery_timeout:
                    self._circuit_breaker_state[provider] = "half-open"

    def get_health_status(self, provider: Optional[str] = None) -> Dict[str, ProviderHealthCheckResult]:
        """Get health status for provider(s)."""
        if provider:
            return {provider: self._health_status.get(provider, ProviderHealthCheckResult(
                provider=provider,
                status=HealthStatus.UNKNOWN
            ))}
        return self._health_status.copy()

    def get_metrics(self, provider: Optional[str] = None) -> Dict[str, ProviderMetrics]:
        """Get metrics for provider(s)."""
        if provider:
            return {provider: self._metrics.get(provider, ProviderMetrics(provider=provider))}
        return self._metrics.copy()

    def get_circuit_breaker_state(self, provider: Optional[str] = None) -> Dict[str, str]:
        """Get circuit breaker state for provider(s)."""
        if provider:
            return {provider: self._circuit_breaker_state.get(provider, "closed")}
        return self._circuit_breaker_state.copy()

    def record_request(
        self,
        provider: str,
        success: bool,
        latency_ms: float,
        cost_usd: float
    ) -> None:
        """Record a request for metrics."""
        if provider not in self._metrics:
            self._metrics[provider] = ProviderMetrics(provider=provider)

        metrics = self._metrics[provider]
        metrics.total_requests += 1

        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1

        metrics.total_latency_ms += latency_ms
        metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
        metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
        metrics.total_cost_usd += cost_usd
        metrics.last_request_at = datetime.utcnow()

    def record_fallback(self, from_provider: str, to_provider: str) -> None:
        """Record a fallback event."""
        from_metrics = self._metrics.get(from_provider)
        if from_metrics:
            from_metrics.fallback_count += 1
        logger.info(f"Fallback: {from_provider} -> {to_provider}")


class HealthCheckEndpoints:
    """FastAPI endpoints for health checks."""

    def __init__(self, health_monitor: ProviderHealthMonitor):
        self._monitor = health_monitor

    async def liveness(self) -> Dict[str, str]:
        """Liveness check."""
        return {"status": "alive"}

    async def readiness(self) -> Dict[str, Any]:
        """Readiness check."""
        health = self._monitor.get_health_status()

        # Check if any provider is available
        has_available = any(
            s.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
            for s in health.values()
        )

        return {
            "status": "ready" if has_available else "not_ready",
            "providers": {
                provider: {
                    "status": result.status.value,
                    "latency_ms": result.latency_ms,
                    "error": result.error,
                }
                for provider, result in health.items()
            },
            "circuit_breakers": self._monitor.get_circuit_breaker_state(),
        }

    async def metrics(self) -> Dict[str, Any]:
        """Provider metrics."""
        return {
            "metrics": {
                provider: {
                    "total_requests": m.total_requests,
                    "success_rate": m.success_rate,
                    "avg_latency_ms": m.avg_latency_ms,
                    "fallback_count": m.fallback_count,
                }
                for provider, m in self._monitor.get_metrics().items()
            }
        }