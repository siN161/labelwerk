"""Placement logic without Qt: snapping, aligning, matching size, scaling.

All rectangles in mm in reading direction, origin = top left corner of the label
(like ``TextObject.x_mm``/``y_mm``). The GUI only converts to screen coordinates.
Exception edit mode (``to_object``/``from_object``): points in dots like
``RenderedObject`` and ``TextLayout`` – so the canvas calculates without a detour via mm.

Image objects behave like text with a fixed frame size (``_framed``); functions only
for fonts (``scale_text``, ``fix_size``, edit mode) reject them with ``TypeError``.
Barcodes have a frame made of module width (whole dots) and height (``_barcode_frame``).
"""
from __future__ import annotations

import copy
import math
from collections.abc import Sequence
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
_EPS = 1e-6                # rounding tolerance when comparing mm values
_DECIMALS = 3              # positions/frames in the model: to 1/1000 mm
GRID_MM = 0.1              # grid of the position fields: dragging/scaling ends on it


def _mm(dots: float, dpi: int = DPI) -> float:
    return dots * 25.4 / dpi


def change_label(doc: Document, label_id: str) -> None:
    """Other label for ``doc`` (is modified). If it has a different resolution, barcodes keep
    their width in mm: module width in the dots of the new printer (whole dots, 1–``max_module``)."""
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
    """Rectangle in mm: top left corner ``x``/``y``, width ``w``, height ``h``."""
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
    """Result of snapping: shift in mm and guide lines ``("x" | "y", mm)``."""
    dx: float = 0.0
    dy: float = 0.0
    guides: list[tuple[str, float]] = field(default_factory=list)


# --- Label ------------------------------------------------------------------------
def object_rect(rendered: RenderedObject) -> Rect:
    """Frame of a rendered object in mm."""
    dpi = rendered.dpi
    return Rect(_mm(rendered.x, dpi), _mm(rendered.y, dpi), _mm(rendered.w, dpi),
                _mm(rendered.h, dpi))


def label_rect(doc: Document, model: str = "QL-600") -> Rect:
    """Whole label in mm (with automatic length as long as ``render_document`` makes it)."""
    w, h = label_size(doc, model)
    return Rect(0.0, 0.0, _mm(w, _label_dpi(doc)), _mm(h, _label_dpi(doc)))


def growing_axis(doc: Document) -> str | None:
    """Axis in reading direction ("x"/"y") in which the label grows with the objects
    (continuous tape with automatic length), otherwise None.

    Edge and centre of the label are not fixed in this axis – they move with the
    outermost object.
    """
    if get_label(doc.label_id).height is not None or doc.length_mm is not None:
        return None
    return "x" if doc.orientation == "horizontal" else "y"


def printable_area(doc: Document, model: str = "QL-600",
                   size: tuple[int, int] | None = None) -> Rect:
    """Printable area: label minus margin along the tape direction or across it.

    ``size``: already known label size (``render.label_size``) – then nothing is rendered.
    """
    w, h = size if size is not None else label_size(doc, model)
    mx, my = label_margins(doc, model)
    dpi = _label_dpi(doc)
    return Rect(_mm(mx, dpi), _mm(my, dpi), _mm(w - 2 * mx, dpi), _mm(h - 2 * my, dpi))


# --- Snapping ---------------------------------------------------------------------
def snap(moving: Rect, targets: list[Rect], area: Rect, tolerance_mm: float,
         label: Rect | None = None, grow: str | None = None, inner: Rect | None = None) -> Snap:
    """Let edges and centre of ``moving`` snap to nearby lines.

    Candidates: edges and centre of the printable area, of the label, of the inner space
    of a decorative frame (``inner``, if given) and of the other objects. Per axis the nearest candidate
    within the tolerance wins (limit included); ``guides`` names all lines that are hit
    after snapping. ``grow`` (``growing_axis``): in this axis label and area offer only
    their start – centre and end move with the object.
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
    """Smallest shift of a point onto a candidate and the lines hit afterwards."""
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


# --- Align, size ------------------------------------------------------------------
def bounds(rects: list[Rect]) -> Rect:
    """Enclosing rectangle (e.g. of the selection); at least one rectangle required."""
    x, y = min(r.x for r in rects), min(r.y for r in rects)
    return Rect(x, y, max(r.right for r in rects) - x, max(r.bottom for r in rects) - y)


def align(rects: list[Rect], mode: str, area: Rect | None = None) -> list[Rect]:
    """Align rectangles – with ``area`` to the paper, otherwise to each other.

    Reference to each other: outermost edge or centre of the selection; a single rectangle
    without ``area`` stays where it is.
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
    """Match the size to the first rectangle (``same``, ``width``, ``height``); corner stays."""
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
    """As large as possible in ``area`` with the same aspect ratio, centred in it.

    ``grow`` (``growing_axis``): in this axis the label grows with it – there the area
    does not limit, the rectangle is only fitted across and keeps its start.
    An empty area (width or height ≤ 0) leaves the rectangle unchanged.
    """
    if area.w <= 0 or area.h <= 0:
        return rect
    if rect.w > 0 and rect.h > 0:
        factor = {"x": area.h / rect.h, "y": area.w / rect.w}.get(
            grow, min(area.w / rect.w, area.h / rect.h))
        rect = replace(rect, w=rect.w * factor, h=rect.h * factor)
    return rect.at(rect.x if grow == "x" else area.cx - rect.w / 2,
                   rect.y if grow == "y" else area.cy - rect.h / 2)


# --- Objects ----------------------------------------------------------------------
Object = TextObject | ImageObject | BarcodeObject


def _framed(obj: Object) -> bool:
    """Fixed frame in ``w_mm``/``h_mm``: image or text with a fixed frame size."""
    return isinstance(obj, ImageObject) or isinstance(obj, TextObject) and obj.fit


def _needs_size(obj: Object) -> bool:
    """Text with automatic font size without a fixed frame: gets its effective size fixed
    when placed (``fix_size``)."""
    return isinstance(obj, TextObject) and not obj.fit and obj.size_pt is None


def _text_only(obj: Object) -> None:
    if not isinstance(obj, TextObject):
        raise TypeError(_("Only for text objects, not for {type}.").format(type=type(obj).__name__))


def place(obj: Object, rect: Rect, dpi: int = DPI) -> Object:
    """Copy of ``obj`` at ``rect``; with a fixed frame also width/height (unrotated), with
    barcodes module width and height (``_barcode_frame``)."""
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
    """``obj`` (is modified) for a frame ``w`` × ``h`` mm (unrotated): module width rounded to
    whole dots (``down``: rounded down – certainly fits), 1–``max_module``;
    linear codes: height ``h`` (2–100 mm). QR is square: the dimension that changes more
    counts. If the content cannot be encoded, the module width stays."""
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
    """Frame of a barcode in mm (after rotating) from module width and height, as it is
    rendered; None if the content cannot be encoded."""
    try:
        w = _mm(barcodes.modules(obj) * obj.module, dpi)
    except barcodes.BarcodeError:
        return None
    h = w if obj.kind == "qr" else obj.h_mm
    if obj.rotation in (90, 270):
        w, h = h, w
    return Rect(obj.x_mm, obj.y_mm, w, h)


def fix_size(obj: TextObject, base_pt: float, dpi: int = DPI) -> TextObject:
    """Copy with the effective base size ``base_pt`` as a fixed font size, without frame size.

    Pieces with their own size keep their ratio; the image stays the same: every size
    gets the shortest decimal number (from 0.1 pt) that gives the same print size.
    """
    _text_only(obj)
    base_dots = round(base_pt * dpi / 72)
    fixed = copy.deepcopy(obj)
    fixed.size_pt, fixed.fit = round(base_pt, 1), False   # gives base_dots again
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
    """Frame in mm as it is in the model (without rounding to dots).

    Position from ``x_mm``/``y_mm``, size with a fixed frame (image, fixed frame size) from
    ``w_mm``/``h_mm`` (rotated), with barcodes from content, module and ``h_mm`` (``barcode_rect``; invalid
    content: as rendered), otherwise as rendered; an object without a position is where it was rendered.
    """
    r = object_rect(rendered)
    x, y = ((obj.x_mm or 0.0, obj.y_mm or 0.0) if obj.positioned else (r.x, r.y))
    w, h = r.w, r.h
    if isinstance(obj, BarcodeObject) and (own := barcode_rect(obj, rendered.dpi)) is not None:
        w, h = own.w, own.h                     # from content and module (also with an outdated image)
    if obj.positioned and _framed(obj) and obj.w_mm is not None and obj.h_mm is not None:
        w, h = (obj.h_mm, obj.w_mm) if obj.rotation in (90, 270) else (obj.w_mm, obj.h_mm)
    return Rect(x, y, w, h)


def _apply_change(obj: Object, rect: Rect, rendered: RenderedObject) -> Rect:
    """Transfer a change relative to the rendered frame to the frame in the model.

    This way arrow keys move by exactly 0.1 mm although the image is rounded to dots;
    remainders of the conversion are rounded to 1/1000 mm.
    """
    shown, exact = object_rect(rendered), exact_rect(obj, rendered)
    return Rect(*(round(e + n - s, _DECIMALS) for e, n, s in (
        (exact.x, rect.x, shown.x), (exact.y, rect.y, shown.y),
        (exact.w, rect.w, shown.w), (exact.h, rect.h, shown.h))))


def move(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
    """Copy of ``obj``, moved to ``rect`` (new position of the rendered frame).

    The size stays. An automatically sized object without its own frame gets, on the first
    move, its effective size (``rendered.base_pt``) as a fixed font size – it looks
    exactly the same afterwards.
    """
    target = _apply_change(obj, rect, rendered)
    if isinstance(obj, TextObject) and (obj.size_pt is None or (obj.fit and not obj.positioned)):
        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
    moved = copy.deepcopy(obj)
    moved.x_mm, moved.y_mm = target.x, target.y
    return moved


def set_frame(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
    """Copy with the frame ``rect`` in mm as it is in the model (numbers in the "Position" section).

    With a fixed frame (image, fixed frame size) position and size apply, otherwise only the
    position. An automatically sized object gets its effective size (``rendered.base_pt``)
    as a fixed font size.
    """
    if _needs_size(obj):
        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
    return place(obj, rect, rendered.dpi)


def resize(obj: Object, rect: Rect, rendered: RenderedObject, handle: str) -> Object:
    """Copy after dragging the handle ``handle`` ("tl", "t", … "l"): rendered frame → ``rect``.

    With a fixed frame size every handle changes the frame. Without, a corner scales the
    font, an edge switches the fixed frame size on.
    An image with ``keep_ratio`` keeps its aspect ratio (``keep_aspect``, the same
    rule as the canvas preview); without it edges and corners distort the frame.
    Barcodes snap to whole dots per module (``_resize_barcode``).
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
    # a fixed frame size needs a fixed font: otherwise the frame would be lost when moving
    framed = (fix_size(obj, rendered.base_pt, rendered.dpi) if obj.size_pt is None
              else copy.deepcopy(obj))
    framed.fit = True
    return place(framed, target, rendered.dpi)


def _resize_barcode(obj: BarcodeObject, target: Rect, old: Rect, handle: str,
                    dpi: int = DPI) -> BarcodeObject:
    """Barcode after dragging a handle: QR keeps the square (``keep_aspect``); with linear codes
    the dimension across the bars changes the module width, the other the height. After snapping,
    what the handle holds stays (opposite edge, otherwise the centre)."""
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
    """Frame ``new`` (after dragging the handle ``handle``) with the aspect ratio of ``old``.

    What stays fixed follows from the handle alone (preview and result calculate the same):
    corner – the dimension that grew more counts, the opposite corner stays. Edge – the
    dragged dimension counts, the opposite edge stays, across it the centre (left/right:
    vertically centred, top/bottom: horizontally centred).
    """
    if old.w <= 0 or old.h <= 0:
        return new
    across, along = "l" in handle or "r" in handle, "t" in handle or "b" in handle
    fx, fy = new.w / old.w, new.h / old.h
    factor = max(fx, fy) if across and along else fx if across else fy
    w, h = old.w * factor, old.h * factor

    def start(old0: float, old1: float, size: float, moves_start: bool, moves_end: bool) -> float:
        if moves_start:
            return old1 - size                 # end stays
        if moves_end:
            return old0                        # start stays
        return (old0 + old1 - size) / 2        # across the dragged edge: centre stays

    return Rect(start(old.x, old.right, w, "l" in handle, "r" in handle),
                start(old.y, old.bottom, h, "t" in handle, "b" in handle), w, h)


# --- Image objects: insert and adjust --------------------------------------------
INSERT_GAP_MM = 2.0      # distance of an object inserted behind existing objects


def insert_frame(doc: Document, model: str, area: Rect, size: tuple[float, float],
                 at: tuple[float, float] | None = None) -> tuple[Rect, float]:
    """Frame for a new object of size ``size`` (mm) and the factor by which it was
    scaled down proportionally for that (1 = 1:1).

    Centred on ``at`` (click/drop point) or in the middle of ``area`` (printable
    area), pushed into the area. In the axis in which the label grows with it
    (``growing_axis``), only the largest label length limits, and the object does not begin
    before the start of the area.
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
    """Like ``insert_frame``, but rather rotated than shrunk (like ``print-file
    --rotate auto``): (frame on the label after rotating, rotation 0/90, factor).
    ``rotate=False`` (setting "do not rotate"): never rotated, like ``insert_frame``.

    ``others``: frames of existing (non-empty) objects. If the label grows with it
    (``growing_axis``), without an explicit point ``at``, and the frame would lie on one
    of them, it goes ``INSERT_GAP_MM`` behind the rearmost object
    (vertical: below, horizontal: to the right of it), further centred across.

    If the object does not fit the area 1:1 but does when rotated by 90°, it is placed rotated
    and 1:1; only if it fits in no orientation is it shrunk unrotated. The limits
    are the same as for ``insert_frame`` (in the growing axis the largest length).
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
    """New barcode of kind ``kind`` with sample content (``barcodes.SAMPLES``), placed like
    an image (``insert_placement``: centred in ``area``, on continuous tape behind ``others``).
    If it does not fit, with linear codes only the height gets smaller first; the module width shrinks
    only when it does not fit even rotated (``rotate``)."""
    dpi = _label_dpi(doc)
    obj = BarcodeObject(kind=kind, data=barcodes.SAMPLES[kind],
                        module=barcodes.insert_module(kind, dpi))
    count = barcodes.modules(obj)
    limit_w, limit_h = _insert_limits(doc, model, area)
    best = None                                       # (fits, module, rotation, height)
    for turn in (0, 90) if rotate else (0,):
        w, h = (limit_w, limit_h) if turn == 0 else (limit_h, limit_w)   # unrotated
        if kind == "qr":
            w = h = min(w, h)
        module = min(obj.module, math.floor(w * dpi / 25.4 / count + _EPS))
        fits = module >= 1 and (kind == "qr" or h >= BARCODE_MM[0])
        if best is None or (fits, module) > best[:2]:  # equally good: unrotated
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
    """Size (width, height in mm) that a new object may have at most 1:1: the
    area, in the growing axis (``growing_axis``) the largest label length."""
    grow = growing_axis(doc)
    if grow is None:
        return area.w, area.h
    mx, my = label_margins(doc, model)
    longest = _mm(length_limits(model)[1] - 2 * (mx if grow == "x" else my), _label_dpi(doc))
    return (longest, area.h) if grow == "x" else (area.w, longest)


def _image_point(obj: ImageObject, u: float, v: float) -> tuple[float, float]:
    """Point in the unrotated frame (mm from its top left corner) → label (mm)."""
    w, h = obj.w_mm, obj.h_mm
    du, dv = {0: (u, v), 90: (h - v, u), 180: (w - u, h - v), 270: (v, w - u)}[obj.rotation]
    return obj.x_mm + du, obj.y_mm + dv


def set_crop(obj: ImageObject, crop: tuple[int, int, int, int] | None) -> ImageObject:
    """Copy with the section ``crop`` (None = whole image). Scale and position of the content
    on the label stay: the frame shrinks to the section or grows around the image."""
    l, t, r, b = obj.box()
    nl, nt, nr, nb = crop if crop is not None else replace(obj, crop=None).box()
    sx, sy = obj.w_mm / (r - l), obj.h_mm / (b - t)          # mm per pixel (unrotated)
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
    """Copy in size 1:1 (``ImageObject.natural_mm``); the top left corner stays."""
    changed = copy.deepcopy(obj)
    changed.w_mm, changed.h_mm = (round(v, _DECIMALS) for v in obj.natural_mm())
    return changed


def set_keep_ratio(obj: ImageObject, keep: bool) -> ImageObject:
    """Copy with "keep aspect ratio"; when switching on, the height follows the width
    (the image fills its frame completely again). The top left corner stays."""
    changed = copy.deepcopy(obj)
    changed.keep_ratio = keep
    if keep:
        l, t, r, b = obj.box()
        changed.h_mm = round(obj.w_mm * (b - t) / (r - l), _DECIMALS)
    return changed


def proportional(rect: Rect, key: str, value: float) -> Rect:
    """``rect`` with width (``key`` "w") or height ("h") ``value``, the other dimension in the same
    ratio; the top left corner stays (field in the "Position" section)."""
    old = rect.w if key == "w" else rect.h
    factor = value / old if old > 0 else 1.0
    return _rounded(Rect(rect.x, rect.y, rect.w * factor, rect.h * factor))


def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) -> TextObject:
    """Copy with all font sizes (base size and pieces) × ``factor``, limited to 4–100 pt.

    The factor is limited so that the ratios are preserved; only if the sizes
    are already further apart than 4–100 pt is each size limited on its own.
    ``base_pt``: effective base size (``RenderedObject.base_pt``) for text with automatic
    size – pieces with their own size then refer to 12 pt and are converted.
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
        for span in spans:                     # reference 12 pt → reference base size
            span.size_pt = span.size_pt * base_pt / REF_PT
        scaled.size_pt = base_pt
    sizes = [scaled.size_pt, *(span.size_pt for span in spans)]
    if min(sizes) <= 0:
        raise ValueError(_("Font size must be greater than 0, not {size!r}.").format(size=min(sizes)))
    low, high = MIN_PT / min(sizes), MAX_PT / max(sizes)
    if low <= high:                            # limit only in the direction of the factor
        factor = min(max(factor, min(low, 1.0)), max(high, 1.0))

    def resize(size: float) -> float:
        # sizes outside 4–100 pt are not pulled in, only not pushed further out
        return min(max(round(size * factor, 1), min(MIN_PT, size)), max(MAX_PT, size))

    scaled.size_pt = resize(scaled.size_pt)
    for span in spans:
        span.size_pt = resize(span.size_pt)
    return scaled


def outside_indices(rendered: list[RenderedObject], size: tuple[int, int],
                    objects: list[Object] | None = None) -> list[int]:
    """Indices of the already rendered objects whose frame extends beyond the label ``size``
    (dots in reading direction, like ``render.label_size``) – without rendering again.

    Empty objects do not count: frames without area or ``obj.is_empty()`` if
    ``objects`` is given.
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
    """Indices of the objects that extend beyond the label (empty objects do not count).

    Like ``render_document``, raises ``TextTooLarge`` if an object without a position does not
    fit at a fixed size – then there is no print image one could ask about.
    """
    size = label_size(doc, model)
    rendered = [render_object(obj, doc, model) for obj in doc.objects]
    return outside_indices(rendered, size, doc.objects)


# --- LAYOUT tab ---------------------------------------------------------------
def align_objects(objs: list[Object], rendered: list[RenderedObject], mode: str,
                  area: Rect | None = None, grow: str | None = None,
                  min_length: float = 0.0, others: Sequence[Rect] = ()) -> list[Object]:
    """Copies of the objects, aligned like ``align`` – with ``area`` to the paper, otherwise to each other.

    The calculation uses the frames as they are in the model (``exact_rect``); an object without a
    position gets its position and effective font size fixed.
    ``grow`` (``growing_axis``): at the paper the selection sits in this axis in every mode
    (start, centre, end) with its outline at the start of the area (margin in tape direction) –
    the label grows to content plus margin, the margins at both ends are then equal.
    If everything together – the selection there and the other visible objects ``others``
    (frames in mm) – is shorter than the minimum length ``min_length`` (mm, print image), the
    label is clamped there – the selection then sits centred in it.
    """
    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
    if area is not None and grow == ("x" if mode in ("left", "hcenter", "right") else "y"):
        if not rects:
            return []
        box = bounds(rects)
        start, extent = (area.x, box.w) if grow == "x" else (area.y, box.h)
        placed = box.at(start, box.y) if grow == "x" else box.at(box.x, start)
        whole = bounds([placed, *others])
        end = whole.right if grow == "x" else whole.bottom
        if end + start < min_length:                     # label is clamped at the minimum length
            start = max(start, (min_length - extent) / 2)    # margin equal at both ends
        shift = (start - box.x, 0.0) if grow == "x" else (0.0, start - box.y)
        moved = [r.at(r.x + shift[0], r.y + shift[1]) for r in rects]
    else:
        moved = align(rects, mode, area)
    return [set_frame(o, _rounded(rect), r) for o, r, rect in zip(objs, rendered, moved)]


def match_objects(objs: list[Object], rendered: list[RenderedObject],
                  mode: str) -> list[Object]:
    """Copies with the size of the first object (``same``, ``width``, ``height``); corner stays.
    The first one (reference) stays the very same object – so it does not need to be rendered again.

    With a fixed frame size (also an image without ``keep_ratio``, linear code) the frame is set.
    Text without a fixed frame size, images with ``keep_ratio`` and QR codes are scaled
    (aspect ratio stays): for "same size" with the mean of width and height ratio, otherwise after
    the matched dimension. If the reference has no area (empty text), everything stays unchanged.
    """
    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
    if not rects or rects[0].w <= 0 or rects[0].h <= 0:
        return list(objs)           # empty reference (invisible frame): match nothing
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
    """Copy, as large as possible centred in ``area`` (aspect ratio stays).

    With a fixed frame (image, fixed frame size) the frame is set, with barcodes the
    largest module width that fits; otherwise the font is scaled and the result
    rendered, so that it certainly fits and is exactly centred.
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
    for __ in range(6):                       # the font does not grow quite linearly: readjust
        scaled.x_mm, scaled.y_mm = area.x, area.y
        size = object_rect(render_object(scaled, doc, model))
        if not (size.w and size.h):
            over = 1.0
        else:                                # in the growing axis nothing limits
            over = {"x": area.h / size.h, "y": area.w / size.w}.get(
                grow, min(area.w / size.w, area.h / size.h))
        if over >= 1:
            best = (scaled, size)            # fits – continue only if there is clearly room left
        if 1 <= over <= 1.01 or over < 1 and scaled.size_pt <= MIN_PT:
            break
        rescaled = scale_text(scaled, over * 0.995)
        if _sizes_of(rescaled) == _sizes_of(scaled):
            break                            # limit 4–100 pt reached
        scaled = rescaled
    scaled, size = best or (scaled, size)
    start = exact_rect(obj, rendered)
    return place(scaled, _rounded(Rect(start.x if grow == "x" else area.cx - size.w / 2,
                                       start.y if grow == "y" else area.cy - size.h / 2,
                                       size.w, size.h)))


def _maximize_barcode(obj: BarcodeObject, old: Rect, area: Rect, grow: str | None,
                      dpi: int = DPI) -> BarcodeObject:
    """Barcode as large as possible centred in ``area``: largest module width that fits
    (rounded down); linear codes fill the height on their own. In the growing axis the
    label does not limit – there the start stays (and with linear codes the dimension). If not even
    1 dot per module fits, the barcode stays as it is."""
    qr = obj.kind == "qr"
    aw = (math.inf if qr else old.w) if grow == "x" else area.w
    ah = (math.inf if qr else old.h) if grow == "y" else area.h
    w, h = (ah, aw) if obj.rotation in (90, 270) else (aw, ah)      # unrotated
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
    """Copy rotated by ``degrees`` (±90, clockwise); the centre of the frame stays.

    An object without a position gets its position and effective font size fixed.
    """
    old = exact_rect(obj, rendered)
    if _needs_size(obj):
        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
    turned = copy.deepcopy(obj)
    turned.rotation = (obj.rotation + degrees) % 360
    w, h = (old.h, old.w) if degrees % 180 else (old.w, old.h)
    return place(turned, _rounded(Rect(old.cx - w / 2, old.cy - h / 2, w, h)), rendered.dpi)


def reorder(items: list, indices: list[int], step: int) -> tuple[list, list[int]]:
    """Move selected entries one place forward (``step`` 1) or backward (−1).

    List = drawing order (back → front). An entry only moves past an unselected one;
    selected ones at the end stay. Returns the new list and the new places of
    ``indices`` (in the same order).
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
    """Copy with the chosen values rounded to ``GRID_MM`` – as the fields in the panel
    show them (after dragging/scaling with the mouse; arrow keys move exactly).

    ``w``/``h`` mean width/height in reading direction (for 90/270° thus ``h_mm``/``w_mm``);
    missing values (None) stay. A snapped object then lies at most 0.05 mm
    beside the guide line – less than one dot (0.085 mm).
    """
    if obj.rotation in (90, 270):
        w, h = h, w
    grid = copy.deepcopy(obj)
    for attr, chosen in (("x_mm", x), ("y_mm", y), ("w_mm", w), ("h_mm", h)):
        value = getattr(grid, attr, None)               # barcodes have no w_mm
        if chosen and value is not None:
            setattr(grid, attr, round(round(value / GRID_MM) * GRID_MM, 1))
    return grid


def _rounded(rect: Rect) -> Rect:
    """Frame for the model: rounded to 1/1000 mm."""
    return Rect(*(round(v, _DECIMALS) for v in (rect.x, rect.y, rect.w, rect.h)))


# --- Edit mode ----------------------------------------------------------------
def to_object(point: tuple[float, float], rendered: RenderedObject,
              rotation: int) -> tuple[float, float]:
    """Point on the label (dots in reading direction) → object coordinates: dots
    relative to the top left corner of the frame before rotation (like ``TextLayout``).

    ``rendered``: the rendered object (frame after rotation), ``rotation`` its rotation.
    Points outside the frame stay valid (hits in overhanging text).
    """
    return _to_frame(point, (rendered.x, rendered.y, rendered.w, rendered.h), rotation)


def from_object(point: tuple[float, float], rendered: RenderedObject,
                rotation: int) -> tuple[float, float]:
    """Inverse of ``to_object``: object coordinates → point on the label (dots)."""
    return _from_frame(point, (rendered.x, rendered.y, rendered.w, rendered.h), rotation)


def _unturned(frame: tuple[float, float, float, float], rotation: int) -> tuple[float, float]:
    """Frame size (width, height) before rotation."""
    if rotation not in ROTATIONS:
        raise ValueError(_("Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees").format(
            rotation=rotation))
    __, __, w, h = frame
    return (h, w) if rotation in (90, 270) else (w, h)


def _from_frame(point: tuple[float, float], frame: tuple[float, float, float, float],
                rotation: int) -> tuple[float, float]:
    """Point in the unrotated frame → label; ``frame`` (x, y, w, h) after rotation, in
    any unit. Rotation is clockwise like ``render._turn``."""
    u, v = point
    x, y = frame[:2]
    w, h = _unturned(frame, rotation)
    return {0: (x + u, y + v), 90: (x + h - v, y + u),
            180: (x + w - u, y + h - v), 270: (x + v, y + w - u)}[rotation]


def _to_frame(point: tuple[float, float], frame: tuple[float, float, float, float],
              rotation: int) -> tuple[float, float]:
    """Inverse of ``_from_frame``."""
    px, py = point[0] - frame[0], point[1] - frame[1]
    w, h = _unturned(frame, rotation)
    return {0: (px, py), 90: (py, h - px), 180: (w - px, h - py), 270: (w - py, px)}[rotation]


def anchor_align(obj: TextObject) -> str:
    """Text alignment by which the frame orients itself when growing (``anchor_after_edit``):
    the common one of the paragraphs; if they differ, the left edge ("left") stays."""
    _text_only(obj)
    aligns = {para.align for para in obj.paragraphs}
    return aligns.pop() if len(aligns) == 1 else "left"


def anchor_after_edit(obj: TextObject, old: RenderedObject,
                      new: RenderedObject) -> tuple[float, float]:
    """New position (``x_mm``, ``y_mm``) of an object without a fixed frame size after its
    text has grown or shrunk while typing – the text stays put.

    ``obj``: the edited object, still at the old position; ``old``: rendered before the
    edit, ``new``: ``obj`` rendered. The point ``TextLayout.anchor`` stays fixed for the
    text alignment ``anchor_align(obj)``: in the text's reading direction the left edge (left,
    justified, mixed), the right edge (right) or the centre (centred), and in
    height the top edge of the first line – rotated accordingly for rotated objects.
    Only for objects with a position: one without a position stays centred on the label, the
    caller sets no position there.
    """
    align = anchor_align(obj)                  # text only (TypeError for images)
    start = exact_rect(obj, old)
    # position of the fixed point relative to the top left corner of the frame (dots)
    ox, oy = from_object(old.layout.anchor(align), old, obj.rotation)
    nx, ny = from_object(new.layout.anchor(align), new, obj.rotation)
    dpi = old.dpi
    return (round(start.x + _mm(ox - old.x, dpi) - _mm(nx - new.x, dpi), _DECIMALS),
            round(start.y + _mm(oy - old.y, dpi) - _mm(ny - new.y, dpi), _DECIMALS))


def frame_area(doc: Document, model: str = "QL-600",
               size: tuple[int, int] | None = None) -> Rect | None:
    """Inner space of the decorative frame in mm (aligning to the label, snapping); None without a frame."""
    box = frame_box(doc, model, size)
    return None if box is None else Rect(*(_mm(v, _label_dpi(doc)) for v in box))


def fill_anchored(doc: Document, columns: list[str], row: list[str], model: str = "QL-600",
                  keep: int | None = None) -> Document:
    """``series.fill`` – and freely placed texts without a fixed frame size keep the point
    of their text alignment (as when typing, ``anchor_after_edit``): "centred" and "right" apply
    to every row, not only to the placeholders. Read-only like ``fill``."""
    from .series import fill
    filled = fill(doc, columns, row, keep)
    for old, new in zip(doc.objects, filled.objects):
        if (new is old or not isinstance(new, TextObject) or not new.positioned or new.fit
                or anchor_align(new) == "left" and new.rotation == 0):
            continue                                  # left without rotation: the edge stays anyway
        try:
            x, y = anchor_after_edit(new, render_object(old, doc, model),
                                     render_object(new, filled, model))
        except ValueError:                            # does not fit: rendering reports the render error
            continue
        new.x_mm, new.y_mm = x, y                     # ``new`` is a copy (fill)
    return filled
