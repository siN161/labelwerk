"""Arbeitsfläche: Etikett in echter Größe und Form, mm-Lineale, Zoom, Längen-Anfasser."""
from __future__ import annotations

import math

from PIL import Image, ImageOps
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from ..labels import DPI, Label, format_mm, length_limits
from ..printer import DEFAULT_MODEL

MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm
RULER = 22               # Linealbreite in Pixeln
_CORNER = 2 * MM         # Eckenradius gestanzter Etiketten
_MARGIN = 15 * MM        # grauer Rand um das Etikett
START_ZOOM = 200         # Prozent; 100 % = echte Größe


def to_qimage(img: Image.Image) -> QImage:
    """Druckbild als QImage; Weiß wird transparent, damit die Etikettform sichtbar bleibt."""
    gray = img.convert("L")
    # Immer schwarz, Alpha = 255 - L: über Weiß ergibt das exakt den Grauwert L (Vorschau = Druck)
    rgba = Image.merge("RGBA", (*(Image.new("L", gray.size, 0),) * 3, ImageOps.invert(gray)))
    return QImage(rgba.tobytes(), rgba.width, rgba.height, 4 * rgba.width,
                  QImage.Format.Format_RGBA8888).copy()


class Canvas(QGraphicsView):
    length_changed = Signal(object)   # neue Länge in mm (float) oder None = automatisch
    zoom_changed = Signal(int)        # Zoom in Prozent
    drag_finished = Signal()          # Anfasser losgelassen (nach tatsächlichem Ziehen)

    def __init__(self, model: str = DEFAULT_MODEL):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#9E9E9E"))
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        min_len, max_len = length_limits(model)
        self.min_mm, self.max_mm = min_len / MM, max_len / MM
        self.zoom = START_ZOOM
        self.orientation = "vertical"
        self._scale = 1.0
        self.label: Label | None = None
        self.outline = self.printable = self.handle = None
        self._caption = ""
        self._dragging = False
        self._moved = False
        self._grab_offset = 0.0
        self._apply_zoom()

    # --- Inhalt -----------------------------------------------------------
    def set_document(self, label: Label, image: Image.Image, orientation: str = "vertical") -> None:
        """Etikett (physische Form) und Druckbild darin anzeigen.

        Die Szene ist immer in Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°,
        damit das Etikett in Leserichtung erscheint.
        """
        if orientation != self.orientation:
            self.orientation = orientation
            self._apply_zoom()
        scene = self.scene()
        scene.clear()
        self.label = label
        tw = label.total_width
        th = label.total_height or image.height
        path = QPainterPath()
        if label.shape == "round":
            path.addEllipse(0, 0, tw, th)
        elif label.shape == "die_cut":
            path.addRoundedRect(0, 0, tw, th, _CORNER, _CORNER)
        else:
            path.addRect(0, 0, tw, th)
        self.outline = scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))

        ox, oy = (tw - image.width) / 2, (th - image.height) / 2
        pixmap = scene.addPixmap(QPixmap.fromImage(to_qimage(image)))
        pixmap.setPos(ox, oy)
        dotted = QPen(QColor("#888888"), 1, Qt.PenStyle.DotLine)
        dotted.setCosmetic(True)
        self.printable = scene.addRect(QRectF(ox, oy, image.width, image.height), dotted)

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

    # --- Länge ziehen -----------------------------------------------------
    def _on_handle(self, event) -> bool:
        return self.handle is not None and self.itemAt(event.position().toPoint()) is self.handle

    def is_dragging(self) -> bool:
        return self._dragging

    def snap_length(self, scene_y: float) -> float:
        """Szene-y der Unterkante → Länge in mm (Raster 0,5 mm, innerhalb der Modellgrenzen)."""
        mm = round(scene_y / MM * 2) / 2
        return min(max(mm, self.min_mm), self.max_mm)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_handle(event):
            self._dragging = True
            self._moved = False
            # Versatz zwischen Cursor und Schnittkante merken, damit der Anfasser nicht springt
            self._grab_offset = self.mapToScene(event.position().toPoint()).y() - self.label_height()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            mm = self.snap_length(
                self.mapToScene(event.position().toPoint()).y() - self._grab_offset)
            self.handle.setY(mm * MM - self.label_height())
            self._caption = self._caption_for(mm * MM)
            self.viewport().update()
            self._moved = True
            self.length_changed.emit(mm)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging:
            self._dragging = False
            if self._moved:
                self.drag_finished.emit()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._on_handle(event):
            self.length_changed.emit(None)
            return
        super().mouseDoubleClickEvent(event)

    def label_height(self) -> float:
        return self.outline.path().boundingRect().height() if self.outline else 0.0

    # --- Lineale und Beschriftung -----------------------------------------
    def drawForeground(self, painter: QPainter, rect) -> None:
        painter.save()
        painter.resetTransform()
        vw, vh = self.viewport().width(), self.viewport().height()
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
