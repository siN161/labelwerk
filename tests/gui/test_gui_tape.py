"""Canvas: remaining tape, closed start, cut line at the end, margin lines (acceptance 3d-1)."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from labelwerk import layout
from labelwerk.document import Document, TextObject
from labelwerk.gui.canvas import MM
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.labels import get_label
from labelwerk.render import render_document
from labelwerk.settings import Settings


def _window(qtbot, label="62", orientation="vertical", length=None):
    doc = Document(label, length_mm=length, orientation=orientation, margin_mm=3,
                   objects=[TextObject("A\nB", size_pt=14, x_mm=5, y_mm=5)])
    win = MainWindow(doc=doc, settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_tape_continues_in_feed_direction_behind_the_end(qtbot, orientation):
    win = _window(qtbot, orientation=orientation)
    canvas = win.canvas
    tape, outline = canvas.tape_rect(), canvas.outline.sceneBoundingRect()
    assert tape.top() == pytest.approx(outline.bottom()) and tape.height() > 0
    assert tape.left() == pytest.approx(outline.left())
    assert tape.width() == pytest.approx(outline.width())
    assert canvas.handle.sceneBoundingRect().intersects(tape)       # handle sits on the tape
    assert canvas.cut_edges() == ["end"]                            # start closed


def test_tape_is_not_part_of_label_size_or_print_image(qtbot):
    win = _window(qtbot)
    before = render_document(win.doc).size
    assert win._shown_size == (before[0], before[1])
    # the piece: print image plus the printer's feed at both ends
    assert win.canvas.outline.sceneBoundingRect().height() == pytest.approx(before[1] + 2 * 35)
    assert win.canvas.tape_rect().bottom() > before[1]


def test_die_cut_label_keeps_its_look_without_tape(qtbot):
    win = _window(qtbot, label="62x29", length=None)
    assert win.canvas.tape_rect().isEmpty() and win.canvas.cut_edges() == []


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_clicks_on_tape_do_nothing(qtbot, orientation):
    win = _window(qtbot, orientation=orientation)
    canvas = win.canvas
    center = canvas.tape_rect().center()
    pos = canvas.mapFromScene(center)
    canvas.set_tool("text")
    n = len(win.doc.objects)
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert len(win.doc.objects) == n and canvas.tool() == "text"
    canvas.set_tool("select")
    canvas.set_selection([0])
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert canvas.selection() == []                                  # like a click into empty space
    assert len(win.doc.objects) == n


@pytest.mark.parametrize("label", ["62", "62x29"])
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_canvas_draws_all_four_margins(qtbot, label, orientation):
    win = _window(qtbot, label=label, orientation=orientation, length=None)
    canvas = win.canvas
    area = layout.printable_area(win.doc, win.model, win._shown_size)
    drawn = canvas.printable.mapRectToScene(canvas.printable.rect())
    sheet = canvas.sheet.mapRectToScene(canvas.sheet.rect())
    # area in reading direction → scene: same size as the area, margin in tape direction visible
    along = (area.y, win._shown_size[1] * 25.4 / 300 - area.bottom) if orientation == "vertical" \
        else (area.x, win._shown_size[0] * 25.4 / 300 - area.right)
    # margin 3 mm from the paper edge: the unprintable strip (die-cut) or the printer's feed
    # (continuous tape) counts too
    label_ = get_label(label)
    edge = label_.feed_margin if label_.height is None else (label_.total_height - label_.height) // 2
    expected = max(0, round(3 * 300 / 25.4) - edge) * 25.4 / 300
    assert along[0] == pytest.approx(expected, abs=0.1)
    assert along[1] == pytest.approx(expected, abs=0.1)
    assert drawn.width() * drawn.height() == pytest.approx(area.w * area.h * MM * MM, rel=0.01)
    assert sheet.contains(drawn)


def test_start_has_no_selection_frame(qtbot):
    win = _window(qtbot)
    fresh = MainWindow(settings=Settings(check_media_on_start=False))
    qtbot.addWidget(fresh)
    assert fresh.canvas.selection() == []


def test_orientation_names_are_plain(qtbot):
    dialog = SettingsDialog(Settings(check_media_on_start=False))
    qtbot.addWidget(dialog)
    assert [dialog.orientation.itemText(i) for i in range(2)] == ["Horizontal", "Vertikal"]
    win = _window(qtbot)
    panel = win.panel("paper")
    assert "Querformat" in panel.horizontal.toolTip() and "Hochformat" in panel.vertical.toolTip()
    assert "Text" not in panel.horizontal.toolTip() + panel.vertical.toolTip()


@pytest.mark.parametrize("label", ["62", "62x29"])
@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_canvas_shades_strips_the_printer_does_not_print(qtbot, label, orientation):
    """Across (total_width − width) / 2, along the tape the feed or the margin of the die-cut label:
    light grey, display only – no clicks, below the content, not in the print image (scene y =
    tape direction, also with "horizontal")."""
    win = _window(qtbot, label=label, orientation=orientation, length=None)
    canvas = win.canvas
    strips = canvas.unprintable
    assert strips.acceptedMouseButtons() == Qt.MouseButton.NoButton
    lbl = get_label(label)
    box = canvas.outline.sceneBoundingRect()
    across = (lbl.total_width - lbl.width) / 2
    along = lbl.feed_margin if lbl.height is None else (lbl.total_height - lbl.height) / 2
    path, mid = strips.path(), box.center()
    assert path.contains(QPointF(box.left() + across / 2, mid.y()))
    assert path.contains(QPointF(box.right() - across / 2, mid.y()))
    assert path.contains(QPointF(mid.x(), box.top() + along / 2))
    assert path.contains(QPointF(mid.x(), box.bottom() - along / 2))
    assert not path.contains(mid)
    assert not path.contains(QPointF(box.left() + across + 1, box.top() + along + 1))
    stack = canvas.scene().items()                      # topmost first
    assert stack.index(canvas.sheet) < stack.index(strips) < stack.index(canvas.outline)
    assert render_document(win.doc).size == (win._shown_size if orientation == "vertical"
                                              else win._shown_size[::-1])


def test_round_label_has_no_shaded_strip_inside_the_circle(qtbot):
    win = _window(qtbot, label="d24")
    assert not win.canvas.unprintable.path().contains(win.canvas.outline.sceneBoundingRect().center())
