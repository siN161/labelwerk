import pytest

from labelwerk.gui.main_window import MainWindow
from labelwerk.media import Media, MediaError
from labelwerk.settings import Settings


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
    return win


def test_check_media_selects_matching_label(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    paper = window.panel("paper")
    paper.check.click()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert window.doc.label_id == "62x29"
    assert paper.media_status.text() == "Eingelegt: 62 × 29 mm gestanzt ✓"
    assert paper.media_status.property("state") == "ok"
    assert paper.check.isEnabled()


def test_mismatch_warning_after_changing_label(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    paper = window.panel("paper")
    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
    assert paper.media_status.property("state") == "warn"
    assert "passt nicht" in paper.media_status.text()
    paper.combo.setCurrentIndex(paper.combo.findData("62"))
    assert paper.media_status.property("state") == "ok"


def test_check_media_error_is_shown(window, qtbot, monkeypatch):
    _printer_with(monkeypatch, error="Keine Antwort vom Drucker auf die Statusabfrage.")
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    status = window.panel("paper").media_status
    assert "Keine Antwort" in status.text() and status.property("state") == "error"


def test_no_media_check_while_printing(window, monkeypatch):
    window.print_action.setEnabled(False)          # Druck läuft
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
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
    _printer_with(monkeypatch, Media(62, 29, "die_cut"))
    win._printer_timer.timeout.emit()              # nächster Abfrage-Takt
    assert "lp1" in win.printer_status.text()
    qtbot.waitUntil(lambda: win.doc.label_id == "62x29", timeout=3000)


def test_printer_appearing_without_auto_check(window, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
    window._printer_timer.timeout.emit()
    assert "lp1" in window.printer_status.text()
    assert not window.is_checking_media()


def test_printer_disconnect_clears_media_status(window, qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
    window.refresh_printer()
    _printer_with(monkeypatch, Media(62, 0, "endless"))
    window.check_media()
    qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
    assert window.panel("paper").media_status.isVisibleTo(window.panel("paper"))
    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: None)
    window.refresh_printer()
    assert window.panel("paper").media_status.isHidden()
    assert window.printer_status.text() == "○ kein Drucker"
