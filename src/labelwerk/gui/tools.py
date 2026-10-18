"""Werkzeug-Registry: Werkzeugleiste und Panel-Stapel werden daraus erzeugt.

Ein neues Werkzeug (Rahmen, Barcode …) ist ein neuer Eintrag in TOOLS.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..document import Document
from .panels import Panel
from .panels.file import FilePanel
from .panels.image import ImagePanel
from .panels.layout import LayoutPanel
from .panels.paper import PaperPanel
from .panels.text import TextPanel


@dataclass(frozen=True)
class Tool:
    key: str
    title: str
    icon: str                                  # Name im Freedesktop-Icon-Theme
    panel: Callable[[Document], Panel]
    tip: str = ""                              # Tooltip (sonst der Titel)


START_TOOL = "paper"                           # Reiter beim Start

TOOLS = [
    Tool("file", "Datei", "document-open", FilePanel, "Datei und Favoriten"),
    Tool("paper", "Papier", "document-page-setup", PaperPanel),
    Tool("text", "Text", "insert-text", TextPanel),
    Tool("image", "Bild", "insert-image", ImagePanel),
    Tool("layout", "Layout", "align-horizontal-left", LayoutPanel),
]
