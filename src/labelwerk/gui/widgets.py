"""Kleine Widget-Anpassungen, die für alle Panels und Dialoge gelten."""
from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

from .. import i18n

# Qt legt das Textfeld eines per Stylesheet gerahmten Zahlenfelds über den linken Rahmen;
# ein Textrand hält die Zahl lesbar (Innenabstände im Stylesheet greifen dort nicht).
TEXT_MARGIN = 10


class SpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(TEXT_MARGIN, 0, 0, 0)


class DoubleSpinBox(QDoubleSpinBox):
    """Zeigt Zahlen mit dem Dezimaltrenner der Sprache (``QLocale``); getippt gelten Komma und
    Punkt (ein Punkt wird in Deutsch zum Komma und umgekehrt)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(TEXT_MARGIN, 0, 0, 0)

    def _own(self, text: str) -> str:
        own = self.locale().decimalPoint()
        return text.replace("." if own == "," else ",", own)

    def validate(self, text: str, pos: int):
        return super().validate(self._own(text), pos)

    def valueFromText(self, text: str) -> float:
        return super().valueFromText(self._own(text))
