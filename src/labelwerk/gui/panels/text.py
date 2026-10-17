"""Panel „Text“: bearbeitet den ausgewählten Textrahmen – zeichenweise wie im P-touch Editor.

Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
Formatierung auf den ganzen Text; sonst nur auf die Markierung. Bereich „Position“: Lage
und (mit fester Rahmengröße) Größe des Rahmens in mm.

Geschrieben wird direkt auf dem Etikett (``gui.text_edit_mode``): Der Editor ``edit`` ist
dafür ein unsichtbarer Eingabepuffer (Kind des Panels, Größe 0, nicht im Layout) – er behält
im Schreibmodus den Tastaturfokus, damit tote Tasten, Compose und Eingabemethoden wirken.
"""
from __future__ import annotations

import math
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (QAction, QFont, QIcon, QTextCharFormat, QTextCursor, QTextFormat,
                           QTextOption)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QTextEdit)

from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
from ...fonts import DEFAULT_FAMILY
from ...layout import Rect
from ...render import REF_PT
from ..symbols import line_icon
from ..widgets import DoubleSpinBox
from . import Panel

_P = QTextFormat.Property

SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
DEFAULT_PT = 19
HINT = "Auf das Etikett klicken, um einen Textrahmen anzulegen"
POSITION_MM = (-999.9, 999.9)    # Lage darf auch neben dem Etikett liegen (ragt hinaus)
SIZE_MM = (1.0, 999.9)
_FRAME_ONLY = "Nur mit fester Rahmengröße änderbar"
_ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}


class PlainPasteEdit(QTextEdit):
    """Rich-Text-Editor, der aus der Zwischenablage nur reinen Text übernimmt."""

    focus_left = Signal()            # Tippen ist abgeschlossen (ein Schritt für Rückgängig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)      # Tab springt weiter, statt "\t" einzufügen
        # eine Zeile je Absatz wie auf dem Etikett: Pos1/Ende gelten für den ganzen Absatz
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        # Schreibmodus: Lage der Schreibmarke auf dem Etikett für Eingabemethoden (→ QRect)
        self.caret_rect = None

    def inputMethodQuery(self, query):
        if query == Qt.InputMethodQuery.ImCursorRectangle and self.caret_rect is not None:
            return self.caret_rect()           # Kandidatenfenster an der Schreibmarke
        return super().inputMethodQuery(query)

    def keyPressEvent(self, event) -> None:
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.textCursor().insertBlock()   # Umschalt+Enter = normaler Absatz, kein U+2028
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:
        if source.hasText():
            self.textCursor().insertText(source.text())

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.focus_left.emit()


def _button(text: str, tip: str, checkable: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setToolTip(tip)
    button.setCheckable(checkable)
    button.setObjectName("formatButton")
    return button


def _align_icon(key: str, dark_checked: bool = True) -> QIcon:
    """Liniensymbol der Textposition; gewählt weiß auf schwarz nur bei RawBlock."""
    return line_icon(f"align-{key}", dark_checked)


class TextPanel(Panel):
    frame_edited = Signal(str, float)   # Feld im Bereich „Position“ ("x" | "y" | "w" | "h"), mm

    def set_icon_style(self, dark_checked: bool) -> None:
        """Ausrichtungssymbole an das Design anpassen (weiß auf schwarz nur bei RawBlock)."""
        self.dark_checked_icons = dark_checked
        for key, button in self.align_buttons.items():
            button.setIcon(_align_icon(key, dark_checked))

    def __init__(self, doc: Document):
        super().__init__(doc, "Text")
        self.dark_checked_icons = True
        self.index: int | None = None   # bearbeitetes Objekt; None = kein Text ausgewählt
        self._frame: Rect | None = None   # zuletzt angezeigter Rahmen (mm)
        self._updating = False
        self._formatting = False        # während einer Formatierung: contentsChanged nicht doppelt anwenden
        self._shown_pt: float | None = float(DEFAULT_PT)   # zuletzt angezeigte Größe; None = gemischt
        # Grundformat: gilt für alles, was nicht ausdrücklich formatiert ist (nicht Qts Widget-Schrift)
        self._base = {"family": DEFAULT_FAMILY, "pt": float(DEFAULT_PT), "bold": True,
                      "italic": False, "underline": False}

        self.hint = QLabel(HINT)
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.layout_.addWidget(self.hint)

        # unsichtbarer Eingabepuffer des Schreibmodus: fokussierbar, aber ohne Fläche
        self.edit = PlainPasteEdit(self)
        self.edit.setFixedSize(0, 0)
        # Absätze ohne eigene Ausrichtung stehen zentriert – wie bisher in labelwerk; kein
        # Umbruch im Editor (Größe 0), damit Pos1/Ende und Zeilen den Absätzen entsprechen
        option = QTextOption(Qt.AlignmentFlag.AlignHCenter)
        option.setWrapMode(QTextOption.WrapMode.NoWrap)
        self.edit.document().setDefaultTextOption(option)

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
        self.bold = _button("B", "Fett")            # Tooltip mit Kürzel: use_actions
        self.italic = _button("I", "Kursiv")
        self.underline = _button("U", "Unterstrichen")
        for button, attr in ((self.bold, "bold"), (self.italic, "italic"),
                             (self.underline, "underline")):
            button.setProperty("style", attr)
            font = button.font()                 # wirkt auch im klassischen Design ohne Stylesheet
            getattr(font, "set" + attr.capitalize())(True)
            button.setFont(font)
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

        self.section("Position (mm)")
        grid = QGridLayout()
        self.pos_x, self.pos_y, self.pos_w, self.pos_h = (DoubleSpinBox() for _ in range(4))
        self._frame_spins = {"x": self.pos_x, "y": self.pos_y, "w": self.pos_w, "h": self.pos_h}
        for i, (key, text, tip) in enumerate((("x", "X", "Abstand vom linken Etikettrand"),
                                              ("y", "Y", "Abstand vom oberen Etikettrand"),
                                              ("w", "B", "Breite des Rahmens"),
                                              ("h", "H", "Höhe des Rahmens"))):
            spin = self._frame_spins[key]
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
            spin.setRange(*(POSITION_MM if key in "xy" else SIZE_MM))
            spin.setKeyboardTracking(False)        # erst nach Enter/Fokuswechsel/Pfeil übernehmen
            spin.setToolTip(tip)
            label = QLabel(text)
            label.setToolTip(tip)
            grid.addWidget(label, i // 2, (i % 2) * 2)
            grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)
            spin.valueChanged.connect(lambda value, k=key: self._frame_changed(k, value))
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.layout_.addLayout(grid)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()
        self.layout_.addWidget(self.error)
        self.layout_.addStretch()

        self.refresh()
        self.edit.focus_left.connect(self.edited)
        self.edit.document().contentsChanged.connect(self._apply)
        self.edit.currentCharFormatChanged.connect(self._sync_buttons)
        self.edit.cursorPositionChanged.connect(self._sync_buttons)
        self.edit.selectionChanged.connect(self._sync_buttons)
        step = self._step     # Knöpfe und Felder: jede Änderung ein eigener Schritt
        self.family.currentFontChanged.connect(
            lambda font: step(self._format, family=font.family()))
        self.size.activated.connect(lambda _: step(self._size_entered))
        self.size.lineEdit().editingFinished.connect(lambda: step(self._size_entered))
        self.grow.clicked.connect(lambda: step(self._step_size, +1))
        self.shrink.clicked.connect(lambda: step(self._step_size, -1))
        self.bold.clicked.connect(lambda on: step(self._format, bold=on))
        self.italic.clicked.connect(lambda on: step(self._format, italic=on))
        self.underline.clicked.connect(lambda on: step(self._format, underline=on))
        for key, button in self.align_buttons.items():
            button.clicked.connect(lambda _=False, k=key: step(self._align, k))
        self.fit.toggled.connect(lambda _: step(self._apply))

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """Kürzel für Fett/Kursiv/Unterstrichen: wirken, solange das Panel den Fokus hat.
        Die Knöpfe zeigen den Tooltip der Aktion – auch nach dem Umbelegen."""
        for key, button in (("text.bold", self.bold), ("text.italic", self.italic),
                            ("text.underline", self.underline)):
            action = actions[key]
            action.triggered.connect(lambda _=False, b=button: b.click())
            self.addAction(action)
            button.setToolTip(action.toolTip())
            action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))

    @property
    def obj(self) -> TextObject:
        return self.doc.objects[self.index]

    def set_object(self, index: int | None) -> None:
        """Objekt bearbeiten (Index in ``doc.objects``) bzw. mit None keins (Hinweis)."""
        if index != self.index:
            self.index = index
            self._frame = None
            self.refresh()

    def _editing_widgets(self):
        return (self.edit, self.family, self.size, self.grow, self.shrink, self.bold,
                self.italic, self.underline, *self.align_buttons.values(), self.fit,
                *self._frame_spins.values())

    def _step(self, change, *args, **kwargs) -> None:
        """Änderung als eigener Rückgängig-Schritt: vorher Getipptes festhalten, danach das Neue."""
        if self._updating:
            return
        self.edited.emit()
        change(*args, **kwargs)
        self.edited.emit()

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
        obj = self.obj                 # Rahmen und Drehung bleiben beim Tippen erhalten
        fit = self.fit.isChecked()
        w, h = obj.w_mm, obj.h_mm
        if fit and not obj.fit and obj.positioned and self._frame is not None:
            # feste Rahmengröße einschalten: Rahmen bleibt so groß, wie er gerade ist
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
        """Editor aus dem Modell aufbauen (Auswahl, Rückgängig, Ziehen an den Anfassern)."""
        if self.index is not None and not 0 <= self.index < len(self.doc.objects):
            self.index = None                      # Objekt gibt es nicht mehr
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
            # Ohne feste Grundgröße rechnet der Renderer relativ zu REF_PT; Verhältnisse erhalten
            ref = float(obj.size_pt or (REF_PT if any(sp.size_pt for pa in obj.paragraphs
                                                       for sp in pa.spans) else DEFAULT_PT))
            self._base = {"family": (first.family if first else None) or DEFAULT_FAMILY,
                          "pt": ref,
                          "bold": first.bold if first else True,
                          "italic": first.italic if first else False,
                          "underline": first.underline if first else False}
            document = self.edit.document()
            document.setUndoRedoEnabled(False)     # Aufbau ist kein Schritt im Editor
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
            document.setUndoRedoEnabled(True)
            self.edit.setTextCursor(cursor)
            self.edit.setCurrentCharFormat(_char_format_of(self._props(cursor.charFormat())))
            self.fit.setChecked(obj.auto)
        finally:
            self._updating = False
        self._sync_buttons()
        self._update_frame_editing()

    def _show_nothing(self) -> None:
        """Kein Text ausgewählt: leeres, gesperrtes Panel."""
        self._updating = True
        try:
            document = self.edit.document()
            document.setUndoRedoEnabled(False)
            document.clear()
            document.setUndoRedoEnabled(True)
            self.fit.setChecked(False)
        finally:
            self._updating = False
        for combo in (self.family, self.size):         # keine Schrift anzeigen, die nicht gilt
            combo.blockSignals(True)
            combo.setCurrentIndex(-1)
            combo.setEditText("")
            combo.blockSignals(False)
        self.show_frame(None)

    # --- Position -----------------------------------------------------------
    def show_frame(self, rect: Rect | None) -> None:
        """Rahmen des bearbeiteten Objekts in mm anzeigen (vom Hauptfenster nach dem Rendern)."""
        self._frame = rect
        for key, spin in self._frame_spins.items():
            spin.blockSignals(True)
            spin.setValue(getattr(rect, key) if rect is not None else 0.0)
            spin.blockSignals(False)
        self._update_frame_editing()

    def _update_frame_editing(self) -> None:
        """Breite/Höhe nur mit fester Rahmengröße änderbar, sonst Anzeige der Größe."""
        fixed = self.index is not None and self.obj.fit
        for spin in (self.pos_w, self.pos_h):
            if spin.isReadOnly() == fixed:
                spin.setReadOnly(not fixed)          # Pfeile bleiben sichtbar, wirken aber nicht
                spin.style().unpolish(spin)          # Stylesheet: [readOnly="true"] neu anwenden
                spin.style().polish(spin)
            spin.setToolTip(("Breite" if spin is self.pos_w else "Höhe") + " des Rahmens"
                            + ("" if fixed else f" – {_FRAME_ONLY}"))

    def _frame_changed(self, key: str, value: float) -> None:
        if self.index is None or (key in "wh" and not self.obj.fit):
            return
        self.frame_edited.emit(key, value)

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
