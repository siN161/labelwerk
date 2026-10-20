"""Canvas: label in true size and shape, objects (select, drag, snap,
scale by handles, create text, drop images), mm rulers, zoom, length handle.

Edit mode (``gui.text_edit_mode``): the frame being edited is solid and has no
handles; caret and selection arrive as a position in dots from the edit mode
(``set_edit_marks``), the canvas only draws them and reports mouse clicks into the frame."""
from __future__ import annotations

import math

from PIL import Image, ImageOps
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap,
                           QTransform)
from PySide6.QtWidgets import (QApplication, QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsView)

from .. import layout
from . import image_import
from ..i18n import _
from ..labels import DPI, Label, format_mm, length_limits, mm_text
from ..layout import Rect
from ..printer import DEFAULT_MODEL
from ..render import INK, PT, RenderedObject

MM = DPI / 25.4          # scene units (dots) per mm at 300 dpi; per label ``Canvas.mm``
RULER = 22               # ruler width in pixels
_CORNER_MM = 2           # corner radius of die-cut labels
_MARGIN_MM = 15          # grey margin around the label
START_ZOOM = 200         # percent; 100 % = true size
SNAP_PX = 6              # snapping: distance in screen pixels
HANDLE_PX = 8            # edge length of a handle in screen pixels
_DRAG_START_PX = 3       # dragging only starts after this much mouse movement (click ≠ move)
_MIN_FRAME_MM = 1        # smallest frame when scaling
HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")   # corners and edges, clockwise
_HANDLE_CURSORS = {
    "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
    "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
    "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
}
_GUIDE_COLOR = QColor("#E53935")
_TAPE_COLOR = QColor("#BDBDBD")    # lighter than the canvas, readable in every theme
_UNPRINTABLE_COLOR = QColor("#EBEBEB")   # unprintable strip: between label and rest of the tape
TOOL_MODES = ("select", "text")   # selection arrow, "Create text"
_EDIT_REACH_PX = 3                # edit mode: a click this close next to the frame still counts as inside
_SELECTION_ALPHA = 90             # selection: system colour at ≈ 35 % opacity


def to_qimage(img: Image.Image, ink: tuple[int, int, int] = (0, 0, 0)) -> QImage:
    """Print image as QImage; white becomes transparent so that the label shape stays visible.
    ``ink``: ink colour (``render.INK``, red objects on red/black labels)."""
    gray = img.convert("L")
    # Ink colour, alpha = 255 - L: over white this gives exactly the tone L (preview = print)
    rgba = Image.merge("RGBA", (*(Image.new("L", gray.size, c) for c in ink),
                                ImageOps.invert(gray)))
    return QImage(rgba.tobytes(), rgba.width, rgba.height, 4 * rgba.width,
                  QImage.Format.Format_RGBA8888).copy()


class ObjectItem(QGraphicsPixmapItem):
    """An object on the canvas: its image from ``render_object`` at its position.

    Coordinates in dots in reading direction; the parent item (``Canvas.sheet``) rotates
    for "horizontal" into print coordinates.
    """

    def __init__(self, index: int, rendered: RenderedObject, pixmap: QPixmap, keep_ratio: bool,
                 parent: QGraphicsRectItem, keep_aspect: bool = False):
        super().__init__(pixmap, parent)
        self.index = index
        self.rendered = rendered
        self.keep_ratio = keep_ratio     # corners scale the font: aspect ratio stays
        self.keep_aspect = keep_aspect   # edges also keep the ratio (image)
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setPos(rendered.x, rendered.y)
        self.setOffset(rendered.image_dx, rendered.image_dy)   # bleed: image extends beyond the frame
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def is_empty(self) -> bool:
        return self.rendered.w == 0 or self.rendered.h == 0

    def size(self) -> tuple[float, float]:
        """Frame size in dots; an empty text shows a placeholder (one line high)."""
        if self.is_empty():
            line = self.rendered.base_pt * self.rendered.dpi / 72
            return line / 2, line
        return self.rendered.w, self.rendered.h

    def frame(self) -> QRectF:
        """Frame in dots in reading direction (while dragging including preview stretch)."""
        return self.mapRectToParent(QRectF(0, 0, *self.size()))

    def frame_mm(self) -> Rect:
        f, mm = self.frame(), self.rendered.dpi / 25.4
        return Rect(f.x() / mm, f.y() / mm, f.width() / mm, f.height() / mm)


class Canvas(QGraphicsView):
    length_changed = Signal(object)   # new length in mm (float) or None = automatic
    zoom_changed = Signal(int)        # zoom in percent
    drag_finished = Signal()          # length handle released (after actual dragging)
    selection_changed = Signal(list)  # indices of the selected objects in order of selection
    objects_moved = Signal(list, list)         # indices, new frames (Rect, mm) after release
    object_resized = Signal(int, object, str)  # index, new frame (Rect, mm), handle ("tl" …)
    text_requested = Signal(float, float)      # "Create text": click on the label (mm, reading direction)
    edit_requested = Signal(int, object)       # edit text (double click): index, click point
                                               # (QPointF, dots in reading direction) or None
    edit_pressed = Signal(object, bool)        # edit mode: click into the frame (point, shift)
    edit_dragged = Signal(object)              # edit mode: dragging in the frame selects (point)
    edit_double_clicked = Signal(object)       # edit mode: double click selects a word
    edit_left = Signal()                       # edit mode: click next to the frame ends it
    object_clicked = Signal(int)               # click on an object (also one already selected)
    tool_changed = Signal(str)                 # tool: "select" | "text"
    dropped = Signal(object, object, float, float)  # dropped: files (list[Path]), image
                                               # (PIL or None), drop point (mm, reading direction)
    symbol_dropped = Signal(str, float, float)  # symbol dropped from the window: id, point (mm)

    def __init__(self, model: str = DEFAULT_MODEL):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#9E9E9E"))
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)             # mouse pointer over the handles
        self.setAcceptDrops(True)                          # drop images and image files
        self.dpi, self.mm = DPI, MM                        # resolution of the label, dots per mm
        self.set_model(model)
        self.zoom = START_ZOOM
        self.orientation = "vertical"
        self._scale = 1.0
        self.label: Label | None = None
        self.outline = self.printable = self.handle = self.tape = None
        self._tape = QRectF()
        self._cut_edges: list[str] = []
        self.sheet: QGraphicsRectItem | None = None        # label in reading direction (dots)
        self.objects: list[ObjectItem] = []
        self._pixmaps: dict[int, tuple[RenderedObject, QPixmap]] = {}
        self._selection: list[int] = []
        self._area = self._label_rect = Rect(0, 0, 0, 0)
        self._inner: Rect | None = None                    # inner area of the decorative frame (mm)
        self.frame_item: QGraphicsPixmapItem | None = None # decorative frame (below the objects)
        self._frame_source: Image.Image | None = None      # mask from which _frame_pixmap was made
        self._frame_pixmap = QPixmap()
        self._grow: str | None = None                      # growing axis (continuous tape)
        self._guides: list[tuple[str, float]] = []
        self._caption = ""
        self._drag: str | None = None                      # "length" | "move" | "resize"
        self._moved = False
        self._grab_offset = 0.0
        self._press = QPointF()
        self._grabbed = -1
        self._start: dict[int, QPointF] = {}
        self._resize_key = ""
        self._start_frame = QRectF()
        self._handle_offset = QPointF()
        self._handle_cursor = False
        self._tool = "select"
        self.read_only = False                             # view only (parcel label): no clicks
        self._editing: int | None = None                   # object in edit mode
        self._edit_frame = QRectF()                        # frame, caret, selection
        self._caret: QLineF | None = None                  # (dots in reading direction)
        self._marked: list[QRectF] = []
        self._caret_on = True
        self._caret_focus = True                           # the editor has keyboard focus
        self._blink = QTimer(self)
        self._blink.timeout.connect(self._toggle_caret)
        self._apply_zoom()

    # --- Content -----------------------------------------------------------
    def set_document(self, label: Label, size: tuple[int, int],
                     rendered: list[RenderedObject], orientation: str = "vertical",
                     area: Rect | None = None, keep_ratio: list[bool] | None = None,
                     grow: str | None = None, keep_aspect: list[bool] | None = None,
                     frame: Image.Image | None = None, inner: Rect | None = None) -> None:
        """Show the label (physical shape) and the individually rendered objects in it.

        ``size``: label in dots in reading direction (as ``render.label_size``);
        ``area``: printable area in mm (snapping); ``keep_ratio`` per object: corners
        scale the font (without fixed frame size); ``keep_aspect`` per object: edges
        also keep the aspect ratio (image); ``grow``: axis in which the label
        grows (``layout.growing_axis``) – only its start snaps there; ``frame``: mask of the
        decorative frame (``Rendered.frame``), lies below the objects and takes no clicks;
        ``inner``: its inner area in mm (snapping). The scene is always in
        print coordinates; for "horizontal" the view rotates by −90° so that the label appears in
        reading direction – the objects lie in ``sheet``, which counts in reading direction.
        """
        if orientation != self.orientation or label.dpi != self.dpi:
            self.orientation = orientation
            self.dpi, self.mm = label.dpi, label.dpi / 25.4   # scene in the label's dots
            self._apply_zoom()
        self.cancel_object_drag()
        scene = self.scene()
        scene.clear()
        self.label = label
        width, height = size
        horizontal = orientation == "horizontal"
        pw, ph = (height, width) if horizontal else (width, height)   # print image
        tw = label.total_width
        th = label.total_height or ph + 2 * label.feed_margin   # continuous tape: piece with feed
        path = QPainterPath()
        if label.shape == "round":
            path.addEllipse(0, 0, tw, th)
        elif label.shape == "die_cut":
            path.addRoundedRect(0, 0, tw, th, _CORNER_MM * self.mm, _CORNER_MM * self.mm)
        else:
            path.addRect(0, 0, tw, th)
        self.outline = scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))

        ox, oy = (tw - pw) / 2, (th - ph) / 2
        # Strips the printer does not print (across, along the feed or label edge):
        # light grey, display only – below the label content, no clicks, not in the print image
        printed = QPainterPath()
        printed.addRect(QRectF(ox, oy, pw, ph))
        self.unprintable = scene.addPath(path.subtracted(printed), QPen(Qt.PenStyle.NoPen),
                                         QBrush(_UNPRINTABLE_COLOR))
        self.unprintable.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.sheet = QGraphicsRectItem(0, 0, width, height)
        self.sheet.setPen(QPen(Qt.PenStyle.NoPen))
        # reading direction → print: for "horizontal" 90° clockwise as render_document
        self.sheet.setTransform(QTransform().translate(ox + pw, oy).rotate(90) if horizontal
                                else QTransform().translate(ox, oy))
        scene.addItem(self.sheet)
        self.frame_item = None
        if frame is not None:
            if frame is not self._frame_source:  # the renderer returns the same mask unchanged
                self._frame_source = frame
                self._frame_pixmap = QPixmap.fromImage(to_qimage(ImageOps.invert(frame)))
            self.frame_item = QGraphicsPixmapItem(self._frame_pixmap, self.sheet)
            self.frame_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            self.frame_item.setZValue(-1)
            self.frame_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._inner = inner
        self._pixmaps = {id(obj): (obj, self._pixmap(obj)) for obj in rendered}
        ratios = keep_ratio if keep_ratio is not None else [True] * len(rendered)
        aspects = keep_aspect if keep_aspect is not None else [False] * len(rendered)
        self.objects = [ObjectItem(i, obj, self._pixmaps[id(obj)][1], ratio, self.sheet, aspect)
                        for i, (obj, ratio, aspect) in enumerate(zip(rendered, ratios, aspects))]
        self._show_edit_cursor()
        self._label_rect = Rect(0, 0, width / self.mm, height / self.mm)
        self._area = area if area is not None else self._label_rect
        self._grow = grow
        dotted = QPen(QColor("#888888"), 1, Qt.PenStyle.DotLine)
        dotted.setCosmetic(True)
        if label.shape != "round" and area is not None:
            # printable area with all four margins (also in tape direction), in reading direction
            self.printable = QGraphicsRectItem(QRectF(area.x * self.mm, area.y * self.mm,
                                                      area.w * self.mm, area.h * self.mm), self.sheet)
            self.printable.setPen(dotted)
            self.printable.setZValue(-2)                 # below the decorative frame
        else:
            self.printable = scene.addRect(QRectF(ox, oy, pw, ph), dotted)

        self.handle = None
        self._tape = QRectF()
        self._cut_edges = []
        if label.shape == "endless":
            self._add_tape(scene, tw, th)
            dashed = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
            dashed.setCosmetic(True)
            scene.addLine(-2 * self.mm, th, tw + 2 * self.mm, th, dashed)
            self.handle = scene.addRect(QRectF(tw / 2 - 5 * self.mm, th + self.mm, 10 * self.mm, 2 * self.mm),
                                        QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.black))
            self.handle.setCursor(Qt.CursorShape.SizeHorCursor if self.orientation == "horizontal"
                                  else Qt.CursorShape.SizeVerCursor)
            self.handle.setToolTip(_("Drag: set the length · Double-click: automatic"))
            self.handle.setVisible(not self.read_only)
        self._caption = self._caption_for(th)
        margin = _MARGIN_MM * self.mm
        scene.setSceneRect(-margin, -margin, tw + 2 * margin, th + 2 * margin)
        self.set_selection([i for i in self._selection if self._selectable(i)])

    def _add_tape(self, scene: QGraphicsScene, tw: float, th: float) -> None:
        """Continuous tape as in the P-touch Editor: the start of the label in tape direction is a
        closed, solid edge; only the end carries the dashed cut line,
        behind it the tape continues as a light grey strip (scene y; for "horizontal" the
        view is rotated). Display only: does not react to the mouse and belongs neither to the
        print image nor to the label size."""
        self._tape = QRectF(0, th, tw, _MARGIN_MM * self.mm)
        self.tape = scene.addRect(self._tape, QPen(Qt.PenStyle.NoPen), QBrush(_TAPE_COLOR))
        self.tape.setZValue(-1)
        self.tape.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        edge = QPen(QColor("#555555"), 1)
        edge.setCosmetic(True)
        scene.addLine(0, 0, tw, 0, edge)
        self._cut_edges = ["end"]

    def tape_rect(self) -> QRectF:
        """Rest of the tape in scene coordinates (tape direction = scene y, below the label);
        empty for die-cut labels."""
        return QRectF(self._tape)

    def set_model(self, model: str) -> None:
        """Printer model: limits of the label length when dragging."""
        min_len, max_len = length_limits(model)
        self.min_mm, self.max_mm = min_len / MM, max_len / MM

    def cut_edges(self) -> list[str]:
        """Edges in tape direction with cut line: for continuous tape only the end ("end") –
        the start is closed; die-cut labels keep their appearance (empty)."""
        return list(self._cut_edges)

    def _pixmap(self, rendered: RenderedObject) -> QPixmap:
        """Create the pixmap per object image only once (unchanged object = same image).

        The cache holds on to the object image itself so that its id is not reissued."""
        cached = self._pixmaps.get(id(rendered))
        if cached is not None and cached[0] is rendered:
            return cached[1]
        return QPixmap.fromImage(to_qimage(rendered.image, INK[rendered.color]))

    # --- Selection ----------------------------------------------------------
    def selection(self) -> list[int]:
        return list(self._selection)

    def set_selection(self, indices: list[int]) -> None:
        chosen = [] if self.read_only else list(dict.fromkeys(i for i in indices
                                                              if self._selectable(i)))
        if chosen != self._selection:
            self._selection = chosen
            if self._drag not in ("move", "resize"):
                self._grabbed = -1       # numbers may have changed: do not hold on
            self.viewport().update()
            self.selection_changed.emit(self.selection())

    def select_all(self) -> None:
        """Select all objects; "Create text" ends in the process (back to the selection arrow)."""
        self.set_tool("select")
        self.set_selection(list(range(len(self.objects))))

    def _selectable(self, index: int) -> bool:
        return 0 <= index < len(self.objects)

    # --- Edit mode -----------------------------------------------------------
    def editing(self) -> int | None:
        """Object in edit mode (None = none)."""
        return self._editing

    def set_editing(self, index: int | None) -> None:
        """Show edit mode for an object or end it with None: frame solid,
        no handles, text cursor over the object; clicks into it report ``edit_pressed``."""
        self._editing = index
        if index is None:
            self._edit_frame, self._caret, self._marked = QRectF(), None, []
            self._blink.stop()
        self._show_edit_cursor()
        self.viewport().update()

    def set_edit_marks(self, frame: QRectF, caret: QLineF | None, marked: list[QRectF]) -> None:
        """Frame, caret and selection of the edit mode (dots in reading direction,
        like ``sheet``). The caret appears immediately and blinks at the system rate."""
        self._edit_frame, self._caret, self._marked = QRectF(frame), caret, list(marked)
        self._restart_blink()

    def set_caret_focus(self, focused: bool) -> None:
        """Show the caret only while the editor has keyboard focus – otherwise typed
        text lands elsewhere (e.g. in the "Font" field)."""
        self._caret_focus = focused
        self._restart_blink()

    def caret_shown(self) -> bool:
        """Is a caret shown in edit mode (blinking)?"""
        return self._editing is not None and self._caret is not None and self._caret_focus

    def _restart_blink(self) -> None:
        """Caret immediately visible, blinks at the system rate; off without focus."""
        self._caret_on = True
        flash = QApplication.cursorFlashTime()
        if flash > 0 and self.caret_shown():
            self._blink.start(flash // 2)
        else:
            self._blink.stop()                             # off or blinking disabled
        self.viewport().update()

    def caret_line(self) -> QLineF:
        """Caret in view coordinates (empty outside edit mode)."""
        if self._caret is None or self.sheet is None:
            return QLineF()
        return QLineF(self._view_point(self._caret.x1(), self._caret.y1()),
                      self._view_point(self._caret.x2(), self._caret.y2()))

    def selection_rects(self) -> list[QRectF]:
        """Selection in edit mode in view coordinates (one rectangle per line)."""
        return [self._view_rect(rect) for rect in self._marked] if self.sheet is not None else []

    def edit_frame_rect(self) -> QRectF:
        """Frame of the object in edit mode in view coordinates."""
        return self._view_rect(self._edit_frame) if self.sheet is not None else QRectF()

    def _view_rect(self, rect: QRectF) -> QRectF:
        return self.viewportTransform().mapRect(self.sheet.mapRectToScene(rect))

    def _in_edit_frame(self, pos: QPointF) -> bool:
        reach = _EDIT_REACH_PX
        return self.edit_frame_rect().adjusted(-reach, -reach, reach, reach).contains(pos)

    def _show_edit_cursor(self) -> None:
        """Text cursor over the object being edited, otherwise the move cursor."""
        for item in self.objects:
            item.setCursor(Qt.CursorShape.IBeamCursor if item.index == self._editing
                           else Qt.CursorShape.SizeAllCursor)

    def _toggle_caret(self) -> None:
        self._caret_on = not self._caret_on
        self.viewport().update()

    def nudge(self, dx_mm: float, dy_mm: float) -> None:
        """Move selected objects by dx/dy mm (arrow keys; not while dragging)."""
        if self._selection and self._drag not in ("move", "resize"):
            frames = [self.objects[i].frame_mm().moved(dx_mm, dy_mm) for i in self._selection]
            self.objects_moved.emit(self.selection(), frames)

    # --- Tool -----------------------------------------------------------------
    def tool(self) -> str:
        return self._tool

    def set_tool(self, tool: str) -> None:
        """Choose the tool: selection arrow or "Create text" (a click on the label creates text)."""
        if tool not in TOOL_MODES:
            raise ValueError(f"unknown tool {tool!r}")          # programming error, no message
        if tool != self._tool:
            self._tool = tool
            if tool == "text":
                self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
            else:
                self.viewport().unsetCursor()
            self.tool_changed.emit(tool)

    def _create_text(self, pos: QPointF) -> None:
        """"Create text": a click on an object selects it, a click on the label creates text there."""
        item = self._object_at(pos)
        if item is not None:
            self.set_selection([item.index])
            self.set_tool("select")
            self.edit_requested.emit(item.index, self._reading(pos))
            return
        point = self._reading(pos)
        x, y = point.x() / self.mm, point.y() / self.mm
        label = self._label_rect
        if label.x <= x <= label.right and label.y <= y <= label.bottom:
            self.set_tool("select")
            self.text_requested.emit(x, y)

    # --- Geometry ------------------------------------------------------------
    def px_per_mm(self) -> float:
        """Screen pixels per mm at the current zoom."""
        return self._scale * self.mm

    def guides(self) -> list[tuple[str, float]]:
        """Guide lines while dragging: ("x" | "y", mm in reading direction)."""
        return list(self._guides)

    def view_rect(self, index: int) -> QRectF:
        """Frame of an object in view coordinates (pixels)."""
        frame = self.sheet.mapRectToScene(self.objects[index].frame())
        return self.viewportTransform().mapRect(frame)

    def handle_points(self, index: int) -> dict[str, QPointF]:
        """Centres of the 8 handles in view coordinates (the view shows the reading direction)."""
        r = self.view_rect(index)
        cx, cy = r.center().x(), r.center().y()
        return {"tl": r.topLeft(), "t": QPointF(cx, r.top()), "tr": r.topRight(),
                "r": QPointF(r.right(), cy), "br": r.bottomRight(), "b": QPointF(cx, r.bottom()),
                "bl": r.bottomLeft(), "l": QPointF(r.left(), cy)}

    def _reading(self, pos: QPointF) -> QPointF:
        """View point → dots in reading direction."""
        return self.sheet.mapFromScene(self.viewportTransform().inverted()[0].map(pos))

    def _view_point(self, x: float, y: float) -> QPointF:
        """Dots in reading direction → view point."""
        return self.viewportTransform().map(self.sheet.mapToScene(QPointF(x, y)))

    def _object_at(self, pos: QPointF) -> ObjectItem | None:
        for item in self.items(pos.toPoint()):            # topmost first
            if isinstance(item, ObjectItem) and not item.is_empty():
                return item
        return None

    def _handle_at(self, pos: QPointF) -> tuple[int, str] | None:
        reach = HANDLE_PX / 2 + 1
        for index in reversed(self._selection):            # most recently selected first
            if self.objects[index].is_empty() or index == self._editing:
                continue                                   # placeholder, edit mode: no handles
            for key, point in self.handle_points(index).items():
                if abs(point.x() - pos.x()) <= reach and abs(point.y() - pos.y()) <= reach:
                    return index, key
        return None

    # --- Zoom ----------------------------------------------------------------
    def set_zoom(self, percent: int) -> None:
        self.zoom = max(25, min(400, percent))
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom)

    def _apply_zoom(self) -> None:
        self._scale = self.zoom / 100 * self.logicalDpiX() / self.dpi   # 100 % = true size
        self.resetTransform()
        self.scale(self._scale, self._scale)
        if self.orientation == "horizontal":
            self.rotate(-90)                                       # reading direction

    def _caption_for(self, length_dots: float) -> str:
        """Size in reading direction (width × height)."""
        w, h = self.label.size_mm
        w = mm_text(w)
        if self.label.shape == "round":
            return f"Ø {w} mm"
        along = format_mm(round(length_dots)) if self.label.shape == "endless" else mm_text(h)
        return f"{along} × {w} mm" if self.orientation == "horizontal" else f"{w} × {along} mm"

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom + (10 if event.angleDelta().y() > 0 else -10))
        else:
            super().wheelEvent(event)

    # --- Mouse ---------------------------------------------------------------
    def _on_handle(self, event) -> bool:
        return self.handle is not None and self.itemAt(event.position().toPoint()) is self.handle

    def is_dragging(self) -> bool:
        """The length handle or an object is being dragged (selecting in edit mode does not
        count – no object changes)."""
        return self._drag in ("length", "move", "resize")

    def snap_length(self, scene_y: float) -> float:
        """Scene y of the lower edge → length of the piece in mm (0.5 mm grid, within the
        model limits – they apply to the print image, the piece has the feed added)."""
        mm = round(scene_y / self.mm * 2) / 2
        feed = 2 * self.label.feed_margin / self.mm if self.label is not None else 0.0
        return min(max(mm, self.min_mm + feed), self.max_mm + feed)

    def set_read_only(self, read_only: bool) -> None:
        """View only (conversion of a parcel label): clicks, dragging and double click have
        no effect, the length handle is hidden; dropping and zoom still work."""
        self.read_only = read_only
        if read_only:
            self.cancel_object_drag()
            self.set_selection([])
        if self.handle is not None:
            self.handle.setVisible(not read_only)

    def mousePressEvent(self, event) -> None:
        if self.read_only:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.position()
        self._press = pos
        self._moved = False
        # tool of this click – even if the end of edit mode switches it right away
        tool = self._tool
        if self._editing is not None:
            if self._in_edit_frame(pos):
                self._drag = "text"
                shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                self.edit_pressed.emit(self._reading(pos), shift)
                return
            self.edit_left.emit()                          # afterwards the click acts as usual
        if self._on_handle(event):
            self._drag = "length"
            # remember the offset between cursor and cut edge so that the handle does not jump
            self._grab_offset = self.mapToScene(pos.toPoint()).y() - self.label_height()
            return
        if self.sheet is None:
            return
        if tool == "text":
            self._create_text(pos)
            return
        hit = self._handle_at(pos)
        if hit is not None:
            self._begin_resize(*hit, pos)
            return
        item = self._object_at(pos)
        toggle = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if item is None:
            if not toggle:
                self.set_selection([])
        elif toggle:
            chosen = self.selection()
            self.set_selection([i for i in chosen if i != item.index] if item.index in chosen
                               else [*chosen, item.index])
        else:
            if item.index not in self._selection:
                self.set_selection([item.index])
            self.object_clicked.emit(item.index)
            self._drag = "move"
            self._grabbed = item.index
            self._start = {i: self.objects[i].pos() for i in self._selection}

    def _begin_resize(self, index: int, key: str, pos: QPointF) -> None:
        self._drag = "resize"
        self._grabbed = index
        self._resize_key = key
        self._start_frame = self.objects[index].frame()
        f = self._start_frame
        x = f.left() if "l" in key else f.right() if "r" in key else f.center().x()
        y = f.top() if "t" in key else f.bottom() if "b" in key else f.center().y()
        self._handle_offset = QPointF(x, y) - self._reading(pos)   # handle does not jump

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        if self._drag == "length":
            mm = self.snap_length(self.mapToScene(pos.toPoint()).y() - self._grab_offset)
            self.handle.setY(mm * self.mm - self.label_height())
            self._caption = self._caption_for(mm * self.mm)
            self.viewport().update()
            self._moved = True
            self.length_changed.emit(mm)
            return
        if self._drag == "text":
            self.edit_dragged.emit(self._reading(pos))
            return
        if self._drag in ("move", "resize"):
            if not self._moved and (pos - self._press).manhattanLength() < _DRAG_START_PX:
                return
            self._moved = True
            snapping = not event.modifiers() & Qt.KeyboardModifier.AltModifier
            if self._drag == "move":
                self._drag_move(pos, snapping)
            else:
                self._drag_resize(pos)
            self.viewport().update()
            return
        hit = self._handle_at(pos) if self.sheet is not None else None
        if self._handle_cursor and hit is None:
            self.viewport().unsetCursor()
            if self._tool == "text":
                self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)
        if hit is not None and self._tool == "select":     # handle shows its direction
            self.viewport().setCursor(_HANDLE_CURSORS[hit[1]])
        self._handle_cursor = hit is not None and self._tool == "select"

    def _drag_move(self, pos: QPointF, snapping: bool) -> None:
        """Move selected images (model only on release), snapping on the way."""
        delta = self._reading(pos) - self._reading(self._press)
        self._guides = []
        if snapping:
            dx, dy = delta.x() / self.mm, delta.y() / self.mm
            frames = [self._start_rect(i).moved(dx, dy) for i in self._start]
            targets = [item.frame_mm() for item in self.objects
                       if item.index not in self._start and not item.is_empty()]
            snap = layout.snap(layout.bounds(frames), targets, self._area,
                               SNAP_PX / self.px_per_mm(), label=self._label_rect,
                               grow=self._grow, inner=self._inner)
            delta += QPointF(snap.dx * self.mm, snap.dy * self.mm)
            self._guides = snap.guides
        for index, start in self._start.items():
            self.objects[index].setPos(start + delta)

    def _start_rect(self, index: int) -> Rect:
        start, (w, h) = self._start[index], self.objects[index].size()
        return Rect(start.x() / self.mm, start.y() / self.mm, w / self.mm, h / self.mm)

    def _drag_resize(self, pos: QPointF) -> None:
        """Preview while dragging a handle: image stretched, rendering happens on release."""
        item = self.objects[self._grabbed]
        frame = resized_frame(self._start_frame, self._resize_key,
                              self._reading(pos) + self._handle_offset, item.keep_ratio,
                              item.keep_aspect, self.mm)
        item.setPos(frame.topLeft())
        item.setTransform(QTransform.fromScale(frame.width() / item.rendered.w,
                                               frame.height() / item.rendered.h))

    def mouseReleaseEvent(self, event) -> None:
        drag, self._drag = self._drag, None
        if drag == "text":
            return
        if drag == "length":
            if self._moved:
                self.drag_finished.emit()
            return
        if drag in ("move", "resize"):
            self._guides = []
            self.viewport().update()
            index = self._grabbed
            if drag == "move" and self._moved:
                indices = list(self._start)
                self.objects_moved.emit(indices, [self.objects[i].frame_mm() for i in indices])
            elif drag == "resize" and self._moved:
                self.object_resized.emit(index, self.objects[index].frame_mm(), self._resize_key)
            elif drag == "move" and len(self._selection) > 1:
                self.set_selection([index])                # click into the selection: only this one
            return
        super().mouseReleaseEvent(event)

    def cancel_object_drag(self) -> None:
        """Cancel dragging an object (new content, object list changed): the model
        stays unchanged, releasing has no effect any more."""
        if self._drag in ("move", "resize"):
            self._drag = None
            self._guides = []
            self.viewport().update()

    def mouseDoubleClickEvent(self, event) -> None:
        if self.read_only:
            return
        if self._on_handle(event):
            self.length_changed.emit(None)
            return
        if self._editing is not None and self._in_edit_frame(event.position()):
            self.edit_double_clicked.emit(self._reading(event.position()))
            return
        item = self._object_at(event.position()) if self.sheet is not None else None
        if item is not None and event.button() == Qt.MouseButton.LeftButton:
            self.set_selection([item.index])
            self.edit_requested.emit(item.index, self._reading(event.position()))
            return
        super().mouseDoubleClickEvent(event)

    def label_height(self) -> float:
        return self.outline.path().boundingRect().height() if self.outline else 0.0

    # --- Dropping ---------------------------------------------------------
    def _accepts(self, event) -> bool:
        mime = event.mimeData()
        return self.sheet is not None and (
            mime.hasFormat(image_import.MIME_SYMBOL) or mime.hasImage()
            or any(url.isLocalFile() for url in mime.urls()))

    def dragEnterEvent(self, event) -> None:
        if self._accepts(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        self.dragEnterEvent(event)          # not to the scene: it knows no drop targets

    def dropEvent(self, event) -> None:
        if not self._accepts(event):
            event.ignore()
            return
        event.acceptProposedAction()
        point = self._reading(event.position())
        # Copy the data now (QMimeData lives only during the drop), process only
        # afterwards: a dialog (PDF page) in dropEvent would hold on to the source of the drag
        x, y = point.x() / self.mm, point.y() / self.mm
        if event.mimeData().hasFormat(image_import.MIME_SYMBOL):
            symbol = bytes(event.mimeData().data(image_import.MIME_SYMBOL)).decode(errors="replace")
            QTimer.singleShot(0, self, lambda: self.symbol_dropped.emit(symbol, x, y))
            return
        paths = image_import.mime_files(event.mimeData())
        image = None if paths else image_import.mime_image(event.mimeData())
        QTimer.singleShot(0, self, lambda: self.dropped.emit(paths, image, x, y))

    # --- Selection frame, guide lines, rulers ---------------------------------
    def drawForeground(self, painter: QPainter, rect) -> None:
        painter.save()
        painter.resetTransform()
        vw, vh = self.viewport().width(), self.viewport().height()
        self._draw_selection(painter)
        self._draw_editing(painter)
        self._draw_guides(painter, vw, vh)
        if self.outline is not None:
            box = self.label_view_rect()
            painter.setPen(Qt.GlobalColor.black)
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(box.center().x() - 150, box.top() - 26, 300, 20),
                             Qt.AlignmentFlag.AlignCenter, self._caption)
        self._draw_rulers(painter, vw, vh)
        painter.restore()

    def _draw_selection(self, painter: QPainter) -> None:
        """Selected objects: dashed frame with 8 handles (fixed pixel size)."""
        frame = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
        border = QPen(Qt.GlobalColor.black, 1)
        half = HANDLE_PX / 2
        for index in self._selection:
            if index == self._editing:
                continue                                   # edit mode: _draw_editing
            painter.setPen(frame)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.view_rect(index))
            if self.objects[index].is_empty():
                continue                                   # empty text: only the placeholder
            painter.setPen(border)
            painter.setBrush(Qt.GlobalColor.white)
            for point in self.handle_points(index).values():
                painter.drawRect(QRectF(point.x() - half, point.y() - half, HANDLE_PX, HANDLE_PX))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_editing(self, painter: QPainter) -> None:
        """Edit mode: solid frame without handles, selection in the system colour
        (semi-transparent over the print image), blinking caret (1 screen pixel)."""
        if self._editing is None or self.sheet is None:
            return
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.edit_frame_rect())
        color = QColor(self.palette().highlight().color())
        color.setAlpha(_SELECTION_ALPHA)
        for rect in self.selection_rects():
            painter.fillRect(rect, color)
        if self.caret_shown() and self._caret_on:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)   # sharp, 1 pixel
            painter.setPen(QPen(Qt.GlobalColor.black, 0))
            line = self.caret_line()
            painter.drawLine(QPointF(round(line.x1()), round(line.y1())),
                             QPointF(round(line.x2()), round(line.y2())))
            painter.restore()

    def _draw_guides(self, painter: QPainter, vw: int, vh: int) -> None:
        """Red guide lines across the whole view while an object snaps."""
        painter.setPen(QPen(_GUIDE_COLOR, 1))
        for axis, mm in self._guides:
            point = self._view_point(mm * self.mm, mm * self.mm)
            if axis == "x":
                painter.drawLine(QPointF(point.x(), 0), QPointF(point.x(), vh))
            else:
                painter.drawLine(QPointF(0, point.y()), QPointF(vw, point.y()))

    def label_view_rect(self) -> QRectF:
        """Label in view coordinates (takes zoom and rotation into account)."""
        if self.outline is None:
            return QRectF()
        return QRectF(self.mapFromScene(self.outline.path().boundingRect()).boundingRect())

    def _draw_rulers(self, painter: QPainter, vw: int, vh: int) -> None:
        origin = self.label_view_rect().topLeft() if self.outline else self.mapFromScene(QPointF(0, 0))
        ppm = self._scale * self.mm                            # pixels per mm
        small = QFont(painter.font())
        small.setPointSize(7)
        small.setBold(False)
        painter.setFont(small)
        painter.fillRect(0, 0, vw, RULER, Qt.GlobalColor.white)
        painter.fillRect(0, 0, RULER, vh, Qt.GlobalColor.white)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        step = 1 if ppm >= 4 else 5
        for axis, length, start in (("x", vw, origin.x()), ("y", vh, origin.y())):
            first = math.floor((RULER - start) / ppm / step) * step
            mm = first
            while True:
                pos = start + mm * ppm
                if pos > length:
                    break
                if pos >= RULER:
                    tick = 12 if mm % 10 == 0 else 7 if mm % 5 == 0 else 4
                    if axis == "x":
                        painter.drawLine(int(pos), RULER - tick, int(pos), RULER)
                        if mm % 10 == 0:
                            painter.drawText(int(pos) + 2, 9, str(mm))
                    else:
                        painter.drawLine(RULER - tick, int(pos), RULER, int(pos))
                        if mm % 10 == 0:
                            painter.drawText(1, int(pos) - 2, str(mm))
                mm += step
        painter.setPen(QPen(Qt.GlobalColor.black, 3))
        painter.drawLine(0, RULER, vw, RULER)
        painter.drawLine(RULER, 0, RULER, vh)
        painter.fillRect(0, 0, RULER, RULER, Qt.GlobalColor.white)


def resized_frame(start: QRectF, key: str, point: QPointF, keep_ratio: bool,
                  keep_aspect: bool = False, mm: float = MM) -> QRectF:
    """Frame after dragging handle ``key`` to ``point`` (dots in reading direction).

    The opposite corner or edge stays put; at least 1 mm (``mm``: dots per mm of the
    label). ``keep_ratio``:
    corners keep the aspect ratio (scale the font); ``keep_aspect``: corners and
    edges as on release (``layout.keep_aspect``, image).
    """
    left, top, right, bottom = start.left(), start.top(), start.right(), start.bottom()
    if "l" in key:
        left = min(point.x(), right - _MIN_FRAME_MM * mm)
    if "r" in key:
        right = max(point.x(), left + _MIN_FRAME_MM * mm)
    if "t" in key:
        top = min(point.y(), bottom - _MIN_FRAME_MM * mm)
    if "b" in key:
        bottom = max(point.y(), top + _MIN_FRAME_MM * mm)
    if keep_aspect:
        old = Rect(start.x(), start.y(), start.width(), start.height())
        new = layout.keep_aspect(old, Rect(left, top, right - left, bottom - top), key)
        return QRectF(new.x, new.y, new.w, new.h)
    if keep_ratio and len(key) == 2:
        factor = max((right - left) / start.width(), (bottom - top) / start.height())
        w, h = start.width() * factor, start.height() * factor
        left, right = (right - w, right) if "l" in key else (left, left + w)
        top, bottom = (bottom - h, bottom) if "t" in key else (top, top + h)
    return QRectF(QPointF(left, top), QPointF(right, bottom))
