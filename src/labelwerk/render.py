"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung.

Der Zeilensatz verallgemeinert Pillows ``multiline_text`` auf formatierte Textstücke:
gleicher Zeilenabstand (Unterkante von „A“ + 4 Punkte), gleiche Ausrichtungsrechnung –
reiner Text sieht dadurch pixelgleich aus wie früher.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageOps

from . import fonts
from .document import (ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS,
                       Document, Paragraph, Span, TextObject)
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


@dataclass
class RenderedObject:
    """Einzeln gerendertes Objekt in Druckpunkten, in Leserichtung.

    ``x``/``y``/``w``/``h``: Rahmen auf dem Etikett (Auswahl, Einrasten, Layout);
    ``base_pt``: wirksame Grundgröße.
    ``image``: Graustufen (L), weißer Grund, Tinte schwarz – deckt den Rahmen und die ganze
    Tinte ab (Anschnitt: Kantenglättung, Unterstreichung, Glyphen wie „J“ reichen etwas über
    den Rahmen); seine linke obere Ecke liegt bei ``x + image_dx``, ``y + image_dy``
    (``image_dx``/``image_dy`` ≤ 0).
    """
    image: Image.Image
    x: int
    y: int
    w: int
    h: int
    base_pt: float
    image_dx: int = 0
    image_dy: int = 0


def render_object(obj: TextObject, doc: Document, model: str = "QL-600") -> RenderedObject:
    """Ein Objekt einzeln rendern (Arbeitsfläche); Position bezogen auf das Etikett von ``doc``."""
    sheet = _sheet(doc, model)
    prep = _prepare(obj, sheet)
    width = height = 0
    if not obj.positioned:                     # mittig: braucht die Etikettgröße
        others = [_prepare(o, sheet) for o in doc.objects if o is not obj]
        width, height = _label_size(sheet, [prep, *others])
    return _finish(prep, sheet, width, height)


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).

    Objekte werden einzeln gerendert und in Listenreihenfolge (hinten → vorne) aufgeklebt;
    nur ihre Tinte deckt, über das Etikett ragende Teile werden abgeschnitten.
    Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
    wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
    Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
    """
    sheet = _sheet(doc, model)
    preps = [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]]
    width, height = _label_size(sheet, preps)
    return compose([_finish(prep, sheet, width, height) for prep in preps], (width, height),
                   doc.orientation)


def compose(rendered: list[RenderedObject], size: tuple[int, int],
            orientation: str = "vertical") -> Image.Image:
    """Druckbild aus einzeln gerenderten Objekten (``size`` = Etikett in Leserichtung).

    Die Arbeitsfläche zeigt dieselben Objektbilder – so bleibt Vorschau = Druck.
    """
    img = Image.new("RGB", size, "white")
    for obj in rendered:
        img.paste((0, 0, 0), (obj.x + obj.image_dx, obj.y + obj.image_dy),
                  ImageOps.invert(obj.image))
    return img.rotate(-90, expand=True) if orientation == "horizontal" else img


def label_size(doc: Document, model: str = "QL-600") -> tuple[int, int]:
    """Etikettgröße (Breite, Höhe) in Druckpunkten in Leserichtung – wie ``render_document``."""
    sheet = _sheet(doc, model)
    return _label_size(sheet, [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]])


def label_margins(doc: Document, model: str = "QL-600") -> tuple[int, int]:
    """Ränder (links/rechts, oben/unten) in Druckpunkten in Leserichtung."""
    sheet = _sheet(doc, model)
    return (sheet.margin, MARGIN) if sheet.horizontal else (MARGIN, sheet.margin)


# --- Etikett und Objekte ------------------------------------------------------------
@dataclass
class _Sheet:
    """Etikett in Druckpunkten; ``feed`` None = Länge automatisch (Endlosband)."""
    label_id: str
    horizontal: bool
    across: int                # quer zum Band (fest)
    feed: int | None           # in Bandlaufrichtung
    margin: int                # Rand in Bandlaufrichtung
    min_len: int
    max_len: int

    def room(self) -> tuple[int, int]:
        """Bedruckbarer Bereich (Breite, Höhe) in Leserichtung; automatische Länge: Höchstlänge."""
        across = self.across - 2 * MARGIN
        feed = (self.feed or self.max_len) - 2 * self.margin
        return (feed, across) if self.horizontal else (across, feed)


def _sheet(doc: Document, model: str) -> _Sheet:
    if doc.orientation not in ORIENTATIONS:
        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
    feed = label.height
    if feed is None and doc.length_mm is not None:
        feed = min(max(_dots(doc.length_mm), min_len), max_len)
    if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
        margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
    return _Sheet(doc.label_id, doc.orientation == "horizontal", label.width, feed, margin,
                  min_len, max_len)


def _dots(mm: float) -> int:
    return round(mm * DPI / 25.4)


@dataclass
class _Prepared:
    """Gemessenes Objekt: Grundgröße, Zeilen (an der breitesten Zeile ausgerichtet), Tintenbox."""
    obj: TextObject
    base: int
    lines: list
    box: tuple[int, int, int, int]
    frame: tuple[int, int] | None      # feste Rahmengröße positionierter Objekte (ungedreht)

    def size(self) -> tuple[int, int]:
        """Rahmengröße nach dem Drehen."""
        l, t, r, b = self.box
        w, h = self.frame or (r - l, b - t)
        return (h, w) if self.obj.rotation in (90, 270) else (w, h)


def _prepare(obj: TextObject, sheet: _Sheet) -> _Prepared:
    for para in obj.paragraphs:
        if para.align not in ALIGNMENTS:
            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
                             "rechts, Blocksatz (left, center, right, justify)")
    if obj.rotation not in ROTATIONS:
        raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
    max_w, max_h = sheet.room()
    if obj.rotation in (90, 270):
        max_w, max_h = max_h, max_w
    auto_start = max(10, sheet.across // 5)
    if obj.positioned and obj.fit:
        # Endlosband mit automatischer Länge: ohne eigenes Maß ist der Rahmen in
        # Bandlaufrichtung unbegrenzt – der Text wird nur quer eingepasst
        along = sheet.horizontal != (obj.rotation in (90, 270))   # Objektbreite längs zum Band
        open_w, open_h = (sheet.feed is None and along), (sheet.feed is None and not along)
        frame_w = _dots(obj.w_mm) if obj.w_mm is not None else None if open_w else max_w
        frame_h = _dots(obj.h_mm) if obj.h_mm is not None else None if open_h else max_h
        if obj.w_mm is not None or obj.h_mm is not None:
            auto_start = round(MAX_PT * PT)    # eigener Rahmen: Text füllt ihn aus
        base = _fit(obj, auto_start, _UNBOUNDED if frame_w is None else frame_w,
                    _UNBOUNDED if frame_h is None else frame_h, sheet.label_id)
        lines = _shape(obj, base)
        l, t, r, b = box = _block_box(lines)
        frame = (r - l if frame_w is None else frame_w, b - t if frame_h is None else frame_h)
        return _Prepared(obj, base, lines, box, frame)
    if obj.positioned and not obj.auto:
        base = round(obj.size_pt * PT)         # darf hinausragen – kein TextTooLarge
    else:
        base = _fit(obj, auto_start, max_w, max_h, sheet.label_id)
    lines = _shape(obj, base)
    return _Prepared(obj, base, lines, _block_box(lines), None)


def _label_size(sheet: _Sheet, preps: list[_Prepared]) -> tuple[int, int]:
    """Etikettgröße in Leserichtung; automatische Länge aus dem Platzbedarf der Objekte."""
    feed = sheet.feed
    if feed is None:
        needed = 0
        for prep in preps:
            w, h = prep.size()
            size = w if sheet.horizontal else h
            if prep.obj.positioned:
                start = prep.obj.x_mm if sheet.horizontal else prep.obj.y_mm
                needed = max(needed, _dots(start or 0) + size + sheet.margin)
            else:
                needed = max(needed, size + 2 * sheet.margin)
        feed = min(max(needed, sheet.min_len), sheet.max_len)
    return (feed, sheet.across) if sheet.horizontal else (sheet.across, feed)


def _finish(prep: _Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
    """Objektbild zeichnen und auf dem Etikett (``width`` × ``height``) platzieren.

    Gerechnet wird ungedreht in einer Fläche ``area`` (positioniert: der eigene Rahmen,
    sonst das Etikett – bei 90/270 mit getauschten Seiten); danach werden Bild, Rahmen und
    Bildlage mit der Fläche gedreht.
    """
    obj = prep.obj
    lines, (l, t, r, b) = prep.lines, prep.box
    turned = obj.rotation in (90, 270)
    if obj.positioned:
        if prep.frame is None:                 # Rahmen = Tintenbox des Textes
            frame = (0, 0, r - l, b - t)
            x0, y0 = -l, -t
        else:                                  # Text im festen Rahmen ausgerichtet
            frame = (0, 0, *prep.frame)
            x0, y0, lines = _align(obj, prep.base, lines, prep.box, 0, *prep.frame)
        area = frame[2:]
        origin = (_dots(obj.x_mm or 0), _dots(obj.y_mm or 0))
    else:                                      # mittig auf dem Etikett wie bisher
        area = (height, width) if turned else (width, height)
        # Innenrand der Textzeilen: Rand in Bandlaufrichtung, wenn sie längs zum Band laufen
        start = sheet.margin if sheet.horizontal != turned else MARGIN
        x0, y0, lines = _align(obj, prep.base, lines, prep.box, start, *area)
        fl, ft, fr, fb = _block_box(lines)
        frame = (x0 + fl, y0 + ft, fr - fl, fb - ft)
        origin = (0, 0)
    image, (ix, iy) = _paint(lines, x0 - frame[0], y0 - frame[1], *frame[2:],
                             at=(origin[0] + frame[0], origin[1] + frame[1]))
    picture = (frame[0] + ix, frame[1] + iy, image.width, image.height)
    if obj.rotation:
        image = image.transpose(_TRANSPOSE[obj.rotation])
        frame = _turn(frame, area, obj.rotation)
        picture = _turn(picture, area, obj.rotation)
    base_pt = obj.size_pt if not obj.auto else prep.base / PT
    return RenderedObject(image, origin[0] + frame[0], origin[1] + frame[1], frame[2], frame[3],
                          base_pt, picture[0] - frame[0], picture[1] - frame[1])


_TRANSPOSE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
              270: Image.Transpose.ROTATE_90}     # im Uhrzeigersinn
_UNBOUNDED = 1 << 30       # „unbegrenzt“ beim Einpassen


def _turn(rect: tuple[int, int, int, int], area: tuple[int, int],
          rotation: int) -> tuple[int, int, int, int]:
    """Rechteck (x, y, w, h) in einer Fläche ``area`` (Breite, Höhe) mit ihr im Uhrzeigersinn
    drehen – wie ``_TRANSPOSE`` die Pixel."""
    x, y, w, h = rect
    aw, ah = area
    if rotation == 90:
        return (ah - y - h, x, h, w)
    if rotation == 180:
        return (aw - x - w, ah - y - h, w, h)
    if rotation == 270:
        return (y, aw - x - w, h, w)
    return rect


def _align(obj: TextObject, base: int, lines: list, box: tuple[int, int, int, int],
           start: int, width: int, height: int) -> tuple[int, int, list]:
    """Ursprung des Textblocks in einem Rahmen ``width`` × ``height`` (Innenrand ``start``)."""
    l, t, r, b = box
    x0 = (width - (r - l)) // 2 - l
    if any(para.align != "center" for para in obj.paragraphs):
        # Absätze richten sich an der Rahmenbreite aus
        lines = _shape(obj, base, frame=width - 2 * start)
        fl, t, fr, b = _block_box(lines)
        x0 = min(max(start, -fl), width - fr)            # Tinte bleibt im Rahmen
    return x0, (height - (b - t)) // 2 - t, lines


def _paint(lines: list, x0: int, y0: int, width: int, height: int,
           at: tuple[int, int] = (0, 0)) -> tuple[Image.Image, tuple[int, int]]:
    """Zeilen in ein Graustufenbild zeichnen, Blockursprung bei (x0, y0) im Rahmen
    ``width`` × ``height``; ``at``: Lage des Rahmens auf dem Etikett.

    Das Bild deckt den Rahmen und die ganze Tinte ab (Anschnitt); zurück kommen das Bild
    und die Lage seiner linken oberen Ecke relativ zum Rahmen.
    """
    # Rand für Tinte außerhalb der Tintenbox; zugleich wird keine Zeichenkoordinate
    # negativ (Pillow rundet dort anders)
    pad = max((p.dots for pieces in lines for p in pieces), default=0)
    px, py = pad + max(0, -x0), pad + max(0, -y0)
    # round() rundet .5 zur geraden Zahl: Versatz zum Etikett gerade halten, damit
    # Unterstreichung und Ersatzkursive genau wie direkt auf dem Etikett gezeichnet landen
    px, py = px + (px - at[0]) % 2, py + (py - at[1]) % 2
    canvas = Image.new("L", (px + max(width, x0 + 1, 1) + pad, py + max(height, y0 + 1, 1) + pad),
                       255)
    _draw(canvas, lines, x0 + px, y0 + py)
    left, top, right, bottom = px, py, px + width, py + height
    ink = ImageOps.invert(canvas).getbbox()
    if ink is not None:
        left, top = min(left, ink[0]), min(top, ink[1])
        right, bottom = max(right, ink[2]), max(bottom, ink[3])
    return canvas.crop((left, top, right, bottom)), (left - px, top - py)


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
        # Meldung in der größten eingestellten Größe – die sieht der Nutzer im Editor
        largest = max((span.size_pt or obj.size_pt for para in obj.paragraphs
                       for span in para.spans), default=obj.size_pt)
        max_pt = int(best / PT * largest / obj.size_pt) if best else None
        if max_pt is not None and max_pt < MIN_PT:
            max_pt = None                      # kleiner als erlaubt: zählt als „passt nicht“
        raise TextTooLarge(largest, max_pt, label_id)
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
    img.paste(0, (round(x) - pad, round(y)), sheared)
