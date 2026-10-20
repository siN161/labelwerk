"""Frozen copy of render.py before stage 3d-1 (reference for the pixel comparison).

Only the imports were changed to absolute; otherwise unchanged. Do not develop further.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from labelwerk import fonts
from labelwerk.document import (ALIGNMENTS, MAX_MARGIN_MM, MIN_PT, ORIENTATIONS, Document, Paragraph,
                                Span, TextObject)
from labelwerk.labels import DPI, get_label, length_limits

MARGIN = 12            # dots, about 1 mm
PT = DPI / 72          # dots per typographic point
REF_PT = 12.0          # reference size for automatic scaling of pieces with their own size
MIN_DOTS = 8           # smallest font in dots
_LINE_GAP = 4          # like Pillow multiline_text
_SLANT = 0.2           # substitute italic: shear when the font has no real italic


class TextTooLarge(ValueError):
    """Text does not fit on the label at a fixed font size."""

    def __init__(self, size_pt: float, max_pt: float | None, label_id: str):
        if max_pt is None:                     # does not fit even at the smallest size
            message = (f"Text passt nicht auf Etikett {label_id!r} – auch nicht in der "
                       "kleinsten Schriftgröße.")
        else:
            message = (f"Text passt nicht auf Etikett {label_id!r} bei Schriftgröße "
                       f"{_fmt_pt(size_pt)} pt (höchstens {_fmt_pt(max_pt)} pt).")
        super().__init__(message)
        self.size_pt, self.max_pt = size_pt, max_pt


def _fmt_pt(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def render_text(text: str, label_id: str, size_pt: float | None = None,
                font_path: str | None = None) -> Image.Image:
    """Render plain text (default formatting)."""
    obj = TextObject.plain(text, size_pt=size_pt, font_path=font_path)
    return render_document(Document(label_id, objects=[obj]))


def font_warnings(doc: Document) -> list[str]:
    """Notes on substituted fonts (once per family)."""
    warnings: list[str] = []
    for obj in doc.objects:
        for para in obj.paragraphs:
            for span in para.spans:
                if span.family is None:
                    continue
                match = fonts.resolve(span.family, span.bold, span.italic)
                text = f"Schrift „{span.family}“ nicht gefunden – ersetzt durch „{match.family}“."
                if match.family.casefold() != span.family.casefold() and text not in warnings:
                    warnings.append(text)
    return warnings


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Document as print image in exact resolution (preview = print).

    Rendered in reading direction; with orientation “horizontal” (text along the tape)
    the image is then rotated by 90° clockwise for the printer – so the start of the text
    comes out of the printer first and the variable end lies on the right in reading direction.
    """
    if doc.orientation not in ORIENTATIONS:
        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
    horizontal = doc.orientation == "horizontal"
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
    # later: margin all around from the paper edge (the unprintable strip counts)
    side = max(0, margin - (label.total_width - label.width) // 2)
    if label.height is not None:
        margin = max(0, margin - (label.total_height - label.height) // 2)
    # later: lengthwise the printer's feed counts too, fixed length = cut piece
    margin = max(0, margin - label.feed_margin)
    across = label.width                      # across the tape (fixed)
    side = min(side, max(0, (across - 2 * MARGIN) // 2))
    feed = label.height                       # along the tape; None = automatic
    if feed is None and doc.length_mm is not None:
        feed = min(max(round(doc.length_mm * DPI / 25.4) - 2 * label.feed_margin, min_len), max_len)
    if feed is not None:                      # fixed length: the margin must not use up everything
        margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
    obj = doc.objects[0] if doc.objects else TextObject("")
    for para in obj.paragraphs:
        if para.align not in ALIGNMENTS:
            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
                             "rechts, Blocksatz (left, center, right, justify)")

    across_room = across - 2 * side
    feed_room = (feed if feed else max_len) - 2 * margin
    max_w, max_h = (feed_room, across_room) if horizontal else (across_room, feed_room)
    base = _fit(obj, max(10, across // 5), max_w, max_h, doc.label_id)
    lines = _shape(obj, base)
    l, t, r, b = _block_box(lines)

    text_w, text_h = r - l, b - t
    if feed is None:
        feed = min(max((text_w if horizontal else text_h) + 2 * margin, min_len), max_len)
    width, height = (feed, across) if horizontal else (across, feed)
    img = Image.new("RGB", (width, height), "white")
    x0 = (width - text_w) // 2 - l
    if any(para.align != "center" for para in obj.paragraphs):
        # Text frame over the full width in reading direction: paragraphs align to the frame
        start = margin if horizontal else side
        frame = width - 2 * start
        lines = _shape(obj, base, frame=frame)
        fl, ft, fr, fb = _block_box(lines)
        x0 = min(max(start, -fl), width - fr)            # ink stays in the image
        t, text_h = ft, fb - ft
    _draw(img, lines, x0, (height - text_h) // 2 - t)
    return img.rotate(-90, expand=True) if horizontal else img


# --- Font sizes ---------------------------------------------------------
def _span_dots(obj: TextObject, span: Span, base: int) -> int:
    """Size of a piece in dots at base size ``base`` (scaled together)."""
    if span.size_pt is None:
        return base
    ref = obj.size_pt or REF_PT
    return max(1, round(base * span.size_pt / ref))


def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str) -> int:
    """Base size in dots: fixed, or the largest fitting one ≤ auto_start (halving)."""
    def fits(base: int) -> bool:
        l, t, r, b = _block_box(_shape(obj, base, mode="1"))
        return (r - l) <= max_w and (b - t) <= max_h

    start = auto_start if obj.auto else round(obj.size_pt * PT)
    if fits(start):
        return start
    best, lo, hi = None, MIN_DOTS, start - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(mid):
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    if not obj.auto:
        # Message at the largest size set – that is what the user sees in the editor
        largest = max((span.size_pt or obj.size_pt for para in obj.paragraphs
                       for span in para.spans), default=obj.size_pt)
        max_pt = int(best / PT * largest / obj.size_pt) if best else None
        if max_pt is not None and max_pt < MIN_PT:
            max_pt = None                      # smaller than allowed: counts as “does not fit”
        raise TextTooLarge(largest, max_pt, label_id)
    return best if best else MIN_DOTS          # does not fit even small – show the smallest size


# --- Line layout --------------------------------------------------------------
@dataclass
class _Piece:
    text: str
    font: object
    dots: int
    underline: bool
    slant: bool                # substitute italic
    x: float = 0.0             # left, relative to the block
    y: float = 0.0             # top edge (ascender line), relative to the block


def _font_for(obj: TextObject, span: Span, dots: int):
    if span.family is None and obj.font_path:
        return fonts.load(obj.font_path, dots), span.italic   # fixed file: substitute italic
    match = fonts.resolve(span.family, span.bold, span.italic)
    return fonts.load(match.path, dots), span.italic and not match.italic


def _shape(obj: TextObject, base: int, mode: str = "L",
           frame: float | None = None) -> list[list[_Piece]]:
    """Pieces with position in the block (mode “1” for measuring, “L” for drawing – like Pillow).

    Without ``frame`` the lines align to the widest line; with ``frame``
    (frame width) to that width – justified text still stretches to the widest line."""
    rows = []
    for para in obj.paragraphs:
        spans = para.spans or [Span("")]
        pieces = []
        for span in spans:
            dots = _span_dots(obj, span, base)
            font, slant = _font_for(obj, span, dots)
            pieces.append(_Piece(span.text, font, dots, span.underline, slant))
        rows.append((para, pieces))

    widths = [sum(p.font.getlength(p.text, mode) for p in pieces) for _, pieces in rows]
    # Descenders of large pieces need room below the line; with uniform font 0
    min_descent = min(p.font.getmetrics()[1] for _, pieces in rows for p in pieces)
    max_width = max(widths, default=0)
    ref = max_width if frame is None else frame
    top = 0.0
    lines = []
    for (para, pieces), width in zip(rows, widths):
        ascent = max(p.font.getmetrics()[0] for p in pieces)
        spacing = max(p.font.getbbox("A", mode)[3] for p in pieces) + _LINE_GAP
        if para.align == "justify":
            pieces = _justify(pieces, max_width, mode)
        else:
            x = {"left": 0.0, "center": (ref - width) / 2.0,
                 "right": ref - width}[para.align]
            for p in pieces:
                p.x = x
                x += p.font.getlength(p.text, mode)
        for p in pieces:
            p.y = top + ascent - p.font.getmetrics()[0]    # common baseline
        lines.append(pieces)
        top += spacing + max(p.font.getmetrics()[1] for p in pieces) - min_descent
    return lines


def _justify(pieces: list[_Piece], max_width: float, mode: str) -> list[_Piece]:
    """Stretch word spacing until the line fills the block width (one word: left-aligned)."""
    words: list[_Piece] = []
    gaps_before: list[bool] = []
    for p in pieces:
        for i, part in enumerate(p.text.split(" ")):
            words.append(_Piece(part, p.font, p.dots, p.underline, p.slant))
            gaps_before.append(i > 0)
    gaps = sum(gaps_before[1:])
    used = sum(w.font.getlength(w.text, mode) for w in words)
    extra = (max_width - used) / gaps if gaps else 0.0
    x = 0.0
    for word, gap in zip(words, gaps_before):
        if gap:
            x += extra
        word.x = x
        x += word.font.getlength(word.text, mode)
    return words


def _block_box(lines: list[list[_Piece]]) -> tuple[int, int, int, int]:
    """Ink box of the block (like Pillow multiline_textbbox), rounded to whole dots."""
    boxes = []
    for pieces in lines:
        for p in pieces:
            l, t, r, b = p.font.getbbox(p.text, "1", anchor="la")
            if p.underline:
                b = max(b, p.font.getmetrics()[0] + _underline(p.dots)[0] + _underline(p.dots)[1])
            if p.slant:
                r += _SLANT * p.font.getmetrics()[0]
                l -= _slant_pad(p)
            boxes.append((p.x + l, p.y + t, p.x + r, p.y + b))
    if not boxes:
        return (0, 0, 0, 0)
    return tuple(round(v) for v in (min(b[0] for b in boxes), min(b[1] for b in boxes),
                                    max(b[2] for b in boxes), max(b[3] for b in boxes)))


def _underline(dots: int) -> tuple[int, int]:
    """(Distance below the baseline, thickness) in dots."""
    return max(1, round(dots * 0.10)), max(1, round(dots * 0.06))


def _draw(img: Image.Image, lines: list[list[_Piece]], x0: int, y0: int) -> None:
    draw = ImageDraw.Draw(img)
    for pieces in lines:
        for p in pieces:
            x, y = x0 + p.x, y0 + p.y
            if p.slant:
                _draw_slanted(img, p, x, y)
            else:
                draw.text((x, y), p.text, fill="black", font=p.font, anchor="la")
            if p.underline and p.text:
                offset, thickness = _underline(p.dots)
                base_y = round(y + p.font.getmetrics()[0] + offset)
                length = p.font.getlength(p.text)
                draw.rectangle((round(x), base_y, round(x + length), base_y + thickness - 1),
                               fill="black")


def _slant_pad(p: _Piece) -> int:
    """Room on the left for the substitute italic: descender sheared to the left and negative
    left side bearing."""
    left = p.font.getbbox(p.text, anchor="la")[0] if p.text else 0
    return math.ceil(_SLANT * p.font.getmetrics()[1]) + max(0, -left)


def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
    """Substitute italic: draw the piece individually and shear it to the right around the baseline."""
    ascent, descent = p.font.getmetrics()
    pad = _slant_pad(p)
    width = pad + int(p.font.getlength(p.text) + _SLANT * ascent) + 2
    mask = Image.new("L", (width, ascent + descent), 0)
    ImageDraw.Draw(mask).text((pad, 0), p.text, fill=255, font=p.font, anchor="la")
    sheared = mask.transform(mask.size, Image.Transform.AFFINE,
                             (1, _SLANT, -_SLANT * ascent, 0, 1, 0), Image.Resampling.BICUBIC)
    img.paste((0, 0, 0), (round(x) - pad, round(y)), sheared)
