"""Generates Brother raster data and sends it to the printer."""
from __future__ import annotations

import socket
from collections.abc import Callable

from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from brother_ql.raster import BrotherQLRaster
from PIL import Image

from .document import CUTS
from .i18n import N_, _, ngettext
from .labels import get_label, labels_for_model
from .printers import DEFAULT_MODEL, backend_for, capabilities, route_fits

DEFAULT_BACKEND = "linux_kernel"
DEFAULT_PRINTER = "file:///dev/usb/lp0"

# error texts from brother_ql.reader -> understandable message (translated when reported)
_PRINTER_ERRORS = {
    "Replace media error": N_("The loaded roll does not match the label {label!r} – "
                              "check the roll or choose another label."),
    "No media when printing": N_("No roll loaded."),
    "End of media (die-cut size only)": N_("The label roll is empty."),
    "Media cannot be fed (also when the media end is detected)":
        N_("The tape cannot be fed – roll empty or loaded incorrectly?"),
    "Tape cutter jam": N_("Cutter jammed."),
    "Cover opened while printing (Except QL-500)": N_("Cover opened while printing."),
}
_PRINTER_ERROR = N_("Printer error: {err}")      # other errors from brother_ql


class PrintError(Exception):
    """Printing failed; the message is meant for users."""


class PrintCancelled(Exception):
    """Series cancelled (before a part job) – not an error; ``printed`` of ``total`` have
    already been sent."""

    def __init__(self, printed: int, total: int):
        self.printed, self.total = printed, total
        super().__init__(ngettext("Cancelled – {printed} of {total} label printed",
                                  "Cancelled – {printed} of {total} labels printed", total).format(
            printed=printed, total=total) if printed else _("Cancelled – nothing printed"))


MAX_CUT_EVERY = 255         # Brother ESC i A n: at most every 255 labels
# Part jobs: the printer reports errors only shortly after sending (brother_ql: 10 s from the start) –
# long series therefore go out in parts, each one is checked. "Only at the end" cuts after
# every part (it is as long as the cut interval), "after each" notices nothing of this. Between
# the parts it can be cancelled – small parts, so that this takes effect quickly.
MAX_JOB_EACH = 10
THRESHOLD = 70.0            # brother_ql: a dot prints from (100 − THRESHOLD) % black
CONNECT_TIMEOUT_S = 5       # network printer: wait this long for the connection
_UNREACHABLE = N_("Network printer {printer} not reachable ({reason}) – switched on, in the same "
                  "network, address correct?")


_LEVEL = min(255, max(0, int((100.0 - THRESHOLD) / 100.0 * 255)))   # like brother_ql.convert


def to_print_mode(image: Image.Image, red: bool = False) -> Image.Image:
    """Print image as a 1-bit image with the same threshold as brother_ql – prints bit-identical, but
    needs only a twenty-fourth of the memory of RGB (series with many labels).
    ``red`` (red/black label): pure black, red, white (``pure_colors``) – 1 bit would lose the
    red."""
    if red:
        return pure_colors(image)
    return image.convert("L").point(lambda v: 0 if 255 - v >= _LEVEL else 255, mode="1")


def pure_colors(image: Image.Image) -> Image.Image:
    """Print image red/black brought to pure colours – with the same threshold as a
    black-and-white label (brother_ql would otherwise take only very dark dots as black, text would become
    thinner than in the preview). Black ink lowers all channels, red ink only green and blue:
    black where red is dark enough; red where otherwise green is dark enough."""
    r, g, __ = image.convert("RGB").split()
    black = r.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
    red = g.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
    out = Image.new("RGB", image.size, "white")
    out.paste((255, 0, 0), (0, 0), red)
    out.paste((0, 0, 0), (0, 0), black)
    return out


def cut_interval(mode: str, count: int) -> int:
    """Cut every n labels: "each" → 1, "end" → all (with more than 255 labels
    additionally after every 255 – the printer cannot do more)."""
    if mode not in CUTS:
        raise ValueError(_("Unknown cut {mode!r} – allowed: {allowed}").format(
            mode=mode, allowed=", ".join(CUTS)))
    return 1 if mode == "each" else max(1, min(count, MAX_CUT_EVERY))


class _Raster(BrotherQLRaster):
    """brother_ql for series: selectable cut interval (otherwise fixed after each label), pages
    after the first marked as follow-up pages (ESC i z, n9) and data in a
    ``bytearray`` – ``bytes +=`` copied everything at every command (long series: minutes)."""

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
    """Raster data for one label or several in one job (series); ``cut``: cut at all
    (never without a cutter on the model), ``cut_every``: every n labels
    (``cut_interval``) and at the end. Red/black labels (62red) with a red layer."""
    images = [images] if isinstance(images, Image.Image) else list(images)
    if not images:
        raise ValueError(_("No labels to print"))
    if not isinstance(cut_every, int) or isinstance(cut_every, bool) or cut_every < 1:
        raise ValueError(_("Cut every n labels: n must be a whole number from 1, not {value!r}")
                         .format(value=cut_every))
    if label_id not in {label.id for label in labels_for_model(model)}:
        raise ValueError(_("Label {label!r} does not fit the {model} – see "
                           "'labelwerk -m {model} labels'").format(label=label_id, model=model))
    qlr = _Raster(model, cut_every)
    qlr.exception_on_warning = True
    red = get_label(label_id).two_color          # only two-colour models have 62red (checked above)
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
    """Print one label or several (series); status from brother_ql (of the last part).

    A series goes out in part jobs (``MAX_JOB_EACH`` or ``cut_every`` labels), each one
    is checked; an error aborts and – if parts were already printed – names the affected
    labels. ``cancelled()`` is asked before each part (True → ``PrintCancelled``; a
    part already sent runs to the end), ``progress(printed, all)`` after each. ``backend``: None =
    from the URI (``tcp://`` → network: one job – the printer reports no status there).
    ``cups:NAME``: one job to the CUPS queue (``options``: driver options, e.g.
    cut); status ``{"outcome": "sent", "job": id}``. ``zpl+file://…``/``zpl+tcp://…``:
    Zebra, one data stream (``options["mode"]``: "" as set at the printer, T/C/P); status
    ``{"outcome": "sent"}``."""
    backend = backend or backend_for(printer)
    images = [image] if isinstance(image, Image.Image) else list(image)
    if label_id not in {label.id for label in labels_for_model(model)}:
        raise PrintError(_("Label {label!r} does not fit the printer ({model}).").format(
            label=label_id, model=model))
    if not route_fits(backend, model):
        raise PrintError(_("Model {model} does not fit the printer {printer} – give cups:NAME for "
                           "CUPS, zpl:203/300/600 for Zebra, otherwise a Brother QL.").format(
            model=model, printer=printer))
    if backend == "cups":
        return _print_cups(printer[len("cups:"):], images, label_id, options, cancelled)
    if backend == "zpl":
        return _print_zpl(printer, images, options, cancelled)
    if backend == "network":
        _reachable(printer)
    part = MAX_JOB_EACH if cut_every == 1 else min(cut_every, MAX_CUT_EVERY)
    if backend == "network" and cut_every == 1:
        # over the network the printer reports no status: parts could be neither checked nor cancelled
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
            if start == 0:                  # nothing printed yet: message as for a single label
                raise
            # the printer reports with a delay – the error may also belong to labels before it
            raise PrintError(_("Error at label {first}–{last} of {total} (check the ones before "
                               "too): {error}").format(first=start + 1, last=start + len(chunk),
                                                       total=len(images), error=e)) from None
        if progress is not None:
            progress(start + len(chunk), len(images))
    return status


def _print_cups(name: str, images: list[Image.Image], label_id: str,
                options: dict[str, str] | None, cancelled: Callable[[], bool] | None) -> dict:
    """Hand over to CUPS – one job; the queue prints afterwards (cancelling happens there)."""
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
    """Zebra: all labels as one ZPL data stream (the printer reports no status)."""
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
    except OSError as e:                  # pyusb: USBError is an OSError
        if backend != "network":
            raise _usb_error(e, printer) from None
        raise PrintError(_(_UNREACHABLE).format(printer=printer, reason=e.strerror or e)) \
            from None
    except ValueError as e:
        if str(e) != "Device not found":  # pyusb
            raise
        raise PrintError(_("Printer not found: {printer}\n"
                           "Check: switched on, Editor Lite LED off, 'lsusb'.").format(
            printer=printer)) from None

    errors = (status.get("printer_state") or {}).get("errors") or []
    if errors:
        raise PrintError("\n".join(
            _(_PRINTER_ERRORS.get(err, _PRINTER_ERROR)).format(label=label_id, err=err)
            for err in errors))
    return status


def _usb_error(e: OSError, printer: str) -> PrintError:
    """Understandable message for a missing, locked or busy USB device."""
    if isinstance(e, PermissionError):
        return PrintError(_("No permission for {device} – is the user in group 'lp'?")
                          .format(device=printer))
    if isinstance(e, FileNotFoundError):
        return PrintError(_("Printer not found: {printer}\n"
                            "Check: switched on, Editor Lite LED off, 'lsusb', "
                            "'lsmod | grep usblp'.").format(printer=printer))
    return PrintError(_("Printer {printer} not ready ({reason}) – in use or busy? Wait a moment "
                        "or switch it off and on.").format(printer=printer,
                                                           reason=e.strerror or e))


def _reachable(printer: str) -> None:
    """Contact the network printer beforehand with a timeout – brother_ql otherwise waits without limit
    (with a wrong address about two minutes)."""
    host, __, port = printer[len("tcp://"):].partition(":")
    try:
        socket.create_connection((host, int(port or 9100)), timeout=CONNECT_TIMEOUT_S).close()
    except (OSError, ValueError) as e:
        reason = _("no answer") if isinstance(e, TimeoutError) \
            else getattr(e, "strerror", None) or e
        raise PrintError(_(_UNREACHABLE).format(printer=printer, reason=reason)) from None
