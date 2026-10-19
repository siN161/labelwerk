import pytest

from labelwerk.gui.main_window import MainWindow
from labelwerk.media import Media, MediaError
from labelwerk.settings import Settings

from labelwerk.printers import Printer

LP1 = Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")


def _printer_with(monkeypatch, media=None, error=None):
    monkeypatch.setattr("labelwerk.gui.media_worker.find_brother_lp", lambda: "file:///dev/usb/lp1")

    def read(printer):
        if error:
            raise MediaError(error)
        return media
    monkeypatch.setattr("labelwerk.gui.media_worker.read_media", read)


@pytest.fixture
def window(qtbot):
    win = MainWindow(settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    win.canvas.set_selection([0])      # Start ohne Auswahl: das Startobjekt zum Tippen wählen
    return win


def test_check_media_selects_matching_label(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    paper = window.panel("paper")
    paper.check.click()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert window.doc.label_id == "62x29"
    assert window.media_status.text() == "Rolle: 62 × 29 mm gestanzt ✓ – Etikett angepasst"
    assert window.media_status.property("state") == "ok"
    assert paper.check.isEnabled()


def test_mismatch_warning_after_changing_label(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert window.media_status.property("state") == "warn"
    assert "passt nicht" in window.media_status.text()
    paper.combo.setCurrentIndex(paper.combo.findData("62"))
    assert window.media_status.property("state") == "ok"


def test_check_media_error_is_shown(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, error="Keine Antwort vom Drucker auf die Statusabfrage.")
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    status = window.media_status
    assert "Keine Antwort" in status.text() and status.property("state") == "error"


def test_no_media_check_while_printing(window, monkeypatch):
    window._printing = True                        # Druck läuft
    window.check_media()
    assert not window.is_checking_media()


def test_no_print_while_media_check_runs(window, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
    window.panel("text").edit.setPlainText("Hallo")
    window._media_signals = object()               # Prüfung läuft
    window.print_label()
    assert "geprüft" in window.result.text()


def test_printer_appearing_triggers_status_and_media_check(qtbot, monkeypatch):
    win = MainWindow(settings=Settings(check_media_on_start=True))
    qtbot.addWidget(win)
    assert win.printer_status.text() == "○ kein Drucker"
    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    win._printer_timer.timeout.emit()              # nächster Abfrage-Takt
    assert "lp1" in win.printer_status.text()
    qtbot.waitUntil(lambda: win.doc.label_id == "62x29", timeout=3000)


def test_printer_appearing_without_auto_check(window, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
    window._printer_timer.timeout.emit()
    assert "lp1" in window.printer_status.text()
    assert not window.is_checking_media()


def test_printer_disconnect_clears_media_status(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
    window.refresh_printer()
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert not window.media_status.isHidden()
    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [])
    window.refresh_printer()
    assert window.media_status.isHidden()
    assert window.printer_status.text() == "○ kein Drucker"


# --- Druck und Medium-Prüfung schließen sich aus ----------------------------
def test_no_media_check_during_empty_dialog_and_print_proceeds(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", lambda: "file:///dev/usb/lp1")
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
                        lambda *a, **kw: {"did_print": True})
    seen = {}

    def dialog():
        window.check_media()                      # Timer feuert während des Dialogs
        seen["checking"] = window.is_checking_media()
        return True
    monkeypatch.setattr(MainWindow, "confirm_empty", lambda self: dialog())
    window.print_label()
    assert seen["checking"] is False
    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
    assert "Gedruckt" in window.result.text()


def test_cancelled_empty_dialog_resets_printing(window, monkeypatch):
    monkeypatch.setattr(MainWindow, "confirm_empty", lambda self: False)
    window.print_label()
    assert not window.is_printing()
    assert window.print_action.isEnabled()


def test_check_button_disabled_while_printing(window, qtbot, monkeypatch):
    import threading
    release = threading.Event()

    def blocking(*a, **kw):
        release.wait(5)
        return {"did_print": True}
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", lambda: "file:///dev/usb/lp1")
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", blocking)
    window.panel("text").edit.setPlainText("Hallo")
    window.print_label()
    try:
        assert window.is_printing()
        assert not window.panel("paper").check.isEnabled()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not window.is_printing(), timeout=3000)
    assert window.panel("paper").check.isEnabled()


def test_adjusted_label_is_mentioned(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert "angepasst" in window.media_status.text()


def test_matching_label_not_mentioned_as_adjusted(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert "angepasst" not in window.media_status.text()


def test_media_check_is_caught_up_after_print(qtbot, monkeypatch):
    win = MainWindow(settings=Settings(check_media_on_start=True))
    qtbot.addWidget(win)
    win._printing = True                           # Druck läuft, Drucker erscheint
    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    win.refresh_printer()
    assert not win.is_checking_media()
    win._print_done({"did_print": True})           # Druck fertig
    qtbot.waitUntil(lambda: win.doc.label_id == "62x29", timeout=3000)


def test_pending_media_check_dropped_on_disconnect(qtbot, monkeypatch):
    win = MainWindow(settings=Settings(check_media_on_start=True))
    qtbot.addWidget(win)
    win._printing = True
    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
    win.refresh_printer()
    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [])
    win.refresh_printer()
    win._printing = False
    win._print_finished()
    assert not win.is_checking_media()


def test_close_stops_printer_timer(window):
    assert window._printer_timer.isActive()
    window.close()
    assert not window._printer_timer.isActive()


def test_media_status_lives_in_footer_not_in_panel(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert window.media_status.parent() is window.statusBar() or \
        window.statusBar().isAncestorOf(window.media_status)
    assert window.media_status.text() == "Rolle: 62 mm endlos ✓"
    assert not hasattr(window.panel("paper"), "media_status")


def test_long_media_error_is_elided_in_footer(window):
    from labelwerk.detect import BUSY_MESSAGE
    from labelwerk.i18n import _
    window.panel("paper").show_media_error(_(BUSY_MESSAGE))
    label = window.media_status
    assert label.sizeHint().width() <= 360
    assert label.text().endswith("…")
    assert "belegt" in label.toolTip()
