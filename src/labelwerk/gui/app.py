"""Einstiegspunkt labelwerk-gui."""
from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import i18n
from ..desktop import APP_ID, APP_NAME
from ..settings import configured_language

from .main_window import MainWindow


def load_theme(name: str = "rawblock") -> str:
    """Stylesheet aus labelwerk/gui/theme/<name>.qss; @THEME@ wird zum Theme-Ordner (für Grafiken)."""
    folder = resources.files("labelwerk.gui") / "theme"
    qss = (folder / f"{name}.qss").read_text(encoding="utf-8")
    # in Anführungszeichen, damit Leerzeichen im Installationspfad nicht stören
    return qss.replace("url(@THEME@/", 'url("' + str(folder).replace("\\", "/") + "/").replace(".svg)", '.svg")')


def apply_theme(app: QApplication, name: str) -> None:
    """„rawblock“ = eigenes Stylesheet, „classic“ = reiner Qt-Systemstil (ohne Stylesheet)."""
    app.setStyleSheet(load_theme() if name == "rawblock" else "")


def apply_identity(app: QApplication) -> None:
    """Name, App-ID (Wayland: Zuordnung zum Starter-Eintrag) und Fenstersymbol setzen."""
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    icon = resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg"
    app.setWindowIcon(QIcon(str(icon)))


def install_translations(app: QApplication) -> QTranslator | None:
    """Qt-eigene Texte (Speichern, Abbrechen, Ja …) in der Sprache von labelwerk
    (``i18n.language()``); Englisch braucht keine Übersetzung (None)."""
    if i18n.language() == i18n.SOURCE:
        return None
    translator = QTranslator(app)
    if translator.load(QLocale(i18n.language()), "qtbase", "_",
                       QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        return translator
    return None


def set_language() -> str:
    """Sprache aus den Einstellungen (sonst System) setzen – vor dem ersten Text; Zahlen in Feldern
    mit ihrem Dezimaltrenner (``QLocale``)."""
    language = i18n.set_language(configured_language())
    QLocale.setDefault(QLocale(language))
    return language


def main() -> int:
    set_language()
    app = QApplication(sys.argv)
    apply_identity(app)
    install_translations(app)
    window = MainWindow()
    apply_theme(app, window.settings.theme)
    window.show()
    # labelwerk-gui [DATEI]: Datei öffnen (Doppelklick im Dateimanager), sonst Start-Favorit
    paths = [a for a in app.arguments()[1:] if not a.startswith("-")]
    window.start(paths[0] if paths else None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
