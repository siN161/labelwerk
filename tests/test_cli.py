import pytest
from PIL import Image

from labelwerk.cli import main


def test_preview_writes_png_without_printer(tmp_path):
    out = tmp_path / "vorschau.png"
    rc = main(["print", "Hallo", "-l", "62", "--preview", str(out)])
    assert rc == 0
    assert out.exists()


def test_missing_printer_gives_friendly_error(monkeypatch, capsys):
    def not_found(**kwargs):
        raise FileNotFoundError(kwargs["printer_identifier"])
    monkeypatch.setattr("labelwerk.printer.send", not_found)
    rc = main(["print", "Hallo", "-l", "62", "-p", "file:///nonexistent/lp9"])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_auto_printer_without_device_gives_friendly_error(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: False)
    rc = main(["print", "Hallo", "-l", "62"])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_auto_printer_with_pyusb_uses_usb_discovery(monkeypatch):
    monkeypatch.setattr("labelwerk.cli.find_brother_usb", lambda: "usb://0x04f9:0x20c0")
    sent = {}
    def fake_print(img, label, **kw):
        sent.update(kw)
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    rc = main(["print", "Hallo", "-l", "62", "-b", "pyusb"])
    assert rc == 0
    assert sent["printer"] == "usb://0x04f9:0x20c0"


def test_auto_printer_with_network_asks_for_address(capsys):
    rc = main(["print", "Hallo", "-l", "62", "-b", "network"])
    assert rc == 2
    assert "tcp://" in capsys.readouterr().err


def test_print_error_gives_friendly_message(monkeypatch, capsys):
    from labelwerk.printer import PrintError
    def fail(*a, **kw):
        raise PrintError("Eingelegte Rolle passt nicht")
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fail)
    rc = main(["print", "Hallo", "-l", "62", "-p", "file:///dev/usb/lp0"])
    assert rc == 2
    assert "Rolle passt nicht" in capsys.readouterr().err


def test_unknown_label_gives_friendly_error(capsys):
    rc = main(["print", "Hallo", "-l", "99", "--preview", "x.png"])
    assert rc == 2
    assert "Unbekanntes Etikett" in capsys.readouterr().err


def test_font_size_too_large_gives_friendly_error(capsys):
    rc = main(["print", "Sehr langer Text", "-l", "29", "-s", "48", "--preview", "x.png"])
    assert rc == 2
    assert "passt nicht" in capsys.readouterr().err


def _png(tmp_path, w_mm=40, h_mm=20):
    path = tmp_path / "motiv.png"
    Image.new("L", (round(w_mm * 300 / 25.4), round(h_mm * 300 / 25.4)), 0).save(path)
    return path


def test_print_file_preview_reports_size_in_mm(tmp_path, capsys):
    out = tmp_path / "vorschau.png"
    rc = main(["print-file", str(_png(tmp_path)), "-l", "62", "--preview", str(out)])
    assert rc == 0
    assert out.exists()
    assert "58,9 × 22,0 mm" in capsys.readouterr().out


def test_print_file_sends_image_in_label_width(tmp_path, monkeypatch):
    sent = {}
    def fake_print(img, label, **kw):
        sent["size"] = img.size
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    rc = main(["print-file", str(_png(tmp_path)), "-l", "62", "-p", "file:///dev/usb/lp0"])
    assert rc == 0
    assert sent["size"][0] == 696


def test_print_file_unsupported_type(tmp_path, capsys):
    path = tmp_path / "notiz.txt"
    path.write_text("x")
    rc = main(["print-file", str(path), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "nicht unterstützt" in capsys.readouterr().err


def test_print_file_missing_file(tmp_path, capsys):
    rc = main(["print-file", str(tmp_path / "fehlt.pdf"), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_print_file_too_large_suggests_fit(tmp_path, capsys):
    rc = main(["print-file", str(_png(tmp_path, 120, 70)), "--preview", str(tmp_path / "x.png")])
    assert rc == 2
    assert "--fit" in capsys.readouterr().err


def test_corrupt_file_gives_friendly_error(tmp_path, capsys):
    path = tmp_path / "kaputt.pdf"
    path.write_bytes(b"kein pdf")
    rc = main(["print-file", str(path), "--preview", str(tmp_path / "o.png")])
    assert rc == 2
    assert "kann nicht gelesen werden" in capsys.readouterr().err


def test_preview_into_missing_directory_gives_friendly_error(tmp_path, capsys):
    rc = main(["print", "Hallo", "--preview", str(tmp_path / "nodir" / "o.png")])
    assert rc == 2
    assert "Vorschau kann nicht gespeichert werden" in capsys.readouterr().err


def test_preview_with_unknown_extension_gives_friendly_error(tmp_path, capsys):
    rc = main(["print-file", str(_png(tmp_path)), "--preview", str(tmp_path / "o.txt")])
    assert rc == 2
    assert "Vorschau kann nicht gespeichert werden" in capsys.readouterr().err


def test_print_file_rotate_0_with_fit(tmp_path, capsys):
    out = tmp_path / "vorschau.png"
    rc = main(["print-file", str(_png(tmp_path, 90, 47)), "-l", "62", "--rotate", "0", "--fit",
               "--preview", str(out)])
    assert rc == 0
    assert "58,9 × 32,8 mm" in capsys.readouterr().out


def test_busy_printer_gives_specific_hint(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: True)
    rc = main(["print", "Hallo", "-l", "62"])
    assert rc == 2
    assert "von einem anderen Programm belegt" in capsys.readouterr().err


def test_install_desktop_uses_xdg_data_home(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr("labelwerk.desktop.shutil.which", lambda name: None)   # kein update-…
    monkeypatch.setattr("labelwerk.desktop.subprocess.run",
                        lambda *a, **k: pytest.fail("externes Programm gestartet"))
    rc = main(["install-desktop"])
    assert rc == 0
    assert (tmp_path / "applications" / "labelwerk.desktop").exists()
    assert "labelwerk.desktop" in capsys.readouterr().out
    assert main(["install-desktop", "--remove"]) == 0
    assert not (tmp_path / "applications" / "labelwerk.desktop").exists()


def _write_settings(**values):
    import json
    import os
    from pathlib import Path
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values))


def test_default_label_comes_from_settings(tmp_path, capsys):
    _write_settings(label_id="62x29")
    rc = main(["print", "Hallo", "--preview", str(tmp_path / "v.png")])
    assert rc == 0
    assert "58,9 × 22,9 mm" in capsys.readouterr().out


def _preview(tmp_path, *args):
    out = tmp_path / "v.png"
    assert main(["print", "Hallo Welt", *args, "--preview", str(out)]) == 0
    return Image.open(out).convert("RGB").tobytes()


def _expected(orientation="vertical", margin=1.0):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    doc = Document("62", orientation=orientation, margin_mm=margin, objects=[TextObject("Hallo Welt")])
    return render_document(doc).convert("RGB").tobytes()


def test_default_orientation_comes_from_settings(tmp_path):
    _write_settings(orientation="horizontal")
    assert _preview(tmp_path) == _expected("horizontal")


def test_orientation_option_overrides_settings(tmp_path):
    _write_settings(orientation="horizontal")
    assert _preview(tmp_path, "--orientation", "vertical") == _expected("vertical")


def test_margin_option(tmp_path):
    assert _preview(tmp_path, "--margin", "5") == _expected(margin=5.0)


def test_broken_settings_warn_but_work(tmp_path, capsys):
    import os
    from pathlib import Path
    path = Path(os.environ["XDG_CONFIG_HOME"]) / "labelwerk" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text("{kaputt")
    assert main(["print", "Hallo", "--preview", str(tmp_path / "v.png")]) == 0
    assert "nicht lesbar" in capsys.readouterr().err


def test_media_command_shows_loaded_roll(monkeypatch, capsys):
    from labelwerk.media import Media
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.cli.read_media", lambda printer: Media(62, 0, "endless"))
    assert main(["media"]) == 0
    assert "Eingelegt: 62 mm endlos (Etikett 62)" in capsys.readouterr().out


def test_media_command_error(monkeypatch, capsys):
    from labelwerk.media import MediaError
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")

    def fail(printer):
        raise MediaError("Keine Antwort vom Drucker auf die Statusabfrage.")
    monkeypatch.setattr("labelwerk.cli.read_media", fail)
    assert main(["media"]) == 2
    assert "Keine Antwort" in capsys.readouterr().err


def test_media_command_without_printer(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: False)
    assert main(["media"]) == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_font_size_auto_overrides_saved_size(tmp_path):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    _write_settings(font_size=80)
    expected = render_document(Document("62", objects=[TextObject("Hallo Welt", size_pt=None)]))
    assert _preview(tmp_path, "-s", "auto") == expected.convert("RGB").tobytes()


def test_font_size_option_beats_settings(tmp_path):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    _write_settings(font_size=80)
    expected = render_document(Document("62", objects=[TextObject("Hallo Welt", size_pt=24)]))
    assert _preview(tmp_path, "-s", "24") == expected.convert("RGB").tobytes()


@pytest.mark.parametrize("value", ["3", "101", "abc", "1.5"])
def test_font_size_invalid_is_argparse_error(value, capsys):
    with pytest.raises(SystemExit) as e:
        main(["print", "X", "-s", value])
    assert e.value.code == 2
    assert "Schriftgröße" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["25", "-1", "nan", "inf", "abc"])
def test_margin_invalid_is_argparse_error(value, capsys):
    with pytest.raises(SystemExit) as e:
        main(["print", "X", f"--margin={value}"])
    assert e.value.code == 2
    assert "Rand" in capsys.readouterr().err


def _rich_expected(**plain):
    from labelwerk.document import Document, TextObject
    from labelwerk.render import render_document
    obj = TextObject.plain("Hallo\nWelt", **plain)
    return render_document(Document("62", objects=[obj])).convert("RGB").tobytes()


def _rich_preview(tmp_path, *args):
    out = tmp_path / "v.png"
    assert main(["print", "Hallo\\nWelt", *args, "--preview", str(out)]) == 0
    return Image.open(out).convert("RGB").tobytes()


def test_align_option(tmp_path):
    assert _rich_preview(tmp_path, "--align", "left") == _rich_expected(align="left")


def test_style_options(tmp_path):
    assert _rich_preview(tmp_path, "--no-bold", "--italic", "--underline") == \
        _rich_expected(bold=False, italic=True, underline=True)


def test_font_family_option_and_warning(tmp_path, capsys):
    assert _rich_preview(tmp_path, "--font-family", "GibtsGarNicht 4711") == \
        _rich_expected(family="GibtsGarNicht 4711")
    assert "GibtsGarNicht 4711" in capsys.readouterr().err


def test_default_font_family_from_settings(tmp_path):
    _write_settings(font_family="Liberation Sans")
    assert _rich_preview(tmp_path) == _rich_expected(family="Liberation Sans")


def test_font_path_beats_font_family_from_settings(tmp_path):
    from labelwerk import fonts
    path = fonts.resolve(None, False, False).path          # DejaVu Sans normal als Datei
    _write_settings(font_family="Liberation Sans")
    assert _rich_preview(tmp_path, "--font", path) == _rich_expected(font_path=path)


def test_font_path_and_font_family_together_is_error(capsys):
    assert main(["print", "X", "--font", "/x.ttf", "--font-family", "Y", "--preview", "/tmp/x.png"]) == 2
    assert "--font" in capsys.readouterr().err


def test_fonts_command_lists_families(capsys):
    assert main(["fonts"]) == 0
    assert "DejaVu Sans" in capsys.readouterr().out.splitlines()


def test_fonts_command_short_list_and_all(monkeypatch, capsys):
    from labelwerk import cli
    monkeypatch.setattr(cli, "families", lambda all=False: ["A", "B"] if all else ["A"])
    assert main(["fonts"]) == 0
    assert capsys.readouterr().out.splitlines() == ["A"]
    assert main(["fonts", "--all"]) == 0
    assert capsys.readouterr().out.splitlines() == ["A", "B"]


def test_align_invalid_is_argparse_error():
    with pytest.raises(SystemExit) as e:
        main(["print", "X", "--align", "mittig"])
    assert e.value.code == 2


def test_unloadable_font_gives_friendly_error(tmp_path, capsys):
    broken = tmp_path / "kaputt.ttf"
    broken.write_text("keine Schrift")
    rc = main(["print", "Hallo", "-l", "62", "--font", str(broken), "--preview",
               str(tmp_path / "v.png")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "kann nicht geladen werden" in err and "Traceback" not in err


def test_align_left_changes_preview(tmp_path):
    assert _rich_preview(tmp_path, "--align", "left") != _rich_preview(tmp_path, "--align", "center")


def test_install_desktop_write_error_is_a_message(tmp_path, monkeypatch, capsys):
    blocker = tmp_path / "share"
    blocker.write_text("kein Ordner")
    monkeypatch.setenv("XDG_DATA_HOME", str(blocker))
    monkeypatch.setattr("labelwerk.desktop.shutil.which", lambda name: None)
    assert main(["install-desktop"]) == 2
    assert "nicht eingetragen" in capsys.readouterr().err


def test_install_desktop_reports_failed_update_tools(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr("labelwerk.desktop.update_databases", lambda data, **kw: ["update-mime-database"])
    assert main(["install-desktop"]) == 0
    assert "update-mime-database" in capsys.readouterr().err


# --- Drucker-Kompatibilität ----------------------------------------------------------------------
def _detected(monkeypatch, *found):
    from labelwerk.printers import Printer
    monkeypatch.setattr("labelwerk.cli.printers.usb_printers",
                        lambda *a, **k: [Printer(uri, model, f"{model} · x") for uri, model in found])


def test_model_auto_uses_the_detected_printer(monkeypatch, capsys):
    _detected(monkeypatch, ("file:///dev/usb/lp1", "QL-1100"))
    assert main(["labels"]) == 0
    assert "102 " in capsys.readouterr().out


def test_model_auto_without_printer_uses_the_last_model(monkeypatch, capsys):
    _write_settings(last_model="QL-820NWB")
    assert main(["labels"]) == 0
    assert "62red" in capsys.readouterr().out


def test_unknown_model_is_an_error(capsys):
    assert main(["-m", "QL-9", "labels"]) == 2
    assert "Unbekanntes Druckermodell 'QL-9'" in capsys.readouterr().err


def test_printers_command_lists_printers_and_models(monkeypatch, capsys):
    _detected(monkeypatch, ("file:///dev/usb/lp1", "QL-600"), ("file:///dev/usb/lp2", "QL-700"))
    _write_settings(network_printers=[{"name": "Büro", "host": "10.0.0.5", "model": "QL-720NW"}])
    assert main(["printers"]) == 0
    out = capsys.readouterr().out
    assert "file:///dev/usb/lp1" in out and "geprüft" in out
    assert "QL-700" in out and "ungeprüft – Rückmeldung erwünscht" in out
    assert "tcp://10.0.0.5:9100" in out
    assert "Wirksames Modell: QL-600" in out and "QL-1100 (ungeprüft)" in out


def test_label_auto_reads_the_loaded_roll(monkeypatch, tmp_path):
    from labelwerk.media import Media
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.cli.read_media", lambda printer: Media(29, 0, "endless"))
    out = tmp_path / "v.png"
    assert main(["print", "Hallo", "-l", "auto", "--preview", str(out)]) == 0
    assert Image.open(out).width == 306                       # 29 mm endlos


@pytest.mark.parametrize("media, message", [(None, "nicht gefunden"),
                                            ("none", "Keine Rolle eingelegt"),
                                            ("odd", "Kein Etikett für die eingelegte Rolle")])
def test_label_auto_errors(monkeypatch, capsys, media, message):
    from labelwerk.media import Media
    monkeypatch.setattr("labelwerk.cli.find_brother_lp",
                        lambda: None if media is None else "file:///dev/usb/lp0")
    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: False)
    roll = Media(0, 0, "none") if media == "none" else Media(70, 0, "endless")
    monkeypatch.setattr("labelwerk.cli.read_media", lambda printer: roll)
    assert main(["print", "Hallo", "-l", "auto", "--preview", "x.png"]) == 2
    assert message in capsys.readouterr().err


def test_auto_printer_includes_network_printers(monkeypatch):
    _write_settings(network_printers=[{"name": "Büro", "host": "10.0.0.5", "model": "QL-720NW"}])
    sent = {}

    def fake_print(img, label, **kw):
        sent.update(kw)
        return {"outcome": "sent", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    assert main(["print", "Hallo", "-l", "62"]) == 0
    assert sent["printer"] == "tcp://10.0.0.5:9100" and sent["backend"] is None
    assert sent["model"] == "QL-720NW"                        # Modell des Netzwerkdruckers


def test_given_printer_decides_the_model(monkeypatch):
    _detected(monkeypatch, ("file:///dev/usb/lp0", "QL-600"), ("file:///dev/usb/lp1", "QL-1100"))
    sent = {}

    def fake_print(img, label, **kw):
        sent.update(kw, label=label, width=img.width)
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    assert main(["print", "Hallo", "-l", "102", "-p", "file:///dev/usb/lp1"]) == 0
    assert (sent["model"], sent["label"], sent["width"]) == ("QL-1100", "102", 1164)
    assert main(["print", "Hallo", "-l", "102", "-p", "usb://0x04f9:0x20a7"]) == 0
    assert sent["model"] == "QL-1100"


def test_label_that_does_not_fit_the_model_is_an_error(capsys):
    assert main(["-m", "QL-600", "print", "Hallo", "-l", "62red", "--preview", "x.png"]) == 2
    assert "Etikett '62red' passt nicht zum QL-600" in capsys.readouterr().err


def test_label_auto_asks_the_chosen_printer(monkeypatch):
    from labelwerk.media import Media
    _detected(monkeypatch, ("file:///dev/usb/lp0", "QL-600"), ("file:///dev/usb/lp1", "QL-700"))
    asked = []
    monkeypatch.setattr("labelwerk.cli.read_media",
                        lambda printer: asked.append(printer) or Media(62, 0, "endless"))
    assert main(["print", "Hallo", "-l", "auto", "-p", "file:///dev/usb/lp1",
                 "--preview", "x.png"]) == 0
    assert asked == ["file:///dev/usb/lp1"]


def test_label_auto_needs_usb(capsys):
    assert main(["print", "Hallo", "-l", "auto", "-p", "tcp://10.0.0.5", "--preview", "x.png"]) == 2
    assert "nur bei Druckern per USB" in capsys.readouterr().err


def test_network_backend_without_entries_explains(capsys, monkeypatch):
    assert main(["print", "Hallo", "-l", "62", "-b", "network"]) == 2
    assert "Kein Netzwerkdrucker eingetragen" in capsys.readouterr().err


def test_media_asks_the_chosen_printer(monkeypatch, capsys):
    from labelwerk.media import Media
    _detected(monkeypatch, ("file:///dev/usb/lp0", "QL-600"), ("file:///dev/usb/lp1", "QL-700"))
    _write_settings(printer="file:///dev/usb/lp1")
    asked = []
    monkeypatch.setattr("labelwerk.cli.read_media",
                        lambda printer: asked.append(printer) or Media(62, 0, "endless"))
    assert main(["media"]) == 0
    assert asked == ["file:///dev/usb/lp1"]


def test_missing_chosen_printer_is_named(monkeypatch, capsys):
    _detected(monkeypatch, ("file:///dev/usb/lp0", "QL-600"))
    _write_settings(printer="file:///dev/usb/lp1")
    assert main(["print", "Hallo", "-l", "62"]) == 2
    assert "Gewählter Drucker file:///dev/usb/lp1 nicht gefunden" in capsys.readouterr().err


# --- CUPS ---------------------------------------------------------------------------------------
@pytest.fixture
def cups_queue(monkeypatch):
    """CUPS nachgebildet: Warteschlange „Buero“ ohne PPD, Aufrufe aufgezeichnet."""
    from labelwerk import cups
    calls = []

    def run(*args, **kw):
        calls.append(args)
        if args[0] == "lpstat":
            return "Buero\n" if args[1] == "-e" else "device for Buero: ipp://10.0.0.9/ipp/print\n"
        return "request id is Buero-7 (1 file(s))\n" if args[0] == "lp" else ""
    monkeypatch.setattr(cups, "_run", run)
    return calls


def test_print_to_a_cups_queue(cups_queue, capsys):
    assert main(["print", "Hallo", "-p", "cups:Buero", "-l", "57x32mm@300"]) == 0
    assert "An CUPS übergeben (Auftrag Buero-7)" in capsys.readouterr().out
    lp = cups_queue[-1]
    assert lp[:7] == ("lp", "-d", "Buero", "-o", "media=Custom.57x32mm", "-o", "print-scaling=none")


def test_cups_queue_needs_its_labels(cups_queue, capsys):
    assert main(["print", "Hallo", "-p", "cups:Buero", "-l", "62"]) == 2
    assert "passt nicht zum cups:Buero" in capsys.readouterr().err
    assert not any(c[0] == "lp" for c in cups_queue)


def test_cups_queues_are_listed(cups_queue, capsys):
    assert main(["printers"]) == 0
    out = capsys.readouterr().out
    assert "Buero · CUPS" in out and "cups:Buero" in out and "cups:NAME (ungeprüft)" in out
    assert main(["-m", "cups:Buero", "labels"]) == 0
    assert "57x32mm@300" in capsys.readouterr().out


def test_print_file_to_cups_in_its_resolution(cups_queue, tmp_path, monkeypatch):
    from labelwerk import cups
    monkeypatch.setattr(cups, "queue_info", lambda name: cups.QueueInfo(
        (("w162h90", 57.2, 31.8),), 203))
    sizes = []
    monkeypatch.setattr(cups, "print_images",
                        lambda name, images, w, h, dpi, options=None: sizes.extend(i.size for i in images)
                        or cups.Job("Buero-8"))
    assert main(["print-file", str(_png(tmp_path, 40, 20)), "-p", "cups:Buero",
                 "-l", "57.2x31.8mm@203"]) == 0
    assert sizes == [(457, 254)]


# --- Zebra --------------------------------------------------------------------------------------
def test_print_to_a_zebra_device(tmp_path, capsys, monkeypatch):
    from labelwerk import zpl
    monkeypatch.setattr(zpl, "_is_device", lambda info: True)    # Datei statt Gerät
    device = tmp_path / "lp2"
    device.write_bytes(b"")
    assert main(["-m", "zpl:300", "print", "Hallo", "-p", f"zpl+file://{device}",
                 "-l", "57x32mm@305", "-b", "zebra"]) == 0
    assert device.read_bytes().startswith(b"^XA^PW684^LL384")     # ohne ^MM: wie am Drucker
    assert main(["print", "Hallo", "-p", f"zpl+file://{device}", "-l", "57x32mm@305"]) == 2
    assert "passt nicht zum zpl:203" in capsys.readouterr().err     # ohne -m: 203 dpi


def test_zebra_on_usb_is_listed(tmp_path, monkeypatch, capsys):
    from labelwerk import printers
    monkeypatch.setattr(printers, "zebra_printers", lambda **kw: [printers.Printer(
        "zpl+file:///dev/usb/lp2", "zpl:203", "ZTC GK420d · lp2", "zebra")])
    assert main(["printers"]) == 0
    out = capsys.readouterr().out
    assert "ZTC GK420d · lp2" in out and "zpl+file:///dev/usb/lp2" in out and "Zebra zpl:203" in out


def test_model_and_route_mismatch_is_a_message(capsys):
    assert main(["-m", "zpl:203", "print", "X", "-p", "tcp://10.0.0.5", "-l", "51x25mm@203"]) == 2
    assert "passt nicht zum Drucker" in capsys.readouterr().err


@pytest.fixture
def office_queue(monkeypatch):
    """„Etiketten“ (Dymo-Größen) und „Buero“ (A4/Letter) in CUPS."""
    from labelwerk import cups
    calls = []

    def run(*args, **kw):
        calls.append(args)
        if args[0] == "lpstat":
            return ("Buero\nEtiketten\n" if args[1] == "-e" else
                    "device for Buero: ipp://10.0.0.9/ipp/print\n"
                    "device for Etiketten: usb://DYMO/LabelWriter%20450\n")
        if args[0] == "lpoptions":
            return ("PageSize/Media Size: Letter *A4\n" if args[2] == "Buero"
                    else "PageSize/Media Size: *57x32mm\n")
        return "request id is Etiketten-3 (1 file(s))\n" if args[0] == "lp" else ""
    monkeypatch.setattr(cups, "_run", run)
    return calls


def test_office_printers_are_not_listed(office_queue, capsys):
    assert main(["printers"]) == 0
    out = capsys.readouterr().out
    assert "Etiketten · CUPS" in out and "Buero ·" not in out
    assert ("1 Bürodrucker ausgeblendet – „labelwerk printers --all“ zeigt ihn, drucken mit "
            "-p cups:NAME") in out


def test_all_printers_option_lists_office_printers_without_asking(office_queue, capsys):
    assert main(["printers", "--all"]) == 0
    out = capsys.readouterr().out
    assert "Buero · CUPS" in out and "ausgeblendet" not in out
    assert not any(c[0] == "lpoptions" for c in office_queue)    # nichts einzuordnen


def test_office_printers_are_listed_with_the_setting(office_queue, capsys):
    _write_settings(cups_all=True)
    assert main(["printers"]) == 0
    assert "Buero · CUPS" in capsys.readouterr().out
    assert not any(c[0] == "lpoptions" for c in office_queue)


def test_chosen_office_printer_is_listed(office_queue, capsys):
    _write_settings(printer="cups:Buero")
    assert main(["printers"]) == 0
    assert "Buero · CUPS" in capsys.readouterr().out


def test_backend_cups_skips_office_printers(office_queue, capsys):
    assert main(["print", "Hallo", "-b", "cups", "-l", "57x32mm@300"]) == 0
    assert "Auftrag Etiketten-3" in capsys.readouterr().out


def test_explicit_queue_is_not_classified(office_queue, capsys):
    assert main(["print", "Hallo", "-p", "cups:Buero", "-l", "57x32mm@300"]) == 0
    assert ("lpoptions", "-p", "Etiketten", "-l") not in office_queue   # nur Buero (Etiketten)


def test_backend_cups_names_hidden_office_printers(monkeypatch, capsys):
    from labelwerk import cups

    def run(*args, **kw):
        if args[0] == "lpstat":
            return "Buero\n" if args[1] == "-e" else ""
        return "PageSize/Media Size: Letter *A4\n" if args[0] == "lpoptions" else ""
    monkeypatch.setattr(cups, "_run", run)
    assert main(["print", "Hallo", "-b", "cups", "-l", "62"]) == 2
    err = capsys.readouterr().err
    assert "Keine CUPS-Warteschlange" in err and "Bürodrucker ausgeblendet: Buero" in err


def test_backend_cups_takes_the_first_queue(cups_queue, capsys):
    assert main(["print", "Hallo", "-b", "cups", "-l", "57x32mm@300"]) == 0
    assert "Auftrag Buero-7" in capsys.readouterr().out


def test_cups_is_not_asked_without_need(cups_queue):
    main(["print", "Hallo", "-l", "62", "--preview", "/dev/null"])
    assert not any(c[0] == "lpstat" for c in cups_queue)


def test_cli_speaks_english_with_lang(capsys):
    assert main(["--lang", "en", "print", "X", "-l", "999"]) == 2
    err = capsys.readouterr().err
    assert "Unknown label" in err or "unknown" in err.lower()
    assert main(["print", "X", "-l", "999"]) == 2                 # ohne --lang: Deutsch (conftest)
    assert "Unbekanntes Etikett" in capsys.readouterr().err


@pytest.mark.parametrize("argv, code", [(["--lang=en", "labels"], "en"), (["-m", "QL-600", "--lang", "en", "labels"], "en"),
                                        (["labels", "--lang", "en"], "de"), (["print", "--", "--lang"], "de")])
def test_language_option_before_the_command(argv, code):
    from labelwerk.cli import _language
    assert (_language(argv) or "de") == code


def test_argparse_texts_are_translated(capsys):
    with pytest.raises(SystemExit):
        main(["print"])
    err = capsys.readouterr().err
    assert "Aufruf: labelwerk print" in err and "Fehler: diese Angaben fehlen: text" in err
