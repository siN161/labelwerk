"""Panel „Text“: Inhalt und Schriftgröße des Textobjekts."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QSpinBox

from ...document import Document, TextObject
from . import Panel


class TextPanel(Panel):
    def __init__(self, doc: Document):
        super().__init__(doc, "Text")
        if not doc.objects:
            doc.objects.append(TextObject())

        self.section("Inhalt")
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Text eingeben …")
        self.layout_.addWidget(self.edit)

        self.section("Schriftgröße")
        row = QHBoxLayout()
        self.auto = QCheckBox("Automatisch")
        self.size = QSpinBox()
        self.size.setRange(8, 400)
        self.size.setValue(60)
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
        self.obj.text = self.edit.toPlainText()
        self.obj.font_size = None if self.auto.isChecked() else self.size.value()
        self.size.setEnabled(not self.auto.isChecked())
        self.changed.emit()

    def refresh(self) -> None:
        for w in (self.edit, self.auto, self.size):
            w.blockSignals(True)
        if self.edit.toPlainText() != self.obj.text:
            self.edit.setPlainText(self.obj.text)
        self.auto.setChecked(self.obj.font_size is None)
        if self.obj.font_size is not None:
            self.size.setValue(self.obj.font_size)
        self.size.setEnabled(not self.auto.isChecked())
        for w in (self.edit, self.auto, self.size):
            w.blockSignals(False)

    def show_error(self, message: str | None) -> None:
        self.error.setText(message or "")
        self.error.setVisible(bool(message))
