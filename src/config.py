# src/config.py
import json
from src.models import Action, KeyBinding, Match, Profile, Settings, Config

VALID_HUD_MODES = {"flash", "pinned", "off"}
VALID_ACTION_TYPES = {"send_keys", "open", "launch", "run", "text"}


class ConfigError(Exception):
    pass


def _parse_action(data: dict) -> Action:
    if not isinstance(data, dict) or "type" not in data:
        raise ConfigError(f"action must be an object with a 'type': {data!r}")
    t = data["type"]
    if t not in VALID_ACTION_TYPES:
        raise ConfigError(f"unknown action type: {t!r}")
    return Action(type=t, keys=data.get("keys"), target=data.get("target"), text=data.get("text"))


def _parse_binding(data: dict) -> KeyBinding:
    if "label" not in data or "action" not in data:
        raise ConfigError(f"key binding needs 'label' and 'action': {data!r}")
    return KeyBinding(label=data["label"], action=_parse_action(data["action"]))


def _parse_profile(data: dict) -> Profile:
    for req in ("name", "color", "match"):
        if req not in data:
            raise ConfigError(f"profile missing '{req}': {data!r}")
    match = data["match"]
    if not isinstance(match, dict):
        raise ConfigError(f"profile.match must be an object: {match!r}")
    keys = {cid: _parse_binding(b) for cid, b in data.get("keys", {}).items()}
    return Profile(
        name=data["name"],
        color=data["color"],
        match=Match(process=list(match.get("process", [])), title=match.get("title")),
        keys=keys,
    )


def _parse_settings(data: dict) -> Settings:
    s = Settings()
    if "hud_toggle_hotkey" in data:
        s.hud_toggle_hotkey = data["hud_toggle_hotkey"]
    if "hud_mode" in data:
        if data["hud_mode"] not in VALID_HUD_MODES:
            raise ConfigError(f"invalid hud_mode: {data['hud_mode']!r}")
        s.hud_mode = data["hud_mode"]
    if "hud_flash_seconds" in data:
        s.hud_flash_seconds = float(data["hud_flash_seconds"])
    if "theme" in data:
        s.theme = data["theme"]
    return s


def parse_config(data: dict) -> Config:
    if not isinstance(data, dict):
        raise ConfigError("config root must be an object")
    if "profiles" not in data or not isinstance(data["profiles"], list):
        raise ConfigError("config needs a 'profiles' list")
    if "controls" not in data or not isinstance(data["controls"], dict):
        raise ConfigError("config needs a 'controls' object")
    settings = _parse_settings(data.get("settings", {}))
    controls = {str(k): str(v) for k, v in data["controls"].items()}
    profiles = [_parse_profile(p) for p in data["profiles"]]
    return Config(settings=settings, controls=controls, profiles=profiles)


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return parse_config(data)
