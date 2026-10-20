"""Tool registry: the toolbar and the panel stack are generated from it.

A new tool is a new entry in TOOLS.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..document import Document
from ..i18n import N_
from .panels import Panel
from .panels.barcode import BarcodePanel
from .panels.file import FilePanel
from .panels.image import ImagePanel
from .panels.layout import LayoutPanel
from .panels.paper import PaperPanel
from .panels.parcel import ParcelPanel
from .panels.series import SeriesPanel
from .panels.text import TextPanel


@dataclass(frozen=True)
class Tool:
    key: str
    title: str                                 # English (N_), _(title) is displayed
    icon: str                                  # name in the freedesktop icon theme
    panel: Callable[[Document], Panel]
    tip: str = ""                              # tooltip (otherwise the title), English (N_)


START_TOOL = "paper"                           # tab at startup


TOOLS = [
    Tool("file", N_("File"), "document-open", FilePanel, N_("File and favorites")),
    Tool("paper", N_("Paper"), "document-page-setup", PaperPanel),
    Tool("text", N_("Text"), "insert-text", TextPanel),
    Tool("image", N_("Image"), "insert-image", ImagePanel),
    Tool("barcode", N_("Barcode"), "view-barcode-qr", BarcodePanel, N_("Barcodes and QR codes")),
    Tool("layout", N_("Layout"), "align-horizontal-left", LayoutPanel),
    Tool("series", N_("Series"), "view-list-text", SeriesPanel,
         N_("Series from a table or numbering")),
    Tool("parcel", N_("Parcel"), "mail-send", ParcelPanel,
         N_("Convert a parcel label (DHL, Hermes …) for the label printer")),
]
