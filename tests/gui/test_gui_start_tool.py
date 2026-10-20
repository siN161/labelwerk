"""Tab at startup (setting “Tab at startup”: fixed tab or last used)."""
import pytest

from labelwerk.document import Document, TextObject
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.tools import START_TOOL, TOOLS
from labelwerk.settings import START_TOOLS, Settings, load_settings


def _window(qtbot, **settings):
    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
                     settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    return win


def _current(win) -> str:
    return next(key for key, action in win.tool_actions.items() if action.isChecked())


def test_start_tools_are_the_tools_of_the_window():
    assert list(START_TOOLS[1:]) == [tool.key for tool in TOOLS]


def test_default_start_tool_is_paper(qtbot):
    win = _window(qtbot)
    assert START_TOOL == "paper" and _current(win) == "paper"
    assert win.panels.currentWidget() is win.panel("paper")


@pytest.mark.parametrize("key", ["series", "text", "file"])
def test_fixed_start_tool(qtbot, key):
    win = _window(qtbot, start_tool=key, last_tool="image")
    assert _current(win) == key and win.panels.currentWidget() is win.panel(key)


def test_last_used_tool(qtbot):
    win = _window(qtbot, start_tool="last", last_tool="barcode")
    assert _current(win) == "barcode" and win.panels.currentWidget() is win.panel("barcode")


def test_last_used_without_a_value_starts_with_paper(qtbot):
    assert _current(_window(qtbot, start_tool="last")) == "paper"


def test_switching_tabs_remembers_the_last_tool_and_saves_it_on_close(qtbot, monkeypatch):
    from labelwerk.gui import main_window as mw
    saved = []
    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: saved.append(f["last_tool"]))
    win = _window(qtbot)
    win.tool_actions["series"].trigger()
    assert win.settings.last_tool == "series"
    win._show_tool("barcode")                                         # also without a click
    assert win.settings.last_tool == "barcode"
    assert saved == [] and win.result.text() == ""                    # in memory, silently
    win.close()
    assert saved == ["barcode"]                                       # when closing, once


def test_last_tool_is_not_saved_on_close_when_unchanged(qtbot, monkeypatch):
    from labelwerk.gui import main_window as mw
    saved = []
    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: saved.append(f["last_tool"]))
    win = _window(qtbot, start_tool="last", last_tool="image")
    win.tool_actions["text"].trigger()
    win.tool_actions["image"].trigger()                               # again as at startup
    win.close()
    assert saved == []


def test_last_tool_reaches_the_file_on_close(qtbot):
    win = _window(qtbot)
    win.tool_actions["layout"].trigger()
    assert load_settings().last_tool != "layout"
    win.close()
    assert load_settings().last_tool == "layout"


def test_save_error_on_close_is_ignored(qtbot, monkeypatch):
    from labelwerk.gui import main_window as mw

    def fail(*args, **fields):
        raise OSError("Datenträger voll")
    monkeypatch.setattr(mw, "update_settings", fail)
    win = _window(qtbot)
    win.tool_actions["layout"].trigger()
    win.close()                                                       # no crash
    assert not win.isVisible()


def test_close_cancelled_saves_nothing(qtbot, monkeypatch):
    from labelwerk.gui import main_window as mw
    saved = []
    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: saved.append(f["last_tool"]))
    win = _window(qtbot)
    win.show()
    win.tool_actions["layout"].trigger()
    monkeypatch.setattr(win.files, "maybe_save", lambda: False)       # prompt: Cancel
    win.close()
    assert saved == [] and win.isVisible()
    monkeypatch.setattr(win.files, "maybe_save", lambda: True)
    win.close()
    assert saved == ["layout"]


def test_start_in_text_tab_creates_text(qtbot):
    win = _window(qtbot, start_tool="text")
    assert win.canvas.tool() == "text"
    assert _window(qtbot, start_tool="image").canvas.tool() == "select"


def test_settings_dialog_keeps_the_last_tool(qtbot, monkeypatch):
    """The dialog does not change the last used tab (even if it changes
    while the dialog is open)."""
    from labelwerk.gui import main_window as mw
    win = _window(qtbot)
    win.tool_actions["layout"].trigger()

    class Dialog:
        DialogCode = mw.SettingsDialog.DialogCode

        def __init__(self, settings, **kwargs):
            self.saved = Settings(**{**vars(settings), "last_tool": "file", "warnings": []})

        def exec(self):
            win.tool_actions["text"].trigger()                     # while the dialog is open
            return self.DialogCode.Accepted

        def deleteLater(self):
            pass

    monkeypatch.setattr(mw, "SettingsDialog", Dialog)
    win.open_settings()
    assert win.settings.last_tool == "text"


def test_last_tool_on_close_keeps_settings_saved_by_another_instance(qtbot):
    """A second instance (double-click on a file) changes the theme and saves; if the first one
    closes afterwards, the theme stays – only the tab is added."""
    from labelwerk.settings import save_settings
    save_settings(Settings(theme="rawblock"))
    win = _window(qtbot, theme="rawblock")
    win.tool_actions["layout"].trigger()
    save_settings(Settings(theme="classic"))                       # second instance
    win.close()
    s = load_settings()
    assert (s.theme, s.last_tool) == ("classic", "layout")


def test_silent_saves_keep_settings_saved_by_another_instance(qtbot, tmp_path):
    """Silent saving (Recently opened, printer chosen) writes only its field."""
    from labelwerk.settings import save_settings
    win = _window(qtbot, theme="rawblock")
    save_settings(Settings(theme="classic"))                       # second instance
    win.choose_printer("tcp://192.0.2.1")
    s = load_settings()
    assert (s.theme, s.printer) == ("classic", "tcp://192.0.2.1")
