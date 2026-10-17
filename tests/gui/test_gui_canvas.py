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
