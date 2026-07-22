# commandpad

Turn a cheap macro pad into an app-aware command deck. Detects the focused app, switches
key/knob layers per app, and shows a toggleable on-screen HUD of the current layer's
shortcuts.

- **Stack:** Python 3.11 + PySide6 (Qt). No compiler; just run it.
- **Config:** `profiles.json` — add apps/shortcuts via the config file or GUI editor, never
  a rebuild.
- **Platform:** Windows first, Linux later (only the key listener + active-window detector
  are OS-specific).

See `docs/specs/2026-07-22-commandpad-design.md` for the full design.

## Run (once implemented)
```
pip install -r requirements.txt
pythonw src/main.py
```
