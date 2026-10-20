"""“Check media” in a background thread (status query, prints nothing)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from ..i18n import _
from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
from ..media import MediaError, label_for_media, read_media


class MediaSignals(QObject):
    found = Signal(object, object)   # Media, label ID or None
    failed = Signal(str)             # message for the PAPER panel


class MediaWorker(QRunnable):
    def __init__(self, model: str, printer: str | None = None):
        super().__init__()
        self.model = model
        self.printer = printer                     # URI of the chosen USB printer; None = search
        self.signals = MediaSignals()

    def run(self) -> None:
        try:
            printer = self.printer or find_brother_lp()
            if printer is None:
                self.signals.failed.emit(_(BUSY_MESSAGE) if brother_busy() else _(PRINTER_NOT_FOUND))
                return
            media = read_media(printer)
        except MediaError as e:
            self.signals.failed.emit(str(e))
            return
        except Exception as e:  # no thread crash; message instead of traceback
            self.signals.failed.emit(_("Unexpected error while checking the roll: {error}").format(error=e))
            return
        self.signals.found.emit(media, label_for_media(media, self.model))
