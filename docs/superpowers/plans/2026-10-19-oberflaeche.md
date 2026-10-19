# Oberfläche – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reiter lassen sich in den Einstellungen ausblenden (DATEI/PAPIER fest); Öffnen-Dialoge zeigen eine Vorschau (Bilder, SVG, PDF mit Seitenwahl, Etiketten, Tabellen); wahlweise Dateiauswahl des Systems (XDG-Portal).

**Architecture:** Einstellungen im Kern (`settings.py`), Oberfläche in `main_window.py`, `settings_dialog.py` und dem neuen `gui/file_dialog.py`; Vorschau-Lesen im Hintergrund-Thread.

**Tech Stack:** Python ≥ 3.10, Pillow, pypdfium2, brother_ql-inventree 1.3.x, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-19-oberflaeche-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-ob-lin`), nach jedem Task volle Suite grün mit Exit-Code 0 (2680 → 2709 → 2762); jeder Teil von einem Reviewer geprüft und korrigiert, danach ein Gesamtreview (in Task 2 enthalten).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Kern bleibt **Qt-frei** (`labels.py`, `render.py`, `layout.py`, `fonts.py`, `settings.py`, `cups.py`, `printers.py`, `cli.py`); kein Test erreicht echte Hardware, CUPS oder das Netz (`cups._run` ist in tests/conftest.py ersetzt); **nie den echten Drucker ansprechen**; keine echte Einstellungsdatei (conftest lenkt `XDG_CONFIG_HOME` um).
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten, ohne echte Dialoge; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen englisch mit `_()`, Deutsch in `po/de.po` (in den Patches enthalten); Kommentare deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Reiter ausblenden

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-19-oberflaeche-design.md`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/settings.py`
- Create: `tests/gui/test_gui_hidden_tools.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `settings.hidden_tools`, `HIDEABLE_TOOLS` (gleich mit gui/tools.py), QUIET; Einstellungsdialog → Ansicht „Reiter in der Leiste“ (`tool_boxes`, DATEI/PAPIER gesperrt, `tools_note`), ausgeblendete im Start-Reiter gesperrt; `MainWindow.apply_hidden_tools(fall_back=)`, `_tool_visible`/`_tool_needed` (SERIE bei Serie oder Schnitt-Optionen), Rückfall bei leerer Auswahl, `_start_tool`/`_remember_tool` überspringen ausgeblendete.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_hidden_tools.py b/tests/gui/test_gui_hidden_tools.py
new file mode 100644
index 0000000..f0b208f
--- /dev/null
+++ b/tests/gui/test_gui_hidden_tools.py
@@ -0,0 +1,266 @@
+"""Reiter ausblenden (Einstellung „Reiter in der Leiste“): DATEI und PAPIER bleiben immer, Objekte
+ausgeblendeter Reiter bleiben bearbeitbar, Tastenkürzel wirken weiter."""
+from PySide6.QtWidgets import QApplication
+
+from labelwerk.document import BarcodeObject, Document, TextObject
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.gui.settings_dialog import SettingsDialog
+from labelwerk.gui.tools import TOOLS
+from labelwerk.settings import HIDEABLE_TOOLS, Settings
+
+from test_gui_cups import queue  # noqa: F401  (Fixture: CUPS-Warteschlangen Dymo/Laser)
+from test_gui_printers import workers  # noqa: F401  (Fixture)
+
+
+def _window(qtbot, objects=None, **settings):
+    win = MainWindow(doc=Document("62", objects=objects or [TextObject("A")]),
+                     settings=Settings(check_media_on_start=False, **settings))
+    qtbot.addWidget(win)
+    win.show()
+    return win
+
+
+def _checked(win) -> list[str]:
+    """Hervorgehobene Knöpfe in der Leiste (ausgeblendete zählen nicht – man sieht sie nicht)."""
+    return [key for key, action in win.tool_actions.items()
+            if action.isChecked() and action.isVisible()]
+
+
+def test_hideable_tools_are_all_tools_but_file_and_paper():
+    assert list(HIDEABLE_TOOLS) == [t.key for t in TOOLS if t.key not in ("file", "paper")]
+
+
+def test_hidden_tools_have_no_button(qtbot):
+    win = _window(qtbot, hidden_tools=["barcode", "series"])
+    visible = {key: action.isVisible() for key, action in win.tool_actions.items()}
+    assert visible == {"file": True, "paper": True, "text": True, "image": True,
+                       "barcode": False, "layout": True, "series": False}
+
+
+def test_selecting_an_object_of_a_hidden_tool_shows_its_panel(qtbot):
+    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
+                  hidden_tools=["barcode"])
+    win.render_now()
+    win.canvas.set_selection([1])
+    QApplication.processEvents()
+    assert win.panels.currentWidget() is win.panel("barcode")
+    assert _checked(win) == []                                     # kein Knopf hervorgehoben
+    win.tool_actions["text"].trigger()                             # sichtbarer Reiter: normal
+    assert _checked(win) == ["text"] and win.panels.currentWidget() is win.panel("text")
+
+
+def test_hidden_tool_shown_by_selection_is_not_remembered(qtbot):
+    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
+                  hidden_tools=["barcode"])
+    win.tool_actions["layout"].trigger()
+    win.tool_actions["text"].trigger()
+    win.render_now()
+    win.canvas.set_selection([1])
+    QApplication.processEvents()
+    assert win.panels.currentWidget() is win.panel("barcode")
+    assert win.settings.last_tool == "text"
+
+
+def test_hidden_start_tool_starts_with_paper(qtbot):
+    win = _window(qtbot, start_tool="series", hidden_tools=["series"])
+    assert _checked(win) == ["paper"] and win.panels.currentWidget() is win.panel("paper")
+
+
+def test_hidden_last_tool_starts_with_paper(qtbot):
+    win = _window(qtbot, start_tool="last", last_tool="layout", hidden_tools=["layout"])
+    assert _checked(win) == ["paper"]
+
+
+def test_shortcuts_of_hidden_tools_keep_working(qtbot):
+    win = _window(qtbot, hidden_tools=["barcode"])
+    win.shortcut_actions["barcode.insert"].trigger()
+    assert any(isinstance(obj, BarcodeObject) for obj in win.doc.objects)
+    assert win.panels.currentWidget() is win.panel("barcode") and _checked(win) == []
+
+
+def test_hiding_the_current_tool_falls_back_to_paper(qtbot):
+    win = _window(qtbot)
+    win.tool_actions["series"].trigger()
+    win.settings.hidden_tools = ["series"]
+    win.apply_hidden_tools()
+    assert not win.tool_actions["series"].isVisible()
+    assert _checked(win) == ["paper"] and win.panels.currentWidget() is win.panel("paper")
+
+
+def test_showing_tools_again(qtbot):
+    win = _window(qtbot, hidden_tools=["text", "image"])
+    win.settings.hidden_tools = []
+    win.apply_hidden_tools()
+    assert all(action.isVisible() for action in win.tool_actions.values())
+
+
+def test_settings_dialog_has_a_checkbox_per_tool(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(hidden_tools=["series"]), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    boxes = dialog.tool_boxes
+    assert list(boxes) == [t.key for t in TOOLS]
+    for key in ("file", "paper"):
+        assert boxes[key].isChecked() and not boxes[key].isEnabled()
+    assert not boxes["series"].isChecked() and boxes["text"].isChecked()
+    boxes["barcode"].setChecked(False)
+    boxes["series"].setChecked(True)
+    assert dialog.values().hidden_tools == ["barcode"]
+
+
+def test_saving_settings_applies_hidden_tools_immediately(qtbot, monkeypatch):
+    win = _window(qtbot)
+
+    class FakeDialog:
+        DialogCode = SettingsDialog.DialogCode
+
+        def __init__(self, settings, **kw):
+            self.saved = Settings(**{**vars(settings), "hidden_tools": ["layout"]})
+
+        def exec(self):
+            return SettingsDialog.DialogCode.Accepted
+
+        def deleteLater(self):
+            pass
+
+    from labelwerk.gui import main_window as mw
+    monkeypatch.setattr(mw, "SettingsDialog", FakeDialog)
+    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: None)
+    monkeypatch.setattr(win, "_save_settings", lambda *keys: None)
+    win.open_settings()
+    assert not win.tool_actions["layout"].isVisible()
+
+
+# --- SERIE erscheint, solange sie gebraucht wird -----------------------------------
+def test_series_button_appears_while_the_label_has_a_series(qtbot):
+    from labelwerk.document import Numbering, Series
+    win = _window(qtbot, hidden_tools=["series"])
+    win.render_now()
+    assert not win.tool_actions["series"].isVisible()
+    win.doc.series = Series(numbering=Numbering(count=3))
+    win.render_now()
+    assert win.tool_actions["series"].isVisible()
+    win.doc.series = None
+    win.render_now()
+    assert not win.tool_actions["series"].isVisible()
+
+
+def test_series_button_visible_for_a_file_with_a_series(qtbot):
+    from labelwerk.document import Numbering, Series
+    win = _window(qtbot, objects=[TextObject("Nr {Nummer}")], hidden_tools=["series"])
+    win.doc.series = Series(numbering=Numbering(count=2))
+    win.render_now()
+    assert win.tool_actions["series"].isVisible()
+
+
+def test_series_button_visible_with_driver_cut_options(qtbot, monkeypatch, queue, workers):
+    from test_gui_printers import _window as printer_window
+    win = printer_window(qtbot, monkeypatch, [], printer="cups:Dymo", hidden_tools=["series"])
+    assert win.panel("series").driver_cuts
+    assert win.tool_actions["series"].isVisible()
+    win.choose_printer("cups:Laser")                               # Treiber ohne Schnitt-Option
+    assert not win.tool_actions["series"].isVisible()
+
+
+def test_settings_dialog_explains_that_series_can_appear(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    assert dialog.tools_note.objectName() == "note" and "Serie" in dialog.tools_note.text()
+
+
+# --- Nach SPEICHERN nur zurückfallen, wenn nötig -----------------------------------
+def _save_with(win, monkeypatch, **changes):
+    class FakeDialog:
+        DialogCode = SettingsDialog.DialogCode
+
+        def __init__(self, settings, **kw):
+            self.saved = Settings(**{**vars(settings), **changes})
+
+        def exec(self):
+            return SettingsDialog.DialogCode.Accepted
+
+        def deleteLater(self):
+            pass
+
+    from labelwerk.gui import main_window as mw
+    monkeypatch.setattr(mw, "SettingsDialog", FakeDialog)
+    monkeypatch.setattr(win, "_save_settings", lambda *keys: None)
+    win.open_settings()
+
+
+def test_saving_other_settings_keeps_the_panel_of_the_selection(qtbot, monkeypatch):
+    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
+                  hidden_tools=["barcode"])
+    win.render_now()
+    win.canvas.set_selection([1])
+    QApplication.processEvents()
+    _save_with(win, monkeypatch, start_zoom=150)
+    assert win.panels.currentWidget() is win.panel("barcode")
+
+
+def test_hiding_the_tool_of_the_selection_keeps_its_panel(qtbot, monkeypatch):
+    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)])
+    win.render_now()
+    win.canvas.set_selection([1])
+    QApplication.processEvents()
+    _save_with(win, monkeypatch, hidden_tools=["barcode"])
+    assert win.panels.currentWidget() is win.panel("barcode")
+
+
+def test_hiding_text_keeps_the_edit_mode(qtbot, monkeypatch):
+    win = _window(qtbot)
+    win.render_now()
+    win.edit_text(0)
+    assert win.edit_session.active
+    _save_with(win, monkeypatch, hidden_tools=["text"])
+    assert win.edit_session.active and win.panels.currentWidget() is win.panel("text")
+
+
+# --- Auswahl leer → zurück zu einem sichtbaren Reiter ------------------------------
+def test_empty_selection_leaves_a_hidden_panel(qtbot):
+    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
+                  hidden_tools=["barcode", "text"])
+    win.tool_actions["layout"].trigger()
+    win.tool_actions["image"].trigger()                            # zuletzt benutzt: BILD
+    win.render_now()
+    win.canvas.set_selection([1])
+    QApplication.processEvents()
+    assert win.panels.currentWidget() is win.panel("barcode")
+    win.canvas.set_selection([])
+    QApplication.processEvents()
+    assert win.panels.currentWidget() is win.panel("image") and _checked(win) == ["image"]
+    assert win.canvas.tool() == "select"
+
+
+def test_empty_selection_without_a_last_tool_goes_to_paper(qtbot):
+    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
+                  hidden_tools=["barcode", "text"])
+    win.render_now()
+    win.canvas.set_selection([0])
+    QApplication.processEvents()
+    assert win.panels.currentWidget() is win.panel("text")
+    win.canvas.set_selection([])
+    QApplication.processEvents()
+    assert win.panels.currentWidget() is win.panel("paper")
+    assert win.canvas.tool() == "select"                           # kein „Text anlegen“
+
+
+# --- Einstellungsdialog: Reiter beim Start folgt den Häkchen -----------------------
+def _enabled(combo, key) -> bool:
+    return combo.model().item(combo.findData(key)).isEnabled()
+
+
+def test_hidden_tools_are_disabled_as_start_tab(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(hidden_tools=["series"]), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    combo = dialog.start_tool
+    assert not _enabled(combo, "series") and _enabled(combo, "text") and _enabled(combo, "last")
+    dialog.tool_boxes["series"].setChecked(True)
+    assert _enabled(combo, "series")
+
+
+def test_hiding_the_start_tab_switches_to_last_used(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(start_tool="barcode"), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    dialog.tool_boxes["barcode"].setChecked(False)
+    assert dialog.start_tool.currentData() == "last"
+    assert dialog.values().start_tool == "last"
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 4506ba0..32b7c9f 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -493,3 +493,33 @@ def test_update_settings_cleans_invalid_and_old_keys(tmp_path):
     assert data["theme"] == base.theme == "rawblock"
     assert data["zukunft"] == 1 and data["last_tool"] == "text"
     assert load_settings(path).warnings == []
+
+
+# --- Reiter ausblenden --------------------------------------------------------------
+def test_hidden_tools_default_and_roundtrip(tmp_path):
+    from labelwerk.settings import HIDEABLE_TOOLS
+    assert Settings().hidden_tools == [] and "file" not in HIDEABLE_TOOLS
+    path = tmp_path / "s.json"
+    save_settings(Settings(hidden_tools=["series", "barcode"]), path)
+    loaded = load_settings(path)
+    assert loaded.hidden_tools == ["series", "barcode"] and loaded.warnings == []
+
+
+@pytest.mark.parametrize("raw, expected", [
+    (["file", "paper", "series"], ["series"]),          # DATEI/PAPIER bleiben immer
+    (["druck", 3, None, "text", "text"], ["text"]),     # Unbekanntes, Doppeltes
+    ("series", []), (None, []), ({"a": 1}, []),
+])
+def test_invalid_hidden_tools_are_dropped_quietly(tmp_path, raw, expected):
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps({"hidden_tools": raw}))
+    s = load_settings(path)
+    assert s.hidden_tools == expected and s.warnings == []
+
+
+def test_update_settings_cleans_hidden_tools(tmp_path):
+    from labelwerk.settings import update_settings
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps({"hidden_tools": ["paper", "layout"]}))
+    update_settings(path, Settings(), last_tool="text")
+    assert json.loads(path.read_text())["hidden_tools"] == ["layout"]
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_hidden_tools.py, Fälle in tests/test_settings.py) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 1266a99..c7a23ea 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -51,7 +51,9 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   CLI `--lang` (auch argparse-Texte); Zahlen mit dem Dezimaltrenner der Sprache (Eingabe Komma und Punkt),
   Excel-Zahlen im Etikett nach der Region des Systems; `{Nummer}`/`{Number}` und „Spalte n“/„Column n“ in
   jeder Sprache; Symbole mit deutschen und englischen Namen (Suche in beiden); Layout-Test je Sprache.
-- Einstellungen: Reiter beim Start (fest oder zuletzt benutzter), Standard für neue Bilder (Strich/Foto, Schwelle).
+- Einstellungen: Reiter beim Start (fest oder zuletzt benutzter), Standard für neue Bilder (Strich/Foto, Schwelle),
+  Reiter ausblenden (Ansicht → „Reiter in der Leiste“; DATEI/PAPIER immer; Objekte ausgeblendeter Reiter bleiben
+  bearbeitbar – Auswahl zeigt ihr Panel, Tastenkürzel wirken).
 - Schriftliste (Abnahme-Korrekturen): nur Schriften mit deutschen Zeichen, ohne Kopien (Powerline/Nerd Font),
   Symbol-/Farbschriften und CJK-Regionsvarianten, jede in ihrer Schrift (FontCombo statt QFontComboBox, keine
   Qt-Sammelnamen wie „Sans Serif“); Einstellung „Alle Schriften zeigen“ (`fonts_all`, sofort), CLI `fonts --all`;
@@ -61,7 +63,7 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   gewählte bleibt sichtbar).
 - Stilles Speichern (Zuletzt geöffnet/verwendet, Favoriten, gewählter Drucker, letzter Reiter) schreibt nur sein
   Feld (`settings.update_settings`) – was eine zweite Instanz gespeichert hat, bleibt.
-- 2680 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- 2709 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -165,6 +167,7 @@ src/labelwerk/
               `image_threshold` (Bilder einfügen: Zuschnitt, Drehen, Strich/Foto, Schwelle neuer Bilder; Symbole nicht),
               `start_tool` (Reiter beim Start: START_TOOLS = „last“ + Werkzeug-Schlüssel, gleich mit gui/tools.py TOOLS – Test)/
               `last_tool` (zuletzt benutzter Reiter: GUI merkt ihn im Speicher, schreibt beim Schließen; ungültig → "" ohne Hinweis, QUIET_KEYS),
+              `hidden_tools` (ausgeblendete Reiter, nur HIDEABLE_TOOLS = alle außer file/paper; Rest still verworfen, QUIET_KEYS),
               `symbols_recent` (höchstens 24)/`symbols_favorites` (Symbol-ids), `recent_files` (höchstens 10)/`start_favorite`
               (der Einstellungsdialog reicht sie durch); Drucker: `printer` (gewählte URI, "" = automatisch), `printer_model`
               (Ersatz), `last_model` (zuletzt erkannt), `network_printers` ({name, host, model}; valid_host: IPv4/Name ohne
@@ -246,7 +249,11 @@ src/labelwerk/
                     insert_column (Reiter SERIE bleibt), _print_series (Prüfungen und ask_print_count vor dem Rendern, eigener
                     Renderer, confirm_outside_rows, 1 Bit, ein Auftrag mit cut_interval), print_document druckt Serien-Favoriten
                     ganz; start(path) (Datei bzw. Start-Favorit),
-                    print_document(doc) (anderes Etikett drucken, gleiche Rückfragen); closeEvent fragt bei Änderungen
+                    print_document(doc) (anderes Etikett drucken, gleiche Rückfragen); closeEvent fragt bei Änderungen;
+                    apply_hidden_tools(fall_back) (Knöpfe ausgeblendeter Reiter unsichtbar – SERIE bleibt, solange Serie
+                    oder Schnitt-Optionen des Druckers: _tool_visible; nach SPEICHERN nur bei geänderten hidden_tools und
+                    Panel nicht für Auswahl/Schreibmodus → zuletzt benutzter sichtbarer bzw. PAPIER; leere Auswahl ebenso;
+                    Start-Reiter und last_tool überspringen ausgeblendete)
     panels/barcode.py Reiter Barcode: Art (für den gewählten bzw. nächsten), BARCODE EINFÜGEN (Aktion barcode.insert),
                     Inhalt (textEdited live, erster Anschlag/editingFinished = ein Schritt), Prüfhinweis, Modul (ModuleSpin:
                     Punkte, angezeigt in mm), Höhe/Klartext bzw. Fehlerkorrektur, Ruhezone, Drehen, Position; focus_data
@@ -305,7 +312,9 @@ src/labelwerk/
                     Druckermodell als Ersatz, Zebra-Auflösung, Netzwerkdrucker-Tabelle mit Prüfung der Adresse und Modell
                     Brother/Zebra, „Alle CUPS-Drucker zeigen“; Etikett eines anderen Druckers bleibt; Neues Etikett: …,
                     Schriftart (FontCombo) mit „Alle Schriften zeigen“ darunter (sofort); Bilder einfügen: Zuschnitt, Drehen,
-                    Umwandlung Strich/Foto, Schwelle; Ansicht: Start-Zoom, Reiter beim Start, Design, Sprache) und
+                    Umwandlung Strich/Foto, Schwelle; Ansicht: Start-Zoom, Reiter beim Start, Reiter in der Leiste (tool_boxes, sperren
+                    ausgeblendete im Start-Reiter; tools_note),
+                    Design, Sprache) und
                     Tastenkürzel (Konflikte sperren Speichern); restart_hint neben SPEICHERN (Stand beim Start: started)
     theme/          QSS-Stylesheet (rawblock.qss)
     icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
diff --git a/README.md b/README.md
index a35e860..51a35bc 100644
--- a/README.md
+++ b/README.md
@@ -88,7 +88,7 @@ labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entf
 
 Aufbau wie im P-touch Editor: Werkzeugleiste (Datei, Papier, Text, Bild, Barcode, Layout, Serie), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Unten links steht der Drucker: ein Klick wählt einen anderen (bei mehreren) oder trägt einen Netzwerkdrucker ein; während eine Serie vorbereitet oder gedruckt wird, bricht ABBRECHEN sie ab (beim Drucken nach dem laufenden Teil, bis zu 10 Etiketten). Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.
 
-Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). Der Rand zählt ab Papierkante: Die Streifen, die der Drucker ohnehin freilässt (quer ~1,5 mm, längs zum Endlosband ~3 mm), zählen mit und sind auf der Arbeitsfläche hellgrau. Die Lineale zählen ab Papierkante, die Felder unter „Position“ ab dem bedruckbaren Bereich. Die Länge eines Endlosband-Etiketts ist das abgeschnittene Stück (Dateien älterer Versionen drucken dadurch ~6 mm kürzer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil), den Reiter beim Start (fest oder „Zuletzt benutzter“) und den Standard für neue Bilder (Strich/Foto, Schwelle); gespeichert in `~/.config/labelwerk/settings.json`.
+Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). Der Rand zählt ab Papierkante: Die Streifen, die der Drucker ohnehin freilässt (quer ~1,5 mm, längs zum Endlosband ~3 mm), zählen mit und sind auf der Arbeitsfläche hellgrau. Die Lineale zählen ab Papierkante, die Felder unter „Position“ ab dem bedruckbaren Bereich. Die Länge eines Endlosband-Etiketts ist das abgeschnittene Stück (Dateien älterer Versionen drucken dadurch ~6 mm kürzer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil), den Reiter beim Start (fest oder „Zuletzt benutzter“), welche Reiter in der Leiste stehen (DATEI und PAPIER immer; ein ausgeblendeter Reiter erscheint trotzdem, wenn du ein Objekt seiner Art anklickst, SERIE auch, solange das Etikett eine Serie hat oder der Drucker Schnitt-Optionen bietet; ohne LAYOUT erreichst du Ausrichten und Größe angleichen nur über eigene Tastenkürzel unter Einstellungen → Tastenkürzel, die Farbe Rot/Schwarz gar nicht) und den Standard für neue Bilder (Strich/Foto, Schwelle); gespeichert in `~/.config/labelwerk/settings.json`.
 
 Text: Geschrieben wird direkt auf dem Etikett. Mit dem Knopf „A“ (Text anlegen, Taste T) und einem Klick entsteht ein Rahmen, in den man sofort tippt (linksbündig ab dem Klickpunkt); ein Doppelklick auf einen Text setzt die Schreibmarke an die Klickstelle (ein einfacher Klick wählt den Rahmen nur); bei gewähltem Rahmen startet **F2** oder **Enter** den Schreibmodus mit der Schreibmarke am Textende. Im Schreibmodus markiert Ziehen Text, Doppelklick ein Wort, Umschalt+Klick erweitert; Pfeiltasten, Pos1/Ende, Entf, Enter, Strg+A/C/X/V und Strg+Z wirken auf den Text. **Esc** oder ein Klick neben den Rahmen beendet den Schreibmodus – die ganze Bearbeitung ist dann ein Schritt für Rückgängig. Ohne feste Rahmengröße wächst der Rahmen beim Tippen an der Kante seiner Textposition (links, rechts, Mitte). Die Schriftauswahl zeigt jede Schrift in ihrer Schrift und nur Schriften mit deutschen Zeichen, ohne Kopien und Symbolschriften (Einstellungen → „Alle Schriften zeigen“ zeigt alle); eine Schrift aus einer Datei, die dort fehlt, bleibt sichtbar. Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition wirken zeichenweise wie im P-touch Editor: im Schreibmodus auf die Markierung bzw. das Weitertippen, sonst auf den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.
 
diff --git a/docs/superpowers/specs/2026-10-19-oberflaeche-design.md b/docs/superpowers/specs/2026-10-19-oberflaeche-design.md
index 82bbc19..41950be 100644
--- a/docs/superpowers/specs/2026-10-19-oberflaeche-design.md
+++ b/docs/superpowers/specs/2026-10-19-oberflaeche-design.md
@@ -25,6 +25,14 @@ Prüfung mit der Abnahme.
 - **Hauptfenster:** ausgeblendete Werkzeugknöpfe unsichtbar; Auswahl eines Objekts, dessen Reiter ausgeblendet ist,
   zeigt dessen Bereich trotzdem (kein Knopf hervorgehoben); Tastenkürzel (z. B. Barcode einfügen) wirken weiter;
   Reiter beim Start bzw. zuletzt benutzter ausgeblendet → PAPIER.
+- **SERIE erscheint trotzdem**, solange sie gebraucht wird: das Etikett hat eine Serie oder der Drucker bietet
+  Schnitt-Optionen im Reiter SERIE (CUPS-Treiber, Zebra-Modus); Erläuterung im Dialog unter den Häkchen.
+- **Zurückfallen:** nach SPEICHERN nur, wenn sich die ausgeblendeten Reiter geändert haben und das gezeigte Panel
+  weder zur Auswahl noch zum Schreibmodus gehört; wird die Auswahl leer und das gezeigte Panel ist ausgeblendet →
+  zuletzt benutzter sichtbarer Reiter (sonst PAPIER), danach Werkzeug wie üblich (kein „Text anlegen“ ohne Reiter).
+- **Reiter beim Start** im Dialog: ausgeblendete Reiter gesperrt (an die Häkchen gekoppelt); wird der gewählte gerade
+  ausgeblendet → „Zuletzt benutzter“.
+- Ohne LAYOUT sind Ausrichten/Größe angleichen nur über eigene Tastenkürzel erreichbar, die Farbe nicht (README).
 
 ## 2 – Dateiauswahl mit Vorschau
 
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 3d6960e..e6a64bb 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -181,6 +181,7 @@ class MainWindow(QMainWindow):
         start = self._start_tool()
         self.tool_actions[start].setChecked(True)
         self.panels.setCurrentWidget(self._panel_by_key[start])
+        self.apply_hidden_tools()
         self.panels.currentChanged.connect(self._remember_tool)    # erst nach dem Start-Reiter
         self._stored_tool = self.settings.last_tool   # zuletzt benutzter Reiter, wie in der Datei
         self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
@@ -428,16 +429,58 @@ class MainWindow(QMainWindow):
         if wanted == "last":
             wanted = self.settings.last_tool
         for key in (wanted, START_TOOL):
-            if key in self.tool_actions:
+            if key in self.tool_actions and key not in self.settings.hidden_tools:
                 return key
         return next(iter(self.tool_actions))
 
+    def apply_hidden_tools(self, fall_back: bool = True) -> None:
+        """Ausgeblendete Reiter (Einstellung ``hidden_tools``) aus der Leiste nehmen. Ihre Panels
+        bleiben: die Auswahl eines Objekts zeigt sie trotzdem (ohne hervorgehobenen Knopf).
+        ``fall_back``: ist der gezeigte Reiter jetzt ausgeblendet und gehört nicht zur Auswahl bzw.
+        zum Schreibmodus, geht es zum zuletzt benutzten sichtbaren Reiter (sonst PAPIER)."""
+        self._update_tool_buttons()
+        current = self._current_tool()
+        if fall_back and not self._tool_visible(current) and not self._panel_in_use(current):
+            self._show_visible_tool()
+
+    def _update_tool_buttons(self) -> None:
+        """Knöpfe der Leiste nach ``hidden_tools`` – SERIE erscheint trotzdem, solange sie
+        gebraucht wird (Serie im Etikett, Schnitt-Optionen des Druckers)."""
+        for key, action in self.tool_actions.items():
+            action.setVisible(self._tool_visible(key))
+
+    def _tool_visible(self, key: str) -> bool:
+        if key not in self.settings.hidden_tools:
+            return True
+        return key == "series" and (self.doc.series is not None
+                                    or not self.panel("series").driver_box.isHidden())
+
+    def _panel_in_use(self, key: str) -> bool:
+        """Gehört das Panel zur Auswahl (Objekt seiner Art zuletzt gewählt) bzw. zum Schreibmodus?"""
+        if key == "text" and self.edit_session.active:
+            return True
+        selection = self.canvas.selection()
+        return bool(selection) and 0 <= selection[-1] < len(self.doc.objects) \
+            and _panel_for(self.doc.objects[selection[-1]]) == key
+
+    def _show_visible_tool(self) -> None:
+        """Zum zuletzt benutzten sichtbaren Reiter (sonst PAPIER) – wie ein Klick auf ihn."""
+        key = self.settings.last_tool
+        if key not in self.tool_actions or not self._tool_visible(key):
+            key = START_TOOL
+        self._tool_triggered(key)
+        self.tool_actions[key].setChecked(True)
+
+    def _current_tool(self) -> str:
+        """Schlüssel des gezeigten Panels."""
+        return next((k for k, panel in self._panel_by_key.items()
+                     if panel is self.panels.currentWidget()), "")
+
     def _remember_tool(self, _index: int = 0) -> None:
         """Gezeigten Reiter als zuletzt benutzten merken (``last_tool``) – nur im Speicher: jeder
         Klick auf ein Objekt kann den Reiter wechseln; auf die Platte kommt er beim Schließen."""
-        key = next((k for k, panel in self._panel_by_key.items()
-                    if panel is self.panels.currentWidget()), "")
-        if key:
+        key = self._current_tool()
+        if key and key not in self.settings.hidden_tools:   # nur per Auswahl gezeigt: nicht merken
             self.settings.last_tool = key
 
     def _show_tool(self, key: str) -> None:
@@ -487,6 +530,8 @@ class MainWindow(QMainWindow):
         self.history.select(self.doc, indices)
         if indices:
             self._show_object_panel()
+        elif not self._tool_visible(self._current_tool()):
+            self._show_visible_tool()               # ausgeblendeter Reiter nur für die Auswahl
         self._sync_tool()
 
     def _drop_empty_frames(self, indices: list[int]) -> list[int]:
@@ -569,6 +614,7 @@ class MainWindow(QMainWindow):
 
     def render_now(self) -> None:
         self._timer.stop()
+        self._update_tool_buttons()                 # SERIE: Serie hinzugefügt/entfernt
         self.files.update_title()                   # „•“ bei ungespeicherten Änderungen
         if self.canvas.is_dragging():   # Ziehen nicht unterbrechen – nach dem Loslassen rendern
             self._timer.start()
@@ -1609,6 +1655,7 @@ class MainWindow(QMainWindow):
             panel.set_driver_cuts((zpl.cut_option(),), chosen)
         else:
             panel.set_cutter(capabilities(self.model).cutter)
+        self._update_tool_buttons()                 # SERIE: Schnitt-Optionen des Druckers
 
     def _options_key(self) -> str:
         """Unter diesem Schlüssel stehen die Druck-Optionen in den Einstellungen: das Modell
@@ -1708,6 +1755,7 @@ class MainWindow(QMainWindow):
             if saved.printer.startswith(("tcp://", "zpl+tcp://")) and saved.printer not in {
                     p.uri for p in network_printers(network_entries(saved))}:
                 saved.printer = ""                  # Netzwerkdrucker entfernt/geändert: automatisch
+            hidden_changed = saved.hidden_tools != self.settings.hidden_tools
             self.settings = saved
             self._save_settings()
             from PySide6.QtWidgets import QApplication
@@ -1715,6 +1763,7 @@ class MainWindow(QMainWindow):
             apply_theme(QApplication.instance(), self.settings.theme)
             self.apply_theme_icons()
             self.apply_font_list()
+            self.apply_hidden_tools(fall_back=hidden_changed)
             apply_shortcuts(self.shortcut_actions,
                             without_conflicts(effective(self.settings.shortcuts))[0])
             self.files.refresh_lists()                  # „Beim Start“ im Reiter Datei
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 7a871ee..ab42f12 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -10,7 +10,7 @@ from pathlib import Path
 from PySide6.QtCore import QSize, Qt
 from PySide6.QtGui import QColor, QKeySequence
 from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
-                               QDialogButtonBox, QFormLayout, QFrame, QGroupBox,
+                               QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QGroupBox,
                                QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QPushButton,
                                QScrollArea, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
                                QTabWidget,
@@ -22,8 +22,8 @@ from ..i18n import N_, _
 from ..labels import get_label, labels_for_model
 from ..printer import DEFAULT_MODEL
 from ..printers import SUPPORTED_MODELS, capabilities
-from ..settings import (Settings, restart_pending, save_settings, started_values,
-                        valid_host)
+from ..settings import (HIDEABLE_TOOLS, Settings, restart_pending, save_settings,
+                        started_values, valid_host)
 from .tools import TOOLS
 from .widgets import DoubleSpinBox, FontCombo, SpinBox
 
@@ -207,6 +207,26 @@ class SettingsDialog(QDialog):
             self.start_tool.addItem(_(tool.title), tool.key)
         self.start_tool.setCurrentIndex(max(0, self.start_tool.findData(settings.start_tool)))
         form.addRow(_("Tab at startup"), self.start_tool)
+        # Reiter in der Leiste: DATEI und PAPIER immer (dort wird das Etikett gewählt)
+        self.tool_boxes: dict[str, QCheckBox] = {}
+        grid = QGridLayout()
+        grid.setContentsMargins(0, 0, 0, 0)
+        for index, tool in enumerate(TOOLS):
+            box = QCheckBox(_(tool.title))
+            box.setChecked(tool.key not in settings.hidden_tools)
+            if tool.key not in HIDEABLE_TOOLS:
+                box.setChecked(True)
+                box.setEnabled(False)
+            self.tool_boxes[tool.key] = box
+            box.toggled.connect(lambda _on=False, key=tool.key: self._tool_box_toggled(key))
+            grid.addWidget(box, index // 2, index % 2)
+        form.addRow(_("Tabs in the toolbar"), grid)
+        self.tools_note = QLabel(_("Series still appears when the label has a series or the "
+                                   "printer offers cut options."))
+        self.tools_note.setObjectName("note")
+        self.tools_note.setWordWrap(True)
+        form.addRow(self.tools_note)
+        self._enable_start_tools()
         self.theme = QComboBox()
         self.theme.addItem("RawBlock", "rawblock")
         self.theme.addItem(_("Classic"), "classic")
@@ -424,6 +444,19 @@ class SettingsDialog(QDialog):
     def _family_changed(self, _family) -> None:
         self._family_touched = True
 
+    def _enable_start_tools(self) -> None:
+        """„Reiter beim Start“: ausgeblendete Reiter gesperrt (gekoppelt an die Häkchen)."""
+        model = self.start_tool.model()
+        for key, box in self.tool_boxes.items():
+            model.item(self.start_tool.findData(key)).setEnabled(box.isChecked())
+
+    def _tool_box_toggled(self, key: str) -> None:
+        """Häkchen eines Reiters: Start-Reiter mitsperren; der gewählte Start-Reiter ist gerade
+        ausgeblendet worden → „Zuletzt benutzter“."""
+        self._enable_start_tools()
+        if not self.tool_boxes[key].isChecked() and self.start_tool.currentData() == key:
+            self.start_tool.setCurrentIndex(self.start_tool.findData("last"))
+
     def restart_needed(self) -> bool:
         """Wirkt eine gewählte Einstellung erst nach einem Neustart anders als jetzt? (Liest nur die
         Felder der Neustart-Einstellungen – keine Prüfung anderer Felder.)"""
@@ -446,6 +479,8 @@ class SettingsDialog(QDialog):
             start_zoom=self.zoom.value(),
             start_tool=self.start_tool.currentData(),
             last_tool=self._last_tool,
+            hidden_tools=[key for key, box in self.tool_boxes.items()
+                          if key in HIDEABLE_TOOLS and not box.isChecked()],
             theme=self.theme.currentData(),
             image_crop=self.image_crop.isChecked(),
             image_rotate=self.image_rotate.isChecked(),
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index 5a7d8be..33bdc4f 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -2089,6 +2089,10 @@ msgstr "Serie"
 msgid "Series from a table or numbering"
 msgstr "Serien aus Tabelle oder Nummerierung"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Series still appears when the label has a series or the printer offers cut options."
+msgstr "Serie erscheint trotzdem, wenn das Etikett eine Serie hat oder der Drucker Schnitt-Optionen bietet."
+
 #: src/labelwerk/gui/file_session.py
 #: src/labelwerk/gui/main_window.py
 #, python-brace-format
@@ -2289,6 +2293,10 @@ msgstr "Tabelle nicht gefunden: {path}"
 msgid "Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"
 msgstr "Tabellen (*.csv *.xlsx *.xlsm *.tsv *.txt);;Alle Dateien (*)"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Tabs in the toolbar"
+msgstr "Reiter in der Leiste"
+
 #: src/labelwerk/zpl.py
 msgid "Tear off"
 msgstr "Abreißen"
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index 2b40165..028b48c 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -2068,6 +2068,10 @@ msgstr ""
 msgid "Series from a table or numbering"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Series still appears when the label has a series or the printer offers cut options."
+msgstr ""
+
 #: src/labelwerk/gui/file_session.py
 #: src/labelwerk/gui/main_window.py
 #, python-brace-format
@@ -2268,6 +2272,10 @@ msgstr ""
 msgid "Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Tabs in the toolbar"
+msgstr ""
+
 #: src/labelwerk/zpl.py
 msgid "Tear off"
 msgstr ""
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index a4fe106..491652a 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -26,8 +26,11 @@ THEMES = ("rawblock", "classic")
 RESTART_KEYS = ("language", "start_zoom", "start_tool")   # wirken erst nach einem Neustart (Hinweis)
 # Reiter beim Start: „last“ = zuletzt benutzter, sonst Schlüssel der Werkzeuge (gui/tools.py TOOLS)
 START_TOOLS = ("last", "file", "paper", "text", "image", "barcode", "layout", "series")
+# Reiter, die sich ausblenden lassen (DATEI und PAPIER bleiben immer – dort wird das Etikett gewählt)
+HIDEABLE_TOOLS = tuple(key for key in START_TOOLS[1:] if key not in ("file", "paper"))
 SYMBOL_LISTS = ("symbols_recent", "symbols_favorites")
-QUIET_KEYS = ("last_tool",)   # nur gemerkt, nicht vom Nutzer eingestellt: ungültig → Standard ohne Hinweis
+# ungültig → Standard ohne Hinweis: nur gemerkt (last_tool) bzw. nur Ein-/Ausblenden (hidden_tools)
+QUIET_KEYS = ("last_tool", "hidden_tools")
 
 
 @dataclass
@@ -42,6 +45,7 @@ class Settings:
     start_zoom: int = 200
     start_tool: str = "paper"              # Reiter beim Start (START_TOOLS; "last" = zuletzt benutzter)
     last_tool: str = ""                    # zuletzt benutzter Reiter (still gespeichert)
+    hidden_tools: list[str] = field(default_factory=list)   # ausgeblendete Reiter (HIDEABLE_TOOLS)
     theme: str = "rawblock"                # "rawblock" oder "classic" (Qt-Systemstil)
     image_crop: bool = True                # Bilder beim Einfügen auf den Inhalt zuschneiden
     image_rotate: bool = False             # Bilder drehen, wenn sie nur gedreht 1:1 passen
@@ -88,6 +92,7 @@ def _rules(model: str | None = None) -> dict:
         "image_threshold": lambda v: _is_int(v) and 0 <= v <= 255,
         "start_tool": lambda v: v in START_TOOLS,
         "last_tool": lambda v: v == "" or (v in START_TOOLS and v != "last"),
+        "hidden_tools": lambda v: isinstance(v, list),
         "symbols_recent": lambda v: isinstance(v, list),
         "symbols_favorites": lambda v: isinstance(v, list),
         "recent_files": lambda v: isinstance(v, list),
@@ -186,6 +191,8 @@ def load_settings(path: str | Path | None = None, model: str | None = None) -> S
                 value = _symbol_ids(key, value, settings.warnings)
             elif key == "recent_files":
                 value = _text_list(key, value, settings.warnings)[:RECENT_FILES]
+            elif key == "hidden_tools":            # still: DATEI/PAPIER und Unbekanntes fallen weg
+                value = list(dict.fromkeys(v for v in value if v in HIDEABLE_TOOLS))
             elif key == "network_printers":
                 value = _network(value, settings.warnings)
             elif key == "printer_options":
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2709 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-19-oberflaeche-design.md src/labelwerk/gui/main_window.py src/labelwerk/gui/settings_dialog.py src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/settings.py tests/gui/test_gui_hidden_tools.py tests/test_settings.py
git commit -m "Reiter ausblenden: Einstellung „Reiter in der Leiste“ (DATEI/PAPIER fest), Objekte ausgeblendeter Reiter bleiben bearbeitbar, SERIE erscheint, solange gebraucht

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Dateiauswahl mit Vorschau und Dateiauswahl des Systems

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-19-oberflaeche-design.md`
- Modify: `src/labelwerk/gui/app.py`
- Create: `src/labelwerk/gui/file_dialog.py`
- Modify: `src/labelwerk/gui/file_session.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/series.py`
- Modify: `src/labelwerk/settings.py`
- Create: `tests/gui/test_gui_checkbox_style.py`
- Create: `tests/gui/test_gui_file_dialog.py`
- Modify: `tests/gui/test_gui_hidden_tools.py`
- Modify: `tests/gui/test_gui_image.py`
- Modify: `tests/gui/test_gui_language.py`
- Modify: `tests/gui/test_gui_series.py`
- Modify: `tests/test_i18n.py`
- Modify: `tests/test_series.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `gui/file_dialog.py` (`PreviewFileDialog`, `ask_open` → `Chosen` mit `.page`, `make_preview` im Hintergrund, `exec_dialog`); `series.load_table(…, limit=)`/`Table.more`; `settings.system_file_dialog` (RESTART_KEYS, `configured_file_dialog`), `restart_pending(values, started)`, `start_tool_for`; `app.qt_arguments`/`system_dialog_available`; `MainWindow.system_dialog`; Speichern-Rückfrage bei nativem Dialog; gesperrte gesetzte Häkchen sichtbar (rawblock.qss); Doku.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_checkbox_style.py b/tests/gui/test_gui_checkbox_style.py
new file mode 100644
index 0000000..92c79b9
--- /dev/null
+++ b/tests/gui/test_gui_checkbox_style.py
@@ -0,0 +1,24 @@
+"""RawBlock: ein gesperrtes, aber gesetztes Häkchen (DATEI/PAPIER unter „Reiter in der Leiste“) sieht
+gesetzt aus – nicht wie ein leeres Kästchen."""
+from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton
+
+from labelwerk.gui.app import load_theme
+
+
+def _indicator_center(qtbot, qapp, checked: bool):
+    box = QCheckBox("X")
+    qtbot.addWidget(box)
+    box.setStyleSheet(load_theme())
+    box.setChecked(checked)
+    box.setEnabled(False)
+    box.resize(box.sizeHint())
+    box.show()
+    image = box.grab().toImage()
+    opt = QStyleOptionButton()
+    box.initStyleOption(opt)
+    rect = box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, box)
+    return image.pixelColor(rect.center()).lightness()
+
+
+def test_disabled_checked_box_looks_checked(qtbot, qapp):
+    assert _indicator_center(qtbot, qapp, True) < _indicator_center(qtbot, qapp, False) - 60
diff --git a/tests/gui/test_gui_file_dialog.py b/tests/gui/test_gui_file_dialog.py
new file mode 100644
index 0000000..9dff370
--- /dev/null
+++ b/tests/gui/test_gui_file_dialog.py
@@ -0,0 +1,367 @@
+"""Dateiauswahl mit Vorschau (Etappe Oberfläche): Vorschau je Dateiart, eigener Dialog mit
+Seitenwahl für PDF, Dateiauswahl des Systems als Einstellung – nie ein echter modaler Dialog."""
+from pathlib import Path
+
+import pytest
+from PIL import Image
+from PySide6.QtWidgets import QFileDialog
+
+from labelwerk import storage
+from labelwerk.document import Document, TextObject
+from labelwerk.gui import file_dialog
+from labelwerk.gui.file_dialog import Chosen, PreviewFileDialog, ask_open, make_preview
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.settings import Settings
+
+
+def _png(tmp_path, name="bild.png", size=(400, 200)) -> Path:
+    path = tmp_path / name
+    Image.new("RGB", size, "black").save(path)
+    return path
+
+
+def _pdf(tmp_path, sizes=((300, 150), (150, 300), (200, 200))) -> Path:
+    path = tmp_path / "marken.pdf"
+    pages = [Image.new("RGB", s, "black") for s in sizes]
+    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=72)
+    return path
+
+
+# --- Vorschau je Dateiart -------------------------------------------------------------
+def test_image_preview_is_scaled_and_names_the_size(tmp_path):
+    preview = make_preview(_png(tmp_path), size=100)
+    assert preview.image is not None and max(preview.image.width(), preview.image.height()) <= 100
+    assert preview.image.width() > preview.image.height()
+    assert "bild.png" in preview.text and "400 × 200" in preview.text
+
+
+def test_jpeg_preview_follows_the_exif_orientation(tmp_path):
+    path = tmp_path / "foto.jpg"
+    exif = Image.Exif()
+    exif[0x0112] = 6                                   # 90° gedreht aufgenommen
+    Image.new("RGB", (400, 200), "gray").save(path, exif=exif)
+    preview = make_preview(path, size=100)
+    assert preview.image.height() > preview.image.width()
+
+
+def test_svg_preview(tmp_path):
+    path = tmp_path / "zeichen.svg"
+    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" '
+                    'viewBox="0 0 40 20"><rect width="40" height="20"/></svg>')
+    preview = make_preview(path, size=100)
+    assert preview.image is not None and preview.image.width() > preview.image.height()
+
+
+def test_pdf_preview_shows_the_chosen_page(tmp_path):
+    path = _pdf(tmp_path)
+    first, second = make_preview(path, 1, size=100), make_preview(path, 2, size=100)
+    assert first.pages == second.pages == 3
+    assert first.image.width() > first.image.height()
+    assert second.image.height() > second.image.width()
+    assert "Seite 2 von 3" in second.text
+    assert make_preview(path, 9, size=100).page == 3          # außerhalb → letzte Seite
+
+
+def test_label_file_preview(tmp_path):
+    path = tmp_path / "etikett.labelwerk"
+    storage.save(Document("62", objects=[TextObject("Hallo")]), path)
+    preview = make_preview(path, size=120)
+    assert preview.image is not None and "etikett.labelwerk" in preview.text
+
+
+def test_table_preview_shows_the_first_rows(tmp_path):
+    path = tmp_path / "klemmen.csv"
+    path.write_text("Klemme;Signal\n" + "".join(f"X{i};S{i}\n" for i in range(30)))
+    preview = make_preview(path)
+    assert preview.image is None
+    assert "Klemme" in preview.text and "X0" in preview.text and "X8" not in preview.text
+    assert "mehr als 8 Zeilen" in preview.text
+    path.write_text("Klemme;Signal\nX1;S1\nX2;S2\n")
+    assert "2 Zeilen" in make_preview(path).text
+
+
+def test_large_pictures_are_not_decoded(tmp_path, monkeypatch):
+    """Pixelgrenze vor dem Dekodieren (Speicher) – JPEG wird verkleinert dekodiert und darf."""
+    monkeypatch.setattr(file_dialog, "MAX_PREVIEW_PIXELS", 1000)
+    preview = make_preview(_png(tmp_path))
+    assert preview.image is None and "Keine Vorschau" in preview.text and "400 × 200" in preview.text
+    jpeg = tmp_path / "foto.jpg"
+    Image.new("RGB", (400, 200), "gray").save(jpeg)
+    assert make_preview(jpeg, size=100).image is not None
+
+
+@pytest.mark.parametrize("w, h", [(100000, 1), (1, 100000), (0.001, 1)])
+def test_svg_with_extreme_proportions_does_not_break(tmp_path, w, h):
+    path = tmp_path / "strich.svg"
+    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
+                    f'<rect width="{w}" height="{h}"/></svg>')
+    preview = make_preview(path, size=100)
+    assert preview.image is None or not preview.image.isNull()
+    if preview.image is not None:
+        assert max(preview.image.width(), preview.image.height()) <= 100
+
+
+@pytest.mark.parametrize("name, data", [("kaputt.png", b"keine Bilddaten"),
+                                        ("kaputt.pdf", b"%PDF-1.4 kaputt"),
+                                        ("kaputt.labelwerk", b"{"), ("kaputt.csv", b"\xff\xfe\x00")])
+def test_broken_files_have_no_preview_but_never_raise(tmp_path, name, data):
+    path = tmp_path / name
+    path.write_bytes(data)
+    preview = make_preview(path)
+    assert preview.image is None and name in preview.text
+
+
+def test_too_large_files_are_not_read(tmp_path, monkeypatch):
+    path = _png(tmp_path)
+    monkeypatch.setattr(file_dialog, "MAX_PREVIEW_BYTES", 10)
+    preview = make_preview(path)
+    assert preview.image is None and "bild.png" in preview.text and "Keine Vorschau" in preview.text
+
+
+def test_other_files_and_folders_show_name_and_size(tmp_path):
+    path = tmp_path / "notiz.xyz"
+    path.write_bytes(b"x" * 2048)
+    assert make_preview(path).text.startswith("notiz.xyz")
+    assert make_preview(tmp_path).image is None
+
+
+# --- eigener Dialog ---------------------------------------------------------------------
+def test_dialog_is_not_native_and_shows_the_preview_of_the_current_file(qtbot, tmp_path):
+    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)")
+    qtbot.addWidget(dialog)
+    assert dialog.testOption(QFileDialog.Option.DontUseNativeDialog)
+    dialog.show_preview(str(_png(tmp_path)))
+    qtbot.waitUntil(lambda: not dialog.pane.image.pixmap().isNull(), timeout=3000)
+    assert not dialog.pane.pages.isVisible()
+
+
+def test_preview_is_read_in_the_background_and_stale_results_are_dropped(qtbot, tmp_path):
+    from labelwerk.gui.file_dialog import PreviewPane
+    pane = PreviewPane()
+    qtbot.addWidget(pane)
+    first, second = _png(tmp_path, "a.png"), _png(tmp_path, "b.png", (100, 300))
+    pane.show_file(str(first))
+    generation = pane.generation
+    pane.show_file(str(second))
+    assert pane.generation == generation + 1
+    qtbot.waitUntil(lambda: "b.png" in pane.info.text(), timeout=3000)
+    pane.show_result(generation, make_preview(first))        # verspätetes Ergebnis von a.png
+    assert "b.png" in pane.info.text()
+
+
+def test_pdf_preview_comes_at_once(qtbot, tmp_path):
+    """PDFium ist nicht threadsicher: PDF-Vorschau im GUI-Thread (klein, schnell)."""
+    from labelwerk.gui.file_dialog import PreviewPane
+    pane = PreviewPane(pages=True)
+    qtbot.addWidget(pane)
+    pane.show_file(str(_pdf(tmp_path)))
+    assert "Seite 1 von 3" in pane.info.text() and not pane.image.pixmap().isNull()
+
+
+def test_dialog_layout_leaves_room_for_the_file_list(qtbot, tmp_path):
+    from PySide6.QtWidgets import QListView, QSplitter, QTreeView
+    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)")
+    qtbot.addWidget(dialog)
+    assert dialog.findChild(QListView, "sidebar").minimumWidth() >= 160
+    header = dialog.findChild(QTreeView, "treeView").header()
+    assert header.isSectionHidden(2)                          # Spalte Typ
+    assert header.sectionResizeMode(0) == header.ResizeMode.Stretch
+    screen = dialog.screen().availableGeometry()
+    assert dialog.width() <= 0.9 * screen.width() + 1 and dialog.height() <= 0.9 * screen.height() + 1
+    dialog.show()
+    splitter = dialog.findChild(QSplitter, "splitter")
+    qtbot.waitUntil(lambda: splitter.sizes()[0] >= 160, timeout=2000)
+
+
+def test_dialog_follows_the_current_file(qtbot, tmp_path):
+    path = _png(tmp_path)
+    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)")
+    qtbot.addWidget(dialog)
+    dialog.currentChanged.emit(str(path))
+    qtbot.waitUntil(lambda: "bild.png" in dialog.pane.info.text(), timeout=2000)
+
+
+def test_pdf_page_is_chosen_in_the_dialog(qtbot, tmp_path):
+    path = _pdf(tmp_path)
+    dialog = PreviewFileDialog(None, "Bild einfügen", str(tmp_path), "Alle (*)", pages=True)
+    qtbot.addWidget(dialog)
+    dialog.show()
+    dialog.show_preview(str(path))
+    assert dialog.pane.pages.isVisible() and dialog.pane.page_label.text() == "1/3"
+    dialog.pane.next.click()
+    assert dialog.pane.page_label.text() == "2/3" and dialog.pane.page == 2
+    dialog.pane.next.click()
+    dialog.pane.next.click()                                  # bleibt auf der letzten
+    assert dialog.pane.page == 3 and not dialog.pane.next.isEnabled()
+    dialog.pane.prev.click()
+    assert dialog.page_for(str(path)) == 2
+    assert dialog.page_for(str(tmp_path / "andere.pdf")) is None
+
+
+def test_without_pages_option_pdf_has_no_page_choice(qtbot, tmp_path):
+    dialog = PreviewFileDialog(None, "Etikett öffnen", str(tmp_path), "Alle (*)")
+    qtbot.addWidget(dialog)
+    dialog.show()
+    dialog.show_preview(str(_pdf(tmp_path)))
+    assert not dialog.pane.pages.isVisible()
+
+
+def test_ask_open_returns_path_and_page(qtbot, tmp_path, monkeypatch):
+    path = _pdf(tmp_path)
+
+    def user(dialog):
+        dialog.show_preview(str(path))
+        dialog.pane.next.click()
+        dialog.selectFile(str(path))
+        return True
+    monkeypatch.setattr(file_dialog, "exec_dialog", user)
+    chosen = ask_open(None, "Bild einfügen", str(tmp_path), "Alle (*)", pages=True)
+    assert isinstance(chosen, Chosen) and chosen == str(path) and chosen.page == 2
+
+
+def test_ask_open_cancelled(qtbot, tmp_path, monkeypatch):
+    monkeypatch.setattr(file_dialog, "exec_dialog", lambda dialog: False)
+    assert ask_open(None, "Bild einfügen", str(tmp_path), "Alle (*)") is None
+
+
+def test_system_dialog_uses_the_qt_dialog_and_asks_the_page_later(tmp_path, monkeypatch):
+    seen = []
+    monkeypatch.setattr(file_dialog, "exec_dialog", lambda d: pytest.fail("eigener Dialog"))
+    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
+                        lambda parent, title, folder, filter_: seen.append((title, folder))
+                        or (str(tmp_path / "a.pdf"), filter_))
+    chosen = ask_open(None, "Bild einfügen", str(tmp_path), "Alle (*)", system=True, pages=True)
+    assert chosen == str(tmp_path / "a.pdf") and chosen.page is None
+    assert seen == [("Bild einfügen", str(tmp_path))]
+
+
+# --- Hauptfenster ----------------------------------------------------------------------
+def _window(qtbot, **settings):
+    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
+                     settings=Settings(check_media_on_start=False, **settings))
+    qtbot.addWidget(win)
+    return win
+
+
+def test_insert_image_takes_the_page_from_the_dialog(qtbot, tmp_path, monkeypatch):
+    path = _pdf(tmp_path)
+
+    def user(dialog):
+        assert dialog.windowTitle() == "Bild einfügen"
+        assert dialog.nameFilters()[0].startswith("Bilder und PDF (")
+        dialog.show_preview(str(path))
+        dialog.pane.next.click()
+        dialog.selectFile(str(path))
+        return True
+    monkeypatch.setattr(file_dialog, "exec_dialog", user)
+    win = _window(qtbot)
+    win.ask_pdf_page = lambda path, count: pytest.fail("Seite schon im Dialog gewählt")
+    win.panel("image").from_file.click()
+    assert (win.doc.objects[1].source, win.doc.objects[1].page) == ("marken.pdf", 2)
+    assert win._image_dir == str(tmp_path)
+
+
+def test_with_system_dialog_the_page_is_asked_afterwards(qtbot, tmp_path, monkeypatch):
+    path = _pdf(tmp_path)
+    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
+                        lambda *args: (str(path), ""))
+    win = _window(qtbot, system_file_dialog=True)
+    asked = []
+    win.ask_pdf_page = lambda p, count: asked.append(count) or 3
+    win.panel("image").from_file.click()
+    assert asked == [3] and win.doc.objects[1].page == 3
+
+
+def test_series_table_and_open_label_use_the_preview_dialog(qtbot, tmp_path, monkeypatch):
+    seen = []
+    monkeypatch.setattr(file_dialog, "exec_dialog",
+                        lambda d: seen.append((d.windowTitle(), d.nameFilters()[0])) and False)
+    win = _window(qtbot)
+    assert win.ask_series_file() is None
+    assert win.files.ask_open_file() is None
+    assert seen[0][0] == "Tabelle für die Serie" and seen[0][1].startswith("Tabellen (")
+    assert seen[1][0] == "Etikett öffnen" and seen[1][1].startswith("labelwerk-Etiketten (")
+
+
+# --- Einstellung „Dateiauswahl des Systems verwenden“ -----------------------------------
+def test_setting_in_the_dialog_needs_a_restart(qtbot, tmp_path):
+    from labelwerk.gui.settings_dialog import SettingsDialog
+    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    dialog.show()
+    assert not dialog.system_file_dialog.isChecked() and dialog.restart_hint.isHidden()
+    dialog.system_file_dialog.setChecked(True)
+    assert dialog.restart_hint.isVisible()
+    assert dialog.values().system_file_dialog is True
+
+
+def test_system_dialog_is_chosen_by_a_qt_argument_without_touching_the_environment(monkeypatch):
+    """Platform-Theme „xdgdesktopportal“ (Dialog des Desktops über das XDG-Portal) als Argument
+    der Anwendung – Kindprozesse erben nichts."""
+    from labelwerk.gui.app import qt_arguments
+    monkeypatch.setenv("QT_QPA_PLATFORMTHEME", "qt5ct")
+    assert qt_arguments(["labelwerk-gui", "a.labelwerk"], True) == [
+        "labelwerk-gui", "-platformtheme", "xdgdesktopportal", "a.labelwerk"]
+    assert qt_arguments(["labelwerk-gui"], False) == ["labelwerk-gui"]
+    import os
+    assert os.environ["QT_QPA_PLATFORMTHEME"] == "qt5ct"
+
+
+def test_system_dialog_needs_the_qt_plugin(monkeypatch, tmp_path):
+    assert file_dialog.system_dialog_available()               # PySide6 bringt es mit
+    plugins = tmp_path / "plugins" / "platformthemes"
+    plugins.mkdir(parents=True)
+    monkeypatch.setattr(file_dialog, "_plugins_path", lambda: str(tmp_path / "plugins"))
+    assert not file_dialog.system_dialog_available()
+    (plugins / "libqxdgdesktopportal.so").write_bytes(b"")
+    assert file_dialog.system_dialog_available()
+
+
+def test_without_plugin_the_setting_is_locked_and_the_own_dialog_is_used(qtbot, tmp_path,
+                                                                        monkeypatch):
+    from labelwerk.gui.settings_dialog import SettingsDialog
+    monkeypatch.setattr(file_dialog, "system_dialog_available", lambda: False)
+    dialog = SettingsDialog(Settings(system_file_dialog=True), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    assert not dialog.system_file_dialog.isEnabled() and dialog.system_file_dialog.toolTip()
+    seen = []
+    monkeypatch.setattr(file_dialog, "exec_dialog", lambda d: seen.append(d) and False)
+    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
+                        lambda *a: pytest.fail("Systemdialog ohne Plugin"))
+    win = _window(qtbot, system_file_dialog=True)
+    assert win.ask_image_file() is None and len(seen) == 1
+
+
+def test_the_dialog_kind_is_fixed_at_start(qtbot, tmp_path, monkeypatch):
+    """Die Einstellung wirkt erst nach einem Neustart – bis dahin bleibt der Weg vom Start."""
+    seen = []
+    monkeypatch.setattr(file_dialog, "exec_dialog", lambda d: seen.append(d) and False)
+    monkeypatch.setattr(file_dialog.QFileDialog, "getOpenFileName",
+                        lambda *a: pytest.fail("Systemdialog vor dem Neustart"))
+    win = _window(qtbot)
+    win.settings.system_file_dialog = True                     # gespeichert, noch nicht neu gestartet
+    assert win.ask_image_file() is None and win.ask_series_file() is None
+    assert win.files.ask_open_file() is None and len(seen) == 3
+
+
+def test_save_as_with_the_system_dialog_asks_before_replacing(qtbot, tmp_path, monkeypatch):
+    """Dialoge des Desktops fragen nicht immer vor dem Ersetzen – labelwerk fragt selbst."""
+    target = tmp_path / "da.labelwerk"
+    storage.save(Document("62", objects=[TextObject("alt")]), target)
+    win = _window(qtbot, system_file_dialog=True)
+    win.files.ask_save_file = lambda suggested: str(target)
+    asked = []
+    win.files.ask_replace_file = lambda path: asked.append(path) or False
+    assert not win.files.save_as()
+    assert asked == [target] and storage.load(target).objects[0].paragraphs[0].text == "alt"
+    win.files.ask_replace_file = lambda path: asked.append(path) or True
+    assert win.files.save_as() and len(asked) == 2
+
+
+def test_save_dialog_is_not_native_with_the_own_dialog(qtbot, monkeypatch):
+    seen = []
+    monkeypatch.setattr(QFileDialog, "exec", lambda self: seen.append(
+        self.testOption(QFileDialog.Option.DontUseNativeDialog)) or 0)
+    win = _window(qtbot)
+    win.files.ask_save_file("x.labelwerk")
+    assert seen == [True]
diff --git a/tests/gui/test_gui_hidden_tools.py b/tests/gui/test_gui_hidden_tools.py
index f0b208f..e65f69a 100644
--- a/tests/gui/test_gui_hidden_tools.py
+++ b/tests/gui/test_gui_hidden_tools.py
@@ -264,3 +264,69 @@ def test_hiding_the_start_tab_switches_to_last_used(qtbot, tmp_path):
     dialog.tool_boxes["barcode"].setChecked(False)
     assert dialog.start_tool.currentData() == "last"
     assert dialog.values().start_tool == "last"
+
+
+# --- SERIE: Panel gezeigt → Knopf bleibt, bis der Reiter wechselt ------------------
+def _series_window(qtbot):
+    win = _window(qtbot, hidden_tools=["series"])
+    win.panel("series").numbering_button.click()                    # Nummerierung als Serie
+    win.render_now()
+    assert win.doc.series is not None
+    win.tool_actions["series"].trigger()
+    assert win.panels.currentWidget() is win.panel("series")
+    return win
+
+
+def test_series_button_stays_after_remove_while_shown(qtbot):
+    win = _series_window(qtbot)
+    win.panel("series").remove_button.click()
+    win.render_now()
+    assert win.doc.series is None and win.tool_actions["series"].isVisible()
+    win.tool_actions["text"].trigger()
+    assert not win.tool_actions["series"].isVisible()
+
+
+def test_series_button_stays_after_new_label_while_shown(qtbot):
+    win = _series_window(qtbot)
+    win.files.new()
+    win.render_now()
+    assert win.doc.series is None
+    assert win.panels.currentWidget() is not win.panel("series") \
+        or win.tool_actions["series"].isVisible()
+    win.tool_actions["paper"].trigger()
+    assert not win.tool_actions["series"].isVisible()
+
+
+def test_series_button_stays_after_printer_change_while_shown(qtbot, monkeypatch, queue, workers):
+    from test_gui_printers import _window as printer_window
+    win = printer_window(qtbot, monkeypatch, [], printer="cups:Dymo", hidden_tools=["series"])
+    win.tool_actions["series"].trigger()
+    win.choose_printer("cups:Laser")
+    assert win.tool_actions["series"].isVisible()
+    win.tool_actions["paper"].trigger()
+    assert not win.tool_actions["series"].isVisible()
+
+
+def test_unchanged_hidden_tools_in_other_order_do_not_fall_back(qtbot, monkeypatch):
+    win = _window(qtbot, objects=[TextObject("A"), BarcodeObject(kind="qr", data="X", module=4)],
+                  hidden_tools=["barcode", "layout"])
+    win.render_now()
+    win.canvas.set_selection([1])
+    QApplication.processEvents()
+    win.canvas.set_selection([1])
+    _save_with(win, monkeypatch, hidden_tools=["layout", "barcode"])
+    assert win.panels.currentWidget() is win.panel("barcode")
+
+
+def test_start_tab_already_hidden_is_locked_without_restart_hint(qtbot, tmp_path):
+    dialog = SettingsDialog(Settings(start_tool="series", hidden_tools=["series"]), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    dialog.show()
+    assert not _enabled(dialog.start_tool, "series")
+    assert not dialog.restart_hint.isVisible()
+    assert dialog.values().start_tool == "paper"                  # wie es tatsächlich startet
+
+
+def test_start_with_hidden_tools_does_not_fall_back(qtbot):
+    win = _window(qtbot, start_tool="text", hidden_tools=["barcode"])
+    assert win.panels.currentWidget() is win.panel("text")
diff --git a/tests/gui/test_gui_image.py b/tests/gui/test_gui_image.py
index 18732c1..6c97001 100644
--- a/tests/gui/test_gui_image.py
+++ b/tests/gui/test_gui_image.py
@@ -363,10 +363,10 @@ def test_file_dialog_filter_accepts_uppercase_names():
 def test_file_dialog_filter_in_the_language(qtbot, monkeypatch):
     """Der Dialog „Bild einfügen“ bekommt den Filter in der Sprache der Oberfläche."""
     from labelwerk import i18n
-    from labelwerk.gui import main_window
+    from labelwerk.gui import file_dialog
     seen = []
-    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName",
-                        lambda parent, title, folder, filter_: seen.append((title, filter_)) or ("", ""))
+    monkeypatch.setattr(file_dialog, "exec_dialog",
+                        lambda d: seen.append((d.windowTitle(), ";;".join(d.nameFilters()))) and False)
     win = _window(qtbot)
     win.ask_image_file()
     assert seen[-1][0] == "Bild einfügen" and seen[-1][1].startswith("Bilder und PDF (")
diff --git a/tests/gui/test_gui_language.py b/tests/gui/test_gui_language.py
index b8a679e..d9bd1e2 100644
--- a/tests/gui/test_gui_language.py
+++ b/tests/gui/test_gui_language.py
@@ -43,7 +43,7 @@ def test_restart_notice_stays_next_to_save(qtbot, tmp_path):
     vergleicht mit dem Stand beim Start: wieder zurückgestellt, kein Hinweis."""
     dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
                             started={"language": "en", "start_zoom": 200,
-                                     "start_tool": "paper"})
+                                     "start_tool": "paper", "system_file_dialog": False})
     qtbot.addWidget(dialog)
     dialog.show()
     assert dialog.restart_hint.isHidden()
@@ -59,7 +59,7 @@ def test_saved_but_not_restarted_still_shows_the_notice(qtbot, tmp_path):
     """Gespeichert, aber noch nicht neu gestartet: beim nächsten Öffnen steht der Hinweis gleich da."""
     dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
                             started={"language": "de", "start_zoom": 200,
-                                     "start_tool": "paper"})
+                                     "start_tool": "paper", "system_file_dialog": False})
     qtbot.addWidget(dialog)
     assert not dialog.restart_hint.isHidden()
 
diff --git a/tests/gui/test_gui_series.py b/tests/gui/test_gui_series.py
index 06f1e97..bff94cd 100644
--- a/tests/gui/test_gui_series.py
+++ b/tests/gui/test_gui_series.py
@@ -521,8 +521,9 @@ def test_table_is_read_once_when_chosen(qtbot, tmp_path, monkeypatch):
 def test_file_dialog_starts_at_the_current_table(qtbot, tmp_path, monkeypatch):
     win, path = _with_table(qtbot, tmp_path)
     seen = []
-    monkeypatch.setattr(main_window.QFileDialog, "getOpenFileName",
-                        lambda parent, title, folder, filters: seen.append(folder) or ("", ""))
+    from labelwerk.gui import file_dialog
+    monkeypatch.setattr(file_dialog, "exec_dialog",
+                        lambda dialog: seen.append(dialog.directory().absolutePath()) and False)
     del win.ask_series_file
     win.choose_series_table()
     assert seen == [str(path.parent)]
diff --git a/tests/test_i18n.py b/tests/test_i18n.py
index c153ec4..ae5794c 100644
--- a/tests/test_i18n.py
+++ b/tests/test_i18n.py
@@ -202,9 +202,14 @@ def test_numbers_in_label_content_follow_the_region():
 
 def test_restart_pending():
     from labelwerk.settings import restart_pending
-    started = {"language": "de", "start_zoom": 200, "start_tool": "paper"}
-    assert not restart_pending("", 200, "paper", started)   # Automatisch = Systemsprache (de)
-    assert not restart_pending("de", 200, "paper", started)
-    assert restart_pending("en", 200, "paper", started)
-    assert restart_pending("de", 150, "paper", started)
-    assert restart_pending("de", 200, "last", started)
+    started = {"language": "de", "start_zoom": 200, "start_tool": "paper",
+               "system_file_dialog": False}
+
+    def pending(**changed):
+        return restart_pending({**started, **changed}, started)
+    assert not pending(language="")                           # Automatisch = Systemsprache (de)
+    assert not pending()
+    assert pending(language="en")
+    assert pending(start_zoom=150)
+    assert pending(start_tool="last")
+    assert pending(system_file_dialog=True)
diff --git a/tests/test_series.py b/tests/test_series.py
index 22b1601..68f3b9d 100644
--- a/tests/test_series.py
+++ b/tests/test_series.py
@@ -533,3 +533,25 @@ def test_unnamed_columns_in_every_language(tmp_path):
     doc = Document("62", objects=[TextObject("{Spalte 2} {Column 2}")])
     assert missing(doc, table.columns) == []
     assert fill(doc, table.columns, table.rows[0]).objects[0].text == "24V 24V"
+
+
+# --- nur der Anfang (Vorschau im Dateidialog) --------------------------------------------------
+@pytest.mark.parametrize("count, more", [(3, False), (4, True), (50, True)])
+def test_load_table_reads_only_the_first_rows(tmp_path, count, more):
+    path = tmp_path / "t.csv"
+    path.write_text("A;B\n" + "".join(f"{i};x\n\n" for i in range(count)))   # leere Zeilen zählen nicht
+    table = load_table(path, limit=3)
+    assert table.columns == ["A", "B"] and [r[0] for r in table.rows] == ["0", "1", "2"][:count]
+    assert table.more is more
+
+
+def test_load_table_limit_in_excel(tmp_path):
+    path = tmp_path / "t.xlsx"
+    book = openpyxl.Workbook()
+    book.active.append(["A"])
+    for i in range(10):
+        book.active.append([i])
+    book.save(path)
+    table = load_table(path, limit=2)
+    assert table.rows == [["0"], ["1"]] and table.more is True
+    assert load_table(path).more is False and len(load_table(path).rows) == 10
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 32b7c9f..558bad1 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -424,8 +424,34 @@ def test_start_tool_needs_a_restart():
     started = started_values(Settings(start_tool="paper"))
     assert started["start_tool"] == "paper"
     language = started["language"]
-    assert not restart_pending(language, 200, "paper", started)
-    assert restart_pending(language, 200, "last", started)
+    assert not restart_pending({**started, "start_tool": "paper"}, started)
+    assert restart_pending({**started, "start_tool": "last"}, started)
+
+
+# --- Dateiauswahl des Systems ---------------------------------------------------------
+def test_system_file_dialog_default_validation_and_restart(tmp_path):
+    from labelwerk.settings import RESTART_KEYS, started_values
+    path = tmp_path / "s.json"
+    assert load_settings(path).system_file_dialog is False       # eigener Dialog mit Vorschau
+    save_settings(Settings(system_file_dialog=True), path)
+    assert load_settings(path).system_file_dialog is True
+    path.write_text(json.dumps({"system_file_dialog": "ja"}))
+    s = load_settings(path)
+    assert s.system_file_dialog is False and s.warnings
+    assert "system_file_dialog" in RESTART_KEYS
+    assert started_values(Settings(system_file_dialog=True))["system_file_dialog"] is True
+
+
+@pytest.mark.parametrize("raw, expected", [({"system_file_dialog": True}, True),
+                                           ({"system_file_dialog": False}, False),
+                                           ({"system_file_dialog": "ja"}, False), ([], False),
+                                           (None, False)])
+def test_configured_file_dialog_is_read_before_everything(tmp_path, raw, expected):
+    from labelwerk.settings import configured_file_dialog
+    path = tmp_path / "s.json"
+    if raw is not None:
+        path.write_text(json.dumps(raw))
+    assert configured_file_dialog(path) is expected
 
 
 # --- stilles Speichern einzelner Felder ------------------------------------------------
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_file_dialog.py, tests/gui/test_gui_checkbox_style.py, Fälle in tests/test_settings.py, tests/test_series.py u. a.) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index c7a23ea..b36e90b 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -54,6 +54,10 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Einstellungen: Reiter beim Start (fest oder zuletzt benutzter), Standard für neue Bilder (Strich/Foto, Schwelle),
   Reiter ausblenden (Ansicht → „Reiter in der Leiste“; DATEI/PAPIER immer; Objekte ausgeblendeter Reiter bleiben
   bearbeitbar – Auswahl zeigt ihr Panel, Tastenkürzel wirken).
+- Dateiauswahl mit Vorschau (Etappe Oberfläche): eigener Öffnen-Dialog (Bild einfügen, Etikett öffnen, Tabelle
+  der Serie) mit Vorschau rechts (Bilder, SVG, PDF mit Seitenwahl – keine Seitenfrage danach –, Etiketten,
+  Tabellen; im Hintergrund gelesen); Einstellung „Dateiauswahl des Systems verwenden“ (nach Neustart: Qt-Platform-
+  Theme xdgdesktopportal als Argument = Dialog des Desktops über das XDG-Portal; ohne Qt-Plugin gesperrt).
 - Schriftliste (Abnahme-Korrekturen): nur Schriften mit deutschen Zeichen, ohne Kopien (Powerline/Nerd Font),
   Symbol-/Farbschriften und CJK-Regionsvarianten, jede in ihrer Schrift (FontCombo statt QFontComboBox, keine
   Qt-Sammelnamen wie „Sans Serif“); Einstellung „Alle Schriften zeigen“ (`fonts_all`, sofort), CLI `fonts --all`;
@@ -63,7 +67,7 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   gewählte bleibt sichtbar).
 - Stilles Speichern (Zuletzt geöffnet/verwendet, Favoriten, gewählter Drucker, letzter Reiter) schreibt nur sein
   Feld (`settings.update_settings`) – was eine zweite Instanz gespeichert hat, bleibt.
-- 2709 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- 2762 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -174,8 +178,10 @@ src/labelwerk/
               Port/Schema/Steuerzeichen; Modell auch zpl:…), network_entries(settings); `printer_options` (Modell →
               Druck-Optionen: CUPS-Schnitt-Optionen, Zebra-Modus; je Eintrag geprüft, leerer Wert erlaubt), `zebra_dpi`
               (0 = erkannt), `cups_all` (auch CUPS-Bürodrucker im Druckermenü/`labelwerk printers`; Dialog → Drucker),
-              `fonts_all` (alle Schriften in den Auswahlen, sofort), `language` ("" = System); RESTART_KEYS (language, start_zoom, start_tool), started_values/
-              restart_pending (wirksamer Vergleich mit dem Start), configured_language (vor allem anderen gelesen);
+              `fonts_all` (alle Schriften in den Auswahlen, sofort), `language` ("" = System); `system_file_dialog` (Dateiauswahl des Systems); RESTART_KEYS (language, start_zoom, start_tool,
+              system_file_dialog), start_tool_for (ausgeblendeter Start-Reiter = PAPIER, so verglichen und
+              gespeichert), started_values/restart_pending(values, started) (wirksamer Vergleich mit dem
+              Start), configured_language/configured_file_dialog (vor allem anderen gelesen);
               load_settings(path, model=None): Etikett muss nur ein bekanntes Etikett sein (auch
               „BxHmm@dpi“; ob es zum Drucker passt, prüfen GUI und CLI); save_settings schreibt alles,
               update_settings(path, base, **felder) nur diese Felder in die neu gelesene Datei (Rest bleibt wie dort,
@@ -197,7 +203,8 @@ src/labelwerk/
               (Spalte „Nummer“), check, table_for(series, base); Endungen .csv/.tsv/.txt bzw. .xlsx/.xlsm; Excel höchstens
               MAX_RAW_ROWS Zeilen samt leeren; Table.sheet/sheets (gelesenes Blatt, alle Arbeitsblätter);
               Platzhalter {Spalte} in Text und Barcode-Inhalt (Leerzeichen in den Klammern egal):
-              placeholders, missing, fill(doc, columns, row, keep) – nur zum Lesen: unveränderte Objekte bleiben dieselben
+              placeholders, missing, fill(doc, columns, row, keep) – nur zum Lesen: unveränderte Objekte bleiben dieselben;
+              load_table(…, limit=n): nur die ersten n Zeilen (Vorschau), Table.more = es folgen weitere
   favorites.py Favoriten = *.labelwerk in $XDG_DATA_HOME/labelwerk/favoriten: favorites, find, add (overwrite), rename, remove
   clipart.py  Symbol-Bibliothek ohne Qt: catalog() aus clipart_data/clipart.zip (catalog.json + SVGs, einmal ganz gelesen;
               Einträge mit names/subgroups {de, en} – Anzeige in der Sprache, je Sprache gecacht, Suche über beide;
@@ -251,7 +258,7 @@ src/labelwerk/
                     ganz; start(path) (Datei bzw. Start-Favorit),
                     print_document(doc) (anderes Etikett drucken, gleiche Rückfragen); closeEvent fragt bei Änderungen;
                     apply_hidden_tools(fall_back) (Knöpfe ausgeblendeter Reiter unsichtbar – SERIE bleibt, solange Serie
-                    oder Schnitt-Optionen des Druckers: _tool_visible; nach SPEICHERN nur bei geänderten hidden_tools und
+                    oder Schnitt-Optionen des Druckers: _tool_needed, bzw. solange ihr Panel zu sehen ist: _tool_visible; nach SPEICHERN nur bei geänderten hidden_tools und
                     Panel nicht für Auswahl/Schreibmodus → zuletzt benutzter sichtbarer bzw. PAPIER; leere Auswahl ebenso;
                     Start-Reiter und last_tool überspringen ausgeblendete)
     panels/barcode.py Reiter Barcode: Art (für den gewählten bzw. nächsten), BARCODE EINFÜGEN (Aktion barcode.insert),
@@ -304,6 +311,16 @@ src/labelwerk/
                     jede Schrift in ihrer Schrift, fremde Schrift bleibt oben gewählt, None = leer bei gemischten Schriften;
                     Breite unabhängig von den Namen; Signal family_chosen) – Reiter Text
                     und Einstellungen
+    file_dialog.py  Öffnen-Dialoge: ask_open(parent, title, folder, filters, system, pages, model) -> Chosen | None
+                    (Chosen = Pfad als str mit .page: im Dialog gewählte PDF-Seite); PreviewFileDialog (nicht nativ,
+                    Vorschau rechts: PreviewPane, ◀ n/N ▶ bei PDF mit pages; Platz: Orte ≥ 160 px, Name dehnt sich,
+                    ohne Typ; ≤ 90 % Bildschirm), make_preview(path, page, size, model) -> Preview (Bild verkleinert
+                    gelesen samt EXIF-Lage, Pixelgrenze vor dem Dekodieren außer JPEG, SVG, PDF, *.labelwerk, Tabellen
+                    nur der Anfang; Fehler → „Keine Vorschau“) – im Hintergrund-Thread (Generation, veraltete
+                    verfallen), PDF im GUI-Thread (PDFium); system: QFileDialog des Systems; system_dialog_available
+                    (Qt-Plugin platformthemes/*xdgdesktopportal*); exec_dialog in Tests ersetzt;
+                    MainWindow.system_dialog = Weg vom Start (Einstellung beim Start und Plugin), auch „Speichern unter“
+                    (dann eigene Ersetzen-Rückfrage); app.qt_arguments: „-platformtheme xdgdesktopportal“ beim Start
     symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
     print_worker.py Drucken im Hintergrund-Thread (cancel(): threading.Event; Signale progress, cancelled)
     media_worker.py  Medium prüfen im Hintergrund (MediaWorker(model, printer): URI des gewählten USB-Druckers; Ergebnis eines
@@ -314,7 +331,7 @@ src/labelwerk/
                     Schriftart (FontCombo) mit „Alle Schriften zeigen“ darunter (sofort); Bilder einfügen: Zuschnitt, Drehen,
                     Umwandlung Strich/Foto, Schwelle; Ansicht: Start-Zoom, Reiter beim Start, Reiter in der Leiste (tool_boxes, sperren
                     ausgeblendete im Start-Reiter; tools_note),
-                    Design, Sprache) und
+                    Design, Dateiauswahl des Systems, Sprache) und
                     Tastenkürzel (Konflikte sperren Speichern); restart_hint neben SPEICHERN (Stand beim Start: started)
     theme/          QSS-Stylesheet (rawblock.qss)
     icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
@@ -361,7 +378,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Paketierung (8).
+Nächste Schritte: Paketmarken umwandeln (Spec 2026-10-19-paketmarken), dann Paketierung (8).
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -378,7 +395,7 @@ Umsetzung:
 - GUI bleibt dünn: Logik, die testbar ist, gehört in den Kern
 
 ## Roadmap danach
-0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto (erledigt, Spec 2026-10-18-bildschirmfoto) · 3d-2c Symbole/ClipArt (erledigt, Spec 2026-10-18-symbole) · 3c Neu/Öffnen/Speichern + Favoriten (erledigt, Spec 2026-10-18-dateien-favoriten) · Zierrahmen ums Etikett (erledigt, Spec 2026-10-18-zierrahmen) · 3e Serien aus CSV/Excel und Nummerierung (erledigt, Spec 2026-10-18-serien) · Barcodes/QR (erledigt, Spec 2026-10-19-barcodes).
+0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto (erledigt, Spec 2026-10-18-bildschirmfoto) · 3d-2c Symbole/ClipArt (erledigt, Spec 2026-10-18-symbole) · 3c Neu/Öffnen/Speichern + Favoriten (erledigt, Spec 2026-10-18-dateien-favoriten) · Zierrahmen ums Etikett (erledigt, Spec 2026-10-18-zierrahmen) · 3e Serien aus CSV/Excel und Nummerierung (erledigt, Spec 2026-10-18-serien) · Barcodes/QR (erledigt, Spec 2026-10-19-barcodes) · Abnahme-Korrekturen (erledigt, Spec 2026-10-19-abnahme-korrekturen) · Oberfläche (erledigt, Spec 2026-10-19-oberflaeche).
 1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
 2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
 3. ~~Barcodes und QR-Codes~~ erledigt (QR, Code 128, Code 39, EAN-13/8; später ggf. DataMatrix, ITF, GS1-128)
diff --git a/README.md b/README.md
index 51a35bc..efadb9f 100644
--- a/README.md
+++ b/README.md
@@ -94,7 +94,7 @@ Text: Geschrieben wird direkt auf dem Etikett. Mit dem Knopf „A“ (Text anleg
 
 Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste (oder im Reiter „Text“ ohne Auswahl) und einem Klick aufs Etikett einen Rahmen anlegen – bleibt er leer, verschwindet er wieder, sobald man den Schreibmodus verlässt. Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus; Lage und Größe landen auf 0,1 mm wie in den Feldern), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.
 
-Bild: Im Reiter „Bild“ fügt „Aus Datei …“ (Strg+Umschalt+I) PNG, JPG, GIF, BMP, WebP, SVG oder eine PDF-Seite ein (bei mehreren Seiten fragt ein Dialog nach der Seite), „Aus Zwischenablage“ ein kopiertes Bild. Bilddateien und Bilder lassen sich auch aufs Etikett ziehen (landen an der Ablagestelle). Strg+V auf der Arbeitsfläche fügt ein, was die Zwischenablage oben hat: in labelwerk kopierte Objekte, sonst kopierte Bilddateien (Dateimanager), sonst Text als neuen Textrahmen (auch wenn ein Bild dabei ist, etwa bei Tabellenzellen – das Bild fügt „Aus Zwischenablage“ ein), sonst ein Bild. Bilder kommen in Originalgröße 1:1 (aus der Auflösung der Datei, sonst 300 dpi) und automatisch zugeschnitten (Schnittmarken und weißer Rand fallen weg – z. B. bei der Internetmarke); zu große werden proportional eingepasst, die Statusleiste nennt den Faktor (Codes ggf. nicht mehr lesbar). Das Panel stellt die Umwandlung in Schwarz/Weiß ein: Strich (harte Schwelle – Codes, Schrift, Logos) oder Foto (Rasterpunkte), Schwelle (höher = mehr Schwarz), Umkehren; dazu Zuschnitt an/aus, Originalgröße 1:1 und Seitenverhältnis beibehalten (dann halten auch die Kanten-Anfasser das Verhältnis). Bilder lassen sich verschieben, skalieren, drehen, ausrichten, kopieren und rückgängig machen wie Text; ein Doppelklick auf ein Bild startet keinen Schreibmodus.
+Bild: Im Reiter „Bild“ fügt „Aus Datei …“ (Strg+Umschalt+I) PNG, JPG, GIF, BMP, WebP, SVG oder eine PDF-Seite ein (die Dateiauswahl zeigt rechts eine Vorschau – Bilder, SVG, PDF mit Seitenwahl ◀ n/N ▶, auch Etiketten und Tabellen in den anderen Öffnen-Dialogen; Einstellungen → Ansicht → „Dateiauswahl des Systems verwenden“ nimmt nach einem Neustart den Dialog des Desktops, dann fragt ein Dialog nach der PDF-Seite), „Aus Zwischenablage“ ein kopiertes Bild. Bilddateien und Bilder lassen sich auch aufs Etikett ziehen (landen an der Ablagestelle). Strg+V auf der Arbeitsfläche fügt ein, was die Zwischenablage oben hat: in labelwerk kopierte Objekte, sonst kopierte Bilddateien (Dateimanager), sonst Text als neuen Textrahmen (auch wenn ein Bild dabei ist, etwa bei Tabellenzellen – das Bild fügt „Aus Zwischenablage“ ein), sonst ein Bild. Bilder kommen in Originalgröße 1:1 (aus der Auflösung der Datei, sonst 300 dpi) und automatisch zugeschnitten (Schnittmarken und weißer Rand fallen weg – z. B. bei der Internetmarke); zu große werden proportional eingepasst, die Statusleiste nennt den Faktor (Codes ggf. nicht mehr lesbar). Das Panel stellt die Umwandlung in Schwarz/Weiß ein: Strich (harte Schwelle – Codes, Schrift, Logos) oder Foto (Rasterpunkte), Schwelle (höher = mehr Schwarz), Umkehren; dazu Zuschnitt an/aus, Originalgröße 1:1 und Seitenverhältnis beibehalten (dann halten auch die Kanten-Anfasser das Verhältnis). Bilder lassen sich verschieben, skalieren, drehen, ausrichten, kopieren und rückgängig machen wie Text; ein Doppelklick auf ein Bild startet keinen Schreibmodus.
 
 Barcode: Im Reiter „Barcode“ wählst du die Art (QR-Code, Code 128, Code 39, EAN-13, EAN-8) und fügst mit „Barcode einfügen“ einen Code mit Beispielinhalt ein – den Inhalt tippst du gleich darüber (jede Eingabe sofort auf dem Etikett). Gezeichnet wird in ganzen Druckpunkten, damit der Code bei 300 dpi lesbar bleibt: „Modul“ ist die Breite des schmalsten Strichs bzw. eines QR-Quadrats, Anfasser und Felder rasten darauf ein; Strichcodes haben dazu Höhe und Klartext, QR-Codes die Fehlerkorrektur (L/M/Q/H). Falscher Inhalt (z. B. Buchstaben im EAN) steht als Hinweis im Panel, der Barcode erscheint schraffiert (bleibt wählbar) und das Etikett wird nicht gedruckt; bei EAN mit 12 bzw. 7 Ziffern wird die Prüfziffer ergänzt. In einer Serie geht `{Spalte}` auch im Inhalt (Doppelklick auf die Spalte ersetzt den Beispielinhalt). Lass um den Code die angezeigte Ruhezone frei.
 
diff --git a/docs/superpowers/specs/2026-10-19-oberflaeche-design.md b/docs/superpowers/specs/2026-10-19-oberflaeche-design.md
index 41950be..3c60980 100644
--- a/docs/superpowers/specs/2026-10-19-oberflaeche-design.md
+++ b/docs/superpowers/specs/2026-10-19-oberflaeche-design.md
@@ -37,21 +37,29 @@ Prüfung mit der Abnahme.
 ## 2 – Dateiauswahl mit Vorschau
 
 - **Eigener Dialog** `gui/file_dialog.py`: `QFileDialog` (nicht nativ) mit Vorschau-Bereich rechts, für alle
-  Öffnen-Dialoge (Etikett öffnen, Bild einfügen, Tabelle der Serie, später Paketmarke). Speichern bleibt wie bisher
-  (ohne Vorschau).
-  - Vorschau je Datei, beim Markieren: Bilder (PNG/JPG/GIF/BMP/WebP, verkleinert gelesen, EXIF-Lage), SVG,
-    PDF (Seite gerendert, bei mehreren Seiten Seitenwahl ◀ n/N ▶ – die gewählte Seite gilt, die Seitenfrage danach
-    entfällt), `*.labelwerk` (Etikett gerendert wie bei Favoriten), Tabellen (erste Zeilen); sonst Name und Größe.
-  - Grenzen wie beim Einfügen (Dateigröße, Pixel); Fehler → „Keine Vorschau“, nie ein Absturz; große Dateien
-    blockieren nicht spürbar (verkleinertes Lesen, PDF nur die gewählte Seite klein).
-  - Merkt Ordner wie bisher; Ablegen/Doppelklick wie gewohnt.
-- **Einstellung** `system_file_dialog: bool = False` – „Dateiauswahl des Systems verwenden“ (Dialog → Ansicht).
-  An: Dateiauswahl des Desktops über das XDG-Portal (`org.freedesktop.portal.FileChooser`, QtDBus wie das
-  Bildschirmfoto); ohne Portal Qt-Dialog. Vorschau und PDF-Seitenwahl dann wie vom Desktop (Seitenfrage danach wie
-  bisher).
-- **Tests:** Vorschau je Dateiart (erzeugte Dateien), defekte Datei, PDF-Seitenwahl ersetzt die Seitenfrage,
-  Einstellung schaltet den Weg; Portal gegen ein Test-Portal auf privatem Bus (eigene Config ohne servicedir, wie
-  tests/gui/fake_portal.py) – nie das echte Portal.
+  Öffnen-Dialoge (Etikett öffnen, Bild einfügen, Tabelle der Serie, später Paketmarke). Speichern ohne Vorschau,
+  auf diesem Weg ebenfalls Qts Dialog (fragt selbst vor dem Ersetzen).
+  - Vorschau je Datei, beim Markieren (kurz verzögert): Bilder (PNG/JPG/GIF/BMP/WebP, verkleinert gelesen,
+    EXIF-Lage), SVG, PDF (Seite gerendert, bei mehreren Seiten Seitenwahl ◀ n/N ▶ – die gewählte Seite gilt, die
+    Seitenfrage danach entfällt), `*.labelwerk` (Etikett gerendert, mit Rand), Tabellen (nur Kopf + erste 8
+    Zeilen gelesen – `series.load_table(limit=)`, „mehr als 8 Zeilen“); sonst Name und Größe.
+  - Grenzen: Dateigröße, Pixel vor dem Dekodieren (JPEG ausgenommen – verkleinert schon beim Dekodieren),
+    extreme Seitenverhältnisse; Fehler → „Keine Vorschau“, nie ein Absturz.
+  - Ohne Blockade: gelesen wird in einem Hintergrund-Thread (QImage dort, QPixmap im GUI-Thread, Generationszähler –
+    veraltete Ergebnisse verfallen); PDF im GUI-Thread (PDFium ist nicht threadsicher, kleine Seite ~50 ms).
+  - Platz für die Liste: Orte links mindestens 160 px, Spalte Name dehnt sich, Typ entfällt, Größe/Datum aus der
+    Schriftbreite; Fenster ~1100 × 640, höchstens 90 % des Bildschirms.
+- **Einstellung** `system_file_dialog: bool = False` – „Dateiauswahl des Systems verwenden“ (Dialog → Ansicht),
+  **wirkt nach einem Neustart** (Hinweis neben SPEICHERN): labelwerk startet dann mit dem Qt-Platform-Theme
+  `xdgdesktopportal` (Argument `-platformtheme`, keine Umgebungsvariable – Kindprozesse erben nichts), Qt nimmt den
+  Dialog des Desktops über das XDG-Portal samt Filtern und Ordner (eigene QtDBus-Aufrufe gehen nicht: PySide6 kann
+  die Filter `a(sa(us))` nicht übergeben); ohne Portal Qts eigener Dialog. Bis zum Neustart gilt der Weg vom Start.
+  Fehlt das Qt-Plugin (`platformthemes/*xdgdesktopportal*`), ist die Einstellung gesperrt (Erläuterung) und es gilt
+  der eigene Dialog. Mit Dialog des Desktops: Seitenfrage danach wie bisher; „Speichern unter“ fragt vor dem
+  Ersetzen selbst (Dialoge des Desktops tun es nicht immer).
+- **Tests:** Vorschau je Dateiart (erzeugte Dateien), defekte/zu große Dateien, Hintergrund und veraltete
+  Ergebnisse, PDF-Seitenwahl ersetzt die Seitenfrage, Weg vom Start, Plugin fehlt, Argumente der Anwendung,
+  Ersetzen-Rückfrage, Layout – kein echter modaler Dialog (`exec_dialog` ersetzt).
 
 ## Nicht enthalten
 
diff --git a/src/labelwerk/gui/app.py b/src/labelwerk/gui/app.py
index 6b522ff..9b5000b 100644
--- a/src/labelwerk/gui/app.py
+++ b/src/labelwerk/gui/app.py
@@ -10,8 +10,9 @@ from PySide6.QtWidgets import QApplication
 
 from .. import i18n
 from ..desktop import APP_ID, APP_NAME
-from ..settings import configured_language
+from ..settings import configured_file_dialog, configured_language
 
+from . import file_dialog
 from .main_window import MainWindow
 
 
@@ -57,9 +58,19 @@ def set_language() -> str:
     return language
 
 
+def qt_arguments(argv: list[str], system_dialog: bool) -> list[str]:
+    """Argumente der Anwendung; Dateiauswahl des Systems: Platform-Theme „xdgdesktopportal“ (Qt
+    nimmt dann den Dialog des Desktops über das XDG-Portal) – als Argument, nicht als
+    Umgebungsvariable, die Kindprozesse erben würden. Qt entfernt die Option aus ``arguments()``."""
+    if not system_dialog:
+        return list(argv)
+    return [*argv[:1], "-platformtheme", "xdgdesktopportal", *argv[1:]]
+
+
 def main() -> int:
     set_language()
-    app = QApplication(sys.argv)
+    app = QApplication(qt_arguments(sys.argv, configured_file_dialog()
+                                    and file_dialog.system_dialog_available()))
     apply_identity(app)
     install_translations(app)
     window = MainWindow()
diff --git a/src/labelwerk/gui/file_dialog.py b/src/labelwerk/gui/file_dialog.py
new file mode 100644
index 0000000..d42b814
--- /dev/null
+++ b/src/labelwerk/gui/file_dialog.py
@@ -0,0 +1,417 @@
+"""Dateiauswahl zum Öffnen: eigener Qt-Dialog mit Vorschau rechts (Bilder, SVG, PDF mit
+Seitenwahl, Etiketten, Tabellen) – oder die Dateiauswahl des Systems (Einstellung
+``system_file_dialog``, ab dem Start: Qt bringt sie über das XDG-Portal selbst mit, wenn die
+Anwendung mit dem Platform-Theme „xdgdesktopportal“ startet – ``app.qt_arguments``; ohne dieses
+Qt-Plugin gibt es nur den eigenen Dialog: ``system_dialog_available``).
+
+Vorschauen sind fremde Eingabe: Größe und Pixel begrenzt, verkleinert gelesen, jeder Fehler →
+„Keine Vorschau“ (nie ein Absturz). Gelesen wird im Hintergrund (ein Thread, veraltete Ergebnisse
+zählen nicht); PDF im GUI-Thread – PDFium ist nicht threadsicher und alle anderen PDF-Aufrufe
+laufen dort. ``exec_dialog`` ist in Tests ersetzbar (kein echter modaler Dialog).
+"""
+from __future__ import annotations
+
+from dataclasses import dataclass
+from pathlib import Path
+
+from PIL import Image, ImageOps
+from PySide6.QtCore import QLibraryInfo, QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
+from PySide6.QtGui import QImage, QImageIOHandler, QImageReader, QPainter, QPixmap
+from PySide6.QtSvg import QSvgRenderer
+from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
+                               QListView, QPushButton, QSplitter, QTreeView, QVBoxLayout, QWidget)
+
+from .. import series, storage
+from ..i18n import _, ngettext, number
+from ..render import Renderer
+from ..storage import SUFFIX
+
+PREVIEW_PX = 260                       # Kantenlänge der Vorschau
+MAX_PREVIEW_BYTES = 64 * 1024 * 1024   # größere Dateien: nur Name und Größe
+MAX_PREVIEW_PIXELS = 50_000_000        # Bilder: mehr Pixel nicht dekodieren (JPEG verkleinert schon dabei)
+TABLE_ROWS = 8                         # Tabellen: so viele Zeilen in der Vorschau
+TABLE_CELL = 24                        # Zeichen je Zelle in der Vorschau
+DELAY_MS = 120                         # Vorschau erst, wenn die Auswahl kurz stehen bleibt
+DIALOG_SIZE = (1100, 640)              # höchstens 90 % des Bildschirms
+SIDEBAR_PX = 160                       # Orte links: mindestens so breit
+_RASTER = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
+_TABLES = (*series.CSV_SUFFIXES, ".xlsx", ".xlsm")
+
+
+class Chosen(str):
+    """Gewählter Pfad; ``page``: im Dialog gewählte PDF-Seite (None = nicht gewählt – dann fragt
+    der Aufrufer wie bisher)."""
+    page: int | None = None
+
+    def __new__(cls, path: str, page: int | None = None):
+        chosen = super().__new__(cls, path)
+        chosen.page = page
+        return chosen
+
+
+@dataclass
+class Preview:
+    """Vorschau einer Datei: Bild (oder None), Text darunter (Name, Größe, Tabelle …),
+    Seitenzahl und gezeigte Seite (PDF)."""
+    image: QImage | None
+    text: str
+    pages: int = 1
+    page: int = 1
+
+
+def make_preview(path: str | Path, page: int = 1, size: int = PREVIEW_PX,
+                 model: str = "QL-600") -> Preview:
+    """Vorschau einer Datei für den Dialog; Ordner/fehlende Datei → leer, Fehler → „Keine Vorschau“."""
+    path = Path(path)
+    try:
+        if not path.is_file():
+            return Preview(None, "")
+        nbytes = path.stat().st_size
+    except OSError:
+        return Preview(None, "")
+    info = f"{path.name}\n{_size_text(nbytes)}"
+    if nbytes > MAX_PREVIEW_BYTES:
+        return Preview(None, f"{info}\n{_('No preview')}")
+    suffix = path.suffix.lower()
+    try:
+        if suffix in _RASTER:
+            return _raster(path, size, info)
+        if suffix == ".svg":
+            return _svg(path, size, info)
+        if suffix == ".pdf":
+            return _pdf(path, page, size, info)
+        if suffix == SUFFIX:
+            return _label(path, size, info, model)
+        if suffix in _TABLES:
+            return _table(path, info)
+    except Exception:                   # fremde Datei: jeder Fehler heißt „keine Vorschau“
+        return Preview(None, f"{info}\n{_('No preview')}")
+    return Preview(None, info)
+
+
+def _size_text(nbytes: int) -> str:
+    if nbytes < 1024:
+        return ngettext("{count} byte", "{count} bytes", nbytes).format(count=nbytes)
+    if nbytes < 1024 * 1024:
+        return _("{size} KB").format(size=number(round(nbytes / 1024, 1)))
+    return _("{size} MB").format(size=number(round(nbytes / 1024 / 1024, 1)))
+
+
+def _no_preview(info: str) -> Preview:
+    return Preview(None, f"{info}\n{_('No preview')}")
+
+
+def _raster(path: Path, size: int, info: str) -> Preview:
+    reader = QImageReader(str(path))
+    reader.setAutoTransform(True)                  # EXIF-Lage wie beim Einfügen
+    raw = reader.size()                            # wie gespeichert, vor der Drehung
+    if not raw.isValid() or raw.isEmpty():
+        return _no_preview(info)
+    if raw.width() * raw.height() > MAX_PREVIEW_PIXELS and bytes(reader.format()) != b"jpeg":
+        return _no_preview(f"{info}\n{raw.width()} × {raw.height()} px")
+    reader.setScaledSize(_fit(raw, size))
+    image = reader.read()
+    if image.isNull():
+        return _no_preview(info)
+    turned = reader.transformation() & QImageIOHandler.Transformation.TransformationRotate90
+    full = raw.transposed() if turned else raw
+    return Preview(image, f"{info}\n{full.width()} × {full.height()} px")
+
+
+def _fit(full: QSize, size: int, grow: bool = False) -> QSize:
+    """Größe innerhalb ``size`` × ``size`` mit gleichem Seitenverhältnis (``grow``: auch größer
+    als das Bild); jede Kante mindestens 1."""
+    factor = size / max(full.width(), full.height(), 1)
+    if not grow:
+        factor = min(1.0, factor)
+    return QSize(max(1, round(full.width() * factor)), max(1, round(full.height() * factor)))
+
+
+def _svg(path: Path, size: int, info: str) -> Preview:
+    renderer = QSvgRenderer(str(path))
+    if not renderer.isValid() or renderer.defaultSize().isEmpty():
+        return _no_preview(info)
+    image = QImage(_fit(renderer.defaultSize(), size, grow=True),
+                   QImage.Format.Format_ARGB32_Premultiplied)
+    if image.isNull():
+        return _no_preview(info)
+    image.fill(Qt.GlobalColor.white)
+    painter = QPainter(image)
+    renderer.render(painter)
+    painter.end()
+    return Preview(image, info)
+
+
+def _pdf(path: Path, page: int, size: int, info: str) -> Preview:
+    import pypdfium2 as pdfium
+
+    pdf = pdfium.PdfDocument(path)
+    try:
+        pages = len(pdf)
+        if pages < 1:
+            return _no_preview(info)
+        page = min(max(page, 1), pages)
+        pdf_page = pdf[page - 1]
+        scale = size / max(pdf_page.get_size())
+        image = _qimage(pdf_page.render(scale=scale).to_pil())
+    finally:
+        pdf.close()
+    text = _("Page {page} of {count}").format(page=page, count=pages)
+    return Preview(image, f"{info}\n{text}", pages, page)
+
+
+def _label(path: Path, size: int, info: str, model: str) -> Preview:
+    image = Renderer().render(storage.load(path), model, placeholders=True).image
+    image.thumbnail((size - 2, size - 2))
+    return Preview(_qimage(ImageOps.expand(image.convert("L"), 1, fill=160)), info)   # Etikettrand
+
+
+def _table(path: Path, info: str) -> Preview:
+    table = series.load_table(path, limit=TABLE_ROWS)          # nur der Anfang (große Tabellen)
+    lines = [" | ".join(_cell(c) for c in table.columns)]
+    lines += [" | ".join(_cell(c) for c in row) for row in table.rows]
+    rows = len(table.rows)
+    count = (ngettext("more than {count} row", "more than {count} rows", rows) if table.more
+             else ngettext("{count} row", "{count} rows", rows)).format(count=rows)
+    return Preview(None, f"{info} · {count}\n\n" + "\n".join(lines))
+
+
+def _cell(text: str) -> str:
+    return text if len(text) <= TABLE_CELL else text[:TABLE_CELL - 1] + "…"
+
+
+def _qimage(image: Image.Image) -> QImage:
+    rgb = image.convert("RGB")
+    return QImage(rgb.tobytes(), rgb.width, rgb.height, 3 * rgb.width,
+                  QImage.Format.Format_RGB888).copy()
+
+
+class _Done(QObject):
+    """Ergebnis eines Vorschau-Auftrags (Generation, Preview) – über Threadgrenzen hinweg."""
+    done = Signal(int, object)
+
+
+class _Job(QRunnable):
+    def __init__(self, generation: int, path: str, page: int, model: str, emitter: _Done):
+        super().__init__()
+        self._args = (path, page, PREVIEW_PX, model)
+        self._generation = generation
+        self._emitter = emitter                   # hält den Sender am Leben, bis gemeldet ist
+
+    def run(self) -> None:
+        preview = make_preview(*self._args)       # QImage geht im Hintergrund, QPixmap nicht
+        try:
+            self._emitter.done.emit(self._generation, preview)
+        except RuntimeError:                      # Dialog inzwischen geschlossen
+            pass
+
+
+_pool: QThreadPool | None = None
+
+
+def _threads() -> QThreadPool:
+    """Ein Hintergrund-Thread für alle Vorschauen (nacheinander, nie parallel)."""
+    global _pool
+    if _pool is None:
+        _pool = QThreadPool()
+        _pool.setMaxThreadCount(1)
+    return _pool
+
+
+def wait_for_previews() -> None:
+    """Laufende Vorschauen abwarten (Dialog geschlossen, Tests)."""
+    if _pool is not None:
+        _pool.waitForDone()
+
+
+class PreviewPane(QWidget):
+    """Vorschau rechts im Dialog: Bild, Text, bei PDF mit mehreren Seiten ◀ n/N ▶. Gelesen wird
+    im Hintergrund; jedes ``show_file`` zählt die Generation hoch, ältere Ergebnisse verfallen."""
+
+    def __init__(self, pages: bool = False, model: str = "QL-600"):
+        super().__init__()
+        self._pages_allowed = pages
+        self._model = model
+        self.path: str | None = None
+        self.page = 1
+        self._count = 1
+        self.generation = 0
+        self._emitter = _Done()
+        self._emitter.done.connect(self.show_result)
+        layout = QVBoxLayout(self)
+        layout.setContentsMargins(8, 0, 0, 0)
+        self.setFixedWidth(PREVIEW_PX + 8)            # gleich breit mit und ohne Bild
+        self.image = QLabel()
+        self.image.setFixedSize(PREVIEW_PX, PREVIEW_PX)
+        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
+        self.image.setObjectName("filePreview")
+        self.image.setFrameShape(QFrame.Shape.Box)    # Etiketten sind weiß: Rand zeigt die Fläche
+        layout.addWidget(self.image)
+        self.pages = QWidget()
+        row = QHBoxLayout(self.pages)
+        row.setContentsMargins(0, 0, 0, 0)
+        self.prev = QPushButton("◀")
+        self.next = QPushButton("▶")
+        self.page_label = QLabel()
+        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
+        for widget in (self.prev, self.page_label, self.next):
+            row.addWidget(widget)
+        self.prev.clicked.connect(lambda: self._turn(-1))
+        self.next.clicked.connect(lambda: self._turn(1))
+        self.pages.setToolTip(_("Page of the PDF to insert"))
+        self.pages.hide()
+        layout.addWidget(self.pages)
+        self.info = QLabel()
+        self.info.setWordWrap(True)
+        self.info.setMaximumWidth(PREVIEW_PX)
+        self.info.setTextFormat(Qt.TextFormat.PlainText)
+        self.info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
+        layout.addWidget(self.info, 1)
+
+    def show_file(self, path: str | None) -> None:
+        """Vorschau einer Datei zeigen (neue Datei: erste Seite)."""
+        if path != self.path:
+            self.page = 1
+        self.path = path
+        self._update()
+
+    def _turn(self, step: int) -> None:
+        self.page = min(max(self.page + step, 1), self._count)
+        self._update()
+
+    def _update(self) -> None:
+        self.generation += 1
+        if not self.path:
+            self.show_result(self.generation, Preview(None, ""))
+        elif Path(self.path).suffix.lower() == ".pdf":    # PDFium: nur im GUI-Thread
+            self.show_result(self.generation,
+                             make_preview(self.path, self.page, PREVIEW_PX, self._model))
+        else:
+            _threads().start(_Job(self.generation, self.path, self.page, self._model,
+                                  self._emitter))
+
+    def show_result(self, generation: int, preview: Preview) -> None:
+        """Ergebnis zeigen – nur das des letzten Auftrags."""
+        if generation != self.generation:
+            return
+        self.page, self._count = preview.page, preview.pages
+        if preview.image is not None:
+            self.image.setPixmap(QPixmap.fromImage(preview.image))
+        else:
+            self.image.clear()
+        self.image.setVisible(preview.image is not None)   # Tabelle/Text: oben beginnen
+        self.info.setText(preview.text)
+        many = self._pages_allowed and preview.image is not None and preview.pages > 1
+        self.pages.setVisible(many)
+        self.page_label.setText(f"{preview.page}/{preview.pages}")
+        self.prev.setEnabled(preview.page > 1)
+        self.next.setEnabled(preview.page < preview.pages)
+
+
+class PreviewFileDialog(QFileDialog):
+    """Qt-Dialog „Öffnen“ (nicht der des Systems) mit Vorschau der markierten Datei rechts.
+    ``pages``: bei PDF lässt sich die Seite wählen (``page_for``)."""
+
+    def __init__(self, parent, title: str, folder: str, filters: str, pages: bool = False,
+                 model: str = "QL-600"):
+        super().__init__(parent, title, folder, filters)
+        self.setOption(QFileDialog.Option.DontUseNativeDialog)
+        self.setFileMode(QFileDialog.FileMode.ExistingFile)
+        self.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
+        self.pane = PreviewPane(pages, model)
+        layout = self.layout()
+        if isinstance(layout, QGridLayout):
+            layout.addWidget(self.pane, 0, layout.columnCount(), layout.rowCount(), 1)
+        self._arrange()                         # nach Qts Wiederherstellung des letzten Stands
+        self._pending: str | None = None
+        self._timer = QTimer(self)
+        self._timer.setSingleShot(True)
+        self._timer.setInterval(DELAY_MS)
+        self._timer.timeout.connect(lambda: self.show_preview(self._pending))
+        self.currentChanged.connect(self._current_changed)
+
+    def _arrange(self) -> None:
+        """Platz für die Dateiliste: Orte links schmal, Spalte Name dehnt sich, Typ entfällt,
+        Größe und Datum so breit wie nötig; Fenster höchstens 90 % des Bildschirms."""
+        sidebar = self.findChild(QListView, "sidebar")
+        if sidebar is not None:
+            sidebar.setMinimumWidth(SIDEBAR_PX)
+        self._split()
+        tree = self.findChild(QTreeView, "treeView")
+        if tree is not None:
+            header = tree.header()
+            metrics = tree.fontMetrics()
+            header.setStretchLastSection(False)
+            header.setSectionHidden(2, True)                        # Typ
+            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
+            for column, sample in ((1, "9999,99 KiB"), (3, "00.00.0000 00:00")):
+                title = str(tree.model().headerData(column, Qt.Orientation.Horizontal) or "")
+                width = max(metrics.horizontalAdvance(sample),
+                            header.fontMetrics().horizontalAdvance(title) * 1.15)   # Kopf fett
+                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
+                header.resizeSection(column, round(width) + 28)
+        screen = self.screen().availableGeometry()
+        self.resize(min(DIALOG_SIZE[0], int(screen.width() * 0.9)),
+                    min(DIALOG_SIZE[1], int(screen.height() * 0.9)))
+
+    def _split(self) -> None:
+        splitter = self.findChild(QSplitter, "splitter")
+        if splitter is not None:
+            splitter.setStretchFactor(0, 0)
+            splitter.setStretchFactor(1, 1)
+            splitter.setSizes([SIDEBAR_PX + 20, max(600, splitter.width() - SIDEBAR_PX - 20)])
+
+    def showEvent(self, event) -> None:
+        super().showEvent(event)
+        self._split()                           # erst sichtbar gelten die Breiten
+
+    def done(self, result: int) -> None:
+        wait_for_previews()                     # kein Ergebnis mehr nach dem Schließen
+        super().done(result)
+
+    def _current_changed(self, path: str) -> None:
+        self._pending = path
+        self._timer.start()                     # Pfeiltasten: erst die stehende Auswahl lesen
+
+    def show_preview(self, path: str | None) -> None:
+        self.pane.show_file(path or None)
+
+    def page_for(self, path: str) -> int | None:
+        """Im Dialog gewählte Seite, wenn ``path`` die gezeigte PDF mit Seitenwahl ist."""
+        shown = self.pane.path
+        if not self.pane.pages.isHidden() and shown and Path(shown).resolve() == Path(path).resolve():
+            return self.pane.page
+        return None
+
+
+def _plugins_path() -> str:
+    return QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
+
+
+def system_dialog_available() -> bool:
+    """Bringt diese Qt-Installation das Platform-Theme „xdgdesktopportal“ mit (Dialog des
+    Desktops über das XDG-Portal)? Ohne es gibt es nur den eigenen Dialog."""
+    return any((Path(_plugins_path()) / "platformthemes").glob("*xdgdesktopportal*"))
+
+
+def exec_dialog(dialog: QFileDialog) -> bool:
+    """Dialog zeigen und warten (in Tests ersetzt: kein echter modaler Dialog)."""
+    return bool(dialog.exec())
+
+
+def ask_open(parent, title: str, folder: str, filters: str, *, system: bool = False,
+             pages: bool = False, model: str = "QL-600") -> Chosen | None:
+    """Datei zum Öffnen wählen: eigener Dialog mit Vorschau (``pages``: PDF-Seite im Dialog
+    wählbar) bzw. die Dateiauswahl des Systems (``system``; Seite dann nicht gewählt).
+    None = abgebrochen."""
+    if system:
+        path, _filter = QFileDialog.getOpenFileName(parent, title, folder, filters)
+        return Chosen(path) if path else None
+    dialog = PreviewFileDialog(parent, title, folder, filters, pages, model)
+    try:
+        if not exec_dialog(dialog) or not dialog.selectedFiles():
+            return None
+        path = dialog.selectedFiles()[0]
+        return Chosen(path, dialog.page_for(path) if pages else None)
+    finally:
+        dialog.deleteLater()
diff --git a/src/labelwerk/gui/file_session.py b/src/labelwerk/gui/file_session.py
index 922a01c..98986a8 100644
--- a/src/labelwerk/gui/file_session.py
+++ b/src/labelwerk/gui/file_session.py
@@ -26,6 +26,7 @@ from ..labels import labels_for_model
 from ..render import Renderer
 from ..settings import new_document
 from ..storage import SUFFIX, StorageError, exists, os_reason
+from . import file_dialog
 from .history import restore
 from .panels.file import PREVIEW
 
@@ -68,6 +69,9 @@ class FileSession(QObject):
         dialog = QFileDialog(self.window, _("Save label"), suggested, _file_filter())
         dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
         dialog.setDefaultSuffix(SUFFIX[1:])
+        # eigener Weg: Qts Dialog (fragt selbst vor dem Ersetzen); mit Dateiauswahl des Systems der
+        # des Desktops – save_as fragt dann selbst nach
+        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, not self.window.system_dialog)
         try:
             return dialog.selectedFiles()[0] if dialog.exec() and dialog.selectedFiles() else None
         finally:
@@ -93,9 +97,9 @@ class FileSession(QObject):
                 loaded=loaded, label=label_id))
 
     def ask_open_file(self) -> str | None:
-        path, _filter = QFileDialog.getOpenFileName(self.window, _("Open label"), self._dir,
-                                                    _file_filter())
-        return path or None
+        return file_dialog.ask_open(self.window, _("Open label"), self._dir, _file_filter(),
+                                    system=self.window.system_dialog,
+                                    model=self.window.model)
 
     def ask_save_changes(self) -> str:
         """„save“ | „discard“ | „cancel“."""
@@ -259,6 +263,8 @@ class FileSession(QObject):
             path = path.with_name(path.name + SUFFIX)
             if path.exists() and not self.ask_replace_file(path):   # Dialog sah den Namen ohne
                 return False
+        elif self.window.system_dialog and path.exists() and not self.ask_replace_file(path):
+            return False                    # Dialoge des Desktops fragen nicht immer selbst
         return self._write(path)
 
     def _write(self, path: Path) -> bool:
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index e6a64bb..a70018d 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -11,7 +11,7 @@ from pathlib import Path
 from PIL import Image
 from PySide6.QtCore import QMimeData, Qt, QThreadPool, QTimer
 from PySide6.QtGui import QAction, QActionGroup, QIcon
-from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFileDialog, QFrame,
+from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFrame,
                                QHBoxLayout, QInputDialog, QLineEdit,
                                QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
                                QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
@@ -42,7 +42,7 @@ from ..shortcuts import effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
 from .history import History, restore
-from . import image_import
+from . import file_dialog, image_import
 from .image_import import CLIPBOARD, DROPPED, MIME_OBJECTS, SCREENSHOT, SYMBOL_SOURCE
 from .media_worker import MediaWorker
 from .panels.image import CROP_FAILED
@@ -181,8 +181,9 @@ class MainWindow(QMainWindow):
         start = self._start_tool()
         self.tool_actions[start].setChecked(True)
         self.panels.setCurrentWidget(self._panel_by_key[start])
-        self.apply_hidden_tools()
+        self.apply_hidden_tools(fall_back=False)    # Start-Reiter überspringt ausgeblendete schon
         self.panels.currentChanged.connect(self._remember_tool)    # erst nach dem Start-Reiter
+        self.panels.currentChanged.connect(self._update_tool_buttons)   # SERIE: Knopf bis zum Wechsel
         self._stored_tool = self.settings.last_tool   # zuletzt benutzter Reiter, wie in der Datei
         self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
         spacer = QWidget()
@@ -267,6 +268,9 @@ class MainWindow(QMainWindow):
         self.statusBar().addWidget(self.cancel_button)
         # Stand beim Start: der Einstellungsdialog zeigt danach, was erst ein Neustart ändert
         self._started = started_values(self.settings)
+        # Dateiauswahl des Systems gilt ab dem Start (Platform-Theme der Anwendung) und nur mit Plugin
+        self.system_dialog = (self._started["system_file_dialog"]
+                              and file_dialog.system_dialog_available())
         self._sync_tool()                           # Start im Reiter Text: „Text anlegen“
         self.zoom_label = QLabel()
         for text, delta in (("−", -ZOOM_STEP), ("+", ZOOM_STEP)):
@@ -440,21 +444,29 @@ class MainWindow(QMainWindow):
         zum Schreibmodus, geht es zum zuletzt benutzten sichtbaren Reiter (sonst PAPIER)."""
         self._update_tool_buttons()
         current = self._current_tool()
-        if fall_back and not self._tool_visible(current) and not self._panel_in_use(current):
+        if fall_back and not self._tool_needed(current) and not self._panel_in_use(current):
             self._show_visible_tool()
 
-    def _update_tool_buttons(self) -> None:
+    def _update_tool_buttons(self, _index: int = 0) -> None:
         """Knöpfe der Leiste nach ``hidden_tools`` – SERIE erscheint trotzdem, solange sie
         gebraucht wird (Serie im Etikett, Schnitt-Optionen des Druckers)."""
         for key, action in self.tool_actions.items():
             action.setVisible(self._tool_visible(key))
 
-    def _tool_visible(self, key: str) -> bool:
+    def _tool_needed(self, key: str) -> bool:
+        """Knopf gehört in die Leiste: nicht ausgeblendet – oder SERIE wird gebraucht (Serie im
+        Etikett, Schnitt-Optionen des Druckers)."""
         if key not in self.settings.hidden_tools:
             return True
         return key == "series" and (self.doc.series is not None
                                     or not self.panel("series").driver_box.isHidden())
 
+    def _tool_visible(self, key: str) -> bool:
+        """Wie ``_tool_needed``; SERIE bleibt außerdem, solange ihr Panel zu sehen ist – der Knopf
+        verschwindet erst beim Wechsel (nach ENTFERNEN, Neu, Druckerwechsel)."""
+        return self._tool_needed(key) or (key == "series"
+                                          and self.panels.currentWidget() is self.panel("series"))
+
     def _panel_in_use(self, key: str) -> bool:
         """Gehört das Panel zur Auswahl (Objekt seiner Art zuletzt gewählt) bzw. zum Schreibmodus?"""
         if key == "text" and self.edit_session.active:
@@ -466,7 +478,7 @@ class MainWindow(QMainWindow):
     def _show_visible_tool(self) -> None:
         """Zum zuletzt benutzten sichtbaren Reiter (sonst PAPIER) – wie ein Klick auf ihn."""
         key = self.settings.last_tool
-        if key not in self.tool_actions or not self._tool_visible(key):
+        if key not in self.tool_actions or not self._tool_needed(key):
             key = START_TOOL
         self._tool_triggered(key)
         self.tool_actions[key].setChecked(True)
@@ -830,10 +842,10 @@ class MainWindow(QMainWindow):
         """Dialog für die Tabelle einer Serie (in Tests ersetzbar); beginnt im Ordner der
         aktuellen Tabelle."""
         current = self.doc.series.source if self.doc.series is not None else None
-        path, _filter = QFileDialog.getOpenFileName(
+        return file_dialog.ask_open(
             self, _("Table for the series"), str(Path(current).parent) if current else "",
-            _("Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"))
-        return path or None
+            _("Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"),
+            system=self.system_dialog)
 
     def choose_series_table(self) -> None:
         """TABELLE …: Datei wählen, lesen (Fehler → Meldung, nichts geändert), verknüpfen."""
@@ -1193,16 +1205,19 @@ class MainWindow(QMainWindow):
         """„Bild einfügen …“: Datei wählen; das Bild kommt in die Mitte des bedruckbaren
         Bereichs."""
         path = self.ask_image_file()
-        if path:
-            self.insert_image_files([Path(path)])
+        if path:                                    # im Dialog gewählte PDF-Seite: keine Seitenfrage
+            self.insert_image_files([Path(path)], page=getattr(path, "page", None))
 
     def ask_image_file(self) -> str | None:
-        """Dateidialog „Bilder und PDF“ (in Tests ersetzbar); None = abgebrochen."""
-        path, _filter = QFileDialog.getOpenFileName(self, _("Insert image"), self._image_dir,
-                                              image_import.file_filter())
+        """Dateidialog „Bilder und PDF“ mit Vorschau (in Tests ersetzbar); None = abgebrochen.
+        Ergebnis ``file_dialog.Chosen``: Pfad, bei PDF evtl. mit gewählter Seite (``page``)."""
+        path = file_dialog.ask_open(self, _("Insert image"), self._image_dir,
+                                    image_import.file_filter(),
+                                    system=self.system_dialog, pages=True,
+                                    model=self.model)
         if path:
             self._image_dir = str(Path(path).parent)
-        return path or None
+        return path
 
     def ask_pdf_page(self, path: Path, count: int) -> int | None:
         """Seitenwahl für ein PDF mit mehreren Seiten (in Tests ersetzbar); None = abgebrochen."""
@@ -1755,7 +1770,7 @@ class MainWindow(QMainWindow):
             if saved.printer.startswith(("tcp://", "zpl+tcp://")) and saved.printer not in {
                     p.uri for p in network_printers(network_entries(saved))}:
                 saved.printer = ""                  # Netzwerkdrucker entfernt/geändert: automatisch
-            hidden_changed = saved.hidden_tools != self.settings.hidden_tools
+            hidden_changed = set(saved.hidden_tools) != set(self.settings.hidden_tools)
             self.settings = saved
             self._save_settings()
             from PySide6.QtWidgets import QApplication
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index ab42f12..ea6aefb 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -23,7 +23,8 @@ from ..labels import get_label, labels_for_model
 from ..printer import DEFAULT_MODEL
 from ..printers import SUPPORTED_MODELS, capabilities
 from ..settings import (HIDEABLE_TOOLS, Settings, restart_pending, save_settings,
-                        started_values, valid_host)
+                        start_tool_for, started_values, valid_host)
+from . import file_dialog
 from .tools import TOOLS
 from .widgets import DoubleSpinBox, FontCombo, SpinBox
 
@@ -232,6 +233,15 @@ class SettingsDialog(QDialog):
         self.theme.addItem(_("Classic"), "classic")
         self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
         form.addRow(_("Theme"), self.theme)
+        self.system_file_dialog = QCheckBox(_("Use the file dialog of the system"))
+        self.system_file_dialog.setToolTip(_("Dialog of the desktop instead of the labelwerk dialog "
+                                             "with preview (takes effect after a restart)"))
+        self.system_file_dialog.setChecked(settings.system_file_dialog)
+        if not file_dialog.system_dialog_available():         # Qt-Plugin fehlt: nur eigener Dialog
+            self.system_file_dialog.setEnabled(False)
+            self.system_file_dialog.setToolTip(_("Not available: this Qt installation has no "
+                                                 "module for the file dialog of the system"))
+        form.addRow(self.system_file_dialog)
         self.language = QComboBox()
         system = i18n.system_language()
         self.language.addItem(_("Automatic (system language: {language})").format(
@@ -251,9 +261,10 @@ class SettingsDialog(QDialog):
         self.language.currentIndexChanged.connect(self._update_restart_hint)
         self.zoom.valueChanged.connect(self._update_restart_hint)
         self.start_tool.currentIndexChanged.connect(self._update_restart_hint)
+        self.system_file_dialog.toggled.connect(self._update_restart_hint)
 
-        hint = QLabel(_("“New label” applies to new labels, start zoom, tab at startup and language "
-                        "from the next start, everything else immediately."))
+        hint = QLabel(_("“New label” applies to new labels, start zoom, tab at startup, file dialog "
+                        "and language from the next start, everything else immediately."))
         hint.setWordWrap(True)
         layout.addWidget(hint)
         layout.addStretch()
@@ -444,6 +455,10 @@ class SettingsDialog(QDialog):
     def _family_changed(self, _family) -> None:
         self._family_touched = True
 
+    def _hidden_tools(self) -> list[str]:
+        return [key for key, box in self.tool_boxes.items()
+                if key in HIDEABLE_TOOLS and not box.isChecked()]
+
     def _enable_start_tools(self) -> None:
         """„Reiter beim Start“: ausgeblendete Reiter gesperrt (gekoppelt an die Häkchen)."""
         model = self.start_tool.model()
@@ -456,12 +471,17 @@ class SettingsDialog(QDialog):
         self._enable_start_tools()
         if not self.tool_boxes[key].isChecked() and self.start_tool.currentData() == key:
             self.start_tool.setCurrentIndex(self.start_tool.findData("last"))
+        self._update_restart_hint()             # wirksamer Start-Reiter hängt an den Häkchen
 
     def restart_needed(self) -> bool:
         """Wirkt eine gewählte Einstellung erst nach einem Neustart anders als jetzt? (Liest nur die
         Felder der Neustart-Einstellungen – keine Prüfung anderer Felder.)"""
-        return restart_pending(self.language.currentData(), self.zoom.value(),
-                               self.start_tool.currentData(), self._started)
+        return restart_pending({"language": self.language.currentData(),
+                                "start_zoom": self.zoom.value(),
+                                "start_tool": start_tool_for(self.start_tool.currentData(),
+                                                             self._hidden_tools()),
+                                "system_file_dialog": self.system_file_dialog.isChecked()},
+                               self._started)
 
     def _update_restart_hint(self) -> None:
         self.restart_hint.setVisible(self.restart_needed())
@@ -477,11 +497,11 @@ class SettingsDialog(QDialog):
             fonts_all=self.fonts_all.isChecked(),
             check_media_on_start=self.check_media.isChecked(),
             start_zoom=self.zoom.value(),
-            start_tool=self.start_tool.currentData(),
+            start_tool=start_tool_for(self.start_tool.currentData(), self._hidden_tools()),
             last_tool=self._last_tool,
-            hidden_tools=[key for key, box in self.tool_boxes.items()
-                          if key in HIDEABLE_TOOLS and not box.isChecked()],
+            hidden_tools=self._hidden_tools(),
             theme=self.theme.currentData(),
+            system_file_dialog=self.system_file_dialog.isChecked(),
             image_crop=self.image_crop.isChecked(),
             image_rotate=self.image_rotate.isChecked(),
             image_mode=self.image_mode.currentData(),
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index 1558d2e..dfd4019 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -96,6 +96,8 @@ QCheckBox::indicator { width: 16px; height: 16px; border: 3px solid #000000; bac
 QCheckBox::indicator:checked { background: #000000; }
 QCheckBox:disabled, QRadioButton:disabled, QLabel:disabled { color: #999999; }
 QCheckBox::indicator:disabled { border-color: #CCCCCC; background: #F5F5F5; }
+/* gesperrt, aber gesetzt (z. B. DATEI/PAPIER unter „Reiter in der Leiste“): sichtbar gefüllt */
+QCheckBox::indicator:checked:disabled { border-color: #999999; background: #999999; }
 /* Schieberegler (Schwelle): schwarze Linie, eckiger Griff */
 QSlider::groove:horizontal { height: 3px; background: #000000; }
 QSlider::handle:horizontal { width: 12px; margin: -9px 0; background: #000000; border: none; }
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index 33bdc4f..f018a3f 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -579,6 +579,10 @@ msgstr "Löschen …"
 msgid "Design and print labels (Brother QL)"
 msgstr "Etiketten gestalten und drucken (Brother QL)"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Dialog of the desktop instead of the labelwerk dialog with preview (takes effect after a restart)"
+msgstr "Dialog des Desktops statt des labelwerk-Dialogs mit Vorschau (wirkt nach einem Neustart)"
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Die-cut"
 msgstr "Gestanzt"
@@ -1415,6 +1419,10 @@ msgstr ""
 msgid "No permission for {device} – is the user in group 'lp'?"
 msgstr "Keine Berechtigung für {device} – Benutzer in Gruppe 'lp'?"
 
+#: src/labelwerk/gui/file_dialog.py
+msgid "No preview"
+msgstr "Keine Vorschau"
+
 #: src/labelwerk/gui/main_window.py
 msgid "No printer for this label – choose a printer in the status bar."
 msgstr "Kein Drucker für dieses Etikett – in der Statusleiste einen Drucker wählen."
@@ -1445,6 +1453,10 @@ msgstr "Keine Serie"
 msgid "Not a Zebra address: {uri}"
 msgstr "Keine Zebra-Adresse: {uri}"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Not available: this Qt installation has no module for the file dialog of the system"
+msgstr "Nicht verfügbar: Dieser Qt-Installation fehlt das Modul für die Dateiauswahl des Systems"
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Note: {tools} did not work – the file association may only apply after logging in again."
@@ -1625,6 +1637,15 @@ msgstr "Innenabstand des Rahmens muss zwischen {low} und {high} mm liegen"
 msgid "Page must be at least 1."
 msgstr "Seite muss mindestens 1 sein."
 
+#: src/labelwerk/gui/file_dialog.py
+msgid "Page of the PDF to insert"
+msgstr "Seite der PDF, die eingefügt wird"
+
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "Page {page} of {count}"
+msgstr "Seite {page} von {count}"
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/tools.py
 msgid "Paper"
@@ -2545,6 +2566,10 @@ msgstr "Ungespeicherte Änderungen"
 msgid "Untitled"
 msgstr "Unbenannt"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Use the file dialog of the system"
+msgstr "Dateiauswahl des Systems verwenden"
+
 #. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
 #: src/labelwerk/storage.py
 #, python-brace-format
@@ -2756,6 +2781,13 @@ msgstr "Rand ringsum ab Papierkante in mm – die Streifen, die der Drucker frei
 msgid "model not detected"
 msgstr "Modell nicht erkannt"
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "more than {count} row"
+msgid_plural "more than {count} rows"
+msgstr[0] "mehr als {count} Zeile"
+msgstr[1] "mehr als {count} Zeilen"
+
 #: src/labelwerk/storage.py
 msgid "name too long"
 msgstr "Name zu lang"
@@ -2884,6 +2916,13 @@ msgstr "{app}-Etikett"
 msgid "{checked} of {total} selected"
 msgstr "{checked} von {total} gewählt"
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{count} byte"
+msgid_plural "{count} bytes"
+msgstr[0] "{count} Byte"
+msgstr[1] "{count} Byte"
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "{count} office printer hidden – “labelwerk printers --all” shows it, print with -p cups:NAME"
@@ -2891,6 +2930,13 @@ msgid_plural "{count} office printers hidden – “labelwerk printers --all”
 msgstr[0] "{count} Bürodrucker ausgeblendet – „labelwerk printers --all“ zeigt ihn, drucken mit -p cups:NAME"
 msgstr[1] "{count} Bürodrucker ausgeblendet – „labelwerk printers --all“ zeigt sie, drucken mit -p cups:NAME"
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{count} row"
+msgid_plural "{count} rows"
+msgstr[0] "{count} Zeile"
+msgstr[1] "{count} Zeilen"
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
@@ -3097,6 +3143,16 @@ msgstr "{percent} %"
 msgid "{printer} not found – switch it on or choose another one"
 msgstr "{printer} nicht gefunden – einschalten oder einen anderen wählen"
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{size} KB"
+msgstr "{size} KB"
+
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{size} MB"
+msgstr "{size} MB"
+
 #: src/labelwerk/gui/panels/image.py
 #, python-brace-format
 msgid "{source} · page {page}"
@@ -3154,8 +3210,8 @@ msgid "Ø {width} mm · round"
 msgstr "Ø {width} mm · rund"
 
 #: src/labelwerk/gui/settings_dialog.py
-msgid "“New label” applies to new labels, start zoom, tab at startup and language from the next start, everything else immediately."
-msgstr "„Neues Etikett“ gilt für neue Etiketten, Startzoom, Reiter beim Start und Sprache ab dem nächsten Start, alles andere sofort."
+msgid "“New label” applies to new labels, start zoom, tab at startup, file dialog and language from the next start, everything else immediately."
+msgstr "„Neues Etikett“ gilt für neue Etiketten, Startzoom, Reiter beim Start, Dateiauswahl und Sprache ab dem nächsten Start, alles andere sofort."
 
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index 028b48c..47c81f7 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -570,6 +570,10 @@ msgstr ""
 msgid "Design and print labels (Brother QL)"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Dialog of the desktop instead of the labelwerk dialog with preview (takes effect after a restart)"
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Die-cut"
 msgstr ""
@@ -1398,6 +1402,10 @@ msgstr ""
 msgid "No permission for {device} – is the user in group 'lp'?"
 msgstr ""
 
+#: src/labelwerk/gui/file_dialog.py
+msgid "No preview"
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "No printer for this label – choose a printer in the status bar."
 msgstr ""
@@ -1428,6 +1436,10 @@ msgstr ""
 msgid "Not a Zebra address: {uri}"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Not available: this Qt installation has no module for the file dialog of the system"
+msgstr ""
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "Note: {tools} did not work – the file association may only apply after logging in again."
@@ -1608,6 +1620,15 @@ msgstr ""
 msgid "Page must be at least 1."
 msgstr ""
 
+#: src/labelwerk/gui/file_dialog.py
+msgid "Page of the PDF to insert"
+msgstr ""
+
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "Page {page} of {count}"
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/tools.py
 msgid "Paper"
@@ -2524,6 +2545,10 @@ msgstr ""
 msgid "Untitled"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Use the file dialog of the system"
+msgstr ""
+
 #. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
 #: src/labelwerk/storage.py
 #, python-brace-format
@@ -2735,6 +2760,13 @@ msgstr ""
 msgid "model not detected"
 msgstr ""
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "more than {count} row"
+msgid_plural "more than {count} rows"
+msgstr[0] ""
+msgstr[1] ""
+
 #: src/labelwerk/storage.py
 msgid "name too long"
 msgstr ""
@@ -2863,6 +2895,13 @@ msgstr ""
 msgid "{checked} of {total} selected"
 msgstr ""
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{count} byte"
+msgid_plural "{count} bytes"
+msgstr[0] ""
+msgstr[1] ""
+
 #: src/labelwerk/cli.py
 #, python-brace-format
 msgid "{count} office printer hidden – “labelwerk printers --all” shows it, print with -p cups:NAME"
@@ -2870,6 +2909,13 @@ msgid_plural "{count} office printers hidden – “labelwerk printers --all”
 msgstr[0] ""
 msgstr[1] ""
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{count} row"
+msgid_plural "{count} rows"
+msgstr[0] ""
+msgstr[1] ""
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
@@ -3074,6 +3120,16 @@ msgstr ""
 msgid "{printer} not found – switch it on or choose another one"
 msgstr ""
 
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{size} KB"
+msgstr ""
+
+#: src/labelwerk/gui/file_dialog.py
+#, python-brace-format
+msgid "{size} MB"
+msgstr ""
+
 #: src/labelwerk/gui/panels/image.py
 #, python-brace-format
 msgid "{source} · page {page}"
@@ -3131,7 +3187,7 @@ msgid "Ø {width} mm · round"
 msgstr ""
 
 #: src/labelwerk/gui/settings_dialog.py
-msgid "“New label” applies to new labels, start zoom, tab at startup and language from the next start, everything else immediately."
+msgid "“New label” applies to new labels, start zoom, tab at startup, file dialog and language from the next start, everything else immediately."
 msgstr ""
 
 #: src/labelwerk/gui/settings_dialog.py
diff --git a/src/labelwerk/series.py b/src/labelwerk/series.py
index b04ad67..296cdcd 100644
--- a/src/labelwerk/series.py
+++ b/src/labelwerk/series.py
@@ -57,18 +57,20 @@ class Table:
     rows: list[list[str]]
     sheet: str | None = field(default=None, compare=False)
     sheets: list[str] = field(default_factory=list, compare=False)
+    more: bool = field(default=False, compare=False)   # nur der Anfang gelesen (limit), es folgen weitere
 
 
 # --- Tabellen lesen ----------------------------------------------------------------------------
-def load_table(path: str | Path, sheet: str | None = None) -> Table:
+def load_table(path: str | Path, sheet: str | None = None, limit: int | None = None) -> Table:
     """CSV oder Excel; erste Zeile = Spaltennamen; leere Zeilen entfallen (auch mittendrin).
-    ``sheet``: Excel-Blatt (None = erstes sichtbares Arbeitsblatt)."""
+    ``sheet``: Excel-Blatt (None = erstes sichtbares Arbeitsblatt); ``limit``: nur so viele
+    Zeilen lesen (Vorschau), ``Table.more`` sagt, ob weitere folgen."""
     path = Path(path)
     suffix = path.suffix.lower()
     if suffix in EXCEL_SUFFIXES:
-        return _read_excel(path, sheet)
+        return _read_excel(path, sheet, limit)
     if suffix in CSV_SUFFIXES:
-        return _read_csv(path)
+        return _read_csv(path, limit)
     raise SeriesError(_("{name}: not a table format – CSV or Excel (.xlsx)").format(
         name=path.name or path))
 
@@ -136,22 +138,22 @@ def _separator(text: str) -> str:
     return best
 
 
-def _read_csv(path: Path) -> Table:
+def _read_csv(path: Path, limit: int | None = None) -> Table:
     text = _decode(_read_bytes(path), path)
     if "\x00" in text:                                   # Binärdatei mit falscher Endung
         raise SeriesError(_("{name}: table not readable (not a text file)").format(name=path.name))
     reader = csv.reader(io.StringIO(text, newline=""), delimiter=_separator(text))
-    limit = csv.field_size_limit()
+    field_limit = csv.field_size_limit()
     try:
         csv.field_size_limit(MAX_CELL)
-        return _collect(reader, path)
+        return _collect(reader, path, limit)
     except csv.Error as e:
         if "field larger" in str(e):
             raise SeriesError(_("{name}: cell too long (at most {limit} characters)").format(
                 name=path.name, limit=i18n.thousands(MAX_CELL))) from e
         raise SeriesError(_("{name}: table not readable").format(name=path.name)) from e
     finally:
-        csv.field_size_limit(limit)
+        csv.field_size_limit(field_limit)
 
 
 def _open_excel(path: Path):
@@ -172,7 +174,7 @@ def _open_excel(path: Path):
         raise SeriesError(_("{name}: Excel file not readable").format(name=path.name)) from e
 
 
-def _read_excel(path: Path, sheet: str | None) -> Table:
+def _read_excel(path: Path, sheet: str | None, limit: int | None = None) -> Table:
     book = _open_excel(path)
     try:
         sheets = book.worksheets                          # ohne Diagrammblätter
@@ -192,7 +194,7 @@ def _read_excel(path: Path, sheet: str | None) -> Table:
             width = max(1, min(width, chosen.max_column))
         rows = ([_cell(cell.value, getattr(cell, "number_format", "General")) for cell in row]
                 for row in _limited(chosen.iter_rows(max_col=width), path))
-        table = _collect(rows, path)
+        table = _collect(rows, path, limit)
         table.sheet, table.sheets = chosen.title, [ws.title for ws in sheets]
         return table
     except SeriesError:
@@ -254,11 +256,13 @@ def _number(value: int | float, number_format: str) -> str:
     return f"{value:.15g}".replace(".", i18n.content_decimal()) + suffix
 
 
-def _collect(rows: Iterable[list], path: Path) -> Table:
+def _collect(rows: Iterable[list], path: Path, limit: int | None = None) -> Table:
     """Zeilen einsammeln: Zellen als Text (Umbrüche → Leerzeichen), leere Zellen am Zeilenende
-    und leere Zeilen weg, Spaltennamen eindeutig, Grenzen sofort prüfen."""
+    und leere Zeilen weg, Spaltennamen eindeutig, Grenzen sofort prüfen; ``limit``: nach so
+    vielen Zeilen aufhören (``more``: es folgt noch eine)."""
     header: list[str] | None = None
     data: list[list[str]] = []
+    more = False
     for row in rows:
         cells = [_BREAKS.sub(" ", str(cell)) for cell in row]
         while cells and not cells[-1].strip():
@@ -271,6 +275,9 @@ def _collect(rows: Iterable[list], path: Path) -> Table:
                     name=path.name, limit=MAX_COLUMNS))
             header = cells
             continue
+        if limit is not None and len(data) == limit:
+            more = True
+            break
         if len(data) == MAX_ROWS:
             raise SeriesError(_("{name}: too many rows (at most {limit})").format(
                 name=path.name, limit=i18n.thousands(MAX_ROWS)))
@@ -285,7 +292,7 @@ def _collect(rows: Iterable[list], path: Path) -> Table:
             unique, n = f"{name} ({n})", n + 1
         columns.append(unique)
     width = len(columns)
-    return Table(columns, [(row + [""] * width)[:width] for row in data])
+    return Table(columns, [(row + [""] * width)[:width] for row in data], more=more)
 
 
 # --- Nummerierung und Serie --------------------------------------------------------------------
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 491652a..3653915 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -23,7 +23,7 @@ from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model, is_model
 from .storage import RECENT_FILES
 
 THEMES = ("rawblock", "classic")
-RESTART_KEYS = ("language", "start_zoom", "start_tool")   # wirken erst nach einem Neustart (Hinweis)
+RESTART_KEYS = ("language", "start_zoom", "start_tool", "system_file_dialog")   # erst nach Neustart (Hinweis)
 # Reiter beim Start: „last“ = zuletzt benutzter, sonst Schlüssel der Werkzeuge (gui/tools.py TOOLS)
 START_TOOLS = ("last", "file", "paper", "text", "image", "barcode", "layout", "series")
 # Reiter, die sich ausblenden lassen (DATEI und PAPIER bleiben immer – dort wird das Etikett gewählt)
@@ -47,6 +47,7 @@ class Settings:
     last_tool: str = ""                    # zuletzt benutzter Reiter (still gespeichert)
     hidden_tools: list[str] = field(default_factory=list)   # ausgeblendete Reiter (HIDEABLE_TOOLS)
     theme: str = "rawblock"                # "rawblock" oder "classic" (Qt-Systemstil)
+    system_file_dialog: bool = False       # Dateiauswahl des Desktops (Portal) statt eigener mit Vorschau
     image_crop: bool = True                # Bilder beim Einfügen auf den Inhalt zuschneiden
     image_rotate: bool = False             # Bilder drehen, wenn sie nur gedreht 1:1 passen
     image_mode: str = "line"               # neue Bilder: Strich ("line") oder Foto ("photo")
@@ -86,6 +87,7 @@ def _rules(model: str | None = None) -> dict:
         "check_media_on_start": lambda v: isinstance(v, bool),
         "start_zoom": lambda v: _is_int(v) and 25 <= v <= 400,
         "theme": lambda v: v in THEMES,
+        "system_file_dialog": lambda v: isinstance(v, bool),
         "image_crop": lambda v: isinstance(v, bool),
         "image_rotate": lambda v: isinstance(v, bool),
         "image_mode": lambda v: v in MODES,
@@ -130,29 +132,50 @@ def _printer_options(value: dict, warnings: list[str]) -> dict[str, dict[str, st
     return {k: o for k, o in valid.items() if o}
 
 
+def start_tool_for(start_tool: str, hidden_tools: list[str]) -> str:
+    """Reiter, mit dem labelwerk wirklich startet: ein ausgeblendeter Start-Reiter wird PAPIER
+    (wie ``MainWindow._start_tool``)."""
+    return "paper" if start_tool in hidden_tools else start_tool
+
+
 def started_values(settings: Settings) -> dict:
     """Was beim Start galt (für ``restart_pending``): die gesetzte Sprache und die Neustart-
-    Einstellungen."""
-    return {**{key: getattr(settings, key) for key in RESTART_KEYS}, "language": i18n.language()}
+    Einstellungen (Start-Reiter wirksam, ausgeblendet = PAPIER)."""
+    return {**{key: getattr(settings, key) for key in RESTART_KEYS}, "language": i18n.language(),
+            "start_tool": start_tool_for(settings.start_tool, settings.hidden_tools)}
 
 
-def restart_pending(language: str, start_zoom: int, start_tool: str, started: dict) -> bool:
-    """Wirkt eine Einstellung erst nach einem Neustart anders als jetzt? Sprache wirksam verglichen
-    ("" = Systemsprache), Start-Zoom und Reiter beim Start mit dem Wert beim Start."""
+def restart_pending(values: dict, started: dict) -> bool:
+    """Wirkt eine Einstellung erst nach einem Neustart anders als jetzt? ``values``: gewählte Werte
+    der Neustart-Einstellungen (``RESTART_KEYS``); Sprache wirksam verglichen ("" = Systemsprache),
+    die übrigen mit dem Wert beim Start."""
+    language = values["language"]
     effective = language if language in i18n.available() else i18n.system_language()
-    return (effective != started["language"] or start_zoom != started["start_zoom"]
-            or start_tool != started["start_tool"])
+    return effective != started["language"] or any(
+        values[key] != started[key] for key in RESTART_KEYS if key != "language")
 
 
-def configured_language(path: str | Path | None = None) -> str:
-    """Eingestellte Sprache ("" = System) – vor allem anderen gelesen (die Meldungen beim Laden der
-    Einstellungen kommen schon in dieser Sprache); unlesbar oder ungültig → ""."""
+def _configured(path: str | Path | None, key: str, valid) -> object | None:
+    """Wert ``key`` direkt aus der Datei (vor allem anderen gelesen); unlesbar/ungültig → None."""
     try:
         raw = json.loads(Path(path or settings_path()).read_text(encoding="utf-8"))
     except (OSError, ValueError):
-        return ""
-    value = raw.get("language") if isinstance(raw, dict) else None
-    return value if isinstance(value, str) and value in i18n.available() else ""
+        return None
+    value = raw.get(key) if isinstance(raw, dict) else None
+    return value if valid(value) else None
+
+
+def configured_language(path: str | Path | None = None) -> str:
+    """Eingestellte Sprache ("" = System) – vor allem anderen gelesen (die Meldungen beim Laden der
+    Einstellungen kommen schon in dieser Sprache); unlesbar oder ungültig → ""."""
+    return _configured(path, "language",
+                       lambda v: isinstance(v, str) and v in i18n.available()) or ""
+
+
+def configured_file_dialog(path: str | Path | None = None) -> bool:
+    """Dateiauswahl des Systems eingestellt? – vor dem Start der Oberfläche gelesen (das
+    Platform-Theme von Qt gilt ab dem Anlegen der Anwendung)."""
+    return _configured(path, "system_file_dialog", lambda v: isinstance(v, bool)) is True
 
 
 def settings_path() -> Path:
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2762 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-19-oberflaeche-design.md src/labelwerk/gui/app.py src/labelwerk/gui/file_dialog.py src/labelwerk/gui/file_session.py src/labelwerk/gui/main_window.py src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/series.py src/labelwerk/settings.py tests/gui/test_gui_checkbox_style.py tests/gui/test_gui_file_dialog.py tests/gui/test_gui_hidden_tools.py tests/gui/test_gui_image.py tests/gui/test_gui_language.py tests/gui/test_gui_series.py tests/test_i18n.py tests/test_series.py tests/test_settings.py
git commit -m "Dateiauswahl mit Vorschau (Bilder, SVG, PDF mit Seitenwahl, Etiketten, Tabellen; im Hintergrund), Einstellung „Dateiauswahl des Systems verwenden“ (XDG-Portal nach Neustart), Zusammenspiel mit ausgeblendeten Reitern, gesperrte Häkchen sichtbar, Doku

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Abnahme (manuell, durch den Nutzer)

- [ ] Einstellungen → Ansicht → Reiter in der Leiste: z. B. Barcode und Layout ausblenden; Leiste ohne die Knöpfe; ein Barcode in einer Datei lässt sich anklicken und bearbeiten.
- [ ] Bild einfügen: Vorschau rechts für PNG/JPG/SVG/PDF (Seitenwahl ◀ ▶, danach keine Seitenfrage), Etikett öffnen zeigt das Etikett, Tabelle der Serie die ersten Zeilen.
- [ ] Einstellung „Dateiauswahl des Systems verwenden“ → Neustart → Dialog des Desktops (COSMIC).
