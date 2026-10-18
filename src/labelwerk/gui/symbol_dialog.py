"""Fenster „Symbol einfügen“ (wie die ClipArt-Auswahl im P-touch Editor).

Nicht modal und bleibt offen: Suche oben (über die ganze Bibliothek), Gruppen links (Zuletzt verwendet, Favoriten,
Eigene, Elektro, Versand, Sicherheit, Allgemein; Untergruppe als Auswahl), Raster rechts.
Einfügen per Doppelklick, Enter (im Raster und im Suchfeld: erster Treffer), Kontextmenü oder
Ziehen aufs Etikett (MIME ``MIME_SYMBOL`` = id); Pfeil runter im Suchfeld führt ins Raster, Esc
schließt. Werkzeugfenster: die Kürzel des Hauptfensters (Strg+Z …) wirken weiter.
Vorschaubilder rastert das Modell erst, wenn sie zu sehen sind – auch bei ca. 5000 Icons
flüssig. Gerechnet (Katalog, Suche) wird im Kern (``clipart``); Einfügen, Zuletzt verwendet
und Favoriten (Einstellungen) führt das Hauptfenster.
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
from .image_import import MIME_SYMBOL
ICON_PX = 48
ICON_CACHE = 3000              # höchstens so viele Vorschauen gemerkt (ca. 30 MB)
SPECIAL = (("zuletzt", "Zuletzt verwendet"), ("favoriten", "Favoriten"))
ALL_SUBGROUPS = "Alle"
EMPTY_OWN = ("Noch keine eigenen Symbole. SVG- oder PNG-Dateien in diesen Ordner legen "
             "(Unterordner werden nicht gelesen):\n{path}")
EMPTY_FAVORITES = "Noch keine Favoriten – Symbol wählen und ★ drücken."
EMPTY_RECENT = "Noch nichts eingefügt."
NO_RESULTS = "Nichts gefunden."
FAVORITE = ("☆ FAVORIT", "★ FAVORIT")          # nicht / schon Favorit
WINDOW_SIZE = (720, 520)


class SymbolModel(QAbstractListModel):
    """Symbole als Liste; Vorschau (48 px) erst bei Bedarf gerastert und gemerkt."""

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
            # doppelt so fein gerastert: scharf auch auf HiDPI-Bildschirmen
            icon = self._icons[symbol.id] = QIcon(preview(symbol, 2 * ICON_PX))
        return icon


def preview(symbol: Symbol, px: int) -> QPixmap:
    """Symbol eingepasst in ``px`` × ``px`` auf Weiß (unlesbar: leeres Feld)."""
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
    """Eigenes Fenster (Werkzeugfenster des Hauptfensters), eine Instanz je Hauptfenster."""

    chosen = Signal(object)             # Symbol einfügen (Doppelklick, Enter, Knopf)
    favorites_changed = Signal(list)    # neue Favoriten (ids)

    def __init__(self, recent: list[str], favorites: list[str], parent=None):
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle("Symbol einfügen")
        self.resize(*WINDOW_SIZE)
        self.recent = list(recent)
        self.favorites = list(favorites)
        outer = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setObjectName("symbolSearch")
        self.search.setPlaceholderText("Suchen … (z. B. Erde, zerbrechlich, Haus)")
        self.search.setClearButtonEnabled(True)
        outer.addWidget(self.search)
        row = QHBoxLayout()
        outer.addLayout(row, 1)
        self.groups = QListWidget()
        self.groups.setObjectName("symbolGroups")
        self.groups.setMaximumWidth(180)
        self._group_keys = [key for key, _ in SPECIAL] + [key for key, _ in clipart.GROUPS]
        for _, name in (*SPECIAL, *clipart.GROUPS):
            self.groups.addItem(name)
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
        self.grid.setLayoutMode(QListView.LayoutMode.Batched)    # große Gruppen schrittweise
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
        self.open_folder = QPushButton("ORDNER ÖFFNEN")
        self.open_folder.setToolTip("Ordner für eigene Symbole öffnen (wird angelegt)")
        self.favorite = QPushButton(FAVORITE[0])
        self.favorite.setObjectName("formatButton")     # RawBlock: gedrückt schwarz
        self.favorite.setCheckable(True)
        self.insert = QPushButton("EINFÜGEN")
        for button in (self.open_folder, self.favorite):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(self.insert)
        right.addLayout(buttons)
        self.info = QLabel()                      # Name · Quelle · Lizenz des gewählten
        self.info.setWordWrap(True)
        right.addWidget(self.info)

        self.search.textChanged.connect(lambda _: self.refresh())
        self.search.returnPressed.connect(self.choose)            # erster Treffer ist gewählt
        self.search.installEventFilter(self)
        self.groups.currentRowChanged.connect(lambda _: self._group_changed())
        self.subgroup.currentIndexChanged.connect(lambda _: self.refresh())
        # nur doppelklicken – „activated“ käme nach dem Doppelklick noch einmal (bzw. bei
        # Einfachklick-Einstellung schon beim Auswählen); Enter: eventFilter
        self.grid.doubleClicked.connect(lambda _: self.choose())
        self.grid.installEventFilter(self)
        self.grid.customContextMenuRequested.connect(self._context_menu)
        self.grid.selectionModel().currentChanged.connect(lambda *_: self._current_changed())
        self.insert.clicked.connect(self.choose)
        self.favorite.clicked.connect(self._toggle_favorite)
        self.open_folder.clicked.connect(self.show_own_folder)
        start = "zuletzt" if clipart.resolve(self.recent) else "elektro"
        self.groups.setCurrentRow(self._group_keys.index(start))

    # --- Inhalt -----------------------------------------------------------
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
        if event.key() == Qt.Key.Key_Escape:       # Suchfeld und Raster reichen Esc weiter
            self.close()
        else:
            super().keyPressEvent(event)

    def _group_changed(self) -> None:
        if self.search.text():
            self.search.blockSignals(True)       # Gruppe gewählt: die Suche endet
            self.search.clear()
            self.search.blockSignals(False)
        group = self.group()
        names = [] if group in ("zuletzt", "favoriten") else sorted(
            {s.subgroup for s in clipart.symbols(group)})
        self.subgroup.blockSignals(True)
        self.subgroup.clear()
        self.subgroup.addItems([ALL_SUBGROUPS, *names] if len(names) > 1 else [])
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
        """Raster neu füllen: mit Suchtext die Treffer der ganzen Bibliothek, sonst Gruppe und
        Untergruppe."""
        text = self.search.text().strip()
        if text:
            pool = clipart.search(text)
        else:
            pool = self._pool()
            sub = self.subgroup.currentText()
            if sub and sub != ALL_SUBGROUPS:
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
            return NO_RESULTS
        return {"eigene": EMPTY_OWN.format(path=clipart.own_dir()),
                "favoriten": EMPTY_FAVORITES, "zuletzt": EMPTY_RECENT}.get(self.group(), "")

    def current(self) -> Symbol | None:
        index = self.grid.currentIndex()
        return self.model.symbols[index.row()] if index.isValid() else None

    def _current_changed(self) -> None:
        symbol = self.current()
        self.insert.setEnabled(symbol is not None)
        self.favorite.setEnabled(symbol is not None)
        favorite = symbol is not None and symbol.id in self.favorites
        self.favorite.setChecked(favorite)
        self.favorite.setText(FAVORITE[favorite])
        self.info.setText("" if symbol is None else
                          f"{symbol.name} · {symbol.source}"
                          + (f" · {symbol.license}" if symbol.license else ""))

    # --- Aktionen ---------------------------------------------------------
    def choose(self) -> None:
        if (symbol := self.current()) is not None:
            self.chosen.emit(symbol)

    def set_recent(self, recent: list[str]) -> None:
        """Nach dem Einfügen: neue Liste; die Gruppe „Zuletzt verwendet“ folgt."""
        self.recent = list(recent)
        if self.group() == "zuletzt":
            self.refresh()

    def menu_for(self, index: QModelIndex) -> QMenu:
        """Kontextmenü eines Symbols: Einfügen, Zu Favoriten / Aus Favoriten entfernen."""
        self.grid.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction("Einfügen", self.choose)
        favorite = self.current() is not None and self.current().id in self.favorites
        menu.addAction("Aus Favoriten entfernen" if favorite else "Zu Favoriten",
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
        """Ordner für eigene Symbole anlegen und im Dateimanager öffnen."""
        folder = clipart.own_dir()
        folder.mkdir(parents=True, exist_ok=True)
        self.open_url(QUrl.fromLocalFile(str(folder)))

    def open_url(self, url: QUrl) -> None:
        """Im Dateimanager öffnen (in Tests ersetzbar)."""
        QDesktopServices.openUrl(url)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.group() == "eigene":
            self.refresh()                     # neu abgelegte Dateien zeigen
        self.search.setFocus()
