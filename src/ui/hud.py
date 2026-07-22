# src/ui/hud.py
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QVBoxLayout, QHBoxLayout, QFrame
)
from src.models import Profile

# Physical layout: 3 rows x 4 cols of keys on the left, 2 knobs stacked on the right.
_KEY_GRID = [["k1", "k2", "k3", "k4"],
             ["k5", "k6", "k7", "k8"],
             ["k9", "k10", "k11", "k12"]]
# (display name, ccw id, press/click id, cw id)
_KNOBS = [("Knob 1", "knob1.ccw", "knob1.press", "knob1.cw"),
          ("Knob 2", "knob2.ccw", "knob2.press", "knob2.cw")]


class HudOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_now)
        self._cells = {}          # control id -> label widget
        self._sides = set()       # knob ccw/cw ids (get directional arrows)
        self._circles = set()     # knob press ids (circular; show a dot when empty)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._root = QFrame(self)
        self._root.setObjectName("hudRoot")
        outer.addWidget(self._root)

        root_v = QVBoxLayout(self._root)
        root_v.setContentsMargins(18, 14, 18, 16)
        root_v.setSpacing(12)

        self._title = QLabel("", self._root)
        self._title.setObjectName("hudTitle")
        root_v.addWidget(self._title)

        body = QHBoxLayout()
        body.setSpacing(20)

        # --- key grid (left) ---
        grid = QGridLayout()
        grid.setSpacing(7)
        for r, row in enumerate(_KEY_GRID):
            for c, cid in enumerate(row):
                cell = QLabel("", self._root)
                cell.setObjectName("hudCell")
                cell.setAlignment(Qt.AlignCenter)
                cell.setWordWrap(True)
                cell.setFixedSize(80, 54)
                grid.addWidget(cell, r, c)
                self._cells[cid] = cell
        body.addLayout(grid)

        # --- knob column (right) ---
        knob_col = QVBoxLayout()
        knob_col.setSpacing(12)
        for name, ccw, press, cw in _KNOBS:
            frame = QFrame(self._root)
            frame.setObjectName("hudKnobFrame")
            kv = QVBoxLayout(frame)
            kv.setContentsMargins(10, 8, 10, 8)
            kv.setSpacing(6)

            name_lbl = QLabel(name, frame)
            name_lbl.setObjectName("hudKnobName")
            name_lbl.setAlignment(Qt.AlignCenter)
            kv.addWidget(name_lbl)

            row = QHBoxLayout()
            row.setSpacing(8)
            lccw = QLabel("", frame)
            lccw.setObjectName("hudKnobSide")
            lccw.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lccw.setFixedWidth(70)
            lccw.setWordWrap(True)
            circle = QLabel("", frame)
            circle.setObjectName("hudKnobCircle")
            circle.setAlignment(Qt.AlignCenter)
            circle.setFixedSize(60, 60)
            circle.setWordWrap(True)
            lcw = QLabel("", frame)
            lcw.setObjectName("hudKnobSide")
            lcw.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lcw.setFixedWidth(70)
            lcw.setWordWrap(True)
            row.addWidget(lccw)
            row.addWidget(circle)
            row.addWidget(lcw)
            kv.addLayout(row)

            knob_col.addWidget(frame)
            self._cells[ccw] = lccw
            self._cells[cw] = lcw
            self._cells[press] = circle
            self._sides.update({ccw, cw})
            self._circles.add(press)
        knob_col.addStretch(1)
        body.addLayout(knob_col)

        root_v.addLayout(body)

    def _apply_theme(self, color: str):
        self.setStyleSheet(f"""
            #hudRoot {{
                background: rgba(22,22,24,238);
                border: 2px solid {color};
                border-radius: 16px;
            }}
            #hudTitle {{ color: {color}; font: 800 16px 'Segoe UI'; }}
            #hudCell {{
                background: #2a2a2d; color: #8a8a90;
                border: 1px solid #37373b; border-radius: 9px;
                font: 600 10px 'Segoe UI'; padding: 2px;
            }}
            #hudCell[mapped="true"] {{
                background: #34313d; color: #ffffff; border: 1px solid {color};
            }}
            #hudKnobFrame {{
                background: rgba(255,255,255,0.03);
                border: 1px solid #333338; border-radius: 14px;
            }}
            #hudKnobName {{
                color: #7a7a80; font: 700 8px 'Segoe UI';
                letter-spacing: 2px;
            }}
            #hudKnobSide {{ color: #6f6f75; font: 10px 'Segoe UI'; }}
            #hudKnobSide[mapped="true"] {{ color: #e6e6e6; }}
            #hudKnobCircle {{
                background: #2a2a2d; color: #6f6f75;
                border: 2px solid #47474d; border-radius: 30px;
                font: 700 9px 'Segoe UI';
            }}
            #hudKnobCircle[mapped="true"] {{
                border: 2px solid {color}; color: #ffffff; background: #34313d;
            }}
        """)

    def _set_cell(self, cid: str, profile: Profile):
        lbl = self._cells.get(cid)
        if lbl is None:
            return
        b = profile.keys.get(cid)
        mapped = b is not None
        if mapped:
            text = b.label
            if cid in self._sides:
                text = f"↺ {text}" if cid.endswith(".ccw") else f"{text} ↻"
        else:
            text = "•" if cid in self._circles else ""
        lbl.setText(text)
        lbl.setProperty("mapped", "true" if mapped else "false")
        lbl.style().unpolish(lbl)
        lbl.style().polish(lbl)

    def show_profile(self, profile: Profile, controls=None):
        self._title.setText(profile.name)
        self._apply_theme(profile.color)
        for cid in self._cells:
            self._set_cell(cid, profile)
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
