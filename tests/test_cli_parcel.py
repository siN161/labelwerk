"""labelwerk parcel: Markentypen auflisten, Marke erkennen, Vorschau, Drucken (ersetzt)."""
from PIL import Image

from labelwerk.cli import main
from parcelmark import make_pdf


def test_list_shows_the_types(capsys):
    assert main(["parcel", "--list"]) == 0
    out = capsys.readouterr().out
    assert "dhl-privat-1" in out and "hermes-2" in out and "ungeprüft" in out


def test_preview_of_a_detected_label(tmp_path, capsys):
    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "DHL Online Frankierung")])
    out = tmp_path / "v.png"
    assert main(["parcel", str(path), "-l", "62", "--preview", str(out)]) == 0
    text = capsys.readouterr().out
    assert "dhl-privat-1" in text
    img = Image.open(out)
    assert img.width == 696                                  # quer: ganzes 62-mm-Band


def test_preview_of_two_labels(tmp_path):
    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "Amazon Rücksendung")])
    out = tmp_path / "v.png"
    assert main(["parcel", str(path), "--type", "hermes-1", "-l", "62", "--preview", str(out)]) == 0
    assert (tmp_path / "v-1.png").exists() and (tmp_path / "v-2.png").exists()


def test_unknown_label_type_is_reported(tmp_path, capsys):
    path = make_pdf(tmp_path / "marke.pdf", size_mm=(50, 50), texts=[(5, 5, "Hallo")])
    assert main(["parcel", str(path), "-l", "62", "--preview", str(tmp_path / "v.png")]) == 2
    assert "nicht erkannt" in capsys.readouterr().err
    assert main(["parcel", str(path), "--type", "dpd-9", "-l", "62"]) == 2
    assert "Unbekannter Markentyp" in capsys.readouterr().err


def test_missing_file_is_reported(tmp_path, capsys):
    assert main(["parcel", str(tmp_path / "fehlt.pdf"), "-l", "62"]) == 2
    assert "nicht gefunden" in capsys.readouterr().err
    assert main(["parcel", "-l", "62"]) == 2


def test_print_sends_all_labels_in_one_job(tmp_path, monkeypatch):
    sent = {}

    def fake_print(images, label, **kw):
        sent["images"], sent["label"] = images, label
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "Amazon Rücksendung")])
    rc = main(["parcel", str(path), "--type", "dhl-retour-4", "-l", "62", "-p", "file:///dev/usb/lp0"])
    assert rc == 0 and sent["label"] == "62" and len(sent["images"]) == 2


def test_shrunk_barcodes_are_mentioned(tmp_path, capsys):
    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "DHL Online Frankierung")])
    assert main(["parcel", str(path), "--type", "dhl-privat-1", "-l", "62x100",
                 "--preview", str(tmp_path / "v.png")]) == 0
    assert "Barcodes verkleinert" in capsys.readouterr().err


def test_tie_between_untested_types_asks_for_the_type(tmp_path, capsys):
    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "Hermes Paketschein")])
    assert main(["parcel", str(path), "-l", "62", "--preview", str(tmp_path / "v.png")]) == 2
    err = capsys.readouterr().err
    assert "--type" in err and "hermes-2" in err and "hermes-3" in err
    assert not (tmp_path / "v.png").exists()
    assert main(["parcel", str(path), "--type", "hermes-2", "-l", "62",
                 "--preview", str(tmp_path / "v.png")]) == 0


def test_image_needs_a_type(tmp_path, capsys):
    Image.new("RGB", (800, 1131), "white").save(tmp_path / "foto.png")   # A4-Verhältnis, ohne Text
    assert main(["parcel", str(tmp_path / "foto.png"), "-l", "62"]) == 2
    assert "nicht erkannt" in capsys.readouterr().err
    assert main(["parcel", str(tmp_path / "foto.png"), "--type", "dhl-privat-1", "-l", "62",
                 "--preview", str(tmp_path / "v.png")]) == 0
