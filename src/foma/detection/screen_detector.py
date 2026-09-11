"""Fallback detector: screen capture + template matching.

Used only when UIA is unavailable or returns nothing. It grabs the screen with
``mss`` and runs multi-scale ``opencv`` template matching against button crops
(*.png) found in the configured template directory.

Unlike UIA this is inherently layout-sensitive: capture a fresh crop from YOUR
screen/resolution/zoom and place it in ``assets/templates/``. Each crop is
matched at several scales to tolerate minor zoom/DPI differences.
"""

from __future__ import annotations

from pathlib import Path

from .base import Detection, Detector


def _load_numpy():
    import numpy as np

    return np


def _load_mss():
    import mss

    return mss


def _load_cv2():
    import cv2

    return cv2


class ScreenDetector(Detector):
    name = "screen"

    def __init__(
        self,
        template_dir: str | Path = "assets/templates",
        confidence: float = 0.85,
        scales: tuple[float, ...] = (1.0, 0.9, 0.8, 0.7),
    ) -> None:
        self._template_dir = Path(template_dir)
        self._confidence = confidence
        self._scales = scales
        self._templates: list[tuple[object, int, int]] = []
        self._loaded = False

    def detect(self) -> Detection | None:
        if not self._ready():
            return None
        cv2 = _load_cv2()
        np = _load_numpy()
        mss = _load_mss()

        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
        frame = cv2.cvtColor(np.asarray(shot), cv2.COLOR_BGRA2GRAY)

        best: Detection | None = None
        best_score = self._confidence
        for template, tw, th in self._templates:
            for scale in self._scales:
                if scale == 1.0:
                    resized = frame
                else:
                    resized = cv2.resize(
                        frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                    )
                if resized.shape[0] < th or resized.shape[1] < tw:
                    continue
                result = cv2.matchTemplate(resized, template, cv2.TM_CCOEFF_NORMED)
                _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
                if max_val > best_score:
                    best_score = float(max_val)
                    best = Detection(
                        x=int(max_loc[0] / scale),
                        y=int(max_loc[1] / scale),
                        width=int(tw / scale),
                        height=int(th / scale),
                        confidence=best_score,
                    )
        return best

    def _ready(self) -> bool:
        cv2 = _load_cv2()
        if not self._loaded:
            if self._template_dir.is_dir():
                for png in sorted(self._template_dir.glob("*.png")):
                    template = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        th, tw = template.shape[:2]
                        self._templates.append((template, tw, th))
            self._loaded = True
        return bool(self._templates)
