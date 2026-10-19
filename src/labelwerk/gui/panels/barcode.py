"""Panel „Barcode“: Strichcodes und QR-Codes einfügen und den gewählten einstellen.

Art (QR, Code 128, Code 39, EAN-13, EAN-8), Inhalt (jede Eingabe sofort, eine Bearbeitung = ein
Rückgängig-Schritt), Modulbreite in ganzen Druckpunkten (angezeigt in mm), Höhe und Klartext
(Strichcodes), Fehlerkorrektur (QR), Drehen (Aktionen wie im Reiter Layout) und der Bereich
„Position“. Kodieren und Prüfen macht der Kern (``barcodes``); Einfügen und Rahmenfelder führt
das Hauptfenster aus.
"""
from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QValidator
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QToolButton, QWidget)

from ... import barcodes, series
from ...document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, MAX_MODULE, BarcodeObject,
                         Document)
from ...labels import DPI
from ...layout import Rect
from ..symbols import SIZE, line_icon
from ..widgets import DoubleSpinBox, SpinBox
from . import Panel
from .position import PositionSection

HINT = "Barcode oder QR-Code einfügen – Art wählen, Inhalt eintippen"
LEVELS = (("L", "L – 7 %"), ("M", "M – 15 %"), ("Q", "Q – 25 %"), ("H", "H – 30 %"))
MM_PER_DOT = 25.4 / DPI
_NUMBER = re.compile(r"\d*[.,]?\d*")
_ROTATE = (("rotate_left", "object.rotate_left", "rotate-left"),     # (Attribut, Aktion, Symbol)
           ("rotate_right", "object.rotate_right", "rotate-right"))


def _mm(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


class ModuleSpin(SpinBox):
    """Modulbreite in ganzen Druckpunkten, angezeigt und eingegeben in mm („0.25 mm“ wie die
    anderen Zahlenfelder; ein Komma geht auch)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(1, MAX_MODULE)
        self.setSuffix(" mm")

    def textFromValue(self, value: int) -> str:
        return f"{value * MM_PER_DOT:.2f}"

    def _dots(self, text: str) -> int | None:
        """Getippte mm → Druckpunkte; None, wenn (noch) keine gültige Zahl."""
        core = text.removesuffix(self.suffix()).strip().replace(",", ".")
        if not _NUMBER.fullmatch(core) or core in ("", "."):
            return None
        mm = float(core)
        return round(mm / MM_PER_DOT) if math.isfinite(mm) else None

    def valueFromText(self, text: str) -> int:
        dots = self._dots(text)
        return self.value() if dots is None else min(max(dots, 1), MAX_MODULE)

    def validate(self, text: str, pos: int):
        """Nur Ziffern mit einem Komma/Punkt; außerhalb 1–``MAX_MODULE`` Punkte unfertig (wird
        nicht übernommen)."""
        core = text.removesuffix(self.suffix()).strip()
        if not _NUMBER.fullmatch(core.replace(",", ".")):
            return QValidator.State.Invalid, text, pos
        dots = self._dots(text)
        if dots is None or not 1 <= dots <= MAX_MODULE:
            return QValidator.State.Intermediate, text, pos
        return QValidator.State.Acceptable, text, pos


class _KeepUndo(QObject):
    """Strg+Z/Strg+Umschalt+Z im Inhaltsfeld gehören dem Etikett (ein Schritt je Bearbeitung),
    nicht dem eigenen Rückgängig des Felds."""

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.ShortcutOverride and (
                event.matches(QKeySequence.StandardKey.Undo)
                or event.matches(QKeySequence.StandardKey.Redo)):
            event.ignore()
            return True
        return False


class BarcodePanel(Panel):
    frame_edited = Signal(str, float)   # Feld im Bereich „Position“ ("x" | "y" | "w" | "h"), mm

    def __init__(self, doc: Document):
        super().__init__(doc, "Barcode")
        self.index: int | None = None   # bearbeiteter Barcode; None = keiner ausgewählt
        # Serie: Barcode mit dem Wert der Vorschau-Zeile (Hauptfenster), für den Prüfhinweis
        self.fill_preview: Callable[[BarcodeObject], BarcodeObject] | None = None
        self._updating = False
        self._typing = False            # Inhalt wird gerade getippt (ein Rückgängig-Schritt)

        self.hint = QLabel(HINT)
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.layout_.addWidget(self.hint)

        self.section("Art")
        self.kind = QComboBox()
        for kind in BARCODE_KINDS:
            self.kind.addItem(barcodes.TITLES[kind], kind)
        self.kind.setToolTip("Art des Barcodes – für den gewählten bzw. den nächsten")
        self.layout_.addWidget(self.kind)
        self.insert = QPushButton("BARCODE EINFÜGEN")
        self.insert.setToolTip("Barcode der gewählten Art einfügen")
        self.layout_.addWidget(self.insert)

        self.section("Inhalt")
        self.data = QLineEdit()
        self.data.setMaxLength(MAX_BARCODE_DATA)
        self._keep_undo = _KeepUndo(self)
        self.data.installEventFilter(self._keep_undo)
        self.data.setToolTip("Inhalt des Codes; {Spalte} füllt die Serie")
        self.layout_.addWidget(self.data)
        self.check = QLabel()
        self.check.setObjectName("hint")
        self.check.setWordWrap(True)
        self.check.setTextFormat(Qt.TextFormat.PlainText)
        self.layout_.addWidget(self.check)

        self.section("Größe")
        self.size_box = QWidget()
        grid = QGridLayout(self.size_box)
        grid.setContentsMargins(0, 0, 0, 0)
        self.module = ModuleSpin()
        self.module.setKeyboardTracking(False)
        self.module.setToolTip("Breite des schmalsten Strichs bzw. eines QR-Quadrats – in ganzen "
                               "Druckpunkten (0,085 mm), damit der Code lesbar bleibt")
        self.height = DoubleSpinBox()
        self.height.setSuffix(" mm")
        self.height.setDecimals(1)
        self.height.setSingleStep(0.5)
        self.height.setRange(*BARCODE_MM)
        self.height.setKeyboardTracking(False)
        self.height.setToolTip("Höhe samt Klartext")
        self.error = QComboBox()
        for level, title in LEVELS:
            self.error.addItem(title, level)
        self.error.setToolTip("Fehlerkorrektur: höher = lesbar trotz Schmutz/Kratzern, aber größer")
        self.module_label, self.height_label = QLabel("Modul"), QLabel("Höhe")
        self.error_label = QLabel("Fehlerkorrektur")
        for row, (label, widget) in enumerate(((self.module_label, self.module),
                                               (self.height_label, self.height),
                                               (self.error_label, self.error))):
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(1, 1)
        self.layout_.addWidget(self.size_box)
        self.text = QCheckBox("Klartext")
        self.text.setToolTip("Inhalt unter dem Strichcode lesbar drucken")
        self.layout_.addWidget(self.text)
        self.quiet = QLabel()
        self.quiet.setObjectName("hint")
        self.quiet.setWordWrap(True)
        self.layout_.addWidget(self.quiet)

        self.section("Drehen")
        row = QHBoxLayout()
        row.setSpacing(4)
        for attr, _, _ in _ROTATE:
            button = QToolButton()
            button.setObjectName("layoutButton")
            button.setAutoRaise(True)
            button.setIconSize(SIZE)
            setattr(self, attr, button)
            row.addWidget(button)
        row.addStretch()
        self.layout_.addLayout(row)
        self.set_icon_style(True)

        self.section("Position (mm)")
        self.position = PositionSection()
        self.position.edited.connect(self._frame_changed)
        self.layout_.addWidget(self.position)
        self.layout_.addStretch()

        self.refresh()
        step = self._step               # jede Einstellung ein eigener Rückgängig-Schritt
        self.kind.activated.connect(self._kind_chosen)
        self.data.textEdited.connect(self._data_edited)
        self.data.editingFinished.connect(self._data_finished)
        self.module.valueChanged.connect(lambda v: step(self._set, module=v))
        self.height.valueChanged.connect(lambda v: step(self._set, h_mm=round(v, 3)))
        self.text.clicked.connect(lambda on: step(self._set, text=on))
        self.error.activated.connect(lambda _: step(self._set, error=self.error.currentData()))

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """„Barcode einfügen“ und Drehen lösen ihre Aktionen aus (Kürzel im Tooltip); die Art
        zum Einfügen liest das Hauptfenster aus ``chosen_kind``."""
        insert = actions["barcode.insert"]
        self.insert.clicked.connect(lambda _=False: insert.trigger())
        self.insert.setToolTip(insert.toolTip())
        insert.changed.connect(lambda: self.insert.setToolTip(insert.toolTip()))
        for attr, key, _ in _ROTATE:
            button, rotate = getattr(self, attr), actions[key]
            button.clicked.connect(lambda _=False, a=rotate: a.trigger())
            button.setToolTip(rotate.toolTip())
            rotate.changed.connect(lambda b=button, a=rotate: b.setToolTip(a.toolTip()))

    def set_icon_style(self, dark_checked: bool) -> None:
        for attr, _, icon in _ROTATE:
            getattr(self, attr).setIcon(line_icon(icon, dark_checked, hover=True))

    @property
    def obj(self) -> BarcodeObject:
        return self.doc.objects[self.index]

    def chosen_kind(self) -> str:
        """Art aus der Auswahl (für „Barcode einfügen“)."""
        return self.kind.currentData()

    def set_object(self, index: int | None) -> None:
        """Barcode bearbeiten (Index in ``doc.objects``) bzw. mit None keinen."""
        if index != self.index:
            self.index = index
            self.refresh()

    def focus_data(self) -> None:
        """Inhalt markiert in den Fokus (nach dem Einfügen, Doppelklick): Tippen ersetzt ihn."""
        self.data.setFocus()
        self.data.selectAll()

    def _settings_widgets(self):
        return (self.data, self.size_box, self.text, self.rotate_left, self.rotate_right,
                self.position)

    # --- Modell → Panel -----------------------------------------------------
    def refresh(self) -> None:
        if self.index is not None and not (0 <= self.index < len(self.doc.objects)
                                           and isinstance(self.obj, BarcodeObject)):
            self.index = None                      # Objekt gibt es nicht mehr (Rückgängig …)
        selected = self.index is not None
        self.hint.setVisible(not selected)
        for widget in self._settings_widgets():
            widget.setEnabled(selected)
        self._updating = True
        self._typing = False
        try:
            kind = self.chosen_kind()
            obj = self.obj if selected else BarcodeObject(
                kind=kind, data=barcodes.SAMPLES[kind], module=barcodes.INSERT_MODULE.get(kind, 3))
            if selected:
                self.kind.setCurrentIndex(self.kind.findData(obj.kind))
            if self.data.text() != obj.data:
                self.data.setText(obj.data)
            self.module.setValue(obj.module)
            self.height.setValue(obj.h_mm)
            self.text.setChecked(obj.text)
            self.error.setCurrentIndex(self.error.findData(obj.error))
            qr = obj.kind == "qr"
            for widget in (self.height_label, self.height, self.text):
                widget.setVisible(not qr)
            for widget in (self.error_label, self.error):
                widget.setVisible(qr)
            if not selected:
                self._set_check("")
                self.quiet.setText("")
                self.show_frame(None)
                return
            self._show_check()
        finally:
            self._updating = False

    def update_check(self) -> None:
        """Prüfhinweis neu (z. B. andere Vorschau-Zeile der Serie)."""
        if self.index is not None and 0 <= self.index < len(self.doc.objects) \
                and isinstance(self.obj, BarcodeObject):
            self._show_check()

    def _show_check(self) -> None:
        """Fehler des Inhalts bzw. Hinweise (ergänzte Prüfziffer, Ruhezone) – mit Platzhaltern
        in einer Serie für den Wert der Vorschau-Zeile."""
        obj = self.obj
        if self.fill_preview is not None and series.placeholders(Document(objects=[obj])):
            obj = self.fill_preview(obj)
        try:
            barcodes.size(obj)
            code = barcodes.check(obj)
        except barcodes.BarcodeError as e:
            self._set_check(str(e))
        else:
            completed = code.readable if obj.kind in ("ean13", "ean8") else ""
            given = "".join(obj.data.split())
            self._set_check(f"Mit Prüfziffer: {completed}" if completed and completed != given
                            else "")
        side = "ringsum" if obj.kind == "qr" else "links und rechts je"
        self.quiet.setText(f"Ruhezone: {side} {_mm(barcodes.quiet_mm(obj))} mm frei lassen")

    def _set_check(self, text: str) -> None:
        self.check.setText(text)
        self.check.setVisible(bool(text))           # leer: kein leerer Hinweis-Kasten

    def show_frame(self, rect: Rect | None) -> None:
        """Rahmen des Barcodes in mm anzeigen (vom Hauptfenster nach dem Rendern)."""
        self.position.show_frame(rect, editable_size=True)

    # --- Panel → Modell -----------------------------------------------------
    def _step(self, change, *args, **kwargs) -> None:
        """Änderung als eigener Rückgängig-Schritt (vorher Offenes festhalten, danach das Neue)."""
        if self._updating or self.index is None:
            return
        self.edited.emit()
        change(*args, **kwargs)
        self.edited.emit()

    def _change(self, change) -> None:
        self.doc.objects[self.index] = change(self.obj)
        self.refresh()
        self.changed.emit()

    def _set(self, **values) -> None:
        self._change(lambda obj: replace(obj, **values))

    def _kind_chosen(self) -> None:
        """Art gewählt: für den gewählten Barcode (ein Schritt) bzw. für den nächsten."""
        if self.index is None:
            self.refresh()
        else:
            self._step(self._change, self._with_kind)

    def _with_kind(self, obj: BarcodeObject) -> BarcodeObject:
        """Neue Art: Beispielinhalt der alten wird der der neuen; zwischen QR und Strichcode die
        übliche Modulbreite der neuen Art."""
        kind = self.chosen_kind()
        data = barcodes.SAMPLES[kind] if obj.data == barcodes.SAMPLES[obj.kind] else obj.data
        module = obj.module
        if (kind == "qr") != (obj.kind == "qr"):
            module = barcodes.INSERT_MODULE.get(kind, 3)
        return replace(obj, kind=kind, data=data, module=module)

    def _data_edited(self, text: str) -> None:
        """Getippt: sofort aufs Etikett; der erste Anschlag hält den Stand davor fest, das Ende
        der Bearbeitung (Enter, Fokus weg) den neuen – zusammen ein Schritt."""
        if self._updating or self.index is None:
            return
        if not self._typing:
            self.edited.emit()
            self._typing = True
        self.doc.objects[self.index] = replace(self.obj, data=text)
        self._show_check()
        self.changed.emit()

    def _data_finished(self) -> None:
        if self._typing:
            self._typing = False
            self.edited.emit()

    def _frame_changed(self, key: str, value: float) -> None:
        if self.index is not None:
            self.frame_edited.emit(key, value)
