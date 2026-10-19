"""Zierrahmen ums Etikett: Arten, Lage im bedruckbaren Bereich, Innenraum, runde Etiketten."""
import pytest

from labelwerk import layout
from labelwerk.document import FRAME_STYLES, Document, Frame, TextObject
from labelwerk.render import Renderer, frame_box, label_size, render_document

# 62x29 senkrecht: 696 × 271 Punkte; Rand 4 mm ab Papierkante (_image), davon liegen quer 18 und
# längs 35 Punkte im unbedruckbaren Streifen → Ränder 29 (quer) und 12 (längs) –
# Außenkante des Rahmens: x 29 … 666, y 12 … 258; 0,5 mm = 6 Punkte
LEFT, TOP, RIGHT, BOTTOM = 29, 12, 666, 258
LW = 6


def _image(frame, label="62x29", objects=None, **kw):
    kw.setdefault("margin_mm", 4.0)
    return render_document(Document(label, objects=objects or [], frame=frame, **kw))


def _black(img, x, y) -> bool:
    return img.getpixel((x, y))[0] == 0


def _row(img, y, x0, x1) -> list[bool]:
    return [_black(img, x, y) for x in range(x0, x1)]


def _runs(values: list[bool]) -> int:
    """Anzahl schwarzer Abschnitte."""
    return sum(1 for i, v in enumerate(values) if v and (i == 0 or not values[i - 1]))


def test_without_frame_the_label_stays_white():
    assert _image(None).getextrema() == ((255, 255),) * 3


def test_single_frame_lies_on_the_printable_edge():
    img = _image(Frame("single"))
    for x in (LEFT, LEFT + LW - 1, RIGHT - LW + 1, RIGHT):
        assert _black(img, x, 130)
    for x in (LEFT - 1, LEFT + LW, RIGHT - LW, RIGHT + 1):
        assert not _black(img, x, 130)
    for y in (TOP, TOP + LW - 1, BOTTOM - LW + 1, BOTTOM):
        assert _black(img, 300, y)
    for y in (TOP - 1, TOP + LW, BOTTOM - LW, BOTTOM + 1):
        assert not _black(img, 300, y)


def test_inset_moves_the_frame_inwards():
    img = _image(Frame("single", inset_mm=2))          # 24 Punkte
    assert not _black(img, LEFT + 23, 130) and _black(img, LEFT + 24, 130)


def test_line_width_follows_line_mm():
    img = _image(Frame("single", line_mm=1))           # 12 Punkte
    assert _black(img, LEFT + 11, 130) and not _black(img, LEFT + 12, 130)
    thin = _image(Frame("single", line_mm=0.1))        # 1 Punkt
    assert _black(thin, LEFT, 130) and not _black(thin, LEFT + 1, 130)


def test_double_frame_has_two_lines_with_a_gap():
    img = _image(Frame("double"))
    assert _row(img, 130, LEFT, LEFT + 3 * LW + 1) == [True] * LW + [False] * LW + [True] * LW + [False]


def test_thick_thin_frame_is_thick_outside():
    img = _image(Frame("thick_thin"))
    assert _row(img, 130, LEFT, LEFT + 4 * LW + 1) == ([True] * 2 * LW + [False] * LW + [True] * LW
                                                        + [False])


@pytest.mark.parametrize("style", ["dashed", "dotted"])
def test_dashed_and_dotted_frames_are_interrupted_lines_on_the_band(style):
    img = _image(Frame(style))
    top = _row(img, TOP + LW // 2, LEFT, RIGHT + 1)
    assert _runs(top) >= 20 and not all(top)
    assert _black(img, LEFT + LW // 2, TOP + LW // 2)            # Ecke ist besetzt
    inner = img.crop((LEFT + LW, TOP + LW, RIGHT - LW + 1, BOTTOM - LW + 1))
    assert inner.getextrema() == ((255, 255),) * 3                # nichts innerhalb der Linie
    outside = [_black(img, x, TOP - 1) for x in range(0, 696)]
    assert not any(outside)


def test_dashes_are_longer_than_dots():
    dashed = _row(_image(Frame("dashed")), TOP + LW // 2, LEFT, RIGHT + 1)
    dotted = _row(_image(Frame("dotted")), TOP + LW // 2, LEFT, RIGHT + 1)
    assert sum(dashed) > sum(dotted)
    assert _runs(dotted) > _runs(dashed)


def test_corners_frame_only_draws_the_corners():
    img = _image(Frame("corners"))                     # Schenkel 4 mm = 47 Punkte
    assert _black(img, LEFT, TOP + 46) and not _black(img, LEFT, TOP + 47)
    assert _black(img, LEFT + 46, TOP) and not _black(img, LEFT + 47, TOP)
    assert not _black(img, LEFT, 130) and not _black(img, 300, TOP)
    assert _black(img, RIGHT, BOTTOM) and _black(img, RIGHT, TOP) and _black(img, LEFT, BOTTOM)


def test_corner_legs_are_at_most_a_quarter_of_the_shorter_side():
    img = _image(Frame("corners"), label="23x23")      # 202 × 202, Ränder 12, Rahmen 178 → Schenkel 44
    assert _black(img, 12, 12 + 43) and not _black(img, 12, 12 + 44)


@pytest.mark.parametrize("style", ["single", "double", "thick_thin", "dashed", "dotted", "corners"])
def test_rounded_frames_leave_the_corner_free(style):
    img = _image(Frame(style, rounded=True))           # Eckradius 2 mm = 24 Punkte
    assert not _black(img, LEFT, TOP) and not _black(img, LEFT + 2, TOP + 2)
    assert any(_black(img, x, y) for x in range(LEFT, LEFT + LW) for y in range(TOP + 24, TOP + 60))


def test_round_label_gets_a_circle():
    img = _image(Frame("single"), label="d24", margin_mm=3.05)   # 236 × 236, Ränder 36 − 24 = 12
    assert _black(img, 12, 118) and _black(img, 118, 12) and _black(img, 223, 118)
    assert not _black(img, 30, 30)                     # Ecke außerhalb des Kreises
    assert not _black(img, 118, 118)


@pytest.mark.parametrize("style", ["corners", "dashed"])
def test_round_label_ignores_corners_and_rounding(style):
    rounded = _image(Frame(style, rounded=True), label="d24")
    plain = _image(Frame("single" if style == "corners" else style), label="d24")
    assert rounded.tobytes() == plain.tobytes()


def test_auto_length_grows_by_the_frame():
    text = [TextObject("Hallo\nWelt\nZeile drei", size_pt=20)]     # feste Größe: nur der Rahmen zählt
    plain = label_size(Document("62", objects=text))
    framed = label_size(Document("62", objects=text, frame=Frame("single")))
    assert framed == (plain[0], plain[1] + 2 * (LW + 12))        # Linie + 1 mm Innenabstand
    img = _image(Frame("single"), label="62", objects=text, margin_mm=1)
    assert _black(img, 300, framed[1] - 1)             # längs liegt 1 mm im Vorschub des Druckers
    img = _image(Frame("single"), label="62", objects=text, margin_mm=4)
    framed = label_size(Document("62", objects=text, frame=Frame("single"), margin_mm=4))
    assert _black(img, 300, framed[1] - 13) and not _black(img, 300, framed[1] - 12)   # 47 − 35


def test_automatic_text_stays_inside_the_frame_and_shrinks():
    objects = [TextObject("WWWWWWWWWWWWWWWWWWWW")]
    plain = Renderer().render(Document("62x29", objects=objects))
    framed = Renderer().render(Document("62x29", objects=objects, frame=Frame("single")))
    assert framed.objects[0].base_pt < plain.objects[0].base_pt
    inner = 12 + LW + 12
    img = framed.image
    for x in list(range(LEFT + LW, inner)) + list(range(696 - inner, RIGHT - LW + 1)):
        assert not any(_black(img, x, y) for y in range(TOP + LW, BOTTOM - LW + 1)), x


def test_text_alignment_starts_at_the_inner_edge():
    """Linksbündig beginnt am Innenraum: Rand + Linie + Innenabstand statt nur am Rand."""
    from labelwerk.document import Paragraph, Span

    def left_ink(frame):
        obj = TextObject([Paragraph([Span("links")], "left")], size_pt=12)
        img = _image(frame, objects=[obj]).convert("L")
        start = LEFT + LW if frame else 0              # mit Rahmen: die Linie nicht mitzählen
        inside = img.crop((start, TOP + LW, RIGHT - LW + 1, BOTTOM - LW + 1))
        return start + inside.point(lambda v: 255 - v).getbbox()[0]
    assert left_ink(Frame("single")) - left_ink(None) == LW + 12


def test_positioned_objects_keep_their_place():
    objects = [TextObject("A", size_pt=12, x_mm=5, y_mm=5)]
    plain = Renderer().render(Document("62x29", objects=objects)).objects[0]
    framed = Renderer().render(Document("62x29", objects=objects, frame=Frame("single"))).objects[0]
    assert (framed.x, framed.y, framed.w, framed.h) == (plain.x, plain.y, plain.w, plain.h)


def test_frame_that_leaves_no_room_gives_a_message():
    with pytest.raises(ValueError, match="Rahmen passt nicht aufs Etikett"):
        _image(Frame("single", inset_mm=10, padding_mm=10), label="d12")


@pytest.mark.parametrize("frame, message", [
    (Frame("wave"), "Unbekannte Rahmenart"),
    (Frame("single", line_mm=5), "Strichstärke"),
    (Frame("single", line_mm=0), "Strichstärke"),
    (Frame("single", inset_mm=-1), "Abstand zum Rand"),
    (Frame("single", padding_mm=11), "Innenabstand"),
    (Frame("single", line_mm=float("nan")), "Strichstärke"),
])
def test_invalid_frames_give_german_messages(frame, message):
    with pytest.raises(ValueError, match=message):
        _image(frame)


@pytest.mark.parametrize("style", FRAME_STYLES)
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_renderer_matches_the_print_image(style, orientation):
    doc = Document("62", objects=[TextObject("Text"), TextObject("B", size_pt=10, x_mm=3, y_mm=2)],
                   orientation=orientation, frame=Frame(style, rounded=True))
    renderer = Renderer()
    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()
    doc.frame = Frame("double", padding_mm=3)
    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()
    doc.frame = None
    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()


def test_frame_box_is_the_inner_room():
    doc = Document("62x29", frame=Frame("single"))     # Rand 1 mm liegt im unbedruckbaren Streifen
    assert frame_box(doc, size=(696, 271)) == (18, 18, 696 - 36, 271 - 36)
    assert frame_box(Document("62x29"), size=(696, 271)) is None
    wide = Document("62x29", orientation="horizontal", margin_mm=3, frame=Frame("double"))
    pad = 3 * LW + 12                                  # Rand 35: längs 35 − 35 = 0, quer 35 − 18 = 17
    assert frame_box(wide, size=(271, 696)) == (pad, 17 + pad, 271 - 2 * pad, 696 - 34 - 2 * pad)


def test_frame_area_in_mm():
    doc = Document("62x29", frame=Frame("single"))
    area = layout.frame_area(doc, size=(696, 271))
    assert area == layout.Rect(18 * 25.4 / 300, 18 * 25.4 / 300, 660 * 25.4 / 300, 235 * 25.4 / 300)
    assert layout.frame_area(Document("62x29"), size=(696, 271)) is None


# --- Nachbesserungen nach dem Review ------------------------------------------------------
def test_dashed_corner_is_filled_to_the_outer_edge():
    img = _image(Frame("dashed", line_mm=2))
    for x, y in ((LEFT, TOP), (RIGHT, TOP), (LEFT, BOTTOM), (RIGHT, BOTTOM)):
        assert _black(img, x, y)


def _lengths_of_runs(values: list[bool]) -> tuple[list[int], list[int]]:
    """Längen der schwarzen und der weißen Abschnitte (ohne den ersten und letzten)."""
    runs, current, length = [], values[0], 0
    for v in values:
        if v == current:
            length += 1
        else:
            runs.append((current, length))
            current, length = v, 1
    runs.append((current, length))
    inner = runs[1:-1]
    return [n for black, n in inner if black], [n for black, n in inner if not black]


def test_dashes_are_three_line_widths_with_gaps_of_two():
    lw = 12                                            # 1 mm
    row = _row(_image(Frame("dashed", line_mm=1)), TOP + lw // 2, LEFT, RIGHT + 1)
    dashes, gaps = _lengths_of_runs(row)
    assert all(abs(n - 3 * lw) <= 3 for n in dashes), dashes      # gleichmäßig auf die Seite
    assert all(abs(n - 2 * lw) <= 3 for n in gaps), gaps          # verteilt


def test_dots_are_two_line_widths_apart():
    lw = 12
    row = _row(_image(Frame("dotted", line_mm=1)), TOP + lw // 2, LEFT, RIGHT + 1)
    starts = [i for i, v in enumerate(row) if v and (i == 0 or not row[i - 1])]
    steps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(abs(step - 2 * lw) <= 1 for step in steps), steps


def _first_black(img, x, y0):
    return next(y for y in range(y0, img.height) if _black(img, x, y))


def test_corner_radius_is_two_millimetres():
    img = _image(Frame("single", rounded=True))        # Radius 24 Punkte, Linie 6
    assert _first_black(img, LEFT, TOP) == TOP + 20    # Bogen trifft die Kante kurz vor 24


def test_corner_radius_is_at_most_a_quarter_of_the_shorter_side():
    doc = Document("12", objects=[TextObject("A", size_pt=6)], frame=Frame("single", rounded=True),
                   margin_mm=2.5)                      # 30 Punkte: quer 30 − 18 = 12, längs 30 − 35
    img = render_document(doc)                         # quer 82 Punkte → Radius 20
    assert _first_black(img, 12, 0) == 16


def test_double_rounded_lines_stay_concentric():
    img = _image(Frame("double", rounded=True))
    diagonal = [_black(img, LEFT + t, TOP + t) for t in range(0, 40)]
    dashes, gaps = _lengths_of_runs([False] + diagonal + [False])
    assert len(dashes) == 2 and 3 <= gaps[0] <= 6, (dashes, gaps)


def test_round_label_inner_room_is_the_square_in_the_circle():
    # Ø 212, Linie 6, Innenabstand 12 → Radius 88 → Quadrat 124
    doc = Document("d24", frame=Frame(), margin_mm=3.05)          # Ränder 36 − 24 = 12
    assert frame_box(doc, size=(236, 236)) == (56, 56, 124, 124)


def test_corners_without_room_give_a_message():
    with pytest.raises(ValueError, match="Rahmen passt nicht aufs Etikett"):
        render_document(Document("62", frame=Frame("corners", inset_mm=6.2, line_mm=0.1,
                                                    padding_mm=0)))


def test_endless_label_keeps_room_inside_the_frame():
    """Leeres Endlosband oder nur frei platzierte Objekte: das Etikett wird lang genug, dass im
    Rahmen Platz bleibt – nie ein negativer Innenraum."""
    for objects in ([], [TextObject("A", size_pt=10, x_mm=2, y_mm=1)]):
        doc = Document("62", objects=objects, frame=Frame("single", inset_mm=10, padding_mm=10,
                                                          line_mm=3))
        size = label_size(doc)
        assert frame_box(doc, size=size)[3] >= 1
        render_document(doc)


def test_frame_check_only_on_the_render_path():
    """Ränder und bedruckbarer Bereich lassen sich auch ohne Platz im Rahmen bestimmen –
    die GUI ruft sie außerhalb des Renderns auf."""
    from labelwerk.render import label_margins
    doc = Document("d12", objects=[TextObject("A")], frame=Frame("single", inset_mm=10))
    assert label_margins(doc) == (0, 0)                # 1 mm liegt im unbedruckbaren Streifen
    assert layout.printable_area(doc, size=(94, 94)).w > 0
    with pytest.raises(ValueError, match="Rahmen passt nicht"):
        Renderer().render(doc)


def test_rounded_must_be_a_bool():
    with pytest.raises(ValueError, match="abgerundet"):
        _image(Frame("single", rounded="ja"))


def test_renderer_follows_padding_on_a_fixed_label():
    """Innenabstand ändert die automatische Schrift auf festem Etikett – derselbe Renderer
    muss neu messen (Rahmen gehört zum Kontext)."""
    doc = Document("62x29", objects=[TextObject("WWWWWWWWWWWWWWWWWWWW")], frame=Frame("single"))
    renderer = Renderer()
    first = renderer.render(doc).objects[0].base_pt
    doc.frame = Frame("single", padding_mm=8)
    result = renderer.render(doc)
    assert result.objects[0].base_pt < first
    assert result.image.tobytes() == render_document(doc).tobytes()


def test_renderer_follows_the_margin_at_the_same_size():
    doc = Document("62x29", objects=[TextObject("A", size_pt=10, x_mm=20, y_mm=10)],
                   frame=Frame("single"))
    renderer = Renderer()
    renderer.render(doc)
    doc.margin_mm = 3
    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()


def test_positioned_fit_object_ignores_the_frame():
    obj = TextObject("Rahmen", fit=True, x_mm=2, y_mm=2)
    plain = Renderer().render(Document("62x29", objects=[obj])).objects[0]
    framed = Renderer().render(Document("62x29", objects=[obj], frame=Frame("double", padding_mm=5))
                               ).objects[0]
    assert (framed.base_pt, framed.w, framed.h) == (plain.base_pt, plain.w, plain.h)
def test_renderer_reports_the_frame_mask():
    from labelwerk.render import frame_mask
    doc = Document("62x29", objects=[TextObject("A")], frame=Frame("double"))
    result = Renderer().render(doc)
    assert result.frame.tobytes() == frame_mask(doc, size=result.size).tobytes()
    assert Renderer().render(Document("62x29")).frame is None


# --- Schlussreview ---------------------------------------------------------------------------
@pytest.mark.parametrize("style", ["single", "double", "thick_thin", "dashed", "dotted", "corners"])
def test_rounded_corners_stay_out_of_the_inner_room(style):
    """Auch ohne Innenabstand reichen die Bögen nicht in den Innenraum (seine Ecken)."""
    from labelwerk.render import frame_mask
    doc = Document("62x29", frame=Frame(style, rounded=True, padding_mm=0))
    x, y, w, h = frame_box(doc, size=(696, 271))
    assert frame_mask(doc, size=(696, 271)).crop((x, y, x + w, y + h)).getbbox() is None


def test_label_with_only_a_frame_is_not_empty():
    assert not Document("62x29", frame=Frame()).is_empty()
    assert Document("62x29").is_empty()
