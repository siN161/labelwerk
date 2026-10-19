"""Platzier-Logik ohne Qt: Einrasten, Ausrichten, Größe angleichen, Skalieren.

Alle Rechtecke in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts
(wie ``TextObject.x_mm``/``y_mm``). Die GUI rechnet nur in Bildschirmkoordinaten um.
Ausnahme Schreibmodus (``to_object``/``from_object``): Punkte in Druckpunkten wie
``RenderedObject`` und ``TextLayout`` – so rechnet die Arbeitsfläche ohne Umweg über mm.

Bild-Objekte verhalten sich wie Text mit fester Rahmengröße (``_framed``); Funktionen nur
für Schrift (``scale_text``, ``fix_size``, Schreibmodus) weisen sie mit ``TypeError`` ab.
Barcodes haben einen Rahmen aus Modulbreite (ganze Druckpunkte) und Höhe (``_barcode_frame``).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field, replace

from . import barcodes
from .document import (BARCODE_MM, MAX_PT, MIN_PT, ROTATIONS, BarcodeObject, Document,
                       ImageObject, TextObject)
from .i18n import _
from .labels import DPI, get_label, length_limits
from .render import (PT, REF_PT, RenderedObject, frame_box, span_dots, label_margins, label_size,
                     render_object)

ALIGN_MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom")
SIZE_MODES = ("same", "width", "height")
_EPS = 1e-6                # Rundungsspielraum beim Vergleich von mm-Werten
_DECIMALS = 3              # Positionen/Rahmen im Modell: auf 1/1000 mm
GRID_MM = 0.1              # Raster der Positionsfelder: Ziehen/Skalieren endet darauf


def _mm(dots: float, dpi: int = DPI) -> float:
    return dots * 25.4 / dpi


def change_label(doc: Document, label_id: str) -> None:
    """Anderes Etikett für ``doc`` (wird geändert). Hat es eine andere Auflösung, behalten Barcodes
    ihre Breite in mm: Modulbreite in den Punkten des neuen Druckers (ganze Punkte, 1–``max_module``)."""
    old, new = _label_dpi(doc), get_label(label_id).dpi
    doc.label_id = label_id
    if old == new:
        return
    for obj in doc.objects:
        if isinstance(obj, BarcodeObject) and isinstance(obj.module, int):
            obj.module = min(max(round(obj.module * new / old), 1), barcodes.max_module(new))


def _label_dpi(doc: Document) -> int:
    return get_label(doc.label_id).dpi


@dataclass(frozen=True)
class Rect:
    """Rechteck in mm: linke obere Ecke ``x``/``y``, Breite ``w``, Höhe ``h``."""
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def moved(self, dx: float, dy: float) -> "Rect":
        return replace(self, x=self.x + dx, y=self.y + dy)

    def at(self, x: float, y: float) -> "Rect":
        return replace(self, x=x, y=y)


@dataclass
class Snap:
    """Ergebnis des Einrastens: Verschiebung in mm und Hilfslinien ``("x" | "y", mm)``."""
    dx: float = 0.0
    dy: float = 0.0
    guides: list[tuple[str, float]] = field(default_factory=list)


# --- Etikett ----------------------------------------------------------------------
def object_rect(rendered: RenderedObject) -> Rect:
    """Rahmen eines gerenderten Objekts in mm."""
    dpi = rendered.dpi
    return Rect(_mm(rendered.x, dpi), _mm(rendered.y, dpi), _mm(rendered.w, dpi),
                _mm(rendered.h, dpi))


def label_rect(doc: Document, model: str = "QL-600") -> Rect:
    """Ganzes Etikett in mm (bei automatischer Länge so lang, wie ``render_document`` es macht)."""
    w, h = label_size(doc, model)
    return Rect(0.0, 0.0, _mm(w, _label_dpi(doc)), _mm(h, _label_dpi(doc)))


def growing_axis(doc: Document) -> str | None:
    """Achse in Leserichtung („x“/„y“), in der das Etikett mit den Objekten wächst
    (Endlosband mit automatischer Länge), sonst None.

    Kante und Mitte des Etiketts liegen in dieser Achse nicht fest – sie wandern mit dem
    am weitesten außen liegenden Objekt.
    """
    if get_label(doc.label_id).height is not None or doc.length_mm is not None:
        return None
    return "x" if doc.orientation == "horizontal" else "y"


def printable_area(doc: Document, model: str = "QL-600",
                   size: tuple[int, int] | None = None) -> Rect:
    """Bedruckbarer Bereich: Etikett minus Rand in Bandlaufrichtung bzw. quer dazu.

    ``size``: schon bekannte Etikettgröße (``render.label_size``) – dann wird nichts gerendert.
    """
    w, h = size if size is not None else label_size(doc, model)
    mx, my = label_margins(doc, model)
    dpi = _label_dpi(doc)
    return Rect(_mm(mx, dpi), _mm(my, dpi), _mm(w - 2 * mx, dpi), _mm(h - 2 * my, dpi))


# --- Einrasten --------------------------------------------------------------------
def snap(moving: Rect, targets: list[Rect], area: Rect, tolerance_mm: float,
         label: Rect | None = None, grow: str | None = None, inner: Rect | None = None) -> Snap:
    """Kanten und Mitte von ``moving`` an nahe Linien einrasten lassen.

    Kandidaten: Kanten und Mitte des bedruckbaren Bereichs, des Etiketts und des Innenraums
    eines Zierrahmens (``inner``, falls angegeben) und der anderen Objekte. Je Achse gewinnt der nächste Kandidat innerhalb der Toleranz
    (Grenze eingeschlossen); ``guides`` nennt alle Linien, die nach dem Einrasten getroffen
    werden. ``grow`` (``growing_axis``): In dieser Achse bieten Etikett und Bereich nur
    ihren Anfang an – Mitte und Ende wandern mit dem Objekt.
    """
    sheets = [area, *(r for r in (label, inner) if r is not None)]
    x_lines = [v for r in sheets for v in ((r.x,) if grow == "x" else (r.x, r.cx, r.right))]
    y_lines = [v for r in sheets for v in ((r.y,) if grow == "y" else (r.y, r.cy, r.bottom))]
    dx, x_guides = _snap_axis((moving.x, moving.cx, moving.right),
                              x_lines + [v for r in targets for v in (r.x, r.cx, r.right)],
                              tolerance_mm)
    dy, y_guides = _snap_axis((moving.y, moving.cy, moving.bottom),
                              y_lines + [v for r in targets for v in (r.y, r.cy, r.bottom)],
                              tolerance_mm)
    return Snap(dx, dy, [("x", v) for v in x_guides] + [("y", v) for v in y_guides])


def _snap_axis(points: tuple[float, ...], candidates: list[float],
               tolerance: float) -> tuple[float, list[float]]:
    """Kleinste Verschiebung eines Punkts auf einen Kandidaten und die danach getroffenen Linien."""
    shifts = [c - p for p in points for c in candidates if abs(c - p) <= tolerance + _EPS]
    if not shifts:
        return 0.0, []
    best = min(shifts, key=abs)
    hits: list[float] = []
    for cand in sorted(candidates):
        hit = any(abs(p + best - cand) <= _EPS for p in points)
        if hit and not (hits and cand - hits[-1] <= _EPS):
            hits.append(cand)
    return best, hits


# --- Ausrichten, Größe ------------------------------------------------------------
def bounds(rects: list[Rect]) -> Rect:
    """Umgebendes Rechteck (z. B. der Auswahl); mindestens ein Rechteck nötig."""
    x, y = min(r.x for r in rects), min(r.y for r in rects)
    return Rect(x, y, max(r.right for r in rects) - x, max(r.bottom for r in rects) - y)


def align(rects: list[Rect], mode: str, area: Rect | None = None) -> list[Rect]:
    """Rechtecke ausrichten – mit ``area`` am Papier, sonst aneinander.

    Bezug aneinander: äußerste Kante bzw. Mitte der Auswahl; ein einzelnes Rechteck
    ohne ``area`` bleibt, wo es ist.
    """
    if mode not in ALIGN_MODES:
        raise ValueError(_("Unknown alignment {mode!r} – allowed: {allowed}").format(
            mode=mode, allowed=", ".join(ALIGN_MODES)))
    if area is None:
        if len(rects) < 2:
            return list(rects)
        area = bounds(rects)
    moved_to = {
        "left": lambda r: r.at(area.x, r.y),
        "hcenter": lambda r: r.at(area.cx - r.w / 2, r.y),
        "right": lambda r: r.at(area.right - r.w, r.y),
        "top": lambda r: r.at(r.x, area.y),
        "vcenter": lambda r: r.at(r.x, area.cy - r.h / 2),
        "bottom": lambda r: r.at(r.x, area.bottom - r.h),
    }[mode]
    return [moved_to(r) for r in rects]


def match_size(rects: list[Rect], mode: str) -> list[Rect]:
    """Größe an das erste Rechteck angleichen (``same``, ``width``, ``height``); Ecke bleibt."""
    if mode not in SIZE_MODES:
        raise ValueError(_("Unknown size matching {mode!r} – allowed: {allowed}").format(
            mode=mode, allowed=", ".join(SIZE_MODES)))
    if not rects:
        return []
    ref = rects[0]
    w = mode in ("same", "width")
    h = mode in ("same", "height")
    return [replace(r, w=ref.w if w else r.w, h=ref.h if h else r.h) for r in rects]


def maximize(rect: Rect, area: Rect, grow: str | None = None) -> Rect:
    """Größtmöglich in ``area`` bei gleichem Seitenverhältnis, mittig darin.

    ``grow`` (``growing_axis``): In dieser Achse wächst das Etikett mit – dort begrenzt die
    Fläche nicht, das Rechteck wird nur quer eingepasst und behält seinen Anfang.
    Eine leere Fläche (Breite oder Höhe ≤ 0) lässt das Rechteck unverändert.
    """
    if area.w <= 0 or area.h <= 0:
        return rect
    if rect.w > 0 and rect.h > 0:
        factor = {"x": area.h / rect.h, "y": area.w / rect.w}.get(
            grow, min(area.w / rect.w, area.h / rect.h))
        rect = replace(rect, w=rect.w * factor, h=rect.h * factor)
    return rect.at(rect.x if grow == "x" else area.cx - rect.w / 2,
                   rect.y if grow == "y" else area.cy - rect.h / 2)


# --- Objekte ----------------------------------------------------------------------
Object = TextObject | ImageObject | BarcodeObject


def _framed(obj: Object) -> bool:
    """Fester Rahmen in ``w_mm``/``h_mm``: Bild oder Text mit fester Rahmengröße."""
    return isinstance(obj, ImageObject) or isinstance(obj, TextObject) and obj.fit


def _needs_size(obj: Object) -> bool:
    """Text mit automatischer Schriftgröße ohne festen Rahmen: bekommt beim Platzieren seine
    wirksame Größe fest (``fix_size``)."""
    return isinstance(obj, TextObject) and not obj.fit and obj.size_pt is None


def _text_only(obj: Object) -> None:
    if not isinstance(obj, TextObject):
        raise TypeError(_("Only for text objects, not for {type}.").format(type=type(obj).__name__))


def place(obj: Object, rect: Rect, dpi: int = DPI) -> Object:
    """Kopie von ``obj`` an ``rect``; bei festem Rahmen auch Breite/Höhe (ungedreht), bei
    Barcodes Modulbreite und Höhe (``_barcode_frame``)."""
    placed = copy.deepcopy(obj)
    placed.x_mm, placed.y_mm = rect.x, rect.y
    w, h = (rect.h, rect.w) if obj.rotation in (90, 270) else (rect.w, rect.h)
    if isinstance(obj, BarcodeObject):
        return _barcode_frame(placed, w, h, dpi=dpi)
    if _framed(obj):
        placed.w_mm, placed.h_mm = w, h
    return placed


def _barcode_frame(obj: BarcodeObject, w: float, h: float, down: bool = False,
                   dpi: int = DPI) -> BarcodeObject:
    """``obj`` (wird geändert) für einen Rahmen ``w`` × ``h`` mm (ungedreht): Modulbreite auf
    ganze Druckpunkte gerundet (``down``: abgerundet – passt sicher hinein), 1–``max_module``;
    Strichcodes: Höhe ``h`` (2–100 mm). QR ist quadratisch: Es zählt das Maß, das sich stärker
    ändert. Lässt sich der Inhalt nicht kodieren, bleibt die Modulbreite."""
    if obj.kind != "qr":
        h = min(max(h, BARCODE_MM[0]), BARCODE_MM[1])
        obj.h_mm = math.floor(h * 1000 + _EPS) / 1000 if down else round(h, _DECIMALS)
    try:
        count = barcodes.modules(obj)
    except barcodes.BarcodeError:
        return obj
    if obj.kind == "qr":
        side = _mm(count * obj.module, dpi)
        w = w if abs(w - side) >= abs(h - side) else h
    dots = w * dpi / 25.4 / count
    module = math.floor(dots + _EPS) if down else round(dots)
    obj.module = min(max(module, 1), barcodes.max_module(dpi))
    return obj


def barcode_rect(obj: BarcodeObject, dpi: int = DPI) -> Rect | None:
    """Rahmen eines Barcodes in mm (nach dem Drehen) aus Modulbreite und Höhe, wie er gerendert
    wird; None, wenn sich der Inhalt nicht kodieren lässt."""
    try:
        w = _mm(barcodes.modules(obj) * obj.module, dpi)
    except barcodes.BarcodeError:
        return None
    h = w if obj.kind == "qr" else obj.h_mm
    if obj.rotation in (90, 270):
        w, h = h, w
    return Rect(obj.x_mm, obj.y_mm, w, h)


def fix_size(obj: TextObject, base_pt: float, dpi: int = DPI) -> TextObject:
    """Kopie mit der wirksamen Grundgröße ``base_pt`` als fester Schriftgröße, ohne Rahmengröße.

    Stücke mit eigener Größe behalten ihr Verhältnis; das Bild bleibt gleich: Jede Größe
    bekommt die kürzeste Dezimalzahl (ab 0,1 pt), die dieselbe Druckgröße ergibt.
    """
    _text_only(obj)
    base_dots = round(base_pt * dpi / 72)
    fixed = copy.deepcopy(obj)
    fixed.size_pt, fixed.fit = round(base_pt, 1), False   # ergibt wieder base_dots
    for old, new in zip((s for p in obj.paragraphs for s in p.spans),
                        (s for p in fixed.paragraphs for s in p.spans)):
        if old.size_pt is None:
            continue
        dots = span_dots(obj, old, base_dots)
        exact = old.size_pt * fixed.size_pt / (obj.size_pt or REF_PT)
        new.size_pt = next((value for value in (round(exact, d) for d in range(1, 7))
                            if span_dots(fixed, replace(new, size_pt=value), base_dots) == dots),
                           exact)
    return fixed


def exact_rect(obj: Object, rendered: RenderedObject) -> Rect:
    """Rahmen in mm, wie er im Modell steht (ohne Rundung auf Druckpunkte).

    Position aus ``x_mm``/``y_mm``, Größe bei festem Rahmen (Bild, feste Rahmengröße) aus
    ``w_mm``/``h_mm`` (gedreht), bei Barcodes aus Inhalt, Modul und ``h_mm`` (``barcode_rect``; ungültiger
    Inhalt: wie gerendert), sonst wie gerendert; ein Objekt ohne Position steht, wo es gerendert wurde.
    """
    r = object_rect(rendered)
    x, y = ((obj.x_mm or 0.0, obj.y_mm or 0.0) if obj.positioned else (r.x, r.y))
    w, h = r.w, r.h
    if isinstance(obj, BarcodeObject) and (own := barcode_rect(obj, rendered.dpi)) is not None:
        w, h = own.w, own.h                     # aus Inhalt und Modul (auch bei veraltetem Bild)
    if obj.positioned and _framed(obj) and obj.w_mm is not None and obj.h_mm is not None:
        w, h = (obj.h_mm, obj.w_mm) if obj.rotation in (90, 270) else (obj.w_mm, obj.h_mm)
    return Rect(x, y, w, h)


def _apply_change(obj: Object, rect: Rect, rendered: RenderedObject) -> Rect:
    """Änderung gegenüber dem gerenderten Rahmen auf den Rahmen im Modell übertragen.

    So verschieben Pfeiltasten genau um 0,1 mm, obwohl das Bild auf Druckpunkte gerundet ist;
    Reste der Umrechnung werden auf 1/1000 mm gerundet.
    """
    shown, exact = object_rect(rendered), exact_rect(obj, rendered)
    return Rect(*(round(e + n - s, _DECIMALS) for e, n, s in (
        (exact.x, rect.x, shown.x), (exact.y, rect.y, shown.y),
        (exact.w, rect.w, shown.w), (exact.h, rect.h, shown.h))))


def move(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
    """Kopie von ``obj``, verschoben auf ``rect`` (neue Lage des gerenderten Rahmens).

    Die Größe bleibt. Ein automatisch großes Objekt ohne eigenen Rahmen bekommt beim ersten
    Verschieben seine wirksame Größe (``rendered.base_pt``) als feste Schriftgröße – es sieht
    danach genauso aus.
    """
    target = _apply_change(obj, rect, rendered)
    if isinstance(obj, TextObject) and (obj.size_pt is None or (obj.fit and not obj.positioned)):
        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
    moved = copy.deepcopy(obj)
    moved.x_mm, moved.y_mm = target.x, target.y
    return moved


def set_frame(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
    """Kopie mit dem Rahmen ``rect`` in mm, wie er im Modell steht (Zahlen im Panel „Position“).

    Mit festem Rahmen (Bild, feste Rahmengröße) gelten Lage und Größe, sonst nur die Lage. Ein
    automatisch großes Objekt bekommt dabei seine wirksame Größe (``rendered.base_pt``) als
    feste Schriftgröße.
    """
    if _needs_size(obj):
        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
    return place(obj, rect, rendered.dpi)


def resize(obj: Object, rect: Rect, rendered: RenderedObject, handle: str) -> Object:
    """Kopie nach Ziehen am Anfasser ``handle`` („tl“, „t“, … „l“): gerenderter Rahmen → ``rect``.

    Mit fester Rahmengröße ändert jeder Anfasser den Rahmen. Ohne skaliert eine Ecke die
    Schrift, eine Kante schaltet die feste Rahmengröße ein.
    Ein Bild mit ``keep_ratio`` behält dabei sein Seitenverhältnis (``keep_aspect``, dieselbe
    Regel wie die Vorschau der Arbeitsfläche), ohne verzerren Kanten und Ecken den Rahmen.
    Barcodes rasten auf ganze Druckpunkte je Modul ein (``_resize_barcode``).
    """
    corner = len(handle) == 2
    target = _apply_change(obj, rect, rendered)
    if isinstance(obj, BarcodeObject):
        return _resize_barcode(obj, target, exact_rect(obj, rendered), handle, rendered.dpi)
    if isinstance(obj, ImageObject):
        if obj.keep_ratio:
            target = _rounded(keep_aspect(exact_rect(obj, rendered), target, handle))
        return place(obj, target, rendered.dpi)
    if obj.fit:
        return place(obj, target, rendered.dpi)
    if corner:
        old = object_rect(rendered)
        factor = ((rect.w * rect.h) / (old.w * old.h)) ** 0.5 if old.w and old.h else 1.0
        return place(scale_text(obj, factor, base_pt=rendered.base_pt), target, rendered.dpi)
    # feste Rahmengröße braucht eine feste Schrift: sonst ginge der Rahmen beim Verschieben verloren
    framed = (fix_size(obj, rendered.base_pt, rendered.dpi) if obj.size_pt is None
              else copy.deepcopy(obj))
    framed.fit = True
    return place(framed, target, rendered.dpi)


def _resize_barcode(obj: BarcodeObject, target: Rect, old: Rect, handle: str,
                    dpi: int = DPI) -> BarcodeObject:
    """Barcode nach Ziehen am Anfasser: QR hält das Quadrat (``keep_aspect``); bei Strichcodes
    ändert das Maß quer zu den Strichen die Modulbreite, das andere die Höhe. Nach dem Einrasten
    bleibt, was der Anfasser festhält (gegenüberliegende Kante, sonst die Mitte)."""
    if obj.kind == "qr":
        target = keep_aspect(old, target, handle)
    turned = obj.rotation in (90, 270)
    across, along = "l" in handle or "r" in handle, "t" in handle or "b" in handle
    w, h = (target.h, target.w) if turned else (target.w, target.h)
    ow, oh = (old.h, old.w) if turned else (old.w, old.h)
    sized = _barcode_frame(copy.deepcopy(obj), w if (along if turned else across) else ow,
                           h if (across if turned else along) else oh, dpi=dpi)
    shown = barcode_rect(sized, dpi) or target
    x = (target.right - shown.w if "l" in handle else target.x if "r" in handle
         else target.cx - shown.w / 2)
    y = (target.bottom - shown.h if "t" in handle else target.y if "b" in handle
         else target.cy - shown.h / 2)
    sized.x_mm, sized.y_mm = round(x, _DECIMALS), round(y, _DECIMALS)
    return sized


def keep_aspect(old: Rect, new: Rect, handle: str) -> Rect:
    """Rahmen ``new`` (nach Ziehen am Anfasser ``handle``) mit dem Seitenverhältnis von ``old``.

    Was fest bleibt, folgt allein aus dem Anfasser (Vorschau und Ergebnis rechnen gleich):
    Ecke – das stärker gewachsene Maß zählt, die gegenüberliegende Ecke bleibt. Kante – das
    gezogene Maß zählt, die gegenüberliegende Kante bleibt, quer dazu die Mitte (links/rechts:
    senkrecht mittig, oben/unten: waagerecht mittig).
    """
    if old.w <= 0 or old.h <= 0:
        return new
    across, along = "l" in handle or "r" in handle, "t" in handle or "b" in handle
    fx, fy = new.w / old.w, new.h / old.h
    factor = max(fx, fy) if across and along else fx if across else fy
    w, h = old.w * factor, old.h * factor

    def start(old0: float, old1: float, size: float, moves_start: bool, moves_end: bool) -> float:
        if moves_start:
            return old1 - size                 # Ende bleibt
        if moves_end:
            return old0                        # Anfang bleibt
        return (old0 + old1 - size) / 2        # quer zur gezogenen Kante: Mitte bleibt

    return Rect(start(old.x, old.right, w, "l" in handle, "r" in handle),
                start(old.y, old.bottom, h, "t" in handle, "b" in handle), w, h)


# --- Bild-Objekte: einfügen und einstellen ---------------------------------------
INSERT_GAP_MM = 2.0      # Abstand eines hinter vorhandene Objekte eingefügten Objekts


def insert_frame(doc: Document, model: str, area: Rect, size: tuple[float, float],
                 at: tuple[float, float] | None = None) -> tuple[Rect, float]:
    """Rahmen für ein neues Objekt der Größe ``size`` (mm) und den Faktor, um den es dafür
    proportional verkleinert wurde (1 = 1:1).

    Mittig auf ``at`` (Klick-/Ablagepunkt) bzw. in der Mitte von ``area`` (bedruckbarer
    Bereich), in den Bereich geschoben. In der Achse, in der das Etikett mitwächst
    (``growing_axis``), begrenzt nur die größte Etikettlänge, und das Objekt beginnt nicht
    vor dem Anfang des Bereichs.
    """
    grow = growing_axis(doc)
    limit_w, limit_h = _insert_limits(doc, model, area)
    w, h = size
    factor = min(1.0, limit_w / w, limit_h / h) if w > 0 and h > 0 else 1.0
    w, h = w * factor, h * factor
    cx, cy = at if at is not None else (area.cx, area.cy)

    def inside(start: float, low: float, high: float, open_end: bool) -> float:
        start = max(start, low)
        return start if open_end else min(start, max(low, high))

    x = inside(cx - w / 2, area.x, area.right - w, grow == "x")
    y = inside(cy - h / 2, area.y, area.bottom - h, grow == "y")
    return _rounded(Rect(x, y, w, h)), factor


def insert_placement(doc: Document, model: str, area: Rect, size: tuple[float, float],
                     at: tuple[float, float] | None = None,
                     others: list[Rect] | None = None,
                     rotate: bool = True) -> tuple[Rect, int, float]:
    """Wie ``insert_frame``, aber lieber gedreht als verkleinert (wie ``print-file
    --rotate auto``): (Rahmen auf dem Etikett nach dem Drehen, Drehung 0/90, Faktor).
    ``rotate=False`` (Einstellung „nicht drehen“): nie gedreht, wie ``insert_frame``.

    ``others``: Rahmen vorhandener (nicht leerer) Objekte. Wächst das Etikett mit
    (``growing_axis``), ohne ausdrücklichen Punkt ``at``, und läge der Rahmen auf einem
    davon, kommt er ``INSERT_GAP_MM`` hinter das am weitesten hinten liegende Objekt
    (senkrecht: unter, waagerecht: rechts davon), quer weiter mittig.

    Passt das Objekt 1:1 nicht in den Bereich, gedreht um 90° aber schon, kommt es gedreht
    und 1:1; nur wenn es in keiner Lage passt, wird es ungedreht verkleinert. Die Grenzen
    sind dieselben wie bei ``insert_frame`` (in der mitwachsenden Achse die größte Länge).
    """
    limit_w, limit_h = _insert_limits(doc, model, area)
    w, h = size
    turn = rotate and not (w <= limit_w and h <= limit_h) and h <= limit_w and w <= limit_h
    rect, factor = insert_frame(doc, model, area, (h, w) if turn else size, at)
    grow = growing_axis(doc)
    if grow and at is None and any(_overlap(rect, o) for o in others or ()):
        if grow == "x":
            rect = _rounded(replace(rect, x=max(o.right for o in others) + INSERT_GAP_MM))
        else:
            rect = _rounded(replace(rect, y=max(o.bottom for o in others) + INSERT_GAP_MM))
    return rect, 90 if turn else 0, factor


def new_barcode(doc: Document, model: str, area: Rect, kind: str,
                others: list[Rect] | None = None, rotate: bool = True) -> BarcodeObject:
    """Neuer Barcode der Art ``kind`` mit Beispielinhalt (``barcodes.SAMPLES``), platziert wie
    ein Bild (``insert_placement``: mittig in ``area``, auf einem Endlosband hinter ``others``).
    Passt er nicht, wird bei Strichcodes zuerst nur die Höhe kleiner; die Modulbreite schrumpft
    erst, wenn er auch gedreht nicht hineinpasst (``rotate``)."""
    dpi = _label_dpi(doc)
    obj = BarcodeObject(kind=kind, data=barcodes.SAMPLES[kind],
                        module=barcodes.insert_module(kind, dpi))
    count = barcodes.modules(obj)
    limit_w, limit_h = _insert_limits(doc, model, area)
    best = None                                       # (passt, Modul, Drehung, Höhe)
    for turn in (0, 90) if rotate else (0,):
        w, h = (limit_w, limit_h) if turn == 0 else (limit_h, limit_w)   # ungedreht
        if kind == "qr":
            w = h = min(w, h)
        module = min(obj.module, math.floor(w * dpi / 25.4 / count + _EPS))
        fits = module >= 1 and (kind == "qr" or h >= BARCODE_MM[0])
        if best is None or (fits, module) > best[:2]:  # gleich gut: ungedreht
            best = (fits, module, turn, h)
    __, module, obj.rotation, h = best
    obj.module = max(1, module)
    if kind != "qr":
        obj.h_mm = math.floor(min(max(h, BARCODE_MM[0]), obj.h_mm) * 1000 + _EPS) / 1000
    shown = barcode_rect(obj, dpi)
    rect, __, __ = insert_placement(doc, model, area, (shown.w, shown.h), others=others,
                                  rotate=False)
    obj.x_mm = round(rect.cx - shown.w / 2, _DECIMALS)
    obj.y_mm = round(rect.cy - shown.h / 2, _DECIMALS)
    return obj


def _overlap(a: Rect, b: Rect) -> bool:
    return a.x < b.right and b.x < a.right and a.y < b.bottom and b.y < a.bottom


def _insert_limits(doc: Document, model: str, area: Rect) -> tuple[float, float]:
    """Größe (Breite, Höhe in mm), die ein neues Objekt 1:1 höchstens haben darf: der
    Bereich, in der mitwachsenden Achse (``growing_axis``) die größte Etikettlänge."""
    grow = growing_axis(doc)
    if grow is None:
        return area.w, area.h
    mx, my = label_margins(doc, model)
    longest = _mm(length_limits(model)[1] - 2 * (mx if grow == "x" else my), _label_dpi(doc))
    return (longest, area.h) if grow == "x" else (area.w, longest)


def _image_point(obj: ImageObject, u: float, v: float) -> tuple[float, float]:
    """Punkt im ungedrehten Rahmen (mm ab seiner linken oberen Ecke) → Etikett (mm)."""
    w, h = obj.w_mm, obj.h_mm
    du, dv = {0: (u, v), 90: (h - v, u), 180: (w - u, h - v), 270: (v, w - u)}[obj.rotation]
    return obj.x_mm + du, obj.y_mm + dv


def set_crop(obj: ImageObject, crop: tuple[int, int, int, int] | None) -> ImageObject:
    """Kopie mit dem Ausschnitt ``crop`` (None = ganzes Bild). Maßstab und Lage des Inhalts
    auf dem Etikett bleiben: Der Rahmen schrumpft auf den Ausschnitt bzw. wächst ums Bild."""
    l, t, r, b = obj.box()
    nl, nt, nr, nb = crop if crop is not None else replace(obj, crop=None).box()
    sx, sy = obj.w_mm / (r - l), obj.h_mm / (b - t)          # mm je Pixel (ungedreht)
    u0, v0 = (nl - l) * sx, (nt - t) * sy
    w, h = (nr - nl) * sx, (nb - nt) * sy
    corners = [_image_point(obj, u0, v0), _image_point(obj, u0 + w, v0 + h)]
    changed = copy.deepcopy(obj)
    changed.crop = crop
    changed.x_mm = round(min(p[0] for p in corners), _DECIMALS)
    changed.y_mm = round(min(p[1] for p in corners), _DECIMALS)
    changed.w_mm, changed.h_mm = round(w, _DECIMALS), round(h, _DECIMALS)
    return changed


def original_size(obj: ImageObject) -> ImageObject:
    """Kopie in Größe 1:1 (``ImageObject.natural_mm``); die linke obere Ecke bleibt."""
    changed = copy.deepcopy(obj)
    changed.w_mm, changed.h_mm = (round(v, _DECIMALS) for v in obj.natural_mm())
    return changed


def set_keep_ratio(obj: ImageObject, keep: bool) -> ImageObject:
    """Kopie mit „Seitenverhältnis beibehalten“; beim Einschalten folgt die Höhe der Breite
    (das Bild füllt seinen Rahmen wieder ganz). Die linke obere Ecke bleibt."""
    changed = copy.deepcopy(obj)
    changed.keep_ratio = keep
    if keep:
        l, t, r, b = obj.box()
        changed.h_mm = round(obj.w_mm * (b - t) / (r - l), _DECIMALS)
    return changed


def proportional(rect: Rect, key: str, value: float) -> Rect:
    """``rect`` mit Breite (``key`` „w“) bzw. Höhe („h“) ``value``, das andere Maß im selben
    Verhältnis; die linke obere Ecke bleibt (Feld im Bereich „Position“)."""
    old = rect.w if key == "w" else rect.h
    factor = value / old if old > 0 else 1.0
    return _rounded(Rect(rect.x, rect.y, rect.w * factor, rect.h * factor))


def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) -> TextObject:
    """Kopie mit allen Schriftgrößen (Grundgröße und Stücke) × ``factor``, auf 4–100 pt begrenzt.

    Der Faktor wird so begrenzt, dass die Verhältnisse erhalten bleiben; nur wenn die Größen
    schon weiter auseinanderliegen als 4–100 pt, wird jede Größe für sich begrenzt.
    ``base_pt``: wirksame Grundgröße (``RenderedObject.base_pt``) für Text mit automatischer
    Größe – Stücke mit eigener Größe beziehen sich dann auf 12 pt und werden umgerechnet.
    """
    _text_only(obj)
    if factor <= 0:
        raise ValueError(_("Factor must be greater than 0, not {factor!r}.").format(factor=factor))
    scaled = copy.deepcopy(obj)
    spans = [span for para in scaled.paragraphs for span in para.spans
             if span.size_pt is not None]
    if obj.size_pt is None:
        if base_pt is None:
            raise ValueError(_("Text with automatic font size needs the effective base size "
                               "(base_pt) for scaling."))
        if base_pt <= 0:
            raise ValueError(_("Font size must be greater than 0, not {size!r}.").format(size=base_pt))
        for span in spans:                     # Bezug 12 pt → Bezug Grundgröße
            span.size_pt = span.size_pt * base_pt / REF_PT
        scaled.size_pt = base_pt
    sizes = [scaled.size_pt, *(span.size_pt for span in spans)]
    if min(sizes) <= 0:
        raise ValueError(_("Font size must be greater than 0, not {size!r}.").format(size=min(sizes)))
    low, high = MIN_PT / min(sizes), MAX_PT / max(sizes)
    if low <= high:                            # Grenze nur in Richtung des Faktors
        factor = min(max(factor, min(low, 1.0)), max(high, 1.0))

    def resize(size: float) -> float:
        # Größen außerhalb 4–100 pt werden nicht hineingezogen, nur nicht weiter hinaus
        return min(max(round(size * factor, 1), min(MIN_PT, size)), max(MAX_PT, size))

    scaled.size_pt = resize(scaled.size_pt)
    for span in spans:
        span.size_pt = resize(span.size_pt)
    return scaled


def outside_indices(rendered: list[RenderedObject], size: tuple[int, int],
                    objects: list[Object] | None = None) -> list[int]:
    """Indizes der schon gerenderten Objekte, deren Rahmen über das Etikett ``size``
    (Druckpunkte in Leserichtung, wie ``render.label_size``) ragt – ohne neu zu rendern.

    Leere Objekte zählen nicht: Rahmen ohne Fläche bzw. ``obj.is_empty()``, falls
    ``objects`` angegeben ist.
    """
    width, height = size
    outside = []
    for i, r in enumerate(rendered):
        if r.w == 0 or r.h == 0 or (objects is not None and objects[i].is_empty()):
            continue
        if r.x < 0 or r.y < 0 or r.x + r.w > width or r.y + r.h > height:
            outside.append(i)
    return outside


def objects_outside(doc: Document, model: str = "QL-600") -> list[int]:
    """Indizes der Objekte, die über das Etikett ragen (leere Objekte zählen nicht).

    Wirft wie ``render_document`` ``TextTooLarge``, wenn ein Objekt ohne Position bei fester
    Größe nicht passt – dann gibt es kein Druckbild, nach dem man fragen könnte.
    """
    size = label_size(doc, model)
    rendered = [render_object(obj, doc, model) for obj in doc.objects]
    return outside_indices(rendered, size, doc.objects)


# --- Reiter „Layout“ ----------------------------------------------------------------
def align_objects(objs: list[Object], rendered: list[RenderedObject], mode: str,
                  area: Rect | None = None, grow: str | None = None) -> list[Object]:
    """Kopien der Objekte, ausgerichtet wie ``align`` – mit ``area`` am Papier, sonst aneinander.

    Gerechnet wird mit den Rahmen, wie sie im Modell stehen (``exact_rect``); ein Objekt ohne
    Position bekommt seine Lage und wirksame Schriftgröße fest.
    ``grow`` (``growing_axis``): Am Papier sitzt die Auswahl in dieser Achse bei jedem Modus
    (Anfang, Mitte, Ende) mit ihrem Umriss am Anfang des Bereichs (Rand in Bandrichtung) –
    das Etikett wächst bis Inhalt plus Rand, die Ränder an beiden Enden sind dann gleich.
    """
    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
    if area is not None and grow == ("x" if mode in ("left", "hcenter", "right") else "y"):
        if not rects:
            return []
        box = bounds(rects)
        shift = (area.x - box.x, 0.0) if grow == "x" else (0.0, area.y - box.y)
        moved = [r.at(r.x + shift[0], r.y + shift[1]) for r in rects]
    else:
        moved = align(rects, mode, area)
    return [set_frame(o, _rounded(rect), r) for o, r, rect in zip(objs, rendered, moved)]


def match_objects(objs: list[Object], rendered: list[RenderedObject],
                  mode: str) -> list[Object]:
    """Kopien mit der Größe des ersten Objekts (``same``, ``width``, ``height``); Ecke bleibt.
    Das erste (Bezug) bleibt unverändert dasselbe Objekt – so muss es nicht neu gerendert werden.

    Mit fester Rahmengröße (auch Bild ohne ``keep_ratio``, Strichcode) wird der Rahmen gesetzt.
    Text ohne feste Rahmengröße, Bilder mit ``keep_ratio`` und QR-Codes werden skaliert
    (Seitenverhältnis bleibt): bei „gleicher Größe“ mit dem Mittel aus Breiten- und Höhenverhältnis, sonst nach
    dem angeglichenen Maß. Hat der Bezug keine Fläche (leerer Text), bleibt alles unverändert.
    """
    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
    if not rects or rects[0].w <= 0 or rects[0].h <= 0:
        return list(objs)           # leerer Bezug (unsichtbarer Rahmen): nichts angleichen
    result = objs[:1]
    for obj, r, old, new in zip(objs[1:], rendered[1:], rects[1:], match_size(rects, mode)[1:]):
        uniform = (obj.keep_ratio if isinstance(obj, ImageObject) else obj.kind == "qr"
                   if isinstance(obj, BarcodeObject) else not obj.fit)
        if not uniform:
            result.append(set_frame(obj, _rounded(new), r))
            continue
        fx = new.w / old.w if old.w else 1.0
        fy = new.h / old.h if old.h else 1.0
        factor = {"same": (fx * fy) ** 0.5, "width": fx, "height": fy}[mode]
        if not isinstance(obj, TextObject):
            result.append(place(obj, _rounded(Rect(old.x, old.y, old.w * factor,
                                                   old.h * factor)), r.dpi))
        else:
            result.append(place(scale_text(obj, factor, base_pt=r.base_pt), _rounded(old), r.dpi))
    return result


def maximize_object(obj: Object, rendered: RenderedObject, area: Rect, doc: Document,
                    model: str = "QL-600") -> Object:
    """Kopie, so groß wie möglich mittig in ``area`` (Seitenverhältnis bleibt).

    Mit festem Rahmen (Bild, feste Rahmengröße) wird der Rahmen gesetzt, bei Barcodes die
    größte Modulbreite, die hineinpasst; sonst wird die Schrift skaliert und das Ergebnis
    gerendert, damit es sicher hineinpasst und genau mittig steht.
    """
    grow = growing_axis(doc)
    if isinstance(obj, BarcodeObject):
        return _maximize_barcode(obj, exact_rect(obj, rendered), area, grow, rendered.dpi)
    if _framed(obj):
        return set_frame(obj, _rounded(maximize(exact_rect(obj, rendered), area, grow)),
                         rendered)
    shown = object_rect(rendered)
    target = maximize(shown, area, grow)
    factor = target.w / shown.w if shown.w else 1.0
    scaled = scale_text(obj, factor, base_pt=rendered.base_pt)
    best = None
    for __ in range(6):                       # Schrift wächst nicht ganz linear: nachregeln
        scaled.x_mm, scaled.y_mm = area.x, area.y
        size = object_rect(render_object(scaled, doc, model))
        if not (size.w and size.h):
            over = 1.0
        else:                                # in der mitwachsenden Achse begrenzt nichts
            over = {"x": area.h / size.h, "y": area.w / size.w}.get(
                grow, min(area.w / size.w, area.h / size.h))
        if over >= 1:
            best = (scaled, size)            # passt – weiter nur, wenn deutlich Platz bleibt
        if 1 <= over <= 1.01 or over < 1 and scaled.size_pt <= MIN_PT:
            break
        rescaled = scale_text(scaled, over * 0.995)
        if _sizes_of(rescaled) == _sizes_of(scaled):
            break                            # Grenze 4–100 pt erreicht
        scaled = rescaled
    scaled, size = best or (scaled, size)
    start = exact_rect(obj, rendered)
    return place(scaled, _rounded(Rect(start.x if grow == "x" else area.cx - size.w / 2,
                                       start.y if grow == "y" else area.cy - size.h / 2,
                                       size.w, size.h)))


def _maximize_barcode(obj: BarcodeObject, old: Rect, area: Rect, grow: str | None,
                      dpi: int = DPI) -> BarcodeObject:
    """Barcode so groß wie möglich mittig in ``area``: größte Modulbreite, die hineinpasst
    (abgerundet); Strichcodes füllen die Höhe für sich. In der mitwachsenden Achse begrenzt das
    Etikett nicht – dort bleibt der Anfang (und bei Strichcodes das Maß). Passt nicht einmal
    1 Druckpunkt je Modul, bleibt der Barcode, wie er ist."""
    qr = obj.kind == "qr"
    aw = (math.inf if qr else old.w) if grow == "x" else area.w
    ah = (math.inf if qr else old.h) if grow == "y" else area.h
    w, h = (ah, aw) if obj.rotation in (90, 270) else (aw, ah)      # ungedreht
    try:
        count = barcodes.modules(obj)
    except barcodes.BarcodeError:
        return copy.deepcopy(obj)
    module = math.floor((min(w, h) if qr else w) * dpi / 25.4 / count + _EPS)
    if module < 1:
        return copy.deepcopy(obj)
    sized = copy.deepcopy(obj)
    sized.module = min(module, barcodes.max_module(dpi))
    if not qr:
        sized.h_mm = math.floor(min(max(h, BARCODE_MM[0]), BARCODE_MM[1]) * 1000 + _EPS) / 1000
    shown = barcode_rect(sized, dpi)
    sized.x_mm = round(old.x if grow == "x" else area.cx - shown.w / 2, _DECIMALS)
    sized.y_mm = round(old.y if grow == "y" else area.cy - shown.h / 2, _DECIMALS)
    return sized


def _sizes_of(obj: TextObject) -> list[float | None]:
    return [obj.size_pt, *(span.size_pt for para in obj.paragraphs for span in para.spans)]


def rotate(obj: Object, rendered: RenderedObject, degrees: int) -> Object:
    """Kopie, um ``degrees`` (±90, im Uhrzeigersinn) gedreht; die Mitte des Rahmens bleibt.

    Ein Objekt ohne Position bekommt seine Lage und wirksame Schriftgröße fest.
    """
    old = exact_rect(obj, rendered)
    if _needs_size(obj):
        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
    turned = copy.deepcopy(obj)
    turned.rotation = (obj.rotation + degrees) % 360
    w, h = (old.h, old.w) if degrees % 180 else (old.w, old.h)
    return place(turned, _rounded(Rect(old.cx - w / 2, old.cy - h / 2, w, h)), rendered.dpi)


def reorder(items: list, indices: list[int], step: int) -> tuple[list, list[int]]:
    """Ausgewählte Einträge um einen Platz nach vorne (``step`` 1) bzw. hinten (−1) schieben.

    Liste = Zeichenreihenfolge (hinten → vorne). Ein Eintrag rückt nur an einem nicht
    ausgewählten vorbei; Ausgewählte am Ende bleiben stehen. Liefert die neue Liste und die
    neuen Plätze von ``indices`` (in derselben Reihenfolge).
    """
    order = list(range(len(items)))
    chosen = set(indices)
    positions = range(len(order) - 2, -1, -1) if step > 0 else range(1, len(order))
    for pos in positions:
        other = pos + (1 if step > 0 else -1)
        if order[pos] in chosen and order[other] not in chosen:
            order[pos], order[other] = order[other], order[pos]
    return [items[i] for i in order], [order.index(i) for i in indices]


def to_grid(obj: Object, x: bool = False, y: bool = False, w: bool = False,
            h: bool = False) -> Object:
    """Kopie mit den gewählten Werten auf ``GRID_MM`` gerundet – so, wie die Felder im Panel
    sie zeigen (nach Ziehen/Skalieren mit der Maus; Pfeiltasten verschieben genau).

    ``w``/``h`` meinen Breite/Höhe in Leserichtung (bei 90/270° also ``h_mm``/``w_mm``);
    fehlende Werte (None) bleiben. Ein eingerastetes Objekt liegt danach höchstens 0,05 mm
    neben der Hilfslinie – weniger als ein Druckpunkt (0,085 mm).
    """
    if obj.rotation in (90, 270):
        w, h = h, w
    grid = copy.deepcopy(obj)
    for attr, chosen in (("x_mm", x), ("y_mm", y), ("w_mm", w), ("h_mm", h)):
        value = getattr(grid, attr, None)               # Barcodes haben kein w_mm
        if chosen and value is not None:
            setattr(grid, attr, round(round(value / GRID_MM) * GRID_MM, 1))
    return grid


def _rounded(rect: Rect) -> Rect:
    """Rahmen fürs Modell: auf 1/1000 mm gerundet."""
    return Rect(*(round(v, _DECIMALS) for v in (rect.x, rect.y, rect.w, rect.h)))


# --- Schreibmodus -------------------------------------------------------------------
def to_object(point: tuple[float, float], rendered: RenderedObject,
              rotation: int) -> tuple[float, float]:
    """Punkt auf dem Etikett (Druckpunkte in Leserichtung) → Objektkoordinaten: Druckpunkte
    relativ zur linken oberen Ecke des Rahmens vor der Drehung (wie ``TextLayout``).

    ``rendered``: das gerenderte Objekt (Rahmen nach der Drehung), ``rotation`` seine Drehung.
    Punkte außerhalb des Rahmens bleiben gültig (Treffer im überstehenden Text).
    """
    return _to_frame(point, (rendered.x, rendered.y, rendered.w, rendered.h), rotation)


def from_object(point: tuple[float, float], rendered: RenderedObject,
                rotation: int) -> tuple[float, float]:
    """Umkehrung von ``to_object``: Objektkoordinaten → Punkt auf dem Etikett (Druckpunkte)."""
    return _from_frame(point, (rendered.x, rendered.y, rendered.w, rendered.h), rotation)


def _unturned(frame: tuple[float, float, float, float], rotation: int) -> tuple[float, float]:
    """Rahmengröße (Breite, Höhe) vor der Drehung."""
    if rotation not in ROTATIONS:
        raise ValueError(_("Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees").format(
            rotation=rotation))
    __, __, w, h = frame
    return (h, w) if rotation in (90, 270) else (w, h)


def _from_frame(point: tuple[float, float], frame: tuple[float, float, float, float],
                rotation: int) -> tuple[float, float]:
    """Punkt im ungedrehten Rahmen → Etikett; ``frame`` (x, y, w, h) nach der Drehung, in
    beliebiger Einheit. Gedreht wird im Uhrzeigersinn wie ``render._turn``."""
    u, v = point
    x, y = frame[:2]
    w, h = _unturned(frame, rotation)
    return {0: (x + u, y + v), 90: (x + h - v, y + u),
            180: (x + w - u, y + h - v), 270: (x + v, y + w - u)}[rotation]


def _to_frame(point: tuple[float, float], frame: tuple[float, float, float, float],
              rotation: int) -> tuple[float, float]:
    """Umkehrung von ``_from_frame``."""
    px, py = point[0] - frame[0], point[1] - frame[1]
    w, h = _unturned(frame, rotation)
    return {0: (px, py), 90: (py, h - px), 180: (w - px, h - py), 270: (w - py, px)}[rotation]


def anchor_align(obj: TextObject) -> str:
    """Textposition, nach der sich der Rahmen beim Wachsen richtet (``anchor_after_edit``):
    die gemeinsame der Absätze; haben sie verschiedene, bleibt die linke Kante („left“)."""
    _text_only(obj)
    aligns = {para.align for para in obj.paragraphs}
    return aligns.pop() if len(aligns) == 1 else "left"


def anchor_after_edit(obj: TextObject, old: RenderedObject,
                      new: RenderedObject) -> tuple[float, float]:
    """Neue Position (``x_mm``, ``y_mm``) eines Objekts ohne feste Rahmengröße, nachdem sein
    Text beim Tippen gewachsen oder geschrumpft ist – der Text bleibt stehen.

    ``obj``: das bearbeitete Objekt, noch an der alten Position; ``old``: gerendert vor der
    Bearbeitung, ``new``: ``obj`` gerendert. Fest bleibt der Punkt ``TextLayout.anchor`` zur
    Textposition ``anchor_align(obj)``: in Leserichtung des Texts die linke Kante (links,
    Blocksatz, gemischt), die rechte Kante (rechts) bzw. die Mitte (zentriert) und in der
    Höhe die Oberkante der ersten Zeile – bei gedrehten Objekten entsprechend gedreht.
    Nur für Objekte mit Position: eines ohne Position bleibt mittig auf dem Etikett, der
    Aufrufer setzt dort keine Position.
    """
    align = anchor_align(obj)                  # nur Text (TypeError bei Bildern)
    start = exact_rect(obj, old)
    # Lage des festen Punkts relativ zur linken oberen Ecke des Rahmens (Druckpunkte)
    ox, oy = from_object(old.layout.anchor(align), old, obj.rotation)
    nx, ny = from_object(new.layout.anchor(align), new, obj.rotation)
    dpi = old.dpi
    return (round(start.x + _mm(ox - old.x, dpi) - _mm(nx - new.x, dpi), _DECIMALS),
            round(start.y + _mm(oy - old.y, dpi) - _mm(ny - new.y, dpi), _DECIMALS))


def frame_area(doc: Document, model: str = "QL-600",
               size: tuple[int, int] | None = None) -> Rect | None:
    """Innenraum des Zierrahmens in mm (Ausrichten am Etikett, Einrasten); None ohne Rahmen."""
    box = frame_box(doc, model, size)
    return None if box is None else Rect(*(_mm(v, _label_dpi(doc)) for v in box))


def fill_anchored(doc: Document, columns: list[str], row: list[str], model: str = "QL-600",
                  keep: int | None = None) -> Document:
    """``series.fill`` – und frei platzierte Texte ohne feste Rahmengröße behalten den Punkt
    ihrer Textposition (wie beim Tippen, ``anchor_after_edit``): „mittig“ und „rechts“ gelten
    für jede Zeile, nicht nur für die Platzhalter. Nur zum Lesen wie ``fill``."""
    from .series import fill
    filled = fill(doc, columns, row, keep)
    for old, new in zip(doc.objects, filled.objects):
        if (new is old or not isinstance(new, TextObject) or not new.positioned or new.fit
                or anchor_align(new) == "left" and new.rotation == 0):
            continue                                  # links ohne Drehung: Kante bleibt ohnehin
        try:
            x, y = anchor_after_edit(new, render_object(old, doc, model),
                                     render_object(new, filled, model))
        except ValueError:                            # passt nicht: Renderfehler meldet das Rendern
            continue
        new.x_mm, new.y_mm = x, y                     # ``new`` ist eine Kopie (fill)
    return filled
