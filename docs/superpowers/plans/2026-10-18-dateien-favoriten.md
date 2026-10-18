# Neu/Öffnen/Speichern + Favoriten (Etappe 3c) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Etiketten als Datei speichern und öffnen, Favoriten als Vorlagen mit Vorschau und Direktdruck, Zuletzt geöffnet, Start mit Datei oder Favorit, Doppelklick im Dateimanager.

**Architecture:** Kern `storage.py` (Format *.labelwerk, Dateien als fremde Eingabe streng geprüft) und `favorites.py` (Ordner); in der GUI hält `FileSession` Pfad, gespeicherten Stand und Dialoge und ersetzt das Dokument an Ort und Stelle; der Reiter ★ zeigt Knöpfe, Favoriten und Zuletzt geöffnet; `desktop.py` meldet den Dateityp an.

**Tech Stack:** Python ≥ 3.10, Pillow, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-18-dateien-favoriten-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-3c-fix2`), nach jedem Task volle Suite grün mit Exit-Code 0 (1535 → 1622 → 1683 → 1694); jeder Schritt von einem Reviewer geprüft und korrigiert (Kern: EPS/Ghostscript über Bilddaten, Struktur/Grenzen/NaN, atomares Speichern mit Rechten/Symlinks, Namen; GUI: Rolle stellt Dateien nicht mehr um, Ansicht nach Renderfehler, Direktdruck prüft Etikett/Rolle, Speichern-Dialog mit Endung; Desktop: Exec-Quoting, Tests ohne externe Programme).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Dateien sind fremde Eingabe: nie ein Traceback, nie ein externes Programm beim Laden; Bilddaten nur PNG.
- Kern bleibt **Qt-frei** (`storage.py`, `favorites.py`, `settings.py`, `desktop.py`); **Vorschau = Druck**.
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten (XDG-Ordner isoliert), ohne externe Programme (update-mime-database …), ohne echten Dateimanager oder Dialog; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen und Kommentare auf Deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Kern – Etiketten als Datei (*.labelwerk), Favoriten-Ordner, Einstellungen

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/document.py`
- Create: `src/labelwerk/favorites.py`
- Modify: `src/labelwerk/files.py`
- Modify: `src/labelwerk/gui/image_import.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/render.py`
- Modify: `src/labelwerk/settings.py`
- Create: `src/labelwerk/storage.py`
- Modify: `tests/gui/test_gui_settings.py`
- Create: `tests/test_favorites.py`
- Modify: `tests/test_files.py`
- Modify: `tests/test_settings.py`
- Create: `tests/test_storage.py`

**Interfaces / Produces:** `storage.py`: `FORMAT`, `VERSION`, `SUFFIX`, `RECENT_FILES`, Schemata `SPAN`/`PARAGRAPH`/`TEXT`/`IMAGE`/`DOCUMENT`, `StorageError`, `os_reason` (ab Task 3; Task 1: `_reason`), `to_dict`, `from_dict`, `save(doc, path)`, `load(path)`, `add_recent_file`; `favorites.py`: `Favorite(name, path)`, `favorites_dir`, `favorites`, `find`, `add(doc, name, overwrite)`, `rename`, `remove`; Einstellungen `recent_files`/`start_favorite` (Dialog reicht durch); `Image.open(..., formats=…)` in files/render/document/image_import.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index 7b258ad..92628a2 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -377,3 +377,10 @@ def test_dialog_keeps_symbol_lists(qtbot):
     qtbot.addWidget(dialog)
     values = dialog.values()
     assert (values.symbols_recent, values.symbols_favorites) == (["labelwerk/erde"], ["iso7010/W012"])
+
+
+def test_dialog_keeps_recent_files_and_start_favorite(qtbot):
+    dialog = SettingsDialog(Settings(recent_files=["/a.labelwerk"], start_favorite="Absender"))
+    qtbot.addWidget(dialog)
+    values = dialog.values()
+    assert (values.recent_files, values.start_favorite) == (["/a.labelwerk"], "Absender")
diff --git a/tests/test_favorites.py b/tests/test_favorites.py
new file mode 100644
index 0000000..36687e3
--- /dev/null
+++ b/tests/test_favorites.py
@@ -0,0 +1,96 @@
+"""Favoriten (Etappe 3c): gespeicherte Etiketten im Favoriten-Ordner."""
+import pytest
+
+from labelwerk import favorites
+from labelwerk.document import Document, TextObject
+from labelwerk.storage import load
+
+
+def _doc(text="Absender"):
+    return Document("62", objects=[TextObject(text)])
+
+
+def test_folder_follows_xdg_data_home(tmp_path, monkeypatch):
+    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
+    assert favorites.favorites_dir() == tmp_path / "labelwerk" / "favoriten"
+
+
+def test_no_folder_no_favorites():
+    assert favorites.favorites() == []
+
+
+def test_add_and_list_sorted_without_case():
+    favorites.add(_doc("Z"), "zebra")
+    favorites.add(_doc("A"), "Absender")
+    favorites.add(_doc("R"), "regal")
+    assert [f.name for f in favorites.favorites()] == ["Absender", "regal", "zebra"]
+    assert load(favorites.find("Absender").path).objects[0].text == "A"
+
+
+def test_add_existing_name_needs_overwrite():
+    favorites.add(_doc("alt"), "Absender")
+    with pytest.raises(FileExistsError):
+        favorites.add(_doc("neu"), "Absender")
+    favorites.add(_doc("neu"), "Absender", overwrite=True)
+    assert load(favorites.find("Absender").path).objects[0].text == "neu"
+
+
+@pytest.mark.parametrize("name", ["", "   ", "a/b", ".versteckt", "a\\b", "x" * 201])
+def test_invalid_names(name):
+    with pytest.raises(ValueError, match="Name"):
+        favorites.add(_doc(), name)
+
+
+def test_name_is_trimmed():
+    favorite = favorites.add(_doc(), "  Regal 3  ")
+    assert favorite.name == "Regal 3" and favorite.path.name == "Regal 3.labelwerk"
+
+
+def test_rename_and_remove():
+    favorite = favorites.add(_doc(), "alt")
+    renamed = favorites.rename(favorite, "neu")
+    assert [f.name for f in favorites.favorites()] == ["neu"] and renamed.name == "neu"
+    favorites.add(_doc(), "anderer")
+    with pytest.raises(FileExistsError):
+        favorites.rename(renamed, "anderer")
+    favorites.remove(renamed)
+    assert [f.name for f in favorites.favorites()] == ["anderer"]
+
+
+def test_other_files_and_hidden_files_are_not_favorites():
+    folder = favorites.favorites_dir()
+    folder.mkdir(parents=True)
+    (folder / "notiz.txt").write_text("x")
+    (folder / ".versteckt.labelwerk").write_text("{}")
+    favorites.add(_doc(), "echt")
+    assert [f.name for f in favorites.favorites()] == ["echt"]
+
+
+def test_find_unknown_is_none():
+    assert favorites.find("gibt es nicht") is None
+
+
+@pytest.mark.parametrize("name", ["a\nb", "a\x07b", "😀" * 60])
+def test_control_characters_and_too_long_names_in_bytes(name):
+    with pytest.raises(ValueError, match="Name"):
+        favorites.add(_doc(), name)
+
+
+def test_names_are_normalized_nfc():
+    favorites.add(_doc(), "Café")
+    assert [f.name for f in favorites.favorites()] == ["Café"]
+    with pytest.raises(FileExistsError):
+        favorites.add(_doc(), "Café")
+
+
+def test_sorting_is_stable_for_case_variants():
+    favorites.add(_doc(), "absender")
+    favorites.add(_doc(), "Absender")
+    assert [f.name for f in favorites.favorites()] == ["Absender", "absender"]
+
+
+def test_rename_missing_favorite_gives_german_message():
+    favorite = favorites.add(_doc(), "weg")
+    favorites.remove(favorite)
+    with pytest.raises(OSError, match="nicht gefunden"):
+        favorites.rename(favorite, "neu")
diff --git a/tests/test_files.py b/tests/test_files.py
index f0229e3..58eba1e 100644
--- a/tests/test_files.py
+++ b/tests/test_files.py
@@ -573,3 +573,16 @@ def test_ink_box_threshold_and_empty():
     assert ink_box(img) is None
     img.paste((249, 249, 249), (5, 5, 20, 20))
     assert ink_box(img) == (5, 5, 20, 20)
+
+
+def test_postscript_disguised_as_png_is_refused_without_ghostscript(tmp_path, monkeypatch):
+    """Pillow erkennt das Format am Inhalt – EPS liefe sonst durch Ghostscript."""
+    import subprocess
+    for name in ("Popen", "call", "check_call", "check_output", "run"):
+        monkeypatch.setattr(subprocess, name, lambda *a, **k: pytest.fail("Ghostscript gestartet"))
+    path = tmp_path / "bild.png"
+    path.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 30 30\nshowpage\n%%EOF\n")
+    with pytest.raises(ValueError, match="kein lesbares Bild"):
+        load_image(path)
+    with pytest.raises(ValueError, match="kein lesbares Bild"):
+        load_file(path)
diff --git a/tests/test_settings.py b/tests/test_settings.py
index ecb9b39..448270a 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -261,3 +261,31 @@ def test_save_is_atomic_and_leaves_no_temp_files(tmp_path, monkeypatch):
         save_settings(Settings(margin_mm=5), path)
     assert load_settings(path).margin_mm == 3.0          # alte Datei unversehrt
     assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]
+
+
+# --- Dateien ------------------------------------------------------------------------
+def test_recent_files_and_start_favorite_default_and_roundtrip(tmp_path):
+    s = Settings()
+    assert (s.recent_files, s.start_favorite) == ([], None)
+    path = tmp_path / "s.json"
+    save_settings(Settings(recent_files=["/a.labelwerk", "/b.labelwerk"], start_favorite="Absender"),
+                  path)
+    loaded = load_settings(path)
+    assert loaded.recent_files == ["/a.labelwerk", "/b.labelwerk"]
+    assert loaded.start_favorite == "Absender" and loaded.warnings == []
+
+
+def test_recent_files_are_cleaned_when_loading(tmp_path):
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps({"recent_files": [f"/{i}.labelwerk" for i in range(12)] + ["/0.labelwerk", 3]}))
+    s = load_settings(path)
+    assert s.recent_files == [f"/{i}.labelwerk" for i in range(10)]
+    assert any("recent_files" in w for w in s.warnings)
+
+
+@pytest.mark.parametrize("value", [3, "", "  "])
+def test_invalid_start_favorite_falls_back(tmp_path, value):
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps({"start_favorite": value}))
+    s = load_settings(path)
+    assert s.start_favorite is None and any("start_favorite" in w for w in s.warnings)
diff --git a/tests/test_storage.py b/tests/test_storage.py
new file mode 100644
index 0000000..28371ea
--- /dev/null
+++ b/tests/test_storage.py
@@ -0,0 +1,334 @@
+"""Etiketten als Datei (Etappe 3c): Format *.labelwerk, Rundweg, Fehler."""
+import base64
+import json
+
+import pytest
+from PIL import Image, ImageDraw
+
+from labelwerk import storage
+from labelwerk.document import Document, ImageObject, Paragraph, Span, TextObject
+from labelwerk.render import render_document
+from labelwerk.storage import StorageError, load, save
+
+SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
+       b'<rect width="40" height="20" fill="black"/></svg>')
+
+
+def _picture():
+    img = Image.new("RGB", (120, 60), "white")
+    ImageDraw.Draw(img).rectangle((10, 10, 109, 49), fill=(200, 30, 30))
+    return img
+
+
+def _document():
+    text = TextObject([Paragraph([Span("Absender ", family="DejaVu Serif", size_pt=12),
+                                  Span("fett", bold=True, italic=True, underline=True)], "left"),
+                       Paragraph([Span("Zeile 2", bold=False)], "right")],
+                      size_pt=10, fit=True, x_mm=2.5, y_mm=3, w_mm=40, h_mm=12, rotation=90)
+    centred = TextObject("mittig")                       # Position None = mittig
+    image = ImageObject.from_image(_picture(), 300, "bild.png", crop=(10, 10, 110, 50))
+    image.x_mm, image.y_mm, image.rotation = 30, 4, 180
+    image.mode, image.threshold, image.invert, image.keep_ratio = "photo", 90, True, False
+    vector = ImageObject.from_image(Image.new("RGB", (40, 20), "black"), 96, "Symbol: Erde",
+                                    svg=SVG)
+    vector.x_mm, vector.y_mm = 5, 20
+    return Document("62", length_mm=45, orientation="horizontal", margin_mm=2,
+                    objects=[text, centred, image, vector])
+
+
+def test_roundtrip_gives_the_same_document(tmp_path):
+    doc = _document()
+    path = tmp_path / "etikett.labelwerk"
+    save(doc, path)
+    assert load(path) == doc
+
+
+def test_roundtrip_gives_the_same_print_image(tmp_path):
+    doc = _document()
+    path = tmp_path / "etikett.labelwerk"
+    save(doc, path)
+    assert render_document(load(path)).tobytes() == render_document(doc).tobytes()
+
+
+def test_file_is_versioned_readable_json(tmp_path):
+    path = tmp_path / "e.labelwerk"
+    save(_document(), path)
+    data = json.loads(path.read_text(encoding="utf-8"))
+    assert (data["format"], data["version"]) == ("labelwerk", 1)
+    objects = data["document"]["objects"]
+    assert [o["type"] for o in objects] == ["text", "text", "image", "image"]
+    assert objects[0]["paragraphs"][0]["spans"][0]["text"] == "Absender "
+    assert base64.b64decode(objects[3]["svg"]) == SVG and objects[2]["svg"] is None
+    assert "Absender" in path.read_text(encoding="utf-8")   # Umlaute/Text lesbar, nicht maskiert
+
+
+def test_save_is_atomic_and_leaves_no_temp_files(tmp_path, monkeypatch):
+    path = tmp_path / "e.labelwerk"
+    save(Document("62", objects=[TextObject("alt")]), path)
+    before = path.read_bytes()
+
+    def broken(*args, **kwargs):
+        raise OSError(28, "Kein Platz")
+    monkeypatch.setattr(storage.os, "replace", broken)
+    with pytest.raises(OSError, match="nicht gespeichert"):
+        save(Document("62", objects=[TextObject("neu")]), path)
+    assert path.read_bytes() == before
+    assert [p.name for p in tmp_path.iterdir()] == ["e.labelwerk"]
+
+
+def test_unknown_fields_are_ignored_and_missing_get_defaults(tmp_path):
+    data = storage.to_dict(Document("62", objects=[TextObject("x")]))
+    data["document"]["zukunft"] = 1
+    data["document"]["objects"][0]["schatten"] = True
+    del data["document"]["objects"][0]["rotation"]
+    del data["document"]["margin_mm"]
+    doc = storage.from_dict(data)
+    assert doc.objects[0].rotation == 0 and doc.margin_mm == 1.0 and doc.objects[0].text == "x"
+
+
+# --- Fehler ---------------------------------------------------------------------------
+def _write(tmp_path, content):
+    path = tmp_path / "kaputt.labelwerk"
+    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
+    return path
+
+
+def _valid():
+    return storage.to_dict(_document())
+
+
+def test_missing_file(tmp_path):
+    with pytest.raises(StorageError, match="nicht gefunden"):
+        load(tmp_path / "fehlt.labelwerk")
+
+
+def test_not_json(tmp_path):
+    with pytest.raises(StorageError, match="keine labelwerk-Datei"):
+        load(_write(tmp_path, "{kein json"))
+
+
+def test_foreign_json(tmp_path):
+    with pytest.raises(StorageError, match="keine labelwerk-Datei"):
+        load(_write(tmp_path, {"format": "anderes", "version": 1}))
+
+
+def test_newer_version(tmp_path):
+    data = _valid()
+    data["version"] = 2
+    with pytest.raises(StorageError, match="neueren labelwerk"):
+        load(_write(tmp_path, data))
+
+
+@pytest.mark.parametrize("change, message", [
+    (lambda d: d["document"].update(orientation="schräg"), "orientation"),
+    (lambda d: d["document"].update(margin_mm="viel"), "margin_mm"),
+    (lambda d: d["document"].update(objects={}), "objects"),
+    (lambda d: d["document"]["objects"][0].update(type="kreis"), "Objektart"),
+    (lambda d: d["document"]["objects"][0].update(rotation=45), "rotation"),
+    (lambda d: d["document"]["objects"][0].update(x_mm=True), "x_mm"),
+    (lambda d: d["document"]["objects"][0]["paragraphs"][0].update(align="mitte"), "align"),
+    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text=3), "text"),
+    (lambda d: d["document"]["objects"][2].update(mode="bunt"), "mode"),
+    (lambda d: d["document"]["objects"][2].update(crop=[1, 2, 3]), "crop"),
+    (lambda d: d["document"]["objects"][2].update(png="kein base64!"), "Bilddaten"),
+    (lambda d: d["document"]["objects"][2].update(png=base64.b64encode(b"kein png").decode()),
+     "Bilddaten"),
+])
+def test_invalid_values_give_german_error_naming_the_field(tmp_path, change, message):
+    data = _valid()
+    change(data)
+    with pytest.raises(StorageError, match=message):
+        load(_write(tmp_path, data))
+
+
+def test_error_names_the_file(tmp_path):
+    with pytest.raises(StorageError, match="kaputt.labelwerk"):
+        load(_write(tmp_path, "nicht json"))
+
+
+# --- Zuletzt geöffnet -------------------------------------------------------------------
+def test_add_recent_file_newest_first_without_duplicates_and_limit():
+    recent = [f"/a/{i}.labelwerk" for i in range(10)]
+    assert storage.add_recent_file(recent, "/a/3.labelwerk")[:2] == ["/a/3.labelwerk", "/a/0.labelwerk"]
+    new = storage.add_recent_file(recent, "/neu.labelwerk")
+    assert len(new) == 10 and new[0] == "/neu.labelwerk" and "/a/9.labelwerk" not in new
+
+
+def test_schemas_cover_every_dataclass_field():
+    """Neue Felder müssen ins Schema – sonst gingen sie beim Speichern still verloren."""
+    from dataclasses import fields
+    for cls, schema, extra in ((Span, storage.SPAN, set()), (Paragraph, storage.PARAGRAPH, {"spans"}),
+                               (TextObject, storage.TEXT, {"paragraphs"}),
+                               (ImageObject, storage.IMAGE, set()),
+                               (Document, storage.DOCUMENT, {"objects"})):
+        assert {f.name for f in fields(cls)} == set(schema) | extra, cls.__name__
+
+
+# --- Nachbesserungen: fremde und kaputte Dateien ---------------------------------------
+EPS = (b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 30 30\n"
+       b"newpath 0 0 moveto 30 30 lineto stroke showpage\n%%EOF\n")
+
+
+@pytest.fixture
+def no_subprocess(monkeypatch):
+    """Kein externes Programm (Ghostscript) darf beim Laden oder Rendern starten."""
+    import subprocess
+
+    def blocked(*args, **kwargs):
+        raise AssertionError(f"externes Programm gestartet: {args[:1]}")
+    for name in ("Popen", "call", "check_call", "check_output", "run"):
+        monkeypatch.setattr(subprocess, name, blocked)
+
+
+def _image_with(png_bytes):
+    data = _valid()
+    data["document"]["objects"][2]["png"] = base64.b64encode(png_bytes).decode()
+    data["document"]["objects"][2]["crop"] = None
+    return data
+
+
+def test_postscript_in_image_data_is_refused_without_ghostscript(tmp_path, no_subprocess):
+    with pytest.raises(StorageError, match="Bilddaten"):
+        load(_write(tmp_path, _image_with(EPS)))
+
+
+@pytest.mark.parametrize("fmt", ["JPEG", "TIFF", "BMP", "GIF"])
+def test_only_png_is_accepted_as_image_data(tmp_path, fmt):
+    import io
+    buffer = io.BytesIO()
+    Image.new("RGB", (8, 8), "white").save(buffer, fmt)
+    with pytest.raises(StorageError, match="Bilddaten"):
+        load(_write(tmp_path, _image_with(buffer.getvalue())))
+
+
+def test_damaged_png_stream_is_refused_when_loading(tmp_path):
+    import io, zlib, struct
+    buffer = io.BytesIO()
+    Image.new("RGB", (40, 40), "red").save(buffer, "PNG")
+    raw = bytearray(buffer.getvalue())
+    start = raw.index(b"IDAT")                                  # Daten kaputt, CRC passend
+    length = struct.unpack(">I", raw[start - 4:start])[0]
+    raw[start + 4:start + 4 + length] = b"\x00" * length
+    raw[start + 4 + length:start + 8 + length] = struct.pack(
+        ">I", zlib.crc32(bytes(raw[start:start + 4 + length])))
+    with pytest.raises(StorageError, match="Bilddaten"):
+        load(_write(tmp_path, _image_with(bytes(raw))))
+
+
+def test_huge_image_is_refused(tmp_path):
+    import io
+    buffer = io.BytesIO()
+    Image.new("1", (7000, 10)).save(buffer, "PNG")
+    with pytest.raises(StorageError, match="zu groß"):
+        load(_write(tmp_path, _image_with(buffer.getvalue())))
+
+
+def test_crop_outside_the_image_is_refused(tmp_path):
+    data = _valid()
+    data["document"]["objects"][2]["crop"] = [0, 0, 9999, 10]
+    with pytest.raises(StorageError, match="crop"):
+        load(_write(tmp_path, data))
+
+
+@pytest.mark.parametrize("raw", [
+    '{"format": "labelwerk", "version": 1, "document": {"margin_mm": NaN}}',
+    '{"format": "labelwerk", "version": 1, "document": {"margin_mm": Infinity}}',
+    '{"format": "labelwerk", "version": 1, "document": {"length_mm": 1e400}}',
+])
+def test_non_finite_numbers_are_refused(tmp_path, raw):
+    with pytest.raises(StorageError):
+        load(_write(tmp_path, raw))
+
+
+def test_deeply_nested_json_is_refused(tmp_path):
+    with pytest.raises(StorageError, match="beschädigt"):
+        load(_write(tmp_path, "[" * 200000))
+
+
+@pytest.mark.parametrize("change, message", [
+    (lambda d: d["document"]["objects"][0].update(paragraphs=["abc"]), "Objekt 1"),
+    (lambda d: d["document"]["objects"][0]["paragraphs"][0].update(spans=["abc"]), "Objekt 1"),
+    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].pop("text"), "text"),
+    (lambda d: d["document"]["objects"][0].update(size_pt=1e308), "size_pt"),
+    (lambda d: d["document"]["objects"][0].update(size_pt=0), "size_pt"),
+    (lambda d: d["document"]["objects"][0].update(x_mm=1e9), "x_mm"),
+    (lambda d: d["document"]["objects"][0].update(w_mm=-5), "w_mm"),
+    (lambda d: d["document"]["objects"][0].update(rotation=90.0), "rotation"),
+    (lambda d: d["document"]["objects"][2].update(w_mm=1e6), "w_mm"),
+    (lambda d: d["document"]["objects"][2].update(dpi=0), "dpi"),
+    (lambda d: d["document"]["objects"][2].update(threshold=300), "threshold"),
+    (lambda d: d["document"]["objects"][2].update(page=0), "page"),
+    (lambda d: d["document"].update(length_mm=0), "length_mm"),
+    (lambda d: d["document"].update(margin_mm=99), "margin_mm"),
+    (lambda d: d["document"].update(label_id="999"), "Etikett"),
+    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="a\nb"),
+     "Zeilenumbruch"),
+    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="a b"),
+     "Zeilenumbruch"),
+    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="\ud800"),
+     "text"),
+])
+def test_structure_and_bounds_are_checked(tmp_path, change, message):
+    data = _valid()
+    change(data)
+    with pytest.raises(StorageError, match=message):
+        load(_write(tmp_path, data))
+
+
+def test_loaded_documents_render_without_unexpected_errors(tmp_path):
+    """Was ``load`` annimmt, scheitert beim Rendern höchstens mit ``ValueError``."""
+    data = _valid()
+    data["document"]["objects"][0].update(size_pt=1000, x_mm=-9999, w_mm=300, h_mm=300)
+    doc = load(_write(tmp_path, data))
+    try:
+        render_document(doc)
+    except ValueError:
+        pass
+
+
+def test_empty_paragraphs_become_one_empty_line(tmp_path):
+    data = _valid()
+    data["document"]["objects"][1]["paragraphs"] = []
+    doc = load(_write(tmp_path, data))
+    assert doc.objects[1].text == "" and len(doc.objects[1].paragraphs) == 1
+
+
+def test_utf8_with_bom_is_read(tmp_path):
+    path = tmp_path / "bom.labelwerk"
+    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(_valid()).encode())
+    assert load(path) == _document()
+
+
+def test_messages_are_german(tmp_path):
+    folder = tmp_path / "ordner.labelwerk"
+    folder.mkdir()
+    with pytest.raises(StorageError, match="ist ein Ordner"):
+        load(folder)
+    with pytest.raises(OSError, match="Ordner fehlt"):
+        save(_document(), tmp_path / "fehlt" / "x.labelwerk")
+
+
+def test_save_keeps_permissions_and_follows_symlinks(tmp_path):
+    import os, stat
+    target = tmp_path / "echt.labelwerk"
+    save(_document(), target)
+    assert stat.S_IMODE(target.stat().st_mode) == 0o666 & ~_umask()
+    os.chmod(target, 0o640)
+    link = tmp_path / "link.labelwerk"
+    link.symlink_to(target)
+    save(Document("62", objects=[TextObject("neu")]), link)
+    assert link.is_symlink() and load(target).objects[0].text == "neu"
+    assert stat.S_IMODE(target.stat().st_mode) == 0o640
+
+
+def _umask():
+    import os
+    mask = os.umask(0)
+    os.umask(mask)
+    return mask
+
+
+def test_long_file_name_can_be_saved(tmp_path):
+    path = tmp_path / ("x" * 240 + ".labelwerk")
+    save(_document(), path)
+    assert load(path) == _document()
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_storage.py, tests/test_favorites.py, neue Fälle in tests/test_settings.py, tests/test_files.py, tests/gui/test_gui_settings.py) schlagen fehl (ImportError `labelwerk.storage`/`favorites` bzw. fehlende Felder), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 9a40c48..3da4931 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -19,7 +19,8 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Bildschirmfoto (Etappe 3d-2b): Knopf BILDSCHIRMFOTO im Reiter Bild – labelwerk blendet sich aus, der Desktop zeigt seine Auswahl (XDG-Portal), das Bild kommt mit 300 dpi aufs Etikett; ohne Portal Hinweis auf Zwischenablage + Strg+V.
 - SVG-Dateien sind Vektorbilder: in jeder Größe scharf gerastert (Etappe 3d-2c).
 - Symbole/ClipArt (Etappe 3d-2c): Knopf SYMBOL im Reiter Bild – Fenster „Symbol einfügen“ (bleibt offen; Suche über die ganze Bibliothek, Gruppen Zuletzt verwendet/Favoriten/Elektro/Versand/Sicherheit/Allgemein/Eigene, Doppelklick/Enter/Ziehen fügt ein); Symbole 15 mm, Vektor, zugeschnitten.
-- 1535 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Etiketten als Datei (Etappe 3c, Kern): storage (*.labelwerk), Favoriten-Ordner, Einstellungen recent_files/start_favorite.
+- 1622 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -61,7 +62,14 @@ src/labelwerk/
               crop, svg) setzt 1:1-Größe;
               box() (Ausschnitt in Pixeln), natural_mm() (Größe 1:1)
   settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic), `image_crop`/`image_rotate` (Bilder einfügen),
-              `symbols_recent` (höchstens 24)/`symbols_favorites` (Symbol-ids; der Einstellungsdialog reicht sie durch)
+              `symbols_recent` (höchstens 24)/`symbols_favorites` (Symbol-ids), `recent_files` (höchstens 10)/`start_favorite`
+              (der Einstellungsdialog reicht sie durch)
+  storage.py  Etiketten als Datei (*.labelwerk, JSON versioniert, Bilder Base64): to_dict/from_dict, save (atomar), load;
+              Schemata SPAN/PARAGRAPH/TEXT/IMAGE/DOCUMENT (jedes Dataclass-Feld, Test hält gleich); Dateien sind fremde Eingabe:
+              Prüfung je Feld nach Art, Wertebereich (endlich, Grenzen) und Struktur → StorageError (deutsch, mit Dateiname),
+              Bilddaten nur PNG (ganz dekodiert, höchstens MAX_PIXELS), Etikett bekannt; unbekannte Felder übergangen,
+              fehlende = Standard; save atomar (Symlink verfolgt, Rechte bleiben/umask, fsync); add_recent_file
+  favorites.py Favoriten = *.labelwerk in $XDG_DATA_HOME/labelwerk/favoriten: favorites, find, add (overwrite), rename, remove
   clipart.py  Symbol-Bibliothek ohne Qt: catalog() aus clipart_data/clipart.zip (catalog.json + SVGs, einmal ganz gelesen;
               erzeugt von tools/fetch_clipart.py: Tabler Icons MIT ohne Marken (Kategorien Brand und Laundry/Pflegesymbole + Sperrliste tabler_skip, u. a. Michelin),
               ISO 7000/7010 von Wikimedia Commons nur gemeinfrei/CC0 ohne Einschränkungen (Stand fest: tools/clipart/commons.lock.json,
@@ -137,6 +145,7 @@ Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`),
 - Gruppe `lp` gilt erst nach neuer Anmeldung; bis dahin im Terminal `newgrp lp`.
 - Benutzer braucht Gruppe `lp` für `/dev/usb/lpN` (`crw-rw---- root lp`). Erledigt.
 - `Replace media error` = angefordertes Etikett passt nicht zur eingelegten Rolle (Drucker erkennt die DK-Rolle per Sensor).
+- Pillow erkennt Formate am Inhalt: `Image.open` immer mit `formats=[…]` – EPS liefe sonst durch Ghostscript (auch bei „.png“).
 - D-Bus in Tests: nie `dbus-daemon --session`/`dbus-run-session` – deren Standard-Config startet echte Dienste (Portal öffnet Auswahl auf dem Bildschirm); eigene busconfig ohne servicedir.
 - GUI-Tests: jedes Widget bei `qtbot.addWidget` anmelden (sonst Absturz beim Beenden); immer Exit-Code von pytest prüfen, nicht nur „passed“.
 - Statusabfrage (Medium prüfen): Invalidate (200 × 0x00) + ESC @ + ESC i S, Antwort 32 Bytes sofort; brother_ql-Lesen nicht verwenden (kann ohne Zeitlimit blockieren).
diff --git a/src/labelwerk/document.py b/src/labelwerk/document.py
index 647a8e9..e355fc4 100644
--- a/src/labelwerk/document.py
+++ b/src/labelwerk/document.py
@@ -161,7 +161,7 @@ class ImageObject:
         """Ausschnitt (l, t, r, b) in Pixeln – ohne ``crop`` das ganze Bild."""
         if self.crop is not None:
             return self.crop
-        with Image.open(io.BytesIO(self.png)) as img:   # liest nur den Kopf der Datei
+        with Image.open(io.BytesIO(self.png), formats=["PNG"]) as img:   # nur den Kopf
             return (0, 0, *img.size)
 
     def natural_mm(self) -> tuple[float, float]:
@@ -171,7 +171,7 @@ class ImageObject:
 
     def image(self) -> Image.Image:
         """Das Original als RGB-Bild."""
-        with Image.open(io.BytesIO(self.png)) as img:
+        with Image.open(io.BytesIO(self.png), formats=["PNG"]) as img:
             return img.convert("RGB")
 
 
diff --git a/src/labelwerk/favorites.py b/src/labelwerk/favorites.py
new file mode 100644
index 0000000..7e8156b
--- /dev/null
+++ b/src/labelwerk/favorites.py
@@ -0,0 +1,78 @@
+"""Favoriten: gespeicherte Etiketten im Ordner ``$XDG_DATA_HOME/labelwerk/favoriten`` (ohne Qt).
+
+Ein Favorit ist eine ``*.labelwerk``-Datei; sein Name ist der Dateiname ohne Endung. Die GUI
+öffnet ihn als neues, unbenanntes Etikett (Vorlage) – das Original bleibt unverändert.
+"""
+from __future__ import annotations
+
+import os
+import unicodedata
+from dataclasses import dataclass
+from pathlib import Path
+
+from .document import Document
+from .storage import SUFFIX, save
+
+MAX_NAME_BYTES = 200        # Dateiname höchstens 255 Bytes (Endung, Reserve)
+
+
+@dataclass(frozen=True)
+class Favorite:
+    name: str
+    path: Path
+
+
+def favorites_dir() -> Path:
+    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
+    return Path(base) / "labelwerk" / "favoriten"
+
+
+def favorites() -> list[Favorite]:
+    """Alle Favoriten, sortiert ohne Groß/Klein; fehlt der Ordner, keine."""
+    try:
+        paths = [p for p in favorites_dir().iterdir()
+                 if p.is_file() and p.suffix == SUFFIX and not p.name.startswith(".")]
+    except OSError:
+        return []
+    return [Favorite(p.stem, p) for p in sorted(paths, key=lambda p: (p.stem.casefold(), p.stem))]
+
+
+def find(name: str) -> Favorite | None:
+    return next((f for f in favorites() if f.name == name), None)
+
+
+def _checked(name: str) -> str:
+    """Name als Dateiname: NFC (gleich aussehende Namen sind gleich), getrimmt, nicht leer, ohne
+    Pfad- und Steuerzeichen, nicht versteckt, nicht zu lang (in Bytes)."""
+    name = unicodedata.normalize("NFC", name.strip())
+    if (not name or len(name.encode("utf-8")) > MAX_NAME_BYTES or name.startswith(".")
+            or any(c in "/\\" or unicodedata.category(c) == "Cc" for c in name)):
+        raise ValueError(f"Name für den Favoriten ungültig: „{name}“ (nicht leer, nicht zu lang, "
+                         f"ohne / und \\ und Steuerzeichen, nicht mit Punkt beginnend)")
+    return name
+
+
+def add(doc: Document, name: str, overwrite: bool = False) -> Favorite:
+    """Etikett als Favorit speichern; vorhandener Name ohne ``overwrite``: ``FileExistsError``."""
+    name = _checked(name)
+    path = favorites_dir() / f"{name}{SUFFIX}"
+    if path.exists() and not overwrite:
+        raise FileExistsError(f"Favorit „{name}“ gibt es schon")
+    path.parent.mkdir(parents=True, exist_ok=True)
+    save(doc, path)
+    return Favorite(name, path)
+
+
+def rename(favorite: Favorite, name: str) -> Favorite:
+    name = _checked(name)
+    path = favorite.path.with_name(f"{name}{SUFFIX}")
+    if not favorite.path.exists():
+        raise FileNotFoundError(f"Favorit „{favorite.name}“ nicht gefunden")
+    if path.exists() and not path.samefile(favorite.path):     # Groß/Klein-Dateisysteme
+        raise FileExistsError(f"Favorit „{name}“ gibt es schon")
+    favorite.path.rename(path)
+    return Favorite(name, path)
+
+
+def remove(favorite: Favorite) -> None:
+    favorite.path.unlink(missing_ok=True)
diff --git a/src/labelwerk/files.py b/src/labelwerk/files.py
index baec035..14c9062 100644
--- a/src/labelwerk/files.py
+++ b/src/labelwerk/files.py
@@ -16,6 +16,8 @@ from .render import MARGIN
 _IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
 # Bild-Objekte: zusätzlich GIF (erstes Bild), BMP, WebP; SVG rastert die Oberfläche
 _OBJECT_SUFFIXES = (*_IMAGE_SUFFIXES, ".gif", ".bmp", ".webp")
+_IMAGE_FORMATS = ["PNG", "JPEG"]                       # Pillow-Formate zu den Endungen
+_OBJECT_FORMATS = [*_IMAGE_FORMATS, "GIF", "BMP", "WEBP"]
 
 INK = 128            # dunkler gilt als bedruckt
 INK_LEVEL = 250      # Symbole: heller als das zählt beim Zuschneiden als Papier
@@ -50,7 +52,8 @@ def load_image(path: str | Path, page: int = 1,
     with _readable(path):
         if path.suffix.lower() == ".pdf":
             return _load_pdf_page(path, page)
-        with Image.open(path) as src:                  # GIF: erstes Bild
+        # Formate fest: Pillow erkennt sie sonst am Inhalt (EPS liefe durch Ghostscript)
+        with Image.open(path, formats=_OBJECT_FORMATS) as src:     # GIF: erstes Bild
             x_dpi, y_dpi = _file_dpi(src) if dpi is None else (dpi, dpi)
             if src.getexif().get(0x0112, 1) in (5, 6, 7, 8):   # EXIF dreht um 90°
                 x_dpi, y_dpi = y_dpi, x_dpi
@@ -150,7 +153,7 @@ def _pdf_page(path: Path, page: int):
 
 
 def _load_image(path: Path) -> Image.Image:
-    with Image.open(path) as src:
+    with Image.open(path, formats=_IMAGE_FORMATS) as src:
         dpi = float(src.info.get("dpi", (DPI, DPI))[0]) or DPI
         img = to_8bit(src).convert("RGBA")             # 16-Bit-Graustufen skalieren
     img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img).convert("L")
diff --git a/src/labelwerk/gui/image_import.py b/src/labelwerk/gui/image_import.py
index 7003904..7aed391 100644
--- a/src/labelwerk/gui/image_import.py
+++ b/src/labelwerk/gui/image_import.py
@@ -160,7 +160,7 @@ def load_symbol(symbol: Symbol, side_mm: float) -> tuple[Image.Image, float, tup
         sheet = (max(1, round(size.width() * k)), max(1, round(size.height() * k)))
         image, svg = _render(renderer, sheet, (0, 0, *sheet)), None if linked else data
     else:
-        with Image.open(io.BytesIO(data)) as img:
+        with Image.open(io.BytesIO(data), formats=["PNG"]) as img:     # nur PNG (kein EPS)
             image, svg = on_white(img), None
     crop = files.ink_box(image)
     l, t, r, b = crop or (0, 0, *image.size)
@@ -194,7 +194,7 @@ def to_pil(image: QImage) -> Image.Image:
     buffer = QBuffer()
     buffer.open(QIODevice.OpenModeFlag.WriteOnly)
     image.save(buffer, "PNG")
-    with Image.open(io.BytesIO(bytes(buffer.data()))) as img:
+    with Image.open(io.BytesIO(bytes(buffer.data())), formats=["PNG"]) as img:
         return on_white(img)
 
 
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index c240ad7..74a111d 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -44,6 +44,8 @@ class SettingsDialog(QDialog):
         self.path = path
         self.saved: Settings | None = None
         self._symbols = (settings.symbols_recent, settings.symbols_favorites)   # nur durchgereicht
+        self._recent_files = settings.recent_files                             # nur durchgereicht
+        self._start_favorite = settings.start_favorite
         outer = QVBoxLayout(self)
         self.tabs = QTabWidget()
         outer.addWidget(self.tabs)
@@ -292,6 +294,8 @@ class SettingsDialog(QDialog):
             image_rotate=self.image_rotate.isChecked(),
             symbols_recent=list(self._symbols[0]),
             symbols_favorites=list(self._symbols[1]),
+            recent_files=list(self._recent_files),
+            start_favorite=self._start_favorite,
             shortcuts={action_id: seq for action_id, seq in self._keys.items()
                        if not _same(seq, shortcuts.action(action_id).default)},
         )
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 0324072..e98ff66 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -553,7 +553,7 @@ def _vector_source(svg: bytes, png: bytes, crop: tuple[int, int, int, int] | Non
                    size: tuple[int, int], keep_ratio: bool) -> Image.Image:
     """Wie ``_scaled_source``, aber neu gerastert statt skaliert: das Blatt so groß, dass der
     Ausschnitt (Pixel der Vorschau-PNG) genau ``size`` füllt – scharf in jeder Größe."""
-    with Image.open(io.BytesIO(png)) as img:     # liest nur den Kopf der Datei
+    with Image.open(io.BytesIO(png), formats=["PNG"]) as img:     # liest nur den Kopf
         sheet = img.size
     l, t, r, b = crop if crop is not None else (0, 0, *sheet)
     _check_crop((l, t, r, b), sheet)
@@ -598,7 +598,7 @@ def _source(png: bytes, crop: tuple[int, int, int, int] | None) -> Image.Image:
     eines ``bytes``-Objekts, der Schlüssel kostet nach dem ersten Mal fast nichts.
     Das Ergebnis wird geteilt und darf nicht verändert werden.
     """
-    with Image.open(io.BytesIO(png)) as img:
+    with Image.open(io.BytesIO(png), formats=["PNG"]) as img:
         img = img.convert("RGB")
     if crop is not None:
         _check_crop(crop, img.size)
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index a437548..803b939 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -15,6 +15,7 @@ from .clipart import RECENT_LIMIT
 from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .fonts import DEFAULT_FAMILY
 from .labels import labels_for_model
+from .storage import RECENT_FILES
 
 THEMES = ("rawblock", "classic")
 SYMBOL_LISTS = ("symbols_recent", "symbols_favorites")
@@ -34,6 +35,8 @@ class Settings:
     image_rotate: bool = False             # Bilder drehen, wenn sie nur gedreht 1:1 passen
     symbols_recent: list[str] = field(default_factory=list)      # Symbol-ids, neueste zuerst
     symbols_favorites: list[str] = field(default_factory=list)   # Symbol-ids
+    recent_files: list[str] = field(default_factory=list)   # Zuletzt geöffnet (Pfade), neueste zuerst
+    start_favorite: str | None = None      # Favorit, mit dem labelwerk startet; None = leer
     shortcuts: dict[str, str] = field(default_factory=dict)   # nur geänderte Kürzel, "" = keins
     warnings: list[str] = field(default_factory=list, compare=False, repr=False)
 
@@ -58,6 +61,8 @@ def _rules(model: str) -> dict:
         "image_rotate": lambda v: isinstance(v, bool),
         "symbols_recent": lambda v: isinstance(v, list),
         "symbols_favorites": lambda v: isinstance(v, list),
+        "recent_files": lambda v: isinstance(v, list),
+        "start_favorite": lambda v: v is None or (isinstance(v, str) and bool(v.strip())),
     }
 
 
@@ -93,6 +98,8 @@ def load_settings(path: str | Path | None = None, model: str = "QL-600") -> Sett
                 value = float(value)
             elif key in SYMBOL_LISTS:
                 value = _symbol_ids(key, value, settings.warnings)
+            elif key == "recent_files":
+                value = _text_list(key, value, settings.warnings)[:RECENT_FILES]
             setattr(settings, key, value)
         else:
             settings.warnings.append(f"Einstellung {key!r} ungültig ({value!r}) – "
@@ -103,13 +110,18 @@ def load_settings(path: str | Path | None = None, model: str = "QL-600") -> Sett
     return settings
 
 
-def _symbol_ids(key: str, value: list, warnings: list[str]) -> list[str]:
-    """Symbol-ids: ungültige Einträge einzeln verworfen (mit Hinweis), Doppelte entfernt,
-    Zuletzt verwendet auf ``RECENT_LIMIT`` begrenzt."""
+def _text_list(key: str, value: list, warnings: list[str]) -> list[str]:
+    """Liste von Texten: ungültige Einträge einzeln verworfen (mit Hinweis), Doppelte entfernt."""
     valid = [i for i in value if isinstance(i, str) and i]
     if len(valid) != len(value):
         warnings.append(f"Einstellung {key!r}: ungültige Einträge verworfen.")
-    ids = list(dict.fromkeys(valid))
+    return list(dict.fromkeys(valid))
+
+
+def _symbol_ids(key: str, value: list, warnings: list[str]) -> list[str]:
+    """Symbol-ids: ungültige Einträge einzeln verworfen (mit Hinweis), Doppelte entfernt,
+    Zuletzt verwendet auf ``RECENT_LIMIT`` begrenzt."""
+    ids = _text_list(key, value, warnings)
     return ids[:RECENT_LIMIT] if key == "symbols_recent" else ids
 
 
diff --git a/src/labelwerk/storage.py b/src/labelwerk/storage.py
new file mode 100644
index 0000000..99d5550
--- /dev/null
+++ b/src/labelwerk/storage.py
@@ -0,0 +1,308 @@
+"""Etiketten als Datei (*.labelwerk): JSON, versioniert, ohne Qt.
+
+``{"format": "labelwerk", "version": 1, "document": {…}}`` – Objekte mit ``"type"`` (``text`` |
+``image``) und ihren Feldern; Bilddaten (PNG, SVG) Base64. Eine Datei kann von irgendwoher
+stammen: beim Laden wird jedes Feld nach Art, Wertebereich und Struktur geprüft (``StorageError``
+mit deutscher Meldung statt Traceback; was angenommen wird, scheitert beim Rendern höchstens
+verständlich). Bilddaten müssen PNG sein (Pillow erkennt Formate am Inhalt – EPS liefe sonst
+durch Ghostscript) und werden ganz dekodiert. Unbekannte Felder werden übergangen, fehlende
+bekommen den Standardwert. Die Schemata nennen jedes Feld der Dataclasses (ein Test hält sie
+gleich).
+"""
+from __future__ import annotations
+
+import base64
+import binascii
+import io
+import json
+import math
+import os
+import reprlib
+import stat
+from pathlib import Path
+
+from PIL import Image
+
+from .document import (ALIGNMENTS, MAX_MARGIN_MM, ORIENTATIONS, ROTATIONS, Document, ImageObject,
+                       Paragraph, Span, TextObject)
+from .imaging import MAX_PIXELS, MODES
+from .labels import get_label
+
+FORMAT = "labelwerk"
+VERSION = 1
+SUFFIX = ".labelwerk"
+RECENT_FILES = 10
+MAX_FILE_BYTES = 256 * 1024 * 1024    # größere Dateien werden nicht gelesen
+MAX_POSITION_MM = 10_000.0            # Lage eines Objekts (auch weit neben dem Etikett)
+MAX_SIZE_MM = 1_000.0                 # Rahmen, Etikettlänge (QL: höchstens 1 m)
+MAX_SIZE_PT = 1_000.0                 # Schriftgröße (über MAX_PT hinaus, wie scale_text es lässt)
+LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85  "   # gehören zwischen Absätze, nicht in Stücke
+_TMP_PREFIX = ".labelwerk-"
+
+# Feld → Art (siehe ``_KINDS``)
+SPAN = {"text": "span_text", "family": "str?", "size_pt": "pt?", "bold": "bool", "italic": "bool",
+        "underline": "bool"}
+PARAGRAPH = {"align": "align"}                                    # dazu „spans“
+TEXT = {"size_pt": "pt?", "font_path": "str?", "fit": "bool", "x_mm": "pos?", "y_mm": "pos?",
+        "w_mm": "size?", "h_mm": "size?", "rotation": "rotation"}  # dazu „paragraphs“
+IMAGE = {"png": "bytes", "source": "str", "page": "page?", "crop": "crop", "x_mm": "pos",
+         "y_mm": "pos", "w_mm": "size", "h_mm": "size", "rotation": "rotation", "mode": "mode",
+         "threshold": "threshold", "invert": "bool", "keep_ratio": "bool", "dpi": "dpi",
+         "svg": "bytes?"}
+DOCUMENT = {"label_id": "label", "length_mm": "size?", "orientation": "orientation",
+            "margin_mm": "margin"}                                # dazu „objects“
+
+
+def _num(v) -> bool:
+    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
+
+
+def _int(v) -> bool:
+    return isinstance(v, int) and not isinstance(v, bool)
+
+
+def _text(v) -> bool:
+    """Text, der sich als UTF-8 schreiben lässt (keine einzelnen Surrogates)."""
+    if not isinstance(v, str):
+        return False
+    try:
+        v.encode("utf-8")
+    except UnicodeEncodeError:
+        return False
+    return True
+
+
+def _label(v) -> bool:
+    try:
+        get_label(v)
+    except (ValueError, TypeError):
+        return False
+    return True
+
+
+_KINDS = {
+    "str": _text, "bool": lambda v: isinstance(v, bool), "bytes": lambda v: isinstance(v, str),
+    "span_text": _text,
+    "pos": lambda v: _num(v) and abs(v) <= MAX_POSITION_MM,
+    "size": lambda v: _num(v) and 0 < v <= MAX_SIZE_MM,
+    "pt": lambda v: _num(v) and 0 < v <= MAX_SIZE_PT,
+    "margin": lambda v: _num(v) and 0 <= v <= MAX_MARGIN_MM,
+    "dpi": lambda v: _num(v) and 0 < v <= 1_000_000,
+    "threshold": lambda v: _int(v) and 0 <= v <= 255,
+    "page": lambda v: _int(v) and v >= 1,
+    "align": lambda v: v in ALIGNMENTS, "orientation": lambda v: v in ORIENTATIONS,
+    "rotation": lambda v: _int(v) and v in ROTATIONS,
+    "mode": lambda v: v in MODES, "label": _label,
+    "crop": lambda v: v is None or (isinstance(v, list) and len(v) == 4 and all(map(_int, v))),
+}
+
+
+class StorageError(ValueError):
+    """Datei lässt sich nicht als Etikett lesen (Meldung auf Deutsch, mit Dateiname)."""
+
+
+def _reason(error: OSError) -> str:
+    """Grund eines Datei-Fehlers auf Deutsch (statt englischem Text des Betriebssystems)."""
+    if isinstance(error, FileNotFoundError):
+        return "Ordner fehlt"
+    if isinstance(error, IsADirectoryError):
+        return "ist ein Ordner"
+    if isinstance(error, PermissionError):
+        return "keine Berechtigung"
+    if getattr(error, "errno", None) == 36:     # ENAMETOOLONG
+        return "Name zu lang"
+    if getattr(error, "errno", None) == 28:     # ENOSPC
+        return "kein Platz auf dem Datenträger"
+    return "Fehler beim Zugriff"
+
+
+# --- Schreiben ---------------------------------------------------------------------------
+def _dump(obj, schema: dict) -> dict:
+    out = {}
+    for key, kind in schema.items():
+        value = getattr(obj, key)
+        if kind.startswith("bytes") and value is not None:
+            value = base64.b64encode(value).decode("ascii")
+        elif isinstance(value, tuple):
+            value = list(value)
+        out[key] = value
+    return out
+
+
+def to_dict(doc: Document) -> dict:
+    objects = []
+    for obj in doc.objects:
+        if isinstance(obj, TextObject):
+            objects.append({"type": "text", **_dump(obj, TEXT), "paragraphs": [
+                {**_dump(p, PARAGRAPH), "spans": [_dump(s, SPAN) for s in p.spans]}
+                for p in obj.paragraphs]})
+        else:
+            objects.append({"type": "image", **_dump(obj, IMAGE)})
+    return {"format": FORMAT, "version": VERSION,
+            "document": {**_dump(doc, DOCUMENT), "objects": objects}}
+
+
+def save(doc: Document, path: str | Path) -> Path:
+    """Atomar speichern (temporäre Datei im selben Ordner, dann ersetzen): ein Abbruch
+    hinterlässt die alte Datei. Ein Symlink wird verfolgt (das Ziel ändert sich), Rechte einer
+    vorhandenen Datei bleiben, neue Dateien bekommen die Rechte nach umask. Fehler:
+    ``OSError`` mit deutscher Meldung."""
+    path = Path(path)
+    target = Path(os.path.realpath(path))
+    try:
+        text = json.dumps(to_dict(doc), ensure_ascii=False, indent=1, allow_nan=False) + "\n"
+    except ValueError as e:
+        raise OSError(f"{path.name} wurde nicht gespeichert: ungültige Zahlen im Etikett") from e
+    tmp = None
+    try:
+        for attempt in range(100):          # freier Name für die temporäre Datei
+            tmp = target.with_name(f"{_TMP_PREFIX}{os.getpid()}-{attempt}.tmp")
+            try:
+                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)   # umask gilt
+                break
+            except FileExistsError:
+                continue
+        else:
+            raise FileExistsError(tmp)
+        with os.fdopen(fd, "w", encoding="utf-8") as f:
+            f.write(text)
+            f.flush()
+            os.fsync(f.fileno())
+        if target.exists():
+            os.chmod(tmp, stat.S_IMODE(target.stat().st_mode))
+        os.replace(tmp, target)
+        tmp = None
+    except OSError as e:
+        raise OSError(f"{path.name} wurde nicht gespeichert ({_reason(e)})") from e
+    finally:
+        if tmp is not None:
+            Path(tmp).unlink(missing_ok=True)
+    return path
+
+
+# --- Lesen -------------------------------------------------------------------------------
+def _check(value, kind: str, key: str, where: str):
+    """Wert prüfen und umwandeln (Base64 → bytes); ungültig → StorageError."""
+    optional = kind.endswith("?")
+    kind = kind.rstrip("?")
+    if value is None and optional:
+        return None
+    if not _KINDS[kind](value):
+        if kind == "label":
+            raise StorageError(f"Etikett{where} unbekannt: {reprlib.repr(value)}")
+        raise StorageError(f"Wert für „{key}“{where} ungültig: {reprlib.repr(value)}")
+    if kind == "span_text" and any(c in value for c in LINE_BREAKS):
+        raise StorageError(f"Zeilenumbruch in „{key}“{where} – Zeilen sind eigene Absätze")
+    if kind == "bytes":
+        try:
+            return base64.b64decode(value, validate=True)
+        except (binascii.Error, ValueError) as e:
+            raise StorageError(f"Bilddaten „{key}“{where} nicht lesbar") from e
+    return value
+
+
+def _load(data, schema: dict, where: str, required: tuple[str, ...] = ()) -> dict:
+    if not isinstance(data, dict):
+        raise StorageError(f"Eintrag{where} ist kein Objekt")
+    for key in required:
+        if key not in data:
+            raise StorageError(f"„{key}“{where} fehlt")
+    return {key: _check(data[key], kind, key, where) for key, kind in schema.items() if key in data}
+
+
+def _list(data: dict, key: str, where: str) -> list:
+    value = data.get(key, [])
+    if not isinstance(value, list):
+        raise StorageError(f"Wert für „{key}“{where} ungültig: {reprlib.repr(value)}")
+    return value
+
+
+def _image(data: dict, where: str) -> ImageObject:
+    values = _load(data, IMAGE, where, required=("png", "w_mm", "h_mm"))
+    try:
+        with Image.open(io.BytesIO(values["png"]), formats=["PNG"]) as img:
+            size = img.size
+            if max(size) > MAX_PIXELS:
+                raise StorageError(f"Bild{where} zu groß ({size[0]} × {size[1]} Pixel, "
+                                   f"höchstens {MAX_PIXELS})")
+            img.load()                      # ganz dekodieren: kaputte Daten fallen jetzt auf
+    except StorageError:
+        raise
+    except Exception as e:  # Pillow wirft je nach Schaden verschiedene Fehler
+        raise StorageError(f"Bilddaten{where} nicht lesbar (nur PNG)") from e
+    crop = values.get("crop")
+    if crop is not None and not (0 <= crop[0] < crop[2] <= size[0]
+                                 and 0 <= crop[1] < crop[3] <= size[1]):
+        raise StorageError(f"Wert für „crop“{where} liegt nicht im Bild: {crop}")
+    return ImageObject(**values)
+
+
+def _text_object(item: dict, where: str) -> TextObject:
+    values = _load(item, TEXT, where)
+    paragraphs = []
+    for p in _list(item, "paragraphs", where):
+        align = _load(p, PARAGRAPH, where)
+        spans = [Span(**_load(s, SPAN, where, required=("text",)))
+                 for s in _list(p, "spans", where)]
+        paragraphs.append(Paragraph(spans, **align))
+    return TextObject(paragraphs or [Paragraph([Span("")])], **values)   # leer = eine Zeile
+
+
+def from_dict(data) -> Document:
+    if not isinstance(data, dict) or data.get("format") != FORMAT:
+        raise StorageError("keine labelwerk-Datei")
+    version = data.get("version")
+    if not _int(version) or version < 1:
+        raise StorageError(f"keine labelwerk-Datei (Format-Version {reprlib.repr(version)})")
+    if version > VERSION:
+        raise StorageError(f"mit einem neueren labelwerk gespeichert (Format-Version {version}) "
+                           f"– bitte labelwerk aktualisieren")
+    document = data.get("document")
+    values = _load(document, DOCUMENT, "")
+    objects = []
+    for number, item in enumerate(_list(document, "objects", ""), start=1):
+        where = f" in Objekt {number}"
+        kind = item.get("type") if isinstance(item, dict) else None
+        if kind == "text":
+            objects.append(_text_object(item, where))
+        elif kind == "image":
+            objects.append(_image(item, where))
+        else:
+            raise StorageError(f"Objektart{where} unbekannt: {reprlib.repr(kind)}")
+    return Document(**values, objects=objects)
+
+
+def _reject_constant(name: str):
+    raise ValueError(f"{name} ist keine Zahl")
+
+
+def load(path: str | Path) -> Document:
+    """Etikett aus einer Datei; jeder Fehler als ``StorageError`` mit Dateiname."""
+    path = Path(path)
+    try:
+        if path.stat().st_size > MAX_FILE_BYTES:
+            raise StorageError(f"{path.name}: Datei zu groß")
+        text = path.read_text(encoding="utf-8-sig")       # auch mit BOM (Windows-Editoren)
+    except FileNotFoundError as e:
+        raise StorageError(f"Datei nicht gefunden: {path}") from e
+    except OSError as e:
+        raise StorageError(f"{path.name} kann nicht gelesen werden ({_reason(e)})") from e
+    except UnicodeDecodeError as e:
+        raise StorageError(f"{path.name}: keine labelwerk-Datei (kein UTF-8-Text)") from e
+    try:
+        data = json.loads(text, parse_constant=_reject_constant)   # NaN, Infinity
+    except RecursionError as e:
+        raise StorageError(f"{path.name}: Datei beschädigt (zu tief verschachtelt)") from e
+    except ValueError as e:
+        raise StorageError(f"{path.name}: keine labelwerk-Datei oder beschädigt") from e
+    try:
+        return from_dict(data)
+    except StorageError as e:
+        raise StorageError(f"{path.name}: {e}") from e
+    except (TypeError, AttributeError, KeyError, RecursionError, OverflowError) as e:
+        raise StorageError(f"{path.name}: Datei beschädigt") from e   # Sicherheitsnetz
+
+
+def add_recent_file(recent: list[str], path: str, limit: int = RECENT_FILES) -> list[str]:
+    """„Zuletzt geöffnet“: ``path`` nach vorn, ohne Doppelte, höchstens ``limit``."""
+    return [path, *(p for p in recent if p != path)][:limit]
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1622 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/document.py src/labelwerk/favorites.py src/labelwerk/files.py src/labelwerk/gui/image_import.py src/labelwerk/gui/settings_dialog.py src/labelwerk/render.py src/labelwerk/settings.py src/labelwerk/storage.py tests/gui/test_gui_settings.py tests/test_favorites.py tests/test_files.py tests/test_settings.py tests/test_storage.py
git commit -m "Kern: Etiketten als Datei (*.labelwerk), Favoriten-Ordner, Zuletzt geöffnet und Start-Favorit in den Einstellungen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: GUI – Reiter ★: Neu/Öffnen/Speichern, Rückfrage, Favoriten, Zuletzt geöffnet, Start

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/gui/app.py`
- Create: `src/labelwerk/gui/file_session.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Create: `src/labelwerk/gui/panels/file.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/gui/tools.py`
- Modify: `src/labelwerk/shortcuts.py`
- Modify: `tests/gui/conftest.py`
- Create: `tests/gui/test_gui_files.py`
- Modify: `tests/gui/test_gui_image.py`
- Modify: `tests/gui/test_gui_layout.py`
- Modify: `tests/gui/test_gui_window.py`

**Interfaces / Produces:** `gui/file_session.py` (`FileSession`, `answer_for`), `gui/panels/file.py` (`FilePanel`), Werkzeug `file` (★) zuerst, `START_TOOL`; Aktionen `file.new/open/save/save_as`; `MainWindow.files`, `start(path)`, `print_document(doc)`; Einstellungsdialog „Beim Start“; app.py Datei-Argument; tests/gui/conftest.py: Rückfrage sitzungsweit ersetzt, Dateimanager gesperrt.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/conftest.py b/tests/gui/conftest.py
index c10a5db..b6c8a02 100644
--- a/tests/gui/conftest.py
+++ b/tests/gui/conftest.py
@@ -33,6 +33,22 @@ else:
         monkeypatch.setattr("labelwerk.gui.screenshot.session_bus",
                             lambda: QDBusConnection("labelwerk-test-kein-bus"))
 
+    @pytest.fixture(autouse=True, scope="session")
+    def discard_changes_on_close():
+        """Schließen mit Änderungen fragt nach – in Tests ohne Dialog: verwerfen (einzelne Tests
+        ersetzen die Antwort selbst). Für die ganze Sitzung: auch Fenster, die erst am Ende
+        geschlossen werden, dürfen keinen echten Dialog öffnen (der hinge)."""
+        with pytest.MonkeyPatch.context() as patch:
+            patch.setattr("labelwerk.gui.file_session.FileSession.ask_save_changes",
+                          lambda self: "discard")
+            yield
+
+    @pytest.fixture(autouse=True)
+    def no_file_manager(monkeypatch):
+        """Kein Test öffnet den echten Dateimanager (Ordner öffnen ist sonst ersetzt)."""
+        monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl",
+                            lambda url: pytest.fail(f"Dateimanager geöffnet: {url}"))
+
     @pytest.fixture(autouse=True)
     def no_printer(monkeypatch):
         """Kein Test liest echte Druckerdaten aus /sys."""
diff --git a/tests/gui/test_gui_files.py b/tests/gui/test_gui_files.py
new file mode 100644
index 0000000..4fe452d
--- /dev/null
+++ b/tests/gui/test_gui_files.py
@@ -0,0 +1,593 @@
+"""Reiter ★ (Etappe 3c): Neu/Öffnen/Speichern, ungespeicherte Änderungen, Favoriten, Zuletzt
+geöffnet, Start mit Datei oder Favorit. Dialoge und Rückfragen sind ersetzt."""
+import pytest
+from PySide6.QtCore import Qt
+
+from labelwerk import favorites, shortcuts, storage
+from labelwerk.document import Document, TextObject
+from labelwerk.gui import main_window
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.gui.tools import TOOLS
+from labelwerk.render import render_document
+from labelwerk.settings import Settings, load_settings
+
+
+def _doc(text="Absender"):
+    return Document("62", length_mm=40, objects=[TextObject(text, size_pt=14, x_mm=4, y_mm=4)])
+
+
+def _window(qtbot, doc=None, **settings):
+    win = MainWindow(doc=doc or _doc(), settings=Settings(check_media_on_start=False, **settings))
+    qtbot.addWidget(win)
+    win.show()
+    return win
+
+
+class Answers:
+    """Ersatz für Dialoge: Antworten der Reihe nach, gestellte Fragen gemerkt."""
+
+    def __init__(self, win, **answers):
+        self.asked = []
+        for name, value in answers.items():
+            setattr(win.files, name, self._answer(name, value))
+
+    def _answer(self, name, value):
+        def ask(*args):
+            self.asked.append(name)
+            return value() if callable(value) else value
+        return ask
+
+
+def _type(win, text):
+    win.doc.objects[0] = TextObject(text, size_pt=14, x_mm=4, y_mm=4)
+    win.panel("text").refresh()
+    win.render_now()
+    win._commit()
+
+
+# --- Reiter, Aktionen ------------------------------------------------------------------
+def test_star_tab_comes_first_and_window_starts_on_paper(qtbot):
+    assert [tool.key for tool in TOOLS][:2] == ["file", "paper"]
+    win = _window(qtbot)
+    action = win.tool_actions["file"]
+    assert action.text() == "★" and action.toolTip() == "Datei und Favoriten"
+    assert win.panels.currentWidget() is win.panel("paper")
+
+
+@pytest.mark.parametrize("key, default", [("file.new", "Ctrl+N"), ("file.open", "Ctrl+O"),
+                                          ("file.save", "Ctrl+S"), ("file.save_as", "Ctrl+Shift+S")])
+def test_file_actions_have_global_shortcuts(qtbot, key, default):
+    entry = shortcuts.action(key)
+    assert (entry.default, entry.scope) == (default, "global")
+    win = _window(qtbot)
+    assert win.shortcut_actions[key] in win.actions()
+
+
+def test_panel_buttons_trigger_the_actions(qtbot):
+    win = _window(qtbot)
+    panel = win.panel("file")
+    assert [b.text() for b in (panel.new, panel.open, panel.save, panel.save_as)] == [
+        "NEU", "ÖFFNEN …", "SPEICHERN", "SPEICHERN UNTER …"]
+    assert "Ctrl+S" in panel.save.toolTip()
+
+
+# --- Speichern, Öffnen, Titel ----------------------------------------------------------
+def test_title_untitled_and_dot_when_changed(qtbot):
+    win = _window(qtbot)
+    assert win.windowTitle() == "Unbenannt – labelwerk"
+    _type(win, "Neu")
+    assert win.windowTitle() == "• Unbenannt – labelwerk"
+    win.undo()
+    assert win.windowTitle() == "Unbenannt – labelwerk"        # zurück zum Ausgangsstand
+
+
+def test_save_asks_for_a_file_the_first_time_and_adds_the_suffix(qtbot, tmp_path):
+    win = _window(qtbot)
+    answers = Answers(win, ask_save_file=str(tmp_path / "absender"))
+    win.shortcut_actions["file.save"].trigger()
+    path = tmp_path / "absender.labelwerk"
+    assert storage.load(path) == win.doc
+    assert answers.asked == ["ask_save_file"]
+    assert win.windowTitle() == "absender – labelwerk"
+    assert win.result.text() == "Gespeichert: absender.labelwerk"
+    _type(win, "geändert")
+    win.shortcut_actions["file.save"].trigger()                  # jetzt ohne Dialog
+    assert answers.asked == ["ask_save_file"] and storage.load(path).objects[0].text == "geändert"
+
+
+def test_save_as_always_asks(qtbot, tmp_path):
+    win = _window(qtbot)
+    Answers(win, ask_save_file=str(tmp_path / "a.labelwerk"))
+    win.shortcut_actions["file.save"].trigger()
+    answers = Answers(win, ask_save_file=str(tmp_path / "b.labelwerk"))
+    win.shortcut_actions["file.save_as"].trigger()
+    assert answers.asked == ["ask_save_file"] and (tmp_path / "b.labelwerk").exists()
+    assert win.windowTitle() == "b – labelwerk"
+
+
+def test_cancelled_save_dialog_changes_nothing(qtbot):
+    win = _window(qtbot)
+    _type(win, "x")
+    Answers(win, ask_save_file=None)
+    assert not win.files.save()
+    assert win.windowTitle().startswith("•")
+
+
+def test_save_error_is_shown(qtbot, tmp_path):
+    win = _window(qtbot)
+    Answers(win, ask_save_file=str(tmp_path / "fehlt" / "x.labelwerk"))
+    assert not win.files.save()
+    assert "nicht gespeichert" in win.result.text() and win.result.property("state") == "error"
+
+
+def test_open_replaces_the_document_and_resets_undo(qtbot, tmp_path):
+    path = tmp_path / "regal.labelwerk"
+    storage.save(_doc("Regal 3"), path)
+    win = _window(qtbot)
+    Answers(win, ask_open_file=str(path))
+    win.shortcut_actions["file.open"].trigger()
+    assert win.doc.objects[0].text == "Regal 3"
+    assert win.panel("text").doc is win.doc                      # Panels behalten das Objekt
+    assert not win.history.can_undo(win.doc)
+    assert win.windowTitle() == "regal – labelwerk"
+    assert load_settings().recent_files == [str(path)]
+
+
+def test_open_broken_file_keeps_the_document(qtbot, tmp_path):
+    path = tmp_path / "kaputt.labelwerk"
+    path.write_text("kein json")
+    win = _window(qtbot)
+    Answers(win, ask_open_file=str(path))
+    win.shortcut_actions["file.open"].trigger()
+    assert win.doc.objects[0].text == "Absender"
+    assert "kaputt.labelwerk" in win.result.text() and win.result.property("state") == "error"
+
+
+def test_new_gives_an_empty_label_from_the_settings(qtbot):
+    win = _window(qtbot, label_id="62x29")
+    win.shortcut_actions["file.new"].trigger()
+    assert win.doc.label_id == "62x29" and win.doc.is_empty()
+    assert win.windowTitle() == "Unbenannt – labelwerk"
+
+
+# --- Rückfrage bei ungespeicherten Änderungen ---------------------------------------------
+@pytest.mark.parametrize("trigger", ["new", "open", "close"])
+def test_unchanged_label_needs_no_question(qtbot, tmp_path, trigger):
+    path = tmp_path / "x.labelwerk"
+    storage.save(_doc(), path)
+    win = _window(qtbot)
+    answers = Answers(win, ask_save_changes="cancel", ask_open_file=str(path))
+    {"new": win.files.new, "open": win.files.open, "close": win.close}[trigger]()
+    assert answers.asked in ([], ["ask_open_file"])
+
+
+def test_changes_cancel_keeps_everything(qtbot):
+    win = _window(qtbot)
+    _type(win, "wichtig")
+    answers = Answers(win, ask_save_changes="cancel")
+    win.files.new()
+    assert answers.asked == ["ask_save_changes"] and win.doc.objects[0].text == "wichtig"
+
+
+def test_changes_discard_continues(qtbot):
+    win = _window(qtbot)
+    _type(win, "weg")
+    Answers(win, ask_save_changes="discard")
+    win.files.new()
+    assert win.doc.is_empty()
+
+
+def test_changes_save_saves_first(qtbot, tmp_path):
+    win = _window(qtbot)
+    _type(win, "behalten")
+    Answers(win, ask_save_changes="save", ask_save_file=str(tmp_path / "b.labelwerk"))
+    win.files.new()
+    assert storage.load(tmp_path / "b.labelwerk").objects[0].text == "behalten"
+    assert win.doc.is_empty()
+
+
+def test_close_with_changes_can_be_cancelled(qtbot):
+    win = _window(qtbot)
+    _type(win, "x")
+    Answers(win, ask_save_changes="cancel")
+    win.close()
+    assert win.isVisible()
+    Answers(win, ask_save_changes="discard")
+    win.close()
+    assert not win.isVisible()
+
+
+# --- Favoriten -------------------------------------------------------------------------
+def test_add_current_label_as_favorite(qtbot):
+    win = _window(qtbot)
+    answers = Answers(win, ask_favorite_name=lambda: "Absender")
+    win.panel("file").add_favorite.click()
+    assert [f.name for f in favorites.favorites()] == ["Absender"]
+    assert storage.load(favorites.find("Absender").path) == win.doc
+    assert answers.asked == ["ask_favorite_name"]
+    assert win.panel("file").favorite_names() == ["Absender"]
+
+
+def test_favorite_name_suggestion_is_the_first_text(qtbot):
+    win = _window(qtbot, Document("62", objects=[TextObject("Regal 3\nSchrauben")]))
+    assert win.files.suggested_name() == "Regal 3"
+
+
+def test_existing_favorite_name_asks_before_overwriting(qtbot):
+    favorites.add(_doc("alt"), "Absender")
+    win = _window(qtbot)
+    answers = Answers(win, ask_favorite_name="Absender", ask_overwrite=False)
+    win.files.add_favorite()
+    assert storage.load(favorites.find("Absender").path).objects[0].text == "alt"
+    Answers(win, ask_favorite_name="Absender", ask_overwrite=True)
+    win.files.add_favorite()
+    assert storage.load(favorites.find("Absender").path).objects[0].text == "Absender"
+    assert answers.asked == ["ask_favorite_name", "ask_overwrite"]
+
+
+def test_invalid_favorite_name_gives_message(qtbot):
+    win = _window(qtbot)
+    Answers(win, ask_favorite_name="a/b")
+    win.files.add_favorite()
+    assert favorites.favorites() == [] and "Name" in win.result.text()
+
+
+def test_clicking_a_favorite_opens_it_as_new_untitled_label(qtbot):
+    favorites.add(_doc("Vorlage"), "Absender")
+    win = _window(qtbot, _doc("anderes"))
+    win.panel("file").open_favorite_at(0)
+    assert win.doc.objects[0].text == "Vorlage"
+    assert win.windowTitle() == "Unbenannt – labelwerk"
+    assert win.files.path is None
+    _type(win, "geändert")
+    assert storage.load(favorites.find("Absender").path).objects[0].text == "Vorlage"
+
+
+def test_favorite_previews_are_rendered(qtbot):
+    favorites.add(_doc("A"), "A")
+    win = _window(qtbot)
+    preview = win.panel("file").favorite_preview(0)
+    assert preview is not None and preview.width() <= 110
+
+
+def test_printing_a_favorite_does_not_touch_the_open_label(qtbot, monkeypatch):
+    favorites.add(_doc("Fav"), "Fav")
+    started = []
+
+    class FakeWorker:
+        def __init__(self, image, label_id, model):
+            started.append((image.tobytes(), label_id))
+            from labelwerk.gui.print_worker import PrintSignals
+            self.signals = PrintSignals()
+    monkeypatch.setattr(main_window, "PrintWorker", FakeWorker)
+    monkeypatch.setattr(main_window.QThreadPool, "globalInstance",
+                        lambda: type("P", (), {"start": lambda self, w: None})())
+    win = _window(qtbot, _doc("offen"))
+    win.panel("file").print_favorite_at(0)
+    assert started == [(render_document(_doc("Fav")).tobytes(), "62")]
+    assert win.doc.objects[0].text == "offen"
+
+
+def test_rename_remove_and_start_favorite(qtbot):
+    favorites.add(_doc(), "alt")
+    win = _window(qtbot)
+    panel = win.panel("file")
+    Answers(win, ask_favorite_name="neu")
+    win.files.rename_favorite(favorites.find("alt"))
+    assert panel.favorite_names() == ["neu"]
+    win.files.toggle_start_favorite(favorites.find("neu"))
+    assert win.settings.start_favorite == "neu" and load_settings().start_favorite == "neu"
+    Answers(win, ask_remove=True)
+    win.files.remove_favorite(favorites.find("neu"))
+    assert panel.favorite_names() == [] and win.settings.start_favorite is None
+
+
+def test_favorite_context_menu_actions(qtbot):
+    favorites.add(_doc(), "Absender")
+    win = _window(qtbot)
+    menu = win.panel("file").favorite_menu(0)
+    assert [a.text() for a in menu.actions()] == [
+        "Öffnen als neues Etikett", "Drucken", "Umbenennen …", "Löschen …", "Beim Start öffnen",
+        "Ordner öffnen"]
+    assert menu.actions()[4].isCheckable()
+
+
+def test_empty_favorites_show_a_hint(qtbot):
+    win = _window(qtbot)
+    panel = win.panel("file")
+    assert panel.favorites_hint.isVisibleTo(panel) and "AKTUELL" in panel.favorites_hint.text()
+
+
+def test_opening_a_favorite_with_changes_asks_first(qtbot):
+    favorites.add(_doc("Fav"), "Fav")
+    win = _window(qtbot)
+    _type(win, "ungespeichert")
+    answers = Answers(win, ask_save_changes="cancel")
+    win.panel("file").open_favorite_at(0)
+    assert answers.asked == ["ask_save_changes"] and win.doc.objects[0].text == "ungespeichert"
+
+
+# --- Zuletzt geöffnet -----------------------------------------------------------------
+def test_recent_files_list_and_open(qtbot, tmp_path):
+    a, b = tmp_path / "a.labelwerk", tmp_path / "b.labelwerk"
+    storage.save(_doc("A"), a)
+    storage.save(_doc("B"), b)
+    win = _window(qtbot, recent_files=[str(b), str(a)])
+    panel = win.panel("file")
+    assert panel.recent_names() == ["b", "a"]
+    assert panel.recent.item(0).toolTip() == str(b)
+    panel.open_recent_at(1)
+    assert win.doc.objects[0].text == "A" and win.settings.recent_files[0] == str(a)
+    assert panel.recent_names() == ["a", "b"]
+
+
+def test_missing_recent_file_is_greyed_and_removed_on_click(qtbot, tmp_path):
+    win = _window(qtbot, recent_files=[str(tmp_path / "weg.labelwerk")])
+    panel = win.panel("file")
+    item = panel.recent.item(0)
+    assert item.foreground().color() == panel.palette().color(panel.palette().ColorRole.PlaceholderText)
+    panel.open_recent_at(0)
+    assert panel.recent_names() == [] and win.settings.recent_files == []
+    assert "nicht gefunden" in win.result.text()
+
+
+# --- Start --------------------------------------------------------------------------
+def test_start_with_a_file(qtbot, tmp_path):
+    path = tmp_path / "start.labelwerk"
+    storage.save(_doc("Start"), path)
+    win = _window(qtbot)
+    win.start(str(path))
+    assert win.doc.objects[0].text == "Start" and win.windowTitle() == "start – labelwerk"
+
+
+def test_start_with_the_start_favorite(qtbot):
+    favorites.add(_doc("Fav"), "Absender")
+    win = _window(qtbot, start_favorite="Absender")
+    win.start(None)
+    assert win.doc.objects[0].text == "Fav" and win.files.path is None
+
+
+def test_missing_start_favorite_starts_empty_with_hint(qtbot):
+    win = _window(qtbot, start_favorite="weg")
+    win.start(None)
+    assert "weg" in win.result.text()
+
+
+def test_settings_dialog_offers_start_favorite(qtbot):
+    from labelwerk.gui.settings_dialog import SettingsDialog
+    favorites.add(_doc(), "Absender")
+    favorites.add(_doc(), "Regal")
+    dialog = SettingsDialog(Settings(start_favorite="Regal"))
+    qtbot.addWidget(dialog)
+    combo = dialog.start_favorite
+    assert [combo.itemText(i) for i in range(combo.count())] == ["Leeres Etikett", "Absender", "Regal"]
+    assert combo.currentText() == "Regal"
+    combo.setCurrentIndex(0)
+    assert dialog.values().start_favorite is None
+    combo.setCurrentIndex(1)
+    assert dialog.values().start_favorite == "Absender"
+
+
+def test_settings_dialog_keeps_a_missing_start_favorite_visible(qtbot):
+    from labelwerk.gui.settings_dialog import SettingsDialog
+    dialog = SettingsDialog(Settings(start_favorite="weg"))
+    qtbot.addWidget(dialog)
+    assert dialog.start_favorite.currentText() == "weg (fehlt)"
+    assert dialog.values().start_favorite == "weg"
+
+
+def test_label_the_printer_cannot_print_is_refused(qtbot, tmp_path):
+    """102 mm gibt es bei brother_ql, der QL-600 druckt aber höchstens 62 mm."""
+    path = tmp_path / "breit.labelwerk"
+    storage.save(Document("102", objects=[TextObject("breit")]), path)
+    win = _window(qtbot)
+    Answers(win, ask_open_file=str(path))
+    win.files.open()
+    assert win.doc.objects[0].text == "Absender"
+    assert "102" in win.result.text() and "QL-600" in win.result.text()
+
+
+def test_recent_paths_are_normalized(qtbot, tmp_path):
+    path = tmp_path / "a.labelwerk"
+    storage.save(_doc(), path)
+    (tmp_path / "x").mkdir()
+    win = _window(qtbot)
+    assert win.files.open(str(tmp_path / "x" / ".." / "a.labelwerk"))
+    win.files.open(str(path))
+    assert win.settings.recent_files == [str(path.resolve())]
+
+
+# --- Nachbesserungen ---------------------------------------------------------------------
+from labelwerk.media import Media  # noqa: E402
+
+
+def test_roll_check_adjusts_a_fresh_label_without_marking_it_changed(qtbot):
+    win = _window(qtbot)
+    win._media_found(Media(62, 29, "die_cut"), "62x29")
+    assert win.doc.label_id == "62x29" and not win.files.modified()
+    assert win.windowTitle() == "Unbenannt – labelwerk"
+
+
+def test_roll_check_does_not_change_an_opened_file(qtbot, tmp_path):
+    path = tmp_path / "regal.labelwerk"
+    storage.save(_doc("Regal"), path)
+    win = _window(qtbot)
+    win.files.open(str(path))
+    win._media_found(Media(62, 29, "die_cut"), "62x29")
+    assert win.doc.label_id == "62" and not win.files.modified()
+
+
+def test_roll_check_does_not_change_an_opened_favorite(qtbot):
+    favorites.add(_doc("Fav"), "Fav")
+    win = _window(qtbot)
+    win.panel("file").open_favorite_at(0)
+    win._media_found(Media(62, 29, "die_cut"), "62x29")
+    assert win.doc.label_id == "62"
+
+
+def test_new_label_follows_the_known_roll(qtbot):
+    win = _window(qtbot)
+    win.panel("paper").show_media(Media(62, 29, "die_cut"), "62x29")
+    win.files.new()
+    assert win.doc.label_id == "62x29"
+
+
+def test_opening_a_label_that_does_not_render_replaces_the_view(qtbot, tmp_path):
+    """Renderfehler nach dem Öffnen: die Arbeitsfläche zeigt nicht mehr das alte Etikett."""
+    path = tmp_path / "gross.labelwerk"
+    storage.save(Document("62", length_mm=20, objects=[TextObject("X" * 40, size_pt=100)]), path)
+    win = _window(qtbot, Document("62", length_mm=40, objects=[
+        TextObject("a", x_mm=1, y_mm=1), TextObject("b", x_mm=20, y_mm=1)]))
+    win.files.open(str(path))
+    assert len(win.doc.objects) == 1 and win._render_error is not None
+    assert win.rendered == []                      # keine Bilder des alten Etiketts mehr
+
+
+def test_printing_a_favorite_checks_the_label(qtbot, monkeypatch):
+    path = favorites.favorites_dir()
+    path.mkdir(parents=True)
+    storage.save(Document("102", objects=[TextObject("breit")]), path / "breit.labelwerk")
+    monkeypatch.setattr(main_window, "PrintWorker", lambda *a: pytest.fail("gedruckt"))
+    win = _window(qtbot)
+    win.panel("file").print_favorite_at(0)
+    assert "passt nicht" in win.result.text()
+
+
+def test_printing_a_favorite_for_another_roll_asks_first(qtbot, monkeypatch):
+    favorites.add(Document("62x29", objects=[TextObject("klein")]), "klein")
+    monkeypatch.setattr(main_window, "PrintWorker", lambda *a: pytest.fail("gedruckt"))
+    win = _window(qtbot)
+    win.panel("paper").show_media(Media(62, 0, "endless"), "62")
+    answers = Answers(win, ask_print_other_roll=False)
+    win.panel("file").print_favorite_at(0)
+    assert answers.asked == ["ask_print_other_roll"]
+
+
+def test_favorite_print_buttons_are_locked_while_printing(qtbot):
+    favorites.add(_doc(), "A")
+    win = _window(qtbot)
+    win._set_printing(True)
+    row = win.panel("file").favorites.itemWidget(win.panel("file").favorites.item(0))
+    assert not row.print.isEnabled()
+    win.print_document(_doc())
+    assert "Druck läuft" in win.result.text()
+    win._set_printing(False)
+    assert row.print.isEnabled()
+
+
+def test_save_as_asks_before_replacing_when_the_suffix_was_added(qtbot, tmp_path):
+    storage.save(_doc("alt"), tmp_path / "absender.labelwerk")
+    win = _window(qtbot)
+    answers = Answers(win, ask_save_file=str(tmp_path / "absender"), ask_replace_file=False)
+    assert not win.files.save_as()
+    assert answers.asked == ["ask_save_file", "ask_replace_file"]
+    assert storage.load(tmp_path / "absender.labelwerk").objects[0].text == "alt"
+
+
+def test_upper_case_suffix_is_kept(qtbot, tmp_path):
+    win = _window(qtbot)
+    Answers(win, ask_save_file=str(tmp_path / "x.LABELWERK"))
+    assert win.files.save_as()
+    assert (tmp_path / "x.LABELWERK").exists()
+
+
+def test_settings_dialog_start_favorite_shows_in_the_star_tab(qtbot, monkeypatch):
+    favorites.add(_doc(), "A")
+    win = _window(qtbot)
+
+    class FakeDialog:
+        DialogCode = type("D", (), {"Accepted": 1})
+
+        def __init__(self, settings, **kw):
+            self.saved = Settings(**{**vars(settings), "start_favorite": "A", "warnings": []})
+
+        def exec(self):
+            return 1
+
+        def deleteLater(self):
+            pass
+    monkeypatch.setattr(main_window, "SettingsDialog", FakeDialog)
+    win.open_settings()
+    menu = win.panel("file").favorite_menu(0)
+    assert menu.actions()[4].isChecked()
+
+
+def test_broken_favorite_preview_does_not_stop_the_window(qtbot, monkeypatch):
+    favorites.add(_doc(), "A")
+    monkeypatch.setattr("labelwerk.gui.file_session.render_document",
+                        lambda *a, **k: (_ for _ in ()).throw(KeyError("kaputt")))
+    win = _window(qtbot)
+    assert win.panel("file").favorite_preview(0) is None
+
+
+def test_saving_keeps_the_writing_mode(qtbot, tmp_path):
+    win = _window(qtbot)
+    win.canvas.set_selection([0])
+    win.edit_selected()
+    Answers(win, ask_save_file=str(tmp_path / "a.labelwerk"))
+    win.files.save()
+    assert win.edit_session.active
+
+
+def test_cancelled_question_keeps_the_writing_mode(qtbot):
+    win = _window(qtbot)
+    _type(win, "geändert")
+    win.canvas.set_selection([0])
+    win.edit_selected()
+    Answers(win, ask_save_changes="cancel")
+    win.files.new()
+    assert win.edit_session.active
+
+
+def test_broken_favorite_does_not_ask_about_changes_first(qtbot):
+    path = favorites.favorites_dir()
+    path.mkdir(parents=True)
+    (path / "kaputt.labelwerk").write_text("kein json")
+    win = _window(qtbot)
+    _type(win, "x")
+    answers = Answers(win, ask_save_changes="cancel")
+    win.panel("file").open_favorite_at(0)
+    assert answers.asked == [] and "kaputt" in win.result.text()
+
+
+def test_successful_open_replaces_an_old_message(qtbot, tmp_path):
+    path = tmp_path / "a.labelwerk"
+    storage.save(_doc(), path)
+    win = _window(qtbot)
+    win._set_result("Datei nicht gefunden: …", "error")
+    win.files.open(str(path))
+    assert win.result.text() == "Geöffnet: a.labelwerk" and win.result.property("state") == "ok"
+
+
+def test_suggested_names_have_no_path_characters_and_keep_the_favorite_name(qtbot):
+    win = _window(qtbot, Document("62", objects=[TextObject("A/B 3")]))
+    assert win.files.suggested_name() == "A-B 3"
+    favorites.add(_doc("Text"), "Absender")
+    win.files.refresh_lists()
+    win.panel("file").open_favorite_at(0)
+    assert win.files.suggested_name() == "Absender"
+
+
+def test_keyboard_opens_favorites_and_recent_files(qtbot, tmp_path):
+    favorites.add(_doc("Fav"), "Fav")
+    win = _window(qtbot)
+    panel = win.panel("file")
+    panel.favorites.itemActivated.emit(panel.favorites.item(0))
+    assert win.doc.objects[0].text == "Fav"
+
+
+def test_question_buttons_map_to_answers():
+    from PySide6.QtWidgets import QMessageBox
+    from labelwerk.gui.file_session import answer_for
+    assert [answer_for(b.value) for b in (QMessageBox.StandardButton.Save,
+                                          QMessageBox.StandardButton.Discard,
+                                          QMessageBox.StandardButton.Cancel)] == [
+        "save", "discard", "cancel"]
+    assert answer_for(0) == "cancel"                 # Fenster-X / Esc
+
+
+def test_ctrl_s_saves(qtbot, tmp_path):
+    win = _window(qtbot)
+    answers = Answers(win, ask_save_file=str(tmp_path / "k.labelwerk"))
+    win.panel("file").save.click()
+    assert answers.asked == ["ask_save_file"] and (tmp_path / "k.labelwerk").exists()
diff --git a/tests/gui/test_gui_image.py b/tests/gui/test_gui_image.py
index 5a9c4f8..46ff576 100644
--- a/tests/gui/test_gui_image.py
+++ b/tests/gui/test_gui_image.py
@@ -132,7 +132,7 @@ def _status(win):
 
 # --- Werkzeug und Panel -------------------------------------------------------------
 def test_image_tool_comes_after_text(window):
-    assert [tool.key for tool in TOOLS] == ["paper", "text", "image", "layout"]
+    assert [tool.key for tool in TOOLS] == ["file", "paper", "text", "image", "layout"]
     window.tool_actions["image"].trigger()
     assert window.panels.currentWidget() is window.panel("image")
     assert window.canvas.tool() == "select"
diff --git a/tests/gui/test_gui_layout.py b/tests/gui/test_gui_layout.py
index 3b2b8ec..66c8133 100644
--- a/tests/gui/test_gui_layout.py
+++ b/tests/gui/test_gui_layout.py
@@ -64,7 +64,7 @@ def _frames(window):
 
 # --- Reiter -----------------------------------------------------------------------
 def test_layout_tool_follows_text_and_image(window):
-    assert [tool.key for tool in TOOLS][:4] == ["paper", "text", "image", "layout"]
+    assert [tool.key for tool in TOOLS][1:5] == ["paper", "text", "image", "layout"]
     window.tool_actions["layout"].trigger()
     assert window.panels.currentWidget() is _panel(window)
 
diff --git a/tests/gui/test_gui_window.py b/tests/gui/test_gui_window.py
index cf5cb65..6ee3f58 100644
--- a/tests/gui/test_gui_window.py
+++ b/tests/gui/test_gui_window.py
@@ -277,7 +277,7 @@ def test_window_title_and_app_name_use_app_name(window, qapp):
     from labelwerk.desktop import APP_NAME
     from labelwerk.gui.app import apply_identity
     apply_identity(qapp)
-    assert window.windowTitle() == APP_NAME
+    assert window.windowTitle() == f"Unbenannt – {APP_NAME}"       # Etappe 3c: Dateiname
     assert qapp.applicationName() == APP_NAME
 
 
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_files.py) schlagen fehl (ImportError/fehlende Attribute), außerdem die angepassten alten Tests zu Reiter-Reihenfolge und Fenstertitel; alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 3da4931..bd7c15b 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -19,8 +19,8 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Bildschirmfoto (Etappe 3d-2b): Knopf BILDSCHIRMFOTO im Reiter Bild – labelwerk blendet sich aus, der Desktop zeigt seine Auswahl (XDG-Portal), das Bild kommt mit 300 dpi aufs Etikett; ohne Portal Hinweis auf Zwischenablage + Strg+V.
 - SVG-Dateien sind Vektorbilder: in jeder Größe scharf gerastert (Etappe 3d-2c).
 - Symbole/ClipArt (Etappe 3d-2c): Knopf SYMBOL im Reiter Bild – Fenster „Symbol einfügen“ (bleibt offen; Suche über die ganze Bibliothek, Gruppen Zuletzt verwendet/Favoriten/Elektro/Versand/Sicherheit/Allgemein/Eigene, Doppelklick/Enter/Ziehen fügt ein); Symbole 15 mm, Vektor, zugeschnitten.
-- Etiketten als Datei (Etappe 3c, Kern): storage (*.labelwerk), Favoriten-Ordner, Einstellungen recent_files/start_favorite.
-- 1622 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Datei und Favoriten (Etappe 3c): Reiter ★ – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“).
+- 1683 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -95,8 +95,15 @@ src/labelwerk/
                     Bildschirmfoto (insert_screenshot: ausblenden, Portal, wieder zeigen; Haken screenshot_available/take_screenshot,
                     Antwort screenshot_finished; 5 min Sicherheitsnetz), Symbole (open_symbols, insert_symbol: SYMBOL_MM 15 mm,
                     höchstens quer zum Band; Zuletzt verwendet/Favoriten still gespeichert), Strg+V nach Zwischenablage des Systems (eigene Kopie › Dateien › Text › Bild; Stand beim Ändern gemerkt,
-                    Daten erst beim Einfügen gelesen); Auswahl zeigt Panel der Objektart
-    tools.py        Werkzeug-Registry (Papier, Text, Bild, Layout; neue Werkzeuge als Eintrag)
+                    Daten erst beim Einfügen gelesen); Auswahl zeigt Panel der Objektart; start(path) (Datei bzw. Start-Favorit),
+                    print_document(doc) (anderes Etikett drucken, gleiche Rückfragen); closeEvent fragt bei Änderungen
+    tools.py        Werkzeug-Registry (★ Datei, Papier, Text, Bild, Layout; neue Werkzeuge als Eintrag; START_TOOL = Papier)
+    file_session.py FileSession: Neu/Öffnen/Speichern, modified/update_title („•“), maybe_save (Rückfrage), Dokument an Ort und
+                    Stelle ersetzen (Verlauf neu), Etikett muss zum Drucker passen, origin new|file|favorite (nur „new“ folgt
+                    der geprüften Rolle, may_follow_roll; Neu nimmt die eingelegte Rolle), Favoriten (Vorlage öffnen, drucken über
+                    MainWindow.print_document, andere Rolle → Rückfrage, umbenennen/löschen/Start), Zuletzt geöffnet (Pfade
+                    aufgelöst); Dialoge ask_* ersetzbar (Speichern-Dialog ergänzt die Endung selbst)
+    panels/file.py  Reiter ★: Knöpfe (Aktionen file.*), Favoriten mit Vorschau und ⎙ je Zeile, Kontextmenü, Zuletzt geöffnet
     panels/         Eigenschaften-Panels je Werkzeug (paper, text und image mit Bereich Position)
     symbol_dialog.py Fenster „Symbol einfügen“ (SymbolDialog, Werkzeugfenster, nicht modal; Enter/Esc/Kontextmenü): Suche, Gruppen + Untergruppe, Raster über
                     SymbolModel (Vorschau erst bei Bedarf gerastert), Ziehen (MIME_SYMBOL = id), ★ Favorit, Ordner öffnen (open_url ersetzbar)
@@ -147,6 +154,7 @@ Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`),
 - `Replace media error` = angefordertes Etikett passt nicht zur eingelegten Rolle (Drucker erkennt die DK-Rolle per Sensor).
 - Pillow erkennt Formate am Inhalt: `Image.open` immer mit `formats=[…]` – EPS liefe sonst durch Ghostscript (auch bei „.png“).
 - D-Bus in Tests: nie `dbus-daemon --session`/`dbus-run-session` – deren Standard-Config startet echte Dienste (Portal öffnet Auswahl auf dem Bildschirm); eigene busconfig ohne servicedir.
+- GUI-Tests: Rückfrage „Änderungen speichern?“ ist sitzungsweit ersetzt (conftest, Antwort verwerfen) – sonst hinge ein echter Dialog beim Schließen.
 - GUI-Tests: jedes Widget bei `qtbot.addWidget` anmelden (sonst Absturz beim Beenden); immer Exit-Code von pytest prüfen, nicht nur „passed“.
 - Statusabfrage (Medium prüfen): Invalidate (200 × 0x00) + ESC @ + ESC i S, Antwort 32 Bytes sofort; brother_ql-Lesen nicht verwenden (kann ohne Zeitlimit blockieren).
 - Backends: `linux_kernel` (Standard, `/dev/usb/lpN`), `pyusb` (`usb://0x04f9:0x20c0`), `network`.
@@ -164,7 +172,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Etappe 3c Neu/Öffnen/Speichern + Favoriten (Roadmap 0).
+Nächste Schritte: Zierrahmen ums Etikett, danach 3e Serien aus CSV/Excel (Roadmap 0).
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -181,7 +189,7 @@ Umsetzung:
 - GUI bleibt dünn: Logik, die testbar ist, gehört in den Kern
 
 ## Roadmap danach
-0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto (erledigt, Spec 2026-10-18-bildschirmfoto) · 3d-2c Symbole/ClipArt (erledigt, Spec 2026-10-18-symbole) · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
+0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto (erledigt, Spec 2026-10-18-bildschirmfoto) · 3d-2c Symbole/ClipArt (erledigt, Spec 2026-10-18-symbole) · 3c Neu/Öffnen/Speichern + Favoriten (erledigt, Spec 2026-10-18-dateien-favoriten) · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
 1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
 2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
 3. Barcodes und QR-Codes
diff --git a/src/labelwerk/gui/app.py b/src/labelwerk/gui/app.py
index b7f84d4..cad3587 100644
--- a/src/labelwerk/gui/app.py
+++ b/src/labelwerk/gui/app.py
@@ -51,6 +51,9 @@ def main() -> int:
     window = MainWindow()
     apply_theme(app, window.settings.theme)
     window.show()
+    # labelwerk-gui [DATEI]: Datei öffnen (Doppelklick im Dateimanager), sonst Start-Favorit
+    paths = [a for a in app.arguments()[1:] if not a.startswith("-")]
+    window.start(paths[0] if paths else None)
     return app.exec()
 
 
diff --git a/src/labelwerk/gui/file_session.py b/src/labelwerk/gui/file_session.py
new file mode 100644
index 0000000..50fcdbd
--- /dev/null
+++ b/src/labelwerk/gui/file_session.py
@@ -0,0 +1,387 @@
+"""Datei-Sitzung des Hauptfensters: Neu/Öffnen/Speichern, ungespeicherte Änderungen,
+Favoriten und Zuletzt geöffnet (Reiter ★).
+
+Gerechnet wird im Kern (``storage``, ``favorites``); hier liegen Dialoge, Rückfragen und das
+Ersetzen des Dokuments. Das Dokument-Objekt bleibt dasselbe (Panels halten es fest) – es wird
+an Ort und Stelle auf den neuen Stand gesetzt, der Rückgängig-Verlauf beginnt neu. Alle
+Dialoge sind Methoden ``ask_*`` und in Tests ersetzbar.
+"""
+from __future__ import annotations
+
+import copy
+from pathlib import Path
+
+from PIL import Image
+from PySide6.QtCore import QObject, Qt, QUrl
+from PySide6.QtGui import QDesktopServices, QImage, QPixmap
+from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
+
+from .. import favorites, storage
+from ..desktop import APP_NAME
+from ..document import Document, TextObject
+from ..favorites import Favorite
+from ..labels import labels_for_model
+from ..render import render_document
+from ..settings import new_document
+from ..storage import SUFFIX, StorageError
+from .history import restore
+from .panels.file import PREVIEW
+
+FILE_FILTER = f"labelwerk-Etiketten (*{SUFFIX})"
+UNTITLED = "Unbenannt"
+MODIFIED = "• "
+NAME_LENGTH = 40               # vorgeschlagener Favoriten-Name: höchstens so lang
+PREVIEW_ERRORS = Exception     # Vorschau eines Favoriten: jeder Fehler → „nicht lesbar“
+
+
+def answer_for(button: int) -> str:
+    """Knopf der Rückfrage „Änderungen speichern?“ → „save“ | „discard“ | „cancel“."""
+    return {QMessageBox.StandardButton.Save.value: "save",
+            QMessageBox.StandardButton.Discard.value: "discard"}.get(button, "cancel")
+
+
+class FileSession(QObject):
+    def __init__(self, window):
+        super().__init__(window)
+        self.window = window
+        self.path: Path | None = None               # gespeicherte Datei; None = unbenannt
+        self.origin = "new"                         # „new“ | „file“ | „favorite“ (Herkunft)
+        self._template: str | None = None           # Name des Favoriten, solange unbenannt
+        self._saved = copy.deepcopy(window.doc)     # Stand beim Öffnen/Speichern
+        self._dir = ""                              # Ordner des letzten Öffnens/Speicherns
+        self._previews: dict[tuple[str, float], QPixmap | None] = {}
+        panel = window.panel("file")
+        panel.favorite_open.connect(self.open_favorite)
+        panel.favorite_print.connect(self.print_favorite)
+        panel.favorite_rename.connect(self.rename_favorite)
+        panel.favorite_remove.connect(self.remove_favorite)
+        panel.favorite_start.connect(self.toggle_start_favorite)
+        panel.favorites_folder.connect(self.open_favorites_folder)
+        panel.favorite_add.connect(self.add_favorite)
+        panel.recent_open.connect(self.open_recent)
+        self.refresh_lists()
+
+    # --- Dialoge (in Tests ersetzbar) -------------------------------------
+    def ask_save_file(self, suggested: str) -> str | None:
+        """Dialog ergänzt die Endung selbst – so fragt er vor dem Ersetzen nach dem vollen Namen."""
+        dialog = QFileDialog(self.window, "Etikett speichern", suggested, FILE_FILTER)
+        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
+        dialog.setDefaultSuffix(SUFFIX[1:])
+        return dialog.selectedFiles()[0] if dialog.exec() and dialog.selectedFiles() else None
+
+    def ask_replace_file(self, path: Path) -> bool:
+        return QMessageBox.question(
+            self.window, "Datei ersetzen", f"„{path.name}“ gibt es schon. Ersetzen?",
+            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
+            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
+
+    def ask_print_other_roll(self, label_id: str, loaded: str) -> bool:
+        return QMessageBox.question(
+            self.window, "Andere Rolle",
+            f"Eingelegt ist {loaded}, der Favorit ist für {label_id}. Trotzdem drucken?",
+            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
+            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
+
+    def ask_open_file(self) -> str | None:
+        path, _ = QFileDialog.getOpenFileName(self.window, "Etikett öffnen", self._dir,
+                                              FILE_FILTER)
+        return path or None
+
+    def ask_save_changes(self) -> str:
+        """„save“ | „discard“ | „cancel“."""
+        box = QMessageBox(QMessageBox.Icon.Question, "Ungespeicherte Änderungen",
+                          f"„{self.name()}“ wurde geändert. Änderungen speichern?",
+                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
+                          | QMessageBox.StandardButton.Cancel, self.window)
+        box.setDefaultButton(QMessageBox.StandardButton.Save)
+        return answer_for(box.exec())
+
+    def ask_favorite_name(self, suggested: str) -> str | None:
+        name, ok = QInputDialog.getText(self.window, "Favorit", "Name des Favoriten:",
+                                        text=suggested)
+        return name if ok else None
+
+    def ask_overwrite(self, name: str) -> bool:
+        return QMessageBox.question(
+            self.window, "Favorit ersetzen", f"Favorit „{name}“ gibt es schon. Ersetzen?",
+            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
+            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
+
+    def ask_remove(self, name: str) -> bool:
+        return QMessageBox.question(
+            self.window, "Favorit löschen", f"Favorit „{name}“ löschen?",
+            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
+            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
+
+    def open_url(self, url: QUrl) -> None:
+        QDesktopServices.openUrl(url)
+
+    # --- Zustand ----------------------------------------------------------
+    def name(self) -> str:
+        return self.path.stem if self.path is not None else UNTITLED
+
+    def modified(self) -> bool:
+        return self.window.doc != self._saved
+
+    def may_follow_roll(self) -> bool:
+        """Darf „Medium prüfen“ das Etikett umstellen? Nur bei einem neuen Etikett – eine
+        geöffnete Datei oder ein Favorit gehört zu ihrer Rolle (Panel zeigt „passt nicht“)."""
+        return self.origin == "new"
+
+    def mark_unchanged(self) -> None:
+        """Aktueller Stand gilt als Ausgangsstand (z. B. Rolle bei einem unberührten Etikett)."""
+        self._saved = copy.deepcopy(self.window.doc)
+        self.update_title()
+
+    def update_title(self) -> None:
+        mark = MODIFIED if self.modified() else ""
+        self.window.setWindowTitle(f"{mark}{self.name()} – {APP_NAME}")
+
+    def maybe_save(self) -> bool:
+        """Vor Neu/Öffnen/Schließen: bei Änderungen fragen; False = abbrechen (der Schreibmodus
+        läuft dann weiter). Das Dokument ist auch beim Tippen aktuell."""
+        if not self.modified():
+            return True
+        answer = self.ask_save_changes()
+        if answer == "save":
+            return self.save()
+        return answer == "discard"
+
+    def _fits_printer(self, doc: Document, name: str) -> bool:
+        """Etikett muss zum Drucker passen (sonst gäbe es dafür keine Auswahl im Reiter Papier)."""
+        if doc.label_id in {label.id for label in labels_for_model(self.window.model)}:
+            return True
+        self.window._set_result(f"{name}: Etikett „{doc.label_id}“ passt nicht zum "
+                                f"{self.window.model}", "error")
+        return False
+
+    def _replace(self, doc: Document, path: Path | None, origin: str = "new",
+                 template: str | None = None) -> None:
+        """Dokument an Ort und Stelle ersetzen, Verlauf neu, nichts ausgewählt."""
+        window = self.window
+        window.finish_editing()
+        window.canvas.set_selection([])
+        window._structure_changing()    # Renderfehler: keine Bilder des alten Etiketts stehen lassen
+        restore(window.doc, doc)
+        window.history.reset(window.doc)
+        for panel in window._panel_by_key.values():
+            panel.refresh()
+        window.render_now()
+        self.path = path
+        self.origin = "file" if path is not None else origin
+        self._template = template
+        self._saved = copy.deepcopy(window.doc)
+        self.update_title()
+        window._update_edit_actions()
+
+    # --- Neu, Öffnen, Speichern -------------------------------------------
+    def new(self) -> None:
+        """Leeres Etikett nach den Einstellungen – auf der eingelegten Rolle, wenn bekannt."""
+        if self.maybe_save():
+            doc = new_document(self.window.settings)
+            loaded = self.window.panel("paper").media_label
+            if loaded is not None:
+                doc.label_id = loaded
+            self._replace(doc, None)
+
+    def open(self, path: str | None = None, ask: bool = True) -> bool:
+        """Datei öffnen (ohne ``path``: Dialog); Fehler → Statusleiste, Etikett bleibt."""
+        if ask and not self.maybe_save():
+            return False
+        path = path or self.ask_open_file()
+        if not path:
+            return False
+        path = Path(path).resolve()          # gleiche Datei = gleicher Eintrag in „Zuletzt“
+        try:
+            doc = storage.load(path)
+        except StorageError as e:
+            self.window._set_result(str(e), "error")
+            return False
+        if not self._fits_printer(doc, path.name):
+            return False
+        self._replace(doc, path)
+        self._dir = str(path.parent)
+        self._remember(path)
+        self.window._set_result(f"Geöffnet: {path.name}", "ok")
+        return True
+
+    def save(self) -> bool:
+        if self.path is None:
+            return self.save_as()
+        return self._write(self.path)
+
+    def save_as(self) -> bool:
+        suggested = str(self.path) if self.path is not None else str(
+            Path(self._dir or Path.home()) / f"{self.suggested_name() or UNTITLED}{SUFFIX}")
+        path = self.ask_save_file(suggested)
+        if not path:
+            return False
+        path = Path(path)
+        if path.suffix.lower() != SUFFIX:
+            path = path.with_name(path.name + SUFFIX)
+            if path.exists() and not self.ask_replace_file(path):   # Dialog sah den Namen ohne
+                return False
+        return self._write(path)
+
+    def _write(self, path: Path) -> bool:
+        try:
+            storage.save(self.window.doc, path)
+        except OSError as e:
+            self.window._set_result(str(e), "error")
+            return False
+        self.path = path.resolve()
+        self._dir = str(path.parent)
+        self._saved = copy.deepcopy(self.window.doc)
+        self.update_title()
+        self._remember(self.path)
+        self.window._set_result(f"Gespeichert: {path.name}", "ok")
+        return True
+
+    def _remember(self, path: Path) -> None:
+        settings = self.window.settings
+        settings.recent_files = storage.add_recent_file(settings.recent_files, str(path))
+        self.window._save_settings()
+        self.refresh_lists()
+
+    def open_recent(self, path: str) -> None:
+        if not Path(path).exists():
+            settings = self.window.settings
+            settings.recent_files = [p for p in settings.recent_files if p != path]
+            self.window._save_settings()
+            self.refresh_lists()
+            self.window._set_result(f"Datei nicht gefunden: {path} – aus der Liste entfernt",
+                                    "error")
+            return
+        self.open(path)
+
+    # --- Favoriten --------------------------------------------------------
+    def suggested_name(self) -> str:
+        """Vorschlag für einen Namen: Dateiname bzw. Favorit, sonst die erste Textzeile (ohne
+        Pfadzeichen)."""
+        if self.path is not None:
+            return self.path.stem
+        if self._template is not None:
+            return self._template
+        for obj in self.window.doc.objects:
+            if isinstance(obj, TextObject) and obj.text.strip():
+                line = obj.text.strip().split("\n")[0][:NAME_LENGTH].strip()
+                return line.replace("/", "-").replace("\\", "-")
+        return ""
+
+    def add_favorite(self) -> None:
+        self.window.finish_editing()
+        name = self.ask_favorite_name(self.suggested_name())
+        if name is None:
+            return
+        try:
+            try:
+                favorite = favorites.add(self.window.doc, name)
+            except FileExistsError:
+                if not self.ask_overwrite(name.strip()):
+                    return
+                favorite = favorites.add(self.window.doc, name, overwrite=True)
+        except (ValueError, OSError) as e:
+            self.window._set_result(str(e), "error")
+            return
+        self.refresh_lists()
+        self.window._set_result(f"Favorit „{favorite.name}“ gespeichert", "ok")
+
+    def _load_favorite(self, favorite: Favorite) -> Document | None:
+        try:
+            return storage.load(favorite.path)
+        except StorageError as e:
+            self.window._set_result(str(e), "error")
+            return None
+
+    def open_favorite(self, favorite: Favorite) -> bool:
+        """Als neues, unbenanntes Etikett öffnen (Vorlage) – das Original bleibt unverändert.
+        Erst laden und prüfen, dann nach Änderungen fragen."""
+        doc = self._load_favorite(favorite)
+        if doc is None or not self._fits_printer(doc, favorite.name) or not self.maybe_save():
+            return False
+        self._replace(doc, None, origin="favorite", template=favorite.name)
+        return True
+
+    def print_favorite(self, favorite: Favorite) -> None:
+        """Direkt drucken: Etikett muss zum Drucker passen; liegt bekannt eine andere Rolle ein,
+        erst fragen (sonst meldete der Drucker nur „Replace media“)."""
+        doc = self._load_favorite(favorite)
+        if doc is None or not self._fits_printer(doc, favorite.name):
+            return
+        loaded = self.window.panel("paper").media_label
+        if loaded is not None and loaded != doc.label_id and not self.ask_print_other_roll(
+                doc.label_id, loaded):
+            return
+        self.window.print_document(doc)
+
+    def rename_favorite(self, favorite: Favorite) -> None:
+        name = self.ask_favorite_name(favorite.name)
+        if name is None or name.strip() == favorite.name:
+            return
+        try:
+            renamed = favorites.rename(favorite, name)
+        except (ValueError, OSError) as e:
+            self.window._set_result(str(e), "error")
+            return
+        if self.window.settings.start_favorite == favorite.name:
+            self.window.settings.start_favorite = renamed.name
+            self.window._save_settings()
+        self.refresh_lists()
+
+    def remove_favorite(self, favorite: Favorite) -> None:
+        if not self.ask_remove(favorite.name):
+            return
+        try:
+            favorites.remove(favorite)
+        except OSError as e:
+            self.window._set_result(str(e), "error")
+            return
+        if self.window.settings.start_favorite == favorite.name:
+            self.window.settings.start_favorite = None
+            self.window._save_settings()
+        self.refresh_lists()
+
+    def toggle_start_favorite(self, favorite: Favorite) -> None:
+        settings = self.window.settings
+        settings.start_favorite = None if settings.start_favorite == favorite.name else favorite.name
+        self.window._save_settings()
+        self.refresh_lists()
+
+    def open_favorites_folder(self) -> None:
+        folder = favorites.favorites_dir()
+        folder.mkdir(parents=True, exist_ok=True)
+        self.open_url(QUrl.fromLocalFile(str(folder)))
+
+    # --- Listen im Panel --------------------------------------------------
+    def refresh_lists(self) -> None:
+        panel = self.window.panel("file")
+        current = favorites.favorites()
+        panel.set_favorites([(f, self._preview(f)) for f in current],
+                            self.window.settings.start_favorite)
+        panel.set_recent(self.window.settings.recent_files)
+        paths = {str(f.path) for f in current}       # Vorschauen alter Stände vergessen
+        self._previews = {k: v for k, v in self._previews.items() if k[0] in paths}
+
+    def _preview(self, favorite: Favorite) -> QPixmap | None:
+        """Druckbild des Favoriten, eingepasst (gemerkt je Datei und Änderungszeit)."""
+        try:
+            key = (str(favorite.path), favorite.path.stat().st_mtime)
+        except OSError:
+            return None
+        if key not in self._previews:
+            try:
+                image = render_document(storage.load(favorite.path), self.window.model)
+            except PREVIEW_ERRORS:  # eine kaputte Vorschau darf das Fenster nicht aufhalten
+                self._previews[key] = None
+            else:
+                self._previews[key] = _pixmap(image).scaled(
+                    PREVIEW, Qt.AspectRatioMode.KeepAspectRatio,
+                    Qt.TransformationMode.SmoothTransformation)
+        return self._previews[key]
+
+
+def _pixmap(image: Image.Image) -> QPixmap:
+    gray = image.convert("L")
+    qimage = QImage(gray.tobytes(), gray.width, gray.height, gray.width,
+                    QImage.Format.Format_Grayscale8)
+    return QPixmap.fromImage(qimage.copy())
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 8e32dfa..959bfc6 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -16,7 +16,7 @@ from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, Q
                                QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                                QWidget)
 
-from .. import clipart
+from .. import clipart, favorites
 from ..desktop import APP_NAME
 from ..detect import brother_busy, find_brother_lp
 from ..document import Document, ImageObject, TextObject
@@ -25,10 +25,11 @@ from ..fonts import DEFAULT_FAMILY
 from ..labels import DPI, get_label
 from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, growing_axis,
                       insert_placement, match_objects, maximize_object, move, object_rect,
-                      outside_indices, printable_area, proportional, reorder, resize, rotate,
+                      objects_outside, outside_indices, printable_area, proportional, reorder, resize, rotate,
                       set_frame, to_grid)
 from ..printer import DEFAULT_MODEL
-from ..render import Renderer, RenderedObject, font_warnings, set_svg_rasterizer
+from ..render import (Renderer, RenderedObject, font_warnings, render_document,
+                      set_svg_rasterizer)
 from ..settings import Settings, load_settings, new_document, save_settings
 from ..shortcuts import effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
@@ -39,13 +40,14 @@ from .image_import import CLIPBOARD, DROPPED, MIME_OBJECTS, SCREENSHOT, SYMBOL_S
 from .media_worker import MediaWorker
 from .panels.image import CROP_FAILED
 from .panels.text import DEFAULT_PT
+from .file_session import FileSession
 from .print_worker import PrintWorker
 from .screenshot import FAILED as SCREENSHOT_FAILED, ScreenshotPortal
 from .symbol_dialog import SymbolDialog
 from .settings_dialog import SettingsDialog
 from .symbols import SIZE, line_icon
 from .text_edit_mode import TextEditSession
-from .tools import TOOLS, Tool
+from .tools import START_TOOL, TOOLS, Tool
 
 RENDER_DELAY_MS = 150
 PANEL_WIDTH = 280          # Eigenschaften-Panels; bei wenig Höhe rollbar
@@ -146,12 +148,15 @@ class MainWindow(QMainWindow):
             self.panels.addWidget(panel)
             self._panel_by_key[tool.key] = panel
             action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
+            action.setToolTip(tool.tip or tool.title)
             action.setCheckable(True)
             action.triggered.connect(lambda _=False, key=tool.key: self._tool_triggered(key))
             group.addAction(action)
             toolbar.addAction(action)
             self.tool_actions[tool.key] = action
-        next(iter(self.tool_actions.values())).setChecked(True)
+        start = START_TOOL if START_TOOL in self.tool_actions else next(iter(self.tool_actions))
+        self.tool_actions[start].setChecked(True)
+        self.panels.setCurrentWidget(self._panel_by_key[start])
         spacer = QWidget()
         spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
         toolbar.addWidget(spacer)
@@ -178,6 +183,12 @@ class MainWindow(QMainWindow):
         self.canvas.symbol_dropped.connect(self._symbol_dropped)
         self.history = History(self.doc)
         self.history.changed.connect(self._update_edit_actions)
+        # Datei und Favoriten (Reiter ★): Neu/Öffnen/Speichern, Rückfrage bei Änderungen
+        self.files = FileSession(self)
+        for key, handler in (("file.new", self.files.new), ("file.open", self.files.open),
+                             ("file.save", self.files.save), ("file.save_as", self.files.save_as)):
+            self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
+            self.addAction(self.shortcut_actions[key])
         self._connect_view_actions()
         self._connect_canvas_actions()
         self._connect_layout_actions()
@@ -483,6 +494,7 @@ class MainWindow(QMainWindow):
 
     def render_now(self) -> None:
         self._timer.stop()
+        self.files.update_title()                   # „•“ bei ungespeicherten Änderungen
         if self.canvas.is_dragging():   # Ziehen nicht unterbrechen – nach dem Loslassen rendern
             self._timer.start()
             return
@@ -1248,7 +1260,24 @@ class MainWindow(QMainWindow):
             self._media_check_pending = False
             self.check_media()
 
+    def start(self, path: str | None = None) -> None:
+        """Nach dem Öffnen des Fensters: Datei aus der Befehlszeile, sonst der Start-Favorit
+        (als neues Etikett), sonst bleibt das leere Etikett."""
+        if path:
+            self.files.open(path, ask=False)
+            return
+        name = self.settings.start_favorite
+        if name:
+            favorite = favorites.find(name)
+            if favorite is None:
+                self._set_result(f"Start-Favorit „{name}“ nicht gefunden – leeres Etikett", "error")
+            else:
+                self.files.open_favorite(favorite)
+
     def closeEvent(self, event) -> None:
+        if not self.files.maybe_save():
+            event.ignore()                          # Abbrechen: Fenster bleibt offen
+            return
         self._printer_timer.stop()
         if self.symbol_window is not None:
             self.symbol_window.close()              # sonst hielte es die App offen
@@ -1281,6 +1310,7 @@ class MainWindow(QMainWindow):
             self.apply_theme_icons()
             apply_shortcuts(self.shortcut_actions,
                             without_conflicts(effective(self.settings.shortcuts))[0])
+            self.files.refresh_lists()                  # „Beim Start“ im Reiter ★
             self._set_result("Einstellungen gespeichert – gelten für neue Etiketten.", "ok")
 
     # --- Medium prüfen ----------------------------------------------------
@@ -1301,9 +1331,13 @@ class MainWindow(QMainWindow):
         QThreadPool.globalInstance().start(worker)
 
     def _media_found(self, media, label_id) -> None:
+        """Rolle erkannt: ein neues Etikett folgt ihr (war es unberührt, bleibt es das); eine
+        geöffnete Datei oder ein Favorit bleibt bei ihrem Etikett – das Panel zeigt „passt nicht“."""
         self._media_finished()
-        adjusted = label_id is not None and label_id != self.doc.label_id
+        adjusted = (label_id is not None and label_id != self.doc.label_id
+                    and self.files.may_follow_roll())
         if adjusted:
+            unchanged = not self.files.modified()
             editing = self.edit_session.active
             if editing:     # Stand vor der Bearbeitung mit neuer Rolle: eigener Schritt davor
                 before = self.history.current()
@@ -1316,6 +1350,8 @@ class MainWindow(QMainWindow):
                 self._update_edit_actions()
             else:
                 self._commit()
+            if unchanged:
+                self.files.mark_unchanged()
         self.panel("paper").show_media(media, label_id, adjusted)
 
     def _media_failed(self, message: str) -> None:
@@ -1347,21 +1383,40 @@ class MainWindow(QMainWindow):
             self.render_now()
         if self.image is None or self._render_error is not None:
             return   # Fehler steht bereits in der Statusleiste
+        self._print(self.image, self.doc, self._outside)
+
+    def print_document(self, doc: Document) -> None:
+        """Anderes Etikett drucken (Favorit), ohne das offene anzutasten – gleiche Rückfragen."""
+        if self.is_printing():
+            self._set_result("Druck läuft – bitte warten.", "error")
+            return
+        try:
+            image = render_document(doc, self.model)
+            outside = objects_outside(doc, self.model)
+        except ValueError as e:
+            self._set_result(str(e), "error")
+            return
+        except Exception as e:  # fremde Datei: Meldung statt Traceback
+            self._set_result(f"Etikett kann nicht gedruckt werden ({type(e).__name__})", "error")
+            return
+        self._print(image, doc, outside)
+
+    def _print(self, image, doc: Document, outside: list[int]) -> None:
         if self.is_checking_media():
             self._set_result("Rolle wird gerade geprüft – bitte gleich noch einmal drucken.", "error")
             return
         # Druck sperrt die Medium-Prüfung schon vor dem Dialog (Timer läuft währenddessen weiter)
         self._set_printing(True)
-        if self.doc.is_empty() and not self.confirm_empty():
+        if doc.is_empty() and not self.confirm_empty():
             self._set_printing(False)
             return
-        if self._outside and not self.confirm_outside():
+        if outside and not self.confirm_outside():
             self._set_printing(False)
             return
         self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
         self.result.style().polish(self.result)
         self.result.setText("Drucke …")
-        worker = PrintWorker(self.image, self.doc.label_id, self.model)
+        worker = PrintWorker(image, doc.label_id, self.model)
         self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
         worker.signals.done.connect(self._print_done)
         worker.signals.failed.connect(self._print_failed)
@@ -1370,6 +1425,7 @@ class MainWindow(QMainWindow):
     def _set_printing(self, printing: bool) -> None:
         self._printing = printing
         self.print_action.setEnabled(not printing)
+        self.panel("file").set_printing(printing)
         self.panel("paper").check.setEnabled(not printing)
 
     def _print_done(self, status: dict) -> None:
diff --git a/src/labelwerk/gui/panels/file.py b/src/labelwerk/gui/panels/file.py
new file mode 100644
index 0000000..8fd271d
--- /dev/null
+++ b/src/labelwerk/gui/panels/file.py
@@ -0,0 +1,199 @@
+"""Panel „★“: Neu/Öffnen/Speichern, Favoriten (mit Vorschau, ⎙ je Favorit) und Zuletzt geöffnet.
+
+Nur Anzeige: Knöpfe lösen die Aktionen des Hauptfensters aus, Listen melden per Signal, was
+gewählt wurde – ausgeführt wird in ``gui.file_session.FileSession``.
+"""
+from __future__ import annotations
+
+from pathlib import Path
+
+from PySide6.QtCore import QSize, Qt, Signal
+from PySide6.QtGui import QAction, QPixmap
+from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
+                               QPushButton, QToolButton, QWidget)
+
+from ...document import Document
+from ...favorites import Favorite
+from . import Panel
+
+PREVIEW = QSize(110, 46)            # Vorschau eines Favoriten (eingepasst)
+FAVORITE_ROWS = 5                   # so viele Favoriten sichtbar, mehr per Bildlauf
+RECENT_ROWS = 6
+FAVORITES_HINT = "Noch keine Favoriten – ein Etikett gestalten und „+ AKTUELL“ drücken."
+BROKEN = "nicht lesbar"
+
+
+class _FavoriteRow(QWidget):
+    """Zeile: Vorschau, Name, ⎙ (druckt diesen Favoriten)."""
+
+    def __init__(self, favorite: Favorite, preview: QPixmap | None, start: bool, on_print):
+        super().__init__()
+        row = QHBoxLayout(self)
+        row.setContentsMargins(2, 2, 2, 2)
+        self.preview = QLabel()
+        self.preview.setFixedSize(PREVIEW)
+        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
+        if preview is not None:
+            self.preview.setPixmap(preview)
+        else:
+            self.preview.setText(BROKEN)
+        self.name = QLabel(f"{favorite.name}{'  ▸ Start' if start else ''}")
+        self.name.setWordWrap(True)
+        self.print = QToolButton()
+        self.print.setText("⎙")
+        self.print.setToolTip(f"„{favorite.name}“ drucken")
+        self.print.clicked.connect(on_print)
+        row.addWidget(self.preview)
+        row.addWidget(self.name, 1)
+        row.addWidget(self.print)
+
+
+class FilePanel(Panel):
+    favorite_open = Signal(object)        # Favorite → als neues Etikett öffnen
+    favorite_print = Signal(object)       # Favorite → drucken
+    favorite_rename = Signal(object)
+    favorite_remove = Signal(object)
+    favorite_start = Signal(object)       # Favorite → „Beim Start öffnen“ an/aus
+    favorites_folder = Signal()           # Ordner öffnen
+    favorite_add = Signal()               # „+ AKTUELL“
+    recent_open = Signal(str)             # Pfad
+
+    def __init__(self, doc: Document):
+        super().__init__(doc, "Datei")
+        self._favorites: list[Favorite] = []
+        self._start: str | None = None
+        self._printing = False
+        self._recent: list[str] = []
+        row = QHBoxLayout()
+        self.new = QPushButton("NEU")
+        self.open = QPushButton("ÖFFNEN …")
+        row.addWidget(self.new)
+        row.addWidget(self.open)
+        self.layout_.addLayout(row)
+        self.save = QPushButton("SPEICHERN")
+        self.save_as = QPushButton("SPEICHERN UNTER …")
+        for button in (self.save, self.save_as):          # volle Breite: lange Beschriftung
+            self.layout_.addWidget(button)
+
+        self.section("Favoriten")
+        self.add_favorite = QPushButton("+ AKTUELL")
+        self.add_favorite.setToolTip("Aktuelles Etikett als Favorit speichern")
+        self.add_favorite.clicked.connect(self.favorite_add)
+        self.layout_.addWidget(self.add_favorite)
+        self.favorites_hint = QLabel(FAVORITES_HINT)
+        self.favorites_hint.setObjectName("hint")
+        self.favorites_hint.setWordWrap(True)
+        self.layout_.addWidget(self.favorites_hint)
+        self.favorites = QListWidget()
+        self.favorites.setObjectName("favorites")
+        self.favorites.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
+        self.favorites.itemClicked.connect(lambda item: self.open_favorite_at(self.favorites.row(item)))
+        self.favorites.itemActivated.connect(lambda item: self.open_favorite_at(self.favorites.row(item)))
+        self.favorites.customContextMenuRequested.connect(self._favorite_context)
+        self.layout_.addWidget(self.favorites)
+
+        self.section("Zuletzt geöffnet")
+        self.recent = QListWidget()
+        self.recent.setObjectName("recent")
+        self.recent.itemClicked.connect(lambda item: self.open_recent_at(self.recent.row(item)))
+        self.recent.itemActivated.connect(lambda item: self.open_recent_at(self.recent.row(item)))
+        self.layout_.addWidget(self.recent)
+        self.layout_.addStretch()
+
+    def use_actions(self, actions: dict[str, QAction]) -> None:
+        """Knöpfe lösen die Datei-Aktionen aus (Kürzel im Tooltip, auch nach dem Umbelegen)."""
+        for button, key in ((self.new, "file.new"), (self.open, "file.open"),
+                            (self.save, "file.save"), (self.save_as, "file.save_as")):
+            action = actions[key]
+            button.clicked.connect(lambda _=False, a=action: a.trigger())
+            button.setToolTip(action.toolTip())
+            action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))
+
+    # --- Favoriten --------------------------------------------------------
+    def set_favorites(self, favorites: list[tuple[Favorite, QPixmap | None]],
+                      start: str | None) -> None:
+        """Liste neu füllen: (Favorit, Vorschau oder None = nicht lesbar); ``start`` = Name
+        des Start-Favoriten."""
+        self._favorites = [f for f, _ in favorites]
+        self._start = start
+        self.favorites.clear()
+        for favorite, preview in favorites:
+            item = QListWidgetItem()
+            item.setToolTip(str(favorite.path))
+            item.setSizeHint(QSize(PREVIEW.width() + 120, PREVIEW.height() + 8))
+            self.favorites.addItem(item)
+            row = _FavoriteRow(favorite, preview, favorite.name == start,
+                               lambda _=False, f=favorite: self.favorite_print.emit(f))
+            row.print.setEnabled(not self._printing)
+            self.favorites.setItemWidget(item, row)
+        self.favorites_hint.setVisible(not favorites)
+        self.favorites.setVisible(bool(favorites))
+        _fit_height(self.favorites, min(len(favorites), FAVORITE_ROWS), PREVIEW.height() + 8)
+
+    def set_printing(self, printing: bool) -> None:
+        """Während eines Drucks sind die ⎙-Knöpfe gesperrt (wie DRUCKEN)."""
+        self._printing = printing
+        for row in range(self.favorites.count()):
+            self.favorites.itemWidget(self.favorites.item(row)).print.setEnabled(not printing)
+
+    def favorite_names(self) -> list[str]:
+        return [f.name for f in self._favorites]
+
+    def favorite_preview(self, row: int) -> QPixmap | None:
+        widget = self.favorites.itemWidget(self.favorites.item(row))
+        pixmap = widget.preview.pixmap()
+        return None if pixmap is None or pixmap.isNull() else pixmap
+
+    def open_favorite_at(self, row: int) -> None:
+        self.favorite_open.emit(self._favorites[row])
+
+    def print_favorite_at(self, row: int) -> None:
+        self.favorite_print.emit(self._favorites[row])
+
+    def favorite_menu(self, row: int) -> QMenu:
+        """Kontextmenü eines Favoriten."""
+        favorite = self._favorites[row]
+        menu = QMenu(self)
+        menu.addAction("Öffnen als neues Etikett", lambda: self.favorite_open.emit(favorite))
+        menu.addAction("Drucken", lambda: self.favorite_print.emit(favorite))
+        menu.addAction("Umbenennen …", lambda: self.favorite_rename.emit(favorite))
+        menu.addAction("Löschen …", lambda: self.favorite_remove.emit(favorite))
+        start = menu.addAction("Beim Start öffnen", lambda: self.favorite_start.emit(favorite))
+        start.setCheckable(True)
+        start.setChecked(favorite.name == self._start)
+        menu.addAction("Ordner öffnen", self.favorites_folder)
+        return menu
+
+    def _favorite_context(self, pos) -> None:
+        item = self.favorites.itemAt(pos)
+        if item is not None:
+            self.favorite_menu(self.favorites.row(item)).exec(
+                self.favorites.viewport().mapToGlobal(pos))
+
+    # --- Zuletzt geöffnet -------------------------------------------------
+    def set_recent(self, paths: list[str]) -> None:
+        """Zuletzt geöffnet: Name, Pfad im Tooltip; fehlt die Datei, ausgegraut."""
+        self._recent = list(paths)
+        self.recent.clear()
+        grey = self.palette().color(self.palette().ColorRole.PlaceholderText)
+        for path in paths:
+            item = QListWidgetItem(Path(path).stem)
+            item.setToolTip(path)
+            if not Path(path).exists():
+                item.setForeground(grey)
+            self.recent.addItem(item)
+        rows = min(len(paths), RECENT_ROWS)
+        _fit_height(self.recent, rows, self.recent.sizeHintForRow(0) if rows else 0)
+        self.recent.setVisible(bool(paths))
+
+    def recent_names(self) -> list[str]:
+        return [Path(p).stem for p in self._recent]
+
+    def open_recent_at(self, row: int) -> None:
+        self.recent_open.emit(self._recent[row])
+
+
+def _fit_height(view: QListWidget, rows: int, row_height: int) -> None:
+    """Liste so hoch wie ``rows`` Zeilen (mehr per Bildlauf) – der Rest des Panels bleibt sichtbar."""
+    frame = 2 * view.frameWidth()
+    view.setFixedHeight(rows * row_height + frame + (4 if rows else 0))
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 74a111d..b9d6026 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -15,7 +15,7 @@ from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                                QStyledItemDelegate, QTableWidget, QTableWidgetItem, QTabWidget,
                                QVBoxLayout, QWidget)
 
-from .. import shortcuts
+from .. import favorites, shortcuts
 from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
 from ..labels import labels_for_model
 from ..printer import DEFAULT_MODEL
@@ -45,7 +45,6 @@ class SettingsDialog(QDialog):
         self.saved: Settings | None = None
         self._symbols = (settings.symbols_recent, settings.symbols_favorites)   # nur durchgereicht
         self._recent_files = settings.recent_files                             # nur durchgereicht
-        self._start_favorite = settings.start_favorite
         outer = QVBoxLayout(self)
         self.tabs = QTabWidget()
         outer.addWidget(self.tabs)
@@ -92,6 +91,16 @@ class SettingsDialog(QDialog):
         self._family_touched = False
         self.font_family.currentFontChanged.connect(self._family_changed)
         form.addRow("Schriftart", self.font_family)
+        self.start_favorite = QComboBox()
+        self.start_favorite.addItem("Leeres Etikett", None)
+        for favorite in favorites.favorites():
+            self.start_favorite.addItem(favorite.name, favorite.name)
+        if settings.start_favorite and self.start_favorite.findData(settings.start_favorite) < 0:
+            # gelöscht oder umbenannt: sichtbar lassen, nicht still auf „leer“ setzen
+            self.start_favorite.addItem(f"{settings.start_favorite} (fehlt)", settings.start_favorite)
+        self.start_favorite.setCurrentIndex(max(0, self.start_favorite.findData(settings.start_favorite)))
+        self.start_favorite.setToolTip("Etikett, mit dem labelwerk startet (Favorit als Vorlage)")
+        form.addRow("Beim Start", self.start_favorite)
 
         form = self._section(layout, "Bilder einfügen")
         self.image_crop = QCheckBox("Automatisch zuschneiden (ohne Schnittmarken und Leerraum)")
@@ -295,7 +304,7 @@ class SettingsDialog(QDialog):
             symbols_recent=list(self._symbols[0]),
             symbols_favorites=list(self._symbols[1]),
             recent_files=list(self._recent_files),
-            start_favorite=self._start_favorite,
+            start_favorite=self.start_favorite.currentData(),
             shortcuts={action_id: seq for action_id, seq in self._keys.items()
                        if not _same(seq, shortcuts.action(action_id).default)},
         )
diff --git a/src/labelwerk/gui/tools.py b/src/labelwerk/gui/tools.py
index 0f1a8db..16effd1 100644
--- a/src/labelwerk/gui/tools.py
+++ b/src/labelwerk/gui/tools.py
@@ -9,6 +9,7 @@ from typing import Callable
 
 from ..document import Document
 from .panels import Panel
+from .panels.file import FilePanel
 from .panels.image import ImagePanel
 from .panels.layout import LayoutPanel
 from .panels.paper import PaperPanel
@@ -21,9 +22,13 @@ class Tool:
     title: str
     icon: str                                  # Name im Freedesktop-Icon-Theme
     panel: Callable[[Document], Panel]
+    tip: str = ""                              # Tooltip (sonst der Titel)
 
 
+START_TOOL = "paper"                           # Reiter beim Start
+
 TOOLS = [
+    Tool("file", "★", "", FilePanel, "Datei und Favoriten"),
     Tool("paper", "Papier", "document-page-setup", PaperPanel),
     Tool("text", "Text", "insert-text", TextPanel),
     Tool("image", "Bild", "insert-image", ImagePanel),
diff --git a/src/labelwerk/shortcuts.py b/src/labelwerk/shortcuts.py
index b537133..a6f5f34 100644
--- a/src/labelwerk/shortcuts.py
+++ b/src/labelwerk/shortcuts.py
@@ -27,6 +27,10 @@ class Action:
 
 
 ACTIONS: tuple[Action, ...] = (
+    Action("file.new", "Neues Etikett", "Ctrl+N", "global"),
+    Action("file.open", "Öffnen …", "Ctrl+O", "global"),
+    Action("file.save", "Speichern", "Ctrl+S", "global"),
+    Action("file.save_as", "Speichern unter …", "Ctrl+Shift+S", "global"),
     Action("file.print", "Drucken", "Ctrl+P", "global"),
     Action("app.settings", "Einstellungen", "Ctrl+,", "global"),
     Action("view.zoom_in", "Vergrößern (Zoom)", "Ctrl++", "global"),
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1683 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/gui/app.py src/labelwerk/gui/file_session.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/file.py src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/tools.py src/labelwerk/shortcuts.py tests/gui/conftest.py tests/gui/test_gui_files.py tests/gui/test_gui_image.py tests/gui/test_gui_layout.py tests/gui/test_gui_window.py
git commit -m "GUI: Reiter ★ – Neu/Öffnen/Speichern, Rückfrage bei Änderungen, Favoriten mit Vorschau und Direktdruck, Zuletzt geöffnet, Start mit Datei oder Favorit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Desktop – Dateityp *.labelwerk anmelden

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/desktop.py`
- Modify: `src/labelwerk/storage.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_desktop.py`

**Interfaces / Produces:** `desktop.MIME_TYPE`, `mime_xml()`, `update_databases(data, which, run) -> list[str]`, `install/uninstall(..., which, run, update)`, `Exec="…" %f` gequotet; CLI meldet gescheiterte Update-Werkzeuge und Schreibfehler; `storage.os_reason`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/test_cli.py b/tests/test_cli.py
index 76b0b9b..ee8f8d1 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -151,6 +151,9 @@ def test_busy_printer_gives_specific_hint(monkeypatch, capsys):
 
 def test_install_desktop_uses_xdg_data_home(tmp_path, monkeypatch, capsys):
     monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
+    monkeypatch.setattr("labelwerk.desktop.shutil.which", lambda name: None)   # kein update-…
+    monkeypatch.setattr("labelwerk.desktop.subprocess.run",
+                        lambda *a, **k: pytest.fail("externes Programm gestartet"))
     rc = main(["install-desktop"])
     assert rc == 0
     assert (tmp_path / "applications" / "labelwerk.desktop").exists()
@@ -338,3 +341,19 @@ def test_unloadable_font_gives_friendly_error(tmp_path, capsys):
 
 def test_align_left_changes_preview(tmp_path):
     assert _rich_preview(tmp_path, "--align", "left") != _rich_preview(tmp_path, "--align", "center")
+
+
+def test_install_desktop_write_error_is_a_message(tmp_path, monkeypatch, capsys):
+    blocker = tmp_path / "share"
+    blocker.write_text("kein Ordner")
+    monkeypatch.setenv("XDG_DATA_HOME", str(blocker))
+    monkeypatch.setattr("labelwerk.desktop.shutil.which", lambda name: None)
+    assert main(["install-desktop"]) == 2
+    assert "nicht eingetragen" in capsys.readouterr().err
+
+
+def test_install_desktop_reports_failed_update_tools(tmp_path, monkeypatch, capsys):
+    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
+    monkeypatch.setattr("labelwerk.desktop.update_databases", lambda data, **kw: ["update-mime-database"])
+    assert main(["install-desktop"]) == 0
+    assert "update-mime-database" in capsys.readouterr().err
diff --git a/tests/test_desktop.py b/tests/test_desktop.py
index 1695a47..f12a53d 100644
--- a/tests/test_desktop.py
+++ b/tests/test_desktop.py
@@ -1,6 +1,12 @@
+import functools
+
 import pytest
 
-from labelwerk.desktop import install, uninstall
+from labelwerk import desktop
+
+# ohne externe Programme (update-mime-database …): nichts gefunden
+install = functools.partial(desktop.install, which=lambda name: None)
+uninstall = functools.partial(desktop.uninstall, which=lambda name: None)
 
 
 @pytest.fixture
@@ -16,9 +22,9 @@ def test_install_writes_desktop_entry_and_icon(tmp_path, gui_exe):
     paths = install(gui_exe, data)
     entry = data / "applications" / "labelwerk.desktop"
     icon = data / "icons" / "hicolor" / "scalable" / "apps" / "labelwerk.svg"
-    assert set(paths) == {entry, icon}
+    assert {entry, icon} <= set(paths)
     text = entry.read_text()
-    assert f"Exec={gui_exe}\n" in text
+    assert f'Exec="{gui_exe}" %f\n' in text
     assert "Icon=labelwerk\n" in text
     assert "StartupWMClass=labelwerk\n" in text
     assert icon.read_text().lstrip().startswith("<svg")
@@ -45,6 +51,102 @@ def test_uninstall_removes_files(tmp_path, gui_exe):
 
 
 def test_display_name_comes_from_app_name(tmp_path, gui_exe, monkeypatch):
-    import labelwerk.desktop as desktop
     monkeypatch.setattr(desktop, "APP_NAME", "Neuer Name")
     assert "Name=Neuer Name\n" in desktop.desktop_entry(gui_exe)
+
+
+# --- Dateityp *.labelwerk (Etappe 3c) ---------------------------------------------------
+class Runner:
+    """Ersatz für externe Programme: merkt die Aufrufe, startet nichts."""
+
+    def __init__(self, available=True):
+        self.calls = []
+        self.available = available
+
+    def which(self, name):
+        return f"/usr/bin/{name}" if self.available else None
+
+    def run(self, args, **kwargs):
+        self.calls.append(args)
+
+
+def test_install_registers_the_file_type(tmp_path, gui_exe):
+    data = tmp_path / "share"
+    runner = Runner()
+    paths = desktop.install(gui_exe, data, which=runner.which, run=runner.run)
+    mime = data / "mime" / "packages" / "labelwerk.xml"
+    mime_icon = data / "icons" / "hicolor" / "scalable" / "mimetypes" / "application-x-labelwerk.svg"
+    assert mime in paths and mime_icon in paths
+    xml = mime.read_text()
+    assert 'type="application/x-labelwerk"' in xml and 'pattern="*.labelwerk"' in xml
+    entry = (data / "applications" / "labelwerk.desktop").read_text()
+    assert f'Exec="{gui_exe}" %f\n' in entry and "MimeType=application/x-labelwerk;\n" in entry
+    assert runner.calls == [["/usr/bin/update-mime-database", str(data / "mime")],
+                            ["/usr/bin/update-desktop-database", str(data / "applications")]]
+
+
+def test_install_without_update_tools_still_works(tmp_path, gui_exe):
+    runner = Runner(available=False)
+    desktop.install(gui_exe, tmp_path / "share", which=runner.which, run=runner.run)
+    assert runner.calls == []
+
+
+def test_uninstall_removes_the_file_type(tmp_path, gui_exe):
+    data = tmp_path / "share"
+    runner = Runner()
+    desktop.install(gui_exe, data, which=runner.which, run=runner.run)
+    runner.calls.clear()
+    removed = desktop.uninstall(data, which=runner.which, run=runner.run)
+    assert data / "mime" / "packages" / "labelwerk.xml" in removed
+    assert not (data / "mime" / "packages" / "labelwerk.xml").exists()
+    assert ["/usr/bin/update-mime-database", str(data / "mime")] in runner.calls
+
+
+def test_failing_update_tool_is_no_error(tmp_path, gui_exe):
+    import subprocess
+
+    def broken(args, **kwargs):
+        raise subprocess.CalledProcessError(1, args)
+    desktop.install(gui_exe, tmp_path / "share", which=Runner().which, run=broken)
+
+
+def test_exec_path_with_spaces_and_special_characters_is_quoted(tmp_path):
+    """Desktop-Entry-Spezifikation: Pfad in Anführungszeichen, \\ " ` $ maskiert, % verdoppelt."""
+    exe = tmp_path / "mein Ordner $x 100%" / "labelwerk-gui"
+    exe.parent.mkdir()
+    exe.write_text("#!/bin/sh\n")
+    entry = desktop.desktop_entry(exe)
+    quoted = str(exe).replace("$", "\\\\$").replace("%", "%%")
+    assert f'Exec="{quoted}" %f\n' in entry
+
+
+def test_uninstall_updates_both_databases_and_nothing_installed_does_nothing(tmp_path, gui_exe):
+    data = tmp_path / "share"
+    runner = Runner()
+    assert desktop.uninstall(data, which=runner.which, run=runner.run) == []
+    assert runner.calls == []
+    desktop.install(gui_exe, data, which=runner.which, run=runner.run)
+    runner.calls.clear()
+    desktop.uninstall(data, which=runner.which, run=runner.run)
+    assert ["/usr/bin/update-desktop-database", str(data / "applications")] in runner.calls
+
+
+@pytest.mark.parametrize("error", [OSError("fehlt"), "timeout"])
+def test_failing_update_tool_is_reported(tmp_path, gui_exe, error):
+    import subprocess
+
+    def broken(args, **kwargs):
+        if error == "timeout":
+            raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))
+        raise error
+    failed = desktop.update_databases(tmp_path, which=Runner().which, run=broken)
+    assert failed == []                                  # Ordner fehlen: nichts aufgerufen
+    desktop.install(gui_exe, tmp_path / "share", which=lambda n: None)
+    failed = desktop.update_databases(tmp_path / "share", which=Runner().which, run=broken)
+    assert failed == ["update-mime-database", "update-desktop-database"]
+
+
+def test_mime_comment_has_english_fallback_and_german(tmp_path):
+    xml = desktop.mime_xml()
+    assert "<comment>labelwerk label</comment>" in xml
+    assert '<comment xml:lang="de">labelwerk-Etikett</comment>' in xml
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests in tests/test_desktop.py und tests/test_cli.py schlagen fehl (fehlende Namen `update_databases`, `mime_xml` …), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index bd7c15b..00f518e 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -19,8 +19,8 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Bildschirmfoto (Etappe 3d-2b): Knopf BILDSCHIRMFOTO im Reiter Bild – labelwerk blendet sich aus, der Desktop zeigt seine Auswahl (XDG-Portal), das Bild kommt mit 300 dpi aufs Etikett; ohne Portal Hinweis auf Zwischenablage + Strg+V.
 - SVG-Dateien sind Vektorbilder: in jeder Größe scharf gerastert (Etappe 3d-2c).
 - Symbole/ClipArt (Etappe 3d-2c): Knopf SYMBOL im Reiter Bild – Fenster „Symbol einfügen“ (bleibt offen; Suche über die ganze Bibliothek, Gruppen Zuletzt verwendet/Favoriten/Elektro/Versand/Sicherheit/Allgemein/Eigene, Doppelklick/Enter/Ziehen fügt ein); Symbole 15 mm, Vektor, zugeschnitten.
-- Datei und Favoriten (Etappe 3c): Reiter ★ – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“).
-- 1683 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Datei und Favoriten (Etappe 3c): Reiter ★ – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“); `labelwerk install-desktop` meldet *.labelwerk an (Doppelklick öffnet).
+- 1694 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -87,7 +87,9 @@ src/labelwerk/
               nur quer), set_crop (Maßstab und Lage des Inhalts bleiben), original_size, set_keep_ratio, proportional
   shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
               without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
-  desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
+  desktop.py  .desktop-Eintrag (Exec … %f, MimeType) + Icon + Dateityp application/x-labelwerk (*.labelwerk, mime/packages,
+              Icon) installieren/entfernen (XDG_DATA_HOME), Exec-Pfad gequotet; update_databases (update-mime-/-desktop-database, gescheiterte → Hinweis)
+              (which/run ersetzbar – Tests starten keine Programme); APP_ID
   gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
     main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
                     shortcut_actions (Aktions-ID → QAction); rendert über render.Renderer; leere Textrahmen entfallen beim Abwählen;
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index dace9a1..7b1471c 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -17,6 +17,7 @@ from .labels import format_mm, labels_for_model
 from .media import MediaError, label_for_media, read_media
 from .render import font_warnings, render_document
 from .settings import load_settings
+from .storage import os_reason
 
 
 def _font_size(value: str) -> float | None:
@@ -184,22 +185,40 @@ def _apply_settings(args: argparse.Namespace) -> None:
 
 
 def _install_desktop(remove: bool) -> int:
+    data = desktop.data_home()
     if remove:
-        removed = desktop.uninstall()
+        try:
+            removed = desktop.uninstall(data, update=False)
+        except OSError as e:
+            print(f"labelwerk wurde nicht entfernt ({os_reason(e)}).", file=sys.stderr)
+            return 2
         print("\n".join(f"Entfernt: {p}" for p in removed) or "Nichts zu entfernen.")
+        if removed:
+            _report_update(desktop.update_databases(data))
         return 0
     gui_exe = Path(sys.executable).parent / "labelwerk-gui"
     try:
-        paths = desktop.install(gui_exe)
+        paths = desktop.install(gui_exe, data, update=False)
     except ValueError as e:
         print(e, file=sys.stderr)
         return 2
+    except OSError as e:
+        print(f"labelwerk wurde nicht eingetragen ({os_reason(e)}).", file=sys.stderr)
+        return 2
     for path in paths:
         print(f"Installiert: {path}")
-    print("labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden).")
+    _report_update(desktop.update_databases(data))
+    print("labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden); "
+          "Doppelklick auf eine .labelwerk-Datei öffnet sie.")
     return 0
 
 
+def _report_update(failed: list[str]) -> None:
+    if failed:
+        print(f"Hinweis: {', '.join(failed)} hat nicht geklappt – Dateizuordnung gilt ggf. erst "
+              f"nach neuer Anmeldung.", file=sys.stderr)
+
+
 def main(argv: list[str] | None = None) -> int:
     args = _parser().parse_args(argv)
 
diff --git a/src/labelwerk/desktop.py b/src/labelwerk/desktop.py
index 266f55a..dc4dd1d 100644
--- a/src/labelwerk/desktop.py
+++ b/src/labelwerk/desktop.py
@@ -1,27 +1,57 @@
-"""Starter-Eintrag (.desktop) und Icon für die Desktop-Umgebung (XDG, z. B. COSMIC/GNOME)."""
+"""Starter-Eintrag (.desktop), Icon und Dateityp *.labelwerk für die Desktop-Umgebung (XDG,
+z. B. COSMIC/GNOME): Doppelklick auf eine Etikett-Datei öffnet sie in labelwerk."""
 from __future__ import annotations
 
 import os
+import shutil
+import subprocess
 from importlib import resources
 from pathlib import Path
 
 APP_NAME = "labelwerk"  # angezeigter Name (Fenster, Starter, Hilfe) – Umbenennen: CLAUDE.md, Roadmap 7
 APP_ID = "labelwerk"    # technische ID; muss zu QGuiApplication.setDesktopFileName passen
+MIME_TYPE = "application/x-labelwerk"      # Etikett-Datei *.labelwerk
+MIME_ICON = MIME_TYPE.replace("/", "-")    # Icon-Name nach XDG (shared-mime-info leitet ihn ab)
 
 
 def data_home() -> Path:
     return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
 
 
-def _targets(data: Path) -> tuple[Path, Path]:
-    return (data / "applications" / f"{APP_ID}.desktop",
-            data / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg")
+def _targets(data: Path) -> tuple[Path, Path, Path, Path]:
+    """Starter-Eintrag, App-Icon, Dateityp (shared-mime-info), Icon des Dateityps."""
+    icons = data / "icons" / "hicolor" / "scalable"
+    return (data / "applications" / f"{APP_ID}.desktop", icons / "apps" / f"{APP_ID}.svg",
+            data / "mime" / "packages" / f"{APP_ID}.xml", icons / "mimetypes" / f"{MIME_ICON}.svg")
+
+
+def mime_xml() -> str:
+    return (
+        '<?xml version="1.0" encoding="UTF-8"?>\n'
+        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
+        f'  <mime-type type="{MIME_TYPE}">\n'
+        f"    <comment>{APP_NAME} label</comment>\n"
+        f'    <comment xml:lang="de">{APP_NAME}-Etikett</comment>\n'
+        '    <sub-class-of type="application/json"/>\n'
+        '    <glob pattern="*.labelwerk"/>\n'
+        "  </mime-type>\n"
+        "</mime-info>\n")
 
 
 def icon_svg() -> str:
     return (resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg").read_text(encoding="utf-8")
 
 
+def _exec_arg(path: Path) -> str:
+    """Pfad als Argument für ``Exec=`` (Desktop-Entry-Spezifikation): in Anführungszeichen,
+    \\ " ` $ mit Backslash maskiert, dann jeder Backslash für die Zeichenkette der Datei noch
+    einmal verdoppelt; % als %% (sonst ein Feldcode)."""
+    text = str(path)
+    for char in ("\\", '"', "`", "$"):
+        text = text.replace(char, "\\" + char)
+    return '"' + text.replace("\\", "\\\\").replace("%", "%%") + '"'
+
+
 def desktop_entry(gui_exe: Path) -> str:
     return (
         "[Desktop Entry]\n"
@@ -29,8 +59,9 @@ def desktop_entry(gui_exe: Path) -> str:
         f"Name={APP_NAME}\n"
         "GenericName=Etikettendruck\n"
         "Comment=Etiketten gestalten und drucken (Brother QL)\n"
-        f"Exec={gui_exe}\n"
+        f"Exec={_exec_arg(gui_exe)} %f\n"
         f"Icon={APP_ID}\n"
+        f"MimeType={MIME_TYPE};\n"
         "Terminal=false\n"
         "Categories=Office;\n"
         "Keywords=Etikett;Label;Brother;QL;Drucker;P-touch;\n"
@@ -38,25 +69,55 @@ def desktop_entry(gui_exe: Path) -> str:
     )
 
 
-def install(gui_exe: Path, data: Path | None = None) -> list[Path]:
-    """Starter-Eintrag und Icon schreiben; vorhandene werden überschrieben."""
+UPDATE_TIMEOUT_S = 20
+
+
+def update_databases(data: Path, which=None, run=None) -> list[str]:
+    """Datenbanken der Desktop-Umgebung auffrischen (falls die Werkzeuge da sind); gibt die
+    gescheiterten Werkzeuge zurück – spätestens nach neuer Anmeldung gilt der Eintrag trotzdem.
+    ``which``/``run`` erst hier aufgelöst (in Tests ersetzbar, auch über das Modul)."""
+    which, run = which or shutil.which, run or subprocess.run
+    failed = []
+    for tool, folder in (("update-mime-database", data / "mime"),
+                         ("update-desktop-database", data / "applications")):
+        exe = which(tool)
+        if exe is None or not folder.is_dir():
+            continue
+        try:
+            run([exe, str(folder)], check=True, capture_output=True, timeout=UPDATE_TIMEOUT_S)
+        except (OSError, subprocess.SubprocessError):
+            failed.append(tool)
+    return failed
+
+
+def install(gui_exe: Path, data: Path | None = None, which=None, run=None,
+            update: bool = True) -> list[Path]:
+    """Starter-Eintrag, Icon und Dateityp schreiben; vorhandene werden überschrieben. Danach
+    (``update``) die Datenbanken auffrischen (``update_databases``). Schreibfehler: ``OSError``."""
     gui_exe = Path(gui_exe)
     if not gui_exe.exists():
         raise ValueError(f"labelwerk-gui nicht gefunden ({gui_exe}) – "
                          "GUI installiert? pip install -e \".[gui]\"")
-    entry, icon = _targets(data or data_home())
-    for path in (entry, icon):
+    data = data or data_home()
+    entry, icon, mime, mime_icon = _targets(data)
+    contents = {entry: desktop_entry(gui_exe.resolve()), icon: icon_svg(), mime: mime_xml(),
+                mime_icon: icon_svg()}
+    for path, text in contents.items():
         path.parent.mkdir(parents=True, exist_ok=True)
-    entry.write_text(desktop_entry(gui_exe.resolve()), encoding="utf-8")
-    icon.write_text(icon_svg(), encoding="utf-8")
-    return [entry, icon]
+        path.write_text(text, encoding="utf-8")
+    if update:
+        update_databases(data, which, run)
+    return list(contents)
 
 
-def uninstall(data: Path | None = None) -> list[Path]:
-    """Starter-Eintrag und Icon entfernen; gibt die entfernten Dateien zurück."""
+def uninstall(data: Path | None = None, which=None, run=None, update: bool = True) -> list[Path]:
+    """Starter-Eintrag, Icon und Dateityp entfernen; gibt die entfernten Dateien zurück."""
+    data = data or data_home()
     removed = []
-    for path in _targets(data or data_home()):
+    for path in _targets(data):
         if path.exists():
             path.unlink()
             removed.append(path)
+    if removed and update:
+        update_databases(data, which, run)
     return removed
diff --git a/src/labelwerk/storage.py b/src/labelwerk/storage.py
index 99d5550..edc7369 100644
--- a/src/labelwerk/storage.py
+++ b/src/labelwerk/storage.py
@@ -101,7 +101,7 @@ class StorageError(ValueError):
     """Datei lässt sich nicht als Etikett lesen (Meldung auf Deutsch, mit Dateiname)."""
 
 
-def _reason(error: OSError) -> str:
+def os_reason(error: OSError) -> str:
     """Grund eines Datei-Fehlers auf Deutsch (statt englischem Text des Betriebssystems)."""
     if isinstance(error, FileNotFoundError):
         return "Ordner fehlt"
@@ -173,7 +173,7 @@ def save(doc: Document, path: str | Path) -> Path:
         os.replace(tmp, target)
         tmp = None
     except OSError as e:
-        raise OSError(f"{path.name} wurde nicht gespeichert ({_reason(e)})") from e
+        raise OSError(f"{path.name} wurde nicht gespeichert ({os_reason(e)})") from e
     finally:
         if tmp is not None:
             Path(tmp).unlink(missing_ok=True)
@@ -286,7 +286,7 @@ def load(path: str | Path) -> Document:
     except FileNotFoundError as e:
         raise StorageError(f"Datei nicht gefunden: {path}") from e
     except OSError as e:
-        raise StorageError(f"{path.name} kann nicht gelesen werden ({_reason(e)})") from e
+        raise StorageError(f"{path.name} kann nicht gelesen werden ({os_reason(e)})") from e
     except UnicodeDecodeError as e:
         raise StorageError(f"{path.name}: keine labelwerk-Datei (kein UTF-8-Text)") from e
     try:
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1694 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/cli.py src/labelwerk/desktop.py src/labelwerk/storage.py tests/test_cli.py tests/test_desktop.py
git commit -m "Desktop: Dateityp *.labelwerk anmelden – Doppelklick im Dateimanager öffnet in labelwerk

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Abnahme (manuell, durch den Nutzer)

- [ ] Reiter ★: Etikett gestalten, SPEICHERN (Dialog, Endung ergänzt), Titel ohne „•“; ändern → „•“; Schließen fragt.
- [ ] ÖFFNEN, Zuletzt geöffnet (auch eine gelöschte Datei: ausgegraut, Hinweis), NEU.
- [ ] + AKTUELL als Favorit „Absender“; Klick öffnet als neues Etikett; ⎙ druckt direkt (offenes Etikett bleibt); Umbenennen/Löschen; „Beim Start öffnen“ und Einstellungen → Beim Start; Neustart startet mit dem Favoriten.
- [ ] `labelwerk install-desktop` erneut ausführen; Doppelklick auf eine .labelwerk-Datei im Dateimanager öffnet sie.
- [ ] Mit eingelegter anderer Rolle: geöffnete Datei wird nicht umgestellt (Panel „passt nicht“), neues Etikett folgt der Rolle.
