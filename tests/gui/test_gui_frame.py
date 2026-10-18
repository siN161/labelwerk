"""Zierrahmen in der GUI: Bereich „Rahmen“ im Reiter Papier, Arbeitsfläche, Ausrichten am Innenraum."""
import pytest
from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from labelwerk import layout, storage
from labelwerk.document import Document, Frame, ImageObject, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.app import apply_theme
from labelwerk.gui.main_window import MainWindow
from labelwerk.render import render_document
from labelwerk.settings import Settings

STYLES = ["Kein", "Einfach", "Doppelt", "Dick-dünn", "Gestrichelt", "Gepunktet", "Nur Ecken"]


def _window(qtbot, doc=None):
    win = MainWindow(doc=doc or Document("62x29", objects=[TextObject("Hallo")]),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    win.render_now()
    return win


def _choose(paper, title):
    paper.frame_style.setCurrentIndex(paper.frame_style.findText(title))


def test_frame_section_lists_the_styles_with_previews(qtbot):
    paper = _window(qtbot).panel("paper")
    combo = paper.frame_style
    assert [combo.itemText(i) for i in range(combo.count())] == STYLES
    assert all(not combo.itemIcon(i).isNull() for i in range(1, combo.count()))
    assert combo.currentText() == "Kein"
    for widget in (paper.frame_rounded, paper.frame_line, paper.frame_inset, paper.frame_padding):
        assert not widget.isEnabled()


def test_choosing_a_style_sets_the_frame_and_shows_it(qtbot):
    win = _window(qtbot)
    paper = win.panel("paper")
    _choose(paper, "Doppelt")
    win.render_now()
    assert win.doc.frame == Frame("double")
    assert all(w.isEnabled() for w in (paper.frame_rounded, paper.frame_line, paper.frame_inset,
                                       paper.frame_padding))
    assert win.image.tobytes() == render_document(win.doc).tobytes()
    assert win.image.getpixel((12, 130))[0] == 0
    _choose(paper, "Kein")
    assert win.doc.frame is None


def test_fields_change_the_frame(qtbot):
    win = _window(qtbot)
    paper = win.panel("paper")
    _choose(paper, "Einfach")
    paper.frame_rounded.setChecked(True)
    paper.frame_line.setValue(1.2)
    paper.frame_inset.setValue(2.0)
    paper.frame_padding.setValue(0.5)
    assert win.doc.frame == Frame("single", rounded=True, line_mm=1.2, inset_mm=2.0, padding_mm=0.5)


def test_field_limits_follow_the_core(qtbot):
    from labelwerk.document import FRAME_LINE_MM, MAX_FRAME_MM
    from labelwerk.gui.panels.paper import PaperPanel
    paper = PaperPanel(Document())
    qtbot.addWidget(paper)
    assert (paper.frame_line.minimum(), paper.frame_line.maximum()) == FRAME_LINE_MM
    assert paper.frame_inset.maximum() == paper.frame_padding.maximum() == MAX_FRAME_MM
    assert not paper.frame_line.keyboardTracking()       # erst bei Enter/Verlassen ein Schritt


def test_each_change_is_one_undo_step(qtbot):
    win = _window(qtbot)
    paper = win.panel("paper")
    _choose(paper, "Gestrichelt")
    paper.frame_line.setValue(1.0)
    win.shortcut_actions["edit.undo"].trigger()
    assert win.doc.frame == Frame("dashed")
    assert paper.frame_line.value() == 0.5
    win.shortcut_actions["edit.undo"].trigger()
    assert win.doc.frame is None and paper.frame_style.currentText() == "Kein"


def test_refresh_shows_the_frame_of_an_opened_label(qtbot):
    doc = Document("62x29", objects=[TextObject("A")],
                   frame=Frame("dotted", rounded=True, line_mm=0.3, inset_mm=1, padding_mm=2))
    paper = _window(qtbot, doc).panel("paper")
    assert paper.frame_style.currentText() == "Gepunktet"
    assert paper.frame_rounded.isChecked()
    assert (paper.frame_line.value(), paper.frame_inset.value(), paper.frame_padding.value()) == (
        0.3, 1.0, 2.0)


def test_round_labels_offer_no_corners_and_no_rounding(qtbot):
    win = _window(qtbot, Document("d24", objects=[TextObject("A")], frame=Frame("single")))
    paper = win.panel("paper")
    corners = paper.frame_style.findText("Nur Ecken")
    assert not paper.frame_style.model().item(corners).isEnabled()
    assert not paper.frame_rounded.isEnabled()
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert paper.frame_style.model().item(corners).isEnabled() and paper.frame_rounded.isEnabled()


def test_canvas_shows_the_frame_but_it_takes_no_clicks(qtbot):
    win = _window(qtbot)
    assert win.canvas.frame_item is None
    _choose(win.panel("paper"), "Einfach")
    win.render_now()
    item = win.canvas.frame_item
    assert item is not None and not item.pixmap().isNull()
    assert item.acceptedMouseButtons() == Qt.MouseButton.NoButton
    assert item.zValue() < min(o.zValue() for o in win.canvas.objects)
    assert (item.pixmap().width(), item.pixmap().height()) == win._shown_size


def test_frame_error_is_shown_like_other_render_errors(qtbot):
    win = _window(qtbot, Document("d12", objects=[TextObject("A")]))
    paper = win.panel("paper")
    _choose(paper, "Einfach")
    paper.frame_inset.setValue(10)
    win.render_now()
    assert "Rahmen passt nicht" in win.result.text()


def test_align_to_paper_uses_the_inner_room(qtbot):
    doc = Document("62x29", objects=[TextObject("A", size_pt=12, x_mm=20, y_mm=10)],
                   frame=Frame("single"))
    win = _window(qtbot, doc)
    inner = layout.frame_area(win.doc)
    win.canvas.set_selection([0])
    win.align_selected("left", paper=True)
    frame = layout.exact_rect(win.doc.objects[0], win.rendered[0])
    assert frame.x == pytest.approx(inner.x, abs=0.001)


def test_maximize_uses_the_inner_room(qtbot):
    doc = Document("62x29", objects=[TextObject("A", size_pt=12, x_mm=20, y_mm=10)],
                   frame=Frame("single"))
    win = _window(qtbot, doc)
    inner = layout.frame_area(win.doc)
    win.canvas.set_selection([0])
    win.maximize_selected()
    frame = layout.exact_rect(win.doc.objects[0], win.rendered[0])
    assert inner.x - 0.001 <= frame.x and frame.right <= inner.right + 0.001
    assert inner.y - 0.001 <= frame.y and frame.bottom <= inner.bottom + 0.001


def _send(canvas, kind, pos, buttons):
    button = (Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
              else Qt.MouseButton.NoButton)
    QApplication.sendEvent(canvas.viewport(), QMouseEvent(
        kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)), button, buttons,
        Qt.KeyboardModifier.NoModifier))


def test_canvas_snaps_to_the_inner_room(qtbot):
    win = _window(qtbot, Document("62x29", objects=[TextObject("A", size_pt=12, x_mm=20, y_mm=10)],
                                  frame=Frame("single", padding_mm=3)))
    canvas = win.canvas
    inner = layout.frame_area(win.doc)
    rect = layout.object_rect(canvas.objects[0].rendered)
    start = canvas.view_rect(0).center()
    end = start + QPointF(round((inner.x - rect.x) * canvas.px_per_mm()) + 2, 0)   # 2 px daneben
    left = Qt.MouseButton.LeftButton
    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, left)
    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, left)
    _send(canvas, QMouseEvent.Type.MouseMove, end, left)
    assert ("x", pytest.approx(inner.x)) in canvas.guides()
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    assert layout.object_rect(canvas.objects[0].rendered).x == pytest.approx(inner.x, abs=0.1)
    win.panel("paper").frame_style.setCurrentIndex(0)
    win.render_now()
    assert win.canvas._inner is None


# --- Nachbesserungen nach dem Review ------------------------------------------------------
def _type(box, value):
    """Wert ins Feld tippen, ohne Enter (Feld hat den Fokus, meldet aber noch nichts)."""
    box.lineEdit().selectAll()
    box.lineEdit().insert(box.textFromValue(value))


def test_typed_value_counts_when_printing_right_away(qtbot, monkeypatch):
    win = _window(qtbot)
    paper = win.panel("paper")
    _choose(paper, "Einfach")
    _type(paper.frame_line, 2.0)
    monkeypatch.setattr(main_window.QApplication, "focusWidget", lambda: paper.frame_line)
    printed = []
    monkeypatch.setattr(win, "_print", lambda image, doc, outside: printed.append(doc.frame))
    win.print_label()
    assert printed == [Frame("single", line_mm=2.0)]


def test_typed_value_counts_when_saving_right_away(qtbot, monkeypatch, tmp_path):
    win = _window(qtbot)
    paper = win.panel("paper")
    _choose(paper, "Einfach")
    _type(paper.frame_padding, 4.0)
    monkeypatch.setattr(main_window.QApplication, "focusWidget", lambda: paper.frame_padding)
    win.files.ask_save_file = lambda suggested: str(tmp_path / "r.labelwerk")
    win.shortcut_actions["file.save"].trigger()
    assert storage.load(tmp_path / "r.labelwerk").frame == Frame("single", padding_mm=4.0)


def test_canvas_frame_is_smoothed_and_reused(qtbot):
    win = _window(qtbot)
    _choose(win.panel("paper"), "Einfach")
    win.render_now()
    item = win.canvas.frame_item
    assert item.transformationMode() == Qt.TransformationMode.SmoothTransformation
    pixmap = item.pixmap().cacheKey()
    win.doc.objects[0] = TextObject("Anders")
    win.render_now()                                   # Rahmen unverändert: Bild bleibt
    assert win.canvas.frame_item.pixmap().cacheKey() == pixmap


@pytest.mark.parametrize("theme", ["rawblock", "classic"])
def test_frame_fields_are_not_cut_off(qtbot, theme):
    apply_theme(QApplication.instance(), theme)
    try:
        win = _window(qtbot)
        win.resize(1200, 900)
        win.tool_actions["paper"].trigger()
        QApplication.processEvents()
        paper = win.panel("paper")
        for box in (paper.frame_line, paper.frame_inset, paper.frame_padding):
            longest = box.textFromValue(box.maximum()) + box.suffix()        # „10.0 mm“
            edit = box.lineEdit()
            room = edit.width() - edit.textMargins().left() - edit.textMargins().right()
            assert room >= edit.fontMetrics().horizontalAdvance(longest), longest
        for label in paper.frame_labels:
            assert isinstance(label, QLabel) and label.width() >= label.sizeHint().width()
    finally:
        apply_theme(QApplication.instance(), "classic")


def test_values_stay_when_switching_to_none_and_back(qtbot):
    win = _window(qtbot)
    paper = win.panel("paper")
    _choose(paper, "Einfach")
    paper.frame_line.setValue(1.5)
    _choose(paper, "Kein")
    paper.refresh()                                    # z. B. Rückgängig eines anderen Schritts
    _choose(paper, "Einfach")
    assert win.doc.frame == Frame("single", line_mm=1.5)


def test_inserted_images_and_symbols_fit_the_inner_room(qtbot):
    win = _window(qtbot, Document("62x29", objects=[], frame=Frame("double")))
    inner = layout.frame_area(win.doc)
    big = ImageObject.from_image(Image.new("RGB", (3000, 3000), "black"), 300, "gross.png")
    win._insert_images([big], None, [])
    obj = win.doc.objects[-1]
    assert inner.y - 0.001 <= obj.y_mm and obj.y_mm + obj.h_mm <= inner.bottom + 0.001
    assert win._symbol_mm() <= min(inner.w, inner.h)


def test_round_label_explains_the_circle(qtbot):
    win = _window(qtbot, Document("d24", objects=[TextObject("A")], frame=Frame("single")))
    paper = win.panel("paper")
    assert "Kreis" in paper.frame_style.toolTip()
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert "Kreis" not in paper.frame_style.toolTip()


def test_paper_sections_put_orientation_above_margins_and_frame(qtbot):
    paper = _window(qtbot).panel("paper")
    layout_ = paper.layout_
    sections = [layout_.itemAt(i).widget().text() for i in range(layout_.count())
                if isinstance(layout_.itemAt(i).widget(), QLabel)
                and layout_.itemAt(i).widget().property("role") == "section"]
    assert sections == ["ETIKETT", "LÄNGE", "AUSRICHTUNG", "RÄNDER", "RAHMEN"]
