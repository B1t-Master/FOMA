"""App composition tests (no real OS interaction)."""

from __future__ import annotations

import pytest

from foma.app import FomaApp, build_detectors
from foma.engines.orchestrator import Orchestrator


def test_build_detectors_obeys_config(make_config) -> None:
    config = make_config()
    assert [d.name for d in build_detectors(config)] == ["uia", "screen"]

    config = make_config(detection={"uia_enabled": False})
    assert [d.name for d in build_detectors(config)] == ["screen"]

    config = make_config(detection={"screen_fallback": False})
    assert [d.name for d in build_detectors(config)] == ["uia"]

    config = make_config(detection={"uia_enabled": False, "screen_fallback": False})
    assert build_detectors(config) == []


def test_app_requires_at_least_one_detector(make_config) -> None:
    config = make_config(detection={"uia_enabled": False, "screen_fallback": False})
    with pytest.raises(ValueError, match="at least one detector"):
        FomaApp(config)


def test_app_builds_orchestrator(make_config) -> None:
    app = FomaApp(make_config())
    assert isinstance(app.orchestrator, Orchestrator)
    assert app.telemetry.detections == 0
