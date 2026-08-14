"""Dependency injection container for enterprise-grade service management."""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, TypeVar, Optional, Dict, Type, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from core.config import Settings
from core.provider_router import ProviderRouter
from core.orchestrator_core import DatasetOrchestrator
from core.db import AsyncDB
from core.cache import SimpleRedisCache
from core.observability import ObservabilityManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifetime(Enum):
    """Service lifetime definitions."""
    TRANSIENT = "transient"     # New instance every time
    SCOPED = "scoped"          # One instance per request/session
    SINGLETON = "singleton"    # One instance for application lifetime


@dataclass
class ServiceDescriptor:
    """Descriptor for a registered service."""
    service_type: Type
    factory: Callable[..., Any]
    lifetime: ServiceLifetime
    instance: Optional[Any] = None
    depends_on: list[Type] = field(default_factory=list)


class DependencyError(Exception):
    """Raised when dependency resolution fails."""
    pass


class ServiceContainer:
    """
    Enterprise-grade dependency injection container.

    Features:
    - Constructor injection for all dependencies
    - Singleton, scoped, and transient lifetime management
    - Circular dependency detection
    - Async-safe initialization
    - Graceful shutdown handling
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._initialized: Set[Type] = set()
        self._initializing: Set[Type] = set()
        self._shutdown_callbacks: list[Callable] = []
        self._is_shutting_down = False

    def register(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        depends_on: list[Type] = None
    ) -> 'ServiceContainer':
        """Register a service with its factory."""
        if service_type in self._services:
            raise ValueError(f"Service {service_type.__name__} already registered")

        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime,
            depends_on=depends_on or []
        )
        logger.debug(f"Registered service: {service_type.__name__} ({lifetime.value})")
        return self

    def register_singleton(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        depends_on: list[Type] = None
    ) -> 'ServiceContainer':
        """Register a singleton service."""
        return self.register(service_type, factory, ServiceLifetime.SINGLETON, depends_on)

    def register_scoped(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        depends_on: list[Type] = None
    ) -> 'ServiceContainer':
        """Register a scoped service."""
        return self.register(service_type, factory, ServiceLifetime.SCOPED, depends_on)

    def register_instance(self, service_type: Type[T], instance: T) -> 'ServiceContainer':
        """Register an existing instance as singleton."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=lambda: instance,
            lifetime=ServiceLifetime.SINGLETON,
            instance=instance
        )
        self._initialized.add(service_type)
        return self

    async def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service by type."""
        if self._is_shutting_down:
            raise DependencyError("Container is shutting down")

        if service_type not in self._services:
            raise DependencyError(f"Service {service_type.__name__} not registered")

        descriptor = self._services[service_type]

        # Circular dependency detection
        if service_type in self._initializing:
            raise DependencyError(
                f"Circular dependency detected: {service_type.__name__}"
            )

        # Return existing singleton instance
        if descriptor.lifetime == ServiceLifetime.SINGLETON and descriptor.instance is not None:
            return descriptor.instance

        # Resolve dependencies first
        self._initializing.add(service_type)
        try:
            dependencies = {}
            for dep_type in descriptor.depends_on:
                dependencies[dep_type.__name__] = await self.resolve(dep_type)

            # Create instance
            instance = descriptor.factory(**dependencies)

            # Store singleton instances
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                descriptor.instance = instance
                self._initialized.add(service_type)

            return instance

        finally:
            self._initializing.discard(service_type)

    def add_shutdown_callback(self, callback: Callable) -> None:
        """Add a callback to run during shutdown."""
        self._shutdown_callbacks.append(callback)

    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        logger.info("Shutting down service container...")
        self._is_shutting_down = True

        # Run shutdown callbacks in reverse order
        for callback in reversed(self._shutdown_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

        # Clear singleton instances
        for descriptor in self._services.values():
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                if hasattr(descriptor.instance, 'close'):
                    try:
                        await descriptor.instance.close()
                    except Exception as e:
                        logger.error(f"Error closing {descriptor.service_type.__name__}: {e}")

        self._services.clear()
        self._initialized.clear()
        logger.info("Service container shutdown complete")


# Global container (created on first use)
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container."""
    global _container
    if _container is None:
        raise DependencyError("Container not initialized. Call create_container() first.")
    return _container


def set_container(container: ServiceContainer) -> None:
    """Set the global service container."""
    global _container
    _container = container


async def create_container(settings: Settings) -> ServiceContainer:
    """Create and configure the service container."""
    container = ServiceContainer(settings)

    # Register core services
    container.register_singleton(
        Settings,
        lambda: settings
    )

    # Database (singleton for connection pool)
    container.register_singleton(
        AsyncDB,
        lambda: AsyncDB(settings.postgres_url),
        depends_on=[Settings]
    )

    # Cache (singleton for connection pool)
    container.register_singleton(
        SimpleRedisCache,
        lambda: SimpleRedisCache(settings.redis_url),
        depends_on=[Settings]
    )

    # Observability (singleton)
    container.register_singleton(
        ObservabilityManager,
        lambda: ObservabilityManager(settings),
        depends_on=[Settings]
    )

    # Provider router (singleton)
    container.register_singleton(
        ProviderRouter,
        lambda settings=settings: ProviderRouter(settings),
        depends_on=[Settings]
    )

    # Orchestrator (singleton for LangGraph state)
    container.register_singleton(
        DatasetOrchestrator,
        lambda: DatasetOrchestrator(),
        depends_on=[Settings]
    )

    # Add shutdown handler
    container.add_shutdown_callback(lambda: logger.info("Container shutdown callback executed"))

    set_container(container)
    return container