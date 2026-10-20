"""Label document: label and list of objects (UI-independent, JSON-friendly)."""
from __future__ import annotations

import io
from dataclasses import dataclass, field, replace

from PIL import Image

from .imaging import MAX_DPI, limit_size, on_white

ORIENTATIONS = ("vertical", "horizontal")
ALIGNMENTS = ("left", "center", "right", "justify")
ROTATIONS = (0, 90, 180, 270)      # degrees clockwise
COLORS = ("black", "red")          # colour per object; red only on red/black labels (62red)
MAX_MARGIN_MM = 20.0
MAX_POSITION_MM = 999.9            # position of an object (GUI position fields, also beside the label)
MIN_PT, MAX_PT = 4.0, 100.0
# Decorative frame: single, double, thick-thin, dashed, dotted, corners only
FRAME_STYLES = ("single", "double", "thick_thin", "dashed", "dotted", "corners")
FRAME_LINE_MM = (0.1, 3.0)          # line width
MAX_FRAME_MM = 10.0                 # distance to the margin, inner padding
# Series: cut after every label or only at the end; limits of the numbering
CUTS = ("each", "end")
MAX_SERIES_ROWS = 10_000
MAX_NUMBER = 10**9
MAX_DIGITS = 10
# Barcodes: kinds, QR error correction, module width in dots, height, content
BARCODE_KINDS = ("qr", "code128", "code39", "ean13", "ean8")
QR_LEVELS = ("L", "M", "Q", "H")
MAX_MODULE = 20                     # at 300 dpi; other resolutions accordingly (barcodes.max_module)
MODULE_LIMIT = 40                   # valid module width at all (600 dpi)
BARCODE_MM = (2.0, 100.0)           # height of the barcodes including the human-readable text
MAX_BARCODE_DATA = 2000


@dataclass
class Span:
    """Equally formatted piece of text."""
    text: str
    family: str | None = None       # None = default font (DejaVu Sans)
    size_pt: float | None = None    # None = base size of the text object
    bold: bool = True               # today's look stays the default
    italic: bool = False
    underline: bool = False


@dataclass
class Paragraph:
    """A line (paragraph) made of text pieces."""
    spans: list[Span] = field(default_factory=list)
    align: str = "center"           # left | center | right | justify

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


@dataclass
class TextObject:
    """Formatted text. ``TextObject("Zeile 1\\nZeile 2")`` creates plain text."""
    paragraphs: list[Paragraph] | str = field(default_factory=list)
    size_pt: float | None = None    # base size; None = automatic
    font_path: str | None = None    # fixed TTF file for pieces without a family (CLI --font)
    fit: bool = False               # “Fixed frame size”: base size + ratios, scaled together
    # Frame in mm in reading direction, origin = top left corner of the label
    x_mm: float | None = None       # top left corner; both None = centred on the label,
    y_mm: float | None = None       # only one set: the other counts as 0
    w_mm: float | None = None       # frame size only with fit; None = printable area
                                    # (continuous tape, automatic length: lengthwise = text length)
    h_mm: float | None = None
    rotation: int = 0               # 0 | 90 | 180 | 270
    color: str = "black"            # COLORS

    @property
    def positioned(self) -> bool:
        """Freely placed as soon as ``x_mm`` or ``y_mm`` is set (otherwise centred as before)."""
        return self.x_mm is not None or self.y_mm is not None

    @property
    def auto(self) -> bool:
        """Size is adjusted automatically (no fixed base size or fixed frame size)."""
        return self.size_pt is None or self.fit

    def __post_init__(self) -> None:
        if isinstance(self.paragraphs, str):
            self.paragraphs = [Paragraph([Span(line)]) for line in self.paragraphs.split("\n")]

    @classmethod
    def plain(cls, text: str, size_pt: float | None = None, align: str = "center",
              family: str | None = None, bold: bool = True, italic: bool = False,
              underline: bool = False, font_path: str | None = None) -> "TextObject":
        """Plain text with uniform formatting for all lines."""
        paragraphs = [Paragraph([Span(line, family, None, bold, italic, underline)], align)
                      for line in text.split("\n")]
        return cls(paragraphs, size_pt=size_pt, font_path=font_path)

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)

    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass(kw_only=True)
class ImageObject:
    """Image on the label; black/white only when rendering (``imaging.to_layers``).

    Usually created with ``ImageObject.from_image``. The frame is always set – as with
    text with a fixed frame size: ``x_mm``/``y_mm`` top left corner on the label (after
    rotating), ``w_mm``/``h_mm`` size before rotating.
    """
    png: bytes = field(repr=False)  # original in colour (on white), lossless as PNG
    source: str = ""                # file name or “Clipboard”
    page: int | None = None         # PDF page
    crop: tuple[int, int, int, int] | None = None   # crop (l, t, r, b) in pixels; None = whole
    x_mm: float = 0.0
    y_mm: float = 0.0
    w_mm: float
    h_mm: float
    rotation: int = 0               # 0 | 90 | 180 | 270
    mode: str = "line"              # line (hard threshold) | photo (dithered)
    threshold: int = 128            # 0–255; higher = more ink
    invert: bool = False
    keep_ratio: bool = True         # keep aspect ratio (corners/edges scale equally)
    dpi: float = 300.0              # resolution of ``png`` – gives the 1:1 size (``natural_mm``)
    svg: bytes | None = field(default=None, repr=False)   # vector image: rasterised at frame size
                                    # (``render.set_svg_rasterizer``); ``png`` is a preview
    color: str = "black"            # COLORS

    def __post_init__(self) -> None:
        if self.crop is not None:                # JSON delivers a list
            self.crop = tuple(int(v) for v in self.crop)

    @property
    def positioned(self) -> bool:
        """An image always has a position (unlike text, which can be centred)."""
        return True

    def is_empty(self) -> bool:
        return False

    @classmethod
    def from_image(cls, img: Image.Image, dpi: float, source: str, page: int | None = None,
                   crop: tuple[int, int, int, int] | None = None,
                   svg: bytes | None = None) -> "ImageObject":
        """Image 1:1 according to ``dpi`` (size of the section ``crop``, otherwise of the whole image).

        Transparency becomes white; very large images are limited (``imaging.limit_size``) –
        the section is scaled along, the print size stays (``dpi`` = resolution afterwards).
        With ``svg`` a vector image: ``img`` is its preview (the whole sheet rasterised).
        """
        l, t, r, b = crop if crop is not None else (0, 0, *img.size)
        mm = 25.4 / dpi                          # print size from the original
        rgb, stored_dpi = limit_size(on_white(img), dpi)
        if crop is not None and rgb.size != img.size:
            fx, fy = rgb.width / img.width, rgb.height / img.height
            crop = (round(l * fx), round(t * fy), round(r * fx), round(b * fy))
        return cls(png=_png(rgb), source=source, page=page, crop=crop,
                   w_mm=(r - l) * mm, h_mm=(b - t) * mm, dpi=stored_dpi, svg=svg)

    def limit_resolution(self) -> "ImageObject":
        """Copy with at most ``MAX_DPI`` relative to the current print size (``w_mm``/
        ``h_mm``) – e.g. after fitting a phone photo. 1:1 size (``natural_mm``) and
        section are scaled along; an image within limits comes back unchanged (the same object),
        a vector image always (its PNG is only a preview – scaled down the section would get coarser)."""
        if self.svg is not None:
            return self
        l, t, r, b = self.box()
        dpi = max((r - l) / self.w_mm, (b - t) / self.h_mm) * 25.4
        if dpi <= MAX_DPI:
            return self
        img = self.image()
        small, _ = limit_size(img, dpi)
        fx, fy = small.width / img.width, small.height / img.height
        crop = (None if self.crop is None
                else (round(l * fx), round(t * fy), round(r * fx), round(b * fy)))
        return replace(self, png=_png(small), crop=crop, dpi=self.dpi * fx)

    def box(self) -> tuple[int, int, int, int]:
        """Section (l, t, r, b) in pixels – without ``crop`` the whole image."""
        if self.crop is not None:
            return self.crop
        with Image.open(io.BytesIO(self.png), formats=["PNG"]) as img:   # only the header
            return (0, 0, *img.size)

    def natural_mm(self) -> tuple[float, float]:
        """1:1 size (width, height in mm, unrotated) of the section from ``dpi``."""
        l, t, r, b = self.box()
        return (r - l) * 25.4 / self.dpi, (b - t) * 25.4 / self.dpi

    def image(self) -> Image.Image:
        """The original as an RGB image."""
        with Image.open(io.BytesIO(self.png), formats=["PNG"]) as img:
            return img.convert("RGB")


@dataclass(kw_only=True)
class BarcodeObject:
    """Barcode or QR code. Drawn in whole dots (``barcodes.draw``): the width
    follows from the content (number of modules × ``module``), there is no ``w_mm``. QR codes are
    square (``h_mm`` and ``text`` apply only to barcodes)."""
    kind: str = "qr"                # BARCODE_KINDS
    data: str = ""                  # content; placeholder {column} is filled by the series
    x_mm: float = 0.0               # top left corner on the label (after rotating)
    y_mm: float = 0.0
    module: int = 3                 # dots per module (narrowest bar, QR square)
    h_mm: float = 10.0              # height including human-readable text, unrotated (barcodes only)
    rotation: int = 0               # 0 | 90 | 180 | 270
    text: bool = True               # human-readable text below the barcode
    error: str = "M"                # QR error correction QR_LEVELS
    color: str = "black"            # COLORS

    @property
    def positioned(self) -> bool:
        """A barcode always has a position (like an image)."""
        return True

    def is_empty(self) -> bool:
        """Never empty: without content rendering reports an error (no invisible frame)."""
        return False


def _png(img: Image.Image) -> bytes:
    """Image as PNG bytes (lossless)."""
    buffer = io.BytesIO()
    img.save(buffer, "PNG", compress_level=1)    # large photos about 4× faster
    return buffer.getvalue()


@dataclass(frozen=True)
class Frame:
    """Decorative frame around the label (like the P-touch “Frame”) in the printable area."""
    style: str = "single"           # FRAME_STYLES
    rounded: bool = False           # rounded corners (not on round labels)
    line_mm: float = 0.5            # line width
    inset_mm: float = 0.0           # distance from the printable margin
    padding_mm: float = 1.0         # distance to the content (automatically placed text, length)


@dataclass(frozen=True)
class Numbering:
    """Numbering without a file: ``start + i·step`` for i < ``count``, padded with zeros to
    ``digits`` places (column “Number”)."""
    start: int = 1
    step: int = 1
    count: int = 10
    digits: int = 0


@dataclass(frozen=True)
class Series:
    """Series: placeholders ``{column}`` in the text are filled per row of a table (``source``, CSV
    or Excel, ``sheet`` = sheet; None = first) or of a numbering."""
    source: str | None = None
    sheet: str | None = None
    numbering: Numbering | None = None
    cut: str = "each"               # CUTS: after every label | only at the end


@dataclass
class Document:
    label_id: str = "62"
    length_mm: float | None = None    # continuous tape only; None = automatic
    orientation: str = "vertical"     # "vertical" (text across the tape) | "horizontal" (along it)
    margin_mm: float = 1.0            # margin all around from the paper edge (the unprintable strip counts)
    objects: list[TextObject | ImageObject | BarcodeObject] = field(default_factory=list)
    frame: Frame | None = None        # decorative frame; None = none
    series: Series | None = None      # series from table or numbering; None = single label

    def is_empty(self) -> bool:
        """True if nothing would be printed: no object with visible content and no frame."""
        return self.frame is None and all(obj.is_empty() for obj in self.objects)
