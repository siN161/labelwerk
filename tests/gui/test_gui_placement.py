"""Arbeitsfläche mit Objekten: Auswahl, Ziehen, Einrasten, Anfasser, Tastatur (Etappe 3d-1)."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QKeySequence, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from labelwerk import layout
from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import ObjectItem, to_qimage
from labelwerk.gui.main_window import MainWindow
from labelwerk.labels import DPI
from labelwerk.render import render_document, render_object
from labelwerk.settings import Settings

NO_MOD = Qt.KeyboardModifier.NoModifier
ALT = Qt.KeyboardModifier.AltModifier
CTRL = Qt.KeyboardModifier.ControlModifier
LEFT = Qt.MouseButton.LeftButton
DOT_MM = 25.4 / DPI


def _doc(orientation="vertical", length_mm=40):
    return Document("62", length_mm=length_mm, orientation=orientation, objects=[
        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=20)])


def _window(qtbot, doc, settings=None):
    win = MainWindow(doc=doc, settings=settings)
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def window(qtbot):
    return _window(qtbot, _doc())


def _send(canvas, kind, pos, buttons, modifiers=NO_MOD):
    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)),
                        button, buttons, modifiers)
    QApplication.sendEvent(canvas.viewport(), event)


def _click(canvas, pos, modifiers=NO_MOD):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, pos, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton, modifiers)


def _press_move(canvas, start, end, modifiers=NO_MOD):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT, modifiers)
    middle = (start + end) / 2
    _send(canvas, QMouseEvent.Type.MouseMove, middle, LEFT, modifiers)
    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT, modifiers)


def _drag(canvas, start, end, modifiers=NO_MOD):
    _press_move(canvas, start, end, modifiers)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, modifiers)


def _center(canvas, index):
    return canvas.view_rect(index).center()


# --- Elemente ---------------------------------------------------------------------
def test_canvas_shows_one_item_per_object(window):
    items = window.canvas.objects
    assert len(items) == 2 and all(isinstance(item, ObjectItem) for item in items)
    assert [item.index for item in items] == [0, 1]


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_canvas_shows_the_object_images_that_are_printed(qtbot, orientation):
    doc = _doc(orientation)
    doc.objects.append(TextObject("Mitte"))
    win = _window(qtbot, doc)
    for obj, item in zip(doc.objects, win.canvas.objects):
        rendered = render_object(obj, doc)
        assert item.rendered.image.tobytes() == rendered.image.tobytes()
        assert (item.pos().x(), item.pos().y()) == (rendered.x, rendered.y)
        shown = item.pixmap().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        assert shown == to_qimage(rendered.image)
    assert win.image.tobytes() == render_document(doc).tobytes()


def test_horizontal_view_shows_objects_in_reading_direction(qtbot):
    win = _window(qtbot, _doc("horizontal", length_mm=60))
    first, second = win.canvas.view_rect(0), win.canvas.view_rect(1)
    assert second.top() > first.bottom()                   # „Zwei“ steht unter „Eins“
    assert first.width() > first.height()                  # Text liegt waagrecht


def test_only_changed_objects_are_rendered_again(window, monkeypatch):
    calls = []
    real = render_object

    def counting(obj, doc, model="QL-600"):
        calls.append(obj.text)
        return real(obj, doc, model)

    monkeypatch.setattr("labelwerk.gui.main_window.render_object", counting)
    window.render_now()
    assert calls == []
    window.doc.objects[1] = layout.place(window.doc.objects[1], layout.Rect(10, 25, 0, 0))
    window.render_now()
    assert calls == ["Zwei"]


# --- Auswahl ----------------------------------------------------------------------
def test_click_selects_ctrl_click_toggles_empty_click_clears(window):
    canvas = window.canvas
    seen = []
    canvas.selection_changed.connect(seen.append)
    _click(canvas, _center(canvas, 1))
    assert canvas.selection() == [1]
    _click(canvas, _center(canvas, 0), CTRL)
    assert canvas.selection() == [1, 0]
    _click(canvas, _center(canvas, 1), CTRL)
    assert canvas.selection() == [0]
    empty = canvas.view_rect(1).bottomRight() + QPointF(40, 40)
    _click(canvas, empty)
    assert canvas.selection() == []
    assert seen == [[1], [1, 0], [0], []]


def test_click_on_selected_object_of_many_selects_only_it(window):
    canvas = window.canvas
    canvas.select_all()
    assert canvas.selection() == [0, 1]
    _click(canvas, _center(canvas, 1))
    assert canvas.selection() == [1]


def test_selection_survives_rendering(window):
    window.canvas.set_selection([1])
    window.render_now()
    assert window.canvas.selection() == [1]


# --- Verschieben ------------------------------------------------------------------
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_drag_moves_object_and_updates_model_on_release(qtbot, orientation):
    win = _window(qtbot, _doc(orientation, length_mm=60))
    canvas = win.canvas
    ppm = canvas.px_per_mm()
    start = _center(canvas, 0)
    end = start + QPointF(80, 40)                          # rechts und unten in Leserichtung
    _press_move(canvas, start, end, ALT)
    assert canvas.view_rect(0).center().x() == pytest.approx(end.x(), abs=1)
    assert win.doc.objects[0].x_mm == 4                   # Modell erst beim Loslassen
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, ALT)
    obj = win.doc.objects[0]
    assert obj.x_mm == pytest.approx(4 + 80 / ppm, abs=0.01)
    assert obj.y_mm == pytest.approx(4 + 40 / ppm, abs=0.01)
    assert win.doc.objects[1].x_mm == 4
    assert canvas.view_rect(0).center().x() == pytest.approx(end.x(), abs=1)


def test_drag_moves_all_selected_objects(window):
    canvas = window.canvas
    canvas.select_all()
    start = _center(canvas, 0)
    _drag(canvas, start, start + QPointF(50, 0), ALT)
    moved = 50 / canvas.px_per_mm()
    assert [o.x_mm for o in window.doc.objects] == pytest.approx([4 + moved] * 2, abs=0.01)


def test_click_without_moving_leaves_model_untouched(window):
    before = [o.x_mm for o in window.doc.objects]
    _click(window.canvas, _center(window.canvas, 0))
    assert [o.x_mm for o in window.doc.objects] == before


def test_first_drag_of_automatic_object_fixes_its_size(qtbot):
    win = _window(qtbot, Document("62", objects=[TextObject("Hallo")]))
    base_pt = win.canvas.objects[0].rendered.base_pt
    start = _center(win.canvas, 0)
    _drag(win.canvas, start, start + QPointF(0, 30), ALT)
    obj = win.doc.objects[0]
    assert obj.positioned and not obj.fit
    assert obj.size_pt == round(base_pt, 1)


def test_typing_keeps_position_of_moved_object(window, qtbot):
    start = _center(window.canvas, 0)
    _drag(window.canvas, start, start + QPointF(30, 0), ALT)
    x = window.doc.objects[0].x_mm
    window.panel("text").edit.setPlainText("Eins!")
    assert window.doc.objects[0].text == "Eins!"
    assert (window.doc.objects[0].x_mm, window.doc.objects[0].y_mm) == (x, 4)


@pytest.mark.parametrize("modifiers", [NO_MOD, ALT])
def test_drag_snaps_to_label_center_unless_alt(window, modifiers):
    canvas = window.canvas
    ppm = canvas.px_per_mm()
    label = layout.label_rect(window.doc)
    rect = layout.object_rect(canvas.objects[0].rendered)
    # Mitte des Objekts landet 2 Bildschirmpixel neben der Etikettmitte (Toleranz 6 px)
    dx = round((label.cx - rect.cx) * ppm) + 2
    start = _center(canvas, 0)
    _press_move(canvas, start, start + QPointF(dx, 0), modifiers)
    guides = canvas.guides()
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, start + QPointF(dx, 0),
          Qt.MouseButton.NoButton, modifiers)
    printed = layout.object_rect(canvas.objects[0].rendered)
    offset = printed.cx - label.cx
    if modifiers == ALT:
        assert offset == pytest.approx(2 / ppm, abs=0.6 / ppm)
        assert guides == []
    else:
        assert abs(offset) <= DOT_MM                       # genauer geht der Druck nicht
        assert ("x", pytest.approx(label.cx)) in guides
    assert canvas.guides() == []                           # Hilfslinien nur beim Ziehen


def test_render_waits_while_dragging(window):
    canvas = window.canvas
    start = _center(canvas, 0)
    _press_move(canvas, start, start + QPointF(30, 0), ALT)
    item = canvas.objects[0]
    window.render_now()                                    # z. B. verzögertes Rendern
    assert canvas.objects[0] is item and canvas.is_dragging()
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, start + QPointF(30, 0),
          Qt.MouseButton.NoButton, ALT)
    assert window.doc.objects[0].x_mm > 4


# --- Anfasser ---------------------------------------------------------------------
def test_selected_object_has_eight_handles(window):
    window.canvas.set_selection([0])
    handles = window.canvas.handle_points(0)
    assert set(handles) == {"tl", "t", "tr", "r", "br", "b", "bl", "l"}
    rect = window.canvas.view_rect(0)
    assert handles["tl"] == rect.topLeft() and handles["br"] == rect.bottomRight()


def test_corner_drag_scales_font(window):
    canvas = window.canvas
    canvas.set_selection([0])
    rect = canvas.view_rect(0)
    corner = canvas.handle_points(0)["br"]
    _drag(canvas, corner, corner + QPointF(rect.width() / 2, rect.height() / 2))
    obj = window.doc.objects[0]
    assert obj.size_pt == pytest.approx(21, abs=0.6)
    assert not obj.fit and (obj.x_mm, obj.y_mm) == pytest.approx((4, 4), abs=0.1)


def test_edge_drag_turns_fixed_frame_on(window):
    canvas = window.canvas
    canvas.set_selection([0])
    before = layout.object_rect(canvas.objects[0].rendered)
    edge = canvas.handle_points(0)["r"]
    _drag(canvas, edge, edge + QPointF(10 * canvas.px_per_mm(), 0))
    obj = window.doc.objects[0]
    assert obj.fit
    assert obj.w_mm == pytest.approx(before.w + 10, abs=0.2)
    assert obj.h_mm == pytest.approx(before.h, abs=0.01)
    assert window.panel("text").fit.isChecked()            # Panel zeigt das Modell


def test_handle_drag_on_fixed_frame_changes_frame(qtbot):
    doc = _doc()
    doc.objects[0] = TextObject("Eins", size_pt=14, fit=True, x_mm=4, y_mm=4, w_mm=20, h_mm=8)
    win = _window(qtbot, doc)
    canvas = win.canvas
    canvas.set_selection([0])
    ppm = canvas.px_per_mm()
    corner = canvas.handle_points(0)["br"]
    _drag(canvas, corner, corner + QPointF(10 * ppm, 2 * ppm))
    obj = win.doc.objects[0]
    assert (obj.w_mm, obj.h_mm) == pytest.approx((30, 10), abs=0.2)
    assert obj.size_pt == 14


# --- Tastatur ---------------------------------------------------------------------
def _focus(window, qtbot):
    window.activateWindow()
    window.canvas.setFocus()
    qtbot.waitUntil(lambda: window.canvas.hasFocus(), timeout=1000)


def test_arrow_keys_nudge_selected_object(window, qtbot):
    window.canvas.set_selection([1])
    _focus(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_Left)
    assert window.doc.objects[1].x_mm == pytest.approx(3.9)
    QTest.keyClick(window.canvas, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert window.doc.objects[1].y_mm == pytest.approx(21)
    assert (window.doc.objects[0].x_mm, window.doc.objects[0].y_mm) == (4, 4)


def test_arrow_keys_without_selection_do_nothing(window, qtbot):
    _focus(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_Right)
    assert [o.x_mm for o in window.doc.objects] == [4, 4]


def test_delete_removes_selected_objects(window, qtbot):
    window.canvas.set_selection([0])
    _focus(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_Delete)
    assert [o.text for o in window.doc.objects] == ["Zwei"]
    assert window.canvas.selection() == []
    assert window.panel("text").index is None              # nichts mehr ausgewählt
    assert len(window.canvas.objects) == 1


def test_select_all_and_delete_leaves_no_object(window, qtbot):
    _focus(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_A, CTRL)
    assert window.canvas.selection() == [0, 1]
    QTest.keyClick(window.canvas, Qt.Key.Key_Delete)
    assert window.doc.objects == [] and window.canvas.objects == []
    assert window.panel("text").edit.toPlainText() == ""


def test_shortcuts_come_from_settings(qtbot):
    win = _window(qtbot, _doc(), Settings(shortcuts={"object.nudge_left": "Ctrl+J"}))
    assert win.actions["object.nudge_left"].shortcut() == QKeySequence("Ctrl+J")
    win.canvas.set_selection([0])
    _focus(win, qtbot)
    QTest.keyClick(win.canvas, Qt.Key.Key_J, CTRL)
    assert win.doc.objects[0].x_mm == pytest.approx(3.9)


# --- Hinweise ---------------------------------------------------------------------
def test_object_outside_label_shows_status_hint(qtbot):
    doc = _doc()
    doc.objects[1] = TextObject("Zwei", size_pt=14, x_mm=55, y_mm=20)
    win = _window(qtbot, doc)
    assert "Objekt ragt über das Etikett hinaus" in win.result.text()
    win.canvas.set_selection([1])
    win.canvas.nudge(-30, 0)
    assert "ragt" not in win.result.text()
