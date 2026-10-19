"""Reiter ausblenden (Einstellung „Reiter in der Leiste“): DATEI und PAPIER bleiben immer, Objekte
ausgeblendeter Reiter bleiben bearbeitbar, Tastenkürzel wirken weiter."""
from PySide6.QtWidgets import QApplication

from labelwerk.document import BarcodeObject, Document, TextObject
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.gui.tools import TOOLS
from labelwerk.settings import HIDEABLE_TOOLS, Settings

from test_gui_cups import queue  # noqa: F401  (Fixture: CUPS-Warteschlangen Dymo/Laser)
from test_gui_printers import workers  # noqa: F401  (Fixture)


def _window(qtbot, objects=None, **settings):
    win = MainWindow(doc=Document("62", objects=objects or [TextObject("A")]),
                     settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    win.show()
    return win


def _checked(win) -> list[str]:
    """Hervorgehobene Knöpfe in der Leiste (ausgeblendete zählen nicht – man sieht sie nicht)."""
    return [key for key, action in win.tool_actions.items()
            if action.isChecked() and action.isVisible()]


def test_hideable_tools_are_all_tools_but_file_and_paper():
    assert list(HIDEABLE_TOOLS) == [t.key for t in TOOLS if t.key not in ("file", "paper")]


def test_hidden_tools_have_no_button(qtbot):
    win = _window(qtbot, hidden_tools=["barcode", "series"])
    visible = {key: action.isVisible() for key, action in win.tool_actions.items()}
    assert visible == {"file": True, "paper": True, "text": True, "image": True,
                       "barcode": False, "layout": True, "series": False}


def test_selecting_an_object_of_a_hidden_tool_shows_its_panel(qtbot):
    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
                  hidden_tools=["barcode"])
    win.render_now()
    win.canvas.set_selection([1])
    QApplication.processEvents()
    assert win.panels.currentWidget() is win.panel("barcode")
    assert _checked(win) == []                                     # kein Knopf hervorgehoben
    win.tool_actions["text"].trigger()                             # sichtbarer Reiter: normal
    assert _checked(win) == ["text"] and win.panels.currentWidget() is win.panel("text")


def test_hidden_tool_shown_by_selection_is_not_remembered(qtbot):
    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
                  hidden_tools=["barcode"])
    win.tool_actions["layout"].trigger()
    win.tool_actions["text"].trigger()
    win.render_now()
    win.canvas.set_selection([1])
    QApplication.processEvents()
    assert win.panels.currentWidget() is win.panel("barcode")
    assert win.settings.last_tool == "text"


def test_hidden_start_tool_starts_with_paper(qtbot):
    win = _window(qtbot, start_tool="series", hidden_tools=["series"])
    assert _checked(win) == ["paper"] and win.panels.currentWidget() is win.panel("paper")


def test_hidden_last_tool_starts_with_paper(qtbot):
    win = _window(qtbot, start_tool="last", last_tool="layout", hidden_tools=["layout"])
    assert _checked(win) == ["paper"]


def test_shortcuts_of_hidden_tools_keep_working(qtbot):
    win = _window(qtbot, hidden_tools=["barcode"])
    win.shortcut_actions["barcode.insert"].trigger()
    assert any(isinstance(obj, BarcodeObject) for obj in win.doc.objects)
    assert win.panels.currentWidget() is win.panel("barcode") and _checked(win) == []


def test_hiding_the_current_tool_falls_back_to_paper(qtbot):
    win = _window(qtbot)
    win.tool_actions["series"].trigger()
    win.settings.hidden_tools = ["series"]
    win.apply_hidden_tools()
    assert not win.tool_actions["series"].isVisible()
    assert _checked(win) == ["paper"] and win.panels.currentWidget() is win.panel("paper")


def test_showing_tools_again(qtbot):
    win = _window(qtbot, hidden_tools=["text", "image"])
    win.settings.hidden_tools = []
    win.apply_hidden_tools()
    assert all(action.isVisible() for action in win.tool_actions.values())


def test_settings_dialog_has_a_checkbox_per_tool(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(hidden_tools=["series"]), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    boxes = dialog.tool_boxes
    assert list(boxes) == [t.key for t in TOOLS]
    for key in ("file", "paper"):
        assert boxes[key].isChecked() and not boxes[key].isEnabled()
    assert not boxes["series"].isChecked() and boxes["text"].isChecked()
    boxes["barcode"].setChecked(False)
    boxes["series"].setChecked(True)
    assert dialog.values().hidden_tools == ["barcode"]


def test_saving_settings_applies_hidden_tools_immediately(qtbot, monkeypatch):
    win = _window(qtbot)

    class FakeDialog:
        DialogCode = SettingsDialog.DialogCode

        def __init__(self, settings, **kw):
            self.saved = Settings(**{**vars(settings), "hidden_tools": ["layout"]})

        def exec(self):
            return SettingsDialog.DialogCode.Accepted

        def deleteLater(self):
            pass

    from labelwerk.gui import main_window as mw
    monkeypatch.setattr(mw, "SettingsDialog", FakeDialog)
    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: None)
    monkeypatch.setattr(win, "_save_settings", lambda *keys: None)
    win.open_settings()
    assert not win.tool_actions["layout"].isVisible()


# --- SERIE erscheint, solange sie gebraucht wird -----------------------------------
def test_series_button_appears_while_the_label_has_a_series(qtbot):
    from labelwerk.document import Numbering, Series
    win = _window(qtbot, hidden_tools=["series"])
    win.render_now()
    assert not win.tool_actions["series"].isVisible()
    win.doc.series = Series(numbering=Numbering(count=3))
    win.render_now()
    assert win.tool_actions["series"].isVisible()
    win.doc.series = None
    win.render_now()
    assert not win.tool_actions["series"].isVisible()


def test_series_button_visible_for_a_file_with_a_series(qtbot):
    from labelwerk.document import Numbering, Series
    win = _window(qtbot, objects=[TextObject("Nr {Nummer}")], hidden_tools=["series"])
    win.doc.series = Series(numbering=Numbering(count=2))
    win.render_now()
    assert win.tool_actions["series"].isVisible()


def test_series_button_visible_with_driver_cut_options(qtbot, monkeypatch, queue, workers):
    from test_gui_printers import _window as printer_window
    win = printer_window(qtbot, monkeypatch, [], printer="cups:Dymo", hidden_tools=["series"])
    assert win.panel("series").driver_cuts
    assert win.tool_actions["series"].isVisible()
    win.choose_printer("cups:Laser")                               # Treiber ohne Schnitt-Option
    assert not win.tool_actions["series"].isVisible()


def test_settings_dialog_explains_that_series_can_appear(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    assert dialog.tools_note.objectName() == "note" and "Serie" in dialog.tools_note.text()


# --- Nach SPEICHERN nur zurückfallen, wenn nötig -----------------------------------
def _save_with(win, monkeypatch, **changes):
    class FakeDialog:
        DialogCode = SettingsDialog.DialogCode

        def __init__(self, settings, **kw):
            self.saved = Settings(**{**vars(settings), **changes})

        def exec(self):
            return SettingsDialog.DialogCode.Accepted

        def deleteLater(self):
            pass

    from labelwerk.gui import main_window as mw
    monkeypatch.setattr(mw, "SettingsDialog", FakeDialog)
    monkeypatch.setattr(win, "_save_settings", lambda *keys: None)
    win.open_settings()


def test_saving_other_settings_keeps_the_panel_of_the_selection(qtbot, monkeypatch):
    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
                  hidden_tools=["barcode"])
    win.render_now()
    win.canvas.set_selection([1])
    QApplication.processEvents()
    _save_with(win, monkeypatch, start_zoom=150)
    assert win.panels.currentWidget() is win.panel("barcode")


def test_hiding_the_tool_of_the_selection_keeps_its_panel(qtbot, monkeypatch):
    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)])
    win.render_now()
    win.canvas.set_selection([1])
    QApplication.processEvents()
    _save_with(win, monkeypatch, hidden_tools=["barcode"])
    assert win.panels.currentWidget() is win.panel("barcode")


def test_hiding_text_keeps_the_edit_mode(qtbot, monkeypatch):
    win = _window(qtbot)
    win.render_now()
    win.edit_text(0)
    assert win.edit_session.active
    _save_with(win, monkeypatch, hidden_tools=["text"])
    assert win.edit_session.active and win.panels.currentWidget() is win.panel("text")


# --- Auswahl leer → zurück zu einem sichtbaren Reiter ------------------------------
def test_empty_selection_leaves_a_hidden_panel(qtbot):
    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
                  hidden_tools=["barcode", "text"])
    win.tool_actions["layout"].trigger()
    win.tool_actions["image"].trigger()                            # zuletzt benutzt: BILD
    win.render_now()
    win.canvas.set_selection([1])
    QApplication.processEvents()
    assert win.panels.currentWidget() is win.panel("barcode")
    win.canvas.set_selection([])
    QApplication.processEvents()
    assert win.panels.currentWidget() is win.panel("image") and _checked(win) == ["image"]
    assert win.canvas.tool() == "select"


def test_empty_selection_without_a_last_tool_goes_to_paper(qtbot):
    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
                  hidden_tools=["barcode", "text"])
    win.render_now()
    win.canvas.set_selection([0])
    QApplication.processEvents()
    assert win.panels.currentWidget() is win.panel("text")
    win.canvas.set_selection([])
    QApplication.processEvents()
    assert win.panels.currentWidget() is win.panel("paper")
    assert win.canvas.tool() == "select"                           # kein „Text anlegen“


# --- Einstellungsdialog: Reiter beim Start folgt den Häkchen -----------------------
def _enabled(combo, key) -> bool:
    return combo.model().item(combo.findData(key)).isEnabled()


def test_hidden_tools_are_disabled_as_start_tab(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(hidden_tools=["series"]), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    combo = dialog.start_tool
    assert not _enabled(combo, "series") and _enabled(combo, "text") and _enabled(combo, "last")
    dialog.tool_boxes["series"].setChecked(True)
    assert _enabled(combo, "series")


def test_hiding_the_start_tab_switches_to_last_used(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(start_tool="barcode"), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    dialog.tool_boxes["barcode"].setChecked(False)
    assert dialog.start_tool.currentData() == "last"
    assert dialog.values().start_tool == "last"


# --- SERIE: Panel gezeigt → Knopf bleibt, bis der Reiter wechselt ------------------
def _series_window(qtbot):
    win = _window(qtbot, hidden_tools=["series"])
    win.panel("series").numbering_button.click()                    # Nummerierung als Serie
    win.render_now()
    assert win.doc.series is not None
    win.tool_actions["series"].trigger()
    assert win.panels.currentWidget() is win.panel("series")
    return win


def test_series_button_stays_after_remove_while_shown(qtbot):
    win = _series_window(qtbot)
    win.panel("series").remove_button.click()
    win.render_now()
    assert win.doc.series is None and win.tool_actions["series"].isVisible()
    win.tool_actions["text"].trigger()
    assert not win.tool_actions["series"].isVisible()


def test_series_button_stays_after_new_label_while_shown(qtbot):
    win = _series_window(qtbot)
    win.files.new()
    win.render_now()
    assert win.doc.series is None
    assert win.panels.currentWidget() is not win.panel("series") \
        or win.tool_actions["series"].isVisible()
    win.tool_actions["paper"].trigger()
    assert not win.tool_actions["series"].isVisible()


def test_series_button_stays_after_printer_change_while_shown(qtbot, monkeypatch, queue, workers):
    from test_gui_printers import _window as printer_window
    win = printer_window(qtbot, monkeypatch, [], printer="cups:Dymo", hidden_tools=["series"])
    win.tool_actions["series"].trigger()
    win.choose_printer("cups:Laser")
    assert win.tool_actions["series"].isVisible()
    win.tool_actions["paper"].trigger()
    assert not win.tool_actions["series"].isVisible()


def test_unchanged_hidden_tools_in_other_order_do_not_fall_back(qtbot, monkeypatch):
    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
                  hidden_tools=["barcode", "layout"])
    win.render_now()
    win.canvas.set_selection([1])
    QApplication.processEvents()
    win.canvas.set_selection([1])
    _save_with(win, monkeypatch, hidden_tools=["layout", "barcode"])
    assert win.panels.currentWidget() is win.panel("barcode")


def test_start_tab_already_hidden_is_locked_without_restart_hint(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(start_tool="series", hidden_tools=["series"]), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    dialog.show()
    assert not _enabled(dialog.start_tool, "series")
    assert not dialog.restart_hint.isVisible()
    assert dialog.values().start_tool == "paper"                  # wie es tatsächlich startet


def test_start_with_hidden_tools_does_not_fall_back(qtbot):
    win = _window(qtbot, start_tool="text", hidden_tools=["barcode"])
    assert win.panels.currentWidget() is win.panel("text")


def test_undo_after_a_shortcut_insert_leaves_the_hidden_panel(qtbot):
    """Echtes Tastenkürzel fügt bei ausgeblendetem BARCODE ein (Panel nur für die Auswahl);
    Strg+Z nimmt es zurück – leere Auswahl kehrt zu einem sichtbaren Reiter zurück."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win = _window(qtbot, hidden_tools=["barcode"], shortcuts={"barcode.insert": "Ctrl+Shift+B"})
    win.tool_actions["image"].trigger()
    win.activateWindow()
    win.canvas.setFocus()
    qtbot.waitUntil(lambda: win.canvas.hasFocus(), timeout=1000)
    ctrl = Qt.KeyboardModifier.ControlModifier
    QTest.keyClick(win.canvas, Qt.Key.Key_B, ctrl | Qt.KeyboardModifier.ShiftModifier)
    assert any(isinstance(obj, BarcodeObject) for obj in win.doc.objects)
    assert win.panels.currentWidget() is win.panel("barcode")
    QTest.keyClick(win.canvas, Qt.Key.Key_Z, ctrl)
    QApplication.processEvents()
    assert not any(isinstance(obj, BarcodeObject) for obj in win.doc.objects)
    assert win.panels.currentWidget() is win.panel("image") and _checked(win) == ["image"]
