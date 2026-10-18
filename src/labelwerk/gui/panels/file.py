"""Panel „★“: Neu/Öffnen/Speichern, Favoriten (mit Vorschau, ⎙ je Favorit) und Zuletzt geöffnet.

Nur Anzeige: Knöpfe lösen die Aktionen des Hauptfensters aus, Listen melden per Signal, was
gewählt wurde – ausgeführt wird in ``gui.file_session.FileSession``.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QStyle, QToolButton, QWidget)

from ...document import Document
from ...favorites import Favorite
from ...storage import exists
from . import Panel

PREVIEW = QSize(110, 46)            # Vorschau eines Favoriten (eingepasst)
FAVORITE_ROWS = 5                   # so viele Favoriten sichtbar, mehr per Bildlauf
RECENT_ROWS = 6
FAVORITES_HINT = "Noch keine Favoriten – ein Etikett gestalten und „+ AKTUELL“ drücken."
BROKEN = "nicht lesbar"


class _FavoriteRow(QWidget):
    """Zeile: Vorschau, Name, ⎙ (druckt diesen Favoriten)."""

    def __init__(self, favorite: Favorite, preview: QPixmap | None, start: bool, on_print):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if preview is not None:
            self.preview.setPixmap(preview)
        else:
            self.preview.setText(BROKEN)
        self.name = QLabel(f"{favorite.name}{'  ▸ Start' if start else ''}")
        self.name.setTextFormat(Qt.TextFormat.PlainText)    # „<b>“ im Namen bleibt Text
        self.name.setWordWrap(True)
        self.print = QToolButton()
        self.print.setText("⎙")
        self.print.setToolTip(f"„{favorite.name}“ drucken")
        self.print.clicked.connect(on_print)
        row.addWidget(self.preview)
        row.addWidget(self.name, 1)
        row.addWidget(self.print)


class FilePanel(Panel):
    favorite_open = Signal(object)        # Favorite → als neues Etikett öffnen
    favorite_print = Signal(object)       # Favorite → drucken
    favorite_rename = Signal(object)
    favorite_remove = Signal(object)
    favorite_start = Signal(object)       # Favorite → „Beim Start öffnen“ an/aus
    favorites_folder = Signal()           # Ordner öffnen
    favorite_add = Signal()               # „+ AKTUELL“
    recent_open = Signal(str)             # Pfad

    def __init__(self, doc: Document):
        super().__init__(doc, "Datei")
        self._favorites: list[Favorite] = []
        self._start: str | None = None
        self._printing = False
        self._recent: list[str] = []
        row = QHBoxLayout()
        self.new = QPushButton("NEU")
        self.open = QPushButton("ÖFFNEN …")
        row.addWidget(self.new)
        row.addWidget(self.open)
        self.layout_.addLayout(row)
        self.save = QPushButton("SPEICHERN")
        self.save_as = QPushButton("SPEICHERN UNTER …")
        for button in (self.save, self.save_as):          # volle Breite: lange Beschriftung
            self.layout_.addWidget(button)

        self.section("Favoriten")
        self.add_favorite = QPushButton("+ AKTUELL")
        self.add_favorite.setToolTip("Aktuelles Etikett als Favorit speichern")
        self.add_favorite.clicked.connect(self.favorite_add)
        self.layout_.addWidget(self.add_favorite)
        self.favorites_hint = QLabel(FAVORITES_HINT)
        self.favorites_hint.setObjectName("hint")
        self.favorites_hint.setWordWrap(True)
        self.layout_.addWidget(self.favorites_hint)
        self.favorites = QListWidget()
        self.favorites.setObjectName("favorites")
        self.favorites.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _open_on_click(self.favorites, lambda row: self.open_favorite_at(row))
        self.favorites.customContextMenuRequested.connect(self._favorite_context)
        self.layout_.addWidget(self.favorites)

        self.section("Zuletzt geöffnet")
        self.recent = QListWidget()
        self.recent.setObjectName("recent")
        _open_on_click(self.recent, lambda row: self.open_recent_at(row))
        self.layout_.addWidget(self.recent)
        self.layout_.addStretch()

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """Knöpfe lösen die Datei-Aktionen aus (Kürzel im Tooltip, auch nach dem Umbelegen)."""
        for button, key in ((self.new, "file.new"), (self.open, "file.open"),
                            (self.save, "file.save"), (self.save_as, "file.save_as")):
            action = actions[key]
            button.clicked.connect(lambda _=False, a=action: a.trigger())
            button.setToolTip(action.toolTip())
            action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))

    # --- Favoriten --------------------------------------------------------
    def set_favorites(self, favorites: list[tuple[Favorite, QPixmap | None]],
                      start: str | None) -> None:
        """Liste neu füllen: (Favorit, Vorschau oder None = nicht lesbar); ``start`` = Name
        des Start-Favoriten."""
        self._favorites = [f for f, _ in favorites]
        self._start = start
        self.favorites.clear()
        for favorite, preview in favorites:
            item = QListWidgetItem()
            item.setToolTip(str(favorite.path))
            item.setSizeHint(QSize(PREVIEW.width() + 120, PREVIEW.height() + 8))
            self.favorites.addItem(item)
            row = _FavoriteRow(favorite, preview, favorite.name == start,
                               lambda _=False, f=favorite: self.favorite_print.emit(f))
            row.print.setEnabled(not self._printing)
            self.favorites.setItemWidget(item, row)
        self.favorites_hint.setVisible(not favorites)
        self.favorites.setVisible(bool(favorites))
        _fit_height(self.favorites, min(len(favorites), FAVORITE_ROWS), PREVIEW.height() + 8)

    def set_printing(self, printing: bool) -> None:
        """Während eines Drucks sind die ⎙-Knöpfe gesperrt (wie DRUCKEN)."""
        self._printing = printing
        for row in range(self.favorites.count()):
            self.favorites.itemWidget(self.favorites.item(row)).print.setEnabled(not printing)

    def favorite_names(self) -> list[str]:
        return [f.name for f in self._favorites]

    def favorite_preview(self, row: int) -> QPixmap | None:
        widget = self.favorites.itemWidget(self.favorites.item(row))
        pixmap = widget.preview.pixmap()
        return None if pixmap is None or pixmap.isNull() else pixmap

    def open_favorite_at(self, row: int) -> None:
        self.favorite_open.emit(self._favorites[row])

    def print_favorite_at(self, row: int) -> None:
        self.favorite_print.emit(self._favorites[row])

    def favorite_menu(self, row: int) -> QMenu:
        """Kontextmenü eines Favoriten."""
        favorite = self._favorites[row]
        menu = QMenu(self)
        menu.addAction("Öffnen als neues Etikett", lambda: self.favorite_open.emit(favorite))
        menu.addAction("Drucken", lambda: self.favorite_print.emit(favorite))
        menu.addAction("Umbenennen …", lambda: self.favorite_rename.emit(favorite))
        menu.addAction("Löschen …", lambda: self.favorite_remove.emit(favorite))
        start = menu.addAction("Beim Start öffnen", lambda: self.favorite_start.emit(favorite))
        start.setCheckable(True)
        start.setChecked(favorite.name == self._start)
        menu.addAction("Ordner öffnen", self.favorites_folder)
        return menu

    def _favorite_context(self, pos) -> None:
        item = self.favorites.itemAt(pos)
        if item is not None:
            self.favorite_menu(self.favorites.row(item)).exec(
                self.favorites.viewport().mapToGlobal(pos))

    # --- Zuletzt geöffnet -------------------------------------------------
    def set_recent(self, paths: list[str]) -> None:
        """Zuletzt geöffnet: Name, Pfad im Tooltip; fehlt die Datei, ausgegraut."""
        self._recent = list(paths)
        self.recent.clear()
        grey = self.palette().color(self.palette().ColorRole.PlaceholderText)
        for path in paths:
            item = QListWidgetItem(Path(path).stem)
            item.setToolTip(path)
            if not exists(path):
                item.setForeground(grey)
            self.recent.addItem(item)
        rows = min(len(paths), RECENT_ROWS)
        _fit_height(self.recent, rows, self.recent.sizeHintForRow(0) if rows else 0)
        self.recent.setVisible(bool(paths))

    def recent_names(self) -> list[str]:
        return [Path(p).stem for p in self._recent]

    def open_recent_at(self, row: int) -> None:
        self.recent_open.emit(self._recent[row])


def _open_on_click(view: QListWidget, open_row) -> None:
    """Klick und Aktivieren (Eingabe, Doppelklick) öffnen die Zeile – einmal: Stile, die schon
    per Einzelklick aktivieren (z. B. KDE), melden dazu zusätzlich ``itemActivated``."""
    def clicked(item) -> None:
        if not view.style().styleHint(QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick,
                                      None, view):
            open_row(view.row(item))

    view.itemClicked.connect(clicked)
    view.itemActivated.connect(lambda item: open_row(view.row(item)))


def _fit_height(view: QListWidget, rows: int, row_height: int) -> None:
    """Liste so hoch wie ``rows`` Zeilen (mehr per Bildlauf) – der Rest des Panels bleibt sichtbar."""
    frame = 2 * view.frameWidth()
    view.setFixedHeight(rows * row_height + frame + (4 if rows else 0))
