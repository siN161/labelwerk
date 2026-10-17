"""Lädt fertige Dateien (PDF, PNG, JPG) und bringt sie 1:1 aufs Etikett."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from .labels import DPI, format_mm, get_label, length_limits
from .render import MARGIN

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")

INK = 128            # dunkler gilt als bedruckt
MM = DPI / 25.4      # Punkte pro mm


def load_file(path: str | Path, page: int = 1) -> Image.Image:
    """Datei als Graustufenbild bei 300 dpi (Größe in mm bleibt erhalten)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix != ".pdf" and suffix not in _IMAGE_SUFFIXES:
        raise ValueError(f"Dateityp nicht unterstützt: {suffix or path.name} – möglich: PDF, PNG, JPG")
    if not path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
    return _load_pdf(path, page) if suffix == ".pdf" else _load_image(path)


def _load_pdf(path: Path, page: int) -> Image.Image:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(path)
    try:
        if not 1 <= page <= len(pdf):
            raise ValueError(f"PDF hat nur {len(pdf)} Seite(n).")
        return pdf[page - 1].render(scale=DPI / 72).to_pil().convert("L")
    finally:
        pdf.close()


def _load_image(path: Path) -> Image.Image:
    with Image.open(path) as src:
        dpi = float(src.info.get("dpi", (DPI, DPI))[0]) or DPI
        img = src.convert("RGBA")
    img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img).convert("L")
    if round(dpi) != DPI:
        f = DPI / dpi
        img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
                         Image.LANCZOS)
    return img


def crop(img: Image.Image) -> Image.Image:
    """Auf den Bereich zwischen vier Eck-Schnittmarken zuschneiden, sonst auf den Inhalt."""
    ink = img.point(lambda v: 255 if v < INK else 0)
    box = ink.getbbox()
    if box is None:
        raise ValueError("Datei enthält keinen druckbaren Inhalt.")
    content = ink.crop(box)
    tl = _corner_mark(content)
    tr = _corner_mark(ImageOps.mirror(content))
    bl = _corner_mark(ImageOps.flip(content))
    br = _corner_mark(content.rotate(180))
    if None in (tl, tr, bl, br):
        return img.crop(box)
    w, h = content.size
    left, top = max(tl[0], bl[0]), max(tl[1], tr[1])
    right, bottom = w - max(tr[0], br[0]), h - max(bl[1], br[1])
    return img.crop((box[0] + left, box[1] + top, box[0] + right, box[1] + bottom))


def _corner_mark(ink: Image.Image) -> tuple[int, int] | None:
    """Innenkante (x, y) eines Schnittmarken-Kreuzes in der Ecke oben links, sonst None.

    Linien müssen am Rand des Inhalts beginnen, auf den ersten 3 mm zu 40 % dunkel
    (auch gepunktet) und höchstens 1 mm dick sein – so gilt Text oder ein Logo nicht als Marke.
    """
    span, window = round(3 * MM), round(10 * MM)
    w, h = ink.size
    px = ink.load()
    need = 0.4 * span
    rows = [y for y in range(min(window, h))
            if sum(px[x, y] > 0 for x in range(min(span, w))) >= need]
    cols = [x for x in range(min(window, w))
            if sum(px[x, y] > 0 for y in range(min(span, h))) >= need]
    if not rows or not cols or rows[-1] - rows[0] > MM or cols[-1] - cols[0] > MM:
        return None
    return cols[-1] + 2, rows[-1] + 2


def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
                 model: str = "QL-600") -> Image.Image:
    """Motiv 1:1 mittig aufs Etikett setzen; drehen nur wenn nötig, verkleinern nur mit fit."""
    label = get_label(label_id)
    min_len, max_len = length_limits(model)
    max_w = label.width
    max_h = label.height if label.height else max_len - 2 * MARGIN

    def fits(w: int, h: int) -> bool:
        return w <= max_w and h <= max_h

    if not fits(*img.size):
        if fits(img.height, img.width):
            img = img.rotate(90, expand=True)
        elif fit:
            img = _shrink(img, max_w, max_h)
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


def _shrink(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Proportional verkleinern, in der Lage (gedreht oder nicht), die größer bleibt."""
    def scale(w: int, h: int) -> float:
        return min(max_w / w, max_h / h)

    if scale(img.height, img.width) > scale(*img.size):
        img = img.rotate(90, expand=True)
    s = scale(*img.size)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
