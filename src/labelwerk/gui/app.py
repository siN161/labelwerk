"""Einstiegspunkt labelwerk-gui."""
from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ..desktop import APP_ID

from .main_window import MainWindow


def load_theme(name: str = "rawblock") -> str:
    """Stylesheet aus labelwerk/gui/theme/<name>.qss."""
    return (resources.files("labelwerk.gui") / "theme" / f"{name}.qss").read_text(encoding="utf-8")


def apply_identity(app: QApplication) -> None:
    """Name, App-ID (Wayland: Zuordnung zum Starter-Eintrag) und Fenstersymbol setzen."""
    app.setApplicationName("labelwerk")
    app.setDesktopFileName(APP_ID)
    icon = resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg"
    app.setWindowIcon(QIcon(str(icon)))


def main() -> int:
    app = QApplication(sys.argv)
    apply_identity(app)
    app.setStyleSheet(load_theme())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
