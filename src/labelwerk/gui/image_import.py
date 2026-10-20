"""Obtain images for the IMAGE tool: file, clipboard, drop.

Qt rasterises SVG (``QSvgRenderer``) – so the core stays Qt-free; all other files are loaded by
``files.load_image``. Images from the clipboard or dropped image data have no reliable
resolution and count as 300 dpi.
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
ALLOWED = "PNG, JPG, GIF, BMP, WebP, SVG, PDF"  # for messages
_PATTERNS = " ".join(f"*{s} *{s.upper()}" for s in SUFFIXES)   # upper case: cameras, Windows
# Source of an inserted image: saved with the label and compared – hence fixed
# (German, as in older files) and translated only for display (``source_title``)
CLIPBOARD = "Zwischenablage"
DROPPED = "Abgelegtes Bild"
SCREENSHOT = "Bildschirmfoto"
MIME_OBJECTS = "application/x-labelwerk-objects"   # copied objects (identifier of the copy)
SYMBOL_SOURCE = "Symbol: {name}"                    # source of an inserted symbol
_SOURCE_TITLES = {CLIPBOARD: N_("Clipboard"), DROPPED: N_("Dropped image"),
                  SCREENSHOT: N_("Screenshot")}
MIME_SYMBOL = "application/x-labelwerk-symbol"     # symbol dragged from the window (id)
SYMBOL_PROBE_PX = 512          # symbol: first rasterise coarsely to find the content
SVG_DPI = 96                                    # SVG: 1 px = 1/96 in


def file_filter() -> str:
    """Filter of the “Insert image” file dialog in the configured language."""
    return _("Images and PDF ({patterns});;All files (*)").format(patterns=_PATTERNS)


def source_title(source: str) -> str:
    """Source of an image for display: fixed sources (clipboard, drop, screenshot,
    symbol) translated, file names as they are."""
    if source in _SOURCE_TITLES:
        return _(_SOURCE_TITLES[source])
    if is_symbol_source(source):
        return _("Symbol: {name}").format(name=source[len(SYMBOL_SOURCE.split("{")[0]):])
    return source


def page_count(path: Path) -> int:
    """Page count (PDF), otherwise 1 – errors as when loading (``ValueError``, ``FileNotFoundError``)."""
    return files.page_count(path) if Path(path).suffix.lower() == ".pdf" else 1


def load(path: Path, page: int = 1) -> tuple[Image.Image, float]:
    """Image from a file: (RGB image, dpi); SVG is rasterised here, the rest in the core.
    Other file types: ``ValueError`` listing all possible types (including SVG)."""
    path = Path(path)
    if path.suffix.lower() not in SUFFIXES:
        raise ValueError(_("File type not supported: {type} – possible: {allowed}").format(
            type=path.suffix or path.name, allowed=ALLOWED))
    if path.suffix.lower() == ".svg":
        return load_svg(path)
    return files.load_image(path, page)


def load_screenshot(path: Path) -> tuple[Image.Image, float]:
    """Screenshot file: (RGB image, dpi) with 1 screen pixel = 1 dot (300 dpi) –
    a resolution given by the file does not apply; a huge photo is scaled down
    (``imaging.limit_size``), and the returned resolution drops with it so the size stays right."""
    return files.load_image(path, dpi=DPI)


def load_svg(path: Path) -> tuple[Image.Image, float]:
    """Rasterise SVG at 300 dpi on white (size from width/height including unit, otherwise Qt's
    size/viewBox; 1 px = 1/96 in); very large drawings more coarsely, at most
    ``MAX_PIXELS`` on the longest side."""
    if not path.exists():
        raise FileNotFoundError(_("File not found: {path}").format(path=path))
    # with references to other files via the path (they lie next to the SVG), otherwise from the
    # bytes – the same way as when rasterising a vector image (preview = raster)
    vector = load_vector(path)
    renderer = QSvgRenderer(str(path)) if vector is None else _svg_renderer(vector)
    size = renderer.defaultSize()
    if not renderer.isValid() or size.isEmpty():
        raise ValueError(_("Cannot read file: {name} (not a valid SVG)").format(name=path.name))
    # Qt computes mm/in/pt at 90 dpi – so read dimensions with a unit ourselves (CSS: 96 px/in)
    width, height = svg_size(path) or (size.width(), size.height())
    dpi = min(DPI, MAX_PIXELS * SVG_DPI / max(width, height))
    pixels = (max(1, round(width * dpi / SVG_DPI)), max(1, round(height * dpi / SVG_DPI)))
    return _render(renderer, pixels, (0, 0, *pixels)), dpi


# Reference to another file: href that points neither to a place in the document (#…) nor to
# embedded data (data:)
_EXTERNAL = re.compile(rb"""href\s*=\s*["'](?!\s*(?:#|data:))""")


def load_vector(path: Path) -> bytes | None:
    """SVG file as a vector image: its bytes – unless it refers to other files (``<image>``,
    external ``<use>``; those only apply next to the SVG): then None, it becomes a pixel image.
    Other file types: None."""
    path = Path(path)
    if path.suffix.lower() != ".svg":
        return None
    data = path.read_bytes()
    return None if _EXTERNAL.search(data) else data


@lru_cache(maxsize=4)
def _svg_renderer(svg: bytes) -> QSvgRenderer:
    """Parsed SVG (resizing re-rasterises without re-parsing)."""
    return QSvgRenderer(QByteArray(svg))


def _render(renderer: QSvgRenderer, size: tuple[int, int],
            region: tuple[int, int, int, int]) -> Image.Image:
    """Whole sheet at ``size`` pixels, of which ``region`` (x, y, w, h), RGB on white."""
    x, y, w, h = region
    image = QImage(w, h, QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.translate(-x, -y)
    renderer.render(painter, QRectF(0, 0, *size))
    painter.end()
    return Image.frombuffer("RGB", (w, h), image.constBits(), "raw", "RGB",
                            image.bytesPerLine(), 1).copy()     # one copy: Qt frees the original


def is_symbol_source(source: str) -> bool:
    """Does the image come from the symbol library (source ``SYMBOL_SOURCE``)?"""
    return source.startswith(SYMBOL_SOURCE.split("{")[0])


def rasterize_svg(svg: bytes, size: tuple[int, int],
                  region: tuple[int, int, int, int]) -> Image.Image:
    """Rasteriser for vector images (``render.set_svg_rasterizer``): the whole sheet at
    ``size`` pixels, of which only ``region`` (x, y, w, h) – RGB on white. Broken SVG:
    ``ValueError``; likewise an SVG with references to other files (those only apply next to
    the SVG, not in a saved document)."""
    if _EXTERNAL.search(svg):
        raise ValueError(_("Vector image refers to other files – they are not saved with it."))
    renderer = _svg_renderer(svg)
    if not renderer.isValid():
        raise ValueError(_("Cannot read vector image (not a valid SVG)."))
    return _render(renderer, size, region)


def load_symbol(symbol: Symbol, side_mm: float) -> tuple[Image.Image, float, tuple | None,
                                                         bytes | None]:
    """Symbol as ingredients of an image object: (preview RGB, dpi, region, SVG bytes or None).

    Cropped to the ink (not the crop-mark detection: outlined characters would otherwise not
    stay whole); the longer side of the content measures ``side_mm`` (size 1:1). Entirely white:
    region None (whole image). Vectors are rasterised so that the content has ``MAX_DPI``
    – but the preview at most ``MAX_PIXELS`` large (tiny content on a large page). Own
    SVGs with references to other files become pixel images (like ``load_vector``).
    Unreadable: ``ValueError``/``OSError``."""
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
        with Image.open(io.BytesIO(data), formats=["PNG"]) as img:     # PNG only (no EPS)
            image, svg = on_white(img), None
    crop = files.ink_box(image)
    l, t, r, b = crop or (0, 0, *image.size)
    return image, max(r - l, b - t) * 25.4 / side_mm, crop, svg


_UNITS = {"": 1.0, "px": 1.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "pt": 96 / 72,
          "pc": 16.0}                           # CSS pixels per unit (96 px = 1 in)
_LENGTH = re.compile(r"\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z]*)\s*$")


def svg_size(path: Path) -> tuple[float, float] | None:
    """Width and height of the drawing in CSS pixels (1/96 in) from ``width``/``height`` of the
    root element, with units px/mm/cm/in/pt/pc; None if a value is missing, is relative
    (%, em) or the file cannot be read – then Qt's size (viewBox) applies."""
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
    """QImage → RGB image (transparency becomes white)."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    with Image.open(io.BytesIO(bytes(buffer.data())), formats=["PNG"]) as img:
        return on_white(img)


def mime_image(mime: QMimeData | None) -> Image.Image | None:
    """Image data from the clipboard or a drop, otherwise None."""
    if mime is None or not mime.hasImage():
        return None
    data = mime.imageData()
    if isinstance(data, QPixmap):
        data = data.toImage()
    if not isinstance(data, QImage) or data.isNull():
        return None
    return to_pil(data)


def mime_files(mime: QMimeData | None) -> list[Path]:
    """Local files from a drop (file manager)."""
    if mime is None or not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


def mime_text(mime: QMimeData | None) -> str:
    """Text from the clipboard as a text frame receives it: line endings as “\\n”,
    tabs as spaces, no blank lines at the end; empty without text."""
    if mime is None or not mime.hasText():
        return ""
    text = mime.text().replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    return text.rstrip("\n") if text.strip() else ""
