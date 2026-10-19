"""Erzeugt Brother-Rasterdaten und sendet sie an den Drucker."""
from __future__ import annotations

import socket
from collections.abc import Callable

from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from brother_ql.raster import BrotherQLRaster
from PIL import Image

from .document import CUTS
from .labels import get_label, labels_for_model
from .printers import DEFAULT_MODEL, backend_for, capabilities

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


class PrintCancelled(Exception):
    """Serie abgebrochen (vor einem Teilauftrag) – kein Fehler; ``printed`` von ``total`` sind
    schon gesendet."""

    def __init__(self, printed: int, total: int):
        self.printed, self.total = printed, total
        super().__init__(f"Abgebrochen – {printed} von {total} Etiketten gedruckt" if printed
                         else "Abgebrochen – nichts gedruckt")


MAX_CUT_EVERY = 255         # Brother ESC i A n: höchstens alle 255 Etiketten
# Teilaufträge: Der Drucker meldet Fehler nur kurz nach dem Senden (brother_ql: 10 s ab Beginn) –
# lange Serien gehen deshalb in Teilen hinaus, jeder wird geprüft. „Nur am Ende“ schneidet nach
# jedem Teil (er ist so lang wie der Schnittabstand), „nach jedem“ merkt nichts davon. Zwischen
# den Teilen lässt sich abbrechen – kleine Teile, damit das schnell wirkt.
MAX_JOB_EACH = 10
THRESHOLD = 70.0            # brother_ql: ein Punkt druckt ab (100 − THRESHOLD) % Schwarz
CONNECT_TIMEOUT_S = 5       # Netzwerkdrucker: so lange auf die Verbindung warten


_LEVEL = min(255, max(0, int((100.0 - THRESHOLD) / 100.0 * 255)))   # wie brother_ql.convert


def to_print_mode(image: Image.Image, red: bool = False) -> Image.Image:
    """Druckbild als 1-Bit-Bild mit derselben Schwelle wie brother_ql – druckt bitgleich, braucht
    aber nur ein Vierundzwanzigstel des Speichers von RGB (Serien mit vielen Etiketten).
    ``red`` (Etikett Rot/Schwarz): reines Schwarz, Rot, Weiß (``pure_colors``) – 1 Bit verlöre
    das Rot."""
    if red:
        return pure_colors(image)
    return image.convert("L").point(lambda v: 0 if 255 - v >= _LEVEL else 255, mode="1")


def pure_colors(image: Image.Image) -> Image.Image:
    """Druckbild Rot/Schwarz auf reine Farben gebracht – mit derselben Schwelle wie ein
    Schwarz-Weiß-Etikett (brother_ql nähme sonst nur sehr dunkle Punkte als Schwarz, Text würde
    dünner als in der Vorschau). Schwarze Tinte senkt alle Kanäle, rote nur Grün und Blau:
    Schwarz, wo Rot dunkel genug ist; Rot, wo sonst Grün dunkel genug ist."""
    r, g, _ = image.convert("RGB").split()
    black = r.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
    red = g.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
    out = Image.new("RGB", image.size, "white")
    out.paste((255, 0, 0), (0, 0), red)
    out.paste((0, 0, 0), (0, 0), black)
    return out


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
    schneiden (ohne Abschneider des Modells nie), ``cut_every``: alle n Etiketten
    (``cut_interval``) und am Ende. Etiketten Rot/Schwarz (62red) mit Rot-Ebene."""
    images = [images] if isinstance(images, Image.Image) else list(images)
    if not images:
        raise ValueError("Keine Etiketten zum Drucken")
    if not isinstance(cut_every, int) or isinstance(cut_every, bool) or cut_every < 1:
        raise ValueError(f"Schneiden alle n Etiketten: n muss eine ganze Zahl ab 1 sein, "
                         f"nicht {cut_every!r}")
    if label_id not in {label.id for label in labels_for_model(model)}:
        raise ValueError(f"Etikett {label_id!r} passt nicht zum {model} – siehe "
                         f"'labelwerk -m {model} labels'")
    qlr = _Raster(model, cut_every)
    qlr.exception_on_warning = True
    red = get_label(label_id).two_color          # nur Zweifarb-Modelle haben 62red (oben geprüft)
    return bytes(convert(
        qlr=qlr,
        images=[pure_colors(img) for img in images] if red else images,
        label=label_id,
        rotate="0",
        threshold=THRESHOLD,
        dither=False,
        compress=False,
        red=red,
        dpi_600=False,
        hq=True,
        cut=cut and capabilities(model).cutter,
    ))


def print_image(
    image: Image.Image | list[Image.Image],
    label_id: str,
    model: str = DEFAULT_MODEL,
    printer: str = DEFAULT_PRINTER,
    backend: str | None = None,
    cut: bool = True,
    cut_every: int = 1,
    cancelled: Callable[[], bool] | None = None,
    progress: Callable[[int, int], None] | None = None,
    options: dict[str, str] | None = None,
) -> dict:
    """Ein Etikett oder mehrere (Serie) drucken; Status von brother_ql (des letzten Teils).

    Eine Serie geht in Teilaufträgen hinaus (``MAX_JOB_EACH`` bzw. ``cut_every`` Etiketten), jeder
    wird geprüft; ein Fehler bricht ab und nennt – waren schon Teile gedruckt – die betroffenen
    Etiketten. ``cancelled()`` wird vor jedem Teil gefragt (True → ``PrintCancelled``; ein
    gesendeter Teil läuft zu Ende), ``progress(gedruckt, alle)`` nach jedem. ``backend``: None =
    aus der URI (``tcp://`` → Netzwerk: ein Auftrag – der Drucker meldet dort keinen Status).
    ``cups:NAME``: ein Auftrag an die CUPS-Warteschlange (``options``: Treiber-Optionen, z. B.
    Schnitt); Status ``{"outcome": "sent", "job": Kennung}``. ``zpl+file://…``/``zpl+tcp://…``:
    Zebra, ein Datenstrom (``options["mode"]``: "" wie am Drucker, T/C/P); Status
    ``{"outcome": "sent"}``."""
    backend = backend or backend_for(printer)
    images = [image] if isinstance(image, Image.Image) else list(image)
    if label_id not in {label.id for label in labels_for_model(model)}:
        raise PrintError(f"Etikett {label_id!r} passt nicht zum Drucker ({model}).")
    if backend == "cups":
        return _print_cups(printer[len("cups:"):], images, label_id, options, cancelled)
    if backend == "zpl":
        return _print_zpl(printer, images, options, cancelled)
    if backend == "network":
        _reachable(printer)
    part = MAX_JOB_EACH if cut_every == 1 else min(cut_every, MAX_CUT_EVERY)
    if backend == "network" and cut_every == 1:
        # übers Netz meldet der Drucker keinen Status: Teile ließen sich weder prüfen noch abbrechen
        part = max(1, len(images))
    status: dict = {}
    for start in range(0, len(images), part):
        if cancelled is not None and cancelled():
            raise PrintCancelled(start, len(images))
        chunk = images[start:start + part]
        try:
            status = _send(build_instructions(chunk, label_id, model=model, cut=cut,
                                              cut_every=cut_every),
                           label_id, printer, backend)
        except PrintError as e:
            if start == 0:                  # noch nichts gedruckt: Meldung wie bei einem Etikett
                raise
            # der Drucker meldet verzögert – der Fehler kann auch zu Etiketten davor gehören
            raise PrintError(f"Fehler bei Etikett {start + 1}–{start + len(chunk)} von {len(images)} "
                             f"(auch die davor prüfen): {e}") from None
        if progress is not None:
            progress(start + len(chunk), len(images))
    return status


def _print_cups(name: str, images: list[Image.Image], label_id: str,
                options: dict[str, str] | None, cancelled: Callable[[], bool] | None) -> dict:
    """An CUPS übergeben – ein Auftrag; danach druckt die Warteschlange (Abbrechen dort)."""
    from . import cups
    if cancelled is not None and cancelled():
        raise PrintCancelled(0, len(images))
    label = get_label(label_id)
    try:
        job = cups.print_images(name, images, *label.size_mm, label.dpi, options)
    except cups.CupsError as e:
        raise PrintError(str(e)) from None
    return {"outcome": "sent", "did_print": False, "job": job.id}


def _print_zpl(uri: str, images: list[Image.Image], options: dict[str, str] | None,
               cancelled: Callable[[], bool] | None) -> dict:
    """Zebra: alle Etiketten als ein ZPL-Datenstrom (der Drucker meldet keinen Status)."""
    from . import zpl
    if cancelled is not None and cancelled():
        raise PrintCancelled(0, len(images))
    mode = (options or {}).get("mode", "")
    try:
        zpl.send(zpl.stream(images, mode if mode in zpl.MODES else ""), uri)
    except zpl.ZplError as e:
        raise PrintError(str(e)) from None
    return {"outcome": "sent", "did_print": False}


def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
    try:
        status = send(instructions=data, printer_identifier=printer,
                      backend_identifier=backend, blocking=True)
    except OSError as e:                  # pyusb: USBError ist ein OSError
        if backend != "network":
            raise _usb_error(e, printer) from None
        raise PrintError(f"Netzwerkdrucker {printer} nicht erreichbar ({e.strerror or e}) – "
                         "eingeschaltet, im selben Netz, Adresse richtig?") from None
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


def _usb_error(e: OSError, printer: str) -> PrintError:
    """Verständliche Meldung für ein fehlendes, gesperrtes oder belegtes USB-Gerät."""
    if isinstance(e, PermissionError):
        return PrintError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?")
    if isinstance(e, FileNotFoundError):
        return PrintError(f"Drucker nicht gefunden: {printer}\n"
                          "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', "
                          "'lsmod | grep usblp'.")
    return PrintError(f"Drucker {printer} nicht bereit ({e.strerror or e}) – belegt oder "
                      "gerade beschäftigt? Kurz warten bzw. aus- und einschalten.")


def _reachable(printer: str) -> None:
    """Netzwerkdrucker vorab mit Zeitlimit ansprechen – brother_ql wartet sonst ohne Grenze
    (bei einer falschen Adresse rund zwei Minuten)."""
    host, _, port = printer[len("tcp://"):].partition(":")
    try:
        socket.create_connection((host, int(port or 9100)), timeout=CONNECT_TIMEOUT_S).close()
    except (OSError, ValueError) as e:
        reason = "keine Antwort" if isinstance(e, TimeoutError) else getattr(e, "strerror", None) or e
        raise PrintError(f"Netzwerkdrucker {printer} nicht erreichbar ({reason}) – "
                         "eingeschaltet, im selben Netz, Adresse richtig?") from None
