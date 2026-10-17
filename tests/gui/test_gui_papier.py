import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM, Canvas
from labelwerk.gui.main_window import MainWindow
from labelwerk.labels import get_label
from labelwerk.render import render_document
from labelwerk.settings import Settings


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    win.panel("text").edit.setPlainText("Max Mustermann")
    win.render_now()
    return win


def test_orientation_switch_changes_document_and_preview(window):
    paper = window.panel("paper")
    assert paper.vertical.isChecked()
    paper.horizontal.setChecked(True)
    window.render_now()
    assert window.doc.orientation == "horizontal"
    assert window.image.tobytes() == render_document(window.doc).tobytes()


def test_margin_changes_document_and_length(window):
    paper = window.panel("paper")
    paper.horizontal.setChecked(True)
    window.render_now()
    before = window.image.height
    paper.margin.setValue(5.0)
    window.render_now()
    assert window.doc.margin_mm == 5.0
    assert window.image.height == before + 2 * (59 - 12)


def test_horizontal_view_shows_handle_right_of_label(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    label_box = canvas.label_view_rect()
    handle = canvas.mapFromScene(canvas.handle.sceneBoundingRect().center())
    assert handle.x() > label_box.right()
    assert label_box.width() > label_box.height()          # Adresse liegt quer im Bild


def test_horizontal_caption_reads_length_first(qtbot):
    view = Canvas()
    qtbot.addWidget(view)
    doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("A")])
    view.set_document(get_label("62"), render_document(doc), "horizontal")
    assert view._caption == "50,0 × 62 mm"


def _mouse(view, kind, scene_point, buttons):
    pos = QPointF(view.mapFromScene(scene_point))
    event = QMouseEvent(kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                        Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
                        else Qt.MouseButton.NoButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), event)


def test_dragging_in_horizontal_view_sets_length(window):
    window.panel("paper").horizontal.setChecked(True)
    window.render_now()
    canvas = window.canvas
    start = canvas.handle.sceneBoundingRect().center()
    end = QPointF(start.x(), start.y() + 80.1 * MM - canvas.label_height())
    _mouse(canvas, QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton)
    _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert window.doc.length_mm == 80.0


def test_window_starts_with_settings(qtbot):
    settings = Settings(label_id="62x29", orientation="horizontal", margin_mm=3, font_size_pt=19,
                        start_zoom=150)
    win = MainWindow(settings=settings)
    qtbot.addWidget(win)
    assert (win.doc.label_id, win.doc.orientation, win.doc.margin_mm) == ("62x29", "horizontal", 3)
    assert win.panel("paper").horizontal.isChecked()
    assert win.panel("paper").margin.value() == 3.0
    assert not win.panel("text").fit.isChecked() and win.panel("text").size.currentText() == "19"
    assert win.canvas.zoom == 150


def test_settings_warnings_appear_in_status_bar(qtbot):
    win = MainWindow(settings=Settings(warnings=["Einstellung 'start_zoom' ungültig"]))
    qtbot.addWidget(win)
    assert "start_zoom" in win.result.text()
