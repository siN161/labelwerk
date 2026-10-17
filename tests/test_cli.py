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
