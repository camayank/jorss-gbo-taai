"""
Lightweight In-Process Event Bus

Thread-safe publish/subscribe for decoupled subsystem communication.
No external dependencies (no Redis/Kafka).

Usage:
    from events.event_bus import EventBus, get_event_bus
    bus = get_event_bus()
    bus.on(AdvisorProfileComplete, my_handler)
    bus.emit(AdvisorProfileComplete(...))
"""

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class EventBus:
    """Thread-safe in-process event bus."""

    def __init__(self):
        self._handlers: Dict[Type, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event_type: Type, handler: Callable) -> None:
        """Subscribe a handler to an event type."""
        with self._lock:
            self._handlers[event_type].append(handler)

    def off(self, event_type: Type, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def emit(self, event: Any) -> None:
        """Emit an event to all subscribed handlers.

        Handler errors are logged but do NOT block other handlers.
        """
        event_type = type(event)
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    f"[EventBus] Handler {handler.__name__} failed for "
                    f"{event_type.__name__}. Continuing to next handler."
                )

    def handler_count(self, event_type: Type) -> int:
        """Return number of handlers registered for an event type."""
        with self._lock:
            return len(self._handlers.get(event_type, []))


# Singleton
_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get or create the global event bus singleton."""
    global _event_bus
    if _event_bus is None:
        with _bus_lock:
            if _event_bus is None:
                _event_bus = EventBus()
    return _event_bus
