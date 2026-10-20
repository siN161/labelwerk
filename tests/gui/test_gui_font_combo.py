"""Font picker FontCombo: list from fonts.families, each font in its own typeface, a foreign font
stays visible."""
from PySide6.QtCore import Qt

from labelwerk.gui.widgets import FontCombo


def _combo(qtbot, names=("DejaVu Sans", "DejaVu Serif", "Liberation Sans")):
    combo = FontCombo(list(names))
    qtbot.addWidget(combo)
    return combo


def _items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_lists_families_each_in_its_own_font(qtbot):
    combo = _combo(qtbot)
    assert _items(combo) == ["DejaVu Sans", "DejaVu Serif", "Liberation Sans"]
    assert combo.itemData(1, Qt.ItemDataRole.FontRole).family() == "DejaVu Serif"


def test_default_list_comes_from_fonts(qtbot, monkeypatch):
    from labelwerk import fonts
    monkeypatch.setattr(fonts, "families", lambda all=False: ["B", "C"] if all else ["B"])
    combo = FontCombo()
    qtbot.addWidget(combo)
    assert _items(combo) == ["B"]
    assert "Sans Serif" not in _items(combo)                   # no Qt collective names


def test_unknown_family_is_shown_on_top_and_chosen(qtbot):
    combo = _combo(qtbot)
    combo.set_current_family("GibtsGarNicht 4711")
    assert combo.current_family() == "GibtsGarNicht 4711" and combo.currentIndex() == 0
    assert combo.count() == 4
    combo.set_current_family("GanzAnders")                       # just a foreign entry
    assert _items(combo)[0] == "GanzAnders" and combo.count() == 4
    combo.set_current_family("DejaVu Serif")                     # foreign entry is dropped
    assert _items(combo) == ["DejaVu Sans", "DejaVu Serif", "Liberation Sans"]
    assert combo.current_family() == "DejaVu Serif"


def test_family_chosen_signal(qtbot):
    combo = _combo(qtbot)
    combo.set_current_family("DejaVu Sans")
    with qtbot.waitSignal(combo.family_chosen) as blocker:
        combo.setCurrentIndex(2)                                 # like a choice in the list
    assert blocker.args == ["Liberation Sans"]
    with qtbot.waitSignal(combo.family_chosen) as blocker:
        combo.set_current_family("DejaVu Serif")
    assert blocker.args == ["DejaVu Serif"]
    with qtbot.assertNotEmitted(combo.family_chosen):
        combo.set_current_family("DejaVu Serif")                 # unchanged
        combo.setCurrentIndex(-1)                                # empty: no font


def test_empty_shows_nothing(qtbot):
    combo = _combo(qtbot)
    combo.set_current_family("DejaVu Serif")
    combo.setCurrentIndex(-1)
    assert combo.currentText() == "" and combo.current_family() is None


def test_set_families_keeps_current_choice(qtbot):
    combo = _combo(qtbot)
    combo.set_current_family("Liberation Sans")
    with qtbot.assertNotEmitted(combo.family_chosen):
        combo.set_families(["DejaVu Sans"])
    assert combo.current_family() == "Liberation Sans"           # stays (now as a foreign font)
    assert _items(combo) == ["Liberation Sans", "DejaVu Sans"]
    combo.set_families(["DejaVu Sans", "Liberation Sans"])
    assert _items(combo) == ["DejaVu Sans", "Liberation Sans"]
    assert combo.current_family() == "Liberation Sans"


def test_set_none_shows_nothing_without_signal(qtbot):
    combo = _combo(qtbot)
    combo.set_current_family("DejaVu Serif")
    with qtbot.assertNotEmitted(combo.family_chosen):
        combo.set_current_family(None)
    assert combo.current_family() is None
    with qtbot.waitSignal(combo.family_chosen) as blocker:
        combo.set_current_family("DejaVu Serif")                 # chosen again: reports
    assert blocker.args == ["DejaVu Serif"]


def test_old_qt_name_with_foundry_shows_installed_family(qtbot, monkeypatch):
    from labelwerk import fonts
    monkeypatch.setattr(fonts, "families", lambda all=False: ["C059", "DejaVu Sans"])
    combo = _combo(qtbot, ("C059", "DejaVu Sans"))
    combo.set_current_family("C059 [UKWN]")
    assert combo.current_family() == "C059" and combo.count() == 2   # no foreign entry
    combo.set_current_family("Sans Serif")                           # collective name stays foreign
    assert combo.current_family() == "Sans Serif" and combo.count() == 3


def test_long_font_names_do_not_widen_the_panel(qtbot):
    from labelwerk.gui.app import load_theme
    from labelwerk.gui.main_window import PANEL_WIDTH
    short = _combo(qtbot, ("A",))
    long = _combo(qtbot, ("A", "Ein sehr langer Schriftname Extra Condensed Semibold Italic Display"))
    for combo in (short, long):
        combo.setStyleSheet(load_theme())
        combo.ensurePolished()
    assert long.minimumSizeHint().width() == short.minimumSizeHint().width() < PANEL_WIDTH
