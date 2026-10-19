"""Panel „Bild“: Bilder einfügen (Datei, Zwischenablage, Bildschirmfoto, Symbol) und das
gewählte Bild einstellen.

Umwandlung in Schwarz/Weiß (Strich = harte Schwelle, Foto = Rasterpunkte), Schwelle,
Umkehren, Zuschnitt (automatisch an/aus), Originalgröße 1:1, Seitenverhältnis, Drehen
(Aktionen des Hauptfensters wie im Reiter Layout) und der Bereich „Position“ (``panels.position``, Größe immer änderbar). Gerechnet wird im Kern
(``layout.set_crop`` …); Einfügen und Rahmenfelder führt das Hauptfenster aus.
"""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QPushButton,
                               QRadioButton, QSlider, QToolButton)

from ... import layout
from ...document import Document, ImageObject
from ...files import NOT_WHITE, crop_box, ink_box
from ...i18n import N_, _
from ...layout import Rect
from ...settings import Settings
from ..image_import import is_symbol_source, source_title
from ..symbols import SIZE, line_icon
from ..widgets import SpinBox
from . import Panel
from .position import PositionSection

HINT = N_("Insert an image from a file, the clipboard, as a screenshot or symbol – or drag it "
          "onto the label")
CROP_FAILED = N_("Image not cropped – only white area found")
_SOURCE_PX = 240                    # Quelle: längere Namen in der Mitte gekürzt (Tooltip)
_ROTATE = (("rotate_left", "object.rotate_left", "rotate-left"),     # (Attribut, Aktion, Symbol)
           ("rotate_right", "object.rotate_right", "rotate-right"))


class ImagePanel(Panel):
    frame_edited = Signal(str, float)   # Feld im Bereich „Position“ ("x" | "y" | "w" | "h"), mm
    paste_requested = Signal()          # „Aus Zwischenablage“
    message = Signal(str, str)          # Hinweis für die Statusleiste (Text, Zustand)

    def __init__(self, doc: Document):
        super().__init__(doc, _("Image"))
        self.index: int | None = None   # bearbeitetes Bild; None = keins ausgewählt
        # ohne Auswahl gezeigt: Standard für neue Bilder (set_defaults; vorher der aus Settings)
        self._defaults = (Settings.image_mode, Settings.image_threshold)
        self._updating = False

        self.hint = QLabel(_(HINT))
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.layout_.addWidget(self.hint)

        self.section(_("Insert"))
        self.from_file = QPushButton(_("FROM FILE …"))
        self.from_file.setToolTip(_("Insert an image or PDF page"))
        self.from_clipboard = QPushButton(_("FROM CLIPBOARD"))
        self.from_clipboard.setToolTip(_("Insert an image from the clipboard"))
        self.from_clipboard.setEnabled(False)
        self.from_clipboard.clicked.connect(self.paste_requested)
        self.screenshot = QPushButton(_("SCREENSHOT"))
        self.screenshot.setToolTip(_("Insert a screenshot"))
        self.symbol = QPushButton(_("SYMBOL"))
        self.symbol.setToolTip(_("Insert symbol …"))
        for button in (self.from_file, self.from_clipboard, self.screenshot, self.symbol):
            self.layout_.addWidget(button)

        self.section(_("Source"))
        self.source = QLabel()
        self.source.setObjectName("imageSource")
        self.layout_.addWidget(self.source)

        self.section(_("Conversion"))
        row = QHBoxLayout()
        self.line = QRadioButton(_("Line art"))
        self.line.setToolTip(_("Hard threshold – for codes, text and logos"))
        self.photo = QRadioButton(_("Photo"))
        self.photo.setToolTip(_("Grayscale as halftone dots – for photos and gradients"))
        self.mode_group = QButtonGroup(self)
        for button in (self.line, self.photo):
            self.mode_group.addButton(button)
            row.addWidget(button)
        row.addStretch()
        self.layout_.addLayout(row)
        row = QHBoxLayout()                    # „Schwelle [128]“, darunter der Regler
        self.threshold_label = QLabel(_("Threshold"))
        self.threshold_value = SpinBox()
        self.threshold = QSlider(Qt.Orientation.Horizontal)
        for widget in (self.threshold_label, self.threshold, self.threshold_value):
            widget.setToolTip(_("Higher = darker"))
        self.threshold.setRange(0, 255)
        self.threshold_value.setRange(0, 255)
        self.threshold_value.setKeyboardTracking(False)
        row.addWidget(self.threshold_label)
        row.addWidget(self.threshold_value, 1)
        self.layout_.addLayout(row)
        self.layout_.addWidget(self.threshold)
        self.invert = QCheckBox(_("Invert"))
        self.invert.setToolTip(_("Swap black and white"))
        self.layout_.addWidget(self.invert)

        self.section(_("Size"))
        self.crop = QCheckBox(_("Crop automatically"))
        self.crop.setToolTip(_("Crop to the content (without crop marks and blank space); "
                               "off = whole image"))
        self.keep_ratio = QCheckBox(_("Keep aspect ratio"))
        self.keep_ratio.setToolTip(_("Handles and fields scale the image without distortion"))
        self.original = QPushButton(_("ORIGINAL SIZE 1:1"))
        self.original.setToolTip(_("Print size from the resolution of the image (e.g. stamp, code)"))
        for widget in (self.crop, self.keep_ratio, self.original):
            self.layout_.addWidget(widget)

        self.section(_("Rotate"))
        row = QHBoxLayout()
        row.setSpacing(4)
        for attr, __, ___ in _ROTATE:
            button = QToolButton()
            button.setObjectName("layoutButton")
            button.setAutoRaise(True)              # Symbol beim Darüberfahren: Modus „Active“
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
        step = self._step               # jede Einstellung ein eigener Rückgängig-Schritt
        self.line.clicked.connect(lambda: step(self._set, mode="line"))
        self.photo.clicked.connect(lambda: step(self._set, mode="photo"))
        self.threshold.valueChanged.connect(self._threshold_moved)
        # Ziehen am Regler: ein Schritt vom Drücken bis zum Loslassen
        self.threshold.sliderPressed.connect(self._edited)
        self.threshold.sliderReleased.connect(self._edited)
        self.threshold_value.valueChanged.connect(lambda v: step(self._set, threshold=v))
        self.invert.clicked.connect(lambda on: step(self._set, invert=on))
        self.crop.clicked.connect(lambda on: step(self._set_crop, on))
        self.keep_ratio.clicked.connect(
            lambda on: step(self._change, lambda obj: layout.set_keep_ratio(obj, on)))
        self.original.clicked.connect(lambda: step(self._change, layout.original_size))

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """„Aus Datei …“ und „Bildschirmfoto“ lösen ihre Aktionen aus (Kürzel im Tooltip)."""
        for button, key in ((self.from_file, "image.insert"),
                            (self.screenshot, "image.screenshot"),
                            (self.symbol, "image.symbol")):
            action = actions[key]
            button.clicked.connect(lambda _checked=False, a=action: a.trigger())
            button.setToolTip(action.toolTip())
            action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))
        # Drehen: dieselben Aktionen wie im Reiter Layout (wirken auf die Auswahl = das Bild)
        for attr, key, __ in _ROTATE:
            button, rotate = getattr(self, attr), actions[key]
            button.clicked.connect(lambda _checked=False, a=rotate: a.trigger())
            button.setToolTip(rotate.toolTip())
            rotate.changed.connect(lambda b=button, a=rotate: b.setToolTip(a.toolTip()))

    def set_icon_style(self, dark_checked: bool) -> None:
        for attr, __, icon in _ROTATE:
            getattr(self, attr).setIcon(line_icon(icon, dark_checked, hover=True))

    @property
    def obj(self) -> ImageObject:
        return self.doc.objects[self.index]

    def set_object(self, index: int | None) -> None:
        """Bild bearbeiten (Index in ``doc.objects``) bzw. mit None keins."""
        if index != self.index:
            self.index = index
            self.refresh()

    def set_clipboard_image(self, available: bool) -> None:
        """Enthält die Zwischenablage ein Bild? („Aus Zwischenablage“ nur dann aktiv)."""
        self.from_clipboard.setEnabled(available)

    def _settings_widgets(self):
        return (self.line, self.photo, self.threshold_label, self.threshold, self.threshold_value,
                self.invert, self.crop, self.keep_ratio, self.original, self.rotate_left,
                self.rotate_right, self.position)

    # --- Modell → Panel -----------------------------------------------------
    def set_defaults(self, mode: str, threshold: int) -> None:
        """Standard für neue Bilder (Einstellungen) – zeigt das Panel ohne Auswahl."""
        self._defaults = (mode, threshold)
        self.refresh()

    def refresh(self) -> None:
        if self.index is not None and not (0 <= self.index < len(self.doc.objects)
                                           and isinstance(self.obj, ImageObject)):
            self.index = None                      # Objekt gibt es nicht mehr (Rückgängig …)
        selected = self.index is not None
        self.hint.setVisible(not selected)
        for widget in self._settings_widgets():
            widget.setEnabled(selected)
        self._updating = True
        try:
            if not selected:
                self._show_source("")
                mode, threshold = self._defaults
                (self.photo if mode == "photo" else self.line).setChecked(True)
                self.threshold.setValue(threshold)
                self.threshold_value.setValue(threshold)
                for box in (self.invert, self.crop, self.keep_ratio):
                    box.setChecked(False)
                self.show_frame(None)
                return
            obj = self.obj
            source = source_title(obj.source)
            self._show_source(source if obj.page is None else
                              _("{source} · page {page}").format(source=source, page=obj.page))
            (self.photo if obj.mode == "photo" else self.line).setChecked(True)
            self.threshold.setValue(obj.threshold)
            self.threshold_value.setValue(obj.threshold)
            self.invert.setChecked(obj.invert)
            self.crop.setChecked(obj.crop is not None)
            self.keep_ratio.setChecked(obj.keep_ratio)
        finally:
            self._updating = False

    def _show_source(self, text: str) -> None:
        metrics = self.source.fontMetrics()
        self.source.setText(metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, _SOURCE_PX))
        self.source.setToolTip(text)

    def show_frame(self, rect: Rect | None) -> None:
        """Rahmen des Bilds in mm anzeigen (vom Hauptfenster nach dem Rendern)."""
        self.position.show_frame(rect, editable_size=True)

    # --- Panel → Modell -----------------------------------------------------
    def _edited(self) -> None:
        if not self._updating and self.index is not None:
            self.edited.emit()

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

    def _threshold_moved(self, value: int) -> None:
        """Regler: Zahl mitführen; beim Ziehen nur anzeigen (Schritt bis zum Loslassen)."""
        if self._updating or self.index is None:
            return
        if self.threshold.isSliderDown():
            self._set(threshold=value)
        else:
            self._step(self._set, threshold=value)

    def _set_crop(self, on: bool) -> None:
        """Zuschnitt an (auf den Inhalt: alles, was nicht weiß ist; bei Symbolen auf die Tinte,
        wie beim Einfügen) bzw. aus (ganzes Bild); ist das Bild ganz weiß, bleibt es ganz –
        mit Hinweis."""
        if not on:
            self._change(lambda obj: layout.set_crop(obj, None))
            return
        if is_symbol_source(self.obj.source):
            box = ink_box(self.obj.image())
        else:
            box = crop_box(self.obj.image(), self.obj.dpi, ink=NOT_WHITE)
        if box is None:
            self.refresh()                         # Haken wieder aus
            self.message.emit(_(CROP_FAILED), "warn")
            return
        self._change(lambda obj: layout.set_crop(obj, box))

    def _frame_changed(self, key: str, value: float) -> None:
        if self.index is not None:
            self.frame_edited.emit(key, value)
