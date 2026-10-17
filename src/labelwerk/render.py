"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .document import Document, TextObject
from .labels import DPI, get_label, length_limits

MARGIN = 12  # Punkte, ca. 1 mm
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",            # Arch
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",  # Fedora
]


class TextTooLarge(ValueError):
    """Text passt bei fester Schriftgröße nicht aufs Etikett."""

    def __init__(self, size: int, max_size: int, label_id: str):
        super().__init__(f"Text passt nicht auf Etikett {label_id!r} bei Schriftgröße {size} "
                         f"(höchstens {max_size}).")
        self.size, self.max_size = size, max_size


def _load_font(size: int, font_path: str | None):
    for path in [font_path, *_FONT_CANDIDATES]:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _text_box(text: str, font) -> tuple[int, int, int, int]:
    probe = ImageDraw.Draw(Image.new("1", (1, 1)))
    return probe.multiline_textbbox((0, 0), text, font=font, align="center")


def render_text(
    text: str,
    label_id: str,
    font_size: int | None = None,
    font_path: str | None = None,
) -> Image.Image:
    obj = TextObject(text, font_size=font_size, font_path=font_path)
    return render_document(Document(label_id, objects=[obj]))


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Dokument als Bild in exakter Druckauflösung (Vorschau = Druck)."""
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    height = label.height
    if height is None and doc.length_mm is not None:
        height = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
    obj = doc.objects[0] if doc.objects else TextObject()
    text, font_size, font_path = obj.text, obj.font_size, obj.font_path

    max_w = label.width - 2 * MARGIN
    max_h = (height - 2 * MARGIN) if height else None

    size = font_size or max(10, label.width // 5)
    while True:
        font = _load_font(size, font_path)
        l, t, r, b = _text_box(text, font)
        fits_w = (r - l) <= max_w
        fits_h = max_h is None or (b - t) <= max_h
        if (fits_w and fits_h) or size <= 8:
            break
        size -= 2
    if font_size is not None and size != font_size:
        raise TextTooLarge(font_size, size, doc.label_id)

    text_w, text_h = r - l, b - t
    height = height or min(max(text_h + 2 * MARGIN, min_len), max_len)
    img = Image.new("RGB", (label.width, height), "white")
    x = (label.width - text_w) // 2 - l
    y = (height - text_h) // 2 - t
    ImageDraw.Draw(img).multiline_text((x, y), text, fill="black", font=font, align="center")
    return img
