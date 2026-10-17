"""Eingelegte Rolle vom Drucker abfragen („Medium prüfen“) – reine Statusabfrage, druckt nichts."""
from __future__ import annotations

import os
import select
import time
from dataclasses import dataclass

from brother_ql.reader import RESP_MEDIA_TYPES, interpret_response

from .labels import labels_for_model

# Puffer leeren (Invalidate), initialisieren (ESC @), Status anfragen (ESC i S)
STATUS_REQUEST = b"\x00" * 200 + b"\x1b\x40" + b"\x1b\x69\x53"
TIMEOUT_S = 2.0
_KINDS = {"Continuous length tape": "endless", "Die-cut labels": "die_cut", "No media": "none"}


class MediaError(ValueError):
    """Rolle konnte nicht ermittelt werden; die Meldung ist für Nutzer gedacht."""


@dataclass(frozen=True)
class Media:
    width_mm: int
    length_mm: int
    kind: str                # "endless", "die_cut" oder "none"

    def describe(self) -> str:
        if self.kind == "none":
            return "keine Rolle eingelegt"
        if self.kind == "endless":
            return f"{self.width_mm} mm endlos"
        return f"{self.width_mm} × {self.length_mm} mm gestanzt"


def read_media(printer: str, timeout: float = TIMEOUT_S) -> Media:
    """Rolle im Drucker (``file:///dev/usb/lpN``) abfragen."""
    return parse_media(query_status(printer, timeout))


def parse_media(data: bytes) -> Media:
    if len(data) > 11 and data[11] not in RESP_MEDIA_TYPES:
        raise MediaError(f"Unbekannte Rolle (Code 0x{data[11]:02X})")
    try:
        status = interpret_response(data)
    except Exception as e:  # brother_ql wirft je nach Fehler NameError, UnboundLocalError …
        raise MediaError(f"Unverständliche Antwort vom Drucker: {e}") from None
    kind = _KINDS.get(status["media_type"])
    if kind is None:
        raise MediaError(f"Unbekannte Rolle: {status['media_type']}")
    if kind == "none" or status["media_width"] == 0:
        return Media(0, 0, "none")
    if status["errors"]:
        raise MediaError("Drucker meldet: " + ", ".join(status["errors"]))
    return Media(status["media_width"], status["media_length"], kind)


def label_for_media(media: Media, model: str = "QL-600") -> str | None:
    """Passende Etikett-ID zur eingelegten Rolle, sonst None."""
    for label in labels_for_model(model):
        if media.kind == "endless" and label.shape == "endless" \
                and label.size_mm[0] == media.width_mm:
            return label.id
        if media.kind == "die_cut" and label.shape in ("die_cut", "round") \
                and label.size_mm == (media.width_mm, media.length_mm):
            return label.id
    return None


def _open_device(path: str) -> int:
    return os.open(path, os.O_RDWR | os.O_NONBLOCK)


def query_status(printer: str, timeout: float = TIMEOUT_S, opener=_open_device) -> bytes:
    """Statusabfrage senden und die 32-Byte-Antwort lesen – mit festem Zeitlimit, nie blockierend."""
    if not printer.startswith("file://"):
        raise MediaError("Medium prüfen geht nur über /dev/usb/lpN (Backend linux_kernel).")
    try:
        fd = opener(printer[len("file://"):])
    except FileNotFoundError:
        raise MediaError(f"Drucker nicht gefunden: {printer}") from None
    except PermissionError:
        raise MediaError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?") from None
    except OSError as e:
        raise MediaError(f"Drucker nicht erreichbar: {e}") from None
    try:
        os.write(fd, STATUS_REQUEST)
        data, deadline = b"", time.monotonic() + timeout
        while len(data) < 32:
            left = deadline - time.monotonic()
            if left <= 0:
                raise MediaError("Keine Antwort vom Drucker auf die Statusabfrage.")
            ready, _, _ = select.select([fd], [], [], min(left, 0.1))
            if ready:
                try:
                    data += os.read(fd, 32 - len(data))
                except BlockingIOError:
                    pass
        return data
    except OSError as e:
        raise MediaError(f"Fehler bei der Statusabfrage: {e}") from None
    finally:
        os.close(fd)
