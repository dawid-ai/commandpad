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
