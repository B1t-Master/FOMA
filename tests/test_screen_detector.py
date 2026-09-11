"""Screen-capture fallback detector tests using fakes for cv2/mss/numpy."""

from __future__ import annotations

import numpy as np

import foma.detection.screen_detector as screen_detector
from foma.detection.screen_detector import ScreenDetector


class FakeCv2:
    TM_CCOEFF_NORMED = 0
    COLOR_BGRA2GRAY = 0
    INTER_AREA = 0
    IMREAD_GRAYSCALE = 0

    def __init__(self, match_score: float, imread_ok: bool = True) -> None:
        self._score = match_score
        self._imread_ok = imread_ok

    def imread(self, *args, **kwargs):
        if not self._imread_ok:
            return None
        return np.zeros((10, 20), dtype=np.uint8)

    def cvtColor(self, frame, *args, **kwargs):
        return frame

    def resize(self, img, *args, **kwargs):
        return img

    def matchTemplate(self, img, template, method):
        return np.full((1, 1), self._score)

    def minMaxLoc(self, result):
        return (0.0, np.max(result), (0, 0), (1, 1))


class _MssInstance:
    def __init__(self) -> None:
        self.monitors: list[dict] = [{}]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def grab(self, monitor):
        return np.zeros((100, 100, 4), dtype=np.uint8)


class FakeMss:
    """Module-level fake: ``FakeMss.mss()`` yields an instance."""

    def mss(self):
        return _MssInstance()


def make_detector(
    monkeypatch,
    tmp_path,
    *,
    score: float = 0.99,
    imread_ok: bool = True,
    scales=(1.0,),
):
    (tmp_path / "skip.png").write_bytes(b"fake-png")
    monkeypatch.setattr(screen_detector, "_load_cv2", lambda: FakeCv2(score, imread_ok))
    monkeypatch.setattr(screen_detector, "_load_mss", lambda: FakeMss())
    monkeypatch.setattr(screen_detector, "_load_numpy", lambda: np)
    return ScreenDetector(template_dir=tmp_path, confidence=0.85, scales=scales)


def test_no_templates_directory_returns_none(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(screen_detector, "_load_cv2", lambda: FakeCv2(0.5))
    monitor = ScreenDetector(template_dir=tmp_path / "missing", confidence=0.85)
    assert monitor.detect() is None


def test_returns_detection_above_confidence(monkeypatch, tmp_path) -> None:
    detector = make_detector(monkeypatch, tmp_path, score=0.99)
    result = detector.detect()
    assert result is not None
    assert result.confidence >= 0.85
    assert result.width > 0
    assert result.height > 0


def test_below_confidence_is_ignored(monkeypatch, tmp_path) -> None:
    detector = make_detector(monkeypatch, tmp_path, score=0.50)
    assert detector.detect() is None


def test_unreadable_template_disables_detector(monkeypatch, tmp_path) -> None:
    detector = make_detector(monkeypatch, tmp_path, imread_ok=False)
    assert detector.detect() is None
