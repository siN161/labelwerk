"""QActions from the shortcut directory (``shortcuts.ACTIONS``): one per action, shortcut changeable.

Whoever uses an action connects ``triggered`` and attaches it to the matching widget
(global ones to the main window, "canvas" to the canvas, "edit" to the text panel that holds
the editor of the edit mode).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QKeySequence

from .. import shortcuts
from ..i18n import _

_CONTEXT = {
    "global": Qt.ShortcutContext.WindowShortcut,
    "canvas": Qt.ShortcutContext.WidgetWithChildrenShortcut,
    "edit": Qt.ShortcutContext.WidgetWithChildrenShortcut,
}


def build_actions(parent: QObject, mapping: dict[str, str]) -> dict[str, QAction]:
    """One QAction per action of the directory, with name, scope and shortcut from ``mapping``."""
    actions = {}
    for entry in shortcuts.ACTIONS:
        action = QAction(_(entry.name), parent)
        action.setObjectName(entry.id)
        action.setShortcutContext(_CONTEXT[entry.scope])
        actions[entry.id] = action
    apply_shortcuts(actions, mapping)
    return actions


def apply_shortcuts(actions: dict[str, QAction], mapping: dict[str, str]) -> None:
    """Set the shortcuts (e.g. after saving the settings); the tooltip names the shortcut."""
    for action_id, action in actions.items():
        sequence = QKeySequence(mapping.get(action_id, ""))
        if sequence.toString() == "Return":           # Enter on the numeric keypad counts too
            action.setShortcuts([sequence, QKeySequence("Enter")])
        else:
            action.setShortcut(sequence)
        name = _(shortcuts.action(action_id).name)
        keys = sequence.toString(QKeySequence.SequenceFormat.NativeText)
        action.setToolTip(f"{name} ({keys})" if keys else name)
