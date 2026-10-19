"""Druck im Hintergrund-Thread, damit die Oberfläche nicht blockiert."""
from __future__ import annotations

import threading

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
from ..printer import PrintCancelled, PrintError, print_image


class PrintSignals(QObject):
    done = Signal(dict)       # Status von brother_ql
    failed = Signal(str)      # Meldung für die Statusleiste
    progress = Signal(int, int)   # Serie: gedruckt, alle (nach jedem Teilauftrag)
    cancelled = Signal(str)   # Serie abgebrochen (Meldung)


class PrintWorker(QRunnable):
    """``image``: ein Etikett oder eine Liste (Serie, ein Auftrag); ``cut_every``: schneiden
    alle n Etiketten (``printer.cut_interval``); ``printer``: URI des gewählten Druckers (USB oder
    Netzwerk). ``cancel()`` (aus dem GUI-Thread) bricht vor dem nächsten Teilauftrag ab."""

    def __init__(self, image: Image.Image | list[Image.Image], label_id: str, model: str,
                 cut_every: int = 1, printer: str | None = None):
        super().__init__()
        self.image, self.label_id, self.model = image, label_id, model
        self.printer = printer                     # URI; None = USB-Drucker selbst suchen
        self.cut_every = cut_every
        self.signals = PrintSignals()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            printer = self.printer or find_brother_lp()
            if printer is None:
                self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
                return
            status = print_image(self.image, self.label_id, model=self.model, printer=printer,
                                 cut_every=self.cut_every, cancelled=self._cancel.is_set,
                                 progress=self.signals.progress.emit)
        except PrintCancelled as e:
            self.signals.cancelled.emit(str(e))
            return
        except PrintError as e:
            self.signals.failed.emit(str(e))
            return
        except Exception as e:  # kein Absturz des Threads; Meldung statt Traceback
            self.signals.failed.emit(f"Unerwarteter Fehler beim Drucken: {e}")
            return
        self.signals.done.emit(status)
