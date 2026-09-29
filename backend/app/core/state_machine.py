from enum import Enum
from typing import Any, Callable, List, Optional


class AutomationState(str, Enum):
    IDLE = "idle"
    SEARCHING = "searching"
    AWAITING_CAPTCHA = "awaiting_captcha"
    BILLS_LOADED = "bills_loaded"
    BILL_SELECTED = "bill_selected"
    READY_TO_PRINT = "ready_to_print"
    PRINTING = "printing"
    ERROR = "error"


VALID_TRANSITIONS: dict[AutomationState, set[AutomationState]] = {
    AutomationState.IDLE: {AutomationState.SEARCHING, AutomationState.READY_TO_PRINT},
    AutomationState.SEARCHING: {AutomationState.AWAITING_CAPTCHA, AutomationState.BILLS_LOADED, AutomationState.ERROR, AutomationState.IDLE},
    AutomationState.AWAITING_CAPTCHA: {AutomationState.SEARCHING, AutomationState.BILLS_LOADED, AutomationState.ERROR},
    AutomationState.BILLS_LOADED: {AutomationState.BILL_SELECTED, AutomationState.SEARCHING, AutomationState.PRINTING, AutomationState.ERROR},
    AutomationState.BILL_SELECTED: {AutomationState.READY_TO_PRINT, AutomationState.ERROR},
    AutomationState.READY_TO_PRINT: {AutomationState.PRINTING, AutomationState.ERROR},
    AutomationState.PRINTING: {AutomationState.IDLE, AutomationState.ERROR},
    AutomationState.ERROR: {AutomationState.IDLE, AutomationState.SEARCHING, AutomationState.PRINTING},
}

StateChangeListener = Callable[[AutomationState, AutomationState], None]


class StateMachine:
    def __init__(self) -> None:
        self._current_state: AutomationState = AutomationState.IDLE
        self._listeners: List[StateChangeListener] = []

    @property
    def current_state(self) -> AutomationState:
        return self._current_state

    def transition(self, new_state: AutomationState) -> None:
        allowed = VALID_TRANSITIONS.get(self._current_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self._current_state.value} -> {new_state.value}"
            )
        old_state = self._current_state
        self._current_state = new_state
        self._notify_listeners(old_state, new_state)

    def add_listener(self, listener: StateChangeListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: StateChangeListener) -> None:
        self._listeners.remove(listener)

    def reset(self) -> None:
        old_state = self._current_state
        self._current_state = AutomationState.IDLE
        self._notify_listeners(old_state, AutomationState.IDLE)

    def _notify_listeners(self, old_state: AutomationState, new_state: AutomationState) -> None:
        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception:
                pass
