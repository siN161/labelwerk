"""Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QSizePolicy, QStackedWidget,
                               QToolBar, QToolButton, QWidget)

from ..document import Document, TextObject
from ..labels import get_label
from ..printer import DEFAULT_MODEL
from ..render import render_document
from .canvas import Canvas
from .tools import TOOLS, Tool

RENDER_DELAY_MS = 150


class MainWindow(QMainWindow):
    def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                 model: str = DEFAULT_MODEL):
        super().__init__()
        self.setWindowTitle("labelwerk")
        self.resize(1100, 700)
        self.doc = doc or Document(objects=[TextObject()])
        self.model = model
        self.image = None

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
        self.toolbar = toolbar

        # Arbeitsfläche
        self.canvas = Canvas(model)
        self.canvas.length_changed.connect(self._on_length_dragged)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.panels)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        # Statusleiste: Zoom
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
            self.panel("text").show_error(str(e))
            return
        self.panel("text").show_error(None)
        self.image = image
        self.canvas.set_document(get_label(self.doc.label_id), image)

    def _on_length_dragged(self, length_mm) -> None:
        self.doc.length_mm = length_mm
        self.panel("paper").refresh()
        self.schedule_render()
