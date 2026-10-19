"""Hauptfenster: Werkzeugleiste, Bearbeitungsleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

import copy
import math
import uuid
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QMimeData, QSignalBlocker, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFrame,
                               QHBoxLayout, QInputDialog, QLineEdit,
                               QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                               QWidget)

from .. import barcodes, clipart, favorites, fonts, parcel, series
from ..desktop import APP_NAME
from ..detect import brother_busy
from .. import cups, zpl
from .. import printers as printers_mod
from ..printers import (UNTESTED_HINT, Printer, capabilities, choose, cups_printers,
                        effective_model, network_printers, usb_printers, zebra_printers)
from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, Series, TextObject
from ..files import NOT_WHITE, crop_box
from ..fonts import DEFAULT_FAMILY
from ..i18n import N_, _, language, ngettext
from ..labels import DPI, get_label, labels_for_model, length_limits
from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, change_label, exact_rect,
                      fill_anchored, frame_area, growing_axis, insert_placement, match_objects,
                      maximize_object, move, new_barcode, object_rect, objects_outside, outside_indices,
                      printable_area, proportional, reorder, resize, rotate, set_frame, to_grid)
from ..printer import DEFAULT_MODEL, cut_interval, to_print_mode
from ..render import (Renderer, RenderedObject, font_warnings, render_document,
                      set_svg_rasterizer)
from ..settings import (Settings, load_settings, network_entries, new_document, save_settings,
                        started_values, update_settings)
from ..shortcuts import ACTIONS, effective, without_conflicts
from .actions import apply_shortcuts, build_actions
from .canvas import Canvas
from .history import History, restore
from . import file_dialog, image_import
from .image_import import CLIPBOARD, DROPPED, MIME_OBJECTS, SCREENSHOT, SYMBOL_SOURCE
from .media_worker import MediaWorker
from .parcel_editor import ParcelTypeEditor
from .panels.image import CROP_FAILED
from .panels.text import DEFAULT_PT
from .file_session import FileSession
from .print_worker import PrintWorker
from .screenshot import FAILED as SCREENSHOT_FAILED, ScreenshotPortal
from .symbol_dialog import SymbolDialog
from .settings_dialog import SettingsDialog
from .symbols import SIZE, line_icon
from .text_edit_mode import TextEditSession
from .tools import START_TOOL, TOOLS, Tool

RENDER_DELAY_MS = 150
PANEL_WIDTH = 280          # Eigenschaften-Panels; bei wenig Höhe rollbar
MEDIA_STATUS_MAX_PX = 360   # Rollen-Hinweis in der Fußzeile; Rest per „…“ und Tooltip
PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff
ZOOM_STEP = 10             # Prozentpunkte je Klick bzw. Kürzel
NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
_DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
OUTSIDE_HINT = N_("Object extends beyond the label")
PASTE_OFFSET_MM = 2.0      # Einfügen/Duplizieren: versetzt nach rechts und unten
PROGRESS_EVERY = 25        # Serie drucken: Fortschritt alle so viele Etiketten
# Hinweise: englisch (N_), angezeigt wird _(…)
TURNED_HINT = N_("Image rotated by 90° so that it fits 1:1")
NO_CLIPBOARD_IMAGE = N_("No image in the clipboard.")
NO_SCREENSHOT = N_("Screenshot not available (no XDG portal) – copy it to the clipboard with the "
                   "system tool and paste it with Ctrl+V")
SYMBOL_MM = 15.0           # Symbol: längere Seite beim Einfügen (höchstens quer zum Band)
LIBRARY_ERRORS = (OSError, zipfile.BadZipFile, KeyError, ValueError)   # Archiv fehlt/beschädigt
HIDE_DELAY_MS = 300        # Bildschirmfoto: so lange nimmt der Desktop das Fenster weg
RESTORE_TIMEOUT_MS = 300_000  # Sicherheitsnetz nur für Portale, die nie antworten: so lange kann
                              # eine Auswahl offen sein, erst danach kommt das Fenster trotzdem wieder
# Bearbeitungsleiste: Aktion und eigenes Symbol (gui/icons); None = Trenner
EDIT_BAR = (("tool.select", "tool-select"), ("tool.text", "tool-text"), None,
            ("edit.cut", "edit-cut"), ("edit.copy", "edit-copy"), ("edit.paste", "edit-paste"),
            None, ("edit.undo", "edit-undo"), ("edit.redo", "edit-redo"))
_SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
OBJECT_PANELS = ("text", "image", "barcode")   # Panel je Objektart (Text, Bild, Barcode)
CHECKING_ROLL = N_("Checking the roll – please print again in a moment.")
PRINTING_WAIT = N_("Printing – please wait.")
PARCEL_VIEW_ONLY = N_("Parcel label: view only – to edit, use OPEN IN EDITOR or choose another tab.")
PARCEL_CHOOSE_TYPE = N_("Choose the parcel label type first.")


def shrunk_hint(factor: float, mode: str) -> str:
    """Hinweis zum verkleinerten Bild: Prozent abgerundet (nie „100 %“, nie „0 %“); Codes
    werden nur bei Strich erwähnt – ein Foto wird gerastert, Codes sind dort nicht gemeint."""
    percent = math.floor(factor * 100 + 1e-9)
    shown = _("{percent}%").format(percent=percent) if percent else _("< 1%")    # „37 %“
    if mode == "line":
        return _("Image reduced to {percent} – codes may no longer be readable").format(
            percent=shown)
    return _("Image reduced to {percent}").format(percent=shown)


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str | None = None, settings: Settings | None = None):
        """``model``: Druckermodell fest vorgeben; None = erkannt (``refresh_printer``), bis dahin
        Ersatzmodell bzw. zuletzt erkanntes aus den Einstellungen."""
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.settings = settings if settings is not None else load_settings(model=model)
        self.doc = doc if doc is not None else new_document(self.settings)
        self._fixed_model = model is not None
        self.model = model or effective_model(None, self.settings.printer_model,
                                              self.settings.last_model)
        self.printers: list[Printer] = []           # gefundene Drucker (USB, Netzwerk)
        self.printer: Printer | None = None         # gewählter bzw. erster gefundener
        self.image = None
        self._shown_size = (0, 0)                   # Etikettgröße der letzten gültigen Anzeige
        self._structure_dirty = False               # Objektliste seit der letzten Anzeige umgebaut
        self.rendered: list[RenderedObject] = []    # Objektbilder auf der Arbeitsfläche = im Druck
        self.renderer = Renderer()                  # rendert nur geänderte Objekte neu
        set_svg_rasterizer(image_import.rasterize_svg)   # Vektorbilder: Qt rastert SVG
        self._render_error: str | None = None
        self._shown_objects: list = []              # Objekte der Anzeige (Serie: gefüllte Zeile)
        self._hint: str | None = None               # Hinweis (ragt hinaus, Schrift ersetzt)
        self._print_signals = None
        self._worker = None                         # laufender Druck (Abbrechen)
        self._cancel_requested = False              # Serie: beim Vorbereiten abbrechen
        self._media_signals = None
        self._media_uri: str | None = None          # Drucker der laufenden Prüfung
        self._printer_present = False
        self._printing = False
        self._media_check_pending = False
        self._clipboard: list[TextObject | ImageObject] = []   # interne Zwischenablage (Kopien)
        self._clipboard_token = ""                  # Kennung der Kopie im System (MIME_OBJECTS)
        self._system = _ClipboardState()            # Zwischenablage des Systems (beim Ändern)
        self._text_pastes = 0                       # Text eingefügt seit dem letzten Ändern
        self._notice: str | None = None             # Meldung zum Einfügen von Bildern
        self._image_dir = ""                        # Ordner des zuletzt eingefügten Bilds
        self._parcel_dir = ""                       # Ordner der zuletzt geöffneten Paketmarke
        self._parcel_renderer = Renderer()          # Umwandlung einer Paketmarke (nur Ansicht)
        self._parcel_disabled: set[str] = set()     # in der Ansicht der Paketmarke gesperrt
        self._portal: ScreenshotPortal | None = None   # Bildschirmfoto (beim ersten Gebrauch)
        self.symbol_window: SymbolDialog | None = None  # „Symbol einfügen“ (beim ersten Gebrauch)
        self._symbols_were_open = False             # Bildschirmfoto: Symbol-Fenster mit ausgeblendet
        self._shooting = False                      # Fenster für ein Bildschirmfoto ausgeblendet
        self._quit_on_close = True                  # Einstellung der App vor dem Ausblenden
        self._shot_pending = False                  # Antwort des Portals steht noch aus
        self._merge_next = None                     # Pfeiltasten: Schritte zusammenfassen
        self._restoring = False                     # Rückgängig setzt gerade die Auswahl
        self._arranging = False                     # Auswahl wird intern umgestellt (Anlegen …)
        self._outside: list[int] = []               # Objekte, die über das Etikett ragen
        self._area = Rect(0, 0, 0, 0)               # bedruckbarer Bereich (mm), mit dem Bild
        self._inner: Rect | None = None             # Innenraum des Zierrahmens (mm), mit dem Bild
        self._shown_frame = None                    # Rahmen-Maske der letzten gültigen Anzeige
        # alle Kürzel kommen aus dem Verzeichnis (shortcuts.ACTIONS) und sind änderbar;
        # doppelt belegte (von Hand bearbeitete Datei): die spätere Aktion bleibt ohne Kürzel
        keys, key_warnings = without_conflicts(effective(self.settings.shortcuts))
        self.shortcut_actions = build_actions(self, keys)

        # Werkzeugleiste + Panels aus der Registry
        toolbar = QToolBar(_("Tools"))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        self.panels = QStackedWidget()
        self.panels.setObjectName("panels")
        self.panels.setFixedWidth(PANEL_WIDTH)
        self.tool_actions: dict[str, QAction] = {}
        self._panel_by_key = {}
        group = QActionGroup(self)
        for index, tool in enumerate(tools):
            panel = tool.panel(self.doc)
            panel.changed.connect(self.schedule_render)
            panel.changed.connect(self._update_edit_actions)
            panel.edited.connect(self._commit)
            self.panels.addWidget(panel)
            self._panel_by_key[tool.key] = panel
            action = QAction(QIcon.fromTheme(tool.icon), _(tool.title).upper(), self)
            action.setToolTip(_(tool.tip or tool.title))
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, key=tool.key: self._tool_triggered(key))
            group.addAction(action)
            toolbar.addAction(action)
            self.tool_actions[tool.key] = action
        start = self._start_tool()
        self.tool_actions[start].setChecked(True)
        self.panels.setCurrentWidget(self._panel_by_key[start])
        self.apply_hidden_tools(fall_back=False)    # Start-Reiter überspringt ausgeblendete schon
        self.panels.currentChanged.connect(self._remember_tool)    # erst nach dem Start-Reiter
        self.panels.currentChanged.connect(self._update_tool_buttons)   # SERIE: Knopf bis zum Wechsel
        self._stored_tool = self.settings.last_tool   # zuletzt benutzter Reiter, wie in der Datei
        self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
        # EINSTELLUNGEN und DRUCKEN in einer eigenen Leiste rechts daneben: nie im Überlauf –
        # überlaufen dürfen nur die Reiterknöpfe
        self.app_bar = QToolBar(_("Actions"))
        self.app_bar.setObjectName("appBar")
        self.app_bar.setMovable(False)
        self.app_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(self.app_bar)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.app_bar.addWidget(spacer)
        self.settings_action = self._toolbar_action("app.settings", "preferences-system",
                                                    _("SETTINGS"), self.open_settings)
        self.app_bar.addAction(self.settings_action)
        self.print_action = self._toolbar_action("file.print", "document-print", _("PRINT"),
                                                 self.print_label)
        self.app_bar.addAction(self.print_action)
        self.app_bar.widgetForAction(self.print_action).setObjectName("print")
        self.tool_bar = toolbar
        QTimer.singleShot(0, self, self.fit_toolbars)     # erst mit dem Design (apply_theme) messen

        # Arbeitsfläche
        self.canvas = Canvas(self.model)
        self.canvas.set_zoom(self.settings.start_zoom)
        self.canvas.length_changed.connect(self._on_length_dragged)
        self.canvas.drag_finished.connect(self._length_drag_finished)
        self.canvas.objects_moved.connect(self._move_objects)
        self.canvas.object_resized.connect(self._resize_object)
        self.canvas.text_requested.connect(self.create_text)
        self.canvas.edit_requested.connect(self.edit_text)
        self.canvas.selection_changed.connect(self._update_edit_actions)
        self.canvas.object_clicked.connect(self._show_object_panel)
        self.canvas.dropped.connect(self._dropped)
        self.canvas.symbol_dropped.connect(self._symbol_dropped)
        self.history = History(self.doc)
        self.history.changed.connect(self._update_edit_actions)
        # Datei und Favoriten (Reiter Datei): Neu/Öffnen/Speichern, Rückfrage bei Änderungen
        self.files = FileSession(self)
        for key, handler in (("file.new", self.files.new), ("file.open", self.files.open),
                             ("file.save", self.files.save), ("file.save_as", self.files.save_as)):
            self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
            self.addAction(self.shortcut_actions[key])
        self._connect_view_actions()
        self._connect_canvas_actions()
        self._connect_layout_actions()
        self._build_edit_bar()
        for panel in self._panel_by_key.values():
            panel.use_actions(self.shortcut_actions)
        self.apply_theme_icons()
        self.apply_font_list()
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        scroll = QScrollArea()                  # kleine Bildschirme: Panel rollt statt Fenster wächst
        scroll.setObjectName("panelScroll")
        # Klick auf freie Panel-Fläche nimmt niemandem den Fokus (Schreibmodus tippt weiter)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setWidget(self.panels)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(PANEL_WIDTH + scroll.verticalScrollBar().sizeHint().width())
        layout.addWidget(scroll)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        # Statusleiste: Drucker (Knopf mit Auswahl), Ergebnis, Zoom
        self.printer_status = QToolButton()
        self.printer_status.setObjectName("printerChoice")
        self.printer_status.setAutoRaise(True)
        self.printer_status.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.printer_menu = QMenu(self.printer_status)
        self.printer_menu.aboutToShow.connect(self._fill_printer_menu)
        self.printer_status.setMenu(self.printer_menu)
        self.result = QLabel()
        self.result.setTextFormat(Qt.TextFormat.PlainText)   # Namen mit „<b>“ bleiben Text
        self.statusBar().addWidget(self.printer_status)
        self.media_status = QLabel()            # Rolle im Drucker (Medium prüfen)
        self.media_status.setObjectName("mediaStatus")
        self.media_status.hide()
        self.statusBar().addWidget(self.media_status)
        self.statusBar().addWidget(self.result, 1)
        self.cancel_button = QPushButton(_("CANCEL"))   # Serie: beim Vorbereiten und Drucken
        self.cancel_button.setObjectName("cancelPrint")
        self.cancel_button.setToolTip(_("Cancel the series – a part already sent (up to 10 labels, "
                                        "with “Only at the end” the whole job) is still printed"))
        self.cancel_button.clicked.connect(self.cancel_print)
        self.cancel_button.hide()
        self.statusBar().addWidget(self.cancel_button)
        # Stand beim Start: der Einstellungsdialog zeigt danach, was erst ein Neustart ändert
        self._started = started_values(self.settings)
        # Dateiauswahl des Systems gilt ab dem Start (Platform-Theme der Anwendung) und nur mit Plugin
        self.system_dialog = (self._started["system_file_dialog"]
                              and file_dialog.system_dialog_available())
        self._sync_tool()                           # Start im Reiter Text: „Text anlegen“
        self.zoom_label = QLabel()
        for text, delta in (("−", -ZOOM_STEP), ("+", ZOOM_STEP)):
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(lambda _=False, d=delta: self.canvas.set_zoom(self.canvas.zoom + d))
            self.statusBar().addPermanentWidget(button)
            if text == "−":
                self.statusBar().addPermanentWidget(self.zoom_label)
        self.canvas.zoom_changed.connect(
            lambda z: self.zoom_label.setText(_("{percent}%").format(percent=z)))
        self.zoom_label.setText(_("{percent}%").format(percent=self.canvas.zoom))

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RENDER_DELAY_MS)
        self._timer.timeout.connect(self.render_now)
        self.panel("paper").check_media_requested.connect(self.check_media)
        self.panel("paper").set_model(self.model)      # Panels entstehen mit dem Standardmodell
        self._update_cut_choices()
        self.panel("layout").color_chosen.connect(self.set_color_selected)
        self.panel("series").driver_cut_chosen.connect(self._driver_cut_chosen)
        self.panel("paper").media_status_changed.connect(self._show_media_status)
        self._printer_timer = QTimer(self)
        self._printer_timer.setInterval(PRINTER_POLL_MS)
        self._printer_timer.timeout.connect(self.refresh_printer)
        self._printer_timer.start()
        self._hide_timer = QTimer(self)              # Bildschirmfoto: erst ausblenden, dann Auswahl
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._take_hidden)
        self._restore_timer = QTimer(self)           # … und ohne Antwort wieder zeigen
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._show_again)

        # Schreibmodus direkt auf dem Etikett (Editor des Text-Panels als Eingabepuffer)
        self.edit_session = TextEditSession(self)
        self._keep: int | None = None               # Objekt mit Platzhaltern zeigen (Schreibmodus-Start)
        self.panel("text").changed.connect(self.edit_session.content_changed)
        self._connect_edit_mode()
        self.render_now()
        self.canvas.selection_changed.connect(self._on_selection)
        for key in OBJECT_PANELS:
            self.panel(key).frame_edited.connect(
                lambda field, value, k=key: self._edit_frame(k, field, value))
        self.panel("image").paste_requested.connect(self.paste_image)
        self.panel("image").message.connect(self._set_result)
        self.panel("series").table_requested.connect(self.choose_series_table)
        self.panel("series").insert_column.connect(self.insert_column)
        self.panel("barcode").fill_preview = self._filled_barcode
        self._connect_parcel()
        self._clipboard_changed()
        self.refresh_printer()
        self._fit_label()                           # Standard-Etikett eines anderen Druckers
        if self.settings.warnings or key_warnings:
            self._set_result(" · ".join(self.settings.warnings + key_warnings), "error")

    def panel(self, key: str):
        return self._panel_by_key[key]

    def fit_toolbars(self, resize: bool = True) -> None:
        """Mit dem Design gemessen: die Leiste EINSTELLUNGEN/DRUCKEN nie schmaler als ihre Knöpfe
        (die Reiterknöpfe laufen bei Platzmangel über); ``resize`` (Start): das Fenster so breit,
        dass alles passt – höchstens so breit wie der Bildschirm."""
        ext = self.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
        if ext is not None:                         # Überlauf-Knopf sichtbar beschriften
            ext.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            ext.setText("»")
            ext.setToolTip(_("More tabs"))
        buttons = sum(self.app_bar.widgetForAction(a).sizeHint().width()
                      for a in (self.settings_action, self.print_action))
        self.app_bar.setMinimumWidth(buttons + 24)
        self._mark_overflow()
        if not resize:
            return
        screen = self.screen().availableGeometry().width() if self.screen() else 0
        wanted = self.tool_bar.sizeHint().width() + buttons + 48
        if screen:
            wanted = min(wanted, screen)
        if wanted > self.width():
            self.resize(wanted, self.height())

    def _connect_parcel(self) -> None:
        """Reiter PAKET: Umwandlung auf der Arbeitsfläche, Drucken, Editor, eigene Typen."""
        if "parcel" not in self._panel_by_key:
            return
        panel = self.panel("parcel")
        panel.view_changed.connect(self.render_now)
        panel.open_requested.connect(self.open_parcel_file)
        panel.print_requested.connect(self.print_documents)
        panel.editor_requested.connect(self.open_parcel_in_editor)
        panel.own_requested.connect(self.new_own_parcel_type)
        panel.rename_requested.connect(self.rename_own_parcel_type)
        panel.remove_requested.connect(self.remove_own_parcel_type)
        self.panels.currentChanged.connect(self._parcel_view_switched)

    def _toolbar_action(self, key: str, icon: str, text: str, handler) -> QAction:
        """Aktion aus dem Verzeichnis als Knopf der Werkzeugleiste (Kürzel bleibt änderbar)."""
        action = self.shortcut_actions[key]
        action.setIcon(QIcon.fromTheme(icon))
        action.setText(text)
        action.triggered.connect(lambda _=False: handler())
        return action

    def _connect_view_actions(self) -> None:
        """Zoom per Kürzel – wie die Knöpfe −/+ in der Statusleiste."""
        handlers = {"view.zoom_in": lambda: self.canvas.set_zoom(self.canvas.zoom + ZOOM_STEP),
                    "view.zoom_out": lambda: self.canvas.set_zoom(self.canvas.zoom - ZOOM_STEP),
                    "view.zoom_reset": lambda: self.canvas.set_zoom(100)}
        for key, handler in handlers.items():
            self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
            self.addAction(self.shortcut_actions[key])

    def _connect_canvas_actions(self) -> None:
        """Kürzel der Arbeitsfläche (Pfeiltasten, Zwischenablage, Werkzeug) und Rückgängig."""
        for direction, (sx, sy) in _DIRECTIONS.items():
            for suffix, step in NUDGE_MM.items():
                action = self.shortcut_actions[f"object.nudge_{direction}{suffix}"]
                action.triggered.connect(
                    lambda _=False, dx=sx * step, dy=sy * step: self.nudge(dx, dy))
                self.canvas.addAction(action)
        handlers = {"edit.delete": self.delete_selected, "edit.select_all": self.canvas.select_all,
                    "edit.cut": self.cut_selected, "edit.copy": self.copy_selected,
                    "edit.paste": self.paste, "edit.duplicate": self.duplicate_selected,
                    "tool.select": lambda: self._choose_tool("select"),
                    "tool.text": lambda: self._choose_tool("text"),
                    "image.insert": self.insert_image_file,
                    "image.screenshot": self.insert_screenshot,
                    "image.symbol": self.open_symbols,
                    "barcode.insert": self.insert_barcode}
        handlers["text.start_edit"] = handlers["text.start_edit_enter"] = self.edit_selected
        for key, handler in handlers.items():
            self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
            self.canvas.addAction(self.shortcut_actions[key])
        # global: wirkt überall; im Schreibmodus nutzt der Editor Strg+Z selbst (eigenes Rückgängig)
        # und gibt an das Dokument weiter, wenn er nichts mehr hat
        self.shortcut_actions["edit.undo"].triggered.connect(self.undo)
        self.shortcut_actions["edit.redo"].triggered.connect(self.redo)
        self.addActions([self.shortcut_actions["edit.undo"], self.shortcut_actions["edit.redo"]])

    def _connect_edit_mode(self) -> None:
        """Esc (Bereich „Schreibmodus“, fest) und Klick neben den Rahmen beenden den
        Schreibmodus – ein leer gebliebener Rahmen entfällt dabei. Rückgängig, Zwischenablage
        und ihre Knöpfe folgen im Schreibmodus dem Editor."""
        end = self.shortcut_actions["text.end_edit"]
        end.triggered.connect(lambda _=False: self.finish_editing())
        self.panel("text").addAction(end)
        self.canvas.edit_left.connect(lambda: self.finish_editing())
        editor = self.panel("text").edit
        for signal in (editor.copyAvailable, editor.undoAvailable, editor.redoAvailable):
            signal.connect(self._update_edit_actions)
        # Einfügen-Knöpfe folgen der Zwischenablage des Systems (PySide trennt die Verbindung
        # mit dem Fenster, ein späteres Ändern der Zwischenablage trifft nichts Gelöschtes)
        QApplication.clipboard().dataChanged.connect(self._clipboard_changed)

    def _connect_layout_actions(self) -> None:
        """Reiter „Layout“: Ausrichten, Größe angleichen, Drehen, Reihenfolge (auch per Kürzel)."""
        handlers = {"size.maximize": self.maximize_selected,
                    "object.rotate_left": lambda: self.rotate_selected(-90),
                    "object.rotate_right": lambda: self.rotate_selected(90),
                    "object.bring_forward": lambda: self.reorder_selected(1),
                    "object.send_backward": lambda: self.reorder_selected(-1)}
        for mode in ALIGN_MODES:
            handlers[f"align.{mode}"] = lambda m=mode: self.align_selected(m)
            handlers[f"align.paper_{mode}"] = lambda m=mode: self.align_selected(m, paper=True)
        for mode in SIZE_MODES:
            handlers[f"size.{mode}"] = lambda m=mode: self.match_selected(m)
        for key, handler in handlers.items():
            self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
            self.canvas.addAction(self.shortcut_actions[key])

    def _build_edit_bar(self) -> None:
        """Bearbeitungsleiste unter der Werkzeugleiste: Werkzeug, Zwischenablage, Rückgängig."""
        bar = QToolBar(_("Edit"))
        bar.setObjectName("editBar")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        bar.setIconSize(SIZE)
        self.addToolBarBreak()
        self.addToolBar(bar)
        self.edit_bar = bar
        modes = QActionGroup(self)                 # Auswahl-Pfeil oder „Text anlegen“
        for key in ("tool.select", "tool.text"):
            self.shortcut_actions[key].setCheckable(True)
            modes.addAction(self.shortcut_actions[key])
        self.shortcut_actions["tool.select"].setChecked(True)
        self.canvas.tool_changed.connect(lambda tool: self.shortcut_actions[f"tool.{tool}"].setChecked(True))
        for entry in EDIT_BAR:
            if entry is None:
                bar.addSeparator()
            else:
                bar.addAction(self.shortcut_actions[entry[0]])   # Symbol setzt apply_theme_icons

    def _start_tool(self) -> str:
        """Reiter beim Start: Einstellung ``start_tool`` („last“ = zuletzt benutzter); ohne
        gültigen Wert ``START_TOOL``."""
        wanted = self.settings.start_tool
        if wanted == "last":
            wanted = self.settings.last_tool
        for key in (wanted, START_TOOL):
            if key in self.tool_actions and key not in self.settings.hidden_tools:
                return key
        return next(iter(self.tool_actions))

    def apply_hidden_tools(self, fall_back: bool = True) -> None:
        """Ausgeblendete Reiter (Einstellung ``hidden_tools``) aus der Leiste nehmen. Ihre Panels
        bleiben: die Auswahl eines Objekts zeigt sie trotzdem (ohne hervorgehobenen Knopf).
        ``fall_back``: ist der gezeigte Reiter jetzt ausgeblendet und gehört nicht zur Auswahl bzw.
        zum Schreibmodus, geht es zum zuletzt benutzten sichtbaren Reiter (sonst PAPIER)."""
        self._update_tool_buttons()
        current = self._current_tool()
        if fall_back and not self._tool_needed(current) and not self._panel_in_use(current):
            self._show_visible_tool()

    def _update_tool_buttons(self, _index: int = 0) -> None:
        """Knöpfe der Leiste nach ``hidden_tools`` – SERIE erscheint trotzdem, solange sie
        gebraucht wird (Serie im Etikett, Schnitt-Optionen des Druckers)."""
        for key, action in self.tool_actions.items():
            action.setVisible(self._tool_visible(key))
        QTimer.singleShot(0, self, self._mark_overflow)    # nach dem Neuordnen der Leiste

    def _mark_overflow(self) -> None:
        """Liegt der aktive Reiter im Überlauf der Leiste, ist der Knopf „»“ hervorgehoben."""
        ext = self.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
        if ext is None:
            return
        hidden = any(action.isChecked() and action.isVisible()
                     and not self.tool_bar.widgetForAction(action).isVisible()
                     for action in self.tool_actions.values())
        if ext.property("active") != hidden:
            ext.setProperty("active", hidden)
            ext.style().unpolish(ext)
            ext.style().polish(ext)
            # auch ohne Stylesheet (Design „Klassisch“) sichtbar: fett und mit Punkt
            ext.setText("» •" if hidden else "»")
            font = ext.font()
            font.setBold(hidden)
            ext.setFont(font)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self, self._mark_overflow)    # Überlauf ändert sich mit der Breite

    def createPopupMenu(self):
        """Kein Kontextmenü zum Ausblenden der Leisten (Aktionen/Werkzeuge gehören immer dazu)."""
        menu = super().createPopupMenu()
        if menu is not None:
            for bar in (self.tool_bar, self.app_bar):
                menu.removeAction(bar.toggleViewAction())
            if menu.isEmpty():
                return None
        return menu

    def _tool_needed(self, key: str) -> bool:
        """Knopf gehört in die Leiste: nicht ausgeblendet – oder SERIE wird gebraucht (Serie im
        Etikett, Schnitt-Optionen des Druckers)."""
        if key not in self.settings.hidden_tools:
            return True
        return key == "series" and (self.doc.series is not None
                                    or not self.panel("series").driver_box.isHidden())

    def _tool_visible(self, key: str) -> bool:
        """Wie ``_tool_needed``; SERIE bleibt außerdem, solange ihr Panel zu sehen ist – der Knopf
        verschwindet erst beim Wechsel (nach ENTFERNEN, Neu, Druckerwechsel)."""
        return self._tool_needed(key) or (key == "series"
                                          and self.panels.currentWidget() is self.panel("series"))

    def _panel_in_use(self, key: str) -> bool:
        """Gehört das Panel zur Auswahl (Objekt seiner Art zuletzt gewählt) bzw. zum Schreibmodus?"""
        if key == "text" and self.edit_session.active:
            return True
        selection = self.canvas.selection()
        return bool(selection) and 0 <= selection[-1] < len(self.doc.objects) \
            and _panel_for(self.doc.objects[selection[-1]]) == key

    def _show_visible_tool(self) -> None:
        """Zum zuletzt benutzten sichtbaren Reiter (sonst PAPIER) – wie ein Klick auf ihn."""
        key = self.settings.last_tool
        if key not in self.tool_actions or not self._tool_needed(key):
            key = START_TOOL
        self._tool_triggered(key)
        self.tool_actions[key].setChecked(True)

    def _current_tool(self) -> str:
        """Schlüssel des gezeigten Panels."""
        return next((k for k, panel in self._panel_by_key.items()
                     if panel is self.panels.currentWidget()), "")

    def _remember_tool(self, _index: int = 0) -> None:
        """Gezeigten Reiter als zuletzt benutzten merken (``last_tool``) – nur im Speicher: jeder
        Klick auf ein Objekt kann den Reiter wechseln; auf die Platte kommt er beim Schließen."""
        key = self._current_tool()
        if key and key not in self.settings.hidden_tools:   # nur per Auswahl gezeigt: nicht merken
            self.settings.last_tool = key

    def _show_tool(self, key: str) -> None:
        """Panel eines Werkzeugs zeigen (wie ein Klick auf seinen Knopf)."""
        self.tool_actions[key].setChecked(True)
        self.panels.setCurrentWidget(self.panel(key))

    def _choose_tool(self, tool: str) -> None:
        """Auswahl-Pfeil oder „Text anlegen“ (Bearbeitungsleiste, Kürzel) – beendet den
        Schreibmodus."""
        self.finish_editing()
        self.canvas.set_tool(tool)

    def _tool_triggered(self, key: str) -> None:
        """Werkzeug-Reiter: Panel zeigen; Text ohne Auswahl heißt „Text anlegen“, jedes
        andere Panel arbeitet mit dem Auswahl-Pfeil (und beendet den Schreibmodus)."""
        if key != "text":
            self.finish_editing()
        self.panels.setCurrentWidget(self.panel(key))
        if key == "text":
            self._sync_tool()
        else:
            self.canvas.set_tool("select")

    def _sync_tool(self) -> None:
        """Werkzeug passend zur Auswahl: Text-Panel ohne Auswahl = „Text anlegen“ (Hinweis
        im Panel); mit Auswahl der Auswahl-Pfeil – wie nach einem Klick auf ein Objekt."""
        if self.canvas.selection():
            self.canvas.set_tool("select")
        elif self.panels.currentWidget() is self.panel("text"):
            self.canvas.set_tool("text")

    def _on_selection(self, indices: list[int]) -> None:
        """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen (Text oder Bild) – außer
        der Reiter „Layout“ ist zu sehen. Ein leerer Textrahmen, den die Auswahl verlässt,
        entfällt."""
        if self._arranging:                         # Anlegen, Umnummerieren: nur mitführen
            self._follow_selection(indices)
            return
        if self.edit_session.active and indices != [self.edit_session.index]:
            self.finish_editing(drop_empty=False)   # leere Rahmen entfallen gleich hier unten
        if not self._restoring:
            indices = self._drop_empty_frames(indices)
        self._follow_selection(indices)
        if self._restoring:                         # Rückgängig wechselt nicht den Reiter –
            if not indices and not self._tool_visible(self._current_tool()):
                self._show_visible_tool()           # außer weg vom ausgeblendeten der Auswahl
            return
        self.history.select(self.doc, indices)
        if indices:
            self._show_object_panel()
        elif not self._tool_visible(self._current_tool()):
            self._show_visible_tool()               # ausgeblendeter Reiter nur für die Auswahl
        self._sync_tool()

    def _drop_empty_frames(self, indices: list[int]) -> list[int]:
        """Leere Textrahmen (mit Position), die nicht mehr ausgewählt sind, entfernen; die
        Auswahl wird umnummeriert. Unsichtbar und nicht anklickbar, sollen sie weder liegen
        bleiben noch das Etikett verlängern.

        Kein eigener Rückgängig-Schritt: Ist nichts anderes offen, ersetzt das den aktuellen
        Stand (das Anlegen entfällt dann ganz), sonst gehört es zum laufenden Schritt."""
        empty = [i for i, obj in enumerate(self.doc.objects)
                 if obj.positioned and obj.is_empty() and i not in indices]
        if not empty:
            return indices
        recorded = self.history.is_current(self.doc)
        self._structure_changing()
        for index in reversed(empty):
            del self.doc.objects[index]
        indices = [i - sum(e < i for e in empty) for i in indices]
        self._arranging = True
        try:
            self.canvas.set_selection(indices)     # vor dem Neuzeichnen: Indizes passen
            self._follow_selection(indices)        # Text-Panel nicht auf dem entfernten Rahmen
            self.render_now()
        finally:
            self._arranging = False
        if recorded:
            self.history.amend(self.doc, indices)
        return indices

    def _show_object_panel(self) -> None:
        """Zum Panel des zuletzt gewählten Objekts – Text oder Bild (auch beim Klick auf ein
        schon gewähltes); der Reiter „Layout“ arbeitet mit jeder Auswahl und bleibt."""
        if self.panels.currentWidget() in (self.panel("layout"), self.panel("series")):
            return                                  # beide arbeiten mit jeder Auswahl
        selection = self.canvas.selection()
        if selection and 0 <= selection[-1] < len(self.doc.objects):
            key = _panel_for(self.doc.objects[selection[-1]])
            if self.panels.currentWidget() is not self.panel(key):
                self._show_tool(key)

    def _follow_selection(self, indices: list[int]) -> None:
        """Panels erfahren die Auswahl; das Panel seiner Art bearbeitet das zuletzt gewählte
        Objekt, das andere keins."""
        for panel in self._panel_by_key.values():
            panel.set_selection(indices)
        last = indices[-1] if indices and indices[-1] < len(self.doc.objects) else None
        kind = _panel_for(self.doc.objects[last]) if last is not None else None
        for key in OBJECT_PANELS:
            self.panel(key).set_object(last if kind == key else None)
        self._update_frame()

    def _update_frame(self) -> None:
        """Bereich „Position“: Rahmen des bearbeiteten Objekts, wie er gerendert ist."""
        for key in OBJECT_PANELS:
            panel = self.panel(key)
            index = panel.index
            if index is None or not self._valid(index):
                panel.show_frame(None)
            else:
                panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))

    def _update_edit_actions(self) -> None:
        if self._parcel_locked():                   # Paketmarke: nur Ansicht
            for entry in ACTIONS:
                action = self.shortcut_actions[entry.id]
                if (entry.scope == "canvas" or entry.id in ("edit.undo", "edit.redo")) \
                        and action.isEnabled():
                    action.setEnabled(False)
                    self._parcel_disabled.add(entry.id)
            return
        if self._parcel_disabled:                   # wieder wie vorher, Rest regelt das Folgende
            for key in self._parcel_disabled:
                self.shortcut_actions[key].setEnabled(True)
            self._parcel_disabled.clear()
            self.panel("layout").set_selection(self.canvas.selection())   # Ausrichten nach Auswahl
        if self.edit_session.update_actions(self.shortcut_actions):   # wirken auf den Editor
            return
        self.shortcut_actions["text.end_edit"].setEnabled(False)
        selection = self.canvas.selection()
        single_text = (len(selection) == 1 and selection[0] < len(self.doc.objects)
                       and isinstance(self.doc.objects[selection[0]], (TextObject, BarcodeObject)))
        for key in ("text.start_edit", "text.start_edit_enter"):
            self.shortcut_actions[key].setEnabled(single_text)
        for key in _SELECTION_ACTIONS:
            self.shortcut_actions[key].setEnabled(bool(selection))
        self.shortcut_actions["edit.paste"].setEnabled(self._can_paste())
        self.shortcut_actions["edit.undo"].setEnabled(self.history.can_undo(self.doc))
        self.shortcut_actions["edit.redo"].setEnabled(self.history.can_redo(self.doc))

    # --- Rendern ----------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        self._update_tool_buttons()                 # SERIE: Serie hinzugefügt/entfernt
        self.files.update_title()                   # „•“ bei ungespeicherten Änderungen
        if self.canvas.is_dragging():   # Ziehen nicht unterbrechen – nach dem Loslassen rendern
            self._timer.start()
            return
        if self._render_parcel():                   # Reiter PAKET mit Marke: nur Ansicht
            return
        if self.canvas.read_only:
            self.canvas.set_read_only(False)
            self._update_edit_actions()             # Bearbeiten wieder möglich
        view = self._view_doc()
        try:
            # jedes Objekt höchstens einmal messen und zeichnen; Fläche und „ragt hinaus“
            # folgen aus den gerenderten Objekten; ein Barcode, der sich nicht kodieren lässt,
            # bleibt als Platzhalter wählbar (Fehler wie ein Renderfehler: kein Druck)
            result = self.renderer.render(view, self.model, placeholders=True)
        except ValueError as e:
            # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
            self._render_error = self._series_error(str(e))
            self._drop_stale_view()
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        error = self._series_error(result.errors[0][1], result.errors[0][0]) if result.errors else None
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
        self._render_error = error
        if error is not None:
            self._set_result(error, "error")
        if self._hint is not None and self.result.text() == self._hint:
            self._set_result("", "")   # alten Hinweis nur löschen, wenn er noch dasteht
        self._hint = None
        size, rendered = result.size, result.objects
        area = printable_area(self.doc, self.model, size)
        outside = outside_indices(rendered, size, self.doc.objects)
        hints = ([_(OUTSIDE_HINT)] if outside else []) + font_warnings(self.doc)
        series_panel = self.panel("series")
        if self.doc.series is not None and series_panel.error:
            hints.append(_("Series: {error}").format(error=series_panel.error))
        series_panel.show_missing(series.missing(self.doc, series_panel.table.columns)
                                  if series_panel.table is not None else [])
        if hints and not self.result.text():
            self._hint = " · ".join(hints)
            self._set_result(self._hint, "error")
        self.panel("text").show_error(None)
        self.image = result.image
        self.rendered = rendered
        self._shown_objects = view.objects          # was die Arbeitsfläche zeigt (Serie: gefüllt)
        self._shown_size = size
        self._structure_dirty = False
        self._outside = outside
        self._area = area
        self._inner = frame_area(self.doc, self.model, size)
        self._shown_frame = result.frame
        # Anfasser: Ecken halten das Seitenverhältnis bei Text ohne feste Rahmengröße, bei
        # Bildern mit „Seitenverhältnis beibehalten“ und QR-Codes – die beiden auch an den Kanten
        aspect = [_keeps_aspect(obj) for obj in self.doc.objects]
        self.canvas.set_document(get_label(self.doc.label_id), size, rendered, self.doc.orientation,
                                 area, keep_ratio=[keep or isinstance(obj, TextObject) and not obj.fit
                                                   for obj, keep in zip(self.doc.objects, aspect)],
                                 grow=growing_axis(self.doc), keep_aspect=aspect,
                                 frame=result.frame, inner=self._inner)
        self.panel("layout").set_growing(growing_axis(self.doc))
        red = get_label(self.doc.label_id).two_color and capabilities(self.model).two_color
        self.panel("layout").set_red_available(red)
        self.panel("barcode").red_available = red
        self.panel("barcode").module.set_dpi(get_label(self.doc.label_id).dpi)
        self._update_frame()
        self.panel("barcode").update_check()        # Serie: Prüfhinweis zur Vorschau-Zeile
        self.edit_session.update_marks()            # Schreibmarke zum neuen Zeilensatz

    # --- Paketmarke (Reiter PAKET) ------------------------------------------------
    def _parcel_shown(self) -> bool:
        """Reiter PAKET ist zu sehen."""
        return ("parcel" in self._panel_by_key
                and self.panels.currentWidget() is self.panel("parcel"))

    def _parcel_locked(self) -> bool:
        """Reiter PAKET mit geladener Marke: Arbeitsfläche ist nur Ansicht (mit oder ohne
        Umwandlung) – nichts ändert das Dokument."""
        return self._parcel_shown() and self.panel("parcel").source is not None

    def _parcel_blocks(self) -> bool:
        """Bearbeiten im Reiter PAKET mit Marke: Hinweis statt Änderung (True = gesperrt)."""
        if not self._parcel_locked():
            return False
        self._set_result(_(PARCEL_VIEW_ONLY), "error")
        return True

    def _render_parcel(self) -> bool:
        """Reiter PAKET mit geladener Marke: die Arbeitsfläche zeigt das gewählte Etikett der
        Umwandlung bzw. – ohne Umwandlung (nicht erkannt, Typ nicht gewählt, Fehler) – ein leeres
        Etikett, immer nur zur Ansicht (True); ohne Marke das Dokument (False). Die Umwandlung
        folgt dem Etikett des Dokuments und dem Drucker."""
        if not self._parcel_shown():
            return False
        panel = self.panel("parcel")
        blocker = QSignalBlocker(panel)             # Umwandlung neu – gezeigt wird hier gleich
        panel.set_target(self.doc.label_id, self.model)
        del blocker
        if panel.source is None:
            return False
        self.finish_editing()
        self.canvas.set_selection([])
        doc = panel.current_document()
        try:
            if doc is None:
                raise ValueError(None)
            result = self._parcel_renderer.render(doc, self.model)
        except ValueError as e:
            if e.args and e.args[0]:
                panel.show_render_error(str(e))
            doc = Document(self.doc.label_id, length_mm=self.doc.length_mm,
                           orientation=self.doc.orientation)   # leer: nichts zu sehen
            result = self._parcel_renderer.render(doc, self.model)
        size = result.size
        count = len(result.objects)
        self.canvas.set_read_only(True)
        self.canvas.set_document(get_label(doc.label_id), size, result.objects, doc.orientation,
                                 printable_area(doc, self.model, size), keep_ratio=[False] * count,
                                 grow=None, keep_aspect=[False] * count, frame=result.frame)
        self._update_edit_actions()
        return True

    def _parcel_view_switched(self, _index: int = 0) -> None:
        """Reiterwechsel: Arbeitsfläche zeigt die Umwandlung bzw. wieder das Dokument."""
        self.render_now()

    def ask_parcel_file(self) -> str | None:
        """Dateidialog „Paketmarke öffnen“ mit Vorschau (in Tests ersetzbar); None = abgebrochen."""
        path = file_dialog.ask_open(self, _("Open parcel label"), self._parcel_dir,
                                    _("Parcel labels (*.pdf *.png *.jpg *.jpeg *.gif);;"
                                      "All files (*)"),
                                    system=self.system_dialog, model=self.model)
        if path:
            self._parcel_dir = str(Path(path).parent)
        return str(path) if path else None

    def open_parcel_file(self) -> None:
        """MARKE ÖFFNEN …: Datei wählen, laden, Typ erkennen, umwandeln (Fehler im Panel)."""
        path = self.ask_parcel_file()
        if path:
            self.panel("parcel").load(path)

    def print_documents(self, docs: list[Document]) -> None:
        """Mehrere Etiketten (Umwandlung einer Paketmarke) in einem Auftrag drucken, Schnitt nach
        jedem – gleiche Prüfungen und Rückfragen wie sonst."""
        if not docs:
            return
        if self.is_printing():
            self._set_result(_(PRINTING_WAIT), "error")
            return
        if not self._can_print(docs[0]):
            return
        red = get_label(docs[0].label_id).two_color and capabilities(self.model).two_color
        images, outside = [], []
        try:
            for number, doc in enumerate(docs, start=1):
                images.append(to_print_mode(render_document(doc, self.model), red))
                if objects_outside(doc, self.model):
                    outside.append(number)
        except ValueError as e:
            self._set_result(str(e), "error")
            return
        self._print(images if len(images) > 1 else images[0], docs[0], outside)

    def open_parcel_in_editor(self, doc: Document) -> None:
        """Gezeigtes Etikett der Umwandlung als gewöhnliches Etikett öffnen (Rückfrage bei
        Änderungen wie bei Neu); danach zeigt die Arbeitsfläche wieder den Editor."""
        if self.files.open_document(copy.deepcopy(doc)):
            self._tool_triggered("paper")
            self.tool_actions["paper"].setChecked(True)

    def exec_parcel_editor(self, editor: ParcelTypeEditor) -> bool:
        """Fenster „Eigener Markentyp“ zeigen (in Tests ersetzbar); True = gespeichert."""
        return editor.exec() == ParcelTypeEditor.DialogCode.Accepted

    def new_own_parcel_type(self) -> None:
        """EIGENEN TYP ANLEGEN …: Bereiche auf der geöffneten Marke festlegen, speichern."""
        panel = self.panel("parcel")
        if panel.source is None:
            return
        taken = {t.id for t in parcel.own_types()}
        editor = ParcelTypeEditor(self, panel.source, self.doc.label_id, self.model, taken)
        try:
            if not self.exec_parcel_editor(editor):
                return
            ptype = editor.result_type()
            parcel.save_own(ptype)
        except (parcel.ParcelError, OSError) as e:
            self._set_result(_("Own type not saved: {error}").format(error=e), "error")
            return
        finally:
            editor.deleteLater()
        panel.refresh_types(ptype.id)
        self._set_result(_("Own type “{name}” saved").format(name=ptype.name), "ok")

    def ask_parcel_type_name(self, current: str) -> str | None:
        """Neuer Name eines eigenen Typs (in Tests ersetzbar); None = abgebrochen."""
        name, ok = QInputDialog.getText(self, _("Rename own type"), _("Name:"), text=current)
        return name.strip() if ok and name.strip() else None

    def ask_remove_parcel_type(self, name: str) -> bool:
        """Rückfrage vor dem Löschen eines eigenen Typs (in Tests ersetzbar)."""
        return QMessageBox.question(
            self, _("Delete own type"), _("Delete the own type “{name}”?").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def rename_own_parcel_type(self, type_id: str) -> None:
        try:
            ptype = parcel.find(type_id)
            name = self.ask_parcel_type_name(ptype.name)
            if name is None:
                return
            parcel.save_own(replace(ptype, names={language() or "en": name}))
        except (parcel.ParcelError, OSError) as e:
            self._set_result(str(e), "error")
            return
        self.panel("parcel").refresh_types()            # gewählter Typ bleibt gewählt

    def remove_own_parcel_type(self, type_id: str) -> None:
        try:
            ptype = parcel.find(type_id)
            if not self.ask_remove_parcel_type(ptype.name):
                return
            parcel.remove_own(type_id)
        except (parcel.ParcelError, OSError) as e:
            self._set_result(str(e), "error")
            return
        self.panel("parcel").refresh_types()

    def _drop_stale_view(self) -> None:
        """Nach einem Renderfehler: Objektbilder, die nicht mehr zu ``doc.objects`` passen
        (gelöscht, eingefügt, umsortiert – ``_structure_changing``), von der Arbeitsfläche
        nehmen – sonst wirkten Auswahl und Ziehen auf ein anderes Objekt. Bei gleichem Aufbau
        bleibt das letzte gültige Bild stehen."""
        if not self._structure_dirty:
            return
        self._structure_dirty = False
        self.rendered = []
        self.canvas.set_document(get_label(self.doc.label_id), self._shown_size, [],
                                 self.doc.orientation,
                                 self._area, keep_ratio=[], grow=growing_axis(self.doc),
                                 frame=self._shown_frame, inner=self._inner)

    # --- Rückgängig -------------------------------------------------------
    def _commit(self, merge=None) -> None:
        """Stand nach einer abgeschlossenen Aktion festhalten (ohne Änderung kein Schritt).

        Vor jeder Aktion aufgerufen, wird noch nicht Festgehaltenes ein eigener Schritt. Nicht
        während die Auswahl intern umgestellt wird (z. B. ein leerer Rahmen entfällt); das hält
        der Aufrufer selbst fest. Im Schreibmodus gehört alles zur laufenden Bearbeitung – sie
        wird beim Beenden ein Schritt (``finish_editing``)."""
        if self._arranging or self.edit_session.active:
            return
        self.history.push(self.doc, merge, self.canvas.selection())
        self._update_edit_actions()

    def undo(self) -> None:
        """Rückgängig – im Schreibmodus erst innerhalb der Bearbeitung (``TextEditSession.undo``),
        dann im Dokument (Knopf und Strg+Z gleich)."""
        if self._parcel_blocks():
            return
        self.accept_pending_input()                 # eben Getipptes ist der letzte Schritt
        if not self.edit_session.undo():
            self._restore(self.history.undo(self.doc, self.canvas.selection()))

    def redo(self) -> None:
        """Wiederherstellen – im Schreibmodus erst im Editor, dann im Dokument (wie ``undo``)."""
        if self._parcel_blocks():
            return
        self.accept_pending_input()
        if not self.edit_session.redo():
            self._restore(self.history.redo(self.doc, self.canvas.selection()))

    def _restore(self, snapshot: Document | None) -> None:
        """Stand zurückholen – samt der Auswahl, die zu ihm gehörte (dieselben Objekte)."""
        if snapshot is None:
            return
        selection = self.history.selection
        self._structure_changing()
        self._restoring = True       # Auswahl, die beim Neuzeichnen entfällt, nicht festhalten
        try:
            restore(self.doc, snapshot)
            for panel in self._panel_by_key.values():
                panel.refresh()
            self.render_now()
            self.canvas.set_selection(selection)        # ungültige Indizes entfallen
        finally:
            self._restoring = False
        self._sync_tool()
        self._update_edit_actions()

    # --- Objekte auf der Arbeitsfläche ------------------------------------
    def nudge(self, dx_mm: float, dy_mm: float) -> None:
        """Pfeiltasten: Auswahl verschieben; mehrere Schritte hintereinander = ein Rückgängig."""
        self._merge_next = ("nudge", tuple(self.canvas.selection()))
        try:
            self.canvas.nudge(dx_mm, dy_mm)
        finally:
            self._merge_next = None

    def _valid(self, index: int) -> bool:
        """Index passt zum Dokument und zu den gerenderten Objekten (nicht veraltet)."""
        return 0 <= index < min(len(self.doc.objects), len(self.rendered))

    def _structure_changing(self) -> None:
        """Objektliste ändert sich (Löschen, Einfügen, Rückgängig, Reihenfolge …): laufendes
        Ziehen abbrechen – seine Indizes gälten nicht mehr – und gleich neu zeichnen lassen."""
        self._structure_dirty = True
        self.canvas.cancel_object_drag()

    def _move_objects(self, indices: list[int], rects: list[Rect]) -> None:
        indices_rects = [(i, r) for i, r in zip(indices, rects) if self._valid(i)]
        if not indices_rects:
            return
        self._commit()
        dragged = self._merge_next is None          # Maus: auf 0,1 mm wie die Felder; Pfeile genau
        for index, rect in indices_rects:
            moved = move(self.doc.objects[index], rect, self.rendered[index])
            self.doc.objects[index] = to_grid(moved, x=True, y=True) if dragged else moved
        self._objects_changed(indices)
        self._commit(self._merge_next)

    def _resize_object(self, index: int, rect: Rect, handle: str) -> None:
        if not self._valid(index):
            return
        self._commit()
        resized = self._keep_content(index, resize(self._layout_object(index), rect,
                                                   self.rendered[index], handle))
        # nur die gezogenen Kanten auf 0,1 mm (wie die Felder) – die anderen bleiben genau
        self.doc.objects[index] = to_grid(resized, x="l" in handle, y="t" in handle,
                                          w="l" in handle or "r" in handle,
                                          h="t" in handle or "b" in handle)
        self._objects_changed([index])
        self._commit()

    def create_text(self, x_mm: float, y_mm: float) -> None:
        """Neuer leerer Textrahmen an x/y (mm, Leserichtung), ausgewählt, gleich im Schreibmodus.

        Schrift aus den Einstellungen (automatische Größe → 19 pt). Andere leere Texte sind
        unsichtbar und drucken nicht – sie entfallen dabei."""
        if self._parcel_blocks():
            return
        self.finish_editing()
        self._structure_changing()
        self._commit()
        obj = self._new_text("")
        obj.x_mm, obj.y_mm = round(x_mm, 1), round(y_mm, 1)
        self.doc.objects[:] = [o for o in self.doc.objects if not o.is_empty()]
        self.doc.objects.append(obj)
        index = len(self.doc.objects) - 1
        self._arranging = True            # der neue, noch leere Rahmen bleibt
        try:
            self.canvas.set_selection([])  # erst nach der Änderung: Auswahl davor bleibt im Stand
            self._objects_changed(list(range(len(self.doc.objects))))
        finally:
            self._arranging = False
        self.canvas.set_selection([index])
        self.edit_text(index)                       # Anlegen und Schreiben: ein Schritt

    def _view_doc(self) -> Document:
        """Was die Arbeitsfläche zeigt: mit Serie das Etikett der Vorschau-Zeile – das Objekt im
        Schreibmodus mit seinen Platzhaltern (Schreibmarke passt zum Text)."""
        row = self.panel("series").preview()
        if row is None:
            return self.doc
        keep = self._keep if self._keep is not None else self.edit_session.index
        return fill_anchored(self.doc, *row, self.model, keep=keep)

    def _series_error(self, message: str, index: int | None = None) -> str:
        """Renderfehler mit Serie: welche Zeile – bzw. dass es im Schreibmodus an den
        Platzhaltern liegt (sie stehen statt der Werte da). ``index``: Objekt des Fehlers, falls
        bekannt (Barcode als Platzhalter) – nur das Objekt im Schreibmodus zeigt Platzhalter."""
        if self.panel("series").preview() is None:
            return message
        kept = self._keep if self._keep is not None else self.edit_session.index
        if kept is not None and index in (None, kept):
            return _("{message} – with placeholders in text editing (choose a smaller font)"
                     ).format(message=message)
        return _("Row {row}: {message}").format(row=self.panel("series").current_row(),
                                                 message=message)

    def ask_series_file(self) -> str | None:
        """Dialog für die Tabelle einer Serie (in Tests ersetzbar); beginnt im Ordner der
        aktuellen Tabelle."""
        current = self.doc.series.source if self.doc.series is not None else None
        return file_dialog.ask_open(
            self, _("Table for the series"), str(Path(current).parent) if current else "",
            _("Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"),
            system=self.system_dialog)

    def choose_series_table(self) -> None:
        """TABELLE …: Datei wählen, lesen (Fehler → Meldung, nichts geändert), verknüpfen."""
        path = self.ask_series_file()
        if not path:
            return
        path = str(Path(path).resolve())
        try:
            table = series.load_table(path)
        except series.SeriesError as e:
            self._set_result(str(e), "error")
            return
        cut = self.doc.series.cut if self.doc.series is not None else "each"
        self.panel("series").set_series(Series(source=path, cut=cut), table)   # einmal gelesen

    def insert_column(self, name: str) -> None:
        """Spalte als ``{Name}`` einfügen: ans Ende des gewählten Textobjekts (seine letzte
        Formatierung) bzw. in den Inhalt des gewählten Barcodes (ersetzt den Beispielinhalt,
        sonst angehängt), sonst als neuer Text links oben – ein Schritt."""
        self.finish_editing()
        placeholder = "{" + name + "}"
        selection = [i for i in self.canvas.selection() if self._valid(i)]
        if len(selection) == 1 and isinstance(self.doc.objects[selection[0]], BarcodeObject):
            self._commit()
            obj = self.doc.objects[selection[0]]
            sample = obj.data == barcodes.SAMPLES.get(obj.kind)
            data = placeholder if sample else obj.data + placeholder
            if len(data) > MAX_BARCODE_DATA:
                self._set_result(_("Content too long (at most {count} characters)").format(
                    count=MAX_BARCODE_DATA), "error")
                return
            self.doc.objects[selection[0]] = replace(obj, data=data)
            self._objects_changed(selection)
            self._commit()
            return
        if len(selection) == 1 and isinstance(self.doc.objects[selection[0]], TextObject):
            self._commit()                          # noch nicht Festgehaltenes zuerst
            obj = self.doc.objects[selection[0]]
            last = obj.paragraphs[-1].spans[-1]
            gap = " " if obj.text and not obj.text[-1].isspace() else ""   # {A} {B}, nicht {A}{B}
            last.text += gap + placeholder
            self._objects_changed(selection)
            self._commit()
            return
        if self._timer.isActive():
            self.render_now()                       # aktueller Innenraum
        obj = self._new_text(placeholder)
        area = self._paper_area()
        obj.x_mm, obj.y_mm = round(area.x, 3), round(area.y, 3)
        self._insert([obj])

    def _new_text(self, text: str) -> TextObject:
        """Neuer Text mit der Schrift aus den Einstellungen (automatische Größe → 19 pt),
        linksbündig: Er wächst von seiner Position nach rechts (wie P-touch)."""
        family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
        return TextObject.plain(text, size_pt=self.settings.font_size_pt or DEFAULT_PT,
                                align="left", family=family)

    def edit_selected(self) -> None:
        """F2/Enter: Schreibmodus für das einzige gewählte Objekt, Schreibmarke am Textende."""
        selection = self.canvas.selection()
        if not self.edit_session.active and len(selection) == 1:
            self.edit_text(selection[0])

    def edit_text(self, index: int, point=None) -> None:
        """Schreibmodus für ein Objekt: auswählen, Text-Panel zeigen, Schreibmarke an
        ``point`` (QPointF, Druckpunkte in Leserichtung – z. B. Doppelklick) bzw. ans Ende.
        Bilder haben keinen Schreibmodus; bei Barcodes geht der Fokus ins Inhaltsfeld."""
        if 0 <= index < len(self.doc.objects) and isinstance(self.doc.objects[index],
                                                             BarcodeObject):
            self.finish_editing()
            if self.canvas.selection() != [index]:
                self.canvas.set_selection([index])
            self._show_tool("barcode")
            self.panel("barcode").focus_data()
            return
        if 0 <= index < len(self.doc.objects) and not isinstance(self.doc.objects[index],
                                                                 TextObject):
            return
        if self.edit_session.active:
            if self.edit_session.index == index:
                return
            self.finish_editing(drop_empty=False)   # entfällt gleich beim Wählen (Nummern!)
        if not self._valid(index):
            return
        if self.canvas.selection() != [index]:
            self.canvas.set_selection([index])
            index = self.canvas.selection()[-1]     # ggf. umnummeriert (leerer Rahmen entfiel)
        self._show_tool("text")
        if self.panel("series").preview() is not None:
            # Serie: das Objekt zeigt im Schreibmodus seine Platzhalter – vor der Schreibmarke
            # rendern, sonst passen Zeilensatz und Text nicht (die Lage wanderte beim Tippen);
            # die Klickstelle im gefüllten Text lässt sich nicht übertragen: Marke ans Ende
            self._keep, point = index, None
            try:
                self.render_now()
            finally:
                self._keep = None
        elif self._timer.isActive():
            self.render_now()                       # Klick trifft den aktuellen Zeilensatz
        self.edit_session.start(index, point)
        self._update_edit_actions()

    def finish_editing(self, drop_empty: bool = True) -> None:
        """Schreibmodus beenden (Esc, Klick daneben, anderes Werkzeug oder Reiter, Befehl auf
        der Auswahl); die ganze Bearbeitung wird ein Rückgängig-Schritt. Ein leer gebliebener
        Rahmen entfällt dabei – außer bei ``drop_empty=False``, wenn der Aufrufer gerade die
        Auswahl ändert (dann entfällt er dort, ``_on_selection``)."""
        index = self.edit_session.end()
        if index is None:
            return
        if (drop_empty and self._valid(index) and self.doc.objects[index].positioned
                and self.doc.objects[index].is_empty()):
            self.canvas.set_selection([])           # leerer Rahmen entfällt (_on_selection)
        self._commit()
        if self.panel("series").preview() is not None:
            self.render_now()                       # wieder die Werte statt der Platzhalter

    def delete_selected(self) -> None:
        """Ausgewählte Objekte löschen (auch das letzte – das Etikett ist dann leer)."""
        self.finish_editing()
        indices = self.canvas.selection()
        if not indices:
            return
        self._structure_changing()
        self._commit()
        for index in sorted(indices, reverse=True):
            del self.doc.objects[index]
        self.canvas.set_selection([])     # erst nach der Änderung: Auswahl davor bleibt im Stand
        self.render_now()
        self._commit()

    def _edit_frame(self, panel: str, key: str, value: float) -> None:
        """Zahl im Bereich „Position“ des Panels ``panel`` geändert: Objekt verschieben bzw.
        Rahmen ändern; ein Bild mit „Seitenverhältnis beibehalten“ ändert beide Maße."""
        self.finish_editing()
        index = self.panel(panel).index
        if index is None or not self._valid(index):
            return
        self._commit()
        obj = self._layout_object(index)
        exact = exact_rect(obj, self.rendered[index])
        if isinstance(obj, ImageObject) and obj.keep_ratio and key in "wh":
            rect = proportional(exact, key, round(value, 3))
        else:
            rect = replace(exact, **{key: round(value, 3)})
        self.doc.objects[index] = self._keep_content(index, set_frame(obj, rect,
                                                                      self.rendered[index]))
        self._objects_changed([index])
        self._commit()

    # --- Reiter „Layout“ ---------------------------------------------------
    def align_selected(self, mode: str, paper: bool = False) -> None:
        """Auswahl aneinander bzw. am bedruckbaren Bereich (mit Zierrahmen: an seinem
        Innenraum) ausrichten."""
        label = get_label(self.doc.label_id)
        min_length = length_limits(self.model)[0] * 25.4 / label.dpi
        self._change_selected(lambda objs, rendered: align_objects(
            objs, rendered, mode, self._paper_area() if paper else None, growing_axis(self.doc),
            min_length, self._unselected_rects()))

    def _unselected_rects(self) -> list[Rect]:
        """Rahmen (mm) der sichtbaren, nicht gewählten Objekte – nach dem Rendern aufrufen."""
        chosen = set(self.canvas.selection())
        return [exact_rect(self._layout_object(i), self.rendered[i])
                for i in range(len(self.doc.objects))
                if i not in chosen and self._valid(i) and not self.doc.objects[i].is_empty()]

    def _paper_area(self) -> Rect:
        """Fläche für „am Etikett“ (Ausrichten, Maximieren): Innenraum des Zierrahmens, sonst
        der bedruckbare Bereich."""
        return self._inner if self._inner is not None else self._area

    def match_selected(self, mode: str) -> None:
        """Größe, Breite oder Höhe an das zuerst gewählte Objekt angleichen."""
        self._change_selected(lambda objs, rendered: match_objects(objs, rendered, mode))

    def maximize_selected(self) -> None:
        """Jedes gewählte Objekt so groß wie möglich mittig in den bedruckbaren Bereich bzw. den
        Innenraum des Zierrahmens (auf Endlosband mit automatischer Länge nur quer –
        ``maximize_object``)."""
        self._change_selected(lambda objs, rendered: [
            maximize_object(obj, r, self._paper_area(), self.doc, self.model)
            for obj, r in zip(objs, rendered)])

    def rotate_selected(self, degrees: int) -> None:
        """Auswahl um 90° drehen (−90 = links); die Mitte jedes Objekts bleibt."""
        self._change_selected(lambda objs, rendered: [
            rotate(obj, r, degrees) for obj, r in zip(objs, rendered)])

    def _change_selected(self, change) -> None:
        """Gewählte Objekte durch ``change(objekte, gerendert)`` ersetzen – ein Schritt.

        ``change`` läuft nach dem Rendern: Rahmen und ``self._area`` sind aktuell."""
        self.finish_editing()
        if self._timer.isActive():
            self.render_now()                   # z. B. eben Getipptes: aktuelle Rahmen
        # leere Rahmen sind unsichtbar und drucken nicht: sie nehmen an Layout-Befehlen nicht teil
        indices = [i for i in self.canvas.selection()
                   if self._valid(i) and not self.doc.objects[i].is_empty()]
        if not indices:
            return
        self._commit()
        changed = change([self._layout_object(i) for i in indices],
                         [self.rendered[i] for i in indices])
        for index, obj in zip(indices, changed):
            self.doc.objects[index] = self._keep_content(index, obj)
        self._objects_changed(indices)
        self._commit()

    def _layout_object(self, index: int):
        """Objekt für Größe und Lage: Barcodes, wie sie die Arbeitsfläche zeigt (Serie: mit dem
        Wert der Vorschau-Zeile – ihre Breite folgt aus dem Inhalt), sonst das Objekt selbst."""
        obj = self.doc.objects[index]
        shown = self._shown_objects[index] if index < len(self._shown_objects) else obj
        if isinstance(obj, BarcodeObject) and isinstance(shown, BarcodeObject):
            return replace(obj, data=shown.data)   # nur der Inhalt: die Anzeige kann veraltet sein
        return obj

    def _keep_content(self, index: int, changed):
        """Ergebnis von Größe und Lage zurück ins Etikett: Barcodes behalten ihren Inhalt (mit
        Platzhaltern), nur Modul, Höhe, Lage und Drehung kommen aus ``changed``."""
        obj = self.doc.objects[index]
        if isinstance(obj, BarcodeObject) and isinstance(changed, BarcodeObject):
            return replace(changed, data=obj.data)
        return changed

    def set_color_selected(self, color: str) -> None:
        """Farbe der Auswahl (Reiter Layout; Rot nur auf Etiketten Rot/Schwarz)."""
        self._change_selected(lambda objs, rendered: [replace(obj, color=color) for obj in objs])

    def reorder_selected(self, step: int) -> None:
        """Auswahl einen Platz nach vorne (1) bzw. hinten (−1); die Auswahl wandert mit."""
        self.finish_editing()
        indices = self.canvas.selection()
        if not indices:
            return
        self._structure_changing()
        self._commit()
        self.doc.objects[:], moved = reorder(self.doc.objects, indices, step)
        self.render_now()
        self.canvas.set_selection(moved)
        self._commit()

    # --- Zwischenablage ---------------------------------------------------
    def copy_selected(self) -> None:
        """Ausgewählte Objekte (in Zeichenreihenfolge) in die interne Zwischenablage kopieren –
        im Schreibmodus den markierten Text in die Zwischenablage des Systems."""
        if self.edit_session.copy():
            self._update_edit_actions()             # Einfügen ist jetzt möglich
            return
        indices = sorted(self.canvas.selection())
        if indices:
            self._clipboard = [self._placed_copy(i) for i in indices]
            self._announce_copy()
            self._update_edit_actions()

    def _announce_copy(self) -> None:
        """Kopie in der Zwischenablage des Systems kennzeichnen (``MIME_OBJECTS`` mit eigener
        Kennung, dazu der Text der Textobjekte für andere Programme). Die Objekte selbst
        bleiben in der internen Zwischenablage; kopiert jemand danach etwas anderes, fügt
        Strg+V das ein."""
        self._clipboard_token = uuid.uuid4().hex
        mime = QMimeData()
        mime.setData(MIME_OBJECTS, self._clipboard_token.encode())
        text = "\n".join(obj.text for obj in self._clipboard
                         if isinstance(obj, TextObject) and not obj.is_empty())
        if text:
            mime.setText(text)
        QApplication.clipboard().setMimeData(mime)
        self._system = _ClipboardState(token=self._clipboard_token, text=bool(text),
                                       empty=False)    # auch ohne (verspätetes) dataChanged

    def cut_selected(self) -> None:
        if not self.edit_session.cut():
            self.copy_selected()
            self.delete_selected()

    def paste(self) -> None:
        """Einfügen, was die Zwischenablage des Systems oben hat, in dieser Reihenfolge:
        hier kopierte Objekte (jedes Mal 2 mm weiter versetzt; ist die Zwischenablage leer,
        die zuletzt kopierten) › lokale Dateien (wie „Aus Datei“) › Text (neuer Textrahmen –
        auch wenn ein Bild dabei ist, z. B. Tabellenzellen; das Bild bleibt über „Aus
        Zwischenablage“ erreichbar) › Bild (Mitte des bedruckbaren Bereichs). Eingefügtes ist
        ausgewählt. Im Schreibmodus Text in den Text (als reiner Text). Nur hier werden die
        Daten der Zwischenablage gelesen."""
        if self._parcel_blocks():
            return
        if self.edit_session.paste():
            return
        if self._owns_clipboard() or (self._clipboard and self._system.empty):
            self._clipboard = [_offset(obj) for obj in self._clipboard]
            self._insert(copy.deepcopy(self._clipboard))
            return
        mime = QApplication.clipboard().mimeData()
        if paths := image_import.mime_files(mime):
            self.insert_image_files(paths)
        elif text := image_import.mime_text(mime):
            self._paste_text(text)
        elif (image := image_import.mime_image(mime)) is not None:
            self._insert_picture(image, CLIPBOARD)

    def _owns_clipboard(self) -> bool:
        """Liegt die zuletzt hier kopierte Auswahl oben in der Zwischenablage des Systems?"""
        return bool(self._clipboard) and self._system.token == self._clipboard_token

    def _can_paste(self) -> bool:
        system = self._system
        return (self._owns_clipboard() or (bool(self._clipboard) and system.empty)
                or system.files or system.text or system.image)

    def _clipboard_changed(self) -> None:
        """Zwischenablage des Systems geändert: Stand einmal merken (ohne Bild- und Textdaten
        zu holen – die liest erst ``paste``), Knöpfe „Einfügen“ und „Aus Zwischenablage“."""
        self._system = _ClipboardState.of(QApplication.clipboard().mimeData())
        self._text_pastes = 0
        self.panel("image").set_clipboard_image(self._system.image)
        self._update_edit_actions()

    def _paste_text(self, text: str) -> None:
        """Text aus der Zwischenablage als neuer Textrahmen links oben im bedruckbaren
        Bereich (wie „Text anlegen“), ausgewählt – ohne Schreibmodus. Derselbe Text noch
        einmal eingefügt: jedes Mal 2 mm weiter versetzt (wie Objekte)."""
        if self._timer.isActive():
            self.render_now()                       # aktueller bedruckbarer Bereich
        obj = self._new_text(text)
        shift = self._text_pastes * PASTE_OFFSET_MM
        area = self._paper_area()                   # mit Zierrahmen: in seinem Innenraum
        obj.x_mm, obj.y_mm = round(area.x + shift, 3), round(area.y + shift, 3)
        self._text_pastes += 1
        self._insert([obj])

    def duplicate_selected(self) -> None:
        """Auswahl 2 mm versetzt verdoppeln; die Zwischenablage bleibt unberührt."""
        indices = sorted(self.canvas.selection())
        if indices:
            self._insert([_offset(self._placed_copy(i)) for i in indices])

    def _placed_copy(self, index: int) -> TextObject | ImageObject:
        """Kopie mit Position: ein mittiges Objekt bekommt seine Lage und Schriftgröße fest."""
        obj = self.doc.objects[index]
        if obj.positioned or index >= len(self.rendered):
            return copy.deepcopy(obj)
        rendered = self.rendered[index]
        return move(obj, object_rect(rendered), rendered)

    def _insert(self, objects: list[TextObject | ImageObject]) -> None:
        self.finish_editing()
        self._structure_changing()
        self._commit()
        start = len(self.doc.objects)
        self.doc.objects.extend(objects)
        self._objects_changed(list(range(start, len(self.doc.objects))))
        self.canvas.set_selection(list(range(start, len(self.doc.objects))))
        self._commit()

    # --- Bilder einfügen ---------------------------------------------------
    def insert_image_file(self) -> None:
        """„Bild einfügen …“: Datei wählen; das Bild kommt in die Mitte des bedruckbaren
        Bereichs."""
        path = self.ask_image_file()
        if path:                                    # im Dialog gewählte PDF-Seite: keine Seitenfrage
            self.insert_image_files([Path(path)], page=getattr(path, "page", None))

    def ask_image_file(self) -> str | None:
        """Dateidialog „Bilder und PDF“ mit Vorschau (in Tests ersetzbar); None = abgebrochen.
        Ergebnis ``file_dialog.Chosen``: Pfad, bei PDF evtl. mit gewählter Seite (``page``)."""
        path = file_dialog.ask_open(self, _("Insert image"), self._image_dir,
                                    image_import.file_filter(),
                                    system=self.system_dialog, pages=True,
                                    model=self.model)
        if path:
            self._image_dir = str(Path(path).parent)
        return path

    def ask_pdf_page(self, path: Path, count: int) -> int | None:
        """Seitenwahl für ein PDF mit mehreren Seiten (in Tests ersetzbar); None = abgebrochen."""
        page, ok = QInputDialog.getInt(self, _("Choose PDF page"),
                                       _("{name} has {count} pages. Which one to insert?").format(
                                           name=path.name, count=count),
                                       1, 1, count)
        return page if ok else None

    def insert_image_files(self, paths: list, at: tuple[float, float] | None = None,
                           page: int | None = None) -> None:
        """Bilddateien einfügen – mittig auf ``at`` (mm, Ablagepunkt) bzw. in der Mitte des
        bedruckbaren Bereichs. Bei einem PDF mit mehreren Seiten wird die Seite erfragt
        (``page`` gibt sie vor). Fehler stehen verständlich in der Statusleiste; was sich
        laden ließ, wird eingefügt (ein Schritt)."""
        if self._parcel_blocks():
            return
        objects, notes, failed = [], [], False
        for path in map(Path, paths):
            pdf = path.suffix.lower() == ".pdf"
            try:
                number = page or (self._choose_page(path) if pdf else 1)
                if number is None:
                    continue                        # Seitenwahl abgebrochen
                image, dpi = image_import.load(path, number)
                svg = image_import.load_vector(path)
            except (ValueError, OSError) as e:
                notes.append(str(e))
                failed = True
                continue
            objects.append(self._new_image(image, dpi, path.name, number if pdf else None, notes,
                                           svg))
        self._insert_images(objects, at, notes, "error" if failed else "warn")

    def _choose_page(self, path: Path) -> int | None:
        count = image_import.page_count(path)
        return 1 if count <= 1 else self.ask_pdf_page(path, count)

    def paste_image(self) -> None:
        """„Aus Zwischenablage“: Bild der Zwischenablage in die Mitte des bedruckbaren Bereichs."""
        image = image_import.mime_image(QApplication.clipboard().mimeData())
        if image is None:
            self._show_notice([_(NO_CLIPBOARD_IMAGE)], "error")
            return
        self._insert_picture(image, CLIPBOARD)

    # --- Bildschirmfoto ------------------------------------------------------
    def _screenshot_portal(self) -> ScreenshotPortal:
        if self._portal is None:
            self._portal = ScreenshotPortal(parent=self)
            self._portal.finished.connect(self.screenshot_finished)
        return self._portal

    def screenshot_available(self) -> bool:
        """Gibt es das Bildschirmfoto-Portal? (in Tests ersetzbar)"""
        return self._screenshot_portal().available()

    def take_screenshot(self) -> None:
        """Auswahl des Desktops öffnen; die Antwort kommt über ``screenshot_finished`` (in
        Tests ersetzbar)."""
        self._screenshot_portal().take()

    def insert_screenshot(self) -> None:
        """„Bildschirmfoto“ wie P-touch: labelwerk geht aus dem Weg, der Desktop zeigt seine
        Auswahl (Bereich, Fenster, Bildschirm), danach liegt das Bild auf dem Etikett.
        Ohne Portal bleibt das Fenster und ein Hinweis nennt den Weg über die Zwischenablage."""
        if self._shooting:
            return
        self.finish_editing()
        if not self.screenshot_available():
            self._show_notice([_(NO_SCREENSHOT)], "error")
            return
        self._shooting = self._shot_pending = True
        self.shortcut_actions["image.screenshot"].setEnabled(False)
        # das Symbol-Fenster ist eigenes Fenster: mit ausblenden, sonst ist es mit auf dem Foto
        self._symbols_were_open = self.symbol_window is not None and self.symbol_window.isVisible()
        if self._symbols_were_open:
            self.symbol_window.hide()
        # ausgeblendet ist kein Fenster mehr sichtbar: schlösse sich jetzt ein anderes, endete
        # die App sonst
        app = QApplication.instance()
        self._quit_on_close = app.quitOnLastWindowClosed()
        app.setQuitOnLastWindowClosed(False)
        self.hide()
        self._hide_timer.start(HIDE_DELAY_MS)

    def _take_hidden(self) -> None:
        """Fenster ist weg: Auswahl öffnen; ohne Antwort kommt das Fenster nach
        ``RESTORE_TIMEOUT_MS`` trotzdem wieder. Ein unerwarteter Fehler lässt das Fenster nie
        verschwunden."""
        self._restore_timer.start(RESTORE_TIMEOUT_MS)
        try:
            self.take_screenshot()
        except Exception as e:  # Fenster sofort zurück; Meldung statt Traceback
            self.screenshot_finished(None, f"{_(SCREENSHOT_FAILED)} – {e}")

    def screenshot_finished(self, path: Path | None, error: str | None) -> None:
        """Antwort des Portals: Pfad → einfügen (300 dpi: 1 Bildschirmpixel = 1 Druckpunkt, wie
        aus der Zwischenablage), Meldung → Statusleiste, (None, None) = abgebrochen. Es zählt
        nur die erste Antwort je Aufnahme – auch eine nach der Zeitüberschreitung (kommt sie
        erst während der nächsten Aufnahme, gilt sie für diese, und die entfällt)."""
        if not self._shot_pending:
            return
        self._shot_pending = False
        self._show_again()
        if error is not None:
            self._show_notice([error], "error")
            return
        if path is None:
            return
        try:
            image, dpi = image_import.load_screenshot(Path(path))
        except (ValueError, OSError) as e:
            self._show_notice([_("Screenshot: {error}").format(error=e)], "error")
            return
        self._insert_picture(image, SCREENSHOT, dpi=dpi)

    def _show_again(self) -> None:
        """Nach dem Bildschirmfoto (oder ohne Antwort nach ``RESTORE_TIMEOUT_MS``): Fenster
        zeigen und nach vorn holen, Aktion wieder frei."""
        self._restore_timer.stop()
        if not self._shooting:
            return
        self._end_shooting()
        self.show()
        if self._symbols_were_open:
            self.symbol_window.show()
            self._symbols_were_open = False
        self.raise_()
        self.activateWindow()

    # --- Symbole -------------------------------------------------------------
    def open_symbols(self) -> None:
        """Fenster „Symbol einfügen“ zeigen (eine Instanz, bleibt offen)."""
        self.finish_editing()
        if self.symbol_window is None:
            try:
                self.symbol_window = SymbolDialog(self.settings.symbols_recent,
                                                  self.settings.symbols_favorites, self)
            except LIBRARY_ERRORS as e:
                self._library_unreadable(e)
                return
            self.symbol_window.chosen.connect(lambda symbol: self.insert_symbol(symbol))
            self.symbol_window.favorites_changed.connect(self._favorites_changed)
        self.symbol_window.show()
        self.symbol_window.raise_()
        self.symbol_window.activateWindow()

    def insert_symbol(self, symbol: clipart.Symbol, at: tuple[float, float] | None = None) -> None:
        """Symbol als Bild-Objekt einfügen: längere Seite ``SYMBOL_MM`` (höchstens quer zum
        Band bedruckbar), auf den Inhalt zugeschnitten, Strich, Vektor wenn SVG; Platzierung wie
        Bilder; danach „Zuletzt verwendet“."""
        if self._parcel_blocks():
            return
        if self._timer.isActive():
            self.render_now()                       # aktueller bedruckbarer Bereich
        try:
            image, dpi, crop, svg = image_import.load_symbol(symbol, self._symbol_mm())
        except (ValueError, OSError, KeyError, zipfile.BadZipFile,
                Image.DecompressionBombError) as e:
            self._show_notice([_("Symbol: {error}").format(error=e)], "error")
            return
        obj = ImageObject.from_image(image, dpi, SYMBOL_SOURCE.format(name=symbol.name),
                                     crop=crop, svg=svg)
        # Größe passt schon quer zum Band – Drehen nach Einstellung gilt für Symbole nicht
        self._insert_images([obj], at, [] if crop is not None else [_(CROP_FAILED)], rotate=False)
        self.settings.symbols_recent = clipart.add_recent(self.settings.symbols_recent, symbol.id)
        self._save_settings("symbols_recent")
        if self.symbol_window is not None:
            self.symbol_window.set_recent(self.settings.symbols_recent)

    def _symbol_mm(self) -> float:
        """Größe neuer Symbole: ``SYMBOL_MM``, höchstens der bedruckbare Bereich quer zum Band
        (in der mitwachsenden Achse begrenzt das Etikett nicht)."""
        grow = growing_axis(self.doc)
        area = self._paper_area()                   # mit Zierrahmen: sein Innenraum
        cross = area.h if grow == "x" else area.w if grow == "y" else min(area.w, area.h)
        return max(1.0, math.floor(min(SYMBOL_MM, cross) * 1000) / 1000)   # nie knapp zu groß

    # --- Barcodes ------------------------------------------------------------
    def insert_barcode(self) -> None:
        """Barcode der im Reiter gewählten Art mit Beispielinhalt einfügen (``layout.new_barcode``:
        mittig im Innenraum bzw. bedruckbaren Bereich, lieber gedreht als kleiner; auf einem
        Endlosband hinter den vorhandenen Objekten) – ausgewählt, der Inhalt markiert im Fokus:
        Tippen ersetzt das Beispiel."""
        if self._parcel_blocks():
            return
        self.finish_editing()
        if self._timer.isActive():
            self.render_now()                       # aktueller bedruckbarer Bereich
        others = [object_rect(r) for o, r in zip(self.doc.objects, self.rendered)
                  if not o.is_empty()]
        obj = new_barcode(self.doc, self.model, self._paper_area(),
                          self.panel("barcode").chosen_kind(), others)
        self._insert([obj])
        self._show_tool("barcode")
        self.panel("barcode").focus_data()

    def _filled_barcode(self, obj: BarcodeObject) -> BarcodeObject:
        """Barcode mit dem Wert der Vorschau-Zeile (Prüfhinweis im Panel); ohne Serie er selbst."""
        row = self.panel("series").preview()
        return obj if row is None else series.fill(Document(objects=[obj]), *row).objects[0]

    def _symbol_dropped(self, symbol_id: str, x_mm: float, y_mm: float) -> None:
        try:
            symbol = clipart.find(symbol_id)
        except LIBRARY_ERRORS as e:
            self._library_unreadable(e)
            return
        if symbol is not None:
            self.insert_symbol(symbol, at=(x_mm, y_mm))

    def _library_unreadable(self, error: Exception) -> None:
        """Archiv der Symbol-Bibliothek fehlt oder ist beschädigt: Meldung statt Traceback."""
        self._set_result(_("Symbol library unreadable: {error}").format(error=error), "error")

    def _favorites_changed(self, favorites: list[str]) -> None:
        self.settings.symbols_favorites = list(favorites)
        self._save_settings("symbols_favorites")

    def _save_settings(self, *keys: str) -> None:
        """Einstellungen still speichern (Zuletzt verwendet, Favoriten, Drucker …): nur die Felder
        ``keys`` (``update_settings`` – was eine zweite Instanz gespeichert hat, bleibt); ohne
        ``keys`` alles. Fehler in die Statusleiste."""
        try:
            if keys:
                update_settings(base=self.settings, **{key: getattr(self.settings, key) for key in keys})
            else:
                save_settings(self.settings)
                self._stored_tool = self.settings.last_tool
        except OSError as e:
            self._set_result(str(e), "error")

    def _end_shooting(self) -> None:
        self._shooting = False
        self._hide_timer.stop()
        self.shortcut_actions["image.screenshot"].setEnabled(True)
        QApplication.instance().setQuitOnLastWindowClosed(self._quit_on_close)

    def _dropped(self, paths: list[Path], image: Image.Image | None, x_mm: float,
                 y_mm: float) -> None:
        """Bilddateien oder Bilddaten auf die Arbeitsfläche abgelegt: an der Ablagestelle
        (kommt nach dem Ablegen, ``Canvas.dropped`` – ein PDF-Seitendialog ist dann möglich).
        Im Reiter PAKET lädt eine abgelegte Datei die Marke, Bilddaten ändern nichts."""
        if self._parcel_shown() and paths:
            self.panel("parcel").load(paths[0])
            return
        if self._parcel_blocks():
            return
        if paths:
            self.insert_image_files(paths, at=(x_mm, y_mm))
        elif image is not None:
            self._insert_picture(image, DROPPED, at=(x_mm, y_mm))

    def _insert_picture(self, image: Image.Image, source: str,
                        at: tuple[float, float] | None = None, dpi: float = DPI) -> None:
        """Bild ohne Auflösungsangabe (Zwischenablage, Bilddaten, Bildschirmfoto) einfügen –
        300 dpi, also 1 Pixel = 1 Druckpunkt."""
        if self._parcel_blocks():
            return
        notes: list[str] = []
        self._insert_images([self._new_image(image, dpi, source, None, notes)], at, notes)

    def _new_image(self, image: Image.Image, dpi: float, source: str, page: int | None,
                   notes: list[str], svg: bytes | None = None) -> ImageObject:
        """Bild-Objekt 1:1, automatisch zugeschnitten (alles, was nicht weiß ist; Einstellung
        ``image_crop``); ist das Bild ganz weiß, bleibt es ganz – mit Hinweis in ``notes``.
        Mit ``svg`` ein Vektorbild (``image`` ist dessen Vorschau). Strich/Foto und Schwelle aus
        den Einstellungen (``image_mode``, ``image_threshold``)."""
        crop = None
        if self.settings.image_crop:
            crop = crop_box(image, dpi, ink=NOT_WHITE)
            if crop is None and _(CROP_FAILED) not in notes:
                notes.append(_(CROP_FAILED))
        obj = ImageObject.from_image(image, dpi, source, page, crop, svg)
        obj.mode, obj.threshold = self.settings.image_mode, self.settings.image_threshold
        return obj

    def _insert_images(self, objects: list[ImageObject], at: tuple[float, float] | None,
                       notes: list[str], state: str = "warn", rotate: bool | None = None) -> None:
        """Bilder platzieren (``layout.insert_placement``: mittig; passt ein Bild nur um 90°
        gedreht 1:1, kommt es mit Einstellung ``image_rotate`` gedreht; auf einem Endlosband mit automatischer Länge hinter den
        vorhandenen Objekten statt darüber, sonst wird ein zu großes proportional verkleinert und
        danach auf höchstens 600 dpi der neuen Größe begrenzt; mehrere je 2 mm versetzt) und
        einfügen – ein Schritt, ausgewählt."""
        if objects:
            if self._timer.isActive():
                self.render_now()                   # aktueller bedruckbarer Bereich
            smallest, shrunk_mode, turned = 1.0, "line", False
            # vorhandene Objekte: auf einem Endlosband kommt das Bild dahinter, nicht darüber
            others = [object_rect(r) for o, r in zip(self.doc.objects, self.rendered)
                      if not o.is_empty()]
            for number, obj in enumerate(objects):
                rect, rotation, factor = insert_placement(
                    self.doc, self.model, self._paper_area(), (obj.w_mm, obj.h_mm), at, others,
                    rotate=self.settings.image_rotate if rotate is None else rotate)
                others.append(rect)
                shift = number * PASTE_OFFSET_MM if at is not None or not growing_axis(
                    self.doc) else 0.0
                obj.x_mm, obj.y_mm = rect.x + shift, rect.y + shift
                obj.w_mm, obj.h_mm = (rect.h, rect.w) if rotation else (rect.w, rect.h)
                obj.rotation = rotation
                turned = turned or bool(rotation)
                if factor < 1:
                    objects[number] = obj.limit_resolution()
                if factor < smallest:
                    smallest, shrunk_mode = factor, obj.mode
            self._insert(objects)
            if turned:
                notes.append(_(TURNED_HINT))
            if smallest < 1:
                notes.append(shrunk_hint(smallest, shrunk_mode))
        self._show_notice(notes, state)

    def _show_notice(self, notes: list[str], state: str) -> None:
        """Meldungen zum Einfügen in der Statusleiste; ohne Meldung verschwindet eine ältere."""
        if notes:
            self._notice = " · ".join(notes)
            self._set_result(self._notice, state)
        elif self._notice is not None and self.result.text() == self._notice:
            self._set_result("", "")
            self._notice = None

    def _objects_changed(self, indices: list[int]) -> None:
        for key in OBJECT_PANELS:
            if self.panel(key).index in indices:
                self.panel(key).refresh()   # z. B. Anfasser schaltet feste Rahmengröße ein
        self.render_now()

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        if not self.canvas.is_dragging():   # beim Ziehen erst nach dem Loslassen rendern
            self.schedule_render()
            self._commit()                  # Doppelklick: automatische Länge

    def _length_drag_finished(self) -> None:
        self.render_now()
        self._commit()

    def _show_media_status(self, text: str, state: str) -> None:
        self.media_status.setProperty("state", state)
        self.media_status.style().polish(self.media_status)
        # lange Meldungen kürzen, damit das Druckergebnis daneben sichtbar bleibt
        metrics = self.media_status.fontMetrics()
        self.media_status.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight,
                                                     MEDIA_STATUS_MAX_PX - 24))
        self.media_status.setToolTip(text)
        self.media_status.setVisible(bool(text))

    def _set_result(self, text: str, state: str) -> None:
        self.result.setProperty("state", state)
        self.result.style().polish(self.result)
        self.result.setText(text)

    # --- Drucken ----------------------------------------------------------
    def refresh_printer(self) -> None:
        """Drucker suchen (USB in sysfs, eingetragene Netzwerkdrucker), den gewählten bzw. ersten
        nehmen, sein Modell übernehmen (``set_model``), Statusleiste aktualisieren; beim
        Erscheinen eines USB-Druckers ggf. Medium prüfen."""
        tip = ""
        try:
            direct = (usb_printers() + zebra_printers(dpi=self.settings.zebra_dpi)
                      + network_printers(network_entries(self.settings)))
            found = direct + cups_printers(direct, keep=self.settings.printer,
                                           office=self.settings.cups_all)
            busy = not any(p.source == "usb" for p in found) and brother_busy()
        except OSError:
            found, busy = None, False
        chosen = choose(found or [], self.settings.printer)
        switched = (self.printer is not None and chosen is not None
                    and chosen.uri != self.printer.uri)
        self.printers, self.printer = found or [], chosen
        if found is None:
            text = _("○ Printer status unknown")
        elif chosen is None and self.settings.printer:
            text = _("○ selected printer missing")
            tip = _("{printer} not found – switch it on or choose another one").format(
                printer=self.settings.printer)
        elif chosen is not None:
            text = f"● {chosen.name}"
            if chosen.model is None:
                text = _("● {name} (as {model})").format(name=chosen.name, model=self.model)
                tip = _("Model not recognized – choose a fallback model in the settings")
            elif not capabilities(chosen.model).tested:
                text = _("● {name} · untested").format(name=chosen.name)
                tip = f"{chosen.model}: {_(UNTESTED_HINT)}"
        elif busy:
            text = _("● Printer busy (another application)")
        else:
            text = _("○ no printer")
        self.printer_status.setText(text)
        self.printer_status.setToolTip(tip or _("Choose printer"))
        if chosen is not None and chosen.model and chosen.model != self.settings.last_model:
            self.settings.last_model = chosen.model     # gilt beim nächsten Start ohne Drucker
            self._save_settings("last_model")
        if not self._fixed_model:
            model = effective_model(chosen, self.settings.printer_model, self.settings.last_model)
            if model != self.model:
                self.set_model(model)
        self._update_media_button()
        if switched:                                # andere Rolle möglich: neu prüfen
            self.panel("paper").clear_media()
            self._printer_present = False
        present = chosen is not None and chosen.source == "usb"
        if present and not self._printer_present and self.settings.check_media_on_start:
            self._media_check_pending = True
        if not present:
            self._media_check_pending = False
            if self._printer_present:
                self.panel("paper").clear_media()
        self._printer_present = present
        self._run_pending_media_check()

    def _usb_uri(self) -> str | None:
        """Gewählter USB-Drucker (Medium prüfen); None = selbst suchen."""
        return self.printer.uri if self.printer is not None and self.printer.source == "usb" else None

    def _fill_printer_menu(self) -> None:
        """Menü am Druckerknopf: Automatisch, gefundene Drucker, Netzwerkdrucker eintragen."""
        menu = self.printer_menu
        menu.clear()
        auto = menu.addAction(_("Automatic (first found)"))
        auto.setCheckable(True)
        auto.setChecked(not self.settings.printer)
        auto.triggered.connect(lambda _=False: self.choose_printer(""))
        for printer in self.printers:
            untested = printer.model is not None and not capabilities(printer.model).tested
            action = menu.addAction(_("{name} – untested").format(name=printer.name) if untested
                                    else printer.name)
            action.setCheckable(True)
            action.setChecked(printer.uri == self.settings.printer)
            action.setToolTip(_(UNTESTED_HINT) if untested else printer.uri)
            action.triggered.connect(lambda _=False, uri=printer.uri: self.choose_printer(uri))
        if not self.printers:
            menu.addAction(_("No printer found")).setEnabled(False)
        menu.addSeparator()
        menu.addAction(_("Add network printer …"), self.open_settings)

    def choose_printer(self, uri: str) -> None:
        """Drucker wählen (URI; "" = automatisch) – gespeichert."""
        self.settings.printer = uri
        self._save_settings("printer")
        self.refresh_printer()

    def set_model(self, model: str) -> None:
        """Druckermodell gewechselt: Etiketten, Längen, Schnitt und Farben folgen; das offene
        Etikett bleibt – passt es nicht, steht das in der Statusleiste."""
        self.model = model
        self.canvas.set_model(model)
        self.panel("paper").set_model(model)
        self._update_cut_choices()
        self._fit_label()
        self.schedule_render()

    def _update_cut_choices(self) -> None:
        """Reiter SERIE: Schnitt nach dem Drucker – Brother: nach jedem/nur am Ende bzw. ohne
        Abschneider der Hinweis; CUPS: die Schnitt-Optionen seines Treibers; Zebra: der Modus."""
        panel = self.panel("series")
        chosen = self.settings.printer_options.get(self._options_key(), {})
        if self.model.startswith("cups:"):
            panel.set_driver_cuts(cups.queue_info(self.model[len("cups:"):]).cut_options, chosen)
        elif zpl.is_model(self.model):
            panel.set_driver_cuts((zpl.cut_option(),), chosen)
        else:
            panel.set_cutter(capabilities(self.model).cutter)
        self._update_tool_buttons()                 # SERIE: Schnitt-Optionen des Druckers

    def _options_key(self) -> str:
        """Unter diesem Schlüssel stehen die Druck-Optionen in den Einstellungen: das Modell
        („cups:NAME“ bzw. „zpl:203“ – die Nummer lpN eines USB-Geräts wechselt beim Einstecken)."""
        return self.model

    def _driver_cut_chosen(self, key: str, value: str) -> None:
        """Schnitt-Option bzw. Modus gewählt – gilt für diesen Drucker (Einstellungen)."""
        if self.model.startswith("cups:") or zpl.is_model(self.model):
            self.settings.printer_options.setdefault(self._options_key(), {})[key] = value
            self._save_settings("printer_options")

    def _fit_label(self) -> None:
        """Passt das Etikett nicht zum Modell: ein neues, unberührtes Etikett nimmt ein passendes
        (``FileSession.fitting_label``), sonst bleibt es mit Hinweis (Datei, Favorit, Änderungen)."""
        label = self.doc.label_id
        if label in {lbl.id for lbl in labels_for_model(self.model)}:
            return
        if self.files.may_follow_roll() and not self.files.modified():
            change_label(self.doc, self.files.fitting_label(label))
            self.panel("paper").refresh()
            self.history.reset(self.doc)            # unberührt: kein Schritt zurück zum Unpassenden
            self.files.mark_unchanged()
            self._set_result(_("Label {label} does not fit the {model} – using {new}").format(
                label=get_label(label).description, model=self.model,
                new=get_label(self.doc.label_id).description), "warn")
            return
        self._set_result(_("Label {label} does not fit the printer ({model}) – choose another one "
                           "in the Paper tab").format(label=get_label(label).description,
                                                      model=self.model), "error")

    def _run_pending_media_check(self) -> None:
        """Automatische Prüfung nachholen, sobald weder Druck noch Prüfung laufen."""
        if self._media_check_pending and not self.is_printing() and not self.is_checking_media():
            self._media_check_pending = False
            self.check_media()

    def start(self, path: str | None = None) -> None:
        """Nach dem Öffnen des Fensters: Datei aus der Befehlszeile, sonst der Start-Favorit
        (als neues Etikett), sonst bleibt das leere Etikett."""
        if path:
            self.files.open(path, ask=False)
            return
        name = self.settings.start_favorite
        if name:
            favorite = favorites.find(name)
            if favorite is None:
                self._set_result(_("Start favorite “{name}” not found – empty label").format(
                    name=name), "error")
            else:
                self.files.open_favorite(favorite)

    def closeEvent(self, event) -> None:
        if not self.files.maybe_save():
            event.ignore()                          # Abbrechen: Fenster bleibt offen
            return
        self._printer_timer.stop()
        if self.symbol_window is not None:
            self.symbol_window.close()              # sonst hielte es die App offen
        self._restore_timer.stop()
        self._shot_pending = False                  # keine Auswahl und kein Einfügen mehr
        if self._shooting:
            self._end_shooting()
        if self.settings.last_tool != self._stored_tool:   # zuletzt benutzter Reiter, still
            try:
                update_settings(base=self.settings, last_tool=self.settings.last_tool)
                self._stored_tool = self.settings.last_tool
            except OSError:
                pass                                # beim Beenden: nichts mehr zu melden
        super().closeEvent(event)

    # --- Einstellungen ----------------------------------------------------
    def apply_theme_icons(self) -> None:
        """Symbole, die vom Design abhängen (weiß auf schwarz nur bei RawBlock)."""
        dark = self.settings.theme == "rawblock"
        for panel in self._panel_by_key.values():
            panel.set_icon_style(dark)
        for entry in EDIT_BAR:
            if entry is not None:
                self.shortcut_actions[entry[0]].setIcon(line_icon(entry[1], dark, hover=True))

    def apply_font_list(self) -> None:
        """Schriftauswahl im Reiter Text: kurze Liste oder alle (Einstellung „Alle Schriften“)."""
        if "text" in self._panel_by_key:
            self._panel_by_key["text"].family.set_families(fonts.families(all=self.settings.fonts_all))

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, model=self.model, parent=self, started=self._started)
        accepted = dialog.exec() == SettingsDialog.DialogCode.Accepted
        saved = dialog.saved
        dialog.deleteLater()                    # nicht bis zum Schließen des Fensters behalten
        if accepted and saved is not None:
            # während der Dialog offen war, kann sich Drucker/letztes Modell geändert haben
            saved.printer, saved.last_model = self.settings.printer, self.settings.last_model
            saved.printer_options = self.settings.printer_options
            saved.last_tool = self.settings.last_tool
            if saved.printer.startswith(("tcp://", "zpl+tcp://")) and saved.printer not in {
                    p.uri for p in network_printers(network_entries(saved))}:
                saved.printer = ""                  # Netzwerkdrucker entfernt/geändert: automatisch
            hidden_changed = set(saved.hidden_tools) != set(self.settings.hidden_tools)
            self.settings = saved
            self._save_settings()
            from PySide6.QtWidgets import QApplication
            from .app import apply_theme
            apply_theme(QApplication.instance(), self.settings.theme)
            self.apply_theme_icons()
            QTimer.singleShot(0, self, lambda: self.fit_toolbars(resize=False))   # neues Design messen
            self.apply_font_list()
            self.apply_hidden_tools(fall_back=hidden_changed)
            apply_shortcuts(self.shortcut_actions,
                            without_conflicts(effective(self.settings.shortcuts))[0])
            self.files.refresh_lists()                  # „Beim Start“ im Reiter Datei
            self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
            self.refresh_printer()                      # Netzwerkdrucker, Ersatzmodell
            self._set_result(_("Settings saved – they apply to new labels."), "ok")

    # --- Medium prüfen ----------------------------------------------------
    def is_printing(self) -> bool:
        return self._printing

    def is_checking_media(self) -> bool:
        return self._media_signals is not None

    def check_media(self) -> None:
        if self.is_printing() or self.is_checking_media():
            return
        self._media_uri = self._usb_uri()
        worker = MediaWorker(self.model, self._media_uri)
        self._media_signals = worker.signals
        worker.signals.found.connect(self._media_found)
        worker.signals.failed.connect(self._media_failed)
        self.panel("paper").set_checking(True)
        QThreadPool.globalInstance().start(worker)

    def _media_found(self, media, label_id) -> None:
        """Rolle erkannt: ein neues Etikett folgt ihr (war es unberührt, bleibt es das); eine
        geöffnete Datei oder ein Favorit bleibt bei ihrem Etikett – das Panel zeigt „passt nicht“."""
        self._media_finished()
        if self._media_uri != self._usb_uri():      # inzwischen anderer Drucker: Rolle gilt nicht
            return
        adjusted = (label_id is not None and label_id != self.doc.label_id
                    and self.files.may_follow_roll())
        if adjusted:
            unchanged = not self.files.modified()
            editing = self.edit_session.active
            if editing:     # Stand vor der Bearbeitung mit neuer Rolle: eigener Schritt davor
                before = self.history.current()
                change_label(before, label_id)
            change_label(self.doc, label_id)
            self.panel("paper").refresh()
            self.schedule_render()
            if editing:
                self.history.push(before, selection=self.history.selection)
                self._update_edit_actions()
            else:
                self._commit()
            if unchanged:
                self.files.mark_unchanged()
        self.panel("paper").show_media(media, label_id, adjusted)

    def _media_failed(self, message: str) -> None:
        self._media_finished()
        self.panel("paper").show_media_error(message)

    def _media_finished(self) -> None:
        self._media_signals = None
        self.panel("paper").set_checking(False)
        self._run_pending_media_check()

    def confirm_outside(self) -> bool:
        answer = QMessageBox.question(
            self, _("Object sticks out"),
            _("An object extends beyond the label and will be cut off. Print anyway?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def confirm_empty(self) -> bool:
        answer = QMessageBox.question(
            self, _("Empty label"), _("The label is empty. Print anyway?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        return answer == QMessageBox.StandardButton.Yes

    def accept_pending_input(self) -> None:
        """Eben getippte Zahl übernehmen: Zahlenfelder ohne Tastatur-Mitlauf und editierbare
        Auswahllisten (Schriftgröße) melden ihren Wert erst bei Enter oder beim Verlassen –
        DRUCKEN in der Werkzeugleiste und Kürzel nehmen den Fokus nicht. Vor Drucken, Speichern
        und Rückgängig aufrufen."""
        widget = QApplication.focusWidget()
        if isinstance(widget, QLineEdit) and isinstance(widget.parent(), QComboBox):
            widget = widget.parent()
        if isinstance(widget, QAbstractSpinBox):
            widget.interpretText()
        elif isinstance(widget, QComboBox) and widget.isEditable():
            widget.lineEdit().editingFinished.emit()

    def print_label(self) -> None:
        self.accept_pending_input()
        if self._parcel_locked():                   # Reiter PAKET mit Marke: nur sie drucken
            panel = self.panel("parcel")
            if panel.documents():
                self.print_documents(panel.documents())   # was die Arbeitsfläche zeigt
            else:
                self._set_result(panel.error or _(PARCEL_CHOOSE_TYPE), "error")
            return
        if self._timer.isActive():
            self.render_now()
        if self.doc.series is not None:             # rendert jede Zeile selbst (Fehler: „Zeile n“)
            panel = self.panel("series")
            if panel.check_file():                  # Tabelle draußen geändert: Auswahl ist neu
                self.render_now()
                self._set_result(_("Series: {error}").format(error=panel.error) if panel.error
                                 else _("The table has changed and was read again – check the "
                                        "selection and print again."), "error")
                return
            if panel.error:
                self._set_result(_("Series: {error}").format(error=panel.error), "error")
                return
            self._print_series(self.doc, panel.table, panel.checked_rows())
            return
        if self._render_error is not None:
            self._set_result(self._render_error, "error")   # nicht still nichts tun
            return
        if self.image is None:
            return
        self._print(self.image, self.doc, self._outside)

    def _print_series(self, doc: Document, table: series.Table,
                      rows: list[tuple[int, list[str]]]) -> None:
        """Gewählte Zeilen drucken: erst Rolle/Druck prüfen und nach der Anzahl fragen, dann
        jede Zeile rendern (Fortschritt in der Statusleiste), Zeilen, die über das Etikett
        ragen, nennen und fragen – ein Auftrag. Scheitert eine Zeile, wird nichts gedruckt."""
        if not table.rows:
            self._set_result(_("The table has no rows – nothing printed."), "error")
            return
        if not rows:
            self._set_result(_("No row selected – nothing printed."), "error")
            return
        if self.is_checking_media():
            self._set_result(_(CHECKING_ROLL), "error")
            return
        if self.is_printing():
            self._set_result(_(PRINTING_WAIT), "error")
            return
        if not self._can_print(doc):
            return
        if not self.ask_print_count(len(rows)):
            return
        model, printer = self.model, self.printer   # gilt für die ganze Serie
        images, outside = [], []
        doc = copy.deepcopy(doc)                    # Eingaben während des Vorbereitens zählen nicht
        renderer = Renderer()                       # unveränderte Objekte aus dem Cache
        red = get_label(doc.label_id).two_color and capabilities(model).two_color
        self._set_printing(True)                    # gesperrt, solange vorbereitet wird
        self._cancel_requested = False
        self.cancel_button.setVisible(len(rows) > 1)
        try:
            for done, (number, values) in enumerate(rows):
                if done % PROGRESS_EVERY == 0 and len(rows) > PROGRESS_EVERY:
                    self._set_result(_("Preparing {current}/{total} …").format(
                        current=done + 1, total=len(rows)), "")
                    QApplication.processEvents()    # auch „Abbrechen“
                    if self._cancel_requested:
                        self._set_result(_("Cancelled – nothing printed"), "")
                        return
                try:
                    result = renderer.render(fill_anchored(doc, table.columns, values, model),
                                             model)
                except ValueError as e:
                    self._set_result(_("Row {row}: {message}").format(row=number, message=e), "error")
                    return
                if outside_indices(result.objects, result.size, doc.objects):
                    outside.append(number)
                images.append(to_print_mode(result.image, red))   # 1 Bit: wenig Speicher
        finally:
            self._set_printing(False)
            self.cancel_button.hide()
        if outside and not self.confirm_outside_rows(outside):
            self._set_result("", "")
            return
        cut = doc.series.cut if capabilities(model).cutter else "each"   # ohne Abschneider: kleine Teile
        self._print(images, doc, [], cut_interval(cut, len(images)), model, printer)

    def confirm_outside_rows(self, numbers: list[int]) -> bool:
        """Rückfrage: Zeilen, in denen etwas über das Etikett ragt (in Tests ersetzbar)."""
        shown = ", ".join(map(str, numbers[:10])) + (" …" if len(numbers) > 10 else "")
        text = ngettext("Row {rows} extends beyond the label and will be cut off. Print anyway?",
                        "Rows {rows} extend beyond the label and will be cut off. Print anyway?",
                        len(numbers)).format(rows=shown)
        return QMessageBox.question(
            self, _("Object sticks out"), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def ask_print_count(self, count: int) -> bool:
        """Rückfrage vor dem Drucken einer Serie (in Tests ersetzbar)."""
        text = ngettext("Print {count} label?", "Print {count} labels?", count).format(count=count)
        return QMessageBox.question(
            self, _("Print series"), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes

    def print_document(self, doc: Document) -> None:
        """Anderes Etikett drucken (Favorit), ohne das offene anzutasten – gleiche Rückfragen;
        mit Serie alle Zeilen."""
        if self.is_printing():
            self._set_result(_(PRINTING_WAIT), "error")
            return
        if doc.series is not None:
            try:
                table = series.table_for(doc.series)
            except ValueError as e:                  # SeriesError
                self._set_result(str(e), "error")
                return
            except Exception as e:  # fremde Datei: Meldung statt Traceback
                self._set_result(_("Cannot read the series ({error})").format(
                    error=type(e).__name__), "error")
                return
            self._print_series(doc, table, list(enumerate(table.rows, start=1)))
            return
        try:
            image = render_document(doc, self.model)
            outside = objects_outside(doc, self.model)
        except ValueError as e:
            self._set_result(str(e), "error")
            return
        except Exception as e:  # fremde Datei: Meldung statt Traceback
            self._set_result(_("Cannot print the label ({error})").format(
                error=type(e).__name__), "error")
            return
        self._print(image, doc, outside)

    def _can_print(self, doc: Document) -> bool:
        """Vor dem Rendern prüfbar: gewählter Drucker da, Etikett passt zum Modell (Meldung)."""
        if self.printer is None and self.settings.printer:
            self._set_result(_("Selected printer not found – switch it on or choose another one "
                               "in the status bar."), "error")
            return False
        if self.printer is None and not printers_mod.brother_model(self.model):
            self._set_result(_("No printer for this label – choose a printer in the status bar."),
                             "error")
            return False
        if doc.label_id not in {label.id for label in labels_for_model(self.model)}:
            self._set_result(_("Label “{label}” does not fit the printer ({model}).").format(
                label=doc.label_id, model=self.model), "error")
            return False
        return True

    def _print(self, image, doc: Document, outside: list[int], cut_every: int = 1,
               model: str | None = None, printer: Printer | None = None) -> None:
        """``image``: ein Druckbild oder eine Liste (Serie, ein Auftrag); ``model``/``printer``:
        festgehalten beim Start einer Serie (sonst die jetzigen)."""
        if self.is_checking_media():
            self._set_result(_(CHECKING_ROLL), "error")
            return
        if model is None:
            if not self._can_print(doc):
                return
            model, printer = self.model, self.printer
        # Druck sperrt die Medium-Prüfung schon vor dem Dialog (Timer läuft währenddessen weiter)
        self._set_printing(True)
        if doc.is_empty() and not self.confirm_empty():
            self._set_printing(False)
            return
        if outside and not self.confirm_outside():
            self._set_printing(False)
            return
        self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
        self.result.style().polish(self.result)
        self.result.setText(_("Printing …"))
        options = (self.settings.printer_options.get(model, {})
                   if model.startswith("cups:") or zpl.is_model(model) else {})
        worker = PrintWorker(image, doc.label_id, model, cut_every,
                             printer=printer.uri if printer else None, options=options)
        self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
        self._worker = worker
        worker.signals.done.connect(self._print_done)
        worker.signals.failed.connect(self._print_failed)
        worker.signals.progress.connect(
            lambda done, total: self._set_result(
                _("Printing … {done} of {total}").format(done=done, total=total), ""))
        worker.signals.cancelled.connect(self._print_cancelled)
        # übers Netz geht eine Serie als ein Auftrag hinaus (kein Status): nichts abzubrechen
        self.cancel_button.setVisible(isinstance(image, list) and len(image) > 1
                                      and (printer is None or printer.source == "usb"))
        QThreadPool.globalInstance().start(worker)

    def cancel_print(self) -> None:
        """„Abbrechen“: beim Vorbereiten sofort (nichts gedruckt), beim Drucken vor dem nächsten
        Teilauftrag."""
        self._cancel_requested = True
        if self._worker is not None:
            self._worker.cancel()
            self._set_result(_("Cancelling …"), "")

    def _set_printing(self, printing: bool) -> None:
        self._printing = printing
        self.print_action.setEnabled(not printing)
        self.panel("file").set_printing(printing)
        self._update_media_button()

    def _update_media_button(self) -> None:
        """„Medium prüfen“ geht nur per USB und nicht während eines Drucks."""
        network = self.printer is not None and self.printer.source != "usb"   # Netz, CUPS
        check = self.panel("paper").check
        missing = self.printer is None and bool(self.settings.printer)     # gewählter fehlt
        check.setEnabled(not self._printing and not network and not missing
                         and not self.is_checking_media())
        check.setToolTip(_("Check media only works with Brother printers via USB") if network
                         else _("Ask the printer which roll is loaded (prints nothing)"))

    def _print_done(self, status: dict) -> None:
        ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
        self.result.setProperty("state", "ok" if ok else "error")
        sent_only = status.get("outcome") == "sent" and not status.get("did_print")
        if status.get("job"):
            self.result.setProperty("state", "ok")
            self.result.setText(_("Handed to the print queue ✓ (job {job})").format(
                job=status["job"]))
            self._print_finished()
            return
        self.result.setText((_("Sent ✓ (the printer reports no status)") if sent_only
                             else _("Printed ✓")) if ok
                            else _("Status: {outcome}").format(outcome=status.get("outcome")))
        self._print_finished()

    def _print_cancelled(self, message: str) -> None:
        self.result.setProperty("state", "")
        self.result.setText(message)
        self._print_finished()

    def _print_failed(self, message: str) -> None:
        self.result.setProperty("state", "error")
        self.result.setText(message.replace("\n", " "))
        self._print_finished()

    def _print_finished(self) -> None:
        self._print_signals = None
        self._worker = None
        self.cancel_button.hide()
        self.result.style().polish(self.result)
        self._set_printing(False)
        self.refresh_printer()


def _panel_for(obj: TextObject | ImageObject | BarcodeObject) -> str:
    """Panel, das ein Objekt bearbeitet."""
    return ("image" if isinstance(obj, ImageObject) else "barcode"
            if isinstance(obj, BarcodeObject) else "text")


def _keeps_aspect(obj: TextObject | ImageObject | BarcodeObject) -> bool:
    """Anfasser halten das Seitenverhältnis auch an den Kanten: Bild mit „Seitenverhältnis
    beibehalten“, QR-Code (quadratisch)."""
    return (isinstance(obj, ImageObject) and obj.keep_ratio
            or isinstance(obj, BarcodeObject) and obj.kind == "qr")


@dataclass(frozen=True)
class _ClipboardState:
    """Was die Zwischenablage des Systems anbietet – gemerkt beim Ändern, damit das Freigeben
    der Knöpfe (bei jedem Schritt) keine Daten holt. ``token``: Kennung einer hier kopierten
    Auswahl (``MIME_OBJECTS``, wenige Bytes)."""
    token: str = ""
    files: bool = False
    text: bool = False
    image: bool = False
    empty: bool = True

    @classmethod
    def of(cls, mime: QMimeData | None) -> "_ClipboardState":
        if mime is None or not mime.formats():
            return cls()
        token = (bytes(mime.data(MIME_OBJECTS)).decode(errors="replace")
                 if mime.hasFormat(MIME_OBJECTS) else "")
        return cls(token=token, files=bool(image_import.mime_files(mime)),
                   text=bool(image_import.mime_text(mime)), image=mime.hasImage(), empty=False)


def _offset(obj: TextObject | ImageObject) -> TextObject | ImageObject:
    """Kopie, um ``PASTE_OFFSET_MM`` nach rechts und unten versetzt."""
    moved = copy.deepcopy(obj)
    moved.x_mm = round((obj.x_mm or 0.0) + PASTE_OFFSET_MM, 3)
    moved.y_mm = round((obj.y_mm or 0.0) + PASTE_OFFSET_MM, 3)
    return moved
