"""TEXT panel edits the selected frame, area "Position" (stage 3d-1)."""
import pytest
from PySide6.QtTest import QTest

from labelwerk import layout
from labelwerk.document import Document, TextObject
from labelwerk.gui.main_window import MainWindow
from labelwerk.labels import DPI
from labelwerk.settings import Settings

DOT_MM = 25.4 / DPI
HINT = "Auf das Etikett klicken, um einen Textrahmen anzulegen"


def _doc():
    return Document("62", length_mm=40, objects=[
        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=20)])


def _window(qtbot, doc=None):
    win = MainWindow(doc=doc if doc is not None else _doc(),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def window(qtbot):
    return _window(qtbot)


def _spins(panel):
    return panel.pos_x, panel.pos_y, panel.pos_w, panel.pos_h


def _values(panel):
    return tuple(spin.value() for spin in _spins(panel))


# --- Panel follows the selection ---------------------------------------------------
def test_without_selection_panel_shows_hint(window):
    panel = window.panel("text")
    assert window.canvas.selection() == [] and panel.index is None
    assert not panel.hint.isHidden() and panel.hint.text() == HINT
    assert not panel.edit.isEnabled() and panel.edit.toPlainText() == ""
    assert not panel.bold.isEnabled() and not panel.pos_x.isEnabled()


def test_panel_edits_selected_object(window):
    panel = window.panel("text")
    window.canvas.set_selection([1])
    assert panel.index == 1 and panel.hint.isHidden() and panel.edit.isEnabled()
    assert panel.edit.toPlainText() == "Zwei"
    panel.edit.setPlainText("Zwei!")
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei!"]
    assert (window.doc.objects[1].x_mm, window.doc.objects[1].y_mm) == (4, 20)


def test_panel_edits_last_selected_of_several(window):
    panel = window.panel("text")
    window.canvas.set_selection([1, 0])
    assert panel.edit.toPlainText() == "Eins"
    window.canvas.set_selection([0, 1])
    assert panel.edit.toPlainText() == "Zwei"


def test_nothing_is_selected_at_start_and_no_frame_is_drawn(qtbot):
    win = MainWindow(settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    assert win.canvas.selection() == [] and win.panel("text").index is None
    assert win.panels.currentWidget() is win.panel("paper")
    win.tool_actions["text"].trigger()                       # TEXT tab: create text
    assert win.canvas.tool() == "text"
    assert win.shortcut_actions["tool.text"].isChecked()
    win.create_text(5, 5)
    assert len(win.doc.objects) == 1 and win.doc.objects[0].positioned


def test_selecting_switches_to_text_panel_and_paper_tab_keeps_selection(window):
    assert window.panels.currentWidget() is window.panel("paper")
    window.canvas.set_selection([0])
    assert window.panels.currentWidget() is window.panel("text")
    assert window.tool_actions["text"].isChecked()
    window.tool_actions["paper"].trigger()
    assert window.panels.currentWidget() is window.panel("paper")
    assert window.canvas.selection() == [0]


def test_text_tab_without_selection_starts_text_tool(window):
    window.tool_actions["text"].trigger()
    assert window.canvas.tool() == "text"
    window.shortcut_actions["tool.select"].trigger()
    window.canvas.set_selection([0])
    window.tool_actions["paper"].trigger()
    window.tool_actions["text"].trigger()
    assert window.canvas.tool() == "select"


def test_typing_goes_into_newly_created_text(window, qtbot):
    window.create_text(30, 12)
    editor = window.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    QTest.keyClicks(editor, "Neu")
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Neu"]
    # new text left-aligned: line start and top edge of the font stay at the click point
    assert window.doc.objects[2].paragraphs[0].align == "left"
    rendered = window.rendered[2]
    x, y = layout.from_object(rendered.layout.anchor("left"), rendered, 0)
    assert (x * DOT_MM, y * DOT_MM) == pytest.approx((30, 12), abs=DOT_MM)


def test_deleting_last_object_leaves_label_empty(qtbot):
    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Allein")]))
    win.canvas.set_selection([0])
    win.delete_selected()
    assert win.doc.objects == [] and win.canvas.objects == []
    assert win.panel("text").index is None and not win.panel("text").hint.isHidden()
    assert win.doc.is_empty()
    win.undo()
    assert [o.text for o in win.doc.objects] == ["Allein"]


# --- Area "Position" ---------------------------------------------------------------
def test_position_shows_frame_of_selected_object(window):
    window.canvas.set_selection([1])
    shown = window.canvas.objects[1].frame_mm()
    x, y, w, h = _values(window.panel("text"))
    assert (x, y) == (4, 20)
    assert (w, h) == pytest.approx((shown.w, shown.h), abs=0.05)
    spin = window.panel("text").pos_x
    assert (spin.decimals(), spin.singleStep()) == (1, 0.1)


def test_position_of_centered_object_is_computed(qtbot):
    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Mitte")]))
    win.canvas.set_selection([0])
    shown = win.canvas.objects[0].frame_mm()
    x, y, _, _ = _values(win.panel("text"))
    assert (x, y) == pytest.approx((shown.x, shown.y), abs=0.05)


def test_editing_x_and_y_moves_object(window):
    window.canvas.set_selection([1])
    panel = window.panel("text")
    panel.pos_x.setValue(10.5)
    panel.pos_y.setValue(22)
    obj = window.doc.objects[1]
    assert (obj.x_mm, obj.y_mm) == (10.5, 22)
    frame = window.canvas.objects[1].frame_mm()
    assert (frame.x, frame.y) == pytest.approx((10.5, 22), abs=DOT_MM)
    window.undo()
    assert (window.doc.objects[1].x_mm, window.doc.objects[1].y_mm) == (10.5, 20)
    assert panel.pos_y.value() == 20


def test_editing_position_of_centered_object_positions_it(qtbot):
    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Mitte")]))
    win.canvas.set_selection([0])
    base_pt = win.canvas.objects[0].rendered.base_pt
    win.panel("text").pos_y.setValue(3)
    obj = win.doc.objects[0]
    assert obj.positioned and obj.y_mm == 3 and obj.size_pt == round(base_pt, 1)


def test_width_and_height_only_editable_with_fixed_frame(window):
    window.canvas.set_selection([0])
    panel = window.panel("text")
    assert panel.pos_w.isReadOnly() and panel.pos_h.isReadOnly()
    assert not panel.pos_x.isReadOnly()
    panel.fit.setChecked(True)
    assert not panel.pos_w.isReadOnly() and not panel.pos_h.isReadOnly()
    panel.pos_w.setValue(30)
    obj = window.doc.objects[0]
    assert obj.fit and obj.w_mm == 30 and (obj.x_mm, obj.y_mm) == (4, 4)
    assert window.canvas.objects[0].frame_mm().w == pytest.approx(30, abs=DOT_MM)


def test_size_edit_without_fixed_frame_is_ignored_by_the_panel(window):
    """Even if the Position area reports a size: not without a fixed frame size."""
    window.canvas.set_selection([0])
    panel = window.panel("text")
    seen = []
    panel.frame_edited.connect(lambda key, value: seen.append((key, value)))
    panel._frame_changed("w", 30)
    panel._frame_changed("x", 6)
    assert seen == [("x", 6)]


def test_turning_fixed_frame_on_keeps_current_frame_size(window):
    window.canvas.set_selection([0])
    shown = window.canvas.objects[0].frame_mm()
    window.panel("text").fit.setChecked(True)
    obj = window.doc.objects[0]
    assert obj.fit and (obj.w_mm, obj.h_mm) == pytest.approx((shown.w, shown.h), abs=0.001)
    frame = window.canvas.objects[0].frame_mm()
    assert (frame.w, frame.h) == pytest.approx((shown.w, shown.h), abs=DOT_MM)


def test_position_follows_nudge(window):
    window.canvas.set_selection([1])
    window.nudge(1, -0.5)
    assert window.panel("text").pos_x.value() == 5
    assert window.panel("text").pos_y.value() == 19.5


def test_panels_scroll_instead_of_growing_the_window(window):
    window.canvas.set_selection([0])
    assert window.minimumSizeHint().height() < 600          # also fits 768 px screens
    assert window.panels.parentWidget().parentWidget().objectName() == "panelScroll"


def test_combos_are_blank_without_selection(window):
    panel = window.panel("text")
    assert panel.size.currentText() == "" and panel.family.currentText() == ""
    window.canvas.set_selection([0])
    assert panel.size.currentText() == "14" and panel.family.currentText()
