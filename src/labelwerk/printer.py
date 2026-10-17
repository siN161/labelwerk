"""Erzeugt Brother-Rasterdaten und sendet sie an den Drucker."""
from __future__ import annotations

from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from brother_ql.raster import BrotherQLRaster
from PIL import Image

DEFAULT_MODEL = "QL-600"
DEFAULT_BACKEND = "linux_kernel"
DEFAULT_PRINTER = "file:///dev/usb/lp0"


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
    return send(instructions=data, printer_identifier=printer,
                backend_identifier=backend, blocking=True)
