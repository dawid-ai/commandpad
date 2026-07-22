# commandpad — design spec

**Date:** 2026-07-22
**Status:** approved design → implementation planning
**Stack:** Python 3.11 + PySide6 (Qt), Windows first (Linux later)

---

## 1. Purpose

Turn a cheap, closed-firmware macro pad into an **app-aware command deck**. The app detects
the focused desktop application and switches "profiles" (layers) so each physical key/knob
does different things per app, and shows a **toggleable on-screen HUD** listing the current
profile's shortcuts as a reminder while the user learns them.

Replaces an AutoHotkey setup (`F:\02 - Personal\Assistant\macro.ahk`) whose app-detection
was never actually enabled (its `CheckActiveWindow` is commented out — layers were switched
manually with `Win+1..5`). Automatic app-detection is the core value.

### Success criteria (v1 done)
- Focus an app → the correct profile activates automatically.
- Each mapped key/knob fires its per-profile action reliably.
- HUD toggles on/off and shows the active profile's labels; supports flash and pinned modes.
- Add a new app or remap a key via the GUI editor (or `profiles.json`) — no code change, no
  restart, no rebuild.

## 2. Hardware context

Closed **VSDINSIDE** 12-key + 2-knob pad, USB VID `0x1189` (WCH CH55x-class),
configured via `sdcx-tech.com` (proprietary WebHID; config persists on-device). NOT QMK —
cannot be reflashed. App-aware logic therefore **must** live on the PC.

The pad is configured (once, via the vendor tool) to emit **collision-proof signals**:
- 12 keys → `F13`–`F24`
- 2 knobs × 3 actions (ccw / cw / press) → `Ctrl+Alt+Shift+F13`..`F18` ("Hyper" combos)

Nothing else on the system uses these, so the app **only listens** — it does not intercept
or suppress keystrokes. This removes the hardest, flakiest part of a Windows key hook.

## 3. Architecture

One tray app, always running. Small single-purpose components; the two OS-specific ones sit
behind an interface so the Linux port is contained.

```
  ┌─────────────┐         ┌──────────────┐
  │  Listener   │         │ App Detector │
  │ (pad keys)  │         │(focused app) │
  └──────┬──────┘         └──────┬───────┘
         │ "F13 pressed"         │ "active = obsidian"
         ▼                       ▼
       ┌─────────────────────────────┐        ┌──────────┐
       │        Dispatcher           │◀──────▶│  Config  │  profiles.json
       │ (control × profile → action)│  reads │  Store   │  (hot-reload)
       └──────────────┬──────────────┘        └──────────┘
                       │ "open today's note"
                       ▼
                ┌──────────────┐
                │ Action Runner│  send_keys · open · launch · run · text
                └──────────────┘

  App Detector also ─▶ HUD overlay
                    └▶ (optional) pad RGB profile switch  [spike, nice-to-have]

  Tray icon: current profile · toggle HUD · open Editor · quit
  Editor window: manage apps/profiles, assign keys, themes → writes profiles.json
```

### Components
| Component | Responsibility | OS-specific? |
|-----------|----------------|--------------|
| **Listener** | Detect the pad's signals (F13–F24 + Hyper combos), emit "control X fired". Listen only, no suppression. | **Yes** (behind adapter) |
| **App Detector** | Watch the focused window, resolve process → active profile. Debounced. | **Yes** (behind adapter) |
| **Config Store** | Load/validate `profiles.json`, watch the file, hot-reload on change. Single source of truth. | No |
| **Dispatcher** | Map `(control, active profile) → action`. The brain. | No |
| **Action Runner** | Execute an action (see §5). | No (actions may shell out) |
| **HUD overlay** | Translucent always-on-top panel showing the active profile's labels; toggle + modes. | No (PySide6) |
| **Tray icon** | Status, toggle HUD, open editor, quit. | No (PySide6) |
| **Editor** | GUI to manage profiles/keys/settings; writes `profiles.json`. | No (PySide6) |

### OS adapter
Only **Listener** and **App Detector** are platform-specific. A small interface
(`platform/base.py` + `platform/windows.py`, later `platform/linux.py`) is the entire
port surface. Windows uses a low-level keyboard hook / `pynput` for the listener and
`pywin32`/`psutil` (`GetForegroundWindow` → PID → process name) for detection.

## 4. Config (`profiles.json`)

Runtime data, hot-reloaded. Three parts: `settings`, a one-time `controls` map, and
`profiles`.

```jsonc
{
  "settings": {
    "hud_toggle_hotkey": "ctrl+alt+shift+h",
    "hud_mode": "flash",            // flash | pinned | off
    "hud_flash_seconds": 2,
    "theme": "dark"
  },
  "controls": {                     // physical control -> signal the pad emits (set once)
    "k1": "f13", "k2": "f14", "k3": "f15", "k4": "f16",
    "k5": "f17", "k6": "f18", "k7": "f19", "k8": "f20",
    "k9": "f21", "k10": "f22", "k11": "f23", "k12": "f24",
    "knob1.ccw": "ctrl+alt+shift+f13", "knob1.cw": "ctrl+alt+shift+f14", "knob1.press": "ctrl+alt+shift+f15",
    "knob2.ccw": "ctrl+alt+shift+f16", "knob2.cw": "ctrl+alt+shift+f17", "knob2.press": "ctrl+alt+shift+f18"
  },
  "profiles": [
    {
      "name": "Obsidian",
      "color": "#8b5cf6",
      "match": { "process": ["Obsidian.exe"] },   // optional: "title": "<regex>"
      "keys": {
        "k1":       { "label": "Today",    "action": { "type": "open",      "target": "obsidian://open?file=01-Daily/{today}" } },
        "k2":       { "label": "Search",   "action": { "type": "send_keys", "keys": "ctrl+shift+f" } },
        "knob1.cw": { "label": "Next tab", "action": { "type": "send_keys", "keys": "ctrl+tab" } }
      }
    },
    {
      "name": "Default",
      "color": "#2d2d2d",
      "match": { "process": ["*"] },               // fallback, listed last
      "keys": { "k1": { "label": "Copy", "action": { "type": "send_keys", "keys": "ctrl+c" } } }
    }
  ]
}
```

- **Profile matching:** `title regex` > `process name` > `Default`. First match wins;
  `Default` is the catch-all, always last.
- **The `label` IS the HUD.** The overlay renders the active profile's labels — no separate
  documentation step. Adding a key writes its label; it appears in the HUD automatically.
- **Validation:** on load, validate structure and warn (don't crash) on bad entries; keep
  running on the last-good config if a hot-reload is invalid.

## 5. Action types (v1)

| type | does | example `action` |
|------|------|------------------|
| `send_keys` | Fire a shortcut at the focused app | `{ "type": "send_keys", "keys": "ctrl+shift+f" }` |
| `open` | Open a file / URL / URI (supports `{today}` etc. tokens) | `{ "type": "open", "target": "https://…" }` |
| `launch` | Start or focus an app | `{ "type": "launch", "target": "Obsidian" }` |
| `run` | Run a shell command | `{ "type": "run", "target": "git -C … pull" }` |
| `text` | Type literal text (then user keeps typing) | `{ "type": "text", "text": "/note " }` |

Tokens (v1): `{today}` (yyyy-mm-dd). More can be added later.

## 6. HUD behavior

- **Toggle** via `hud_toggle_hotkey` (default `Ctrl+Alt+Shift+H`, collision-proof).
- **Modes:** `flash` (appears on app-switch, fades after `hud_flash_seconds`), `pinned`
  (stays until toggled off), `off` (only shows on the hotkey).
- **Look:** translucent rounded panel laid out as the 4×3 grid + 2 knobs; each cell shows
  the key's label; accented in the active profile's `color`; profile name shown. QSS-themed.
- Position configurable (default bottom-center, matching the old AHK indicator).

## 7. Editor (GUI)

- Opens from the tray. Left: profile list (add/remove). Center: clickable 4×3 + 2-knob grid
  mirroring the pad — click a control → set label + action (type dropdown + target field).
- Per profile: name, `match` (process/title), color. **"Grab focused app"** button captures
  the current foreground process so the user needn't know the `.exe` name.
- Global settings: HUD hotkey, mode, theme.
- Save → writes `profiles.json` → running engine hot-reloads. No restart.

## 8. Open items (do not block v1)

- **Physical RGB per app (nice-to-have, time-boxed spike).** Unknown if the closed board
  exposes a live profile-switch/RGB command. Spike: sniff `sdcx-tech.com` WebHID traffic (or
  inspect `ch57x-keyboard-tool`) for a replayable command. If found and ≤ a few hours, wire
  it (switch pad profile/RGB on app-change, bounded by however many on-device profiles
  exist). If not, physical RGB stays static; the HUD color is the feedback. Never blocks v1.
- **Autostart:** a `pythonw src/main.py` shortcut in `shell:startup` (no console window).
- **Packaging:** PyInstaller `.exe` deferred to a later "release" step (for build-in-public
  distribution). Personal use just runs the script.

## 9. Testing

- **Unit tests (pure logic, no OS):** config parse/validate, profile matching precedence,
  `(control × profile) → action` resolution, token expansion. This is the safety net.
- **Smoke tests:** listener emits on F13–F24 + Hyper combos; app detector reports the right
  process. Manual harness acceptable for the OS bits.

## 10. Out of scope (YAGNI for v1)

Cloud sync, multi-device, plugin system, macro recording, non-VID-0x1189 hardware, mobile.
Keep the core tight; these are post-v1 only if a real need appears.

## 11. Content angle

Doubles as a build-in-public piece for **dawid.ai** / the visibility project: "I turned a
$20 Temu keypad into my command center" (cheapest-productivity-hack framing; exact hook
TBD). Record the build; the article/video lands in `knowledge/areas/dawid-ai/`. The honesty
bar (per Dawid's content rules): the free thing must actually work and be reproducible — so
the repo + `profiles.example.json` ship publicly.
```
