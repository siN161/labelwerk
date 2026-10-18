"""Panel „Serie“: Tabelle (CSV/Excel) oder Nummerierung, Spalten, Zeilen mit Häkchen, Vorschau.

Die Tabelle liest der Kern (``series.table_for``); das Panel merkt sich, woraus sie stammt
(Quelle, Blatt, Nummerierung) und liest nur bei Änderung neu – nicht als Nebenwirkung von
Rückgängig. Eine geänderte Datei liest ``check_file`` (vor dem Drucken), ``reload`` (Öffnen) liest
immer. Die Häkchen gehören zur Anzeige, nicht zum Etikett (nach dem Öffnen ist jede Zeile gewählt).
"""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QListWidget, QPushButton, QTableWidget, QTableWidgetItem, QToolButton,
                               QWidget)

from ... import series
from ...document import CUTS, MAX_DIGITS, MAX_NUMBER, MAX_SERIES_ROWS, Document, Numbering, Series
from ...series import SeriesError, Table
from ..widgets import SpinBox
from . import Panel

NO_SERIES = "Keine Serie"
NUMBERING = "Nummerierung"
CUT_TITLES = {"each": "Nach jedem Etikett", "end": "Nur am Ende"}
SHOWN_COLUMNS = 3                   # Spalten in der Zeilentabelle (die Häkchen sitzen in der ersten)
ROWS_HEIGHT = 180


class SeriesPanel(Panel):
    table_requested = Signal()          # TABELLE … – das Hauptfenster fragt nach der Datei
    insert_column = Signal(str)         # Spaltenname → als {Name} ins Etikett

    def __init__(self, doc: Document):
        super().__init__(doc, "Serie")
        self.table: Table | None = None
        self.error: str | None = None        # Tabelle nicht lesbar
        self._field_error: str | None = None  # Nummerierungsfeld ungültig (nicht übernommen)
        self._missing: list[str] = []         # Platzhalter ohne Spalte
        self._key = None                      # woraus ``table`` stammt
        self._stamp = None                    # Änderungszeit der Datei beim Lesen
        self._current = 0                     # Vorschau-Zeile

        self.section("Quelle")
        self.table_button = QPushButton("TABELLE …")
        self.table_button.setToolTip("CSV- oder Excel-Datei (.xlsx) – erste Zeile = Spaltennamen")
        self.numbering_button = QPushButton("NUMMERIERUNG")
        self.numbering_button.setToolTip("Zahlen ohne Datei: Spalte „Nummer“")
        for button in (self.table_button, self.numbering_button):   # volle Breite: lange Texte
            self.layout_.addWidget(button)
        self.source_label = QLabel(NO_SERIES)
        self.source_label.setWordWrap(True)
        self.layout_.addWidget(self.source_label)
        self.sheet = QComboBox()
        self.sheet.setToolTip("Blatt der Excel-Datei")
        self.layout_.addWidget(self.sheet)
        self.numbering_box = QWidget()
        grid = QGridLayout(self.numbering_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)
        self.start = self._spin(-MAX_NUMBER, MAX_NUMBER, "Erste Zahl")
        self.step = self._spin(-MAX_NUMBER, MAX_NUMBER, "Abstand zur nächsten Zahl (nicht 0)")
        self.count = self._spin(1, MAX_SERIES_ROWS, "Wie viele Etiketten")
        self.digits = self._spin(0, MAX_DIGITS, "Mit Nullen auf so viele Stellen auffüllen (0 = nicht)")
        for line, (title, box) in enumerate((("Start", self.start), ("Schritt", self.step),
                                             ("Anzahl", self.count), ("Stellen", self.digits))):
            grid.addWidget(QLabel(title), line, 0)
            grid.addWidget(box, line, 1)
        self.layout_.addWidget(self.numbering_box)
        self.remove_button = QPushButton("ENTFERNEN")
        self.remove_button.setToolTip("Serie aus dem Etikett nehmen (Platzhalter bleiben stehen)")
        self.layout_.addWidget(self.remove_button)
        self.error_label = QLabel()
        self.error_label.setObjectName("hint")
        self.error_label.setWordWrap(True)
        self.layout_.addWidget(self.error_label)

        self.section("Spalten")
        self.columns = QListWidget()
        self.columns.setToolTip("Doppelklick: als {Spalte} ins gewählte Textobjekt bzw. als neuer Text")
        self.columns.setFixedHeight(90)
        self.layout_.addWidget(self.columns)

        self.section("Zeilen")
        self.rows = QTableWidget(0, 0)
        self.rows.setFixedHeight(ROWS_HEIGHT)
        self.rows.verticalHeader().setVisible(False)
        self.rows.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rows.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rows.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.rows.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rows.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.layout_.addWidget(self.rows)
        row = QHBoxLayout()
        self.all_button = QPushButton("ALLE")
        self.none_button = QPushButton("KEINE")
        row.addWidget(self.all_button)
        row.addWidget(self.none_button)
        self.layout_.addLayout(row)
        self.count_label = QLabel()
        self.layout_.addWidget(self.count_label)

        self.section("Vorschau")
        row = QHBoxLayout()
        self.prev_button = QToolButton()
        self.prev_button.setText("◀")
        self.prev_button.setToolTip("Vorige Zeile auf der Arbeitsfläche")
        self.row_label = QLabel()
        self.row_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QToolButton()
        self.next_button.setText("▶")
        self.next_button.setToolTip("Nächste Zeile auf der Arbeitsfläche")
        row.addWidget(self.prev_button)
        row.addWidget(self.row_label, 1)
        row.addWidget(self.next_button)
        self.layout_.addLayout(row)

        self.section("Schnitt")
        self.cut = QComboBox()
        for mode in CUTS:
            self.cut.addItem(CUT_TITLES[mode], mode)
        self.cut.setToolTip("Beim Drucken der Serie: nach jedem Etikett schneiden oder nur am Ende "
                            "(Endlosband: zwischen den Etiketten bleiben einige mm Vorschub, "
                            "ohne Trennmarke)")
        self.layout_.addWidget(self.cut)
        self.layout_.addStretch()

        self.table_button.clicked.connect(self.table_requested)
        self.numbering_button.clicked.connect(self._start_numbering)
        self.remove_button.clicked.connect(self._remove)
        self.sheet.currentIndexChanged.connect(self._choose_sheet)
        for box in (self.start, self.step, self.count, self.digits):
            box.valueChanged.connect(self._apply_numbering)
        # Doppelklick bzw. Enter (je nach Stil auch Einfachklick) – nur dieses Signal, sonst doppelt
        self.columns.itemActivated.connect(lambda item: self.insert_column.emit(item.text()))
        self.rows.itemChanged.connect(lambda _item: self._update_count())
        self.rows.currentCellChanged.connect(lambda row, *_: self._go_to(row))
        self.all_button.clicked.connect(lambda: self._check_all(True))
        self.none_button.clicked.connect(lambda: self._check_all(False))
        self.prev_button.clicked.connect(lambda: self._go_to(self._current - 1))
        self.next_button.clicked.connect(lambda: self._go_to(self._current + 1))
        self.cut.currentIndexChanged.connect(self._apply_cut)
        self.refresh()

    @staticmethod
    def _spin(low: int, high: int, tip: str) -> SpinBox:
        box = SpinBox()
        box.setRange(low, high)
        box.setToolTip(tip)
        box.setKeyboardTracking(False)          # erst bei Enter/Verlassen: ein Rückgängig-Schritt
        return box

    # --- Stand aus dem Dokument -------------------------------------------------------------
    def refresh(self) -> None:
        """Felder aus ``doc.series``; die Tabelle nur neu lesen, wenn sich Quelle, Blatt,
        Nummerierung oder die Datei geändert haben."""
        value = self.doc.series
        widgets = (self.sheet, self.start, self.step, self.count, self.digits, self.cut)
        for w in widgets:
            w.blockSignals(True)
        self._field_error = None                     # Felder zeigen wieder den gültigen Stand
        key = _key(value)
        if key != self._key:
            self._key = key
            self._load(value)
        if value is None:
            self.source_label.setText(NO_SERIES)
            self.source_label.setToolTip("")
        elif value.numbering is not None:
            self.source_label.setText(NUMBERING)
            self.source_label.setToolTip("")
            n = value.numbering
            for box, v in ((self.start, n.start), (self.step, n.step), (self.count, n.count),
                           (self.digits, n.digits)):
                box.setValue(v)
        else:
            self.source_label.setText(Path(value.source).name)
            self.source_label.setToolTip(value.source)
        self.numbering_box.setVisible(value is not None and value.numbering is not None)
        self.remove_button.setEnabled(value is not None)
        self.cut.setCurrentIndex(self.cut.findData(value.cut if value is not None else "each"))
        self.cut.setEnabled(value is not None)
        for w in widgets:
            w.blockSignals(False)
        self._show_error()

    def reload(self) -> None:
        """Tabelle neu lesen (Öffnen): Häkchen alle gesetzt, erste Zeile in der Vorschau."""
        self._key = object()
        self.refresh()

    def check_file(self) -> bool:
        """Tabellendatei seit dem Lesen geändert? Dann neu lesen (Häkchen neu) – True."""
        value = self.doc.series
        if value is None or value.source is None or _stamp(value.source) == self._stamp:
            return False
        self.reload()
        return True

    def _load(self, value: Series | None, table: Table | None = None) -> None:
        """Tabelle lesen (``table``: schon gelesen) und anzeigen; Blätter auch, wenn das
        gewählte fehlt – dann lässt sich ein anderes wählen."""
        self.table, self.error = table, None
        sheets: list[str] = []
        if value is not None:
            self._stamp = _stamp(value.source) if value.source is not None else None
            if value.source is not None:
                try:
                    sheets = series.sheet_names(value.source)
                except SeriesError:
                    sheets = []
            if table is None:
                try:
                    self.table = series.table_for(value)
                except SeriesError as e:
                    self.error = str(e)
        self.sheet.clear()
        self.sheet.addItems(sheets)
        if sheets:
            self.sheet.setCurrentIndex(max(0, sheets.index(value.sheet)) if value.sheet in sheets
                                       else 0)
        self.sheet.setVisible(bool(sheets))
        self._fill_lists()

    def _fill_lists(self) -> None:
        table = self.table
        self.columns.clear()
        self.rows.blockSignals(True)
        self.rows.clear()
        shown = table.columns[:SHOWN_COLUMNS] if table is not None else []
        self.rows.setColumnCount(len(shown))
        self.rows.setHorizontalHeaderLabels(shown)
        self.rows.setRowCount(len(table.rows) if table is not None else 0)
        if table is not None:
            self.columns.addItems(table.columns)
            for r, values in enumerate(table.rows):
                for c in range(len(shown)):
                    item = QTableWidgetItem(values[c])
                    if c == 0:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        item.setCheckState(Qt.CheckState.Checked)
                    self.rows.setItem(r, c, item)
        self.rows.blockSignals(False)
        self._current = 0
        self._update_count()
        self._update_row_label()

    # --- Abfragen des Hauptfensters --------------------------------------------------------------
    def current_row(self) -> int:
        """Vorschau-Zeile (ab 1)."""
        return self._current + 1

    def preview(self) -> tuple[list[str], list[str]] | None:
        """(Spalten, Zeile) für die Arbeitsfläche – None ohne Serie oder ohne Zeilen."""
        if self.doc.series is None or self.table is None or not self.table.rows:
            return None
        return self.table.columns, self.table.rows[min(self._current, len(self.table.rows) - 1)]

    def checked_rows(self) -> list[tuple[int, list[str]]]:
        """Gewählte Zeilen als (Nummer ab 1, Werte)."""
        if self.table is None:
            return []
        return [(r + 1, values) for r, values in enumerate(self.table.rows)
                if self.rows.item(r, 0) is None
                or self.rows.item(r, 0).checkState() == Qt.CheckState.Checked]

    def show_missing(self, names: list[str]) -> None:
        """Platzhalter ohne Spalte anzeigen (nach jedem Rendern)."""
        if names != self._missing:
            self._missing = names
            self._show_error()

    def _show_error(self) -> None:
        lines = []
        if self.doc.series is not None and self.error:
            lines.append(self.error)
        if self.doc.series is not None and self._field_error:
            lines.append(self._field_error)
        if self.doc.series is not None and self.table is not None and self._missing:
            lines.append("Unbekannte Spalte: " + ", ".join(self._missing))
        self.error_label.setText("\n".join(lines))
        self.error_label.setVisible(bool(lines))

    # --- Änderungen ----------------------------------------------------------------------------
    def set_series(self, value: Series | None, table: Table | None = None) -> None:
        """Serie setzen (ein Rückgängig-Schritt) und anzeigen; ``table``: schon gelesen."""
        self.doc.series = value
        if table is not None:
            self._key = _key(value)
            self._load(value, table)
        self.refresh()
        self.changed.emit()
        self.edited.emit()

    def _start_numbering(self) -> None:
        cut = self.doc.series.cut if self.doc.series is not None else "each"
        self.set_series(Series(numbering=Numbering(), cut=cut))

    def _remove(self) -> None:
        self.set_series(None)

    def _choose_sheet(self) -> None:
        if self.doc.series is not None and self.doc.series.source is not None:
            self.set_series(replace(self.doc.series, sheet=self.sheet.currentText() or None))

    def _apply_numbering(self) -> None:
        value = self.doc.series
        if value is None or value.numbering is None:
            return
        numbering = Numbering(self.start.value(), self.step.value(), self.count.value(),
                              self.digits.value())
        try:
            series.check_numbering(numbering)    # ungültig: nicht übernehmen, Hinweis zeigen
        except SeriesError as e:
            self._field_error = str(e)
            self._show_error()
            return
        self._field_error = None
        self.set_series(replace(value, numbering=numbering))

    def _apply_cut(self) -> None:
        if self.doc.series is not None:
            self.set_series(replace(self.doc.series, cut=self.cut.currentData()))

    def _check_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.rows.blockSignals(True)
        for r in range(self.rows.rowCount()):
            self.rows.item(r, 0).setCheckState(state)
        self.rows.blockSignals(False)
        self._update_count()

    def _go_to(self, row: int) -> None:
        total = len(self.table.rows) if self.table is not None else 0
        if not 0 <= row < total or row == self._current:
            return
        self._current = row
        self._update_row_label()
        self.changed.emit()                  # Arbeitsfläche zeigt die Zeile (kein Rückgängig-Schritt)

    def _update_count(self) -> None:
        total = self.rows.rowCount()
        self.count_label.setText(f"{len(self.checked_rows())} von {total} gewählt" if total else "")

    def _update_row_label(self) -> None:
        total = len(self.table.rows) if self.table is not None else 0
        if total and self.rows.currentRow() != self._current:   # Vorschau-Zeile in der Tabelle zeigen
            self.rows.blockSignals(True)
            self.rows.setCurrentCell(self._current, 0)
            self.rows.blockSignals(False)
        self.row_label.setText(f"Zeile {self._current + 1}/{total}" if total else "")
        self.prev_button.setEnabled(self._current > 0)
        self.next_button.setEnabled(self._current < total - 1)


def _key(value: Series | None):
    """Woraus die Tabelle stammt (Schnitt zählt nicht)."""
    return None if value is None else (value.source, value.sheet, value.numbering)


def _stamp(source: str):
    """Änderungszeit der Tabellendatei (fehlt → eigener Wert)."""
    try:
        return os.stat(source).st_mtime_ns
    except (OSError, ValueError):
        return "fehlt"
