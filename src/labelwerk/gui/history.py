"""Undo/redo via document snapshots (``copy.deepcopy``).

After every completed action the main window records the state with ``push``.
Changes that are not recorded yet (e.g. an ongoing edit in edit mode) are turned into a
step by ``undo`` itself beforehand.

Each state has the selection (indices) that last applied to it: after undo/redo
``selection`` shows it, so the selection lies on the same objects – even if the order
has changed.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from typing import Hashable

from PySide6.QtCore import QObject, Signal

from ..document import Document

LIMIT = 100   # at most this many steps back


@dataclass
class _State:
    doc: Document
    selection: list[int] = field(default_factory=list)


class History(QObject):
    changed = Signal()   # undo/redo may now be (no longer) possible

    def __init__(self, doc: Document, limit: int = LIMIT):
        super().__init__()
        self.limit = limit
        self.reset(doc)

    def reset(self, doc: Document) -> None:
        """New baseline (e.g. new or opened label) – without steps."""
        self._states = [_State(copy.deepcopy(doc))]
        self._pos = 0
        self._merge: Hashable | None = None
        self.changed.emit()

    def current(self) -> Document:
        """Copy of the current state (without anything not yet recorded)."""
        return copy.deepcopy(self._states[self._pos].doc)

    @property
    def selection(self) -> list[int]:
        """Selection belonging to the current state (copy)."""
        return list(self._states[self._pos].selection)

    def select(self, current: Document, selection: list[int]) -> None:
        """Selection changed (not a step): applies to the current state – only if ``current``
        still matches it, otherwise it belongs to the next ``push``."""
        if current == self._states[self._pos].doc:
            self._states[self._pos].selection = list(selection)

    def push(self, doc: Document, merge: Hashable | None = None,
             selection: list[int] = ()) -> bool:
        """Record the state after an action; False if nothing has changed.

        ``selection`` is the selection for it – without a change to the document only it is
        taken over for the current state. Consecutive steps with the same ``merge``
        (e.g. arrow keys on the same selection) are combined into one step;
        if the run leads back to the previous state, the step is dropped.
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
            del self._states[self._pos + 1:]        # redo is discarded
            self._states.append(state)
            del self._states[:-(self.limit + 1)]
            self._pos = len(self._states) - 1
        self._merge = merge
        self.changed.emit()
        return True

    def is_current(self, doc: Document) -> bool:
        """``doc`` matches the current state (nothing not yet recorded)."""
        return not self._pending(doc)

    def amend(self, doc: Document, selection: list[int] = ()) -> None:
        """Replace the current state without a step of its own (e.g. an empty text frame is dropped).

        If it then equals the previous state, the step that produced it is dropped."""
        self._states[self._pos] = _State(copy.deepcopy(doc), list(selection))
        if not self._drop_if_unchanged():
            self._merge = None
            self.changed.emit()

    def _drop_if_unchanged(self) -> bool:
        """Discard the current state if it equals the previous one (its selection then applies
        there); a run with ``merge`` starts afresh afterwards."""
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
        """State before the last step (copy) or None; ``current`` = document now,
        ``selection`` = selection now. The selection of the new state is in ``selection``."""
        self.push(current, selection=selection)
        if self._pos == 0:
            return None
        return self._step(-1)

    def redo(self, current: Document, selection: list[int] = ()) -> Document | None:
        """Redo an undone step (copy) or None.

        If ``current`` has changed since, that is a new step – nothing left to
        redo."""
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
    """Set ``target`` to the state of ``snapshot`` in place.

    Panels hold on to the document object; it is therefore not replaced."""

    for f in fields(Document):
        setattr(target, f.name, copy.deepcopy(getattr(snapshot, f.name)))
