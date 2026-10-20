"""Main window: tool bar, edit bar, panel stack, canvas, status bar."""
from __future__ import annotations

import copy
import math
import uuid
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QMimeData, QSignalBlocker, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QDockWidget, QFrame,
                               QInputDialog, QLineEdit,
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
PANEL_WIDTH = 280          # properties panels; scrollable when height is short
MEDIA_STATUS_MAX_PX = 360   # roll note in the footer; the rest via “…” and tooltip
PRINTER_POLL_MS = 2000     # printer detection: only a look into /sys, no USB access
ZOOM_STEP = 10             # percentage points per click or shortcut
NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # arrow keys fine / with Shift
_DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
OUTSIDE_HINT = N_("Object extends beyond the label")
PASTE_OFFSET_MM = 2.0      # paste/duplicate: offset to the right and down
PROGRESS_EVERY = 25        # printing a series: progress every so many labels
# Notes: English (N_), _(…) is displayed
TURNED_HINT = N_("Image rotated by 90° so that it fits 1:1")
NO_CLIPBOARD_IMAGE = N_("No image in the clipboard.")
NO_SCREENSHOT = N_("Screenshot not available (no XDG portal) – copy it to the clipboard with the "
                   "system tool and paste it with Ctrl+V")
SYMBOL_MM = 15.0           # symbol: longer side on insertion (at most across the tape)
LIBRARY_ERRORS = (OSError, zipfile.BadZipFile, KeyError, ValueError)   # archive missing/damaged
HIDE_DELAY_MS = 300        # screenshot: how long the desktop takes to hide the window
RESTORE_TIMEOUT_MS = 300_000  # safety net for portals that never answer: a selection may stay open this long,
                              # only after that does the window come back anyway
# Edit bar: action and own icon (gui/icons); None = separator
EDIT_BAR = (("tool.select", "tool-select"), ("tool.text", "tool-text"), None,
            ("edit.cut", "edit-cut"), ("edit.copy", "edit-copy"), ("edit.paste", "edit-paste"),
            None, ("edit.undo", "edit-undo"), ("edit.redo", "edit-redo"))
_SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
OBJECT_PANELS = ("text", "image", "barcode")   # panel per object kind (text, image, barcode)
CHECKING_ROLL = N_("Checking the roll – please print again in a moment.")
PRINTING_WAIT = N_("Printing – please wait.")
PARCEL_VIEW_ONLY = N_("Parcel label: view only – to edit, use OPEN IN EDITOR or choose another tab.")
PARCEL_CHOOSE_TYPE = N_("Choose the parcel label type first.")


def shrunk_hint(factor: float, mode: str) -> str:
    """Note on the reduced image: percentage rounded down (never “100 %”, never “0 %”); codes
    are only mentioned for line art – a photo is rasterised, codes are not meant there."""
    percent = math.floor(factor * 100 + 1e-9)
    shown = _("{percent}%").format(percent=percent) if percent else _("< 1%")    # „37 %“
    if mode == "line":
        return _("Image reduced to {percent} – codes may no longer be readable").format(
            percent=shown)
    return _("Image reduced to {percent}").format(percent=shown)


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str | None = None, settings: Settings | None = None):
        """``model``: fix the printer model; None = detected (``refresh_printer``), until then
        the fallback model or the last detected one from the settings."""
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.settings = settings if settings is not None else load_settings(model=model)
        self.doc = doc if doc is not None else new_document(self.settings)
        self._fixed_model = model is not None
        self.model = model or effective_model(None, self.settings.printer_model,
                                              self.settings.last_model)
        self.printers: list[Printer] = []           # printers found (USB, network)
        self.printer: Printer | None = None         # chosen or first found
        self.image = None
        self._shown_size = (0, 0)                   # label size of the last valid display
        self._structure_dirty = False               # object list rebuilt since the last display
        self.rendered: list[RenderedObject] = []    # object images on the canvas = in the print
        self.renderer = Renderer()                  # renders only changed objects again
        set_svg_rasterizer(image_import.rasterize_svg)   # vector images: Qt rasterizes SVG
        self._render_error: str | None = None
        self._shown_objects: list = []              # objects of the display (series: filled row)
        self._hint: str | None = None               # note (sticks out, font replaced)
        self._print_signals = None
        self._worker = None                         # running print job (cancel)
        self._cancel_requested = False              # series: cancel while preparing
        self._media_signals = None
        self._media_uri: str | None = None          # printer of the running check
        self._printer_present = False
        self._printing = False
        self._media_check_pending = False
        self._clipboard: list[TextObject | ImageObject] = []   # internal clipboard (copies)
        self._clipboard_token = ""                  # ID of the copy in the system (MIME_OBJECTS)
        self._system = _ClipboardState()            # system clipboard (on change)
        self._text_pastes = 0                       # text pasted since the last change
        self._notice: str | None = None             # message about pasting images
        self._image_dir = ""                        # folder of the most recently inserted image
        self._parcel_dir = ""                       # folder of the most recently opened parcel label
        self._parcel_renderer = Renderer()          # conversion of a parcel label (view only)
        self._parcel_disabled: set[str] = set()     # locked in the parcel label view
        self._portal: ScreenshotPortal | None = None   # screenshot (on first use)
        self.symbol_window: SymbolDialog | None = None  # “Insert symbol” (on first use)
        self._symbols_were_open = False             # screenshot: symbol window hidden too
        self._shooting = False                      # window hidden for a screenshot
        self._quit_on_close = True                  # app setting from before hiding
        self._shot_pending = False                  # portal answer still pending
        self._merge_next = None                     # arrow keys: merge steps
        self._restoring = False                     # undo is setting the selection
        self._arranging = False                     # selection is being changed internally (creating …)
        self._outside: list[int] = []               # objects that stick out over the label
        self._area = Rect(0, 0, 0, 0)               # printable area (mm), with the image
        self._inner: Rect | None = None             # interior of the decorative frame (mm), with the image
        self._shown_frame = None                    # frame mask of the last valid display
        # all shortcuts come from the directory (shortcuts.ACTIONS) and are changeable;
        # double-assigned (hand-edited file): the later action stays without a shortcut
        keys, key_warnings = without_conflicts(effective(self.settings.shortcuts))
        self.shortcut_actions = build_actions(self, keys)

        # Tool bar + panels from the registry
        toolbar = QToolBar(_("Tools"))
        toolbar.setObjectName("toolBar")            # name: part of the saved window state
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        self.panels = QStackedWidget()
        self.panels.setObjectName("panels")
        self.panels.setMinimumWidth(PANEL_WIDTH)      # wider by dragging the dock edge
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
        self.apply_hidden_tools(fall_back=False)    # start tab already skips hidden ones
        self.panels.currentChanged.connect(self._remember_tool)    # only after the start tab
        self.panels.currentChanged.connect(self._update_tool_buttons)   # SERIES: button until the switch
        self._stored_tool = self.settings.last_tool   # last used tab, as in the file
        self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
        # SETTINGS and PRINT in a bar of their own on the right: never in the overflow –
        # only the tab buttons may overflow
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
        QTimer.singleShot(0, self, self.fit_toolbars)     # measure only with the design (apply_theme)

        # Canvas
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
        # File and favourites (FILE tab): New/Open/Save, prompt on changes
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
        scroll = QScrollArea()                  # small screens: panel scrolls, window stays
        scroll.setObjectName("panelScroll")
        # A click on a free panel area takes focus from nobody (edit mode keeps typing)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setWidget(self.panels)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(PANEL_WIDTH + scroll.verticalScrollBar().sizeHint().width())
        # Side bar as a dock: left or right, wider by dragging, detachable – never closed
        self.panel_dock = QDockWidget(_("Properties"), self)
        self.panel_dock.setObjectName("panelDock")
        self.panel_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                                    | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.panel_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea
                                        | Qt.DockWidgetArea.RightDockWidgetArea)
        self.panel_dock.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.panel_dock)
        self.setCentralWidget(self.canvas)
        if self.settings.window_state:              # place and width as last time
            self.restoreState(QByteArray.fromBase64(self.settings.window_state.encode("ascii")))
        else:                                       # first start: as narrow as the panels allow
            self.resizeDocks([self.panel_dock], [scroll.minimumWidth()], Qt.Orientation.Horizontal)
        self._stored_state = self.settings.window_state

        # Status bar: printer (button with choice), result, zoom
        self.printer_status = QToolButton()
        self.printer_status.setObjectName("printerChoice")
        self.printer_status.setAutoRaise(True)
        self.printer_status.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.printer_menu = QMenu(self.printer_status)
        self.printer_menu.aboutToShow.connect(self._fill_printer_menu)
        self.printer_status.setMenu(self.printer_menu)
        self.result = QLabel()
        self.result.setTextFormat(Qt.TextFormat.PlainText)   # names with “<b>” stay text
        self.statusBar().addWidget(self.printer_status)
        self.media_status = QLabel()            # roll in the printer (check media)
        self.media_status.setObjectName("mediaStatus")
        self.media_status.hide()
        self.statusBar().addWidget(self.media_status)
        self.statusBar().addWidget(self.result, 1)
        self.cancel_button = QPushButton(_("CANCEL"))   # series: while preparing and printing
        self.cancel_button.setObjectName("cancelPrint")
        self.cancel_button.setToolTip(_("Cancel the series – a part already sent (up to 10 labels, "
                                        "with “Only at the end” the whole job) is still printed"))
        self.cancel_button.clicked.connect(self.cancel_print)
        self.cancel_button.hide()
        self.statusBar().addWidget(self.cancel_button)
        # State at start: the settings dialog then shows what only a restart changes
        self._started = started_values(self.settings)
        # System file dialog applies from the start (platform theme of the application), only with the plugin
        self.system_dialog = (self._started["system_file_dialog"]
                              and file_dialog.system_dialog_available())
        self._sync_tool()                           # start in the TEXT tab: "Add text"
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
        self.panel("paper").set_model(self.model)      # panels are created with the default model
        self._update_cut_choices()
        self.panel("layout").color_chosen.connect(self.set_color_selected)
        self.panel("series").driver_cut_chosen.connect(self._driver_cut_chosen)
        self.panel("paper").media_status_changed.connect(self._show_media_status)
        self._printer_timer = QTimer(self)
        self._printer_timer.setInterval(PRINTER_POLL_MS)
        self._printer_timer.timeout.connect(self.refresh_printer)
        self._printer_timer.start()
        self._hide_timer = QTimer(self)              # screenshot: first hide, then selection
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._take_hidden)
        self._restore_timer = QTimer(self)           # … and show again without an answer
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._show_again)

        # Edit mode directly on the label (the TEXT panel's editor as input buffer)
        self.edit_session = TextEditSession(self)
        self._keep: int | None = None               # show object with placeholders (edit mode start)
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
        self._fit_label()                           # default label of another printer
        if self.settings.warnings or key_warnings:
            self._set_result(" · ".join(self.settings.warnings + key_warnings), "error")

    def panel(self, key: str):
        return self._panel_by_key[key]

    def fit_toolbars(self, resize: bool = True) -> None:
        """Measured with the design: the SETTINGS/PRINT bar never narrower than its buttons
        (the tab buttons overflow when space is short); ``resize`` (start): the window as wide
        as needed for everything to fit – at most as wide as the screen."""
        ext = self.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
        if ext is not None:                         # label the overflow button visibly
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
        """PARCEL tab: conversion on the canvas, printing, editor, own types."""
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
        """Action from the directory as a button of the tool bar (shortcut stays changeable)."""
        action = self.shortcut_actions[key]
        action.setIcon(QIcon.fromTheme(icon))
        action.setText(text)
        action.triggered.connect(lambda _=False: handler())
        return action

    def _connect_view_actions(self) -> None:
        """Zoom via shortcut – like the −/+ buttons in the status bar."""
        handlers = {"view.zoom_in": lambda: self.canvas.set_zoom(self.canvas.zoom + ZOOM_STEP),
                    "view.zoom_out": lambda: self.canvas.set_zoom(self.canvas.zoom - ZOOM_STEP),
                    "view.zoom_reset": lambda: self.canvas.set_zoom(100)}
        for key, handler in handlers.items():
            self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
            self.addAction(self.shortcut_actions[key])

    def _connect_canvas_actions(self) -> None:
        """Canvas shortcuts (arrow keys, clipboard, tool) and undo."""
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
        # global: works everywhere; in edit mode the editor uses Ctrl+Z itself (its own undo)
        # and passes it on to the document when it has nothing left
        self.shortcut_actions["edit.undo"].triggered.connect(self.undo)
        self.shortcut_actions["edit.redo"].triggered.connect(self.redo)
        self.addActions([self.shortcut_actions["edit.undo"], self.shortcut_actions["edit.redo"]])

    def _connect_edit_mode(self) -> None:
        """Esc (area “edit mode”, fixed) and a click beside the frame end
        edit mode – a frame left empty is dropped. Undo, clipboard
        and their buttons follow the editor in edit mode."""
        end = self.shortcut_actions["text.end_edit"]
        end.triggered.connect(lambda _=False: self.finish_editing())
        self.panel("text").addAction(end)
        self.canvas.edit_left.connect(lambda: self.finish_editing())
        editor = self.panel("text").edit
        for signal in (editor.copyAvailable, editor.undoAvailable, editor.redoAvailable):
            signal.connect(self._update_edit_actions)
        # Paste buttons follow the system clipboard (PySide drops the connection
        # with the window, a later clipboard change hits nothing deleted)
        QApplication.clipboard().dataChanged.connect(self._clipboard_changed)

    def _connect_layout_actions(self) -> None:
        """LAYOUT tab: align, match size, rotate, order (also via shortcut)."""
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
        """Edit bar below the tool bar: tool, clipboard, undo."""
        bar = QToolBar(_("Edit"))
        bar.setObjectName("editBar")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        bar.setIconSize(SIZE)
        self.addToolBarBreak()
        self.addToolBar(bar)
        self.edit_bar = bar
        modes = QActionGroup(self)                 # select pointer or “Add text”
        for key in ("tool.select", "tool.text"):
            self.shortcut_actions[key].setCheckable(True)
            modes.addAction(self.shortcut_actions[key])
        self.shortcut_actions["tool.select"].setChecked(True)
        self.canvas.tool_changed.connect(lambda tool: self.shortcut_actions[f"tool.{tool}"].setChecked(True))
        for entry in EDIT_BAR:
            if entry is None:
                bar.addSeparator()
            else:
                bar.addAction(self.shortcut_actions[entry[0]])   # icon is set by apply_theme_icons

    def _start_tool(self) -> str:
        """Tab at start: setting ``start_tool`` (“last” = last used); without a
        valid value ``START_TOOL``."""
        wanted = self.settings.start_tool
        if wanted == "last":
            wanted = self.settings.last_tool
        for key in (wanted, START_TOOL):
            if key in self.tool_actions and key not in self.settings.hidden_tools:
                return key
        return next(iter(self.tool_actions))

    def apply_hidden_tools(self, fall_back: bool = True) -> None:
        """Take hidden tabs (setting ``hidden_tools``) off the bar. Their panels
        stay: selecting an object shows them anyway (without a highlighted button).
        ``fall_back``: if the shown tab is now hidden and does not belong to the selection or
        edit mode, go to the last used visible tab (else PAPER)."""
        self._update_tool_buttons()
        current = self._current_tool()
        if fall_back and not self._tool_needed(current) and not self._panel_in_use(current):
            self._show_visible_tool()

    def _update_tool_buttons(self, _index: int = 0) -> None:
        """Buttons of the bar according to ``hidden_tools`` – SERIES appears anyway while
        it is needed (series in the label, cutting options of the printer)."""
        for key, action in self.tool_actions.items():
            action.setVisible(self._tool_visible(key))
        QTimer.singleShot(0, self, self._mark_overflow)    # after the bar has been rearranged

    def _mark_overflow(self) -> None:
        """If the active tab lies in the bar's overflow, the “»” button is highlighted."""
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
            # visible even without a stylesheet (design “Classic”): bold and with a dot
            ext.setText("» •" if hidden else "»")
            font = ext.font()
            font.setBold(hidden)
            ext.setFont(font)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self, self._mark_overflow)    # overflow changes with the width

    def createPopupMenu(self):
        """No context menu for hiding the bars (actions/tools always belong)."""
        menu = super().createPopupMenu()
        if menu is not None:
            for bar in (self.tool_bar, self.app_bar):
                menu.removeAction(bar.toggleViewAction())
            if menu.isEmpty():
                return None
        return menu

    def _tool_needed(self, key: str) -> bool:
        """Button belongs on the bar: not hidden – or SERIES is needed (series in the
        label, cutting options of the printer)."""
        if key not in self.settings.hidden_tools:
            return True
        return key == "series" and (self.doc.series is not None
                                    or not self.panel("series").driver_box.isHidden())

    def _tool_visible(self, key: str) -> bool:
        """Like ``_tool_needed``; SERIES also stays while its panel is visible – the button
        disappears only on switching (after REMOVE, New, printer change)."""
        return self._tool_needed(key) or (key == "series"
                                          and self.panels.currentWidget() is self.panel("series"))

    def _panel_in_use(self, key: str) -> bool:
        """Does the panel belong to the selection (object of its kind chosen last) or to edit mode?"""
        if key == "text" and self.edit_session.active:
            return True
        selection = self.canvas.selection()
        return bool(selection) and 0 <= selection[-1] < len(self.doc.objects) \
            and _panel_for(self.doc.objects[selection[-1]]) == key

    def _show_visible_tool(self) -> None:
        """To the last used visible tab (else PAPER) – like a click on it."""
        key = self.settings.last_tool
        if key not in self.tool_actions or not self._tool_needed(key):
            key = START_TOOL
        self._tool_triggered(key)
        self.tool_actions[key].setChecked(True)

    def _current_tool(self) -> str:
        """Key of the shown panel."""
        return next((k for k, panel in self._panel_by_key.items()
                     if panel is self.panels.currentWidget()), "")

    def _remember_tool(self, _index: int = 0) -> None:
        """Remember the shown tab as last used (``last_tool``) – in memory only: every
        click on an object may switch the tab; it goes to disk on closing."""
        key = self._current_tool()
        if key and key not in self.settings.hidden_tools:   # only shown via the selection: do not remember
            self.settings.last_tool = key

    def _show_tool(self, key: str) -> None:
        """Show the panel of a tool (like a click on its button)."""
        self.tool_actions[key].setChecked(True)
        self.panels.setCurrentWidget(self.panel(key))

    def _choose_tool(self, tool: str) -> None:
        """Select pointer or “Add text” (edit bar, shortcut) – ends
        edit mode."""
        self.finish_editing()
        self.canvas.set_tool(tool)

    def _tool_triggered(self, key: str) -> None:
        """Tool tab: show panel; text without selection means “Add text”, every
        other panel works with the select pointer (and ends edit mode)."""
        if key != "text":
            self.finish_editing()
        self.panels.setCurrentWidget(self.panel(key))
        if key == "text":
            self._sync_tool()
        else:
            self.canvas.set_tool("select")

    def _sync_tool(self) -> None:
        """Tool matching the selection: TEXT panel without selection = “Add text” (note
        in the panel); with a selection the select pointer – as after a click on an object."""
        if self.canvas.selection():
            self.canvas.set_tool("select")
        elif self.panels.currentWidget() is self.panel("text"):
            self.canvas.set_tool("text")

    def _on_selection(self, indices: list[int]) -> None:
        """Selection on the canvas: show the object's panel (text or image) – unless
        the LAYOUT tab is visible. An empty text frame that the selection leaves
        is dropped."""
        if self._arranging:                         # creating, renumbering: just follow along
            self._follow_selection(indices)
            return
        if self.edit_session.active and indices != [self.edit_session.index]:
            self.finish_editing(drop_empty=False)   # empty frames are dropped right down here
        if not self._restoring:
            indices = self._drop_empty_frames(indices)
        self._follow_selection(indices)
        if self._restoring:                         # undo does not switch the tab –
            if not indices and not self._tool_visible(self._current_tool()):
                self._show_visible_tool()           # except away from the hidden one of the selection
            return
        self.history.select(self.doc, indices)
        if indices:
            self._show_object_panel()
        elif not self._tool_visible(self._current_tool()):
            self._show_visible_tool()               # hidden tab only for the selection
        self._sync_tool()

    def _drop_empty_frames(self, indices: list[int]) -> list[int]:
        """Remove empty text frames (with position) that are no longer selected; the
        selection is renumbered. Invisible and not clickable, they should neither stay
        lying around nor extend the label.

        No undo step of its own: if nothing else is open, this replaces the current
        state (creating it is then dropped entirely), otherwise it belongs to the running step."""
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
            self.canvas.set_selection(indices)     # before redrawing: indices fit
            self._follow_selection(indices)        # TEXT panel not on the removed frame
            self.render_now()
        finally:
            self._arranging = False
        if recorded:
            self.history.amend(self.doc, indices)
        return indices

    def _show_object_panel(self) -> None:
        """To the panel of the most recently chosen object – text or image (also on a click on an
        already chosen one); the LAYOUT tab works with any selection and stays."""
        if self.panels.currentWidget() in (self.panel("layout"), self.panel("series")):
            return                                  # both work with any selection
        selection = self.canvas.selection()
        if selection and 0 <= selection[-1] < len(self.doc.objects):
            key = _panel_for(self.doc.objects[selection[-1]])
            if self.panels.currentWidget() is not self.panel(key):
                self._show_tool(key)

    def _follow_selection(self, indices: list[int]) -> None:
        """Panels learn the selection; the panel of its kind edits the most recently chosen
        object, the other none."""
        for panel in self._panel_by_key.values():
            panel.set_selection(indices)
        last = indices[-1] if indices and indices[-1] < len(self.doc.objects) else None
        kind = _panel_for(self.doc.objects[last]) if last is not None else None
        for key in OBJECT_PANELS:
            self.panel(key).set_object(last if kind == key else None)
        self._update_frame()

    def _update_frame(self) -> None:
        """POSITION area: frame of the edited object, as rendered."""
        for key in OBJECT_PANELS:
            panel = self.panel(key)
            index = panel.index
            if index is None or not self._valid(index):
                panel.show_frame(None)
            else:
                panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))

    def _update_edit_actions(self) -> None:
        if self._parcel_locked():                   # parcel label: view only
            for entry in ACTIONS:
                action = self.shortcut_actions[entry.id]
                if (entry.scope == "canvas" or entry.id in ("edit.undo", "edit.redo")) \
                        and action.isEnabled():
                    action.setEnabled(False)
                    self._parcel_disabled.add(entry.id)
            return
        if self._parcel_disabled:                   # as before, the following handles the rest
            for key in self._parcel_disabled:
                self.shortcut_actions[key].setEnabled(True)
            self._parcel_disabled.clear()
            self.panel("layout").set_selection(self.canvas.selection())   # align according to selection
        if self.edit_session.update_actions(self.shortcut_actions):   # act on the editor
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

    # --- Rendering -------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        self._update_tool_buttons()                 # SERIES: series added/removed
        self.files.update_title()                   # “•” on unsaved changes
        if self.canvas.is_dragging():   # do not interrupt dragging – render after release
            self._timer.start()
            return
        if self._render_parcel():                   # PARCEL tab with label: view only
            return
        if self.canvas.read_only:
            self.canvas.set_read_only(False)
            self._update_edit_actions()             # editing possible again
        view = self._view_doc()
        try:
            # measure and draw each object at most once; area and “sticks out”
            # follow from the rendered objects; a barcode that cannot be encoded
            # stays selectable as a placeholder (error like a render error: no print)
            result = self.renderer.render(view, self.model, placeholders=True)
        except ValueError as e:
            # last valid image stays in the preview but is not printed
            self._render_error = self._series_error(str(e))
            self._drop_stale_view()
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        error = self._series_error(result.errors[0][1], result.errors[0][0]) if result.errors else None
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # only clear the render error, no print result
        self._render_error = error
        if error is not None:
            self._set_result(error, "error")
        if self._hint is not None and self.result.text() == self._hint:
            self._set_result("", "")   # only clear the old note if it is still there
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
        self._shown_objects = view.objects          # what the canvas shows (series: filled)
        self._shown_size = size
        self._structure_dirty = False
        self._outside = outside
        self._area = area
        self._inner = frame_area(self.doc, self.model, size)
        self._shown_frame = result.frame
        # Handles: corners keep the aspect ratio for text without fixed frame size, for
        # images with “Keep aspect ratio” and QR codes – both also on the edges
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
        self.panel("barcode").update_check()        # series: check note for the preview row
        self.edit_session.update_marks()            # caret for the new line layout

    # --- Parcel label (PARCEL tab) ------------------------------------------------
    def _parcel_shown(self) -> bool:
        """PARCEL tab is visible."""
        return ("parcel" in self._panel_by_key
                and self.panels.currentWidget() is self.panel("parcel"))

    def _parcel_locked(self) -> bool:
        """PARCEL tab with a loaded label: the canvas is view only (with or without
        conversion) – nothing changes the document."""
        return self._parcel_shown() and self.panel("parcel").source is not None

    def _parcel_blocks(self) -> bool:
        """Editing in the PARCEL tab with a label: note instead of change (True = locked)."""
        if not self._parcel_locked():
            return False
        self._set_result(_(PARCEL_VIEW_ONLY), "error")
        return True

    def _render_parcel(self) -> bool:
        """PARCEL tab with a loaded label: the canvas shows the chosen label of the
        conversion or – without conversion (not recognised, type not chosen, error) – an empty
        label, always view only (True); without a label the document (False). The conversion
        follows the document's label and the printer."""
        if not self._parcel_shown():
            return False
        panel = self.panel("parcel")
        blocker = QSignalBlocker(panel)             # conversion anew – shown right here
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
                           orientation=self.doc.orientation)   # empty: nothing to show
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
        """Tab switch: canvas shows the conversion or the document again."""
        self.render_now()

    def ask_parcel_file(self) -> str | None:
        """“Open parcel label” file dialog with preview (replaceable in tests); None = cancelled."""
        path = file_dialog.ask_open(self, _("Open parcel label"), self._parcel_dir,
                                    _("Parcel labels (*.pdf *.png *.jpg *.jpeg *.gif);;"
                                      "All files (*)"),
                                    system=self.system_dialog, model=self.model)
        if path:
            self._parcel_dir = str(Path(path).parent)
        return str(path) if path else None

    def open_parcel_file(self) -> None:
        """OPEN PARCEL LABEL …: choose file, load, recognise type, convert (errors in the panel)."""
        path = self.ask_parcel_file()
        if path:
            self.panel("parcel").load(path)

    def print_documents(self, docs: list[Document]) -> None:
        """Print several labels (conversion of a parcel label) in one job, cut after
        each – same checks and prompts as otherwise."""
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
        """Open the shown label of the conversion as an ordinary label (prompt on
        changes as with New); afterwards the canvas shows the editor again."""
        if self.files.open_document(copy.deepcopy(doc)):
            self._tool_triggered("paper")
            self.tool_actions["paper"].setChecked(True)

    def exec_parcel_editor(self, editor: ParcelTypeEditor) -> bool:
        """Show the "New own parcel label type" window (replaceable in tests); True = saved."""
        return editor.exec() == ParcelTypeEditor.DialogCode.Accepted

    def new_own_parcel_type(self) -> None:
        """CREATE OWN TYPE …: define areas on the opened label, save."""
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
        """New name of an own type (replaceable in tests); None = cancelled."""
        name, ok = QInputDialog.getText(self, _("Rename own type"), _("Name:"), text=current)
        return name.strip() if ok and name.strip() else None

    def ask_remove_parcel_type(self, name: str) -> bool:
        """Prompt before deleting an own type (replaceable in tests)."""
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
        self.panel("parcel").refresh_types()            # chosen type stays chosen

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
        """After a render error: take object images that no longer match ``doc.objects``
        (deleted, inserted, reordered – ``_structure_changing``) off the canvas
        – otherwise selection and dragging would act on another object. With the same structure
        the last valid image stays."""
        if not self._structure_dirty:
            return
        self._structure_dirty = False
        self.rendered = []
        self.canvas.set_document(get_label(self.doc.label_id), self._shown_size, [],
                                 self.doc.orientation,
                                 self._area, keep_ratio=[], grow=growing_axis(self.doc),
                                 frame=self._shown_frame, inner=self._inner)

    # --- Undo -------------------------------------------------------
    def _commit(self, merge=None) -> None:
        """Record the state after a completed action (no step without a change).

        Called before every action, anything not yet recorded becomes a step of its own. Not
        while the selection is being changed internally (e.g. an empty frame is dropped); the
        caller records that itself. In edit mode everything belongs to the running edit – it
        becomes one step on ending (``finish_editing``)."""
        if self._arranging or self.edit_session.active:
            return
        self.history.push(self.doc, merge, self.canvas.selection())
        self._update_edit_actions()

    def undo(self) -> None:
        """Undo – in edit mode first within the edit (``TextEditSession.undo``),
        then in the document (button and Ctrl+Z the same)."""
        if self._parcel_blocks():
            return
        self.accept_pending_input()                 # what was just typed is the last step
        if not self.edit_session.undo():
            self._restore(self.history.undo(self.doc, self.canvas.selection()))

    def redo(self) -> None:
        """Redo – in edit mode first in the editor, then in the document (like ``undo``)."""
        if self._parcel_blocks():
            return
        self.accept_pending_input()
        if not self.edit_session.redo():
            self._restore(self.history.redo(self.doc, self.canvas.selection()))

    def _restore(self, snapshot: Document | None) -> None:
        """Restore a state – with the selection that belonged to it (the same objects)."""
        if snapshot is None:
            return
        selection = self.history.selection
        self._structure_changing()
        self._restoring = True       # do not record a selection that is dropped on redrawing
        try:
            restore(self.doc, snapshot)
            for panel in self._panel_by_key.values():
                panel.refresh()
            self.render_now()
            self.canvas.set_selection(selection)        # invalid indices are dropped
        finally:
            self._restoring = False
        self._sync_tool()
        self._update_edit_actions()

    # --- Objects on the canvas ------------------------------------
    def nudge(self, dx_mm: float, dy_mm: float) -> None:
        """Arrow keys: move the selection; several steps in a row = one undo."""
        self._merge_next = ("nudge", tuple(self.canvas.selection()))
        try:
            self.canvas.nudge(dx_mm, dy_mm)
        finally:
            self._merge_next = None

    def _valid(self, index: int) -> bool:
        """Index fits the document and the rendered objects (not stale)."""
        return 0 <= index < min(len(self.doc.objects), len(self.rendered))

    def _structure_changing(self) -> None:
        """Object list changes (delete, insert, undo, order …): cancel a running
        drag – its indices would no longer apply – and have it redrawn right away."""
        self._structure_dirty = True
        self.canvas.cancel_object_drag()

    def _move_objects(self, indices: list[int], rects: list[Rect]) -> None:
        indices_rects = [(i, r) for i, r in zip(indices, rects) if self._valid(i)]
        if not indices_rects:
            return
        self._commit()
        dragged = self._merge_next is None          # mouse: to 0.1 mm like the fields; arrows exact
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
        # only the dragged edges to 0.1 mm (like the fields) – the others stay exact
        self.doc.objects[index] = to_grid(resized, x="l" in handle, y="t" in handle,
                                          w="l" in handle or "r" in handle,
                                          h="t" in handle or "b" in handle)
        self._objects_changed([index])
        self._commit()

    def create_text(self, x_mm: float, y_mm: float) -> None:
        """New empty text frame at x/y (mm, reading direction), selected, straight into edit mode.

        Font from the settings (automatic size → 19 pt). Other empty texts are
        invisible and do not print – they are dropped in the process."""
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
        self._arranging = True            # the new, still empty frame stays
        try:
            self.canvas.set_selection([])  # only after the change: the selection before it stays in the state
            self._objects_changed(list(range(len(self.doc.objects))))
        finally:
            self._arranging = False
        self.canvas.set_selection([index])
        self.edit_text(index)                       # create and write: one step

    def _view_doc(self) -> Document:
        """What the canvas shows: with a series the label of the preview row – the object in
        edit mode with its placeholders (caret fits the text)."""
        row = self.panel("series").preview()
        if row is None:
            return self.doc
        keep = self._keep if self._keep is not None else self.edit_session.index
        return fill_anchored(self.doc, *row, self.model, keep=keep)

    def _series_error(self, message: str, index: int | None = None) -> str:
        """Render error with a series: which row – or that in edit mode it is due to the
        placeholders (they stand in place of the values). ``index``: object of the error, if
        known (barcode as placeholder) – only the object in edit mode shows placeholders."""
        if self.panel("series").preview() is None:
            return message
        kept = self._keep if self._keep is not None else self.edit_session.index
        if kept is not None and index in (None, kept):
            return _("{message} – with placeholders in text editing (choose a smaller font)"
                     ).format(message=message)
        return _("Row {row}: {message}").format(row=self.panel("series").current_row(),
                                                 message=message)

    def ask_series_file(self) -> str | None:
        """Dialog for a series' table (replaceable in tests); starts in the folder of the
        current table."""
        current = self.doc.series.source if self.doc.series is not None else None
        return file_dialog.ask_open(
            self, _("Table for the series"), str(Path(current).parent) if current else "",
            _("Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"),
            system=self.system_dialog)

    def choose_series_table(self) -> None:
        """TABLE …: choose file, read (error → message, nothing changed), link."""
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
        self.panel("series").set_series(Series(source=path, cut=cut), table)   # read once

    def insert_column(self, name: str) -> None:
        """Insert a column as ``{Name}``: at the end of the chosen text object (its last
        formatting) or into the content of the chosen barcode (replaces the sample content,
        otherwise appended), otherwise as a new text at the top left – one step."""
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
            self._commit()                          # record anything not yet recorded first
            obj = self.doc.objects[selection[0]]
            last = obj.paragraphs[-1].spans[-1]
            gap = " " if obj.text and not obj.text[-1].isspace() else ""   # {A} {B}, not {A}{B}
            last.text += gap + placeholder
            self._objects_changed(selection)
            self._commit()
            return
        if self._timer.isActive():
            self.render_now()                       # current inner area
        obj = self._new_text(placeholder)
        area = self._paper_area()
        obj.x_mm, obj.y_mm = round(area.x, 3), round(area.y, 3)
        self._insert([obj])

    def _new_text(self, text: str) -> TextObject:
        """New text with the font from the settings (automatic size → 19 pt),
        left-aligned: it grows from its position to the right (as in P-touch)."""
        family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
        return TextObject.plain(text, size_pt=self.settings.font_size_pt or DEFAULT_PT,
                                align="left", family=family)

    def edit_selected(self) -> None:
        """F2/Enter: edit mode for the only chosen object, caret at the end of the text."""
        selection = self.canvas.selection()
        if not self.edit_session.active and len(selection) == 1:
            self.edit_text(selection[0])

    def edit_text(self, index: int, point=None) -> None:
        """Edit mode for an object: select, show TEXT panel, caret at
        ``point`` (QPointF, dots in reading direction – e.g. double-click) or at the end.
        Images have no edit mode; for barcodes the focus goes to the content field."""
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
            self.finish_editing(drop_empty=False)   # dropped right on choosing (numbers!)
        if not self._valid(index):
            return
        if self.canvas.selection() != [index]:
            self.canvas.set_selection([index])
            index = self.canvas.selection()[-1]     # possibly renumbered (empty frame was dropped)
        self._show_tool("text")
        if self.panel("series").preview() is not None:
            # Series: in edit mode the object shows its placeholders – render before the caret
            # so that line layout and text do not fit otherwise (the position drifted while typing);
            # the click position in the filled text cannot be transferred: caret to the end
            self._keep, point = index, None
            try:
                self.render_now()
            finally:
                self._keep = None
        elif self._timer.isActive():
            self.render_now()                       # a click hits the current line layout
        self.edit_session.start(index, point)
        self._update_edit_actions()

    def finish_editing(self, drop_empty: bool = True) -> None:
        """End edit mode (Esc, click beside it, other tool or tab, command on
        the selection); the whole edit becomes one undo step. A frame left empty
        is dropped – except with ``drop_empty=False``, when the caller is just
        changing the selection (then it is dropped there, ``_on_selection``)."""
        index = self.edit_session.end()
        if index is None:
            return
        if (drop_empty and self._valid(index) and self.doc.objects[index].positioned
                and self.doc.objects[index].is_empty()):
            self.canvas.set_selection([])           # empty frame is dropped (_on_selection)
        self._commit()
        if self.panel("series").preview() is not None:
            self.render_now()                       # the values again instead of the placeholders

    def delete_selected(self) -> None:
        """Delete the selected objects (also the last one – the label is then empty)."""
        self.finish_editing()
        indices = self.canvas.selection()
        if not indices:
            return
        self._structure_changing()
        self._commit()
        for index in sorted(indices, reverse=True):
            del self.doc.objects[index]
        self.canvas.set_selection([])     # only after the change: the selection before it stays in the state
        self.render_now()
        self._commit()

    def _edit_frame(self, panel: str, key: str, value: float) -> None:
        """Number in the POSITION area of panel ``panel`` changed: move the object or
        change the frame; an image with “Keep aspect ratio” changes both dimensions."""
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

    # --- LAYOUT tab -------------------------------------------------------
    def align_selected(self, mode: str, paper: bool = False) -> None:
        """Align the selection to each other or to the printable area (with decorative frame: to its
        interior)."""
        label = get_label(self.doc.label_id)
        min_length = length_limits(self.model)[0] * 25.4 / label.dpi
        self._change_selected(lambda objs, rendered: align_objects(
            objs, rendered, mode, self._paper_area() if paper else None, growing_axis(self.doc),
            min_length, self._unselected_rects()))

    def _unselected_rects(self) -> list[Rect]:
        """Frames (mm) of the visible, unselected objects – call after rendering."""
        chosen = set(self.canvas.selection())
        return [exact_rect(self._layout_object(i), self.rendered[i])
                for i in range(len(self.doc.objects))
                if i not in chosen and self._valid(i) and not self.doc.objects[i].is_empty()]

    def _paper_area(self) -> Rect:
        """Area for “to the label” (align, maximise): interior of the decorative frame, otherwise
        the printable area."""
        return self._inner if self._inner is not None else self._area

    def match_selected(self, mode: str) -> None:
        """Match size, width or height to the first chosen object."""
        self._change_selected(lambda objs, rendered: match_objects(objs, rendered, mode))

    def maximize_selected(self) -> None:
        """Make each chosen object as large as possible, centred in the printable area or the
        interior of the decorative frame (on continuous tape with automatic length only across –
        ``maximize_object``)."""
        self._change_selected(lambda objs, rendered: [
            maximize_object(obj, r, self._paper_area(), self.doc, self.model)
            for obj, r in zip(objs, rendered)])

    def rotate_selected(self, degrees: int) -> None:
        """Rotate the selection by 90° (−90 = left); the centre of each object stays."""
        self._change_selected(lambda objs, rendered: [
            rotate(obj, r, degrees) for obj, r in zip(objs, rendered)])

    def _change_selected(self, change) -> None:
        """Replace the chosen objects by ``change(objects, rendered)`` – one step.

        ``change`` runs after rendering: frames and ``self._area`` are current."""
        self.finish_editing()
        if self._timer.isActive():
            self.render_now()                   # e.g. just typed: current frames
        # empty frames are invisible and do not print: they do not take part in layout commands
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
        """Object for size and position: barcodes as the canvas shows them (series: with the
        value of the preview row – its width follows from the content), otherwise the object itself."""
        obj = self.doc.objects[index]
        shown = self._shown_objects[index] if index < len(self._shown_objects) else obj
        if isinstance(obj, BarcodeObject) and isinstance(shown, BarcodeObject):
            return replace(obj, data=shown.data)   # only the content: the display may be stale
        return obj

    def _keep_content(self, index: int, changed):
        """Result of size and position back into the label: barcodes keep their content (with
        placeholders), only module, height, position and rotation come from ``changed``."""
        obj = self.doc.objects[index]
        if isinstance(obj, BarcodeObject) and isinstance(changed, BarcodeObject):
            return replace(changed, data=obj.data)
        return changed

    def set_color_selected(self, color: str) -> None:
        """Colour of the selection (LAYOUT tab; red only on red/black labels)."""
        self._change_selected(lambda objs, rendered: [replace(obj, color=color) for obj in objs])

    def reorder_selected(self, step: int) -> None:
        """Move the selection one place forward (1) or back (−1); the selection moves along."""
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

    # --- Clipboard --------------------------------------------------------
    def copy_selected(self) -> None:
        """Copy the selected objects (in drawing order) to the internal clipboard –
        in edit mode the marked text to the system clipboard."""
        if self.edit_session.copy():
            self._update_edit_actions()             # pasting is now possible
            return
        indices = sorted(self.canvas.selection())
        if indices:
            self._clipboard = [self._placed_copy(i) for i in indices]
            self._announce_copy()
            self._update_edit_actions()

    def _announce_copy(self) -> None:
        """Mark the copy in the system clipboard (``MIME_OBJECTS`` with its own
        ID, plus the text of the text objects for other programs). The objects themselves
        stay in the internal clipboard; if someone copies something else afterwards,
        Ctrl+V pastes that."""
        self._clipboard_token = uuid.uuid4().hex
        mime = QMimeData()
        mime.setData(MIME_OBJECTS, self._clipboard_token.encode())
        text = "\n".join(obj.text for obj in self._clipboard
                         if isinstance(obj, TextObject) and not obj.is_empty())
        if text:
            mime.setText(text)
        QApplication.clipboard().setMimeData(mime)
        self._system = _ClipboardState(token=self._clipboard_token, text=bool(text),
                                       empty=False)    # even without a (delayed) dataChanged

    def cut_selected(self) -> None:
        if not self.edit_session.cut():
            self.copy_selected()
            self.delete_selected()

    def paste(self) -> None:
        """Paste what the system clipboard has on top, in this order:
        objects copied here (offset 2 mm further each time; if the clipboard is empty,
        the most recently copied) › local files (like “FROM FILE”) › text (new text frame –
        even if an image is included, e.g. table cells; the image stays reachable via “FROM
        CLIPBOARD”) › image (centre of the printable area). Pasted items are
        selected. In edit mode text into the text (as plain text). Only here is the
        clipboard data read."""
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
        """Is the most recently copied selection on top of the system clipboard?"""
        return bool(self._clipboard) and self._system.token == self._clipboard_token

    def _can_paste(self) -> bool:
        system = self._system
        return (self._owns_clipboard() or (bool(self._clipboard) and system.empty)
                or system.files or system.text or system.image)

    def _clipboard_changed(self) -> None:
        """System clipboard changed: note the state once (without fetching image and text data
        – only ``paste`` reads those), buttons “Paste” and “FROM CLIPBOARD”."""
        self._system = _ClipboardState.of(QApplication.clipboard().mimeData())
        self._text_pastes = 0
        self.panel("image").set_clipboard_image(self._system.image)
        self._update_edit_actions()

    def _paste_text(self, text: str) -> None:
        """Text from the clipboard as a new text frame at the top left of the printable
        area (like “Add text”), selected – without edit mode. The same text pasted
        again: offset 2 mm further each time (like objects)."""
        if self._timer.isActive():
            self.render_now()                       # current printable area
        obj = self._new_text(text)
        shift = self._text_pastes * PASTE_OFFSET_MM
        area = self._paper_area()                   # with decorative frame: in its interior
        obj.x_mm, obj.y_mm = round(area.x + shift, 3), round(area.y + shift, 3)
        self._text_pastes += 1
        self._insert([obj])

    def duplicate_selected(self) -> None:
        """Duplicate the selection offset by 2 mm; the clipboard stays untouched."""
        indices = sorted(self.canvas.selection())
        if indices:
            self._insert([_offset(self._placed_copy(i)) for i in indices])

    def _placed_copy(self, index: int) -> TextObject | ImageObject:
        """Copy with position: a centred object gets its position and font size fixed."""
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

    # --- Insert images ---------------------------------------------------
    def insert_image_file(self) -> None:
        """“Insert image …”: choose file; the image goes to the centre of the printable
        area."""
        path = self.ask_image_file()
        if path:                                    # PDF page chosen in the dialog: no page prompt
            self.insert_image_files([Path(path)], page=getattr(path, "page", None))

    def ask_image_file(self) -> str | None:
        """File dialog “Images and PDF” with preview (replaceable in tests); None = cancelled.
        Result ``file_dialog.Chosen``: path, for a PDF possibly with the chosen page (``page``)."""
        path = file_dialog.ask_open(self, _("Insert image"), self._image_dir,
                                    image_import.file_filter(),
                                    system=self.system_dialog, pages=True,
                                    model=self.model)
        if path:
            self._image_dir = str(Path(path).parent)
        return path

    def ask_pdf_page(self, path: Path, count: int) -> int | None:
        """Page choice for a PDF with several pages (replaceable in tests); None = cancelled."""
        page, ok = QInputDialog.getInt(self, _("Choose PDF page"),
                                       _("{name} has {count} pages. Which one to insert?").format(
                                           name=path.name, count=count),
                                       1, 1, count)
        return page if ok else None

    def insert_image_files(self, paths: list, at: tuple[float, float] | None = None,
                           page: int | None = None) -> None:
        """Insert image files – centred on ``at`` (mm, drop point) or in the centre of the
        printable area. For a PDF with several pages the page is asked for
        (``page`` presets it). Errors appear understandably in the status bar; whatever could
        be loaded is inserted (one step)."""
        if self._parcel_blocks():
            return
        objects, notes, failed = [], [], False
        for path in map(Path, paths):
            pdf = path.suffix.lower() == ".pdf"
            try:
                number = page or (self._choose_page(path) if pdf else 1)
                if number is None:
                    continue                        # page choice cancelled
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
        """“FROM CLIPBOARD”: image from the clipboard into the centre of the printable area."""
        image = image_import.mime_image(QApplication.clipboard().mimeData())
        if image is None:
            self._show_notice([_(NO_CLIPBOARD_IMAGE)], "error")
            return
        self._insert_picture(image, CLIPBOARD)

    # --- Screenshot -----------------------------------------------------------
    def _screenshot_portal(self) -> ScreenshotPortal:
        if self._portal is None:
            self._portal = ScreenshotPortal(parent=self)
            self._portal.finished.connect(self.screenshot_finished)
        return self._portal

    def screenshot_available(self) -> bool:
        """Is there a screenshot portal? (replaceable in tests)"""
        return self._screenshot_portal().available()

    def take_screenshot(self) -> None:
        """Open the desktop's selection; the answer arrives via ``screenshot_finished`` (replaceable in
        tests)."""
        self._screenshot_portal().take()

    def insert_screenshot(self) -> None:
        """“SCREENSHOT” as in P-touch: labelwerk gets out of the way, the desktop shows its
        selection (area, window, screen), then the image lies on the label.
        Without a portal the window stays and a note names the way via the clipboard."""
        if self._shooting:
            return
        self.finish_editing()
        if not self.screenshot_available():
            self._show_notice([_(NO_SCREENSHOT)], "error")
            return
        self._shooting = self._shot_pending = True
        self.shortcut_actions["image.screenshot"].setEnabled(False)
        # the symbol window is a window of its own: hide it too, otherwise it is on the photo
        self._symbols_were_open = self.symbol_window is not None and self.symbol_window.isVisible()
        if self._symbols_were_open:
            self.symbol_window.hide()
        # once hidden, no window is visible any more: if another one closed now, the app would
        # end
        app = QApplication.instance()
        self._quit_on_close = app.quitOnLastWindowClosed()
        app.setQuitOnLastWindowClosed(False)
        self.hide()
        self._hide_timer.start(HIDE_DELAY_MS)

    def _take_hidden(self) -> None:
        """Window is gone: open the selection; without an answer the window comes back after
        ``RESTORE_TIMEOUT_MS`` anyway. An unexpected error never leaves the window
        gone."""
        self._restore_timer.start(RESTORE_TIMEOUT_MS)
        try:
            self.take_screenshot()
        except Exception as e:  # window back at once; message instead of traceback
            self.screenshot_finished(None, f"{_(SCREENSHOT_FAILED)} – {e}")

    def screenshot_finished(self, path: Path | None, error: str | None) -> None:
        """Portal answer: path → insert (300 dpi: 1 screen pixel = 1 dot, as
        from the clipboard), message → status bar, (None, None) = cancelled. Only
        the first answer per capture counts – also one after the timeout (if it comes
        only during the next capture, it counts for that one, and that one is dropped)."""
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
        """After the screenshot (or without an answer after ``RESTORE_TIMEOUT_MS``): show the
        window and bring it to the front, action free again."""
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

    # --- Symbols -------------------------------------------------------------
    def open_symbols(self) -> None:
        """Show the “Insert symbol” window (one instance, stays open)."""
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
        """Insert a symbol as an image object: longer side ``SYMBOL_MM`` (at most printable
        across the tape), cropped to the content, line art, vector if SVG; placement like
        images; afterwards “Recently used”."""
        if self._parcel_blocks():
            return
        if self._timer.isActive():
            self.render_now()                       # current printable area
        try:
            image, dpi, crop, svg = image_import.load_symbol(symbol, self._symbol_mm())
        except (ValueError, OSError, KeyError, zipfile.BadZipFile,
                Image.DecompressionBombError) as e:
            self._show_notice([_("Symbol: {error}").format(error=e)], "error")
            return
        obj = ImageObject.from_image(image, dpi, SYMBOL_SOURCE.format(name=symbol.name),
                                     crop=crop, svg=svg)
        # size already fits across the tape – rotating per setting does not apply to symbols
        self._insert_images([obj], at, [] if crop is not None else [_(CROP_FAILED)], rotate=False)
        self.settings.symbols_recent = clipart.add_recent(self.settings.symbols_recent, symbol.id)
        self._save_settings("symbols_recent")
        if self.symbol_window is not None:
            self.symbol_window.set_recent(self.settings.symbols_recent)

    def _symbol_mm(self) -> float:
        """Size of new symbols: ``SYMBOL_MM``, at most the printable area across the tape
        (on the growing axis the label does not limit)."""
        grow = growing_axis(self.doc)
        area = self._paper_area()                   # with decorative frame: its interior
        cross = area.h if grow == "x" else area.w if grow == "y" else min(area.w, area.h)
        return max(1.0, math.floor(min(SYMBOL_MM, cross) * 1000) / 1000)   # never slightly too large

    # --- Barcodes ------------------------------------------------------------
    def insert_barcode(self) -> None:
        """Insert a barcode of the kind chosen in the tab with sample content (``layout.new_barcode``:
        centred in the interior or printable area, rotated rather than smaller; on a
        continuous tape behind the existing objects) – selected, the content marked in focus:
        typing replaces the sample."""
        if self._parcel_blocks():
            return
        self.finish_editing()
        if self._timer.isActive():
            self.render_now()                       # current printable area
        others = [object_rect(r) for o, r in zip(self.doc.objects, self.rendered)
                  if not o.is_empty()]
        obj = new_barcode(self.doc, self.model, self._paper_area(),
                          self.panel("barcode").chosen_kind(), others)
        self._insert([obj])
        self._show_tool("barcode")
        self.panel("barcode").focus_data()

    def _filled_barcode(self, obj: BarcodeObject) -> BarcodeObject:
        """Barcode with the value of the preview row (check note in the panel); without a series itself."""
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
        """Archive of the symbol library is missing or damaged: message instead of traceback."""
        self._set_result(_("Symbol library unreadable: {error}").format(error=error), "error")

    def _favorites_changed(self, favorites: list[str]) -> None:
        self.settings.symbols_favorites = list(favorites)
        self._save_settings("symbols_favorites")

    def _save_settings(self, *keys: str) -> None:
        """Save settings silently (recently used, favourites, printer …): only the fields
        ``keys`` (``update_settings`` – what a second instance saved stays); without
        ``keys`` everything. Errors go to the status bar."""
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
        """Image files or image data dropped on the canvas: at the drop point
        (comes after dropping, ``Canvas.dropped`` – a PDF page dialog is then possible).
        In the PARCEL tab a dropped file loads the label, image data change nothing."""
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
        """Insert an image without resolution (clipboard, image data, screenshot) –
        300 dpi, i.e. 1 pixel = 1 dot."""
        if self._parcel_blocks():
            return
        notes: list[str] = []
        self._insert_images([self._new_image(image, dpi, source, None, notes)], at, notes)

    def _new_image(self, image: Image.Image, dpi: float, source: str, page: int | None,
                   notes: list[str], svg: bytes | None = None) -> ImageObject:
        """Image object 1:1, automatically cropped (everything that is not white; setting
        ``image_crop``); if the image is entirely white, it stays whole – with a note in ``notes``.
        With ``svg`` a vector image (``image`` is its preview). Line art/photo and threshold from
        the settings (``image_mode``, ``image_threshold``)."""
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
        """Place images (``layout.insert_placement``: centred; if an image fits 1:1 only
        rotated by 90°, it comes rotated with the ``image_rotate`` setting; on a continuous tape with
        automatic length behind the existing objects instead of over them, otherwise one that is too
        large is reduced proportionally and then limited to at most 600 dpi of the new size;
        several offset 2 mm each) and insert – one step, selected."""
        if objects:
            if self._timer.isActive():
                self.render_now()                   # current printable area
            smallest, shrunk_mode, turned = 1.0, "line", False
            # existing objects: on a continuous tape the image goes behind them, not over them
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
        """Messages on inserting in the status bar; without a message an older one disappears."""
        if notes:
            self._notice = " · ".join(notes)
            self._set_result(self._notice, state)
        elif self._notice is not None and self.result.text() == self._notice:
            self._set_result("", "")
            self._notice = None

    def _objects_changed(self, indices: list[int]) -> None:
        for key in OBJECT_PANELS:
            if self.panel(key).index in indices:
                self.panel(key).refresh()   # e.g. a handle switches on a fixed frame size
        self.render_now()

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        if not self.canvas.is_dragging():   # when dragging render only after release
            self.schedule_render()
            self._commit()                  # double-click: automatic length

    def _length_drag_finished(self) -> None:
        self.render_now()
        self._commit()

    def _show_media_status(self, text: str, state: str) -> None:
        self.media_status.setProperty("state", state)
        self.media_status.style().polish(self.media_status)
        # shorten long messages so that the print result beside it stays visible
        metrics = self.media_status.fontMetrics()
        self.media_status.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight,
                                                     MEDIA_STATUS_MAX_PX - 24))
        self.media_status.setToolTip(text)
        self.media_status.setVisible(bool(text))

    def _set_result(self, text: str, state: str) -> None:
        self.result.setProperty("state", state)
        self.result.style().polish(self.result)
        self.result.setText(text)

    # --- Printing ---------------------------------------------------------
    def refresh_printer(self) -> None:
        """Look for printers (USB in sysfs, registered network printers), take the chosen or first
        one, adopt its model (``set_model``), update the status bar; when a USB
        printer appears possibly check media."""
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
            self.settings.last_model = chosen.model     # applies at the next start without a printer
            self._save_settings("last_model")
        if not self._fixed_model:
            model = effective_model(chosen, self.settings.printer_model, self.settings.last_model)
            if model != self.model:
                self.set_model(model)
        self._update_media_button()
        if switched:                                # another roll possible: check again
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
        """Chosen USB printer (check media); None = look for it yourself."""
        return self.printer.uri if self.printer is not None and self.printer.source == "usb" else None

    def _fill_printer_menu(self) -> None:
        """Menu on the printer button: Automatic, found printers, add network printer."""
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
        """Choose a printer (URI; "" = automatic) – saved."""
        self.settings.printer = uri
        self._save_settings("printer")
        self.refresh_printer()

    def set_model(self, model: str) -> None:
        """Printer model changed: labels, lengths, cut and colours follow; the open
        label stays – if it does not fit, the status bar says so."""
        self.model = model
        self.canvas.set_model(model)
        self.panel("paper").set_model(model)
        self._update_cut_choices()
        self._fit_label()
        self.schedule_render()

    def _update_cut_choices(self) -> None:
        """SERIES tab: cut by printer – Brother: after each/only at the end, or the note
        when there is no cutter; CUPS: the cutting options of its driver; Zebra: the mode."""
        panel = self.panel("series")
        chosen = self.settings.printer_options.get(self._options_key(), {})
        if self.model.startswith("cups:"):
            panel.set_driver_cuts(cups.queue_info(self.model[len("cups:"):]).cut_options, chosen)
        elif zpl.is_model(self.model):
            panel.set_driver_cuts((zpl.cut_option(),), chosen)
        else:
            panel.set_cutter(capabilities(self.model).cutter)
        self._update_tool_buttons()                 # SERIES: cutting options of the printer

    def _options_key(self) -> str:
        """Under this key the print options are kept in the settings: the model
        (“cups:NAME” or “zpl:203” – the number lpN of a USB device changes on plugging in)."""
        return self.model

    def _driver_cut_chosen(self, key: str, value: str) -> None:
        """Cutting option or mode chosen – applies to this printer (settings)."""
        if self.model.startswith("cups:") or zpl.is_model(self.model):
            self.settings.printer_options.setdefault(self._options_key(), {})[key] = value
            self._save_settings("printer_options")

    def _fit_label(self) -> None:
        """If the label does not fit the model: a new, untouched label takes a fitting one
        (``FileSession.fitting_label``), otherwise it stays with a note (file, favourite, changes)."""
        label = self.doc.label_id
        if label in {lbl.id for lbl in labels_for_model(self.model)}:
            return
        if self.files.may_follow_roll() and not self.files.modified():
            change_label(self.doc, self.files.fitting_label(label))
            self.panel("paper").refresh()
            self.history.reset(self.doc)            # untouched: no step back to the unfitting one
            self.files.mark_unchanged()
            self._set_result(_("Label {label} does not fit the {model} – using {new}").format(
                label=get_label(label).description, model=self.model,
                new=get_label(self.doc.label_id).description), "warn")
            return
        self._set_result(_("Label {label} does not fit the printer ({model}) – choose another one "
                           "in the Paper tab").format(label=get_label(label).description,
                                                      model=self.model), "error")

    def _run_pending_media_check(self) -> None:
        """Catch up the automatic check as soon as neither printing nor checking is running."""
        if self._media_check_pending and not self.is_printing() and not self.is_checking_media():
            self._media_check_pending = False
            self.check_media()

    def start(self, path: str | None = None) -> None:
        """After the window opens: file from the command line, otherwise the start favourite
        (as a new label), otherwise the empty label stays."""
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
            event.ignore()                          # Cancel: window stays open
            return
        self._printer_timer.stop()
        if self.symbol_window is not None:
            self.symbol_window.close()              # otherwise it would keep the app open
        self._restore_timer.stop()
        self._shot_pending = False                  # no selection and no inserting any more
        if self._shooting:
            self._end_shooting()
        self.settings.window_state = bytes(self.saveState().toBase64()).decode("ascii")
        changed = {key: getattr(self.settings, key) for key, stored in
                   (("last_tool", self._stored_tool), ("window_state", self._stored_state))
                   if getattr(self.settings, key) != stored}
        if changed:                                 # last used tab, side bar: silently
            try:
                update_settings(base=self.settings, **changed)
                self._stored_tool, self._stored_state = (self.settings.last_tool,
                                                         self.settings.window_state)
            except OSError:
                pass                                # on quitting: nothing more to report
        super().closeEvent(event)

    # --- Settings ---------------------------------------------------------
    def apply_theme_icons(self) -> None:
        """Symbols that depend on the design (white on black only with BlackWerk)."""
        dark = self.settings.theme == "blackwerk"
        for panel in self._panel_by_key.values():
            panel.set_icon_style(dark)
        for entry in EDIT_BAR:
            if entry is not None:
                self.shortcut_actions[entry[0]].setIcon(line_icon(entry[1], dark, hover=True))

    def apply_font_list(self) -> None:
        """Font choice in the TEXT tab: short list or all (setting “Show all fonts”)."""
        if "text" in self._panel_by_key:
            self._panel_by_key["text"].family.set_families(fonts.families(all=self.settings.fonts_all))

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, model=self.model, parent=self, started=self._started)
        accepted = dialog.exec() == SettingsDialog.DialogCode.Accepted
        saved = dialog.saved
        dialog.deleteLater()                    # do not keep until the window closes
        if accepted and saved is not None:
            # while the dialog was open, printer/last model may have changed
            saved.printer, saved.last_model = self.settings.printer, self.settings.last_model
            saved.printer_options = self.settings.printer_options
            saved.last_tool = self.settings.last_tool
            if saved.printer.startswith(("tcp://", "zpl+tcp://")) and saved.printer not in {
                    p.uri for p in network_printers(network_entries(saved))}:
                saved.printer = ""                  # network printer removed/changed: automatic
            hidden_changed = set(saved.hidden_tools) != set(self.settings.hidden_tools)
            self.settings = saved
            self._save_settings()
            from PySide6.QtWidgets import QApplication
            from .app import apply_theme
            apply_theme(QApplication.instance(), self.settings.theme)
            self.apply_theme_icons()
            QTimer.singleShot(0, self, lambda: self.fit_toolbars(resize=False))   # measure the new theme
            self.apply_font_list()
            self.apply_hidden_tools(fall_back=hidden_changed)
            apply_shortcuts(self.shortcut_actions,
                            without_conflicts(effective(self.settings.shortcuts))[0])
            self.files.refresh_lists()                  # "At start" in the FILE tab
            self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
            self.refresh_printer()                      # network printers, fallback model
            self._set_result(_("Settings saved – they apply to new labels."), "ok")

    # --- Check media ----------------------------------------------------
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
        """Roll detected: a new label follows it (if it was untouched, it stays so); an
        opened file or a favourite stays with its label – the panel shows “does not fit”."""
        self._media_finished()
        if self._media_uri != self._usb_uri():      # another printer meanwhile: the roll does not count
            return
        adjusted = (label_id is not None and label_id != self.doc.label_id
                    and self.files.may_follow_roll())
        if adjusted:
            unchanged = not self.files.modified()
            editing = self.edit_session.active
            if editing:     # state before the edit with the new roll: a step of its own before
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
        """Accept a number just typed: number fields without keyboard tracking and editable
        selection lists (font size) report their value only on Enter or on leaving –
        PRINT in the tool bar and shortcuts do not take the focus. Call before printing, saving
        and undo."""
        widget = QApplication.focusWidget()
        if isinstance(widget, QLineEdit) and isinstance(widget.parent(), QComboBox):
            widget = widget.parent()
        if isinstance(widget, QAbstractSpinBox):
            widget.interpretText()
        elif isinstance(widget, QComboBox) and widget.isEditable():
            widget.lineEdit().editingFinished.emit()

    def print_label(self) -> None:
        self.accept_pending_input()
        if self._parcel_locked():                   # PARCEL tab with label: print only that
            panel = self.panel("parcel")
            if panel.documents():
                self.print_documents(panel.documents())   # what the canvas shows
            else:
                self._set_result(panel.error or _(PARCEL_CHOOSE_TYPE), "error")
            return
        if self._timer.isActive():
            self.render_now()
        if self.doc.series is not None:             # renders each row itself (error: “Row n”)
            panel = self.panel("series")
            if panel.check_file():                  # table changed outside: the selection is new
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
            self._set_result(self._render_error, "error")   # do not silently do nothing
            return
        if self.image is None:
            return
        self._print(self.image, self.doc, self._outside)

    def _print_series(self, doc: Document, table: series.Table,
                      rows: list[tuple[int, list[str]]]) -> None:
        """Print the chosen rows: first check roll/print and ask for the count, then
        render each row (progress in the status bar), name rows that stick out over the label
        and ask – one job. If a row fails, nothing is printed."""
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
        model, printer = self.model, self.printer   # applies to the whole series
        images, outside = [], []
        doc = copy.deepcopy(doc)                    # input during preparation does not count
        renderer = Renderer()                       # unchanged objects from the cache
        red = get_label(doc.label_id).two_color and capabilities(model).two_color
        self._set_printing(True)                    # locked while preparing
        self._cancel_requested = False
        self.cancel_button.setVisible(len(rows) > 1)
        try:
            for done, (number, values) in enumerate(rows):
                if done % PROGRESS_EVERY == 0 and len(rows) > PROGRESS_EVERY:
                    self._set_result(_("Preparing {current}/{total} …").format(
                        current=done + 1, total=len(rows)), "")
                    QApplication.processEvents()    # also “Cancel”
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
                images.append(to_print_mode(result.image, red))   # 1 bit: little memory
        finally:
            self._set_printing(False)
            self.cancel_button.hide()
        if outside and not self.confirm_outside_rows(outside):
            self._set_result("", "")
            return
        cut = doc.series.cut if capabilities(model).cutter else "each"   # without cutter: small parts
        self._print(images, doc, [], cut_interval(cut, len(images)), model, printer)

    def confirm_outside_rows(self, numbers: list[int]) -> bool:
        """Prompt: rows in which something sticks out over the label (replaceable in tests)."""
        shown = ", ".join(map(str, numbers[:10])) + (" …" if len(numbers) > 10 else "")
        text = ngettext("Row {rows} extends beyond the label and will be cut off. Print anyway?",
                        "Rows {rows} extend beyond the label and will be cut off. Print anyway?",
                        len(numbers)).format(rows=shown)
        return QMessageBox.question(
            self, _("Object sticks out"), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def ask_print_count(self, count: int) -> bool:
        """Prompt before printing a series (replaceable in tests)."""
        text = ngettext("Print {count} label?", "Print {count} labels?", count).format(count=count)
        return QMessageBox.question(
            self, _("Print series"), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes

    def print_document(self, doc: Document) -> None:
        """Print another label (favourite) without touching the open one – same prompts;
        with a series all rows."""
        if self.is_printing():
            self._set_result(_(PRINTING_WAIT), "error")
            return
        if doc.series is not None:
            try:
                table = series.table_for(doc.series)
            except ValueError as e:                  # SeriesError
                self._set_result(str(e), "error")
                return
            except Exception as e:  # untrusted file: message instead of a traceback
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
        except Exception as e:  # untrusted file: message instead of a traceback
            self._set_result(_("Cannot print the label ({error})").format(
                error=type(e).__name__), "error")
            return
        self._print(image, doc, outside)

    def _can_print(self, doc: Document) -> bool:
        """Checkable before rendering: chosen printer present, label fits the model (message)."""
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
        """``image``: a print image or a list (series, one job); ``model``/``printer``:
        fixed at the start of a series (otherwise the current ones)."""
        if self.is_checking_media():
            self._set_result(_(CHECKING_ROLL), "error")
            return
        if model is None:
            if not self._can_print(doc):
                return
            model, printer = self.model, self.printer
        # Printing locks the media check before the dialog (timer keeps running meanwhile)
        self._set_printing(True)
        if doc.is_empty() and not self.confirm_empty():
            self._set_printing(False)
            return
        if outside and not self.confirm_outside():
            self._set_printing(False)
            return
        self.result.setProperty("state", "")  # do not leave old red/green standing
        self.result.style().polish(self.result)
        self.result.setText(_("Printing …"))
        options = (self.settings.printer_options.get(model, {})
                   if model.startswith("cups:") or zpl.is_model(model) else {})
        worker = PrintWorker(image, doc.label_id, model, cut_every,
                             printer=printer.uri if printer else None, options=options)
        self._print_signals = worker.signals  # reference until the end of printing
        self._worker = worker
        worker.signals.done.connect(self._print_done)
        worker.signals.failed.connect(self._print_failed)
        worker.signals.progress.connect(
            lambda done, total: self._set_result(
                _("Printing … {done} of {total}").format(done=done, total=total), ""))
        worker.signals.cancelled.connect(self._print_cancelled)
        # over the network a series goes out as one job (no status): nothing to cancel
        self.cancel_button.setVisible(isinstance(image, list) and len(image) > 1
                                      and (printer is None or printer.source == "usb"))
        QThreadPool.globalInstance().start(worker)

    def cancel_print(self) -> None:
        """“Cancel”: while preparing at once (nothing printed), while printing before the next
        partial job."""
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
        """“Check media” works only via USB and not during a print."""
        network = self.printer is not None and self.printer.source != "usb"   # network, CUPS
        check = self.panel("paper").check
        missing = self.printer is None and bool(self.settings.printer)     # chosen one is missing
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
    """Panel that edits an object."""
    return ("image" if isinstance(obj, ImageObject) else "barcode"
            if isinstance(obj, BarcodeObject) else "text")


def _keeps_aspect(obj: TextObject | ImageObject | BarcodeObject) -> bool:
    """Handles keep the aspect ratio on the edges too: image with “Keep aspect
    ratio”, QR code (square)."""
    return (isinstance(obj, ImageObject) and obj.keep_ratio
            or isinstance(obj, BarcodeObject) and obj.kind == "qr")


@dataclass(frozen=True)
class _ClipboardState:
    """What the system clipboard offers – remembered on change, so that enabling
    the buttons (at every step) fetches no data. ``token``: ID of a selection
    copied here (``MIME_OBJECTS``, a few bytes)."""
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
    """Copy, offset by ``PASTE_OFFSET_MM`` to the right and down."""
    moved = copy.deepcopy(obj)
    moved.x_mm = round((obj.x_mm or 0.0) + PASTE_OFFSET_MM, 3)
    moved.y_mm = round((obj.y_mm or 0.0) + PASTE_OFFSET_MM, 3)
    return moved
