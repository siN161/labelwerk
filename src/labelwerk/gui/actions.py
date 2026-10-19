"""QActions aus dem Kürzel-Verzeichnis (``shortcuts.ACTIONS``): eine je Aktion, Kürzel änderbar.

Wer eine Aktion nutzt, verbindet ``triggered`` und hängt sie an das passende Widget
(globale ans Hauptfenster, „canvas“ an die Arbeitsfläche, „edit“ ans Text-Panel, in dem der
Editor des Schreibmodus steckt).
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
    """Je Aktion des Verzeichnisses eine QAction mit Name, Bereich und Kürzel aus ``mapping``."""
    actions = {}
    for entry in shortcuts.ACTIONS:
        action = QAction(_(entry.name), parent)
        action.setObjectName(entry.id)
        action.setShortcutContext(_CONTEXT[entry.scope])
        actions[entry.id] = action
    apply_shortcuts(actions, mapping)
    return actions


def apply_shortcuts(actions: dict[str, QAction], mapping: dict[str, str]) -> None:
    """Kürzel (z. B. nach dem Speichern der Einstellungen) setzen; Tooltip nennt das Kürzel."""
    for action_id, action in actions.items():
        sequence = QKeySequence(mapping.get(action_id, ""))
        if sequence.toString() == "Return":           # Enter auf dem Ziffernblock gilt mit
            action.setShortcuts([sequence, QKeySequence("Enter")])
        else:
            action.setShortcut(sequence)
        name = _(shortcuts.action(action_id).name)
        keys = sequence.toString(QKeySequence.SequenceFormat.NativeText)
        action.setToolTip(f"{name} ({keys})" if keys else name)
