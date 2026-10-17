"""Rückgängig/Wiederherstellen über Dokument-Schnappschüsse (``copy.deepcopy``).

Nach jeder abgeschlossenen Aktion hält das Hauptfenster den Stand mit ``push`` fest.
Änderungen, die noch nicht festgehalten sind (z. B. Tippen im Textfeld, das erst beim
Verlassen des Felds ein Schritt wird), macht ``undo`` vorher selbst zu einem Schritt.
"""
from __future__ import annotations

import copy
from dataclasses import fields
from typing import Hashable

from PySide6.QtCore import QObject, Signal

from ..document import Document

LIMIT = 100   # höchstens so viele Schritte zurück


class History(QObject):
    changed = Signal()   # Rückgängig/Wiederherstellen ggf. jetzt (nicht mehr) möglich

    def __init__(self, doc: Document, limit: int = LIMIT):
        super().__init__()
        self.limit = limit
        self.reset(doc)

    def reset(self, doc: Document) -> None:
        """Neuer Ausgangsstand (z. B. neues oder geöffnetes Etikett) – ohne Schritte."""
        self._states = [copy.deepcopy(doc)]
        self._pos = 0
        self._merge: Hashable | None = None
        self.changed.emit()

    def push(self, doc: Document, merge: Hashable | None = None) -> bool:
        """Stand nach einer Aktion festhalten; False, wenn sich nichts geändert hat.

        Aufeinanderfolgende Schritte mit gleichem ``merge`` (z. B. Pfeiltasten auf dieselbe
        Auswahl) werden zu einem Schritt zusammengefasst.
        """
        if doc == self._states[self._pos]:
            return False
        snapshot = copy.deepcopy(doc)
        if (merge is not None and merge == self._merge and self._pos > 0
                and self._pos == len(self._states) - 1):
            self._states[self._pos] = snapshot
        else:
            del self._states[self._pos + 1:]        # Wiederherstellen verfällt
            self._states.append(snapshot)
            del self._states[:-(self.limit + 1)]
            self._pos = len(self._states) - 1
        self._merge = merge
        self.changed.emit()
        return True

    def can_undo(self, current: Document | None = None) -> bool:
        return self._pos > 0 or self._pending(current)

    def can_redo(self, current: Document | None = None) -> bool:
        return self._pos < len(self._states) - 1 and not self._pending(current)

    def undo(self, current: Document) -> Document | None:
        """Stand vor dem letzten Schritt (Kopie) oder None; ``current`` = Dokument jetzt."""
        self.push(current)
        if self._pos == 0:
            return None
        return self._step(-1)

    def redo(self, current: Document) -> Document | None:
        """Rückgängig gemachten Schritt wiederholen (Kopie) oder None.

        Hat sich ``current`` seitdem geändert, ist das ein neuer Schritt – nichts mehr zu
        wiederholen."""
        self.push(current)
        if self._pos == len(self._states) - 1:
            return None
        return self._step(+1)

    def _step(self, direction: int) -> Document:
        self._pos += direction
        self._merge = None
        self.changed.emit()
        return copy.deepcopy(self._states[self._pos])

    def _pending(self, current: Document | None) -> bool:
        return current is not None and current != self._states[self._pos]


def restore(target: Document, snapshot: Document) -> None:
    """``target`` an Ort und Stelle auf den Stand von ``snapshot`` setzen.

    Panels halten das Dokument-Objekt fest; es wird deshalb nicht ersetzt."""
    for f in fields(Document):
        setattr(target, f.name, copy.deepcopy(getattr(snapshot, f.name)))
