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
