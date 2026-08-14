"""
Enterprise Reliability Patterns

Circuit breakers, retry policies, bulkhead isolation,
and resilience patterns for distributed AI infrastructure.
"""

from typing import Optional, Callable, Any, Dict, List, TypeVar, Generic, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import asyncio
import logging
import random
import time

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
    RetryCallState,
)
from tenacity import retry as async_retry


logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject all
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 2          # Successes to close from half-open
    timeout_seconds: float = 30.0      # Time before trying half-open
    half_open_max_calls: int = 3       # Max calls in half-open state
    excluded_exceptions: tuple = ()     # Exceptions that don't count


class CircuitBreaker:
    """Enterprise circuit breaker with failure counting and auto-recovery.

    Prevents cascading failures by opening circuit when failure threshold
    is exceeded, and automatically testing recovery after timeout.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state with timeout-based transitions."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed >= self.config.timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
        return self._state

    @property
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        return self.state != CircuitState.OPEN

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics for observability."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' CLOSED after recovery")

    async def record_failure(self, exception: Optional[Exception] = None) -> None:
        """Record a failed call."""
        # Check if exception should be excluded
        if exception and self.config.excluded_exceptions:
            if isinstance(exception, self.config.excluded_exceptions):
                return

        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()
            self._success_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.config.half_open_max_calls:
                    logger.warning(f"Circuit breaker '{self.name}' re-opening after half-open failures")
                    self._state = CircuitState.OPEN

            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' OPEN after {self._failure_count} failures"
                )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        if not self.is_available:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN"
            )

        if self._state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' half-open limit reached"
                    )
                self._half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure(e)
            raise


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different providers/resources."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def get_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        return {name: breaker.get_metrics() for name, breaker in self._breakers.items()}


# Global circuit breaker manager
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get global circuit breaker manager instance."""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager


# ============================================================================
# Retry Policies with Tenacity
# ============================================================================

class RetryPolicy(str, Enum):
    """Predefined retry policies."""
    DEFAULT = "default"           # 3 retries, exponential backoff
    AGGRESSIVE = "aggressive"    # 5 retries, faster backoff
    CONSERVATIVE = "conservative" # 2 retries, longer backoff
    TRANSIENT = "transient"      # 4 retries, jittered


def get_retry_decorator(
    policy: RetryPolicy = RetryPolicy.DEFAULT,
    max_attempts: Optional[int] = None,
    max_wait_seconds: Optional[float] = None
):
    """Get configured retry decorator based on policy.

    Args:
        policy: Predefined retry policy
        max_attempts: Override max attempts
        max_wait_seconds: Override max wait time
    """
    configs = {
        RetryPolicy.DEFAULT: {
            "stop": stop_after_attempt(max_attempts or 3),
            "wait": wait_exponential(multiplier=1, max=max_wait_seconds or 10),
        },
        RetryPolicy.AGGRESSIVE: {
            "stop": stop_after_attempt(max_attempts or 5),
            "wait": wait_exponential(multiplier=0.5, max=max_wait_seconds or 5),
        },
        RetryPolicy.CONSERVATIVE: {
            "stop": stop_after_attempt(max_attempts or 2),
            "wait": wait_exponential(multiplier=2, max=max_wait_seconds or 30),
        },
        RetryPolicy.TRANSIENT: {
            "stop": stop_after_attempt(max_attempts or 4),
            "wait": wait_exponential(multiplier=1, min=1, max=max_wait_seconds or 15),
        },
    }

    return async_retry(
        **configs[policy],
        retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
        retry_error_callback=lambda state: logger.warning(
            f"Retry exhausted after {state.attempt_number} attempts: {state.outcome.exception()}"
        ),
    )


# ============================================================================
# Bulkhead Isolation
# ============================================================================

@dataclass
class BulkheadConfig:
    """Configuration for bulkhead isolation."""
    max_concurrent: int = 10          # Max concurrent calls
    max_queue_size: int = 100         # Max queued calls
    timeout_seconds: float = 30.0     # Queue timeout


class Bulkhead:
    """Async semaphore-based bulkhead for resource isolation.

    Limits concurrent operations and prevents resource exhaustion.
    """

    def __init__(self, name: str, config: Optional[BulkheadConfig] = None):
        self.name = name
        self.config = config or BulkheadConfig()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_count = 0
        self._total_accepted = 0
        self._total_rejected = 0
        self._lock = asyncio.Lock()
        self._created_time = datetime.utcnow()

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get or create semaphore lazily."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        return self._semaphore

    @property
    def available_capacity(self) -> int:
        """Get available concurrent capacity."""
        return max(0, self.config.max_concurrent - self._active_count)

    @property
    def queue_depth(self) -> int:
        """Get approximate queue depth."""
        return self._total_accepted - self._total_rejected - self._active_count

    async def acquire(self) -> bool:
        """Acquire a slot in the bulkhead.

        Returns True if acquired, False if rejected due to capacity.
        """
        if not self._semaphore:
            self._get_semaphore()

        async with self._lock:
            if self._active_count >= self.config.max_concurrent:
                self._total_rejected += 1
                logger.warning(
                    f"Bulkhead '{self.name}' rejected call - "
                    f"active={self._active_count}, limit={self.config.max_concurrent}"
                )
                return False
            self._active_count += 1
            self._total_accepted += 1

        return True

    async def release(self) -> None:
        """Release a slot back to the bulkhead."""
        async with self._lock:
            self._active_count = max(0, self._active_count - 1)

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through bulkhead with automatic acquire/release."""
        if not await self.acquire():
            raise BulkheadRejectedError(
                f"Bulkhead '{self.name}' rejected - capacity exceeded"
            )

        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout_seconds
                )
            else:
                return await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=self.config.timeout_seconds
                )
        finally:
            await self.release()

    def get_metrics(self) -> Dict[str, Any]:
        """Get bulkhead metrics."""
        return {
            "name": self.name,
            "active": self._active_count,
            "max_concurrent": self.config.max_concurrent,
            "available": self.available_capacity,
            "queue_depth": self.queue_depth,
            "total_accepted": self._total_accepted,
            "total_rejected": self._total_rejected,
            "uptime_seconds": (datetime.utcnow() - self._created_time).total_seconds(),
        }


class BulkheadRejectedError(Exception):
    """Raised when bulkhead rejects due to capacity."""
    pass


class BulkheadManager:
    """Manages multiple bulkheads for different providers/resources."""

    def __init__(self):
        self._bulkheads: Dict[str, Bulkhead] = {}
        self._lock = asyncio.Lock()

    async def get_bulkhead(
        self,
        name: str,
        config: Optional[BulkheadConfig] = None
    ) -> Bulkhead:
        """Get or create a bulkhead."""
        async with self._lock:
            if name not in self._bulkheads:
                self._bulkheads[name] = Bulkhead(name, config)
            return self._bulkheads[name]

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all bulkheads."""
        return {name: bh.get_metrics() for name, bh in self._bulkheads.items()}


# Global bulkhead manager
_bulkhead_manager: Optional[BulkheadManager] = None


def get_bulkhead_manager() -> BulkheadManager:
    """Get global bulkhead manager instance."""
    global _bulkhead_manager
    if _bulkhead_manager is None:
        _bulkhead_manager = BulkheadManager()
    return _bulkhead_manager


# ============================================================================
# Connection Pooling
# ============================================================================

@dataclass
class PoolConfig:
    """Configuration for connection pool."""
    min_size: int = 1
    max_size: int = 10
    max_idle_time_seconds: float = 300.0
    checkout_timeout_seconds: float = 10.0
    health_check_interval_seconds: float = 60.0


class PooledConnection(Generic[T]):
    """Wrapper for pooled connections with health checks."""

    def __init__(
        self,
        connection: T,
        pool: "ConnectionPool",
        created_at: datetime
    ):
        self._connection = connection
        self._pool = pool
        self._created_at = created_at
        self._last_used = datetime.utcnow()
        self._is_valid = True

    @property
    def connection(self) -> T:
        return self._connection

    async def check_health(self) -> bool:
        """Check if connection is still healthy."""
        if not self._is_valid:
            return False
        # Check idle time
        idle_time = (datetime.utcnow() - self._last_used).total_seconds()
        if idle_time > self._pool.config.max_idle_time_seconds:
            self._is_valid = False
        return self._is_valid

    async def release(self) -> None:
        """Release connection back to pool."""
        self._last_used = datetime.utcnow()
        await self._pool._return_connection(self)

    async def close(self) -> None:
        """Close connection and remove from pool."""
        self._is_valid = False
        await self._pool._remove_connection(self)


class ConnectionPool(Generic[T]):
    """Generic async connection pool with lifecycle management."""

    def __init__(
        self,
        name: str,
        factory: Callable[[], T],
        config: Optional[PoolConfig] = None
    ):
        self.name = name
        self.factory = factory
        self.config = config or PoolConfig()
        self._pool: List[PooledConnection[T]] = []
        self._lock = asyncio.Lock()
        self._in_use: int = 0
        self._total_created = 0
        self._total_failed = 0

    @property
    def available_count(self) -> int:
        return len(self._pool)

    @property
    def in_use_count(self) -> int:
        return self._in_use

    @property
    def total_count(self) -> int:
        return self._total_created

    async def acquire(self) -> PooledConnection[T]:
        """Acquire a connection from the pool."""
        async with self._lock:
            # Try to get from pool
            while self._pool:
                conn = self._pool.pop()
                if await conn.check_health():
                    self._in_use += 1
                    return conn
                self._total_failed += 1

            # Create new if under limit
            if self._total_created < self.config.max_size:
                try:
                    new_conn = self.factory()
                    pooled = PooledConnection(new_conn, self, datetime.utcnow())
                    self._total_created += 1
                    self._in_use += 1
                    return pooled
                except Exception as e:
                    logger.error(f"Failed to create connection in pool '{self.name}': {e}")
                    self._total_failed += 1
                    raise

            # Wait for available connection
            raise PoolExhaustedError(
                f"Pool '{self.name}' exhausted: {self.config.max_size} connections in use"
            )

    async def _return_connection(self, conn: PooledConnection) -> None:
        """Return connection to pool."""
        async with self._lock:
            self._in_use = max(0, self._in_use - 1)
            if conn._is_valid and len(self._pool) < self.config.max_size:
                self._pool.append(conn)
            else:
                self._total_failed += 1

    async def _remove_connection(self, conn: PooledConnection) -> None:
        """Remove connection from pool."""
        async with self._lock:
            if conn in self._pool:
                self._pool.remove(conn)
            self._in_use = max(0, self._in_use - 1)

    def get_metrics(self) -> Dict[str, Any]:
        """Get pool metrics."""
        return {
            "name": self.name,
            "available": self.available_count,
            "in_use": self.in_use_count,
            "total": self.total_count,
            "max_size": self.config.max_size,
            "total_failed": self._total_failed,
        }

    async def drain(self) -> None:
        """Drain all connections from pool."""
        async with self._lock:
            self._pool.clear()


class PoolExhaustedError(Exception):
    """Raised when connection pool is exhausted."""
    pass


# ============================================================================
# Typed Provider Interface
# ============================================================================

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProviderAdapterProtocol(Protocol):
    """Protocol for provider adapters with strict typing."""

    @property
    def provider_name(self) -> str:
        """Unique provider identifier."""
        ...

    @property
    def supports_embeddings(self) -> bool:
        """Whether provider supports embeddings."""
        ...

    @property
    def embedding_dimension(self) -> int:
        """Dimension of embeddings produced."""
        ...

    async def complete(self, request: "ProviderRequest") -> "ProviderResponse":
        """Send completion request."""
        ...

    async def stream_complete(
        self,
        request: "ProviderRequest"
    ) -> AsyncGenerator["StreamingChunk", None]:
        """Stream completion response."""
        ...


# Re-export for convenience
__all__ = [
    # Circuit Breaker
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerManager",
    "get_circuit_breaker_manager",

    # Retry Policies
    "RetryPolicy",
    "get_retry_decorator",

    # Bulkhead
    "BulkheadConfig",
    "Bulkhead",
    "BulkheadRejectedError",
    "BulkheadManager",
    "get_bulkhead_manager",

    # Pooling
    "PoolConfig",
    "PooledConnection",
    "ConnectionPool",
    "PoolExhaustedError",

    # Protocols
    "ProviderAdapterProtocol",
]