"""Panel „Text“: Inhalt und Schriftgröße des Textobjekts."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit

from ...document import MAX_PT, MIN_PT, Document, TextObject
from ..widgets import SpinBox
from . import Panel


class TextPanel(Panel):
    def __init__(self, doc: Document):
        super().__init__(doc, "Text")
        if not doc.objects:
            doc.objects.append(TextObject(""))

        self.section("Inhalt")
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Text eingeben …")
        self.layout_.addWidget(self.edit)

        self.section("Schriftgröße (pt)")
        row = QHBoxLayout()
        self.auto = QCheckBox("Automatisch")
        self.size = SpinBox()
        self.size.setRange(int(MIN_PT), int(MAX_PT))
        self.size.setValue(19)
        row.addWidget(self.auto)
        row.addWidget(self.size)
        self.layout_.addLayout(row)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        self.layout_.addWidget(self.error)
        self.layout_.addStretch()

        self.refresh()
        self.edit.textChanged.connect(self._apply)
        self.auto.toggled.connect(self._apply)
        self.size.valueChanged.connect(self._apply)

    @property
    def obj(self) -> TextObject:
        return self.doc.objects[0]

    def _apply(self) -> None:
        size = None if self.auto.isChecked() else self.size.value()
        self.doc.objects[0] = TextObject.plain(self.edit.toPlainText(), size_pt=size,
                                               font_path=self.obj.font_path)
        self.size.setEnabled(not self.auto.isChecked())
        self.changed.emit()

    def refresh(self) -> None:
        for w in (self.edit, self.auto, self.size):
            w.blockSignals(True)
        if self.edit.toPlainText() != self.obj.text:
            self.edit.setPlainText(self.obj.text)
        self.auto.setChecked(self.obj.size_pt is None)
        if self.obj.size_pt is not None:
            self.size.setValue(round(self.obj.size_pt))
        self.size.setEnabled(not self.auto.isChecked())
        for w in (self.edit, self.auto, self.size):
            w.blockSignals(False)

    def show_error(self, message: str | None) -> None:
        self.error.setText(message or "")
        self.error.setVisible(bool(message))
