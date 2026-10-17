from labelwerk.document import Document, TextObject
from labelwerk.render import render_document, render_text


def test_empty_document():
    assert Document().is_empty()
    assert Document(objects=[TextObject("")]).is_empty()
    assert Document(objects=[TextObject("  \n ")]).is_empty()
    assert not Document(objects=[TextObject("Hallo")]).is_empty()


def test_render_document_equals_render_text():
    doc = Document("62", objects=[TextObject("Hallo\nWelt")])
    assert render_document(doc).tobytes() == render_text("Hallo\nWelt", "62").tobytes()


def test_fixed_length_sets_height():
    doc = Document("62", length_mm=50, objects=[TextObject("Hallo")])
    assert render_document(doc).height == 591


def test_length_is_clamped_to_model_limits():
    assert render_document(Document("62", length_mm=5, objects=[TextObject("A")])).height == 150
    assert render_document(Document("62", length_mm=2000, objects=[TextObject("A")])).height == 11811


def test_short_auto_length_is_raised_to_minimum():
    assert render_document(Document("62", objects=[TextObject(".")])).height == 150


def test_too_tall_text_for_fixed_length_raises():
    import pytest
    from labelwerk.render import TextTooLarge
    doc = Document("62", length_mm=15, objects=[TextObject("A\nB\nC", font_size=100)])
    with pytest.raises(TextTooLarge):
        render_document(doc)


def test_length_is_ignored_for_die_cut():
    doc = Document("62x29", length_mm=50, objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 271)


def test_empty_document_renders_blank_label():
    img = render_document(Document("62"))
    assert img.convert("L").getextrema() == (255, 255)


def _ink(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0)


def test_horizontal_endless_prints_across_full_width_and_grows_with_text():
    short = render_document(Document("62", orientation="horizontal", objects=[TextObject("Hi")]))
    long = render_document(Document("62", orientation="horizontal",
                                    objects=[TextObject("Max Mustermann")]))
    assert short.width == long.width == 696
    assert long.height > short.height


def test_horizontal_text_reads_along_the_tape():
    img = render_document(Document("62", orientation="horizontal",
                                   objects=[TextObject("Hallo\n.", font_size=150)]))
    reading = img.rotate(90, expand=True)              # zurück in Leserichtung
    ink = _ink(reading)
    top = ink.crop((0, 0, reading.width, reading.height // 2)).histogram()[255]
    bottom = ink.crop((0, reading.height // 2, reading.width, reading.height)).histogram()[255]
    assert top > 3 * bottom                             # „Hallo“ oben, kleiner Punkt unten


def test_horizontal_auto_font_matches_vertical():
    def ink_height(orientation):
        img = render_document(Document("62", orientation=orientation, objects=[TextObject("Hallo")]))
        reading = img.rotate(90, expand=True) if orientation == "horizontal" else img
        box = _ink(reading).getbbox()
        return box[3] - box[1]
    assert ink_height("horizontal") == ink_height("vertical")   # gleiche Obergrenze


def test_horizontal_fixed_length():
    doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 591)


def test_horizontal_die_cut_keeps_print_size():
    doc = Document("62x29", orientation="horizontal", objects=[TextObject("Hallo")])
    assert render_document(doc).size == (696, 271)


def test_margin_extends_auto_length():
    def height(margin):
        doc = Document("62", margin_mm=margin, objects=[TextObject("A", font_size=200)])
        return render_document(doc).height
    assert height(5) - height(1) == 2 * (59 - 12)        # 5 mm = 59 Punkte, 1 mm = 12


def test_margin_is_clamped_to_20_mm():
    def height(margin):
        doc = Document("62", margin_mm=margin, objects=[TextObject("A", font_size=200)])
        return render_document(doc).height
    assert height(50) == height(20)
    assert height(-3) == height(0)


def test_unknown_orientation_raises():
    import pytest
    with pytest.raises(ValueError, match="Ausrichtung"):
        render_document(Document("62", orientation="schräg", objects=[TextObject("A")]))


def test_horizontal_render_is_fast_enough_for_live_preview():
    import time
    doc = Document("62", orientation="horizontal",
                   objects=[TextObject("Max Mustermann\nMusterstr. 5\n12345 Musterstadt")])
    render_document(doc)                      # Aufwärmen (Schrift laden)
    start = time.perf_counter()
    render_document(doc)
    assert time.perf_counter() - start < 0.5


def _ink_bbox(img):
    from PIL import ImageOps
    return ImageOps.invert(img.convert("L")).getbbox()


def test_margin_larger_than_fixed_length_is_limited():
    img = render_document(Document("62", length_mm=10, margin_mm=20, objects=[TextObject("A")]))
    assert img.height == 150
    left, top, right, bottom = _ink_bbox(img)
    assert top > 0 and bottom < img.height
    assert bottom - top >= 20                 # nicht auf Mindestschrift geschrumpft


def test_margin_larger_than_die_cut_label_is_limited():
    img = render_document(Document("62x29", margin_mm=20, objects=[TextObject("A")]))
    assert img.size == (696, 271)
    box = _ink_bbox(img)
    assert box is not None and box[3] - box[1] >= 20
