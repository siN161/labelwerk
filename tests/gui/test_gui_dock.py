"""Side bar (properties panels) as a dock: resizable, left or right, detachable, remembered."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget

from labelwerk.document import Document, TextObject
from labelwerk.gui.main_window import PANEL_WIDTH, MainWindow
from labelwerk.settings import Settings, load_settings, save_settings


def _window(qtbot, settings=None):
    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
                     settings=settings or Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.resize(1600, 900)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_panels_sit_in_a_movable_dock(qtbot):
    win = _window(qtbot)
    dock = win.panel_dock
    assert isinstance(dock, QDockWidget) and dock.widget().objectName() == "panelScroll"
    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.LeftDockWidgetArea
    features = dock.features()
    assert features & QDockWidget.DockWidgetFeature.DockWidgetMovable
    assert features & QDockWidget.DockWidgetFeature.DockWidgetFloatable
    assert not features & QDockWidget.DockWidgetFeature.DockWidgetClosable   # never lost
    assert dock.allowedAreas() == (Qt.DockWidgetArea.LeftDockWidgetArea
                                   | Qt.DockWidgetArea.RightDockWidgetArea)


def test_dock_width_can_grow(qtbot):
    win = _window(qtbot)
    assert win.panels.minimumWidth() == PANEL_WIDTH
    assert win.panels.maximumWidth() > PANEL_WIDTH and win.panel_dock.maximumWidth() > PANEL_WIDTH
    win.resizeDocks([win.panel_dock], [PANEL_WIDTH + 200], Qt.Orientation.Horizontal)
    qtbot.wait(20)                                       # the dock layout applies the size later
    assert win.panel_dock.width() > PANEL_WIDTH + 100


def test_dock_place_and_width_are_remembered(qtbot):
    save_settings(Settings(check_media_on_start=False))
    win = _window(qtbot, load_settings())
    win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, win.panel_dock)
    win.resizeDocks([win.panel_dock], [PANEL_WIDTH + 120], Qt.Orientation.Horizontal)
    qtbot.wait(20)
    width = win.panel_dock.width()
    win.close()
    stored = load_settings()
    assert stored.window_state
    again = _window(qtbot, stored)
    qtbot.wait(20)
    assert again.dockWidgetArea(again.panel_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert abs(again.panel_dock.width() - width) <= 2


def test_broken_window_state_is_ignored_quietly(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"window_state": "not base64 !"}')
    settings = load_settings(path)
    assert settings.window_state == "" and not settings.warnings


def test_first_start_is_as_narrow_as_before(qtbot):
    win = _window(qtbot)
    qtbot.wait(20)
    assert win.panel_dock.widget().width() == win.panel_dock.widget().minimumWidth()


def test_settings_dialog_keeps_the_dock_state(qtbot, monkeypatch):
    """SAVE in the settings dialog must not forget where the side bar is (review 2026-10-20)."""
    from labelwerk.gui import main_window as mw
    save_settings(Settings(check_media_on_start=False))
    win = _window(qtbot, load_settings())
    win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, win.panel_dock)
    qtbot.wait(20)

    real = mw.SettingsDialog

    class Dialog:
        DialogCode = real.DialogCode

        def __init__(self, settings, **_kw):
            dialog = real(settings, model=win.model)
            qtbot.addWidget(dialog)
            self.saved = dialog.values()

        def exec(self):
            return self.DialogCode.Accepted

        def deleteLater(self):
            pass
    monkeypatch.setattr(mw, "SettingsDialog", Dialog)
    win.open_settings()
    assert load_settings().window_state == win.settings.window_state != ""
    win.close()
    again = _window(qtbot, load_settings())
    assert again.dockWidgetArea(again.panel_dock) == Qt.DockWidgetArea.RightDockWidgetArea


def test_toolbars_come_back_and_huge_widths_are_limited(qtbot):
    win = _window(qtbot)
    win.tool_bar.hide()
    win.resizeDocks([win.panel_dock], [1400], Qt.Orientation.Horizontal)
    qtbot.wait(20)
    win.close()
    from labelwerk.settings import Settings as S
    again = _window(qtbot, S(check_media_on_start=False, window_state=win.settings.window_state))
    qtbot.wait(20)
    assert again.tool_bar.isVisible() and again.app_bar.isVisible()
    assert again.panel_dock.width() <= again.width() // 2 + 2


# --- Dragging with visible feedback (Wayland: a floating window does not follow the mouse) -------
def _drag_title(qtbot, win, to_x):
    from PySide6.QtCore import QPoint
    title = win.panel_dock.titleBarWidget()
    start = QPoint(20, title.height() // 2)
    qtbot.mousePress(title, Qt.MouseButton.LeftButton, pos=start)
    target = title.mapFrom(win, QPoint(to_x, win.height() // 2))
    qtbot.mouseMove(title, title.mapFrom(win, QPoint(win.width() // 2, win.height() // 2)))
    qtbot.mouseMove(title, target)
    return title, target


def test_dragging_the_title_previews_and_docks_on_the_other_side(qtbot):
    win = _window(qtbot)
    title, target = _drag_title(qtbot, win, win.width() - 40)
    preview = win.panel_dock.preview
    assert preview.isVisible() and not win.panel_dock.isFloating()      # stays docked meanwhile
    assert preview.geometry().right() >= win.width() - 2                 # right edge shown
    qtbot.mouseRelease(title, Qt.MouseButton.LeftButton, pos=target)
    assert not preview.isVisible()
    assert win.dockWidgetArea(win.panel_dock) == Qt.DockWidgetArea.RightDockWidgetArea


def test_preview_follows_the_half_of_the_window(qtbot):
    win = _window(qtbot)
    title, target = _drag_title(qtbot, win, win.width() - 40)
    assert win.panel_dock.preview.geometry().right() >= win.width() - 2
    from PySide6.QtCore import QPoint
    qtbot.mouseMove(title, title.mapFrom(win, QPoint(40, win.height() // 2)))
    assert win.panel_dock.preview.geometry().left() <= 2                 # now on the left
    qtbot.mouseRelease(title, Qt.MouseButton.LeftButton,
                       pos=title.mapFrom(win, QPoint(40, win.height() // 2)))
    assert win.dockWidgetArea(win.panel_dock) == Qt.DockWidgetArea.LeftDockWidgetArea


def test_float_button_detaches_and_docks_again(qtbot):
    win = _window(qtbot)
    button = win.panel_dock.titleBarWidget().float_button
    button.click()
    assert win.panel_dock.isFloating()
    button.click()
    assert not win.panel_dock.isFloating()
