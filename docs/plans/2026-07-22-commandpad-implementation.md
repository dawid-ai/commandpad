# commandpad Implementation Plan

> Task-by-task plan. Each task is TDD (write test → fail → implement → pass → commit); steps use checkbox (`- [ ]`) tracking.

**Goal:** Build a Windows tray app that detects the focused application and makes a cheap macro pad's keys/knobs do different things per app, with a toggleable on-screen HUD showing the current layer's shortcuts.

**Architecture:** A pure-logic core (config parsing, profile matching, action resolution, token expansion) with no OS or UI dependencies, wrapped by a platform adapter (keyboard listener + active-window detector) and a PySide6 UI (HUD, tray, editor). Data flows: pad signal → control id → active profile → action → effect. Config is `profiles.json`, hot-reloaded; adding apps/shortcuts is never a code change.

**Tech Stack:** Python 3.11, PySide6 (Qt), pynput (key listener + effects), pywin32 + psutil (active-window detection), watchdog (config file watching), pytest.

## Global Constraints

- **Python 3.11**, standard library + the pinned deps only. No compiler / no build step.
- **Pure-logic modules** (`models`, `config`, `dispatcher`, `tokens`, `actions`) MUST NOT import PySide6, pynput, pywin32, or any OS/UI library. They are unit-tested in isolation.
- **OS-specific code** lives ONLY under `src/platform_impl/` behind the `platform_impl/base.py` interfaces. (Package named `platform_impl` to avoid shadowing the stdlib `platform` module.)
- **Signal strings** are lowercase, `+`-joined, modifiers in fixed order `ctrl+alt+shift+win+<key>`, e.g. `f13`, `ctrl+alt+shift+f13`. Both `controls` values and the listener output use this exact format.
- **Config file:** `profiles.json` (gitignored, personal); `profiles.example.json` is committed.
- **Action types:** `send_keys`, `open`, `launch`, `run`, `text` — exact strings.
- **HUD modes:** `flash`, `pinned`, `off` — exact strings.
- Commit after every task. Conventional commit messages.

---

## File Structure

```
requirements.txt
profiles.example.json
src/
  __init__.py
  models.py              # dataclasses: Action, KeyBinding, Match, Profile, Settings, Config
  config.py              # parse_config, load_config, ConfigError, ConfigWatcher
  tokens.py              # expand_tokens
  dispatcher.py          # signal_to_control, match_profile, resolve_action
  actions.py             # Effects protocol, run_action
  platform_impl/
    __init__.py
    base.py              # KeyListener, AppDetector, Effects interfaces
    windows.py           # WindowsKeyListener, WindowsAppDetector, WindowsEffects
  engine.py              # Engine: wires listener+detector+dispatcher+actions (headless-capable)
  ui/
    __init__.py
    hud.py               # HudOverlay (PySide6)
    tray.py              # TrayIcon (PySide6)
    editor.py            # EditorWindow (PySide6)
  main.py                # entry: build config, engine, Qt app, tray, HUD; run loop
tests/
  __init__.py
  test_models.py
  test_config.py
  test_tokens.py
  test_dispatcher.py
  test_actions.py
  test_engine.py
```

---

## Task 1: Project setup + models

**Files:**
- Create: `requirements.txt`, `src/__init__.py`, `tests/__init__.py`, `src/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: dataclasses `Action(type, keys=None, target=None, text=None)`, `KeyBinding(label, action)`, `Match(process=[], title=None)`, `Profile(name, color, match, keys={})`, `Settings(hud_toggle_hotkey, hud_mode, hud_flash_seconds, theme)`, `Config(settings, controls, profiles)`.

- [ ] **Step 1: Write requirements.txt**

```
PySide6==6.7.*
pynput==1.7.*
pywin32==306; sys_platform == "win32"
psutil==6.*
watchdog==4.*
pytest==8.*
```

- [ ] **Step 2: Create empty package markers**

Create `src/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 3: Write the failing test**

```python
# tests/test_models.py
from src.models import Action, KeyBinding, Match, Profile, Settings, Config


def test_models_construct_and_default():
    a = Action(type="send_keys", keys="ctrl+c")
    b = KeyBinding(label="Copy", action=a)
    p = Profile(name="Default", color="#2d2d2d", match=Match(process=["*"]), keys={"k1": b})
    s = Settings()
    c = Config(settings=s, controls={"k1": "f13"}, profiles=[p])

    assert c.profiles[0].keys["k1"].action.keys == "ctrl+c"
    assert c.controls["k1"] == "f13"
    assert s.hud_mode == "flash"           # default
    assert p.match.title is None           # default
    assert Match().process == []           # default is a fresh list
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 5: Write models.py**

```python
# src/models.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Action:
    type: str                       # send_keys | open | launch | run | text
    keys: Optional[str] = None      # send_keys
    target: Optional[str] = None    # open | launch | run
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add requirements.txt src/__init__.py tests/__init__.py src/models.py tests/test_models.py
git commit -m "feat: project setup and core data models"
```

---

## Task 2: Config parsing + validation

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: all dataclasses from `src/models.py`.
- Produces: `parse_config(data: dict) -> Config`; `load_config(path: str) -> Config`; `ConfigError(Exception)`. `parse_config` raises `ConfigError` on structural problems; missing `settings` fields fall back to `Settings` defaults; each profile requires `name`, `color`, `match`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Write config.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: config parsing and validation"
```

---

## Task 3: Token expansion

**Files:**
- Create: `src/tokens.py`
- Test: `tests/test_tokens.py`

**Interfaces:**
- Produces: `expand_tokens(text: str, today: Optional[date] = None) -> str`. Replaces `{today}` with ISO date. `today` is injectable for tests. Non-string input returned unchanged is NOT required — callers always pass strings.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tokens.py
from datetime import date
from src.tokens import expand_tokens


def test_today_token():
    assert expand_tokens("01-Daily/{today}", today=date(2026, 7, 22)) == "01-Daily/2026-07-22"


def test_no_token_unchanged():
    assert expand_tokens("ctrl+c", today=date(2026, 7, 22)) == "ctrl+c"


def test_multiple_tokens():
    assert expand_tokens("{today}-{today}", today=date(2026, 1, 2)) == "2026-01-02-2026-01-02"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tokens.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write tokens.py**

```python
# src/tokens.py
from datetime import date
from typing import Optional


def expand_tokens(text: str, today: Optional[date] = None) -> str:
    today = today or date.today()
    return text.replace("{today}", today.isoformat())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tokens.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/tokens.py tests/test_tokens.py
git commit -m "feat: token expansion"
```

---

## Task 4: Dispatcher (signal→control, profile matching, action resolution)

**Files:**
- Create: `src/dispatcher.py`
- Test: `tests/test_dispatcher.py`

**Interfaces:**
- Consumes: `Config`, `Profile`, `Action` from models.
- Produces:
  - `signal_to_control(config: Config, signal: str) -> Optional[str]`
  - `match_profile(profiles: list[Profile], process_name: str, window_title: str) -> Optional[Profile]` — precedence: title regex (case-insensitive `re.search`) > exact process name (case-insensitive) > default (`"*"` in process list); first match within a tier wins.
  - `resolve_action(profile: Profile, control_id: str) -> Optional[Action]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dispatcher.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dispatcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write dispatcher.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dispatcher.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/dispatcher.py tests/test_dispatcher.py
git commit -m "feat: dispatcher — signal mapping, profile matching, action resolution"
```

---

## Task 5: Action runner + Effects protocol

**Files:**
- Create: `src/actions.py`
- Test: `tests/test_actions.py`

**Interfaces:**
- Consumes: `Action` from models, `expand_tokens` from tokens.
- Produces:
  - `Effects` (typing.Protocol) with `send_keys(keys)`, `open_target(target)`, `launch(target)`, `run_command(target)`, `type_text(text)`.
  - `run_action(action: Action, effects: Effects, today=None) -> None` — routes by `action.type`, expands tokens on `target`/`text`, raises `ValueError` on unknown type.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_actions.py
from datetime import date
import pytest
from src.actions import run_action
from src.models import Action


class FakeEffects:
    def __init__(self):
        self.calls = []
    def send_keys(self, keys): self.calls.append(("send_keys", keys))
    def open_target(self, target): self.calls.append(("open", target))
    def launch(self, target): self.calls.append(("launch", target))
    def run_command(self, target): self.calls.append(("run", target))
    def type_text(self, text): self.calls.append(("text", text))


def test_send_keys_routes():
    fx = FakeEffects()
    run_action(Action("send_keys", keys="ctrl+c"), fx)
    assert fx.calls == [("send_keys", "ctrl+c")]


def test_open_expands_tokens():
    fx = FakeEffects()
    run_action(Action("open", target="d/{today}"), fx, today=date(2026, 7, 22))
    assert fx.calls == [("open", "d/2026-07-22")]


def test_text_expands_tokens():
    fx = FakeEffects()
    run_action(Action("text", text="/note "), fx, today=date(2026, 7, 22))
    assert fx.calls == [("text", "/note ")]


def test_run_and_launch_route():
    fx = FakeEffects()
    run_action(Action("launch", target="Obsidian"), fx)
    run_action(Action("run", target="git pull"), fx)
    assert fx.calls == [("launch", "Obsidian"), ("run", "git pull")]


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        run_action(Action("teleport", target="x"), FakeEffects())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_actions.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write actions.py**

```python
# src/actions.py
from datetime import date
from typing import Optional, Protocol, runtime_checkable
from src.models import Action
from src.tokens import expand_tokens


@runtime_checkable
class Effects(Protocol):
    def send_keys(self, keys: str) -> None: ...
    def open_target(self, target: str) -> None: ...
    def launch(self, target: str) -> None: ...
    def run_command(self, target: str) -> None: ...
    def type_text(self, text: str) -> None: ...


def run_action(action: Action, effects: Effects, today: Optional[date] = None) -> None:
    if action.type == "send_keys":
        effects.send_keys(action.keys or "")
    elif action.type == "open":
        effects.open_target(expand_tokens(action.target or "", today))
    elif action.type == "launch":
        effects.launch(action.target or "")
    elif action.type == "run":
        effects.run_command(expand_tokens(action.target or "", today))
    elif action.type == "text":
        effects.type_text(expand_tokens(action.text or "", today))
    else:
        raise ValueError(f"Unknown action type: {action.type!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_actions.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/actions.py tests/test_actions.py
git commit -m "feat: action runner with injectable Effects"
```

---

## Task 6: Platform interfaces

**Files:**
- Create: `src/platform_impl/__init__.py`, `src/platform_impl/base.py`

**Interfaces:**
- Produces (Protocols):
  - `KeyListener`: `start(on_signal: Callable[[str], None]) -> None`, `stop() -> None`
  - `AppDetector`: `current() -> tuple[str, str]` returning `(process_name, window_title)`
  - (`Effects` already defined in `actions.py`; platform impls will satisfy it.)

- [ ] **Step 1: Create the package marker**

Create `src/platform_impl/__init__.py` (empty).

- [ ] **Step 2: Write base.py**

```python
# src/platform_impl/base.py
from typing import Callable, Protocol


class KeyListener(Protocol):
    def start(self, on_signal: Callable[[str], None]) -> None: ...
    def stop(self) -> None: ...


class AppDetector(Protocol):
    def current(self) -> tuple[str, str]:
        """Return (process_name, window_title) of the foreground window."""
        ...
```

- [ ] **Step 3: Verify it imports**

Run: `python -c "from src.platform_impl.base import KeyListener, AppDetector; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add src/platform_impl/__init__.py src/platform_impl/base.py
git commit -m "feat: platform adapter interfaces"
```

---

## Task 7: Engine (headless wiring) + test

**Files:**
- Create: `src/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `Config`, `dispatcher.*`, `actions.run_action`, `AppDetector`, `Effects`.
- Produces: `Engine(config, detector, effects, on_profile_change=None)` with:
  - `handle_signal(signal: str) -> None` — the core loop: signal → control → current profile (via detector) → action → effect. Silently ignores unmapped signals/controls.
  - `current_profile() -> Optional[Profile]` — matches the detector's current app against config.
  - `update_config(config: Config) -> None` — swap config on hot-reload.

This is the milestone: with a fake detector + fake effects, the whole listen→act loop is testable without Windows or UI.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine.py
from src.engine import Engine
from src.config import parse_config


def _config():
    return parse_config({
        "controls": {"k1": "f13"},
        "profiles": [
            {"name": "Obsidian", "color": "#8b5cf6", "match": {"process": ["Obsidian.exe"]},
             "keys": {"k1": {"label": "Search", "action": {"type": "send_keys", "keys": "ctrl+shift+f"}}}},
            {"name": "Default", "color": "#2d2d2d", "match": {"process": ["*"]},
             "keys": {"k1": {"label": "Copy", "action": {"type": "send_keys", "keys": "ctrl+c"}}}},
        ],
    })


class FakeDetector:
    def __init__(self, proc="Obsidian.exe", title=""):
        self.proc, self.title = proc, title
    def current(self):
        return (self.proc, self.title)


class FakeEffects:
    def __init__(self):
        self.calls = []
    def send_keys(self, keys): self.calls.append(("send_keys", keys))
    def open_target(self, t): self.calls.append(("open", t))
    def launch(self, t): self.calls.append(("launch", t))
    def run_command(self, t): self.calls.append(("run", t))
    def type_text(self, t): self.calls.append(("text", t))


def test_signal_fires_active_profile_action():
    fx = FakeEffects()
    eng = Engine(_config(), FakeDetector("Obsidian.exe"), fx)
    eng.handle_signal("f13")
    assert fx.calls == [("send_keys", "ctrl+shift+f")]


def test_same_signal_different_app_different_action():
    fx = FakeEffects()
    det = FakeDetector("notepad.exe")           # falls to Default
    eng = Engine(_config(), det, fx)
    eng.handle_signal("f13")
    assert fx.calls == [("send_keys", "ctrl+c")]


def test_unmapped_signal_is_ignored():
    fx = FakeEffects()
    eng = Engine(_config(), FakeDetector("Obsidian.exe"), fx)
    eng.handle_signal("f99")                     # no control
    assert fx.calls == []


def test_profile_change_callback_fires_on_switch():
    seen = []
    eng = Engine(_config(), FakeDetector("Obsidian.exe"), FakeEffects(),
                 on_profile_change=lambda p: seen.append(p.name))
    eng.refresh_profile()
    eng.detector.proc = "notepad.exe"
    eng.refresh_profile()
    assert seen == ["Obsidian", "Default"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write engine.py**

```python
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
        run_action(action, self.effects)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -v`
Expected: PASS (all tasks 1–7)

- [ ] **Step 6: Commit**

```bash
git add src/engine.py tests/test_engine.py
git commit -m "feat: engine wiring — full listen-to-act loop (headless-testable)"
```

---

## Task 8: Windows platform implementation

**Files:**
- Create: `src/platform_impl/windows.py`

**Interfaces:**
- Consumes: `KeyListener`, `AppDetector` shapes from `base.py`; satisfies `Effects` from `actions.py`.
- Produces: `WindowsKeyListener` (emits signal strings in the canonical format), `WindowsAppDetector`, `WindowsEffects`.

**Note:** OS-bound; verified by the manual smoke test in Task 9, not unit tests.

- [ ] **Step 1: Write windows.py**

```python
# src/platform_impl/windows.py
import os
import subprocess
import webbrowser
from typing import Callable

from pynput import keyboard
import win32gui
import win32process
import psutil

# Map pynput keys to our signal token names.
_MODS = {
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr,
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
}


def _mod_name(key) -> str:
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        return "ctrl"
    if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
        return "alt"
    if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
        return "shift"
    return "win"


def _key_token(key) -> str | None:
    """Return the base token for a non-modifier key, e.g. 'f13', or None to ignore."""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        return None
    name = getattr(key, "name", None)
    return name.lower() if name else None


class WindowsKeyListener:
    """Listens for the pad's collision-proof signals and reports them as
    'ctrl+alt+shift+f13'-style strings. Listen-only; does not suppress."""

    def __init__(self):
        self._listener = None
        self._down_mods = set()

    def start(self, on_signal: Callable[[str], None]) -> None:
        def on_press(key):
            if key in _MODS:
                self._down_mods.add(_mod_name(key))
                return
            base = _key_token(key)
            if not base:
                return
            parts = []
            for m in ("ctrl", "alt", "shift", "win"):
                if m in self._down_mods:
                    parts.append(m)
            parts.append(base)
            on_signal("+".join(parts))

        def on_release(key):
            if key in _MODS:
                self._down_mods.discard(_mod_name(key))

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None


class WindowsAppDetector:
    def current(self) -> tuple[str, str]:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
        proc = ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid).name()
        except Exception:
            pass
        return (proc, title)


class WindowsEffects:
    """Satisfies the Effects protocol on Windows."""

    def __init__(self):
        self._kb = keyboard.Controller()

    def send_keys(self, keys: str) -> None:
        parts = keys.lower().split("+")
        mods, main = parts[:-1], parts[-1]
        mod_keys = {"ctrl": keyboard.Key.ctrl, "alt": keyboard.Key.alt,
                    "shift": keyboard.Key.shift, "win": keyboard.Key.cmd}
        special = getattr(keyboard.Key, main, None)
        target = special if special is not None else main
        pressed = [mod_keys[m] for m in mods if m in mod_keys]
        for m in pressed:
            self._kb.press(m)
        self._kb.press(target)
        self._kb.release(target)
        for m in reversed(pressed):
            self._kb.release(m)

    def open_target(self, target: str) -> None:
        if target.startswith(("http://", "https://")):
            webbrowser.open(target)
        elif "://" in target:            # custom URI scheme, e.g. obsidian://
            os.startfile(target)
        else:
            os.startfile(target)

    def launch(self, target: str) -> None:
        os.startfile(target)

    def run_command(self, target: str) -> None:
        subprocess.Popen(target, shell=True)

    def type_text(self, text: str) -> None:
        self._kb.type(text)
```

- [ ] **Step 2: Verify it imports on Windows**

Run: `python -c "from src.platform_impl.windows import WindowsKeyListener, WindowsAppDetector, WindowsEffects; print('ok')"`
Expected: prints `ok` (installs pywin32/pynput/psutil first via `pip install -r requirements.txt`)

- [ ] **Step 3: Commit**

```bash
git add src/platform_impl/windows.py
git commit -m "feat: Windows listener, app detector, and effects"
```

---

## Task 9: Config watcher + example config + headless smoke run

**Files:**
- Modify: `src/config.py` (add `ConfigWatcher`)
- Create: `profiles.example.json`, `scripts/smoke_headless.py`

**Interfaces:**
- Produces: `ConfigWatcher(path: str, on_change: Callable[[], None])` with `start()`/`stop()`, using `watchdog` to call `on_change` when the file is written.

- [ ] **Step 1: Add ConfigWatcher to config.py**

Append to `src/config.py`:

```python
# --- file watching (appended) ---
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os as _os


class _Handler(FileSystemEventHandler):
    def __init__(self, path, on_change):
        self._path = _os.path.abspath(path)
        self._on_change = on_change
    def on_modified(self, event):
        if _os.path.abspath(event.src_path) == self._path:
            self._on_change()


class ConfigWatcher:
    def __init__(self, path: str, on_change):
        self._path = path
        self._observer = Observer()
        self._observer.schedule(_Handler(path, on_change),
                                _os.path.dirname(_os.path.abspath(path)) or ".",
                                recursive=False)
    def start(self):
        self._observer.start()
    def stop(self):
        self._observer.stop()
        self._observer.join(timeout=2)
```

- [ ] **Step 2: Write profiles.example.json**

```json
{
  "settings": {
    "hud_toggle_hotkey": "ctrl+alt+shift+h",
    "hud_mode": "flash",
    "hud_flash_seconds": 2,
    "theme": "dark"
  },
  "controls": {
    "k1": "f13", "k2": "f14", "k3": "f15", "k4": "f16",
    "k5": "f17", "k6": "f18", "k7": "f19", "k8": "f20",
    "k9": "f21", "k10": "f22", "k11": "f23", "k12": "f24",
    "knob1.ccw": "ctrl+alt+shift+f13", "knob1.cw": "ctrl+alt+shift+f14", "knob1.press": "ctrl+alt+shift+f15",
    "knob2.ccw": "ctrl+alt+shift+f16", "knob2.cw": "ctrl+alt+shift+f17", "knob2.press": "ctrl+alt+shift+f18"
  },
  "profiles": [
    {
      "name": "Obsidian", "color": "#8b5cf6",
      "match": { "process": ["Obsidian.exe"] },
      "keys": {
        "k1": { "label": "Search", "action": { "type": "send_keys", "keys": "ctrl+shift+f" } },
        "knob1.cw": { "label": "Next tab", "action": { "type": "send_keys", "keys": "ctrl+tab" } }
      }
    },
    {
      "name": "Default", "color": "#2d2d2d",
      "match": { "process": ["*"] },
      "keys": {
        "k1": { "label": "Copy", "action": { "type": "send_keys", "keys": "ctrl+c" } },
        "k2": { "label": "Paste", "action": { "type": "send_keys", "keys": "ctrl+v" } }
      }
    }
  ]
}
```

- [ ] **Step 3: Write a headless smoke script**

```python
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
```

- [ ] **Step 4: Run the smoke script (manual)**

Run: `python scripts/smoke_headless.py`
Focus Obsidian (or any app), type `f13`, Enter. Expected: it prints the active process and, if a mapping exists, performs the action (e.g. sends Ctrl+Shift+F to Obsidian). Confirms detector + engine + effects work end-to-end on real Windows.

- [ ] **Step 5: Commit**

```bash
git add src/config.py profiles.example.json scripts/smoke_headless.py
git commit -m "feat: config hot-reload watcher, example config, headless smoke script"
```

---

## Task 10: HUD overlay

**Files:**
- Create: `src/ui/__init__.py`, `src/ui/hud.py`

**Interfaces:**
- Consumes: `Profile`, `Config`.
- Produces: `HudOverlay(QWidget)` with `show_profile(profile: Profile, controls: dict[str, str])`, `flash(seconds: float)`, `toggle_pinned()`, `hide_now()`. Frameless, translucent, always-on-top; renders the 4×3 grid + 2 knobs with each control's label, accented by `profile.color`.

- [ ] **Step 1: Create the ui package marker**

Create `src/ui/__init__.py` (empty).

- [ ] **Step 2: Write hud.py**

```python
# src/ui/hud.py
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QFrame
from src.models import Profile

_KEY_GRID = [["k1", "k2", "k3", "k4"],
             ["k5", "k6", "k7", "k8"],
             ["k9", "k10", "k11", "k12"]]
_KNOBS = ["knob1.ccw", "knob1.cw", "knob1.press", "knob2.ccw", "knob2.cw", "knob2.press"]


class HudOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_now)
        self._build()

    def _build(self):
        self._root = QFrame(self)
        self._root.setObjectName("hudRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._root)
        self._title = QLabel("", self._root)
        self._title.setObjectName("hudTitle")
        self._grid = QGridLayout()
        self._cells = {}
        col_wrap = QVBoxLayout(self._root)
        col_wrap.addWidget(self._title)
        col_wrap.addLayout(self._grid)
        for r, row in enumerate(_KEY_GRID):
            for c, cid in enumerate(row):
                lbl = QLabel("", self._root)
                lbl.setObjectName("hudCell")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFixedSize(96, 44)
                self._grid.addWidget(lbl, r, c)
                self._cells[cid] = lbl
        self._knob_row = QGridLayout()
        for i, cid in enumerate(_KNOBS):
            lbl = QLabel("", self._root)
            lbl.setObjectName("hudKnob")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(96, 28)
            self._knob_row.addWidget(lbl, 0, i)
            self._cells[cid] = lbl
        col_wrap.addLayout(self._knob_row)

    def _apply_theme(self, color: str):
        self.setStyleSheet(f"""
            #hudRoot {{ background: rgba(26,26,26,235); border: 2px solid {color};
                        border-radius: 12px; }}
            #hudTitle {{ color: {color}; font: 700 15px 'Segoe UI'; padding: 8px 4px; }}
            #hudCell {{ background: #333; color: #ececec; border-radius: 6px;
                        font: 600 11px 'Segoe UI'; }}
            #hudKnob {{ background: #2a2a2a; color: #adadad; border-radius: 6px;
                        font: 10px 'Segoe UI'; }}
        """)

    def show_profile(self, profile: Profile, controls: dict):
        self._title.setText(profile.name)
        self._apply_theme(profile.color)
        for cid, lbl in self._cells.items():
            binding = profile.keys.get(cid)
            lbl.setText(binding.label if binding else "")
        self.adjustSize()
        self._reposition()

    def _reposition(self):
        screen = self.screen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2,
                  screen.bottom() - self.height() - 80)

    def flash(self, seconds: float):
        self.show()
        self._timer.start(int(seconds * 1000))

    def toggle_pinned(self):
        self._timer.stop()
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def hide_now(self):
        self._timer.stop()
        self.hide()
```

- [ ] **Step 3: Manual visual check**

Run:
```bash
python -c "from PySide6.QtWidgets import QApplication; from src.ui.hud import HudOverlay; from src.config import load_config; from src.dispatcher import match_profile; app=QApplication([]); c=load_config('profiles.example.json'); p=match_profile(c.profiles,'Obsidian.exe',''); h=HudOverlay(); h.show_profile(p,c.controls); h.flash(3); app.exec()"
```
Expected: a translucent purple-bordered panel appears bottom-center for 3s showing "Obsidian", with "Search" on k1 and "Next tab" on a knob cell, then hides.

- [ ] **Step 4: Commit**

```bash
git add src/ui/__init__.py src/ui/hud.py
git commit -m "feat: HUD overlay widget"
```

---

## Task 11: Tray icon + global HUD toggle hotkey

**Files:**
- Create: `src/ui/tray.py`

**Interfaces:**
- Consumes: PySide6.
- Produces: `TrayIcon(on_toggle_hud, on_open_editor, on_quit)` — a `QSystemTrayIcon` with a menu (current profile label, Toggle HUD, Open Editor, Quit) and `set_profile(name: str)`.

- [ ] **Step 1: Write tray.py**

```python
# src/ui/tray.py
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor


def _placeholder_icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(QColor("#8b5cf6"))
    return QIcon(pm)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, on_toggle_hud, on_open_editor, on_quit):
        super().__init__(_placeholder_icon())
        self.setToolTip("commandpad")
        menu = QMenu()
        self._profile_action = menu.addAction("Profile: —")
        self._profile_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Toggle HUD", on_toggle_hud)
        menu.addAction("Open Editor", on_open_editor)
        menu.addSeparator()
        menu.addAction("Quit", on_quit)
        self.setContextMenu(menu)
        self.show()

    def set_profile(self, name: str):
        self._profile_action.setText(f"Profile: {name}")
```

Global hotkey: the HUD toggle uses the same `pynput` listener stream already running — `main.py` (Task 12) checks the incoming signal against `settings.hud_toggle_hotkey` before passing it to the engine. No separate hotkey library needed.

- [ ] **Step 2: Commit**

```bash
git add src/ui/tray.py
git commit -m "feat: system tray icon and menu"
```

---

## Task 12: main.py — wire everything and run

**Files:**
- Create: `src/main.py`

**Interfaces:**
- Consumes: everything above.
- Produces: an executable entry point. Builds config (from `profiles.json`, falling back to `profiles.example.json`), starts the Windows listener/detector/effects, the engine, the HUD, the tray, and the config watcher; routes signals; runs the Qt event loop.

- [ ] **Step 1: Write main.py**

```python
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
```

- [ ] **Step 2: Manual end-to-end run**

Run: `python src/main.py` (or `pythonw src/main.py` for no console).
Expected: a tray icon appears; focusing Obsidian flashes the HUD with the Obsidian profile; pressing the pad keys performs the mapped actions; `Ctrl+Alt+Shift+H` toggles the pinned HUD; editing `profiles.json` hot-reloads.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: main entry point wiring engine, HUD, tray, hot-reload"
```

---

## Task 13: Editor GUI

**Files:**
- Create: `src/ui/editor.py`
- Modify: `src/main.py` (wire `on_open_editor` to open it)

**Interfaces:**
- Consumes: `Config`, `load_config`, and a save routine.
- Produces: `EditorWindow(config_path: str, on_saved: Callable[[], None])` — lists profiles; per profile edits name/color/match and the 12 keys + 6 knob actions (label + action type + target/keys/text); a "Grab focused app" button (uses `WindowsAppDetector`); Save writes JSON to `config_path`.

**Note:** This task is larger; keep the widget focused on editing and delegate all persistence to a single `save_config(config, path)` helper. Split into sub-widgets if `editor.py` exceeds ~300 lines.

- [ ] **Step 1: Add save_config to config.py**

Append to `src/config.py`:

```python
def save_config(config: Config, path: str) -> None:
    """Serialize a Config back to profiles.json."""
    data = {
        "settings": {
            "hud_toggle_hotkey": config.settings.hud_toggle_hotkey,
            "hud_mode": config.settings.hud_mode,
            "hud_flash_seconds": config.settings.hud_flash_seconds,
            "theme": config.settings.theme,
        },
        "controls": dict(config.controls),
        "profiles": [
            {
                "name": p.name, "color": p.color,
                "match": {"process": list(p.match.process),
                          **({"title": p.match.title} if p.match.title else {})},
                "keys": {
                    cid: {"label": b.label,
                          "action": {k: v for k, v in {
                              "type": b.action.type, "keys": b.action.keys,
                              "target": b.action.target, "text": b.action.text,
                          }.items() if v is not None}}
                    for cid, b in p.keys.items()
                },
            }
            for p in config.profiles
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        import json
        json.dump(data, f, indent=2)
```

- [ ] **Step 2: Write a round-trip test**

```python
# tests/test_config.py  (append)
from src.config import save_config


def test_save_then_load_round_trips(tmp_path):
    c = parse_config(_valid_data())
    path = str(tmp_path / "out.json")
    save_config(c, path)
    again = load_config(path)
    assert again.profiles[0].keys["k1"].action.target == "x"
    assert again.settings.hud_mode == "pinned"
```

- [ ] **Step 3: Run the round-trip test**

Run: `python -m pytest tests/test_config.py::test_save_then_load_round_trips -v`
Expected: PASS

- [ ] **Step 4: Write editor.py**

```python
# src/ui/editor.py
from PySide6.QtWidgets import (
    QWidget, QListWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QLabel, QScrollArea, QGridLayout
)
from src.config import load_config, save_config
from src.models import Action, KeyBinding, Match, Profile
from src.platform_impl.windows import WindowsAppDetector

_CONTROL_IDS = [f"k{i}" for i in range(1, 13)] + [
    "knob1.ccw", "knob1.cw", "knob1.press", "knob2.ccw", "knob2.cw", "knob2.press"]
_ACTION_TYPES = ["send_keys", "open", "launch", "run", "text"]


class EditorWindow(QWidget):
    def __init__(self, config_path: str, on_saved):
        super().__init__()
        self.setWindowTitle("commandpad — editor")
        self.resize(760, 620)
        self._path = config_path
        self._on_saved = on_saved
        self._config = load_config(config_path)
        self._detector = WindowsAppDetector()
        self._current_idx = 0
        self._build()
        self._load_profile(0)

    def _build(self):
        root = QHBoxLayout(self)
        self._list = QListWidget()
        for p in self._config.profiles:
            self._list.addItem(p.name)
        self._list.currentRowChanged.connect(self._on_select)
        left = QVBoxLayout()
        left.addWidget(QLabel("Profiles"))
        left.addWidget(self._list)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        form = QFormLayout()
        self._name = QLineEdit()
        self._color = QLineEdit()
        self._process = QLineEdit()
        grab = QPushButton("Grab focused app")
        grab.clicked.connect(self._grab_app)
        form.addRow("Name", self._name)
        form.addRow("Color", self._color)
        form.addRow("Process(es)", self._process)
        form.addRow("", grab)
        right.addLayout(form)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_host = QWidget()
        self._grid = QGridLayout(grid_host)
        self._rows = {}
        for i, cid in enumerate(_CONTROL_IDS):
            self._grid.addWidget(QLabel(cid), i, 0)
            label = QLineEdit()
            atype = QComboBox(); atype.addItems(_ACTION_TYPES)
            payload = QLineEdit()   # keys/target/text combined field
            self._grid.addWidget(label, i, 1)
            self._grid.addWidget(atype, i, 2)
            self._grid.addWidget(payload, i, 3)
            self._rows[cid] = (label, atype, payload)
        scroll.setWidget(grid_host)
        right.addWidget(scroll, 1)

        save = QPushButton("Save")
        save.clicked.connect(self._save)
        right.addWidget(save)
        root.addLayout(right, 2)

    def _on_select(self, idx):
        if idx >= 0:
            self._capture_profile(self._current_idx)
            self._load_profile(idx)
            self._current_idx = idx

    def _load_profile(self, idx):
        p = self._config.profiles[idx]
        self._name.setText(p.name)
        self._color.setText(p.color)
        self._process.setText(", ".join(p.match.process))
        for cid, (label, atype, payload) in self._rows.items():
            b = p.keys.get(cid)
            if b:
                label.setText(b.label)
                atype.setCurrentText(b.action.type)
                payload.setText(b.action.keys or b.action.target or b.action.text or "")
            else:
                label.setText(""); atype.setCurrentIndex(0); payload.setText("")

    def _capture_profile(self, idx):
        p = self._config.profiles[idx]
        p.name = self._name.text().strip() or p.name
        p.color = self._color.text().strip() or p.color
        p.match = Match(process=[s.strip() for s in self._process.text().split(",") if s.strip()],
                        title=p.match.title)
        keys = {}
        for cid, (label, atype, payload) in self._rows.items():
            lbl = label.text().strip()
            val = payload.text()
            if not lbl and not val:
                continue
            t = atype.currentText()
            action = Action(type=t,
                            keys=val if t == "send_keys" else None,
                            target=val if t in ("open", "launch", "run") else None,
                            text=val if t == "text" else None)
            keys[cid] = KeyBinding(label=lbl or cid, action=action)
        p.keys = keys
        self._list.item(idx).setText(p.name)

    def _grab_app(self):
        proc, _ = self._detector.current()
        if proc:
            existing = self._process.text().strip()
            self._process.setText(f"{existing}, {proc}" if existing else proc)

    def _save(self):
        self._capture_profile(self._current_idx)
        save_config(self._config, self._path)
        self._on_saved()
```

- [ ] **Step 5: Wire the editor into main.py**

In `src/main.py`, replace the tray construction. Change:

```python
    tray = TrayIcon(on_toggle_hud=toggle_hud, on_open_editor=lambda: None, on_quit=app.quit)
```

to:

```python
    from src.ui.editor import EditorWindow
    editor_holder = {}
    def open_editor():
        w = EditorWindow(CONFIG_PATH, on_saved=reload_config)
        editor_holder["win"] = w   # keep a reference so it isn't GC'd
        w.show()
    tray = TrayIcon(on_toggle_hud=toggle_hud, on_open_editor=open_editor, on_quit=app.quit)
```

(Ensure `reload_config` is defined above this point; move its definition up if needed.)

- [ ] **Step 6: Manual check**

Run: `python src/main.py` → tray → Open Editor. Add a process to a profile via "Grab focused app", set a key's label + action, Save. Confirm `profiles.json` is written and the console prints `[config] reloaded`.

- [ ] **Step 7: Commit**

```bash
git add src/ui/editor.py src/config.py tests/test_config.py src/main.py
git commit -m "feat: config editor GUI with save + round-trip test"
```

---

## Task 14: Autostart helper + run docs

**Files:**
- Create: `scripts/install_autostart.py`
- Modify: `README.md`

**Interfaces:**
- Produces: a script that drops a `pythonw` shortcut into the Startup folder.

- [ ] **Step 1: Write install_autostart.py**

```python
# scripts/install_autostart.py
"""Create a Startup shortcut that runs commandpad at login (no console window)."""
import os
import sys

def main():
    startup = os.path.join(os.environ["APPDATA"],
                           r"Microsoft\Windows\Start Menu\Programs\Startup")
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    target = os.path.join(repo, "src", "main.py")
    shortcut = os.path.join(startup, "commandpad.lnk")

    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    lnk = shell.CreateShortCut(shortcut)
    lnk.Targetpath = pythonw
    lnk.Arguments = f'"{target}"'
    lnk.WorkingDirectory = repo
    lnk.save()
    print(f"Installed autostart: {shortcut}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update README run section**

Replace the `## Run (once implemented)` section of `README.md` with:

```markdown
## Run

```
pip install -r requirements.txt
copy profiles.example.json profiles.json   # first time; then edit via the tray > Open Editor
pythonw src/main.py
```

Run at login: `python scripts/install_autostart.py`.
```

- [ ] **Step 3: Commit**

```bash
git add scripts/install_autostart.py README.md
git commit -m "feat: autostart installer and run docs"
```

---

## Task 15 (deferred spike): physical RGB per profile

**Do not schedule with v1.** Time-boxed investigation only, after v1 is in daily use.

- [ ] Capture the WebHID traffic `sdcx-tech.com` sends when switching the pad's on-device profile / setting RGB (Chrome DevTools → the WebHID frames), or inspect `ch57x-keyboard-tool`'s wire format for VID `0x1189`.
- [ ] If a replayable "switch profile N" / "set color" HID report exists, add `src/platform_impl/windows_hid.py` using `hidapi` to send it, and call it from `on_profile_change` (bounded by the number of on-device profiles). Keep it behind a `settings.rgb_sync` flag, default off.
- [ ] If no such command exists, close the spike: physical RGB stays static; the HUD color remains the feedback. Record the finding in the spec.

---

## Self-Review

**Spec coverage:**
- Purpose / app-aware switching → Tasks 4, 7, 12 ✓
- Config shape + validation + hot-reload → Tasks 2, 9 ✓
- Action types (all 5) → Task 5 ✓
- Profile matching precedence → Task 4 ✓
- HUD + modes → Tasks 10, 12 ✓
- Editor (config-driven, grab app) → Task 13 ✓
- OS adapter isolation → Tasks 6, 8 ✓
- Testing (pure-logic unit tests) → Tasks 1–5, 7, 13 ✓
- Autostart / packaging deferral → Task 14 ✓
- RGB spike (non-blocking) → Task 15 ✓
- Content angle → captured in spec §11 (no code task; downstream) ✓

**Placeholder scan:** none — every code step contains complete, runnable code.

**Type consistency:** `Effects` defined once (Task 5), implemented in Task 8, consumed in Task 7/12. `Engine` signature stable across Tasks 7/12. `save_config`/`load_config`/`parse_config` names consistent. Control-id vocabulary (`k1..k12`, `knob{1,2}.{ccw,cw,press}`) identical across config, HUD, editor.
```
