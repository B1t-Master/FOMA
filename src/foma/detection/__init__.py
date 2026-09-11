"""Detector abstraction and concrete detection strategies."""

from .base import Detection, Detector
from .screen_detector import ScreenDetector
from .uia_detector import UIADetector

__all__ = ["Detection", "Detector", "ScreenDetector", "UIADetector"]
