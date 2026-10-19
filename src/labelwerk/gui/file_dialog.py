"""Dateiauswahl zum Öffnen: eigener Qt-Dialog mit Vorschau rechts (Bilder, SVG, PDF mit
Seitenwahl, Etiketten, Tabellen) – oder die Dateiauswahl des Systems (Einstellung
``system_file_dialog``, ab dem Start: Qt bringt sie über das XDG-Portal selbst mit, wenn die
Anwendung mit dem Platform-Theme „xdgdesktopportal“ startet – ``app.qt_arguments``; ohne dieses
Qt-Plugin gibt es nur den eigenen Dialog: ``system_dialog_available``).

Vorschauen sind fremde Eingabe: Größe und Pixel begrenzt, verkleinert gelesen, jeder Fehler →
„Keine Vorschau“ (nie ein Absturz). Gelesen wird im Hintergrund (ein Thread, veraltete Ergebnisse
zählen nicht); PDF im GUI-Thread – PDFium ist nicht threadsicher und alle anderen PDF-Aufrufe
laufen dort. ``exec_dialog`` ist in Tests ersetzbar (kein echter modaler Dialog).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QLibraryInfo, QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QImage, QImageIOHandler, QImageReader, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QListView, QPushButton, QSplitter, QTreeView, QVBoxLayout, QWidget)

from .. import series, storage
from ..files import PDFIUM_LOCK
from ..i18n import _, ngettext, number
from ..render import Renderer
from ..storage import SUFFIX

PREVIEW_PX = 260                       # Kantenlänge der Vorschau
MAX_PREVIEW_BYTES = 64 * 1024 * 1024   # größere Dateien: nur Name und Größe
MAX_PREVIEW_PIXELS = 50_000_000        # Bilder: mehr Pixel nicht dekodieren (JPEG verkleinert schon dabei)
TABLE_ROWS = 8                         # Tabellen: so viele Zeilen in der Vorschau
TABLE_CELL = 24                        # Zeichen je Zelle in der Vorschau
DELAY_MS = 120                         # Vorschau erst, wenn die Auswahl kurz stehen bleibt
DIALOG_SIZE = (1100, 640)              # höchstens 90 % des Bildschirms
SIDEBAR_PX = 160                       # Orte links: mindestens so breit
_RASTER = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
_TABLES = (*series.CSV_SUFFIXES, ".xlsx", ".xlsm")


class Chosen(str):
    """Gewählter Pfad; ``page``: im Dialog gewählte PDF-Seite (None = nicht gewählt – dann fragt
    der Aufrufer wie bisher)."""
    page: int | None = None

    def __new__(cls, path: str, page: int | None = None):
        chosen = super().__new__(cls, path)
        chosen.page = page
        return chosen


@dataclass
class Preview:
    """Vorschau einer Datei: Bild (oder None), Text darunter (Name, Größe, Tabelle …),
    Seitenzahl und gezeigte Seite (PDF)."""
    image: QImage | None
    text: str
    pages: int = 1
    page: int = 1


def make_preview(path: str | Path, page: int = 1, size: int = PREVIEW_PX,
                 model: str = "QL-600") -> Preview:
    """Vorschau einer Datei für den Dialog; Ordner/fehlende Datei → leer, Fehler → „Keine Vorschau“."""
    path = Path(path)
    try:
        if not path.is_file():
            return Preview(None, "")
        nbytes = path.stat().st_size
    except OSError:
        return Preview(None, "")
    info = f"{path.name}\n{_size_text(nbytes)}"
    if nbytes > MAX_PREVIEW_BYTES:
        return Preview(None, f"{info}\n{_('No preview')}")
    suffix = path.suffix.lower()
    try:
        if suffix in _RASTER:
            return _raster(path, size, info)
        if suffix == ".svg":
            return _svg(path, size, info)
        if suffix == ".pdf":
            return _pdf(path, page, size, info)
        if suffix == SUFFIX:
            return _label(path, size, info, model)
        if suffix in _TABLES:
            return _table(path, info)
    except Exception:                   # fremde Datei: jeder Fehler heißt „keine Vorschau“
        return Preview(None, f"{info}\n{_('No preview')}")
    return Preview(None, info)


def _size_text(nbytes: int) -> str:
    if nbytes < 1024:
        return ngettext("{count} byte", "{count} bytes", nbytes).format(count=nbytes)
    if nbytes < 1024 * 1024:
        return _("{size} KiB").format(size=number(round(nbytes / 1024, 1)))
    return _("{size} MiB").format(size=number(round(nbytes / 1024 / 1024, 1)))


def _no_preview(info: str) -> Preview:
    return Preview(None, f"{info}\n{_('No preview')}")


def _raster(path: Path, size: int, info: str) -> Preview:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)                  # EXIF-Lage wie beim Einfügen
    raw = reader.size()                            # wie gespeichert, vor der Drehung
    if not raw.isValid() or raw.isEmpty():
        return _no_preview(info)
    if raw.width() * raw.height() > MAX_PREVIEW_PIXELS and bytes(reader.format()) != b"jpeg":
        return _no_preview(f"{info}\n{raw.width()} × {raw.height()} px")
    reader.setScaledSize(_fit(raw, size))
    image = reader.read()
    if image.isNull():
        return _no_preview(info)
    turned = reader.transformation() & QImageIOHandler.Transformation.TransformationRotate90
    full = raw.transposed() if turned else raw
    return Preview(image, f"{info}\n{full.width()} × {full.height()} px")


def _fit(full: QSize, size: int, grow: bool = False) -> QSize:
    """Größe innerhalb ``size`` × ``size`` mit gleichem Seitenverhältnis (``grow``: auch größer
    als das Bild); jede Kante mindestens 1."""
    factor = size / max(full.width(), full.height(), 1)
    if not grow:
        factor = min(1.0, factor)
    return QSize(max(1, round(full.width() * factor)), max(1, round(full.height() * factor)))


def _svg(path: Path, size: int, info: str) -> Preview:
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid() or renderer.defaultSize().isEmpty():
        return _no_preview(info)
    image = QImage(_fit(renderer.defaultSize(), size, grow=True),
                   QImage.Format.Format_ARGB32_Premultiplied)
    if image.isNull():
        return _no_preview(info)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return Preview(image, info)


def _pdf(path: Path, page: int, size: int, info: str) -> Preview:
    import pypdfium2 as pdfium

    with PDFIUM_LOCK:                                 # PDFium ist nicht threadsicher
        pdf = pdfium.PdfDocument(path)
        try:
            pages = len(pdf)
            if pages < 1:
                return _no_preview(info)
            page = min(max(page, 1), pages)
            pdf_page = pdf[page - 1]
            scale = size / max(pdf_page.get_size())
            image = _qimage(pdf_page.render(scale=scale).to_pil())
        finally:
            pdf.close()
    text = _("Page {page} of {count}").format(page=page, count=pages)
    return Preview(image, f"{info}\n{text}", pages, page)


def _label(path: Path, size: int, info: str, model: str) -> Preview:
    image = Renderer().render(storage.load(path), model, placeholders=True).image
    image.thumbnail((size - 2, size - 2))
    return Preview(_qimage(ImageOps.expand(image.convert("L"), 1, fill=160)), info)   # Etikettrand


def _table(path: Path, info: str) -> Preview:
    table = series.load_table(path, limit=TABLE_ROWS)          # nur der Anfang (große Tabellen)
    lines = [" | ".join(_cell(c) for c in table.columns)]
    lines += [" | ".join(_cell(c) for c in row) for row in table.rows]
    rows = len(table.rows)
    count = (ngettext("more than {count} row", "more than {count} rows", rows) if table.more
             else ngettext("{count} row", "{count} rows", rows)).format(count=rows)
    return Preview(None, f"{info} · {count}\n\n" + "\n".join(lines))


def _cell(text: str) -> str:
    return text if len(text) <= TABLE_CELL else text[:TABLE_CELL - 1] + "…"


def _qimage(image: Image.Image) -> QImage:
    rgb = image.convert("RGB")
    return QImage(rgb.tobytes(), rgb.width, rgb.height, 3 * rgb.width,
                  QImage.Format.Format_RGB888).copy()


class _Done(QObject):
    """Ergebnis eines Vorschau-Auftrags (Generation, Preview) – über Threadgrenzen hinweg."""
    done = Signal(int, object)


class _Job(QRunnable):
    def __init__(self, generation: int, path: str, page: int, model: str, emitter: _Done):
        super().__init__()
        self._args = (path, page, PREVIEW_PX, model)
        self._generation = generation
        self._emitter = emitter                   # hält den Sender am Leben, bis gemeldet ist

    def run(self) -> None:
        preview = make_preview(*self._args)       # QImage geht im Hintergrund, QPixmap nicht
        try:
            self._emitter.done.emit(self._generation, preview)
        except RuntimeError:                      # Dialog inzwischen geschlossen
            pass


_pool: QThreadPool | None = None


def _threads() -> QThreadPool:
    """Ein Hintergrund-Thread für alle Vorschauen (nacheinander, nie parallel)."""
    global _pool
    if _pool is None:
        _pool = QThreadPool()
        _pool.setMaxThreadCount(1)
    return _pool


def wait_for_previews() -> None:
    """Laufende Vorschauen abwarten (Dialog geschlossen, Tests)."""
    if _pool is not None:
        _pool.waitForDone()


class PreviewPane(QWidget):
    """Vorschau rechts im Dialog: Bild, Text, bei PDF mit mehreren Seiten ◀ n/N ▶. Gelesen wird
    im Hintergrund; jedes ``show_file`` zählt die Generation hoch, ältere Ergebnisse verfallen."""

    def __init__(self, pages: bool = False, model: str = "QL-600"):
        super().__init__()
        self._pages_allowed = pages
        self._model = model
        self.path: str | None = None
        self.page = 1
        self._count = 1
        self.generation = 0
        self._emitter = _Done()
        self._emitter.done.connect(self.show_result)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        self.setFixedWidth(PREVIEW_PX + 8)            # gleich breit mit und ohne Bild
        self.image = QLabel()
        self.image.setFixedSize(PREVIEW_PX, PREVIEW_PX)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setObjectName("filePreview")
        self.image.setFrameShape(QFrame.Shape.Box)    # Etiketten sind weiß: Rand zeigt die Fläche
        layout.addWidget(self.image)
        self.pages = QWidget()
        row = QHBoxLayout(self.pages)
        row.setContentsMargins(0, 0, 0, 0)
        self.prev = QPushButton("◀")
        self.next = QPushButton("▶")
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for widget in (self.prev, self.page_label, self.next):
            row.addWidget(widget)
        self.prev.clicked.connect(lambda: self._turn(-1))
        self.next.clicked.connect(lambda: self._turn(1))
        self.pages.setToolTip(_("Page of the PDF to insert"))
        self.pages.hide()
        layout.addWidget(self.pages)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setMaximumWidth(PREVIEW_PX)
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.info, 1)

    def show_file(self, path: str | None) -> None:
        """Vorschau einer Datei zeigen (neue Datei: erste Seite)."""
        if path != self.path:
            self.page = 1
        self.path = path
        self._update()

    def _turn(self, step: int) -> None:
        self.page = min(max(self.page + step, 1), self._count)
        self._update()

    def _update(self) -> None:
        self.generation += 1
        if not self.path:
            self.show_result(self.generation, Preview(None, ""))
        elif Path(self.path).suffix.lower() == ".pdf":    # PDFium: nur im GUI-Thread
            self.show_result(self.generation,
                             make_preview(self.path, self.page, PREVIEW_PX, self._model))
        else:
            _threads().clear()                    # noch nicht begonnene Aufträge sind veraltet
            _threads().start(_Job(self.generation, self.path, self.page, self._model,
                                  self._emitter))

    def show_result(self, generation: int, preview: Preview) -> None:
        """Ergebnis zeigen – nur das des letzten Auftrags."""
        if generation != self.generation:
            return
        self.page, self._count = preview.page, preview.pages
        if preview.image is not None:
            self.image.setPixmap(QPixmap.fromImage(preview.image))
        else:
            self.image.clear()
        self.image.setVisible(preview.image is not None)   # Tabelle/Text: oben beginnen
        self.info.setText(preview.text)
        many = self._pages_allowed and preview.image is not None and preview.pages > 1
        self.pages.setVisible(many)
        self.page_label.setText(f"{preview.page}/{preview.pages}")
        self.prev.setEnabled(preview.page > 1)
        self.next.setEnabled(preview.page < preview.pages)


class PreviewFileDialog(QFileDialog):
    """Qt-Dialog „Öffnen“ (nicht der des Systems) mit Vorschau der markierten Datei rechts.
    ``pages``: bei PDF lässt sich die Seite wählen (``page_for``)."""

    def __init__(self, parent, title: str, folder: str, filters: str, pages: bool = False,
                 model: str = "QL-600"):
        super().__init__(parent, title, folder, filters)
        self.setOption(QFileDialog.Option.DontUseNativeDialog)
        self.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        self.pane = PreviewPane(pages, model)
        layout = self.layout()
        if isinstance(layout, QGridLayout):
            layout.addWidget(self.pane, 0, layout.columnCount(), layout.rowCount(), 1)
        # Qt speichert den Stand des Dialogs für alle Programme (QtProject.conf): Spalten, Seitenleiste
        # und Splitter nur für labelwerk einrichten, beim Schließen zurückstellen
        self._qt_state = self.saveState()
        self._arrange()                         # nach Qts Wiederherstellung des letzten Stands
        self._pending: str | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DELAY_MS)
        self._timer.timeout.connect(lambda: self.show_preview(self._pending))
        self.currentChanged.connect(self._current_changed)

    def _arrange(self) -> None:
        """Platz für die Dateiliste: Orte links schmal, Spalte Name dehnt sich, Typ entfällt,
        Größe und Datum so breit wie nötig; Fenster höchstens 90 % des Bildschirms."""
        sidebar = self.findChild(QListView, "sidebar")
        if sidebar is not None:
            sidebar.setMinimumWidth(SIDEBAR_PX)
        self._split()
        tree = self.findChild(QTreeView, "treeView")
        if tree is not None:
            header = tree.header()
            metrics = tree.fontMetrics()
            header.setStretchLastSection(False)
            header.setSectionHidden(2, True)                        # Typ
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for column, sample in ((1, "9999,99 KiB"), (3, "00.00.0000 00:00")):
                title = str(tree.model().headerData(column, Qt.Orientation.Horizontal) or "")
                width = max(metrics.horizontalAdvance(sample),
                            header.fontMetrics().horizontalAdvance(title) * 1.15)   # Kopf fett
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
                header.resizeSection(column, round(width) + 28)
        screen = self.screen().availableGeometry()
        self.resize(min(DIALOG_SIZE[0], int(screen.width() * 0.9)),
                    min(DIALOG_SIZE[1], int(screen.height() * 0.9)))

    def _split(self) -> None:
        splitter = self.findChild(QSplitter, "splitter")
        if splitter is not None:
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setSizes([SIDEBAR_PX + 20, max(600, splitter.width() - SIDEBAR_PX - 20)])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._split()                           # erst sichtbar gelten die Breiten

    def restore_qt_state(self) -> None:
        """Stand des Qt-Dialogs wie vor ``_arrange`` (Qt speichert ihn beim Zerstören)."""
        self.restoreState(self._qt_state)

    def done(self, result: int) -> None:
        self._timer.stop()
        _threads().clear()                      # nur den laufenden Auftrag abwarten
        wait_for_previews()                     # kein Ergebnis mehr nach dem Schließen
        self.restore_qt_state()
        super().done(result)

    def _current_changed(self, path: str) -> None:
        self._pending = path
        self._timer.start()                     # Pfeiltasten: erst die stehende Auswahl lesen

    def show_preview(self, path: str | None) -> None:
        self.pane.show_file(path or None)

    def page_for(self, path: str) -> int | None:
        """Im Dialog gewählte Seite, wenn ``path`` die gezeigte PDF mit Seitenwahl ist."""
        shown = self.pane.path
        if not self.pane.pages.isHidden() and shown and Path(shown).resolve() == Path(path).resolve():
            return self.pane.page
        return None


def _plugins_path() -> str:
    return QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)


def system_dialog_available() -> bool:
    """Bringt diese Qt-Installation das Platform-Theme „xdgdesktopportal“ mit (Dialog des
    Desktops über das XDG-Portal)? Ohne es gibt es nur den eigenen Dialog."""
    return any((Path(_plugins_path()) / "platformthemes").glob("*xdgdesktopportal*"))


def exec_dialog(dialog: QFileDialog) -> bool:
    """Dialog zeigen und warten (in Tests ersetzt: kein echter modaler Dialog)."""
    return bool(dialog.exec())


def ask_open(parent, title: str, folder: str, filters: str, *, system: bool = False,
             pages: bool = False, model: str = "QL-600") -> Chosen | None:
    """Datei zum Öffnen wählen: eigener Dialog mit Vorschau (``pages``: PDF-Seite im Dialog
    wählbar) bzw. die Dateiauswahl des Systems (``system``; Seite dann nicht gewählt).
    None = abgebrochen."""
    if system:
        path, _filter = QFileDialog.getOpenFileName(parent, title, folder, filters)
        return Chosen(path) if path else None
    dialog = PreviewFileDialog(parent, title, folder, filters, pages, model)
    try:
        if not exec_dialog(dialog) or not dialog.selectedFiles():
            return None
        path = dialog.selectedFiles()[0]
        return Chosen(path, dialog.page_for(path) if pages else None)
    finally:
        dialog.restore_qt_state()               # auch ohne done() (Tests): Qt-Stand unverändert
        dialog.deleteLater()
