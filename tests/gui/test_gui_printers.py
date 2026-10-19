"""Drucker-Kompatibilität in der GUI: Druckerwahl in der Statusleiste, Modellwechsel (Etiketten,
Schnitt, Farbe), Netzwerkdrucker, Einstellungen, Farbe in Layout, Druck an den gewählten Drucker."""
import pytest
from PySide6.QtWidgets import QTableWidgetItem

from labelwerk.document import Document, Numbering, Series, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.main_window import MainWindow
from labelwerk.gui.print_worker import PrintSignals
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.printers import Printer
from labelwerk.settings import Settings, load_settings

QL600 = Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")
QL500 = Printer("file:///dev/usb/lp2", "QL-500", "QL-500 · lp2")
QL820 = Printer("file:///dev/usb/lp3", "QL-820NWB", "QL-820NWB · lp3")
QL1100 = Printer("file:///dev/usb/lp4", "QL-1100", "QL-1100 · lp4")
UNKNOWN = Printer("file:///dev/usb/lp0", None, "Brother-Drucker · lp0")


def _window(qtbot, monkeypatch, found=(), doc=None, **settings):
    monkeypatch.setattr(main_window, "usb_printers", lambda: list(found))
    win = MainWindow(doc=doc if doc is not None else Document("62", objects=[TextObject("A")]),
                     settings=Settings(check_media_on_start=False, **settings))
    qtbot.addWidget(win)
    win.show()
    win.render_now()
    return win


def _labels(win):
    combo = win.panel("paper").combo
    return [combo.itemData(i) for i in range(combo.count()) if combo.itemData(i)]


class FakeWorker:
    instances = []

    def __init__(self, image, label_id, model, cut_every=1, printer=None):
        self.image, self.label_id, self.model, self.printer = image, label_id, model, printer
        self.cut_every = cut_every
        self.signals = PrintSignals()
        FakeWorker.instances.append(self)


@pytest.fixture
def workers(monkeypatch):
    FakeWorker.instances = []
    monkeypatch.setattr(main_window, "PrintWorker", FakeWorker)
    monkeypatch.setattr(main_window.QThreadPool.globalInstance(), "start", lambda worker: None)
    return FakeWorker.instances


# --- Erkennen und wählen --------------------------------------------------------------------------
def test_detected_model_drives_labels_and_is_remembered(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL1100])
    assert win.model == "QL-1100" and "102" in _labels(win)
    assert win.printer_status.text() == "● QL-1100 · lp4 · ungeprüft"
    assert "Rückmeldung erwünscht" in win.printer_status.toolTip()
    assert win.settings.last_model == "QL-1100"
    assert load_settings().last_model == "QL-1100"                 # gespeichert


def test_tested_model_has_no_marker(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL600])
    assert win.printer_status.text() == "● QL-600 · lp1" and win.model == "QL-600"
    assert "102" not in _labels(win)


def test_without_printer_the_last_model_counts(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [], last_model="QL-820NWB")
    assert win.model == "QL-820NWB" and "62red" in _labels(win)
    assert win.printer_status.text() == "○ kein Drucker"


def test_unknown_model_uses_the_fallback(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [UNKNOWN], printer_model="QL-700")
    assert win.model == "QL-700"
    assert win.printer_status.text() == "● Brother-Drucker · lp0 (als QL-700)"


def test_menu_lists_printers_and_choosing_one_is_saved(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL600, QL1100])
    assert win.printer is not None and win.printer.uri == QL600.uri
    win._fill_printer_menu()
    texts = [a.text() for a in win.printer_menu.actions() if a.text()]
    assert texts[:3] == ["Automatisch (erster gefundener)", "QL-600 · lp1",
                         "QL-1100 · lp4 – ungeprüft"]
    assert texts[-1] == "Netzwerkdrucker eintragen …"
    next(a for a in win.printer_menu.actions() if a.text().startswith("QL-1100")).trigger()
    assert win.printer.uri == QL1100.uri and win.model == "QL-1100"
    assert load_settings().printer == QL1100.uri
    win.choose_printer("")
    assert win.printer.uri == QL600.uri


def test_network_printer_from_the_settings(qtbot, monkeypatch, workers):
    win = _window(qtbot, monkeypatch, [], network_printers=[
        {"name": "Büro", "host": "10.0.0.5", "model": "QL-720NW"}])
    assert win.printer.uri == "tcp://10.0.0.5:9100" and win.model == "QL-720NW"
    assert not win.panel("paper").check.isEnabled()                   # Medium prüfen nur USB
    assert "nur bei Druckern per USB" in win.panel("paper").check.toolTip()
    win.panel("text").edit.setPlainText("Hallo")
    win.print_label()
    assert workers[0].printer == "tcp://10.0.0.5:9100" and workers[0].model == "QL-720NW"


def test_network_status_says_sent(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [])
    win._print_done({"outcome": "sent", "did_print": False})
    assert win.result.text() == "Gesendet ✓ (der Drucker meldet keinen Status zurück)"


# --- Modellwechsel -------------------------------------------------------------------------------
def test_label_that_does_not_fit_stays_with_a_hint(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL1100], doc=Document("102", objects=[TextObject("A")]))
    win.files.origin = "file"                        # geöffnete Datei: bleibt bei ihrem Etikett
    found = [QL600]
    monkeypatch.setattr(main_window, "usb_printers", lambda: found)
    win.refresh_printer()
    assert win.model == "QL-600" and win.doc.label_id == "102"
    combo = win.panel("paper").combo
    assert combo.currentData() == "102" and "passt nicht zum QL-600" in combo.currentText()
    assert "passt nicht zum Drucker (QL-600)" in win.result.text()


def test_printer_without_cutter_hides_the_cut_choice(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL500])
    panel = win.panel("series")
    assert panel.cut.isHidden() and not panel.no_cutter.isHidden()
    win2 = _window(qtbot, monkeypatch, [QL600])
    assert not win2.panel("series").cut.isHidden() and win2.panel("series").no_cutter.isHidden()


def test_fixed_model_is_not_replaced(qtbot, monkeypatch):
    monkeypatch.setattr(main_window, "usb_printers", lambda: [QL1100])
    win = MainWindow(doc=Document("62"), model="QL-600",
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    assert win.model == "QL-600"


# --- Farbe ---------------------------------------------------------------------------------------
def test_color_buttons_need_a_red_label_on_a_two_color_printer(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL600])
    win.canvas.set_selection([0])
    layout = win.panel("layout")
    assert not layout.colors["red"].isEnabled() and "62 mm Rot/Schwarz" in layout.colors["red"].toolTip()
    win2 = _window(qtbot, monkeypatch, [QL820],
                   doc=Document("62red", objects=[TextObject("A", size_pt=20, x_mm=2, y_mm=2)]))
    win2.canvas.set_selection([0])
    layout = win2.panel("layout")
    assert layout.colors["red"].isEnabled()
    layout.colors["red"].click()
    assert win2.doc.objects[0].color == "red" and win2.rendered[0].color == "red"
    assert (255, 0, 0) in {c for _, c in win2.image.getcolors(1 << 20)}
    win2.undo()
    assert win2.doc.objects[0].color == "black"


def test_red_series_keeps_red(qtbot, monkeypatch, workers):
    obj = TextObject("X{Nummer}", size_pt=20, x_mm=2, y_mm=2)
    obj.color = "red"
    win = _window(qtbot, monkeypatch, [QL820], doc=Document(
        "62red", objects=[obj], series=Series(numbering=Numbering(count=2))))
    win.panel("series").refresh()
    win.ask_print_count = lambda n: True
    win.print_label()
    images = workers[0].image
    assert all(img.mode == "RGB" and (255, 0, 0) in {c for _, c in img.getcolors(1 << 20)}
               for img in images)


# --- Einstellungen -------------------------------------------------------------------------------
def test_settings_dialog_edits_model_fallback_and_network_printers(qtbot, tmp_path):
    path = tmp_path / "s.json"
    dialog = SettingsDialog(Settings(printer="tcp://1.2.3.4:9100", last_model="QL-700",
                                     network_printers=[{"name": "Alt", "host": "1.2.3.4",
                                                        "model": "QL-710W"}]), path)
    qtbot.addWidget(dialog)
    assert dialog.network.rowCount() == 1
    dialog.printer_model.setCurrentIndex(dialog.printer_model.findData("QL-570"))
    dialog.add_network.click()
    dialog.network.setItem(1, 0, QTableWidgetItem("Lager"))
    dialog.network.setItem(1, 1, QTableWidgetItem("drucker.lan"))
    dialog.accept()
    saved = load_settings(path)
    assert saved.printer_model == "QL-570" and saved.last_model == "QL-700"
    assert saved.printer == "tcp://1.2.3.4:9100"
    assert saved.network_printers == [{"name": "Alt", "host": "1.2.3.4", "model": "QL-710W"},
                                      {"name": "Lager", "host": "drucker.lan",
                                       "model": "QL-720NW"}]


def test_settings_dialog_rejects_a_bad_address(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    dialog.add_network.click()
    dialog.network.setItem(0, 1, QTableWidgetItem("tcp://10.0.0.5:9100"))
    dialog.accept()
    assert dialog.saved is None and "Adresse „tcp://10.0.0.5:9100“ ungültig" in dialog.error.text()
    assert not (tmp_path / "s.json").exists()


def test_untested_models_are_marked_in_the_settings(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    items = [dialog.printer_model.itemText(i) for i in range(dialog.printer_model.count())]
    assert items[0] == "Automatisch (erkannt)" and "QL-600" in items and "QL-700 – ungeprüft" in items


# --- Nachbesserungen nach dem Review --------------------------------------------------------------
def test_new_untouched_label_follows_the_printer(qtbot, monkeypatch):
    monkeypatch.setattr(main_window, "usb_printers", lambda: [QL600])
    win = MainWindow(settings=Settings(check_media_on_start=False, label_id="102"))
    qtbot.addWidget(win)
    assert win.doc.label_id == "62" and not win.files.modified()
    assert "passt nicht zum QL-600 – 62 mm endlos genommen" in win.result.text()
    win.files.new()
    assert win.doc.label_id == "62"


def test_switching_usb_printers_forgets_the_roll(qtbot, monkeypatch):
    from labelwerk.media import Media
    win = _window(qtbot, monkeypatch, [QL1100, QL600])
    win.panel("paper").show_media(Media(102, 0, "endless"), "102")
    win.choose_printer(QL600.uri)
    assert win.panel("paper").media_label is None
    win.files.new()
    assert win.doc.label_id in {label.id for label in __import__(
        "labelwerk.labels", fromlist=["x"]).labels_for_model("QL-600")}


def test_missing_chosen_printer_is_not_replaced(qtbot, monkeypatch, workers):
    win = _window(qtbot, monkeypatch, [QL600], printer=QL1100.uri)
    assert win.printer is None and win.printer_status.text() == "○ gewählter Drucker fehlt"
    win.panel("text").edit.setPlainText("Hallo")
    win.print_label()
    assert workers == [] and "Gewählter Drucker nicht gefunden" in win.result.text()


def test_black_stays_available_and_red_needs_a_two_color_model(qtbot, monkeypatch):
    obj = TextObject("A", size_pt=20, x_mm=2, y_mm=2)
    obj.color = "red"
    win = _window(qtbot, monkeypatch, [QL600], doc=Document("62", objects=[obj]))
    win.files.origin = "file"
    win.canvas.set_selection([0])
    layout = win.panel("layout")
    assert layout.colors["black"].isEnabled() and not layout.colors["red"].isEnabled()
    layout.colors["black"].click()
    assert win.doc.objects[0].color == "black"
    red = _window(qtbot, monkeypatch, [QL600], doc=Document("62red", objects=[TextObject("B")]))
    red.files.origin = "file"
    red.canvas.set_selection([0])
    assert not red.panel("layout").colors["red"].isEnabled()      # 62red, aber QL-600


def test_unfitting_entry_is_not_selectable_and_disappears(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL1100], doc=Document("102", objects=[TextObject("A")]))
    win.files.origin = "file"
    monkeypatch.setattr(main_window, "usb_printers", lambda: [QL600])
    win.refresh_printer()
    combo = win.panel("paper").combo
    index = combo.findData("102")
    assert not combo.model().item(index).isEnabled()
    combo.setCurrentIndex(combo.findData("62"))
    assert win.doc.label_id == "62" and combo.findData("102") < 0


def test_media_button_stays_off_while_checking(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL600])
    win.is_checking_media = lambda: True
    win.refresh_printer()
    assert not win.panel("paper").check.isEnabled()


def test_settings_keep_a_label_of_another_printer(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(label_id="102"), tmp_path / "s.json", model="QL-600")
    qtbot.addWidget(dialog)
    assert dialog.values().label_id == "102"
    assert "passt nicht zum QL-600" in dialog.label.currentText()


def test_remove_without_selection_removes_nothing(qtbot, tmp_path):
    dialog = SettingsDialog(Settings(network_printers=[
        {"name": "A", "host": "1.1.1.1", "model": "QL-710W"},
        {"name": "B", "host": "2.2.2.2", "model": "QL-710W"}]), tmp_path / "s.json")
    qtbot.addWidget(dialog)
    dialog.network.setCurrentCell(-1, -1)
    dialog.remove_network.click()
    assert dialog.network.rowCount() == 2


def test_canvas_length_limits_follow_the_model(qtbot, monkeypatch):
    win = _window(qtbot, monkeypatch, [QL1100])
    assert win.canvas.max_mm == pytest.approx(35434 * 25.4 / 300, abs=0.5)
