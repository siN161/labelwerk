"""Panel „Papier“: Etikett, Länge (Endlosband), Ränder, Zierrahmen und Ausrichtung – wie im
P-touch Editor."""
from __future__ import annotations

from PIL import Image, ImageOps
from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QRadioButton, QWidget)

from ... import layout
from ...document import FRAME_LINE_MM, MAX_FRAME_MM, MAX_MARGIN_MM, Document, Frame
from ...i18n import N_, _
from ...labels import DPI, format_mm, get_label, labels_for_model, length_limits, mm_text
from ...media import Media
from ...printer import DEFAULT_MODEL
from ...render import frame_mask
from ..widgets import DoubleSpinBox
from . import Panel

_GROUPS = (("endless", N_("Continuous")), ("die_cut", N_("Die-cut")), ("round", N_("Round")))
FRAME_TITLES = ((N_("No border"), None), (N_("Single"), "single"), (N_("Double"), "double"),
                (N_("Thick-thin"), "thick_thin"), (N_("Dashed"), "dashed"), (N_("Dotted"), "dotted"),
                (N_("Corners only"), "corners"))
FRAME_ICON = QSize(56, 22)
ROUND_TIP = N_("On round labels every border becomes a circle.")
NOTE_STYLE = "color: #666666; font-size: 11px; font-weight: 400; border: none; padding: 0;"


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
        super().__init__(doc, _("Paper"))
        self.media: Media | None = None          # zuletzt erkannte Rolle
        self.media_label: str | None = None      # passendes Etikett dazu
        self.media_adjusted = False              # Etikett wurde automatisch angepasst

        self.section(_("Label"))
        self.combo = QComboBox()
        self.model = model
        self._fill_labels()
        self.layout_.addWidget(self.combo)
        self.check = QPushButton(_("CHECK MEDIA"))
        self.check.setToolTip(_("Ask the printer which roll is loaded (prints nothing)"))
        self.check.clicked.connect(self.check_media_requested)
        self.layout_.addWidget(self.check)

        self.length_title = self.section(_("Length"))
        self.length_box = QWidget()
        row = QHBoxLayout(self.length_box)
        row.setContentsMargins(0, 0, 0, 0)
        self.length_auto = QCheckBox(_("Automatic"))
        self.length = DoubleSpinBox()
        self.length.setSuffix(" mm")
        self.length.setDecimals(1)
        self.length.setSingleStep(0.5)
        self._set_length_range()
        self.length.setValue(50.0)
        row.addWidget(self.length_auto)
        row.addWidget(self.length)
        self.layout_.addWidget(self.length_box)

        self.fixed_size = QLabel()
        self.fixed_size.setObjectName("fixedSize")
        self.layout_.addWidget(self.fixed_size)

        self.section(_("Orientation"))
        self.horizontal = QRadioButton(_("Horizontal"))
        self.horizontal.setToolTip(_("Label in landscape – text runs along the tape"))
        self.vertical = QRadioButton(_("Vertical"))
        self.vertical.setToolTip(_("Label in portrait – text runs across the tape"))
        self.orientation_group = QButtonGroup(self)
        for button in (self.horizontal, self.vertical):
            self.orientation_group.addButton(button)
            self.layout_.addWidget(button)
        self.section(_("Margins"))
        self.margin = DoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.layout_.addWidget(self.margin)
        self.margin_hint = QLabel()                 # Rand längs kleiner als der Vorschub
        self.margin_hint.setObjectName("note")
        self.margin_hint.setStyleSheet(NOTE_STYLE)   # dezent, in jedem Design
        self.margin_hint.setWordWrap(True)
        self.layout_.addWidget(self.margin_hint)

        self.section(_("Border"))
        self.frame_style = QComboBox()
        self.frame_style.setIconSize(FRAME_ICON)
        for title, style in FRAME_TITLES:
            self.frame_style.addItem(frame_icon(style), _(title), style)
        self.layout_.addWidget(self.frame_style)
        self.frame_rounded = QCheckBox(_("Rounded"))
        self.layout_.addWidget(self.frame_rounded)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)              # Felder füllen die Breite (wie die übrigen)
        defaults = Frame()
        self.frame_line = _spin(*FRAME_LINE_MM, 0.1, _("Line width"))
        self.frame_inset = _spin(0.0, MAX_FRAME_MM, 0.5,
                                 _("Distance of the border from the printable edge"))
        self.frame_padding = _spin(0.0, MAX_FRAME_MM, 0.5,
                                   _("Distance between the border and automatically placed text"))
        self.frame_labels: list[QLabel] = []
        for row, (title, box, value) in enumerate((
                (_("Line"), self.frame_line, defaults.line_mm),
                (_("Inset"), self.frame_inset, defaults.inset_mm),
                (_("Padding"), self.frame_padding, defaults.padding_mm))):
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

    def set_model(self, model: str) -> None:
        """Druckermodell gewechselt: Etiketten und Längengrenzen folgen; das Etikett des Dokuments
        bleibt (passt es nicht, steht es mit Hinweis in der Liste)."""
        if model == self.model:
            return
        self.model = model
        for w in self._widgets():
            w.blockSignals(True)
        self._fill_labels()
        self._set_length_range()
        for w in self._widgets():
            w.blockSignals(False)
        self.refresh()

    def _fill_labels(self) -> None:
        """Etiketten des Modells nach Form gruppiert; ein Etikett des Dokuments, das das Modell
        nicht kann, bleibt sichtbar („passt nicht zum …“), damit nichts still umgestellt wird."""
        self.combo.clear()
        labels = labels_for_model(self.model)
        for shape, title in _GROUPS:
            group = [lbl for lbl in labels if lbl.shape == shape]
            if not group:
                continue
            self.combo.addItem(f"— {_(title)} —")
            self.combo.model().item(self.combo.count() - 1).setEnabled(False)
            for lbl in group:
                self.combo.addItem(lbl.description, lbl.id)
        self._unfit = None
        if self.combo.findData(self.doc.label_id) < 0:      # gewählt bleibt es, wählbar nicht
            self._unfit = self.doc.label_id
            self.combo.addItem(_("{label} – does not fit the {model}").format(
                label=get_label(self.doc.label_id).description, model=self.model), self.doc.label_id)
            self.combo.model().item(self.combo.count() - 1).setEnabled(False)

    def _set_length_range(self) -> None:
        """Länge des Stücks: Grenzen des Modells (für das Druckbild) plus Vorschub an beiden
        Enden."""
        min_len, max_len = length_limits(self.model)
        feed = 2 * get_label(self.doc.label_id).feed_margin
        blocked = self.length.blockSignals(True)
        self.length.setRange(round((min_len + feed) * 25.4 / DPI, 1),
                             round((max_len + feed) * 25.4 / DPI, 1))
        self.length.blockSignals(blocked)

    def _apply(self) -> None:
        layout.change_label(self.doc, self.combo.currentData())
        if self._unfit is not None and self._unfit != self.doc.label_id:
            self.combo.blockSignals(True)
            self._fill_labels()                      # Eintrag „passt nicht“ verschwindet
            self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
            self.combo.blockSignals(False)
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
        if self.combo.findData(self.doc.label_id) < 0 or (
                self._unfit is not None and self._unfit != self.doc.label_id):
            self._fill_labels()          # andere Datei bzw. passendes Etikett: Liste neu
        self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
        self._set_length_range()                     # Grenzen des Etiketts vor seinem Wert
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
        self.check.setText(_("CHECKING …") if running else _("CHECK MEDIA"))

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
            self._set_media_status(_("Roll: none loaded"), "warn")
        elif self.media_label is None:
            self._set_media_status(_("Roll: {media} – no matching label").format(
                media=self.media.describe()), "warn")
        elif self.media_label == self.doc.label_id:
            text = _("Roll: {media} ✓ – label adjusted") if self.media_adjusted else _("Roll: {media} ✓")
            self._set_media_status(text.format(media=self.media.describe()), "ok")
        else:
            self._set_media_status(_("Roll: {media} – selection does not match").format(
                media=self.media.describe()), "warn")

    def _set_media_status(self, text: str, state: str) -> None:
        self.media_status_changed.emit(text, state)

    def _update_visibility(self) -> None:
        label = get_label(self.doc.label_id)
        endless = label.shape == "endless"
        self.length_title.setVisible(endless)
        self.length_box.setVisible(endless)
        self.length.setEnabled(not self.length_auto.isChecked())
        self._set_length_range()                       # Vorschub hängt am Etikett
        strip = label.feed_margin
        self.margin_hint.setVisible(endless and round(self.doc.margin_mm * label.dpi / 25.4) < strip)
        self.margin_hint.setText(_("Along the tape the printer leaves {mm} mm free – a smaller "
                                   "margin has no effect there.").format(mm=format_mm(strip, label.dpi)))
        across = (label.total_width - label.width) // 2
        along = strip if endless else (label.total_height - label.height) // 2
        self.margin.setToolTip(
            _("Distance from the paper edge all around (the printer leaves about {across} mm free "
              "across the tape and about {along} mm along it anyway)").format(
                across=format_mm(across, label.dpi), along=format_mm(along, label.dpi))
            if across or along else _("Distance from the paper edge all around"))
        self.fixed_size.setVisible(not endless)
        w, h = label.size_mm
        w, h = mm_text(w), mm_text(h)
        self.fixed_size.setText(_("Ø {width} mm · round").format(width=w) if label.shape == "round"
                                else _("{width} × {height} mm · die-cut").format(width=w, height=h))
        self._update_frame_widgets()

    def _update_frame_widgets(self) -> None:
        """Felder nur mit Rahmen; runde Etiketten: Kreis – keine Ecken, nicht abgerundet."""
        round_label = get_label(self.doc.label_id).shape == "round"
        corners = self.frame_style.findData("corners")
        self.frame_style.model().item(corners).setEnabled(not round_label)
        self.frame_style.setToolTip(_(ROUND_TIP) if round_label else "")
        active = self.doc.frame is not None
        self.frame_rounded.setEnabled(active and not round_label)
        for box in self._frame_boxes():
            box.setEnabled(active)
