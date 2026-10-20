"""Property panels: one per tool, they edit their part of the document."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...document import Document


class Panel(QWidget):
    """Base: holds the document, emits changed after every change.

    ``edited`` reports a completed state for undo (the main window keeps it;
    without a change since the last state it is not a new step).
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
        label.setWordWrap(True)                  # long titles (other languages) wrap
        self.layout_.addWidget(label)
        return label

    def refresh(self) -> None:
        """Reset the widgets from the document (e.g. after dragging on the canvas)."""

    def show_error(self, message: str | None) -> None:
        """Show an error message or clear it with None (only where useful)."""

    def set_selection(self, indices: list[int]) -> None:
        """Selection on the canvas has changed (indices in the order of selection)."""

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """Take over actions of the main window (``gui.actions``) for own buttons."""

    def set_icon_style(self, dark_checked: bool) -> None:
        """Adapt icons to the theme (white on black only in BlackWerk)."""
