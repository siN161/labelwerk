# Drucker-Kompatibilität – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** labelwerk erkennt das Druckermodell, richtet Etiketten, Abschneider und Farben danach, kann Netzwerkdrucker und mehrere Drucker, druckt Rot/Schwarz (ungeprüft) und hält die Rasterdaten je Modell mit Referenztests fest.

**Architecture:** Kern `printers.py` (Drucker-Beschreibung, Erkennung über sysfs ohne USB-Zugriff, Fähigkeiten aus brother_ql) – Grundlage für spätere Fremdhersteller; `labels`/`printer`/`render`/`settings`/`cli` nutzen ihn; die GUI wählt den Drucker in der Statusleiste und folgt seinem Modell.

**Tech Stack:** Python ≥ 3.10, Pillow, brother_ql-inventree 1.3.x, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-19-drucker-kompatibilitaet-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-compat-gui`), nach jedem Task volle Suite grün mit Exit-Code 0 (2238 → 2310 → 2337); jeder Schritt von einem Reviewer geprüft und korrigiert (Kern: Modell folgt dem angegebenen Drucker `-p`, Etikett muss zum Modell passen, Rot nur auf Zweifarb-Modellen und mit derselben Schwelle wie Schwarz-Weiß, Netzwerk mit Zeitlimit, belegtes USB-Gerät als Meldung, Brother-Laser nicht vor QL, Referenzbild ohne Pillow-Linien; GUI: Druckerwechsel vergisst die Rolle, Etikett eines anderen Druckers bleibt erhalten bzw. neues nimmt ein passendes, gewählter Drucker wird nicht still ersetzt, Schwarz immer wählbar, Einträge „passt nicht“ nicht wählbar).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Neue Felder im Dokument gehören ins Speicherformat (Schema-Test); Tabellen und Dateien sind fremde Eingabe (nie ein Traceback).
- Keine neue Abhängigkeit; brother_ql-inventree wird auf `<1.4` begrenzt (Referenztests hashen seine Rasterdaten).
- Kern bleibt **Qt-frei** (`printers.py`, `labels.py`, `printer.py`, `render.py`, `settings.py`, `cli.py`); kein Test erreicht echte Hardware oder das Netz (`send`, `socket.create_connection` sind in tests/conftest.py gesperrt, sysfs ist leer); **Vorschau = Druck**; **nie den echten Drucker ansprechen** (Rasterdaten prüfen, `send`/`PrintWorker` ersetzen).
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten, ohne echte Dialoge; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen und Kommentare auf Deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Kern – Drucker erkennen, Fähigkeiten je Modell, Netzwerk, Rot/Schwarz, CLI, Referenztests

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/labels.py`
- Modify: `src/labelwerk/printer.py`
- Create: `src/labelwerk/printers.py`
- Modify: `src/labelwerk/render.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `src/labelwerk/storage.py`
- Modify: `tests/conftest.py`
- Create: `tests/golden/raster.json`
- Modify: `tests/test_cli.py`
- Create: `tests/test_golden.py`
- Create: `tests/test_printers.py`
- Create: `tools/golden.py`

**Interfaces / Produces:** `printers.py` (`Printer(uri, model, name, source)`, `usb_printers(sys_root)`, `SYS_ROOT`, `NetworkEntry`, `network_printers`, `choose(printers, wanted)`, `printer_for(uri, found)`, `effective_model(printer, fallback, last)`, `Capabilities`/`capabilities(model)`, `known_model`, `backend_for`, `SUPPORTED_MODELS`, `TESTED_MODELS`, `PRODUCT_IDS`, `UNTESTED_HINT`, `DEFAULT_MODEL`); `labels.labels_for_model` aus den Fähigkeiten, `Label.two_color`; `printer`: `pure_colors`, `to_print_mode(image, red)`, Etikett muss zum Modell passen, ohne Abschneider kein Schnitt, Netzwerk mit Zeitlimit (`_reachable`), `print_image(…, backend=None)`; `document.COLORS`, `color` an Text/Bild/Barcode; `render.INK`, `RenderedObject.color`; `settings`: `printer`, `printer_model`, `last_model`, `network_printers`, `valid_host`, `network_entries`, `load_settings(path, model=None)`; CLI `-m auto`, `-l auto`, `printers`; `tools/golden.py`, `tests/golden/raster.json`; brother_ql auf 1.3.x.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/conftest.py b/tests/conftest.py
index 1f36cb5..e35f482 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -9,6 +9,12 @@ def isolated_config(monkeypatch, tmp_path_factory):
     monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path_factory.mktemp("data")))
 
 
+@pytest.fixture(autouse=True)
+def no_real_sysfs(monkeypatch, tmp_path_factory):
+    """Kein Test sieht echte Drucker in /sys (Erkennung über ``printers.usb_printers``)."""
+    monkeypatch.setattr("labelwerk.printers.SYS_ROOT", str(tmp_path_factory.mktemp("usbmisc")))
+
+
 @pytest.fixture(autouse=True)
 def no_leftover_rasterizer():
     """Das Hauptfenster meldet die Qt-Raster-Funktion für Vektorbilder an – danach wieder ohne,
@@ -34,5 +40,6 @@ def no_real_hardware(monkeypatch):
         return blocked
     monkeypatch.setattr("labelwerk.media.query_status", guard("query_status"))
     monkeypatch.setattr("labelwerk.printer.send", guard("send"))
+    monkeypatch.setattr("labelwerk.printer.socket.create_connection", guard("create_connection"))
     yield
     assert not calls, f"Test hat echte Hardware-Funktionen erreicht: {calls}"
diff --git a/tests/golden/raster.json b/tests/golden/raster.json
new file mode 100644
index 0000000..bca934d
--- /dev/null
+++ b/tests/golden/raster.json
@@ -0,0 +1,118 @@
+{
+ "QL-1050": {
+  "102": "06b47322257575ee14956abbb1db47ea7a46565ea64dba95251ced25ec4f364c",
+  "62": "4c47164f95e92eb4ca8f7f0f56ca307fb7a87e96367db64d9a5817ce5a56260b",
+  "62-ohne-schnitt": "3a53c8c5cd18cd786d24a8e2f3b8f5bf18b3e60a152c9972fb4112af4ffc32c0",
+  "62-serie": "a594e6fd699e7dd29ff230e65770dc9c03c3d8073028ddb174e6f159b4967a68",
+  "62x29": "d43ade317b609567f0dc93fd64cd9bbcea3d8ef673f5a9d25d6733a32d0226a9"
+ },
+ "QL-1060N": {
+  "102": "06b47322257575ee14956abbb1db47ea7a46565ea64dba95251ced25ec4f364c",
+  "62": "4c47164f95e92eb4ca8f7f0f56ca307fb7a87e96367db64d9a5817ce5a56260b",
+  "62-ohne-schnitt": "3a53c8c5cd18cd786d24a8e2f3b8f5bf18b3e60a152c9972fb4112af4ffc32c0",
+  "62-serie": "a594e6fd699e7dd29ff230e65770dc9c03c3d8073028ddb174e6f159b4967a68",
+  "62x29": "d43ade317b609567f0dc93fd64cd9bbcea3d8ef673f5a9d25d6733a32d0226a9"
+ },
+ "QL-1100": {
+  "102": "06b47322257575ee14956abbb1db47ea7a46565ea64dba95251ced25ec4f364c",
+  "62": "4c47164f95e92eb4ca8f7f0f56ca307fb7a87e96367db64d9a5817ce5a56260b",
+  "62-ohne-schnitt": "3a53c8c5cd18cd786d24a8e2f3b8f5bf18b3e60a152c9972fb4112af4ffc32c0",
+  "62-serie": "a594e6fd699e7dd29ff230e65770dc9c03c3d8073028ddb174e6f159b4967a68",
+  "62x29": "d43ade317b609567f0dc93fd64cd9bbcea3d8ef673f5a9d25d6733a32d0226a9"
+ },
+ "QL-1110NWB": {
+  "102": "06b47322257575ee14956abbb1db47ea7a46565ea64dba95251ced25ec4f364c",
+  "62": "4c47164f95e92eb4ca8f7f0f56ca307fb7a87e96367db64d9a5817ce5a56260b",
+  "62-ohne-schnitt": "3a53c8c5cd18cd786d24a8e2f3b8f5bf18b3e60a152c9972fb4112af4ffc32c0",
+  "62-serie": "a594e6fd699e7dd29ff230e65770dc9c03c3d8073028ddb174e6f159b4967a68",
+  "62x29": "d43ade317b609567f0dc93fd64cd9bbcea3d8ef673f5a9d25d6733a32d0226a9"
+ },
+ "QL-1115NWB": {
+  "102": "06b47322257575ee14956abbb1db47ea7a46565ea64dba95251ced25ec4f364c",
+  "62": "4c47164f95e92eb4ca8f7f0f56ca307fb7a87e96367db64d9a5817ce5a56260b",
+  "62-ohne-schnitt": "3a53c8c5cd18cd786d24a8e2f3b8f5bf18b3e60a152c9972fb4112af4ffc32c0",
+  "62-serie": "a594e6fd699e7dd29ff230e65770dc9c03c3d8073028ddb174e6f159b4967a68",
+  "62x29": "d43ade317b609567f0dc93fd64cd9bbcea3d8ef673f5a9d25d6733a32d0226a9"
+ },
+ "QL-500": {
+  "62": "39a9f42dd74a07f3bb99d1b3c95ebc84d59392a6e26e16a76fa41bf592d6a608",
+  "62-ohne-schnitt": "39a9f42dd74a07f3bb99d1b3c95ebc84d59392a6e26e16a76fa41bf592d6a608",
+  "62-serie": "8242b3de4a8e858946a336c763e761e85a0051d643d1646d4643ca602c96f608",
+  "62x29": "a157186e4a741497d150d494188f5a47f31d9e6715e288b4af3888eb1f622d10"
+ },
+ "QL-550": {
+  "62": "560a52a793e76273acbf1de1a7e650c5d9e02a6ba68d77e7c78ce34d50291ed0",
+  "62-ohne-schnitt": "68670419308626037e412900e85e1b4e22d1c36759cd037a8c75a71f2a37f74f",
+  "62-serie": "9e31c2c9e723ce93dcffb891b92c1c2cbe74bb40d263d9465b99db4740030834",
+  "62x29": "0f053fad7a468aab93490f7bd52fdf19a1c659203fe1ace86257cde5ec90161b"
+ },
+ "QL-560": {
+  "62": "560a52a793e76273acbf1de1a7e650c5d9e02a6ba68d77e7c78ce34d50291ed0",
+  "62-ohne-schnitt": "68670419308626037e412900e85e1b4e22d1c36759cd037a8c75a71f2a37f74f",
+  "62-serie": "9e31c2c9e723ce93dcffb891b92c1c2cbe74bb40d263d9465b99db4740030834",
+  "62x29": "0f053fad7a468aab93490f7bd52fdf19a1c659203fe1ace86257cde5ec90161b"
+ },
+ "QL-570": {
+  "62": "560a52a793e76273acbf1de1a7e650c5d9e02a6ba68d77e7c78ce34d50291ed0",
+  "62-ohne-schnitt": "68670419308626037e412900e85e1b4e22d1c36759cd037a8c75a71f2a37f74f",
+  "62-serie": "9e31c2c9e723ce93dcffb891b92c1c2cbe74bb40d263d9465b99db4740030834",
+  "62x29": "0f053fad7a468aab93490f7bd52fdf19a1c659203fe1ace86257cde5ec90161b"
+ },
+ "QL-580N": {
+  "62": "31d5d0fd1c06cdf6302ff71e1b15e2b25e3c1a8fd8083a56c818a66f54740378",
+  "62-ohne-schnitt": "303049e435b884e181afb9de00c6948b876637715fa4a137922f5f8e63f09ecc",
+  "62-serie": "c52a48becbec5f09713666947d5d382b6cd4a4c0b3e4e9396438a5bac4edfc6c",
+  "62x29": "4e55066c27f729ef90a387fedcdbc905bc8f39ef08b295e2f4432b437392ed7b"
+ },
+ "QL-600": {
+  "62": "31d5d0fd1c06cdf6302ff71e1b15e2b25e3c1a8fd8083a56c818a66f54740378",
+  "62-ohne-schnitt": "303049e435b884e181afb9de00c6948b876637715fa4a137922f5f8e63f09ecc",
+  "62-serie": "c52a48becbec5f09713666947d5d382b6cd4a4c0b3e4e9396438a5bac4edfc6c",
+  "62x29": "4e55066c27f729ef90a387fedcdbc905bc8f39ef08b295e2f4432b437392ed7b"
+ },
+ "QL-650TD": {
+  "62": "31d5d0fd1c06cdf6302ff71e1b15e2b25e3c1a8fd8083a56c818a66f54740378",
+  "62-ohne-schnitt": "303049e435b884e181afb9de00c6948b876637715fa4a137922f5f8e63f09ecc",
+  "62-serie": "c52a48becbec5f09713666947d5d382b6cd4a4c0b3e4e9396438a5bac4edfc6c",
+  "62x29": "4e55066c27f729ef90a387fedcdbc905bc8f39ef08b295e2f4432b437392ed7b"
+ },
+ "QL-700": {
+  "62": "560a52a793e76273acbf1de1a7e650c5d9e02a6ba68d77e7c78ce34d50291ed0",
+  "62-ohne-schnitt": "68670419308626037e412900e85e1b4e22d1c36759cd037a8c75a71f2a37f74f",
+  "62-serie": "9e31c2c9e723ce93dcffb891b92c1c2cbe74bb40d263d9465b99db4740030834",
+  "62x29": "0f053fad7a468aab93490f7bd52fdf19a1c659203fe1ace86257cde5ec90161b"
+ },
+ "QL-710W": {
+  "62": "31d5d0fd1c06cdf6302ff71e1b15e2b25e3c1a8fd8083a56c818a66f54740378",
+  "62-ohne-schnitt": "303049e435b884e181afb9de00c6948b876637715fa4a137922f5f8e63f09ecc",
+  "62-serie": "c52a48becbec5f09713666947d5d382b6cd4a4c0b3e4e9396438a5bac4edfc6c",
+  "62x29": "4e55066c27f729ef90a387fedcdbc905bc8f39ef08b295e2f4432b437392ed7b"
+ },
+ "QL-720NW": {
+  "62": "31d5d0fd1c06cdf6302ff71e1b15e2b25e3c1a8fd8083a56c818a66f54740378",
+  "62-ohne-schnitt": "303049e435b884e181afb9de00c6948b876637715fa4a137922f5f8e63f09ecc",
+  "62-serie": "c52a48becbec5f09713666947d5d382b6cd4a4c0b3e4e9396438a5bac4edfc6c",
+  "62x29": "4e55066c27f729ef90a387fedcdbc905bc8f39ef08b295e2f4432b437392ed7b"
+ },
+ "QL-800": {
+  "62": "0314de823e92a00771b72689faffd0726437e9a60a6ad1a9ade2c3b1c8fa8c90",
+  "62-ohne-schnitt": "10c321787fd5fb1bcf437c967d6f3c364ee27c4faae8ec43c849eac1a4c59660",
+  "62-serie": "ca3921378c6ae5d3e418d27ce00c74c882272eab35adb553327dd079418197b7",
+  "62red": "19eaeea1060cb095734963a22d71aca1d8c71199804e3925b198368ccec951c6",
+  "62x29": "623c3f9e871631b93f38303b4118df9f64c13f76994a5684f7b7fc9ed751eced"
+ },
+ "QL-810W": {
+  "62": "ca6671788e48070990e8ea78b62e2598b0b25c93db8af64075607a5612f51193",
+  "62-ohne-schnitt": "0c3ff1532f9723402a4927dbc264017a0d21509e8d1316dff2bfe731210a3813",
+  "62-serie": "add99f9db45db791b462d45122ca026a6e1ece4daf3f3384b4a8ffde56603723",
+  "62red": "4fdb1ef39fb0e243b64a95beb6464892a3406cb68e1753bb5584c0922383bff4",
+  "62x29": "985a654b6b81165290bdd0770f95a9f5867fdc7b44c45fb9b677b36a7ebdcbae"
+ },
+ "QL-820NWB": {
+  "62": "ca6671788e48070990e8ea78b62e2598b0b25c93db8af64075607a5612f51193",
+  "62-ohne-schnitt": "0c3ff1532f9723402a4927dbc264017a0d21509e8d1316dff2bfe731210a3813",
+  "62-serie": "add99f9db45db791b462d45122ca026a6e1ece4daf3f3384b4a8ffde56603723",
+  "62red": "4fdb1ef39fb0e243b64a95beb6464892a3406cb68e1753bb5584c0922383bff4",
+  "62x29": "985a654b6b81165290bdd0770f95a9f5867fdc7b44c45fb9b677b36a7ebdcbae"
+ }
+}
diff --git a/tests/test_cli.py b/tests/test_cli.py
index ee8f8d1..35cae29 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -357,3 +357,114 @@ def test_install_desktop_reports_failed_update_tools(tmp_path, monkeypatch, caps
     monkeypatch.setattr("labelwerk.desktop.update_databases", lambda data, **kw: ["update-mime-database"])
     assert main(["install-desktop"]) == 0
     assert "update-mime-database" in capsys.readouterr().err
+
+
+# --- Drucker-Kompatibilität ----------------------------------------------------------------------
+def _detected(monkeypatch, *found):
+    from labelwerk.printers import Printer
+    monkeypatch.setattr("labelwerk.cli.printers.usb_printers",
+                        lambda *a, **k: [Printer(uri, model, f"{model} · x") for uri, model in found])
+
+
+def test_model_auto_uses_the_detected_printer(monkeypatch, capsys):
+    _detected(monkeypatch, ("file:///dev/usb/lp1", "QL-1100"))
+    assert main(["labels"]) == 0
+    assert "102 " in capsys.readouterr().out
+
+
+def test_model_auto_without_printer_uses_the_last_model(monkeypatch, capsys):
+    _write_settings(last_model="QL-820NWB")
+    assert main(["labels"]) == 0
+    assert "62red" in capsys.readouterr().out
+
+
+def test_unknown_model_is_an_error(capsys):
+    assert main(["-m", "QL-9", "labels"]) == 2
+    assert "Unbekanntes Druckermodell 'QL-9'" in capsys.readouterr().err
+
+
+def test_printers_command_lists_printers_and_models(monkeypatch, capsys):
+    _detected(monkeypatch, ("file:///dev/usb/lp1", "QL-600"), ("file:///dev/usb/lp2", "QL-700"))
+    _write_settings(network_printers=[{"name": "Büro", "host": "10.0.0.5", "model": "QL-720NW"}])
+    assert main(["printers"]) == 0
+    out = capsys.readouterr().out
+    assert "file:///dev/usb/lp1" in out and "geprüft" in out
+    assert "QL-700" in out and "ungeprüft – Rückmeldung erwünscht" in out
+    assert "tcp://10.0.0.5:9100" in out
+    assert "Wirksames Modell: QL-600" in out and "QL-1100 (ungeprüft)" in out
+
+
+def test_label_auto_reads_the_loaded_roll(monkeypatch, tmp_path):
+    from labelwerk.media import Media
+    monkeypatch.setattr("labelwerk.cli.find_brother_lp", lambda: "file:///dev/usb/lp0")
+    monkeypatch.setattr("labelwerk.cli.read_media", lambda printer: Media(29, 0, "endless"))
+    out = tmp_path / "v.png"
+    assert main(["print", "Hallo", "-l", "auto", "--preview", str(out)]) == 0
+    assert Image.open(out).width == 306                       # 29 mm endlos
+
+
+@pytest.mark.parametrize("media, message", [(None, "nicht gefunden"),
+                                            ("none", "Keine Rolle eingelegt"),
+                                            ("odd", "Kein Etikett für die eingelegte Rolle")])
+def test_label_auto_errors(monkeypatch, capsys, media, message):
+    from labelwerk.media import Media
+    monkeypatch.setattr("labelwerk.cli.find_brother_lp",
+                        lambda: None if media is None else "file:///dev/usb/lp0")
+    monkeypatch.setattr("labelwerk.cli.brother_busy", lambda: False)
+    roll = Media(0, 0, "none") if media == "none" else Media(70, 0, "endless")
+    monkeypatch.setattr("labelwerk.cli.read_media", lambda printer: roll)
+    assert main(["print", "Hallo", "-l", "auto", "--preview", "x.png"]) == 2
+    assert message in capsys.readouterr().err
+
+
+def test_auto_printer_includes_network_printers(monkeypatch):
+    _write_settings(network_printers=[{"name": "Büro", "host": "10.0.0.5", "model": "QL-720NW"}])
+    sent = {}
+
+    def fake_print(img, label, **kw):
+        sent.update(kw)
+        return {"outcome": "sent", "did_print": True}
+    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
+    assert main(["print", "Hallo", "-l", "62"]) == 0
+    assert sent["printer"] == "tcp://10.0.0.5:9100" and sent["backend"] is None
+    assert sent["model"] == "QL-720NW"                        # Modell des Netzwerkdruckers
+
+
+def test_given_printer_decides_the_model(monkeypatch):
+    _detected(monkeypatch, ("file:///dev/usb/lp0", "QL-600"), ("file:///dev/usb/lp1", "QL-1100"))
+    sent = {}
+
+    def fake_print(img, label, **kw):
+        sent.update(kw, label=label, width=img.width)
+        return {"outcome": "printed", "did_print": True}
+    monkeypatch.setattr("labelwerk.cli.prn.print_image", fake_print)
+    assert main(["print", "Hallo", "-l", "102", "-p", "file:///dev/usb/lp1"]) == 0
+    assert (sent["model"], sent["label"], sent["width"]) == ("QL-1100", "102", 1164)
+    assert main(["print", "Hallo", "-l", "102", "-p", "usb://0x04f9:0x20a7"]) == 0
+    assert sent["model"] == "QL-1100"
+
+
+def test_label_that_does_not_fit_the_model_is_an_error(capsys):
+    assert main(["-m", "QL-600", "print", "Hallo", "-l", "62red", "--preview", "x.png"]) == 2
+    assert "Etikett '62red' passt nicht zum QL-600" in capsys.readouterr().err
+
+
+def test_label_auto_asks_the_chosen_printer(monkeypatch):
+    from labelwerk.media import Media
+    _detected(monkeypatch, ("file:///dev/usb/lp0", "QL-600"), ("file:///dev/usb/lp1", "QL-700"))
+    asked = []
+    monkeypatch.setattr("labelwerk.cli.read_media",
+                        lambda printer: asked.append(printer) or Media(62, 0, "endless"))
+    assert main(["print", "Hallo", "-l", "auto", "-p", "file:///dev/usb/lp1",
+                 "--preview", "x.png"]) == 0
+    assert asked == ["file:///dev/usb/lp1"]
+
+
+def test_label_auto_needs_usb(capsys):
+    assert main(["print", "Hallo", "-l", "auto", "-p", "tcp://10.0.0.5", "--preview", "x.png"]) == 2
+    assert "nur bei Druckern per USB" in capsys.readouterr().err
+
+
+def test_network_backend_without_entries_explains(capsys, monkeypatch):
+    assert main(["print", "Hallo", "-l", "62", "-b", "network"]) == 2
+    assert "Kein Netzwerkdrucker eingetragen" in capsys.readouterr().err
diff --git a/tests/test_golden.py b/tests/test_golden.py
new file mode 100644
index 0000000..547de6d
--- /dev/null
+++ b/tests/test_golden.py
@@ -0,0 +1,35 @@
+"""Referenztests je Druckermodell: Die Rasterdaten eines festen Testetiketts ändern sich nur
+gewollt (dann ``python tools/golden.py --update``). Beweist, was gesendet wird – nicht, was
+gedruckt wird."""
+import importlib.util
+import json
+from pathlib import Path
+
+import pytest
+
+from labelwerk.printers import SUPPORTED_MODELS
+
+ROOT = Path(__file__).resolve().parent.parent
+_spec = importlib.util.spec_from_file_location("golden", ROOT / "tools" / "golden.py")
+golden = importlib.util.module_from_spec(_spec)
+_spec.loader.exec_module(golden)
+STORED = json.loads((ROOT / "tests" / "golden" / "raster.json").read_text())
+
+
+def test_every_supported_model_has_references():
+    assert sorted(STORED) == sorted(SUPPORTED_MODELS)
+
+
+@pytest.mark.parametrize("model", SUPPORTED_MODELS)
+def test_raster_data_is_unchanged(model):
+    current = {name: golden.hashlib.sha256(data).hexdigest()
+               for name, data in golden.cases(model).items()}
+    assert current == STORED[model]
+
+
+def test_cases_cover_cut_width_and_red():
+    assert "62-ohne-schnitt" in STORED["QL-600"] and "102" not in STORED["QL-600"]
+    assert "102" in STORED["QL-1100"] and "62red" in STORED["QL-820NWB"]
+    # ohne Abschneider: mit und ohne Schnitt gleich
+    assert STORED["QL-500"]["62"] == STORED["QL-500"]["62-ohne-schnitt"]
+    assert STORED["QL-600"]["62"] != STORED["QL-600"]["62-ohne-schnitt"]
diff --git a/tests/test_printers.py b/tests/test_printers.py
new file mode 100644
index 0000000..a0b27e2
--- /dev/null
+++ b/tests/test_printers.py
@@ -0,0 +1,319 @@
+"""Drucker-Kompatibilität: Erkennung (sysfs), Fähigkeiten je Modell, Etiketten, Wahl, Netzwerk,
+Abschneider, Rot/Schwarz, Einstellungen."""
+import pytest
+from PIL import Image, ImageDraw
+
+from labelwerk import printers
+from labelwerk.document import Document, ImageObject, TextObject
+from labelwerk.labels import labels_for_model
+from labelwerk.printer import PrintError, build_instructions, print_image, to_print_mode
+from labelwerk.printers import (Capabilities, NetworkEntry, Printer, backend_for, capabilities,
+                                choose, effective_model, known_model, network_printers,
+                                usb_printers)
+from labelwerk.render import render_document
+from labelwerk.settings import load_settings, network_entries, save_settings, Settings
+
+
+def _fake_lp(sys_root, devices, name, vendor="04f9", product_id="", product="", ieee=""):
+    usb_dev = devices / f"usb-{name}"
+    iface = usb_dev / "1-1:1.0"
+    iface.mkdir(parents=True)
+    (usb_dev / "idVendor").write_text(vendor + "\n")
+    if product_id:
+        (usb_dev / "idProduct").write_text(product_id + "\n")
+    if product:
+        (usb_dev / "product").write_text(product + "\n")
+    if ieee:
+        (iface / "ieee1284_id").write_text(ieee)
+    (sys_root / name).mkdir(parents=True)
+    (sys_root / name / "device").symlink_to(iface)
+
+
+# --- Erkennung -------------------------------------------------------------------------------
+def test_model_from_the_ieee1284_id_first(tmp_path):
+    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
+    _fake_lp(sys_root, devices, "lp1", product_id="2042", product="QL-700",
+             ieee="MFG:Brother;CMD:PT-CBP;MDL:QL-600;CLS:PRINTER;")
+    assert usb_printers(sys_root) == [Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")]
+
+
+def test_model_from_the_product_name_then_the_product_id(tmp_path):
+    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
+    _fake_lp(sys_root, devices, "lp0", product_id="2042", product="QL-720NW")
+    _fake_lp(sys_root, devices, "lp1", product_id="2042")
+    _fake_lp(sys_root, devices, "lp2", product_id="ffff")
+    _fake_lp(sys_root, devices, "lp3", vendor="03f0", product="LaserJet")   # anderer Hersteller
+    found = usb_printers(sys_root)
+    assert [(p.uri, p.model, p.name) for p in found] == [
+        ("file:///dev/usb/lp0", "QL-720NW", "QL-720NW · lp0"),
+        ("file:///dev/usb/lp1", "QL-700", "QL-700 · lp1"),
+        ("file:///dev/usb/lp2", None, "Brother-Drucker · lp2")]
+
+
+def test_no_printers_without_sysfs(tmp_path):
+    assert usb_printers(tmp_path / "fehlt") == []
+
+
+def test_default_sysfs_is_isolated_in_tests():
+    assert usb_printers() == []
+
+
+@pytest.mark.parametrize("name, model", [
+    ("QL-600", "QL-600"), ("QL-600G", "QL-600"), ("Brother QL-820NWB", "QL-820NWB"),
+    ("ql-1110nwb", "QL-1110NWB"), ("QL-1100", "QL-1100"), ("PT-P700", None), ("", None),
+    (None, None), ("QL-9999", None)])
+def test_known_model(name, model):
+    assert known_model(name) == model
+
+
+# --- Fähigkeiten und Etiketten -------------------------------------------------------------------
+def test_capabilities_from_brother_ql():
+    assert capabilities("QL-600") == Capabilities("QL-600", True, False, 62, (150, 11811), True)
+    assert not capabilities("QL-500").cutter
+    assert capabilities("QL-820NWB").two_color and not capabilities("QL-820NWB").tested
+    assert capabilities("QL-1100").max_tape_mm == 104
+    with pytest.raises(ValueError, match="Unbekanntes Druckermodell"):
+        capabilities("PT-P700")
+
+
+def test_supported_models_are_the_ql_series():
+    assert "QL-600" in printers.SUPPORTED_MODELS and "QL-1115NWB" in printers.SUPPORTED_MODELS
+    assert not any(m.startswith("PT") for m in printers.SUPPORTED_MODELS)
+
+
+def _ids(model):
+    return {label.id for label in labels_for_model(model)}
+
+
+def test_labels_follow_the_model():
+    assert "62red" not in _ids("QL-600") and "102" not in _ids("QL-600")
+    assert "62red" in _ids("QL-820NWB")
+    assert {"102", "103", "104", "102x51", "62"} <= _ids("QL-1100")
+    assert "102" in _ids("QL-1050") and "103" not in _ids("QL-1050")
+    assert not any(i.startswith("pt") for i in _ids("QL-1100"))
+    with pytest.raises(ValueError, match="Unbekanntes Druckermodell"):
+        labels_for_model("PT-P700")
+
+
+# --- Wahl und Modell ----------------------------------------------------------------------------
+USB = Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")
+NET = Printer("tcp://10.0.0.5:9100", "QL-720NW", "Büro · Netzwerk", "network")
+
+
+def test_choose_the_wanted_printer_else_the_first_usb():
+    assert choose([NET, USB]) == USB
+    assert choose([NET, USB], NET.uri) == NET
+    assert choose([NET, USB], "file:///dev/usb/lp9") == USB         # nicht mehr da
+    assert choose([NET]) == NET and choose([]) is None
+
+
+def test_effective_model():
+    assert effective_model(USB, "QL-700", "QL-800") == "QL-600"
+    unknown = Printer("file:///dev/usb/lp0", None, "Brother-Drucker · lp0")
+    assert effective_model(unknown, "QL-700", "QL-800") == "QL-700"
+    assert effective_model(None, "", "QL-800") == "QL-800"
+    assert effective_model(None) == "QL-600"
+    assert effective_model(None, "PT-P700", "kaputt") == "QL-600"
+
+
+def test_network_printers_and_backends():
+    assert network_printers([NetworkEntry("Büro", "10.0.0.5", "QL-720NW")]) == [NET]
+    assert network_printers([NetworkEntry("", "drucker.lan", "QL-710W")])[0].name == \
+        "drucker.lan · Netzwerk"
+    assert backend_for("tcp://10.0.0.5:9100") == "network"
+    assert backend_for("usb://0x04f9:0x20c0") == "pyusb"
+    assert backend_for("file:///dev/usb/lp1") == "linux_kernel"
+
+
+# --- Drucken ------------------------------------------------------------------------------------
+def _image(red=False):
+    img = Image.new("RGB", (696, 120), "white")
+    ImageDraw.Draw(img).rectangle((10, 10, 100, 100), fill=(255, 0, 0) if red else (0, 0, 0))
+    return img
+
+
+def test_without_cutter_nothing_is_cut():
+    assert build_instructions(_image(), "62", "QL-500", cut=True) == \
+        build_instructions(_image(), "62", "QL-500", cut=False)
+    assert build_instructions(_image(), "62", "QL-600", cut=True) != \
+        build_instructions(_image(), "62", "QL-600", cut=False)
+
+
+def _plane_ink(data: bytes, plane: int) -> int:
+    """Gesetzte Bytes in den Rasterzeilen einer Ebene (w 01 schwarz, w 02 rot)."""
+    marker, total, start = b"w" + bytes([plane]), 0, 0
+    while (i := data.find(marker, start)) >= 0:
+        size = data[i + 2]
+        total += sum(1 for b in data[i + 3:i + 3 + size] if b)
+        start = i + 3 + size
+    return total
+
+
+def test_red_labels_get_a_red_plane():
+    red = build_instructions(_image(red=True), "62red", "QL-820NWB")
+    black = build_instructions(_image(), "62red", "QL-820NWB")
+    assert _plane_ink(red, 2) > 0 and _plane_ink(red, 1) == 0
+    assert _plane_ink(black, 1) > 0 and _plane_ink(black, 2) == 0
+
+
+def test_print_mode_keeps_red():
+    img = _image(red=True)
+    assert to_print_mode(img, red=True).getpixel((50, 50)) == (255, 0, 0)
+    assert to_print_mode(img).mode == "1"
+
+
+class _Socket:
+    def close(self):
+        pass
+
+
+def test_network_printer_uses_the_network_backend(monkeypatch):
+    seen = {}
+    monkeypatch.setattr("labelwerk.printer.socket.create_connection",
+                        lambda address, timeout: seen.update(probe=(address, timeout)) or _Socket())
+
+    def send(instructions, printer_identifier, backend_identifier, blocking):
+        seen.update(printer=printer_identifier, backend=backend_identifier)
+        return {"outcome": "sent", "did_print": False}
+    monkeypatch.setattr("labelwerk.printer.send", send)
+    print_image(_image(), "62", model="QL-720NW", printer="tcp://10.0.0.5:9100")
+    assert seen == {"printer": "tcp://10.0.0.5:9100", "backend": "network",
+                    "probe": (("10.0.0.5", 9100), 5)}
+
+
+@pytest.mark.parametrize("error, reason", [
+    (ConnectionRefusedError(111, "Connection refused"), "Connection refused"),
+    (TimeoutError("timed out"), "keine Antwort")])
+def test_unreachable_network_printer_is_a_print_error(monkeypatch, error, reason):
+    def connect(address, timeout):
+        raise error
+    monkeypatch.setattr("labelwerk.printer.socket.create_connection", connect)
+    with pytest.raises(PrintError, match=rf"Netzwerkdrucker tcp://10.0.0.5:9100 nicht erreichbar "
+                                         rf"\({reason}\)"):
+        print_image(_image(), "62", model="QL-720NW", printer="tcp://10.0.0.5:9100")
+
+
+# --- Farbe --------------------------------------------------------------------------------------
+def test_red_objects_print_red_only_on_red_labels():
+    obj = TextObject.plain("Achtung", size_pt=20)
+    obj.color = "red"
+    img = render_document(Document("62red", objects=[obj]), "QL-820NWB")
+    colors = {c for _, c in img.getcolors(1 << 20)}
+    assert (255, 0, 0) in colors and (0, 0, 0) not in colors
+    plain = render_document(Document("62", objects=[obj]), "QL-820NWB")
+    assert (255, 0, 0) not in {c for _, c in plain.getcolors(1 << 20)}     # Vorschau = Druck
+    single = render_document(Document("62red", objects=[obj]), "QL-600")  # Modell ohne Rot
+    assert (255, 0, 0) not in {c for _, c in single.getcolors(1 << 20)}
+
+
+def test_images_and_barcodes_can_be_red():
+    from labelwerk.document import BarcodeObject
+    image = ImageObject.from_image(Image.new("RGB", (60, 60), "black"), 300, "x")
+    image.color = "red"
+    code = BarcodeObject(kind="qr", data="x", x_mm=20, color="red")
+    img = render_document(Document("62red", objects=[image, code]), "QL-820NWB")
+    assert img.getpixel((10, 10)) == (255, 0, 0)
+    assert img.getpixel((round(20 * 300 / 25.4) + 2, 2)) == (255, 0, 0)
+
+
+def test_unknown_color_is_a_render_error():
+    obj = TextObject("A")
+    obj.color = "blau"
+    with pytest.raises(ValueError, match="Unbekannte Farbe"):
+        render_document(Document("62", objects=[obj]))
+
+
+def test_color_is_saved():
+    from labelwerk import storage
+    obj = TextObject("A")
+    obj.color = "red"
+    data = storage.to_dict(Document("62red", objects=[obj]))
+    assert storage.from_dict(data).objects[0].color == "red"
+    data["document"]["objects"][0]["color"] = "blau"
+    with pytest.raises(storage.StorageError, match="„color“"):
+        storage.from_dict(data)
+
+
+# --- Einstellungen ------------------------------------------------------------------------------
+def test_printer_settings_round_trip(tmp_path):
+    path = tmp_path / "s.json"
+    settings = Settings(printer="tcp://10.0.0.5:9100", printer_model="",
+                        last_model="QL-1100", label_id="102",
+                        network_printers=[{"name": "Büro", "host": "10.0.0.5",
+                                           "model": "QL-720NW"}])
+    save_settings(settings, path)
+    loaded = load_settings(path)                    # Etikett 102 gilt für das letzte Modell
+    assert (loaded.printer, loaded.printer_model, loaded.last_model, loaded.label_id) == (
+        "tcp://10.0.0.5:9100", "", "QL-1100", "102")
+    assert network_entries(loaded) == [NetworkEntry("Büro", "10.0.0.5", "QL-720NW")]
+    assert loaded.warnings == []
+
+
+def test_invalid_printer_settings_fall_back(tmp_path):
+    path = tmp_path / "s.json"
+    path.write_text('{"printer": "ftp://x", "printer_model": "PT-P700", "last_model": 5, '
+                    '"network_printers": [{"name": "ok", "host": "10.0.0.5", "model": "QL-710W"},'
+                    ' {"host": "a b", "model": "QL-710W"}, {"host": "tcp://x", "model": "QL-710W"},'
+                    ' {"host": "x", "model": "PT-P700"}, "kaputt"]}')
+    loaded = load_settings(path)
+    assert (loaded.printer, loaded.printer_model, loaded.last_model) == ("", "", "")
+    assert loaded.network_printers == [{"name": "ok", "host": "10.0.0.5", "model": "QL-710W"}]
+    assert len(loaded.warnings) == 4
+
+
+def test_fallback_model_comes_before_the_last_one(tmp_path):
+    path = tmp_path / "s.json"
+    save_settings(Settings(printer_model="QL-700", last_model="QL-1100", label_id="102"), path)
+    loaded = load_settings(path)                    # 102 kann der QL-700 nicht
+    assert loaded.label_id == "62" and loaded.warnings
+
+
+# --- Nachbesserungen nach dem Review --------------------------------------------------------------
+def test_choose_prefers_a_recognised_model():
+    laser = Printer("file:///dev/usb/lp0", None, "Brother-Drucker · lp0")
+    assert choose([laser, USB]) == USB
+    assert choose([laser]) == laser
+
+
+def test_printer_for_a_given_uri():
+    from labelwerk.printers import printer_for
+    assert printer_for(USB.uri, [NET, USB]) is USB
+    assert printer_for("usb://0x04f9:0x20a7/ABC", []).model == "QL-1100"
+    assert printer_for("usb://0x04f9:0x9999", []).model is None
+    assert printer_for("tcp://1.2.3.4:9100", []).source == "network"
+
+
+def test_label_must_fit_the_model():
+    with pytest.raises(ValueError, match="Etikett '62red' passt nicht zum QL-600"):
+        build_instructions(_image(red=True), "62red", "QL-600")
+    with pytest.raises(PrintError, match="passt nicht zum Drucker"):
+        print_image(_image(), "102", model="QL-600")
+
+
+def test_red_labels_use_the_same_threshold_as_black_and_white():
+    """Antialiasing-Graustufen werden auf 62red genauso schwarz wie auf 62 (Vorschau = Druck)."""
+    text = TextObject.plain("Grauer Rand 8 pt", size_pt=8)
+    plain = to_print_mode(render_document(Document("62", objects=[text]), "QL-820NWB"))
+    red = to_print_mode(render_document(Document("62red", objects=[text]), "QL-820NWB"), red=True)
+    assert plain.histogram()[0] == sum(1 for c in red.getdata() if c == (0, 0, 0))
+    from labelwerk.printer import pure_colors
+    edge = Image.new("RGB", (5, 1))
+    for x, color in enumerate([(179, 179, 179), (180, 180, 180), (255, 179, 179),
+                               (255, 180, 180), (100, 20, 20)]):
+        edge.putpixel((x, 0), color)
+    assert list(pure_colors(edge).getdata()) == [(0, 0, 0), (255, 255, 255), (255, 0, 0),
+                                                 (255, 255, 255), (0, 0, 0)]
+
+
+def test_busy_usb_device_is_a_print_error(monkeypatch):
+    def send(**kw):
+        raise OSError(16, "Device or resource busy")
+    monkeypatch.setattr("labelwerk.printer.send", send)
+    with pytest.raises(PrintError, match=r"nicht bereit \(Device or resource busy\)"):
+        print_image(_image(), "62", printer="file:///dev/usb/lp0")
+
+
+def test_host_without_control_characters():
+    from labelwerk.settings import valid_host
+    assert valid_host("drucker.lan") and valid_host(" 10.0.0.5 ")
+    assert not any(valid_host(h) for h in ("a\x00b", "fe80::1", "tcp://x", "a b", "", "x/y"))
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_printers.py, tests/test_golden.py, neue Fälle in tests/test_cli.py) schlagen fehl (ImportError `labelwerk.printers`, fehlende Datei `tools/golden.py`), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/pyproject.toml b/pyproject.toml
index 982e24a..1956d67 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -12,7 +12,9 @@ license = "GPL-3.0-or-later AND MIT AND CC0-1.0"
 license-files = ["LICEN[CS]E*", "src/labelwerk/clipart_data/LICENSES.md"]
 requires-python = ">=3.10"
 dependencies = [
-    "brother_ql-inventree>=1.3,<2",   # printer._Raster nutzt Interna (add_cut_every, page_number)
+    # printer._Raster nutzt Interna (add_cut_every, page_number); Referenztests (tests/golden) hashen
+    # die Rasterdaten – neue Version erst nach tools/golden.py prüfen
+    "brother_ql-inventree>=1.3,<1.4",
     "pillow>=10.1",
     "pypdfium2>=4",
     "openpyxl>=3.1",      # Excel-Tabellen für Serien (MIT)
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index a98e013..f9b99ae 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -1,4 +1,5 @@
-"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | fonts | install-desktop"""
+"""Kommandozeile: labelwerk labels | print "Text" | print-file datei.pdf | media | printers | fonts |
+install-desktop"""
 from __future__ import annotations
 
 import argparse
@@ -9,14 +10,15 @@ from PIL import Image
 
 from . import desktop
 from . import printer as prn
+from . import printers
 from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
 from .files import crop, fit_to_label, load_file
 from .fonts import DEFAULT_FAMILY, families
 from .document import ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
-from .labels import format_mm, labels_for_model
+from .labels import format_mm, get_label, labels_for_model
 from .media import MediaError, label_for_media, read_media
 from .render import font_warnings, render_document
-from .settings import load_settings
+from .settings import load_settings, network_entries
 from .storage import os_reason
 
 
@@ -44,11 +46,12 @@ def _margin(value: str) -> float:
 
 
 def _add_output_options(p: argparse.ArgumentParser) -> None:
-    p.add_argument("-l", "--label", help="Etikett, z. B. 62 (Standard aus den Einstellungen)")
+    p.add_argument("-l", "--label", help="Etikett, z. B. 62, oder auto (eingelegte Rolle vom "
+                                         "Drucker); Standard aus den Einstellungen")
     p.add_argument("-p", "--printer", default="auto",
                    help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP")
-    p.add_argument("-b", "--backend", default=prn.DEFAULT_BACKEND,
-                   choices=["linux_kernel", "pyusb", "network"])
+    p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network"],
+                   help="Standard: aus dem Drucker (tcp:// → network)")
     p.add_argument("--no-cut", action="store_true")
     p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")
 
@@ -58,7 +61,9 @@ _UNSET = object()   # -s nicht angegeben (None bedeutet „auto“)
 
 def _parser() -> argparse.ArgumentParser:
     p = argparse.ArgumentParser(prog=desktop.APP_NAME)
-    p.add_argument("-m", "--model", default=prn.DEFAULT_MODEL)
+    p.add_argument("-m", "--model", default="auto",
+                   help="auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700; "
+                        "siehe 'labelwerk printers'")
     sub = p.add_subparsers(dest="cmd", required=True)
 
     sub.add_parser("labels", help="Etiketten für das Modell auflisten")
@@ -92,6 +97,7 @@ def _parser() -> argparse.ArgumentParser:
     _add_output_options(pf)
 
     sub.add_parser("media", help="eingelegte Rolle vom Drucker abfragen (druckt nichts)")
+    sub.add_parser("printers", help="gefundene Drucker und unterstützte Modelle auflisten")
     sub.add_parser("fonts", help="installierte Schriftfamilien auflisten")
 
     di = sub.add_parser("install-desktop", help="labelwerk-gui im Starter (Super-Taste) eintragen")
@@ -105,17 +111,61 @@ _NOT_DETECTED = {
     "pyusb": "Brother-Drucker per USB (pyusb) nicht gefunden.\n"
              f"{_HARDWARE_HINT}, Zugriff auf den USB-Bus (udev-Regel).\n"
              "Manuell angeben mit -p usb://0x04f9:0xPID",
-    "network": "Netzwerkdrucker werden nicht automatisch erkannt.\n"
+    "network": "Kein Netzwerkdrucker eingetragen (Einstellungen der GUI).\n"
                "Adresse angeben mit -p tcp://IP",
 }
 
 
-def _detect_printer(backend: str) -> str | None:
-    if backend == "linux_kernel":
-        return find_brother_lp()
-    if backend == "pyusb":
-        return find_brother_usb()
-    return None
+def _target(args: argparse.Namespace, settings) -> printers.Printer | None:
+    """Drucker, auf den sich der Befehl bezieht: ``-p`` (gefunden oder aus der URI beschrieben),
+    bei ``-p auto`` per pyusb bzw. der gewählte/erste aus sysfs und den eingetragenen
+    Netzwerkdruckern (``-b`` grenzt ein); None = keiner."""
+    wanted = getattr(args, "printer", "auto")
+    backend = getattr(args, "backend", None)
+    if backend == "pyusb" and wanted == "auto":
+        uri = find_brother_usb()
+        return printers.printer_for(uri, []) if uri else None
+    found = _all_printers(settings)
+    if wanted != "auto":
+        return printers.printer_for(wanted, found)
+    if backend == "network":
+        found = [p for p in found if p.source == "network"]
+    elif backend == "linux_kernel":
+        found = [p for p in found if p.source == "usb"]
+    return printers.choose(found, settings.printer)
+
+
+def _all_printers(settings) -> list[printers.Printer]:
+    return printers.usb_printers() + printers.network_printers(network_entries(settings))
+
+
+def _resolve_model(model: str, target: printers.Printer | None, settings) -> str:
+    """``-m auto``: Modell des Zieldruckers, sonst Ersatzmodell bzw. zuletzt erkanntes aus den
+    Einstellungen; ein angegebenes muss bekannt sein."""
+    if model != "auto":
+        if model not in printers.SUPPORTED_MODELS:
+            raise ValueError(f"Unbekanntes Druckermodell {model!r} – erlaubt: "
+                             f"{', '.join(printers.SUPPORTED_MODELS)}")
+        return model
+    return printers.effective_model(target, settings.printer_model, settings.last_model)
+
+
+def _auto_label(model: str, target: printers.Printer | None) -> str:
+    """``-l auto``: Etikett zur eingelegten Rolle (Statusabfrage per USB beim Zieldrucker) – sonst
+    ValueError."""
+    if target is not None and target.source != "usb":
+        raise ValueError("-l auto (Rolle abfragen) geht nur bei Druckern per USB.")
+    printer = target.uri if target is not None and target.uri.startswith("file://") \
+        else find_brother_lp()
+    if printer is None:
+        raise ValueError(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
+    media = read_media(printer)
+    if media.kind == "none":
+        raise ValueError("Keine Rolle eingelegt.")
+    label = label_for_media(media, model)
+    if label is None:
+        raise ValueError(f"Kein Etikett für die eingelegte Rolle ({media.describe()}) beim {model}.")
+    return label
 
 
 def _make_image(args: argparse.Namespace) -> Image.Image:
@@ -135,10 +185,11 @@ def _make_image(args: argparse.Namespace) -> Image.Image:
 
 def _send(img: Image.Image, args: argparse.Namespace) -> int:
     if args.printer == "auto":
-        args.printer = _detect_printer(args.backend)
+        args.printer = args.target.uri if args.target is not None else None
         if args.printer is None:
-            busy = args.backend == "linux_kernel" and brother_busy()
-            print(BUSY_MESSAGE if busy else _NOT_DETECTED[args.backend], file=sys.stderr)
+            busy = args.backend in (None, "linux_kernel") and brother_busy()
+            print(BUSY_MESSAGE if busy else _NOT_DETECTED[args.backend or "linux_kernel"],
+                  file=sys.stderr)
             return 2
 
     try:
@@ -152,7 +203,24 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
     return 0 if ok else 1
 
 
-def _show_media() -> int:
+def _show_printers(model: str) -> int:
+    """Gefundene Drucker (USB, eingetragene Netzwerkdrucker) und unterstützte Modelle."""
+    found = _all_printers(load_settings())
+    for p in found:
+        caps = printers.capabilities(p.model) if p.model else None
+        state = ("Modell nicht erkannt" if caps is None else
+                 "geprüft" if caps.tested else printers.UNTESTED_HINT)
+        print(f"{p.name:<28} {p.uri:<30} {state}")
+    if not found:
+        print("Kein Drucker gefunden.")
+    print(f"Wirksames Modell: {model}")
+    print("Unterstützt: " + ", ".join(
+        f"{m}{'' if printers.capabilities(m).tested else ' (ungeprüft)'}"
+        for m in printers.SUPPORTED_MODELS))
+    return 0
+
+
+def _show_media(model: str) -> int:
     printer = find_brother_lp()
     if printer is None:
         print(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND, file=sys.stderr)
@@ -162,7 +230,7 @@ def _show_media() -> int:
     except MediaError as e:
         print(e, file=sys.stderr)
         return 2
-    label = label_for_media(media)
+    label = label_for_media(media, model)
     hint = f" (Etikett {label})" if label else " (kein passendes Etikett)" if media.kind != "none" else ""
     print(f"Eingelegt: {media.describe()}{hint}")
     return 0
@@ -175,6 +243,12 @@ def _apply_settings(args: argparse.Namespace) -> None:
         print(warning, file=sys.stderr)
     if hasattr(args, "label") and args.label is None:
         args.label = settings.label_id
+    if getattr(args, "label", None) == "auto":
+        args.label = _auto_label(args.model, args.target)
+    if hasattr(args, "label") and get_label(args.label).id not in {   # unbekannt: ValueError
+            label.id for label in labels_for_model(args.model)}:
+        raise ValueError(f"Etikett {args.label!r} passt nicht zum {args.model} – siehe "
+                         f"'labelwerk -m {args.model} labels'")
     if args.cmd == "print":
         args.orientation = args.orientation or settings.orientation
         args.margin = settings.margin_mm if args.margin is None else args.margin
@@ -221,6 +295,13 @@ def _report_update(failed: list[str]) -> None:
 
 def main(argv: list[str] | None = None) -> int:
     args = _parser().parse_args(argv)
+    settings = load_settings()
+    args.target = _target(args, settings)
+    try:
+        args.model = _resolve_model(args.model, args.target, settings)
+    except ValueError as e:
+        print(e, file=sys.stderr)
+        return 2
 
     if args.cmd == "labels":
         for lbl in labels_for_model(args.model):
@@ -231,7 +312,9 @@ def main(argv: list[str] | None = None) -> int:
     if args.cmd == "install-desktop":
         return _install_desktop(args.remove)
     if args.cmd == "media":
-        return _show_media()
+        return _show_media(args.model)
+    if args.cmd == "printers":
+        return _show_printers(args.model)
     if args.cmd == "fonts":
         print("\n".join(families()))
         return 0
@@ -239,7 +322,11 @@ def main(argv: list[str] | None = None) -> int:
     if args.cmd == "print" and args.font and args.font_family:
         print("--font (Schriftdatei) und --font-family schließen sich aus.", file=sys.stderr)
         return 2
-    _apply_settings(args)
+    try:
+        _apply_settings(args)
+    except (ValueError, MediaError) as e:            # -l auto: kein Drucker, keine Rolle
+        print(e, file=sys.stderr)
+        return 2
 
     try:
         img = _make_image(args)
diff --git a/src/labelwerk/document.py b/src/labelwerk/document.py
index 33761ba..442be7a 100644
--- a/src/labelwerk/document.py
+++ b/src/labelwerk/document.py
@@ -11,6 +11,7 @@ from .imaging import MAX_DPI, limit_size, on_white
 ORIENTATIONS = ("vertical", "horizontal")
 ALIGNMENTS = ("left", "center", "right", "justify")
 ROTATIONS = (0, 90, 180, 270)      # Grad im Uhrzeigersinn
+COLORS = ("black", "red")          # Farbe je Objekt; Rot nur auf Etiketten Rot/Schwarz (62red)
 MAX_MARGIN_MM = 20.0
 MAX_POSITION_MM = 999.9            # Lage eines Objekts (Positionsfelder der GUI, auch neben dem Etikett)
 MIN_PT, MAX_PT = 4.0, 100.0
@@ -67,6 +68,7 @@ class TextObject:
                                     # (Endlosband, automatische Länge: längs = Textlänge)
     h_mm: float | None = None
     rotation: int = 0               # 0 | 90 | 180 | 270
+    color: str = "black"            # COLORS
 
     @property
     def positioned(self) -> bool:
@@ -123,6 +125,7 @@ class ImageObject:
     dpi: float = 300.0              # Auflösung von ``png`` – ergibt die Größe 1:1 (``natural_mm``)
     svg: bytes | None = field(default=None, repr=False)   # Vektorbild: beim Rendern in Rahmengröße
                                     # gerastert (``render.set_svg_rasterizer``); ``png`` ist Vorschau
+    color: str = "black"            # COLORS
 
     def __post_init__(self) -> None:
         if self.crop is not None:                # JSON liefert eine Liste
@@ -205,6 +208,7 @@ class BarcodeObject:
     rotation: int = 0               # 0 | 90 | 180 | 270
     text: bool = True               # Klartext unter dem Strichcode
     error: str = "M"                # QR-Fehlerkorrektur QR_LEVELS
+    color: str = "black"            # COLORS
 
     @property
     def positioned(self) -> bool:
diff --git a/src/labelwerk/labels.py b/src/labelwerk/labels.py
index a31fa9c..cc50d88 100644
--- a/src/labelwerk/labels.py
+++ b/src/labelwerk/labels.py
@@ -4,11 +4,8 @@ from __future__ import annotations
 from dataclasses import dataclass
 
 from brother_ql.labels import Color, FormFactor, LabelsManager
-from brother_ql.models import ModelsManager
 
-# Maximale Bandbreite in mm je Modell (QL-5xx/6xx/7xx/8xx: 62 mm)
-MAX_TAPE_MM = {"QL-600": 62}
-TWO_COLOR_MODELS = {"QL-800", "QL-810W", "QL-820NWB"}
+from .printers import capabilities
 
 DPI = 300  # Druckauflösung der QL-Drucker
 
@@ -24,6 +21,7 @@ class Label:
     size_mm: tuple[int, int]  # Nenngröße laut Etikett, z. B. (62, 29); Endlos: (62, 0)
     total_width: int        # physische Breite in Punkten (bedruckbarer Bereich liegt mittig)
     total_height: int | None  # physische Höhe in Punkten; None = Endlosband
+    two_color: bool = False   # Rot/Schwarz (DK-22251, „62red“)
 
 
 def _convert(raw) -> Label:
@@ -37,7 +35,8 @@ def _convert(raw) -> Label:
         desc, shape = f"{raw.tape_size[0]} x {raw.tape_size[1]} mm gestanzt", "die_cut"
     total_w, total_h = raw.dots_total
     return Label(raw.identifier, w, None if endless else h, raw.tape_size[0], desc,
-                 shape, tuple(raw.tape_size), total_w, None if endless else total_h)
+                 shape, tuple(raw.tape_size), total_w, None if endless else total_h,
+                 raw.color == Color.BLACK_RED_WHITE)
 
 
 def _all_raw():
@@ -52,16 +51,16 @@ def get_label(label_id: str) -> Label:
 
 
 def labels_for_model(model: str) -> list[Label]:
-    max_mm = MAX_TAPE_MM.get(model)
+    """Etiketten, die ``model`` drucken kann (``printers.capabilities``): bis zu seiner Breite,
+    ohne P-touch-Bänder, Rot/Schwarz nur bei Zweifarb-Modellen; unbekanntes Modell → ValueError."""
+    caps = capabilities(model)
     result = []
     for raw in _all_raw():
         if raw.restricted_to_models and model not in raw.restricted_to_models:
             continue
-        if max_mm is not None and raw.tape_size[0] > max_mm:
+        if raw.tape_size[0] > caps.max_tape_mm or raw.form_factor == FormFactor.PTOUCH_ENDLESS:
             continue
-        if model.startswith("QL") and raw.form_factor == FormFactor.PTOUCH_ENDLESS:
-            continue
-        if raw.color == Color.BLACK_RED_WHITE and model not in TWO_COLOR_MODELS:
+        if raw.color == Color.BLACK_RED_WHITE and not caps.two_color:
             continue
         result.append(_convert(raw))
     return result
@@ -74,7 +73,4 @@ def format_mm(dots: int) -> str:
 
 def length_limits(model: str) -> tuple[int, int]:
     """Erlaubte Etikettlänge (Endlosband) in Punkten, z. B. (150, 11811) für den QL-600."""
-    for m in ModelsManager().iter_elements():
-        if m.identifier == model:
-            return m.min_max_length_dots
-    raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
+    return capabilities(model).length_limits
diff --git a/src/labelwerk/printer.py b/src/labelwerk/printer.py
index c0f0c72..3f4acf5 100644
--- a/src/labelwerk/printer.py
+++ b/src/labelwerk/printer.py
@@ -1,6 +1,7 @@
 """Erzeugt Brother-Rasterdaten und sendet sie an den Drucker."""
 from __future__ import annotations
 
+import socket
 from collections.abc import Callable
 
 from brother_ql.backends.helpers import send
@@ -9,8 +10,9 @@ from brother_ql.raster import BrotherQLRaster
 from PIL import Image
 
 from .document import CUTS
+from .labels import get_label, labels_for_model
+from .printers import DEFAULT_MODEL, backend_for, capabilities
 
-DEFAULT_MODEL = "QL-600"
 DEFAULT_BACKEND = "linux_kernel"
 DEFAULT_PRINTER = "file:///dev/usb/lp0"
 
@@ -48,13 +50,34 @@ MAX_CUT_EVERY = 255         # Brother ESC i A n: höchstens alle 255 Etiketten
 # den Teilen lässt sich abbrechen – kleine Teile, damit das schnell wirkt.
 MAX_JOB_EACH = 10
 THRESHOLD = 70.0            # brother_ql: ein Punkt druckt ab (100 − THRESHOLD) % Schwarz
+CONNECT_TIMEOUT_S = 5       # Netzwerkdrucker: so lange auf die Verbindung warten
 
 
-def to_print_mode(image: Image.Image) -> Image.Image:
+_LEVEL = min(255, max(0, int((100.0 - THRESHOLD) / 100.0 * 255)))   # wie brother_ql.convert
+
+
+def to_print_mode(image: Image.Image, red: bool = False) -> Image.Image:
     """Druckbild als 1-Bit-Bild mit derselben Schwelle wie brother_ql – druckt bitgleich, braucht
-    aber nur ein Vierundzwanzigstel des Speichers von RGB (Serien mit vielen Etiketten)."""
-    level = min(255, max(0, int((100.0 - THRESHOLD) / 100.0 * 255)))   # wie brother_ql.convert
-    return image.convert("L").point(lambda v: 0 if 255 - v >= level else 255, mode="1")
+    aber nur ein Vierundzwanzigstel des Speichers von RGB (Serien mit vielen Etiketten).
+    ``red`` (Etikett Rot/Schwarz): reines Schwarz, Rot, Weiß (``pure_colors``) – 1 Bit verlöre
+    das Rot."""
+    if red:
+        return pure_colors(image)
+    return image.convert("L").point(lambda v: 0 if 255 - v >= _LEVEL else 255, mode="1")
+
+
+def pure_colors(image: Image.Image) -> Image.Image:
+    """Druckbild Rot/Schwarz auf reine Farben gebracht – mit derselben Schwelle wie ein
+    Schwarz-Weiß-Etikett (brother_ql nähme sonst nur sehr dunkle Punkte als Schwarz, Text würde
+    dünner als in der Vorschau). Schwarze Tinte senkt alle Kanäle, rote nur Grün und Blau:
+    Schwarz, wo Rot dunkel genug ist; Rot, wo sonst Grün dunkel genug ist."""
+    r, g, _ = image.convert("RGB").split()
+    black = r.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
+    red = g.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
+    out = Image.new("RGB", image.size, "white")
+    out.paste((255, 0, 0), (0, 0), red)
+    out.paste((0, 0, 0), (0, 0), black)
+    return out
 
 
 def cut_interval(mode: str, count: int) -> int:
@@ -88,27 +111,32 @@ def build_instructions(
     cut: bool = True, cut_every: int = 1,
 ) -> bytes:
     """Rasterdaten für ein Etikett oder mehrere in einem Auftrag (Serie); ``cut``: überhaupt
-    schneiden, ``cut_every``: alle n Etiketten (``cut_interval``) und am Ende."""
+    schneiden (ohne Abschneider des Modells nie), ``cut_every``: alle n Etiketten
+    (``cut_interval``) und am Ende. Etiketten Rot/Schwarz (62red) mit Rot-Ebene."""
     images = [images] if isinstance(images, Image.Image) else list(images)
     if not images:
         raise ValueError("Keine Etiketten zum Drucken")
     if not isinstance(cut_every, int) or isinstance(cut_every, bool) or cut_every < 1:
         raise ValueError(f"Schneiden alle n Etiketten: n muss eine ganze Zahl ab 1 sein, "
                          f"nicht {cut_every!r}")
+    if label_id not in {label.id for label in labels_for_model(model)}:
+        raise ValueError(f"Etikett {label_id!r} passt nicht zum {model} – siehe "
+                         f"'labelwerk -m {model} labels'")
     qlr = _Raster(model, cut_every)
     qlr.exception_on_warning = True
+    red = get_label(label_id).two_color          # nur Zweifarb-Modelle haben 62red (oben geprüft)
     return bytes(convert(
         qlr=qlr,
-        images=images,
+        images=[pure_colors(img) for img in images] if red else images,
         label=label_id,
         rotate="0",
         threshold=THRESHOLD,
         dither=False,
         compress=False,
-        red=False,
+        red=red,
         dpi_600=False,
         hq=True,
-        cut=cut,
+        cut=cut and capabilities(model).cutter,
     ))
 
 
@@ -117,7 +145,7 @@ def print_image(
     label_id: str,
     model: str = DEFAULT_MODEL,
     printer: str = DEFAULT_PRINTER,
-    backend: str = DEFAULT_BACKEND,
+    backend: str | None = None,
     cut: bool = True,
     cut_every: int = 1,
     cancelled: Callable[[], bool] | None = None,
@@ -128,8 +156,14 @@ def print_image(
     Eine Serie geht in Teilaufträgen hinaus (``MAX_JOB_EACH`` bzw. ``cut_every`` Etiketten), jeder
     wird geprüft; ein Fehler bricht ab und nennt – waren schon Teile gedruckt – die betroffenen
     Etiketten. ``cancelled()`` wird vor jedem Teil gefragt (True → ``PrintCancelled``; ein
-    gesendeter Teil läuft zu Ende), ``progress(gedruckt, alle)`` nach jedem."""
+    gesendeter Teil läuft zu Ende), ``progress(gedruckt, alle)`` nach jedem. ``backend``: None =
+    aus der URI (``tcp://`` → Netzwerk)."""
+    backend = backend or backend_for(printer)
     images = [image] if isinstance(image, Image.Image) else list(image)
+    if label_id not in {label.id for label in labels_for_model(model)}:
+        raise PrintError(f"Etikett {label_id!r} passt nicht zum Drucker ({model}).")
+    if backend == "network":
+        _reachable(printer)
     part = MAX_JOB_EACH if cut_every == 1 else min(cut_every, MAX_CUT_EVERY)
     status: dict = {}
     for start in range(0, len(images), part):
@@ -155,12 +189,11 @@ def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
     try:
         status = send(instructions=data, printer_identifier=printer,
                       backend_identifier=backend, blocking=True)
-    except FileNotFoundError:
-        raise PrintError(f"Drucker nicht gefunden: {printer}\n"
-                         "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', "
-                         "'lsmod | grep usblp'.") from None
-    except PermissionError:
-        raise PrintError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?") from None
+    except OSError as e:                  # pyusb: USBError ist ein OSError
+        if backend != "network":
+            raise _usb_error(e, printer) from None
+        raise PrintError(f"Netzwerkdrucker {printer} nicht erreichbar ({e.strerror or e}) – "
+                         "eingeschaltet, im selben Netz, Adresse richtig?") from None
     except ValueError as e:
         if str(e) != "Device not found":  # pyusb
             raise
@@ -173,3 +206,27 @@ def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
             _PRINTER_ERRORS.get(err, "Druckerfehler: {err}").format(label=label_id, err=err)
             for err in errors))
     return status
+
+
+def _usb_error(e: OSError, printer: str) -> PrintError:
+    """Verständliche Meldung für ein fehlendes, gesperrtes oder belegtes USB-Gerät."""
+    if isinstance(e, PermissionError):
+        return PrintError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?")
+    if isinstance(e, FileNotFoundError):
+        return PrintError(f"Drucker nicht gefunden: {printer}\n"
+                          "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', "
+                          "'lsmod | grep usblp'.")
+    return PrintError(f"Drucker {printer} nicht bereit ({e.strerror or e}) – belegt oder "
+                      "gerade beschäftigt? Kurz warten bzw. aus- und einschalten.")
+
+
+def _reachable(printer: str) -> None:
+    """Netzwerkdrucker vorab mit Zeitlimit ansprechen – brother_ql wartet sonst ohne Grenze
+    (bei einer falschen Adresse rund zwei Minuten)."""
+    host, _, port = printer[len("tcp://"):].partition(":")
+    try:
+        socket.create_connection((host, int(port or 9100)), timeout=CONNECT_TIMEOUT_S).close()
+    except (OSError, ValueError) as e:
+        reason = "keine Antwort" if isinstance(e, TimeoutError) else getattr(e, "strerror", None) or e
+        raise PrintError(f"Netzwerkdrucker {printer} nicht erreichbar ({reason}) – "
+                         "eingeschaltet, im selben Netz, Adresse richtig?") from None
diff --git a/src/labelwerk/printers.py b/src/labelwerk/printers.py
new file mode 100644
index 0000000..c9d1a42
--- /dev/null
+++ b/src/labelwerk/printers.py
@@ -0,0 +1,173 @@
+"""Drucker: Beschreibung, Erkennung und Fähigkeiten – ohne Qt und ohne Druckcode.
+
+Ein ``Printer`` beschreibt, wohin gedruckt wird (URI wie für ``printer.print_image``) und welches
+Modell es ist; die Fähigkeiten (Etikettenbreite, Abschneider, Zweifarbdruck, Längen) kommen aus
+brother_ql (``capabilities``). Erkannt wird über sysfs ohne USB-Zugriff: Modell aus der
+IEEE-1284-Kennung des Druckers, sonst aus dem USB-Produktnamen, sonst aus der Produkt-ID.
+Netzwerkdrucker stehen in den Einstellungen; erkannt wird dort nichts (kein Netzverkehr).
+"""
+from __future__ import annotations
+
+from dataclasses import dataclass
+from pathlib import Path
+
+from brother_ql.models import ModelsManager
+
+BROTHER_VENDOR_ID = "04f9"
+SYS_ROOT = "/sys/class/usbmisc"             # Tests setzen ein leeres Verzeichnis
+DEFAULT_MODEL = "QL-600"
+NETWORK_PORT = 9100
+TESTED_MODELS = frozenset({"QL-600"})       # auf echter Hardware geprüft (README-Tabelle)
+# USB-Produkt-IDs (Vendor 04f9) – letzte Rückfallebene, wenn der Drucker weder IEEE-1284-Kennung
+# noch Produktnamen liefert
+PRODUCT_IDS = {
+    "2015": "QL-500", "2016": "QL-550", "2027": "QL-560", "2028": "QL-570", "2029": "QL-580N",
+    "201b": "QL-650TD", "20c0": "QL-600", "2042": "QL-700", "2043": "QL-710W", "2044": "QL-720NW",
+    "209b": "QL-800", "209c": "QL-810W", "209d": "QL-820NWB", "2020": "QL-1050",
+    "202a": "QL-1060N", "20a7": "QL-1100", "20a8": "QL-1110NWB", "20ab": "QL-1115NWB",
+}
+UNTESTED_HINT = "ungeprüft – Rückmeldung erwünscht"
+
+
+def _models() -> dict:
+    """brother_ql-Modelle der QL-Reihe (P-touch-Bandgeräte bleiben draußen)."""
+    return {m.identifier: m for m in ModelsManager().iter_elements()
+            if m.identifier.startswith("QL-")}
+
+
+SUPPORTED_MODELS = tuple(_models())
+
+
+@dataclass(frozen=True)
+class Capabilities:
+    """Was ein Modell kann (aus brother_ql)."""
+    model: str
+    cutter: bool                 # Abschneider
+    two_color: bool              # Rot/Schwarz (Etikett 62red)
+    max_tape_mm: int             # breiteste Rolle
+    length_limits: tuple[int, int]   # Endlosband: kürzeste/längste Länge in Druckpunkten
+    tested: bool                 # auf echter Hardware geprüft
+
+
+def capabilities(model: str) -> Capabilities:
+    m = _models().get(model)
+    if m is None:
+        raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
+    return Capabilities(model, bool(m.cutting), bool(m.two_color),
+                        104 if m.number_bytes_per_row >= 162 else 62,
+                        tuple(m.min_max_length_dots), model in TESTED_MODELS)
+
+
+def known_model(name: str | None) -> str | None:
+    """Modellname, wie ihn der Drucker meldet („QL-600“, „QL-600G“, „Brother QL-720NW“), als
+    unterstütztes Modell – sonst None. Zusätze nach dem Modell (Länderkürzel) zählen nicht."""
+    if not name:
+        return None
+    name = name.strip().upper().replace("BROTHER ", "")
+    if name in SUPPORTED_MODELS:
+        return name
+    matches = [m for m in SUPPORTED_MODELS if name.startswith(m)]
+    return max(matches, key=len) if matches else None
+
+
+@dataclass(frozen=True)
+class Printer:
+    """Ein Drucker: ``uri`` wie für ``printer.print_image`` (``file:///dev/usb/lp1`` bzw.
+    ``tcp://host:9100``), ``model`` (None = nicht erkannt), ``name`` zur Anzeige, ``source``
+    ``usb`` | ``network``."""
+    uri: str
+    model: str | None
+    name: str
+    source: str = "usb"
+
+
+def backend_for(uri: str) -> str:
+    """brother_ql-Backend zur URI."""
+    if uri.startswith("tcp://"):
+        return "network"
+    if uri.startswith("usb://"):
+        return "pyusb"
+    return "linux_kernel"
+
+
+def _read(path: Path) -> str:
+    try:
+        return path.read_text(errors="replace").strip()
+    except OSError:
+        return ""
+
+
+def _ieee1284_model(text: str) -> str | None:
+    """„MFG:Brother;CMD:PT-CBP;MDL:QL-600;CLS:PRINTER;“ → „QL-600“."""
+    for part in text.split(";"):
+        key, _, value = part.partition(":")
+        if key.strip().upper() in ("MDL", "MODEL"):
+            return value.strip()
+    return None
+
+
+def usb_printers(sys_root: str | Path | None = None,
+                 dev_root: str = "/dev/usb") -> list[Printer]:
+    """Alle Brother-Drucker unter ``/dev/usb/lp*`` (sysfs, ohne USB-Zugriff), nach Name sortiert."""
+    found = []
+    for entry in sorted(Path(sys_root or SYS_ROOT).glob("lp*")):
+        iface = (entry / "device").resolve()
+        for node in (iface, *iface.parents):
+            if not (node / "idVendor").exists():
+                continue
+            if _read(node / "idVendor") == BROTHER_VENDOR_ID:
+                model = (known_model(_ieee1284_model(_read(iface / "ieee1284_id")))
+                         or known_model(_read(node / "product"))
+                         or PRODUCT_IDS.get(_read(node / "idProduct").lower()))
+                found.append(Printer(f"file://{dev_root}/{entry.name}", model,
+                                     f"{model or 'Brother-Drucker'} · {entry.name}"))
+            break
+    return found
+
+
+@dataclass(frozen=True)
+class NetworkEntry:
+    """Netzwerkdrucker aus den Einstellungen."""
+    name: str
+    host: str
+    model: str
+
+
+def network_printers(entries: list[NetworkEntry]) -> list[Printer]:
+    return [Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, f"{e.name or e.host} · Netzwerk",
+                    "network") for e in entries]
+
+
+def choose(printers: list[Printer], wanted: str = "") -> Printer | None:
+    """Der gewählte Drucker (URI aus den Einstellungen; "" = automatisch) bzw. der erste gefundene
+    USB-Drucker mit erkanntem Modell (ein Brother-Laser auf lp0 soll keine QL-Daten bekommen), dann
+    der erste USB-Drucker, sonst der erste überhaupt; None = keiner."""
+    for p in printers:
+        if wanted and p.uri == wanted:
+            return p
+    usb = [p for p in printers if p.source == "usb"]
+    known = [p for p in usb if p.model is not None]
+    return (known or usb or printers or [None])[0]
+
+
+def printer_for(uri: str, found: list[Printer]) -> Printer:
+    """Drucker zu einer angegebenen URI: ein gefundener mit dieser URI, sonst neu beschrieben –
+    bei ``usb://0x04f9:0xPID`` mit dem Modell zur Produkt-ID."""
+    for p in found:
+        if p.uri == uri:
+            return p
+    model = None
+    if uri.startswith("usb://"):
+        pid = uri[len("usb://"):].split("/")[0].split(":")[-1].lower().removeprefix("0x")
+        model = PRODUCT_IDS.get(pid.zfill(4))
+    source = "network" if uri.startswith("tcp://") else "usb"
+    return Printer(uri, model, uri, source)
+
+
+def effective_model(printer: Printer | None, fallback: str = "", last: str = "") -> str:
+    """Modell, nach dem sich Etiketten und Fähigkeiten richten: das erkannte, sonst das Ersatzmodell
+    aus den Einstellungen, sonst das zuletzt erkannte, sonst ``DEFAULT_MODEL``."""
+    for model in (printer.model if printer else None, fallback, last):
+        if model in SUPPORTED_MODELS:
+            return model
+    return DEFAULT_MODEL
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index fe65c83..15000d4 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -20,10 +20,11 @@ from functools import cached_property, lru_cache
 from PIL import Image, ImageChops, ImageDraw, ImageOps
 
 from . import barcodes, fonts, imaging
-from .document import (ALIGNMENTS, FRAME_LINE_MM, FRAME_STYLES, MAX_FRAME_MM, MAX_MARGIN_MM,
-                       MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS, BarcodeObject, Document, Frame,
-                       ImageObject, Paragraph, Span, TextObject)
+from .document import (ALIGNMENTS, COLORS, FRAME_LINE_MM, FRAME_STYLES, MAX_FRAME_MM,
+                       MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS, BarcodeObject,
+                       Document, Frame, ImageObject, Paragraph, Span, TextObject)
 from .labels import DPI, get_label, length_limits
+from .printers import capabilities
 
 MARGIN = 12            # Punkte, ca. 1 mm
 PT = DPI / 72          # Druckpunkte pro typografischem Punkt
@@ -33,6 +34,7 @@ _LINE_GAP = 4          # wie Pillow multiline_text
 _SLANT = 0.2           # Ersatzkursive: Scherung, wenn die Schrift keine echte Kursive hat
 FRAME_RADIUS_MM = 2.0  # Eckradius abgerundeter Rahmen (höchstens ¼ der kürzeren Seite)
 FRAME_CORNER_MM = 4.0  # Schenkel bei „nur Ecken“ (höchstens ¼ der kürzeren Seite)
+INK = {"black": (0, 0, 0), "red": (255, 0, 0)}   # Druckfarben im Druckbild (brother_ql trennt Rot)
 
 
 class TextTooLarge(ValueError):
@@ -88,7 +90,8 @@ class RenderedObject:
     den Rahmen); seine linke obere Ecke liegt bei ``x + image_dx``, ``y + image_dy``
     (``image_dx``/``image_dy`` ≤ 0; Bild-Objekte und Barcodes: genau der Rahmen, 0).
     ``layout``: der Zeilensatz, aus dem das Bild gezeichnet wurde (Schreibmarke, Treffer);
-    None bei Bild-Objekten und Barcodes.
+    None bei Bild-Objekten und Barcodes. ``color``: Druckfarbe der Tinte (``INK``) – Rot nur auf
+    Etiketten Rot/Schwarz, sonst schwarz.
     """
     image: Image.Image
     x: int
@@ -99,6 +102,7 @@ class RenderedObject:
     image_dx: int = 0
     image_dy: int = 0
     layout: TextLayout | None = field(default=None, compare=False, repr=False)
+    color: str = "black"
 
 
 def render_object(obj: TextObject | ImageObject | BarcodeObject, doc: Document,
@@ -155,7 +159,7 @@ def compose(rendered: list[RenderedObject], size: tuple[int, int],
     if frame is not None:
         img.paste((0, 0, 0), (0, 0), frame)
     for obj in rendered:
-        img.paste((0, 0, 0), (obj.x + obj.image_dx, obj.y + obj.image_dy),
+        img.paste(INK[obj.color], (obj.x + obj.image_dx, obj.y + obj.image_dy),
                   ImageOps.invert(obj.image))
     return img.rotate(-90, expand=True) if orientation == "horizontal" else img
 
@@ -340,6 +344,7 @@ class _Sheet:
     max_len: int
     frame: Frame | None = None
     round: bool = False        # rundes Etikett: Rahmen ist ein Kreis
+    red: bool = False          # Etikett Rot/Schwarz auf einem Zweifarb-Modell: Rot druckt rot
 
     def margins(self) -> tuple[int, int]:
         """Ränder (links/rechts, oben/unten) in Leserichtung."""
@@ -392,7 +397,8 @@ def _sheet(doc: Document, model: str) -> _Sheet:
     if doc.frame is not None:
         _check_frame(doc.frame)
     return _Sheet(doc.label_id, doc.orientation == "horizontal", label.width, feed, margin, side,
-                  min_len, max_len, doc.frame, label.shape == "round")
+                  min_len, max_len, doc.frame, label.shape == "round",
+                  label.two_color and capabilities(model).two_color)
 
 
 FRAME_TOO_BIG = "Rahmen passt nicht aufs Etikett – Abstand, Strichstärke oder Innenabstand verkleinern"
@@ -428,6 +434,8 @@ class Prepared:
 
 
 def _prepare(obj: TextObject | ImageObject | BarcodeObject, sheet: _Sheet) -> Prepared:
+    if obj.color not in COLORS:
+        raise ValueError(f"Unbekannte Farbe {obj.color!r} – erlaubt: schwarz, rot (black, red)")
     if isinstance(obj, ImageObject):
         return _prepare_image(obj)
     if isinstance(obj, BarcodeObject):
@@ -525,6 +533,14 @@ def _place(prep: Prepared, sheet: _Sheet, width: int, height: int
 
 
 def _finish(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
+    """Objekt zeichnen und platzieren (``_finish_shape``); Rot nur auf Etiketten Rot/Schwarz."""
+    rendered = _finish_shape(prep, sheet, width, height)
+    if prep.obj.color == "red" and sheet.red:
+        rendered.color = "red"
+    return rendered
+
+
+def _finish_shape(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
     """Objektbild aus dem Zeilensatz (``_place``) zeichnen und auf dem Etikett platzieren;
     Bild, Rahmen und Bildlage werden mit der Fläche gedreht."""
     obj = prep.obj
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 803b939..1bbae8f 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -15,6 +15,7 @@ from .clipart import RECENT_LIMIT
 from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .fonts import DEFAULT_FAMILY
 from .labels import labels_for_model
+from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model
 from .storage import RECENT_FILES
 
 THEMES = ("rawblock", "classic")
@@ -37,6 +38,10 @@ class Settings:
     symbols_favorites: list[str] = field(default_factory=list)   # Symbol-ids
     recent_files: list[str] = field(default_factory=list)   # Zuletzt geöffnet (Pfade), neueste zuerst
     start_favorite: str | None = None      # Favorit, mit dem labelwerk startet; None = leer
+    printer: str = ""                      # gewählter Drucker (URI); "" = automatisch
+    printer_model: str = ""                # Ersatz, wenn das Modell nicht erkannt wird; "" = keins
+    last_model: str = ""                   # zuletzt erkanntes Modell (gilt ohne Drucker)
+    network_printers: list[dict] = field(default_factory=list)   # {name, host, model}
     shortcuts: dict[str, str] = field(default_factory=dict)   # nur geänderte Kürzel, "" = keins
     warnings: list[str] = field(default_factory=list, compare=False, repr=False)
 
@@ -63,6 +68,11 @@ def _rules(model: str) -> dict:
         "symbols_favorites": lambda v: isinstance(v, list),
         "recent_files": lambda v: isinstance(v, list),
         "start_favorite": lambda v: v is None or (isinstance(v, str) and bool(v.strip())),
+        "printer": lambda v: isinstance(v, str) and (
+            v == "" or v.startswith(("file://", "tcp://", "usb://"))),
+        "printer_model": lambda v: v == "" or v in SUPPORTED_MODELS,
+        "last_model": lambda v: v == "" or v in SUPPORTED_MODELS,
+        "network_printers": lambda v: isinstance(v, list),
     }
 
 
@@ -74,7 +84,9 @@ def settings_path() -> Path:
     return Path(base) / "labelwerk" / "settings.json"
 
 
-def load_settings(path: str | Path | None = None, model: str = "QL-600") -> Settings:
+def load_settings(path: str | Path | None = None, model: str | None = None) -> Settings:
+    """``model``: Modell für die Prüfung des Etiketts; None = aus den Einstellungen (Ersatzmodell,
+    zuletzt erkanntes)."""
     path = Path(path) if path else settings_path()
     settings = Settings()
     try:
@@ -87,6 +99,9 @@ def load_settings(path: str | Path | None = None, model: str = "QL-600") -> Sett
         settings.warnings.append(f"Einstellungen nicht lesbar ({path}): {e} – Standardwerte aktiv.")
         return settings
     _migrate_font_size(raw, settings)
+    if model is None:
+        model = effective_model(None, *(raw.get(k) if raw.get(k) in SUPPORTED_MODELS else ""
+                                        for k in ("printer_model", "last_model")))
     for key, valid in _rules(model).items():
         if key not in raw:
             continue
@@ -100,6 +115,8 @@ def load_settings(path: str | Path | None = None, model: str = "QL-600") -> Sett
                 value = _symbol_ids(key, value, settings.warnings)
             elif key == "recent_files":
                 value = _text_list(key, value, settings.warnings)[:RECENT_FILES]
+            elif key == "network_printers":
+                value = _network(value, settings.warnings)
             setattr(settings, key, value)
         else:
             settings.warnings.append(f"Einstellung {key!r} ungültig ({value!r}) – "
@@ -118,6 +135,31 @@ def _text_list(key: str, value: list, warnings: list[str]) -> list[str]:
     return list(dict.fromkeys(valid))
 
 
+def _network(value: list, warnings: list[str]) -> list[dict]:
+    """Netzwerkdrucker: Einträge mit Host (ohne Leerzeichen, ohne Schema) und bekanntem Modell;
+    ungültige einzeln verworfen (mit Hinweis)."""
+    valid = [{"name": e.get("name") or "", "host": e["host"].strip(), "model": e["model"]}
+             for e in value if isinstance(e, dict) and isinstance(e.get("host"), str)
+             and valid_host(e["host"]) and e.get("model") in SUPPORTED_MODELS
+             and isinstance(e.get("name", ""), str)]
+    if len(valid) != len(value):
+        warnings.append("Einstellung 'network_printers': ungültige Einträge verworfen.")
+    return valid
+
+
+def valid_host(host: str) -> bool:
+    """IPv4-Adresse oder Hostname (ohne Schema, Pfad, Port, Leer- und Steuerzeichen; IPv6 geht
+    nicht – „:“ trennt den Port)."""
+    host = host.strip()
+    return (bool(host) and host.isprintable() and not any(c in host for c in " /:")
+            and len(host) <= 253)
+
+
+def network_entries(settings: Settings) -> list[NetworkEntry]:
+    """Netzwerkdrucker der Einstellungen für ``printers.network_printers``."""
+    return [NetworkEntry(e["name"], e["host"], e["model"]) for e in settings.network_printers]
+
+
 def _symbol_ids(key: str, value: list, warnings: list[str]) -> list[str]:
     """Symbol-ids: ungültige Einträge einzeln verworfen (mit Hinweis), Doppelte entfernt,
     Zuletzt verwendet auf ``RECENT_LIMIT`` begrenzt."""
diff --git a/src/labelwerk/storage.py b/src/labelwerk/storage.py
index b05d6b6..4eef4e9 100644
--- a/src/labelwerk/storage.py
+++ b/src/labelwerk/storage.py
@@ -25,11 +25,11 @@ from pathlib import Path
 from PIL import Image
 
 from . import barcodes
-from .document import (ALIGNMENTS, BARCODE_KINDS, BARCODE_MM, CUTS, FRAME_LINE_MM, FRAME_STYLES,
-                       MAX_BARCODE_DATA, MAX_DIGITS, MAX_FRAME_MM, MAX_MARGIN_MM, MAX_MODULE,
-                       MAX_NUMBER, MAX_POSITION_MM, MAX_SERIES_ROWS, ORIENTATIONS, QR_LEVELS,
-                       ROTATIONS, BarcodeObject, Document, Frame, ImageObject, Numbering, Paragraph,
-                       Series, Span, TextObject)
+from .document import (ALIGNMENTS, BARCODE_KINDS, BARCODE_MM, COLORS, CUTS, FRAME_LINE_MM,
+                       FRAME_STYLES, MAX_BARCODE_DATA, MAX_DIGITS, MAX_FRAME_MM, MAX_MARGIN_MM,
+                       MAX_MODULE, MAX_NUMBER, MAX_POSITION_MM, MAX_SERIES_ROWS, ORIENTATIONS,
+                       QR_LEVELS, ROTATIONS, BarcodeObject, Document, Frame, ImageObject, Numbering,
+                       Paragraph, Series, Span, TextObject)
 from .imaging import MAX_PIXELS, MODES
 from .labels import get_label
 
@@ -52,14 +52,14 @@ SPAN = {"text": "span_text", "family": "str?", "size_pt": "pt?", "bold": "bool",
         "underline": "bool"}
 PARAGRAPH = {"align": "align"}                                    # dazu „spans“
 TEXT = {"size_pt": "pt?", "font_path": "str?", "fit": "bool", "x_mm": "pos?", "y_mm": "pos?",
-        "w_mm": "size?", "h_mm": "size?", "rotation": "rotation"}  # dazu „paragraphs“
+        "w_mm": "size?", "h_mm": "size?", "rotation": "rotation", "color": "color"}  # dazu „paragraphs“
 IMAGE = {"png": "bytes", "source": "str", "page": "page?", "crop": "crop", "x_mm": "pos",
          "y_mm": "pos", "w_mm": "size", "h_mm": "size", "rotation": "rotation", "mode": "mode",
          "threshold": "threshold", "invert": "bool", "keep_ratio": "bool", "dpi": "dpi",
-         "svg": "bytes?"}
+         "svg": "bytes?", "color": "color"}
 BARCODE = {"kind": "barcode_kind", "data": "barcode_data", "x_mm": "pos", "y_mm": "pos",
            "module": "module", "h_mm": "barcode_mm", "rotation": "rotation", "text": "bool",
-           "error": "qr_level"}
+           "error": "qr_level", "color": "color"}
 FRAME = {"style": "frame_style", "rounded": "bool", "line_mm": "frame_line",
          "inset_mm": "frame_mm", "padding_mm": "frame_mm"}
 NUMBERING = {"start": "number", "step": "step", "count": "count", "digits": "digits"}
@@ -121,6 +121,7 @@ _KINDS = {
     "module": lambda v: _int(v) and 1 <= v <= MAX_MODULE,
     "barcode_mm": lambda v: _num(v) and BARCODE_MM[0] <= v <= BARCODE_MM[1],
     "qr_level": lambda v: v in QR_LEVELS,
+    "color": lambda v: v in COLORS,
     "path": lambda v: _text(v) and v != "" and "\x00" not in v,
     "crop": lambda v: v is None or (isinstance(v, list) and len(v) == 4 and all(map(_int, v))),
 }
diff --git a/tools/golden.py b/tools/golden.py
new file mode 100644
index 0000000..36f533e
--- /dev/null
+++ b/tools/golden.py
@@ -0,0 +1,76 @@
+"""Referenz-Rasterdaten je Druckermodell (tests/golden/raster.json) prüfen bzw. neu erzeugen.
+
+    python tools/golden.py            # vergleichen (wie der Test)
+    python tools/golden.py --update   # nach einer gewollten Änderung neu schreiben
+
+Je Modell ein festes Testetikett (nur Formen, keine Schrift – Schriftversionen dürfen nicht
+zählen) als SHA-256 der Rasterdaten: Endlos 62 mm mit und ohne Schnitt, gestanzt 62×29, bei
+breiten Modellen 102 mm, bei Zweifarb-Modellen 62red. Beweist, was gesendet wird – nicht, was
+gedruckt wird. Die Werte hängen an brother_ql (pyproject: auf 1.3.x festgelegt) – nach einem
+Update der Bibliothek prüfen und neu erzeugen.
+"""
+from __future__ import annotations
+
+import hashlib
+import json
+import sys
+from pathlib import Path
+
+from PIL import Image, ImageDraw
+
+from labelwerk.labels import get_label, labels_for_model
+from labelwerk.printer import build_instructions
+from labelwerk.printers import SUPPORTED_MODELS
+
+GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "raster.json"
+
+
+def test_image(label_id: str, length: int = 200) -> Image.Image:
+    """Rahmen, Schachbrett (und bei 62red ein rotes Feld) über die ganze Breite – nur achsparallele
+    Rechtecke, damit keine Zeichenroutine von Pillow mitzählt."""
+    label = get_label(label_id)
+    size = (label.width, label.height or length)
+    img = Image.new("RGB", size, "white")
+    pen = ImageDraw.Draw(img)
+    pen.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="black", width=3)
+    for y in range(10, size[1] - 10, 20):
+        for x in range(10 + (y // 20) % 2 * 10, size[0] // 2, 20):
+            pen.rectangle((x, y, x + 9, y + 9), fill="black")
+    if label.two_color:
+        pen.rectangle((size[0] // 2 + 10, 10, size[0] - 10, size[1] // 2), fill=(255, 0, 0))
+    return img
+
+
+def cases(model: str) -> dict[str, bytes]:
+    available = {label.id for label in labels_for_model(model)}
+    out = {"62": build_instructions(test_image("62"), "62", model),
+           "62-ohne-schnitt": build_instructions(test_image("62"), "62", model, cut=False),
+           "62x29": build_instructions(test_image("62x29"), "62x29", model),
+           "62-serie": build_instructions([test_image("62")] * 3, "62", model, cut_every=3)}
+    if "102" in available:
+        out["102"] = build_instructions(test_image("102"), "102", model)
+    if "62red" in available:
+        out["62red"] = build_instructions(test_image("62red"), "62red", model)
+    return out
+
+
+def digests() -> dict[str, dict[str, str]]:
+    return {model: {name: hashlib.sha256(data).hexdigest() for name, data in cases(model).items()}
+            for model in SUPPORTED_MODELS}
+
+
+def main(argv: list[str]) -> int:
+    current = digests()
+    if "--update" in argv:
+        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
+        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
+        print(f"geschrieben: {GOLDEN}")
+        return 0
+    stored = json.loads(GOLDEN.read_text())
+    changed = [m for m in sorted(set(current) | set(stored)) if current.get(m) != stored.get(m)]
+    print("unverändert" if not changed else "geändert: " + ", ".join(changed))
+    return 1 if changed else 0
+
+
+if __name__ == "__main__":
+    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2310 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/labelwerk/cli.py src/labelwerk/document.py src/labelwerk/labels.py src/labelwerk/printer.py src/labelwerk/printers.py src/labelwerk/render.py src/labelwerk/settings.py src/labelwerk/storage.py tests/conftest.py tests/golden/raster.json tests/test_cli.py tests/test_golden.py tests/test_printers.py tools/golden.py
git commit -m "Kern: Drucker-Kompatibilität – Modell erkennen (IEEE-1284, Produktname, Produkt-ID), Fähigkeiten je Modell, alle QL inkl. 102 mm, Netzwerkdrucker, ohne Abschneider, Rot/Schwarz je Objekt, CLI -m/-l auto und printers, Referenztests je Modell

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: GUI – Druckerwahl, Modellwechsel, Einstellungen, Farbe, README-Tabelle

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/file_session.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/media_worker.py`
- Modify: `src/labelwerk/gui/panels/barcode.py`
- Modify: `src/labelwerk/gui/panels/layout.py`
- Modify: `src/labelwerk/gui/panels/paper.py`
- Modify: `src/labelwerk/gui/panels/series.py`
- Modify: `src/labelwerk/gui/print_worker.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/printers.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/gui/conftest.py`
- Modify: `tests/gui/test_gui_barcode.py`
- Modify: `tests/gui/test_gui_cancel.py`
- Modify: `tests/gui/test_gui_files.py`
- Modify: `tests/gui/test_gui_media.py`
- Create: `tests/gui/test_gui_printers.py`
- Modify: `tests/gui/test_gui_series.py`
- Modify: `tests/gui/test_gui_window.py`
- Modify: `tests/test_printers.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `MainWindow`: `printers`/`printer`, `refresh_printer` (Erkennung, Auswahl, Modell), `choose_printer(uri)`, `set_model(model)`, `_fit_label`, `_fill_printer_menu`, `printer_menu`, `printer_status` (QToolButton), `set_color_selected`, `_update_media_button`; `FileSession.fitting_label`; `PaperPanel.set_model`; `Canvas.set_model`, `to_qimage(img, ink)`; `SeriesPanel.set_cutter`, `no_cutter`; `LayoutPanel.colors`, `color_chosen`, `set_red_available`; `BarcodePanel.red_available`; `PrintWorker(…, printer=None)`, `MediaWorker(model, printer=None)`; `SettingsDialog`: `printer_model`, `network`, `add_network`, `remove_network`; `settings`: Etikett nur noch „bekannt“; `printers.choose` ohne Ersatz für einen fehlenden gewählten Drucker; README-Tabelle.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/conftest.py b/tests/gui/conftest.py
index b6c8a02..43f5f55 100644
--- a/tests/gui/conftest.py
+++ b/tests/gui/conftest.py
@@ -52,10 +52,11 @@ else:
     @pytest.fixture(autouse=True)
     def no_printer(monkeypatch):
         """Kein Test liest echte Druckerdaten aus /sys."""
-        for module in ("labelwerk.gui.main_window", "labelwerk.gui.print_worker",
-                       "labelwerk.gui.media_worker"):
+        for module in ("labelwerk.gui.print_worker", "labelwerk.gui.media_worker"):
             monkeypatch.setattr(f"{module}.find_brother_lp", lambda: None)
             monkeypatch.setattr(f"{module}.brother_busy", lambda: False)
+        monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [])
+        monkeypatch.setattr("labelwerk.gui.main_window.brother_busy", lambda: False)
 
         calls = []
 
diff --git a/tests/gui/test_gui_barcode.py b/tests/gui/test_gui_barcode.py
index e6dbd28..4eacbb0 100644
--- a/tests/gui/test_gui_barcode.py
+++ b/tests/gui/test_gui_barcode.py
@@ -257,7 +257,7 @@ def test_series_prints_the_filled_barcode(qtbot, monkeypatch):
     jobs = []
 
     class Fake:
-        def __init__(self, image, label_id, model, cut_every=1):
+        def __init__(self, image, label_id, model, cut_every=1, printer=None):
             jobs.append(image)
             from labelwerk.gui.print_worker import PrintSignals
             self.signals = PrintSignals()
diff --git a/tests/gui/test_gui_cancel.py b/tests/gui/test_gui_cancel.py
index cec0433..d46e5ea 100644
--- a/tests/gui/test_gui_cancel.py
+++ b/tests/gui/test_gui_cancel.py
@@ -13,7 +13,7 @@ class FakeWorker:
     """Druck-Worker ohne Thread und Drucker; merkt sich „Abbrechen“."""
     instances = []
 
-    def __init__(self, image, label_id, model, cut_every=1):
+    def __init__(self, image, label_id, model, cut_every=1, printer=None):
         self.image, self.cancelled = image, False
         self.signals = PrintSignals()
         FakeWorker.instances.append(self)
diff --git a/tests/gui/test_gui_files.py b/tests/gui/test_gui_files.py
index 832828a..4a2dccb 100644
--- a/tests/gui/test_gui_files.py
+++ b/tests/gui/test_gui_files.py
@@ -255,7 +255,7 @@ def test_printing_a_favorite_does_not_touch_the_open_label(qtbot, monkeypatch):
     started = []
 
     class FakeWorker:
-        def __init__(self, image, label_id, model, cut_every=1):
+        def __init__(self, image, label_id, model, cut_every=1, printer=None):
             started.append((image.tobytes(), label_id))
             from labelwerk.gui.print_worker import PrintSignals
             self.signals = PrintSignals()
diff --git a/tests/gui/test_gui_media.py b/tests/gui/test_gui_media.py
index 9788b90..d165dea 100644
--- a/tests/gui/test_gui_media.py
+++ b/tests/gui/test_gui_media.py
@@ -4,6 +4,10 @@ from labelwerk.gui.main_window import MainWindow
 from labelwerk.media import Media, MediaError
 from labelwerk.settings import Settings
 
+from labelwerk.printers import Printer
+
+LP1 = Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")
+
 
 def _printer_with(monkeypatch, media=None, error=None):
     monkeypatch.setattr("labelwerk.gui.media_worker.find_brother_lp", lambda: "file:///dev/usb/lp1")
@@ -74,7 +78,7 @@ def test_printer_appearing_triggers_status_and_media_check(qtbot, monkeypatch):
     win = MainWindow(settings=Settings(check_media_on_start=True))
     qtbot.addWidget(win)
     assert win.printer_status.text() == "○ kein Drucker"
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
     _printer_with(monkeypatch, Media(62, 29, "die_cut"))
     win._printer_timer.timeout.emit()              # nächster Abfrage-Takt
     assert "lp1" in win.printer_status.text()
@@ -82,20 +86,20 @@ def test_printer_appearing_triggers_status_and_media_check(qtbot, monkeypatch):
 
 
 def test_printer_appearing_without_auto_check(window, monkeypatch):
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
     window._printer_timer.timeout.emit()
     assert "lp1" in window.printer_status.text()
     assert not window.is_checking_media()
 
 
 def test_printer_disconnect_clears_media_status(window, qtbot, monkeypatch):
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
     window.refresh_printer()
     _printer_with(monkeypatch, Media(62, 0, "endless"))
     window.check_media()
     qtbot.waitUntil(lambda: not window.is_checking_media(), timeout=3000)
     assert not window.media_status.isHidden()
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: None)
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [])
     window.refresh_printer()
     assert window.media_status.isHidden()
     assert window.printer_status.text() == "○ kein Drucker"
@@ -165,7 +169,7 @@ def test_media_check_is_caught_up_after_print(qtbot, monkeypatch):
     win = MainWindow(settings=Settings(check_media_on_start=True))
     qtbot.addWidget(win)
     win._printing = True                           # Druck läuft, Drucker erscheint
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
     _printer_with(monkeypatch, Media(62, 29, "die_cut"))
     win.refresh_printer()
     assert not win.is_checking_media()
@@ -177,9 +181,9 @@ def test_pending_media_check_dropped_on_disconnect(qtbot, monkeypatch):
     win = MainWindow(settings=Settings(check_media_on_start=True))
     qtbot.addWidget(win)
     win._printing = True
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: "file:///dev/usb/lp1")
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [LP1])
     win.refresh_printer()
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", lambda: None)
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", lambda: [])
     win.refresh_printer()
     win._printing = False
     win._print_finished()
diff --git a/tests/gui/test_gui_printers.py b/tests/gui/test_gui_printers.py
new file mode 100644
index 0000000..43ff8db
--- /dev/null
+++ b/tests/gui/test_gui_printers.py
@@ -0,0 +1,296 @@
+"""Drucker-Kompatibilität in der GUI: Druckerwahl in der Statusleiste, Modellwechsel (Etiketten,
+Schnitt, Farbe), Netzwerkdrucker, Einstellungen, Farbe in Layout, Druck an den gewählten Drucker."""
+import pytest
+from PySide6.QtWidgets import QTableWidgetItem
+
+from labelwerk.document import Document, Numbering, Series, TextObject
+from labelwerk.gui import main_window
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.gui.print_worker import PrintSignals
+from labelwerk.gui.settings_dialog import SettingsDialog
+from labelwerk.printers import Printer
+from labelwerk.settings import Settings, load_settings
+
+QL600 = Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")
+QL500 = Printer("file:///dev/usb/lp2", "QL-500", "QL-500 · lp2")
+QL820 = Printer("file:///dev/usb/lp3", "QL-820NWB", "QL-820NWB · lp3")
+QL1100 = Printer("file:///dev/usb/lp4", "QL-1100", "QL-1100 · lp4")
+UNKNOWN = Printer("file:///dev/usb/lp0", None, "Brother-Drucker · lp0")
+
+
+def _window(qtbot, monkeypatch, found=(), doc=None, **settings):
+    monkeypatch.setattr(main_window, "usb_printers", lambda: list(found))
+    win = MainWindow(doc=doc if doc is not None else Document("62", objects=[TextObject("A")]),
+                     settings=Settings(check_media_on_start=False, **settings))
+    qtbot.addWidget(win)
+    win.show()
+    win.render_now()
+    return win
+
+
+def _labels(win):
+    combo = win.panel("paper").combo
+    return [combo.itemData(i) for i in range(combo.count()) if combo.itemData(i)]
+
+
+class FakeWorker:
+    instances = []
+
+    def __init__(self, image, label_id, model, cut_every=1, printer=None):
+        self.image, self.label_id, self.model, self.printer = image, label_id, model, printer
+        self.cut_every = cut_every
+        self.signals = PrintSignals()
+        FakeWorker.instances.append(self)
+
+
+@pytest.fixture
+def workers(monkeypatch):
+    FakeWorker.instances = []
+    monkeypatch.setattr(main_window, "PrintWorker", FakeWorker)
+    monkeypatch.setattr(main_window.QThreadPool.globalInstance(), "start", lambda worker: None)
+    return FakeWorker.instances
+
+
+# --- Erkennen und wählen --------------------------------------------------------------------------
+def test_detected_model_drives_labels_and_is_remembered(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL1100])
+    assert win.model == "QL-1100" and "102" in _labels(win)
+    assert win.printer_status.text() == "● QL-1100 · lp4 · ungeprüft"
+    assert "Rückmeldung erwünscht" in win.printer_status.toolTip()
+    assert win.settings.last_model == "QL-1100"
+    assert load_settings().last_model == "QL-1100"                 # gespeichert
+
+
+def test_tested_model_has_no_marker(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL600])
+    assert win.printer_status.text() == "● QL-600 · lp1" and win.model == "QL-600"
+    assert "102" not in _labels(win)
+
+
+def test_without_printer_the_last_model_counts(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [], last_model="QL-820NWB")
+    assert win.model == "QL-820NWB" and "62red" in _labels(win)
+    assert win.printer_status.text() == "○ kein Drucker"
+
+
+def test_unknown_model_uses_the_fallback(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [UNKNOWN], printer_model="QL-700")
+    assert win.model == "QL-700"
+    assert win.printer_status.text() == "● Brother-Drucker · lp0 (als QL-700)"
+
+
+def test_menu_lists_printers_and_choosing_one_is_saved(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL600, QL1100])
+    assert win.printer is not None and win.printer.uri == QL600.uri
+    win._fill_printer_menu()
+    texts = [a.text() for a in win.printer_menu.actions() if a.text()]
+    assert texts[:3] == ["Automatisch (erster gefundener)", "QL-600 · lp1",
+                         "QL-1100 · lp4 – ungeprüft"]
+    assert texts[-1] == "Netzwerkdrucker eintragen …"
+    next(a for a in win.printer_menu.actions() if a.text().startswith("QL-1100")).trigger()
+    assert win.printer.uri == QL1100.uri and win.model == "QL-1100"
+    assert load_settings().printer == QL1100.uri
+    win.choose_printer("")
+    assert win.printer.uri == QL600.uri
+
+
+def test_network_printer_from_the_settings(qtbot, monkeypatch, workers):
+    win = _window(qtbot, monkeypatch, [], network_printers=[
+        {"name": "Büro", "host": "10.0.0.5", "model": "QL-720NW"}])
+    assert win.printer.uri == "tcp://10.0.0.5:9100" and win.model == "QL-720NW"
+    assert not win.panel("paper").check.isEnabled()                   # Medium prüfen nur USB
+    assert "nur bei Druckern per USB" in win.panel("paper").check.toolTip()
+    win.panel("text").edit.setPlainText("Hallo")
+    win.print_label()
+    assert workers[0].printer == "tcp://10.0.0.5:9100" and workers[0].model == "QL-720NW"
+
+
+def test_network_status_says_sent(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [])
+    win._print_done({"outcome": "sent", "did_print": False})
+    assert win.result.text() == "Gesendet ✓ (der Drucker meldet keinen Status zurück)"
+
+
+# --- Modellwechsel -------------------------------------------------------------------------------
+def test_label_that_does_not_fit_stays_with_a_hint(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL1100], doc=Document("102", objects=[TextObject("A")]))
+    win.files.origin = "file"                        # geöffnete Datei: bleibt bei ihrem Etikett
+    found = [QL600]
+    monkeypatch.setattr(main_window, "usb_printers", lambda: found)
+    win.refresh_printer()
+    assert win.model == "QL-600" and win.doc.label_id == "102"
+    combo = win.panel("paper").combo
+    assert combo.currentData() == "102" and "passt nicht zum QL-600" in combo.currentText()
+    assert "passt nicht zum Drucker (QL-600)" in win.result.text()
+
+
+def test_printer_without_cutter_hides_the_cut_choice(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL500])
+    panel = win.panel("series")
+    assert panel.cut.isHidden() and not panel.no_cutter.isHidden()
+    win2 = _window(qtbot, monkeypatch, [QL600])
+    assert not win2.panel("series").cut.isHidden() and win2.panel("series").no_cutter.isHidden()
+
+
+def test_fixed_model_is_not_replaced(qtbot, monkeypatch):
+    monkeypatch.setattr(main_window, "usb_printers", lambda: [QL1100])
+    win = MainWindow(doc=Document("62"), model="QL-600",
+                     settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    assert win.model == "QL-600"
+
+
+# --- Farbe ---------------------------------------------------------------------------------------
+def test_color_buttons_need_a_red_label_on_a_two_color_printer(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL600])
+    win.canvas.set_selection([0])
+    layout = win.panel("layout")
+    assert not layout.colors["red"].isEnabled() and "62 mm Rot/Schwarz" in layout.colors["red"].toolTip()
+    win2 = _window(qtbot, monkeypatch, [QL820],
+                   doc=Document("62red", objects=[TextObject("A", size_pt=20, x_mm=2, y_mm=2)]))
+    win2.canvas.set_selection([0])
+    layout = win2.panel("layout")
+    assert layout.colors["red"].isEnabled()
+    layout.colors["red"].click()
+    assert win2.doc.objects[0].color == "red" and win2.rendered[0].color == "red"
+    assert (255, 0, 0) in {c for _, c in win2.image.getcolors(1 << 20)}
+    win2.undo()
+    assert win2.doc.objects[0].color == "black"
+
+
+def test_red_series_keeps_red(qtbot, monkeypatch, workers):
+    obj = TextObject("X{Nummer}", size_pt=20, x_mm=2, y_mm=2)
+    obj.color = "red"
+    win = _window(qtbot, monkeypatch, [QL820], doc=Document(
+        "62red", objects=[obj], series=Series(numbering=Numbering(count=2))))
+    win.panel("series").refresh()
+    win.ask_print_count = lambda n: True
+    win.print_label()
+    images = workers[0].image
+    assert all(img.mode == "RGB" and (255, 0, 0) in {c for _, c in img.getcolors(1 << 20)}
+               for img in images)
+
+
+# --- Einstellungen -------------------------------------------------------------------------------
+def test_settings_dialog_edits_model_fallback_and_network_printers(qtbot, tmp_path):
+    path = tmp_path / "s.json"
+    dialog = SettingsDialog(Settings(printer="tcp://1.2.3.4:9100", last_model="QL-700",
+                                     network_printers=[{"name": "Alt", "host": "1.2.3.4",
+                                                        "model": "QL-710W"}]), path)
+    qtbot.addWidget(dialog)
+    assert dialog.network.rowCount() == 1
+    dialog.printer_model.setCurrentIndex(dialog.printer_model.findData("QL-570"))
+    dialog.add_network.click()
+    dialog.network.setItem(1, 0, QTableWidgetItem("Lager"))
+    dialog.network.setItem(1, 1, QTableWidgetItem("drucker.lan"))
+    dialog.accept()
+    saved = load_settings(path)
+    assert saved.printer_model == "QL-570" and saved.last_model == "QL-700"
+    assert saved.printer == "tcp://1.2.3.4:9100"
+    assert saved.network_printers == [{"name": "Alt", "host": "1.2.3.4", "model": "QL-710W"},
+                                      {"name": "Lager", "host": "drucker.lan",
+                                       "model": "QL-720NW"}]
+
+
+def test_settings_dialog_rejects_a_bad_address(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    dialog.add_network.click()
+    dialog.network.setItem(0, 1, QTableWidgetItem("tcp://10.0.0.5:9100"))
+    dialog.accept()
+    assert dialog.saved is None and "Adresse „tcp://10.0.0.5:9100“ ungültig" in dialog.error.text()
+    assert not (tmp_path / "s.json").exists()
+
+
+def test_untested_models_are_marked_in_the_settings(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    items = [dialog.printer_model.itemText(i) for i in range(dialog.printer_model.count())]
+    assert items[0] == "Automatisch (erkannt)" and "QL-600" in items and "QL-700 – ungeprüft" in items
+
+
+# --- Nachbesserungen nach dem Review --------------------------------------------------------------
+def test_new_untouched_label_follows_the_printer(qtbot, monkeypatch):
+    monkeypatch.setattr(main_window, "usb_printers", lambda: [QL600])
+    win = MainWindow(settings=Settings(check_media_on_start=False, label_id="102"))
+    qtbot.addWidget(win)
+    assert win.doc.label_id == "62" and not win.files.modified()
+    assert "passt nicht zum QL-600 – 62 mm endlos genommen" in win.result.text()
+    win.files.new()
+    assert win.doc.label_id == "62"
+
+
+def test_switching_usb_printers_forgets_the_roll(qtbot, monkeypatch):
+    from labelwerk.media import Media
+    win = _window(qtbot, monkeypatch, [QL1100, QL600])
+    win.panel("paper").show_media(Media(102, 0, "endless"), "102")
+    win.choose_printer(QL600.uri)
+    assert win.panel("paper").media_label is None
+    win.files.new()
+    assert win.doc.label_id in {label.id for label in __import__(
+        "labelwerk.labels", fromlist=["x"]).labels_for_model("QL-600")}
+
+
+def test_missing_chosen_printer_is_not_replaced(qtbot, monkeypatch, workers):
+    win = _window(qtbot, monkeypatch, [QL600], printer=QL1100.uri)
+    assert win.printer is None and win.printer_status.text() == "○ gewählter Drucker fehlt"
+    win.panel("text").edit.setPlainText("Hallo")
+    win.print_label()
+    assert workers == [] and "Gewählter Drucker nicht gefunden" in win.result.text()
+
+
+def test_black_stays_available_and_red_needs_a_two_color_model(qtbot, monkeypatch):
+    obj = TextObject("A", size_pt=20, x_mm=2, y_mm=2)
+    obj.color = "red"
+    win = _window(qtbot, monkeypatch, [QL600], doc=Document("62", objects=[obj]))
+    win.files.origin = "file"
+    win.canvas.set_selection([0])
+    layout = win.panel("layout")
+    assert layout.colors["black"].isEnabled() and not layout.colors["red"].isEnabled()
+    layout.colors["black"].click()
+    assert win.doc.objects[0].color == "black"
+    red = _window(qtbot, monkeypatch, [QL600], doc=Document("62red", objects=[TextObject("B")]))
+    red.files.origin = "file"
+    red.canvas.set_selection([0])
+    assert not red.panel("layout").colors["red"].isEnabled()      # 62red, aber QL-600
+
+
+def test_unfitting_entry_is_not_selectable_and_disappears(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL1100], doc=Document("102", objects=[TextObject("A")]))
+    win.files.origin = "file"
+    monkeypatch.setattr(main_window, "usb_printers", lambda: [QL600])
+    win.refresh_printer()
+    combo = win.panel("paper").combo
+    index = combo.findData("102")
+    assert not combo.model().item(index).isEnabled()
+    combo.setCurrentIndex(combo.findData("62"))
+    assert win.doc.label_id == "62" and combo.findData("102") < 0
+
+
+def test_media_button_stays_off_while_checking(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL600])
+    win.is_checking_media = lambda: True
+    win.refresh_printer()
+    assert not win.panel("paper").check.isEnabled()
+
+
+def test_settings_keep_a_label_of_another_printer(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(label_id="102"), tmp_path / "s.json", model="QL-600")
+    qtbot.addWidget(dialog)
+    assert dialog.values().label_id == "102"
+    assert "passt nicht zum QL-600" in dialog.label.currentText()
+
+
+def test_remove_without_selection_removes_nothing(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(network_printers=[
+        {"name": "A", "host": "1.1.1.1", "model": "QL-710W"},
+        {"name": "B", "host": "2.2.2.2", "model": "QL-710W"}]), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    dialog.network.setCurrentCell(-1, -1)
+    dialog.remove_network.click()
+    assert dialog.network.rowCount() == 2
+
+
+def test_canvas_length_limits_follow_the_model(qtbot, monkeypatch):
+    win = _window(qtbot, monkeypatch, [QL1100])
+    assert win.canvas.max_mm == pytest.approx(35434 * 25.4 / 300, abs=0.5)
diff --git a/tests/gui/test_gui_series.py b/tests/gui/test_gui_series.py
index 0a3fee7..5ad4cb7 100644
--- a/tests/gui/test_gui_series.py
+++ b/tests/gui/test_gui_series.py
@@ -47,7 +47,7 @@ class FakeWorker:
     """Druck-Worker, der nur mitschreibt (kein Thread, kein Drucker)."""
     jobs = []
 
-    def __init__(self, image, label_id, model, cut_every=1):
+    def __init__(self, image, label_id, model, cut_every=1, printer=None):
         FakeWorker.jobs.append((image, label_id, cut_every))
         from labelwerk.gui.print_worker import PrintSignals
         self.signals = PrintSignals()
diff --git a/tests/gui/test_gui_window.py b/tests/gui/test_gui_window.py
index 063387c..a47f64b 100644
--- a/tests/gui/test_gui_window.py
+++ b/tests/gui/test_gui_window.py
@@ -252,7 +252,7 @@ def test_printer_detection_error_at_startup(qtbot, monkeypatch):
     def broken():
         raise OSError("kaputt")
 
-    monkeypatch.setattr("labelwerk.gui.main_window.find_brother_lp", broken)
+    monkeypatch.setattr("labelwerk.gui.main_window.usb_printers", broken)
     win = MainWindow()
     qtbot.addWidget(win)
     assert "unbekannt" in win.printer_status.text()
diff --git a/tests/test_printers.py b/tests/test_printers.py
index a0b27e2..9c1ca88 100644
--- a/tests/test_printers.py
+++ b/tests/test_printers.py
@@ -103,7 +103,7 @@ NET = Printer("tcp://10.0.0.5:9100", "QL-720NW", "Büro · Netzwerk", "network")
 def test_choose_the_wanted_printer_else_the_first_usb():
     assert choose([NET, USB]) == USB
     assert choose([NET, USB], NET.uri) == NET
-    assert choose([NET, USB], "file:///dev/usb/lp9") == USB         # nicht mehr da
+    assert choose([NET, USB], "file:///dev/usb/lp9") is None        # gewählter fehlt: keiner
     assert choose([NET]) == NET and choose([]) is None
 
 
@@ -261,11 +261,14 @@ def test_invalid_printer_settings_fall_back(tmp_path):
     assert len(loaded.warnings) == 4
 
 
-def test_fallback_model_comes_before_the_last_one(tmp_path):
+def test_saved_label_survives_another_model(tmp_path):
+    """Wer zwei Drucker abwechselnd nutzt, behält sein Etikett – ob es passt, prüft GUI/CLI."""
     path = tmp_path / "s.json"
-    save_settings(Settings(printer_model="QL-700", last_model="QL-1100", label_id="102"), path)
-    loaded = load_settings(path)                    # 102 kann der QL-700 nicht
-    assert loaded.label_id == "62" and loaded.warnings
+    save_settings(Settings(printer_model="QL-700", last_model="QL-600", label_id="102"), path)
+    loaded = load_settings(path)
+    assert loaded.label_id == "102" and loaded.warnings == []
+    path.write_text('{"label_id": "pt12"}')
+    assert load_settings(path).label_id == "62"         # P-touch-Band: kein QL-Etikett
 
 
 # --- Nachbesserungen nach dem Review --------------------------------------------------------------
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 448270a..0e6089e 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -64,8 +64,8 @@ def test_new_document_uses_settings():
 import pytest
 
 
-@pytest.mark.parametrize("label", ["102", "62red"])
-def test_label_not_in_model_list_falls_back(tmp_path, label):
+@pytest.mark.parametrize("label", ["pt12", "gibt-es-nicht", 62])
+def test_unknown_label_falls_back(tmp_path, label):
     path = tmp_path / "s.json"
     path.write_text(json.dumps({"label_id": label}))
     s = load_settings(path)
@@ -73,6 +73,15 @@ def test_label_not_in_model_list_falls_back(tmp_path, label):
     assert len(s.warnings) == 1
 
 
+@pytest.mark.parametrize("label", ["102", "62red"])
+def test_label_of_another_printer_is_kept(tmp_path, label):
+    """Ob das Etikett zum angeschlossenen Drucker passt, prüfen GUI und CLI (zwei Drucker)."""
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps({"label_id": label}))
+    s = load_settings(path)
+    assert s.label_id == label and s.warnings == []
+
+
 def test_unreadable_config_dir_gives_warning_not_exception(tmp_path, monkeypatch):
     from pathlib import Path
 
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_printers.py) schlagen fehl (fehlende Attribute), außerdem angepasste Tests (Erkennung über `usb_printers` in test_gui_media/test_gui_window, Fake-Worker mit `printer`, `choose`/Etikett-Regeln in tests/test_printers.py und tests/test_settings.py); alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 5682642..5f0056d 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -32,14 +32,20 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   Inhalt = schraffierter Platzhalter auf der Arbeitsfläche (wählbar, Meldung, kein Druck); {Spalte} der Serie auch im
   Inhalt (Prüfhinweis und Anfasser rechnen mit der Vorschau-Zeile); Doppelklick/F2/Enter → Inhaltsfeld (Strg+Z dort =
   Rückgängig des Etiketts).
+- Drucker-Kompatibilität (Roadmap 6): Modell automatisch erkannt (IEEE-1284-Kennung, USB-Produktname, Produkt-ID),
+  alle QL aus brother_ql inkl. 102 mm; Statusleiste: Druckerknopf mit Auswahl (Automatisch, gefundene, Netzwerkdrucker
+  eintragen), „ungeprüft“ für andere Modelle; Modellwechsel: Etiketten, Längen, Schnitt (ohne Abschneider ausgeblendet),
+  Farbe; Netzwerkdrucker per IP in den Einstellungen (Medium prüfen nur USB); Rot/Schwarz je Objekt (Reiter Layout →
+  Farbe, nur 62red auf QL-8xx, ungeprüft); CLI -m/-l auto, labelwerk printers; Referenztests je Modell (tests/golden).
 - Datei und Favoriten (Etappe 3c): Reiter DATEI – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“); `labelwerk install-desktop` meldet *.labelwerk an (Doppelklick öffnet).
-- 2238 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- 2337 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
 src/labelwerk/
-  labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager);
-              filtert für QL-600: >62 mm, PT-Bänder, Rot/Schwarz-Etiketten
+  labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager): labels_for_model nach
+              printers.capabilities (Breite, restricted_to_models, ohne PT-Bänder, 62red nur Zweifarb-Modelle);
+              Label.two_color
   render.py   render_text(text, label_id, size_pt, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
               render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
               compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise:
@@ -84,6 +90,11 @@ src/labelwerk/
               Teil cancelled() → PrintCancelled(printed, total) (kein PrintError), nach jedem progress(k, N); to_print_mode (1 Bit, bitgleich
               zur Schwelle von brother_ql: 100 − THRESHOLD %)
   detect.py   find_brother_lp() -> "file:///dev/usb/lpN" | None
+  printers.py Drucker ohne Qt: Printer(uri, model, name, source usb|network), usb_printers() (sysfs: IEEE-1284 „MDL:“,
+              product, idProduct → PRODUCT_IDS; SYS_ROOT in Tests leer), network_printers(NetworkEntry), choose (gewählt –
+              fehlt er: None, kein Ersatz; automatisch: USB mit Modell › USB › erster), printer_for(uri) (usb://…:0xPID → Modell), effective_model (erkannt › Ersatz ›
+              zuletzt › QL-600), capabilities(model) (cutter, two_color, max_tape_mm 62/104, length_limits, tested),
+              SUPPORTED_MODELS (QL ohne PT), TESTED_MODELS, backend_for(uri)
   document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit);
               TextObject: Position x_mm/y_mm (None = mittig wie bisher), Rahmen w_mm/h_mm (mit fit), Drehen rotation 0/90/180/270
               ImageObject: png (Farboriginal), source/page/crop, Rahmen x/y/w/h_mm immer gesetzt, rotation, mode/threshold/invert,
@@ -211,7 +222,8 @@ src/labelwerk/
 ```
 Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.
 
-Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`), `pillow>=10.1`, `pypdfium2>=4`,
+Abhängigkeiten: `brother_ql-inventree>=1.3,<1.4` (GPLv3+, Import als `brother_ql`; Referenztests hashen die
+Rasterdaten – neue Version erst nach `tools/golden.py`), `pillow>=10.1`, `pypdfium2>=4`,
 `openpyxl>=3.1` (MIT, Excel), `defusedxml>=0.7` (PSF, sicheres XML für openpyxl), `segno>=1.5` (BSD-3-Clause, QR);
 nur Entwicklung: `zxing-cpp` (Apache-2.0, liest Barcodes in Tests; ab Python 3.12). Build: hatchling, src-Layout.
 
@@ -246,8 +258,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Drucker-Kompatibilität (6, Antworten stehen: 1a 2b 3a 4b ungetestet 5a 6a 7a 8a 9a),
-Fremdhersteller (6b), Übersetzungen (7), Paketierung (8).
+Nächste Schritte: Fremdhersteller (6b), Übersetzungen (7), Paketierung (8).
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -273,7 +284,8 @@ Umsetzung:
    - Bilder (PNG/JPG/SVG) als Objekt aufs Etikett, Umwandlung in Schwarz/Weiß
    - Fertiges Bild/PDF 1:1 drucken, ohne Editor (auch per CLI)
    - P-touch-Etiketten (.lbx = ZIP mit XML): Text, Rahmen, Barcodes, Bilder übernehmen
-6. Drucker-Kompatibilität (vor Veröffentlichung, QL-Familie):
+6. Drucker-Kompatibilität (vor Veröffentlichung, QL-Familie) – umgesetzt (Spec 2026-10-19-drucker-kompatibilitaet;
+   ungeprüft bis auf QL-600, Rückmeldungen sammeln):
    - Modell automatisch erkennen (USB-Produkt-ID, z. B. `20c0` → QL-600; sonst Statusabfrage) + Modell-Feld in den Einstellungen als Rückfallebene; alle festen „QL-600“-Annahmen (GUI, Einstellungen, Etikettenliste, Medium prüfen, `DEFAULT_MODEL`) lesen das Modell aus einer Quelle.
    - Fähigkeiten statt Modellnamen: Etiketten, Breite, Abschneider, Zweifarbdruck, Mindestlänge aus `brother_ql` (`ModelsManager`, `LabelsManager`).
    - Golden-Tests je Modell: Testetikett → Rasterdaten mit Referenz vergleichen (beweist, was gesendet wird – nicht, was gedruckt wird).
diff --git a/README.md b/README.md
index 460b021..b8479a9 100644
--- a/README.md
+++ b/README.md
@@ -4,6 +4,22 @@ Etiketten gestalten und drucken auf **Brother-QL-Druckern unter Linux** – ohne
 
 Getestet mit: QL-600 (USB). Andere QL-Modelle sollten funktionieren, Rückmeldungen willkommen.
 
+## Welche Drucker funktionieren?
+
+| Stand | Drucker |
+|---|---|
+| **geprüft** | QL-600 mit DK-22205 (62 mm endlos), USB |
+| **sollte funktionieren** (ungeprüft) | QL-500, QL-550, QL-560, QL-570, QL-580N, QL-650TD, QL-700, QL-710W, QL-720NW, QL-800, QL-810W, QL-820NWB – Etiketten bis 62 mm, USB oder Netzwerk |
+| **sollte funktionieren** (ungeprüft) | breite Modelle QL-1050, QL-1060N, QL-1100, QL-1110NWB, QL-1115NWB – Etiketten bis 102/104 mm |
+| **ungeprüft** | Rot/Schwarz-Druck (QL-8xx mit DK-22251 „62red“): Farbe je Objekt im Reiter Layout |
+| **nicht unterstützt** | P-touch-Bandgeräte (PT-…), Drucker anderer Hersteller |
+
+labelwerk erkennt das Modell des angeschlossenen Druckers selbst (`labelwerk printers` zeigt, was es
+findet); Etiketten, Abschneider und Farben richten sich danach. Wird ein Modell nicht erkannt, lässt
+es sich in den Einstellungen festlegen. Netzwerkdrucker (WLAN/LAN-Modelle) trägst du in den
+Einstellungen mit IP-Adresse ein; „Medium prüfen“ geht nur per USB. Hast du ein ungeprüftes Modell
+ausprobiert, freue ich mich über eine Rückmeldung (Issue mit Modell, Rolle und Ergebnis).
+
 ## Installation
 
 ```bash
@@ -29,12 +45,14 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62x29 --preview vorschau.png
 labelwerk print "X1 -K3\nKlemme 24V" -l 62x29      # drucken (Drucker wird automatisch erkannt)
 labelwerk print-file internetmarke.pdf -l 62       # PDF/PNG/JPG 1:1 drucken
 labelwerk media                                            # eingelegte Rolle anzeigen (druckt nichts)
+labelwerk printers                                         # gefundene Drucker und unterstützte Modelle
+labelwerk print "Regal 4" -l auto                          # Etikett nach der eingelegten Rolle
 labelwerk fonts                                            # installierte Schriften
 labelwerk print "Max Mustermann\nMusterstr. 5" --align left --font-family "Liberation Sans" -s 14
 labelwerk print "Max Mustermann\nMusterstr. 5\n12345 Musterstadt" --orientation horizontal -s 19
 ```
 
-Optionen: `-s` Schriftgröße (`auto` oder 8–400), `--font` eigene TTF, `-b pyusb` alternatives USB-Backend, `--no-cut`.
+Optionen: `-s` Schriftgröße (`auto` oder 8–400), `--font` eigene TTF, `-m QL-700` Modell (Standard: erkannt), `-p tcp://IP` Netzwerkdrucker, `-b pyusb` alternatives USB-Backend, `--no-cut`.
 `print-file` schneidet auf den Inhalt zu (Schnittmarken, z. B. der Internetmarke, und Leerraum fallen weg), dreht bei Bedarf und druckt 1:1; `--rotate 0|90|180|270` legt die Drehung fest (Grad im Uhrzeigersinn), `--fit` verkleinert zu große Motive, `--page N` wählt die PDF-Seite. Internetmarke quer wie im PDF: `--rotate 0 --fit`.
 
 ## Grafische Oberfläche
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index a49c92c..161a31f 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -20,7 +20,7 @@ from . import image_import
 from ..labels import DPI, Label, format_mm, length_limits
 from ..layout import Rect
 from ..printer import DEFAULT_MODEL
-from ..render import PT, RenderedObject
+from ..render import INK, PT, RenderedObject
 
 MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm
 RULER = 22               # Linealbreite in Pixeln
@@ -45,11 +45,13 @@ _EDIT_REACH_PX = 3                # Schreibmodus: Klick so knapp neben dem Rahme
 _SELECTION_ALPHA = 90             # Markierung: Systemfarbe zu ≈ 35 % deckend
 
 
-def to_qimage(img: Image.Image) -> QImage:
-    """Druckbild als QImage; Weiß wird transparent, damit die Etikettform sichtbar bleibt."""
+def to_qimage(img: Image.Image, ink: tuple[int, int, int] = (0, 0, 0)) -> QImage:
+    """Druckbild als QImage; Weiß wird transparent, damit die Etikettform sichtbar bleibt.
+    ``ink``: Druckfarbe (``render.INK``, rote Objekte auf Etiketten Rot/Schwarz)."""
     gray = img.convert("L")
-    # Immer schwarz, Alpha = 255 - L: über Weiß ergibt das exakt den Grauwert L (Vorschau = Druck)
-    rgba = Image.merge("RGBA", (*(Image.new("L", gray.size, 0),) * 3, ImageOps.invert(gray)))
+    # Farbe der Tinte, Alpha = 255 - L: über Weiß ergibt das exakt den Ton L (Vorschau = Druck)
+    rgba = Image.merge("RGBA", (*(Image.new("L", gray.size, c) for c in ink),
+                                ImageOps.invert(gray)))
     return QImage(rgba.tobytes(), rgba.width, rgba.height, 4 * rgba.width,
                   QImage.Format.Format_RGBA8888).copy()
 
@@ -123,8 +125,7 @@ class Canvas(QGraphicsView):
         self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
         self.viewport().setMouseTracking(True)             # Mauszeiger über den Anfassern
         self.setAcceptDrops(True)                          # Bilder und Bilddateien ablegen
-        min_len, max_len = length_limits(model)
-        self.min_mm, self.max_mm = min_len / MM, max_len / MM
+        self.set_model(model)
         self.zoom = START_ZOOM
         self.orientation = "vertical"
         self._scale = 1.0
@@ -278,6 +279,11 @@ class Canvas(QGraphicsView):
         leer bei gestanzten Etiketten."""
         return QRectF(self._tape)
 
+    def set_model(self, model: str) -> None:
+        """Druckermodell: Grenzen der Etikettlänge beim Ziehen."""
+        min_len, max_len = length_limits(model)
+        self.min_mm, self.max_mm = min_len / MM, max_len / MM
+
     def cut_edges(self) -> list[str]:
         """Kanten in Bandrichtung mit Schnittlinie: bei Endlosband nur das Ende („end“) –
         der Anfang ist geschlossen; gestanzte Etiketten behalten ihre Darstellung (leer)."""
@@ -290,7 +296,7 @@ class Canvas(QGraphicsView):
         cached = self._pixmaps.get(id(rendered))
         if cached is not None and cached[0] is rendered:
             return cached[1]
-        return QPixmap.fromImage(to_qimage(rendered.image))
+        return QPixmap.fromImage(to_qimage(rendered.image, INK[rendered.color]))
 
     # --- Auswahl ----------------------------------------------------------
     def selection(self) -> list[int]:
diff --git a/src/labelwerk/gui/file_session.py b/src/labelwerk/gui/file_session.py
index c1e4b0a..ee540ef 100644
--- a/src/labelwerk/gui/file_session.py
+++ b/src/labelwerk/gui/file_session.py
@@ -190,7 +190,21 @@ class FileSession(QObject):
             loaded = self.window.panel("paper").media_label
             if loaded is not None:
                 doc.label_id = loaded
+            wanted = doc.label_id
+            doc.label_id = self.fitting_label(wanted)
             self._replace(doc, None)
+            if doc.label_id != wanted:
+                self.window._set_result(f"Etikett „{wanted}“ passt nicht zum {self.window.model} – "
+                                        f"{doc.label_id} genommen", "warn")
+
+    def fitting_label(self, label_id: str) -> str:
+        """``label_id``, wenn es zum Drucker passt, sonst die eingelegte Rolle, sonst 62 mm endlos
+        bzw. das erste Etikett des Modells."""
+        fitting = [label.id for label in labels_for_model(self.window.model)]
+        for candidate in (label_id, self.window.panel("paper").media_label, "62"):
+            if candidate in fitting:
+                return candidate
+        return fitting[0]
 
     def open(self, path: str | None = None, ask: bool = True) -> bool:
         """Datei öffnen (ohne ``path``: Dialog); Fehler → Statusleiste, Etikett bleibt."""
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index ea87e34..9f544e4 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -13,17 +13,19 @@ from PySide6.QtCore import QMimeData, Qt, QThreadPool, QTimer
 from PySide6.QtGui import QAction, QActionGroup, QIcon
 from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFileDialog, QFrame,
                                QHBoxLayout, QInputDialog, QLineEdit,
-                               QLabel, QMainWindow, QMessageBox, QPushButton,
+                               QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
                                QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                                QWidget)
 
 from .. import barcodes, clipart, favorites, series
 from ..desktop import APP_NAME
-from ..detect import brother_busy, find_brother_lp
+from ..detect import brother_busy
+from ..printers import (UNTESTED_HINT, Printer, capabilities, choose, effective_model,
+                        network_printers, usb_printers)
 from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, Series, TextObject
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
-from ..labels import DPI, get_label
+from ..labels import DPI, get_label, labels_for_model
 from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, fill_anchored,
                       frame_area, growing_axis, insert_placement, match_objects, maximize_object,
                       move, new_barcode, object_rect, objects_outside, outside_indices,
@@ -31,7 +33,7 @@ from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect,
 from ..printer import DEFAULT_MODEL, cut_interval, to_print_mode
 from ..render import (Renderer, RenderedObject, font_warnings, render_document,
                       set_svg_rasterizer)
-from ..settings import Settings, load_settings, new_document, save_settings
+from ..settings import Settings, load_settings, network_entries, new_document, save_settings
 from ..shortcuts import effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
@@ -89,13 +91,19 @@ def shrunk_hint(factor: float, mode: str) -> str:
 
 class MainWindow(QMainWindow):
     def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
-                 model: str = DEFAULT_MODEL, settings: Settings | None = None):
+                 model: str | None = None, settings: Settings | None = None):
+        """``model``: Druckermodell fest vorgeben; None = erkannt (``refresh_printer``), bis dahin
+        Ersatzmodell bzw. zuletzt erkanntes aus den Einstellungen."""
         super().__init__()
         self.setWindowTitle(APP_NAME)
         self.resize(1100, 700)
         self.settings = settings if settings is not None else load_settings(model=model)
         self.doc = doc if doc is not None else new_document(self.settings)
-        self.model = model
+        self._fixed_model = model is not None
+        self.model = model or effective_model(None, self.settings.printer_model,
+                                              self.settings.last_model)
+        self.printers: list[Printer] = []           # gefundene Drucker (USB, Netzwerk)
+        self.printer: Printer | None = None         # gewählter bzw. erster gefundener
         self.image = None
         self._shown_size = (0, 0)                   # Etikettgröße der letzten gültigen Anzeige
         self._structure_dirty = False               # Objektliste seit der letzten Anzeige umgebaut
@@ -176,7 +184,7 @@ class MainWindow(QMainWindow):
         toolbar.widgetForAction(self.print_action).setObjectName("print")
 
         # Arbeitsfläche
-        self.canvas = Canvas(model)
+        self.canvas = Canvas(self.model)
         self.canvas.set_zoom(self.settings.start_zoom)
         self.canvas.length_changed.connect(self._on_length_dragged)
         self.canvas.drag_finished.connect(self._length_drag_finished)
@@ -220,8 +228,14 @@ class MainWindow(QMainWindow):
         layout.addWidget(self.canvas, 1)
         self.setCentralWidget(central)
 
-        # Statusleiste: Drucker, Ergebnis, Zoom
-        self.printer_status = QLabel()
+        # Statusleiste: Drucker (Knopf mit Auswahl), Ergebnis, Zoom
+        self.printer_status = QToolButton()
+        self.printer_status.setObjectName("printerChoice")
+        self.printer_status.setAutoRaise(True)
+        self.printer_status.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
+        self.printer_menu = QMenu(self.printer_status)
+        self.printer_menu.aboutToShow.connect(self._fill_printer_menu)
+        self.printer_status.setMenu(self.printer_menu)
         self.result = QLabel()
         self.result.setTextFormat(Qt.TextFormat.PlainText)   # Namen mit „<b>“ bleiben Text
         self.statusBar().addWidget(self.printer_status)
@@ -253,6 +267,9 @@ class MainWindow(QMainWindow):
         self._timer.setInterval(RENDER_DELAY_MS)
         self._timer.timeout.connect(self.render_now)
         self.panel("paper").check_media_requested.connect(self.check_media)
+        self.panel("paper").set_model(self.model)      # Panels entstehen mit dem Standardmodell
+        self.panel("series").set_cutter(capabilities(self.model).cutter)
+        self.panel("layout").color_chosen.connect(self.set_color_selected)
         self.panel("paper").media_status_changed.connect(self._show_media_status)
         self._printer_timer = QTimer(self)
         self._printer_timer.setInterval(PRINTER_POLL_MS)
@@ -282,6 +299,7 @@ class MainWindow(QMainWindow):
         self.panel("barcode").fill_preview = self._filled_barcode
         self._clipboard_changed()
         self.refresh_printer()
+        self._fit_label()                           # Standard-Etikett eines anderen Druckers
         if self.settings.warnings or key_warnings:
             self._set_result(" · ".join(self.settings.warnings + key_warnings), "error")
 
@@ -571,6 +589,9 @@ class MainWindow(QMainWindow):
                                  grow=growing_axis(self.doc), keep_aspect=aspect,
                                  frame=result.frame, inner=self._inner)
         self.panel("layout").set_growing(growing_axis(self.doc))
+        red = get_label(self.doc.label_id).two_color and capabilities(self.model).two_color
+        self.panel("layout").set_red_available(red)
+        self.panel("barcode").red_available = red
         self._update_frame()
         self.panel("barcode").update_check()        # Serie: Prüfhinweis zur Vorschau-Zeile
         self.edit_session.update_marks()            # Schreibmarke zum neuen Zeilensatz
@@ -943,6 +964,10 @@ class MainWindow(QMainWindow):
             return replace(changed, data=obj.data)
         return changed
 
+    def set_color_selected(self, color: str) -> None:
+        """Farbe der Auswahl (Reiter Layout; Rot nur auf Etiketten Rot/Schwarz)."""
+        self._change_selected(lambda objs, rendered: [replace(obj, color=color) for obj in objs])
+
     def reorder_selected(self, step: int) -> None:
         """Auswahl einen Platz nach vorne (1) bzw. hinten (−1); die Auswahl wandert mit."""
         self.finish_editing()
@@ -1414,19 +1439,50 @@ class MainWindow(QMainWindow):
 
     # --- Drucken ----------------------------------------------------------
     def refresh_printer(self) -> None:
-        """Statusleiste aktualisieren; beim Erscheinen des Druckers ggf. Medium prüfen."""
+        """Drucker suchen (USB in sysfs, eingetragene Netzwerkdrucker), den gewählten bzw. ersten
+        nehmen, sein Modell übernehmen (``set_model``), Statusleiste aktualisieren; beim
+        Erscheinen eines USB-Druckers ggf. Medium prüfen."""
+        tip = ""
         try:
-            printer = find_brother_lp()
-            if printer:
-                text = f"● {self.model} · {Path(printer).name}"
-            elif brother_busy():
-                text = "● Drucker belegt (andere Anwendung)"
-            else:
-                text = "○ kein Drucker"
+            found = usb_printers() + network_printers(network_entries(self.settings))
+            busy = not any(p.source == "usb" for p in found) and brother_busy()
         except OSError:
-            printer, text = None, "○ Druckerstatus unbekannt"
+            found, busy = None, False
+        chosen = choose(found or [], self.settings.printer)
+        switched = (self.printer is not None and chosen is not None
+                    and chosen.uri != self.printer.uri)
+        self.printers, self.printer = found or [], chosen
+        if found is None:
+            text = "○ Druckerstatus unbekannt"
+        elif chosen is None and self.settings.printer:
+            text = "○ gewählter Drucker fehlt"
+            tip = f"{self.settings.printer} nicht gefunden – einschalten oder einen anderen wählen"
+        elif chosen is not None:
+            text = f"● {chosen.name}"
+            if chosen.model is None:
+                text += f" (als {self.model})"
+                tip = "Modell nicht erkannt – in den Einstellungen ein Ersatzmodell wählen"
+            elif not capabilities(chosen.model).tested:
+                text += " · ungeprüft"
+                tip = f"{chosen.model}: {UNTESTED_HINT}"
+        elif busy:
+            text = "● Drucker belegt (andere Anwendung)"
+        else:
+            text = "○ kein Drucker"
         self.printer_status.setText(text)
-        present = printer is not None
+        self.printer_status.setToolTip(tip or "Drucker wählen")
+        if chosen is not None and chosen.model and chosen.model != self.settings.last_model:
+            self.settings.last_model = chosen.model     # gilt beim nächsten Start ohne Drucker
+            self._save_settings()
+        if not self._fixed_model:
+            model = effective_model(chosen, self.settings.printer_model, self.settings.last_model)
+            if model != self.model:
+                self.set_model(model)
+        self._update_media_button()
+        if switched:                                # andere Rolle möglich: neu prüfen
+            self.panel("paper").clear_media()
+            self._printer_present = False
+        present = chosen is not None and chosen.source == "usb"
         if present and not self._printer_present and self.settings.check_media_on_start:
             self._media_check_pending = True
         if not present:
@@ -1436,6 +1492,62 @@ class MainWindow(QMainWindow):
         self._printer_present = present
         self._run_pending_media_check()
 
+    def _usb_uri(self) -> str | None:
+        """Gewählter USB-Drucker (Medium prüfen); None = selbst suchen."""
+        return self.printer.uri if self.printer is not None and self.printer.source == "usb" else None
+
+    def _fill_printer_menu(self) -> None:
+        """Menü am Druckerknopf: Automatisch, gefundene Drucker, Netzwerkdrucker eintragen."""
+        menu = self.printer_menu
+        menu.clear()
+        auto = menu.addAction("Automatisch (erster gefundener)")
+        auto.setCheckable(True)
+        auto.setChecked(not self.settings.printer)
+        auto.triggered.connect(lambda _=False: self.choose_printer(""))
+        for printer in self.printers:
+            untested = printer.model is not None and not capabilities(printer.model).tested
+            action = menu.addAction(printer.name + (" – ungeprüft" if untested else ""))
+            action.setCheckable(True)
+            action.setChecked(printer.uri == self.settings.printer)
+            action.setToolTip(UNTESTED_HINT if untested else printer.uri)
+            action.triggered.connect(lambda _=False, uri=printer.uri: self.choose_printer(uri))
+        if not self.printers:
+            menu.addAction("Kein Drucker gefunden").setEnabled(False)
+        menu.addSeparator()
+        menu.addAction("Netzwerkdrucker eintragen …", self.open_settings)
+
+    def choose_printer(self, uri: str) -> None:
+        """Drucker wählen (URI; "" = automatisch) – gespeichert."""
+        self.settings.printer = uri
+        self._save_settings()
+        self.refresh_printer()
+
+    def set_model(self, model: str) -> None:
+        """Druckermodell gewechselt: Etiketten, Längen, Schnitt und Farben folgen; das offene
+        Etikett bleibt – passt es nicht, steht das in der Statusleiste."""
+        self.model = model
+        self.canvas.set_model(model)
+        self.panel("paper").set_model(model)
+        self.panel("series").set_cutter(capabilities(model).cutter)
+        self._fit_label()
+        self.schedule_render()
+
+    def _fit_label(self) -> None:
+        """Passt das Etikett nicht zum Modell: ein neues, unberührtes Etikett nimmt ein passendes
+        (``FileSession.fitting_label``), sonst bleibt es mit Hinweis (Datei, Favorit, Änderungen)."""
+        label = self.doc.label_id
+        if label in {lbl.id for lbl in labels_for_model(self.model)}:
+            return
+        if self.files.may_follow_roll() and not self.files.modified():
+            self.doc.label_id = self.files.fitting_label(label)
+            self.panel("paper").refresh()
+            self.files.mark_unchanged()
+            self._set_result(f"Etikett {get_label(label).description} passt nicht zum {self.model} "
+                             f"– {get_label(self.doc.label_id).description} genommen", "warn")
+            return
+        self._set_result(f"Etikett {get_label(label).description} passt nicht zum Drucker "
+                         f"({self.model}) – im Reiter Papier ein anderes wählen", "error")
+
     def _run_pending_media_check(self) -> None:
         """Automatische Prüfung nachholen, sobald weder Druck noch Prüfung laufen."""
         if self._media_check_pending and not self.is_printing() and not self.is_checking_media():
@@ -1485,7 +1597,10 @@ class MainWindow(QMainWindow):
         saved = dialog.saved
         dialog.deleteLater()                    # nicht bis zum Schließen des Fensters behalten
         if accepted and saved is not None:
+            # während der Dialog offen war, kann sich Drucker/letztes Modell geändert haben
+            saved.printer, saved.last_model = self.settings.printer, self.settings.last_model
             self.settings = saved
+            self._save_settings()
             from PySide6.QtWidgets import QApplication
             from .app import apply_theme
             apply_theme(QApplication.instance(), self.settings.theme)
@@ -1493,6 +1608,7 @@ class MainWindow(QMainWindow):
             apply_shortcuts(self.shortcut_actions,
                             without_conflicts(effective(self.settings.shortcuts))[0])
             self.files.refresh_lists()                  # „Beim Start“ im Reiter Datei
+            self.refresh_printer()                      # Netzwerkdrucker, Ersatzmodell
             self._set_result("Einstellungen gespeichert – gelten für neue Etiketten.", "ok")
 
     # --- Medium prüfen ----------------------------------------------------
@@ -1505,7 +1621,7 @@ class MainWindow(QMainWindow):
     def check_media(self) -> None:
         if self.is_printing() or self.is_checking_media():
             return
-        worker = MediaWorker(self.model)
+        worker = MediaWorker(self.model, self._usb_uri())
         self._media_signals = worker.signals
         worker.signals.found.connect(self._media_found)
         worker.signals.failed.connect(self._media_failed)
@@ -1619,6 +1735,7 @@ class MainWindow(QMainWindow):
         images, outside = [], []
         doc = copy.deepcopy(doc)                    # Eingaben während des Vorbereitens zählen nicht
         renderer = Renderer()                       # unveränderte Objekte aus dem Cache
+        red = get_label(doc.label_id).two_color and capabilities(self.model).two_color
         self._set_printing(True)                    # gesperrt, solange vorbereitet wird
         self._cancel_requested = False
         self.cancel_button.setVisible(len(rows) > 1)
@@ -1638,7 +1755,7 @@ class MainWindow(QMainWindow):
                     return
                 if outside_indices(result.objects, result.size, doc.objects):
                     outside.append(number)
-                images.append(to_print_mode(result.image))   # 1 Bit: wenig Speicher
+                images.append(to_print_mode(result.image, red))   # 1 Bit: wenig Speicher
         finally:
             self._set_printing(False)
             self.cancel_button.hide()
@@ -1698,6 +1815,10 @@ class MainWindow(QMainWindow):
         if self.is_checking_media():
             self._set_result("Rolle wird gerade geprüft – bitte gleich noch einmal drucken.", "error")
             return
+        if self.printer is None and self.settings.printer:
+            self._set_result("Gewählter Drucker nicht gefunden – einschalten oder in der "
+                             "Statusleiste einen anderen wählen.", "error")
+            return
         # Druck sperrt die Medium-Prüfung schon vor dem Dialog (Timer läuft währenddessen weiter)
         self._set_printing(True)
         if doc.is_empty() and not self.confirm_empty():
@@ -1709,7 +1830,8 @@ class MainWindow(QMainWindow):
         self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
         self.result.style().polish(self.result)
         self.result.setText("Drucke …")
-        worker = PrintWorker(image, doc.label_id, self.model, cut_every)
+        worker = PrintWorker(image, doc.label_id, self.model, cut_every,
+                             printer=self.printer.uri if self.printer else None)
         self._print_signals = worker.signals  # Referenz bis zum Ende des Drucks
         self._worker = worker
         worker.signals.done.connect(self._print_done)
@@ -1732,12 +1854,22 @@ class MainWindow(QMainWindow):
         self._printing = printing
         self.print_action.setEnabled(not printing)
         self.panel("file").set_printing(printing)
-        self.panel("paper").check.setEnabled(not printing)
+        self._update_media_button()
+
+    def _update_media_button(self) -> None:
+        """„Medium prüfen“ geht nur per USB und nicht während eines Drucks."""
+        network = self.printer is not None and self.printer.source == "network"
+        check = self.panel("paper").check
+        check.setEnabled(not self._printing and not network and not self.is_checking_media())
+        check.setToolTip("Medium prüfen geht nur bei Druckern per USB" if network
+                         else "Eingelegte Rolle vom Drucker abfragen (druckt nichts)")
 
     def _print_done(self, status: dict) -> None:
         ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
         self.result.setProperty("state", "ok" if ok else "error")
-        self.result.setText("Gedruckt ✓" if ok else f"Status: {status.get('outcome')}")
+        sent_only = status.get("outcome") == "sent" and not status.get("did_print")
+        self.result.setText(("Gesendet ✓ (der Drucker meldet keinen Status zurück)" if sent_only
+                             else "Gedruckt ✓") if ok else f"Status: {status.get('outcome')}")
         self._print_finished()
 
     def _print_cancelled(self, message: str) -> None:
diff --git a/src/labelwerk/gui/media_worker.py b/src/labelwerk/gui/media_worker.py
index 3a5708c..1b5486b 100644
--- a/src/labelwerk/gui/media_worker.py
+++ b/src/labelwerk/gui/media_worker.py
@@ -13,14 +13,15 @@ class MediaSignals(QObject):
 
 
 class MediaWorker(QRunnable):
-    def __init__(self, model: str):
+    def __init__(self, model: str, printer: str | None = None):
         super().__init__()
         self.model = model
+        self.printer = printer                     # URI des gewählten USB-Druckers; None = suchen
         self.signals = MediaSignals()
 
     def run(self) -> None:
         try:
-            printer = find_brother_lp()
+            printer = self.printer or find_brother_lp()
             if printer is None:
                 self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
                 return
diff --git a/src/labelwerk/gui/panels/barcode.py b/src/labelwerk/gui/panels/barcode.py
index c595437..49428bf 100644
--- a/src/labelwerk/gui/panels/barcode.py
+++ b/src/labelwerk/gui/panels/barcode.py
@@ -97,6 +97,7 @@ class BarcodePanel(Panel):
         self.index: int | None = None   # bearbeiteter Barcode; None = keiner ausgewählt
         # Serie: Barcode mit dem Wert der Vorschau-Zeile (Hauptfenster), für den Prüfhinweis
         self.fill_preview: Callable[[BarcodeObject], BarcodeObject] | None = None
+        self.red_available = False      # Etikett und Drucker können Rot (Hinweis nur dann)
         self._updating = False
         self._typing = False            # Inhalt wird gerade getippt (ein Rückgängig-Schritt)
 
@@ -294,7 +295,9 @@ class BarcodePanel(Panel):
             self._set_check(f"Mit Prüfziffer: {completed}" if completed and completed != given
                             else "")
         side = "ringsum" if obj.kind == "qr" else "links und rechts je"
-        self.quiet.setText(f"Ruhezone: {side} {_mm(barcodes.quiet_mm(obj))} mm frei lassen")
+        red = (" · Rot lesen viele Scanner schlecht" if obj.color == "red" and self.red_available
+               else "")
+        self.quiet.setText(f"Ruhezone: {side} {_mm(barcodes.quiet_mm(obj))} mm frei lassen{red}")
 
     def _set_check(self, text: str) -> None:
         self.check.setText(text)
diff --git a/src/labelwerk/gui/panels/layout.py b/src/labelwerk/gui/panels/layout.py
index 636c417..98303ae 100644
--- a/src/labelwerk/gui/panels/layout.py
+++ b/src/labelwerk/gui/panels/layout.py
@@ -5,8 +5,9 @@ gerechnet wird im Kern (``layout``). Ohne passende Auswahl sind die Knöpfe gesp
 """
 from __future__ import annotations
 
+from PySide6.QtCore import Signal
 from PySide6.QtGui import QAction
-from PySide6.QtWidgets import QHBoxLayout, QToolButton
+from PySide6.QtWidgets import QHBoxLayout, QPushButton, QToolButton
 
 from ...document import Document
 from ..symbols import SIZE, line_icon
@@ -34,13 +35,18 @@ _PAPER_AXIS = {f"align.paper_{mode}": axis for axis, modes in
                for mode in modes}
 GROWING_HINT = ("Bei automatischer Länge wächst das Etikett mit – "
                 "das Objekt sitzt mit gleichem Rand an beiden Enden")
+COLOR_TITLES = (("black", "SCHWARZ"), ("red", "ROT"))
+NO_RED = "Rot nur auf dem Etikett 62 mm Rot/Schwarz (DK-22251) mit einem QL-8xx"
 
 
 class LayoutPanel(Panel):
+    color_chosen = Signal(str)          # Farbe für die Auswahl ("black" | "red")
+
     def __init__(self, doc: Document):
         super().__init__(doc, "Layout")
         self._dark = True
         self._count = 0
+        self._red = False               # Etikett kann Rot
         self._grow: str | None = None
         self.buttons: dict[str, QToolButton] = {}
         for title, row in LAYOUT_SECTIONS:
@@ -59,7 +65,17 @@ class LayoutPanel(Panel):
                 line.addWidget(button)
             line.addStretch()
             self.layout_.addLayout(line)
+        self.section("Farbe")
+        line = QHBoxLayout()
+        self.colors: dict[str, QPushButton] = {}
+        for color, title in COLOR_TITLES:
+            button = QPushButton(title)
+            button.clicked.connect(lambda _=False, c=color: self.color_chosen.emit(c))
+            self.colors[color] = button
+            line.addWidget(button)
+        self.layout_.addLayout(line)
         self.layout_.addStretch()
+        self._enable()
 
     def use_actions(self, actions: dict[str, QAction]) -> None:
         for key, button in self.buttons.items():
@@ -71,6 +87,12 @@ class LayoutPanel(Panel):
         self._count = len(indices)
         self._enable()
 
+    def set_red_available(self, available: bool) -> None:
+        """Kann das Etikett Rot (62red auf einem Zweifarb-Modell)? Sonst sind die Farben gesperrt."""
+        if available != self._red:
+            self._red = available
+            self._enable()
+
     def set_growing(self, axis: str | None) -> None:
         """Achse, in der das Etikett mitwächst (``layout.growing_axis``): dort sitzt das
         Objekt beim Ausrichten am Papier am Randanfang (Hinweis im Tooltip)."""
@@ -79,6 +101,9 @@ class LayoutPanel(Panel):
             self._enable()
 
     def _enable(self) -> None:
+        for color, button in self.colors.items():          # Schwarz geht immer (zurück)
+            button.setEnabled(self._count > 0 and (self._red or color == "black"))
+            button.setToolTip("" if self._red or color == "black" else NO_RED)
         for key, button in self.buttons.items():
             target = button.defaultAction() or button
             growing = _PAPER_AXIS.get(key) == self._grow and self._grow is not None
diff --git a/src/labelwerk/gui/panels/paper.py b/src/labelwerk/gui/panels/paper.py
index a548a4a..bb4deea 100644
--- a/src/labelwerk/gui/panels/paper.py
+++ b/src/labelwerk/gui/panels/paper.py
@@ -61,15 +61,8 @@ class PaperPanel(Panel):
 
         self.section("Etikett")
         self.combo = QComboBox()
-        labels = labels_for_model(model)
-        for shape, title in _GROUPS:
-            group = [lbl for lbl in labels if lbl.shape == shape]
-            if not group:
-                continue
-            self.combo.addItem(f"— {title} —")
-            self.combo.model().item(self.combo.count() - 1).setEnabled(False)
-            for lbl in group:
-                self.combo.addItem(lbl.description, lbl.id)
+        self.model = model
+        self._fill_labels()
         self.layout_.addWidget(self.combo)
         self.check = QPushButton("MEDIUM PRÜFEN")
         self.check.setToolTip("Eingelegte Rolle vom Drucker abfragen (druckt nichts)")
@@ -85,8 +78,7 @@ class PaperPanel(Panel):
         self.length.setSuffix(" mm")
         self.length.setDecimals(1)
         self.length.setSingleStep(0.5)
-        min_len, max_len = length_limits(model)
-        self.length.setRange(round(min_len * 25.4 / DPI, 1), round(max_len * 25.4 / DPI, 1))
+        self._set_length_range()
         self.length.setValue(50.0)
         row.addWidget(self.length_auto)
         row.addWidget(self.length)
@@ -176,8 +168,51 @@ class PaperPanel(Panel):
         self.changed.emit()
         self.edited.emit()           # jede Rahmen-Änderung ist ein eigener Schritt
 
+    def set_model(self, model: str) -> None:
+        """Druckermodell gewechselt: Etiketten und Längengrenzen folgen; das Etikett des Dokuments
+        bleibt (passt es nicht, steht es mit Hinweis in der Liste)."""
+        if model == self.model:
+            return
+        self.model = model
+        for w in self._widgets():
+            w.blockSignals(True)
+        self._fill_labels()
+        self._set_length_range()
+        for w in self._widgets():
+            w.blockSignals(False)
+        self.refresh()
+
+    def _fill_labels(self) -> None:
+        """Etiketten des Modells nach Form gruppiert; ein Etikett des Dokuments, das das Modell
+        nicht kann, bleibt sichtbar („passt nicht zum …“), damit nichts still umgestellt wird."""
+        self.combo.clear()
+        labels = labels_for_model(self.model)
+        for shape, title in _GROUPS:
+            group = [lbl for lbl in labels if lbl.shape == shape]
+            if not group:
+                continue
+            self.combo.addItem(f"— {title} —")
+            self.combo.model().item(self.combo.count() - 1).setEnabled(False)
+            for lbl in group:
+                self.combo.addItem(lbl.description, lbl.id)
+        self._unfit = None
+        if self.combo.findData(self.doc.label_id) < 0:      # gewählt bleibt es, wählbar nicht
+            self._unfit = self.doc.label_id
+            self.combo.addItem(f"{get_label(self.doc.label_id).description} – passt nicht zum "
+                               f"{self.model}", self.doc.label_id)
+            self.combo.model().item(self.combo.count() - 1).setEnabled(False)
+
+    def _set_length_range(self) -> None:
+        min_len, max_len = length_limits(self.model)
+        self.length.setRange(round(min_len * 25.4 / DPI, 1), round(max_len * 25.4 / DPI, 1))
+
     def _apply(self) -> None:
         self.doc.label_id = self.combo.currentData()
+        if self._unfit is not None and self._unfit != self.doc.label_id:
+            self.combo.blockSignals(True)
+            self._fill_labels()                      # Eintrag „passt nicht“ verschwindet
+            self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
+            self.combo.blockSignals(False)
         self.media_adjusted = False   # Auswahl ist jetzt vom Nutzer
         self.doc.length_mm = None if self.length_auto.isChecked() else self.length.value()
         self.doc.margin_mm = self.margin.value()
@@ -190,6 +225,9 @@ class PaperPanel(Panel):
     def refresh(self) -> None:
         for w in self._widgets():
             w.blockSignals(True)
+        if self.combo.findData(self.doc.label_id) < 0 or (
+                self._unfit is not None and self._unfit != self.doc.label_id):
+            self._fill_labels()          # andere Datei bzw. passendes Etikett: Liste neu
         self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
         self.length_auto.setChecked(self.doc.length_mm is None)
         if self.doc.length_mm is not None:
diff --git a/src/labelwerk/gui/panels/series.py b/src/labelwerk/gui/panels/series.py
index ad9e1fc..c5f6e9d 100644
--- a/src/labelwerk/gui/panels/series.py
+++ b/src/labelwerk/gui/panels/series.py
@@ -25,6 +25,7 @@ from . import Panel
 NO_SERIES = "Keine Serie"
 NUMBERING = "Nummerierung"
 CUT_TITLES = {"each": "Nach jedem Etikett", "end": "Nur am Ende"}
+NO_CUTTER = "Drucker ohne Abschneider – Etiketten von Hand abtrennen"
 SHOWN_COLUMNS = 3                   # Spalten in der Zeilentabelle (die Häkchen sitzen in der ersten)
 ROWS_HEIGHT = 180
 
@@ -118,7 +119,7 @@ class SeriesPanel(Panel):
         row.addWidget(self.next_button)
         self.layout_.addLayout(row)
 
-        self.section("Schnitt")
+        self.cut_title = self.section("Schnitt")
         self.cut = QComboBox()
         for mode in CUTS:
             self.cut.addItem(CUT_TITLES[mode], mode)
@@ -126,6 +127,11 @@ class SeriesPanel(Panel):
                             "(Endlosband: zwischen den Etiketten bleiben einige mm Vorschub, "
                             "ohne Trennmarke)")
         self.layout_.addWidget(self.cut)
+        self.no_cutter = QLabel(NO_CUTTER)
+        self.no_cutter.setObjectName("hint")
+        self.no_cutter.setWordWrap(True)
+        self.no_cutter.hide()
+        self.layout_.addWidget(self.no_cutter)
         self.layout_.addStretch()
 
         self.table_button.clicked.connect(self.table_requested)
@@ -324,6 +330,12 @@ class SeriesPanel(Panel):
         self._field_error = None
         self.set_series(replace(value, numbering=numbering))
 
+    def set_cutter(self, cutter: bool) -> None:
+        """Drucker mit bzw. ohne Abschneider: ohne gibt es keine Schnitt-Auswahl, nur den Hinweis."""
+        self.cut_title.setVisible(cutter)
+        self.cut.setVisible(cutter)
+        self.no_cutter.setVisible(not cutter)
+
     def _apply_cut(self) -> None:
         if self.doc.series is not None:
             self.set_series(replace(self.doc.series, cut=self.cut.currentData()))
diff --git a/src/labelwerk/gui/print_worker.py b/src/labelwerk/gui/print_worker.py
index cc85614..824db56 100644
--- a/src/labelwerk/gui/print_worker.py
+++ b/src/labelwerk/gui/print_worker.py
@@ -19,13 +19,14 @@ class PrintSignals(QObject):
 
 class PrintWorker(QRunnable):
     """``image``: ein Etikett oder eine Liste (Serie, ein Auftrag); ``cut_every``: schneiden
-    alle n Etiketten (``printer.cut_interval``). ``cancel()`` (aus dem GUI-Thread) bricht vor dem
-    nächsten Teilauftrag ab."""
+    alle n Etiketten (``printer.cut_interval``); ``printer``: URI des gewählten Druckers (USB oder
+    Netzwerk). ``cancel()`` (aus dem GUI-Thread) bricht vor dem nächsten Teilauftrag ab."""
 
     def __init__(self, image: Image.Image | list[Image.Image], label_id: str, model: str,
-                 cut_every: int = 1):
+                 cut_every: int = 1, printer: str | None = None):
         super().__init__()
         self.image, self.label_id, self.model = image, label_id, model
+        self.printer = printer                     # URI; None = USB-Drucker selbst suchen
         self.cut_every = cut_every
         self.signals = PrintSignals()
         self._cancel = threading.Event()
@@ -35,7 +36,7 @@ class PrintWorker(QRunnable):
 
     def run(self) -> None:
         try:
-            printer = find_brother_lp()
+            printer = self.printer or find_brother_lp()
             if printer is None:
                 self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
                 return
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index b9d6026..cfa9c00 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -10,16 +10,18 @@ from pathlib import Path
 from PySide6.QtCore import QSize, Qt
 from PySide6.QtGui import QColor, QFont, QKeySequence
 from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
-                               QDialogButtonBox, QFontComboBox, QFormLayout, QGroupBox,
+                               QDialogButtonBox, QFontComboBox, QFormLayout, QFrame, QGroupBox,
                                QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QPushButton,
-                               QStyledItemDelegate, QTableWidget, QTableWidgetItem, QTabWidget,
+                               QScrollArea, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
+                               QTabWidget,
                                QVBoxLayout, QWidget)
 
 from .. import favorites, shortcuts
 from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
-from ..labels import labels_for_model
+from ..labels import get_label, labels_for_model
 from ..printer import DEFAULT_MODEL
-from ..settings import Settings, save_settings
+from ..printers import SUPPORTED_MODELS, capabilities
+from ..settings import Settings, save_settings, valid_host
 from .widgets import DoubleSpinBox, SpinBox
 
 SCOPE_NAMES = {"global": "Global", "canvas": "Arbeitsfläche", "edit": "Schreibmodus"}
@@ -45,17 +47,25 @@ class SettingsDialog(QDialog):
         self.saved: Settings | None = None
         self._symbols = (settings.symbols_recent, settings.symbols_favorites)   # nur durchgereicht
         self._recent_files = settings.recent_files                             # nur durchgereicht
+        self._printer, self._last_model = settings.printer, settings.last_model   # nur durchgereicht
         outer = QVBoxLayout(self)
         self.tabs = QTabWidget()
         outer.addWidget(self.tabs)
         general = QWidget()
-        self.tabs.addTab(general, "Allgemein")
+        scroll = QScrollArea()                   # Drucker-Liste macht den Reiter hoch: rollen statt quetschen
+        scroll.setWidget(general)
+        scroll.setWidgetResizable(True)
+        scroll.setFrameShape(QFrame.Shape.NoFrame)
+        self.tabs.addTab(scroll, "Allgemein")
         layout = QVBoxLayout(general)
 
         form = self._section(layout, "Neues Etikett")
         self.label = QComboBox()
         for lbl in labels_for_model(model):
             self.label.addItem(lbl.description, lbl.id)
+        if self.label.findData(settings.label_id) < 0:    # anderer Drucker: nicht still ersetzen
+            self.label.addItem(f"{get_label(settings.label_id).description} – passt nicht zum "
+                               f"{model}", settings.label_id)
         self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
         form.addRow("Etikett", self.label)
         self.orientation = QComboBox()
@@ -115,6 +125,32 @@ class SettingsDialog(QDialog):
         self.check_media = QCheckBox("Rolle beim Start und beim Einschalten prüfen")
         self.check_media.setChecked(settings.check_media_on_start)
         form.addRow(self.check_media)
+        self.printer_model = _model_combo("Automatisch (erkannt)")
+        self.printer_model.setCurrentIndex(max(0, self.printer_model.findData(settings.printer_model)))
+        self.printer_model.setToolTip("Nur nötig, wenn labelwerk das Modell nicht erkennt "
+                                      "(gilt dann und ohne angeschlossenen Drucker)")
+        form.addRow("Druckermodell", self.printer_model)
+        self.network = QTableWidget(0, 3)
+        self.network.setHorizontalHeaderLabels(["Name", "Adresse", "Modell"])
+        self.network.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
+        self.network.verticalHeader().hide()
+        self.network.setMinimumHeight(110)
+        for entry in settings.network_printers:
+            self._add_network(entry["name"], entry["host"], entry["model"])
+        buttons = QHBoxLayout()
+        self.add_network = QPushButton("HINZUFÜGEN")
+        self.add_network.clicked.connect(lambda: self._add_network("", "", "QL-720NW"))
+        self.remove_network = QPushButton("ENTFERNEN")
+        self.remove_network.clicked.connect(
+            lambda: self.network.removeRow(self.network.currentRow())
+            if self.network.currentRow() >= 0 else None)
+        buttons.addWidget(self.add_network)
+        buttons.addWidget(self.remove_network)
+        buttons.addStretch()
+        box = QVBoxLayout()
+        box.addWidget(self.network)
+        box.addLayout(buttons)
+        form.addRow("Netzwerkdrucker", box)
 
         form = self._section(layout, "Ansicht")
         self.zoom = SpinBox()
@@ -285,6 +321,33 @@ class SettingsDialog(QDialog):
         self.conflict_hint.setVisible(bool(found))
         self.save_button.setEnabled(not found)
 
+    def _add_network(self, name: str, host: str, model: str) -> None:
+        row = self.network.rowCount()
+        self.network.insertRow(row)
+        self.network.setItem(row, 0, QTableWidgetItem(name))
+        self.network.setItem(row, 1, QTableWidgetItem(host))
+        combo = _model_combo(None)
+        combo.setCurrentIndex(max(0, combo.findData(model)))
+        self.network.setCellWidget(row, 2, combo)
+
+    def _network_values(self) -> list[dict] | None:
+        """Netzwerkdrucker aus der Tabelle; leere Zeilen entfallen; None bei ungültiger Adresse
+        (Hinweis steht dann im Dialog)."""
+        entries = []
+        for row in range(self.network.rowCount()):
+            name = (self.network.item(row, 0) or QTableWidgetItem()).text().strip()
+            host = (self.network.item(row, 1) or QTableWidgetItem()).text().strip()
+            if not name and not host:
+                continue
+            if not valid_host(host):
+                self.error.setText(f"Netzwerkdrucker {name or row + 1}: Adresse „{host}“ ungültig – "
+                                   "nur IP-Adresse oder Name, ohne „tcp://“ und Port")
+                self.error.show()
+                return None
+            entries.append({"name": name, "host": host,
+                            "model": self.network.cellWidget(row, 2).currentData()})
+        return entries
+
     def _family_changed(self, _font) -> None:
         self._family_touched = True
 
@@ -305,6 +368,10 @@ class SettingsDialog(QDialog):
             symbols_favorites=list(self._symbols[1]),
             recent_files=list(self._recent_files),
             start_favorite=self.start_favorite.currentData(),
+            printer=self._printer,
+            printer_model=self.printer_model.currentData(),
+            last_model=self._last_model,
+            network_printers=self._network_values() or [],
             shortcuts={action_id: seq for action_id, seq in self._keys.items()
                        if not _same(seq, shortcuts.action(action_id).default)},
         )
@@ -312,6 +379,8 @@ class SettingsDialog(QDialog):
     def accept(self) -> None:
         if not self.save_button.isEnabled():
             return                                   # Kürzel doppelt belegt (Hinweis steht da)
+        if self._network_values() is None:
+            return                                   # Adresse ungültig (Hinweis steht da)
         settings = self.values()
         try:
             save_settings(settings, self.path)
@@ -323,6 +392,16 @@ class SettingsDialog(QDialog):
         super().accept()
 
 
+def _model_combo(automatic: str | None) -> QComboBox:
+    """Druckermodelle (ungeprüfte gekennzeichnet); ``automatic``: erster Eintrag mit Wert ""."""
+    combo = QComboBox()
+    if automatic is not None:
+        combo.addItem(automatic, "")
+    for model in SUPPORTED_MODELS:
+        combo.addItem(model if capabilities(model).tested else f"{model} – ungeprüft", model)
+    return combo
+
+
 class _KeyDelegate(QStyledItemDelegate):
     """Spalte „Kürzel“: Bearbeiten mit ``QKeySequenceEdit`` – genau eine Tastenkombination,
     ✕ leert. Esc bricht ab (die Tabelle schließt den Editor ohne Übernahme)."""
diff --git a/src/labelwerk/printers.py b/src/labelwerk/printers.py
index c9d1a42..e0a9d6c 100644
--- a/src/labelwerk/printers.py
+++ b/src/labelwerk/printers.py
@@ -139,12 +139,12 @@ def network_printers(entries: list[NetworkEntry]) -> list[Printer]:
 
 
 def choose(printers: list[Printer], wanted: str = "") -> Printer | None:
-    """Der gewählte Drucker (URI aus den Einstellungen; "" = automatisch) bzw. der erste gefundene
-    USB-Drucker mit erkanntem Modell (ein Brother-Laser auf lp0 soll keine QL-Daten bekommen), dann
-    der erste USB-Drucker, sonst der erste überhaupt; None = keiner."""
-    for p in printers:
-        if wanted and p.uri == wanted:
-            return p
+    """Der gewählte Drucker (URI aus den Einstellungen) – fehlt er, None: gedruckt wird nicht auf
+    einem anderen als dem gewählten. Automatisch (""): der erste gefundene USB-Drucker mit erkanntem
+    Modell (ein Brother-Laser auf lp0 soll keine QL-Daten bekommen), dann der erste USB-Drucker,
+    sonst der erste überhaupt; None = keiner."""
+    if wanted:
+        return next((p for p in printers if p.uri == wanted), None)
     usb = [p for p in printers if p.source == "usb"]
     known = [p for p in usb if p.model is not None]
     return (known or usb or printers or [None])[0]
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 1bbae8f..efaeac6 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -50,8 +50,10 @@ def _is_int(v) -> bool:
     return isinstance(v, int) and not isinstance(v, bool)
 
 
-def _rules(model: str) -> dict:
-    known = {lab.id for lab in labels_for_model(model)}
+def _rules(model: str | None = None) -> dict:
+    """Prüfregeln; das Etikett muss ein bekanntes sein – ob es zum Drucker passt, prüfen GUI und
+    CLI erst mit dem erkannten Modell (wer zwei Drucker abwechselnd nutzt, behält sein Etikett)."""
+    known = {lab.id for m in SUPPORTED_MODELS for lab in labels_for_model(m)}
     return {
         "label_id": lambda v: isinstance(v, str) and v in known,
         "orientation": lambda v: v in ORIENTATIONS,
@@ -76,7 +78,7 @@ def _rules(model: str) -> dict:
     }
 
 
-_KEYS = (*_rules("QL-600"), "shortcuts")
+_KEYS = (*_rules(), "shortcuts")
 
 
 def settings_path() -> Path:
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2337 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md src/labelwerk/gui/canvas.py src/labelwerk/gui/file_session.py src/labelwerk/gui/main_window.py src/labelwerk/gui/media_worker.py src/labelwerk/gui/panels/barcode.py src/labelwerk/gui/panels/layout.py src/labelwerk/gui/panels/paper.py src/labelwerk/gui/panels/series.py src/labelwerk/gui/print_worker.py src/labelwerk/gui/settings_dialog.py src/labelwerk/printers.py src/labelwerk/settings.py tests/gui/conftest.py tests/gui/test_gui_barcode.py tests/gui/test_gui_cancel.py tests/gui/test_gui_files.py tests/gui/test_gui_media.py tests/gui/test_gui_printers.py tests/gui/test_gui_series.py tests/gui/test_gui_window.py tests/test_printers.py tests/test_settings.py
git commit -m "GUI: Druckerwahl in der Statusleiste, Modell folgt dem Drucker (Etiketten, Längen, Schnitt), Netzwerkdrucker und Ersatzmodell in den Einstellungen, Farbe Schwarz/Rot im Reiter Layout, README-Tabelle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Abnahme (manuell, durch den Nutzer)

- [ ] Statusleiste zeigt „● QL-600 · lp1“; Menü am Druckerknopf: Automatisch, Drucker, Netzwerkdrucker eintragen.
- [ ] `labelwerk printers` listet den QL-600 als geprüft; `labelwerk print "Test" -l auto --preview x.png` nimmt die eingelegte Rolle.
- [ ] Einstellungen: Druckermodell (Ersatz) und Netzwerkdrucker eintragen/entfernen; ungültige Adresse wird gemeldet.
- [ ] Reiter Layout: Farbe nur Schwarz wählbar (QL-600); Probedruck wie bisher unverändert (Referenztests).
