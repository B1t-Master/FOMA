"""Trusted mouse-click engine.

A real OS-level click (injected with ``pynput``) is always treated as a trusted
user gesture by the browser, which is why this beats page-context synthetic
clicks (YouTube explicitly rejects those via ``isTrusted`` checks).

The cursor is restored to its previous position after every click so the user's
hands are never fought for the mouse.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class Pointer(Protocol):
    """Anything with a movable position and a left-click."""

    @property
    def position(self) -> tuple[int, int]: ...

    @position.setter
    def position(self, value: tuple[int, int]) -> None: ...

    def click_left(self) -> None: ...


@dataclass(frozen=True)
class ClickResult:
    latency_ms: float
    was_clicked: bool


class PynputPointer:
    """Adapts a ``pynput.mouse.Controller`` to the ``Pointer`` protocol."""

    def __init__(self, controller=None) -> None:
        self._controller = controller if controller is not None else _make_controller()

    @property
    def position(self) -> tuple[int, int]:
        return self._controller.position

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        self._controller.position = value

    def click_left(self) -> None:
        self._controller.click(_button(), 1)


def _make_controller():
    from pynput.mouse import Controller

    return Controller()


def _button():
    from pynput.mouse import Button

    return Button.left


class Clicker:
    def __init__(
        self,
        pointer: Pointer,
        restore_cursor: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._pointer = pointer
        self._restore_cursor = restore_cursor
        self._clock = clock

    def click(self, x: int, y: int) -> ClickResult:
        original = self._pointer.position
        start = self._clock()
        self._pointer.position = (x, y)
        self._pointer.click_left()
        if self._restore_cursor:
            self._pointer.position = original
        else:
            self._pointer.position = (x, y)
        end = self._clock()
        return ClickResult(latency_ms=max(0.0, (end - start) * 1000.0), was_clicked=True)
