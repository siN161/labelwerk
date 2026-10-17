"""Erzeugt Brother-Rasterdaten und sendet sie an den Drucker."""
from __future__ import annotations

from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from brother_ql.raster import BrotherQLRaster
from PIL import Image

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


def build_instructions(
    image: Image.Image, label_id: str, model: str = DEFAULT_MODEL, cut: bool = True
) -> bytes:
    qlr = BrotherQLRaster(model)
    qlr.exception_on_warning = True
    return convert(
        qlr=qlr,
        images=[image],
        label=label_id,
        rotate="0",
        threshold=70.0,
        dither=False,
        compress=False,
        red=False,
        dpi_600=False,
        hq=True,
        cut=cut,
    )


def print_image(
    image: Image.Image,
    label_id: str,
    model: str = DEFAULT_MODEL,
    printer: str = DEFAULT_PRINTER,
    backend: str = DEFAULT_BACKEND,
    cut: bool = True,
) -> dict:
    data = build_instructions(image, label_id, model=model, cut=cut)
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
