"""Schreibmodus: Text direkt im Rahmen auf dem Etikett schreiben und markieren.

Der Editor des Text-Panels bleibt als unsichtbarer Eingabepuffer erhalten und hat im
Schreibmodus den Tastaturfokus; die Arbeitsfläche zeigt weiter das echte Objektbild aus dem
Kern. Schreibmarke, Markierung und Mausklicks rechnet ``TextEditSession`` über den
Zeilensatz desselben Renders (``RenderedObject.layout``) um – Vorschau = Druck gilt auch
beim Tippen. Positionen: Editor in UTF-16-Einheiten, Zeilensatz in Zeichen
(``render.to_utf16``/``from_utf16``).

Start und Ende samt Rückgängig-Schritt steuert das Hauptfenster (``MainWindow.edit_text``,
``finish_editing``); die Sitzung meldet nur, dass sie enden soll (``end_requested``).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QGuiApplication, QTextCursor, QTextDocument

from .. import layout
from ..render import PT, RenderedObject, TextLayout, from_utf16, to_utf16


class TextEditSession(QObject):
    """Schreibmodus für höchstens ein Textobjekt (``index``) des Hauptfensters."""

    end_requested = Signal()          # Esc: Schreibmodus soll enden

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._canvas = window.canvas
        self._editor = window.panel("text").edit
        self.index: int | None = None
        self._canvas.edit_pressed.connect(self._press)
        for signal in (self._editor.cursorPositionChanged, self._editor.selectionChanged):
            signal.connect(self.update_marks)
        self._editor.installEventFilter(self)

    @property
    def active(self) -> bool:
        return self.index is not None

    # --- Start / Ende -------------------------------------------------------
    def start(self, index: int, point: QPointF | None = None) -> None:
        """Schreibmodus für Objekt ``index`` (gewählt, im Text-Panel): Editor neu aus dem
        Modell, Tastaturfokus hinein, Schreibmarke an ``point`` (Druckpunkte in Leserichtung,
        z. B. Doppelklick) oder ans Textende."""
        self._window.panel("text").refresh()      # Editor = Modell, eigenes Rückgängig ab hier
        self.index = index
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
        self._editor.caret_rect = None
        self._canvas.set_editing(None)
        self._canvas.setFocusProxy(None)
        if self._editor.hasFocus():
            self._canvas.setFocus()
        return index

    def content_changed(self) -> None:
        """Text oder Format geändert: sofort neu rendern, damit Schreibmarke und Bild zum
        selben Zeilensatz gehören."""
        if self.active:
            self._window.render_now()

    # --- Anzeige ------------------------------------------------------------
    def update_marks(self) -> None:
        """Schreibmarke, Markierung und Rahmen aus Editor und aktuellem Zeilensatz an die
        Arbeitsfläche geben. Passt der Zeilensatz (noch) nicht zum Editor – das Rendern
        folgt gleich bzw. ist gescheitert –, bleibt die bisherige Anzeige."""
        current = self._current()
        if current is None:
            return
        rendered, text_layout, text, rotation = current
        cursor = self._editor.textCursor()
        pos = from_utf16(text, cursor.position())
        anchor = from_utf16(text, cursor.anchor())
        x, top, height = text_layout.caret(pos)
        caret = QLineF(_label(rendered, rotation, x, top),
                       _label(rendered, rotation, x, top + height))
        marked = ([_label_rect(rendered, rotation, *rect)
                   for rect in text_layout.selection_rects(anchor, pos)] if anchor != pos else [])
        self._canvas.set_edit_marks(self._frame(rendered, rotation, x, top, height),
                                    caret, marked)
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

    def _frame(self, rendered: RenderedObject, rotation: int, x: float, top: float,
               height: float) -> QRectF:
        """Rahmen des Objekts; ein leerer Text bekommt einen Platzhalter (halbe Zeile breit)
        um die Schreibmarke – je nach Textposition rechts, mittig oder links von ihr."""
        if rendered.w and rendered.h:
            return QRectF(rendered.x, rendered.y, rendered.w, rendered.h)
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
        position = self._position_at(point)
        if position is None:
            return
        cursor = self._editor.textCursor()
        mode = QTextCursor.MoveMode.KeepAnchor if extend else QTextCursor.MoveMode.MoveAnchor
        cursor.setPosition(position, mode)
        self._editor.setTextCursor(cursor)
        self._editor.setFocus()

    def eventFilter(self, watched, event) -> bool:
        if (self.active and watched is self._editor and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape):
            self.end_requested.emit()
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
