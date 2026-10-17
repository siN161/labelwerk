"""Eigene Liniensymbole (``gui/icons/<name>-black.svg`` / ``-white.svg``, 16 × 16).

Schwarz im Normalzustand; im Design RawBlock weiß, wo der Knopf schwarz hinterlegt ist
(gewählt bzw. beim Darüberfahren). Im klassischen Design bleibt der Knopf hell, also schwarz.
"""
from __future__ import annotations

from importlib import resources

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

SIZE = QSize(16, 16)


def line_icon(name: str, dark: bool = True, hover: bool = False) -> QIcon:
    """Symbol ``name``; ``dark``: gewählt weiß auf schwarz (RawBlock).

    ``hover``: auch beim Darüberfahren weiß – für Knöpfe, die dann schwarz werden und den
    Modus „Active“ nur beim Darüberfahren nutzen (QToolButton mit autoRaise, Werkzeugleisten).
    """
    folder = resources.files("labelwerk.gui") / "icons"

    def path(color: str) -> str:
        return str(folder / f"{name}-{color}.svg")
    light = "white" if dark else "black"
    icon = QIcon()
    icon.addFile(path("black"), QSize(), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addFile(path(light), QSize(), QIcon.Mode.Normal, QIcon.State.On)
    if hover:
        icon.addFile(path(light), QSize(), QIcon.Mode.Active, QIcon.State.Off)
        icon.addFile(path(light), QSize(), QIcon.Mode.Active, QIcon.State.On)
    return icon
