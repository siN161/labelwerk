"""Panel „Text“: zeichenweise Formatierung wie im P-touch Editor.

Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
Formatierung auf den ganzen Text; sonst nur auf die Markierung.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (QFont, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextFormat,
                           QTextOption)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit)

from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
from ...fonts import DEFAULT_FAMILY
from . import Panel

_P = QTextFormat.Property

SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
DEFAULT_PT = 19
_ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}


class PlainPasteEdit(QTextEdit):
    """Rich-Text-Editor, der aus der Zwischenablage nur reinen Text übernimmt."""

    def insertFromMimeData(self, source) -> None:
        if source.hasText():
            self.textCursor().insertText(source.text())


def _button(text: str, tip: str, checkable: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setToolTip(tip)
    button.setCheckable(checkable)
    button.setObjectName("formatButton")
    return button


class TextPanel(Panel):
    def __init__(self, doc: Document):
        super().__init__(doc, "Text")
        if not doc.objects:
            doc.objects.append(TextObject(""))
        self._updating = False
        # Grundformat: gilt für alles, was nicht ausdrücklich formatiert ist (nicht Qts Widget-Schrift)
        self._base = {"family": DEFAULT_FAMILY, "pt": float(DEFAULT_PT), "bold": True,
                      "italic": False, "underline": False}

        self.section("Inhalt")
        self.edit = PlainPasteEdit()
        self.edit.setPlaceholderText("Text eingeben …")
        # Absätze ohne eigene Ausrichtung stehen zentriert – wie bisher in labelwerk
        self.edit.document().setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignHCenter))
        self.layout_.addWidget(self.edit)

        self.section("Schrift")
        self.family = QFontComboBox()
        self.layout_.addWidget(self.family)
        row = QHBoxLayout()
        self.size = QComboBox()
        self.size.setEditable(True)
        self.size.addItems([str(s) for s in SIZES_PT])
        self.size.setToolTip("Schriftgröße in pt")
        self.grow = _button("A⁺", "Schrift größer", checkable=False)
        self.shrink = _button("A⁻", "Schrift kleiner", checkable=False)
        row.addWidget(self.size, 1)
        row.addWidget(self.grow)
        row.addWidget(self.shrink)
        self.layout_.addLayout(row)

        self.section("Stil")
        row = QHBoxLayout()
        self.bold = _button("B", "Fett (Strg+B)")
        self.italic = _button("I", "Kursiv (Strg+I)")
        self.underline = _button("U", "Unterstrichen (Strg+U)")
        for button, attr in ((self.bold, "bold"), (self.italic, "italic"),
                             (self.underline, "underline")):
            button.setProperty("style", attr)
            row.addWidget(button)
        self.layout_.addLayout(row)

        self.section("Textposition")
        row = QHBoxLayout()
        self.align_group = QButtonGroup(self)
        self.align_buttons = {}
        for key, text, tip in (("left", "⯇", "Linksbündig"), ("center", "≡", "Zentriert"),
                               ("right", "⯈", "Rechtsbündig"), ("justify", "☰", "Blocksatz")):
            button = _button(text, tip)
            self.align_group.addButton(button)
            self.align_buttons[key] = button
            row.addWidget(button)
        self.layout_.addLayout(row)

        self.fit = _button("FESTE RAHMENGRÖSSE", "Text automatisch so skalieren, dass er passt")
        self.layout_.addWidget(self.fit)

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
        self.family.currentFontChanged.connect(lambda font: self._format(family=font.family()))
        self.size.activated.connect(lambda _: self._size_entered())
        self.size.lineEdit().editingFinished.connect(self._size_entered)
        self.grow.clicked.connect(lambda: self._step_size(+1))
        self.shrink.clicked.connect(lambda: self._step_size(-1))
        self.bold.clicked.connect(lambda on: self._format(bold=on))
        self.italic.clicked.connect(lambda on: self._format(italic=on))
        self.underline.clicked.connect(lambda on: self._format(underline=on))
        for key, button in self.align_buttons.items():
            button.clicked.connect(lambda _=False, k=key: self._align(k))
        self.fit.toggled.connect(lambda _: self._apply())
        for keys, button in ((QKeySequence.StandardKey.Bold, self.bold),
                             (QKeySequence.StandardKey.Italic, self.italic),
                             (QKeySequence.StandardKey.Underline, self.underline)):
            QShortcut(keys, self.edit, activated=button.click)

    @property
    def obj(self) -> TextObject:
        return self.doc.objects[0]

    # --- Formatieren ------------------------------------------------------
    def _target(self) -> QTextCursor:
        """Markierung, sonst der ganze Text (wie ein ausgewählter Textrahmen)."""
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
        if not self.edit.textCursor().hasSelection():   # ganzer Text: Grundformat anpassen
            for key, value in (("family", family), ("pt", size), ("bold", bold),
                               ("italic", italic), ("underline", underline)):
                if value is not None:
                    self._base[key] = value
        self._target().mergeCharFormat(fmt)
        self.edit.mergeCurrentCharFormat(fmt)       # Weitertippen in gleicher Formatierung
        self._apply()

    def set_size_pt(self, size: float) -> None:
        size = min(max(size, MIN_PT), MAX_PT)
        self._format(size=size)
        self._sync_buttons()

    def _size_entered(self) -> None:
        try:
            self.set_size_pt(float(self.size.currentText().replace(",", ".")))
        except ValueError:
            self._sync_buttons()

    def _step_size(self, direction: int) -> None:
        current = self._props(self.edit.currentCharFormat())["pt"]
        if direction > 0:
            bigger = [s for s in SIZES_PT if s > current + 0.01]
            self.set_size_pt(bigger[0] if bigger else min(current + 12, MAX_PT))
        else:
            smaller = [s for s in SIZES_PT if s < current - 0.01]
            self.set_size_pt(smaller[-1] if smaller else MIN_PT)

    def _align(self, key: str) -> None:
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.Document)
        fmt = cursor.blockFormat()
        fmt.setAlignment(_ALIGN_TO_QT[key])
        cursor.mergeBlockFormat(fmt)
        self._apply()

    # --- Editor ↔ Modell --------------------------------------------------
    def _props(self, fmt: QTextCharFormat) -> dict:
        """Formatierung eines Textstücks: nur ausdrücklich Gesetztes, sonst Grundformat."""
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
        """Fehlende Eigenschaften aus dem Grundformat setzen – der Editor zeigt, was gedruckt wird."""
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
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid():
                    spans.append(_span(fragment.text(), self._props(fragment.charFormat()), base_pt))
                it += 1
            if not spans:
                spans.append(_span("", self._props(block.charFormat()), base_pt))
            paragraphs.append(Paragraph(spans, _block_align(block.blockFormat())))
            block = block.next()
        return TextObject(paragraphs, size_pt=base_pt, font_path=self.obj.font_path,
                          fit=self.fit.isChecked())

    def _apply(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            self._fill_base_formats()
        finally:
            self._updating = False
        self.doc.objects[0] = self.to_text_object()
        self._sync_buttons()
        self.changed.emit()

    def refresh(self) -> None:
        """Editor aus dem Modell aufbauen (Start mit Einstellungen, später „Öffnen“)."""
        obj = self.obj
        self._updating = True
        try:
            first = obj.paragraphs[0].spans[0] if obj.paragraphs and obj.paragraphs[0].spans else None
            self._base = {"family": (first.family if first else None) or DEFAULT_FAMILY,
                          "pt": float(obj.size_pt or DEFAULT_PT),
                          "bold": first.bold if first else True,
                          "italic": first.italic if first else False,
                          "underline": first.underline if first else False}
            document = self.edit.document()
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
                    cursor.insertText(span.text, _char_format(span, obj.size_pt or DEFAULT_PT))
            self.edit.setTextCursor(cursor)
            self.edit.setCurrentCharFormat(_char_format_of(self._props(cursor.charFormat())))
            self.fit.setChecked(obj.auto)
        finally:
            self._updating = False
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        """Knöpfe zeigen die Formatierung an der Schreibmarke."""
        props = self._props(self.edit.currentCharFormat())
        widgets = (self.family, self.size, self.bold, self.italic, self.underline,
                   *self.align_buttons.values())
        for w in widgets:
            w.blockSignals(True)
        self.family.setCurrentFont(QFont(props["family"]))
        self.size.setEditText(f"{props['pt']:g}")
        self.bold.setChecked(props["bold"])
        self.italic.setChecked(props["italic"])
        self.underline.setChecked(props["underline"])
        align = _block_align(self.edit.textCursor().blockFormat())
        self.align_buttons[align].setChecked(True)
        for w in widgets:
            w.blockSignals(False)

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
    """Sind alle vom Modell gelesenen Eigenschaften ausdrücklich gesetzt?"""
    return (fmt.hasProperty(_P.FontFamilies) and fmt.hasProperty(_P.FontPointSize)
            and fmt.fontPointSize() > 0 and fmt.hasProperty(_P.FontWeight)
            and fmt.hasProperty(_P.FontItalic)
            and (fmt.hasProperty(_P.TextUnderlineStyle) or fmt.hasProperty(_P.FontUnderline)))


def _block_align(fmt) -> str:
    """Ausrichtung eines Absatzes; nicht gesetzt (z. B. nach setPlainText) = zentriert."""
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
