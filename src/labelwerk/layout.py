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
_DECIMALS = 3              # Positionen/Rahmen im Modell: auf 1/1000 mm


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


def fix_size(obj: TextObject, base_pt: float) -> TextObject:
    """Kopie mit der wirksamen Grundgröße ``base_pt`` als fester Schriftgröße, ohne Rahmengröße.

    Stücke mit eigener Größe behalten ihr Verhältnis; das Bild bleibt gleich.
    """
    base_pt = round(base_pt, 1)            # wie scale_text; Stücke rechnen mit derselben Größe
    factor = 1.0 if obj.size_pt is None else base_pt / obj.size_pt
    fixed = scale_text(obj, factor, base_pt=base_pt)
    fixed.fit = False
    return fixed


def exact_rect(obj: TextObject, rendered: RenderedObject) -> Rect:
    """Rahmen in mm, wie er im Modell steht (ohne Rundung auf Druckpunkte).

    Position aus ``x_mm``/``y_mm``, Größe bei fester Rahmengröße aus ``w_mm``/``h_mm``
    (gedreht), sonst wie gerendert; ein Objekt ohne Position steht, wo es gerendert wurde.
    """
    r = object_rect(rendered)
    x, y = ((obj.x_mm or 0.0, obj.y_mm or 0.0) if obj.positioned else (r.x, r.y))
    w, h = r.w, r.h
    if obj.positioned and obj.fit and obj.w_mm is not None and obj.h_mm is not None:
        w, h = (obj.h_mm, obj.w_mm) if obj.rotation in (90, 270) else (obj.w_mm, obj.h_mm)
    return Rect(x, y, w, h)


def _apply_change(obj: TextObject, rect: Rect, rendered: RenderedObject) -> Rect:
    """Änderung gegenüber dem gerenderten Rahmen auf den Rahmen im Modell übertragen.

    So verschieben Pfeiltasten genau um 0,1 mm, obwohl das Bild auf Druckpunkte gerundet ist;
    Reste der Umrechnung werden auf 1/1000 mm gerundet.
    """
    shown, exact = object_rect(rendered), exact_rect(obj, rendered)
    return Rect(*(round(e + n - s, _DECIMALS) for e, n, s in (
        (exact.x, rect.x, shown.x), (exact.y, rect.y, shown.y),
        (exact.w, rect.w, shown.w), (exact.h, rect.h, shown.h))))


def move(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
    """Kopie von ``obj``, verschoben auf ``rect`` (neue Lage des gerenderten Rahmens).

    Die Größe bleibt. Ein automatisch großes Objekt ohne eigenen Rahmen bekommt beim ersten
    Verschieben seine wirksame Größe (``rendered.base_pt``) als feste Schriftgröße – es sieht
    danach genauso aus.
    """
    target = _apply_change(obj, rect, rendered)
    if obj.size_pt is None or (obj.fit and not obj.positioned):
        obj = fix_size(obj, rendered.base_pt)
    moved = copy.deepcopy(obj)
    moved.x_mm, moved.y_mm = target.x, target.y
    return moved


def set_frame(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
    """Kopie mit dem Rahmen ``rect`` in mm, wie er im Modell steht (Zahlen im Panel „Position“).

    Mit fester Rahmengröße gelten Lage und Größe, sonst nur die Lage. Ein automatisch großes
    Objekt bekommt dabei seine wirksame Größe (``rendered.base_pt``) als feste Schriftgröße.
    """
    if not obj.fit and obj.size_pt is None:
        obj = fix_size(obj, rendered.base_pt)
    return place(obj, rect)


def resize(obj: TextObject, rect: Rect, rendered: RenderedObject, corner: bool) -> TextObject:
    """Kopie nach Ziehen an einem Anfasser: gerenderter Rahmen → ``rect``.

    Mit fester Rahmengröße ändert jeder Anfasser den Rahmen. Ohne skaliert eine Ecke
    (``corner``) die Schrift, eine Kante schaltet die feste Rahmengröße ein.
    """
    target = _apply_change(obj, rect, rendered)
    if obj.fit:
        return place(obj, target)
    if corner:
        old = object_rect(rendered)
        factor = ((rect.w * rect.h) / (old.w * old.h)) ** 0.5 if old.w and old.h else 1.0
        return place(scale_text(obj, factor, base_pt=rendered.base_pt), target)
    framed = copy.deepcopy(obj)
    framed.fit = True
    return place(framed, target)


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


# --- Reiter „Layout“ ----------------------------------------------------------------
def align_objects(objs: list[TextObject], rendered: list[RenderedObject], mode: str,
                  area: Rect | None = None) -> list[TextObject]:
    """Kopien der Objekte, ausgerichtet wie ``align`` – mit ``area`` am Papier, sonst aneinander.

    Gerechnet wird mit den Rahmen, wie sie im Modell stehen (``exact_rect``); ein Objekt ohne
    Position bekommt seine Lage und wirksame Schriftgröße fest.
    """
    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
    return [set_frame(o, _rounded(rect), r)
            for o, r, rect in zip(objs, rendered, align(rects, mode, area))]


def match_objects(objs: list[TextObject], rendered: list[RenderedObject],
                  mode: str) -> list[TextObject]:
    """Kopien mit der Größe des ersten Objekts (``same``, ``width``, ``height``); Ecke bleibt.

    Mit fester Rahmengröße wird der Rahmen gesetzt. Text ohne feste Rahmengröße wird
    skaliert (Seitenverhältnis bleibt): bei „gleicher Größe“ mit dem Mittel aus Breiten-
    und Höhenverhältnis, sonst nach dem angeglichenen Maß.
    """
    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
    result = [copy.deepcopy(objs[0])] if objs else []
    for obj, r, old, new in zip(objs[1:], rendered[1:], rects[1:], match_size(rects, mode)[1:]):
        if obj.fit:
            result.append(set_frame(obj, _rounded(new), r))
            continue
        fx = new.w / old.w if old.w else 1.0
        fy = new.h / old.h if old.h else 1.0
        factor = {"same": (fx * fy) ** 0.5, "width": fx, "height": fy}[mode]
        result.append(place(scale_text(obj, factor, base_pt=r.base_pt), _rounded(old)))
    return result


def maximize_object(obj: TextObject, rendered: RenderedObject, area: Rect, doc: Document,
                    model: str = "QL-600") -> TextObject:
    """Kopie, so groß wie möglich mittig in ``area`` (Seitenverhältnis bleibt).

    Mit fester Rahmengröße wird der Rahmen gesetzt; sonst wird die Schrift skaliert und
    das Ergebnis gerendert, damit es sicher hineinpasst und genau mittig steht.
    """
    if obj.fit:
        return set_frame(obj, _rounded(maximize(exact_rect(obj, rendered), area)), rendered)
    shown = object_rect(rendered)
    factor = maximize(shown, area).w / shown.w if shown.w else 1.0
    scaled = scale_text(obj, factor, base_pt=rendered.base_pt)
    for _ in range(5):                       # Schrift wächst nicht ganz linear: nachregeln
        scaled.x_mm, scaled.y_mm = area.x, area.y
        size = object_rect(render_object(scaled, doc, model))
        over = min(area.w / size.w, area.h / size.h) if size.w and size.h else 1.0
        if over >= 1 or scaled.size_pt <= MIN_PT:
            break
        scaled = scale_text(scaled, over * 0.995)
    return place(scaled, _rounded(Rect(area.cx - size.w / 2, area.cy - size.h / 2,
                                       size.w, size.h)))


def rotate(obj: TextObject, rendered: RenderedObject, degrees: int) -> TextObject:
    """Kopie, um ``degrees`` (±90, im Uhrzeigersinn) gedreht; die Mitte des Rahmens bleibt.

    Ein Objekt ohne Position bekommt seine Lage und wirksame Schriftgröße fest.
    """
    old = exact_rect(obj, rendered)
    if not obj.fit and obj.size_pt is None:
        obj = fix_size(obj, rendered.base_pt)
    turned = copy.deepcopy(obj)
    turned.rotation = (obj.rotation + degrees) % 360
    w, h = (old.h, old.w) if degrees % 180 else (old.w, old.h)
    return place(turned, _rounded(Rect(old.cx - w / 2, old.cy - h / 2, w, h)))


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


def _rounded(rect: Rect) -> Rect:
    """Rahmen fürs Modell: auf 1/1000 mm gerundet."""
    return Rect(*(round(v, _DECIMALS) for v in (rect.x, rect.y, rect.w, rect.h)))
