"""Dialog „Einstellungen“: Standardwerte für neue Etiketten, Drucker, Ansicht.

Neue Einstellung = Feld in settings.Settings + eine Zeile im passenden Abschnitt hier.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFontComboBox,
                               QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QVBoxLayout)

from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
from ..labels import labels_for_model
from ..printer import DEFAULT_MODEL
from ..settings import Settings, save_settings
from .widgets import DoubleSpinBox, SpinBox


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, path: str | Path | None = None,
                 model: str = DEFAULT_MODEL, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.path = path
        self.saved: Settings | None = None
        layout = QVBoxLayout(self)

        form = self._section(layout, "Neues Etikett")
        self.label = QComboBox()
        for lbl in labels_for_model(model):
            self.label.addItem(lbl.description, lbl.id)
        self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
        form.addRow("Etikett", self.label)
        self.orientation = QComboBox()
        self.orientation.addItem("Horizontal (Text längs zum Band)", "horizontal")
        self.orientation.addItem("Vertikal (Text quer zum Band)", "vertical")
        self.orientation.setCurrentIndex(self.orientation.findData(settings.orientation))
        form.addRow("Ausrichtung", self.orientation)
        self.margin = DoubleSpinBox()
        self.margin.setSuffix(" mm")
        self.margin.setDecimals(1)
        self.margin.setSingleStep(0.5)
        self.margin.setRange(0.0, MAX_MARGIN_MM)
        self.margin.setValue(settings.margin_mm)
        form.addRow("Ränder", self.margin)
        row = QHBoxLayout()
        self.font_auto = QCheckBox("Automatisch")
        self.font_size = DoubleSpinBox()
        self.font_size.setDecimals(1)
        self.font_size.setSingleStep(0.5)
        self.font_size.setRange(MIN_PT, MAX_PT)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(settings.font_size_pt or 19)
        self.font_auto.setChecked(settings.font_size_pt is None)
        self.font_size.setEnabled(settings.font_size_pt is not None)
        self.font_auto.toggled.connect(lambda auto: self.font_size.setEnabled(not auto))
        row.addWidget(self.font_auto)
        row.addWidget(self.font_size)
        form.addRow("Schriftgröße", row)
        self.font_family = QFontComboBox()
        self.font_family.setCurrentFont(QFont(settings.font_family))
        # Nicht installierte Schrift nicht stillschweigend durch Ersatz überschreiben
        self._orig_family = settings.font_family
        self._family_touched = False
        self.font_family.currentFontChanged.connect(self._family_changed)
        form.addRow("Schriftart", self.font_family)

        form = self._section(layout, "Drucker")
        self.check_media = QCheckBox("Rolle beim Start und beim Einschalten prüfen")
        self.check_media.setChecked(settings.check_media_on_start)
        form.addRow(self.check_media)

        form = self._section(layout, "Ansicht")
        self.zoom = SpinBox()
        self.zoom.setSuffix(" %")
        self.zoom.setRange(25, 400)
        self.zoom.setSingleStep(10)
        self.zoom.setValue(settings.start_zoom)
        form.addRow("Startzoom", self.zoom)

        hint = QLabel("Gilt für neue Etiketten bzw. ab dem nächsten Start.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
        box = QGroupBox(title.upper())
        form = QFormLayout(box)
        layout.addWidget(box)
        return form

    def _family_changed(self, _font) -> None:
        self._family_touched = True

    def values(self) -> Settings:
        return Settings(
            label_id=self.label.currentData(),
            orientation=self.orientation.currentData(),
            margin_mm=self.margin.value(),
            font_size_pt=None if self.font_auto.isChecked() else self.font_size.value(),
            font_family=(self.font_family.currentFont().family() if self._family_touched
                         else self._orig_family),
            check_media_on_start=self.check_media.isChecked(),
            start_zoom=self.zoom.value(),
        )

    def accept(self) -> None:
        settings = self.values()
        try:
            save_settings(settings, self.path)
        except OSError as e:
            self.error.setText(str(e))
            self.error.show()
            return                                   # Dialog bleibt offen
        self.saved = settings
        super().accept()
