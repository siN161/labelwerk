"""Arbeitsfläche: Etikett in echter Größe und Form, Objekte (auswählen, ziehen, einrasten,
an Anfassern skalieren), mm-Lineale, Zoom, Längen-Anfasser."""
from __future__ import annotations

import math

from PIL import Image, ImageOps
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap,
                           QTransform)
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from .. import layout
from ..labels import DPI, Label, format_mm, length_limits
from ..layout import Rect
from ..printer import DEFAULT_MODEL
from ..render import RenderedObject

MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm
RULER = 22               # Linealbreite in Pixeln
_CORNER = 2 * MM         # Eckenradius gestanzter Etiketten
_MARGIN = 15 * MM        # grauer Rand um das Etikett
START_ZOOM = 200         # Prozent; 100 % = echte Größe
SNAP_PX = 6              # Einrasten: Abstand in Bildschirmpixeln
HANDLE_PX = 8            # Kantenlänge eines Anfassers in Bildschirmpixeln
_DRAG_START_PX = 3       # erst ab dieser Mausbewegung wird gezogen (Klick ≠ Verschieben)
_MIN_FRAME = MM          # kleinster Rahmen beim Skalieren (1 mm)
HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")   # Ecken und Kanten, im Uhrzeigersinn
_HANDLE_CURSORS = {
    "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
    "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
    "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
}
_GUIDE_COLOR = QColor("#E53935")


def to_qimage(img: Image.Image) -> QImage:
    """Druckbild als QImage; Weiß wird transparent, damit die Etikettform sichtbar bleibt."""
    gray = img.convert("L")
    # Immer schwarz, Alpha = 255 - L: über Weiß ergibt das exakt den Grauwert L (Vorschau = Druck)
    rgba = Image.merge("RGBA", (*(Image.new("L", gray.size, 0),) * 3, ImageOps.invert(gray)))
    return QImage(rgba.tobytes(), rgba.width, rgba.height, 4 * rgba.width,
                  QImage.Format.Format_RGBA8888).copy()


class ObjectItem(QGraphicsPixmapItem):
    """Ein Objekt auf der Arbeitsfläche: sein Bild aus ``render_object`` an seiner Position.

    Koordinaten in Druckpunkten in Leserichtung; das Elternelement (``Canvas.sheet``) dreht
    bei „horizontal“ in Druckkoordinaten.
    """

    def __init__(self, index: int, rendered: RenderedObject, pixmap: QPixmap, keep_ratio: bool,
                 parent: QGraphicsRectItem):
        super().__init__(pixmap, parent)
        self.index = index
        self.rendered = rendered
        self.keep_ratio = keep_ratio     # Ecken skalieren die Schrift: Seitenverhältnis bleibt
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setPos(rendered.x, rendered.y)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def is_empty(self) -> bool:
        return self.rendered.w == 0 or self.rendered.h == 0

    def frame(self) -> QRectF:
        """Rahmen in Druckpunkten in Leserichtung (beim Ziehen samt Vorschau-Streckung)."""
        return self.mapRectToParent(QRectF(0, 0, self.rendered.w, self.rendered.h))

    def frame_mm(self) -> Rect:
        f = self.frame()
        return Rect(f.x() / MM, f.y() / MM, f.width() / MM, f.height() / MM)


class Canvas(QGraphicsView):
    length_changed = Signal(object)   # neue Länge in mm (float) oder None = automatisch
    zoom_changed = Signal(int)        # Zoom in Prozent
    drag_finished = Signal()          # Längen-Anfasser losgelassen (nach tatsächlichem Ziehen)
    selection_changed = Signal(list)  # Indizes der ausgewählten Objekte in der Reihenfolge der Wahl
    objects_moved = Signal(list, list)         # Indizes, neue Rahmen (Rect, mm) nach dem Loslassen
    object_resized = Signal(int, object, str)  # Index, neuer Rahmen (Rect, mm), Anfasser („tl“ …)

    def __init__(self, model: str = DEFAULT_MODEL):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#9E9E9E"))
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)             # Mauszeiger über den Anfassern
        min_len, max_len = length_limits(model)
        self.min_mm, self.max_mm = min_len / MM, max_len / MM
        self.zoom = START_ZOOM
        self.orientation = "vertical"
        self._scale = 1.0
        self.label: Label | None = None
        self.outline = self.printable = self.handle = None
        self.sheet: QGraphicsRectItem | None = None        # Etikett in Leserichtung (Druckpunkte)
        self.objects: list[ObjectItem] = []
        self._pixmaps: dict[int, tuple[RenderedObject, QPixmap]] = {}
        self._selection: list[int] = []
        self._area = self._label_rect = Rect(0, 0, 0, 0)
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
        self._apply_zoom()

    # --- Inhalt -----------------------------------------------------------
    def set_document(self, label: Label, size: tuple[int, int],
                     rendered: list[RenderedObject], orientation: str = "vertical",
                     area: Rect | None = None, keep_ratio: list[bool] | None = None) -> None:
        """Etikett (physische Form) und die einzeln gerenderten Objekte darin anzeigen.

        ``size``: Etikett in Druckpunkten in Leserichtung (wie ``render.label_size``);
        ``area``: bedruckbarer Bereich in mm (Einrasten); ``keep_ratio`` je Objekt: Ecken
        skalieren die Schrift (ohne feste Rahmengröße). Die Szene ist immer in
        Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°, damit das Etikett in
        Leserichtung erscheint – die Objekte liegen in ``sheet``, das in Leserichtung zählt.
        """
        if orientation != self.orientation:
            self.orientation = orientation
            self._apply_zoom()
        self._cancel_object_drag()
        scene = self.scene()
        scene.clear()
        self.label = label
        width, height = size
        horizontal = orientation == "horizontal"
        pw, ph = (height, width) if horizontal else (width, height)   # Druckbild
        tw = label.total_width
        th = label.total_height or ph
        path = QPainterPath()
        if label.shape == "round":
            path.addEllipse(0, 0, tw, th)
        elif label.shape == "die_cut":
            path.addRoundedRect(0, 0, tw, th, _CORNER, _CORNER)
        else:
            path.addRect(0, 0, tw, th)
        self.outline = scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))

        ox, oy = (tw - pw) / 2, (th - ph) / 2
        self.sheet = QGraphicsRectItem(0, 0, width, height)
        self.sheet.setPen(QPen(Qt.PenStyle.NoPen))
        # Leserichtung → Druck: bei „horizontal“ 90° im Uhrzeigersinn wie render_document
        self.sheet.setTransform(QTransform().translate(ox + pw, oy).rotate(90) if horizontal
                                else QTransform().translate(ox, oy))
        scene.addItem(self.sheet)
        self._pixmaps = {id(obj): (obj, self._pixmap(obj)) for obj in rendered}
        ratios = keep_ratio if keep_ratio is not None else [True] * len(rendered)
        self.objects = [ObjectItem(i, obj, self._pixmaps[id(obj)][1], ratio, self.sheet)
                        for i, (obj, ratio) in enumerate(zip(rendered, ratios))]
        self._label_rect = Rect(0, 0, width / MM, height / MM)
        self._area = area if area is not None else self._label_rect
        dotted = QPen(QColor("#888888"), 1, Qt.PenStyle.DotLine)
        dotted.setCosmetic(True)
        self.printable = scene.addRect(QRectF(ox, oy, pw, ph), dotted)

        self.handle = None
        if label.shape == "endless":
            dashed = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
            dashed.setCosmetic(True)
            scene.addLine(-2 * MM, 0, tw + 2 * MM, 0, dashed)
            scene.addLine(-2 * MM, th, tw + 2 * MM, th, dashed)
            self.handle = scene.addRect(QRectF(tw / 2 - 5 * MM, th + MM, 10 * MM, 2 * MM),
                                        QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.black))
            self.handle.setCursor(Qt.CursorShape.SizeHorCursor if self.orientation == "horizontal"
                                  else Qt.CursorShape.SizeVerCursor)
            self.handle.setToolTip("Ziehen: Länge festlegen · Doppelklick: automatisch")
        self._caption = self._caption_for(th)
        scene.setSceneRect(-_MARGIN, -_MARGIN, tw + 2 * _MARGIN, th + 2 * _MARGIN)
        self.set_selection([i for i in self._selection if self._selectable(i)])

    def _pixmap(self, rendered: RenderedObject) -> QPixmap:
        """Pixmap je Objektbild nur einmal erzeugen (unverändertes Objekt = dasselbe Bild).

        Der Cache hält das Objektbild selbst fest, damit seine id nicht neu vergeben wird."""
        cached = self._pixmaps.get(id(rendered))
        if cached is not None and cached[0] is rendered:
            return cached[1]
        return QPixmap.fromImage(to_qimage(rendered.image))

    # --- Auswahl ----------------------------------------------------------
    def selection(self) -> list[int]:
        return list(self._selection)

    def set_selection(self, indices: list[int]) -> None:
        chosen = list(dict.fromkeys(i for i in indices if self._selectable(i)))
        if chosen != self._selection:
            self._selection = chosen
            self.viewport().update()
            self.selection_changed.emit(self.selection())

    def select_all(self) -> None:
        self.set_selection(list(range(len(self.objects))))

    def _selectable(self, index: int) -> bool:
        return 0 <= index < len(self.objects) and not self.objects[index].is_empty()

    def nudge(self, dx_mm: float, dy_mm: float) -> None:
        """Ausgewählte Objekte um dx/dy mm verschieben (Pfeiltasten)."""
        if self._selection:
            frames = [self.objects[i].frame_mm().moved(dx_mm, dy_mm) for i in self._selection]
            self.objects_moved.emit(self.selection(), frames)

    # --- Geometrie --------------------------------------------------------
    def px_per_mm(self) -> float:
        """Bildschirmpixel je mm beim aktuellen Zoom."""
        return self._scale * MM

    def guides(self) -> list[tuple[str, float]]:
        """Hilfslinien beim Ziehen: ("x" | "y", mm in Leserichtung)."""
        return list(self._guides)

    def view_rect(self, index: int) -> QRectF:
        """Rahmen eines Objekts in Ansichtskoordinaten (Pixel)."""
        frame = self.sheet.mapRectToScene(self.objects[index].frame())
        return self.viewportTransform().mapRect(frame)

    def handle_points(self, index: int) -> dict[str, QPointF]:
        """Mittelpunkte der 8 Anfasser in Ansichtskoordinaten (Ansicht zeigt die Leserichtung)."""
        r = self.view_rect(index)
        cx, cy = r.center().x(), r.center().y()
        return {"tl": r.topLeft(), "t": QPointF(cx, r.top()), "tr": r.topRight(),
                "r": QPointF(r.right(), cy), "br": r.bottomRight(), "b": QPointF(cx, r.bottom()),
                "bl": r.bottomLeft(), "l": QPointF(r.left(), cy)}

    def _reading(self, pos: QPointF) -> QPointF:
        """Ansichtspunkt → Druckpunkte in Leserichtung."""
        return self.sheet.mapFromScene(self.viewportTransform().inverted()[0].map(pos))

    def _view_point(self, x: float, y: float) -> QPointF:
        """Druckpunkte in Leserichtung → Ansichtspunkt."""
        return self.viewportTransform().map(self.sheet.mapToScene(QPointF(x, y)))

    def _object_at(self, pos: QPointF) -> ObjectItem | None:
        for item in self.items(pos.toPoint()):            # oberstes zuerst
            if isinstance(item, ObjectItem) and not item.is_empty():
                return item
        return None

    def _handle_at(self, pos: QPointF) -> tuple[int, str] | None:
        reach = HANDLE_PX / 2 + 1
        for index in reversed(self._selection):            # zuletzt gewähltes zuerst
            for key, point in self.handle_points(index).items():
                if abs(point.x() - pos.x()) <= reach and abs(point.y() - pos.y()) <= reach:
                    return index, key
        return None

    # --- Zoom -------------------------------------------------------------
    def set_zoom(self, percent: int) -> None:
        self.zoom = max(25, min(400, percent))
        self._apply_zoom()
        self.zoom_changed.emit(self.zoom)

    def _apply_zoom(self) -> None:
        self._scale = self.zoom / 100 * self.logicalDpiX() / DPI   # 100 % = echte Größe
        self.resetTransform()
        self.scale(self._scale, self._scale)
        if self.orientation == "horizontal":
            self.rotate(-90)                                       # Leserichtung

    def _caption_for(self, length_dots: float) -> str:
        """Größenangabe in Leserichtung (Breite × Höhe)."""
        w, h = self.label.size_mm
        if self.label.shape == "round":
            return f"Ø {w} mm"
        along = format_mm(round(length_dots)) if self.label.shape == "endless" else str(h)
        return f"{along} × {w} mm" if self.orientation == "horizontal" else f"{w} × {along} mm"

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom + (10 if event.angleDelta().y() > 0 else -10))
        else:
            super().wheelEvent(event)

    # --- Maus -------------------------------------------------------------
    def _on_handle(self, event) -> bool:
        return self.handle is not None and self.itemAt(event.position().toPoint()) is self.handle

    def is_dragging(self) -> bool:
        """Längen-Anfasser oder Objekt wird gerade gezogen."""
        return self._drag is not None

    def snap_length(self, scene_y: float) -> float:
        """Szene-y der Unterkante → Länge in mm (Raster 0,5 mm, innerhalb der Modellgrenzen)."""
        mm = round(scene_y / MM * 2) / 2
        return min(max(mm, self.min_mm), self.max_mm)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.position()
        self._press = pos
        self._moved = False
        if self._on_handle(event):
            self._drag = "length"
            # Versatz zwischen Cursor und Schnittkante merken, damit der Anfasser nicht springt
            self._grab_offset = self.mapToScene(pos.toPoint()).y() - self.label_height()
            return
        if self.sheet is None:
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
        self._handle_offset = QPointF(x, y) - self._reading(pos)   # Anfasser springt nicht

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        if self._drag == "length":
            mm = self.snap_length(self.mapToScene(pos.toPoint()).y() - self._grab_offset)
            self.handle.setY(mm * MM - self.label_height())
            self._caption = self._caption_for(mm * MM)
            self.viewport().update()
            self._moved = True
            self.length_changed.emit(mm)
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
        super().mouseMoveEvent(event)
        if hit is not None:                                # Anfasser zeigt seine Richtung
            self.viewport().setCursor(_HANDLE_CURSORS[hit[1]])
        self._handle_cursor = hit is not None

    def _drag_move(self, pos: QPointF, snapping: bool) -> None:
        """Ausgewählte Bilder verschieben (Modell erst beim Loslassen), dabei einrasten."""
        delta = self._reading(pos) - self._reading(self._press)
        self._guides = []
        if snapping:
            dx, dy = delta.x() / MM, delta.y() / MM
            frames = [self._start_rect(i).moved(dx, dy) for i in self._start]
            targets = [item.frame_mm() for item in self.objects
                       if item.index not in self._start and not item.is_empty()]
            snap = layout.snap(layout.bounds(frames), targets, self._area,
                               SNAP_PX / self.px_per_mm(), label=self._label_rect)
            delta += QPointF(snap.dx * MM, snap.dy * MM)
            self._guides = snap.guides
        for index, start in self._start.items():
            self.objects[index].setPos(start + delta)

    def _start_rect(self, index: int) -> Rect:
        start, rendered = self._start[index], self.objects[index].rendered
        return Rect(start.x() / MM, start.y() / MM, rendered.w / MM, rendered.h / MM)

    def _drag_resize(self, pos: QPointF) -> None:
        """Vorschau beim Ziehen an einem Anfasser: Bild gestreckt, gerendert wird beim Loslassen."""
        item = self.objects[self._grabbed]
        frame = resized_frame(self._start_frame, self._resize_key,
                              self._reading(pos) + self._handle_offset, item.keep_ratio)
        item.setPos(frame.topLeft())
        item.setTransform(QTransform.fromScale(frame.width() / item.rendered.w,
                                               frame.height() / item.rendered.h))

    def mouseReleaseEvent(self, event) -> None:
        drag, self._drag = self._drag, None
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
                self.set_selection([index])                # Klick in die Auswahl: nur dieses
            return
        super().mouseReleaseEvent(event)

    def _cancel_object_drag(self) -> None:
        """Neuer Inhalt während des Ziehens: Ziehen am alten Element abbrechen."""
        if self._drag in ("move", "resize"):
            self._drag = None
            self._guides = []

    def mouseDoubleClickEvent(self, event) -> None:
        if self._on_handle(event):
            self.length_changed.emit(None)
            return
        super().mouseDoubleClickEvent(event)

    def label_height(self) -> float:
        return self.outline.path().boundingRect().height() if self.outline else 0.0

    # --- Auswahlrahmen, Hilfslinien, Lineale ------------------------------
    def drawForeground(self, painter: QPainter, rect) -> None:
        painter.save()
        painter.resetTransform()
        vw, vh = self.viewport().width(), self.viewport().height()
        self._draw_selection(painter)
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
        """Ausgewählte Objekte: gestrichelter Rahmen mit 8 Anfassern (feste Pixelgröße)."""
        frame = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
        border = QPen(Qt.GlobalColor.black, 1)
        half = HANDLE_PX / 2
        for index in self._selection:
            painter.setPen(frame)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.view_rect(index))
            painter.setPen(border)
            painter.setBrush(Qt.GlobalColor.white)
            for point in self.handle_points(index).values():
                painter.drawRect(QRectF(point.x() - half, point.y() - half, HANDLE_PX, HANDLE_PX))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_guides(self, painter: QPainter, vw: int, vh: int) -> None:
        """Rote Hilfslinien über die ganze Ansicht, solange ein Objekt einrastet."""
        painter.setPen(QPen(_GUIDE_COLOR, 1))
        for axis, mm in self._guides:
            point = self._view_point(mm * MM, mm * MM)
            if axis == "x":
                painter.drawLine(QPointF(point.x(), 0), QPointF(point.x(), vh))
            else:
                painter.drawLine(QPointF(0, point.y()), QPointF(vw, point.y()))

    def label_view_rect(self) -> QRectF:
        """Etikett in Ansichtskoordinaten (berücksichtigt Zoom und Drehung)."""
        if self.outline is None:
            return QRectF()
        return QRectF(self.mapFromScene(self.outline.path().boundingRect()).boundingRect())

    def _draw_rulers(self, painter: QPainter, vw: int, vh: int) -> None:
        origin = self.label_view_rect().topLeft() if self.outline else self.mapFromScene(QPointF(0, 0))
        ppm = self._scale * MM                            # Pixel pro mm
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


def resized_frame(start: QRectF, key: str, point: QPointF, keep_ratio: bool) -> QRectF:
    """Rahmen nach Ziehen am Anfasser ``key`` auf ``point`` (Druckpunkte in Leserichtung).

    Die gegenüberliegende Ecke bzw. Kante bleibt stehen; mindestens 1 mm. ``keep_ratio``:
    Ecken behalten das Seitenverhältnis (Schrift skalieren).
    """
    left, top, right, bottom = start.left(), start.top(), start.right(), start.bottom()
    if "l" in key:
        left = min(point.x(), right - _MIN_FRAME)
    if "r" in key:
        right = max(point.x(), left + _MIN_FRAME)
    if "t" in key:
        top = min(point.y(), bottom - _MIN_FRAME)
    if "b" in key:
        bottom = max(point.y(), top + _MIN_FRAME)
    if keep_ratio and len(key) == 2:
        factor = max((right - left) / start.width(), (bottom - top) / start.height())
        w, h = start.width() * factor, start.height() * factor
        left, right = (right - w, right) if "l" in key else (left, left + w)
        top, bottom = (bottom - h, bottom) if "t" in key else (top, top + h)
    return QRectF(QPointF(left, top), QPointF(right, bottom))
