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
