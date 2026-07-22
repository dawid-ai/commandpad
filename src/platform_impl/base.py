# src/platform_impl/base.py
from typing import Callable, Protocol


class KeyListener(Protocol):
    def start(self, on_signal: Callable[[str], None]) -> None: ...
    def stop(self) -> None: ...


class AppDetector(Protocol):
    def current(self) -> tuple[str, str]:
        """Return (process_name, window_title) of the foreground window."""
        ...
