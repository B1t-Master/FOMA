"""Primary detector: Windows UI Automation.

Reads the accessibility tree of the running browser. The "Skip Ad" button is
found by its accessible name (e.g. "Skip Ad") and role (Button), not by pixels,
so resolution, zoom level, colour scheme, view mode and DPI scaling are all
irrelevant. The OS gives us the button's exact on-screen rectangle, which the
click engine then targets.

Supports Chrome/Edge (``Chrome_WidgetWin_1``) and Firefox (``MozillaWindowClass``).
"""

from __future__ import annotations

import re

from .base import Detection, Detector

BROWSER_CLASSES: dict[str, tuple[str, ...]] = {
    "chrome": ("Chrome_WidgetWin_1",),
    "edge": ("Chrome_WidgetWin_1",),
    "firefox": ("MozillaWindowClass",),
}

# How many candidate matches to probe per control type before giving up.
_MAX_MATCHES = 6

# Per-probe existence timeout. When no ad is playing the skip button is absent,
# so this bounds the cost of a "miss" (short) while keeping hits instant.
_EXISTS_TIMEOUT_S = 0.03


def _load_uiautomation():
    """Lazily import the Windows UIA wrapper (keeps tests dependency-free)."""
    import uiautomation as auto

    return auto


class UIADetector(Detector):
    name = "uia"

    def __init__(
        self,
        name_patterns: tuple[str, ...] = (".*skip.*ad.*", ".*ad.*skip.*"),
        browsers: tuple[str, ...] = ("chrome", "firefox"),
        search_depth: int = 24,
        _auto_module=None,
    ) -> None:
        self._joined_pattern = "|".join(f"(?:{p})" for p in name_patterns)
        self._matched_name = re.compile(self._joined_pattern, re.IGNORECASE)
        self._classes: set[str] = set()
        for browser in browsers:
            self._classes.update(BROWSER_CLASSES.get(browser, ()))
        self._search_depth = search_depth
        self._auto_module = _auto_module

    def detect(self) -> Detection | None:
        auto = self._auto_module if self._auto_module is not None else _load_uiautomation()
        root = auto.GetRootControl()
        for window in root.GetChildren():
            try:
                if not self._is_browser_window(window):
                    continue
                button = self._find_skip_button(auto, window)
                if button is not None:
                    return self._to_detection(button)
            except Exception:
                continue
        return None

    def _is_browser_window(self, window) -> bool:
        if window.ClassName not in self._classes:
            return False
        return bool(getattr(window, "IsVisible", True))

    def _find_skip_button(self, auto, window):
        for control_type in (
            auto.ControlType.ButtonControl,
            auto.ControlType.CustomControl,
        ):
            for index in range(1, _MAX_MATCHES + 1):
                candidate = window.Control(
                    searchDepth=self._search_depth,
                    foundIndex=index,
                    ControlType=control_type,
                    RegexName=self._matched_name.pattern,
                )
                if not candidate.Exists(_EXISTS_TIMEOUT_S):
                    break
                name = candidate.Name or ""
                if self._matched_name.match(name) and not candidate.IsOffscreen:
                    return candidate
        return None

    def _to_detection(self, button) -> Detection | None:
        rect = button.BoundingRectangle
        width = int(rect.right) - int(rect.left)
        height = int(rect.bottom) - int(rect.top)
        if width <= 0 or height <= 0:
            return None
        return Detection(
            x=int(rect.left),
            y=int(rect.top),
            width=width,
            height=height,
            confidence=1.0,
        )
