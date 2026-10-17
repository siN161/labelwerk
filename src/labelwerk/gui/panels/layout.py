"""Panel „Layout“: gewählte Objekte ausrichten, Größe angleichen, drehen, Reihenfolge – wie P-touch.

Die Knöpfe lösen die Aktionen des Hauptfensters aus (Kürzel-Verzeichnis, Kürzel im Tooltip);
gerechnet wird im Kern (``layout``). Ohne passende Auswahl sind die Knöpfe gesperrt.
"""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QToolButton

from ...document import Document
from ..symbols import SIZE, line_icon
from . import Panel

# Bereiche mit Knöpfen: (Aktion, Symbol)
LAYOUT_SECTIONS = (
    ("Gewählte Objekte ausrichten", tuple((f"align.{mode}", f"align-objects-{mode}") for mode in
                                          ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
    ("Am Papier ausrichten", tuple((f"align.paper_{mode}", f"align-paper-{mode}") for mode in
                                   ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
    ("Vergrößern/Verkleinern", (("size.maximize", "size-maximize"), ("size.same", "size-same"),
                                ("size.width", "size-width"), ("size.height", "size-height"))),
    ("Drehen", (("object.rotate_left", "rotate-left"), ("object.rotate_right", "rotate-right"))),
    ("Reihenfolge", (("object.bring_forward", "order-forward"),
                     ("object.send_backward", "order-backward"))),
)
_ICONS = {key: icon for _, row in LAYOUT_SECTIONS for key, icon in row}
# Aneinander ausrichten und angleichen braucht mindestens zwei Objekte, alles andere eins
_FROM_TWO = {key for key, _ in LAYOUT_SECTIONS[0][1]} | {"size.same", "size.width", "size.height"}
MIN_SELECTED = {key: 2 if key in _FROM_TWO else 1 for key in _ICONS}
# Am Papier in Bandrichtung ausrichten: je Achse der Leserichtung, in der das Etikett wächst
_PAPER_AXIS = {f"align.paper_{mode}": axis for axis, modes in
               (("x", ("left", "hcenter", "right")), ("y", ("top", "vcenter", "bottom")))
               for mode in modes}
GROWING_HINT = ("Bei automatischer Länge wächst das Etikett mit – Länge festlegen, "
                "um in Bandrichtung auszurichten")


class LayoutPanel(Panel):
    def __init__(self, doc: Document):
        super().__init__(doc, "Layout")
        self._dark = True
        self._count = 0
        self._grow: str | None = None
        self.buttons: dict[str, QToolButton] = {}
        for title, row in LAYOUT_SECTIONS:
            # lange Überschriften brechen an Leerzeichen um; ohne Leerzeichen nicht, sonst
            # reserviert Qt bei „/“ eine zweite Zeile
            self.section(title).setWordWrap(" " in title)
            line = QHBoxLayout()
            line.setSpacing(4)
            for key, _ in row:
                button = QToolButton()
                button.setObjectName("layoutButton")
                button.setAutoRaise(True)              # Symbol beim Darüberfahren: Modus „Active“
                button.setIconSize(SIZE)
                button.setEnabled(False)
                self.buttons[key] = button
                line.addWidget(button)
            line.addStretch()
            self.layout_.addLayout(line)
        self.layout_.addStretch()

    def use_actions(self, actions: dict[str, QAction]) -> None:
        for key, button in self.buttons.items():
            button.setDefaultAction(actions[key])
        self.set_icon_style(self._dark)
        self._enable()

    def set_selection(self, indices: list[int]) -> None:
        self._count = len(indices)
        self._enable()

    def set_growing(self, axis: str | None) -> None:
        """Achse, in der das Etikett mitwächst (``layout.growing_axis``): dort ist das
        Ausrichten am Papier gesperrt."""
        if axis != self._grow:
            self._grow = axis
            self._enable()

    def _enable(self) -> None:
        for key, button in self.buttons.items():
            target = button.defaultAction() or button
            blocked = _PAPER_AXIS.get(key) == self._grow and self._grow is not None
            target.setEnabled(self._count >= MIN_SELECTED[key] and not blocked)
            if key in _PAPER_AXIS and button.defaultAction() is not None:
                name = target.toolTip().split("\n")[0]
                target.setToolTip(f"{name}\n{GROWING_HINT}" if blocked else name)

    def set_icon_style(self, dark_checked: bool) -> None:
        self._dark = dark_checked
        for key, button in self.buttons.items():
            target = button.defaultAction() or button
            target.setIcon(line_icon(_ICONS[key], dark_checked, hover=True))
