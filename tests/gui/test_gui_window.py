import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from labelwerk.gui.app import load_theme
from labelwerk.gui.canvas import MM
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.tools import TOOLS


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    return win


def test_theme_is_packaged():
    assert "QToolBar" in load_theme()


def test_registry_creates_button_and_panel_per_tool(window):
    assert list(window.tool_actions) == [tool.key for tool in TOOLS]
    assert window.panels.count() == len(TOOLS)
    window.tool_actions["text"].trigger()
    assert window.panels.currentWidget() is window.panel("text")


def test_typing_updates_preview(window, qtbot):
    before = window.image.tobytes()
    window.panel("text").edit.setPlainText("Hallo")
    qtbot.waitUntil(lambda: window.image.tobytes() != before, timeout=1000)


def test_too_large_font_shows_hint_in_text_panel(window):
    panel = window.panel("text")
    panel.edit.setPlainText("Sehr langer Text")
    panel.fit.setChecked(False)
    panel.set_size_pt(72)
    window.render_now()
    assert not panel.error.isHidden()
    assert "höchstens" in panel.error.text()


def test_changing_label_changes_preview_size(window):
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    window.render_now()
    assert window.image.size == (696, 271)


def test_paper_panel_shows_length_only_for_endless(window):
    paper = window.panel("paper")
    assert not paper.length_box.isHidden() and paper.fixed_size.isHidden()
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert paper.length_box.isHidden()
    assert paper.fixed_size.text() == "62 × 29 mm · gestanzt"


def test_fixed_length_sets_preview_height(window):
    paper = window.panel("paper")
    paper.length_auto.setChecked(False)
    paper.length.setValue(50.0)
    window.render_now()
    assert window.image.height == round(50 * MM)


def _mouse(view, kind, scene_point, buttons):
    pos = QPointF(view.mapFromScene(scene_point))
    event = QMouseEvent(kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                        Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
                        else Qt.MouseButton.NoButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def _drag_handle(window, to_y):
    """Untere Schnittkante am Anfasser auf Szene-y to_y ziehen (Greifversatz bleibt erhalten)."""
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    end = QPointF(start.x(), start.y() + to_y - canvas.label_height())
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


def test_dragging_handle_sets_fixed_length(window):
    _drag_handle(window, 40.1 * MM)   # ±1 Pixel Rundung bleibt im 0,5-mm-Raster
    assert window.doc.length_mm == 40.0                   # Raster 0,5 mm
    paper = window.panel("paper")
    assert not paper.length_auto.isChecked()
    assert paper.length.value() == 40.0


def test_dragging_below_minimum_stops_at_12_7_mm(window):
    _drag_handle(window, 2 * MM)
    assert window.doc.length_mm == pytest.approx(12.7, abs=0.01)


def test_double_click_on_handle_resets_to_automatic(window):
    _drag_handle(window, 40 * MM)
    window.render_now()
    center = window.canvas.handle.sceneBoundingRect().center()
    _mouse(window.canvas, QMouseEvent.Type.MouseButtonDblClick, center, Qt.MouseButton.LeftButton)
    assert window.doc.length_mm is None
    assert window.panel("paper").length_auto.isChecked()


def test_print_success_shows_status_and_reenables_button(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")
    sent = {}

    def fake_print(image, label_id, **kw):
        sent["size"] = image.size
        return {"outcome": "printed", "did_print": True}

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fake_print)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.text() == "Gedruckt ✓"
    assert sent["size"][0] == 696


def test_print_error_is_shown(window, qtbot, monkeypatch):
    from labelwerk.printer import PrintError

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")

    def fail(*a, **kw):
        raise PrintError("Eingelegte Rolle passt nicht zum Etikett '62'")

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fail)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "Rolle passt nicht" in window.result.text()


def test_no_printer_message(window, qtbot):
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "nicht gefunden" in window.result.text()


def test_empty_label_asks_and_cancel_does_not_print(window, monkeypatch):
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **kw: asked.append(a) or QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    window.print_label()
    assert asked
    assert window.print_action.isEnabled()
    assert window.result.text() == ""


def test_detection_error_does_not_hang_button(window, qtbot, monkeypatch):
    def broken():
        raise OSError("kaputt")

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", broken)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "kaputt" in window.result.text()


def test_new_print_resets_result_state(window, qtbot, monkeypatch):
    from labelwerk.printer import PrintError

    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")

    def fail(*a, **kw):
        raise PrintError("kaputt")

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fail)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.property("state") == "error"

    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"outcome": "printed", "did_print": True})
    window.print_label()
    assert window.result.property("state") == ""
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert window.result.property("state") == "ok"


def _press_move(window, dy_mm, kind=QMouseEvent.Type.MouseMove, start=None):
    canvas = window.canvas
    point = QPointF(start.x(), start.y() + dy_mm * MM)
    _mouse(canvas, kind, point, Qt.MouseButton.LeftButton)


def test_drag_without_motion_does_not_drift_and_renders_only_on_release(window, qtbot):
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    height_before = canvas.label_height()
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _press_move(window, 10, start=start)
    first = window.doc.length_mm
    qtbot.wait(300)   # früher: Render mitten im Ziehen verschob das Etikett unter dem Cursor
    assert canvas.label_height() == height_before
    _press_move(window, 10, start=start)
    assert window.doc.length_mm == first
    end = QPointF(start.x(), start.y() + 10 * MM)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert not canvas.is_dragging()
    assert window.image.height == round(first * MM)
    assert canvas.label_height() == pytest.approx(round(first * MM))


def test_render_error_blocks_print_and_shows_in_status(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    panel = window.panel("text")
    panel.edit.setPlainText("Sehr langer Text")
    panel.fit.setChecked(False)
    panel.set_size_pt(72)
    window.print_label()
    assert "höchstens" in window.result.text()
    assert window.result.property("state") == "error"
    assert window.print_action.isEnabled()
    panel.fit.setChecked(True)
    window.render_now()
    assert panel.error.isHidden()
    assert window.result.text() == ""


def test_render_success_keeps_print_result(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp",
                        lambda: "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"outcome": "printed", "did_print": True})
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    window.render_now()
    assert window.result.text() == "Gedruckt ✓"


def test_printer_detection_error_at_startup(qtbot, monkeypatch):
    def broken():
        raise OSError("kaputt")

    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", broken)
    win = MainWindow()
    qtbot.addWidget(win)
    assert "unbekannt" in win.printer_status.text()


def test_busy_printer_message(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.brother_busy", lambda: True)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "belegt" in window.result.text()


def test_app_identity_sets_icon_and_desktop_name(qapp):
    from labelwerk.gui.app import apply_identity
    apply_identity(qapp)
    assert qapp.desktopFileName() == "labelwerk"
    assert not qapp.windowIcon().isNull()


def test_window_title_and_app_name_use_app_name(window, qapp):
    from labelwerk.desktop import APP_NAME
    from labelwerk.gui.app import apply_identity
    apply_identity(qapp)
    assert window.windowTitle() == APP_NAME
    assert qapp.applicationName() == APP_NAME


def test_theme_arrows_resolve_to_existing_files():
    import re
    from pathlib import Path
    theme = load_theme()
    assert "@THEME@" not in theme
    urls = [u.strip('"') for u in re.findall(r"url\(([^)]+)\)", theme)]
    assert urls and all(Path(u).exists() for u in urls)


def test_number_fields_keep_text_clear_of_frame(window, qtbot):
    from PySide6.QtWidgets import QAbstractSpinBox
    from labelwerk.gui.settings_dialog import SettingsDialog
    from labelwerk.settings import Settings
    dialog = SettingsDialog(Settings())
    qtbot.addWidget(dialog)          # sonst lebt der Dialog bis nach dem Ende der QApplication
    spins = window.findChildren(QAbstractSpinBox) + dialog.findChildren(QAbstractSpinBox)
    assert len(spins) >= 5
    assert all(s.lineEdit().textMargins().left() >= 8 for s in spins)


def test_theme_urls_are_quoted():
    import re
    assert all(u.startswith('"') for u in re.findall(r"url\(([^)]+)\)", load_theme()))


def test_toolbar_buttons_have_equal_space_above_and_below(qtbot, qapp):
    """Abstand Knopf ↔ Leistenrand oben gleich unten (gemessen an dunklen Pixelzeilen)."""
    from PySide6.QtWidgets import QToolBar
    from labelwerk.settings import Settings
    qapp.setStyleSheet(load_theme())
    try:
        win = MainWindow(settings=Settings(check_media_on_start=False))
        qtbot.addWidget(win)
        win.show()
        toolbar = win.findChild(QToolBar)
        img = toolbar.grab().toImage()
        x = toolbar.widgetForAction(win.tool_actions["text"]).geometry().center().x()
        dark = [y for y in range(img.height()) if img.pixelColor(x, y).lightness() < 80]
        bands, current = [], [dark[0]]
        for y in dark[1:]:
            if y == current[-1] + 1:
                current.append(y)
            else:
                bands.append(current)
                current = [y]
        bands.append(current)
        top_gap = bands[0][0]
        bottom_gap = bands[-1][0] - bands[-2][-1] - 1
        assert top_gap == bottom_gap
    finally:
        qapp.setStyleSheet("")


def test_unloadable_font_shows_error_in_panel_and_status(window, monkeypatch):
    from PIL import ImageFont

    from labelwerk import fonts

    def broken(path, size):
        raise OSError("invalid pixel size")
    monkeypatch.setattr(ImageFont, "truetype", broken)
    fonts.load.cache_clear()
    try:
        window.panel("text").edit.setPlainText("Hallo")
        window.render_now()
        assert "kann nicht geladen werden" in window.panel("text").error.text()
        assert "kann nicht geladen werden" in window.result.text()
    finally:
        monkeypatch.undo()
        fonts.load.cache_clear()


def test_font_replacement_hint_in_status_bar(window):
    from labelwerk.document import Paragraph, Span, TextObject
    window.doc.objects[0] = TextObject([Paragraph([Span("Hallo", family="GibtsGarNicht 4711")])])
    window.render_now()
    assert "GibtsGarNicht 4711" in window.result.text()
    assert window.result.property("state") == "error"
    window.doc.objects[0] = TextObject([Paragraph([Span("Hallo")])])
    window.render_now()
    assert window.result.text() == ""


def test_global_actions_come_from_shortcut_registry(window, monkeypatch):
    """Drucken, Einstellungen und Zoom sind Aktionen des Kürzel-Verzeichnisses."""
    from PySide6.QtGui import QKeySequence
    assert window.print_action is window.actions["file.print"]
    assert window.settings_action is window.actions["app.settings"]
    assert window.print_action.shortcut() == QKeySequence("Ctrl+P")
    assert "Ctrl+P" in window.print_action.toolTip()
    asked = []                                              # leeres Etikett: Rückfrage = Druck läuft
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **kw: asked.append(a) or QMessageBox.StandardButton.Cancel)
    window.panel("text").edit.setPlainText("")
    window.actions["file.print"].trigger()
    assert asked
    window.canvas.set_zoom(100)
    window.actions["view.zoom_in"].trigger()
    assert window.canvas.zoom == 110
    window.actions["view.zoom_out"].trigger()
    window.actions["view.zoom_out"].trigger()
    assert window.canvas.zoom == 90
    window.actions["view.zoom_reset"].trigger()
    assert window.canvas.zoom == 100
    from PySide6.QtWidgets import QWidget
    window_actions = QWidget.actions(window)                # self.actions ist das Verzeichnis
    assert all(window.actions[key] in window_actions
               for key in ("view.zoom_in", "view.zoom_out", "view.zoom_reset", "edit.undo"))


# --- Rückfrage: Objekt ragt über das Etikett --------------------------------------
def _outside_window(qtbot):
    from labelwerk.document import Document, TextObject
    from labelwerk.settings import Settings
    doc = Document("62", length_mm=30, objects=[TextObject("Rand", size_pt=20, x_mm=55, y_mm=5)])
    win = MainWindow(doc=doc, settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    return win


def test_print_with_outside_object_asks_and_no_does_not_print(qtbot, monkeypatch):
    win = _outside_window(qtbot)
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **kw: asked.append(a) or QMessageBox.StandardButton.No)
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    win.print_label()
    (_, title, text, buttons, default), = asked
    assert text == "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
    assert buttons == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    assert default == QMessageBox.StandardButton.No
    assert not win.is_printing() and win.print_action.isEnabled()


def test_print_with_outside_object_yes_prints(qtbot, monkeypatch):
    win = _outside_window(qtbot)
    monkeypatch.setattr(MainWindow, "confirm_outside", lambda self: True)
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", lambda: "file:///dev/usb/lp0")
    sent = []
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: sent.append(a) or {"did_print": True})
    win.print_label()
    qtbot.waitUntil(lambda: win.print_action.isEnabled(), timeout=3000)
    assert sent and win.result.text() == "Gedruckt ✓"


def test_print_inside_label_does_not_ask(window, qtbot, monkeypatch):
    monkeypatch.setattr(MainWindow, "confirm_outside", lambda self: pytest.fail("keine Rückfrage"))
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"did_print": True})
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
