"""Panel „Text“: zeichenweise Formatierung wie im P-touch Editor.

Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
Formatierung auf den ganzen Text; sonst nur auf die Markierung.
"""
from __future__ import annotations

import math
from importlib import resources

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (QFont, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextFormat,
                           QTextOption)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit)

from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
from ...fonts import DEFAULT_FAMILY
from ...render import REF_PT
from . import Panel

_P = QTextFormat.Property

SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
DEFAULT_PT = 19
_ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}


class PlainPasteEdit(QTextEdit):
    """Rich-Text-Editor, der aus der Zwischenablage nur reinen Text übernimmt."""

    def __init__(self):
        super().__init__()
        self.setTabChangesFocus(True)      # Tab springt weiter, statt "\t" einzufügen

    def keyPressEvent(self, event) -> None:
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.textCursor().insertBlock()   # Umschalt+Enter = normaler Absatz, kein U+2028
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
    """Liniensymbol: schwarz im Normalzustand, weiß auf dem schwarzen Hintergrund gewählter Knöpfe
    (RawBlock); im klassischen Design bleibt der gewählte Knopf hell, also auch schwarz."""
    folder = resources.files("labelwerk.gui") / "icons"
    icon = QIcon()
    for color, state in (("black", QIcon.State.Off), ("white" if dark_checked else "black", QIcon.State.On)):
        path = str(folder / f"align-{key}-{color}.svg")
        icon.addFile(path, QSize(), QIcon.Mode.Normal, state)
    return icon


class TextPanel(Panel):
    def set_icon_style(self, dark_checked: bool) -> None:
        """Ausrichtungssymbole an das Design anpassen (weiß auf schwarz nur bei RawBlock)."""
        self.dark_checked_icons = dark_checked
        for key, button in self.align_buttons.items():
            button.setIcon(_align_icon(key, dark_checked))

    def __init__(self, doc: Document):
        super().__init__(doc, "Text")
        self.dark_checked_icons = True
        if not doc.objects:
            doc.objects.append(TextObject(""))
        self._updating = False
        self._formatting = False        # während einer Formatierung: contentsChanged nicht doppelt anwenden
        self._shown_pt: float | None = float(DEFAULT_PT)   # zuletzt angezeigte Größe; None = gemischt
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
        self.size.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)   # Eingaben nicht an die Liste anhängen
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
        for key, tip in (("left", "Linksbündig"), ("center", "Zentriert"),
                         ("right", "Rechtsbündig"), ("justify", "Blocksatz")):
            button = _button("", tip)
            button.setIcon(_align_icon(key))
            button.setIconSize(QSize(16, 16))
            button.setAccessibleName(tip)
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
        self.edit.selectionChanged.connect(self._sync_buttons)
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
            QShortcut(keys, self, context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
                      activated=button.click)

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
        self._formatting = True
        try:
            self._target().mergeCharFormat(fmt)
            if not self.edit.textCursor().hasSelection():
                self.edit.mergeCurrentCharFormat(fmt)   # Weitertippen in gleicher Formatierung
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
        # Fokusverlust mit unverändertem Wert darf nichts vereinheitlichen (Qt meldet ihn teils
        # auch als „activated“, daher gilt die Prüfung für beide Wege)
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
        """Jedes Textstück in der Markierung (sonst im ganzen Text) auf seine eigene nächste Stufe."""
        if self._updating:
            return
        selected = self.edit.textCursor().hasSelection()
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
            align = _block_align(block.blockFormat())
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid():
                    props = self._props(fragment.charFormat())
                    # U+2028 (Zeilentrenner) und Tab sind im Modell nicht vorgesehen
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
        return TextObject(paragraphs, size_pt=base_pt, font_path=self.obj.font_path,
                          fit=self.fit.isChecked())

    def _apply(self) -> None:
        if self._updating or self._formatting:
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
            # Ohne feste Grundgröße rechnet der Renderer relativ zu REF_PT; Verhältnisse erhalten
            ref = float(obj.size_pt or (REF_PT if any(sp.size_pt for pa in obj.paragraphs
                                                       for sp in pa.spans) else DEFAULT_PT))
            self._base = {"family": (first.family if first else None) or DEFAULT_FAMILY,
                          "pt": ref,
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
                    cursor.insertText(span.text, _char_format(span, ref))
                if not any(span.text for span in para.spans):
                    # leerer Absatz: insertText("") tut nichts, Format am Absatz selbst ablegen
                    fmt = (_char_format(para.spans[0], ref) if para.spans
                           else _char_format_of(self._base))
                    cursor.setBlockCharFormat(fmt)
                    cursor.setCharFormat(fmt)
            self.edit.setTextCursor(cursor)
            self.edit.setCurrentCharFormat(_char_format_of(self._props(cursor.charFormat())))
            self.fit.setChecked(obj.auto)
        finally:
            self._updating = False
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        """Knöpfe zeigen die Formatierung an der Schreibmarke."""
        props = self._props(self.edit.currentCharFormat())
        mixed = self._selection_sizes()
        self._shown_pt = None if len(mixed) > 1 else props["pt"]
        widgets = (self.family, self.size, self.bold, self.italic, self.underline,
                   *self.align_buttons.values())
        for w in widgets:
            w.blockSignals(True)
        self.family.setCurrentFont(QFont(props["family"]))
        self.size.setEditText("" if len(mixed) > 1 else f"{props['pt']:g}")
        self.bold.setChecked(props["bold"])
        self.italic.setChecked(props["italic"])
        self.underline.setChecked(props["underline"])
        align = _block_align(self.edit.textCursor().blockFormat())
        self.align_buttons[align].setChecked(True)
        for w in widgets:
            w.blockSignals(False)

    def _selection_sizes(self) -> set[float]:
        """Verschiedene Größen innerhalb der Markierung (leer ohne Markierung)."""
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            return set()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        sizes = set()
        block = self.edit.document().findBlock(start)
        while block.isValid() and block.position() < end:
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if (fragment.isValid() and fragment.position() < end
                        and fragment.position() + fragment.length() > start):
                    sizes.add(round(self._props(fragment.charFormat())["pt"], 2))
                it += 1
            block = block.next()
        return sizes

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
