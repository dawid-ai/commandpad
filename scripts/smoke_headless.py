# scripts/smoke_headless.py
"""Manual smoke test: prints the active app and fires actions for typed signals.
Run: python scripts/smoke_headless.py
Type a signal like 'f13' or 'ctrl+alt+shift+f14' and press Enter; Ctrl+C to quit."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import load_config
from src.engine import Engine
from src.platform_impl.windows import WindowsAppDetector, WindowsEffects

cfg = load_config("profiles.example.json")
eng = Engine(cfg, WindowsAppDetector(), WindowsEffects(),
             on_profile_change=lambda p: print(f"[profile] {p.name}"))

print("Focus an app, then type a signal (e.g. f13). Ctrl+C to quit.")
while True:
    sig = input("signal> ").strip()
    proc, title = eng.detector.current()
    print(f"  active: {proc!r} / {title!r}")
    eng.handle_signal(sig)
