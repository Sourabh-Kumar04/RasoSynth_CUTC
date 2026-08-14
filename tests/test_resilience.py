"""
Tests for Enterprise Reliability Patterns

Circuit breakers, retry policies, bulkhead isolation,
and resilience patterns.
"""

import pytest
import asyncio
from datetime import datetime
from typing import List

# Import reliability patterns
import sys
sys.path.insert(0, str(__file__).rsplit('/tests/', 1)[0])

from core.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    Bulkhead,
    BulkheadConfig,
    BulkheadRejectedError,
    RetryPolicy,
    get_retry_decorator,
    PoolConfig,
    ConnectionPool,
    PooledConnection,
)


# ============================================================================
# Circuit Breaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state_is_closed(self):
        """Circuit starts in CLOSED state."""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available

    def test_opens_after_failure_threshold(self):
        """Circuit opens after failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        async def fail():
            raise ValueError("fail")

        # Record failures
        for _ in range(3):
            asyncio.run(cb.record_failure(ValueError("fail")))

        assert cb.state == CircuitState.OPEN
        assert not cb.is_available

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Circuit transitions to HALF_OPEN after timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.1)
        cb = CircuitBreaker("test", config)

        # Open the circuit
        await cb.record_failure(ValueError("fail"))
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Should transition to HALF_OPEN on next check
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.is_available

    @pytest.mark.asyncio
    async def test_closes_after_success_threshold(self):
        """Circuit closes after success threshold in half-open."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            timeout_seconds=0.1
        )
        cb = CircuitBreaker("test", config)

        # Open then transition to half-open
        await cb.record_failure(ValueError("fail"))
        await asyncio.sleep(0.15)
        _ = cb.state  # Trigger transition

        assert cb.state == CircuitState.HALF_OPEN

        # Record successes
        await cb.record_success()
        await cb.record_success()

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_call_through_breaker(self):
        """Successful calls pass through, failures recorded."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        async def success():
            return "success"

        result = await cb.call(success)
        assert result == "success"
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_call_rejected_when_open(self):
        """Calls rejected when circuit is open."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout_seconds=1)
        cb = CircuitBreaker("test", config)

        await cb.record_failure(ValueError("fail"))

        async def operation():
            return "done"

        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(operation)

    def test_excluded_exceptions(self):
        """Excluded exceptions don't count toward failures."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            excluded_exceptions=(ValueError,)
        )
        cb = CircuitBreaker("test", config)

        asyncio.run(cb.record_failure(ValueError("excluded")))
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_get_metrics(self):
        """Circuit breaker provides metrics."""
        cb = CircuitBreaker("test")
        metrics = cb.get_metrics()

        assert "name" in metrics
        assert "state" in metrics
        assert "failure_count" in metrics
        assert metrics["name"] == "test"


# ============================================================================
# Bulkhead Tests
# ============================================================================

class TestBulkhead:
    """Test bulkhead isolation functionality."""

    def test_initial_available_capacity(self):
        """Bulkhead reports correct available capacity."""
        config = BulkheadConfig(max_concurrent=5)
        bh = Bulkhead("test", config)

        assert bh.available_capacity == 5

    @pytest.mark.asyncio
    async def test_acquire_releases_slot(self):
        """Acquired slots are released."""
        config = BulkheadConfig(max_concurrent=2)
        bh = Bulkhead("test", config)

        acquired = await bh.acquire()
        assert acquired
        assert bh.available_capacity == 1

        await bh.release()
        assert bh.available_capacity == 2

    @pytest.mark.asyncio
    async def test_rejects_when_full(self):
        """Bulkhead rejects when at capacity."""
        config = BulkheadConfig(max_concurrent=1)
        bh = Bulkhead("test", config)

        await bh.acquire()
        assert not await bh.acquire()

    @pytest.mark.asyncio
    async def test_execute_with_semaphore(self):
        """Execute wraps function with semaphore control."""
        config = BulkheadConfig(max_concurrent=2)
        bh = Bulkhead("test", config)

        async def operation():
            await asyncio.sleep(0.01)
            return "done"

        result = await bh.execute(operation)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_reject_error_on_capacity(self):
        """Rejection raises BulkheadRejectedError."""
        config = BulkheadConfig(max_concurrent=1)
        bh = Bulkhead("test", config)
        await bh.acquire()

        async def operation():
            return "should not run"

        with pytest.raises(BulkheadRejectedError):
            await bh.execute(operation)

    def test_metrics(self):
        """Bulkhead provides metrics."""
        config = BulkheadConfig(max_concurrent=5)
        bh = Bulkhead("test", config)
        metrics = bh.get_metrics()

        assert "name" in metrics
        assert "active" in metrics
        assert "max_concurrent" in metrics
        assert metrics["max_concurrent"] == 5


# ============================================================================
# Retry Policy Tests
# ============================================================================

class TestRetryPolicies:
    """Test retry policy configurations."""

    def test_get_default_retry_decorator(self):
        """Default policy configured correctly."""
        decorator = get_retry_decorator(RetryPolicy.DEFAULT)

        assert decorator is not None
        # Verify it's a retry decorator
        assert hasattr(decorator, '__name__')

    def test_get_aggressive_retry_decorator(self):
        """Aggressive policy configured for quick retries."""
        decorator = get_retry_decorator(RetryPolicy.AGGRESSIVE)
        assert decorator is not None

    def test_get_conservative_retry_decorator(self):
        """Conservative policy configured for minimal retries."""
        decorator = get_retry_decorator(RetryPolicy.CONSERVATIVE)
        assert decorator is not None

    def test_custom_max_attempts(self):
        """Custom max attempts override policy defaults."""
        decorator = get_retry_decorator(RetryPolicy.DEFAULT, max_attempts=5)
        assert decorator is not None


# ============================================================================
# Connection Pool Tests
# ============================================================================

class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.mark.asyncio
    async def test_acquire_returns_connection(self):
        """Pool returns pooled connection."""
        pool = ConnectionPool(
            name="test",
            factory=lambda: {"id": 1},
            config=PoolConfig(max_size=2)
        )

        conn = await pool.acquire()
        assert conn is not None
        assert conn.connection == {"id": 1}
        assert pool.in_use_count == 1

    @pytest.mark.asyncio
    async def test_reuse_connection(self):
        """Pool reuses connections."""
        pool = ConnectionPool(
            name="test",
            factory=lambda: {"id": 1},
            config=PoolConfig(max_size=1)
        )

        conn1 = await pool.acquire()
        await conn1.release()

        conn2 = await pool.acquire()
        assert conn1 is conn2  # Same connection reused
        assert pool.in_use_count == 1

    @pytest.mark.asyncio
    async def test_exhausted_pool_raises(self):
        """Pool raises when exhausted."""
        pool = ConnectionPool(
            name="test",
            factory=lambda: {"id": 1},
            config=PoolConfig(max_size=1)
        )

        await pool.acquire()

        from core.resilience import PoolExhaustedError
        with pytest.raises(PoolExhaustedError):
            await pool.acquire()

    def test_pool_metrics(self):
        """Pool provides metrics."""
        pool = ConnectionPool(
            name="test",
            factory=lambda: {"id": 1},
            config=PoolConfig(max_size=5)
        )

        metrics = pool.get_metrics()
        assert "name" in metrics
        assert "max_size" in metrics
        assert metrics["max_size"] == 5


# ============================================================================
# Integration Tests
# ============================================================================

class TestResiliencePatterns:
    """Integration tests for resilience patterns working together."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_bulkhead(self):
        """Circuit breaker and bulkhead work together."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("provider", config)

        bulkhead_config = BulkheadConfig(max_concurrent=5)
        bh = await asyncio.get_event_loop().run_in_executor(
            None, lambda: Bulkhead("provider", bulkhead_config)
        ) if False else Bulkhead("provider", bulkhead_config)

        async def failing_operation():
            raise ConnectionError("provider down")

        # Bulkhead should track capacity
        for _ in range(5):
            await bh.acquire()

        # Circuit should track failures
        for _ in range(3):
            await cb.record_failure(ConnectionError("down"))

        assert not cb.is_available or bh.available_capacity == 0

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """System degrades gracefully under failure."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config)

        bulkhead_config = BulkheadConfig(max_concurrent=1)
        bh = Bulkhead("test", bulkhead_config)

        # Exhaust bulkhead
        await bh.acquire()

        # Fail circuit
        await cb.record_failure(ValueError("fail"))
        await cb.record_failure(ValueError("fail"))

        # Both should indicate unavailability
        assert not cb.is_available
        assert bh.available_capacity == 0


# ============================================================================
# Async Concurrency Tests
# ============================================================================

class TestAsyncConcurrency:
    """Test async concurrency patterns."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Semaphore correctly limits concurrent operations."""
        semaphore = asyncio.Semaphore(2)
        active = 0
        max_active = 0

        async def limited_task():
            nonlocal active, max_active
            async with semaphore:
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.01)
                active -= 1

        # Run 5 tasks with limit of 2
        await asyncio.gather(*[limited_task() for _ in range(5)])

        assert max_active <= 2

    @pytest.mark.asyncio
    async def test_backpressure_with_queue(self):
        """Queue provides backpressure."""
        queue = asyncio.Queue(maxsize=2)
        produced = []
        consumed = []

        async def producer():
            for i in range(5):
                await queue.put(i)
                produced.append(i)
                await asyncio.sleep(0.001)

        async def consumer():
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.01)
                    consumed.append(item)
                except asyncio.TimeoutError:
                    break

        await asyncio.gather(producer(), consumer())

        # Not all items may be produced due to backpressure
        assert len(consumed) <= len(produced)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])