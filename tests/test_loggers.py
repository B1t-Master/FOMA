"""Console and JSONL logger tests."""

from __future__ import annotations

import asyncio
import io
import json
from datetime import datetime

from foma.events import Event, EventBus
from foma.loggers import ConsoleLogger, JsonlLogger
from foma.telemetry.metrics import Telemetry

EVENT = Event(
    "ad_detected",
    {"x": 100, "y": 200, "width": 120, "height": 40, "detector": "uia", "latency_ms": 3.2},
    ts=1_700_000_000.0,
)


def test_jsonl_writes_events_in_order(tmp_path) -> None:
    logger = JsonlLogger(tmp_path)
    logger._write(Event("startup", {"detectors": ["uia"]}, ts=1.0))
    logger._write(Event("skip_clicked", {"x": 1}, ts=2.0))
    logger.close()
    day = datetime.now().strftime("%Y-%m-%d")
    lines = (tmp_path / f"foma-{day}.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["type"] == "startup"
    assert json.loads(lines[1])["type"] == "skip_clicked"


def test_jsonl_rotates_by_day(tmp_path, monkeypatch) -> None:
    import foma.loggers.jsonl_logger as jsonl_module

    class FakeDatetime:
        current = datetime(2026, 9, 11, 10, 0, 0)

        @classmethod
        def now(cls):
            return cls.current

    monkeypatch.setattr(jsonl_module, "datetime", FakeDatetime)
    logger = JsonlLogger(tmp_path)
    logger._write(Event("startup", ts=1.0))
    FakeDatetime.current = datetime(2026, 9, 12, 9, 0, 0)
    logger._write(Event("startup", ts=2.0))
    logger.close()
    assert (tmp_path / "foma-2026-09-11.jsonl").exists()
    assert (tmp_path / "foma-2026-09-12.jsonl").exists()


def test_jsonl_run_loop_ends_on_shutdown(tmp_path) -> None:
    bus = EventBus()
    logger = JsonlLogger(tmp_path)

    async def drive():
        task = asyncio.create_task(logger.run(bus))
        await asyncio.sleep(0)  # let the logger subscribe first
        await bus.publish(Event("startup", ts=1.0))
        await bus.publish(Event("shutdown", ts=2.0))
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(drive())
    day = datetime.now().strftime("%Y-%m-%d")
    content = (tmp_path / f"foma-{day}.jsonl").read_text(encoding="utf-8")
    assert '"type":"shutdown"' in content


def test_console_logs_events() -> None:
    stream = io.StringIO()
    telemetry = Telemetry(memory_probe=lambda: 15.0)
    logger = ConsoleLogger(telemetry, summary_interval_s=3600, stream=stream)

    async def drive():
        bus = EventBus()
        task = asyncio.create_task(logger.run(bus))
        await asyncio.sleep(0)  # let the logger subscribe first
        await bus.publish(EVENT)
        await bus.publish(Event("skip_clicked", {"x": 160, "y": 220, "click_latency_ms": 40.0}))
        await bus.publish(Event("shutdown", {"state": "idle", "uptime_s": 5.0}))
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(drive())
    output = stream.getvalue()
    assert "AD_DETECTED" in output
    assert "detector=uia" in output
    assert "SKIP_CLICKED" in output
    assert "SHUTDOWN" in output


def test_console_emits_periodic_summary() -> None:
    stream = io.StringIO()
    telemetry = Telemetry(memory_probe=lambda: 20.0)
    logger = ConsoleLogger(telemetry, summary_interval_s=0.01, stream=stream)

    async def drive():
        bus = EventBus()
        task = asyncio.create_task(logger.run(bus))
        await asyncio.sleep(0)  # let the logger subscribe first
        await bus.publish(Event("ram_sample", {"ram_mb": 20.0}))
        await asyncio.sleep(0.03)  # let the summary timer fire
        await bus.publish(Event("shutdown", {"state": "idle", "uptime_s": 0.1}))
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(drive())
    assert "TELEMETRY" in stream.getvalue()
    assert "ram_mb=" in stream.getvalue()


def test_summary_reading_telemetry() -> None:
    stream = io.StringIO()
    telemetry = Telemetry(memory_probe=lambda: 18.4)
    telemetry.sample_ram()
    telemetry.record_skip(42.0)
    logger = ConsoleLogger(telemetry, summary_interval_s=3600, stream=stream)
    logger._print_summary(final=True)
    assert "FINAL SUMMARY" in stream.getvalue()
    assert "skipped=1" in stream.getvalue()
    assert "ram_mb=18.40" in stream.getvalue()
