"""Shared fixtures and fakes for the FOMA test suite."""

from __future__ import annotations

import pytest

from foma.config import AppConfig, DetectionConfig, FomaConfig
from foma.detection.base import Detection, Detector

DETECTION = Detection(x=100, y=200, width=120, height=40)


@pytest.fixture
def make_config():
    def factory(**overrides):
        return FomaConfig(
            app=AppConfig(**overrides.get("app", {})),
            detection=DetectionConfig(**overrides.get("detection", {})),
        )

    return factory


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, delta: float) -> None:
        self._t += delta


class FakePointer:
    """Implements the ``Pointer`` protocol without touching the OS."""

    def __init__(self, position: tuple[int, int] = (0, 0), clock: FakeClock | None = None) -> None:
        self.position = position
        self.clock = clock
        self.clicks = 0
        self.last_position: tuple[int, int] | None = None

    def click_left(self) -> None:
        self.clicks += 1
        self.last_position = self.position
        if self.clock is not None:
            self.clock.advance(0.05)


class ConstantDetector(Detector):
    def __init__(self, detection: Detection | None) -> None:
        self.name = "const"
        self.detection = detection
        self.calls = 0

    def detect(self) -> Detection | None:
        self.calls += 1
        return self.detection


class SequenceDetector(Detector):
    def __init__(self, *results: Detection | None) -> None:
        self.name = "seq"
        self._results = list(results)
        self.calls = 0

    def detect(self) -> Detection | None:
        self.calls += 1
        return self._results.pop(0) if self._results else None


class FailingDetector(Detector):
    def __init__(self) -> None:
        self.name = "failing"

    def detect(self) -> Detection | None:
        raise RuntimeError("boom")


@pytest.fixture
def pointer():
    return FakePointer()


@pytest.fixture
def clock():
    return FakeClock()
