"""Click engine tests."""

from __future__ import annotations

from foma.engines.clicker import Clicker

from .conftest import FakeClock, FakePointer


def test_click_moves_pointer_and_restores() -> None:
    pointer = FakePointer(position=(50, 60))
    clicker = Clicker(pointer, restore_cursor=True)
    result = clicker.click(100, 120)
    assert pointer.clicks == 1
    assert pointer.last_position == (100, 120)
    assert pointer.position == (50, 60)
    assert result.was_clicked is True


def test_no_restore_leaves_pointer_at_target() -> None:
    pointer = FakePointer(position=(50, 60))
    clicker = Clicker(pointer, restore_cursor=False)
    clicker.click(100, 120)
    assert pointer.position == (100, 120)


def test_latency_reported_in_milliseconds() -> None:
    clock = FakeClock(0.0)
    pointer = FakePointer(clock=clock)
    clicker = Clicker(pointer, restore_cursor=True, clock=clock)
    result = clicker.click(10, 20)
    assert result.latency_ms == 50.0


def test_latency_never_negative() -> None:
    pointer = FakePointer()
    clicker = Clicker(pointer, clock=lambda: 10.0)
    result = clicker.click(10, 20)
    assert result.latency_ms >= 0.0
