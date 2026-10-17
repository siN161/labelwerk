"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung.

Der Zeilensatz verallgemeinert Pillows ``multiline_text`` auf formatierte Textstücke:
gleicher Zeilenabstand (Unterkante von „A“ + 4 Punkte), gleiche Ausrichtungsrechnung –
reiner Text sieht dadurch pixelgleich aus wie früher.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import fonts
from .document import (ALIGNMENTS, MAX_MARGIN_MM, MIN_PT, ORIENTATIONS, Document, Paragraph,
                       Span, TextObject)
from .labels import DPI, get_label, length_limits

MARGIN = 12            # Punkte, ca. 1 mm
PT = DPI / 72          # Druckpunkte pro typografischem Punkt
REF_PT = 12.0          # Bezugsgröße für automatische Skalierung von Stücken mit eigener Größe
MIN_DOTS = 8           # kleinste Schrift in Druckpunkten
_LINE_GAP = 4          # wie Pillow multiline_text
_SLANT = 0.2           # Ersatzkursive: Scherung, wenn die Schrift keine echte Kursive hat


class TextTooLarge(ValueError):
    """Text passt bei fester Schriftgröße nicht aufs Etikett."""

    def __init__(self, size_pt: float, max_pt: float | None, label_id: str):
        if max_pt is None:                     # passt nicht einmal in der kleinsten Größe
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
    """Reinen Text rendern (Standardformatierung)."""
    obj = TextObject.plain(text, size_pt=size_pt, font_path=font_path)
    return render_document(Document(label_id, objects=[obj]))


def font_warnings(doc: Document) -> list[str]:
    """Hinweise zu ersetzten Schriften (je Familie einmal)."""
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
    if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
        margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
    obj = doc.objects[0] if doc.objects else TextObject("")
    for para in obj.paragraphs:
        if para.align not in ALIGNMENTS:
            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
                             "rechts, Blocksatz (left, center, right, justify)")

    across_room = across - 2 * MARGIN
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
        # Textrahmen über die volle Breite in Leserichtung: Absätze richten sich am Rahmen aus
        start = margin if horizontal else MARGIN
        frame = width - 2 * start
        lines = _shape(obj, base, frame=frame)
        fl, ft, fr, fb = _block_box(lines)
        x0 = min(max(start, -fl), width - fr)            # Tinte bleibt im Bild
        t, text_h = ft, fb - ft
    _draw(img, lines, x0, (height - text_h) // 2 - t)
    return img.rotate(-90, expand=True) if horizontal else img


# --- Schriftgrößen ----------------------------------------------------------
def _span_dots(obj: TextObject, span: Span, base: int) -> int:
    """Größe eines Stücks in Druckpunkten bei Grundgröße ``base`` (gemeinsam skaliert)."""
    if span.size_pt is None:
        return base
    ref = obj.size_pt or REF_PT
    return max(1, round(base * span.size_pt / ref))


def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str) -> int:
    """Grundgröße in Druckpunkten: fest, oder größte passende ≤ auto_start (Halbierung)."""
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
        max_pt = int(best / PT) if best else None
        if max_pt is not None and max_pt < MIN_PT:
            max_pt = None                      # kleiner als erlaubt: zählt als „passt nicht“
        raise TextTooLarge(obj.size_pt, max_pt, label_id)
    return best if best else MIN_DOTS          # passt nicht einmal klein – kleinste Größe zeigen


# --- Zeilensatz ---------------------------------------------------------------
@dataclass
class _Piece:
    text: str
    font: object
    dots: int
    underline: bool
    slant: bool                # Ersatzkursive
    x: float = 0.0             # links, relativ zum Block
    y: float = 0.0             # Oberkante (Ascender-Linie), relativ zum Block


def _font_for(obj: TextObject, span: Span, dots: int):
    if span.family is None and obj.font_path:
        return fonts.load(obj.font_path, dots), span.italic   # feste Datei: Ersatzkursive
    match = fonts.resolve(span.family, span.bold, span.italic)
    return fonts.load(match.path, dots), span.italic and not match.italic


def _shape(obj: TextObject, base: int, mode: str = "L",
           frame: float | None = None) -> list[list[_Piece]]:
    """Stücke mit Position im Block (mode „1“ zum Messen, „L“ zum Zeichnen – wie Pillow).

    Ohne ``frame`` richten sich die Zeilen an der breitesten Zeile aus; mit ``frame``
    (Rahmenbreite) an dieser Breite – Blocksatz dehnt weiter auf die breiteste Zeile."""
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
    # Unterlängen großer Stücke brauchen Platz unter der Zeile; bei einheitlicher Schrift 0
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
            p.y = top + ascent - p.font.getmetrics()[0]    # gemeinsame Grundlinie
        lines.append(pieces)
        top += spacing + max(p.font.getmetrics()[1] for p in pieces) - min_descent
    return lines


def _justify(pieces: list[_Piece], max_width: float, mode: str) -> list[_Piece]:
    """Wortabstände dehnen, bis die Zeile die Blockbreite füllt (ein Wort: linksbündig)."""
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
    """Tintenbox des Blocks (wie Pillow multiline_textbbox), auf ganze Punkte gerundet."""
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
    """(Abstand unter der Grundlinie, Stärke) in Druckpunkten."""
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
    """Platz links für die Ersatzkursive: nach links gescherte Unterlänge und negative
    linke Seitenpeilung."""
    left = p.font.getbbox(p.text, anchor="la")[0] if p.text else 0
    return math.ceil(_SLANT * p.font.getmetrics()[1]) + max(0, -left)


def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
    """Ersatzkursive: Stück einzeln zeichnen und um die Grundlinie nach rechts scheren."""
    ascent, descent = p.font.getmetrics()
    pad = _slant_pad(p)
    width = pad + int(p.font.getlength(p.text) + _SLANT * ascent) + 2
    mask = Image.new("L", (width, ascent + descent), 0)
    ImageDraw.Draw(mask).text((pad, 0), p.text, fill=255, font=p.font, anchor="la")
    sheared = mask.transform(mask.size, Image.Transform.AFFINE,
                             (1, _SLANT, -_SLANT * ascent, 0, 1, 0), Image.Resampling.BICUBIC)
    img.paste((0, 0, 0), (round(x) - pad, round(y)), sheared)
