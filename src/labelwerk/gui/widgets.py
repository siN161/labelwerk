"""Kleine Widget-Anpassungen, die für alle Panels und Dialoge gelten."""
from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

# Qt legt das Textfeld eines per Stylesheet gerahmten Zahlenfelds über den linken Rahmen;
# ein Textrand hält die Zahl lesbar (Innenabstände im Stylesheet greifen dort nicht).
TEXT_MARGIN = 10


class SpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(TEXT_MARGIN, 0, 0, 0)


class DoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(TEXT_MARGIN, 0, 0, 0)
