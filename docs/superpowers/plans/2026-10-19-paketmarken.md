# Paketmarken umwandeln – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paketmarken (DHL, Hermes; Land wählbar, Daten nachpflegbar) für den Etikettendrucker umwandeln: Marke öffnen, Typ erkennen, in Stücke schneiden und neu anordnen (Barcodes 1:1), drucken – im Reiter PAKET und per `labelwerk parcel`; eigene Typen aufziehen.

**Architecture:** Qt-freier Kern `parcel.py` mit Katalog `parcel_data/catalog.json` (gemessene Bereiche, Anordnung je Format), Umwandlung erzeugt normale Dokumente aus Bild-Objekten; Oberfläche dünn darauf (Panel, Editor-Fenster), CLI `parcel`.

**Tech Stack:** Python ≥ 3.10, Pillow, pypdfium2, brother_ql-inventree 1.3.x, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-19-paketmarken-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-pk-lin`), nach jedem Task volle Suite grün mit Exit-Code 0 (2767 → 2891 → 2938 → 2952); jeder Teil von einem Reviewer geprüft und korrigiert, danach ein Gesamtreview (Task 3).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Kern bleibt **Qt-frei** (`labels.py`, `render.py`, `layout.py`, `fonts.py`, `settings.py`, `cups.py`, `printers.py`, `cli.py`); kein Test erreicht echte Hardware, CUPS oder das Netz (`cups._run` ist in tests/conftest.py ersetzt); **nie den echten Drucker ansprechen**; keine echte Einstellungsdatei (conftest lenkt `XDG_CONFIG_HOME` um).
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten, ohne echte Dialoge; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen englisch mit `_()`, Deutsch in `po/de.po` (in den Patches enthalten); Kommentare deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Paketmarken – Kern, Katalog, CLI, Werkzeuge

**Files:**
- Modify: `.gitignore`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-19-paketmarken-design.md`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/files.py`
- Modify: `src/labelwerk/gui/file_dialog.py`
- Create: `src/labelwerk/parcel.py`
- Create: `src/labelwerk/parcel_data/README.md`
- Create: `src/labelwerk/parcel_data/catalog.json`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Create: `tests/parcelmark.py`
- Create: `tests/test_cli_parcel.py`
- Create: `tests/test_parcel.py`
- Create: `tools/parcel/README.md`
- Create: `tools/parcel/analyze.py`
- Create: `tools/parcel/assemble.py`
- Create: `tools/parcel/catalog.py`
- Create: `tools/parcel/extract.py`
- Create: `tools/parcel/make_sheets.py`
- Create: `tools/parcel/workdir.py`

**Interfaces / Produces:** `parcel.py` (`countries`, `carriers`, `types`, `find`, `load` → `Source`, `detect`, `ambiguous`, `placement`, `convert` → `Conversion`, `snap`, `arrange`, `all_pieces`, eigene Typen `own_*`/`save_own`/`remove_own`, `ParcelError`); `parcel_data/catalog.json` + README; `files.PDFIUM_LOCK`; CLI `labelwerk parcel`; `tools/parcel/` (Testblätter, Auswertung – nur zum Pflegen).

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/parcelmark.py b/tests/parcelmark.py
new file mode 100644
index 0000000..d388084
--- /dev/null
+++ b/tests/parcelmark.py
@@ -0,0 +1,49 @@
+"""Erzeugte Test-Paketmarken (keine echten Daten): kleine PDFs mit Text (Helvetica) und schwarzen
+Flächen, von Hand geschrieben – ohne Qt und ohne zusätzliche Bibliothek."""
+from __future__ import annotations
+
+from pathlib import Path
+
+PT = 72 / 25.4
+
+
+def make_pdf(path: Path, size_mm=(210, 297), texts=(), rects=(), images=()) -> Path:
+    """PDF mit einer Seite ``size_mm``. ``texts``: (x_mm, y_mm, Text) – y von oben;
+    ``rects``: (x0, y0, x1, y1) in mm, schwarz gefüllt; ``images``: (x_mm, y_mm, PIL-Bild „L“,
+    dpi) – als Graustufenbild eingebettet (Barcodes)."""
+    w, h = size_mm[0] * PT, size_mm[1] * PT
+    ops = ["0 g"]
+    for x0, y0, x1, y1 in rects:
+        ops.append(f"{x0 * PT:.2f} {h - y1 * PT:.2f} {(x1 - x0) * PT:.2f} {(y1 - y0) * PT:.2f} re f")
+    for n, (x, y, img, dpi) in enumerate(images):
+        iw, ih = img.width * 72 / dpi, img.height * 72 / dpi
+        ops.append(f"q {iw:.2f} 0 0 {ih:.2f} {x * PT:.2f} {h - y * PT - ih:.2f} cm /Im{n} Do Q")
+    for x, y, text in texts:
+        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
+        ops.append(f"BT /F1 10 Tf {x * PT:.2f} {h - y * PT:.2f} Td ({safe}) Tj ET")
+    content = "\n".join(ops).encode("latin-1")
+    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
+               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"]
+    xobjects = " ".join(f"/Im{n} {6 + n} 0 R" for n in range(len(images)))
+    objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w:.2f} {h:.2f}] "
+                   f"/Resources << /Font << /F1 5 0 R >> /XObject << {xobjects} >> >> "
+                   f"/Contents 4 0 R >>".encode())
+    objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
+    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
+                   b"/Encoding /WinAnsiEncoding >>")
+    for _, _, img, _ in images:
+        data = img.convert("L").tobytes()
+        objects.append(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace "
+                       b"/DeviceGray /BitsPerComponent 8 /Length %d >>\nstream\n"
+                       % (img.width, img.height, len(data)) + data + b"\nendstream")
+    out, offsets = bytearray(b"%PDF-1.4\n"), []
+    for number, body in enumerate(objects, 1):
+        offsets.append(len(out))
+        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
+    xref = len(out)
+    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
+    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
+    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
+    path = Path(path)
+    path.write_bytes(bytes(out))
+    return path
diff --git a/tests/test_cli_parcel.py b/tests/test_cli_parcel.py
new file mode 100644
index 0000000..1a578c8
--- /dev/null
+++ b/tests/test_cli_parcel.py
@@ -0,0 +1,79 @@
+"""labelwerk parcel: Markentypen auflisten, Marke erkennen, Vorschau, Drucken (ersetzt)."""
+from PIL import Image
+
+from labelwerk.cli import main
+from parcelmark import make_pdf
+
+
+def test_list_shows_the_types(capsys):
+    assert main(["parcel", "--list"]) == 0
+    out = capsys.readouterr().out
+    assert "dhl-privat-1" in out and "hermes-2" in out and "ungeprüft" in out
+
+
+def test_preview_of_a_detected_label(tmp_path, capsys):
+    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "DHL Online Frankierung")])
+    out = tmp_path / "v.png"
+    assert main(["parcel", str(path), "-l", "62", "--preview", str(out)]) == 0
+    text = capsys.readouterr().out
+    assert "dhl-privat-1" in text
+    img = Image.open(out)
+    assert img.width == 696                                  # quer: ganzes 62-mm-Band
+
+
+def test_preview_of_two_labels(tmp_path):
+    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "Amazon Rücksendung")])
+    out = tmp_path / "v.png"
+    assert main(["parcel", str(path), "--type", "hermes-1", "-l", "62", "--preview", str(out)]) == 0
+    assert (tmp_path / "v-1.png").exists() and (tmp_path / "v-2.png").exists()
+
+
+def test_unknown_label_type_is_reported(tmp_path, capsys):
+    path = make_pdf(tmp_path / "marke.pdf", size_mm=(50, 50), texts=[(5, 5, "Hallo")])
+    assert main(["parcel", str(path), "-l", "62", "--preview", str(tmp_path / "v.png")]) == 2
+    assert "nicht erkannt" in capsys.readouterr().err
+    assert main(["parcel", str(path), "--type", "dpd-9", "-l", "62"]) == 2
+    assert "Unbekannter Markentyp" in capsys.readouterr().err
+
+
+def test_missing_file_is_reported(tmp_path, capsys):
+    assert main(["parcel", str(tmp_path / "fehlt.pdf"), "-l", "62"]) == 2
+    assert "nicht gefunden" in capsys.readouterr().err
+    assert main(["parcel", "-l", "62"]) == 2
+
+
+def test_print_sends_all_labels_in_one_job(tmp_path, monkeypatch):
+    sent = {}
+
+    def fake_print(images, label, **kw):
+        sent["images"], sent["label"] = images, label
+        return {"outcome": "printed", "did_print": True}
+    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
+    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "Amazon Rücksendung")])
+    rc = main(["parcel", str(path), "--type", "dhl-retour-4", "-l", "62", "-p", "file:///dev/usb/lp0"])
+    assert rc == 0 and sent["label"] == "62" and len(sent["images"]) == 2
+
+
+def test_shrunk_barcodes_are_mentioned(tmp_path, capsys):
+    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "DHL Online Frankierung")])
+    assert main(["parcel", str(path), "--type", "dhl-privat-1", "-l", "62x100",
+                 "--preview", str(tmp_path / "v.png")]) == 0
+    assert "Barcodes verkleinert" in capsys.readouterr().err
+
+
+def test_tie_between_untested_types_asks_for_the_type(tmp_path, capsys):
+    path = make_pdf(tmp_path / "marke.pdf", texts=[(20, 20, "Hermes Paketschein")])
+    assert main(["parcel", str(path), "-l", "62", "--preview", str(tmp_path / "v.png")]) == 2
+    err = capsys.readouterr().err
+    assert "--type" in err and "hermes-2" in err and "hermes-3" in err
+    assert not (tmp_path / "v.png").exists()
+    assert main(["parcel", str(path), "--type", "hermes-2", "-l", "62",
+                 "--preview", str(tmp_path / "v.png")]) == 0
+
+
+def test_image_needs_a_type(tmp_path, capsys):
+    Image.new("RGB", (800, 1131), "white").save(tmp_path / "foto.png")   # A4-Verhältnis, ohne Text
+    assert main(["parcel", str(tmp_path / "foto.png"), "-l", "62"]) == 2
+    assert "nicht erkannt" in capsys.readouterr().err
+    assert main(["parcel", str(tmp_path / "foto.png"), "--type", "dhl-privat-1", "-l", "62",
+                 "--preview", str(tmp_path / "v.png")]) == 0
diff --git a/tests/test_parcel.py b/tests/test_parcel.py
new file mode 100644
index 0000000..eab3bab
--- /dev/null
+++ b/tests/test_parcel.py
@@ -0,0 +1,538 @@
+"""Paketmarken umwandeln (Kern): Katalog, Laden, Erkennen, Kanten anpassen, Umwandeln, eigene Typen.
+
+Nur erzeugte Test-Marken (tests/parcelmark.py) – nie echte Marken mit Adressen."""
+import json
+
+import pytest
+from PIL import Image, ImageDraw
+
+from labelwerk import i18n, parcel
+from labelwerk.document import BarcodeObject, ImageObject
+from labelwerk.labels import get_label
+from labelwerk.render import label_size, render_document
+from parcelmark import make_pdf
+
+MM = 300 / 25.4
+
+
+# --- Katalog -------------------------------------------------------------------------
+def test_catalog_has_the_german_types():
+    ids = {t.id for t in parcel.types("DE")}
+    assert {"dhl-privat-1", "dhl-privat-1a", "dhl-privat-2", "dhl-privat-3", "dhl-privat-4",
+            "dhl-privat-4a", "dhl-privat-4b", "dhl-business-1", "dhl-business-5", "dhl-retour-1",
+            "dhl-retour-4", "hermes-1", "hermes-2", "hermes-3"} <= ids
+    assert parcel.find("dhl-privat-1").verified and not parcel.find("hermes-2").verified
+    assert [code for code, _ in parcel.countries()] == ["DE"]
+    assert dict(parcel.carriers("DE")) == {"dhl": "DHL", "hermes": "Hermes"}
+
+
+@pytest.mark.parametrize("ptype", parcel.types("DE"), ids=lambda t: t.id)
+def test_every_type_is_consistent(ptype):
+    assert ptype.names["de"] and ptype.names["en"]
+    assert ptype.layouts, "jeder mitgelieferte Typ hat ein Layout"
+    w, h = max(s[0] for s in ptype.source_sizes), max(s[1] for s in ptype.source_sizes)
+    for key, sheets in ptype.layouts.items():
+        assert key in parcel.LAYOUTS
+        for sheet in sheets:
+            assert sheet.pieces
+            for piece in sheet.pieces:
+                x0, y0, x1, y1 = piece.src
+                assert 0 <= x0 < x1 <= w + 1 and 0 <= y0 < y1 <= h + 1, piece
+                dx0, dy0, dx1, dy1 = piece.dst
+                assert -1 <= dx0 < dx1 <= sheet.size_mm[0] + 1, piece
+                assert -1 <= dy0 < dy1 <= sheet.size_mm[1] + 1, piece
+                assert piece.rotation in (0, 90, 180, 270) and piece.kind in parcel.KINDS
+
+
+def test_names_follow_the_language():
+    ptype = parcel.find("dhl-privat-3")
+    assert ptype.name == "DHL Warenpost national"
+    i18n.set_language("en")
+    assert ptype.name == "DHL Warenpost domestic"
+
+
+def test_unknown_type_is_a_friendly_error():
+    with pytest.raises(parcel.ParcelError, match="Unbekannter Markentyp"):
+        parcel.find("dpd-1")
+
+
+# --- Laden und Erkennen --------------------------------------------------------------
+def test_load_reads_size_and_text(tmp_path):
+    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung")])
+    source = parcel.load(path)
+    assert source.page_count == 1
+    assert source.sizes_mm[0] == pytest.approx((210, 297), abs=0.2)
+    assert "DHL Online Frankierung" in source.texts[0]
+    page = source.page(1, 150)
+    assert page.size == pytest.approx((210 * 150 / 25.4, 297 * 150 / 25.4), abs=1)
+
+
+def test_load_rejects_other_files(tmp_path):
+    (tmp_path / "x.txt").write_text("hallo")
+    with pytest.raises(parcel.ParcelError):
+        parcel.load(tmp_path / "x.txt")
+    (tmp_path / "kaputt.pdf").write_bytes(b"%PDF-1.4 nix")
+    with pytest.raises(parcel.ParcelError):
+        parcel.load(tmp_path / "kaputt.pdf")
+    with pytest.raises(parcel.ParcelError):
+        parcel.load(tmp_path / "fehlt.pdf")
+
+
+def test_detect_dhl_domestic(tmp_path):
+    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung"),
+                                                (20, 30, "Sendungsnummer")])
+    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE")]
+    assert found[0] == "dhl-privat-1"
+    assert "dhl-privat-1a" in found and "hermes-2" not in found
+
+
+def test_detect_prefers_the_100x150_layout_on_wide_labels(tmp_path):
+    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung")])
+    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE", label_id="102")]
+    assert found[0] == "dhl-privat-1a"
+
+
+def test_detect_warenpost_with_customs(tmp_path):
+    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Warenpost International"),
+                                                (20, 30, "CN 23")])
+    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE")]
+    assert set(found[:2]) == {"dhl-privat-4a", "dhl-privat-4b"}
+    assert "dhl-privat-3" not in found
+
+
+def test_detect_by_page_size(tmp_path):
+    path = make_pdf(tmp_path / "m.pdf", size_mm=(105, 203), texts=[(10, 10, "DHL PAKET")])
+    assert parcel.detect(parcel.load(path), "DE")[0][0].id == "dhl-business-2"
+
+
+def test_detect_hermes(tmp_path):
+    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Hermes Paketschein")])
+    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE")]
+    assert set(found[:2]) == {"hermes-2", "hermes-3"}
+
+
+def test_detect_raster_label(tmp_path):
+    Image.new("RGB", (1800, 1200), "white").save(tmp_path / "m.gif")
+    found = [t.id for t, _ in parcel.detect(parcel.load(tmp_path / "m.gif"), "DE")]
+    assert found[0] == "dhl-retour-3"
+
+
+def test_detect_nothing(tmp_path):
+    path = make_pdf(tmp_path / "m.pdf", size_mm=(50, 50), texts=[(5, 5, "Hallo")])
+    assert parcel.detect(parcel.load(path), "DE") == []
+
+
+# --- Kanten an die Marke anpassen -----------------------------------------------------
+def _page(*rects):
+    img = Image.new("L", (round(100 * MM), round(100 * MM)), 255)
+    draw = ImageDraw.Draw(img)
+    for x0, y0, x1, y1 in rects:
+        draw.rectangle([round(x0 * MM), round(y0 * MM), round(x1 * MM) - 1, round(y1 * MM) - 1], 0)
+    return img
+
+
+def test_snap_moves_a_cut_edge_out_to_white():
+    img = _page((20, 20, 41, 40))                     # Fläche ragt 1 mm über die rechte Kante
+    box = parcel.snap(img, (20, 20, 40, 40), 300)
+    assert box[2] == pytest.approx(41, abs=0.2) and box[:2] == pytest.approx((20, 20), abs=0.01)
+
+
+def test_snap_keeps_white_edges_and_long_overhangs():
+    img = _page((20, 20, 50, 40))                     # ragt 10 mm hinaus: keine weiße Linie nah
+    assert parcel.snap(img, (20, 20, 40, 40), 300) == pytest.approx((20, 20, 40, 40))
+    img = _page((22, 22, 38, 38))                     # Kanten schon weiß
+    assert parcel.snap(img, (20, 20, 40, 40), 300) == pytest.approx((20, 20, 40, 40))
+
+
+# --- Umwandeln ----------------------------------------------------------------------
+def _barcode_page(tmp_path, ptype_id="dhl-privat-1"):
+    """Testmarke mit einem Code 128 im ersten Barcode-Stück des Typs (quer wie auf der Marke)."""
+    from labelwerk import barcodes
+    piece = max((p for p in parcel.find(ptype_id).layouts["62"][0].pieces if p.kind == "barcode"),
+                key=lambda p: (p.src[2] - p.src[0]) * (p.src[3] - p.src[1]))     # größtes Barcode-Stück
+    code = barcodes.draw(BarcodeObject(kind="code128", data="LW123456", module=4, h_mm=18))
+    if piece.src[3] - piece.src[1] > piece.src[2] - piece.src[0]:
+        code = code.rotate(90, expand=True)                    # hochkant wie auf der Marke
+    x = piece.src[0] + 2
+    y = piece.src[1] + 2
+    return make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung")],
+                    rects=[(10, 30, 30, 40)], images=[(x, y, code, 300)])
+
+
+def test_convert_dhl_domestic_for_62_mm(tmp_path):
+    source = parcel.load(_barcode_page(tmp_path))
+    result = parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
+    assert result.layout == "62" and len(result.documents) == 1
+    doc = result.documents[0]
+    assert doc.label_id == "62" and doc.orientation == "horizontal"
+    assert len(doc.objects) == 7 and all(isinstance(o, ImageObject) for o in doc.objects)
+    assert all(o.mode == "line" and not o.keep_ratio for o in doc.objects)
+    width, height = label_size(doc, "QL-600")
+    assert height == get_label("62").width                   # quer: ganzes Band
+    assert result.scale == pytest.approx(58.93 / 59.58, abs=0.02)
+    assert result.notes == []                                # Barcodes ≥ 97 %
+    assert 160 < doc.length_mm < 190
+    for obj in doc.objects:                                  # alles auf dem Etikett
+        assert obj.x_mm >= -0.01 and obj.y_mm >= -0.01
+        assert obj.y_mm + obj.h_mm <= 58.95
+        assert obj.x_mm + obj.w_mm <= doc.length_mm - 5.9
+
+
+def test_converted_barcode_is_readable(tmp_path):
+    zxingcpp = pytest.importorskip("zxingcpp", reason="zxing-cpp fehlt (Wheels erst ab Python 3.12)")
+    source = parcel.load(_barcode_page(tmp_path))
+    doc = parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600").documents[0]
+    img = render_document(doc, "QL-600").convert("L")
+    texts = [r.text for r in zxingcpp.read_barcodes(img)]
+    assert "LW123456" in texts
+
+
+def test_wider_tape_makes_it_larger(tmp_path):
+    source = parcel.load(_barcode_page(tmp_path))
+    narrow = parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
+    wide = parcel.convert(source, parcel.find("dhl-privat-1"), "102", "QL-1100")
+    assert wide.scale > 1.5 * narrow.scale
+    assert wide.documents[0].length_mm > 1.5 * narrow.documents[0].length_mm
+
+
+def test_wide_label_uses_the_100x150_layout(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
+    result = parcel.convert(source, parcel.find("dhl-privat-1a"), "104x150mm@300", "zpl:300")
+    assert result.layout == "100x150"
+    assert result.documents[0].orientation == "vertical"
+    assert result.notes == []
+
+
+def test_short_die_cut_label_shrinks_with_a_note(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
+    result = parcel.convert(source, parcel.find("dhl-privat-1"), "62x100", "QL-600")
+    assert result.scale < 0.6
+    assert any("Barcodes verkleinert" in n for n in result.notes)
+    doc = result.documents[0]
+    w, h = label_size(doc, "QL-600")
+    for obj in doc.objects:
+        assert obj.x_mm + obj.w_mm <= w / MM + 0.05 and obj.y_mm + obj.h_mm <= h / MM + 0.05
+
+
+def test_two_labels_for_a_return(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Amazon Rücksendung")]))
+    result = parcel.convert(source, parcel.find("dhl-retour-4"), "62", "QL-600")
+    assert len(result.documents) == 2
+
+
+def test_raster_label_is_placed_where_the_type_says(tmp_path):
+    img = Image.new("RGB", (1800, 1200), "white")
+    ImageDraw.Draw(img).rectangle([0, 0, 1799, 1199], outline="black", width=30)
+    img.save(tmp_path / "m.gif")
+    source = parcel.load(tmp_path / "m.gif")
+    ptype = parcel.find("dhl-retour-3")
+    page = source.page(1, 100, ptype)
+    assert page.size == pytest.approx((210 * 100 / 25.4, 297 * 100 / 25.4), abs=1)
+    k = 100 / 25.4                                            # Lage aus der Regel: 189,4 mm von oben
+    assert page.getpixel((round(50 * k), round((189.4 + 101.6 - 1) * k))) < 128   # Rahmen unten
+    assert page.getpixel((round(50 * k), round(150 * k))) == 255
+    assert page.getpixel((2, 2)) == 255
+    result = parcel.convert(source, ptype, "62", "QL-600")
+    assert result.documents and render_document(result.documents[0], "QL-600")
+
+
+def test_round_labels_are_refused(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
+    with pytest.raises(parcel.ParcelError):
+        parcel.convert(source, parcel.find("dhl-privat-1"), "d24", "QL-600")
+
+
+# --- Eigene Typen -------------------------------------------------------------------
+def _own(**changes):
+    data = {"id": "own-test", "names": {"de": "Meine Marke", "en": "My label"},
+            "source": {"sizes_mm": [[210, 297]]}, "detect": {"all": ["Meine Firma"]},
+            "pieces": [{"page": 1, "src": [10, 10, 110, 60], "rotation": 0, "kind": "text"},
+                       {"page": 1, "src": [10, 100, 60, 130], "rotation": 0, "kind": "barcode"},
+                       {"page": 1, "src": [100, 100, 130, 200], "rotation": 90, "kind": "text"}]}
+    data.update(changes)
+    return data
+
+
+def test_own_types_round_trip():
+    ptype = parcel.own_from_dict(_own())
+    parcel.save_own(ptype)
+    assert [t.id for t in parcel.own_types()] == ["own-test"]
+    assert parcel.find("own-test").own and parcel.find("own-test").name == "Meine Marke"
+    assert "own-test" in {t.id for t in parcel.types("DE")}       # eigene in jedem Land
+    parcel.remove_own("own-test")
+    assert parcel.own_types() == []
+
+
+@pytest.mark.parametrize("change", [{"pieces": []}, {"id": "../x"}, {"names": {"de": ""}},
+                                    {"pieces": [{"page": 1, "src": [10, 10, 5, 5], "rotation": 0,
+                                                 "kind": "text"}]},
+                                    {"pieces": [{"page": 1, "src": [0, 0, 10, 10], "rotation": 45,
+                                                 "kind": "text"}]},
+                                    {"pieces": [{"page": 1, "src": [0, 0, 10, 10], "rotation": 0,
+                                                 "kind": "foto"}]}])
+def test_own_types_are_checked(change):
+    with pytest.raises(parcel.ParcelError):
+        parcel.own_from_dict(_own(**change))
+
+
+def test_broken_own_file_is_skipped_with_a_note():
+    parcel.own_dir().mkdir(parents=True)
+    (parcel.own_dir() / "kaputt.json").write_text("{nicht json")
+    (parcel.own_dir() / "gut.json").write_text(json.dumps(_own(id="own-gut")))
+    assert [t.id for t in parcel.own_types()] == ["own-gut"]
+    assert any("kaputt.json" in w for w in parcel.own_warnings())
+
+
+def test_arrange_fills_columns_along_the_tape():
+    ptype = parcel.own_from_dict(_own())
+    sheet = parcel.arrange(ptype.pieces, 58.9)
+    assert sheet.size_mm[1] == pytest.approx(58.9)
+    text, code, turned = sheet.pieces
+    assert code.dst[2] - code.dst[0] == pytest.approx(50)                # Barcode 1:1
+    assert text.dst[2] - text.dst[0] == pytest.approx(100)              # passt quer: 1:1
+    assert turned.dst[3] - turned.dst[1] == pytest.approx(30)           # gedreht: 100 lang → längs
+    for piece in sheet.pieces:
+        assert piece.dst[3] <= 58.9 + 1e-6
+
+
+def test_own_type_converts(tmp_path):
+    ptype = parcel.own_from_dict(_own())
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Meine Firma")]))
+    assert parcel.detect(source, "DE", own=[ptype])[0][0].id == "own-test"
+    result = parcel.convert(source, ptype, "62", "QL-600")
+    assert len(result.documents[0].objects) == 3 and result.layout == "own"
+
+
+def test_snap_only_for_untested_types_and_not_into_other_pieces(tmp_path, monkeypatch):
+    calls = []
+    real = parcel.snap
+
+    def spy(img, box, dpi, limit_mm=3.0):
+        calls.append(box)
+        return real(img, box, dpi, limit_mm)
+    monkeypatch.setattr(parcel, "snap", spy)
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
+    parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
+    assert calls == []                                       # geprüft: Kanten genau
+    parcel.convert(source, parcel.find("dhl-privat-2"), "62", "QL-600")
+    assert calls
+    a = parcel.Piece(1, (10, 10, 20, 20), 0)
+    b = parcel.Piece(1, (21, 10, 30, 20), 0)
+    assert parcel._alone(a, (9, 10, 22, 20), [a, b]) == (9, 10, 20, 20)   # nicht in b hinein
+
+
+# --- Lage, Drehung und Malreihenfolge je Typ -------------------------------------------
+def _marked_sheet(ptype, size_mm=None, k=300 / 25.4):
+    """Marke (Bild bei 300 dpi) mit einem schwarzen Quadrat oben links in jedem Bereich – zeigt
+    nach dem Umwandeln, ob Lage und Drehung stimmen."""
+    w, h = size_mm or ptype.source_sizes[0]
+    img = Image.new("L", (round(w * k), round(h * k)), 255)
+    draw = ImageDraw.Draw(img)
+    for piece in parcel.all_pieces(ptype):
+        x0, y0, x1, y1 = piece.src
+        draw.rectangle([round((x0 + 0.18 * (x1 - x0)) * k), round((y0 + 0.18 * (y1 - y0)) * k),
+                        round((x0 + 0.32 * (x1 - x0)) * k), round((y0 + 0.32 * (y1 - y0)) * k)], 0)
+    return img
+
+
+_ROTATED = {0: lambda u, v: (u, v), 90: lambda u, v: (1 - v, u), 180: lambda u, v: (1 - u, 1 - v),
+            270: lambda u, v: (v, 1 - u)}
+
+
+def _covered(dst, later):
+    x0, y0, x1, y1 = dst
+    area = 0.0
+    for a0, b0, a1, b1 in later:
+        area += max(0, min(x1, a1) - max(x0, a0)) * max(0, min(y1, b1) - max(y0, b0))
+    return area / ((x1 - x0) * (y1 - y0))
+
+
+@pytest.mark.parametrize("ptype", [t for t in parcel.types("DE")], ids=lambda t: t.id)
+def test_every_piece_lands_where_and_how_the_type_says(ptype, tmp_path):
+    marked = _marked_sheet(ptype)
+    if ptype.raster:                                      # Bildmarke: nur ihr Ausschnitt der Seite
+        k = 300 / 25.4
+        x, y = ptype.raster["x_mm"] * k, ptype.raster["y_mm"] * k
+        marked.crop((round(x), round(y), round(x) + 1800, round(y) + 1200)).save(tmp_path / "m.png")
+        source = parcel.load(tmp_path / "m.png")
+    else:
+        source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=ptype.source_sizes[0],
+                                      images=[(0, 0, marked, 300)]))
+    label = "102x152" if "62" not in ptype.layouts else "62"
+    result = parcel.convert(source, ptype, label, "QL-1100")
+    sheets = ptype.layouts["62" if "62" in ptype.layouts else "100x150"]
+    checked = 0
+    for doc, sheet in zip(result.documents, sheets):
+        for n, (obj, piece) in enumerate(zip(doc.objects, sheet.pieces)):
+            if _covered(piece.dst, [p.dst for p in sheet.pieces[n + 1:]]) > 0.05:
+                continue                                  # verdeckt: Malreihenfolge-Test unten
+            img = obj.image().convert("L")
+            u, v = _ROTATED[piece.rotation](0.25, 0.25)
+            pixel = img.getpixel((min(img.width - 1, round(u * img.width)),
+                                  min(img.height - 1, round(v * img.height))))
+            assert pixel < 128, (ptype.id, n, piece)
+            checked += 1
+    assert checked >= 1
+
+
+def test_later_pieces_cover_earlier_ones_cleanly(tmp_path):
+    """DHL national: das Leitcode-Quadrat liegt auf dem Kopfstreifen – dessen Tinte darf darunter
+    nicht durchscheinen."""
+    ptype = parcel.find("dhl-privat-1")
+    pieces = ptype.layouts["62"][0].pieces
+    head, square = pieces[0], pieces[3]
+    assert _covered(head.dst, [square.dst]) > 0
+    k = 300 / 25.4
+    img = Image.new("L", (round(210 * k), round(297 * k)), 255)
+    x0, y0, x1, y1 = head.src
+    ImageDraw.Draw(img).rectangle([round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)], 0)
+    x0, y0, x1, y1 = square.src
+    ImageDraw.Draw(img).rectangle([round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)], 255)
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", images=[(0, 0, img, 300)]))
+    doc = parcel.convert(source, ptype, "62", "QL-600").documents[0]
+    reading = render_document(doc, "QL-600").convert("L").rotate(90, expand=True)
+    obj = doc.objects[3]
+    centre = (round((obj.x_mm + obj.w_mm / 2) * k), round((obj.y_mm + obj.h_mm / 2) * k))
+    assert reading.getpixel(centre) == 255                # weißes Quadrat bleibt weiß
+
+
+def test_crop_outside_the_page_is_white():
+    page = Image.new("L", (100, 100), 0)
+    out = parcel._crop_white(page, (-10, -10, 50, 50))
+    assert out.size == (60, 60) and out.getpixel((2, 2)) == 255 and out.getpixel((30, 30)) == 0
+
+
+# --- Seitenlage: quer, andere Größe, Bild ------------------------------------------------
+def test_landscape_page_is_turned_upright(tmp_path):
+    ptype = parcel.find("dhl-privat-1")
+    landscape = _marked_sheet(ptype).rotate(90, expand=True)     # Marke quer (gegen den Uhrzeiger)
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(297, 210),
+                                  images=[(0, 0, landscape, 300)]))
+    assert parcel.placement(source, ptype).rotation == 90
+    page = source.page(1, 300 / 25.4 * 25.4 / 1, ptype)
+    assert page.size == pytest.approx((210 * 300 / 25.4, 297 * 300 / 25.4), abs=2)
+    doc = parcel.convert(source, ptype, "62", "QL-600").documents[0]
+    img = doc.objects[2].image().convert("L")               # Stück ohne Drehung
+    assert img.getpixel((round(0.25 * img.width), round(0.25 * img.height))) < 128
+
+
+def test_landscape_page_with_unclear_direction_is_refused(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(297, 210)))
+    with pytest.raises(parcel.ParcelError, match="quer"):
+        parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
+
+
+def test_letter_page_sits_top_left_on_a4(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(215.9, 279.4),
+                                  rects=[(0, 0, 215.9, 279.4)]))
+    ptype = parcel.find("dhl-retour-4")
+    page = source.page(1, 50, ptype)
+    k = 50 / 25.4
+    assert page.size == pytest.approx((210 * k, 297 * k), abs=1)
+    assert page.getpixel((round(100 * k), round(270 * k))) == 0          # Letter-Inhalt
+    assert page.getpixel((round(100 * k), round(290 * k))) == 255        # darunter weiß
+
+
+@pytest.mark.parametrize("ptype", [t for t in parcel.types("DE")], ids=lambda t: t.id)
+def test_every_listed_page_size_is_accepted(ptype, tmp_path):
+    for size in ptype.source_sizes:
+        if ptype.raster:
+            continue
+        source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=size))
+        place = parcel.placement(source, ptype)
+        assert place.frame_mm == ptype.source_sizes[0] and place.rotation == 0
+
+
+def test_wrong_page_size_is_a_friendly_error(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(2000, 2000)))
+    with pytest.raises(parcel.ParcelError, match="passt nicht"):
+        parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
+    with pytest.raises(parcel.ParcelError, match="zu groß"):
+        parcel.load(make_pdf(tmp_path / "a4.pdf")).page(1, 2000)
+
+
+def test_image_of_another_shape_is_not_recognized(tmp_path):
+    Image.new("RGB", (1000, 1000), "white").save(tmp_path / "q.gif")
+    assert parcel.detect(parcel.load(tmp_path / "q.gif"), "DE") == []
+
+
+def test_full_page_image_is_stretched_to_the_page_of_the_type(tmp_path):
+    ptype = parcel.find("dhl-privat-1")
+    _marked_sheet(ptype, k=100 / 25.4).save(tmp_path / "seite.png")   # 100 dpi, keine Angabe
+    source = parcel.load(tmp_path / "seite.png")
+    doc = parcel.convert(source, ptype, "62", "QL-600").documents[0]
+    img = doc.objects[2].image().convert("L")
+    assert img.getpixel((round(0.25 * img.width), round(0.25 * img.height))) < 128
+
+
+def test_huge_images_are_refused_before_decoding(tmp_path):
+    Image.new("1", (9400, 9400), 1).save(tmp_path / "riesig.png")
+    with pytest.raises(parcel.ParcelError, match="zu viele Pixel"):
+        parcel.load(tmp_path / "riesig.png")
+
+
+@pytest.mark.parametrize("dpi, expected", [(2, None), (72, 72.0), (5000, None)])
+def test_implausible_image_resolution_counts_as_missing(tmp_path, dpi, expected):
+    Image.new("RGB", (600, 400), "white").save(tmp_path / "m.png", dpi=(dpi, dpi))
+    source = parcel.load(tmp_path / "m.png")
+    assert source.image_dpi == (pytest.approx(expected, abs=0.5) if expected else None)
+
+
+def test_16_bit_gray_image_keeps_its_ink(tmp_path):
+    img = Image.new("I;16", (300, 200), 65535)
+    img.paste(0, (0, 0, 100, 100))
+    img.save(tmp_path / "m.png")
+    page = parcel.load(tmp_path / "m.png").image
+    assert page.getpixel((10, 10)) < 64 and page.getpixel((250, 150)) > 192
+
+
+def test_pdf_without_pages_has_its_own_message(tmp_path):
+    body = (b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
+            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n")
+    xref = len(body)
+    body += (b"xref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
+             b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref)
+    (tmp_path / "leer.pdf").write_bytes(body)
+    with pytest.raises(parcel.ParcelError, match="keine Seiten|nicht"):
+        parcel.load(tmp_path / "leer.pdf")
+
+
+# --- Layout fehlt fürs Format, Gleichstand, eigene Typen --------------------------------
+def test_missing_layout_is_arranged_from_the_pieces(tmp_path):
+    ptype = parcel.find("dhl-privat-1a-100x150")
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(100, 150)))
+    result = parcel.convert(source, ptype, "62", "QL-600")
+    assert result.layout == "arranged"
+    doc = result.documents[0]
+    for obj, piece in zip(doc.objects, ptype.layouts["100x150"][0].pieces):
+        w, h = piece.turned_mm()
+        if piece.kind == "barcode" and h <= 58.9:
+            assert (obj.w_mm, obj.h_mm) == pytest.approx((w, h), abs=0.05)   # Barcodes 1:1
+        assert obj.y_mm + obj.h_mm <= 58.95
+
+
+def test_ambiguous_marks_ties_without_a_tested_winner(tmp_path):
+    hermes = parcel.load(make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein")]))
+    assert {t.id for t in parcel.ambiguous(parcel.detect(hermes, "DE"))} == {"hermes-2", "hermes-3"}
+    dhl = parcel.load(make_pdf(tmp_path / "d.pdf", texts=[(20, 20, "DHL Online Frankierung")]))
+    assert parcel.ambiguous(parcel.detect(dhl, "DE")) == []
+
+
+@pytest.mark.parametrize("src", [[10, 10, 10.5, 50], [10, 10, 50, 10.5], [10, 10, 211, 50],
+                                 [10, 10, 50, 298]])
+def test_own_areas_need_size_and_must_lie_on_the_page(src):
+    with pytest.raises(parcel.ParcelError, match="Bereiche"):
+        parcel.own_from_dict(_own(pieces=[{"page": 1, "src": src, "rotation": 0, "kind": "text"}]))
+
+
+def test_damaged_own_file_says_so():
+    parcel.own_dir().mkdir(parents=True)
+    (parcel.own_dir() / "kaputt.json").write_text("{nicht json")
+    parcel.own_types()
+    assert any("beschädigt" in w for w in parcel.own_warnings())
+
+
+def test_version_mark_decides_between_hermes_labels(tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein V4.2.000")]))
+    found = parcel.detect(source, "DE")
+    assert found[0][0].id == "hermes-2" and parcel.ambiguous(found) == []
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_parcel.py, tests/test_cli_parcel.py) schlagen fehl (ImportError `labelwerk.parcel`), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/.gitignore b/.gitignore
index 24aadd5..c12d9c3 100644
--- a/.gitignore
+++ b/.gitignore
@@ -7,3 +7,11 @@ build/
 *.egg-info/
 .pytest_cache/
 /*.png
+# Pflege der Paketmarken (tools/parcel): Ausgaben und echte Marken nie einchecken
+check/
+result/
+analyse/
+analyse.json
+templates*.json
+templates-bericht.txt
+Original/
diff --git a/CLAUDE.md b/CLAUDE.md
index 0d06f0a..c2e87ff 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -67,7 +67,14 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   gewählte bleibt sichtbar).
 - Stilles Speichern (Zuletzt geöffnet/verwendet, Favoriten, gewählter Drucker, letzter Reiter) schreibt nur sein
   Feld (`settings.update_settings`) – was eine zweite Instanz gespeichert hat, bleibt.
-- 2767 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Paketmarken (Etappe Paketmarken, Kern + CLI): `labelwerk parcel MARKE [--type ID|auto] [--country DE] [-l …]
+  [--preview]`, `parcel --list`; 19 Typen DE (DHL privat/Business/Warenpost/Retoure, Hermes, Amazon-Retoure) aus
+  Testblättern bei paketikett.de ermittelt (`parcel_data/catalog.json`, Werkzeuge `tools/parcel/`), DHL national 1/1a
+  am echten Original geprüft (DataMatrix + 2 ITF lesbar); erkennt Typ an Text/Seitengröße (Gleichstand ungeprüfter
+  Typen → `--type` verlangt), schneidet/dreht/skaliert die Stücke (Barcodes 1:1, verdeckte Teile weiß), quer
+  liegende Marken gedreht, breiteres Band → größer, 100×150-Layout ab 95 mm (fehlt das Layout: neu angeordnet);
+  eigene Typen in `$XDG_DATA_HOME/labelwerk/paketmarken`.
+- 2886 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -118,7 +125,8 @@ src/labelwerk/
               families() = kurze Liste (:lang=de, ohne Farbschriften, Powerline/Nerd-Font-Kopien, Symbolschriften,
               CJK-Regionsvarianten), families(all=True) alle (Einstellung `fonts_all`, CLI fonts --all); canonical:
               alte Qt-Namen „Name [Hersteller]“ → „Name“ (resolve, font_warnings, FontCombo)
-  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
+  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi); PDFIUM_LOCK (RLock: jeder
+              PDFium-Aufruf in files, gui/file_dialog und parcel – PDFium ist nicht threadsicher)
               crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
               load_image(path, page, dpi=None) -> (RGB-Bild, dpi) für Bild-Objekte (PNG/JPG/GIF/BMP/WebP/PDF, Transparenz → weiß, EXIF-Lage; dpi gesetzt: Dateiauflösung gilt nicht, quadratisch diese dpi);
               crop_box(img, dpi, ink) -> (l, t, r, b) | None, dieselbe Logik wie crop() (Bilder: ink=NOT_WHITE); page_count(path) (PDF-Seitenwahl)
@@ -217,6 +225,27 @@ src/labelwerk/
               Rang: genaues Wort/Kürzel › Namenswort beginnt › Suchbegriff beginnt › im Namen › sonst), find/resolve(ids), data, is_vector, own_dir/own_symbols ($XDG_DATA_HOME/labelwerk/symbole,
               SVG/PNG, ohne versteckte), add_recent; Archiv fehlt/defekt: OSError/BadZipFile/KeyError/ValueError (GUI: Meldung „Symbol-Bibliothek nicht lesbar“)
   media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
+  parcel.py   Paketmarken ohne Qt: Katalog parcel_data/catalog.json (Länder → Dienste → Typen; Format/Herkunft/
+              eigene Typen/„Neuen Typ beisteuern“ in parcel_data/README.md, gepflegt mit tools/parcel/ – Arbeitsordner
+              außerhalb des Repos Pflicht, workdir.py) – countries, carriers, types(country) (+ eigene), find;
+              ParcelType (names {de,en} → name, source_sizes – erste = Seitenfläche, raster-Regel für Bildmarken {dpi,
+              x_mm, y_mm, px}, detect all/any/none, layouts "62"/"100x150" → Sheet(size_mm, pieces), verified, own),
+              Piece(page, src mm, rotation im Uhrzeigersinn, dst-Rechteck mm, kind barcode|text), all_pieces;
+              load(path) → Source (PDF: Größen + Text; Bild über files.load_image, Pixel vor dem Dekodieren begrenzt,
+              dpi < 50/> 1200 = keine Angabe; page(n, dpi, type) in der Seitenfläche des Typs, außen weiß, ≤
+              MAX_PAGE_PIXELS); placement(source, type, n) → Placement(frame, content, rotation, offset): passende
+              Größe wie sie ist (Letter oben links auf A4), quer → gedreht (_turn: mehr Tinte in den Bereichen,
+              sonst Fehler), Bild: Regel bzw. Seitenverhältnis ±3 % gestreckt, sonst ParcelError; detect(source,
+              country, label_id, own) (_fits, all muss vorkommen; Gleichstand: geprüft, passendes Layout,
+              Katalogreihenfolge), ambiguous(found) (Gleichstand ohne geprüften Sieger → fragen); snap (Kante bis
+              weiß, ≤ 3 mm, nur ungeprüfte Typen, _alone: nie in andere Stücke); convert(source, type, label_id,
+              model) → Conversion(documents, notes, layout "62"/"100x150"/"arranged"/"own", scale) (Seitenlage
+              geprüft, je Ausgabe-Etikett ein Document mit ImageObjects, Rand 0, spätere Stücke maskieren frühere
+              weiß – _mask_covered, Ausschnitte außerhalb weiß – _crop_white; endlos: Länge = Inhalt + Vorschub,
+              Breite füllt das Band; fest: passt hinein, bessere Lage; fehlt das Layout fürs Format: arrange;
+              Hinweis bei Barcodes < 97 %; rund → Fehler); arrange (Spalten längs des Bands, Barcodes 1:1);
+              own_dir/own_types/own_warnings (beschädigt …)/own_from_dict (geprüft, Kanten ≥ 1 mm in der Seite)/
+              own_to_dict/save_own/remove_own
   layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
               growing_axis (Endlosband wächst mit; align_objects am Papier: Anfang des Bereichs, auf Mindestlänge mittig –
               min_length –, nur wenn auch mit den übrigen Objekten (others) das Etikett dort klemmt), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
@@ -335,7 +364,8 @@ src/labelwerk/
                     Tastenkürzel (Konflikte sperren Speichern); restart_hint neben SPEICHERN (Stand beim Start: started)
     theme/          QSS-Stylesheet (rawblock.qss)
     icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
-  cli.py      labelwerk labels | labelwerk media | labelwerk printers [--all] (Bürodrucker; sonst Zeile „n ausgeblendet“) | labelwerk fonts [--all] | -m auto (Modell des Zieldruckers:
+  cli.py      labelwerk labels | labelwerk media | labelwerk printers [--all] (Bürodrucker; sonst Zeile „n ausgeblendet“) | labelwerk fonts [--all] | labelwerk parcel DATEI [--type ID|auto] [--country DE] [--preview A.png] /
+              parcel --list | -m auto (Modell des Zieldruckers:
               -p bzw. gewählter/erster) | -l auto (Rolle des Zieldruckers per USB) | Etikett muss zum Modell passen | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
 ```
 Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `printers`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.
@@ -378,7 +408,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Paketmarken umwandeln (eigener Branch paketmarken), dann Paketierung (8).
+Nächste Schritte: Paketierung (8).
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
diff --git a/README.md b/README.md
index efadb9f..3680ab5 100644
--- a/README.md
+++ b/README.md
@@ -64,6 +64,8 @@ labelwerk labels                                   # verfügbare Etiketten
 labelwerk print "X1 -K3\nKlemme 24V" -l 62x29 --preview vorschau.png
 labelwerk print "X1 -K3\nKlemme 24V" -l 62x29      # drucken (Drucker wird automatisch erkannt)
 labelwerk print-file internetmarke.pdf -l 62       # PDF/PNG/JPG 1:1 drucken
+labelwerk parcel paketmarke.pdf -l 62              # Paketmarke (DHL, Hermes …) fürs Etikett umwandeln
+labelwerk parcel --list                            # Markentypen (DE) – geprüft/ungeprüft/eigene
 labelwerk media                                            # eingelegte Rolle anzeigen (druckt nichts)
 labelwerk printers                                         # gefundene Drucker und unterstützte Modelle
 labelwerk printers --all                                   # auch CUPS-Bürodrucker
@@ -116,6 +118,17 @@ Tastenkürzel (Standard):
 
 Ausrichten, Größe angleichen und Maximieren haben ab Werk kein Kürzel. Im Schreibmodus gelten die Tasten des Texts statt der Objekt-Kürzel (Pfeile bewegen die Schreibmarke, Entf löscht Zeichen); Esc zum Beenden ist fest. Alle Kürzel lassen sich unter „Einstellungen“ → „Tastenkürzel“ ändern (Zeile anklicken, neue Kombination drücken; Esc, Enter und Tab sind nicht belegbar). Doppelt belegte Kürzel werden rot markiert und sperren das Speichern; stehen in einer von Hand bearbeiteten `settings.json` doppelte, behält die erste Aktion ihr Kürzel und die Statusleiste meldet es.
 
+## Paketmarken
+
+`labelwerk parcel MARKE.pdf` wandelt Paketmarken (DHL privat/Geschäftskunden/Warenpost/Retoure, Hermes, Amazon-Retouren –
+19 Typen für Deutschland) für den Etikettendrucker um: der Typ wird an Text und Seitengröße erkannt (`--type ID`
+legt ihn fest), die Marke wird in Stücke geschnitten und neu angeordnet – Barcodes in Originalgröße, Adressen kleiner.
+Auf 62 mm endlos ergibt das ein 15–28 cm langes Etikett, auf breiteren Bändern wird alles größer, Typ „1a“ ergibt
+100 × 150 mm (4×6-Drucker). Mehrere Etiketten (Retoure) gehen in einem Auftrag, `--preview a.png` schreibt `a-1.png`,
+`a-2.png`. Geprüft an einer echten Marke sind DHL national (1/1a), die übrigen Typen stammen aus Testblättern
+(„ungeprüft“; ihre Kanten rücken an der Marke bis zum nächsten weißen Rand). Eigene Typen und neue Länder:
+`src/labelwerk/parcel_data/README.md`. Vor dem Versand prüfen, ob die Barcodes lesbar sind.
+
 ## Architektur
 
 ```
@@ -135,6 +148,7 @@ imaging.py  Bilder: Schwarz/Weiß-Umwandlung (Strich/Foto), Größe begrenzen
 barcodes.py Barcodes: Code 128/39, EAN-13/8 (eigene Kodierung), QR (segno), in ganzen Druckpunkten
 layout.py   Platzieren: Einrasten, Ausrichten, Größe angleichen, ragt hinaus
 shortcuts.py Tastenkürzel-Verzeichnis (Standard, Konflikte, Prüfung)
+parcel.py   Paketmarken: Typen je Land (parcel_data/catalog.json), Erkennen, Umwandeln, eigene Typen
 gui/        PySide6-Oberfläche (nur Anzeige/Bearbeitung, kein Druckcode)
 ```
 
diff --git a/docs/superpowers/specs/2026-10-19-paketmarken-design.md b/docs/superpowers/specs/2026-10-19-paketmarken-design.md
index 783c30b..d66b8f2 100644
--- a/docs/superpowers/specs/2026-10-19-paketmarken-design.md
+++ b/docs/superpowers/specs/2026-10-19-paketmarken-design.md
@@ -40,35 +40,59 @@ Beispiele), Briefmarken/Internetmarke (geht schon über `print-file`), Texterken
 
 ## 1 – Daten: Markentypen (`src/labelwerk/parcel_data/`)
 
-- **Katalog** `catalog.json`: Länder (`DE` mit Namen {de, en}) → Dienste (`dhl`, `hermes`, Namen) → Typen. Ein Typ:
-  `id` („dhl-privat-1“), `names` {de, en}, `country`, `carrier`, `source` (Seitengröße in mm, z. B. 210 × 297, mit
-  Toleranz; Seiten des PDFs), `detect` (Textmuster, Seitengröße, Gewicht), `verified` (bool), `layouts`.
-- **Layout** je Ausgabe-Format (`"62"` = Referenz 62 mm endlos, `"100x150"` falls vorhanden): Liste von Etiketten
-  (Retoure: zwei), je Etikett Länge in mm und Stücke: `page`, `src` [x0, y0, x1, y1] mm auf der Marke, `rotation`
-  (0/90/180/270), `dst` [x, y] mm (linke obere Ecke auf dem Etikett, Leserichtung), `scale`, `kind`
-  (`barcode` | `text` – Barcodes nie verkleinern).
-- **Werte** aus der Testblatt-Auswertung (Kanten auf 0,5 mm), DHL Privat 1/1a am echten Original geschärft
-  (`verified: true`). Herkunft in `parcel_data/README.md` (Verfahren, keine Kopie fremden Codes).
-- **Eigene Typen:** `$XDG_DATA_HOME/labelwerk/paketmarken/*.json`, gleiches Format, `own: true`; fremde Eingabe
-  (geprüft wie Dateien: Grenzen, Struktur → `ParcelError`, kein Traceback).
+- **Katalog** `catalog.json` (Format in `parcel_data/README.md`): Länder (`DE` mit Namen {de, en}) → Dienste (`dhl`,
+  `hermes`, Namen) → Typen. Ein Typ: `id` („dhl-privat-1“), `names` {de, en}, `country`, `carrier`,
+  `source` (`sizes_mm`: mögliche Seitengrößen, ± 4 mm, auch quer; `raster` für Bildmarken: Auflösung und Lage auf der
+  Seite), `detect` (`all`/`any`/`none`: Begriffe im PDF-Text), `verified` (bool), `layouts`.
+- **Layout** je Ausgabe-Format (`"62"` = Referenz 62 mm endlos: Seite quer, x längs des Bands; `"100x150"` falls
+  vorhanden, hochkant): Liste von Ausgabe-Etiketten (Retoure: zwei), je Etikett `size_mm` und Stücke in
+  Malreihenfolge: `page`, `src` [x0, y0, x1, y1] mm auf der Marke, `rotation` (im Uhrzeigersinn 0/90/180/270),
+  `dst` [x0, y0, x1, y1] mm – Rechteck nach dem Drehen, das Stück wird genau darauf skaliert (paketikett skaliert
+  leicht ungleich) –, `kind` (`barcode` | `text`; vergrößerte Stücke > 1,03 gelten als Barcode).
+- **Werte** aus der Testblatt-Auswertung (Kanten auf 0,25 mm, Ausschnitte auf die Seite begrenzt), DHL Privat 1/1a am
+  echten Original geschärft (`verified: true`). 1a gibt es zweimal: Eingang A4 (`dhl-privat-1a`) und Marke 100 × 150
+  (`dhl-privat-1a-100x150`). Amazon-PDF-Typen auch im Letter-Format. Amazon-GIF (`dhl-retour-3`): Bild bei 300 dpi
+  an geschätzter Stelle der A4-Seite (x −2,5 mm, y 189,4 mm). Herkunft und „Neuen Typ beisteuern“ in
+  `parcel_data/README.md` (Verfahren, keine Kopie fremden Codes).
+- **Eigene Typen:** `$XDG_DATA_HOME/labelwerk/paketmarken/<id>.json` – nur `pieces` (ohne `dst`, `arrange` ordnet an),
+  `source`, `detect`, `names`; fremde Eingabe (`own_from_dict`: Kennung, Namen, Größen, Begriffe, Stücke geprüft →
+  `ParcelError`, kaputte Dateien übergangen mit Hinweis `own_warnings`).
 
 ## 2 – Kern: `parcel.py` (ohne Qt)
 
-- `catalog(country=None)`, `countries()`, `find(type_id)`, `own_types()`, `save_own(type)`, `remove_own(id)`.
-- `load(path)` → `Source` (Seiten als Bilder in Druckerauflösung über pypdfium2, Seitengrößen in mm, Text je Seite);
-  PNG/JPG/GIF als eine Seite (Amazon-GIF). Fremde Eingabe: Größe, Seitenzahl begrenzt.
-- `detect(source, country)` → Typen mit Punktzahl (Textmuster, Seitengröße), bester zuerst; nichts → [].
-- `snap(img, box_px)`: Kanten eines Stücks nach außen bis zur ersten ganz weißen Zeile/Spalte, höchstens 3 mm; ohne
-  weiße Linie bleibt die Kante (Antwort 6a).
-- `convert(source, type, label_id, model)` → `Document`(e) (je Etikett eins): Stücke als `ImageObject` (Strich,
-  Schwelle 128, 1:1 bei `scale` 1), Länge fest. **Skalierung:** Layout `"62"` gilt für die bedruckbare Breite von
-  62 mm endlos; anderes Band/Etikett: Layout mit Faktor bedruckbare Breite ÷ Referenz (breiter → größer, Antwort 2a);
-  Etikett ab 95 mm Breite und Typ mit `"100x150"`-Layout → dieses; festes (gestanztes) Etikett zu kurz → so weit
-  verkleinert, dass es passt. Barcode-Stücke unter 100 % → Hinweis „Barcodes verkleinert – vor dem Versand
-  prüfen, ob sie lesbar sind“.
-- `arrange(pieces, across_mm)` (eigene Typen ohne `dst`): Stücke nacheinander in Spalten längs des Bands, je Spalte so
-  hoch wie die Breite, Text-Stücke höchstens so verkleinert, dass sie passen, Barcodes 1:1 (zu breit → gedreht, sonst
-  Hinweis).
+- `countries()`, `carriers(country)`, `types(country=None)` (mitgelieferte des Lands + eigene), `find(type_id)`,
+  `own_dir()`, `own_types()`, `own_warnings()`, `own_from_dict(data)`, `own_to_dict(type)`, `save_own(type)`,
+  `remove_own(id)`; `ParcelType` (`name` in der Sprache, `verified`, `own`, `layouts`, `pieces`), `Piece`, `Sheet`.
+- `load(path)` → `Source` (Seitengrößen in mm und Text je Seite; `page(n, dpi, type)` rendert bei Bedarf in der
+  Seitenfläche des Typs, außen weiß, eine Seite gemerkt, höchstens 80 Mio. Pixel); PNG/JPG/GIF als eine Seite über
+  `files.load_image` (Transparenz, 16 Bit, EXIF, Größe begrenzt; Pixel vor dem Dekodieren ≤ 50 Mio.; dpi < 50 oder
+  > 1200 gilt als fehlend). Fremde Eingabe: Endung, ≤ 32 MB, 1–20 Seiten (0 Seiten: eigene Meldung) → `ParcelError`.
+- `placement(source, type, n)` → `Placement`: Seite in der Seitenfläche des Typs (erste `sizes_mm`) – passende Größe
+  wie sie ist (Letter oben links auf A4, weiß aufgefüllt), quer liegende gedreht (die Drehung, bei der mehr Tinte in
+  den Bereichen liegt; liegen beide gleich auf: „Richtung nicht eindeutig“), Bild nach Bild-Regel (Seitenverhältnis
+  der erwarteten Pixel ±3 %) bzw. auf eine Seitengröße gestreckt (±3 %); sonst `ParcelError` („passt nicht zum Typ“) –
+  `convert` prüft das vorab.
+- `detect(source, country, label_id=None, own=None)` → [(Typ, Punktzahl)], bester zuerst: Seitengröße muss passen
+  (Bildmarken: Typ mit Bild-Regel), `all` muss vorkommen; Gleichstand: geprüfte vor ungeprüften, mit `label_id` der
+  Typ mit passendem Layout (ab 95 mm: 100×150), sonst Katalogreihenfolge; nichts → []. Bilder: nur der Rastertyp
+  mit passendem Seitenverhältnis (Amazon-GIF), sonst nichts → `--type` bzw. Auswahl. `ambiguous(found)`: gleichauf
+  liegende Spitze ohne geprüften Sieger → diese Typen (CLI druckt dann nicht, sondern verlangt `--type`).
+- `snap(img, box_mm, dpi)`: Kanten, die Inhalt durchschneiden, nach außen bis zur ersten ganz weißen Linie, höchstens
+  3 mm (Antwort 6a) – **nur für ungeprüfte Typen** (am echten DHL-Original verschlechterte es geprüfte Kanten von 5,2
+  auf 8,2 % Abweichung) und nie neu in den Ausschnitt eines anderen Stücks (`_alone`).
+- `convert(source, type, label_id, model)` → `Conversion(documents, notes, layout, scale)`: je Ausgabe-Etikett ein
+  `Document` (Rand 0, Stücke als `ImageObject`, Strich/Schwelle 128, Seitenverhältnis frei, vorab gedreht); Inhalt
+  auf seine Fläche beschnitten, quer mittig. **Skalierung:** Endlosband – Inhalt füllt die bedruckbare Breite (breiter
+  → größer, Antwort 2a), Länge = Inhalt + Vorschub, höchstens Modellgrenze; festes Etikett – passt hinein, die Lage
+  (längs/quer) mit dem größeren Maßstab gewinnt. Ab 95 mm bedruckbarer Breite und mit `"100x150"`-Layout → dieses.
+  Spätere Stücke (Malreihenfolge) machen frühere dort weiß, wo sie liegen (sonst verdeckt Tinte darunter z. B. den
+  DataMatrix-Code); Ausschnitte außerhalb der Seite sind weiß. Fehlt das Layout fürs Format (nur 100×150, aber
+  schmales Band), ordnet `arrange` die Stücke neu an (Layout „arranged“, Barcodes 1:1).
+  Barcode-Stücke unter 97 % → Hinweis „Barcodes verkleinert auf n % – vor dem Versand prüfen, ob sie sich lesen
+  lassen.“ Runde Etiketten → `ParcelError`. Marke gerendert in Druckerauflösung × größtem Maßstab (≤ 600 dpi).
+- `arrange(pieces, across_mm)` (eigene Typen): Stücke nacheinander in Spalten längs des Bands bis zur Breite, Texte
+  höchstens so verkleinert, dass sie quer passen, Barcodes 1:1 (nur zu breite kleiner); eigene Typen werden nie
+  vergrößert.
 
 ## 3 – Oberfläche: Reiter PAKETMARKE
 
@@ -86,15 +110,18 @@ Beispiele), Briefmarken/Internetmarke (geht schon über `print-file`), Texterken
 
 ## 4 – Kommandozeile
 
-`labelwerk parcel DATEI [--type ID|auto] [--country DE] [-l ETIKETT] [-m MODELL] [-p DRUCKER] [--preview AUS.png]`,
-`labelwerk parcel --list [--country DE]` (Typen mit Erkennung/ungeprüft). `--preview` mit mehreren Etiketten:
+`labelwerk parcel DATEI [--type ID|auto] [--country DE] [-l ETIKETT] [-m MODELL] [-p DRUCKER] [--preview AUS.png]`
+(nennt den erkannten Typ und gleich gute andere, Hinweise auf stderr; drucken: alle Etiketten in einem Auftrag),
+`labelwerk parcel --list [--country DE]` (Typen mit geprüft/ungeprüft/eigener). `--preview` mit mehreren Etiketten:
 `AUS-1.png`, `AUS-2.png`.
 
 ## 5 – Werkzeug für neue Typen (`tools/parcel/`)
 
-`make_sheets.py` (Testblätter, Qt), `analyze.py` (Auswertung der umgewandelten Blätter → Layout-JSON; nur zum
-Pflegen, braucht numpy/scipy/zxing-cpp, keine Laufzeit-Abhängigkeit), Anleitung „Neuen Markentyp beisteuern“ in
-`parcel_data/README.md`.
+`make_sheets.py` (Testblätter, Qt), `analyze.py` (QR-Codes im Ergebnis → Bereiche), `extract.py` (genaue Bereiche
+je Typ: fehlende Stücke per Kreuzkorrelation, Kanten per Nachbau-Vergleich), `assemble.py` (→ templates.json),
+`catalog.py` (→ catalog.json mit Erkennung); nur zum Pflegen, braucht numpy/scipy/zxing-cpp, keine Laufzeit-
+Abhängigkeit; Datenordner über `LABELWERK_PARCEL_DIR`, echte Marken nur lokal (`Original/originale.json`).
+Anleitung „Neuen Typ beisteuern“ in `parcel_data/README.md`, Überblick `tools/parcel/README.md`.
 
 ## Tests
 
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index c13fe9e..5791c2b 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -1,5 +1,5 @@
-"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | printers | fonts |
-install-desktop"""
+"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | parcel marke.pdf | media |
+printers | fonts | install-desktop"""
 from __future__ import annotations
 
 import argparse
@@ -8,7 +8,7 @@ from pathlib import Path
 
 from PIL import Image
 
-from . import desktop, i18n
+from . import desktop, i18n, parcel
 from . import printer as prn
 from . import printers
 from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
@@ -139,6 +139,14 @@ def _parser() -> argparse.ArgumentParser:
                     help=_("auto (default: rotate only if needed) or degrees clockwise"))
     _add_output_options(pf)
 
+    pa = sub.add_parser("parcel", help=_("convert a parcel label (DHL, Hermes …) for the label printer"))
+    pa.add_argument("file", nargs="?", help=_("parcel label as PDF, PNG, JPG or GIF"))
+    pa.add_argument("--type", default="auto",
+                    help=_("auto (default: detect) or a type from 'labelwerk parcel --list'"))
+    pa.add_argument("--country", default="DE", help=_("country of the parcel label types (default DE)"))
+    pa.add_argument("--list", action="store_true", help=_("list the parcel label types"))
+    _add_output_options(pa)
+
     sub.add_parser("media", help=_("query the roll loaded in the printer (prints nothing)"))
     pp = sub.add_parser("printers", help=_("list found printers and supported models"))
     pp.add_argument("--all", dest="show_all", action="store_true",
@@ -286,6 +294,63 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
     return 0 if ok else 1
 
 
+def _list_parcel_types(country: str) -> int:
+    """labelwerk parcel --list: Typen des Lands und eigene (Kennung, Name, Prüfstand)."""
+    for ptype in parcel.types(country):
+        state = _("own") if ptype.own else (_("tested") if ptype.verified else _("untested"))
+        print(f"{ptype.id:<24} {ptype.name} ({state})")
+    for warning in parcel.own_warnings():
+        print(warning, file=sys.stderr)
+    return 0
+
+
+def _parcel(args: argparse.Namespace) -> int:
+    """labelwerk parcel DATEI: Typ erkennen (bzw. --type), umwandeln, Vorschau oder drucken."""
+    try:
+        source = parcel.load(args.file)
+        if args.type == "auto":
+            found = parcel.detect(source, args.country, label_id=args.label)
+            if not found:
+                print(_("Parcel label type not recognized – specify it with --type "
+                        "(see 'labelwerk parcel --list')."), file=sys.stderr)
+                return 2
+            tied = parcel.ambiguous(found)
+            if tied:
+                print(_("Parcel label type not unique – choose one with --type: {ids}").format(
+                    ids=", ".join(f"{t.id} ({t.name})" for t in tied)), file=sys.stderr)
+                return 2
+            ptype = found[0][0]
+            others = [t.id for t, score in found[1:] if score == found[0][1]]
+        else:
+            ptype, others = parcel.find(args.type), []
+        result = parcel.convert(source, ptype, args.label, args.model)
+        images = [render_document(doc, args.model) for doc in result.documents]
+    except (ValueError, FileNotFoundError) as e:
+        print(e, file=sys.stderr)
+        return 2
+    print(_("Parcel label: {name} ({id})").format(name=ptype.name, id=ptype.id))
+    if others:
+        print(_("Also possible: {ids} (--type)").format(ids=", ".join(others)))
+    for note in result.notes:
+        print(note, file=sys.stderr)
+    if not args.preview:
+        return _send(images, args)
+    paths = ([Path(args.preview)] if len(images) == 1 else
+             [Path(args.preview).with_name(f"{Path(args.preview).stem}-{n}{Path(args.preview).suffix}")
+              for n in range(1, len(images) + 1)])
+    dpi = get_label(args.label).dpi
+    for img, path in zip(images, paths):
+        try:
+            img.save(path)
+        except (OSError, ValueError) as e:
+            print(_("Preview cannot be saved: {path} ({error})").format(path=path, error=e),
+                  file=sys.stderr)
+            return 2
+        print(_("Preview: {path} ({width} × {height} mm)").format(
+            path=path, width=format_mm(img.width, dpi), height=format_mm(img.height, dpi)))
+    return 0
+
+
 def _show_printers(model: str, show_all: bool = False) -> int:
     """Gefundene Drucker (USB, eingetragene Netzwerkdrucker, CUPS-Warteschlangen – Bürodrucker nur
     mit ``show_all`` bzw. Einstellung ``cups_all``) und unterstützte Modelle."""
@@ -428,6 +493,12 @@ def main(argv: list[str] | None = None) -> int:
         print("\n".join(families(all=args.all)))
         return 0
 
+    if args.cmd == "parcel" and args.list:
+        return _list_parcel_types(args.country)
+    if args.cmd == "parcel" and not args.file:
+        print(_("Parcel label missing – labelwerk parcel FILE (or --list)"), file=sys.stderr)
+        return 2
+
     if args.cmd == "print" and args.font and args.font_family:
         print(_("--font (font file) and --font-family exclude each other."), file=sys.stderr)
         return 2
@@ -437,6 +508,8 @@ def main(argv: list[str] | None = None) -> int:
         print(e, file=sys.stderr)
         return 2
 
+    if args.cmd == "parcel":
+        return _parcel(args)
     try:
         img = _make_image(args)
     except (ValueError, FileNotFoundError) as e:
diff --git a/src/labelwerk/files.py b/src/labelwerk/files.py
index 3166dfb..ca26632 100644
--- a/src/labelwerk/files.py
+++ b/src/labelwerk/files.py
@@ -3,6 +3,7 @@ Bild-Objekte (``load_image``)."""
 from __future__ import annotations
 
 import struct
+import threading
 import zlib
 from contextlib import contextmanager
 from pathlib import Path
@@ -14,6 +15,9 @@ from .imaging import MAX_PIXELS, limit_size, on_white, to_8bit
 from .labels import DPI, format_mm, get_label, length_limits
 from .render import MARGIN
 
+# PDFium ist nicht threadsicher: jeder Aufruf (hier, Vorschau im Dateidialog, Paketmarken) hält diese Sperre
+PDFIUM_LOCK = threading.RLock()
+
 _IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
 # Bild-Objekte: zusätzlich GIF (erstes Bild), BMP, WebP; SVG rastert die Oberfläche
 _OBJECT_SUFFIXES = (*_IMAGE_SUFFIXES, ".gif", ".bmp", ".webp")
@@ -73,7 +77,7 @@ def _file_dpi(src: Image.Image) -> tuple[float, float]:
 def page_count(path: str | Path) -> int:
     """Seitenzahl einer PDF-Datei (für die Seitenwahl vor ``load_image``)."""
     path = _checked(path, (), "PDF", 1)
-    with _readable(path):
+    with _readable(path), PDFIUM_LOCK:
         import pypdfium2 as pdfium
 
         pdf = pdfium.PdfDocument(path)
@@ -147,14 +151,16 @@ def _load_pdf_page(path: Path, page: int) -> tuple[Image.Image, float]:
 def _pdf_page(path: Path, page: int):
     import pypdfium2 as pdfium
 
-    pdf = pdfium.PdfDocument(path)
-    try:
-        if not 1 <= page <= len(pdf):
-            raise ValueError(ngettext("The PDF has only {count} page.", "The PDF has only {count} pages.",
-                                      len(pdf)).format(count=len(pdf)))
-        yield pdf[page - 1]
-    finally:
-        pdf.close()
+    with PDFIUM_LOCK:
+        pdf = pdfium.PdfDocument(path)
+        try:
+            if not 1 <= page <= len(pdf):
+                raise ValueError(ngettext("The PDF has only {count} page.",
+                                          "The PDF has only {count} pages.",
+                                          len(pdf)).format(count=len(pdf)))
+            yield pdf[page - 1]
+        finally:
+            pdf.close()
 
 
 def _load_image(path: Path, target: int = DPI) -> Image.Image:
diff --git a/src/labelwerk/gui/file_dialog.py b/src/labelwerk/gui/file_dialog.py
index 9ba61c4..ee71314 100644
--- a/src/labelwerk/gui/file_dialog.py
+++ b/src/labelwerk/gui/file_dialog.py
@@ -22,6 +22,7 @@ from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QH
                                QListView, QPushButton, QSplitter, QTreeView, QVBoxLayout, QWidget)
 
 from .. import series, storage
+from ..files import PDFIUM_LOCK
 from ..i18n import _, ngettext, number
 from ..render import Renderer
 from ..storage import SUFFIX
@@ -145,17 +146,18 @@ def _svg(path: Path, size: int, info: str) -> Preview:
 def _pdf(path: Path, page: int, size: int, info: str) -> Preview:
     import pypdfium2 as pdfium
 
-    pdf = pdfium.PdfDocument(path)
-    try:
-        pages = len(pdf)
-        if pages < 1:
-            return _no_preview(info)
-        page = min(max(page, 1), pages)
-        pdf_page = pdf[page - 1]
-        scale = size / max(pdf_page.get_size())
-        image = _qimage(pdf_page.render(scale=scale).to_pil())
-    finally:
-        pdf.close()
+    with PDFIUM_LOCK:                                 # PDFium ist nicht threadsicher
+        pdf = pdfium.PdfDocument(path)
+        try:
+            pages = len(pdf)
+            if pages < 1:
+                return _no_preview(info)
+            page = min(max(page, 1), pages)
+            pdf_page = pdf[page - 1]
+            scale = size / max(pdf_page.get_size())
+            image = _qimage(pdf_page.render(scale=scale).to_pil())
+        finally:
+            pdf.close()
     text = _("Page {page} of {count}").format(page=page, count=pages)
     return Preview(image, f"{info}\n{text}", pages, page)
 
diff --git a/src/labelwerk/parcel.py b/src/labelwerk/parcel.py
new file mode 100644
index 0000000..1a7f900
--- /dev/null
+++ b/src/labelwerk/parcel.py
@@ -0,0 +1,772 @@
+"""Paketmarken umwandeln ohne Qt: Markentypen je Land, Laden, Erkennen, Umwandeln für den Etikettendrucker.
+
+Eine Paketmarke (DHL, Hermes …) kommt als A4/A5/100×150-PDF oder als Bild. Jeder Markentyp schneidet
+feste Bereiche aus (``Piece.src`` in mm auf der Marke), dreht sie (im Uhrzeigersinn) und setzt sie auf
+ein Ausgabe-Etikett (``Piece.dst`` in mm, Rechteck nach dem Drehen) – Barcodes in Originalgröße,
+Adressen und Infotexte kleiner. Die mitgelieferten Typen stehen in ``parcel_data/catalog.json``
+(Herkunft: ``parcel_data/README.md``), eigene Typen in ``$XDG_DATA_HOME/labelwerk/paketmarken``
+(nur die Bereiche; ``arrange`` ordnet sie auf dem Band an).
+
+Ungeprüfte Typen (Bereiche nur aus Testblättern) rücken ihre Kanten an der echten Marke bis zum
+nächsten weißen Rand (``snap``), geprüfte nicht – ihre Kanten sind genau.
+
+``convert`` macht daraus gewöhnliche Etiketten (``Document`` mit einem ``ImageObject`` je Stück):
+das Layout wird auf die bedruckbare Breite des Etiketts skaliert (breiteres Band → größer), bei
+festen Etiketten so weit verkleinert, dass es passt.
+"""
+from __future__ import annotations
+
+import json
+import os
+import re
+from dataclasses import dataclass, field, replace
+from functools import lru_cache
+from pathlib import Path
+
+from PIL import Image
+
+from . import i18n
+from .document import Document, ImageObject
+from .files import PDFIUM_LOCK, _checked, _readable, load_image
+from .i18n import N_, _
+from .labels import get_label, length_limits
+
+CATALOG = Path(__file__).with_name("parcel_data") / "catalog.json"
+LAYOUTS = ("62", "100x150")        # Referenz-Layouts: 62 mm endlos (quer = Seitenhöhe), 100 × 150 mm
+KINDS = ("barcode", "text")        # Barcodes werden nie verkleinert angeordnet
+SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif")
+_IMAGE_FORMATS = ["PNG", "JPEG", "GIF"]
+MAX_FILE_BYTES = 32 * 1024 * 1024
+MAX_PAGES = 20
+MAX_DPI = 600
+MIN_PIECE_MM = 1.0                 # eigene Bereiche: Kanten mindestens so lang
+SNAP_MM = 3.0                      # Kante höchstens so weit nach außen bis zum weißen Rand
+SIZE_TOLERANCE_MM = 4.0
+WIDE_MM = 95.0                     # ab dieser bedruckbaren Breite gilt ein 100×150-Layout
+BARCODE_MIN = 0.97                 # darunter Hinweis: Barcodes verkleinert
+WHITE = 200                        # Grauwert ab dem ein Pixel als weiß gilt (Kanten anpassen)
+MAX_PAGE_PIXELS = 80_000_000       # Seite gerendert höchstens (A4 bei 600 dpi: 35 Mio.)
+MAX_IMAGE_PIXELS = 50_000_000      # Bildmarke höchstens (vor dem Dekodieren geprüft)
+DPI_PLAUSIBLE = (50, 1200)         # andere Angaben in Bildern gelten als fehlend
+ASPECT_TOLERANCE = 0.03            # Bild passt zur Seite/Regel, wenn das Seitenverhältnis ±3 % stimmt
+TURN_MARGIN = 1.15                 # quer liegende Marke: bessere Drehung muss so viel mehr Tinte treffen
+_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
+_own_warnings: list[str] = []
+
+
+class ParcelError(ValueError):
+    """Paketmarke oder Markentyp unbrauchbar (Meldung für Nutzer, übersetzt)."""
+
+
+@dataclass(frozen=True)
+class Piece:
+    """Ein Stück der Marke: ``src`` (x0, y0, x1, y1) in mm auf Seite ``page``, im Uhrzeigersinn um
+    ``rotation`` gedreht auf ``dst`` (x0, y0, x1, y1) in mm des Ausgabe-Etiketts gesetzt."""
+    page: int
+    src: tuple[float, float, float, float]
+    rotation: int
+    dst: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
+    kind: str = "text"
+
+    def turned_mm(self) -> tuple[float, float]:
+        """Größe des Ausschnitts nach dem Drehen (Breite, Höhe) in mm."""
+        w, h = self.src[2] - self.src[0], self.src[3] - self.src[1]
+        return (h, w) if self.rotation in (90, 270) else (w, h)
+
+    def scale(self) -> float:
+        """Maßstab vom Ausschnitt zum Ziel (Mittel aus beiden Achsen)."""
+        w, h = self.turned_mm()
+        return ((self.dst[2] - self.dst[0]) / w + (self.dst[3] - self.dst[1]) / h) / 2
+
+
+@dataclass(frozen=True)
+class Sheet:
+    """Ein Ausgabe-Etikett eines Layouts: Größe (Breite, Höhe) in mm und Stücke in Malreihenfolge."""
+    size_mm: tuple[float, float]
+    pieces: tuple[Piece, ...]
+
+
+@dataclass(frozen=True)
+class ParcelType:
+    id: str
+    names: dict = field(compare=False)                 # {Sprache: Name}
+    country: str = ""
+    carrier: str = ""
+    source_sizes: tuple[tuple[float, float], ...] = ()  # mögliche Seitengrößen der Marke in mm
+    raster: dict | None = field(default=None, compare=False)   # Bildmarke: {"dpi", "x_mm", "y_mm"}
+    detect: dict = field(default_factory=dict, compare=False)  # {"all", "any", "none"}: Begriffe
+    layouts: dict = field(default_factory=dict, compare=False)  # "62"/"100x150" → (Sheet, …)
+    pieces: tuple[Piece, ...] = ()                      # eigene Typen: nur Bereiche (arrange)
+    verified: bool = False
+    own: bool = False
+
+    @property
+    def name(self) -> str:
+        """Name in der Sprache von labelwerk (sonst Englisch, sonst der erste)."""
+        return (self.names.get(i18n.language()) or self.names.get("en")
+                or next(iter(self.names.values()), self.id))
+
+
+# --- Katalog ---------------------------------------------------------------------------
+@lru_cache(maxsize=1)
+def _catalog() -> dict:
+    return json.loads(CATALOG.read_text(encoding="utf-8"))
+
+
+@lru_cache(maxsize=1)
+def _builtin() -> tuple[ParcelType, ...]:
+    return tuple(_type(entry) for entry in _catalog()["types"])
+
+
+def _type(entry: dict, own: bool = False) -> ParcelType:
+    layouts = {key: tuple(Sheet(tuple(s["size_mm"]), tuple(_piece(p) for p in s["pieces"]))
+                          for s in sheets) for key, sheets in entry.get("layouts", {}).items()}
+    source = entry.get("source", {})
+    return ParcelType(entry["id"], dict(entry["names"]), entry.get("country", ""),
+                      entry.get("carrier", ""), tuple(tuple(s) for s in source.get("sizes_mm", ())),
+                      source.get("raster"), dict(entry.get("detect", {})), layouts,
+                      tuple(_piece(p) for p in entry.get("pieces", ())),
+                      bool(entry.get("verified", False)), own)
+
+
+def _piece(p: dict) -> Piece:
+    return Piece(int(p.get("page", 1)), tuple(float(v) for v in p["src"]), int(p["rotation"]),
+                 tuple(float(v) for v in p.get("dst", (0, 0, 0, 0))), p.get("kind", "text"))
+
+
+def countries() -> list[tuple[str, str]]:
+    """Länder mit mitgelieferten Typen: (Kürzel, Name in der Sprache)."""
+    return [(code, _local(entry["names"])) for code, entry in _catalog()["countries"].items()]
+
+
+def carriers(country: str) -> list[tuple[str, str]]:
+    """Dienste eines Lands: (Schlüssel, Name)."""
+    entry = _catalog()["countries"].get(country, {})
+    return [(key, _local(names)) for key, names in entry.get("carriers", {}).items()]
+
+
+def _local(names: dict) -> str:
+    return names.get(i18n.language()) or names.get("en") or next(iter(names.values()), "")
+
+
+def types(country: str | None = None) -> list[ParcelType]:
+    """Mitgelieferte Typen (eines Lands) und danach die eigenen."""
+    return [t for t in _builtin() if country is None or t.country == country] + own_types()
+
+
+def find(type_id: str) -> ParcelType:
+    for ptype in (*_builtin(), *own_types()):
+        if ptype.id == type_id:
+            return ptype
+    raise ParcelError(_("Unknown parcel label type: {id}").format(id=type_id))
+
+
+# --- Eigene Typen ----------------------------------------------------------------------
+def own_dir() -> Path:
+    """Ordner der eigenen Markentypen (``$XDG_DATA_HOME/labelwerk/paketmarken``)."""
+    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
+    return Path(base) / "labelwerk" / "paketmarken"
+
+
+def own_types() -> list[ParcelType]:
+    """Eigene Typen aus ``own_dir`` (jede Datei für sich geprüft; kaputte übergangen, Hinweis in
+    ``own_warnings``)."""
+    _own_warnings.clear()
+    found = []
+    folder = own_dir()
+    if not folder.is_dir():
+        return found
+    for path in sorted(folder.glob("*.json")):
+        try:
+            if path.stat().st_size > 1024 * 1024:
+                raise ParcelError(_("file too large"))
+            found.append(own_from_dict(json.loads(path.read_text(encoding="utf-8"))))
+        except json.JSONDecodeError:
+            _own_warnings.append(_("Own parcel label type {name} not readable: {reason}").format(
+                name=path.name, reason=_("damaged")))
+        except (OSError, ValueError) as e:              # ParcelError ist ValueError
+            _own_warnings.append(_("Own parcel label type {name} not readable: {reason}").format(
+                name=path.name, reason=e))
+    return found
+
+
+def own_warnings() -> list[str]:
+    """Hinweise zu eigenen Typen, die ``own_types`` übergangen hat."""
+    return list(_own_warnings)
+
+
+def own_from_dict(data) -> ParcelType:
+    """Eigenen Typ aus JSON-Daten prüfen und anlegen (fremde Eingabe → ``ParcelError``)."""
+    def bad(what):
+        return ParcelError(_("Invalid parcel label type: {what}").format(what=_(what)))
+    if not isinstance(data, dict):
+        raise bad(N_("data"))
+    type_id = data.get("id")
+    if not isinstance(type_id, str) or not _ID.fullmatch(type_id) \
+            or type_id in {t.id for t in _builtin()}:
+        raise bad(N_("identifier"))
+    names = data.get("names")
+    if not isinstance(names, dict) or not names or not all(
+            isinstance(k, str) and isinstance(v, str) and v.strip() and len(v) <= 200
+            for k, v in names.items()):
+        raise bad(N_("names"))
+    sizes = data.get("source", {}).get("sizes_mm") if isinstance(data.get("source"), dict) else None
+    if not isinstance(sizes, list) or not sizes or not all(_numbers(s, 2, 5, 2000) for s in sizes):
+        raise bad(N_("page sizes"))
+    detect = data.get("detect", {})
+    if not isinstance(detect, dict) or not all(
+            k in ("all", "any", "none") and isinstance(v, list) and len(v) <= 20
+            and all(isinstance(w, str) and 0 < len(w) <= 100 for w in v) for k, v in detect.items()):
+        raise bad(N_("recognition words"))
+    raw = data.get("pieces")
+    if not isinstance(raw, list) or not 1 <= len(raw) <= 30:
+        raise bad(N_("areas"))
+    width, height = max(s[0] for s in sizes), max(s[1] for s in sizes)
+    pieces = []
+    for p in raw:
+        if not isinstance(p, dict) or p.get("rotation") not in (0, 90, 180, 270) \
+                or p.get("kind", "text") not in KINDS or not isinstance(p.get("page", 1), int) \
+                or isinstance(p.get("page", 1), bool) or not 1 <= p.get("page", 1) <= MAX_PAGES \
+                or not _numbers(p.get("src"), 4, 0, max(width, height) + 1):
+            raise bad(N_("areas"))
+        x0, y0, x1, y1 = p["src"]
+        if not (x1 - x0 >= MIN_PIECE_MM and y1 - y0 >= MIN_PIECE_MM and x1 <= width and y1 <= height):
+            raise bad(N_("areas"))
+        pieces.append(Piece(p.get("page", 1), (float(x0), float(y0), float(x1), float(y1)),
+                            p["rotation"], kind=p.get("kind", "text")))
+    return ParcelType(type_id, dict(names), "", "own", tuple(tuple(map(float, s)) for s in sizes),
+                      None, {k: list(v) for k, v in detect.items()}, {}, tuple(pieces), False, True)
+
+
+def _numbers(value, count: int, low: float, high: float) -> bool:
+    return (isinstance(value, list) and len(value) == count
+            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and low <= v <= high
+                    for v in value))
+
+
+def own_to_dict(ptype: ParcelType) -> dict:
+    return {"version": 1, "id": ptype.id, "names": dict(ptype.names),
+            "source": {"sizes_mm": [list(s) for s in ptype.source_sizes]},
+            "detect": {k: list(v) for k, v in ptype.detect.items() if v},
+            "pieces": [{"page": p.page, "src": list(p.src), "rotation": p.rotation, "kind": p.kind}
+                       for p in ptype.pieces]}
+
+
+def save_own(ptype: ParcelType) -> Path:
+    """Eigenen Typ speichern (überschreibt einen gleichnamigen)."""
+    own_from_dict(own_to_dict(ptype))                   # nur Gültiges kommt auf die Platte
+    folder = own_dir()
+    folder.mkdir(parents=True, exist_ok=True)
+    path = folder / f"{ptype.id}.json"
+    tmp = path.with_suffix(".json.tmp")
+    tmp.write_text(json.dumps(own_to_dict(ptype), ensure_ascii=False, indent=1), encoding="utf-8")
+    tmp.replace(path)
+    return path
+
+
+def remove_own(type_id: str) -> None:
+    if not _ID.fullmatch(type_id or ""):
+        raise ParcelError(_("Unknown parcel label type: {id}").format(id=type_id))
+    (own_dir() / f"{type_id}.json").unlink(missing_ok=True)
+
+
+# --- Laden -------------------------------------------------------------------------------
+@dataclass
+class Source:
+    """Geladene Marke: Seitengrößen in mm, Text je Seite; Seitenbilder bei Bedarf (``page``)."""
+    path: Path
+    sizes_mm: list[tuple[float, float]]
+    texts: list[str]
+    image: Image.Image | None = None      # Bildmarke (eine Seite, Graustufen)
+    image_dpi: float | None = None        # Auflösung aus der Datei (None = keine/unplausible Angabe)
+    _cache: dict = field(default_factory=dict, repr=False)
+    _places: dict = field(default_factory=dict, repr=False)
+
+    @property
+    def page_count(self) -> int:
+        return len(self.sizes_mm)
+
+    @property
+    def raster(self) -> bool:
+        return self.image is not None
+
+    def page(self, number: int, dpi: float, ptype: ParcelType | None = None) -> Image.Image:
+        """Seite ``number`` als Graustufenbild bei ``dpi`` – mit ``ptype`` in dessen Seitenfläche
+        (``placement``): passende Seite wie sie ist, quer liegende gedreht, andere Größe (Letter auf
+        A4) oben links auf weißer Fläche; eine Bildmarke nach der Bild-Regel des Typs bzw. auf seine
+        Seitengröße gestreckt. Außerhalb der Marke ist alles weiß."""
+        if not 1 <= number <= self.page_count:
+            raise ParcelError(_("The parcel label has no page {page}.").format(page=number))
+        place_key = (number, ptype.id if ptype is not None else None)
+        if place_key not in self._places:
+            self._places[place_key] = placement(self, ptype, number)
+        place = self._places[place_key]
+        key = (number, round(dpi, 3), place)
+        if key not in self._cache:
+            w_mm, h_mm = place.frame_mm
+            if w_mm * h_mm * (dpi / 25.4) ** 2 > MAX_PAGE_PIXELS:
+                raise ParcelError(_("Parcel label page too large: {name}").format(name=self.path.name))
+            self._cache.clear()                           # nur eine Seite im Speicher
+            self._cache[key] = self._render(number, dpi, place)
+        return self._cache[key]
+
+    def _render(self, number: int, dpi: float, place: "Placement") -> Image.Image:
+        k = dpi / 25.4
+        w_mm, h_mm = place.content_mm                     # Inhalt vor dem Drehen
+        if self.raster:
+            content = self.image.resize((max(1, round(w_mm * k)), max(1, round(h_mm * k))),
+                                        Image.LANCZOS)
+        else:
+            content = _render_pdf(self.path, number, dpi)
+        if place.rotation:
+            content = content.rotate(-place.rotation, expand=True)   # im Uhrzeigersinn
+        frame = Image.new("L", (round(place.frame_mm[0] * k), round(place.frame_mm[1] * k)), 255)
+        frame.paste(content, (round(place.offset_mm[0] * k), round(place.offset_mm[1] * k)))
+        return frame
+
+
+@dataclass(frozen=True)
+class Placement:
+    """Wie eine Seite in der Fläche eines Typs liegt: Fläche, Inhalt (mm vor dem Drehen), Drehung
+    im Uhrzeigersinn, Lage der linken oberen Ecke (mm, nach dem Drehen)."""
+    frame_mm: tuple[float, float]
+    content_mm: tuple[float, float]
+    rotation: int = 0
+    offset_mm: tuple[float, float] = (0.0, 0.0)
+
+
+def placement(source: Source, ptype: ParcelType | None, number: int = 1) -> Placement:
+    """Lage der Seite ``number`` in der Seitenfläche von ``ptype`` (ohne Typ: wie sie ist) – passt sie
+    nicht, ``ParcelError`` (z. B. falscher Typ von Hand gewählt)."""
+    size = source.sizes_mm[number - 1]
+    if ptype is None or not ptype.source_sizes:
+        return Placement(size, size)
+    frame = ptype.source_sizes[0]
+    if source.raster:
+        return _raster_placement(source, ptype, frame)
+    for a, b in ptype.source_sizes:
+        if abs(size[0] - a) <= SIZE_TOLERANCE_MM and abs(size[1] - b) <= SIZE_TOLERANCE_MM:
+            return Placement(frame, size)                 # passt (Letter: oben links auf A4)
+    for a, b in ptype.source_sizes:
+        if abs(size[0] - b) <= SIZE_TOLERANCE_MM and abs(size[1] - a) <= SIZE_TOLERANCE_MM:
+            return Placement(frame, size, _turn(source, ptype, number))
+    raise ParcelError(_("The parcel label ({width} × {height} mm) does not fit the type {name}.")
+                      .format(width=round(size[0]), height=round(size[1]), name=ptype.name))
+
+
+def _raster_placement(source: Source, ptype: ParcelType, frame) -> Placement:
+    img = source.image
+    rule = ptype.raster
+    if rule is not None:                                  # z. B. Amazon-GIF: feste Lage
+        px = rule.get("px")
+        if px and not _aspect_fits(img.size, px):
+            raise ParcelError(_("The image does not fit the type {name}.").format(name=ptype.name))
+        dpi = float(rule.get("dpi", 300)) * (img.width / px[0] if px else 1.0)
+        content = (img.width * 25.4 / dpi, img.height * 25.4 / dpi)
+        return Placement(frame, content, 0, (float(rule.get("x_mm", 0)), float(rule.get("y_mm", 0))))
+    for a, b in ptype.source_sizes:                       # Bild einer ganzen Seite: gestreckt
+        if _aspect_fits(img.size, (a, b)):
+            return Placement(frame, (a, b))
+        if _aspect_fits(img.size, (b, a)):
+            return Placement(frame, (b, a), _turn(source, ptype, 1))
+    raise ParcelError(_("The image does not fit the type {name}.").format(name=ptype.name))
+
+
+def _aspect_fits(size, ref) -> bool:
+    return abs(size[0] / size[1] - ref[0] / ref[1]) <= ASPECT_TOLERANCE * ref[0] / ref[1]
+
+
+def _turn(source: Source, ptype: ParcelType, number: int) -> int:
+    """Quer liegende Marke: Drehung (90 oder 270) mit mehr Tinte in den Bereichen des Typs; liegen
+    beide gleich auf, ist die Richtung nicht eindeutig → ``ParcelError``."""
+    pieces = [p for p in all_pieces(ptype) if p.page == number]
+    dpi = 40.0
+    scores = {}
+    for rotation in (90, 270):
+        place = Placement(ptype.source_sizes[0],
+                          source.sizes_mm[number - 1] if not source.raster
+                          else (ptype.source_sizes[0][1], ptype.source_sizes[0][0]), rotation)
+        page = source._render(number, dpi, place)
+        k = dpi / 25.4
+        ink = 0
+        for piece in pieces:
+            box = tuple(round(v * k) for v in piece.src)
+            ink += sum(page.crop(box).point(lambda v: 255 if v < WHITE else 0).histogram()[255:])
+        scores[rotation] = ink
+    best = max(scores, key=scores.get)
+    other = scores[270 if best == 90 else 90]
+    if scores[best] <= other * TURN_MARGIN:
+        raise ParcelError(_("The parcel label is in landscape and its direction is unclear – save it "
+                            "in portrait first."))
+    return best
+
+
+def _render_pdf(path: Path, number: int, dpi: float) -> Image.Image:
+    import pypdfium2 as pdfium
+    with _readable(path), PDFIUM_LOCK:
+        pdf = pdfium.PdfDocument(path)
+        try:
+            return pdf[number - 1].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
+        finally:
+            pdf.close()
+
+
+def all_pieces(ptype: ParcelType) -> tuple[Piece, ...]:
+    """Alle Bereiche eines Typs (eigene: ``pieces``, sonst die des ersten Layouts)."""
+    if ptype.pieces:
+        return ptype.pieces
+    sheets = next(iter(ptype.layouts.values()), ())
+    return tuple(p for sheet in sheets for p in sheet.pieces)
+
+
+def load(path: str | Path) -> Source:
+    """Marke laden: PDF (Seitengrößen, Text) oder Bild (PNG/JPG/GIF, eine Seite – wie Bild-Objekte
+    gelesen: Transparenz weiß, 16 Bit, EXIF-Lage, Größe begrenzt); fremde Eingabe geprüft (Endung,
+    Dateigröße, Pixel, Seitenzahl) – Fehler als ``ParcelError``."""
+    path = Path(path)
+    try:
+        path = _checked(path, SUFFIXES[1:], "PDF, PNG, JPG, GIF", 1)
+        if path.stat().st_size > MAX_FILE_BYTES:
+            raise ParcelError(_("Parcel label file too large: {name}").format(name=path.name))
+        with _readable(path):
+            if path.suffix.lower() == ".pdf":
+                return _load_pdf(path)
+            with Image.open(path, formats=_IMAGE_FORMATS) as head:   # nur der Kopf: Größe, dpi
+                pixels = head.width * head.height
+                dpi = head.info.get("dpi")
+            if pixels > MAX_IMAGE_PIXELS:
+                raise ParcelError(_("Parcel label image has too many pixels: {name}").format(
+                    name=path.name))
+            dpi = float(dpi[0]) if dpi and dpi[0] else None
+            if dpi is not None and not DPI_PLAUSIBLE[0] <= dpi <= DPI_PLAUSIBLE[1]:
+                dpi = None                                # Angabe unbrauchbar: wie ohne
+            img, used = load_image(path, dpi=dpi or 300.0)
+            img = img.convert("L")
+            size = (img.width * 25.4 / used, img.height * 25.4 / used)
+            return Source(path, [size], [""], img, dpi)
+    except ParcelError:
+        raise
+    except (ValueError, FileNotFoundError) as e:
+        raise ParcelError(str(e)) from e
+
+
+def _load_pdf(path: Path) -> Source:
+    import pypdfium2 as pdfium
+    with PDFIUM_LOCK:
+        pdf = pdfium.PdfDocument(path)
+        try:
+            if len(pdf) < 1:
+                raise ParcelError(_("The PDF has no pages: {name}").format(name=path.name))
+            if len(pdf) > MAX_PAGES:
+                raise ParcelError(_("Parcel label has too many pages: {name}").format(name=path.name))
+            sizes, texts = [], []
+            for page in pdf:
+                w, h = page.get_size()
+                sizes.append((w * 25.4 / 72, h * 25.4 / 72))
+                texts.append(page.get_textpage().get_text_range())
+            return Source(path, sizes, texts)
+        finally:
+            pdf.close()
+
+
+# --- Erkennen ---------------------------------------------------------------------------
+def detect(source: Source, country: str | None = None, label_id: str | None = None,
+           own: list[ParcelType] | None = None) -> list[tuple[ParcelType, float]]:
+    """Passende Typen mit Punktzahl, bester zuerst: Seitengröße muss passen (Bildmarken: Typ mit
+    Bild-Regel), alle Begriffe aus ``all`` im Text, ``any`` zählt mit, ``none`` zählt dagegen; mit
+    ``label_id`` gewinnt bei Gleichstand der Typ mit einem Layout für dieses Etikett."""
+    candidates = [t for t in _builtin() if country is None or t.country == country]
+    candidates += own_types() if own is None else own
+    text = " ".join(source.texts).casefold()
+    wide = _wide(label_id) if label_id else False
+    found = []
+    for order, ptype in enumerate(candidates):
+        if not _fits(source, ptype):
+            continue
+        score = 3.0
+        words = ptype.detect
+        if any(w.casefold() not in text for w in words.get("all", ())):
+            continue
+        score += 2 * len(words.get("all", ()))
+        score += sum(1 for w in words.get("any", ()) if w.casefold() in text)
+        score -= 4 * sum(1 for w in words.get("none", ()) if w.casefold() in text)
+        if ptype.own:
+            score += 0.5                                  # eigener Typ: genauer gemeint
+        if label_id is not None and ptype.layouts:
+            score += 0.25 if ("100x150" in ptype.layouts) == wide else 0.0
+        if score >= 3:
+            found.append((ptype, score, order))
+    found.sort(key=lambda f: (-f[1], not f[0].verified, f[2]))
+    return [(ptype, score) for ptype, score, _ in found]
+
+
+def ambiguous(found: list[tuple[ParcelType, float]]) -> list[ParcelType]:
+    """Gleichstand an der Spitze von ``detect``, den keine geprüfte Vorlage entscheidet: die
+    gleichauf liegenden Typen (dann nicht selbst wählen, sondern fragen); sonst []."""
+    if len(found) < 2 or found[0][0].verified or found[1][1] < found[0][1]:
+        return []
+    return [ptype for ptype, score in found if score == found[0][1]]
+
+
+def _fits(source: Source, ptype: ParcelType) -> bool:
+    """Passt die Marke zum Typ? PDF: Seitengröße (auch quer); Bild: Bild-Regel (Seitenverhältnis der
+    erwarteten Pixel) bzw. Seitenverhältnis einer Seitengröße."""
+    if source.raster:
+        if ptype.raster is not None:
+            px = ptype.raster.get("px")
+            return not px or _aspect_fits(source.image.size, px)
+        return any(_aspect_fits(source.image.size, s) or _aspect_fits(source.image.size, s[::-1])
+                   for s in ptype.source_sizes)
+    return ptype.raster is None and _size_fits(source.sizes_mm[0], ptype.source_sizes)
+
+
+def _size_fits(size: tuple[float, float], sizes) -> bool:
+    w, h = size
+    return any(abs(w - a) <= SIZE_TOLERANCE_MM and abs(h - b) <= SIZE_TOLERANCE_MM
+               or abs(w - b) <= SIZE_TOLERANCE_MM and abs(h - a) <= SIZE_TOLERANCE_MM
+               for a, b in sizes)
+
+
+def _wide(label_id: str) -> bool:
+    label = get_label(label_id)
+    return label.width * 25.4 / label.dpi >= WIDE_MM
+
+
+# --- Kanten anpassen --------------------------------------------------------------------
+def snap(img: Image.Image, box_mm, dpi: float, limit_mm: float = SNAP_MM):
+    """Kanten eines Ausschnitts (mm) nach außen bis zur ersten ganz weißen Zeile/Spalte rücken,
+    wenn sie Inhalt durchschneiden – höchstens ``limit_mm``; ohne weiße Linie in Reichweite bleibt
+    die Kante. Weiße Kanten bleiben, wie sie sind."""
+    k = dpi / 25.4
+    x0, y0, x1, y1 = (round(v * k) for v in box_mm)
+    x0, y0 = max(0, x0), max(0, y0)
+    x1, y1 = min(img.width, x1), min(img.height, y1)
+    if x1 - x0 < 2 or y1 - y0 < 2:
+        return tuple(box_mm)
+    gray = img.convert("L")
+    reach = round(limit_mm * k)
+
+    def white(a0, b0, a1, b1):
+        if a0 < 0 or b0 < 0 or a1 > img.width or b1 > img.height:
+            return True                                   # Seitenrand gilt als weiß
+        return gray.crop((a0, b0, a1, b1)).getextrema()[0] >= WHITE
+
+    edges = list(box_mm)
+    # links, oben, rechts, unten: Linie direkt innerhalb der Kante, dann Schritt für Schritt hinaus
+    for side in range(4):
+        def line(n):
+            if side == 0:
+                return white(x0 - 1 - n, y0, x0 - n, y1)
+            if side == 1:
+                return white(x0, y0 - 1 - n, x1, y0 - n)
+            if side == 2:
+                return white(x1 + n, y0, x1 + n + 1, y1)
+            return white(x0, y1 + n, x1, y1 + n + 1)
+        if line(-1) or line(0):                           # Kante schneidet keinen Inhalt
+            continue
+        for n in range(1, reach + 1):
+            if line(n):                                   # erste weiße Linie außerhalb
+                edges[side] += -n / k if side < 2 else n / k
+                break
+    return tuple(edges)
+
+
+# --- Anordnen (eigene Typen) ---------------------------------------------------------------
+def arrange(pieces, across_mm: float, gap_mm: float = 1.0) -> Sheet:
+    """Stücke nacheinander in Spalten längs des Bands, je Spalte bis zur Breite ``across_mm``:
+    Barcodes 1:1 (nur wenn sie quer nicht passen, kleiner), Texte höchstens so verkleinert, dass sie
+    quer passen."""
+    placed, x, y, column = [], 0.0, 0.0, 0.0
+    for piece in pieces:
+        w, h = piece.turned_mm()
+        s = min(1.0, across_mm / h)
+        w, h = w * s, h * s
+        if y > 0 and y + h > across_mm + 1e-6:            # neue Spalte
+            x, y, column = x + column + gap_mm, 0.0, 0.0
+        placed.append(replace(piece, dst=(x, y, x + w, y + h)))
+        y += h + gap_mm
+        column = max(column, w)
+    return Sheet((x + column, across_mm), tuple(placed))
+
+
+# --- Umwandeln ----------------------------------------------------------------------------
+@dataclass
+class Conversion:
+    documents: list[Document]
+    notes: list[str]
+    layout: str                 # "62", "100x150", "arranged" (Stücke neu angeordnet) oder "own"
+    scale: float                # Faktor vom Layout aufs Etikett
+
+
+def convert(source: Source, ptype: ParcelType, label_id: str, model: str = "QL-600") -> Conversion:
+    """Marke ``source`` nach Typ ``ptype`` in Etiketten für ``label_id`` umwandeln (je Ausgabe-
+    Etikett ein ``Document`` mit einem Bild-Objekt je Stück, Strich/Schwelle 128). Passt die Marke
+    nicht zum Typ (Seitengröße, Bild), ``ParcelError``.
+
+    Layout: ab ``WIDE_MM`` bedruckbarer Breite das 100×150-Layout, sonst das 62-mm-Layout; fehlt das
+    passende (z. B. 1a auf 62 mm), ordnet ``arrange`` die Stücke des vorhandenen neu an („arranged“),
+    eigene Typen immer („own“)."""
+    label = get_label(label_id)
+    if label.shape == "round":
+        raise ParcelError(_("Round labels are not suitable for parcel labels."))
+    for number in sorted({p.page for p in all_pieces(ptype)}):
+        if number > source.page_count:
+            raise ParcelError(_("The parcel label has no page {page}.").format(page=number))
+        placement(source, ptype, number)                  # passt die Marke? sonst Meldung
+    k = label.dpi / 25.4
+    across = label.width / k
+    along = None if label.height is None else label.height / k
+    wide = across >= WIDE_MM
+    if not ptype.layouts:
+        key, sheets = "own", (arrange(ptype.pieces, across),)
+    elif wide and "100x150" in ptype.layouts:
+        key, sheets = "100x150", ptype.layouts["100x150"]
+    elif "62" in ptype.layouts:
+        key, sheets = "62", ptype.layouts["62"]
+    else:                                                 # nur 100×150, aber schmales Band
+        key = "arranged"
+        sheets = tuple(arrange(sheet.pieces, across) for sheet in next(iter(ptype.layouts.values())))
+    feed = label.feed_margin / k
+    max_len = length_limits(model)[1] / k if label.height is None else None
+    documents, notes, scales, shrunk = [], [], [], 1.0
+    for sheet in sheets:
+        doc, f, small = _sheet_document(source, ptype, sheet, label_id, across, along, feed, max_len,
+                                        grow=key in LAYOUTS)
+        documents.append(doc)
+        scales.append(f)
+        shrunk = min(shrunk, small)
+    if shrunk < BARCODE_MIN:
+        notes.append(_("Barcodes shrunk to {percent} % – check before shipping that they can be "
+                       "read.").format(percent=round(shrunk * 100)))
+    return Conversion(documents, notes, key, min(scales))
+
+
+def _sheet_document(source, ptype, sheet, label_id, across, along, feed, max_len, grow):
+    label = get_label(label_id)
+    pieces = sheet.pieces
+    # erste Schätzung des Maßstabs → Auflösung zum Rendern der Marke (Seite höchstens MAX_PAGE_PIXELS)
+    f0, _o = _fit(_bbox(pieces), sheet, across, along, max_len, grow)
+    frame_w, frame_h = ptype.source_sizes[0] if ptype.source_sizes else source.sizes_mm[0]
+    dpi = min(MAX_DPI, label.dpi * max(1.0, max(p.scale() for p in pieces) * f0),
+              25.4 * (MAX_PAGE_PIXELS / (frame_w * frame_h)) ** 0.5 * 0.99)
+    snapped = []
+    for piece in pieces:
+        src = piece.src
+        if not ptype.verified:                            # geprüfte Typen haben genaue Kanten
+            page = source.page(piece.page, dpi, ptype)
+            src = _alone(piece, snap(page, piece.src, dpi), pieces)
+        snapped.append(_grow(piece, src))
+    box = _bbox(snapped)
+    f, horizontal = _fit(box, sheet, across, along, max_len, grow)
+    bx0, by0, bx1, by1 = box
+    content_w, content_h = (bx1 - bx0) * f, (by1 - by0) * f
+    if horizontal:                                         # Seite x längs des Bands
+        off_x = 0.0 if along is None else (along - content_w) / 2
+        off_y = (across - content_h) / 2
+    else:
+        off_x = (across - content_w) / 2
+        off_y = 0.0 if along is None else (along - content_h) / 2
+    objects = []
+    k = dpi / 25.4
+    for n, piece in enumerate(snapped):
+        page = source.page(piece.page, dpi, ptype)
+        img = _crop_white(page, tuple(round(v * k) for v in piece.src))
+        if piece.rotation:
+            img = img.rotate(-piece.rotation, expand=True, fillcolor=255)   # im Uhrzeigersinn
+        img = _mask_covered(img, piece.dst, [p.dst for p in snapped[n + 1:]])
+        obj = ImageObject.from_image(img, dpi, source.path.name, piece.page)
+        dx0, dy0, dx1, dy1 = piece.dst
+        objects.append(replace(obj, x_mm=(dx0 - bx0) * f + off_x, y_mm=(dy0 - by0) * f + off_y,
+                               w_mm=(dx1 - dx0) * f, h_mm=(dy1 - dy0) * f, keep_ratio=False,
+                               mode="line", threshold=128))
+    length = None
+    if along is None:
+        length = (content_w if horizontal else content_h) + 2 * feed
+    doc = Document(label_id, length_mm=length, orientation="horizontal" if horizontal else "vertical",
+                   margin_mm=0.0, objects=objects)
+    barcodes = [p.scale() * f for p in snapped if p.kind == "barcode"]
+    return doc, f, min(barcodes, default=1.0)
+
+
+def _crop_white(page: Image.Image, box) -> Image.Image:
+    """Ausschnitt; was außerhalb der Seite liegt, ist weiß (Pillow füllte schwarz)."""
+    x0, y0, x1, y1 = box
+    out = Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)), 255)
+    out.paste(page.crop((max(0, x0), max(0, y0), min(page.width, x1), min(page.height, y1))),
+              (max(0, -x0), max(0, -y0)))
+    return out
+
+
+def _mask_covered(img: Image.Image, dst, later) -> Image.Image:
+    """Wo spätere Stücke (Malreihenfolge) liegen, wird dieses Stück weiß – sonst verdeckte sein
+    Weiß nichts, seine Tinte aber den Barcode darüber."""
+    x0, y0, x1, y1 = dst
+    fx, fy = img.width / (x1 - x0), img.height / (y1 - y0)
+    boxes = []
+    for a0, b0, a1, b1 in later:
+        l, t, r, b = max(x0, a0), max(y0, b0), min(x1, a1), min(y1, b1)
+        if l < r and t < b:
+            boxes.append((round((l - x0) * fx), round((t - y0) * fy),
+                          round((r - x0) * fx), round((b - y0) * fy)))
+    if boxes:
+        img = img.copy()
+        for box in boxes:
+            img.paste(255, box)
+    return img
+
+
+def _alone(piece: Piece, src, pieces):
+    """Angepasste Kanten nur, wo sie nicht neu in den Ausschnitt eines anderen Stücks reichen
+    (sonst käme dessen Inhalt doppelt aufs Etikett) – solche Kanten bleiben, wie sie waren."""
+    def hits(box, other):
+        return box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]
+    others = [p.src for p in pieces if p is not piece and p.page == piece.page]
+    result = list(piece.src)
+    for side in range(4):
+        trial = list(result)
+        trial[side] = src[side]
+        if not any(hits(trial, o) and not hits(piece.src, o) for o in others):
+            result = trial
+    return tuple(result)
+
+
+def _bbox(pieces):
+    return (min(p.dst[0] for p in pieces), min(p.dst[1] for p in pieces),
+            max(p.dst[2] for p in pieces), max(p.dst[3] for p in pieces))
+
+
+def _fit(box, sheet, across, along, max_len, grow):
+    """Maßstab und Lage (True = Seite x längs des Bands): Endlosband – Breite füllt das Band
+    (``grow``: auch größer), höchstens ``max_len`` lang; festes Etikett – passt hinein, die Lage
+    mit dem größeren Maßstab gewinnt (bei Gleichstand die natürliche: lange Seite längs)."""
+    w, h = box[2] - box[0], box[3] - box[1]
+    natural = sheet.size_mm[0] >= sheet.size_mm[1]
+    options = []
+    for horizontal in (natural, not natural):
+        long_, short = (w, h) if horizontal else (h, w)
+        f = across / short
+        if not grow:
+            f = min(1.0, f)
+        limit = along if along is not None else max_len
+        if limit is not None:
+            f = min(f, limit / long_)
+        options.append((f, horizontal))
+        if along is None:
+            break                                          # Endlosband: natürliche Lage
+    return max(options, key=lambda o: o[0])
+
+
+def _grow(piece: Piece, src) -> Piece:
+    """Stück mit angepasstem Ausschnitt: das Ziel wächst im selben Maßstab mit (Kanten gedreht)."""
+    if tuple(src) == tuple(piece.src):
+        return piece
+    w, h = piece.turned_mm()
+    sx, sy = (piece.dst[2] - piece.dst[0]) / w, (piece.dst[3] - piece.dst[1]) / h
+    dl, dt = piece.src[0] - src[0], piece.src[1] - src[1]       # nach außen positiv
+    dr, db = src[2] - piece.src[2], src[3] - piece.src[3]
+    # Quelle links/oben/rechts/unten → Ziel links/oben/rechts/unten nach Drehung im Uhrzeigersinn
+    left, top, right, bottom = {0: (dl, dt, dr, db), 90: (db, dl, dt, dr),
+                                180: (dr, db, dl, dt), 270: (dt, dr, db, dl)}[piece.rotation]
+    x0, y0, x1, y1 = piece.dst
+    return replace(piece, src=tuple(src),
+                   dst=(x0 - left * sx, y0 - top * sy, x1 + right * sx, y1 + bottom * sy))
diff --git a/src/labelwerk/parcel_data/README.md b/src/labelwerk/parcel_data/README.md
new file mode 100644
index 0000000..54568b2
--- /dev/null
+++ b/src/labelwerk/parcel_data/README.md
@@ -0,0 +1,71 @@
+# Paketmarken-Typen (`catalog.json`)
+
+Welche Bereiche einer Paketmarke (DHL, Hermes …) auf das Etikett kommen und wohin, steht hier als Daten –
+labelwerk (`parcel.py`) liest nur diese Datei. Neue Länder, Dienste und Typen brauchen keinen Code.
+
+## Herkunft
+
+Die Bereiche (`src`) sind gemessene Tatsachen über die Marken; die Anordnung (`dst`) ist nach dem Vorbild
+von paketikett.de nachgemessen. Ermittelt wurden beide mit Testblättern
+(`tools/parcel/make_sheets.py`: 10-mm-Raster, in jeder Zelle ein QR-Code mit ihrer Lage), die ein
+Umwandlungsdienst (paketikett.de) wie eine Marke verarbeitet hat; `tools/parcel/analyze.py` und
+`extract.py` lesen aus dem Ergebnis ab, welcher Bereich mit welcher Drehung und welchem Maßstab wohin
+kam. Es wurde kein Code des Dienstes übernommen. `verified: true` heißt: an einer echten Marke
+nachgeprüft (Original und Ergebnis); alle anderen Typen sind „ungeprüft“ – labelwerk rückt ihre Kanten
+an der echten Marke bis zum nächsten weißen Rand (höchstens 3 mm).
+
+## Format
+
+```json
+{"version": 1,
+ "countries": {"DE": {"names": {"de": "Deutschland", "en": "Germany"},
+                      "carriers": {"dhl": {"de": "DHL", "en": "DHL"}}}},
+ "types": [{
+   "id": "dhl-privat-1", "country": "DE", "carrier": "dhl",
+   "names": {"de": "…", "en": "…"}, "verified": true,
+   "source": {"sizes_mm": [[210, 297]], "raster": {"dpi": 300, "x_mm": 0, "y_mm": 0}},
+   "detect": {"all": ["DHL"], "any": ["Online Frankierung"], "none": ["Warenpost"]},
+   "layouts": {"62": [{"size_mm": [180, 62], "pieces": [
+       {"page": 1, "src": [x0, y0, x1, y1], "rotation": 90, "dst": [x0, y0, x1, y1], "kind": "barcode"}]}]}
+ }]}
+```
+
+- **source**: mögliche Seitengrößen der Marke in mm (± 4 mm, auch quer); `raster` nur für Marken, die als
+  Bild kommen (z. B. GIF): in dieser Auflösung an diese Stelle der Seite gelegt.
+- **detect**: Begriffe im Text der PDF – `all` müssen vorkommen, `any` zählen dafür, `none` dagegen.
+- **layouts**: `"62"` = Referenz 62 mm endlos (Seite quer: x längs des Bands, y quer), `"100x150"` =
+  Etikett 100 × 150 mm (hochkant). Je Layout ein oder mehrere Ausgabe-Etiketten (Retoure: zwei).
+- **pieces** (Malreihenfolge = Reihenfolge, spätere liegen oben): `src` Rechteck auf der Marke in mm (Ursprung
+  oben links), `rotation` Drehung im Uhrzeigersinn, `dst` Rechteck nach dem Drehen auf dem Ausgabe-Etikett in
+  mm (das Stück wird genau darauf skaliert), `kind` `barcode` (nicht verkleinert gemeint) oder `text`.
+
+labelwerk skaliert das Layout auf die bedruckbare Breite des Etiketts (breiteres Band → größer) bzw. passt es in
+ein festes Etikett ein; Barcodes unter 97 % ergeben einen Hinweis.
+
+## Neuen Typ beisteuern
+
+Arbeitsordner außerhalb des Repositorys, z. B. `export LABELWERK_PARCEL_DIR=~/paketmarken-pflege`:
+
+1. Testblätter erzeugen: `QT_QPA_PLATFORM=offscreen python tools/parcel/make_sheets.py`.
+2. Das passende Blatt beim Dienst als Marke dieses Typs umwandeln, Ergebnis in den Arbeitsordner legen.
+3. In `tools/parcel/extract.py` den Typ in `TYPES` eintragen, dann `python tools/parcel/extract.py TYPID` und
+   `python tools/parcel/assemble.py` (braucht numpy, scipy, zxing-cpp – nur zum Pflegen, nicht für labelwerk).
+4. `python tools/parcel/catalog.py "$LABELWERK_PARCEL_DIR/templates.json" src/labelwerk/parcel_data/catalog.json`
+   (Erkennungsbegriffe dort ergänzen), Vergleichsbilder in `check/` ansehen, Tests laufen lassen.
+
+## Eigene Typen
+
+In labelwerk angelegte Typen liegen als `$XDG_DATA_HOME/labelwerk/paketmarken/<id>.json` – nur Bereiche, die
+Anordnung macht labelwerk selbst (Spalten längs des Bands, Barcodes 1:1, Texte höchstens auf Bandbreite verkleinert):
+
+```json
+{"version": 1, "id": "meine-marke", "names": {"de": "Meine Marke"},
+ "source": {"sizes_mm": [[210, 297]]}, "detect": {"all": ["Meine Firma"]},
+ "pieces": [{"page": 1, "src": [10, 10, 110, 60], "rotation": 0, "kind": "text"}]}
+```
+
+Geprüft beim Lesen: Kennung (Kleinbuchstaben, Ziffern, Bindestrich; keine mitgelieferte), Namen, Seitengrößen
+(5–2000 mm), Begriffe, 1–30 Bereiche mit Kanten ≥ 1 mm innerhalb der Seite, Drehung 0/90/180/270, Art
+`barcode`/`text`. Kaputte Dateien werden übergangen (Hinweis).
+
+Echte Marken enthalten Namen und Adressen – sie gehören nie ins Repository.
diff --git a/src/labelwerk/parcel_data/catalog.json b/src/labelwerk/parcel_data/catalog.json
new file mode 100644
index 0000000..02c8d4e
--- /dev/null
+++ b/src/labelwerk/parcel_data/catalog.json
@@ -0,0 +1,2767 @@
+{
+ "version": 1,
+ "countries": {
+  "DE": {
+   "names": {
+    "de": "Deutschland",
+    "en": "Germany"
+   },
+   "carriers": {
+    "dhl": {
+     "de": "DHL",
+     "en": "DHL"
+    },
+    "hermes": {
+     "de": "Hermes",
+     "en": "Hermes"
+    }
+   }
+  }
+ },
+ "types": [
+  {
+   "id": "dhl-privat-1",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL national (dhl.de, Post-Shop, eBay)",
+    "en": "DHL domestic (dhl.de, Post shop, eBay)"
+   },
+   "verified": true,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Online Frankierung",
+     "Sendungsnummer",
+     "Leitcode",
+     "Paket"
+    ],
+    "none": [
+     "Warenpost",
+     "Retoure",
+     "International",
+     "Geschäftskunden",
+     "Amazon"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       180.0,
+       62.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         9.5,
+         24.25,
+         35.25,
+         123.75
+        ],
+        "rotation": 90,
+        "dst": [
+         3.4,
+         2.86,
+         78.09,
+         22.15
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         35.75,
+         54.25,
+         74.0,
+         124.0
+        ],
+        "rotation": 90,
+        "dst": [
+         3.42,
+         23.29,
+         48.78,
+         48.15
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         95.0,
+         47.25,
+         126.0,
+         123.5
+        ],
+        "rotation": 0,
+        "dst": [
+         83.2,
+         1.66,
+         106.39,
+         58.88
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         18.25,
+         24.5,
+         45.75,
+         53.75
+        ],
+        "rotation": 90,
+        "dst": [
+         51.86,
+         9.83,
+         81.41,
+         37.27
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         136.75,
+         38.25,
+         165.25,
+         107.5
+        ],
+        "rotation": 90,
+        "dst": [
+         109.26,
+         3.29,
+         178.5,
+         31.82
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         173.25,
+         38.25,
+         201.75,
+         107.5
+        ],
+        "rotation": 90,
+        "dst": [
+         109.33,
+         32.67,
+         178.48,
+         61.24
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         82.25,
+         24.75,
+         95.5,
+         123.75
+        ],
+        "rotation": 90,
+        "dst": [
+         3.2,
+         48.73,
+         77.45,
+         58.67
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-privat-1a",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL national 100 × 150 mm (dhl.de, Post-Shop, eBay)",
+    "en": "DHL domestic 100 × 150 mm (dhl.de, Post shop, eBay)"
+   },
+   "verified": true,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Online Frankierung",
+     "Sendungsnummer",
+     "Leitcode",
+     "Paket"
+    ],
+    "none": [
+     "Warenpost",
+     "Retoure",
+     "International",
+     "Geschäftskunden",
+     "Amazon"
+    ]
+   },
+   "layouts": {
+    "100x150": [
+     {
+      "size_mm": [
+       100.0,
+       149.9
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         9.25,
+         22.0,
+         126.5,
+         126.75
+        ],
+        "rotation": 90,
+        "dst": [
+         2.54,
+         2.07,
+         70.71,
+         78.31
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         18.0,
+         23.25,
+         46.75,
+         54.5
+        ],
+        "rotation": 90,
+        "dst": [
+         50.05,
+         7.67,
+         81.31,
+         36.29
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         126.25,
+         22.0,
+         202.25,
+         126.75
+        ],
+        "rotation": 90,
+        "dst": [
+         2.55,
+         80.33,
+         96.87,
+         148.76
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-privat-1a-100x150",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL national, Marke 100 × 150 mm",
+    "en": "DHL domestic, 100 × 150 mm label"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      100,
+      150
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Online Frankierung",
+     "Sendungsnummer",
+     "Paket"
+    ],
+    "none": [
+     "Warenpost",
+     "Retoure",
+     "Amazon"
+    ]
+   },
+   "layouts": {
+    "100x150": [
+     {
+      "size_mm": [
+       100.0,
+       149.9
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         9.25,
+         22.0,
+         100.0,
+         126.75
+        ],
+        "rotation": 90,
+        "dst": [
+         2.53,
+         2.07,
+         70.66,
+         61.11
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         18.0,
+         23.25,
+         46.5,
+         54.5
+        ],
+        "rotation": 90,
+        "dst": [
+         49.96,
+         7.73,
+         81.33,
+         36.13
+        ],
+        "kind": "barcode"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-privat-2",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL national/international (dhl.de, Post-Shop, eBay)",
+    "en": "DHL domestic/international (dhl.de, Post shop, eBay)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "International",
+     "Online Frankierung",
+     "Sendungsnummer"
+    ],
+    "none": [
+     "Warenpost",
+     "Retoure",
+     "Geschäftskunden",
+     "Amazon"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       220.0,
+       62.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         9.5,
+         24.25,
+         35.25,
+         123.75
+        ],
+        "rotation": 90,
+        "dst": [
+         3.4,
+         2.86,
+         78.11,
+         22.14
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         35.75,
+         54.25,
+         74.0,
+         124.0
+        ],
+        "rotation": 90,
+        "dst": [
+         3.41,
+         23.3,
+         48.78,
+         48.15
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         95.0,
+         47.25,
+         132.0,
+         123.5
+        ],
+        "rotation": 0,
+        "dst": [
+         83.24,
+         1.65,
+         111.02,
+         58.89
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         18.25,
+         24.25,
+         45.75,
+         54.25
+        ],
+        "rotation": 90,
+        "dst": [
+         51.53,
+         9.79,
+         81.6,
+         37.24
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         133.25,
+         24.75,
+         154.75,
+         124.0
+        ],
+        "rotation": 90,
+        "dst": [
+         118.54,
+         3.34,
+         217.85,
+         24.91
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         162.75,
+         24.75,
+         184.25,
+         124.0
+        ],
+        "rotation": 90,
+        "dst": [
+         118.57,
+         24.87,
+         217.88,
+         46.55
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         192.25,
+         24.5,
+         205.75,
+         124.25
+        ],
+        "rotation": 90,
+        "dst": [
+         118.59,
+         46.59,
+         217.96,
+         60.65
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         82.25,
+         24.75,
+         95.5,
+         123.75
+        ],
+        "rotation": 90,
+        "dst": [
+         3.2,
+         48.73,
+         77.45,
+         58.67
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-privat-3",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Warenpost national",
+    "en": "DHL Warenpost domestic"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Warenpost"
+    ],
+    "any": [
+     "DHL",
+     "Deutsche Post"
+    ],
+    "none": [
+     "International",
+     "CN 23",
+     "CN23",
+     "Zoll",
+     "Customs"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       220.1,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         3.0,
+         12.0,
+         102.5,
+         71.25
+        ],
+        "rotation": 0,
+        "dst": [
+         10.13,
+         2.64,
+         104.6,
+         59.05
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         3.0,
+         77.75,
+         29.0,
+         98.5
+        ],
+        "rotation": 0,
+        "dst": [
+         84.63,
+         2.58,
+         109.37,
+         22.43
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         3.25,
+         113.0,
+         102.5,
+         134.0
+        ],
+        "rotation": 0,
+        "dst": [
+         118.72,
+         2.65,
+         218.02,
+         23.73
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         3.0,
+         140.0,
+         102.5,
+         161.5
+        ],
+        "rotation": 0,
+        "dst": [
+         118.5,
+         23.62,
+         217.99,
+         45.27
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         3.0,
+         168.25,
+         102.5,
+         181.0
+        ],
+        "rotation": 0,
+        "dst": [
+         118.46,
+         45.07,
+         217.98,
+         57.69
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         4.75,
+         4.5,
+         69.0,
+         10.75
+        ],
+        "rotation": 270,
+        "dst": [
+         2.5,
+         2.31,
+         7.5,
+         53.71
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-privat-4",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Warenpost international ohne Zoll",
+    "en": "DHL Warenpost international without customs"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Warenpost"
+    ],
+    "any": [
+     "International"
+    ],
+    "none": [
+     "CN 23",
+     "CN23",
+     "Zoll",
+     "Customs"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       283.6,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         3.25,
+         6.0,
+         102.25,
+         66.5
+        ],
+        "rotation": 0,
+        "dst": [
+         1.87,
+         1.72,
+         96.98,
+         59.9
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         3.0,
+         67.25,
+         95.75,
+         119.75
+        ],
+        "rotation": 0,
+        "dst": [
+         99.91,
+         1.68,
+         183.42,
+         49.05
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         31.5,
+         67.25,
+         102.25,
+         119.75
+        ],
+        "rotation": 0,
+        "dst": [
+         125.55,
+         1.67,
+         189.26,
+         49.01
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         1.75,
+         122.75,
+         102.25,
+         186.5
+        ],
+        "rotation": 0,
+        "dst": [
+         189.24,
+         1.63,
+         279.69,
+         59.14
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-privat-4a",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Warenpost international mit Zoll",
+    "en": "DHL Warenpost international with customs"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Warenpost"
+    ],
+    "any": [
+     "CN 23",
+     "CN23",
+     "Zoll",
+     "Customs",
+     "International"
+    ],
+    "none": []
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       223.5,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         111.75,
+         0.0,
+         163.25,
+         23.75
+        ],
+        "rotation": 270,
+        "dst": [
+         31.68,
+         4.36,
+         55.48,
+         55.98
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         164.75,
+         0.0,
+         210.0,
+         26.0
+        ],
+        "rotation": 270,
+        "dst": [
+         2.03,
+         7.57,
+         30.8,
+         57.41
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         110.75,
+         26.25,
+         182.0,
+         51.75
+        ],
+        "rotation": 270,
+        "dst": [
+         55.46,
+         -0.08,
+         75.8,
+         57.09
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         111.0,
+         52.5,
+         206.5,
+         105.5
+        ],
+        "rotation": 270,
+        "dst": [
+         79.57,
+         2.54,
+         111.3,
+         59.95
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         58.75,
+         0.0,
+         110.25,
+         105.0
+        ],
+        "rotation": 270,
+        "dst": [
+         118.49,
+         8.55,
+         223.53,
+         60.11
+        ],
+        "kind": "barcode"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-privat-4b",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Warenpost international mit Zoll (neu)",
+    "en": "DHL Warenpost international with customs (new)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Warenpost"
+    ],
+    "any": [
+     "CN 23",
+     "CN23",
+     "Zoll",
+     "Customs",
+     "International"
+    ],
+    "none": []
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       276.0,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         3.25,
+         6.0,
+         102.25,
+         66.5
+        ],
+        "rotation": 0,
+        "dst": [
+         1.87,
+         1.72,
+         96.99,
+         59.9
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         3.0,
+         67.25,
+         102.25,
+         131.25
+        ],
+        "rotation": 0,
+        "dst": [
+         99.89,
+         1.67,
+         189.27,
+         59.39
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         1.75,
+         134.0,
+         98.25,
+         197.75
+        ],
+        "rotation": 0,
+        "dst": [
+         189.23,
+         1.71,
+         276.11,
+         59.21
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-business-1",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Geschäftskunden A5 national",
+    "en": "DHL business customers A5 domestic"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      148,
+      210
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Geschäftskunden",
+     "DHL PAKET",
+     "Sendungsnummer"
+    ],
+    "none": [
+     "International",
+     "Warenpost",
+     "Retoure"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       220.1,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         22.75,
+         6.75,
+         124.5,
+         61.5
+        ],
+        "rotation": 0,
+        "dst": [
+         0.74,
+         1.65,
+         89.27,
+         49.36
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.25,
+         69.75,
+         123.25,
+         81.25
+        ],
+        "rotation": 0,
+        "dst": [
+         0.74,
+         49.93,
+         87.79,
+         59.94
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.25,
+         83.0,
+         123.25,
+         124.0
+        ],
+        "rotation": 270,
+        "dst": [
+         93.15,
+         1.7,
+         116.91,
+         59.75
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.25,
+         124.5,
+         123.25,
+         141.5
+        ],
+        "rotation": 0,
+        "dst": [
+         118.34,
+         2.94,
+         218.35,
+         19.92
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.5,
+         148.25,
+         123.25,
+         170.75
+        ],
+        "rotation": 0,
+        "dst": [
+         118.55,
+         19.89,
+         218.36,
+         42.47
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.5,
+         178.0,
+         123.25,
+         194.75
+        ],
+        "rotation": 0,
+        "dst": [
+         118.57,
+         42.47,
+         218.35,
+         59.29
+        ],
+        "kind": "barcode"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-business-2",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Geschäftskunden 105 × 203 mm national",
+    "en": "DHL business customers 105 × 203 mm domestic"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      105,
+      203
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Geschäftskunden",
+     "DHL PAKET",
+     "Sendungsnummer"
+    ],
+    "none": [
+     "International",
+     "Warenpost",
+     "Retoure"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       203.2,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         2.75,
+         3.5,
+         102.75,
+         58.75
+        ],
+        "rotation": 0,
+        "dst": [
+         0.86,
+         0.77,
+         85.89,
+         47.87
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         2.75,
+         66.75,
+         102.5,
+         80.75
+        ],
+        "rotation": 0,
+        "dst": [
+         0.87,
+         48.24,
+         85.69,
+         60.07
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         2.75,
+         120.25,
+         101.5,
+         146.5
+        ],
+        "rotation": 0,
+        "dst": [
+         93.19,
+         1.22,
+         191.92,
+         27.43
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         2.75,
+         150.75,
+         101.5,
+         180.0
+        ],
+        "rotation": 0,
+        "dst": [
+         93.21,
+         27.49,
+         191.92,
+         56.88
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         2.25,
+         58.25,
+         99.5,
+         67.0
+        ],
+        "rotation": 270,
+        "dst": [
+         87.09,
+         2.92,
+         92.12,
+         58.84
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-business-3",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Geschäftskunden 99 × 200 mm national (Shopify)",
+    "en": "DHL business customers 99 × 200 mm domestic (Shopify)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      99,
+      200
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Shopify",
+     "Geschäftskunden",
+     "DHL PAKET",
+     "Sendungsnummer"
+    ],
+    "none": [
+     "International",
+     "Warenpost",
+     "Retoure"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       210.0,
+       62.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         0.0,
+         0.0,
+         98.75,
+         76.5
+        ],
+        "rotation": 0,
+        "dst": [
+         3.39,
+         -0.01,
+         83.43,
+         62.02
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         0.0,
+         77.75,
+         99.0,
+         118.75
+        ],
+        "rotation": 270,
+        "dst": [
+         84.66,
+         1.67,
+         108.39,
+         59.12
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         0.0,
+         119.0,
+         98.75,
+         137.5
+        ],
+        "rotation": 0,
+        "dst": [
+         110.02,
+         1.77,
+         208.86,
+         20.24
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         0,
+         142.75,
+         99,
+         158.25
+        ],
+        "rotation": 0,
+        "dst": [
+         110.09,
+         20.36,
+         209.17,
+         35.79
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         0.0,
+         164.25,
+         99.0,
+         187.5
+        ],
+        "rotation": 0,
+        "dst": [
+         110.01,
+         35.76,
+         209.14,
+         59.09
+        ],
+        "kind": "barcode"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-business-4",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Geschäftskunden A5 international",
+    "en": "DHL business customers A5 international"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      148,
+      210
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "International",
+     "Geschäftskunden",
+     "CN 23",
+     "CN23"
+    ],
+    "none": [
+     "Warenpost",
+     "Retoure"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       220.1,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         22.75,
+         6.75,
+         124.5,
+         61.5
+        ],
+        "rotation": 0,
+        "dst": [
+         0.73,
+         -0.06,
+         89.3,
+         47.68
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.25,
+         69.75,
+         123.25,
+         82.75
+        ],
+        "rotation": 0,
+        "dst": [
+         0.73,
+         48.27,
+         87.8,
+         59.53
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.25,
+         127.0,
+         123.25,
+         143.0
+        ],
+        "rotation": 0,
+        "dst": [
+         118.34,
+         1.22,
+         218.33,
+         17.15
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.25,
+         83.0,
+         123.25,
+         119.0
+        ],
+        "rotation": 270,
+        "dst": [
+         93.14,
+         1.71,
+         114.08,
+         59.76
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.5,
+         148.25,
+         123.25,
+         171.5
+        ],
+        "rotation": 0,
+        "dst": [
+         118.56,
+         17.01,
+         218.36,
+         40.33
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         23.5,
+         177.5,
+         123.25,
+         194.75
+        ],
+        "rotation": 0,
+        "dst": [
+         118.56,
+         40.25,
+         218.35,
+         57.63
+        ],
+        "kind": "barcode"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-business-5",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Geschäftskunden A6 international",
+    "en": "DHL business customers A6 international"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      105,
+      148
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "International",
+     "Geschäftskunden",
+     "CN 23",
+     "CN23"
+    ],
+    "none": [
+     "Warenpost",
+     "Retoure"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       170.0,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         17.0,
+         4.0,
+         87.25,
+         59.0
+        ],
+        "rotation": 0,
+        "dst": [
+         3.45,
+         1.88,
+         73.75,
+         56.97
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         17.0,
+         57.5,
+         87.25,
+         86.75
+        ],
+        "rotation": 270,
+        "dst": [
+         74.4,
+         3.35,
+         96.51,
+         56.16
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         17.0,
+         86.5,
+         85.25,
+         136.25
+        ],
+        "rotation": 0,
+        "dst": [
+         98.21,
+         4.24,
+         170.07,
+         56.72
+        ],
+        "kind": "barcode"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-retour-1",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Retoure (Retourenportal)",
+    "en": "DHL return (returns portal)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Retoure",
+     "Retourenportal",
+     "Return"
+    ],
+    "none": [
+     "Amazon"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       203.3,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         16.25,
+         26.25,
+         91.0,
+         130.5
+        ],
+        "rotation": 90,
+        "dst": [
+         3.33,
+         0.09,
+         86.73,
+         60.05
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         87.25,
+         28.0,
+         158.25,
+         132.25
+        ],
+        "rotation": 90,
+        "dst": [
+         87.96,
+         0.0,
+         171.33,
+         56.94
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         169.5,
+         44.25,
+         192.25,
+         108.75
+        ],
+        "rotation": 0,
+        "dst": [
+         177.84,
+         0.02,
+         198.46,
+         58.35
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-retour-2",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Retoure (neues Retourenportal)",
+    "en": "DHL return (new returns portal)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "DHL"
+    ],
+    "any": [
+     "Retoure",
+     "Retourenportal",
+     "Return"
+    ],
+    "none": [
+     "Amazon"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       183.9,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         7.5,
+         27.75,
+         62.75,
+         119.25
+        ],
+        "rotation": 90,
+        "dst": [
+         1.76,
+         1.58,
+         93.29,
+         56.92
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         99.75,
+         51.5,
+         119.5,
+         103.0
+        ],
+        "rotation": 0,
+        "dst": [
+         71.83,
+         8.43,
+         91.6,
+         60.11
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         120.0,
+         28.25,
+         181.75,
+         119.25
+        ],
+        "rotation": 90,
+        "dst": [
+         97.4,
+         0.09,
+         183.87,
+         58.92
+        ],
+        "kind": "text"
+       }
+      ]
+     },
+     {
+      "size_mm": [
+       87.1,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         64.75,
+         27.5,
+         92.75,
+         119.0
+        ],
+        "rotation": 90,
+        "dst": [
+         0.16,
+         -0.11,
+         87.27,
+         26.78
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-retour-3",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Retoure Amazon (GIF)",
+    "en": "DHL return Amazon (GIF)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ],
+    "raster": {
+     "dpi": 300,
+     "x_mm": -2.5,
+     "y_mm": 189.4,
+     "px": [
+      1800,
+      1200
+     ]
+    }
+   },
+   "detect": {
+    "all": [],
+    "any": [],
+    "none": []
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       160.0,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         4.75,
+         238.25,
+         48.25,
+         285.25
+        ],
+        "rotation": 90,
+        "dst": [
+         3.91,
+         2.98,
+         50.98,
+         46.51
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         78.5,
+         198.75,
+         94.5,
+         285.5
+        ],
+        "rotation": 90,
+        "dst": [
+         71.94,
+         1.73,
+         158.83,
+         17.93
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         56.5,
+         202.25,
+         76.0,
+         282.0
+        ],
+        "rotation": 0,
+        "dst": [
+         50.88,
+         0.04,
+         65.67,
+         60.05
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         103.25,
+         198.75,
+         129.25,
+         285.5
+        ],
+        "rotation": 90,
+        "dst": [
+         71.96,
+         17.84,
+         158.86,
+         44.03
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         135.75,
+         198.75,
+         149.5,
+         285.5
+        ],
+        "rotation": 90,
+        "dst": [
+         71.96,
+         44.0,
+         158.84,
+         57.7
+        ],
+        "kind": "barcode"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "dhl-retour-4",
+   "country": "DE",
+   "carrier": "dhl",
+   "names": {
+    "de": "DHL Retoure Amazon (PDF)",
+    "en": "DHL return Amazon (PDF)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ],
+     [
+      215.9,
+      279.4
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Amazon"
+    ],
+    "any": [
+     "Rücksendung",
+     "Rücksendeetikett",
+     "DHL"
+    ],
+    "none": [
+     "Hermes"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       145.2,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         32.5,
+         102.5,
+         86.0,
+         137.0
+        ],
+        "rotation": 0,
+        "dst": [
+         4.2,
+         4.16,
+         55.11,
+         37.05
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         60.0,
+         177.25,
+         152.75,
+         193.5
+        ],
+        "rotation": 0,
+        "dst": [
+         1.91,
+         42.34,
+         90.12,
+         57.98
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         45.0,
+         148.5,
+         76.75,
+         169.5
+        ],
+        "rotation": 0,
+        "dst": [
+         59.15,
+         16.86,
+         84.46,
+         33.66
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         116.75,
+         115.5,
+         160.5,
+         168.0
+        ],
+        "rotation": 0,
+        "dst": [
+         105.72,
+         5.91,
+         145.14,
+         53.23
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         127.75,
+         102.0,
+         174.5,
+         112.75
+        ],
+        "rotation": 0,
+        "dst": [
+         54.98,
+         3.34,
+         99.4,
+         13.56
+        ],
+        "kind": "text"
+       }
+      ]
+     },
+     {
+      "size_mm": [
+       145.2,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         19.5,
+         225.25,
+         190.25,
+         286.25
+        ],
+        "rotation": 0,
+        "dst": [
+         0.03,
+         0.74,
+         145.23,
+         52.74
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         103.25,
+         225.5,
+         171.0,
+         277.75
+        ],
+        "rotation": 0,
+        "dst": [
+         71.17,
+         0.98,
+         128.86,
+         45.57
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "hermes-1",
+   "country": "DE",
+   "carrier": "hermes",
+   "names": {
+    "de": "Hermes Retoure Amazon",
+    "en": "Hermes return Amazon"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ],
+     [
+      215.9,
+      279.4
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Amazon"
+    ],
+    "any": [
+     "Rücksendung",
+     "Rücksendeetikett",
+     "Hermes"
+    ],
+    "none": [
+     "DHL"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       145.2,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         32.5,
+         102.5,
+         86.0,
+         137.0
+        ],
+        "rotation": 0,
+        "dst": [
+         4.2,
+         4.16,
+         55.11,
+         37.05
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         60.0,
+         177.25,
+         152.75,
+         193.5
+        ],
+        "rotation": 0,
+        "dst": [
+         1.91,
+         42.34,
+         90.12,
+         57.98
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         45.0,
+         148.5,
+         76.75,
+         169.5
+        ],
+        "rotation": 0,
+        "dst": [
+         59.15,
+         16.86,
+         84.46,
+         33.66
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         116.75,
+         115.5,
+         160.5,
+         168.0
+        ],
+        "rotation": 0,
+        "dst": [
+         105.72,
+         5.91,
+         145.14,
+         53.23
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         127.75,
+         102.0,
+         174.5,
+         112.75
+        ],
+        "rotation": 0,
+        "dst": [
+         54.98,
+         3.34,
+         99.4,
+         13.56
+        ],
+        "kind": "text"
+       }
+      ]
+     },
+     {
+      "size_mm": [
+       145.2,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         19.5,
+         225.25,
+         190.25,
+         286.25
+        ],
+        "rotation": 0,
+        "dst": [
+         0.03,
+         0.74,
+         145.23,
+         52.74
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         103.25,
+         225.5,
+         171.0,
+         277.75
+        ],
+        "rotation": 0,
+        "dst": [
+         71.17,
+         0.98,
+         128.86,
+         45.57
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "hermes-2",
+   "country": "DE",
+   "carrier": "hermes",
+   "names": {
+    "de": "Hermes Paketschein (V4.2)",
+    "en": "Hermes parcel label (V4.2)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Hermes"
+    ],
+    "any": [
+     "Paketschein",
+     "Sendungsnummer",
+     "V4.2"
+    ],
+    "none": [
+     "Amazon",
+     "V1.0"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       154.9,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         18.25,
+         32.25,
+         53.25,
+         89.25
+        ],
+        "rotation": 0,
+        "dst": [
+         0.4,
+         0.28,
+         34.56,
+         55.74
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         16.25,
+         99.0,
+         77.0,
+         126.0
+        ],
+        "rotation": 0,
+        "dst": [
+         33.97,
+         32.97,
+         94.88,
+         59.99
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         98.75,
+         25.5,
+         138.75,
+         42.5
+        ],
+        "rotation": 0,
+        "dst": [
+         94.07,
+         0.03,
+         122.1,
+         11.94
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         99.5,
+         52.0,
+         142.5,
+         114.0
+        ],
+        "rotation": 0,
+        "dst": [
+         94.94,
+         13.56,
+         125.12,
+         56.73
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         67.5,
+         76.25,
+         97.5,
+         93.25
+        ],
+        "rotation": 0,
+        "dst": [
+         71.84,
+         16.93,
+         92.83,
+         28.85
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         145.5,
+         49.25,
+         181.75,
+         88.25
+        ],
+        "rotation": 0,
+        "dst": [
+         125.09,
+         15.36,
+         150.48,
+         42.7
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         17.75,
+         16.75,
+         69.25,
+         22.25
+        ],
+        "rotation": 0,
+        "dst": [
+         34.44,
+         2.41,
+         70.49,
+         6.26
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         141.0,
+         13.5,
+         188.0,
+         22.5
+        ],
+        "rotation": 0,
+        "dst": [
+         125.75,
+         2.51,
+         153.95,
+         7.91
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         67.5,
+         25.25,
+         97.5,
+         37.5
+        ],
+        "rotation": 0,
+        "dst": [
+         69.69,
+         8.36,
+         90.69,
+         16.94
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  },
+  {
+   "id": "hermes-3",
+   "country": "DE",
+   "carrier": "hermes",
+   "names": {
+    "de": "Hermes Paketschein (V1.0)",
+    "en": "Hermes parcel label (V1.0)"
+   },
+   "verified": false,
+   "source": {
+    "sizes_mm": [
+     [
+      210,
+      297
+     ]
+    ]
+   },
+   "detect": {
+    "all": [
+     "Hermes"
+    ],
+    "any": [
+     "Paketschein",
+     "Sendungsnummer",
+     "V1.0"
+    ],
+    "none": [
+     "Amazon",
+     "V4.2"
+    ]
+   },
+   "layouts": {
+    "62": [
+     {
+      "size_mm": [
+       169.9,
+       60.0
+      ],
+      "pieces": [
+       {
+        "page": 1,
+        "src": [
+         20.0,
+         29.75,
+         51.0,
+         91.5
+        ],
+        "rotation": 0,
+        "dst": [
+         2.46,
+         -0.11,
+         32.6,
+         59.9
+        ],
+        "kind": "barcode"
+       },
+       {
+        "page": 1,
+        "src": [
+         20.0,
+         98.5,
+         88.5,
+         133.25
+        ],
+        "rotation": 0,
+        "dst": [
+         41.4,
+         23.51,
+         106.55,
+         56.58
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         97.0,
+         36.25,
+         145.5,
+         62.25
+        ],
+        "rotation": 0,
+        "dst": [
+         131.18,
+         1.52,
+         169.89,
+         22.43
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         69.0,
+         77.0,
+         94.5,
+         98.0
+        ],
+        "rotation": 0,
+        "dst": [
+         105.8,
+         16.91,
+         123.73,
+         31.69
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         97.25,
+         76.75,
+         145.75,
+         113.75
+        ],
+        "rotation": 0,
+        "dst": [
+         131.14,
+         27.07,
+         169.94,
+         56.74
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         162.25,
+         117.5,
+         187.75,
+         132.0
+        ],
+        "rotation": 0,
+        "dst": [
+         110.02,
+         48.19,
+         127.81,
+         58.48
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         139.25,
+         13.5,
+         188.0,
+         22.5
+        ],
+        "rotation": 0,
+        "dst": [
+         88.58,
+         2.51,
+         122.71,
+         8.81
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         97.0,
+         24.75,
+         141.75,
+         37.75
+        ],
+        "rotation": 0,
+        "dst": [
+         42.32,
+         8.34,
+         80.36,
+         19.39
+        ],
+        "kind": "text"
+       },
+       {
+        "page": 1,
+        "src": [
+         15.0,
+         15.0,
+         109.0,
+         22.25
+        ],
+        "rotation": 0,
+        "dst": [
+         41.79,
+         2.84,
+         88.79,
+         6.47
+        ],
+        "kind": "text"
+       }
+      ]
+     }
+    ]
+   }
+  }
+ ]
+}
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index ec2a7a1..6b5acf2 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -159,6 +159,11 @@ msgstr "Längs zum Band lässt der Drucker {mm} mm frei – ein kleinerer Rand w
 msgid "Also copies, symbol fonts and fonts without German characters – otherwise only fonts that can write German"
 msgstr "Auch Kopien, Symbolschriften und Schriften ohne deutsche Zeichen – sonst nur Schriften, die Deutsch schreiben können"
 
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Also possible: {ids} (--type)"
+msgstr "Auch möglich: {ids} (--type)"
+
 #: src/labelwerk/gui/main_window.py
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
@@ -215,6 +220,11 @@ msgstr "Barcode ohne Inhalt"
 msgid "Barcodes and QR codes"
 msgstr "Barcodes und QR-Codes"
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Barcodes shrunk to {percent} % – check before shipping that they can be read."
+msgstr "Barcodes verkleinert auf {percent} % – vor dem Versand prüfen, ob sie sich lesen lassen."
+
 #: src/labelwerk/gui/panels/text.py
 #: src/labelwerk/shortcuts.py
 msgid "Bold"
@@ -1045,6 +1055,11 @@ msgstr "Ungültige Adresse: {uri}"
 msgid "Invalid name for the favorite: “{name}” (not empty, not too long, without / and \\ and control characters, not starting with a dot)"
 msgstr "Name für den Favoriten ungültig: „{name}“ (nicht leer, nicht zu lang, ohne / und \\ und Steuerzeichen, nicht mit Punkt beginnend)"
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Invalid parcel label type: {what}"
+msgstr "Ungültiger Markentyp: {what}"
+
 #: src/labelwerk/cups.py
 #, python-brace-format
 msgid "Invalid queue name: {name!r}"
@@ -1604,6 +1619,11 @@ msgstr "Reihenfolge"
 msgid "Orientation"
 msgstr "Ausrichtung"
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Own parcel label type {name} not readable: {reason}"
+msgstr "Eigener Markentyp {name} nicht lesbar: {reason}"
+
 #: src/labelwerk/files.py
 msgid "PDF is encrypted"
 msgstr "PDF ist verschlüsselt"
@@ -1651,6 +1671,44 @@ msgstr "Seite {page} von {count}"
 msgid "Paper"
 msgstr "Papier"
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label file too large: {name}"
+msgstr "Paketmarke zu groß: {name}"
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label has too many pages: {name}"
+msgstr "Paketmarke hat zu viele Seiten: {name}"
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label image has too many pixels: {name}"
+msgstr "Bild der Paketmarke hat zu viele Pixel: {name}"
+
+#: src/labelwerk/cli.py
+msgid "Parcel label missing – labelwerk parcel FILE (or --list)"
+msgstr "Paketmarke fehlt – labelwerk parcel DATEI (oder --list)"
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label page too large: {name}"
+msgstr "Seite der Paketmarke zu groß: {name}"
+
+#: src/labelwerk/cli.py
+msgid "Parcel label type not recognized – specify it with --type (see 'labelwerk parcel --list')."
+msgstr "Markentyp nicht erkannt – mit --type angeben (siehe „labelwerk parcel --list“)."
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Parcel label type not unique – choose one with --type: {ids}"
+msgstr "Markentyp nicht eindeutig – mit --type wählen: {ids}"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Parcel label: {name} ({id})"
+msgstr "Paketmarke: {name} ({id})"
+
 #: src/labelwerk/shortcuts.py
 msgid "Paste"
 msgstr "Einfügen"
@@ -1929,6 +1987,10 @@ msgstr "Drehung {rotate!r} nicht möglich – erlaubt: auto, 0, 90, 180, 270"
 msgid "Round"
 msgstr "Rund"
 
+#: src/labelwerk/parcel.py
+msgid "Round labels are not suitable for parcel labels."
+msgstr "Runde Etiketten eignen sich nicht für Paketmarken."
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Rounded"
 msgstr "Abgerundet"
@@ -2349,6 +2411,11 @@ msgstr "Schreibmodus"
 msgid "Text with automatic font size needs the effective base size (base_pt) for scaling."
 msgstr "Text mit automatischer Schriftgröße braucht die wirksame Grundgröße (base_pt) zum Skalieren."
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The PDF has no pages: {name}"
+msgstr "Die PDF hat keine Seiten: {name}"
+
 #: src/labelwerk/files.py
 #, python-brace-format
 msgid "The PDF has only {count} page."
@@ -2360,6 +2427,11 @@ msgstr[1] "PDF hat nur {count} Seite(n)."
 msgid "The file has no printable content."
 msgstr "Datei enthält keinen druckbaren Inhalt."
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The image does not fit the type {name}."
+msgstr "Das Bild passt nicht zum Typ {name}."
+
 #: src/labelwerk/gui/main_window.py
 msgid "The label is empty. Print anyway?"
 msgstr "Das Etikett ist leer. Trotzdem drucken?"
@@ -2373,6 +2445,20 @@ msgstr "Etikettenrolle ist leer."
 msgid "The loaded roll does not match the label {label!r} – check the roll or choose another label."
 msgstr "Eingelegte Rolle passt nicht zum Etikett {label!r} – Rolle prüfen oder anderes Etikett wählen."
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The parcel label ({width} × {height} mm) does not fit the type {name}."
+msgstr "Die Paketmarke ({width} × {height} mm) passt nicht zum Typ {name}."
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The parcel label has no page {page}."
+msgstr "Die Paketmarke hat keine Seite {page}."
+
+#: src/labelwerk/parcel.py
+msgid "The parcel label is in landscape and its direction is unclear – save it in portrait first."
+msgstr "Die Paketmarke liegt quer und ihre Richtung ist nicht eindeutig – bitte zuerst hochkant speichern."
+
 #: src/labelwerk/gui/main_window.py
 msgid "The table has changed and was read again – check the selection and print again."
 msgstr "Tabelle wurde geändert und neu eingelesen – Auswahl prüfen und erneut drucken."
@@ -2521,6 +2607,11 @@ msgstr "Objektart{where} unbekannt: {kind}"
 msgid "Unknown orientation {orientation!r} – allowed: horizontal, vertical"
 msgstr "Unbekannte Ausrichtung {orientation!r} – erlaubt: horizontal, vertical"
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Unknown parcel label type: {id}"
+msgstr "Unbekannter Markentyp: {id}"
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Unknown printer model {model!r} – allowed: {models}, zpl:203/300/600 or cups:NAME"
@@ -2676,10 +2767,18 @@ msgstr "alle Schriftfamilien, auch Kopien, Symbolschriften und andere Schriftsys
 msgid "also list office printers (CUPS queues with A4/Letter paper)"
 msgstr "auch Bürodrucker zeigen (CUPS-Warteschlangen mit A4/Letter-Papier)"
 
+#: src/labelwerk/parcel.py
+msgid "areas"
+msgstr "Bereiche"
+
 #: src/labelwerk/cli.py
 msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
 msgstr "auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (Warteschlange, siehe 'labelwerk printers'), zpl+file:///dev/usb/lpN bzw. zpl+tcp://IP (Zebra, mit -m zpl:203/300/600)"
 
+#: src/labelwerk/cli.py
+msgid "auto (default: detect) or a type from 'labelwerk parcel --list'"
+msgstr "auto (Standard: erkennen) oder ein Typ aus „labelwerk parcel --list“"
+
 #: src/labelwerk/cli.py
 msgid "auto (default: detected, otherwise from the settings) or e.g. QL-700, zpl:300 (Zebra), cups:NAME; see 'labelwerk printers'"
 msgstr "auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700, zpl:300 (Zebra), cups:NAME; siehe 'labelwerk printers'"
@@ -2692,6 +2791,22 @@ msgstr "auto (Standard: nur drehen wenn nötig) oder Grad im Uhrzeigersinn"
 msgid "bold (default) or --no-bold"
 msgstr "fett (Standard) bzw. --no-bold"
 
+#: src/labelwerk/cli.py
+msgid "convert a parcel label (DHL, Hermes …) for the label printer"
+msgstr "Paketmarke (DHL, Hermes …) für den Etikettendrucker umwandeln"
+
+#: src/labelwerk/cli.py
+msgid "country of the parcel label types (default DE)"
+msgstr "Land der Markentypen (Standard DE)"
+
+#: src/labelwerk/parcel.py
+msgid "damaged"
+msgstr "beschädigt"
+
+#: src/labelwerk/parcel.py
+msgid "data"
+msgstr "Daten"
+
 #: src/labelwerk/cli.py
 msgid "default: from the printer (tcp:// → network)"
 msgstr "Standard: aus dem Drucker (tcp:// → network)"
@@ -2704,6 +2819,10 @@ msgstr "nicht schneiden (Brother; bei CUPS/Zebra stellt das der Treiber bzw. der
 msgid "file is damaged or incomplete"
 msgstr "Datei ist beschädigt oder unvollständig"
 
+#: src/labelwerk/parcel.py
+msgid "file too large"
+msgstr "Datei zu groß"
+
 #: src/labelwerk/storage.py
 msgid "folder missing"
 msgstr "Ordner fehlt"
@@ -2712,6 +2831,10 @@ msgstr "Ordner fehlt"
 msgid "font family, e.g. 'Liberation Sans' (see 'labelwerk fonts')"
 msgstr "Schriftfamilie, z. B. 'Liberation Sans' (siehe 'labelwerk fonts')"
 
+#: src/labelwerk/parcel.py
+msgid "identifier"
+msgstr "Kennung"
+
 #: src/labelwerk/files.py
 msgid "image has too many pixels"
 msgstr "Bild hat zu viele Pixel"
@@ -2773,6 +2896,10 @@ msgstr "installierte Schriftfamilien mit deutschen Zeichen auflisten"
 msgid "list the labels for the model"
 msgstr "Etiketten für das Modell auflisten"
 
+#: src/labelwerk/cli.py
+msgid "list the parcel label types"
+msgstr "Markentypen auflisten"
+
 #: src/labelwerk/cli.py
 msgid "margin all around from the paper edge in mm – the strips the printer leaves free count (about 1.5 mm across, 3 mm along a continuous tape; default from the settings)"
 msgstr "Rand ringsum ab Papierkante in mm – die Streifen, die der Drucker freilässt, zählen mit (quer rund 1,5 mm, längs zum Endlosband 3 mm; Standard aus den Einstellungen)"
@@ -2792,6 +2919,10 @@ msgstr[1] "mehr als {count} Zeilen"
 msgid "name too long"
 msgstr "Name zu lang"
 
+#: src/labelwerk/parcel.py
+msgid "names"
+msgstr "Namen"
+
 #: src/labelwerk/printer.py
 msgid "no answer"
 msgstr "keine Antwort"
@@ -2841,6 +2972,18 @@ msgstr "keine gültige PDF-Datei"
 msgid "only save a preview, do not print"
 msgstr "nur Vorschau speichern, nicht drucken"
 
+#: src/labelwerk/cli.py
+msgid "own"
+msgstr "eigener"
+
+#: src/labelwerk/parcel.py
+msgid "page sizes"
+msgstr "Seitengrößen"
+
+#: src/labelwerk/cli.py
+msgid "parcel label as PDF, PNG, JPG or GIF"
+msgstr "Paketmarke als PDF, PNG, JPG oder GIF"
+
 #: src/labelwerk/cli.py
 msgid "path to a .ttf file"
 msgstr "Pfad zu einer .ttf-Datei"
@@ -2861,6 +3004,10 @@ msgstr "eingelegte Rolle vom Drucker abfragen (druckt nichts)"
 msgid "read error"
 msgstr "Lesefehler"
 
+#: src/labelwerk/parcel.py
+msgid "recognition words"
+msgstr "Erkennungsbegriffe"
+
 #: src/labelwerk/cli.py
 msgid "remove the entry and icon again"
 msgstr "Eintrag und Icon wieder entfernen"
@@ -2894,6 +3041,10 @@ msgstr "unterstrichen"
 msgid "unreadable"
 msgstr "nicht lesbar"
 
+#: src/labelwerk/cli.py
+msgid "untested"
+msgstr "ungeprüft"
+
 #: src/labelwerk/printers.py
 msgid "untested – feedback welcome"
 msgstr "ungeprüft – Rückmeldung erwünscht"
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index c3bde3e..df7fbbc 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -158,6 +158,11 @@ msgstr ""
 msgid "Also copies, symbol fonts and fonts without German characters – otherwise only fonts that can write German"
 msgstr ""
 
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Also possible: {ids} (--type)"
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr ""
@@ -214,6 +219,11 @@ msgstr ""
 msgid "Barcodes and QR codes"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Barcodes shrunk to {percent} % – check before shipping that they can be read."
+msgstr ""
+
 #: src/labelwerk/gui/panels/text.py
 #: src/labelwerk/shortcuts.py
 msgid "Bold"
@@ -1036,6 +1046,11 @@ msgstr ""
 msgid "Invalid name for the favorite: “{name}” (not empty, not too long, without / and \\ and control characters, not starting with a dot)"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Invalid parcel label type: {what}"
+msgstr ""
+
 #: src/labelwerk/cups.py
 #, python-brace-format
 msgid "Invalid queue name: {name!r}"
@@ -1587,6 +1602,11 @@ msgstr ""
 msgid "Orientation"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Own parcel label type {name} not readable: {reason}"
+msgstr ""
+
 #: src/labelwerk/files.py
 msgid "PDF is encrypted"
 msgstr ""
@@ -1634,6 +1654,44 @@ msgstr ""
 msgid "Paper"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label file too large: {name}"
+msgstr ""
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label has too many pages: {name}"
+msgstr ""
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label image has too many pixels: {name}"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "Parcel label missing – labelwerk parcel FILE (or --list)"
+msgstr ""
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Parcel label page too large: {name}"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "Parcel label type not recognized – specify it with --type (see 'labelwerk parcel --list')."
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Parcel label type not unique – choose one with --type: {ids}"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Parcel label: {name} ({id})"
+msgstr ""
+
 #: src/labelwerk/shortcuts.py
 msgid "Paste"
 msgstr ""
@@ -1908,6 +1966,10 @@ msgstr ""
 msgid "Round"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+msgid "Round labels are not suitable for parcel labels."
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Rounded"
 msgstr ""
@@ -2328,6 +2390,11 @@ msgstr ""
 msgid "Text with automatic font size needs the effective base size (base_pt) for scaling."
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The PDF has no pages: {name}"
+msgstr ""
+
 #: src/labelwerk/files.py
 #, python-brace-format
 msgid "The PDF has only {count} page."
@@ -2339,6 +2406,11 @@ msgstr[1] ""
 msgid "The file has no printable content."
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The image does not fit the type {name}."
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "The label is empty. Print anyway?"
 msgstr ""
@@ -2352,6 +2424,20 @@ msgstr ""
 msgid "The loaded roll does not match the label {label!r} – check the roll or choose another label."
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The parcel label ({width} × {height} mm) does not fit the type {name}."
+msgstr ""
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The parcel label has no page {page}."
+msgstr ""
+
+#: src/labelwerk/parcel.py
+msgid "The parcel label is in landscape and its direction is unclear – save it in portrait first."
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "The table has changed and was read again – check the selection and print again."
 msgstr ""
@@ -2500,6 +2586,11 @@ msgstr ""
 msgid "Unknown orientation {orientation!r} – allowed: horizontal, vertical"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Unknown parcel label type: {id}"
+msgstr ""
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Unknown printer model {model!r} – allowed: {models}, zpl:203/300/600 or cups:NAME"
@@ -2655,10 +2746,18 @@ msgstr ""
 msgid "also list office printers (CUPS queues with A4/Letter paper)"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+msgid "areas"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
 msgstr ""
 
+#: src/labelwerk/cli.py
+msgid "auto (default: detect) or a type from 'labelwerk parcel --list'"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "auto (default: detected, otherwise from the settings) or e.g. QL-700, zpl:300 (Zebra), cups:NAME; see 'labelwerk printers'"
 msgstr ""
@@ -2671,6 +2770,22 @@ msgstr ""
 msgid "bold (default) or --no-bold"
 msgstr ""
 
+#: src/labelwerk/cli.py
+msgid "convert a parcel label (DHL, Hermes …) for the label printer"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "country of the parcel label types (default DE)"
+msgstr ""
+
+#: src/labelwerk/parcel.py
+msgid "damaged"
+msgstr ""
+
+#: src/labelwerk/parcel.py
+msgid "data"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "default: from the printer (tcp:// → network)"
 msgstr ""
@@ -2683,6 +2798,10 @@ msgstr ""
 msgid "file is damaged or incomplete"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+msgid "file too large"
+msgstr ""
+
 #: src/labelwerk/storage.py
 msgid "folder missing"
 msgstr ""
@@ -2691,6 +2810,10 @@ msgstr ""
 msgid "font family, e.g. 'Liberation Sans' (see 'labelwerk fonts')"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+msgid "identifier"
+msgstr ""
+
 #: src/labelwerk/files.py
 msgid "image has too many pixels"
 msgstr ""
@@ -2752,6 +2875,10 @@ msgstr ""
 msgid "list the labels for the model"
 msgstr ""
 
+#: src/labelwerk/cli.py
+msgid "list the parcel label types"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "margin all around from the paper edge in mm – the strips the printer leaves free count (about 1.5 mm across, 3 mm along a continuous tape; default from the settings)"
 msgstr ""
@@ -2771,6 +2898,10 @@ msgstr[1] ""
 msgid "name too long"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+msgid "names"
+msgstr ""
+
 #: src/labelwerk/printer.py
 msgid "no answer"
 msgstr ""
@@ -2820,6 +2951,18 @@ msgstr ""
 msgid "only save a preview, do not print"
 msgstr ""
 
+#: src/labelwerk/cli.py
+msgid "own"
+msgstr ""
+
+#: src/labelwerk/parcel.py
+msgid "page sizes"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "parcel label as PDF, PNG, JPG or GIF"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "path to a .ttf file"
 msgstr ""
@@ -2840,6 +2983,10 @@ msgstr ""
 msgid "read error"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+msgid "recognition words"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "remove the entry and icon again"
 msgstr ""
@@ -2873,6 +3020,10 @@ msgstr ""
 msgid "unreadable"
 msgstr ""
 
+#: src/labelwerk/cli.py
+msgid "untested"
+msgstr ""
+
 #: src/labelwerk/printers.py
 msgid "untested – feedback welcome"
 msgstr ""
diff --git a/tools/parcel/README.md b/tools/parcel/README.md
new file mode 100644
index 0000000..ca1c2bd
--- /dev/null
+++ b/tools/parcel/README.md
@@ -0,0 +1,19 @@
+# Werkzeuge: Paketmarken-Typen pflegen
+
+Nur zum Pflegen von `src/labelwerk/parcel_data/catalog.json` – labelwerk selbst braucht sie nicht.
+Benötigt numpy, scipy, zxing-cpp, pypdfium2, Pillow, segno und (für `make_sheets.py`) PySide6.
+
+| Skript | Zweck |
+|---|---|
+| `make_sheets.py [ORDNER]` | Testblätter (A4/A5 hoch/quer, 100×150, 105×203, 103×199) mit QR-Raster |
+| `analyze.py ERGEBNIS.pdf …` | QR-Codes im umgewandelten Ergebnis → Bereiche je Stück (`analyse.json`) |
+| `extract.py [TYPID …]` | genaue Bereiche je Typ (fehlende Stücke, Kanten geschärft) → `result/`, `check/` |
+| `assemble.py` | `result/*.json` → `templates.json` + Bericht |
+| `workdir.py` | Arbeitsordner prüfen (außerhalb des Repositorys) |
+| `catalog.py templates.json catalog.json` | Daten für labelwerk (Erkennung, Seitengrößen, Bild-Regeln) |
+
+Arbeitsordner ist Pflicht: `LABELWERK_PARCEL_DIR=ordner` (bzw. bei `make_sheets.py` als Argument) – dort liegen
+Testblätter, umgewandelte Ergebnisse und alle Ausgaben (`analyse/`, `check/`, `result/`, `templates.json`). Liegt
+der Ordner im Repository, brechen die Werkzeuge ab (`workdir.py`); `.gitignore` deckt die Ausgaben zusätzlich ab.
+Ablauf und Format: `src/labelwerk/parcel_data/README.md`. Echte Marken (Gegenprobe) nur lokal in
+`Original/` mit `Original/originale.json` – nie ins Repository.
diff --git a/tools/parcel/analyze.py b/tools/parcel/analyze.py
new file mode 100644
index 0000000..9bcb8fe
--- /dev/null
+++ b/tools/parcel/analyze.py
@@ -0,0 +1,229 @@
+"""paketikett-Ergebnisse genau auswerten.
+
+1. QR-Codes im Ergebnis lesen (Inhalt „KÜRZEL x y“ = Mitte der Zelle in mm auf dem Testblatt).
+2. Je Code eine affine Abbildung Testblatt(mm) → Ergebnis(px) aus den vier Ecken.
+3. Codes mit gleicher Abbildung = ein ausgeschnittener Bereich; Abbildung aus allen Ecken neu.
+4. Grenzen genau: dunkle Pixel des Ergebnisses, die das (gerenderte) Testblatt unter dieser Abbildung
+   erklärt, zusammenhängend mit den Codes des Bereichs → Rechteck im Ergebnis → zurück aufs Testblatt.
+
+Aufruf: LABELWERK_PARCEL_DIR=ordner python analyze.py ERGEBNIS.pdf [...]
+"""
+import json
+import math
+import sys
+from pathlib import Path
+
+import numpy as np
+import pypdfium2 as pdfium
+import zxingcpp
+from PIL import Image, ImageDraw
+from scipy import ndimage
+
+DPI = 300
+PX = DPI / 25.4
+QR_MM = 7.4
+sys.path.insert(0, str(Path(__file__).parent))
+from workdir import workdir  # noqa: E402
+
+# Arbeitsordner mit Testblättern und umgewandelten Ergebnissen; Ausgaben (Bilder, JSON) ebenfalls dort
+DATA = workdir()
+WORK = DATA
+NAMES = {"A4H": "A4-hoch", "A4Q": "A4-quer", "A5H": "A5-hoch", "A5Q": "A5-quer", "L100": "100x150",
+         "L105": "105x203", "L103": "103x199"}
+OUT = WORK / "analyse"
+_sheets = {}
+
+
+def page_images(path, dpi=DPI):
+    pdf = pdfium.PdfDocument(str(path))
+    for i in range(len(pdf)):
+        page = pdf[i]
+        w, h = page.get_size()
+        img = page.render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
+        yield i, img, (w * 25.4 / 72, h * 25.4 / 72)
+
+
+def sheet(code, sparse):
+    key = (code, sparse)
+    if key not in _sheets:
+        f = DATA / f"testblatt-{NAMES[code]}{'-wenig' if sparse else ''}.pdf"
+        __, img, __ = next(page_images(f, 600))
+        dark = np.asarray(img) < 100
+        k = 600 / 25.4
+        yy, xx = np.indices(dark.shape)
+        on_line = (np.abs(((xx / k) + 5) % 10 - 5) < 0.4) | (np.abs(((yy / k) + 5) % 10 - 5) < 0.4)
+        _sheets[key] = dark & ~on_line                     # nur QR-Module (Linien sind periodisch)
+    return _sheets[key]
+
+
+def decode(img):
+    found = []
+    tile, step = 700, 500
+    for y in range(0, max(1, img.height - 200), step):
+        for x in range(0, max(1, img.width - 200), step):
+            box = (x, y, min(img.width, x + tile), min(img.height, y + tile))
+            for r in zxingcpp.read_barcodes(img.crop(box), formats=zxingcpp.BarcodeFormat.QRCode):
+                p = r.position
+                pts = [(q.x + x, q.y + y) for q in (p.top_left, p.top_right, p.bottom_right, p.bottom_left)]
+                c = np.mean(pts, axis=0)
+                if any(t == r.text and np.linalg.norm(np.mean(q, axis=0) - c) < 15 for t, q in found):
+                    continue
+                found.append((r.text, pts))
+    return found
+
+
+def corners(cx, cy):
+    h = QR_MM / 2
+    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]
+
+
+def fit(src, dst):
+    """Affine Abbildung (2×3) mm → px nach kleinsten Quadraten."""
+    A = np.hstack([np.asarray(src, float), np.ones((len(src), 1))])
+    M, *_ = np.linalg.lstsq(A, np.asarray(dst, float), rcond=None)
+    err = np.abs(A @ M - dst).max()
+    return M.T, err                                      # 2×3
+
+
+def apply(M, pts):
+    pts = np.asarray(pts, float)
+    return pts @ M[:, :2].T + M[:, 2]
+
+
+def group(items):
+    gs = []
+    for it in items:
+        for g in gs:
+            if g["code"] != it["code"]:
+                continue
+            L0, L = g["M"][:, :2], it["M"][:, :2]
+            if np.linalg.norm(L - L0) / np.linalg.norm(L0) > 0.04:
+                continue
+            pred = g["p0"] + L0 @ (np.array(it["c"]) - g["c0"])
+            if np.linalg.norm(pred - it["p"]) < 15:
+                g["items"].append(it)
+                break
+        else:
+            gs.append({"code": it["code"], "M": it["M"], "p0": it["p"], "c0": np.array(it["c"]), "items": [it]})
+    for g in gs:
+        src = [p for it in g["items"] for p in corners(*it["c"])]
+        dst = [p for it in g["items"] for p in it["pts"]]
+        g["M"], g["err"] = fit(src, dst)
+    return gs
+
+
+def seed(g):
+    """Rechteck der gelesenen Codes samt Ruhezone (px)."""
+    pts = np.array([p for it in g["items"] for p in it["pts"]])
+    q = 1.3 * PX * np.linalg.norm(g["M"][:, 0]) / PX
+    return [pts[:, 0].min() - q, pts[:, 1].min() - q, pts[:, 0].max() + q, pts[:, 1].max() + q]
+
+
+def refine(box, others, ink):
+    """Rechteck nach außen erweitern, bis eine ganz weiße Spalte/Zeile kommt (Lücke zwischen den
+    Stücken – innerhalb eines Stücks kreuzen die Rasterlinien jede Spalte), ein anderes Stück beginnt
+    oder das Bild endet."""
+    H, W = ink.shape
+    x0, y0, x1, y1 = (int(round(v)) for v in box)
+    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
+
+    def hits(nx0, ny0, nx1, ny1):
+        return any(nx0 < o[2] and o[0] < nx1 and ny0 < o[3] and o[1] < ny1 for o in others)
+
+    changed = True
+    while changed:
+        changed = False
+        if x0 > 0 and ink[y0:y1, x0 - 1].any() and not hits(x0 - 1, y0, x0, y1):
+            x0 -= 1; changed = True
+        if x1 < W and ink[y0:y1, x1].any() and not hits(x1, y0, x1 + 1, y1):
+            x1 += 1; changed = True
+        if y0 > 0 and ink[y0 - 1, x0:x1].any() and not hits(x0, y0 - 1, x1, y0):
+            y0 -= 1; changed = True
+        if y1 < H and ink[y1, x0:x1].any() and not hits(x0, y1, x1, y1 + 1):
+            y1 += 1; changed = True
+    return x0, y0, x1, y1
+
+
+def describe(M):
+    L = M[:, :2] / PX
+    sx, sy = np.linalg.norm(L[:, 0]), np.linalg.norm(L[:, 1])
+    angle = (math.degrees(math.atan2(L[1, 0], L[0, 0])) + 360) % 360
+    mirror = np.linalg.det(L) < 0
+    return round(angle / 90) % 4 * 90, angle, sx, sy, mirror
+
+
+def analyze(path):
+    sparse = "wenig" in path.name
+    result = {"file": f"{path.parent.name}/{path.name}", "pages": []}
+    for i, img, page_mm in page_images(path):
+        arr = np.asarray(img)
+        dark = arr < 128
+        items = []
+        for text, pts in decode(img):
+            try:
+                code, cx, cy = text.split()
+                c = (float(cx), float(cy))
+            except ValueError:
+                continue
+            M, err = fit(corners(*c), pts)
+            if err < 6:
+                items.append({"code": code, "c": c, "pts": pts, "M": M, "p": np.mean(pts, axis=0)})
+        regions = []
+        canvas = img.convert("RGB")
+        draw = ImageDraw.Draw(canvas)
+        ink = arr < 245
+        gs = group(items)
+        seeds = [seed(g) for g in gs]
+        boxes = [list(refine(seeds[n], [s for m, s in enumerate(seeds) if m != n], ink)) for n in range(len(gs))]
+        # aneinanderstoßende Stücke: Grenze mitten in der Lücke zwischen den gelesenen Codes
+        for a in range(len(gs)):
+            for b in range(len(gs)):
+                A_, B_ = boxes[a], boxes[b]
+                if a == b or not (A_[0] < B_[2] and B_[0] < A_[2] and A_[1] < B_[3] and B_[1] < A_[3]):
+                    continue
+                sa, sb = seeds[a], seeds[b]
+                if sa[2] <= sb[0]:                       # a links von b
+                    m = round((sa[2] + sb[0]) / 2); A_[2] = min(A_[2], m); B_[0] = max(B_[0], m)
+                elif sa[3] <= sb[1]:                     # a über b
+                    m = round((sa[3] + sb[1]) / 2); A_[3] = min(A_[3], m); B_[1] = max(B_[1], m)
+        for n, g in enumerate(gs):
+            box = boxes[n]
+            x0, y0, x1, y1 = box
+            A = np.vstack([g["M"], [0, 0, 1]])
+            Ai = np.linalg.inv(A)
+            cs = apply(Ai[:2], [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
+            s0, s1 = cs.min(axis=0), cs.max(axis=0)
+            rot, angle, sx, sy, mirror = describe(g["M"])
+            regions.append({"code": g["code"], "codes": len(g["items"]),
+                            "src_mm": [round(v, 1) for v in (*s0, *s1)],
+                            "dst_mm": [round(v / PX, 1) for v in (x0, y0, x1, y1)],
+                            "rot": rot, "angle": round(angle, 2), "scale": [round(sx, 3), round(sy, 3)],
+                            "mirror": bool(mirror), "fit_px": round(float(g["err"]), 1), "M": g["M"].tolist()})
+            draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=3)
+            draw.text((x0 + 6, y0 + 6), f"{s0[0]:.0f},{s0[1]:.0f}", fill=(255, 0, 0))
+        regions.sort(key=lambda r: (r["dst_mm"][0], r["dst_mm"][1]))
+        result["pages"].append({"size_mm": [round(v, 1) for v in page_mm], "codes": len(items), "regions": regions})
+        OUT.mkdir(exist_ok=True)
+        canvas.save(OUT / f"{path.parent.name}-{path.stem[:45]}-{i + 1}.png".replace(" ", "_"))
+    return result
+
+
+def main(paths):
+    allres = []
+    for p in paths:
+        r = analyze(Path(p))
+        allres.append(r)
+        print(f"\n=== {r['file']}")
+        for i, pg in enumerate(r["pages"]):
+            print(f"Seite {i + 1}: {pg['size_mm'][0]} × {pg['size_mm'][1]} mm, {pg['codes']} Codes")
+            for g in pg["regions"]:
+                s, d = g["src_mm"], g["dst_mm"]
+                print(f"  {g['code']:4s} Quelle {s[0]:6.1f},{s[1]:6.1f} – {s[2]:6.1f},{s[3]:6.1f}"
+                      f"  → Ziel {d[0]:6.1f},{d[1]:5.1f} – {d[2]:6.1f},{d[3]:5.1f}"
+                      f"  {g['rot']:3d}° ({g['angle']:6.2f})  Maßstab {g['scale'][0]:.3f}/{g['scale'][1]:.3f}"
+                      f"{'  GESPIEGELT' if g['mirror'] else ''}  [{g['codes']}]")
+    (WORK / "analyse.json").write_text(json.dumps(allres, indent=1, ensure_ascii=False))
+
+
+if __name__ == "__main__":
+    main(sys.argv[1:])
diff --git a/tools/parcel/assemble.py b/tools/parcel/assemble.py
new file mode 100644
index 0000000..f2c46e7
--- /dev/null
+++ b/tools/parcel/assemble.py
@@ -0,0 +1,125 @@
+"""result/*.json → templates.json (Layout-Format der Spec) + templates-bericht.txt."""
+import json
+import sys
+from pathlib import Path
+
+PX = 300 / 25.4
+
+
+def dst_of(p):
+    M = p["M"]; src = p["src"]
+    xs, ys = [], []
+    for x, y in ((src[0], src[1]), (src[2], src[1]), (src[2], src[3]), (src[0], src[3])):
+        xs.append(M[0][0] * x + M[0][1] * y + M[0][2])
+        ys.append(M[1][0] * x + M[1][1] * y + M[1][2])
+    return [min(xs) / PX, min(ys) / PX, max(xs) / PX, max(ys) / PX]
+
+
+def piece(p):
+    """Kanten auf 0,25 mm; Ziel aus der Abbildung für genau diese Kanten (0,01 mm)."""
+    src = [round(v * 4) / 4 for v in p["src"]]
+    M = p["M"]
+    xs, ys = [], []
+    for x, y in ((src[0], src[1]), (src[2], src[1]), (src[2], src[3]), (src[0], src[3])):
+        xs.append(M[0][0] * x + M[0][1] * y + M[0][2])
+        ys.append(M[1][0] * x + M[1][1] * y + M[1][2])
+    return {"page": p["page"], "src": src, "rotation": p["rotation"],
+            "dst": [round(min(xs) / PX, 2), round(min(ys) / PX, 2), round(max(xs) / PX, 2), round(max(ys) / PX, 2)],
+            "scale": p["scale"], "kind": p["kind"]}
+
+def inv_map(M, x, y):
+    """px (Ergebnis) → mm (Quelle)."""
+    import numpy as np
+    A = np.vstack([np.array(M), [0, 0, 1]])
+    q = np.linalg.solve(A, [x, y, 1])
+    return q[0], q[1]
+
+
+def tidy(pieces, size_mm):
+    """Ziele auf die Seite beschneiden; aufeinanderliegende Streifen (Überlappung über die volle
+    Breite bzw. Höhe) an der Grenze trennen – so hängt nichts von der Malreihenfolge ab, wo es nicht
+    nötig ist. Quelle passend nachgeführt (Abbildung M)."""
+    W, H = size_mm
+
+    def set_dst(p, d):
+        pts = [inv_map(p["M"], d[0] * PX, d[1] * PX), inv_map(p["M"], d[2] * PX, d[3] * PX)]
+        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
+        p["src"] = [min(xs), min(ys), max(xs), max(ys)]
+        p["_dst"] = d
+
+    for p in pieces:
+        d = list(p["_dst"])
+        d = [max(0.0, d[0]), max(0.0, d[1]), min(W, d[2]), min(H, d[3])]
+        if d != p["_dst"]:
+            set_dst(p, d)
+    for j in range(len(pieces)):
+        for i in range(j):
+            a, b = pieces[i]["_dst"], pieces[j]["_dst"]
+            ox = min(a[2], b[2]) - max(a[0], b[0]); oy = min(a[3], b[3]) - max(a[1], b[1])
+            if ox <= 0.3 or oy <= 0.3:
+                continue
+            wa, ha = a[2] - a[0], a[3] - a[1]; wb, hb = b[2] - b[0], b[3] - b[1]
+            d = list(a)
+            if ox >= 0.9 * min(wa, wb) and oy < 0.5 * min(ha, hb):      # übereinander gestapelt
+                if a[1] < b[1]: d[3] = b[1]
+                else: d[1] = b[3]
+            elif oy >= 0.9 * min(ha, hb) and ox < 0.5 * min(wa, wb):    # nebeneinander
+                if a[0] < b[0]: d[2] = b[0]
+                else: d[0] = b[2]
+            else:
+                continue                                                # echtes Darüberlegen
+            set_dst(pieces[i], d)
+
+
+sys.path.insert(0, str(Path(__file__).parent))
+from workdir import workdir  # noqa: E402
+
+HERE = workdir()                        # Arbeitsordner (result/ → templates.json)
+ORDER = ["dhl-privat-1", "dhl-privat-1a", "dhl-privat-1a-100x150", "dhl-privat-2", "dhl-privat-3", "dhl-privat-4",
+         "dhl-privat-4a", "dhl-privat-4b", "dhl-business-1", "dhl-business-2", "dhl-business-3", "dhl-business-4",
+         "dhl-business-5", "dhl-retour-1", "dhl-retour-2", "dhl-retour-3", "dhl-retour-4", "hermes-1", "hermes-2",
+         "hermes-3"]
+
+
+def main():
+    types, rows = [], []
+    for tid in ORDER:
+        f = HERE / "result" / f"{tid}.json"
+        if not f.exists():
+            rows.append(f"{tid}: FEHLT")
+            continue
+        r = json.loads(f.read_text())
+        layouts = {}
+        for fmt, labels in r["layouts"].items():
+            layouts[fmt] = []
+            for lab in labels:
+                w, h = lab["size_mm"]
+                for p in lab["pieces"]:
+                    p["_dst"] = dst_of(p)
+                tidy(lab["pieces"], (w, h))
+                layouts[fmt].append({
+                    "size_mm": [w, h], "length_mm": max(w, h), "height_mm": min(w, h),
+                    "pieces": [piece(p) for p in lab["pieces"]]})
+        types.append({"id": r["id"], "names": r["names"], "country": r["country"], "carrier": r["carrier"],
+                      "source": r["source"], "verified": r["verified"], "layouts": layouts})
+        fmt = next(iter(layouts))
+        n = sum(len(l["pieces"]) for l in layouts[fmt])
+        lengths = " + ".join(f"{l['size_mm'][0]:g}×{l['size_mm'][1]:g}" for l in layouts[fmt])
+        dev = ", ".join(f"S{c['page']} {c['mismatch_pct']} %"
+                        + (f" (Original {c['original_mismatch_pct'][1]} %)" if "original_mismatch_pct" in c else "")
+                        for c in r["check"])
+        rows.append(f"{tid:24s} {n:2d} Stücke  {lengths:20s}  Abweichung {dev}  "
+                    f"{'verifiziert' if r['verified'] else 'ungeprüft'}")
+    note = ("Koordinaten in mm. src: Rechteck auf der Quellseite (x nach rechts, y nach unten, Ursprung oben links).\n"
+            "rotation: Drehung im Uhrzeigersinn von Quelle zu Ziel. dst: Rechteck [x0, y0, x1, y1] des gedrehten\n"
+            "Stücks auf der Ausgabeseite size_mm (x nach rechts, y nach unten) – das Stück wird genau auf dieses\n"
+            "Rechteck skaliert; scale: mittlerer Maßstab (zur Information, kind: barcode bei ≈ 1).\n"
+            "Reihenfolge der Stücke = Malreihenfolge (spätere liegen oben).\n")
+    out = {"format": 1, "note": note, "types": types}
+    (HERE / "templates.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
+    (HERE / "templates-bericht.txt").write_text(note + "\n" + "\n".join(rows) + "\n")
+    print("\n".join(rows))
+
+
+if __name__ == "__main__":
+    main()
diff --git a/tools/parcel/catalog.py b/tools/parcel/catalog.py
new file mode 100644
index 0000000..de3e274
--- /dev/null
+++ b/tools/parcel/catalog.py
@@ -0,0 +1,98 @@
+"""templates.json (Auswertung) → src/labelwerk/parcel_data/catalog.json (Daten für labelwerk).
+
+Aufruf: python catalog.py templates.json ../../src/labelwerk/parcel_data/catalog.json
+Erkennungs-Begriffe, weitere Seitengrößen und Bild-Regeln stehen hier von Hand."""
+import json
+import sys
+from pathlib import Path
+
+src = json.loads(Path(sys.argv[1]).read_text())
+out = Path(sys.argv[2])
+
+A4, LETTER, A5, A6 = [210, 297], [215.9, 279.4], [148, 210], [105, 148]
+NOT_INTL = ["International", "CN 23", "CN23", "Zoll", "Customs"]
+DETECT = {
+    "dhl-privat-1": {"all": ["DHL"], "any": ["Online Frankierung", "Sendungsnummer", "Leitcode", "Paket"],
+                     "none": ["Warenpost", "Retoure", "International", "Geschäftskunden", "Amazon"]},
+    "dhl-privat-1a": {"all": ["DHL"], "any": ["Online Frankierung", "Sendungsnummer", "Leitcode", "Paket"],
+                      "none": ["Warenpost", "Retoure", "International", "Geschäftskunden", "Amazon"]},
+    "dhl-privat-1a-100x150": {"all": ["DHL"], "any": ["Online Frankierung", "Sendungsnummer", "Paket"],
+                              "none": ["Warenpost", "Retoure", "Amazon"]},
+    "dhl-privat-2": {"all": ["DHL"], "any": ["International", "Online Frankierung", "Sendungsnummer"],
+                     "none": ["Warenpost", "Retoure", "Geschäftskunden", "Amazon"]},
+    "dhl-privat-3": {"all": ["Warenpost"], "any": ["DHL", "Deutsche Post"], "none": NOT_INTL},
+    "dhl-privat-4": {"all": ["Warenpost"], "any": ["International"], "none": ["CN 23", "CN23", "Zoll", "Customs"]},
+    "dhl-privat-4a": {"all": ["Warenpost"], "any": ["CN 23", "CN23", "Zoll", "Customs", "International"], "none": []},
+    "dhl-privat-4b": {"all": ["Warenpost"], "any": ["CN 23", "CN23", "Zoll", "Customs", "International"], "none": []},
+    "dhl-business-1": {"all": ["DHL"], "any": ["Geschäftskunden", "DHL PAKET", "Sendungsnummer"],
+                       "none": ["International", "Warenpost", "Retoure"]},
+    "dhl-business-2": {"all": ["DHL"], "any": ["Geschäftskunden", "DHL PAKET", "Sendungsnummer"],
+                       "none": ["International", "Warenpost", "Retoure"]},
+    "dhl-business-3": {"all": ["DHL"], "any": ["Shopify", "Geschäftskunden", "DHL PAKET", "Sendungsnummer"],
+                       "none": ["International", "Warenpost", "Retoure"]},
+    "dhl-business-4": {"all": ["DHL"], "any": ["International", "Geschäftskunden", "CN 23", "CN23"],
+                       "none": ["Warenpost", "Retoure"]},
+    "dhl-business-5": {"all": ["DHL"], "any": ["International", "Geschäftskunden", "CN 23", "CN23"],
+                       "none": ["Warenpost", "Retoure"]},
+    "dhl-retour-1": {"all": ["DHL"], "any": ["Retoure", "Retourenportal", "Return"], "none": ["Amazon"]},
+    "dhl-retour-2": {"all": ["DHL"], "any": ["Retoure", "Retourenportal", "Return"], "none": ["Amazon"]},
+    "dhl-retour-3": {"all": [], "any": [], "none": []},
+    "dhl-retour-4": {"all": ["Amazon"], "any": ["Rücksendung", "Rücksendeetikett", "DHL"], "none": ["Hermes"]},
+    "hermes-1": {"all": ["Amazon"], "any": ["Rücksendung", "Rücksendeetikett", "Hermes"], "none": ["DHL"]},
+    # Versionskennung, die Hermes auf den Schein druckt (so heißen die Typen bei paketikett.de)
+    "hermes-2": {"all": ["Hermes"], "any": ["Paketschein", "Sendungsnummer", "V4.2"], "none": ["Amazon", "V1.0"]},
+    "hermes-3": {"all": ["Hermes"], "any": ["Paketschein", "Sendungsnummer", "V1.0"], "none": ["Amazon", "V4.2"]},
+}
+SOURCES = {"dhl-retour-4": [A4, LETTER], "hermes-1": [A4, LETTER]}
+# Amazon-GIF (6 × 4 Zoll, 300 dpi): Lage auf der A4-Seite geschätzt (meiste Tinte in den Stücken)
+RASTER = {"dhl-retour-3": {"dpi": 300, "x_mm": -2.5, "y_mm": 189.4, "px": [1800, 1200]}}
+
+
+def clamp(p, size):
+    """Ausschnitt auf die Seite begrenzen; das Ziel schrumpft im selben Maßstab mit (Drehung beachtet)."""
+    x0, y0, x1, y1 = p["src"]
+    w, h = size
+    nx0, ny0, nx1, ny1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
+    dl, dt, dr, db = nx0 - x0, ny0 - y0, x1 - nx1, y1 - ny1          # nach innen positiv
+    if not any((dl, dt, dr, db)):
+        return p
+    tw, th = (y1 - y0, x1 - x0) if p["rotation"] in (90, 270) else (x1 - x0, y1 - y0)
+    sx = (p["dst"][2] - p["dst"][0]) / tw
+    sy = (p["dst"][3] - p["dst"][1]) / th
+    left, top, right, bottom = {0: (dl, dt, dr, db), 90: (db, dl, dt, dr),
+                                180: (dr, db, dl, dt), 270: (dt, dr, db, dl)}[p["rotation"]]
+    a, b, c, d = p["dst"]
+    return dict(p, src=[nx0, ny0, nx1, ny1],
+                dst=[a + left * sx, b + top * sy, c - right * sx, d - bottom * sy])
+
+
+def r(v):
+    return [round(x, 2) for x in v]
+
+
+types = []
+for t in src["types"]:
+    layouts = {}
+    sizes = SOURCES.get(t["id"], [t["source"]["size_mm"]])
+    max_size = (max(a for a, _ in sizes), max(b for _, b in sizes))
+    for key, sheets in t["layouts"].items():
+        layouts[key] = [{"size_mm": r(s["size_mm"]), "pieces": [
+            {"page": p["page"], "src": r(p["src"]), "rotation": p["rotation"], "dst": r(p["dst"]),
+             "kind": "barcode" if p["scale"] > 1.03 or abs(p["scale"] - 1) < 0.03 else "text"}
+            for p in (clamp(q, max_size) for q in s["pieces"])]} for s in sheets]
+    source = {"sizes_mm": SOURCES.get(t["id"], [t["source"]["size_mm"]])}
+    if t["id"] in RASTER:
+        source["raster"] = RASTER[t["id"]]
+    types.append({"id": t["id"], "country": t["country"], "carrier": t["carrier"], "names": t["names"],
+                  "verified": bool(t.get("verified")), "source": source, "detect": DETECT[t["id"]],
+                  "layouts": layouts})
+
+catalog = {
+    "version": 1,
+    "countries": {"DE": {"names": {"de": "Deutschland", "en": "Germany"},
+                         "carriers": {"dhl": {"de": "DHL", "en": "DHL"},
+                                      "hermes": {"de": "Hermes", "en": "Hermes"}}}},
+    "types": types,
+}
+out.write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
+print(len(types), "Typen →", out)
diff --git a/tools/parcel/extract.py b/tools/parcel/extract.py
new file mode 100644
index 0000000..6282013
--- /dev/null
+++ b/tools/parcel/extract.py
@@ -0,0 +1,479 @@
+"""Genaue Bereiche je paketikett-Typ: Stücke aus den QR-Codes (analyze2), fehlende Stücke per
+Kreuzkorrelation, Kanten per Nachbau-Vergleich geschärft.
+
+LABELWERK_PARCEL_DIR=ordner python extract.py [TYPID …]  (Konfiguration in TYPES unten) → check/<id>-<n>.png, result/<id>.json
+"""
+import json
+import sys
+from pathlib import Path
+
+import numpy as np
+from PIL import Image
+from scipy import ndimage, signal
+
+sys.path.insert(0, str(Path(__file__).parent))
+import analyze as A  # noqa: E402
+
+HERE = A.WORK
+D = A.DATA
+PX = A.PX
+SHEET = {"A4H": ("testblatt-A4-hoch.pdf", (210, 297)), "A5H": ("testblatt-A5-hoch.pdf", (148, 210)),
+         "L100": ("testblatt-100x150.pdf", (100, 150))}
+
+# id: (Ordner, Datei, Name de, Name en, Dienst, Quelle mm, Format)
+TYPES = {
+    "dhl-privat-1": ("DHL Privat", "1 DHL National [dhl.de][shop.deutschepost.de][ebay] - a4 hoch.pdf",
+                     "DHL national (dhl.de, Post-Shop, eBay)", "DHL domestic (dhl.de, Post shop, eBay)",
+                     "dhl", (210, 297), "62"),
+    "dhl-privat-1a": ("DHL Privat", "1a DHL National [dhl.de][shop.deutschepost.de][ebay] 100x150 - a4 hoch.pdf",
+                      "DHL national 100 × 150 mm (dhl.de, Post-Shop, eBay)",
+                      "DHL domestic 100 × 150 mm (dhl.de, Post shop, eBay)", "dhl", (210, 297), "100x150"),
+    "dhl-privat-1a-100x150": ("DHL Privat", "1a 1 DHL National [dhl.de][shop.deutschepost.de][ebay] - 100x150.pdf",
+                              "DHL national, Marke 100 × 150 mm", "DHL domestic, 100 × 150 mm label", "dhl",
+                              (100, 150), "100x150"),
+    "dhl-privat-2": ("DHL Privat", "2 DHL National International [dhl.de][shop.deutschepost.de][ebay] - a4 hoch.pdf",
+                     "DHL national/international (dhl.de, Post-Shop, eBay)",
+                     "DHL domestic/international (dhl.de, Post shop, eBay)", "dhl", (210, 297), "62"),
+    "dhl-privat-3": ("DHL Privat", "3 DHL Warenpost national - a4 hoch.pdf", "DHL Warenpost national",
+                     "DHL Warenpost domestic", "dhl", (210, 297), "62"),
+    "dhl-privat-4": ("DHL Privat", "4 DHL Warenpost international ohne Zoll - a4 hoch.pdf",
+                     "DHL Warenpost international ohne Zoll", "DHL Warenpost international without customs",
+                     "dhl", (210, 297), "62"),
+    "dhl-privat-4a": ("DHL Privat", "4a DHL Warenpost international mit Zoll - a4 hoch.pdf",
+                      "DHL Warenpost international mit Zoll", "DHL Warenpost international with customs",
+                      "dhl", (210, 297), "62"),
+    "dhl-privat-4b": ("DHL Privat", "4b DHL Warenpost international mit Zoll NEU - a4 hoch.pdf",
+                      "DHL Warenpost international mit Zoll (neu)", "DHL Warenpost international with customs (new)",
+                      "dhl", (210, 297), "62"),
+    "dhl-business-1": ("DHL Business", "1 DHL A5 national Geschäftskunden [Business Portal] - A5 hoch.pdf",
+                       "DHL Geschäftskunden A5 national", "DHL business customers A5 domestic", "dhl",
+                       (148, 210), "62"),
+    "dhl-business-2": ("DHL Business", "2 DHL 105 x 203 mm national Geschäftskunden [Business Portal] - A5 hoch.pdf",
+                       "DHL Geschäftskunden 105 × 203 mm national", "DHL business customers 105 × 203 mm domestic",
+                       "dhl", (105, 203), "62"),
+    "dhl-business-3": ("DHL Business", "3 DHL 99 x 200 mm national Geschäftskunden [Shopify Business Portal] - A5 hoch.pdf",
+                       "DHL Geschäftskunden 99 × 200 mm national (Shopify)",
+                       "DHL business customers 99 × 200 mm domestic (Shopify)", "dhl", (99, 200), "62"),
+    "dhl-business-4": ("DHL Business", "4 DHL A5 international Geschäftskunden [Business Portal] - A5 hoch.pdf",
+                       "DHL Geschäftskunden A5 international", "DHL business customers A5 international", "dhl",
+                       (148, 210), "62"),
+    "dhl-business-5": ("DHL Business", "5 DHL A6 international Geschäftskunden [Business Portal] - A5 hoch.pdf",
+                       "DHL Geschäftskunden A6 international", "DHL business customers A6 international", "dhl",
+                       (105, 148), "62"),
+    "dhl-retour-1": ("DHL Retour", "1 DHL Retour [Retourenportal] - A4 hoch.pdf", "DHL Retoure (Retourenportal)",
+                     "DHL return (returns portal)", "dhl", (210, 297), "62"),
+    "dhl-retour-2": ("DHL Retour", "2 DHL Retour [neues Retourenportal] - A4 hoch.pdf",
+                     "DHL Retoure (neues Retourenportal)", "DHL return (new returns portal)", "dhl", (210, 297), "62"),
+    "dhl-retour-3": ("DHL Retour", "3 DHL Retour [Amazon gif] - A4 hoch.pdf", "DHL Retoure Amazon (GIF)",
+                     "DHL return Amazon (GIF)", "dhl", (210, 297), "62"),
+    "dhl-retour-4": ("DHL Retour", "4 DHL Retour [Amazon pdf] - A4 hoch.pdf", "DHL Retoure Amazon (PDF)",
+                     "DHL return Amazon (PDF)", "dhl", (210, 297), "62"),
+    "hermes-1": ("Hermes", "1 Hermes Retour [Amazon] - A4 hoch.pdf", "Hermes Retoure Amazon",
+                 "Hermes return Amazon", "hermes", (210, 297), "62"),
+    "hermes-2": ("Hermes", "2 Hermes V4.2.000 - A4 hoch.pdf", "Hermes Paketschein (V4.2)",
+                 "Hermes parcel label (V4.2)", "hermes", (210, 297), "62"),
+    "hermes-3": ("Hermes", "3 Hermes V1.0.2 - A4 hoch.pdf", "Hermes Paketschein (V1.0)",
+                 "Hermes parcel label (V1.0)", "hermes", (210, 297), "62"),
+}
+# Echte Marken (nur lokal, nie ins Repo): Original/originale.json im Datenordner, z. B.
+# {"source": "marke.pdf", "results": {"dhl-privat-1": "marke-umgewandelt-1.pdf"}}
+_originals = D / "Original" / "originale.json"
+_orig = json.loads(_originals.read_text()) if _originals.exists() else {"source": "", "results": {}}
+ORIGINAL = _orig["results"]
+ORIGINAL_SRC = _orig["source"]
+
+
+# --- Bilder ---------------------------------------------------------------------------
+def target_ink(img):
+    """Tinte im Ergebnis in Polarität der Quelle (paketikett kehrt die Testblätter um)."""
+    a = np.asarray(img, float)
+    nonwhite = (a < 235).sum()
+    if (a < 60).mean() > 0.4 or nonwhite and ((a >= 140) & (a < 220)).sum() / nonwhite > 0.2:   # umgekehrt
+        t = np.where(a >= 235, 255.0, 255 - np.minimum(255, a * 1.5))
+    else:
+        t = a
+    return t < 128
+
+
+def src_ink(img):
+    return np.asarray(img) < 128
+
+
+def rot_point(x, y, r, W0, H0):
+    """Pixel (x, y) nach Drehung des Bildes um r° im Uhrzeigersinn (expand)."""
+    if r == 0:
+        return x, y
+    if r == 90:
+        return H0 - 1 - y, x
+    if r == 180:
+        return W0 - 1 - x, H0 - 1 - y
+    return y, W0 - 1 - x
+
+
+def rotate_cw(a, r):
+    return np.rot90(a, k=-(r // 90)) if r else a
+
+
+# --- Stücke ---------------------------------------------------------------------------
+class Piece:
+    def __init__(self, M, src_mm, codes):
+        self.M = np.asarray(M, float)        # mm (Quelle) → px (Ergebnis), 2×3
+        self.src = list(src_mm)              # [x0, y0, x1, y1] mm
+        self.codes = codes
+
+    def full(self):
+        return np.vstack([self.M, [0, 0, 1]])
+
+    def dst_box(self):
+        x0, y0, x1, y1 = self.src
+        pts = np.array([[x0, y0, 1], [x1, y0, 1], [x1, y1, 1], [x0, y1, 1]], float)
+        q = (self.full() @ pts.T).T
+        return (int(round(q[:, 0].min())), int(round(q[:, 1].min())),
+                int(round(q[:, 0].max())), int(round(q[:, 1].max())))
+
+    def rotation(self):
+        L = self.M[:, :2]
+        ang = (np.degrees(np.arctan2(L[1, 0], L[0, 0])) + 360) % 360
+        return int(round(ang / 90) % 4 * 90)
+
+    def scale(self):
+        L = self.M[:, :2] / PX
+        return float(np.linalg.norm(L[:, 0])), float(np.linalg.norm(L[:, 1]))
+
+
+def warp(src_img, piece, shape):
+    H, W = shape
+    inv = np.linalg.inv(piece.full() @ np.diag([1 / PX, 1 / PX, 1]))   # px out → px Quelle
+    w = src_img.transform((W, H), Image.AFFINE, tuple(inv[:2].ravel()), resample=Image.BILINEAR, fillcolor=255)
+    return np.asarray(w) < 128
+
+
+def initial_pieces(out_img, sparse=False):
+    items = []
+    for text, pts in A.decode(out_img):
+        try:
+            code, cx, cy = text.split()
+            c = (float(cx), float(cy))
+        except ValueError:
+            continue
+        M, err = A.fit(A.corners(*c), pts)
+        if err < 6:
+            items.append({"code": code, "c": c, "pts": pts, "M": M, "p": np.mean(pts, axis=0)})
+    groups = A.group(items)
+    code = items[0]["code"] if items else None
+    pieces = []
+    for g in groups:
+        pts = np.array([p for it in g["items"] for p in A.corners(*it["c"])])
+        s0, s1 = pts.min(axis=0), pts.max(axis=0)
+        pieces.append(Piece(g["M"], [s0[0] - 1.3, s0[1] - 1.3, s1[0] + 1.3, s1[1] + 1.3], len(g["items"])))
+    return code, pieces
+
+
+# --- Kosten ---------------------------------------------------------------------------
+class Scene:
+    def __init__(self, target, warped_list, pieces):
+        self.target = target
+        self.tdil = ndimage.binary_dilation(target, iterations=1)
+        self.warped = warped_list
+        self.pieces = pieces
+        self.active = [True] * len(pieces)
+        self.cdil = [ndimage.binary_dilation(w, iterations=1) for w in warped_list]
+
+    def compose(self):
+        H, W = self.target.shape
+        c = np.zeros((H, W), bool)
+        cd = np.zeros((H, W), bool)
+        for i, p in enumerate(self.pieces):
+            if not self.active[i]:
+                continue
+            x0, y0, x1, y1 = p.dst_box()
+            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
+            if x1 > x0 and y1 > y0:
+                c[y0:y1, x0:x1] = self.warped[i][y0:y1, x0:x1]
+                cd[y0:y1, x0:x1] = self.cdil[i][y0:y1, x0:x1]
+        return c, cd
+
+    def cost(self):
+        c, cd = self.compose()
+        return int((c & ~self.tdil).sum() + (self.target & ~cd).sum())
+
+    def optimize(self, step=0.25, rng=3.0, rounds=3, extra=None):
+        best = self.cost() + (extra() if extra else 0)
+        for _ in range(rounds):
+            improved = False
+            for i, p in enumerate(self.pieces):
+                if not self.active[i]:
+                    continue
+                for e in range(4):
+                    base = p.src[e]
+                    for d in np.arange(-rng, rng + step / 2, step):
+                        p.src[e] = base + d
+                        if p.src[0] >= p.src[2] - 1 or p.src[1] >= p.src[3] - 1:
+                            continue
+                        c = self.cost() + (extra() if extra else 0)
+                        if c < best:
+                            best, base, improved = c, p.src[e], True
+                    p.src[e] = base
+            margin = 0.003 * self.target.sum()        # schwache Stücke nur, wenn sie deutlich helfen
+            for i, p in enumerate(self.pieces):
+                if p.codes < 2:
+                    small = min(p.src[2] - p.src[0], p.src[3] - p.src[1]) < 4
+                    self.active[i] = not self.active[i]
+                    c = self.cost() + (extra() if extra else 0)
+                    if self.active[i] and not small and c < best - margin:
+                        best, improved = c, True
+                    elif not self.active[i] and (small or c <= best + margin):
+                        best, improved = c, True
+                    else:
+                        self.active[i] = not self.active[i]
+            if not improved:
+                break
+        return best
+
+
+# --- fehlende Stücke ----------------------------------------------------------------------
+def residual(target, pieces, active, min_mm2):
+    H, W = target.shape
+    covered = np.zeros((H, W), bool)
+    for i, p in enumerate(pieces):
+        if active[i]:
+            x0, y0, x1, y1 = p.dst_box()
+            covered[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
+    covered = ndimage.binary_dilation(covered, iterations=int(PX))
+    rest = target & ~covered
+    rest = ndimage.binary_closing(rest, np.ones((int(2 * PX), int(2 * PX))))
+    lab, n = ndimage.label(rest)
+    comps = []
+    for k in range(1, n + 1):
+        ys, xs = np.nonzero(lab == k)
+        if len(ys) / PX ** 2 >= min_mm2:
+            comps.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1, len(ys)))
+    return comps
+
+
+def search(patch, sink, scales):
+    """Beste Abbildung (Dice der Tinte) für ein Stück Ergebnis: Drehung, Maßstab, Lage."""
+    Pi = patch.astype(float)
+    best = None
+    for r in (0, 90, 180, 270):
+        R = rotate_cw(sink, r)
+        img = Image.fromarray((~R).astype(np.uint8) * 255)
+        for s in scales:
+            S = np.asarray(img.resize((max(1, int(R.shape[1] * s)), max(1, int(R.shape[0] * s))),
+                                      Image.BILINEAR)) < 128
+            if S.shape[0] < Pi.shape[0] or S.shape[1] < Pi.shape[1]:
+                continue
+            Sf = S.astype(float)
+            ov = signal.fftconvolve(Sf, Pi[::-1, ::-1], mode="valid")
+            win = signal.fftconvolve(Sf, np.ones_like(Pi), mode="valid")
+            c = 2 * ov / (Pi.sum() + win + 1e-9)
+            idx = np.unravel_index(np.argmax(c), c.shape)
+            if best is None or c[idx] > best[0]:
+                best = (float(c[idx]), r, s, idx)
+    return best
+
+
+def piece_from(r, s, oy, ox, bx0, by0, shape):
+    H0, W0 = shape
+    srcpts, dstpts = [], []
+    for x, y in ((0, 0), (W0 - 1, 0), (0, H0 - 1), (W0 - 1, H0 - 1)):
+        rx, ry = rot_point(x, y, r, W0, H0)
+        srcpts.append((x / PX, y / PX))
+        dstpts.append((rx * s - ox + bx0, ry * s - oy + by0))
+    M, __ = A.fit(srcpts, dstpts)
+    return M
+
+
+def find_missing(scene, src_img, scales, min_mm2=25, rounds=4):
+    """Tinte, die kein Stück erklärt → Abbildung per Kreuzkorrelation (Dice) suchen; Ausdehnung des
+    neuen Stücks = Blöcke (1 mm), in denen die Abbildung die Tinte erklärt. Mehrere Runden: ein
+    Rest aus zwei Stücken wird so nacheinander zerlegt."""
+    target = scene.target
+    H, W = target.shape
+    sink = src_ink(src_img)
+    pieces = list(scene.pieces)
+    active = list(scene.active)
+    found = []
+    tried = set()
+    for _ in range(rounds):
+        comps = [c for c in residual(target, pieces, active, min_mm2) if c[:4] not in tried]
+        if not comps:
+            break
+        new = False
+        for bx0, by0, bx1, by1, area in comps:
+            tried.add((bx0, by0, bx1, by1))
+            patch = target[by0:by1, bx0:bx1]
+            if patch.mean() < 0.02 or min(patch.shape) < 2 * PX:
+                continue
+            best = search(patch, sink, scales)
+            if best is None or best[0] < 0.5:
+                print(f"  Rest {bx0 / PX:.0f},{by0 / PX:.0f} mm ({area / PX ** 2:.0f} mm²): keine Abbildung"
+                      f" ({best[0] if best else None:.2f})")
+                continue
+            score, r, s, (oy, ox) = best
+            M = piece_from(r, s, oy, ox, bx0, by0, sink.shape)
+            p = Piece(M, [0, 0, 1, 1], 2)
+            w = warp(src_img, p, target.shape)
+            # Ausdehnung: größte zusammenhängende Fläche von Blöcken (1 mm) mit Übereinstimmung
+            B = int(PX)
+            gh, gw = (by1 - by0 + B - 1) // B, (bx1 - bx0 + B - 1) // B
+            grid = np.zeros((gh, gw), bool)
+            for j in range(gh):
+                for i in range(gw):
+                    y, x = by0 + j * B, bx0 + i * B
+                    tw = w[y:y + B, x:x + B]; tt = target[y:y + B, x:x + B]
+                    n = tw.sum() + tt.sum()
+                    grid[j, i] = n >= 4 and 2 * (tw & tt).sum() / n > 0.75
+            grid = ndimage.binary_closing(grid, np.ones((3, 3))) & ndimage.binary_dilation(grid)
+            lab, n = ndimage.label(grid)
+            if not n:
+                continue
+            sizes = ndimage.sum(grid, lab, range(1, n + 1))
+            jj, ii = np.nonzero(lab == 1 + int(np.argmax(sizes)))
+            d0 = (bx0 + ii.min() * B, by0 + jj.min() * B)
+            d1 = (bx0 + (ii.max() + 1) * B, by0 + (jj.max() + 1) * B)
+            inv = np.linalg.inv(np.vstack([M, [0, 0, 1]]))
+            cs = A.apply(inv[:2], [d0, (d1[0], d0[1]), d1, (d0[0], d1[1])])
+            s0, s1 = cs.min(axis=0), cs.max(axis=0)
+            p.src = [s0[0], s0[1], s1[0], s1[1]]
+            print(f"  Rest {bx0 / PX:.0f},{by0 / PX:.0f} mm: Drehung {r}°, Maßstab {s:.3f}, Dice {score:.2f}"
+                  f" → Quelle {s0[0]:.1f},{s0[1]:.1f}–{s1[0]:.1f},{s1[1]:.1f}")
+            found.append(p)
+            pieces.append(p)
+            active.append(True)
+            new = True
+        if not new:
+            break
+    return found
+
+
+def same_transform(a, b, tol_px=4):
+    """Gleiche Abbildung: lineare Teile ≈ gleich, Lage eines gemeinsamen Punktes ≈ gleich."""
+    La, Lb = a.M[:, :2], b.M[:, :2]
+    if np.linalg.norm(La - Lb) / np.linalg.norm(La) > 0.015:
+        return False
+    c = np.array([(a.src[0] + a.src[2]) / 2, (a.src[1] + a.src[3]) / 2])
+    return np.linalg.norm(A.apply(a.M, [c])[0] - A.apply(b.M, [c])[0]) < tol_px
+
+
+def merge(pieces):
+    """Stücke mit gleicher Abbildung zu einem (umschließendes Rechteck in der Quelle)."""
+    out = []
+    for p in pieces:
+        for q in out:
+            if same_transform(q, p):
+                q.src = [min(q.src[0], p.src[0]), min(q.src[1], p.src[1]),
+                         max(q.src[2], p.src[2]), max(q.src[3], p.src[3])]
+                q.codes = max(q.codes, p.codes)
+                break
+        else:
+            out.append(p)
+    return out
+
+
+def refine_translation(piece, src_img, target, rng=3):
+    """Lage eines Stücks pixelgenau nachstellen (±rng px)."""
+    H, W = target.shape
+    x0, y0, x1, y1 = piece.dst_box()
+    x0, y0, x1, y1 = max(0, x0 + 10), max(0, y0 + 10), min(W, x1 - 10), min(H, y1 - 10)
+    if x1 - x0 < 20 or y1 - y0 < 20:
+        return
+    w = warp(src_img, piece, target.shape)
+    best = None
+    for dy in range(-rng, rng + 1):
+        for dx in range(-rng, rng + 1):
+            t = target[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
+            if t.shape != (y1 - y0, x1 - x0):
+                continue
+            c = int((t ^ w[y0:y1, x0:x1]).sum())
+            if best is None or c < best[0]:
+                best = (c, dx, dy)
+    if best and (best[1] or best[2]):
+        piece.M[:, 2] += [best[1], best[2]]
+
+
+# --- Ablauf ---------------------------------------------------------------------------
+def process(tid):
+    folder, fname, de, en, carrier, source, fmt = TYPES[tid]
+    out_path = D / folder / fname
+    pages_out = list(A.page_images(out_path))
+    result = {"id": tid, "names": {"de": de, "en": en}, "country": "DE", "carrier": carrier,
+              "source": {"size_mm": list(source)}, "verified": tid in ORIGINAL, "layouts": {fmt: []},
+              "check": []}
+    for pno, out_img, size in pages_out:
+        code, pieces = initial_pieces(out_img)
+        sheet_file, sheet_size = SHEET[code]
+        src_img = next(A.page_images(D / sheet_file))[1]
+        target = target_ink(out_img)
+        for p in pieces:
+            refine_translation(p, src_img, target)
+        scene = Scene(target, [warp(src_img, p, target.shape) for p in pieces], pieces)
+        scene.optimize(rounds=1)
+        scales = sorted({round(np.mean(p.scale()), 2) for p in pieces} |
+                        {round(v, 3) for v in np.arange(0.45, 1.151, 0.025)})
+        extra = find_missing(scene, src_img, scales)
+        for p in extra:
+            refine_translation(p, src_img, target)
+        if extra:
+            keep = [p for i, p in enumerate(pieces) if scene.active[i]]
+            pieces = merge(keep + merge(extra))
+            scene = Scene(target, [warp(src_img, p, target.shape) for p in pieces], pieces)
+        cost = scene.optimize()
+        ink = int(target.sum())
+        check = {"page": pno + 1, "mismatch_pct": round(100 * cost / max(1, ink), 1)}
+        # Gegenprobe/Schärfen am echten Original (gemeinsame Kosten)
+        if tid in ORIGINAL:
+            o_out = list(A.page_images(D / "Original" / ORIGINAL[tid]))[pno][1]
+            o_src = next(A.page_images(D / "Original" / ORIGINAL_SRC))[1]
+            o_target = target_ink(o_out)
+            o_scene = Scene(o_target, [warp(o_src, p, o_target.shape) for p in pieces], pieces)
+            o_scene.active = scene.active
+            before = o_scene.cost()
+            o_ink = int(o_target.sum())
+            # Original zählt gleich viel wie das Testblatt (normiert)
+            w = ink / max(1, o_ink)
+            scene.optimize(extra=lambda: int(w * o_scene.cost()), step=0.25, rng=2.0, rounds=2)
+            after = o_scene.cost()
+            check["original_mismatch_pct"] = [round(100 * before / max(1, o_ink), 1),
+                                              round(100 * after / max(1, o_ink), 1)]
+            check["mismatch_pct"] = round(100 * scene.cost() / max(1, ink), 1)
+            save_check(o_scene, HERE / "check" / f"{tid}-{pno + 1}-original.png")
+        save_check(scene, HERE / "check" / f"{tid}-{pno + 1}.png")
+        label = {"size_mm": [round(size[0], 1), round(size[1], 1)], "pieces": []}
+        for i, p in enumerate(pieces):
+            if not scene.active[i]:
+                continue
+            x0, y0, x1, y1 = p.dst_box()
+            sx, sy = p.scale()
+            label["pieces"].append({
+                "page": 1, "src": [round(v * 4) / 4 for v in p.src], "rotation": p.rotation(),
+                "dst": [round(x0 / PX * 4) / 4, round(y0 / PX * 4) / 4], "scale": round((sx + sy) / 2, 3),
+                "scale_xy": [round(sx, 3), round(sy, 3)],
+                "kind": "barcode" if abs((sx + sy) / 2 - 1) < 0.03 else "text",
+                "M": p.M.round(4).tolist()})
+        # Reihenfolge = Malreihenfolge (spätere Stücke liegen oben)
+        result["layouts"][fmt].append(label)
+        result["check"].append(check)
+        print(f"{tid} Seite {pno + 1}: {len(label['pieces'])} Stücke, Abweichung {check}")
+    (HERE / "result").mkdir(exist_ok=True)
+    (HERE / "result" / f"{tid}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
+    return result
+
+
+def save_check(scene, path):
+    c, __ = scene.compose()
+    t = scene.target
+    rgb = np.stack([np.where(c, 0, 255), np.where(t, 0, 255), np.where(t, 0, 255)], -1).astype(np.uint8)
+    img = Image.fromarray(rgb)
+    from PIL import ImageDraw
+    d = ImageDraw.Draw(img)
+    for i, p in enumerate(scene.pieces):
+        if scene.active[i]:
+            d.rectangle(p.dst_box(), outline=(0, 160, 0), width=2)
+    path.parent.mkdir(exist_ok=True)
+    img.save(path)
+
+
+if __name__ == "__main__":
+    for tid in (sys.argv[1:] or TYPES):
+        process(tid)
diff --git a/tools/parcel/make_sheets.py b/tools/parcel/make_sheets.py
new file mode 100644
index 0000000..cdb9bb9
--- /dev/null
+++ b/tools/parcel/make_sheets.py
@@ -0,0 +1,75 @@
+"""Testblätter für einen Umwandlungsdienst (z. B. paketikett.de): Vektor-PDF mit echtem Text, Raster alle
+10 mm, in jedem Feld ein QR-Code „KÜRZEL x y“ (Mitte der Zelle in mm). Aus dem umgewandelten Ergebnis
+liest ``analyze.py`` ab, welcher Bereich wohin kam (Drehung, Maßstab). Keine echten Daten.
+
+Aufruf: QT_QPA_PLATFORM=offscreen python make_sheets.py ARBEITSORDNER (bzw. $LABELWERK_PARCEL_DIR)
+"""
+import os
+import sys
+
+import segno
+from workdir import workdir
+from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
+from PySide6.QtGui import QColor, QFont, QGuiApplication, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
+
+SHEETS = {  # Name: (Kürzel im QR, Breite, Höhe in mm)
+    "A4-hoch": ("A4H", 210, 297), "A4-quer": ("A4Q", 297, 210), "A5-hoch": ("A5H", 148, 210),
+    "A5-quer": ("A5Q", 210, 148), "100x150": ("L100", 100, 150), "105x203": ("L105", 105, 203),
+    "103x199": ("L103", 103, 199),
+}
+
+
+def sheet(out, name, code, w, h, sparse=False):
+    path = os.path.join(out, f"testblatt-{name}{'-wenig' if sparse else ''}.pdf")
+    pdf = QPdfWriter(path)
+    pdf.setPageSize(QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter, name))
+    pdf.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
+    pdf.setResolution(1200)
+    pdf.setTitle(f"labelwerk Testblatt {name}")
+    p = QPainter(pdf)
+    mm = pdf.resolution() / 25.4
+    p.scale(mm, mm)                                  # ab hier in mm
+    thin, thick = QPen(QColor(150, 150, 150), 0.1), QPen(Qt.GlobalColor.black, 0.35)
+    if not sparse:
+        for x in range(0, w + 1, 10):
+            p.setPen(thick if x % 50 == 0 else thin)
+            p.drawLine(QPointF(x, 0), QPointF(x, h))
+        for y in range(0, h + 1, 10):
+            p.setPen(thick if y % 50 == 0 else thin)
+            p.drawLine(QPointF(0, y), QPointF(w, y))
+    step = 30 if sparse else 10
+    for x in range(0, w - 9, step):
+        for y in range(0, h - 9, step):
+            cx, cy = x + 5, y + 5
+            qr = segno.make(f"{code} {cx} {cy}", error="l", micro=False)   # Version 1: 21 Module
+            n = qr.symbol_size(border=0)[0]
+            size = 7.4                                # 0,35 mm je Modul, 1,3 mm Ruhezone zur Linie
+            cell = size / n
+            ox, oy = x + (10 - size) / 2, y + (10 - size) / 2
+            for r, row in enumerate(qr.matrix):
+                for c, v in enumerate(row):
+                    if v:
+                        p.fillRect(QRectF(ox + c * cell, oy + r * cell, cell, cell), Qt.GlobalColor.black)
+    # Ecken und Richtung: asymmetrisch, damit Drehung/Spiegelung eindeutig ist
+    big = QFont("DejaVu Sans")
+    big.setPixelSize(4)
+    big.setBold(True)
+    p.setFont(big)
+    for text, rect in (("OL", QRectF(1, 1, 12, 5)), ("OR", QRectF(w - 13, 1, 12, 5)),
+                       ("UL", QRectF(1, h - 6, 12, 5)), ("UR", QRectF(w - 13, h - 6, 12, 5))):
+        p.fillRect(rect, QColor(255, 255, 255))
+        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
+    p.drawText(QRectF(0, h / 2 - 3, w, 6), Qt.AlignmentFlag.AlignCenter, f"labelwerk Testblatt {name} ↑ OBEN")
+    p.end()
+
+
+def main(out):
+    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])   # noqa: F841 (Schriften)
+    for name, (code, w, h) in SHEETS.items():
+        sheet(out, name, code, w, h)
+        if name.startswith("A4"):
+            sheet(out, name, code, w, h, sparse=True)
+
+
+if __name__ == "__main__":
+    main(str(workdir(sys.argv[1] if len(sys.argv) > 1 else None)))
diff --git a/tools/parcel/workdir.py b/tools/parcel/workdir.py
new file mode 100644
index 0000000..20032e2
--- /dev/null
+++ b/tools/parcel/workdir.py
@@ -0,0 +1,20 @@
+"""Arbeitsordner der Pflege-Werkzeuge: Testblätter, umgewandelte Ergebnisse und alle Ausgaben liegen
+dort – nie im Repository (echte Marken enthalten Namen und Adressen)."""
+import os
+import sys
+from pathlib import Path
+
+REPO = Path(__file__).resolve().parents[2]
+
+
+def workdir(argument: str | None = None) -> Path:
+    """Ordner aus ``argument`` bzw. ``$LABELWERK_PARCEL_DIR``; fehlt er oder liegt er im Repository,
+    bricht das Werkzeug mit einer Meldung ab."""
+    value = argument or os.environ.get("LABELWERK_PARCEL_DIR")
+    if not value:
+        sys.exit("Arbeitsordner fehlt: LABELWERK_PARCEL_DIR=ordner setzen (außerhalb des Repositorys).")
+    path = Path(value).expanduser().resolve()
+    if path == REPO or REPO in path.parents:
+        sys.exit(f"{path} liegt im Repository – Ausgaben und Marken gehören nicht hinein.")
+    path.mkdir(parents=True, exist_ok=True)
+    return path
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2891 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add .gitignore CLAUDE.md README.md docs/superpowers/specs/2026-10-19-paketmarken-design.md src/labelwerk/cli.py src/labelwerk/files.py src/labelwerk/gui/file_dialog.py src/labelwerk/parcel.py src/labelwerk/parcel_data/README.md src/labelwerk/parcel_data/catalog.json src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot tests/parcelmark.py tests/test_cli_parcel.py tests/test_parcel.py tools/parcel/README.md tools/parcel/analyze.py tools/parcel/assemble.py tools/parcel/catalog.py tools/parcel/extract.py tools/parcel/make_sheets.py tools/parcel/workdir.py
git commit -m "Paketmarken – Kern: Katalog DE (DHL, Hermes; 20 Typen nach dem Testblatt-Verfahren gemessen), parcel.py (laden, erkennen, umwandeln, eigene Typen, anordnen), CLI labelwerk parcel, tools/parcel, PDFium-Sperre

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Paketmarken – Reiter PAKET und eigene Typen

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-19-paketmarken-design.md`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/file_session.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Create: `src/labelwerk/gui/panels/parcel.py`
- Create: `src/labelwerk/gui/parcel_editor.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/gui/tools.py`
- Modify: `src/labelwerk/parcel.py`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/gui/test_gui_hidden_tools.py`
- Modify: `tests/gui/test_gui_image.py`
- Create: `tests/gui/test_gui_parcel.py`
- Modify: `tests/gui/test_gui_series.py`
- Modify: `tests/gui/test_gui_settings.py`
- Modify: `tests/test_parcel.py`

**Interfaces / Produces:** Werkzeug `parcel` (gui/tools.py, START_TOOLS/HIDEABLE_TOOLS), `gui/panels/parcel.py`, `gui/parcel_editor.py`, `Canvas.read_only`, MainWindow: Umwandlung als Nur-Ansicht, `print_documents`, IM EDITOR ÖFFNEN (`FileSession.open_document`), Aktionsleiste `app_bar`, `fit_toolbars`; `parcel.default_country`, `own_id`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_hidden_tools.py b/tests/gui/test_gui_hidden_tools.py
index 629e2f4..b147221 100644
--- a/tests/gui/test_gui_hidden_tools.py
+++ b/tests/gui/test_gui_hidden_tools.py
@@ -34,7 +34,7 @@ def test_hidden_tools_have_no_button(qtbot):
     win = _window(qtbot, hidden_tools=["barcode", "series"])
     visible = {key: action.isVisible() for key, action in win.tool_actions.items()}
     assert visible == {"file": True, "paper": True, "text": True, "image": True,
-                       "barcode": False, "layout": True, "series": False}
+                       "barcode": False, "layout": True, "series": False, "parcel": True}
 
 
 def test_selecting_an_object_of_a_hidden_tool_shows_its_panel(qtbot):
diff --git a/tests/gui/test_gui_image.py b/tests/gui/test_gui_image.py
index 6c97001..de2da03 100644
--- a/tests/gui/test_gui_image.py
+++ b/tests/gui/test_gui_image.py
@@ -133,7 +133,7 @@ def _status(win):
 # --- Werkzeug und Panel -------------------------------------------------------------
 def test_image_tool_comes_after_text(window):
     assert [tool.key for tool in TOOLS] == ["file", "paper", "text", "image", "barcode", "layout",
-                                           "series"]
+                                           "series", "parcel"]
     window.tool_actions["image"].trigger()
     assert window.panels.currentWidget() is window.panel("image")
     assert window.canvas.tool() == "select"
diff --git a/tests/gui/test_gui_parcel.py b/tests/gui/test_gui_parcel.py
new file mode 100644
index 0000000..5aa372b
--- /dev/null
+++ b/tests/gui/test_gui_parcel.py
@@ -0,0 +1,571 @@
+"""Reiter PAKET (Panel „Paketmarke“): Marke öffnen, Typ erkennen, Umwandlung ansehen (nur Ansicht), drucken, im
+Editor öffnen, eigene Typen anlegen/umbenennen/löschen. Nur erzeugte Testmarken (parcelmark)."""
+import pytest
+from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
+from PySide6.QtGui import QDropEvent
+from PySide6.QtWidgets import QApplication
+
+from labelwerk import parcel
+from labelwerk.document import Document, ImageObject, TextObject
+from labelwerk.gui import main_window
+from labelwerk.gui.parcel_editor import ParcelTypeEditor
+from labelwerk.gui.panels.parcel import OWN, TYPE_ROLE
+from labelwerk.settings import Settings
+from parcelmark import make_pdf
+
+from test_gui_printers import workers  # noqa: F401  (Fixture: Druck ersetzt)
+
+
+@pytest.fixture(autouse=True)
+def own_folder(tmp_path, monkeypatch):
+    """Eigene Typen in einem leeren Ordner (nie die echten Daten)."""
+    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
+
+
+def _window(qtbot, doc=None, **settings):
+    win = main_window.MainWindow(doc=doc or Document("62", objects=[TextObject("A")]),
+                                 settings=Settings(check_media_on_start=False, **settings))
+    qtbot.addWidget(win)
+    win.show()
+    win.render_now()
+    return win
+
+
+def _dhl(tmp_path, name="dhl.pdf"):
+    return make_pdf(tmp_path / name, texts=[(20, 20, "DHL Online Frankierung"),
+                                            (20, 40, "Sendungsnummer")],
+                    rects=[(15, 30, 120, 34), (140, 40, 190, 100)])
+
+
+def _amazon(tmp_path):
+    return make_pdf(tmp_path / "amazon.pdf", texts=[(20, 20, "Amazon Rücksendung DHL Retoure")],
+                    rects=[(40, 120, 150, 160), (60, 240, 150, 270)])
+
+
+def _open(win, path):
+    win.ask_parcel_file = lambda: str(path)
+    win._tool_triggered("parcel")
+    win.tool_actions["parcel"].setChecked(True)
+    win.panel("parcel").open_button.click()
+    win.render_now()
+    return win.panel("parcel")
+
+
+def _type_ids(panel) -> list[str]:
+    return [panel.types.item(i).data(TYPE_ROLE) for i in range(panel.types.count())
+            if panel.types.item(i).data(TYPE_ROLE)]
+
+
+def test_parcel_tool_is_in_the_toolbar(qtbot):
+    win = _window(qtbot)
+    assert "parcel" in win.tool_actions
+    assert win.tool_actions["parcel"].text() == "PAKET"
+    assert win.tool_actions["parcel"].toolTip() == ("Paketmarke (DHL, Hermes …) für den "
+                                                    "Etikettendrucker umwandeln")
+    panel = win.panel("parcel")
+    assert panel.country.currentData() == "DE"
+    assert {"dhl-privat-1", "hermes-2"} <= set(_type_ids(panel))
+    assert not panel.print_button.isEnabled() and not panel.editor_button.isEnabled()
+    assert not panel.own_button.isEnabled()                     # erst mit geöffneter Marke
+
+
+def test_open_detects_the_type_and_shows_the_conversion(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    assert panel.chosen_type().id == "dhl-privat-1"             # 62 mm: Layout „62“ gewinnt
+    assert panel.types.currentItem().text().startswith("✓ ")
+    assert panel.file_label.text() == "dhl.pdf"
+    docs = panel.documents()
+    assert len(docs) == 1 and docs[0].label_id == "62"
+    assert win.canvas.read_only and len(win.canvas.objects) == len(docs[0].objects) == 7
+    assert win.canvas.handle is None or not win.canvas.handle.isVisible()
+    assert panel.print_button.isEnabled() and panel.editor_button.isEnabled()
+    assert win.doc.objects == [TextObject("A")]                 # Dokument unangetastet
+
+
+def test_other_tab_shows_the_document_again(qtbot, tmp_path):
+    win = _window(qtbot)
+    _open(win, _dhl(tmp_path))
+    win._tool_triggered("paper")
+    assert not win.canvas.read_only and len(win.canvas.objects) == 1
+    win._tool_triggered("parcel")
+    assert win.canvas.read_only and len(win.canvas.objects) == 7
+
+
+def test_canvas_ignores_clicks_on_the_conversion(qtbot, tmp_path):
+    win = _window(qtbot)
+    _open(win, _dhl(tmp_path))
+    center = win.canvas.mapFromScene(win.canvas.objects[0].sceneBoundingRect().center())
+    qtbot.mouseClick(win.canvas.viewport(), Qt.MouseButton.LeftButton, pos=center)
+    qtbot.mouseDClick(win.canvas.viewport(), Qt.MouseButton.LeftButton, pos=center)
+    assert win.canvas.selection() == [] and win.edit_session.active is False
+    win.shortcut_actions["edit.select_all"].trigger()          # nichts wählbar: Entf löscht nichts
+    win.shortcut_actions["edit.delete"].trigger()
+    assert win.canvas.selection() == [] and win.doc.objects == [TextObject("A")]
+
+
+def test_choosing_another_type_converts_again(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-2")
+    panel.types.setCurrentItem(item)
+    assert panel.chosen_type().id == "dhl-privat-2"
+    assert len(win.canvas.objects) == len(panel.documents()[0].objects)
+    assert "ungeprüft" in item.text()
+
+
+def test_unrecognised_mark_asks_for_the_type(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, make_pdf(tmp_path / "x.pdf", size_mm=(50, 50), texts=[(5, 5, "Hallo")]))
+    assert panel.chosen_type() is None and panel.documents() == []
+    assert panel.notes.isVisibleTo(panel) and "nicht erkannt" in panel.notes.text()
+    assert win.canvas.read_only and win.canvas.objects == []    # leer, nur Ansicht
+
+
+def test_unreadable_file_is_a_notice(qtbot, tmp_path):
+    win = _window(qtbot)
+    bad = tmp_path / "kaputt.pdf"
+    bad.write_bytes(b"kein PDF")
+    panel = _open(win, bad)
+    assert panel.source is None and panel.notes.isVisibleTo(panel) and panel.notes.text()
+
+
+def test_print_sends_every_label_in_one_job(qtbot, tmp_path, workers):  # noqa: F811
+    win = _window(qtbot)
+    panel = _open(win, _amazon(tmp_path))
+    assert len(panel.documents()) == 2 and panel.page_label.text() == "Etikett 1/2"
+    panel.print_button.click()
+    assert len(workers) == 1
+    job = workers[0]
+    assert isinstance(job.image, list) and len(job.image) == 2
+    assert job.label_id == "62" and job.cut_every == 1
+
+
+def test_toolbar_print_prints_the_conversion(qtbot, tmp_path, workers):  # noqa: F811
+    win = _window(qtbot)
+    _open(win, _dhl(tmp_path))
+    win.print_label()
+    assert len(workers) == 1 and not isinstance(workers[0].image, list)
+    assert workers[0].image.size[1] > 1000                     # Umwandlung, nicht das Etikett „A“
+
+
+def test_arrows_show_the_second_label(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _amazon(tmp_path))
+    first = len(win.canvas.objects)
+    panel.next_button.click()
+    assert panel.page_label.text() == "Etikett 2/2" and not panel.next_button.isEnabled()
+    assert len(win.canvas.objects) == len(panel.documents()[1].objects) != 0
+    panel.prev_button.click()
+    assert len(win.canvas.objects) == first
+
+
+def test_open_in_editor_replaces_the_document(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    panel.editor_button.click()
+    assert len(win.doc.objects) == 7 and all(isinstance(o, ImageObject) for o in win.doc.objects)
+    assert win.panels.currentWidget() is win.panel("paper") and not win.canvas.read_only
+    assert len(win.canvas.objects) == 7
+    assert win.files.origin == "parcel" and not win.files.may_follow_roll()
+    win.undo()                                                  # Verlauf neu: nichts zurück
+    assert len(win.doc.objects) == 7
+
+
+def test_open_in_editor_respects_the_save_question(qtbot, tmp_path, monkeypatch):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    monkeypatch.setattr(win.files, "maybe_save", lambda: False)   # „Abbrechen“
+    panel.editor_button.click()
+    assert win.doc.objects == [TextObject("A")] and win.panels.currentWidget() is panel
+
+
+def test_conversion_follows_the_label_of_the_document(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    win.doc.label_id = "62x100"                                 # gestanzt, zu kurz
+    win.render_now()
+    assert panel.documents()[0].label_id == "62x100"
+    assert panel.notes.isVisibleTo(panel) and "Barcodes" in panel.notes.text()
+
+
+def test_drop_on_the_canvas_loads_the_mark(qtbot, tmp_path):
+    win = _window(qtbot)
+    win._tool_triggered("parcel")
+    win._dropped([_dhl(tmp_path)], None, 10, 10)
+    assert win.panel("parcel").chosen_type().id == "dhl-privat-1"
+    assert win.doc.objects == [TextObject("A")]                 # kein Bild eingefügt
+
+
+def test_drop_on_the_panel_loads_the_mark(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = win.panel("parcel")
+    mime = QMimeData()
+    mime.setUrls([QUrl.fromLocalFile(str(_dhl(tmp_path)))])
+    event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.NoButton,
+                       Qt.KeyboardModifier.NoModifier)
+    panel.dropEvent(event)
+    assert panel.chosen_type().id == "dhl-privat-1"
+
+
+def test_country_own_only_lists_own_types(qtbot, tmp_path):
+    parcel.save_own(parcel.own_from_dict(_own_data()))
+    win = _window(qtbot)
+    panel = win.panel("parcel")
+    panel.country.setCurrentIndex(panel.country.findData(OWN))
+    assert _type_ids(panel) == ["eigen-lager"]
+    panel.country.setCurrentIndex(panel.country.findData("DE"))
+    assert _type_ids(panel)[-1] == "eigen-lager" and "dhl-privat-1" in _type_ids(panel)
+
+
+def _own_data(**changes):
+    data = {"id": "eigen-lager", "names": {"de": "Lager"}, "source": {"sizes_mm": [[210, 297]]},
+            "detect": {"all": ["Mein Lager"]},
+            "pieces": [{"page": 1, "src": [10, 10, 110, 60], "rotation": 90, "kind": "text"},
+                       {"page": 1, "src": [10, 100, 60, 130], "rotation": 0, "kind": "barcode"}]}
+    data.update(changes)
+    return data
+
+
+def test_new_own_type_is_saved_and_chosen(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, make_pdf(tmp_path / "lager.pdf", texts=[(20, 20, "Mein Lager GmbH")],
+                                rects=[(15, 15, 100, 50)]))
+    assert panel.chosen_type() is None
+    seen = []
+
+    def fill(editor):
+        seen.append(editor)
+        editor.add_area((10, 10, 110, 60), rotation=90)
+        editor.add_area((10, 100, 60, 130), barcode=True)
+        editor.name.setText("Mein Lager")
+        editor.words.setText("Mein Lager")
+        return True
+    win.exec_parcel_editor = fill
+    panel.own_button.click()
+    assert seen and parcel.own_types()[0].names == {"de": "Mein Lager"}
+    assert panel.chosen_type().id == "eigen-mein-lager"
+    assert panel.documents() and len(panel.documents()[0].objects) == 2
+    assert win.canvas.read_only and len(win.canvas.objects) == 2
+    assert "gespeichert" in win.result.text()
+
+
+def test_cancelled_editor_saves_nothing(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    win.exec_parcel_editor = lambda editor: False
+    panel.own_button.click()
+    assert parcel.own_types() == []
+
+
+def test_rename_and_remove_own_type(qtbot, tmp_path):
+    parcel.save_own(parcel.own_from_dict(_own_data()))
+    win = _window(qtbot)
+    win.ask_parcel_type_name = lambda current: "Lager Nord"
+    win.rename_own_parcel_type("eigen-lager")
+    assert parcel.find("eigen-lager").name == "Lager Nord"
+    assert any("Lager Nord" in win.panel("parcel").types.item(i).text()
+               for i in range(win.panel("parcel").types.count()))
+    win.ask_remove_parcel_type = lambda name: False
+    win.remove_own_parcel_type("eigen-lager")
+    assert parcel.own_types()
+    win.ask_remove_parcel_type = lambda name: True
+    win.remove_own_parcel_type("eigen-lager")
+    assert parcel.own_types() == [] and "eigen-lager" not in _type_ids(win.panel("parcel"))
+
+
+# --- Fenster „Eigener Markentyp“ ----------------------------------------------------------
+def _editor(qtbot, tmp_path):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Firma")],
+                                  rects=[(15, 15, 100, 50)]))
+    editor = ParcelTypeEditor(None, source, "62", "QL-600", {"eigen-test"})
+    qtbot.addWidget(editor)
+    editor.show()
+    return editor
+
+
+def test_editor_builds_a_checked_type(qtbot, tmp_path):
+    editor = _editor(qtbot, tmp_path)
+    save = editor.buttons.button(editor.buttons.StandardButton.Save)
+    assert not save.isEnabled()
+    editor.add_area((10, 10, 110, 60))
+    editor.add_area((1, 1, 2, 2))                               # zu klein: zählt nicht
+    editor.list.setCurrentRow(0)
+    editor.rotation.setCurrentIndex(1)                          # 90°
+    editor.barcode.setChecked(True)
+    editor.name.setText("Test")
+    assert save.isEnabled()
+    ptype = editor.result_type()
+    assert ptype.id == "eigen-test-2" and ptype.own              # „eigen-test“ ist vergeben
+    assert ptype.pieces[0].rotation == 90 and ptype.pieces[0].kind == "barcode"
+    assert ptype.pieces[0].src == pytest.approx((10, 10, 110, 60), abs=0.3)
+    assert len(ptype.pieces) == 1 and ptype.source_sizes == ((210.0, 297.0),)
+    assert not editor.preview.pixmap().isNull()
+
+
+def test_editor_draws_and_removes_areas_with_the_mouse(qtbot, tmp_path):
+    editor = _editor(qtbot, tmp_path)
+    view = editor.view
+    start = view.mapFromScene(QPointF(50, 50))
+    end = view.mapFromScene(QPointF(300, 200))
+    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
+    qtbot.mouseMove(view.viewport(), end)
+    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
+    assert len(editor.pieces()) == 1 and editor.list.count() == 1
+    editor.list.setCurrentRow(0)
+    editor.view.setFocus()
+    qtbot.keyClick(editor, Qt.Key.Key_Delete)
+    assert editor.pieces() == [] and editor.list.count() == 0
+
+
+def test_editor_words_become_recognition(qtbot, tmp_path):
+    editor = _editor(qtbot, tmp_path)
+    editor.add_area((10, 10, 110, 60))
+    editor.name.setText("Firma")
+    editor.words.setText("Firma, Lager ")
+    assert editor.result_type().detect == {"all": ["Firma", "Lager"]}
+    QApplication.processEvents()
+
+
+# --- Gleichstand, nicht erkannt, neu angeordnet ------------------------------------------
+def test_tie_between_unverified_types_lets_the_user_choose(qtbot, tmp_path):
+    """Hermes 2 und 3 lassen sich am Text nicht unterscheiden: kein Typ vorgewählt, nichts
+    gedruckt, der Hinweis nennt beide; die Wahl entscheidet."""
+    win = _window(qtbot)
+    panel = _open(win, make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein")]))
+    assert panel.chosen_type() is None and panel.documents() == []
+    assert not panel.print_button.isEnabled()
+    text = panel.notes.text()
+    assert "gleich gut" in text
+    assert parcel.find("hermes-2").name in text and parcel.find("hermes-3").name in text
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "hermes-3")
+    panel.types.setCurrentItem(item)
+    assert panel.chosen_type().id == "hermes-3" and panel.documents()
+    assert "gleich gut" not in panel.notes.text()
+
+
+def test_image_of_unknown_shape_is_not_recognised(qtbot, tmp_path):
+    from PIL import Image
+    Image.new("RGB", (1000, 1000), "white").save(tmp_path / "q.png")
+    win = _window(qtbot)
+    panel = _open(win, tmp_path / "q.png")
+    assert panel.chosen_type() is None and panel.documents() == []
+    assert "nicht erkannt" in panel.notes.text()
+    assert len(_type_ids(panel)) >= 19                          # Liste bleibt wählbar
+
+
+def test_wrong_size_for_the_chosen_type_is_a_notice(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, make_pdf(tmp_path / "gross.pdf", size_mm=(400, 400)))
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-1")
+    panel.types.setCurrentItem(item)
+    assert panel.documents() == [] and "passt nicht" in panel.notes.text()
+
+
+def test_arranged_layout_says_so(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, make_pdf(tmp_path / "m.pdf", size_mm=(100, 150),
+                                texts=[(10, 10, "DHL Online Frankierung")]))
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-1a-100x150")
+    panel.types.setCurrentItem(item)
+    assert panel.conversion.layout == "arranged"
+    assert "neu angeordnet" in panel.notes.text()
+
+
+# --- Review 559ac76: nur Ansicht, Drucken ohne Umwandlung, ✓, Leiste, Editor ----------------
+VIEW_ONLY = "nur Ansicht"
+
+
+def _view_only(win):
+    return VIEW_ONLY in win.result.text()
+
+
+def test_edit_actions_are_disabled_while_the_parcel_view_is_shown(qtbot, tmp_path):
+    win = _window(qtbot)
+    win.insert_barcode()                                        # ein Schritt im Verlauf
+    _open(win, _dhl(tmp_path))
+    actions = win.shortcut_actions
+    for key in ("edit.paste", "edit.undo", "edit.redo", "edit.select_all", "tool.text",
+                "image.insert", "barcode.insert", "align.left"):
+        assert not actions[key].isEnabled(), key
+    win._tool_triggered("paper")
+    win.render_now()
+    assert actions["edit.undo"].isEnabled() and actions["edit.select_all"].isEnabled()
+
+
+def test_every_way_of_changing_the_document_is_refused_in_the_parcel_view(qtbot, tmp_path):
+    from PIL import Image
+    from labelwerk import clipart
+    win = _window(qtbot)
+    win.insert_barcode()
+    before = list(win.doc.objects)
+    _open(win, _dhl(tmp_path))
+    QApplication.clipboard().setText("Eingefügt")
+    picture = Image.new("RGB", (60, 40), "black")
+    png = tmp_path / "bild.png"
+    picture.save(png)
+    ways = [win.paste, win.undo, win.redo, win.insert_barcode,
+            lambda: win.insert_symbol(clipart.symbols("allgemein")[0]),
+            lambda: win.insert_image_files([png]),
+            lambda: win._insert_picture(picture, "Test"),
+            lambda: win._dropped([], picture, 10, 10),
+            lambda: win.create_text(5, 5)]
+    for way in ways:
+        win._set_result("", "")
+        way()
+        assert win.doc.objects == before, way
+        assert _view_only(win), way
+    win._dropped([_amazon(tmp_path)], None, 10, 10)              # Datei: lädt die Marke
+    assert win.panel("parcel").path.name == "amazon.pdf" and win.doc.objects == before
+
+
+def test_without_a_conversion_nothing_is_printed(qtbot, tmp_path, workers):  # noqa: F811
+    win = _window(qtbot)
+    panel = _open(win, make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein")]))
+    assert panel.documents() == [] and win.canvas.read_only and win.canvas.objects == []
+    win.print_label()
+    assert workers == [] and "Markentyp" in win.result.text()
+    win.shortcut_actions["file.print"].trigger()
+    assert workers == []
+
+
+def test_wrong_size_error_is_shown_when_printing(qtbot, tmp_path, workers):  # noqa: F811
+    win = _window(qtbot)
+    panel = _open(win, make_pdf(tmp_path / "gross.pdf", size_mm=(400, 400)))
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-1")
+    panel.types.setCurrentItem(item)
+    win.print_label()
+    assert workers == [] and "passt nicht" in win.result.text()
+
+
+def test_check_mark_only_at_the_best_types_and_tie_hint(qtbot, tmp_path, monkeypatch):
+    first, second, third = (parcel.find(i) for i in ("dhl-privat-1", "dhl-privat-2", "hermes-2"))
+    monkeypatch.setattr(parcel, "detect", lambda *a, **k: [(first, 5.0), (second, 5.0),
+                                                          (third, 1.0)])
+    monkeypatch.setattr(parcel, "ambiguous", lambda found: [])      # geprüfter Sieger
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    marked = {panel.types.item(i).data(TYPE_ROLE) for i in range(panel.types.count())
+              if panel.types.item(i).text().startswith("✓ ")}
+    assert marked == {"dhl-privat-1", "dhl-privat-2"}
+    assert panel.chosen_type().id == "dhl-privat-1"
+    assert "bitte Auswahl prüfen" in panel.notes.text()
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-2")
+    panel.types.setCurrentItem(item)
+    assert "bitte Auswahl prüfen" not in panel.notes.text()
+
+
+def test_type_list_shows_about_seven_entries(qtbot):
+    win = _window(qtbot)
+    assert win.panel("parcel").types.minimumHeight() >= 220
+
+
+def test_open_in_editor_counts_as_changed(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    panel.editor_button.click()
+    assert win.files.modified() and "•" in win.windowTitle()
+
+
+def test_own_type_buttons_and_rename_keeps_the_choice(qtbot, tmp_path):
+    parcel.save_own(parcel.own_from_dict(_own_data()))
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    assert panel.chosen_type().id == "dhl-privat-1" and not panel.own_row.isVisibleTo(panel)
+    win.ask_parcel_type_name = lambda current: "Lager Nord"
+    win.rename_own_parcel_type("eigen-lager")
+    assert panel.chosen_type().id == "dhl-privat-1"             # Wahl bleibt
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "eigen-lager")
+    panel.types.setCurrentItem(item)
+    assert panel.own_row.isVisibleTo(panel)
+    renamed = []
+    panel.rename_requested.connect(renamed.append)
+    panel.rename_button.click()
+    assert renamed == ["eigen-lager"]
+    win.ask_remove_parcel_type = lambda name: True
+    panel.remove_button.click()
+    assert parcel.own_types() == []
+
+
+def test_damaged_own_types_are_shown_as_a_hint(qtbot, tmp_path):
+    parcel.own_dir().mkdir(parents=True)
+    (parcel.own_dir() / "kaputt.json").write_text("{nicht json")
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    assert "beschädigt" in panel.notes.text()
+
+
+@pytest.mark.parametrize("lang", ["de", "en"])
+def test_print_and_settings_never_overflow(qtbot, lang):
+    from PySide6.QtCore import QLocale
+    from labelwerk import i18n
+    from labelwerk.gui.app import load_theme
+    app = QApplication.instance()
+    i18n.set_language(lang)
+    app.setStyleSheet(load_theme())
+    try:
+        win = _window(qtbot)
+        win.fit_toolbars()
+        win.resize(1100, 800)
+        for _ in range(3):
+            QApplication.processEvents()
+        for action in (win.print_action, win.settings_action):
+            button = win.app_bar.widgetForAction(action)
+            assert button.isVisible(), action.text()
+            right = button.mapTo(win, button.rect().topRight()).x()
+            assert right <= win.width(), action.text()
+    finally:
+        app.setStyleSheet("")
+        i18n.set_language("de")
+        QLocale.setDefault(QLocale("de"))
+
+
+# --- Fenster „Eigener Markentyp“: Prüfung, Grenzen, Vorschau ------------------------------
+def test_editor_save_needs_a_valid_type_and_accept_checks(qtbot, tmp_path):
+    editor = _editor(qtbot, tmp_path)
+    save = editor.buttons.button(editor.buttons.StandardButton.Save)
+    editor.add_area((10, 10, 110, 60))
+    assert not save.isEnabled()                                 # ohne Namen
+    editor.accept()
+    assert editor.result() == 0 and "Namen" in editor.preview.text()
+    editor.name.setText("Test")
+    assert save.isEnabled()
+    assert editor.name.maxLength() == 200
+
+
+def test_editor_areas_stay_on_the_page(qtbot, tmp_path):
+    editor = _editor(qtbot, tmp_path)
+    editor.add_area((10, 10, 60, 40))
+    area = editor._areas[1][0]
+    area.setPos(QPointF(-500, 99999))
+    rect, page = area.scene_rect(), editor.view.scene().sceneRect()
+    assert page.contains(rect)
+
+
+def test_editor_warns_about_overlapping_areas(qtbot, tmp_path):
+    editor = _editor(qtbot, tmp_path)
+    editor.add_area((10, 10, 60, 40))
+    assert not editor.overlap.isVisibleTo(editor)
+    editor.add_area((50, 30, 90, 70))
+    assert editor.overlap.isVisibleTo(editor)
+
+
+def test_editor_preview_waits_while_moving_and_name_does_not_render(qtbot, tmp_path, monkeypatch):
+    editor = _editor(qtbot, tmp_path)
+    editor.add_area((10, 10, 60, 40))
+    calls = []
+    monkeypatch.setattr(editor, "_render_preview", lambda: calls.append(1))
+    editor.name.setText("Neu")
+    assert calls == []                                          # Name: keine neue Vorschau
+    area = editor._areas[1][0]
+    area.setPos(area.pos() + QPointF(5, 5))
+    assert calls == [] and editor._preview_timer.isActive()
+    editor._preview_now()                                       # Loslassen: sofort
+    assert calls == [1] and not editor._preview_timer.isActive()
diff --git a/tests/gui/test_gui_series.py b/tests/gui/test_gui_series.py
index bff94cd..a80b81e 100644
--- a/tests/gui/test_gui_series.py
+++ b/tests/gui/test_gui_series.py
@@ -63,7 +63,7 @@ def printed(monkeypatch):
 
 # --- Reiter und Quelle -------------------------------------------------------------------------
 def test_series_tab_follows_layout(qtbot):
-    assert [tool.key for tool in TOOLS][-1] == "series"
+    assert [tool.key for tool in TOOLS][-2:] == ["series", "parcel"]   # Paketmarke ganz hinten
     panel = _window(qtbot).panel("series")
     assert panel.source_label.text() == "Keine Serie"
     assert not panel.remove_button.isEnabled()
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index c35dd4b..44eee13 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -430,7 +430,7 @@ def test_dialog_start_tool_choice(qtbot, tmp_path):
     combo = dialog.start_tool
     assert combo.currentData() == "series"
     assert [combo.itemData(i) for i in range(combo.count())] == [
-        "last", "file", "paper", "text", "image", "barcode", "layout", "series"]
+        "last", "file", "paper", "text", "image", "barcode", "layout", "series", "parcel"]
     assert combo.itemText(0) == "Zuletzt benutzter" and combo.itemText(2) == "Papier"
     assert dialog.restart_hint.isHidden()
     combo.setCurrentIndex(combo.findData("last"))
diff --git a/tests/test_parcel.py b/tests/test_parcel.py
index eab3bab..8e91223 100644
--- a/tests/test_parcel.py
+++ b/tests/test_parcel.py
@@ -536,3 +536,34 @@ def test_version_mark_decides_between_hermes_labels(tmp_path):
     source = parcel.load(make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein V4.2.000")]))
     found = parcel.detect(source, "DE")
     assert found[0][0].id == "hermes-2" and parcel.ambiguous(found) == []
+
+
+# --- Hilfen für die Oberfläche ----------------------------------------------------------
+@pytest.mark.parametrize("env, expected", [
+    ({"LC_ALL": "de_DE.UTF-8"}, "DE"), ({"LANG": "de_AT.UTF-8"}, "DE"),
+    ({"LC_ALL": "", "LC_MESSAGES": "", "LANG": "C"}, "DE"), ({"LANG": "fr_FR.UTF-8"}, "DE")])
+def test_default_country_follows_the_region_or_takes_the_first(monkeypatch, env, expected):
+    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
+        monkeypatch.delenv(key, raising=False)
+    for key, value in env.items():
+        monkeypatch.setenv(key, value)
+    assert parcel.default_country() == expected     # nur DE im Katalog: sonst das erste Land
+
+
+def test_default_country_prefers_a_matching_region(monkeypatch):
+    monkeypatch.setattr(parcel, "countries", lambda: [("AT", "Österreich"), ("DE", "Deutschland")])
+    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
+    assert parcel.default_country() == "DE"
+    monkeypatch.setenv("LC_ALL", "C")
+    monkeypatch.setenv("LANG", "")
+    assert parcel.default_country() == "AT"
+
+
+def test_own_id_is_a_free_slug():
+    assert parcel.own_id("Mein Lager – Retoure", set()) == "eigen-mein-lager-retoure"
+    assert parcel.own_id("Mein Lager – Retoure", {"eigen-mein-lager-retoure"}) \
+        == "eigen-mein-lager-retoure-2"
+    assert parcel.own_id("äöü ß", set()) == "eigen-aeoeue-ss"
+    assert parcel.own_id("!!!", set()) == "eigen-typ"
+    slug = parcel.own_id("x" * 200, set())
+    assert len(slug) <= 64 and parcel.own_from_dict(_own(id=slug)).id == slug
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_parcel.py u. a.) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index c2e87ff..a9f5d5e 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -74,7 +74,18 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   Typen → `--type` verlangt), schneidet/dreht/skaliert die Stücke (Barcodes 1:1, verdeckte Teile weiß), quer
   liegende Marken gedreht, breiteres Band → größer, 100×150-Layout ab 95 mm (fehlt das Layout: neu angeordnet);
   eigene Typen in `$XDG_DATA_HOME/labelwerk/paketmarken`.
-- 2886 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+  GUI: Reiter PAKET (Land aus der Region / „Nur eigene Typen“, MARKE ÖFFNEN … mit Vorschau-Dialog oder Ablegen auf
+  Panel/Arbeitsfläche, Typliste nach Dienst mit ✓ erkannt/„ungeprüft“, Hinweise, Arbeitsfläche zeigt die Umwandlung
+  nur zur Ansicht ◀ n/N ▶, DRUCKEN – auch in der Werkzeugleiste – alle Etiketten in einem Auftrag, IM EDITOR ÖFFNEN
+  als normales Etikett; EIGENER TYP …: Fenster mit der Marke, Bereiche aufziehen/verschieben/Entf, Drehung,
+  „Barcode – nicht verkleinern“, Name, „Erkennen an“, Vorschau; Umbenennen/Löschen im Kontextmenü); Umwandlung
+  folgt Etikett (Reiter PAPIER) und Drucker; Gleichstand ungeprüfter Typen und „nicht erkannt“: kein Typ
+  vorgewählt, Hinweis nennt die Kandidaten; ✓ nur an den Besten; mit Marke ist die Arbeitsfläche nur Ansicht
+  (Bearbeiten gesperrt mit Hinweis, ohne Umwandlung leer, DRUCKEN druckt dann nicht); IM EDITOR ÖFFNEN gilt als
+  geändert; eigener Typ: SPEICHERN nur gültig, Bereiche auf der Seite, Überlappung gemeldet, Vorschau entprellt.
+- Werkzeugleiste: EINSTELLUNGEN/DRUCKEN in eigener Leiste rechts (appBar, nie im Überlauf – nur Reiterknöpfe laufen
+  über); Fenster beim Start so breit, dass alles passt (fit_toolbars nach dem Design, höchstens Bildschirmbreite).
+- 2938 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -245,7 +256,9 @@ src/labelwerk/
               Breite füllt das Band; fest: passt hinein, bessere Lage; fehlt das Layout fürs Format: arrange;
               Hinweis bei Barcodes < 97 %; rund → Fehler); arrange (Spalten längs des Bands, Barcodes 1:1);
               own_dir/own_types/own_warnings (beschädigt …)/own_from_dict (geprüft, Kanten ≥ 1 mm in der Seite)/
-              own_to_dict/save_own/remove_own
+              own_to_dict/save_own/remove_own;
+              default_country (Region aus LC_ALL › LC_MESSAGES › LANG, sonst erstes Land), own_id(name, taken)
+              („eigen-…“, frei)
   layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
               growing_axis (Endlosband wächst mit; align_objects am Papier: Anfang des Bereichs, auf Mindestlänge mittig –
               min_length –, nur wenn auch mit den übrigen Objekten (others) das Etikett dort klemmt), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
@@ -298,7 +311,22 @@ src/labelwerk/
                     current_row), Schnitt (Brother: set_cutter; CUPS/Zebra: set_driver_cuts mit den Optionen des Treibers bzw.
                     dem Modus, Signal driver_cut_chosen → Einstellungen je Modell); liest nur bei geänderter Quelle/Blatt/Nummerierung, check_file (Datei geändert, vor dem
                     Drucken), reload (Öffnen); Fehler und unbekannte Platzhalter als Hinweis
-    tools.py        Werkzeug-Registry (Datei, Papier, Text, Bild, Barcode, Layout, Serie; neue Werkzeuge als Eintrag; START_TOOL = Papier)
+    tools.py        Werkzeug-Registry (Datei, Papier, Text, Bild, Barcode, Layout, Serie, Paket; neue Werkzeuge als Eintrag; START_TOOL = Papier)
+    panels/parcel.py Reiter PAKET (ParcelPanel): Land, MARKE ÖFFNEN (Signal open_requested → MainWindow.ask_parcel_file),
+                    load(path) → parcel.load/detect/convert, Typliste (TYPE_ROLE; Überschriften nicht wählbar; eigene
+                    Typen mit Kontextmenü → rename_requested/remove_requested), set_target(label_id, model) (Umwandlung
+                    neu), documents/current_document (◀ ▶), print_requested(list), editor_requested(doc), own_requested,
+                    view_changed; Ablegen von PDF/PNG/JPG/GIF; ✓ nur an den Besten (_top), Gleichstand (_tied, ambiguous)
+                    ohne Vorwahl, „bitte Auswahl prüfen“ (_check_choice), error/show_render_error, Knöpfe UMBENENNEN/
+                    LÖSCHEN bei eigenem Typ (own_row), parcel.own_warnings als Hinweis
+                    MainWindow: _parcel_locked (Reiter PAKET mit Marke = nur Ansicht: Aktionen gesperrt, _parcel_blocks
+                    mit Hinweis in paste/undo/redo/Einfügen/Ablegen von Bilddaten, leeres Etikett ohne Umwandlung,
+                    print_label druckt nur die Umwandlung), app_bar + fit_toolbars (EINSTELLUNGEN/DRUCKEN nie im Überlauf)
+    parcel_editor.py ParcelTypeEditor (Fenster „Eigener Markentyp“): Seite der Marke (EDIT_DPI), Bereiche ziehen/verschieben/
+                    Entf (add_area, remove_selected), je Bereich Drehung und Barcode, Name, „Erkennen an“ (detect all),
+                    Vorschau über parcel.convert (entprellt PREVIEW_DELAY_MS, beim Loslassen sofort); type_data/result_type
+                    → parcel.own_from_dict; problem() (SPEICHERN nur gültig, accept prüft), Bereiche auf der Seite,
+                    overlapping() → Hinweis; Splitter Marke/Einstellungen
     file_session.py FileSession: Neu/Öffnen/Speichern, modified/update_title („•“), maybe_save (Rückfrage), Dokument an Ort und
                     Stelle ersetzen (Verlauf neu), Etikett muss zum Drucker passen, origin new|file|favorite (nur „new“ folgt
                     der geprüften Rolle, may_follow_roll; Speichern macht daraus „file“; modified() ohne leere Textrahmen; Neu nimmt die eingelegte Rolle), Favoriten (Vorlage öffnen, drucken über
@@ -324,7 +352,8 @@ src/labelwerk/
     panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
     panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen), Farbe (SCHWARZ immer,
                     ROT nur 62red auf einem Zweifarb-Modell: set_red_available; Signal color_chosen)
-    canvas.py       Etikett in echter Größe (Endlosband: Stück mit Vorschub, Länge ziehen = Stück), unbedruckbare Streifen
+    canvas.py       read_only/set_read_only (Umwandlung einer Paketmarke: keine Klicks, keine Auswahl, Anfasser
+                    aus; Ablegen und Zoom gehen); Etikett in echter Größe (Endlosband: Stück mit Vorschub, Länge ziehen = Stück), unbedruckbare Streifen
                     hellgrau (unprintable, keine Klicks), Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
                     Zierrahmen (frame_item unter den Objekten, keine Klicks; Einrasten am Innenraum);
                     Ablegen von Dateien/Bilddaten (Daten im dropEvent kopiert, Signal dropped danach, mm) und Symbolen (symbol_dropped); Anfasser-Vorschau mit
diff --git a/README.md b/README.md
index 3680ab5..10b762f 100644
--- a/README.md
+++ b/README.md
@@ -129,6 +129,14 @@ Auf 62 mm endlos ergibt das ein 15–28 cm langes Etikett, auf breiteren Bänder
 („ungeprüft“; ihre Kanten rücken an der Marke bis zum nächsten weißen Rand). Eigene Typen und neue Länder:
 `src/labelwerk/parcel_data/README.md`. Vor dem Versand prüfen, ob die Barcodes lesbar sind.
 
+In der Oberfläche: Reiter **PAKET** → MARKE ÖFFNEN … (oder die Datei aufs Panel bzw. die Arbeitsfläche ziehen). Der
+erkannte Typ ist mit ✓ gewählt, die Arbeitsfläche zeigt das Ergebnis für das Etikett aus dem Reiter PAPIER (nur
+Ansicht, ◀ ▶ bei mehreren Etiketten). DRUCKEN druckt alle Etiketten in einem Auftrag, IM EDITOR ÖFFNEN macht daraus
+ein normales Etikett (die Stücke sind Bilder). EIGENER TYP … öffnet die Marke groß: Bereiche mit der Maus aufziehen,
+je Bereich Drehung und „Barcode – nicht verkleinern“ wählen, Namen und optional einen Text zum Erkennen eintragen –
+labelwerk ordnet die Stücke selbst auf dem Band an. Eigene Typen lassen sich in der Liste umbenennen und löschen
+(rechte Maustaste).
+
 ## Architektur
 
 ```
diff --git a/docs/superpowers/specs/2026-10-19-paketmarken-design.md b/docs/superpowers/specs/2026-10-19-paketmarken-design.md
index d66b8f2..3ed7ec9 100644
--- a/docs/superpowers/specs/2026-10-19-paketmarken-design.md
+++ b/docs/superpowers/specs/2026-10-19-paketmarken-design.md
@@ -27,7 +27,7 @@ von paketikett wird kein Code übernommen. Originale des Nutzers kommen nicht in
    (Layout auf die bedruckbare Breite skaliert).
 3. **b – Ausgabe je Drucker:** 62 mm endlos (Brother) bzw. 100 × 150 mm (4×6-Etiketten, Zebra/CUPS); allgemein das
    Etikett des gewählten Druckers.
-4. **b – Reiter PAKETMARKE** in der GUI **und** CLI `labelwerk parcel`.
+4. **b – Reiter PAKET** (Überschrift „Paketmarke“) in der GUI **und** CLI `labelwerk parcel`.
 5. **a – Typ automatisch erkennen** (Text, Seitengröße), von Hand änderbar.
 6. **a – Kanten an die echte Marke anpassen:** Bereiche rücken nach außen bis zum nächsten weißen Rand.
 7. **b – eigene Typen gleich mit:** Bereiche auf einer Marke aufziehen, als eigenen Typ speichern.
@@ -94,19 +94,32 @@ Beispiele), Briefmarken/Internetmarke (geht schon über `print-file`), Texterken
   höchstens so verkleinert, dass sie quer passen, Barcodes 1:1 (nur zu breite kleiner); eigene Typen werden nie
   vergrößert.
 
-## 3 – Oberfläche: Reiter PAKETMARKE
-
-- **Werkzeug** `parcel` in `gui/tools.py` (auch `START_TOOLS`); Panel `panels/parcel.py`:
-  Land (Auswahl, Standard aus der Sprache/Region, nur Länder mit Typen + „Eigene“), MARKE ÖFFNEN … (PDF/PNG/JPG/GIF,
-  Ablegen auf das Panel), erkannter Typ vorgewählt (Liste nach Dienst gruppiert, „ungeprüft“-Kennzeichen), Vorschau
-  auf der Arbeitsfläche (erstes Etikett; mehrere: ◀ n/N ▶ wie Serie), DRUCKEN (alle Etiketten in einem Auftrag, Schnitt
-  nach jedem), IM EDITOR ÖFFNEN (Etikett als normales Dokument, Stücke verschiebbar; Rückfrage bei Änderungen wie
-  Neu).
-- **Eigener Typ:** EIGENEN TYP ANLEGEN … öffnet die Marke groß in einem Fenster; Bereiche aufziehen (Rechteck, Drehung
-  0/90/180/270, Häkchen „Barcode – nicht verkleinern“), Name, Speichern → `arrange` ordnet an; Umbenennen/Löschen in
-  der Liste. Eigene Typen erscheinen unter „Eigene“ und werden auch erkannt (Seitengröße + optional Textmuster aus
-  dem Fenster).
-- Nichts wird gedruckt, solange kein Typ gewählt ist; Fehler als Hinweis im Panel.
+## 3 – Oberfläche: Reiter PAKET (Panel-Überschrift „Paketmarke“)
+
+Der Reiter heißt kurz „PAKET“ (Tooltip „Paketmarke …“), damit die Werkzeugleiste auf Deutsch nicht überläuft;
+EINSTELLUNGEN und DRUCKEN stehen in einer eigenen Leiste rechts und laufen nie über (nur Reiterknöpfe dürfen es).
+
+- **Werkzeug** `parcel` in `gui/tools.py` (auch `START_TOOLS`/`HIDEABLE_TOOLS`); Panel `panels/parcel.py`:
+  Land (Auswahl, Standard aus der Region, nur Länder mit Typen + „Nur eigene Typen“), MARKE ÖFFNEN … (Dateidialog mit
+  Vorschau; PDF/PNG/JPG/GIF, Ablegen auf Panel oder Arbeitsfläche), Typliste nach Dienst gruppiert (etwa 7 Einträge
+  sichtbar), ✓ an den Typen mit der höchsten Punktzahl, „ungeprüft“-Kennzeichen; vorgewählt der beste – bei
+  Gleichstand ohne geprüften Sieger (`parcel.ambiguous`) oder ohne Treffer nichts (Hinweis nennt die Kandidaten),
+  bei Gleichstand mit Sieger Hinweis „bitte Auswahl prüfen“; Hinweise aus der Umwandlung, Fehler (`ParcelError`,
+  Renderfehler) und beschädigte eigene Typen im Panel.
+- **Nur Ansicht:** Mit geladener Marke zeigt die Arbeitsfläche das gewählte Etikett der Umwandlung (◀ n/N ▶) bzw. –
+  ohne Umwandlung – ein leeres Etikett; Aktionen des Bereichs Arbeitsfläche und Rückgängig/Wiederherstellen sind
+  gesperrt, Einfügen/Symbol/Bild/Ablegen von Bilddaten ändern nichts (Hinweis „nur Ansicht – IM EDITOR ÖFFNEN oder
+  anderen Reiter wählen“); eine abgelegte Datei lädt die Marke. Anderer Reiter: wieder das Dokument.
+- **DRUCKEN** (Panel, Werkzeugleiste, Strg+P): alle Etiketten in einem Auftrag, Schnitt nach jedem; ohne Umwandlung
+  nichts, Meldung „Erst den Markentyp wählen“ bzw. der Fehler. **IM EDITOR ÖFFNEN:** Etikett als normales Dokument
+  (Stücke verschiebbar), gilt als geändert (Rückfrage beim Schließen/Neu); Rückfrage bei Änderungen wie Neu.
+- **Eigener Typ:** EIGENER TYP … öffnet die Marke groß in einem Fenster (Splitter Marke/Einstellungen); Bereiche
+  aufziehen, verschieben (auf der Seite begrenzt), Entf löscht; Drehung 0/90/180/270, „Barcode – nicht verkleinern“,
+  Name (höchstens 200 Zeichen), „Erkennen an“; Hinweis bei überlappenden Bereichen; Vorschau des Ergebnisses
+  (entprellt, beim Loslassen sofort; der Name ändert sie nicht); SPEICHERN nur mit gültigem Typ
+  (`own_from_dict`), sonst der Grund in der Vorschau. Gewählter eigener Typ: Knöpfe UMBENENNEN …/LÖSCHEN unter der
+  Liste (auch Kontextmenü); Umbenennen behält die aktuelle Wahl. Eigene Typen erscheinen am Ende der Liste und
+  werden auch erkannt (Seitengröße + optional Textmuster).
 
 ## 4 – Kommandozeile
 
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index c6a5f40..e9816e8 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -159,6 +159,7 @@ class Canvas(QGraphicsView):
         self._handle_offset = QPointF()
         self._handle_cursor = False
         self._tool = "select"
+        self.read_only = False                             # nur Ansicht (Paketmarke): keine Klicks
         self._editing: int | None = None                   # Objekt im Schreibmodus
         self._edit_frame = QRectF()                        # Rahmen, Schreibmarke, Markierung
         self._caret: QLineF | None = None                  # (Druckpunkte in Leserichtung)
@@ -266,6 +267,7 @@ class Canvas(QGraphicsView):
             self.handle.setCursor(Qt.CursorShape.SizeHorCursor if self.orientation == "horizontal"
                                   else Qt.CursorShape.SizeVerCursor)
             self.handle.setToolTip(_("Drag: set the length · Double-click: automatic"))
+            self.handle.setVisible(not self.read_only)
         self._caption = self._caption_for(th)
         margin = _MARGIN_MM * self.mm
         scene.setSceneRect(-margin, -margin, tw + 2 * margin, th + 2 * margin)
@@ -315,7 +317,8 @@ class Canvas(QGraphicsView):
         return list(self._selection)
 
     def set_selection(self, indices: list[int]) -> None:
-        chosen = list(dict.fromkeys(i for i in indices if self._selectable(i)))
+        chosen = [] if self.read_only else list(dict.fromkeys(i for i in indices
+                                                              if self._selectable(i)))
         if chosen != self._selection:
             self._selection = chosen
             if self._drag not in ("move", "resize"):
@@ -531,7 +534,19 @@ class Canvas(QGraphicsView):
         feed = 2 * self.label.feed_margin / self.mm if self.label is not None else 0.0
         return min(max(mm, self.min_mm + feed), self.max_mm + feed)
 
+    def set_read_only(self, read_only: bool) -> None:
+        """Nur Ansicht (Umwandlung einer Paketmarke): Klicks, Ziehen und Doppelklick wirken
+        nicht, der Längen-Anfasser ist ausgeblendet; Ablegen und Zoom gehen weiter."""
+        self.read_only = read_only
+        if read_only:
+            self.cancel_object_drag()
+            self.set_selection([])
+        if self.handle is not None:
+            self.handle.setVisible(not read_only)
+
     def mousePressEvent(self, event) -> None:
+        if self.read_only:
+            return
         if event.button() != Qt.MouseButton.LeftButton:
             super().mousePressEvent(event)
             return
@@ -684,6 +699,8 @@ class Canvas(QGraphicsView):
             self.viewport().update()
 
     def mouseDoubleClickEvent(self, event) -> None:
+        if self.read_only:
+            return
         if self._on_handle(event):
             self.length_changed.emit(None)
             return
diff --git a/src/labelwerk/gui/file_session.py b/src/labelwerk/gui/file_session.py
index 98986a8..3ada15a 100644
--- a/src/labelwerk/gui/file_session.py
+++ b/src/labelwerk/gui/file_session.py
@@ -47,7 +47,7 @@ class FileSession(QObject):
         super().__init__(window)
         self.window = window
         self.path: Path | None = None               # gespeicherte Datei; None = unbenannt
-        self.origin = "new"                         # „new“ | „file“ | „favorite“ (Herkunft)
+        self.origin = "new"                         # „new“ | „file“ | „favorite“ | „parcel“ (Herkunft)
         self._template: str | None = None           # Name des Favoriten, solange unbenannt
         self._saved = copy.deepcopy(window.doc)     # Stand beim Öffnen/Speichern
         self._dir = ""                              # Ordner des letzten Öffnens/Speicherns
@@ -207,6 +207,17 @@ class FileSession(QObject):
                     _("Label “{label}” does not fit the {model} – using {new}").format(
                         label=wanted, model=self.window.model, new=doc.label_id), "warn")
 
+    def open_document(self, doc: Document) -> bool:
+        """Fertiges Etikett (z. B. Umwandlung einer Paketmarke) als neues, ungespeichertes
+        öffnen – Rückfrage bei Änderungen wie bei Neu; folgt nicht der Rolle; gilt als geändert
+        (Rückfrage beim Schließen/Neu). False = abgebrochen."""
+        if not self.maybe_save():
+            return False
+        self._replace(doc, None, origin="parcel")
+        self._saved = Document(doc.label_id)      # nirgends gespeichert: gilt als geändert
+        self.update_title()
+        return True
+
     def fitting_label(self, label_id: str) -> str:
         """``label_id``, wenn es zum Drucker passt, sonst die eingelegte Rolle, sonst 62 mm endlos
         bzw. das erste Etikett des Modells."""
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 566f6f2..adca5e6 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -9,7 +9,7 @@ from dataclasses import dataclass, replace
 from pathlib import Path
 
 from PIL import Image
-from PySide6.QtCore import QMimeData, Qt, QThreadPool, QTimer
+from PySide6.QtCore import QMimeData, QSignalBlocker, Qt, QThreadPool, QTimer
 from PySide6.QtGui import QAction, QActionGroup, QIcon
 from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFrame,
                                QHBoxLayout, QInputDialog, QLineEdit,
@@ -17,7 +17,7 @@ from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFrame
                                QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                                QWidget)
 
-from .. import barcodes, clipart, favorites, fonts, series
+from .. import barcodes, clipart, favorites, fonts, parcel, series
 from ..desktop import APP_NAME
 from ..detect import brother_busy
 from .. import cups, zpl
@@ -27,7 +27,7 @@ from ..printers import (UNTESTED_HINT, Printer, capabilities, choose, cups_print
 from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, Series, TextObject
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
-from ..i18n import N_, _, ngettext
+from ..i18n import N_, _, language, ngettext
 from ..labels import DPI, get_label, labels_for_model, length_limits
 from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, change_label, exact_rect,
                       fill_anchored, frame_area, growing_axis, insert_placement, match_objects,
@@ -38,13 +38,14 @@ from ..render import (Renderer, RenderedObject, font_warnings, render_document,
                       set_svg_rasterizer)
 from ..settings import (Settings, load_settings, network_entries, new_document, save_settings,
                         started_values, update_settings)
-from ..shortcuts import effective, without_conflicts
+from ..shortcuts import ACTIONS, effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
 from .history import History, restore
 from . import file_dialog, image_import
 from .image_import import CLIPBOARD, DROPPED, MIME_OBJECTS, SCREENSHOT, SYMBOL_SOURCE
 from .media_worker import MediaWorker
+from .parcel_editor import ParcelTypeEditor
 from .panels.image import CROP_FAILED
 from .panels.text import DEFAULT_PT
 from .file_session import FileSession
@@ -84,6 +85,8 @@ _SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
 OBJECT_PANELS = ("text", "image", "barcode")   # Panel je Objektart (Text, Bild, Barcode)
 CHECKING_ROLL = N_("Checking the roll – please print again in a moment.")
 PRINTING_WAIT = N_("Printing – please wait.")
+PARCEL_VIEW_ONLY = N_("Parcel label: view only – to edit, use OPEN IN EDITOR or choose another tab.")
+PARCEL_CHOOSE_TYPE = N_("Choose the parcel label type first.")
 
 
 def shrunk_hint(factor: float, mode: str) -> str:
@@ -135,6 +138,9 @@ class MainWindow(QMainWindow):
         self._text_pastes = 0                       # Text eingefügt seit dem letzten Ändern
         self._notice: str | None = None             # Meldung zum Einfügen von Bildern
         self._image_dir = ""                        # Ordner des zuletzt eingefügten Bilds
+        self._parcel_dir = ""                       # Ordner der zuletzt geöffneten Paketmarke
+        self._parcel_renderer = Renderer()          # Umwandlung einer Paketmarke (nur Ansicht)
+        self._parcel_disabled: set[str] = set()     # in der Ansicht der Paketmarke gesperrt
         self._portal: ScreenshotPortal | None = None   # Bildschirmfoto (beim ersten Gebrauch)
         self.symbol_window: SymbolDialog | None = None  # „Symbol einfügen“ (beim ersten Gebrauch)
         self._symbols_were_open = False             # Bildschirmfoto: Symbol-Fenster mit ausgeblendet
@@ -186,16 +192,25 @@ class MainWindow(QMainWindow):
         self.panels.currentChanged.connect(self._update_tool_buttons)   # SERIE: Knopf bis zum Wechsel
         self._stored_tool = self.settings.last_tool   # zuletzt benutzter Reiter, wie in der Datei
         self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
+        # EINSTELLUNGEN und DRUCKEN in einer eigenen Leiste rechts daneben: nie im Überlauf –
+        # überlaufen dürfen nur die Reiterknöpfe
+        self.app_bar = QToolBar(_("Actions"))
+        self.app_bar.setObjectName("appBar")
+        self.app_bar.setMovable(False)
+        self.app_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
+        self.addToolBar(self.app_bar)
         spacer = QWidget()
         spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
-        toolbar.addWidget(spacer)
+        self.app_bar.addWidget(spacer)
         self.settings_action = self._toolbar_action("app.settings", "preferences-system",
                                                     _("SETTINGS"), self.open_settings)
-        toolbar.addAction(self.settings_action)
+        self.app_bar.addAction(self.settings_action)
         self.print_action = self._toolbar_action("file.print", "document-print", _("PRINT"),
                                                  self.print_label)
-        toolbar.addAction(self.print_action)
-        toolbar.widgetForAction(self.print_action).setObjectName("print")
+        self.app_bar.addAction(self.print_action)
+        self.app_bar.widgetForAction(self.print_action).setObjectName("print")
+        self.tool_bar = toolbar
+        QTimer.singleShot(0, self.fit_toolbars)     # erst mit dem Design (apply_theme) messen
 
         # Arbeitsfläche
         self.canvas = Canvas(self.model)
@@ -320,6 +335,7 @@ class MainWindow(QMainWindow):
         self.panel("series").table_requested.connect(self.choose_series_table)
         self.panel("series").insert_column.connect(self.insert_column)
         self.panel("barcode").fill_preview = self._filled_barcode
+        self._connect_parcel()
         self._clipboard_changed()
         self.refresh_printer()
         self._fit_label()                           # Standard-Etikett eines anderen Druckers
@@ -329,6 +345,39 @@ class MainWindow(QMainWindow):
     def panel(self, key: str):
         return self._panel_by_key[key]
 
+    def fit_toolbars(self) -> None:
+        """Mit dem Design gemessen: die Leiste EINSTELLUNGEN/DRUCKEN nie schmaler als ihre Knöpfe
+        (die Reiterknöpfe laufen bei Platzmangel über), das Fenster beim Start so breit, dass
+        alles passt – höchstens so breit wie der Bildschirm."""
+        ext = self.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
+        if ext is not None:                         # Überlauf-Knopf sichtbar beschriften
+            ext.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
+            ext.setText("»")
+            ext.setToolTip(_("More tabs"))
+        buttons = sum(self.app_bar.widgetForAction(a).sizeHint().width()
+                      for a in (self.settings_action, self.print_action))
+        self.app_bar.setMinimumWidth(buttons + 24)
+        screen = self.screen().availableGeometry().width() if self.screen() else 0
+        wanted = self.tool_bar.sizeHint().width() + buttons + 48
+        if screen:
+            wanted = min(wanted, screen)
+        if wanted > self.width():
+            self.resize(wanted, self.height())
+
+    def _connect_parcel(self) -> None:
+        """Reiter PAKET: Umwandlung auf der Arbeitsfläche, Drucken, Editor, eigene Typen."""
+        if "parcel" not in self._panel_by_key:
+            return
+        panel = self.panel("parcel")
+        panel.view_changed.connect(self.render_now)
+        panel.open_requested.connect(self.open_parcel_file)
+        panel.print_requested.connect(self.print_documents)
+        panel.editor_requested.connect(self.open_parcel_in_editor)
+        panel.own_requested.connect(self.new_own_parcel_type)
+        panel.rename_requested.connect(self.rename_own_parcel_type)
+        panel.remove_requested.connect(self.remove_own_parcel_type)
+        self.panels.currentChanged.connect(self._parcel_view_switched)
+
     def _toolbar_action(self, key: str, icon: str, text: str, handler) -> QAction:
         """Aktion aus dem Verzeichnis als Knopf der Werkzeugleiste (Kürzel bleibt änderbar)."""
         action = self.shortcut_actions[key]
@@ -608,6 +657,17 @@ class MainWindow(QMainWindow):
                 panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))
 
     def _update_edit_actions(self) -> None:
+        if self._parcel_locked():                   # Paketmarke: nur Ansicht
+            for entry in ACTIONS:
+                action = self.shortcut_actions[entry.id]
+                if (entry.scope == "canvas" or entry.id in ("edit.undo", "edit.redo")) \
+                        and action.isEnabled():
+                    action.setEnabled(False)
+                    self._parcel_disabled.add(entry.id)
+            return
+        for key in self._parcel_disabled:           # wieder wie vorher, Rest regelt das Folgende
+            self.shortcut_actions[key].setEnabled(True)
+        self._parcel_disabled.clear()
         if self.edit_session.update_actions(self.shortcut_actions):   # wirken auf den Editor
             return
         self.shortcut_actions["text.end_edit"].setEnabled(False)
@@ -633,6 +693,11 @@ class MainWindow(QMainWindow):
         if self.canvas.is_dragging():   # Ziehen nicht unterbrechen – nach dem Loslassen rendern
             self._timer.start()
             return
+        if self._render_parcel():                   # Reiter PAKET mit Marke: nur Ansicht
+            return
+        if self.canvas.read_only:
+            self.canvas.set_read_only(False)
+            self._update_edit_actions()             # Bearbeiten wieder möglich
         view = self._view_doc()
         try:
             # jedes Objekt höchstens einmal messen und zeichnen; Fläche und „ragt hinaus“
@@ -694,6 +759,167 @@ class MainWindow(QMainWindow):
         self.panel("barcode").update_check()        # Serie: Prüfhinweis zur Vorschau-Zeile
         self.edit_session.update_marks()            # Schreibmarke zum neuen Zeilensatz
 
+    # --- Paketmarke (Reiter PAKET) ------------------------------------------------
+    def _parcel_shown(self) -> bool:
+        """Reiter PAKET ist zu sehen."""
+        return ("parcel" in self._panel_by_key
+                and self.panels.currentWidget() is self.panel("parcel"))
+
+    def _parcel_locked(self) -> bool:
+        """Reiter PAKET mit geladener Marke: Arbeitsfläche ist nur Ansicht (mit oder ohne
+        Umwandlung) – nichts ändert das Dokument."""
+        return self._parcel_shown() and self.panel("parcel").source is not None
+
+    def _parcel_blocks(self) -> bool:
+        """Bearbeiten im Reiter PAKET mit Marke: Hinweis statt Änderung (True = gesperrt)."""
+        if not self._parcel_locked():
+            return False
+        self._set_result(_(PARCEL_VIEW_ONLY), "error")
+        return True
+
+    def _render_parcel(self) -> bool:
+        """Reiter PAKET mit geladener Marke: die Arbeitsfläche zeigt das gewählte Etikett der
+        Umwandlung bzw. – ohne Umwandlung (nicht erkannt, Typ nicht gewählt, Fehler) – ein leeres
+        Etikett, immer nur zur Ansicht (True); ohne Marke das Dokument (False). Die Umwandlung
+        folgt dem Etikett des Dokuments und dem Drucker."""
+        if not self._parcel_shown():
+            return False
+        panel = self.panel("parcel")
+        blocker = QSignalBlocker(panel)             # Umwandlung neu – gezeigt wird hier gleich
+        panel.set_target(self.doc.label_id, self.model)
+        del blocker
+        if panel.source is None:
+            return False
+        self.finish_editing()
+        self.canvas.set_selection([])
+        doc = panel.current_document()
+        try:
+            if doc is None:
+                raise ValueError(None)
+            result = self._parcel_renderer.render(doc, self.model)
+        except ValueError as e:
+            if e.args and e.args[0]:
+                panel.show_render_error(str(e))
+            doc = Document(self.doc.label_id, length_mm=self.doc.length_mm,
+                           orientation=self.doc.orientation)   # leer: nichts zu sehen
+            result = self._parcel_renderer.render(doc, self.model)
+        size = result.size
+        count = len(result.objects)
+        self.canvas.set_read_only(True)
+        self.canvas.set_document(get_label(doc.label_id), size, result.objects, doc.orientation,
+                                 printable_area(doc, self.model, size), keep_ratio=[False] * count,
+                                 grow=None, keep_aspect=[False] * count, frame=result.frame)
+        self._update_edit_actions()
+        return True
+
+    def _parcel_view_switched(self, _index: int = 0) -> None:
+        """Reiterwechsel: Arbeitsfläche zeigt die Umwandlung bzw. wieder das Dokument."""
+        self.render_now()
+
+    def ask_parcel_file(self) -> str | None:
+        """Dateidialog „Paketmarke öffnen“ mit Vorschau (in Tests ersetzbar); None = abgebrochen."""
+        path = file_dialog.ask_open(self, _("Open parcel label"), self._parcel_dir,
+                                    _("Parcel labels (*.pdf *.png *.jpg *.jpeg *.gif);;"
+                                      "All files (*)"),
+                                    system=self.system_dialog, model=self.model)
+        if path:
+            self._parcel_dir = str(Path(path).parent)
+        return str(path) if path else None
+
+    def open_parcel_file(self) -> None:
+        """MARKE ÖFFNEN …: Datei wählen, laden, Typ erkennen, umwandeln (Fehler im Panel)."""
+        path = self.ask_parcel_file()
+        if path:
+            self.panel("parcel").load(path)
+
+    def print_documents(self, docs: list[Document]) -> None:
+        """Mehrere Etiketten (Umwandlung einer Paketmarke) in einem Auftrag drucken, Schnitt nach
+        jedem – gleiche Prüfungen und Rückfragen wie sonst."""
+        if not docs:
+            return
+        if self.is_printing():
+            self._set_result(_(PRINTING_WAIT), "error")
+            return
+        if not self._can_print(docs[0]):
+            return
+        red = get_label(docs[0].label_id).two_color and capabilities(self.model).two_color
+        images, outside = [], []
+        try:
+            for number, doc in enumerate(docs, start=1):
+                images.append(to_print_mode(render_document(doc, self.model), red))
+                if objects_outside(doc, self.model):
+                    outside.append(number)
+        except ValueError as e:
+            self._set_result(str(e), "error")
+            return
+        self._print(images if len(images) > 1 else images[0], docs[0], outside)
+
+    def open_parcel_in_editor(self, doc: Document) -> None:
+        """Gezeigtes Etikett der Umwandlung als gewöhnliches Etikett öffnen (Rückfrage bei
+        Änderungen wie bei Neu); danach zeigt die Arbeitsfläche wieder den Editor."""
+        if self.files.open_document(copy.deepcopy(doc)):
+            self._tool_triggered("paper")
+            self.tool_actions["paper"].setChecked(True)
+
+    def exec_parcel_editor(self, editor: ParcelTypeEditor) -> bool:
+        """Fenster „Eigener Markentyp“ zeigen (in Tests ersetzbar); True = gespeichert."""
+        return editor.exec() == ParcelTypeEditor.DialogCode.Accepted
+
+    def new_own_parcel_type(self) -> None:
+        """EIGENEN TYP ANLEGEN …: Bereiche auf der geöffneten Marke festlegen, speichern."""
+        panel = self.panel("parcel")
+        if panel.source is None:
+            return
+        taken = {t.id for t in parcel.own_types()}
+        editor = ParcelTypeEditor(self, panel.source, self.doc.label_id, self.model, taken)
+        try:
+            if not self.exec_parcel_editor(editor):
+                return
+            ptype = editor.result_type()
+            parcel.save_own(ptype)
+        except (parcel.ParcelError, OSError) as e:
+            self._set_result(_("Own type not saved: {error}").format(error=e), "error")
+            return
+        finally:
+            editor.deleteLater()
+        panel.refresh_types(ptype.id)
+        self._set_result(_("Own type “{name}” saved").format(name=ptype.name), "ok")
+
+    def ask_parcel_type_name(self, current: str) -> str | None:
+        """Neuer Name eines eigenen Typs (in Tests ersetzbar); None = abgebrochen."""
+        name, ok = QInputDialog.getText(self, _("Rename own type"), _("Name:"), text=current)
+        return name.strip() if ok and name.strip() else None
+
+    def ask_remove_parcel_type(self, name: str) -> bool:
+        """Rückfrage vor dem Löschen eines eigenen Typs (in Tests ersetzbar)."""
+        return QMessageBox.question(
+            self, _("Delete own type"), _("Delete the own type “{name}”?").format(name=name),
+            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
+            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
+
+    def rename_own_parcel_type(self, type_id: str) -> None:
+        try:
+            ptype = parcel.find(type_id)
+            name = self.ask_parcel_type_name(ptype.name)
+            if name is None:
+                return
+            parcel.save_own(replace(ptype, names={language() or "en": name}))
+        except (parcel.ParcelError, OSError) as e:
+            self._set_result(str(e), "error")
+            return
+        self.panel("parcel").refresh_types()            # gewählter Typ bleibt gewählt
+
+    def remove_own_parcel_type(self, type_id: str) -> None:
+        try:
+            ptype = parcel.find(type_id)
+            if not self.ask_remove_parcel_type(ptype.name):
+                return
+            parcel.remove_own(type_id)
+        except (parcel.ParcelError, OSError) as e:
+            self._set_result(str(e), "error")
+            return
+        self.panel("parcel").refresh_types()
+
     def _drop_stale_view(self) -> None:
         """Nach einem Renderfehler: Objektbilder, die nicht mehr zu ``doc.objects`` passen
         (gelöscht, eingefügt, umsortiert – ``_structure_changing``), von der Arbeitsfläche
@@ -724,12 +950,16 @@ class MainWindow(QMainWindow):
     def undo(self) -> None:
         """Rückgängig – im Schreibmodus erst innerhalb der Bearbeitung (``TextEditSession.undo``),
         dann im Dokument (Knopf und Strg+Z gleich)."""
+        if self._parcel_blocks():
+            return
         self.accept_pending_input()                 # eben Getipptes ist der letzte Schritt
         if not self.edit_session.undo():
             self._restore(self.history.undo(self.doc, self.canvas.selection()))
 
     def redo(self) -> None:
         """Wiederherstellen – im Schreibmodus erst im Editor, dann im Dokument (wie ``undo``)."""
+        if self._parcel_blocks():
+            return
         self.accept_pending_input()
         if not self.edit_session.redo():
             self._restore(self.history.redo(self.doc, self.canvas.selection()))
@@ -801,6 +1031,8 @@ class MainWindow(QMainWindow):
 
         Schrift aus den Einstellungen (automatische Größe → 19 pt). Andere leere Texte sind
         unsichtbar und drucken nicht – sie entfallen dabei."""
+        if self._parcel_blocks():
+            return
         self.finish_editing()
         self._structure_changing()
         self._commit()
@@ -1134,6 +1366,8 @@ class MainWindow(QMainWindow):
         Zwischenablage“ erreichbar) › Bild (Mitte des bedruckbaren Bereichs). Eingefügtes ist
         ausgewählt. Im Schreibmodus Text in den Text (als reiner Text). Nur hier werden die
         Daten der Zwischenablage gelesen."""
+        if self._parcel_blocks():
+            return
         if self.edit_session.paste():
             return
         if self._owns_clipboard() or (self._clipboard and self._system.empty):
@@ -1235,6 +1469,8 @@ class MainWindow(QMainWindow):
         bedruckbaren Bereichs. Bei einem PDF mit mehreren Seiten wird die Seite erfragt
         (``page`` gibt sie vor). Fehler stehen verständlich in der Statusleiste; was sich
         laden ließ, wird eingefügt (ein Schritt)."""
+        if self._parcel_blocks():
+            return
         objects, notes, failed = [], [], False
         for path in map(Path, paths):
             pdf = path.suffix.lower() == ".pdf"
@@ -1370,6 +1606,8 @@ class MainWindow(QMainWindow):
         """Symbol als Bild-Objekt einfügen: längere Seite ``SYMBOL_MM`` (höchstens quer zum
         Band bedruckbar), auf den Inhalt zugeschnitten, Strich, Vektor wenn SVG; Platzierung wie
         Bilder; danach „Zuletzt verwendet“."""
+        if self._parcel_blocks():
+            return
         if self._timer.isActive():
             self.render_now()                       # aktueller bedruckbarer Bereich
         try:
@@ -1401,6 +1639,8 @@ class MainWindow(QMainWindow):
         mittig im Innenraum bzw. bedruckbaren Bereich, lieber gedreht als kleiner; auf einem
         Endlosband hinter den vorhandenen Objekten) – ausgewählt, der Inhalt markiert im Fokus:
         Tippen ersetzt das Beispiel."""
+        if self._parcel_blocks():
+            return
         self.finish_editing()
         if self._timer.isActive():
             self.render_now()                       # aktueller bedruckbarer Bereich
@@ -1456,7 +1696,13 @@ class MainWindow(QMainWindow):
     def _dropped(self, paths: list[Path], image: Image.Image | None, x_mm: float,
                  y_mm: float) -> None:
         """Bilddateien oder Bilddaten auf die Arbeitsfläche abgelegt: an der Ablagestelle
-        (kommt nach dem Ablegen, ``Canvas.dropped`` – ein PDF-Seitendialog ist dann möglich)."""
+        (kommt nach dem Ablegen, ``Canvas.dropped`` – ein PDF-Seitendialog ist dann möglich).
+        Im Reiter PAKET lädt eine abgelegte Datei die Marke, Bilddaten ändern nichts."""
+        if self._parcel_shown() and paths:
+            self.panel("parcel").load(paths[0])
+            return
+        if self._parcel_blocks():
+            return
         if paths:
             self.insert_image_files(paths, at=(x_mm, y_mm))
         elif image is not None:
@@ -1466,6 +1712,8 @@ class MainWindow(QMainWindow):
                         at: tuple[float, float] | None = None, dpi: float = DPI) -> None:
         """Bild ohne Auflösungsangabe (Zwischenablage, Bilddaten, Bildschirmfoto) einfügen –
         300 dpi, also 1 Pixel = 1 Druckpunkt."""
+        if self._parcel_blocks():
+            return
         notes: list[str] = []
         self._insert_images([self._new_image(image, dpi, source, None, notes)], at, notes)
 
@@ -1871,6 +2119,13 @@ class MainWindow(QMainWindow):
 
     def print_label(self) -> None:
         self.accept_pending_input()
+        if self._parcel_locked():                   # Reiter PAKET mit Marke: nur sie drucken
+            panel = self.panel("parcel")
+            if panel.documents():
+                self.print_documents(panel.documents())   # was die Arbeitsfläche zeigt
+            else:
+                self._set_result(panel.error or _(PARCEL_CHOOSE_TYPE), "error")
+            return
         if self._timer.isActive():
             self.render_now()
         if self.doc.series is not None:             # rendert jede Zeile selbst (Fehler: „Zeile n“)
diff --git a/src/labelwerk/gui/panels/parcel.py b/src/labelwerk/gui/panels/parcel.py
new file mode 100644
index 0000000..a7fdb96
--- /dev/null
+++ b/src/labelwerk/gui/panels/parcel.py
@@ -0,0 +1,399 @@
+"""Panel des Reiters PAKET (Überschrift „Paketmarke“): Marke öffnen, Typ wählen (erkannt), Umwandlung ansehen, drucken oder als
+Etikett in den Editor holen; eigene Typen anlegen, umbenennen, löschen.
+
+Die Logik steckt in ``labelwerk.parcel``; das Panel hält nur die geladene Marke, den gewählten
+Typ und die Umwandlung für das Etikett des Hauptfensters (``set_target``). Die Arbeitsfläche zeigt
+die Umwandlung, solange dieses Panel zu sehen ist (``documents``/``current_document``).
+"""
+from __future__ import annotations
+
+from pathlib import Path
+
+from PySide6.QtCore import Qt, Signal
+from PySide6.QtGui import QFont
+from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
+                               QPushButton, QToolButton, QWidget)
+
+from ... import parcel
+from ...document import Document
+from ...i18n import N_, _, pgettext
+from . import Panel
+
+OWN = "own"                                   # Eintrag „Eigene Typen“ in der Länderauswahl
+UNVERIFIED = N_("unverified")
+TYPE_ROLE = Qt.ItemDataRole.UserRole          # Kennung des Typs an jedem Listeneintrag
+
+
+class ParcelPanel(Panel):
+    view_changed = Signal()                   # Umwandlung neu (Arbeitsfläche zeigen)
+    print_requested = Signal(list)            # Etiketten (Document) drucken – ein Auftrag
+    editor_requested = Signal(object)         # Etikett (Document) im Editor öffnen
+    own_requested = Signal()                  # Fenster „Eigener Typ“ öffnen
+    rename_requested = Signal(str)            # eigener Typ (Kennung) umbenennen
+    remove_requested = Signal(str)            # eigener Typ (Kennung) löschen
+    open_requested = Signal()                 # MARKE ÖFFNEN … (Dateidialog im Hauptfenster)
+
+    def __init__(self, doc: Document):
+        super().__init__(doc, _("Parcel label"))
+        self.source: parcel.Source | None = None
+        self.path: Path | None = None
+        self.conversion: parcel.Conversion | None = None
+        self._label_id = doc.label_id
+        self._model = "QL-600"
+        self._current = 0                      # gezeigtes Etikett der Umwandlung
+        self._error: str | None = None
+        self._scores: dict[str, float] = {}    # erkannte Typen → Punktzahl
+        self._tied: list[str] = []             # Gleichstand ohne geprüften Sieger: Nutzer wählt
+        self._top: list[str] = []              # Typen mit der höchsten Punktzahl (✓)
+        self._check_choice = False             # vorgewählt, aber andere gleich gut: prüfen
+        self.setAcceptDrops(True)
+
+        self.section(_("Country"))
+        self.country = QComboBox()
+        for code, name in parcel.countries():
+            self.country.addItem(name, code)
+        self.country.addItem(_("Own types only"), OWN)
+        self.country.setCurrentIndex(max(0, self.country.findData(parcel.default_country())))
+        self.layout_.addWidget(self.country)
+
+        self.section(_("File"))
+        self.open_button = QPushButton(_("OPEN PARCEL LABEL …"))
+        self.open_button.setToolTip(_("PDF or image of a parcel label (DHL, Hermes …) – "
+                                      "or drop the file here"))
+        self.layout_.addWidget(self.open_button)
+        self.file_label = QLabel(_("No parcel label open – open one or drop the file here."))
+        self.file_label.setWordWrap(True)
+        self.file_label.setTextFormat(Qt.TextFormat.PlainText)
+        self.layout_.addWidget(self.file_label)
+
+        self.section(pgettext("parcel", "Type"))
+        self.types = QListWidget()
+        rows = self.types.fontMetrics().lineSpacing() * 2 + 6    # Einträge brechen oft um
+        self.types.setMinimumHeight(max(220, 7 * rows // 2 * 2))       # etwa 7 Einträge
+        self.types.setWordWrap(True)                  # lange Typnamen brechen um
+        self.types.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
+        self.types.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
+        self.layout_.addWidget(self.types)
+        own_row = QWidget()                            # nur bei gewähltem eigenem Typ
+        own_layout = QHBoxLayout(own_row)
+        own_layout.setContentsMargins(0, 0, 0, 0)
+        self.rename_button = QPushButton(_("RENAME …"))
+        self.remove_button = QPushButton(_("DELETE"))
+        own_layout.addWidget(self.rename_button)
+        own_layout.addWidget(self.remove_button)
+        self.own_row = own_row
+        own_row.hide()
+        self.layout_.addWidget(own_row)
+        self.own_button = QPushButton(_("NEW OWN TYPE …"))
+        self.own_button.setToolTip(_("Draw the areas on the open parcel label and save them as "
+                                     "your own type"))
+        self.layout_.addWidget(self.own_button)
+
+        self.notes = QLabel()
+        self.notes.setObjectName("hint")
+        self.notes.setWordWrap(True)
+        self.notes.setTextFormat(Qt.TextFormat.PlainText)
+        self.notes.hide()
+        self.layout_.addWidget(self.notes)
+
+        self.section(_("Result"))
+        row = QWidget()
+        nav = QHBoxLayout(row)
+        nav.setContentsMargins(0, 0, 0, 0)
+        self.prev_button = QToolButton()
+        self.prev_button.setText("◀")
+        self.prev_button.setToolTip(_("Previous label on the canvas"))
+        self.page_label = QLabel()
+        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
+        self.next_button = QToolButton()
+        self.next_button.setText("▶")
+        self.next_button.setToolTip(_("Next label on the canvas"))
+        nav.addWidget(self.prev_button)
+        nav.addWidget(self.page_label, 1)
+        nav.addWidget(self.next_button)
+        self.layout_.addWidget(row)
+        self.print_button = QPushButton(_("PRINT"))
+        self.print_button.setToolTip(_("Print all labels of the parcel label in one job"))
+        self.layout_.addWidget(self.print_button)
+        self.editor_button = QPushButton(_("OPEN IN EDITOR"))
+        self.editor_button.setToolTip(_("Edit the shown label like any other label (pieces as "
+                                        "images)"))
+        self.layout_.addWidget(self.editor_button)
+        self.layout_.addStretch(1)
+
+        self.country.currentIndexChanged.connect(self._country_changed)
+        self.open_button.clicked.connect(self.open_requested)
+        self.types.currentItemChanged.connect(self._type_chosen)
+        self.types.customContextMenuRequested.connect(self._context_menu)
+        self.own_button.clicked.connect(self.own_requested)
+        self.rename_button.clicked.connect(self._rename_chosen)
+        self.remove_button.clicked.connect(self._remove_chosen)
+        self.prev_button.clicked.connect(lambda: self._go_to(self._current - 1))
+        self.next_button.clicked.connect(lambda: self._go_to(self._current + 1))
+        self.print_button.clicked.connect(self._print)
+        self.editor_button.clicked.connect(self._to_editor)
+        self._fill_types()
+        self._update()
+
+    # --- Zustand ------------------------------------------------------------------------
+    @property
+    def country_code(self) -> str:
+        return self.country.currentData()
+
+    @property
+    def error(self) -> str | None:
+        """Fehler beim Laden/Umwandeln (gezeigt im Panel), sonst None."""
+        return self._error
+
+    def show_render_error(self, message: str) -> None:
+        """Die Umwandlung ließ sich nicht rendern: als Hinweis, nicht druckbar."""
+        self.conversion, self._error = None, message
+        self._update()
+
+    def documents(self) -> list[Document]:
+        return list(self.conversion.documents) if self.conversion is not None else []
+
+    def current_document(self) -> Document | None:
+        docs = self.documents()
+        return docs[self._current] if docs else None
+
+    def chosen_type(self) -> parcel.ParcelType | None:
+        item = self.types.currentItem()
+        type_id = item.data(TYPE_ROLE) if item is not None else None
+        if not type_id:
+            return None
+        try:
+            return parcel.find(type_id)
+        except parcel.ParcelError:
+            return None
+
+    def set_target(self, label_id: str, model: str) -> None:
+        """Etikett und Drucker des Hauptfensters: die Umwandlung gilt für sie (neu bei Wechsel)."""
+        if (label_id, model) == (self._label_id, self._model):
+            return
+        self._label_id, self._model = label_id, model
+        if self.source is not None:
+            self._detect(keep=True)
+            self._convert()
+
+    # --- Laden --------------------------------------------------------------------------
+    def load(self, path: str | Path) -> bool:
+        """Marke laden, Typ erkennen und umwandeln; Fehler als Hinweis (nichts geladen)."""
+        try:
+            source = parcel.load(path)
+        except parcel.ParcelError as e:
+            self._show_error(str(e))
+            return False
+        self.source, self.path = source, Path(path)
+        self._detect(keep=False)
+        self._convert()
+        return True
+
+    def _detect(self, keep: bool) -> None:
+        """Typen erkennen (✓ an denen mit der höchsten Punktzahl); ``keep``: gewählten Typ
+        behalten – sonst den besten vorwählen, außer bei Gleichstand ohne geprüften Sieger oder
+        ohne Treffer (dann wählt der Nutzer)."""
+        chosen = self.chosen_type()
+        country = None if self.country_code == OWN else self.country_code
+        found = self._found(country)
+        if keep and chosen is not None:
+            wanted = chosen.id
+        elif self._tied or not found:
+            wanted = None                       # gleich gut oder nicht erkannt: Nutzer wählt
+        else:
+            wanted = found[0][0].id
+        self._check_choice = not keep and wanted is not None and len(self._top) > 1
+        self._fill_types(wanted)
+
+    def _found(self, country: str | None) -> list[tuple[parcel.ParcelType, float]]:
+        """Erkannte Typen (Punktzahl, Gleichstand) für die Quelle merken."""
+        found = parcel.detect(self.source, country, self._label_id)
+        if self.country_code == OWN:
+            found = [(t, s) for t, s in found if t.own]
+        self._scores = {t.id: s for t, s in found}
+        best = max(self._scores.values(), default=None)
+        self._top = [t.id for t, s in found if s == best]
+        self._tied = [t.id for t in parcel.ambiguous(found)]
+        return found
+
+    def _convert(self) -> None:
+        """Umwandlung für das Etikett des Hauptfensters (Fehler: Hinweis, keine Umwandlung)."""
+        self.conversion, self._current, self._error = None, 0, None
+        ptype = self.chosen_type()
+        if self.source is not None and ptype is not None:
+            try:
+                self.conversion = parcel.convert(self.source, ptype, self._label_id, self._model)
+            except (parcel.ParcelError, ValueError) as e:
+                self._error = str(e)
+        self._update()
+        self.view_changed.emit()
+
+    def _show_error(self, message: str) -> None:
+        self._error = message
+        self._update()
+
+    # --- Typen --------------------------------------------------------------------------
+    def _fill_types(self, wanted: str | None = None) -> None:
+        """Liste nach Dienst gruppiert (Überschriften nicht wählbar), eigene Typen am Ende;
+        erkannte Typen vorn in ihrer Gruppe mit ✓, ungeprüfte gekennzeichnet."""
+        self.types.blockSignals(True)
+        try:
+            self.types.clear()
+            groups: list[tuple[str, list[parcel.ParcelType]]] = []
+            if self.country_code != OWN:
+                for key, name in parcel.carriers(self.country_code):
+                    members = [t for t in parcel.types(self.country_code)
+                               if not t.own and t.carrier == key]
+                    if members:
+                        groups.append((name, members))
+            own = parcel.own_types()
+            if own:
+                groups.append((_("Own types"), own))
+            select = None
+            for name, members in groups:
+                head = QListWidgetItem(name.upper())
+                head.setFlags(Qt.ItemFlag.NoItemFlags)
+                font = QFont(head.font())
+                font.setBold(True)
+                head.setFont(font)
+                self.types.addItem(head)
+                members = sorted(members, key=lambda t: -self._scores.get(t.id, -1e9))
+                for ptype in members:
+                    text = ptype.name
+                    if ptype.id in self._top:
+                        text = "✓ " + text
+                    if not ptype.verified and not ptype.own:
+                        text = _("{name} · {unverified}").format(name=text, unverified=_(UNVERIFIED))
+                    item = QListWidgetItem(text)
+                    item.setData(TYPE_ROLE, ptype.id)
+                    item.setToolTip(ptype.name)
+                    self.types.addItem(item)
+                    if ptype.id == wanted:
+                        select = item
+            if select is not None:
+                self.types.setCurrentItem(select)
+                self.types.scrollToItem(select)
+        finally:
+            self.types.blockSignals(False)
+
+    def refresh_types(self, wanted: str | None = None) -> None:
+        """Eigene Typen geändert (angelegt, umbenannt, gelöscht): Liste und Umwandlung neu."""
+        current = self.chosen_type()
+        if self.source is not None:
+            country = None if self.country_code == OWN else self.country_code
+            self._found(country)
+        self._fill_types(wanted or (current.id if current is not None else None))
+        self._convert()
+
+    def _country_changed(self) -> None:
+        if self.source is not None:
+            self._detect(keep=False)
+        else:
+            self._fill_types()
+        self._convert()
+
+    def _type_chosen(self, *_args) -> None:
+        self._tied = []                         # gewählt: der Gleichstand ist entschieden
+        self._check_choice = False
+        self._convert()
+
+    def _chosen_own(self) -> str | None:
+        ptype = self.chosen_type()
+        return ptype.id if ptype is not None and ptype.own else None
+
+    def _rename_chosen(self) -> None:
+        if (type_id := self._chosen_own()) is not None:
+            self.rename_requested.emit(type_id)
+
+    def _remove_chosen(self) -> None:
+        if (type_id := self._chosen_own()) is not None:
+            self.remove_requested.emit(type_id)
+
+    def _context_menu(self, point) -> None:
+        item = self.types.itemAt(point)
+        type_id = item.data(TYPE_ROLE) if item is not None else None
+        if not type_id or not self._is_own(type_id):
+            return
+        menu = QMenu(self)
+        menu.addAction(_("Rename …"), lambda: self.rename_requested.emit(type_id))
+        menu.addAction(_("Delete"), lambda: self.remove_requested.emit(type_id))
+        menu.exec(self.types.viewport().mapToGlobal(point))
+
+    @staticmethod
+    def _is_own(type_id: str) -> bool:
+        return any(t.id == type_id for t in parcel.own_types())
+
+    # --- Ergebnis -----------------------------------------------------------------------
+    def _go_to(self, index: int) -> None:
+        docs = self.documents()
+        if docs and 0 <= index < len(docs):
+            self._current = index
+            self._update()
+            self.view_changed.emit()
+
+    def _print(self) -> None:
+        docs = self.documents()
+        if docs:
+            self.print_requested.emit(docs)
+
+    def _to_editor(self) -> None:
+        doc = self.current_document()
+        if doc is not None:
+            self.editor_requested.emit(doc)
+
+    def _update(self) -> None:
+        """Anzeige nach dem Zustand: Datei, Hinweise, Etikett n/N, Knöpfe."""
+        if self.path is not None:
+            self.file_label.setText(self.path.name)
+        notes = list(self.conversion.notes) if self.conversion is not None else []
+        if self._check_choice and self.chosen_type() is not None:
+            notes.insert(0, _("Several types fit equally well – please check the choice."))
+        if self.conversion is not None and self.conversion.layout == "arranged":
+            notes.insert(0, _("No layout for this label – the pieces were arranged anew."))
+        if self._error:
+            notes.insert(0, self._error)
+        elif self.source is not None and self.chosen_type() is None:
+            if self._tied:
+                names = ", ".join(parcel.find(type_id).name for type_id in self._tied)
+                notes.insert(0, _("Several types fit equally well ({types}) – choose one in the "
+                                  "list.").format(types=names))
+            elif not self._scores:
+                notes.insert(0, _("Type not recognised – choose it in the list."))
+            else:
+                notes.insert(0, _("Choose the type in the list."))
+        notes += parcel.own_warnings()          # beschädigte eigene Typen
+        self.own_row.setVisible(self._chosen_own() is not None)
+        self.notes.setText("\n".join(notes))
+        self.notes.setVisible(bool(notes))
+        docs = self.documents()
+        self.page_label.setText(_("Label {current}/{total}").format(
+            current=self._current + 1, total=len(docs)) if docs else "–")
+        self.prev_button.setEnabled(self._current > 0)
+        self.next_button.setEnabled(self._current < len(docs) - 1)
+        self.print_button.setEnabled(bool(docs))
+        self.editor_button.setEnabled(bool(docs))
+        self.own_button.setEnabled(self.source is not None)
+
+    # --- Ablegen ------------------------------------------------------------------------
+    def dragEnterEvent(self, event) -> None:
+        if _parcel_files(event.mimeData()):
+            event.acceptProposedAction()
+        else:
+            event.ignore()
+
+    def dragMoveEvent(self, event) -> None:
+        self.dragEnterEvent(event)
+
+    def dropEvent(self, event) -> None:
+        paths = _parcel_files(event.mimeData())
+        if not paths:
+            event.ignore()
+            return
+        event.acceptProposedAction()
+        self.load(paths[0])
+
+
+def _parcel_files(mime) -> list[Path]:
+    """Lokale Dateien mit Endung einer Paketmarke."""
+    return [Path(url.toLocalFile()) for url in mime.urls()
+            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in parcel.SUFFIXES]
diff --git a/src/labelwerk/gui/parcel_editor.py b/src/labelwerk/gui/parcel_editor.py
new file mode 100644
index 0000000..3f30212
--- /dev/null
+++ b/src/labelwerk/gui/parcel_editor.py
@@ -0,0 +1,430 @@
+"""Fenster „Eigener Markentyp“: Bereiche auf einer geöffneten Paketmarke aufziehen und als eigenen
+Typ speichern (``parcel.own_from_dict`` prüft, ``parcel.arrange`` ordnet beim Umwandeln an).
+
+Rechtecke auf der Marke ziehen (leere Stelle), verschieben (Rechteck ziehen), löschen (Entf); je
+Bereich Drehung im Uhrzeigersinn und „Barcode – nicht verkleinern“. Die Vorschau zeigt das Ergebnis
+auf dem Etikett des Hauptfensters.
+"""
+from __future__ import annotations
+
+from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
+from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
+from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
+                               QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
+                               QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout, QLabel,
+                               QLineEdit, QListWidget, QSpinBox, QSplitter, QVBoxLayout,
+                               QWidget)
+
+from .. import parcel
+from ..i18n import _, language
+from ..render import render_document
+
+EDIT_DPI = 100                      # Auflösung der Marke im Fenster
+MIN_MM = 3.0                        # kleinere Rechtecke zählen nicht (Klick statt Ziehen)
+PREVIEW_W = 420                     # Breite der Ergebnis-Vorschau in Pixeln
+PREVIEW_H = 220
+PREVIEW_DELAY_MS = 250              # Vorschau erst, wenn das Ziehen kurz ruht (beim Loslassen sofort)
+NAME_MAX = 200
+ROTATIONS = (0, 90, 180, 270)
+
+
+def gray_pixmap(image) -> QPixmap:
+    """Graustufenbild (PIL) als Pixmap – Weiß bleibt weiß (Marke, Vorschau)."""
+    gray = image.convert("L")
+    return QPixmap.fromImage(QImage(gray.tobytes(), gray.width, gray.height, gray.width,
+                                    QImage.Format.Format_Grayscale8).copy())
+
+
+class _Area(QGraphicsRectItem):
+    """Ein Bereich auf der Marke (Szene in Pixeln bei ``EDIT_DPI``), verschiebbar, mit Nummer."""
+
+    def __init__(self, rect: QRectF, number: int, moved):
+        super().__init__(QRectF(0, 0, rect.width(), rect.height()))
+        self.setPos(rect.topLeft())
+        self.rotation_ = 0
+        self.barcode = False
+        self._moved = moved
+        pen = QPen(QColor("#E00000"), 2)
+        pen.setCosmetic(True)
+        self.setPen(pen)
+        self.setBrush(QBrush(QColor(224, 0, 0, 40)))
+        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
+                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
+                      | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
+        self.label = QGraphicsSimpleTextItem(str(number), self)
+        self.label.setBrush(QColor("#E00000"))
+        self.label.setPos(4, 2)
+
+    def set_number(self, number: int) -> None:
+        self.label.setText(str(number))
+
+    def scene_rect(self) -> QRectF:
+        return self.mapRectToScene(self.rect())
+
+    def itemChange(self, change, value):
+        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
+            bounds = self.scene().sceneRect()         # nie über den Rand der Seite hinaus
+            if not bounds.isEmpty():
+                w, h = self.rect().width(), self.rect().height()
+                return QPointF(min(max(value.x(), bounds.left()), bounds.right() - w),
+                               min(max(value.y(), bounds.top()), bounds.bottom() - h))
+        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
+            self._moved()
+        return super().itemChange(change, value)
+
+
+class _PageView(QGraphicsView):
+    """Seite der Marke; Ziehen auf freier Fläche zeichnet ein neues Rechteck."""
+    drawn = Signal(QRectF)
+    released = Signal()                       # Maus losgelassen (Verschieben beendet)
+
+    def __init__(self):
+        super().__init__()
+        self.setScene(QGraphicsScene(self))
+        self.setBackgroundBrush(QColor("#9E9E9E"))
+        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
+        self._start: QPointF | None = None
+        self._rubber: QGraphicsRectItem | None = None
+
+    def mousePressEvent(self, event) -> None:
+        point = self.mapToScene(event.position().toPoint())
+        item = self.itemAt(event.position().toPoint())
+        if event.button() == Qt.MouseButton.LeftButton and not isinstance(item, (_Area,
+                                                                               QGraphicsSimpleTextItem)):
+            self.scene().clearSelection()
+            self._start = point
+            pen = QPen(QColor("#E00000"), 1, Qt.PenStyle.DashLine)
+            pen.setCosmetic(True)
+            self._rubber = self.scene().addRect(QRectF(point, point), pen)
+            return
+        super().mousePressEvent(event)
+
+    def mouseMoveEvent(self, event) -> None:
+        if self._start is not None and self._rubber is not None:
+            self._rubber.setRect(QRectF(self._start, self.mapToScene(event.position().toPoint()))
+                                 .normalized())
+            return
+        super().mouseMoveEvent(event)
+
+    def mouseReleaseEvent(self, event) -> None:
+        if self._start is not None and self._rubber is not None:
+            rect = self._rubber.rect()
+            self.scene().removeItem(self._rubber)
+            self._start = self._rubber = None
+            self.drawn.emit(rect)
+            return
+        super().mouseReleaseEvent(event)
+        self.released.emit()
+
+
+class ParcelTypeEditor(QDialog):
+    """Bereiche einer Marke als eigenen Typ festlegen; ``result_type`` liefert den geprüften Typ."""
+
+    def __init__(self, parent, source: parcel.Source, label_id: str, model: str,
+                 taken: set[str] | None = None):
+        super().__init__(parent)
+        self.setWindowTitle(_("New own parcel label type"))
+        self.source, self.label_id, self.model = source, label_id, model
+        self._taken = set(taken or ())
+        self._areas: dict[int, list[_Area]] = {}           # Seite → Bereiche
+        self._page = 1
+        k = EDIT_DPI / 25.4
+        self._k = k
+
+        self._preview_timer = QTimer(self)
+        self._preview_timer.setSingleShot(True)
+        self._preview_timer.setInterval(PREVIEW_DELAY_MS)
+        self._preview_timer.timeout.connect(self._render_preview)
+        self.view = _PageView()
+        self.view.drawn.connect(self._drawn)
+        self.view.released.connect(self._preview_now)
+        self.view.scene().selectionChanged.connect(self._selection_changed)
+        self.page_spin = QSpinBox()
+        self.page_spin.setRange(1, source.page_count)
+        self.page_spin.setPrefix(_("Page "))
+        self.page_spin.setVisible(source.page_count > 1)
+        self.page_spin.valueChanged.connect(self._show_page)
+
+        self.name = QLineEdit()
+        self.name.setMaxLength(NAME_MAX)
+        self.name.setPlaceholderText(_("e.g. Returns of my shop"))
+        self.words = QLineEdit()
+        self.words.setPlaceholderText(_("optional, e.g. a company name on the label"))
+        self.words.setToolTip(_("Text that is on every such label – labelwerk then recognises "
+                                "the type when opening (several words: separate with commas)"))
+        self.list = QListWidget()
+        self.list.currentRowChanged.connect(self._row_chosen)
+        self.rotation = QComboBox()
+        for degrees in ROTATIONS:
+            self.rotation.addItem(_("{degrees}° clockwise").format(degrees=degrees), degrees)
+        self.rotation.currentIndexChanged.connect(self._area_changed)
+        self.barcode = QCheckBox(_("Barcode – do not shrink"))
+        self.barcode.toggled.connect(self._area_changed)
+        self.preview = QLabel()
+        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
+        self.preview.setMinimumSize(PREVIEW_W, PREVIEW_H)
+        self.preview.setWordWrap(True)
+        self.preview.setObjectName("parcelPreview")
+        self.overlap = QLabel(_("Areas overlap – their content then appears twice on the label."))
+        self.overlap.setObjectName("note")
+        self.overlap.setWordWrap(True)
+        self.overlap.hide()
+        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
+                                        | QDialogButtonBox.StandardButton.Cancel)
+        self.buttons.accepted.connect(self.accept)
+        self.buttons.rejected.connect(self.reject)
+        self.name.textChanged.connect(self._check)        # Name ändert die Vorschau nicht
+
+        side = QWidget()
+        form = QFormLayout(side)
+        form.addRow(_("Name"), self.name)
+        form.addRow(_("Recognise by"), self.words)
+        hint = QLabel(_("Drag on the label to mark an area, drag an area to move it, Del removes "
+                        "the chosen one. Areas are placed on the tape in this order."))
+        hint.setWordWrap(True)
+        hint.setObjectName("note")
+        form.addRow(hint)
+        form.addRow(_("Areas"), self.list)
+        form.addRow(_("Rotation"), self.rotation)
+        form.addRow(self.barcode)
+        form.addRow(self.overlap)
+        form.addRow(_("Result"), self.preview)
+        left = QWidget()
+        left_layout = QVBoxLayout(left)
+        left_layout.setContentsMargins(0, 0, 0, 0)
+        left_layout.addWidget(self.page_spin)
+        left_layout.addWidget(self.view, 1)
+        self.splitter = QSplitter(Qt.Orientation.Horizontal)
+        self.splitter.addWidget(left)
+        self.splitter.addWidget(side)
+        self.splitter.setStretchFactor(0, 3)
+        self.splitter.setStretchFactor(1, 2)
+        outer = QVBoxLayout(self)
+        outer.addWidget(self.splitter, 1)
+        outer.addWidget(self.buttons)
+        self.resize(1100, 720)
+        self.splitter.setSizes([640, 440])          # Marke groß, Einstellungen daneben
+        self._show_page(1)
+        self._update()
+
+    # --- Seite und Bereiche -------------------------------------------------------------
+    def _show_page(self, number: int) -> None:
+        for area in self._areas.get(self._page, []):
+            self.view.scene().removeItem(area)
+        self._page = number
+        scene = self.view.scene()
+        for item in list(scene.items()):
+            if not isinstance(item, (_Area, QGraphicsSimpleTextItem)):
+                scene.removeItem(item)
+        try:
+            image = self.source.page(number, EDIT_DPI)
+        except (parcel.ParcelError, ValueError) as e:
+            self.preview.setText(str(e))
+            return
+        page = scene.addPixmap(gray_pixmap(image))
+        page.setZValue(-1)
+        scene.setSceneRect(QRectF(0, 0, image.width, image.height))
+        for area in self._areas.get(number, []):
+            scene.addItem(area)
+        self.view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
+        self._fill_list()
+
+    def showEvent(self, event) -> None:
+        super().showEvent(event)
+        self.view.fitInView(self.view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
+
+    def add_area(self, rect_mm, rotation: int = 0, barcode: bool = False) -> None:
+        """Bereich (x0, y0, x1, y1 in mm auf der gezeigten Seite) hinzufügen."""
+        x0, y0, x1, y1 = rect_mm
+        self._drawn(QRectF(x0 * self._k, y0 * self._k, (x1 - x0) * self._k, (y1 - y0) * self._k),
+                    rotation, barcode)
+
+    def _drawn(self, rect: QRectF, rotation: int = 0, barcode: bool = False) -> None:
+        bounds = self.view.scene().sceneRect()
+        rect = rect.intersected(bounds) if not bounds.isEmpty() else rect
+        if rect.width() < MIN_MM * self._k or rect.height() < MIN_MM * self._k:
+            return
+        areas = self._areas.setdefault(self._page, [])
+        area = _Area(rect, self._number(len(areas)), self._schedule_preview)
+        area.rotation_, area.barcode = rotation, barcode
+        areas.append(area)
+        self.view.scene().addItem(area)
+        self._fill_list()
+        self.list.setCurrentRow(len(areas) - 1)
+        self._update()
+
+    def _number(self, index: int) -> int:
+        """Laufende Nummer über alle Seiten (Reihenfolge auf dem Band)."""
+        return sum(len(self._areas.get(p, [])) for p in range(1, self._page)) + index + 1
+
+    def remove_selected(self) -> None:
+        areas = self._areas.get(self._page, [])
+        for area in [a for a in areas if a.isSelected()]:
+            areas.remove(area)
+            self.view.scene().removeItem(area)
+        for index, area in enumerate(areas):
+            area.set_number(self._number(index))
+        self._fill_list()
+        self._update()
+
+    def keyPressEvent(self, event) -> None:
+        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not self.name.hasFocus() \
+                and not self.words.hasFocus():
+            self.remove_selected()
+            return
+        super().keyPressEvent(event)
+
+    def _fill_list(self) -> None:
+        self.list.blockSignals(True)
+        self.list.clear()
+        for index, area in enumerate(self._areas.get(self._page, [])):
+            x0, y0, x1, y1 = self._mm(area)
+            text = _("{number}: {w} × {h} mm").format(number=self._number(index),
+                                                     w=round(x1 - x0), h=round(y1 - y0))
+            if area.barcode:
+                text += " · " + _("barcode")
+            self.list.addItem(text)
+        self.list.blockSignals(False)
+
+    def _mm(self, area: _Area) -> tuple[float, float, float, float]:
+        r = area.scene_rect()
+        return tuple(round(v / self._k, 1) for v in (r.left(), r.top(), r.right(), r.bottom()))
+
+    def _current_area(self) -> _Area | None:
+        areas = self._areas.get(self._page, [])
+        row = self.list.currentRow()
+        return areas[row] if 0 <= row < len(areas) else None
+
+    def _row_chosen(self, row: int) -> None:
+        area = self._current_area()
+        for widget in (self.rotation, self.barcode):
+            widget.setEnabled(area is not None)
+        if area is None:
+            return
+        self.view.scene().blockSignals(True)
+        self.view.scene().clearSelection()
+        area.setSelected(True)
+        self.view.scene().blockSignals(False)
+        for widget, value in ((self.rotation, ROTATIONS.index(area.rotation_)),
+                              (self.barcode, area.barcode)):
+            widget.blockSignals(True)
+            widget.setCurrentIndex(value) if widget is self.rotation else widget.setChecked(value)
+            widget.blockSignals(False)
+
+    def _selection_changed(self) -> None:
+        areas = self._areas.get(self._page, [])
+        try:
+            chosen = [i for i, a in enumerate(areas) if a.isSelected()]
+        except RuntimeError:                              # Fenster wird gerade abgebaut
+            return
+        if chosen and chosen[0] != self.list.currentRow():
+            self.list.setCurrentRow(chosen[0])
+
+    def _area_changed(self) -> None:
+        area = self._current_area()
+        if area is None:
+            return
+        area.rotation_ = self.rotation.currentData()
+        area.barcode = self.barcode.isChecked()
+        row = self.list.currentRow()
+        self._fill_list()
+        self.list.setCurrentRow(row)
+        self._update()
+
+    def _schedule_preview(self) -> None:
+        """Bereich wird verschoben: Liste und Prüfung sofort, Vorschau erst, wenn es ruht."""
+        row = self.list.currentRow()
+        self._fill_list()
+        self.list.setCurrentRow(row)
+        self._check()
+        self._preview_timer.start()
+
+    def _preview_now(self) -> None:
+        if self._preview_timer.isActive():
+            self._preview_timer.stop()
+            self._render_preview()
+
+    # --- Ergebnis -----------------------------------------------------------------------
+    def pieces(self) -> list[dict]:
+        """Bereiche in Bandreihenfolge (Seite für Seite) für ``parcel.own_from_dict``."""
+        out = []
+        for page in sorted(self._areas):
+            for area in self._areas[page]:
+                out.append({"page": page, "src": list(self._mm(area)), "rotation": area.rotation_,
+                            "kind": "barcode" if area.barcode else "text"})
+        return out
+
+    def type_data(self) -> dict:
+        name = self.name.text().strip()
+        words = [w.strip() for w in self.words.text().split(",") if w.strip()]
+        sizes = sorted({(round(w, 1), round(h, 1)) for w, h in self.source.sizes_mm})
+        return {"id": parcel.own_id(name, self._taken), "names": {language() or "en": name},
+                "source": {"sizes_mm": [list(s) for s in sizes]},
+                "detect": {"all": words} if words else {}, "pieces": self.pieces()}
+
+    def result_type(self) -> parcel.ParcelType:
+        """Geprüfter eigener Typ (``ParcelError``, wenn etwas fehlt)."""
+        return parcel.own_from_dict(self.type_data())
+
+    def problem(self) -> str | None:
+        """Was dem Speichern noch fehlt (übersetzt) – None, wenn der Typ gültig ist."""
+        if not self.name.text().strip():
+            return _("Enter a name.")
+        if not self.pieces():
+            return _("Mark at least one area.")
+        try:
+            self.result_type()
+        except parcel.ParcelError as e:
+            return str(e)
+        return None
+
+    def overlapping(self) -> bool:
+        """Überlappen sich Bereiche derselben Seite?"""
+        for areas in self._areas.values():
+            rects = [a.scene_rect() for a in areas]
+            for i, a in enumerate(rects):
+                if any(a.intersects(b) for b in rects[i + 1:]):
+                    return True
+        return False
+
+    def _check(self) -> None:
+        """SPEICHERN nur mit gültigem Typ; Hinweis bei überlappenden Bereichen."""
+        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self.problem() is None)
+        self.overlap.setVisible(self.overlapping())
+
+    def _update(self) -> None:
+        self._check()
+        self._preview_timer.stop()
+        self._render_preview()
+
+    def accept(self) -> None:
+        """Nur mit gültigem Typ schließen; sonst steht der Grund in der Vorschau."""
+        problem = self.problem()
+        if problem is not None:
+            self.preview.setPixmap(QPixmap())
+            self.preview.setText(problem)
+            return
+        super().accept()
+
+    def _render_preview(self) -> None:
+        """Ergebnis auf dem Etikett des Hauptfensters (erstes Etikett), verkleinert."""
+        if not self.pieces():
+            self.preview.setPixmap(QPixmap())
+            self.preview.setText(_("Mark at least one area."))
+            return
+        data = self.type_data()
+        data["names"] = data["names"] if self.name.text().strip() else {"en": "preview"}
+        try:
+            ptype = parcel.own_from_dict(data)
+            docs = parcel.convert(self.source, ptype, self.label_id, self.model).documents
+            image = render_document(docs[0], self.model)
+        except (parcel.ParcelError, ValueError) as e:
+            self.preview.setPixmap(QPixmap())
+            self.preview.setText(str(e))
+            return
+        if docs[0].orientation == "horizontal":        # Druckbild → Leserichtung
+            image = image.rotate(90, expand=True)
+        pixmap = gray_pixmap(image)
+        self.preview.setText("")
+        self.preview.setPixmap(pixmap.scaled(PREVIEW_W, PREVIEW_H, Qt.AspectRatioMode.KeepAspectRatio,
+                                             Qt.TransformationMode.SmoothTransformation))
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index dfd4019..aad307b 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -34,6 +34,8 @@ QToolBar#editBar { padding: 4px 6px; }
 QToolBar#editBar QToolButton { padding: 3px 10px; letter-spacing: 1px; }
 QToolBar#editBar::separator { background: #000000; width: 3px; margin: 2px 8px 5px 8px; }
 QToolBar QToolButton#print { background: #000000; color: #FFFFFF; }
+/* Überlauf der Reiterknöpfe: schmaler Knopf „»“ (Qt gibt ihm eine feste kleine Breite) */
+QToolBar QToolButton#qt_toolbar_ext_button { border: none; padding: 0; margin: 0; letter-spacing: 0; }
 QToolBar QToolButton#print:hover { background: #FFFFFF; color: #000000; }
 QToolBar QToolButton:disabled, QToolBar QToolButton#print:disabled {
     background: #F0F0F0;
diff --git a/src/labelwerk/gui/tools.py b/src/labelwerk/gui/tools.py
index 9a2d15e..c7c1aa7 100644
--- a/src/labelwerk/gui/tools.py
+++ b/src/labelwerk/gui/tools.py
@@ -15,6 +15,7 @@ from .panels.file import FilePanel
 from .panels.image import ImagePanel
 from .panels.layout import LayoutPanel
 from .panels.paper import PaperPanel
+from .panels.parcel import ParcelPanel
 from .panels.series import SeriesPanel
 from .panels.text import TextPanel
 
@@ -39,4 +40,6 @@ TOOLS = [
     Tool("layout", N_("Layout"), "align-horizontal-left", LayoutPanel),
     Tool("series", N_("Series"), "view-list-text", SeriesPanel,
          N_("Series from a table or numbering")),
+    Tool("parcel", N_("Parcel"), "mail-send", ParcelPanel,
+         N_("Convert a parcel label (DHL, Hermes …) for the label printer")),
 ]
diff --git a/src/labelwerk/parcel.py b/src/labelwerk/parcel.py
index 1a7f900..e177d47 100644
--- a/src/labelwerk/parcel.py
+++ b/src/labelwerk/parcel.py
@@ -161,6 +161,33 @@ def find(type_id: str) -> ParcelType:
     raise ParcelError(_("Unknown parcel label type: {id}").format(id=type_id))
 
 
+def default_country() -> str:
+    """Land der Region (Gebietsschema ``LC_ALL`` › ``LC_MESSAGES`` › ``LANG``, z. B. „de_DE“ → DE),
+    wenn es Typen dafür gibt – sonst das erste Land des Katalogs."""
+    codes = [code for code, _name in countries()]
+    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
+        value = os.environ.get(key, "")
+        if value:
+            region = value.split(".")[0].split("@")[0].partition("_")[2].upper()
+            if region in codes:
+                return region
+            break                                     # gesetzt, aber ohne passendes Land
+    return codes[0] if codes else ""
+
+
+_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
+
+
+def own_id(name: str, taken) -> str:
+    """Kennung für einen neuen eigenen Typ aus seinem Namen („eigen-…“, frei, gültig)."""
+    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold().translate(_UMLAUTS)).strip("-")
+    base = ("eigen-" + (slug or "typ"))[:58].rstrip("-")
+    candidate, number = base, 2
+    while candidate in taken or candidate in {t.id for t in _builtin()}:
+        candidate, number = f"{base}-{number}", number + 1
+    return candidate
+
+
 # --- Eigene Typen ----------------------------------------------------------------------
 def own_dir() -> Path:
     """Ordner der eigenen Markentypen (``$XDG_DATA_HOME/labelwerk/paketmarken``)."""
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index 6b5acf2..435345f 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -62,6 +62,10 @@ msgstr "ALLE"
 msgid "Action"
 msgstr "Aktion"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Actions"
+msgstr "Aktionen"
+
 #: src/labelwerk/shortcuts.py
 msgid "Actual size (100%)"
 msgstr "Echte Größe (100 %)"
@@ -168,6 +172,14 @@ msgstr "Auch möglich: {ids} (--type)"
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Areas"
+msgstr "Bereiche"
+
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Areas overlap – their content then appears twice on the label."
+msgstr "Bereiche überlappen – ihr Inhalt erscheint dann doppelt auf dem Etikett."
+
 #: src/labelwerk/zpl.py
 msgid "As set on the printer"
 msgstr "Wie am Drucker eingestellt"
@@ -216,6 +228,10 @@ msgstr "Barcode zu niedrig für den Klartext – höher ziehen oder Klartext aus
 msgid "Barcode without content"
 msgstr "Barcode ohne Inhalt"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Barcode – do not shrink"
+msgstr "Barcode – nicht verkleinern"
+
 #: src/labelwerk/gui/tools.py
 msgid "Barcodes and QR codes"
 msgstr "Barcodes und QR-Codes"
@@ -412,6 +428,14 @@ msgstr "PDF-Seite wählen"
 msgid "Choose printer"
 msgstr "Drucker wählen"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Choose the parcel label type first."
+msgstr "Erst den Markentyp wählen."
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Choose the type in the list."
+msgstr "Typ in der Liste wählen."
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Chosen printer {printer} not found – switch it on or specify it with -p."
@@ -497,6 +521,10 @@ msgstr "Umwandlung"
 msgid "Conversion of new images (symbols stay line art)"
 msgstr "Umwandlung neuer Bilder (Symbole bleiben Strich)"
 
+#: src/labelwerk/gui/tools.py
+msgid "Convert a parcel label (DHL, Hermes …) for the label printer"
+msgstr "Paketmarke (DHL, Hermes …) für den Etikettendrucker umwandeln"
+
 #: src/labelwerk/shortcuts.py
 msgid "Copy"
 msgstr "Kopieren"
@@ -509,6 +537,10 @@ msgstr "Nur Ecken"
 msgid "Count"
 msgstr "Anzahl"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Country"
+msgstr "Land"
+
 #: src/labelwerk/printer.py
 msgid "Cover opened while printing."
 msgstr "Deckel während des Drucks geöffnet."
@@ -555,6 +587,10 @@ msgstr "Schnitt"
 msgid "Cutting is set by the printer driver (system printer settings)"
 msgstr "Schneiden stellt der Druckertreiber ein (Druckerverwaltung des Systems)"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "DELETE"
+msgstr "LÖSCHEN"
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Dashed"
 msgstr "Gestrichelt"
@@ -568,6 +604,7 @@ msgstr "Standard"
 msgid "Default: {keys}"
 msgstr "Standard: {keys}"
 
+#: src/labelwerk/gui/panels/parcel.py
 #: src/labelwerk/shortcuts.py
 msgid "Delete"
 msgstr "Löschen"
@@ -581,6 +618,15 @@ msgstr "Favorit löschen"
 msgid "Delete favorite “{name}”?"
 msgstr "Favorit „{name}“ löschen?"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Delete own type"
+msgstr "Eigenen Typ löschen"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Delete the own type “{name}”?"
+msgstr "Den eigenen Typ „{name}“ löschen?"
+
 #: src/labelwerk/gui/panels/file.py
 msgid "Delete …"
 msgstr "Löschen …"
@@ -652,10 +698,18 @@ msgstr "Doppelt"
 msgid "Double-click: as {{column}} into the selected text object or as new text"
 msgstr "Doppelklick: als {{Spalte}} ins gewählte Textobjekt bzw. als neuer Text"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Drag on the label to mark an area, drag an area to move it, Del removes the chosen one. Areas are placed on the tape in this order."
+msgstr "Auf der Marke ziehen markiert einen Bereich, einen Bereich ziehen verschiebt ihn, Entf löscht den gewählten. Auf dem Band stehen die Bereiche in dieser Reihenfolge."
+
 #: src/labelwerk/gui/canvas.py
 msgid "Drag: set the length · Double-click: automatic"
 msgstr "Ziehen: Länge festlegen · Doppelklick: automatisch"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Draw the areas on the open parcel label and save them as your own type"
+msgstr "Bereiche auf der geöffneten Marke aufziehen und als eigenen Typ speichern"
+
 #: src/labelwerk/gui/image_import.py
 msgid "Dropped image"
 msgstr "Abgelegtes Bild"
@@ -668,6 +722,10 @@ msgstr "Duplizieren"
 msgid "Edit"
 msgstr "Bearbeiten"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Edit the shown label like any other label (pieces as images)"
+msgstr "Das gezeigte Etikett wie jedes andere bearbeiten (Stücke als Bilder)"
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Effective model: {model}"
@@ -686,6 +744,10 @@ msgstr "Leeres Etikett"
 msgid "End text editing"
 msgstr "Schreibmodus beenden"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Enter a name."
+msgstr "Bitte einen Namen eingeben."
+
 #. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
 #: src/labelwerk/storage.py
 #, python-brace-format
@@ -762,6 +824,7 @@ msgid "Favorites folder not created ({reason})"
 msgstr "Favoriten-Ordner nicht angelegt ({reason})"
 
 #: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/panels/parcel.py
 #: src/labelwerk/gui/tools.py
 msgid "File"
 msgstr "Datei"
@@ -1143,6 +1206,11 @@ msgstr "Etikett zu groß (Objekte zusammen {dots:.0f} Mio. Druckpunkte, höchste
 msgid "Label too large ({count} objects, at most {limit})"
 msgstr "Etikett zu groß ({count} Objekte, höchstens {limit})"
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "Label {current}/{total}"
+msgstr "Etikett {current}/{total}"
+
 #: src/labelwerk/printer.py
 #, python-brace-format
 msgid "Label {label!r} does not fit the printer ({model})."
@@ -1260,6 +1328,10 @@ msgstr "Rand: Zahl von 0 bis {max} mm"
 msgid "Margins"
 msgstr "Ränder"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Mark at least one area."
+msgstr "Mindestens einen Bereich markieren."
+
 #: src/labelwerk/shortcuts.py
 msgid "Maximize on paper"
 msgstr "Auf Papier maximieren"
@@ -1286,6 +1358,10 @@ msgstr "Modul"
 msgid "Module width {module!r} invalid – allowed: 1–{limit} dots"
 msgstr "Modulbreite {module!r} ungültig – erlaubt: 1–{limit} Druckpunkte"
 
+#: src/labelwerk/gui/main_window.py
+msgid "More tabs"
+msgstr "Weitere Reiter"
+
 #: src/labelwerk/shortcuts.py
 msgid "Move down (0.1 mm)"
 msgstr "Nach unten (0,1 mm)"
@@ -1326,6 +1402,10 @@ msgstr "Eigene"
 msgid "NEW"
 msgstr "NEU"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "NEW OWN TYPE …"
+msgstr "EIGENER TYP …"
+
 #: src/labelwerk/gui/panels/series.py
 msgid "NONE"
 msgstr "KEINE"
@@ -1334,6 +1414,7 @@ msgstr "KEINE"
 msgid "NUMBERING"
 msgstr "NUMMERIERUNG"
 
+#: src/labelwerk/gui/parcel_editor.py
 #: src/labelwerk/gui/settings_dialog.py
 msgid "Name"
 msgstr "Name"
@@ -1342,6 +1423,10 @@ msgstr "Name"
 msgid "Name of the favorite:"
 msgstr "Name des Favoriten:"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Name:"
+msgstr "Name:"
+
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
 msgid "Network printer {name}: address “{host}” invalid – only an IP address or name, without “tcp://” and port"
@@ -1361,6 +1446,14 @@ msgstr "Netzwerkdrucker"
 msgid "New label"
 msgstr "Neues Etikett"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "New own parcel label type"
+msgstr "Eigener Markentyp"
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Next label on the canvas"
+msgstr "Nächstes Etikett auf der Arbeitsfläche"
+
 #: src/labelwerk/gui/panels/series.py
 msgid "Next row on the canvas"
 msgstr "Nächste Zeile auf der Arbeitsfläche"
@@ -1410,6 +1503,10 @@ msgstr "Kein Etikett für die eingelegte Rolle ({media}) beim {model}."
 msgid "No labels to print"
 msgstr "Keine Etiketten zum Drucken"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "No layout for this label – the pieces were arranged anew."
+msgstr "Kein Layout für dieses Etikett – die Stücke wurden neu angeordnet."
+
 #: src/labelwerk/cli.py
 msgid ""
 "No network printer configured (GUI settings).\n"
@@ -1427,6 +1524,10 @@ msgstr ""
 "Noch keine eigenen Symbole. SVG- oder PNG-Dateien in diesen Ordner legen (Unterordner werden nicht gelesen):\n"
 "{path}"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "No parcel label open – open one or drop the file here."
+msgstr "Keine Paketmarke geöffnet – öffnen oder die Datei hier ablegen."
+
 #: src/labelwerk/media.py
 #: src/labelwerk/printer.py
 #: src/labelwerk/zpl.py
@@ -1526,6 +1627,14 @@ msgstr "Zahlen ohne Datei: Spalte „{column}“"
 msgid "OPEN FOLDER"
 msgstr "ORDNER ÖFFNEN"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "OPEN IN EDITOR"
+msgstr "IM EDITOR ÖFFNEN"
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "OPEN PARCEL LABEL …"
+msgstr "MARKE ÖFFNEN …"
+
 #: src/labelwerk/gui/panels/file.py
 msgid "OPEN …"
 msgstr "ÖFFNEN …"
@@ -1592,6 +1701,10 @@ msgstr "Ordner öffnen"
 msgid "Open label"
 msgstr "Etikett öffnen"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Open parcel label"
+msgstr "Paketmarke öffnen"
+
 #: src/labelwerk/gui/symbol_dialog.py
 msgid "Open the folder for your own symbols (created if needed)"
 msgstr "Ordner für eigene Symbole öffnen (wird angelegt)"
@@ -1624,10 +1737,32 @@ msgstr "Ausrichtung"
 msgid "Own parcel label type {name} not readable: {reason}"
 msgstr "Eigener Markentyp {name} nicht lesbar: {reason}"
 
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Own type not saved: {error}"
+msgstr "Eigener Typ nicht gespeichert: {error}"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Own type “{name}” saved"
+msgstr "Eigener Typ „{name}“ gespeichert"
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Own types"
+msgstr "Eigene Typen"
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Own types only"
+msgstr "Nur eigene Typen"
+
 #: src/labelwerk/files.py
 msgid "PDF is encrypted"
 msgstr "PDF ist verschlüsselt"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "PDF or image of a parcel label (DHL, Hermes …) – or drop the file here"
+msgstr "PDF oder Bild einer Paketmarke (DHL, Hermes …) – oder die Datei hier ablegen"
+
 #: src/labelwerk/cli.py
 msgid "PDF page (default 1)"
 msgstr "PDF-Seite (Standard 1)"
@@ -1637,6 +1772,7 @@ msgid "PDF, PNG or JPG"
 msgstr "PDF, PNG oder JPG"
 
 #: src/labelwerk/gui/main_window.py
+#: src/labelwerk/gui/panels/parcel.py
 msgid "PRINT"
 msgstr "DRUCKEN"
 
@@ -1653,6 +1789,10 @@ msgstr "Innenabstand"
 msgid "Padding of the border must be between {low} and {high} mm"
 msgstr "Innenabstand des Rahmens muss zwischen {low} und {high} mm liegen"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Page "
+msgstr "Seite "
+
 #: src/labelwerk/files.py
 msgid "Page must be at least 1."
 msgstr "Seite muss mindestens 1 sein."
@@ -1671,6 +1811,14 @@ msgstr "Seite {page} von {count}"
 msgid "Paper"
 msgstr "Papier"
 
+#: src/labelwerk/gui/tools.py
+msgid "Parcel"
+msgstr "Paket"
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Parcel label"
+msgstr "Paketmarke"
+
 #: src/labelwerk/parcel.py
 #, python-brace-format
 msgid "Parcel label file too large: {name}"
@@ -1704,11 +1852,19 @@ msgstr "Markentyp nicht erkannt – mit --type angeben (siehe „labelwerk parce
 msgid "Parcel label type not unique – choose one with --type: {ids}"
 msgstr "Markentyp nicht eindeutig – mit --type wählen: {ids}"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Parcel label: view only – to edit, use OPEN IN EDITOR or choose another tab."
+msgstr "Paketmarke: nur Ansicht – zum Bearbeiten IM EDITOR ÖFFNEN oder einen anderen Reiter wählen."
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Parcel label: {name} ({id})"
 msgstr "Paketmarke: {name} ({id})"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Parcel labels (*.pdf *.png *.jpg *.jpeg *.gif);;All files (*)"
+msgstr "Paketmarken (*.pdf *.png *.jpg *.jpeg *.gif);;Alle Dateien (*)"
+
 #: src/labelwerk/shortcuts.py
 msgid "Paste"
 msgstr "Einfügen"
@@ -1747,6 +1903,10 @@ msgstr "Vorschau kann nicht gespeichert werden: {path} ({error})"
 msgid "Preview: {path} ({width} × {height} mm)"
 msgstr "Vorschau: {path} ({width} × {height} mm)"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Previous label on the canvas"
+msgstr "Vorheriges Etikett auf der Arbeitsfläche"
+
 #: src/labelwerk/gui/panels/series.py
 msgid "Previous row on the canvas"
 msgstr "Vorige Zeile auf der Arbeitsfläche"
@@ -1756,6 +1916,10 @@ msgstr "Vorige Zeile auf der Arbeitsfläche"
 msgid "Print"
 msgstr "Drucken"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Print all labels of the parcel label in one job"
+msgstr "Alle Etiketten der Paketmarke in einem Auftrag drucken"
+
 #: src/labelwerk/gui/main_window.py
 msgid "Print series"
 msgstr "Serie drucken"
@@ -1883,6 +2047,10 @@ msgstr "ROT"
 msgid "REMOVE"
 msgstr "ENTFERNEN"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "RENAME …"
+msgstr "UMBENENNEN …"
+
 #: src/labelwerk/gui/panels/file.py
 msgid "Recently opened"
 msgstr "Zuletzt geöffnet"
@@ -1891,6 +2059,10 @@ msgstr "Zuletzt geöffnet"
 msgid "Recently used"
 msgstr "Zuletzt verwendet"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Recognise by"
+msgstr "Erkennen an"
+
 #: src/labelwerk/gui/panels/layout.py
 msgid "Red only on the 62 mm red/black label (DK-22251) with a QL-8xx"
 msgstr "Rot nur auf dem Etikett 62 mm Rot/Schwarz (DK-22251) mit einem QL-8xx"
@@ -1912,7 +2084,12 @@ msgstr "Serie aus dem Etikett nehmen (Platzhalter bleiben stehen)"
 msgid "Removed: {path}"
 msgstr "Entfernt: {path}"
 
+#: src/labelwerk/gui/main_window.py
+msgid "Rename own type"
+msgstr "Eigenen Typ umbenennen"
+
 #: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/panels/parcel.py
 msgid "Rename …"
 msgstr "Umbenennen …"
 
@@ -1936,6 +2113,11 @@ msgstr "Größe ändern"
 msgid "Resolution of Zebra printers on USB, in case labelwerk does not detect it correctly (otherwise 203 dpi)"
 msgstr "Auflösung der Zebra-Drucker am USB, falls labelwerk sie nicht richtig erkennt (sonst 203 dpi)"
 
+#: src/labelwerk/gui/panels/parcel.py
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Result"
+msgstr "Ergebnis"
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Roll: none loaded"
 msgstr "Rolle: keine eingelegt"
@@ -1978,6 +2160,10 @@ msgstr "90° nach rechts drehen"
 msgid "Rotate if the image only fits 1:1 when rotated"
 msgstr "Drehen, wenn das Bild nur gedreht 1:1 passt"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Rotation"
+msgstr "Drehung"
+
 #: src/labelwerk/files.py
 #, python-brace-format
 msgid "Rotation {rotate!r} not possible – allowed: auto, 0, 90, 180, 270"
@@ -2221,6 +2407,15 @@ msgstr "Einstellungen nicht lesbar ({path}): {error} – Standardwerte aktiv."
 msgid "Settings saved – they apply to new labels."
 msgstr "Einstellungen gespeichert – gelten für neue Etiketten."
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "Several types fit equally well ({types}) – choose one in the list."
+msgstr "Mehrere Arten passen gleich gut ({types}) – bitte in der Liste wählen."
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Several types fit equally well – please check the choice."
+msgstr "Mehrere Typen passen gleich gut – bitte Auswahl prüfen."
+
 #: src/labelwerk/gui/panels/series.py
 msgid "Sheet of the Excel file"
 msgstr "Blatt der Excel-Datei"
@@ -2407,6 +2602,10 @@ msgstr "Text passt nicht auf Etikett {label_id!r} – auch nicht in der kleinste
 msgid "Text editing"
 msgstr "Schreibmodus"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Text that is on every such label – labelwerk then recognises the type when opening (several words: separate with commas)"
+msgstr "Text, der auf jeder solchen Marke steht – labelwerk erkennt den Typ dann beim Öffnen (mehrere Wörter mit Komma trennen)"
+
 #: src/labelwerk/layout.py
 msgid "Text with automatic font size needs the effective base size (base_pt) for scaling."
 msgstr "Text mit automatischer Schriftgröße braucht die wirksame Grundgröße (base_pt) zum Skalieren."
@@ -2505,6 +2704,10 @@ msgstr "Werkzeuge"
 msgid "Type"
 msgstr "Art"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Type not recognised – choose it in the list."
+msgstr "Typ nicht erkannt – in der Liste wählen."
+
 #: src/labelwerk/gui/panels/barcode.py
 msgid "Type of barcode – for the selected one or the next one"
 msgstr "Art des Barcodes – für den gewählten bzw. den nächsten"
@@ -2787,6 +2990,10 @@ msgstr "auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700,
 msgid "auto (default: rotate only if needed) or degrees clockwise"
 msgstr "auto (Standard: nur drehen wenn nötig) oder Grad im Uhrzeigersinn"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "barcode"
+msgstr "Barcode"
+
 #: src/labelwerk/cli.py
 msgid "bold (default) or --no-bold"
 msgstr "fett (Standard) bzw. --no-bold"
@@ -2815,6 +3022,10 @@ msgstr "Standard: aus dem Drucker (tcp:// → network)"
 msgid "do not cut (Brother; for CUPS/Zebra the driver or the mode in the GUI settings decides)"
 msgstr "nicht schneiden (Brother; bei CUPS/Zebra stellt das der Treiber bzw. der Modus in den Einstellungen der GUI ein)"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "e.g. Returns of my shop"
+msgstr "z. B. Retouren meines Shops"
+
 #: src/labelwerk/files.py
 msgid "file is damaged or incomplete"
 msgstr "Datei ist beschädigt oder unvollständig"
@@ -2972,6 +3183,10 @@ msgstr "keine gültige PDF-Datei"
 msgid "only save a preview, do not print"
 msgstr "nur Vorschau speichern, nicht drucken"
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "optional, e.g. a company name on the label"
+msgstr "freiwillig, z. B. ein Firmenname auf der Marke"
+
 #: src/labelwerk/cli.py
 msgid "own"
 msgstr "eigener"
@@ -3049,6 +3264,10 @@ msgstr "ungeprüft"
 msgid "untested – feedback welcome"
 msgstr "ungeprüft – Rückmeldung erwünscht"
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "unverified"
+msgstr "ungeprüft"
+
 #: src/labelwerk/cli.py
 msgid "vertical: portrait (reading direction across the tape), horizontal: landscape (along the tape); default from the settings"
 msgstr "vertical: Hochformat (Leserichtung quer zum Band), horizontal: Querformat (längs zum Band); Standard aus den Einstellungen"
@@ -3088,6 +3307,11 @@ msgid_plural "{count} rows"
 msgstr[0] "{count} Zeile"
 msgstr[1] "{count} Zeilen"
 
+#: src/labelwerk/gui/parcel_editor.py
+#, python-brace-format
+msgid "{degrees}° clockwise"
+msgstr "{degrees}° im Uhrzeigersinn"
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
@@ -3159,6 +3383,11 @@ msgstr "{name} wurde nicht gespeichert: ungültige Zahlen im Etikett"
 msgid "{name} · Network"
 msgstr "{name} · Netzwerk"
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "{name} · {unverified}"
+msgstr "{name} · {unverified}"
+
 #: src/labelwerk/gui/main_window.py
 #, python-brace-format
 msgid "{name} – untested"
@@ -3279,6 +3508,11 @@ msgstr ""
 "{not_found}\n"
 "Manuell angeben mit -p file:///dev/usb/lpN"
 
+#: src/labelwerk/gui/parcel_editor.py
+#, python-brace-format
+msgid "{number}: {w} × {h} mm"
+msgstr "{number}: {w} × {h} mm"
+
 #: src/labelwerk/zpl.py
 #, python-brace-format
 msgid "{path} is not a printer device"
@@ -3476,6 +3710,11 @@ msgctxt "argparse"
 msgid "usage: "
 msgstr "Aufruf: "
 
+#: src/labelwerk/gui/panels/parcel.py
+msgctxt "parcel"
+msgid "Type"
+msgstr "Markentyp"
+
 #. Translators: column without a name in the table header: "Column 3"
 #: src/labelwerk/series.py
 msgctxt "series"
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index df7fbbc..39dfddd 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -61,6 +61,10 @@ msgstr ""
 msgid "Action"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Actions"
+msgstr ""
+
 #: src/labelwerk/shortcuts.py
 msgid "Actual size (100%)"
 msgstr ""
@@ -167,6 +171,14 @@ msgstr ""
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Areas"
+msgstr ""
+
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Areas overlap – their content then appears twice on the label."
+msgstr ""
+
 #: src/labelwerk/zpl.py
 msgid "As set on the printer"
 msgstr ""
@@ -215,6 +227,10 @@ msgstr ""
 msgid "Barcode without content"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Barcode – do not shrink"
+msgstr ""
+
 #: src/labelwerk/gui/tools.py
 msgid "Barcodes and QR codes"
 msgstr ""
@@ -403,6 +419,14 @@ msgstr ""
 msgid "Choose printer"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Choose the parcel label type first."
+msgstr ""
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Choose the type in the list."
+msgstr ""
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Chosen printer {printer} not found – switch it on or specify it with -p."
@@ -488,6 +512,10 @@ msgstr ""
 msgid "Conversion of new images (symbols stay line art)"
 msgstr ""
 
+#: src/labelwerk/gui/tools.py
+msgid "Convert a parcel label (DHL, Hermes …) for the label printer"
+msgstr ""
+
 #: src/labelwerk/shortcuts.py
 msgid "Copy"
 msgstr ""
@@ -500,6 +528,10 @@ msgstr ""
 msgid "Count"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Country"
+msgstr ""
+
 #: src/labelwerk/printer.py
 msgid "Cover opened while printing."
 msgstr ""
@@ -546,6 +578,10 @@ msgstr ""
 msgid "Cutting is set by the printer driver (system printer settings)"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "DELETE"
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Dashed"
 msgstr ""
@@ -559,6 +595,7 @@ msgstr ""
 msgid "Default: {keys}"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
 #: src/labelwerk/shortcuts.py
 msgid "Delete"
 msgstr ""
@@ -572,6 +609,15 @@ msgstr ""
 msgid "Delete favorite “{name}”?"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Delete own type"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Delete the own type “{name}”?"
+msgstr ""
+
 #: src/labelwerk/gui/panels/file.py
 msgid "Delete …"
 msgstr ""
@@ -643,10 +689,18 @@ msgstr ""
 msgid "Double-click: as {{column}} into the selected text object or as new text"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Drag on the label to mark an area, drag an area to move it, Del removes the chosen one. Areas are placed on the tape in this order."
+msgstr ""
+
 #: src/labelwerk/gui/canvas.py
 msgid "Drag: set the length · Double-click: automatic"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Draw the areas on the open parcel label and save them as your own type"
+msgstr ""
+
 #: src/labelwerk/gui/image_import.py
 msgid "Dropped image"
 msgstr ""
@@ -659,6 +713,10 @@ msgstr ""
 msgid "Edit"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Edit the shown label like any other label (pieces as images)"
+msgstr ""
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Effective model: {model}"
@@ -677,6 +735,10 @@ msgstr ""
 msgid "End text editing"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Enter a name."
+msgstr ""
+
 #. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
 #: src/labelwerk/storage.py
 #, python-brace-format
@@ -753,6 +815,7 @@ msgid "Favorites folder not created ({reason})"
 msgstr ""
 
 #: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/panels/parcel.py
 #: src/labelwerk/gui/tools.py
 msgid "File"
 msgstr ""
@@ -1134,6 +1197,11 @@ msgstr ""
 msgid "Label too large ({count} objects, at most {limit})"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "Label {current}/{total}"
+msgstr ""
+
 #: src/labelwerk/printer.py
 #, python-brace-format
 msgid "Label {label!r} does not fit the printer ({model})."
@@ -1251,6 +1319,10 @@ msgstr ""
 msgid "Margins"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Mark at least one area."
+msgstr ""
+
 #: src/labelwerk/shortcuts.py
 msgid "Maximize on paper"
 msgstr ""
@@ -1277,6 +1349,10 @@ msgstr ""
 msgid "Module width {module!r} invalid – allowed: 1–{limit} dots"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "More tabs"
+msgstr ""
+
 #: src/labelwerk/shortcuts.py
 msgid "Move down (0.1 mm)"
 msgstr ""
@@ -1317,6 +1393,10 @@ msgstr ""
 msgid "NEW"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "NEW OWN TYPE …"
+msgstr ""
+
 #: src/labelwerk/gui/panels/series.py
 msgid "NONE"
 msgstr ""
@@ -1325,6 +1405,7 @@ msgstr ""
 msgid "NUMBERING"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
 #: src/labelwerk/gui/settings_dialog.py
 msgid "Name"
 msgstr ""
@@ -1333,6 +1414,10 @@ msgstr ""
 msgid "Name of the favorite:"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Name:"
+msgstr ""
+
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
 msgid "Network printer {name}: address “{host}” invalid – only an IP address or name, without “tcp://” and port"
@@ -1352,6 +1437,14 @@ msgstr ""
 msgid "New label"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "New own parcel label type"
+msgstr ""
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Next label on the canvas"
+msgstr ""
+
 #: src/labelwerk/gui/panels/series.py
 msgid "Next row on the canvas"
 msgstr ""
@@ -1397,6 +1490,10 @@ msgstr ""
 msgid "No labels to print"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "No layout for this label – the pieces were arranged anew."
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid ""
 "No network printer configured (GUI settings).\n"
@@ -1410,6 +1507,10 @@ msgid ""
 "{path}"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "No parcel label open – open one or drop the file here."
+msgstr ""
+
 #: src/labelwerk/media.py
 #: src/labelwerk/printer.py
 #: src/labelwerk/zpl.py
@@ -1509,6 +1610,14 @@ msgstr ""
 msgid "OPEN FOLDER"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "OPEN IN EDITOR"
+msgstr ""
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "OPEN PARCEL LABEL …"
+msgstr ""
+
 #: src/labelwerk/gui/panels/file.py
 msgid "OPEN …"
 msgstr ""
@@ -1575,6 +1684,10 @@ msgstr ""
 msgid "Open label"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Open parcel label"
+msgstr ""
+
 #: src/labelwerk/gui/symbol_dialog.py
 msgid "Open the folder for your own symbols (created if needed)"
 msgstr ""
@@ -1607,10 +1720,32 @@ msgstr ""
 msgid "Own parcel label type {name} not readable: {reason}"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Own type not saved: {error}"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Own type “{name}” saved"
+msgstr ""
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Own types"
+msgstr ""
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Own types only"
+msgstr ""
+
 #: src/labelwerk/files.py
 msgid "PDF is encrypted"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "PDF or image of a parcel label (DHL, Hermes …) – or drop the file here"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "PDF page (default 1)"
 msgstr ""
@@ -1620,6 +1755,7 @@ msgid "PDF, PNG or JPG"
 msgstr ""
 
 #: src/labelwerk/gui/main_window.py
+#: src/labelwerk/gui/panels/parcel.py
 msgid "PRINT"
 msgstr ""
 
@@ -1636,6 +1772,10 @@ msgstr ""
 msgid "Padding of the border must be between {low} and {high} mm"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Page "
+msgstr ""
+
 #: src/labelwerk/files.py
 msgid "Page must be at least 1."
 msgstr ""
@@ -1654,6 +1794,14 @@ msgstr ""
 msgid "Paper"
 msgstr ""
 
+#: src/labelwerk/gui/tools.py
+msgid "Parcel"
+msgstr ""
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Parcel label"
+msgstr ""
+
 #: src/labelwerk/parcel.py
 #, python-brace-format
 msgid "Parcel label file too large: {name}"
@@ -1687,11 +1835,19 @@ msgstr ""
 msgid "Parcel label type not unique – choose one with --type: {ids}"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Parcel label: view only – to edit, use OPEN IN EDITOR or choose another tab."
+msgstr ""
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Parcel label: {name} ({id})"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Parcel labels (*.pdf *.png *.jpg *.jpeg *.gif);;All files (*)"
+msgstr ""
+
 #: src/labelwerk/shortcuts.py
 msgid "Paste"
 msgstr ""
@@ -1730,6 +1886,10 @@ msgstr ""
 msgid "Preview: {path} ({width} × {height} mm)"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Previous label on the canvas"
+msgstr ""
+
 #: src/labelwerk/gui/panels/series.py
 msgid "Previous row on the canvas"
 msgstr ""
@@ -1739,6 +1899,10 @@ msgstr ""
 msgid "Print"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Print all labels of the parcel label in one job"
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "Print series"
 msgstr ""
@@ -1862,6 +2026,10 @@ msgstr ""
 msgid "REMOVE"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "RENAME …"
+msgstr ""
+
 #: src/labelwerk/gui/panels/file.py
 msgid "Recently opened"
 msgstr ""
@@ -1870,6 +2038,10 @@ msgstr ""
 msgid "Recently used"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Recognise by"
+msgstr ""
+
 #: src/labelwerk/gui/panels/layout.py
 msgid "Red only on the 62 mm red/black label (DK-22251) with a QL-8xx"
 msgstr ""
@@ -1891,7 +2063,12 @@ msgstr ""
 msgid "Removed: {path}"
 msgstr ""
 
+#: src/labelwerk/gui/main_window.py
+msgid "Rename own type"
+msgstr ""
+
 #: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/panels/parcel.py
 msgid "Rename …"
 msgstr ""
 
@@ -1915,6 +2092,11 @@ msgstr ""
 msgid "Resolution of Zebra printers on USB, in case labelwerk does not detect it correctly (otherwise 203 dpi)"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Result"
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Roll: none loaded"
 msgstr ""
@@ -1957,6 +2139,10 @@ msgstr ""
 msgid "Rotate if the image only fits 1:1 when rotated"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Rotation"
+msgstr ""
+
 #: src/labelwerk/files.py
 #, python-brace-format
 msgid "Rotation {rotate!r} not possible – allowed: auto, 0, 90, 180, 270"
@@ -2200,6 +2386,15 @@ msgstr ""
 msgid "Settings saved – they apply to new labels."
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "Several types fit equally well ({types}) – choose one in the list."
+msgstr ""
+
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Several types fit equally well – please check the choice."
+msgstr ""
+
 #: src/labelwerk/gui/panels/series.py
 msgid "Sheet of the Excel file"
 msgstr ""
@@ -2386,6 +2581,10 @@ msgstr ""
 msgid "Text editing"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "Text that is on every such label – labelwerk then recognises the type when opening (several words: separate with commas)"
+msgstr ""
+
 #: src/labelwerk/layout.py
 msgid "Text with automatic font size needs the effective base size (base_pt) for scaling."
 msgstr ""
@@ -2484,6 +2683,10 @@ msgstr ""
 msgid "Type"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "Type not recognised – choose it in the list."
+msgstr ""
+
 #: src/labelwerk/gui/panels/barcode.py
 msgid "Type of barcode – for the selected one or the next one"
 msgstr ""
@@ -2766,6 +2969,10 @@ msgstr ""
 msgid "auto (default: rotate only if needed) or degrees clockwise"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "barcode"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "bold (default) or --no-bold"
 msgstr ""
@@ -2794,6 +3001,10 @@ msgstr ""
 msgid "do not cut (Brother; for CUPS/Zebra the driver or the mode in the GUI settings decides)"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "e.g. Returns of my shop"
+msgstr ""
+
 #: src/labelwerk/files.py
 msgid "file is damaged or incomplete"
 msgstr ""
@@ -2951,6 +3162,10 @@ msgstr ""
 msgid "only save a preview, do not print"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+msgid "optional, e.g. a company name on the label"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "own"
 msgstr ""
@@ -3028,6 +3243,10 @@ msgstr ""
 msgid "untested – feedback welcome"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgid "unverified"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "vertical: portrait (reading direction across the tape), horizontal: landscape (along the tape); default from the settings"
 msgstr ""
@@ -3067,6 +3286,11 @@ msgid_plural "{count} rows"
 msgstr[0] ""
 msgstr[1] ""
 
+#: src/labelwerk/gui/parcel_editor.py
+#, python-brace-format
+msgid "{degrees}° clockwise"
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
@@ -3138,6 +3362,11 @@ msgstr ""
 msgid "{name} · Network"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "{name} · {unverified}"
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 #, python-brace-format
 msgid "{name} – untested"
@@ -3256,6 +3485,11 @@ msgid ""
 "Specify manually with -p file:///dev/usb/lpN"
 msgstr ""
 
+#: src/labelwerk/gui/parcel_editor.py
+#, python-brace-format
+msgid "{number}: {w} × {h} mm"
+msgstr ""
+
 #: src/labelwerk/zpl.py
 #, python-brace-format
 msgid "{path} is not a printer device"
@@ -3452,6 +3686,11 @@ msgctxt "argparse"
 msgid "usage: "
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+msgctxt "parcel"
+msgid "Type"
+msgstr ""
+
 #. Translators: column without a name in the table header: "Column 3"
 #: src/labelwerk/series.py
 msgctxt "series"
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 3653915..05f9a36 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -25,7 +25,7 @@ from .storage import RECENT_FILES
 THEMES = ("rawblock", "classic")
 RESTART_KEYS = ("language", "start_zoom", "start_tool", "system_file_dialog")   # erst nach Neustart (Hinweis)
 # Reiter beim Start: „last“ = zuletzt benutzter, sonst Schlüssel der Werkzeuge (gui/tools.py TOOLS)
-START_TOOLS = ("last", "file", "paper", "text", "image", "barcode", "layout", "series")
+START_TOOLS = ("last", "file", "paper", "text", "image", "barcode", "layout", "series", "parcel")
 # Reiter, die sich ausblenden lassen (DATEI und PAPIER bleiben immer – dort wird das Etikett gewählt)
 HIDEABLE_TOOLS = tuple(key for key in START_TOOLS[1:] if key not in ("file", "paper"))
 SYMBOL_LISTS = ("symbols_recent", "symbols_favorites")
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2938 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-19-paketmarken-design.md src/labelwerk/gui/canvas.py src/labelwerk/gui/file_session.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/parcel.py src/labelwerk/gui/parcel_editor.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/gui/tools.py src/labelwerk/parcel.py src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/settings.py tests/gui/test_gui_hidden_tools.py tests/gui/test_gui_image.py tests/gui/test_gui_parcel.py tests/gui/test_gui_series.py tests/gui/test_gui_settings.py tests/test_parcel.py
git commit -m "Paketmarken – Reiter PAKET: Marke öffnen, Typ erkennen/wählen, Vorschau als Nur-Ansicht, Drucken aller Etiketten in einem Auftrag, im Editor öffnen, eigene Typen im Fenster „Eigener Markentyp“; Aktionsleiste rechts nie im Überlauf

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Paketmarken nach Gesamtreview

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-19-paketmarken-design.md`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/parcel.py`
- Modify: `src/labelwerk/gui/parcel_editor.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/parcel.py`
- Modify: `src/labelwerk/parcel_data/README.md`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `tests/gui/test_gui_parcel.py`
- Modify: `tests/test_parcel.py`

**Interfaces / Produces:** Verschwundene Marke → `ParcelError`, Editor klemmt Bereiche an den Seitenrand, Layout-Aktionen nach PAKET, `fit_toolbars` nach Designwechsel, „»“ hervorgehoben, Hinweise und Doku.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_parcel.py b/tests/gui/test_gui_parcel.py
index 5aa372b..283fbc6 100644
--- a/tests/gui/test_gui_parcel.py
+++ b/tests/gui/test_gui_parcel.py
@@ -569,3 +569,96 @@ def test_editor_preview_waits_while_moving_and_name_does_not_render(qtbot, tmp_p
     assert calls == [] and editor._preview_timer.isActive()
     editor._preview_now()                                       # Loslassen: sofort
     assert calls == [1] and not editor._preview_timer.isActive()
+
+
+# --- Gesamtreview proto-pk-final -------------------------------------------------------------
+def test_deleted_mark_resets_the_result(qtbot, tmp_path, workers):  # noqa: F811
+    win = _window(qtbot)
+    path = _dhl(tmp_path)
+    panel = _open(win, path)
+    assert panel.documents()
+    path.unlink()
+    panel.source._cache.clear()                                 # anderes Etikett: Seite neu lesen
+    item = next(panel.types.item(i) for i in range(panel.types.count())
+                if panel.types.item(i).data(TYPE_ROLE) == "dhl-privat-2")
+    panel.types.setCurrentItem(item)
+    win.render_now()
+    assert panel.documents() == [] and not panel.print_button.isEnabled()
+    assert panel.page_label.text() == "–" and "nicht mehr lesen" in panel.notes.text()
+    assert win.canvas.read_only and win.canvas.objects == []
+    win.print_label()
+    assert workers == []
+
+
+def test_failed_second_load_keeps_the_previous_mark(qtbot, tmp_path):
+    win = _window(qtbot)
+    panel = _open(win, _dhl(tmp_path))
+    bad = tmp_path / "kaputt.pdf"
+    bad.write_bytes(b"kein PDF")
+    assert not panel.load(bad)
+    assert panel.path.name == "dhl.pdf" and panel.documents()
+    assert "vorige Paketmarke bleibt geladen" in panel.notes.text()
+
+
+@pytest.mark.parametrize("size", [(210, 297), (148, 210), (100, 150)])
+def test_editor_area_to_the_page_edge_is_valid(qtbot, tmp_path, size):
+    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=size, rects=[(5, 5, 50, 50)]))
+    editor = ParcelTypeEditor(None, source, "62", "QL-600", set())
+    qtbot.addWidget(editor)
+    editor.add_area((0, 0, size[0] + 1, size[1] + 1))           # bis über den Rand gezogen
+    editor.name.setText("Rand")
+    assert editor.pieces()[0]["src"] == [0, 0, size[0], size[1]]
+    assert editor.problem() is None and editor.result_type()
+
+
+def test_layout_actions_follow_the_selection_after_the_parcel_view(qtbot, tmp_path):
+    win = _window(qtbot)
+    win.canvas.set_selection([0])
+    assert win.shortcut_actions["align.paper_left"].isEnabled()     # vorher: Auswahl da
+    _open(win, _dhl(tmp_path))
+    win._tool_triggered("layout")
+    win.render_now()
+    assert win.canvas.selection() == []
+    assert not win.shortcut_actions["align.paper_left"].isEnabled()   # ohne Auswahl nichts
+
+
+def test_fit_toolbars_after_a_theme_change_keeps_the_window_width(qtbot):
+    win = _window(qtbot)
+    win.resize(900, 700)
+    win.fit_toolbars(resize=False)
+    assert win.width() == 900 and win.app_bar.minimumWidth() > 0
+
+
+def test_toolbars_cannot_be_hidden_by_the_context_menu(qtbot):
+    win = _window(qtbot)
+    menu = win.createPopupMenu()
+    actions = menu.actions() if menu is not None else []
+    assert win.tool_bar.toggleViewAction() not in actions
+    assert win.app_bar.toggleViewAction() not in actions
+
+
+def test_overflow_button_is_highlighted_for_a_hidden_active_tab(qtbot):
+    from PySide6.QtWidgets import QToolButton
+    from labelwerk.gui.app import load_theme
+    app = QApplication.instance()
+    app.setStyleSheet(load_theme())
+    try:
+        win = _window(qtbot)
+        win.fit_toolbars(resize=False)
+        win.resize(760, 700)
+        for _ in range(3):
+            QApplication.processEvents()
+        ext = win.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
+        hidden = [k for k, a in win.tool_actions.items()
+                  if not win.tool_bar.widgetForAction(a).isVisible()]
+        assert ext is not None and ext.isVisible() and hidden
+        win._tool_triggered(hidden[-1])
+        win.tool_actions[hidden[-1]].setChecked(True)
+        win._mark_overflow()
+        assert ext.property("active") is True
+        win._tool_triggered("paper")
+        win.tool_actions["paper"].setChecked(True)
+        win._mark_overflow()
+        assert ext.property("active") is False
+    finally:
+        app.setStyleSheet("")
diff --git a/tests/test_parcel.py b/tests/test_parcel.py
index 8e91223..2619962 100644
--- a/tests/test_parcel.py
+++ b/tests/test_parcel.py
@@ -521,7 +521,7 @@ def test_ambiguous_marks_ties_without_a_tested_winner(tmp_path):
 @pytest.mark.parametrize("src", [[10, 10, 10.5, 50], [10, 10, 50, 10.5], [10, 10, 211, 50],
                                  [10, 10, 50, 298]])
 def test_own_areas_need_size_and_must_lie_on_the_page(src):
-    with pytest.raises(parcel.ParcelError, match="Bereiche"):
+    with pytest.raises(parcel.ParcelError, match="Bereich"):
         parcel.own_from_dict(_own(pieces=[{"page": 1, "src": src, "rotation": 0, "kind": "text"}]))
 
 
@@ -567,3 +567,33 @@ def test_own_id_is_a_free_slug():
     assert parcel.own_id("!!!", set()) == "eigen-typ"
     slug = parcel.own_id("x" * 200, set())
     assert len(slug) <= 64 and parcel.own_from_dict(_own(id=slug)).id == slug
+
+
+# --- Gesamtreview: Marke verschwunden, Bereiche am Rand -------------------------------------
+def test_mark_deleted_after_loading_is_a_friendly_error(tmp_path):
+    path = make_pdf(tmp_path / "weg.pdf", texts=[(20, 20, "DHL Online Frankierung")])
+    source = parcel.load(path)
+    path.unlink()
+    with pytest.raises(parcel.ParcelError, match="nicht mehr lesen"):
+        source.page(1, 100)
+    path.write_bytes(b"kein PDF mehr")                          # durch etwas anderes ersetzt
+    with pytest.raises(parcel.ParcelError, match="nicht mehr lesen"):
+        source.page(1, 100)
+
+
+@pytest.mark.parametrize("size", [(210, 297), (148, 210), (100, 150)])
+def test_own_area_up_to_the_page_edge_is_clamped(size):
+    w, h = size
+    data = _own(source={"sizes_mm": [list(size)]},
+                pieces=[{"page": 1, "src": [0, 0, w + 0.4, h + 0.4], "rotation": 0, "kind": "text"}])
+    assert parcel.own_from_dict(data).pieces[0].src == (0, 0, w, h)
+    data["pieces"][0]["src"] = [0, 0, w + 0.6, h]
+    with pytest.raises(parcel.ParcelError, match="Bereich 1 ragt über die Seite"):
+        parcel.own_from_dict(data)
+
+
+def test_own_area_too_small_names_the_area():
+    pieces = [{"page": 1, "src": [10, 10, 60, 60], "rotation": 0, "kind": "text"},
+              {"page": 1, "src": [10, 10, 10.5, 60], "rotation": 0, "kind": "text"}]
+    with pytest.raises(parcel.ParcelError, match="Bereich 2 ist zu klein"):
+        parcel.own_from_dict(_own(pieces=pieces))
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (Fälle in tests/gui/test_gui_parcel.py, tests/test_parcel.py) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index a9f5d5e..3266f33 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -84,8 +84,10 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   (Bearbeiten gesperrt mit Hinweis, ohne Umwandlung leer, DRUCKEN druckt dann nicht); IM EDITOR ÖFFNEN gilt als
   geändert; eigener Typ: SPEICHERN nur gültig, Bereiche auf der Seite, Überlappung gemeldet, Vorschau entprellt.
 - Werkzeugleiste: EINSTELLUNGEN/DRUCKEN in eigener Leiste rechts (appBar, nie im Überlauf – nur Reiterknöpfe laufen
-  über); Fenster beim Start so breit, dass alles passt (fit_toolbars nach dem Design, höchstens Bildschirmbreite).
-- 2938 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+  über, „»“ hervorgehoben, solange der aktive Reiter dort liegt – _mark_overflow; Leisten nicht über das Kontextmenü
+  ausblendbar); Fenster beim Start so breit, dass alles passt (fit_toolbars nach dem Design und nach jedem
+  Designwechsel ohne Größenänderung, höchstens Bildschirmbreite).
+- 2952 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
diff --git a/README.md b/README.md
index 10b762f..f1ae1b8 100644
--- a/README.md
+++ b/README.md
@@ -130,12 +130,15 @@ Auf 62 mm endlos ergibt das ein 15–28 cm langes Etikett, auf breiteren Bänder
 `src/labelwerk/parcel_data/README.md`. Vor dem Versand prüfen, ob die Barcodes lesbar sind.
 
 In der Oberfläche: Reiter **PAKET** → MARKE ÖFFNEN … (oder die Datei aufs Panel bzw. die Arbeitsfläche ziehen). Der
-erkannte Typ ist mit ✓ gewählt, die Arbeitsfläche zeigt das Ergebnis für das Etikett aus dem Reiter PAPIER (nur
-Ansicht, ◀ ▶ bei mehreren Etiketten). DRUCKEN druckt alle Etiketten in einem Auftrag, IM EDITOR ÖFFNEN macht daraus
-ein normales Etikett (die Stücke sind Bilder). EIGENER TYP … öffnet die Marke groß: Bereiche mit der Maus aufziehen,
-je Bereich Drehung und „Barcode – nicht verkleinern“ wählen, Namen und optional einen Text zum Erkennen eintragen –
-labelwerk ordnet die Stücke selbst auf dem Band an. Eigene Typen lassen sich in der Liste umbenennen und löschen
-(rechte Maustaste).
+erkannte Typ ist gewählt, ✓ steht an den Typen, die am besten passen. Passen mehrere gleich gut und ist keiner davon
+geprüft, oder wird die Marke nicht erkannt, ist nichts gewählt – ein Hinweis nennt die Kandidaten, die Wahl in der
+Liste entscheidet. Die Arbeitsfläche zeigt das Ergebnis für das Etikett aus dem Reiter PAPIER (nur Ansicht – Bearbeiten
+ist gesperrt, ◀ ▶ bei mehreren Etiketten; ohne gewählten Typ bleibt sie leer und DRUCKEN druckt nichts). DRUCKEN
+druckt alle Etiketten in einem Auftrag, IM EDITOR ÖFFNEN macht daraus ein normales Etikett (die Stücke sind Bilder).
+EIGENER TYP … öffnet die Marke groß: Bereiche mit der Maus aufziehen, je Bereich Drehung und „Barcode – nicht
+verkleinern“ wählen, Namen und optional einen Text zum Erkennen eintragen – labelwerk ordnet die Stücke selbst auf
+dem Band an. Ist ein eigener Typ gewählt, stehen unter der Liste UMBENENNEN … und LÖSCHEN (auch über die rechte
+Maustaste).
 
 ## Architektur
 
diff --git a/docs/superpowers/specs/2026-10-19-paketmarken-design.md b/docs/superpowers/specs/2026-10-19-paketmarken-design.md
index 3ed7ec9..1d9ab1e 100644
--- a/docs/superpowers/specs/2026-10-19-paketmarken-design.md
+++ b/docs/superpowers/specs/2026-10-19-paketmarken-design.md
@@ -96,8 +96,10 @@ Beispiele), Briefmarken/Internetmarke (geht schon über `print-file`), Texterken
 
 ## 3 – Oberfläche: Reiter PAKET (Panel-Überschrift „Paketmarke“)
 
-Der Reiter heißt kurz „PAKET“ (Tooltip „Paketmarke …“), damit die Werkzeugleiste auf Deutsch nicht überläuft;
-EINSTELLUNGEN und DRUCKEN stehen in einer eigenen Leiste rechts und laufen nie über (nur Reiterknöpfe dürfen es).
+Der Reiter heißt kurz „PAKET“ (Tooltip „Paketmarke …“), damit möglichst alle Reiter in die Leiste passen.
+EINSTELLUNGEN und DRUCKEN stehen in einer eigenen Leiste rechts und laufen nie über; reicht der Platz nicht, liegen
+die letzten Reiterknöpfe hinter „»“ – hervorgehoben, solange der aktive Reiter dort liegt. Die Leisten lassen
+sich nicht über das Kontextmenü ausblenden.
 
 - **Werkzeug** `parcel` in `gui/tools.py` (auch `START_TOOLS`/`HIDEABLE_TOOLS`); Panel `panels/parcel.py`:
   Land (Auswahl, Standard aus der Region, nur Länder mit Typen + „Nur eigene Typen“), MARKE ÖFFNEN … (Dateidialog mit
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index adca5e6..af90dfe 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -210,7 +210,7 @@ class MainWindow(QMainWindow):
         self.app_bar.addAction(self.print_action)
         self.app_bar.widgetForAction(self.print_action).setObjectName("print")
         self.tool_bar = toolbar
-        QTimer.singleShot(0, self.fit_toolbars)     # erst mit dem Design (apply_theme) messen
+        QTimer.singleShot(0, self, self.fit_toolbars)     # erst mit dem Design (apply_theme) messen
 
         # Arbeitsfläche
         self.canvas = Canvas(self.model)
@@ -345,10 +345,10 @@ class MainWindow(QMainWindow):
     def panel(self, key: str):
         return self._panel_by_key[key]
 
-    def fit_toolbars(self) -> None:
+    def fit_toolbars(self, resize: bool = True) -> None:
         """Mit dem Design gemessen: die Leiste EINSTELLUNGEN/DRUCKEN nie schmaler als ihre Knöpfe
-        (die Reiterknöpfe laufen bei Platzmangel über), das Fenster beim Start so breit, dass
-        alles passt – höchstens so breit wie der Bildschirm."""
+        (die Reiterknöpfe laufen bei Platzmangel über); ``resize`` (Start): das Fenster so breit,
+        dass alles passt – höchstens so breit wie der Bildschirm."""
         ext = self.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
         if ext is not None:                         # Überlauf-Knopf sichtbar beschriften
             ext.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
@@ -357,6 +357,9 @@ class MainWindow(QMainWindow):
         buttons = sum(self.app_bar.widgetForAction(a).sizeHint().width()
                       for a in (self.settings_action, self.print_action))
         self.app_bar.setMinimumWidth(buttons + 24)
+        self._mark_overflow()
+        if not resize:
+            return
         screen = self.screen().availableGeometry().width() if self.screen() else 0
         wanted = self.tool_bar.sizeHint().width() + buttons + 48
         if screen:
@@ -501,6 +504,34 @@ class MainWindow(QMainWindow):
         gebraucht wird (Serie im Etikett, Schnitt-Optionen des Druckers)."""
         for key, action in self.tool_actions.items():
             action.setVisible(self._tool_visible(key))
+        QTimer.singleShot(0, self, self._mark_overflow)    # nach dem Neuordnen der Leiste
+
+    def _mark_overflow(self) -> None:
+        """Liegt der aktive Reiter im Überlauf der Leiste, ist der Knopf „»“ hervorgehoben."""
+        ext = self.tool_bar.findChild(QToolButton, "qt_toolbar_ext_button")
+        if ext is None:
+            return
+        hidden = any(action.isChecked() and action.isVisible()
+                     and not self.tool_bar.widgetForAction(action).isVisible()
+                     for action in self.tool_actions.values())
+        if ext.property("active") != hidden:
+            ext.setProperty("active", hidden)
+            ext.style().unpolish(ext)
+            ext.style().polish(ext)
+
+    def resizeEvent(self, event) -> None:
+        super().resizeEvent(event)
+        QTimer.singleShot(0, self, self._mark_overflow)    # Überlauf ändert sich mit der Breite
+
+    def createPopupMenu(self):
+        """Kein Kontextmenü zum Ausblenden der Leisten (Aktionen/Werkzeuge gehören immer dazu)."""
+        menu = super().createPopupMenu()
+        if menu is not None:
+            for bar in (self.tool_bar, self.app_bar):
+                menu.removeAction(bar.toggleViewAction())
+            if menu.isEmpty():
+                return None
+        return menu
 
     def _tool_needed(self, key: str) -> bool:
         """Knopf gehört in die Leiste: nicht ausgeblendet – oder SERIE wird gebraucht (Serie im
@@ -665,9 +696,11 @@ class MainWindow(QMainWindow):
                     action.setEnabled(False)
                     self._parcel_disabled.add(entry.id)
             return
-        for key in self._parcel_disabled:           # wieder wie vorher, Rest regelt das Folgende
-            self.shortcut_actions[key].setEnabled(True)
-        self._parcel_disabled.clear()
+        if self._parcel_disabled:                   # wieder wie vorher, Rest regelt das Folgende
+            for key in self._parcel_disabled:
+                self.shortcut_actions[key].setEnabled(True)
+            self._parcel_disabled.clear()
+            self.panel("layout").set_selection(self.canvas.selection())   # Ausrichten nach Auswahl
         if self.edit_session.update_actions(self.shortcut_actions):   # wirken auf den Editor
             return
         self.shortcut_actions["text.end_edit"].setEnabled(False)
@@ -2027,6 +2060,7 @@ class MainWindow(QMainWindow):
             from .app import apply_theme
             apply_theme(QApplication.instance(), self.settings.theme)
             self.apply_theme_icons()
+            QTimer.singleShot(0, self, lambda: self.fit_toolbars(resize=False))   # neues Design messen
             self.apply_font_list()
             self.apply_hidden_tools(fall_back=hidden_changed)
             apply_shortcuts(self.shortcut_actions,
diff --git a/src/labelwerk/gui/panels/parcel.py b/src/labelwerk/gui/panels/parcel.py
index a7fdb96..e93e60e 100644
--- a/src/labelwerk/gui/panels/parcel.py
+++ b/src/labelwerk/gui/panels/parcel.py
@@ -182,7 +182,10 @@ class ParcelPanel(Panel):
         try:
             source = parcel.load(path)
         except parcel.ParcelError as e:
-            self._show_error(str(e))
+            message = str(e)
+            if self.source is not None:            # die vorige Marke bleibt
+                message = _("{error} – the previous parcel label stays loaded.").format(error=e)
+            self._show_error(message)
             return False
         self.source, self.path = source, Path(path)
         self._detect(keep=False)
@@ -358,7 +361,7 @@ class ParcelPanel(Panel):
                 notes.insert(0, _("Several types fit equally well ({types}) – choose one in the "
                                   "list.").format(types=names))
             elif not self._scores:
-                notes.insert(0, _("Type not recognised – choose it in the list."))
+                notes.insert(0, _("Type not recognized – choose it in the list."))
             else:
                 notes.insert(0, _("Choose the type in the list."))
         notes += parcel.own_warnings()          # beschädigte eigene Typen
diff --git a/src/labelwerk/gui/parcel_editor.py b/src/labelwerk/gui/parcel_editor.py
index 3f30212..10689da 100644
--- a/src/labelwerk/gui/parcel_editor.py
+++ b/src/labelwerk/gui/parcel_editor.py
@@ -25,6 +25,7 @@ PREVIEW_W = 420                     # Breite der Ergebnis-Vorschau in Pixeln
 PREVIEW_H = 220
 PREVIEW_DELAY_MS = 250              # Vorschau erst, wenn das Ziehen kurz ruht (beim Loslassen sofort)
 NAME_MAX = 200
+SNAP_MM = 0.5                       # so nah am Seitenrand zählt als Rand
 ROTATIONS = (0, 90, 180, 270)
 
 
@@ -150,7 +151,7 @@ class ParcelTypeEditor(QDialog):
         self.name.setPlaceholderText(_("e.g. Returns of my shop"))
         self.words = QLineEdit()
         self.words.setPlaceholderText(_("optional, e.g. a company name on the label"))
-        self.words.setToolTip(_("Text that is on every such label – labelwerk then recognises "
+        self.words.setToolTip(_("Text that is on every such label – labelwerk then recognizes "
                                 "the type when opening (several words: separate with commas)"))
         self.list = QListWidget()
         self.list.currentRowChanged.connect(self._row_chosen)
@@ -287,8 +288,16 @@ class ParcelTypeEditor(QDialog):
         self.list.blockSignals(False)
 
     def _mm(self, area: _Area) -> tuple[float, float, float, float]:
+        """Bereich in mm auf seiner Seite – auf die Seitengröße begrenzt (Rundung am Rand)."""
         r = area.scene_rect()
-        return tuple(round(v / self._k, 1) for v in (r.left(), r.top(), r.right(), r.bottom()))
+        page = next((p for p, areas in self._areas.items() if area in areas), self._page)
+        w, h = (round(v, 1) for v in self.source.sizes_mm[page - 1])
+
+        def edge(value: float, size: float) -> float:   # Pixel-Rundung am Seitenrand: genau der Rand
+            value = min(max(value, 0.0), size)
+            return 0.0 if value < SNAP_MM else size if value > size - SNAP_MM else value
+        x0, y0, x1, y1 = (round(v / self._k, 1) for v in (r.left(), r.top(), r.right(), r.bottom()))
+        return edge(x0, w), edge(y0, h), edge(x1, w), edge(y1, h)
 
     def _current_area(self) -> _Area | None:
         areas = self._areas.get(self._page, [])
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index aad307b..506e7dd 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -36,6 +36,7 @@ QToolBar#editBar::separator { background: #000000; width: 3px; margin: 2px 8px 5
 QToolBar QToolButton#print { background: #000000; color: #FFFFFF; }
 /* Überlauf der Reiterknöpfe: schmaler Knopf „»“ (Qt gibt ihm eine feste kleine Breite) */
 QToolBar QToolButton#qt_toolbar_ext_button { border: none; padding: 0; margin: 0; letter-spacing: 0; }
+QToolBar QToolButton#qt_toolbar_ext_button[active="true"] { background: #000000; color: #FFFFFF; }
 QToolBar QToolButton#print:hover { background: #FFFFFF; color: #000000; }
 QToolBar QToolButton:disabled, QToolBar QToolButton#print:disabled {
     background: #F0F0F0;
diff --git a/src/labelwerk/parcel.py b/src/labelwerk/parcel.py
index e177d47..a8915b1 100644
--- a/src/labelwerk/parcel.py
+++ b/src/labelwerk/parcel.py
@@ -28,7 +28,7 @@ from PIL import Image
 from . import i18n
 from .document import Document, ImageObject
 from .files import PDFIUM_LOCK, _checked, _readable, load_image
-from .i18n import N_, _
+from .i18n import N_, _, number as number_text
 from .labels import get_label, length_limits
 
 CATALOG = Path(__file__).with_name("parcel_data") / "catalog.json"
@@ -40,6 +40,7 @@ MAX_FILE_BYTES = 32 * 1024 * 1024
 MAX_PAGES = 20
 MAX_DPI = 600
 MIN_PIECE_MM = 1.0                 # eigene Bereiche: Kanten mindestens so lang
+EDGE_TOLERANCE_MM = 0.5            # eigene Bereiche dürfen so weit über den Seitenrand (Rundung)
 SNAP_MM = 3.0                      # Kante höchstens so weit nach außen bis zum weißen Rand
 SIZE_TOLERANCE_MM = 4.0
 WIDE_MM = 95.0                     # ab dieser bedruckbaren Breite gilt ein 100×150-Layout
@@ -250,15 +251,21 @@ def own_from_dict(data) -> ParcelType:
         raise bad(N_("areas"))
     width, height = max(s[0] for s in sizes), max(s[1] for s in sizes)
     pieces = []
-    for p in raw:
+    for number, p in enumerate(raw, start=1):
         if not isinstance(p, dict) or p.get("rotation") not in (0, 90, 180, 270) \
                 or p.get("kind", "text") not in KINDS or not isinstance(p.get("page", 1), int) \
                 or isinstance(p.get("page", 1), bool) or not 1 <= p.get("page", 1) <= MAX_PAGES \
                 or not _numbers(p.get("src"), 4, 0, max(width, height) + 1):
             raise bad(N_("areas"))
         x0, y0, x1, y1 = p["src"]
-        if not (x1 - x0 >= MIN_PIECE_MM and y1 - y0 >= MIN_PIECE_MM and x1 <= width and y1 <= height):
-            raise bad(N_("areas"))
+        if x1 > width + EDGE_TOLERANCE_MM or y1 > height + EDGE_TOLERANCE_MM:
+            raise ParcelError(_("Invalid parcel label type: area {number} reaches beyond the "
+                                "page.").format(number=number))
+        x1, y1 = min(x1, width), min(y1, height)          # Rundung am Rand: auf die Seite
+        if not (x1 - x0 >= MIN_PIECE_MM and y1 - y0 >= MIN_PIECE_MM):
+            raise ParcelError(_("Invalid parcel label type: area {number} is too small (at least "
+                                "{size} mm).").format(number=number,
+                                                      size=number_text(MIN_PIECE_MM)))
         pieces.append(Piece(p.get("page", 1), (float(x0), float(y0), float(x1), float(y1)),
                             p["rotation"], kind=p.get("kind", "text")))
     return ParcelType(type_id, dict(names), "", "own", tuple(tuple(map(float, s)) for s in sizes),
@@ -429,13 +436,21 @@ def _turn(source: Source, ptype: ParcelType, number: int) -> int:
 
 
 def _render_pdf(path: Path, number: int, dpi: float) -> Image.Image:
+    """Seite rendern; die Datei kann seit dem Laden gelöscht, verschoben oder ersetzt sein →
+    ``ParcelError`` (übersetzt)."""
     import pypdfium2 as pdfium
-    with _readable(path), PDFIUM_LOCK:
-        pdf = pdfium.PdfDocument(path)
-        try:
-            return pdf[number - 1].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
-        finally:
-            pdf.close()
+    try:
+        with _readable(path), PDFIUM_LOCK:
+            pdf = pdfium.PdfDocument(path)
+            try:
+                return pdf[number - 1].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
+            finally:
+                pdf.close()
+    except (ValueError, FileNotFoundError, IndexError) as e:
+        reason = (_("page {page} is missing").format(page=number) if isinstance(e, IndexError)
+                  else str(e))
+        raise ParcelError(_("The parcel label can no longer be read ({reason}) – open it "
+                            "again.").format(reason=reason)) from e
 
 
 def all_pieces(ptype: ParcelType) -> tuple[Piece, ...]:
diff --git a/src/labelwerk/parcel_data/README.md b/src/labelwerk/parcel_data/README.md
index 54568b2..6188f2d 100644
--- a/src/labelwerk/parcel_data/README.md
+++ b/src/labelwerk/parcel_data/README.md
@@ -23,7 +23,7 @@ an der echten Marke bis zum nächsten weißen Rand (höchstens 3 mm).
  "types": [{
    "id": "dhl-privat-1", "country": "DE", "carrier": "dhl",
    "names": {"de": "…", "en": "…"}, "verified": true,
-   "source": {"sizes_mm": [[210, 297]], "raster": {"dpi": 300, "x_mm": 0, "y_mm": 0}},
+   "source": {"sizes_mm": [[210, 297]], "raster": {"dpi": 300, "x_mm": 0, "y_mm": 0, "px": [1800, 1200]}},
    "detect": {"all": ["DHL"], "any": ["Online Frankierung"], "none": ["Warenpost"]},
    "layouts": {"62": [{"size_mm": [180, 62], "pieces": [
        {"page": 1, "src": [x0, y0, x1, y1], "rotation": 90, "dst": [x0, y0, x1, y1], "kind": "barcode"}]}]}
@@ -31,7 +31,8 @@ an der echten Marke bis zum nächsten weißen Rand (höchstens 3 mm).
 ```
 
 - **source**: mögliche Seitengrößen der Marke in mm (± 4 mm, auch quer); `raster` nur für Marken, die als
-  Bild kommen (z. B. GIF): in dieser Auflösung an diese Stelle der Seite gelegt.
+  Bild kommen (z. B. GIF): in dieser Auflösung (`dpi`) an diese Stelle der Seite gelegt (`x_mm`, `y_mm`); `px`
+  ist die erwartete Pixelgröße (Breite, Höhe) – nur Bilder mit diesem Seitenverhältnis gelten als dieser Typ.
 - **detect**: Begriffe im Text der PDF – `all` müssen vorkommen, `any` zählen dafür, `none` dagegen.
 - **layouts**: `"62"` = Referenz 62 mm endlos (Seite quer: x längs des Bands, y quer), `"100x150"` =
   Etikett 100 × 150 mm (hochkant). Je Layout ein oder mehrere Ausgabe-Etiketten (Retoure: zwei).
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index 435345f..2d7d694 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -1118,6 +1118,16 @@ msgstr "Ungültige Adresse: {uri}"
 msgid "Invalid name for the favorite: “{name}” (not empty, not too long, without / and \\ and control characters, not starting with a dot)"
 msgstr "Name für den Favoriten ungültig: „{name}“ (nicht leer, nicht zu lang, ohne / und \\ und Steuerzeichen, nicht mit Punkt beginnend)"
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Invalid parcel label type: area {number} is too small (at least {size} mm)."
+msgstr "Ungültiger Markentyp: Bereich {number} ist zu klein (mindestens {size} mm)."
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Invalid parcel label type: area {number} reaches beyond the page."
+msgstr "Ungültiger Markentyp: Bereich {number} ragt über die Seite."
+
 #: src/labelwerk/parcel.py
 #, python-brace-format
 msgid "Invalid parcel label type: {what}"
@@ -2410,7 +2420,7 @@ msgstr "Einstellungen gespeichert – gelten für neue Etiketten."
 #: src/labelwerk/gui/panels/parcel.py
 #, python-brace-format
 msgid "Several types fit equally well ({types}) – choose one in the list."
-msgstr "Mehrere Arten passen gleich gut ({types}) – bitte in der Liste wählen."
+msgstr "Mehrere Typen passen gleich gut ({types}) – bitte in der Liste wählen."
 
 #: src/labelwerk/gui/panels/parcel.py
 msgid "Several types fit equally well – please check the choice."
@@ -2603,7 +2613,7 @@ msgid "Text editing"
 msgstr "Schreibmodus"
 
 #: src/labelwerk/gui/parcel_editor.py
-msgid "Text that is on every such label – labelwerk then recognises the type when opening (several words: separate with commas)"
+msgid "Text that is on every such label – labelwerk then recognizes the type when opening (several words: separate with commas)"
 msgstr "Text, der auf jeder solchen Marke steht – labelwerk erkennt den Typ dann beim Öffnen (mehrere Wörter mit Komma trennen)"
 
 #: src/labelwerk/layout.py
@@ -2649,6 +2659,11 @@ msgstr "Eingelegte Rolle passt nicht zum Etikett {label!r} – Rolle prüfen ode
 msgid "The parcel label ({width} × {height} mm) does not fit the type {name}."
 msgstr "Die Paketmarke ({width} × {height} mm) passt nicht zum Typ {name}."
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The parcel label can no longer be read ({reason}) – open it again."
+msgstr "Die Paketmarke lässt sich nicht mehr lesen ({reason}) – bitte neu öffnen."
+
 #: src/labelwerk/parcel.py
 #, python-brace-format
 msgid "The parcel label has no page {page}."
@@ -2705,7 +2720,7 @@ msgid "Type"
 msgstr "Art"
 
 #: src/labelwerk/gui/panels/parcel.py
-msgid "Type not recognised – choose it in the list."
+msgid "Type not recognized – choose it in the list."
 msgstr "Typ nicht erkannt – in der Liste wählen."
 
 #: src/labelwerk/gui/panels/barcode.py
@@ -3195,6 +3210,11 @@ msgstr "eigener"
 msgid "page sizes"
 msgstr "Seitengrößen"
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "page {page} is missing"
+msgstr "Seite {page} fehlt"
+
 #: src/labelwerk/cli.py
 msgid "parcel label as PDF, PNG, JPG or GIF"
 msgstr "Paketmarke als PDF, PNG, JPG oder GIF"
@@ -3312,6 +3332,11 @@ msgstr[1] "{count} Zeilen"
 msgid "{degrees}° clockwise"
 msgstr "{degrees}° im Uhrzeigersinn"
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "{error} – the previous parcel label stays loaded."
+msgstr "{error} – die vorige Paketmarke bleibt geladen."
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index 39dfddd..e32681d 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -1109,6 +1109,16 @@ msgstr ""
 msgid "Invalid name for the favorite: “{name}” (not empty, not too long, without / and \\ and control characters, not starting with a dot)"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Invalid parcel label type: area {number} is too small (at least {size} mm)."
+msgstr ""
+
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "Invalid parcel label type: area {number} reaches beyond the page."
+msgstr ""
+
 #: src/labelwerk/parcel.py
 #, python-brace-format
 msgid "Invalid parcel label type: {what}"
@@ -2582,7 +2592,7 @@ msgid "Text editing"
 msgstr ""
 
 #: src/labelwerk/gui/parcel_editor.py
-msgid "Text that is on every such label – labelwerk then recognises the type when opening (several words: separate with commas)"
+msgid "Text that is on every such label – labelwerk then recognizes the type when opening (several words: separate with commas)"
 msgstr ""
 
 #: src/labelwerk/layout.py
@@ -2628,6 +2638,11 @@ msgstr ""
 msgid "The parcel label ({width} × {height} mm) does not fit the type {name}."
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "The parcel label can no longer be read ({reason}) – open it again."
+msgstr ""
+
 #: src/labelwerk/parcel.py
 #, python-brace-format
 msgid "The parcel label has no page {page}."
@@ -2684,7 +2699,7 @@ msgid "Type"
 msgstr ""
 
 #: src/labelwerk/gui/panels/parcel.py
-msgid "Type not recognised – choose it in the list."
+msgid "Type not recognized – choose it in the list."
 msgstr ""
 
 #: src/labelwerk/gui/panels/barcode.py
@@ -3174,6 +3189,11 @@ msgstr ""
 msgid "page sizes"
 msgstr ""
 
+#: src/labelwerk/parcel.py
+#, python-brace-format
+msgid "page {page} is missing"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "parcel label as PDF, PNG, JPG or GIF"
 msgstr ""
@@ -3291,6 +3311,11 @@ msgstr[1] ""
 msgid "{degrees}° clockwise"
 msgstr ""
 
+#: src/labelwerk/gui/panels/parcel.py
+#, python-brace-format
+msgid "{error} – the previous parcel label stays loaded."
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2952 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-19-paketmarken-design.md src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/parcel.py src/labelwerk/gui/parcel_editor.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/parcel.py src/labelwerk/parcel_data/README.md src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot tests/gui/test_gui_parcel.py tests/test_parcel.py
git commit -m "Paketmarken nach Gesamtreview: verschwundene Marke ohne Absturz, Bereiche bis zum Seitenrand, Layout-Aktionen nach PAKET, Leisten nach Designwechsel, Überlauf hervorgehoben, Hinweise und Doku

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Abnahme (manuell, durch den Nutzer)

- [ ] Reiter PAKET: echte DHL-Marke (dhl.de, A4) öffnen → als „DHL national“ erkannt, Vorschau auf 62 mm, DRUCKEN; mit dem Handy Leitcode/Identcode/Sicherheitscode scannen.
- [ ] Gleiche Marke mit Typ 1a (100 × 150) auf 62 mm: neu angeordnet, Hinweis.
- [ ] `labelwerk parcel MARKE.pdf --preview p.png` und `labelwerk parcel --list`.
- [ ] Eigener Typ: Bereiche aufziehen, Barcode markieren, speichern, wieder erkennen.
