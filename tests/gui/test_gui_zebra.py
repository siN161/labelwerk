"""Zebra direkt (ZPL) in der GUI: Druckermenü, Etiketten in seiner Auflösung, Modus im Reiter SERIE
(je Drucker gespeichert), Netzwerk-Zebra in den Einstellungen, Druck mit Modus."""
from PySide6.QtWidgets import QTableWidgetItem

from labelwerk.document import Document, Numbering, Series, TextObject
from labelwerk.gui import main_window
from labelwerk.gui.settings_dialog import SettingsDialog
from labelwerk.printers import Printer
from labelwerk.settings import Settings, load_settings

from test_gui_printers import QL600, _labels, _window, workers  # noqa: F401  (Fixture)

ZEBRA = Printer("zpl+file:///dev/usb/lp2", "zpl:300", "ZTC ZD420-300dpi · lp2", "zebra")
L57 = "57x32mm@305"                                       # 300 dpi = 12 Punkte/mm


def _zebra_window(qtbot, monkeypatch, found=(ZEBRA,), **kw):
    monkeypatch.setattr(main_window, "zebra_printers", lambda **kw: list(found))
    return _window(qtbot, monkeypatch, [], **kw)


def test_zebra_is_chosen_and_brings_its_labels(qtbot, monkeypatch):
    win = _zebra_window(qtbot, monkeypatch)
    assert win.printer.uri == ZEBRA.uri and win.model == "zpl:300"
    assert _labels(win)[:2] == ["51x25mm@305", L57]
    assert win.doc.label_id == "51x25mm@305"                  # neues Etikett folgt dem Drucker
    assert win.printer_status.text() == "● ZTC ZD420-300dpi · lp2 · ungeprüft"
    assert not win.panel("paper").check.isEnabled()
    assert win.canvas.dpi == 305


def test_brother_comes_before_zebra(qtbot, monkeypatch):
    monkeypatch.setattr(main_window, "zebra_printers", lambda **kw: [ZEBRA])
    win = _window(qtbot, monkeypatch, [QL600])
    assert win.printer.uri == QL600.uri
    win._fill_printer_menu()
    texts = [a.text() for a in win.printer_menu.actions() if a.text()]
    assert texts[1:3] == ["QL-600 · lp1", "ZTC ZD420-300dpi · lp2 – ungeprüft"]


def test_mode_in_the_series_tab(qtbot, monkeypatch):
    win = _zebra_window(qtbot, monkeypatch)
    panel = win.panel("series")
    combo = panel.driver_cuts["mode"]
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Wie am Drucker eingestellt", "Abreißen", "Schneiden (nur mit Abschneider)",
        "Ablösen (nur mit Spender)"]
    assert combo.currentData() == ""                          # sendet kein ^MM
    combo.setCurrentIndex(2)
    assert load_settings().printer_options == {"zpl:300": {"mode": "C"}}   # je Modell, nicht lpN


def test_series_to_zebra_with_its_mode(qtbot, monkeypatch, workers):
    win = _zebra_window(qtbot, monkeypatch, doc=Document(
        L57, objects=[TextObject("X{Nummer}")], series=Series(numbering=Numbering(count=2))),
        printer_options={"zpl:300": {"mode": "P"}})
    win.panel("series").refresh()
    win.ask_print_count = lambda n: True
    win.print_label()
    worker = workers[0]
    assert (worker.printer, worker.model, worker.options) == (ZEBRA.uri, "zpl:300", {"mode": "P"})
    assert worker.image[0].size == (684, 384) and win.cancel_button.isHidden()


def test_network_zebra_in_the_settings(qtbot, tmp_path):
    path = tmp_path / "s.json"
    dialog = SettingsDialog(Settings(), path)
    qtbot.addWidget(dialog)
    dialog.add_network.click()
    dialog.network.setItem(0, 0, QTableWidgetItem("Lager"))
    dialog.network.setItem(0, 1, QTableWidgetItem("10.0.0.8"))
    combo = dialog.network.cellWidget(0, 2)
    assert combo.findText("Zebra (ZPL) 203 dpi – ungeprüft") >= 0
    assert dialog.printer_model.findData("zpl:203") < 0            # Ersatzmodell: nur Brother
    combo.setCurrentIndex(combo.findData("zpl:203"))
    dialog.accept()
    assert load_settings(path).network_printers == [
        {"name": "Lager", "host": "10.0.0.8", "model": "zpl:203"}]


def test_zebra_resolution_in_the_settings(qtbot, tmp_path):
    path = tmp_path / "s.json"
    dialog = SettingsDialog(Settings(), path)
    qtbot.addWidget(dialog)
    dialog.zebra_dpi.setCurrentIndex(dialog.zebra_dpi.findData(300))
    dialog.accept()
    assert load_settings(path).zebra_dpi == 300


def test_zebra_resolution_setting_is_used(qtbot, monkeypatch):
    seen = {}
    monkeypatch.setattr(main_window, "zebra_printers", lambda **kw: seen.update(kw) or [])
    _window(qtbot, monkeypatch, [], zebra_dpi=600)
    assert seen == {"dpi": 600}
