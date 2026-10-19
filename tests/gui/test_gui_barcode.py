"""Reiter BARCODE: einfügen, Art, Inhalt live, Prüfhinweise, Größe, Anfasser, Doppelklick,
Spalte einfügen, Serie drucken, Rückgängig."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from labelwerk import barcodes
from labelwerk.document import BarcodeObject, Document, Numbering, Series, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.main_window import MainWindow
from labelwerk.layout import barcode_rect
from labelwerk.printer import to_print_mode
from labelwerk.render import render_document
from labelwerk.series import fill
from labelwerk.settings import Settings
from labelwerk.shortcuts import ACTIONS

LEFT = Qt.MouseButton.LeftButton
MM = 300 / 25.4


def _window(qtbot, doc=None):
    win = MainWindow(doc=doc if doc is not None else Document("62x29"),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    win.render_now()
    return win


def _with_barcode(qtbot, kind="qr", doc=None):
    win = _window(qtbot, doc)
    panel = win.panel("barcode")
    panel.kind.setCurrentIndex(panel.kind.findData(kind))
    panel.kind.activated.emit(panel.kind.currentIndex())
    panel.insert.click()
    win.render_now()
    return win, panel


def _send(canvas, kind, pos, buttons):
    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)), button,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(canvas.viewport(), event)


def _drag(canvas, start, end):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


def _double_click(canvas, pos):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, pos, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)
    _send(canvas, QMouseEvent.Type.MouseButtonDblClick, pos, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)


def _type(panel, text):
    """Inhalt tippen und mit Enter abschließen (wie am Feld)."""
    panel.data.setFocus()
    panel.data.selectAll()
    QTest.keyClicks(panel.data, text)
    QTest.keyClick(panel.data, Qt.Key.Key_Return)


# --- Reiter und Einfügen -------------------------------------------------------------------------
def test_barcode_tab_without_selection(qtbot):
    win = _window(qtbot)
    win.tool_actions["barcode"].trigger()
    panel = win.panel("barcode")
    assert win.panels.currentWidget() is panel
    assert panel.hint.isVisible() and not panel.data.isEnabled() and panel.insert.isEnabled()
    assert [panel.kind.itemData(i) for i in range(panel.kind.count())] == [
        "qr", "code128", "code39", "ean13", "ean8"]
    assert panel.error.isVisible() and not panel.height.isVisible()
    panel.kind.setCurrentIndex(panel.kind.findData("code128"))
    panel.kind.activated.emit(panel.kind.currentIndex())
    assert panel.height.isVisible() and panel.text.isVisible() and not panel.error.isVisible()
    assert win.doc.objects == []


def test_insert_action_is_in_the_shortcut_registry():
    assert any(a.id == "barcode.insert" and a.scope == "canvas" for a in ACTIONS)


@pytest.mark.parametrize("kind", ["qr", "code128", "ean13"])
def test_insert_puts_the_sample_in_the_middle_and_selects_it(qtbot, kind):
    win, panel = _with_barcode(qtbot, kind)
    obj, = win.doc.objects
    assert isinstance(obj, BarcodeObject) and obj.kind == kind
    assert obj.data == barcodes.SAMPLES[kind]
    assert win.canvas.selection() == [0] and win.panels.currentWidget() is panel
    assert panel.index == 0 and panel.data.text() == obj.data
    assert panel.data.selectedText() == obj.data              # Tippen ersetzt das Beispiel
    rect, area = barcode_rect(obj), win._paper_area()
    assert (rect.cx, rect.cy) == (pytest.approx(area.cx, abs=0.01), pytest.approx(area.cy, abs=0.01))
    assert len(win.rendered) == 1


def test_insert_is_one_undo_step(qtbot):
    win, _ = _with_barcode(qtbot)
    win.undo()
    assert win.doc.objects == []


# --- Inhalt ------------------------------------------------------------------------------------
def test_typing_changes_the_content_live_and_is_one_step(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    panel.data.setFocus()
    panel.data.selectAll()
    QTest.keyClicks(panel.data, "X1-")
    assert win.doc.objects[0].data == "X1-"                   # schon vor Enter
    QTest.keyClicks(panel.data, "K3")
    QTest.keyClick(panel.data, Qt.Key.Key_Return)
    win.render_now()
    assert win.doc.objects[0].data == "X1-K3"
    assert win.rendered[0].w == barcodes.size(win.doc.objects[0])[0]
    win.undo()
    assert win.doc.objects[0].data == barcodes.SAMPLES["code128"]


def test_invalid_content_shows_the_reason_and_a_placeholder(qtbot, monkeypatch):
    win, panel = _with_barcode(qtbot, "ean13")
    _type(panel, "4006")
    win.render_now()
    assert panel.check.text() == "EAN-13 braucht 12 oder 13 Ziffern (4 eingegeben)"
    assert panel.check.isVisible()
    shown = win.rendered[0]                                   # schraffierter Platzhalter
    assert shown.image.tobytes() == barcodes.placeholder(shown.w, shown.h).tobytes()
    assert "EAN-13 braucht" in win.result.text()
    printed = []
    monkeypatch.setattr(main_window, "PrintWorker", lambda *a, **k: printed.append(a))
    win.print_label()
    assert printed == [] and "EAN-13 braucht" in win.result.text()


def test_ean_shows_the_completed_check_digit(qtbot):
    win, panel = _with_barcode(qtbot, "ean13")
    assert panel.check.text() == "Mit Prüfziffer: 5901234123457"
    _type(panel, "5901234123457")
    assert panel.check.text() == "" and not panel.check.isVisible()


def test_quiet_zone_hint(qtbot):
    _, panel = _with_barcode(qtbot, "code128")
    assert panel.quiet.text() == "Ruhezone: links und rechts je 2,5 mm frei lassen"
    _, qr = _with_barcode(qtbot, "qr")
    assert qr.quiet.text() == "Ruhezone: ringsum 2,0 mm frei lassen"


# --- Art und Größe -----------------------------------------------------------------------------
def test_changing_the_kind_replaces_only_the_sample(qtbot):
    win, panel = _with_barcode(qtbot, "qr")
    panel.kind.setCurrentIndex(panel.kind.findData("code128"))
    panel.kind.activated.emit(panel.kind.currentIndex())
    obj = win.doc.objects[0]
    assert (obj.kind, obj.data, obj.module) == ("code128", "ABC-123", 3)
    _type(panel, "Eigener Text")
    panel.kind.setCurrentIndex(panel.kind.findData("code39"))
    panel.kind.activated.emit(panel.kind.currentIndex())
    assert (win.doc.objects[0].kind, win.doc.objects[0].data) == ("code39", "Eigener Text")
    win.undo()
    assert win.doc.objects[0].kind == "code128"


def test_module_is_shown_in_millimetres(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    assert panel.module.text() == "0.25 mm"
    panel.module.setValue(4)
    assert win.doc.objects[0].module == 4 and panel.module.text() == "0.34 mm"
    assert panel.module.valueFromText("0.5") == 6 and panel.module.valueFromText("0,5") == 6
    assert panel.module.valueFromText("x") == 4
    win.undo()
    assert win.doc.objects[0].module == 3


def test_height_text_and_error_level(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    panel.height.setValue(14.5)
    panel.text.click()
    obj = win.doc.objects[0]
    assert (obj.h_mm, obj.text) == (14.5, False)
    win, qr = _with_barcode(qtbot, "qr")
    qr.error.setCurrentIndex(qr.error.findData("H"))
    qr.error.activated.emit(qr.error.currentIndex())
    assert win.doc.objects[0].error == "H"


def test_position_fields_snap_the_module(qtbot):
    win, panel = _with_barcode(qtbot, "qr")
    side = barcode_rect(win.doc.objects[0]).w
    panel.position.spins["w"].setValue(round(side * 4 / 6, 1))   # Modul 6 → 4
    assert win.doc.objects[0].module == 4


def test_qr_handle_keeps_the_square_and_snaps(qtbot):
    win, _ = _with_barcode(qtbot, "qr")
    canvas = win.canvas
    point = canvas.handle_points(0)["r"]
    _drag(canvas, point, point + QPointF(5 * canvas.px_per_mm(), 0))
    obj = win.doc.objects[0]
    rect = barcode_rect(obj)
    assert obj.module > 6 and rect.w == pytest.approx(rect.h)
    assert win.rendered[0].w == win.rendered[0].h == barcodes.modules(obj) * obj.module


def test_bar_code_bottom_handle_changes_the_height(qtbot):
    win, _ = _with_barcode(qtbot, "code128")
    canvas = win.canvas
    point = canvas.handle_points(0)["b"]
    _drag(canvas, point, point + QPointF(0, 3 * canvas.px_per_mm()))
    obj = win.doc.objects[0]
    assert obj.module == 3 and obj.h_mm == pytest.approx(13.0, abs=0.15)


# --- Arbeitsfläche ------------------------------------------------------------------------------
def test_double_click_focuses_the_content(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    win.tool_actions["paper"].trigger()
    win.canvas.set_selection([])
    _double_click(win.canvas, win.canvas.view_rect(0).center())
    assert win.panels.currentWidget() is panel and win.canvas.selection() == [0]
    assert panel.data.selectedText() == "ABC-123"
    assert not win.edit_session.active


def test_barcode_rotates_like_other_objects(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    panel.rotate_right.click()
    assert win.doc.objects[0].rotation == 90


# --- Serie --------------------------------------------------------------------------------------
def test_column_replaces_the_sample_or_is_appended(qtbot):
    win, panel = _with_barcode(qtbot, "code128",
                               Document("62x29", series=Series(numbering=Numbering(count=3))))
    win.panel("series").refresh()
    win.insert_column("Nummer")
    assert win.doc.objects[0].data == "{Nummer}"
    win.insert_column("Nummer")
    assert win.doc.objects[0].data == "{Nummer}{Nummer}"
    assert panel.data.text() == "{Nummer}{Nummer}"


def test_series_prints_the_filled_barcode(qtbot, monkeypatch):
    doc = Document("62x29", objects=[BarcodeObject(kind="code128", data="X{Nummer}", x_mm=3,
                                                   y_mm=3)],
                   series=Series(numbering=Numbering(count=2)))
    win = _window(qtbot, doc)
    win.panel("series").refresh()
    jobs = []

    class Fake:
        def __init__(self, image, label_id, model, cut_every=1):
            jobs.append(image)
            from labelwerk.gui.print_worker import PrintSignals
            self.signals = PrintSignals()
    monkeypatch.setattr(main_window, "PrintWorker", Fake)
    monkeypatch.setattr(main_window.QThreadPool.globalInstance(), "start", lambda worker: None)
    win.ask_print_count = lambda n: True
    win.print_label()
    images, = jobs
    assert [i.tobytes() for i in images] == [
        to_print_mode(render_document(fill(doc, ["Nummer"], [n]))).tobytes() for n in ("1", "2")]


def test_invalid_row_names_the_row(qtbot, monkeypatch):
    doc = Document("62x29", objects=[BarcodeObject(kind="ean8", data="{Nummer}", x_mm=3, y_mm=3)],
                   series=Series(numbering=Numbering(count=2)))
    win = _window(qtbot, doc)
    win.panel("series").refresh()
    win.render_now()
    assert "Zeile 1: EAN-8 braucht" in win.result.text()


# --- Nachbesserungen nach dem Review ------------------------------------------------------------
def test_invalid_barcode_stays_selectable_after_opening(qtbot, tmp_path):
    """Ein ungültiger Barcode legt die Arbeitsfläche nicht lahm (Platzhalter statt Fehler)."""
    doc = Document("62x29", objects=[TextObject.plain("Hallo", size_pt=12),
                                     BarcodeObject(kind="ean13", data="123", x_mm=3, y_mm=3)])
    win = _window(qtbot, doc)
    assert len(win.rendered) == 2
    assert win.canvas.set_selection([0, 1]) or win.canvas.selection() == [0, 1]
    assert "EAN-13 braucht" in win.result.text()


def test_inserting_next_to_an_invalid_barcode_keeps_the_canvas(qtbot):
    win, panel = _with_barcode(qtbot, "ean13")
    _type(panel, "4006")
    win.canvas.set_selection([])
    panel.insert.click()
    assert len(win.rendered) == 2 and win.canvas.selection() == [1] and panel.index == 1


def test_ctrl_z_in_the_content_field_undoes_the_label(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    win.activateWindow()
    panel.data.setFocus()
    qtbot.waitUntil(panel.data.hasFocus, timeout=1000)
    QTest.keyClick(panel.data, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert win.doc.objects == []                               # Einfügen rückgängig


def test_typing_then_ctrl_z_undoes_the_whole_edit(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    win.activateWindow()
    panel.data.setFocus()
    qtbot.waitUntil(panel.data.hasFocus, timeout=1000)
    panel.data.selectAll()
    QTest.keyClicks(panel.data, "X1")
    QTest.keyClick(panel.data, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert win.doc.objects[0].data == "ABC-123" and panel.data.text() == "ABC-123"


def test_series_handles_use_the_filled_content(qtbot):
    doc = Document("62x29", objects=[BarcodeObject(kind="code128", data="X{Nummer}", x_mm=3,
                                                   y_mm=3)],
                   series=Series(numbering=Numbering(count=3)))
    win = _window(qtbot, doc)
    win.panel("series").refresh()
    win.render_now()
    before = win.rendered[0].w                                 # „X1“: 4 Werte + Stopp
    win.canvas.set_selection([0])
    point = win.canvas.handle_points(0)["r"]
    _drag(win.canvas, point, point + QPointF(1 * win.canvas.px_per_mm(), 0))
    obj = win.doc.objects[0]
    assert obj.data == "X{Nummer}" and obj.module == 3          # 1 mm mehr: kein Sprung
    assert win.rendered[0].w == before
    panel = win.panel("barcode")
    panel.position.spins["w"].setValue(round(before * 2 / MM, 1))   # doppelt so breit
    assert win.doc.objects[0].module == 6 and win.doc.objects[0].data == "X{Nummer}"


def test_check_uses_the_preview_row_in_a_series(qtbot):
    doc = Document("62x29", objects=[BarcodeObject(kind="ean8", data="{Nummer}", x_mm=3, y_mm=3)],
                   series=Series(numbering=Numbering(start=1234567, count=2)))
    win = _window(qtbot, doc)
    win.panel("series").refresh()
    win.render_now()
    win.canvas.set_selection([0])
    panel = win.panel("barcode")
    assert panel.check.text() == "Mit Prüfziffer: 12345670"


def test_content_is_limited_to_what_can_be_saved(qtbot):
    from labelwerk.document import MAX_BARCODE_DATA
    _, panel = _with_barcode(qtbot, "qr")
    assert panel.data.maxLength() == MAX_BARCODE_DATA


@pytest.mark.parametrize("text, state", [("0.25", "Acceptable"), ("0,3", "Acceptable"),
                                         ("", "Intermediate"), (".", "Intermediate"),
                                         ("5", "Intermediate"), ("0", "Intermediate"),
                                         ("abc", "Invalid"), ("nan", "Invalid"),
                                         ("1e400", "Invalid"), ("-1", "Invalid")])
def test_module_field_accepts_only_sensible_millimetres(qtbot, text, state):
    from labelwerk.gui.panels.barcode import ModuleSpin
    spin = ModuleSpin()
    qtbot.addWidget(spin)
    assert spin.validate(text + " mm", 0)[0].name == state
    assert spin.valueFromText(text + " mm") in range(1, 21)


def test_enter_on_a_selected_barcode_focuses_the_content(qtbot):
    win, panel = _with_barcode(qtbot, "code128")
    win.tool_actions["paper"].trigger()
    win.canvas.set_selection([0])
    assert win.shortcut_actions["text.start_edit"].isEnabled()
    win.shortcut_actions["text.start_edit"].trigger()
    assert win.panels.currentWidget() is panel and panel.data.selectedText() == "ABC-123"


def test_favorite_with_placeholder_barcode_has_a_preview(qtbot):
    from labelwerk import favorites
    doc = Document("62x29", objects=[BarcodeObject(kind="ean8", data="{Nummer}", x_mm=3, y_mm=3)],
                   series=Series(numbering=Numbering(count=2)))
    favorites.add(doc, "Serie EAN")
    win = _window(qtbot)
    assert win.panel("file").favorite_preview(0) is not None
