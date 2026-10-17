import pytest

from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import Canvas
from labelwerk.labels import get_label
from labelwerk.render import render_document


@pytest.fixture
def canvas(qtbot):
    view = Canvas()
    qtbot.addWidget(view)
    return view


def _show(canvas, label_id):
    doc = Document(label_id, objects=[TextObject("Test")])
    canvas.set_document(get_label(label_id), render_document(doc))


def test_die_cut_outline_has_physical_size(canvas):
    _show(canvas, "62x29")
    rect = canvas.outline.path().boundingRect()
    assert (rect.width(), rect.height()) == (732, 341)
    assert canvas.handle is None


def test_round_label_is_a_circle(canvas):
    from PySide6.QtCore import QPointF
    _show(canvas, "d24")
    path = canvas.outline.path()
    assert path.contains(QPointF(142, 142))           # Mitte
    assert not path.contains(QPointF(5, 5))           # Ecke liegt außerhalb


def test_endless_label_has_length_handle(canvas):
    _show(canvas, "62")
    assert canvas.handle is not None
    assert canvas.outline.path().boundingRect().width() == 732


def test_printable_area_is_centered(canvas):
    _show(canvas, "62x29")
    rect = canvas.printable.rect()
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (18, 35, 696, 271)


def test_zoom_is_clamped(canvas):
    canvas.set_zoom(1000)
    assert canvas.zoom == 400
    canvas.set_zoom(5)
    assert canvas.zoom == 25


def test_preview_grays_match_print_image():
    from PIL import Image
    from PySide6.QtGui import QImage, QPainter
    from labelwerk.gui.canvas import to_qimage

    img = Image.new("L", (256, 4))
    img.putdata([x for _ in range(4) for x in range(256)])
    qimg = to_qimage(img)
    base = QImage(256, 4, QImage.Format.Format_RGB32)
    base.fill(0xFFFFFFFF)
    painter = QPainter(base)
    painter.drawImage(0, 0, qimg)
    painter.end()
    for x in range(256):
        assert abs(base.pixelColor(x, 0).red() - x) <= 1
    assert qimg.pixelColor(255, 0).alpha() == 0


def test_length_handle_does_not_jump_when_grabbed(qtbot, canvas):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from labelwerk.gui.canvas import MM

    canvas.set_document(get_label("62"), render_document(Document("62", objects=[TextObject("Test")])))
    qtbot.addWidget(canvas)
    canvas.show()
    emitted = []
    canvas.length_changed.connect(emitted.append)
    start_mm = canvas.label_height() / MM

    def send(kind, scene_pt, button, buttons):
        local = QPointF(canvas.mapFromScene(scene_pt))
        ev = QMouseEvent(kind, local, canvas.viewport().mapToGlobal(local), button, buttons,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(canvas.viewport(), ev)

    center = canvas.handle.sceneBoundingRect().center()
    left = Qt.MouseButton.LeftButton
    send(QEvent.Type.MouseButtonPress, center, left, left)
    send(QEvent.Type.MouseMove, QPointF(center.x(), center.y() + 10 * MM),
         Qt.MouseButton.NoButton, left)
    send(QEvent.Type.MouseButtonRelease, QPointF(center.x(), center.y() + 10 * MM),
         left, Qt.MouseButton.NoButton)
    assert emitted
    # Schnittkante wandert um 10 mm (nicht zum Cursor, der ~2 mm tiefer liegt);
    # Toleranz = ein Rasterschritt, weil Mauskoordinaten ganze Pixel sind
    assert abs(emitted[-1] - (start_mm + 10)) <= 0.5
