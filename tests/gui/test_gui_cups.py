"""CUPS queues in the GUI: printer menu, labels of the driver, cut options in the SERIES tab
(saved per printer), handing over to the queue."""
import pytest

from labelwerk import cups
from labelwerk.document import Document, Numbering, Series, TextObject
from labelwerk.gui import main_window
from labelwerk.settings import load_settings

from test_gui_printers import QL600, _labels, _window, workers  # noqa: F401  (Fixture)

OPTIONS = ("PageSize/Media Size: *w162h90 w154h64.8\n"
           "CutMedia/Schneiden: *Off EndOfJob EndOfPage\n")


@pytest.fixture
def queue(monkeypatch):
    """Queue “Dymo” (driver with cut option) and “Laser” (without)."""
    def run(*args, **kw):
        if args[0] == "lpstat":
            return ("Dymo\nLaser\n" if args[1] == "-e" else
                    "device for Dymo: usb://DYMO/LabelWriter%20450\n"
                    "device for Laser: ipp://10.0.0.7/ipp/print\n")
        if args[0] == "lpoptions":
            return OPTIONS if args[2] == "Dymo" else "PageSize/Media Size: *w162h90\n"
        return ""
    monkeypatch.setattr(cups, "_run", run)


def test_queues_appear_in_the_printer_menu(qtbot, monkeypatch, queue):
    win = _window(qtbot, monkeypatch, [QL600])
    win._fill_printer_menu()
    texts = [a.text() for a in win.printer_menu.actions() if a.text()]
    assert texts[1:4] == ["QL-600 · lp1", "Dymo · CUPS – ungeprüft", "Laser · CUPS – ungeprüft"]
    assert win.printer.uri == QL600.uri                      # Brother direct first
    win.choose_printer("cups:Dymo")
    assert win.model == "cups:Dymo" and load_settings().printer == "cups:Dymo"
    assert _labels(win) == ["57.1x31.7mm@300", "54.3x22.9mm@300"]
    assert win.printer_status.text() == "● Dymo · CUPS · ungeprüft"
    assert not win.panel("paper").check.isEnabled()          # Check media only for Brother via USB


def test_driver_cut_options_in_the_series_tab(qtbot, monkeypatch, queue):
    win = _window(qtbot, monkeypatch, [], printer="cups:Dymo")
    panel = win.panel("series")
    assert panel.cut.isHidden() and not panel.driver_box.isHidden()
    combo = panel.driver_cuts["CutMedia"]
    assert [combo.itemText(i) for i in range(combo.count())] == ["Off", "EndOfJob", "EndOfPage"]
    assert combo.currentText() == "Off"                      # driver default
    combo.setCurrentIndex(2)
    assert load_settings().printer_options == {"cups:Dymo": {"CutMedia": "EndOfPage"}}
    win.choose_printer("cups:Laser")                         # driver without cut option
    assert panel.driver_box.isHidden() and "Druckertreiber" in panel.no_cutter.text()
    win.choose_printer("cups:Dymo")
    assert panel.driver_cuts["CutMedia"].currentText() == "EndOfPage"


def test_brother_after_cups_shows_its_cut_choice_again(qtbot, monkeypatch, queue):
    win = _window(qtbot, monkeypatch, [QL600], printer="cups:Dymo")
    win.choose_printer(QL600.uri)
    panel = win.panel("series")
    assert not panel.cut.isHidden() and panel.driver_box.isHidden() and panel.no_cutter.isHidden()


def test_series_goes_to_the_queue_with_the_chosen_options(qtbot, monkeypatch, queue, workers):
    win = _window(qtbot, monkeypatch, [], printer="cups:Dymo", doc=Document(
        "57.1x31.7mm@300", objects=[TextObject("X{Nummer}")],
        series=Series(numbering=Numbering(count=3))),
        printer_options={"cups:Dymo": {"CutMedia": "EndOfJob"}})
    win.panel("series").refresh()
    win.ask_print_count = lambda n: True
    win.print_label()
    worker = workers[0]
    assert (worker.printer, worker.model) == ("cups:Dymo", "cups:Dymo")
    assert worker.options == {"CutMedia": "EndOfJob"} and len(worker.image) == 3
    assert worker.image[0].size == (674, 374)
    assert win.cancel_button.isHidden()                      # one job: nothing to cancel
    win._print_done({"outcome": "sent", "did_print": False, "job": "Dymo-4"})
    assert win.result.text() == "An die Druckwarteschlange übergeben ✓ (Auftrag Dymo-4)"


def test_settings_keep_cups_printer_options(qtbot, tmp_path):
    from labelwerk.gui.settings_dialog import SettingsDialog
    from labelwerk.settings import Settings
    dialog = SettingsDialog(Settings(printer_options={"cups:Dymo": {"CutMedia": "Off"}}))
    qtbot.addWidget(dialog)
    assert dialog.values().printer_options == {"cups:Dymo": {"CutMedia": "Off"}}


def test_queues_are_never_chosen_automatically(qtbot, monkeypatch, queue):
    win = _window(qtbot, monkeypatch, [], last_model="QL-600")
    assert win.printer is None and win.model == "QL-600"     # office printers on the network stay off
    assert "cups:Dymo" in [p.uri for p in win.printers]
    assert load_settings().last_model in ("", "QL-600")


@pytest.fixture
def office(monkeypatch):
    """“Dymo” (labels) and “Buero” (A4/Letter, an office printer)."""
    def run(*args, **kw):
        if args[0] == "lpstat":
            return ("Dymo\nBuero\n" if args[1] == "-e" else
                    "device for Dymo: usb://DYMO/LabelWriter%20450\n"
                    "device for Buero: ipp://10.0.0.7/ipp/print\n")
        if args[0] == "lpoptions":
            return OPTIONS if args[2] == "Dymo" else "PageSize/Media Size: Letter *A4\n"
        return ""
    monkeypatch.setattr(cups, "_run", run)


def _menu(win):
    win._fill_printer_menu()
    return [a.text() for a in win.printer_menu.actions() if a.text()]


def test_office_printers_are_hidden_in_the_menu(qtbot, monkeypatch, office):
    win = _window(qtbot, monkeypatch, [QL600])
    assert "Dymo · CUPS – ungeprüft" in _menu(win)
    assert not any("Buero" in t for t in _menu(win))


def test_office_printers_with_the_setting(qtbot, monkeypatch, office):
    win = _window(qtbot, monkeypatch, [QL600], cups_all=True)
    assert "Buero · CUPS – ungeprüft" in _menu(win)


def test_chosen_office_printer_stays_in_the_menu(qtbot, monkeypatch, office):
    win = _window(qtbot, monkeypatch, [QL600], printer="cups:Buero")
    assert "Buero · CUPS – ungeprüft" in _menu(win) and win.printer.uri == "cups:Buero"


def test_show_all_cups_printers_in_the_settings(qtbot, tmp_path):
    from labelwerk.gui.settings_dialog import SettingsDialog
    from labelwerk.settings import Settings
    path = tmp_path / "s.json"
    dialog = SettingsDialog(Settings(), path)
    qtbot.addWidget(dialog)
    assert not dialog.cups_all.isChecked()
    dialog.cups_all.setChecked(True)
    dialog.accept()
    assert load_settings(path).cups_all is True
