"""Panel „Papier“: Etikett, Länge (Endlosband), Ränder und Ausrichtung – wie im P-touch Editor."""
from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout,
                               QLabel, QRadioButton, QWidget)

from ...document import MAX_MARGIN_MM, Document
from ...labels import DPI, get_label, labels_for_model, length_limits
from ...printer import DEFAULT_MODEL
from . import Panel

_GROUPS = (("endless", "Endlos"), ("die_cut", "Gestanzt"), ("round", "Rund"))


class PaperPanel(Panel):
    def __init__(self, doc: Document, model: str = DEFAULT_MODEL):
        super().__init__(doc, "Papier")

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

        self.length_title = self.section("Länge")
        self.length_box = QWidget()
        row = QHBoxLayout(self.length_box)
        row.setContentsMargins(0, 0, 0, 0)
        self.length_auto = QCheckBox("Automatisch")
        self.length = QDoubleSpinBox()
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

        self.section("Ränder")
        self.margin = QDoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setToolTip("Abstand vorne/hinten in Bandlaufrichtung")
        self.layout_.addWidget(self.margin)

        self.section("Ausrichtung")
        self.horizontal = QRadioButton("Horizontal")
        self.horizontal.setToolTip("Text längs zum Band – z. B. Versandetikett")
        self.vertical = QRadioButton("Vertikal")
        self.vertical.setToolTip("Text quer zum Band")
        self.orientation_group = QButtonGroup(self)
        for button in (self.horizontal, self.vertical):
            self.orientation_group.addButton(button)
            self.layout_.addWidget(button)
        self.layout_.addStretch()

        self.refresh()
        self.combo.currentIndexChanged.connect(self._apply)
        self.length_auto.toggled.connect(self._apply)
        self.length.valueChanged.connect(self._apply)
        self.margin.valueChanged.connect(self._apply)
        self.horizontal.toggled.connect(self._apply)

    def _widgets(self):
        return (self.combo, self.length_auto, self.length, self.margin, self.horizontal, self.vertical)

    def _apply(self) -> None:
        self.doc.label_id = self.combo.currentData()
        self.doc.length_mm = None if self.length_auto.isChecked() else self.length.value()
        self.doc.margin_mm = self.margin.value()
        self.doc.orientation = "horizontal" if self.horizontal.isChecked() else "vertical"
        self._update_visibility()
        self.changed.emit()

    def refresh(self) -> None:
        for w in self._widgets():
            w.blockSignals(True)
        self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
        self.length_auto.setChecked(self.doc.length_mm is None)
        if self.doc.length_mm is not None:
            self.length.setValue(self.doc.length_mm)
        self.margin.setValue(self.doc.margin_mm)
        (self.horizontal if self.doc.orientation == "horizontal" else self.vertical).setChecked(True)
        for w in self._widgets():
            w.blockSignals(False)
        self._update_visibility()

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
