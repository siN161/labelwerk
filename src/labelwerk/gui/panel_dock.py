"""Side bar dock with its own title bar: dragging shows where it docks, a button detaches it.

Qt's own dock dragging lets the floating dock follow the mouse – under Wayland an application may
not move its windows, so the panel stood still in the middle and docking only happened by chance.
Here the dock stays docked while dragging; a preview shows the edge (left or right half of the
window) where it lands on release. A detached dock is moved by the window system
(``startSystemMove`` – works under Wayland too); the button or a double click docks it again.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QDockWidget, QHBoxLayout, QLabel, QMainWindow,
                               QToolButton, QWidget)

from ..i18n import _

LEFT, RIGHT = Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea


class DockPreview(QWidget):
    """Where the dock lands: a translucent strip at the left or right edge of the window."""

    def __init__(self, window: QMainWindow):
        super().__init__(window)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        color = QColor(self.palette().highlight().color())
        color.setAlpha(70)
        painter.fillRect(self.rect(), color)
        painter.setPen(QPen(self.palette().text().color(), 3))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))


class DockTitle(QWidget):
    """Title bar of the side bar: name, button "detach/dock"; dragging moves the dock."""

    def __init__(self, dock: PanelDock):
        super().__init__(dock)
        self.dock = dock
        self.setObjectName("dockTitle")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 2, 2)
        self.label = QLabel(dock.windowTitle())
        self.float_button = QToolButton()
        self.float_button.setObjectName("dockFloat")
        self.float_button.setAutoRaise(True)
        self.float_button.clicked.connect(lambda: dock.setFloating(not dock.isFloating()))
        layout.addWidget(self.label, 1)
        layout.addWidget(self.float_button)
        self._press: QPoint | None = None
        self._dragging = False
        dock.topLevelChanged.connect(self._update_button)
        self._update_button()

    def _update_button(self, *_args) -> None:
        floating = self.dock.isFloating()
        self.float_button.setText("⇲" if floating else "⧉")
        self.float_button.setToolTip(_("Dock in the window") if floating
                                     else _("Detach as a window of its own"))
        self.setToolTip("" if floating else _("Drag to the left or right edge to dock there"))

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        if self.dock.isFloating():
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()                # the window system moves it (Wayland too)
            return
        self._press = event.globalPosition().toPoint()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._press is None:
            return super().mouseMoveEvent(event)
        point = event.globalPosition().toPoint()
        if not self._dragging and ((point - self._press).manhattanLength()
                                   < QApplication.startDragDistance()):
            return
        self._dragging = True
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.dock.show_preview(self.dock.side_at(point))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._press is not None and self._dragging:
            self.dock.dock_at(self.dock.side_at(event.globalPosition().toPoint()))
        self._press, self._dragging = None, False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.dock.hide_preview()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        self.dock.setFloating(not self.dock.isFloating())
        event.accept()


class PanelDock(QDockWidget):
    """Dock of the properties panels: left or right, wider by dragging its edge, detachable."""

    def __init__(self, title: str, window: QMainWindow):
        super().__init__(title, window)
        self.setObjectName("panelDock")
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.setAllowedAreas(LEFT | RIGHT)
        self.setTitleBarWidget(DockTitle(self))
        self.preview = DockPreview(window)

    def _main(self) -> QMainWindow:
        return self.parentWidget()

    def side_at(self, global_point: QPoint) -> Qt.DockWidgetArea:
        """Left or right half of the window under the mouse."""
        window = self._main()
        return RIGHT if window.mapFromGlobal(global_point).x() > window.width() / 2 else LEFT

    def show_preview(self, side: Qt.DockWidgetArea) -> None:
        window = self._main()
        central = window.centralWidget()
        top = central.geometry().top() if central is not None else 0
        height = central.height() if central is not None else window.height()
        width = self.width()
        x = 0 if side == LEFT else window.width() - width
        self.preview.setGeometry(QRect(x, top, width, height))
        self.preview.raise_()
        self.preview.show()

    def hide_preview(self) -> None:
        self.preview.hide()

    def dock_at(self, side: Qt.DockWidgetArea) -> None:
        window = self._main()
        if window.dockWidgetArea(self) != side:
            width = self.width()
            window.addDockWidget(side, self)
            window.resizeDocks([self], [width], Qt.Orientation.Horizontal)   # keeps its width
