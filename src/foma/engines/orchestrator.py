"""Async main loop wiring detectors, clicker, state and telemetry together.

The loop is intentionally dumb and small:

    poll -> detect -> (if found) click -> publish events -> drift-correct sleep

Detection runs in a worker thread (``asyncio.to_thread``) so a slow UIA scan
never blocks the event loop. Every tick publishes to the event bus, which the
console and JSONL loggers consume.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress

from ..detection.base import Detection, Detector
from ..events import Event, EventBus
from ..telemetry.metrics import Telemetry
from .clicker import Clicker
from .state import State, StateMachine


class Orchestrator:
    def __init__(
        self,
        detectors: list[Detector],
        clicker: Clicker,
        state: StateMachine,
        bus: EventBus,
        telemetry: Telemetry,
        poll_interval_s: float = 0.5,
        cooldown_s: float = 4.0,
        clock: Callable[[], float] = time.monotonic,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        if not detectors:
            raise ValueError("at least one detector is required")
        self._detectors = detectors
        self._clicker = clicker
        self._state = state
        self._bus = bus
        self._telemetry = telemetry
        self._poll_interval_s = poll_interval_s
        self._cooldown_s = cooldown_s
        self._clock = clock
        self._stop = stop_event if stop_event is not None else asyncio.Event()
        self._ready_at = 0.0
        self._last_detector_name = ""

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop

    @property
    def telemetry(self) -> Telemetry:
        return self._telemetry

    @property
    def state(self) -> StateMachine:
        return self._state

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        try:
            await self._bus.publish(
                Event(
                    "startup",
                    {
                        "detectors": [d.name for d in self._detectors],
                        "poll_interval_s": self._poll_interval_s,
                    },
                )
            )
            while not self._stop.is_set():
                tick_started = self._clock()
                try:
                    await self._tick()
                except Exception as exc:
                    self._telemetry.record_error()
                    await self._bus.publish(
                        Event("error", {"type": type(exc).__name__, "message": str(exc)})
                    )
                elapsed = self._clock() - tick_started
                await self._sleep(max(0.0, self._poll_interval_s - elapsed))
        finally:
            await self._bus.publish(
                Event(
                    "shutdown",
                    {"state": self._state.state.value, "uptime_s": self._telemetry.uptime_s},
                )
            )

    async def run_once(self) -> bool:
        """Single detection+click pass; used by tests and ``--once``."""
        found = False
        t0 = self._clock()
        detection, errors = await asyncio.to_thread(self._detect_once)
        await self._publish_errors(errors)
        if detection is not None:
            found = True
            detect_ms = (self._clock() - t0) * 1000.0
            await self._publish_detection(detection, detect_ms)
            await self._action(detection)
        return found

    async def _tick(self) -> None:
        if self._state.state is State.PAUSED:
            return
        if self._clock() < self._ready_at:
            return
        t0 = self._clock()
        detection, errors = await asyncio.to_thread(self._detect_once)
        await self._publish_errors(errors)
        if detection is None:
            return
        detect_ms = (self._clock() - t0) * 1000.0
        await self._publish_detection(detection, detect_ms)
        await self._action(detection)

    async def _publish_errors(self, errors: list[tuple[str, str]]) -> None:
        for detector_name, message in errors:
            await self._bus.publish(
                Event("error", {"detector": detector_name, "message": message})
            )

    async def _publish_detection(self, detection: Detection, detect_ms: float) -> None:
        self._telemetry.record_detection(detect_ms)
        await self._bus.publish(
            Event(
                "ad_detected",
                {
                    "x": detection.x,
                    "y": detection.y,
                    "width": detection.width,
                    "height": detection.height,
                    "confidence": round(detection.confidence, 3),
                    "detector": self._last_detector_name,
                    "latency_ms": round(detect_ms, 2),
                },
            )
        )

    async def _action(self, detection: Detection) -> None:
        if self._state.state is not State.IDLE:
            return
        self._state.transition(State.SKIPPING)
        cx, cy = detection.center
        try:
            result = await asyncio.to_thread(self._clicker.click, cx, cy)
        except Exception as exc:
            self._state.reset()
            self._telemetry.record_error()
            await self._bus.publish(
                Event("error", {"type": type(exc).__name__, "message": str(exc)})
            )
            return
        self._state.transition(State.SKIPPED)
        self._state.transition(State.IDLE)
        self._ready_at = self._clock() + self._cooldown_s
        self._telemetry.record_skip(result.latency_ms)
        await self._bus.publish(
            Event(
                "skip_clicked",
                {
                    "x": cx,
                    "y": cy,
                    "click_latency_ms": round(result.latency_ms, 2),
                    "cooldown_until": self._ready_at,
                },
            )
        )

    def _detect_once(self) -> tuple[Detection | None, list[tuple[str, str]]]:
        errors: list[tuple[str, str]] = []
        for detector in self._detectors:
            try:
                detection = detector.detect()
            except Exception as exc:
                self._telemetry.record_error()
                errors.append((detector.name, f"{type(exc).__name__}: {exc}"))
                continue
            if detection is not None:
                self._last_detector_name = detector.name
                return detection, errors
        return None, errors

    async def _sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        with suppress(TimeoutError):
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
