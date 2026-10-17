"""Zeilensatz als TextLayout: Schreibmarke, Treffer, Markierung, Anker beim Wachsen (Etappe 3d-1b)."""
import copy
import math
from dataclasses import replace

import pytest

from labelwerk import fonts, layout
from labelwerk.document import ROTATIONS, Document, Paragraph, Span, TextObject
from labelwerk.render import (RenderedObject, from_utf16, render_object, text_layout,
                              to_utf16)

DEJAVU_BOLD = fonts.resolve(None, True, False).path
_TOL = 2           # Druckpunkte: Kantenglättung, Neigung der Kursiven knapp über der Grundlinie
_BAND = (8, 2)     # Tintenband über der Grundlinie: von 8 bis 2 Punkte darüber

# Nur Buchstaben, deren Tinte knapp über der Grundlinie genau ein zusammenhängendes Stück
# ist (E, L, T, I, Z) – so lässt sich jedes Zeichen im Druckbild wiederfinden; keine stark
# unterschnittenen Paare wie „LT“ (dort reicht der Fuß des „L“ unter das „T“ – die Schreibmarke
# steht wie in Qt am Ursprung des „T“, also über dem Fuß)
_MIXED = TextObject([
    Paragraph([Span("EL", size_pt=10), Span("TI", size_pt=30, italic=True),
               Span("ZE", bold=False)], "left"),
    Paragraph([Span("LITEZ ELITE ZIEL", underline=True)], "right"),
    Paragraph([], "center"),
    Paragraph([Span("EL TI  ZE"), Span("IE", size_pt=14)], "justify"),
    Paragraph([Span("ZIEL", italic=True)], "center"),
], size_pt=12, x_mm=3, y_mm=4)
_SLANTED = TextObject([Paragraph([Span("EL"), Span("TIZE", italic=True), Span("LE")], "left")],
                      size_pt=24, font_path=DEJAVU_BOLD, x_mm=2, y_mm=2)
_FRAMED = TextObject([Paragraph([Span("ZIEL")], "left"), Paragraph([Span("LE")], "right")],
                     size_pt=12, fit=True, x_mm=2, y_mm=2, w_mm=40, h_mm=15)
_CASES = {
    "gemischt": Document("62", length_mm=80, objects=[_MIXED]),
    "Ersatzkursive": Document("62", length_mm=60, objects=[_SLANTED]),
    "fester Rahmen": Document("62", length_mm=60, objects=[_FRAMED]),
    "ohne Position": Document("62", objects=[TextObject.plain("ZIEL\nELITE LZ", align="right")]),
    "ohne Position, längs": Document("29", orientation="horizontal",
                                     objects=[TextObject.plain("LITE\nZE", align="left")]),
}


def _ink(rendered: RenderedObject):
    return rendered.image.point(lambda v: 255 if v < 128 else 0)


def _band_pieces(ink, top: int, bottom: int) -> list[tuple[int, int]]:
    """Zusammenhängende Tintenstücke (links, rechts) in den Pixelzeilen ``top``..``bottom``."""
    band = ink.crop((0, top, ink.width, bottom))
    pieces: list[list[int]] = []
    for x in range(band.width):
        if band.crop((x, 0, x + 1, band.height)).getbbox() is None:
            continue
        if pieces and pieces[-1][1] == x:
            pieces[-1][1] = x + 1
        else:
            pieces.append([x, x + 1])
    return [tuple(p) for p in pieces]


def _plain(text: str, size_pt: float = 12, align: str = "center", **placement) -> TextObject:
    """Reiner Text mit Position, Drehung … (``TextObject.plain`` kennt keine Platzierung)."""
    return replace(TextObject.plain(text, size_pt=size_pt, align=align), **placement)


def _positions(obj: TextObject) -> int:
    """Anzahl der Positionen (Zeichen + Absatzwechsel + Ende)."""
    return len(obj.text) + 1


# --- Schreibmarke im echten Druckbild ------------------------------------------------
@pytest.mark.parametrize("name", _CASES)
def test_caret_lies_between_ink_of_neighbouring_characters(name):
    doc = _CASES[name]
    obj = doc.objects[0]
    rendered = render_object(obj, doc)
    text = text_layout(obj, doc)
    ink = _ink(rendered)
    dx, dy = rendered.image_dx, rendered.image_dy      # Bild liegt bei Rahmen + (dx, dy)
    start = 0
    for line, para in zip(text.lines, obj.paragraphs):
        chars = para.text
        carets = [text.caret(start + j) for j in range(len(chars) + 1)]
        xs = [x for x, _, _ in carets]
        assert xs == sorted(xs)
        inked = [j for j, c in enumerate(chars) if c != " "]
        if inked:
            row = round(line.baseline) - dy
            pieces = _band_pieces(ink, row - _BAND[0], row - _BAND[1])
            assert len(pieces) == len(inked), f"Zeile {chars!r}"
            left = {j: p[0] + dx for j, p in zip(inked, pieces)}       # in Rahmenkoordinaten
            right = {j: p[1] + dx for j, p in zip(inked, pieces)}
            for j, (x, y, h) in enumerate(carets):
                before = [right[k] for k in inked if k < j]
                after = [left[k] for k in inked if k >= j]
                if before:
                    assert x >= before[-1] - _TOL, f"Position {j} in {chars!r}"
                if after:
                    assert x <= after[0] + _TOL, f"Position {j} in {chars!r}"
                assert y <= line.baseline - _BAND[0] and y + h >= line.baseline
        start += len(chars) + 1


def test_caret_follows_kerning_under_the_t():
    obj = _plain("To", size_pt=40, align="left", x_mm=2, y_mm=2)
    doc = Document("62", length_mm=80, objects=[obj])
    rendered, text = render_object(obj, doc), text_layout(obj, doc)
    row = round(text.lines[0].baseline) - rendered.image_dy
    # halbe x-Höhe: Stamm des „T“, dann linke und rechte Seite des „o“ (unter dem Dach)
    stem, bowl, _ = _band_pieces(_ink(rendered), row - 50, row - 40)
    x = text.caret(1)[0] - rendered.image_dx
    assert stem[1] - _TOL <= x <= bowl[0] + _TOL


def test_caret_follows_kerning_at_the_top_of_av():
    obj = _plain("AV", size_pt=60, align="left", x_mm=2, y_mm=2)
    doc = Document("62", length_mm=80, objects=[obj])
    rendered, text = render_object(obj, doc), text_layout(obj, doc)
    ink = _ink(rendered)
    top = ink.getbbox()[1]
    # oben: Spitze des „A“, dann die beiden Arme des „V“ – das „V“ beginnt über dem „A“
    apex, arm, _ = _band_pieces(ink, top + 2, top + 8)
    x = text.caret(1)[0] - rendered.image_dx
    assert apex[1] - _TOL <= x <= arm[0] + _TOL
    assert text.caret(2)[0] == pytest.approx(text.lines[0].stops[-1])


def test_rendered_object_carries_the_same_layout():
    doc = _CASES["gemischt"]
    obj = doc.objects[0]
    rendered, text = render_object(obj, doc), text_layout(obj, doc)
    assert [rendered.layout.caret(p) for p in range(_positions(obj))] == \
        [text.caret(p) for p in range(_positions(obj))]
    assert (text.width, text.height) == (rendered.w, rendered.h)


def test_layout_size_is_unrotated_frame():
    obj = copy.deepcopy(_MIXED)
    obj.rotation = 90
    doc = Document("62", length_mm=80, objects=[obj])
    rendered, text = render_object(obj, doc), text_layout(obj, doc)
    assert (text.width, text.height) == (rendered.h, rendered.w)


# --- Treffer --------------------------------------------------------------------------
@pytest.mark.parametrize("name", _CASES)
def test_hit_on_caret_gives_its_position(name):
    doc = _CASES[name]
    text = text_layout(doc.objects[0], doc)
    for pos in range(_positions(doc.objects[0])):
        x, y, h = text.caret(pos)
        assert text.hit(x, y + h / 2) == pos


def test_hit_beside_and_beyond_the_text():
    obj = _plain("ZIEL\nLE\nTEIL", size_pt=12, align="center", x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    _, y, h = text.caret(5)                        # zweite Zeile „LE“: Positionen 5..7
    assert text.hit(-1000, y + h / 2) == 5         # links daneben → Zeilenanfang
    assert text.hit(10_000, y + h / 2) == 7        # rechts daneben → Zeilenende
    x0 = text.caret(1)[0]
    assert text.hit(x0, -1000) == 1                # darüber → erste Zeile
    assert text.hit(text.caret(9)[0], 10_000) == 9  # darunter → letzte Zeile


def test_hit_picks_nearest_character_boundary():
    obj = _plain("EL", size_pt=20, align="left", x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    (x0, y, h), (x1, _, _) = text.caret(0), text.caret(1)
    assert text.hit(x0 + (x1 - x0) * 0.4, y + h / 2) == 0
    assert text.hit(x0 + (x1 - x0) * 0.6, y + h / 2) == 1


def test_hit_skips_positions_inside_a_character_cluster():
    obj = _plain("e\u0301x", size_pt=20, align="left", x_mm=2, y_mm=2)   # „é“ zerlegt
    text = text_layout(obj, Document("62", objects=[obj]))
    x, y, h = text.caret(1)
    assert x == text.caret(2)[0]                   # Akzent hat keine eigene Breite
    assert text.hit(x, y + h / 2) == 2             # hinter dem ganzen „é“


def test_caret_positions_are_clamped():
    obj = _plain("EL", size_pt=20, x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    assert text.caret(-5) == text.caret(0) and text.caret(99) == text.caret(2)


# --- Leerer Absatz, leerer Rahmen -------------------------------------------------------
@pytest.mark.parametrize("align", ["left", "center", "right", "justify"])
def test_empty_paragraph_caret_follows_alignment(align):
    obj = TextObject([Paragraph([Span("ZIELE", size_pt=30)], align), Paragraph([], align),
                      Paragraph([Span("Z")], align)], size_pt=12, x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    first, end, empty = text.caret(0), text.caret(5), text.caret(6)
    expected = {"left": first[0], "justify": first[0], "right": end[0],
                "center": (first[0] + end[0]) / 2}[align]
    assert empty[0] == pytest.approx(expected, abs=0.5)
    assert empty[1] > first[1] + first[2] / 2           # unter der ersten Zeile
    assert empty[2] == pytest.approx(text.caret(7)[2])  # Höhe der Grundgröße, nicht 30 pt
    assert empty[2] < first[2] / 2


@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_empty_object_caret_at_frame(align):
    obj = _plain("", size_pt=12, align=align, x_mm=5, y_mm=5)
    doc = Document("62", objects=[obj])
    text, rendered = text_layout(obj, doc), render_object(obj, doc)
    x, y, h = text.caret(0)
    assert (rendered.w, rendered.h) == (text.width, text.height)
    assert x == pytest.approx(0, abs=0.5) and y == pytest.approx(0, abs=1)
    assert h == pytest.approx(text_layout(_plain("E", size_pt=12, x_mm=5, y_mm=5),
                                          doc).caret(0)[2])
    assert text.hit(30, 30) == 0 and text.selection_rects(0, 0) == []


# --- Ausrichtung ------------------------------------------------------------------
def _two_lines(align):
    obj = _plain("ZIEL\nLE ZIELTEIL", size_pt=12, align=align, x_mm=2, y_mm=2)
    return text_layout(obj, Document("62", objects=[obj]))


def test_left_lines_start_together():
    text = _two_lines("left")
    assert text.caret(0)[0] == pytest.approx(text.caret(5)[0])


def test_right_lines_end_together():
    text = _two_lines("right")
    assert text.caret(4)[0] == pytest.approx(text.caret(16)[0], abs=0.5)
    assert text.caret(0)[0] > text.caret(5)[0] + 50


def test_centered_lines_share_middle():
    text = _two_lines("center")
    assert (text.caret(0)[0] + text.caret(4)[0]) / 2 == \
        pytest.approx((text.caret(5)[0] + text.caret(16)[0]) / 2, abs=0.5)


def test_justify_stretches_gaps_evenly_to_block_width():
    obj = TextObject([Paragraph([Span("EL TI  ZE"), Span("LT", size_pt=14)], "justify"),
                      Paragraph([Span("LITEZ ELITE ZIELE LITE")], "left")], size_pt=12,
                     x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    # Leerzeichen bei 2, 5, 6: Schreibmarke davor und danach – der gedehnte Abstand
    gaps = [text.caret(p + 1)[0] - text.caret(p)[0] for p in (2, 5, 6)]
    space = fonts.load(DEJAVU_BOLD, round(12 * 300 / 72)).getlength(" ")
    assert gaps[0] == pytest.approx(gaps[1]) == pytest.approx(gaps[2])
    assert gaps[0] > 2 * space
    assert text.caret(11)[0] == pytest.approx(text.caret(34)[0], abs=1)   # füllt die Blockbreite


def test_mixed_sizes_share_baseline_and_caret_heights_scale():
    obj = TextObject([Paragraph([Span("E", size_pt=10), Span("E", size_pt=30)], "left")],
                     size_pt=20, x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    (_, y_small, h_small), (_, y_big, h_big) = text.caret(1), text.caret(2)
    assert h_big / h_small == pytest.approx(3, rel=0.1)
    assert y_small > y_big
    baseline = text.lines[0].baseline
    assert y_big < y_small < baseline < y_small + h_small < y_big + h_big


def test_caret_at_paragraph_start_uses_first_character_else_character_before():
    obj = TextObject([Paragraph([Span("E", size_pt=10), Span("E", size_pt=30)], "left")],
                     size_pt=20, x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    assert text.caret(0)[2] == text.caret(1)[2] < text.caret(2)[2]


def test_line_boxes_span_from_stop_to_stop():
    obj = TextObject([Paragraph([Span("EL TI  ZE")], "justify"),
                      Paragraph([Span("LITEZ ELITE ZIELE")], "left")], size_pt=12, x_mm=2, y_mm=2)
    line = text_layout(obj, Document("62", objects=[obj])).lines[0]
    boxes = line.boxes()
    assert len(boxes) == len("EL TI  ZE") == line.end - line.start
    assert boxes == [(a, b) for a, b in zip(line.stops, line.stops[1:])]
    assert boxes[2][1] - boxes[2][0] == pytest.approx(boxes[5][1] - boxes[5][0])   # gedehnte Lücken


# --- Positionen wie Qt (UTF-16) ----------------------------------------------------
_EMOJI = "a\U0001F600b\nc"      # 😀 außerhalb der BMP: in UTF-16 zwei Einheiten


@pytest.mark.parametrize("pos, pos16", [(0, 0), (1, 1), (2, 3), (3, 4), (4, 5), (5, 6)])
def test_utf16_positions(pos, pos16):
    assert to_utf16(_EMOJI, pos) == pos16
    assert from_utf16(_EMOJI, pos16) == pos


def test_utf16_position_inside_surrogate_pair_is_before_the_character():
    assert from_utf16(_EMOJI, 2) == 1
    assert from_utf16(_EMOJI, 99) == len(_EMOJI) and to_utf16("ab", 9) == 2


# --- Markierung ---------------------------------------------------------------------
def test_selection_within_one_line():
    text = _two_lines("left")
    (x1, _, _), (x2, _, _) = text.caret(6), text.caret(9)
    line = text.lines[1]
    assert text.selection_rects(6, 9) == [pytest.approx((x1, line.top, x2 - x1, line.height))]
    assert text.selection_rects(9, 6) == text.selection_rects(6, 9)
    assert text.selection_rects(7, 7) == []


def test_selection_over_lines_and_empty_paragraph():
    obj = TextObject([Paragraph([Span("ZIEL")], "left"), Paragraph([], "left"),
                      Paragraph([Span("LE")], "left")], size_pt=12, x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    rects = text.selection_rects(2, 7)             # „EL“, Wechsel, leerer Absatz, Wechsel, „L“
    assert len(rects) == 3
    first, empty, last = rects
    assert first[0] == pytest.approx(text.caret(2)[0])
    assert first[2] > text.caret(4)[0] - text.caret(2)[0]     # Absatzwechsel mitmarkiert
    assert empty[2] > 0                                         # leerer Absatz sichtbar
    assert last[0] == pytest.approx(text.caret(6)[0])
    assert last[2] == pytest.approx(text.caret(7)[0] - text.caret(6)[0])
    assert [r[1] for r in rects] == [line.top for line in text.lines]
    # Markierung endet am Zeilenende (vor dem Wechsel): kein Rechteck für die nächste Zeile
    assert len(text.selection_rects(0, 4)) == 1


# --- Etikett ↔ Objekt -------------------------------------------------------------
def test_object_coordinates_for_quarter_turn():
    rendered = RenderedObject(None, 100, 200, 30, 50, 12.0)     # ungedreht 50 × 30
    assert layout.from_object((0, 0), rendered, 90) == pytest.approx((130, 200))
    assert layout.from_object((50, 0), rendered, 90) == pytest.approx((130, 250))
    assert layout.from_object((0, 30), rendered, 90) == pytest.approx((100, 200))
    assert layout.from_object((0, 0), rendered, 270) == pytest.approx((100, 250))
    assert layout.from_object((0, 0), rendered, 180) == pytest.approx((130, 250))
    assert layout.to_object((130, 250), rendered, 90) == pytest.approx((50, 0))


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_object_coordinates_round_trip(rotation):
    rendered = RenderedObject(None, 100, 200, 30, 50, 12.0)
    for point in [(0, 0), (12.5, 3.25), (29, 49), (-4, 70)]:
        there = layout.from_object(point, rendered, rotation)
        assert layout.to_object(there, rendered, rotation) == pytest.approx(point)


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_object_coordinates_follow_the_rotated_image(rotation):
    obj = TextObject([Paragraph([Span("Ziel", size_pt=10), Span("EL", italic=True)], "left"),
                      Paragraph([Span("xy", underline=True)], "right")],
                     size_pt=16, x_mm=4, y_mm=3, rotation=rotation)
    flat_obj = copy.deepcopy(obj)
    flat_obj.rotation = 0
    flat = render_object(flat_obj, Document("62", length_mm=50, objects=[flat_obj]))
    turned = render_object(obj, Document("62", length_mm=50, objects=[obj]))
    for iy in range(flat.image.height):
        for ix in range(flat.image.width):
            u, v = ix + flat.image_dx + 0.5, iy + flat.image_dy + 0.5   # Pixelmitte
            lx, ly = layout.from_object((u, v), turned, rotation)
            jx = math.floor(lx - turned.x - turned.image_dx)
            jy = math.floor(ly - turned.y - turned.image_dy)
            assert turned.image.getpixel((jx, jy)) == flat.image.getpixel((ix, iy))


def test_invalid_rotation_for_object_coordinates():
    with pytest.raises(ValueError, match="Drehung"):
        layout.to_object((0, 0), RenderedObject(None, 0, 0, 1, 1, 12.0), 45)


# --- Anker beim Wachsen ----------------------------------------------------------
_EDITS = [                                     # nacheinander getippt
    ["ace", "nun ice"],
    ["hace", "nun ice"],                       # Oberlänge
    ["hacegy", "nun ice"],                     # Unterlänge am Ende
    ["hacegy", "jnun ice"],                    # „j“ am Zeilenanfang (ragt nach links)
    ["hacegy", "jnun ice ende"],               # mehr Text am Ende
]


def _edge(text, align):
    """Bezugspunkt in Objektkoordinaten, unabhängig von ``TextLayout.anchor``: Ausrichtungs-
    kante der ersten Zeile auf ihrer Grundlinie."""
    line = text.lines[0]
    x = {"left": line.stops[0], "justify": line.stops[0], "right": line.stops[-1],
         "center": (line.stops[0] + line.stops[-1]) / 2}[align]
    return x, line.baseline


@pytest.mark.parametrize("rotation", ROTATIONS)
@pytest.mark.parametrize("align", ["left", "center", "right", "justify"])
def test_text_stays_in_place_while_typing(align, rotation):
    def build(paras):
        # Zeile 1 ist immer die breiteste: ihre Kante ist die des Blocks
        return TextObject([Paragraph([Span(t)], align) for t in paras], size_pt=20,
                          x_mm=20, y_mm=15, rotation=rotation)

    doc = Document("62", length_mm=100)
    obj = build(_EDITS[0])
    old = render_object(obj, doc)
    fixed = layout.from_object(_edge(old.layout, align), old, rotation)
    for paras in _EDITS[1:]:
        edited = replace(build(paras), x_mm=obj.x_mm, y_mm=obj.y_mm)
        edited.x_mm, edited.y_mm = layout.anchor_after_edit(edited, old,
                                                            render_object(edited, doc))
        obj, old = edited, render_object(edited, doc)
        assert layout.from_object(_edge(old.layout, align), old, rotation) == \
            pytest.approx(fixed, abs=1), paras


def test_anchor_for_quarter_turn_keeps_top_right_of_left_text():
    obj = _plain("ace", size_pt=20, align="left", x_mm=20, y_mm=15, rotation=90)
    doc = Document("62", length_mm=100)
    old = render_object(obj, doc)
    edited = replace(obj, paragraphs=TextObject.plain("ace\nzweite Zeile", align="left").paragraphs)
    new = render_object(edited, doc)
    x, y = layout.anchor_after_edit(edited, old, new)
    # gedreht: Textoberkante rechts, Zeilenanfang oben – neue Zeilen wachsen nach links
    assert x < obj.x_mm - 3 and y == pytest.approx(obj.y_mm, abs=0.2)


def test_layout_anchor_is_block_edge_on_first_ascender_line():
    obj = TextObject([Paragraph([Span("kurz")], "right"), Paragraph([Span("viel laenger")], "right")],
                     size_pt=12, x_mm=2, y_mm=2)
    text = text_layout(obj, Document("62", objects=[obj]))
    widest = text.lines[1]
    assert text.anchor("right") == pytest.approx((widest.stops[-1], text.lines[0].top))
    assert text.anchor("left") == pytest.approx((widest.stops[0], text.lines[0].top))
    assert text.anchor("center")[0] == pytest.approx((widest.stops[0] + widest.stops[-1]) / 2)
    with pytest.raises(ValueError, match="Textposition"):
        text.anchor("middle")


@pytest.mark.parametrize("aligns, expected", [
    (["center", "center"], "center"), (["right"], "right"), (["justify"], "justify"),
    (["center", "right"], "left"), ([], "left"),
])
def test_anchor_align_of_object(aligns, expected):
    obj = TextObject([Paragraph([Span("A")], a) for a in aligns])
    assert layout.anchor_align(obj) == expected
