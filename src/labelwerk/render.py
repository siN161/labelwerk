"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .labels import get_label

MARGIN = 12  # Punkte, ca. 1 mm
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",            # Arch
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",  # Fedora
]


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
    label = get_label(label_id)
    max_w = label.width - 2 * MARGIN
    max_h = (label.height - 2 * MARGIN) if label.height else None

    size = font_size or max(10, label.width // 5)
    while True:
        font = _load_font(size, font_path)
        l, t, r, b = _text_box(text, font)
        fits_w = (r - l) <= max_w
        fits_h = max_h is None or (b - t) <= max_h
        if (fits_w and fits_h) or size <= 8:
            break
        size -= 2

    text_w, text_h = r - l, b - t
    height = label.height or text_h + 2 * MARGIN
    img = Image.new("RGB", (label.width, height), "white")
    x = (label.width - text_w) // 2 - l
    y = (height - text_h) // 2 - t
    ImageDraw.Draw(img).multiline_text((x, y), text, fill="black", font=font, align="center")
    return img
