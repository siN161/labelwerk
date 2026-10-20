"""Small widget adjustments that apply to all panels and dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox

from .. import fonts, i18n

# Qt puts the text field of a number field framed by a stylesheet over the left frame edge;
# a text margin keeps the number readable (paddings in the stylesheet do not take effect there).
TEXT_MARGIN = 10


class SpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(TEXT_MARGIN, 0, 0, 0)


class DoubleSpinBox(QDoubleSpinBox):
    """Shows numbers with the language's decimal separator (``QLocale``); when typed, comma and
    period both work (a period becomes a comma in German and vice versa)."""

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


MIN_FONT_CHARS = 8                              # font selection: at least this many characters wide


class FontCombo(QComboBox):
    """Font selection from ``fonts.families`` (instead of QFontComboBox: no Qt collective names like
    “Sans Serif”, only the short list), each font shown in its own typeface. A font that is not in
    the list (from a file or a setting) appears at the top and selected – nothing gets lost.
    ``family_chosen`` reports every other font (choice in the list or
    ``set_current_family``), never “empty”."""
    family_chosen = Signal(str)

    def __init__(self, names: list[str] | None = None, parent=None):
        super().__init__(parent)
        # Width independent of the names (like QFontComboBox) – long names do not widen the panel
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(MIN_FONT_CHARS)
        self._extra: str | None = None          # foreign font at the top of the list
        self._last: str | None = None           # last reported or set font
        self.set_families(fonts.families() if names is None else names)
        self.currentIndexChanged.connect(self._index_changed)

    def current_family(self) -> str | None:
        return self.currentText() if self.currentIndex() >= 0 else None

    def set_families(self, names: list[str]) -> None:
        """Refill the list; the chosen font stays (if need be as a foreign font at the top)."""
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
        """Show a font (None = empty, e.g. mixed fonts); reports ``family_chosen``
        when a font changes (except with blocked signals)."""
        name = fonts.canonical(name)            # old Qt name “C059 [UKWN]” → “C059”
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
            self.removeItem(0)                  # only a foreign entry
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
