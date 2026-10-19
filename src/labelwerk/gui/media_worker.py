"""„Medium prüfen“ im Hintergrund-Thread (Statusabfrage, druckt nichts)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
from ..media import MediaError, label_for_media, read_media


class MediaSignals(QObject):
    found = Signal(object, object)   # Media, Etikett-ID oder None
    failed = Signal(str)             # Meldung für das Papier-Panel


class MediaWorker(QRunnable):
    def __init__(self, model: str, printer: str | None = None):
        super().__init__()
        self.model = model
        self.printer = printer                     # URI des gewählten USB-Druckers; None = suchen
        self.signals = MediaSignals()

    def run(self) -> None:
        try:
            printer = self.printer or find_brother_lp()
            if printer is None:
                self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
                return
            media = read_media(printer)
        except MediaError as e:
            self.signals.failed.emit(str(e))
            return
        except Exception as e:  # kein Absturz des Threads; Meldung statt Traceback
            self.signals.failed.emit(f"Unerwarteter Fehler beim Prüfen der Rolle: {e}")
            return
        self.signals.found.emit(media, label_for_media(media, self.model))
