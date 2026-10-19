"""Objekte einzeln rendern und zusammensetzen (Etappe 3d-1)."""
import pytest
from PIL import Image

import _render_before_3d as before
from labelwerk.document import ROTATIONS, Document, Paragraph, Span, TextObject
from labelwerk.labels import DPI, length_limits
from labelwerk.render import (RenderedObject, finish_object, label_margins, label_size,
                             prepare_object, render_document, render_object)


def _dots(mm):
    return round(mm * DPI / 25.4)


def _along(doc):
    """Rand in Bandlaufrichtung (der Vorschub des Druckers zählt mit)."""
    return label_margins(doc)[0 if doc.orientation == "horizontal" else 1]


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
    assert img.size == (306, _dots(50) - 2 * 35)        # Stück 50 mm, Vorschub an beiden Enden


def test_object_beyond_label_is_clipped():
    objs = [TextObject("Unten", size_pt=40, x_mm=-5, y_mm=25),
            TextObject("Rechts", size_pt=40, x_mm=55, y_mm=2)]
    img = render_document(Document("62", length_mm=30, objects=objs))
    assert img.size == (696, _dots(30) - 2 * 35)
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
    assert render_document(doc).height == ro.y + ro.h + _along(doc)


def test_auto_length_horizontal_uses_x():
    obj = TextObject("B", size_pt=20, x_mm=70, y_mm=5)
    doc = Document("62", orientation="horizontal", objects=[obj])
    ro = render_object(obj, doc)
    assert render_document(doc).height == ro.x + ro.w + _along(doc)


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


# --- Anschnitt: Tinte außerhalb der Tintenbox (Kantenglättung, Unterstreichung, „J“) ------
def _ink_cases():
    texts = {"Hallo unterstrichen": lambda: [Paragraph([Span("Hallo", underline=True)])],
             "Jahr": lambda: [Paragraph([Span("Jahr", bold=False)])],
             "Jahr fett": lambda: [Paragraph([Span("Jahr")])],
             "jung links": lambda: [Paragraph([Span("jung")], "left")]}
    for name, paras in texts.items():
        for orientation in ("vertical", "horizontal"):
            for size in (12, None):
                yield pytest.param(Document("62", orientation=orientation,
                                            objects=[TextObject(paras(), size_pt=size)]),
                                   id=f"{name}-{orientation}-{size or 'auto'}")


@pytest.mark.parametrize("doc", list(_ink_cases()))
def test_ink_beyond_box_is_pixel_identical_to_before(doc):
    new, old = render_document(doc), before.render_document(doc)
    assert new.size == old.size and new.tobytes() == old.tobytes()


def test_random_unpositioned_objects_are_pixel_identical_to_before():
    import random
    rng = random.Random(3)
    chars = "JjfgQyAa W_"
    mismatches = []
    for i in range(200):
        paras = []
        for _ in range(rng.randint(1, 2)):
            spans = [Span("".join(rng.choice(chars) for _ in range(rng.randint(1, 5))),
                          bold=rng.random() < 0.5, italic=rng.random() < 0.3,
                          underline=rng.random() < 0.4,
                          size_pt=rng.choice([None, None, 8, 20]))
                     for _ in range(rng.randint(1, 2))]
            paras.append(Paragraph(spans, rng.choice(["left", "center", "right", "justify"])))
        doc = Document(rng.choice(["62", "29", "12", "62x29"]),
                       orientation=rng.choice(["vertical", "horizontal"]),
                       objects=[TextObject(paras, size_pt=rng.choice([None, 10, 12, 24]))])
        try:
            old = before.render_document(doc)
        except ValueError:
            continue
        new = render_document(doc)
        if new.size != old.size or new.tobytes() != old.tobytes():
            mismatches.append((i, doc))
    assert mismatches == []


def test_object_image_covers_frame_and_ink():
    obj = TextObject([Paragraph([Span("Hallo", underline=True)])], size_pt=12, x_mm=5, y_mm=5)
    ro = render_object(obj, Document("62", length_mm=40, objects=[obj]))
    assert ro.image_dx <= 0 and ro.image_dy <= 0
    assert ro.image_dx + ro.image.width >= ro.w and ro.image_dy + ro.image.height >= ro.h


# --- Feste Rahmengröße auf Endlosband mit automatischer Länge ---------------------------
@pytest.mark.parametrize("orientation, frame", [("vertical", dict(w_mm=30)),
                                                ("horizontal", dict(h_mm=10)),
                                                ("vertical", {}), ("horizontal", {})])
def test_fit_without_feed_size_uses_text_extent_on_auto_length(orientation, frame):
    obj = TextObject("Hallo", fit=True, x_mm=2, y_mm=3, **frame)
    doc = Document("62", orientation=orientation, objects=[obj])
    ro = render_object(obj, doc)
    length = render_document(doc).height
    start, extent = (ro.y, ro.h) if orientation == "vertical" else (ro.x, ro.w)
    assert length == max(start + extent + _along(doc), length_limits("QL-600")[0])
    assert length < _dots(60)                       # nicht die Höchstlänge
    ink = _ink_box(ro.image)
    assert ink[3] - ink[1] > 0.8 * ro.h or ink[2] - ink[0] > 0.8 * ro.w   # Text füllt den Rahmen


def test_fit_with_given_across_size_fills_it_on_auto_length():
    narrow = render_object(TextObject("Hallo", fit=True, x_mm=2, y_mm=3, w_mm=20),
                           Document("62"))
    wide = render_object(TextObject("Hallo", fit=True, x_mm=2, y_mm=3, w_mm=40),
                         Document("62"))
    assert narrow.w == _dots(20) and wide.w == _dots(40)
    assert wide.base_pt > narrow.base_pt


# --- Gedrehtes Objekt ohne Position -------------------------------------------------
@pytest.mark.parametrize("rotation", [90, 270])
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_rotated_unpositioned_object_is_not_clipped(rotation, orientation):
    paras = [Paragraph([Span("kurz")], "left"), Paragraph([Span("viel längere Zeile")], "center")]
    obj = TextObject(paras, size_pt=12, rotation=rotation)
    doc = Document("62", orientation=orientation, objects=[obj])
    ro = render_object(obj, doc)
    width, height = _reading(render_document(doc), doc).size
    assert 0 <= ro.x and ro.x + ro.w <= width and 0 <= ro.y and ro.y + ro.h <= height
    left, top, right, bottom = _ink_box(ro.image)
    assert ro.x + ro.image_dx + left >= 0 and ro.y + ro.image_dy + top >= 0
    assert ro.x + ro.image_dx + right <= width and ro.y + ro.image_dy + bottom <= height
    unturned = render_object(TextObject(paras, size_pt=12), doc)
    assert ro.h == pytest.approx(unturned.w, abs=3) or ro.w == pytest.approx(unturned.h, abs=3)


def test_upside_down_unpositioned_left_text_starts_at_right_edge():
    obj = TextObject.plain("links", align="left", size_pt=12)
    obj.rotation = 180
    doc = Document("62", objects=[obj])
    upright = render_object(TextObject.plain("links", align="left", size_pt=12), doc)
    ro = render_object(obj, doc)
    width = render_document(doc).width
    assert (ro.w, ro.h) == (upright.w, upright.h)
    assert ro.x + ro.w == width - upright.x           # Textanfang am anderen Rand


@pytest.mark.parametrize("kw, frame", [(dict(y_mm=10), (0, 10)), (dict(x_mm=7), (7, 0))])
def test_one_coordinate_positions_object_other_is_zero(kw, frame):
    obj = TextObject("A", size_pt=20, **kw)
    assert obj.positioned
    ro = render_object(obj, Document("62", length_mm=40, objects=[obj]))
    assert (ro.x, ro.y) == (_dots(frame[0]), _dots(frame[1]))


# --- Leere Rahmen, schrittweises Rendern (Arbeitsfläche) ----------------------------
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
@pytest.mark.parametrize("text", ["", "   "])
def test_empty_positioned_object_does_not_lengthen_auto_label(orientation, text):
    doc = Document("62", orientation=orientation,
                   objects=[TextObject("Hallo", size_pt=14, x_mm=2, y_mm=2)])
    size = label_size(doc)
    doc.objects.append(TextObject.plain(text, size_pt=14))
    doc.objects[-1].x_mm, doc.objects[-1].y_mm = 80, 80
    assert label_size(doc) == size


_STEPWISE = [
    Document("62", objects=[TextObject("Mitte"), TextObject("Pos", size_pt=14, x_mm=3, y_mm=60),
                            TextObject("Rahmen", fit=True, x_mm=5, y_mm=5, w_mm=30, h_mm=8,
                                       rotation=90)]),
    Document("62", orientation="horizontal",
             objects=[TextObject.plain("links\nzwei", align="left"),
                      TextObject("weit", size_pt=20, x_mm=90, y_mm=3)]),
    Document("62x29", objects=[TextObject("Mitte", rotation=270), TextObject("")]),
    Document("62", objects=[]),
]


@pytest.mark.parametrize("doc", _STEPWISE)
def test_prepared_objects_give_same_size_and_images(doc):
    prepared = [prepare_object(obj, doc) for obj in doc.objects]
    size = label_size(doc, prepared=prepared)
    assert size == label_size(doc)
    for obj, prep in zip(doc.objects, prepared):
        a, b = finish_object(prep, doc, size), render_object(obj, doc)
        assert (a.x, a.y, a.w, a.h, a.base_pt, a.image_dx, a.image_dy) == \
               (b.x, b.y, b.w, b.h, b.base_pt, b.image_dx, b.image_dy)
        assert a.image.tobytes() == b.image.tobytes()
