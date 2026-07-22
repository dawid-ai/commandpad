import json
import pytest
from src.config import parse_config, load_config, ConfigError
from src.models import Config


def _valid_data():
    return {
        "settings": {"hud_mode": "pinned"},
        "controls": {"k1": "f13", "knob1.cw": "ctrl+alt+shift+f14"},
        "profiles": [
            {
                "name": "Obsidian",
                "color": "#8b5cf6",
                "match": {"process": ["Obsidian.exe"]},
                "keys": {"k1": {"label": "Today", "action": {"type": "open", "target": "x"}}},
            },
            {"name": "Default", "color": "#2d2d2d", "match": {"process": ["*"]}, "keys": {}},
        ],
    }


def test_parse_valid_config():
    c = parse_config(_valid_data())
    assert isinstance(c, Config)
    assert c.settings.hud_mode == "pinned"
    assert c.settings.theme == "dark"                       # defaulted
    assert c.controls["knob1.cw"] == "ctrl+alt+shift+f14"
    assert c.profiles[0].keys["k1"].action.type == "open"
    assert c.profiles[0].keys["k1"].action.target == "x"


def test_missing_profiles_raises():
    data = _valid_data()
    del data["profiles"]
    with pytest.raises(ConfigError):
        parse_config(data)


def test_profile_missing_name_raises():
    data = _valid_data()
    del data["profiles"][0]["name"]
    with pytest.raises(ConfigError):
        parse_config(data)


def test_bad_hud_mode_raises():
    data = _valid_data()
    data["settings"]["hud_mode"] = "sparkle"
    with pytest.raises(ConfigError):
        parse_config(data)


def test_load_config_from_file(tmp_path):
    p = tmp_path / "profiles.json"
    p.write_text(json.dumps(_valid_data()), encoding="utf-8")
    c = load_config(str(p))
    assert c.profiles[1].name == "Default"


from src.config import save_config


def test_save_then_load_round_trips(tmp_path):
    c = parse_config(_valid_data())
    path = str(tmp_path / "out.json")
    save_config(c, path)
    again = load_config(path)
    assert again.profiles[0].keys["k1"].action.target == "x"
    assert again.settings.hud_mode == "pinned"
