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
        dialog.accept()                       # saves to XDG_CONFIG_HOME (test folder)
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
    path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings(font_family="Liberation Sans"), path=path)
    qtbot.addWidget(dialog)
    assert dialog.values().font_family == "Liberation Sans"
    dialog.font_family.set_current_family("DejaVu Sans")
    dialog.accept()
    assert load_settings(path).font_family == "DejaVu Sans"


def test_unknown_font_family_survives_unchanged_dialog(qtbot):
    dlg = SettingsDialog(Settings(font_family="GibtsGarNicht 4711"))
    qtbot.addWidget(dlg)
    assert dlg.values().font_family == "GibtsGarNicht 4711"


def test_changed_font_family_is_taken_over(qtbot):
    dlg = SettingsDialog(Settings(font_family="GibtsGarNicht 4711"))
    qtbot.addWidget(dlg)
    dlg.font_family.setCurrentIndex(0)
    dlg.font_family.setCurrentIndex(1)
    assert dlg.values().font_family == dlg.font_family.current_family() != "GibtsGarNicht 4711"


def test_all_fonts_option_fills_the_list_at_once(qtbot, monkeypatch):
    from labelwerk import fonts
    monkeypatch.setattr(fonts, "families",
                        lambda all=False: ["DejaVu Sans", "Zapf X"] if all else ["DejaVu Sans"])
    dlg = SettingsDialog(Settings(font_family="DejaVu Sans"))
    qtbot.addWidget(dlg)
    assert not dlg.fonts_all.isChecked() and dlg.font_family.count() == 1
    dlg.fonts_all.setChecked(True)                               # immediately in the list
    assert dlg.font_family.count() == 2 and dlg.font_family.current_family() == "DejaVu Sans"
    assert dlg.values().fonts_all is True and dlg.values().font_family == "DejaVu Sans"
    assert not dlg.restart_needed()                              # takes effect without a restart


def test_all_fonts_option_sits_under_the_font(qtbot):
    """Show all fonts" sits directly below the font (section NEW LABEL)."""
    from PySide6.QtWidgets import QFormLayout
    dlg = SettingsDialog(Settings())
    qtbot.addWidget(dlg)
    form = dlg.font_family.parentWidget().layout()
    assert isinstance(form, QFormLayout) and form is dlg.fonts_all.parentWidget().layout()
    row, __ = form.getWidgetPosition(dlg.font_family)
    assert form.getWidgetPosition(dlg.fonts_all)[0] == row + 1


def test_saved_all_fonts_option_applies_to_text_panel(qtbot, monkeypatch):
    from labelwerk import fonts
    monkeypatch.setattr(fonts, "families",
                        lambda all=False: ["DejaVu Sans", "Zapf X"] if all else ["DejaVu Sans"])
    win = MainWindow(settings=Settings(check_media_on_start=False, fonts_all=True))
    qtbot.addWidget(win)
    family = win.panel("text").family
    assert [family.itemText(i) for i in range(family.count())] == ["DejaVu Sans", "Zapf X"]
    monkeypatch.setattr(SettingsDialog, "exec", lambda self: (
        self.fonts_all.setChecked(False), self.accept(), QDialog.DialogCode.Accepted)[-1])
    win.open_settings()
    assert win.settings.fonts_all is False
    assert [family.itemText(i) for i in range(family.count())] == ["DejaVu Sans"]


def test_dialog_keeps_fractional_font_size(qtbot):
    dialog = SettingsDialog(Settings(font_size_pt=10.5))
    qtbot.addWidget(dialog)
    assert dialog.values().font_size_pt == 10.5


def test_dialog_theme_roundtrip(qtbot):
    dialog = SettingsDialog(Settings(theme="classic"))
    qtbot.addWidget(dialog)
    assert dialog.theme.currentText() == "Klassisch"
    assert dialog.values().theme == "classic"
    dialog.theme.setCurrentIndex(dialog.theme.findData("blackwerk"))
    assert dialog.values().theme == "blackwerk"


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
        apply_theme(qapp, "blackwerk")
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


# --- Tab Shortcuts -----------------------------------------------------------------
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
    assert tabs.widget(0).isAncestorOf(dialog.label)        # existing fields under General


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
    dialog.set_shortcut("edit.cut", "")                     # shortcut cleared
    dialog.set_shortcut("edit.paste", "Ctrl+V")             # = default
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
    table.cellClicked.emit(_row("file.print"), 0)           # click anywhere in the row
    editor = table.findChild(QKeySequenceEdit)
    assert editor is not None and editor.isClearButtonEnabled()
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    assert editor.maximumSequenceLength() == 1                 # exactly one key combination
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
    dialog.set_shortcut("app.settings", "Ctrl+P")           # like "Print"
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
    dialog.set_shortcut("text.bold", "Ctrl+D")             # "Duplicate" applies only on the canvas
    assert dialog.save_button.isEnabled()


def test_conflict_with_saved_settings_is_shown_on_open(qtbot):
    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"edit.copy": "Ctrl+X"}))
    assert _is_red(dialog, "edit.cut") and not dialog.save_button.isEnabled()


def test_standard_button_resets_one_row(qtbot):
    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P",
                                                         "edit.copy": ""}))
    assert dialog.reset_button("edit.paste") is None            # already default
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
    assert win.shortcut_actions["text.bold"] in win.panel("text").actions()   # B/I/U via the actions
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
    editor.setKeySequence(QKeySequence(Qt.Key.Key_Shift))   # only a modifier key
    index = table.model().index(_row("edit.copy"), 2)
    delegate.setModelData(editor, table.model(), index)
    assert dialog.shortcut("edit.copy") == "Ctrl+C"         # unchanged
    assert not dialog.key_hint.isHidden()
    assert "Shift" in dialog.key_hint.text() and "Kopieren" in dialog.key_hint.text()
    dialog.set_shortcut("edit.copy", "Ctrl+Shift+C")        # next valid input
    assert dialog.key_hint.isHidden()


def test_dialog_fits_on_small_screens(qtbot):
    from PySide6.QtCore import QSize
    from labelwerk.gui.settings_dialog import DIALOG_SIZE, MIN_SIZE, initial_size
    dialog = _shortcut_dialog(qtbot)
    assert (dialog.minimumWidth(), dialog.minimumHeight()) == MIN_SIZE   # minimum size, not fixed
    assert initial_size(QSize(1920, 1080)) == QSize(*DIALOG_SIZE)
    small = initial_size(QSize(700, 500))
    assert small.width() <= 700 and small.height() <= 500
    assert initial_size(QSize(300, 200)) == QSize(*MIN_SIZE)  # never smaller than the minimum size
    screen = dialog.screen().availableGeometry().size()
    assert dialog.size() == initial_size(screen)


def test_dialog_keeps_symbol_lists(qtbot):
    """The symbol window maintains recently used and favourites – the dialog passes them through."""
    dialog = SettingsDialog(Settings(symbols_recent=["labelwerk/erde"],
                                     symbols_favorites=["iso7010/W012"]))
    qtbot.addWidget(dialog)
    values = dialog.values()
    assert (values.symbols_recent, values.symbols_favorites) == (["labelwerk/erde"], ["iso7010/W012"])


def test_dialog_keeps_recent_files_and_start_favorite(qtbot):
    dialog = SettingsDialog(Settings(recent_files=["/a.labelwerk"], start_favorite="Absender"))
    qtbot.addWidget(dialog)
    values = dialog.values()
    assert (values.recent_files, values.start_favorite) == (["/a.labelwerk"], "Absender")


def test_dialog_start_tool_choice(qtbot, tmp_path):
    path = tmp_path / "s.json"
    dialog = SettingsDialog(Settings(start_tool="series", last_tool="image"), path)
    qtbot.addWidget(dialog)
    combo = dialog.start_tool
    assert combo.currentData() == "series"
    assert [combo.itemData(i) for i in range(combo.count())] == [
        "last", "file", "paper", "text", "image", "barcode", "layout", "series", "parcel"]
    assert combo.itemText(0) == "Zuletzt benutzter" and combo.itemText(2) == "Papier"
    assert dialog.restart_hint.isHidden()
    combo.setCurrentIndex(combo.findData("last"))
    assert not dialog.restart_hint.isHidden()                       # takes effect only at the next start
    dialog.accept()
    saved = load_settings(path)
    assert (saved.start_tool, saved.last_tool) == ("last", "image")  # last used stays


def test_dialog_image_defaults(qtbot, tmp_path):
    path = tmp_path / "s.json"
    dialog = SettingsDialog(Settings(image_mode="photo", image_threshold=90), path)
    qtbot.addWidget(dialog)
    assert dialog.image_mode.currentData() == "photo" and dialog.image_threshold.value() == 90
    assert [dialog.image_mode.itemText(i) for i in range(2)] == ["Strich", "Foto"]
    dialog.image_mode.setCurrentIndex(dialog.image_mode.findData("line"))
    dialog.image_threshold.setValue(150)
    assert dialog.restart_hint.isHidden()                           # takes effect immediately
    dialog.accept()
    saved = load_settings(path)
    assert (saved.image_mode, saved.image_threshold) == ("line", 150)


def test_saved_image_defaults_apply_at_once(qtbot, monkeypatch):
    from labelwerk.document import Document, TextObject
    from labelwerk.gui import main_window as mw
    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)

    class Dialog:
        DialogCode = mw.SettingsDialog.DialogCode

        def __init__(self, settings, **kwargs):
            self.saved = Settings(**{**vars(settings), "image_mode": "photo",
                                     "image_threshold": 70, "warnings": []})

        def exec(self):
            return self.DialogCode.Accepted

        def deleteLater(self):
            pass

    monkeypatch.setattr(mw, "SettingsDialog", Dialog)
    win.open_settings()
    panel = win.panel("image")
    assert panel.photo.isChecked() and panel.threshold.value() == 70


def test_font_list_is_read_once_at_startup(qtbot, monkeypatch):
    """With "Show all fonts" the start reads only the full list (not the short one first)."""
    from labelwerk import fonts
    calls = []

    def families(all=False):
        calls.append(all)
        return ["DejaVu Sans", "Zapf X"] if all else ["DejaVu Sans"]
    monkeypatch.setattr(fonts, "families", families)
    win = MainWindow(settings=Settings(check_media_on_start=False, fonts_all=True))
    qtbot.addWidget(win)
    assert calls == [True]
    assert win.panel("text").family.count() == 2
