# src/dispatcher.py
import re
from typing import Optional
from src.models import Action, Config, Profile


def signal_to_control(config: Config, signal: str) -> Optional[str]:
    for control_id, sig in config.controls.items():
        if sig == signal:
            return control_id
    return None


def match_profile(profiles: list[Profile], process_name: str,
                  window_title: str) -> Optional[Profile]:
    title = window_title or ""
    proc = (process_name or "").lower()

    # Tier 1: title regex
    for p in profiles:
        if p.match.title and re.search(p.match.title, title, re.IGNORECASE):
            return p
    # Tier 2: exact process name
    for p in profiles:
        for pat in p.match.process:
            if pat != "*" and pat.lower() == proc:
                return p
    # Tier 3: default wildcard
    for p in profiles:
        if "*" in p.match.process:
            return p
    return None


def resolve_action(profile: Profile, control_id: str) -> Optional[Action]:
    binding = profile.keys.get(control_id)
    return binding.action if binding else None
