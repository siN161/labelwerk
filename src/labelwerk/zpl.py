"""Zebra-Etikettendrucker direkt in ihrer Druckersprache ZPL – ohne Treiber und ohne Qt.

Jedes Etikett wird ein Bild (``^GFA``, Zeilen komprimiert nach dem ASCII-Verfahren von Zebra) in
der Auflösung des Druckers; eine Serie ist ein Datenstrom, Etikett für Etikett erzeugt. Gesendet
wird roh an ``/dev/usb/lpN`` (``zpl+file://…``) bzw. an TCP-Port 9100 (``zpl+tcp://host:9100``).
Der Drucker meldet nichts zurück – „gesendet“ heißt nicht „gedruckt“.

Auflösung: Zebra rechnet in Punkten je mm – „203 dpi“ sind 8, „300 dpi“ 12, „600 dpi“ 24 Punkte/mm
(203,2 / 304,8 / 609,6 dpi). Die Etiketten tragen deshalb 203, 305 bzw. 610 dpi.
"""
from __future__ import annotations

import os
import re
import select
import socket
import stat
from collections.abc import Iterable, Iterator
from urllib.parse import urlsplit

from PIL import Image

from .cups import CutOption
from .labels import sized_id

PREFIX = "zpl:"                    # Modell-ID: zpl:203, zpl:300, zpl:600 (Name wie beim Hersteller)
URI_PREFIXES = ("zpl+file://", "zpl+tcp://")
RESOLUTIONS = (203, 300, 600)
DOTS_PER_MM = {203: 8, 300: 12, 600: 24}
DEFAULT_DPI = 203
VENDOR_ID = "0a5f"
PORT = 9100
TIMEOUT_S = 5                      # Verbindung aufbauen
WRITE_TIMEOUT_S = 30               # je Datenblock: so lange darf der Drucker keine Daten annehmen
CHUNK = 64 * 1024
MAX_GRAPHIC = 99_999               # Bytes je ^GFA (ältere Firmware) – größere Bilder in Streifen
# gängige Etiketten (Breite × Höhe in mm): 2×1", 57×32, 3×2", 4×2", 4×3", 4×4", 4×6" …
MEDIA = ((51, 25), (57, 32), (38, 25), (60, 40), (76, 51), (102, 51), (102, 76), (102, 102),
         (102, 152))
# Nach dem Druck: "" = wie am Drucker eingestellt (kein ^MM), sonst ^MMT/C/P
MODES = {"": "Wie am Drucker eingestellt", "T": "Abreißen", "C": "Schneiden (nur mit Abschneider)",
         "P": "Ablösen (nur mit Spender)"}
CUT_OPTION = CutOption("mode", "Nach dem Druck", tuple(MODES), "", tuple(MODES.values()))


class ZplError(Exception):
    """Senden gescheitert (Meldung für Nutzer)."""


def is_model(model) -> bool:
    return isinstance(model, str) and model.startswith(PREFIX) and model[len(PREFIX):] in {
        str(d) for d in RESOLUTIONS}


def model_for(dpi: int) -> str:
    return f"{PREFIX}{dpi}"


def dpi_of(model: str) -> int:
    """Auflösung der Etiketten eines Modells: Punkte je mm × 25,4 (gerundet)."""
    return round(DOTS_PER_MM[int(model[len(PREFIX):])] * 25.4)


def label_ids(model: str) -> list[str]:
    """Etiketten eines Zebra-Modells: ``MEDIA`` in seiner Auflösung."""
    return [sized_id(w, h, dpi_of(model)) for w, h in MEDIA]


def dpi_from_id(text: str) -> int | None:
    """Auflösung aus einer IEEE-1284-Kennung oder einem Namen („ZD420-300dpi“, „ZT410 600 dpi“)."""
    m = re.search(r"(203|300|600)\s*dpi", text, re.I)
    return int(m[1]) if m else None


def speaks_zpl(ieee1284: str) -> bool:
    """Versteht der Drucker ZPL? Nennt seine Kennung Befehlssätze (``CMD:``/``COMMAND SET:``)
    ohne ZPL (EPL-Geräte wie LP 2844, Kartendrucker), nicht; ohne Angabe: ja."""
    for part in ieee1284.split(";"):
        key, _, value = part.partition(":")
        if key.strip().upper() in ("CMD", "COMMAND SET"):
            return "ZPL" in value.upper()
    return True


# --- ZPL ------------------------------------------------------------------------------------------
def _count(n: int) -> str:
    """Wiederholungszahl nach Zebra: g–z = 20…400, G–Y = 1…19 (zusammengesetzt, n ≤ 419)."""
    high, low = divmod(n, 20)
    return (chr(ord("f") + high) if high else "") + (chr(ord("F") + low) if low else "")


def _compress_row(row: str) -> str:
    """Eine Hex-Zeile: Folgen gleicher Zeichen mit Zahl davor, Nullen am Ende als „,“."""
    stripped = row.rstrip("0")
    if not stripped:
        return ","
    out, i = [], 0
    while i < len(stripped):
        j = i
        while j < len(stripped) and stripped[j] == stripped[i]:
            j += 1
        n = j - i
        while n > 0:
            take = min(n, 419)
            out.append((_count(take) if take > 1 else "") + stripped[i])
            n -= take
        i = j
    return "".join(out) + ("," if len(stripped) < len(row) else "")


def _bits(image: Image.Image) -> tuple[bytes, int]:
    """Bild als Bitfolge für ZPL (1 = Punkt), Zeilen auf ganze Bytes mit Weiß aufgefüllt."""
    img = image.convert("L").point(lambda v: 0 if v < 128 else 255).convert("1")
    row_bytes = (img.width + 7) // 8
    padded = Image.new("1", (row_bytes * 8, img.height), 1)    # Füllbits weiß, nicht schwarz
    padded.paste(img, (0, 0))
    return bytes(b ^ 0xFF for b in padded.tobytes()), row_bytes   # Pillow: 1 = weiß


def _graphic(data: bytes, row_bytes: int, first: int, last: int) -> str:
    rows, previous = [], None
    for y in range(first, last):
        row = data[y * row_bytes:(y + 1) * row_bytes].hex().upper()
        rows.append(":" if row == previous else _compress_row(row))
        previous = row
    total = row_bytes * (last - first)
    return f"^GFA,{total},{total},{row_bytes},{''.join(rows)}"


def graphic(image: Image.Image) -> str:
    """``^GFA`` eines Bilds (schwarz = Punkt): Bytes je Zeile, komprimierte Zeilen, gleiche Zeile
    hintereinander als „:“ – höchstens ``MAX_GRAPHIC`` Bytes, sonst ``fields`` nehmen."""
    data, row_bytes = _bits(image)
    return _graphic(data, row_bytes, 0, image.height)


def fields(image: Image.Image) -> str:
    """Bild als ``^FO0,y^GFA…^FS``-Felder: in waagrechten Streifen zu höchstens ``MAX_GRAPHIC``
    Bytes (ältere Firmware nimmt nicht mehr je Grafik)."""
    data, row_bytes = _bits(image)
    band = max(1, MAX_GRAPHIC // row_bytes)
    return "".join(f"^FO0,{y}{_graphic(data, row_bytes, y, min(y + band, image.height))}^FS"
                   for y in range(0, image.height, band))


def label(image: Image.Image, mode: str = "") -> bytes:
    """ZPL eines Etiketts: ``^XA [^MM<Modus>] ^PW ^LL ^LH0,0 ^FO…^GFA…^FS ^PQ1 ^XZ``."""
    if mode not in MODES:
        raise ValueError(f"Unbekannter Modus {mode!r} – erlaubt: {', '.join(m for m in MODES if m)}")
    head = f"^MM{mode}" if mode else ""
    return (f"^XA{head}^PW{image.width}^LL{image.height}^LH0,0{fields(image)}^PQ1^XZ\n"
            .encode("ascii"))


def stream(images: Iterable[Image.Image], mode: str = "") -> Iterator[bytes]:
    """ZPL Etikett für Etikett (eine Serie braucht nicht alles auf einmal im Speicher)."""
    for image in images:
        yield label(image, mode)


def build(images: list[Image.Image], mode: str = "") -> bytes:
    """ZPL für ``images`` (je ein Etikett in Druckerauflösung, Breite quer zum Druckkopf)."""
    return b"".join(stream(images, mode))


# --- Senden ---------------------------------------------------------------------------------------
def _is_device(info: os.stat_result) -> bool:
    """Druckergerät (Zeichengerät); Tests ersetzen die Prüfung."""
    return stat.S_ISCHR(info.st_mode)


def send(data: bytes | Iterable[bytes], uri: str) -> None:
    """ZPL roh an den Drucker: ``zpl+file:///dev/usb/lpN`` bzw. ``zpl+tcp://host[:port]``;
    ``data`` auch Stück für Stück (``stream``)."""
    chunks = [data] if isinstance(data, bytes) else data
    if uri.startswith("zpl+file://"):
        return _send_device(chunks, uri[len("zpl+file://"):])
    if uri.startswith("zpl+tcp://"):
        return _send_network(chunks, uri)
    raise ZplError(f"Keine Zebra-Adresse: {uri}")


def _send_device(chunks: Iterable[bytes], path: str) -> None:
    """An das Gerät: ohne es anzulegen, nicht blockierend mit Zeitlimit je Block (usblp wartet
    sonst endlos, wenn Papier fehlt oder der Drucker pausiert), jeder Block ganz geschrieben."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    except FileNotFoundError:
        raise ZplError(f"Zebra-Drucker nicht gefunden: {path} – eingeschaltet, Kabel?") from None
    except PermissionError:
        raise ZplError(f"Keine Berechtigung für {path} – Benutzer in Gruppe 'lp'?") from None
    except OSError as e:
        raise ZplError(f"Zebra-Drucker nicht erreichbar: {path} ({e.strerror or e})") from None
    sent = 0
    try:
        if not _is_device(os.fstat(fd)):
            raise ZplError(f"{path} ist kein Druckergerät")
        poller = select.poll()
        poller.register(fd, select.POLLOUT)
        for chunk in chunks:
            view = memoryview(chunk)
            while view:
                if not poller.poll(WRITE_TIMEOUT_S * 1000):
                    raise ZplError(f"Zebra-Drucker nimmt keine Daten an ({sent} Bytes gesendet) – "
                                   "Papier, Farbband, Pause?")
                try:
                    n = os.write(fd, view[:CHUNK])
                except BlockingIOError:
                    continue
                view, sent = view[n:], sent + n
    except OSError as e:
        raise ZplError(f"Senden an {path} abgebrochen nach {sent} Bytes ({e.strerror or e})") from None
    finally:
        os.close(fd)


def _send_network(chunks: Iterable[bytes], uri: str) -> None:
    """Über TCP: Zeitlimit für den Aufbau, danach je Block (ein langsamer Drucker darf einen
    großen Auftrag annehmen)."""
    parts = urlsplit(uri[len("zpl+"):])
    try:
        port = parts.port or PORT
    except ValueError:
        raise ZplError(f"Ungültige Adresse: {uri}") from None
    if not parts.hostname:
        raise ZplError(f"Ungültige Adresse: {uri}")
    try:
        conn = socket.create_connection((parts.hostname, port), timeout=TIMEOUT_S)
    except OSError as e:
        raise ZplError(f"Zebra-Drucker {parts.hostname} nicht erreichbar ({e.strerror or e}) – "
                       "eingeschaltet, im selben Netz, Adresse richtig?") from None
    sent = 0
    with conn:
        conn.settimeout(WRITE_TIMEOUT_S)
        try:
            for chunk in chunks:
                view = memoryview(chunk)
                while view:
                    n = conn.send(view[:CHUNK])
                    view, sent = view[n:], sent + n
        except OSError as e:
            raise ZplError(f"Verbindung zu {parts.hostname} abgebrochen nach {sent} Bytes "
                           f"({e.strerror or e})") from None
