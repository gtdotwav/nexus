"""
NEXUS — EventBus tests.

Validates: event emission, handler execution, parallel async handlers,
error isolation, thread-safe emit, history, and stats.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.event_bus import EventBus, EventType, Event


@pytest.mark.asyncio
async def test_emit_calls_handler():
    """Emit should call the registered handler with the event."""
    bus = EventBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.on(EventType.KILL, handler)
    event = await bus.emit(EventType.KILL, {"creature": "Dragon"}, source="test")

    assert len(received) == 1
    assert received[0].type == EventType.KILL
    assert received[0].data["creature"] == "Dragon"
    assert received[0].source == "test"


@pytest.mark.asyncio
async def test_emit_ignores_unsubscribed_types():
    """Handler should NOT be called for events it didn't subscribe to."""
    bus = EventBus()
    called = False

    async def handler(event: Event):
        nonlocal called
        called = True

    bus.on(EventType.KILL, handler)
    await bus.emit(EventType.DEATH, {})

    assert not called


@pytest.mark.asyncio
async def test_parallel_async_handlers():
    """Multiple async handlers should execute concurrently, not sequentially."""
    bus = EventBus()
    order = []

    async def slow_handler(event: Event):
        order.append("slow_start")
        await asyncio.sleep(0.05)
        order.append("slow_end")

    async def fast_handler(event: Event):
        order.append("fast_start")
        order.append("fast_end")

    bus.on(EventType.KILL, slow_handler, priority=10)
    bus.on(EventType.KILL, fast_handler, priority=0)

    await bus.emit(EventType.KILL, {})

    # In parallel: fast should complete before slow finishes
    assert "fast_end" in order
    assert "slow_end" in order
    # Fast handler should finish before slow handler
    assert order.index("fast_end") < order.index("slow_end")


@pytest.mark.asyncio
async def test_handler_error_isolation():
    """A failing handler should not prevent other handlers from running."""
    bus = EventBus()
    received = []

    async def bad_handler(event: Event):
        raise ValueError("boom")

    async def good_handler(event: Event):
        received.append(event)

    bus.on(EventType.KILL, bad_handler, priority=10)
    bus.on(EventType.KILL, good_handler, priority=0)

    # Should NOT raise
    await bus.emit(EventType.KILL, {"test": True})

    assert len(received) == 1


@pytest.mark.asyncio
async def test_sync_handler():
    """Sync handlers should work alongside async handlers."""
    bus = EventBus()
    sync_received = []

    def sync_handler(event: Event):
        sync_received.append(event.data)

    bus.on(EventType.STATE_UPDATED, sync_handler)
    await bus.emit(EventType.STATE_UPDATED, {"hp": 80})

    assert len(sync_received) == 1
    assert sync_received[0]["hp"] == 80


@pytest.mark.asyncio
async def test_global_handler():
    """on_any() handlers should receive ALL events."""
    bus = EventBus()
    all_events = []

    async def global_handler(event: Event):
        all_events.append(event.type)

    bus.on_any(global_handler)

    await bus.emit(EventType.KILL, {})
    await bus.emit(EventType.DEATH, {})
    await bus.emit(EventType.HP_CHANGED, {})

    assert all_events == [EventType.KILL, EventType.DEATH, EventType.HP_CHANGED]


@pytest.mark.asyncio
async def test_off_unsubscribes():
    """off() should remove a handler so it's no longer called."""
    bus = EventBus()
    calls = 0

    async def handler(event: Event):
        nonlocal calls
        calls += 1

    bus.on(EventType.KILL, handler)
    await bus.emit(EventType.KILL, {})
    assert calls == 1

    bus.off(EventType.KILL, handler)
    await bus.emit(EventType.KILL, {})
    assert calls == 1  # No additional call


@pytest.mark.asyncio
async def test_event_history():
    """Events should be stored in history ring buffer."""
    bus = EventBus(history_size=3)

    for i in range(5):
        await bus.emit(EventType.KILL, {"n": i})

    history = bus.get_history(EventType.KILL, max_age_s=60)
    # Ring buffer size 3, so only last 3 events retained
    assert len(history) == 3
    assert [e.data["n"] for e in history] == [2, 3, 4]


@pytest.mark.asyncio
async def test_get_last():
    """get_last() should return the most recent event."""
    bus = EventBus()

    assert bus.get_last(EventType.KILL) is None

    await bus.emit(EventType.KILL, {"creature": "Rat"})
    await bus.emit(EventType.KILL, {"creature": "Dragon"})

    last = bus.get_last(EventType.KILL)
    assert last is not None
    assert last.data["creature"] == "Dragon"


@pytest.mark.asyncio
async def test_stats():
    """Stats should reflect current bus state."""
    bus = EventBus()

    async def h1(event): pass
    async def h2(event): pass

    bus.on(EventType.KILL, h1)
    bus.on(EventType.DEATH, h2)
    bus.on_any(h1)

    await bus.emit(EventType.KILL, {})
    await bus.emit(EventType.KILL, {})

    stats = bus.stats
    assert stats["total_events"] == 2
    assert stats["handler_count"] == 2
    assert stats["global_handlers"] == 1
    assert stats["active_channels"] == 2


@pytest.mark.asyncio
async def test_priority_ordering():
    """Higher priority handlers should run before lower priority."""
    bus = EventBus()
    order = []

    def low_priority(event: Event):
        order.append("low")

    def high_priority(event: Event):
        order.append("high")

    bus.on(EventType.KILL, low_priority, priority=0)
    bus.on(EventType.KILL, high_priority, priority=10)

    await bus.emit(EventType.KILL, {})

    # Sync handlers run inline in priority order
    assert order == ["high", "low"]
