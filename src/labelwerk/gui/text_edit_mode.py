"""Edit mode: write and select text directly in the frame on the label.

The text panel's editor is kept as an invisible input buffer and has the keyboard focus in
edit mode; the canvas keeps showing the real object image from the core. Caret, selection and
mouse clicks are converted by ``TextEditSession`` via the line layout of the same render
(``RenderedObject.layout``) – preview = print also holds while typing. Positions: editor in
UTF-16 units, line layout in characters (``render.to_utf16``/``from_utf16``).

In edit mode the editor's keys apply (arrows, Home/End, Del, Ctrl+A/C/X/V/Z …);
Up/Down follow the lines on the label, Tab has no effect (labelwerk does not print tabs, and
the focus should not leave the text). Ctrl+Z and Ctrl+Shift+Z carry on in the document like
the buttons when the editor has nothing left to undo or redo. A frame without a fixed size
grows at the edge of its text position (``layout.anchor_after_edit``). Start and end including
the undo step (one edit = one step) are controlled by the main window (``MainWindow.edit_text``,
``finish_editing``); in edit mode undo, clipboard and the enabling of their buttons are
passed on to the session (``undo``, ``copy`` … ``update_actions``).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QTextCursor, QTextDocument
from PySide6.QtWidgets import QAbstractButton, QApplication

from .. import layout
from ..render import RenderedObject, TextLayout, from_utf16, to_utf16

_VERTICAL = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}
_TABS = (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)


class TextEditSession(QObject):
    """Edit mode for at most one text object (``index``) of the main window."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._canvas = window.canvas
        self._panel = window.panel("text")
        self._editor = self._panel.edit
        self.index: int | None = None
        self._goal: tuple[float, int] | None = None   # Up/Down: target x and position afterwards
        self._quiet = False                       # display only once the object is in place
        self._canvas.edit_pressed.connect(self._press)
        self._canvas.edit_dragged.connect(self._drag)
        self._canvas.edit_double_clicked.connect(self._select_word)
        for signal in (self._editor.cursorPositionChanged, self._editor.selectionChanged):
            signal.connect(self.update_marks)
        # after a panel button or when the list of “Font”/size closes or Enter is pressed
        # there, keep typing at the caret – arrow keys in the field stay there
        self._panel.formatted.connect(self._return_focus_from_button)
        self._popups = []
        for combo in (self._panel.family, self._panel.size):
            popup = combo.view().window()
            popup.installEventFilter(self)
            self._popups.append(popup)
            if combo.lineEdit() is not None:
                combo.lineEdit().returnPressed.connect(self._return_focus)
        QApplication.instance().focusChanged.connect(self._focus_changed)
        self._editor.installEventFilter(self)

    @property
    def active(self) -> bool:
        return self.index is not None

    # --- Start / End -------------------------------------------------------
    def start(self, index: int, point: QPointF | None = None) -> None:
        """Edit mode for object ``index`` (selected, in the text panel): editor rebuilt from the
        model, keyboard focus into it, caret at ``point`` (dots in reading direction,
        e.g. double-click) or at the end of the text."""
        self._panel.refresh()                      # editor = model, own undo from here on
        self.index = index
        self._goal = None
        self._panel.set_editing(True)
        self._editor.caret_rect = self._caret_rect
        self._canvas.set_editing(index)
        self._canvas.setFocusProxy(self._editor)   # click on the canvas: focus stays in the editor
        self._editor.setFocus()
        cursor = self._editor.textCursor()
        position = self._position_at(point) if point is not None else None
        if position is None:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        else:
            cursor.setPosition(position)
        self._editor.setTextCursor(cursor)
        self._canvas.set_caret_focus(self._editor.hasFocus())
        self.update_marks()

    def end(self) -> int | None:
        """End edit mode (selection is dropped, object shortcuts apply again); returns
        the index of the edited object."""
        index, self.index = self.index, None
        if index is None:
            return None
        cursor = self._editor.textCursor()
        cursor.clearSelection()                    # formatting applies to the whole frame again
        self._editor.setTextCursor(cursor)
        self._panel.set_editing(False)
        self._editor.caret_rect = None
        self._canvas.set_editing(None)
        self._canvas.setFocusProxy(None)
        if self._editor.hasFocus():
            self._canvas.setFocus()
        return index

    def content_changed(self) -> None:
        """Text or format changed: render immediately so caret and image belong to the same
        line layout. A frame with a position and without a fixed size grows at the edge of
        its text position (the top edge of the first line stays); without a position the
        text stays centred, a fixed frame size fits it in as before."""
        if not self.active:
            return
        window, index = self._window, self.index
        obj = window.doc.objects[index]
        anchored = obj.positioned and not obj.fit and index < len(window.rendered)
        old = window.rendered[index] if anchored else None   # as last displayed
        self._quiet = True
        try:
            window.render_now()                        # new text, still at the old position
            new = window.rendered[index] if index < len(window.rendered) else None
            if (old is not None and new is not None and new is not old
                    and old.layout is not None and new.layout is not None):
                position = layout.anchor_after_edit(obj, old, new)
                if position != (obj.x_mm, obj.y_mm):
                    obj.x_mm, obj.y_mm = position
                    window.render_now()
                    # the line layout does not depend on the position (relative to the frame): keep
                    # using the character boundaries already measured instead of measuring again
                    window.rendered[index].layout = new.layout
        finally:
            self._quiet = False
        self.update_marks()

    # --- Commands (buttons, shortcuts) --------------------------------------------
    # Return value True = handled in edit mode; False = the main window runs the command
    # on the document or the selection.
    def undo(self) -> bool:
        """Undo in the editor; if there is nothing left to undo there, edit mode ends and
        the document carries on (False). An empty new frame is dropped – that is then the
        whole step. If the document has nothing either: keep writing."""
        if not self.active:
            return False
        if self._editor.document().isUndoAvailable():
            self._editor.undo()
            return True
        window = self._window
        obj = window.doc.objects[self.index]
        if obj.positioned and obj.is_empty():
            selection = window.history.selection    # selection before creating
            window.finish_editing()
            self._canvas.set_selection(selection)
            return True
        if not window.history.can_undo(window.doc):
            return True                             # nothing to undo: keep writing
        window.finish_editing()
        return False

    def redo(self) -> bool:
        """Redo in the editor; if it has nothing left, edit mode ends and the document
        carries on (False) – as with ``undo``."""
        if not self.active:
            return False
        if self._editor.document().isRedoAvailable():
            self._editor.redo()
            return True
        window = self._window
        if not window.history.can_redo(window.doc):
            return True                             # nothing to redo: keep writing
        window.finish_editing()
        return False

    def copy(self) -> bool:
        """Copy the selected text to the system clipboard."""
        active = self.active          # note it first: if the session ends in the process, it still applies
        if active:
            self._editor.copy()
        return active

    def cut(self) -> bool:
        """Cut the selected text (system clipboard)."""
        active = self.active          # note it first: if the session ends in the process, it still applies
        if active:
            self._editor.cut()
        return active

    def paste(self) -> bool:
        """Paste text from the system clipboard (as plain text)."""
        active = self.active          # note it first: if the session ends in the process, it still applies
        if active:
            self._editor.paste()
        return active

    def update_actions(self, actions: dict) -> bool:
        """In edit mode the buttons act on the text in the editor: set the enabling of the
        actions (``gui.actions``) accordingly; undo/redo also when only the document
        has something."""
        if not self.active:
            return False
        editor, window = self._editor, self._window
        marked = editor.textCursor().hasSelection()
        enabled = {"edit.cut": marked, "edit.copy": marked, "edit.paste": editor.canPaste(),
                   "edit.duplicate": False, "edit.delete": False,
                   "edit.undo": (editor.document().isUndoAvailable()
                                 or window.history.can_undo(window.doc)),
                   "edit.redo": (editor.document().isRedoAvailable()
                                 or window.history.can_redo(window.doc)),
                   "text.end_edit": True, "text.start_edit": False,
                   "text.start_edit_enter": False}
        for key, value in enabled.items():
            actions[key].setEnabled(value)
        return True

    # --- Display ------------------------------------------------------------
    def update_marks(self) -> None:
        """Pass caret, selection and frame from the editor and the current line layout to the
        canvas. If the line layout does not (yet) match the editor – rendering follows
        soon or has failed – the previous display stays."""
        if self._quiet:
            return
        current = self._current()
        if current is None:
            return
        rendered, text_layout, text, rotation = current
        cursor = self._editor.textCursor()
        pos = from_utf16(text, cursor.position())
        anchor = from_utf16(text, cursor.anchor())
        x, top, height = text_layout.caret(pos)
        scale = self._panel.typing_scale()
        if abs(scale - 1) > 1e-6:                     # continued typing at another size (A⁺ …)
            baseline = next(line.baseline for line in text_layout.lines
                            if line.start <= pos <= line.end)
            top, height = baseline - (baseline - top) * scale, height * scale
        caret = QLineF(_label(rendered, rotation, x, top),
                       _label(rendered, rotation, x, top + height))
        frame = self._frame(rendered, text_layout, rotation, x, top, height)
        # a selected paragraph break at the end of the widest line ends at the frame
        marked = ([_label_rect(rendered, rotation, *rect).intersected(frame)
                   for rect in text_layout.selection_rects(anchor, pos)] if anchor != pos else [])
        self._canvas.set_edit_marks(frame, caret, marked)
        if self._editor.hasFocus():
            QGuiApplication.inputMethod().update(Qt.InputMethodQuery.ImCursorRectangle)

    def _caret_rect(self) -> QRect:
        """Caret on the canvas in coordinates of the (invisible) editor."""
        line = self._canvas.caret_line()
        rect = QRectF(line.p1(), line.p2()).normalized()
        top_left = self._editor.mapFromGlobal(
            self._canvas.viewport().mapToGlobal(rect.topLeft().toPoint()))
        return QRect(top_left.x(), top_left.y(), max(1, round(rect.width())),
                     max(1, round(rect.height())))

    def _frame(self, rendered: RenderedObject, text_layout: TextLayout, rotation: int,
               x: float, top: float, height: float) -> QRectF:
        """Frame in edit mode: ink box of the object including the lines from ascender to
        descender, so caret and selection lie inside. An empty text gets a placeholder
        (half a line wide) around the caret – to the right, centred or to the left of it,
        depending on the text position."""
        if rendered.w and rendered.h:
            lines = text_layout.lines
            left = min(line.stops[0] for line in lines)
            right = max(line.stops[-1] for line in lines)
            bottom = max(line.top + line.height for line in lines)
            box = _label_rect(rendered, rotation, left, lines[0].top, right - left,
                              bottom - lines[0].top)
            return box.united(QRectF(rendered.x, rendered.y, rendered.w, rendered.h))
        width = rendered.base_pt * rendered.dpi / 72 / 2
        obj = self._window.doc.objects[self.index]
        align = obj.paragraphs[0].align if obj.paragraphs else "left"
        left = x - {"center": width / 2, "right": width}.get(align, 0.0)
        return _label_rect(rendered, rotation, left, top, width, height)

    def _current(self) -> tuple[RenderedObject, TextLayout, str, int] | None:
        """Rendered object, its line layout, editor text and rotation – only if the
        line layout matches the text in the editor."""
        window, index = self._window, self.index
        if index is None or not 0 <= index < min(len(window.rendered), len(window.doc.objects)):
            return None
        rendered = window.rendered[index]
        text = editor_text(self._editor.document())
        if rendered.layout is None or "\n".join(rendered.layout.texts) != text:
            return None
        return rendered, rendered.layout, text, window.doc.objects[index].rotation

    # --- Mouse and keyboard ----------------------------------------------------
    def _position_at(self, point: QPointF) -> int | None:
        """Editor position (UTF-16) of the character boundary at the point (dots in reading direction)."""
        current = self._current()
        if current is None:
            return None
        rendered, text_layout, text, rotation = current
        u, v = layout.to_object((point.x(), point.y()), rendered, rotation)
        return to_utf16(text, text_layout.hit(u, v))

    def _press(self, point: QPointF, extend: bool) -> None:
        """Click in the frame: caret there (with Shift: selection up to there)."""
        self._move_to(self._position_at(point), extend)
        self._editor.setFocus()

    def _drag(self, point: QPointF) -> None:
        """Dragging in the frame selects from the click point to here."""
        self._move_to(self._position_at(point), extend=True)

    def _select_word(self, point: QPointF) -> None:
        """Double-click in edit mode selects the word at the point."""
        position = self._position_at(point)
        if position is None:
            return
        cursor = self._editor.textCursor()
        cursor.setPosition(position)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        self._editor.setTextCursor(cursor)

    def _move_to(self, position: int | None, extend: bool) -> None:
        if position is None:
            return
        cursor = self._editor.textCursor()
        mode = QTextCursor.MoveMode.KeepAnchor if extend else QTextCursor.MoveMode.MoveAnchor
        cursor.setPosition(position, mode)
        self._editor.setTextCursor(cursor)

    def _vertical(self, step: int, extend: bool) -> None:
        """Up/Down: to the line above/below, as close as possible to the same place on the
        label (the editor does not know the label's lines). Above the first or below the
        last line it goes to the start or the end."""
        current = self._current()
        if current is None:
            return
        _, text_layout, text, _ = current
        position = self._editor.textCursor().position()
        pos = from_utf16(text, position)
        lines = text_layout.lines
        row = next(i for i, line in enumerate(lines) if line.start <= pos <= line.end)
        # several Up/Down in a row: keep the column from the start of the sequence
        x = (self._goal[0] if self._goal is not None and self._goal[1] == position
             else text_layout.caret(pos)[0])
        if 0 <= row + step < len(lines):
            line = lines[row + step]
            target = text_layout.hit(x, line.top + line.height / 2)
        else:
            target = 0 if step < 0 else lines[-1].end
        self._move_to(to_utf16(text, target), extend)
        self._goal = (x, self._editor.textCursor().position())

    def _return_focus(self) -> None:
        """After formatting in the panel, keep typing at the caret."""
        if self.active:
            self._editor.setFocus()

    def _return_focus_from_button(self) -> None:
        """A panel button has formatted (the click took its focus): back to the text.
        Fields with keyboard operation (font, size) keep it."""
        if isinstance(QApplication.focusWidget(), QAbstractButton):
            self._return_focus()

    def _focus_changed(self, _old, new) -> None:
        if self.active:
            self._canvas.set_caret_focus(new is self._editor)

    def eventFilter(self, watched, event) -> bool:
        if watched in self._popups and event.type() == QEvent.Type.Hide:
            QTimer.singleShot(0, self._return_focus)   # after Qt has given the focus back
        elif (self.active and watched is self._editor
              and event.type() == QEvent.Type.KeyPress):
            if event.key() in _TABS:
                return True                             # Tab: no effect, focus stays
            if (event.matches(QKeySequence.StandardKey.Undo)
                    and not self._editor.document().isUndoAvailable()):
                self._window.undo()                     # like the button: carry on in the document
                return True
            if (event.matches(QKeySequence.StandardKey.Redo)
                    and not self._editor.document().isRedoAvailable()):
                self._window.redo()                     # likewise redo
                return True
            if (event.key() in _VERTICAL
                    and not event.modifiers() & ~Qt.KeyboardModifier.ShiftModifier):
                self._vertical(_VERTICAL[event.key()],
                               bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                return True
        return super().eventFilter(watched, event)


def editor_text(document: QTextDocument) -> str:
    """Editor text as the model receives it (``TextPanel.to_text_object``): paragraphs
    with "\\n", line separator U+2028 as a paragraph, tab as a space – one character each, so
    the positions stay the same."""
    lines = []
    block = document.begin()
    while block.isValid():
        lines.append(block.text().replace("\t", " ").replace("\u2028", "\n"))
        block = block.next()
    return "\n".join(lines)


def _label(rendered: RenderedObject, rotation: int, u: float, v: float) -> QPointF:
    """Object coordinates (unrotated) → point on the label (dots in reading direction)."""
    return QPointF(*layout.from_object((u, v), rendered, rotation))


def _label_rect(rendered: RenderedObject, rotation: int, u: float, v: float, w: float,
                h: float) -> QRectF:
    """Rectangle in object coordinates → rectangle on the label (rotation in 90° steps)."""

    return QRectF(_label(rendered, rotation, u, v),
                  _label(rendered, rotation, u + w, v + h)).normalized()
