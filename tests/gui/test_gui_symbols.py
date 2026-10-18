"""Symbole/ClipArt (Etappe 3d-2c): Fenster „Symbol einfügen“, Einfügen, Zuletzt verwendet,
Favoriten, eigener Ordner, Ziehen aufs Etikett."""
import zipfile

import pytest
from PIL import Image
from PySide6.QtCore import QByteArray, QMimeData, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from labelwerk import clipart, shortcuts
from labelwerk.document import Document, ImageObject, TextObject
from labelwerk.gui.image_import import MIME_SYMBOL
from labelwerk.gui.main_window import SYMBOL_MM, MainWindow
from labelwerk.gui.symbol_dialog import EMPTY_OWN, NO_RESULTS, SymbolDialog
from labelwerk.settings import Settings, load_settings

NO_MOD = Qt.KeyboardModifier.NoModifier
LEFT = Qt.MouseButton.LeftButton


def _window(qtbot, doc=None, **settings):
    win = MainWindow(doc=doc or Document("62", length_mm=40,
                                         objects=[TextObject("Eins", size_pt=14, x_mm=2, y_mm=2)]),
                     settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    win.show()
    return win


def _open(win, qtbot) -> SymbolDialog:
    win.panel("image").symbol.click()
    dialog = win.symbol_window
    qtbot.waitUntil(dialog.isVisible, timeout=2000)
    return dialog


def _show_group(dialog, name):
    dialog.groups.setCurrentRow([dialog.groups.item(i).text()
                                 for i in range(dialog.groups.count())].index(name))


def _select(dialog, symbol_id):
    row = [s.id for s in dialog.model.symbols].index(symbol_id)
    dialog.grid.setCurrentIndex(dialog.model.index(row))


def _ids(dialog):
    return [s.id for s in dialog.model.symbols]


# --- Aktion und Fenster ---------------------------------------------------------------
def test_symbol_action_and_button(qtbot):
    entry = shortcuts.action("image.symbol")
    assert (entry.name, entry.default, entry.scope) == ("Symbol einfügen …", "", "canvas")
    win = _window(qtbot)
    assert win.panel("image").symbol.text() == "SYMBOL …"
    dialog = _open(win, qtbot)
    assert dialog.windowTitle() == "Symbol einfügen" and not dialog.isModal()
    win.panel("image").symbol.click()
    assert win.symbol_window is dialog                      # eine Instanz


def test_groups_and_start_in_electrical_without_recent(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    assert [dialog.groups.item(i).text() for i in range(dialog.groups.count())] == [
        "Zuletzt verwendet", "Favoriten", "Elektro", "Versand", "Sicherheit", "Allgemein", "Eigene"]
    assert dialog.groups.currentItem().text() == "Elektro"
    assert "labelwerk/schutzleiter" in _ids(dialog)


def test_subgroups_filter_large_groups(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    _show_group(dialog, "Sicherheit")
    assert dialog.subgroup.isVisible() and dialog.subgroup.itemText(0) == "Alle"
    dialog.subgroup.setCurrentText("Warnzeichen")
    assert _ids(dialog) and all(i.startswith("iso7010/W") for i in _ids(dialog))


def test_search_spans_the_whole_library(qtbot):
    dialog = _open(_window(qtbot), qtbot)                   # steht in „Elektro“
    dialog.search.setText("Haus")
    assert "tabler/outline/home" in _ids(dialog)
    dialog.search.setText("gibtesnichtxyz")
    assert _ids(dialog) == [] and dialog.empty.text() == NO_RESULTS
    assert not dialog.insert.isEnabled()


def test_previews_are_rendered_on_demand(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    icon = dialog.model.data(dialog.model.index(0), Qt.ItemDataRole.DecorationRole)
    assert not icon.isNull()
    tip = dialog.model.data(dialog.model.index(0), Qt.ItemDataRole.ToolTipRole)
    assert dialog.model.symbols[0].name in tip


# --- Einfügen -------------------------------------------------------------------------
def test_double_click_signal_inserts_a_15_mm_vector_symbol(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/schutzleiter")
    index = dialog.grid.currentIndex()
    dialog.grid.doubleClicked.emit(index)
    obj = win.doc.objects[1]
    assert isinstance(obj, ImageObject) and obj.svg is not None
    assert obj.source == "Symbol: Schutzleiter (PE)"
    assert max(obj.w_mm, obj.h_mm) == pytest.approx(SYMBOL_MM, abs=0.05)
    assert (obj.mode, obj.keep_ratio) == ("line", True)
    assert win.canvas.selection() == [1]
    win.undo()
    assert len(win.doc.objects) == 1


def test_original_size_is_the_symbol_size(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/erde")
    dialog.insert.click()
    obj = win.doc.objects[1]
    assert max(obj.natural_mm()) == pytest.approx(SYMBOL_MM, abs=0.05)


def test_inserted_symbol_is_cropped_to_its_ink(qtbot):
    """Tabler-Icons haben Rand in der Zeichenfläche – der fällt weg."""
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    dialog.search.setText("house")
    _select(dialog, "tabler/outline/home")
    dialog.insert.click()
    obj = win.doc.objects[1]
    l, t, r, b = obj.crop
    assert l > 0 and t > 0 and r < obj.image().width and b < obj.image().height


@pytest.mark.parametrize("symbol_id", ["labelwerk/motor", "labelwerk/batterie", "iso7000/0627",
                                       "tabler/outline/home"])
def test_crop_off_and_on_again_gives_the_same_section(qtbot, symbol_id):
    """Das Panel schneidet Symbole wie beim Einfügen auf die Tinte zu (nicht per
    Schnittmarken-Erkennung: von „Motor“ bliebe sonst nur das „M“)."""
    win = _window(qtbot)
    win.insert_symbol(clipart.find(symbol_id))
    obj = win.doc.objects[1]
    inserted = obj.crop
    assert inserted is not None
    panel = win.panel("image")
    panel.crop.click()
    assert win.doc.objects[1].crop is None
    panel.crop.click()
    assert win.doc.objects[1].crop == inserted
    assert not win.result.text().startswith("Zuschnitt")


def test_symbol_on_narrow_tape_fits_across(qtbot):
    win = _window(qtbot, Document("12", objects=[TextObject("A", size_pt=8)]))
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/erde")
    dialog.insert.click()
    obj = win.doc.objects[1]
    assert max(obj.w_mm, obj.h_mm) == pytest.approx(win._area.w, abs=0.05)
    assert "verkleinert" not in win.result.text()


def test_recent_is_updated_saved_and_shown(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    for symbol_id in ("labelwerk/erde", "labelwerk/motor", "labelwerk/erde"):
        _show_group(dialog, "Elektro")
        _select(dialog, symbol_id)
        dialog.insert.click()
    assert win.settings.symbols_recent[:2] == ["labelwerk/erde", "labelwerk/motor"]
    assert load_settings().symbols_recent[:2] == ["labelwerk/erde", "labelwerk/motor"]
    _show_group(dialog, "Zuletzt verwendet")
    assert _ids(dialog) == ["labelwerk/erde", "labelwerk/motor"]


def test_window_starts_with_recent_when_there_are_some(qtbot):
    dialog = _open(_window(qtbot, symbols_recent=["iso7000/0621", "weg/da"]), qtbot)
    assert dialog.groups.currentItem().text() == "Zuletzt verwendet"
    assert _ids(dialog) == ["iso7000/0621"]                 # unbekannte ids übergangen


def test_favorites_toggle_and_save(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/motor")
    dialog.favorite.click()
    assert dialog.favorite.isChecked()
    assert win.settings.symbols_favorites == ["labelwerk/motor"]
    assert load_settings().symbols_favorites == ["labelwerk/motor"]
    _show_group(dialog, "Favoriten")
    assert _ids(dialog) == ["labelwerk/motor"]
    dialog.favorite.click()
    assert _ids(dialog) == [] and win.settings.symbols_favorites == []


# --- eigener Ordner -------------------------------------------------------------------
def test_own_folder_empty_hint_and_open_button(qtbot, monkeypatch):
    dialog = _open(_window(qtbot), qtbot)
    opened = []
    monkeypatch.setattr(dialog, "open_url", lambda url: opened.append(url.toLocalFile()))
    _show_group(dialog, "Eigene")
    assert dialog.empty.text() == EMPTY_OWN.format(path=clipart.own_dir())
    assert dialog.open_folder.isVisible()
    dialog.open_folder.click()
    assert clipart.own_dir().is_dir() and opened == [str(clipart.own_dir())]


def test_own_png_symbol_is_inserted_as_pixel_image(qtbot):
    folder = clipart.own_dir()
    folder.mkdir(parents=True)
    img = Image.new("RGB", (200, 100), "white")
    img.paste((0, 0, 0), (20, 20, 180, 80))
    img.save(folder / "Stempel.png")
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _show_group(dialog, "Eigene")
    assert _ids(dialog) == ["ordner/Stempel.png"]
    dialog.insert.click()
    obj = win.doc.objects[1]
    assert obj.svg is None and obj.source == "Symbol: Stempel"
    assert (obj.w_mm, obj.h_mm) == pytest.approx((SYMBOL_MM, SYMBOL_MM * 60 / 160), abs=0.05)


def test_broken_own_symbol_gives_message(qtbot):
    folder = clipart.own_dir()
    folder.mkdir(parents=True)
    (folder / "kaputt.svg").write_text("<svg")
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _show_group(dialog, "Eigene")
    dialog.insert.click()
    assert len(win.doc.objects) == 1
    assert win.result.text().startswith("Symbol: ") and win.result.property("state") == "error"


# --- Ziehen aufs Etikett ------------------------------------------------------------
def _drop(canvas, mime, pos):
    try:                    # QDragEnterEvent nimmt erst ab PySide6 6.12 QPointF (CI 3.10: 6.11)
        QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD)
    except TypeError:
        pos = pos.toPoint()
    for event in (QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD),
                  QDropEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD)):
        QApplication.sendEvent(canvas.viewport(), event)
    QTest.qWait(0)


def test_model_drag_data_is_the_symbol_id(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    _select(dialog, "labelwerk/erde")
    mime = dialog.model.mimeData([dialog.grid.currentIndex()])
    assert bytes(mime.data(MIME_SYMBOL)).decode() == "labelwerk/erde"


def test_dropping_a_symbol_inserts_it_at_the_point(qtbot):
    win = _window(qtbot)
    mime = QMimeData()
    mime.setData(MIME_SYMBOL, QByteArray(b"labelwerk/erde"))
    _drop(win.canvas, mime, QPointF(win.canvas.viewport().rect().center()))
    assert len(win.doc.objects) == 2
    obj = win.doc.objects[1]
    assert obj.source == "Symbol: Erde"
    assert obj.x_mm + obj.w_mm / 2 == pytest.approx(31, abs=3)      # Etikettmitte (62 mm)


def test_unknown_dropped_symbol_is_ignored(qtbot):
    win = _window(qtbot)
    mime = QMimeData()
    mime.setData(MIME_SYMBOL, QByteArray(b"gibt/es/nicht"))
    _drop(win.canvas, mime, QPointF(win.canvas.viewport().rect().center()))
    assert len(win.doc.objects) == 1


def test_closing_the_main_window_closes_the_symbol_window(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    win.close()
    assert not dialog.isVisible()


# --- Nachbesserungen: Bedienung, Sonderfälle ------------------------------------------
def test_real_double_click_inserts_exactly_once(qtbot):
    """Qt meldet nach dem Doppelklick zusätzlich „activated“ – eingefügt wird trotzdem einmal."""
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/erde")
    point = dialog.grid.visualRect(dialog.grid.currentIndex()).center()
    QTest.mouseClick(dialog.grid.viewport(), LEFT, NO_MOD, point)
    QTest.mouseDClick(dialog.grid.viewport(), LEFT, NO_MOD, point)
    assert len(win.doc.objects) == 2


def test_single_click_only_selects(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/erde")
    point = dialog.grid.visualRect(dialog.model.index(1)).center()
    QTest.mouseClick(dialog.grid.viewport(), LEFT, NO_MOD, point)
    assert len(win.doc.objects) == 1 and dialog.grid.currentIndex().row() == 1


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_enter_in_the_grid_inserts(qtbot, key):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/motor")
    QTest.keyClick(dialog.grid, key)
    assert len(win.doc.objects) == 2 and win.doc.objects[1].source == "Symbol: Motor"


def test_enter_in_the_search_inserts_the_first_hit(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    QTest.keyClicks(dialog.search, "zerbrech")
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    assert win.doc.objects[1].source == "Symbol: Zerbrechlich"


def test_arrow_down_moves_from_search_into_the_grid(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    dialog.search.setFocus()
    QTest.keyClick(dialog.search, Qt.Key.Key_Down)
    assert dialog.focusWidget() is dialog.grid


def test_escape_closes_the_window(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    QTest.keyClick(dialog.search, Qt.Key.Key_Escape)
    assert not dialog.isVisible()


def test_choosing_a_group_ends_the_search(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    dialog.search.setText("Haus")
    _show_group(dialog, "Versand")
    assert dialog.search.text() == "" and "iso7000/0621" in _ids(dialog)


def test_unknown_recent_ids_do_not_open_an_empty_group(qtbot):
    dialog = _open(_window(qtbot, symbols_recent=["weg/da"]), qtbot)
    assert dialog.groups.currentItem().text() == "Elektro"


def test_previews_are_only_rendered_when_seen(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    _show_group(dialog, "Allgemein")
    QTest.qWait(50)
    assert 0 < len(dialog.model._icons) < dialog.model.rowCount() // 10


def test_favorite_button_shows_its_state(qtbot):
    dialog = _open(_window(qtbot), qtbot)
    _select(dialog, "labelwerk/erde")
    assert dialog.favorite.objectName() == "formatButton" and dialog.favorite.text().startswith("☆")
    dialog.favorite.click()
    assert dialog.favorite.isChecked() and dialog.favorite.text().startswith("★")


def test_context_menu_inserts_and_toggles_favorite(qtbot):
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _select(dialog, "labelwerk/erde")
    menu = dialog.menu_for(dialog.grid.currentIndex())
    texts = [a.text() for a in menu.actions()]
    assert texts == ["Einfügen", "Zu Favoriten"]
    menu.actions()[1].trigger()
    assert win.settings.symbols_favorites == ["labelwerk/erde"]
    assert [a.text() for a in dialog.menu_for(dialog.grid.currentIndex()).actions()][1] == \
        "Aus Favoriten entfernen"
    menu.actions()[0].trigger()
    assert len(win.doc.objects) == 2


def test_wide_symbol_on_narrow_tape_is_neither_shrunk_nor_turned(qtbot):
    win = _window(qtbot, Document("12", objects=[TextObject("A", size_pt=8)]), image_rotate=True)
    dialog = _open(win, qtbot)
    dialog.search.setText("house")
    _select(dialog, "tabler/outline/home")
    dialog.insert.click()
    obj = win.doc.objects[1]
    assert obj.rotation == 0 and max(obj.w_mm, obj.h_mm) <= win._area.w
    assert "verkleinert" not in win.result.text() and "gedreht" not in win.result.text()


def test_screenshot_hides_the_symbol_window_too(qtbot, monkeypatch):
    monkeypatch.setattr(MainWindow, "screenshot_available", lambda self: True)
    monkeypatch.setattr(MainWindow, "take_screenshot", lambda self: None)
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    win.insert_screenshot()
    assert not dialog.isVisible()
    win.screenshot_finished(None, None)
    assert dialog.isVisible()


def test_white_own_symbol_gives_crop_hint(qtbot):
    folder = clipart.own_dir()
    folder.mkdir(parents=True)
    Image.new("RGB", (50, 50), "white").save(folder / "weiss.png")
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _show_group(dialog, "Eigene")
    dialog.insert.click()
    assert win.doc.objects[1].crop is None
    assert "nicht zugeschnitten" in win.result.text()


def test_tiny_drawing_on_a_big_page_does_not_explode(qtbot):
    """Winziger Inhalt auf großer Seite: die Vorschau bleibt begrenzt, kein Speicherfehler."""
    folder = clipart.own_dir()
    folder.mkdir(parents=True)
    (folder / "punkt.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">'
        '<circle cx="500" cy="500" r="3"/></svg>')
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _show_group(dialog, "Eigene")
    dialog.insert.click()
    obj = win.doc.objects[1]
    assert max(obj.image().size) <= 6000 and obj.svg is not None
    assert max(obj.w_mm, obj.h_mm) == pytest.approx(SYMBOL_MM, rel=0.05)


def test_own_svg_with_linked_file_becomes_pixel_image(qtbot):
    folder = clipart.own_dir()
    folder.mkdir(parents=True)
    Image.new("RGB", (40, 40), "black").save(folder / "bild.png")
    (folder / "mit-bild.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'width="96" height="96"><image xlink:href="bild.png" width="96" height="96"/></svg>')
    win = _window(qtbot)
    dialog = _open(win, qtbot)
    _show_group(dialog, "Eigene")
    _select(dialog, "ordner/mit-bild.svg")
    dialog.insert.click()
    obj = win.doc.objects[1]
    assert obj.svg is None and obj.image().convert("L").getextrema()[0] == 0


# --- Bibliotheksarchiv defekt oder fehlend ------------------------------------------
def _clear_library_caches():
    for function in (clipart._files, clipart.catalog, clipart._index):
        function.cache_clear()


@pytest.fixture
def broken_library(tmp_path, monkeypatch):
    def make(kind):
        archive = tmp_path / "clipart.zip"
        if kind == "garbage":
            archive.write_bytes(b"kein Zip")
        elif kind == "nocatalog":
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("x.svg", "<svg/>")
        elif kind == "badjson":
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("catalog.json", "{")
        monkeypatch.setattr(clipart, "ARCHIVE", archive)
        _clear_library_caches()
    _clear_library_caches()
    yield make
    _clear_library_caches()      # der Archivpfad kommt mit monkeypatch zurück


@pytest.mark.parametrize("kind", ["garbage", "nocatalog", "badjson", "missing"])
def test_unreadable_library_gives_message_and_no_window(qtbot, broken_library, kind):
    broken_library(kind)
    win = _window(qtbot, symbols_recent=["labelwerk/motor"])
    win.panel("image").symbol.click()
    assert win.symbol_window is None
    assert win.result.text().startswith("Symbol-Bibliothek nicht lesbar: ")
    assert win.result.property("state") == "error"


def test_unreadable_library_does_not_break_dropping(qtbot, broken_library):
    broken_library("garbage")
    win = _window(qtbot)
    win._symbol_dropped("labelwerk/motor", 5, 5)
    assert len(win.doc.objects) == 1
    assert win.result.text().startswith("Symbol-Bibliothek nicht lesbar: ")
