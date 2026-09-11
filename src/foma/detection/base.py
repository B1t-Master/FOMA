"""Shared detection primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    """A screen rectangle where a target button was found."""

    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


class Detector(ABC):
    """A strategy that can find the skip button on screen."""

    name: str = "detector"

    @abstractmethod
    def detect(self) -> Detection | None:
        """Return the button rectangle, or None when not present."""
        raise NotImplementedError
