"""Lightweight runtime metrics: click/detection latency and RAM usage.

Targets the tool's core promise of being invisible on the machine: we measure
(a) the latency of each detection→click pass in milliseconds and (b) the
process's resident set size (RSS) in MB, sampled on a timer. Everything is kept
in memory and summarised for the console and the JSONL event log.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress

from ..events import Event, EventBus


def _default_memory_probe() -> float:
    import psutil

    return psutil.Process().memory_info().rss / (1024 * 1024)


class Telemetry:
    def __init__(
        self,
        window: int = 200,
        clock: Callable[[], float] = time.time,
        memory_probe: Callable[[], float] | None = None,
    ) -> None:
        self._window = window
        self._clock = clock
        self._memory_probe = memory_probe or _default_memory_probe
        self._start = clock()
        self._detect_latencies: deque[float] = deque(maxlen=window)
        self._total_latencies: deque[float] = deque(maxlen=window)
        self._ram_samples: deque[float] = deque(maxlen=window * 4)
        self.peak_ram_mb = 0.0
        self.last_ram_mb = 0.0
        self.detections = 0
        self.ads_skipped = 0
        self.errors = 0

    @property
    def uptime_s(self) -> float:
        return max(0.0, self._clock() - self._start)

    def record_detection(self, latency_ms: float) -> None:
        self.detections += 1
        self._detect_latencies.append(latency_ms)

    def record_skip(self, total_latency_ms: float) -> None:
        self.ads_skipped += 1
        self._total_latencies.append(total_latency_ms)

    def record_error(self) -> None:
        self.errors += 1

    def sample_ram(self) -> float:
        mb = self._memory_probe()
        self.last_ram_mb = mb
        self.peak_ram_mb = max(self.peak_ram_mb, mb)
        self._ram_samples.append(mb)
        return mb

    def avg_detect_latency_ms(self) -> float:
        if not self._detect_latencies:
            return 0.0
        return sum(self._detect_latencies) / len(self._detect_latencies)

    def avg_total_latency_ms(self) -> float:
        if not self._total_latencies:
            return 0.0
        return sum(self._total_latencies) / len(self._total_latencies)

    def summary(self) -> dict:
        return {
            "uptime_s": round(self.uptime_s, 1),
            "ram_mb": round(self.last_ram_mb, 2),
            "peak_ram_mb": round(self.peak_ram_mb, 2),
            "avg_detect_ms": round(self.avg_detect_latency_ms(), 2),
            "avg_total_ms": round(self.avg_total_latency_ms(), 2),
            "last_total_ms": round(self._total_latencies[-1], 2) if self._total_latencies else 0.0,
            "ads_skipped": self.ads_skipped,
            "detections": self.detections,
            "errors": self.errors,
        }


async def ram_sampler_task(
    bus: EventBus,
    telemetry: Telemetry,
    interval_s: float,
    stop_event: asyncio.Event,
) -> None:
    """Sample RSS every ``interval_s`` seconds and publish it as events."""
    while not stop_event.is_set():
        mb = telemetry.sample_ram()
        await bus.publish(Event("ram_sample", {"ram_mb": round(mb, 2)}))
        with suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
