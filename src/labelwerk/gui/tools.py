"""Werkzeug-Registry: Werkzeugleiste und Panel-Stapel werden daraus erzeugt.

Ein neues Werkzeug ist ein neuer Eintrag in TOOLS.
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
    title: str                                 # englisch (N_), angezeigt wird _(title)
    icon: str                                  # Name im Freedesktop-Icon-Theme
    panel: Callable[[Document], Panel]
    tip: str = ""                              # Tooltip (sonst der Titel), englisch (N_)


START_TOOL = "paper"                           # Reiter beim Start

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
