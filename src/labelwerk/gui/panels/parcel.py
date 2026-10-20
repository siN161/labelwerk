"""Panel des Reiters PAKET (Überschrift „Paketmarke“): Marke öffnen, Typ wählen (erkannt), Umwandlung ansehen, drucken oder als
Etikett in den Editor holen; eigene Typen anlegen, umbenennen, löschen; Freiräume eigener Typen
für diese Marke ändern (nicht gespeichert).

Die Logik steckt in ``labelwerk.parcel``; das Panel hält nur die geladene Marke, den gewählten
Typ und die Umwandlung für das Etikett des Hauptfensters (``set_target``). Die Arbeitsfläche zeigt
die Umwandlung, solange dieses Panel zu sehen ist (``documents``/``current_document``).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMenu, QPushButton, QToolButton, QWidget)

from ... import parcel
from ...document import Document
from ...i18n import N_, _, pgettext
from ..widgets import DoubleSpinBox
from . import Panel

OWN = "own"                                   # Eintrag „Eigene Typen“ in der Länderauswahl
UNVERIFIED = N_("unverified")
TYPE_ROLE = Qt.ItemDataRole.UserRole          # Kennung des Typs an jedem Listeneintrag


class ParcelPanel(Panel):
    view_changed = Signal()                   # Umwandlung neu (Arbeitsfläche zeigen)
    print_requested = Signal(list)            # Etiketten (Document) drucken – ein Auftrag
    editor_requested = Signal(object)         # Etikett (Document) im Editor öffnen
    own_requested = Signal()                  # Fenster „Eigener Typ“ öffnen
    rename_requested = Signal(str)            # eigener Typ (Kennung) umbenennen
    remove_requested = Signal(str)            # eigener Typ (Kennung) löschen
    open_requested = Signal()                 # MARKE ÖFFNEN … (Dateidialog im Hauptfenster)

    def __init__(self, doc: Document):
        super().__init__(doc, _("Parcel label"))
        self.source: parcel.Source | None = None
        self.path: Path | None = None
        self.conversion: parcel.Conversion | None = None
        self._label_id = doc.label_id
        self._model = "QL-600"
        self._current = 0                      # gezeigtes Etikett der Umwandlung
        self._error: str | None = None
        self._scores: dict[str, float] = {}    # erkannte Typen → Punktzahl
        self._tied: list[str] = []             # Gleichstand ohne geprüften Sieger: Nutzer wählt
        self._top: list[str] = []              # Typen mit der höchsten Punktzahl (✓)
        self._check_choice = False             # vorgewählt, aber andere gleich gut: prüfen
        self._spaces_for: tuple | None = None  # Typ und seine Freiräume, die die Felder zeigen
        self.setAcceptDrops(True)

        self.section(_("Country"))
        self.country = QComboBox()
        for code, name in parcel.countries():
            self.country.addItem(name, code)
        self.country.addItem(_("Own types only"), OWN)
        self.country.setCurrentIndex(max(0, self.country.findData(parcel.default_country())))
        self.layout_.addWidget(self.country)

        self.section(_("File"))
        self.open_button = QPushButton(_("OPEN PARCEL LABEL …"))
        self.open_button.setToolTip(_("PDF or image of a parcel label (DHL, Hermes …) – "
                                      "or drop the file here"))
        self.layout_.addWidget(self.open_button)
        self.file_label = QLabel(_("No parcel label open – open one or drop the file here."))
        self.file_label.setWordWrap(True)
        self.file_label.setTextFormat(Qt.TextFormat.PlainText)
        self.layout_.addWidget(self.file_label)

        self.section(pgettext("parcel", "Type"))
        self.types = QListWidget()
        rows = self.types.fontMetrics().lineSpacing() * 2 + 6    # Einträge brechen oft um
        self.types.setMinimumHeight(max(220, 7 * rows // 2 * 2))       # etwa 7 Einträge
        self.types.setWordWrap(True)                  # lange Typnamen brechen um
        self.types.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.types.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layout_.addWidget(self.types)
        own_row = QWidget()                            # nur bei gewähltem eigenem Typ
        own_layout = QHBoxLayout(own_row)
        own_layout.setContentsMargins(0, 0, 0, 0)
        self.rename_button = QPushButton(_("RENAME …"))
        self.remove_button = QPushButton(_("DELETE"))
        own_layout.addWidget(self.rename_button)
        own_layout.addWidget(self.remove_button)
        self.own_row = own_row
        own_row.hide()
        self.layout_.addWidget(own_row)
        self.own_button = QPushButton(_("NEW OWN TYPE …"))
        self.own_button.setToolTip(_("Draw the areas on the open parcel label and save them as "
                                     "your own type"))
        self.layout_.addWidget(self.own_button)

        self.spaces_title = self.section(_("Space"))
        self.spaces_box = QWidget()                    # je Freiraum des eigenen Typs ein Feld
        self._spaces_form = QFormLayout(self.spaces_box)
        self._spaces_form.setContentsMargins(0, 0, 0, 0)
        self.space_boxes: list[DoubleSpinBox] = []
        self.layout_.addWidget(self.spaces_box)
        self.spaces_title.hide()
        self.spaces_box.hide()

        self.notes = QLabel()
        self.notes.setObjectName("hint")
        self.notes.setWordWrap(True)
        self.notes.setTextFormat(Qt.TextFormat.PlainText)
        self.notes.hide()
        self.layout_.addWidget(self.notes)

        self.section(_("Result"))
        row = QWidget()
        nav = QHBoxLayout(row)
        nav.setContentsMargins(0, 0, 0, 0)
        self.prev_button = QToolButton()
        self.prev_button.setText("◀")
        self.prev_button.setToolTip(_("Previous label on the canvas"))
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QToolButton()
        self.next_button.setText("▶")
        self.next_button.setToolTip(_("Next label on the canvas"))
        nav.addWidget(self.prev_button)
        nav.addWidget(self.page_label, 1)
        nav.addWidget(self.next_button)
        self.layout_.addWidget(row)
        self.print_button = QPushButton(_("PRINT"))
        self.print_button.setToolTip(_("Print all labels of the parcel label in one job"))
        self.layout_.addWidget(self.print_button)
        self.editor_button = QPushButton(_("OPEN IN EDITOR"))
        self.editor_button.setToolTip(_("Edit the shown label like any other label (pieces as "
                                        "images)"))
        self.layout_.addWidget(self.editor_button)
        self.layout_.addStretch(1)

        self.country.currentIndexChanged.connect(self._country_changed)
        self.open_button.clicked.connect(self.open_requested)
        self.types.currentItemChanged.connect(self._type_chosen)
        self.types.customContextMenuRequested.connect(self._context_menu)
        self.own_button.clicked.connect(self.own_requested)
        self.rename_button.clicked.connect(self._rename_chosen)
        self.remove_button.clicked.connect(self._remove_chosen)
        self.prev_button.clicked.connect(lambda: self._go_to(self._current - 1))
        self.next_button.clicked.connect(lambda: self._go_to(self._current + 1))
        self.print_button.clicked.connect(self._print)
        self.editor_button.clicked.connect(self._to_editor)
        self._fill_types()
        self._update()

    # --- Zustand ------------------------------------------------------------------------
    @property
    def country_code(self) -> str:
        return self.country.currentData()

    @property
    def error(self) -> str | None:
        """Fehler beim Laden/Umwandeln (gezeigt im Panel), sonst None."""
        return self._error

    def show_render_error(self, message: str) -> None:
        """Die Umwandlung ließ sich nicht rendern: als Hinweis, nicht druckbar."""
        self.conversion, self._error = None, message
        self._update()

    def documents(self) -> list[Document]:
        return list(self.conversion.documents) if self.conversion is not None else []

    def current_document(self) -> Document | None:
        docs = self.documents()
        return docs[self._current] if docs else None

    def chosen_type(self) -> parcel.ParcelType | None:
        item = self.types.currentItem()
        type_id = item.data(TYPE_ROLE) if item is not None else None
        if not type_id:
            return None
        try:
            return parcel.find(type_id)
        except parcel.ParcelError:
            return None

    def set_target(self, label_id: str, model: str) -> None:
        """Etikett und Drucker des Hauptfensters: die Umwandlung gilt für sie (neu bei Wechsel)."""
        if (label_id, model) == (self._label_id, self._model):
            return
        self._label_id, self._model = label_id, model
        if self.source is not None:
            self._detect(keep=True)
            self._convert()

    # --- Laden --------------------------------------------------------------------------
    def load(self, path: str | Path) -> bool:
        """Marke laden, Typ erkennen und umwandeln; Fehler als Hinweis (nichts geladen)."""
        try:
            source = parcel.load(path)
        except parcel.ParcelError as e:
            message = str(e)
            if self.source is not None:            # die vorige Marke bleibt
                message = _("{error} – the previous parcel label stays loaded.").format(error=e)
            self._show_error(message)
            return False
        self.source, self.path = source, Path(path)
        self._spaces_for = None                    # neue Marke: Freiräume wie im Typ
        self._detect(keep=False)
        self._convert()
        return True

    def _detect(self, keep: bool) -> None:
        """Typen erkennen (✓ an denen mit der höchsten Punktzahl); ``keep``: gewählten Typ
        behalten – sonst den besten vorwählen, außer bei Gleichstand ohne geprüften Sieger oder
        ohne Treffer (dann wählt der Nutzer)."""
        chosen = self.chosen_type()
        country = None if self.country_code == OWN else self.country_code
        found = self._found(country)
        if keep and chosen is not None:
            wanted = chosen.id
        elif self._tied or not found:
            wanted = None                       # gleich gut oder nicht erkannt: Nutzer wählt
        else:
            wanted = found[0][0].id
        self._check_choice = not keep and wanted is not None and len(self._top) > 1
        self._fill_types(wanted)

    def _found(self, country: str | None) -> list[tuple[parcel.ParcelType, float]]:
        """Erkannte Typen (Punktzahl, Gleichstand) für die Quelle merken."""
        found = parcel.detect(self.source, country, self._label_id)
        if self.country_code == OWN:
            found = [(t, s) for t, s in found if t.own]
        self._scores = {t.id: s for t, s in found}
        best = max(self._scores.values(), default=None)
        self._top = [t.id for t, s in found if s == best]
        self._tied = [t.id for t in parcel.ambiguous(found)]
        return found

    def _convert(self) -> None:
        """Umwandlung für das Etikett des Hauptfensters (Fehler: Hinweis, keine Umwandlung)."""
        self.conversion, self._current, self._error = None, 0, None
        ptype = self.chosen_type()
        self._show_spaces(ptype)
        if ptype is not None and self.space_boxes:
            ptype = parcel.with_spaces(ptype, [box.value() for box in self.space_boxes])
        if self.source is not None and ptype is not None:
            try:
                self.conversion = parcel.convert(self.source, ptype, self._label_id, self._model)
            except (parcel.ParcelError, ValueError) as e:
                self._error = str(e)
        self._update()
        self.view_changed.emit()

    def _show_spaces(self, ptype: parcel.ParcelType | None) -> None:
        """Felder für die Freiräume des gewählten Typs – vorbelegt aus dem Typ, wenn ein anderer
        Typ oder eine neue Marke kommt; sonst bleiben die geänderten Werte."""
        key = (ptype.id, tuple(parcel.spaces(ptype))) if ptype is not None else None
        if key == self._spaces_for and key is not None:
            return
        self._spaces_for = key
        while self._spaces_form.rowCount():           # takeRow + deleteLater: das Feld, dessen
            row = self._spaces_form.takeRow(0)        # Signal gerade läuft, lebt bis danach
            for item in (row.labelItem, row.fieldItem):
                if item is not None and item.widget() is not None:
                    item.widget().hide()
                    item.widget().deleteLater()
        self.space_boxes = []
        for index, length in (parcel.spaces(ptype) if ptype is not None else []):
            box = DoubleSpinBox()
            box.setRange(0, parcel.MAX_SPACE_MM)
            box.setDecimals(1)
            box.setSuffix(" mm")
            box.setKeyboardTracking(False)            # erst nach der Eingabe neu umwandeln
            box.setValue(length)
            box.setToolTip(_("Blank tape for this parcel label – the type keeps its value"))
            box.valueChanged.connect(self._convert)
            self._spaces_form.addRow(_("After area {number}").format(number=index + 1), box)
            self.space_boxes.append(box)
        self.spaces_title.setVisible(bool(self.space_boxes))
        self.spaces_box.setVisible(bool(self.space_boxes))

    def _show_error(self, message: str) -> None:
        self._error = message
        self._update()

    # --- Typen --------------------------------------------------------------------------
    def _fill_types(self, wanted: str | None = None) -> None:
        """Liste nach Dienst gruppiert (Überschriften nicht wählbar), eigene Typen am Ende;
        erkannte Typen vorn in ihrer Gruppe mit ✓, ungeprüfte gekennzeichnet."""
        self.types.blockSignals(True)
        try:
            self.types.clear()
            groups: list[tuple[str, list[parcel.ParcelType]]] = []
            if self.country_code != OWN:
                for key, name in parcel.carriers(self.country_code):
                    members = [t for t in parcel.types(self.country_code)
                               if not t.own and t.carrier == key]
                    if members:
                        groups.append((name, members))
            own = parcel.own_types()
            if own:
                groups.append((_("Own types"), own))
            select = None
            for name, members in groups:
                head = QListWidgetItem(name.upper())
                head.setFlags(Qt.ItemFlag.NoItemFlags)
                font = QFont(head.font())
                font.setBold(True)
                head.setFont(font)
                self.types.addItem(head)
                members = sorted(members, key=lambda t: -self._scores.get(t.id, -1e9))
                for ptype in members:
                    text = ptype.name
                    if ptype.id in self._top:
                        text = "✓ " + text
                    if not ptype.verified and not ptype.own:
                        text = _("{name} · {unverified}").format(name=text, unverified=_(UNVERIFIED))
                    item = QListWidgetItem(text)
                    item.setData(TYPE_ROLE, ptype.id)
                    item.setToolTip(ptype.name)
                    self.types.addItem(item)
                    if ptype.id == wanted:
                        select = item
            if select is not None:
                self.types.setCurrentItem(select)
                self.types.scrollToItem(select)
        finally:
            self.types.blockSignals(False)

    def refresh_types(self, wanted: str | None = None) -> None:
        """Eigene Typen geändert (angelegt, umbenannt, gelöscht): Liste und Umwandlung neu."""
        current = self.chosen_type()
        if self.source is not None:
            country = None if self.country_code == OWN else self.country_code
            self._found(country)
        self._fill_types(wanted or (current.id if current is not None else None))
        self._convert()

    def _country_changed(self) -> None:
        if self.source is not None:
            self._detect(keep=False)
        else:
            self._fill_types()
        self._convert()

    def _type_chosen(self, *_args) -> None:
        self._tied = []                         # gewählt: der Gleichstand ist entschieden
        self._check_choice = False
        self._convert()

    def _chosen_own(self) -> str | None:
        ptype = self.chosen_type()
        return ptype.id if ptype is not None and ptype.own else None

    def _rename_chosen(self) -> None:
        if (type_id := self._chosen_own()) is not None:
            self.rename_requested.emit(type_id)

    def _remove_chosen(self) -> None:
        if (type_id := self._chosen_own()) is not None:
            self.remove_requested.emit(type_id)

    def _context_menu(self, point) -> None:
        item = self.types.itemAt(point)
        type_id = item.data(TYPE_ROLE) if item is not None else None
        if not type_id or not self._is_own(type_id):
            return
        menu = QMenu(self)
        menu.addAction(_("Rename …"), lambda: self.rename_requested.emit(type_id))
        menu.addAction(_("Delete"), lambda: self.remove_requested.emit(type_id))
        menu.exec(self.types.viewport().mapToGlobal(point))

    @staticmethod
    def _is_own(type_id: str) -> bool:
        return any(t.id == type_id for t in parcel.own_types())

    # --- Ergebnis -----------------------------------------------------------------------
    def _go_to(self, index: int) -> None:
        docs = self.documents()
        if docs and 0 <= index < len(docs):
            self._current = index
            self._update()
            self.view_changed.emit()

    def _print(self) -> None:
        docs = self.documents()
        if docs:
            self.print_requested.emit(docs)

    def _to_editor(self) -> None:
        doc = self.current_document()
        if doc is not None:
            self.editor_requested.emit(doc)

    def _update(self) -> None:
        """Anzeige nach dem Zustand: Datei, Hinweise, Etikett n/N, Knöpfe."""
        if self.path is not None:
            self.file_label.setText(self.path.name)
        notes = list(self.conversion.notes) if self.conversion is not None else []
        if self._check_choice and self.chosen_type() is not None:
            notes.insert(0, _("Several types fit equally well – please check the choice."))
        if self.conversion is not None and self.conversion.layout == "arranged":
            notes.insert(0, _("No layout for this label – the pieces were arranged anew."))
        if self._error:
            notes.insert(0, self._error)
        elif self.source is not None and self.chosen_type() is None:
            if self._tied:
                names = ", ".join(parcel.find(type_id).name for type_id in self._tied)
                notes.insert(0, _("Several types fit equally well ({types}) – choose one in the "
                                  "list.").format(types=names))
            elif not self._scores:
                notes.insert(0, _("Type not recognized – choose it in the list."))
            else:
                notes.insert(0, _("Choose the type in the list."))
        notes += parcel.own_warnings()          # beschädigte eigene Typen
        self.own_row.setVisible(self._chosen_own() is not None)
        self.notes.setText("\n".join(notes))
        self.notes.setVisible(bool(notes))
        docs = self.documents()
        self.page_label.setText(_("Label {current}/{total}").format(
            current=self._current + 1, total=len(docs)) if docs else "–")
        self.prev_button.setEnabled(self._current > 0)
        self.next_button.setEnabled(self._current < len(docs) - 1)
        self.print_button.setEnabled(bool(docs))
        self.editor_button.setEnabled(bool(docs))
        self.own_button.setEnabled(self.source is not None)

    # --- Ablegen ------------------------------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        if _parcel_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        paths = _parcel_files(event.mimeData())
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.load(paths[0])


def _parcel_files(mime) -> list[Path]:
    """Lokale Dateien mit Endung einer Paketmarke."""
    return [Path(url.toLocalFile()) for url in mime.urls()
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in parcel.SUFFIXES]
