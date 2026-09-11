"""Console logger: readable lines for the background process window.

Also emits a periodic telemetry summary (RAM + latency) on the configured
interval so the user always has a live health line while FOMA runs.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from datetime import datetime
from typing import TextIO

from ..events import Event, EventBus
from ..telemetry.metrics import Telemetry

_TYPE_LABELS = {
    "startup": "STARTUP",
    "shutdown": "SHUTDOWN",
    "ad_detected": "AD_DETECTED",
    "skip_clicked": "SKIP_CLICKED",
    "ram_sample": "RAM_SAMPLE",
    "error": "ERROR",
}


class ConsoleLogger:
    def __init__(
        self,
        telemetry: Telemetry,
        summary_interval_s: float = 30.0,
        stream: TextIO = sys.stdout,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._telemetry = telemetry
        self._summary_interval_s = summary_interval_s
        self._stream = stream
        self._clock = clock

    async def run(self, bus: EventBus) -> None:
        queue = bus.subscribe()
        last_summary = self._clock()
        try:
            while True:
                timeout = max(0.0, last_summary + self._summary_interval_s - self._clock())
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout or None)
                except TimeoutError:
                    self._print_summary(final=False)
                    last_summary = self._clock()
                    continue
                self._print_event(event)
                if self._clock() - last_summary >= self._summary_interval_s:
                    self._print_summary(final=False)
                    last_summary = self._clock()
                if event.type == "shutdown":
                    break
        finally:
            bus.unsubscribe(queue)

    def _print_event(self, event: Event) -> None:
        label = _TYPE_LABELS.get(event.type, event.type.upper())
        ts = datetime.fromtimestamp(event.ts).strftime("%H:%M:%S")
        self._stream.write(f"[{ts}] {label} {self._describe(event)}\n")
        self._stream.flush()

    def _describe(self, event: Event) -> str:
        d = event.data
        if event.type == "ad_detected":
            return (
                f"rect=({d['x']},{d['y']},{d['width']}x{d['height']}) "
                f"detector={d.get('detector', '?')} detect_ms={d.get('latency_ms', 0)}"
            )
        if event.type == "skip_clicked":
            return f"at=({d['x']},{d['y']}) click_ms={d.get('click_latency_ms', 0)}"
        if event.type == "ram_sample":
            return f"ram_mb={d['ram_mb']}"
        if event.type == "error":
            return f"{d.get('type', '')}: {d.get('message', '')}"
        if event.type == "startup":
            return f"detectors=[{','.join(d.get('detectors', []))}]"
        if event.type == "shutdown":
            return f"state={d.get('state')} uptime_s={d.get('uptime_s', 0)}"
        return f"{d}"

    def _print_summary(self, final: bool) -> None:
        s = self._telemetry.summary()
        heading = "FINAL SUMMARY" if final else "TELEMETRY"
        line = (
            f"[{datetime.now().strftime('%H:%M:%S')}] {heading} "
            f"ram_mb={s['ram_mb']:.2f} peak_mb={s['peak_ram_mb']:.2f} "
            f"avg_total_ms={s['avg_total_ms']:.2f} last_total_ms={s['last_total_ms']:.2f} "
            f"detect_ms={s['avg_detect_ms']:.2f} skipped={s['ads_skipped']} "
            f"detections={s['detections']} errors={s['errors']}"
        )
        self._stream.write(line + "\n")
        self._stream.flush()
