"""Erzeugt Brother-Rasterdaten und sendet sie an den Drucker."""
from __future__ import annotations

from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from brother_ql.raster import BrotherQLRaster
from PIL import Image

from .document import CUTS

DEFAULT_MODEL = "QL-600"
DEFAULT_BACKEND = "linux_kernel"
DEFAULT_PRINTER = "file:///dev/usb/lp0"

# Fehlertexte aus brother_ql.reader -> verständliche Meldung
_PRINTER_ERRORS = {
    "Replace media error": "Eingelegte Rolle passt nicht zum Etikett {label!r} – "
                           "Rolle prüfen oder anderes Etikett wählen.",
    "No media when printing": "Keine Rolle eingelegt.",
    "End of media (die-cut size only)": "Etikettenrolle ist leer.",
    "Media cannot be fed (also when the media end is detected)":
        "Band kann nicht transportiert werden – Rolle leer oder falsch eingelegt?",
    "Tape cutter jam": "Schneidwerk blockiert.",
    "Cover opened while printing (Except QL-500)": "Deckel während des Drucks geöffnet.",
}


class PrintError(Exception):
    """Druck fehlgeschlagen; die Meldung ist für Nutzer gedacht."""


MAX_CUT_EVERY = 255         # Brother ESC i A n: höchstens alle 255 Etiketten
# Teilaufträge: Der Drucker meldet Fehler nur kurz nach dem Senden (brother_ql: 10 s ab Beginn) –
# lange Serien gehen deshalb in Teilen hinaus, jeder wird geprüft. „Nur am Ende“ schneidet nach
# jedem Teil (er ist so lang wie der Schnittabstand), „nach jedem“ merkt nichts davon.
MAX_JOB_EACH = 50
THRESHOLD = 70.0            # brother_ql: ein Punkt druckt ab (100 − THRESHOLD) % Schwarz


def to_print_mode(image: Image.Image) -> Image.Image:
    """Druckbild als 1-Bit-Bild mit derselben Schwelle wie brother_ql – druckt bitgleich, braucht
    aber nur ein Vierundzwanzigstel des Speichers von RGB (Serien mit vielen Etiketten)."""
    level = min(255, max(0, int((100.0 - THRESHOLD) / 100.0 * 255)))   # wie brother_ql.convert
    return image.convert("L").point(lambda v: 0 if 255 - v >= level else 255, mode="1")


def cut_interval(mode: str, count: int) -> int:
    """Schneiden alle n Etiketten: „each“ → 1, „end“ → alle (bei mehr als 255 Etiketten
    zusätzlich nach je 255 – mehr kann der Drucker nicht)."""
    if mode not in CUTS:
        raise ValueError(f"Unbekannter Schnitt {mode!r} – erlaubt: {', '.join(CUTS)}")
    return 1 if mode == "each" else max(1, min(count, MAX_CUT_EVERY))


class _Raster(BrotherQLRaster):
    """brother_ql für Serien: Schnittabstand wählbar (sonst fest nach jedem Etikett), Seiten
    nach der ersten als Folgeseiten gekennzeichnet (ESC i z, n9) und Daten in einem
    ``bytearray`` – ``bytes +=`` kopierte bei jedem Befehl alles (lange Serien: Minuten)."""

    def __init__(self, model: str, cut_every: int):
        super().__init__(model)
        self.data = bytearray(self.data)
        self._cut_every = min(cut_every, MAX_CUT_EVERY)

    def add_cut_every(self, n: int = 1) -> None:
        super().add_cut_every(self._cut_every)

    def add_print(self, last_page: bool = True) -> None:
        super().add_print(last_page)
        self.page_number += 1


def build_instructions(
    images: Image.Image | list[Image.Image], label_id: str, model: str = DEFAULT_MODEL,
    cut: bool = True, cut_every: int = 1,
) -> bytes:
    """Rasterdaten für ein Etikett oder mehrere in einem Auftrag (Serie); ``cut``: überhaupt
    schneiden, ``cut_every``: alle n Etiketten (``cut_interval``) und am Ende."""
    images = [images] if isinstance(images, Image.Image) else list(images)
    if not images:
        raise ValueError("Keine Etiketten zum Drucken")
    if not isinstance(cut_every, int) or isinstance(cut_every, bool) or cut_every < 1:
        raise ValueError(f"Schneiden alle n Etiketten: n muss eine ganze Zahl ab 1 sein, "
                         f"nicht {cut_every!r}")
    qlr = _Raster(model, cut_every)
    qlr.exception_on_warning = True
    return bytes(convert(
        qlr=qlr,
        images=images,
        label=label_id,
        rotate="0",
        threshold=THRESHOLD,
        dither=False,
        compress=False,
        red=False,
        dpi_600=False,
        hq=True,
        cut=cut,
    ))


def print_image(
    image: Image.Image | list[Image.Image],
    label_id: str,
    model: str = DEFAULT_MODEL,
    printer: str = DEFAULT_PRINTER,
    backend: str = DEFAULT_BACKEND,
    cut: bool = True,
    cut_every: int = 1,
) -> dict:
    """Ein Etikett oder mehrere (Serie) drucken; Status von brother_ql (des letzten Teils).

    Eine Serie geht in Teilaufträgen hinaus (``MAX_JOB_EACH`` bzw. ``cut_every`` Etiketten), jeder
    wird geprüft; ein Fehler bricht ab und nennt – waren schon Teile gedruckt – die betroffenen
    Etiketten."""
    images = [image] if isinstance(image, Image.Image) else list(image)
    part = MAX_JOB_EACH if cut_every == 1 else min(cut_every, MAX_CUT_EVERY)
    status: dict = {}
    for start in range(0, len(images), part):
        chunk = images[start:start + part]
        try:
            status = _send(build_instructions(chunk, label_id, model=model, cut=cut,
                                              cut_every=cut_every),
                           label_id, printer, backend)
        except PrintError as e:
            if start == 0:                  # noch nichts gedruckt: Meldung wie bei einem Etikett
                raise
            raise PrintError(f"Etikett {start + 1}–{start + len(chunk)} von {len(images)}: "
                             f"{e}") from None
    return status


def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
    try:
        status = send(instructions=data, printer_identifier=printer,
                      backend_identifier=backend, blocking=True)
    except FileNotFoundError:
        raise PrintError(f"Drucker nicht gefunden: {printer}\n"
                         "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', "
                         "'lsmod | grep usblp'.") from None
    except PermissionError:
        raise PrintError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?") from None
    except ValueError as e:
        if str(e) != "Device not found":  # pyusb
            raise
        raise PrintError(f"Drucker nicht gefunden: {printer}\n"
                         "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'.") from None

    errors = (status.get("printer_state") or {}).get("errors") or []
    if errors:
        raise PrintError("\n".join(
            _PRINTER_ERRORS.get(err, "Druckerfehler: {err}").format(label=label_id, err=err)
            for err in errors))
    return status
