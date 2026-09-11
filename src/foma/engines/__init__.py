"""Automation engines: clicking, state tracking, orchestration."""

from .clicker import Clicker, ClickResult, PynputPointer
from .orchestrator import Orchestrator
from .state import IllegalTransition, State, StateMachine

__all__ = [
    "ClickResult",
    "Clicker",
    "IllegalTransition",
    "Orchestrator",
    "PynputPointer",
    "State",
    "StateMachine",
]
