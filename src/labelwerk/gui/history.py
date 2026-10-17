"""Rückgängig/Wiederherstellen über Dokument-Schnappschüsse (``copy.deepcopy``).

Nach jeder abgeschlossenen Aktion hält das Hauptfenster den Stand mit ``push`` fest.
Änderungen, die noch nicht festgehalten sind (z. B. eine laufende Bearbeitung im
Schreibmodus), macht ``undo`` vorher selbst zu einem Schritt.

Zu jedem Stand gehört die Auswahl (Indizes), die zuletzt dazu galt: Nach Rückgängig/
Wiederherstellen zeigt ``selection`` sie, damit die Auswahl auf denselben Objekten liegt –
auch wenn sich die Reihenfolge geändert hat.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from typing import Hashable

from PySide6.QtCore import QObject, Signal

from ..document import Document

LIMIT = 100   # höchstens so viele Schritte zurück


@dataclass
class _State:
    doc: Document
    selection: list[int] = field(default_factory=list)


class History(QObject):
    changed = Signal()   # Rückgängig/Wiederherstellen ggf. jetzt (nicht mehr) möglich

    def __init__(self, doc: Document, limit: int = LIMIT):
        super().__init__()
        self.limit = limit
        self.reset(doc)

    def reset(self, doc: Document) -> None:
        """Neuer Ausgangsstand (z. B. neues oder geöffnetes Etikett) – ohne Schritte."""
        self._states = [_State(copy.deepcopy(doc))]
        self._pos = 0
        self._merge: Hashable | None = None
        self.changed.emit()

    def current(self) -> Document:
        """Kopie des aktuellen Stands (ohne noch nicht Festgehaltenes)."""
        return copy.deepcopy(self._states[self._pos].doc)

    @property
    def selection(self) -> list[int]:
        """Auswahl, die zum aktuellen Stand gehört (Kopie)."""
        return list(self._states[self._pos].selection)

    def select(self, current: Document, selection: list[int]) -> None:
        """Auswahl geändert (kein Schritt): gilt für den aktuellen Stand – nur wenn ``current``
        ihm noch entspricht, sonst gehört sie zum nächsten ``push``."""
        if current == self._states[self._pos].doc:
            self._states[self._pos].selection = list(selection)

    def push(self, doc: Document, merge: Hashable | None = None,
             selection: list[int] = ()) -> bool:
        """Stand nach einer Aktion festhalten; False, wenn sich nichts geändert hat.

        ``selection`` ist die Auswahl dazu – ohne Änderung am Dokument wird nur sie für den
        aktuellen Stand übernommen. Aufeinanderfolgende Schritte mit gleichem ``merge``
        (z. B. Pfeiltasten auf dieselbe Auswahl) werden zu einem Schritt zusammengefasst;
        führt die Serie zurück zum Stand davor, entfällt der Schritt.
        """
        state = _State(self._states[self._pos].doc, list(selection))
        if doc == state.doc:
            self._states[self._pos] = state
            return False
        state.doc = copy.deepcopy(doc)
        if (merge is not None and merge == self._merge and self._pos > 0
                and self._pos == len(self._states) - 1):
            self._states[self._pos] = state
            if self._drop_if_unchanged():
                return True
        else:
            del self._states[self._pos + 1:]        # Wiederherstellen verfällt
            self._states.append(state)
            del self._states[:-(self.limit + 1)]
            self._pos = len(self._states) - 1
        self._merge = merge
        self.changed.emit()
        return True

    def is_current(self, doc: Document) -> bool:
        """``doc`` entspricht dem aktuellen Stand (nichts noch nicht Festgehaltenes)."""
        return not self._pending(doc)

    def amend(self, doc: Document, selection: list[int] = ()) -> None:
        """Aktuellen Stand ohne eigenen Schritt ersetzen (z. B. ein leerer Textrahmen entfällt).

        Gleicht er danach dem Stand davor, entfällt der Schritt, der ihn erzeugt hat."""
        self._states[self._pos] = _State(copy.deepcopy(doc), list(selection))
        if not self._drop_if_unchanged():
            self._merge = None
            self.changed.emit()

    def _drop_if_unchanged(self) -> bool:
        """Aktuellen Stand verwerfen, wenn er dem vorigen gleicht (seine Auswahl gilt dann
        dort); eine Serie mit ``merge`` beginnt danach neu."""
        if self._pos == 0 or self._states[self._pos].doc != self._states[self._pos - 1].doc:
            return False
        self._states[self._pos - 1].selection = self._states[self._pos].selection
        del self._states[self._pos]
        self._pos -= 1
        self._merge = None
        self.changed.emit()
        return True

    def can_undo(self, current: Document | None = None) -> bool:
        return self._pos > 0 or self._pending(current)

    def can_redo(self, current: Document | None = None) -> bool:
        return self._pos < len(self._states) - 1 and not self._pending(current)

    def undo(self, current: Document, selection: list[int] = ()) -> Document | None:
        """Stand vor dem letzten Schritt (Kopie) oder None; ``current`` = Dokument jetzt,
        ``selection`` = Auswahl jetzt. Die Auswahl des neuen Stands steht in ``selection``."""
        self.push(current, selection=selection)
        if self._pos == 0:
            return None
        return self._step(-1)

    def redo(self, current: Document, selection: list[int] = ()) -> Document | None:
        """Rückgängig gemachten Schritt wiederholen (Kopie) oder None.

        Hat sich ``current`` seitdem geändert, ist das ein neuer Schritt – nichts mehr zu
        wiederholen."""
        self.push(current, selection=selection)
        if self._pos == len(self._states) - 1:
            return None
        return self._step(+1)

    def _step(self, direction: int) -> Document:
        self._pos += direction
        self._merge = None
        self.changed.emit()
        return copy.deepcopy(self._states[self._pos].doc)

    def _pending(self, current: Document | None) -> bool:
        return current is not None and current != self._states[self._pos].doc


def restore(target: Document, snapshot: Document) -> None:
    """``target`` an Ort und Stelle auf den Stand von ``snapshot`` setzen.

    Panels halten das Dokument-Objekt fest; es wird deshalb nicht ersetzt."""
    for f in fields(Document):
        setattr(target, f.name, copy.deepcopy(getattr(snapshot, f.name)))
