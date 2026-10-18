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


def test_dialog_image_import_roundtrip(qtbot):
    dialog = SettingsDialog(Settings(image_crop=False, image_rotate=True))
    qtbot.addWidget(dialog)
    assert not dialog.image_crop.isChecked() and dialog.image_rotate.isChecked()
    assert (dialog.values().image_crop, dialog.values().image_rotate) == (False, True)
    dialog.image_crop.setChecked(True)
    dialog.image_rotate.setChecked(False)
    assert (dialog.values().image_crop, dialog.values().image_rotate) == (True, False)


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


def test_dialog_keeps_shortcuts_when_saving(qtbot, tmp_path):
    path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings(shortcuts={"file.print": "Ctrl+Shift+P"}), path=path)
    qtbot.addWidget(dialog)
    dialog.accept()
    assert load_settings(path).shortcuts == {"file.print": "Ctrl+Shift+P"}


# --- Reiter „Tastenkürzel“ ----------------------------------------------------------
def _shortcut_dialog(qtbot, settings=None, path=None):
    dialog = SettingsDialog(settings or Settings(), path=path)
    qtbot.addWidget(dialog)
    return dialog


def _row(action_id):
    from labelwerk import shortcuts
    return [a.id for a in shortcuts.ACTIONS].index(action_id)


def _is_red(dialog, action_id):
    item = dialog.shortcut_table.item(_row(action_id), 0)
    return item.foreground().color().name() == "#ff0000"


def test_dialog_has_tabs_general_and_shortcuts(qtbot):
    dialog = _shortcut_dialog(qtbot)
    tabs = dialog.tabs
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["Allgemein", "Tastenkürzel"]
    assert tabs.widget(0).isAncestorOf(dialog.label)        # bisherige Felder unter „Allgemein“


def test_shortcut_table_lists_every_action_with_scope_and_keys(qtbot):
    from PySide6.QtGui import QKeySequence
    from labelwerk import shortcuts
    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P"}))
    table = dialog.shortcut_table
    assert table.rowCount() == len(shortcuts.ACTIONS)
    assert [table.horizontalHeaderItem(c).text() for c in range(3)] == ["Aktion", "Bereich", "Kürzel"]
    row = _row("file.print")
    assert (table.item(row, 0).text(), table.item(row, 1).text()) == ("Drucken", "Global")
    native = QKeySequence("Ctrl+Shift+P").toString(QKeySequence.SequenceFormat.NativeText)
    assert table.item(row, 2).text() == native
    assert table.item(_row("edit.copy"), 1).text() == "Arbeitsfläche"
    assert table.item(_row("text.bold"), 1).text() == "Schreibmodus"
    assert table.item(_row("align.left"), 2).text() == ""


def test_fixed_shortcut_row_is_not_editable(qtbot):
    from PySide6.QtCore import Qt
    dialog = _shortcut_dialog(qtbot)
    row = _row("text.end_edit")
    table = dialog.shortcut_table
    assert table.item(row, 1).text() == "Schreibmodus"
    assert not table.item(row, 2).flags() & Qt.ItemFlag.ItemIsEditable
    assert "fest" in table.item(row, 2).toolTip()
    assert table.item(_row("text.bold"), 2).flags() & Qt.ItemFlag.ItemIsEditable


def test_values_contain_only_changed_shortcuts(qtbot):
    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P"}))
    dialog.set_shortcut("edit.copy", "Ctrl+Shift+C")
    dialog.set_shortcut("edit.cut", "")                     # Kürzel geleert
    dialog.set_shortcut("edit.paste", "Ctrl+V")             # = Standard
    assert dialog.values().shortcuts == {"file.print": "Ctrl+Shift+P",
                                         "edit.copy": "Ctrl+Shift+C", "edit.cut": ""}


def test_shortcut_cell_edits_with_key_sequence_edit(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QKeySequenceEdit
    dialog = _shortcut_dialog(qtbot)
    dialog.show()
    dialog.activateWindow()
    dialog.tabs.setCurrentIndex(1)
    table = dialog.shortcut_table
    table.cellClicked.emit(_row("file.print"), 0)           # Klick irgendwo in die Zeile
    editor = table.findChild(QKeySequenceEdit)
    assert editor is not None and editor.isClearButtonEnabled()
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    assert editor.maximumSequenceLength() == 1                 # genau eine Tastenkombination
    QTest.keyClick(editor, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier
                   | Qt.KeyboardModifier.AltModifier)
    qtbot.waitUntil(lambda: dialog.shortcut("file.print") == "Ctrl+Alt+P", timeout=2000)
    assert dialog.values().shortcuts == {"file.print": "Ctrl+Alt+P"}


def test_escape_cancels_shortcut_editing(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QKeySequenceEdit
    dialog = _shortcut_dialog(qtbot)
    dialog.show()
    dialog.activateWindow()
    dialog.tabs.setCurrentIndex(1)
    dialog.shortcut_table.cellClicked.emit(_row("edit.copy"), 2)
    editor = dialog.shortcut_table.findChild(QKeySequenceEdit)
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not editor.isVisible(), timeout=1000)
    assert dialog.shortcut("edit.copy") == "Ctrl+C"


def test_conflict_marks_rows_red_and_blocks_saving(qtbot):
    dialog = _shortcut_dialog(qtbot)
    assert dialog.save_button.isEnabled() and dialog.conflict_hint.isHidden()
    dialog.set_shortcut("app.settings", "Ctrl+P")           # wie „Drucken“
    assert _is_red(dialog, "app.settings") and _is_red(dialog, "file.print")
    assert not _is_red(dialog, "edit.copy")
    assert not dialog.save_button.isEnabled()
    assert not dialog.conflict_hint.isHidden()
    assert "Drucken" in dialog.conflict_hint.text()
    assert "Einstellungen" in dialog.conflict_hint.text()
    dialog.set_shortcut("app.settings", "Ctrl+Shift+E")
    assert not _is_red(dialog, "file.print")
    assert dialog.save_button.isEnabled() and dialog.conflict_hint.isHidden()


def test_same_key_in_canvas_and_text_is_no_conflict(qtbot):
    dialog = _shortcut_dialog(qtbot)
    dialog.set_shortcut("text.bold", "Ctrl+D")             # „Duplizieren“ gilt nur auf der Fläche
    assert dialog.save_button.isEnabled()


def test_conflict_with_saved_settings_is_shown_on_open(qtbot):
    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"edit.copy": "Ctrl+X"}))
    assert _is_red(dialog, "edit.cut") and not dialog.save_button.isEnabled()


def test_standard_button_resets_one_row(qtbot):
    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P",
                                                         "edit.copy": ""}))
    assert dialog.reset_button("edit.paste") is None            # schon Standard
    dialog.reset_button("file.print").click()
    assert dialog.shortcut("file.print") == "Ctrl+P"
    assert dialog.reset_button("file.print") is None
    assert dialog.values().shortcuts == {"edit.copy": ""}


def test_reset_all(qtbot):
    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P",
                                                         "edit.copy": "Ctrl+X"}))
    assert not dialog.save_button.isEnabled()
    dialog.reset_all.click()
    assert dialog.values().shortcuts == {}
    assert dialog.save_button.isEnabled() and not _is_red(dialog, "edit.cut")


def test_saved_shortcut_takes_effect_in_window(qtbot, monkeypatch):
    from PySide6.QtGui import QKeySequence
    win = MainWindow(settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)

    def fake_exec(dialog):
        dialog.set_shortcut("file.print", "Ctrl+Shift+P")
        dialog.set_shortcut("text.bold", "Ctrl+Shift+B")
        dialog.accept()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
    win.settings_action.trigger()
    assert win.settings.shortcuts == {"file.print": "Ctrl+Shift+P", "text.bold": "Ctrl+Shift+B"}
    assert win.shortcut_actions["file.print"].shortcut() == QKeySequence("Ctrl+Shift+P")
    assert win.shortcut_actions["text.bold"].shortcut() == QKeySequence("Ctrl+Shift+B")
    assert win.shortcut_actions["text.bold"] in win.panel("text").actions()   # B/I/U über die Aktionen
    panel = win.panel("text")
    assert panel.bold.toolTip() == win.shortcut_actions["text.bold"].toolTip()
    assert "Ctrl+Shift+B" in panel.bold.toolTip() and "Ctrl+I" in panel.italic.toolTip()


def test_conflicting_shortcuts_from_file_warn_and_later_one_is_empty(qtbot):
    from PySide6.QtGui import QKeySequence
    win = MainWindow(settings=Settings(check_media_on_start=False,
                                       shortcuts={"edit.duplicate": "Ctrl+C"}))
    qtbot.addWidget(win)
    assert win.shortcut_actions["edit.copy"].shortcut() == QKeySequence("Ctrl+C")
    assert win.shortcut_actions["edit.duplicate"].shortcut().isEmpty()
    assert "Tastenkürzel doppelt belegt: Ctrl+C" in win.result.text()
    assert win.result.property("state") == "error"


def test_shortcut_hint_names_keys_that_cannot_be_assigned(qtbot):
    dialog = _shortcut_dialog(qtbot)
    assert "Esc, Enter und Tab" in dialog.shortcut_hint.text()


def test_rejected_key_input_is_reported(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QKeySequenceEdit
    dialog = _shortcut_dialog(qtbot)
    table = dialog.shortcut_table
    delegate = table.itemDelegateForColumn(2)
    editor = QKeySequenceEdit()
    qtbot.addWidget(editor)
    editor.setKeySequence(QKeySequence(Qt.Key.Key_Shift))   # nur eine Umschalttaste
    index = table.model().index(_row("edit.copy"), 2)
    delegate.setModelData(editor, table.model(), index)
    assert dialog.shortcut("edit.copy") == "Ctrl+C"         # unverändert
    assert not dialog.key_hint.isHidden()
    assert "Shift" in dialog.key_hint.text() and "Kopieren" in dialog.key_hint.text()
    dialog.set_shortcut("edit.copy", "Ctrl+Shift+C")        # nächste gültige Eingabe
    assert dialog.key_hint.isHidden()


def test_dialog_fits_on_small_screens(qtbot):
    from PySide6.QtCore import QSize
    from labelwerk.gui.settings_dialog import DIALOG_SIZE, MIN_SIZE, initial_size
    dialog = _shortcut_dialog(qtbot)
    assert (dialog.minimumWidth(), dialog.minimumHeight()) == MIN_SIZE   # Mindestgröße, nicht fest
    assert initial_size(QSize(1920, 1080)) == QSize(*DIALOG_SIZE)
    small = initial_size(QSize(700, 500))
    assert small.width() <= 700 and small.height() <= 500
    assert initial_size(QSize(300, 200)) == QSize(*MIN_SIZE)  # nie kleiner als die Mindestgröße
    screen = dialog.screen().availableGeometry().size()
    assert dialog.size() == initial_size(screen)


def test_dialog_keeps_symbol_lists(qtbot):
    """Zuletzt verwendet und Favoriten pflegt das Symbol-Fenster – der Dialog reicht sie durch."""
    dialog = SettingsDialog(Settings(symbols_recent=["labelwerk/erde"],
                                     symbols_favorites=["iso7010/W012"]))
    qtbot.addWidget(dialog)
    values = dialog.values()
    assert (values.symbols_recent, values.symbols_favorites) == (["labelwerk/erde"], ["iso7010/W012"])
