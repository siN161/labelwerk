"""Bilder für das Werkzeug „Bild“ beschaffen: Datei, Zwischenablage, Ablegen.

SVG rastert Qt (``QSvgRenderer``) – so bleibt der Kern Qt-frei; alle anderen Dateien lädt
``files.load_image``. Bilder aus der Zwischenablage oder abgelegte Bilddaten haben keine
verlässliche Auflösung und gelten als 300 dpi.
"""
from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .. import clipart, files
from ..clipart import Symbol
from ..i18n import N_, _
from ..imaging import MAX_DPI, MAX_PIXELS, on_white
from ..labels import DPI

SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".pdf")
ALLOWED = "PNG, JPG, GIF, BMP, WebP, SVG, PDF"  # für Meldungen
_PATTERNS = " ".join(f"*{s} *{s.upper()}" for s in SUFFIXES)   # Großschreibung: Kameras, Windows
# Quelle eines eingefügten Bilds: wird mit dem Etikett gespeichert und verglichen – deshalb fest
# (deutsch, wie in älteren Dateien) und nur beim Anzeigen übersetzt (``source_title``)
CLIPBOARD = "Zwischenablage"
DROPPED = "Abgelegtes Bild"
SCREENSHOT = "Bildschirmfoto"
MIME_OBJECTS = "application/x-labelwerk-objects"   # kopierte Objekte (Kennung der Kopie)
SYMBOL_SOURCE = "Symbol: {name}"                    # Quelle eines eingefügten Symbols
_SOURCE_TITLES = {CLIPBOARD: N_("Clipboard"), DROPPED: N_("Dropped image"),
                  SCREENSHOT: N_("Screenshot")}
MIME_SYMBOL = "application/x-labelwerk-symbol"     # Symbol aus dem Fenster gezogen (id)
SYMBOL_PROBE_PX = 512          # Symbol: erst grob rastern, um den Inhalt zu finden
SVG_DPI = 96                                    # SVG: 1 px = 1/96 in


def file_filter() -> str:
    """Filter des Dateidialogs „Bild einfügen“ in der eingestellten Sprache."""
    return _("Images and PDF ({patterns});;All files (*)").format(patterns=_PATTERNS)


def source_title(source: str) -> str:
    """Quelle eines Bilds zum Anzeigen: feste Quellen (Zwischenablage, Ablegen, Bildschirmfoto,
    Symbol) übersetzt, Dateinamen wie sie sind."""
    if source in _SOURCE_TITLES:
        return _(_SOURCE_TITLES[source])
    if is_symbol_source(source):
        return _("Symbol: {name}").format(name=source[len(SYMBOL_SOURCE.split("{")[0]):])
    return source


def page_count(path: Path) -> int:
    """Seitenzahl (PDF), sonst 1 – Fehler wie beim Laden (``ValueError``, ``FileNotFoundError``)."""
    return files.page_count(path) if Path(path).suffix.lower() == ".pdf" else 1


def load(path: Path, page: int = 1) -> tuple[Image.Image, float]:
    """Bild aus einer Datei: (RGB-Bild, dpi); SVG wird hier gerastert, der Rest im Kern.
    Andere Dateitypen: ``ValueError`` mit allen möglichen Typen (samt SVG)."""
    path = Path(path)
    if path.suffix.lower() not in SUFFIXES:
        raise ValueError(_("File type not supported: {type} – possible: {allowed}").format(
            type=path.suffix or path.name, allowed=ALLOWED))
    if path.suffix.lower() == ".svg":
        return load_svg(path)
    return files.load_image(path, page)


def load_screenshot(path: Path) -> tuple[Image.Image, float]:
    """Bildschirmfoto-Datei: (RGB-Bild, dpi) mit 1 Bildschirmpixel = 1 Druckpunkt (300 dpi) –
    eine Auflösungsangabe der Datei gilt nicht; ein riesiges Foto wird verkleinert
    (``imaging.limit_size``), die zurückgegebene Auflösung sinkt dann mit, damit die Größe stimmt."""
    return files.load_image(path, dpi=DPI)


def load_svg(path: Path) -> tuple[Image.Image, float]:
    """SVG bei 300 dpi auf Weiß rastern (Größe aus width/height samt Einheit, sonst Qts
    Größe/viewBox; 1 px = 1/96 in); sehr große Zeichnungen gröber, höchstens
    ``MAX_PIXELS`` auf der längsten Seite."""
    if not path.exists():
        raise FileNotFoundError(_("File not found: {path}").format(path=path))
    # mit Verweisen auf andere Dateien über den Pfad (sie liegen neben der SVG), sonst aus den
    # Bytes – derselbe Weg wie beim Rastern eines Vektorbilds (Vorschau = Raster)
    vector = load_vector(path)
    renderer = QSvgRenderer(str(path)) if vector is None else _svg_renderer(vector)
    size = renderer.defaultSize()
    if not renderer.isValid() or size.isEmpty():
        raise ValueError(_("Cannot read file: {name} (not a valid SVG)").format(name=path.name))
    # Qt rechnet mm/in/pt mit 90 dpi – Maße mit Einheit deshalb selbst lesen (CSS: 96 px/in)
    width, height = svg_size(path) or (size.width(), size.height())
    dpi = min(DPI, MAX_PIXELS * SVG_DPI / max(width, height))
    pixels = (max(1, round(width * dpi / SVG_DPI)), max(1, round(height * dpi / SVG_DPI)))
    return _render(renderer, pixels, (0, 0, *pixels)), dpi


# Verweis auf eine andere Datei: href, das weder auf eine Stelle im Dokument (#…) noch auf
# eingebettete Daten (data:) zeigt
_EXTERNAL = re.compile(rb"""href\s*=\s*["'](?!\s*(?:#|data:))""")


def load_vector(path: Path) -> bytes | None:
    """SVG-Datei als Vektorbild: ihre Bytes – außer sie verweist auf andere Dateien (``<image>``,
    externes ``<use>``; die gelten nur neben der SVG): dann None, sie wird Pixelbild. Andere
    Dateitypen: None."""
    path = Path(path)
    if path.suffix.lower() != ".svg":
        return None
    data = path.read_bytes()
    return None if _EXTERNAL.search(data) else data


@lru_cache(maxsize=4)
def _svg_renderer(svg: bytes) -> QSvgRenderer:
    """Geparstes SVG (Größe ändern rastert neu, ohne neu zu parsen)."""
    return QSvgRenderer(QByteArray(svg))


def _render(renderer: QSvgRenderer, size: tuple[int, int],
            region: tuple[int, int, int, int]) -> Image.Image:
    """Ganzes Blatt auf ``size`` Pixel, davon ``region`` (x, y, w, h), RGB auf Weiß."""
    x, y, w, h = region
    image = QImage(w, h, QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.translate(-x, -y)
    renderer.render(painter, QRectF(0, 0, *size))
    painter.end()
    return Image.frombuffer("RGB", (w, h), image.constBits(), "raw", "RGB",
                            image.bytesPerLine(), 1).copy()     # eine Kopie: Qt gibt frei


def is_symbol_source(source: str) -> bool:
    """Stammt das Bild aus der Symbol-Bibliothek (Quelle ``SYMBOL_SOURCE``)?"""
    return source.startswith(SYMBOL_SOURCE.split("{")[0])


def rasterize_svg(svg: bytes, size: tuple[int, int],
                  region: tuple[int, int, int, int]) -> Image.Image:
    """Raster-Funktion für Vektorbilder (``render.set_svg_rasterizer``): das ganze Blatt auf
    ``size`` Pixel, davon nur ``region`` (x, y, w, h) – RGB auf Weiß. Kaputtes SVG:
    ``ValueError``; ebenso ein SVG mit Verweisen auf andere Dateien (die gelten nur neben der
    SVG, nicht in einem gespeicherten Dokument)."""
    if _EXTERNAL.search(svg):
        raise ValueError(_("Vector image refers to other files – they are not saved with it."))
    renderer = _svg_renderer(svg)
    if not renderer.isValid():
        raise ValueError(_("Cannot read vector image (not a valid SVG)."))
    return _render(renderer, size, region)


def load_symbol(symbol: Symbol, side_mm: float) -> tuple[Image.Image, float, tuple | None,
                                                         bytes | None]:
    """Symbol als Bild-Objekt-Zutaten: (Vorschau RGB, dpi, Ausschnitt, SVG-Bytes oder None).

    Zugeschnitten auf die Tinte (nicht die Schnittmarken-Erkennung: umrandete Zeichen blieben
    sonst nicht ganz); die längere Seite des Inhalts misst ``side_mm`` (Größe 1:1). Ganz weiß:
    Ausschnitt None (ganzes Bild). Vektoren werden so gerastert, dass der Inhalt ``MAX_DPI`` hat
    – die Vorschau aber höchstens ``MAX_PIXELS`` groß (winziger Inhalt auf großer Seite). Eigene
    SVGs mit Verweisen auf andere Dateien werden Pixelbilder (wie ``load_vector``).
    Unlesbar: ``ValueError``/``OSError``."""
    data = clipart.data(symbol)
    if clipart.is_vector(symbol):
        linked = _EXTERNAL.search(data) is not None
        renderer = QSvgRenderer(symbol.file) if linked else _svg_renderer(data)
        size = renderer.defaultSize()
        if not renderer.isValid() or size.isEmpty():
            raise ValueError(_("Cannot read symbol {name} (not a valid SVG).").format(name=symbol.name))
        k = SYMBOL_PROBE_PX / max(size.width(), size.height())
        probe = (max(1, round(size.width() * k)), max(1, round(size.height() * k)))
        if box := files.ink_box(_render(renderer, probe, (0, 0, *probe))):
            k *= side_mm / 25.4 * MAX_DPI / max(box[2] - box[0], box[3] - box[1])
        k = min(k, MAX_PIXELS / max(size.width(), size.height()))
        sheet = (max(1, round(size.width() * k)), max(1, round(size.height() * k)))
        image, svg = _render(renderer, sheet, (0, 0, *sheet)), None if linked else data
    else:
        with Image.open(io.BytesIO(data), formats=["PNG"]) as img:     # nur PNG (kein EPS)
            image, svg = on_white(img), None
    crop = files.ink_box(image)
    l, t, r, b = crop or (0, 0, *image.size)
    return image, max(r - l, b - t) * 25.4 / side_mm, crop, svg


_UNITS = {"": 1.0, "px": 1.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "pt": 96 / 72,
          "pc": 16.0}                           # CSS-Pixel je Einheit (96 px = 1 in)
_LENGTH = re.compile(r"\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z]*)\s*$")


def svg_size(path: Path) -> tuple[float, float] | None:
    """Breite und Höhe der Zeichnung in CSS-Pixeln (1/96 in) aus ``width``/``height`` des
    Wurzelelements, mit Einheiten px/mm/cm/in/pt/pc; None, wenn eine Angabe fehlt, relativ
    ist (%, em) oder die Datei sich nicht lesen lässt – dann zählt Qts Größe (viewBox)."""
    try:
        __, root = next(ElementTree.iterparse(path, events=("start",)))
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
    with Image.open(io.BytesIO(bytes(buffer.data())), formats=["PNG"]) as img:
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
