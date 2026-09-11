"""Telemetry tests."""

from __future__ import annotations

import asyncio

from foma.events import EventBus
from foma.telemetry.metrics import Telemetry, ram_sampler_task


def make_telemetry(memory_mb: float = 10.0) -> Telemetry:
    return Telemetry(memory_probe=lambda: memory_mb)


def test_detection_and_skip_counting() -> None:
    telemetry = make_telemetry()
    telemetry.record_detection(5.0)
    telemetry.record_detection(15.0)
    telemetry.record_skip(20.0)
    telemetry.record_skip(40.0)
    assert telemetry.detections == 2
    assert telemetry.ads_skipped == 2
    assert telemetry.avg_detect_latency_ms() == 10.0
    assert telemetry.avg_total_latency_ms() == 30.0
    assert telemetry.summary()["last_total_ms"] == 40.0


def test_latency_window_trims_old_samples() -> None:
    telemetry = Telemetry(window=3, memory_probe=lambda: 1.0)
    for value in (1.0, 2.0, 3.0, 4.0):
        telemetry.record_skip(value)
    assert telemetry.avg_total_latency_ms() == 3.0


def test_ram_sample_tracks_current_and_peak() -> None:
    values = iter([10.0, 12.0, 9.0])
    telemetry = Telemetry(memory_probe=lambda: next(values))
    telemetry.sample_ram()
    telemetry.sample_ram()
    telemetry.sample_ram()
    assert telemetry.last_ram_mb == 9.0
    assert telemetry.peak_ram_mb == 12.0


def test_summary_shape() -> None:
    telemetry = make_telemetry(memory_mb=18.4)
    telemetry.sample_ram()
    telemetry.record_skip(42.0)
    summary = telemetry.summary()
    for key in (
        "uptime_s",
        "ram_mb",
        "peak_ram_mb",
        "avg_detect_ms",
        "avg_total_ms",
        "last_total_ms",
        "ads_skipped",
        "detections",
        "errors",
    ):
        assert key in summary
    assert summary["ram_mb"] == 18.4
    assert summary["ads_skipped"] == 1


def test_error_counting() -> None:
    telemetry = make_telemetry()
    telemetry.record_error()
    telemetry.record_error()
    assert telemetry.errors == 2


async def test_ram_sampler_publishes_and_stops() -> None:
    bus = EventBus()
    telemetry = make_telemetry(memory_mb=21.0)
    stop = asyncio.Event()
    task = asyncio.create_task(ram_sampler_task(bus, telemetry, interval_s=60, stop_event=stop))
    queue = bus.subscribe()
    try:
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event.type == "ram_sample"
        assert event.data["ram_mb"] == 21.0
        stop.set()
        await asyncio.wait_for(task, timeout=1)
    finally:
        task.cancel()
        bus.unsubscribe(queue)
