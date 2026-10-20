"""Panel “File”: New/Open/Save, favourites (with preview, ⎙ per favourite) and Recently opened.

Display only: buttons trigger the main window's actions, lists report via signal what
was chosen – execution is in ``gui.file_session.FileSession``.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QStyle, QToolButton, QWidget)

from ...document import Document
from ...favorites import Favorite
from ...i18n import N_, _
from ...storage import exists
from . import Panel

PREVIEW = QSize(110, 46)            # preview of a favourite (fitted)
FAVORITE_ROWS = 5                   # this many favourites visible, more by scrolling
RECENT_ROWS = 6
FAVORITES_HINT = N_("No favorites yet – design a label and press “+ CURRENT”.")
BROKEN = N_("unreadable")


class _FavoriteRow(QWidget):
    """Row: preview, name, ⎙ (prints this favourite)."""

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
            self.preview.setText(_(BROKEN))
        self.name = QLabel(_("{name}  ▸ Start").format(name=favorite.name) if start else favorite.name)
        self.name.setTextFormat(Qt.TextFormat.PlainText)    # “<b>” in the name stays text
        self.name.setWordWrap(True)
        self.print = QToolButton()
        self.print.setText("⎙")
        self.print.setToolTip(_("Print “{name}”").format(name=favorite.name))
        self.print.clicked.connect(on_print)
        row.addWidget(self.preview)
        row.addWidget(self.name, 1)
        row.addWidget(self.print)


class FilePanel(Panel):
    favorite_open = Signal(object)        # Favorite → open as a new label
    favorite_print = Signal(object)       # favourite → print
    favorite_rename = Signal(object)
    favorite_remove = Signal(object)
    favorite_start = Signal(object)       # Favorite → “Open at startup” on/off
    favorites_folder = Signal()           # open folder
    favorite_add = Signal()               # "+ CURRENT"
    recent_open = Signal(str)             # path

    def __init__(self, doc: Document):
        super().__init__(doc, _("File"))
        self._favorites: list[Favorite] = []
        self._start: str | None = None
        self._printing = False
        self._recent: list[str] = []
        row = QHBoxLayout()
        self.new = QPushButton(_("NEW"))
        self.open = QPushButton(_("OPEN …"))
        row.addWidget(self.new)
        row.addWidget(self.open)
        self.layout_.addLayout(row)
        self.save = QPushButton(_("SAVE"))
        self.save_as = QPushButton(_("SAVE AS …"))
        for button in (self.save, self.save_as):          # full width: long caption
            self.layout_.addWidget(button)

        self.section(_("Favorites"))
        self.add_favorite = QPushButton(_("+ CURRENT"))
        self.add_favorite.setToolTip(_("Save the current label as a favorite"))
        self.add_favorite.clicked.connect(self.favorite_add)
        self.layout_.addWidget(self.add_favorite)
        self.favorites_hint = QLabel(_(FAVORITES_HINT))
        self.favorites_hint.setObjectName("hint")
        self.favorites_hint.setWordWrap(True)
        self.layout_.addWidget(self.favorites_hint)
        self.favorites = QListWidget()
        self.favorites.setObjectName("favorites")
        self.favorites.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _open_on_click(self.favorites, lambda row: self.open_favorite_at(row))
        self.favorites.customContextMenuRequested.connect(self._favorite_context)
        self.layout_.addWidget(self.favorites)

        self.section(_("Recently opened"))
        self.recent = QListWidget()
        self.recent.setObjectName("recent")
        _open_on_click(self.recent, lambda row: self.open_recent_at(row))
        self.layout_.addWidget(self.recent)
        self.layout_.addStretch()

    def use_actions(self, actions: dict[str, QAction]) -> None:
        """Buttons trigger the file actions (shortcut in the tooltip, also after remapping)."""
        for button, key in ((self.new, "file.new"), (self.open, "file.open"),
                            (self.save, "file.save"), (self.save_as, "file.save_as")):
            action = actions[key]
            button.clicked.connect(lambda _checked=False, a=action: a.trigger())
            button.setToolTip(action.toolTip())
            action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))

    # --- Favourites -------------------------------------------------------
    def set_favorites(self, favorites: list[tuple[Favorite, QPixmap | None]],
                      start: str | None) -> None:
        """Refill the list: (favourite, preview or None = not readable); ``start`` = name
        of the startup favourite."""
        self._favorites = [f for f, __ in favorites]
        self._start = start
        self.favorites.clear()
        for favorite, preview in favorites:
            item = QListWidgetItem()
            item.setToolTip(str(favorite.path))
            item.setSizeHint(QSize(PREVIEW.width() + 120, PREVIEW.height() + 8))
            self.favorites.addItem(item)
            row = _FavoriteRow(favorite, preview, favorite.name == start,
                               lambda _checked=False, f=favorite: self.favorite_print.emit(f))
            row.print.setEnabled(not self._printing)
            self.favorites.setItemWidget(item, row)
        self.favorites_hint.setVisible(not favorites)
        self.favorites.setVisible(bool(favorites))
        _fit_height(self.favorites, min(len(favorites), FAVORITE_ROWS), PREVIEW.height() + 8)

    def set_printing(self, printing: bool) -> None:
        """While printing the ⎙ buttons are locked (like PRINT)."""
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
        """Context menu of a favourite."""
        favorite = self._favorites[row]
        menu = QMenu(self)
        menu.addAction(_("Open as new label"), lambda: self.favorite_open.emit(favorite))
        menu.addAction(_("Print"), lambda: self.favorite_print.emit(favorite))
        menu.addAction(_("Rename …"), lambda: self.favorite_rename.emit(favorite))
        menu.addAction(_("Delete …"), lambda: self.favorite_remove.emit(favorite))
        start = menu.addAction(_("Open at startup"), lambda: self.favorite_start.emit(favorite))
        start.setCheckable(True)
        start.setChecked(favorite.name == self._start)
        menu.addAction(_("Open folder"), lambda: self.favorites_folder.emit())
        return menu

    def _favorite_context(self, pos) -> None:
        item = self.favorites.itemAt(pos)
        if item is not None:
            self.favorite_menu(self.favorites.row(item)).exec(
                self.favorites.viewport().mapToGlobal(pos))

    # --- Recently opened -------------------------------------------------
    def set_recent(self, paths: list[str]) -> None:
        """Recently opened: name, path in the tooltip; if the file is missing, greyed out."""
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
    """Click and activate (Enter, double-click) open the row – once: styles that already
    activate on single click (e.g. KDE) additionally emit ``itemActivated``."""
    def clicked(item) -> None:
        if not view.style().styleHint(QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick,
                                      None, view):
            open_row(view.row(item))

    view.itemClicked.connect(clicked)
    view.itemActivated.connect(lambda item: open_row(view.row(item)))


def _fit_height(view: QListWidget, rows: int, row_height: int) -> None:
    """List as high as ``rows`` rows (more by scrolling) – the rest of the panel stays visible."""
    frame = 2 * view.frameWidth()
    view.setFixedHeight(rows * row_height + frame + (4 if rows else 0))
