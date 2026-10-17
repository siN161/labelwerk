from labelwerk.render import render_text


def test_endless_label_uses_full_printable_width():
    img = render_text("Hallo", "62")
    assert img.width == 696


def test_die_cut_label_matches_exact_size():
    img = render_text("Hallo", "62x29")
    assert img.size == (696, 271)


def test_multiline_text_makes_endless_label_longer():
    one = render_text("A", "62", font_size=60)
    two = render_text("A\nB", "62", font_size=60)
    assert two.height > one.height


def test_long_text_is_shrunk_to_fit_width():
    img = render_text("Sehr langer Text, der niemals passt", "29", font_size=200)
    assert img.width == 306
    # rechter Rand bleibt weiß -> nichts abgeschnitten
    right_edge = img.crop((img.width - 2, 0, img.width, img.height)).convert("L")
    assert right_edge.getextrema()[0] == 255
