"""Own line symbols (``gui/icons/<name>-black.svg`` / ``-white.svg``, 16 × 16).

Black in the normal state; in the BlackWerk design white where the button has a black background
(selected or on hover). In the System design the button stays light, hence black.
"""
from __future__ import annotations

from importlib import resources

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

SIZE = QSize(16, 16)


def line_icon(name: str, dark: bool = True, hover: bool = False) -> QIcon:
    """Symbol ``name``; ``dark``: selected white on black (BlackWerk).

    ``hover``: also white on hover – for buttons that then turn black and use the
    “Active” mode only on hover (QToolButton with autoRaise, toolbars).

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
