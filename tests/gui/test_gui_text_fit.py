"""Longer texts (English/German) fit: in no panel, in the settings dialog and in the
toolbar is a button or a label cut off or sticking out over the edge.

With ``LABELWERK_SHOTS=/folder`` the test saves screenshots per language and panel (acceptance).
"""
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QLabel, QPushButton,
                               QRadioButton, QToolButton)

from labelwerk import i18n
from labelwerk.document import BarcodeObject, Document, ImageObject, Numbering, Series, TextObject
from labelwerk.gui.app import install_translations, load_theme
from labelwerk.gui.main_window import PANEL_WIDTH, MainWindow
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.gui.tools import TOOLS
from labelwerk.settings import Settings

SHOTS = os.environ.get("LABELWERK_SHOTS")


def _cut_off(root, limit: int | None = None) -> list[str]:
    """Visible buttons/labels whose text does not fit completely or which stick out beyond
    ``limit`` (right edge in pixels, relative to ``root``)."""
    problems = []
    for widget in root.findChildren(QAbstractButton) + root.findChildren(QLabel):
        if not widget.isVisibleTo(root) or not widget.text():
            continue
        text = widget.text().replace("\n", " ")
        if isinstance(widget, QLabel) and widget.wordWrap():
            pass                                           # wraps
        elif isinstance(widget, (QPushButton, QToolButton, QCheckBox, QRadioButton, QLabel)) \
                and widget.width() < widget.minimumSizeHint().width() - 1:
            problems.append(f"abgeschnitten: {text!r} ({widget.width()} < "
                            f"{widget.minimumSizeHint().width()})")
        if limit is not None:
            right = widget.mapTo(root, widget.rect().topRight()).x()
            if right > limit + 1:
                problems.append(f"ragt hinaus: {text!r} (bis {right} > {limit})")
    return problems


@pytest.fixture(params=["en", "de"])
def language(request, qapp):
    i18n.set_language(request.param)
    QLocale.setDefault(QLocale(request.param))
    translator = install_translations(qapp)                # Qt buttons ("Save") as in the program
    qapp.setStyleSheet(load_theme())                       # BlackWerk: default theme
    yield request.param
    QLocale.setDefault(QLocale("de"))
    qapp.setStyleSheet("")
    if translator is not None:
        qapp.removeTranslator(translator)


def _shot(widget, name: str) -> None:
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        widget.grab().save(str(Path(SHOTS) / f"{name}.png"))


def _window(qtbot, doc, width=1280):
    win = MainWindow(doc=doc, settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.resize(width, 800)
    win.show()
    win.render_now()
    return win


def _panels(win, language: str, name: str) -> list[str]:
    problems = []
    for tool in TOOLS:
        win._show_tool(tool.key)
        QApplication.processEvents()
        panel = win.panel(tool.key)
        problems += [f"{language} {name} {tool.key}: {p}" for p in _cut_off(panel, PANEL_WIDTH)]
        _shot(panel, f"{language}-{name}-{tool.key}")
    return problems


def test_panels_fit(qtbot, language):
    win = _window(qtbot, Document("62", objects=[TextObject("A")]))
    problems = _panels(win, language, "text")
    problems += [f"{language} Werkzeugleiste/Statusleiste: {p}"
                 for p in _cut_off(win.statusBar()) + _cut_off(win.menuWidget() or win)]
    _shot(win, f"{language}-fenster")
    assert problems == []


def test_panels_with_selected_objects_fit(qtbot, language):
    from PIL import Image
    image = ImageObject.from_image(Image.new("RGB", (200, 100), "black"), 300, "bild.png")
    doc = Document("62", objects=[BarcodeObject(kind="code128", data="ABC-123", module=2),
                                  image, TextObject("X{Nummer}")],
                   series=Series(numbering=Numbering(count=3)))
    win = _window(qtbot, doc)
    win.panel("series").refresh()
    problems = []
    for index, name in ((0, "barcode"), (1, "bild")):
        win.canvas.set_selection([index])
        QApplication.processEvents()
        assert win.canvas.selection() == [index]
        problems += _panels(win, language, name)
    assert problems == []


def test_status_bar_fits_at_1024(qtbot, language):
    win = _window(qtbot, Document("62", objects=[TextObject("A")]), width=1024)
    win._set_result(i18n._("Settings saved – they apply to new labels."), "ok")
    QApplication.processEvents()
    _shot(win.statusBar(), f"{language}-statusleiste-1024")
    assert _cut_off(win.statusBar()) == []


def test_symbol_window_fits(qtbot, language):
    win = _window(qtbot, Document("62", objects=[TextObject("A")]))
    win.open_symbols()
    QApplication.processEvents()
    _shot(win.symbol_window, f"{language}-symbole")
    assert _cut_off(win.symbol_window) == []


def test_settings_dialog_fits(qtbot, language, tmp_path):
    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.zoom.setValue(150)                              # with restart notice next to SAVE
    assert dialog.restart_hint.isVisible()
    QApplication.processEvents()
    assert _cut_off(dialog) == []
    _shot(dialog, f"{language}-einstellungen")
