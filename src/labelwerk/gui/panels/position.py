"""Bereich „Position“ der Objekt-Panels: Lage (X/Y) und Größe (B/H) des Rahmens in mm.

Gemeinsames Widget für alle Objektarten; das Panel zeigt damit den Rahmen, wie ihn das
Hauptfenster gerendert hat (``show_frame``), und meldet geänderte Felder (``edited``).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ...document import MAX_POSITION_MM
from ...i18n import N_, _
from ...layout import Rect
from ..widgets import DoubleSpinBox

POSITION_MM = (-MAX_POSITION_MM, MAX_POSITION_MM)   # Lage darf auch neben dem Etikett liegen (ragt hinaus)
SIZE_MM = (1.0, 999.9)
FRAME_ONLY = N_("Only changeable with a fixed frame size")
_FIELDS = (("x", "X", N_("Distance from the left edge of the label")),
           ("y", "Y", N_("Distance from the top edge of the label")),
           ("w", N_("W"), N_("Width of the frame")),         # B(reite)
           ("h", N_("H"), N_("Height of the frame")))


class PositionSection(QWidget):
    """Vier Zahlenfelder X/Y/B/H (mm, 0,1 mm genau). Breite und Höhe lassen sich nur ändern,
    wenn das Objekt eine änderbare Größe hat (``set_size_editable``) – sonst zeigen sie sie
    nur an (Pfeile sichtbar, ohne Wirkung). Der Besitzer ruft ``set_size_editable`` (oder
    ``show_frame``) jedes Mal auf, wenn sich bei seinem Objekt ändert, ob die Größe änderbar
    ist (z. B. feste Rahmengröße an/aus) – sonst meldet der Bereich veraltet."""

    edited = Signal(str, float)     # Feld ("x" | "y" | "w" | "h") und neuer Wert in mm

    def __init__(self, parent=None):
        super().__init__(parent)
        self._size_editable = True
        self.spins = {key: DoubleSpinBox() for key, __, ___ in _FIELDS}   # x, y, w, h
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, (key, text, tip) in enumerate(_FIELDS):
            spin = self.spins[key]
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
            spin.setRange(*(POSITION_MM if key in "xy" else SIZE_MM))
            spin.setKeyboardTracking(False)        # erst nach Enter/Fokuswechsel/Pfeil übernehmen
            spin.setToolTip(_(tip))
            label = QLabel(text if key in "xy" else _(text))
            label.setToolTip(_(tip))
            grid.addWidget(label, i // 2, (i % 2) * 2)
            grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)
            spin.valueChanged.connect(lambda value, k=key: self._changed(k, value))
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.set_size_editable(False)

    def show_frame(self, rect: Rect | None, editable_size: bool) -> None:
        """Rahmen in mm anzeigen (None = Nullen), ohne ``edited`` auszulösen."""
        for key, spin in self.spins.items():
            spin.blockSignals(True)
            spin.setValue(getattr(rect, key) if rect is not None else 0.0)
            spin.blockSignals(False)
        self.set_size_editable(editable_size)

    def set_size_editable(self, editable: bool) -> None:
        """Breite/Höhe änderbar bzw. nur Anzeige der Größe."""
        self._size_editable = editable
        for spin, tip in ((self.spins["w"], _("Width of the frame")),
                          (self.spins["h"], _("Height of the frame"))):
            if spin.isReadOnly() == editable:
                spin.setReadOnly(not editable)       # Pfeile bleiben sichtbar, wirken aber nicht
                spin.style().unpolish(spin)          # Stylesheet: [readOnly="true"] neu anwenden
                spin.style().polish(spin)
            spin.setToolTip(tip if editable else f"{tip} – {_(FRAME_ONLY)}")

    def _changed(self, key: str, value: float) -> None:
        if key in "wh" and not self._size_editable:
            return
        self.edited.emit(key, value)
