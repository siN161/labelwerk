import pytest
from labelwerk.labels import format_mm, get_label, labels_for_model, length_limits


def test_62mm_endless_has_696_printable_dots():
    label = get_label("62")
    assert label.width == 696
    assert label.height is None  # continuous


def test_die_cut_label_has_fixed_height():
    label = get_label("62x29")
    assert (label.width, label.height) == (696, 271)


def test_unknown_label_raises():
    with pytest.raises(ValueError, match="Unbekanntes Etikett"):
        get_label("999")


def test_ql600_excludes_labels_wider_than_62mm():
    ids = {l.id for l in labels_for_model("QL-600")}
    assert "62" in ids
    assert "102" not in ids


def test_ql600_excludes_ptouch_tapes():
    ids = {l.id for l in labels_for_model("QL-600")}
    assert not any(i.startswith("pt") for i in ids)


def test_ql600_excludes_two_color_labels():
    ids = {l.id for l in labels_for_model("QL-600")}
    assert "62red" not in ids


def test_round_label_description():
    assert get_label("d24").description == "Ø 24 mm rund"


def test_format_mm_uses_decimal_comma():
    assert format_mm(696) == "58,9"


def test_length_limits_for_ql600():
    assert length_limits("QL-600") == (150, 11811)


def test_label_shape_and_physical_size():
    endless, die_cut, round_ = get_label("62"), get_label("62x29"), get_label("d24")
    assert (endless.shape, endless.total_width, endless.total_height) == ("endless", 732, None)
    assert (die_cut.shape, die_cut.total_width, die_cut.total_height) == ("die_cut", 732, 341)
    assert (round_.shape, round_.size_mm) == ("round", (24, 24))
