"""Prepare images for printing (without Qt): put on white, limit the size, convert into
print layers.

Print layers (``to_layers``) are images in mode "1" as printed: black (0) = ink,
white (255) = paper. Today there is only the ``"black"`` layer. For the two-colour printing of the
QL-8xx a ``"red"`` layer will be added later – from the colour image (red tones → red, the
rest → black); printing then combines both layers (brother_ql ``red=True``).
That is why the original stays in colour until ``to_layers`` converts it.
"""
from __future__ import annotations

from PIL import Image, ImageChops

from .i18n import _

MODES = ("line", "photo")      # line (hard threshold) | photo (halftone dots)
MAX_DPI = 600                  # the QL prints no finer (300 dpi) – more only costs memory
MAX_PIXELS = 6000              # longest side in pixels (memory; at 300 dpi a good 50 cm)


_GRAY_16 = ("I", "I;16", "I;16B", "I;16L", "I;16N")   # 16-bit greyscale (PNG, TIFF)


def to_8bit(img: Image.Image) -> Image.Image:
    """Scale 16-bit greyscale to 8 bit (0–65535 → 0–255); Pillow would clip when
    converting – the image would arrive almost white. Other images unchanged."""
    if img.mode in _GRAY_16:
        return img.convert("I").point(lambda v: v / 257).convert("L")
    return img


def on_white(img: Image.Image) -> Image.Image:
    """Image as RGB; transparency (alpha channel, transparent palette colour) becomes white."""
    img = to_8bit(img)
    if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba).convert("RGB")
    if img.mode == "F":                       # floating-point greyscale
        img = img.convert("L")
    return img.convert("RGB")


def limit_size(img: Image.Image, dpi: float,
               stretch: float = 1.0) -> tuple[Image.Image, float]:
    """Shrink very large images: at most ``MAX_DPI`` relative to the print size and
    at most ``MAX_PIXELS`` on the longest side. The print size stays (the resolution
    drops with it); an image within the limits comes back unchanged. ``stretch``: factor for the
    height (unequal resolution) – the calculation uses the stretched size, in one
    step from the original (no upscaling beforehand); even with ``factor`` 1 it is
    stretched then."""
    height = max(1, round(img.height * stretch))
    factor = min(1.0, MAX_DPI / dpi, MAX_PIXELS / max(img.width, height))
    if factor >= 1.0 and height == img.height:
        return img, dpi
    size = (max(1, round(img.width * factor)), max(1, round(height * factor)))
    return img.resize(size, Image.Resampling.LANCZOS, reducing_gap=3.0), dpi * factor


def check(mode: str, threshold: int) -> None:
    """Check the conversion and threshold; ``ValueError`` with an understandable message."""
    if mode not in MODES:
        raise ValueError(_("Unknown conversion {mode!r} – allowed: line art, photo (line, photo)").format(
            mode=mode))
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 255:
        raise ValueError(_("Threshold must be a whole number from 0 to 255, not {threshold!r}.").format(
            threshold=threshold))


def photo_curve(threshold: int) -> list[int]:
    """Brightness curve for ``"photo"`` (table 0–255): ``v' = 255 · (v / 255) ** g`` with
    ``g = 2 ** ((threshold − 128) / 64)`` – higher threshold → darker, 128 = unchanged;
    0 and 255 stay fixed (paper stays white, black stays full)."""
    gamma = 2 ** ((threshold - 128) / 64)
    return [round(255 * (v / 255) ** gamma) for v in range(256)]


def to_layers(img: Image.Image, mode: str, threshold: int,
              invert: bool) -> dict[str, Image.Image]:
    """Convert an image into print layers (see module description), same size as ``img``.

    ``"line"``: greyscale, darker than ``threshold`` becomes ink (hard threshold – codes,
    text, logos). ``"photo"``: gamma curve (``photo_curve``: 128 = unchanged, white and
    black stay), then Floyd-Steinberg dithering (photos, gradients) – white paper
    never gets dots. In both cases: higher threshold → more ink. ``invert`` swaps
    ink and paper at the end.
    """
    check(mode, threshold)
    gray = img.convert("L")
    if mode == "line":
        black = gray.point([0 if v < threshold else 255 for v in range(256)])
        black = black.convert("1", dither=Image.Dither.NONE)
    else:
        if threshold != 128:
            gray = gray.point(photo_curve(threshold))
        black = gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    if invert:
        black = ImageChops.invert(black)
    return {"black": black}
