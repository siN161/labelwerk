"""Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSizePolicy,
                               QStackedWidget, QToolBar, QToolButton, QWidget)

from ..desktop import APP_NAME
from ..detect import brother_busy, find_brother_lp
from ..document import Document, TextObject
from ..labels import get_label
from ..layout import Rect, move, objects_outside, printable_area, resize
from ..printer import DEFAULT_MODEL
from ..render import RenderedObject, compose, font_warnings, label_size, render_object
from ..settings import Settings, load_settings, new_document
from ..shortcuts import effective
from .actions import apply_shortcuts, build_actions
from .canvas import Canvas
from .media_worker import MediaWorker
from .print_worker import PrintWorker
from .settings_dialog import SettingsDialog
from .tools import TOOLS, Tool

RENDER_DELAY_MS = 150
MEDIA_STATUS_MAX_PX = 360   # Rollen-Hinweis in der Fußzeile; Rest per „…“ und Tooltip
PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff
NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
_DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"


@dataclass
class _Cached:
    """Gerendertes Objekt samt Stand, aus dem es entstand (Neu-Rendern nur bei Änderung)."""
    obj: TextObject            # hält das Objekt fest, damit seine id nicht neu vergeben wird
    snapshot: TextObject
    key: tuple
    rendered: RenderedObject


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
        self.rendered: list[RenderedObject] = []    # Objektbilder auf der Arbeitsfläche = im Druck
        self._cache: dict[int, _Cached] = {}
        self._render_error: str | None = None
        self._hint: str | None = None               # Hinweis (ragt hinaus, Schrift ersetzt)
        self._print_signals = None
        self._media_signals = None
        self._printer_present = False
        self._printing = False
        self._media_check_pending = False

        # Werkzeugleiste + Panels aus der Registry
        toolbar = QToolBar("Werkzeuge")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)
        self.panels = QStackedWidget()
        self.panels.setObjectName("panels")
        self.panels.setFixedWidth(280)
        self.tool_actions: dict[str, QAction] = {}
        self._panel_by_key = {}
        group = QActionGroup(self)
        for index, tool in enumerate(tools):
            panel = tool.panel(self.doc)
            panel.changed.connect(self.schedule_render)
            self.panels.addWidget(panel)
            self._panel_by_key[tool.key] = panel
            action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, i=index: self.panels.setCurrentIndex(i))
            group.addAction(action)
            toolbar.addAction(action)
            self.tool_actions[tool.key] = action
        next(iter(self.tool_actions.values())).setChecked(True)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.settings_action = QAction(QIcon.fromTheme("preferences-system"), "EINSTELLUNGEN", self)
        self.settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(self.settings_action)
        self.print_action = QAction(QIcon.fromTheme("document-print"), "DRUCKEN", self)
        self.print_action.triggered.connect(self.print_label)
        toolbar.addAction(self.print_action)
        toolbar.widgetForAction(self.print_action).setObjectName("print")

        # Arbeitsfläche
        self.canvas = Canvas(model)
        self.canvas.set_zoom(self.settings.start_zoom)
        self.apply_theme_icons()
        self.canvas.length_changed.connect(self._on_length_dragged)
        self.canvas.drag_finished.connect(self.render_now)
        self.canvas.objects_moved.connect(self._move_objects)
        self.canvas.object_resized.connect(self._resize_object)
        self.actions = build_actions(self, effective(self.settings.shortcuts))
        self._connect_canvas_actions()
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.panels)
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
        for text, delta in (("−", -10), ("+", 10)):
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
        self.refresh_printer()
        if self.settings.warnings:
            self._set_result(" · ".join(self.settings.warnings), "error")

    def panel(self, key: str):
        return self._panel_by_key[key]

    def _connect_canvas_actions(self) -> None:
        """Kürzel der Arbeitsfläche: Pfeiltasten, Löschen, Alles auswählen."""
        for direction, (sx, sy) in _DIRECTIONS.items():
            for suffix, step in NUDGE_MM.items():
                action = self.actions[f"object.nudge_{direction}{suffix}"]
                action.triggered.connect(
                    lambda _=False, dx=sx * step, dy=sy * step: self.canvas.nudge(dx, dy))
                self.canvas.addAction(action)
        self.actions["edit.delete"].triggered.connect(self.delete_selected)
        self.actions["edit.select_all"].triggered.connect(self.canvas.select_all)
        self.canvas.addActions([self.actions["edit.delete"], self.actions["edit.select_all"]])

    # --- Rendern ----------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        if self.canvas.is_dragging():   # Ziehen nicht unterbrechen – nach dem Loslassen rendern
            self._timer.start()
            return
        try:
            size = label_size(self.doc, self.model)
            rendered = self._render_objects(size)
            image = compose(rendered, size, self.doc.orientation)
            area = printable_area(self.doc, self.model)
            outside = objects_outside(self.doc, self.model)
        except ValueError as e:
            # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
            self._render_error = str(e)
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
        self._render_error = None
        if self._hint is not None and self.result.text() == self._hint:
            self._set_result("", "")   # alten Hinweis nur löschen, wenn er noch dasteht
        self._hint = None
        hints = ([OUTSIDE_HINT] if outside else []) + font_warnings(self.doc)
        if hints and not self.result.text():
            self._hint = " · ".join(hints)
            self._set_result(self._hint, "error")
        self.panel("text").show_error(None)
        self.image = image
        self.rendered = rendered
        self.canvas.set_document(get_label(self.doc.label_id), size, rendered, self.doc.orientation,
                                 area, keep_ratio=[not obj.fit for obj in self.doc.objects])

    def _render_objects(self, size: tuple[int, int]) -> list[RenderedObject]:
        """Objekte einzeln rendern; unveränderte kommen aus dem Cache.

        Ein Objekt ohne Position steht mittig und hängt deshalb auch von der Etikettgröße ab.
        """
        doc = self.doc
        context = (self.model, doc.label_id, doc.orientation, doc.margin_mm, doc.length_mm)
        cache: dict[int, _Cached] = {}
        for obj in doc.objects:
            key = (context, None if obj.positioned else size)
            entry = self._cache.get(id(obj))
            if entry is None or entry.obj is not obj or entry.key != key or entry.snapshot != obj:
                entry = _Cached(obj, copy.deepcopy(obj), key, render_object(obj, doc, self.model))
            cache[id(obj)] = entry
        self._cache = cache
        return [cache[id(obj)].rendered for obj in doc.objects]

    # --- Objekte auf der Arbeitsfläche ------------------------------------
    def _move_objects(self, indices: list[int], rects: list[Rect]) -> None:
        for index, rect in zip(indices, rects):
            if index < len(self.rendered):
                self.doc.objects[index] = move(self.doc.objects[index], rect, self.rendered[index])
        self._objects_changed(indices)

    def _resize_object(self, index: int, rect: Rect, handle: str) -> None:
        if index < len(self.rendered):
            self.doc.objects[index] = resize(self.doc.objects[index], rect, self.rendered[index],
                                             corner=len(handle) == 2)
        self._objects_changed([index])

    def delete_selected(self) -> None:
        """Ausgewählte Objekte löschen; ein leerer Text bleibt, damit das Text-Panel etwas hat."""
        indices = self.canvas.selection()
        if not indices:
            return
        self.canvas.set_selection([])
        for index in sorted(indices, reverse=True):
            del self.doc.objects[index]
        if not self.doc.objects:
            self.doc.objects.append(new_document(self.settings).objects[0])
        self._objects_changed([0])

    def _objects_changed(self, indices: list[int]) -> None:
        if 0 in indices:
            self.panel("text").refresh()   # Text-Panel bearbeitet (noch) das erste Objekt
        self.render_now()

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        if not self.canvas.is_dragging():   # beim Ziehen erst nach dem Loslassen rendern
            self.schedule_render()

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
        self.panel("text").set_icon_style(self.settings.theme == "rawblock")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, model=self.model, parent=self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted and dialog.saved is not None:
            self.settings = dialog.saved
            from PySide6.QtWidgets import QApplication
            from .app import apply_theme
            apply_theme(QApplication.instance(), self.settings.theme)
            self.apply_theme_icons()
            apply_shortcuts(self.actions, effective(self.settings.shortcuts))
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
        self.panel("paper").show_media(media, label_id, adjusted)

    def _media_failed(self, message: str) -> None:
        self._media_finished()
        self.panel("paper").show_media_error(message)

    def _media_finished(self) -> None:
        self._media_signals = None
        self.panel("paper").set_checking(False)
        self._run_pending_media_check()

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
