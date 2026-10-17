"""QActions aus dem Kürzel-Verzeichnis (``shortcuts.ACTIONS``): eine je Aktion, Kürzel änderbar.

Wer eine Aktion nutzt, verbindet ``triggered`` und hängt sie an das passende Widget
(globale ans Hauptfenster, „canvas“ an die Arbeitsfläche, „text“ ans Textfeld).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QKeySequence

from .. import shortcuts

_CONTEXT = {
    "global": Qt.ShortcutContext.WindowShortcut,
    "canvas": Qt.ShortcutContext.WidgetWithChildrenShortcut,
    "text": Qt.ShortcutContext.WidgetWithChildrenShortcut,
}


def build_actions(parent: QObject, mapping: dict[str, str]) -> dict[str, QAction]:
    """Je Aktion des Verzeichnisses eine QAction mit Name, Bereich und Kürzel aus ``mapping``."""
    actions = {}
    for entry in shortcuts.ACTIONS:
        action = QAction(entry.name, parent)
        action.setObjectName(entry.id)
        action.setShortcutContext(_CONTEXT[entry.scope])
        actions[entry.id] = action
    apply_shortcuts(actions, mapping)
    return actions


def apply_shortcuts(actions: dict[str, QAction], mapping: dict[str, str]) -> None:
    """Kürzel (z. B. nach dem Speichern der Einstellungen) setzen; Tooltip nennt das Kürzel."""
    for action_id, action in actions.items():
        sequence = QKeySequence(mapping.get(action_id, ""))
        action.setShortcut(sequence)
        name = shortcuts.action(action_id).name
        keys = sequence.toString(QKeySequence.SequenceFormat.NativeText)
        action.setToolTip(f"{name} ({keys})" if keys else name)
