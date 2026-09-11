"""State machine tests."""

from __future__ import annotations

import pytest

from foma.engines.state import IllegalTransition, State, StateMachine


def test_initial_state_is_idle() -> None:
    assert StateMachine().state is State.IDLE


def test_full_skip_lifecycle() -> None:
    sm = StateMachine()
    sm.transition(State.SKIPPING)
    assert sm.state is State.SKIPPING
    sm.transition(State.SKIPPED)
    assert sm.state is State.SKIPPED
    sm.transition(State.IDLE)
    assert sm.state is State.IDLE


def test_illegal_transition_raises() -> None:
    sm = StateMachine()
    with pytest.raises(IllegalTransition):
        sm.transition(State.SKIPPED)


def test_pause_and_resume() -> None:
    sm = StateMachine()
    sm.pause()
    assert sm.state is State.PAUSED
    sm.pause()  # idempotent
    assert sm.state is State.PAUSED
    sm.resume()
    assert sm.state is State.IDLE


def test_listeners_notified_of_changes() -> None:
    sm = StateMachine()
    seen = []
    sm.on_change(lambda s: seen.append(s.value))
    sm.transition(State.SKIPPING)
    sm.pause()
    sm.resume()
    assert seen == ["skipping", "paused", "idle"]


def test_reset_returns_to_idle() -> None:
    sm = StateMachine()
    sm.transition(State.SKIPPING)
    sm.transition(State.SKIPPED)
    sm.reset()
    assert sm.state is State.IDLE
