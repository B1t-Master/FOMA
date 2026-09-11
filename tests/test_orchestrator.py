"""Orchestrator loop tests: detection, clicking, cooldown and error handling."""

from __future__ import annotations

import asyncio

import pytest

from foma.engines.clicker import Clicker
from foma.engines.orchestrator import Orchestrator
from foma.engines.state import State, StateMachine
from foma.events import EventBus
from foma.telemetry.metrics import Telemetry

from .conftest import DETECTION, ConstantDetector, FailingDetector, FakePointer, SequenceDetector


def build_orchestrator(
    detectors,
    poll_interval_s=0.01,
    cooldown_s=5.0,
):
    bus = EventBus()
    state = StateMachine()
    clicker = Clicker(FakePointer(), restore_cursor=True)
    orchestrator = Orchestrator(
        detectors=detectors,
        clicker=clicker,
        state=state,
        bus=bus,
        telemetry=Telemetry(memory_probe=lambda: 10.0),
        poll_interval_s=poll_interval_s,
        cooldown_s=cooldown_s,
    )
    return orchestrator, bus


async def collect(bus: EventBus, orchestrator: Orchestrator, duration: float) -> list:
    queue = bus.subscribe()
    events: list = []
    consumed = []

    async def drain():
        while True:
            event = await queue.get()
            consumed.append(event)
            events.append(event)

    drainer = asyncio.create_task(drain())
    runner = asyncio.create_task(orchestrator.run())
    try:
        await asyncio.sleep(duration)
        orchestrator.stop()
        await asyncio.wait_for(runner, timeout=2)
    finally:
        drainer.cancel()
        bus.unsubscribe(queue)
    return events


async def test_run_once_clicks_and_records() -> None:
    orch, _ = build_orchestrator([ConstantDetector(DETECTION)])
    found = await orch.run_once()
    assert found is True
    assert orch.telemetry.ads_skipped == 1
    assert orch.telemetry.detections == 1
    assert orch.state.state is State.IDLE


async def test_run_once_with_no_detection() -> None:
    orch, _ = build_orchestrator([ConstantDetector(None)])
    found = await orch.run_once()
    assert found is False
    assert orch.telemetry.detections == 0


async def test_loop_clicks_once_then_respects_cooldown() -> None:
    orch, bus = build_orchestrator([ConstantDetector(DETECTION)], cooldown_s=5.0)
    events = await collect(bus, orch, 0.06)
    assert orch.telemetry.ads_skipped == 1
    assert sum(1 for e in events if e.type == "skip_clicked") == 1
    assert sum(1 for e in events if e.type == "ad_detected") == 1


async def test_short_cooldown_allows_second_skip() -> None:
    orch, bus = build_orchestrator([ConstantDetector(DETECTION)], cooldown_s=0.001)
    await collect(bus, orch, 0.06)
    assert orch.telemetry.ads_skipped >= 2


async def test_no_detection_yields_no_ad_events() -> None:
    orch, bus = build_orchestrator([ConstantDetector(None)])
    events = await collect(bus, orch, 0.04)
    assert not any(e.type in ("ad_detected", "skip_clicked") for e in events)
    assert orch.telemetry.detections == 0


async def test_paused_skips_detection() -> None:
    detector = ConstantDetector(DETECTION)
    orch, _ = build_orchestrator([detector])
    orch.state.pause()
    await orch._tick()
    assert detector.calls == 0
    orch.state.resume()


async def test_detector_exception_recorded_and_loop_survives() -> None:
    orch, bus = build_orchestrator(
        [FailingDetector(), ConstantDetector(DETECTION)],
        cooldown_s=0.001,
    )
    events = await collect(bus, orch, 0.04)
    assert orch.telemetry.ads_skipped >= 1
    assert orch.telemetry.errors >= 1
    assert any(e.type == "error" for e in events)


async def test_first_detector_takes_priority() -> None:
    seq = SequenceDetector(DETECTION, DETECTION)
    orch, bus = build_orchestrator([seq, ConstantDetector(DETECTION)])
    queue = bus.subscribe()
    await orch.run_once()
    detectors = [
        e.data.get("detector")
        for e in drain_queue(queue)
        if e.type == "ad_detected"
    ]
    bus.unsubscribe(queue)
    assert detectors == ["seq"]


async def test_telemetry_and_state_are_exposed() -> None:
    orch, _ = build_orchestrator([ConstantDetector(DETECTION)])
    assert isinstance(orch.telemetry, Telemetry)
    assert isinstance(orch.state, StateMachine)
    assert isinstance(orch.stop_event, asyncio.Event)


async def test_no_detectors_raise() -> None:
    with pytest.raises(ValueError, match="at least one detector"):
        build_orchestrator([])


def drain_queue(queue) -> list:
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out
