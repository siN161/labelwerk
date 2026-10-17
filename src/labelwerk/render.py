"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .document import MAX_MARGIN_MM, ORIENTATIONS, Document, TextObject
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
    box = probe.multiline_textbbox((0, 0), text, font=font, align="center")
    return tuple(round(v) for v in box)        # Pillow liefert teils Kommazahlen


def render_text(
    text: str,
    label_id: str,
    font_size: int | None = None,
    font_path: str | None = None,
) -> Image.Image:
    obj = TextObject(text, font_size=font_size, font_path=font_path)
    return render_document(Document(label_id, objects=[obj]))


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).

    Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
    wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
    Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
    """
    if doc.orientation not in ORIENTATIONS:
        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
    horizontal = doc.orientation == "horizontal"
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
    across = label.width                      # quer zum Band (fest)
    feed = label.height                       # in Bandlaufrichtung; None = automatisch
    if feed is None and doc.length_mm is not None:
        feed = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
    obj = doc.objects[0] if doc.objects else TextObject()

    across_room = across - 2 * MARGIN
    feed_room = (feed if feed else max_len) - 2 * margin
    max_w, max_h = (feed_room, across_room) if horizontal else (across_room, feed_room)
    start = obj.font_size or max(10, across // 5)   # automatisch: höchstens 1/5 der Bandbreite
    font, (l, t, r, b) = _fit_font(obj, start, max_w, max_h, doc.label_id)

    text_w, text_h = r - l, b - t
    if feed is None:
        feed = min(max((text_w if horizontal else text_h) + 2 * margin, min_len), max_len)
    width, height = (feed, across) if horizontal else (across, feed)
    img = Image.new("RGB", (width, height), "white")
    x = (width - text_w) // 2 - l
    y = (height - text_h) // 2 - t
    ImageDraw.Draw(img).multiline_text((x, y), obj.text, fill="black", font=font, align="center")
    return img.rotate(-90, expand=True) if horizontal else img


def _fit_font(obj: TextObject, start: int, max_w: int, max_h: int, label_id: str):
    """Größte Schrift ≤ start, mit der der Text in max_w × max_h passt (Halbierungssuche)."""
    def attempt(size):
        font = _load_font(size, obj.font_path)
        box = _text_box(obj.text, font)
        return (box[2] - box[0]) <= max_w and (box[3] - box[1]) <= max_h, font, box

    ok, font, box = attempt(start)
    if ok:
        return font, box
    best, lo, hi = None, 8, start - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        ok, f, bx = attempt(mid)
        if ok:
            best, lo = (mid, f, bx), mid + 1
        else:
            hi = mid - 1
    if obj.font_size is not None:
        raise TextTooLarge(obj.font_size, best[0] if best else 8, label_id)
    if best is None:                          # passt nicht einmal in 8 – kleinste Größe zeigen
        _, f, bx = attempt(8)
        return f, bx
    return best[1], best[2]
