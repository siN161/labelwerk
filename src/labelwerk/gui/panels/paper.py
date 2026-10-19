"""Panel „Papier“: Etikett, Länge (Endlosband), Ränder, Zierrahmen und Ausrichtung – wie im
P-touch Editor."""
from __future__ import annotations

from PIL import Image, ImageOps
from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QRadioButton, QWidget)

from ...document import FRAME_LINE_MM, MAX_FRAME_MM, MAX_MARGIN_MM, Document, Frame
from ...labels import DPI, get_label, labels_for_model, length_limits
from ...media import Media
from ...printer import DEFAULT_MODEL
from ...render import frame_mask
from ..widgets import DoubleSpinBox
from . import Panel

_GROUPS = (("endless", "Endlos"), ("die_cut", "Gestanzt"), ("round", "Rund"))
FRAME_TITLES = (("Kein", None), ("Einfach", "single"), ("Doppelt", "double"),
                ("Dick-dünn", "thick_thin"), ("Gestrichelt", "dashed"), ("Gepunktet", "dotted"),
                ("Nur Ecken", "corners"))
FRAME_ICON = QSize(56, 22)
ROUND_TIP = "Auf runden Etiketten wird jeder Rahmen ein Kreis."


def frame_icon(style: str | None) -> QIcon:
    """Vorschau einer Rahmenart auf weißem Etikett – aus dem Kern gezeichnet (dicke Linie,
    damit sie klein lesbar bleibt); None = leeres Etikett („Kein“, gleich hoch)."""
    size = (FRAME_ICON.width(), FRAME_ICON.height())
    if style is None:
        small = Image.new("L", size, 255)
    else:
        doc = Document("62x29", frame=Frame(style, line_mm=1.5, padding_mm=0))
        small = ImageOps.invert(frame_mask(doc)).resize(size, Image.Resampling.BOX)
    rgb = small.convert("RGB")                  # deckend weiß – auch auf dunkler Palette
    image = QImage(rgb.tobytes(), rgb.width, rgb.height, 3 * rgb.width, QImage.Format.Format_RGB888)
    return QIcon(QPixmap.fromImage(image.copy()))


def _spin(low: float, high: float, step: float, tip: str) -> DoubleSpinBox:
    box = DoubleSpinBox()
    box.setSuffix(" mm")
    box.setDecimals(1)
    box.setSingleStep(step)
    box.setRange(low, high)
    box.setToolTip(tip)
    box.setKeyboardTracking(False)          # erst bei Enter/Verlassen: ein Rückgängig-Schritt
    return box


class PaperPanel(Panel):
    check_media_requested = Signal()
    media_status_changed = Signal(str, str)   # Text, Zustand (ok/warn/error/"") für die Fußzeile

    def __init__(self, doc: Document, model: str = DEFAULT_MODEL):
        super().__init__(doc, "Papier")
        self.media: Media | None = None          # zuletzt erkannte Rolle
        self.media_label: str | None = None      # passendes Etikett dazu
        self.media_adjusted = False              # Etikett wurde automatisch angepasst

        self.section("Etikett")
        self.combo = QComboBox()
        labels = labels_for_model(model)
        for shape, title in _GROUPS:
            group = [lbl for lbl in labels if lbl.shape == shape]
            if not group:
                continue
            self.combo.addItem(f"— {title} —")
            self.combo.model().item(self.combo.count() - 1).setEnabled(False)
            for lbl in group:
                self.combo.addItem(lbl.description, lbl.id)
        self.layout_.addWidget(self.combo)
        self.check = QPushButton("MEDIUM PRÜFEN")
        self.check.setToolTip("Eingelegte Rolle vom Drucker abfragen (druckt nichts)")
        self.check.clicked.connect(self.check_media_requested)
        self.layout_.addWidget(self.check)

        self.length_title = self.section("Länge")
        self.length_box = QWidget()
        row = QHBoxLayout(self.length_box)
        row.setContentsMargins(0, 0, 0, 0)
        self.length_auto = QCheckBox("Automatisch")
        self.length = DoubleSpinBox()
        self.length.setSuffix(" mm")
        self.length.setDecimals(1)
        self.length.setSingleStep(0.5)
        min_len, max_len = length_limits(model)
        self.length.setRange(round(min_len * 25.4 / DPI, 1), round(max_len * 25.4 / DPI, 1))
        self.length.setValue(50.0)
        row.addWidget(self.length_auto)
        row.addWidget(self.length)
        self.layout_.addWidget(self.length_box)

        self.fixed_size = QLabel()
        self.fixed_size.setObjectName("fixedSize")
        self.layout_.addWidget(self.fixed_size)

        self.section("Ausrichtung")
        self.horizontal = QRadioButton("Horizontal")
        self.horizontal.setToolTip("Etikett im Querformat – Leserichtung längs zum Band")
        self.vertical = QRadioButton("Vertikal")
        self.vertical.setToolTip("Etikett im Hochformat – Leserichtung quer zum Band")
        self.orientation_group = QButtonGroup(self)
        for button in (self.horizontal, self.vertical):
            self.orientation_group.addButton(button)
            self.layout_.addWidget(button)
        self.section("Ränder")
        self.margin = DoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setToolTip("Abstand zur Papierkante ringsum (quer lässt der Drucker ohnehin "
                               "rund 1,5 mm frei)")
        self.layout_.addWidget(self.margin)

        self.section("Rahmen")
        self.frame_style = QComboBox()
        self.frame_style.setIconSize(FRAME_ICON)
        for title, style in FRAME_TITLES:
            self.frame_style.addItem(frame_icon(style), title, style)
        self.layout_.addWidget(self.frame_style)
        self.frame_rounded = QCheckBox("Abgerundet")
        self.layout_.addWidget(self.frame_rounded)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)              # Felder füllen die Breite (wie die übrigen)
        defaults = Frame()
        self.frame_line = _spin(*FRAME_LINE_MM, 0.1, "Strichstärke der Linie")
        self.frame_inset = _spin(0.0, MAX_FRAME_MM, 0.5, "Abstand des Rahmens vom bedruckbaren Rand")
        self.frame_padding = _spin(0.0, MAX_FRAME_MM, 0.5,
                                   "Abstand zwischen Rahmen und automatisch gesetztem Text")
        self.frame_labels: list[QLabel] = []
        for row, (title, box, value) in enumerate((
                ("Linie", self.frame_line, defaults.line_mm),
                ("Randabstand", self.frame_inset, defaults.inset_mm),
                ("Innenabstand", self.frame_padding, defaults.padding_mm))):
            box.setValue(value)
            label = QLabel(title)
            label.setToolTip(box.toolTip())
            self.frame_labels.append(label)
            grid.addWidget(label, row, 0)
            grid.addWidget(box, row, 1)
        self.layout_.addLayout(grid)
        self._last_frame = defaults               # Werte bleiben bei „Kein“ für später stehen

        self.layout_.addStretch()

        self.refresh()
        self.combo.currentIndexChanged.connect(self._apply)
        self.length_auto.toggled.connect(self._apply)
        self.length.valueChanged.connect(self._apply)
        self.margin.valueChanged.connect(self._apply)
        self.horizontal.toggled.connect(self._apply)
        self.frame_style.currentIndexChanged.connect(self._apply_frame)
        self.frame_rounded.toggled.connect(self._apply_frame)
        for box in self._frame_boxes():
            box.valueChanged.connect(self._apply_frame)

    def _widgets(self):
        return (self.combo, self.length_auto, self.length, self.margin, self.horizontal, self.vertical,
                self.frame_style, self.frame_rounded, *self._frame_boxes())

    def _frame_boxes(self) -> tuple[DoubleSpinBox, ...]:
        return (self.frame_line, self.frame_inset, self.frame_padding)

    def _apply_frame(self) -> None:
        """Rahmen aus den Feldern; „Kein“ = kein Rahmen (die Felder bleiben für später stehen)."""
        style = self.frame_style.currentData()
        frame = Frame(style or self._last_frame.style, self.frame_rounded.isChecked(),
                      self.frame_line.value(), self.frame_inset.value(), self.frame_padding.value())
        self._last_frame = frame
        self.doc.frame = None if style is None else frame
        self._update_frame_widgets()
        self.changed.emit()
        self.edited.emit()           # jede Rahmen-Änderung ist ein eigener Schritt

    def _apply(self) -> None:
        self.doc.label_id = self.combo.currentData()
        self.media_adjusted = False   # Auswahl ist jetzt vom Nutzer
        self.doc.length_mm = None if self.length_auto.isChecked() else self.length.value()
        self.doc.margin_mm = self.margin.value()
        self.doc.orientation = "horizontal" if self.horizontal.isChecked() else "vertical"
        self._update_visibility()
        self._update_media_status()
        self.changed.emit()
        self.edited.emit()           # jede Papier-Änderung ist ein eigener Schritt

    def refresh(self) -> None:
        for w in self._widgets():
            w.blockSignals(True)
        self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
        self.length_auto.setChecked(self.doc.length_mm is None)
        if self.doc.length_mm is not None:
            self.length.setValue(self.doc.length_mm)
        self.margin.setValue(self.doc.margin_mm)
        (self.horizontal if self.doc.orientation == "horizontal" else self.vertical).setChecked(True)
        if self.doc.frame is not None:
            self._last_frame = self.doc.frame
        frame = self._last_frame                     # ohne Rahmen: zuletzt gewählte Werte
        self.frame_style.setCurrentIndex(self.frame_style.findData(
            None if self.doc.frame is None else frame.style))
        self.frame_rounded.setChecked(frame.rounded)
        for box, value in zip(self._frame_boxes(), (frame.line_mm, frame.inset_mm, frame.padding_mm)):
            box.setValue(value)
        for w in self._widgets():
            w.blockSignals(False)
        self._update_visibility()
        self._update_media_status()

    # --- Medium prüfen ----------------------------------------------------
    def set_checking(self, running: bool) -> None:
        self.check.setEnabled(not running)
        self.check.setText("PRÜFE …" if running else "MEDIUM PRÜFEN")

    def show_media(self, media: Media, label_id: str | None, adjusted: bool = False) -> None:
        self.media, self.media_label, self.media_adjusted = media, label_id, adjusted
        self._update_media_status()

    def show_media_error(self, message: str) -> None:
        self.media = self.media_label = None
        self._set_media_status(message.replace("\n", " "), "error")

    def clear_media(self) -> None:
        self.media = self.media_label = None
        self._set_media_status("", "")

    def _update_media_status(self) -> None:
        if self.media is None:
            return
        if self.media.kind == "none":
            self._set_media_status("Rolle: keine eingelegt", "warn")
        elif self.media_label is None:
            self._set_media_status(f"Rolle: {self.media.describe()} – kein passendes Etikett", "warn")
        elif self.media_label == self.doc.label_id:
            hint = " – Etikett angepasst" if self.media_adjusted else ""
            self._set_media_status(f"Rolle: {self.media.describe()} ✓{hint}", "ok")
        else:
            self._set_media_status(f"Rolle: {self.media.describe()} – Auswahl passt nicht", "warn")

    def _set_media_status(self, text: str, state: str) -> None:
        self.media_status_changed.emit(text, state)

    def _update_visibility(self) -> None:
        label = get_label(self.doc.label_id)
        endless = label.shape == "endless"
        self.length_title.setVisible(endless)
        self.length_box.setVisible(endless)
        self.length.setEnabled(not self.length_auto.isChecked())
        self.fixed_size.setVisible(not endless)
        w, h = label.size_mm
        self.fixed_size.setText(f"Ø {w} mm · rund" if label.shape == "round"
                                else f"{w} × {h} mm · gestanzt")
        self._update_frame_widgets()

    def _update_frame_widgets(self) -> None:
        """Felder nur mit Rahmen; runde Etiketten: Kreis – keine Ecken, nicht abgerundet."""
        round_label = get_label(self.doc.label_id).shape == "round"
        corners = self.frame_style.findData("corners")
        self.frame_style.model().item(corners).setEnabled(not round_label)
        self.frame_style.setToolTip(ROUND_TIP if round_label else "")
        active = self.doc.frame is not None
        self.frame_rounded.setEnabled(active and not round_label)
        for box in self._frame_boxes():
            box.setEnabled(active)
