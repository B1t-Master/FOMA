"""Primary detector: Windows UI Automation.

Reads the accessibility tree of the running browser. The "Skip Ad" button is
found by its accessible name (e.g. "Skip", "Skip Ad", "Skip Ads") and role
(Button), not by pixels, so resolution, zoom level, colour scheme, view mode and
DPI scaling are all irrelevant. The OS gives us the button's exact on-screen
rectangle, which the click engine then targets.

The search is a bounded depth-first walk of the window's control tree done
client-side:

- the regex is matched case-insensitively (the ``uiautomation`` library's own
  ``RegexName`` filter is case-sensitive, which would hide any real "Skip" button)
- the walk is capped by a node budget so "no ad running" misses stay cheap
- a candidate is only accepted if it is a clickable control type that is
  currently on-screen, so off-screen decoys such as "Skip navigation" are skipped

Supports Chrome/Edge (``Chrome_WidgetWin_1``) and Firefox (``MozillaWindowClass``).
"""

from __future__ import annotations

import re
from typing import Any

from .base import Detection, Detector

BROWSER_CLASSES: dict[str, tuple[str, ...]] = {
    "chrome": ("Chrome_WidgetWin_1",),
    "edge": ("Chrome_WidgetWin_1",),
    "firefox": ("MozillaWindowClass",),
}

# YouTube exposes the button as just "Skip" (new UI) or "Skip Ad"/"Skip Ads"
# (legacy UI/localisations). Anchored so "Skip navigation" does not match.
DEFAULT_NAME_PATTERNS: tuple[str, ...] = (r"skip\s*(ads?)?\s*$", r".*ad.*skip.*")

# The real button lives quite deep in the browser's DOM (observable ~depth 29);
# leave generous headroom without walking the entire 128-level tree.
DEFAULT_SEARCH_DEPTH = 64

# Cap on nodes visited per window per pass, so "no ad" misses are bounded.
# YouTube's player DOM is large (2k+ nodes); leave headroom so the skip button
# is never cut off mid-scan.
_MAX_NODES = 4000

# UIA control types that are safe to click. Chrome renders HTML <button> as a
# ButtonControl; some players expose it as a custom control instead.
_CLICKABLE_TYPES = {"ButtonControl", "CustomControl"}


def _load_uiautomation():
    """Lazily import the Windows UIA wrapper (keeps tests dependency-free)."""
    import uiautomation as auto

    return auto


class UIADetector(Detector):
    name = "uia"

    def __init__(
        self,
        name_patterns: tuple[str, ...] = DEFAULT_NAME_PATTERNS,
        browsers: tuple[str, ...] = ("chrome", "firefox"),
        search_depth: int = DEFAULT_SEARCH_DEPTH,
        max_nodes: int = _MAX_NODES,
        _auto_module=None,
    ) -> None:
        self._matched_name = re.compile(
            "|".join(f"(?:{p})" for p in name_patterns), re.IGNORECASE
        )
        self._classes: set[str] = set()
        for browser in browsers:
            self._classes.update(BROWSER_CLASSES.get(browser, ()))
        self._search_depth = search_depth
        self._max_nodes = max_nodes
        self._auto_module = _auto_module
        self._remaining = max_nodes

    def detect(self) -> Detection | None:
        auto = self._auto_module if self._auto_module is not None else _load_uiautomation()
        root = auto.GetRootControl()
        for window in root.GetChildren():
            try:
                if not self._is_browser_window(window):
                    continue
                self._remaining = self._max_nodes
                button = self._find_skip_button(window)
                if button is not None:
                    return self._to_detection(button)
            except Exception:
                continue
        return None

    def _is_browser_window(self, window) -> bool:
        if window.ClassName not in self._classes:
            return False
        return bool(getattr(window, "IsVisible", True))

    def _find_skip_button(self, window) -> Any:
        stack: list[tuple[Any, int]] = [(window, 0)]
        while stack:
            if self._remaining <= 0:
                return None
            control, depth = stack.pop()
            self._remaining -= 1
            if depth > self._search_depth:
                continue
            try:
                name = control.Name or ""
            except Exception:
                continue
            if not self._matched_name.match(name):
                self._push_children(stack, control, depth)
                continue
            # Name matches: accept only if it is a clickable, on-screen control.
            try:
                if control.ControlTypeName not in _CLICKABLE_TYPES:
                    continue
                if control.IsOffscreen:
                    continue
            except Exception:
                continue
            return control
        return None

    def _push_children(self, stack: list, control: Any, depth: int) -> None:
        try:
            children = control.GetChildren()
        except Exception:
            return
        for child in children:
            stack.append((child, depth + 1))

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
