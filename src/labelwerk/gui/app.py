"""Einstiegspunkt labelwerk-gui."""
from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ..desktop import APP_ID, APP_NAME

from .main_window import MainWindow


def load_theme(name: str = "rawblock") -> str:
    """Stylesheet aus labelwerk/gui/theme/<name>.qss; @THEME@ wird zum Theme-Ordner (für Grafiken)."""
    folder = resources.files("labelwerk.gui") / "theme"
    qss = (folder / f"{name}.qss").read_text(encoding="utf-8")
    return qss.replace("@THEME@", str(folder).replace("\\", "/"))


def apply_identity(app: QApplication) -> None:
    """Name, App-ID (Wayland: Zuordnung zum Starter-Eintrag) und Fenstersymbol setzen."""
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    icon = resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg"
    app.setWindowIcon(QIcon(str(icon)))


def install_translations(app: QApplication) -> QTranslator | None:
    """Qt-eigene Texte (Speichern, Abbrechen, Ja …) auf Deutsch – passend zu labelwerk."""
    translator = QTranslator(app)
    if translator.load(QLocale(QLocale.Language.German, QLocale.Country.Germany), "qtbase", "_",
                       QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        return translator
    return None


def main() -> int:
    app = QApplication(sys.argv)
    apply_identity(app)
    install_translations(app)
    app.setStyleSheet(load_theme())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
