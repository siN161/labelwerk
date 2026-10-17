"""Platzier-Logik ohne Qt: Einrasten, Ausrichten, Größe angleichen, Skalieren (Etappe 3d-1)."""
import pytest

from labelwerk import layout
from labelwerk.document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
from labelwerk.labels import DPI
from labelwerk.layout import Rect, Snap
from labelwerk.render import MARGIN, RenderedObject, render_document, render_object


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
    assert _t(area) == _approx(Rect(_mm(MARGIN), feed, label.w - 2 * _mm(MARGIN),
                                      label.h - 2 * feed))


def test_printable_area_horizontal_swaps_margins():
    doc = Document("62x29", margin_mm=2, orientation="horizontal")
    label = layout.label_rect(doc)
    feed = _mm(round(2 * DPI / 25.4))
    area = layout.printable_area(doc)
    assert _t(area) == _approx(Rect(feed, _mm(MARGIN), label.w - 2 * feed,
                                      label.h - 2 * _mm(MARGIN)))


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
    # Größen außerhalb 4–100 (z. B. von Hand bearbeitet): jede Größe für sich begrenzt
    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=100)])], size_pt=2)
    assert _sizes(layout.scale_text(obj, 1.5)) == (MIN_PT, [None, MAX_PT])


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
