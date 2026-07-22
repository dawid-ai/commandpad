from src.engine import Engine
from src.config import parse_config


def _config():
    return parse_config({
        "controls": {"k1": "f13"},
        "profiles": [
            {"name": "Obsidian", "color": "#8b5cf6", "match": {"process": ["Obsidian.exe"]},
             "keys": {"k1": {"label": "Search", "action": {"type": "send_keys", "keys": "ctrl+shift+f"}}}},
            {"name": "Default", "color": "#2d2d2d", "match": {"process": ["*"]},
             "keys": {"k1": {"label": "Copy", "action": {"type": "send_keys", "keys": "ctrl+c"}}}},
        ],
    })


class FakeDetector:
    def __init__(self, proc="Obsidian.exe", title=""):
        self.proc, self.title = proc, title
    def current(self):
        return (self.proc, self.title)


class FakeEffects:
    def __init__(self):
        self.calls = []
    def send_keys(self, keys): self.calls.append(("send_keys", keys))
    def open_target(self, t): self.calls.append(("open", t))
    def run_command(self, t): self.calls.append(("run", t))
    def type_text(self, t): self.calls.append(("text", t))


def test_signal_fires_active_profile_action():
    fx = FakeEffects()
    eng = Engine(_config(), FakeDetector("Obsidian.exe"), fx)
    eng.handle_signal("f13")
    assert fx.calls == [("send_keys", "ctrl+shift+f")]


def test_same_signal_different_app_different_action():
    fx = FakeEffects()
    det = FakeDetector("notepad.exe")           # falls to Default
    eng = Engine(_config(), det, fx)
    eng.handle_signal("f13")
    assert fx.calls == [("send_keys", "ctrl+c")]


def test_unmapped_signal_is_ignored():
    fx = FakeEffects()
    eng = Engine(_config(), FakeDetector("Obsidian.exe"), fx)
    eng.handle_signal("f99")                     # no control
    assert fx.calls == []


def test_profile_change_callback_fires_on_switch():
    seen = []
    eng = Engine(_config(), FakeDetector("Obsidian.exe"), FakeEffects(),
                 on_profile_change=lambda p: seen.append(p.name))
    eng.refresh_profile()
    eng.detector.proc = "notepad.exe"
    eng.refresh_profile()
    assert seen == ["Obsidian", "Default"]


class RaisingEffects(FakeEffects):
    def send_keys(self, keys):
        raise RuntimeError("boom")


def _config_with_two_controls():
    return parse_config({
        "controls": {"k1": "f13", "k2": "f14"},
        "profiles": [
            {"name": "Obsidian", "color": "#8b5cf6", "match": {"process": ["Obsidian.exe"]},
             "keys": {
                 "k1": {"label": "Search", "action": {"type": "send_keys", "keys": "ctrl+shift+f"}},
                 "k2": {"label": "Open", "action": {"type": "open", "target": "http://example.com"}},
             }},
        ],
    })


def test_throwing_action_does_not_propagate():
    fx = RaisingEffects()
    eng = Engine(_config_with_two_controls(), FakeDetector("Obsidian.exe"), fx)
    eng.handle_signal("f13")          # maps to send_keys, which raises internally -- must not propagate
    assert fx.calls == []             # RaisingEffects raises before recording the call
    # the listener/engine must still work for other signals after a failure
    eng.handle_signal("f14")
    assert fx.calls == [("open", "http://example.com")]
