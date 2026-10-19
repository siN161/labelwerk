"""Zeichenweise Formatierung im Kern (Etappe 3a)."""
import pytest
from PIL import Image, ImageDraw

from labelwerk import fonts
from labelwerk.document import Document, Paragraph, Span, TextObject
from labelwerk.render import TextTooLarge, font_warnings, render_document

DEJAVU_BOLD = fonts.resolve(None, True, False).path


def _ink(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0)


def _old_render(text: str, size: int | None = None) -> Image.Image:
    """Der Algorithmus vor Etappe 3a (Pillow multiline_text, zentriert), Etikett 62 vertikal;
    Rand 1 mm: quer und längs ganz im Streifen, den der Drucker freilässt (kein eigener Rand)."""
    def box(font):
        probe = ImageDraw.Draw(Image.new("1", (1, 1)))
        return tuple(round(v) for v in probe.multiline_textbbox((0, 0), text, font=font,
                                                                 align="center"))

    def fits(s):
        l, t, r, b = box(fonts.load(DEJAVU_BOLD, s))
        return r - l <= 696 and b - t <= 11811     # kein Rand: Drucker lässt 1,5 mm bzw. 3 mm

    start = size or max(10, 696 // 5)
    best = start if fits(start) else max(s for s in range(8, start) if fits(s))
    font = fonts.load(DEJAVU_BOLD, best)
    l, t, r, b = box(font)
    height = min(max(b - t, 150), 11811)
    img = Image.new("RGB", (696, height), "white")
    ImageDraw.Draw(img).multiline_text(((696 - (r - l)) // 2 - l, (height - (b - t)) // 2 - t),
                                       text, fill="black", font=font, align="center")
    return img


@pytest.mark.parametrize("text", ["Hallo", "X1 -K3\nKlemme 24V", "Sehr langer Text der schrumpft",
                                  "", "A\n\nB"])
def test_plain_text_is_pixel_identical_to_before(text):
    assert render_document(Document("62", objects=[TextObject(text)])).tobytes() == \
        _old_render(text).tobytes()


def test_plain_text_with_fixed_size_is_pixel_identical_to_before():
    new = render_document(Document("62", objects=[TextObject("A\nB", size_pt=48)]))
    assert new.tobytes() == _old_render("A\nB", 200).tobytes()


def test_mixed_sizes_share_one_baseline():
    obj = TextObject([Paragraph([Span("H", size_pt=10), Span("H", size_pt=30)], "left")],
                     size_pt=20)
    # beide „H“ haben keine Unterlänge: gleiche Unterkante = gemeinsame Grundlinie
    h_boxes = _letter_boxes(_ink(render_document(Document("62", objects=[obj]))))
    assert len(h_boxes) == 2
    assert abs(h_boxes[0][3] - h_boxes[1][3]) <= 1
    assert (h_boxes[1][3] - h_boxes[1][1]) > 2 * (h_boxes[0][3] - h_boxes[0][1])


def _letter_boxes(ink):
    """Tintenboxen getrennter Buchstaben (spaltenweise getrennt)."""
    cols = [x for x in range(ink.width) if ink.crop((x, 0, x + 1, ink.height)).getbbox()]
    groups, current = [], [cols[0]]
    for x in cols[1:]:
        if x == current[-1] + 1:
            current.append(x)
        else:
            groups.append(current)
            current = [x]
    groups.append(current)
    boxes = []
    for g in groups:
        _, top, _, bottom = ink.crop((g[0], 0, g[-1] + 1, ink.height)).getbbox()
        boxes.append((g[0], top, g[-1] + 1, bottom))
    return boxes


def _line_boxes(ink):
    """Tintenboxen der Zeilen (an leeren Pixelzeilen getrennt)."""
    rows = [y for y in range(ink.height) if ink.crop((0, y, ink.width, y + 1)).getbbox()]
    groups, current = [], [rows[0]]
    for y in rows[1:]:
        if y == current[-1] + 1:
            current.append(y)
        else:
            groups.append(current)
            current = [y]
    groups.append(current)
    boxes = []
    for g in groups:
        l, _, r, _ = ink.crop((0, g[0], ink.width, g[-1] + 1)).getbbox()
        boxes.append((l, g[0], r, g[-1] + 1))
    return boxes


def _line_edges(img, align):
    obj = TextObject.plain("Kurz\nDeutlich laengere Zeile", size_pt=12, align=align)
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    return top, bottom


def test_left_aligned_lines_share_left_edge():
    top, bottom = _line_edges(None, "left")
    assert abs(top[0] - bottom[0]) <= 3
    assert top[2] < bottom[2] - 50


def test_right_aligned_lines_share_right_edge():
    top, bottom = _line_edges(None, "right")
    assert abs(top[2] - bottom[2]) <= 3
    assert top[0] > bottom[0] + 50


def test_justify_spreads_words_to_block_width():
    obj = TextObject([Paragraph([Span("ein zwei drei")], "justify"),
                      Paragraph([Span("eine laengere Zeile")], "left")], size_pt=12)
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    assert abs(top[0] - bottom[0]) <= 3 and abs(top[2] - bottom[2]) <= 6


def test_underline_draws_below_baseline():
    plain = _ink(render_document(Document("62", objects=[TextObject.plain("ma", size_pt=40)])))
    under = _ink(render_document(Document("62", objects=[TextObject.plain("ma", size_pt=40,
                                                                          underline=True)])))
    assert under.getbbox()[3] > plain.getbbox()[3]


def test_italic_without_real_italic_is_slanted():
    upright = render_document(Document("62", objects=[TextObject.plain("I", size_pt=40)]))
    slanted = render_document(Document("62", objects=[TextObject.plain("I", size_pt=40,
                                                                       italic=True)]))
    assert upright.tobytes() != slanted.tobytes()
    a, b = _ink(upright).getbbox(), _ink(slanted).getbbox()
    assert (b[2] - b[0]) > (a[2] - a[0])          # geschert = breiter


def test_regular_and_bold_differ():
    bold = render_document(Document("62", objects=[TextObject.plain("Hallo", size_pt=30)]))
    regular = render_document(Document("62", objects=[TextObject.plain("Hallo", size_pt=30,
                                                                       bold=False)]))
    assert bold.tobytes() != regular.tobytes()


def test_auto_size_keeps_ratios():
    obj = TextObject([Paragraph([Span("H", size_pt=8)], "left"),
                      Paragraph([Span("H", size_pt=16)], "left")])
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    ratio = (bottom[3] - bottom[1]) / (top[3] - top[1])
    assert 1.8 < ratio < 2.2


def test_fixed_size_too_large_reports_pt():
    with pytest.raises(TextTooLarge, match=r"bei Schriftgröße 60 pt \(höchstens \d+ pt\)"):
        render_document(Document("29", objects=[TextObject.plain("Langer Text", size_pt=60)]))


def test_unknown_alignment_raises():
    with pytest.raises(ValueError, match="Textposition"):
        render_document(Document("62", objects=[TextObject.plain("A", align="mittig")]))


def test_font_warnings_for_unknown_family():
    doc = Document("62", objects=[TextObject.plain("A", family="GibtsGarNicht 4711")])
    warnings = font_warnings(doc)
    assert len(warnings) == 1 and "GibtsGarNicht 4711" in warnings[0]
    assert font_warnings(Document("62", objects=[TextObject("A")])) == []


def test_text_property_and_plain_roundtrip():
    obj = TextObject.plain("Zeile 1\nZeile 2", align="left")
    assert obj.text == "Zeile 1\nZeile 2"
    assert [p.align for p in obj.paragraphs] == ["left", "left"]


# --- Fix nach Review ---------------------------------------------------------
def test_mixed_sizes_descenders_do_not_overlap_next_line():
    obj = TextObject([Paragraph([Span("gpqy", size_pt=36)], "left"),   # ohne i-/j-Punkte
                      Paragraph([Span("HHH", size_pt=8)], "left")], size_pt=20)
    lines = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    assert len(lines) == 2                       # Unterlängen berühren die nächste Zeile nicht
    assert lines[0][3] <= lines[1][1]


def _italic_pair(text):
    upright = _ink(render_document(Document("62", objects=[TextObject.plain(text, size_pt=60)])))
    italic = _ink(render_document(Document("62", objects=[TextObject.plain(text, size_pt=60,
                                                                           italic=True)])))
    return upright, italic


def _dark(ink):
    return ink.histogram()[255]


@pytest.mark.parametrize("text", ["j", "jjj"])
def test_synthetic_italic_keeps_left_ink(text):
    upright, italic = _italic_pair(text)
    assert _dark(italic) >= _dark(upright) * 0.99      # kein abgeschnittener Bogen
    # Breite links der Mitte: Scherung schiebt die Unterlänge nach links, nichts abgeschnitten
    up_l, it_l = upright.getbbox(), italic.getbbox()
    up_c, it_c = (up_l[0] + up_l[2]) / 2, (it_l[0] + it_l[2]) / 2
    assert (it_c - it_l[0]) >= (up_c - up_l[0])


def test_nothing_fits_even_at_minimum_size():
    with pytest.raises(TextTooLarge, match="auch nicht in der kleinsten Schriftgröße") as exc:
        render_document(Document("62", objects=[TextObject.plain("W" * 300, size_pt=20)]))
    assert exc.value.max_pt is None


def test_max_pt_below_minimum_reports_nothing_fits():
    with pytest.raises(TextTooLarge) as exc:
        render_document(Document("62", objects=[TextObject.plain("W" * 60, size_pt=20)]))
    assert exc.value.max_pt is None
    assert str(exc.value) == ("Text passt nicht auf Etikett '62' – auch nicht in der kleinsten "
                              "Schriftgröße.")


def test_italic_with_font_path_is_slanted():
    upright = render_document(Document("62", objects=[
        TextObject.plain("Hallo", size_pt=30, font_path=DEJAVU_BOLD)]))
    italic = render_document(Document("62", objects=[
        TextObject.plain("Hallo", size_pt=30, italic=True, font_path=DEJAVU_BOLD)]))
    assert upright.tobytes() != italic.tobytes()


def test_fit_scales_relative_to_base_size():
    """Feste Rahmengröße mit Grundgröße 20 pt: ein 10-pt-Stück bleibt halb so groß."""
    obj = TextObject([Paragraph([Span("H", size_pt=10)], "left"),
                      Paragraph([Span("H")], "left")], size_pt=20, fit=True)
    top, bottom = _line_boxes(_ink(render_document(Document("62", objects=[obj]))))
    ratio = (bottom[3] - bottom[1]) / (top[3] - top[1])
    assert 1.8 < ratio < 2.2


def test_fit_never_raises_text_too_large():
    obj = TextObject.plain("Sehr langer Text", size_pt=60)
    obj.fit = True
    render_document(Document("29", objects=[obj]))          # schrumpft statt Fehler


# --- Textrahmen über die volle Breite (Abnahme-Fix) ---------------------------
def _bbox(img):
    return _ink(img).getbbox()


def _one(align, **doc_kw):
    obj = TextObject([Paragraph([Span("Test")], align)], size_pt=12)
    return render_document(Document("62", objects=[obj], **doc_kw))


def test_single_line_left_sits_at_left_margin():
    from labelwerk.render import MARGIN
    left, center = _bbox(_one("left")), _bbox(_one("center"))
    assert left[0] <= MARGIN + 8
    assert left[0] < center[0] - 50


def test_single_line_right_sits_at_right_margin():
    from labelwerk.render import MARGIN
    img = _one("right")
    assert _bbox(img)[2] >= img.width - MARGIN - 8
    assert _bbox(img)[2] <= img.width


def test_center_single_line_stays_centered():
    img = _one("center")
    l, _, r, _ = _bbox(img)
    assert abs(l - (img.width - r)) <= 2


def test_mixed_left_and_right_paragraphs_use_full_width():
    from labelwerk.render import MARGIN
    obj = TextObject([Paragraph([Span("Aa")], "left"), Paragraph([Span("Bb")], "right")],
                     size_pt=12)
    img = render_document(Document("62", objects=[obj]))
    half = img.height // 2
    top = _ink(img.crop((0, 0, img.width, half))).getbbox()
    bottom = _ink(img.crop((0, half, img.width, img.height))).getbbox()
    assert top[0] <= MARGIN + 8
    assert bottom[2] >= img.width - MARGIN - 8


def test_horizontal_fixed_length_left_starts_at_label_start():
    obj = TextObject([Paragraph([Span("Test")], "left")], size_pt=12)
    img = render_document(Document("62", objects=[obj], orientation="horizontal", length_mm=100))
    # gedreht um 90° im Uhrzeigersinn: Textanfang liegt oben
    assert _bbox(img)[1] <= 20
    obj = TextObject([Paragraph([Span("Test")], "right")], size_pt=12)
    img = render_document(Document("62", objects=[obj], orientation="horizontal", length_mm=100))
    assert _bbox(img)[3] >= img.height - 20


def test_aligned_ink_stays_inside_image():
    obj = TextObject([Paragraph([Span("Sehr langer Text der schrumpft")], "right")])
    img = render_document(Document("62", objects=[obj]))
    l, _, r, _ = _bbox(img)
    assert l >= 0 and r <= img.width


def test_too_large_message_names_largest_span_size():
    # Grundgröße 19 pt, aber das ganze Wort steht auf 72 pt: die Meldung nennt 72 pt
    obj = TextObject([Paragraph([Span("Tests", size_pt=72)])], size_pt=19)
    doc = Document(label_id="62", objects=[obj])
    with pytest.raises(TextTooLarge, match=r"bei Schriftgröße 72 pt \(höchstens (\d+) pt\)") as exc:
        render_document(doc)
    assert 40 < exc.value.max_pt < 72
    # die genannte Höchstgröße passt wirklich
    obj.paragraphs[0].spans[0].size_pt = exc.value.max_pt
    render_document(doc)
