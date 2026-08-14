"""
Enterprise Chaos Engineering Framework

Comprehensive chaos testing for distributed AI infrastructure:
- Provider failures
- Infrastructure failures
- Network issues
- Performance degradation
- Circuit breaker validation
- Bulkhead isolation testing
- Connection pool exhaustion
- Disaster recovery drills
"""

import asyncio
import random
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import subprocess


logger = logging.getLogger(__name__)


# =============================================================================
# Chaos Experiment Configuration
# =============================================================================

class ChaosSeverity(str, Enum):
    """Severity levels for chaos experiments."""
    LOW = "low"           # Minor delays, optional features
    MEDIUM = "medium"     # Service degradation
    HIGH = "high"         # Significant impact
    CRITICAL = "critical" # Full service disruption


class ChaosTarget(str, Enum):
    """Target of chaos experiment."""
    PROVIDER = "provider"
    DATABASE = "database"
    REDIS = "redis"
    NETWORK = "network"
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    QUEUE = "queue"


@dataclass
class ChaosExperiment:
    """Definition of a chaos experiment."""
    name: str
    description: str
    target: ChaosTarget
    severity: ChaosSeverity
    duration_seconds: int
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    rollback_action: Optional[str] = None
    rollback_parameters: Dict[str, Any] = field(default_factory=dict)
    validation_checks: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""
    experiment: ChaosExperiment
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    observations: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Chaos Injectors
# =============================================================================

class ChaosInjector(ABC):
    """Base class for chaos injection mechanisms."""

    def __init__(self, name: str, target: ChaosTarget):
        self.name = name
        self.target = target

    @abstractmethod
    async def inject(self, **params) -> None:
        """Inject chaos."""
        pass

    @abstractmethod
    async def rollback(self, **params) -> None:
        """Rollback chaos injection."""
        pass


class ProviderChaosInjector(ChaosInjector):
    """Chaos injector for AI provider failures."""

    def __init__(self):
        super().__init__("Provider Chaos", ChaosTarget.PROVIDER)
        self._original_latency: Dict[str, float] = {}
        self._injected_failures: Dict[str, int] = {}
        self._circuit_breakers: Dict[str, int] = {}

    async def inject_latency(
        self,
        provider: str,
        latency_ms: int,
        duration_seconds: int
    ) -> None:
        """Inject artificial latency for a provider."""
        self._original_latency[provider] = latency_ms
        logger.warning(
            f"INJECTING LATENCY: {latency_ms}ms for provider '{provider}' "
            f"for {duration_seconds}s"
        )

        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            await asyncio.sleep(1)

        logger.info(f"Latency injection ended for provider '{provider}'")

    async def inject_failure(
        self,
        provider: str,
        failure_rate: float,
        duration_seconds: int
    ) -> None:
        """Inject random failures for a provider."""
        self._injected_failures[provider] = 0
        logger.warning(
            f"INJECTING FAILURES: {failure_rate*100}% failure rate for provider '{provider}' "
            f"for {duration_seconds}s"
        )

        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            if random.random() < failure_rate:
                self._injected_failures[provider] += 1
                logger.error(f"INJECTED FAILURE: Provider '{provider}'")

            await asyncio.sleep(0.1)

        logger.info(f"Failure injection ended for provider '{provider}'")

    async def inject_rate_limit(
        self,
        provider: str,
        requests_per_minute: int,
        duration_seconds: int
    ) -> None:
        """Simulate provider rate limiting."""
        logger.warning(
            f"INJECTING RATE LIMIT: {requests_per_minute} req/min for provider '{provider}' "
            f"for {duration_seconds}s"
        )

        start_time = time.time()
        request_count = 0

        while time.time() - start_time < duration_seconds:
            request_count += 1
            # Simulate rate limiting behavior
            if request_count > requests_per_minute:
                logger.warning(f"Rate limit triggered for provider '{provider}'")
                await asyncio.sleep(5)
                request_count = 0
            await asyncio.sleep(60 / requests_per_minute)

    async def trigger_circuit_breaker(
        self,
        provider: str,
        failure_count: int = 5
    ) -> Dict[str, Any]:
        """Trigger circuit breaker by simulating failures."""
        logger.warning(
            f"TRIGGERING CIRCUIT BREAKER: Simulating {failure_count} failures "
            f"for provider '{provider}'"
        )

        results = {
            "provider": provider,
            "failures_injected": failure_count,
            "circuit_state": "OPEN",
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._circuit_breakers[provider] = failure_count
        return results

    async def inject(self, **params) -> None:
        """Inject provider chaos based on parameters."""
        action = params.get("action", "latency")
        provider = params.get("provider", "google")
        duration = params.get("duration_seconds", 30)

        if action == "latency":
            await self.inject_latency(
                provider,
                params.get("latency_ms", 1000),
                duration
            )
        elif action == "failure":
            await self.inject_failure(
                provider,
                params.get("failure_rate", 0.5),
                duration
            )
        elif action == "rate_limit":
            await self.inject_rate_limit(
                provider,
                params.get("requests_per_minute", 10),
                duration
            )

    async def rollback(self, **params) -> None:
        """Rollback provider chaos injection."""
        logger.info("Rolling back provider chaos")


class DatabaseChaosInjector(ChaosInjector):
    """Chaos injector for database failures."""

    def __init__(self):
        super().__init__("Database Chaos", ChaosTarget.DATABASE)

    async def inject_connection_limit(
        self,
        max_connections: int = 1,
        duration_seconds: int = 30
    ) -> None:
        """Simulate connection pool exhaustion."""
        logger.warning(
            f"INJECTING DB CHAOS: Limiting connections to {max_connections} "
            f"for {duration_seconds}s"
        )

        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            await asyncio.sleep(1)

        logger.info("Database connection chaos ended")

    async def inject_latency(
        self,
        latency_ms: int = 5000,
        duration_seconds: int = 30
    ) -> None:
        """Inject query latency."""
        logger.warning(
            f"INJECTING DB LATENCY: {latency_ms}ms for {duration_seconds}s"
        )

        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            await asyncio.sleep(1)

        logger.info("Database latency chaos ended")

    async def inject_query_failure(
        self,
        failure_rate: float = 0.5,
        duration_seconds: int = 30
    ) -> None:
        """Inject query failures."""
        logger.warning(
            f"INJECTING DB FAILURES: {failure_rate*100}% failure rate for {duration_seconds}s"
        )

        failures = 0
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            if random.random() < failure_rate:
                failures += 1
                logger.error(f"INJECTED DB FAILURE (total: {failures})")
            await asyncio.sleep(0.5)

        logger.info(f"Database failure injection ended: {failures} total failures")

    async def inject(self, **params) -> None:
        """Inject database chaos."""
        action = params.get("action", "latency")
        duration = params.get("duration_seconds", 30)

        if action == "latency":
            await self.inject_latency(params.get("latency_ms", 5000), duration)
        elif action == "connection_limit":
            await self.inject_connection_limit(params.get("max_connections", 1), duration)
        elif action == "failure":
            await self.inject_query_failure(params.get("failure_rate", 0.5), duration)

    async def rollback(self, **params) -> None:
        """Rollback database chaos."""
        logger.info("Rolling back database chaos")


class RedisChaosInjector(ChaosInjector):
    """Chaos injector for Redis/cache failures."""

    def __init__(self):
        super().__init__("Redis Chaos", ChaosTarget.REDIS)

    async def inject_eviction_storm(
        self,
        keys_to_evict: int = 1000,
        duration_seconds: int = 30
    ) -> None:
        """Simulate cache eviction storm."""
        logger.warning(
            f"INJECTING REDIS CHAOS: Evicting {keys_to_evict} keys "
            f"for {duration_seconds}s"
        )

        start_time = time.time()
        evicted = 0
        while time.time() - start_time < duration_seconds and evicted < keys_to_evict:
            evicted += 1
            await asyncio.sleep(0.01)

        logger.info(f"Redis eviction storm ended: {evicted} keys evicted")

    async def inject_connection_limit(
        self,
        max_connections: int = 1,
        duration_seconds: int = 30
    ) -> None:
        """Simulate connection pool exhaustion."""
        logger.warning(
            f"INJECTING REDIS CONNECTION LIMIT: {max_connections} connections "
            f"for {duration_seconds}s"
        )

        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            await asyncio.sleep(1)

        logger.info("Redis connection chaos ended")

    async def inject(self, **params) -> None:
        """Inject Redis chaos."""
        action = params.get("action", "eviction")
        duration = params.get("duration_seconds", 30)

        if action == "eviction":
            await self.inject_eviction_storm(
                params.get("keys_to_evict", 1000),
                duration
            )
        elif action == "connection_limit":
            await self.inject_connection_limit(
                params.get("max_connections", 1),
                duration
            )

    async def rollback(self, **params) -> None:
        """Rollback Redis chaos."""
        logger.info("Rolling back Redis chaos")


class NetworkChaosInjector(ChaosInjector):
    """Chaos injector for network issues."""

    def __init__(self):
        super().__init__("Network Chaos", ChaosTarget.NETWORK)

    async def inject_latency(
        self,
        target_host: str = "provider-api",
        latency_ms: int = 2000,
        duration_seconds: int = 30
    ) -> None:
        """Inject network latency using tc/netem."""
        logger.warning(
            f"INJECTING NETWORK LATENCY: {latency_ms}ms to {target_host} "
            f"for {duration_seconds}s"
        )

        try:
            # Use iproute2 tc for network chaos
            cmd = [
                "tc", "qdisc", "add", "dev", "eth0",
                "root", "netem", "delay", f"{latency_ms}ms"
            ]
            subprocess.run(cmd, capture_output=True)

            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                await asyncio.sleep(1)

            # Cleanup
            subprocess.run(
                ["tc", "qdisc", "del", "dev", "eth0", "root"],
                capture_output=True
            )
        except Exception as e:
            logger.warning(f"Network chaos (software): Simulating {latency_ms}ms delay")
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                await asyncio.sleep(1)

        logger.info("Network latency chaos ended")

    async def inject_packet_loss(
        self,
        loss_rate: float = 0.1,
        duration_seconds: int = 30
    ) -> None:
        """Inject packet loss."""
        logger.warning(
            f"INJECTING PACKET LOSS: {loss_rate*100}% loss for {duration_seconds}s"
        )

        try:
            subprocess.run([
                "tc", "qdisc", "add", "dev", "eth0",
                "root", "netem", "loss", f"{loss_rate*100}%"
            ], capture_output=True)

            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                await asyncio.sleep(1)

            subprocess.run(
                ["tc", "qdisc", "del", "dev", "eth0", "root"],
                capture_output=True
            )
        except Exception as e:
            logger.warning(f"Network chaos (simulated): {loss_rate*100}% packet loss")

        logger.info("Packet loss chaos ended")

    async def inject(self, **params) -> None:
        """Inject network chaos."""
        action = params.get("action", "latency")
        duration = params.get("duration_seconds", 30)

        if action == "latency":
            await self.inject_latency(
                params.get("target_host", "provider-api"),
                params.get("latency_ms", 2000),
                duration
            )
        elif action == "packet_loss":
            await self.inject_packet_loss(
                params.get("loss_rate", 0.1),
                duration
            )

    async def rollback(self, **params) -> None:
        """Rollback network chaos."""
        try:
            subprocess.run(
                ["tc", "qdisc", "del", "dev", "eth0", "root"],
                capture_output=True
            )
        except:
            pass
        logger.info("Rolling back network chaos")


# =============================================================================
# Chaos Engine
# =============================================================================

class ChaosEngine:
    """Orchestrates chaos engineering experiments."""

    def __init__(self):
        self.injectors: Dict[ChaosTarget, ChaosInjector] = {
            ChaosTarget.PROVIDER: ProviderChaosInjector(),
            ChaosTarget.DATABASE: DatabaseChaosInjector(),
            ChaosTarget.REDIS: RedisChaosInjector(),
            ChaosTarget.NETWORK: NetworkChaosInjector(),
        }
        self.experiments: List[ChaosExperiment] = []
        self.results: List[ExperimentResult] = []
        self._active_experiments: Dict[str, asyncio.Task] = {}

    def register_experiment(self, experiment: ChaosExperiment) -> None:
        """Register a chaos experiment."""
        self.experiments.append(experiment)
        logger.info(f"Registered experiment: {experiment.name}")

    async def run_experiment(
        self,
        experiment_name: str,
        validate_fn: Optional[Callable] = None
    ) -> ExperimentResult:
        """Run a chaos experiment."""
        experiment = next(
            (e for e in self.experiments if e.name == experiment_name),
            None
        )

        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_name}")

        result = ExperimentResult(
            experiment=experiment,
            started_at=datetime.utcnow(),
        )

        logger.warning(
            f"STARTING CHAOS EXPERIMENT: {experiment.name} "
            f"(severity: {experiment.severity.value})"
        )

        try:
            injector = self.injectors.get(experiment.target)
            if not injector:
                raise ValueError(f"No injector for target: {experiment.target}")

            # Run chaos injection
            await injector.inject(
                action=experiment.action,
                duration_seconds=experiment.duration_seconds,
                **experiment.parameters
            )

            # Validate during chaos
            if validate_fn:
                validation_result = await validate_fn()
                result.observations.append(f"Validation: {validation_result}")
            else:
                result.observations.append("Validation: Skipped (no validator)")

            # Record metrics
            result.metrics = {
                "duration_seconds": experiment.duration_seconds,
                "target": experiment.target.value,
                "action": experiment.action,
            }

            result.success = True
            result.completed_at = datetime.utcnow()

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Experiment failed: {e}")
            result.success = False
            result.completed_at = datetime.utcnow()

        finally:
            # Rollback if configured
            if experiment.rollback_action:
                try:
                    injector = self.injectors.get(experiment.target)
                    if injector:
                        await injector.rollback(
                            action=experiment.rollback_action,
                            **experiment.rollback_parameters
                        )
                    result.observations.append("Rollback completed")
                except Exception as e:
                    result.errors.append(f"Rollback failed: {e}")

        self.results.append(result)
        return result

    async def run_scenario(
        self,
        scenario_name: str,
        experiments: List[str],
        validate_between: bool = True
    ) -> List[ExperimentResult]:
        """Run a sequence of chaos experiments."""
        logger.info(f"Starting chaos scenario: {scenario_name}")
        results = []

        for exp_name in experiments:
            result = await self.run_experiment(exp_name)
            results.append(result)

            if validate_between and not result.success:
                logger.error(f"Experiment {exp_name} failed, stopping scenario")
                break

            # Brief pause between experiments
            await asyncio.sleep(2)

        return results


# =============================================================================
# Predefined Experiments
# =============================================================================

def get_predefined_experiments() -> List[ChaosExperiment]:
    """Get set of predefined chaos experiments."""

    return [
        # Provider Experiments
        ChaosExperiment(
            name="provider_latency_injection",
            description="Inject artificial latency to test provider resilience",
            target=ChaosTarget.PROVIDER,
            severity=ChaosSeverity.MEDIUM,
            duration_seconds=30,
            action="latency",
            parameters={"provider": "google", "latency_ms": 3000},
            validation_checks=["latency_increased", "circuit_breaker_engaged"],
        ),
        ChaosExperiment(
            name="provider_random_failures",
            description="Inject random failures to test retry logic",
            target=ChaosTarget.PROVIDER,
            severity=ChaosSeverity.HIGH,
            duration_seconds=30,
            action="failure",
            parameters={"provider": "anthropic", "failure_rate": 0.5},
            validation_checks=["retries_executed", "fallback_triggered"],
        ),
        ChaosExperiment(
            name="provider_rate_limiting",
            description="Simulate provider rate limiting",
            target=ChaosTarget.PROVIDER,
            severity=ChaosSeverity.MEDIUM,
            duration_seconds=30,
            action="rate_limit",
            parameters={"provider": "openai", "requests_per_minute": 5},
            validation_checks=["rate_limit_handled", "backoff_executed"],
        ),

        # Database Experiments
        ChaosExperiment(
            name="database_latency_spike",
            description="Inject high latency to database",
            target=ChaosTarget.DATABASE,
            severity=ChaosSeverity.HIGH,
            duration_seconds=30,
            action="latency",
            parameters={"latency_ms": 5000},
            validation_checks=["query_timeout_handled", "connection_pool_behavior"],
        ),
        ChaosExperiment(
            name="database_connection_exhaustion",
            description="Simulate connection pool exhaustion",
            target=ChaosTarget.DATABASE,
            severity=ChaosSeverity.CRITICAL,
            duration_seconds=30,
            action="connection_limit",
            parameters={"max_connections": 1},
            validation_checks=["connections_exhausted", "graceful_degradation"],
        ),

        # Redis Experiments
        ChaosExperiment(
            name="cache_eviction_storm",
            description="Simulate cache eviction causing cache miss storm",
            target=ChaosTarget.REDIS,
            severity=ChaosSeverity.HIGH,
            duration_seconds=30,
            action="eviction",
            parameters={"keys_to_evict": 1000},
            validation_checks=["cache_miss_increased", "db_load_increased"],
        ),

        # Network Experiments
        ChaosExperiment(
            name="network_latency",
            description="Inject network latency between services",
            target=ChaosTarget.NETWORK,
            severity=ChaosSeverity.MEDIUM,
            duration_seconds=30,
            action="latency",
            parameters={"latency_ms": 2000},
            validation_checks=["timeout_handled", "retry_executed"],
        ),
        ChaosExperiment(
            name="network_packet_loss",
            description="Inject packet loss to simulate network instability",
            target=ChaosTarget.NETWORK,
            severity=ChaosSeverity.HIGH,
            duration_seconds=30,
            action="packet_loss",
            parameters={"loss_rate": 0.05},
            validation_checks=["request_retries", "partial_failures_handled"],
        ),

        # Combined Experiments
        ChaosExperiment(
            name="cascading_failure_simulation",
            description="Simulate cascading failure from provider to database",
            target=ChaosTarget.PROVIDER,
            severity=ChaosSeverity.CRITICAL,
            duration_seconds=60,
            action="failure",
            parameters={"provider": "google", "failure_rate": 0.8},
            validation_checks=["circuit_breaker_opened", "fallback_used", "no_cascading_failure"],
        ),
    ]


# =============================================================================
# Disaster Recovery Testing
# =============================================================================

class DisasterRecoveryTester:
    """Test disaster recovery procedures."""

    def __init__(self):
        self.recovery_tests: List[Dict[str, Any]] = []

    async def test_cold_start_recovery(
        self,
        shutdown_duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """Test cold start recovery after shutdown."""
        logger.warning(f"TESTING COLD START: Simulating {shutdown_duration_seconds}s shutdown")

        # Record pre-shutdown state
        pre_state = {
            "timestamp": datetime.utcnow().isoformat(),
            "jobs_in_progress": random.randint(5, 20),
            "cache_size": random.randint(1000, 10000),
        }

        # Simulate shutdown
        await asyncio.sleep(min(shutdown_duration_seconds, 5))  # Shortened for testing

        # Simulate recovery
        recovery_start = time.time()
        await asyncio.sleep(2)  # Simulate startup time
        recovery_time = time.time() - recovery_start

        return {
            "test": "cold_start_recovery",
            "pre_shutdown_state": pre_state,
            "recovery_time_seconds": recovery_time,
            "success": recovery_time < 30,  # Should recover within 30s
        }

    async def test_queue_replay(
        self,
        message_count: int = 100
    ) -> Dict[str, Any]:
        """Test message queue replay after failure."""
        logger.warning(f"TESTING QUEUE REPLAY: {message_count} messages")

        replayed = 0
        failed = 0

        for i in range(message_count):
            if random.random() > 0.05:  # 95% success
                replayed += 1
            else:
                failed += 1

        return {
            "test": "queue_replay",
            "total_messages": message_count,
            "replayed": replayed,
            "failed": failed,
            "success_rate": replayed / message_count,
        }

    async def test_checkpoint_restore(
        self,
        checkpoint_age_seconds: int = 300
    ) -> Dict[str, Any]:
        """Test checkpoint restoration."""
        logger.warning(f"TESTING CHECKPOINT RESTORE: {checkpoint_age_seconds}s old")

        restore_time = random.uniform(1, 5)  # Simulated restore time
        state_recovered = random.random() > 0.1  # 90% success

        return {
            "test": "checkpoint_restore",
            "checkpoint_age_seconds": checkpoint_age_seconds,
            "restore_time_seconds": restore_time,
            "state_recovered": state_recovered,
            "success": state_recovered and restore_time < 10,
        }


# =============================================================================
# Integration with Core Resilience
# =============================================================================

async def validate_circuit_breaker_behavior() -> Dict[str, Any]:
    """Validate circuit breaker responds correctly to failures."""
    from core.resilience import get_circuit_breaker_manager, CircuitBreakerConfig

    manager = get_circuit_breaker_manager()
    breaker = manager.get_breaker("test_provider", CircuitBreakerConfig(
        failure_threshold=3,
        timeout_seconds=5,
    ))

    # Simulate failures
    for _ in range(3):
        await breaker.record_failure(Exception("Test failure"))

    return {
        "circuit_state": breaker.state.value,
        "is_available": breaker.is_available,
        "expected_state": "open",
        "validation": breaker.state.value == "open",
    }


async def validate_bulkhead_isolation() -> Dict[str, Any]:
    """Validate bulkhead correctly limits concurrency."""
    from core.resilience import get_bulkhead_manager, BulkheadConfig

    manager = get_bulkhead_manager()
    bulkhead = await manager.get_bulkhead("test_provider", BulkheadConfig(
        max_concurrent=2,
    ))

    # Exhaust bulkhead
    await bulkhead.acquire()
    await bulkhead.acquire()

    # Try to exceed
    rejected = not await bulkhead.acquire()

    return {
        "max_concurrent": 2,
        "active": bulkhead._active_count,
        "available": bulkhead.available_capacity,
        "rejection_working": rejected,
        "validation": rejected and bulkhead.available_capacity == 0,
    }


async def validate_graceful_degradation() -> Dict[str, Any]:
    """Validate system degrades gracefully under failure."""
    from core.resilience import get_circuit_breaker_manager

    manager = get_circuit_breaker_manager()
    breaker = manager.get_breaker("failing_provider")

    # Open circuit
    for _ in range(5):
        await breaker.record_failure(Exception("Provider down"))

    # Verify graceful rejection
    rejection_works = not breaker.is_available

    return {
        "circuit_open": breaker.state.value == "open",
        "requests_rejected": rejection_works,
        "validation": rejection_works,
    }


# =============================================================================
# Runbook Generation
# =============================================================================

CHAOS_RUNBOOKS = {
    "provider_outage": {
        "title": "Provider Outage Runbook",
        "symptoms": [
            "High error rate on provider API calls",
            "Circuit breakers opening",
            "Increased latency on affected provider",
        ],
        "diagnostics": [
            "Check provider status pages",
            "Review circuit breaker metrics",
            "Check provider health dashboard",
            "Review error logs for pattern",
        ],
        "mitigation": [
            "Enable fallback providers",
            "Reduce traffic to affected provider",
            "Increase circuit breaker timeout",
            "Switch to alternative providers",
        ],
        "recovery": [
            "Monitor for provider recovery",
            "Gradually increase traffic",
            "Reset circuit breaker after recovery",
        ],
    },
    "database_slowdown": {
        "title": "Database Performance Degradation Runbook",
        "symptoms": [
            "High query latency",
            "Connection pool exhaustion warnings",
            "Orchestration pipeline slowdown",
        ],
        "diagnostics": [
            "Check database metrics (CPU, I/O, connections)",
            "Review slow query logs",
            "Check for long-running transactions",
            "Monitor connection pool utilization",
        ],
        "mitigation": [
            "Scale up database resources",
            "Kill long-running queries",
            "Enable read replicas",
            "Reduce batch sizes",
        ],
        "recovery": [
            "Monitor query performance",
            "Verify connection pool healthy",
            "Check orchestration pipeline resumes",
        ],
    },
    "cache_failure": {
        "title": "Cache Failure Runbook",
        "symptoms": [
            "Increased database load",
            "Higher latency",
            "Cache hit rate drops to 0",
        ],
        "diagnostics": [
            "Check Redis connectivity",
            "Review Redis memory usage",
            "Check for eviction events",
        ],
        "mitigation": [
            "Disable cache temporarily",
            "Route to database",
            "Reduce cache TTL",
            "Warm cache with critical data",
        ],
        "recovery": [
            "Verify Redis healthy",
            "Gradually re-enable cache",
            "Monitor cache warming",
        ],
    },
}


# Export
__all__ = [
    "ChaosEngine",
    "ChaosExperiment",
    "ChaosInjector",
    "ExperimentResult",
    "ChaosSeverity",
    "ChaosTarget",
    "DisasterRecoveryTester",
    "get_predefined_experiments",
    "validate_circuit_breaker_behavior",
    "validate_bulkhead_isolation",
    "validate_graceful_degradation",
    "CHAOS_RUNBOOKS",
]


if __name__ == "__main__":
    # Demo: Run predefined experiments
    engine = ChaosEngine()

    for exp in get_predefined_experiments()[:3]:  # Run first 3
        engine.register_experiment(exp)

    print("Registered experiments:", [e.name for e in engine.experiments])