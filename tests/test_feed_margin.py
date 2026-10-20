"""Along the continuous tape the Brother printer leaves ``feed_margin`` dots free at start and end
(brother_ql, ESC i d: 35 dots ≈ 3 mm). The margin counts this strip (as across it counts the
unprintable strip); a fixed length means the cut-off piece."""
import pytest

from labelwerk.document import Document, TextObject
from labelwerk.labels import get_label, length_limits, sized_id
from labelwerk.render import label_margins, label_size, render_document


def test_feed_margin_of_labels():
    assert get_label("62").feed_margin == 35            # continuous tape: feed of the printer
    assert get_label("29").feed_margin == 35
    assert get_label("62x29").feed_margin == 0          # die-cut: the label itself limits
    assert get_label("d24").feed_margin == 0
    assert get_label(sized_id(57, 32, 203)).feed_margin == 0   # other manufacturers


@pytest.mark.parametrize("orientation, along", [("vertical", 1), ("horizontal", 0)])
def test_margin_along_tape_counts_printer_strip(orientation, along):
    small = Document("62", orientation=orientation, margin_mm=1.0, objects=[TextObject("A")])
    assert label_margins(small)[along] == 0             # 1 mm lies in the printer's strip
    wide = Document("62", orientation=orientation, margin_mm=5.0, objects=[TextObject("A")])
    assert label_margins(wide)[along] == round(5 * 300 / 25.4) - 35
    assert label_margins(wide)[1 - along] == round(5 * 300 / 25.4) - 18   # across as before


def test_margin_on_die_cut_unchanged():
    doc = Document("62x29", margin_mm=3.0, objects=[TextObject("A")])
    label = get_label("62x29")
    m = round(3 * 300 / 25.4)
    assert label_margins(doc) == (m - (label.total_width - label.width) // 2,
                                  m - (label.total_height - label.height) // 2)


def test_fixed_length_is_the_cut_piece():
    doc = Document("62", length_mm=50.0, objects=[TextObject("A")])
    assert label_size(doc)[1] == round(50 * 300 / 25.4) - 2 * 35
    assert render_document(doc).size[1] == round(50 * 300 / 25.4) - 2 * 35


def test_fixed_length_stays_within_model_limits():
    min_len, max_len = length_limits("QL-600")
    short = Document("62", length_mm=1.0, objects=[TextObject("A")])
    assert label_size(short)[1] == min_len              # limits apply to the print image
    long = Document("62", length_mm=5000.0, objects=[TextObject("A")])
    assert label_size(long)[1] == max_len


def test_automatic_length_adds_no_margin_inside_printer_strip():
    text = Document("62", margin_mm=1.0, objects=[TextObject("A", size_pt=60)])
    wide = Document("62", margin_mm=5.0, objects=[TextObject("A", size_pt=60)])
    # 5 mm: 2 × (59 − 35) dots more than 1 mm (there the margin is entirely in the strip)
    assert label_size(wide)[1] - label_size(text)[1] == 2 * (round(5 * 300 / 25.4) - 35)
