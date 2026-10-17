"""Bearbeitungsleiste: Text anlegen, Zwischenablage, Rückgängig (Etappe 3d-1)."""
from importlib import resources

import pytest
from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolBar

from labelwerk import shortcuts
from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM
from labelwerk.gui.main_window import MainWindow
from labelwerk.settings import Settings

NO_MOD = Qt.KeyboardModifier.NoModifier
ALT = Qt.KeyboardModifier.AltModifier
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
LEFT = Qt.MouseButton.LeftButton


def _doc(orientation="vertical"):
    return Document("62", length_mm=40, orientation=orientation, objects=[
        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=20)])


def _window(qtbot, doc=None, settings=None):
    win = MainWindow(doc=doc if doc is not None else _doc(),
                     settings=settings or Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def window(qtbot):
    return _window(qtbot)


def _send(canvas, kind, pos, buttons, modifiers=NO_MOD):
    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)),
                        button, buttons, modifiers)
    QApplication.sendEvent(canvas.viewport(), event)


def _click(canvas, pos, modifiers=NO_MOD):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, pos, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton, modifiers)


def _double_click(canvas, pos):
    _click(canvas, pos)
    _send(canvas, QMouseEvent.Type.MouseButtonDblClick, pos, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)


def _drag(canvas, start, end, modifiers=ALT):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, modifiers)


def _view_point(canvas, x_mm, y_mm):
    """Punkt in mm in Leserichtung → Ansichtskoordinaten."""
    scene = canvas.sheet.mapToScene(QPointF(x_mm * MM, y_mm * MM))
    return canvas.viewportTransform().map(scene)


def _focus_canvas(window, qtbot):
    window.activateWindow()
    window.canvas.setFocus()
    qtbot.waitUntil(lambda: window.canvas.hasFocus(), timeout=1000)


def _positions(window):
    return [(o.x_mm, o.y_mm) for o in window.doc.objects]


# --- Leiste -----------------------------------------------------------------------
def test_edit_bar_holds_tools_clipboard_and_history(window):
    bar = window.edit_bar
    assert isinstance(bar, QToolBar) and bar.objectName() == "editBar"
    ids = [a.objectName() if not a.isSeparator() else "|" for a in bar.actions()]
    assert ids == ["tool.select", "tool.text", "|", "edit.cut", "edit.copy", "edit.paste",
                   "|", "edit.undo", "edit.redo"]
    assert window.toolBarBreak(bar)                         # eigene Zeile unter den Werkzeugen
    assert "Ctrl+Z" in window.actions["edit.undo"].toolTip()


def test_edit_bar_buttons_show_own_icons_only(window):
    folder = resources.files("labelwerk.gui") / "icons"
    for action in window.edit_bar.actions():
        if action.isSeparator():
            continue
        button = window.edit_bar.widgetForAction(action)
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert not action.icon().isNull()
        name = shortcuts.action(action.objectName()).name
        assert action.toolTip().startswith(name)
    for name in ("tool-select", "tool-text", "edit-cut", "edit-copy", "edit-paste",
                 "edit-undo", "edit-redo"):
        for color in ("black", "white"):
            assert (folder / f"{name}-{color}.svg").is_file()
    assert "(T)" in window.actions["tool.text"].toolTip()


def _ink(icon, mode=QIcon.Mode.Normal, state=QIcon.State.Off):
    image = icon.pixmap(QSize(16, 16), mode, state).toImage()
    pixels = [image.pixelColor(x, y) for x in range(16) for y in range(16)]
    return {(c.red(), c.green(), c.blue()) for c in pixels if c.alpha() > 200}


def test_edit_bar_icons_follow_theme(qtbot):
    win = _window(qtbot, settings=Settings(check_media_on_start=False, theme="rawblock"))
    icon = win.actions["tool.select"].icon()
    assert _ink(icon) == {(0, 0, 0)}
    assert _ink(icon, state=QIcon.State.On) == {(255, 255, 255)}      # gewählt: weiß auf schwarz
    assert _ink(icon, QIcon.Mode.Active) == {(255, 255, 255)}         # darüber: weiß auf schwarz
    win.settings = Settings(check_media_on_start=False, theme="classic")
    win.apply_theme_icons()
    icon = win.actions["tool.select"].icon()
    assert _ink(icon, state=QIcon.State.On) == {(0, 0, 0)}


def test_click_on_selected_object_leaves_paper_tab_but_not_layout(window):
    window.canvas.set_selection([0])
    window.tool_actions["paper"].trigger()
    _click(window.canvas, window.canvas.view_rect(0).center())
    assert window.panels.currentWidget() is window.panel("text")
    window.tool_actions["layout"].trigger()
    _click(window.canvas, window.canvas.view_rect(0).center())
    assert window.panels.currentWidget() is window.panel("layout")
    assert window.tool_actions["layout"].isChecked()


def test_select_all_ends_text_tool(window, qtbot):
    window.actions["tool.text"].trigger()
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_A, CTRL)
    assert window.canvas.selection() == [0, 1]
    assert window.canvas.tool() == "select" and window.actions["tool.select"].isChecked()


def test_tool_modes_are_exclusive(window):
    select, text = window.actions["tool.select"], window.actions["tool.text"]
    assert select.isChecked() and not text.isChecked()
    assert window.canvas.tool() == "select"
    text.trigger()
    assert window.canvas.tool() == "text" and text.isChecked() and not select.isChecked()
    select.trigger()
    assert window.canvas.tool() == "select" and select.isChecked()


def test_t_and_esc_switch_tool_on_canvas(window, qtbot):
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_T)
    assert window.canvas.tool() == "text" and window.actions["tool.text"].isChecked()
    QTest.keyClick(window.canvas, Qt.Key.Key_Escape)
    assert window.canvas.tool() == "select" and window.actions["tool.select"].isChecked()


def test_clipboard_actions_follow_selection(window):
    for key in ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete"):
        assert not window.actions[key].isEnabled()
    assert not window.actions["edit.paste"].isEnabled()
    window.canvas.set_selection([0])
    for key in ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete"):
        assert window.actions[key].isEnabled()
    window.actions["edit.copy"].trigger()
    assert window.actions["edit.paste"].isEnabled()


# --- Text anlegen -----------------------------------------------------------------
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_click_with_text_tool_creates_text_at_click_point(qtbot, orientation):
    win = _window(qtbot, _doc(orientation))
    win.actions["tool.text"].trigger()
    _click(win.canvas, _view_point(win.canvas, 30, 12))
    assert len(win.doc.objects) == 3
    obj = win.doc.objects[2]
    assert obj.is_empty() and not obj.fit
    assert (obj.x_mm, obj.y_mm) == pytest.approx((30, 12), abs=0.1)
    assert win.canvas.selection() == [2]
    assert win.canvas.tool() == "select" and win.actions["tool.select"].isChecked()
    assert win.panels.currentWidget() is win.panel("text")
    qtbot.waitUntil(lambda: win.panel("text").edit.hasFocus(), timeout=1000)


def test_new_text_uses_font_from_settings(qtbot):
    win = _window(qtbot, settings=Settings(check_media_on_start=False, font_size_pt=24,
                                           font_family="DejaVu Serif"))
    win.create_text(10, 5)
    obj = win.doc.objects[-1]
    assert obj.size_pt == 24
    assert obj.paragraphs[0].spans[0].family == "DejaVu Serif"


def test_new_text_with_automatic_size_setting_gets_19_pt(qtbot):
    win = _window(qtbot, settings=Settings(check_media_on_start=False, font_size_pt=None))
    win.create_text(10, 5)
    obj = win.doc.objects[-1]
    assert obj.size_pt == 19 and obj.paragraphs[0].spans[0].family is None


def test_new_empty_text_is_selected_with_a_visible_frame(window):
    window.create_text(30, 12)
    rect = window.canvas.view_rect(2)
    assert rect.width() > 0 and rect.height() > 0      # Platzhalter, bis Text da ist
    point = _view_point(window.canvas, 30, 12)
    assert rect.topLeft().x() == pytest.approx(point.x(), abs=1)
    assert rect.topLeft().y() == pytest.approx(point.y(), abs=1)


def test_creating_text_removes_other_empty_texts(qtbot):
    doc = _doc()
    doc.objects.append(TextObject(""))
    win = _window(qtbot, doc)
    win.create_text(30, 12)
    assert [o.text for o in win.doc.objects] == ["Eins", "Zwei", ""]
    assert win.doc.objects[2].positioned and win.canvas.selection() == [2]


def test_click_outside_label_with_text_tool_creates_nothing(window):
    window.actions["tool.text"].trigger()
    label = window.canvas.label_view_rect()
    _click(window.canvas, label.bottomRight() + QPointF(20, 20))
    assert len(window.doc.objects) == 2
    assert window.canvas.tool() == "text"


def test_click_on_object_with_text_tool_selects_it(window, qtbot):
    window.actions["tool.text"].trigger()
    _click(window.canvas, window.canvas.view_rect(1).center())
    assert len(window.doc.objects) == 2
    assert window.canvas.selection() == [1] and window.canvas.tool() == "select"
    qtbot.waitUntil(lambda: window.panel("text").edit.hasFocus(), timeout=1000)


def test_double_click_on_text_focuses_editor(window, qtbot):
    window.tool_actions["paper"].trigger()
    _double_click(window.canvas, window.canvas.view_rect(1).center())
    assert window.canvas.selection() == [1]
    assert window.panels.currentWidget() is window.panel("text")
    qtbot.waitUntil(lambda: window.panel("text").edit.hasFocus(), timeout=1000)


# --- Zwischenablage ---------------------------------------------------------------
def test_copy_paste_offsets_by_2_mm_each_time(window, qtbot):
    window.canvas.set_selection([1])
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_C, CTRL)
    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Zwei"]
    assert _positions(window)[2] == pytest.approx((6, 22))
    assert window.canvas.selection() == [2]
    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
    assert _positions(window)[3] == pytest.approx((8, 24))
    assert window.canvas.selection() == [3]
    assert window.doc.objects[1].x_mm == 4                   # Original bleibt


def test_paste_keeps_order_and_copies_are_independent(window):
    window.canvas.set_selection([1, 0])
    window.actions["edit.copy"].trigger()
    window.doc.objects[0] = TextObject("geändert", size_pt=14, x_mm=4, y_mm=4)
    window.actions["edit.paste"].trigger()
    assert [o.text for o in window.doc.objects] == ["geändert", "Zwei", "Eins", "Zwei"]
    assert window.canvas.selection() == [2, 3]


def test_copy_of_centered_text_pastes_next_to_it(qtbot):
    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Mitte")]))
    shown = win.canvas.objects[0].frame_mm()
    win.canvas.set_selection([0])
    win.actions["edit.copy"].trigger()
    win.actions["edit.paste"].trigger()
    pasted = win.doc.objects[1]
    assert pasted.positioned and pasted.size_pt is not None
    assert (pasted.x_mm, pasted.y_mm) == pytest.approx((shown.x + 2, shown.y + 2), abs=0.01)
    assert not win.doc.objects[0].positioned


def test_cut_removes_and_paste_brings_back(window, qtbot):
    window.canvas.set_selection([0])
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_X, CTRL)
    assert [o.text for o in window.doc.objects] == ["Zwei"]
    assert window.canvas.selection() == []
    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
    assert [o.text for o in window.doc.objects] == ["Zwei", "Eins"]
    assert _positions(window)[1] == pytest.approx((6, 6))


def test_duplicate_leaves_clipboard_alone(window, qtbot):
    window.canvas.set_selection([0])
    window.actions["edit.copy"].trigger()
    window.canvas.set_selection([1])
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_D, CTRL)
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Zwei"]
    assert _positions(window)[2] == pytest.approx((6, 22))
    assert window.canvas.selection() == [2]
    window.actions["edit.paste"].trigger()
    assert window.doc.objects[3].text == "Eins"


# --- Rückgängig -------------------------------------------------------------------
def _undo(window):
    window.actions["edit.undo"].trigger()


def _redo(window):
    window.actions["edit.redo"].trigger()


def test_undo_redo_drag(window):
    start = window.canvas.view_rect(0).center()
    _drag(window.canvas, start, start + QPointF(40, 0))
    moved = window.doc.objects[0].x_mm
    assert moved > 4
    _undo(window)
    assert window.doc.objects[0].x_mm == 4
    assert window.canvas.objects[0].frame_mm().x == pytest.approx(
        window.canvas.objects[1].frame_mm().x)           # Arbeitsfläche folgt
    _redo(window)
    assert window.doc.objects[0].x_mm == moved


def test_undo_resize(window):
    window.canvas.set_selection([0])
    edge = window.canvas.handle_points(0)["r"]
    _drag(window.canvas, edge, edge + QPointF(10 * window.canvas.px_per_mm(), 0), NO_MOD)
    assert window.doc.objects[0].fit
    _undo(window)
    assert not window.doc.objects[0].fit and window.doc.objects[0].w_mm is None


def test_consecutive_nudges_are_one_step(window, qtbot):
    window.canvas.set_selection([1])
    _focus_canvas(window, qtbot)
    for _ in range(3):
        QTest.keyClick(window.canvas, Qt.Key.Key_Right)
    assert window.doc.objects[1].x_mm == pytest.approx(4.3)
    QTest.keyClick(window.canvas, Qt.Key.Key_Z, CTRL)
    assert window.doc.objects[1].x_mm == 4
    QTest.keyClick(window.canvas, Qt.Key.Key_Z, CTRL | SHIFT)
    assert window.doc.objects[1].x_mm == pytest.approx(4.3)


def test_undo_create_delete_paste_duplicate(window):
    steps = []
    window.create_text(30, 12)
    steps.append(3)
    window.panel("text").edit.setPlainText("Neu")            # Getipptes: eigener Schritt
    steps.append(3)
    window.canvas.set_selection([0])
    window.delete_selected()
    steps.append(2)
    window.canvas.set_selection([0])
    window.actions["edit.copy"].trigger()
    window.actions["edit.paste"].trigger()
    steps.append(3)
    window.actions["edit.duplicate"].trigger()
    steps.append(4)
    counts = []
    for _ in steps:
        counts.append(len(window.doc.objects))
        _undo(window)
    assert counts == list(reversed(steps))
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
    assert not window.actions["edit.undo"].isEnabled()
    _redo(window)
    assert len(window.doc.objects) == 3 and window.actions["edit.redo"].isEnabled()


def test_undo_cut(window):
    window.canvas.set_selection([0])
    window.actions["edit.cut"].trigger()
    _undo(window)
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]


def test_typing_is_one_step_when_editor_loses_focus(window, qtbot):
    window.canvas.set_selection([0])
    editor = window.panel("text").edit
    window.activateWindow()
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    QTest.keyClicks(editor, " und mehr")
    _focus_canvas(window, qtbot)                            # Fokus verlässt das Textfeld
    assert window.doc.objects[0].text == "Eins und mehr"
    _undo(window)
    assert window.doc.objects[0].text == "Eins"
    assert editor.toPlainText() == "Eins"                   # Panel folgt
    _redo(window)
    assert editor.toPlainText() == "Eins und mehr"


def test_format_button_is_its_own_step(window):
    window.canvas.set_selection([0])
    panel = window.panel("text")
    panel.edit.setPlainText("Eins!")                        # Tippen, noch nicht festgehalten
    panel.italic.click()
    _undo(window)
    assert window.doc.objects[0].text == "Eins!"
    assert not window.doc.objects[0].paragraphs[0].spans[0].italic
    _undo(window)
    assert window.doc.objects[0].text == "Eins"


def test_undo_button_is_enabled_by_pending_typing(window):
    window.canvas.set_selection([0])
    assert not window.actions["edit.undo"].isEnabled()
    window.panel("text").edit.setPlainText("Neu")
    assert window.actions["edit.undo"].isEnabled()
    _undo(window)
    assert window.doc.objects[0].text == "Eins"


def test_paper_change_is_undoable(window):
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert window.doc.label_id == "62x29"
    _undo(window)
    assert window.doc.label_id == "62"
    assert paper.combo.currentData() == "62"


def test_ctrl_z_in_editor_uses_editor_undo(window, qtbot):
    window.canvas.set_selection([0])
    window.canvas.nudge(1, 0)                               # Schritt im Dokument
    editor = window.panel("text").edit
    window.activateWindow()
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    editor.moveCursor(editor.textCursor().MoveOperation.End)
    QTest.keyClicks(editor, "X")
    assert window.doc.objects[0].text == "EinsX"
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
    assert window.doc.objects[0].text == "Eins"             # Editor hat rückgängig gemacht
    assert window.doc.objects[0].x_mm == pytest.approx(5)   # Dokument nicht
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
    assert editor.toPlainText() == "Eins"                   # Aufbau des Editors ist kein Schritt


def test_undo_restores_selection_of_the_state(window):
    window.canvas.set_selection([1])
    window.canvas.nudge(1, 0)
    _undo(window)
    assert window.canvas.selection() == [1]
    window.create_text(30, 12)
    assert window.canvas.selection() == [2]
    _undo(window)
    assert window.canvas.selection() == [1]                 # Auswahl vor dem Anlegen
    window.canvas.set_selection([0])
    window.delete_selected()
    _undo(window)
    assert window.canvas.selection() == [0]                 # Gelöschtes ist wieder gewählt


# --- Leere Textrahmen -------------------------------------------------------------
def _empty_area(canvas):
    return canvas.view_rect(1).bottomRight() + QPointF(40, 40)


def test_empty_frame_is_removed_when_clicking_away(window):
    window.create_text(30, 12)
    assert len(window.doc.objects) == 3
    _click(window.canvas, _empty_area(window.canvas))
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
    assert len(window.canvas.objects) == 2
    assert not window.actions["edit.undo"].isEnabled()       # kein leerer Schritt übrig


def test_empty_frame_is_removed_when_selecting_another_object(window):
    window.create_text(30, 12)
    _click(window.canvas, window.canvas.view_rect(1).center())
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
    assert window.canvas.selection() == [1]
    assert window.panel("text").edit.toPlainText() == "Zwei"


def test_selection_is_renumbered_when_empty_frame_before_it_goes(qtbot):
    doc = _doc()
    frame = TextObject.plain("", size_pt=14)
    frame.x_mm, frame.y_mm = 30, 12
    doc.objects.insert(0, frame)
    win = _window(qtbot, doc)
    win.canvas.set_selection([0])
    win.canvas.set_selection([2])
    assert [o.text for o in win.doc.objects] == ["Eins", "Zwei"]
    assert win.canvas.selection() == [1]
    assert win.panel("text").edit.toPlainText() == "Zwei"


def test_frame_with_text_stays(window):
    window.create_text(30, 12)
    window.panel("text").edit.setPlainText("Neu")
    _click(window.canvas, _empty_area(window.canvas))
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Neu"]


def test_empty_frame_removed_while_pasting_is_part_of_the_paste_step(window):
    window.canvas.set_selection([0])
    window.copy_selected()
    window.create_text(30, 12)
    window.paste()
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Eins"]
    assert window.canvas.selection() == [2]
    _undo(window)
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", ""]


def test_empty_frame_does_not_lengthen_auto_label(qtbot):
    doc = _doc()
    doc.length_mm = None
    win = _window(qtbot, doc)
    length = win.canvas.label_height()
    win.create_text(10, 80)
    assert len(win.doc.objects) == 3 and win.canvas.selection() == [2]
    assert win.canvas.label_height() == length


# --- Werkzeug folgt dem Panel -------------------------------------------------------
def test_text_panel_without_selection_activates_text_tool(window):
    _click(window.canvas, window.canvas.view_rect(0).center())
    assert window.panels.currentWidget() is window.panel("text")
    assert window.canvas.tool() == "select"
    _click(window.canvas, _empty_area(window.canvas))
    assert window.canvas.selection() == []
    assert window.canvas.tool() == "text" and window.actions["tool.text"].isChecked()


def test_paper_panel_without_selection_keeps_select_tool(window):
    window.canvas.set_selection([0])
    window.tool_actions["paper"].trigger()
    _click(window.canvas, _empty_area(window.canvas))
    assert window.canvas.tool() == "select"


@pytest.mark.parametrize("other", ["paper", "layout"])
def test_switching_from_text_panel_returns_to_select_tool(window, other):
    window.tool_actions["text"].trigger()
    assert window.canvas.tool() == "text"
    window.tool_actions[other].trigger()
    assert window.canvas.tool() == "select" and window.actions["tool.select"].isChecked()


def test_undo_and_redo_set_tool_by_restored_selection(window):
    _click(window.canvas, window.canvas.view_rect(0).center())
    window.actions["edit.cut"].trigger()
    assert window.canvas.selection() == [] and window.canvas.tool() == "text"
    _undo(window)                                            # Auswahl wieder [0]
    assert window.canvas.selection() == [0] and window.canvas.tool() == "select"
    _redo(window)                                            # Stand ohne Auswahl
    assert window.canvas.selection() == [] and window.canvas.tool() == "text"
    assert window.panels.currentWidget() is window.panel("text")


# --- Rückgängig: Kleinigkeiten ------------------------------------------------------
def test_nudges_back_to_start_leave_no_undo_step(window, qtbot):
    window.canvas.set_selection([1])
    _focus_canvas(window, qtbot)
    for key in (Qt.Key.Key_Right, Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_Left):
        QTest.keyClick(window.canvas, key)
    assert window.doc.objects[1].x_mm == pytest.approx(4)
    assert not window.actions["edit.undo"].isEnabled()


@pytest.mark.parametrize("step", ["paste", "create", "duplicate"])
def test_undo_on_paper_tab_stays_on_paper_tab(window, step):
    window.canvas.set_selection([0])
    window.copy_selected()
    {"paste": window.paste, "create": lambda: window.create_text(30, 12),
     "duplicate": window.duplicate_selected}[step]()
    if step == "create":
        window.panel("text").edit.setPlainText("Neu")
    window.tool_actions["paper"].trigger()
    _undo(window)
    assert window.panels.currentWidget() is window.panel("paper")
    _redo(window)
    assert window.panels.currentWidget() is window.panel("paper")
