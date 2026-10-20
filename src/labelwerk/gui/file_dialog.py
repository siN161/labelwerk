"""File selection for opening: own Qt dialog with a preview on the right (images, SVG, PDF with
page selection, labels, tables) – or the system's file selection (setting
``system_file_dialog``, from startup: Qt brings it along via the XDG portal itself when the
application starts with the platform theme “xdgdesktopportal” – ``app.qt_arguments``; without this
Qt plugin there is only the own dialog: ``system_dialog_available``).

Previews are foreign input: size and pixels limited, read downscaled, every error →
“No preview” (never a crash). Reading happens in the background (one thread, outdated results
do not count); PDF in the GUI thread – PDFium is not thread-safe and all other PDF calls
run there. ``exec_dialog`` can be replaced in tests (no real modal dialog).
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

PREVIEW_PX = 260                       # edge length of the preview
MAX_PREVIEW_BYTES = 64 * 1024 * 1024   # larger files: only name and size
MAX_PREVIEW_PIXELS = 50_000_000        # images: decode no more pixels (JPEG is downscaled while decoding)
TABLE_ROWS = 8                         # tables: this many rows in the preview
TABLE_CELL = 24                        # characters per cell in the preview
DELAY_MS = 120                         # preview only when the selection stops for a moment
DIALOG_SIZE = (1100, 640)              # at most 90 % of the screen
SIDEBAR_PX = 160                       # places on the left: at least this wide
_RASTER = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
_TABLES = (*series.CSV_SUFFIXES, ".xlsx", ".xlsm")


class Chosen(str):
    """Chosen path; ``page``: PDF page chosen in the dialog (None = not chosen – then the caller
    asks as before)."""
    page: int | None = None

    def __new__(cls, path: str, page: int | None = None):
        chosen = super().__new__(cls, path)
        chosen.page = page
        return chosen


@dataclass
class Preview:
    """Preview of a file: image (or None), text below (name, size, table …),
    page count and shown page (PDF)."""
    image: QImage | None
    text: str
    pages: int = 1
    page: int = 1


def make_preview(path: str | Path, page: int = 1, size: int = PREVIEW_PX,
                 model: str = "QL-600") -> Preview:
    """Preview of a file for the dialog; folder/missing file → empty, error → “No preview”."""
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
    except Exception:                   # foreign file: every error means “no preview”
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
    reader.setAutoTransform(True)                  # EXIF orientation as when inserting
    raw = reader.size()                            # as stored, before rotation
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
    """Size within ``size`` × ``size`` with the same aspect ratio (``grow``: also larger
    than the image); each edge at least 1."""
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

    with PDFIUM_LOCK:                                 # PDFium is not thread-safe
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
    return Preview(_qimage(ImageOps.expand(image.convert("L"), 1, fill=160)), info)   # label edge


def _table(path: Path, info: str) -> Preview:
    table = series.load_table(path, limit=TABLE_ROWS)          # only the beginning (large tables)
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
    """Result of a preview job (generation, preview) – across thread boundaries."""
    done = Signal(int, object)


class _Job(QRunnable):
    def __init__(self, generation: int, path: str, page: int, model: str, emitter: _Done):
        super().__init__()
        self._args = (path, page, PREVIEW_PX, model)
        self._generation = generation
        self._emitter = emitter                   # keeps the sender alive until reported

    def run(self) -> None:
        preview = make_preview(*self._args)       # QImage may go to the background, QPixmap may not
        try:
            self._emitter.done.emit(self._generation, preview)
        except RuntimeError:                      # dialog closed in the meantime
            pass


_pool: QThreadPool | None = None


def _threads() -> QThreadPool:
    """One background thread for all previews (one after another, never in parallel)."""
    global _pool
    if _pool is None:
        _pool = QThreadPool()
        _pool.setMaxThreadCount(1)
    return _pool


def wait_for_previews() -> None:
    """Wait for running previews (dialog closed, tests)."""
    if _pool is not None:
        _pool.waitForDone()


class PreviewPane(QWidget):
    """Preview on the right in the dialog: image, text, ◀ n/N ▶ for PDFs with several pages. Reading
    happens in the background; each ``show_file`` increments the generation, older results expire."""

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
        self.setFixedWidth(PREVIEW_PX + 8)            # same width with and without image
        self.image = QLabel()
        self.image.setFixedSize(PREVIEW_PX, PREVIEW_PX)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setObjectName("filePreview")
        self.image.setFrameShape(QFrame.Shape.Box)    # labels are white: the border shows the area
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
        """Show the preview of a file (new file: first page)."""
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
        elif Path(self.path).suffix.lower() == ".pdf":    # PDFium: only in the GUI thread
            self.show_result(self.generation,
                             make_preview(self.path, self.page, PREVIEW_PX, self._model))
        else:
            _threads().clear()                    # jobs not yet started are outdated
            _threads().start(_Job(self.generation, self.path, self.page, self._model,
                                  self._emitter))

    def show_result(self, generation: int, preview: Preview) -> None:
        """Show the result – only that of the last job."""
        if generation != self.generation:
            return
        self.page, self._count = preview.page, preview.pages
        if preview.image is not None:
            self.image.setPixmap(QPixmap.fromImage(preview.image))
        else:
            self.image.clear()
        self.image.setVisible(preview.image is not None)   # table/text: start at the top
        self.info.setText(preview.text)
        many = self._pages_allowed and preview.image is not None and preview.pages > 1
        self.pages.setVisible(many)
        self.page_label.setText(f"{preview.page}/{preview.pages}")
        self.prev.setEnabled(preview.page > 1)
        self.next.setEnabled(preview.page < preview.pages)


class PreviewFileDialog(QFileDialog):
    """Qt dialog “Open” (not the system's) with a preview of the selected file on the right.
    ``pages``: for PDFs the page can be chosen (``page_for``)."""

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
        # Qt stores the dialog's state for all programs (QtProject.conf): set up columns, sidebar
        # and splitter only for labelwerk, restore when closing
        self._qt_state = self.saveState()
        self._arrange()                         # after Qt's restoration of the last state
        self._pending: str | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DELAY_MS)
        self._timer.timeout.connect(lambda: self.show_preview(self._pending))
        self.currentChanged.connect(self._current_changed)

    def _arrange(self) -> None:
        """Room for the file list: places on the left narrow, column Name stretches, Type is dropped,
        size and date as wide as needed; window at most 90 % of the screen."""
        sidebar = self.findChild(QListView, "sidebar")
        if sidebar is not None:
            sidebar.setMinimumWidth(SIDEBAR_PX)
        self._split()
        tree = self.findChild(QTreeView, "treeView")
        if tree is not None:
            header = tree.header()
            metrics = tree.fontMetrics()
            header.setStretchLastSection(False)
            header.setSectionHidden(2, True)                        # type
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for column, sample in ((1, "9999,99 KiB"), (3, "00.00.0000 00:00")):
                title = str(tree.model().headerData(column, Qt.Orientation.Horizontal) or "")
                width = max(metrics.horizontalAdvance(sample),
                            header.fontMetrics().horizontalAdvance(title) * 1.15)   # header bold
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
        self._split()                           # widths only apply once visible

    def restore_qt_state(self) -> None:
        """State of the Qt dialog as before ``_arrange`` (Qt stores it when destroyed)."""
        self.restoreState(self._qt_state)

    def done(self, result: int) -> None:
        self._timer.stop()
        _threads().clear()                      # only wait for the running job
        wait_for_previews()                     # no result after closing
        self.restore_qt_state()
        super().done(result)

    def _current_changed(self, path: str) -> None:
        self._pending = path
        self._timer.start()                     # arrow keys: first read the settled selection

    def show_preview(self, path: str | None) -> None:
        self.pane.show_file(path or None)

    def page_for(self, path: str) -> int | None:
        """Page chosen in the dialog if ``path`` is the shown PDF with page selection."""
        shown = self.pane.path
        if not self.pane.pages.isHidden() and shown and Path(shown).resolve() == Path(path).resolve():
            return self.pane.page
        return None


def _plugins_path() -> str:
    return QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)


def system_dialog_available() -> bool:
    """Does this Qt installation bring the platform theme “xdgdesktopportal” (the desktop's
    dialog via the XDG portal)? Without it there is only the own dialog."""
    return any((Path(_plugins_path()) / "platformthemes").glob("*xdgdesktopportal*"))


def exec_dialog(dialog: QFileDialog) -> bool:
    """Show the dialog and wait (replaced in tests: no real modal dialog)."""
    return bool(dialog.exec())


def ask_open(parent, title: str, folder: str, filters: str, *, system: bool = False,
             pages: bool = False, model: str = "QL-600") -> Chosen | None:
    """Choose a file to open: own dialog with preview (``pages``: PDF page selectable in the dialog)
    or the system's file selection (``system``; page then not chosen).
    None = cancelled."""
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
        dialog.restore_qt_state()               # even without done() (tests): Qt state unchanged
        dialog.deleteLater()
