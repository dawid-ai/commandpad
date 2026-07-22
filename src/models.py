# src/models.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Action:
    type: str                       # send_keys | open | run | text
    keys: Optional[str] = None      # send_keys
    target: Optional[str] = None    # open | run
    text: Optional[str] = None      # text


@dataclass
class KeyBinding:
    label: str
    action: Action


@dataclass
class Match:
    process: list[str] = field(default_factory=list)
    title: Optional[str] = None     # regex, matched case-insensitively


@dataclass
class Profile:
    name: str
    color: str
    match: Match
    keys: dict[str, KeyBinding] = field(default_factory=dict)


@dataclass
class Settings:
    hud_toggle_hotkey: str = "ctrl+alt+shift+h"
    hud_mode: str = "flash"          # flash | pinned | off
    hud_flash_seconds: float = 2.0
    theme: str = "dark"


@dataclass
class Config:
    settings: Settings
    controls: dict[str, str]         # control_id -> signal string
    profiles: list[Profile]
