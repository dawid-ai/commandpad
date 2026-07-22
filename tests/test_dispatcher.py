from src.dispatcher import signal_to_control, match_profile, resolve_action
from src.models import Action, KeyBinding, Match, Profile, Config, Settings


def _profiles():
    obs = Profile("Obsidian", "#8b5cf6", Match(process=["Obsidian.exe"]),
                  {"k1": KeyBinding("Today", Action("open", target="x"))})
    gh = Profile("GitHub", "#111", Match(process=[], title=r"github\.com"), {})
    default = Profile("Default", "#2d2d2d", Match(process=["*"]), {})
    return [gh, obs, default]


def test_signal_to_control_found():
    c = Config(Settings(), {"k1": "f13", "knob1.cw": "ctrl+alt+shift+f14"}, [])
    assert signal_to_control(c, "ctrl+alt+shift+f14") == "knob1.cw"


def test_signal_to_control_missing():
    c = Config(Settings(), {"k1": "f13"}, [])
    assert signal_to_control(c, "f99") is None


def test_match_by_process_case_insensitive():
    p = match_profile(_profiles(), "obsidian.exe", "Some Note - Obsidian")
    assert p.name == "Obsidian"


def test_title_beats_process():
    # Chrome focused on github.com -> GitHub profile wins over any process match
    p = match_profile(_profiles(), "chrome.exe", "Pull Requests · github.com")
    assert p.name == "GitHub"


def test_falls_back_to_default():
    p = match_profile(_profiles(), "notepad.exe", "Untitled")
    assert p.name == "Default"


def test_resolve_action_hit_and_miss():
    obs = _profiles()[1]
    assert resolve_action(obs, "k1").type == "open"
    assert resolve_action(obs, "k9") is None
