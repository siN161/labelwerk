"""“Position” area of the object panels: position (X/Y) and size (W/H) of the frame in mm.

Shared widget for all object kinds; the panel uses it to show the frame as the
main window rendered it (``show_frame``) and reports changed fields (``edited``).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ...document import MAX_POSITION_MM
from ...i18n import N_, _
from ...layout import Rect
from ..widgets import DoubleSpinBox

POSITION_MM = (-MAX_POSITION_MM, MAX_POSITION_MM)   # position may also lie beside the label (sticks out)
SIZE_MM = (1.0, 999.9)
FRAME_ONLY = N_("Only changeable with a fixed frame size")
_FIELDS = (("x", "X", N_("Distance from the left edge of the label")),
           ("y", "Y", N_("Distance from the top edge of the label")),
           ("w", N_("W"), N_("Width of the frame")),         # W(idth)
           ("h", N_("H"), N_("Height of the frame")))


class PositionSection(QWidget):
    """Four number fields X/Y/W/H (mm, 0.1 mm precision). Width and height can only be changed
    if the object has a changeable size (``set_size_editable``) – otherwise they only
    display it (arrows visible, no effect). The owner calls ``set_size_editable`` (or
    ``show_frame``) every time it changes for its object whether the size is changeable
    (e.g. fixed frame size on/off) – otherwise the area reports outdated values."""

    edited = Signal(str, float)     # field ("x" | "y" | "w" | "h") and new value in mm

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
            spin.setKeyboardTracking(False)        # accept only after Enter/focus change/arrow
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
        """Show the frame in mm (None = zeros) without triggering ``edited``."""
        for key, spin in self.spins.items():
            spin.blockSignals(True)
            spin.setValue(getattr(rect, key) if rect is not None else 0.0)
            spin.blockSignals(False)
        self.set_size_editable(editable_size)

    def set_size_editable(self, editable: bool) -> None:
        """Width/height changeable or display of the size only."""
        self._size_editable = editable
        for spin, tip in ((self.spins["w"], _("Width of the frame")),
                          (self.spins["h"], _("Height of the frame"))):
            if spin.isReadOnly() == editable:
                spin.setReadOnly(not editable)       # arrows stay visible but have no effect
                spin.style().unpolish(spin)          # stylesheet: re-apply [readOnly="true"]
                spin.style().polish(spin)
            spin.setToolTip(tip if editable else f"{tip} – {_(FRAME_ONLY)}")

    def _changed(self, key: str, value: float) -> None:
        if key in "wh" and not self._size_editable:
            return
        self.edited.emit(key, value)
