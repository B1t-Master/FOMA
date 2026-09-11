"""Minimal state machine for the ad-skip lifecycle.

    idle --detected--> skipping --clicked--> skipped --(next poll)--> idle
    idle ----------------pause----------> paused --resume--> idle
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum


class State(Enum):
    IDLE = "idle"
    PAUSED = "paused"
    SKIPPING = "skipping"
    SKIPPED = "skipped"


_TRANSITIONS: dict[State, frozenset[State]] = {
    State.IDLE: frozenset({State.SKIPPING, State.PAUSED}),
    State.SKIPPING: frozenset({State.SKIPPED}),
    State.SKIPPED: frozenset({State.IDLE}),
    State.PAUSED: frozenset({State.IDLE}),
}


class IllegalTransition(ValueError):
    def __init__(self, current: State, target: State) -> None:
        super().__init__(f"illegal transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


class StateMachine:
    def __init__(self) -> None:
        self._state = State.IDLE
        self._listeners: list[Callable[[State], None]] = []

    @property
    def state(self) -> State:
        return self._state

    def on_change(self, listener: Callable[[State], None]) -> None:
        self._listeners.append(listener)

    def transition(self, target: State) -> None:
        if target not in _TRANSITIONS[self._state]:
            raise IllegalTransition(self._state, target)
        self._state = target
        self._notify()

    def pause(self) -> None:
        if self._state is not State.PAUSED:
            self._state = State.PAUSED
            self._notify()

    def resume(self) -> None:
        if self._state is State.PAUSED:
            self._state = State.IDLE
            self._notify()

    def reset(self) -> None:
        if self._state is not State.IDLE:
            self._state = State.IDLE
            self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener(self._state)
