"""Objekte einzeln rendern und zusammensetzen (Etappe 3d-1)."""
import pytest
from PIL import Image

import _render_before_3d as before
from labelwerk.document import ROTATIONS, Document, Paragraph, Span, TextObject
from labelwerk.labels import DPI
from labelwerk.render import RenderedObject, render_document, render_object


def _dots(mm):
    return round(mm * DPI / 25.4)


def _ink_box(img):
    """Tintenbox (Pixel dunkler als 50 %)."""
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


def _reading(img, doc):
    """Druckbild zurück in Leserichtung drehen."""
    return img.rotate(90, expand=True) if doc.orientation == "horizontal" else img


# --- Pixelgleichheit für ein Objekt ohne Position -------------------------------
_MIXED = TextObject([Paragraph([Span("klein", size_pt=10), Span("GROSS", size_pt=30)], "left"),
                     Paragraph([Span("rechts", italic=True, underline=True)], "right")],
                    size_pt=20)
_CASES = [
    Document("62", objects=[TextObject("Hallo")]),
    Document("62", objects=[TextObject("X1 -K3\nKlemme 24V")]),
    Document("62", objects=[TextObject("A\nB", size_pt=48)]),
    Document("62", objects=[TextObject.plain("Links\nmehr Text", align="left")]),
    Document("62", objects=[TextObject.plain("Rechts\nmehr Text", align="right", size_pt=20)]),
    Document("62", objects=[TextObject.plain("Block satz hier\nlange Zeile mit Worten",
                                             align="justify")]),
    Document("62", objects=[_MIXED]),
    Document("62", objects=[TextObject("Fest", size_pt=30, fit=True)]),
    Document("62", objects=[TextObject("")]),
    Document("62", objects=[]),
    Document("62", objects=[TextObject("Schräg")], margin_mm=5),
    Document("29", objects=[TextObject("Sehr langer Text der schrumpft")]),
    Document("62x29", objects=[TextObject.plain("Gestanzt", align="left")]),
    Document("62", objects=[TextObject("Quer")], orientation="horizontal"),
    Document("62", objects=[TextObject.plain("Längs links", align="left", size_pt=24)],
             orientation="horizontal", length_mm=100),
    Document("29", objects=[TextObject.plain("Rechts", align="right")], orientation="horizontal"),
    Document("62", objects=[TextObject("Feste Länge", size_pt=20)], length_mm=40),
    Document("12", objects=[TextObject.plain("Kursiv", italic=True)], orientation="horizontal"),
]


@pytest.mark.parametrize("doc", _CASES, ids=range(len(_CASES)))
def test_unpositioned_object_is_pixel_identical_to_before(doc):
    new = render_document(doc)
    old = before.render_document(doc)
    assert new.mode == old.mode and new.size == old.size
    assert new.tobytes() == old.tobytes()


# --- Modell -----------------------------------------------------------------
def test_text_object_defaults_are_unpositioned():
    obj = TextObject("A")
    assert (obj.x_mm, obj.y_mm, obj.w_mm, obj.h_mm, obj.rotation) == (None, None, None, None, 0)
    assert ROTATIONS == (0, 90, 180, 270)


def test_invalid_rotation_raises():
    with pytest.raises(ValueError, match="Drehung"):
        render_document(Document("62", objects=[TextObject("A", rotation=45)]))


# --- Position ---------------------------------------------------------------
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_positioned_ink_starts_at_position(orientation):
    obj = TextObject("H", size_pt=20, x_mm=10, y_mm=5)
    doc = Document("62", length_mm=60, orientation=orientation, objects=[obj])
    left, top, _, _ = _ink_box(_reading(render_document(doc), doc))
    # oben schließt die Tinte an den Rahmen an, links liegt nur die Vorbreite der Schrift davor
    bearing = _ink_box(render_object(obj, doc).image)[0]
    assert left == _dots(10) + bearing and bearing < 20 * 0.2 * 300 / 72
    assert abs(top - _dots(5)) <= 1


def test_render_object_reports_frame_on_label():
    obj = TextObject("H", size_pt=20, x_mm=10, y_mm=5)
    ro = render_object(obj, Document("62", length_mm=60, objects=[obj]))
    assert isinstance(ro, RenderedObject)
    assert (ro.x, ro.y) == (_dots(10), _dots(5))
    assert ro.image.mode == "L" and ro.image.size == (ro.w, ro.h)
    assert ro.base_pt == 20


def test_positioned_object_never_raises_text_too_large():
    obj = TextObject("W" * 60, size_pt=40, x_mm=0, y_mm=0)
    img = render_document(Document("29", length_mm=50, objects=[obj]))
    assert img.size == (306, _dots(50))


def test_object_beyond_label_is_clipped():
    objs = [TextObject("Unten", size_pt=40, x_mm=-5, y_mm=25),
            TextObject("Rechts", size_pt=40, x_mm=55, y_mm=2)]
    img = render_document(Document("62", length_mm=30, objects=objs))
    assert img.size == (696, _dots(30))
    assert _ink_box(img) is not None


# --- Drehen -----------------------------------------------------------------
@pytest.mark.parametrize("rotation, transpose", [(90, Image.Transpose.ROTATE_270),
                                                 (180, Image.Transpose.ROTATE_180),
                                                 (270, Image.Transpose.ROTATE_90)])
def test_rotation_turns_object_image_clockwise(rotation, transpose):
    doc = Document("62", length_mm=60)
    upright = render_object(TextObject("Ab", size_pt=30, x_mm=5, y_mm=5), doc)
    turned = render_object(TextObject("Ab", size_pt=30, x_mm=5, y_mm=5, rotation=rotation), doc)
    if rotation == 180:
        assert (turned.w, turned.h) == (upright.w, upright.h)
    else:
        assert (turned.w, turned.h) == (upright.h, upright.w)
    assert (turned.x, turned.y) == (upright.x, upright.y)
    assert turned.image.tobytes() == upright.image.transpose(transpose).tobytes()


def test_rotated_object_is_placed_on_label():
    obj = TextObject("Ab", size_pt=30, x_mm=5, y_mm=5, rotation=90)
    doc = Document("62", length_mm=60, objects=[obj])
    ro = render_object(obj, doc)
    left, top, right, bottom = _ink_box(render_document(doc))
    assert abs(left - ro.x) <= 1 and abs(top - ro.y) <= 1
    assert bottom - top > right - left              # hochkant


# --- Zusammensetzen -----------------------------------------------------------
def test_later_object_does_not_erase_earlier_ink():
    first = TextObject("H", size_pt=60, x_mm=5, y_mm=5)
    second = TextObject("H", size_pt=60, x_mm=7, y_mm=6)   # Rahmen überdeckt das erste „H“
    doc = Document("62", length_mm=40, objects=[first, second])
    a = render_object(first, doc)
    b = render_object(second, doc)
    assert b.x < a.x + a.w and b.y < a.y + a.h
    alone = render_document(Document("62", length_mm=40, objects=[first])).convert("L")
    both = render_document(doc).convert("L")
    ink = [(x, y) for y in range(alone.height) for x in range(alone.width)
           if alone.getpixel((x, y)) < 128]
    assert ink and all(both.getpixel(p) < 128 for p in ink)


def test_auto_length_grows_with_farthest_object():
    near = TextObject("A", size_pt=20, x_mm=5, y_mm=5)
    far = TextObject("B", size_pt=20, x_mm=5, y_mm=60)
    doc = Document("62", objects=[near, far])
    ro = render_object(far, doc)
    assert render_document(doc).height == ro.y + ro.h + _dots(doc.margin_mm)


def test_auto_length_horizontal_uses_x():
    obj = TextObject("B", size_pt=20, x_mm=70, y_mm=5)
    doc = Document("62", orientation="horizontal", objects=[obj])
    ro = render_object(obj, doc)
    assert render_document(doc).height == ro.x + ro.w + _dots(doc.margin_mm)


def test_auto_length_keeps_room_for_unpositioned_object():
    centered = TextObject("Mitte\nzwei\ndrei", size_pt=40)
    near = TextObject("A", size_pt=10, x_mm=1, y_mm=1)
    alone = render_document(Document("62", objects=[centered]))
    assert render_document(Document("62", objects=[centered, near])).height == alone.height


# --- Feste Rahmengröße -----------------------------------------------------------
def test_fit_into_frame():
    obj = TextObject("Hallo Welt", size_pt=12, fit=True, x_mm=2, y_mm=3, w_mm=30, h_mm=8)
    doc = Document("62", length_mm=40, objects=[obj])
    ro = render_object(obj, doc)
    assert (ro.x, ro.y, ro.w, ro.h) == (_dots(2), _dots(3), _dots(30), _dots(8))
    left, top, right, bottom = _ink_box(ro.image)
    assert left >= 0 and top >= 0 and right <= ro.w and bottom <= ro.h
    assert right - left > ro.w * 0.8 or bottom - top > ro.h * 0.8    # füllt den Rahmen
    bigger = render_object(TextObject("Hallo Welt", size_pt=12, fit=True, x_mm=2, y_mm=3,
                                      w_mm=60, h_mm=16), doc)
    assert bigger.base_pt > ro.base_pt


# --- Grundgröße ---------------------------------------------------------------
def test_base_pt_of_auto_object_reproduces_image():
    doc = Document("62", objects=[TextObject("Hallo")])
    ro = render_object(doc.objects[0], doc)
    assert 4 < ro.base_pt < 100
    fixed = Document("62", objects=[TextObject("Hallo", size_pt=ro.base_pt)])
    assert render_document(fixed).tobytes() == render_document(doc).tobytes()


# --- Zusammensetzen aus Objektbildern (Arbeitsfläche = Druck) -------------------------
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_compose_from_object_images_equals_render_document(orientation):
    from labelwerk.render import compose, label_size
    doc = Document("62", orientation=orientation, objects=[
        TextObject("Mitte"), TextObject("oben", size_pt=14, x_mm=3, y_mm=2)])
    rendered = [render_object(obj, doc) for obj in doc.objects]
    image = compose(rendered, label_size(doc), orientation)
    assert image.tobytes() == render_document(doc).tobytes()
