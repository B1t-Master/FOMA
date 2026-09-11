"""Event bus tests."""

from __future__ import annotations

import asyncio
import json

from foma.events import Event, EventBus


async def test_publish_delivers_to_all_subscribers() -> None:
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    await bus.publish(Event("ad_detected", {"x": 1}))
    e1 = await asyncio.wait_for(q1.get(), timeout=1)
    e2 = await asyncio.wait_for(q2.get(), timeout=1)
    assert e1.type == "ad_detected"
    assert e2.type == "ad_detected"
    assert bus.subscriber_count == 2


async def test_unsubscribe_removes_queue() -> None:
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    assert bus.subscriber_count == 0
    await bus.publish(Event("heartbeat"))
    assert q.empty()


async def test_full_queue_drops_oldest() -> None:
    bus = EventBus(maxsize=2)
    q = bus.subscribe()
    events = [Event(f"e{i}") for i in range(4)]
    for event in events:
        await bus.publish(event)
    got = [q.get_nowait().type for _ in range(2)]
    assert got == ["e2", "e3"]


def test_event_to_json_roundtrip() -> None:
    event = Event("skip_clicked", {"x": 10, "y": 20}, ts=1234.0)
    payload = json.loads(event.to_json())
    assert payload == {"type": "skip_clicked", "ts": 1234.0, "data": {"x": 10, "y": 20}}


def test_event_to_dict() -> None:
    event = Event("ad_detected", {"width": 100, "height": 40}, ts=1.0)
    assert event.to_dict()["data"]["width"] == 100
