"""Printing in a background thread so the UI does not block."""
from __future__ import annotations

import threading

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from ..i18n import _
from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
from ..printer import PrintCancelled, PrintError, print_image


class PrintSignals(QObject):
    done = Signal(dict)       # status from brother_ql
    failed = Signal(str)      # message for the status bar
    progress = Signal(int, int)   # series: printed, total (after each partial job)
    cancelled = Signal(str)   # series cancelled (message)


class PrintWorker(QRunnable):
    """``image``: one label or a list (series, one job); ``cut_every``: cut after every n
    labels (``printer.cut_interval``); ``printer``: URI of the chosen printer (USB or
    network). ``cancel()`` (from the GUI thread) aborts before the next partial job."""

    def __init__(self, image: Image.Image | list[Image.Image], label_id: str, model: str,
                 cut_every: int = 1, printer: str | None = None,
                 options: dict[str, str] | None = None):
        super().__init__()
        self.image, self.label_id, self.model = image, label_id, model
        self.printer = printer                     # URI; None = find the USB printer yourself
        self.options = options or {}               # driver options (CUPS, e.g. cut)
        self.cut_every = cut_every
        self.signals = PrintSignals()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            printer = self.printer or find_brother_lp()
            if printer is None:
                self.signals.failed.emit(_(BUSY_MESSAGE) if brother_busy() else _(PRINTER_NOT_FOUND))
                return
            status = print_image(self.image, self.label_id, model=self.model, printer=printer,
                                 cut_every=self.cut_every, cancelled=self._cancel.is_set,
                                 progress=self.signals.progress.emit, options=self.options)
        except PrintCancelled as e:
            self.signals.cancelled.emit(str(e))
            return
        except PrintError as e:
            self.signals.failed.emit(str(e))
            return
        except Exception as e:  # no thread crash; message instead of traceback

            self.signals.failed.emit(_("Unexpected error while printing: {error}").format(error=e))
            return
        self.signals.done.emit(status)
