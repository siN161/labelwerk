"""Loads finished files (PDF, PNG, JPG) and puts them 1:1 onto the label; loads images for
image objects (``load_image``)."""
from __future__ import annotations

import struct
import threading
import zlib
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageOps

from .i18n import _, ngettext
from .imaging import MAX_PIXELS, limit_size, on_white, to_8bit
from .labels import DPI, format_mm, get_label, length_limits
from .render import MARGIN

# PDFium is not thread-safe: every call (here, preview in the file dialog, parcel labels) holds this lock
PDFIUM_LOCK = threading.RLock()

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
# Image objects: additionally GIF (first frame), BMP, WebP; the GUI rasterises SVG
_OBJECT_SUFFIXES = (*_IMAGE_SUFFIXES, ".gif", ".bmp", ".webp")
_IMAGE_FORMATS = ["PNG", "JPEG"]                       # Pillow formats for the extensions
_OBJECT_FORMATS = [*_IMAGE_FORMATS, "GIF", "BMP", "WEBP"]

INK = 128            # darker counts as printed
INK_LEVEL = 250      # symbols: lighter than this counts as paper when cropping
NOT_WHITE = 245      # image objects: everything that is not (almost) white belongs to the content
_PDFIUM_PASSWORD = 4   # FPDF_ERR_PASSWORD
MM = DPI / 25.4      # dots per mm


def load_file(path: str | Path, page: int = 1, dpi: int = DPI) -> Image.Image:
    """File as a greyscale image at ``dpi`` (resolution of the label; size in mm stays)."""
    path = _checked(path, _IMAGE_SUFFIXES, "PDF, PNG, JPG", page)
    with _readable(path):
        return (_load_pdf(path, page, dpi) if path.suffix.lower() == ".pdf"
                else _load_image(path, dpi))


def load_image(path: str | Path, page: int = 1,
               dpi: float | None = None) -> tuple[Image.Image, float]:
    """Image for an image object: (RGB image at original resolution, dpi).

    PNG, JPG, GIF (first frame), BMP, WebP and PDF (page ``page``, rendered at 300 dpi).
    Transparency becomes white, the EXIF orientation (phone photos) is applied; without a DPI
    value 300 dpi applies (rounded to 0.01: PNG stores dots per metre). If the resolution is
    high and differs across and along (fax: 204 × 98 dpi), the height is scaled to match – the
    print size is right, ``dpi`` is the horizontal one. Very large images are limited
    (``imaging.limit_size``: at most 600 dpi or 6000 px on the longest side) – PDF pages
    are rendered at a suitable size right away. With ``dpi`` the resolution of the file does not
    apply: the image counts as square with this resolution (no stretching, no shrinking because of
    a high value in the file), limited as usual, relative to ``dpi``; PDF pages
    stay untouched.
    """
    path = _checked(path, _OBJECT_SUFFIXES, "PNG, JPG, GIF, BMP, WebP, PDF", page)
    with _readable(path):
        if path.suffix.lower() == ".pdf":
            return _load_pdf_page(path, page)
        # fixed formats: Pillow otherwise detects them by content (EPS would run through Ghostscript)
        with Image.open(path, formats=_OBJECT_FORMATS) as src:     # GIF: first frame
            x_dpi, y_dpi = _file_dpi(src) if dpi is None else (dpi, dpi)
            if src.getexif().get(0x0112, 1) in (5, 6, 7, 8):   # EXIF rotates by 90°
                x_dpi, y_dpi = y_dpi, x_dpi
            img = on_white(ImageOps.exif_transpose(src))   # phone photos: orientation from EXIF
        return limit_size(img, x_dpi, x_dpi / y_dpi)    # height adjusted, limits before stretching


def _file_dpi(src: Image.Image) -> tuple[float, float]:
    """Resolution (horizontal, vertical) from the file, rounded to 0.01; if it is missing or
    0, 300 dpi applies."""
    dpi = src.info.get("dpi", (DPI, DPI))
    return tuple(round(float(v), 2) or float(DPI) for v in dpi[:2])


def page_count(path: str | Path) -> int:
    """Page count of a PDF file (for the page choice before ``load_image``)."""
    path = _checked(path, (), "PDF", 1)
    with _readable(path), PDFIUM_LOCK:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(path)
        try:
            return len(pdf)
        finally:
            pdf.close()


def _checked(path: str | Path, suffixes: tuple[str, ...], allowed: str, page: int) -> Path:
    """Check file type, existence and page count."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix != ".pdf" and suffix not in suffixes:
        raise ValueError(_("File type not supported: {suffix} – possible: {allowed}").format(
            suffix=suffix or path.name, allowed=allowed))
    if not path.exists():
        raise FileNotFoundError(_("File not found: {path}").format(path=path))
    if suffix == ".pdf" and page < 1:
        raise ValueError(_("Page must be at least 1."))
    return path


@contextmanager
def _readable(path: Path):
    """Read errors as a readable message (``ValueError``, missing file
    ``FileNotFoundError``) – without English text from the operating system, Pillow or PDFium."""
    try:
        yield
    except FileNotFoundError:
        raise FileNotFoundError(_("File not found: {path}").format(path=path)) from None
    except (OSError, RuntimeError, SyntaxError, struct.error, zlib.error,
            Image.DecompressionBombError) as e:
        raise ValueError(_("Cannot read file: {name} ({reason})").format(
            name=path.name, reason=_reason(e))) from e


def _reason(error: Exception) -> str:
    """Reason for a read error (translated)."""
    if isinstance(error, IsADirectoryError):
        return _("is a folder")
    if isinstance(error, PermissionError):
        return _("no read permission")
    if isinstance(error, Image.DecompressionBombError):
        return _("image has too many pixels")
    if isinstance(error, Image.UnidentifiedImageError):
        return _("not a readable image")
    if isinstance(error, RuntimeError):            # PDFium (pypdfium2.PdfiumError)
        if getattr(error, "err_code", None) == _PDFIUM_PASSWORD:
            return _("PDF is encrypted")
        return _("not a valid PDF file")
    if (isinstance(error, (SyntaxError, struct.error, zlib.error))
            or any(word in str(error) for word in ("truncated", "broken", "corrupt"))):
        return _("file is damaged or incomplete")
    return _("read error")


def _load_pdf(path: Path, page: int, dpi: int = DPI) -> Image.Image:
    with _pdf_page(path, page) as pdf_page:
        return pdf_page.render(scale=dpi / 72).to_pil().convert("L")


def _load_pdf_page(path: Path, page: int) -> tuple[Image.Image, float]:
    """PDF page in colour at 300 dpi – coarser for very large pages (``MAX_PIXELS``)."""
    with _pdf_page(path, page) as pdf_page:
        dpi = min(DPI, MAX_PIXELS * 72 / max(pdf_page.get_size()))
        return pdf_page.render(scale=dpi / 72).to_pil().convert("RGB"), dpi


@contextmanager
def _pdf_page(path: Path, page: int):
    import pypdfium2 as pdfium

    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            if not 1 <= page <= len(pdf):
                raise ValueError(ngettext("The PDF has only {count} page.",
                                          "The PDF has only {count} pages.",
                                          len(pdf)).format(count=len(pdf)))
            yield pdf[page - 1]
        finally:
            pdf.close()


def _load_image(path: Path, target: int = DPI) -> Image.Image:
    with Image.open(path, formats=_IMAGE_FORMATS) as src:
        dpi = float(src.info.get("dpi", (DPI, DPI))[0]) or DPI
        img = to_8bit(src).convert("RGBA")             # scale 16-bit greyscale
    img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img).convert("L")
    if round(dpi) != target:
        f = target / dpi
        img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
                         Image.LANCZOS)
    return img


def crop(img: Image.Image, dpi: int = DPI) -> Image.Image:
    """Crop to the content; if four corner crop marks lie outside, without the marks."""
    return img.crop(_content_box(img, dpi, INK))


def crop_box(img: Image.Image, dpi: float = DPI,
             ink: int = INK) -> tuple[int, int, int, int] | None:
    """Section (l, t, r, b) with the content; if four corner crop marks lie outside, without the
    marks and the empty space between them – None if the image has no content.

    Content is what is darker than ``ink`` (default as in ``crop()``; image objects use
    ``NOT_WHITE`` so that light photos and yellow logos are not cut off). The marks
    themselves are always searched with ``INK`` – light elements outside do not disturb. Colour
    images count by their brightness, transparency first onto white; ``dpi``: resolution of the
    image (size of the marks in mm).
    """
    try:
        return _content_box(img, dpi, ink)
    except ValueError:
        return None


def ink_box(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Outline of everything not white (lighter than ``INK_LEVEL`` is paper), without crop-mark
    detection – for symbols whose outlined glyphs ``crop_box`` would otherwise cut inside;
    entirely white: None."""
    return on_white(img).convert("L").point(lambda v: 255 if v < INK_LEVEL else 0).getbbox()


def _content_box(img: Image.Image, dpi: float, level: int) -> tuple[int, int, int, int]:
    """``crop_box``, but without content ``ValueError`` with a message (for ``crop()``)."""
    gray = img if img.mode == "L" else on_white(img).convert("L")
    ink = gray.point(lambda v: 255 if v < level else 0)
    box = ink.getbbox()
    if box is None:
        raise ValueError(_("The file has no printable content."))
# Crop marks are black: always search on the mask with ``INK`` so that light
# elements elsewhere on the page (grey line of text) do not displace them from the edge
    marks = ink if level == INK else gray.point(lambda v: 255 if v < INK else 0)
    marks_box = marks.getbbox()
    if marks_box is None:
        return box
    content = marks.crop(marks_box)
    mm = dpi / 25.4
    tl = _corner_mark(content, mm)
    tr = _corner_mark(ImageOps.mirror(content), mm)
    bl = _corner_mark(ImageOps.flip(content), mm)
    br = _corner_mark(content.rotate(180), mm)
    if None in (tl, tr, bl, br):
        return box
    w, h = content.size
    left, top = max(tl[0], bl[0]), max(tl[1], tr[1])
    right, bottom = w - max(tr[0], br[0]), h - max(bl[1], br[1])
    x0, y0 = marks_box[:2]
    inner = (x0 + left, y0 + top, x0 + right, y0 + bottom)
    trimmed = ink.crop(inner).getbbox()  # remove empty space inside the marks
    if trimmed is None:
        raise ValueError(_("There is no printable content between the crop marks."))
    return (inner[0] + trimmed[0], inner[1] + trimmed[1],
            inner[0] + trimmed[2], inner[1] + trimmed[3])


def _corner_mark(ink: Image.Image, mm: float = MM) -> tuple[int, int] | None:
    """Inner corner (x, y) of a crop-mark cross in the top-left corner, otherwise None.

    Lines must start at the edge of the content, be 40 % dark over the first 3 mm
    (also dotted) and at most 1 mm thick – so text or a logo does not count as a mark.
    ``mm``: pixels per mm.
    """
    span, window = round(3 * mm), round(10 * mm)
    w, h = ink.size
    px = ink.load()
    need = 0.4 * span
    rows = [y for y in range(min(window, h))
            if sum(px[x, y] > 0 for x in range(min(span, w))) >= need]
    cols = [x for x in range(min(window, w))
            if sum(px[x, y] > 0 for y in range(min(span, h))) >= need]
    if not rows or not cols or rows[-1] - rows[0] > mm or cols[-1] - cols[0] > mm:
        return None
    return cols[-1] + 2, rows[-1] + 2


ROTATIONS = ("auto", 0, 90, 180, 270)


def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
                 model: str = "QL-600", rotate: str | int = "auto",
                 dpi: int = DPI) -> Image.Image:
    """Place the motif (``dpi`` as in ``load_file``) 1:1 centred on the label – at the resolution
    of the label (others are converted); shrink only with fit.

    rotate: "auto" rotates only when needed (90° counter-clockwise), otherwise a fixed
    rotation in degrees clockwise (0, 90, 180, 270).
    """
    if rotate not in ROTATIONS:
        raise ValueError(_("Rotation {rotate!r} not possible – allowed: auto, 0, 90, 180, 270").format(
            rotate=rotate))
    label = get_label(label_id)
    if label.dpi != dpi:                         # same size in the printer's dots
        f = label.dpi / dpi
        img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
                         Image.LANCZOS)
    min_len, max_len = length_limits(model)
    max_w = label.width
    max_h = label.height if label.height else max_len - 2 * MARGIN

    def fits(w: int, h: int) -> bool:
        return w <= max_w and h <= max_h

    if rotate != "auto":
        img = img.rotate(-rotate, expand=True)
    if not fits(*img.size):
        if rotate == "auto" and fits(img.height, img.width):
            img = img.rotate(90, expand=True)
        elif fit:
            img = _shrink(img, max_w, max_h, may_rotate=rotate == "auto")
        else:
            mm = lambda dots: format_mm(dots, label.dpi)   # noqa: E731
            text = (_("Image is {width} × {height} mm, label {label!r} is at most {max_w} mm wide – "
                      "shrink with --fit (codes may become unreadable)") if not label.height
                    else _("Image is {width} × {height} mm, label {label!r} is at most {max_w} × "
                           "{max_h} mm – shrink with --fit (codes may become unreadable)"))
            raise ValueError(text.format(width=mm(img.width), height=mm(img.height), label=label_id,
                                         max_w=mm(max_w), max_h=mm(max_h)))

    height = label.height or min(max(img.height + 2 * MARGIN, min_len), max_len)
    out = Image.new("L", (max_w, height), 255)
    out.paste(img, ((max_w - img.width) // 2, (height - img.height) // 2))
    return out


def _shrink(img: Image.Image, max_w: int, max_h: int, may_rotate: bool = True) -> Image.Image:
    """Scale down proportionally; with may_rotate in the orientation that stays larger."""
    def scale(w: int, h: int) -> float:
        return min(max_w / w, max_h / h)

    if may_rotate and scale(img.height, img.width) > scale(*img.size):
        img = img.rotate(90, expand=True)
    s = scale(*img.size)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
