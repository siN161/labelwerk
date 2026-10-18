"""Bereich „Position“ der Objekt-Panels: Lage (X/Y) und Größe (B/H) des Rahmens in mm.

Gemeinsames Widget für alle Objektarten; das Panel zeigt damit den Rahmen, wie ihn das
Hauptfenster gerendert hat (``show_frame``), und meldet geänderte Felder (``edited``).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ...layout import Rect
from ..widgets import DoubleSpinBox

POSITION_MM = (-999.9, 999.9)    # Lage darf auch neben dem Etikett liegen (ragt hinaus)
SIZE_MM = (1.0, 999.9)
FRAME_ONLY = "Nur mit fester Rahmengröße änderbar"
_FIELDS = (("x", "X", "Abstand vom linken Etikettrand"),
           ("y", "Y", "Abstand vom oberen Etikettrand"),
           ("w", "B", "Breite des Rahmens"),
           ("h", "H", "Höhe des Rahmens"))


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
        self.spins = {key: DoubleSpinBox() for key, _, _ in _FIELDS}   # x, y, w, h
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, (key, text, tip) in enumerate(_FIELDS):
            spin = self.spins[key]
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
            spin.setRange(*(POSITION_MM if key in "xy" else SIZE_MM))
            spin.setKeyboardTracking(False)        # erst nach Enter/Fokuswechsel/Pfeil übernehmen
            spin.setToolTip(tip)
            label = QLabel(text)
            label.setToolTip(tip)
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
        for spin, name in ((self.spins["w"], "Breite"), (self.spins["h"], "Höhe")):
            if spin.isReadOnly() == editable:
                spin.setReadOnly(not editable)       # Pfeile bleiben sichtbar, wirken aber nicht
                spin.style().unpolish(spin)          # Stylesheet: [readOnly="true"] neu anwenden
                spin.style().polish(spin)
            spin.setToolTip(f"{name} des Rahmens" + ("" if editable else f" – {FRAME_ONLY}"))

    def _changed(self, key: str, value: float) -> None:
        if key in "wh" and not self._size_editable:
            return
        self.edited.emit(key, value)
