"""Drucker über CUPS: nachgebildete Ausgaben von lpstat/lpoptions/lp und PPDs – kein Test ruft
echte Befehle (conftest ersetzt ``cups._run``)."""
import subprocess

import pytest
from PIL import Image

from labelwerk import cups, printers
from labelwerk.labels import get_label, labels_for_model
from labelwerk.printer import PrintError, print_image

REAL_RUN = cups._run                               # vor dem Ersetzen durch conftest

LPSTAT_E = "Dymo_LabelWriter_450\nBuero\nQL600\n"
LPSTAT_V = ("device for Dymo_LabelWriter_450: usb://DYMO/LabelWriter%20450?serial=01010112345600\n"
            "device for Buero: ipp://192.168.1.20/ipp/print\n"
            "device for QL600: usb://Brother/QL-600?serial=000F1Z401370\n")
LPOPTIONS = ("PageSize/Media Size: w79h252 *w154h64.8 30252_Address 99010 w162h90 Custom.WIDTHxHEIGHT\n"
             "Resolution/Output Resolution: 136x136dpi *300x300dpi 300x600dpi\n"
             "DymoCutOptions/Cut: *Cut ChainMarks\n"
             "PrintQuality/Print Quality: Text *Graphics\n")
PPD = """*PPD-Adobe: "4.3"
*ModelName: "DYMO LabelWriter 450"
*DefaultResolution: 300x300dpi
*OpenUI *PageSize/Media Size: PickOne
*PageSize w154h64.8/30252 Address: "<</PageSize[154 64.8]>>setpagedevice"
*CloseUI: *PageSize
*PaperDimension w154h64.8/30252 Address: "154 64.8"
*PaperDimension 99012/99012 Large Address: "102.05 252"
*PaperDimension Tiny/Too small: "5 5"
*PaperDimension w288h432/4 x 6: "288 432"
"""


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """CUPS nachgebildet: Ausgaben je Befehl, aufgezeichnete Aufrufe."""
    calls, outputs = [], {"lpstat -e": LPSTAT_E, "lpstat -v": LPSTAT_V,
                          "lpoptions": LPOPTIONS, "lp": "request id is Dymo_LabelWriter_450-12 (2 file(s))\n"}

    def run(*args, **kw):
        calls.append(args)
        key = " ".join(args[:2]) if args[0] == "lpstat" else args[0]
        out = outputs[key]
        if isinstance(out, Exception):
            raise out
        if args[0] == "lp":                        # PDF: Seitenzahl und Seitengröße in Punkt
            import pypdfium2
            pdf = pypdfium2.PdfDocument(args[-1])
            calls[-1] = args + ((len(pdf), tuple(round(v, 2) for v in pdf[0].get_size())),)
            pdf.close()
        return out
    monkeypatch.setattr(cups, "_run", run)
    monkeypatch.setattr(cups, "PPD_DIR", tmp_path)
    cups.forget()
    return calls, outputs, tmp_path


def test_queues_with_devices(fake):
    calls, _, _ = fake
    found = cups.queues()
    assert [q.name for q in found] == ["Dymo_LabelWriter_450", "Buero", "QL600"]
    assert found[1].device == "ipp://192.168.1.20/ipp/print"


def test_queues_are_read_in_the_background(fake, monkeypatch):
    calls, _, _ = fake
    monkeypatch.setattr(cups, "BACKGROUND", True)
    assert cups.queues() == []                         # die Oberfläche wartet nicht
    cups._queues_thread.join(5)
    assert [q.name for q in cups.queues()][0] == "Dymo_LabelWriter_450"
    assert len(calls) == 2                             # gemerkt, nicht jedes Mal gefragt


def test_localized_output_is_understood(fake):
    _, outputs, _ = fake
    outputs["lpstat -v"] = "Gerät für Buero: ipp://192.168.1.20/ipp/print\n"
    outputs["lp"] = "Anfrage-ID ist Buero-31 (1 Datei(en))\n"
    assert cups.queues()[1].device == "ipp://192.168.1.20/ipp/print"
    label = labels_for_model("cups:Buero")[0]
    status = print_image(Image.new("1", (label.width, label.height), 1), label.id,
                         model="cups:Buero", printer="cups:Buero")
    assert status["job"] == "Buero-31"
    env = cups._environment()
    assert env["LC_MESSAGES"] == "C" and "LC_ALL" not in env and "UTF-8" in env.get(
        "LC_CTYPE", env.get("LANG", "")).upper().replace("UTF8", "UTF-8")


def test_without_device_list_the_queues_stay(fake):
    _, outputs, _ = fake
    outputs["lpstat -v"] = cups.CupsError("kaputt")
    assert [q.device for q in cups.queues()] == ["", "", ""]


def test_cups_failure_is_not_remembered(fake):
    _, outputs, _ = fake
    outputs["lpoptions"] = cups.CupsError("CUPS antwortet nicht (lpoptions)")
    assert cups.queue_info("Dymo_LabelWriter_450").source == "list"
    outputs["lpoptions"] = LPOPTIONS
    assert cups.queue_info("Dymo_LabelWriter_450").source == "options"


def test_no_cups_means_no_queues(fake):
    _, outputs, _ = fake
    outputs["lpstat -e"] = cups.CupsError("CUPS-Befehle fehlen")
    assert cups.queues() == []


def test_media_from_the_ppd(fake):
    _, _, folder = fake
    (folder / "Dymo_LabelWriter_450.ppd").write_text(PPD)
    info = cups.queue_info("Dymo_LabelWriter_450")
    assert info.source == "ppd" and info.dpi == 300
    assert info.media == (("w154h64.8", 54.3, 22.9), ("99012", 36.0, 88.9),
                          ("w288h432", 101.6, 152.4))          # „Tiny“ zu klein: entfällt
    assert info.label_ids() == ["54.3x22.9mm@300", "36x88.9mm@300", "101.6x152.4mm@300"]
    assert info.media_key(36, 88.9) == "99012" and info.media_key(50, 30) == "Custom.50x30mm"


def test_media_from_option_names_without_ppd(fake):
    info = cups.queue_info("Dymo_LabelWriter_450")
    assert info.source == "options" and info.dpi == 300
    assert [m[0] for m in info.media] == ["w79h252", "w154h64.8", "w162h90"]   # Namen ohne Maß entfallen
    assert info.media[0][1:] == (27.9, 88.9)


def test_media_list_per_maker_as_last_resort(fake):
    _, outputs, _ = fake
    outputs["lpoptions"] = "Resolution/Resolution: *203dpi\n"
    info = cups.queue_info("Zebra_GK420d")
    assert info.source == "list" and info.dpi == 203
    assert ("Custom.102x152mm", 102.0, 152.0) in info.media
    assert cups.queue_info("Unbekannt").media[0][1:] == (57.0, 32.0)


@pytest.mark.parametrize("text, dpi", [("*DefaultResolution: 203dpi", 203),
                                       ("*DefaultResolution: 300x600dpi", 300),
                                       ("*DefaultResolution: 4800dpi", 300),     # außerhalb: 300
                                       ("", 300)])
def test_resolution_from_the_ppd(text, dpi):
    assert cups._parse_ppd(text)[0] == dpi


def test_cut_options(fake):
    (cut,) = cups.queue_info("Dymo_LabelWriter_450").cut_options
    assert (cut.key, cut.title, cut.choices, cut.default) == (
        "DymoCutOptions", "Cut", ("Cut", "ChainMarks"), "Cut")


def test_print_one_job_with_all_labels(fake):
    calls, _, folder = fake
    (folder / "Dymo_LabelWriter_450.ppd").write_text(PPD)
    label = get_label("36x88.9mm@300")
    images = [Image.new("1", (label.width, label.height), 1)] * 2
    status = print_image(images, label.id, model="cups:Dymo_LabelWriter_450",
                         printer="cups:Dymo_LabelWriter_450", options={"DymoCutOptions": "ChainMarks"})
    assert status == {"outcome": "sent", "did_print": False, "job": "Dymo_LabelWriter_450-12"}
    lp = calls[-1]
    assert lp[:-3] == ("lp", "-d", "Dymo_LabelWriter_450", "-o", "media=99012",
                       "-o", "print-scaling=none", "-o", "orientation-requested=3",
                       "-o", "fit-to-page=false", "-o", "PageSize=99012",
                       "-o", "DymoCutOptions=ChainMarks")
    assert lp[-3] == "--" and lp[-2].endswith(".pdf")          # ein PDF, eine Seite je Etikett
    pages, size = lp[-1]
    assert pages == 2 and size == (round(label.width * 72 / 300, 2), round(label.height * 72 / 300, 2))


def test_print_errors_are_readable(fake):
    _, outputs, _ = fake
    outputs["lp"] = cups.CupsError("CUPS: lp: The printer or class does not exist.")
    label = labels_for_model("cups:Buero")[0]
    with pytest.raises(PrintError, match="does not exist"):
        print_image(Image.new("1", (label.width, label.height), 1), label.id,
                    model="cups:Buero", printer="cups:Buero")


def test_label_must_fit_the_queue(fake):
    with pytest.raises(PrintError, match="passt nicht"):
        print_image(Image.new("1", (10, 10), 1), "62", model="cups:Buero", printer="cups:Buero")


def test_commands_have_a_time_limit(monkeypatch):
    seen = {}                                      # echtes _run, aber subprocess ersetzt

    def run(args, **kw):
        seen.update(kw)
        raise subprocess.TimeoutExpired(args, kw["timeout"])
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(cups.CupsError, match="antwortet nicht"):
        REAL_RUN("lpstat", "-e")
    assert seen["timeout"] == cups.TIMEOUT_S


def test_missing_commands_and_failures(monkeypatch):
    def missing(args, **kw):
        raise FileNotFoundError(args[0])
    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(cups.CupsError, match="cups-client"):
        REAL_RUN("lp")
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(
        args, 1, "", "lp: Error - The printer or class does not exist.\n"))
    with pytest.raises(cups.CupsError, match="does not exist"):
        REAL_RUN("lp", "-d", "x")


# --- Drucker und Modelle -----------------------------------------------------------------------
def test_queues_are_printers_without_doubling_the_brother(fake):
    direct = [printers.Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1", "usb")]
    names = [p.uri for p in printers.cups_printers(direct)]
    assert names == ["cups:Dymo_LabelWriter_450", "cups:Buero"]
    assert len(printers.cups_printers([])) == 3        # ohne Direktweg auch die Brother-Warteschlange
    p = printers.cups_printers([])[0]
    assert (p.model, p.name, p.source) == ("cups:Dymo_LabelWriter_450",
                                           "Dymo_LabelWriter_450 · CUPS", "cups")


def test_cups_models(fake):
    assert printers.is_model("cups:Buero") and not printers.is_model("cups:")
    caps = printers.capabilities("cups:Dymo_LabelWriter_450")    # fragt CUPS nicht
    assert not caps.cutter and not caps.two_color and not caps.tested
    assert not printers.is_model("cups:-x") and not printers.is_model("cups:../etc/x")
    assert printers.effective_model(printers.printer_for("cups:Buero", [])) == "cups:Buero"
    assert printers.backend_for("cups:Buero") == "cups"
    labels = labels_for_model("cups:Dymo_LabelWriter_450")
    assert labels[0].id == "27.9x88.9mm@300" and all(lbl.shape == "die_cut" for lbl in labels)


def test_automatic_choice_never_takes_a_queue(fake):
    queues = printers.cups_printers([])
    assert printers.choose(queues) is None
    net = printers.Printer("tcp://10.0.0.5:9100", "QL-720NW", "Büro", "network")
    assert printers.choose(queues + [net]) == net
    assert printers.choose(queues, "cups:Buero").uri == "cups:Buero"


def test_chosen_brother_queue_stays_next_to_the_direct_printer(fake):
    direct = [printers.Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1", "usb")]
    assert "cups:QL600" in [p.uri for p in printers.cups_printers(direct, keep="cups:QL600")]


@pytest.mark.parametrize("key, title, cut", [("CutMedia", "Cut", True), ("DymoCutOptions", "", True),
                                             ("Cutter", "Messer", True), ("Schnitt", "", True),
                                             ("ExecuteMode", "Execute", False),
                                             ("Port", "Schnittstelle", False)])
def test_cut_options_by_word(key, title, cut):
    assert bool(cups._cut_options({key: (title or key, ["a", "b"], "a")})) == cut


def test_bad_queue_names_are_not_used(fake):
    _, outputs, folder = fake
    outputs["lpstat -e"] = "Gut\n-o\n../x\nmit Leer\n"
    assert [q.name for q in cups.queues()] == ["Gut"]
    with pytest.raises(cups.CupsError, match="Ungültiger Name"):
        cups.print_images("../x", [Image.new("1", (8, 8), 1)], 57, 32, 300)
