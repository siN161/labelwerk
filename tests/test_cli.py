from PIL import Image

from labelwerk.cli import main


def test_preview_writes_png_without_printer(tmp_path):
    out = tmp_path / "vorschau.png"
    rc = main(["print", "Hallo", "-l", "62", "--preview", str(out)])
    assert rc == 0
    assert out.exists()


def test_missing_printer_gives_friendly_error(capsys):
    rc = main(["print", "Hallo", "-l", "62", "-p", "file:///nonexistent/lp9"])
    assert rc == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_auto_printer_without_device_gives_friendly_error(monkeypatch, capsys):
    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: None)
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
    rc = main(["print", "Sehr langer Text", "-l", "29", "-s", "200", "--preview", "x.png"])
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
