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
