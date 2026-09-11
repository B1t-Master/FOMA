"""UIA detector tests against a fake UIA module (control tree)."""

from __future__ import annotations

import types

from foma.detection.base import Detection
from foma.detection.uia_detector import UIADetector


class FakeRect:
    left = 100
    top = 200
    right = 280
    bottom = 240


class FakeControl:
    """A node in the fake UIA tree."""

    def __init__(
        self,
        name: str = "",
        ctype: str = "ButtonControl",
        offscreen: bool = False,
        children=(),
        rect: type[FakeRect] = FakeRect,
    ) -> None:
        self.Name = name
        self.ControlTypeName = ctype
        self.IsOffscreen = offscreen
        self.BoundingRectangle = rect()
        self._children = list(children)
        self.name_reads = 0

    @property
    def Name(self) -> str:
        self.name_reads += 1
        return self._name

    @Name.setter
    def Name(self, value: str) -> None:
        self._name = value

    def GetChildren(self):
        return self._children


def btn(
    name="Skip",
    offscreen=False,
    children=(),
    ctype="ButtonControl",
    rect=FakeRect,
) -> FakeControl:
    return FakeControl(name=name, ctype=ctype, offscreen=offscreen, children=children, rect=rect)


def window(children, class_name: str = "Chrome_WidgetWin_1", visible: bool = True) -> FakeControl:
    w = FakeControl(name="", ctype="PaneControl", children=children)
    w.ClassName = class_name
    w.IsVisible = visible
    return w


class FakeRoot:
    def __init__(self, *windows) -> None:
        self._windows = list(windows)

    def GetChildren(self):
        return self._windows


class FakeAuto:
    ControlType = types.SimpleNamespace(ButtonControl=1, CustomControl=2)

    def __init__(self, root: FakeRoot) -> None:
        self._root = root

    def GetRootControl(self):
        return self._root


def make_detector(auto: FakeAuto, patterns=None, **kwargs):
    return UIADetector(
        name_patterns=tuple(patterns) if patterns else (r"skip\s*(ads?)?\s*$",),
        browsers=("chrome",),
        _auto_module=auto,
        **kwargs,
    )


def test_finds_skip_button_by_plain_name() -> None:
    auto = FakeAuto(FakeRoot(window([FakeControl(name="", children=[btn("Skip")])])))
    result = make_detector(auto).detect()
    assert result == Detection(x=100, y=200, width=180, height=40, confidence=1.0)
    assert result.center == (190, 220)


def test_finds_skip_ad_and_skip_ads_names() -> None:
    for name in ("Skip Ad", "Skip Ads"):
        auto = FakeAuto(FakeRoot(window([btn(name)])))
        assert make_detector(auto).detect() is not None, name


def test_patterns_are_case_insensitive() -> None:
    auto = FakeAuto(FakeRoot(window([btn("SKIP AD")])))
    assert make_detector(auto).detect() is not None


def test_skips_offscreen_decoys_then_finds_real_button() -> None:
    # "Skip navigation" is off-screen during playback; the visible "Skip" is the ads one.
    auto = FakeAuto(
        FakeRoot(window([btn("Skip navigation", offscreen=True), btn("Skip")]))
    )
    assert make_detector(auto).detect() is not None


def test_ignores_foreign_windows() -> None:
    auto = FakeAuto(FakeRoot(window([btn()], class_name="SomeOtherClass")))
    assert make_detector(auto).detect() is None


def test_offscreen_only_button_is_ignored() -> None:
    auto = FakeAuto(FakeRoot(window([btn(offscreen=True)])))
    assert make_detector(auto).detect() is None


def test_missing_button_returns_none() -> None:
    auto = FakeAuto(FakeRoot(window([FakeControl(name="", children=[])])))
    assert make_detector(auto).detect() is None


def test_name_not_matching_pattern_is_ignored() -> None:
    auto = FakeAuto(FakeRoot(window([btn("Volume Slider")])))
    assert make_detector(auto).detect() is None


def test_matching_non_clickable_types_are_ignored() -> None:
    auto = FakeAuto(FakeRoot(window([btn("Skip", ctype="TextControl")])))
    assert make_detector(auto).detect() is None


def test_firefox_only_configured_ignores_chrome() -> None:
    auto = FakeAuto(FakeRoot(window([btn()])))
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

    auto = FakeAuto(FakeRoot(window([btn(rect=DegenerateRect)])))
    assert make_detector(auto).detect() is None


def test_broken_subtree_does_not_abort_scan() -> None:
    class ExplodingControl(FakeControl):
        def GetChildren(self):
            raise RuntimeError("COM failed")

    auto = FakeAuto(FakeRoot(window([ExplodingControl(name=""), btn("Skip")])))
    assert make_detector(auto).detect() is not None


def test_node_budget_bounds_miss_cost() -> None:
    # Empty browser window whose subtree exceeds the budget: must return fast,
    # never walking forever. 100 controls with default budget still find.
    controls = [FakeControl(name="") for _ in range(2000)]
    auto = FakeAuto(FakeRoot(window(controls)))
    detector = make_detector(auto, max_nodes=50)
    assert detector.detect() is None
    assert detector._remaining == 0


def test_search_depth_is_respected() -> None:
    # window(0) -> container(1) -> container(2) -> button(3)
    deep = FakeControl(name="", children=[FakeControl(name="", children=[btn("Skip")])])
    auto = FakeAuto(FakeRoot(window([deep])))
    detector = make_detector(auto, search_depth=2)
    assert detector.detect() is None
    assert make_detector(auto, search_depth=3).detect() is not None
