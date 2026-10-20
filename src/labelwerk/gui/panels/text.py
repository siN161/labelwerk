"""Panel “Text”: edits the selected text frame – character by character as in the P-touch Editor.

Rule as with a selected text frame in P-touch: if nothing is selected, formatting applies to the
whole text; otherwise only to the selection. In edit mode it applies to further typing when
there is no selection (text position: to the paragraph of the caret) – unless the frame is
still empty. Area “Position” (``panels.position``): position and (with a fixed frame size)
size of the frame in mm.

Writing happens directly on the label (``gui.text_edit_mode``): the editor ``edit`` is
an invisible input buffer for that (child of the panel, size 0, not in the layout) – in edit
mode it keeps the keyboard focus so that dead keys, compose and input methods work.
"""
from __future__ import annotations

import math
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (QAction, QFont, QIcon, QTextCharFormat, QTextCursor, QTextFormat,
                           QTextOption)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit)

from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
from ...fonts import DEFAULT_FAMILY
from ... import fonts, i18n
from ...i18n import N_, _, pgettext
from ...layout import Rect
from ...render import REF_PT
from ..symbols import line_icon
from ..widgets import FontCombo
from . import Panel
from .position import PositionSection

_P = QTextFormat.Property

SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
DEFAULT_PT = 19
HINT = N_("Click on the label to create a text frame")
_ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}


class PlainPasteEdit(QTextEdit):
    """Rich-text editor that takes only plain text from the clipboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)      # never insert "\t" (in edit mode a filter
                                           # also catches it, focus stays in the text)
        # one line per paragraph as on the label: Home/End apply to the whole paragraph
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        # Edit mode: position of the caret on the label for input methods (→ QRect)
        self.caret_rect = None

    def inputMethodQuery(self, query):
        if query == Qt.InputMethodQuery.ImCursorRectangle and self.caret_rect is not None:
            return self.caret_rect()           # candidate window at the caret
        return super().inputMethodQuery(query)

    def keyPressEvent(self, event) -> None:
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.textCursor().insertBlock()   # Shift+Enter = normal paragraph, no U+2028
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:
        if source.hasText():
            self.textCursor().insertText(source.text())


def _button(text: str, tip: str, checkable: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setToolTip(tip)
    button.setCheckable(checkable)
    button.setObjectName("formatButton")
    return button


def _align_icon(key: str, dark_checked: bool = True) -> QIcon:
    """Line icon of the text position; when selected white on black only in BlackWerk."""
    return line_icon(f"align-{key}", dark_checked)


class TextPanel(Panel):
    frame_edited = Signal(str, float)   # field in the "Position" section ("x" | "y" | "w" | "h"), mm
    formatted = Signal()                # button/field has formatted (edit mode: focus back)

    def set_icon_style(self, dark_checked: bool) -> None:
        """Adapt alignment icons to the theme (white on black only in BlackWerk)."""
        self.dark_checked_icons = dark_checked
        for key, button in self.align_buttons.items():
            button.setIcon(_align_icon(key, dark_checked))

    def __init__(self, doc: Document):
        super().__init__(doc, _("Text"))
        self.dark_checked_icons = True
        self.index: int | None = None   # object being edited; None = no text selected
        self._editing = False           # edit mode (``set_editing``)
        self._frame: Rect | None = None   # last frame shown (mm)
        self._updating = False
        self._formatting = False        # during a formatting: do not apply contentsChanged twice
        self._shown_pt: float | None = float(DEFAULT_PT)   # last size shown; None = mixed
        # Base format: applies to everything not explicitly formatted (not Qt's widget font)
        self._base = {"family": DEFAULT_FAMILY, "pt": float(DEFAULT_PT), "bold": True,
                      "italic": False, "underline": False}

        self.hint = QLabel(_(HINT))
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.layout_.addWidget(self.hint)

        # invisible input buffer of edit mode: focusable but without area
        self.edit = PlainPasteEdit(self)
        self.edit.setFixedSize(0, 0)
        # only edit mode gives it the focus (setFocus) – never Tab or a click
        self.edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Paragraphs without their own alignment are centred – as before in labelwerk; no
        # wrapping in the editor (size 0), so that Home/End and lines match the paragraphs
        option = QTextOption(Qt.AlignmentFlag.AlignHCenter)
        option.setWrapMode(QTextOption.WrapMode.NoWrap)
        self.edit.document().setDefaultTextOption(option)

        self.section(pgettext("text panel", "Font"))
        self.family = FontCombo([])      # filled by MainWindow.apply_font_list (short or all)
        self.layout_.addWidget(self.family)
        row = QHBoxLayout()
        self.size = QComboBox()
        self.size.setEditable(True)
        self.size.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)   # do not append input to the list
        self.size.addItems([str(s) for s in SIZES_PT])
        self.size.setToolTip(_("Font size in pt"))
        self.grow = _button("A⁺", _("Larger font"), checkable=False)
        self.shrink = _button("A⁻", _("Smaller font"), checkable=False)
        row.addWidget(self.size, 1)
        row.addWidget(self.grow)
        row.addWidget(self.shrink)
        self.layout_.addLayout(row)

        self.section(_("Style"))
        row = QHBoxLayout()
        self.bold = _button("B", _("Bold"))            # tooltip with shortcut: use_actions
        self.italic = _button("I", _("Italic"))
        self.underline = _button("U", _("Underline"))
        for button, attr in ((self.bold, "bold"), (self.italic, "italic"),
                             (self.underline, "underline")):
            button.setProperty("style", attr)
            font = button.font()                 # also works in the System theme without a stylesheet
            getattr(font, "set" + attr.capitalize())(True)
            button.setFont(font)
            row.addWidget(button)
        self.layout_.addLayout(row)

        self.section(_("Text alignment"))
        row = QHBoxLayout()
        self.align_group = QButtonGroup(self)
        self.align_buttons = {}
        for key, tip in (("left", _("Align left")), ("center", _("Centered")),
                         ("right", _("Align right")), ("justify", _("Justified"))):
            button = _button("", tip)
            button.setIcon(_align_icon(key))
            button.setIconSize(QSize(16, 16))
            button.setAccessibleName(tip)
            self.align_group.addButton(button)
            self.align_buttons[key] = button
            row.addWidget(button)
        self.layout_.addLayout(row)

        self.fit = _button(_("FIXED FRAME SIZE"), _("Scale the text automatically so that it fits"))
        self.layout_.addWidget(self.fit)

        self.section(_("Position (mm)"))
        self.position = PositionSection()
        self.pos_x, self.pos_y, self.pos_w, self.pos_h = (self.position.spins[k] for k in "xywh")
        self.position.edited.connect(self._frame_changed)
        self.layout_.addWidget(self.position)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        self.layout_.addWidget(self.error)
        self.layout_.addStretch()

        self.refresh()
        self.edit.document().contentsChanged.connect(self._apply)
        self.edit.currentCharFormatChanged.connect(self._sync_buttons)
        self.edit.cursorPositionChanged.connect(self._sync_buttons)
        self.edit.selectionChanged.connect(self._sync_buttons)
        step = self._step     # buttons and fields: every change is its own step
        self.family.family_chosen.connect(lambda family: step(self._format, family=family))
        self.size.activated.connect(lambda _index: step(self._size_entered))
        self.size.lineEdit().editingFinished.connect(lambda: step(self._size_entered))
        self.grow.clicked.connect(lambda: step(self._step_size, +1))
        self.shrink.clicked.connect(lambda: step(self._step_size, -1))
        self.bold.clicked.connect(lambda on: step(self._format, bold=on))
        self.italic.clicked.connect(lambda on: step(self._format, italic=on))
        self.underline.clicked.connect(lambda on: step(self._format, underline=on))
        for key, button in self.align_buttons.items():
            button.clicked.connect(lambda _checked=False, k=key: step(self._align, k))
        self.fit.toggled.connect(lambda _checked: step(self._apply))

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """Shortcuts for bold/italic/underline: work while the panel has the focus.
        The buttons show the action's tooltip – also after remapping."""
        for key, button in (("text.bold", self.bold), ("text.italic", self.italic),
                            ("text.underline", self.underline)):
            action = actions[key]
            action.triggered.connect(lambda _checked=False, b=button: b.click())
            self.addAction(action)
            button.setToolTip(action.toolTip())
            action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))

    @property
    def obj(self) -> TextObject:
        return self.doc.objects[self.index]

    def set_object(self, index: int | None) -> None:
        """Edit an object (index in ``doc.objects``) or none with None (hint)."""
        if index != self.index:
            self.index = index
            self._frame = None
            self.refresh()

    def _editing_widgets(self):
        return (self.edit, self.family, self.size, self.grow, self.shrink, self.bold,
                self.italic, self.underline, *self.align_buttons.values(), self.fit,
                *self.position.spins.values())

    def set_editing(self, editing: bool) -> None:
        """Edit mode on/off: formatting without a selection then applies to further typing."""
        self._editing = editing

    def _whole_text(self) -> bool:
        """Does a formatting without a selection act on the whole text? Always outside
        edit mode, in edit mode only with a still empty frame."""
        return not self._editing or self.edit.document().isEmpty()

    def _step(self, change, *args, **kwargs) -> None:
        """Change as its own undo step: record what was typed before, then the new state.
        (In edit mode it belongs to the current edit – the main window handles that.)"""
        if self._updating:
            return
        self.edited.emit()
        change(*args, **kwargs)
        self.edited.emit()
        self.formatted.emit()

    # --- Formatting -------------------------------------------------------
    def _target(self) -> QTextCursor:
        """Selection, otherwise the whole text (like a selected text frame)."""
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)
        return cursor

    def _format(self, family: str | None = None, size: float | None = None,
                bold: bool | None = None, italic: bool | None = None,
                underline: bool | None = None) -> None:
        if self._updating:
            return
        fmt = QTextCharFormat()
        if family is not None:
            fmt.setFontFamilies([family])
        if size is not None:
            fmt.setFontPointSize(size)
        if bold is not None:
            fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        if italic is not None:
            fmt.setFontItalic(italic)
        if underline is not None:
            fmt.setFontUnderline(underline)
        selected = self.edit.textCursor().hasSelection()
        whole = not selected and self._whole_text()
        if whole:                                       # whole text: adjust the base format
            for key, value in (("family", family), ("pt", size), ("bold", bold),
                               ("italic", italic), ("underline", underline)):
                if value is not None:
                    self._base[key] = value
        self._formatting = True
        try:
            if selected or whole:
                self._target().mergeCharFormat(fmt)
            if not selected:
                self.edit.mergeCurrentCharFormat(fmt)   # keep typing in the same formatting
        finally:
            self._formatting = False
        self._apply()

    def set_size_pt(self, size: float) -> None:
        size = min(max(size, MIN_PT), MAX_PT)
        self._format(size=size)
        self._sync_buttons()

    def _size_entered(self) -> None:
        try:
            size = float(self.size.currentText().replace(",", "."))
        except ValueError:
            self._sync_buttons()
            return
        if not math.isfinite(size):
            self._sync_buttons()
            return
        # Loss of focus with an unchanged value must not unify anything (Qt sometimes reports it
        # also as “activated”, hence the check applies to both paths)
        if self._shown_pt is not None and abs(size - self._shown_pt) < 0.01:
            return
        self.set_size_pt(size)

    @staticmethod
    def _step_pt(current: float, direction: int) -> float:
        if direction > 0:
            bigger = [s for s in SIZES_PT if s > current + 0.01]
            return bigger[0] if bigger else min(current + 12, MAX_PT)
        smaller = [s for s in SIZES_PT if s < current - 0.01]
        return smaller[-1] if smaller else MIN_PT

    def _step_size(self, direction: int) -> None:
        """Each text piece in the selection (otherwise in the whole text) to its own next step."""
        if self._updating:
            return
        selected = self.edit.textCursor().hasSelection()
        if not selected and not self._whole_text():     # edit mode: only for further typing
            pt = self._props(self.edit.currentCharFormat())["pt"]
            fmt = QTextCharFormat()
            fmt.setFontPointSize(min(max(self._step_pt(pt, direction), MIN_PT), MAX_PT))
            self.edit.mergeCurrentCharFormat(fmt)
            self._apply()
            return
        cursor = self._target()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        document = self.edit.document()
        pieces = []
        block = document.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid():
                    a = max(start, fragment.position())
                    b = min(end, fragment.position() + fragment.length())
                    if a < b:
                        pieces.append((a, b, self._props(fragment.charFormat())["pt"]))
                it += 1
            block = block.next()
        editor = QTextCursor(document)
        self._formatting = True
        try:
            editor.beginEditBlock()
            for a, b, pt in pieces:
                editor.setPosition(a)
                editor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
                fmt = QTextCharFormat()
                fmt.setFontPointSize(min(max(self._step_pt(pt, direction), MIN_PT), MAX_PT))
                editor.mergeCharFormat(fmt)
            editor.endEditBlock()
            if not selected:
                self._base["pt"] = min(max(self._step_pt(self._base["pt"], direction), MIN_PT), MAX_PT)
                fmt = QTextCharFormat()
                fmt.setFontPointSize(self._base["pt"])
                self.edit.mergeCurrentCharFormat(fmt)
        finally:
            self._formatting = False
        self._apply()

    def _align(self, key: str) -> None:
        """Text position of the paragraphs in the selection or – in edit mode without a selection –
        of the paragraph at the caret; otherwise of all paragraphs."""
        cursor = self.edit.textCursor()
        if not cursor.hasSelection() and self._whole_text():
            cursor.select(QTextCursor.SelectionType.Document)
        fmt = cursor.blockFormat()
        fmt.setAlignment(_ALIGN_TO_QT[key])
        cursor.mergeBlockFormat(fmt)
        self._apply()

    # --- Editor ↔ model --------------------------------------------------
    def _props(self, fmt: QTextCharFormat) -> dict:
        """Formatting of a text piece: only what is explicitly set, otherwise base format."""
        props = dict(self._base)
        families = fmt.fontFamilies() if fmt.hasProperty(_P.FontFamilies) else None
        if families:
            props["family"] = families[0]
        if fmt.hasProperty(_P.FontPointSize) and fmt.fontPointSize() > 0:
            props["pt"] = fmt.fontPointSize()
        if fmt.hasProperty(_P.FontWeight):
            props["bold"] = fmt.fontWeight() >= QFont.Weight.Bold
        if fmt.hasProperty(_P.FontItalic):
            props["italic"] = fmt.fontItalic()
        if fmt.hasProperty(_P.TextUnderlineStyle) or fmt.hasProperty(_P.FontUnderline):
            props["underline"] = fmt.fontUnderline()
        return props

    def _fill_base_formats(self) -> None:
        """Set missing properties from the base format – the editor shows what is printed."""
        document = self.edit.document()
        block = document.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid() and not _complete(fragment.charFormat()):
                    cursor = QTextCursor(document)
                    cursor.setPosition(fragment.position())
                    cursor.setPosition(fragment.position() + fragment.length(),
                                       QTextCursor.MoveMode.KeepAnchor)
                    cursor.mergeCharFormat(_char_format_of(self._props(fragment.charFormat())))
                it += 1
            block = block.next()
        if not _complete(self.edit.currentCharFormat()):
            self.edit.mergeCurrentCharFormat(_char_format_of(self._props(self.edit.currentCharFormat())))

    def to_text_object(self) -> TextObject:
        base_pt = self._base["pt"]
        paragraphs = []
        block = self.edit.document().begin()
        while block.isValid():
            spans = []
            align = _block_align(block.blockFormat())
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid():
                    props = self._props(fragment.charFormat())
                    # U+2028 (line separator) and tab are not provided for in the model
                    text = fragment.text().replace("\t", " ")
                    for index, part in enumerate(text.split("\u2028")):
                        if index:
                            paragraphs.append(Paragraph(spans, align))
                            spans = []
                        spans.append(_span(part, props, base_pt))
                it += 1
            if not spans:
                spans.append(_span("", self._props(block.charFormat()), base_pt))
            paragraphs.append(Paragraph(spans, align))
            block = block.next()
        obj = self.obj                 # frame and rotation are kept while typing
        fit = self.fit.isChecked()
        w, h = obj.w_mm, obj.h_mm
        if fit and not obj.fit and obj.positioned and self._frame is not None:
            # switch on fixed frame size: the frame stays as large as it currently is
            w, h = round(self._frame.w, 3), round(self._frame.h, 3)
            if obj.rotation in (90, 270):
                w, h = h, w
        return TextObject(paragraphs, size_pt=base_pt, font_path=obj.font_path,
                          fit=fit, x_mm=obj.x_mm, y_mm=obj.y_mm,
                          w_mm=w, h_mm=h, rotation=obj.rotation)

    def _apply(self) -> None:
        if self._updating or self._formatting or self.index is None:
            return
        self._updating = True
        try:
            self._fill_base_formats()
        finally:
            self._updating = False
        self.doc.objects[self.index] = self.to_text_object()
        self._sync_buttons()
        self._update_frame_editing()
        self.changed.emit()

    def refresh(self) -> None:
        """Build the editor from the model (selection, undo, dragging at the handles)."""
        if self.index is not None and not (0 <= self.index < len(self.doc.objects)
                                           and isinstance(self.obj, TextObject)):
            self.index = None                      # object no longer exists (undo …)
        editing = self.index is not None
        self.hint.setVisible(not editing)
        for widget in self._editing_widgets():
            widget.setEnabled(editing)
        if not editing:
            self._show_nothing()
            return
        obj = self.obj
        self._updating = True
        try:
            first = obj.paragraphs[0].spans[0] if obj.paragraphs and obj.paragraphs[0].spans else None
            # Without a fixed base size the renderer computes relative to REF_PT; keep ratios
            ref = float(obj.size_pt or (REF_PT if any(sp.size_pt for pa in obj.paragraphs
                                                       for sp in pa.spans) else DEFAULT_PT))
            self._base = {"family": (first.family if first else None) or DEFAULT_FAMILY,
                          "pt": ref,
                          "bold": first.bold if first else True,
                          "italic": first.italic if first else False,
                          "underline": first.underline if first else False}
            document = self.edit.document()
            document.setUndoRedoEnabled(False)     # building is not a step in the editor
            document.clear()
            cursor = QTextCursor(document)
            cursor.setCharFormat(_char_format_of(self._base))
            for index, para in enumerate(obj.paragraphs):
                if index:
                    cursor.insertBlock()
                block_fmt = cursor.blockFormat()
                block_fmt.setAlignment(_ALIGN_TO_QT.get(para.align, Qt.AlignmentFlag.AlignHCenter))
                cursor.setBlockFormat(block_fmt)
                for span in para.spans:
                    cursor.insertText(span.text, _char_format(span, ref))
                if not any(span.text for span in para.spans):
                    # empty paragraph: insertText("") does nothing, store the format on the paragraph itself
                    fmt = (_char_format(para.spans[0], ref) if para.spans
                           else _char_format_of(self._base))
                    cursor.setBlockCharFormat(fmt)
                    cursor.setCharFormat(fmt)
            document.setUndoRedoEnabled(True)
            self.edit.setTextCursor(cursor)
            self.edit.setCurrentCharFormat(_char_format_of(self._props(cursor.charFormat())))
            self.fit.setChecked(obj.auto)
        finally:
            self._updating = False
        self._sync_buttons()
        self._update_frame_editing()

    def _show_nothing(self) -> None:
        """No text selected: empty, locked panel."""
        self._updating = True
        try:
            document = self.edit.document()
            document.setUndoRedoEnabled(False)
            document.clear()
            document.setUndoRedoEnabled(True)
            self.fit.setChecked(False)
            # do not show a font that does not apply – without blocked signals: the fields remember
            # “empty” and show the same font again on reselecting
            for combo in (self.family, self.size):
                combo.setCurrentIndex(-1)
                combo.setEditText("")
        finally:
            self._updating = False
        self.show_frame(None)

    # --- Position -----------------------------------------------------------
    def show_frame(self, rect: Rect | None) -> None:
        """Show the frame of the edited object in mm (from the main window after rendering)."""
        self._frame = rect
        self.position.show_frame(rect, self._fixed_frame())

    def _update_frame_editing(self) -> None:
        """Width/height changeable only with a fixed frame size, otherwise display of the size."""
        self.position.set_size_editable(self._fixed_frame())

    def _fixed_frame(self) -> bool:
        return self.index is not None and self.obj.fit

    def _frame_changed(self, key: str, value: float) -> None:
        if self.index is None or (key in "wh" and not self.obj.fit):
            return                                  # size only with a fixed frame size
        self.frame_edited.emit(key, value)

    def _sync_buttons(self) -> None:
        """Buttons show the formatting at the caret."""
        props = self._props(self.edit.currentCharFormat())
        mixed = self._selection_sizes()
        mixed_families = len({fonts.canonical(f) for f in self._selection_values("family")}) > 1
        self._shown_pt = None if len(mixed) > 1 else props["pt"]
        widgets = (self.family, self.size, self.bold, self.italic, self.underline,
                   *self.align_buttons.values())
        for w in widgets:
            w.blockSignals(True)
        # mixed fonts: field empty (like the size); a choice then sets all to it
        self.family.set_current_family(None if mixed_families else props["family"])
        self.size.setEditText("" if len(mixed) > 1 else i18n.number(props["pt"]))
        self.bold.setChecked(props["bold"])
        self.italic.setChecked(props["italic"])
        self.underline.setChecked(props["underline"])
        align = _block_align(self.edit.textCursor().blockFormat())
        self.align_buttons[align].setChecked(True)
        for w in widgets:
            w.blockSignals(False)

    def typing_scale(self) -> float:
        """Font size for further typing relative to the font the caret in the line layout is
        measured by (characters before it, at paragraph start the one after, empty paragraph:
        base size); 1.0 with selection or without own format for further typing."""
        cursor = self.edit.textCursor()
        if cursor.hasSelection():
            return 1.0
        probe = QTextCursor(self.edit.document())     # format in the text, not the one for typing
        probe.setPosition(cursor.position())
        here = (self._base["pt"] if probe.block().length() <= 1
                else self._props(probe.charFormat())["pt"])
        return self._props(self.edit.currentCharFormat())["pt"] / here

    def _selection_sizes(self) -> set[float]:
        """Different sizes within the selection (empty without selection)."""
        return {round(pt, 2) for pt in self._selection_values("pt")}

    def _selection_values(self, key: str) -> set:
        """Different values of a formatting (``_props`` key) within the selection
        (empty without selection)."""
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            return set()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        values = set()
        block = self.edit.document().findBlock(start)
        while block.isValid() and block.position() < end:
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if (fragment.isValid() and fragment.position() < end
                        and fragment.position() + fragment.length() > start):
                    values.add(self._props(fragment.charFormat())[key])
                it += 1
            block = block.next()
        return values

    def show_error(self, message: str | None) -> None:
        self.error.setText(message or "")
        self.error.setVisible(bool(message))


def _span(text: str, props: dict, base_pt: float) -> Span:
    return Span(text,
                family=None if props["family"] == DEFAULT_FAMILY else props["family"],
                size_pt=None if abs(props["pt"] - base_pt) < 0.01 else props["pt"],
                bold=props["bold"], italic=props["italic"], underline=props["underline"])


def _char_format_of(props: dict) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setFontFamilies([props["family"]])
    fmt.setFontPointSize(props["pt"])
    fmt.setFontWeight(QFont.Weight.Bold if props["bold"] else QFont.Weight.Normal)
    fmt.setFontItalic(props["italic"])
    fmt.setFontUnderline(props["underline"])
    return fmt


def _char_format(span: Span, base_pt: float) -> QTextCharFormat:
    return _char_format_of({"family": span.family or DEFAULT_FAMILY,
                            "pt": span.size_pt or base_pt, "bold": span.bold,
                            "italic": span.italic, "underline": span.underline})


def _complete(fmt: QTextCharFormat) -> bool:
    """Are all properties read from the model explicitly set?"""
    return (fmt.hasProperty(_P.FontFamilies) and fmt.hasProperty(_P.FontPointSize)
            and fmt.fontPointSize() > 0 and fmt.hasProperty(_P.FontWeight)
            and fmt.hasProperty(_P.FontItalic)
            and (fmt.hasProperty(_P.TextUnderlineStyle) or fmt.hasProperty(_P.FontUnderline)))


def _block_align(fmt) -> str:
    """Alignment of a paragraph; not set (e.g. after setPlainText) = centred."""
    if not fmt.hasProperty(QTextFormat.Property.BlockAlignment):
        return "center"
    return _align_of(fmt.alignment())


def _align_of(alignment) -> str:
    if alignment & Qt.AlignmentFlag.AlignJustify:
        return "justify"
    if alignment & Qt.AlignmentFlag.AlignRight:
        return "right"
    if alignment & Qt.AlignmentFlag.AlignLeft:
        return "left"
    return "center"
