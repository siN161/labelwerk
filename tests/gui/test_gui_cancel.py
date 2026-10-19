"""Serie abbrechen: beim Vorbereiten (nichts gedruckt) und zwischen den Teilaufträgen."""
import pytest

from labelwerk.document import Document, Numbering, Series, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.print_worker import PrintSignals, PrintWorker
from labelwerk.printer import PrintCancelled
from labelwerk.settings import Settings


class FakeWorker:
    """Druck-Worker ohne Thread und Drucker; merkt sich „Abbrechen“."""
    instances = []

    def __init__(self, image, label_id, model, cut_every=1):
        self.image, self.cancelled = image, False
        self.signals = PrintSignals()
        FakeWorker.instances.append(self)

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def workers(monkeypatch):
    FakeWorker.instances = []
    monkeypatch.setattr(main_window, "PrintWorker", FakeWorker)
    monkeypatch.setattr(main_window.QThreadPool.globalInstance(), "start", lambda worker: None)
    return FakeWorker.instances


def _window(qtbot, count=3, series=True):
    doc = Document("62x29", objects=[TextObject("X{Nummer}", size_pt=14)],
                   series=Series(numbering=Numbering(count=count)) if series else None)
    win = MainWindow(doc=doc, settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    win.panel("series").refresh()
    win.render_now()
    win.ask_print_count = lambda n: True
    return win


def test_cancel_button_is_hidden_without_printing(qtbot):
    win = _window(qtbot)
    assert win.cancel_button.isHidden()


def test_series_print_offers_cancel_and_stops_the_worker(qtbot, workers):
    win = _window(qtbot)
    win.print_label()
    worker, = workers
    assert not win.cancel_button.isHidden() and not win.print_action.isEnabled()
    win.cancel_button.click()
    assert worker.cancelled and win.result.text() == "Wird abgebrochen …"
    worker.signals.cancelled.emit("Abgebrochen – 10 von 30 Etiketten gedruckt")
    assert win.cancel_button.isHidden() and win.print_action.isEnabled()
    assert win.result.text() == "Abgebrochen – 10 von 30 Etiketten gedruckt"


def test_progress_is_shown(qtbot, workers):
    win = _window(qtbot, count=25)
    win.print_label()
    workers[0].signals.progress.emit(10, 25)
    assert win.result.text() == "Drucke … 10 von 25"


@pytest.mark.parametrize("finish", ["done", "failed"])
def test_end_of_printing_hides_cancel(qtbot, workers, finish):
    win = _window(qtbot)
    win.print_label()
    signals = workers[0].signals
    signals.done.emit({"did_print": True}) if finish == "done" else signals.failed.emit("x")
    assert win.cancel_button.isHidden()


def test_single_label_has_no_cancel(qtbot, workers):
    win = _window(qtbot, series=False)
    win.print_label()
    assert workers and win.cancel_button.isHidden()


def test_cancel_while_preparing_prints_nothing(qtbot, workers, monkeypatch):
    win = _window(qtbot, count=60)                       # Vorbereiten meldet sich alle 25 Zeilen
    clicks = []

    def events(*args, **kwargs):
        if not clicks:
            clicks.append(1)
            assert not win.cancel_button.isHidden()
            win.cancel_button.click()
    monkeypatch.setattr(main_window.QApplication, "processEvents", events)
    win.print_label()
    assert workers == [] and win.result.text() == "Abgebrochen – nichts gedruckt"
    assert win.cancel_button.isHidden() and win.print_action.isEnabled()


def test_worker_passes_cancel_and_progress_and_reports_cancelled(qtbot, monkeypatch):
    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", lambda: "file:///dev/usb/lp0")
    seen = {}

    def fake_print(image, label_id, **kw):
        seen["before"] = kw["cancelled"]()
        kw["progress"](10, 20)
        worker.cancel()
        seen["after"] = kw["cancelled"]()
        raise PrintCancelled(10, 20)
    monkeypatch.setattr("labelwerk.gui.print_worker.print_image", fake_print)
    worker = PrintWorker([object()] * 20, "62", "QL-600")
    progress, cancelled = [], []
    worker.signals.progress.connect(lambda d, n: progress.append((d, n)))
    worker.signals.cancelled.connect(cancelled.append)
    worker.run()
    assert seen == {"before": False, "after": True}
    assert progress == [(10, 20)] and cancelled == ["Abgebrochen – 10 von 20 Etiketten gedruckt"]
