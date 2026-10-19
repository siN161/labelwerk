"""Sprache in der GUI: Wahl in den Einstellungen, Neustart-Hinweis, Zahlenfelder je Sprache,
Oberfläche auf Englisch."""
from PySide6.QtCore import QLocale

from labelwerk import i18n
from labelwerk.document import Document, TextObject
from labelwerk.gui import app as gui_app
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.gui.widgets import DoubleSpinBox
from labelwerk.settings import Settings, configured_language, load_settings, save_settings


def _window(qtbot, settings=None):
    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
                     settings=settings or Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


def test_language_choice_in_the_settings(qtbot, tmp_path):
    path = tmp_path / "s.json"
    dialog = SettingsDialog(Settings(), path)
    qtbot.addWidget(dialog)
    assert dialog.language.itemText(0) == "Automatisch (Systemsprache: Deutsch)"
    assert [dialog.language.itemText(i) for i in range(1, 3)] == ["Deutsch", "English"]
    assert dialog.restart_hint.isHidden()
    dialog.language.setCurrentIndex(dialog.language.findData("en"))
    assert not dialog.restart_hint.isHidden()
    assert dialog.restart_hint.text() == "Änderungen erst nach Neustart aktiv"
    dialog.language.setCurrentIndex(0)                    # zurück: Hinweis verschwindet
    assert dialog.restart_hint.isHidden()
    dialog.zoom.setValue(150)                             # Start-Zoom wirkt auch erst beim Start
    assert not dialog.restart_hint.isHidden()
    dialog.language.setCurrentIndex(dialog.language.findData("en"))
    dialog.accept()
    assert load_settings(path).language == "en" and configured_language(path) == "en"


def test_restart_notice_stays_next_to_save(qtbot, tmp_path):
    """Der Hinweis steht unten neben SPEICHERN – auch im Reiter Tastenkürzel sichtbar – und
    vergleicht mit dem Stand beim Start: wieder zurückgestellt, kein Hinweis."""
    dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
                            started={"language": "en", "start_zoom": 200,
                                     "start_tool": "paper", "system_file_dialog": False})
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.restart_hint.isHidden()
    dialog.language.setCurrentIndex(dialog.language.findData("de"))
    dialog.tabs.setCurrentIndex(1)                         # anderer Reiter: Hinweis bleibt sichtbar
    assert dialog.restart_hint.isVisible()
    assert dialog.restart_hint.parent() is dialog            # Fußzeile, nicht im Reiter
    dialog.language.setCurrentIndex(dialog.language.findData("en"))
    assert dialog.restart_hint.isHidden()


def test_saved_but_not_restarted_still_shows_the_notice(qtbot, tmp_path):
    """Gespeichert, aber noch nicht neu gestartet: beim nächsten Öffnen steht der Hinweis gleich da."""
    dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
                            started={"language": "de", "start_zoom": 200,
                                     "start_tool": "paper", "system_file_dialog": False})
    qtbot.addWidget(dialog)
    assert not dialog.restart_hint.isHidden()


def test_start_takes_the_configured_language(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_settings(Settings(language="en"))
    assert gui_app.set_language() == "en" and QLocale().decimalPoint() == "."
    save_settings(Settings(language=""))                   # Automatisch: LANGUAGE=de (conftest)
    assert gui_app.set_language() == "de" and QLocale().decimalPoint() == ","


def test_number_fields_take_comma_and_point(qtbot):
    box = DoubleSpinBox()
    qtbot.addWidget(box)
    box.setDecimals(1)
    box.setRange(0, 100)
    assert box.valueFromText("3.5") == box.valueFromText("3,5") == 3.5
    assert box.textFromValue(3.5) == "3,5"


def test_window_in_english(qtbot):
    i18n.set_language("en")
    win = _window(qtbot)
    win.render_now()
    texts = {b.text() for b in win.findChildren(type(win.cancel_button)) if b.text()}
    assert "CANCEL" in texts
    assert "Etikett" not in win.windowTitle()
