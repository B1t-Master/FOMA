"""Composition root: wires configuration into running components.

Keeping all wiring here means the pieces stay small, dependency-injected and
unit-testable, and swapping a detector or adding an SSE stream later is a local
change in one place.
"""

from __future__ import annotations

import asyncio

from .config import FomaConfig
from .detection.base import Detector
from .detection.screen_detector import ScreenDetector
from .detection.uia_detector import UIADetector
from .engines.clicker import Clicker, PynputPointer
from .engines.orchestrator import Orchestrator
from .engines.state import StateMachine
from .events import EventBus
from .loggers import ConsoleLogger, JsonlLogger
from .telemetry import Telemetry, ram_sampler_task


def build_detectors(config: FomaConfig) -> list[Detector]:
    detectors: list[Detector] = []
    if config.detection.uia_enabled:
        detectors.append(
            UIADetector(
                name_patterns=config.detection.name_patterns,
                browsers=config.app.browsers,
                search_depth=config.detection.search_depth,
            )
        )
    if config.detection.screen_fallback:
        detectors.append(
            ScreenDetector(
                template_dir=config.detection.template_dir,
                confidence=config.detection.confidence,
            )
        )
    return detectors


class FomaApp:
    def __init__(self, config: FomaConfig) -> None:
        self.config = config
        self.bus = EventBus()
        self.telemetry = Telemetry()
        self.state = StateMachine()
        self.clicker = Clicker(PynputPointer(), restore_cursor=config.app.cursor_restore)
        self.orchestrator = Orchestrator(
            detectors=build_detectors(config),
            clicker=self.clicker,
            state=self.state,
            bus=self.bus,
            telemetry=self.telemetry,
            poll_interval_s=config.app.poll_interval_s,
            cooldown_s=config.app.cooldown_s,
        )
        self.console = ConsoleLogger(
            telemetry=self.telemetry,
            summary_interval_s=config.app.console_summary_interval_s,
        )
        self.jsonl = JsonlLogger(config.app.log_dir)

    def request_stop(self) -> None:
        self.orchestrator.stop()

    async def run(self) -> None:
        waiters = [
            asyncio.create_task(self.console.run(self.bus), name="console"),
            asyncio.create_task(self.jsonl.run(self.bus), name="jsonl"),
        ]
        await asyncio.sleep(0)  # let the loggers subscribe before any event is published
        tasks = [
            *waiters,
            asyncio.create_task(self.orchestrator.run(), name="orchestrator"),
            asyncio.create_task(
                ram_sampler_task(
                    self.bus,
                    self.telemetry,
                    self.config.app.ram_sample_interval_s,
                    self.orchestrator.stop_event,
                ),
                name="ram-sampler",
            ),
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
