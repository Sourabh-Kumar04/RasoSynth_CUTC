"""
Provider Hot-Switching & Automatic Failover System

Enables dynamic provider switching during active job execution,
automatic failover on errors, and intelligent provider migration.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4

from core.resilience import CircuitBreaker, CircuitState, CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures that trigger failover."""
    RATE_LIMIT = "rate_limit"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTH_FAILURE = "auth_failure"
    PROVIDER_DOWN = "provider_down"
    LATENCY_SPIKE = "latency_spike"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    TIMEOUT = "timeout"
    STREAMING_DISCONNECT = "streaming_disconnect"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class FailureEvent:
    """Record of a failure event."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    provider: str = ""
    failure_type: FailureType = FailureType.UNKNOWN_ERROR
    error_message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    latency_ms: float = 0.0


@dataclass
class MigrationRecord:
    """Record of provider migration."""
    migration_id: str = field(default_factory=lambda: str(uuid4()))
    job_id: str = ""
    from_provider: str = ""
    to_provider: str = ""
    failure_type: Optional[FailureType] = None
    checkpoint_id: Optional[str] = None
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class FailureDetectionService:
    """
    Detects various failure types that trigger failover.
    """

    def __init__(self):
        self.latency_threshold_ms = 5000  # 5 seconds
        self.rate_limit_status_codes = {429, 503}
        self.auth_failure_codes = {401, 403}

    def detect_failure(
        self,
        provider: str,
        error: Exception,
        latency_ms: float = 0.0,
        status_code: Optional[int] = None,
    ) -> Optional[FailureType]:
        """Analyze error and determine failure type."""

        error_msg = str(error).lower()

        # Rate limit detection
        if status_code == 429 or "rate limit" in error_msg or "too many requests" in error_msg:
            return FailureType.RATE_LIMIT

        # Quota exhaustion
        if "quota" in error_msg or "insufficient credits" in error_msg or "billing" in error_msg:
            return FailureType.QUOTA_EXHAUSTED

        # Authentication failure
        if status_code in self.auth_failure_codes or "unauthorized" in error_msg or "invalid api key" in error_msg:
            return FailureType.AUTH_FAILURE

        # Provider down
        if "service unavailable" in error_msg or "provider unavailable" in error_msg or "connection refused" in error_msg:
            return FailureType.PROVIDER_DOWN

        # Timeout
        if "timeout" in error_msg or "timed out" in error_msg:
            return FailureType.TIMEOUT

        # Latency spike
        if latency_ms > self.latency_threshold_ms:
            return FailureType.LATENCY_SPIKE

        return FailureType.UNKNOWN_ERROR


class AutomaticFailoverEngine:
    """
    Automatic provider failover with intelligent retry and recovery.

    Features:
    - Automatic failure detection
    - Smart provider selection for fallback
    - Checkpoint preservation before migration
    - Adaptive retry policies
    """

    def __init__(
        self,
        provider_registry,  # ProviderRegistry
        checkpoint_manager,  # CheckpointManager
        config: Optional[Dict] = None,
    ):
        self.providers = provider_registry
        self.checkpoint_manager = checkpoint_manager
        self.config = config or {}

        self.detection_service = FailureDetectionService()
        self.failure_history: Dict[str, List[FailureEvent]] = {}
        self.migration_history: List[MigrationRecord] = []

        # Circuit breakers per provider
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Fallback chains
        self._fallback_chains: Dict[str, List[str]] = {}

        # Callbacks for state changes
        self.on_failover_callbacks: List[Callable] = []
        self.on_checkpoint_callbacks: List[Callable] = []

    def set_fallback_chain(self, primary: str, fallback_chain: List[str]) -> None:
        """Set fallback chain for a primary provider."""
        self._fallback_chains[primary] = fallback_chain
        logger.info(f"Set fallback chain for {primary}: {fallback_chain}")

    def register_failover_callback(self, callback: Callable) -> None:
        """Register callback for failover events."""
        self.on_failover_callbacks.append(callback)

    def register_checkpoint_callback(self, callback: Callable) -> None:
        """Register callback for checkpoint events."""
        self.on_checkpoint_callbacks.append(callback)

    async def handle_failure(
        self,
        job_id: str,
        current_provider: str,
        error: Exception,
        stage: str,
        progress: float,
        extracted_content: List = None,
        filtered_samples: List = None,
        constructed_samples: List = None,
        latency_ms: float = 0.0,
        status_code: Optional[int] = None,
    ) -> Optional[str]:
        """
        Handle failure and determine failover action.

        Returns: new provider name if failover happened, None if should retry
        """

        # Detect failure type
        failure_type = self.detection_service.detect_failure(
            current_provider, error, latency_ms, status_code
        )

        # Record failure
        event = FailureEvent(
            provider=current_provider,
            failure_type=failure_type,
            error_message=str(error),
            latency_ms=latency_ms,
        )
        self._record_failure(current_provider, event)

        # Get circuit breaker state
        cb = self.circuit_breakers.get(current_provider)
        if cb and cb.state == CircuitState.OPEN:
            failure_type = FailureType.CIRCUIT_BREAKER_OPEN

        # Determine action based on failure type
        if failure_type in [FailureType.RATE_LIMIT, FailureType.QUOTA_EXHAUSTED]:
            # These require provider switch
            new_provider = await self._select_fallback_provider(current_provider, job_id)
            if new_provider:
                # Create checkpoint before migration
                checkpoint_id = await self._create_checkpoint_before_migration(
                    job_id, current_provider, new_provider,
                    stage, progress,
                    extracted_content, filtered_samples, constructed_samples,
                )

                # Record migration
                await self._record_migration(
                    job_id, current_provider, new_provider, failure_type, checkpoint_id
                )

                # Trigger callbacks
                for callback in self.on_failover_callbacks:
                    try:
                        await callback(job_id, current_provider, new_provider, failure_type)
                    except Exception as e:
                        logger.error(f"Failover callback error: {e}")

                logger.info(f"Failover: {current_provider} -> {new_provider} (job: {job_id})")
                return new_provider

        elif failure_type == FailureType.CIRCUIT_BREAKER_OPEN:
            # Circuit breaker is open, switch immediately
            new_provider = await self._select_fallback_provider(current_provider, job_id)
            if new_provider:
                await self._record_migration(
                    job_id, current_provider, new_provider, failure_type, None
                )
                return new_provider

        elif failure_type == FailureType.LATENCY_SPIKE:
            # Could be temporary, try once more with backoff
            return None  # Let retry handler deal with it

        # For other failures, try fallback
        new_provider = await self._select_fallback_provider(current_provider, job_id)
        if new_provider and new_provider != current_provider:
            return new_provider

        return None  # No fallback available

    async def _select_fallback_provider(
        self,
        current_provider: str,
        job_id: str,
    ) -> Optional[str]:
        """Select best fallback provider."""
        # Check explicit fallback chain
        chain = self._fallback_chains.get(current_provider)
        if chain:
            for provider in chain:
                if await self._is_provider_available(provider):
                    return provider

        # Get all available providers from registry
        available = await self._get_available_providers()

        # Filter out current provider and return best option
        for provider in available:
            if provider != current_provider:
                return provider

        return None

    async def _is_provider_available(self, provider: str) -> bool:
        """Check if provider is available (circuit breaker not open)."""
        cb = self.circuit_breakers.get(provider)
        if cb:
            return cb.is_available
        return True  # Assume available if no circuit breaker

    async def _get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        # This would integrate with the provider registry
        # For now, return known providers
        return [
            "google_gemini", "nvidia_nim", "anthropic_claude",
            "openai", "huggingface", "xai", "ollama", "deepseek"
        ]

    async def _create_checkpoint_before_migration(
        self,
        job_id: str,
        from_provider: str,
        to_provider: str,
        stage: str,
        progress: float,
        extracted_content: List = None,
        filtered_samples: List = None,
        constructed_samples: List = None,
    ) -> Optional[str]:
        """Create checkpoint before provider migration."""
        try:
            from core.orchestrator.checkpoints import CheckpointStage, ProviderContext

            provider_context = ProviderContext(
                provider_name=to_provider,
                model="",  # Would be set based on provider
                api_key_hash="",  # Security: don't store actual keys
                capabilities=[],
            )

            checkpoint = await self.checkpoint_manager.create_checkpoint(
                job_id=job_id,
                stage=CheckpointStage(stage),
                progress=progress,
                provider_context=provider_context,
                extracted_content=extracted_content or [],
                filtered_samples=filtered_samples or [],
                constructed_samples=constructed_samples or [],
                metadata={
                    "migration": True,
                    "from_provider": from_provider,
                    "to_provider": to_provider,
                },
            )

            # Trigger callbacks
            for callback in self.on_checkpoint_callbacks:
                try:
                    await callback(job_id, checkpoint.checkpoint_id)
                except Exception as e:
                    logger.error(f"Checkpoint callback error: {e}")

            return checkpoint.checkpoint_id

        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return None

    async def _record_migration(
        self,
        job_id: str,
        from_provider: str,
        to_provider: str,
        failure_type: FailureType,
        checkpoint_id: Optional[str],
    ) -> None:
        """Record provider migration."""
        record = MigrationRecord(
            job_id=job_id,
            from_provider=from_provider,
            to_provider=to_provider,
            failure_type=failure_type,
            checkpoint_id=checkpoint_id,
        )
        self.migration_history.append(record)

    def _record_failure(self, provider: str, event: FailureEvent) -> None:
        """Record failure for analytics."""
        if provider not in self.failure_history:
            self.failure_history[provider] = []
        self.failure_history[provider].append(event)

        # Update circuit breaker
        if provider not in self.circuit_breakers:
            self.circuit_breakers[provider] = CircuitBreaker(provider)

        asyncio.create_task(
            self.circuit_breakers[provider].record_failure(event.error_message)
        )

    def get_migration_history(self, job_id: Optional[str] = None) -> List[MigrationRecord]:
        """Get migration history."""
        if job_id:
            return [m for m in self.migration_history if m.job_id == job_id]
        return self.migration_history

    def get_failure_stats(self) -> Dict[str, Dict[str, int]]:
        """Get failure statistics per provider."""
        stats = {}
        for provider, events in self.failure_history.items():
            stats[provider] = {
                "total": len(events),
                "rate_limit": sum(1 for e in events if e.failure_type == FailureType.RATE_LIMIT),
                "quota": sum(1 for e in events if e.failure_type == FailureType.QUOTA_EXHAUSTED),
                "auth": sum(1 for e in events if e.failure_type == FailureType.AUTH_FAILURE),
                "latency": sum(1 for e in events if e.failure_type == FailureType.LATENCY_SPIKE),
            }
        return stats


class ProviderHotSwitcher:
    """
    Manual provider hot-switching during active job execution.

    Allows users to:
    - Switch providers while jobs are running
    - Update API keys during execution
    - Reorder fallback chains
    - Trigger manual migration
    """

    def __init__(
        self,
        failover_engine: AutomaticFailoverEngine,
        provider_router,  # ProviderRouter
    ):
        self.failover_engine = failover_engine
        self.provider_router = provider_router

    async def switch_provider(
        self,
        job_id: str,
        new_provider: str,
        create_checkpoint: bool = True,
    ) -> bool:
        """Manually switch to a different provider."""

        # Validate provider exists
        available = await self.failover_engine._get_available_providers()
        if new_provider not in available:
            logger.error(f"Provider {new_provider} not available")
            return False

        try:
            # Update router's active provider
            if hasattr(self.provider_router, 'set_active_provider'):
                await self.provider_router.set_active_provider(new_provider)

            # Create checkpoint if requested
            if create_checkpoint:
                from core.orchestrator.checkpoints import CheckpointStage
                # Would get current state and create checkpoint
                logger.info(f"Manual switch: {job_id} to {new_provider}")

            return True

        except Exception as e:
            logger.error(f"Provider switch failed: {e}")
            return False

    async def update_api_key(
        self,
        provider: str,
        new_api_key: str,
    ) -> bool:
        """Update API key for provider during runtime."""

        try:
            # Update provider config
            if hasattr(self.provider_router, 'update_provider_key'):
                await self.provider_router.update_provider_key(provider, new_api_key)

            logger.info(f"API key updated for {provider}")
            return True

        except Exception as e:
            logger.error(f"API key update failed: {e}")
            return False

    async def reorder_fallback_chain(
        self,
        primary_provider: str,
        new_chain: List[str],
    ) -> None:
        """Reorder fallback chain for a provider."""

        self.failover_engine.set_fallback_chain(primary_provider, new_chain)
        logger.info(f"Fallback chain updated for {primary_provider}: {new_chain}")