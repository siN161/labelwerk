"""Lädt fertige Dateien (PDF, PNG, JPG) und bringt sie 1:1 aufs Etikett; lädt Bilder für
Bild-Objekte (``load_image``)."""
from __future__ import annotations

import struct
import zlib
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageOps

from .imaging import MAX_PIXELS, limit_size, on_white, to_8bit
from .labels import DPI, format_mm, get_label, length_limits
from .render import MARGIN

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
# Bild-Objekte: zusätzlich GIF (erstes Bild), BMP, WebP; SVG rastert die Oberfläche
_OBJECT_SUFFIXES = (*_IMAGE_SUFFIXES, ".gif", ".bmp", ".webp")

INK = 128            # dunkler gilt als bedruckt
NOT_WHITE = 245      # Bild-Objekte: alles, was nicht (fast) weiß ist, gehört zum Inhalt
_PDFIUM_PASSWORD = 4   # FPDF_ERR_PASSWORD
MM = DPI / 25.4      # Punkte pro mm


def load_file(path: str | Path, page: int = 1) -> Image.Image:
    """Datei als Graustufenbild bei 300 dpi (Größe in mm bleibt erhalten)."""
    path = _checked(path, _IMAGE_SUFFIXES, "PDF, PNG, JPG", page)
    with _readable(path):
        return _load_pdf(path, page) if path.suffix.lower() == ".pdf" else _load_image(path)


def load_image(path: str | Path, page: int = 1) -> tuple[Image.Image, float]:
    """Bild für ein Bild-Objekt: (RGB-Bild in Originalauflösung, dpi).

    PNG, JPG, GIF (erstes Bild), BMP, WebP und PDF (Seite ``page``, gerendert bei 300 dpi).
    Transparenz wird weiß, die EXIF-Lage (Handyfotos) wird angewandt; ohne DPI-Angabe
    gelten 300 dpi (auf 0,01 gerundet: PNG speichert Punkte je Meter). Ist die Auflösung
    hoch und quer verschieden (Fax: 204 × 98 dpi), wird die Höhe passend skaliert – die
    Druckgröße stimmt, ``dpi`` ist die waagrechte. Sehr große Bilder werden begrenzt
    (``imaging.limit_size``: höchstens 600 dpi bzw. 6000 px längste Seite) – PDF-Seiten
    werden gleich passend gerendert.
    """
    path = _checked(path, _OBJECT_SUFFIXES, "PNG, JPG, GIF, BMP, WebP, PDF", page)
    with _readable(path):
        if path.suffix.lower() == ".pdf":
            return _load_pdf_page(path, page)
        with Image.open(path) as src:                  # GIF: erstes Bild
            x_dpi, y_dpi = _file_dpi(src)
            if src.getexif().get(0x0112, 1) in (5, 6, 7, 8):   # EXIF dreht um 90°
                x_dpi, y_dpi = y_dpi, x_dpi
            img = on_white(ImageOps.exif_transpose(src))   # Handyfotos: Lage aus EXIF
        return limit_size(img, x_dpi, x_dpi / y_dpi)    # Höhe passend, Grenzen vor dem Strecken


def _file_dpi(src: Image.Image) -> tuple[float, float]:
    """Auflösung (waagrecht, senkrecht) aus der Datei, auf 0,01 gerundet; fehlt sie oder
    ist sie 0, gelten 300 dpi."""
    dpi = src.info.get("dpi", (DPI, DPI))
    return tuple(round(float(v), 2) or float(DPI) for v in dpi[:2])


def page_count(path: str | Path) -> int:
    """Seitenzahl einer PDF-Datei (für die Seitenwahl vor ``load_image``)."""
    path = _checked(path, (), "PDF", 1)
    with _readable(path):
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(path)
        try:
            return len(pdf)
        finally:
            pdf.close()


def _checked(path: str | Path, suffixes: tuple[str, ...], allowed: str, page: int) -> Path:
    """Dateityp, Vorhandensein und Seitenzahl prüfen."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix != ".pdf" and suffix not in suffixes:
        raise ValueError(f"Dateityp nicht unterstützt: {suffix or path.name} – möglich: {allowed}")
    if not path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
    if suffix == ".pdf" and page < 1:
        raise ValueError("Seite muss mindestens 1 sein.")
    return path


@contextmanager
def _readable(path: Path):
    """Lesefehler als verständliche deutsche Meldung (``ValueError``, fehlende Datei
    ``FileNotFoundError``) – ohne englischen Text aus Betriebssystem, Pillow oder PDFium."""
    try:
        yield
    except FileNotFoundError:
        raise FileNotFoundError(f"Datei nicht gefunden: {path}") from None
    except (OSError, RuntimeError, SyntaxError, struct.error, zlib.error,
            Image.DecompressionBombError) as e:
        raise ValueError(f"Datei kann nicht gelesen werden: {path.name} ({_reason(e)})") from e


def _reason(error: Exception) -> str:
    """Grund eines Lesefehlers auf Deutsch."""
    if isinstance(error, IsADirectoryError):
        return "ist ein Ordner"
    if isinstance(error, PermissionError):
        return "keine Leserechte"
    if isinstance(error, Image.DecompressionBombError):
        return "Bild hat zu viele Pixel"
    if isinstance(error, Image.UnidentifiedImageError):
        return "kein lesbares Bild"
    if isinstance(error, RuntimeError):            # PDFium (pypdfium2.PdfiumError)
        if getattr(error, "err_code", None) == _PDFIUM_PASSWORD:
            return "PDF ist verschlüsselt"
        return "keine gültige PDF-Datei"
    if (isinstance(error, (SyntaxError, struct.error, zlib.error))
            or any(word in str(error) for word in ("truncated", "broken", "corrupt"))):
        return "Datei ist beschädigt oder unvollständig"
    return "Lesefehler"


def _load_pdf(path: Path, page: int) -> Image.Image:
    with _pdf_page(path, page) as pdf_page:
        return pdf_page.render(scale=DPI / 72).to_pil().convert("L")


def _load_pdf_page(path: Path, page: int) -> tuple[Image.Image, float]:
    """PDF-Seite in Farbe bei 300 dpi – bei sehr großen Seiten gröber (``MAX_PIXELS``)."""
    with _pdf_page(path, page) as pdf_page:
        dpi = min(DPI, MAX_PIXELS * 72 / max(pdf_page.get_size()))
        return pdf_page.render(scale=dpi / 72).to_pil().convert("RGB"), dpi


@contextmanager
def _pdf_page(path: Path, page: int):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(path)
    try:
        if not 1 <= page <= len(pdf):
            raise ValueError(f"PDF hat nur {len(pdf)} Seite(n).")
        yield pdf[page - 1]
    finally:
        pdf.close()


def _load_image(path: Path) -> Image.Image:
    with Image.open(path) as src:
        dpi = float(src.info.get("dpi", (DPI, DPI))[0]) or DPI
        img = to_8bit(src).convert("RGBA")             # 16-Bit-Graustufen skalieren
    img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img).convert("L")
    if round(dpi) != DPI:
        f = DPI / dpi
        img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
                         Image.LANCZOS)
    return img


def crop(img: Image.Image) -> Image.Image:
    """Auf den Inhalt zuschneiden; liegen vier Eck-Schnittmarken außen, ohne die Marken."""
    return img.crop(_content_box(img, DPI, INK))


def crop_box(img: Image.Image, dpi: float = DPI,
             ink: int = INK) -> tuple[int, int, int, int] | None:
    """Ausschnitt (l, t, r, b) mit dem Inhalt; liegen vier Eck-Schnittmarken außen, ohne die
    Marken und den Leerraum dazwischen – None, wenn das Bild keinen Inhalt hat.

    Inhalt ist, was dunkler als ``ink`` ist (Standard wie ``crop()``; Bild-Objekte nehmen
    ``NOT_WHITE``, damit helle Fotos und gelbe Logos nicht abgeschnitten werden). Die Marken
    selbst werden immer mit ``INK`` gesucht – helle Elemente außerhalb stören nicht. Bilder in
    Farbe zählen nach ihrer Helligkeit, Transparenz zuerst auf Weiß; ``dpi``: Auflösung des
    Bilds (Maße der Marken in mm).
    """
    try:
        return _content_box(img, dpi, ink)
    except ValueError:
        return None


def _content_box(img: Image.Image, dpi: float, level: int) -> tuple[int, int, int, int]:
    """``crop_box``, ohne Inhalt aber ``ValueError`` mit Meldung (für ``crop()``)."""
    gray = img if img.mode == "L" else on_white(img).convert("L")
    ink = gray.point(lambda v: 255 if v < level else 0)
    box = ink.getbbox()
    if box is None:
        raise ValueError("Datei enthält keinen druckbaren Inhalt.")
    # Schnittmarken sind schwarz: immer auf der Maske mit ``INK`` suchen, damit helle
    # Elemente anderswo auf der Seite (graue Textzeile) sie nicht vom Rand verdrängen
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
    trimmed = ink.crop(inner).getbbox()  # Leerraum innerhalb der Marken entfernen
    if trimmed is None:
        raise ValueError("Zwischen den Schnittmarken ist kein druckbarer Inhalt.")
    return (inner[0] + trimmed[0], inner[1] + trimmed[1],
            inner[0] + trimmed[2], inner[1] + trimmed[3])


def _corner_mark(ink: Image.Image, mm: float = MM) -> tuple[int, int] | None:
    """Innenkante (x, y) eines Schnittmarken-Kreuzes in der Ecke oben links, sonst None.

    Linien müssen am Rand des Inhalts beginnen, auf den ersten 3 mm zu 40 % dunkel
    (auch gepunktet) und höchstens 1 mm dick sein – so gilt Text oder ein Logo nicht als Marke.
    ``mm``: Pixel je mm.
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
                 model: str = "QL-600", rotate: str | int = "auto") -> Image.Image:
    """Motiv 1:1 mittig aufs Etikett setzen; verkleinern nur mit fit.

    rotate: "auto" dreht nur wenn nötig (90° gegen den Uhrzeigersinn), sonst feste
    Drehung in Grad im Uhrzeigersinn (0, 90, 180, 270).
    """
    if rotate not in ROTATIONS:
        raise ValueError(f"Drehung {rotate!r} nicht möglich – erlaubt: auto, 0, 90, 180, 270")
    label = get_label(label_id)
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
            limit = (f"{format_mm(max_w)} mm breit" if not label.height
                     else f"{format_mm(max_w)} × {format_mm(max_h)} mm groß")
            raise ValueError(
                f"Motiv ist {format_mm(img.width)} × {format_mm(img.height)} mm, "
                f"Etikett {label_id!r} ist höchstens {limit} – "
                "mit --fit verkleinern (Codes evtl. nicht mehr lesbar)")

    height = label.height or min(max(img.height + 2 * MARGIN, min_len), max_len)
    out = Image.new("L", (max_w, height), 255)
    out.paste(img, ((max_w - img.width) // 2, (height - img.height) // 2))
    return out


def _shrink(img: Image.Image, max_w: int, max_h: int, may_rotate: bool = True) -> Image.Image:
    """Proportional verkleinern; mit may_rotate in der Lage, die größer bleibt."""
    def scale(w: int, h: int) -> float:
        return min(max_w / w, max_h / h)

    if may_rotate and scale(img.height, img.width) > scale(*img.size):
        img = img.rotate(90, expand=True)
    s = scale(*img.size)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
