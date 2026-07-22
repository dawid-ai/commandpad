# src/ui/editor.py
from PySide6.QtWidgets import (
    QWidget, QListWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QLabel, QScrollArea, QGridLayout, QDialog,
    QKeySequenceEdit
)
from PySide6.QtGui import QKeySequence
from src.config import load_config, save_config
from src.models import Action, KeyBinding, Match, Profile
from src.platform_impl.windows import WindowsAppDetector


def _seq_to_signal(seq: QKeySequence) -> str:
    """Convert a captured QKeySequence to commandpad's 'ctrl+shift+f' format."""
    text = seq.toString(QKeySequence.PortableText)
    if not text:
        return ""
    first = text.split(", ")[0]                     # take the first chord only
    return first.strip().lower().replace("meta", "win")

_CONTROL_IDS = [f"k{i}" for i in range(1, 13)] + [
    "knob1.ccw", "knob1.cw", "knob1.press", "knob2.ccw", "knob2.cw", "knob2.press"]
_ACTION_TYPES = ["send_keys", "open", "run", "text"]


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
        # header row
        for col, head in enumerate(["Control", "Label (shown on HUD)", "Type", "Keys / target / text", ""]):
            h = QLabel(head)
            h.setStyleSheet("color:#888;font-weight:600;")
            self._grid.addWidget(h, 0, col)
        for i, cid in enumerate(_CONTROL_IDS, start=1):
            self._grid.addWidget(QLabel(cid), i, 0)
            label = QLineEdit()
            atype = QComboBox(); atype.addItems(_ACTION_TYPES)
            payload = QLineEdit()   # keys/target/text combined field
            payload.setPlaceholderText("ctrl+c  ·  https://…  ·  a path  ·  text")
            cap = QPushButton("⌨")
            cap.setFixedWidth(32)
            cap.setToolTip("Press a shortcut to capture it (for send_keys)")
            cap.clicked.connect(lambda _=False, p=payload: self._capture_keys(p))
            self._grid.addWidget(label, i, 1)
            self._grid.addWidget(atype, i, 2)
            self._grid.addWidget(payload, i, 3)
            self._grid.addWidget(cap, i, 4)
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
                            target=val if t in ("open", "run") else None,
                            text=val if t == "text" else None)
            keys[cid] = KeyBinding(label=lbl or cid, action=action)
        p.keys = keys
        self._list.item(idx).setText(p.name)

    def _capture_keys(self, payload_field: QLineEdit):
        dlg = QDialog(self)
        dlg.setWindowTitle("Capture shortcut")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Press the key combination, then OK:"))
        kse = QKeySequenceEdit()
        try:
            kse.setMaximumSequenceLength(1)     # single chord (Qt 6.5+)
        except AttributeError:
            pass
        v.addWidget(kse)
        buttons = QHBoxLayout()
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        v.addLayout(buttons)
        kse.setFocus()
        if dlg.exec():
            sig = _seq_to_signal(kse.keySequence())
            if sig:
                payload_field.setText(sig)

    def _grab_app(self):
        proc, _ = self._detector.current()
        if proc:
            existing = self._process.text().strip()
            self._process.setText(f"{existing}, {proc}" if existing else proc)

    def _save(self):
        self._capture_profile(self._current_idx)
        save_config(self._config, self._path)
        self._on_saved()
