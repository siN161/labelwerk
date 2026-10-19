"""Barcodes als Objekte: Platzieren (Anfasser, Felder, Ausrichten, Maximieren, Drehen), Einfügen,
Platzhalter der Serie, Speichern."""
import json
from dataclasses import replace

import pytest

from labelwerk import barcodes, layout, storage
from labelwerk.document import BarcodeObject, Document, TextObject
from labelwerk.layout import Rect, exact_rect, object_rect
from labelwerk.render import render_object
from labelwerk.series import fill, missing, placeholders
from labelwerk.storage import StorageError

MM = 25.4 / 300          # mm je Druckpunkt


def _bar(**kw) -> BarcodeObject:
    kw.setdefault("x_mm", 5.0)
    kw.setdefault("y_mm", 3.0)
    return BarcodeObject(**kw)


def _rendered(obj, label="62x29"):
    return render_object(obj, Document(label, objects=[obj]))


def _width(obj) -> float:
    """Breite ungedreht in mm aus Modulen × Modulbreite."""
    return barcodes.modules(obj) * obj.module * MM


# --- Rahmen im Modell -----------------------------------------------------------------------------
def test_exact_rect_takes_the_height_from_the_model():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=9.95)
    rect = exact_rect(obj, _rendered(obj))
    assert rect == Rect(5.0, 3.0, pytest.approx(_width(obj)), 9.95)
    turned = _bar(kind="code128", data="AB", module=3, h_mm=9.95, rotation=90)
    assert exact_rect(turned, _rendered(turned)) == Rect(5.0, 3.0, 9.95,
                                                         pytest.approx(_width(turned)))


def test_barcode_rect_matches_the_rendered_frame():
    for obj in (_bar(kind="qr", data="labelwerk", module=4),
                _bar(kind="ean13", data="590123412345", module=2, rotation=270)):
        rect, shown = layout.barcode_rect(obj), object_rect(_rendered(obj))
        assert (rect.w, rect.h) == (pytest.approx(shown.w, abs=0.05),
                                    pytest.approx(shown.h, abs=0.05))
    assert layout.barcode_rect(_bar(kind="ean8", data="12")) is None


# --- Anfasser ----------------------------------------------------------------------------------
def _drag(obj, handle, dx=0.0, dy=0.0):
    r = _rendered(obj)
    old = object_rect(r)
    x, y, w, h = old.x, old.y, old.w, old.h
    if "l" in handle:
        x, w = x + dx, w - dx
    if "r" in handle:
        w += dx
    if "t" in handle:
        y, h = y + dy, h - dy
    if "b" in handle:
        h += dy
    return layout.resize(obj, Rect(x, y, w, h), r, handle)


def test_right_handle_snaps_to_whole_dots_per_module():
    obj = _bar(kind="code128", data="AB", module=3)
    count = barcodes.modules(obj)
    wider = _drag(obj, "r", dx=0.6 * count * MM)        # 3,6 Punkte je Modul → 4
    assert (wider.module, wider.x_mm, wider.y_mm, wider.h_mm) == (4, 5.0, 3.0, 10.0)
    assert _drag(obj, "r", dx=0.4 * count * MM).module == 3
    assert _drag(obj, "r", dx=-1.6 * count * MM).module == 1


def test_left_handle_keeps_the_right_edge():
    obj = _bar(kind="code128", data="AB", module=3)
    right = 5.0 + _width(obj)
    narrower = _drag(obj, "l", dx=0.8 * barcodes.modules(obj) * MM)   # 2,2 → 2 Punkte je Modul
    assert narrower.module == 2
    assert narrower.x_mm + _width(narrower) == pytest.approx(right, abs=1e-3)


def test_bottom_handle_changes_only_the_height():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=10)
    taller = _drag(obj, "b", dy=2.5)
    assert (taller.module, taller.h_mm, taller.y_mm) == (3, pytest.approx(12.5, abs=0.01), 3.0)
    top = _drag(obj, "t", dy=-1.0)
    assert top.h_mm == pytest.approx(11.0, abs=0.01)
    assert top.y_mm + top.h_mm == pytest.approx(13.0, abs=1e-3)


def test_corner_of_a_bar_code_changes_module_and_height():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=10)
    both = _drag(obj, "br", dx=1.0 * barcodes.modules(obj) * MM, dy=-3)
    assert (both.module, both.h_mm) == (4, pytest.approx(7.0, abs=0.01))


def test_turned_bar_code_right_handle_changes_the_height():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=10, rotation=90)
    wider = _drag(obj, "r", dx=2)
    assert (wider.module, wider.h_mm) == (3, pytest.approx(12.0, abs=0.01))
    longer = _drag(obj, "b", dy=1.0 * barcodes.modules(obj) * MM)
    assert (longer.module, longer.h_mm) == (4, 10.0)


def test_qr_corner_keeps_the_square_and_the_opposite_corner():
    obj = _bar(kind="qr", data="labelwerk", module=4)        # 21 Module
    bigger = _drag(obj, "br", dx=21 * 2 * MM, dy=21 * 0.5 * MM)
    assert (bigger.module, bigger.x_mm, bigger.y_mm) == (6, 5.0, 3.0)
    smaller = _drag(obj, "tl", dx=21 * 0.8 * MM, dy=21 * 0.7 * MM)    # 3,2 → 3
    side = 21 * 3 * MM
    assert smaller.module == 3
    assert smaller.x_mm + side == pytest.approx(5.0 + 21 * 4 * MM, abs=1e-3)
    assert smaller.y_mm + side == pytest.approx(3.0 + 21 * 4 * MM, abs=1e-3)


def test_qr_edge_keeps_the_middle_across():
    obj = _bar(kind="qr", data="labelwerk", module=4)
    middle = 3.0 + 21 * 4 * MM / 2
    wider = _drag(obj, "r", dx=21 * 2 * MM)
    assert wider.module == 6 and wider.x_mm == 5.0
    assert wider.y_mm + 21 * 6 * MM / 2 == pytest.approx(middle, abs=1e-3)


def test_module_and_height_stay_in_their_limits():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=10)
    assert _drag(obj, "r", dx=30 * barcodes.modules(obj) * MM).module == 20
    assert _drag(obj, "b", dy=-9.5).h_mm == 2.0
    assert _drag(obj, "b", dy=200).h_mm == 100.0


# --- Felder, Ausrichten, Angleichen, Maximieren, Drehen -------------------------------------------
def test_size_fields_set_module_and_height():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=10)
    r = _rendered(obj)
    exact = exact_rect(obj, r)
    wide = layout.set_frame(obj, Rect(exact.x, exact.y, exact.w * 5 / 3, exact.h), r)
    assert (wide.module, wide.h_mm) == (5, 10.0)
    low = layout.set_frame(obj, Rect(exact.x, exact.y, exact.w, 6.5), r)
    assert (low.module, low.h_mm) == (3, 6.5)
    moved = layout.set_frame(obj, Rect(1, 2, exact.w, exact.h), r)
    assert (moved.x_mm, moved.y_mm, moved.module, moved.h_mm) == (1, 2, 3, 10.0)


def test_qr_height_field_changes_the_module():
    obj = _bar(kind="qr", data="labelwerk", module=4)
    r = _rendered(obj)
    exact = exact_rect(obj, r)
    assert layout.set_frame(obj, Rect(exact.x, exact.y, exact.w, 21 * 8 * MM), r).module == 8
    assert layout.set_frame(obj, Rect(exact.x, exact.y, 21 * 2 * MM, exact.h), r).module == 2


def test_align_keeps_the_size():
    objs = [_bar(kind="code128", data="AB", module=3, x_mm=4),
            _bar(kind="qr", data="x", module=5, x_mm=20, y_mm=9)]
    rendered = [_rendered(o) for o in objs]
    left = layout.align_objects(objs, rendered, "left")
    assert [o.x_mm for o in left] == [4, 4]
    assert [(o.module, o.h_mm) for o in left] == [(3, 10.0), (5, 10.0)]


def test_match_width_and_height():
    ref = _bar(kind="code128", data="AB", module=4, h_mm=12)
    other = _bar(kind="code128", data="AB", module=2, h_mm=8)
    rendered = [_rendered(ref), _rendered(other)]
    width = layout.match_objects([ref, other], rendered, "width")[1]
    assert (width.module, width.h_mm) == (4, 8.0)
    height = layout.match_objects([ref, other], rendered, "height")[1]
    assert (height.module, height.h_mm) == (2, 12.0)
    qr = _bar(kind="qr", data="labelwerk", module=2)
    square = layout.match_objects([_bar(kind="qr", data="labelwerk", module=6), qr],
                                  [_rendered(_bar(kind="qr", data="labelwerk", module=6)),
                                   _rendered(qr)], "height")[1]
    assert square.module == 6


def test_maximize_takes_the_largest_module_that_fits():
    doc = Document("62x29")
    area = layout.printable_area(doc)
    obj = _bar(kind="qr", data="labelwerk", module=2)
    big = layout.maximize_object(obj, _rendered(obj), area, doc)
    side = 21 * big.module * MM
    assert side <= min(area.w, area.h) + 1e-6 and 21 * (big.module + 1) * MM > area.h
    assert big.x_mm + side / 2 == pytest.approx(area.cx, abs=1e-3)
    assert big.y_mm + side / 2 == pytest.approx(area.cy, abs=1e-3)
    bar = _bar(kind="code128", data="AB", module=1, h_mm=5)
    wide = layout.maximize_object(bar, _rendered(bar), area, doc)
    assert _width(wide) <= area.w + 1e-6 and wide.h_mm <= area.h + 1e-6
    assert wide.module > 1


def test_rotate_keeps_module_and_middle():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=10)
    r = _rendered(obj)
    old = exact_rect(obj, r)
    turned = layout.rotate(obj, r, 90)
    assert (turned.rotation, turned.module, turned.h_mm) == (90, 3, 10.0)
    new = layout.barcode_rect(turned)
    assert (new.cx, new.cy) == (pytest.approx(old.cx, abs=1e-3), pytest.approx(old.cy, abs=1e-3))


def test_move_and_grid():
    obj = _bar(kind="code128", data="AB", module=3, h_mm=10.04)
    r = _rendered(obj)
    moved = layout.move(obj, object_rect(r).at(10, 7), r)
    assert (moved.x_mm, moved.y_mm) == (pytest.approx(10 + 5.0 - object_rect(r).x, abs=1e-3),
                                        pytest.approx(7 + 3.0 - object_rect(r).y, abs=1e-3))
    grid = layout.to_grid(obj, x=True, y=True, w=True, h=True)
    assert (grid.h_mm, grid.module) == (10.0, 3)


def test_text_functions_reject_barcodes():
    with pytest.raises(TypeError):
        layout.scale_text(_bar(kind="qr", data="x"), 2)


def test_invalid_content_keeps_the_module():
    obj = _bar(kind="ean13", data="12", module=3, h_mm=10)
    placed = layout.place(obj, Rect(1, 1, 40, 12))
    assert (placed.module, placed.h_mm, placed.x_mm) == (3, 12, 1)


# --- Einfügen ----------------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["qr", "code128", "code39", "ean13", "ean8"])
def test_new_barcode_lies_in_the_middle_with_sample_content(kind):
    doc = Document("62x29")
    area = layout.printable_area(doc)
    obj = layout.new_barcode(doc, "QL-600", area, kind)
    assert obj.data == barcodes.SAMPLES[kind] and obj.rotation == 0
    rect = layout.barcode_rect(obj)
    assert (rect.cx, rect.cy) == (pytest.approx(area.cx, abs=1e-3), pytest.approx(area.cy, abs=1e-3))
    assert obj.module == (6 if kind == "qr" else 3)


def test_new_barcode_shrinks_on_a_small_label():
    doc = Document("23x23")
    area = layout.printable_area(doc)
    obj = layout.new_barcode(doc, "QL-600", area, "code128")
    rect = layout.barcode_rect(obj)
    assert obj.module < 3
    assert rect.x >= area.x - 1e-6 and rect.right <= area.right + 1e-6
    assert rect.y >= area.y - 1e-6 and rect.bottom <= area.bottom + 1e-6


def test_new_barcode_turns_rather_than_shrinks():
    doc = Document("12")                 # quer 9 mm bedruckbar, Endlosband wächst längs
    area = layout.printable_area(doc)
    obj = layout.new_barcode(doc, "QL-600", area, "code128")
    assert (obj.rotation, obj.module) == (90, 3)
    assert obj.h_mm <= area.w + 1e-6                     # gedreht: Höhe liegt quer
    render_object(obj, Document("12", objects=[obj]))


@pytest.mark.parametrize("label", ["12", "d12", "23x23", "29", "62x29"])
@pytest.mark.parametrize("kind", ["qr", "code128", "code39", "ean13", "ean8"])
def test_new_barcode_renders_and_fits_everywhere(label, kind):
    doc = Document(label)
    area = layout.printable_area(doc)
    obj = layout.new_barcode(doc, "QL-600", area, kind)
    render_object(obj, Document(label, objects=[obj]))            # kein „zu niedrig“
    rect = layout.barcode_rect(obj)
    smallest = layout.barcode_rect(replace(obj, module=1, rotation=0))
    if smallest.w > max(layout._insert_limits(doc, "QL-600", area)):
        assert obj.module == 1                          # passt nicht einmal so: kleinstmöglich
        return
    grow = layout.growing_axis(doc)
    if grow != "x":
        assert area.x - 1e-6 <= rect.x and rect.right <= area.right + 1e-6
    if grow != "y":
        assert area.y - 1e-6 <= rect.y and rect.bottom <= area.bottom + 1e-6


@pytest.mark.parametrize("label", ["12", "d12", "62"])
@pytest.mark.parametrize("kind", ["qr", "code128", "ean13"])
@pytest.mark.parametrize("rotation", [0, 90])
def test_maximize_renders_and_fits_across(label, kind, rotation):
    doc = Document(label)
    obj = _bar(kind=kind, data=barcodes.SAMPLES[kind], module=1, h_mm=3, x_mm=1, y_mm=1,
               rotation=rotation)
    area = layout.printable_area(doc)
    big = layout.maximize_object(obj, _rendered(obj, label), area, doc)
    render_object(big, Document(label, objects=[big]))
    rect = layout.barcode_rect(big)
    grow = layout.growing_axis(doc)
    one = layout.barcode_rect(replace(obj, module=1))   # Strichcodes: nur die Modul-Richtung zählt
    need = ([("x", one.w, area.w), ("y", one.h, area.h)] if kind == "qr"
            else [("y", one.h, area.h)] if rotation == 90 else [("x", one.w, area.w)])
    if any(axis != grow and size > room + 1e-6 for axis, size, room in need):
        assert big == obj                               # passt nicht einmal 1 Punkt: bleibt
        return
    if grow != "x":
        assert rect.w <= area.w + 1e-6
    if grow != "y":
        assert rect.h <= area.h + 1e-6
    assert big.module >= obj.module


# --- Serie -------------------------------------------------------------------------------------
def test_placeholders_in_barcode_content():
    doc = Document(objects=[TextObject("{Name}"), _bar(kind="qr", data="https://x/{ Id }/{Name}")])
    assert placeholders(doc) == ["Name", "Id"]
    assert missing(doc, ["Name"]) == ["Id"]


def test_fill_barcode_content():
    plain = _bar(kind="code128", data="fest")
    doc = Document(objects=[_bar(kind="code39", data="X{Nr}-{Unbekannt}"), plain])
    filled = fill(doc, ["Nr"], ["17"])
    assert filled.objects[0].data == "X17-{Unbekannt}"
    assert doc.objects[0].data == "X{Nr}-{Unbekannt}"              # Original bleibt
    assert filled.objects[1] is plain                             # ohne Platzhalter: dasselbe
    assert fill(doc, ["Nr"], ["17"], keep=0).objects[0] is doc.objects[0]


def test_fill_anchored_keeps_the_barcode_corner():
    doc = Document("62x29", objects=[_bar(kind="code128", data="{Nr}", x_mm=10, y_mm=4)])
    filled = layout.fill_anchored(doc, ["Nr"], ["123456789"])
    assert (filled.objects[0].x_mm, filled.objects[0].y_mm) == (10, 4)


# --- Speichern ----------------------------------------------------------------------------------
def test_storage_round_trip():
    objs = [_bar(kind="qr", data="https://example.org", module=5, error="H", rotation=90),
            _bar(kind="ean13", data="590123412345", module=2, h_mm=14.5, text=False)]
    doc = Document("62x29", objects=objs)
    data = storage.to_dict(doc)
    assert data["document"]["objects"][0]["type"] == "barcode"
    assert storage.from_dict(json.loads(json.dumps(data))).objects == objs


@pytest.mark.parametrize("field, value", [("kind", "pdf417"), ("module", 0), ("module", 21),
                                          ("module", 2.5), ("h_mm", 1), ("h_mm", 101),
                                          ("error", "X"), ("data", 5), ("data", "x" * 2001),
                                          ("text", "ja")])
def test_storage_rejects_invalid_barcodes(field, value):
    data = storage.to_dict(Document(objects=[_bar(kind="code128", data="A")]))
    data["document"]["objects"][0][field] = value
    with pytest.raises(StorageError, match=f"„{field}“ in Objekt 1"):
        storage.from_dict(data)


def test_storage_needs_kind_and_content():
    data = storage.to_dict(Document(objects=[_bar(kind="code128", data="A")]))
    del data["document"]["objects"][0]["data"]
    with pytest.raises(StorageError, match="„data“ in Objekt 1 fehlt"):
        storage.from_dict(data)


def test_storage_keeps_invalid_content_for_the_render_error():
    data = storage.to_dict(Document(objects=[_bar(kind="ean13", data="123")]))
    assert storage.from_dict(data).objects[0].data == "123"


def test_storage_counts_barcodes_against_the_size_limit():
    """Größtmögliche Fläche ohne Kodieren – auch ein Platzhalter (erst die Serie füllt ihn) und
    ungültiger Inhalt zählen voll."""
    big = _bar(kind="code39", data="{Nummer}", module=20, h_mm=100)
    w, h = barcodes.max_size(big)
    fits = storage.MAX_FRAME_DOTS // (w * h)
    assert len(storage.from_dict(storage.to_dict(Document(objects=[big] * fits))).objects) == fits
    with pytest.raises(StorageError, match="Etikett zu groß"):
        storage.from_dict(storage.to_dict(Document(objects=[big] * (fits + 1))))
