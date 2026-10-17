"""Werkzeug „Bild“ (Etappe 3d-2a): einfügen aus Datei, Zwischenablage und per Ablegen,
Bild-Panel, Bilder auf der Arbeitsfläche wie Text."""
import io
import math

import pytest
from PIL import Image, ImageDraw
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from labelwerk import layout, shortcuts
from labelwerk.document import Document, ImageObject, TextObject
from labelwerk.gui.image_import import CLIPBOARD, MIME_OBJECTS
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.tools import TOOLS
from labelwerk.settings import Settings

NO_MOD = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
LEFT = Qt.MouseButton.LeftButton
MM = 300 / 25.4                                # Pixel je mm bei 300 dpi


def _picture(w=300, h=150, border=30, gray=0) -> Image.Image:
    """Weißes Bild mit Rand ``border`` und einem Schachbrett (wie ein QR-Code) darin."""
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((border, border, w - border - 1, h - border - 1), fill=(gray,) * 3)
    for y in range(border, h - border, 10):
        for x in range(border + (y // 10) % 2 * 10, w - border, 20):
            draw.rectangle((x, y, x + 9, y + 9), fill="white")
    return img


def _file(tmp_path, img=None, name="code.png", dpi=300):
    path = tmp_path / name
    (img or _picture()).save(path, dpi=(dpi, dpi))
    return path


def _qimage(img: Image.Image) -> QImage:
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return QImage.fromData(buffer.getvalue())


def _doc():
    return Document("62", length_mm=40, objects=[TextObject("Eins", size_pt=14, x_mm=4, y_mm=4)])


def _window(qtbot, doc=None):
    win = MainWindow(doc=doc if doc is not None else _doc(),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def window(qtbot):
    return _window(qtbot)


def _insert_file(win, path, page=None):
    win.ask_image_file = lambda: str(path)
    win.ask_pdf_page = lambda path, count: page
    win.panel("image").from_file.click()


def _with_image(qtbot, tmp_path, img=None, **settings):
    win = _window(qtbot)
    _insert_file(win, _file(tmp_path, img))
    for key, value in settings.items():
        setattr(win.doc.objects[1], key, value)
    win.render_now()
    return win


def _send(canvas, kind, pos, buttons, modifiers=NO_MOD):
    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)),
                        button, buttons, modifiers)
    QApplication.sendEvent(canvas.viewport(), event)


def _click(canvas, pos):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, pos, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)


def _double_click(canvas, pos):
    _click(canvas, pos)
    _send(canvas, QMouseEvent.Type.MouseButtonDblClick, pos, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)


def _drag(canvas, start, end):
    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


def _focus_canvas(win, qtbot):
    win.activateWindow()
    win.canvas.setFocus()
    qtbot.waitUntil(lambda: win.canvas.hasFocus(), timeout=1000)


def _drop(canvas, mime, pos, process=True):
    """Ablegen; verarbeitet wird erst nach dem Ereignis (``process``: gleich abwarten)."""
    try:                    # QDragEnterEvent nimmt erst ab PySide6 6.12 QPointF (CI 3.10: 6.11)
        QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD)
    except TypeError:
        pos = pos.toPoint()
    for event in (QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD),
                  QDropEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD)):
        QApplication.sendEvent(canvas.viewport(), event)
    if process:
        QTest.qWait(0)


def _ink(win, index):
    return win.rendered[index].image.histogram()[0]


def _status(win):
    return win.result.text()


# --- Werkzeug und Panel -------------------------------------------------------------
def test_image_tool_comes_after_text(window):
    assert [tool.key for tool in TOOLS] == ["paper", "text", "image", "layout"]
    window.tool_actions["image"].trigger()
    assert window.panels.currentWidget() is window.panel("image")
    assert window.canvas.tool() == "select"
    panel = window.panel("image")
    assert panel.hint.isVisible() and not panel.threshold.isEnabled()


def test_insert_action_is_in_the_shortcut_registry(window):
    entry = shortcuts.action("image.insert")
    assert (entry.default, entry.scope) == ("Ctrl+Shift+I", "canvas")
    assert window.shortcut_actions["image.insert"] in window.canvas.actions()
    assert "Ctrl+Shift+I" in window.panel("image").from_file.toolTip()


# --- Aus Datei ----------------------------------------------------------------------
def test_file_is_inserted_one_to_one_centred_cropped_and_selected(window, tmp_path):
    _insert_file(window, _file(tmp_path))
    obj = window.doc.objects[1]
    assert isinstance(obj, ImageObject) and obj.source == "code.png"
    assert obj.crop == (30, 30, 270, 120)                    # Rand fällt weg
    assert (obj.w_mm, obj.h_mm) == pytest.approx((240 / MM, 90 / MM))
    rect = layout.exact_rect(obj, window.rendered[1])
    area = window._area
    assert (rect.cx, rect.cy) == pytest.approx((area.cx, area.cy), abs=0.01)
    assert window.canvas.selection() == [1]
    assert window.panels.currentWidget() is window.panel("image")
    assert window.panel("image").index == 1
    window.undo()                                            # ein Schritt
    assert len(window.doc.objects) == 1


def test_cancelled_file_dialog_inserts_nothing(window):
    window.ask_image_file = lambda: None
    window.panel("image").from_file.click()
    assert len(window.doc.objects) == 1 and not window.history.can_undo(window.doc)


def test_too_large_image_is_fitted_with_hint(window, tmp_path):
    _insert_file(window, _file(tmp_path, _picture(3000, 400, border=0)))
    obj = window.doc.objects[1]
    area = window._area
    assert obj.w_mm == pytest.approx(area.w, abs=0.01)
    assert obj.w_mm / obj.h_mm == pytest.approx(3000 / 400, rel=1e-4)
    percent = math.floor(area.w / (3000 / MM) * 100)
    assert _status(window) == f"Bild auf {percent} % verkleinert – Codes ggf. nicht mehr lesbar"
    # eingepasst: höchstens 600 dpi bezogen auf die neue Druckgröße, 1:1-Größe bleibt
    assert obj.image().width == pytest.approx(600 * obj.w_mm / 25.4, abs=1)
    assert obj.natural_mm() == pytest.approx((3000 / MM, 400 / MM), abs=0.05)   # ganze Pixel


def test_shrink_hint_never_says_zero_percent(window, tmp_path):
    _insert_file(window, _file(tmp_path, _picture(3000, 30, border=0), dpi=4))    # 19 m
    assert window.doc.objects[1].w_mm == pytest.approx(window._area.w, abs=0.01)
    assert _status(window).startswith("Bild auf < 1 % verkleinert")


def test_shrink_hint_never_says_hundred_percent(window, tmp_path):
    """Knapp zu groß (99,8 %): abgerundet, nie „auf 100 % verkleinert“."""
    width = round(window._area.w * MM / 0.998)
    _insert_file(window, _file(tmp_path, _picture(width, 60, border=0)))
    assert window.doc.objects[1].rotation == 0
    assert _status(window).startswith("Bild auf 99 % verkleinert")


def test_shrink_hint_mentions_codes_only_in_line_mode():
    from labelwerk.gui.main_window import shrunk_hint
    assert shrunk_hint(0.372, "line") == "Bild auf 37 % verkleinert – Codes ggf. nicht mehr lesbar"
    assert shrunk_hint(0.372, "photo") == "Bild auf 37 % verkleinert"
    assert shrunk_hint(0.289, "photo") == "Bild auf 28 % verkleinert"      # abgerundet
    assert shrunk_hint(0.29, "photo") == "Bild auf 29 % verkleinert"       # ohne Rundungsfehler
    assert shrunk_hint(0.9999, "photo") == "Bild auf 99 % verkleinert"
    assert shrunk_hint(0.001, "photo") == "Bild auf < 1 % verkleinert"


def _stamp_doc():
    """Endlosband 62 mm, automatische Länge, senkrecht (Standard) mit einem Absender."""
    return Document("62", objects=[TextObject("Absender", size_pt=10, x_mm=3, y_mm=3)])


def test_wide_image_is_turned_instead_of_shrunk(qtbot, tmp_path):
    """70 × 34 mm (wie eine Internetmarke) auf 62 mm senkrecht: gedreht 1:1 statt 81 %."""
    win = _window(qtbot, _stamp_doc())
    _insert_file(win, _file(tmp_path, _picture(827, 402, border=0)))
    obj = win.doc.objects[1]
    assert obj.rotation == 90
    assert (obj.w_mm, obj.h_mm) == pytest.approx(obj.natural_mm(), abs=0.001)    # 1:1
    assert obj.w_mm == pytest.approx(827 / MM, abs=0.01)
    rect = layout.exact_rect(obj, win.rendered[1])
    assert (rect.w, rect.h) == pytest.approx((obj.h_mm, obj.w_mm), abs=0.01)
    assert win._area.x - 0.01 <= rect.x and rect.right <= win._area.right + 0.01
    assert _status(win) == "Bild um 90° gedreht, damit es 1:1 passt"
    assert win.result.property("state") == "warn"
    assert win.canvas.selection() == [1]


def test_wide_clipboard_image_is_turned_too(qtbot):
    win = _window(qtbot, _stamp_doc())
    QApplication.clipboard().setImage(_qimage(_picture(827, 402, border=0)))
    win.panel("image").from_clipboard.click()
    obj = win.doc.objects[1]
    assert obj.rotation == 90 and (obj.w_mm, obj.h_mm) == pytest.approx(obj.natural_mm(), abs=0.001)
    assert "Bild um 90° gedreht" in _status(win)


def test_wide_image_stays_unturned_when_horizontal(qtbot, tmp_path):
    doc = _stamp_doc()
    doc.orientation = "horizontal"
    win = _window(qtbot, doc)
    _insert_file(win, _file(tmp_path, _picture(827, 402, border=0)))
    obj = win.doc.objects[1]
    assert obj.rotation == 0 and (obj.w_mm, obj.h_mm) == pytest.approx(obj.natural_mm(), abs=0.001)
    assert _status(win) == ""


def _pdf(tmp_path):
    path = tmp_path / "marken.pdf"
    pages = [_picture(300, 150), _picture(150, 150)]
    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=300)
    return path


def test_pdf_with_several_pages_asks_for_the_page(window, tmp_path):
    asked = []
    window.ask_image_file = lambda: str(_pdf(tmp_path))
    window.ask_pdf_page = lambda path, count: asked.append(count) or 2
    window.panel("image").from_file.click()
    obj = window.doc.objects[1]
    assert asked == [2]
    assert (obj.source, obj.page) == ("marken.pdf", 2)
    assert (obj.w_mm, obj.h_mm) == pytest.approx((90 / MM, 90 / MM), abs=0.6)   # PDF: Kanten geglättet
    assert window.panel("image").source.text() == "marken.pdf · Seite 2"


def test_cancelled_page_dialog_inserts_nothing(window, tmp_path):
    _insert_file(window, _pdf(tmp_path), page=None)
    assert len(window.doc.objects) == 1


def test_svg_size_units_are_case_insensitive(tmp_path):
    from labelwerk.gui.image_import import svg_size
    path = tmp_path / "gross.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="25.4MM" height="1IN"/>')
    assert svg_size(path) == pytest.approx((96, 96))


def test_svg_is_rasterized_at_300_dpi(window, tmp_path):
    path = tmp_path / "logo.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="96" height="48">'
                    '<rect width="96" height="48" fill="black"/></svg>')
    _insert_file(window, path)
    obj = window.doc.objects[1]
    assert obj.source == "logo.svg"
    assert (obj.w_mm, obj.h_mm) == pytest.approx((25.4, 12.7), abs=0.1)   # 1 in × ½ in
    assert obj.image().size == (300, 150)
    assert _ink(window, 1) > 0.9 * 300 * 150


@pytest.mark.parametrize("width, height", [("25.4mm", "12.7mm"), ("1in", "0.5in"),
                                           ("2.54cm", "36pt"), ("6pc", "48px")])
def test_svg_with_physical_units_keeps_its_size(window, tmp_path, width, height):
    """mm/cm/in/pt/pc nach CSS (96 px je Zoll) – Qt rechnete mit 90 dpi (6 % zu klein)."""
    path = tmp_path / "masse.svg"
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                    'viewBox="0 0 20 10"><rect width="20" height="10" fill="black"/></svg>')
    _insert_file(window, path)
    obj = window.doc.objects[1]
    assert (obj.w_mm, obj.h_mm) == pytest.approx((25.4, 12.7), abs=0.1)
    assert obj.image().size == (300, 150)
    assert _ink(window, 1) > 0.9 * 300 * 150


@pytest.mark.parametrize("name, content, message", [
    ("kaputt.png", b"kein bild", "kann nicht gelesen werden"),
    ("notiz.txt", b"text", "Dateityp nicht unterstützt"),
    ("kaputt.svg", b"<svg", "kann nicht gelesen werden"),
])
def test_unreadable_files_show_a_message(window, tmp_path, name, content, message):
    path = tmp_path / name
    path.write_bytes(content)
    _insert_file(window, path)
    assert len(window.doc.objects) == 1
    assert message in _status(window)
    assert window.result.property("state") == "error"


def test_unsupported_type_message_lists_all_image_types(window, tmp_path):
    path = tmp_path / "notiz.txt"
    path.write_text("x")
    _insert_file(window, path)
    assert _status(window) == ("Dateityp nicht unterstützt: .txt – möglich: "
                               "PNG, JPG, GIF, BMP, WebP, SVG, PDF")


def test_file_dialog_filter_accepts_uppercase_names():
    from labelwerk.gui.image_import import FILE_FILTER
    for pattern in ("*.png", "*.PNG", "*.jpeg", "*.JPEG", "*.svg", "*.SVG", "*.PDF"):
        assert f" {pattern}" in FILE_FILTER or f"({pattern}" in FILE_FILTER


def test_missing_file_and_missing_page_show_a_message(window, tmp_path):
    window.insert_image_files([tmp_path / "fehlt.png"])
    assert "nicht gefunden" in _status(window)
    window.insert_image_files([_pdf(tmp_path)], page=5)
    assert "nur 2 Seite" in _status(window)
    assert len(window.doc.objects) == 1


def test_light_image_is_kept_whole(window, tmp_path):
    """Helles Foto ohne Weiß: alles ist Inhalt („nicht weiß“), nichts wird abgeschnitten."""
    _insert_file(window, _file(tmp_path, Image.new("RGB", (300, 150), (220, 220, 220))))
    obj = window.doc.objects[1]
    assert obj.crop == (0, 0, 300, 150) and (obj.w_mm, obj.h_mm) == pytest.approx((300 / MM, 150 / MM))
    assert "zugeschnitten" not in _status(window)


def test_yellow_logo_is_cropped_to_the_logo(window, tmp_path):
    img = Image.new("RGB", (300, 150), "white")
    img.paste((255, 220, 0), (40, 30, 200, 120))
    _insert_file(window, _file(tmp_path, img))
    assert window.doc.objects[1].crop == (40, 30, 200, 120)


def test_white_image_is_not_cropped_with_hint(window, tmp_path):
    _insert_file(window, _file(tmp_path, Image.new("RGB", (300, 150), "white")))
    obj = window.doc.objects[1]
    assert obj.crop is None and (obj.w_mm, obj.h_mm) == pytest.approx((300 / MM, 150 / MM))
    assert _status(window) == "Bild nicht zugeschnitten – nur weiße Fläche gefunden"
    panel = window.panel("image")
    assert not panel.crop.isChecked()
    panel.crop.click()                                      # Zuschnitt: findet nichts
    assert not panel.crop.isChecked() and window.doc.objects[1].crop is None
    assert _status(window) == "Bild nicht zugeschnitten – nur weiße Fläche gefunden"


# --- Zwischenablage -----------------------------------------------------------------
def test_clipboard_button_follows_the_clipboard(window):
    button = window.panel("image").from_clipboard
    assert not button.isEnabled()
    QApplication.clipboard().setImage(_qimage(_picture()))
    assert button.isEnabled()
    QApplication.clipboard().setText("nur Text")
    assert not button.isEnabled()


def test_blank_text_clipboard_does_not_enable_paste(window):
    QApplication.clipboard().setText("  \n\t ")
    assert not window.shortcut_actions["edit.paste"].isEnabled()


def test_clipboard_image_via_panel(window):
    QApplication.clipboard().setImage(_qimage(_picture()))
    window.panel("image").from_clipboard.click()
    obj = window.doc.objects[1]
    assert isinstance(obj, ImageObject) and obj.source == CLIPBOARD
    assert (obj.w_mm, obj.h_mm) == pytest.approx((240 / MM, 90 / MM))   # 300 dpi, zugeschnitten
    assert window.canvas.selection() == [1]


def test_clipboard_without_image_shows_a_message(window):
    QApplication.clipboard().setText("nur Text")
    window.paste_image()
    assert len(window.doc.objects) == 1
    assert _status(window) == "Kein Bild in der Zwischenablage."


def test_ctrl_v_pastes_clipboard_image(window, qtbot):
    QApplication.clipboard().setImage(_qimage(_picture()))
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
    assert isinstance(window.doc.objects[1], ImageObject)


def test_copy_marks_the_system_clipboard_and_ctrl_v_pastes_objects(window, qtbot):
    window.canvas.set_selection([0])
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_C, CTRL)
    mime = QApplication.clipboard().mimeData()
    assert mime.hasFormat(MIME_OBJECTS) and mime.text() == "Eins"
    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
    assert [type(o) for o in window.doc.objects] == [TextObject, TextObject]
    assert window.doc.objects[1].x_mm == pytest.approx(6)    # Objekt, kein neuer Textrahmen


def test_other_clipboard_content_wins_over_older_copy(window, qtbot):
    window.canvas.set_selection([0])
    window.copy_selected()
    QApplication.clipboard().setImage(_qimage(_picture()))
    window.paste()
    assert isinstance(window.doc.objects[1], ImageObject)


def test_paste_uses_last_copy_when_system_clipboard_is_empty(window):
    window.canvas.set_selection([0])
    window.copy_selected()
    QApplication.clipboard().clear()                          # z. B. Zwischenablage nicht erreichbar
    assert window.shortcut_actions["edit.paste"].isEnabled()
    window.paste()
    assert [o.text for o in window.doc.objects] == ["Eins", "Eins"]


def test_ctrl_v_with_text_creates_text_frame(window, qtbot):
    QApplication.clipboard().setText("Hallo\r\nWelt\n")
    _focus_canvas(window, qtbot)
    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
    obj = window.doc.objects[1]
    assert isinstance(obj, TextObject) and obj.text == "Hallo\nWelt"
    assert all(p.align == "left" for p in obj.paragraphs)
    area = window._area
    assert (obj.x_mm, obj.y_mm) == pytest.approx((area.x, area.y), abs=0.05)
    assert window.canvas.selection() == [1] and not window.edit_session.active
    window.undo()
    assert len(window.doc.objects) == 1


def test_paste_follows_the_system_clipboard(window):
    paste = window.shortcut_actions["edit.paste"]
    assert not paste.isEnabled()
    QApplication.clipboard().setText("Text")
    assert paste.isEnabled()
    QApplication.clipboard().clear()
    assert not paste.isEnabled()


def test_copied_image_pastes_offset(window, tmp_path):
    _insert_file(window, _file(tmp_path))
    before = window.doc.objects[1]
    window.copy_selected()
    window.paste()
    pasted = window.doc.objects[2]
    assert isinstance(pasted, ImageObject) and pasted.png is before.png
    assert (pasted.x_mm, pasted.y_mm) == pytest.approx((before.x_mm + 2, before.y_mm + 2))


def _set_clipboard(text=None, image=None, files=()):
    mime = QMimeData()
    if text is not None:
        mime.setText(text)
    if image is not None:
        mime.setImageData(_qimage(image))
    if files:
        mime.setUrls([QUrl.fromLocalFile(str(path)) for path in files])
    QApplication.clipboard().setMimeData(mime)


def test_ctrl_v_with_local_files_inserts_the_images(window, tmp_path):
    path = _file(tmp_path)
    _set_clipboard(text=str(path), files=[path])           # wie aus dem Dateimanager
    assert window.shortcut_actions["edit.paste"].isEnabled()
    window.paste()
    obj = window.doc.objects[1]
    assert isinstance(obj, ImageObject) and obj.source == "code.png"


def test_ctrl_v_with_other_local_file_says_so(window, tmp_path):
    path = tmp_path / "liste.csv"
    path.write_text("a;b")
    _set_clipboard(files=[path])
    window.paste()
    assert len(window.doc.objects) == 1
    assert _status(window).startswith("Dateityp nicht unterstützt: .csv")


def test_ctrl_v_text_wins_over_image(window):
    """Tabellenzellen bringen auch ein Bild mit – Strg+V nimmt den Text; das Bild gibt es über
    „Aus Zwischenablage“."""
    _set_clipboard(text="A1\tB1", image=_picture())
    window.paste()
    obj = window.doc.objects[1]
    assert isinstance(obj, TextObject) and obj.text == "A1 B1"
    assert window.panel("image").from_clipboard.isEnabled()
    window.panel("image").from_clipboard.click()
    assert isinstance(window.doc.objects[2], ImageObject)


def test_ctrl_v_image_only_inserts_image(window):
    _set_clipboard(image=_picture())
    window.paste()
    assert isinstance(window.doc.objects[1], ImageObject)


def test_ctrl_v_text_only_inserts_text(window):
    _set_clipboard(text="Nur Text")
    window.paste()
    assert window.doc.objects[1].text == "Nur Text"


def test_repeated_text_paste_is_offset_like_objects(window):
    QApplication.clipboard().setText("Hallo")
    for _ in range(3):
        window.paste()
    area = window._area
    xs = [(o.x_mm, o.y_mm) for o in window.doc.objects[1:]]
    assert xs == [pytest.approx((area.x + 2 * i, area.y + 2 * i), abs=0.01) for i in range(3)]
    QApplication.clipboard().setText("Neu")                 # neuer Inhalt: wieder links oben
    window.paste()
    assert (window.doc.objects[4].x_mm, window.doc.objects[4].y_mm) == \
        pytest.approx((area.x, area.y), abs=0.01)


def test_copied_image_leaves_no_text_on_the_system_clipboard(window, tmp_path):
    _insert_file(window, _file(tmp_path))
    window.copy_selected()
    mime = QApplication.clipboard().mimeData()
    assert mime.hasFormat(MIME_OBJECTS) and not mime.hasText()


class _SpyMime(QMimeData):
    """Zwischenablage, die mitschreibt, ob ihre Daten gelesen werden."""

    def __init__(self):
        super().__init__()
        self.reads = []
        self.setText("Text")

    def text(self):
        self.reads.append("text")
        return super().text()

    def imageData(self):
        self.reads.append("image")
        return super().imageData()

    def urls(self):
        self.reads.append("urls")
        return super().urls()


def test_edit_actions_do_not_read_clipboard_data(window, monkeypatch):
    from PySide6.QtGui import QClipboard
    spy = _SpyMime()
    monkeypatch.setattr(QClipboard, "mimeData", lambda self, *args: spy)
    window._clipboard_changed()                             # einmal beim Ändern: ohne Daten
    spy.reads.clear()
    window.canvas.set_selection([0])
    for _ in range(3):
        window._update_edit_actions()
        window.nudge(0.1, 0)                                # jeder Schritt prüft die Knöpfe
    assert window.shortcut_actions["edit.paste"].isEnabled()
    assert spy.reads == []


# --- Ablegen ------------------------------------------------------------------------
def _point(win, x_mm, y_mm):
    return win.canvas._view_point(x_mm * MM, y_mm * MM)


def test_dropped_file_lands_at_drop_point(window, tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(_file(tmp_path)))])
    _drop(window.canvas, mime, _point(window, 30, 25))
    obj = window.doc.objects[1]
    rect = layout.exact_rect(obj, window.rendered[1])
    assert (rect.cx, rect.cy) == pytest.approx((30, 25), abs=0.2)
    assert window.canvas.selection() == [1]


def test_dropped_image_data_is_inserted(window):
    mime = QMimeData()
    mime.setImageData(_qimage(_picture()))
    _drop(window.canvas, mime, _point(window, 30, 20))
    assert isinstance(window.doc.objects[1], ImageObject)


def test_dropping_several_files_offsets_each_by_2_mm(window, tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(_file(tmp_path, name=n))) for n in ("a.png", "b.png")])
    _drop(window.canvas, mime, _point(window, 30, 25))
    first, second = window.doc.objects[1:]
    assert (second.x_mm - first.x_mm, second.y_mm - first.y_mm) == pytest.approx((2, 2))
    assert window.canvas.selection() == [1, 2]


def test_dropped_pdf_asks_for_the_page_after_the_drop(window, tmp_path):
    asked = []
    window.ask_pdf_page = lambda path, count: asked.append(count) or 2
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(_pdf(tmp_path)))])
    _drop(window.canvas, mime, _point(window, 30, 25), process=False)
    assert asked == [] and len(window.doc.objects) == 1     # kein Dialog im Ablegen
    del mime                                               # Daten sind schon kopiert
    QTest.qWait(0)
    assert asked == [2] and window.doc.objects[1].page == 2


def test_dropped_unsupported_file_shows_message(window, tmp_path):
    path = tmp_path / "notiz.txt"
    path.write_text("x")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    _drop(window.canvas, mime, _point(window, 30, 20))
    assert len(window.doc.objects) == 1 and "Dateityp" in _status(window)


# --- Bild-Panel: Umwandlung, Größe --------------------------------------------------
def test_panel_shows_selected_image(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    panel = win.panel("image")
    assert panel.source.text() == "code.png"
    assert panel.line.isChecked() and panel.threshold.value() == 128
    assert panel.threshold_value.value() == 128
    assert panel.crop.isChecked() and panel.keep_ratio.isChecked() and not panel.invert.isChecked()
    assert not panel.position.spins["w"].isReadOnly()        # Größe immer änderbar


def test_threshold_changes_image_and_is_undoable(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path, _picture(gray=150))
    assert _ink(win, 1) == 0                                 # Grau 150 > Schwelle 128
    win.panel("image").threshold_value.setValue(200)
    win.render_now()
    assert win.doc.objects[1].threshold == 200 and _ink(win, 1) > 0
    win.undo()
    assert win.doc.objects[1].threshold == 128 and win.panel("image").threshold.value() == 128


def test_dragging_the_threshold_slider_is_one_step(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    slider = win.panel("image").threshold
    slider.setSliderDown(True)
    for value in (140, 160, 180):
        slider.setValue(value)
    slider.setSliderDown(False)
    assert win.doc.objects[1].threshold == 180
    assert win.panel("image").threshold_value.value() == 180
    win.undo()
    assert win.doc.objects[1].threshold == 128


def test_invert_and_photo_change_the_image(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path, _picture(gray=100))
    panel = win.panel("image")
    line = win.rendered[1].image.tobytes()
    panel.invert.click()
    win.render_now()
    assert win.doc.objects[1].invert and win.rendered[1].image.tobytes() != line
    panel.invert.click()
    win.render_now()
    ink = _ink(win, 1)
    panel.photo.click()
    win.render_now()
    assert win.doc.objects[1].mode == "photo" and 0 < _ink(win, 1) < ink   # Grau gerastert
    win.undo()
    assert win.doc.objects[1].mode == "line" and panel.line.isChecked()


def test_crop_off_shows_whole_image_in_place(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    before = win.doc.objects[1]
    win.panel("image").crop.click()
    obj = win.doc.objects[1]
    assert obj.crop is None and (obj.w_mm, obj.h_mm) == pytest.approx((300 / MM, 150 / MM))
    assert obj.x_mm == pytest.approx(before.x_mm - 30 / MM, abs=0.01)
    win.undo()
    assert win.doc.objects[1].crop == (30, 30, 270, 120)


def test_original_size_and_keep_ratio(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path, w_mm=40.0, h_mm=40.0, keep_ratio=False)
    panel = win.panel("image")
    panel.refresh()
    assert not panel.keep_ratio.isChecked()
    panel.keep_ratio.click()
    obj = win.doc.objects[1]
    assert obj.keep_ratio and (obj.w_mm, obj.h_mm) == pytest.approx((40, 15))
    panel.original.click()
    obj = win.doc.objects[1]
    assert (obj.w_mm, obj.h_mm) == pytest.approx((240 / MM, 90 / MM))
    win.undo()
    assert win.doc.objects[1].w_mm == pytest.approx(40)


def test_width_field_keeps_ratio(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    win.panel("image").position.spins["w"].setValue(40)
    obj = win.doc.objects[1]
    assert (obj.w_mm, obj.h_mm) == pytest.approx((40, 15))
    win.doc.objects[1].keep_ratio = False
    win.panel("image").position.spins["h"].setValue(20)
    obj = win.doc.objects[1]
    assert (obj.w_mm, obj.h_mm) == pytest.approx((40, 20))


# --- Auswahl, Schreibmodus, Layout --------------------------------------------------
def test_selection_switches_between_text_and_image_panel(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    win.canvas.set_selection([0])
    assert win.panels.currentWidget() is win.panel("text")
    assert win.panel("image").index is None
    win.canvas.set_selection([1])
    assert win.panels.currentWidget() is win.panel("image")
    assert win.tool_actions["image"].isChecked() and win.panel("text").index is None
    win.tool_actions["layout"].trigger()
    win.canvas.set_selection([0, 1])
    assert win.panels.currentWidget() is win.panel("layout")


def test_clicking_an_image_shows_image_panel(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    win.canvas.set_selection([])
    win.tool_actions["paper"].trigger()
    _click(win.canvas, win.canvas.view_rect(1).center())
    assert win.canvas.selection() == [1]
    assert win.panels.currentWidget() is win.panel("image")


def test_double_click_and_f2_on_image_do_not_start_edit_mode(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    _double_click(win.canvas, win.canvas.view_rect(1).center())
    assert not win.edit_session.active and win.canvas.editing() is None
    assert not win.shortcut_actions["text.start_edit"].isEnabled()
    win.edit_selected()
    assert not win.edit_session.active


def test_undo_with_image_and_text_keeps_panels_working(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    win.canvas.set_selection([0])
    win.delete_selected()                                    # Bild rutscht auf Platz 0
    win.canvas.set_selection([0])
    assert win.panel("image").index == 0
    win.undo()
    win.undo()
    assert [type(o) for o in win.doc.objects] == [TextObject]


def test_layout_same_height_for_text_and_image(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    win.canvas.set_selection([0, 1])
    win.match_selected("height")
    text, image = (layout.exact_rect(o, r) for o, r in zip(win.doc.objects, win.rendered))
    assert image.h == pytest.approx(text.h, abs=0.01)
    assert image.w / image.h == pytest.approx(240 / 90, abs=0.01)


def test_rotate_and_reorder_images(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    before = layout.exact_rect(win.doc.objects[1], win.rendered[1])
    win.rotate_selected(90)
    obj = win.doc.objects[1]
    rect = layout.exact_rect(obj, win.rendered[1])
    assert obj.rotation == 90 and (rect.w, rect.h) == pytest.approx((before.h, before.w), abs=0.01)
    win.reorder_selected(-1)
    assert isinstance(win.doc.objects[0], ImageObject) and win.canvas.selection() == [0]


@pytest.mark.parametrize("handle", ["br", "r", "b"])
def test_handles_keep_image_ratio(qtbot, tmp_path, handle):
    win = _with_image(qtbot, tmp_path)
    canvas = win.canvas
    point = canvas.handle_points(1)[handle]
    shift = 10 * canvas.px_per_mm()
    _drag(canvas, point, point + QPointF(shift if "r" in handle else 0,
                                         shift if "b" in handle else 0))
    obj = win.doc.objects[1]
    assert obj.w_mm / obj.h_mm == pytest.approx(240 / 90, rel=0.01)
    assert obj.w_mm > 240 / MM + 5


def test_edge_without_keep_ratio_distorts(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path, keep_ratio=False)
    canvas = win.canvas
    point = canvas.handle_points(1)["r"]
    _drag(canvas, point, point + QPointF(10 * canvas.px_per_mm(), 0))
    obj = win.doc.objects[1]
    assert obj.w_mm == pytest.approx(240 / MM + 10, abs=0.2)
    assert obj.h_mm == pytest.approx(90 / MM, abs=0.01)


def test_resize_preview_keeps_ratio_at_the_edge(qtbot, tmp_path):
    win = _with_image(qtbot, tmp_path)
    canvas = win.canvas
    point = canvas.handle_points(1)["r"]
    _send(canvas, QMouseEvent.Type.MouseButtonPress, point, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, point + QPointF(30, 0), LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, point + QPointF(60, 0), LEFT)
    frame = canvas.objects[1].frame()
    assert frame.width() / frame.height() == pytest.approx(240 / 90, rel=0.01)
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, point + QPointF(60, 0),
          Qt.MouseButton.NoButton)


@pytest.mark.parametrize("orientation, rotation", [("vertical", 0), ("vertical", 90),
                                                   ("horizontal", 0), ("horizontal", 270)])
@pytest.mark.parametrize("handle", ["tl", "t", "tr", "r", "br", "b", "bl", "l"])
def test_image_does_not_jump_after_releasing_a_handle(qtbot, tmp_path, handle, orientation,
                                                      rotation):
    """Vorschau beim Ziehen = Rahmen nach dem Loslassen, an allen Anfassern – bis auf das
    Einrasten der gezogenen Kanten auf 0,1 mm (``to_grid``) und ½ Druckpunkt Rundung."""
    win = _window(qtbot, Document("62", length_mm=60, orientation=orientation,
                                  objects=[TextObject("Eins", size_pt=14, x_mm=4, y_mm=4)]))
    _insert_file(win, _file(tmp_path))
    win.doc.objects[1].rotation = rotation
    win.render_now()
    canvas = win.canvas
    point = canvas.handle_points(1)[handle]
    centre = canvas.view_rect(1).center()
    step = 3.3 * canvas.px_per_mm()
    sign = lambda d: (d > 1) - (d < -1)                        # noqa: E731
    end = point + QPointF(sign(point.x() - centre.x()) * step,
                          sign(point.y() - centre.y()) * step)
    _send(canvas, QMouseEvent.Type.MouseButtonPress, point, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, (point + end) / 2, LEFT)
    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT)
    preview = canvas.objects[1].frame()
    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    win.render_now()
    after = layout.exact_rect(win.doc.objects[1], win.rendered[1])     # Rahmen im Modell, mm
    assert max(after.w, after.h) > 240 / MM + 3                # gewachsen
    for a, b in ((after.x, preview.left()), (after.y, preview.top()),
                 (after.right, preview.right()), (after.bottom, preview.bottom())):
        assert a * MM == pytest.approx(b, abs=0.1 * MM + 0.5)


def test_insert_on_growing_tape_goes_behind_existing_text(qtbot):
    """Endlosband, automatische Länge: ein Bild ohne Ablagepunkt liegt nicht auf dem Text
    am Anfang, sondern dahinter; das Etikett wächst mit."""
    win = _window(qtbot, Document("62", length_mm=None, objects=[
        TextObject("Absender", size_pt=14, x_mm=4, y_mm=2)]))
    win.render_now()
    before = layout.label_rect(win.doc).h
    win._insert_picture(_picture(300, 300), CLIPBOARD)
    win.render_now()
    text, image = (layout.object_rect(r) for r in win.rendered)
    assert image.y >= text.bottom + 2 - 0.2
    assert layout.label_rect(win.doc).h > before
