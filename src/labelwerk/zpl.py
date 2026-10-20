"""Zebra label printers directly in their printer language ZPL – without driver and without Qt.

Each label becomes an image (``^GFA``, rows compressed with Zebra's ASCII method) at
the resolution of the printer; a series is one data stream, generated label by label. It is sent
raw to ``/dev/usb/lpN`` (``zpl+file://…``) or to TCP port 9100 (``zpl+tcp://host:9100``).
The printer reports nothing back – "sent" does not mean "printed".

Resolution: Zebra counts in dots per mm – "203 dpi" is 8, "300 dpi" 12, "600 dpi" 24 dots/mm
(203.2 / 304.8 / 609.6 dpi). The labels therefore carry 203, 305 and 610 dpi.
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
from .i18n import N_, _
from .labels import sized_id

PREFIX = "zpl:"                    # model ID: zpl:203, zpl:300, zpl:600 (name as at the manufacturer)
URI_PREFIXES = ("zpl+file://", "zpl+tcp://")
RESOLUTIONS = (203, 300, 600)
DOTS_PER_MM = {203: 8, 300: 12, 600: 24}
DEFAULT_DPI = 203
VENDOR_ID = "0a5f"
PORT = 9100
TIMEOUT_S = 5                      # establishing the connection
WRITE_TIMEOUT_S = 30               # per data block: for this long the printer may accept no data
CHUNK = 64 * 1024
MAX_GRAPHIC = 99_999               # bytes per ^GFA (older firmware) – larger images in strips
# common labels (width × height in mm): 2×1", 57×32, 3×2", 4×2", 4×3", 4×4", 4×6" …
MEDIA = ((51, 25), (57, 32), (38, 25), (60, 40), (76, 51), (102, 51), (102, 76), (102, 102),
         (102, 152))
# After printing: "" = as set on the printer (no ^MM), otherwise ^MMT/C/P; titles and names only
# marked – displayed translated via ``cut_option()``
MODES = {"": N_("As set on the printer"), "T": N_("Tear off"), "C": N_("Cut (cutter only)"),
         "P": N_("Peel off (dispenser only)")}
CUT_OPTION = CutOption("mode", N_("After printing"), tuple(MODES), "", tuple(MODES.values()))


def cut_option() -> CutOption:
    """``CUT_OPTION`` for display: titles and names of the modes in the configured language."""
    return CutOption(CUT_OPTION.key, _(CUT_OPTION.title), CUT_OPTION.choices, CUT_OPTION.default,
                     tuple(_(text) for text in CUT_OPTION.labels))


class ZplError(Exception):
    """Sending failed (message for the user)."""


def is_model(model) -> bool:
    return isinstance(model, str) and model.startswith(PREFIX) and model[len(PREFIX):] in {
        str(d) for d in RESOLUTIONS}


def model_for(dpi: int) -> str:
    return f"{PREFIX}{dpi}"


def dpi_of(model: str) -> int:
    """Resolution of the labels of a model: dots per mm × 25.4 (rounded)."""
    return round(DOTS_PER_MM[int(model[len(PREFIX):])] * 25.4)


def label_ids(model: str) -> list[str]:
    """Labels of a Zebra model: ``MEDIA`` at its resolution."""
    return [sized_id(w, h, dpi_of(model)) for w, h in MEDIA]


def dpi_from_id(text: str) -> int | None:
    """Resolution from an IEEE-1284 ID or a name ("ZD420-300dpi", "ZT410 600 dpi")."""
    m = re.search(r"(203|300|600)\s*dpi", text, re.I)
    return int(m[1]) if m else None


def speaks_zpl(ieee1284: str) -> bool:
    """Does the printer understand ZPL? Not if its ID names command sets (``CMD:``/``COMMAND SET:``)
    without ZPL (EPL devices such as LP 2844, card printers); without information: yes."""
    for part in ieee1284.split(";"):
        key, __, value = part.partition(":")
        if key.strip().upper() in ("CMD", "COMMAND SET"):
            return "ZPL" in value.upper()
    return True


# --- ZPL ------------------------------------------------------------------------------------------
def _count(n: int) -> str:
    """Repeat count after Zebra: g–z = 20…400, G–Y = 1…19 (combined, n ≤ 419)."""
    high, low = divmod(n, 20)
    return (chr(ord("f") + high) if high else "") + (chr(ord("F") + low) if low else "")


def _compress_row(row: str) -> str:
    """One hex row: runs of equal characters with a count in front, zeros at the end as ","."""
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
    """Image as a bit sequence for ZPL (1 = dot), rows padded with white to whole bytes."""
    img = image.convert("L").point(lambda v: 0 if v < 128 else 255).convert("1")
    row_bytes = (img.width + 7) // 8
    padded = Image.new("1", (row_bytes * 8, img.height), 1)    # padding bits white, not black
    padded.paste(img, (0, 0))
    return bytes(b ^ 0xFF for b in padded.tobytes()), row_bytes   # Pillow: 1 = white


def _graphic(data: bytes, row_bytes: int, first: int, last: int) -> str:
    rows, previous = [], None
    for y in range(first, last):
        row = data[y * row_bytes:(y + 1) * row_bytes].hex().upper()
        rows.append(":" if row == previous else _compress_row(row))
        previous = row
    total = row_bytes * (last - first)
    return f"^GFA,{total},{total},{row_bytes},{''.join(rows)}"


def graphic(image: Image.Image) -> str:
    """``^GFA`` of an image (black = dot): bytes per row, compressed rows, the same row
    repeated as ":" – at most ``MAX_GRAPHIC`` bytes, otherwise use ``fields``."""
    data, row_bytes = _bits(image)
    return _graphic(data, row_bytes, 0, image.height)


def fields(image: Image.Image) -> str:
    """Image as ``^FO0,y^GFA…^FS`` fields: in horizontal strips of at most ``MAX_GRAPHIC``
    bytes (older firmware accepts no more per graphic)."""
    data, row_bytes = _bits(image)
    band = max(1, MAX_GRAPHIC // row_bytes)
    return "".join(f"^FO0,{y}{_graphic(data, row_bytes, y, min(y + band, image.height))}^FS"
                   for y in range(0, image.height, band))


def label(image: Image.Image, mode: str = "") -> bytes:
    """ZPL of a label: ``^XA [^MM<mode>] ^PW ^LL ^LH0,0 ^FO…^GFA…^FS ^PQ1 ^XZ``."""
    if mode not in MODES:
        raise ValueError(_("Unknown mode {mode!r} – allowed: {allowed}").format(
            mode=mode, allowed=", ".join(m for m in MODES if m)))
    head = f"^MM{mode}" if mode else ""
    return (f"^XA{head}^PW{image.width}^LL{image.height}^LH0,0{fields(image)}^PQ1^XZ\n"
            .encode("ascii"))


def stream(images: Iterable[Image.Image], mode: str = "") -> Iterator[bytes]:
    """ZPL label by label (a series does not need everything in memory at once)."""
    for image in images:
        yield label(image, mode)


def build(images: list[Image.Image], mode: str = "") -> bytes:
    """ZPL for ``images`` (one label each at printer resolution, width across the print head)."""
    return b"".join(stream(images, mode))


# --- Sending ---------------------------------------------------------------------------------------
def _is_device(info: os.stat_result) -> bool:
    """Printer device (character device); tests replace the check."""
    return stat.S_ISCHR(info.st_mode)


def send(data: bytes | Iterable[bytes], uri: str) -> None:
    """Send ZPL raw to the printer: ``zpl+file:///dev/usb/lpN`` or ``zpl+tcp://host[:port]``;
    ``data`` also piece by piece (``stream``)."""
    chunks = [data] if isinstance(data, bytes) else data
    if uri.startswith("zpl+file://"):
        return _send_device(chunks, uri[len("zpl+file://"):])
    if uri.startswith("zpl+tcp://"):
        return _send_network(chunks, uri)
    raise ZplError(_("Not a Zebra address: {uri}").format(uri=uri))


def _send_device(chunks: Iterable[bytes], path: str) -> None:
    """To the device: without creating it, non-blocking with a time limit per block (usblp otherwise
    waits forever if paper is missing or the printer is paused), every block written completely."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    except FileNotFoundError:
        raise ZplError(_("Zebra printer not found: {path} – switched on, cable?").format(
            path=path)) from None
    except PermissionError:
        raise ZplError(_("No permission for {device} – is the user in group 'lp'?").format(
            device=path)) from None
    except OSError as e:
        raise ZplError(_("Zebra printer not reachable: {path} ({reason})").format(
            path=path, reason=e.strerror or e)) from None
    sent = 0
    try:
        if not _is_device(os.fstat(fd)):
            raise ZplError(_("{path} is not a printer device").format(path=path))
        poller = select.poll()
        poller.register(fd, select.POLLOUT)
        for chunk in chunks:
            view = memoryview(chunk)
            while view:
                if not poller.poll(WRITE_TIMEOUT_S * 1000):
                    raise ZplError(_("Zebra printer does not accept data ({sent} bytes sent) – "
                                     "paper, ribbon, paused?").format(sent=sent))
                try:
                    n = os.write(fd, view[:CHUNK])
                except BlockingIOError:
                    continue
                view, sent = view[n:], sent + n
    except OSError as e:
        raise ZplError(_("Sending to {path} aborted after {sent} bytes ({reason})").format(
            path=path, sent=sent, reason=e.strerror or e)) from None
    finally:
        os.close(fd)


def _send_network(chunks: Iterable[bytes], uri: str) -> None:
    """Via TCP: time limit for establishing the connection, then per block (a slow printer may
    accept a large job)."""
    parts = urlsplit(uri[len("zpl+"):])
    try:
        port = parts.port or PORT
    except ValueError:
        raise ZplError(_("Invalid address: {uri}").format(uri=uri)) from None
    if not parts.hostname:
        raise ZplError(_("Invalid address: {uri}").format(uri=uri))
    try:
        conn = socket.create_connection((parts.hostname, port), timeout=TIMEOUT_S)
    except OSError as e:
        raise ZplError(_("Zebra printer {host} not reachable ({reason}) – switched on, in the "
                         "same network, address correct?").format(
            host=parts.hostname, reason=e.strerror or e)) from None
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
            raise ZplError(_("Connection to {host} aborted after {sent} bytes ({reason})").format(
                host=parts.hostname, sent=sent, reason=e.strerror or e)) from None
