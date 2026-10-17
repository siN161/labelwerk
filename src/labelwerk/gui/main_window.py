"""Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSizePolicy,
                               QStackedWidget, QToolBar, QToolButton, QWidget)

from ..desktop import APP_NAME
from ..detect import brother_busy, find_brother_lp
from ..document import Document, TextObject
from ..labels import get_label
from ..printer import DEFAULT_MODEL
from ..render import render_document
from .canvas import Canvas
from .print_worker import PrintWorker
from .tools import TOOLS, Tool

RENDER_DELAY_MS = 150


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str = DEFAULT_MODEL):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.doc = doc if doc is not None else Document(objects=[TextObject()])
        self.model = model
        self.image = None
        self._render_error: str | None = None
        self._print_signals = None

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
        self.print_action = QAction(QIcon.fromTheme("document-print"), "DRUCKEN", self)
        self.print_action.triggered.connect(self.print_label)
        toolbar.addAction(self.print_action)
        toolbar.widgetForAction(self.print_action).setObjectName("print")

        # Arbeitsfläche
        self.canvas = Canvas(model)
        self.canvas.length_changed.connect(self._on_length_dragged)
        self.canvas.drag_finished.connect(self.render_now)
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
        self.render_now()
        self.refresh_printer()

    def panel(self, key: str):
        return self._panel_by_key[key]

    # --- Rendern ----------------------------------------------------------
    def schedule_render(self) -> None:
        self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        try:
            image = render_document(self.doc, self.model)
        except ValueError as e:
            # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
            self._render_error = str(e)
            self.panel("text").show_error(self._render_error)
            self._set_result(self._render_error, "error")
            return
        if self._render_error is not None and self.result.text() == self._render_error:
            self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
        self._render_error = None
        self.panel("text").show_error(None)
        self.image = image
        self.canvas.set_document(get_label(self.doc.label_id), image)

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        if not self.canvas.is_dragging():   # beim Ziehen erst nach dem Loslassen rendern
            self.schedule_render()

    def _set_result(self, text: str, state: str) -> None:
        self.result.setProperty("state", state)
        self.result.style().polish(self.result)
        self.result.setText(text)

    # --- Drucken ----------------------------------------------------------
    def refresh_printer(self) -> None:
        try:
            printer = find_brother_lp()
            if printer:
                text = f"● {self.model} · {Path(printer).name}"
            elif brother_busy():
                text = "● Drucker belegt (andere Anwendung)"
            else:
                text = "○ kein Drucker"
        except OSError:
            text = "○ Druckerstatus unbekannt"
        self.printer_status.setText(text)

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
        if self.doc.is_empty() and not self.confirm_empty():
            return
        self.print_action.setEnabled(False)
        self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
        self.result.style().polish(self.result)
        self.result.setText("Drucke …")
        worker = PrintWorker(self.image, self.doc.label_id, self.model)
        self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
        worker.signals.done.connect(self._print_done)
        worker.signals.failed.connect(self._print_failed)
        QThreadPool.globalInstance().start(worker)

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
        self.print_action.setEnabled(True)
        self.refresh_printer()
