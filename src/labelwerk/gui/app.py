"""Entry point labelwerk-gui."""
from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import i18n
from ..desktop import APP_ID, APP_NAME
from ..settings import configured_file_dialog, configured_language

from . import file_dialog
from .main_window import MainWindow


def load_theme(name: str = "rawblock") -> str:
    """Stylesheet from labelwerk/gui/theme/<name>.qss; @THEME@ becomes the theme folder (for graphics)."""
    folder = resources.files("labelwerk.gui") / "theme"
    qss = (folder / f"{name}.qss").read_text(encoding="utf-8")
    # quoted so that spaces in the installation path do no harm
    return qss.replace("url(@THEME@/", 'url("' + str(folder).replace("\\", "/") + "/").replace(".svg)", '.svg")')


def apply_theme(app: QApplication, name: str) -> None:
    """“rawblock” = own stylesheet, “classic” = plain Qt system style (no stylesheet)."""
    app.setStyleSheet(load_theme() if name == "rawblock" else "")


def apply_identity(app: QApplication) -> None:
    """Set name, app ID (Wayland: link to the launcher entry) and window icon."""
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    icon = resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg"
    app.setWindowIcon(QIcon(str(icon)))


def install_translations(app: QApplication) -> QTranslator | None:
    """Qt's own texts (Save, Cancel, Yes …) in labelwerk's language
    (``i18n.language()``); English needs no translation (None)."""
    if i18n.language() == i18n.SOURCE:
        return None
    translator = QTranslator(app)
    if translator.load(QLocale(i18n.language()), "qtbase", "_",
                       QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        return translator
    return None


def set_language() -> str:
    """Set the language from the settings (else the system) – before the first text; numbers in
    fields with their decimal separator (``QLocale``)."""
    language = i18n.set_language(configured_language())
    QLocale.setDefault(QLocale(language))
    return language


def qt_arguments(argv: list[str], system_dialog: bool) -> list[str]:
    """Application arguments; system file dialog: platform theme “xdgdesktopportal” (Qt then uses
    the desktop's dialog via the XDG portal) – as an argument, not as an environment variable
    that child processes would inherit. Qt removes the option from ``arguments()``."""
    if not system_dialog:
        return list(argv)
    return [*argv[:1], "-platformtheme", "xdgdesktopportal", *argv[1:]]


def main() -> int:
    set_language()
    app = QApplication(qt_arguments(sys.argv, configured_file_dialog()
                                    and file_dialog.system_dialog_available()))
    apply_identity(app)
    install_translations(app)
    window = MainWindow()
    apply_theme(app, window.settings.theme)
    window.show()
    # labelwerk-gui [FILE]: open file (double-click in the file manager), else start favourite
    paths = [a for a in app.arguments()[1:] if not a.startswith("-")]
    window.start(paths[0] if paths else None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
