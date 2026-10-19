"""Dateiauswahl mit Vorschau (Etappe Oberfläche): Vorschau je Dateiart, eigener Dialog mit
Seitenwahl für PDF, Dateiauswahl des Systems als Einstellung – nie ein echter modaler Dialog."""
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QFileDialog

from labelwerk import storage
from labelwerk.document import Document, TextObject
from labelwerk.gui import file_dialog
from labelwerk.gui.file_dialog import Chosen, PreviewFileDialog, ask_open, make_preview
from labelwerk.gui.main_window import MainWindow
from labelwerk.settings import Settings


def _png(tmp_path, name="bild.png", size=(400, 200)) -> Path:
    path = tmp_path / name
    Image.new("RGB", size, "black").save(path)
    return path


def _pdf(tmp_path, sizes=((300, 150), (150, 300), (200, 200))) -> Path:
    path = tmp_path / "marken.pdf"
    pages = [Image.new("RGB", s, "black") for s in sizes]
    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=72)
    return path


# --- Vorschau je Dateiart -------------------------------------------------------------
def test_image_preview_is_scaled_and_names_the_size(tmp_path):
    preview = make_preview(_png(tmp_path), size=100)
    assert preview.image is not None and max(preview.image.width(), preview.image.height()) <= 100
    assert preview.image.width() > preview.image.height()
    assert "bild.png" in preview.text and "400 × 200" in preview.text


def test_jpeg_preview_follows_the_exif_orientation(tmp_path):
    path = tmp_path / "foto.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6                                   # 90° gedreht aufgenommen
    Image.new("RGB", (400, 200), "gray").save(path, exif=exif)
    preview = make_preview(path, size=100)
    assert preview.image.height() > preview.image.width()


def test_svg_preview(tmp_path):
    path = tmp_path / "zeichen.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" '
                    'viewBox="0 0 40 20"><rect width="40" height="20"/></svg>')
    preview = make_preview(path, size=100)
    assert preview.image is not None and preview.image.width() > preview.image.height()


def test_pdf_preview_shows_the_chosen_page(tmp_path):
    path = _pdf(tmp_path)
    first, second = make_preview(path, 1, size=100), make_preview(path, 2, size=100)
    assert first.pages == second.pages == 3
    assert first.image.width() > first.image.height()
    assert second.image.height() > second.image.width()
    assert "Seite 2 von 3" in second.text
    assert make_preview(path, 9, size=100).page == 3          # außerhalb → letzte Seite


def test_label_file_preview(tmp_path):
    path = tmp_path / "etikett.labelwerk"
    storage.save(Document("62", objects=[TextObject("Hallo")]), path)
    preview = make_preview(path, size=120)
    assert preview.image is not None and "etikett.labelwerk" in preview.text


def test_table_preview_shows_the_first_rows(tmp_path):
    path = tmp_path / "klemmen.csv"
    path.write_text("Klemme;Signal\n" + "".join(f"X{i};S{i}\n" for i in range(30)))
    preview = make_preview(path)
    assert preview.image is None
    assert "Klemme" in preview.text and "X0" in preview.text and "X8" not in preview.text
    assert "mehr als 8 Zeilen" in preview.text
    path.write_text("Klemme;Signal\nX1;S1\nX2;S2\n")
    assert "2 Zeilen" in make_preview(path).text


def test_large_pictures_are_not_decoded(tmp_path, monkeypatch):
    """Pixelgrenze vor dem Dekodieren (Speicher) – JPEG wird verkleinert dekodiert und darf."""
    monkeypatch.setattr(file_dialog, "MAX_PREVIEW_PIXELS", 1000)
    preview = make_preview(_png(tmp_path))
    assert preview.image is None and "Keine Vorschau" in preview.text and "400 × 200" in preview.text
    jpeg = tmp_path / "foto.jpg"
    Image.new("RGB", (400, 200), "gray").save(jpeg)
    assert make_preview(jpeg, size=100).image is not None


@pytest.mark.parametrize("w, h", [(100000, 1), (1, 100000), (0.001, 1)])
def test_svg_with_extreme_proportions_does_not_break(tmp_path, w, h):
    path = tmp_path / "strich.svg"
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
                    f'<rect width="{w}" height="{h}"/></svg>')
    preview = make_preview(path, size=100)
    assert preview.image is None or not preview.image.isNull()
    if preview.image is not None:
        assert max(preview.image.width(), preview.image.height()) <= 100


@pytest.mark.parametrize("name, data", [("kaputt.png", b"keine Bilddaten"),
                                        ("kaputt.pdf", b"%PDF-1.4 kaputt"),
                                        ("kaputt.labelwerk", b"{"), ("kaputt.csv", b"\xff\xfe\x00")])
def test_broken_files_have_no_preview_but_never_raise(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    preview = make_preview(path)
    assert preview.image is None and name in preview.text


def test_too_large_files_are_not_read(tmp_path, monkeypatch):
    path = _png(tmp_path)
    monkeypatch.setattr(file_dialog, "MAX_PREVIEW_BYTES", 10)
    preview = make_preview(path)
    assert preview.image is None and "bild.png" in preview.text and "Keine Vorschau" in preview.text


def test_other_files_and_folders_show_name_and_size(tmp_path):
    path = tmp_path / "notiz.xyz"
    path.write_bytes(b"x" * 2048)
    assert make_preview(path).text.startswith("notiz.xyz")
    assert make_preview(tmp_path).image is None


# --- eigener Dialog ---------------------------------------------------------------------
def test_dialog_is_not_native_and_shows_the_preview_of_the_current_file(qtbot, tmp_path):
    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)")
    qtbot.addWidget(dialog)
    assert dialog.testOption(QFileDialog.Option.DontUseNativeDialog)
    dialog.show_preview(str(_png(tmp_path)))
    qtbot.waitUntil(lambda: not dialog.pane.image.pixmap().isNull(), timeout=3000)
    assert not dialog.pane.pages.isVisible()


def test_preview_is_read_in_the_background_and_stale_results_are_dropped(qtbot, tmp_path):
    from labelwerk.gui.file_dialog import PreviewPane
    pane = PreviewPane()
    qtbot.addWidget(pane)
    first, second = _png(tmp_path, "a.png"), _png(tmp_path, "b.png", (100, 300))
    pane.show_file(str(first))
    generation = pane.generation
    pane.show_file(str(second))
    assert pane.generation == generation + 1
    qtbot.waitUntil(lambda: "b.png" in pane.info.text(), timeout=3000)
    pane.show_result(generation, make_preview(first))        # verspätetes Ergebnis von a.png
    assert "b.png" in pane.info.text()


def test_pdf_preview_comes_at_once(qtbot, tmp_path):
    """PDFium ist nicht threadsicher: PDF-Vorschau im GUI-Thread (klein, schnell)."""
    from labelwerk.gui.file_dialog import PreviewPane
    pane = PreviewPane(pages=True)
    qtbot.addWidget(pane)
    pane.show_file(str(_pdf(tmp_path)))
    assert "Seite 1 von 3" in pane.info.text() and not pane.image.pixmap().isNull()


def test_dialog_layout_leaves_room_for_the_file_list(qtbot, tmp_path):
    from PySide6.QtWidgets import QListView, QSplitter, QTreeView
    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)")
    qtbot.addWidget(dialog)
    assert dialog.findChild(QListView, "sidebar").minimumWidth() >= 160
    header = dialog.findChild(QTreeView, "treeView").header()
    assert header.isSectionHidden(2)                          # Spalte Typ
    assert header.sectionResizeMode(0) == header.ResizeMode.Stretch
    screen = dialog.screen().availableGeometry()
    assert dialog.width() <= 0.9 * screen.width() + 1 and dialog.height() <= 0.9 * screen.height() + 1
    dialog.show()
    splitter = dialog.findChild(QSplitter, "splitter")
    qtbot.waitUntil(lambda: splitter.sizes()[0] >= 160, timeout=2000)


def test_dialog_follows_the_current_file(qtbot, tmp_path):
    path = _png(tmp_path)
    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)")
    qtbot.addWidget(dialog)
    dialog.currentChanged.emit(str(path))
    qtbot.waitUntil(lambda: "bild.png" in dialog.pane.info.text(), timeout=2000)


def test_pdf_page_is_chosen_in_the_dialog(qtbot, tmp_path):
    path = _pdf(tmp_path)
    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)", pages=True)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.show_preview(str(path))
    assert dialog.pane.pages.isVisible() and dialog.pane.page_label.text() == "1/3"
    dialog.pane.next.click()
    assert dialog.pane.page_label.text() == "2/3" and dialog.pane.page == 2
    dialog.pane.next.click()
    dialog.pane.next.click()                                  # bleibt auf der letzten
    assert dialog.pane.page == 3 and not dialog.pane.next.isEnabled()
    dialog.pane.prev.click()
    assert dialog.page_for(str(path)) == 2
    assert dialog.page_for(str(tmp_path / "andere.pdf")) is None


def test_without_pages_option_pdf_has_no_page_choice(qtbot, tmp_path):
    dialog = PreviewFileDialog(None, "Etikett öffnen", str(tmp_path), "Alle (*)")
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.show_preview(str(_pdf(tmp_path)))
    assert not dialog.pane.pages.isVisible()


def test_ask_open_returns_path_and_page(qtbot, tmp_path, monkeypatch):
    path = _pdf(tmp_path)

    def user(dialog):
        dialog.show_preview(str(path))
        dialog.pane.next.click()
        dialog.selectFile(str(path))
        return True
    monkeypatch.setattr(file_dialog, "exec_dialog", user)
    chosen = ask_open(None, "Bild einfügen", str(tmp_path), "Alle (*)", pages=True)
    assert isinstance(chosen, Chosen) and chosen == str(path) and chosen.page == 2


def test_ask_open_cancelled(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(file_dialog, "exec_dialog", lambda dialog: False)
    assert ask_open(None, "Bild einfügen", str(tmp_path), "Alle (*)") is None


def test_system_dialog_uses_the_qt_dialog_and_asks_the_page_later(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(file_dialog, "exec_dialog", lambda d: pytest.fail("eigener Dialog"))
    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
                        lambda parent, title, folder, filter_: seen.append((title, folder))
                        or (str(tmp_path / "a.pdf"), filter_))
    chosen = ask_open(None, "Bild einfügen", str(tmp_path), "Alle (*)", system=True, pages=True)
    assert chosen == str(tmp_path / "a.pdf") and chosen.page is None
    assert seen == [("Bild einfügen", str(tmp_path))]


# --- Hauptfenster ----------------------------------------------------------------------
def _window(qtbot, **settings):
    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
                     settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    return win


def test_insert_image_takes_the_page_from_the_dialog(qtbot, tmp_path, monkeypatch):
    path = _pdf(tmp_path)

    def user(dialog):
        assert dialog.windowTitle() == "Bild einfügen"
        assert dialog.nameFilters()[0].startswith("Bilder und PDF (")
        dialog.show_preview(str(path))
        dialog.pane.next.click()
        dialog.selectFile(str(path))
        return True
    monkeypatch.setattr(file_dialog, "exec_dialog", user)
    win = _window(qtbot)
    win.ask_pdf_page = lambda path, count: pytest.fail("Seite schon im Dialog gewählt")
    win.panel("image").from_file.click()
    assert (win.doc.objects[1].source, win.doc.objects[1].page) == ("marken.pdf", 2)
    assert win._image_dir == str(tmp_path)


def test_with_system_dialog_the_page_is_asked_afterwards(qtbot, tmp_path, monkeypatch):
    path = _pdf(tmp_path)
    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
                        lambda *args: (str(path), ""))
    win = _window(qtbot, system_file_dialog=True)
    asked = []
    win.ask_pdf_page = lambda p, count: asked.append(count) or 3
    win.panel("image").from_file.click()
    assert asked == [3] and win.doc.objects[1].page == 3


def test_series_table_and_open_label_use_the_preview_dialog(qtbot, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(file_dialog, "exec_dialog",
                        lambda d: seen.append((d.windowTitle(), d.nameFilters()[0])) and False)
    win = _window(qtbot)
    assert win.ask_series_file() is None
    assert win.files.ask_open_file() is None
    assert seen[0][0] == "Tabelle für die Serie" and seen[0][1].startswith("Tabellen (")
    assert seen[1][0] == "Etikett öffnen" and seen[1][1].startswith("labelwerk-Etiketten (")


# --- Einstellung „Dateiauswahl des Systems verwenden“ -----------------------------------
def test_setting_in_the_dialog_needs_a_restart(qtbot, tmp_path):
    from labelwerk.gui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.system_file_dialog.isChecked() and dialog.restart_hint.isHidden()
    dialog.system_file_dialog.setChecked(True)
    assert dialog.restart_hint.isVisible()
    assert dialog.values().system_file_dialog is True


def test_system_dialog_is_chosen_by_a_qt_argument_without_touching_the_environment(monkeypatch):
    """Platform-Theme „xdgdesktopportal“ (Dialog des Desktops über das XDG-Portal) als Argument
    der Anwendung – Kindprozesse erben nichts."""
    from labelwerk.gui.app import qt_arguments
    monkeypatch.setenv("QT_QPA_PLATFORMTHEME", "qt5ct")
    assert qt_arguments(["labelwerk-gui", "a.labelwerk"], True) == [
        "labelwerk-gui", "-platformtheme", "xdgdesktopportal", "a.labelwerk"]
    assert qt_arguments(["labelwerk-gui"], False) == ["labelwerk-gui"]
    import os
    assert os.environ["QT_QPA_PLATFORMTHEME"] == "qt5ct"


def test_system_dialog_needs_the_qt_plugin(monkeypatch, tmp_path):
    assert file_dialog.system_dialog_available()               # PySide6 bringt es mit
    plugins = tmp_path / "plugins" / "platformthemes"
    plugins.mkdir(parents=True)
    monkeypatch.setattr(file_dialog, "_plugins_path", lambda: str(tmp_path / "plugins"))
    assert not file_dialog.system_dialog_available()
    (plugins / "libqxdgdesktopportal.so").write_bytes(b"")
    assert file_dialog.system_dialog_available()


def test_without_plugin_the_setting_is_locked_and_the_own_dialog_is_used(qtbot, tmp_path,
                                                                        monkeypatch):
    from labelwerk.gui.settings_dialog import SettingsDialog
    monkeypatch.setattr(file_dialog, "system_dialog_available", lambda: False)
    dialog = SettingsDialog(Settings(system_file_dialog=True), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    assert not dialog.system_file_dialog.isEnabled() and dialog.system_file_dialog.toolTip()
    seen = []
    monkeypatch.setattr(file_dialog, "exec_dialog", lambda d: seen.append(d) and False)
    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
                        lambda *a: pytest.fail("Systemdialog ohne Plugin"))
    win = _window(qtbot, system_file_dialog=True)
    assert win.ask_image_file() is None and len(seen) == 1


def test_the_dialog_kind_is_fixed_at_start(qtbot, tmp_path, monkeypatch):
    """Die Einstellung wirkt erst nach einem Neustart – bis dahin bleibt der Weg vom Start."""
    seen = []
    monkeypatch.setattr(file_dialog, "exec_dialog", lambda d: seen.append(d) and False)
    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
                        lambda *a: pytest.fail("Systemdialog vor dem Neustart"))
    win = _window(qtbot)
    win.settings.system_file_dialog = True                     # gespeichert, noch nicht neu gestartet
    assert win.ask_image_file() is None and win.ask_series_file() is None
    assert win.files.ask_open_file() is None and len(seen) == 3


def test_save_as_with_the_system_dialog_asks_before_replacing(qtbot, tmp_path, monkeypatch):
    """Dialoge des Desktops fragen nicht immer vor dem Ersetzen – labelwerk fragt selbst."""
    target = tmp_path / "da.labelwerk"
    storage.save(Document("62", objects=[TextObject("alt")]), target)
    win = _window(qtbot, system_file_dialog=True)
    win.files.ask_save_file = lambda suggested: str(target)
    asked = []
    win.files.ask_replace_file = lambda path: asked.append(path) or False
    assert not win.files.save_as()
    assert asked == [target] and storage.load(target).objects[0].paragraphs[0].text == "alt"
    win.files.ask_replace_file = lambda path: asked.append(path) or True
    assert win.files.save_as() and len(asked) == 2


def test_save_dialog_is_not_native_with_the_own_dialog(qtbot, monkeypatch):
    seen = []
    monkeypatch.setattr(QFileDialog, "exec", lambda self: seen.append(
        self.testOption(QFileDialog.Option.DontUseNativeDialog)) or 0)
    win = _window(qtbot)
    win.files.ask_save_file("x.labelwerk")
    assert seen == [True]
