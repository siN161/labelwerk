"""SERIES panel: table (CSV/Excel) or numbering, columns, rows with checkmarks, preview.

The core reads the table (``series.table_for``); the panel remembers where it came from
(source, sheet, numbering) and rereads only on change – not as a side effect of
undo. ``check_file`` rereads a changed file (before printing), ``reload`` (open) always rereads.
The checkmarks belong to the display, not to the label (after opening, every row is chosen).
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
from ...i18n import N_, _, ngettext
from ...series import SeriesError, Table
from ..widgets import SpinBox
from . import Panel

NO_SERIES = N_("No series")
NUMBERING = N_("Numbering")
CUT_TITLES = {"each": N_("After each label"), "end": N_("Only at the end")}
NO_CUTTER = N_("Printer without cutter – separate the labels by hand")
DRIVER_CUTS = N_("Cutting is set by the printer driver (system printer settings)")
SHOWN_COLUMNS = 3                   # columns in the row table (the checkmarks sit in the first)
ROWS_HEIGHT = 180


class SeriesPanel(Panel):
    table_requested = Signal()          # TABLE … – the main window asks for the file
    insert_column = Signal(str)         # column name → into the label as {Name}
    driver_cut_chosen = Signal(str, str)   # CUPS: driver option for cutting, chosen value

    def __init__(self, doc: Document):
        super().__init__(doc, _("Series"))
        self.table: Table | None = None
        self.error: str | None = None        # table not readable
        self._field_error: str | None = None  # numbering field invalid (not applied)
        self._missing: list[str] = []         # placeholders without a column
        self._key = None                      # where ``table`` came from
        self._stamp = None                    # modification time of the file when read
        self._current = 0                     # preview row

        self.section(_("Source"))
        self.table_button = QPushButton(_("TABLE …"))
        self.table_button.setToolTip(_("CSV or Excel file (.xlsx) – first row = column names"))
        self.numbering_button = QPushButton(_("NUMBERING"))
        self.numbering_button.setToolTip(_("Numbers without a file: column “{column}”").format(
            column=series.number_column()))
        for button in (self.table_button, self.numbering_button):   # full width: long texts
            self.layout_.addWidget(button)
        self.source_label = QLabel(_(NO_SERIES))
        self.source_label.setWordWrap(True)
        self.layout_.addWidget(self.source_label)
        self.sheet = QComboBox()
        self.sheet.setToolTip(_("Sheet of the Excel file"))
        self.layout_.addWidget(self.sheet)
        self.numbering_box = QWidget()
        grid = QGridLayout(self.numbering_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)
        self.start = self._spin(-MAX_NUMBER, MAX_NUMBER, _("First number"))
        self.step = self._spin(-MAX_NUMBER, MAX_NUMBER, _("Step to the next number (not 0)"))
        self.count = self._spin(1, MAX_SERIES_ROWS, _("How many labels"))
        self.digits = self._spin(0, MAX_DIGITS,
                                 _("Pad with zeros to this many digits (0 = no padding)"))
        for line, (title, box) in enumerate(((_("Start"), self.start), (_("Step"), self.step),
                                             (_("Count"), self.count), (_("Digits"), self.digits))):
            grid.addWidget(QLabel(title), line, 0)
            grid.addWidget(box, line, 1)
        self.layout_.addWidget(self.numbering_box)
        self.remove_button = QPushButton(_("REMOVE"))
        self.remove_button.setToolTip(_("Remove the series from the label (placeholders stay)"))
        self.layout_.addWidget(self.remove_button)
        self.error_label = QLabel()
        self.error_label.setObjectName("hint")
        self.error_label.setWordWrap(True)
        self.layout_.addWidget(self.error_label)

        self.section(_("Columns"))
        self.columns = QListWidget()
        self.columns.setToolTip(_("Double-click: as {{column}} into the selected text object or as new "
                                   "text").format())
        self.columns.setFixedHeight(90)
        self.layout_.addWidget(self.columns)

        self.section(_("Rows"))
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
        self.all_button = QPushButton(_("ALL"))
        self.none_button = QPushButton(_("NONE"))
        row.addWidget(self.all_button)
        row.addWidget(self.none_button)
        self.layout_.addLayout(row)
        self.count_label = QLabel()
        self.layout_.addWidget(self.count_label)

        self.section(_("Preview"))
        row = QHBoxLayout()
        self.prev_button = QToolButton()
        self.prev_button.setText("◀")
        self.prev_button.setToolTip(_("Previous row on the canvas"))
        self.row_label = QLabel()
        self.row_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QToolButton()
        self.next_button.setText("▶")
        self.next_button.setToolTip(_("Next row on the canvas"))
        row.addWidget(self.prev_button)
        row.addWidget(self.row_label, 1)
        row.addWidget(self.next_button)
        self.layout_.addLayout(row)

        self.cut_title = self.section(_("Cutting"))
        self.cut = QComboBox()
        for mode in CUTS:
            self.cut.addItem(_(CUT_TITLES[mode]), mode)
        self.cut.setToolTip(_("When printing the series: cut after each label or only at the end "
                              "(continuous tape: a few mm of feed remain between the labels, "
                              "without a separator mark)"))
        self.layout_.addWidget(self.cut)
        self.no_cutter = QLabel(_(NO_CUTTER))
        self.no_cutter.setObjectName("hint")
        self.no_cutter.setWordWrap(True)
        self.no_cutter.hide()
        self.layout_.addWidget(self.no_cutter)
        # Driver options for cutting (printer via CUPS): one choice per option
        self.driver_box = QWidget()
        self.driver_grid = QGridLayout(self.driver_box)
        self.driver_grid.setContentsMargins(0, 0, 0, 0)
        self.driver_grid.setColumnStretch(1, 1)
        self.driver_box.hide()
        self.layout_.addWidget(self.driver_box)
        self.driver_cuts: dict[str, QComboBox] = {}
        self.layout_.addStretch()

        self.table_button.clicked.connect(self.table_requested)
        self.numbering_button.clicked.connect(self._start_numbering)
        self.remove_button.clicked.connect(self._remove)
        self.sheet.currentIndexChanged.connect(self._choose_sheet)
        for box in (self.start, self.step, self.count, self.digits):
            box.valueChanged.connect(self._apply_numbering)
        # Double-click or Enter (depending on the style also single click) – only this signal, otherwise twice
        self.columns.itemActivated.connect(lambda item: self.insert_column.emit(item.text()))
        self.rows.itemChanged.connect(lambda _item: self._update_count())
        self.rows.currentCellChanged.connect(lambda row, *_args: self._go_to(row))
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
        box.setKeyboardTracking(False)          # only on Enter/leaving: one undo step
        return box

    # --- State from the document ------------------------------------------------------------
    def refresh(self) -> None:
        """Fields from ``doc.series``; reread the table only if the source, sheet,
        numbering or the file have changed."""
        value = self.doc.series
        widgets = (self.sheet, self.start, self.step, self.count, self.digits, self.cut)
        for w in widgets:
            w.blockSignals(True)
        self._field_error = None                     # fields show the valid state again
        key = _key(value)
        if key != self._key:
            self._key = key
            self._load(value)
        if value is None:
            self.source_label.setText(_(NO_SERIES))
            self.source_label.setToolTip("")
        elif value.numbering is not None:
            self.source_label.setText(_(NUMBERING))
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
        """Reread the table (open): all checkmarks set, first row in the preview."""
        self._key = object()
        self.refresh()

    def check_file(self) -> bool:
        """Table file changed since reading? Then reread (checkmarks reset) – True."""
        value = self.doc.series
        if value is None or value.source is None or _stamp(value.source) == self._stamp:
            return False
        self.reload()
        return True

    def _load(self, value: Series | None, table: Table | None = None) -> None:
        """Read and show the table (``table``: already read); sheets too, even if the
        chosen one is missing – then another can be chosen."""
        self.table, self.error = table, None
        if value is not None:
            self._stamp = _stamp(value.source) if value.source is not None else None
            if table is None:
                try:
                    self.table = series.table_for(value)
                except SeriesError as e:
                    self.error = str(e)
        # Sheets from the workbook that was read; if reading fails (sheet missing), fetch them separately
        sheets = self.table.sheets if self.table is not None else []
        if self.table is None and value is not None and value.source is not None:
            try:
                sheets = series.sheet_names(value.source)
            except SeriesError:
                sheets = []
        shown = self.table.sheet if self.table is not None else value.sheet if value else None
        self.sheet.blockSignals(True)               # filling is not a choice by the user
        self.sheet.clear()
        self.sheet.addItems(sheets)
        if sheets:
            self.sheet.setCurrentIndex(sheets.index(shown) if shown in sheets else 0)
        self.sheet.blockSignals(False)
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

    # --- Queries from the main window ------------------------------------------------------------
    def current_row(self) -> int:
        """Preview row (from 1)."""
        return self._current + 1

    def preview(self) -> tuple[list[str], list[str]] | None:
        """(Columns, row) for the canvas – None without a series or without rows."""
        if self.doc.series is None or self.table is None or not self.table.rows:
            return None
        return self.table.columns, self.table.rows[min(self._current, len(self.table.rows) - 1)]

    def checked_rows(self) -> list[tuple[int, list[str]]]:
        """Chosen rows as (number from 1, values)."""
        if self.table is None:
            return []
        return [(r + 1, values) for r, values in enumerate(self.table.rows)
                if self.rows.item(r, 0) is None
                or self.rows.item(r, 0).checkState() == Qt.CheckState.Checked]

    def show_missing(self, names: list[str]) -> None:
        """Show placeholders without a column (after every render)."""
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
            lines.append(ngettext("Unknown column: {columns}", "Unknown columns: {columns}",
                                  len(self._missing)).format(columns=", ".join(self._missing)))
        self.error_label.setText("\n".join(lines))
        self.error_label.setVisible(bool(lines))

    # --- Changes -------------------------------------------------------------------------------
    def set_series(self, value: Series | None, table: Table | None = None) -> None:
        """Set the series (one undo step) and show it; ``table``: already read."""
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
            series.check_numbering(numbering)    # invalid: do not apply, show the hint
        except SeriesError as e:
            self._field_error = str(e)
            self._show_error()
            return
        self._field_error = None
        self.set_series(replace(value, numbering=numbering))

    def set_cutter(self, cutter: bool) -> None:
        """Printer with or without cutter: without one there is no cut choice, only the hint."""
        self.cut_title.setVisible(cutter)
        self.cut.setVisible(cutter)
        self.no_cutter.setText(_(NO_CUTTER))
        self.no_cutter.setVisible(not cutter)
        self.driver_box.hide()

    def set_driver_cuts(self, options, chosen: dict[str, str]) -> None:
        """Printer via CUPS or Zebra: instead of “After each label/Only at the end” the cut options
        of its driver or the mode (``cups.CutOption``), chosen as in ``chosen`` (otherwise the
        default); without such options the hint that the driver decides."""
        while self.driver_grid.count():
            self.driver_grid.takeAt(0).widget().deleteLater()
        self.driver_cuts = {}
        for row, option in enumerate(options):
            combo = QComboBox()
            for choice, text in zip(option.choices, option.labels or option.choices):
                combo.addItem(text, choice)          # driver texts stay, Zebra already translated
            combo.setCurrentIndex(max(0, combo.findData(chosen.get(option.key, option.default))))
            combo.currentIndexChanged.connect(
                lambda _unused=0, key=option.key, box=combo: self.driver_cut_chosen.emit(
                    key, box.currentData()))
            self.driver_grid.addWidget(QLabel(option.title), row, 0)
            self.driver_grid.addWidget(combo, row, 1)
            self.driver_cuts[option.key] = combo
        self.cut.hide()
        self.cut_title.setVisible(True)
        self.driver_box.setVisible(bool(options))
        self.no_cutter.setText(_(DRIVER_CUTS))
        self.no_cutter.setVisible(not options)

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
        self.changed.emit()                  # the canvas shows the row (no undo step)

    def _update_count(self) -> None:
        total = self.rows.rowCount()
        self.count_label.setText(_("{checked} of {total} selected").format(
            checked=len(self.checked_rows()), total=total) if total else "")

    def _update_row_label(self) -> None:
        total = len(self.table.rows) if self.table is not None else 0
        if total and self.rows.currentRow() != self._current:   # show the preview row in the table
            self.rows.blockSignals(True)
            self.rows.setCurrentCell(self._current, 0)
            self.rows.blockSignals(False)
        self.row_label.setText(_("Row {row}/{total}").format(row=self._current + 1, total=total)
                                if total else "")
        self.prev_button.setEnabled(self._current > 0)
        self.next_button.setEnabled(self._current < total - 1)


def _key(value: Series | None):
    """Where the table came from (cut does not count)."""
    return None if value is None else (value.source, value.sheet, value.numbering)


def _stamp(source: str):
    """Modification time of the table file (missing → own value)."""
    try:
        return os.stat(source).st_mtime_ns
    except (OSError, ValueError):
        return "fehlt"
