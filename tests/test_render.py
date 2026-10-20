import pytest

from labelwerk.render import TextTooLarge, render_text


def test_endless_label_uses_full_printable_width():
    img = render_text("Hallo", "62")
    assert img.width == 696


def test_die_cut_label_matches_exact_size():
    img = render_text("Hallo", "62x29")
    assert img.size == (696, 271)


def test_multiline_text_makes_endless_label_longer():
    one = render_text("A", "62", size_pt=29)
    two = render_text("A\nB", "62", size_pt=29)
    assert two.height > one.height


def test_long_text_is_shrunk_to_fit_width():
    img = render_text("Sehr langer Text, der niemals passt", "29")
    assert img.width == 306
    # right edge stays white -> nothing cut off
    right_edge = img.crop((img.width - 2, 0, img.width, img.height)).convert("L")
    assert right_edge.getextrema()[0] == 255


def test_fixed_font_size_too_large_raises_with_max_size():
    with pytest.raises(TextTooLarge, match=r"Schriftgröße 48 pt .*höchstens \d+ pt") as exc:
        render_text("Sehr langer Text", "29", size_pt=48)
    assert isinstance(exc.value, ValueError)
    render_text("Sehr langer Text", "29", size_pt=exc.value.max_pt)  # fits


def test_fixed_font_size_is_not_shrunk():
    small = render_text("A", "62", size_pt=24)
    large = render_text("A", "62", size_pt=72)
    assert large.height > small.height
