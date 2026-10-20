"""Panel “Barcode”: insert barcodes and QR codes and adjust the selected one.

Kind (QR, Code 128, Code 39, EAN-13, EAN-8), content (every input immediately, one edit = one
undo step), module width in whole dots (shown in mm), height and human-readable text
(barcodes), error correction (QR), rotate (actions as in the Layout tab) and the area
“Position”. Encoding and checking is done by the core (``barcodes``); inserting and frame
fields are handled by the main window.
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
from ...document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, BarcodeObject,
                         Document)
from ... import i18n
from ...i18n import N_, _
from ...labels import DPI
from ...layout import Rect
from ..symbols import SIZE, line_icon
from ..widgets import DoubleSpinBox, SpinBox
from . import Panel
from .position import PositionSection

HINT = N_("Insert a barcode or QR code – choose the type, type the content")
LEVELS = (("L", N_("L – 7%")), ("M", N_("M – 15%")), ("Q", N_("Q – 25%")), ("H", N_("H – 30%")))
_NUMBER = re.compile(r"\d*[.,]?\d*")
_ROTATE = (("rotate_left", "object.rotate_left", "rotate-left"),     # (attribute, action, icon)
           ("rotate_right", "object.rotate_right", "rotate-right"))


def _mm(value: float) -> str:
    return i18n.number(value, 1)


class ModuleSpin(SpinBox):
    """Module width in whole dots, shown and entered in mm (“0.25 mm” like the
    other number fields; a comma works too)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dpi = DPI                  # resolution of the label: one dot is 25.4/dpi mm
        self.setRange(1, barcodes.max_module(DPI))
        self.setSuffix(" mm")

    def set_dpi(self, dpi: int) -> None:
        """Resolution changed: the same number of dots shows a different width in mm."""
        if dpi != self.dpi:
            self.dpi = dpi
            self.setMaximum(max(barcodes.max_module(dpi), self.value()))
            self.lineEdit().setText(self.textFromValue(self.value()) + self.suffix())

    def textFromValue(self, value: int) -> str:
        return i18n.number(value * 25.4 / self.dpi, 2)

    def _dots(self, text: str) -> int | None:
        """Typed mm → dots; None if (not yet) a valid number."""
        core = text.removesuffix(self.suffix()).strip().replace(",", ".")
        if not _NUMBER.fullmatch(core) or core in ("", "."):
            return None
        mm = float(core)
        return round(mm * self.dpi / 25.4) if math.isfinite(mm) else None

    def valueFromText(self, text: str) -> int:
        dots = self._dots(text)
        return self.value() if dots is None else min(max(dots, 1), self.maximum())

    def validate(self, text: str, pos: int):
        """Only digits with one comma/dot; outside 1–``maximum()`` dots unfinished (is
        not accepted)."""
        core = text.removesuffix(self.suffix()).strip()
        if not _NUMBER.fullmatch(core.replace(",", ".")):
            return QValidator.State.Invalid, text, pos
        dots = self._dots(text)
        if dots is None or not 1 <= dots <= self.maximum():
            return QValidator.State.Intermediate, text, pos
        return QValidator.State.Acceptable, text, pos


class _KeepUndo(QObject):
    """Ctrl+Z/Ctrl+Shift+Z in the content field belong to the label (one step per edit),
    not to the field's own undo."""

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.ShortcutOverride and (
                event.matches(QKeySequence.StandardKey.Undo)
                or event.matches(QKeySequence.StandardKey.Redo)):
            event.ignore()
            return True
        return False


class BarcodePanel(Panel):
    frame_edited = Signal(str, float)   # field in the "Position" section ("x" | "y" | "w" | "h"), mm

    def __init__(self, doc: Document):
        super().__init__(doc, _("Barcode"))
        self.index: int | None = None   # barcode being edited; None = none selected
        # Series: barcode with the value of the preview row (main window), for the check hint
        self.fill_preview: Callable[[BarcodeObject], BarcodeObject] | None = None
        self.red_available = False      # label and printer can do red (hint only then)
        self._updating = False
        self._typing = False            # content is being typed (one undo step)

        self.hint = QLabel(_(HINT))
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.layout_.addWidget(self.hint)

        self.section(_("Type"))
        self.kind = QComboBox()
        for kind in BARCODE_KINDS:
            self.kind.addItem(_(barcodes.TITLES[kind]), kind)
        self.kind.setToolTip(_("Type of barcode – for the selected one or the next one"))
        self.layout_.addWidget(self.kind)
        self.insert = QPushButton(_("INSERT BARCODE"))
        self.insert.setToolTip(_("Insert a barcode of the chosen type"))
        self.layout_.addWidget(self.insert)

        self.section(_("Content"))
        self.data = QLineEdit()
        self.data.setMaxLength(MAX_BARCODE_DATA)
        self._keep_undo = _KeepUndo(self)
        self.data.installEventFilter(self._keep_undo)
        self.data.setToolTip(_("Content of the code; {{column}} is filled by the series").format())
        self.layout_.addWidget(self.data)
        self.check = QLabel()
        self.check.setObjectName("hint")
        self.check.setWordWrap(True)
        self.check.setTextFormat(Qt.TextFormat.PlainText)
        self.layout_.addWidget(self.check)

        self.section(_("Size"))
        self.size_box = QWidget()
        grid = QGridLayout(self.size_box)
        grid.setContentsMargins(0, 0, 0, 0)
        self.module = ModuleSpin()
        self.module.setKeyboardTracking(False)
        self.module.setToolTip(_("Width of the narrowest bar or of one QR square – in whole dots "
                                 "(0.085 mm), so the code stays readable"))
        self.height = DoubleSpinBox()
        self.height.setSuffix(" mm")
        self.height.setDecimals(1)
        self.height.setSingleStep(0.5)
        self.height.setRange(*BARCODE_MM)
        self.height.setKeyboardTracking(False)
        self.height.setToolTip(_("Height including the human-readable text"))
        self.error = QComboBox()
        for level, title in LEVELS:
            self.error.addItem(_(title), level)
        self.error.setToolTip(_("Error correction: higher = readable despite dirt/scratches, but larger"))
        self.module_label, self.height_label = QLabel(_("Module")), QLabel(_("Height"))
        self.error_label = QLabel(_("Error correction"))
        for row, (label, widget) in enumerate(((self.module_label, self.module),
                                               (self.height_label, self.height),
                                               (self.error_label, self.error))):
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(1, 1)
        self.layout_.addWidget(self.size_box)
        self.text = QCheckBox(_("Human-readable text"))
        self.text.setToolTip(_("Print the content readable below the barcode"))
        self.layout_.addWidget(self.text)
        self.quiet = QLabel()
        self.quiet.setObjectName("hint")
        self.quiet.setWordWrap(True)
        self.layout_.addWidget(self.quiet)

        self.section(_("Rotate"))
        row = QHBoxLayout()
        row.setSpacing(4)
        for attr, __, ___ in _ROTATE:
            button = QToolButton()
            button.setObjectName("layoutButton")
            button.setAutoRaise(True)
            button.setIconSize(SIZE)
            setattr(self, attr, button)
            row.addWidget(button)
        row.addStretch()
        self.layout_.addLayout(row)
        self.set_icon_style(True)

        self.section(_("Position (mm)"))
        self.position = PositionSection()
        self.position.edited.connect(self._frame_changed)
        self.layout_.addWidget(self.position)
        self.layout_.addStretch()

        self.refresh()
        step = self._step               # every setting is its own undo step
        self.kind.activated.connect(self._kind_chosen)
        self.data.textEdited.connect(self._data_edited)
        self.data.editingFinished.connect(self._data_finished)
        self.module.valueChanged.connect(lambda v: step(self._set, module=v))
        self.height.valueChanged.connect(lambda v: step(self._set, h_mm=round(v, 3)))
        self.text.clicked.connect(lambda on: step(self._set, text=on))
        self.error.activated.connect(lambda _index: step(self._set, error=self.error.currentData()))

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """“Insert barcode” and rotate trigger their actions (shortcut in the tooltip); the kind
        for inserting is read by the main window from ``chosen_kind``."""
        insert = actions["barcode.insert"]
        self.insert.clicked.connect(lambda _checked=False: insert.trigger())
        self.insert.setToolTip(insert.toolTip())
        insert.changed.connect(lambda: self.insert.setToolTip(insert.toolTip()))
        for attr, key, __ in _ROTATE:
            button, rotate = getattr(self, attr), actions[key]
            button.clicked.connect(lambda _checked=False, a=rotate: a.trigger())
            button.setToolTip(rotate.toolTip())
            rotate.changed.connect(lambda b=button, a=rotate: b.setToolTip(a.toolTip()))

    def set_icon_style(self, dark_checked: bool) -> None:
        for attr, __, icon in _ROTATE:
            getattr(self, attr).setIcon(line_icon(icon, dark_checked, hover=True))

    @property
    def obj(self) -> BarcodeObject:
        return self.doc.objects[self.index]

    def chosen_kind(self) -> str:
        """Kind from the selection (for “Insert barcode”)."""
        return self.kind.currentData()

    def set_object(self, index: int | None) -> None:
        """Edit a barcode (index in ``doc.objects``) or none with None."""
        if index != self.index:
            self.index = index
            self.refresh()

    def focus_data(self) -> None:
        """Content selected in focus (after inserting, double-click): typing replaces it."""
        self.data.setFocus()
        self.data.selectAll()

    def _settings_widgets(self):
        return (self.data, self.size_box, self.text, self.rotate_left, self.rotate_right,
                self.position)

    # --- Model → panel -----------------------------------------------------
    def refresh(self) -> None:
        if self.index is not None and not (0 <= self.index < len(self.doc.objects)
                                           and isinstance(self.obj, BarcodeObject)):
            self.index = None                      # object no longer exists (undo …)
        selected = self.index is not None
        self.hint.setVisible(not selected)
        for widget in self._settings_widgets():
            widget.setEnabled(selected)
        self._updating = True
        self._typing = False
        try:
            kind = self.chosen_kind()
            obj = self.obj if selected else BarcodeObject(
                kind=kind, data=barcodes.SAMPLES[kind],
                module=barcodes.insert_module(kind, self.module.dpi))
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
        """Check hint anew (e.g. other preview row of the series)."""
        if self.index is not None and 0 <= self.index < len(self.doc.objects) \
                and isinstance(self.obj, BarcodeObject):
            self._show_check()

    def _show_check(self) -> None:
        """Error of the content or hints (completed check digit, quiet zone) – with placeholders
        in a series for the value of the preview row."""
        obj = self.obj
        if self.fill_preview is not None and series.placeholders(Document(objects=[obj])):
            obj = self.fill_preview(obj)
        try:
            barcodes.size(obj, self.module.dpi)
            code = barcodes.check(obj)
        except barcodes.BarcodeError as e:
            self._set_check(str(e))
        else:
            completed = code.readable if obj.kind in ("ean13", "ean8") else ""
            given = "".join(obj.data.split())
            self._set_check(_("With check digit: {code}").format(code=completed)
                            if completed and completed != given else "")
        quiet = (_("Quiet zone: leave {mm} mm free all around") if obj.kind == "qr"
                 else _("Quiet zone: leave {mm} mm free on the left and right each"))
        text = quiet.format(mm=_mm(barcodes.quiet_mm(obj, self.module.dpi)))
        if obj.color == "red" and self.red_available:
            text += " · " + _("Many scanners read red poorly")
        self.quiet.setText(text)

    def _set_check(self, text: str) -> None:
        self.check.setText(text)
        self.check.setVisible(bool(text))           # empty: no empty hint box

    def show_frame(self, rect: Rect | None) -> None:
        """Show the barcode's frame in mm (from the main window after rendering)."""
        self.position.show_frame(rect, editable_size=True)

    # --- Panel → model -----------------------------------------------------
    def _step(self, change, *args, **kwargs) -> None:
        """Change as its own undo step (record what is open before, the new state after)."""
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
        """Kind chosen: for the selected barcode (one step) or for the next one."""
        if self.index is None:
            self.refresh()
        else:
            self._step(self._change, self._with_kind)

    def _with_kind(self, obj: BarcodeObject) -> BarcodeObject:
        """New kind: sample content of the old becomes that of the new; between QR and barcode the
        usual module width of the new kind."""
        kind = self.chosen_kind()
        data = barcodes.SAMPLES[kind] if obj.data == barcodes.SAMPLES[obj.kind] else obj.data
        module = obj.module
        if (kind == "qr") != (obj.kind == "qr"):
            module = barcodes.insert_module(kind, self.module.dpi)
        return replace(obj, kind=kind, data=data, module=module)

    def _data_edited(self, text: str) -> None:
        """Typed: straight onto the label; the first keystroke records the state before, the end
        of the edit (Enter, focus away) the new one – together one step."""
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
