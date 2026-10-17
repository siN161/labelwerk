"""Einstiegspunkt labelwerk-gui."""
from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def load_theme(name: str = "rawblock") -> str:
    """Stylesheet aus labelwerk/gui/theme/<name>.qss."""
    return (resources.files("labelwerk.gui") / "theme" / f"{name}.qss").read_text(encoding="utf-8")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("labelwerk")
    app.setStyleSheet(load_theme())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
