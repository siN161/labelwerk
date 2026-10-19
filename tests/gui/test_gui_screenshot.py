"""Werkzeug Bild – Bildschirmfoto (Etappe 3d-2b): Ablauf im Hauptfenster. Das Portal ist durch
Haken ersetzt (``screenshot_available``/``take_screenshot``); ohne Ersatz sieht die GUI keinen
Sitzungsbus (``conftest.no_session_bus``) – nie das echte Portal."""
import pytest
from PIL import Image, ImageDraw

from labelwerk import shortcuts
from labelwerk.document import Document, ImageObject, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.main_window import NO_SCREENSHOT, SCREENSHOT, MainWindow
from labelwerk.i18n import _
from labelwerk.settings import Settings

MM = 300 / 25.4


def _window(qtbot, doc=None, **settings):
    win = MainWindow(doc=doc or Document("62", length_mm=40,
                                         objects=[TextObject("Eins", size_pt=14, x_mm=4, y_mm=4)]),
                     settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    win.show()
    return win


def _shot(tmp_path, w=240, h=120, dpi=(72, 72)):
    """Bildschirmfoto-Datei: weißer Rand, schwarzes Feld (Datei mit DPI-Angabe, die nicht gilt)."""
    img = Image.new("RGB", (w, h), "white")
    ImageDraw.Draw(img).rectangle((20, 20, w - 21, h - 21), fill="black")
    path = tmp_path / "Bildschirmfoto vom 2026-10-18.png"
    img.save(path, dpi=dpi)
    return path


@pytest.fixture
def portal(monkeypatch):
    """Ersetztes Portal: verfügbar; ``calls`` zählt die Aufnahmen."""
    class Fake:
        available = True
        calls = 0
    fake = Fake()
    monkeypatch.setattr(MainWindow, "screenshot_available", lambda self: fake.available)

    def take(self):
        fake.calls += 1
    monkeypatch.setattr(MainWindow, "take_screenshot", take)
    return fake


def _start(win, qtbot, portal):
    calls = portal.calls
    win.panel("image").screenshot.click()
    qtbot.waitUntil(lambda: portal.calls == calls + 1, timeout=2000)


# --- Aktion und Knopf ----------------------------------------------------------------
def test_screenshot_action_has_no_default_key(qtbot):
    entry = shortcuts.action("image.screenshot")
    assert (_(entry.name), entry.default, entry.scope) == ("Bildschirmfoto einfügen", "", "canvas")
    win = _window(qtbot)
    assert win.shortcut_actions["image.screenshot"] in win.canvas.actions()
    button = win.panel("image").screenshot
    assert button.text() == "BILDSCHIRMFOTO" and button.isEnabled()
    assert button.toolTip() == "Bildschirmfoto einfügen"


def test_assigned_key_shows_in_tooltip(qtbot):
    win = _window(qtbot, shortcuts={"image.screenshot": "Ctrl+Alt+S"})
    assert "Ctrl+Alt+S" in win.panel("image").screenshot.toolTip()


# --- Ablauf ------------------------------------------------------------------------
def test_window_hides_then_portal_is_called(qtbot, portal):
    win = _window(qtbot)
    win.panel("image").screenshot.click()
    assert not win.isVisible() and portal.calls == 0          # erst ausblenden …
    qtbot.waitUntil(lambda: portal.calls == 1, timeout=2000)  # … dann die Auswahl
    assert not win.isVisible()
    assert not win.shortcut_actions["image.screenshot"].isEnabled()


def test_screenshot_is_inserted_at_300_dpi_and_selected(qtbot, portal, tmp_path):
    win = _window(qtbot)
    _start(win, qtbot, portal)
    win.screenshot_finished(_shot(tmp_path), None)
    assert win.isVisible() and win.shortcut_actions["image.screenshot"].isEnabled()
    obj = win.doc.objects[1]
    assert isinstance(obj, ImageObject) and obj.source == SCREENSHOT == "Bildschirmfoto"
    assert obj.dpi == 300                                     # DPI-Angabe der Datei gilt nicht
    assert (obj.w_mm, obj.h_mm) == pytest.approx((200 / MM, 80 / MM), abs=0.01)   # zugeschnitten
    assert win.canvas.selection() == [1]
    win.undo()
    assert len(win.doc.objects) == 1                          # ein Rückgängig-Schritt


def test_screenshot_follows_crop_setting(qtbot, portal, tmp_path):
    win = _window(qtbot, image_crop=False)
    _start(win, qtbot, portal)
    win.screenshot_finished(_shot(tmp_path), None)
    obj = win.doc.objects[1]
    assert obj.crop is None and obj.w_mm == pytest.approx(240 / MM, abs=0.01)


def test_screenshot_follows_rotate_setting(qtbot, portal, tmp_path):
    """Endlosband 62 mm, automatische Länge: breites Foto mit „drehen“ gedreht 1:1."""
    doc = Document("62", objects=[TextObject("Absender", size_pt=10, x_mm=3, y_mm=3)])
    win = _window(qtbot, doc, image_rotate=True)
    _start(win, qtbot, portal)
    win.screenshot_finished(_shot(tmp_path, 867, 442), None)
    obj = win.doc.objects[1]
    assert obj.rotation == 90 and obj.w_mm == pytest.approx(827 / MM, abs=0.01)
    assert "Bild um 90° gedreht" in win.result.text()


def test_huge_screenshot_keeps_its_size(qtbot, portal, tmp_path):
    """Über zwei 4K-Bildschirme: beim Laden auf 6000 px begrenzt – die Größe bleibt 1:1."""
    win = _window(qtbot)
    _start(win, qtbot, portal)
    win.screenshot_finished(_shot(tmp_path, 7680, 400), None)
    obj = win.doc.objects[1]
    assert obj.natural_mm()[0] == pytest.approx(7640 / MM, rel=0.002)


def test_screenshot_with_unequal_file_resolution_keeps_its_aspect(qtbot, portal, tmp_path):
    win = _window(qtbot)
    _start(win, qtbot, portal)
    win.screenshot_finished(_shot(tmp_path, 240, 120, dpi=(72, 144)), None)
    w, h = win.doc.objects[1].natural_mm()
    assert w == pytest.approx(200 / MM, rel=0.002) and h == pytest.approx(80 / MM, rel=0.002)   # zugeschnitten


def test_cancel_inserts_nothing_and_says_nothing(qtbot, portal):
    win = _window(qtbot)
    _start(win, qtbot, portal)
    win.screenshot_finished(None, None)
    assert win.isVisible() and len(win.doc.objects) == 1 and win.result.text() == ""
    assert win.shortcut_actions["image.screenshot"].isEnabled()


def test_portal_error_is_shown(qtbot, portal):
    win = _window(qtbot)
    _start(win, qtbot, portal)
    win.screenshot_finished(None, "Bildschirmfoto fehlgeschlagen – keine Bilddatei erhalten")
    assert win.isVisible() and len(win.doc.objects) == 1
    assert win.result.text() == "Bildschirmfoto fehlgeschlagen – keine Bilddatei erhalten"
    assert win.result.property("state") == "error"
    assert win.shortcut_actions["image.screenshot"].isEnabled()


def test_unreadable_file_is_shown(qtbot, portal, tmp_path):
    win = _window(qtbot)
    _start(win, qtbot, portal)
    win.screenshot_finished(tmp_path / "weg.png", None)
    assert win.isVisible() and len(win.doc.objects) == 1
    assert win.result.text().startswith("Bildschirmfoto: ") and "weg.png" in win.result.text()
    assert win.result.property("state") == "error"


def test_error_in_take_brings_window_back_at_once(qtbot, monkeypatch):
    monkeypatch.setattr(MainWindow, "screenshot_available", lambda self: True)

    def broken(self):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(MainWindow, "take_screenshot", broken)
    win = _window(qtbot)
    win.panel("image").screenshot.click()
    qtbot.waitUntil(win.isVisible, timeout=2000)
    assert win.result.text() == "Bildschirmfoto fehlgeschlagen – kaputt"
    assert win.shortcut_actions["image.screenshot"].isEnabled()
    assert not win._restore_timer.isActive()


def test_real_portal_object_answers_through_the_window(qtbot, monkeypatch):
    """Echtes ``ScreenshotPortal`` (ohne Sitzungsbus in Tests): seine Antwort kommt über
    ``finished`` im Hauptfenster an – noch während ``take()``."""
    monkeypatch.setattr(MainWindow, "screenshot_available", lambda self: True)
    win = _window(qtbot)
    win.panel("image").screenshot.click()
    qtbot.waitUntil(win.isVisible, timeout=2000)
    assert win.result.text() == ("Bildschirmfoto fehlgeschlagen – keine Verbindung zum "
                                 "Sitzungsbus")
    assert win.shortcut_actions["image.screenshot"].isEnabled()
    assert not win._restore_timer.isActive()


def test_app_does_not_quit_while_hidden(qtbot, portal, qapp):
    assert qapp.quitOnLastWindowClosed()
    win = _window(qtbot)
    _start(win, qtbot, portal)
    assert not qapp.quitOnLastWindowClosed()
    win.screenshot_finished(None, None)
    assert qapp.quitOnLastWindowClosed()


def test_closing_during_screenshot_ends_it(qtbot, portal, tmp_path, monkeypatch):
    monkeypatch.setattr(main_window, "RESTORE_TIMEOUT_MS", 100)
    win = _window(qtbot)
    win.panel("image").screenshot.click()
    win.close()                                    # noch in der Pause vor der Auswahl
    qtbot.wait(main_window.HIDE_DELAY_MS + 200)
    assert portal.calls == 0 and not win.isVisible()
    win.screenshot_finished(_shot(tmp_path), None)
    assert len(win.doc.objects) == 1


def test_without_portal_window_stays_and_hint_names_clipboard(qtbot):
    """Ohne Ersatz: kein Sitzungsbus in Tests → wie ein System ohne Portal."""
    win = _window(qtbot)
    win.panel("image").screenshot.click()
    assert win.isVisible()
    assert win.result.text() == _(NO_SCREENSHOT) and "Strg+V" in _(NO_SCREENSHOT)
    assert win.result.property("state") == "error"


def test_second_click_while_taking_does_nothing(qtbot, portal):
    win = _window(qtbot)
    _start(win, qtbot, portal)
    win.insert_screenshot()
    qtbot.wait(main_window.HIDE_DELAY_MS + 100)
    assert portal.calls == 1


def test_timeout_shows_window_and_late_answer_still_inserts(qtbot, portal, tmp_path,
                                                            monkeypatch):
    monkeypatch.setattr(main_window, "RESTORE_TIMEOUT_MS", 100)
    win = _window(qtbot)
    _start(win, qtbot, portal)
    qtbot.waitUntil(win.isVisible, timeout=2000)
    assert win.shortcut_actions["image.screenshot"].isEnabled()
    win.screenshot_finished(_shot(tmp_path), None)
    assert len(win.doc.objects) == 2
    win.screenshot_finished(_shot(tmp_path), None)            # nur die erste Antwort zählt
    assert len(win.doc.objects) == 2


def test_answer_without_open_screenshot_is_ignored(qtbot, tmp_path):
    win = _window(qtbot)
    win.screenshot_finished(_shot(tmp_path), None)
    assert len(win.doc.objects) == 1


def test_screenshot_ends_text_editing_first(qtbot, portal):
    win = _window(qtbot)
    win.canvas.set_selection([0])
    win.edit_selected()
    assert win.edit_session.active
    _start(win, qtbot, portal)
    assert not win.edit_session.active


def test_screenshot_takes_the_image_default(qtbot, portal, tmp_path):
    win = _window(qtbot, image_mode="photo", image_threshold=60)
    _start(win, qtbot, portal)
    assert win._shot_pending
    win.screenshot_finished(_shot(tmp_path), None)
    obj = win.doc.objects[1]
    assert (obj.mode, obj.threshold) == ("photo", 60)
