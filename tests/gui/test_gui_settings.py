import json
import os
from pathlib import Path

from PySide6.QtWidgets import QDialog

from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.settings import Settings, load_settings


def test_dialog_shows_current_settings(qtbot):
    dialog = SettingsDialog(Settings(label_id="62x29", orientation="horizontal", margin_mm=3,
                                     font_size_pt=19, check_media_on_start=False, start_zoom=150))
    qtbot.addWidget(dialog)
    assert dialog.values() == Settings(label_id="62x29", orientation="horizontal", margin_mm=3.0,
                                       font_size_pt=19, check_media_on_start=False, start_zoom=150)


def test_dialog_saves_to_file(qtbot, tmp_path):
    path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings(), path=path)
    qtbot.addWidget(dialog)
    dialog.orientation.setCurrentIndex(dialog.orientation.findData("horizontal"))
    dialog.font_auto.setChecked(False)
    dialog.font_size.setValue(19)
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    saved = load_settings(path)
    assert (saved.orientation, saved.font_size_pt) == ("horizontal", 19)
    assert dialog.saved == saved


def test_dialog_save_error_keeps_dialog_open(qtbot, tmp_path):
    blocker = tmp_path / "datei"
    blocker.write_text("x")
    dialog = SettingsDialog(Settings(), path=blocker / "settings.json")
    qtbot.addWidget(dialog)
    dialog.accept()
    assert dialog.saved is None
    assert not dialog.error.isHidden() and "nicht gespeichert" in dialog.error.text()


def test_window_opens_dialog_and_takes_new_settings(qtbot, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)

    def fake_exec(dialog):
        dialog.check_media.setChecked(False)
        dialog.accept()                       # speichert in XDG_CONFIG_HOME (Test-Ordner)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
    win.settings_action.trigger()
    assert win.settings.check_media_on_start is False
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    assert json.loads(path.read_text())["check_media_on_start"] is False
    assert "gespeichert" in win.result.text()


def test_qt_dialog_buttons_are_german(qapp):
    import pytest
    from PySide6.QtWidgets import QDialogButtonBox
    from labelwerk.gui.app import install_translations
    translator = install_translations(qapp)
    if translator is None:
        pytest.skip("qtbase_de.qm nicht installiert")
    try:
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        assert sorted(b.text() for b in box.buttons()) == ["Abbrechen", "Speichern"]
    finally:
        qapp.removeTranslator(translator)


def test_dialog_font_family_roundtrip(qtbot, tmp_path):
    from PySide6.QtGui import QFont
    path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings(font_family="Liberation Sans"), path=path)
    qtbot.addWidget(dialog)
    assert dialog.values().font_family == "Liberation Sans"
    dialog.font_family.setCurrentFont(QFont("DejaVu Sans"))
    dialog.accept()
    assert load_settings(path).font_family == "DejaVu Sans"


def test_unknown_font_family_survives_unchanged_dialog(qtbot):
    dlg = SettingsDialog(Settings(font_family="GibtsGarNicht 4711"))
    qtbot.addWidget(dlg)
    assert dlg.values().font_family == "GibtsGarNicht 4711"


def test_changed_font_family_is_taken_over(qtbot):
    from PySide6.QtGui import QFont
    dlg = SettingsDialog(Settings(font_family="GibtsGarNicht 4711"))
    qtbot.addWidget(dlg)
    dlg.font_family.setCurrentIndex(0)
    dlg.font_family.setCurrentIndex(1)
    assert dlg.values().font_family == dlg.font_family.currentFont().family() != "GibtsGarNicht 4711"


def test_dialog_keeps_fractional_font_size(qtbot):
    dialog = SettingsDialog(Settings(font_size_pt=10.5))
    qtbot.addWidget(dialog)
    assert dialog.values().font_size_pt == 10.5


def test_dialog_theme_roundtrip(qtbot):
    dialog = SettingsDialog(Settings(theme="classic"))
    qtbot.addWidget(dialog)
    assert dialog.theme.currentText() == "Klassisch"
    assert dialog.values().theme == "classic"
    dialog.theme.setCurrentIndex(dialog.theme.findData("rawblock"))
    assert dialog.values().theme == "rawblock"


def test_apply_theme_sets_and_clears_stylesheet(qapp):
    from labelwerk.gui.app import apply_theme
    try:
        apply_theme(qapp, "rawblock")
        assert qapp.styleSheet() != ""
        apply_theme(qapp, "classic")
        assert qapp.styleSheet() == ""
    finally:
        qapp.setStyleSheet("")


def test_saving_dialog_applies_theme_and_icons(qtbot, qapp, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)

    def fake_exec(dialog):
        dialog.theme.setCurrentIndex(dialog.theme.findData("classic"))
        dialog.accept()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
    try:
        qapp.setStyleSheet("QWidget { color: red; }")
        win.settings_action.trigger()
        assert qapp.styleSheet() == ""
        assert win.settings.theme == "classic"
        assert win.panel("text").dark_checked_icons is False
    finally:
        qapp.setStyleSheet("")
