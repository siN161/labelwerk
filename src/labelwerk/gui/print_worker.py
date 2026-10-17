"""Druck im Hintergrund-Thread, damit die Oberfläche nicht blockiert."""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
from ..printer import PrintError, print_image


class PrintSignals(QObject):
    done = Signal(dict)       # Status von brother_ql
    failed = Signal(str)      # Meldung für die Statusleiste


class PrintWorker(QRunnable):
    def __init__(self, image: Image.Image, label_id: str, model: str):
        super().__init__()
        self.image, self.label_id, self.model = image, label_id, model
        self.signals = PrintSignals()

    def run(self) -> None:
        printer = find_brother_lp()
        if printer is None:
            self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
            return
        try:
            status = print_image(self.image, self.label_id, model=self.model, printer=printer)
        except PrintError as e:
            self.signals.failed.emit(str(e))
            return
        except Exception as e:  # kein Absturz des Threads; Meldung statt Traceback
            self.signals.failed.emit(f"Unerwarteter Fehler beim Drucken: {e}")
            return
        self.signals.done.emit(status)
