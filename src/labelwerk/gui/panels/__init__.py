"""Eigenschaften-Panels: je Werkzeug eines, bearbeiten ihren Teil des Dokuments."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
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
        label.setWordWrap(True)                  # lange Titel (andere Sprachen) brechen um
        self.layout_.addWidget(label)
        return label

    def refresh(self) -> None:
        """Widgets aus dem Dokument neu setzen (z. B. nach Ziehen auf der Arbeitsfläche)."""

    def show_error(self, message: str | None) -> None:
        """Fehlermeldung anzeigen bzw. mit None löschen (nur wo sinnvoll)."""

    def set_selection(self, indices: list[int]) -> None:
        """Auswahl auf der Arbeitsfläche hat sich geändert (Indizes in der Reihenfolge der Wahl)."""

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """Aktionen des Hauptfensters (``gui.actions``) für eigene Knöpfe übernehmen."""

    def set_icon_style(self, dark_checked: bool) -> None:
        """Symbole an das Design anpassen (weiß auf schwarz nur bei RawBlock)."""
