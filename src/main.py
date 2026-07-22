# src/main.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from src.config import load_config, ConfigWatcher, ConfigError
from src.engine import Engine
from src.platform_impl.windows import WindowsKeyListener, WindowsAppDetector, WindowsEffects
from src.ui.hud import HudOverlay
from src.ui.tray import TrayIcon

CONFIG_PATH = "profiles.json" if os.path.exists("profiles.json") else "profiles.example.json"


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = load_config(CONFIG_PATH)
    detector = WindowsAppDetector()
    effects = WindowsEffects()
    hud = HudOverlay()

    def on_profile_change(profile):
        tray.set_profile(profile.name)
        if config.settings.hud_mode == "flash":
            hud.show_profile(profile, config.controls)
            hud.flash(config.settings.hud_flash_seconds)
        elif config.settings.hud_mode == "pinned" and hud.isVisible():
            hud.show_profile(profile, config.controls)

    engine = Engine(config, detector, effects, on_profile_change=on_profile_change)

    def toggle_hud():
        p = engine.current_profile()
        if p:
            hud.show_profile(p, config.settings and engine.config.controls)
        hud.toggle_pinned()

    tray = TrayIcon(on_toggle_hud=toggle_hud, on_open_editor=lambda: None, on_quit=app.quit)

    # Route pad signals; intercept the HUD toggle hotkey first.
    def on_signal(signal: str):
        if signal == engine.config.settings.hud_toggle_hotkey:
            toggle_hud()
            return
        engine.handle_signal(signal)

    listener = WindowsKeyListener()
    listener.start(on_signal)

    # Poll the foreground app ~4x/sec to drive profile switching.
    poll = QTimer()
    poll.timeout.connect(engine.refresh_profile)
    poll.start(250)

    # Hot-reload config on file change (marshal to the Qt thread via a timer).
    def reload_config():
        try:
            engine.update_config(load_config(CONFIG_PATH))
            print("[config] reloaded")
        except ConfigError as e:
            print(f"[config] invalid, keeping previous: {e}")

    watcher = ConfigWatcher(CONFIG_PATH, lambda: QTimer.singleShot(0, reload_config))
    watcher.start()

    try:
        engine.refresh_profile()
        sys.exit(app.exec())
    finally:
        listener.stop()
        watcher.stop()


if __name__ == "__main__":
    main()
