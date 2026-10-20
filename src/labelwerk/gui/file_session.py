"""File session of the main window: New/Open/Save, unsaved changes, favourites and recently
opened files (FILE tab).

The computing happens in the core (``storage``, ``favorites``); this module holds the dialogs,
confirmation prompts and the replacing of the document. The document object stays the same
(panels hold on to it) – it is set to the new state in place, and the undo history starts
afresh. All dialogs are ``ask_*`` methods and can be replaced in tests.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from .. import favorites, storage
from ..desktop import APP_NAME
from ..document import Document, TextObject
from ..favorites import Favorite
from ..i18n import N_, _
from ..labels import labels_for_model
from ..render import Renderer
from ..settings import new_document
from ..storage import SUFFIX, StorageError, exists, os_reason
from . import file_dialog
from .history import restore
from .panels.file import PREVIEW

UNTITLED = N_("Untitled")                     # English, _(UNTITLED) is displayed
MODIFIED = "• "
NAME_LENGTH = 40               # suggested favourite name: at most this long
PREVIEW_ERRORS = Exception     # preview of a favourite: any error → “not readable”


def answer_for(button: int) -> str:
    """Button of the “Save changes?” prompt → "save" | "discard" | "cancel"."""
    return {QMessageBox.StandardButton.Save.value: "save",
            QMessageBox.StandardButton.Discard.value: "discard"}.get(button, "cancel")


class FileSession(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.path: Path | None = None               # saved file; None = unnamed
        self.origin = "new"                         # "new" | "file" | "favorite" | "parcel" (origin)
        self._template: str | None = None           # name of the favourite while unnamed
        self._saved = copy.deepcopy(window.doc)     # state when opened/saved
        self._dir = ""                              # folder of the last open/save
        self._previews: dict[tuple[str, float], QPixmap | None] = {}
        panel = window.panel("file")
        panel.favorite_open.connect(self.open_favorite)
        panel.favorite_print.connect(self.print_favorite)
        panel.favorite_rename.connect(self.rename_favorite)
        panel.favorite_remove.connect(self.remove_favorite)
        panel.favorite_start.connect(self.toggle_start_favorite)
        panel.favorites_folder.connect(self.open_favorites_folder)
        panel.favorite_add.connect(self.add_favorite)
        panel.recent_open.connect(self.open_recent)
        self.refresh_lists()

    # --- Dialogs (replaceable in tests) -------------------------------------
    def ask_save_file(self, suggested: str) -> str | None:
        """The dialog adds the extension itself – so it asks about the full name before replacing."""
        dialog = QFileDialog(self.window, _("Save label"), suggested, _file_filter())
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix(SUFFIX[1:])
        # own path: Qt's dialog (asks before replacing itself); with the system file chooser that of
        # the desktop – save_as then asks itself
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, not self.window.system_dialog)
        try:
            return dialog.selectedFiles()[0] if dialog.exec() and dialog.selectedFiles() else None
        finally:
            dialog.deleteLater()

    def _ask_yes_no(self, title: str, text: str) -> bool:
        """Yes/No question (default: No); the text is plain text, even with “<b>” in the name."""
        box = QMessageBox(QMessageBox.Icon.Question, title, text,
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                          self.window)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes.value

    def ask_replace_file(self, path: Path) -> bool:
        return self._ask_yes_no(_("Replace file"),
                                _("“{name}” already exists. Replace it?").format(name=path.name))

    def ask_print_other_roll(self, label_id: str, loaded: str) -> bool:
        return self._ask_yes_no(
            _("Different roll"),
            _("{loaded} is loaded, the favorite is for {label}. Print anyway?").format(
                loaded=loaded, label=label_id))

    def ask_open_file(self) -> str | None:
        return file_dialog.ask_open(self.window, _("Open label"), self._dir, _file_filter(),
                                    system=self.window.system_dialog,
                                    model=self.window.model)

    def ask_save_changes(self) -> str:
        """"save" | "discard" | "cancel"."""
        box = QMessageBox(QMessageBox.Icon.Question, _("Unsaved changes"),
                          _("“{name}” has been changed. Save the changes?").format(
                              name=self.name()),
                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                          | QMessageBox.StandardButton.Cancel, self.window)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return answer_for(box.exec())

    def ask_favorite_name(self, suggested: str) -> str | None:
        name, ok = QInputDialog.getText(self.window, _("Favorite"), _("Name of the favorite:"),
                                        text=suggested)
        return name if ok else None

    def ask_overwrite(self, name: str) -> bool:
        return self._ask_yes_no(_("Replace favorite"),
                                _("Favorite “{name}” already exists. Replace it?").format(name=name))

    def ask_remove(self, name: str) -> bool:
        return self._ask_yes_no(_("Delete favorite"),
                                _("Delete favorite “{name}”?").format(name=name))

    def open_url(self, url: QUrl) -> None:
        QDesktopServices.openUrl(url)

    # --- State ----------------------------------------------------------
    def name(self) -> str:
        return self.path.stem if self.path is not None else _(UNTITLED)

    def modified(self) -> bool:
        """Different from when opened/saved? Empty text frames do not count: a freshly created one
        is dropped anyway when edit mode ends (like ``MainWindow._drop_empty_frames``)."""
        return _without_empty_frames(self.window.doc) != _without_empty_frames(self._saved)

    def may_follow_roll(self) -> bool:
        """May “Check media” switch the label? Only for a new label – an opened file or a
        favourite belongs to its roll (the panel shows “does not fit”)."""
        return self.origin == "new"      # saving turns "new" into "file"

    def mark_unchanged(self) -> None:
        """The current state counts as the baseline (e.g. roll for an untouched label)."""
        self._saved = copy.deepcopy(self.window.doc)
        self.update_title()

    def update_title(self) -> None:
        mark = MODIFIED if self.modified() else ""
        self.window.setWindowTitle(f"{mark}{self.name()} – {APP_NAME}")

    def maybe_save(self) -> bool:
        """Before New/Open/Close: ask if there are changes; False = cancel (edit mode then
        continues). The document is up to date even while typing."""
        self.window.accept_pending_input()
        if not self.modified():
            return True
        answer = self.ask_save_changes()
        if answer == "save":
            return self.save()
        return answer == "discard"

    def _fits_printer(self, doc: Document, name: str) -> bool:
        """The label must fit the printer (otherwise the PAPER tab would offer no choice for it)."""
        if doc.label_id in {label.id for label in labels_for_model(self.window.model)}:
            return True
        self.window._set_result(_("{name}: label “{label}” does not fit the {model}").format(
            name=name, label=doc.label_id, model=self.window.model), "error")
        return False

    def _replace(self, doc: Document, path: Path | None, origin: str = "new",
                 template: str | None = None) -> None:
        """Replace the document in place, new history, nothing selected."""
        window = self.window
        window.finish_editing()
        window.canvas.set_selection([])
        window._structure_changing()    # render error: do not leave images of the old label
        restore(window.doc, doc)
        window.history.reset(window.doc)
        for key, panel in window._panel_by_key.items():
            if key != "series":
                panel.refresh()
        window.panel("series").reload()     # read the table afresh (once), all rows selected
        window.render_now()
        self.path = path
        self.origin = "file" if path is not None else origin
        self._template = template
        self._saved = copy.deepcopy(window.doc)
        self.update_title()
        window._update_edit_actions()

    # --- New, Open, Save -------------------------------------------
    def new(self) -> None:
        """Empty label per the settings – on the inserted roll, if known."""
        if self.maybe_save():
            doc = new_document(self.window.settings)
            loaded = self.window.panel("paper").media_label
            if loaded is not None:
                doc.label_id = loaded
            wanted = doc.label_id
            doc.label_id = self.fitting_label(wanted)
            self._replace(doc, None)
            if doc.label_id != wanted:
                self.window._set_result(
                    _("Label “{label}” does not fit the {model} – using {new}").format(
                        label=wanted, model=self.window.model, new=doc.label_id), "warn")

    def open_document(self, doc: Document) -> bool:
        """Open a finished label (e.g. conversion of a parcel label) as a new, unsaved one –
        prompt on changes as with New; does not follow the roll; counts as modified (prompt on
        close/New). False = cancelled."""
        if not self.maybe_save():
            return False
        self._replace(doc, None, origin="parcel")
        self._saved = Document(doc.label_id)      # saved nowhere: counts as modified
        self.update_title()
        return True

    def fitting_label(self, label_id: str) -> str:
        """``label_id`` if it fits the printer, else the inserted roll, else 62 mm continuous
        or the first label of the model."""
        fitting = [label.id for label in labels_for_model(self.window.model)]
        for candidate in (label_id, self.window.panel("paper").media_label, "62"):
            if candidate in fitting:
                return candidate
        return fitting[0]

    def open(self, path: str | None = None, ask: bool = True) -> bool:
        """Open a file (without ``path``: dialog); error → status bar, label stays."""
        if ask and not self.maybe_save():
            return False
        path = path or self.ask_open_file()
        if not path:
            return False
        path = Path(path).resolve()          # same file = same entry in “Recently opened”
        try:
            doc = storage.load(path)
        except StorageError as e:
            self.window._set_result(str(e), "error")
            return False
        if not self._fits_printer(doc, path.name):
            return False
        self._replace(doc, path)
        self._dir = str(path.parent)
        self._remember(path)
        error = self.window._render_error     # render_now in the replacement has already reported it
        series_panel = self.window.panel("series")
        if error is None and doc.series is not None and series_panel.error:
            error = _("Series: {error}").format(error=series_panel.error)   # e.g. table missing
        if error is None:
            self.window._set_result(_("Opened: {name}").format(name=path.name), "ok")
        else:
            self.window._set_result(_("Opened: {name} – {error}").format(name=path.name,
                                                                         error=error), "error")
        return True

    def save(self) -> bool:
        self.window.accept_pending_input()          # a number just typed belongs to it
        if self.path is None:
            return self.save_as()
        return self._write(self.path)

    def save_as(self) -> bool:
        self.window.accept_pending_input()
        suggested = str(self.path) if self.path is not None else str(
            Path(self._dir or Path.home()) / f"{self.suggested_name() or _(UNTITLED)}{SUFFIX}")
        path = self.ask_save_file(suggested)
        if not path:
            return False
        path = Path(path)
        if path.suffix.lower() != SUFFIX:
            path = path.with_name(path.name + SUFFIX)
            if path.exists() and not self.ask_replace_file(path):   # the dialog saw the name without
                return False
        elif self.window.system_dialog and path.exists() and not self.ask_replace_file(path):
            return False                    # desktop dialogs do not always ask themselves
        return self._write(path)

    def _write(self, path: Path) -> bool:
        try:
            storage.save(self.window.doc, path)
        except OSError as e:
            self.window._set_result(str(e), "error")
            return False
        self.path = path.resolve()
        self.origin = "file"            # saved: belongs to its roll, no longer follows it
        self._dir = str(path.parent)
        self._saved = copy.deepcopy(self.window.doc)
        self.update_title()
        self._remember(self.path)
        self.window._set_result(_("Saved: {name}").format(name=path.name), "ok")
        return True

    def _remember(self, path: Path) -> None:
        settings = self.window.settings
        settings.recent_files = storage.add_recent_file(settings.recent_files, str(path))
        self.window._save_settings("recent_files")
        self.refresh_lists()

    def open_recent(self, path: str) -> None:
        if not exists(path):
            settings = self.window.settings
            settings.recent_files = [p for p in settings.recent_files if p != path]
            self.window._save_settings("recent_files")
            self.refresh_lists()
            self.window._set_result(
                _("File not found: {path} – removed from the list").format(path=path), "error")
            return
        self.open(path)

    # --- Favourites --------------------------------------------------------
    def suggested_name(self) -> str:
        """Suggestion for a name: file name or favourite, else the first line of text (without
        path characters)."""
        if self.path is not None:
            return self.path.stem
        if self._template is not None:
            return self._template
        for obj in self.window.doc.objects:
            if isinstance(obj, TextObject) and obj.text.strip():
                line = obj.text.strip().split("\n")[0][:NAME_LENGTH].strip()
                return line.replace("/", "-").replace("\\", "-")
        return ""

    def add_favorite(self) -> None:
        self.window.finish_editing()
        name = self.ask_favorite_name(self.suggested_name())
        if name is None:
            return
        try:
            try:
                favorite = favorites.add(self.window.doc, name)
            except FileExistsError:
                if not self.ask_overwrite(name.strip()):
                    return
                favorite = favorites.add(self.window.doc, name, overwrite=True)
        except (ValueError, OSError) as e:
            self.window._set_result(str(e), "error")
            return
        self.refresh_lists()
        self.window._set_result(_("Favorite “{name}” saved").format(name=favorite.name), "ok")

    def _load_favorite(self, favorite: Favorite) -> Document | None:
        try:
            return storage.load(favorite.path)
        except StorageError as e:
            self.window._set_result(str(e), "error")
            return None

    def open_favorite(self, favorite: Favorite) -> bool:
        """Open as a new, unnamed label (template) – the original stays unchanged.
        Load and check first, then ask about changes."""
        doc = self._load_favorite(favorite)
        if doc is None or not self._fits_printer(doc, favorite.name) or not self.maybe_save():
            return False
        self._replace(doc, None, origin="favorite", template=favorite.name)
        return True

    def print_favorite(self, favorite: Favorite) -> None:
        """Print directly: the label must fit the printer; if another roll is known to be inserted,
        ask first (otherwise the printer would only report “Replace media”)."""
        doc = self._load_favorite(favorite)
        if doc is None or not self._fits_printer(doc, favorite.name):
            return
        loaded = self.window.panel("paper").media_label
        if loaded is not None and loaded != doc.label_id and not self.ask_print_other_roll(
                doc.label_id, loaded):
            return
        self.window.print_document(doc)

    def rename_favorite(self, favorite: Favorite) -> None:
        name = self.ask_favorite_name(favorite.name)
        if name is None or name.strip() == favorite.name:
            return
        try:
            renamed = favorites.rename(favorite, name)
        except (ValueError, OSError) as e:
            self.window._set_result(str(e), "error")
            return
        if self.window.settings.start_favorite == favorite.name:
            self.window.settings.start_favorite = renamed.name
            self.window._save_settings("start_favorite")
        self.refresh_lists()

    def remove_favorite(self, favorite: Favorite) -> None:
        if not self.ask_remove(favorite.name):
            return
        try:
            favorites.remove(favorite)
        except OSError as e:
            self.window._set_result(str(e), "error")
            return
        if self.window.settings.start_favorite == favorite.name:
            self.window.settings.start_favorite = None
            self.window._save_settings("start_favorite")
        self.refresh_lists()

    def toggle_start_favorite(self, favorite: Favorite) -> None:
        settings = self.window.settings
        settings.start_favorite = None if settings.start_favorite == favorite.name else favorite.name
        self.window._save_settings("start_favorite")
        self.refresh_lists()

    def open_favorites_folder(self) -> None:
        folder = favorites.favorites_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.window._set_result(_("Favorites folder not created ({reason})").format(
                reason=os_reason(e)), "error")
            return
        self.open_url(QUrl.fromLocalFile(str(folder)))

    # --- Lists in the panel --------------------------------------------------
    def refresh_lists(self) -> None:
        panel = self.window.panel("file")
        current = favorites.favorites()
        panel.set_favorites([(f, self._preview(f)) for f in current],
                            self.window.settings.start_favorite)
        panel.set_recent(self.window.settings.recent_files)
        paths = {str(f.path) for f in current}       # forget previews of old states
        self._previews = {k: v for k, v in self._previews.items() if k[0] in paths}

    def _preview(self, favorite: Favorite) -> QPixmap | None:
        """Image of the favourite, fitted (cached per file and modification time); a barcode with
        a series placeholder appears as a placeholder."""
        try:
            key = (str(favorite.path), favorite.path.stat().st_mtime)
        except OSError:
            return None
        if key not in self._previews:
            try:
                image = Renderer().render(storage.load(favorite.path), self.window.model,
                                          placeholders=True).image
            except PREVIEW_ERRORS:  # a broken preview must not hold up the window
                self._previews[key] = None
            else:
                self._previews[key] = _pixmap(image).scaled(
                    PREVIEW, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
        return self._previews[key]


def _file_filter() -> str:
    """File filters of the dialogs (translated when displayed)."""
    return _("labelwerk labels (*{suffix})").format(suffix=SUFFIX)


def _without_empty_frames(doc: Document) -> Document:
    """Document without empty, freely placed text frames (shallow copy, for comparison only)."""

    return replace(doc, objects=[o for o in doc.objects
                                 if not (isinstance(o, TextObject) and o.positioned
                                         and o.is_empty())])


def _pixmap(image: Image.Image) -> QPixmap:
    gray = image.convert("L")
    qimage = QImage(gray.tobytes(), gray.width, gray.height, gray.width,
                    QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(qimage.copy())
