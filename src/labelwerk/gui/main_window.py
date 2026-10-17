"""Hauptfenster: Werkzeugleiste, Bearbeitungsleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                               QWidget)

from ..desktop import APP_NAME
from ..detect import brother_busy, find_brother_lp
from ..document import Document, TextObject
from ..fonts import DEFAULT_FAMILY
from ..labels import get_label
from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, growing_axis,
                      match_objects, maximize_object, move, object_rect, outside_indices,
                      printable_area, reorder, resize, rotate, set_frame, to_grid)
from ..printer import DEFAULT_MODEL
from ..render import (Prepared, RenderedObject, compose, finish_object, font_warnings,
                      label_size, prepare_object)
from ..settings import Settings, load_settings, new_document
from ..shortcuts import effective, without_conflicts
from .actions import apply_shortcuts, build_actions
from .canvas import Canvas
from .history import History, restore
from .media_worker import MediaWorker
from .panels.text import DEFAULT_PT
from .print_worker import PrintWorker
from .settings_dialog import SettingsDialog
from .symbols import SIZE, line_icon
from .tools import TOOLS, Tool

RENDER_DELAY_MS = 150
PANEL_WIDTH = 280          # Eigenschaften-Panels; bei wenig Höhe rollbar
MEDIA_STATUS_MAX_PX = 360   # Rollen-Hinweis in der Fußzeile; Rest per „…“ und Tooltip
PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff
ZOOM_STEP = 10             # Prozentpunkte je Klick bzw. Kürzel
NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
_DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"
PASTE_OFFSET_MM = 2.0      # Einfügen/Duplizieren: versetzt nach rechts und unten
# Bearbeitungsleiste: Aktion und eigenes Symbol (gui/icons); None = Trenner
EDIT_BAR = (("tool.select", "tool-select"), ("tool.text", "tool-text"), None,
            ("edit.cut", "edit-cut"), ("edit.copy", "edit-copy"), ("edit.paste", "edit-paste"),
            None, ("edit.undo", "edit-undo"), ("edit.redo", "edit-redo"))
_SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
SELECTION_PANELS = ("text", "layout")   # arbeiten mit der Auswahl: Wählen wechselt nicht weg


@dataclass
class _Cached:
    """Gemessenes und gerendertes Objekt samt Stand, aus dem es entstand.

    Gemessen wird nur bei Änderung des Objekts bzw. des Etiketts; gezeichnet zusätzlich,
    wenn sich bei einem Objekt ohne Position (steht mittig) die Etikettgröße ändert."""
    obj: TextObject            # hält das Objekt fest, damit seine id nicht neu vergeben wird
    snapshot: TextObject
    context: tuple
    prepared: Prepared
    size: tuple | None = None                  # Etikettgröße des Bilds (None = mit Position)
    rendered: RenderedObject | None = None


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str = DEFAULT_MODEL, settings: Settings | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.settings = settings if settings is not None else load_settings(model=model)
        self.doc = doc if doc is not None else new_document(self.settings)
        self.model = model
        self.image = None
        self._shown_size = (0, 0)                   # Etikettgröße der letzten gültigen Anzeige
        self._structure_dirty = False               # Objektliste seit der letzten Anzeige umgebaut
        self.rendered: list[RenderedObject] = []    # Objektbilder auf der Arbeitsfläche = im Druck
        self._cache: dict[int, _Cached] = {}
        self._render_error: str | None = None
        self._hint: str | None = None               # Hinweis (ragt hinaus, Schrift ersetzt)
        self._print_signals = None
        self._media_signals = None
        self._printer_present = False
        self._printing = False
        self._media_check_pending = False
        self._clipboard: list[TextObject] = []      # interne Zwischenablage (Kopien)
        self._merge_next = None                     # Pfeiltasten: Schritte zusammenfassen
        self._restoring = False                     # Rückgängig setzt gerade die Auswahl
        self._arranging = False                     # Auswahl wird intern umgestellt (Anlegen …)
        self._outside: list[int] = []               # Objekte, die über das Etikett ragen
        self._area = Rect(0, 0, 0, 0)               # bedruckbarer Bereich (mm), mit dem Bild
        self._composed: tuple = (None, [], None)    # Druckbild und woraus es entstand
        # alle Kürzel kommen aus dem Verzeichnis (shortcuts.ACTIONS) und sind änderbar;
        # doppelt belegte (von Hand bearbeitete Datei): die spätere Aktion bleibt ohne Kürzel
        keys, key_warnings = without_conflicts(effective(self.settings.shortcuts))
        self.shortcut_actions = build_actions(self, keys)

        # Werkzeugleiste + Panels aus der Registry
        toolbar = QToolBar("Werkzeuge")
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
            action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, key=tool.key: self._tool_triggered(key))
            group.addAction(action)
            toolbar.addAction(action)
            self.tool_actions[tool.key] = action
        next(iter(self.tool_actions.values())).setChecked(True)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.settings_action = self._toolbar_action("app.settings", "preferences-system",
                                                    "EINSTELLUNGEN", self.open_settings)
        toolbar.addAction(self.settings_action)
        self.print_action = self._toolbar_action("file.print", "document-print", "DRUCKEN",
                                                 self.print_label)
        toolbar.addAction(self.print_action)
        toolbar.widgetForAction(self.print_action).setObjectName("print")

        # Arbeitsfläche
        self.canvas = Canvas(model)
        self.canvas.set_zoom(self.settings.start_zoom)
        self.canvas.length_changed.connect(self._on_length_dragged)
        self.canvas.drag_finished.connect(self._length_drag_finished)
        self.canvas.objects_moved.connect(self._move_objects)
        self.canvas.object_resized.connect(self._resize_object)
        self.canvas.text_requested.connect(self.create_text)
        self.canvas.edit_requested.connect(self.edit_text)
        self.canvas.selection_changed.connect(self._update_edit_actions)
        self.canvas.object_clicked.connect(self._show_object_panel)
        self.history = History(self.doc)
        self.history.changed.connect(self._update_edit_actions)
        self._connect_view_actions()
        self._connect_canvas_actions()
        self._connect_layout_actions()
        self._build_edit_bar()
        for panel in self._panel_by_key.values():
            panel.use_actions(self.shortcut_actions)
        self.apply_theme_icons()
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        scroll = QScrollArea()                  # kleine Bildschirme: Panel rollt statt Fenster wächst
        scroll.setObjectName("panelScroll")
        scroll.setWidget(self.panels)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(PANEL_WIDTH + scroll.verticalScrollBar().sizeHint().width())
        layout.addWidget(scroll)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        # Statusleiste: Drucker, Ergebnis, Zoom
        self.printer_status = QLabel()
        self.result = QLabel()
        self.statusBar().addWidget(self.printer_status)
        self.media_status = QLabel()            # Rolle im Drucker (Medium prüfen)
        self.media_status.setObjectName("mediaStatus")
        self.media_status.hide()
        self.statusBar().addWidget(self.media_status)
        self.statusBar().addWidget(self.result, 1)
        self.zoom_label = QLabel()
        for text, delta in (("−", -ZOOM_STEP), ("+", ZOOM_STEP)):
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(lambda _=False, d=delta: self.canvas.set_zoom(self.canvas.zoom + d))
            self.statusBar().addPermanentWidget(button)
            if text == "−":
                self.statusBar().addPermanentWidget(self.zoom_label)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z} %"))
        self.zoom_label.setText(f"{self.canvas.zoom} %")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(RENDER_DELAY_MS)
        self._timer.timeout.connect(self.render_now)
        self.panel("paper").check_media_requested.connect(self.check_media)
        self.panel("paper").media_status_changed.connect(self._show_media_status)
        self._printer_timer = QTimer(self)
        self._printer_timer.setInterval(PRINTER_POLL_MS)
        self._printer_timer.timeout.connect(self.refresh_printer)
        self._printer_timer.start()

        self.render_now()
        if len(self.doc.objects) == 1:     # einziges Objekt: gleich bearbeitbar (Start wie bisher)
            self.canvas.set_selection([0])
            self._follow_selection([0])
        self.canvas.selection_changed.connect(self._on_selection)
        self.panel("text").frame_edited.connect(self._edit_frame)
        self._update_edit_actions()
        self.refresh_printer()
        if self.settings.warnings or key_warnings:
            self._set_result(" · ".join(self.settings.warnings + key_warnings), "error")

    def panel(self, key: str):
        return self._panel_by_key[key]

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
                    "tool.select": lambda: self.canvas.set_tool("select"),
                    "tool.text": lambda: self.canvas.set_tool("text")}
        for key, handler in handlers.items():
            self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
            self.canvas.addAction(self.shortcut_actions[key])
        # global: wirkt überall – außer im Textfeld, das Strg+Z selbst nutzt (eigenes Rückgängig)
        self.shortcut_actions["edit.undo"].triggered.connect(self.undo)
        self.shortcut_actions["edit.redo"].triggered.connect(self.redo)
        self.addActions([self.shortcut_actions["edit.undo"], self.shortcut_actions["edit.redo"]])

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
        bar = QToolBar("Bearbeiten")
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

    def _show_tool(self, key: str) -> None:
        """Panel eines Werkzeugs zeigen (wie ein Klick auf seinen Knopf)."""
        self.tool_actions[key].setChecked(True)
        self.panels.setCurrentWidget(self.panel(key))

    def _tool_triggered(self, key: str) -> None:
        """Werkzeug-Reiter: Panel zeigen; Text ohne Auswahl heißt „Text anlegen“, jedes
        andere Panel arbeitet mit dem Auswahl-Pfeil."""
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
        """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen – außer ein Panel, das mit
        der Auswahl arbeitet (Text, Layout), ist schon zu sehen. Ein leerer Textrahmen, den
        die Auswahl verlässt, entfällt."""
        if self._arranging:                         # Anlegen, Umnummerieren: nur mitführen
            self._follow_selection(indices)
            return
        if not self._restoring:
            indices = self._drop_empty_frames(indices)
        self._follow_selection(indices)
        if self._restoring:                         # Rückgängig wechselt nicht den Reiter
            return
        self.history.select(self.doc, indices)
        if indices:
            self._show_object_panel()
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
        """Vom Papier-Reiter zum Panel des Objekts (auch beim Klick auf ein schon gewähltes)."""
        if not any(self.panels.currentWidget() is self.panel(key) for key in SELECTION_PANELS):
            self._show_tool("text")

    def _follow_selection(self, indices: list[int]) -> None:
        """Panels erfahren die Auswahl; das Text-Panel bearbeitet das zuletzt gewählte Objekt."""
        for panel in self._panel_by_key.values():
            panel.set_selection(indices)
        self.panel("text").set_object(indices[-1] if indices else None)
        self._update_frame()

    def _update_frame(self) -> None:
        """Bereich „Position“: Rahmen des bearbeiteten Objekts, wie er gerendert ist."""
        panel = self.panel("text")
        index = panel.index
        if index is None or index >= len(self.rendered) or index >= len(self.doc.objects):
            panel.show_frame(None)
        else:
            panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))

    def _update_edit_actions(self) -> None:
        selected = bool(self.canvas.selection())
        for key in _SELECTION_ACTIONS:
            self.shortcut_actions[key].setEnabled(selected)
        self.shortcut_actions["edit.paste"].setEnabled(bool(self._clipboard))
        self.shortcut_actions["edit.undo"].setEnabled(self.history.can_undo(self.doc))
        self.shortcut_actions["edit.redo"].setEnabled(self.history.can_redo(self.doc))

    # --- Rendern ----------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        if self.canvas.is_dragging():   # Ziehen nicht unterbrechen – nach dem Loslassen rendern
            self._timer.start()
            return
        try:
            # jedes Objekt höchstens einmal messen und zeichnen; Größe, Fläche und
            # „ragt hinaus“ folgen aus den gerenderten Objekten
            entries = self._prepare_objects()
            size = label_size(self.doc, self.model, prepared=[e.prepared for e in entries])
            rendered = self._render_objects(entries, size)
            image = self._compose(rendered, size)
        except ValueError as e:
            # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
            self._render_error = str(e)
            self._drop_stale_view()
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
        self._render_error = None
        if self._hint is not None and self.result.text() == self._hint:
            self._set_result("", "")   # alten Hinweis nur löschen, wenn er noch dasteht
        self._hint = None
        area = printable_area(self.doc, self.model, size)
        outside = outside_indices(rendered, size, self.doc.objects)
        hints = ([OUTSIDE_HINT] if outside else []) + font_warnings(self.doc)
        if hints and not self.result.text():
            self._hint = " · ".join(hints)
            self._set_result(self._hint, "error")
        self.panel("text").show_error(None)
        self.image = image
        self.rendered = rendered
        self._shown_size = size
        self._structure_dirty = False
        self._outside = outside
        self._area = area
        self.canvas.set_document(get_label(self.doc.label_id), size, rendered, self.doc.orientation,
                                 area, keep_ratio=[not obj.fit for obj in self.doc.objects],
                                 grow=growing_axis(self.doc))
        self.panel("layout").set_growing(growing_axis(self.doc))
        self._update_frame()

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
                                 self._area, keep_ratio=[], grow=growing_axis(self.doc))

    def _prepare_objects(self) -> list[_Cached]:
        """Objekte messen; unveränderte kommen aus dem Cache."""
        doc = self.doc
        context = (self.model, doc.label_id, doc.orientation, doc.margin_mm, doc.length_mm)
        cache: dict[int, _Cached] = {}
        for obj in doc.objects:
            entry = self._cache.get(id(obj))
            if (entry is None or entry.obj is not obj or entry.context != context
                    or entry.snapshot != obj):
                entry = _Cached(obj, copy.deepcopy(obj), context,
                                prepare_object(obj, doc, self.model))
            cache[id(obj)] = entry
        self._cache = cache
        return [cache[id(obj)] for obj in doc.objects]

    def _render_objects(self, entries: list[_Cached], size: tuple[int, int]) -> list[RenderedObject]:
        """Gemessene Objekte zeichnen; ein Objekt ohne Position steht mittig und wird deshalb
        auch neu gezeichnet, wenn sich die Etikettgröße ändert."""
        for entry in entries:
            key = None if entry.obj.positioned else size
            if entry.rendered is None or entry.size != key:
                entry.rendered = finish_object(entry.prepared, self.doc, size, self.model)
                entry.size = key
        return [entry.rendered for entry in entries]

    def _compose(self, rendered: list[RenderedObject], size: tuple[int, int]):
        """Druckbild – unverändert, solange dieselben Objektbilder auf derselben Größe liegen."""
        key = (size, self.doc.orientation)
        if (self.image is None or key != self._composed[0]
                or len(rendered) != len(self._composed[1])
                or any(a is not b for a, b in zip(rendered, self._composed[1]))):
            self._composed = (key, list(rendered), compose(rendered, size, self.doc.orientation))
        return self._composed[2]

    # --- Rückgängig -------------------------------------------------------
    def _commit(self, merge=None) -> None:
        """Stand nach einer abgeschlossenen Aktion festhalten (ohne Änderung kein Schritt).

        Vor jeder Aktion aufgerufen, wird noch nicht Festgehaltenes (Getipptes) ein eigener
        Schritt. Tippen im Textfeld wird ein Schritt, sobald der Fokus das Feld verlässt –
        nicht, während die Auswahl intern umgestellt wird (z. B. Textfeld gesperrt, weil ein
        leerer Rahmen entfällt); das hält der Aufrufer selbst fest."""
        if self._arranging:
            return
        self.history.push(self.doc, merge, self.canvas.selection())
        self._update_edit_actions()

    def undo(self) -> None:
        self._restore(self.history.undo(self.doc, self.canvas.selection()))

    def redo(self) -> None:
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
        resized = resize(self.doc.objects[index], rect, self.rendered[index],
                         corner=len(handle) == 2)
        # nur die gezogenen Kanten auf 0,1 mm (wie die Felder) – die anderen bleiben genau
        self.doc.objects[index] = to_grid(resized, x="l" in handle, y="t" in handle,
                                          w="l" in handle or "r" in handle,
                                          h="t" in handle or "b" in handle)
        self._objects_changed([index])
        self._commit()

    def create_text(self, x_mm: float, y_mm: float) -> None:
        """Neuer leerer Textrahmen an x/y (mm, Leserichtung), ausgewählt, Schreibmarke ins Textfeld.

        Schrift aus den Einstellungen (automatische Größe → 19 pt). Andere leere Texte sind
        unsichtbar und drucken nicht – sie entfallen dabei."""
        self._structure_changing()
        self._commit()
        family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
        obj = TextObject.plain("", size_pt=self.settings.font_size_pt or DEFAULT_PT, family=family)
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
        self._commit()
        self.edit_text(index)

    def edit_text(self, index: int) -> None:
        """Text eines Objekts bearbeiten: auswählen, Text-Panel zeigen, Schreibmarke hinein."""
        if index not in self.canvas.selection():
            self.canvas.set_selection([index])
        self._show_tool("text")
        self.panel("text").edit.setFocus()

    def delete_selected(self) -> None:
        """Ausgewählte Objekte löschen (auch das letzte – das Etikett ist dann leer)."""
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

    def _edit_frame(self, key: str, value: float) -> None:
        """Zahl im Bereich „Position“ geändert: Objekt verschieben bzw. Rahmen ändern."""
        index = self.panel("text").index
        if index is None or not self._valid(index):
            return
        self._commit()
        obj = self.doc.objects[index]
        rect = replace(exact_rect(obj, self.rendered[index]), **{key: round(value, 3)})
        self.doc.objects[index] = set_frame(obj, rect, self.rendered[index])
        self._objects_changed([index])
        self._commit()

    # --- Reiter „Layout“ ---------------------------------------------------
    def align_selected(self, mode: str, paper: bool = False) -> None:
        """Auswahl aneinander bzw. am bedruckbaren Bereich ausrichten."""
        self._change_selected(lambda objs, rendered: align_objects(
            objs, rendered, mode, self._area if paper else None, growing_axis(self.doc)))

    def match_selected(self, mode: str) -> None:
        """Größe, Breite oder Höhe an das zuerst gewählte Objekt angleichen."""
        self._change_selected(lambda objs, rendered: match_objects(objs, rendered, mode))

    def maximize_selected(self) -> None:
        """Jedes gewählte Objekt so groß wie möglich mittig in den bedruckbaren Bereich
        (auf Endlosband mit automatischer Länge nur quer – ``maximize_object``)."""
        self._change_selected(lambda objs, rendered: [
            maximize_object(obj, r, self._area, self.doc, self.model)
            for obj, r in zip(objs, rendered)])

    def rotate_selected(self, degrees: int) -> None:
        """Auswahl um 90° drehen (−90 = links); die Mitte jedes Objekts bleibt."""
        self._change_selected(lambda objs, rendered: [
            rotate(obj, r, degrees) for obj, r in zip(objs, rendered)])

    def _change_selected(self, change) -> None:
        """Gewählte Objekte durch ``change(objekte, gerendert)`` ersetzen – ein Schritt.

        ``change`` läuft nach dem Rendern: Rahmen und ``self._area`` sind aktuell."""
        if self._timer.isActive():
            self.render_now()                   # z. B. eben Getipptes: aktuelle Rahmen
        # leere Rahmen sind unsichtbar und drucken nicht: sie nehmen an Layout-Befehlen nicht teil
        indices = [i for i in self.canvas.selection()
                   if self._valid(i) and not self.doc.objects[i].is_empty()]
        if not indices:
            return
        self._commit()
        changed = change([self.doc.objects[i] for i in indices], [self.rendered[i] for i in indices])
        for index, obj in zip(indices, changed):
            self.doc.objects[index] = obj
        self._objects_changed(indices)
        self._commit()

    def reorder_selected(self, step: int) -> None:
        """Auswahl einen Platz nach vorne (1) bzw. hinten (−1); die Auswahl wandert mit."""
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
        """Ausgewählte Objekte (in Zeichenreihenfolge) in die interne Zwischenablage kopieren."""
        indices = sorted(self.canvas.selection())
        if indices:
            self._clipboard = [self._placed_copy(i) for i in indices]
            self._update_edit_actions()

    def cut_selected(self) -> None:
        self.copy_selected()
        self.delete_selected()

    def paste(self) -> None:
        """Zwischenablage einfügen – jedes Mal 2 mm weiter versetzt; Eingefügtes ist ausgewählt."""
        if self._clipboard:
            self._clipboard = [_offset(obj) for obj in self._clipboard]
            self._insert(copy.deepcopy(self._clipboard))

    def duplicate_selected(self) -> None:
        """Auswahl 2 mm versetzt verdoppeln; die Zwischenablage bleibt unberührt."""
        indices = sorted(self.canvas.selection())
        if indices:
            self._insert([_offset(self._placed_copy(i)) for i in indices])

    def _placed_copy(self, index: int) -> TextObject:
        """Kopie mit Position: ein mittiges Objekt bekommt seine Lage und Schriftgröße fest."""
        obj = self.doc.objects[index]
        if obj.positioned or index >= len(self.rendered):
            return copy.deepcopy(obj)
        rendered = self.rendered[index]
        return move(obj, object_rect(rendered), rendered)

    def _insert(self, objects: list[TextObject]) -> None:
        self._structure_changing()
        self._commit()
        start = len(self.doc.objects)
        self.doc.objects.extend(objects)
        self._objects_changed(list(range(start, len(self.doc.objects))))
        self.canvas.set_selection(list(range(start, len(self.doc.objects))))
        self._commit()

    def _objects_changed(self, indices: list[int]) -> None:
        if self.panel("text").index in indices:
            self.panel("text").refresh()   # z. B. Anfasser schaltet feste Rahmengröße ein
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
        """Statusleiste aktualisieren; beim Erscheinen des Druckers ggf. Medium prüfen."""
        try:
            printer = find_brother_lp()
            if printer:
                text = f"● {self.model} · {Path(printer).name}"
            elif brother_busy():
                text = "● Drucker belegt (andere Anwendung)"
            else:
                text = "○ kein Drucker"
        except OSError:
            printer, text = None, "○ Druckerstatus unbekannt"
        self.printer_status.setText(text)
        present = printer is not None
        if present and not self._printer_present and self.settings.check_media_on_start:
            self._media_check_pending = True
        if not present:
            self._media_check_pending = False
            if self._printer_present:
                self.panel("paper").clear_media()
        self._printer_present = present
        self._run_pending_media_check()

    def _run_pending_media_check(self) -> None:
        """Automatische Prüfung nachholen, sobald weder Druck noch Prüfung laufen."""
        if self._media_check_pending and not self.is_printing() and not self.is_checking_media():
            self._media_check_pending = False
            self.check_media()

    def closeEvent(self, event) -> None:
        self._printer_timer.stop()
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

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, model=self.model, parent=self)
        accepted = dialog.exec() == SettingsDialog.DialogCode.Accepted
        saved = dialog.saved
        dialog.deleteLater()                    # nicht bis zum Schließen des Fensters behalten
        if accepted and saved is not None:
            self.settings = saved
            from PySide6.QtWidgets import QApplication
            from .app import apply_theme
            apply_theme(QApplication.instance(), self.settings.theme)
            self.apply_theme_icons()
            apply_shortcuts(self.shortcut_actions,
                            without_conflicts(effective(self.settings.shortcuts))[0])
            self._set_result("Einstellungen gespeichert – gelten für neue Etiketten.", "ok")

    # --- Medium prüfen ----------------------------------------------------
    def is_printing(self) -> bool:
        return self._printing

    def is_checking_media(self) -> bool:
        return self._media_signals is not None

    def check_media(self) -> None:
        if self.is_printing() or self.is_checking_media():
            return
        worker = MediaWorker(self.model)
        self._media_signals = worker.signals
        worker.signals.found.connect(self._media_found)
        worker.signals.failed.connect(self._media_failed)
        self.panel("paper").set_checking(True)
        QThreadPool.globalInstance().start(worker)

    def _media_found(self, media, label_id) -> None:
        self._media_finished()
        adjusted = label_id is not None and label_id != self.doc.label_id
        if adjusted:
            self.doc.label_id = label_id
            self.panel("paper").refresh()
            self.schedule_render()
            self._commit()
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
            self, "Objekt ragt hinaus",
            "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def confirm_empty(self) -> bool:
        answer = QMessageBox.question(
            self, "Leeres Etikett", "Das Etikett ist leer. Trotzdem drucken?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        return answer == QMessageBox.StandardButton.Yes

    def print_label(self) -> None:
        if self._timer.isActive():
            self.render_now()
        if self.image is None or self._render_error is not None:
            return   # Fehler steht bereits in der Statusleiste
        if self.is_checking_media():
            self._set_result("Rolle wird gerade geprüft – bitte gleich noch einmal drucken.", "error")
            return
        # Druck sperrt die Medium-Prüfung schon vor dem Dialog (Timer läuft währenddessen weiter)
        self._set_printing(True)
        if self.doc.is_empty() and not self.confirm_empty():
            self._set_printing(False)
            return
        if self._outside and not self.confirm_outside():
            self._set_printing(False)
            return
        self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
        self.result.style().polish(self.result)
        self.result.setText("Drucke …")
        worker = PrintWorker(self.image, self.doc.label_id, self.model)
        self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
        worker.signals.done.connect(self._print_done)
        worker.signals.failed.connect(self._print_failed)
        QThreadPool.globalInstance().start(worker)

    def _set_printing(self, printing: bool) -> None:
        self._printing = printing
        self.print_action.setEnabled(not printing)
        self.panel("paper").check.setEnabled(not printing)

    def _print_done(self, status: dict) -> None:
        ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
        self.result.setProperty("state", "ok" if ok else "error")
        self.result.setText("Gedruckt ✓" if ok else f"Status: {status.get('outcome')}")
        self._print_finished()

    def _print_failed(self, message: str) -> None:
        self.result.setProperty("state", "error")
        self.result.setText(message.replace("\n", " "))
        self._print_finished()

    def _print_finished(self) -> None:
        self._print_signals = None
        self.result.style().polish(self.result)
        self._set_printing(False)
        self.refresh_printer()


def _offset(obj: TextObject) -> TextObject:
    """Kopie, um ``PASTE_OFFSET_MM`` nach rechts und unten versetzt."""
    moved = copy.deepcopy(obj)
    moved.x_mm = round((obj.x_mm or 0.0) + PASTE_OFFSET_MM, 3)
    moved.y_mm = round((obj.y_mm or 0.0) + PASTE_OFFSET_MM, 3)
    return moved
