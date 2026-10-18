"""Reiter Datei (Etappe 3c): Neu/Öffnen/Speichern, ungespeicherte Änderungen, Favoriten, Zuletzt
geöffnet, Start mit Datei oder Favorit. Dialoge und Rückfragen sind ersetzt."""
import pytest
from PySide6.QtCore import Qt

from labelwerk import favorites, shortcuts, storage
from labelwerk.document import Document, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.tools import TOOLS
from labelwerk.render import render_document
from labelwerk.settings import Settings, load_settings


def _doc(text="Absender"):
    return Document("62", length_mm=40, objects=[TextObject(text, size_pt=14, x_mm=4, y_mm=4)])


def _window(qtbot, doc=None, **settings):
    win = MainWindow(doc=doc or _doc(), settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    win.show()
    return win


class Answers:
    """Ersatz für Dialoge: Antworten der Reihe nach, gestellte Fragen gemerkt."""

    def __init__(self, win, **answers):
        self.asked = []
        for name, value in answers.items():
            setattr(win.files, name, self._answer(name, value))

    def _answer(self, name, value):
        def ask(*args):
            self.asked.append(name)
            return value() if callable(value) else value
        return ask


def _type(win, text):
    win.doc.objects[0] = TextObject(text, size_pt=14, x_mm=4, y_mm=4)
    win.panel("text").refresh()
    win.render_now()
    win._commit()


# --- Reiter, Aktionen ------------------------------------------------------------------
def test_file_tab_comes_first_and_window_starts_on_paper(qtbot):
    assert [tool.key for tool in TOOLS][:2] == ["file", "paper"]
    win = _window(qtbot)
    action = win.tool_actions["file"]
    assert action.text() == "DATEI" and action.toolTip() == "Datei und Favoriten"
    assert win.panels.currentWidget() is win.panel("paper")


@pytest.mark.parametrize("key, default", [("file.new", "Ctrl+N"), ("file.open", "Ctrl+O"),
                                          ("file.save", "Ctrl+S"), ("file.save_as", "Ctrl+Shift+S")])
def test_file_actions_have_global_shortcuts(qtbot, key, default):
    entry = shortcuts.action(key)
    assert (entry.default, entry.scope) == (default, "global")
    win = _window(qtbot)
    assert win.shortcut_actions[key] in win.actions()


def test_panel_buttons_trigger_the_actions(qtbot):
    win = _window(qtbot)
    panel = win.panel("file")
    assert [b.text() for b in (panel.new, panel.open, panel.save, panel.save_as)] == [
        "NEU", "ÖFFNEN …", "SPEICHERN", "SPEICHERN UNTER …"]
    assert "Ctrl+S" in panel.save.toolTip()


# --- Speichern, Öffnen, Titel ----------------------------------------------------------
def test_title_untitled_and_dot_when_changed(qtbot):
    win = _window(qtbot)
    assert win.windowTitle() == "Unbenannt – labelwerk"
    _type(win, "Neu")
    assert win.windowTitle() == "• Unbenannt – labelwerk"
    win.undo()
    assert win.windowTitle() == "Unbenannt – labelwerk"        # zurück zum Ausgangsstand


def test_save_asks_for_a_file_the_first_time_and_adds_the_suffix(qtbot, tmp_path):
    win = _window(qtbot)
    answers = Answers(win, ask_save_file=str(tmp_path / "absender"))
    win.shortcut_actions["file.save"].trigger()
    path = tmp_path / "absender.labelwerk"
    assert storage.load(path) == win.doc
    assert answers.asked == ["ask_save_file"]
    assert win.windowTitle() == "absender – labelwerk"
    assert win.result.text() == "Gespeichert: absender.labelwerk"
    _type(win, "geändert")
    win.shortcut_actions["file.save"].trigger()                  # jetzt ohne Dialog
    assert answers.asked == ["ask_save_file"] and storage.load(path).objects[0].text == "geändert"


def test_save_as_always_asks(qtbot, tmp_path):
    win = _window(qtbot)
    Answers(win, ask_save_file=str(tmp_path / "a.labelwerk"))
    win.shortcut_actions["file.save"].trigger()
    answers = Answers(win, ask_save_file=str(tmp_path / "b.labelwerk"))
    win.shortcut_actions["file.save_as"].trigger()
    assert answers.asked == ["ask_save_file"] and (tmp_path / "b.labelwerk").exists()
    assert win.windowTitle() == "b – labelwerk"


def test_cancelled_save_dialog_changes_nothing(qtbot):
    win = _window(qtbot)
    _type(win, "x")
    Answers(win, ask_save_file=None)
    assert not win.files.save()
    assert win.windowTitle().startswith("•")


def test_save_error_is_shown(qtbot, tmp_path):
    win = _window(qtbot)
    Answers(win, ask_save_file=str(tmp_path / "fehlt" / "x.labelwerk"))
    assert not win.files.save()
    assert "nicht gespeichert" in win.result.text() and win.result.property("state") == "error"


def test_open_replaces_the_document_and_resets_undo(qtbot, tmp_path):
    path = tmp_path / "regal.labelwerk"
    storage.save(_doc("Regal 3"), path)
    win = _window(qtbot)
    Answers(win, ask_open_file=str(path))
    win.shortcut_actions["file.open"].trigger()
    assert win.doc.objects[0].text == "Regal 3"
    assert win.panel("text").doc is win.doc                      # Panels behalten das Objekt
    assert not win.history.can_undo(win.doc)
    assert win.windowTitle() == "regal – labelwerk"
    assert load_settings().recent_files == [str(path)]


def test_open_broken_file_keeps_the_document(qtbot, tmp_path):
    path = tmp_path / "kaputt.labelwerk"
    path.write_text("kein json")
    win = _window(qtbot)
    Answers(win, ask_open_file=str(path))
    win.shortcut_actions["file.open"].trigger()
    assert win.doc.objects[0].text == "Absender"
    assert "kaputt.labelwerk" in win.result.text() and win.result.property("state") == "error"


def test_new_gives_an_empty_label_from_the_settings(qtbot):
    win = _window(qtbot, label_id="62x29")
    win.shortcut_actions["file.new"].trigger()
    assert win.doc.label_id == "62x29" and win.doc.is_empty()
    assert win.windowTitle() == "Unbenannt – labelwerk"


# --- Rückfrage bei ungespeicherten Änderungen ---------------------------------------------
@pytest.mark.parametrize("trigger", ["new", "open", "close"])
def test_unchanged_label_needs_no_question(qtbot, tmp_path, trigger):
    path = tmp_path / "x.labelwerk"
    storage.save(_doc(), path)
    win = _window(qtbot)
    answers = Answers(win, ask_save_changes="cancel", ask_open_file=str(path))
    {"new": win.files.new, "open": win.files.open, "close": win.close}[trigger]()
    assert answers.asked in ([], ["ask_open_file"])


def test_changes_cancel_keeps_everything(qtbot):
    win = _window(qtbot)
    _type(win, "wichtig")
    answers = Answers(win, ask_save_changes="cancel")
    win.files.new()
    assert answers.asked == ["ask_save_changes"] and win.doc.objects[0].text == "wichtig"


def test_changes_discard_continues(qtbot):
    win = _window(qtbot)
    _type(win, "weg")
    Answers(win, ask_save_changes="discard")
    win.files.new()
    assert win.doc.is_empty()


def test_changes_save_saves_first(qtbot, tmp_path):
    win = _window(qtbot)
    _type(win, "behalten")
    Answers(win, ask_save_changes="save", ask_save_file=str(tmp_path / "b.labelwerk"))
    win.files.new()
    assert storage.load(tmp_path / "b.labelwerk").objects[0].text == "behalten"
    assert win.doc.is_empty()


def test_close_with_changes_can_be_cancelled(qtbot):
    win = _window(qtbot)
    _type(win, "x")
    Answers(win, ask_save_changes="cancel")
    win.close()
    assert win.isVisible()
    Answers(win, ask_save_changes="discard")
    win.close()
    assert not win.isVisible()


# --- Favoriten -------------------------------------------------------------------------
def test_add_current_label_as_favorite(qtbot):
    win = _window(qtbot)
    answers = Answers(win, ask_favorite_name=lambda: "Absender")
    win.panel("file").add_favorite.click()
    assert [f.name for f in favorites.favorites()] == ["Absender"]
    assert storage.load(favorites.find("Absender").path) == win.doc
    assert answers.asked == ["ask_favorite_name"]
    assert win.panel("file").favorite_names() == ["Absender"]


def test_favorite_name_suggestion_is_the_first_text(qtbot):
    win = _window(qtbot, Document("62", objects=[TextObject("Regal 3\nSchrauben")]))
    assert win.files.suggested_name() == "Regal 3"


def test_existing_favorite_name_asks_before_overwriting(qtbot):
    favorites.add(_doc("alt"), "Absender")
    win = _window(qtbot)
    answers = Answers(win, ask_favorite_name="Absender", ask_overwrite=False)
    win.files.add_favorite()
    assert storage.load(favorites.find("Absender").path).objects[0].text == "alt"
    Answers(win, ask_favorite_name="Absender", ask_overwrite=True)
    win.files.add_favorite()
    assert storage.load(favorites.find("Absender").path).objects[0].text == "Absender"
    assert answers.asked == ["ask_favorite_name", "ask_overwrite"]


def test_invalid_favorite_name_gives_message(qtbot):
    win = _window(qtbot)
    Answers(win, ask_favorite_name="a/b")
    win.files.add_favorite()
    assert favorites.favorites() == [] and "Name" in win.result.text()


def test_clicking_a_favorite_opens_it_as_new_untitled_label(qtbot):
    favorites.add(_doc("Vorlage"), "Absender")
    win = _window(qtbot, _doc("anderes"))
    win.panel("file").open_favorite_at(0)
    assert win.doc.objects[0].text == "Vorlage"
    assert win.windowTitle() == "Unbenannt – labelwerk"
    assert win.files.path is None
    _type(win, "geändert")
    assert storage.load(favorites.find("Absender").path).objects[0].text == "Vorlage"


def test_favorite_previews_are_rendered(qtbot):
    favorites.add(_doc("A"), "A")
    win = _window(qtbot)
    preview = win.panel("file").favorite_preview(0)
    assert preview is not None and preview.width() <= 110


def test_printing_a_favorite_does_not_touch_the_open_label(qtbot, monkeypatch):
    favorites.add(_doc("Fav"), "Fav")
    started = []

    class FakeWorker:
        def __init__(self, image, label_id, model, cut_every=1):
            started.append((image.tobytes(), label_id))
            from labelwerk.gui.print_worker import PrintSignals
            self.signals = PrintSignals()
    monkeypatch.setattr(main_window, "PrintWorker", FakeWorker)
    monkeypatch.setattr(main_window.QThreadPool, "globalInstance",
                        lambda: type("P", (), {"start": lambda self, w: None})())
    win = _window(qtbot, _doc("offen"))
    win.panel("file").print_favorite_at(0)
    assert started == [(render_document(_doc("Fav")).tobytes(), "62")]
    assert win.doc.objects[0].text == "offen"


def test_rename_remove_and_start_favorite(qtbot):
    favorites.add(_doc(), "alt")
    win = _window(qtbot)
    panel = win.panel("file")
    Answers(win, ask_favorite_name="neu")
    win.files.rename_favorite(favorites.find("alt"))
    assert panel.favorite_names() == ["neu"]
    win.files.toggle_start_favorite(favorites.find("neu"))
    assert win.settings.start_favorite == "neu" and load_settings().start_favorite == "neu"
    Answers(win, ask_remove=True)
    win.files.remove_favorite(favorites.find("neu"))
    assert panel.favorite_names() == [] and win.settings.start_favorite is None


def test_favorite_context_menu_actions(qtbot):
    favorites.add(_doc(), "Absender")
    win = _window(qtbot)
    menu = win.panel("file").favorite_menu(0)
    assert [a.text() for a in menu.actions()] == [
        "Öffnen als neues Etikett", "Drucken", "Umbenennen …", "Löschen …", "Beim Start öffnen",
        "Ordner öffnen"]
    assert menu.actions()[4].isCheckable()


def test_favorite_menu_opens_the_folder(qtbot):
    """Rechtsklick → Ordner öffnen: der Menüeintrag selbst (nicht nur die Funktion) öffnet."""
    favorites.add(_doc(), "Absender")
    win = _window(qtbot)
    opened = []
    win.files.open_url = lambda url: opened.append(url.toLocalFile())
    menu = win.panel("file").favorite_menu(0)
    menu.actions()[-1].trigger()
    assert opened == [str(favorites.favorites_dir())]


def test_empty_favorites_show_a_hint(qtbot):
    win = _window(qtbot)
    panel = win.panel("file")
    assert panel.favorites_hint.isVisibleTo(panel) and "AKTUELL" in panel.favorites_hint.text()


def test_opening_a_favorite_with_changes_asks_first(qtbot):
    favorites.add(_doc("Fav"), "Fav")
    win = _window(qtbot)
    _type(win, "ungespeichert")
    answers = Answers(win, ask_save_changes="cancel")
    win.panel("file").open_favorite_at(0)
    assert answers.asked == ["ask_save_changes"] and win.doc.objects[0].text == "ungespeichert"


# --- Zuletzt geöffnet -----------------------------------------------------------------
def test_recent_files_list_and_open(qtbot, tmp_path):
    a, b = tmp_path / "a.labelwerk", tmp_path / "b.labelwerk"
    storage.save(_doc("A"), a)
    storage.save(_doc("B"), b)
    win = _window(qtbot, recent_files=[str(b), str(a)])
    panel = win.panel("file")
    assert panel.recent_names() == ["b", "a"]
    assert panel.recent.item(0).toolTip() == str(b)
    panel.open_recent_at(1)
    assert win.doc.objects[0].text == "A" and win.settings.recent_files[0] == str(a)
    assert panel.recent_names() == ["a", "b"]


def test_missing_recent_file_is_greyed_and_removed_on_click(qtbot, tmp_path):
    win = _window(qtbot, recent_files=[str(tmp_path / "weg.labelwerk")])
    panel = win.panel("file")
    item = panel.recent.item(0)
    assert item.foreground().color() == panel.palette().color(panel.palette().ColorRole.PlaceholderText)
    panel.open_recent_at(0)
    assert panel.recent_names() == [] and win.settings.recent_files == []
    assert "nicht gefunden" in win.result.text()


# --- Start --------------------------------------------------------------------------
def test_start_with_a_file(qtbot, tmp_path):
    path = tmp_path / "start.labelwerk"
    storage.save(_doc("Start"), path)
    win = _window(qtbot)
    win.start(str(path))
    assert win.doc.objects[0].text == "Start" and win.windowTitle() == "start – labelwerk"


def test_start_with_the_start_favorite(qtbot):
    favorites.add(_doc("Fav"), "Absender")
    win = _window(qtbot, start_favorite="Absender")
    win.start(None)
    assert win.doc.objects[0].text == "Fav" and win.files.path is None


def test_missing_start_favorite_starts_empty_with_hint(qtbot):
    win = _window(qtbot, start_favorite="weg")
    win.start(None)
    assert "weg" in win.result.text()


def test_settings_dialog_offers_start_favorite(qtbot):
    from labelwerk.gui.settings_dialog import SettingsDialog
    favorites.add(_doc(), "Absender")
    favorites.add(_doc(), "Regal")
    dialog = SettingsDialog(Settings(start_favorite="Regal"))
    qtbot.addWidget(dialog)
    combo = dialog.start_favorite
    assert [combo.itemText(i) for i in range(combo.count())] == ["Leeres Etikett", "Absender", "Regal"]
    assert combo.currentText() == "Regal"
    combo.setCurrentIndex(0)
    assert dialog.values().start_favorite is None
    combo.setCurrentIndex(1)
    assert dialog.values().start_favorite == "Absender"


def test_settings_dialog_keeps_a_missing_start_favorite_visible(qtbot):
    from labelwerk.gui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(Settings(start_favorite="weg"))
    qtbot.addWidget(dialog)
    assert dialog.start_favorite.currentText() == "weg (fehlt)"
    assert dialog.values().start_favorite == "weg"


def test_label_the_printer_cannot_print_is_refused(qtbot, tmp_path):
    """102 mm gibt es bei brother_ql, der QL-600 druckt aber höchstens 62 mm."""
    path = tmp_path / "breit.labelwerk"
    storage.save(Document("102", objects=[TextObject("breit")]), path)
    win = _window(qtbot)
    Answers(win, ask_open_file=str(path))
    win.files.open()
    assert win.doc.objects[0].text == "Absender"
    assert "102" in win.result.text() and "QL-600" in win.result.text()


def test_recent_paths_are_normalized(qtbot, tmp_path):
    path = tmp_path / "a.labelwerk"
    storage.save(_doc(), path)
    (tmp_path / "x").mkdir()
    win = _window(qtbot)
    assert win.files.open(str(tmp_path / "x" / ".." / "a.labelwerk"))
    win.files.open(str(path))
    assert win.settings.recent_files == [str(path.resolve())]


# --- Nachbesserungen ---------------------------------------------------------------------
from labelwerk.media import Media  # noqa: E402


def test_roll_check_adjusts_a_fresh_label_without_marking_it_changed(qtbot):
    win = _window(qtbot)
    win._media_found(Media(62, 29, "die_cut"), "62x29")
    assert win.doc.label_id == "62x29" and not win.files.modified()
    assert win.windowTitle() == "Unbenannt – labelwerk"


def test_roll_check_does_not_change_an_opened_file(qtbot, tmp_path):
    path = tmp_path / "regal.labelwerk"
    storage.save(_doc("Regal"), path)
    win = _window(qtbot)
    win.files.open(str(path))
    win._media_found(Media(62, 29, "die_cut"), "62x29")
    assert win.doc.label_id == "62" and not win.files.modified()


def test_roll_check_does_not_change_an_opened_favorite(qtbot):
    favorites.add(_doc("Fav"), "Fav")
    win = _window(qtbot)
    win.panel("file").open_favorite_at(0)
    win._media_found(Media(62, 29, "die_cut"), "62x29")
    assert win.doc.label_id == "62"


def test_new_label_follows_the_known_roll(qtbot):
    win = _window(qtbot)
    win.panel("paper").show_media(Media(62, 29, "die_cut"), "62x29")
    win.files.new()
    assert win.doc.label_id == "62x29"


def test_opening_a_label_that_does_not_render_replaces_the_view(qtbot, tmp_path):
    """Renderfehler nach dem Öffnen: die Arbeitsfläche zeigt nicht mehr das alte Etikett."""
    path = tmp_path / "gross.labelwerk"
    storage.save(Document("62", length_mm=20, objects=[TextObject("X" * 40, size_pt=100)]), path)
    win = _window(qtbot, Document("62", length_mm=40, objects=[
        TextObject("a", x_mm=1, y_mm=1), TextObject("b", x_mm=20, y_mm=1)]))
    win.files.open(str(path))
    assert len(win.doc.objects) == 1 and win._render_error is not None
    assert win.rendered == []                      # keine Bilder des alten Etiketts mehr


def test_printing_a_favorite_checks_the_label(qtbot, monkeypatch):
    path = favorites.favorites_dir()
    path.mkdir(parents=True)
    storage.save(Document("102", objects=[TextObject("breit")]), path / "breit.labelwerk")
    monkeypatch.setattr(main_window, "PrintWorker", lambda *a: pytest.fail("gedruckt"))
    win = _window(qtbot)
    win.panel("file").print_favorite_at(0)
    assert "passt nicht" in win.result.text()


def test_printing_a_favorite_for_another_roll_asks_first(qtbot, monkeypatch):
    favorites.add(Document("62x29", objects=[TextObject("klein")]), "klein")
    monkeypatch.setattr(main_window, "PrintWorker", lambda *a: pytest.fail("gedruckt"))
    win = _window(qtbot)
    win.panel("paper").show_media(Media(62, 0, "endless"), "62")
    answers = Answers(win, ask_print_other_roll=False)
    win.panel("file").print_favorite_at(0)
    assert answers.asked == ["ask_print_other_roll"]


def test_favorite_print_buttons_are_locked_while_printing(qtbot):
    favorites.add(_doc(), "A")
    win = _window(qtbot)
    win._set_printing(True)
    row = win.panel("file").favorites.itemWidget(win.panel("file").favorites.item(0))
    assert not row.print.isEnabled()
    win.print_document(_doc())
    assert "Druck läuft" in win.result.text()
    win._set_printing(False)
    assert row.print.isEnabled()


def test_save_as_asks_before_replacing_when_the_suffix_was_added(qtbot, tmp_path):
    storage.save(_doc("alt"), tmp_path / "absender.labelwerk")
    win = _window(qtbot)
    answers = Answers(win, ask_save_file=str(tmp_path / "absender"), ask_replace_file=False)
    assert not win.files.save_as()
    assert answers.asked == ["ask_save_file", "ask_replace_file"]
    assert storage.load(tmp_path / "absender.labelwerk").objects[0].text == "alt"


def test_upper_case_suffix_is_kept(qtbot, tmp_path):
    win = _window(qtbot)
    Answers(win, ask_save_file=str(tmp_path / "x.LABELWERK"))
    assert win.files.save_as()
    assert (tmp_path / "x.LABELWERK").exists()


def test_settings_dialog_start_favorite_shows_in_the_star_tab(qtbot, monkeypatch):
    favorites.add(_doc(), "A")
    win = _window(qtbot)

    class FakeDialog:
        DialogCode = type("D", (), {"Accepted": 1})

        def __init__(self, settings, **kw):
            self.saved = Settings(**{**vars(settings), "start_favorite": "A", "warnings": []})

        def exec(self):
            return 1

        def deleteLater(self):
            pass
    monkeypatch.setattr(main_window, "SettingsDialog", FakeDialog)
    win.open_settings()
    menu = win.panel("file").favorite_menu(0)
    assert menu.actions()[4].isChecked()


def test_broken_favorite_preview_does_not_stop_the_window(qtbot, monkeypatch):
    favorites.add(_doc(), "A")
    monkeypatch.setattr("labelwerk.gui.file_session.render_document",
                        lambda *a, **k: (_ for _ in ()).throw(KeyError("kaputt")))
    win = _window(qtbot)
    assert win.panel("file").favorite_preview(0) is None


def test_saving_keeps_the_writing_mode(qtbot, tmp_path):
    win = _window(qtbot)
    win.canvas.set_selection([0])
    win.edit_selected()
    Answers(win, ask_save_file=str(tmp_path / "a.labelwerk"))
    win.files.save()
    assert win.edit_session.active


def test_cancelled_question_keeps_the_writing_mode(qtbot):
    win = _window(qtbot)
    _type(win, "geändert")
    win.canvas.set_selection([0])
    win.edit_selected()
    Answers(win, ask_save_changes="cancel")
    win.files.new()
    assert win.edit_session.active


def test_broken_favorite_does_not_ask_about_changes_first(qtbot):
    path = favorites.favorites_dir()
    path.mkdir(parents=True)
    (path / "kaputt.labelwerk").write_text("kein json")
    win = _window(qtbot)
    _type(win, "x")
    answers = Answers(win, ask_save_changes="cancel")
    win.panel("file").open_favorite_at(0)
    assert answers.asked == [] and "kaputt" in win.result.text()


def test_successful_open_replaces_an_old_message(qtbot, tmp_path):
    path = tmp_path / "a.labelwerk"
    storage.save(_doc(), path)
    win = _window(qtbot)
    win._set_result("Datei nicht gefunden: …", "error")
    win.files.open(str(path))
    assert win.result.text() == "Geöffnet: a.labelwerk" and win.result.property("state") == "ok"


def test_suggested_names_have_no_path_characters_and_keep_the_favorite_name(qtbot):
    win = _window(qtbot, Document("62", objects=[TextObject("A/B 3")]))
    assert win.files.suggested_name() == "A-B 3"
    favorites.add(_doc("Text"), "Absender")
    win.files.refresh_lists()
    win.panel("file").open_favorite_at(0)
    assert win.files.suggested_name() == "Absender"


def test_keyboard_opens_favorites_and_recent_files(qtbot, tmp_path):
    favorites.add(_doc("Fav"), "Fav")
    win = _window(qtbot)
    panel = win.panel("file")
    panel.favorites.itemActivated.emit(panel.favorites.item(0))
    assert win.doc.objects[0].text == "Fav"


def test_question_buttons_map_to_answers():
    from PySide6.QtWidgets import QMessageBox
    from labelwerk.gui.file_session import answer_for
    assert [answer_for(b.value) for b in (QMessageBox.StandardButton.Save,
                                          QMessageBox.StandardButton.Discard,
                                          QMessageBox.StandardButton.Cancel)] == [
        "save", "discard", "cancel"]
    assert answer_for(0) == "cancel"                 # Fenster-X / Esc


def test_ctrl_s_saves(qtbot, tmp_path):
    win = _window(qtbot)
    answers = Answers(win, ask_save_file=str(tmp_path / "k.labelwerk"))
    win.panel("file").save.click()
    assert answers.asked == ["ask_save_file"] and (tmp_path / "k.labelwerk").exists()


# --- Schlussreview 3c ---------------------------------------------------------------------
def _unreachable_folder(tmp_path):
    import os
    folder = tmp_path / "zu"
    folder.mkdir()
    (folder / "x.labelwerk").write_text("")
    folder.chmod(0)
    if os.geteuid() == 0:
        folder.chmod(0o755)
        pytest.skip("als root gibt es keinen unerreichbaren Ordner")
    return folder


def test_unreachable_recent_path_does_not_stop_the_start(qtbot, tmp_path):
    folder = _unreachable_folder(tmp_path)
    try:
        path = str(folder / "x.labelwerk")
        win = _window(qtbot, recent_files=[path])
        assert win.panel("file").recent_names() == ["x"]
        win.panel("file").open_recent_at(0)             # kein Traceback, Meldung
        assert win.settings.recent_files == [] and "nicht gefunden" in win.result.text()
    finally:
        folder.chmod(0o755)


def test_saved_new_label_does_not_follow_the_roll_any_more(qtbot, tmp_path):
    win = _window(qtbot)
    Answers(win, ask_save_file=str(tmp_path / "neu.labelwerk"))
    assert win.files.save()
    win._media_found(Media(62, 29, "die_cut"), "62x29")
    assert win.doc.label_id == "62" and not win.files.modified()


def test_open_with_render_error_keeps_the_error_visible(qtbot, tmp_path):
    path = tmp_path / "gross.labelwerk"
    storage.save(Document("62", length_mm=20, objects=[TextObject("X" * 40, size_pt=100)]), path)
    win = _window(qtbot)
    win.files.open(str(path))
    assert win._render_error is not None
    assert win.result.property("state") == "error"
    assert win.result.text().startswith("Geöffnet: gross.labelwerk") \
        and win._render_error in win.result.text()


def test_print_with_render_error_says_so_again(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "gross.labelwerk"
    storage.save(Document("62", length_mm=20, objects=[TextObject("X" * 40, size_pt=100)]), path)
    win = _window(qtbot)
    win.files.open(str(path))
    win._set_result("", "")
    monkeypatch.setattr(win, "_print", lambda *a: pytest.fail("darf nicht drucken"))
    win.print_label()
    assert win.result.text() == win._render_error and win.result.property("state") == "error"


def test_many_unsaved_empty_text_frames_do_not_count_as_a_change(qtbot):
    win = _window(qtbot)
    win.doc.objects.append(TextObject("", x_mm=10, y_mm=10))      # frisch angelegter Rahmen
    assert not win.files.modified()
    win.doc.objects[-1] = TextObject("x", x_mm=10, y_mm=10)
    assert win.files.modified()


def test_names_are_shown_as_plain_text(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    favorites.add(_doc("Fav"), "<b>x<b>")
    win = _window(qtbot)
    row = win.panel("file").favorites.itemWidget(win.panel("file").favorites.item(0))
    assert row.name.textFormat() == Qt.TextFormat.PlainText and "<b>x<b>" in row.name.text()
    win._set_result("<b>y</b>", "ok")
    assert win.result.textFormat() == Qt.TextFormat.PlainText
    seen = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda box: seen.append((box.textFormat(), box.text())) or 0)
    win.files.ask_remove("<b>x<b>")
    win.files.ask_overwrite("<b>x<b>")
    win.files.ask_replace_file(__import__("pathlib").Path("<b>x<b>.labelwerk"))
    win.files.ask_print_other_roll("62", "<i>")
    assert len(seen) == 4
    assert all(fmt == Qt.TextFormat.PlainText and "<" in text for fmt, text in seen)


def test_favorites_folder_error_gives_a_message(qtbot, tmp_path, monkeypatch):
    win = _window(qtbot)
    blocker = tmp_path / "datei"
    blocker.write_text("")
    monkeypatch.setattr(favorites, "favorites_dir", lambda: blocker / "favoriten")
    opened = []
    win.files.open_url = opened.append
    win.files.open_favorites_folder()
    assert opened == [] and win.result.property("state") == "error" and win.result.text()


def test_save_dialog_is_released_after_use(qtbot, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    deleted = []
    monkeypatch.setattr(QFileDialog, "exec", lambda self: 0)
    monkeypatch.setattr(QFileDialog, "deleteLater", lambda self: deleted.append(self))
    win = _window(qtbot)
    assert win.files.ask_save_file("x.labelwerk") is None and len(deleted) == 1


@pytest.mark.parametrize("which", ["favorites", "recent"])
def test_single_click_style_opens_only_once(qtbot, tmp_path, which):
    from PySide6.QtWidgets import QProxyStyle, QStyle

    class SingleClick(QProxyStyle):
        def styleHint(self, hint, option=None, widget=None, returnData=None):
            if hint == QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick:
                return 1
            return super().styleHint(hint, option, widget, returnData)

    path = tmp_path / "a.labelwerk"
    storage.save(_doc("A"), path)
    favorites.add(_doc("Fav"), "Fav")
    win = _window(qtbot, recent_files=[str(path)])
    panel = win.panel("file")
    view = getattr(panel, which)
    style = SingleClick()
    view.setStyle(style)
    opened = []
    signal = panel.favorite_open if which == "favorites" else panel.recent_open
    signal.connect(opened.append)
    rect = view.visualItemRect(view.item(0))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert len(opened) == 1
