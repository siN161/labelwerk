# Drucker anderer Hersteller – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** labelwerk druckt außer auf Brother-QL auch auf CUPS-Warteschlangen (z. B. Dymo) und direkt auf Zebra-Drucker (ZPL) – jeweils in der echten Auflösung des Druckers.

**Architecture:** Zuerst die Auflösung je Etikett im Kern (`Label.dpi`, Etiketten „57x32mm@203“), dann `cups.py` (lpstat/lpoptions/lp) und `zpl.py` (ZPL-Bild, Senden) als Qt-freie Wege; `printers`/`labels`/`printer`/`settings`/`cli` binden sie ein, die GUI zeigt sie im Druckermenü und die Schnitt-Optionen im Reiter SERIE.

**Tech Stack:** Python ≥ 3.10, Pillow, pypdfium2 (Tests), brother_ql-inventree 1.3.x, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-19-fremdhersteller-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-vendors3`), nach jedem Task volle Suite grün mit Exit-Code 0 (2348 → 2377 → 2422 → 2466); jeder Schritt von einem Reviewer geprüft und korrigiert (Auflösung: Brother bitgleich, Barcode-Maße in mm, Speichergrenzen, PDF gleich in Druckerauflösung, eine Schreibweise je Etikett; CUPS: nie automatisch gewählt, englische Meldungen, Hintergrund-Thread, Fehler nicht gemerkt, ein PDF je Auftrag ohne Einpassen, Namen geprüft; Zebra: Füllbits weiß, 12/24 Punkte je mm, Zeitlimit je Block, Gerät ohne Anlegen und mit Zeitlimit, nur ZPL-Geräte, Standard ohne ^MM, Streifen ≤ 99 999 Bytes, Serie gestreamt, Optionen je Modell).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Neue Felder im Dokument gehören ins Speicherformat (Schema-Test); Tabellen und Dateien sind fremde Eingabe (nie ein Traceback).
- Keine neue Abhängigkeit (CUPS über die Befehle `lpstat`/`lpoptions`/`lp`).
- Kern bleibt **Qt-frei** (`cups.py`, `zpl.py`, `printers.py`, `labels.py`, `printer.py`, `render.py`, `settings.py`, `cli.py`); kein Test erreicht echte Hardware, CUPS oder das Netz (`send`, `socket.create_connection`, `cups._run` sind in tests/conftest.py ersetzt, sysfs und PPD-Ordner sind leer); **Vorschau = Druck**; **nie den echten Drucker ansprechen** (Rasterdaten prüfen, `send`/`PrintWorker` ersetzen).
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten, ohne echte Dialoge; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen und Kommentare auf Deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Kern – Auflösung je Etikett (Etiketten „BxHmm@dpi“)

**Files:**
- Modify: `src/labelwerk/barcodes.py`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/files.py`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/barcode.py`
- Modify: `src/labelwerk/gui/panels/paper.py`
- Modify: `src/labelwerk/gui/text_edit_mode.py`
- Modify: `src/labelwerk/labels.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/render.py`
- Modify: `src/labelwerk/storage.py`
- Create: `tests/gui/test_gui_label_dpi.py`
- Modify: `tests/test_barcode_objects.py`
- Modify: `tests/test_barcode_reading.py`
- Modify: `tests/test_barcodes.py`
- Create: `tests/test_label_dpi.py`

**Interfaces / Produces:** `labels`: `Label.dpi`, `DPI_RANGE`, `SIZE_MM`, `sized_id(w, h, dpi)`, `sized_label(id)`, `mm_text`, `format_mm(dots, dpi)`; `render`: `_Sheet.dpi`, `RenderedObject.dpi`, `Prepared.dpi`; `layout`: `change_label(doc, label_id)`, dpi-Parameter an `place`/`barcode_rect`/`fix_size`/…; `barcodes`: dpi-Parameter, `scaled`, `insert_module(kind, dpi)`, `max_module(dpi)`; `document.MODULE_LIMIT`; `storage`: Grenzen in Etikett-dpi; `files`: `load_file(…, dpi)`, `crop(img, dpi)`, `fit_to_label(…, dpi)`; GUI: `Canvas.dpi`/`mm`, `resized_frame(…, mm)`, `ModuleSpin.set_dpi`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_label_dpi.py b/tests/gui/test_gui_label_dpi.py
new file mode 100644
index 0000000..a6a1dd4
--- /dev/null
+++ b/tests/gui/test_gui_label_dpi.py
@@ -0,0 +1,21 @@
+"""Arbeitsfläche bei Etiketten anderer Auflösung: echte Größe, mm-Umrechnung, Schreibmarke."""
+import pytest
+
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.canvas import Canvas
+from labelwerk.labels import get_label
+from labelwerk.render import Renderer
+
+
+def test_canvas_shows_a_203_dpi_label_in_real_size(qtbot):
+    canvas = Canvas()
+    qtbot.addWidget(canvas)
+    doc = Document("57x32mm@203", objects=[TextObject("A", size_pt=14, x_mm=10, y_mm=5)])
+    result = Renderer().render(doc)
+    canvas.set_document(get_label(doc.label_id), result.size, result.objects)
+    assert canvas.dpi == 203 and canvas.mm == pytest.approx(203 / 25.4)
+    assert canvas.px_per_mm() == pytest.approx(canvas.zoom / 100 * canvas.logicalDpiX() / 25.4)
+    assert canvas.objects[0].frame_mm().x == pytest.approx(10, abs=0.13)
+    back = Renderer().render(Document("62x29", objects=[TextObject("A")]))
+    canvas.set_document(get_label("62x29"), back.size, back.objects)
+    assert canvas.dpi == 300
diff --git a/tests/test_barcode_objects.py b/tests/test_barcode_objects.py
index 99d9d44..e0e9784 100644
--- a/tests/test_barcode_objects.py
+++ b/tests/test_barcode_objects.py
@@ -330,7 +330,7 @@ def test_storage_round_trip():
     assert storage.from_dict(json.loads(json.dumps(data))).objects == objs
 
 
-@pytest.mark.parametrize("field, value", [("kind", "pdf417"), ("module", 0), ("module", 21),
+@pytest.mark.parametrize("field, value", [("kind", "pdf417"), ("module", 0), ("module", 41),
                                           ("module", 2.5), ("h_mm", 1), ("h_mm", 101),
                                           ("error", "X"), ("data", 5), ("data", "x" * 2001),
                                           ("text", "ja")])
diff --git a/tests/test_barcode_reading.py b/tests/test_barcode_reading.py
index 69b0a94..4565dab 100644
--- a/tests/test_barcode_reading.py
+++ b/tests/test_barcode_reading.py
@@ -66,3 +66,11 @@ def test_zxing_reads_every_qr_level(level):
 def test_zxing_reads_one_dot_modules():
     assert _read(barcodes.draw(_bar(kind="ean13", data="400638133393", module=1, h_mm=8))) \
         == ["4006381333931"]
+
+
+def test_zxing_reads_barcodes_on_a_203_dpi_label():
+    """Andere Drucker: Module in ganzen Punkten bei 203 dpi bleiben lesbar."""
+    objs = [_bar(kind="qr", data="Zebra 203", module=3, x_mm=2, y_mm=2),
+            _bar(kind="code128", data="Z-203", module=2, x_mm=22, y_mm=4, h_mm=10)]
+    found = _read(render_document(Document("57x32mm@203", objects=objs)))
+    assert sorted(found) == ["Z-203", "Zebra 203"]
diff --git a/tests/test_barcodes.py b/tests/test_barcodes.py
index cf488b4..ca4547e 100644
--- a/tests/test_barcodes.py
+++ b/tests/test_barcodes.py
@@ -182,7 +182,7 @@ def test_empty_and_too_long_content():
 
 
 @pytest.mark.parametrize("field, value, message", [
-    ("module", 0, "Modulbreite"), ("module", 21, "Modulbreite"), ("module", True, "Modulbreite"),
+    ("module", 0, "Modulbreite"), ("module", 41, "Modulbreite"), ("module", True, "Modulbreite"),
     ("module", 2.0, "Modulbreite"), ("h_mm", 1.9, "Höhe"), ("h_mm", 100.5, "Höhe"),
     ("h_mm", float("nan"), "Höhe"), ("h_mm", True, "Höhe"), ("text", 1, "Klartext"),
     ("error", "m", "Fehlerkorrektur"), ("rotation", 45, "Drehung")])
diff --git a/tests/test_label_dpi.py b/tests/test_label_dpi.py
new file mode 100644
index 0000000..b742eb4
--- /dev/null
+++ b/tests/test_label_dpi.py
@@ -0,0 +1,177 @@
+"""Auflösung je Etikett (Drucker anderer Hersteller): Etiketten „BxHmm@dpi“, Rendern, Layout und
+Barcodes in der Auflösung des Druckers – dasselbe Etikett ist bei 203 und 300 dpi gleich groß."""
+import pytest
+from PIL import Image
+
+from labelwerk import barcodes, layout, storage
+from labelwerk.document import BarcodeObject, Document, Frame, ImageObject, TextObject
+from labelwerk.files import fit_to_label
+from labelwerk.labels import get_label, sized_id, sized_label
+from labelwerk.render import Renderer, render_document, render_object
+
+L203, L300 = "57x32mm@203", "57x32mm@300"
+
+
+def _ink(img):
+    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()
+
+
+# --- Etiketten ----------------------------------------------------------------------------------
+def test_sized_labels():
+    label = get_label("54x25mm@300")
+    assert (label.width, label.height, label.dpi, label.shape) == (638, 295, 300, "die_cut")
+    assert label.description == "54 × 25 mm · 300 dpi"
+    assert get_label(L203).width == round(57 * 203 / 25.4) == 456
+    assert get_label("101.6x152.4mm@203").description == "101,6 × 152,4 mm · 203 dpi"
+    assert get_label("62").dpi == 300                         # Brother wie bisher
+    assert sized_id(101.6, 50.8, 203) == "101.6x50.8mm@203" and sized_id(54, 25, 300) == "54x25mm@300"
+
+
+@pytest.mark.parametrize("label_id", ["54x25mm@50", "54x25mm@900", "400x25mm@300", "54x25@300",
+                                      "1x25mm@300", "54x25mm@300 ", "54x25mm"])
+def test_invalid_sized_labels(label_id):
+    assert sized_label(label_id) is None
+    with pytest.raises(ValueError, match="Unbekanntes Etikett"):
+        get_label(label_id)
+
+
+def test_sized_label_is_saved_and_opened():
+    doc = Document(L203, objects=[TextObject("A")])
+    assert storage.from_dict(storage.to_dict(doc)).label_id == L203
+
+
+# --- Rendern ------------------------------------------------------------------------------------
+def test_label_image_has_the_printer_resolution():
+    assert render_document(Document(L203, objects=[TextObject("A")])).size == (456, 256)
+    assert render_document(Document(L300, objects=[TextObject("A")])).size == (673, 378)
+
+
+def test_text_has_the_same_size_at_every_resolution():
+    def height_mm(label_id):
+        img = render_document(Document(label_id, objects=[TextObject("Hg", size_pt=20)]))
+        l, t, r, b = _ink(img)
+        return (b - t) * 25.4 / get_label(label_id).dpi
+    assert height_mm(L203) == pytest.approx(height_mm(L300), abs=0.3)
+
+
+def test_positions_and_frames_in_millimetres():
+    obj = TextObject("A", size_pt=12, x_mm=10, y_mm=5)
+    r = render_object(obj, Document(L203, objects=[obj]))
+    assert (r.x, r.y, r.dpi) == (round(10 * 203 / 25.4), round(5 * 203 / 25.4), 203)
+    assert layout.object_rect(r).x == pytest.approx(10, abs=0.13)
+    image = ImageObject.from_image(Image.new("RGB", (236, 118), "black"), 300, "x")  # 20 × 10 mm
+    rendered = render_object(image, Document(L203, objects=[image]))
+    assert (rendered.w, rendered.h) == (160, 80)
+    framed = render_document(Document(L203, frame=Frame("single", line_mm=1), margin_mm=0))
+    assert framed.getpixel((7, 100))[0] == 0 and framed.getpixel((8, 100))[0] == 255   # 1 mm = 8
+
+
+def test_too_large_message_uses_the_resolution():
+    from labelwerk.render import TextTooLarge
+    obj = TextObject("WWWWWWWWWWWW", size_pt=40)
+    with pytest.raises(TextTooLarge) as small:
+        render_document(Document(L203, objects=[obj]))
+    with pytest.raises(TextTooLarge) as large:
+        render_document(Document(L300, objects=[obj]))
+    assert abs(small.value.max_pt - large.value.max_pt) <= 1
+
+
+def test_renderer_and_layout_rects_carry_the_resolution():
+    doc = Document(L203, objects=[TextObject("A", size_pt=12, x_mm=3, y_mm=3)])
+    result = Renderer().render(doc)
+    assert result.objects[0].dpi == 203
+    area = layout.printable_area(doc)
+    assert (area.w, area.h) == (pytest.approx(57 - 2, abs=0.15), pytest.approx(32 - 2, abs=0.15))
+
+
+# --- Barcodes und Layout ------------------------------------------------------------------------
+def test_barcode_modules_are_printer_dots():
+    obj = BarcodeObject(kind="code128", data="AB", module=2, h_mm=10, x_mm=2, y_mm=2)
+    r = render_object(obj, Document(L203, objects=[obj]))
+    assert r.w == barcodes.modules(obj) * 2 and r.h == round(10 * 203 / 25.4)
+    assert layout.barcode_rect(obj, 203).w == pytest.approx(barcodes.modules(obj) * 2 * 25.4 / 203)
+    wider = layout.set_frame(obj, layout.Rect(2, 2, layout.barcode_rect(obj, 203).w * 1.5, 10), r)
+    assert wider.module == 3                                  # 1,5 × 2 Punkte bei 203 dpi
+
+
+def test_fixed_size_text_keeps_its_look_at_203():
+    obj = TextObject("Hallo")
+    doc = Document(L203, objects=[obj])
+    r = render_object(obj, doc)
+    moved = layout.move(obj, layout.object_rect(r).moved(1, 1), r)
+    again = render_object(moved, Document(L203, objects=[moved]))
+    assert (again.w, again.h) == (r.w, r.h)
+
+
+def test_new_barcode_on_a_203_label():
+    doc = Document(L203)
+    area = layout.printable_area(doc)
+    obj = layout.new_barcode(doc, "QL-600", area, "qr")
+    rect = layout.barcode_rect(obj, 203)
+    assert rect.x >= area.x - 1e-6 and rect.right <= area.right + 1e-6
+
+
+def test_print_file_scales_to_the_resolution():
+    img = Image.new("L", (300, 150), 0)                     # 25,4 × 12,7 mm bei 300 dpi
+    out = fit_to_label(img, L203)
+    assert out.size == (456, 256)
+    assert _ink(out.convert("RGB"))[2] - _ink(out.convert("RGB"))[0] == 203
+
+
+# --- Nach der Prüfung: Maße in mm statt fester Druckpunkte -------------------------------------
+@pytest.mark.parametrize("label_id", ["057x32mm@203", "57.0x32mm@203", "57x32mm@0203"])
+def test_only_one_spelling_per_label(label_id):
+    assert sized_label(label_id) is None
+    assert sized_id(57, 32, 203.6) == "57x32mm@204"
+
+
+def test_inserted_barcodes_have_the_same_millimetres():
+    for dpi, ean, qr in ((203, 2, 4), (300, 3, 6), (600, 6, 12)):
+        assert (barcodes.insert_module("ean13", dpi), barcodes.insert_module("qr", dpi)) == (ean, qr)
+    assert (barcodes.max_module(203), barcodes.max_module(300), barcodes.max_module(600)) == (14, 20, 40)
+    doc = Document("57x32mm@600")
+    obj = layout.new_barcode(doc, "QL-600", layout.printable_area(doc), "ean13")
+    assert obj.module * 25.4 / 600 >= 0.25
+
+
+def test_barcode_text_has_the_same_size_at_every_resolution():
+    def text_mm(dpi):
+        obj = BarcodeObject(kind="ean13", data="590123412345",
+                            module=barcodes.scaled(3, dpi), h_mm=15)
+        return barcodes._layout(obj, barcodes.check(obj), dpi).font.size * 25.4 / dpi
+    assert text_mm(203) == pytest.approx(text_mm(300), rel=0.1)
+    assert text_mm(600) == pytest.approx(text_mm(300), rel=0.1)
+
+
+def test_storage_limit_counts_printer_dots():
+    from labelwerk.storage import StorageError
+    big = ImageObject.from_image(Image.new("RGB", (8, 8), "black"), 300, "x")
+    big.w_mm = big.h_mm = 290
+    data = storage.to_dict(Document("300x300mm@300", objects=[big]))
+    storage.from_dict(data)                                   # 11,7 Mio. Punkte: geht
+    many = storage.to_dict(Document("300x300mm@600", objects=[big] * 3))
+    with pytest.raises(StorageError, match="Etikett zu groß"):
+        storage.from_dict(many)                               # 3 × 46,9 Mio. Punkte bei 600 dpi
+
+
+def test_sizes_are_shown_with_a_comma():
+    from labelwerk.labels import mm_text
+    assert (mm_text(101.6), mm_text(57.0), mm_text(62)) == ("101,6", "57", "62")
+
+
+def test_pdf_is_loaded_in_the_printer_resolution(tmp_path):
+    from labelwerk.files import load_file
+    path = tmp_path / "a.png"
+    Image.new("L", (300, 300), 0).save(path, dpi=(300, 300))   # 25,4 mm
+    assert load_file(path, dpi=203).size == (203, 203)
+    sharp = fit_to_label(load_file(path, dpi=203), L203, dpi=203)
+    assert _ink(sharp.convert("RGB"))[2] - _ink(sharp.convert("RGB"))[0] == 203
+
+
+def test_changing_the_label_keeps_barcode_millimetres():
+    doc = Document("57x32mm@300", objects=[BarcodeObject(kind="qr", data="x", module=6),
+                                           TextObject("A")])
+    layout.change_label(doc, "57x32mm@203")
+    assert doc.label_id == "57x32mm@203" and doc.objects[0].module == 4
+    layout.change_label(doc, "62x29")
+    assert doc.objects[0].module == 6
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_label_dpi.py, tests/gui/test_gui_label_dpi.py, Lesetest bei 203 dpi) schlagen fehl (ImportError `sized_id`), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/barcodes.py b/src/labelwerk/barcodes.py
index 5790075..e2e37e1 100644
--- a/src/labelwerk/barcodes.py
+++ b/src/labelwerk/barcodes.py
@@ -15,7 +15,7 @@ import segno
 from PIL import Image, ImageDraw
 
 from . import fonts
-from .document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, MAX_MODULE, QR_LEVELS,
+from .document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, MAX_MODULE, MODULE_LIMIT, QR_LEVELS,
                        ROTATIONS, BarcodeObject)
 from .labels import DPI
 
@@ -23,7 +23,7 @@ TITLES = {"qr": "QR-Code", "code128": "Code 128", "code39": "Code 39", "ean13":
           "ean8": "EAN-8"}
 SAMPLES = {"qr": "labelwerk", "code128": "ABC-123", "code39": "ABC-123", "ean13": "590123412345",
            "ean8": "9638507"}                 # Beispielinhalt beim Einfügen
-INSERT_MODULE = {"qr": 6}    # Modulbreite beim Einfügen (sonst 3 Druckpunkte = 0,25 mm)
+INSERT_MODULE = {"qr": 6}    # Modulbreite beim Einfügen bei 300 dpi (sonst 3 Druckpunkte = 0,25 mm)
 MAX_LINEAR = 80              # Zeichen je Strichcode
 # Ruhezone in Modulen außerhalb des Rahmens (sonst 10) – EAN-13 links 11, davon 7 für die erste Ziffer
 QUIET = {"qr": 4, "ean13": 11, "ean8": 7}
@@ -243,8 +243,8 @@ def _ean8(data: str) -> Code:
 
 
 # --- Maße und Zeichnen -----------------------------------------------------------------------
-def _dots(mm: float) -> int:
-    return round(mm * DPI / 25.4)
+def _dots(mm: float, dpi: int = DPI) -> int:
+    return round(mm * dpi / 25.4)
 
 
 def _number(v) -> bool:
@@ -256,8 +256,8 @@ def check(obj: BarcodeObject) -> Code:
     if obj.rotation not in ROTATIONS:
         raise BarcodeError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
     if not isinstance(obj.module, int) or isinstance(obj.module, bool) \
-            or not 1 <= obj.module <= MAX_MODULE:
-        raise BarcodeError(f"Modulbreite {obj.module!r} ungültig – erlaubt: 1–{MAX_MODULE} "
+            or not 1 <= obj.module <= MODULE_LIMIT:
+        raise BarcodeError(f"Modulbreite {obj.module!r} ungültig – erlaubt: 1–{MODULE_LIMIT} "
                            f"Druckpunkte")
     if not isinstance(obj.text, bool):
         raise BarcodeError(f"Klartext muss an oder aus sein, nicht {obj.text!r}")
@@ -275,10 +275,10 @@ def modules(obj: BarcodeObject) -> int:
     return len(code.rows) if code.matrix else len(code.rows[0]) + (code.lead if obj.text else 0)
 
 
-def quiet_mm(obj: BarcodeObject) -> float:
+def quiet_mm(obj: BarcodeObject, dpi: int = DPI) -> float:
     """Ruhezone links und rechts (mm) außerhalb des Rahmens, die frei bleiben sollte."""
     modules = 7 if obj.kind == "ean13" and obj.text else QUIET.get(obj.kind, 10)
-    return modules * obj.module * 25.4 / DPI
+    return modules * obj.module * 25.4 / dpi
 
 
 # höchstens so viele Module breit (QR: Version 40; Code 128 ganz in B; Code 39 mit Lücken)
@@ -286,11 +286,11 @@ MAX_MODULES = {"qr": 177, "code128": 11 * (MAX_LINEAR + 2) + 13, "code39": 16 *
                "ean13": 102, "ean8": 67}
 
 
-def max_size(obj: BarcodeObject) -> tuple[int, int]:
+def max_size(obj: BarcodeObject, dpi: int = DPI) -> tuple[int, int]:
     """Obere Schranke der Größe (Druckpunkte, ungedreht) ohne Kodieren – für die Grenzen fremder
     Dateien, auch wenn erst die Serie den Inhalt füllt."""
     side = MAX_MODULES.get(obj.kind, 0) * obj.module
-    return (side, side) if obj.kind == "qr" else (side, _dots(obj.h_mm))
+    return (side, side) if obj.kind == "qr" else (side, _dots(obj.h_mm, dpi))
 
 
 @dataclass(frozen=True)
@@ -303,24 +303,24 @@ class _Layout:
     baseline: int = 0
 
 
-def size(obj: BarcodeObject) -> tuple[int, int]:
-    """Größe (Breite, Höhe) in Druckpunkten, ungedreht."""
-    layout = _layout(obj, check(obj))
+def size(obj: BarcodeObject, dpi: int = DPI) -> tuple[int, int]:
+    """Größe (Breite, Höhe) in Druckpunkten bei ``dpi``, ungedreht."""
+    layout = _layout(obj, check(obj), dpi)
     return layout.width, layout.height
 
 
-def _layout(obj: BarcodeObject, code: Code) -> _Layout:
+def _layout(obj: BarcodeObject, code: Code, dpi: int = DPI) -> _Layout:
     m = obj.module
     if code.matrix:
         side = len(code.rows) * m
         return _Layout(side, side, side, side)
     width = (len(code.rows[0]) + (code.lead if obj.text else 0)) * m
-    height = _dots(obj.h_mm)
+    height = _dots(obj.h_mm, dpi)
     if not obj.text:
         return _Layout(width, height, height, height)
-    font, top, bottom, gap = _text_font(code, m, height)
+    font, top, bottom, gap = _text_font(code, m, height, dpi)
     bars = height - gap - top - bottom
-    if bars < _dots(MIN_BARS_MM):
+    if bars < _dots(MIN_BARS_MM, dpi):
         raise BarcodeError("Barcode zu niedrig für den Klartext – höher ziehen oder Klartext aus")
     return _Layout(width, height, bars, bars + (gap + top) // 2, font, bars + gap + top)
 
@@ -330,11 +330,26 @@ def _font_path() -> str:
     return fonts.resolve(None, False, False).path
 
 
-def _text_font(code: Code, m: int, height: int):
+def scaled(dots: int, dpi: int) -> int:
+    """Druckpunkte bei 300 dpi in der Auflösung ``dpi`` (gleiche Größe in mm, mindestens 1)."""
+    return dots if dpi == DPI else max(1, round(dots * dpi / DPI))
+
+
+def insert_module(kind: str, dpi: int = DPI) -> int:
+    """Modulbreite beim Einfügen in Druckpunkten bei ``dpi`` (gleiche mm wie bei 300 dpi)."""
+    return scaled(INSERT_MODULE.get(kind, 3), dpi)
+
+
+def max_module(dpi: int = DPI) -> int:
+    """Größte Modulbreite, die Einpassen und Eingabe bei ``dpi`` zulassen (1,7 mm)."""
+    return min(scaled(MAX_MODULE, dpi), MODULE_LIMIT)
+
+
+def _text_font(code: Code, m: int, height: int, dpi: int = DPI):
     """Klartext-Schrift und ihr Platz (Schrift, über und unter der Grundlinie, Abstand zu den
     Strichen): rund ``TEXT_MODULES`` Module groß (mindestens 6 pt), verkleinert, bis jede Gruppe in
     ihre Breite passt und der Klartext höchstens ``TEXT_SHARE`` der Höhe braucht."""
-    dots = max(TEXT_MODULES * m, MIN_TEXT_DOTS)
+    dots = max(TEXT_MODULES * m, scaled(MIN_TEXT_DOTS, dpi))
     path = _font_path()
     while True:
         font = fonts.load(path, dots)
@@ -342,15 +357,15 @@ def _text_font(code: Code, m: int, height: int):
         top, bottom, gap = -top, max(0, bottom), max(2, dots // 8)
         over = max(font.getlength(text) / ((end - start) * m) for text, start, end in code.text)
         over = max(over, (gap + top + bottom) / (TEXT_SHARE * height))
-        if over <= 1 or dots <= MIN_FIT_DOTS:
+        if over <= 1 or dots <= scaled(MIN_FIT_DOTS, dpi):
             return font, top, bottom, gap
         dots = max(MIN_FIT_DOTS, min(dots - 1, math.floor(dots / over)))
 
 
-def draw(obj: BarcodeObject) -> Image.Image:
+def draw(obj: BarcodeObject, dpi: int = DPI) -> Image.Image:
     """Barcode als Graustufenbild (L, weißer Grund, Tinte schwarz) in ``size(obj)``, ungedreht."""
     code = check(obj)
-    layout = _layout(obj, code)
+    layout = _layout(obj, code, dpi)
     img = Image.new("L", (layout.width, layout.height), 255)
     pen = ImageDraw.Draw(img)
     m = obj.module
@@ -370,10 +385,11 @@ def draw(obj: BarcodeObject) -> Image.Image:
     return img
 
 
-def placeholder_size(obj: BarcodeObject) -> tuple[int, int]:
+def placeholder_size(obj: BarcodeObject, dpi: int = DPI) -> tuple[int, int]:
     """Größe (Druckpunkte, ungedreht) für einen Barcode, der sich nicht kodieren lässt – etwa so
     groß, wie er mit diesem Inhalt würde (Arbeitsfläche: bleibt sichtbar und wählbar)."""
-    m = obj.module if isinstance(obj.module, int) and 1 <= obj.module <= MAX_MODULE else 3
+    m = (obj.module if isinstance(obj.module, int) and 1 <= obj.module <= MODULE_LIMIT
+         else scaled(3, dpi))
     n = len(obj.data) if isinstance(obj.data, str) else 1
     if obj.kind == "qr":
         side = (21 + 4 * min(39, n // 20)) * m
@@ -382,7 +398,7 @@ def placeholder_size(obj: BarcodeObject) -> tuple[int, int]:
     count = {"ean13": 102 if obj.text is True else 95, "ean8": 67,
              "code39": 16 * (n + 2)}.get(obj.kind, 11 * (n + 3) + 13)
     h = obj.h_mm if _number(obj.h_mm) and BARCODE_MM[0] <= obj.h_mm <= BARCODE_MM[1] else 10.0
-    return count * m, _dots(h)
+    return count * m, _dots(h, dpi)
 
 
 def placeholder(width: int, height: int) -> Image.Image:
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index af6720b..c857f97 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -170,9 +170,11 @@ def _auto_label(model: str, target: printers.Printer | None) -> str:
 
 def _make_image(args: argparse.Namespace) -> Image.Image:
     if args.cmd == "print-file":
-        img = crop(load_file(args.file, page=args.page))
+        dpi = get_label(args.label).dpi                # PDF gleich in der Auflösung des Druckers
+        img = crop(load_file(args.file, page=args.page, dpi=dpi), dpi)
         rotate = args.rotate if args.rotate == "auto" else int(args.rotate)
-        return fit_to_label(img, args.label, fit=args.fit, model=args.model, rotate=rotate)
+        return fit_to_label(img, args.label, fit=args.fit, model=args.model, rotate=rotate,
+                            dpi=dpi)
     text = args.text.replace("\\n", "\n")
     obj = TextObject.plain(text, size_pt=args.font_size, align=args.align,
                            family=args.font_family, bold=args.bold, italic=args.italic,
@@ -349,7 +351,9 @@ def main(argv: list[str] | None = None) -> int:
         except (OSError, ValueError) as e:
             print(f"Vorschau kann nicht gespeichert werden: {args.preview} ({e})", file=sys.stderr)
             return 2
-        print(f"Vorschau: {args.preview} ({format_mm(img.width)} × {format_mm(img.height)} mm)")
+        dpi = get_label(args.label).dpi
+        print(f"Vorschau: {args.preview} ({format_mm(img.width, dpi)} × "
+              f"{format_mm(img.height, dpi)} mm)")
         return 0
 
     return _send(img, args)
diff --git a/src/labelwerk/document.py b/src/labelwerk/document.py
index 442be7a..82b2a4a 100644
--- a/src/labelwerk/document.py
+++ b/src/labelwerk/document.py
@@ -27,7 +27,8 @@ MAX_DIGITS = 10
 # Barcodes: Arten, QR-Fehlerkorrektur, Modulbreite in Druckpunkten, Höhe, Inhalt
 BARCODE_KINDS = ("qr", "code128", "code39", "ean13", "ean8")
 QR_LEVELS = ("L", "M", "Q", "H")
-MAX_MODULE = 20
+MAX_MODULE = 20                     # bei 300 dpi; andere Auflösungen entsprechend (barcodes.max_module)
+MODULE_LIMIT = 40                   # gültige Modulbreite überhaupt (600 dpi)
 BARCODE_MM = (2.0, 100.0)           # Höhe der Strichcodes samt Klartext
 MAX_BARCODE_DATA = 2000
 
diff --git a/src/labelwerk/files.py b/src/labelwerk/files.py
index 14c9062..fdf3aa1 100644
--- a/src/labelwerk/files.py
+++ b/src/labelwerk/files.py
@@ -26,11 +26,12 @@ _PDFIUM_PASSWORD = 4   # FPDF_ERR_PASSWORD
 MM = DPI / 25.4      # Punkte pro mm
 
 
-def load_file(path: str | Path, page: int = 1) -> Image.Image:
-    """Datei als Graustufenbild bei 300 dpi (Größe in mm bleibt erhalten)."""
+def load_file(path: str | Path, page: int = 1, dpi: int = DPI) -> Image.Image:
+    """Datei als Graustufenbild bei ``dpi`` (Auflösung des Etiketts; Größe in mm bleibt)."""
     path = _checked(path, _IMAGE_SUFFIXES, "PDF, PNG, JPG", page)
     with _readable(path):
-        return _load_pdf(path, page) if path.suffix.lower() == ".pdf" else _load_image(path)
+        return (_load_pdf(path, page, dpi) if path.suffix.lower() == ".pdf"
+                else _load_image(path, dpi))
 
 
 def load_image(path: str | Path, page: int = 1,
@@ -127,9 +128,9 @@ def _reason(error: Exception) -> str:
     return "Lesefehler"
 
 
-def _load_pdf(path: Path, page: int) -> Image.Image:
+def _load_pdf(path: Path, page: int, dpi: int = DPI) -> Image.Image:
     with _pdf_page(path, page) as pdf_page:
-        return pdf_page.render(scale=DPI / 72).to_pil().convert("L")
+        return pdf_page.render(scale=dpi / 72).to_pil().convert("L")
 
 
 def _load_pdf_page(path: Path, page: int) -> tuple[Image.Image, float]:
@@ -152,21 +153,21 @@ def _pdf_page(path: Path, page: int):
         pdf.close()
 
 
-def _load_image(path: Path) -> Image.Image:
+def _load_image(path: Path, target: int = DPI) -> Image.Image:
     with Image.open(path, formats=_IMAGE_FORMATS) as src:
         dpi = float(src.info.get("dpi", (DPI, DPI))[0]) or DPI
         img = to_8bit(src).convert("RGBA")             # 16-Bit-Graustufen skalieren
     img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img).convert("L")
-    if round(dpi) != DPI:
-        f = DPI / dpi
+    if round(dpi) != target:
+        f = target / dpi
         img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
                          Image.LANCZOS)
     return img
 
 
-def crop(img: Image.Image) -> Image.Image:
+def crop(img: Image.Image, dpi: int = DPI) -> Image.Image:
     """Auf den Inhalt zuschneiden; liegen vier Eck-Schnittmarken außen, ohne die Marken."""
-    return img.crop(_content_box(img, DPI, INK))
+    return img.crop(_content_box(img, dpi, INK))
 
 
 def crop_box(img: Image.Image, dpi: float = DPI,
@@ -250,8 +251,10 @@ ROTATIONS = ("auto", 0, 90, 180, 270)
 
 
 def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
-                 model: str = "QL-600", rotate: str | int = "auto") -> Image.Image:
-    """Motiv 1:1 mittig aufs Etikett setzen; verkleinern nur mit fit.
+                 model: str = "QL-600", rotate: str | int = "auto",
+                 dpi: int = DPI) -> Image.Image:
+    """Motiv (``dpi`` wie bei ``load_file``) 1:1 mittig aufs Etikett setzen – in der Auflösung
+    des Etiketts (andere wird umgerechnet); verkleinern nur mit fit.
 
     rotate: "auto" dreht nur wenn nötig (90° gegen den Uhrzeigersinn), sonst feste
     Drehung in Grad im Uhrzeigersinn (0, 90, 180, 270).
@@ -259,6 +262,10 @@ def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
     if rotate not in ROTATIONS:
         raise ValueError(f"Drehung {rotate!r} nicht möglich – erlaubt: auto, 0, 90, 180, 270")
     label = get_label(label_id)
+    if label.dpi != dpi:                         # gleiche Größe in den Punkten des Druckers
+        f = label.dpi / dpi
+        img = img.resize((max(1, round(img.width * f)), max(1, round(img.height * f))),
+                         Image.LANCZOS)
     min_len, max_len = length_limits(model)
     max_w = label.width
     max_h = label.height if label.height else max_len - 2 * MARGIN
@@ -274,10 +281,11 @@ def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
         elif fit:
             img = _shrink(img, max_w, max_h, may_rotate=rotate == "auto")
         else:
-            limit = (f"{format_mm(max_w)} mm breit" if not label.height
-                     else f"{format_mm(max_w)} × {format_mm(max_h)} mm groß")
+            mm = lambda dots: format_mm(dots, label.dpi)   # noqa: E731
+            limit = (f"{mm(max_w)} mm breit" if not label.height
+                     else f"{mm(max_w)} × {mm(max_h)} mm groß")
             raise ValueError(
-                f"Motiv ist {format_mm(img.width)} × {format_mm(img.height)} mm, "
+                f"Motiv ist {mm(img.width)} × {mm(img.height)} mm, "
                 f"Etikett {label_id!r} ist höchstens {limit} – "
                 "mit --fit verkleinern (Codes evtl. nicht mehr lesbar)")
 
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index 161a31f..baaa250 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -17,20 +17,20 @@ from PySide6.QtWidgets import (QApplication, QGraphicsPixmapItem, QGraphicsRectI
 
 from .. import layout
 from . import image_import
-from ..labels import DPI, Label, format_mm, length_limits
+from ..labels import DPI, Label, format_mm, length_limits, mm_text
 from ..layout import Rect
 from ..printer import DEFAULT_MODEL
 from ..render import INK, PT, RenderedObject
 
-MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm
+MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm bei 300 dpi; je Etikett ``Canvas.mm``
 RULER = 22               # Linealbreite in Pixeln
-_CORNER = 2 * MM         # Eckenradius gestanzter Etiketten
-_MARGIN = 15 * MM        # grauer Rand um das Etikett
+_CORNER_MM = 2           # Eckenradius gestanzter Etiketten
+_MARGIN_MM = 15          # grauer Rand um das Etikett
 START_ZOOM = 200         # Prozent; 100 % = echte Größe
 SNAP_PX = 6              # Einrasten: Abstand in Bildschirmpixeln
 HANDLE_PX = 8            # Kantenlänge eines Anfassers in Bildschirmpixeln
 _DRAG_START_PX = 3       # erst ab dieser Mausbewegung wird gezogen (Klick ≠ Verschieben)
-_MIN_FRAME = MM          # kleinster Rahmen beim Skalieren (1 mm)
+_MIN_FRAME_MM = 1        # kleinster Rahmen beim Skalieren
 HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")   # Ecken und Kanten, im Uhrzeigersinn
 _HANDLE_CURSORS = {
     "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
@@ -82,7 +82,7 @@ class ObjectItem(QGraphicsPixmapItem):
     def size(self) -> tuple[float, float]:
         """Rahmengröße in Druckpunkten; ein leerer Text zeigt einen Platzhalter (eine Zeile hoch)."""
         if self.is_empty():
-            line = self.rendered.base_pt * PT
+            line = self.rendered.base_pt * self.rendered.dpi / 72
             return line / 2, line
         return self.rendered.w, self.rendered.h
 
@@ -91,8 +91,8 @@ class ObjectItem(QGraphicsPixmapItem):
         return self.mapRectToParent(QRectF(0, 0, *self.size()))
 
     def frame_mm(self) -> Rect:
-        f = self.frame()
-        return Rect(f.x() / MM, f.y() / MM, f.width() / MM, f.height() / MM)
+        f, mm = self.frame(), self.rendered.dpi / 25.4
+        return Rect(f.x() / mm, f.y() / mm, f.width() / mm, f.height() / mm)
 
 
 class Canvas(QGraphicsView):
@@ -125,6 +125,7 @@ class Canvas(QGraphicsView):
         self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
         self.viewport().setMouseTracking(True)             # Mauszeiger über den Anfassern
         self.setAcceptDrops(True)                          # Bilder und Bilddateien ablegen
+        self.dpi, self.mm = DPI, MM                        # Auflösung des Etiketts, Punkte je mm
         self.set_model(model)
         self.zoom = START_ZOOM
         self.orientation = "vertical"
@@ -184,8 +185,9 @@ class Canvas(QGraphicsView):
         Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°, damit das Etikett in
         Leserichtung erscheint – die Objekte liegen in ``sheet``, das in Leserichtung zählt.
         """
-        if orientation != self.orientation:
+        if orientation != self.orientation or label.dpi != self.dpi:
             self.orientation = orientation
+            self.dpi, self.mm = label.dpi, label.dpi / 25.4   # Szene in Druckpunkten des Etiketts
             self._apply_zoom()
         self.cancel_object_drag()
         scene = self.scene()
@@ -200,7 +202,7 @@ class Canvas(QGraphicsView):
         if label.shape == "round":
             path.addEllipse(0, 0, tw, th)
         elif label.shape == "die_cut":
-            path.addRoundedRect(0, 0, tw, th, _CORNER, _CORNER)
+            path.addRoundedRect(0, 0, tw, th, _CORNER_MM * self.mm, _CORNER_MM * self.mm)
         else:
             path.addRect(0, 0, tw, th)
         self.outline = scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
@@ -228,15 +230,15 @@ class Canvas(QGraphicsView):
         self.objects = [ObjectItem(i, obj, self._pixmaps[id(obj)][1], ratio, self.sheet, aspect)
                         for i, (obj, ratio, aspect) in enumerate(zip(rendered, ratios, aspects))]
         self._show_edit_cursor()
-        self._label_rect = Rect(0, 0, width / MM, height / MM)
+        self._label_rect = Rect(0, 0, width / self.mm, height / self.mm)
         self._area = area if area is not None else self._label_rect
         self._grow = grow
         dotted = QPen(QColor("#888888"), 1, Qt.PenStyle.DotLine)
         dotted.setCosmetic(True)
         if label.shape != "round" and area is not None:
             # bedruckbarer Bereich mit allen vier Rändern (auch in Bandrichtung), in Leserichtung
-            self.printable = QGraphicsRectItem(QRectF(area.x * MM, area.y * MM,
-                                                      area.w * MM, area.h * MM), self.sheet)
+            self.printable = QGraphicsRectItem(QRectF(area.x * self.mm, area.y * self.mm,
+                                                      area.w * self.mm, area.h * self.mm), self.sheet)
             self.printable.setPen(dotted)
             self.printable.setZValue(-2)                 # unter dem Zierrahmen
         else:
@@ -249,14 +251,15 @@ class Canvas(QGraphicsView):
             self._add_tape(scene, tw, th)
             dashed = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
             dashed.setCosmetic(True)
-            scene.addLine(-2 * MM, th, tw + 2 * MM, th, dashed)
-            self.handle = scene.addRect(QRectF(tw / 2 - 5 * MM, th + MM, 10 * MM, 2 * MM),
+            scene.addLine(-2 * self.mm, th, tw + 2 * self.mm, th, dashed)
+            self.handle = scene.addRect(QRectF(tw / 2 - 5 * self.mm, th + self.mm, 10 * self.mm, 2 * self.mm),
                                         QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.black))
             self.handle.setCursor(Qt.CursorShape.SizeHorCursor if self.orientation == "horizontal"
                                   else Qt.CursorShape.SizeVerCursor)
             self.handle.setToolTip("Ziehen: Länge festlegen · Doppelklick: automatisch")
         self._caption = self._caption_for(th)
-        scene.setSceneRect(-_MARGIN, -_MARGIN, tw + 2 * _MARGIN, th + 2 * _MARGIN)
+        margin = _MARGIN_MM * self.mm
+        scene.setSceneRect(-margin, -margin, tw + 2 * margin, th + 2 * margin)
         self.set_selection([i for i in self._selection if self._selectable(i)])
 
     def _add_tape(self, scene: QGraphicsScene, tw: float, th: float) -> None:
@@ -265,7 +268,7 @@ class Canvas(QGraphicsView):
         dahinter läuft das Band als hellgrauer Streifen weiter (Szene-y; bei „horizontal“ ist
         die Ansicht gedreht). Nur Anzeige: reagiert nicht auf die Maus und gehört weder zum
         Druckbild noch zur Etikettgröße."""
-        self._tape = QRectF(0, th, tw, _MARGIN)
+        self._tape = QRectF(0, th, tw, _MARGIN_MM * self.mm)
         self.tape = scene.addRect(self._tape, QPen(Qt.PenStyle.NoPen), QBrush(_TAPE_COLOR))
         self.tape.setZValue(-1)
         self.tape.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
@@ -423,7 +426,7 @@ class Canvas(QGraphicsView):
             self.edit_requested.emit(item.index, self._reading(pos))
             return
         point = self._reading(pos)
-        x, y = point.x() / MM, point.y() / MM
+        x, y = point.x() / self.mm, point.y() / self.mm
         label = self._label_rect
         if label.x <= x <= label.right and label.y <= y <= label.bottom:
             self.set_tool("select")
@@ -432,7 +435,7 @@ class Canvas(QGraphicsView):
     # --- Geometrie --------------------------------------------------------
     def px_per_mm(self) -> float:
         """Bildschirmpixel je mm beim aktuellen Zoom."""
-        return self._scale * MM
+        return self._scale * self.mm
 
     def guides(self) -> list[tuple[str, float]]:
         """Hilfslinien beim Ziehen: ("x" | "y", mm in Leserichtung)."""
@@ -482,7 +485,7 @@ class Canvas(QGraphicsView):
         self.zoom_changed.emit(self.zoom)
 
     def _apply_zoom(self) -> None:
-        self._scale = self.zoom / 100 * self.logicalDpiX() / DPI   # 100 % = echte Größe
+        self._scale = self.zoom / 100 * self.logicalDpiX() / self.dpi   # 100 % = echte Größe
         self.resetTransform()
         self.scale(self._scale, self._scale)
         if self.orientation == "horizontal":
@@ -491,9 +494,10 @@ class Canvas(QGraphicsView):
     def _caption_for(self, length_dots: float) -> str:
         """Größenangabe in Leserichtung (Breite × Höhe)."""
         w, h = self.label.size_mm
+        w = mm_text(w)
         if self.label.shape == "round":
             return f"Ø {w} mm"
-        along = format_mm(round(length_dots)) if self.label.shape == "endless" else str(h)
+        along = format_mm(round(length_dots)) if self.label.shape == "endless" else mm_text(h)
         return f"{along} × {w} mm" if self.orientation == "horizontal" else f"{w} × {along} mm"
 
     def wheelEvent(self, event) -> None:
@@ -513,7 +517,7 @@ class Canvas(QGraphicsView):
 
     def snap_length(self, scene_y: float) -> float:
         """Szene-y der Unterkante → Länge in mm (Raster 0,5 mm, innerhalb der Modellgrenzen)."""
-        mm = round(scene_y / MM * 2) / 2
+        mm = round(scene_y / self.mm * 2) / 2
         return min(max(mm, self.min_mm), self.max_mm)
 
     def mousePressEvent(self, event) -> None:
@@ -577,8 +581,8 @@ class Canvas(QGraphicsView):
         pos = event.position()
         if self._drag == "length":
             mm = self.snap_length(self.mapToScene(pos.toPoint()).y() - self._grab_offset)
-            self.handle.setY(mm * MM - self.label_height())
-            self._caption = self._caption_for(mm * MM)
+            self.handle.setY(mm * self.mm - self.label_height())
+            self._caption = self._caption_for(mm * self.mm)
             self.viewport().update()
             self._moved = True
             self.length_changed.emit(mm)
@@ -612,28 +616,28 @@ class Canvas(QGraphicsView):
         delta = self._reading(pos) - self._reading(self._press)
         self._guides = []
         if snapping:
-            dx, dy = delta.x() / MM, delta.y() / MM
+            dx, dy = delta.x() / self.mm, delta.y() / self.mm
             frames = [self._start_rect(i).moved(dx, dy) for i in self._start]
             targets = [item.frame_mm() for item in self.objects
                        if item.index not in self._start and not item.is_empty()]
             snap = layout.snap(layout.bounds(frames), targets, self._area,
                                SNAP_PX / self.px_per_mm(), label=self._label_rect,
                                grow=self._grow, inner=self._inner)
-            delta += QPointF(snap.dx * MM, snap.dy * MM)
+            delta += QPointF(snap.dx * self.mm, snap.dy * self.mm)
             self._guides = snap.guides
         for index, start in self._start.items():
             self.objects[index].setPos(start + delta)
 
     def _start_rect(self, index: int) -> Rect:
         start, (w, h) = self._start[index], self.objects[index].size()
-        return Rect(start.x() / MM, start.y() / MM, w / MM, h / MM)
+        return Rect(start.x() / self.mm, start.y() / self.mm, w / self.mm, h / self.mm)
 
     def _drag_resize(self, pos: QPointF) -> None:
         """Vorschau beim Ziehen an einem Anfasser: Bild gestreckt, gerendert wird beim Loslassen."""
         item = self.objects[self._grabbed]
         frame = resized_frame(self._start_frame, self._resize_key,
                               self._reading(pos) + self._handle_offset, item.keep_ratio,
-                              item.keep_aspect)
+                              item.keep_aspect, self.mm)
         item.setPos(frame.topLeft())
         item.setTransform(QTransform.fromScale(frame.width() / item.rendered.w,
                                                frame.height() / item.rendered.h))
@@ -709,7 +713,7 @@ class Canvas(QGraphicsView):
         point = self._reading(event.position())
         # Daten jetzt kopieren (QMimeData lebt nur während des Ablegens), verarbeiten erst
         # danach: ein Dialog (PDF-Seite) im dropEvent hielte die Quelle des Ziehens fest
-        x, y = point.x() / MM, point.y() / MM
+        x, y = point.x() / self.mm, point.y() / self.mm
         if event.mimeData().hasFormat(image_import.MIME_SYMBOL):
             symbol = bytes(event.mimeData().data(image_import.MIME_SYMBOL)).decode(errors="replace")
             QTimer.singleShot(0, self, lambda: self.symbol_dropped.emit(symbol, x, y))
@@ -781,7 +785,7 @@ class Canvas(QGraphicsView):
         """Rote Hilfslinien über die ganze Ansicht, solange ein Objekt einrastet."""
         painter.setPen(QPen(_GUIDE_COLOR, 1))
         for axis, mm in self._guides:
-            point = self._view_point(mm * MM, mm * MM)
+            point = self._view_point(mm * self.mm, mm * self.mm)
             if axis == "x":
                 painter.drawLine(QPointF(point.x(), 0), QPointF(point.x(), vh))
             else:
@@ -795,7 +799,7 @@ class Canvas(QGraphicsView):
 
     def _draw_rulers(self, painter: QPainter, vw: int, vh: int) -> None:
         origin = self.label_view_rect().topLeft() if self.outline else self.mapFromScene(QPointF(0, 0))
-        ppm = self._scale * MM                            # Pixel pro mm
+        ppm = self._scale * self.mm                            # Pixel pro mm
         small = QFont(painter.font())
         small.setPointSize(7)
         small.setBold(False)
@@ -829,22 +833,23 @@ class Canvas(QGraphicsView):
 
 
 def resized_frame(start: QRectF, key: str, point: QPointF, keep_ratio: bool,
-                  keep_aspect: bool = False) -> QRectF:
+                  keep_aspect: bool = False, mm: float = MM) -> QRectF:
     """Rahmen nach Ziehen am Anfasser ``key`` auf ``point`` (Druckpunkte in Leserichtung).
 
-    Die gegenüberliegende Ecke bzw. Kante bleibt stehen; mindestens 1 mm. ``keep_ratio``:
+    Die gegenüberliegende Ecke bzw. Kante bleibt stehen; mindestens 1 mm (``mm``: Druckpunkte je
+    mm des Etiketts). ``keep_ratio``:
     Ecken behalten das Seitenverhältnis (Schrift skalieren); ``keep_aspect``: Ecken und
     Kanten wie beim Loslassen (``layout.keep_aspect``, Bild).
     """
     left, top, right, bottom = start.left(), start.top(), start.right(), start.bottom()
     if "l" in key:
-        left = min(point.x(), right - _MIN_FRAME)
+        left = min(point.x(), right - _MIN_FRAME_MM * mm)
     if "r" in key:
-        right = max(point.x(), left + _MIN_FRAME)
+        right = max(point.x(), left + _MIN_FRAME_MM * mm)
     if "t" in key:
-        top = min(point.y(), bottom - _MIN_FRAME)
+        top = min(point.y(), bottom - _MIN_FRAME_MM * mm)
     if "b" in key:
-        bottom = max(point.y(), top + _MIN_FRAME)
+        bottom = max(point.y(), top + _MIN_FRAME_MM * mm)
     if keep_aspect:
         old = Rect(start.x(), start.y(), start.width(), start.height())
         new = layout.keep_aspect(old, Rect(left, top, right - left, bottom - top), key)
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 68c51d3..022f569 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -26,9 +26,9 @@ from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, S
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
 from ..labels import DPI, get_label, labels_for_model
-from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, fill_anchored,
-                      frame_area, growing_axis, insert_placement, match_objects, maximize_object,
-                      move, new_barcode, object_rect, objects_outside, outside_indices,
+from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, change_label, exact_rect,
+                      fill_anchored, frame_area, growing_axis, insert_placement, match_objects,
+                      maximize_object, move, new_barcode, object_rect, objects_outside, outside_indices,
                       printable_area, proportional, reorder, resize, rotate, set_frame, to_grid)
 from ..printer import DEFAULT_MODEL, cut_interval, to_print_mode
 from ..render import (Renderer, RenderedObject, font_warnings, render_document,
@@ -593,6 +593,7 @@ class MainWindow(QMainWindow):
         red = get_label(self.doc.label_id).two_color and capabilities(self.model).two_color
         self.panel("layout").set_red_available(red)
         self.panel("barcode").red_available = red
+        self.panel("barcode").module.set_dpi(get_label(self.doc.label_id).dpi)
         self._update_frame()
         self.panel("barcode").update_check()        # Serie: Prüfhinweis zur Vorschau-Zeile
         self.edit_session.update_marks()            # Schreibmarke zum neuen Zeilensatz
@@ -1540,7 +1541,7 @@ class MainWindow(QMainWindow):
         if label in {lbl.id for lbl in labels_for_model(self.model)}:
             return
         if self.files.may_follow_roll() and not self.files.modified():
-            self.doc.label_id = self.files.fitting_label(label)
+            change_label(self.doc, self.files.fitting_label(label))
             self.panel("paper").refresh()
             self.history.reset(self.doc)            # unberührt: kein Schritt zurück zum Unpassenden
             self.files.mark_unchanged()
@@ -1647,8 +1648,8 @@ class MainWindow(QMainWindow):
             editing = self.edit_session.active
             if editing:     # Stand vor der Bearbeitung mit neuer Rolle: eigener Schritt davor
                 before = self.history.current()
-                before.label_id = label_id
-            self.doc.label_id = label_id
+                change_label(before, label_id)
+            change_label(self.doc, label_id)
             self.panel("paper").refresh()
             self.schedule_render()
             if editing:
diff --git a/src/labelwerk/gui/panels/barcode.py b/src/labelwerk/gui/panels/barcode.py
index 49428bf..467c689 100644
--- a/src/labelwerk/gui/panels/barcode.py
+++ b/src/labelwerk/gui/panels/barcode.py
@@ -19,7 +19,7 @@ from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, Q
                                QLineEdit, QPushButton, QToolButton, QWidget)
 
 from ... import barcodes, series
-from ...document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, MAX_MODULE, BarcodeObject,
+from ...document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, BarcodeObject,
                          Document)
 from ...labels import DPI
 from ...layout import Rect
@@ -30,7 +30,6 @@ from .position import PositionSection
 
 HINT = "Barcode oder QR-Code einfügen – Art wählen, Inhalt eintippen"
 LEVELS = (("L", "L – 7 %"), ("M", "M – 15 %"), ("Q", "Q – 25 %"), ("H", "H – 30 %"))
-MM_PER_DOT = 25.4 / DPI
 _NUMBER = re.compile(r"\d*[.,]?\d*")
 _ROTATE = (("rotate_left", "object.rotate_left", "rotate-left"),     # (Attribut, Aktion, Symbol)
            ("rotate_right", "object.rotate_right", "rotate-right"))
@@ -46,11 +45,19 @@ class ModuleSpin(SpinBox):
 
     def __init__(self, parent=None):
         super().__init__(parent)
-        self.setRange(1, MAX_MODULE)
+        self.dpi = DPI                  # Auflösung des Etiketts: ein Punkt sind 25,4/dpi mm
+        self.setRange(1, barcodes.max_module(DPI))
         self.setSuffix(" mm")
 
+    def set_dpi(self, dpi: int) -> None:
+        """Auflösung gewechselt: dieselbe Punktzahl zeigt eine andere Breite in mm."""
+        if dpi != self.dpi:
+            self.dpi = dpi
+            self.setMaximum(max(barcodes.max_module(dpi), self.value()))
+            self.lineEdit().setText(self.textFromValue(self.value()) + self.suffix())
+
     def textFromValue(self, value: int) -> str:
-        return f"{value * MM_PER_DOT:.2f}"
+        return f"{value * 25.4 / self.dpi:.2f}"
 
     def _dots(self, text: str) -> int | None:
         """Getippte mm → Druckpunkte; None, wenn (noch) keine gültige Zahl."""
@@ -58,20 +65,20 @@ class ModuleSpin(SpinBox):
         if not _NUMBER.fullmatch(core) or core in ("", "."):
             return None
         mm = float(core)
-        return round(mm / MM_PER_DOT) if math.isfinite(mm) else None
+        return round(mm * self.dpi / 25.4) if math.isfinite(mm) else None
 
     def valueFromText(self, text: str) -> int:
         dots = self._dots(text)
-        return self.value() if dots is None else min(max(dots, 1), MAX_MODULE)
+        return self.value() if dots is None else min(max(dots, 1), self.maximum())
 
     def validate(self, text: str, pos: int):
-        """Nur Ziffern mit einem Komma/Punkt; außerhalb 1–``MAX_MODULE`` Punkte unfertig (wird
+        """Nur Ziffern mit einem Komma/Punkt; außerhalb 1–``maximum()`` Punkte unfertig (wird
         nicht übernommen)."""
         core = text.removesuffix(self.suffix()).strip()
         if not _NUMBER.fullmatch(core.replace(",", ".")):
             return QValidator.State.Invalid, text, pos
         dots = self._dots(text)
-        if dots is None or not 1 <= dots <= MAX_MODULE:
+        if dots is None or not 1 <= dots <= self.maximum():
             return QValidator.State.Intermediate, text, pos
         return QValidator.State.Acceptable, text, pos
 
@@ -249,7 +256,8 @@ class BarcodePanel(Panel):
         try:
             kind = self.chosen_kind()
             obj = self.obj if selected else BarcodeObject(
-                kind=kind, data=barcodes.SAMPLES[kind], module=barcodes.INSERT_MODULE.get(kind, 3))
+                kind=kind, data=barcodes.SAMPLES[kind],
+                module=barcodes.insert_module(kind, self.module.dpi))
             if selected:
                 self.kind.setCurrentIndex(self.kind.findData(obj.kind))
             if self.data.text() != obj.data:
@@ -285,7 +293,7 @@ class BarcodePanel(Panel):
         if self.fill_preview is not None and series.placeholders(Document(objects=[obj])):
             obj = self.fill_preview(obj)
         try:
-            barcodes.size(obj)
+            barcodes.size(obj, self.module.dpi)
             code = barcodes.check(obj)
         except barcodes.BarcodeError as e:
             self._set_check(str(e))
@@ -297,7 +305,7 @@ class BarcodePanel(Panel):
         side = "ringsum" if obj.kind == "qr" else "links und rechts je"
         red = (" · Rot lesen viele Scanner schlecht" if obj.color == "red" and self.red_available
                else "")
-        self.quiet.setText(f"Ruhezone: {side} {_mm(barcodes.quiet_mm(obj))} mm frei lassen{red}")
+        self.quiet.setText(f"Ruhezone: {side} {_mm(barcodes.quiet_mm(obj, self.module.dpi))} mm frei lassen{red}")
 
     def _set_check(self, text: str) -> None:
         self.check.setText(text)
@@ -338,7 +346,7 @@ class BarcodePanel(Panel):
         data = barcodes.SAMPLES[kind] if obj.data == barcodes.SAMPLES[obj.kind] else obj.data
         module = obj.module
         if (kind == "qr") != (obj.kind == "qr"):
-            module = barcodes.INSERT_MODULE.get(kind, 3)
+            module = barcodes.insert_module(kind, self.module.dpi)
         return replace(obj, kind=kind, data=data, module=module)
 
     def _data_edited(self, text: str) -> None:
diff --git a/src/labelwerk/gui/panels/paper.py b/src/labelwerk/gui/panels/paper.py
index bb4deea..4e66795 100644
--- a/src/labelwerk/gui/panels/paper.py
+++ b/src/labelwerk/gui/panels/paper.py
@@ -8,8 +8,9 @@ from PySide6.QtGui import QIcon, QImage, QPixmap
 from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
                                QLabel, QPushButton, QRadioButton, QWidget)
 
+from ... import layout
 from ...document import FRAME_LINE_MM, MAX_FRAME_MM, MAX_MARGIN_MM, Document, Frame
-from ...labels import DPI, get_label, labels_for_model, length_limits
+from ...labels import DPI, get_label, labels_for_model, length_limits, mm_text
 from ...media import Media
 from ...printer import DEFAULT_MODEL
 from ...render import frame_mask
@@ -207,7 +208,7 @@ class PaperPanel(Panel):
         self.length.setRange(round(min_len * 25.4 / DPI, 1), round(max_len * 25.4 / DPI, 1))
 
     def _apply(self) -> None:
-        self.doc.label_id = self.combo.currentData()
+        layout.change_label(self.doc, self.combo.currentData())
         if self._unfit is not None and self._unfit != self.doc.label_id:
             self.combo.blockSignals(True)
             self._fill_labels()                      # Eintrag „passt nicht“ verschwindet
@@ -288,6 +289,7 @@ class PaperPanel(Panel):
         self.length.setEnabled(not self.length_auto.isChecked())
         self.fixed_size.setVisible(not endless)
         w, h = label.size_mm
+        w, h = mm_text(w), mm_text(h)
         self.fixed_size.setText(f"Ø {w} mm · rund" if label.shape == "round"
                                 else f"{w} × {h} mm · gestanzt")
         self._update_frame_widgets()
diff --git a/src/labelwerk/gui/text_edit_mode.py b/src/labelwerk/gui/text_edit_mode.py
index d07efc2..9de531b 100644
--- a/src/labelwerk/gui/text_edit_mode.py
+++ b/src/labelwerk/gui/text_edit_mode.py
@@ -24,7 +24,7 @@ from PySide6.QtGui import QGuiApplication, QKeySequence, QTextCursor, QTextDocum
 from PySide6.QtWidgets import QAbstractButton, QApplication
 
 from .. import layout
-from ..render import PT, RenderedObject, TextLayout, from_utf16, to_utf16
+from ..render import RenderedObject, TextLayout, from_utf16, to_utf16
 
 _VERTICAL = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}
 _TABS = (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
@@ -264,7 +264,7 @@ class TextEditSession(QObject):
             box = _label_rect(rendered, rotation, left, lines[0].top, right - left,
                               bottom - lines[0].top)
             return box.united(QRectF(rendered.x, rendered.y, rendered.w, rendered.h))
-        width = rendered.base_pt * PT / 2
+        width = rendered.base_pt * rendered.dpi / 72 / 2
         obj = self._window.doc.objects[self.index]
         align = obj.paragraphs[0].align if obj.paragraphs else "left"
         left = x - {"center": width / 2, "right": width}.get(align, 0.0)
diff --git a/src/labelwerk/labels.py b/src/labelwerk/labels.py
index cc50d88..e0a31fe 100644
--- a/src/labelwerk/labels.py
+++ b/src/labelwerk/labels.py
@@ -1,6 +1,8 @@
-"""Etikettentypen für Brother-QL-Drucker (Daten aus brother_ql)."""
+"""Etikettentypen: Brother-QL (Daten aus brother_ql, 300 dpi) und Etiketten anderer Drucker als
+IDs mit Größe und Auflösung („54x25mm@300“ – ohne angeschlossenen Drucker lesbar)."""
 from __future__ import annotations
 
+import re
 from dataclasses import dataclass
 
 from brother_ql.labels import Color, FormFactor, LabelsManager
@@ -8,12 +10,15 @@ from brother_ql.labels import Color, FormFactor, LabelsManager
 from .printers import capabilities
 
 DPI = 300  # Druckauflösung der QL-Drucker
+DPI_RANGE = (100, 600)       # Auflösungen anderer Drucker
+SIZE_MM = (5.0, 300.0)       # Kanten fester Etiketten anderer Drucker
+_SIZED = re.compile(r"(\d{1,3}(?:\.\d)?)x(\d{1,3}(?:\.\d)?)mm@(\d{2,3})")
 
 
 @dataclass(frozen=True)
 class Label:
     id: str
-    width: int              # druckbare Punkte quer zum Band (300 dpi)
+    width: int              # druckbare Punkte quer zum Band (bei ``dpi``)
     height: int | None      # None = Endlosband
     tape_mm: int
     description: str
@@ -22,6 +27,7 @@ class Label:
     total_width: int        # physische Breite in Punkten (bedruckbarer Bereich liegt mittig)
     total_height: int | None  # physische Höhe in Punkten; None = Endlosband
     two_color: bool = False   # Rot/Schwarz (DK-22251, „62red“)
+    dpi: int = DPI            # Druckauflösung (Brother 300; andere aus der ID)
 
 
 def _convert(raw) -> Label:
@@ -43,7 +49,38 @@ def _all_raw():
     return list(LabelsManager().iter_elements())
 
 
+def sized_id(w_mm: float, h_mm: float, dpi: int) -> str:
+    """ID eines festen Etiketts anderer Drucker: „54x25mm@300“ (mm auf 0,1)."""
+    return f"{_mm(w_mm)}x{_mm(h_mm)}mm@{round(dpi)}"
+
+
+def _mm(value: float) -> str:
+    return f"{round(value, 1):g}"
+
+
+def mm_text(value: float) -> str:
+    """Maß in mm zum Anzeigen: „62“, „101,6“."""
+    return _mm(value).replace(".", ",")
+
+
+def sized_label(label_id: str) -> Label | None:
+    """Etikett zu einer ID „BxHmm@dpi“ (fest, ganz bedruckbar), sonst None."""
+    m = _SIZED.fullmatch(label_id) if isinstance(label_id, str) else None
+    if m is None:
+        return None
+    w, h, dpi = float(m[1]), float(m[2]), int(m[3])
+    if not (SIZE_MM[0] <= w <= SIZE_MM[1] and SIZE_MM[0] <= h <= SIZE_MM[1]
+            and DPI_RANGE[0] <= dpi <= DPI_RANGE[1]) or label_id != sized_id(w, h, dpi):
+        return None                          # auch „057x32mm@203“: nur eine Schreibweise je Etikett
+    width, height = round(w * dpi / 25.4), round(h * dpi / 25.4)
+    text = f"{mm_text(w)} × {mm_text(h)} mm · {dpi} dpi"
+    return Label(label_id, width, height, round(w), text, "die_cut", (w, h), width, height,
+                 False, dpi)
+
+
 def get_label(label_id: str) -> Label:
+    if (sized := sized_label(label_id)) is not None:
+        return sized
     for raw in _all_raw():
         if raw.identifier == label_id:
             return _convert(raw)
@@ -66,11 +103,12 @@ def labels_for_model(model: str) -> list[Label]:
     return result
 
 
-def format_mm(dots: int) -> str:
-    """Punkte (300 dpi) als mm-Angabe mit Dezimalkomma, z. B. "58,9"."""
-    return f"{dots * 25.4 / DPI:.1f}".replace(".", ",")
+def format_mm(dots: int, dpi: int = DPI) -> str:
+    """Druckpunkte als mm-Angabe mit Dezimalkomma, z. B. "58,9"."""
+    return f"{dots * 25.4 / dpi:.1f}".replace(".", ",")
 
 
 def length_limits(model: str) -> tuple[int, int]:
-    """Erlaubte Etikettlänge (Endlosband) in Punkten, z. B. (150, 11811) für den QL-600."""
+    """Erlaubte Etikettlänge (Endlosband) in Punkten, z. B. (150, 11811) für den QL-600 – bei
+    300 dpi: Endlosband gibt es nur bei Brother (andere Drucker haben feste Etiketten)."""
     return capabilities(model).length_limits
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index dee15de..9756c6e 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -16,7 +16,7 @@ import math
 from dataclasses import dataclass, field, replace
 
 from . import barcodes
-from .document import (BARCODE_MM, MAX_MODULE, MAX_PT, MIN_PT, ROTATIONS, BarcodeObject, Document,
+from .document import (BARCODE_MM, MAX_PT, MIN_PT, ROTATIONS, BarcodeObject, Document,
                        ImageObject, TextObject)
 from .labels import DPI, get_label, length_limits
 from .render import (PT, REF_PT, RenderedObject, frame_box, span_dots, label_margins, label_size,
@@ -29,8 +29,24 @@ _DECIMALS = 3              # Positionen/Rahmen im Modell: auf 1/1000 mm
 GRID_MM = 0.1              # Raster der Positionsfelder: Ziehen/Skalieren endet darauf
 
 
-def _mm(dots: float) -> float:
-    return dots * 25.4 / DPI
+def _mm(dots: float, dpi: int = DPI) -> float:
+    return dots * 25.4 / dpi
+
+
+def change_label(doc: Document, label_id: str) -> None:
+    """Anderes Etikett für ``doc`` (wird geändert). Hat es eine andere Auflösung, behalten Barcodes
+    ihre Breite in mm: Modulbreite in den Punkten des neuen Druckers (ganze Punkte, 1–``max_module``)."""
+    old, new = _label_dpi(doc), get_label(label_id).dpi
+    doc.label_id = label_id
+    if old == new:
+        return
+    for obj in doc.objects:
+        if isinstance(obj, BarcodeObject) and isinstance(obj.module, int):
+            obj.module = min(max(round(obj.module * new / old), 1), barcodes.max_module(new))
+
+
+def _label_dpi(doc: Document) -> int:
+    return get_label(doc.label_id).dpi
 
 
 @dataclass(frozen=True)
@@ -75,13 +91,15 @@ class Snap:
 # --- Etikett ----------------------------------------------------------------------
 def object_rect(rendered: RenderedObject) -> Rect:
     """Rahmen eines gerenderten Objekts in mm."""
-    return Rect(_mm(rendered.x), _mm(rendered.y), _mm(rendered.w), _mm(rendered.h))
+    dpi = rendered.dpi
+    return Rect(_mm(rendered.x, dpi), _mm(rendered.y, dpi), _mm(rendered.w, dpi),
+                _mm(rendered.h, dpi))
 
 
 def label_rect(doc: Document, model: str = "QL-600") -> Rect:
     """Ganzes Etikett in mm (bei automatischer Länge so lang, wie ``render_document`` es macht)."""
     w, h = label_size(doc, model)
-    return Rect(0.0, 0.0, _mm(w), _mm(h))
+    return Rect(0.0, 0.0, _mm(w, _label_dpi(doc)), _mm(h, _label_dpi(doc)))
 
 
 def growing_axis(doc: Document) -> str | None:
@@ -104,7 +122,8 @@ def printable_area(doc: Document, model: str = "QL-600",
     """
     w, h = size if size is not None else label_size(doc, model)
     mx, my = label_margins(doc, model)
-    return Rect(_mm(mx), _mm(my), _mm(w - 2 * mx), _mm(h - 2 * my))
+    dpi = _label_dpi(doc)
+    return Rect(_mm(mx, dpi), _mm(my, dpi), _mm(w - 2 * mx, dpi), _mm(h - 2 * my, dpi))
 
 
 # --- Einrasten --------------------------------------------------------------------
@@ -224,22 +243,23 @@ def _text_only(obj: Object) -> None:
         raise TypeError(f"Nur für Text-Objekte, nicht für {type(obj).__name__}.")
 
 
-def place(obj: Object, rect: Rect) -> Object:
+def place(obj: Object, rect: Rect, dpi: int = DPI) -> Object:
     """Kopie von ``obj`` an ``rect``; bei festem Rahmen auch Breite/Höhe (ungedreht), bei
     Barcodes Modulbreite und Höhe (``_barcode_frame``)."""
     placed = copy.deepcopy(obj)
     placed.x_mm, placed.y_mm = rect.x, rect.y
     w, h = (rect.h, rect.w) if obj.rotation in (90, 270) else (rect.w, rect.h)
     if isinstance(obj, BarcodeObject):
-        return _barcode_frame(placed, w, h)
+        return _barcode_frame(placed, w, h, dpi=dpi)
     if _framed(obj):
         placed.w_mm, placed.h_mm = w, h
     return placed
 
 
-def _barcode_frame(obj: BarcodeObject, w: float, h: float, down: bool = False) -> BarcodeObject:
+def _barcode_frame(obj: BarcodeObject, w: float, h: float, down: bool = False,
+                   dpi: int = DPI) -> BarcodeObject:
     """``obj`` (wird geändert) für einen Rahmen ``w`` × ``h`` mm (ungedreht): Modulbreite auf
-    ganze Druckpunkte gerundet (``down``: abgerundet – passt sicher hinein), 1–``MAX_MODULE``;
+    ganze Druckpunkte gerundet (``down``: abgerundet – passt sicher hinein), 1–``max_module``;
     Strichcodes: Höhe ``h`` (2–100 mm). QR ist quadratisch: Es zählt das Maß, das sich stärker
     ändert. Lässt sich der Inhalt nicht kodieren, bleibt die Modulbreite."""
     if obj.kind != "qr":
@@ -250,19 +270,19 @@ def _barcode_frame(obj: BarcodeObject, w: float, h: float, down: bool = False) -
     except barcodes.BarcodeError:
         return obj
     if obj.kind == "qr":
-        side = _mm(count * obj.module)
+        side = _mm(count * obj.module, dpi)
         w = w if abs(w - side) >= abs(h - side) else h
-    dots = w * DPI / 25.4 / count
+    dots = w * dpi / 25.4 / count
     module = math.floor(dots + _EPS) if down else round(dots)
-    obj.module = min(max(module, 1), MAX_MODULE)
+    obj.module = min(max(module, 1), barcodes.max_module(dpi))
     return obj
 
 
-def barcode_rect(obj: BarcodeObject) -> Rect | None:
+def barcode_rect(obj: BarcodeObject, dpi: int = DPI) -> Rect | None:
     """Rahmen eines Barcodes in mm (nach dem Drehen) aus Modulbreite und Höhe, wie er gerendert
     wird; None, wenn sich der Inhalt nicht kodieren lässt."""
     try:
-        w = _mm(barcodes.modules(obj) * obj.module)
+        w = _mm(barcodes.modules(obj) * obj.module, dpi)
     except barcodes.BarcodeError:
         return None
     h = w if obj.kind == "qr" else obj.h_mm
@@ -271,14 +291,14 @@ def barcode_rect(obj: BarcodeObject) -> Rect | None:
     return Rect(obj.x_mm, obj.y_mm, w, h)
 
 
-def fix_size(obj: TextObject, base_pt: float) -> TextObject:
+def fix_size(obj: TextObject, base_pt: float, dpi: int = DPI) -> TextObject:
     """Kopie mit der wirksamen Grundgröße ``base_pt`` als fester Schriftgröße, ohne Rahmengröße.
 
     Stücke mit eigener Größe behalten ihr Verhältnis; das Bild bleibt gleich: Jede Größe
     bekommt die kürzeste Dezimalzahl (ab 0,1 pt), die dieselbe Druckgröße ergibt.
     """
     _text_only(obj)
-    base_dots = round(base_pt * PT)
+    base_dots = round(base_pt * dpi / 72)
     fixed = copy.deepcopy(obj)
     fixed.size_pt, fixed.fit = round(base_pt, 1), False   # ergibt wieder base_dots
     for old, new in zip((s for p in obj.paragraphs for s in p.spans),
@@ -303,7 +323,7 @@ def exact_rect(obj: Object, rendered: RenderedObject) -> Rect:
     r = object_rect(rendered)
     x, y = ((obj.x_mm or 0.0, obj.y_mm or 0.0) if obj.positioned else (r.x, r.y))
     w, h = r.w, r.h
-    if isinstance(obj, BarcodeObject) and (own := barcode_rect(obj)) is not None:
+    if isinstance(obj, BarcodeObject) and (own := barcode_rect(obj, rendered.dpi)) is not None:
         w, h = own.w, own.h                     # aus Inhalt und Modul (auch bei veraltetem Bild)
     if obj.positioned and _framed(obj) and obj.w_mm is not None and obj.h_mm is not None:
         w, h = (obj.h_mm, obj.w_mm) if obj.rotation in (90, 270) else (obj.w_mm, obj.h_mm)
@@ -331,7 +351,7 @@ def move(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
     """
     target = _apply_change(obj, rect, rendered)
     if isinstance(obj, TextObject) and (obj.size_pt is None or (obj.fit and not obj.positioned)):
-        obj = fix_size(obj, rendered.base_pt)
+        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
     moved = copy.deepcopy(obj)
     moved.x_mm, moved.y_mm = target.x, target.y
     return moved
@@ -345,8 +365,8 @@ def set_frame(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
     feste Schriftgröße.
     """
     if _needs_size(obj):
-        obj = fix_size(obj, rendered.base_pt)
-    return place(obj, rect)
+        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
+    return place(obj, rect, rendered.dpi)
 
 
 def resize(obj: Object, rect: Rect, rendered: RenderedObject, handle: str) -> Object:
@@ -361,24 +381,26 @@ def resize(obj: Object, rect: Rect, rendered: RenderedObject, handle: str) -> Ob
     corner = len(handle) == 2
     target = _apply_change(obj, rect, rendered)
     if isinstance(obj, BarcodeObject):
-        return _resize_barcode(obj, target, exact_rect(obj, rendered), handle)
+        return _resize_barcode(obj, target, exact_rect(obj, rendered), handle, rendered.dpi)
     if isinstance(obj, ImageObject):
         if obj.keep_ratio:
             target = _rounded(keep_aspect(exact_rect(obj, rendered), target, handle))
-        return place(obj, target)
+        return place(obj, target, rendered.dpi)
     if obj.fit:
-        return place(obj, target)
+        return place(obj, target, rendered.dpi)
     if corner:
         old = object_rect(rendered)
         factor = ((rect.w * rect.h) / (old.w * old.h)) ** 0.5 if old.w and old.h else 1.0
-        return place(scale_text(obj, factor, base_pt=rendered.base_pt), target)
+        return place(scale_text(obj, factor, base_pt=rendered.base_pt), target, rendered.dpi)
     # feste Rahmengröße braucht eine feste Schrift: sonst ginge der Rahmen beim Verschieben verloren
-    framed = fix_size(obj, rendered.base_pt) if obj.size_pt is None else copy.deepcopy(obj)
+    framed = (fix_size(obj, rendered.base_pt, rendered.dpi) if obj.size_pt is None
+              else copy.deepcopy(obj))
     framed.fit = True
-    return place(framed, target)
+    return place(framed, target, rendered.dpi)
 
 
-def _resize_barcode(obj: BarcodeObject, target: Rect, old: Rect, handle: str) -> BarcodeObject:
+def _resize_barcode(obj: BarcodeObject, target: Rect, old: Rect, handle: str,
+                    dpi: int = DPI) -> BarcodeObject:
     """Barcode nach Ziehen am Anfasser: QR hält das Quadrat (``keep_aspect``); bei Strichcodes
     ändert das Maß quer zu den Strichen die Modulbreite, das andere die Höhe. Nach dem Einrasten
     bleibt, was der Anfasser festhält (gegenüberliegende Kante, sonst die Mitte)."""
@@ -389,8 +411,8 @@ def _resize_barcode(obj: BarcodeObject, target: Rect, old: Rect, handle: str) ->
     w, h = (target.h, target.w) if turned else (target.w, target.h)
     ow, oh = (old.h, old.w) if turned else (old.w, old.h)
     sized = _barcode_frame(copy.deepcopy(obj), w if (along if turned else across) else ow,
-                           h if (across if turned else along) else oh)
-    shown = barcode_rect(sized) or target
+                           h if (across if turned else along) else oh, dpi=dpi)
+    shown = barcode_rect(sized, dpi) or target
     x = (target.right - shown.w if "l" in handle else target.x if "r" in handle
          else target.cx - shown.w / 2)
     y = (target.bottom - shown.h if "t" in handle else target.y if "b" in handle
@@ -491,8 +513,9 @@ def new_barcode(doc: Document, model: str, area: Rect, kind: str,
     ein Bild (``insert_placement``: mittig in ``area``, auf einem Endlosband hinter ``others``).
     Passt er nicht, wird bei Strichcodes zuerst nur die Höhe kleiner; die Modulbreite schrumpft
     erst, wenn er auch gedreht nicht hineinpasst (``rotate``)."""
+    dpi = _label_dpi(doc)
     obj = BarcodeObject(kind=kind, data=barcodes.SAMPLES[kind],
-                        module=barcodes.INSERT_MODULE.get(kind, 3))
+                        module=barcodes.insert_module(kind, dpi))
     count = barcodes.modules(obj)
     limit_w, limit_h = _insert_limits(doc, model, area)
     best = None                                       # (passt, Modul, Drehung, Höhe)
@@ -500,7 +523,7 @@ def new_barcode(doc: Document, model: str, area: Rect, kind: str,
         w, h = (limit_w, limit_h) if turn == 0 else (limit_h, limit_w)   # ungedreht
         if kind == "qr":
             w = h = min(w, h)
-        module = min(obj.module, math.floor(w * DPI / 25.4 / count + _EPS))
+        module = min(obj.module, math.floor(w * dpi / 25.4 / count + _EPS))
         fits = module >= 1 and (kind == "qr" or h >= BARCODE_MM[0])
         if best is None or (fits, module) > best[:2]:  # gleich gut: ungedreht
             best = (fits, module, turn, h)
@@ -508,7 +531,7 @@ def new_barcode(doc: Document, model: str, area: Rect, kind: str,
     obj.module = max(1, module)
     if kind != "qr":
         obj.h_mm = math.floor(min(max(h, BARCODE_MM[0]), obj.h_mm) * 1000 + _EPS) / 1000
-    shown = barcode_rect(obj)
+    shown = barcode_rect(obj, dpi)
     rect, _, _ = insert_placement(doc, model, area, (shown.w, shown.h), others=others,
                                   rotate=False)
     obj.x_mm = round(rect.cx - shown.w / 2, _DECIMALS)
@@ -527,7 +550,7 @@ def _insert_limits(doc: Document, model: str, area: Rect) -> tuple[float, float]
     if grow is None:
         return area.w, area.h
     mx, my = label_margins(doc, model)
-    longest = _mm(length_limits(model)[1] - 2 * (mx if grow == "x" else my))
+    longest = _mm(length_limits(model)[1] - 2 * (mx if grow == "x" else my), _label_dpi(doc))
     return (longest, area.h) if grow == "x" else (area.w, longest)
 
 
@@ -698,9 +721,9 @@ def match_objects(objs: list[Object], rendered: list[RenderedObject],
         factor = {"same": (fx * fy) ** 0.5, "width": fx, "height": fy}[mode]
         if not isinstance(obj, TextObject):
             result.append(place(obj, _rounded(Rect(old.x, old.y, old.w * factor,
-                                                   old.h * factor))))
+                                                   old.h * factor)), r.dpi))
         else:
-            result.append(place(scale_text(obj, factor, base_pt=r.base_pt), _rounded(old)))
+            result.append(place(scale_text(obj, factor, base_pt=r.base_pt), _rounded(old), r.dpi))
     return result
 
 
@@ -714,7 +737,7 @@ def maximize_object(obj: Object, rendered: RenderedObject, area: Rect, doc: Docu
     """
     grow = growing_axis(doc)
     if isinstance(obj, BarcodeObject):
-        return _maximize_barcode(obj, exact_rect(obj, rendered), area, grow)
+        return _maximize_barcode(obj, exact_rect(obj, rendered), area, grow, rendered.dpi)
     if _framed(obj):
         return set_frame(obj, _rounded(maximize(exact_rect(obj, rendered), area, grow)),
                          rendered)
@@ -746,8 +769,8 @@ def maximize_object(obj: Object, rendered: RenderedObject, area: Rect, doc: Docu
                                        size.w, size.h)))
 
 
-def _maximize_barcode(obj: BarcodeObject, old: Rect, area: Rect, grow: str | None
-                      ) -> BarcodeObject:
+def _maximize_barcode(obj: BarcodeObject, old: Rect, area: Rect, grow: str | None,
+                      dpi: int = DPI) -> BarcodeObject:
     """Barcode so groß wie möglich mittig in ``area``: größte Modulbreite, die hineinpasst
     (abgerundet); Strichcodes füllen die Höhe für sich. In der mitwachsenden Achse begrenzt das
     Etikett nicht – dort bleibt der Anfang (und bei Strichcodes das Maß). Passt nicht einmal
@@ -760,14 +783,14 @@ def _maximize_barcode(obj: BarcodeObject, old: Rect, area: Rect, grow: str | Non
         count = barcodes.modules(obj)
     except barcodes.BarcodeError:
         return copy.deepcopy(obj)
-    module = math.floor((min(w, h) if qr else w) * DPI / 25.4 / count + _EPS)
+    module = math.floor((min(w, h) if qr else w) * dpi / 25.4 / count + _EPS)
     if module < 1:
         return copy.deepcopy(obj)
     sized = copy.deepcopy(obj)
-    sized.module = min(module, MAX_MODULE)
+    sized.module = min(module, barcodes.max_module(dpi))
     if not qr:
         sized.h_mm = math.floor(min(max(h, BARCODE_MM[0]), BARCODE_MM[1]) * 1000 + _EPS) / 1000
-    shown = barcode_rect(sized)
+    shown = barcode_rect(sized, dpi)
     sized.x_mm = round(old.x if grow == "x" else area.cx - shown.w / 2, _DECIMALS)
     sized.y_mm = round(old.y if grow == "y" else area.cy - shown.h / 2, _DECIMALS)
     return sized
@@ -784,11 +807,11 @@ def rotate(obj: Object, rendered: RenderedObject, degrees: int) -> Object:
     """
     old = exact_rect(obj, rendered)
     if _needs_size(obj):
-        obj = fix_size(obj, rendered.base_pt)
+        obj = fix_size(obj, rendered.base_pt, rendered.dpi)
     turned = copy.deepcopy(obj)
     turned.rotation = (obj.rotation + degrees) % 360
     w, h = (old.h, old.w) if degrees % 180 else (old.w, old.h)
-    return place(turned, _rounded(Rect(old.cx - w / 2, old.cy - h / 2, w, h)))
+    return place(turned, _rounded(Rect(old.cx - w / 2, old.cy - h / 2, w, h)), rendered.dpi)
 
 
 def reorder(items: list, indices: list[int], step: int) -> tuple[list, list[int]]:
@@ -903,15 +926,16 @@ def anchor_after_edit(obj: TextObject, old: RenderedObject,
     # Lage des festen Punkts relativ zur linken oberen Ecke des Rahmens (Druckpunkte)
     ox, oy = from_object(old.layout.anchor(align), old, obj.rotation)
     nx, ny = from_object(new.layout.anchor(align), new, obj.rotation)
-    return (round(start.x + _mm(ox - old.x) - _mm(nx - new.x), _DECIMALS),
-            round(start.y + _mm(oy - old.y) - _mm(ny - new.y), _DECIMALS))
+    dpi = old.dpi
+    return (round(start.x + _mm(ox - old.x, dpi) - _mm(nx - new.x, dpi), _DECIMALS),
+            round(start.y + _mm(oy - old.y, dpi) - _mm(ny - new.y, dpi), _DECIMALS))
 
 
 def frame_area(doc: Document, model: str = "QL-600",
                size: tuple[int, int] | None = None) -> Rect | None:
     """Innenraum des Zierrahmens in mm (Ausrichten am Etikett, Einrasten); None ohne Rahmen."""
     box = frame_box(doc, model, size)
-    return None if box is None else Rect(*(_mm(v) for v in box))
+    return None if box is None else Rect(*(_mm(v, _label_dpi(doc)) for v in box))
 
 
 def fill_anchored(doc: Document, columns: list[str], row: list[str], model: str = "QL-600",
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 15000d4..88cb032 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -27,7 +27,7 @@ from .labels import DPI, get_label, length_limits
 from .printers import capabilities
 
 MARGIN = 12            # Punkte, ca. 1 mm
-PT = DPI / 72          # Druckpunkte pro typografischem Punkt
+PT = DPI / 72          # Druckpunkte pro typografischem Punkt bei 300 dpi (Brother); sonst dpi / 72
 REF_PT = 12.0          # Bezugsgröße für automatische Skalierung von Stücken mit eigener Größe
 MIN_DOTS = 8           # kleinste Schrift in Druckpunkten
 _LINE_GAP = 4          # wie Pillow multiline_text
@@ -103,6 +103,7 @@ class RenderedObject:
     image_dy: int = 0
     layout: TextLayout | None = field(default=None, compare=False, repr=False)
     color: str = "black"
+    dpi: int = DPI                     # Auflösung des Etiketts (mm ↔ Druckpunkte)
 
 
 def render_object(obj: TextObject | ImageObject | BarcodeObject, doc: Document,
@@ -293,8 +294,9 @@ class Renderer:
                 except barcodes.BarcodeError as e:
                     if not placeholders:
                         raise
-                    frame = barcodes.placeholder_size(obj)
-                    prepared = Prepared(obj, 0, [], (0, 0, *frame), frame, str(e))
+                    dpi = get_label(doc.label_id).dpi
+                    frame = barcodes.placeholder_size(obj, dpi)
+                    prepared = Prepared(obj, 0, [], (0, 0, *frame), frame, str(e), dpi)
                 entry = _Cached(obj, copy.deepcopy(obj), context, prepared)
             cache[id(obj)] = entry
         self._cache = cache
@@ -345,6 +347,15 @@ class _Sheet:
     frame: Frame | None = None
     round: bool = False        # rundes Etikett: Rahmen ist ein Kreis
     red: bool = False          # Etikett Rot/Schwarz auf einem Zweifarb-Modell: Rot druckt rot
+    dpi: int = DPI             # Auflösung des Etiketts
+
+    def dots(self, mm: float) -> int:
+        return _dots(mm, self.dpi)
+
+    @property
+    def pt(self) -> float:
+        """Druckpunkte je typografischem Punkt."""
+        return self.dpi / 72
 
     def margins(self) -> tuple[int, int]:
         """Ränder (links/rechts, oben/unten) in Leserichtung."""
@@ -360,12 +371,12 @@ class _Sheet:
         if self.round:
             inset = (self.across - _circle_room(self)) // 2
             return inset, inset
-        band = _band(self.frame)
-        inner = band + _dots(self.frame.padding_mm)
+        band = _band(self.frame, self.dpi)
+        inner = band + self.dots(self.frame.padding_mm)
         if self.frame.rounded:          # Ecken des Innenraums bleiben vor den Bögen (auch ohne Abstand)
-            r = _dots(FRAME_RADIUS_MM)  # größter Radius – kleinere Bögen ragen weniger weit
+            r = self.dots(FRAME_RADIUS_MM)  # größter Radius – kleinere Bögen ragen weniger weit
             inner = max(inner, math.ceil(r - (r - band) / math.sqrt(2)) + 1)
-        pad = _dots(self.frame.inset_mm) + inner
+        pad = self.dots(self.frame.inset_mm) + inner
         return mx + pad, my + pad
 
     def room(self, inner: bool = True) -> tuple[int, int]:
@@ -384,21 +395,22 @@ def _sheet(doc: Document, model: str) -> _Sheet:
     label = get_label(doc.label_id)
     min_len, max_len = length_limits(model)
     # Rand ringsum ab Papierkante: der Streifen, den der Drucker dort nicht bedruckt, zählt mit
-    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
+    margin = _dots(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM), label.dpi)
     side = max(0, margin - (label.total_width - label.width) // 2)
     if label.height is not None and label.total_height is not None:
         margin = max(0, margin - (label.total_height - label.height) // 2)
     feed = label.height
     if feed is None and doc.length_mm is not None:
-        feed = min(max(_dots(doc.length_mm), min_len), max_len)
-    side = min(side, max(0, (label.width - 2 * MARGIN) // 2))      # Rand darf nicht alles
-    if feed is not None:                                            # aufbrauchen (quer, feste Länge)
-        margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
+        feed = min(max(_dots(doc.length_mm, label.dpi), min_len), max_len)
+    keep = round(MARGIN * label.dpi / DPI)                          # Rand darf nicht alles
+    side = min(side, max(0, (label.width - 2 * keep) // 2))        # aufbrauchen (quer, feste
+    if feed is not None:                                            # Länge): 1 mm bleibt
+        margin = min(margin, max(0, (feed - 2 * keep) // 2))
     if doc.frame is not None:
         _check_frame(doc.frame)
     return _Sheet(doc.label_id, doc.orientation == "horizontal", label.width, feed, margin, side,
                   min_len, max_len, doc.frame, label.shape == "round",
-                  label.two_color and capabilities(model).two_color)
+                  label.two_color and capabilities(model).two_color, label.dpi)
 
 
 FRAME_TOO_BIG = "Rahmen passt nicht aufs Etikett – Abstand, Strichstärke oder Innenabstand verkleinern"
@@ -411,8 +423,8 @@ def _check_room(sheet: _Sheet) -> None:
         raise ValueError(FRAME_TOO_BIG)
 
 
-def _dots(mm: float) -> int:
-    return round(mm * DPI / 25.4)
+def _dots(mm: float, dpi: int = DPI) -> int:
+    return round(mm * dpi / 25.4)
 
 
 @dataclass
@@ -425,6 +437,7 @@ class Prepared:
     box: tuple[int, int, int, int]
     frame: tuple[int, int] | None      # feste Rahmengröße positionierter Objekte (ungedreht)
     error: str | None = None           # Barcode als Platzhalter (``Renderer``, Arbeitsfläche)
+    dpi: int = DPI                     # Auflösung des Etiketts
 
     def size(self) -> tuple[int, int]:
         """Rahmengröße nach dem Drehen."""
@@ -437,10 +450,10 @@ def _prepare(obj: TextObject | ImageObject | BarcodeObject, sheet: _Sheet) -> Pr
     if obj.color not in COLORS:
         raise ValueError(f"Unbekannte Farbe {obj.color!r} – erlaubt: schwarz, rot (black, red)")
     if isinstance(obj, ImageObject):
-        return _prepare_image(obj)
+        return _prepare_image(obj, sheet.dpi)
     if isinstance(obj, BarcodeObject):
-        frame = barcodes.size(obj)
-        return Prepared(obj, 0, [], (0, 0, *frame), frame)
+        frame = barcodes.size(obj, sheet.dpi)
+        return Prepared(obj, 0, [], (0, 0, *frame), frame, dpi=sheet.dpi)
     for para in obj.paragraphs:
         if para.align not in ALIGNMENTS:
             raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
@@ -456,22 +469,22 @@ def _prepare(obj: TextObject | ImageObject | BarcodeObject, sheet: _Sheet) -> Pr
         # Bandlaufrichtung unbegrenzt – der Text wird nur quer eingepasst
         along = sheet.horizontal != (obj.rotation in (90, 270))   # Objektbreite längs zum Band
         open_w, open_h = (sheet.feed is None and along), (sheet.feed is None and not along)
-        frame_w = _dots(obj.w_mm) if obj.w_mm is not None else None if open_w else max_w
-        frame_h = _dots(obj.h_mm) if obj.h_mm is not None else None if open_h else max_h
+        frame_w = sheet.dots(obj.w_mm) if obj.w_mm is not None else None if open_w else max_w
+        frame_h = sheet.dots(obj.h_mm) if obj.h_mm is not None else None if open_h else max_h
         if obj.w_mm is not None or obj.h_mm is not None:
-            auto_start = round(MAX_PT * PT)    # eigener Rahmen: Text füllt ihn aus
+            auto_start = round(MAX_PT * sheet.pt)    # eigener Rahmen: Text füllt ihn aus
         base = _fit(obj, auto_start, _UNBOUNDED if frame_w is None else frame_w,
-                    _UNBOUNDED if frame_h is None else frame_h, sheet.label_id)
+                    _UNBOUNDED if frame_h is None else frame_h, sheet.label_id, sheet.dpi)
         lines = _shape(obj, base)
         l, t, r, b = box = _block_box(lines)
         frame = (r - l if frame_w is None else frame_w, b - t if frame_h is None else frame_h)
-        return Prepared(obj, base, lines, box, frame)
+        return Prepared(obj, base, lines, box, frame, dpi=sheet.dpi)
     if obj.positioned and not obj.auto:
-        base = round(obj.size_pt * PT)         # darf hinausragen – kein TextTooLarge
+        base = round(obj.size_pt * sheet.pt)   # darf hinausragen – kein TextTooLarge
     else:
-        base = _fit(obj, auto_start, max_w, max_h, sheet.label_id)
+        base = _fit(obj, auto_start, max_w, max_h, sheet.label_id, sheet.dpi)
     lines = _shape(obj, base)
-    return Prepared(obj, base, lines, _block_box(lines), None)
+    return Prepared(obj, base, lines, _block_box(lines), None, dpi=sheet.dpi)
 
 
 def _label_size(sheet: _Sheet, preps: list[Prepared]) -> tuple[int, int]:
@@ -488,7 +501,7 @@ def _label_size(sheet: _Sheet, preps: list[Prepared]) -> tuple[int, int]:
             size = w if sheet.horizontal else h
             if prep.obj.positioned:
                 start = prep.obj.x_mm if sheet.horizontal else prep.obj.y_mm
-                needed = max(needed, _dots(start or 0) + size + along)
+                needed = max(needed, sheet.dots(start or 0) + size + along)
             else:
                 needed = max(needed, size + 2 * along)
         if sheet.frame is not None:            # im Rahmen bleibt immer Platz (kein Innenraum ≤ 0)
@@ -517,7 +530,7 @@ def _place(prep: Prepared, sheet: _Sheet, width: int, height: int
             frame = (0, 0, *prep.frame)
             x0, y0, lines = _align(obj, prep.base, lines, prep.box, 0, *prep.frame)
         area = frame[2:]
-        origin = (_dots(obj.x_mm or 0), _dots(obj.y_mm or 0))
+        origin = (sheet.dots(obj.x_mm or 0), sheet.dots(obj.y_mm or 0))
     else:                                      # mittig auf dem Etikett wie bisher
         area = (height, width) if turned else (width, height)
         # Innenrand der Textzeilen: Rand (mit Rahmen: Innenraum) in Richtung der Zeilen
@@ -556,9 +569,10 @@ def _finish_shape(prep: Prepared, sheet: _Sheet, width: int, height: int) -> Ren
         image = image.transpose(_TRANSPOSE[obj.rotation])
         frame = _turn(frame, area, obj.rotation)
         picture = _turn(picture, area, obj.rotation)
-    base_pt = obj.size_pt if not obj.auto else prep.base / PT
+    base_pt = obj.size_pt if not obj.auto else prep.base / sheet.pt
     return RenderedObject(image, origin[0] + frame[0], origin[1] + frame[1], frame[2], frame[3],
-                          base_pt, picture[0] - frame[0], picture[1] - frame[1], text)
+                          base_pt, picture[0] - frame[0], picture[1] - frame[1], text,
+                          dpi=sheet.dpi)
 
 
 _TRANSPOSE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
@@ -621,7 +635,7 @@ def _paint(lines: list, x0: int, y0: int, width: int, height: int,
 
 
 # --- Bild-Objekte -------------------------------------------------------------------
-def _prepare_image(obj: ImageObject) -> Prepared:
+def _prepare_image(obj: ImageObject, dpi: int = DPI) -> Prepared:
     """Bild-Objekt prüfen und messen: Rahmen in Druckpunkten (ungedreht) aus ``w_mm``/``h_mm``."""
     if obj.rotation not in ROTATIONS:
         raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
@@ -629,8 +643,8 @@ def _prepare_image(obj: ImageObject) -> Prepared:
     if not (obj.w_mm > 0 and obj.h_mm > 0):
         raise ValueError(f"Größe des Bilds muss größer als 0 sein, nicht "
                          f"{obj.w_mm:g} × {obj.h_mm:g} mm.")
-    frame = (max(1, _dots(obj.w_mm)), max(1, _dots(obj.h_mm)))
-    return Prepared(obj, 0, [], (0, 0, *frame), frame)
+    frame = (max(1, _dots(obj.w_mm, dpi)), max(1, _dots(obj.h_mm, dpi)))
+    return Prepared(obj, 0, [], (0, 0, *frame), frame, dpi=dpi)
 
 
 def _finish_image(prep: Prepared) -> RenderedObject:
@@ -653,19 +667,22 @@ def _finish_image(prep: Prepared) -> RenderedObject:
     if obj.rotation:
         image = image.transpose(_TRANSPOSE[obj.rotation])
         frame = _turn(frame, (w, h), obj.rotation)
-    return RenderedObject(image, _dots(obj.x_mm), _dots(obj.y_mm), frame[2], frame[3], 0.0)
+    return RenderedObject(image, _dots(obj.x_mm, prep.dpi), _dots(obj.y_mm, prep.dpi), frame[2],
+                          frame[3], 0.0, dpi=prep.dpi)
 
 
 def _finish_barcode(prep: Prepared) -> RenderedObject:
     """Barcode zeichnen (ganze Druckpunkte, ``barcodes.draw``; mit Fehler den Platzhalter) und
     drehen wie ein Bild."""
     obj = prep.obj
-    image = barcodes.draw(obj) if prep.error is None else barcodes.placeholder(*prep.frame)
+    image = (barcodes.draw(obj, prep.dpi) if prep.error is None
+             else barcodes.placeholder(*prep.frame))
     frame = (0, 0, *image.size)
     if obj.rotation:
         frame = _turn(frame, image.size, obj.rotation)
         image = image.transpose(_TRANSPOSE[obj.rotation])
-    return RenderedObject(image, _dots(obj.x_mm), _dots(obj.y_mm), frame[2], frame[3], 0.0)
+    return RenderedObject(image, _dots(obj.x_mm, prep.dpi), _dots(obj.y_mm, prep.dpi), frame[2],
+                          frame[3], 0.0, dpi=prep.dpi)
 
 
 # Vektorbilder: der Kern rastert nicht selbst (Qt-frei) – die GUI meldet eine Funktion an
@@ -767,13 +784,14 @@ def span_dots(obj: TextObject, span: Span, base: int) -> int:
     return max(1, round(base * span.size_pt / ref))
 
 
-def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str) -> int:
+def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str,
+         dpi: int = DPI) -> int:
     """Grundgröße in Druckpunkten: fest, oder größte passende ≤ auto_start (Halbierung)."""
     def fits(base: int) -> bool:
         l, t, r, b = _block_box(_shape(obj, base, mode="1"))
         return (r - l) <= max_w and (b - t) <= max_h
 
-    start = auto_start if obj.auto else round(obj.size_pt * PT)
+    start = auto_start if obj.auto else round(obj.size_pt * dpi / 72)
     if fits(start):
         return start
     best, lo, hi = None, MIN_DOTS, start - 1
@@ -787,7 +805,7 @@ def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str
         # Meldung in der größten eingestellten Größe – die sieht der Nutzer im Editor
         largest = max((span.size_pt or obj.size_pt for para in obj.paragraphs
                        for span in para.spans), default=obj.size_pt)
-        max_pt = int(best / PT * largest / obj.size_pt) if best else None
+        max_pt = int(best / (dpi / 72) * largest / obj.size_pt) if best else None
         if max_pt is not None and max_pt < MIN_PT:
             max_pt = None                      # kleiner als erlaubt: zählt als „passt nicht“
         raise TextTooLarge(largest, max_pt, label_id)
@@ -1140,14 +1158,14 @@ def _fmt_mm(value: float) -> str:
     return f"{value:g}".replace(".", ",")
 
 
-def _line(frame: Frame) -> int:
+def _line(frame: Frame, dpi: int = DPI) -> int:
     """Strichstärke in Druckpunkten (mindestens 1)."""
-    return max(1, _dots(frame.line_mm))
+    return max(1, _dots(frame.line_mm, dpi))
 
 
-def _band(frame: Frame) -> int:
+def _band(frame: Frame, dpi: int = DPI) -> int:
     """Breite aller Linien zusammen (doppelt: Linie, Lücke, Linie; dick-dünn: 2, 1, 1)."""
-    lw = _line(frame)
+    lw = _line(frame, dpi)
     return {"double": 3 * lw, "thick_thin": 4 * lw}.get(frame.style, lw)
 
 
@@ -1155,7 +1173,7 @@ def _outer(sheet: _Sheet, width: int, height: int) -> tuple[int, int, int, int]:
     """Außenkante des Rahmens (x0, y0, x1, y1; Ende ausschließlich) in Leserichtung; rund:
     das Quadrat um den Kreis."""
     mx, my = sheet.margins()
-    inset = _dots(sheet.frame.inset_mm)
+    inset = sheet.dots(sheet.frame.inset_mm)
     x0, y0, x1, y1 = mx + inset, my + inset, width - mx - inset, height - my - inset
     if sheet.round:
         d = min(x1 - x0, y1 - y0)
@@ -1167,7 +1185,7 @@ def _outer(sheet: _Sheet, width: int, height: int) -> tuple[int, int, int, int]:
 def _circle_room(sheet: _Sheet) -> int:
     """Seite des Quadrats im Kreisrahmen (Innenraum runder Etiketten) in Druckpunkten."""
     x0, _, x1, _ = _outer(sheet, sheet.across, sheet.across)   # runde Etiketten sind quadratisch
-    radius = (x1 - x0) / 2 - _band(sheet.frame) - _dots(sheet.frame.padding_mm)
+    radius = (x1 - x0) / 2 - _band(sheet.frame, sheet.dpi) - sheet.dots(sheet.frame.padding_mm)
     return int(radius * math.sqrt(2)) if radius > 0 else 0
 
 
@@ -1176,11 +1194,11 @@ def _frame_mask(sheet: _Sheet, width: int, height: int) -> Image.Image | None:
     frame = sheet.frame
     if frame is None:
         return None
-    lw = _line(frame)
+    lw = _line(frame, sheet.dpi)
     box = _outer(sheet, width, height)
     w, h = box[2] - box[0], box[3] - box[1]
     style = "single" if sheet.round and frame.style == "corners" else frame.style
-    radius = (min(_dots(FRAME_RADIUS_MM), min(w, h) // 4)
+    radius = (min(sheet.dots(FRAME_RADIUS_MM), min(w, h) // 4)
               if frame.rounded and not sheet.round else 0)
     mask = Image.new("L", (width, height), 0)
     draw = ImageDraw.Draw(mask)
@@ -1204,7 +1222,7 @@ def _frame_mask(sheet: _Sheet, width: int, height: int) -> Image.Image | None:
     else:
         ring(0, lw)
     if style == "corners":
-        leg = min(_dots(FRAME_CORNER_MM), min(w, h) // 4)
+        leg = min(sheet.dots(FRAME_CORNER_MM), min(w, h) // 4)
         if leg < 2 * lw:                     # sonst blieben nur Quadrate (oder nichts)
             raise ValueError(FRAME_TOO_BIG)
         keep = Image.new("L", mask.size, 0)
diff --git a/src/labelwerk/storage.py b/src/labelwerk/storage.py
index 4eef4e9..c93820f 100644
--- a/src/labelwerk/storage.py
+++ b/src/labelwerk/storage.py
@@ -27,7 +27,7 @@ from PIL import Image
 from . import barcodes
 from .document import (ALIGNMENTS, BARCODE_KINDS, BARCODE_MM, COLORS, CUTS, FRAME_LINE_MM,
                        FRAME_STYLES, MAX_BARCODE_DATA, MAX_DIGITS, MAX_FRAME_MM, MAX_MARGIN_MM,
-                       MAX_MODULE, MAX_NUMBER, MAX_POSITION_MM, MAX_SERIES_ROWS, ORIENTATIONS,
+                       MAX_NUMBER, MODULE_LIMIT, MAX_POSITION_MM, MAX_SERIES_ROWS, ORIENTATIONS,
                        QR_LEVELS, ROTATIONS, BarcodeObject, Document, Frame, ImageObject, Numbering,
                        Paragraph, Series, Span, TextObject)
 from .imaging import MAX_PIXELS, MODES
@@ -39,9 +39,8 @@ SUFFIX = ".labelwerk"
 RECENT_FILES = 10
 MAX_FILE_BYTES = 32 * 1024 * 1024     # größere Dateien werden nicht gelesen
 MAX_OBJECTS = 500                     # Objekte je Etikett
-MAX_FRAME_DOTS = 100_000_000          # Summe der Rahmenflächen in Druckpunkten (300 dpi)
+MAX_FRAME_DOTS = 100_000_000          # Summe der Rahmenflächen in Druckpunkten (in Etikett-dpi)
 MAX_BARCODE_TOTAL = 20_000            # Zeichen aller Barcode-Inhalte (Kodieren beim Laden bleibt billig)
-DOTS_PER_MM = 300 / 25.4
 MAX_SIZE_MM = 1_000.0                 # Rahmen, Etikettlänge (QL: höchstens 1 m)
 MAX_SIZE_PT = 1_000.0                 # Schriftgröße (über MAX_PT hinaus, wie scale_text es lässt)
 LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85  "   # gehören zwischen Absätze, nicht in Stücke
@@ -118,7 +117,7 @@ _KINDS = {
     "cut": lambda v: v in CUTS,
     "barcode_kind": lambda v: v in BARCODE_KINDS,
     "barcode_data": lambda v: _text(v) and len(v) <= MAX_BARCODE_DATA,
-    "module": lambda v: _int(v) and 1 <= v <= MAX_MODULE,
+    "module": lambda v: _int(v) and 1 <= v <= MODULE_LIMIT,
     "barcode_mm": lambda v: _num(v) and BARCODE_MM[0] <= v <= BARCODE_MM[1],
     "qr_level": lambda v: v in QR_LEVELS,
     "color": lambda v: v in COLORS,
@@ -370,27 +369,28 @@ def from_dict(data, base: str | Path | None = None) -> Document:
     if total > MAX_BARCODE_TOTAL:
         raise StorageError(f"Etikett zu groß (Barcode-Inhalte zusammen {total} Zeichen, höchstens "
                            f"{MAX_BARCODE_TOTAL})")
-    dots = sum(_dots(o) for o in objects)
+    dpi = get_label(values.get("label_id", Document().label_id)).dpi
+    dots = sum(_dots(o, dpi) for o in objects)
     if dots > MAX_FRAME_DOTS:
         raise StorageError(f"Etikett zu groß (Objekte zusammen {dots / 1e6:.0f} Mio. Druckpunkte, "
                            f"höchstens {MAX_FRAME_DOTS // 1_000_000})")
     return Document(**values, objects=objects)
 
 
-def _dots(obj) -> float:
+def _dots(obj, dpi: int) -> float:
     """Rahmenfläche in Druckpunkten (Grenze „Etikett zu groß“); Barcodes mit ihrer echten Fläche,
     mit Platzhaltern der Serie oder ungültigem Inhalt mit der größtmöglichen (``barcodes.max_size``)
     – was gespeichert wurde, lässt sich wieder öffnen."""
     if isinstance(obj, BarcodeObject):
         from .series import placeholders            # series liest storage – erst hier
-        w, h = barcodes.max_size(obj)
+        w, h = barcodes.max_size(obj, dpi)
         if not placeholders(Document(objects=[obj])):
             try:
-                w, h = barcodes.size(obj)
+                w, h = barcodes.size(obj, dpi)
             except barcodes.BarcodeError:
                 pass
         return w * h
-    return obj.w_mm * obj.h_mm * DOTS_PER_MM ** 2 if obj.w_mm and obj.h_mm else 0
+    return obj.w_mm * obj.h_mm * (dpi / 25.4) ** 2 if obj.w_mm and obj.h_mm else 0
 
 
 def _reject_constant(name: str):
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2377 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/barcodes.py src/labelwerk/cli.py src/labelwerk/document.py src/labelwerk/files.py src/labelwerk/gui/canvas.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/barcode.py src/labelwerk/gui/panels/paper.py src/labelwerk/gui/text_edit_mode.py src/labelwerk/labels.py src/labelwerk/layout.py src/labelwerk/render.py src/labelwerk/storage.py tests/gui/test_gui_label_dpi.py tests/test_barcode_objects.py tests/test_barcode_reading.py tests/test_barcodes.py tests/test_label_dpi.py
git commit -m "Kern: Auflösung je Etikett – Etiketten „BxHmm@dpi“, Rendern, Layout, Barcodes (Maße in mm), Speichergrenzen, Datei-Druck und Arbeitsfläche in der Auflösung des Druckers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: CUPS – Warteschlangen als Drucker, Etiketten aus dem Treiber, Schnitt-Optionen

**Files:**
- Modify: `src/labelwerk/cli.py`
- Create: `src/labelwerk/cups.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/series.py`
- Modify: `src/labelwerk/gui/print_worker.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/labels.py`
- Modify: `src/labelwerk/printer.py`
- Modify: `src/labelwerk/printers.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/conftest.py`
- Modify: `tests/gui/test_gui_barcode.py`
- Modify: `tests/gui/test_gui_cancel.py`
- Create: `tests/gui/test_gui_cups.py`
- Modify: `tests/gui/test_gui_files.py`
- Modify: `tests/gui/test_gui_printers.py`
- Modify: `tests/gui/test_gui_series.py`
- Modify: `tests/test_cli.py`
- Create: `tests/test_cups.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `cups.py` (`queues`, `read_queues`, `queue_info`, `QueueInfo`, `CutOption`, `print_images`, `valid_name`, `forget`, `BACKGROUND`, `PPD_DIR`, `_run`); `printers`: `is_model`, `cups_printers(direct, keep, wait)`, `choose` nie CUPS automatisch, `backend_for` → `cups`; `labels_for_model("cups:NAME")`; `printer.print_image(…, options)`; `settings.printer_options`; CLI `-p cups:NAME`; GUI: `SeriesPanel.set_driver_cuts`, `driver_cut_chosen`, `MainWindow._update_cut_choices`, `PrintWorker(…, options)`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/conftest.py b/tests/conftest.py
index e35f482..f0bfe91 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -15,6 +15,17 @@ def no_real_sysfs(monkeypatch, tmp_path_factory):
     monkeypatch.setattr("labelwerk.printers.SYS_ROOT", str(tmp_path_factory.mktemp("usbmisc")))
 
 
+@pytest.fixture(autouse=True)
+def no_real_cups(monkeypatch, tmp_path_factory):
+    """Kein Test ruft echte CUPS-Befehle (lpstat, lpoptions, lp) oder liest echte PPDs: ohne
+    eigenen Ersatz gibt es keine Warteschlangen."""
+    from labelwerk import cups
+    monkeypatch.setattr(cups, "PPD_DIR", tmp_path_factory.mktemp("ppd"))
+    monkeypatch.setattr(cups, "_run", lambda *args, **kw: "")
+    monkeypatch.setattr(cups, "BACKGROUND", False)
+    cups.forget()                       # Gemerktes aus einem früheren Test gilt nicht
+
+
 @pytest.fixture(autouse=True)
 def no_leftover_rasterizer():
     """Das Hauptfenster meldet die Qt-Raster-Funktion für Vektorbilder an – danach wieder ohne,
diff --git a/tests/gui/test_gui_barcode.py b/tests/gui/test_gui_barcode.py
index 4eacbb0..e40097a 100644
--- a/tests/gui/test_gui_barcode.py
+++ b/tests/gui/test_gui_barcode.py
@@ -257,7 +257,7 @@ def test_series_prints_the_filled_barcode(qtbot, monkeypatch):
     jobs = []
 
     class Fake:
-        def __init__(self, image, label_id, model, cut_every=1, printer=None):
+        def __init__(self, image, label_id, model, cut_every=1, printer=None, options=None):
             jobs.append(image)
             from labelwerk.gui.print_worker import PrintSignals
             self.signals = PrintSignals()
diff --git a/tests/gui/test_gui_cancel.py b/tests/gui/test_gui_cancel.py
index d46e5ea..ce35058 100644
--- a/tests/gui/test_gui_cancel.py
+++ b/tests/gui/test_gui_cancel.py
@@ -13,7 +13,7 @@ class FakeWorker:
     """Druck-Worker ohne Thread und Drucker; merkt sich „Abbrechen“."""
     instances = []
 
-    def __init__(self, image, label_id, model, cut_every=1, printer=None):
+    def __init__(self, image, label_id, model, cut_every=1, printer=None, options=None):
         self.image, self.cancelled = image, False
         self.signals = PrintSignals()
         FakeWorker.instances.append(self)
diff --git a/tests/gui/test_gui_cups.py b/tests/gui/test_gui_cups.py
new file mode 100644
index 0000000..d58c25b
--- /dev/null
+++ b/tests/gui/test_gui_cups.py
@@ -0,0 +1,94 @@
+"""CUPS-Warteschlangen in der GUI: Druckermenü, Etiketten des Treibers, Schnitt-Optionen im Reiter
+SERIE (je Drucker gespeichert), Übergabe an die Warteschlange."""
+import pytest
+
+from labelwerk import cups
+from labelwerk.document import Document, Numbering, Series, TextObject
+from labelwerk.gui import main_window
+from labelwerk.settings import load_settings
+
+from test_gui_printers import QL600, _labels, _window, workers  # noqa: F401  (Fixture)
+
+OPTIONS = ("PageSize/Media Size: *w162h90 w154h64.8\n"
+           "CutMedia/Schneiden: *Off EndOfJob EndOfPage\n")
+
+
+@pytest.fixture
+def queue(monkeypatch):
+    """Warteschlange „Dymo“ (Treiber mit Schnitt-Option) und „Laser“ (ohne)."""
+    def run(*args, **kw):
+        if args[0] == "lpstat":
+            return ("Dymo\nLaser\n" if args[1] == "-e" else
+                    "device for Dymo: usb://DYMO/LabelWriter%20450\n"
+                    "device for Laser: ipp://10.0.0.7/ipp/print\n")
+        if args[0] == "lpoptions":
+            return OPTIONS if args[2] == "Dymo" else "PageSize/Media Size: *w162h90\n"
+        return ""
+    monkeypatch.setattr(cups, "_run", run)
+
+
+def test_queues_appear_in_the_printer_menu(qtbot, monkeypatch, queue):
+    win = _window(qtbot, monkeypatch, [QL600])
+    win._fill_printer_menu()
+    texts = [a.text() for a in win.printer_menu.actions() if a.text()]
+    assert texts[1:4] == ["QL-600 · lp1", "Dymo · CUPS – ungeprüft", "Laser · CUPS – ungeprüft"]
+    assert win.printer.uri == QL600.uri                      # Brother direkt zuerst
+    win.choose_printer("cups:Dymo")
+    assert win.model == "cups:Dymo" and load_settings().printer == "cups:Dymo"
+    assert _labels(win) == ["57.1x31.7mm@300", "54.3x22.9mm@300"]
+    assert win.printer_status.text() == "● Dymo · CUPS · ungeprüft"
+    assert not win.panel("paper").check.isEnabled()          # Medium prüfen nur Brother per USB
+
+
+def test_driver_cut_options_in_the_series_tab(qtbot, monkeypatch, queue):
+    win = _window(qtbot, monkeypatch, [], printer="cups:Dymo")
+    panel = win.panel("series")
+    assert panel.cut.isHidden() and not panel.driver_box.isHidden()
+    combo = panel.driver_cuts["CutMedia"]
+    assert [combo.itemText(i) for i in range(combo.count())] == ["Off", "EndOfJob", "EndOfPage"]
+    assert combo.currentText() == "Off"                      # Standard des Treibers
+    combo.setCurrentIndex(2)
+    assert load_settings().printer_options == {"cups:Dymo": {"CutMedia": "EndOfPage"}}
+    win.choose_printer("cups:Laser")                         # Treiber ohne Schnitt-Option
+    assert panel.driver_box.isHidden() and "Druckertreiber" in panel.no_cutter.text()
+    win.choose_printer("cups:Dymo")
+    assert panel.driver_cuts["CutMedia"].currentText() == "EndOfPage"
+
+
+def test_brother_after_cups_shows_its_cut_choice_again(qtbot, monkeypatch, queue):
+    win = _window(qtbot, monkeypatch, [QL600], printer="cups:Dymo")
+    win.choose_printer(QL600.uri)
+    panel = win.panel("series")
+    assert not panel.cut.isHidden() and panel.driver_box.isHidden() and panel.no_cutter.isHidden()
+
+
+def test_series_goes_to_the_queue_with_the_chosen_options(qtbot, monkeypatch, queue, workers):
+    win = _window(qtbot, monkeypatch, [], printer="cups:Dymo", doc=Document(
+        "57.1x31.7mm@300", objects=[TextObject("X{Nummer}")],
+        series=Series(numbering=Numbering(count=3))),
+        printer_options={"cups:Dymo": {"CutMedia": "EndOfJob"}})
+    win.panel("series").refresh()
+    win.ask_print_count = lambda n: True
+    win.print_label()
+    worker = workers[0]
+    assert (worker.printer, worker.model) == ("cups:Dymo", "cups:Dymo")
+    assert worker.options == {"CutMedia": "EndOfJob"} and len(worker.image) == 3
+    assert worker.image[0].size == (674, 374)
+    assert win.cancel_button.isHidden()                      # ein Auftrag: nichts abzubrechen
+    win._print_done({"outcome": "sent", "did_print": False, "job": "Dymo-4"})
+    assert win.result.text() == "An die Druckwarteschlange übergeben ✓ (Auftrag Dymo-4)"
+
+
+def test_settings_keep_cups_printer_options(qtbot, tmp_path):
+    from labelwerk.gui.settings_dialog import SettingsDialog
+    from labelwerk.settings import Settings
+    dialog = SettingsDialog(Settings(printer_options={"cups:Dymo": {"CutMedia": "Off"}}))
+    qtbot.addWidget(dialog)
+    assert dialog.values().printer_options == {"cups:Dymo": {"CutMedia": "Off"}}
+
+
+def test_queues_are_never_chosen_automatically(qtbot, monkeypatch, queue):
+    win = _window(qtbot, monkeypatch, [], last_model="QL-600")
+    assert win.printer is None and win.model == "QL-600"     # Bürodrucker im Netz bleiben aus
+    assert "cups:Dymo" in [p.uri for p in win.printers]
+    assert load_settings().last_model in ("", "QL-600")
diff --git a/tests/gui/test_gui_files.py b/tests/gui/test_gui_files.py
index 4a2dccb..656b7de 100644
--- a/tests/gui/test_gui_files.py
+++ b/tests/gui/test_gui_files.py
@@ -255,7 +255,7 @@ def test_printing_a_favorite_does_not_touch_the_open_label(qtbot, monkeypatch):
     started = []
 
     class FakeWorker:
-        def __init__(self, image, label_id, model, cut_every=1, printer=None):
+        def __init__(self, image, label_id, model, cut_every=1, printer=None, options=None):
             started.append((image.tobytes(), label_id))
             from labelwerk.gui.print_worker import PrintSignals
             self.signals = PrintSignals()
diff --git a/tests/gui/test_gui_printers.py b/tests/gui/test_gui_printers.py
index a57460e..367d1d7 100644
--- a/tests/gui/test_gui_printers.py
+++ b/tests/gui/test_gui_printers.py
@@ -36,9 +36,9 @@ def _labels(win):
 class FakeWorker:
     instances = []
 
-    def __init__(self, image, label_id, model, cut_every=1, printer=None):
+    def __init__(self, image, label_id, model, cut_every=1, printer=None, options=None):
         self.image, self.label_id, self.model, self.printer = image, label_id, model, printer
-        self.cut_every = cut_every
+        self.cut_every, self.options = cut_every, options
         self.signals = PrintSignals()
         FakeWorker.instances.append(self)
 
@@ -99,7 +99,7 @@ def test_network_printer_from_the_settings(qtbot, monkeypatch, workers):
         {"name": "Büro", "host": "10.0.0.5", "model": "QL-720NW"}])
     assert win.printer.uri == "tcp://10.0.0.5:9100" and win.model == "QL-720NW"
     assert not win.panel("paper").check.isEnabled()                   # Medium prüfen nur USB
-    assert "nur bei Druckern per USB" in win.panel("paper").check.toolTip()
+    assert "nur bei Brother-Druckern per USB" in win.panel("paper").check.toolTip()
     win.panel("text").edit.setPlainText("Hallo")
     win.print_label()
     assert workers[0].printer == "tcp://10.0.0.5:9100" and workers[0].model == "QL-720NW"
diff --git a/tests/gui/test_gui_series.py b/tests/gui/test_gui_series.py
index 5ad4cb7..06f1e97 100644
--- a/tests/gui/test_gui_series.py
+++ b/tests/gui/test_gui_series.py
@@ -47,7 +47,7 @@ class FakeWorker:
     """Druck-Worker, der nur mitschreibt (kein Thread, kein Drucker)."""
     jobs = []
 
-    def __init__(self, image, label_id, model, cut_every=1, printer=None):
+    def __init__(self, image, label_id, model, cut_every=1, printer=None, options=None):
         FakeWorker.jobs.append((image, label_id, cut_every))
         from labelwerk.gui.print_worker import PrintSignals
         self.signals = PrintSignals()
diff --git a/tests/test_cli.py b/tests/test_cli.py
index 2281b82..38d6c25 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -486,3 +486,53 @@ def test_missing_chosen_printer_is_named(monkeypatch, capsys):
     _write_settings(printer="file:///dev/usb/lp1")
     assert main(["print", "Hallo", "-l", "62"]) == 2
     assert "Gewählter Drucker file:///dev/usb/lp1 nicht gefunden" in capsys.readouterr().err
+
+
+# --- CUPS ---------------------------------------------------------------------------------------
+@pytest.fixture
+def cups_queue(monkeypatch):
+    """CUPS nachgebildet: Warteschlange „Buero“ ohne PPD, Aufrufe aufgezeichnet."""
+    from labelwerk import cups
+    calls = []
+
+    def run(*args, **kw):
+        calls.append(args)
+        if args[0] == "lpstat":
+            return "Buero\n" if args[1] == "-e" else "device for Buero: ipp://10.0.0.9/ipp/print\n"
+        return "request id is Buero-7 (1 file(s))\n" if args[0] == "lp" else ""
+    monkeypatch.setattr(cups, "_run", run)
+    return calls
+
+
+def test_print_to_a_cups_queue(cups_queue, capsys):
+    assert main(["print", "Hallo", "-p", "cups:Buero", "-l", "57x32mm@300"]) == 0
+    assert "An CUPS übergeben (Auftrag Buero-7)" in capsys.readouterr().out
+    lp = cups_queue[-1]
+    assert lp[:7] == ("lp", "-d", "Buero", "-o", "media=Custom.57x32mm", "-o", "print-scaling=none")
+
+
+def test_cups_queue_needs_its_labels(cups_queue, capsys):
+    assert main(["print", "Hallo", "-p", "cups:Buero", "-l", "62"]) == 2
+    assert "passt nicht zum cups:Buero" in capsys.readouterr().err
+    assert not any(c[0] == "lp" for c in cups_queue)
+
+
+def test_cups_queues_are_listed(cups_queue, capsys):
+    assert main(["printers"]) == 0
+    out = capsys.readouterr().out
+    assert "Buero · CUPS" in out and "cups:Buero" in out and "cups:NAME (ungeprüft)" in out
+    assert main(["-m", "cups:Buero", "labels"]) == 0
+    assert "57x32mm@300" in capsys.readouterr().out
+
+
+def test_print_file_to_cups_in_its_resolution(cups_queue, tmp_path, monkeypatch):
+    from labelwerk import cups
+    monkeypatch.setattr(cups, "queue_info", lambda name: cups.QueueInfo(
+        (("w162h90", 57.2, 31.8),), 203))
+    sizes = []
+    monkeypatch.setattr(cups, "print_images",
+                        lambda name, images, w, h, dpi, options=None: sizes.extend(i.size for i in images)
+                        or cups.Job("Buero-8"))
+    assert main(["print-file", str(_png(tmp_path, 40, 20)), "-p", "cups:Buero",
+                 "-l", "57.2x31.8mm@203"]) == 0
+    assert sizes == [(457, 254)]
diff --git a/tests/test_cups.py b/tests/test_cups.py
new file mode 100644
index 0000000..bd1b445
--- /dev/null
+++ b/tests/test_cups.py
@@ -0,0 +1,254 @@
+"""Drucker über CUPS: nachgebildete Ausgaben von lpstat/lpoptions/lp und PPDs – kein Test ruft
+echte Befehle (conftest ersetzt ``cups._run``)."""
+import subprocess
+
+import pytest
+from PIL import Image
+
+from labelwerk import cups, printers
+from labelwerk.labels import get_label, labels_for_model
+from labelwerk.printer import PrintError, print_image
+
+REAL_RUN = cups._run                               # vor dem Ersetzen durch conftest
+
+LPSTAT_E = "Dymo_LabelWriter_450\nBuero\nQL600\n"
+LPSTAT_V = ("device for Dymo_LabelWriter_450: usb://DYMO/LabelWriter%20450?serial=01010112345600\n"
+            "device for Buero: ipp://192.168.1.20/ipp/print\n"
+            "device for QL600: usb://Brother/QL-600?serial=000F1Z401370\n")
+LPOPTIONS = ("PageSize/Media Size: w79h252 *w154h64.8 30252_Address 99010 w162h90 Custom.WIDTHxHEIGHT\n"
+             "Resolution/Output Resolution: 136x136dpi *300x300dpi 300x600dpi\n"
+             "DymoCutOptions/Cut: *Cut ChainMarks\n"
+             "PrintQuality/Print Quality: Text *Graphics\n")
+PPD = """*PPD-Adobe: "4.3"
+*ModelName: "DYMO LabelWriter 450"
+*DefaultResolution: 300x300dpi
+*OpenUI *PageSize/Media Size: PickOne
+*PageSize w154h64.8/30252 Address: "<</PageSize[154 64.8]>>setpagedevice"
+*CloseUI: *PageSize
+*PaperDimension w154h64.8/30252 Address: "154 64.8"
+*PaperDimension 99012/99012 Large Address: "102.05 252"
+*PaperDimension Tiny/Too small: "5 5"
+*PaperDimension w288h432/4 x 6: "288 432"
+"""
+
+
+@pytest.fixture
+def fake(monkeypatch, tmp_path):
+    """CUPS nachgebildet: Ausgaben je Befehl, aufgezeichnete Aufrufe."""
+    calls, outputs = [], {"lpstat -e": LPSTAT_E, "lpstat -v": LPSTAT_V,
+                          "lpoptions": LPOPTIONS, "lp": "request id is Dymo_LabelWriter_450-12 (2 file(s))\n"}
+
+    def run(*args, **kw):
+        calls.append(args)
+        key = " ".join(args[:2]) if args[0] == "lpstat" else args[0]
+        out = outputs[key]
+        if isinstance(out, Exception):
+            raise out
+        if args[0] == "lp":                        # PDF: Seitenzahl und Seitengröße in Punkt
+            import pypdfium2
+            pdf = pypdfium2.PdfDocument(args[-1])
+            calls[-1] = args + ((len(pdf), tuple(round(v, 2) for v in pdf[0].get_size())),)
+            pdf.close()
+        return out
+    monkeypatch.setattr(cups, "_run", run)
+    monkeypatch.setattr(cups, "PPD_DIR", tmp_path)
+    cups.forget()
+    return calls, outputs, tmp_path
+
+
+def test_queues_with_devices(fake):
+    calls, _, _ = fake
+    found = cups.queues()
+    assert [q.name for q in found] == ["Dymo_LabelWriter_450", "Buero", "QL600"]
+    assert found[1].device == "ipp://192.168.1.20/ipp/print"
+
+
+def test_queues_are_read_in_the_background(fake, monkeypatch):
+    calls, _, _ = fake
+    monkeypatch.setattr(cups, "BACKGROUND", True)
+    assert cups.queues() == []                         # die Oberfläche wartet nicht
+    cups._queues_thread.join(5)
+    assert [q.name for q in cups.queues()][0] == "Dymo_LabelWriter_450"
+    assert len(calls) == 2                             # gemerkt, nicht jedes Mal gefragt
+
+
+def test_localized_output_is_understood(fake):
+    _, outputs, _ = fake
+    outputs["lpstat -v"] = "Gerät für Buero: ipp://192.168.1.20/ipp/print\n"
+    outputs["lp"] = "Anfrage-ID ist Buero-31 (1 Datei(en))\n"
+    assert cups.queues()[1].device == "ipp://192.168.1.20/ipp/print"
+    label = labels_for_model("cups:Buero")[0]
+    status = print_image(Image.new("1", (label.width, label.height), 1), label.id,
+                         model="cups:Buero", printer="cups:Buero")
+    assert status["job"] == "Buero-31"
+    env = cups._environment()
+    assert env["LC_MESSAGES"] == "C" and "LC_ALL" not in env and "UTF-8" in env.get(
+        "LC_CTYPE", env.get("LANG", "")).upper().replace("UTF8", "UTF-8")
+
+
+def test_without_device_list_the_queues_stay(fake):
+    _, outputs, _ = fake
+    outputs["lpstat -v"] = cups.CupsError("kaputt")
+    assert [q.device for q in cups.queues()] == ["", "", ""]
+
+
+def test_cups_failure_is_not_remembered(fake):
+    _, outputs, _ = fake
+    outputs["lpoptions"] = cups.CupsError("CUPS antwortet nicht (lpoptions)")
+    assert cups.queue_info("Dymo_LabelWriter_450").source == "list"
+    outputs["lpoptions"] = LPOPTIONS
+    assert cups.queue_info("Dymo_LabelWriter_450").source == "options"
+
+
+def test_no_cups_means_no_queues(fake):
+    _, outputs, _ = fake
+    outputs["lpstat -e"] = cups.CupsError("CUPS-Befehle fehlen")
+    assert cups.queues() == []
+
+
+def test_media_from_the_ppd(fake):
+    _, _, folder = fake
+    (folder / "Dymo_LabelWriter_450.ppd").write_text(PPD)
+    info = cups.queue_info("Dymo_LabelWriter_450")
+    assert info.source == "ppd" and info.dpi == 300
+    assert info.media == (("w154h64.8", 54.3, 22.9), ("99012", 36.0, 88.9),
+                          ("w288h432", 101.6, 152.4))          # „Tiny“ zu klein: entfällt
+    assert info.label_ids() == ["54.3x22.9mm@300", "36x88.9mm@300", "101.6x152.4mm@300"]
+    assert info.media_key(36, 88.9) == "99012" and info.media_key(50, 30) == "Custom.50x30mm"
+
+
+def test_media_from_option_names_without_ppd(fake):
+    info = cups.queue_info("Dymo_LabelWriter_450")
+    assert info.source == "options" and info.dpi == 300
+    assert [m[0] for m in info.media] == ["w79h252", "w154h64.8", "w162h90"]   # Namen ohne Maß entfallen
+    assert info.media[0][1:] == (27.9, 88.9)
+
+
+def test_media_list_per_maker_as_last_resort(fake):
+    _, outputs, _ = fake
+    outputs["lpoptions"] = "Resolution/Resolution: *203dpi\n"
+    info = cups.queue_info("Zebra_GK420d")
+    assert info.source == "list" and info.dpi == 203
+    assert ("Custom.102x152mm", 102.0, 152.0) in info.media
+    assert cups.queue_info("Unbekannt").media[0][1:] == (57.0, 32.0)
+
+
+@pytest.mark.parametrize("text, dpi", [("*DefaultResolution: 203dpi", 203),
+                                       ("*DefaultResolution: 300x600dpi", 300),
+                                       ("*DefaultResolution: 4800dpi", 300),     # außerhalb: 300
+                                       ("", 300)])
+def test_resolution_from_the_ppd(text, dpi):
+    assert cups._parse_ppd(text)[0] == dpi
+
+
+def test_cut_options(fake):
+    (cut,) = cups.queue_info("Dymo_LabelWriter_450").cut_options
+    assert (cut.key, cut.title, cut.choices, cut.default) == (
+        "DymoCutOptions", "Cut", ("Cut", "ChainMarks"), "Cut")
+
+
+def test_print_one_job_with_all_labels(fake):
+    calls, _, folder = fake
+    (folder / "Dymo_LabelWriter_450.ppd").write_text(PPD)
+    label = get_label("36x88.9mm@300")
+    images = [Image.new("1", (label.width, label.height), 1)] * 2
+    status = print_image(images, label.id, model="cups:Dymo_LabelWriter_450",
+                         printer="cups:Dymo_LabelWriter_450", options={"DymoCutOptions": "ChainMarks"})
+    assert status == {"outcome": "sent", "did_print": False, "job": "Dymo_LabelWriter_450-12"}
+    lp = calls[-1]
+    assert lp[:-3] == ("lp", "-d", "Dymo_LabelWriter_450", "-o", "media=99012",
+                       "-o", "print-scaling=none", "-o", "orientation-requested=3",
+                       "-o", "fit-to-page=false", "-o", "PageSize=99012",
+                       "-o", "DymoCutOptions=ChainMarks")
+    assert lp[-3] == "--" and lp[-2].endswith(".pdf")          # ein PDF, eine Seite je Etikett
+    pages, size = lp[-1]
+    assert pages == 2 and size == (round(label.width * 72 / 300, 2), round(label.height * 72 / 300, 2))
+
+
+def test_print_errors_are_readable(fake):
+    _, outputs, _ = fake
+    outputs["lp"] = cups.CupsError("CUPS: lp: The printer or class does not exist.")
+    label = labels_for_model("cups:Buero")[0]
+    with pytest.raises(PrintError, match="does not exist"):
+        print_image(Image.new("1", (label.width, label.height), 1), label.id,
+                    model="cups:Buero", printer="cups:Buero")
+
+
+def test_label_must_fit_the_queue(fake):
+    with pytest.raises(PrintError, match="passt nicht"):
+        print_image(Image.new("1", (10, 10), 1), "62", model="cups:Buero", printer="cups:Buero")
+
+
+def test_commands_have_a_time_limit(monkeypatch):
+    seen = {}                                      # echtes _run, aber subprocess ersetzt
+
+    def run(args, **kw):
+        seen.update(kw)
+        raise subprocess.TimeoutExpired(args, kw["timeout"])
+    monkeypatch.setattr(subprocess, "run", run)
+    with pytest.raises(cups.CupsError, match="antwortet nicht"):
+        REAL_RUN("lpstat", "-e")
+    assert seen["timeout"] == cups.TIMEOUT_S
+
+
+def test_missing_commands_and_failures(monkeypatch):
+    def missing(args, **kw):
+        raise FileNotFoundError(args[0])
+    monkeypatch.setattr(subprocess, "run", missing)
+    with pytest.raises(cups.CupsError, match="cups-client"):
+        REAL_RUN("lp")
+    monkeypatch.setattr(subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(
+        args, 1, "", "lp: Error - The printer or class does not exist.\n"))
+    with pytest.raises(cups.CupsError, match="does not exist"):
+        REAL_RUN("lp", "-d", "x")
+
+
+# --- Drucker und Modelle -----------------------------------------------------------------------
+def test_queues_are_printers_without_doubling_the_brother(fake):
+    direct = [printers.Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1", "usb")]
+    names = [p.uri for p in printers.cups_printers(direct)]
+    assert names == ["cups:Dymo_LabelWriter_450", "cups:Buero"]
+    assert len(printers.cups_printers([])) == 3        # ohne Direktweg auch die Brother-Warteschlange
+    p = printers.cups_printers([])[0]
+    assert (p.model, p.name, p.source) == ("cups:Dymo_LabelWriter_450",
+                                           "Dymo_LabelWriter_450 · CUPS", "cups")
+
+
+def test_cups_models(fake):
+    assert printers.is_model("cups:Buero") and not printers.is_model("cups:")
+    caps = printers.capabilities("cups:Dymo_LabelWriter_450")    # fragt CUPS nicht
+    assert not caps.cutter and not caps.two_color and not caps.tested
+    assert not printers.is_model("cups:-x") and not printers.is_model("cups:../etc/x")
+    assert printers.effective_model(printers.printer_for("cups:Buero", [])) == "cups:Buero"
+    assert printers.backend_for("cups:Buero") == "cups"
+    labels = labels_for_model("cups:Dymo_LabelWriter_450")
+    assert labels[0].id == "27.9x88.9mm@300" and all(lbl.shape == "die_cut" for lbl in labels)
+
+
+def test_automatic_choice_never_takes_a_queue(fake):
+    queues = printers.cups_printers([])
+    assert printers.choose(queues) is None
+    net = printers.Printer("tcp://10.0.0.5:9100", "QL-720NW", "Büro", "network")
+    assert printers.choose(queues + [net]) == net
+    assert printers.choose(queues, "cups:Buero").uri == "cups:Buero"
+
+
+def test_chosen_brother_queue_stays_next_to_the_direct_printer(fake):
+    direct = [printers.Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1", "usb")]
+    assert "cups:QL600" in [p.uri for p in printers.cups_printers(direct, keep="cups:QL600")]
+
+
+@pytest.mark.parametrize("key, title, cut", [("CutMedia", "Cut", True), ("DymoCutOptions", "", True),
+                                             ("Cutter", "Messer", True), ("Schnitt", "", True),
+                                             ("ExecuteMode", "Execute", False),
+                                             ("Port", "Schnittstelle", False)])
+def test_cut_options_by_word(key, title, cut):
+    assert bool(cups._cut_options({key: (title or key, ["a", "b"], "a")})) == cut
+
+
+def test_bad_queue_names_are_not_used(fake):
+    _, outputs, folder = fake
+    outputs["lpstat -e"] = "Gut\n-o\n../x\nmit Leer\n"
+    assert [q.name for q in cups.queues()] == ["Gut"]
+    with pytest.raises(cups.CupsError, match="Ungültiger Name"):
+        cups.print_images("../x", [Image.new("1", (8, 8), 1)], 57, 32, 300)
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 0e6089e..3308626 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -298,3 +298,21 @@ def test_invalid_start_favorite_falls_back(tmp_path, value):
     path.write_text(json.dumps({"start_favorite": value}))
     s = load_settings(path)
     assert s.start_favorite is None and any("start_favorite" in w for w in s.warnings)
+
+
+def test_cups_printer_and_its_options_are_kept(tmp_path):
+    path = tmp_path / "settings.json"
+    save_settings(Settings(printer="cups:Dymo", last_model="cups:Dymo", label_id="57x32mm@300",
+                           printer_options={"cups:Dymo": {"CutMedia": "EndOfJob"}}), path)
+    s = load_settings(path)
+    assert (s.printer, s.last_model, s.label_id) == ("cups:Dymo", "cups:Dymo", "57x32mm@300")
+    assert s.printer_options == {"cups:Dymo": {"CutMedia": "EndOfJob"}} and s.warnings == []
+
+
+@pytest.mark.parametrize("bad", [[], {"cups:Dymo": "x"}, {"cups:Dymo": {"CutMedia": 3}},
+                                 {"cups:Dymo": {"CutMedia": "Off -o x=y"}}])
+def test_bad_printer_options_fall_back(tmp_path, bad):
+    path = tmp_path / "settings.json"
+    path.write_text(json.dumps({"printer_options": bad}))
+    s = load_settings(path)
+    assert s.printer_options == {} and s.warnings
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_cups.py, tests/gui/test_gui_cups.py, neue Fälle in tests/test_cli.py und tests/test_settings.py) schlagen fehl (ImportError `labelwerk.cups`), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index c857f97..eca1f30 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -49,8 +49,9 @@ def _add_output_options(p: argparse.ArgumentParser) -> None:
     p.add_argument("-l", "--label", help="Etikett, z. B. 62, oder auto (eingelegte Rolle vom "
                                          "Drucker); Standard aus den Einstellungen")
     p.add_argument("-p", "--printer", default="auto",
-                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP")
-    p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network"],
+                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, "
+                        "cups:NAME (Warteschlange, siehe 'labelwerk printers')")
+    p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network", "cups"],
                    help="Standard: aus dem Drucker (tcp:// → network)")
     p.add_argument("--no-cut", action="store_true")
     p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")
@@ -113,6 +114,8 @@ _NOT_DETECTED = {
              "Manuell angeben mit -p usb://0x04f9:0xPID",
     "network": "Kein Netzwerkdrucker eingetragen (Einstellungen der GUI).\n"
                "Adresse angeben mit -p tcp://IP",
+    "cups": "Keine CUPS-Warteschlange gefunden (Drucker in der Druckerverwaltung einrichten).\n"
+            "Angeben mit -p cups:NAME",
 }
 
 
@@ -128,24 +131,26 @@ def _target(args: argparse.Namespace, settings) -> printers.Printer | None:
     found = _all_printers(settings)
     if wanted != "auto":
         return printers.printer_for(wanted, found)
-    if backend == "network":
-        found = [p for p in found if p.source == "network"]
+    if backend in ("network", "cups"):
+        found = [p for p in found if p.source == backend]
     elif backend == "linux_kernel":
         found = [p for p in found if p.source == "usb"]
     return printers.choose(found, settings.printer)
 
 
 def _all_printers(settings) -> list[printers.Printer]:
-    return printers.usb_printers() + printers.network_printers(network_entries(settings))
+    """Direkt per USB, eingetragene Netzwerkdrucker und Warteschlangen von CUPS."""
+    direct = printers.usb_printers() + printers.network_printers(network_entries(settings))
+    return direct + printers.cups_printers(direct, wait=True)
 
 
 def _resolve_model(model: str, target: printers.Printer | None, settings) -> str:
     """``-m auto``: Modell des Zieldruckers, sonst Ersatzmodell bzw. zuletzt erkanntes aus den
     Einstellungen; ein angegebenes muss bekannt sein."""
     if model != "auto":
-        if model not in printers.SUPPORTED_MODELS:
+        if not printers.is_model(model):
             raise ValueError(f"Unbekanntes Druckermodell {model!r} – erlaubt: "
-                             f"{', '.join(printers.SUPPORTED_MODELS)}")
+                             f"{', '.join(printers.SUPPORTED_MODELS)} oder cups:NAME")
         return model
     return printers.effective_model(target, settings.printer_model, settings.last_model)
 
@@ -205,12 +210,16 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
         print(e, file=sys.stderr)
         return 2
     ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
-    print(f"Status: {status.get('outcome')}")
+    if status.get("job"):
+        print(f"An CUPS übergeben (Auftrag {status['job']})")
+    else:
+        print(f"Status: {status.get('outcome')}")
     return 0 if ok else 1
 
 
 def _show_printers(model: str) -> int:
-    """Gefundene Drucker (USB, eingetragene Netzwerkdrucker) und unterstützte Modelle."""
+    """Gefundene Drucker (USB, eingetragene Netzwerkdrucker, CUPS-Warteschlangen) und unterstützte
+    Modelle."""
     found = _all_printers(load_settings())
     for p in found:
         caps = printers.capabilities(p.model) if p.model else None
@@ -222,7 +231,7 @@ def _show_printers(model: str) -> int:
     print(f"Wirksames Modell: {model}")
     print("Unterstützt: " + ", ".join(
         f"{m}{'' if printers.capabilities(m).tested else ' (ungeprüft)'}"
-        for m in printers.SUPPORTED_MODELS))
+        for m in printers.SUPPORTED_MODELS) + ", CUPS-Warteschlangen cups:NAME (ungeprüft)")
     return 0
 
 
diff --git a/src/labelwerk/cups.py b/src/labelwerk/cups.py
new file mode 100644
index 0000000..3877c32
--- /dev/null
+++ b/src/labelwerk/cups.py
@@ -0,0 +1,323 @@
+"""Drucker über CUPS (das Drucksystem von Linux) – ohne Qt und ohne zusätzliche Bibliothek: nur die
+Befehle ``lpstat``, ``lpoptions`` und ``lp``.
+
+Etikettengrößen und Auflösung kommen aus dem Treiber (PPD: ``*PaperDimension``,
+``*DefaultResolution``), sonst aus den Namen der Größen (``lpoptions -l``: „62x29mm“, „w288h432“
+in Punkt), sonst aus einer Liste je Hersteller (Dymo, Zebra). Schnitt-Optionen sind die
+Treiber-Optionen mit „Cut“ im Namen. Jeder Aufruf hat ein Zeitlimit, Meldungen kommen englisch
+(``LC_MESSAGES=C``, Namen bleiben UTF-8); Fehler werden zur deutschen ``CupsError``. Die Liste
+der Warteschlangen fragt ein Hintergrund-Thread ab – die Oberfläche wartet nie auf CUPS.
+"""
+from __future__ import annotations
+
+import os
+import re
+import subprocess
+import tempfile
+import threading
+import time
+from dataclasses import dataclass, field
+from pathlib import Path
+
+from PIL import Image
+
+from .labels import DPI, DPI_RANGE, SIZE_MM, sized_id
+
+PREFIX = "cups:"
+PPD_DIR = Path("/etc/cups/ppd")            # Tests setzen ein leeres Verzeichnis
+TIMEOUT_S = 5
+PRINT_TIMEOUT_S = 120                      # lp lädt eine ganze Serie hoch
+QUEUE_MAX_AGE_S = 30                       # Liste der Warteschlangen so lange wiederverwenden
+INFO_MAX_AGE_S = 300                       # Treiber-Angaben einer Warteschlange ebenso
+BACKGROUND = True                          # Liste im Hintergrund lesen (Tests: sofort)
+# Name einer Warteschlange (CUPS: druckbar, ohne Leerzeichen, /, \, #, Anführungszeichen)
+_QUEUE_NAME = re.compile(r"[^\s/\\#'\"-][^\s/\\#'\"]{0,126}")
+# Schnitt-Option: „Cut…“ als Wort oder in CamelCase („DymoCutOptions“), „Schneiden“/„Schnitt…“ –
+# nicht „Execute“, nicht „Schnittstelle“
+_CUT = re.compile(r"(?:\b[Cc]ut|(?<=[a-z])Cut|\b[Ss]chn(?:itt|eid))(?!stelle)")
+PT_MM = 25.4 / 72
+# Rückfall: gängige Etiketten je Hersteller (Breite, Höhe in mm)
+MEDIA_LISTS = {
+    "dymo": ((89, 28), (89, 36), (54, 25), (54, 101), (57, 32), (59, 102), (25, 25), (19, 51),
+             (32, 57), (36, 89)),
+    "zebra": ((51, 25), (57, 32), (76, 51), (102, 51), (102, 76), (102, 102), (102, 152),
+              (38, 25), (60, 40)),
+}
+COMMON = ((57, 32), (54, 25), (89, 36), (102, 51), (102, 152), (51, 25))   # unbekannter Hersteller
+
+
+class CupsError(Exception):
+    """CUPS-Befehl gescheitert (Meldung für Nutzer)."""
+
+
+@dataclass(frozen=True)
+class Queue:
+    """Eine Warteschlange: Name und Geräte-URI (z. B. usb://DYMO/LabelWriter%20450)."""
+    name: str
+    device: str = ""
+
+
+@dataclass(frozen=True)
+class CutOption:
+    """Schnitt-Option des Treibers: Schlüssel, Titel und Werte (wie ``lpoptions -l``)."""
+    key: str
+    title: str
+    choices: tuple[str, ...]
+    default: str
+
+
+@dataclass(frozen=True)
+class QueueInfo:
+    """Was der Treiber über Etiketten sagt: Größen (Schlüssel für ``lp``, Breite, Höhe in mm),
+    Auflösung, Schnitt-Optionen; ``source`` woher die Größen stammen (ppd, options, list)."""
+    media: tuple[tuple[str, float, float], ...]
+    dpi: int
+    cut_options: tuple[CutOption, ...] = ()
+    source: str = "ppd"
+
+    def label_ids(self) -> list[str]:
+        ids = []
+        for _, w, h in self.media:
+            label_id = sized_id(w, h, self.dpi)
+            if label_id not in ids:
+                ids.append(label_id)
+        return ids
+
+    def media_key(self, w_mm: float, h_mm: float) -> str:
+        """Größen-Schlüssel des Treibers zu einem Etikett, sonst eine eigene Größe."""
+        for key, w, h in self.media:
+            if abs(w - w_mm) <= 0.15 and abs(h - h_mm) <= 0.15:
+                return key
+        return f"Custom.{w_mm:g}x{h_mm:g}mm"
+
+
+def valid_name(name) -> bool:
+    """Gültiger Name einer Warteschlange (auch Schutz vor Pfaden und Optionen in Aufrufen)."""
+    return isinstance(name, str) and _QUEUE_NAME.fullmatch(name) is not None
+
+
+def _environment() -> dict[str, str]:
+    """Umgebung für CUPS-Befehle: Meldungen englisch (gleich zu lesen), Zeichensatz bleibt."""
+    env = {k: v for k, v in os.environ.items() if k not in ("LC_ALL", "LANGUAGE")}
+    if "UTF-8" not in (env.get("LC_CTYPE") or env.get("LANG") or "").upper().replace("UTF8", "UTF-8"):
+        env["LC_CTYPE"] = "C.UTF-8"
+    env["LC_MESSAGES"] = "C"
+    return env
+
+
+def _run(*args: str, timeout: float = TIMEOUT_S) -> str:
+    """CUPS-Befehl mit Zeitlimit; Ausgabe als Text."""
+    try:
+        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
+                              check=False, env=_environment())
+    except FileNotFoundError:
+        raise CupsError("CUPS-Befehle fehlen (Paket cups-client installieren)") from None
+    except subprocess.TimeoutExpired:
+        raise CupsError(f"CUPS antwortet nicht ({args[0]})") from None
+    if done.returncode != 0:
+        reason = (done.stderr or done.stdout).strip().splitlines()
+        raise CupsError(f"CUPS: {reason[-1] if reason else args[0] + ' gescheitert'}")
+    return done.stdout
+
+
+_lock = threading.Lock()
+_queues_cache: tuple[float | None, list[Queue]] = (None, [])
+_queues_thread: threading.Thread | None = None
+_info_cache: dict[str, tuple[float, QueueInfo]] = {}
+
+
+def read_queues() -> list[Queue]:
+    """Eingerichtete Warteschlangen (``lpstat -e``, Geräte aus ``lpstat -v``) – wartet auf CUPS;
+    ohne CUPS keine, ohne Geräteliste ohne Geräte."""
+    try:
+        names = [n.strip() for n in _run("lpstat", "-e").splitlines() if valid_name(n.strip())]
+    except CupsError:
+        return []
+    devices = {}
+    try:
+        for line in _run("lpstat", "-v").splitlines():
+            m = re.search(r"(\S+):\s+(\S+:/\S*)\s*$", line)      # „device for X:“, „Gerät für X:“
+            if m:
+                devices[m[1]] = m[2]
+    except CupsError:
+        pass
+    return [Queue(n, devices.get(n, "")) for n in names]
+
+
+def queues(max_age: float = QUEUE_MAX_AGE_S, wait: bool = False) -> list[Queue]:
+    """Warteschlangen, wie zuletzt gelesen (höchstens ``max_age`` Sekunden alt); ist die Liste
+    älter, liest ein Hintergrund-Thread sie neu – ``queues()`` wartet nicht (die GUI fragt alle
+    2 s; der erste Aufruf liefert noch keine). ``wait``: neu lesen und warten (CLI)."""
+    global _queues_cache, _queues_thread
+    if wait or not BACKGROUND:
+        found = read_queues()
+        with _lock:
+            _queues_cache = (time.monotonic(), found)
+        return list(found)
+    with _lock:
+        stamp, cached = _queues_cache
+        stale = stamp is None or time.monotonic() - stamp >= max_age
+        if stale and (_queues_thread is None or not _queues_thread.is_alive()):
+            _queues_thread = threading.Thread(target=_refresh_queues, daemon=True)
+            _queues_thread.start()
+        return list(cached)
+
+
+def _refresh_queues() -> None:
+    global _queues_cache
+    found = read_queues()
+    with _lock:
+        _queues_cache = (time.monotonic(), found)
+
+
+def forget() -> None:
+    """Gemerkte Warteschlangen und Treiber-Angaben verwerfen (z. B. neue Warteschlange)."""
+    global _queues_cache
+    with _lock:
+        _queues_cache = (None, [])
+        _info_cache.clear()
+
+
+def queue_info(name: str) -> QueueInfo:
+    """Etiketten, Auflösung und Schnitt-Optionen einer Warteschlange; gemerkt (``INFO_MAX_AGE_S``),
+    außer CUPS hat nicht geantwortet (dann die Liste je Hersteller, beim nächsten Mal neu
+    gefragt). Wartet auf CUPS – nur beim Wählen des Druckers."""
+    with _lock:
+        stamp, info = _info_cache.get(name, (None, None))
+    if info is not None and time.monotonic() - stamp < INFO_MAX_AGE_S:
+        return info
+    try:
+        options = _options(name) if valid_name(name) else {}
+        answered = valid_name(name)
+    except CupsError:
+        options, answered = {}, False
+    info = _queue_info(name, options)
+    if answered:
+        with _lock:
+            _info_cache[name] = (time.monotonic(), info)
+    return info
+
+
+def _queue_info(name: str, options: dict) -> QueueInfo:
+    dpi, media, source = DPI, (), "list"
+    try:
+        if not valid_name(name):
+            raise OSError("kein gültiger Name")
+        dpi, media = _parse_ppd((PPD_DIR / f"{name}.ppd").read_text(errors="replace"))
+        source = "ppd"
+    except OSError:                        # nicht lesbar (Rechte) oder ohne PPD
+        dpi = _option_dpi(options) or DPI
+        media = tuple(m for m in (_media_from_key(k) for k in _choices(options, "PageSize")) if m)
+        source = "options" if media else "list"
+    if not media:
+        maker = next((m for m in MEDIA_LISTS if m in name.lower()), None)
+        media = tuple((f"Custom.{w}x{h}mm", float(w), float(h))
+                      for w, h in MEDIA_LISTS.get(maker, COMMON))
+        source = "list"
+    cuts = tuple(_cut_options(options))
+    return QueueInfo(media, dpi, cuts, source)
+
+
+def _options(name: str) -> dict[str, tuple[str, list[str], str]]:
+    """``lpoptions -p NAME -l``: Schlüssel → (Titel, Werte, Standard); CUPS antwortet nicht →
+    ``CupsError``."""
+    text = _run("lpoptions", "-p", name, "-l")
+    out = {}
+    for line in text.splitlines():
+        head, sep, values = line.partition(":")
+        if not sep:
+            continue
+        key, _, title = head.partition("/")
+        choices = values.split()
+        default = next((c[1:] for c in choices if c.startswith("*")), choices[0] if choices else "")
+        out[key.strip()] = (title.strip() or key.strip(), [c.lstrip("*") for c in choices], default)
+    return out
+
+
+def _choices(options: dict, key: str) -> list[str]:
+    return options.get(key, ("", [], ""))[1]
+
+
+def _option_dpi(options: dict) -> int | None:
+    entry = options.get("Resolution")
+    if entry is None:
+        return None
+    return _dpi(entry[2])
+
+
+def _dpi(text: str) -> int | None:
+    m = re.match(r"\s*(\d+)(?:x\d+)?\s*dpi", text)
+    if not m:
+        return None
+    value = int(m[1])
+    return value if DPI_RANGE[0] <= value <= DPI_RANGE[1] else None
+
+
+def _parse_ppd(text: str) -> tuple[int, tuple[tuple[str, float, float], ...]]:
+    """Auflösung (``*DefaultResolution``) und Größen (``*PaperDimension Name/Text: "w h"`` in Punkt)
+    einer PPD; nur feste Etiketten innerhalb der Grenzen."""
+    dpi = DPI
+    m = re.search(r'^\*DefaultResolution:\s*(\S+)', text, re.M)
+    if m:
+        dpi = _dpi(m[1]) or DPI
+    media = []
+    for key, w, h in re.findall(r'^\*PaperDimension\s+([^/:\s]+)[^:]*:\s*"\s*([\d.]+)\s+([\d.]+)\s*"',
+                                text, re.M):
+        w_mm, h_mm = round(float(w) * PT_MM, 1), round(float(h) * PT_MM, 1)
+        if SIZE_MM[0] <= w_mm <= SIZE_MM[1] and SIZE_MM[0] <= h_mm <= SIZE_MM[1]:
+            media.append((key, w_mm, h_mm))
+    return dpi, tuple(media)
+
+
+def _media_from_key(key: str) -> tuple[str, float, float] | None:
+    """Größe aus einem Namen: „62x29mm“, „w288h432“ (Punkt), „4x6in“; sonst None."""
+    if (m := re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", key)):
+        w, h = float(m[1]), float(m[2])
+    elif (m := re.fullmatch(r"w(\d+(?:\.\d+)?)h(\d+(?:\.\d+)?)", key)):
+        w, h = float(m[1]) * PT_MM, float(m[2]) * PT_MM
+    elif (m := re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)in", key)):
+        w, h = float(m[1]) * 25.4, float(m[2]) * 25.4
+    else:
+        return None
+    w, h = round(w, 1), round(h, 1)
+    if not (SIZE_MM[0] <= w <= SIZE_MM[1] and SIZE_MM[0] <= h <= SIZE_MM[1]):
+        return None
+    return key, w, h
+
+
+def _cut_options(options: dict) -> list[CutOption]:
+    """Treiber-Optionen zum Schneiden (Name oder Titel enthält „cut“/„schnitt“)."""
+    return [CutOption(key, title, tuple(choices), default)
+            for key, (title, choices, default) in options.items()
+            if key != "PageSize" and _CUT.search(f"{key} {title}") and choices]
+
+
+@dataclass
+class Job:
+    """Übergebener Auftrag (``lp``): Kennung wie „Dymo-12“, Seiten (Etiketten)."""
+    id: str
+    pages: int = field(default=1)
+
+
+def print_images(name: str, images: list[Image.Image], w_mm: float, h_mm: float, dpi: int,
+                 options: dict[str, str] | None = None) -> Job:
+    """Etiketten als ein Auftrag an die Warteschlange ``name``: ein PDF mit einer Seite je Etikett
+    in ``dpi`` (Seite = Etikett, 1:1 – ohne Einpassen und Drehen), Größe des Treibers bzw.
+    eigene, dazu ``options`` (z. B. Schnitt). Zurück kommt die Auftrags-Kennung."""
+    if not valid_name(name):
+        raise CupsError(f"Ungültiger Name der Warteschlange: {name!r}")
+    info = queue_info(name)
+    key = info.media_key(w_mm, h_mm)
+    with tempfile.TemporaryDirectory(prefix="labelwerk-") as folder:
+        path = Path(folder) / "etiketten.pdf"
+        first, *rest = [image.convert("1") for image in images]
+        first.save(path, "PDF", resolution=dpi, save_all=True, append_images=rest)
+        args = ["lp", "-d", name, "-o", f"media={key}", "-o", "print-scaling=none",
+                "-o", "orientation-requested=3", "-o", "fit-to-page=false"]
+        if not key.startswith("Custom."):                # Größe des Treibers: auch als PageSize
+            args += ["-o", f"PageSize={key}"]
+        for option, value in (options or {}).items():
+            args += ["-o", f"{option}={value}"]
+        answer = _run(*args, "--", str(path), timeout=PRINT_TIMEOUT_S)
+    m = re.search(r"\b(\S+-\d+)\b", answer)                   # „request id is X-12“, „Anfrage-ID ist X-12“
+    return Job(m[1] if m else name, len(images))
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 022f569..8defa0b 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -20,8 +20,9 @@ from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFileD
 from .. import barcodes, clipart, favorites, series
 from ..desktop import APP_NAME
 from ..detect import brother_busy
-from ..printers import (UNTESTED_HINT, Printer, capabilities, choose, effective_model,
-                        network_printers, usb_printers)
+from .. import cups
+from ..printers import (UNTESTED_HINT, Printer, capabilities, choose, cups_printers,
+                        effective_model, network_printers, usb_printers)
 from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, Series, TextObject
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
@@ -269,8 +270,9 @@ class MainWindow(QMainWindow):
         self._timer.timeout.connect(self.render_now)
         self.panel("paper").check_media_requested.connect(self.check_media)
         self.panel("paper").set_model(self.model)      # Panels entstehen mit dem Standardmodell
-        self.panel("series").set_cutter(capabilities(self.model).cutter)
+        self._update_cut_choices()
         self.panel("layout").color_chosen.connect(self.set_color_selected)
+        self.panel("series").driver_cut_chosen.connect(self._driver_cut_chosen)
         self.panel("paper").media_status_changed.connect(self._show_media_status)
         self._printer_timer = QTimer(self)
         self._printer_timer.setInterval(PRINTER_POLL_MS)
@@ -1446,7 +1448,8 @@ class MainWindow(QMainWindow):
         Erscheinen eines USB-Druckers ggf. Medium prüfen."""
         tip = ""
         try:
-            found = usb_printers() + network_printers(network_entries(self.settings))
+            direct = usb_printers() + network_printers(network_entries(self.settings))
+            found = direct + cups_printers(direct, keep=self.settings.printer)
             busy = not any(p.source == "usb" for p in found) and brother_busy()
         except OSError:
             found, busy = None, False
@@ -1530,10 +1533,26 @@ class MainWindow(QMainWindow):
         self.model = model
         self.canvas.set_model(model)
         self.panel("paper").set_model(model)
-        self.panel("series").set_cutter(capabilities(model).cutter)
+        self._update_cut_choices()
         self._fit_label()
         self.schedule_render()
 
+    def _update_cut_choices(self) -> None:
+        """Reiter SERIE: Schnitt nach dem Drucker – Brother: nach jedem/nur am Ende bzw. ohne
+        Abschneider der Hinweis; CUPS: die Schnitt-Optionen seines Treibers."""
+        panel = self.panel("series")
+        if self.model.startswith("cups:"):
+            options = cups.queue_info(self.model[len("cups:"):]).cut_options
+            panel.set_driver_cuts(options, self.settings.printer_options.get(self.model, {}))
+        else:
+            panel.set_cutter(capabilities(self.model).cutter)
+
+    def _driver_cut_chosen(self, key: str, value: str) -> None:
+        """Treiber-Option zum Schneiden gewählt – gilt für diesen Drucker (Einstellungen)."""
+        if self.model.startswith("cups:"):
+            self.settings.printer_options.setdefault(self.model, {})[key] = value
+            self._save_settings()
+
     def _fit_label(self) -> None:
         """Passt das Etikett nicht zum Modell: ein neues, unberührtes Etikett nimmt ein passendes
         (``FileSession.fitting_label``), sonst bleibt es mit Hinweis (Datei, Favorit, Änderungen)."""
@@ -1602,6 +1621,7 @@ class MainWindow(QMainWindow):
         if accepted and saved is not None:
             # während der Dialog offen war, kann sich Drucker/letztes Modell geändert haben
             saved.printer, saved.last_model = self.settings.printer, self.settings.last_model
+            saved.printer_options = self.settings.printer_options
             if saved.printer.startswith("tcp://") and saved.printer not in {
                     p.uri for p in network_printers(network_entries(saved))}:
                 saved.printer = ""                  # Netzwerkdrucker entfernt/geändert: automatisch
@@ -1857,8 +1877,10 @@ class MainWindow(QMainWindow):
         self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
         self.result.style().polish(self.result)
         self.result.setText("Drucke …")
+        options = (self.settings.printer_options.get(printer.uri, {})
+                   if printer is not None and printer.source == "cups" else {})
         worker = PrintWorker(image, doc.label_id, model, cut_every,
-                             printer=printer.uri if printer else None)
+                             printer=printer.uri if printer else None, options=options)
         self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
         self._worker = worker
         worker.signals.done.connect(self._print_done)
@@ -1887,18 +1909,23 @@ class MainWindow(QMainWindow):
 
     def _update_media_button(self) -> None:
         """„Medium prüfen“ geht nur per USB und nicht während eines Drucks."""
-        network = self.printer is not None and self.printer.source == "network"
+        network = self.printer is not None and self.printer.source != "usb"   # Netz, CUPS
         check = self.panel("paper").check
         missing = self.printer is None and bool(self.settings.printer)     # gewählter fehlt
         check.setEnabled(not self._printing and not network and not missing
                          and not self.is_checking_media())
-        check.setToolTip("Medium prüfen geht nur bei Druckern per USB" if network
+        check.setToolTip("Medium prüfen geht nur bei Brother-Druckern per USB" if network
                          else "Eingelegte Rolle vom Drucker abfragen (druckt nichts)")
 
     def _print_done(self, status: dict) -> None:
         ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
         self.result.setProperty("state", "ok" if ok else "error")
         sent_only = status.get("outcome") == "sent" and not status.get("did_print")
+        if status.get("job"):
+            self.result.setProperty("state", "ok")
+            self.result.setText(f"An die Druckwarteschlange übergeben ✓ (Auftrag {status['job']})")
+            self._print_finished()
+            return
         self.result.setText(("Gesendet ✓ (der Drucker meldet keinen Status zurück)" if sent_only
                              else "Gedruckt ✓") if ok else f"Status: {status.get('outcome')}")
         self._print_finished()
diff --git a/src/labelwerk/gui/panels/series.py b/src/labelwerk/gui/panels/series.py
index c5f6e9d..7e0fbe9 100644
--- a/src/labelwerk/gui/panels/series.py
+++ b/src/labelwerk/gui/panels/series.py
@@ -26,6 +26,7 @@ NO_SERIES = "Keine Serie"
 NUMBERING = "Nummerierung"
 CUT_TITLES = {"each": "Nach jedem Etikett", "end": "Nur am Ende"}
 NO_CUTTER = "Drucker ohne Abschneider – Etiketten von Hand abtrennen"
+DRIVER_CUTS = "Schneiden stellt der Druckertreiber ein (Druckerverwaltung des Systems)"
 SHOWN_COLUMNS = 3                   # Spalten in der Zeilentabelle (die Häkchen sitzen in der ersten)
 ROWS_HEIGHT = 180
 
@@ -33,6 +34,7 @@ ROWS_HEIGHT = 180
 class SeriesPanel(Panel):
     table_requested = Signal()          # TABELLE … – das Hauptfenster fragt nach der Datei
     insert_column = Signal(str)         # Spaltenname → als {Name} ins Etikett
+    driver_cut_chosen = Signal(str, str)   # CUPS: Treiber-Option zum Schneiden, gewählter Wert
 
     def __init__(self, doc: Document):
         super().__init__(doc, "Serie")
@@ -132,6 +134,14 @@ class SeriesPanel(Panel):
         self.no_cutter.setWordWrap(True)
         self.no_cutter.hide()
         self.layout_.addWidget(self.no_cutter)
+        # Treiber-Optionen zum Schneiden (Drucker über CUPS): je Option eine Auswahl
+        self.driver_box = QWidget()
+        self.driver_grid = QGridLayout(self.driver_box)
+        self.driver_grid.setContentsMargins(0, 0, 0, 0)
+        self.driver_grid.setColumnStretch(1, 1)
+        self.driver_box.hide()
+        self.layout_.addWidget(self.driver_box)
+        self.driver_cuts: dict[str, QComboBox] = {}
         self.layout_.addStretch()
 
         self.table_button.clicked.connect(self.table_requested)
@@ -334,7 +344,33 @@ class SeriesPanel(Panel):
         """Drucker mit bzw. ohne Abschneider: ohne gibt es keine Schnitt-Auswahl, nur den Hinweis."""
         self.cut_title.setVisible(cutter)
         self.cut.setVisible(cutter)
+        self.no_cutter.setText(NO_CUTTER)
         self.no_cutter.setVisible(not cutter)
+        self.driver_box.hide()
+
+    def set_driver_cuts(self, options, chosen: dict[str, str]) -> None:
+        """Drucker über CUPS: statt „Nach jedem Etikett/Nur am Ende“ die Schnitt-Optionen seines
+        Treibers (``cups.CutOption``), gewählt wie in ``chosen`` (sonst der Standard des Treibers);
+        ohne solche Optionen der Hinweis, dass der Treiber das bestimmt."""
+        while self.driver_grid.count():
+            self.driver_grid.takeAt(0).widget().deleteLater()
+        self.driver_cuts = {}
+        for row, option in enumerate(options):
+            combo = QComboBox()
+            for choice in option.choices:
+                combo.addItem(choice, choice)
+            combo.setCurrentIndex(max(0, combo.findData(chosen.get(option.key, option.default))))
+            combo.currentIndexChanged.connect(
+                lambda _=0, key=option.key, box=combo: self.driver_cut_chosen.emit(
+                    key, box.currentData()))
+            self.driver_grid.addWidget(QLabel(option.title), row, 0)
+            self.driver_grid.addWidget(combo, row, 1)
+            self.driver_cuts[option.key] = combo
+        self.cut.hide()
+        self.cut_title.setVisible(True)
+        self.driver_box.setVisible(bool(options))
+        self.no_cutter.setText(DRIVER_CUTS)
+        self.no_cutter.setVisible(not options)
 
     def _apply_cut(self) -> None:
         if self.doc.series is not None:
diff --git a/src/labelwerk/gui/print_worker.py b/src/labelwerk/gui/print_worker.py
index 824db56..e877543 100644
--- a/src/labelwerk/gui/print_worker.py
+++ b/src/labelwerk/gui/print_worker.py
@@ -23,10 +23,12 @@ class PrintWorker(QRunnable):
     Netzwerk). ``cancel()`` (aus dem GUI-Thread) bricht vor dem nächsten Teilauftrag ab."""
 
     def __init__(self, image: Image.Image | list[Image.Image], label_id: str, model: str,
-                 cut_every: int = 1, printer: str | None = None):
+                 cut_every: int = 1, printer: str | None = None,
+                 options: dict[str, str] | None = None):
         super().__init__()
         self.image, self.label_id, self.model = image, label_id, model
         self.printer = printer                     # URI; None = USB-Drucker selbst suchen
+        self.options = options or {}               # Treiber-Optionen (CUPS, z. B. Schnitt)
         self.cut_every = cut_every
         self.signals = PrintSignals()
         self._cancel = threading.Event()
@@ -42,7 +44,7 @@ class PrintWorker(QRunnable):
                 return
             status = print_image(self.image, self.label_id, model=self.model, printer=printer,
                                  cut_every=self.cut_every, cancelled=self._cancel.is_set,
-                                 progress=self.signals.progress.emit)
+                                 progress=self.signals.progress.emit, options=self.options)
         except PrintCancelled as e:
             self.signals.cancelled.emit(str(e))
             return
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index cfa9c00..470989c 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -48,6 +48,7 @@ class SettingsDialog(QDialog):
         self._symbols = (settings.symbols_recent, settings.symbols_favorites)   # nur durchgereicht
         self._recent_files = settings.recent_files                             # nur durchgereicht
         self._printer, self._last_model = settings.printer, settings.last_model   # nur durchgereicht
+        self._printer_options = settings.printer_options                          # nur durchgereicht
         outer = QVBoxLayout(self)
         self.tabs = QTabWidget()
         outer.addWidget(self.tabs)
@@ -371,6 +372,7 @@ class SettingsDialog(QDialog):
             printer=self._printer,
             printer_model=self.printer_model.currentData(),
             last_model=self._last_model,
+            printer_options=dict(self._printer_options),
             network_printers=self._network_values() or [],
             shortcuts={action_id: seq for action_id, seq in self._keys.items()
                        if not _same(seq, shortcuts.action(action_id).default)},
diff --git a/src/labelwerk/labels.py b/src/labelwerk/labels.py
index e0a31fe..3c808bc 100644
--- a/src/labelwerk/labels.py
+++ b/src/labelwerk/labels.py
@@ -89,7 +89,11 @@ def get_label(label_id: str) -> Label:
 
 def labels_for_model(model: str) -> list[Label]:
     """Etiketten, die ``model`` drucken kann (``printers.capabilities``): bis zu seiner Breite,
-    ohne P-touch-Bänder, Rot/Schwarz nur bei Zweifarb-Modellen; unbekanntes Modell → ValueError."""
+    ohne P-touch-Bänder, Rot/Schwarz nur bei Zweifarb-Modellen; CUPS-Warteschlange („cups:NAME“):
+    die Größen ihres Treibers in seiner Auflösung; unbekanntes Modell → ValueError."""
+    if isinstance(model, str) and model.startswith("cups:"):
+        from . import cups                     # cups liest diese Datei
+        return [get_label(i) for i in cups.queue_info(model[len("cups:"):]).label_ids()]
     caps = capabilities(model)
     result = []
     for raw in _all_raw():
diff --git a/src/labelwerk/printer.py b/src/labelwerk/printer.py
index 9140368..e2b1bf7 100644
--- a/src/labelwerk/printer.py
+++ b/src/labelwerk/printer.py
@@ -150,6 +150,7 @@ def print_image(
     cut_every: int = 1,
     cancelled: Callable[[], bool] | None = None,
     progress: Callable[[int, int], None] | None = None,
+    options: dict[str, str] | None = None,
 ) -> dict:
     """Ein Etikett oder mehrere (Serie) drucken; Status von brother_ql (des letzten Teils).
 
@@ -157,11 +158,15 @@ def print_image(
     wird geprüft; ein Fehler bricht ab und nennt – waren schon Teile gedruckt – die betroffenen
     Etiketten. ``cancelled()`` wird vor jedem Teil gefragt (True → ``PrintCancelled``; ein
     gesendeter Teil läuft zu Ende), ``progress(gedruckt, alle)`` nach jedem. ``backend``: None =
-    aus der URI (``tcp://`` → Netzwerk: ein Auftrag – der Drucker meldet dort keinen Status)."""
+    aus der URI (``tcp://`` → Netzwerk: ein Auftrag – der Drucker meldet dort keinen Status).
+    ``cups:NAME``: ein Auftrag an die CUPS-Warteschlange (``options``: Treiber-Optionen, z. B.
+    Schnitt); Status ``{"outcome": "sent", "job": Kennung}``."""
     backend = backend or backend_for(printer)
     images = [image] if isinstance(image, Image.Image) else list(image)
     if label_id not in {label.id for label in labels_for_model(model)}:
         raise PrintError(f"Etikett {label_id!r} passt nicht zum Drucker ({model}).")
+    if backend == "cups":
+        return _print_cups(printer[len("cups:"):], images, label_id, options, cancelled)
     if backend == "network":
         _reachable(printer)
     part = MAX_JOB_EACH if cut_every == 1 else min(cut_every, MAX_CUT_EVERY)
@@ -188,6 +193,20 @@ def print_image(
     return status
 
 
+def _print_cups(name: str, images: list[Image.Image], label_id: str,
+                options: dict[str, str] | None, cancelled: Callable[[], bool] | None) -> dict:
+    """An CUPS übergeben – ein Auftrag; danach druckt die Warteschlange (Abbrechen dort)."""
+    from . import cups
+    if cancelled is not None and cancelled():
+        raise PrintCancelled(0, len(images))
+    label = get_label(label_id)
+    try:
+        job = cups.print_images(name, images, *label.size_mm, label.dpi, options)
+    except cups.CupsError as e:
+        raise PrintError(str(e)) from None
+    return {"outcome": "sent", "did_print": False, "job": job.id}
+
+
 def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
     try:
         status = send(instructions=data, printer_identifier=printer,
diff --git a/src/labelwerk/printers.py b/src/labelwerk/printers.py
index e0a9d6c..a2e35a6 100644
--- a/src/labelwerk/printers.py
+++ b/src/labelwerk/printers.py
@@ -49,7 +49,21 @@ class Capabilities:
     tested: bool                 # auf echter Hardware geprüft
 
 
+CUPS = "cups:"                              # Modell-ID bzw. URI einer CUPS-Warteschlange
+GENERIC_LENGTH = (150, 11811)               # Endlosband gibt es bei anderen Druckern nicht
+
+
+def is_model(model) -> bool:
+    """Bekanntes Modell: Brother-QL oder eine CUPS-Warteschlange („cups:NAME“)."""
+    from . import cups
+    return isinstance(model, str) and (model in SUPPORTED_MODELS or model.startswith(CUPS)
+                                       and cups.valid_name(model[len(CUPS):]))
+
+
 def capabilities(model: str) -> Capabilities:
+    if isinstance(model, str) and model.startswith(CUPS) and is_model(model):
+        # Schneiden bestimmt der Treiber (Reiter SERIE) – ohne CUPS zu fragen
+        return Capabilities(model, False, False, 300, GENERIC_LENGTH, False)
     m = _models().get(model)
     if m is None:
         raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
@@ -82,7 +96,9 @@ class Printer:
 
 
 def backend_for(uri: str) -> str:
-    """brother_ql-Backend zur URI."""
+    """Weg zum Drucker: brother_ql-Backend zur URI bzw. „cups“."""
+    if uri.startswith(CUPS):
+        return "cups"
     if uri.startswith("tcp://"):
         return "network"
     if uri.startswith("usb://"):
@@ -142,12 +158,14 @@ def choose(printers: list[Printer], wanted: str = "") -> Printer | None:
     """Der gewählte Drucker (URI aus den Einstellungen) – fehlt er, None: gedruckt wird nicht auf
     einem anderen als dem gewählten. Automatisch (""): der erste gefundene USB-Drucker mit erkanntem
     Modell (ein Brother-Laser auf lp0 soll keine QL-Daten bekommen), dann der erste USB-Drucker,
-    sonst der erste überhaupt; None = keiner."""
+    sonst der erste andere – CUPS-Warteschlangen nie (darunter sind Bürodrucker im Netz), nur
+    gewählt; None = keiner."""
     if wanted:
         return next((p for p in printers if p.uri == wanted), None)
     usb = [p for p in printers if p.source == "usb"]
     known = [p for p in usb if p.model is not None]
-    return (known or usb or printers or [None])[0]
+    others = [p for p in printers if p.source != "cups"]
+    return (known or usb or others or [None])[0]
 
 
 def printer_for(uri: str, found: list[Printer]) -> Printer:
@@ -156,6 +174,8 @@ def printer_for(uri: str, found: list[Printer]) -> Printer:
     for p in found:
         if p.uri == uri:
             return p
+    if uri.startswith(CUPS):
+        return Printer(uri, uri, f"{uri[len(CUPS):]} · CUPS", "cups")
     model = None
     if uri.startswith("usb://"):
         pid = uri[len("usb://"):].split("/")[0].split(":")[-1].lower().removeprefix("0x")
@@ -168,6 +188,18 @@ def effective_model(printer: Printer | None, fallback: str = "", last: str = "")
     """Modell, nach dem sich Etiketten und Fähigkeiten richten: das erkannte, sonst das Ersatzmodell
     aus den Einstellungen, sonst das zuletzt erkannte, sonst ``DEFAULT_MODEL``."""
     for model in (printer.model if printer else None, fallback, last):
-        if model in SUPPORTED_MODELS:
+        if is_model(model):
             return model
     return DEFAULT_MODEL
+
+
+def cups_printers(direct: list[Printer], keep: str = "", wait: bool = False) -> list[Printer]:
+    """Warteschlangen von CUPS als Drucker; ein Brother-QL, den labelwerk direkt per USB findet,
+    erscheint nicht noch einmal über seine Warteschlange – außer sie ist gewählt (``keep``).
+    ``wait``: auf CUPS warten (CLI), sonst die zuletzt gelesene Liste (``cups.queues``)."""
+    from . import cups
+    brother_direct = any(p.source == "usb" and p.model in SUPPORTED_MODELS for p in direct)
+    return [Printer(CUPS + q.name, CUPS + q.name, f"{q.name} · CUPS", "cups")
+            for q in cups.queues(wait=wait)
+            if CUPS + q.name == keep
+            or not (brother_direct and q.device.lower().startswith("usb://brother/ql"))]
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index efaeac6..5ec92b3 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -14,8 +14,8 @@ from . import shortcuts as _shortcuts
 from .clipart import RECENT_LIMIT
 from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .fonts import DEFAULT_FAMILY
-from .labels import labels_for_model
-from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model
+from .labels import labels_for_model, sized_label
+from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model, is_model
 from .storage import RECENT_FILES
 
 THEMES = ("rawblock", "classic")
@@ -42,6 +42,7 @@ class Settings:
     printer_model: str = ""                # Ersatz, wenn das Modell nicht erkannt wird; "" = keins
     last_model: str = ""                   # zuletzt erkanntes Modell (gilt ohne Drucker)
     network_printers: list[dict] = field(default_factory=list)   # {name, host, model}
+    printer_options: dict[str, dict[str, str]] = field(default_factory=dict)  # URI → Treiber-Optionen
     shortcuts: dict[str, str] = field(default_factory=dict)   # nur geänderte Kürzel, "" = keins
     warnings: list[str] = field(default_factory=list, compare=False, repr=False)
 
@@ -55,7 +56,7 @@ def _rules(model: str | None = None) -> dict:
     CLI erst mit dem erkannten Modell (wer zwei Drucker abwechselnd nutzt, behält sein Etikett)."""
     known = {lab.id for m in SUPPORTED_MODELS for lab in labels_for_model(m)}
     return {
-        "label_id": lambda v: isinstance(v, str) and v in known,
+        "label_id": lambda v: isinstance(v, str) and (v in known or sized_label(v) is not None),
         "orientation": lambda v: v in ORIENTATIONS,
         "margin_mm": lambda v: (_is_int(v) or isinstance(v, float)) and 0 <= v <= MAX_MARGIN_MM,
         "font_size_pt": lambda v: v is None or ((_is_int(v) or isinstance(v, float))
@@ -71,9 +72,13 @@ def _rules(model: str | None = None) -> dict:
         "recent_files": lambda v: isinstance(v, list),
         "start_favorite": lambda v: v is None or (isinstance(v, str) and bool(v.strip())),
         "printer": lambda v: isinstance(v, str) and (
-            v == "" or v.startswith(("file://", "tcp://", "usb://"))),
+            v == "" or v.startswith(("file://", "tcp://", "usb://", "cups:"))),
         "printer_model": lambda v: v == "" or v in SUPPORTED_MODELS,
-        "last_model": lambda v: v == "" or v in SUPPORTED_MODELS,
+        "last_model": lambda v: v == "" or is_model(v),
+        "printer_options": lambda v: isinstance(v, dict) and all(
+            isinstance(k, str) and isinstance(o, dict)
+            and all(_option_word(a) and _option_word(b) for a, b in o.items())
+            for k, o in v.items()),
         "network_printers": lambda v: isinstance(v, list),
     }
 
@@ -81,6 +86,12 @@ def _rules(model: str | None = None) -> dict:
 _KEYS = (*_rules(), "shortcuts")
 
 
+def _option_word(value) -> bool:
+    """Schlüssel bzw. Wert einer Druck-Option: ein Wort (``lp -o`` trennt an Leerzeichen)."""
+    return isinstance(value, str) and value.isprintable() and bool(value) \
+        and not any(c.isspace() or c in "='\"" for c in value)
+
+
 def settings_path() -> Path:
     base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
     return Path(base) / "labelwerk" / "settings.json"
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2422 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/cli.py src/labelwerk/cups.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/series.py src/labelwerk/gui/print_worker.py src/labelwerk/gui/settings_dialog.py src/labelwerk/labels.py src/labelwerk/printer.py src/labelwerk/printers.py src/labelwerk/settings.py tests/conftest.py tests/gui/test_gui_barcode.py tests/gui/test_gui_cancel.py tests/gui/test_gui_cups.py tests/gui/test_gui_files.py tests/gui/test_gui_printers.py tests/gui/test_gui_series.py tests/test_cli.py tests/test_cups.py tests/test_settings.py
git commit -m "CUPS: Warteschlangen als Drucker (lpstat/lpoptions/lp), Etiketten und Auflösung aus dem Treiber (PPD, Größennamen, Liste je Hersteller), Druck als ein Auftrag, Schnitt-Optionen des Treibers im Reiter SERIE (je Drucker gespeichert), CLI -p cups:NAME

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Zebra direkt (ZPL), README und Doku

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-19-fremdhersteller-design.md`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/cups.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/series.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/labels.py`
- Modify: `src/labelwerk/printer.py`
- Modify: `src/labelwerk/printers.py`
- Modify: `src/labelwerk/settings.py`
- Create: `src/labelwerk/zpl.py`
- Modify: `tests/golden/raster.json`
- Create: `tests/gui/test_gui_zebra.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_golden.py`
- Modify: `tests/test_settings.py`
- Create: `tests/test_zpl.py`
- Modify: `tools/golden.py`

**Interfaces / Produces:** `zpl.py` (`graphic`, `build(images, mode)`, `send(data, uri)`, `ZplError`, `MEDIA`, `MODES`, `CUT_OPTION`, `is_model`, `model_for`, `dpi_of`, `label_ids`, `dpi_from_id`); `printers.zebra_printers`, Netzwerkeintrag mit Modell `zpl:…`; `printer.print_image` für `zpl+file://`/`zpl+tcp://`; `CutOption.labels`; Einstellungsdialog: Zebra-Modelle für Netzwerkdrucker; `tools/golden.py` mit ZPL-Fällen; README, CLAUDE.md, Spec.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/golden/raster.json b/tests/golden/raster.json
index bca934d..a4d2840 100644
--- a/tests/golden/raster.json
+++ b/tests/golden/raster.json
@@ -114,5 +114,20 @@
   "62-serie": "add99f9db45db791b462d45122ca026a6e1ece4daf3f3384b4a8ffde56603723",
   "62red": "4fdb1ef39fb0e243b64a95beb6464892a3406cb68e1753bb5584c0922383bff4",
   "62x29": "985a654b6b81165290bdd0770f95a9f5867fdc7b44c45fb9b677b36a7ebdcbae"
+ },
+ "zpl:203": {
+  "102x152-schneiden": "f9db953574653877077b2eb310df415890a570ec80aa28cb2f4c055c046026be",
+  "57x32": "ed07494a5f6ddd6128ba98c055ae252173eb709feb40edca39fe2fe1b52d9f1c",
+  "57x32-serie": "aa94fe4fd859e043a81aebe09b89da1357243ed3c4f87f92e571d7e9168bf61b"
+ },
+ "zpl:300": {
+  "102x152-schneiden": "36e7e056acc8102872308d5857b7f8b2299b04a20523d7f3c8b1a2d0adf61499",
+  "57x32": "729a3426669586d4c0147fe6b4c0ff0bd9f7649ae14986e8d7ab1729ffc540ac",
+  "57x32-serie": "898aaccb2d56a36253cebf4a74c1ee8a0f2383a32f1a9a222aecbfbd085676e2"
+ },
+ "zpl:600": {
+  "102x152-schneiden": "f46e35a7051f470b205471d4bf8353796d4baeee5cabec41e36a1d48786dfec9",
+  "57x32": "ba201b752cbfdf88effa78daa0fa373014703f7017ac53cf67bdedf3ee789817",
+  "57x32-serie": "22139838f004caad7d82236e329856114e49b8fd21172040fd2e9c5cf3584a4d"
  }
 }
diff --git a/tests/gui/test_gui_zebra.py b/tests/gui/test_gui_zebra.py
new file mode 100644
index 0000000..8ece663
--- /dev/null
+++ b/tests/gui/test_gui_zebra.py
@@ -0,0 +1,94 @@
+"""Zebra direkt (ZPL) in der GUI: Druckermenü, Etiketten in seiner Auflösung, Modus im Reiter SERIE
+(je Drucker gespeichert), Netzwerk-Zebra in den Einstellungen, Druck mit Modus."""
+from PySide6.QtWidgets import QTableWidgetItem
+
+from labelwerk.document import Document, Numbering, Series, TextObject
+from labelwerk.gui import main_window
+from labelwerk.gui.settings_dialog import SettingsDialog
+from labelwerk.printers import Printer
+from labelwerk.settings import Settings, load_settings
+
+from test_gui_printers import QL600, _labels, _window, workers  # noqa: F401  (Fixture)
+
+ZEBRA = Printer("zpl+file:///dev/usb/lp2", "zpl:300", "ZTC ZD420-300dpi · lp2", "zebra")
+L57 = "57x32mm@305"                                       # 300 dpi = 12 Punkte/mm
+
+
+def _zebra_window(qtbot, monkeypatch, found=(ZEBRA,), **kw):
+    monkeypatch.setattr(main_window, "zebra_printers", lambda **kw: list(found))
+    return _window(qtbot, monkeypatch, [], **kw)
+
+
+def test_zebra_is_chosen_and_brings_its_labels(qtbot, monkeypatch):
+    win = _zebra_window(qtbot, monkeypatch)
+    assert win.printer.uri == ZEBRA.uri and win.model == "zpl:300"
+    assert _labels(win)[:2] == ["51x25mm@305", L57]
+    assert win.doc.label_id == "51x25mm@305"                  # neues Etikett folgt dem Drucker
+    assert win.printer_status.text() == "● ZTC ZD420-300dpi · lp2 · ungeprüft"
+    assert not win.panel("paper").check.isEnabled()
+    assert win.canvas.dpi == 305
+
+
+def test_brother_comes_before_zebra(qtbot, monkeypatch):
+    monkeypatch.setattr(main_window, "zebra_printers", lambda **kw: [ZEBRA])
+    win = _window(qtbot, monkeypatch, [QL600])
+    assert win.printer.uri == QL600.uri
+    win._fill_printer_menu()
+    texts = [a.text() for a in win.printer_menu.actions() if a.text()]
+    assert texts[1:3] == ["QL-600 · lp1", "ZTC ZD420-300dpi · lp2 – ungeprüft"]
+
+
+def test_mode_in_the_series_tab(qtbot, monkeypatch):
+    win = _zebra_window(qtbot, monkeypatch)
+    panel = win.panel("series")
+    combo = panel.driver_cuts["mode"]
+    assert [combo.itemText(i) for i in range(combo.count())] == [
+        "Wie am Drucker eingestellt", "Abreißen", "Schneiden (nur mit Abschneider)",
+        "Ablösen (nur mit Spender)"]
+    assert combo.currentData() == ""                          # sendet kein ^MM
+    combo.setCurrentIndex(2)
+    assert load_settings().printer_options == {"zpl:300": {"mode": "C"}}   # je Modell, nicht lpN
+
+
+def test_series_to_zebra_with_its_mode(qtbot, monkeypatch, workers):
+    win = _zebra_window(qtbot, monkeypatch, doc=Document(
+        L57, objects=[TextObject("X{Nummer}")], series=Series(numbering=Numbering(count=2))),
+        printer_options={"zpl:300": {"mode": "P"}})
+    win.panel("series").refresh()
+    win.ask_print_count = lambda n: True
+    win.print_label()
+    worker = workers[0]
+    assert (worker.printer, worker.model, worker.options) == (ZEBRA.uri, "zpl:300", {"mode": "P"})
+    assert worker.image[0].size == (684, 384) and win.cancel_button.isHidden()
+
+
+def test_network_zebra_in_the_settings(qtbot, tmp_path):
+    path = tmp_path / "s.json"
+    dialog = SettingsDialog(Settings(), path)
+    qtbot.addWidget(dialog)
+    dialog.add_network.click()
+    dialog.network.setItem(0, 0, QTableWidgetItem("Lager"))
+    dialog.network.setItem(0, 1, QTableWidgetItem("10.0.0.8"))
+    combo = dialog.network.cellWidget(0, 2)
+    assert combo.findText("Zebra (ZPL) 203 dpi – ungeprüft") >= 0
+    assert dialog.printer_model.findData("zpl:203") < 0            # Ersatzmodell: nur Brother
+    combo.setCurrentIndex(combo.findData("zpl:203"))
+    dialog.accept()
+    assert load_settings(path).network_printers == [
+        {"name": "Lager", "host": "10.0.0.8", "model": "zpl:203"}]
+
+
+def test_zebra_resolution_in_the_settings(qtbot, tmp_path):
+    path = tmp_path / "s.json"
+    dialog = SettingsDialog(Settings(), path)
+    qtbot.addWidget(dialog)
+    dialog.zebra_dpi.setCurrentIndex(dialog.zebra_dpi.findData(300))
+    dialog.accept()
+    assert load_settings(path).zebra_dpi == 300
+
+
+def test_zebra_resolution_setting_is_used(qtbot, monkeypatch):
+    seen = {}
+    monkeypatch.setattr(main_window, "zebra_printers", lambda **kw: seen.update(kw) or [])
+    _window(qtbot, monkeypatch, [], zebra_dpi=600)
+    assert seen == {"dpi": 600}
diff --git a/tests/test_cli.py b/tests/test_cli.py
index 38d6c25..04a6dce 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -536,3 +536,25 @@ def test_print_file_to_cups_in_its_resolution(cups_queue, tmp_path, monkeypatch)
     assert main(["print-file", str(_png(tmp_path, 40, 20)), "-p", "cups:Buero",
                  "-l", "57.2x31.8mm@203"]) == 0
     assert sizes == [(457, 254)]
+
+
+# --- Zebra --------------------------------------------------------------------------------------
+def test_print_to_a_zebra_device(tmp_path, capsys, monkeypatch):
+    from labelwerk import zpl
+    monkeypatch.setattr(zpl, "_is_device", lambda info: True)    # Datei statt Gerät
+    device = tmp_path / "lp2"
+    device.write_bytes(b"")
+    assert main(["-m", "zpl:300", "print", "Hallo", "-p", f"zpl+file://{device}",
+                 "-l", "57x32mm@305", "-b", "zebra"]) == 0
+    assert device.read_bytes().startswith(b"^XA^PW684^LL384")     # ohne ^MM: wie am Drucker
+    assert main(["print", "Hallo", "-p", f"zpl+file://{device}", "-l", "57x32mm@305"]) == 2
+    assert "passt nicht zum zpl:203" in capsys.readouterr().err     # ohne -m: 203 dpi
+
+
+def test_zebra_on_usb_is_listed(tmp_path, monkeypatch, capsys):
+    from labelwerk import printers
+    monkeypatch.setattr(printers, "zebra_printers", lambda **kw: [printers.Printer(
+        "zpl+file:///dev/usb/lp2", "zpl:203", "ZTC GK420d · lp2", "zebra")])
+    assert main(["printers"]) == 0
+    out = capsys.readouterr().out
+    assert "ZTC GK420d · lp2" in out and "zpl+file:///dev/usb/lp2" in out and "Zebra zpl:203" in out
diff --git a/tests/test_golden.py b/tests/test_golden.py
index 547de6d..793791b 100644
--- a/tests/test_golden.py
+++ b/tests/test_golden.py
@@ -17,10 +17,11 @@ STORED = json.loads((ROOT / "tests" / "golden" / "raster.json").read_text())
 
 
 def test_every_supported_model_has_references():
-    assert sorted(STORED) == sorted(SUPPORTED_MODELS)
+    assert sorted(STORED) == sorted(golden.MODELS)
+    assert set(SUPPORTED_MODELS) < set(golden.MODELS) and "zpl:203" in STORED
 
 
-@pytest.mark.parametrize("model", SUPPORTED_MODELS)
+@pytest.mark.parametrize("model", golden.MODELS)
 def test_raster_data_is_unchanged(model):
     current = {name: golden.hashlib.sha256(data).hexdigest()
                for name, data in golden.cases(model).items()}
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 3308626..d2c6863 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -316,3 +316,13 @@ def test_bad_printer_options_fall_back(tmp_path, bad):
     path.write_text(json.dumps({"printer_options": bad}))
     s = load_settings(path)
     assert s.printer_options == {} and s.warnings
+
+
+def test_network_zebra_is_kept(tmp_path):
+    path = tmp_path / "settings.json"
+    path.write_text(json.dumps({"network_printers": [
+        {"name": "Lager", "host": "10.0.0.8", "model": "zpl:203"},
+        {"name": "x", "host": "10.0.0.9", "model": "zpl:250"}]}))
+    s = load_settings(path)
+    assert s.network_printers == [{"name": "Lager", "host": "10.0.0.8", "model": "zpl:203"}]
+    assert s.warnings
diff --git a/tests/test_zpl.py b/tests/test_zpl.py
new file mode 100644
index 0000000..b985277
--- /dev/null
+++ b/tests/test_zpl.py
@@ -0,0 +1,271 @@
+"""Zebra direkt (ZPL): Aufbau, Kompression (zurückgelesen mit einem eigenen Decoder), Erkennung
+per sysfs, Senden (Gerät/Socket ersetzt) – kein Test spricht einen Drucker oder das Netz an."""
+import random
+import re
+
+import pytest
+from PIL import Image, ImageDraw
+
+from labelwerk import printers, zpl
+from labelwerk.labels import get_label, labels_for_model
+from labelwerk.printer import PrintError, print_image
+
+
+def decode(text: str) -> Image.Image:
+    """``^GFA,total,total,je_zeile,daten`` → Bild (schwarz = Punkt), Kompression nach Zebra
+    zeichenweise zurückgelesen (für die Tests)."""
+    m = re.search(r"\^GFA,(\d+),(\d+),(\d+),([^^]*)", text)
+    total, row_bytes, data = int(m[1]), int(m[3]), m[4]
+    width = row_bytes * 2
+    rows, row, count = [], "", 0
+
+    def finish(fill=""):
+        nonlocal row
+        rows.append(row + fill * (width - len(row)))
+        row = ""
+    for ch in data:
+        if "G" <= ch <= "Y":
+            count += ord(ch) - ord("F")
+        elif "g" <= ch <= "z":
+            count += (ord(ch) - ord("f")) * 20
+        elif ch in ",!":
+            finish("0" if ch == "," else "F")
+        elif ch == ":":
+            assert row == ""
+            rows.append(rows[-1])
+        else:
+            row += ch * max(count, 1)
+            count = 0
+            assert len(row) <= width
+            if len(row) == width:
+                finish()
+    assert row == "" and all(len(r) == width for r in rows)
+    raw = bytes.fromhex("".join(rows))
+    assert len(raw) == total
+    return Image.frombytes("1", (row_bytes * 8, total // row_bytes), bytes(b ^ 0xFF for b in raw))
+
+
+def _picture(w, h, seed=1):
+    rnd = random.Random(seed)
+    img = Image.new("1", (w, h), 1)
+    pen = ImageDraw.Draw(img)
+    for _ in range(40):
+        x, y = rnd.randrange(w), rnd.randrange(h)
+        pen.rectangle((x, y, x + rnd.randrange(1, 60), y + rnd.randrange(1, 9)), fill=0)
+    for x in range(0, w, 7):                                 # Muster: keine Wiederholungen
+        img.putpixel((x, h // 2), 0)
+    return img
+
+
+# --- Kompression --------------------------------------------------------------------------------
+@pytest.mark.parametrize("n, code", [(2, "H"), (19, "Y"), (20, "g"), (21, "gG"), (400, "z"),
+                                     (419, "zY")])
+def test_repeat_counts(n, code):
+    assert zpl._count(n) == code
+
+
+def test_rows():
+    assert zpl._compress_row("FFFF0000") == "JF,"
+    assert zpl._compress_row("0000") == ","
+    assert zpl._compress_row("A1B2") == "A1B2"
+    assert zpl._compress_row("F" * 500) == "zYF" + "jGF"     # 419 + 81
+
+
+@pytest.mark.parametrize("size", [(456, 256), (813, 1218), (9, 3), (1, 1), (684, 40)])
+def test_graphic_reads_back_exactly(size):
+    img = _picture(*size)
+    back = decode(zpl.graphic(img))
+    assert back.crop((0, 0, *size)).tobytes() == img.tobytes()
+    if back.width > size[0]:                                  # Füllbits am Zeilenende: weiß
+        assert back.crop((size[0], 0, back.width, size[1])).getextrema() == (255, 255)
+
+
+def test_white_image_has_no_dots():
+    assert zpl.graphic(Image.new("1", (673, 3), 1)) == "^GFA,255,255,85,,::"
+
+
+def test_fixed_reference_rows():
+    assert zpl._compress_row("B" * 327 + "0" * 3) == "vMB,"      # 327 = v (320) + M (7)
+    assert zpl._compress_row("0F" * 3) == "0F0F0F"
+
+
+def test_large_images_go_in_bands():
+    img = Image.new("1", (1224, 1830), 1)                     # 102 × 152 mm bei 12 Punkten/mm
+    text = zpl.fields(img)
+    sizes = [int(n) for n in re.findall(r"\^GFA,(\d+),", text)]
+    assert max(sizes) <= zpl.MAX_GRAPHIC and sum(sizes) == 153 * 1830
+    assert text.startswith("^FO0,0^GFA") and "^FO0,653^GFA" in text
+
+
+def test_same_rows_become_a_colon():
+    img = Image.new("1", (16, 5), 1)
+    ImageDraw.Draw(img).rectangle((0, 0, 7, 4), fill=0)
+    assert zpl.graphic(img) == "^GFA,10,10,2,HF,::::"
+
+
+def test_build_one_stream_per_series():
+    label = get_label("57x32mm@203")
+    img = Image.new("1", (label.width, label.height), 1)
+    data = zpl.build([img, img], "C").decode()
+    assert data.count("^XA^MMC^PW456^LL256^LH0,0^FO0,0^GFA,") == 2 and data.count("^XZ") == 2
+    assert zpl.build([img]).startswith(b"^XA^PW456")          # Standard: kein ^MM
+    with pytest.raises(ValueError, match="Modus"):
+        zpl.build([img], "X")
+
+
+# --- Modelle und Erkennung ----------------------------------------------------------------------
+def test_zebra_models_and_labels():
+    assert zpl.is_model("zpl:203") and not zpl.is_model("zpl:250") and not zpl.is_model(None)
+    assert printers.is_model("zpl:300")
+    caps = printers.capabilities("zpl:203")             # Schneiden: Modus im Reiter SERIE
+    assert not caps.cutter and not caps.two_color and not caps.tested
+    labels = labels_for_model("zpl:300")                   # 12 Punkte/mm = 304,8 dpi
+    assert labels[0].id == "51x25mm@305" and labels[0].dpi == 305 and len(labels) == len(zpl.MEDIA)
+    assert labels_for_model("zpl:600")[0].id == "51x25mm@610"
+    assert get_label("102x152mm@305").width == 1225             # 102 mm × 12 = 1224 (305 statt 304,8)
+
+
+def _sys_printer(root, name, vendor, ieee="", product=""):
+    dev = root / "devices" / name
+    (dev / "iface").mkdir(parents=True)
+    (dev / "idVendor").write_text(vendor)
+    (dev / "idProduct").write_text("0001")
+    (dev / "product").write_text(product)
+    (dev / "iface" / "ieee1284_id").write_text(ieee)
+    entry = root / "usbmisc" / name
+    entry.mkdir(parents=True)
+    (entry / "device").symlink_to(dev / "iface")
+
+
+@pytest.mark.parametrize("ieee, zpl_ok", [("MFG:Zebra Technologies;CMD:ZPL;MDL:ZD420;", True),
+                                           ("MFG:Zebra;COMMAND SET:EPL2,ZPL;MDL:GK420d;", True),
+                                           ("MFG:Zebra;CMD:EPL2;MDL:LP2844;", False),
+                                           ("MDL:ZXP Series 3;CMD:ZMOTIF;", False), ("", True)])
+def test_only_zpl_printers(ieee, zpl_ok):
+    assert zpl.speaks_zpl(ieee) == zpl_ok
+
+
+def test_zebra_on_usb_is_found_with_its_resolution(tmp_path):
+    _sys_printer(tmp_path, "lp1", "04f9", "MDL:QL-600;")
+    _sys_printer(tmp_path, "lp2", "0a5f", "MFG:Zebra Technologies;MDL:ZTC ZD420-300dpi ZPL;")
+    _sys_printer(tmp_path, "lp3", "0a5f", "", "ZTC GK420d")
+    found = printers.zebra_printers(tmp_path / "usbmisc")
+    assert [(p.uri, p.model, p.name, p.source) for p in found] == [
+        ("zpl+file:///dev/usb/lp2", "zpl:300", "ZTC ZD420-300dpi ZPL · lp2", "zebra"),
+        ("zpl+file:///dev/usb/lp3", "zpl:203", "ZTC GK420d · lp3", "zebra")]
+    assert [p.uri for p in printers.usb_printers(tmp_path / "usbmisc")] == ["file:///dev/usb/lp1"]
+    _sys_printer(tmp_path, "lp4", "0a5f", "MFG:Zebra;CMD:EPL2;MDL:LP2844;")     # nur EPL: nicht
+    assert len(printers.zebra_printers(tmp_path / "usbmisc")) == 2
+    forced = printers.zebra_printers(tmp_path / "usbmisc", dpi=600)       # Einstellung gilt
+    assert [p.model for p in forced] == ["zpl:600", "zpl:600"]
+
+
+def test_network_zebra_and_given_uris():
+    entries = [printers.NetworkEntry("Lager", "10.0.0.8", "zpl:203"),
+               printers.NetworkEntry("Büro", "10.0.0.5", "QL-720NW")]
+    zebra, brother = printers.network_printers(entries)
+    assert (zebra.uri, zebra.model, zebra.source) == ("zpl+tcp://10.0.0.8:9100", "zpl:203", "zebra")
+    assert brother.uri == "tcp://10.0.0.5:9100"
+    given = printers.printer_for("zpl+tcp://10.0.0.9", [])
+    assert (given.model, given.source) == ("zpl:203", "zebra")
+    assert printers.backend_for("zpl+file:///dev/usb/lp2") == "zpl"
+
+
+# --- Drucken ------------------------------------------------------------------------------------
+@pytest.fixture
+def any_file(monkeypatch):
+    """Eine Datei gilt als Druckergerät (Tests schreiben nie an /dev/usb)."""
+    monkeypatch.setattr(zpl, "_is_device", lambda info: True)
+
+
+def test_print_writes_zpl_to_the_device(tmp_path, any_file):
+    device = tmp_path / "lp2"
+    device.write_bytes(b"")
+    label = get_label("57x32mm@203")
+    img = Image.new("1", (label.width, label.height), 1)
+    status = print_image([img] * 3, label.id, model="zpl:203", printer=f"zpl+file://{device}",
+                         options={"mode": "C"})
+    assert status == {"outcome": "sent", "did_print": False}
+    assert device.read_bytes().count(b"^XA^MMC^PW456^LL256") == 3
+
+
+def test_print_over_the_network(monkeypatch):
+    sent = {}
+
+    class Conn:
+        def __enter__(self):
+            return self
+
+        def __exit__(self, *a):
+            return False
+
+        def settimeout(self, value):
+            sent["write_timeout"] = value
+
+        def send(self, data):
+            sent["data"] = sent.get("data", b"") + bytes(data[:1000])     # langsamer Drucker
+            return min(len(data), 1000)
+
+    def connect(address, timeout):
+        sent["address"], sent["timeout"] = address, timeout
+        return Conn()
+    monkeypatch.setattr(zpl.socket, "create_connection", connect)
+    label = get_label("51x25mm@203")
+    print_image(Image.new("1", (label.width, label.height), 1), label.id, model="zpl:203",
+                printer="zpl+tcp://10.0.0.8:9100")
+    assert sent["address"] == ("10.0.0.8", 9100) and sent["timeout"] == zpl.TIMEOUT_S
+    assert sent["write_timeout"] == zpl.WRITE_TIMEOUT_S          # je Block, nicht für alles
+    assert sent["data"].startswith(b"^XA^PW408^LL200") and sent["data"].endswith(b"^XZ\n")
+
+
+def test_send_errors_are_readable(tmp_path, monkeypatch):
+    label = get_label("57x32mm@203")
+    img = Image.new("1", (label.width, label.height), 1)
+    with pytest.raises(PrintError, match="nicht gefunden"):
+        print_image(img, label.id, model="zpl:203", printer=f"zpl+file://{tmp_path}/fehlt")
+    (tmp_path / "datei").write_bytes(b"")
+    with pytest.raises(PrintError, match="kein Druckergerät"):
+        print_image(img, label.id, model="zpl:203", printer=f"zpl+file://{tmp_path}/datei")
+    assert not (tmp_path / "fehlt").exists()                   # nie eine Datei angelegt
+
+    def refuse(address, timeout):
+        raise ConnectionRefusedError(111, "Connection refused")
+    monkeypatch.setattr(zpl.socket, "create_connection", refuse)
+    with pytest.raises(PrintError, match="Zebra-Drucker 10.0.0.8 nicht erreichbar"):
+        print_image(img, label.id, model="zpl:203", printer="zpl+tcp://10.0.0.8")
+    with pytest.raises(PrintError, match="Ungültige Adresse"):
+        print_image(img, label.id, model="zpl:203", printer="zpl+tcp://10.0.0.8:x")
+
+
+def test_brother_label_does_not_fit_a_zebra(tmp_path):
+    with pytest.raises(PrintError, match="passt nicht"):
+        print_image(Image.new("1", (10, 10), 1), "62", model="zpl:203",
+                    printer=f"zpl+file://{tmp_path}/lp2")
+
+
+def test_device_that_takes_no_data_times_out(tmp_path, any_file, monkeypatch):
+    class Stuck:
+        def register(self, fd, events):
+            pass
+
+        def poll(self, timeout):
+            return []
+    monkeypatch.setattr(zpl.select, "poll", Stuck)
+    (tmp_path / "lp2").write_bytes(b"")
+    with pytest.raises(zpl.ZplError, match="nimmt keine Daten an"):
+        zpl.send(b"^XA^XZ", f"zpl+file://{tmp_path}/lp2")
+
+
+def test_series_is_streamed_label_by_label(tmp_path, any_file):
+    label = get_label("51x25mm@203")
+    made = []
+
+    def images():
+        for n in range(3):
+            made.append(n)
+            yield Image.new("1", (label.width, label.height), 1)
+    chunks = zpl.stream(images())
+    assert made == []                                          # erst beim Senden erzeugt
+    zpl.send(chunks, f"zpl+file://{tmp_path}/lp2") if (tmp_path / "lp2").write_bytes(b"") == 0 \
+        else None
+    assert made == [0, 1, 2] and (tmp_path / "lp2").read_bytes().count(b"^XZ") == 3
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_zpl.py, tests/gui/test_gui_zebra.py, ZPL-Referenzen in tests/test_golden.py, neue Fälle in tests/test_cli.py und tests/test_settings.py) schlagen fehl (ImportError `labelwerk.zpl`), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index df0a7b4..b4f8a10 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -38,14 +38,21 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   Farbe; Netzwerkdrucker per IP in den Einstellungen (Medium prüfen nur USB); Rot/Schwarz je Objekt (Reiter Layout →
   Farbe, nur 62red auf QL-8xx, ungeprüft); CLI -m/-l auto, labelwerk printers; Referenztests je Modell (tests/golden).
 - Datei und Favoriten (Etappe 3c): Reiter DATEI – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“); `labelwerk install-desktop` meldet *.labelwerk an (Doppelklick öffnet).
-- 2348 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Drucker anderer Hersteller (Etappe 6b, alles ungeprüft): Auflösung je Etikett (Etiketten „57x32mm@203“, Rendern/Layout/
+  Barcodes/Arbeitsfläche in Druckerauflösung, Barcode-Maße in mm, Etikettwechsel rechnet Module um); CUPS-Warteschlangen
+  im Druckermenü (nie automatisch), Etiketten/Auflösung aus dem Treiber, Druck als PDF in einem Auftrag, Schnitt-Optionen
+  des Treibers im Reiter SERIE; Zebra direkt (ZPL, USB/Netzwerk, Modus Abreißen/Schneiden/Ablösen); CLI -p cups:NAME,
+  zpl+file://, zpl+tcp:// mit -m zpl:203.
+- 2454 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
 src/labelwerk/
   labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager): labels_for_model nach
               printers.capabilities (Breite, restricted_to_models, ohne PT-Bänder, 62red nur Zweifarb-Modelle);
-              Label.two_color
+              Label.two_color, Label.dpi (Brother 300); Etiketten anderer Drucker als ID „BxHmm@dpi“ (sized_id/sized_label,
+              fest, ganz bedruckbar, eine Schreibweise; get_label versteht sie ohne Drucker), mm_text (Maß mit Komma);
+              cups:NAME → Etiketten des Treibers, zpl:DPI → zpl.MEDIA
   render.py   render_text(text, label_id, size_pt, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
               render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
               compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise:
@@ -82,7 +89,8 @@ src/labelwerk/
   imaging.py  Bilder ohne Qt: to_layers(img, mode line|photo, threshold, invert) -> {"black": Bild "1"} (später "red" für QL-8xx),
               on_white, to_8bit (16-Bit-Graustufen skalieren), limit_size (höchstens 600 dpi bzw. 6000 px längste Seite,
               Druckgröße bleibt); Foto: Gammakurve photo_curve (Weiß/Schwarz fest), dann Floyd-Steinberg
-  printer.py  build_instructions(image | [images], label_id, model, cut, cut_every) -> bytes (Brother-Raster, mehrere
+  printer.py  (cups:NAME → cups.print_images, zpl+… → zpl.build/send: je ein Auftrag, Status „sent“)
+              build_instructions(image | [images], label_id, model, cut, cut_every) -> bytes (Brother-Raster, mehrere
               Etiketten = ein Auftrag; _Raster: schneiden alle n über ESC i A n, Folgeseiten markiert, bytearray statt
               bytes += – sonst quadratisch langsam), cut_interval(each|end, Anzahl)
               print_image(image | [images], ..., cut_every, cancelled, progress) -> status-dict; Serien in Teilaufträgen
@@ -94,7 +102,17 @@ src/labelwerk/
               product, idProduct → PRODUCT_IDS; SYS_ROOT in Tests leer), network_printers(NetworkEntry), choose (gewählt –
               fehlt er: None, kein Ersatz; automatisch: USB mit Modell › USB › erster), printer_for(uri) (usb://…:0xPID → Modell), effective_model (erkannt › Ersatz ›
               zuletzt › QL-600), capabilities(model) (cutter, two_color, max_tape_mm 62/104, length_limits, tested),
-              SUPPORTED_MODELS (QL ohne PT), TESTED_MODELS, backend_for(uri)
+              SUPPORTED_MODELS (QL ohne PT), TESTED_MODELS, backend_for(uri) (… | cups | zpl), is_model (QL, cups:NAME,
+              zpl:203/300/600), zebra_printers() (sysfs Vendor 0a5f, dpi aus der Kennung, sonst 203; source zebra),
+              Netzwerkeintrag mit Modell zpl:… → zpl+tcp://, cups_printers(direct, keep, wait) (Brother-QL-Warteschlange
+              nicht doppelt, außer gewählt); choose automatisch nie CUPS
+  cups.py     CUPS ohne Qt: _run (lpstat/lpoptions/lp, Zeitlimit, LC_MESSAGES=C; Tests ersetzen _run, BACKGROUND aus),
+              queues() (Hintergrund-Thread, 30 s; wait=True für die CLI), queue_info(name) -> QueueInfo(media, dpi,
+              cut_options, source ppd|options|list; 5 min gemerkt, Fehler nicht), PPD aus PPD_DIR, valid_name,
+              print_images(name, images, w, h, dpi, options) -> Job (ein PDF, media=/PageSize=, print-scaling=none)
+  zpl.py      Zebra ohne Qt: graphic(img) (^GFA, Zebra-ASCII-Kompression, „:“ = gleiche Zeile), build(images, mode T|C|P),
+              send(data, uri) (zpl+file:// bzw. zpl+tcp://, Zeitlimit) → ZplError; MEDIA, CUT_OPTION (Reiter SERIE),
+              Referenz-Hashes in tests/golden wie Brother
   document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit);
               TextObject: Position x_mm/y_mm (None = mittig wie bisher), Rahmen w_mm/h_mm (mit fit), Drehen rotation 0/90/180/270
               ImageObject: png (Farboriginal), source/page/crop, Rahmen x/y/w/h_mm immer gesetzt, rotation, mode/threshold/invert,
diff --git a/README.md b/README.md
index a33b24a..3f051d3 100644
--- a/README.md
+++ b/README.md
@@ -12,7 +12,9 @@ Getestet mit: QL-600 (USB). Andere QL-Modelle sollten funktionieren, Rückmeldun
 | **sollte funktionieren** (ungeprüft) | QL-500, QL-550, QL-560, QL-570, QL-580N, QL-650TD, QL-700, QL-710W, QL-720NW, QL-800, QL-810W, QL-820NWB – Etiketten bis 62 mm, USB oder Netzwerk |
 | **sollte funktionieren** (ungeprüft) | breite Modelle QL-1050, QL-1060N, QL-1100, QL-1110NWB, QL-1115NWB – Etiketten bis 102/104 mm |
 | **ungeprüft** | Rot/Schwarz-Druck (QL-8xx mit DK-22251 „62red“): Farbe je Objekt im Reiter Layout |
-| **nicht unterstützt** | P-touch-Bandgeräte (PT-…), Drucker anderer Hersteller |
+| **ungeprüft** | Zebra-Etikettendrucker direkt in ZPL (USB oder Netzwerk, 203/300/600 dpi, feste Etiketten) |
+| **ungeprüft** | jeder in CUPS eingerichtete Etikettendrucker (z. B. Dymo LabelWriter): Etiketten und Auflösung aus dem Treiber |
+| **nicht unterstützt** | P-touch-Bandgeräte (PT-…), Bluetooth-Drucker (Niimbot, Phomemo), Endlosband bei anderen Herstellern |
 
 labelwerk erkennt das Modell des angeschlossenen Druckers selbst (`labelwerk printers` zeigt, was es
 findet); Etiketten, Abschneider und Farben richten sich danach. Wird ein Modell nicht erkannt, lässt
@@ -20,6 +22,15 @@ es sich in den Einstellungen festlegen. Netzwerkdrucker (WLAN/LAN-Modelle) träg
 Einstellungen mit IP-Adresse ein; „Medium prüfen“ geht nur per USB. Hast du ein ungeprüftes Modell
 ausprobiert, freue ich mich über eine Rückmeldung (Issue mit Modell, Rolle und Ergebnis).
 
+**Andere Hersteller:** Zebra-Drucker am USB erkennt labelwerk selbst (Auflösung aus der Kennung des
+Druckers, sonst 203 dpi); Netzwerk-Zebras trägst du in den Einstellungen mit Modell „Zebra (ZPL)“ und
+Auflösung ein. Drucker, die in der Druckerverwaltung des Systems (CUPS) eingerichtet sind, stehen im
+Druckermenü als „Name · CUPS“ – sie werden nie automatisch gewählt (darunter sind oft Bürodrucker).
+Gedruckt wird in der echten Auflösung des Druckers, damit Barcodes scharf bleiben. Schneiden stellst du
+im Reiter SERIE ein: bei CUPS die Schnitt-Optionen des Treibers, bei Zebra Abreißen/Schneiden/Ablösen.
+Grenzen: Der Treiber kann einen unbedruckbaren Rand haben (Rand im Reiter PAPIER vergrößern), „Medium
+prüfen“ und Abbrechen gibt es nur bei Brother per USB.
+
 ## Installation
 
 ```bash
@@ -53,6 +64,7 @@ labelwerk print "Max Mustermann\nMusterstr. 5\n12345 Musterstadt" --orientation
 ```
 
 Optionen: `-s` Schriftgröße (`auto` oder 8–400), `--font` eigene TTF, `-m QL-700` Modell (Standard: erkannt), `-p tcp://IP` Netzwerkdrucker, `-b pyusb` alternatives USB-Backend, `--no-cut`.
+Andere Hersteller: `-p cups:NAME` (Warteschlange, Etiketten mit `labelwerk -m cups:NAME labels`), Zebra `-p zpl+file:///dev/usb/lp2` bzw. `-p zpl+tcp://IP` mit `-m zpl:203|300|600`; Etiketten heißen dort `57x32mm@203` (Breite × Höhe @ dpi).
 `print-file` schneidet auf den Inhalt zu (Schnittmarken, z. B. der Internetmarke, und Leerraum fallen weg), dreht bei Bedarf und druckt 1:1; `--rotate 0|90|180|270` legt die Drehung fest (Grad im Uhrzeigersinn), `--fit` verkleinert zu große Motive, `--page N` wählt die PDF-Seite. Internetmarke quer wie im PDF: `--rotate 0 --fit`.
 
 ## Grafische Oberfläche
@@ -96,11 +108,13 @@ Ausrichten, Größe angleichen und Maximieren haben ab Werk kein Kürzel. Im Sch
 ## Architektur
 
 ```
-render.py   Inhalt → Bild in exakter Druckbreite (300 dpi)
+render.py   Inhalt → Bild in exakter Druckbreite (Auflösung des Etiketts: Brother 300 dpi)
 files.py    PDF/Bild → zugeschnitten, 1:1 aufs Etikett gesetzt
-labels.py   Etikettentypen je Modell
+labels.py   Etikettentypen je Modell, Etiketten anderer Drucker „BxHmm@dpi“
 printer.py  Bild → Brother-Rasterdaten → Drucker (via brother_ql)
 printers.py Drucker erkennen (Modell), Fähigkeiten je Modell, Netzwerkdrucker
+cups.py     CUPS-Warteschlangen (lpstat/lpoptions/lp): Etiketten aus dem Treiber, Druck als PDF
+zpl.py      Zebra direkt: Bild → ZPL (^GFA, komprimiert), Senden an USB/TCP
 cli.py      Kommandozeile
 document.py Etikett-Dokument (Etikett, Länge, Objekte)
 settings.py Einstellungen (JSON)
diff --git a/docs/superpowers/specs/2026-10-19-fremdhersteller-design.md b/docs/superpowers/specs/2026-10-19-fremdhersteller-design.md
index df3c82b..50c1414 100644
--- a/docs/superpowers/specs/2026-10-19-fremdhersteller-design.md
+++ b/docs/superpowers/specs/2026-10-19-fremdhersteller-design.md
@@ -49,12 +49,19 @@ eines schon an CUPS übergebenen Auftrags (geht über die Druckerverwaltung des
   Liste je Hersteller (`MEDIA_LISTS`: Dymo-Klassiker 99010/99012/11352/…, Zebra 2×1"/4×6" …). Auflösung aus der PPD,
   sonst 300 dpi. `cut_options(queue)`: Optionen aus `lpoptions -l`, deren Name oder Titel „Cut“/„Schnitt“ enthält
   (Titel und Werte wie angegeben). Aufrufe mit Zeitlimit; Fehler → `CupsError` (deutsch).
-- **Drucken** (`printer.print_image` für `cups:NAME`): PNG je Etikett in Druckerauflösung, `lp -d NAME -o ppi=<dpi>
-  -o PageSize=<Größe> [Schnitt-Optionen] datei1.png …` – eine Serie = ein Auftrag mit mehreren Dateien; Auftrags-ID
-  aus der Antwort („An die Warteschlange übergeben ✓ (Auftrag QL-12)“). Fehler (Warteschlange gestoppt/unbekannt) →
-  `PrintError`.
-- **Modell-ID** `cups:NAME`: `labels_for_model` = Etiketten der Warteschlange, `capabilities` (Abschneider = es gibt
-  eine Schnitt-Option, kein Rot, `tested` = nein).
+- **Drucken** (`printer.print_image` für `cups:NAME`): ein PDF mit einer Seite je Etikett in Druckerauflösung
+  (Seite = Etikett), `lp -d NAME -o media=<Größe> -o print-scaling=none -o orientation-requested=3
+  -o fit-to-page=false [-o PageSize=<Größe des Treibers>] [Schnitt-Optionen] -- etiketten.pdf` – eine Serie = ein
+  Auftrag, ein Dokument (keine Grenze von 1000 Dateien, „am Ende schneiden“ gilt für den Auftrag); Auftrags-ID aus
+  der Antwort („An die Druckwarteschlange übergeben ✓ (Auftrag QL-12)“). Fehler (Warteschlange gestoppt/unbekannt) →
+  `PrintError`. Befehle mit `LC_MESSAGES=C` (Antworten englisch, Namen UTF-8), Namen geprüft (kein `/`, kein `-`
+  am Anfang).
+- **Modell-ID** `cups:NAME`: `labels_for_model` = Etiketten der Warteschlange, `capabilities` (Schneiden bestimmt der
+  Treiber – Reiter SERIE –, kein Rot, `tested` = nein; ohne CUPS zu fragen).
+- **Nicht blockieren:** die Liste der Warteschlangen liest ein Hintergrund-Thread (alle 30 s, `lpstat -e` findet auch
+  Drucker im Netz); Treiber-Angaben werden beim Wählen gelesen und 5 min gemerkt, Fehler nicht.
+- **Nie automatisch:** „Automatisch“ nimmt Brother direkt › Zebra direkt › Netzwerk – CUPS-Warteschlangen nur, wenn
+  gewählt (sonst landete man ohne QL auf dem Bürolaser).
 
 ## 3 – Zebra direkt (ZPL)
 
@@ -65,7 +72,8 @@ eines schon an CUPS übergebenen Auftrags (geht über die Druckerverwaltung des
   Auflösung des Druckers.
 - **ZPL:** `^XA ^PW<Breite> ^LL<Länge> ^MM<Modus> ^FO0,0 ^GFA,…(Bild als Hex, Zeilen komprimiert nach Zebra-ASCII)
   ^FS ^PQ1 ^XZ` je Etikett; Serie = ein Datenstrom. Schnitt-Modus (Reiter SERIE): Abreißen (T), Schneiden (C),
-  Ablösen (P). Senden roh an `/dev/usb/lpN` bzw. TCP 9100 (Zeitlimit wie Brother-Netzwerk).
+  Ablösen (P), gespeichert je Drucker (URI). Senden roh an `/dev/usb/lpN` bzw. TCP 9100 (Zeitlimit wie
+  Brother-Netzwerk).
 - **Modell-ID** `zpl:203` / `zpl:300`; URIs `zpl+file:///dev/usb/lpN`, `zpl+tcp://host:9100`.
 - **Referenztests:** ZPL eines festen Testetiketts je Auflösung als SHA-256 (wie die Brother-Referenzen).
 
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index eca1f30..1293c27 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -50,8 +50,9 @@ def _add_output_options(p: argparse.ArgumentParser) -> None:
                                          "Drucker); Standard aus den Einstellungen")
     p.add_argument("-p", "--printer", default="auto",
                    help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, "
-                        "cups:NAME (Warteschlange, siehe 'labelwerk printers')")
-    p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network", "cups"],
+                        "cups:NAME (Warteschlange, siehe 'labelwerk printers'), "
+                        "zpl+file:///dev/usb/lpN bzw. zpl+tcp://IP (Zebra, mit -m zpl:203/300/600)")
+    p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network", "cups", "zebra"],
                    help="Standard: aus dem Drucker (tcp:// → network)")
     p.add_argument("--no-cut", action="store_true")
     p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")
@@ -63,8 +64,8 @@ _UNSET = object()   # -s nicht angegeben (None bedeutet „auto“)
 def _parser() -> argparse.ArgumentParser:
     p = argparse.ArgumentParser(prog=desktop.APP_NAME)
     p.add_argument("-m", "--model", default="auto",
-                   help="auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700; "
-                        "siehe 'labelwerk printers'")
+                   help="auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700, "
+                        "zpl:300 (Zebra), cups:NAME; siehe 'labelwerk printers'")
     sub = p.add_subparsers(dest="cmd", required=True)
 
     sub.add_parser("labels", help="Etiketten für das Modell auflisten")
@@ -116,6 +117,8 @@ _NOT_DETECTED = {
                "Adresse angeben mit -p tcp://IP",
     "cups": "Keine CUPS-Warteschlange gefunden (Drucker in der Druckerverwaltung einrichten).\n"
             "Angeben mit -p cups:NAME",
+    "zebra": "Kein Zebra-Drucker gefunden.\n"
+             "Angeben mit -p zpl+file:///dev/usb/lpN bzw. -p zpl+tcp://IP und -m zpl:203",
 }
 
 
@@ -131,7 +134,7 @@ def _target(args: argparse.Namespace, settings) -> printers.Printer | None:
     found = _all_printers(settings)
     if wanted != "auto":
         return printers.printer_for(wanted, found)
-    if backend in ("network", "cups"):
+    if backend in ("network", "cups", "zebra"):
         found = [p for p in found if p.source == backend]
     elif backend == "linux_kernel":
         found = [p for p in found if p.source == "usb"]
@@ -140,7 +143,8 @@ def _target(args: argparse.Namespace, settings) -> printers.Printer | None:
 
 def _all_printers(settings) -> list[printers.Printer]:
     """Direkt per USB, eingetragene Netzwerkdrucker und Warteschlangen von CUPS."""
-    direct = printers.usb_printers() + printers.network_printers(network_entries(settings))
+    direct = (printers.usb_printers() + printers.zebra_printers(dpi=settings.zebra_dpi)
+              + printers.network_printers(network_entries(settings)))
     return direct + printers.cups_printers(direct, wait=True)
 
 
@@ -150,7 +154,8 @@ def _resolve_model(model: str, target: printers.Printer | None, settings) -> str
     if model != "auto":
         if not printers.is_model(model):
             raise ValueError(f"Unbekanntes Druckermodell {model!r} – erlaubt: "
-                             f"{', '.join(printers.SUPPORTED_MODELS)} oder cups:NAME")
+                             f"{', '.join(printers.SUPPORTED_MODELS)}, zpl:203/300/600 oder "
+                             "cups:NAME")
         return model
     return printers.effective_model(target, settings.printer_model, settings.last_model)
 
@@ -205,7 +210,9 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
 
     try:
         status = prn.print_image(img, args.label, model=args.model, printer=args.printer,
-                                 backend=args.backend, cut=not args.no_cut)
+                                 backend={"zebra": "zpl"}.get(args.backend, args.backend),
+                                 cut=not args.no_cut,
+                                 options=load_settings().printer_options.get(args.model, {}))
     except prn.PrintError as e:
         print(e, file=sys.stderr)
         return 2
@@ -231,7 +238,8 @@ def _show_printers(model: str) -> int:
     print(f"Wirksames Modell: {model}")
     print("Unterstützt: " + ", ".join(
         f"{m}{'' if printers.capabilities(m).tested else ' (ungeprüft)'}"
-        for m in printers.SUPPORTED_MODELS) + ", CUPS-Warteschlangen cups:NAME (ungeprüft)")
+        for m in printers.SUPPORTED_MODELS)
+          + ", Zebra zpl:203/300/600 (ungeprüft), CUPS-Warteschlangen cups:NAME (ungeprüft)")
     return 0
 
 
diff --git a/src/labelwerk/cups.py b/src/labelwerk/cups.py
index 3877c32..522189f 100644
--- a/src/labelwerk/cups.py
+++ b/src/labelwerk/cups.py
@@ -59,11 +59,13 @@ class Queue:
 
 @dataclass(frozen=True)
 class CutOption:
-    """Schnitt-Option des Treibers: Schlüssel, Titel und Werte (wie ``lpoptions -l``)."""
+    """Schnitt-Option des Treibers: Schlüssel, Titel und Werte (wie ``lpoptions -l``);
+    ``labels``: Anzeige der Werte (sonst die Werte selbst)."""
     key: str
     title: str
     choices: tuple[str, ...]
     default: str
+    labels: tuple[str, ...] = ()
 
 
 @dataclass(frozen=True)
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 8defa0b..f177f0f 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -20,9 +20,9 @@ from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFileD
 from .. import barcodes, clipart, favorites, series
 from ..desktop import APP_NAME
 from ..detect import brother_busy
-from .. import cups
+from .. import cups, zpl
 from ..printers import (UNTESTED_HINT, Printer, capabilities, choose, cups_printers,
-                        effective_model, network_printers, usb_printers)
+                        effective_model, network_printers, usb_printers, zebra_printers)
 from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, Series, TextObject
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
@@ -1448,7 +1448,8 @@ class MainWindow(QMainWindow):
         Erscheinen eines USB-Druckers ggf. Medium prüfen."""
         tip = ""
         try:
-            direct = usb_printers() + network_printers(network_entries(self.settings))
+            direct = (usb_printers() + zebra_printers(dpi=self.settings.zebra_dpi)
+                      + network_printers(network_entries(self.settings)))
             found = direct + cups_printers(direct, keep=self.settings.printer)
             busy = not any(p.source == "usb" for p in found) and brother_busy()
         except OSError:
@@ -1539,18 +1540,25 @@ class MainWindow(QMainWindow):
 
     def _update_cut_choices(self) -> None:
         """Reiter SERIE: Schnitt nach dem Drucker – Brother: nach jedem/nur am Ende bzw. ohne
-        Abschneider der Hinweis; CUPS: die Schnitt-Optionen seines Treibers."""
+        Abschneider der Hinweis; CUPS: die Schnitt-Optionen seines Treibers; Zebra: der Modus."""
         panel = self.panel("series")
+        chosen = self.settings.printer_options.get(self._options_key(), {})
         if self.model.startswith("cups:"):
-            options = cups.queue_info(self.model[len("cups:"):]).cut_options
-            panel.set_driver_cuts(options, self.settings.printer_options.get(self.model, {}))
+            panel.set_driver_cuts(cups.queue_info(self.model[len("cups:"):]).cut_options, chosen)
+        elif zpl.is_model(self.model):
+            panel.set_driver_cuts((zpl.CUT_OPTION,), chosen)
         else:
             panel.set_cutter(capabilities(self.model).cutter)
 
+    def _options_key(self) -> str:
+        """Unter diesem Schlüssel stehen die Druck-Optionen in den Einstellungen: das Modell
+        („cups:NAME“ bzw. „zpl:203“ – die Nummer lpN eines USB-Geräts wechselt beim Einstecken)."""
+        return self.model
+
     def _driver_cut_chosen(self, key: str, value: str) -> None:
-        """Treiber-Option zum Schneiden gewählt – gilt für diesen Drucker (Einstellungen)."""
-        if self.model.startswith("cups:"):
-            self.settings.printer_options.setdefault(self.model, {})[key] = value
+        """Schnitt-Option bzw. Modus gewählt – gilt für diesen Drucker (Einstellungen)."""
+        if self.model.startswith("cups:") or zpl.is_model(self.model):
+            self.settings.printer_options.setdefault(self._options_key(), {})[key] = value
             self._save_settings()
 
     def _fit_label(self) -> None:
@@ -1877,8 +1885,8 @@ class MainWindow(QMainWindow):
         self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
         self.result.style().polish(self.result)
         self.result.setText("Drucke …")
-        options = (self.settings.printer_options.get(printer.uri, {})
-                   if printer is not None and printer.source == "cups" else {})
+        options = (self.settings.printer_options.get(model, {})
+                   if model.startswith("cups:") or zpl.is_model(model) else {})
         worker = PrintWorker(image, doc.label_id, model, cut_every,
                              printer=printer.uri if printer else None, options=options)
         self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
diff --git a/src/labelwerk/gui/panels/series.py b/src/labelwerk/gui/panels/series.py
index 7e0fbe9..e24208d 100644
--- a/src/labelwerk/gui/panels/series.py
+++ b/src/labelwerk/gui/panels/series.py
@@ -349,16 +349,16 @@ class SeriesPanel(Panel):
         self.driver_box.hide()
 
     def set_driver_cuts(self, options, chosen: dict[str, str]) -> None:
-        """Drucker über CUPS: statt „Nach jedem Etikett/Nur am Ende“ die Schnitt-Optionen seines
-        Treibers (``cups.CutOption``), gewählt wie in ``chosen`` (sonst der Standard des Treibers);
-        ohne solche Optionen der Hinweis, dass der Treiber das bestimmt."""
+        """Drucker über CUPS bzw. Zebra: statt „Nach jedem Etikett/Nur am Ende“ die Schnitt-Optionen
+        seines Treibers bzw. der Modus (``cups.CutOption``), gewählt wie in ``chosen`` (sonst der
+        Standard); ohne solche Optionen der Hinweis, dass der Treiber das bestimmt."""
         while self.driver_grid.count():
             self.driver_grid.takeAt(0).widget().deleteLater()
         self.driver_cuts = {}
         for row, option in enumerate(options):
             combo = QComboBox()
-            for choice in option.choices:
-                combo.addItem(choice, choice)
+            for choice, text in zip(option.choices, option.labels or option.choices):
+                combo.addItem(text, choice)
             combo.setCurrentIndex(max(0, combo.findData(chosen.get(option.key, option.default))))
             combo.currentIndexChanged.connect(
                 lambda _=0, key=option.key, box=combo: self.driver_cut_chosen.emit(
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 470989c..683a775 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -16,7 +16,7 @@ from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                                QTabWidget,
                                QVBoxLayout, QWidget)
 
-from .. import favorites, shortcuts
+from .. import favorites, shortcuts, zpl
 from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
 from ..labels import get_label, labels_for_model
 from ..printer import DEFAULT_MODEL
@@ -131,6 +131,14 @@ class SettingsDialog(QDialog):
         self.printer_model.setToolTip("Nur nötig, wenn labelwerk das Modell nicht erkennt "
                                       "(gilt dann und ohne angeschlossenen Drucker)")
         form.addRow("Druckermodell", self.printer_model)
+        self.zebra_dpi = QComboBox()
+        self.zebra_dpi.addItem("Automatisch (erkannt)", 0)
+        for dpi in zpl.RESOLUTIONS:
+            self.zebra_dpi.addItem(f"{dpi} dpi", dpi)
+        self.zebra_dpi.setCurrentIndex(max(0, self.zebra_dpi.findData(settings.zebra_dpi)))
+        self.zebra_dpi.setToolTip("Auflösung der Zebra-Drucker am USB, falls labelwerk sie nicht "
+                                  "richtig erkennt (sonst 203 dpi)")
+        form.addRow("Zebra-Auflösung", self.zebra_dpi)
         self.network = QTableWidget(0, 3)
         self.network.setHorizontalHeaderLabels(["Name", "Adresse", "Modell"])
         self.network.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
@@ -327,7 +335,7 @@ class SettingsDialog(QDialog):
         self.network.insertRow(row)
         self.network.setItem(row, 0, QTableWidgetItem(name))
         self.network.setItem(row, 1, QTableWidgetItem(host))
-        combo = _model_combo(None)
+        combo = _model_combo(None, zebra=True)
         combo.setCurrentIndex(max(0, combo.findData(model)))
         self.network.setCellWidget(row, 2, combo)
 
@@ -373,6 +381,7 @@ class SettingsDialog(QDialog):
             printer_model=self.printer_model.currentData(),
             last_model=self._last_model,
             printer_options=dict(self._printer_options),
+            zebra_dpi=self.zebra_dpi.currentData(),
             network_printers=self._network_values() or [],
             shortcuts={action_id: seq for action_id, seq in self._keys.items()
                        if not _same(seq, shortcuts.action(action_id).default)},
@@ -394,13 +403,17 @@ class SettingsDialog(QDialog):
         super().accept()
 
 
-def _model_combo(automatic: str | None) -> QComboBox:
-    """Druckermodelle (ungeprüfte gekennzeichnet); ``automatic``: erster Eintrag mit Wert ""."""
+def _model_combo(automatic: str | None, zebra: bool = False) -> QComboBox:
+    """Druckermodelle (ungeprüfte gekennzeichnet); ``automatic``: erster Eintrag mit Wert "";
+    ``zebra``: auch Zebra (ZPL) je Auflösung (Netzwerkdrucker)."""
     combo = QComboBox()
     if automatic is not None:
         combo.addItem(automatic, "")
     for model in SUPPORTED_MODELS:
         combo.addItem(model if capabilities(model).tested else f"{model} – ungeprüft", model)
+    if zebra:
+        for dpi in zpl.RESOLUTIONS:
+            combo.addItem(f"Zebra (ZPL) {dpi} dpi – ungeprüft", zpl.model_for(dpi))
     return combo
 
 
diff --git a/src/labelwerk/labels.py b/src/labelwerk/labels.py
index 3c808bc..bd130f6 100644
--- a/src/labelwerk/labels.py
+++ b/src/labelwerk/labels.py
@@ -10,7 +10,7 @@ from brother_ql.labels import Color, FormFactor, LabelsManager
 from .printers import capabilities
 
 DPI = 300  # Druckauflösung der QL-Drucker
-DPI_RANGE = (100, 600)       # Auflösungen anderer Drucker
+DPI_RANGE = (100, 610)       # Auflösungen anderer Drucker (Zebra „600 dpi“ = 24 Punkte/mm = 610)
 SIZE_MM = (5.0, 300.0)       # Kanten fester Etiketten anderer Drucker
 _SIZED = re.compile(r"(\d{1,3}(?:\.\d)?)x(\d{1,3}(?:\.\d)?)mm@(\d{2,3})")
 
@@ -90,7 +90,11 @@ def get_label(label_id: str) -> Label:
 def labels_for_model(model: str) -> list[Label]:
     """Etiketten, die ``model`` drucken kann (``printers.capabilities``): bis zu seiner Breite,
     ohne P-touch-Bänder, Rot/Schwarz nur bei Zweifarb-Modellen; CUPS-Warteschlange („cups:NAME“):
-    die Größen ihres Treibers in seiner Auflösung; unbekanntes Modell → ValueError."""
+    die Größen ihres Treibers in seiner Auflösung; Zebra („zpl:203“): ``zpl.MEDIA``; unbekanntes
+    Modell → ValueError."""
+    from . import zpl                          # zpl liest diese Datei
+    if zpl.is_model(model):
+        return [get_label(i) for i in zpl.label_ids(model)]
     if isinstance(model, str) and model.startswith("cups:"):
         from . import cups                     # cups liest diese Datei
         return [get_label(i) for i in cups.queue_info(model[len("cups:"):]).label_ids()]
diff --git a/src/labelwerk/printer.py b/src/labelwerk/printer.py
index e2b1bf7..0f3ca19 100644
--- a/src/labelwerk/printer.py
+++ b/src/labelwerk/printer.py
@@ -160,13 +160,17 @@ def print_image(
     gesendeter Teil läuft zu Ende), ``progress(gedruckt, alle)`` nach jedem. ``backend``: None =
     aus der URI (``tcp://`` → Netzwerk: ein Auftrag – der Drucker meldet dort keinen Status).
     ``cups:NAME``: ein Auftrag an die CUPS-Warteschlange (``options``: Treiber-Optionen, z. B.
-    Schnitt); Status ``{"outcome": "sent", "job": Kennung}``."""
+    Schnitt); Status ``{"outcome": "sent", "job": Kennung}``. ``zpl+file://…``/``zpl+tcp://…``:
+    Zebra, ein Datenstrom (``options["mode"]``: "" wie am Drucker, T/C/P); Status
+    ``{"outcome": "sent"}``."""
     backend = backend or backend_for(printer)
     images = [image] if isinstance(image, Image.Image) else list(image)
     if label_id not in {label.id for label in labels_for_model(model)}:
         raise PrintError(f"Etikett {label_id!r} passt nicht zum Drucker ({model}).")
     if backend == "cups":
         return _print_cups(printer[len("cups:"):], images, label_id, options, cancelled)
+    if backend == "zpl":
+        return _print_zpl(printer, images, options, cancelled)
     if backend == "network":
         _reachable(printer)
     part = MAX_JOB_EACH if cut_every == 1 else min(cut_every, MAX_CUT_EVERY)
@@ -207,6 +211,20 @@ def _print_cups(name: str, images: list[Image.Image], label_id: str,
     return {"outcome": "sent", "did_print": False, "job": job.id}
 
 
+def _print_zpl(uri: str, images: list[Image.Image], options: dict[str, str] | None,
+               cancelled: Callable[[], bool] | None) -> dict:
+    """Zebra: alle Etiketten als ein ZPL-Datenstrom (der Drucker meldet keinen Status)."""
+    from . import zpl
+    if cancelled is not None and cancelled():
+        raise PrintCancelled(0, len(images))
+    mode = (options or {}).get("mode", "")
+    try:
+        zpl.send(zpl.stream(images, mode if mode in zpl.MODES else ""), uri)
+    except zpl.ZplError as e:
+        raise PrintError(str(e)) from None
+    return {"outcome": "sent", "did_print": False}
+
+
 def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
     try:
         status = send(instructions=data, printer_identifier=printer,
diff --git a/src/labelwerk/printers.py b/src/labelwerk/printers.py
index a2e35a6..9dcc4c1 100644
--- a/src/labelwerk/printers.py
+++ b/src/labelwerk/printers.py
@@ -5,6 +5,7 @@ Modell es ist; die Fähigkeiten (Etikettenbreite, Abschneider, Zweifarbdruck, L
 brother_ql (``capabilities``). Erkannt wird über sysfs ohne USB-Zugriff: Modell aus der
 IEEE-1284-Kennung des Druckers, sonst aus dem USB-Produktnamen, sonst aus der Produkt-ID.
 Netzwerkdrucker stehen in den Einstellungen; erkannt wird dort nichts (kein Netzverkehr).
+Andere Hersteller: CUPS-Warteschlangen (``cups:NAME``) und Zebra direkt (ZPL, ``zpl:203``).
 """
 from __future__ import annotations
 
@@ -54,9 +55,11 @@ GENERIC_LENGTH = (150, 11811)               # Endlosband gibt es bei anderen Dru
 
 
 def is_model(model) -> bool:
-    """Bekanntes Modell: Brother-QL oder eine CUPS-Warteschlange („cups:NAME“)."""
-    from . import cups
-    return isinstance(model, str) and (model in SUPPORTED_MODELS or model.startswith(CUPS)
+    """Bekanntes Modell: Brother-QL, eine CUPS-Warteschlange („cups:NAME“) oder Zebra
+    („zpl:203“)."""
+    from . import cups, zpl
+    return isinstance(model, str) and (model in SUPPORTED_MODELS or zpl.is_model(model)
+                                       or model.startswith(CUPS)
                                        and cups.valid_name(model[len(CUPS):]))
 
 
@@ -64,6 +67,9 @@ def capabilities(model: str) -> Capabilities:
     if isinstance(model, str) and model.startswith(CUPS) and is_model(model):
         # Schneiden bestimmt der Treiber (Reiter SERIE) – ohne CUPS zu fragen
         return Capabilities(model, False, False, 300, GENERIC_LENGTH, False)
+    from . import zpl
+    if zpl.is_model(model):                 # Schneiden: der Modus im Reiter SERIE
+        return Capabilities(model, False, False, 104, GENERIC_LENGTH, False)
     m = _models().get(model)
     if m is None:
         raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
@@ -88,7 +94,7 @@ def known_model(name: str | None) -> str | None:
 class Printer:
     """Ein Drucker: ``uri`` wie für ``printer.print_image`` (``file:///dev/usb/lp1`` bzw.
     ``tcp://host:9100``), ``model`` (None = nicht erkannt), ``name`` zur Anzeige, ``source``
-    ``usb`` | ``network``."""
+    ``usb`` | ``network`` (Brother) | ``cups`` | ``zebra``."""
     uri: str
     model: str | None
     name: str
@@ -99,6 +105,8 @@ def backend_for(uri: str) -> str:
     """Weg zum Drucker: brother_ql-Backend zur URI bzw. „cups“."""
     if uri.startswith(CUPS):
         return "cups"
+    if uri.startswith(("zpl+file://", "zpl+tcp://")):
+        return "zpl"
     if uri.startswith("tcp://"):
         return "network"
     if uri.startswith("usb://"):
@@ -141,6 +149,29 @@ def usb_printers(sys_root: str | Path | None = None,
     return found
 
 
+def zebra_printers(sys_root: str | Path | None = None, dev_root: str = "/dev/usb",
+                   dpi: int = 0) -> list[Printer]:
+    """Zebra-Drucker unter ``/dev/usb/lp*`` (Hersteller 0a5f), die ZPL sprechen (EPL-Geräte und
+    Kartendrucker nicht); Auflösung ``dpi`` (Einstellung), sonst aus der IEEE-1284-Kennung bzw.
+    dem Produktnamen, sonst 203 dpi."""
+    from . import zpl
+    found = []
+    for entry in sorted(Path(sys_root or SYS_ROOT).glob("lp*")):
+        iface = (entry / "device").resolve()
+        for node in (iface, *iface.parents):
+            if not (node / "idVendor").exists():
+                continue
+            ieee = _read(iface / "ieee1284_id")
+            if _read(node / "idVendor") == zpl.VENDOR_ID and zpl.speaks_zpl(ieee):
+                name = _ieee1284_model(ieee) or _read(node / "product") or "Zebra"
+                found_dpi = (dpi if dpi in zpl.RESOLUTIONS else None) or zpl.dpi_from_id(ieee) \
+                    or zpl.dpi_from_id(name) or zpl.DEFAULT_DPI
+                found.append(Printer(f"zpl+file://{dev_root}/{entry.name}",
+                                     zpl.model_for(found_dpi), f"{name} · {entry.name}", "zebra"))
+            break
+    return found
+
+
 @dataclass(frozen=True)
 class NetworkEntry:
     """Netzwerkdrucker aus den Einstellungen."""
@@ -150,7 +181,12 @@ class NetworkEntry:
 
 
 def network_printers(entries: list[NetworkEntry]) -> list[Printer]:
-    return [Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, f"{e.name or e.host} · Netzwerk",
+    """Eingetragene Netzwerkdrucker: Brother (``tcp://``) bzw. Zebra (Modell „zpl:…“,
+    ``zpl+tcp://``)."""
+    from . import zpl
+    return [Printer(f"zpl+tcp://{e.host}:{NETWORK_PORT}", e.model, f"{e.name or e.host} · Netzwerk",
+                    "zebra") if zpl.is_model(e.model) else
+            Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, f"{e.name or e.host} · Netzwerk",
                     "network") for e in entries]
 
 
@@ -176,6 +212,9 @@ def printer_for(uri: str, found: list[Printer]) -> Printer:
             return p
     if uri.startswith(CUPS):
         return Printer(uri, uri, f"{uri[len(CUPS):]} · CUPS", "cups")
+    if uri.startswith(("zpl+file://", "zpl+tcp://")):
+        from . import zpl
+        return Printer(uri, zpl.model_for(zpl.DEFAULT_DPI), uri, "zebra")
     model = None
     if uri.startswith("usb://"):
         pid = uri[len("usb://"):].split("/")[0].split(":")[-1].lower().removeprefix("0x")
@@ -194,12 +233,14 @@ def effective_model(printer: Printer | None, fallback: str = "", last: str = "")
 
 
 def cups_printers(direct: list[Printer], keep: str = "", wait: bool = False) -> list[Printer]:
-    """Warteschlangen von CUPS als Drucker; ein Brother-QL, den labelwerk direkt per USB findet,
-    erscheint nicht noch einmal über seine Warteschlange – außer sie ist gewählt (``keep``).
+    """Warteschlangen von CUPS als Drucker; ein Brother-QL bzw. Zebra, den labelwerk direkt per USB
+    findet, erscheint nicht noch einmal über seine Warteschlange – außer sie ist gewählt (``keep``).
     ``wait``: auf CUPS warten (CLI), sonst die zuletzt gelesene Liste (``cups.queues``)."""
     from . import cups
-    brother_direct = any(p.source == "usb" and p.model in SUPPORTED_MODELS for p in direct)
+    doubles = tuple(prefix for prefix, here in (
+        ("usb://brother/ql", any(p.source == "usb" and p.model in SUPPORTED_MODELS for p in direct)),
+        ("usb://zebra", any(p.source == "zebra" and p.uri.startswith("zpl+file://")
+                            for p in direct))) if here)
     return [Printer(CUPS + q.name, CUPS + q.name, f"{q.name} · CUPS", "cups")
             for q in cups.queues(wait=wait)
-            if CUPS + q.name == keep
-            or not (brother_direct and q.device.lower().startswith("usb://brother/ql"))]
+            if CUPS + q.name == keep or not (doubles and q.device.lower().startswith(doubles))]
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 5ec92b3..5837905 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -15,6 +15,7 @@ from .clipart import RECENT_LIMIT
 from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .fonts import DEFAULT_FAMILY
 from .labels import labels_for_model, sized_label
+from . import zpl
 from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model, is_model
 from .storage import RECENT_FILES
 
@@ -42,7 +43,8 @@ class Settings:
     printer_model: str = ""                # Ersatz, wenn das Modell nicht erkannt wird; "" = keins
     last_model: str = ""                   # zuletzt erkanntes Modell (gilt ohne Drucker)
     network_printers: list[dict] = field(default_factory=list)   # {name, host, model}
-    printer_options: dict[str, dict[str, str]] = field(default_factory=dict)  # URI → Treiber-Optionen
+    printer_options: dict[str, dict[str, str]] = field(default_factory=dict)  # Modell → Druck-Optionen
+    zebra_dpi: int = 0                  # Auflösung der Zebras am USB, 0 = erkannt
     shortcuts: dict[str, str] = field(default_factory=dict)   # nur geänderte Kürzel, "" = keins
     warnings: list[str] = field(default_factory=list, compare=False, repr=False)
 
@@ -75,6 +77,7 @@ def _rules(model: str | None = None) -> dict:
             v == "" or v.startswith(("file://", "tcp://", "usb://", "cups:"))),
         "printer_model": lambda v: v == "" or v in SUPPORTED_MODELS,
         "last_model": lambda v: v == "" or is_model(v),
+        "zebra_dpi": lambda v: v in (0, *zpl.RESOLUTIONS) and not isinstance(v, bool),
         "printer_options": lambda v: isinstance(v, dict) and all(
             isinstance(k, str) and isinstance(o, dict)
             and all(_option_word(a) and _option_word(b) for a, b in o.items())
@@ -149,11 +152,13 @@ def _text_list(key: str, value: list, warnings: list[str]) -> list[str]:
 
 
 def _network(value: list, warnings: list[str]) -> list[dict]:
-    """Netzwerkdrucker: Einträge mit Host (ohne Leerzeichen, ohne Schema) und bekanntem Modell;
+    """Netzwerkdrucker: Einträge mit Host (ohne Leerzeichen, ohne Schema) und bekanntem Modell
+    (Brother-QL oder Zebra „zpl:203“);
     ungültige einzeln verworfen (mit Hinweis)."""
     valid = [{"name": e.get("name") or "", "host": e["host"].strip(), "model": e["model"]}
              for e in value if isinstance(e, dict) and isinstance(e.get("host"), str)
-             and valid_host(e["host"]) and e.get("model") in SUPPORTED_MODELS
+             and valid_host(e["host"]) and (e.get("model") in SUPPORTED_MODELS
+                                             or zpl.is_model(e.get("model")))
              and isinstance(e.get("name", ""), str)]
     if len(valid) != len(value):
         warnings.append("Einstellung 'network_printers': ungültige Einträge verworfen.")
diff --git a/src/labelwerk/zpl.py b/src/labelwerk/zpl.py
new file mode 100644
index 0000000..d1eab59
--- /dev/null
+++ b/src/labelwerk/zpl.py
@@ -0,0 +1,243 @@
+"""Zebra-Etikettendrucker direkt in ihrer Druckersprache ZPL – ohne Treiber und ohne Qt.
+
+Jedes Etikett wird ein Bild (``^GFA``, Zeilen komprimiert nach dem ASCII-Verfahren von Zebra) in
+der Auflösung des Druckers; eine Serie ist ein Datenstrom, Etikett für Etikett erzeugt. Gesendet
+wird roh an ``/dev/usb/lpN`` (``zpl+file://…``) bzw. an TCP-Port 9100 (``zpl+tcp://host:9100``).
+Der Drucker meldet nichts zurück – „gesendet“ heißt nicht „gedruckt“.
+
+Auflösung: Zebra rechnet in Punkten je mm – „203 dpi“ sind 8, „300 dpi“ 12, „600 dpi“ 24 Punkte/mm
+(203,2 / 304,8 / 609,6 dpi). Die Etiketten tragen deshalb 203, 305 bzw. 610 dpi.
+"""
+from __future__ import annotations
+
+import os
+import re
+import select
+import socket
+import stat
+from collections.abc import Iterable, Iterator
+from urllib.parse import urlsplit
+
+from PIL import Image
+
+from .cups import CutOption
+from .labels import sized_id
+
+PREFIX = "zpl:"                    # Modell-ID: zpl:203, zpl:300, zpl:600 (Name wie beim Hersteller)
+URI_PREFIXES = ("zpl+file://", "zpl+tcp://")
+RESOLUTIONS = (203, 300, 600)
+DOTS_PER_MM = {203: 8, 300: 12, 600: 24}
+DEFAULT_DPI = 203
+VENDOR_ID = "0a5f"
+PORT = 9100
+TIMEOUT_S = 5                      # Verbindung aufbauen
+WRITE_TIMEOUT_S = 30               # je Datenblock: so lange darf der Drucker keine Daten annehmen
+CHUNK = 64 * 1024
+MAX_GRAPHIC = 99_999               # Bytes je ^GFA (ältere Firmware) – größere Bilder in Streifen
+# gängige Etiketten (Breite × Höhe in mm): 2×1", 57×32, 3×2", 4×2", 4×3", 4×4", 4×6" …
+MEDIA = ((51, 25), (57, 32), (38, 25), (60, 40), (76, 51), (102, 51), (102, 76), (102, 102),
+         (102, 152))
+# Nach dem Druck: "" = wie am Drucker eingestellt (kein ^MM), sonst ^MMT/C/P
+MODES = {"": "Wie am Drucker eingestellt", "T": "Abreißen", "C": "Schneiden (nur mit Abschneider)",
+         "P": "Ablösen (nur mit Spender)"}
+CUT_OPTION = CutOption("mode", "Nach dem Druck", tuple(MODES), "", tuple(MODES.values()))
+
+
+class ZplError(Exception):
+    """Senden gescheitert (Meldung für Nutzer)."""
+
+
+def is_model(model) -> bool:
+    return isinstance(model, str) and model.startswith(PREFIX) and model[len(PREFIX):] in {
+        str(d) for d in RESOLUTIONS}
+
+
+def model_for(dpi: int) -> str:
+    return f"{PREFIX}{dpi}"
+
+
+def dpi_of(model: str) -> int:
+    """Auflösung der Etiketten eines Modells: Punkte je mm × 25,4 (gerundet)."""
+    return round(DOTS_PER_MM[int(model[len(PREFIX):])] * 25.4)
+
+
+def label_ids(model: str) -> list[str]:
+    """Etiketten eines Zebra-Modells: ``MEDIA`` in seiner Auflösung."""
+    return [sized_id(w, h, dpi_of(model)) for w, h in MEDIA]
+
+
+def dpi_from_id(text: str) -> int | None:
+    """Auflösung aus einer IEEE-1284-Kennung oder einem Namen („ZD420-300dpi“, „ZT410 600 dpi“)."""
+    m = re.search(r"(203|300|600)\s*dpi", text, re.I)
+    return int(m[1]) if m else None
+
+
+def speaks_zpl(ieee1284: str) -> bool:
+    """Versteht der Drucker ZPL? Nennt seine Kennung Befehlssätze (``CMD:``/``COMMAND SET:``)
+    ohne ZPL (EPL-Geräte wie LP 2844, Kartendrucker), nicht; ohne Angabe: ja."""
+    for part in ieee1284.split(";"):
+        key, _, value = part.partition(":")
+        if key.strip().upper() in ("CMD", "COMMAND SET"):
+            return "ZPL" in value.upper()
+    return True
+
+
+# --- ZPL ------------------------------------------------------------------------------------------
+def _count(n: int) -> str:
+    """Wiederholungszahl nach Zebra: g–z = 20…400, G–Y = 1…19 (zusammengesetzt, n ≤ 419)."""
+    high, low = divmod(n, 20)
+    return (chr(ord("f") + high) if high else "") + (chr(ord("F") + low) if low else "")
+
+
+def _compress_row(row: str) -> str:
+    """Eine Hex-Zeile: Folgen gleicher Zeichen mit Zahl davor, Nullen am Ende als „,“."""
+    stripped = row.rstrip("0")
+    if not stripped:
+        return ","
+    out, i = [], 0
+    while i < len(stripped):
+        j = i
+        while j < len(stripped) and stripped[j] == stripped[i]:
+            j += 1
+        n = j - i
+        while n > 0:
+            take = min(n, 419)
+            out.append((_count(take) if take > 1 else "") + stripped[i])
+            n -= take
+        i = j
+    return "".join(out) + ("," if len(stripped) < len(row) else "")
+
+
+def _bits(image: Image.Image) -> tuple[bytes, int]:
+    """Bild als Bitfolge für ZPL (1 = Punkt), Zeilen auf ganze Bytes mit Weiß aufgefüllt."""
+    img = image.convert("L").point(lambda v: 0 if v < 128 else 255).convert("1")
+    row_bytes = (img.width + 7) // 8
+    padded = Image.new("1", (row_bytes * 8, img.height), 1)    # Füllbits weiß, nicht schwarz
+    padded.paste(img, (0, 0))
+    return bytes(b ^ 0xFF for b in padded.tobytes()), row_bytes   # Pillow: 1 = weiß
+
+
+def _graphic(data: bytes, row_bytes: int, first: int, last: int) -> str:
+    rows, previous = [], None
+    for y in range(first, last):
+        row = data[y * row_bytes:(y + 1) * row_bytes].hex().upper()
+        rows.append(":" if row == previous else _compress_row(row))
+        previous = row
+    total = row_bytes * (last - first)
+    return f"^GFA,{total},{total},{row_bytes},{''.join(rows)}"
+
+
+def graphic(image: Image.Image) -> str:
+    """``^GFA`` eines Bilds (schwarz = Punkt): Bytes je Zeile, komprimierte Zeilen, gleiche Zeile
+    hintereinander als „:“ – höchstens ``MAX_GRAPHIC`` Bytes, sonst ``fields`` nehmen."""
+    data, row_bytes = _bits(image)
+    return _graphic(data, row_bytes, 0, image.height)
+
+
+def fields(image: Image.Image) -> str:
+    """Bild als ``^FO0,y^GFA…^FS``-Felder: in waagrechten Streifen zu höchstens ``MAX_GRAPHIC``
+    Bytes (ältere Firmware nimmt nicht mehr je Grafik)."""
+    data, row_bytes = _bits(image)
+    band = max(1, MAX_GRAPHIC // row_bytes)
+    return "".join(f"^FO0,{y}{_graphic(data, row_bytes, y, min(y + band, image.height))}^FS"
+                   for y in range(0, image.height, band))
+
+
+def label(image: Image.Image, mode: str = "") -> bytes:
+    """ZPL eines Etiketts: ``^XA [^MM<Modus>] ^PW ^LL ^LH0,0 ^FO…^GFA…^FS ^PQ1 ^XZ``."""
+    if mode not in MODES:
+        raise ValueError(f"Unbekannter Modus {mode!r} – erlaubt: {', '.join(m for m in MODES if m)}")
+    head = f"^MM{mode}" if mode else ""
+    return (f"^XA{head}^PW{image.width}^LL{image.height}^LH0,0{fields(image)}^PQ1^XZ\n"
+            .encode("ascii"))
+
+
+def stream(images: Iterable[Image.Image], mode: str = "") -> Iterator[bytes]:
+    """ZPL Etikett für Etikett (eine Serie braucht nicht alles auf einmal im Speicher)."""
+    for image in images:
+        yield label(image, mode)
+
+
+def build(images: list[Image.Image], mode: str = "") -> bytes:
+    """ZPL für ``images`` (je ein Etikett in Druckerauflösung, Breite quer zum Druckkopf)."""
+    return b"".join(stream(images, mode))
+
+
+# --- Senden ---------------------------------------------------------------------------------------
+def _is_device(info: os.stat_result) -> bool:
+    """Druckergerät (Zeichengerät); Tests ersetzen die Prüfung."""
+    return stat.S_ISCHR(info.st_mode)
+
+
+def send(data: bytes | Iterable[bytes], uri: str) -> None:
+    """ZPL roh an den Drucker: ``zpl+file:///dev/usb/lpN`` bzw. ``zpl+tcp://host[:port]``;
+    ``data`` auch Stück für Stück (``stream``)."""
+    chunks = [data] if isinstance(data, bytes) else data
+    if uri.startswith("zpl+file://"):
+        return _send_device(chunks, uri[len("zpl+file://"):])
+    if uri.startswith("zpl+tcp://"):
+        return _send_network(chunks, uri)
+    raise ZplError(f"Keine Zebra-Adresse: {uri}")
+
+
+def _send_device(chunks: Iterable[bytes], path: str) -> None:
+    """An das Gerät: ohne es anzulegen, nicht blockierend mit Zeitlimit je Block (usblp wartet
+    sonst endlos, wenn Papier fehlt oder der Drucker pausiert), jeder Block ganz geschrieben."""
+    try:
+        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
+    except FileNotFoundError:
+        raise ZplError(f"Zebra-Drucker nicht gefunden: {path} – eingeschaltet, Kabel?") from None
+    except PermissionError:
+        raise ZplError(f"Keine Berechtigung für {path} – Benutzer in Gruppe 'lp'?") from None
+    except OSError as e:
+        raise ZplError(f"Zebra-Drucker nicht erreichbar: {path} ({e.strerror or e})") from None
+    sent = 0
+    try:
+        if not _is_device(os.fstat(fd)):
+            raise ZplError(f"{path} ist kein Druckergerät")
+        poller = select.poll()
+        poller.register(fd, select.POLLOUT)
+        for chunk in chunks:
+            view = memoryview(chunk)
+            while view:
+                if not poller.poll(WRITE_TIMEOUT_S * 1000):
+                    raise ZplError(f"Zebra-Drucker nimmt keine Daten an ({sent} Bytes gesendet) – "
+                                   "Papier, Farbband, Pause?")
+                try:
+                    n = os.write(fd, view[:CHUNK])
+                except BlockingIOError:
+                    continue
+                view, sent = view[n:], sent + n
+    except OSError as e:
+        raise ZplError(f"Senden an {path} abgebrochen nach {sent} Bytes ({e.strerror or e})") from None
+    finally:
+        os.close(fd)
+
+
+def _send_network(chunks: Iterable[bytes], uri: str) -> None:
+    """Über TCP: Zeitlimit für den Aufbau, danach je Block (ein langsamer Drucker darf einen
+    großen Auftrag annehmen)."""
+    parts = urlsplit(uri[len("zpl+"):])
+    try:
+        port = parts.port or PORT
+    except ValueError:
+        raise ZplError(f"Ungültige Adresse: {uri}") from None
+    if not parts.hostname:
+        raise ZplError(f"Ungültige Adresse: {uri}")
+    try:
+        conn = socket.create_connection((parts.hostname, port), timeout=TIMEOUT_S)
+    except OSError as e:
+        raise ZplError(f"Zebra-Drucker {parts.hostname} nicht erreichbar ({e.strerror or e}) – "
+                       "eingeschaltet, im selben Netz, Adresse richtig?") from None
+    sent = 0
+    with conn:
+        conn.settimeout(WRITE_TIMEOUT_S)
+        try:
+            for chunk in chunks:
+                view = memoryview(chunk)
+                while view:
+                    n = conn.send(view[:CHUNK])
+                    view, sent = view[n:], sent + n
+        except OSError as e:
+            raise ZplError(f"Verbindung zu {parts.hostname} abgebrochen nach {sent} Bytes "
+                           f"({e.strerror or e})") from None
diff --git a/tools/golden.py b/tools/golden.py
index 36f533e..bd6b38e 100644
--- a/tools/golden.py
+++ b/tools/golden.py
@@ -5,8 +5,8 @@
 
 Je Modell ein festes Testetikett (nur Formen, keine Schrift – Schriftversionen dürfen nicht
 zählen) als SHA-256 der Rasterdaten: Endlos 62 mm mit und ohne Schnitt, gestanzt 62×29, bei
-breiten Modellen 102 mm, bei Zweifarb-Modellen 62red. Beweist, was gesendet wird – nicht, was
-gedruckt wird. Die Werte hängen an brother_ql (pyproject: auf 1.3.x festgelegt) – nach einem
+breiten Modellen 102 mm, bei Zweifarb-Modellen 62red; Zebra (ZPL) je Auflösung 57×32 mm,
+102×152 mm mit Schneiden und eine Serie. Beweist, was gesendet wird – nicht, was gedruckt wird. Die Werte hängen an brother_ql (pyproject: auf 1.3.x festgelegt) – nach einem
 Update der Bibliothek prüfen und neu erzeugen.
 """
 from __future__ import annotations
@@ -18,10 +18,14 @@ from pathlib import Path
 
 from PIL import Image, ImageDraw
 
-from labelwerk.labels import get_label, labels_for_model
+from labelwerk import zpl
+from labelwerk.labels import get_label, labels_for_model, sized_id
 from labelwerk.printer import build_instructions
 from labelwerk.printers import SUPPORTED_MODELS
 
+ZPL_MODELS = tuple(zpl.model_for(dpi) for dpi in zpl.RESOLUTIONS)
+MODELS = SUPPORTED_MODELS + ZPL_MODELS
+
 GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "raster.json"
 
 
@@ -42,6 +46,11 @@ def test_image(label_id: str, length: int = 200) -> Image.Image:
 
 
 def cases(model: str) -> dict[str, bytes]:
+    if zpl.is_model(model):
+        small, large = (sized_id(w, h, zpl.dpi_of(model)) for w, h in ((57, 32), (102, 152)))
+        return {"57x32": zpl.build([test_image(small)]),
+                "102x152-schneiden": zpl.build([test_image(large)], "C"),
+                "57x32-serie": zpl.build([test_image(small)] * 3)}
     available = {label.id for label in labels_for_model(model)}
     out = {"62": build_instructions(test_image("62"), "62", model),
            "62-ohne-schnitt": build_instructions(test_image("62"), "62", model, cut=False),
@@ -56,7 +65,7 @@ def cases(model: str) -> dict[str, bytes]:
 
 def digests() -> dict[str, dict[str, str]]:
     return {model: {name: hashlib.sha256(data).hexdigest() for name, data in cases(model).items()}
-            for model in SUPPORTED_MODELS}
+            for model in MODELS}
 
 
 def main(argv: list[str]) -> int:
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2466 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-19-fremdhersteller-design.md src/labelwerk/cli.py src/labelwerk/cups.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/series.py src/labelwerk/gui/settings_dialog.py src/labelwerk/labels.py src/labelwerk/printer.py src/labelwerk/printers.py src/labelwerk/settings.py src/labelwerk/zpl.py tests/golden/raster.json tests/gui/test_gui_zebra.py tests/test_cli.py tests/test_golden.py tests/test_settings.py tests/test_zpl.py tools/golden.py
git commit -m "Zebra direkt (ZPL): Erkennung per USB (Auflösung aus der Kennung) und als Netzwerkdrucker, Etiketten in seiner Auflösung, ^GFA mit Zebra-Kompression, Modus Abreißen/Schneiden/Ablösen im Reiter SERIE, CLI zpl+file:// / zpl+tcp://, Referenztests; README/Doku

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Abnahme (manuell, durch den Nutzer)

- [ ] Brother-Druck unverändert (QL-600, 62 mm und 62×29); Referenztests grün.
- [ ] Falls eine CUPS-Warteschlange eingerichtet ist: im Druckermenü „Name · CUPS“, nicht automatisch gewählt; Etiketten des Treibers im Reiter PAPIER; Reiter SERIE zeigt die Schnitt-Optionen des Treibers.
- [ ] `labelwerk printers`, `labelwerk -m zpl:203 labels`, `labelwerk -m zpl:203 print "Test" -l 57x32mm@203 --preview z.png` (Vorschau 456 × 256 Punkte).
- [ ] Einstellungen: Netzwerkdrucker mit Modell „Zebra (ZPL) 203 dpi“ eintragen.
