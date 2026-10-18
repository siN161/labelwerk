"""Bilder für das Werkzeug „Bild“ beschaffen: Datei, Zwischenablage, Ablegen.

SVG rastert Qt (``QSvgRenderer``) – so bleibt der Kern Qt-frei; alle anderen Dateien lädt
``files.load_image``. Bilder aus der Zwischenablage oder abgelegte Bilddaten haben keine
verlässliche Auflösung und gelten als 300 dpi.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, QMimeData, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .. import files
from ..imaging import MAX_PIXELS, on_white
from ..labels import DPI

SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".pdf")
ALLOWED = "PNG, JPG, GIF, BMP, WebP, SVG, PDF"  # für Meldungen
FILE_FILTER = ("Bilder und PDF (" + " ".join(f"*{s} *{s.upper()}" for s in SUFFIXES) + ");;"
               "Alle Dateien (*)")              # Großschreibung: Kameras, Windows
CLIPBOARD = "Zwischenablage"                    # Quelle eines eingefügten Bilds
DROPPED = "Abgelegtes Bild"
SCREENSHOT = "Bildschirmfoto"
MIME_OBJECTS = "application/x-labelwerk-objects"   # kopierte Objekte (Kennung der Kopie)
SVG_DPI = 96                                    # SVG: 1 px = 1/96 in


def page_count(path: Path) -> int:
    """Seitenzahl (PDF), sonst 1 – Fehler wie beim Laden (``ValueError``, ``FileNotFoundError``)."""
    return files.page_count(path) if Path(path).suffix.lower() == ".pdf" else 1


def load(path: Path, page: int = 1) -> tuple[Image.Image, float]:
    """Bild aus einer Datei: (RGB-Bild, dpi); SVG wird hier gerastert, der Rest im Kern.
    Andere Dateitypen: ``ValueError`` mit allen möglichen Typen (samt SVG)."""
    path = Path(path)
    if path.suffix.lower() not in SUFFIXES:
        raise ValueError(f"Dateityp nicht unterstützt: {path.suffix or path.name} – "
                         f"möglich: {ALLOWED}")
    if path.suffix.lower() == ".svg":
        return load_svg(path)
    return files.load_image(path, page)


def load_screenshot(path: Path) -> tuple[Image.Image, float]:
    """Bildschirmfoto-Datei: (RGB-Bild, dpi) mit 1 Bildschirmpixel = 1 Druckpunkt (300 dpi) –
    eine Auflösungsangabe der Datei gilt nicht; hat das Laden ein riesiges Foto verkleinert
    (``imaging.limit_size``), entsprechend weniger, damit die Größe stimmt."""
    image, _ = load(path)
    with Image.open(path) as raw:
        scale = max(image.size) / max(raw.size)
    return image, DPI * scale


def load_svg(path: Path) -> tuple[Image.Image, float]:
    """SVG bei 300 dpi auf Weiß rastern (Größe aus width/height samt Einheit, sonst Qts
    Größe/viewBox; 1 px = 1/96 in); sehr große Zeichnungen gröber, höchstens
    ``MAX_PIXELS`` auf der längsten Seite."""
    if not path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
    renderer = QSvgRenderer(str(path))
    size = renderer.defaultSize()
    if not renderer.isValid() or size.isEmpty():
        raise ValueError(f"Datei kann nicht gelesen werden: {path.name} (kein gültiges SVG)")
    # Qt rechnet mm/in/pt mit 90 dpi – Maße mit Einheit deshalb selbst lesen (CSS: 96 px/in)
    width, height = svg_size(path) or (size.width(), size.height())
    dpi = min(DPI, MAX_PIXELS * SVG_DPI / max(width, height))
    image = QImage(max(1, round(width * dpi / SVG_DPI)),
                   max(1, round(height * dpi / SVG_DPI)), QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return to_pil(image), dpi


_UNITS = {"": 1.0, "px": 1.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "pt": 96 / 72,
          "pc": 16.0}                           # CSS-Pixel je Einheit (96 px = 1 in)
_LENGTH = re.compile(r"\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z]*)\s*$")


def svg_size(path: Path) -> tuple[float, float] | None:
    """Breite und Höhe der Zeichnung in CSS-Pixeln (1/96 in) aus ``width``/``height`` des
    Wurzelelements, mit Einheiten px/mm/cm/in/pt/pc; None, wenn eine Angabe fehlt, relativ
    ist (%, em) oder die Datei sich nicht lesen lässt – dann zählt Qts Größe (viewBox)."""
    try:
        _, root = next(ElementTree.iterparse(path, events=("start",)))
    except (ElementTree.ParseError, OSError, StopIteration):
        return None
    sizes = []
    for name in ("width", "height"):
        match = _LENGTH.match(root.get(name, ""))
        if match is None or match[2].lower() not in _UNITS or float(match[1]) <= 0:
            return None
        sizes.append(float(match[1]) * _UNITS[match[2].lower()])
    return sizes[0], sizes[1]


def to_pil(image: QImage) -> Image.Image:
    """QImage → RGB-Bild (Transparenz wird weiß)."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    with Image.open(io.BytesIO(bytes(buffer.data()))) as img:
        return on_white(img)


def mime_image(mime: QMimeData | None) -> Image.Image | None:
    """Bilddaten aus der Zwischenablage bzw. einem Ablegen, sonst None."""
    if mime is None or not mime.hasImage():
        return None
    data = mime.imageData()
    if isinstance(data, QPixmap):
        data = data.toImage()
    if not isinstance(data, QImage) or data.isNull():
        return None
    return to_pil(data)


def mime_files(mime: QMimeData | None) -> list[Path]:
    """Lokale Dateien aus einem Ablegen (Dateimanager)."""
    if mime is None or not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


def mime_text(mime: QMimeData | None) -> str:
    """Text aus der Zwischenablage, wie ein Textrahmen ihn bekommt: Zeilenenden als „\\n“,
    Tabulatoren als Leerzeichen, ohne Leerzeilen am Ende; leer ohne Text."""
    if mime is None or not mime.hasText():
        return ""
    text = mime.text().replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    return text.rstrip("\n") if text.strip() else ""
