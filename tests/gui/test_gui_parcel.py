"""PARCEL tab (panel “Parcel label”): open a label, detect the type, view the conversion (view only), print,
open in the editor, create/rename/delete custom types. Only generated test labels (parcelmark)."""
import pytest
from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication

from labelwerk import parcel
from labelwerk.document import Document, ImageObject, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.parcel_editor import ParcelTypeEditor
from labelwerk.gui.panels.parcel import OWN, TYPE_ROLE
from labelwerk.settings import Settings
from parcelmark import make_pdf

from test_gui_printers import workers  # noqa: F401  (Fixture: Druck ersetzt)


@pytest.fixture(autouse=True)
def own_folder(tmp_path, monkeypatch):
    """Custom types in an empty folder (never the real data)."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


def _window(qtbot, doc=None, **settings):
    win = main_window.MainWindow(doc=doc or Document("62", objects=[TextObject("A")]),
                                 settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    win.show()
    win.render_now()
    return win


def _dhl(tmp_path, name="dhl.pdf"):
    return make_pdf(tmp_path / name, texts=[(20, 20, "DHL Online Frankierung"),
                                            (20, 40, "Sendungsnummer")],
                    rects=[(15, 30, 120, 34), (140, 40, 190, 100)])


def _amazon(tmp_path):
    return make_pdf(tmp_path / "amazon.pdf", texts=[(20, 20, "Amazon Rücksendung DHL Retoure")],
                    rects=[(40, 120, 150, 160), (60, 240, 150, 270)])


def _open(win, path):
    win.ask_parcel_file = lambda: str(path)
    win._tool_triggered("parcel")
    win.tool_actions["parcel"].setChecked(True)
    win.panel("parcel").open_button.click()
    win.render_now()
    return win.panel("parcel")


def _type_ids(panel) -> list[str]:
    return [panel.types.item(i).data(TYPE_ROLE) for i in range(panel.types.count())
            if panel.types.item(i).data(TYPE_ROLE)]


def test_parcel_tool_is_in_the_toolbar(qtbot):
    win = _window(qtbot)
    assert "parcel" in win.tool_actions
    assert win.tool_actions["parcel"].text() == "PAKET"
    assert win.tool_actions["parcel"].toolTip() == ("Paketmarke (DHL, Hermes …) für den "
                                                    "Etikettendrucker umwandeln")
    panel = win.panel("parcel")
    assert panel.country.currentData() == "DE"
    assert {"dhl-privat-1", "hermes-2"} <= set(_type_ids(panel))
    assert not panel.print_button.isEnabled() and not panel.editor_button.isEnabled()
    assert not panel.own_button.isEnabled()                     # only with an opened label


def test_open_detects_the_type_and_shows_the_conversion(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    assert panel.chosen_type().id == "dhl-privat-1"             # 62 mm: layout “62” wins
    assert panel.types.currentItem().text().startswith("✓ ")
    assert panel.file_label.text() == "dhl.pdf"
    docs = panel.documents()
    assert len(docs) == 1 and docs[0].label_id == "62"
    assert win.canvas.read_only and len(win.canvas.objects) == len(docs[0].objects) == 7
    assert win.canvas.handle is None or not win.canvas.handle.isVisible()
    assert panel.print_button.isEnabled() and panel.editor_button.isEnabled()
    assert win.doc.objects == [TextObject("A")]                 # document untouched


def test_other_tab_shows_the_document_again(qtbot, tmp_path):
    win = _window(qtbot)
    _open(win, _dhl(tmp_path))
    win._tool_triggered("paper")
    assert not win.canvas.read_only and len(win.canvas.objects) == 1
    win._tool_triggered("parcel")
    assert win.canvas.read_only and len(win.canvas.objects) == 7


def test_canvas_ignores_clicks_on_the_conversion(qtbot, tmp_path):
    win = _window(qtbot)
    _open(win, _dhl(tmp_path))
    center = win.canvas.mapFromScene(win.canvas.objects[0].sceneBoundingRect().center())
    qtbot.mouseClick(win.canvas.viewport(), Qt.MouseButton.LeftButton, pos=center)
    qtbot.mouseDClick(win.canvas.viewport(), Qt.MouseButton.LeftButton, pos=center)
    assert win.canvas.selection() == [] and win.edit_session.active is False
    win.shortcut_actions["edit.select_all"].trigger()          # nothing selectable: Del deletes nothing
    win.shortcut_actions["edit.delete"].trigger()
    assert win.canvas.selection() == [] and win.doc.objects == [TextObject("A")]


def test_choosing_another_type_converts_again(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-2")
    panel.types.setCurrentItem(item)
    assert panel.chosen_type().id == "dhl-privat-2"
    assert len(win.canvas.objects) == len(panel.documents()[0].objects)
    assert "ungeprüft" in item.text()


def test_unrecognised_mark_asks_for_the_type(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "x.pdf", size_mm=(50, 50), texts=[(5, 5, "Hallo")]))
    assert panel.chosen_type() is None and panel.documents() == []
    assert panel.notes.isVisibleTo(panel) and "nicht erkannt" in panel.notes.text()
    assert win.canvas.read_only and win.canvas.objects == []    # empty, view only


def test_unreadable_file_is_a_notice(qtbot, tmp_path):
    win = _window(qtbot)
    bad = tmp_path / "kaputt.pdf"
    bad.write_bytes(b"kein PDF")
    panel = _open(win, bad)
    assert panel.source is None and panel.notes.isVisibleTo(panel) and panel.notes.text()


def test_print_sends_every_label_in_one_job(qtbot, tmp_path, workers):  # noqa: F811
    win = _window(qtbot)
    panel = _open(win, _amazon(tmp_path))
    assert len(panel.documents()) == 2 and panel.page_label.text() == "Etikett 1/2"
    panel.print_button.click()
    assert len(workers) == 1
    job = workers[0]
    assert isinstance(job.image, list) and len(job.image) == 2
    assert job.label_id == "62" and job.cut_every == 1


def test_toolbar_print_prints_the_conversion(qtbot, tmp_path, workers):  # noqa: F811
    win = _window(qtbot)
    _open(win, _dhl(tmp_path))
    win.print_label()
    assert len(workers) == 1 and not isinstance(workers[0].image, list)
    assert workers[0].image.size[1] > 1000                     # the conversion, not the label “A”


def test_arrows_show_the_second_label(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _amazon(tmp_path))
    first = len(win.canvas.objects)
    panel.next_button.click()
    assert panel.page_label.text() == "Etikett 2/2" and not panel.next_button.isEnabled()
    assert len(win.canvas.objects) == len(panel.documents()[1].objects) != 0
    panel.prev_button.click()
    assert len(win.canvas.objects) == first


def test_open_in_editor_replaces_the_document(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    panel.editor_button.click()
    assert len(win.doc.objects) == 7 and all(isinstance(o, ImageObject) for o in win.doc.objects)
    assert win.panels.currentWidget() is win.panel("paper") and not win.canvas.read_only
    assert len(win.canvas.objects) == 7
    assert win.files.origin == "parcel" and not win.files.may_follow_roll()
    win.undo()                                                  # history new: nothing to undo
    assert len(win.doc.objects) == 7


def test_open_in_editor_respects_the_save_question(qtbot, tmp_path, monkeypatch):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    monkeypatch.setattr(win.files, "maybe_save", lambda: False)   # “Cancel”
    panel.editor_button.click()
    assert win.doc.objects == [TextObject("A")] and win.panels.currentWidget() is panel


def test_conversion_follows_the_label_of_the_document(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    win.doc.label_id = "62x100"                                 # die-cut, too short
    win.render_now()
    assert panel.documents()[0].label_id == "62x100"
    assert panel.notes.isVisibleTo(panel) and "Barcodes" in panel.notes.text()


def test_drop_on_the_canvas_loads_the_mark(qtbot, tmp_path):
    win = _window(qtbot)
    win._tool_triggered("parcel")
    win._dropped([_dhl(tmp_path)], None, 10, 10)
    assert win.panel("parcel").chosen_type().id == "dhl-privat-1"
    assert win.doc.objects == [TextObject("A")]                 # no image inserted


def test_drop_on_the_panel_loads_the_mark(qtbot, tmp_path):
    win = _window(qtbot)
    panel = win.panel("parcel")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(_dhl(tmp_path)))])
    event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.NoButton,
                       Qt.KeyboardModifier.NoModifier)
    panel.dropEvent(event)
    assert panel.chosen_type().id == "dhl-privat-1"


def test_country_own_only_lists_own_types(qtbot, tmp_path):
    parcel.save_own(parcel.own_from_dict(_own_data()))
    win = _window(qtbot)
    panel = win.panel("parcel")
    panel.country.setCurrentIndex(panel.country.findData(OWN))
    assert _type_ids(panel) == ["eigen-lager"]
    panel.country.setCurrentIndex(panel.country.findData("DE"))
    assert _type_ids(panel)[-1] == "eigen-lager" and "dhl-privat-1" in _type_ids(panel)


def _own_data(**changes):
    data = {"id": "eigen-lager", "names": {"de": "Lager"}, "source": {"sizes_mm": [[210, 297]]},
            "detect": {"all": ["Mein Lager"]},
            "pieces": [{"page": 1, "src": [10, 10, 110, 60], "rotation": 90, "kind": "text"},
                       {"page": 1, "src": [10, 100, 60, 130], "rotation": 0, "kind": "barcode"}]}
    data.update(changes)
    return data


def test_new_own_type_is_saved_and_chosen(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "lager.pdf", texts=[(20, 20, "Mein Lager GmbH")],
                                rects=[(15, 15, 100, 50)]))
    assert panel.chosen_type() is None
    seen = []

    def fill(editor):
        seen.append(editor)
        editor.add_area((10, 10, 110, 60), rotation=90)
        editor.add_area((10, 100, 60, 130), barcode=True)
        editor.name.setText("Mein Lager")
        editor.words.setText("Mein Lager")
        return True
    win.exec_parcel_editor = fill
    panel.own_button.click()
    assert seen and parcel.own_types()[0].names == {"de": "Mein Lager"}
    assert panel.chosen_type().id == "eigen-mein-lager"
    assert panel.documents() and len(panel.documents()[0].objects) == 2
    assert win.canvas.read_only and len(win.canvas.objects) == 2
    assert "gespeichert" in win.result.text()


def test_cancelled_editor_saves_nothing(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    win.exec_parcel_editor = lambda editor: False
    panel.own_button.click()
    assert parcel.own_types() == []


def test_rename_and_remove_own_type(qtbot, tmp_path):
    parcel.save_own(parcel.own_from_dict(_own_data()))
    win = _window(qtbot)
    win.ask_parcel_type_name = lambda current: "Lager Nord"
    win.rename_own_parcel_type("eigen-lager")
    assert parcel.find("eigen-lager").name == "Lager Nord"
    assert any("Lager Nord" in win.panel("parcel").types.item(i).text()
               for i in range(win.panel("parcel").types.count()))
    win.ask_remove_parcel_type = lambda name: False
    win.remove_own_parcel_type("eigen-lager")
    assert parcel.own_types()
    win.ask_remove_parcel_type = lambda name: True
    win.remove_own_parcel_type("eigen-lager")
    assert parcel.own_types() == [] and "eigen-lager" not in _type_ids(win.panel("parcel"))


# --- Window “New own parcel label type” ---------------------------------------------------
def _editor(qtbot, tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Firma")],
                                  rects=[(15, 15, 100, 50)]))
    editor = ParcelTypeEditor(None, source, "62", "QL-600", {"eigen-test"})
    qtbot.addWidget(editor)
    editor.show()
    return editor


def test_editor_builds_a_checked_type(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    save = editor.buttons.button(editor.buttons.StandardButton.Save)
    assert not save.isEnabled()
    editor.add_area((10, 10, 110, 60))
    editor.add_area((1, 1, 2, 2))                               # too small: does not count
    editor.list.setCurrentRow(0)
    editor.rotation.setCurrentIndex(1)                          # 90°
    editor.barcode.setChecked(True)
    editor.name.setText("Test")
    assert save.isEnabled()
    ptype = editor.result_type()
    assert ptype.id == "eigen-test-2" and ptype.own              # “eigen-test” is taken
    assert ptype.pieces[0].rotation == 90 and ptype.pieces[0].kind == "barcode"
    assert ptype.pieces[0].src == pytest.approx((10, 10, 110, 60), abs=0.3)
    assert len(ptype.pieces) == 1 and ptype.source_sizes == ((210.0, 297.0),)
    assert not editor.preview.pixmap().isNull()


def test_editor_draws_and_removes_areas_with_the_mouse(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    view = editor.view
    start = view.mapFromScene(QPointF(50, 50))
    end = view.mapFromScene(QPointF(300, 200))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert len(editor.pieces()) == 1 and editor.list.count() == 1
    editor.list.setCurrentRow(0)
    editor.view.setFocus()
    qtbot.keyClick(editor, Qt.Key.Key_Delete)
    assert editor.pieces() == [] and editor.list.count() == 0


def test_editor_words_become_recognition(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 110, 60))
    editor.name.setText("Firma")
    editor.words.setText("Firma, Lager ")
    assert editor.result_type().detect == {"all": ["Firma", "Lager"]}
    QApplication.processEvents()


# --- Tie, not detected, rearranged -------------------------------------------------------
def test_tie_between_unverified_types_lets_the_user_choose(qtbot, tmp_path):
    """Hermes 2 and 3 cannot be told apart by the text: no type preselected, nothing
    printed, the note names both; the choice decides."""
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein")]))
    assert panel.chosen_type() is None and panel.documents() == []
    assert not panel.print_button.isEnabled()
    text = panel.notes.text()
    assert "gleich gut" in text
    assert parcel.find("hermes-2").name in text and parcel.find("hermes-3").name in text
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "hermes-3")
    panel.types.setCurrentItem(item)
    assert panel.chosen_type().id == "hermes-3" and panel.documents()
    assert "gleich gut" not in panel.notes.text()


def test_image_of_unknown_shape_is_not_recognised(qtbot, tmp_path):
    from PIL import Image
    Image.new("RGB", (1000, 1000), "white").save(tmp_path / "q.png")
    win = _window(qtbot)
    panel = _open(win, tmp_path / "q.png")
    assert panel.chosen_type() is None and panel.documents() == []
    assert "nicht erkannt" in panel.notes.text()
    assert len(_type_ids(panel)) >= 19                          # list stays selectable


def test_wrong_size_for_the_chosen_type_is_a_notice(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "gross.pdf", size_mm=(400, 400)))
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-1")
    panel.types.setCurrentItem(item)
    assert panel.documents() == [] and "passt nicht" in panel.notes.text()


def test_arranged_layout_says_so(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "m.pdf", size_mm=(100, 150),
                                texts=[(10, 10, "DHL Online Frankierung")]))
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-1a-100x150")
    panel.types.setCurrentItem(item)
    assert panel.conversion.layout == "arranged"
    assert "neu angeordnet" in panel.notes.text()


# --- Review 559ac76: view only, printing without a conversion, ✓, toolbar, editor ----------------
VIEW_ONLY = "nur Ansicht"


def _view_only(win):
    return VIEW_ONLY in win.result.text()


def test_edit_actions_are_disabled_while_the_parcel_view_is_shown(qtbot, tmp_path):
    win = _window(qtbot)
    win.insert_barcode()                                        # one step in the history
    _open(win, _dhl(tmp_path))
    actions = win.shortcut_actions
    for key in ("edit.paste", "edit.undo", "edit.redo", "edit.select_all", "tool.text",
                "image.insert", "barcode.insert", "align.left"):
        assert not actions[key].isEnabled(), key
    win._tool_triggered("paper")
    win.render_now()
    assert actions["edit.undo"].isEnabled() and actions["edit.select_all"].isEnabled()


def test_every_way_of_changing_the_document_is_refused_in_the_parcel_view(qtbot, tmp_path):
    from PIL import Image
    from labelwerk import clipart
    win = _window(qtbot)
    win.insert_barcode()
    before = list(win.doc.objects)
    _open(win, _dhl(tmp_path))
    QApplication.clipboard().setText("Eingefügt")
    picture = Image.new("RGB", (60, 40), "black")
    png = tmp_path / "bild.png"
    picture.save(png)
    ways = [win.paste, win.undo, win.redo, win.insert_barcode,
            lambda: win.insert_symbol(clipart.symbols("allgemein")[0]),
            lambda: win.insert_image_files([png]),
            lambda: win._insert_picture(picture, "Test"),
            lambda: win._dropped([], picture, 10, 10),
            lambda: win.create_text(5, 5)]
    for way in ways:
        win._set_result("", "")
        way()
        assert win.doc.objects == before, way
        assert _view_only(win), way
    win._dropped([_amazon(tmp_path)], None, 10, 10)              # file: loads the label
    assert win.panel("parcel").path.name == "amazon.pdf" and win.doc.objects == before


def test_without_a_conversion_nothing_is_printed(qtbot, tmp_path, workers):  # noqa: F811
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein")]))
    assert panel.documents() == [] and win.canvas.read_only and win.canvas.objects == []
    win.print_label()
    assert workers == [] and "Markentyp" in win.result.text()
    win.shortcut_actions["file.print"].trigger()
    assert workers == []


def test_wrong_size_error_is_shown_when_printing(qtbot, tmp_path, workers):  # noqa: F811
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "gross.pdf", size_mm=(400, 400)))
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-1")
    panel.types.setCurrentItem(item)
    win.print_label()
    assert workers == [] and "passt nicht" in win.result.text()


def test_check_mark_only_at_the_best_types_and_tie_hint(qtbot, tmp_path, monkeypatch):
    first, second, third = (parcel.find(i) for i in ("dhl-privat-1", "dhl-privat-2", "hermes-2"))
    monkeypatch.setattr(parcel, "detect", lambda *a, **k: [(first, 5.0), (second, 5.0),
                                                          (third, 1.0)])
    monkeypatch.setattr(parcel, "ambiguous", lambda found: [])      # tested winner
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    marked = {panel.types.item(i).data(TYPE_ROLE) for i in range(panel.types.count())
              if panel.types.item(i).text().startswith("✓ ")}
    assert marked == {"dhl-privat-1", "dhl-privat-2"}
    assert panel.chosen_type().id == "dhl-privat-1"
    assert "bitte Auswahl prüfen" in panel.notes.text()
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-2")
    panel.types.setCurrentItem(item)
    assert "bitte Auswahl prüfen" not in panel.notes.text()


def test_type_list_shows_about_seven_entries(qtbot):
    win = _window(qtbot)
    assert win.panel("parcel").types.minimumHeight() >= 220


def test_open_in_editor_counts_as_changed(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    panel.editor_button.click()
    assert win.files.modified() and "•" in win.windowTitle()


def test_own_type_buttons_and_rename_keeps_the_choice(qtbot, tmp_path):
    parcel.save_own(parcel.own_from_dict(_own_data()))
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    assert panel.chosen_type().id == "dhl-privat-1" and not panel.own_row.isVisibleTo(panel)
    win.ask_parcel_type_name = lambda current: "Lager Nord"
    win.rename_own_parcel_type("eigen-lager")
    assert panel.chosen_type().id == "dhl-privat-1"             # choice stays
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "eigen-lager")
    panel.types.setCurrentItem(item)
    assert panel.own_row.isVisibleTo(panel)
    renamed = []
    panel.rename_requested.connect(renamed.append)
    panel.rename_button.click()
    assert renamed == ["eigen-lager"]
    win.ask_remove_parcel_type = lambda name: True
    panel.remove_button.click()
    assert parcel.own_types() == []


def test_damaged_own_types_are_shown_as_a_hint(qtbot, tmp_path):
    parcel.own_dir().mkdir(parents=True)
    (parcel.own_dir() / "kaputt.json").write_text("{nicht json")
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    assert "beschädigt" in panel.notes.text()


@pytest.mark.parametrize("lang", ["de", "en"])
def test_print_and_settings_never_overflow(qtbot, lang):
    from PySide6.QtCore import QLocale
    from labelwerk import i18n
    from labelwerk.gui.app import load_theme
    app = QApplication.instance()
    i18n.set_language(lang)
    app.setStyleSheet(load_theme())
    try:
        win = _window(qtbot)
        win.fit_toolbars()
        win.resize(1100, 800)
        for _ in range(3):
            QApplication.processEvents()
        for action in (win.print_action, win.settings_action):
            button = win.app_bar.widgetForAction(action)
            assert button.isVisible(), action.text()
            right = button.mapTo(win, button.rect().topRight()).x()
            assert right <= win.width(), action.text()
    finally:
        app.setStyleSheet("")
        i18n.set_language("de")
        QLocale.setDefault(QLocale("de"))


# --- Window “New own parcel label type”: checks, limits, preview ------------------------------
def test_editor_save_needs_a_valid_type_and_accept_checks(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    save = editor.buttons.button(editor.buttons.StandardButton.Save)
    editor.add_area((10, 10, 110, 60))
    assert not save.isEnabled()                                 # without a name
    editor.accept()
    assert editor.result() == 0 and "Namen" in editor.preview.text()
    editor.name.setText("Test")
    assert save.isEnabled()
    assert editor.name.maxLength() == 200


def test_editor_areas_stay_on_the_page(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 60, 40))
    area = editor._areas[1][0]
    area.setPos(QPointF(-500, 99999))
    rect, page = area.scene_rect(), editor.view.scene().sceneRect()
    assert page.contains(rect)


def test_editor_warns_about_overlapping_areas(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 60, 40))
    assert not editor.overlap.isVisibleTo(editor)
    editor.add_area((50, 30, 90, 70))
    assert editor.overlap.isVisibleTo(editor)


def test_editor_preview_waits_while_moving_and_name_does_not_render(qtbot, tmp_path, monkeypatch):
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 60, 40))
    calls = []
    monkeypatch.setattr(editor, "_render_preview", lambda: calls.append(1))
    editor.name.setText("Neu")
    assert calls == []                                          # name: no new preview
    area = editor._areas[1][0]
    area.setPos(area.pos() + QPointF(5, 5))
    assert calls == [] and editor._preview_timer.isActive()
    editor._preview_now()                                       # release: immediately
    assert calls == [1] and not editor._preview_timer.isActive()


# --- Overall review proto-pk-final -------------------------------------------------------------
def test_deleted_mark_resets_the_result(qtbot, tmp_path, workers):  # noqa: F811
    win = _window(qtbot)
    path = _dhl(tmp_path)
    panel = _open(win, path)
    assert panel.documents()
    path.unlink()
    panel.source._cache.clear()                                 # another label: read the page again
    item = next(panel.types.item(i) for i in range(panel.types.count())
                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-2")
    panel.types.setCurrentItem(item)
    win.render_now()
    assert panel.documents() == [] and not panel.print_button.isEnabled()
    assert panel.page_label.text() == "–" and "nicht mehr lesen" in panel.notes.text()
    assert win.canvas.read_only and win.canvas.objects == []
    win.print_label()
    assert workers == []


def test_failed_second_load_keeps_the_previous_mark(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    bad = tmp_path / "kaputt.pdf"
    bad.write_bytes(b"kein PDF")
    assert not panel.load(bad)
    assert panel.path.name == "dhl.pdf" and panel.documents()
    assert "vorige Paketmarke bleibt geladen" in panel.notes.text()


@pytest.mark.parametrize("size", [(210, 297), (148, 210), (100, 150)])
def test_editor_area_to_the_page_edge_is_valid(qtbot, tmp_path, size):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=size, rects=[(5, 5, 50, 50)]))
    editor = ParcelTypeEditor(None, source, "62", "QL-600", set())
    qtbot.addWidget(editor)
    editor.add_area((0, 0, size[0] + 1, size[1] + 1))           # dragged beyond the edge
    editor.name.setText("Rand")
    assert editor.pieces()[0]["src"] == [0, 0, size[0], size[1]]
    assert editor.problem() is None and editor.result_type()


def test_layout_actions_follow_the_selection_after_the_parcel_view(qtbot, tmp_path):
    win = _window(qtbot)
    win.canvas.set_selection([0])
    assert win.shortcut_actions["align.paper_left"].isEnabled()     # before: selection present
    _open(win, _dhl(tmp_path))
    win._tool_triggered("layout")
    win.render_now()
    assert win.canvas.selection() == []
    assert not win.shortcut_actions["align.paper_left"].isEnabled()   # without a selection nothing


def test_fit_toolbars_after_a_theme_change_keeps_the_window_width(qtbot):
    win = _window(qtbot)
    win.resize(900, 700)
    win.fit_toolbars(resize=False)
    assert win.width() == 900 and win.app_bar.minimumWidth() > 0


def test_toolbars_cannot_be_hidden_by_the_context_menu(qtbot):
    win = _window(qtbot)
    menu = win.createPopupMenu()
    actions = menu.actions() if menu is not None else []
    assert win.tool_bar.toggleViewAction() not in actions
    assert win.app_bar.toggleViewAction() not in actions


def test_overflow_button_is_highlighted_for_a_hidden_active_tab(qtbot):
    from PySide6.QtWidgets import QToolButton
    from labelwerk.gui.app import load_theme
    app = QApplication.instance()
    app.setStyleSheet(load_theme())
    try:
        win = _window(qtbot)
        win.fit_toolbars(resize=False)
        win.resize(760, 700)
        for _ in range(3):
            QApplication.processEvents()
        ext = win.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
        hidden = [k for k, a in win.tool_actions.items()
                  if not win.tool_bar.widgetForAction(a).isVisible()]
        assert ext is not None and ext.isVisible() and hidden
        win._tool_triggered(hidden[-1])
        win.tool_actions[hidden[-1]].setChecked(True)
        win._mark_overflow()
        assert ext.property("active") is True
        win._tool_triggered("paper")
        win.tool_actions["paper"].setChecked(True)
        win._mark_overflow()
        assert ext.property("active") is False
    finally:
        app.setStyleSheet("")


def test_overflow_highlight_shows_without_a_stylesheet(qtbot):
    """Design “Classic” (no stylesheet): the overflow button is still recognisably marked."""
    from PySide6.QtWidgets import QToolButton
    assert QApplication.instance().styleSheet() == ""
    win = _window(qtbot)
    win.fit_toolbars(resize=False)
    ext, hidden = None, []
    for width in (600, 420, 300, 240):                    # without a stylesheet the buttons are narrower
        win.resize(width, 700)
        for _ in range(3):
            QApplication.processEvents()
        ext = win.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
        hidden = [k for k, a in win.tool_actions.items()
                  if not win.tool_bar.widgetForAction(a).isVisible()]
        if hidden:
            break
    assert ext is not None and hidden
    win._tool_triggered(hidden[-1])
    win.tool_actions[hidden[-1]].setChecked(True)
    win._mark_overflow()
    assert ext.text() == "» •" and ext.font().bold()
    win._tool_triggered("paper")
    win.tool_actions["paper"].setChecked(True)
    win._mark_overflow()
    assert ext.text() == "»" and not ext.font().bold()


# --- Space between the pieces ------------------------------------------------------------------
def test_editor_sets_a_space_after_an_area(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 110, 60))
    editor.add_area((10, 100, 60, 130), barcode=True)
    editor.name.setText("Test")
    editor.list.setCurrentRow(0)
    assert editor.space.isEnabled() and editor.space.value() == 0
    editor.space.setValue(20)
    assert editor.pieces()[0]["space_after_mm"] == 20 and "space_after_mm" not in editor.pieces()[1]
    assert "20 mm" in editor.list.item(0).text()
    assert editor.result_type().pieces[0].space_after == 20
    editor.list.setCurrentRow(1)                                # last area: no space after it
    assert not editor.space.isEnabled()
    editor.list.setCurrentRow(0)
    assert editor.space.value() == 20                           # field shows the chosen area


def test_editor_space_shows_in_the_preview(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 60, 40))
    editor.add_area((10, 100, 60, 130))
    editor.list.setCurrentRow(0)
    before = editor.preview.pixmap().width() / editor.preview.pixmap().height()
    editor.space.setValue(80)
    after = editor.preview.pixmap().width() / editor.preview.pixmap().height()
    assert after > before * 1.3                                 # the label becomes clearly longer


def test_panel_changes_the_spaces_for_this_label_only(qtbot, tmp_path):
    pieces = [dict(p) for p in _own_data()["pieces"]]
    pieces[0]["space_after_mm"] = 15
    parcel.save_own(parcel.own_from_dict(_own_data(pieces=pieces)))
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "lager.pdf", texts=[(20, 20, "Mein Lager GmbH")],
                                rects=[(15, 15, 100, 50)]))
    assert panel.chosen_type().id == "eigen-lager"
    assert panel.spaces_box.isVisible() and [b.value() for b in panel.space_boxes] == [15]
    length = panel.documents()[0].length_mm
    panel.space_boxes[0].setValue(40)
    assert panel.documents()[0].length_mm == pytest.approx(length + 25, abs=0.1)
    assert parcel.find("eigen-lager").pieces[0].space_after == 15     # type stays as it is
    win.render_now()
    assert len(win.canvas.objects) == 2                              # canvas follows
    panel.load(tmp_path / "lager.pdf")                                # new label: values of the type
    assert [b.value() for b in panel.space_boxes] == [15]


def test_panel_hides_spaces_for_types_without(qtbot, tmp_path):
    win = _window(qtbot)
    panel = _open(win, _dhl(tmp_path))
    assert panel.chosen_type() is not None and not panel.spaces_box.isVisible()


def test_editor_space_takes_typed_decimals(qtbot, tmp_path):
    """Typing “12,5”: the field must not reset itself while typing (review)."""
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 60, 40))
    editor.add_area((10, 100, 60, 130))
    editor.list.setCurrentRow(0)
    editor.space.lineEdit().selectAll()
    qtbot.keyClicks(editor.space.lineEdit(), "12,5")
    qtbot.keyClick(editor.space.lineEdit(), Qt.Key.Key_Return)
    assert editor.pieces()[0]["space_after_mm"] == 12.5


def test_editor_drops_the_space_of_the_last_area(qtbot, tmp_path):
    editor = _editor(qtbot, tmp_path)
    editor.add_area((10, 10, 60, 40))
    editor.add_area((10, 100, 60, 130))
    editor.list.setCurrentRow(0)
    editor.space.setValue(20)
    editor.list.setCurrentRow(1)
    editor.remove_selected()                                    # the first is now the last
    assert "space_after_mm" not in editor.pieces()[0]
    editor.list.setCurrentRow(0)
    assert not editor.space.isEnabled() and editor.space.toolTip() != editor.SPACE_TIP


def test_panel_spaces_follow_a_changed_type(qtbot, tmp_path):
    """The same type with other spaces (second instance): fields anew from the type."""
    pieces = [dict(p) for p in _own_data()["pieces"]]
    pieces[0]["space_after_mm"] = 15
    parcel.save_own(parcel.own_from_dict(_own_data(pieces=pieces)))
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "lager.pdf", texts=[(20, 20, "Mein Lager GmbH")],
                                rects=[(15, 15, 100, 50)]))
    pieces[0]["space_after_mm"] = 33
    parcel.save_own(parcel.own_from_dict(_own_data(pieces=pieces)))
    panel.refresh_types()
    assert [b.value() for b in panel.space_boxes] == [33]


def test_panel_keeps_changed_spaces_for_another_label(qtbot, tmp_path):
    pieces = [dict(p) for p in _own_data()["pieces"]]
    pieces[0]["space_after_mm"] = 15
    parcel.save_own(parcel.own_from_dict(_own_data(pieces=pieces)))
    win = _window(qtbot)
    panel = _open(win, make_pdf(tmp_path / "lager.pdf", texts=[(20, 20, "Mein Lager GmbH")],
                                rects=[(15, 15, 100, 50)]))
    panel.space_boxes[0].setValue(40)
    panel.set_target("102", "QL-1100")
    assert [b.value() for b in panel.space_boxes] == [40]
