"""
Service Registry — Centralized service lifecycle management.

Replaces ad-hoc global singletons with a testable registry pattern.
Services can be registered, retrieved, and reset (for testing).

Usage:
    from core.service_registry import services

    # Register (typically in app startup)
    services.register("tax_config", TaxConfigLoader())

    # Retrieve
    loader = services.get("tax_config")

    # In tests (via conftest.py fixture)
    services.reset_all()
"""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Thread-safe service registry with lazy initialization support.

    Services can be registered as instances or as factory callables
    (for lazy/deferred initialization).
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}

    def register(self, name: str, instance: Any) -> None:
        """
        Register a service instance.

        Args:
            name: Service identifier (e.g., "tax_config", "webhook_service")
            instance: The service instance
        """
        self._services[name] = instance
        logger.debug(f"Service registered: {name}")

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """
        Register a factory for lazy service initialization.

        The factory will be called on first `get()` and the result cached.

        Args:
            name: Service identifier
            factory: Callable that returns the service instance
        """
        self._factories[name] = factory
        logger.debug(f"Service factory registered: {name}")

    def get(self, name: str, default: Any = None) -> Any:
        """
        Retrieve a registered service.

        If a factory is registered and the service hasn't been initialized,
        the factory is called and the result is cached.

        Args:
            name: Service identifier
            default: Default value if service not found

        Returns:
            Service instance or default
        """
        if name in self._services:
            return self._services[name]

        if name in self._factories:
            instance = self._factories[name]()
            self._services[name] = instance
            return instance

        return default

    def has(self, name: str) -> bool:
        """Check if a service is registered (instance or factory)."""
        return name in self._services or name in self._factories

    def reset(self, name: str) -> None:
        """
        Reset a specific service (remove cached instance).

        If a factory is registered, the service will be re-created on next get().
        """
        self._services.pop(name, None)
        logger.debug(f"Service reset: {name}")

    def reset_all(self) -> None:
        """
        Reset all services. Useful for test isolation.

        Factories are preserved so services can be re-created.
        """
        self._services.clear()
        logger.debug("All services reset")

    def unregister(self, name: str) -> None:
        """Completely remove a service (instance and factory)."""
        self._services.pop(name, None)
        self._factories.pop(name, None)

    @property
    def registered_names(self) -> list:
        """List all registered service names."""
        return list(set(list(self._services.keys()) + list(self._factories.keys())))


# Global singleton registry
services = ServiceRegistry()
