"""Tests for in-process event bus."""

import pytest
import threading
from dataclasses import dataclass

from events.event_bus import EventBus


@dataclass
class FakeEvent:
    value: str
    tenant_id: str


class TestEventBusSubscription:
    """Tests for subscribing and emitting events."""

    def test_handler_receives_emitted_event(self):
        bus = EventBus()
        received = []
        bus.on(FakeEvent, lambda e: received.append(e))
        bus.emit(FakeEvent(value="hello", tenant_id="t1"))
        assert len(received) == 1
        assert received[0].value == "hello"

    def test_multiple_handlers_all_called(self):
        bus = EventBus()
        a, b = [], []
        bus.on(FakeEvent, lambda e: a.append(e))
        bus.on(FakeEvent, lambda e: b.append(e))
        bus.emit(FakeEvent(value="x", tenant_id="t1"))
        assert len(a) == 1
        assert len(b) == 1

    def test_handler_error_does_not_block_others(self):
        bus = EventBus()
        received = []

        def bad_handler(e):
            raise RuntimeError("boom")

        bus.on(FakeEvent, bad_handler)
        bus.on(FakeEvent, lambda e: received.append(e))
        bus.emit(FakeEvent(value="ok", tenant_id="t1"))
        assert len(received) == 1

    def test_no_handlers_emits_without_error(self):
        bus = EventBus()
        bus.emit(FakeEvent(value="ignored", tenant_id="t1"))

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.on(FakeEvent, handler)
        bus.off(FakeEvent, handler)
        bus.emit(FakeEvent(value="x", tenant_id="t1"))
        assert len(received) == 0

    def test_thread_safety(self):
        bus = EventBus()
        count = {"n": 0}
        lock = threading.Lock()

        def handler(e):
            with lock:
                count["n"] += 1

        bus.on(FakeEvent, handler)
        threads = [
            threading.Thread(target=bus.emit, args=(FakeEvent(value=str(i), tenant_id="t1"),))
            for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert count["n"] == 100
