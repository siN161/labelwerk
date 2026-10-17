import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

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
    panel.auto.setChecked(False)
    panel.size.setValue(300)
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
