"""Eigenschaften-Panels: je Werkzeug eines, bearbeiten ihren Teil des Dokuments."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...document import Document


class Panel(QWidget):
    """Basis: hält das Dokument, sendet changed nach jeder Änderung.

    ``edited`` meldet einen abgeschlossenen Stand für Rückgängig (das Hauptfenster hält ihn
    fest; ohne Änderung seit dem letzten Stand ist das kein neuer Schritt).
    """

    changed = Signal()
    edited = Signal()

    def __init__(self, doc: Document, title: str):
        super().__init__()
        self.doc = doc
        self.layout_ = QVBoxLayout(self)
        heading = QLabel(title.upper())
        heading.setObjectName("panelTitle")
        self.layout_.addWidget(heading)

    def section(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setProperty("role", "section")
        self.layout_.addWidget(label)
        return label

    def refresh(self) -> None:
        """Widgets aus dem Dokument neu setzen (z. B. nach Ziehen auf der Arbeitsfläche)."""

    def show_error(self, message: str | None) -> None:
        """Fehlermeldung anzeigen bzw. mit None löschen (nur wo sinnvoll)."""
