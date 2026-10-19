"""Arbeitsfläche bei Etiketten anderer Auflösung: echte Größe, mm-Umrechnung, Schreibmarke."""
import pytest

from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import Canvas
from labelwerk.labels import get_label
from labelwerk.render import Renderer


def test_canvas_shows_a_203_dpi_label_in_real_size(qtbot):
    canvas = Canvas()
    qtbot.addWidget(canvas)
    doc = Document("57x32mm@203", objects=[TextObject("A", size_pt=14, x_mm=10, y_mm=5)])
    result = Renderer().render(doc)
    canvas.set_document(get_label(doc.label_id), result.size, result.objects)
    assert canvas.dpi == 203 and canvas.mm == pytest.approx(203 / 25.4)
    assert canvas.px_per_mm() == pytest.approx(canvas.zoom / 100 * canvas.logicalDpiX() / 25.4)
    assert canvas.objects[0].frame_mm().x == pytest.approx(10, abs=0.13)
    back = Renderer().render(Document("62x29", objects=[TextObject("A")]))
    canvas.set_document(get_label("62x29"), back.size, back.objects)
    assert canvas.dpi == 300
