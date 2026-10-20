"""Window “New own parcel label type”: draw areas on an opened parcel label and save them as a custom
type (``parcel.own_from_dict`` checks, ``parcel.arrange`` lays them out when converting).

Draw rectangles on the label (empty spot), move (drag a rectangle), delete (Del); per area
rotation clockwise, “Barcode – do not shrink” and “Space after” (empty tape up to the next
area). The preview shows the result on the label of the main window.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QSpinBox, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

from .. import parcel
from ..i18n import _, language, number, pgettext
from ..render import render_document
from .widgets import DoubleSpinBox

EDIT_DPI = 100                      # resolution of the label in the window
MIN_MM = 3.0                        # smaller rectangles do not count (click instead of drag)
PREVIEW_W = 420                     # width of the result preview in pixels
PREVIEW_H = 220
PREVIEW_DELAY_MS = 250              # preview only once dragging pauses briefly (immediately on release)
NAME_MAX = 200
SNAP_MM = 0.5                       # this close to the page edge counts as the edge
ROTATIONS = (0, 90, 180, 270)


def gray_pixmap(image) -> QPixmap:
    """Grayscale image (PIL) as pixmap – white stays white (label, preview)."""
    gray = image.convert("L")
    return QPixmap.fromImage(QImage(gray.tobytes(), gray.width, gray.height, gray.width,
                                    QImage.Format.Format_Grayscale8).copy())


class _Area(QGraphicsRectItem):
    """An area on the label (scene in pixels at ``EDIT_DPI``), movable, with a number."""

    def __init__(self, rect: QRectF, number: int, moved):
        super().__init__(QRectF(0, 0, rect.width(), rect.height()))
        self.setPos(rect.topLeft())
        self.rotation_ = 0
        self.barcode = False
        self.space = 0.0                     # space after it (mm, 0 = none)
        self._moved = moved
        pen = QPen(QColor("#E00000"), 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(224, 0, 0, 40)))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
                      | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.label = QGraphicsSimpleTextItem(str(number), self)
        self.label.setBrush(QColor("#E00000"))
        self.label.setPos(4, 2)

    def set_number(self, number: int) -> None:
        self.label.setText(str(number))

    def scene_rect(self) -> QRectF:
        return self.mapRectToScene(self.rect())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            bounds = self.scene().sceneRect()         # never beyond the edge of the page
            if not bounds.isEmpty():
                w, h = self.rect().width(), self.rect().height()
                return QPointF(min(max(value.x(), bounds.left()), bounds.right() - w),
                               min(max(value.y(), bounds.top()), bounds.bottom() - h))
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._moved()
        return super().itemChange(change, value)


class _PageView(QGraphicsView):
    """Page of the label; dragging on free space draws a new rectangle."""
    drawn = Signal(QRectF)
    released = Signal()                       # mouse released (moving finished)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#9E9E9E"))
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        self._start: QPointF | None = None
        self._rubber: QGraphicsRectItem | None = None

    def mousePressEvent(self, event) -> None:
        point = self.mapToScene(event.position().toPoint())
        item = self.itemAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and not isinstance(item, (_Area,
                                                                               QGraphicsSimpleTextItem)):
            self.scene().clearSelection()
            self._start = point
            pen = QPen(QColor("#E00000"), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._rubber = self.scene().addRect(QRectF(point, point), pen)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._start is not None and self._rubber is not None:
            self._rubber.setRect(QRectF(self._start, self.mapToScene(event.position().toPoint()))
                                 .normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._start is not None and self._rubber is not None:
            rect = self._rubber.rect()
            self.scene().removeItem(self._rubber)
            self._start = self._rubber = None
            self.drawn.emit(rect)
            return
        super().mouseReleaseEvent(event)
        self.released.emit()


class ParcelTypeEditor(QDialog):
    """Define areas of a label as a custom type; ``result_type`` returns the checked type."""
    SPACE_TIP = _("Blank tape between this area and the next one")

    def __init__(self, parent, source: parcel.Source, label_id: str, model: str,
                 taken: set[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(_("New own parcel label type"))
        self.source, self.label_id, self.model = source, label_id, model
        self._taken = set(taken or ())
        self._areas: dict[int, list[_Area]] = {}           # page → areas
        self._page = 1
        k = EDIT_DPI / 25.4
        self._k = k

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DELAY_MS)
        self._preview_timer.timeout.connect(self._render_preview)
        self.view = _PageView()
        self.view.drawn.connect(self._drawn)
        self.view.released.connect(self._preview_now)
        self.view.scene().selectionChanged.connect(self._selection_changed)
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, source.page_count)
        self.page_spin.setPrefix(_("Page "))
        self.page_spin.setVisible(source.page_count > 1)
        self.page_spin.valueChanged.connect(self._show_page)

        self.name = QLineEdit()
        self.name.setMaxLength(NAME_MAX)
        self.name.setPlaceholderText(_("e.g. Returns of my shop"))
        self.words = QLineEdit()
        self.words.setPlaceholderText(_("optional, e.g. a company name on the label"))
        self.words.setToolTip(_("Text that is on every such label – labelwerk then recognizes "
                                "the type when opening (several words: separate with commas)"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._row_chosen)
        # order on the tape: drag a row, ▲/▼ or Ctrl+↑/↓ (a space stays with its area)
        self.list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list.model().rowsMoved.connect(self._rows_dragged)
        self.list.installEventFilter(self)
        self.up_button = QToolButton()
        self.up_button.setText("▲")
        self.up_button.setToolTip(_("Earlier on the tape (Ctrl+↑)"))
        self.up_button.clicked.connect(lambda: self.move_area(-1))
        self.down_button = QToolButton()
        self.down_button.setText("▼")
        self.down_button.setToolTip(_("Later on the tape (Ctrl+↓)"))
        self.down_button.clicked.connect(lambda: self.move_area(1))
        self.rotation = QComboBox()
        for degrees in ROTATIONS:
            self.rotation.addItem(_("{degrees}° clockwise").format(degrees=degrees), degrees)
        self.rotation.currentIndexChanged.connect(self._area_changed)
        self.barcode = QCheckBox(_("Barcode – do not shrink"))
        self.barcode.toggled.connect(self._area_changed)
        self.space = DoubleSpinBox()
        self.space.setRange(0, parcel.MAX_SPACE_MM)
        self.space.setDecimals(1)
        self.space.setSuffix(" mm")
        self.space.setSpecialValueText(pgettext("space", "none"))
        self.space.setKeyboardTracking(False)          # only after the input (otherwise the list resets
        self.space.valueChanged.connect(self._area_changed)   # the field while typing)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(PREVIEW_W, PREVIEW_H)
        self.preview.setWordWrap(True)
        self.preview.setObjectName("parcelPreview")
        self.overlap = QLabel(_("Areas overlap – their content then appears twice on the label."))
        self.overlap.setObjectName("note")
        self.overlap.setWordWrap(True)
        self.overlap.hide()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                        | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.name.textChanged.connect(self._check)        # name does not change the preview

        side = QWidget()
        form = QFormLayout(side)
        form.addRow(_("Name"), self.name)
        form.addRow(_("Recognise by"), self.words)
        hint = QLabel(_("Drag on the label to mark an area, drag an area to move it, Del removes "
                        "the chosen one. Areas are placed on the tape in this order."))
        hint.setWordWrap(True)
        hint.setObjectName("note")
        form.addRow(hint)
        order = QWidget()
        order_layout = QHBoxLayout(order)
        order_layout.setContentsMargins(0, 0, 0, 0)
        order_layout.addWidget(self.list, 1)
        buttons = QVBoxLayout()
        buttons.addWidget(self.up_button)
        buttons.addWidget(self.down_button)
        buttons.addStretch(1)
        order_layout.addLayout(buttons)
        form.addRow(_("Areas"), order)
        form.addRow(_("Rotation"), self.rotation)
        form.addRow(self.barcode)
        form.addRow(_("Space after"), self.space)
        form.addRow(self.overlap)
        form.addRow(_("Result"), self.preview)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.page_spin)
        left_layout.addWidget(self.view, 1)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(side)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        outer = QVBoxLayout(self)
        outer.addWidget(self.splitter, 1)
        outer.addWidget(self.buttons)
        self.resize(1100, 720)
        self.splitter.setSizes([640, 440])          # label large, settings beside it
        self._show_page(1)
        self._update()

    # --- Page and areas -----------------------------------------------------------------
    def _show_page(self, number: int) -> None:
        for area in self._areas.get(self._page, []):
            self.view.scene().removeItem(area)
        self._page = number
        scene = self.view.scene()
        for item in list(scene.items()):
            if not isinstance(item, (_Area, QGraphicsSimpleTextItem)):
                scene.removeItem(item)
        try:
            image = self.source.page(number, EDIT_DPI)
        except (parcel.ParcelError, ValueError) as e:
            self.preview.setText(str(e))
            return
        page = scene.addPixmap(gray_pixmap(image))
        page.setZValue(-1)
        scene.setSceneRect(QRectF(0, 0, image.width, image.height))
        for area in self._areas.get(number, []):
            scene.addItem(area)
        self.view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._fill_list()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.view.fitInView(self.view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def add_area(self, rect_mm, rotation: int = 0, barcode: bool = False, space: float = 0.0) -> None:
        """Add an area (x0, y0, x1, y1 in mm on the shown page)."""
        x0, y0, x1, y1 = rect_mm
        self._drawn(QRectF(x0 * self._k, y0 * self._k, (x1 - x0) * self._k, (y1 - y0) * self._k),
                    rotation, barcode, space)

    def _drawn(self, rect: QRectF, rotation: int = 0, barcode: bool = False,
               space: float = 0.0) -> None:
        bounds = self.view.scene().sceneRect()
        rect = rect.intersected(bounds) if not bounds.isEmpty() else rect
        if rect.width() < MIN_MM * self._k or rect.height() < MIN_MM * self._k:
            return
        areas = self._areas.setdefault(self._page, [])
        area = _Area(rect, self._number(len(areas)), self._schedule_preview)
        area.rotation_, area.barcode, area.space = rotation, barcode, space
        areas.append(area)
        self.view.scene().addItem(area)
        self._fill_list()
        self.list.setCurrentRow(len(areas) - 1)
        self._update()

    def _number(self, index: int) -> int:
        """Running number across all pages (order on the tape)."""
        return sum(len(self._areas.get(p, [])) for p in range(1, self._page)) + index + 1

    def remove_selected(self) -> None:
        areas = self._areas.get(self._page, [])
        for area in [a for a in areas if a.isSelected()]:
            areas.remove(area)
            self.view.scene().removeItem(area)
        for index, area in enumerate(areas):
            area.set_number(self._number(index))
        self._fill_list()
        self._update()

    def move_area(self, step: int) -> None:
        """Chosen area one place earlier (-1) or later (+1) on the tape (within its page)."""
        areas = self._areas.get(self._page, [])
        row = self.list.currentRow()
        target = row + step
        if not (0 <= row < len(areas) and 0 <= target < len(areas)):
            return
        areas.insert(target, areas.pop(row))
        self._reordered(target)

    def _rows_dragged(self, _parent, start: int, _end: int, _dest, row: int) -> None:
        """A row was dragged in the list: same order for the areas (Qt counts the target before
        the move)."""
        areas = self._areas.get(self._page, [])
        if not 0 <= start < len(areas):
            return
        target = row - 1 if row > start else row
        areas.insert(target, areas.pop(start))
        QTimer.singleShot(0, self, lambda: self._reordered(target))   # after Qt finished the move

    def _reordered(self, row: int) -> None:
        for index, area in enumerate(self._areas.get(self._page, [])):
            area.set_number(self._number(index))
        self._fill_list()
        self.list.setCurrentRow(row)
        self._update()

    def eventFilter(self, watched, event) -> bool:
        if (watched is self.list and event.type() == QEvent.Type.KeyPress
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)):
            self.move_area(-1 if event.key() == Qt.Key.Key_Up else 1)
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not self.name.hasFocus() \
                and not self.words.hasFocus():
            self.remove_selected()
            return
        super().keyPressEvent(event)

    def _fill_list(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for index, area in enumerate(self._areas.get(self._page, [])):
            x0, y0, x1, y1 = self._mm(area)
            text = _("{number}: {w} × {h} mm").format(number=self._number(index),
                                                     w=round(x1 - x0), h=round(y1 - y0))
            if area.barcode:
                text += " · " + _("barcode")
            if area.space and not self._is_last(area):
                text += " · " + _("space {length} mm").format(length=number(area.space))
            self.list.addItem(text)
        self.list.blockSignals(False)
        self._update_order_buttons()

    def _update_order_buttons(self) -> None:
        row = self.list.currentRow()
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(0 <= row < self.list.count() - 1)

    def _mm(self, area: _Area) -> tuple[float, float, float, float]:
        """Area in mm on its page – limited to the page size (rounding at the edge)."""
        r = area.scene_rect()
        page = next((p for p, areas in self._areas.items() if area in areas), self._page)
        w, h = (round(v, 1) for v in self.source.sizes_mm[page - 1])

        def edge(value: float, size: float) -> float:   # pixel rounding at the page edge: exactly the edge
            value = min(max(value, 0.0), size)
            return 0.0 if value < SNAP_MM else size if value > size - SNAP_MM else value
        x0, y0, x1, y1 = (round(v / self._k, 1) for v in (r.left(), r.top(), r.right(), r.bottom()))
        return edge(x0, w), edge(y0, h), edge(x1, w), edge(y1, h)

    def _is_last(self, area: _Area) -> bool:
        """Last area on the tape (no space counts after it)."""
        pages = [p for p in sorted(self._areas) if self._areas[p]]
        return bool(pages) and self._areas[pages[-1]][-1] is area

    def _current_area(self) -> _Area | None:
        areas = self._areas.get(self._page, [])
        row = self.list.currentRow()
        return areas[row] if 0 <= row < len(areas) else None

    def _row_chosen(self, row: int) -> None:
        area = self._current_area()
        self._update_order_buttons()
        for widget in (self.rotation, self.barcode):
            widget.setEnabled(area is not None)
        last = area is not None and self._is_last(area)
        self.space.setEnabled(area is not None and not last)
        self.space.setToolTip(_("No space after the last area – it only goes between areas")
                              if last else self.SPACE_TIP)
        if area is None:
            return
        self.view.scene().blockSignals(True)
        self.view.scene().clearSelection()
        area.setSelected(True)
        self.view.scene().blockSignals(False)
        for widget in (self.rotation, self.barcode, self.space):
            widget.blockSignals(True)
        self.rotation.setCurrentIndex(ROTATIONS.index(area.rotation_))
        self.barcode.setChecked(area.barcode)
        if self.space.value() != area.space:
            self.space.setValue(area.space)
        for widget in (self.rotation, self.barcode, self.space):
            widget.blockSignals(False)

    def _selection_changed(self) -> None:
        areas = self._areas.get(self._page, [])
        try:
            chosen = [i for i, a in enumerate(areas) if a.isSelected()]
        except RuntimeError:                              # window is being torn down
            return
        if chosen and chosen[0] != self.list.currentRow():
            self.list.setCurrentRow(chosen[0])

    def _area_changed(self) -> None:
        area = self._current_area()
        if area is None:
            return
        area.rotation_ = self.rotation.currentData()
        area.barcode = self.barcode.isChecked()
        area.space = self.space.value()
        row = self.list.currentRow()
        self._fill_list()
        self.list.setCurrentRow(row)
        self._update()

    def _schedule_preview(self) -> None:
        """Area is being moved: list and check immediately, preview only once it pauses."""
        row = self.list.currentRow()
        self._fill_list()
        self.list.setCurrentRow(row)
        self._check()
        self._preview_timer.start()

    def _preview_now(self) -> None:
        if self._preview_timer.isActive():
            self._preview_timer.stop()
            self._render_preview()

    # --- Result -------------------------------------------------------------------------
    def pieces(self) -> list[dict]:
        """Areas in tape order (page by page) for ``parcel.own_from_dict``."""
        out = []
        for page in sorted(self._areas):
            for area in self._areas[page]:
                space = area.space if not self._is_last(area) else 0   # only between the areas
                out.append({"page": page, "src": list(self._mm(area)), "rotation": area.rotation_,
                            "kind": "barcode" if area.barcode else "text",
                            **({"space_after_mm": space} if space else {})})
        return out

    def type_data(self) -> dict:
        name = self.name.text().strip()
        words = [w.strip() for w in self.words.text().split(",") if w.strip()]
        sizes = sorted({(round(w, 1), round(h, 1)) for w, h in self.source.sizes_mm})
        pages = [[round(w, 1), round(h, 1)] for w, h in self.source.sizes_mm]   # per page
        return {"id": parcel.own_id(name, self._taken), "names": {language() or "en": name},
                "source": {"sizes_mm": [list(s) for s in sizes], "pages_mm": pages},
                "detect": {"all": words} if words else {}, "pieces": self.pieces()}

    def result_type(self) -> parcel.ParcelType:
        """Checked custom type (``ParcelError`` if something is missing)."""
        return parcel.own_from_dict(self.type_data())

    def problem(self) -> str | None:
        """What is still missing for saving (translated) – None if the type is valid."""
        if not self.name.text().strip():
            return _("Enter a name.")
        if not self.pieces():
            return _("Mark at least one area.")
        try:
            self.result_type()
        except parcel.ParcelError as e:
            return str(e)
        return None

    def overlapping(self) -> bool:
        """Do areas of the same page overlap?"""
        for areas in self._areas.values():
            rects = [a.scene_rect() for a in areas]
            for i, a in enumerate(rects):
                if any(a.intersects(b) for b in rects[i + 1:]):
                    return True
        return False

    def _check(self) -> None:
        """SAVE only with a valid type; note on overlapping areas."""
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self.problem() is None)
        self.overlap.setVisible(self.overlapping())

    def _update(self) -> None:
        self._check()
        self._preview_timer.stop()
        self._render_preview()

    def accept(self) -> None:
        """Close only with a valid type; otherwise the reason is shown in the preview."""
        problem = self.problem()
        if problem is not None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(problem)
            return
        super().accept()

    def _render_preview(self) -> None:
        """Result on the label of the main window (first label), scaled down."""
        if not self.pieces():
            self.preview.setPixmap(QPixmap())
            self.preview.setText(_("Mark at least one area."))
            return
        data = self.type_data()
        data["names"] = data["names"] if self.name.text().strip() else {"en": "preview"}
        try:
            ptype = parcel.own_from_dict(data)
            docs = parcel.convert(self.source, ptype, self.label_id, self.model).documents
            image = render_document(docs[0], self.model)
        except (parcel.ParcelError, ValueError) as e:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(str(e))
            return
        if docs[0].orientation == "horizontal":        # print image → reading direction
            image = image.rotate(90, expand=True)
        pixmap = gray_pixmap(image)
        self.preview.setText("")
        self.preview.setPixmap(pixmap.scaled(PREVIEW_W, PREVIEW_H, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
