from datetime import date
import pytest
from src.actions import run_action
from src.models import Action


class FakeEffects:
    def __init__(self):
        self.calls = []
    def send_keys(self, keys): self.calls.append(("send_keys", keys))
    def open_target(self, target): self.calls.append(("open", target))
    def run_command(self, target): self.calls.append(("run", target))
    def type_text(self, text): self.calls.append(("text", text))


def test_send_keys_routes():
    fx = FakeEffects()
    run_action(Action("send_keys", keys="ctrl+c"), fx)
    assert fx.calls == [("send_keys", "ctrl+c")]


def test_open_expands_tokens():
    fx = FakeEffects()
    run_action(Action("open", target="d/{today}"), fx, today=date(2026, 7, 22))
    assert fx.calls == [("open", "d/2026-07-22")]


def test_text_expands_tokens():
    fx = FakeEffects()
    run_action(Action("text", text="/note "), fx, today=date(2026, 7, 22))
    assert fx.calls == [("text", "/note ")]


def test_run_routes():
    fx = FakeEffects()
    run_action(Action("run", target="git pull"), fx)
    assert fx.calls == [("run", "git pull")]


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        run_action(Action("teleport", target="x"), FakeEffects())
