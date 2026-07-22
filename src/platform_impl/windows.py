# src/platform_impl/windows.py
import os
import subprocess
import webbrowser
from typing import Callable

from pynput import keyboard
import win32gui
import win32process
import psutil

# Map pynput keys to our signal token names.
_MODS = {
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr,
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
}


def _mod_name(key) -> str:
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        return "ctrl"
    if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
        return "alt"
    if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
        return "shift"
    return "win"


def _key_token(key) -> str | None:
    """Return the base token for a non-modifier key, e.g. 'f13', or None to ignore."""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        return None
    name = getattr(key, "name", None)
    return name.lower() if name else None


class WindowsKeyListener:
    """Listens for the pad's collision-proof signals and reports them as
    'ctrl+alt+shift+f13'-style strings. Listen-only; does not suppress."""

    def __init__(self):
        self._listener = None
        self._down_mods = set()

    def start(self, on_signal: Callable[[str], None]) -> None:
        def on_press(key):
            if key in _MODS:
                self._down_mods.add(_mod_name(key))
                return
            base = _key_token(key)
            if not base:
                return
            parts = []
            for m in ("ctrl", "alt", "shift", "win"):
                if m in self._down_mods:
                    parts.append(m)
            parts.append(base)
            on_signal("+".join(parts))

        def on_release(key):
            if key in _MODS:
                self._down_mods.discard(_mod_name(key))

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None


class WindowsAppDetector:
    def current(self) -> tuple[str, str]:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
        proc = ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid).name()
        except Exception:
            pass
        return (proc, title)


class WindowsEffects:
    """Satisfies the Effects protocol on Windows."""

    def __init__(self):
        self._kb = keyboard.Controller()

    def send_keys(self, keys: str) -> None:
        parts = keys.lower().split("+")
        mods, main = parts[:-1], parts[-1]
        mod_keys = {"ctrl": keyboard.Key.ctrl, "alt": keyboard.Key.alt,
                    "shift": keyboard.Key.shift, "win": keyboard.Key.cmd}
        special = getattr(keyboard.Key, main, None)
        target = special if special is not None else main
        pressed = [mod_keys[m] for m in mods if m in mod_keys]
        for m in pressed:
            self._kb.press(m)
        self._kb.press(target)
        self._kb.release(target)
        for m in reversed(pressed):
            self._kb.release(m)

    def open_target(self, target: str) -> None:
        if target.startswith(("http://", "https://")):
            webbrowser.open(target)
        elif "://" in target:            # custom URI scheme, e.g. obsidian://
            os.startfile(target)
        else:
            os.startfile(target)

    def launch(self, target: str) -> None:
        os.startfile(target)

    def run_command(self, target: str) -> None:
        subprocess.Popen(target, shell=True)

    def type_text(self, text: str) -> None:
        self._kb.type(text)
