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
