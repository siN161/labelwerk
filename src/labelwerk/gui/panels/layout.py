"""LAYOUT panel: align selected objects, match size, rotate, order – like P-touch.

The buttons trigger the main window's actions (shortcut directory, shortcut in the tooltip);
the computing happens in the core (``layout``). Without a suitable selection the buttons are disabled.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QToolButton

from ...document import Document
from ...i18n import N_, _
from ..symbols import SIZE, line_icon
from . import Panel

# areas with buttons: (action, symbol)
LAYOUT_SECTIONS = (
    (N_("Align selected objects"), tuple((f"align.{mode}", f"align-objects-{mode}") for mode in
                                          ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
    (N_("Align to paper"), tuple((f"align.paper_{mode}", f"align-paper-{mode}") for mode in
                                   ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
    (N_("Resize"), (("size.maximize", "size-maximize"), ("size.same", "size-same"),
                                ("size.width", "size-width"), ("size.height", "size-height"))),
    (N_("Rotate"), (("object.rotate_left", "rotate-left"), ("object.rotate_right", "rotate-right"))),
    (N_("Order"), (("object.bring_forward", "order-forward"),
                     ("object.send_backward", "order-backward"))),
)
_ICONS = {key: icon for __, row in LAYOUT_SECTIONS for key, icon in row}
# aligning to each other and matching sizes need at least two objects, everything else one
_FROM_TWO = {key for key, __ in LAYOUT_SECTIONS[0][1]} | {"size.same", "size.width", "size.height"}
MIN_SELECTED = {key: 2 if key in _FROM_TWO else 1 for key in _ICONS}
# aligning to the paper in tape direction: per axis of the reading direction the label grows in
_PAPER_AXIS = {f"align.paper_{mode}": axis for axis, modes in
               (("x", ("left", "hcenter", "right")), ("y", ("top", "vcenter", "bottom")))
               for mode in modes}
GROWING_HINT = N_("With automatic length the label grows along – "
                  "the object keeps the same margin at both ends")
COLOR_TITLES = (("black", N_("BLACK")), ("red", N_("RED")))
NO_RED = N_("Red only on the 62 mm red/black label (DK-22251) with a QL-8xx")


class LayoutPanel(Panel):
    color_chosen = Signal(str)          # colour for the selection ("black" | "red")

    def __init__(self, doc: Document):
        super().__init__(doc, _("Layout"))
        self._dark = True
        self._count = 0
        self._red = False               # label can do red
        self._grow: str | None = None
        self.buttons: dict[str, QToolButton] = {}
        for title, row in LAYOUT_SECTIONS:
            # long headings wrap at spaces; not without spaces, otherwise
            # Qt reserves a second line at "/"
            title = _(title)
            self.section(title).setWordWrap(" " in title)
            line = QHBoxLayout()
            line.setSpacing(4)
            for key, __ in row:
                button = QToolButton()
                button.setObjectName("layoutButton")
                button.setAutoRaise(True)              # symbol on hover: mode "Active"
                button.setIconSize(SIZE)
                button.setEnabled(False)
                self.buttons[key] = button
                line.addWidget(button)
            line.addStretch()
            self.layout_.addLayout(line)
        self.section(_("Color"))
        line = QHBoxLayout()
        self.colors: dict[str, QPushButton] = {}
        for color, title in COLOR_TITLES:
            button = QPushButton(_(title))
            button.clicked.connect(lambda _checked=False, c=color: self.color_chosen.emit(c))
            self.colors[color] = button
            line.addWidget(button)
        self.layout_.addLayout(line)
        self.layout_.addStretch()
        self._enable()

    def use_actions(self, actions: dict[str, QAction]) -> None:
        for key, button in self.buttons.items():
            button.setDefaultAction(actions[key])
        self.set_icon_style(self._dark)
        self._enable()

    def set_selection(self, indices: list[int]) -> None:
        self._count = len(indices)
        self._enable()

    def set_red_available(self, available: bool) -> None:
        """Can the label do red (62red on a two-colour model)? Otherwise the colours are disabled."""
        if available != self._red:
            self._red = available
            self._enable()

    def set_growing(self, axis: str | None) -> None:
        """Axis in which the label grows along (``layout.growing_axis``): there the
        object sits at the start of the margin when aligned to the paper (hint in the tooltip)."""
        if axis != self._grow:
            self._grow = axis
            self._enable()

    def _enable(self) -> None:
        for color, button in self.colors.items():          # black always works (back)
            button.setEnabled(self._count > 0 and (self._red or color == "black"))
            button.setToolTip("" if self._red or color == "black" else _(NO_RED))
        for key, button in self.buttons.items():
            target = button.defaultAction() or button
            growing = _PAPER_AXIS.get(key) == self._grow and self._grow is not None
            target.setEnabled(self._count >= MIN_SELECTED[key])
            if key in _PAPER_AXIS and button.defaultAction() is not None:
                name = target.toolTip().split("\n")[0]
                target.setToolTip(f"{name}\n{_(GROWING_HINT)}" if growing else name)

    def set_icon_style(self, dark_checked: bool) -> None:
        self._dark = dark_checked
        for key, button in self.buttons.items():
            target = button.defaultAction() or button
            target.setIcon(line_icon(_ICONS[key], dark_checked, hover=True))
