"""Platzier-Logik ohne Qt: Einrasten, Ausrichten, Größe angleichen, Skalieren (Etappe 3d-1)."""
import pytest

from labelwerk import layout, render
from labelwerk.document import MAX_PT, MIN_PT, Document, ImageObject, Paragraph, Span, TextObject
from labelwerk.labels import DPI
from labelwerk.layout import Rect, Snap
from labelwerk.render import RenderedObject, render_document, render_object


def _mm(dots):
    return dots * 25.4 / DPI


def _approx(rect, **kw):
    """Rechteck mit Rundungsspielraum vergleichen (pytest.approx kennt keine Dataclasses)."""
    return pytest.approx((rect.x, rect.y, rect.w, rect.h), **kw)


def _t(rect):
    return (rect.x, rect.y, rect.w, rect.h)


def _reading_size(doc):
    img = render_document(doc)
    return img.size[::-1] if doc.orientation == "horizontal" else img.size


# --- Rect -------------------------------------------------------------------------
def test_rect_helpers():
    r = Rect(1, 2, 10, 4)
    assert (r.right, r.bottom, r.cx, r.cy) == (11, 6, 6, 4)


def test_rect_is_frozen():
    with pytest.raises(AttributeError):
        Rect(0, 0, 1, 1).x = 5


def test_rect_moved_and_resized():
    r = Rect(1, 2, 10, 4)
    assert r.moved(2, -1) == Rect(3, 1, 10, 4)
    assert r.at(0, 0) == Rect(0, 0, 10, 4)


def test_object_rect_converts_dots_to_mm():
    rendered = RenderedObject(None, 118, 236, 354, 59, 12.0)
    expected = Rect(_mm(118), _mm(236), _mm(354), _mm(59))
    assert _t(layout.object_rect(rendered)) == _approx(expected)


# --- Etikett und bedruckbarer Bereich ---------------------------------------------
@pytest.mark.parametrize("doc", [
    Document("62x29"),
    Document("62x29", orientation="horizontal"),
    Document("62", length_mm=50, margin_mm=3),
    Document("62", length_mm=50, margin_mm=3, orientation="horizontal"),
    Document("62", objects=[TextObject("Automatische Länge")]),
    Document("62", objects=[TextObject("Längs", size_pt=30)], orientation="horizontal"),
    Document("62", objects=[TextObject("A", size_pt=20, x_mm=70, y_mm=5)]),
    Document("29", objects=[TextObject("B", size_pt=20, x_mm=90, y_mm=2)], orientation="horizontal"),
], ids=range(8))
def test_label_rect_matches_render_document(doc):
    w, h = _reading_size(doc)
    assert _t(layout.label_rect(doc)) == _approx(Rect(0, 0, _mm(w), _mm(h)))


def test_printable_area_vertical_margins():
    doc = Document("62x29", margin_mm=2)
    label = layout.label_rect(doc)
    feed = _mm(round(2 * DPI / 25.4))
    area = layout.printable_area(doc)
    assert _t(area) == _approx(Rect(feed, feed, label.w - 2 * feed,      # Rand ringsum
                                      label.h - 2 * feed))


def test_printable_area_from_known_size_renders_nothing(monkeypatch):
    doc = Document("62", margin_mm=2, objects=[TextObject("A", size_pt=20, x_mm=3, y_mm=50)])
    size, expected = render.label_size(doc), layout.printable_area(doc)
    monkeypatch.setattr(render, "_prepare", lambda *a: pytest.fail("misst neu"))
    assert layout.printable_area(doc, size=size) == expected


def test_printable_area_horizontal_swaps_margins():
    doc = Document("62x29", margin_mm=2, orientation="horizontal")
    label = layout.label_rect(doc)
    feed = _mm(round(2 * DPI / 25.4))
    area = layout.printable_area(doc)
    assert _t(area) == _approx(Rect(feed, feed, label.w - 2 * feed, label.h - 2 * feed))


def test_printable_area_is_centered_on_label():
    doc = Document("62", length_mm=40, margin_mm=4)
    area, label = layout.printable_area(doc), layout.label_rect(doc)
    assert (area.cx, area.cy) == pytest.approx((label.cx, label.cy))


# --- Einrasten --------------------------------------------------------------------
_AREA = Rect(1, 1, 60, 28)
_LABEL = Rect(0, 0, 62, 30)


def test_snap_without_candidates_in_reach_does_nothing():
    moving = Rect(20, 9, 5, 5)
    assert layout.snap(moving, [], _AREA, 0.5) == Snap(0, 0, [])


def test_snap_left_edge_to_area():
    s = layout.snap(Rect(1.3, 9, 5, 5), [], _AREA, 0.5)
    assert s.dx == pytest.approx(-0.3) and s.dy == 0
    assert s.guides == [("x", 1)]


def test_snap_right_and_bottom_edge_to_area():
    s = layout.snap(Rect(55.8, 23.6, 5, 5), [], _AREA, 0.5)
    assert (s.dx, s.dy) == pytest.approx((0.2, 0.4))
    assert sorted(s.guides) == [("x", 61), ("y", 29)]


def test_snap_center_to_label_center():
    s = layout.snap(Rect(28.6, 12.3, 5, 5), [], _AREA, 0.5, label=_LABEL)
    assert (s.dx, s.dy) == pytest.approx((-0.1, 0.2))
    assert sorted(s.guides) == [("x", 31), ("y", 15)]


def test_snap_to_frame_inner_room():
    inner = Rect(3, 3, 56, 24)
    s = layout.snap(Rect(3.2, 9, 5, 5), [], _AREA, 0.5, inner=inner)
    assert s.dx == pytest.approx(-0.2) and s.guides == [("x", 3)]
    s = layout.snap(Rect(53.9, 9, 5, 5), [], _AREA, 0.5, inner=inner)      # rechte Innenkante 59
    assert s.dx == pytest.approx(0.1)


def test_snap_inner_room_offers_only_its_start_in_the_growing_axis():
    inner = Rect(3, 3, 56, 24)
    s = layout.snap(Rect(53.9, 9, 5, 5), [], _AREA, 0.5, inner=inner, grow="x")
    assert s.dx == 0


def test_snap_to_label_edge():
    s = layout.snap(Rect(0.2, 9, 5, 5), [], _AREA, 0.3, label=_LABEL)
    assert s.dx == pytest.approx(-0.2) and s.guides == [("x", 0)]


def test_snap_to_target_edges_and_centers():
    target = Rect(30, 5, 10, 4)                    # Mitte (35, 7)
    s = layout.snap(Rect(20.3, 4.8, 4, 3), [target], _AREA, 0.5)
    assert s.dx == 0                               # waagrecht nichts in Reichweite
    # Oberkante 4,8 → 5; Mitte 6,3 und Unterkante 7,8 liegen zu weit von 7 und 9
    assert s.dy == pytest.approx(0.2) and s.guides == [("y", 5)]
    s = layout.snap(Rect(32.8, 20, 4, 2), [target], _AREA, 0.5)
    assert s.dx == pytest.approx(0.2) and s.guides == [("x", 35)]   # Mitte an Mitte


def test_snap_picks_nearest_candidate():
    targets = [Rect(10.4, 20, 5, 5), Rect(10.1, 20, 5, 5)]
    s = layout.snap(Rect(10, 2, 2, 2), targets, _AREA, 0.5)
    assert s.dx == pytest.approx(0.1) and s.guides == [("x", 10.1)]


def test_snap_tolerance_boundary_is_inclusive():
    assert layout.snap(Rect(1.5, 9, 5, 5), [], _AREA, 0.5).dx == pytest.approx(-0.5)
    assert layout.snap(Rect(1.51, 9, 5, 5), [], _AREA, 0.5).dx == 0


def test_snap_zero_tolerance_only_exact():
    assert layout.snap(Rect(1, 9, 5, 5), [], _AREA, 0).guides == [("x", 1)]
    assert layout.snap(Rect(1.01, 9, 5, 5), [], _AREA, 0) == Snap(0, 0, [])


def test_snap_reports_all_lines_that_match_after_shift():
    # gleich breit wie das Ziel: linke und rechte Kante (und Mitte) treffen gleichzeitig
    target = Rect(30, 5, 10, 4)
    s = layout.snap(Rect(30.2, 16, 10, 4), [target], _AREA, 0.5)
    assert s.dx == pytest.approx(-0.2)
    assert sorted(s.guides) == [("x", 30), ("x", 35), ("x", 40)]


# --- Ausrichten -------------------------------------------------------------------
_RECTS = [Rect(5, 2, 10, 4), Rect(20, 8, 6, 10), Rect(12, 15, 4, 2)]


@pytest.mark.parametrize("mode, expected", [
    ("left", [5, 5, 5]),
    ("right", [16, 20, 22]),              # rechte Kanten auf 26
    ("hcenter", [10.5, 12.5, 13.5]),      # Mitte der Auswahl 15,5
])
def test_align_horizontally_to_each_other(mode, expected):
    out = layout.align(_RECTS, mode)
    assert [r.x for r in out] == pytest.approx(expected)
    assert [r.y for r in out] == [r.y for r in _RECTS]
    assert [(r.w, r.h) for r in out] == [(r.w, r.h) for r in _RECTS]


@pytest.mark.parametrize("mode, expected", [
    ("top", [2, 2, 2]),
    ("bottom", [14, 8, 16]),              # Unterkanten auf 18
    ("vcenter", [8, 5, 9]),               # Mitte der Auswahl 10
])
def test_align_vertically_to_each_other(mode, expected):
    out = layout.align(_RECTS, mode)
    assert [r.y for r in out] == pytest.approx(expected)
    assert [r.x for r in out] == [r.x for r in _RECTS]


@pytest.mark.parametrize("mode, attr, value", [
    ("left", "x", 1), ("right", "right", 61), ("hcenter", "cx", 31),
    ("top", "y", 1), ("bottom", "bottom", 29), ("vcenter", "cy", 15),
])
def test_align_to_area(mode, attr, value):
    out = layout.align(_RECTS, mode, area=_AREA)
    assert [getattr(r, attr) for r in out] == pytest.approx([value] * 3)


def test_bounds_encloses_all_rects():
    assert layout.bounds(_RECTS) == Rect(5, 2, 21, 16)
    assert layout.bounds([Rect(3, 4, 5, 6)]) == Rect(3, 4, 5, 6)


def test_align_single_rect_without_area_is_noop():
    assert layout.align([Rect(3, 4, 5, 6)], "left") == [Rect(3, 4, 5, 6)]
    assert layout.align([], "left") == []


def test_align_single_rect_to_area_moves():
    assert layout.align([Rect(3, 4, 5, 6)], "right", area=_AREA) == [Rect(56, 4, 5, 6)]


def test_align_unknown_mode_raises():
    with pytest.raises(ValueError, match="Ausrichtung"):
        layout.align(_RECTS, "diagonal")


# --- Größe angleichen, maximieren -------------------------------------------------
def test_match_size_uses_first_rect_as_reference():
    out = layout.match_size(_RECTS, "same")
    assert out[0] == _RECTS[0]
    assert all((r.w, r.h) == (10, 4) for r in out)
    assert [(r.x, r.y) for r in out] == [(r.x, r.y) for r in _RECTS]   # linke obere Ecke bleibt


def test_match_width_and_height():
    assert [(r.w, r.h) for r in layout.match_size(_RECTS, "width")] == [(10, 4), (10, 10), (10, 2)]
    assert [(r.w, r.h) for r in layout.match_size(_RECTS, "height")] == [(10, 4), (6, 4), (4, 4)]


def test_match_size_edge_cases():
    assert layout.match_size([], "same") == []
    with pytest.raises(ValueError, match="Größe"):
        layout.match_size(_RECTS, "quadrat")


def test_maximize_wide_rect_fills_width_centered():
    r = layout.maximize(Rect(10, 10, 20, 5), _AREA)        # Seitenverhältnis 4:1
    assert _t(r) == _approx(Rect(1, 15 - 7.5, 60, 15))


def test_maximize_tall_rect_fills_height_centered():
    r = layout.maximize(Rect(10, 10, 7, 14), _AREA)        # 1:2 → Höhe 28
    assert _t(r) == _approx(Rect(31 - 7, 1, 14, 28))


def test_maximize_degenerate_rect_is_only_centered():
    assert layout.maximize(Rect(3, 3, 0, 5), _AREA) == Rect(31, 12.5, 0, 5)


# --- Platzieren -------------------------------------------------------------------
def test_place_sets_position_without_touching_original():
    obj = TextObject("A", size_pt=12)
    placed = layout.place(obj, Rect(4, 5, 30, 10))
    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (4, 5, None, None)
    assert obj.x_mm is None and placed is not obj
    assert placed.paragraphs is not obj.paragraphs


def test_place_fit_object_sets_frame_size():
    obj = TextObject("A", size_pt=12, fit=True)
    placed = layout.place(obj, Rect(4, 5, 30, 10))
    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (4, 5, 30, 10)


def test_place_rotated_fit_object_stores_unrotated_frame():
    obj = TextObject("A", size_pt=12, fit=True, rotation=90)
    placed = layout.place(obj, Rect(4, 5, 10, 30))
    assert (placed.w_mm, placed.h_mm) == (30, 10)
    doc = Document("62", length_mm=60, objects=[placed])
    rect = layout.object_rect(render_object(placed, doc))
    assert _t(rect) == _approx(Rect(4, 5, 10, 30), abs=_mm(1))


# --- Text skalieren ---------------------------------------------------------------
def _sizes(obj):
    return obj.size_pt, [s.size_pt for p in obj.paragraphs for s in p.spans]


def test_scale_text_scales_base_and_spans():
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=20)])], size_pt=10)
    scaled = layout.scale_text(obj, 1.5)
    assert _sizes(scaled) == (15, [None, 30])
    assert _sizes(obj) == (10, [None, 20])                 # Original unverändert


def test_scale_text_clamps_factor_to_keep_ratios():
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=40)])], size_pt=20)
    assert _sizes(layout.scale_text(obj, 10)) == (50, [None, MAX_PT])
    assert _sizes(layout.scale_text(obj, 0.01)) == (MIN_PT, [None, 8])


def test_scale_text_at_limit_keeps_sizes():
    # größtes Stück schon 100 pt: Vergrößern ändert nichts, Verhältnisse bleiben
    obj = TextObject([Paragraph([Span("a", size_pt=5), Span("b", size_pt=100)])], size_pt=10)
    assert _sizes(layout.scale_text(obj, 2)) == (10, [5, 100])
    obj = TextObject([Paragraph([Span("a", size_pt=4), Span("b", size_pt=100)])], size_pt=50)
    assert _sizes(layout.scale_text(obj, 0.5)) == (50, [4, 100])


def test_scale_text_clamps_each_size_when_ratio_too_wide():
    # Größen außerhalb 4–100 (z. B. von Hand bearbeitet): jede Größe für sich begrenzt,
    # aber nicht in den Bereich hineingezogen
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=100)])], size_pt=2)
    assert _sizes(layout.scale_text(obj, 1.5)) == (3, [None, MAX_PT])


def test_scale_text_rounds_to_tenth():
    obj = TextObject("A", size_pt=10)
    assert layout.scale_text(obj, 1.2345).size_pt == 12.3


def test_scale_text_auto_size_uses_effective_base():
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=24)])])   # relativ zu 12 pt
    scaled = layout.scale_text(obj, 2, base_pt=18)
    # bisher wirksam: Grundgröße 18, Stück 24/12 × 18 = 36 → doppelt
    assert _sizes(scaled) == (36, [None, 72])


def test_scale_text_auto_size_without_base_raises():
    with pytest.raises(ValueError, match="Schriftgröße"):
        layout.scale_text(TextObject("A"), 2)


def test_scale_text_rejects_non_positive_factor():
    with pytest.raises(ValueError, match="Faktor"):
        layout.scale_text(TextObject("A", size_pt=10), 0)


def test_scale_text_renders_proportionally_larger():
    obj = TextObject("Hallo", size_pt=10, x_mm=2, y_mm=2)
    doc = Document("62", length_mm=80, objects=[obj])
    small = render_object(obj, doc)
    big = render_object(layout.scale_text(obj, 2), doc)
    assert big.w == pytest.approx(2 * small.w, rel=0.08)


# --- Objekte außerhalb ------------------------------------------------------------
def test_objects_outside_none_for_centered_and_inside():
    doc = Document("62", length_mm=40, objects=[TextObject("Mitte"),
                                                 TextObject("A", size_pt=12, x_mm=5, y_mm=5)])
    assert layout.objects_outside(doc) == []


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_objects_outside_lists_overhanging_indices(orientation):
    doc = Document("62", length_mm=40, orientation=orientation, objects=[
        TextObject("innen", size_pt=12, x_mm=5, y_mm=5),
        TextObject("rechts", size_pt=12, x_mm=60, y_mm=5) if orientation == "vertical"
        else TextObject("unten", size_pt=12, x_mm=5, y_mm=60),
        TextObject("innen", size_pt=12, x_mm=2, y_mm=10),
        TextObject("negativ", size_pt=12, x_mm=-1, y_mm=5),
    ])
    assert layout.objects_outside(doc) == [1, 3]


def test_objects_outside_auto_length_grows_instead():
    # automatische Länge: in Bandlaufrichtung wächst das Etikett mit
    doc = Document("62", objects=[TextObject("weit unten", size_pt=12, x_mm=5, y_mm=150)])
    assert layout.objects_outside(doc) == []


def test_objects_outside_ignores_empty_objects():
    doc = Document("62", length_mm=40, objects=[TextObject("", size_pt=12, x_mm=200, y_mm=200)])
    assert layout.objects_outside(doc) == []


# --- Verschieben und Anfasser (Arbeitsfläche) ---------------------------------------
def _rendered(x_mm, y_mm, w_mm, h_mm, base_pt=12.0):
    """Gerendertes Objekt wie von render_object: Position und Größe auf Druckpunkte gerundet."""
    dots = [round(v * DPI / 25.4) for v in (x_mm, y_mm, w_mm, h_mm)]
    return RenderedObject(None, *dots, base_pt)


def test_exact_rect_uses_model_position_and_fixed_frame():
    obj = TextObject("A", size_pt=12, fit=True, x_mm=4, y_mm=5, w_mm=20, h_mm=8, rotation=90)
    assert layout.exact_rect(obj, _rendered(4, 5, 8, 20)) == Rect(4, 5, 8, 20)   # gedreht
    free = TextObject("A", size_pt=12, x_mm=4, y_mm=5)
    rendered = _rendered(4, 5, 10, 3)
    assert layout.exact_rect(free, rendered) == Rect(4, 5, _mm(rendered.w), _mm(rendered.h))
    centered = TextObject("A")
    assert _t(layout.exact_rect(centered, rendered)) == _t(layout.object_rect(rendered))


def test_fix_size_freezes_effective_size_and_turns_fit_off():
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=24)])], size_pt=12, fit=True)
    fixed = layout.fix_size(obj, 18.04)
    assert _sizes(fixed) == (18, [None, 36])               # Stück behält sein Verhältnis
    assert not fixed.fit and obj.fit


def test_move_shifts_model_position_by_exact_amount():
    # Druckpunkte runden 4 mm auf 3,98 mm – die Verschiebung zählt, nicht der gerundete Wert
    obj = TextObject("A", size_pt=12, x_mm=4, y_mm=5)
    rendered = _rendered(4, 5, 10, 3)
    moved = layout.move(obj, layout.object_rect(rendered).moved(-0.1, 1), rendered)
    assert (moved.x_mm, moved.y_mm) == pytest.approx((3.9, 6))
    assert (moved.size_pt, moved.fit, obj.x_mm) == (12, False, 4)


@pytest.mark.parametrize("obj", [TextObject("Hallo"), TextObject("Hallo", size_pt=12, fit=True)],
                         ids=["ohne Größe", "feste Rahmengröße"])
def test_first_move_of_auto_object_keeps_its_image(obj):
    doc = Document("62", objects=[obj])
    before = render_object(obj, doc)
    moved = layout.move(obj, layout.object_rect(before), before)
    assert moved.positioned and not moved.auto
    doc.objects = [moved]
    after = render_object(moved, doc)
    assert after.image.tobytes() == before.image.tobytes()
    assert (after.x, after.y) == (before.x, before.y)


def test_move_positioned_fit_object_keeps_frame():
    obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8)
    rendered = _rendered(1, 1, 20, 8, base_pt=30)
    moved = layout.move(obj, layout.object_rect(rendered).moved(3, 4), rendered)
    assert (moved.x_mm, moved.y_mm, moved.w_mm, moved.h_mm, moved.fit) == \
        pytest.approx((4, 5, 20, 8, True))
    assert moved.size_pt == 12


def test_resize_fit_object_changes_frame():
    obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8)
    rendered = _rendered(1, 1, 20, 8, base_pt=30)
    old = layout.object_rect(rendered)
    for handle in ("bl", "b"):
        new = Rect(old.x - 1, old.y, old.w + 5, old.h + 4)
        resized = layout.resize(obj, new, rendered, handle)
        assert (resized.x_mm, resized.y_mm, resized.w_mm, resized.h_mm) == \
            pytest.approx((0, 1, 25, 12))
        assert resized.fit and resized.size_pt == 12


def test_resize_corner_scales_text_without_frame():
    obj = TextObject("A", size_pt=12, x_mm=1, y_mm=1)
    rendered = _rendered(1, 1, 10, 5)
    old = layout.object_rect(rendered)
    bigger = Rect(old.x, old.y, old.w * 1.5, old.h * 1.5)
    resized = layout.resize(obj, bigger, rendered, "br")
    assert (resized.size_pt, resized.fit) == (18, False)
    assert (resized.x_mm, resized.y_mm) == pytest.approx((1, 1))
    assert resized.w_mm is None


def test_resize_corner_of_auto_object_uses_effective_size():
    rendered = _rendered(1, 1, 10, 5, base_pt=20)
    old = layout.object_rect(rendered)
    smaller = Rect(0, 0, old.w / 2, old.h / 2)
    resized = layout.resize(TextObject("A"), smaller, rendered, "tl")
    assert (resized.size_pt, resized.x_mm, resized.y_mm) == (10, 0, 0)


def test_resize_edge_turns_fixed_frame_on():
    obj = TextObject("A", size_pt=12, x_mm=1, y_mm=1, rotation=90)
    rendered = _rendered(1, 1, 5, 10)
    old = layout.object_rect(rendered)
    resized = layout.resize(obj, Rect(old.x, old.y, old.w, old.h + 8), rendered, "b")
    assert resized.fit
    assert (resized.x_mm, resized.y_mm, resized.w_mm, resized.h_mm) == \
        pytest.approx((1, 1, old.h + 8, old.w), abs=0.001)             # ungedreht gespeichert


# --- Zahlen im Panel „Position“ -----------------------------------------------------
def test_set_frame_moves_object_without_fixed_frame():
    obj = TextObject("A", size_pt=12, x_mm=4, y_mm=5)
    placed = layout.set_frame(obj, Rect(10, 6, 99, 99), _rendered(4, 5, 10, 3))
    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (10, 6, None, None)
    assert (placed.size_pt, placed.fit, obj.x_mm) == (12, False, 4)


def test_set_frame_positions_automatic_object_with_its_effective_size():
    rendered = _rendered(20, 8, 10, 3, base_pt=23.04)
    placed = layout.set_frame(TextObject("Hallo"), Rect(10, 6, 10, 3), rendered)
    assert placed.positioned and (placed.x_mm, placed.y_mm) == (10, 6)
    assert placed.size_pt == 23 and not placed.fit


@pytest.mark.parametrize("positioned", [True, False])
def test_set_frame_changes_fixed_frame(positioned):
    obj = TextObject("A", size_pt=12, fit=True, w_mm=20 if positioned else None,
                     h_mm=8 if positioned else None,
                     x_mm=1 if positioned else None, y_mm=1 if positioned else None)
    placed = layout.set_frame(obj, Rect(2, 3, 25, 12), _rendered(1, 1, 20, 8))
    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (2, 3, 25, 12)
    assert placed.fit and placed.size_pt == 12


def test_set_frame_stores_rotated_frame_unrotated():
    obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8, rotation=90)
    placed = layout.set_frame(obj, Rect(1, 1, 10, 30), _rendered(1, 1, 8, 20))
    assert (placed.w_mm, placed.h_mm) == (30, 10)


# --- Reiter „Layout“: Objekte ausrichten, angleichen, drehen, Reihenfolge -----------
def _frame(obj, doc=None):
    rendered = render_object(obj, doc or Document("62", length_mm=40, objects=[obj]))
    return layout.exact_rect(obj, rendered), rendered


def _three():
    return [TextObject("A", size_pt=12, x_mm=4, y_mm=4),
            TextObject("Breiter", size_pt=12, x_mm=10, y_mm=15),
            TextObject("B", size_pt=12, fit=True, x_mm=7, y_mm=25, w_mm=20, h_mm=6)]


def _rendered_of(objs):
    doc = Document("62", length_mm=40, objects=objs)
    return [render_object(obj, doc) for obj in objs]


@pytest.mark.parametrize("mode, attr", [("left", "x"), ("right", "right"), ("hcenter", "cx"),
                                        ("top", "y"), ("bottom", "bottom"), ("vcenter", "cy")])
def test_align_objects_to_each_other(mode, attr):
    objs = _three()
    rendered = _rendered_of(objs)
    before = [layout.exact_rect(o, r) for o, r in zip(objs, rendered)]
    aligned = layout.align_objects(objs, rendered, mode)
    expected = getattr(layout.align(before, mode)[0], attr)
    after = [layout.exact_rect(o, r) for o, r in zip(aligned, _rendered_of(aligned))]
    assert [getattr(r, attr) for r in after] == pytest.approx([expected] * 3, abs=0.001)
    other = "y" if attr in ("x", "right", "cx") else "x"     # andere Achse bleibt
    assert [getattr(r, other) for r in after] == pytest.approx([getattr(r, other) for r in before])
    assert (objs[0].x_mm, objs[0].y_mm) == (4, 4)            # Eingabe bleibt unverändert


def test_align_objects_to_paper_uses_area():
    objs = _three()
    area = Rect(1, 1.5, 38, 59)
    aligned = layout.align_objects(objs, _rendered_of(objs), "right", area)
    after = [layout.exact_rect(o, r) for o, r in zip(aligned, _rendered_of(aligned))]
    assert [r.right for r in after] == pytest.approx([39] * 3, abs=0.001)


def test_align_objects_positions_centered_object_with_its_size():
    obj = TextObject("Mitte")
    doc = Document("62", length_mm=40, objects=[obj])
    rendered = render_object(obj, doc)
    [aligned] = layout.align_objects([obj], [rendered], "top", Rect(1, 1.5, 38, 59))
    assert aligned.positioned and aligned.y_mm == pytest.approx(1.5)
    assert aligned.size_pt == pytest.approx(rendered.base_pt, abs=0.05)


def test_match_objects_sets_fixed_frame_to_reference():
    objs = [TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=30, h_mm=10),
            TextObject("B", size_pt=12, fit=True, x_mm=5, y_mm=20, w_mm=10, h_mm=4)]
    rendered = _rendered_of(objs)
    for mode, size in (("same", (30, 10)), ("width", (30, 4)), ("height", (10, 10))):
        ref, other = layout.match_objects(objs, rendered, mode)
        assert ref is objs[0]                                # unverändert, keine Kopie (Cache)
        assert (other.w_mm, other.h_mm, other.x_mm, other.y_mm) == (*size, 5, 20)


@pytest.mark.parametrize("mode", ["same", "width", "height"])
def test_match_objects_scales_text_without_fixed_frame(mode):
    objs = [TextObject("Wort", size_pt=24, x_mm=1, y_mm=1),
            TextObject("Wort", size_pt=12, x_mm=5, y_mm=30)]
    ref, other = layout.match_objects(objs, _rendered_of(objs), mode)
    assert other.size_pt == pytest.approx(24, abs=0.5) and not other.fit
    assert (other.x_mm, other.y_mm) == (5, 30)                # Ecke bleibt


def test_match_objects_keeps_aspect_for_width():
    objs = [TextObject("Langer Text", size_pt=12, x_mm=1, y_mm=1),
            TextObject("Kurz", size_pt=12, x_mm=1, y_mm=20)]
    rendered = _rendered_of(objs)
    _, other = layout.match_objects(objs, rendered, "width")
    after = layout.object_rect(_rendered_of([objs[0], other])[1])
    assert after.w == pytest.approx(layout.object_rect(rendered[0]).w, rel=0.05)
    assert other.size_pt > 12


@pytest.mark.parametrize("fit", [False, True])
def test_maximize_object_fills_area_centered(fit):
    obj = TextObject("Wort", size_pt=12, fit=fit, x_mm=2, y_mm=2,
                     w_mm=10 if fit else None, h_mm=4 if fit else None)
    doc = Document("62", length_mm=40, objects=[obj])
    area = layout.printable_area(doc)
    big = layout.maximize_object(obj, render_object(obj, doc), area, doc)
    r = layout.object_rect(render_object(big, doc))
    assert r.x >= area.x - 0.1 and r.right <= area.right + 0.1
    assert r.y >= area.y - 0.1 and r.bottom <= area.bottom + 0.1
    assert max(r.w / area.w, r.h / area.h) == pytest.approx(1, abs=0.06)
    assert (r.cx, r.cy) == pytest.approx((area.cx, area.cy), abs=0.2)


@pytest.mark.parametrize("fit", [False, True])
@pytest.mark.parametrize("start, degrees, end", [(0, 90, 90), (0, -90, 270), (270, 90, 0),
                                                 (90, -90, 0), (180, 90, 270)])
def test_rotate_keeps_center(fit, start, degrees, end):
    obj = TextObject("Drehen", size_pt=12, fit=fit, x_mm=10, y_mm=10, rotation=start,
                     w_mm=20 if fit else None, h_mm=6 if fit else None)
    before, rendered = _frame(obj)
    turned = layout.rotate(obj, rendered, degrees)
    after, _ = _frame(turned)
    assert turned.rotation == end
    assert (after.w, after.h) == pytest.approx((before.h, before.w), abs=0.1)
    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=0.1)
    if fit:
        assert (turned.w_mm, turned.h_mm) == pytest.approx((20, 6))


def test_rotate_positions_centered_object():
    obj = TextObject("Mitte")
    before, rendered = _frame(obj)
    turned = layout.rotate(obj, rendered, 90)
    after, _ = _frame(turned)
    assert turned.positioned and turned.size_pt is not None
    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=0.1)


@pytest.mark.parametrize("indices, step, order, moved", [
    ([0], 1, "BACD", [1]),
    ([3], 1, "ABCD", [3]),                  # ganz vorne bleibt vorne
    ([1, 2], 1, "ADBC", [2, 3]),
    ([2, 3], 1, "ABCD", [2, 3]),            # blockiert vom vordersten
    ([2, 0], -1, "ACBD", [1, 0]),           # Indizes in der Reihenfolge der Wahl
    ([1], -1, "BACD", [0]),
    ([], 1, "ABCD", []),
])
def test_reorder(indices, step, order, moved):
    items, new = layout.reorder(list("ABCD"), indices, step)
    assert "".join(items) == order and new == moved


# --- Randfälle (Fix-Runde) ----------------------------------------------------------
def test_fix_size_of_auto_object_with_span_sizes_keeps_image():
    obj = TextObject([Paragraph([Span("klein", size_pt=10), Span("GROSS", size_pt=30)])])
    doc = Document("62", objects=[obj])
    before = render_document(doc)
    fixed = layout.fix_size(obj, render_object(obj, doc).base_pt)
    assert fixed.size_pt is not None and not fixed.fit
    assert render_document(Document("62", objects=[fixed])).tobytes() == before.tobytes()


@pytest.mark.parametrize("size", [8, 20, 33])
def test_fix_size_of_fit_object_with_span_sizes_keeps_image(size):
    obj = TextObject([Paragraph([Span("klein", size_pt=10), Span("GROSS", size_pt=30)])],
                     size_pt=size, fit=True)
    doc = Document("62", objects=[obj])
    fixed = layout.fix_size(obj, render_object(obj, doc).base_pt)
    assert render_document(Document("62", objects=[fixed])).tobytes() == \
        render_document(doc).tobytes()


@pytest.mark.parametrize("size", [0, -3])
def test_scale_text_rejects_non_positive_sizes(size):
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=size)])], size_pt=10)
    with pytest.raises(ValueError, match="Schriftgröße"):
        layout.scale_text(obj, 2)
    with pytest.raises(ValueError, match="Schriftgröße"):
        layout.scale_text(TextObject("A", size_pt=size), 2)
    with pytest.raises(ValueError, match="Schriftgröße"):
        layout.scale_text(TextObject("A"), 2, base_pt=size)


def test_scale_text_factor_one_keeps_small_sizes():
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=3)])], size_pt=10)
    assert _sizes(layout.scale_text(obj, 1)) == (10, [None, 3])
    assert _sizes(layout.scale_text(obj, 0.5)) == (10, [None, 3])   # kleiner geht nicht
    assert _sizes(layout.scale_text(obj, 2)) == (20, [None, 6])


def test_scale_text_never_pushes_size_outside_further():
    obj = TextObject("A", size_pt=2)
    assert layout.scale_text(obj, 1).size_pt == 2
    assert layout.scale_text(obj, 1.5).size_pt == 3


@pytest.mark.parametrize("area", [Rect(0, 0, 0, 10), Rect(0, 0, 10, -1)])
def test_maximize_into_empty_area_keeps_rect(area):
    assert layout.maximize(Rect(3, 4, 5, 6), area) == Rect(3, 4, 5, 6)


def test_maximize_on_growing_axis_fits_across_only():
    # Endlosband mit automatischer Länge („y“ wächst): nur die Breite begrenzt
    r = layout.maximize(Rect(10, 30, 10, 10), _AREA, grow="y")
    assert _t(r) == _approx(Rect(_AREA.x, 30, _AREA.w, _AREA.w))
    r = layout.maximize(Rect(30, 10, 10, 10), _AREA, grow="x")
    assert _t(r) == _approx(Rect(30, _AREA.y, _AREA.h, _AREA.h))


@pytest.mark.parametrize("doc, axis", [
    (Document("62"), "y"), (Document("62", orientation="horizontal"), "x"),
    (Document("62", length_mm=40), None), (Document("62x29"), None)])
def test_growing_axis(doc, axis):
    assert layout.growing_axis(doc) == axis


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_maximize_object_on_auto_length_fills_across(orientation):
    obj = TextObject("AB\nCD", size_pt=6, x_mm=2, y_mm=2)
    doc = Document("29", orientation=orientation, objects=[obj])
    area = layout.printable_area(doc)
    big = layout.maximize_object(obj, render_object(obj, doc), area, doc)
    doc.objects = [big]
    r = layout.object_rect(render_object(big, doc))
    across, room = (r.w, area.w) if orientation == "vertical" else (r.h, area.h)
    along, old_room = (r.h, area.h) if orientation == "vertical" else (r.w, area.w)
    assert across == pytest.approx(room, rel=0.06) and across <= room + 0.1
    assert along > old_room                         # Etikett wächst mit, statt zu begrenzen
    assert (big.x_mm, big.y_mm)[orientation == "vertical"] == pytest.approx(2)  # Anfang bleibt


def test_snap_on_growing_axis_ignores_moving_end_and_center():
    area, label = Rect(1, 1, 60, 30), Rect(0, 0, 62, 32)
    moving = Rect(10, 24.5, 10, 6)                 # Unterkante 30,5 nahe area.bottom (31)
    assert layout.snap(moving, [], area, 2, label=label).dy != 0
    s = layout.snap(moving, [], area, 2, label=label, grow="y")
    assert s.dy == 0 and not [g for g in s.guides if g[0] == "y"]
    near_center = Rect(10, 13.5, 10, 6)            # Mitte 16.5 nahe label.cy 16
    assert layout.snap(near_center, [], area, 1, label=label, grow="y").dy == 0
    top = Rect(10, 1.5, 10, 6)                      # Anfang bleibt Einrastziel
    assert layout.snap(top, [], area, 1, label=label, grow="y").dy == pytest.approx(-0.5)


def test_outside_indices_from_rendered_objects():
    rendered = [RenderedObject(None, 10, 10, 20, 20, 12.0),
                RenderedObject(None, 90, 10, 20, 20, 12.0),
                RenderedObject(None, -1, 10, 20, 20, 12.0),
                RenderedObject(None, 500, 500, 0, 0, 12.0)]       # leer
    assert layout.outside_indices(rendered, (100, 50)) == [1, 2]


def test_objects_outside_raises_text_too_large_like_rendering():
    from labelwerk.render import TextTooLarge
    doc = Document("29", objects=[TextObject("W" * 60, size_pt=40)])
    with pytest.raises(TextTooLarge):
        layout.objects_outside(doc)


# --- Raster der Positionsfelder ------------------------------------------------------
def test_to_grid_rounds_chosen_values_to_tenth_mm():
    obj = TextObject("A", fit=True, x_mm=1.234, y_mm=5.678, w_mm=20.049, h_mm=7.051)
    assert _model_frame(layout.to_grid(obj, x=True, w=True)) == (1.2, 5.678, 20.0, 7.051)
    assert _model_frame(layout.to_grid(obj, y=True, h=True)) == (1.234, 5.7, 20.049, 7.1)
    assert _model_frame(obj) == (1.234, 5.678, 20.049, 7.051)          # Original bleibt


def test_to_grid_maps_reading_width_of_turned_object_to_h_mm():
    obj = TextObject("A", fit=True, x_mm=1, y_mm=1, w_mm=20.049, h_mm=7.051, rotation=90)
    assert _model_frame(layout.to_grid(obj, w=True)) == (1, 1, 20.049, 7.1)


def test_to_grid_leaves_missing_values_alone():
    obj = TextObject("A", size_pt=12, x_mm=1.26)
    grid = layout.to_grid(obj, x=True, y=True, w=True, h=True)
    assert _model_frame(grid) == (1.3, None, None, None)


def _model_frame(obj):
    return obj.x_mm, obj.y_mm, obj.w_mm, obj.h_mm


# --- Gedrehte und gemischte Objekte im Reiter „Layout“ -------------------------------------
DOT_MM = 25.4 / DPI


def _mixed():
    """Gedreht ohne/mit fester Rahmengröße und ungedreht – Rahmen in Leserichtung verschieden."""
    return [TextObject("Quer", size_pt=14, x_mm=3, y_mm=4, rotation=90),
            TextObject("Rahmen", size_pt=12, fit=True, x_mm=20, y_mm=10, w_mm=24, h_mm=8,
                       rotation=270),
            TextObject("Gerade", size_pt=10, x_mm=12, y_mm=30)]


def _shown(objs):
    return [layout.object_rect(r) for r in _rendered_of(objs)]


@pytest.mark.parametrize("mode, attr", [("left", "x"), ("right", "right"), ("hcenter", "cx"),
                                        ("top", "y"), ("bottom", "bottom"), ("vcenter", "cy")])
def test_align_rotated_and_mixed_objects(mode, attr):
    objs = _mixed()
    aligned = layout.align_objects(objs, _rendered_of(objs), mode)
    values = [getattr(r, attr) for r in _shown(aligned)]
    assert max(values) - min(values) <= 2 * DOT_MM           # gerendert bündig (Druckpunkte)
    assert [o.rotation for o in aligned] == [90, 270, 0]
    assert aligned[1].fit and (aligned[1].w_mm, aligned[1].h_mm) == (24, 8)   # Rahmen bleibt


@pytest.mark.parametrize("mode", ["same", "width", "height"])
def test_match_size_with_rotated_fixed_frame_reference(mode):
    objs = _mixed()
    ref, other, plain = layout.match_objects([objs[1], objs[0], objs[2]],
                                             _rendered_of([objs[1], objs[0], objs[2]]), mode)
    target = _shown([ref])[0]                                # 8 × 24 mm in Leserichtung
    after = _shown([ref, other, plain])
    for r in after[1:]:                                      # Text ohne Rahmen: Verhältnis bleibt
        measure = {"width": lambda q: q.w, "height": lambda q: q.h,
                   "same": lambda q: q.w * q.h}[mode]      # „gleiche Größe“: gleiche Fläche
        assert measure(r) == pytest.approx(measure(target), rel=0.15)
    assert not other.fit and other.rotation == 90            # Text ohne Rahmen: skaliert


def test_match_size_sets_turned_fixed_frame_from_plain_reference():
    objs = _mixed()
    ref, framed = layout.match_objects([objs[2], objs[1]], _rendered_of([objs[2], objs[1]]),
                                       "same")
    want = _shown([ref])[0]
    got = _shown([framed])[0]
    assert (got.w, got.h) == pytest.approx((want.w, want.h), abs=0.1)
    assert (framed.w_mm, framed.h_mm) == pytest.approx((want.h, want.w), abs=0.01)  # ungedreht


@pytest.mark.parametrize("index", [0, 1])
def test_maximize_rotated_objects(index):
    obj = _mixed()[index]
    doc = Document("62", length_mm=40, objects=[obj])
    area = layout.printable_area(doc)
    big = layout.maximize_object(obj, render_object(obj, doc), area, doc)
    r = layout.object_rect(render_object(big, doc))
    assert r.x >= area.x - 0.1 and r.right <= area.right + 0.1
    assert r.y >= area.y - 0.1 and r.bottom <= area.bottom + 0.1
    assert max(r.w / area.w, r.h / area.h) == pytest.approx(1, abs=0.06)
    assert (r.cx, r.cy) == pytest.approx((area.cx, area.cy), abs=0.2)
    assert big.rotation == obj.rotation and big.fit == obj.fit


# --- Schlussrunde -------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["same", "width", "height"])
@pytest.mark.parametrize("fit", [False, True])
def test_match_objects_with_empty_reference_changes_nothing(mode, fit):
    empty = TextObject("", size_pt=12, x_mm=1, y_mm=1)
    other = TextObject("Zwei", size_pt=14, fit=fit, x_mm=5, y_mm=5, w_mm=20 if fit else None,
                       h_mm=8 if fit else None)
    rendered = [_rendered(1, 1, 0, 0), _rendered(5, 5, 20, 8)]
    result = layout.match_objects([empty, other], rendered, mode)
    assert result == [empty, other]


def test_edge_resize_of_auto_size_text_then_move_keeps_frame():
    obj = TextObject("A", x_mm=1, y_mm=1)                    # size_pt None
    rendered = _rendered(1, 1, 10, 5, base_pt=20)
    old = layout.object_rect(rendered)
    framed = layout.resize(obj, Rect(old.x, old.y, old.w + 10, old.h), rendered, "r")
    assert framed.fit and framed.size_pt == 20
    moved = layout.move(framed, Rect(old.x + 2, old.y, old.w + 10, old.h),
                        _rendered(1, 1, 20, 5, base_pt=20))
    assert moved.fit and moved.w_mm == pytest.approx(framed.w_mm)
    assert moved.h_mm == pytest.approx(framed.h_mm)


@pytest.mark.parametrize("orientation, modes", [
    ("vertical", ("top", "vcenter", "bottom")), ("horizontal", ("left", "hcenter", "right"))])
def test_align_to_paper_along_growing_axis_puts_group_at_start_margin(orientation, modes):
    vertical = orientation == "vertical"
    objs = [TextObject("A\nB", size_pt=14, x_mm=7, y_mm=9),
            TextObject("Zweiter", size_pt=10, x_mm=12, y_mm=20)]
    for mode in modes:
        doc = Document("62", orientation=orientation, margin_mm=3, objects=objs)
        rendered = [render_object(o, doc) for o in doc.objects]
        area = layout.printable_area(doc)
        moved = layout.align_objects(doc.objects, rendered, mode, area,
                                     grow=layout.growing_axis(doc))
        doc.objects = moved
        rects = [layout.object_rect(render_object(o, doc)) for o in moved]
        old = [layout.object_rect(r) for r in rendered]
        box = layout.bounds(rects)
        start, end = (box.y, box.bottom) if vertical else (box.x, box.right)
        assert start == pytest.approx(area.y if vertical else area.x, abs=0.1)
        w, h = layout.label_size(doc)
        length = _mm(h if vertical else w)
        assert length - end == pytest.approx(start, abs=2 * 25.4 / DPI)   # gleicher Rand beidseitig
        gap = (lambda r: r[1].y - r[0].y) if vertical else (lambda r: r[1].x - r[0].x)
        assert gap(rects) == pytest.approx(gap(old), abs=0.1)             # Abstand bleibt


@pytest.mark.parametrize("grow, across", [
    ("y", ("left", "hcenter", "right")), ("x", ("top", "vcenter", "bottom"))])
def test_align_to_paper_across_still_works_on_growing_label(grow, across):
    objs = [TextObject("A", size_pt=12, x_mm=3, y_mm=4)]
    rendered = [_rendered(3, 4, 10, 5)]
    area = Rect(2, 2, 50, 50)
    for mode in across:
        assert layout.align_objects(objs, rendered, mode, area, grow=grow) != objs


@pytest.mark.parametrize("grow, moving", [("y", Rect(10, 1.4, 10, 6)), ("x", Rect(1.4, 10, 6, 10))])
def test_snap_to_start_margin_on_auto_length(grow, moving):
    area, label = Rect(1, 1, 60, 80), Rect(0, 0, 62, 82)
    s = layout.snap(moving, [], area, 1, label=label, grow=grow)
    axis = "y" if grow == "y" else "x"
    assert (s.dy if grow == "y" else s.dx) == pytest.approx(-0.4)
    assert (axis, 1.0) in s.guides


# --- Bilder (Etappe 3d-2a) ----------------------------------------------------------
def _picture(x_mm=10, y_mm=5, w_mm=20, h_mm=10, **kw):
    from PIL import Image
    obj = ImageObject.from_image(Image.new("RGB", (40, 20), "black"), 300, "bild.png")
    obj.x_mm, obj.y_mm, obj.w_mm, obj.h_mm = x_mm, y_mm, w_mm, h_mm
    for key, value in kw.items():
        setattr(obj, key, value)
    return obj


def test_exact_rect_of_image_is_its_frame():
    assert layout.exact_rect(_picture(), _rendered(10, 5, 20, 10)) == Rect(10, 5, 20, 10)
    turned = _picture(rotation=90)
    assert layout.exact_rect(turned, _rendered(10, 5, 10, 20)) == Rect(10, 5, 10, 20)


def test_move_image_keeps_size():
    obj = _picture()
    rendered = _rendered(10, 5, 20, 10)
    moved = layout.move(obj, layout.object_rect(rendered).moved(1.5, -0.5), rendered)
    assert _model_frame(moved) == pytest.approx((11.5, 4.5, 20, 10))
    assert isinstance(moved, ImageObject) and moved.png is obj.png and obj.x_mm == 10


def test_set_frame_of_image_sets_position_and_size():
    obj = _picture(rotation=270)
    placed = layout.set_frame(obj, Rect(1, 2, 8, 30), _rendered(10, 5, 10, 20))
    assert _model_frame(placed) == (1, 2, 30, 8)                   # ungedreht gespeichert


@pytest.mark.parametrize("handle, new, expected", [
    ("br", Rect(10, 5, 40, 12), (10, 5, 40, 20)),     # rechts unten gezogen: größeres Maß zählt
    ("bl", Rect(0, 5, 30, 25), (-20, 5, 50, 25)),     # links unten: rechte obere Ecke bleibt
    ("tl", Rect(14, 1, 16, 14), (2, 1, 28, 14)),      # links oben: rechte untere Ecke bleibt
])
def test_resize_image_corner_keeps_ratio(handle, new, expected):
    obj = _picture()
    rendered = _rendered(10, 5, 20, 10)
    shown = layout.object_rect(rendered)
    delta = Rect(new.x - 10 + shown.x, new.y - 5 + shown.y, new.w - 20 + shown.w,
                 new.h - 10 + shown.h)                 # relativ zum gerundeten Rahmen
    resized = layout.resize(obj, delta, rendered, handle)
    assert _model_frame(resized) == pytest.approx(expected, abs=0.002)
    assert resized.w_mm / resized.h_mm == pytest.approx(2)


def test_resize_image_edge_with_keep_ratio_scales_uniformly_around_centre():
    obj = _picture()
    rendered = _rendered(10, 5, 20, 10)
    old = layout.object_rect(rendered)
    wider = layout.resize(obj, Rect(old.x, old.y, old.w + 10, old.h), rendered, "r")
    assert _model_frame(wider) == pytest.approx((10, 2.5, 30, 15), abs=0.002)   # Mitte senkrecht
    taller = layout.resize(obj, Rect(old.x, old.y - 5, old.w, old.h + 5), rendered, "t")
    assert _model_frame(taller) == pytest.approx((5, 0, 30, 15), abs=0.002)     # Mitte waagerecht


HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")


def _dragged(rect: Rect, handle: str, amount: float) -> Rect:
    """``rect`` nach Ziehen am Anfasser ``handle`` um ``amount`` mm nach außen."""
    left, top, right, bottom = rect.x, rect.y, rect.right, rect.bottom
    left -= amount if "l" in handle else 0
    right += amount if "r" in handle else 0
    top -= amount if "t" in handle else 0
    bottom += amount if "b" in handle else 0
    return Rect(left, top, right - left, bottom - top)


@pytest.mark.parametrize("handle", HANDLES)
def test_keep_aspect_fixes_what_the_handle_says(handle):
    """Ecke: gegenüberliegende Ecke bleibt; Kante: gegenüberliegende Kante bleibt, quer dazu
    die Mitte – unabhängig davon, welches Maß sich (in Rechenrauschen) mehr geändert hat."""
    old = Rect(10, 20, 40, 20)
    new = layout.keep_aspect(old, _dragged(old, handle, 4), handle)
    assert new.w / new.h == pytest.approx(2)
    assert new.w > old.w
    for edge, opposite in (("l", "right"), ("r", "x"), ("t", "bottom"), ("b", "y")):
        if edge in handle:
            assert getattr(new, opposite) == pytest.approx(getattr(old, opposite))
    if handle in ("t", "b"):
        assert new.cx == pytest.approx(old.cx)
    if handle in ("l", "r"):
        assert new.cy == pytest.approx(old.cy)


def test_keep_aspect_edge_ignores_noise_in_the_other_axis():
    old = Rect(10, 20, 40, 20)
    noisy = Rect(10, 20 - 1e-9, 40 + 1e-12, 26 + 1e-9)       # unten gezogen, quer nur Rauschen
    new = layout.keep_aspect(old, noisy, "b")
    assert (new.y, new.h, new.cx) == pytest.approx((20, 26, old.cx))


@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("handle", HANDLES)
def test_resize_image_result_matches_preview(handle, rotation):
    """Die Vorschau (``keep_aspect`` auf dem gezeigten Rahmen) ist das Ergebnis (±1 Punkt)."""
    obj = _picture(x_mm=20, y_mm=12, rotation=rotation)
    _, rendered = _frame(obj)
    shown = layout.object_rect(rendered)
    preview = layout.keep_aspect(shown, _dragged(shown, handle, 3.3), handle)
    resized = layout.resize(obj, preview, rendered, handle)
    after, _ = _frame(resized)
    for a, b in zip((after.x, after.y, after.right, after.bottom),
                    (preview.x, preview.y, preview.right, preview.bottom)):
        assert a == pytest.approx(b, abs=DOT_MM * 1.01)


@pytest.mark.parametrize("handle", ["br", "r"])
def test_resize_image_without_keep_ratio_distorts(handle):
    obj = _picture(keep_ratio=False)
    rendered = _rendered(10, 5, 20, 10)
    old = layout.object_rect(rendered)
    resized = layout.resize(obj, Rect(old.x, old.y, old.w + 10, old.h), rendered, handle)
    assert _model_frame(resized) == pytest.approx((10, 5, 30, 10), abs=0.002)


@pytest.mark.parametrize("degrees, end", [(90, 90), (-90, 270)])
def test_rotate_image_keeps_centre(degrees, end):
    obj = _picture(x_mm=10, y_mm=10)
    before, rendered = _frame(obj)
    turned = layout.rotate(obj, rendered, degrees)
    after, _ = _frame(turned)
    assert turned.rotation == end and (turned.w_mm, turned.h_mm) == (20, 10)
    assert (after.w, after.h) == pytest.approx((10, 20), abs=0.1)
    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=0.1)


def _text_and_image():
    return [TextObject("Text", size_pt=12, x_mm=4, y_mm=4), _picture(x_mm=20, y_mm=12),
            TextObject("Rahmen", size_pt=12, fit=True, x_mm=7, y_mm=25, w_mm=20, h_mm=6)]


@pytest.mark.parametrize("mode, attr", [("left", "x"), ("right", "right"), ("vcenter", "cy")])
def test_align_mixed_text_and_images(mode, attr):
    objs = _text_and_image()
    aligned = layout.align_objects(objs, _rendered_of(objs), mode)
    rects = [layout.exact_rect(o, r) for o, r in zip(aligned, _rendered_of(aligned))]
    assert len({round(getattr(r, attr), 1) for r in rects}) == 1
    assert (aligned[1].w_mm, aligned[1].h_mm) == (20, 10)


def test_match_size_image_to_text_keeps_image_ratio():
    objs = [TextObject("Rahmen", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=30, h_mm=6),
            _picture(x_mm=5, y_mm=20)]
    rendered = _rendered_of(objs)
    # Breite × 1,5, Höhe × 0,6; „gleiche Größe“: Mittel aus beiden Faktoren
    for mode, width in (("width", 30), ("height", 12), ("same", 20 * (1.5 * 0.6) ** 0.5)):
        _, image = layout.match_objects(objs, rendered, mode)
        assert (image.x_mm, image.y_mm) == (5, 20)              # Ecke bleibt
        assert (image.w_mm, image.h_mm) == pytest.approx((width, width / 2), abs=0.002)


def test_match_size_image_without_keep_ratio_takes_frame():
    objs = [TextObject("Rahmen", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=30, h_mm=6),
            _picture(x_mm=5, y_mm=20, keep_ratio=False)]
    _, image = layout.match_objects(objs, _rendered_of(objs), "same")
    assert _model_frame(image) == (5, 20, 30, 6)


def test_match_size_text_to_image_scales_text():
    objs = [_picture(x_mm=1, y_mm=1, w_mm=40, h_mm=20),
            TextObject("Wort", size_pt=10, x_mm=5, y_mm=30)]
    ref, text = layout.match_objects(objs, _rendered_of(objs), "width")
    assert ref is objs[0] and text.size_pt > 10 and not text.fit


@pytest.mark.parametrize("keep_ratio", [True, False])
def test_maximize_image_fills_area_centred(keep_ratio):
    obj = _picture(keep_ratio=keep_ratio)
    doc = Document("62", length_mm=40, objects=[obj])
    area = layout.printable_area(doc)
    big = layout.maximize_object(obj, render_object(obj, doc), area, doc)
    assert big.w_mm / big.h_mm == pytest.approx(2)
    assert big.w_mm == pytest.approx(area.w, abs=0.002)
    assert (big.x_mm + big.w_mm / 2, big.y_mm + big.h_mm / 2) == \
        pytest.approx((area.cx, area.cy), abs=0.002)


def test_outside_counts_images():
    doc = Document("62", length_mm=40, objects=[TextObject("A", size_pt=12, x_mm=2, y_mm=2),
                                                _picture(x_mm=50, y_mm=5)])
    assert layout.objects_outside(doc) == [1]


def test_to_grid_rounds_image_frame():
    obj = layout.to_grid(_picture(x_mm=1.234, w_mm=20.06), x=True, w=True)
    assert (obj.x_mm, obj.w_mm) == (1.2, 20.1)


def test_text_only_helpers_refuse_images():
    obj = _picture()
    rendered = _rendered(10, 5, 20, 10)
    for call in (lambda: layout.scale_text(obj, 2), lambda: layout.fix_size(obj, 12),
                 lambda: layout.anchor_after_edit(obj, rendered, rendered),
                 lambda: layout.anchor_align(obj)):
        with pytest.raises(TypeError, match="Text"):
            call()


# --- Serien: Ankerpunkt beim Füllen ---------------------------------------------------------------
@pytest.mark.parametrize("align, edge", [("center", "cx"), ("right", "right"), ("left", "x")])
def test_filled_text_keeps_its_anchor(align, edge):
    from labelwerk.document import Paragraph, Span
    obj = TextObject([Paragraph([Span("{A}")], align)], size_pt=14, x_mm=20, y_mm=5)
    doc = Document("62x29", objects=[obj])
    raw = layout.object_rect(render_object(obj, doc))
    for value in ("X1", "X1 -K3 Klemme 24V"):
        filled = layout.fill_anchored(doc, ["A"], [value])
        rect = layout.object_rect(render_object(filled.objects[0], filled))
        assert getattr(rect, edge) == pytest.approx(getattr(raw, edge), abs=0.2), value
    assert (obj.x_mm, obj.y_mm) == (20, 5)                 # das Etikett selbst bleibt


def test_fill_anchored_leaves_fixed_frames_and_unpositioned_text():
    fixed = TextObject("{A}", size_pt=14, fit=True, x_mm=2, y_mm=2, w_mm=30, h_mm=10)
    centred = TextObject("{A}", size_pt=14)
    doc = Document("62x29", objects=[fixed, centred])
    filled = layout.fill_anchored(doc, ["A"], ["lang lang"])
    assert (filled.objects[0].x_mm, filled.objects[0].y_mm) == (2, 2)
    assert filled.objects[1].x_mm is None
