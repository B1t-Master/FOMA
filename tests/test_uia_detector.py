"""UIA detector tests against a fake UIA module."""

from __future__ import annotations

import types

from foma.detection.base import Detection
from foma.detection.uia_detector import UIADetector


class FakeRect:
    left = 100
    top = 200
    right = 280
    bottom = 240


class FakeControlProxy:
    """Emulates what ``window.Control(...)`` yields in the real library."""

    BoundingRectangle: object

    def __init__(self, present: bool, name: str = "", offscreen: bool = False) -> None:
        self._present = present
        self.Name = name
        self.IsOffscreen = offscreen
        self.BoundingRectangle = FakeRect()
        self.requested: dict | None = None

    def Exists(self, timeout: float) -> bool:
        return self._present


class FakeWindow:
    def __init__(
        self,
        proxy: FakeControlProxy,
        class_name: str = "Chrome_WidgetWin_1",
        visible: bool = True,
    ) -> None:
        self.ClassName = class_name
        self.IsVisible = visible
        self._proxy = proxy

    def Control(self, **kwargs) -> FakeControlProxy:
        self._proxy.requested = kwargs
        return self._proxy


class FakeRoot:
    def __init__(self, *windows: FakeWindow) -> None:
        self._windows = windows

    def GetChildren(self):
        return self._windows


class FakeAuto:
    ControlType = types.SimpleNamespace(ButtonControl=1, CustomControl=2)

    def __init__(self, root: FakeRoot) -> None:
        self._root = root

    def GetRootControl(self):
        return self._root


def make_detector(auto: FakeAuto, patterns=(".*skip.*ad.*",)):
    return UIADetector(name_patterns=tuple(patterns), browsers=("chrome",), _auto_module=auto)


def test_finds_skip_button_in_chrome_window() -> None:
    proxy = FakeControlProxy(present=True, name="Skip Ad")
    auto = FakeAuto(FakeRoot(FakeWindow(proxy)))
    result = make_detector(auto).detect()
    assert result == Detection(x=100, y=200, width=180, height=40, confidence=1.0)
    assert result.center == (190, 220)
    assert proxy.requested is not None
    assert proxy.requested["searchDepth"] == 24


def test_patterns_are_case_insensitive() -> None:
    proxy = FakeControlProxy(present=True, name="sKiP Ad")
    auto = FakeAuto(FakeRoot(FakeWindow(proxy)))
    assert make_detector(auto).detect() is not None


def test_ignores_foreign_windows() -> None:
    proxy = FakeControlProxy(present=True, name="Skip Ad")
    window = FakeWindow(proxy, class_name="SomeOtherClass")
    auto = FakeAuto(FakeRoot(window))
    assert make_detector(auto).detect() is None


def test_browser_filter_excludes_offscreen_button() -> None:
    proxy = FakeControlProxy(present=True, name="Skip Ad", offscreen=True)
    auto = FakeAuto(FakeRoot(FakeWindow(proxy)))
    assert make_detector(auto).detect() is None


def test_missing_button_returns_none() -> None:
    proxy = FakeControlProxy(present=False, name="Skip Ad")
    auto = FakeAuto(FakeRoot(FakeWindow(proxy)))
    assert make_detector(auto).detect() is None


def test_name_not_matching_pattern_is_ignored() -> None:
    proxy = FakeControlProxy(present=True, name="Volume Slider")
    auto = FakeAuto(FakeRoot(FakeWindow(proxy)))
    assert make_detector(auto).detect() is None


def test_firefox_only_configured_ignores_chrome() -> None:
    proxy = FakeControlProxy(present=True, name="Skip Ad")
    auto = FakeAuto(FakeRoot(FakeWindow(proxy)))
    detector = UIADetector(browsers=("firefox",), _auto_module=auto)
    assert detector.detect() is None


def test_no_windows_returns_none() -> None:
    auto = FakeAuto(FakeRoot())
    assert make_detector(auto).detect() is None


def test_empty_rect_is_rejected() -> None:
    class DegenerateRect:
        left = 0
        top = 0
        right = 0
        bottom = 0

    proxy = FakeControlProxy(present=True, name="Skip Ad")
    proxy.BoundingRectangle = DegenerateRect()
    auto = FakeAuto(FakeRoot(FakeWindow(proxy)))
    assert make_detector(auto).detect() is None


def test_exception_in_window_loop_is_swallowed() -> None:
    class ExplodingWindow(FakeWindow):
        def Control(self, **kwargs):
            raise RuntimeError("COM failed")

    proxy = FakeControlProxy(present=True, name="Skip Ad")
    auto = FakeAuto(FakeRoot(ExplodingWindow(proxy)))
    assert make_detector(auto).detect() is None

    # A later healthy window still produces a result.
    auto2 = FakeAuto(FakeRoot(ExplodingWindow(proxy), FakeWindow(proxy)))
    assert make_detector(auto2).detect() is not None
