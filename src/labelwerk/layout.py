"""Platzier-Logik ohne Qt: Einrasten, Ausrichten, Größe angleichen, Skalieren.

Alle Rechtecke in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts
(wie ``TextObject.x_mm``/``y_mm``). Die GUI rechnet nur in Bildschirmkoordinaten um.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace

from .document import MAX_PT, MIN_PT, Document, TextObject
from .labels import DPI
from .render import REF_PT, RenderedObject, label_margins, label_size, render_object

ALIGN_MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom")
SIZE_MODES = ("same", "width", "height")
_EPS = 1e-6                # Rundungsspielraum beim Vergleich von mm-Werten


def _mm(dots: float) -> float:
    return dots * 25.4 / DPI


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
    return Rect(_mm(rendered.x), _mm(rendered.y), _mm(rendered.w), _mm(rendered.h))


def label_rect(doc: Document, model: str = "QL-600") -> Rect:
    """Ganzes Etikett in mm (bei automatischer Länge so lang, wie ``render_document`` es macht)."""
    w, h = label_size(doc, model)
    return Rect(0.0, 0.0, _mm(w), _mm(h))


def printable_area(doc: Document, model: str = "QL-600") -> Rect:
    """Bedruckbarer Bereich: Etikett minus Rand in Bandlaufrichtung bzw. quer dazu."""
    w, h = label_size(doc, model)
    mx, my = label_margins(doc, model)
    return Rect(_mm(mx), _mm(my), _mm(w - 2 * mx), _mm(h - 2 * my))


# --- Einrasten --------------------------------------------------------------------
def snap(moving: Rect, targets: list[Rect], area: Rect, tolerance_mm: float,
         label: Rect | None = None) -> Snap:
    """Kanten und Mitte von ``moving`` an nahe Linien einrasten lassen.

    Kandidaten: Kanten und Mitte des bedruckbaren Bereichs, des Etiketts (falls angegeben)
    und der anderen Objekte. Je Achse gewinnt der nächste Kandidat innerhalb der Toleranz
    (Grenze eingeschlossen); ``guides`` nennt alle Linien, die nach dem Einrasten getroffen
    werden.
    """
    frames = [area, *([label] if label else []), *targets]
    dx, x_guides = _snap_axis((moving.x, moving.cx, moving.right),
                              [v for r in frames for v in (r.x, r.cx, r.right)], tolerance_mm)
    dy, y_guides = _snap_axis((moving.y, moving.cy, moving.bottom),
                              [v for r in frames for v in (r.y, r.cy, r.bottom)], tolerance_mm)
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
        raise ValueError(f"Unbekannte Ausrichtung {mode!r} – erlaubt: {', '.join(ALIGN_MODES)}")
    if area is None:
        if len(rects) < 2:
            return list(rects)
        area = bounds(rects)
    place = {
        "left": lambda r: r.at(area.x, r.y),
        "hcenter": lambda r: r.at(area.cx - r.w / 2, r.y),
        "right": lambda r: r.at(area.right - r.w, r.y),
        "top": lambda r: r.at(r.x, area.y),
        "vcenter": lambda r: r.at(r.x, area.cy - r.h / 2),
        "bottom": lambda r: r.at(r.x, area.bottom - r.h),
    }[mode]
    return [place(r) for r in rects]


def match_size(rects: list[Rect], mode: str) -> list[Rect]:
    """Größe an das erste Rechteck angleichen (``same``, ``width``, ``height``); Ecke bleibt."""
    if mode not in SIZE_MODES:
        raise ValueError(f"Unbekannte Größenangleichung {mode!r} – erlaubt: {', '.join(SIZE_MODES)}")
    if not rects:
        return []
    ref = rects[0]
    w = mode in ("same", "width")
    h = mode in ("same", "height")
    return [replace(r, w=ref.w if w else r.w, h=ref.h if h else r.h) for r in rects]


def maximize(rect: Rect, area: Rect) -> Rect:
    """Größtmöglich in ``area`` bei gleichem Seitenverhältnis, mittig darin."""
    if rect.w > 0 and rect.h > 0:
        factor = min(area.w / rect.w, area.h / rect.h)
        rect = replace(rect, w=rect.w * factor, h=rect.h * factor)
    return rect.at(area.cx - rect.w / 2, area.cy - rect.h / 2)


# --- Objekte ----------------------------------------------------------------------
def place(obj: TextObject, rect: Rect) -> TextObject:
    """Kopie von ``obj`` an ``rect``; bei fester Rahmengröße auch Breite/Höhe (ungedreht)."""
    placed = copy.deepcopy(obj)
    placed.x_mm, placed.y_mm = rect.x, rect.y
    if obj.fit:
        w, h = (rect.h, rect.w) if obj.rotation in (90, 270) else (rect.w, rect.h)
        placed.w_mm, placed.h_mm = w, h
    return placed


def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) -> TextObject:
    """Kopie mit allen Schriftgrößen (Grundgröße und Stücke) × ``factor``, auf 4–100 pt begrenzt.

    Der Faktor wird so begrenzt, dass die Verhältnisse erhalten bleiben; nur wenn die Größen
    schon weiter auseinanderliegen als 4–100 pt, wird jede Größe für sich begrenzt.
    ``base_pt``: wirksame Grundgröße (``RenderedObject.base_pt``) für Text mit automatischer
    Größe – Stücke mit eigener Größe beziehen sich dann auf 12 pt und werden umgerechnet.
    """
    if factor <= 0:
        raise ValueError(f"Faktor muss größer als 0 sein, nicht {factor!r}.")
    scaled = copy.deepcopy(obj)
    spans = [span for para in scaled.paragraphs for span in para.spans
             if span.size_pt is not None]
    if obj.size_pt is None:
        if base_pt is None:
            raise ValueError("Text mit automatischer Schriftgröße braucht die wirksame "
                             "Grundgröße (base_pt) zum Skalieren.")
        for span in spans:                     # Bezug 12 pt → Bezug Grundgröße
            span.size_pt = span.size_pt * base_pt / REF_PT
        scaled.size_pt = base_pt
    sizes = [scaled.size_pt, *(span.size_pt for span in spans)]
    low, high = MIN_PT / min(sizes), MAX_PT / max(sizes)
    if low <= high:
        factor = min(max(factor, low), high)

    def resize(size: float) -> float:
        return min(max(round(size * factor, 1), MIN_PT), MAX_PT)

    scaled.size_pt = resize(scaled.size_pt)
    for span in spans:
        span.size_pt = resize(span.size_pt)
    return scaled


def objects_outside(doc: Document, model: str = "QL-600") -> list[int]:
    """Indizes der Objekte, die über das Etikett ragen (leere Objekte zählen nicht)."""
    width, height = label_size(doc, model)
    outside = []
    for i, obj in enumerate(doc.objects):
        if obj.is_empty():
            continue
        r = render_object(obj, doc, model)
        if r.x < 0 or r.y < 0 or r.x + r.w > width or r.y + r.h > height:
            outside.append(i)
    return outside
