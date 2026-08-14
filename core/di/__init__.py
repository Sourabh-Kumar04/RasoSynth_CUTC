"""Dependency injection module."""
from core.di.container import (
    ServiceContainer,
    ServiceLifetime,
    ServiceDescriptor,
    DependencyError,
    get_container,
    set_container,
    create_container,
)
from core.di.factory import (
    AppFactory,
    get_app_factory,
    create_prod_app,
    create_test_app,
)

__all__ = [
    "ServiceContainer",
    "ServiceLifetime",
    "ServiceDescriptor",
    "DependencyError",
    "get_container",
    "set_container",
    "create_container",
    "AppFactory",
    "get_app_factory",
    "create_prod_app",
    "create_test_app",
]