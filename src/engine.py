# src/engine.py
from typing import Callable, Optional
from src.models import Config, Profile
from src.dispatcher import signal_to_control, match_profile, resolve_action
from src.actions import Effects, run_action


class Engine:
    def __init__(self, config: Config, detector, effects: Effects,
                 on_profile_change: Optional[Callable[[Profile], None]] = None):
        self.config = config
        self.detector = detector
        self.effects = effects
        self.on_profile_change = on_profile_change
        self._last_profile_name: Optional[str] = None

    def update_config(self, config: Config) -> None:
        self.config = config
        self._last_profile_name = None
        self.refresh_profile()

    def current_profile(self) -> Optional[Profile]:
        proc, title = self.detector.current()
        return match_profile(self.config.profiles, proc, title)

    def refresh_profile(self) -> Optional[Profile]:
        p = self.current_profile()
        if p is not None and p.name != self._last_profile_name:
            self._last_profile_name = p.name
            if self.on_profile_change:
                self.on_profile_change(p)
        return p

    def handle_signal(self, signal: str) -> None:
        control_id = signal_to_control(self.config, signal)
        if control_id is None:
            return
        profile = self.current_profile()
        if profile is None:
            return
        action = resolve_action(profile, control_id)
        if action is None:
            return
        try:
            run_action(action, self.effects)
        except Exception as e:
            print(f"[action error] {e}")
