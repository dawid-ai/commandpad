# src/actions.py
from datetime import date
from typing import Optional, Protocol, runtime_checkable
from src.models import Action
from src.tokens import expand_tokens


@runtime_checkable
class Effects(Protocol):
    def send_keys(self, keys: str) -> None: ...
    def open_target(self, target: str) -> None: ...
    def run_command(self, target: str) -> None: ...
    def type_text(self, text: str) -> None: ...


def run_action(action: Action, effects: Effects, today: Optional[date] = None) -> None:
    if action.type == "send_keys":
        effects.send_keys(action.keys or "")
    elif action.type == "open":
        effects.open_target(expand_tokens(action.target or "", today))
    elif action.type == "run":
        effects.run_command(expand_tokens(action.target or "", today))
    elif action.type == "text":
        effects.type_text(expand_tokens(action.text or "", today))
    else:
        raise ValueError(f"Unknown action type: {action.type!r}")
