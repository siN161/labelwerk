"""Kleine Widget-Anpassungen, die für alle Panels und Dialoge gelten."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox

from .. import fonts, i18n

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


MIN_FONT_CHARS = 8                              # Schriftauswahl: so viele Zeichen mindestens breit


class FontCombo(QComboBox):
    """Schriftauswahl aus ``fonts.families`` (statt QFontComboBox: keine Qt-Sammelnamen wie
    „Sans Serif“, nur die kurze Liste), jede Schrift in ihrer Schrift. Eine Schrift, die nicht in
    der Liste steht (aus Datei oder Einstellung), erscheint oben und gewählt – nichts geht
    verloren. ``family_chosen`` meldet jede andere Schrift (Wahl in der Liste oder
    ``set_current_family``), nie „leer“."""
    family_chosen = Signal(str)

    def __init__(self, names: list[str] | None = None, parent=None):
        super().__init__(parent)
        # Breite unabhängig von den Namen (wie QFontComboBox) – lange Namen weiten das Panel nicht
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(MIN_FONT_CHARS)
        self._extra: str | None = None          # fremde Schrift oben in der Liste
        self._last: str | None = None           # zuletzt gemeldete bzw. gesetzte Schrift
        self.set_families(fonts.families() if names is None else names)
        self.currentIndexChanged.connect(self._index_changed)

    def current_family(self) -> str | None:
        return self.currentText() if self.currentIndex() >= 0 else None

    def set_families(self, names: list[str]) -> None:
        """Liste neu füllen; die gewählte Schrift bleibt (notfalls als fremde Schrift oben)."""
        current = self.current_family()
        blocked = self.blockSignals(True)
        try:
            self.clear()
            self._extra = None
            size = self.font().pointSizeF()
            for name in names:
                font = QFont(name)
                if size > 0:
                    font.setPointSizeF(size)
                self.addItem(name)
                self.setItemData(self.count() - 1, font, Qt.ItemDataRole.FontRole)
            self._select(current)
        finally:
            self.blockSignals(blocked)

    def set_current_family(self, name: str | None) -> None:
        """Schrift anzeigen (None = leer, z. B. gemischte Schriften); meldet ``family_chosen``,
        wenn sich eine Schrift ändert (außer bei blockierten Signalen)."""
        name = fonts.canonical(name)            # alter Qt-Name „C059 [UKWN]“ → „C059“
        changed = name != self._last
        blocked = self.blockSignals(True)
        try:
            self._select(name)
        finally:
            self.blockSignals(blocked)
        if changed and name is not None and not blocked:
            self.family_chosen.emit(name)

    def _select(self, name: str | None) -> None:
        if name is None:
            self.setCurrentIndex(-1)
            self._last = None
            return
        if self._extra is not None and self._extra != name:
            self.removeItem(0)                  # nur ein fremder Eintrag
            self._extra = None
        index = self.findText(name, Qt.MatchFlag.MatchExactly)
        if index < 0:
            self.insertItem(0, name)
            self._extra = name
            index = 0
        self.setCurrentIndex(index)
        self._last = name

    def _index_changed(self, index: int) -> None:
        name = self.current_family()
        if name != self._last:
            self._last = name
            if name is not None:
                self.family_chosen.emit(name)
