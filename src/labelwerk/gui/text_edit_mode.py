"""Schreibmodus: Text direkt im Rahmen auf dem Etikett schreiben und markieren.

Der Editor des Text-Panels bleibt als unsichtbarer Eingabepuffer erhalten und hat im
Schreibmodus den Tastaturfokus; die Arbeitsfläche zeigt weiter das echte Objektbild aus dem
Kern. Schreibmarke, Markierung und Mausklicks rechnet ``TextEditSession`` über den
Zeilensatz desselben Renders (``RenderedObject.layout``) um – Vorschau = Druck gilt auch
beim Tippen. Positionen: Editor in UTF-16-Einheiten, Zeilensatz in Zeichen
(``render.to_utf16``/``from_utf16``).

Im Schreibmodus wirken die Tasten des Editors (Pfeile, Pos1/Ende, Entf, Strg+A/C/X/V/Z …);
Auf/Ab folgen den Zeilen auf dem Etikett, Tab bleibt ohne Wirkung (Tabulatoren druckt
labelwerk nicht, und der Fokus soll den Text nicht verlassen). Strg+Z geht wie der Knopf
im Dokument weiter, wenn im Editor nichts mehr zurückzunehmen ist. Ein Rahmen ohne feste Größe wächst an der Kante
seiner Textposition (``layout.anchor_after_edit``). Start und Ende samt Rückgängig-Schritt
(eine Bearbeitung = ein Schritt) steuert das Hauptfenster (``MainWindow.edit_text``,
``finish_editing``).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QTextCursor, QTextDocument
from PySide6.QtWidgets import QAbstractButton, QApplication

from .. import layout
from ..render import PT, RenderedObject, TextLayout, from_utf16, to_utf16

_VERTICAL = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}
_TABS = (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)


class TextEditSession(QObject):
    """Schreibmodus für höchstens ein Textobjekt (``index``) des Hauptfensters."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._canvas = window.canvas
        self._panel = window.panel("text")
        self._editor = self._panel.edit
        self.index: int | None = None
        self._goal: tuple[float, int] | None = None   # Auf/Ab: Ziel-x und Position danach
        self._quiet = False                       # Anzeige erst, wenn das Objekt steht
        self._canvas.edit_pressed.connect(self._press)
        self._canvas.edit_dragged.connect(self._drag)
        self._canvas.edit_double_clicked.connect(self._select_word)
        for signal in (self._editor.cursorPositionChanged, self._editor.selectionChanged):
            signal.connect(self.update_marks)
        # nach einem Knopf des Panels bzw. wenn die Liste von „Schrift“/Größe zugeht oder
        # dort Enter fällt, weiter an der Schreibmarke tippen – Pfeiltasten im Feld bleiben dort
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

    # --- Start / Ende -------------------------------------------------------
    def start(self, index: int, point: QPointF | None = None) -> None:
        """Schreibmodus für Objekt ``index`` (gewählt, im Text-Panel): Editor neu aus dem
        Modell, Tastaturfokus hinein, Schreibmarke an ``point`` (Druckpunkte in Leserichtung,
        z. B. Doppelklick) oder ans Textende."""
        self._panel.refresh()                      # Editor = Modell, eigenes Rückgängig ab hier
        self.index = index
        self._goal = None
        self._panel.set_editing(True)
        self._editor.caret_rect = self._caret_rect
        self._canvas.set_editing(index)
        self._canvas.setFocusProxy(self._editor)   # Klick auf die Fläche: Fokus bleibt im Editor
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
        """Schreibmodus beenden (Markierung entfällt, Objekt-Kürzel gelten wieder); zurück
        kommt der Index des bearbeiteten Objekts."""
        index, self.index = self.index, None
        if index is None:
            return None
        cursor = self._editor.textCursor()
        cursor.clearSelection()                    # Formatieren wirkt wieder auf den ganzen Rahmen
        self._editor.setTextCursor(cursor)
        self._panel.set_editing(False)
        self._editor.caret_rect = None
        self._canvas.set_editing(None)
        self._canvas.setFocusProxy(None)
        if self._editor.hasFocus():
            self._canvas.setFocus()
        return index

    def content_changed(self) -> None:
        """Text oder Format geändert: sofort neu rendern, damit Schreibmarke und Bild zum
        selben Zeilensatz gehören. Ein Rahmen mit Position und ohne feste Größe wächst dabei
        an der Kante seiner Textposition (die Oberkante der ersten Zeile bleibt); ohne
        Position bleibt der Text mittig, eine feste Rahmengröße passt ihn wie bisher ein."""
        if not self.active:
            return
        window, index = self._window, self.index
        obj = window.doc.objects[index]
        anchored = obj.positioned and not obj.fit and index < len(window.rendered)
        old = window.rendered[index] if anchored else None   # wie zuletzt angezeigt
        self._quiet = True
        try:
            window.render_now()                        # neuer Text, noch an der alten Stelle
            new = window.rendered[index] if index < len(window.rendered) else None
            if (old is not None and new is not None and new is not old
                    and old.layout is not None and new.layout is not None):
                position = layout.anchor_after_edit(obj, old, new)
                if position != (obj.x_mm, obj.y_mm):
                    obj.x_mm, obj.y_mm = position
                    window.render_now()
                    # der Zeilensatz hängt nicht von der Lage ab (relativ zum Rahmen): die
                    # schon gemessenen Zeichengrenzen weiter nutzen statt neu zu messen
                    window.rendered[index].layout = new.layout
        finally:
            self._quiet = False
        self.update_marks()

    # --- Anzeige ------------------------------------------------------------
    def update_marks(self) -> None:
        """Schreibmarke, Markierung und Rahmen aus Editor und aktuellem Zeilensatz an die
        Arbeitsfläche geben. Passt der Zeilensatz (noch) nicht zum Editor – das Rendern
        folgt gleich bzw. ist gescheitert –, bleibt die bisherige Anzeige."""
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
        if abs(scale - 1) > 1e-6:                     # Weitertippen in anderer Größe (A⁺ …)
            baseline = next(line.baseline for line in text_layout.lines
                            if line.start <= pos <= line.end)
            top, height = baseline - (baseline - top) * scale, height * scale
        caret = QLineF(_label(rendered, rotation, x, top),
                       _label(rendered, rotation, x, top + height))
        frame = self._frame(rendered, text_layout, rotation, x, top, height)
        # ein markierter Absatzwechsel am Ende der breitesten Zeile endet am Rahmen
        marked = ([_label_rect(rendered, rotation, *rect).intersected(frame)
                   for rect in text_layout.selection_rects(anchor, pos)] if anchor != pos else [])
        self._canvas.set_edit_marks(frame, caret, marked)
        if self._editor.hasFocus():
            QGuiApplication.inputMethod().update(Qt.InputMethodQuery.ImCursorRectangle)

    def _caret_rect(self) -> QRect:
        """Schreibmarke auf der Arbeitsfläche in Koordinaten des (unsichtbaren) Editors."""
        line = self._canvas.caret_line()
        rect = QRectF(line.p1(), line.p2()).normalized()
        top_left = self._editor.mapFromGlobal(
            self._canvas.viewport().mapToGlobal(rect.topLeft().toPoint()))
        return QRect(top_left.x(), top_left.y(), max(1, round(rect.width())),
                     max(1, round(rect.height())))

    def _frame(self, rendered: RenderedObject, text_layout: TextLayout, rotation: int,
               x: float, top: float, height: float) -> QRectF:
        """Rahmen im Schreibmodus: Tintenbox des Objekts samt den Zeilen von Ober- bis
        Unterlänge, damit Schreibmarke und Markierung darin liegen. Ein leerer Text bekommt
        einen Platzhalter (halbe Zeile breit) um die Schreibmarke – je nach Textposition
        rechts, mittig oder links von ihr."""
        if rendered.w and rendered.h:
            lines = text_layout.lines
            left = min(line.stops[0] for line in lines)
            right = max(line.stops[-1] for line in lines)
            bottom = max(line.top + line.height for line in lines)
            box = _label_rect(rendered, rotation, left, lines[0].top, right - left,
                              bottom - lines[0].top)
            return box.united(QRectF(rendered.x, rendered.y, rendered.w, rendered.h))
        width = rendered.base_pt * PT / 2
        obj = self._window.doc.objects[self.index]
        align = obj.paragraphs[0].align if obj.paragraphs else "left"
        left = x - {"center": width / 2, "right": width}.get(align, 0.0)
        return _label_rect(rendered, rotation, left, top, width, height)

    def _current(self) -> tuple[RenderedObject, TextLayout, str, int] | None:
        """Gerendertes Objekt, sein Zeilensatz, Text des Editors und Drehung – nur wenn der
        Zeilensatz zum Text im Editor passt."""
        window, index = self._window, self.index
        if index is None or not 0 <= index < min(len(window.rendered), len(window.doc.objects)):
            return None
        rendered = window.rendered[index]
        text = editor_text(self._editor.document())
        if rendered.layout is None or "\n".join(rendered.layout.texts) != text:
            return None
        return rendered, rendered.layout, text, window.doc.objects[index].rotation

    # --- Maus und Tastatur ----------------------------------------------------
    def _position_at(self, point: QPointF) -> int | None:
        """Editor-Position (UTF-16) der Zeichengrenze am Punkt (Druckpunkte in Leserichtung)."""
        current = self._current()
        if current is None:
            return None
        rendered, text_layout, text, rotation = current
        u, v = layout.to_object((point.x(), point.y()), rendered, rotation)
        return to_utf16(text, text_layout.hit(u, v))

    def _press(self, point: QPointF, extend: bool) -> None:
        """Klick in den Rahmen: Schreibmarke dorthin (mit Umschalt: Markierung bis dorthin)."""
        self._move_to(self._position_at(point), extend)
        self._editor.setFocus()

    def _drag(self, point: QPointF) -> None:
        """Ziehen im Rahmen markiert vom Klickpunkt bis hierher."""
        self._move_to(self._position_at(point), extend=True)

    def _select_word(self, point: QPointF) -> None:
        """Doppelklick im Schreibmodus markiert das Wort am Punkt."""
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
        """Auf/Ab: in die Zeile darüber/darunter, so nah wie möglich an derselben Stelle auf
        dem Etikett (der Editor kennt die Zeilen des Etiketts nicht). Über der ersten bzw.
        unter der letzten Zeile geht es an den Anfang bzw. ans Ende."""
        current = self._current()
        if current is None:
            return
        _, text_layout, text, _ = current
        position = self._editor.textCursor().position()
        pos = from_utf16(text, position)
        lines = text_layout.lines
        row = next(i for i, line in enumerate(lines) if line.start <= pos <= line.end)
        # mehrmals Auf/Ab hintereinander: die Spalte vom Anfang der Folge halten
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
        """Nach Formatieren im Panel weiter an der Schreibmarke tippen."""
        if self.active:
            self._editor.setFocus()

    def _return_focus_from_button(self) -> None:
        """Ein Knopf des Panels hat formatiert (Klick nahm ihm den Fokus): zurück zum Text.
        Felder mit Tastaturbedienung (Schrift, Größe) behalten ihn."""
        if isinstance(QApplication.focusWidget(), QAbstractButton):
            self._return_focus()

    def _focus_changed(self, _old, new) -> None:
        if self.active:
            self._canvas.set_caret_focus(new is self._editor)

    def eventFilter(self, watched, event) -> bool:
        if watched in self._popups and event.type() == QEvent.Type.Hide:
            QTimer.singleShot(0, self._return_focus)   # nachdem Qt den Fokus zurückgegeben hat
        elif (self.active and watched is self._editor
              and event.type() == QEvent.Type.KeyPress):
            if event.key() in _TABS:
                return True                             # Tab: ohne Wirkung, Fokus bleibt
            if (event.matches(QKeySequence.StandardKey.Undo)
                    and not self._editor.document().isUndoAvailable()):
                self._window.undo()                     # wie der Knopf: weiter im Dokument
                return True
            if (event.key() in _VERTICAL
                    and not event.modifiers() & ~Qt.KeyboardModifier.ShiftModifier):
                self._vertical(_VERTICAL[event.key()],
                               bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                return True
        return super().eventFilter(watched, event)


def editor_text(document: QTextDocument) -> str:
    """Text des Editors, wie ihn das Modell bekommt (``TextPanel.to_text_object``): Absätze
    mit „\\n“, Zeilentrenner U+2028 als Absatz, Tab als Leerzeichen – je ein Zeichen, die
    Positionen bleiben also gleich."""
    lines = []
    block = document.begin()
    while block.isValid():
        lines.append(block.text().replace("\t", " ").replace(" ", "\n"))
        block = block.next()
    return "\n".join(lines)


def _label(rendered: RenderedObject, rotation: int, u: float, v: float) -> QPointF:
    """Objektkoordinaten (ungedreht) → Punkt auf dem Etikett (Druckpunkte in Leserichtung)."""
    return QPointF(*layout.from_object((u, v), rendered, rotation))


def _label_rect(rendered: RenderedObject, rotation: int, u: float, v: float, w: float,
                h: float) -> QRectF:
    """Rechteck in Objektkoordinaten → Rechteck auf dem Etikett (Drehung um 90°-Schritte)."""
    return QRectF(_label(rendered, rotation, u, v),
                  _label(rendered, rotation, u + w, v + h)).normalized()
