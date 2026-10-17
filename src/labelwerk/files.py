"""Lädt fertige Dateien (PDF, PNG, JPG) und bringt sie 1:1 aufs Etikett."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .labels import DPI

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


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
