"""Edit mode: writing directly on the label (stage 3d-1b)."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from labelwerk import layout
from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM
from labelwerk.render import to_utf16
from labelwerk.gui.main_window import MainWindow
from labelwerk.settings import Settings

NO_MOD = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
LEFT = Qt.MouseButton.LeftButton


def _doc(orientation="vertical", rotation=0):
    return Document("62", length_mm=40, orientation=orientation, objects=[
        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4, rotation=rotation),
        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=24)])


def _window(qtbot, doc=None):
    win = MainWindow(doc=doc if doc is not None else _doc(),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    win.activateWindow()
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


def _view_point(canvas, x_dots, y_dots):
    """Point in dots in reading direction → view coordinates."""
    return canvas.viewportTransform().map(canvas.sheet.mapToScene(QPointF(x_dots, y_dots)))


def _char_point(window, index, pos):
    """View point of the caret before character ``pos`` (half line height) in the object."""
    rendered = window.rendered[index]
    x, top, h = rendered.layout.caret(pos)
    point = layout.from_object((x, top + h / 2), rendered, window.doc.objects[index].rotation)
    return _view_point(window.canvas, *point)


def _session(window):
    return window.edit_session


def _empty_area(canvas):
    return canvas.view_rect(1).bottomRight() + QPointF(40, 40)


# --- Start --------------------------------------------------------------------------
def test_text_tool_click_starts_edit_mode_and_typing_lands_in_new_frame(window, qtbot):
    window.shortcut_actions["tool.text"].trigger()
    _click(window.canvas, _view_point(window.canvas, 30 * MM, 12 * MM))
    session = _session(window)
    assert session.active and session.index == 2
    editor = window.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    QTest.keyClicks(editor, "Neu")
    assert window.doc.objects[2].text == "Neu"
    assert window.rendered[2].layout.texts == ["Neu"]          # rendered immediately, without timer
    assert window.canvas.objects[2].rendered is window.rendered[2]


def test_double_click_starts_edit_mode_with_caret_at_click_point(window):
    _double_click(window.canvas, _char_point(window, 1, 2))
    session = _session(window)
    assert session.active and session.index == 1
    assert window.canvas.selection() == [1]
    assert window.panel("text").edit.textCursor().position() == 2
    assert window.panels.currentWidget() is window.panel("text")


def test_double_click_on_rotated_text_hits_the_right_character(qtbot):
    win = _window(qtbot, _doc(rotation=90))
    _double_click(win.canvas, _char_point(win, 0, 3))
    assert _session(win).index == 0
    assert win.panel("text").edit.textCursor().position() == 3


def test_click_into_selected_frame_does_not_start_edit_mode(window):
    window.canvas.set_selection([0])
    _click(window.canvas, window.canvas.view_rect(0).center())
    assert not _session(window).active
    assert window.canvas.selection() == [0]


def test_editor_has_focus_while_editing(window, qtbot):
    _double_click(window.canvas, _char_point(window, 0, 1))
    editor = window.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    _click(window.canvas, _char_point(window, 0, 3))         # click into the frame
    assert editor.hasFocus() and editor.textCursor().position() == 3
    assert _session(window).active


def test_contents_field_is_gone_from_the_panel(window):
    panel = window.panel("text")
    window.canvas.set_selection([0])
    assert panel.edit.width() == 0 and panel.edit.height() == 0
    assert panel.layout_.indexOf(panel.edit) == -1
    sections = [label.text() for label in panel.findChildren(type(panel.hint))
                if label.property("role") == "section"]
    assert "INHALT" not in sections


# --- End ---------------------------------------------------------------------------
def test_esc_ends_edit_mode_and_keeps_the_frame_selected(window, qtbot):
    _double_click(window.canvas, _char_point(window, 0, 1))
    editor = window.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert not _session(window).active
    assert window.canvas.selection() == [0]
    qtbot.waitUntil(window.canvas.hasFocus, timeout=1000)   # object shortcuts apply again
    assert window.canvas.editing() is None


def test_click_outside_ends_edit_mode(window):
    _double_click(window.canvas, _char_point(window, 0, 1))
    _click(window.canvas, _empty_area(window.canvas))
    assert not _session(window).active
    assert window.canvas.selection() == []


def test_click_on_other_object_ends_edit_mode_and_selects_it(window):
    _double_click(window.canvas, _char_point(window, 0, 1))
    _click(window.canvas, window.canvas.view_rect(1).center())
    assert not _session(window).active
    assert window.canvas.selection() == [1]


def test_empty_new_frame_is_removed_when_edit_mode_ends(window, qtbot):
    window.create_text(30, 12)
    editor = window.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
    assert window.canvas.selection() == []


# --- Appearance ----------------------------------------------------------------
def _expected_caret(window, index, pos):
    rendered = window.rendered[index]
    x, top, h = rendered.layout.caret(pos)
    rotation = window.doc.objects[index].rotation
    a = layout.from_object((x, top), rendered, rotation)
    b = layout.from_object((x, top + h), rendered, rotation)
    return _view_point(window.canvas, *a), _view_point(window.canvas, *b)


@pytest.mark.parametrize("orientation, rotation", [("vertical", 0), ("horizontal", 0),
                                                   ("vertical", 90), ("horizontal", 270)])
def test_caret_drawn_where_the_layout_puts_it(qtbot, orientation, rotation):
    win = _window(qtbot, _doc(orientation, rotation))
    _double_click(win.canvas, _char_point(win, 0, 2))
    line = win.canvas.caret_line()
    start, end = _expected_caret(win, 0, 2)
    assert line.p1().x() == pytest.approx(start.x(), abs=1)
    assert line.p1().y() == pytest.approx(start.y(), abs=1)
    assert line.p2().x() == pytest.approx(end.x(), abs=1)
    assert line.p2().y() == pytest.approx(end.y(), abs=1)


def test_caret_follows_typing_with_the_new_layout(window, qtbot):
    _double_click(window.canvas, _char_point(window, 0, 2))
    editor = window.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    editor.moveCursor(editor.textCursor().MoveOperation.End)
    QTest.keyClicks(editor, "XX")
    start, _ = _expected_caret(window, 0, 6)
    assert window.canvas.caret_line().p1().x() == pytest.approx(start.x(), abs=1)


def test_empty_frame_caret_starts_at_click_point(window):
    window.create_text(30, 12)
    line = window.canvas.caret_line()
    point = _view_point(window.canvas, 30 * MM, 12 * MM)
    assert line.p1().x() == pytest.approx(point.x(), abs=1)
    assert line.p1().y() == pytest.approx(point.y(), abs=1)
    assert line.length() > 0


def test_selection_is_drawn_over_the_marked_characters(window):
    _double_click(window.canvas, _char_point(window, 0, 1))
    editor = window.panel("text").edit
    cursor = editor.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(3, cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    rects = window.canvas.selection_rects()
    assert len(rects) == 1
    left, right = _char_point(window, 0, 1).x(), _char_point(window, 0, 3).x()
    assert rects[0].left() == pytest.approx(left, abs=1)
    assert rects[0].right() == pytest.approx(right, abs=1)


def test_edited_frame_has_no_handles(window):
    _double_click(window.canvas, _char_point(window, 0, 1))
    handles = window.canvas.handle_points(0)
    assert window.canvas._handle_at(handles["br"]) is None


def test_input_methods_get_the_caret_position_on_the_label(window, qtbot):
    _double_click(window.canvas, _char_point(window, 0, 2))
    editor = window.panel("text").edit
    rect = editor.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
    caret = window.canvas.caret_line()
    on_screen = editor.mapToGlobal(rect.topLeft())
    expected = window.canvas.viewport().mapToGlobal(caret.p1().toPoint())
    assert abs(on_screen.x() - expected.x()) <= 1 and abs(on_screen.y() - expected.y()) <= 1
    assert rect.height() == pytest.approx(caret.length(), abs=2)


def test_hidden_editor_does_not_wrap_so_home_and_end_cover_the_paragraph(qtbot):
    win = _window(qtbot, Document("62", length_mm=40, objects=[
        TextObject("Max Mustermann Musterstraße", size_pt=10, x_mm=2, y_mm=2)]))
    _double_click(win.canvas, _char_point(win, 0, 20))
    editor = win.panel("text").edit
    QTest.keyClick(editor, Qt.Key.Key_Home)
    assert editor.textCursor().position() == 0
    QTest.keyClick(editor, Qt.Key.Key_End)
    assert editor.textCursor().position() == len("Max Mustermann Musterstraße")


# --- Operation: mouse ------------------------------------------------------------------
CTRL = Qt.KeyboardModifier.ControlModifier


def _plain(text, x_mm, y_mm, align="center", rotation=0, size_pt=14):
    obj = TextObject.plain(text, size_pt=size_pt, align=align, bold=False)
    obj.x_mm, obj.y_mm, obj.rotation = x_mm, y_mm, rotation
    return obj


def _plain_doc(*objects):
    return Document("62", length_mm=60, objects=list(objects) or [
        _plain("Max Mustermann", 4, 4), _plain("Zwei", 4, 24)])


def _drag(canvas, start, end, modifiers=NO_MOD):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, modifiers)


def _editing(qtbot, doc=None, index=0, pos=1):
    """Window with object ``index`` in edit mode, caret before character ``pos``."""
    win = _window(qtbot, doc if doc is not None else _plain_doc())
    _double_click(win.canvas, _char_point(win, index, pos))
    editor = win.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    assert _session(win).index == index
    return win, editor


def _selection(editor):
    cursor = editor.textCursor()
    return cursor.selectionStart(), cursor.selectionEnd()


def test_drag_inside_frame_selects_text_and_bold_formats_only_the_selection(qtbot):
    win, editor = _editing(qtbot)
    before = (win.doc.objects[0].x_mm, win.doc.objects[0].y_mm)
    _drag(win.canvas, _char_point(win, 0, 4), _char_point(win, 0, 14))
    assert _selection(editor) == (4, 14)
    assert (win.doc.objects[0].x_mm, win.doc.objects[0].y_mm) == before   # not moved
    QTest.keyClick(editor, Qt.Key.Key_B, CTRL)
    spans = win.doc.objects[0].paragraphs[0].spans
    assert [(s.text, s.bold) for s in spans] == [("Max ", False), ("Mustermann", True)]
    assert _session(win).active


def test_double_click_in_edit_mode_selects_a_word(qtbot):
    win, editor = _editing(qtbot)
    _double_click(win.canvas, _char_point(win, 0, 7))
    assert editor.textCursor().selectedText() == "Mustermann"
    assert _session(win).active


def test_shift_click_extends_the_selection(qtbot):
    win, editor = _editing(qtbot, pos=2)
    _click(win.canvas, _char_point(win, 0, 9), SHIFT)
    assert _selection(editor) == (2, 9)


# --- Operation: keyboard --------------------------------------------------------------
def test_arrows_move_the_caret_in_edit_mode_and_the_object_outside(qtbot):
    win, editor = _editing(qtbot, pos=3)
    x = win.doc.objects[0].x_mm
    QTest.keyClick(editor, Qt.Key.Key_Left)
    assert editor.textCursor().position() == 2 and win.doc.objects[0].x_mm == x
    QTest.keyClick(editor, Qt.Key.Key_Right, SHIFT)
    assert _selection(editor) == (2, 3)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    qtbot.waitUntil(win.canvas.hasFocus, timeout=1000)
    QTest.keyClick(win.canvas, Qt.Key.Key_Left)
    assert win.doc.objects[0].x_mm == pytest.approx(x - 0.1)


def test_up_and_down_follow_the_lines_on_the_label(qtbot):
    win, editor = _editing(qtbot, _plain_doc(_plain("iiii\nWWWW", 4, 4, align="left")), pos=1)
    QTest.keyClick(editor, Qt.Key.Key_Down)
    text_layout = win.rendered[0].layout
    second = text_layout.lines[1]
    expected = text_layout.hit(text_layout.caret(1)[0], second.top + second.height / 2)
    assert editor.textCursor().position() == expected
    QTest.keyClick(editor, Qt.Key.Key_Up, SHIFT)
    assert _selection(editor) == (1, expected)
    QTest.keyClick(editor, Qt.Key.Key_Up)
    assert editor.textCursor().position() == 0                  # above the first line: the beginning


def test_home_end_and_enter(qtbot):
    win, editor = _editing(qtbot, pos=5)
    QTest.keyClick(editor, Qt.Key.Key_Home)
    assert editor.textCursor().position() == 0
    QTest.keyClick(editor, Qt.Key.Key_End)
    assert editor.textCursor().position() == len("Max Mustermann")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QTest.keyClicks(editor, "x")
    assert win.doc.objects[0].text == "Max Mustermann\nx"


def test_ctrl_a_selects_the_whole_text_of_the_frame_only(qtbot):
    win, editor = _editing(qtbot)
    QTest.keyClick(editor, Qt.Key.Key_A, CTRL)
    assert _selection(editor) == (0, len("Max Mustermann"))
    assert win.canvas.selection() == [0] and _session(win).active


def test_delete_and_backspace_delete_characters_not_the_object(qtbot):
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClick(editor, Qt.Key.Key_Delete)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert [o.text for o in win.doc.objects] == ["MaMustermann", "Zwei"]


def test_copy_and_paste_text_in_edit_mode(qtbot):
    win, editor = _editing(qtbot)
    _double_click(win.canvas, _char_point(win, 0, 1))      # word "Max"
    QTest.keyClick(editor, Qt.Key.Key_C, CTRL)
    QTest.keyClick(editor, Qt.Key.Key_End)
    QTest.keyClick(editor, Qt.Key.Key_V, CTRL)
    assert [o.text for o in win.doc.objects] == ["Max MustermannMax", "Zwei"]


def test_edit_bar_cut_and_paste_work_on_text_in_edit_mode(qtbot):
    win, editor = _editing(qtbot)
    _double_click(win.canvas, _char_point(win, 0, 1))
    win.shortcut_actions["edit.cut"].trigger()
    assert win.doc.objects[0].text == " Mustermann" and len(win.doc.objects) == 2
    win.shortcut_actions["edit.paste"].trigger()
    assert win.doc.objects[0].text == "Max Mustermann" and len(win.doc.objects) == 2


@pytest.mark.parametrize("name", ["copy", "cut", "paste"])
def test_clipboard_command_ending_edit_mode_does_not_fall_through_to_objects(qtbot, name):
    """If edit mode ends during the command, the command still counts as done –
    cutting then does not take the whole object along."""
    win, editor = _editing(qtbot)
    _double_click(win.canvas, _char_point(win, 0, 1))
    setattr(editor, name, win.finish_editing)               # ends edit mode immediately
    assert getattr(_session(win), name)() is True
    assert not _session(win).active and len(win.doc.objects) == 2


def test_end_edit_is_a_fixed_action_of_edit_mode(window):
    action = window.shortcut_actions["text.end_edit"]
    assert action in window.panel("text").actions()
    assert action.shortcut().toString() == "Esc"
    assert not action.isEnabled()                              # only in edit mode
    _double_click(window.canvas, _char_point(window, 0, 1))
    assert action.isEnabled()
    action.trigger()
    assert not _session(window).active


# --- Formatting ----------------------------------------------------------------------
def test_format_without_selection_in_edit_mode_applies_to_typing_only(qtbot):
    win, editor = _editing(qtbot, pos=3)
    win.panel("text").bold.click()
    qtbot.waitUntil(editor.hasFocus, timeout=1000)             # focus back to the caret
    QTest.keyClicks(editor, "X")
    spans = win.doc.objects[0].paragraphs[0].spans
    assert [(s.text, s.bold) for s in spans] == [("Max", False), ("X", True),
                                                 (" Mustermann", False)]


def test_format_outside_edit_mode_applies_to_the_whole_frame(window):
    window.doc.objects[0] = _plain("Max Mustermann", 4, 4)
    window.render_now()
    window.canvas.set_selection([0])
    window.panel("text").bold.click()
    assert all(s.bold for s in window.doc.objects[0].paragraphs[0].spans)


def test_size_for_typing_scales_the_caret(qtbot):
    win, editor = _editing(qtbot, pos=3)
    height = win.canvas.caret_line().length()
    win.panel("text").set_size_pt(28)                         # 14 → 28 pt, only for typing on
    assert win.doc.objects[0].text == "Max Mustermann"
    assert win.canvas.caret_line().length() == pytest.approx(2 * height, abs=2)


# --- Undo -----------------------------------------------------------------------
def test_one_finished_edit_is_one_undo_step(qtbot):
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClicks(editor, "XY")
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    _double_click(win.canvas, _char_point(win, 0, 6))
    QTest.keyClick(editor, Qt.Key.Key_I, CTRL)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert win.doc.objects[0].text == "MaxX Mustermann"
    win.shortcut_actions["edit.undo"].trigger()
    assert win.doc.objects[0] == _plain_doc().objects[0]
    win.shortcut_actions["edit.redo"].trigger()
    assert win.doc.objects[0].text == "MaxX Mustermann"


def test_ctrl_z_while_editing_is_the_editors_undo(qtbot):
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClicks(editor, "X")
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
    assert win.doc.objects[0].text == "Max Mustermann" and _session(win).active
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL | SHIFT)
    assert win.doc.objects[0].text == "MaxX Mustermann"
    win.shortcut_actions["edit.undo"].trigger()               # button: also in the editor
    assert win.doc.objects[0].text == "Max Mustermann" and _session(win).active
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert not win.shortcut_actions["edit.undo"].isEnabled()  # nothing changed: no step


def test_new_frame_and_its_text_are_one_undo_step(window, qtbot):
    window.shortcut_actions["tool.text"].trigger()
    _click(window.canvas, _view_point(window.canvas, 30 * MM, 12 * MM))
    editor = window.panel("text").edit
    QTest.keyClicks(editor, "Neu")
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    window.shortcut_actions["edit.undo"].trigger()
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]


# --- Frame grows --------------------------------------------------------------------
def _anchor(window, index):
    obj, rendered = window.doc.objects[index], window.rendered[index]
    return layout.from_object(rendered.layout.anchor(layout.anchor_align(obj)), rendered,
                              obj.rotation)


@pytest.mark.parametrize("align, rotation", [("left", 0), ("right", 0), ("center", 0),
                                             ("right", 90), ("left", 270)])
def test_frame_grows_at_the_edge_of_the_alignment(qtbot, align, rotation):
    doc = _plain_doc(_plain("Eins", 20, 10, align=align, rotation=rotation))
    win, editor = _editing(qtbot, doc, pos=2)
    before = _anchor(win, 0)
    QTest.keyClick(editor, Qt.Key.Key_End)
    QTest.keyClicks(editor, "Wjg")
    after = _anchor(win, 0)
    assert win.rendered[0].layout.texts == ["EinsWjg"]
    assert after == pytest.approx(before, abs=1)              # ±1 dot
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert _anchor(win, 0) == pytest.approx(before, abs=1)


def test_unpositioned_text_stays_centred_while_typing(qtbot):
    doc = Document("62", length_mm=40, objects=[TextObject.plain("Mitte", size_pt=14)])
    win, editor = _editing(qtbot, doc, pos=2)
    QTest.keyClicks(editor, "WWW")
    assert not win.doc.objects[0].positioned


def test_fixed_frame_keeps_its_frame_while_typing(qtbot):
    obj = _plain("Fest", 4, 4)
    obj.fit, obj.w_mm, obj.h_mm = True, 30.0, 10.0
    win, editor = _editing(qtbot, _plain_doc(obj), pos=2)
    QTest.keyClicks(editor, "WWW")
    after = win.doc.objects[0]
    assert (after.x_mm, after.y_mm, after.w_mm, after.h_mm) == (4, 4, 30.0, 10.0)


def test_editor_keeps_focus_for_input_methods(qtbot):
    win, editor = _editing(qtbot)
    assert QApplication.focusWidget() is editor
    assert editor.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
    _click(win.canvas, _char_point(win, 0, 5))
    assert QApplication.focusWidget() is editor
    win.panel("text").italic.click()
    assert QApplication.focusWidget() is editor



# --- New text: left-aligned from the click point ----------------------------------------
def test_new_text_starts_left_aligned_at_the_click_point_and_grows_to_the_right(window, qtbot):
    window.shortcut_actions["tool.text"].trigger()
    click = _view_point(window.canvas, 30 * MM, 12 * MM)
    _click(window.canvas, click)
    dot = window.canvas.px_per_mm() / MM                   # screen pixels per dot
    line = window.canvas.caret_line()
    assert line.p1().x() == pytest.approx(click.x(), abs=dot)
    assert line.p1().y() == pytest.approx(click.y(), abs=dot)
    editor = window.panel("text").edit
    QTest.keyClicks(editor, "Neu")
    obj, rendered = window.doc.objects[2], window.rendered[2]
    assert [p.align for p in obj.paragraphs] == ["left"]
    x, y = layout.from_object(rendered.layout.anchor("left"), rendered, 0)
    assert (x, y) == pytest.approx((30 * MM, 12 * MM), abs=1)
    assert rendered.x >= 30 * MM - 2 and rendered.w > 0          # grows to the right


# --- Focus stays in edit mode ---------------------------------------------------------
@pytest.mark.parametrize("key", [Qt.Key.Key_Tab, Qt.Key.Key_Backtab])
def test_tab_keeps_focus_in_the_text(qtbot, key):
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClick(QApplication.focusWidget(), key)
    assert QApplication.focusWidget() is editor
    QTest.keyClicks(QApplication.focusWidget(), "x")
    assert win.doc.objects[0].text == "Maxx Mustermann"           # Tab inserts nothing
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
    assert not _session(win).active


def test_click_on_panel_background_keeps_focus_in_the_text(qtbot):
    win, editor = _editing(qtbot, pos=3)
    panel = win.panel("text")
    QTest.mouseClick(panel, LEFT, NO_MOD, panel.rect().bottomLeft() + QPointF(5, -5).toPoint())
    assert QApplication.focusWidget() is editor
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
    assert not _session(win).active


def test_caret_is_hidden_while_the_text_has_no_focus(qtbot):
    win, editor = _editing(qtbot, pos=3)
    assert win.canvas.caret_shown()
    size = win.panel("text").size.lineEdit()
    size.setFocus()
    qtbot.waitUntil(size.hasFocus, timeout=1000)
    assert not win.canvas.caret_shown() and _session(win).active
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    assert win.canvas.caret_shown()


def test_hidden_editor_is_not_reachable_by_tab_outside_edit_mode(window, qtbot):
    window.canvas.set_selection([0])
    editor = window.panel("text").edit
    assert editor.focusPolicy() == Qt.FocusPolicy.NoFocus
    family = window.panel("text").family
    family.setFocus()
    qtbot.waitUntil(family.hasFocus, timeout=1000)
    QTest.keyClick(family, Qt.Key.Key_Backtab)
    assert QApplication.focusWidget() is not editor
    QTest.keyClicks(QApplication.focusWidget(), "zz")
    assert window.doc.objects[0].text == "Eins"


def test_keyboard_in_font_box_while_editing_stays_in_the_box(qtbot):
    win, editor = _editing(qtbot, pos=3)
    family = win.panel("text").family
    family.setFocus()
    qtbot.waitUntil(family.hasFocus, timeout=1000)
    start = family.currentIndex()
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)
    assert family.currentIndex() == min(start + 2, family.count() - 1)   # also with few fonts
    assert editor.textCursor().position() == 3 and not editor.hasFocus()
    family.showPopup()
    family.hidePopup()                                          # choice done: keep typing
    win.activateWindow()                                        # offscreen: the list took it along
    qtbot.waitUntil(editor.hasFocus, timeout=1000)


# --- Empty new frame is dropped on every path ---------------------------------------------
@pytest.mark.parametrize("leave", [lambda w: w.shortcut_actions["tool.select"].trigger(),
                                   lambda w: w.shortcut_actions["tool.text"].trigger(),
                                   lambda w: w.tool_actions["paper"].trigger(),
                                   lambda w: w.tool_actions["layout"].trigger()])
def test_empty_new_frame_is_dropped_on_every_exit(window, leave):
    window.create_text(30, 12)
    leave(window)
    assert not _session(window).active
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]


def test_undo_in_an_empty_new_frame_only_removes_the_frame(window):
    window.canvas.set_selection([1])
    window.nudge(1, 0)
    window.create_text(30, 12)
    window.shortcut_actions["edit.undo"].trigger()
    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
    assert window.doc.objects[1].x_mm == pytest.approx(5)          # moving stays
    window.shortcut_actions["edit.redo"].trigger()
    assert len(window.doc.objects) == 2                           # no empty frame comes back


def test_keyboard_undo_falls_through_like_the_button(qtbot):
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    win.canvas.set_selection([0])
    win.nudge(1, 0)                                              # step in the document
    _double_click(win.canvas, _char_point(win, 0, 3))
    QTest.keyClicks(editor, "X")
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)                   # in the editor
    assert win.doc.objects[0].text == "Max Mustermann" and _session(win).active
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)                   # on in the document
    assert not _session(win).active
    assert win.doc.objects[0].x_mm == pytest.approx(4)


def test_keyboard_undo_with_nothing_to_undo_keeps_edit_mode(qtbot):
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
    assert _session(win).active and win.doc.objects[0].text == "Max Mustermann"


# --- Frame encloses caret and selection ----------------------------------------
@pytest.mark.parametrize("rotation", [0, 90, 270])
def test_edit_frame_encloses_caret_and_selection(qtbot, rotation):
    win, editor = _editing(qtbot, _plain_doc(_plain("Max\nMustermann", 10, 10, rotation=rotation)),
                           pos=2)
    QTest.keyClick(editor, Qt.Key.Key_A, CTRL)
    frame = win.canvas.edit_frame_rect().adjusted(-1, -1, 1, 1)
    line = win.canvas.caret_line()
    assert frame.contains(line.p1()) and frame.contains(line.p2())
    assert win.canvas.selection_rects()
    assert all(frame.contains(rect) for rect in win.canvas.selection_rects())


# --- Characters outside the BMP (UTF-16) ---------------------------------------------------
def test_emoji_positions_for_click_caret_and_selection(qtbot):
    text = "a\U0001F600b c"
    win, editor = _editing(qtbot, _plain_doc(_plain(text, 4, 4, align="left")), pos=0)
    for pos in range(len(text) + 1):
        _click(win.canvas, _char_point(win, 0, pos))
        assert editor.textCursor().position() == to_utf16(text, pos)
        start, _ = _expected_caret(win, 0, pos)
        assert win.canvas.caret_line().p1().x() == pytest.approx(start.x(), abs=1)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(to_utf16(text, 2), cursor.MoveMode.KeepAnchor)   # "a😀"
    editor.setTextCursor(cursor)
    (rect,) = win.canvas.selection_rects()
    assert rect.left() == pytest.approx(_char_point(win, 0, 0).x(), abs=1)
    assert rect.right() == pytest.approx(_char_point(win, 0, 2).x(), abs=1)
    QTest.keyClicks(editor, "Z")
    assert win.doc.objects[0].text == "Zb c"


# --- Final round: Insert button, roll change, redo, F2/Enter -----------------
def test_paste_button_follows_the_system_clipboard_in_edit_mode(qtbot):
    win, editor = _editing(qtbot)
    QApplication.clipboard().setText("")
    win._update_edit_actions()
    assert not win.shortcut_actions["edit.paste"].isEnabled()
    _double_click(win.canvas, _char_point(win, 0, 1))              # select word
    QTest.keyClick(editor, Qt.Key.Key_C, CTRL)
    assert win.shortcut_actions["edit.paste"].isEnabled()
    QApplication.clipboard().setText("")
    assert not win.shortcut_actions["edit.paste"].isEnabled()


def test_clipboard_change_after_closing_the_window_does_not_crash(qtbot):
    win = _window(qtbot)
    win.close()
    win.deleteLater()
    QApplication.sendPostedEvents(None, 0)                         # DeferredDelete
    QApplication.clipboard().setText("nach dem Schließen")


def test_media_result_during_editing_is_its_own_undo_step(qtbot):
    from labelwerk.media import Media
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClicks(editor, "X")
    win._media_found(Media(29, 0, "endless"), "29")
    assert win.doc.label_id == "29"
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    win.shortcut_actions["edit.undo"].trigger()
    assert win.doc.objects[0].text == "Max Mustermann" and win.doc.label_id == "29"
    win.shortcut_actions["edit.undo"].trigger()
    assert win.doc.label_id == "62"
    win.shortcut_actions["edit.redo"].trigger()
    win.shortcut_actions["edit.redo"].trigger()
    assert win.doc.objects[0].text == "MaxX Mustermann" and win.doc.label_id == "29"


def test_redo_falls_through_to_the_document_like_undo(qtbot):
    win, editor = _editing(qtbot, pos=3)
    QTest.keyClicks(editor, "X")
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    win.shortcut_actions["edit.undo"].trigger()                    # text back, redo available
    assert win.doc.objects[0].text == "Max Mustermann"
    _double_click(win.canvas, _char_point(win, 0, 3))
    assert _session(win).active
    redo = win.shortcut_actions["edit.redo"]
    assert redo.isEnabled()                                        # button: continues in the document
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL | SHIFT)
    assert not _session(win).active
    assert win.doc.objects[0].text == "MaxX Mustermann"


def test_redo_in_edit_mode_with_nothing_to_redo_keeps_editing(qtbot):
    win, editor = _editing(qtbot, pos=3)
    assert not win.shortcut_actions["edit.redo"].isEnabled()
    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL | SHIFT)
    assert _session(win).active


@pytest.mark.parametrize("key", [Qt.Key.Key_F2, Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_f2_and_enter_start_edit_mode_with_caret_at_the_end(window, qtbot, key):
    window.canvas.set_selection([0])
    window.canvas.setFocus()
    qtbot.waitUntil(window.canvas.hasFocus, timeout=1000)
    QTest.keyClick(window.canvas, key)
    assert _session(window).index == 0
    editor = window.panel("text").edit
    assert editor.textCursor().position() == len("Eins")


def test_f2_needs_exactly_one_selected_object(window, qtbot):
    start = window.shortcut_actions["text.start_edit"]
    window.canvas.set_selection([0, 1])
    assert not start.isEnabled()
    window.canvas.set_selection([])
    assert not start.isEnabled()
    window.canvas.set_selection([1])
    assert start.isEnabled()


def test_start_edit_shortcuts_are_in_the_directory():
    from labelwerk import shortcuts
    assert shortcuts.action("text.start_edit").default == "F2"
    assert shortcuts.action("text.start_edit").scope == "canvas"
    enter = shortcuts.action("text.start_edit_enter")
    assert enter.fixed and enter.default == "Return"


def test_font_is_shown_again_after_deselect_and_reselect(qtbot):
    # Deselecting clears the font field; selecting again must show the font again
    win = MainWindow(settings=Settings(check_media_on_start=False, font_family="DejaVu Sans"))
    qtbot.addWidget(win)
    win.show()
    panel = win.panel("text")
    win.canvas.text_requested.emit(5.0, 5.0)
    QTest.keyClicks(panel.edit, "Test")
    QTest.keyClick(panel.edit, Qt.Key.Key_Escape)
    win.canvas.set_selection([])
    assert panel.family.currentText() == ""
    win.canvas.set_selection([0])
    assert panel.family.currentText() == "DejaVu Sans"


def test_caret_shows_with_a_detached_side_bar(qtbot):
    """Side bar as its own window: the input buffer (text panel) is in another window – the caret
    still shows while the canvas has the focus (review 2026-10-20)."""
    win = _window(qtbot)
    qtbot.waitExposed(win)
    win.panel_dock.setFloating(True)
    qtbot.wait(50)
    win.activateWindow()
    qtbot.wait(50)
    win.render_now()
    _double_click(win.canvas, _char_point(win, 0, 2))
    qtbot.waitUntil(lambda: _session(win).active, timeout=1000)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QGuiApplication, QKeyEvent
    target = QGuiApplication.focusWindow()
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QGuiApplication.sendEvent(target, QKeyEvent(kind, ord("X"), Qt.KeyboardModifier.ShiftModifier, "X"))
    qtbot.wait(50)
    assert "X" in win.panel("text").edit.toPlainText()
    assert win.canvas.caret_shown()
