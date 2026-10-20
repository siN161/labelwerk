"""“Insert symbol” window (like the clip-art picker in the P-touch Editor).

Non-modal and stays open: search on top (across the whole library), groups on the left (Recently used,
Favorites, My symbols, Electrical, Shipping, Safety, General; subgroup as a choice), grid on the right.
Insert by double click, Enter (in the grid and in the search field: first hit), context menu or
dragging onto the label (MIME ``MIME_SYMBOL`` = id); arrow down in the search field moves into the grid, Esc
closes. Tool window: the shortcuts of the main window (Ctrl+Z …) keep working.
The model only rasterises preview images when they become visible – smooth even with about 5000 icons.
Computing (catalogue, search) is done in the core (``clipart``); inserting, recently used
and favourites (settings) are handled by the main window.
"""
from __future__ import annotations

from PySide6.QtCore import (QAbstractListModel, QByteArray, QEvent, QMimeData, QModelIndex, QSize,
                            Qt, QUrl, Signal)
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit,
                               QListView, QListWidget, QMenu, QPushButton, QVBoxLayout, QWidget)

from .. import clipart
from ..clipart import Symbol
from ..i18n import N_, _
from .image_import import MIME_SYMBOL
ICON_PX = 48
ICON_CACHE = 800               # at most this many previews remembered (96 × 96 × 4 bytes each, about 30 MB)
SPECIAL = (("zuletzt", N_("Recently used")), ("favoriten", N_("Favorites")))
ALL_SUBGROUPS = N_("All")
EMPTY_OWN = N_("No own symbols yet. Put SVG or PNG files into this folder "
               "(subfolders are not read):\n{path}")
EMPTY_FAVORITES = N_("No favorites yet – choose a symbol and press ★.")
EMPTY_RECENT = N_("Nothing inserted yet.")
NO_RESULTS = N_("Nothing found.")
FAVORITE = (N_("☆ FAVORITE"), N_("★ FAVORITE"))          # not / already a favourite
WINDOW_SIZE = (720, 520)


class SymbolModel(QAbstractListModel):
    """Symbols as a list; preview (48 px) rasterised and remembered only on demand."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbols: list[Symbol] = []
        self._icons: dict[str, QIcon] = {}

    def set_symbols(self, symbols: list[Symbol]) -> None:
        self.beginResetModel()
        self.symbols = list(symbols)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.symbols)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        symbol = self.symbols[index.row()]
        if role == Qt.ItemDataRole.DecorationRole:
            return self.icon(symbol)
        if role == Qt.ItemDataRole.ToolTipRole:
            source = f"{symbol.source} · {symbol.license}" if symbol.license else symbol.source
            return f"{symbol.name}\n{source}"
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return symbol.name
        if role == Qt.ItemDataRole.UserRole:
            return symbol
        return None

    def flags(self, index: QModelIndex):
        base = super().flags(index)
        return base | Qt.ItemFlag.ItemIsDragEnabled if index.isValid() else base

    def mimeTypes(self) -> list[str]:
        return [MIME_SYMBOL]

    def mimeData(self, indexes) -> QMimeData:
        mime = QMimeData()
        if indexes:
            mime.setData(MIME_SYMBOL, QByteArray(self.symbols[indexes[0].row()].id.encode()))
        return mime

    def icon(self, symbol: Symbol) -> QIcon:
        icon = self._icons.get(symbol.id)
        if icon is None:
            if len(self._icons) >= ICON_CACHE:
                self._icons.clear()
            # rasterised twice as fine: sharp on HiDPI screens as well
            icon = self._icons[symbol.id] = QIcon(preview(symbol, 2 * ICON_PX))
        return icon


def preview(symbol: Symbol, px: int) -> QPixmap:
    """Symbol fitted into ``px`` × ``px`` on white (unreadable: empty field)."""
    image = QImage(px, px, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    try:
        data = clipart.data(symbol)
    except OSError:
        return QPixmap.fromImage(image)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if clipart.is_vector(symbol):
        renderer = QSvgRenderer(QByteArray(data))
        renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        if renderer.isValid():
            renderer.render(painter)
    else:
        picture = QImage.fromData(data)
        if not picture.isNull():
            scaled = picture.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
            painter.drawImage((px - scaled.width()) // 2, (px - scaled.height()) // 2, scaled)
    painter.end()
    return QPixmap.fromImage(image)


class SymbolDialog(QWidget):
    """Own window (tool window of the main window), one instance per main window."""

    chosen = Signal(object)             # insert symbol (double click, Enter, button)
    favorites_changed = Signal(list)    # new favourites (ids)

    def __init__(self, recent: list[str], favorites: list[str], parent=None):
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle(_("Insert symbol"))
        self.resize(*WINDOW_SIZE)
        self.recent = list(recent)
        self.favorites = list(favorites)
        outer = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setObjectName("symbolSearch")
        self.search.setPlaceholderText(_("Search … (e.g. earth, fragile, house)"))
        self.search.setClearButtonEnabled(True)
        outer.addWidget(self.search)
        row = QHBoxLayout()
        outer.addLayout(row, 1)
        self.groups = QListWidget()
        self.groups.setObjectName("symbolGroups")
        self.groups.setMaximumWidth(180)
        self._group_keys = [key for key, __ in SPECIAL] + [key for key, __ in clipart.GROUPS]
        for __, name in (*SPECIAL, *clipart.GROUPS):
            self.groups.addItem(_(name))
        row.addWidget(self.groups)
        right = QVBoxLayout()
        row.addLayout(right, 1)
        self.subgroup = QComboBox()
        right.addWidget(self.subgroup)
        self.model = SymbolModel(self)
        self.grid = QListView()
        self.grid.setObjectName("symbolGrid")
        self.grid.setModel(self.model)
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setIconSize(QSize(ICON_PX, ICON_PX))
        self.grid.setGridSize(QSize(ICON_PX + 24, ICON_PX + 24))
        self.grid.setUniformItemSizes(True)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setLayoutMode(QListView.LayoutMode.Batched)    # large groups step by step
        self.grid.setBatchSize(200)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.setDragEnabled(True)
        self.grid.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        right.addWidget(self.grid, 1)
        self.empty = QLabel()
        self.empty.setObjectName("hint")
        self.empty.setWordWrap(True)
        self.empty.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right.addWidget(self.empty)
        buttons = QHBoxLayout()
        self.open_folder = QPushButton(_("OPEN FOLDER"))
        self.open_folder.setToolTip(_("Open the folder for your own symbols (created if needed)"))
        self.favorite = QPushButton(_(FAVORITE[0]))
        self.favorite.setObjectName("formatButton")     # RawBlock: pressed is black
        self.favorite.setCheckable(True)
        self.insert = QPushButton(_("INSERT"))
        for button in (self.open_folder, self.favorite):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(self.insert)
        right.addLayout(buttons)
        self.info = QLabel()                      # name · source · licence of the selected one
        self.info.setWordWrap(True)
        right.addWidget(self.info)

        self.search.textChanged.connect(lambda _text: self.refresh())
        self.search.returnPressed.connect(self.choose)            # the first hit is selected
        self.search.installEventFilter(self)
        self.groups.currentRowChanged.connect(lambda _row: self._group_changed())
        self.subgroup.currentIndexChanged.connect(lambda _index: self.refresh())
        # only double-click – "activated" would fire once more after the double click (or, with the
        # single-click setting, already on selecting); Enter: eventFilter
        self.grid.doubleClicked.connect(lambda _index: self.choose())
        self.grid.installEventFilter(self)
        self.grid.customContextMenuRequested.connect(self._context_menu)
        self.grid.selectionModel().currentChanged.connect(lambda *_args: self._current_changed())
        self.insert.clicked.connect(self.choose)
        self.favorite.clicked.connect(self._toggle_favorite)
        self.open_folder.clicked.connect(self.show_own_folder)
        start = "zuletzt" if clipart.resolve(self.recent) else "elektro"
        self.groups.setCurrentRow(self._group_keys.index(start))

    # --- Content -----------------------------------------------------------
    def group(self) -> str:
        return self._group_keys[max(0, self.groups.currentRow())]

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            if watched is self.grid and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.choose()
                return True
            if watched is self.search and event.key() == Qt.Key.Key_Down:
                self.grid.setFocus()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:       # search field and grid pass Esc on
            self.close()
        else:
            super().keyPressEvent(event)

    def _group_changed(self) -> None:
        if self.search.text():
            self.search.blockSignals(True)       # group chosen: the search ends
            self.search.clear()
            self.search.blockSignals(False)
        group = self.group()
        names = [] if group in ("zuletzt", "favoriten") else sorted(
            {s.subgroup for s in clipart.symbols(group)})
        self.subgroup.blockSignals(True)
        self.subgroup.clear()
        self.subgroup.addItems([_(ALL_SUBGROUPS), *names] if len(names) > 1 else [])
        self.subgroup.setVisible(len(names) > 1)
        self.subgroup.blockSignals(False)
        self.open_folder.setVisible(group == "eigene")
        self.refresh()

    def _pool(self) -> list[Symbol]:
        group = self.group()
        if group == "zuletzt":
            return clipart.resolve(self.recent)
        if group == "favoriten":
            return clipart.resolve(self.favorites)
        return clipart.symbols(group)

    def refresh(self) -> None:
        """Refill the grid: with search text the hits of the whole library, otherwise group and
        subgroup."""
        text = self.search.text().strip()
        if text:
            pool = clipart.search(text)
        else:
            pool = self._pool()
            sub = self.subgroup.currentText()
            if self.subgroup.currentIndex() > 0:             # 0 = all
                pool = [s for s in pool if s.subgroup == sub]
        self.subgroup.setEnabled(not text)
        self.model.set_symbols(pool)
        if pool:
            self.grid.setCurrentIndex(self.model.index(0))
        self.empty.setText("" if pool else self._empty_text(bool(text)))
        self.empty.setVisible(not pool)
        self._current_changed()

    def _empty_text(self, searching: bool) -> str:
        if searching:
            return _(NO_RESULTS)
        if self.group() == "eigene":
            return _(EMPTY_OWN).format(path=clipart.own_dir())
        text = {"favoriten": EMPTY_FAVORITES, "zuletzt": EMPTY_RECENT}.get(self.group())
        return _(text) if text else ""

    def current(self) -> Symbol | None:
        index = self.grid.currentIndex()
        return self.model.symbols[index.row()] if index.isValid() else None

    def _current_changed(self) -> None:
        symbol = self.current()
        self.insert.setEnabled(symbol is not None)
        self.favorite.setEnabled(symbol is not None)
        favorite = symbol is not None and symbol.id in self.favorites
        self.favorite.setChecked(favorite)
        self.favorite.setText(_(FAVORITE[favorite]))
        self.info.setText("" if symbol is None else
                          f"{symbol.name} · {symbol.source}"
                          + (f" · {symbol.license}" if symbol.license else ""))

    # --- Actions -----------------------------------------------------------
    def choose(self) -> None:
        if (symbol := self.current()) is not None:
            self.chosen.emit(symbol)

    def set_recent(self, recent: list[str]) -> None:
        """After inserting: new list; the group "Recently used" follows."""
        self.recent = list(recent)
        if self.group() == "zuletzt":
            self.refresh()

    def menu_for(self, index: QModelIndex) -> QMenu:
        """Context menu of a symbol: Insert, Add to favourites / Remove from favourites."""
        self.grid.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction(_("Insert"), self.choose)
        favorite = self.current() is not None and self.current().id in self.favorites
        menu.addAction(_("Remove from favorites") if favorite else _("Add to favorites"),
                       self._toggle_favorite)
        return menu

    def _context_menu(self, pos) -> None:
        index = self.grid.indexAt(pos)
        if index.isValid():
            self.menu_for(index).exec(self.grid.viewport().mapToGlobal(pos))

    def _toggle_favorite(self) -> None:
        symbol = self.current()
        if symbol is None:
            return
        if symbol.id in self.favorites:
            self.favorites.remove(symbol.id)
        else:
            self.favorites.append(symbol.id)
        self.favorites_changed.emit(list(self.favorites))
        if self.group() == "favoriten":
            self.refresh()
        else:
            self._current_changed()

    def show_own_folder(self) -> None:
        """Create the folder for own symbols and open it in the file manager."""
        folder = clipart.own_dir()
        folder.mkdir(parents=True, exist_ok=True)
        self.open_url(QUrl.fromLocalFile(str(folder)))

    def open_url(self, url: QUrl) -> None:
        """Open in the file manager (replaceable in tests)."""
        QDesktopServices.openUrl(url)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.group() == "eigene":
            self.refresh()                     # show newly added files
        self.search.setFocus()
