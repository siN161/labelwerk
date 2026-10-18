"""Bereich „Position“ als eigenes Widget (gemeinsam für Text- und Bild-Panel)."""
from labelwerk.gui.panels.position import PositionSection
from labelwerk.layout import Rect


def _section(qtbot) -> tuple[PositionSection, list]:
    section = PositionSection()
    qtbot.addWidget(section)
    seen = []
    section.edited.connect(lambda key, value: seen.append((key, value)))
    return section, seen


def test_show_frame_sets_values_without_signal(qtbot):
    section, seen = _section(qtbot)
    section.show_frame(Rect(1.5, 2, 30, 8.2), editable_size=True)
    assert [s.value() for s in section.spins.values()] == [1.5, 2, 30, 8.2]
    section.show_frame(None, editable_size=True)
    assert [s.value() for s in section.spins.values()] == [0, 0, 1, 1]   # Mindestgröße 1 mm
    assert seen == []


def test_editable_size_reports_all_fields(qtbot):
    section, seen = _section(qtbot)
    section.show_frame(Rect(1, 2, 30, 8), editable_size=True)
    assert not section.spins["w"].isReadOnly()
    section.spins["x"].setValue(4)
    section.spins["w"].setValue(25)
    assert seen == [("x", 4), ("w", 25)]


def test_fixed_size_only_shows_width_and_height(qtbot):
    section, seen = _section(qtbot)
    section.show_frame(Rect(1, 2, 30, 8), editable_size=False)
    assert section.spins["w"].isReadOnly() and section.spins["h"].isReadOnly()
    assert "Nur mit fester Rahmengröße" in section.spins["w"].toolTip()
    section.spins["h"].setValue(12)
    section.spins["y"].setValue(3)
    assert seen == [("y", 3)]
