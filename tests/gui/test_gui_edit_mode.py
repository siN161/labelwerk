"""Schreibmodus: direkt auf dem Etikett schreiben (Etappe 3d-1b)."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from labelwerk import layout
from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM
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
    """Punkt in Druckpunkten in Leserichtung → Ansichtskoordinaten."""
    return canvas.viewportTransform().map(canvas.sheet.mapToScene(QPointF(x_dots, y_dots)))


def _char_point(window, index, pos):
    """Ansichtspunkt der Schreibmarke vor Zeichen ``pos`` (halbe Zeilenhöhe) im Objekt."""
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
    assert window.rendered[2].layout.texts == ["Neu"]          # sofort gerendert, ohne Timer
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
    _click(window.canvas, _char_point(window, 0, 3))         # Klick in den Rahmen
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


# --- Ende ---------------------------------------------------------------------------
def test_esc_ends_edit_mode_and_keeps_the_frame_selected(window, qtbot):
    _double_click(window.canvas, _char_point(window, 0, 1))
    editor = window.panel("text").edit
    qtbot.waitUntil(editor.hasFocus, timeout=1000)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert not _session(window).active
    assert window.canvas.selection() == [0]
    qtbot.waitUntil(window.canvas.hasFocus, timeout=1000)   # Objekt-Kürzel gelten wieder
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


# --- Darstellung --------------------------------------------------------------------
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
