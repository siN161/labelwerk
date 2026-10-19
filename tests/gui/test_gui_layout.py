"""Reiter „Layout“: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Etappe 3d-1)."""
from importlib import resources

import pytest
from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from labelwerk import layout
from labelwerk.document import Document, TextObject
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.panels.layout import LAYOUT_SECTIONS
from labelwerk.gui.tools import TOOLS
from labelwerk.i18n import _
from labelwerk.labels import DPI
from labelwerk.settings import Settings

DOT_MM = 25.4 / DPI
NO_MOD = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
LEFT = Qt.MouseButton.LeftButton
SELECTED_ALIGN = ("align.left", "align.hcenter", "align.right",
                  "align.top", "align.vcenter", "align.bottom")
PAPER_ALIGN = tuple(key.replace("align.", "align.paper_") for key in SELECTED_ALIGN)
FROM_ONE = PAPER_ALIGN + ("size.maximize", "object.rotate_left", "object.rotate_right",
                          "object.bring_forward", "object.send_backward")
FROM_TWO = SELECTED_ALIGN + ("size.same", "size.width", "size.height")


def _doc():
    return Document("62", length_mm=40, objects=[
        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
        TextObject("Zweiter", size_pt=14, x_mm=12, y_mm=18),
        TextObject("Drei", size_pt=14, fit=True, x_mm=8, y_mm=30, w_mm=20, h_mm=6)])


def _window(qtbot, doc=None):
    win = MainWindow(doc=doc if doc is not None else _doc(),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def window(qtbot):
    return _window(qtbot)


def _panel(window):
    return window.panel("layout")


def _press(window, key):
    """Knopf im Reiter „Layout“ drücken."""
    button = _panel(window).buttons[key]
    assert button.isEnabled(), key
    button.click()


def _frames(window):
    return [layout.exact_rect(o, r) for o, r in zip(window.doc.objects, window.rendered)]


# --- Reiter -----------------------------------------------------------------------
def test_layout_tool_follows_text_and_image(window):
    assert [tool.key for tool in TOOLS][1:6] == ["paper", "text", "image", "barcode", "layout"]
    window.tool_actions["layout"].trigger()
    assert window.panels.currentWidget() is _panel(window)


def test_selecting_keeps_layout_panel(window):
    window.tool_actions["layout"].trigger()
    window.canvas.set_selection([0])
    window.canvas.set_selection([0, 1])
    assert window.panels.currentWidget() is _panel(window)
    assert window.tool_actions["layout"].isChecked()
    assert window.panel("text").index == 1                  # Text-Panel folgt trotzdem


def test_panel_has_sections_like_p_touch(window):
    titles = [_(title) for title, __ in LAYOUT_SECTIONS]
    assert titles == ["Gewählte Objekte ausrichten", "Am Papier ausrichten",
                      "Größe ändern", "Drehen", "Reihenfolge"]
    keys = [key for _, row in LAYOUT_SECTIONS for key, _ in row]
    assert set(keys) == set(FROM_ONE + FROM_TWO) and len(keys) == 20
    assert set(_panel(window).buttons) == set(keys)


def test_buttons_are_icons_with_tooltips_from_actions(window):
    folder = resources.files("labelwerk.gui") / "icons"
    for _, row in LAYOUT_SECTIONS:
        for key, icon in row:
            button = _panel(window).buttons[key]
            assert isinstance(button, QToolButton)
            assert button.defaultAction() is window.shortcut_actions[key]
            assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
            assert not button.icon().isNull()
            for color in ("black", "white"):
                assert (folder / f"{icon}-{color}.svg").is_file()
    tip = _panel(window).buttons["object.rotate_right"].toolTip()
    assert "rechts" in tip and "Ctrl+R" in tip


@pytest.mark.parametrize("selection, enabled", [
    ([], ()), ([0], FROM_ONE), ([0, 1], FROM_ONE + FROM_TWO)])
def test_buttons_enabled_by_selection_count(window, selection, enabled):
    window.canvas.set_selection(selection)
    for key, button in _panel(window).buttons.items():
        assert button.isEnabled() == (key in enabled), key


# --- Ausrichten -------------------------------------------------------------------
@pytest.mark.parametrize("mode, attr", [("left", "x"), ("hcenter", "cx"), ("right", "right"),
                                        ("top", "y"), ("vcenter", "cy"), ("bottom", "bottom")])
def test_align_selected_moves_only_selected(window, mode, attr):
    before = _frames(window)
    window.canvas.set_selection([0, 1])
    _press(window, f"align.{mode}")
    expected = getattr(layout.align(before[:2], mode)[0], attr)
    after = _frames(window)
    assert [getattr(r, attr) for r in after[:2]] == pytest.approx([expected] * 2, abs=0.001)
    assert after[2] == before[2]
    assert window.canvas.selection() == [0, 1]


@pytest.mark.parametrize("mode, attr", [("left", "x"), ("hcenter", "cx"), ("right", "right"),
                                        ("top", "y"), ("vcenter", "cy"), ("bottom", "bottom")])
def test_align_to_paper(window, mode, attr):
    area = layout.printable_area(window.doc)
    window.canvas.set_selection([2])
    _press(window, f"align.paper_{mode}")
    assert getattr(_frames(window)[2], attr) == pytest.approx(getattr(area, attr), abs=0.001)


def test_maximize(window):
    area = layout.printable_area(window.doc)
    window.canvas.set_selection([2])
    _press(window, "size.maximize")
    obj = window.doc.objects[2]
    assert max(obj.w_mm / area.w, obj.h_mm / area.h) == pytest.approx(1)
    assert (obj.x_mm + obj.w_mm / 2, obj.y_mm + obj.h_mm / 2) == pytest.approx(
        (area.cx, area.cy), abs=0.001)


@pytest.mark.parametrize("mode", ["same", "width", "height"])
def test_same_size_scales_text_without_fixed_frame(qtbot, mode):
    doc = Document("62", length_mm=40, objects=[TextObject("Wort", size_pt=28, x_mm=2, y_mm=2),
                                                 TextObject("Wort", size_pt=14, x_mm=2, y_mm=25)])
    win = _window(qtbot, doc)
    win.canvas.set_selection([0, 1])                        # Bezug: zuerst gewähltes
    _press(win, f"size.{mode}")
    obj = win.doc.objects[1]
    assert obj.size_pt == pytest.approx(28, abs=0.6) and not obj.fit
    assert (obj.x_mm, obj.y_mm) == (2, 25)


@pytest.mark.parametrize("mode, size", [("same", (20, 6)), ("width", (20, 3)),
                                        ("height", (10, 6))])
def test_same_size_sets_fixed_frame(qtbot, mode, size):
    doc = Document("62", length_mm=40, objects=[
        TextObject("A", size_pt=14, fit=True, x_mm=2, y_mm=2, w_mm=20, h_mm=6),
        TextObject("B", size_pt=14, fit=True, x_mm=2, y_mm=25, w_mm=10, h_mm=3)])
    win = _window(qtbot, doc)
    win.canvas.set_selection([0, 1])
    _press(win, f"size.{mode}")
    obj = win.doc.objects[1]
    assert (obj.w_mm, obj.h_mm) == size and (obj.x_mm, obj.y_mm) == (2, 25)


# --- Drehen -----------------------------------------------------------------------
@pytest.mark.parametrize("key, rotation", [("object.rotate_right", 90),
                                           ("object.rotate_left", 270)])
def test_rotate_keeps_center(window, key, rotation):
    window.canvas.set_selection([1])
    before = window.canvas.objects[1].frame_mm()
    _press(window, key)
    after = window.canvas.objects[1].frame_mm()
    assert window.doc.objects[1].rotation == rotation
    assert (after.w, after.h) == pytest.approx((before.h, before.w), abs=DOT_MM)
    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=DOT_MM)


def test_rotate_shortcut_on_canvas(window, qtbot):
    window.canvas.set_selection([0])
    window.activateWindow()
    window.canvas.setFocus()
    qtbot.waitUntil(window.canvas.hasFocus, timeout=1000)
    QTest.keyClick(window.canvas, Qt.Key.Key_R, CTRL)
    assert window.doc.objects[0].rotation == 90


def _send(canvas, kind, pos, buttons):
    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)),
                        button, buttons, NO_MOD)
    QApplication.sendEvent(canvas.viewport(), event)


def _drag(canvas, start, end):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


def _rotated(window, index):
    window.canvas.set_selection([index])
    _press(window, "object.rotate_right")
    return window.canvas.objects[index].frame_mm()


def test_edge_handle_of_rotated_text_turns_fixed_frame_on(window):
    canvas = window.canvas
    before = _rotated(window, 0)
    edge = canvas.handle_points(0)["b"]                    # Höhe auf dem Etikett = Breite ungedreht
    _drag(canvas, edge, edge + QPointF(0, 10 * canvas.px_per_mm()))
    obj = window.doc.objects[0]
    assert obj.fit and obj.rotation == 90
    assert (obj.w_mm, obj.h_mm) == pytest.approx((before.h + 10, before.w), abs=0.2)
    after = canvas.objects[0].frame_mm()
    assert (after.x, after.y, after.w, after.h) == pytest.approx(
        (before.x, before.y, before.w, before.h + 10), abs=0.2)


def test_edge_handle_of_rotated_fixed_frame(window):
    canvas = window.canvas
    before = _rotated(window, 2)                            # 20 × 6 mm, gedreht 6 × 20
    assert (before.w, before.h) == pytest.approx((6, 20), abs=DOT_MM)
    edge = canvas.handle_points(2)["r"]
    _drag(canvas, edge, edge + QPointF(4 * canvas.px_per_mm(), 0))
    obj = window.doc.objects[2]
    assert (obj.w_mm, obj.h_mm) == pytest.approx((20, 10), abs=0.2)
    assert canvas.objects[2].frame_mm().w == pytest.approx(10, abs=0.2)


def test_corner_handle_of_rotated_text_scales_font(window):
    canvas = window.canvas
    before = _rotated(window, 0)
    corner = canvas.handle_points(0)["br"]
    rect = canvas.view_rect(0)
    _drag(canvas, corner, corner + QPointF(rect.width() / 2, rect.height() / 2))
    obj = window.doc.objects[0]
    assert obj.size_pt == pytest.approx(21, abs=0.6) and not obj.fit
    after = canvas.objects[0].frame_mm()
    assert (after.x, after.y) == pytest.approx((before.x, before.y), abs=0.2)
    assert after.w == pytest.approx(before.w * 1.5, rel=0.08)


# --- Reihenfolge ------------------------------------------------------------------
def test_bring_forward_and_send_backward_follow_selection(window):
    window.canvas.set_selection([0])
    _press(window, "object.bring_forward")
    assert [o.text for o in window.doc.objects] == ["Zweiter", "Eins", "Drei"]
    assert window.canvas.selection() == [1]
    _press(window, "object.bring_forward")
    assert [o.text for o in window.doc.objects] == ["Zweiter", "Drei", "Eins"]
    assert window.canvas.selection() == [2]
    _press(window, "object.send_backward")
    assert [o.text for o in window.doc.objects] == ["Zweiter", "Eins", "Drei"]
    assert window.canvas.selection() == [1]
    assert window.panel("text").edit.toPlainText() == "Eins"   # Panel folgt dem Objekt


def test_undo_and_redo_of_reorder_keep_selection_on_same_objects(window):
    window.canvas.set_selection([0])
    _press(window, "object.bring_forward")
    assert window.canvas.selection() == [1]
    window.shortcut_actions["edit.undo"].trigger()
    assert [o.text for o in window.doc.objects] == ["Eins", "Zweiter", "Drei"]
    assert [window.doc.objects[i].text for i in window.canvas.selection()] == ["Eins"]
    assert window.panel("text").edit.toPlainText() == "Eins"
    window.shortcut_actions["edit.redo"].trigger()
    assert [window.doc.objects[i].text for i in window.canvas.selection()] == ["Eins"]


def test_undo_keeps_panel(window):
    """Rückgängig wechselt nicht vom Reiter Layout weg, auch wenn sich die Auswahl ändert."""
    window.canvas.set_selection([0])
    window.tool_actions["layout"].trigger()
    window.canvas.set_selection([])
    window.canvas.set_selection([2])
    _press(window, "object.send_backward")
    window._show_tool("paper")
    window.shortcut_actions["edit.undo"].trigger()
    assert window.panels.currentWidget() is window.panel("paper")
    assert [window.doc.objects[i].text for i in window.canvas.selection()] == ["Drei"]


def test_order_of_several_selected(window):
    window.canvas.set_selection([1, 0])
    _press(window, "object.bring_forward")
    assert [o.text for o in window.doc.objects] == ["Drei", "Eins", "Zweiter"]
    assert window.canvas.selection() == [2, 1]


# --- Rückgängig -------------------------------------------------------------------
@pytest.mark.parametrize("key", FROM_ONE + FROM_TWO)
def test_each_operation_is_one_undo_step(window, key):
    window.canvas.set_selection([1, 2] if key in FROM_TWO else [1])
    before = [o.text for o in window.doc.objects], _frames(window)
    _press(window, key)
    assert window.shortcut_actions["edit.undo"].isEnabled()
    window.shortcut_actions["edit.undo"].trigger()
    assert ([o.text for o in window.doc.objects], _frames(window)) == before
    assert not window.shortcut_actions["edit.undo"].isEnabled()


# --- Symbole je Design ------------------------------------------------------------
def _color(icon: QIcon, mode=QIcon.Mode.Normal, state=QIcon.State.Off):
    image = icon.pixmap(QSize(16, 16), mode, state).toImage()
    pixels = [image.pixelColor(x, y) for x in range(16) for y in range(16)]
    ink = [c for c in pixels if c.alpha() > 200]
    return {(c.red(), c.green(), c.blue()) for c in ink}


def test_icons_turn_white_on_hover_only_in_rawblock(window):
    button = _panel(window).buttons["align.left"]
    assert _color(button.icon()) == {(0, 0, 0)}
    assert _color(button.icon(), QIcon.Mode.Active) == {(255, 255, 255)}
    window.panel("layout").set_icon_style(False)
    assert _color(button.icon(), QIcon.Mode.Active) == {(0, 0, 0)}


# --- Schlussrunde -------------------------------------------------------------------
@pytest.mark.parametrize("key", ["size.same", "size.width", "size.height"])
def test_match_with_empty_frame_selected_changes_nothing(qtbot, key, capsys):
    doc = Document("62", length_mm=60, objects=[TextObject("Eins", size_pt=20, x_mm=10, y_mm=30)])
    win = _window(qtbot, doc)
    win.create_text(5, 5)                           # leerer Rahmen, Index 1, ausgewählt
    win.canvas.set_selection([1, 0])                # Strg+Klick auf „Eins“
    before = [(o.text, o.size_pt, o.x_mm, o.y_mm) for o in win.doc.objects]
    win.shortcut_actions[key].trigger()
    assert [(o.text, o.size_pt, o.x_mm, o.y_mm) for o in win.doc.objects] == before
    assert win.doc.objects[0].size_pt == 20
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("key", ["size.same", "size.width", "size.height"])
def test_match_with_empty_frame_and_two_objects_uses_visible_reference(qtbot, key):
    doc = Document("62", length_mm=60, objects=[
        TextObject("Eins", size_pt=20, x_mm=10, y_mm=30), TextObject("Zwei", size_pt=10, x_mm=10, y_mm=10)])
    win = _window(qtbot, doc)
    win.create_text(5, 5)
    win.canvas.set_selection([2, 0, 1])             # leerer Rahmen zuerst gewählt
    win.shortcut_actions[key].trigger()
    assert win.doc.objects[0].size_pt == 20          # Bezug (erstes sichtbares) bleibt
    assert win.doc.objects[1].size_pt != 10          # das andere wurde angeglichen


def test_render_error_then_delete_keeps_canvas_in_step(qtbot):
    doc = Document("62", length_mm=None, objects=[
        TextObject("A", size_pt=14, x_mm=2, y_mm=2), TextObject("Mitte", size_pt=14)])
    win = _window(qtbot, doc)
    win.canvas.set_selection([1])
    win.doc.objects[1].paragraphs = TextObject("W" * 80, size_pt=40).paragraphs   # zu groß
    win.doc.objects[1].size_pt = 40
    win.render_now()
    assert win._render_error is not None
    win.canvas.set_selection([0])
    win.delete_selected()
    assert win.doc.objects[0].text == "W" * 80
    assert win.canvas.objects == [] and win.rendered == []      # kein Bild des gelöschten Objekts
    assert win.canvas.selection() == []
    before = win.doc.objects[0].x_mm
    win.canvas.objects_moved.emit([0], [layout.Rect(9, 9, 5, 5)])
    assert win.doc.objects[0].x_mm == before                    # nichts verschoben


@pytest.mark.parametrize("orientation, growing", [
    ("vertical", ("top", "vcenter", "bottom")), ("horizontal", ("left", "hcenter", "right"))])
def test_paper_align_along_growing_axis_is_enabled_with_hint(qtbot, orientation, growing):
    doc = Document("62", length_mm=None, orientation=orientation, objects=[
        TextObject("A", size_pt=14, x_mm=2, y_mm=2)])
    win = _window(qtbot, doc)
    win.canvas.set_selection([0])
    panel = _panel(win)
    hint = "gleichem Rand an beiden Enden"
    for mode in ("left", "hcenter", "right", "top", "vcenter", "bottom"):
        button = panel.buttons[f"align.paper_{mode}"]
        assert button.isEnabled(), mode
        assert (hint in button.defaultAction().toolTip()) == (mode in growing), mode
    win.doc.length_mm = 40                            # feste Länge: kein Hinweis mehr
    win.render_now()
    assert hint not in panel.buttons[f"align.paper_{growing[0]}"].defaultAction().toolTip()


@pytest.mark.parametrize("margin", [3, 6])             # 3 mm: Etikett auf Mindestlänge geklemmt
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_paper_align_along_growing_axis_gives_equal_margins(qtbot, orientation, margin):
    vertical = orientation == "vertical"
    doc = Document("62", length_mm=None, orientation=orientation, margin_mm=margin, objects=[
        TextObject("Zeile 1\nZeile 2", size_pt=14, x_mm=5, y_mm=6)])
    win = _window(qtbot, doc)
    win.canvas.set_selection([0])
    win.shortcut_actions["align.paper_vcenter" if vertical else "align.paper_hcenter"].trigger()
    r = layout.object_rect(win.rendered[0])
    w, h = win._shown_size
    length = (h if vertical else w) * DOT_MM
    start, end = (r.y, r.bottom) if vertical else (r.x, r.right)
    assert abs(start - (length - end)) <= 2 * DOT_MM


def test_paper_align_top_ignores_minimum_length_when_other_objects_lengthen_label(qtbot):
    """Nur der Titel gewählt, ein zweiter Text macht das Etikett lang: „Oben am Etikett“ setzt
    den Titel an den Anfang, nicht mittig in die Mindestlänge."""
    doc = Document("62", length_mm=None, orientation="vertical", margin_mm=1, objects=[
        TextObject("Titel", size_pt=12, x_mm=5, y_mm=10),
        TextObject("Unten", size_pt=12, x_mm=5, y_mm=60)])
    win = _window(qtbot, doc)
    win.canvas.set_selection([0])
    win.shortcut_actions["align.paper_top"].trigger()
    assert win.doc.objects[0].y_mm == pytest.approx(0, abs=0.01)
    assert win.doc.objects[1].y_mm == 60


def test_canvas_grabbed_is_not_stale_after_selection_drops(qtbot):
    win = _window(qtbot)
    win.canvas._grabbed = 2
    win.canvas.set_selection([0])
    assert win.canvas._grabbed in (-1, 0)
