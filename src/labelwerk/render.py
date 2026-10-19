"""Rendert Etiketteninhalte als Bild in exakter Druckauflösung.

Der Zeilensatz verallgemeinert Pillows ``multiline_text`` auf formatierte Textstücke:
gleicher Zeilenabstand (Unterkante von „A“ + 4 Punkte), gleiche Ausrichtungsrechnung –
reiner Text sieht dadurch pixelgleich aus wie früher.
Das Ergebnis (``TextLayout``) zeichnet das Rendern; dieselben Zahlen liefern der
Arbeitsfläche Schreibmarke, Treffer und Markierung.
Bild-Objekte werden auf ihren Rahmen skaliert und in Schwarz/Weiß umgewandelt
(``imaging.to_layers``); Barcodes zeichnet ``barcodes.draw`` in ganzen Druckpunkten.
"""
from __future__ import annotations

import copy
import io
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property, lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageOps

from . import barcodes, fonts, imaging
from .document import (ALIGNMENTS, COLORS, FRAME_LINE_MM, FRAME_STYLES, MAX_FRAME_MM,
                       MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS, BarcodeObject,
                       Document, Frame, ImageObject, Paragraph, Span, TextObject)
from .labels import DPI, get_label, length_limits
from .printers import capabilities

MARGIN = 12            # Punkte, ca. 1 mm
PT = DPI / 72          # Druckpunkte pro typografischem Punkt bei 300 dpi (Brother); sonst dpi / 72
REF_PT = 12.0          # Bezugsgröße für automatische Skalierung von Stücken mit eigener Größe
MIN_DOTS = 8           # kleinste Schrift in Druckpunkten
_LINE_GAP = 4          # wie Pillow multiline_text
_SLANT = 0.2           # Ersatzkursive: Scherung, wenn die Schrift keine echte Kursive hat
FRAME_RADIUS_MM = 2.0  # Eckradius abgerundeter Rahmen (höchstens ¼ der kürzeren Seite)
FRAME_CORNER_MM = 4.0  # Schenkel bei „nur Ecken“ (höchstens ¼ der kürzeren Seite)
INK = {"black": (0, 0, 0), "red": (255, 0, 0)}   # Druckfarben im Druckbild (brother_ql trennt Rot)


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
        if not isinstance(obj, TextObject):
            continue
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
    ``base_pt``: wirksame Grundgröße (Bild-Objekte, Barcodes: 0).
    ``image``: Graustufen (L), weißer Grund, Tinte schwarz – deckt den Rahmen und die ganze
    Tinte ab (Anschnitt: Kantenglättung, Unterstreichung, Glyphen wie „J“ reichen etwas über
    den Rahmen); seine linke obere Ecke liegt bei ``x + image_dx``, ``y + image_dy``
    (``image_dx``/``image_dy`` ≤ 0; Bild-Objekte und Barcodes: genau der Rahmen, 0).
    ``layout``: der Zeilensatz, aus dem das Bild gezeichnet wurde (Schreibmarke, Treffer);
    None bei Bild-Objekten und Barcodes. ``color``: Druckfarbe der Tinte (``INK``) – Rot nur auf
    Etiketten Rot/Schwarz, sonst schwarz.
    """
    image: Image.Image
    x: int
    y: int
    w: int
    h: int
    base_pt: float
    image_dx: int = 0
    image_dy: int = 0
    layout: TextLayout | None = field(default=None, compare=False, repr=False)
    color: str = "black"
    dpi: int = DPI                     # Auflösung des Etiketts (mm ↔ Druckpunkte)


def render_object(obj: TextObject | ImageObject | BarcodeObject, doc: Document,
                  model: str = "QL-600") -> RenderedObject:
    """Ein Objekt einzeln rendern (Arbeitsfläche); Position bezogen auf das Etikett von ``doc``."""
    return _finish(*_measure(obj, doc, model))


def text_layout(obj: TextObject, doc: Document, model: str = "QL-600") -> TextLayout:
    """Zeilensatz eines Objekts ohne Bild – derselbe, den ``render_object`` zeichnet
    (``RenderedObject.layout``)."""
    if not isinstance(obj, TextObject):
        raise TypeError("Einen Zeilensatz gibt es nur für Text-Objekte.")
    return _place(*_measure(obj, doc, model))[0]


def _measure(obj: TextObject | ImageObject | BarcodeObject, doc: Document,
             model: str) -> tuple[Prepared, _Sheet, int, int]:
    """Objekt messen; Etikettgröße nur für ein Objekt ohne Position (mittig), sonst 0."""
    sheet = _sheet(doc, model)
    prep = _prepare(obj, sheet)
    width = height = 0
    if not obj.positioned:                     # mittig: braucht die Etikettgröße
        others = [_prepare(o, sheet) for o in doc.objects if o is not obj]
        width, height = _label_size(sheet, [prep, *others])
    return prep, sheet, width, height


def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
    """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).

    Objekte werden einzeln gerendert und in Listenreihenfolge (hinten → vorne) aufgeklebt;
    nur ihre Tinte deckt, über das Etikett ragende Teile werden abgeschnitten.
    Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
    wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
    Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
    """
    sheet = _sheet(doc, model)
    _check_room(sheet)
    preps = [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]]
    width, height = _label_size(sheet, preps)
    return compose([_finish(prep, sheet, width, height) for prep in preps], (width, height),
                   doc.orientation, _frame_mask(sheet, width, height))


def compose(rendered: list[RenderedObject], size: tuple[int, int],
            orientation: str = "vertical", frame: Image.Image | None = None) -> Image.Image:
    """Druckbild aus einzeln gerenderten Objekten (``size`` = Etikett in Leserichtung);
    ``frame``: Maske des Zierrahmens (``frame_mask``), liegt unter den Objekten.

    Die Arbeitsfläche zeigt dieselben Objektbilder – so bleibt Vorschau = Druck.
    """
    img = Image.new("RGB", size, "white")
    if frame is not None:
        img.paste((0, 0, 0), (0, 0), frame)
    for obj in rendered:
        img.paste(INK[obj.color], (obj.x + obj.image_dx, obj.y + obj.image_dy),
                  ImageOps.invert(obj.image))
    return img.rotate(-90, expand=True) if orientation == "horizontal" else img


def label_size(doc: Document, model: str = "QL-600",
               prepared: list[Prepared] | None = None) -> tuple[int, int]:
    """Etikettgröße (Breite, Höhe) in Druckpunkten in Leserichtung – wie ``render_document``.

    ``prepared``: schon gemessene Objekte (``prepare_object``, je Objekt in ``doc``) – dann
    wird nichts neu gemessen.
    """
    sheet = _sheet(doc, model)
    if prepared is None or not doc.objects:
        prepared = [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]]
    return _label_size(sheet, prepared)


def prepare_object(obj: TextObject | ImageObject | BarcodeObject, doc: Document,
                   model: str = "QL-600") -> Prepared:
    """Objekt messen (Grundgröße, Zeilen, Rahmengröße) – unabhängig von der Etikettgröße.

    Zusammen mit ``label_size(..., prepared=)`` und ``finish_object`` rendert die
    Arbeitsfläche nur geänderte Objekte neu (``render_object`` misst alle anderen mit).
    """
    return _prepare(obj, _sheet(doc, model))


def finish_object(prep: Prepared, doc: Document, size: tuple[int, int],
                  model: str = "QL-600") -> RenderedObject:
    """Gemessenes Objekt auf dem Etikett ``size`` (wie ``label_size``) rendern – dasselbe
    Ergebnis wie ``render_object``."""
    return _finish(prep, _sheet(doc, model), *size)


def frame_mask(doc: Document, model: str = "QL-600",
               size: tuple[int, int] | None = None) -> Image.Image | None:
    """Zierrahmen als Maske (Modus „L“, 255 = Tinte) in Leserichtung; None ohne Rahmen."""
    if doc.frame is None:
        return None
    return _frame_mask(_sheet(doc, model), *(size if size is not None else label_size(doc, model)))


def frame_box(doc: Document, model: str = "QL-600",
              size: tuple[int, int] | None = None) -> tuple[int, int, int, int] | None:
    """Innenraum des Rahmens (x, y, Breite, Höhe) in Druckpunkten in Leserichtung – dort steht
    automatisch gesetzter Text; None ohne Rahmen."""
    if doc.frame is None:
        return None
    sheet = _sheet(doc, model)
    width, height = size if size is not None else label_size(doc, model)
    ix, iy = sheet.inset()
    return ix, iy, width - 2 * ix, height - 2 * iy


@dataclass
class Rendered:
    """Ergebnis von ``Renderer.render``: Etikettgröße (Druckpunkte in Leserichtung), die
    einzelnen Objektbilder (je Objekt in ``doc.objects``) und das Druckbild daraus."""
    size: tuple[int, int]
    objects: list[RenderedObject]
    image: Image.Image
    frame: Image.Image | None = None       # Zierrahmen als Maske (``frame_mask``), Arbeitsfläche
    errors: list[tuple[int, str]] = field(default_factory=list)   # Platzhalter: (Index, Meldung)


@dataclass
class _Cached:
    """Gemessenes und gerendertes Objekt samt Stand, aus dem es entstand."""
    obj: TextObject | ImageObject | BarcodeObject  # hält das Objekt fest (id bleibt vergeben)
    snapshot: TextObject | ImageObject | BarcodeObject  # Bilder: PNG-Bytes geteilt, nicht kopiert
    context: tuple
    prepared: Prepared
    size: tuple | None = None                  # Etikettgröße des Bilds (None = mit Position)
    rendered: RenderedObject | None = None


class Renderer:
    """Rendert ein Dokument wiederholt und dabei nur, was sich geändert hat (Arbeitsfläche).

    Gemessen wird ein Objekt nur, wenn es selbst oder sein Kontext (Modell, Etikett,
    Ausrichtung, Rand, Länge) sich ändert; gezeichnet zusätzlich, wenn sich bei einem Objekt
    ohne Position (steht mittig) die Etikettgröße ändert. Das Druckbild wird nur neu
    zusammengesetzt, wenn sich ein Objektbild oder die Größe ändert. Ergebnis wie
    ``render_document`` – Vorschau = Druck.

    Schlüssel ist der ganze Objektinhalt (Schnappschuss) – bei Bildern also auch alle
    Einstellungen. Das bleibt billig: ``copy.deepcopy`` teilt unveränderliche PNG-Bytes, und
    der Vergleich derselben Bytes ist ein Identitätsvergleich. Ändert sich nur die
    Umwandlung (Schwelle, Foto, Umkehren), kommt das skalierte Bild aus ``_scaled_source``.
    """

    def __init__(self):
        self._cache: dict[int, _Cached] = {}
        self._composed: tuple = (None, [], None, None)   # Druckbild und woraus es entstand
        self._frame: tuple = (None, None)                # Rahmen-Maske und wofür

    def render(self, doc: Document, model: str = "QL-600",
               placeholders: bool = False) -> Rendered:
        """Dokument rendern; ``ValueError`` (z. B. ``TextTooLarge``) lässt den Cache stehen.

        ``placeholders`` (Arbeitsfläche): Ein Barcode, der sich nicht kodieren lässt (Inhalt halb
        getippt, Platzhalter), wird zum schraffierten Platzhalter statt eines Fehlers – er bleibt
        sichtbar und wählbar; ``Rendered.errors`` nennt ihn. Das Bild ist dann kein Druckbild."""
        _check_room(_sheet(doc, model))
        entries = self._prepare_all(doc, model, placeholders)
        size = label_size(doc, model, prepared=[e.prepared for e in entries])
        objects = self._draw(entries, doc, model, size)
        frame = self._frame_mask(doc, model, size)
        errors = [(i, e.prepared.error) for i, e in enumerate(entries) if e.prepared.error]
        return Rendered(size, objects, self._compose(objects, size, doc.orientation, frame), frame,
                        errors)

    def _frame_mask(self, doc: Document, model: str, size: tuple[int, int]) -> Image.Image | None:
        """Rahmen-Maske – neu nur, wenn sich Rahmen oder Etikett ändern."""
        key = (size, model, doc.label_id, doc.orientation, doc.margin_mm, doc.frame)
        if key != self._frame[0]:
            self._frame = (key, frame_mask(doc, model, size))
        return self._frame[1]

    def _prepare_all(self, doc: Document, model: str, placeholders: bool) -> list[_Cached]:
        """Objekte messen; unveränderte kommen aus dem Cache."""
        context = (model, doc.label_id, doc.orientation, doc.margin_mm, doc.length_mm,
                   doc.frame, _svg_generation, placeholders)
        cache: dict[int, _Cached] = {}
        for obj in doc.objects:
            entry = self._cache.get(id(obj))
            if (entry is None or entry.obj is not obj or entry.context != context
                    or entry.snapshot != obj):
                try:
                    prepared = prepare_object(obj, doc, model)
                except barcodes.BarcodeError as e:
                    if not placeholders:
                        raise
                    dpi = get_label(doc.label_id).dpi
                    frame = barcodes.placeholder_size(obj, dpi)
                    prepared = Prepared(obj, 0, [], (0, 0, *frame), frame, str(e), dpi)
                entry = _Cached(obj, copy.deepcopy(obj), context, prepared)
            cache[id(obj)] = entry
        self._cache = cache
        return [cache[id(obj)] for obj in doc.objects]

    @staticmethod
    def _draw(entries: list[_Cached], doc: Document, model: str,
              size: tuple[int, int]) -> list[RenderedObject]:
        """Gemessene Objekte zeichnen; ein Objekt ohne Position steht mittig und wird deshalb
        auch neu gezeichnet, wenn sich die Etikettgröße ändert."""
        for entry in entries:
            key = None if entry.obj.positioned else size
            if entry.rendered is None or entry.size != key:
                entry.rendered = finish_object(entry.prepared, doc, size, model)
                entry.size = key
        return [entry.rendered for entry in entries]

    def _compose(self, objects: list[RenderedObject], size: tuple[int, int],
                 orientation: str, frame: Image.Image | None) -> Image.Image:
        """Druckbild – unverändert, solange dieselben Objektbilder und derselbe Rahmen auf
        derselben Größe liegen."""
        key = (size, orientation)
        if (key != self._composed[0] or frame is not self._composed[3]
                or len(objects) != len(self._composed[1])
                or any(a is not b for a, b in zip(objects, self._composed[1]))):
            self._composed = (key, list(objects), compose(objects, size, orientation, frame),
                              frame)
        return self._composed[2]


def label_margins(doc: Document, model: str = "QL-600") -> tuple[int, int]:
    """Ränder (links/rechts, oben/unten) in Druckpunkten in Leserichtung."""
    return _sheet(doc, model).margins()


# --- Etikett und Objekte ------------------------------------------------------------
@dataclass
class _Sheet:
    """Etikett in Druckpunkten; ``feed`` None = Länge automatisch (Endlosband)."""
    label_id: str
    horizontal: bool
    across: int                # quer zum Band (fest)
    feed: int | None           # in Bandlaufrichtung
    margin: int                # Rand in Bandlaufrichtung
    side: int                  # Rand quer zum Band (derselbe Wert, auf schmalem Band begrenzt)
    min_len: int
    max_len: int
    frame: Frame | None = None
    round: bool = False        # rundes Etikett: Rahmen ist ein Kreis
    red: bool = False          # Etikett Rot/Schwarz auf einem Zweifarb-Modell: Rot druckt rot
    dpi: int = DPI             # Auflösung des Etiketts

    def dots(self, mm: float) -> int:
        return _dots(mm, self.dpi)

    @property
    def pt(self) -> float:
        """Druckpunkte je typografischem Punkt."""
        return self.dpi / 72

    def margins(self) -> tuple[int, int]:
        """Ränder (links/rechts, oben/unten) in Leserichtung."""
        return (self.margin, self.side) if self.horizontal else (self.side, self.margin)

    def inset(self) -> tuple[int, int]:
        """Abstand des Innenraums vom Etikettrand (links/rechts, oben/unten) in Leserichtung:
        die Ränder, mit Rahmen zusätzlich Abstand, Linie und Innenabstand (rund: Quadrat im
        Kreis)."""
        mx, my = self.margins()
        if self.frame is None:
            return mx, my
        if self.round:
            inset = (self.across - _circle_room(self)) // 2
            return inset, inset
        band = _band(self.frame, self.dpi)
        inner = band + self.dots(self.frame.padding_mm)
        if self.frame.rounded:          # Ecken des Innenraums bleiben vor den Bögen (auch ohne Abstand)
            r = self.dots(FRAME_RADIUS_MM)  # größter Radius – kleinere Bögen ragen weniger weit
            inner = max(inner, math.ceil(r - (r - band) / math.sqrt(2)) + 1)
        pad = self.dots(self.frame.inset_mm) + inner
        return mx + pad, my + pad

    def room(self, inner: bool = True) -> tuple[int, int]:
        """Bedruckbarer Bereich (Breite, Höhe) in Leserichtung; automatische Länge: Höchstlänge.
        ``inner``: mit Rahmen nur sein Innenraum (für automatisch gesetzten Text)."""
        width, height = self.across, self.feed or self.max_len
        if self.horizontal:
            width, height = height, width
        ix, iy = self.inset() if inner else self.margins()
        return width - 2 * ix, height - 2 * iy


def _sheet(doc: Document, model: str) -> _Sheet:
    if doc.orientation not in ORIENTATIONS:
        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
    label = get_label(doc.label_id)
    min_len, max_len = length_limits(model)
    # Rand ringsum ab Papierkante: der Streifen, den der Drucker dort nicht bedruckt, zählt mit
    margin = _dots(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM), label.dpi)
    side = max(0, margin - (label.total_width - label.width) // 2)
    if label.height is not None and label.total_height is not None:
        margin = max(0, margin - (label.total_height - label.height) // 2)
    feed = label.height
    if feed is None and doc.length_mm is not None:
        feed = min(max(_dots(doc.length_mm, label.dpi), min_len), max_len)
    keep = round(MARGIN * label.dpi / DPI)                          # Rand darf nicht alles
    side = min(side, max(0, (label.width - 2 * keep) // 2))        # aufbrauchen (quer, feste
    if feed is not None:                                            # Länge): 1 mm bleibt
        margin = min(margin, max(0, (feed - 2 * keep) // 2))
    if doc.frame is not None:
        _check_frame(doc.frame)
    return _Sheet(doc.label_id, doc.orientation == "horizontal", label.width, feed, margin, side,
                  min_len, max_len, doc.frame, label.shape == "round",
                  label.two_color and capabilities(model).two_color, label.dpi)


FRAME_TOO_BIG = "Rahmen passt nicht aufs Etikett – Abstand, Strichstärke oder Innenabstand verkleinern"


def _check_room(sheet: _Sheet) -> None:
    """Rahmen ohne Innenraum → Meldung. Nur beim Rendern geprüft – Ränder und bedruckbarer
    Bereich bleiben auch dann bestimmbar (die GUI fragt sie außerhalb des Renderns ab)."""
    if sheet.frame is not None and min(sheet.room()) <= 0:
        raise ValueError(FRAME_TOO_BIG)


def _dots(mm: float, dpi: int = DPI) -> int:
    return round(mm * dpi / 25.4)


@dataclass
class Prepared:
    """Gemessenes Objekt: Grundgröße, Zeilen (an der breitesten Zeile ausgerichtet), Tintenbox.
    Bild-Objekte und Barcodes: keine Zeilen, Tintenbox = Rahmen."""
    obj: TextObject | ImageObject | BarcodeObject
    base: int
    lines: list
    box: tuple[int, int, int, int]
    frame: tuple[int, int] | None      # feste Rahmengröße positionierter Objekte (ungedreht)
    error: str | None = None           # Barcode als Platzhalter (``Renderer``, Arbeitsfläche)
    dpi: int = DPI                     # Auflösung des Etiketts

    def size(self) -> tuple[int, int]:
        """Rahmengröße nach dem Drehen."""
        l, t, r, b = self.box
        w, h = self.frame or (r - l, b - t)
        return (h, w) if self.obj.rotation in (90, 270) else (w, h)


def _prepare(obj: TextObject | ImageObject | BarcodeObject, sheet: _Sheet) -> Prepared:
    if obj.color not in COLORS:
        raise ValueError(f"Unbekannte Farbe {obj.color!r} – erlaubt: schwarz, rot (black, red)")
    if isinstance(obj, ImageObject):
        return _prepare_image(obj, sheet.dpi)
    if isinstance(obj, BarcodeObject):
        frame = barcodes.size(obj, sheet.dpi)
        return Prepared(obj, 0, [], (0, 0, *frame), frame, dpi=sheet.dpi)
    for para in obj.paragraphs:
        if para.align not in ALIGNMENTS:
            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
                             "rechts, Blocksatz (left, center, right, justify)")
    if obj.rotation not in ROTATIONS:
        raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
    max_w, max_h = sheet.room(inner=not obj.positioned)   # frei platziert: Rahmen gilt nicht
    if obj.rotation in (90, 270):
        max_w, max_h = max_h, max_w
    auto_start = max(10, sheet.across // 5)
    if obj.positioned and obj.fit:
        # Endlosband mit automatischer Länge: ohne eigenes Maß ist der Rahmen in
        # Bandlaufrichtung unbegrenzt – der Text wird nur quer eingepasst
        along = sheet.horizontal != (obj.rotation in (90, 270))   # Objektbreite längs zum Band
        open_w, open_h = (sheet.feed is None and along), (sheet.feed is None and not along)
        frame_w = sheet.dots(obj.w_mm) if obj.w_mm is not None else None if open_w else max_w
        frame_h = sheet.dots(obj.h_mm) if obj.h_mm is not None else None if open_h else max_h
        if obj.w_mm is not None or obj.h_mm is not None:
            auto_start = round(MAX_PT * sheet.pt)    # eigener Rahmen: Text füllt ihn aus
        base = _fit(obj, auto_start, _UNBOUNDED if frame_w is None else frame_w,
                    _UNBOUNDED if frame_h is None else frame_h, sheet.label_id, sheet.dpi)
        lines = _shape(obj, base)
        l, t, r, b = box = _block_box(lines)
        frame = (r - l if frame_w is None else frame_w, b - t if frame_h is None else frame_h)
        return Prepared(obj, base, lines, box, frame, dpi=sheet.dpi)
    if obj.positioned and not obj.auto:
        base = round(obj.size_pt * sheet.pt)   # darf hinausragen – kein TextTooLarge
    else:
        base = _fit(obj, auto_start, max_w, max_h, sheet.label_id, sheet.dpi)
    lines = _shape(obj, base)
    return Prepared(obj, base, lines, _block_box(lines), None, dpi=sheet.dpi)


def _label_size(sheet: _Sheet, preps: list[Prepared]) -> tuple[int, int]:
    """Etikettgröße in Leserichtung; automatische Länge aus dem Platzbedarf der Objekte."""
    feed = sheet.feed
    if feed is None:
        ix, iy = sheet.inset()
        along = ix if sheet.horizontal else iy     # Rand (+ Rahmen) in Bandlaufrichtung
        needed = 0
        for prep in preps:
            if prep.obj.positioned and prep.obj.is_empty():
                continue                       # leerer Rahmen druckt nicht, verlängert nicht
            w, h = prep.size()
            size = w if sheet.horizontal else h
            if prep.obj.positioned:
                start = prep.obj.x_mm if sheet.horizontal else prep.obj.y_mm
                needed = max(needed, sheet.dots(start or 0) + size + along)
            else:
                needed = max(needed, size + 2 * along)
        if sheet.frame is not None:            # im Rahmen bleibt immer Platz (kein Innenraum ≤ 0)
            needed = max(needed, 2 * along + 1)
        feed = min(max(needed, sheet.min_len), sheet.max_len)
    return (feed, sheet.across) if sheet.horizontal else (sheet.across, feed)


def _place(prep: Prepared, sheet: _Sheet, width: int, height: int
           ) -> tuple[TextLayout, tuple[int, int, int, int], tuple[int, int], tuple[int, int]]:
    """Zeilensatz im Rahmen auf dem Etikett (``width`` × ``height``).

    Gerechnet wird ungedreht in einer Fläche ``area`` (positioniert: der eigene Rahmen,
    sonst das Etikett – bei 90/270 mit getauschten Seiten). Zurück kommen der Zeilensatz
    (relativ zum Rahmen), der Rahmen (x, y, w, h) in der Fläche, die Fläche (Breite, Höhe)
    und die Lage der Fläche auf dem Etikett.
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
        origin = (sheet.dots(obj.x_mm or 0), sheet.dots(obj.y_mm or 0))
    else:                                      # mittig auf dem Etikett wie bisher
        area = (height, width) if turned else (width, height)
        # Innenrand der Textzeilen: Rand (mit Rahmen: Innenraum) in Richtung der Zeilen
        ix, iy = sheet.inset()
        start = iy if turned else ix
        x0, y0, lines = _align(obj, prep.base, lines, prep.box, start, *area)
        fl, ft, fr, fb = _block_box(lines)
        frame = (x0 + fl, y0 + ft, fr - fl, fb - ft)
        origin = (0, 0)
    text = TextLayout([para.text for para in obj.paragraphs], lines, x0 - frame[0],
                      y0 - frame[1], frame[2], frame[3])
    return text, frame, area, origin


def _finish(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
    """Objekt zeichnen und platzieren (``_finish_shape``); Rot nur auf Etiketten Rot/Schwarz."""
    rendered = _finish_shape(prep, sheet, width, height)
    if prep.obj.color == "red" and sheet.red:
        rendered.color = "red"
    return rendered


def _finish_shape(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
    """Objektbild aus dem Zeilensatz (``_place``) zeichnen und auf dem Etikett platzieren;
    Bild, Rahmen und Bildlage werden mit der Fläche gedreht."""
    obj = prep.obj
    if isinstance(obj, ImageObject):
        return _finish_image(prep)
    if isinstance(obj, BarcodeObject):
        return _finish_barcode(prep)
    text, frame, area, origin = _place(prep, sheet, width, height)
    image, (ix, iy) = _paint(text.pieces, text.x0, text.y0, *frame[2:],
                             at=(origin[0] + frame[0], origin[1] + frame[1]))
    picture = (frame[0] + ix, frame[1] + iy, image.width, image.height)
    if obj.rotation:
        image = image.transpose(_TRANSPOSE[obj.rotation])
        frame = _turn(frame, area, obj.rotation)
        picture = _turn(picture, area, obj.rotation)
    base_pt = obj.size_pt if not obj.auto else prep.base / sheet.pt
    return RenderedObject(image, origin[0] + frame[0], origin[1] + frame[1], frame[2], frame[3],
                          base_pt, picture[0] - frame[0], picture[1] - frame[1], text,
                          dpi=sheet.dpi)


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


# --- Bild-Objekte -------------------------------------------------------------------
def _prepare_image(obj: ImageObject, dpi: int = DPI) -> Prepared:
    """Bild-Objekt prüfen und messen: Rahmen in Druckpunkten (ungedreht) aus ``w_mm``/``h_mm``."""
    if obj.rotation not in ROTATIONS:
        raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
    imaging.check(obj.mode, obj.threshold)
    if not (obj.w_mm > 0 and obj.h_mm > 0):
        raise ValueError(f"Größe des Bilds muss größer als 0 sein, nicht "
                         f"{obj.w_mm:g} × {obj.h_mm:g} mm.")
    frame = (max(1, _dots(obj.w_mm, dpi)), max(1, _dots(obj.h_mm, dpi)))
    return Prepared(obj, 0, [], (0, 0, *frame), frame, dpi=dpi)


def _finish_image(prep: Prepared) -> RenderedObject:
    """Bild auf den Rahmen skalieren, in Schwarz/Weiß umwandeln und drehen (wie Text).

    Mit ``keep_ratio`` wird nicht verzerrt: Passt das Seitenverhältnis des Rahmens nicht,
    steht das Bild eingepasst in seiner Mitte (der Rest bleibt Papier, auch mit ``invert``).
    """
    obj = prep.obj
    w, h = prep.frame
    crop = tuple(obj.crop) if obj.crop is not None else None
    if obj.svg is not None and _svg_rasterizer is not None:
        picture = _vector_source(obj.svg, obj.png, crop, (w, h), obj.keep_ratio)
    else:
        picture = _scaled_source(obj.png, crop, (w, h), obj.keep_ratio)
    black = imaging.to_layers(picture, obj.mode, obj.threshold, obj.invert)["black"]
    image = Image.new("L", (w, h), 255)
    image.paste(black.convert("L"), ((w - picture.width) // 2, (h - picture.height) // 2))
    frame = (0, 0, w, h)
    if obj.rotation:
        image = image.transpose(_TRANSPOSE[obj.rotation])
        frame = _turn(frame, (w, h), obj.rotation)
    return RenderedObject(image, _dots(obj.x_mm, prep.dpi), _dots(obj.y_mm, prep.dpi), frame[2],
                          frame[3], 0.0, dpi=prep.dpi)


def _finish_barcode(prep: Prepared) -> RenderedObject:
    """Barcode zeichnen (ganze Druckpunkte, ``barcodes.draw``; mit Fehler den Platzhalter) und
    drehen wie ein Bild."""
    obj = prep.obj
    image = (barcodes.draw(obj, prep.dpi) if prep.error is None
             else barcodes.placeholder(*prep.frame))
    frame = (0, 0, *image.size)
    if obj.rotation:
        frame = _turn(frame, image.size, obj.rotation)
        image = image.transpose(_TRANSPOSE[obj.rotation])
    return RenderedObject(image, _dots(obj.x_mm, prep.dpi), _dots(obj.y_mm, prep.dpi), frame[2],
                          frame[3], 0.0, dpi=prep.dpi)


# Vektorbilder: der Kern rastert nicht selbst (Qt-frei) – die GUI meldet eine Funktion an
SvgRasterizer = Callable[[bytes, tuple[int, int], tuple[int, int, int, int]], Image.Image]
_svg_rasterizer: SvgRasterizer | None = None
_svg_generation = 0          # zählt Wechsel der Raster-Funktion (Kontext im Renderer-Cache)
MAX_SHEET = 4_000_000        # Pixel je Seite: größer ließe Qt Formen still weg


def set_svg_rasterizer(rasterizer: SvgRasterizer | None) -> None:
    """Raster-Funktion für Vektorbilder (``ImageObject.svg``): ``fn(svg, size, region)``
    rastert das ganze Blatt auf ``size`` (w, h) Pixel und liefert davon nur ``region``
    (x, y, w, h) als RGB-Bild auf Weiß. None: Vektorbilder zeigen ihre Vorschau-PNG."""
    global _svg_rasterizer, _svg_generation
    if rasterizer is not _svg_rasterizer:
        _svg_rasterizer = rasterizer
        _svg_generation += 1
        _vector_source.cache_clear()


@lru_cache(maxsize=8)
def _vector_source(svg: bytes, png: bytes, crop: tuple[int, int, int, int] | None,
                   size: tuple[int, int], keep_ratio: bool) -> Image.Image:
    """Wie ``_scaled_source``, aber neu gerastert statt skaliert: das Blatt so groß, dass der
    Ausschnitt (Pixel der Vorschau-PNG) genau ``size`` füllt – scharf in jeder Größe."""
    with Image.open(io.BytesIO(png), formats=["PNG"]) as img:     # liest nur den Kopf
        sheet = img.size
    l, t, r, b = crop if crop is not None else (0, 0, *sheet)
    _check_crop((l, t, r, b), sheet)
    w, h = _fitted((r - l, b - t), size, keep_ratio)
    fx, fy = w / (r - l), h / (b - t)
    full = (round(sheet[0] * fx), round(sheet[1] * fy))
    if max(full) > MAX_SHEET:
        raise ValueError("Vektorbild: Ausschnitt zu stark vergrößert – bitte kleiner skalieren "
                         "oder den Zuschnitt ausschalten.")
    picture = _svg_rasterizer(svg, full, (round(l * fx), round(t * fy), w, h))
    if picture.size != (w, h):
        raise ValueError(f"Vektorbild konnte nicht gerastert werden ({picture.width} × "
                         f"{picture.height} statt {w} × {h} Pixel).")
    return picture if picture.mode == "RGB" else picture.convert("RGB")


def _check_crop(crop: tuple[int, int, int, int], size: tuple[int, int]) -> None:
    """Ausschnitt (l, t, r, b) muss eine Fläche im Bild der Größe ``size`` sein."""
    l, t, r, b = crop
    if not (0 <= l < r <= size[0] and 0 <= t < b <= size[1]):
        raise ValueError(f"Ausschnitt {crop} liegt nicht im Bild "
                         f"({size[0]} × {size[1]} Pixel).")


def _fitted(source: tuple[int, int], size: tuple[int, int], keep_ratio: bool) -> tuple[int, int]:
    """Zielgröße: ``size``, mit ``keep_ratio`` ins Seitenverhältnis von ``source`` eingepasst
    (bis 1 Pixel Rundung füllt es den Rahmen)."""
    w, h = size
    if keep_ratio:
        scale = min(w / source[0], h / source[1])
        fitted = (max(1, round(source[0] * scale)), max(1, round(source[1] * scale)))
        if abs(fitted[0] - w) > 1 or abs(fitted[1] - h) > 1:   # sonst nur Rundung: füllen
            w, h = fitted
    return w, h


@lru_cache(maxsize=2)
def _source(png: bytes, crop: tuple[int, int, int, int] | None) -> Image.Image:
    """Original (RGB), auf den Ausschnitt zugeschnitten.

    Gecacht, damit Ziehen am Anfasser nicht jedes Mal dekodiert: Python merkt sich den Hash
    eines ``bytes``-Objekts, der Schlüssel kostet nach dem ersten Mal fast nichts.
    Das Ergebnis wird geteilt und darf nicht verändert werden.
    """
    with Image.open(io.BytesIO(png), formats=["PNG"]) as img:
        img = img.convert("RGB")
    if crop is not None:
        _check_crop(crop, img.size)
        img = img.crop(crop)
    return img


@lru_cache(maxsize=8)
def _scaled_source(png: bytes, crop: tuple[int, int, int, int] | None, size: tuple[int, int],
                   keep_ratio: bool) -> Image.Image:
    """Ausschnitt auf ``size`` skaliert (Lanczos); mit ``keep_ratio`` eingepasst, nicht
    verzerrt. Gecacht: Schwelle, Foto und Umkehren ändern nur die Umwandlung danach."""
    src = _source(png, crop)
    w, h = _fitted(src.size, size, keep_ratio)
    if src.size == (w, h):
        return src
    # reducing_gap: stark verkleinert erst ganzzahlig reduzieren (schnell), dann Lanczos;
    # vergrößert und bis 2× verkleinert genau wie reines Lanczos (Codes bleiben exakt)
    return src.resize((w, h), Image.Resampling.LANCZOS, reducing_gap=2.0)


# --- Schriftgrößen ----------------------------------------------------------
def span_dots(obj: TextObject, span: Span, base: int) -> int:
    """Größe eines Stücks in Druckpunkten bei Grundgröße ``base`` (gemeinsam skaliert)."""
    if span.size_pt is None:
        return base
    ref = obj.size_pt or REF_PT
    return max(1, round(base * span.size_pt / ref))


def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str,
         dpi: int = DPI) -> int:
    """Grundgröße in Druckpunkten: fest, oder größte passende ≤ auto_start (Halbierung)."""
    def fits(base: int) -> bool:
        l, t, r, b = _block_box(_shape(obj, base, mode="1"))
        return (r - l) <= max_w and (b - t) <= max_h

    start = auto_start if obj.auto else round(obj.size_pt * dpi / 72)
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
        max_pt = int(best / (dpi / 72) * largest / obj.size_pt) if best else None
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
    start: int = 0             # Stelle des ersten Zeichens im Absatz


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
        pieces, start = [], 0
        for span in spans:
            dots = span_dots(obj, span, base)
            font, slant = _font_for(obj, span, dots)
            pieces.append(_Piece(span.text, font, dots, span.underline, slant, start=start))
            start += len(span.text)
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
    """Wortabstände dehnen, bis die Zeile die Blockbreite füllt (ein Wort: linksbündig).

    Die Leerzeichen entfallen: jedes wird zur gedehnten Lücke vor dem folgenden Wort."""
    words: list[_Piece] = []
    gaps_before: list[bool] = []
    for p in pieces:
        start = p.start
        for i, part in enumerate(p.text.split(" ")):
            words.append(_Piece(part, p.font, p.dots, p.underline, p.slant, start=start))
            gaps_before.append(i > 0)
            start += len(part) + 1
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


@dataclass(frozen=True)
class LayoutLine:
    """Eine Zeile (ein Absatz) des Zeilensatzes, Koordinaten wie ``TextLayout``.

    ``stops``: x jeder Zeichengrenze (Zeichen + 1 Werte; Schreibmarke vor Zeichen i);
    ``marks``: je Grenze Oberkante und Höhe der Schreibmarke – in der Schrift des Zeichens
    davor, am Zeilenanfang des ersten Zeichens. Ein leerer Absatz hat kein Zeichen: dort gilt
    die Standardschrift des Objekts in Grundgröße. Schreibt der Editor in einem anderen
    Format weiter, skaliert die GUI die Marke um die Grundlinie (Höhe und Abstand
    Oberkante–Grundlinie wachsen mit der Schriftgröße).
    ``top``: Ascender-Linie der größten Schrift, ``baseline``: gemeinsame Grundlinie,
    ``height``: bis zur tiefsten Unterlänge; ``break_width``: Breite des markierten
    Absatzwechsels (ein Leerzeichen am Zeilenende).
    """
    start: int
    stops: tuple[float, ...]
    marks: tuple[tuple[float, float], ...]
    top: float
    baseline: float
    height: float
    break_width: float

    @property
    def end(self) -> int:
        """Position nach dem letzten Zeichen (vor dem Absatzwechsel)."""
        return self.start + len(self.stops) - 1

    def boxes(self) -> list[tuple[float, float]]:
        """Kästchen (x0, x1) je Zeichen; ein Leerzeichen im Blocksatz reicht über die
        ganze gedehnte Lücke."""
        return list(zip(self.stops, self.stops[1:]))


@dataclass(eq=False)
class TextLayout:
    """Zeilensatz eines Textobjekts: das Rendern zeichnet ``pieces``, die Arbeitsfläche
    bekommt daraus Schreibmarke, Treffer und Markierung (eine Berechnung, zwei Nutzer).

    Koordinaten in Druckpunkten relativ zur linken oberen Ecke des Objektrahmens **vor** der
    Drehung (``width`` × ``height``; bei 90/270° sind ``RenderedObject.w``/``h`` vertauscht –
    ``layout.to_object``/``from_object`` rechnen vom und aufs Etikett um).
    Positionen zählen wie im ``QTextDocument``: die Zeichen der Absätze hintereinander, jeder
    Absatzwechsel zählt als ein Zeichen; Positionen außerhalb werden auf den Text begrenzt.
    """
    texts: list[str]               # Text je Absatz
    pieces: list[list[_Piece]]     # gesetzte Stücke je Zeile, relativ zum Block
    x0: int                        # Blockursprung im Rahmen
    y0: int
    width: int
    height: int

    @cached_property
    def lines(self) -> list[LayoutLine]:
        """Zeilen mit Zeichengrenzen – erst bei Bedarf gemessen (das Rendern braucht sie nicht)."""
        lines, start = [], 0
        for text, pieces in zip(self.texts, self.pieces):
            lines.append(_layout_line(text, pieces, start, self.x0, self.y0))
            start += len(text) + 1
        return lines

    def caret(self, pos: int) -> tuple[float, float, float]:
        """Schreibmarke vor Zeichen ``pos``: (x, Oberkante, Höhe)."""
        line = self._line_at(pos)
        i = self._clamp(pos) - line.start
        return (line.stops[i], *line.marks[i])

    def hit(self, x: float, y: float) -> int:
        """Nächste Zeichengrenze zum Punkt (``x``, ``y``).

        Die Zeile wechselt in der Mitte zwischen Unterkante und nächster Oberkante; Punkte
        über/unter dem Text treffen die erste/letzte Zeile, links/rechts daneben deren
        Anfang/Ende. Grenzen ohne Breite (z. B. vor einem kombinierenden Akzent) zählen
        nicht – getroffen wird die Stelle hinter dem ganzen Zeichen.
        """
        lines = self.lines
        line = lines[sum(1 for above, below in zip(lines, lines[1:])
                         if y >= (above.top + above.height + below.top) / 2)]
        stops = line.stops
        candidates = [k for k in range(len(stops))
                      if k == len(stops) - 1 or stops[k] != stops[k + 1]]
        return line.start + min(candidates, key=lambda k: abs(stops[k] - x))

    def selection_rects(self, a: int, b: int) -> list[tuple[float, float, float, float]]:
        """Markierung zwischen ``a`` und ``b`` (Reihenfolge egal): ein Rechteck
        (x, y, w, h) je betroffener Zeile über die ganze Zeilenhöhe; ein markierter
        Absatzwechsel verlängert seine Zeile um ``break_width``. Die Rechtecke folgen den
        Zeichengrenzen – den nach rechts überhängenden Kopf der Ersatzkursive decken sie
        nicht ab."""
        a, b = sorted((self._clamp(a), self._clamp(b)))
        rects = []
        for line in self.lines:
            if line.end < a or line.start > b:
                continue
            x1 = line.stops[max(a, line.start) - line.start]
            x2 = line.stops[min(b, line.end) - line.start]
            if b > line.end:
                x2 += line.break_width
            if x2 > x1:
                rects.append((x1, line.top, x2 - x1, line.height))
        return rects

    def anchor(self, align: str) -> tuple[float, float]:
        """Punkt, der beim Tippen stehen bleibt (``layout.anchor_after_edit``): senkrecht die
        Oberkante (Ascender-Linie) der ersten Zeile, waagerecht die Bezugskante des Blocks –
        Anfang (links, Blocksatz), Ende (rechts) bzw. Mitte (zentriert) der breitesten Zeile.

        Bezug sind Schriftmaße, nicht die Tinte: eine Oberlänge oder ein „j“ am Zeilenanfang
        verschiebt den Rahmen (Tintenbox), aber nicht den Text. Die Zeile, in die getippt
        wird, bleibt stehen, solange sie die breiteste ist oder ihre Ausrichtung zur
        Bezugskante passt; bei gemischten Ausrichtungen gilt die linke Kante.
        """
        if align not in ALIGNMENTS:
            raise ValueError(f"Unbekannte Textposition {align!r} – erlaubt: links, zentriert, "
                             "rechts, Blocksatz (left, center, right, justify)")
        left = min(line.stops[0] for line in self.lines)
        right = max(line.stops[-1] for line in self.lines)
        share = {"left": 0.0, "justify": 0.0, "center": 0.5, "right": 1.0}[align]
        return left + share * (right - left), self.lines[0].top

    def _clamp(self, pos: int) -> int:
        return min(max(pos, 0), self.lines[-1].end)

    def _line_at(self, pos: int) -> LayoutLine:
        pos = self._clamp(pos)
        return next(line for line in self.lines if line.start <= pos <= line.end)


def to_utf16(text: str, pos: int) -> int:
    """Position in Zeichen (Codepunkte, wie ``TextLayout``) → Position in UTF-16-Einheiten
    (wie ``QTextDocument``: Zeichen außerhalb der BMP zählen doppelt); ``text`` wie
    ``TextObject.text`` (Absatzwechsel = „\\n“)."""
    pos = min(max(pos, 0), len(text))
    return pos + sum(1 for char in text[:pos] if ord(char) > 0xFFFF)


def from_utf16(text: str, pos16: int) -> int:
    """Umkehrung von ``to_utf16``; eine Position mitten in einem Ersatzzeichenpaar zählt als
    die vor dem Zeichen."""
    units = 0
    for i, char in enumerate(text):
        units += 2 if ord(char) > 0xFFFF else 1
        if units > pos16:
            return i
    return len(text)


def _layout_line(text: str, pieces: list[_Piece], start: int, x0: int, y0: int) -> LayoutLine:
    """Zeichengrenzen und Schreibmarken einer Zeile aus ihren gesetzten Stücken."""
    stops = [0.0] * (len(text) + 1)
    for p in pieces:
        t = p.text
        prefix = [p.font.getlength(t[:k], "L") for k in range(len(t) + 1)]
        for j in range(len(t) + 1):
            # Ursprung von Zeichen j, wie gezeichnet – samt Unterschneidung zum Zeichen davor
            # („To“: das „o“ rückt unter das „T“); ein Zeichen ohne eigene Breite (kombinierender
            # Akzent) steht an der Grenze davor; das Ende ist die Länge des ganzen Stücks
            if j == len(t) or prefix[j + 1] == prefix[j]:
                advance = prefix[j]
            else:
                advance = prefix[j + 1] - p.font.getlength(t[j], "L")
            stops[p.start + j] = x0 + p.x + advance
    # Stück je Zeichen: das letzte, das davor beginnt – ein Leerzeichen im Blocksatz gehört
    # so zum Wort davor (gleiches Textstück), ein leeres Stück zum folgenden
    owner, i = [], 0
    for k in range(len(text)):
        while i + 1 < len(pieces) and pieces[i + 1].start <= k:
            i += 1
        owner.append(pieces[i])
    marks = []
    for j in range(len(text) + 1):
        p = owner[j - 1] if j else owner[0] if owner else pieces[0]
        ascent, descent = p.font.getmetrics()
        marks.append((y0 + p.y, ascent + descent))
    top = min(p.y for p in pieces)
    baseline = max(p.y + p.font.getmetrics()[0] for p in pieces)
    bottom = max(p.y + sum(p.font.getmetrics()) for p in pieces)
    last = owner[-1] if owner else pieces[0]
    return LayoutLine(start, tuple(stops), tuple(marks), y0 + top, y0 + baseline, bottom - top,
                      last.font.getlength(" ", "L"))


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


# --- Zierrahmen ---------------------------------------------------------------------
def _check_frame(frame: Frame) -> None:
    if frame.style not in FRAME_STYLES:
        raise ValueError(f"Unbekannte Rahmenart {frame.style!r} – erlaubt: "
                         f"{', '.join(FRAME_STYLES)}")
    if not isinstance(frame.rounded, bool):
        raise ValueError(f"„abgerundet“ des Rahmens muss ja oder nein sein, nicht {frame.rounded!r}")
    for value, (low, high), name in ((frame.line_mm, FRAME_LINE_MM, "Strichstärke"),
                                     (frame.inset_mm, (0.0, MAX_FRAME_MM), "Abstand zum Rand"),
                                     (frame.padding_mm, (0.0, MAX_FRAME_MM), "Innenabstand")):
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value) or not low <= value <= high):
            raise ValueError(f"{name} des Rahmens muss zwischen {_fmt_mm(low)} und "
                             f"{_fmt_mm(high)} mm liegen")


def _fmt_mm(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _line(frame: Frame, dpi: int = DPI) -> int:
    """Strichstärke in Druckpunkten (mindestens 1)."""
    return max(1, _dots(frame.line_mm, dpi))


def _band(frame: Frame, dpi: int = DPI) -> int:
    """Breite aller Linien zusammen (doppelt: Linie, Lücke, Linie; dick-dünn: 2, 1, 1)."""
    lw = _line(frame, dpi)
    return {"double": 3 * lw, "thick_thin": 4 * lw}.get(frame.style, lw)


def _outer(sheet: _Sheet, width: int, height: int) -> tuple[int, int, int, int]:
    """Außenkante des Rahmens (x0, y0, x1, y1; Ende ausschließlich) in Leserichtung; rund:
    das Quadrat um den Kreis."""
    mx, my = sheet.margins()
    inset = sheet.dots(sheet.frame.inset_mm)
    x0, y0, x1, y1 = mx + inset, my + inset, width - mx - inset, height - my - inset
    if sheet.round:
        d = min(x1 - x0, y1 - y0)
        x0, y0 = x0 + (x1 - x0 - d) // 2, y0 + (y1 - y0 - d) // 2
        x1, y1 = x0 + d, y0 + d
    return x0, y0, x1, y1


def _circle_room(sheet: _Sheet) -> int:
    """Seite des Quadrats im Kreisrahmen (Innenraum runder Etiketten) in Druckpunkten."""
    x0, _, x1, _ = _outer(sheet, sheet.across, sheet.across)   # runde Etiketten sind quadratisch
    radius = (x1 - x0) / 2 - _band(sheet.frame, sheet.dpi) - sheet.dots(sheet.frame.padding_mm)
    return int(radius * math.sqrt(2)) if radius > 0 else 0


def _frame_mask(sheet: _Sheet, width: int, height: int) -> Image.Image | None:
    """Zierrahmen als Maske (255 = Tinte): Linien liegen ganz innerhalb der Außenkante."""
    frame = sheet.frame
    if frame is None:
        return None
    lw = _line(frame, sheet.dpi)
    box = _outer(sheet, width, height)
    w, h = box[2] - box[0], box[3] - box[1]
    style = "single" if sheet.round and frame.style == "corners" else frame.style
    radius = (min(sheet.dots(FRAME_RADIUS_MM), min(w, h) // 4)
              if frame.rounded and not sheet.round else 0)
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    def ring(offset: int, thickness: int) -> None:
        xy = (box[0] + offset, box[1] + offset, box[2] - 1 - offset, box[3] - 1 - offset)
        if xy[2] < xy[0] or xy[3] < xy[1]:
            return
        if sheet.round:
            draw.ellipse(xy, outline=255, width=thickness)
        else:
            draw.rounded_rectangle(xy, radius=max(0, radius - offset), outline=255,
                                   width=thickness)

    if style == "double":
        ring(0, lw)
        ring(2 * lw, lw)
    elif style == "thick_thin":
        ring(0, 2 * lw)
        ring(3 * lw, lw)
    else:
        ring(0, lw)
    if style == "corners":
        leg = min(sheet.dots(FRAME_CORNER_MM), min(w, h) // 4)
        if leg < 2 * lw:                     # sonst blieben nur Quadrate (oder nichts)
            raise ValueError(FRAME_TOO_BIG)
        keep = Image.new("L", mask.size, 0)
        corners = ImageDraw.Draw(keep)
        for x, y in ((box[0], box[1]), (box[2] - leg, box[1]), (box[0], box[3] - leg),
                     (box[2] - leg, box[3] - leg)):
            corners.rectangle((x, y, x + leg - 1, y + leg - 1), fill=255)
        mask = ImageChops.darker(mask, keep)
    elif style == "dashed":
        mask = ImageChops.darker(mask, _dashes(sheet.round, box, radius, lw, mask.size))
    elif style == "dotted":
        mask = _dots_mask(sheet.round, box, radius, lw, mask.size)
    return mask


def _sides(box: tuple[int, int, int, int], radius: int, lw: int) -> list[list[tuple[float, float]]]:
    """Mittellinie eines (abgerundeten) Rechteckrahmens in vier Seiten, je von Eckmitte zu
    Eckmitte – Striche und Punkte verteilen sich je Seite gleichmäßig, die Ecken sind besetzt."""
    half = lw / 2
    x0, y0, x1, y1 = box[0] + half, box[1] + half, box[2] - half, box[3] - half
    r = max(radius - half, 0.0)
    centres = {"tl": (x0 + r, y0 + r), "tr": (x1 - r, y0 + r), "br": (x1 - r, y1 - r),
               "bl": (x0 + r, y1 - r)}

    def arc(corner: str, a0: float, a1: float) -> list[tuple[float, float]]:
        cx, cy = centres[corner]
        steps = max(1, math.ceil(r * math.radians(abs(a1 - a0)) / 0.5))
        return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
                 cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps)))
                for i in range(steps + 1)]
    return [arc("tl", 225, 270) + arc("tr", 270, 315),
            arc("tr", 315, 360) + arc("br", 0, 45),
            arc("br", 45, 90) + arc("bl", 90, 135),
            arc("bl", 135, 180) + arc("tl", 180, 225)]


def _lengths(path: list[tuple[float, float]]) -> list[float]:
    out = [0.0]
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        out.append(out[-1] + math.hypot(bx - ax, by - ay))
    return out


def _point(path, lengths, s: float) -> tuple[float, float]:
    """Punkt der Mittellinie bei Bogenlänge ``s``."""
    s = min(max(s, 0.0), lengths[-1])
    for i in range(1, len(path)):
        if lengths[i] >= s:
            span = lengths[i] - lengths[i - 1] or 1.0
            t = (s - lengths[i - 1]) / span
            (ax, ay), (bx, by) = path[i - 1], path[i]
            return ax + (bx - ax) * t, ay + (by - ay) * t
    return path[-1]


def _piece(path, lengths, s0: float, s1: float) -> list[tuple[float, float]]:
    """Stück der Mittellinie zwischen den Bogenlängen ``s0`` und ``s1``."""
    s0, s1 = max(s0, 0.0), min(s1, lengths[-1])
    inner = [p for p, s in zip(path, lengths) if s0 < s < s1]
    return [_point(path, lengths, s0), *inner, _point(path, lengths, s1)]


def _dashes(round_label: bool, box, radius: int, lw: int, size) -> Image.Image:
    """Striche (3 × Strichstärke, Lücke 2 ×, je Seite gleichmäßig) als Maske – breiter als die
    Linie, geschnitten mit ihr ergeben sich saubere Kanten."""
    keep = Image.new("L", size, 0)
    draw = ImageDraw.Draw(keep)
    if round_label:                          # Kreis: Tortenstücke vom Mittelpunkt aus
        d = box[2] - box[0]
        n = max(4, round(math.pi * (d - lw) / (5 * lw)))
        pad = 2 * lw
        wedge = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
        for k in range(n):
            mid = -90 + 360 * k / n
            draw.pieslice(wedge, mid - 108 / n, mid + 108 / n, fill=255)   # 60 % der Teilung
        return keep
    if radius == 0:                          # Eckstriche bis in die äußere Ecke
        for x, y in ((box[0], box[1]), (box[2] - lw, box[1]), (box[0], box[3] - lw),
                     (box[2] - lw, box[3] - lw)):
            draw.rectangle((x, y, x + lw - 1, y + lw - 1), fill=255)
    for side in _sides(box, radius, lw):
        lengths = _lengths(side)
        total = lengths[-1]
        m = max(1, round(total / (5 * lw)))
        period, dash = total / m, 0.6 * total / m
        for k in range(m + 1):
            centre = k * period
            piece = _piece(side, lengths, centre - dash / 2, centre + dash / 2)
            draw.line(piece, fill=255, width=lw + 4, joint="curve")
    return keep


def _dots_mask(round_label: bool, box, radius: int, lw: int, size) -> Image.Image:
    """Runde Punkte (Durchmesser = Strichstärke, Abstand 2 ×) auf der Mittellinie."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    half = lw / 2
    points = []
    if round_label:
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        r = (box[2] - box[0]) / 2 - half
        n = max(8, round(2 * math.pi * r / (2 * lw)))
        points = [(cx + r * math.cos(2 * math.pi * k / n - math.pi / 2),
                   cy + r * math.sin(2 * math.pi * k / n - math.pi / 2)) for k in range(n)]
    else:
        for side in _sides(box, radius, lw):
            lengths = _lengths(side)
            m = max(1, round(lengths[-1] / (2 * lw)))
            points += [_point(side, lengths, lengths[-1] * k / m) for k in range(m)]
    for x, y in points:
        if lw <= 2:
            draw.rectangle((math.floor(x - half), math.floor(y - half),
                            math.floor(x - half) + lw - 1, math.floor(y - half) + lw - 1), fill=255)
        else:
            draw.ellipse((x - half, y - half, x + half - 1, y + half - 1), fill=255)
    return mask
