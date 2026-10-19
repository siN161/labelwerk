# Übersetzungen – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** labelwerk spricht Deutsch und Englisch (Oberfläche, Kommandozeile, Meldungen), nimmt die Sprache des Systems, lässt sie in den Einstellungen umstellen (Hinweis „Änderungen erst nach Neustart aktiv“ neben SPEICHERN) und ist für weitere Sprachen vorbereitet.

**Architecture:** `i18n.py` (gettext-Funktionen, eigener .po-Leser, keine neue Abhängigkeit, kein Build-Schritt) im Kern; alle Nutzertexte englisch mit `_()`, Deutsch wörtlich in `po/de.po` (die bestehenden Tests laufen auf Deutsch und beweisen das); `tools/i18n.py` hält Vorlage und Sprachdateien aktuell.

**Tech Stack:** Python ≥ 3.10 (gettext aus der Standardbibliothek nur für `c2py`), PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-19-uebersetzungen-design.md`

**Herkunft des Codes:** Prototyp (Branch `proto-i18n-final`, entstanden in Schritten: Texte umstellen → Sprachwahl/Zahlen/Platzhalter → Symbole/Layout-Test), volle Suite grün mit Exit-Code 0 (2479 → 2529); jeder Schritt von einem Reviewer geprüft und korrigiert (Treibertexte nicht übersetzt, `update` behält Arbeit der Übersetzer, Hinweise für Übersetzer, Escapes wie C, Systemsprache wie GNU, Mehrzahl, englische Formulierungen, Neustart-Hinweis vergleicht mit dem Start und steht neben SPEICHERN, Excel-Zahlen nach Region, Layout-Test mit Auswahl/Symbolfenster/Statusleiste, englische ISO-Namen aus en.json).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Neue Felder im Dokument gehören ins Speicherformat (Schema-Test); Tabellen und Dateien sind fremde Eingabe (nie ein Traceback).
- Keine neue Abhängigkeit; Texte für Nutzer englisch mit `_()`, Deutsch in `po/de.po` – `python tools/i18n.py check` muss „vollständig“ melden.
- Kern bleibt **Qt-frei** (`cups.py`, `zpl.py`, `printers.py`, `labels.py`, `printer.py`, `render.py`, `settings.py`, `cli.py`); kein Test erreicht echte Hardware, CUPS oder das Netz (`send`, `socket.create_connection`, `cups._run` sind in tests/conftest.py ersetzt, sysfs und PPD-Ordner sind leer); **Vorschau = Druck**; **nie den echten Drucker ansprechen** (Rasterdaten prüfen, `send`/`PrintWorker` ersetzen).
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten, ohne echte Dialoge; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen und Kommentare auf Deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Übersetzungen – Englisch als Quellsprache, Deutsch als Übersetzung, Sprachwahl

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `src/labelwerk/barcodes.py`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/clipart.py`
- Modify: `src/labelwerk/clipart_data/LICENSES.md`
- Modify: `src/labelwerk/clipart_data/clipart.zip`
- Modify: `src/labelwerk/cups.py`
- Modify: `src/labelwerk/desktop.py`
- Modify: `src/labelwerk/detect.py`
- Modify: `src/labelwerk/favorites.py`
- Modify: `src/labelwerk/files.py`
- Modify: `src/labelwerk/fonts.py`
- Modify: `src/labelwerk/gui/actions.py`
- Modify: `src/labelwerk/gui/app.py`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/file_session.py`
- Modify: `src/labelwerk/gui/image_import.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/media_worker.py`
- Modify: `src/labelwerk/gui/panels/__init__.py`
- Modify: `src/labelwerk/gui/panels/barcode.py`
- Modify: `src/labelwerk/gui/panels/file.py`
- Modify: `src/labelwerk/gui/panels/image.py`
- Modify: `src/labelwerk/gui/panels/layout.py`
- Modify: `src/labelwerk/gui/panels/paper.py`
- Modify: `src/labelwerk/gui/panels/position.py`
- Modify: `src/labelwerk/gui/panels/series.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/print_worker.py`
- Modify: `src/labelwerk/gui/screenshot.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/gui/symbol_dialog.py`
- Modify: `src/labelwerk/gui/tools.py`
- Modify: `src/labelwerk/gui/widgets.py`
- Create: `src/labelwerk/i18n.py`
- Modify: `src/labelwerk/imaging.py`
- Modify: `src/labelwerk/labels.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/media.py`
- Create: `src/labelwerk/po/README.md`
- Create: `src/labelwerk/po/de.po`
- Create: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/printer.py`
- Modify: `src/labelwerk/printers.py`
- Modify: `src/labelwerk/render.py`
- Modify: `src/labelwerk/series.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `src/labelwerk/shortcuts.py`
- Modify: `src/labelwerk/storage.py`
- Modify: `src/labelwerk/zpl.py`
- Modify: `tests/conftest.py`
- Modify: `tests/gui/conftest.py`
- Modify: `tests/gui/test_gui_barcode.py`
- Modify: `tests/gui/test_gui_editbar.py`
- Create: `tests/gui/test_gui_language.py`
- Modify: `tests/gui/test_gui_layout.py`
- Modify: `tests/gui/test_gui_media.py`
- Modify: `tests/gui/test_gui_printers.py`
- Modify: `tests/gui/test_gui_screenshot.py`
- Modify: `tests/gui/test_gui_symbols.py`
- Create: `tests/gui/test_gui_text_fit.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_clipart.py`
- Create: `tests/test_i18n.py`
- Modify: `tests/test_series.py`
- Modify: `tests/test_shortcuts.py`
- Modify: `tools/clipart/de.json`
- Create: `tools/clipart/en.json`
- Modify: `tools/fetch_clipart.py`
- Create: `tools/i18n.py`

**Interfaces / Produces:** `i18n.py` (`_`, `N_`, `NP_`, `ngettext`, `pgettext`, `set_language`, `language`, `system_language`, `available`, `NAMES`, `DECIMAL`, `parse_po`, `unquote`, `PoError`, `decimal`, `number`, `thousands`, `parse_number`, `content_decimal`, `all_translations`); `src/labelwerk/po/de.po`, `labelwerk.pot`, `README.md`; `tools/i18n.py` (`extract`, `update`, `check`, `read_raw`, `german_leftovers`); alle Nutzertexte englisch mit `_()`; `settings`: `language`, `RESTART_KEYS`, `started_values`, `restart_pending`, `configured_language`; CLI `--lang`, `ARGPARSE_TEXTS`; `gui.app.set_language`; `SettingsDialog(…, started=)`, `language`, `restart_hint`; `series.number_column`, Aliase; `clipart`: `names`/`subgroups`, Katalog neu (`tools/clipart/en.json`); `widgets.DoubleSpinBox` (Komma/Punkt); Layout-Test `tests/gui/test_gui_text_fit.py`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/conftest.py b/tests/conftest.py
index f0bfe91..83d1d5a 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -1,6 +1,19 @@
 import pytest
 
 
+@pytest.fixture(autouse=True)
+def german(monkeypatch):
+    """Tests laufen auf Deutsch (ihre Erwartungen sind die deutschen Texte), auch wenn CLI/GUI die
+    Sprache des Systems nehmen (``LANGUAGE``); wer eine andere Sprache prüft, setzt sie selbst –
+    danach gilt wieder Deutsch."""
+    from labelwerk import i18n
+    monkeypatch.setenv("LANGUAGE", "de")
+    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")      # Gebietsschema „C“ hieße sonst Englisch
+    i18n.set_language("de")
+    yield
+    i18n.set_language("de")
+
+
 @pytest.fixture(autouse=True)
 def isolated_config(monkeypatch, tmp_path_factory):
     """Kein Test liest oder schreibt die echten Einstellungen oder Daten (eigene Symbole) des
diff --git a/tests/gui/conftest.py b/tests/gui/conftest.py
index 43f5f55..f4e5508 100644
--- a/tests/gui/conftest.py
+++ b/tests/gui/conftest.py
@@ -12,6 +12,14 @@ except ImportError:  # reine CLI-Umgebung: GUI-Tests überspringen
 else:
     import pytest
 
+    @pytest.fixture(autouse=True)
+    def german_numbers(qapp):
+        """Zahlenfelder wie in einer deutschen Sitzung (Komma) – passend zur Sprache der Tests."""
+        from PySide6.QtCore import QLocale
+        QLocale.setDefault(QLocale("de"))
+        yield
+        QLocale.setDefault(QLocale("de"))
+
     @pytest.fixture(autouse=True)
     def no_leftover_theme(qapp):
         """Speichern der Einstellungen setzt das Design der ganzen Anwendung – danach zurück,
diff --git a/tests/gui/test_gui_barcode.py b/tests/gui/test_gui_barcode.py
index e40097a..60493a0 100644
--- a/tests/gui/test_gui_barcode.py
+++ b/tests/gui/test_gui_barcode.py
@@ -171,9 +171,9 @@ def test_changing_the_kind_replaces_only_the_sample(qtbot):
 
 def test_module_is_shown_in_millimetres(qtbot):
     win, panel = _with_barcode(qtbot, "code128")
-    assert panel.module.text() == "0.25 mm"
+    assert panel.module.text() == "0,25 mm"                    # Deutsch: Komma
     panel.module.setValue(4)
-    assert win.doc.objects[0].module == 4 and panel.module.text() == "0.34 mm"
+    assert win.doc.objects[0].module == 4 and panel.module.text() == "0,34 mm"
     assert panel.module.valueFromText("0.5") == 6 and panel.module.valueFromText("0,5") == 6
     assert panel.module.valueFromText("x") == 4
     win.undo()
@@ -395,3 +395,10 @@ def test_barcode_error_in_a_series_names_the_row_while_writing(qtbot):
     win.render_now()
     assert "Zeile 1: EAN-8 braucht" in win.result.text()
     assert "Schreibmodus" not in win.result.text()
+
+
+def test_module_in_english_uses_a_point(qtbot):
+    from labelwerk import i18n
+    i18n.set_language("en")
+    win, panel = _with_barcode(qtbot, "code128")
+    assert panel.module.text() == "0.25 mm" and panel.module.valueFromText("0,5") == 6
diff --git a/tests/gui/test_gui_editbar.py b/tests/gui/test_gui_editbar.py
index 9a2ea9f..c7e32ad 100644
--- a/tests/gui/test_gui_editbar.py
+++ b/tests/gui/test_gui_editbar.py
@@ -9,6 +9,7 @@ from PySide6.QtWidgets import QApplication, QToolBar
 
 from labelwerk import shortcuts
 from labelwerk.document import Document, TextObject
+from labelwerk.i18n import _
 from labelwerk.gui.canvas import MM
 from labelwerk.gui.main_window import MainWindow
 from labelwerk.settings import Settings
@@ -99,7 +100,7 @@ def test_edit_bar_buttons_show_own_icons_only(window):
         button = window.edit_bar.widgetForAction(action)
         assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
         assert not action.icon().isNull()
-        name = shortcuts.action(action.objectName()).name
+        name = _(shortcuts.action(action.objectName()).name)
         assert action.toolTip().startswith(name)
     for name in ("tool-select", "tool-text", "edit-cut", "edit-copy", "edit-paste",
                  "edit-undo", "edit-redo"):
diff --git a/tests/gui/test_gui_language.py b/tests/gui/test_gui_language.py
new file mode 100644
index 0000000..1b4edbd
--- /dev/null
+++ b/tests/gui/test_gui_language.py
@@ -0,0 +1,88 @@
+"""Sprache in der GUI: Wahl in den Einstellungen, Neustart-Hinweis, Zahlenfelder je Sprache,
+Oberfläche auf Englisch."""
+from PySide6.QtCore import QLocale
+
+from labelwerk import i18n
+from labelwerk.document import Document, TextObject
+from labelwerk.gui import app as gui_app
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.gui.settings_dialog import SettingsDialog
+from labelwerk.gui.widgets import DoubleSpinBox
+from labelwerk.settings import Settings, configured_language, load_settings, save_settings
+
+
+def _window(qtbot, settings=None):
+    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
+                     settings=settings or Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    win.show()
+    return win
+
+
+def test_language_choice_in_the_settings(qtbot, tmp_path):
+    path = tmp_path / "s.json"
+    dialog = SettingsDialog(Settings(), path)
+    qtbot.addWidget(dialog)
+    assert dialog.language.itemText(0) == "Automatisch (Systemsprache: Deutsch)"
+    assert [dialog.language.itemText(i) for i in range(1, 3)] == ["Deutsch", "English"]
+    assert dialog.restart_hint.isHidden()
+    dialog.language.setCurrentIndex(dialog.language.findData("en"))
+    assert not dialog.restart_hint.isHidden()
+    assert dialog.restart_hint.text() == "Änderungen erst nach Neustart aktiv"
+    dialog.language.setCurrentIndex(0)                    # zurück: Hinweis verschwindet
+    assert dialog.restart_hint.isHidden()
+    dialog.zoom.setValue(150)                             # Start-Zoom wirkt auch erst beim Start
+    assert not dialog.restart_hint.isHidden()
+    dialog.language.setCurrentIndex(dialog.language.findData("en"))
+    dialog.accept()
+    assert load_settings(path).language == "en" and configured_language(path) == "en"
+
+
+def test_restart_notice_stays_next_to_save(qtbot, tmp_path):
+    """Der Hinweis steht unten neben SPEICHERN – auch im Reiter Tastenkürzel sichtbar – und
+    vergleicht mit dem Stand beim Start: wieder zurückgestellt, kein Hinweis."""
+    dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
+                            started={"language": "en", "start_zoom": 200})
+    qtbot.addWidget(dialog)
+    dialog.show()
+    assert dialog.restart_hint.isHidden()
+    dialog.language.setCurrentIndex(dialog.language.findData("de"))
+    dialog.tabs.setCurrentIndex(1)                         # anderer Reiter: Hinweis bleibt sichtbar
+    assert dialog.restart_hint.isVisible()
+    assert dialog.restart_hint.parent() is dialog            # Fußzeile, nicht im Reiter
+    dialog.language.setCurrentIndex(dialog.language.findData("en"))
+    assert dialog.restart_hint.isHidden()
+
+
+def test_saved_but_not_restarted_still_shows_the_notice(qtbot, tmp_path):
+    """Gespeichert, aber noch nicht neu gestartet: beim nächsten Öffnen steht der Hinweis gleich da."""
+    dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
+                            started={"language": "de", "start_zoom": 200})
+    qtbot.addWidget(dialog)
+    assert not dialog.restart_hint.isHidden()
+
+
+def test_start_takes_the_configured_language(tmp_path, monkeypatch):
+    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
+    save_settings(Settings(language="en"))
+    assert gui_app.set_language() == "en" and QLocale().decimalPoint() == "."
+    save_settings(Settings(language=""))                   # Automatisch: LANGUAGE=de (conftest)
+    assert gui_app.set_language() == "de" and QLocale().decimalPoint() == ","
+
+
+def test_number_fields_take_comma_and_point(qtbot):
+    box = DoubleSpinBox()
+    qtbot.addWidget(box)
+    box.setDecimals(1)
+    box.setRange(0, 100)
+    assert box.valueFromText("3.5") == box.valueFromText("3,5") == 3.5
+    assert box.textFromValue(3.5) == "3,5"
+
+
+def test_window_in_english(qtbot):
+    i18n.set_language("en")
+    win = _window(qtbot)
+    win.render_now()
+    texts = {b.text() for b in win.findChildren(type(win.cancel_button)) if b.text()}
+    assert "CANCEL" in texts
+    assert "Etikett" not in win.windowTitle()
diff --git a/tests/gui/test_gui_layout.py b/tests/gui/test_gui_layout.py
index 8d05407..6714691 100644
--- a/tests/gui/test_gui_layout.py
+++ b/tests/gui/test_gui_layout.py
@@ -12,6 +12,7 @@ from labelwerk.document import Document, TextObject
 from labelwerk.gui.main_window import MainWindow
 from labelwerk.gui.panels.layout import LAYOUT_SECTIONS
 from labelwerk.gui.tools import TOOLS
+from labelwerk.i18n import _
 from labelwerk.labels import DPI
 from labelwerk.settings import Settings
 
@@ -79,9 +80,9 @@ def test_selecting_keeps_layout_panel(window):
 
 
 def test_panel_has_sections_like_p_touch(window):
-    titles = [title for title, _ in LAYOUT_SECTIONS]
+    titles = [_(title) for title, __ in LAYOUT_SECTIONS]
     assert titles == ["Gewählte Objekte ausrichten", "Am Papier ausrichten",
-                      "Vergrößern/Verkleinern", "Drehen", "Reihenfolge"]
+                      "Größe ändern", "Drehen", "Reihenfolge"]
     keys = [key for _, row in LAYOUT_SECTIONS for key, _ in row]
     assert set(keys) == set(FROM_ONE + FROM_TWO) and len(keys) == 20
     assert set(_panel(window).buttons) == set(keys)
diff --git a/tests/gui/test_gui_media.py b/tests/gui/test_gui_media.py
index d165dea..65999c5 100644
--- a/tests/gui/test_gui_media.py
+++ b/tests/gui/test_gui_media.py
@@ -208,7 +208,8 @@ def test_media_status_lives_in_footer_not_in_panel(window, qtbot, monkeypatch):
 
 def test_long_media_error_is_elided_in_footer(window):
     from labelwerk.detect import BUSY_MESSAGE
-    window.panel("paper").show_media_error(BUSY_MESSAGE)
+    from labelwerk.i18n import _
+    window.panel("paper").show_media_error(_(BUSY_MESSAGE))
     label = window.media_status
     assert label.sizeHint().width() <= 360
     assert label.text().endswith("…")
diff --git a/tests/gui/test_gui_printers.py b/tests/gui/test_gui_printers.py
index 367d1d7..56ca0b1 100644
--- a/tests/gui/test_gui_printers.py
+++ b/tests/gui/test_gui_printers.py
@@ -341,7 +341,7 @@ def test_removed_network_printer_is_no_longer_chosen(qtbot, monkeypatch, tmp_pat
     class Dialog:
         DialogCode = SettingsDialog.DialogCode
 
-        def __init__(self, settings, model=None, parent=None):
+        def __init__(self, settings, model=None, parent=None, started=None):
             self.saved = Settings(check_media_on_start=False)       # Eintrag entfernt
 
         def exec(self):
diff --git a/tests/gui/test_gui_screenshot.py b/tests/gui/test_gui_screenshot.py
index 5f38e78..dee9850 100644
--- a/tests/gui/test_gui_screenshot.py
+++ b/tests/gui/test_gui_screenshot.py
@@ -8,6 +8,7 @@ from labelwerk import shortcuts
 from labelwerk.document import Document, ImageObject, TextObject
 from labelwerk.gui import main_window
 from labelwerk.gui.main_window import NO_SCREENSHOT, SCREENSHOT, MainWindow
+from labelwerk.i18n import _
 from labelwerk.settings import Settings
 
 MM = 300 / 25.4
@@ -55,7 +56,7 @@ def _start(win, qtbot, portal):
 # --- Aktion und Knopf ----------------------------------------------------------------
 def test_screenshot_action_has_no_default_key(qtbot):
     entry = shortcuts.action("image.screenshot")
-    assert (entry.name, entry.default, entry.scope) == ("Bildschirmfoto einfügen", "", "canvas")
+    assert (_(entry.name), entry.default, entry.scope) == ("Bildschirmfoto einfügen", "", "canvas")
     win = _window(qtbot)
     assert win.shortcut_actions["image.screenshot"] in win.canvas.actions()
     button = win.panel("image").screenshot
@@ -207,7 +208,7 @@ def test_without_portal_window_stays_and_hint_names_clipboard(qtbot):
     win = _window(qtbot)
     win.panel("image").screenshot.click()
     assert win.isVisible()
-    assert win.result.text() == NO_SCREENSHOT and "Strg+V" in NO_SCREENSHOT
+    assert win.result.text() == _(NO_SCREENSHOT) and "Strg+V" in _(NO_SCREENSHOT)
     assert win.result.property("state") == "error"
 
 
diff --git a/tests/gui/test_gui_symbols.py b/tests/gui/test_gui_symbols.py
index f22791e..f557cf6 100644
--- a/tests/gui/test_gui_symbols.py
+++ b/tests/gui/test_gui_symbols.py
@@ -11,9 +11,11 @@ from PySide6.QtWidgets import QApplication
 
 from labelwerk import clipart, shortcuts
 from labelwerk.document import Document, ImageObject, TextObject
+from labelwerk.i18n import _
 from labelwerk.gui.image_import import MIME_SYMBOL
 from labelwerk.gui.main_window import SYMBOL_MM, MainWindow
 from labelwerk.gui.symbol_dialog import EMPTY_OWN, NO_RESULTS, SymbolDialog
+from labelwerk.i18n import _
 from labelwerk.settings import Settings, load_settings
 
 NO_MOD = Qt.KeyboardModifier.NoModifier
@@ -53,7 +55,7 @@ def _ids(dialog):
 # --- Aktion und Fenster ---------------------------------------------------------------
 def test_symbol_action_and_button(qtbot):
     entry = shortcuts.action("image.symbol")
-    assert (entry.name, entry.default, entry.scope) == ("Symbol einfügen …", "", "canvas")
+    assert (_(entry.name), entry.default, entry.scope) == ("Symbol einfügen …", "", "canvas")
     win = _window(qtbot)
     assert win.panel("image").symbol.text() == "SYMBOL"
     dialog = _open(win, qtbot)
@@ -83,7 +85,7 @@ def test_search_spans_the_whole_library(qtbot):
     dialog.search.setText("Haus")
     assert "tabler/outline/home" in _ids(dialog)
     dialog.search.setText("gibtesnichtxyz")
-    assert _ids(dialog) == [] and dialog.empty.text() == NO_RESULTS
+    assert _ids(dialog) == [] and dialog.empty.text() == _(NO_RESULTS)
     assert not dialog.insert.isEnabled()
 
 
@@ -200,7 +202,7 @@ def test_own_folder_empty_hint_and_open_button(qtbot, monkeypatch):
     opened = []
     monkeypatch.setattr(dialog, "open_url", lambda url: opened.append(url.toLocalFile()))
     _show_group(dialog, "Eigene")
-    assert dialog.empty.text() == EMPTY_OWN.format(path=clipart.own_dir())
+    assert dialog.empty.text() == _(EMPTY_OWN).format(path=clipart.own_dir())
     assert dialog.open_folder.isVisible()
     dialog.open_folder.click()
     assert clipart.own_dir().is_dir() and opened == [str(clipart.own_dir())]
@@ -440,7 +442,7 @@ def test_own_svg_with_linked_file_becomes_pixel_image(qtbot):
 
 # --- Bibliotheksarchiv defekt oder fehlend ------------------------------------------
 def _clear_library_caches():
-    for function in (clipart._files, clipart.catalog, clipart._index):
+    for function in (clipart._files, clipart._catalog, clipart._index_for):
         function.cache_clear()
 
 
diff --git a/tests/gui/test_gui_text_fit.py b/tests/gui/test_gui_text_fit.py
new file mode 100644
index 0000000..1b8000c
--- /dev/null
+++ b/tests/gui/test_gui_text_fit.py
@@ -0,0 +1,135 @@
+"""Längere Texte (Englisch/Deutsch) passen: in keinem Panel, im Einstellungsdialog und in der
+Werkzeugleiste ist ein Knopf oder eine Beschriftung abgeschnitten oder ragt über den Rand.
+
+Mit ``LABELWERK_SHOTS=/ordner`` legt der Test Bildschirmfotos je Sprache und Panel ab (Abnahme).
+"""
+import os
+from pathlib import Path
+
+import pytest
+from PySide6.QtCore import QLocale
+from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QLabel, QPushButton,
+                               QRadioButton, QToolButton)
+
+from labelwerk import i18n
+from labelwerk.document import BarcodeObject, Document, ImageObject, Numbering, Series, TextObject
+from labelwerk.gui.app import install_translations, load_theme
+from labelwerk.gui.main_window import PANEL_WIDTH, MainWindow
+from labelwerk.gui.settings_dialog import SettingsDialog
+from labelwerk.gui.tools import TOOLS
+from labelwerk.settings import Settings
+
+SHOTS = os.environ.get("LABELWERK_SHOTS")
+
+
+def _cut_off(root, limit: int | None = None) -> list[str]:
+    """Sichtbare Knöpfe/Beschriftungen, deren Text nicht ganz hineinpasst bzw. die über
+    ``limit`` (rechter Rand in Pixeln, bezogen auf ``root``) hinausragen."""
+    problems = []
+    for widget in root.findChildren(QAbstractButton) + root.findChildren(QLabel):
+        if not widget.isVisibleTo(root) or not widget.text():
+            continue
+        text = widget.text().replace("\n", " ")
+        if isinstance(widget, QLabel) and widget.wordWrap():
+            pass                                           # bricht um
+        elif isinstance(widget, (QPushButton, QToolButton, QCheckBox, QRadioButton, QLabel)) \
+                and widget.width() < widget.minimumSizeHint().width() - 1:
+            problems.append(f"abgeschnitten: {text!r} ({widget.width()} < "
+                            f"{widget.minimumSizeHint().width()})")
+        if limit is not None:
+            right = widget.mapTo(root, widget.rect().topRight()).x()
+            if right > limit + 1:
+                problems.append(f"ragt hinaus: {text!r} (bis {right} > {limit})")
+    return problems
+
+
+@pytest.fixture(params=["en", "de"])
+def language(request, qapp):
+    i18n.set_language(request.param)
+    QLocale.setDefault(QLocale(request.param))
+    translator = install_translations(qapp)                # Qt-Knöpfe („Speichern“) wie im Programm
+    qapp.setStyleSheet(load_theme())                       # RawBlock: Standard-Design
+    yield request.param
+    QLocale.setDefault(QLocale("de"))
+    qapp.setStyleSheet("")
+    if translator is not None:
+        qapp.removeTranslator(translator)
+
+
+def _shot(widget, name: str) -> None:
+    if SHOTS:
+        Path(SHOTS).mkdir(parents=True, exist_ok=True)
+        widget.grab().save(str(Path(SHOTS) / f"{name}.png"))
+
+
+def _window(qtbot, doc, width=1280):
+    win = MainWindow(doc=doc, settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    win.resize(width, 800)
+    win.show()
+    win.render_now()
+    return win
+
+
+def _panels(win, language: str, name: str) -> list[str]:
+    problems = []
+    for tool in TOOLS:
+        win._show_tool(tool.key)
+        QApplication.processEvents()
+        panel = win.panel(tool.key)
+        problems += [f"{language} {name} {tool.key}: {p}" for p in _cut_off(panel, PANEL_WIDTH)]
+        _shot(panel, f"{language}-{name}-{tool.key}")
+    return problems
+
+
+def test_panels_fit(qtbot, language):
+    win = _window(qtbot, Document("62", objects=[TextObject("A")]))
+    problems = _panels(win, language, "text")
+    problems += [f"{language} Werkzeugleiste/Statusleiste: {p}"
+                 for p in _cut_off(win.statusBar()) + _cut_off(win.menuWidget() or win)]
+    _shot(win, f"{language}-fenster")
+    assert problems == []
+
+
+def test_panels_with_selected_objects_fit(qtbot, language):
+    from PIL import Image
+    image = ImageObject.from_image(Image.new("RGB", (200, 100), "black"), 300, "bild.png")
+    doc = Document("62", objects=[BarcodeObject(kind="code128", data="ABC-123", module=2),
+                                  image, TextObject("X{Nummer}")],
+                   series=Series(numbering=Numbering(count=3)))
+    win = _window(qtbot, doc)
+    win.panel("series").refresh()
+    problems = []
+    for index, name in ((0, "barcode"), (1, "bild")):
+        win.canvas.set_selection([index])
+        QApplication.processEvents()
+        assert win.canvas.selection() == [index]
+        problems += _panels(win, language, name)
+    assert problems == []
+
+
+def test_status_bar_fits_at_1024(qtbot, language):
+    win = _window(qtbot, Document("62", objects=[TextObject("A")]), width=1024)
+    win._set_result(i18n._("Settings saved – they apply to new labels."), "ok")
+    QApplication.processEvents()
+    _shot(win.statusBar(), f"{language}-statusleiste-1024")
+    assert _cut_off(win.statusBar()) == []
+
+
+def test_symbol_window_fits(qtbot, language):
+    win = _window(qtbot, Document("62", objects=[TextObject("A")]))
+    win.open_symbols()
+    QApplication.processEvents()
+    _shot(win.symbol_window, f"{language}-symbole")
+    assert _cut_off(win.symbol_window) == []
+
+
+def test_settings_dialog_fits(qtbot, language, tmp_path):
+    dialog = SettingsDialog(Settings(), tmp_path / "s.json")
+    qtbot.addWidget(dialog)
+    dialog.show()
+    dialog.zoom.setValue(150)                              # mit Neustart-Hinweis neben SPEICHERN
+    assert dialog.restart_hint.isVisible()
+    QApplication.processEvents()
+    assert _cut_off(dialog) == []
+    _shot(dialog, f"{language}-einstellungen")
diff --git a/tests/test_cli.py b/tests/test_cli.py
index ade0872..38e257e 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -573,3 +573,11 @@ def test_backend_cups_takes_the_first_queue(cups_queue, capsys):
 def test_cups_is_not_asked_without_need(cups_queue):
     main(["print", "Hallo", "-l", "62", "--preview", "/dev/null"])
     assert not any(c[0] == "lpstat" for c in cups_queue)
+
+
+def test_cli_speaks_english_with_lang(capsys):
+    assert main(["--lang", "en", "print", "X", "-l", "999"]) == 2
+    err = capsys.readouterr().err
+    assert "Unknown label" in err or "unknown" in err.lower()
+    assert main(["print", "X", "-l", "999"]) == 2                 # ohne --lang: Deutsch (conftest)
+    assert "Unbekanntes Etikett" in capsys.readouterr().err
diff --git a/tests/test_clipart.py b/tests/test_clipart.py
index 569787b..3abb64e 100644
--- a/tests/test_clipart.py
+++ b/tests/test_clipart.py
@@ -7,10 +7,11 @@ from PIL import Image
 
 from labelwerk import clipart
 from labelwerk.clipart import ALLOWED_LICENSES, GROUPS, Symbol
+from labelwerk.i18n import _
 
 
 def test_groups_in_fixed_order_with_german_names():
-    assert [(key, name) for key, name in GROUPS] == [
+    assert [(key, _(name)) for key, name in GROUPS] == [     # Namen übersetzt beim Anzeigen
         ("elektro", "Elektro"), ("versand", "Versand"), ("sicherheit", "Sicherheit"),
         ("allgemein", "Allgemein"), ("eigene", "Eigene")]
 
@@ -208,3 +209,29 @@ def test_resolve_skips_unknown_ids():
 def test_symbol_is_hashable_value():
     a = clipart.find("labelwerk/erde")
     assert isinstance(a, Symbol) and {a: 1}[clipart.find("labelwerk/erde")] == 1
+
+
+def test_names_in_the_language_and_search_in_both():
+    from labelwerk import i18n
+    i18n.set_language("en")
+    earth = clipart.find("labelwerk/erde")
+    assert (earth.name, earth.subgroup) == ("Earth", "Electrical")
+    assert clipart.find("iso7000/0621").name == "Fragile"
+    found = [s.id for s in clipart.search("erde", "elektro")]
+    assert found[0] == "labelwerk/erde"                     # deutsch gesucht, englisch angezeigt
+    i18n.set_language("de")
+    earth = clipart.find("labelwerk/erde")
+    assert (earth.name, earth.subgroup) == ("Erde", "Elektro")
+    assert clipart.search("earth", "elektro")[0].id == "labelwerk/erde"
+    assert clipart.search("fragile", "versand")[0].id == "iso7000/0621"
+    tabler = clipart.find("tabler/filled/home")
+    assert tabler.name == "home (gefüllt)" and "home (filled)" in tabler.names
+
+
+def test_every_symbol_has_both_languages():
+    import json
+    import zipfile
+    entries = json.loads(zipfile.ZipFile(clipart.ARCHIVE).read("catalog.json"))["symbols"]
+    for e in entries:
+        assert set(e["names"]) == {"de", "en"} and all(e["names"].values()), e["id"]
+        assert set(e["subgroups"]) == {"de", "en"} and all(e["subgroups"].values()), e["id"]
diff --git a/tests/test_i18n.py b/tests/test_i18n.py
new file mode 100644
index 0000000..1b84556
--- /dev/null
+++ b/tests/test_i18n.py
@@ -0,0 +1,208 @@
+"""Übersetzungen: .po-Leser, Sprachwahl, Zahlen, Vollständigkeit der Sprachdateien."""
+import importlib.util
+import sys
+from pathlib import Path
+
+import pytest
+
+from labelwerk import i18n
+
+ROOT = Path(__file__).resolve().parent.parent
+_spec = importlib.util.spec_from_file_location("i18n_tool", ROOT / "tools" / "i18n.py")
+tool = importlib.util.module_from_spec(_spec)
+sys.modules["i18n_tool"] = tool                  # dataclasses brauchen das Modul
+_spec.loader.exec_module(tool)
+
+PO = r'''
+msgid ""
+msgstr ""
+"Plural-Forms: nplurals=2; plural=(n != 1);\n"
+
+#: src/labelwerk/x.py:1
+msgid "Label"
+msgstr "Etikett"
+
+msgctxt "verb"
+msgid "Cut"
+msgstr "Schneiden"
+
+msgid "Cut"
+msgstr "Ausschneiden"
+
+msgid "{n} label"
+msgid_plural "{n} labels"
+msgstr[0] "{n} Etikett"
+msgstr[1] "{n} Etiketten"
+
+msgid ""
+"Two\n"
+"lines \"quoted\""
+msgstr "Zwei\nZeilen „zitiert“"
+
+msgid "Not yet"
+msgstr ""
+
+#, fuzzy
+msgid "Unsure"
+msgstr "Unsicher"
+
+#~ msgid "Old"
+#~ msgstr "Alt"
+'''
+
+
+def test_parse_po():
+    catalog = i18n.parse_po(PO, "de")
+    assert catalog.messages[("", "Label")] == ["Etikett"]
+    assert catalog.messages[("verb", "Cut")] == ["Schneiden"]
+    assert catalog.messages[("", "Cut")] == ["Ausschneiden"]
+    assert catalog.messages[("", "{n} label")] == ["{n} Etikett", "{n} Etiketten"]
+    assert catalog.messages[("", 'Two\nlines "quoted"')] == ["Zwei\nZeilen „zitiert“"]
+    assert ("", "Not yet") not in catalog.messages and ("", "Unsure") not in catalog.messages
+    assert ("", "Old") not in catalog.messages
+    assert (catalog.plural_index(1), catalog.plural_index(0), catalog.plural_index(5)) == (0, 1, 1)
+
+
+@pytest.mark.parametrize("bad", ['msgid "x"\nmsgstr "y', 'msgid "x"\nfoo "y"', '"lose"',
+                                 'msgid ""\nmsgstr "Plural-Forms: nplurals=2; plural=import os;\\n"'])
+def test_broken_po_is_an_error(bad):
+    with pytest.raises(i18n.PoError):
+        i18n.parse_po(bad)
+
+
+def test_translate_with_context_plural_and_fallback(monkeypatch):
+    monkeypatch.setattr(i18n, "_catalog", i18n.parse_po(PO, "de"))
+    assert i18n._("Label") == "Etikett" and i18n._("Unknown") == "Unknown"
+    assert i18n.pgettext("verb", "Cut") == "Schneiden" and i18n._("Cut") == "Ausschneiden"
+    assert i18n.ngettext("{n} label", "{n} labels", 1).format(n=1) == "1 Etikett"
+    assert i18n.ngettext("{n} label", "{n} labels", 3).format(n=3) == "3 Etiketten"
+    assert i18n.ngettext("{n} box", "{n} boxes", 3) == "{n} boxes"
+    assert i18n.N_("Label") == "Label"
+
+
+@pytest.mark.parametrize("env, code", [({"LANG": "de_DE.UTF-8"}, "de"), ({"LANG": "de_AT"}, "de"),
+                                       ({"LANGUAGE": "fr:de", "LANG": "fr_FR"}, "de"),
+                                       ({"LC_ALL": "C", "LANG": "de_DE.UTF-8"}, "en"),
+                                       ({"LANG": "fr_FR.UTF-8"}, "en"), ({}, "en"),
+                                       ({"LC_MESSAGES": "en_GB.UTF-8", "LANG": "de_DE"}, "en")])
+def test_system_language(env, code):
+    assert i18n.system_language(env) == code
+
+
+def test_set_language_and_numbers(monkeypatch):
+    assert i18n.set_language("en") == "en" and i18n._("Label") == "Label"
+    assert i18n.number(3.5) == "3.5" and i18n.number(2, 1) == "2.0" and i18n.decimal() == "."
+    assert i18n.set_language("de") == "de"
+    assert i18n.number(3.5) == "3,5" and i18n.decimal() == ","
+    assert i18n.set_language("xx") == "en"                     # unbekannt: Englisch
+    monkeypatch.setenv("LANGUAGE", "de")
+    assert i18n.set_language("") == "de"                       # "" = Systemsprache
+    assert i18n.available() == ["de", "en"]
+
+
+def test_broken_language_file_falls_back(tmp_path, monkeypatch, capsys):
+    (tmp_path / "de.po").write_text('msgid "x"\nfoo')
+    monkeypatch.setattr(i18n, "PO_DIR", tmp_path)
+    assert i18n.set_language("de") == "en"
+    assert "unreadable" in capsys.readouterr().err
+
+
+# --- Sprachdateien ------------------------------------------------------------------------------
+def test_every_text_is_translated():
+    assert tool.problems() == []
+
+
+def test_extract_finds_all_kinds(tmp_path):
+    (tmp_path / "pkg").mkdir()
+    (tmp_path / "pkg" / "m.py").write_text(
+        'from labelwerk.i18n import _, N_, ngettext, pgettext\n'
+        'A = N_("Table")\n'
+        'def f(n):\n'
+        '    return _("Hello {name}"), ngettext("{n} file", "{n} files", n), pgettext("verb", "Cut"),'
+        ' _(variable)\n')
+    found = tool.extract(tmp_path / "pkg")
+    assert sorted(found) == [("", "Hello {name}"), ("", "Table"), ("", "{n} file"), ("verb", "Cut")]
+    assert found[("", "{n} file")].plural == "{n} files"
+
+
+def test_placeholders_must_match():
+    assert tool.placeholders("{label!r} passt nicht ({model})") == ["{label!r}", "{model}"]
+    assert tool.placeholders("100 %") == [] and tool.placeholders("{{wörtlich}}") == []
+
+
+def test_numbers_follow_the_language():
+    from labelwerk.labels import format_mm, mm_text
+    from labelwerk.series import numbering_table
+    i18n.set_language("de")
+    assert (format_mm(300), mm_text(101.6), i18n.thousands(10000)) == ("25,4", "101,6", "10.000")
+    i18n.set_language("en")
+    assert (format_mm(300), mm_text(101.6), i18n.thousands(10000)) == ("25.4", "101.6", "10,000")
+    assert i18n.parse_number("3,5") == i18n.parse_number("3.5") == 3.5
+
+
+def test_no_german_text_outside_the_translation():
+    assert tool.german_leftovers() == []
+
+
+def test_english_samples(monkeypatch):
+    """Stichproben: Meldungen auf Englisch, wenn die Sprache Englisch ist."""
+    from labelwerk import zpl
+    from labelwerk.labels import get_label
+    from labelwerk.printer import PrintError, print_image
+    from PIL import Image
+
+    def never(*args):
+        raise AssertionError("darf nichts senden")
+    monkeypatch.setattr(zpl, "send", never)
+    i18n.set_language("en")
+    assert get_label("54x25mm@300").description == "54 × 25 mm · 300 dpi"
+    with pytest.raises(PrintError, match="does not fit the printer"):
+        print_image(Image.new("1", (10, 10), 1), "62", model="zpl:203", printer="zpl+tcp://x")
+
+
+def test_update_keeps_translator_work(tmp_path, monkeypatch):
+    """``update`` behält Kommentare, unsichere (fuzzy) und veraltete Einträge der Übersetzer."""
+    (tmp_path / "pkg").mkdir()
+    (tmp_path / "pkg" / "m.py").write_text('from labelwerk.i18n import _\nA = _("Hello")\nB = _("New")\n')
+    po_dir = tmp_path / "po"
+    po_dir.mkdir()
+    (po_dir / "de.po").write_text('msgid ""\nmsgstr ""\n"Language: de\\n"\n"Plural-Forms: nplurals=2; '
+                                  'plural=(n != 1);\\n"\n\n# geprüft von Anna\n#, fuzzy\nmsgid "Hello"\n'
+                                  'msgstr "Hallo"\n\nmsgid "Gone"\nmsgstr "Weg"\n', encoding="utf-8")
+    monkeypatch.setattr(tool, "PO_DIR", po_dir)
+    monkeypatch.setattr(tool, "POT", po_dir / "labelwerk.pot")
+    monkeypatch.setattr(tool, "SRC", tmp_path / "pkg")
+    monkeypatch.setattr(tool, "extract", lambda src=None, real=tool.extract: real(tmp_path / "pkg"))
+    tool.update()
+    text = (po_dir / "de.po").read_text(encoding="utf-8")
+    assert "# geprüft von Anna\n" in text and "#, fuzzy\nmsgid \"Hello\"\nmsgstr \"Hallo\"" in text
+    assert 'msgid "New"\nmsgstr ""' in text and '#~ msgid "Gone"\n#~ msgstr "Weg"' in text
+
+
+def test_po_escapes_like_c():
+    assert i18n.unquote(r'"a\nb \"q\" \101 \x42 \\"', "") == 'a\nb "q" A B \\'
+    with pytest.raises(i18n.PoError):
+        i18n.unquote('"a \\q"', "")
+    with pytest.raises(i18n.PoError):
+        i18n.unquote('"a" "b"', "")                 # keine Python-Syntax
+
+
+@pytest.mark.parametrize("env, code", [({"LANGUAGE": "de", "LC_ALL": "C"}, "en"),
+                                       ({"LANGUAGE": "de"}, "en"),
+                                       ({"LANGUAGE": "de", "LANG": "en_US.UTF-8"}, "de")])
+def test_system_language_like_gnu(env, code):
+    assert i18n.system_language(env) == code
+
+
+def test_numbers_in_label_content_follow_the_region():
+    assert i18n.content_decimal({"LC_ALL": "de_DE.UTF-8"}) == ","
+    assert i18n.content_decimal({"LANG": "en_US.UTF-8", "LC_NUMERIC": "fr_FR.UTF-8"}) == ","
+    assert i18n.content_decimal({"LANG": "en_GB.UTF-8"}) == "." and i18n.content_decimal({}) == "."
+
+
+def test_restart_pending():
+    from labelwerk.settings import restart_pending
+    started = {"language": "de", "start_zoom": 200}
+    assert not restart_pending("", 200, started)            # Automatisch = Systemsprache (de)
+    assert not restart_pending("de", 200, started)
+    assert restart_pending("en", 200, started) and restart_pending("de", 150, started)
diff --git a/tests/test_series.py b/tests/test_series.py
index fb9f2d6..22b1601 100644
--- a/tests/test_series.py
+++ b/tests/test_series.py
@@ -505,3 +505,31 @@ def test_table_knows_the_sheet_it_came_from(tmp_path):
     table = load_table(path)
     assert table.sheet == "Sichtbar" and table.sheets == ["Versteckt", "Sichtbar"]
     assert load_table(_csv(tmp_path, "A\n1\n")).sheet is None
+
+
+def test_numbering_placeholder_in_every_language():
+    from labelwerk import i18n
+    from labelwerk.document import Numbering
+    from labelwerk.series import fill, missing, numbering_table
+    doc = Document("62", objects=[TextObject("{Nummer}/{Number}")])
+    i18n.set_language("en")
+    table = numbering_table(Numbering(count=2))
+    assert table.columns == ["Number"] and missing(doc, table.columns) == []
+    assert fill(doc, table.columns, table.rows[0]).objects[0].text == "1/1"
+    i18n.set_language("de")
+    table = numbering_table(Numbering(count=2))
+    assert table.columns == ["Nummer"] and fill(doc, table.columns, ["7"]).objects[0].text == "7/7"
+    assert missing(Document("62", objects=[TextObject("{Numero}")]), table.columns) == ["Numero"]
+
+
+def test_unnamed_columns_in_every_language(tmp_path):
+    from labelwerk import i18n
+    from labelwerk.series import fill, load_table, missing
+    path = tmp_path / "t.csv"
+    path.write_text("Klemme;;Ort\nX1;24V;A\n", encoding="utf-8")
+    i18n.set_language("en")
+    table = load_table(path)
+    assert table.columns == ["Klemme", "Column 2", "Ort"]
+    doc = Document("62", objects=[TextObject("{Spalte 2} {Column 2}")])
+    assert missing(doc, table.columns) == []
+    assert fill(doc, table.columns, table.rows[0]).objects[0].text == "24V 24V"
diff --git a/tests/test_shortcuts.py b/tests/test_shortcuts.py
index b25b772..3d44c4d 100644
--- a/tests/test_shortcuts.py
+++ b/tests/test_shortcuts.py
@@ -4,6 +4,7 @@ import re
 import pytest
 
 from labelwerk import shortcuts
+from labelwerk.i18n import _
 from labelwerk.shortcuts import ACTIONS, SCOPES, Action
 
 
@@ -139,7 +140,7 @@ def test_formatting_and_end_edit_belong_to_edit_mode():
     for action_id in ("text.bold", "text.italic", "text.underline", "text.end_edit"):
         assert shortcuts.action(action_id).scope == "edit"
     end = shortcuts.action("text.end_edit")
-    assert (end.name, end.default, end.fixed) == ("Schreibmodus beenden", "Esc", True)
+    assert (_(end.name), end.default, end.fixed) == ("Schreibmodus beenden", "Esc", True)
     assert not shortcuts.action("text.bold").fixed
 
 
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_i18n.py, tests/gui/test_gui_language.py, tests/gui/test_gui_text_fit.py u. a.) schlagen fehl (ImportError `labelwerk.i18n`), dazu angepasste Tests; alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index b244c51..858dc54 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -43,7 +43,13 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   im Druckermenü (nie automatisch), Etiketten/Auflösung aus dem Treiber, Druck als PDF in einem Auftrag, Schnitt-Optionen
   des Treibers im Reiter SERIE; Zebra direkt (ZPL, USB/Netzwerk, Modus Abreißen/Schneiden/Ablösen); CLI -p cups:NAME,
   zpl+file://, zpl+tcp:// mit -m zpl:203.
-- 2479 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Übersetzungen (Etappe 7): Deutsch und Englisch – Quellsprache im Code Englisch (`_()`), Deutsch in
+  `src/labelwerk/po/de.po`; Sprache des Systems, Einstellung „Sprache“ (nach Neustart; farbiger Hinweis
+  „Änderungen erst nach Neustart aktiv“ im Einstellungsfenster neben SPEICHERN, für Sprache und Start-Zoom),
+  CLI `--lang` (auch argparse-Texte); Zahlen mit dem Dezimaltrenner der Sprache (Eingabe Komma und Punkt),
+  Excel-Zahlen im Etikett nach der Region des Systems; `{Nummer}`/`{Number}` und „Spalte n“/„Column n“ in
+  jeder Sprache; Symbole mit deutschen und englischen Namen (Suche in beiden); Layout-Test je Sprache.
+- 2529 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -80,6 +86,14 @@ src/labelwerk/
               check(obj), modules(obj), size(obj) (Druckpunkte, ungedreht), draw(obj) (L, ganze Punkte je Modul, Klartext
               DejaVu Sans ~9 Module, EAN mit verlängerten Randzeichen), quiet_mm, TITLES/SAMPLES/INSERT_MODULE;
               BarcodeError (ValueError, deutsch); Tests lesen jede Art mit zxing-cpp (nur [dev], Python ≥ 3.12)
+  i18n.py     Übersetzungen ohne Qt: _/N_/NP_/ngettext/pgettext, set_language ("" = System wie GNU: Gebiets-
+              schema LC_ALL › LC_MESSAGES › LANG, „C“ = Englisch, sonst LANGUAGE-Liste), available/NAMES/DECIMAL,
+              eigener .po-Leser (parse_po, unquote mit C-Escapes; Kontext, Mehrzahl über gettext.c2py,
+              fuzzy/veraltet zählen nicht, BOM egal), decimal/number/thousands/parse_number, content_decimal
+              (Region für Etikett-Inhalt), all_translations (Namen in jeder Sprache, z. B. Platzhalter);
+              po/<code>.po im Paket, po/labelwerk.pot erzeugt von tools/i18n.py (extract mit „# Translators:“-
+              Hinweisen und python-brace-format, update behält Kommentare/fuzzy/veraltete, check prüft auch
+              Mehrzahlformen, german_leftovers); Anleitung po/README.md
   fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei
   files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
               crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
@@ -131,7 +145,9 @@ src/labelwerk/
               (Ersatz), `last_model` (zuletzt erkannt), `network_printers` ({name, host, model}; valid_host: IPv4/Name ohne
               Port/Schema/Steuerzeichen; Modell auch zpl:…), network_entries(settings); `printer_options` (Modell →
               Druck-Optionen: CUPS-Schnitt-Optionen, Zebra-Modus; je Eintrag geprüft, leerer Wert erlaubt), `zebra_dpi`
-              (0 = erkannt); load_settings(path, model=None): Etikett muss nur ein bekanntes Etikett sein (auch
+              (0 = erkannt), `language` ("" = System); RESTART_KEYS (language, start_zoom), started_values/
+              restart_pending (wirksamer Vergleich mit dem Start), configured_language (vor allem anderen gelesen);
+              load_settings(path, model=None): Etikett muss nur ein bekanntes Etikett sein (auch
               „BxHmm@dpi“; ob es zum Drucker passt, prüfen GUI und CLI)
   storage.py  Etiketten als Datei (*.labelwerk, JSON versioniert, Bilder Base64): to_dict/from_dict, save (atomar), load;
               Schemata SPAN/PARAGRAPH/TEXT/IMAGE/BARCODE/DOCUMENT (jedes Dataclass-Feld, Test hält gleich); Dateien sind fremde Eingabe:
@@ -152,6 +168,8 @@ src/labelwerk/
               placeholders, missing, fill(doc, columns, row, keep) – nur zum Lesen: unveränderte Objekte bleiben dieselben
   favorites.py Favoriten = *.labelwerk in $XDG_DATA_HOME/labelwerk/favoriten: favorites, find, add (overwrite), rename, remove
   clipart.py  Symbol-Bibliothek ohne Qt: catalog() aus clipart_data/clipart.zip (catalog.json + SVGs, einmal ganz gelesen;
+              Einträge mit names/subgroups {de, en} – Anzeige in der Sprache, je Sprache gecacht, Suche über beide;
+              englische Namen in tools/clipart/en.json, Pflicht für jedes Zeichen;
               erzeugt von tools/fetch_clipart.py: Tabler Icons MIT ohne Marken (Kategorien Brand und Laundry/Pflegesymbole + Sperrliste tabler_skip, u. a. Michelin),
               ISO 7000/7010 von Wikimedia Commons nur gemeinfrei/CC0 ohne Einschränkungen (Stand fest: tools/clipart/commons.lock.json,
               --update), eigene Zeichnungen tools/clipart/eigene (CC0); deutsche Namen/Synonyme tools/clipart/de.json;
@@ -249,7 +267,8 @@ src/labelwerk/
                     inzwischen gewechselten Druckers zählt nicht)
     settings_dialog.py Einstellungen: Reiter Allgemein (rollt; inkl. Design, sofort wirksam über app.apply_theme; Drucker:
                     Druckermodell als Ersatz, Zebra-Auflösung, Netzwerkdrucker-Tabelle mit Prüfung der Adresse und Modell
-                    Brother/Zebra; Etikett eines anderen Druckers bleibt) und Tastenkürzel (Konflikte sperren Speichern)
+                    Brother/Zebra; Etikett eines anderen Druckers bleibt; Ansicht: Start-Zoom, Design, Sprache) und
+                    Tastenkürzel (Konflikte sperren Speichern); restart_hint neben SPEICHERN (Stand beim Start: started)
     theme/          QSS-Stylesheet (rawblock.qss)
     icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
   cli.py      labelwerk labels | labelwerk media | labelwerk printers | labelwerk fonts | -m auto (Modell des Zieldruckers:
@@ -264,7 +283,9 @@ nur Entwicklung: `zxing-cpp` (Apache-2.0, liest Barcodes in Tests; ab Python 3.1
 
 ## Konventionen
 - **TDD**: erst fehlschlagenden Test schreiben, dann implementieren. Tests laufen **ohne Drucker** (Rasterdaten prüfen, sysfs per `tmp_path` faken, Druckfunktionen per `monkeypatch` ersetzen). Kein Test darf echte Hardware ansprechen.
-- Benutzer-Meldungen und Kommentare auf Deutsch (vor Veröffentlichung ggf. auf Englisch umstellen).
+- Benutzer-Meldungen **englisch mit `_()`** (benannte Platzhalter, Tabellen mit `N_` und `_()` beim Anzeigen),
+  Deutsch in `po/de.po` (`python tools/i18n.py update`, dann übersetzen); Tests laufen auf Deutsch (conftest).
+  Kommentare und Docstrings vorerst deutsch (vor Veröffentlichung ggf. auf Englisch umstellen).
 - Fehler für Nutzer verständlich abfangen, keine Tracebacks (Exit-Code 2 bei Hardware-/Rechteproblemen).
 
 ## Hardware-Wissen (hart erarbeitet)
@@ -293,7 +314,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Übersetzungen (7), Paketierung (8).
+Nächste Schritte: Paketierung (8).
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -327,7 +348,7 @@ Umsetzung:
    - README: Kompatibilitätstabelle *geprüft* (QL-600 + DK-22205) / *sollte funktionieren* (62-mm-QL ohne Rot: QL-570/580N/700/710W/720NW …) / *nicht unterstützt*; nach Veröffentlichung Vorlage „Druckerbericht“ für Rückmeldungen.
    - Netzwerkdrucker (`tcp://IP`) in der GUI wählbar.
    - Später, nur mit Testgerät: breite QL-1050/1100 (102 mm), Zweifarbdruck QL-8xx (Objektfarbe), P-touch-Bandgeräte PT-… (TZe-Bänder).
-7. Übersetzungen (vor Veröffentlichung, mindestens **Englisch**):
+7. Übersetzungen – umgesetzt (Spec 2026-10-19-uebersetzungen; gettext überall statt Qt-.ts). Ursprüngliche Notiz:
    - GUI: Qt-Übersetzungen (`self.tr(...)`/`QCoreApplication.translate`, `pyside6-lupdate` → `.ts`, `pyside6-lrelease` → `.qm`, `QTranslator` beim Start; Sprache aus dem System, wählbar in den Einstellungen).
    - Kern und CLI: `gettext` (Meldungen wie `TextTooLarge`, Druckerfehler, CLI-Hilfe), gemeinsame Sprachwahl mit der GUI.
    - Quellsprache festlegen (Deutsch beibehalten oder auf Englisch umstellen) – zusammen mit Punkt 9 (README/Kommentare auf Englisch) entscheiden.
diff --git a/README.md b/README.md
index 3f051d3..c62e65f 100644
--- a/README.md
+++ b/README.md
@@ -48,6 +48,13 @@ sudo usermod -aG lp "$USER"
 
 Beim QL-600 muss die **Editor-Lite-LED aus** sein, sonst meldet er sich als USB-Speicher.
 
+## Sprachen
+
+labelwerk spricht Deutsch und Englisch (Oberfläche, Kommandozeile, Meldungen) und nimmt die Sprache des
+Systems; umstellen in Einstellungen → Ansicht → Sprache (wirkt nach einem Neustart) bzw. mit
+`labelwerk --lang en …`. Weitere Sprachen sind willkommen – Anleitung in
+`src/labelwerk/po/README.md`.
+
 ## Benutzung
 
 ```bash
diff --git a/src/labelwerk/barcodes.py b/src/labelwerk/barcodes.py
index e2e37e1..2a8795c 100644
--- a/src/labelwerk/barcodes.py
+++ b/src/labelwerk/barcodes.py
@@ -17,9 +17,11 @@ from PIL import Image, ImageDraw
 from . import fonts
 from .document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, MAX_MODULE, MODULE_LIMIT, QR_LEVELS,
                        ROTATIONS, BarcodeObject)
+from . import i18n
+from .i18n import N_, _
 from .labels import DPI
 
-TITLES = {"qr": "QR-Code", "code128": "Code 128", "code39": "Code 39", "ean13": "EAN-13",
+TITLES = {"qr": N_("QR code"), "code128": "Code 128", "code39": "Code 39", "ean13": "EAN-13",
           "ean8": "EAN-8"}
 SAMPLES = {"qr": "labelwerk", "code128": "ABC-123", "code39": "ABC-123", "ean13": "590123412345",
            "ean8": "9638507"}                 # Beispielinhalt beim Einfügen
@@ -63,35 +65,37 @@ class Code:
 def encode(kind: str, data: str, error: str = "M") -> Code:
     """Inhalt kodieren (``error``: QR-Fehlerkorrektur, sonst ohne Bedeutung)."""
     if not isinstance(kind, str) or kind not in BARCODE_KINDS:
-        raise BarcodeError(f"Unbekannte Barcode-Art {kind!r}")
+        raise BarcodeError(_("Unknown barcode type {kind!r}").format(kind=kind))
     if not isinstance(data, str):
-        raise BarcodeError(f"Inhalt muss Text sein, nicht {type(data).__name__}")
+        raise BarcodeError(_("Content must be text, not {type}").format(type=type(data).__name__))
     if not isinstance(error, str):
-        raise BarcodeError(f"Unbekannte Fehlerkorrektur {error!r} – erlaubt: L, M, Q, H")
+        raise BarcodeError(_("Unknown error correction {error!r} – allowed: L, M, Q, H").format(error=error))
     return _encode(kind, data, error)
 
 
 @lru_cache(maxsize=256)
 def _encode(kind: str, data: str, error: str) -> Code:
     if not data:
-        raise BarcodeError("Barcode ohne Inhalt")
+        raise BarcodeError(_("Barcode without content"))
     if len(data) > MAX_BARCODE_DATA:
-        raise BarcodeError(f"Inhalt zu lang ({len(data)} Zeichen, höchstens {MAX_BARCODE_DATA})")
+        raise BarcodeError(_("Content too long ({count} characters, at most {limit})").format(
+            count=len(data), limit=MAX_BARCODE_DATA))
     if kind == "qr":
         return _qr(data, error)
     if len(data) > MAX_LINEAR:
-        raise BarcodeError(f"{TITLES[kind]}: Inhalt zu lang ({len(data)} Zeichen, höchstens "
-                           f"{MAX_LINEAR})")
+        raise BarcodeError(_("{title}: content too long ({count} characters, at most {limit})").format(
+            title=_(TITLES[kind]), count=len(data), limit=MAX_LINEAR))
     return {"code128": _code128, "code39": _code39, "ean13": _ean13, "ean8": _ean8}[kind](data)
 
 
 def _qr(data: str, error: str) -> Code:
     if error not in QR_LEVELS:
-        raise BarcodeError(f"Unbekannte Fehlerkorrektur {error!r} – erlaubt: L, M, Q, H")
+        raise BarcodeError(_("Unknown error correction {error!r} – allowed: L, M, Q, H").format(error=error))
     try:
         qr = segno.make_qr(data, error=error, boost_error=False)
     except segno.DataOverflowError as e:
-        raise BarcodeError(f"Inhalt zu lang für einen QR-Code (Fehlerkorrektur {error})") from e
+        raise BarcodeError(_("Content too long for a QR code (error correction {error})").format(
+            error=error)) from e
     rows = tuple("".join("1" if v else "0" for v in row) for row in qr.matrix)
     return Code(rows, matrix=True, readable=data)
 
@@ -124,7 +128,8 @@ _ASCII = "".join(chr(c) for c in range(32, 127))
 def _code128(data: str) -> Code:
     for c in data:
         if not 32 <= ord(c) <= 126:
-            raise BarcodeError(f"Code 128 kann „{c}“ nicht darstellen (nur ASCII ohne Umlaute)")
+            raise BarcodeError(_("Code 128 cannot encode “{char}” (ASCII only, no umlauts)").format(
+                char=c))
     values = _code128_values(data)
     check = (values[0] + sum(i * v for i, v in enumerate(values[1:], start=1))) % 103
     bars = "".join(_bars(_C128[v]) for v in [*values, check]) + _bars(_C128_STOP)
@@ -136,8 +141,8 @@ def _code128_values(data: str) -> list[int]:
     C (zwei Ziffern je Wert), Wechsel kostet einen Wert – kürzester Weg über alle Positionen."""
     n = len(data)
     inf = n * 4 + 8
-    cost = [[inf, inf] for _ in range(n + 1)]   # [B, C]: Werte, bis Position i kodiert ist
-    prev: list[list[tuple[int, int] | None]] = [[None, None] for _ in range(n + 1)]
+    cost = [[inf, inf] for __ in range(n + 1)]   # [B, C]: Werte, bis Position i kodiert ist
+    prev: list[list[tuple[int, int] | None]] = [[None, None] for __ in range(n + 1)]
     cost[0] = [1, 1]                            # Startzeichen B bzw. C
     for i in range(n + 1):
         for s in (0, 1):                        # Wechsel an dieser Stelle
@@ -183,8 +188,8 @@ def _code39(data: str) -> Code:
     for c in data:
         upper = c.upper() if "a" <= c <= "z" else c    # Kleinbuchstaben werden groß gedruckt
         if upper not in _C39 or upper == "*":
-            raise BarcodeError(f"Code 39 kann „{c}“ nicht darstellen (erlaubt: 0–9, A–Z, "
-                               f"Leerzeichen und - . $ / + %)")
+            raise BarcodeError(_("Code 39 cannot encode “{char}” (allowed: 0–9, A–Z, space and "
+                                 "- . $ / + %)").format(char=c))
         text += upper
     parts = ["".join(("1" if k % 2 == 0 else "0") * (WIDE if w == "1" else 1)
                      for k, w in enumerate(_C39[c])) for c in f"*{text}*"]
@@ -209,19 +214,21 @@ def check_digit(digits: str) -> int:
 
 
 def _ean_digits(kind: str, data: str) -> str:
-    title, length = TITLES[kind], 13 if kind == "ean13" else 8
+    title, length = _(TITLES[kind]), 13 if kind == "ean13" else 8
     digits = "".join(data.split())              # Leerzeichen zählen nicht
     for c in digits:
         if c not in _DIGITS:
-            raise BarcodeError(f"{title} kann nur Ziffern darstellen, nicht „{c}“")
+            raise BarcodeError(_("{title} can only encode digits, not “{char}”").format(title=title,
+                                                                                    char=c))
     if len(digits) == length - 1:
         return digits + str(check_digit(digits))
     if len(digits) != length:
-        raise BarcodeError(f"{title} braucht {length - 1} oder {length} Ziffern "
-                           f"({len(digits)} eingegeben)")
+        raise BarcodeError(_("{title} needs {short} or {length} digits ({count} entered)").format(
+            title=title, short=length - 1, length=length, count=len(digits)))
     right = check_digit(digits[:-1])
     if int(digits[-1]) != right:
-        raise BarcodeError(f"{title}: Prüfziffer falsch – richtig wäre {right}")
+        raise BarcodeError(_("{title}: wrong check digit – it should be {right}").format(
+            title=title, right=right))
     return digits
 
 
@@ -254,18 +261,21 @@ def _number(v) -> bool:
 def check(obj: BarcodeObject) -> Code:
     """Einstellungen prüfen und den Inhalt kodieren."""
     if obj.rotation not in ROTATIONS:
-        raise BarcodeError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
+        raise BarcodeError(_("Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees").format(
+            rotation=obj.rotation))
     if not isinstance(obj.module, int) or isinstance(obj.module, bool) \
             or not 1 <= obj.module <= MODULE_LIMIT:
-        raise BarcodeError(f"Modulbreite {obj.module!r} ungültig – erlaubt: 1–{MODULE_LIMIT} "
-                           f"Druckpunkte")
+        raise BarcodeError(_("Module width {module!r} invalid – allowed: 1–{limit} dots").format(
+            module=obj.module, limit=MODULE_LIMIT))
     if not isinstance(obj.text, bool):
-        raise BarcodeError(f"Klartext muss an oder aus sein, nicht {obj.text!r}")
+        raise BarcodeError(_("Human-readable text must be on or off, not {text!r}").format(
+            text=obj.text))
     if obj.error not in QR_LEVELS:
-        raise BarcodeError(f"Unbekannte Fehlerkorrektur {obj.error!r} – erlaubt: L, M, Q, H")
+        raise BarcodeError(_("Unknown error correction {error!r} – allowed: L, M, Q, H").format(
+            error=obj.error))
     if obj.kind != "qr" and not (_number(obj.h_mm) and BARCODE_MM[0] <= obj.h_mm <= BARCODE_MM[1]):
-        raise BarcodeError(f"Höhe {obj.h_mm!r} mm ungültig – erlaubt: {BARCODE_MM[0]:g}–"
-                           f"{BARCODE_MM[1]:g} mm")
+        raise BarcodeError(_("Height {height!r} mm invalid – allowed: {low}–{high} mm").format(
+            height=obj.h_mm, low=i18n.number(BARCODE_MM[0]), high=i18n.number(BARCODE_MM[1])))
     return encode(obj.kind, obj.data, obj.error if obj.kind == "qr" else "M")
 
 
@@ -321,7 +331,8 @@ def _layout(obj: BarcodeObject, code: Code, dpi: int = DPI) -> _Layout:
     font, top, bottom, gap = _text_font(code, m, height, dpi)
     bars = height - gap - top - bottom
     if bars < _dots(MIN_BARS_MM, dpi):
-        raise BarcodeError("Barcode zu niedrig für den Klartext – höher ziehen oder Klartext aus")
+        raise BarcodeError(_("Barcode too short for the human-readable text – make it taller or "
+                             "turn the text off"))
     return _Layout(width, height, bars, bars + (gap + top) // 2, font, bars + gap + top)
 
 
@@ -353,7 +364,7 @@ def _text_font(code: Code, m: int, height: int, dpi: int = DPI):
     path = _font_path()
     while True:
         font = fonts.load(path, dots)
-        _, top, _, bottom = font.getbbox(code.glyphs, anchor="ls")
+        __, top, __, bottom = font.getbbox(code.glyphs, anchor="ls")
         top, bottom, gap = -top, max(0, bottom), max(2, dots // 8)
         over = max(font.getlength(text) / ((end - start) * m) for text, start, end in code.text)
         over = max(over, (gap + top + bottom) / (TEXT_SHARE * height))
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index a465c2d..8970f57 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -8,17 +8,18 @@ from pathlib import Path
 
 from PIL import Image
 
-from . import desktop
+from . import desktop, i18n
 from . import printer as prn
 from . import printers
 from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
 from .files import crop, fit_to_label, load_file
 from .fonts import DEFAULT_FAMILY, families
+from .i18n import NP_, N_, _, pgettext
 from .document import ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .labels import format_mm, get_label, labels_for_model
 from .media import MediaError, label_for_media, read_media
 from .render import font_warnings, render_document
-from .settings import load_settings, network_entries
+from .settings import configured_language, load_settings, network_entries
 from .storage import os_reason
 
 
@@ -27,100 +28,139 @@ def _font_size(value: str) -> float | None:
     if value.lower() == "auto":
         return None
     try:
-        size = float(value.replace(",", "."))
+        size = i18n.parse_number(value)
     except ValueError:
         size = 0.0
     if not MIN_PT <= size <= MAX_PT:
-        raise argparse.ArgumentTypeError("Schriftgröße: 'auto' oder 4–100 (pt)")
+        raise argparse.ArgumentTypeError(_("Font size: 'auto' or 4–100 (pt)"))
     return size
 
 
 def _margin(value: str) -> float:
     try:
-        mm = float(value)
+        mm = i18n.parse_number(value)                  # Komma und Punkt
     except ValueError:
         mm = float("nan")
     if not 0 <= mm <= MAX_MARGIN_MM:      # nan fällt hier ebenfalls durch
-        raise argparse.ArgumentTypeError(f"Rand: Zahl von 0 bis {MAX_MARGIN_MM:g} mm")
+        raise argparse.ArgumentTypeError(_("Margin: number from 0 to {max} mm").format(
+            max=i18n.number(MAX_MARGIN_MM)))
     return mm
 
 
 def _add_output_options(p: argparse.ArgumentParser) -> None:
-    p.add_argument("-l", "--label", help="Etikett, z. B. 62, oder auto (eingelegte Rolle vom "
-                                         "Drucker); Standard aus den Einstellungen")
+    p.add_argument("-l", "--label", help=_("label, e.g. 62, or auto (roll loaded in the "
+                                           "printer); default from the settings"))
     p.add_argument("-p", "--printer", default="auto",
-                   help="auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, "
-                        "cups:NAME (Warteschlange, siehe 'labelwerk printers'), "
-                        "zpl+file:///dev/usb/lpN bzw. zpl+tcp://IP (Zebra, mit -m zpl:203/300/600)")
+                   help=_("auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, "
+                          "cups:NAME (queue, see 'labelwerk printers'), "
+                          "zpl+file:///dev/usb/lpN or zpl+tcp://IP "
+                          "(Zebra, with -m zpl:203/300/600)"))
     p.add_argument("-b", "--backend", choices=["linux_kernel", "pyusb", "network", "cups", "zebra"],
-                   help="Standard: aus dem Drucker (tcp:// → network)")
+                   help=_("default: from the printer (tcp:// → network)"))
     p.add_argument("--no-cut", action="store_true",
-                   help="nicht schneiden (Brother; bei CUPS/Zebra stellt das der Treiber bzw. der "
-                        "Modus in den Einstellungen der GUI ein)")
-    p.add_argument("--preview", metavar="PNG", help="nur Vorschau speichern, nicht drucken")
+                   help=_("do not cut (Brother; for CUPS/Zebra the driver or the mode in the "
+                          "GUI settings decides)"))
+    p.add_argument("--preview", metavar="PNG", help=_("only save a preview, do not print"))
 
 
 _UNSET = object()   # -s nicht angegeben (None bedeutet „auto“)
 
 
+# Texte von argparse selbst (Python übersetzt sie nicht): markiert für die Übersetzung, eingesetzt
+# über ``argparse._`` – fehlt eine (andere Python-Version), bleibt sie englisch
+ARGPARSE_TEXTS = (NP_("argparse", "usage: "), NP_("argparse", "positional arguments"),
+                  NP_("argparse", "options"), NP_("argparse", "show this help message and exit"),
+                  NP_("argparse", "%(prog)s: error: %(message)s\n"),
+                  NP_("argparse", "the following arguments are required: %s"),
+                  NP_("argparse", "unrecognized arguments: %s"),
+                  NP_("argparse", "invalid choice: %(value)r (choose from %(choices)s)"),
+                  NP_("argparse", "argument %(argument_name)s: %(message)s"),
+                  NP_("argparse", "expected one argument"),
+                  NP_("argparse", "invalid %(type)s value: %(value)r"))
+
+
+def _translate_argparse() -> None:
+    argparse._ = lambda text: pgettext("argparse", text)
+
+
+def _language(argv: list[str]) -> str:
+    """``--lang de|en`` (vor dem Bau des Parsers: seine Hilfe ist schon übersetzt), sonst die
+    Einstellung, sonst die Sprache des Systems."""
+    for i, arg in enumerate(argv):
+        if arg == "--" or not arg.startswith("-") and argv[i - 1:i] != ["-m"] \
+                and argv[i - 1:i] != ["--model"] and argv[i - 1:i] != ["--lang"]:
+            break                                       # Unterbefehl bzw. Ende der Optionen
+        if arg == "--lang" and i + 1 < len(argv):
+            return argv[i + 1]
+        if arg.startswith("--lang="):
+            return arg.split("=", 1)[1]
+    return configured_language()
+
+
 def _parser() -> argparse.ArgumentParser:
     p = argparse.ArgumentParser(prog=desktop.APP_NAME)
+    p.add_argument("--lang", choices=i18n.available(),
+                   help=_("language of the output (default: setting, otherwise the system)"))
     p.add_argument("-m", "--model", default="auto",
-                   help="auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700, "
-                        "zpl:300 (Zebra), cups:NAME; siehe 'labelwerk printers'")
+                   help=_("auto (default: detected, otherwise from the settings) or e.g. QL-700, "
+                          "zpl:300 (Zebra), cups:NAME; see 'labelwerk printers'"))
     sub = p.add_subparsers(dest="cmd", required=True)
 
-    sub.add_parser("labels", help="Etiketten für das Modell auflisten")
+    sub.add_parser("labels", help=_("list the labels for the model"))
 
-    pr = sub.add_parser("print", help="Text drucken")
-    pr.add_argument("text", help="Text, Zeilenumbruch mit \\n")
+    pr = sub.add_parser("print", help=_("print text"))
+    pr.add_argument("text", help=_("text, line break with \\n"))
     pr.add_argument("-s", "--font-size", type=_font_size, default=_UNSET, metavar="PT",
-                    help="'auto' oder 4–100 pt (Standard aus den Einstellungen)")
-    pr.add_argument("--font", help="Pfad zu einer .ttf-Datei")
+                    help=_("'auto' or 4–100 pt (default from the settings)"))
+    pr.add_argument("--font", help=_("path to a .ttf file"))
     pr.add_argument("--font-family", metavar="NAME",
-                    help="Schriftfamilie, z. B. 'Liberation Sans' (siehe 'labelwerk fonts')")
+                    help=_("font family, e.g. 'Liberation Sans' (see 'labelwerk fonts')"))
     pr.add_argument("--align", choices=ALIGNMENTS, default="center",
-                    help="Textposition: left, center (Standard), right, justify")
+                    help=_("text position: left, center (default), right, justify"))
     pr.add_argument("--bold", action=argparse.BooleanOptionalAction, default=True,
-                    help="fett (Standard) bzw. --no-bold")
-    pr.add_argument("--italic", action="store_true", help="kursiv")
-    pr.add_argument("--underline", action="store_true", help="unterstrichen")
+                    help=_("bold (default) or --no-bold"))
+    pr.add_argument("--italic", action="store_true", help=_("italic"))
+    pr.add_argument("--underline", action="store_true", help=_("underlined"))
     pr.add_argument("--orientation", choices=ORIENTATIONS,
-                    help="vertical: Hochformat (Leserichtung quer zum Band), horizontal: Querformat (längs zum Band); Standard aus den Einstellungen")
+                    help=_("vertical: portrait (reading direction across the tape), horizontal: "
+                           "landscape (along the tape); default from the settings"))
     pr.add_argument("--margin", type=_margin, metavar="MM",
-                    help="Rand ringsum ab Papierkante in mm (Standard aus den Einstellungen)")
+                    help=_("margin all around from the paper edge in mm (default from the "
+                           "settings)"))
     _add_output_options(pr)
 
-    pf = sub.add_parser("print-file", help="PDF/Bild 1:1 drucken")
-    pf.add_argument("file", help="PDF, PNG oder JPG")
-    pf.add_argument("--page", type=int, default=1, help="PDF-Seite (Standard 1)")
+    pf = sub.add_parser("print-file", help=_("print a PDF/image 1:1"))
+    pf.add_argument("file", help=_("PDF, PNG or JPG"))
+    pf.add_argument("--page", type=int, default=1, help=_("PDF page (default 1)"))
     pf.add_argument("--fit", action="store_true",
-                    help="verkleinern, falls zu groß (Codes evtl. nicht mehr lesbar)")
+                    help=_("shrink if too large (codes may no longer be readable)"))
     pf.add_argument("--rotate", default="auto", choices=["auto", "0", "90", "180", "270"],
-                    help="auto (Standard: nur drehen wenn nötig) oder Grad im Uhrzeigersinn")
+                    help=_("auto (default: rotate only if needed) or degrees clockwise"))
     _add_output_options(pf)
 
-    sub.add_parser("media", help="eingelegte Rolle vom Drucker abfragen (druckt nichts)")
-    sub.add_parser("printers", help="gefundene Drucker und unterstützte Modelle auflisten")
-    sub.add_parser("fonts", help="installierte Schriftfamilien auflisten")
+    sub.add_parser("media", help=_("query the roll loaded in the printer (prints nothing)"))
+    sub.add_parser("printers", help=_("list found printers and supported models"))
+    sub.add_parser("fonts", help=_("list installed font families"))
 
-    di = sub.add_parser("install-desktop", help="labelwerk-gui im Starter (Super-Taste) eintragen")
-    di.add_argument("--remove", action="store_true", help="Eintrag und Icon wieder entfernen")
+    di = sub.add_parser("install-desktop",
+                        help=_("add labelwerk-gui to the launcher (Super key)"))
+    di.add_argument("--remove", action="store_true", help=_("remove the entry and icon again"))
     return p
 
 
-_HARDWARE_HINT = "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'"
+# kein Drucker gefunden, je Backend – übersetzt beim Melden (``{not_found}``: PRINTER_NOT_FOUND)
 _NOT_DETECTED = {
-    "linux_kernel": f"{PRINTER_NOT_FOUND}\nManuell angeben mit -p file:///dev/usb/lpN",
-    "pyusb": "Brother-Drucker per USB (pyusb) nicht gefunden.\n"
-             f"{_HARDWARE_HINT}, Zugriff auf den USB-Bus (udev-Regel).\n"
-             "Manuell angeben mit -p usb://0x04f9:0xPID",
-    "network": "Kein Netzwerkdrucker eingetragen (Einstellungen der GUI).\n"
-               "Adresse angeben mit -p tcp://IP",
-    "cups": "Keine CUPS-Warteschlange gefunden (Drucker in der Druckerverwaltung einrichten).\n"
-            "Angeben mit -p cups:NAME",
-    "zebra": "Kein Zebra-Drucker gefunden.\n"
-             "Angeben mit -p zpl+file:///dev/usb/lpN bzw. -p zpl+tcp://IP und -m zpl:203",
+    "linux_kernel": N_("{not_found}\nSpecify manually with -p file:///dev/usb/lpN"),
+    "pyusb": N_("Brother printer not found via USB (pyusb).\n"
+                "Check: switched on, Editor Lite LED off, 'lsusb', access to the USB bus "
+                "(udev rule).\n"
+                "Specify manually with -p usb://0x04f9:0xPID"),
+    "network": N_("No network printer configured (GUI settings).\n"
+                  "Specify the address with -p tcp://IP"),
+    "cups": N_("No CUPS queue found (set up the printer in the printer settings).\n"
+               "Specify with -p cups:NAME"),
+    "zebra": N_("No Zebra printer found.\n"
+                "Specify with -p zpl+file:///dev/usb/lpN or -p zpl+tcp://IP and -m zpl:203"),
 }
 
 
@@ -160,9 +200,9 @@ def _resolve_model(model: str, target: printers.Printer | None, settings) -> str
     Einstellungen; ein angegebenes muss bekannt sein."""
     if model != "auto":
         if not printers.is_model(model):
-            raise ValueError(f"Unbekanntes Druckermodell {model!r} – erlaubt: "
-                             f"{', '.join(printers.SUPPORTED_MODELS)}, zpl:203/300/600 oder "
-                             "cups:NAME")
+            raise ValueError(_("Unknown printer model {model!r} – allowed: {models}, "
+                               "zpl:203/300/600 or cups:NAME").format(
+                model=model, models=", ".join(printers.SUPPORTED_MODELS)))
         return model
     return printers.effective_model(target, settings.printer_model, settings.last_model)
 
@@ -171,17 +211,18 @@ def _auto_label(model: str, target: printers.Printer | None) -> str:
     """``-l auto``: Etikett zur eingelegten Rolle (Statusabfrage per USB beim Zieldrucker) – sonst
     ValueError."""
     if target is not None and target.source != "usb":
-        raise ValueError("-l auto (Rolle abfragen) geht nur bei Druckern per USB.")
+        raise ValueError(_("-l auto (query the roll) only works with printers via USB."))
     printer = target.uri if target is not None and target.uri.startswith("file://") \
         else find_brother_lp()
     if printer is None:
-        raise ValueError(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
+        raise ValueError(_(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND))
     media = read_media(printer)
     if media.kind == "none":
-        raise ValueError("Keine Rolle eingelegt.")
+        raise ValueError(_("No roll loaded."))
     label = label_for_media(media, model)
     if label is None:
-        raise ValueError(f"Kein Etikett für die eingelegte Rolle ({media.describe()}) beim {model}.")
+        raise ValueError(_("No label for the loaded roll ({media}) on the {model}.").format(
+            media=media.describe(), model=model))
     return label
 
 
@@ -206,13 +247,13 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
     if args.printer == "auto":
         args.printer = args.target.uri if args.target is not None else None
         if args.printer is None and args.settings.printer:
-            print(f"Gewählter Drucker {args.settings.printer} nicht gefunden – einschalten oder "
-                  f"mit -p angeben.", file=sys.stderr)
+            print(_("Chosen printer {printer} not found – switch it on or specify it with -p.")
+                  .format(printer=args.settings.printer), file=sys.stderr)
             return 2
         if args.printer is None:
             busy = args.backend in (None, "linux_kernel") and brother_busy()
-            print(BUSY_MESSAGE if busy else _NOT_DETECTED[args.backend or "linux_kernel"],
-                  file=sys.stderr)
+            print(_(BUSY_MESSAGE) if busy else _(_NOT_DETECTED[args.backend or "linux_kernel"])
+                  .format(not_found=_(PRINTER_NOT_FOUND)), file=sys.stderr)
             return 2
 
     try:
@@ -225,9 +266,9 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
         return 2
     ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
     if status.get("job"):
-        print(f"An CUPS übergeben (Auftrag {status['job']})")
+        print(_("Handed over to CUPS (job {job})").format(job=status["job"]))
     else:
-        print(f"Status: {status.get('outcome')}")
+        print(_("Status: {outcome}").format(outcome=status.get("outcome")))
     return 0 if ok else 1
 
 
@@ -237,27 +278,28 @@ def _show_printers(model: str) -> int:
     found = _all_printers(load_settings())
     for p in found:
         caps = printers.capabilities(p.model) if p.model else None
-        state = ("Modell nicht erkannt" if caps is None else
-                 "geprüft" if caps.tested else printers.UNTESTED_HINT)
+        state = (_("model not detected") if caps is None else
+                 _("tested") if caps.tested else _(printers.UNTESTED_HINT))
         print(f"{p.name:<28} {p.uri:<30} {state}")
     if not found:
-        print("Kein Drucker gefunden.")
-    print(f"Wirksames Modell: {model}")
-    print("Unterstützt: " + ", ".join(
-        f"{m}{'' if printers.capabilities(m).tested else ' (ungeprüft)'}"
-        for m in printers.SUPPORTED_MODELS)
-          + ", Zebra zpl:203/300/600 (ungeprüft), CUPS-Warteschlangen cups:NAME (ungeprüft)")
+        print(_("No printer found."))
+    print(_("Effective model: {model}").format(model=model))
+    models = ", ".join(m if printers.capabilities(m).tested
+                       else _("{model} (untested)").format(model=m)
+                       for m in printers.SUPPORTED_MODELS)
+    print(_("Supported: {models}, Zebra zpl:203/300/600 (untested), CUPS queues cups:NAME "
+            "(untested)").format(models=models))
     return 0
 
 
 def _show_media(model: str, target: printers.Printer | None) -> int:
     if target is not None and target.source != "usb":
-        print("Rolle abfragen geht nur bei Druckern per USB.", file=sys.stderr)
+        print(_("Querying the roll only works with printers via USB."), file=sys.stderr)
         return 2
     printer = target.uri if target is not None and target.uri.startswith("file://") \
         else find_brother_lp()
     if printer is None:
-        print(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND, file=sys.stderr)
+        print(_(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND), file=sys.stderr)
         return 2
     try:
         media = read_media(printer)
@@ -265,8 +307,13 @@ def _show_media(model: str, target: printers.Printer | None) -> int:
         print(e, file=sys.stderr)
         return 2
     label = label_for_media(media, model)
-    hint = f" (Etikett {label})" if label else " (kein passendes Etikett)" if media.kind != "none" else ""
-    print(f"Eingelegt: {media.describe()}{hint}")
+    if label:
+        text = _("Loaded: {media} (label {label})")
+    elif media.kind != "none":
+        text = _("Loaded: {media} (no matching label)")
+    else:
+        text = _("Loaded: {media}")
+    print(text.format(media=media.describe(), label=label))
     return 0
 
 
@@ -281,8 +328,9 @@ def _apply_settings(args: argparse.Namespace) -> None:
         args.label = _auto_label(args.model, args.target)
     if hasattr(args, "label") and get_label(args.label).id not in {   # unbekannt: ValueError
             label.id for label in labels_for_model(args.model)}:
-        raise ValueError(f"Etikett {args.label!r} passt nicht zum {args.model} – siehe "
-                         f"'labelwerk -m {args.model} labels'")
+        raise ValueError(_("Label {label!r} does not fit the {model} – see "
+                           "'labelwerk -m {model} labels'").format(label=args.label,
+                                                                   model=args.model))
     if args.cmd == "print":
         args.orientation = args.orientation or settings.orientation
         args.margin = settings.margin_mm if args.margin is None else args.margin
@@ -298,9 +346,11 @@ def _install_desktop(remove: bool) -> int:
         try:
             removed = desktop.uninstall(data, update=False)
         except OSError as e:
-            print(f"labelwerk wurde nicht entfernt ({os_reason(e)}).", file=sys.stderr)
+            print(_("labelwerk was not removed ({reason}).").format(reason=os_reason(e)),
+                  file=sys.stderr)
             return 2
-        print("\n".join(f"Entfernt: {p}" for p in removed) or "Nichts zu entfernen.")
+        print("\n".join(_("Removed: {path}").format(path=p) for p in removed)
+              or _("Nothing to remove."))
         if removed:
             _report_update(desktop.update_databases(data))
         return 0
@@ -311,23 +361,27 @@ def _install_desktop(remove: bool) -> int:
         print(e, file=sys.stderr)
         return 2
     except OSError as e:
-        print(f"labelwerk wurde nicht eingetragen ({os_reason(e)}).", file=sys.stderr)
+        print(_("labelwerk was not added ({reason}).").format(reason=os_reason(e)),
+              file=sys.stderr)
         return 2
     for path in paths:
-        print(f"Installiert: {path}")
+        print(_("Installed: {path}").format(path=path))
     _report_update(desktop.update_databases(data))
-    print("labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden); "
-          "Doppelklick auf eine .labelwerk-Datei öffnet sie.")
+    print(_("labelwerk now appears in the launcher (wait a moment or log in again if needed); "
+            "double-clicking a .labelwerk file opens it."))
     return 0
 
 
 def _report_update(failed: list[str]) -> None:
     if failed:
-        print(f"Hinweis: {', '.join(failed)} hat nicht geklappt – Dateizuordnung gilt ggf. erst "
-              f"nach neuer Anmeldung.", file=sys.stderr)
+        print(_("Note: {tools} did not work – the file association may only apply after logging "
+                "in again.").format(tools=", ".join(failed)), file=sys.stderr)
 
 
 def main(argv: list[str] | None = None) -> int:
+    argv = sys.argv[1:] if argv is None else argv
+    i18n.set_language(_language(argv))
+    _translate_argparse()
     args = _parser().parse_args(argv)
     settings = load_settings()
     args.settings = settings
@@ -355,7 +409,7 @@ def main(argv: list[str] | None = None) -> int:
         return 0
 
     if args.cmd == "print" and args.font and args.font_family:
-        print("--font (Schriftdatei) und --font-family schließen sich aus.", file=sys.stderr)
+        print(_("--font (font file) and --font-family exclude each other."), file=sys.stderr)
         return 2
     try:
         _apply_settings(args)
@@ -373,11 +427,12 @@ def main(argv: list[str] | None = None) -> int:
         try:
             img.save(args.preview)
         except (OSError, ValueError) as e:
-            print(f"Vorschau kann nicht gespeichert werden: {args.preview} ({e})", file=sys.stderr)
+            print(_("Preview cannot be saved: {path} ({error})").format(path=args.preview, error=e),
+                  file=sys.stderr)
             return 2
         dpi = get_label(args.label).dpi
-        print(f"Vorschau: {args.preview} ({format_mm(img.width, dpi)} × "
-              f"{format_mm(img.height, dpi)} mm)")
+        print(_("Preview: {path} ({width} × {height} mm)").format(
+            path=args.preview, width=format_mm(img.width, dpi), height=format_mm(img.height, dpi)))
         return 0
 
     return _send(img, args)
diff --git a/src/labelwerk/clipart.py b/src/labelwerk/clipart.py
index 5351ce6..f41e973 100644
--- a/src/labelwerk/clipart.py
+++ b/src/labelwerk/clipart.py
@@ -16,13 +16,18 @@ from dataclasses import dataclass
 from functools import lru_cache
 from pathlib import Path
 
+from . import i18n
+from .i18n import N_, _
+
 ARCHIVE = Path(__file__).with_name("clipart_data") / "clipart.zip"
 LICENSES = ARCHIVE.with_name("LICENSES.md")
-GROUPS = (("elektro", "Elektro"), ("versand", "Versand"), ("sicherheit", "Sicherheit"),
-          ("allgemein", "Allgemein"), ("eigene", "Eigene"))
+# Anzeigenamen mit N_ markiert: beim Anzeigen ``_(name)``
+GROUPS = (("elektro", N_("Electrical")), ("versand", N_("Shipping")), ("sicherheit", N_("Safety")),
+          ("allgemein", N_("General")), ("eigene", N_("My symbols")))
 ALLOWED_LICENSES = frozenset({"MIT", "Public domain", "CC0"})
 OWN_SUFFIXES = (".svg", ".png")
-OWN_LICENSE = "eigene Datei"
+OWN_LICENSE = N_("your own file")       # übersetzt in ``own_symbols``
+OWN_SUBGROUP = N_("My symbols")
 RECENT_LIMIT = 24
 _UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
 _WORD = re.compile(r"\w+")
@@ -32,14 +37,16 @@ _WORD = re.compile(r"\w+")
 class Symbol:
     id: str              # „labelwerk/erde“, „iso7010/W012“, „tabler/outline/home“, „ordner/Datei.svg“
     group: str           # Schlüssel aus GROUPS
-    subgroup: str        # z. B. „Warnzeichen“, „Gebäude“
-    name: str            # deutscher Anzeigename
+    subgroup: str        # z. B. „Warnzeichen“, „Gebäude“ (in der Sprache von labelwerk)
+    name: str            # Anzeigename in der Sprache von labelwerk
     keywords: tuple[str, ...]
     file: str            # Pfad im Archiv bzw. im eigenen Ordner
     source: str
     url: str
     author: str
     license: str
+    names: tuple[str, ...] = ()   # Name in jeder Sprache (Suche findet alle)
+    subgroups: tuple[str, ...] = ()   # Untergruppe in jeder Sprache (ebenso)
 
 
 def _fold(text: str) -> str:
@@ -54,13 +61,24 @@ def _files() -> dict[str, bytes]:
         return {name: archive.read(name) for name in archive.namelist()}
 
 
-@lru_cache(maxsize=1)
 def catalog() -> tuple[Symbol, ...]:
-    """Alle mitgelieferten Symbole (einmal gelesen)."""
+    """Alle mitgelieferten Symbole, Namen und Untergruppen in der Sprache von labelwerk (je Sprache
+    einmal gelesen)."""
+    return _catalog(i18n.language())
+
+
+@lru_cache(maxsize=4)
+def _catalog(language: str) -> tuple[Symbol, ...]:
     entries = json.loads(_files()["catalog.json"])["symbols"]
-    return tuple(Symbol(id=e["id"], group=e["group"], subgroup=e["subgroup"], name=e["name"],
-                        keywords=tuple(e["keywords"]), file=e["file"], source=e["source"],
-                        url=e["url"], author=e["author"], license=e["license"])
+
+    def pick(entry: dict, key: str) -> str:   # ältere Kataloge: nur der deutsche Name
+        return entry.get(key + "s", {}).get(language) or entry[key]
+    return tuple(Symbol(id=e["id"], group=e["group"], subgroup=pick(e, "subgroup"),
+                        name=pick(e, "name"), keywords=tuple(e["keywords"]), file=e["file"],
+                        source=e["source"], url=e["url"], author=e["author"], license=e["license"],
+                        names=tuple(dict.fromkeys([*e.get("names", {}).values(), e["name"]])),
+                        subgroups=tuple(dict.fromkeys([*e.get("subgroups", {}).values(),
+                                                       e["subgroup"]])))
                  for e in entries)
 
 
@@ -74,15 +92,21 @@ class _Entry:
 
 
 def _entry(s: Symbol) -> _Entry:
-    name = _fold(s.name)
+    """Suchtexte: Name in jeder Sprache (Anzeigename zuerst), Untergruppe, Suchbegriffe."""
+    names = [_fold(n) for n in dict.fromkeys([s.name, *s.names])]
     keywords = tuple(_fold(k) for k in s.keywords)
-    return _Entry(name, tuple(_WORD.findall(name)), keywords,
-                  " ".join((name, _fold(s.subgroup), *keywords)))
+    return _Entry(" / ".join(names), tuple(w for n in names for w in _WORD.findall(n)), keywords,
+                  " ".join((*names, *(_fold(g) for g in dict.fromkeys([s.subgroup, *s.subgroups])),
+                            *keywords)))
 
 
-@lru_cache(maxsize=1)
 def _index() -> dict[str, tuple[Symbol, _Entry]]:
-    return {s.id: (s, _entry(s)) for s in catalog()}
+    return _index_for(i18n.language())
+
+
+@lru_cache(maxsize=4)
+def _index_for(language: str) -> dict[str, tuple[Symbol, _Entry]]:
+    return {s.id: (s, _entry(s)) for s in _catalog(language)}
 
 
 def own_dir() -> Path:
@@ -100,9 +124,9 @@ def own_symbols(directory: Path | None = None) -> list[Symbol]:
                         and p.suffix.lower() in OWN_SUFFIXES), key=lambda p: p.name.casefold())
     except OSError:
         return []
-    return [Symbol(id=f"ordner/{p.name}", group="eigene", subgroup="Eigene", name=p.stem,
+    return [Symbol(id=f"ordner/{p.name}", group="eigene", subgroup=_(OWN_SUBGROUP), name=p.stem,
                    keywords=(), file=str(p), source=p.name, url="", author="",
-                   license=OWN_LICENSE) for p in paths]
+                   license=_(OWN_LICENSE)) for p in paths]
 
 
 def symbols(group: str | None = None) -> list[Symbol]:
@@ -150,7 +174,7 @@ def search(text: str, group: str | None = None) -> list[Symbol]:
         entry = index[symbol.id][1] if symbol.id in index else _entry(symbol)
         if all(word in entry.text for word in words):
             ranked.append((_rank(entry, words[0]), position, symbol))
-    return [symbol for _, _, symbol in sorted(ranked, key=lambda r: r[:2])]
+    return [symbol for __, __, symbol in sorted(ranked, key=lambda r: r[:2])]
 
 
 def data(symbol: Symbol) -> bytes:
diff --git a/src/labelwerk/clipart_data/LICENSES.md b/src/labelwerk/clipart_data/LICENSES.md
index ed34694..88d99b9 100644
--- a/src/labelwerk/clipart_data/LICENSES.md
+++ b/src/labelwerk/clipart_data/LICENSES.md
@@ -233,7 +233,7 @@ SOFTWARE.
 | Nicht zulässig für Seitenschleifen (P032) | [ISO 7010 P032.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P032.svg) | Original: Unbekannt Vektor: MaxxL | Public domain |
 | Nicht zulässig für Nassschleifen (P033) | [ISO 7010 P033.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P033.svg) | Original: ISO Vektor: Uploader | Public domain |
 | Nicht zulässig für Freihand- und handgeführtes Schleifen (P034) | [ISO 7010 P034.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P034.svg) | Original: ISO Vektor: Uploader | Public domain |
-| Do not wear metal-studded footwear (P035) | [ISO 7010 P035 PD.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P035_PD.svg) | Clemenspool | CC0 |
+| Benutzen mit genagelten Schuhen verboten (P035) | [ISO 7010 P035 PD.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P035_PD.svg) | Clemenspool | CC0 |
 | Kein Zutritt für Kinder (P036) | [ISO 7010 P036.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P036.svg) | ISO | Public domain |
 | Schleppspur verlassen verboten (P037) | [ISO 7010 P037.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P037.svg) | ISO | Public domain |
 | Schaukeln im Sessel verboten (P038) | [ISO 7010 P038.svg](https://commons.wikimedia.org/wiki/File%3AISO_7010_P038.svg) | ISO | Public domain |
diff --git a/src/labelwerk/cups.py b/src/labelwerk/cups.py
index e47c414..968d896 100644
--- a/src/labelwerk/cups.py
+++ b/src/labelwerk/cups.py
@@ -5,7 +5,7 @@ Etikettengrößen und Auflösung kommen aus dem Treiber (PPD: ``*PaperDimension`
 ``*DefaultResolution``), sonst aus den Namen der Größen (``lpoptions -l``: „62x29mm“, „w288h432“
 in Punkt), sonst aus einer Liste je Hersteller (Dymo, Zebra). Schnitt-Optionen sind die
 Treiber-Optionen mit „Cut“ im Namen. Jeder Aufruf hat ein Zeitlimit, Meldungen kommen englisch
-(``LC_MESSAGES=C``, Namen bleiben UTF-8); Fehler werden zur deutschen ``CupsError``. Die Liste
+(``LC_MESSAGES=C``, Namen bleiben UTF-8); Fehler werden zur übersetzten ``CupsError``. Die Liste
 der Warteschlangen fragt ein Hintergrund-Thread ab – die Oberfläche wartet nie auf CUPS.
 """
 from __future__ import annotations
@@ -21,6 +21,7 @@ from pathlib import Path
 
 from PIL import Image
 
+from .i18n import _
 from .labels import DPI, DPI_RANGE, SIZE_MM, sized_id
 
 PREFIX = "cups:"
@@ -80,7 +81,7 @@ class QueueInfo:
 
     def label_ids(self) -> list[str]:
         ids = []
-        for _, w, h in self.media:
+        for __, w, h in self.media:
             label_id = sized_id(w, h, self.dpi)
             if label_id not in ids:
                 ids.append(label_id)
@@ -114,12 +115,13 @@ def _run(*args: str, timeout: float = TIMEOUT_S) -> str:
         done = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                               check=False, env=_environment())
     except FileNotFoundError:
-        raise CupsError("CUPS-Befehle fehlen (Paket cups-client installieren)") from None
+        raise CupsError(_("CUPS commands missing (install the package cups-client)")) from None
     except subprocess.TimeoutExpired:
-        raise CupsError(f"CUPS antwortet nicht ({args[0]})") from None
+        raise CupsError(_("CUPS does not answer ({command})").format(command=args[0])) from None
     if done.returncode != 0:
         reason = (done.stderr or done.stdout).strip().splitlines()
-        raise CupsError(f"CUPS: {reason[-1] if reason else args[0] + ' gescheitert'}")
+        raise CupsError(_("CUPS: {reason}").format(reason=reason[-1]) if reason
+                        else _("CUPS: {command} failed").format(command=args[0]))
     return done.stdout
 
 
@@ -205,7 +207,7 @@ def _queue_info(name: str, options: dict) -> QueueInfo:
     dpi, media, source = DPI, (), "list"
     try:
         if not valid_name(name):
-            raise OSError("kein gültiger Name")
+            raise OSError("invalid queue name")      # intern, nie angezeigt
         dpi, media = _parse_ppd((PPD_DIR / f"{name}.ppd").read_text(errors="replace"))
         source = "ppd"
     except OSError:                        # nicht lesbar (Rechte) oder ohne PPD
@@ -230,7 +232,7 @@ def _options(name: str) -> dict[str, tuple[str, list[str], str]]:
         head, sep, values = line.partition(":")
         if not sep:
             continue
-        key, _, title = head.partition("/")
+        key, __, title = head.partition("/")
         choices = values.split()
         default = next((c[1:] for c in choices if c.startswith("*")), choices[0] if choices else "")
         out[key.strip()] = (title.strip() or key.strip(), [c.lstrip("*") for c in choices], default)
@@ -308,7 +310,7 @@ def print_images(name: str, images: list[Image.Image], w_mm: float, h_mm: float,
     in ``dpi`` (Seite = Etikett, 1:1 – ohne Einpassen und Drehen), Größe des Treibers bzw.
     eigene, dazu ``options`` (z. B. Schnitt). Zurück kommt die Auftrags-Kennung."""
     if not valid_name(name):
-        raise CupsError(f"Ungültiger Name der Warteschlange: {name!r}")
+        raise CupsError(_("Invalid queue name: {name!r}").format(name=name))
     info = queue_info(name)
     key = info.media_key(w_mm, h_mm)
     with tempfile.TemporaryDirectory(prefix="labelwerk-") as folder:
diff --git a/src/labelwerk/desktop.py b/src/labelwerk/desktop.py
index dc4dd1d..3ef0520 100644
--- a/src/labelwerk/desktop.py
+++ b/src/labelwerk/desktop.py
@@ -7,11 +7,21 @@ import shutil
 import subprocess
 from importlib import resources
 from pathlib import Path
+from xml.sax.saxutils import escape
+
+from . import i18n
+from .i18n import N_, _
 
 APP_NAME = "labelwerk"  # angezeigter Name (Fenster, Starter, Hilfe) – Umbenennen: CLAUDE.md, Roadmap 7
 APP_ID = "labelwerk"    # technische ID; muss zu QGuiApplication.setDesktopFileName passen
 MIME_TYPE = "application/x-labelwerk"      # Etikett-Datei *.labelwerk
 MIME_ICON = MIME_TYPE.replace("/", "-")    # Icon-Name nach XDG (shared-mime-info leitet ihn ab)
+# Texte für Starter und Dateityp: englisch, dazu jede Übersetzung als eigener Eintrag (die Dateien
+# gelten für jede Sprache der Sitzung, nicht nur die von labelwerk)
+MIME_COMMENT = N_("{app} label")
+GENERIC_NAME = N_("Label printing")
+COMMENT = N_("Design and print labels (Brother QL)")
+KEYWORDS = N_("Label;Brother;QL;Printer;P-touch;")
 
 
 def data_home() -> Path:
@@ -30,14 +40,37 @@ def mime_xml() -> str:
         '<?xml version="1.0" encoding="UTF-8"?>\n'
         '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
         f'  <mime-type type="{MIME_TYPE}">\n'
-        f"    <comment>{APP_NAME} label</comment>\n"
-        f'    <comment xml:lang="de">{APP_NAME}-Etikett</comment>\n'
+        + "".join("    <comment" + (f' xml:lang="{code}"' if code else "") + ">"
+                  + escape(text.format(app=APP_NAME)) + "</comment>\n"
+                  for code, text in _localized(MIME_COMMENT)) +
         '    <sub-class-of type="application/json"/>\n'
         '    <glob pattern="*.labelwerk"/>\n'
         "  </mime-type>\n"
         "</mime-info>\n")
 
 
+def _localized(text: str) -> list[tuple[str, str]]:
+    """``text`` englisch ("") und in jeder Sprache mit Übersetzung: [(Sprache, Text), …]."""
+    found = [("", text)]
+    for code in i18n.available():
+        if code == i18n.SOURCE:
+            continue
+        try:
+            catalog = i18n.parse_po((i18n.PO_DIR / f"{code}.po").read_text(encoding="utf-8"), code)
+        except (OSError, ValueError):
+            continue
+        forms = catalog.messages.get(("", text))
+        if forms and forms[0] != text:
+            found.append((code, forms[0]))
+    return found
+
+
+def _entries(key: str, text: str) -> str:
+    """Schlüssel eines Starter-Eintrags mit Übersetzungen: ``Key=…``, ``Key[de]=…``."""
+    return "".join(f"{key}{f'[{code}]' if code else ''}={value}\n"
+                   for code, value in _localized(text))
+
+
 def icon_svg() -> str:
     return (resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg").read_text(encoding="utf-8")
 
@@ -57,14 +90,13 @@ def desktop_entry(gui_exe: Path) -> str:
         "[Desktop Entry]\n"
         "Type=Application\n"
         f"Name={APP_NAME}\n"
-        "GenericName=Etikettendruck\n"
-        "Comment=Etiketten gestalten und drucken (Brother QL)\n"
+        + _entries("GenericName", GENERIC_NAME) + _entries("Comment", COMMENT) +
         f"Exec={_exec_arg(gui_exe)} %f\n"
         f"Icon={APP_ID}\n"
         f"MimeType={MIME_TYPE};\n"
         "Terminal=false\n"
         "Categories=Office;\n"
-        "Keywords=Etikett;Label;Brother;QL;Drucker;P-touch;\n"
+        + _entries("Keywords", KEYWORDS) +
         f"StartupWMClass={APP_ID}\n"
     )
 
@@ -96,8 +128,8 @@ def install(gui_exe: Path, data: Path | None = None, which=None, run=None,
     (``update``) die Datenbanken auffrischen (``update_databases``). Schreibfehler: ``OSError``."""
     gui_exe = Path(gui_exe)
     if not gui_exe.exists():
-        raise ValueError(f"labelwerk-gui nicht gefunden ({gui_exe}) – "
-                         "GUI installiert? pip install -e \".[gui]\"")
+        raise ValueError(_("labelwerk-gui not found ({path}) – GUI installed? "
+                           "pip install -e \".[gui]\"").format(path=gui_exe))
     data = data or data_home()
     entry, icon, mime, mime_icon = _targets(data)
     contents = {entry: desktop_entry(gui_exe.resolve()), icon: icon_svg(), mime: mime_xml(),
diff --git a/src/labelwerk/detect.py b/src/labelwerk/detect.py
index 78e52d2..f30a59e 100644
--- a/src/labelwerk/detect.py
+++ b/src/labelwerk/detect.py
@@ -5,14 +5,16 @@ from pathlib import Path
 
 from brother_ql.backends.helpers import discover as _discover
 
+from .i18n import N_
+
 BROTHER_VENDOR_ID = "04f9"
 
-# Meldungen für CLI und GUI
-PRINTER_NOT_FOUND = ("Brother-Drucker unter /dev/usb/lp* nicht gefunden.\n"
-                     "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', 'lsmod | grep usblp'.")
-BUSY_MESSAGE = ("Brother-Drucker ist per USB angeschlossen, aber von einem anderen Programm belegt\n"
-                "(z. B. VM mit USB-Durchreichung). Dort freigeben und den Drucker kurz aus- und\n"
-                "wieder einschalten.")
+# Meldungen für CLI und GUI – nur markiert, beim Anzeigen mit ``_()`` übersetzen
+PRINTER_NOT_FOUND = N_("Brother printer not found under /dev/usb/lp*.\n"
+                       "Check: switched on, Editor Lite LED off, 'lsusb', 'lsmod | grep usblp'.")
+BUSY_MESSAGE = N_("Brother printer is connected via USB but in use by another program\n"
+                  "(e.g. a VM with USB passthrough). Release it there and switch the printer\n"
+                  "off and on again.")
 
 
 def find_brother_lp(sys_root: str | Path = "/sys/class/usbmisc",
diff --git a/src/labelwerk/favorites.py b/src/labelwerk/favorites.py
index 7e8156b..266ac20 100644
--- a/src/labelwerk/favorites.py
+++ b/src/labelwerk/favorites.py
@@ -11,9 +11,11 @@ from dataclasses import dataclass
 from pathlib import Path
 
 from .document import Document
+from .i18n import N_, _
 from .storage import SUFFIX, save
 
 MAX_NAME_BYTES = 200        # Dateiname höchstens 255 Bytes (Endung, Reserve)
+_EXISTS = N_("Favorite “{name}” already exists")
 
 
 @dataclass(frozen=True)
@@ -47,8 +49,9 @@ def _checked(name: str) -> str:
     name = unicodedata.normalize("NFC", name.strip())
     if (not name or len(name.encode("utf-8")) > MAX_NAME_BYTES or name.startswith(".")
             or any(c in "/\\" or unicodedata.category(c) == "Cc" for c in name)):
-        raise ValueError(f"Name für den Favoriten ungültig: „{name}“ (nicht leer, nicht zu lang, "
-                         f"ohne / und \\ und Steuerzeichen, nicht mit Punkt beginnend)")
+        raise ValueError(_("Invalid name for the favorite: “{name}” (not empty, not too long, "
+                           "without / and \\ and control characters, not starting with a dot)")
+                         .format(name=name))
     return name
 
 
@@ -57,7 +60,7 @@ def add(doc: Document, name: str, overwrite: bool = False) -> Favorite:
     name = _checked(name)
     path = favorites_dir() / f"{name}{SUFFIX}"
     if path.exists() and not overwrite:
-        raise FileExistsError(f"Favorit „{name}“ gibt es schon")
+        raise FileExistsError(_(_EXISTS).format(name=name))
     path.parent.mkdir(parents=True, exist_ok=True)
     save(doc, path)
     return Favorite(name, path)
@@ -67,9 +70,9 @@ def rename(favorite: Favorite, name: str) -> Favorite:
     name = _checked(name)
     path = favorite.path.with_name(f"{name}{SUFFIX}")
     if not favorite.path.exists():
-        raise FileNotFoundError(f"Favorit „{favorite.name}“ nicht gefunden")
+        raise FileNotFoundError(_("Favorite “{name}” not found").format(name=favorite.name))
     if path.exists() and not path.samefile(favorite.path):     # Groß/Klein-Dateisysteme
-        raise FileExistsError(f"Favorit „{name}“ gibt es schon")
+        raise FileExistsError(_(_EXISTS).format(name=name))
     favorite.path.rename(path)
     return Favorite(name, path)
 
diff --git a/src/labelwerk/files.py b/src/labelwerk/files.py
index fdf3aa1..3166dfb 100644
--- a/src/labelwerk/files.py
+++ b/src/labelwerk/files.py
@@ -9,6 +9,7 @@ from pathlib import Path
 
 from PIL import Image, ImageOps
 
+from .i18n import _, ngettext
 from .imaging import MAX_PIXELS, limit_size, on_white, to_8bit
 from .labels import DPI, format_mm, get_label, length_limits
 from .render import MARGIN
@@ -87,11 +88,12 @@ def _checked(path: str | Path, suffixes: tuple[str, ...], allowed: str, page: in
     path = Path(path)
     suffix = path.suffix.lower()
     if suffix != ".pdf" and suffix not in suffixes:
-        raise ValueError(f"Dateityp nicht unterstützt: {suffix or path.name} – möglich: {allowed}")
+        raise ValueError(_("File type not supported: {suffix} – possible: {allowed}").format(
+            suffix=suffix or path.name, allowed=allowed))
     if not path.exists():
-        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
+        raise FileNotFoundError(_("File not found: {path}").format(path=path))
     if suffix == ".pdf" and page < 1:
-        raise ValueError("Seite muss mindestens 1 sein.")
+        raise ValueError(_("Page must be at least 1."))
     return path
 
 
@@ -102,30 +104,31 @@ def _readable(path: Path):
     try:
         yield
     except FileNotFoundError:
-        raise FileNotFoundError(f"Datei nicht gefunden: {path}") from None
+        raise FileNotFoundError(_("File not found: {path}").format(path=path)) from None
     except (OSError, RuntimeError, SyntaxError, struct.error, zlib.error,
             Image.DecompressionBombError) as e:
-        raise ValueError(f"Datei kann nicht gelesen werden: {path.name} ({_reason(e)})") from e
+        raise ValueError(_("Cannot read file: {name} ({reason})").format(
+            name=path.name, reason=_reason(e))) from e
 
 
 def _reason(error: Exception) -> str:
     """Grund eines Lesefehlers auf Deutsch."""
     if isinstance(error, IsADirectoryError):
-        return "ist ein Ordner"
+        return _("is a folder")
     if isinstance(error, PermissionError):
-        return "keine Leserechte"
+        return _("no read permission")
     if isinstance(error, Image.DecompressionBombError):
-        return "Bild hat zu viele Pixel"
+        return _("image has too many pixels")
     if isinstance(error, Image.UnidentifiedImageError):
-        return "kein lesbares Bild"
+        return _("not a readable image")
     if isinstance(error, RuntimeError):            # PDFium (pypdfium2.PdfiumError)
         if getattr(error, "err_code", None) == _PDFIUM_PASSWORD:
-            return "PDF ist verschlüsselt"
-        return "keine gültige PDF-Datei"
+            return _("PDF is encrypted")
+        return _("not a valid PDF file")
     if (isinstance(error, (SyntaxError, struct.error, zlib.error))
             or any(word in str(error) for word in ("truncated", "broken", "corrupt"))):
-        return "Datei ist beschädigt oder unvollständig"
-    return "Lesefehler"
+        return _("file is damaged or incomplete")
+    return _("read error")
 
 
 def _load_pdf(path: Path, page: int, dpi: int = DPI) -> Image.Image:
@@ -147,7 +150,8 @@ def _pdf_page(path: Path, page: int):
     pdf = pdfium.PdfDocument(path)
     try:
         if not 1 <= page <= len(pdf):
-            raise ValueError(f"PDF hat nur {len(pdf)} Seite(n).")
+            raise ValueError(ngettext("The PDF has only {count} page.", "The PDF has only {count} pages.",
+                                      len(pdf)).format(count=len(pdf)))
         yield pdf[page - 1]
     finally:
         pdf.close()
@@ -200,7 +204,7 @@ def _content_box(img: Image.Image, dpi: float, level: int) -> tuple[int, int, in
     ink = gray.point(lambda v: 255 if v < level else 0)
     box = ink.getbbox()
     if box is None:
-        raise ValueError("Datei enthält keinen druckbaren Inhalt.")
+        raise ValueError(_("The file has no printable content."))
     # Schnittmarken sind schwarz: immer auf der Maske mit ``INK`` suchen, damit helle
     # Elemente anderswo auf der Seite (graue Textzeile) sie nicht vom Rand verdrängen
     marks = ink if level == INK else gray.point(lambda v: 255 if v < INK else 0)
@@ -222,7 +226,7 @@ def _content_box(img: Image.Image, dpi: float, level: int) -> tuple[int, int, in
     inner = (x0 + left, y0 + top, x0 + right, y0 + bottom)
     trimmed = ink.crop(inner).getbbox()  # Leerraum innerhalb der Marken entfernen
     if trimmed is None:
-        raise ValueError("Zwischen den Schnittmarken ist kein druckbarer Inhalt.")
+        raise ValueError(_("There is no printable content between the crop marks."))
     return (inner[0] + trimmed[0], inner[1] + trimmed[1],
             inner[0] + trimmed[2], inner[1] + trimmed[3])
 
@@ -260,7 +264,8 @@ def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
     Drehung in Grad im Uhrzeigersinn (0, 90, 180, 270).
     """
     if rotate not in ROTATIONS:
-        raise ValueError(f"Drehung {rotate!r} nicht möglich – erlaubt: auto, 0, 90, 180, 270")
+        raise ValueError(_("Rotation {rotate!r} not possible – allowed: auto, 0, 90, 180, 270").format(
+            rotate=rotate))
     label = get_label(label_id)
     if label.dpi != dpi:                         # gleiche Größe in den Punkten des Druckers
         f = label.dpi / dpi
@@ -282,12 +287,12 @@ def fit_to_label(img: Image.Image, label_id: str, fit: bool = False,
             img = _shrink(img, max_w, max_h, may_rotate=rotate == "auto")
         else:
             mm = lambda dots: format_mm(dots, label.dpi)   # noqa: E731
-            limit = (f"{mm(max_w)} mm breit" if not label.height
-                     else f"{mm(max_w)} × {mm(max_h)} mm groß")
-            raise ValueError(
-                f"Motiv ist {mm(img.width)} × {mm(img.height)} mm, "
-                f"Etikett {label_id!r} ist höchstens {limit} – "
-                "mit --fit verkleinern (Codes evtl. nicht mehr lesbar)")
+            text = (_("Image is {width} × {height} mm, label {label!r} is at most {max_w} mm wide – "
+                      "shrink with --fit (codes may become unreadable)") if not label.height
+                    else _("Image is {width} × {height} mm, label {label!r} is at most {max_w} × "
+                           "{max_h} mm – shrink with --fit (codes may become unreadable)"))
+            raise ValueError(text.format(width=mm(img.width), height=mm(img.height), label=label_id,
+                                         max_w=mm(max_w), max_h=mm(max_h)))
 
     height = label.height or min(max(img.height + 2 * MARGIN, min_len), max_len)
     out = Image.new("L", (max_w, height), 255)
diff --git a/src/labelwerk/fonts.py b/src/labelwerk/fonts.py
index c2ee8bd..ab47ddc 100644
--- a/src/labelwerk/fonts.py
+++ b/src/labelwerk/fonts.py
@@ -12,6 +12,8 @@ from pathlib import Path
 
 from PIL import ImageFont
 
+from .i18n import _
+
 DEFAULT_FAMILY = "DejaVu Sans"
 _DEJAVU_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF",
                 "/usr/share/fonts/dejavu-sans-fonts")
@@ -87,5 +89,5 @@ def load(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
         try:
             return ImageFont.truetype(path, size)
         except OSError as e:
-            raise FontLoadError(f"Schrift „{path}“ kann nicht geladen werden ({e}).") from e
+            raise FontLoadError(_("Cannot load font “{path}” ({error}).").format(path=path, error=e)) from e
     return ImageFont.load_default(size=size)
diff --git a/src/labelwerk/gui/actions.py b/src/labelwerk/gui/actions.py
index c4ad81b..21f3c6c 100644
--- a/src/labelwerk/gui/actions.py
+++ b/src/labelwerk/gui/actions.py
@@ -10,6 +10,7 @@ from PySide6.QtCore import QObject, Qt
 from PySide6.QtGui import QAction, QKeySequence
 
 from .. import shortcuts
+from ..i18n import _
 
 _CONTEXT = {
     "global": Qt.ShortcutContext.WindowShortcut,
@@ -22,7 +23,7 @@ def build_actions(parent: QObject, mapping: dict[str, str]) -> dict[str, QAction
     """Je Aktion des Verzeichnisses eine QAction mit Name, Bereich und Kürzel aus ``mapping``."""
     actions = {}
     for entry in shortcuts.ACTIONS:
-        action = QAction(entry.name, parent)
+        action = QAction(_(entry.name), parent)
         action.setObjectName(entry.id)
         action.setShortcutContext(_CONTEXT[entry.scope])
         actions[entry.id] = action
@@ -38,6 +39,6 @@ def apply_shortcuts(actions: dict[str, QAction], mapping: dict[str, str]) -> Non
             action.setShortcuts([sequence, QKeySequence("Enter")])
         else:
             action.setShortcut(sequence)
-        name = shortcuts.action(action_id).name
+        name = _(shortcuts.action(action_id).name)
         keys = sequence.toString(QKeySequence.SequenceFormat.NativeText)
         action.setToolTip(f"{name} ({keys})" if keys else name)
diff --git a/src/labelwerk/gui/app.py b/src/labelwerk/gui/app.py
index cad3587..6b522ff 100644
--- a/src/labelwerk/gui/app.py
+++ b/src/labelwerk/gui/app.py
@@ -8,7 +8,9 @@ from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
 from PySide6.QtGui import QIcon
 from PySide6.QtWidgets import QApplication
 
+from .. import i18n
 from ..desktop import APP_ID, APP_NAME
+from ..settings import configured_language
 
 from .main_window import MainWindow
 
@@ -35,16 +37,28 @@ def apply_identity(app: QApplication) -> None:
 
 
 def install_translations(app: QApplication) -> QTranslator | None:
-    """Qt-eigene Texte (Speichern, Abbrechen, Ja …) auf Deutsch – passend zu labelwerk."""
+    """Qt-eigene Texte (Speichern, Abbrechen, Ja …) in der Sprache von labelwerk
+    (``i18n.language()``); Englisch braucht keine Übersetzung (None)."""
+    if i18n.language() == i18n.SOURCE:
+        return None
     translator = QTranslator(app)
-    if translator.load(QLocale(QLocale.Language.German, QLocale.Country.Germany), "qtbase", "_",
+    if translator.load(QLocale(i18n.language()), "qtbase", "_",
                        QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
         app.installTranslator(translator)
         return translator
     return None
 
 
+def set_language() -> str:
+    """Sprache aus den Einstellungen (sonst System) setzen – vor dem ersten Text; Zahlen in Feldern
+    mit ihrem Dezimaltrenner (``QLocale``)."""
+    language = i18n.set_language(configured_language())
+    QLocale.setDefault(QLocale(language))
+    return language
+
+
 def main() -> int:
+    set_language()
     app = QApplication(sys.argv)
     apply_identity(app)
     install_translations(app)
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index baaa250..c9bcedd 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -17,6 +17,7 @@ from PySide6.QtWidgets import (QApplication, QGraphicsPixmapItem, QGraphicsRectI
 
 from .. import layout
 from . import image_import
+from ..i18n import _
 from ..labels import DPI, Label, format_mm, length_limits, mm_text
 from ..layout import Rect
 from ..printer import DEFAULT_MODEL
@@ -256,7 +257,7 @@ class Canvas(QGraphicsView):
                                         QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.black))
             self.handle.setCursor(Qt.CursorShape.SizeHorCursor if self.orientation == "horizontal"
                                   else Qt.CursorShape.SizeVerCursor)
-            self.handle.setToolTip("Ziehen: Länge festlegen · Doppelklick: automatisch")
+            self.handle.setToolTip(_("Drag: set the length · Double-click: automatic"))
         self._caption = self._caption_for(th)
         margin = _MARGIN_MM * self.mm
         scene.setSceneRect(-margin, -margin, tw + 2 * margin, th + 2 * margin)
diff --git a/src/labelwerk/gui/file_session.py b/src/labelwerk/gui/file_session.py
index ee540ef..6efdf94 100644
--- a/src/labelwerk/gui/file_session.py
+++ b/src/labelwerk/gui/file_session.py
@@ -21,6 +21,7 @@ from .. import favorites, storage
 from ..desktop import APP_NAME
 from ..document import Document, TextObject
 from ..favorites import Favorite
+from ..i18n import N_, _
 from ..labels import labels_for_model
 from ..render import Renderer
 from ..settings import new_document
@@ -28,8 +29,7 @@ from ..storage import SUFFIX, StorageError, exists, os_reason
 from .history import restore
 from .panels.file import PREVIEW
 
-FILE_FILTER = f"labelwerk-Etiketten (*{SUFFIX})"
-UNTITLED = "Unbenannt"
+UNTITLED = N_("Untitled")                     # englisch, angezeigt wird _(UNTITLED)
 MODIFIED = "• "
 NAME_LENGTH = 40               # vorgeschlagener Favoriten-Name: höchstens so lang
 PREVIEW_ERRORS = Exception     # Vorschau eines Favoriten: jeder Fehler → „nicht lesbar“
@@ -65,7 +65,7 @@ class FileSession(QObject):
     # --- Dialoge (in Tests ersetzbar) -------------------------------------
     def ask_save_file(self, suggested: str) -> str | None:
         """Dialog ergänzt die Endung selbst – so fragt er vor dem Ersetzen nach dem vollen Namen."""
-        dialog = QFileDialog(self.window, "Etikett speichern", suggested, FILE_FILTER)
+        dialog = QFileDialog(self.window, _("Save label"), suggested, _file_filter())
         dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
         dialog.setDefaultSuffix(SUFFIX[1:])
         try:
@@ -83,22 +83,25 @@ class FileSession(QObject):
         return box.exec() == QMessageBox.StandardButton.Yes.value
 
     def ask_replace_file(self, path: Path) -> bool:
-        return self._ask_yes_no("Datei ersetzen", f"„{path.name}“ gibt es schon. Ersetzen?")
+        return self._ask_yes_no(_("Replace file"),
+                                _("“{name}” already exists. Replace it?").format(name=path.name))
 
     def ask_print_other_roll(self, label_id: str, loaded: str) -> bool:
         return self._ask_yes_no(
-            "Andere Rolle",
-            f"Eingelegt ist {loaded}, der Favorit ist für {label_id}. Trotzdem drucken?")
+            _("Different roll"),
+            _("{loaded} is loaded, the favorite is for {label}. Print anyway?").format(
+                loaded=loaded, label=label_id))
 
     def ask_open_file(self) -> str | None:
-        path, _ = QFileDialog.getOpenFileName(self.window, "Etikett öffnen", self._dir,
-                                              FILE_FILTER)
+        path, _filter = QFileDialog.getOpenFileName(self.window, _("Open label"), self._dir,
+                                                    _file_filter())
         return path or None
 
     def ask_save_changes(self) -> str:
         """„save“ | „discard“ | „cancel“."""
-        box = QMessageBox(QMessageBox.Icon.Question, "Ungespeicherte Änderungen",
-                          f"„{self.name()}“ wurde geändert. Änderungen speichern?",
+        box = QMessageBox(QMessageBox.Icon.Question, _("Unsaved changes"),
+                          _("“{name}” has been changed. Save the changes?").format(
+                              name=self.name()),
                           QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                           | QMessageBox.StandardButton.Cancel, self.window)
         box.setTextFormat(Qt.TextFormat.PlainText)
@@ -106,22 +109,24 @@ class FileSession(QObject):
         return answer_for(box.exec())
 
     def ask_favorite_name(self, suggested: str) -> str | None:
-        name, ok = QInputDialog.getText(self.window, "Favorit", "Name des Favoriten:",
+        name, ok = QInputDialog.getText(self.window, _("Favorite"), _("Name of the favorite:"),
                                         text=suggested)
         return name if ok else None
 
     def ask_overwrite(self, name: str) -> bool:
-        return self._ask_yes_no("Favorit ersetzen", f"Favorit „{name}“ gibt es schon. Ersetzen?")
+        return self._ask_yes_no(_("Replace favorite"),
+                                _("Favorite “{name}” already exists. Replace it?").format(name=name))
 
     def ask_remove(self, name: str) -> bool:
-        return self._ask_yes_no("Favorit löschen", f"Favorit „{name}“ löschen?")
+        return self._ask_yes_no(_("Delete favorite"),
+                                _("Delete favorite “{name}”?").format(name=name))
 
     def open_url(self, url: QUrl) -> None:
         QDesktopServices.openUrl(url)
 
     # --- Zustand ----------------------------------------------------------
     def name(self) -> str:
-        return self.path.stem if self.path is not None else UNTITLED
+        return self.path.stem if self.path is not None else _(UNTITLED)
 
     def modified(self) -> bool:
         """Anders als beim Öffnen/Speichern? Leere Textrahmen zählen nicht: ein frisch angelegter
@@ -157,8 +162,8 @@ class FileSession(QObject):
         """Etikett muss zum Drucker passen (sonst gäbe es dafür keine Auswahl im Reiter Papier)."""
         if doc.label_id in {label.id for label in labels_for_model(self.window.model)}:
             return True
-        self.window._set_result(f"{name}: Etikett „{doc.label_id}“ passt nicht zum "
-                                f"{self.window.model}", "error")
+        self.window._set_result(_("{name}: label “{label}” does not fit the {model}").format(
+            name=name, label=doc.label_id, model=self.window.model), "error")
         return False
 
     def _replace(self, doc: Document, path: Path | None, origin: str = "new",
@@ -194,8 +199,9 @@ class FileSession(QObject):
             doc.label_id = self.fitting_label(wanted)
             self._replace(doc, None)
             if doc.label_id != wanted:
-                self.window._set_result(f"Etikett „{wanted}“ passt nicht zum {self.window.model} – "
-                                        f"{doc.label_id} genommen", "warn")
+                self.window._set_result(
+                    _("Label “{label}” does not fit the {model} – using {new}").format(
+                        label=wanted, model=self.window.model, new=doc.label_id), "warn")
 
     def fitting_label(self, label_id: str) -> str:
         """``label_id``, wenn es zum Drucker passt, sonst die eingelegte Rolle, sonst 62 mm endlos
@@ -227,11 +233,12 @@ class FileSession(QObject):
         error = self.window._render_error     # render_now im Ersetzen hat ihn schon gemeldet
         series_panel = self.window.panel("series")
         if error is None and doc.series is not None and series_panel.error:
-            error = f"Serie: {series_panel.error}"      # z. B. Tabelle nicht gefunden
+            error = _("Series: {error}").format(error=series_panel.error)   # z. B. Tabelle fehlt
         if error is None:
-            self.window._set_result(f"Geöffnet: {path.name}", "ok")
+            self.window._set_result(_("Opened: {name}").format(name=path.name), "ok")
         else:
-            self.window._set_result(f"Geöffnet: {path.name} – {error}", "error")
+            self.window._set_result(_("Opened: {name} – {error}").format(name=path.name,
+                                                                         error=error), "error")
         return True
 
     def save(self) -> bool:
@@ -243,7 +250,7 @@ class FileSession(QObject):
     def save_as(self) -> bool:
         self.window.accept_pending_input()
         suggested = str(self.path) if self.path is not None else str(
-            Path(self._dir or Path.home()) / f"{self.suggested_name() or UNTITLED}{SUFFIX}")
+            Path(self._dir or Path.home()) / f"{self.suggested_name() or _(UNTITLED)}{SUFFIX}")
         path = self.ask_save_file(suggested)
         if not path:
             return False
@@ -266,7 +273,7 @@ class FileSession(QObject):
         self._saved = copy.deepcopy(self.window.doc)
         self.update_title()
         self._remember(self.path)
-        self.window._set_result(f"Gespeichert: {path.name}", "ok")
+        self.window._set_result(_("Saved: {name}").format(name=path.name), "ok")
         return True
 
     def _remember(self, path: Path) -> None:
@@ -281,8 +288,8 @@ class FileSession(QObject):
             settings.recent_files = [p for p in settings.recent_files if p != path]
             self.window._save_settings()
             self.refresh_lists()
-            self.window._set_result(f"Datei nicht gefunden: {path} – aus der Liste entfernt",
-                                    "error")
+            self.window._set_result(
+                _("File not found: {path} – removed from the list").format(path=path), "error")
             return
         self.open(path)
 
@@ -316,7 +323,7 @@ class FileSession(QObject):
             self.window._set_result(str(e), "error")
             return
         self.refresh_lists()
-        self.window._set_result(f"Favorit „{favorite.name}“ gespeichert", "ok")
+        self.window._set_result(_("Favorite “{name}” saved").format(name=favorite.name), "ok")
 
     def _load_favorite(self, favorite: Favorite) -> Document | None:
         try:
@@ -384,7 +391,8 @@ class FileSession(QObject):
         try:
             folder.mkdir(parents=True, exist_ok=True)
         except OSError as e:
-            self.window._set_result(f"Favoriten-Ordner nicht angelegt ({os_reason(e)})", "error")
+            self.window._set_result(_("Favorites folder not created ({reason})").format(
+                reason=os_reason(e)), "error")
             return
         self.open_url(QUrl.fromLocalFile(str(folder)))
 
@@ -418,6 +426,11 @@ class FileSession(QObject):
         return self._previews[key]
 
 
+def _file_filter() -> str:
+    """Dateifilter der Dialoge (übersetzt beim Anzeigen)."""
+    return _("labelwerk labels (*{suffix})").format(suffix=SUFFIX)
+
+
 def _without_empty_frames(doc: Document) -> Document:
     """Dokument ohne leere, frei platzierte Textrahmen (Flachkopie, nur zum Vergleichen)."""
     return replace(doc, objects=[o for o in doc.objects
diff --git a/src/labelwerk/gui/image_import.py b/src/labelwerk/gui/image_import.py
index 7aed391..b76ed00 100644
--- a/src/labelwerk/gui/image_import.py
+++ b/src/labelwerk/gui/image_import.py
@@ -19,23 +19,43 @@ from PySide6.QtSvg import QSvgRenderer
 
 from .. import clipart, files
 from ..clipart import Symbol
+from ..i18n import N_, _
 from ..imaging import MAX_DPI, MAX_PIXELS, on_white
 from ..labels import DPI
 
 SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".pdf")
 ALLOWED = "PNG, JPG, GIF, BMP, WebP, SVG, PDF"  # für Meldungen
-FILE_FILTER = ("Bilder und PDF (" + " ".join(f"*{s} *{s.upper()}" for s in SUFFIXES) + ");;"
-               "Alle Dateien (*)")              # Großschreibung: Kameras, Windows
-CLIPBOARD = "Zwischenablage"                    # Quelle eines eingefügten Bilds
+_PATTERNS = " ".join(f"*{s} *{s.upper()}" for s in SUFFIXES)   # Großschreibung: Kameras, Windows
+FILE_FILTER = f"Images and PDF ({_PATTERNS});;All files (*)"    # englisch; Dialoge: file_filter()
+# Quelle eines eingefügten Bilds: wird mit dem Etikett gespeichert und verglichen – deshalb fest
+# (deutsch, wie in älteren Dateien) und nur beim Anzeigen übersetzt (``source_title``)
+CLIPBOARD = "Zwischenablage"
 DROPPED = "Abgelegtes Bild"
 SCREENSHOT = "Bildschirmfoto"
 MIME_OBJECTS = "application/x-labelwerk-objects"   # kopierte Objekte (Kennung der Kopie)
 SYMBOL_SOURCE = "Symbol: {name}"                    # Quelle eines eingefügten Symbols
+_SOURCE_TITLES = {CLIPBOARD: N_("Clipboard"), DROPPED: N_("Dropped image"),
+                  SCREENSHOT: N_("Screenshot")}
 MIME_SYMBOL = "application/x-labelwerk-symbol"     # Symbol aus dem Fenster gezogen (id)
 SYMBOL_PROBE_PX = 512          # Symbol: erst grob rastern, um den Inhalt zu finden
 SVG_DPI = 96                                    # SVG: 1 px = 1/96 in
 
 
+def file_filter() -> str:
+    """Filter des Dateidialogs „Bild einfügen“ in der eingestellten Sprache."""
+    return _("Images and PDF ({patterns});;All files (*)").format(patterns=_PATTERNS)
+
+
+def source_title(source: str) -> str:
+    """Quelle eines Bilds zum Anzeigen: feste Quellen (Zwischenablage, Ablegen, Bildschirmfoto,
+    Symbol) übersetzt, Dateinamen wie sie sind."""
+    if source in _SOURCE_TITLES:
+        return _(_SOURCE_TITLES[source])
+    if is_symbol_source(source):
+        return _("Symbol: {name}").format(name=source[len(SYMBOL_SOURCE.split("{")[0]):])
+    return source
+
+
 def page_count(path: Path) -> int:
     """Seitenzahl (PDF), sonst 1 – Fehler wie beim Laden (``ValueError``, ``FileNotFoundError``)."""
     return files.page_count(path) if Path(path).suffix.lower() == ".pdf" else 1
@@ -46,8 +66,8 @@ def load(path: Path, page: int = 1) -> tuple[Image.Image, float]:
     Andere Dateitypen: ``ValueError`` mit allen möglichen Typen (samt SVG)."""
     path = Path(path)
     if path.suffix.lower() not in SUFFIXES:
-        raise ValueError(f"Dateityp nicht unterstützt: {path.suffix or path.name} – "
-                         f"möglich: {ALLOWED}")
+        raise ValueError(_("File type not supported: {type} – possible: {allowed}").format(
+            type=path.suffix or path.name, allowed=ALLOWED))
     if path.suffix.lower() == ".svg":
         return load_svg(path)
     return files.load_image(path, page)
@@ -65,14 +85,14 @@ def load_svg(path: Path) -> tuple[Image.Image, float]:
     Größe/viewBox; 1 px = 1/96 in); sehr große Zeichnungen gröber, höchstens
     ``MAX_PIXELS`` auf der längsten Seite."""
     if not path.exists():
-        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
+        raise FileNotFoundError(_("File not found: {path}").format(path=path))
     # mit Verweisen auf andere Dateien über den Pfad (sie liegen neben der SVG), sonst aus den
     # Bytes – derselbe Weg wie beim Rastern eines Vektorbilds (Vorschau = Raster)
     vector = load_vector(path)
     renderer = QSvgRenderer(str(path)) if vector is None else _svg_renderer(vector)
     size = renderer.defaultSize()
     if not renderer.isValid() or size.isEmpty():
-        raise ValueError(f"Datei kann nicht gelesen werden: {path.name} (kein gültiges SVG)")
+        raise ValueError(_("Cannot read file: {name} (not a valid SVG)").format(name=path.name))
     # Qt rechnet mm/in/pt mit 90 dpi – Maße mit Einheit deshalb selbst lesen (CSS: 96 px/in)
     width, height = svg_size(path) or (size.width(), size.height())
     dpi = min(DPI, MAX_PIXELS * SVG_DPI / max(width, height))
@@ -128,10 +148,10 @@ def rasterize_svg(svg: bytes, size: tuple[int, int],
     ``ValueError``; ebenso ein SVG mit Verweisen auf andere Dateien (die gelten nur neben der
     SVG, nicht in einem gespeicherten Dokument)."""
     if _EXTERNAL.search(svg):
-        raise ValueError("Vektorbild verweist auf andere Dateien – die werden nicht mitgespeichert.")
+        raise ValueError(_("Vector image refers to other files – they are not saved with it."))
     renderer = _svg_renderer(svg)
     if not renderer.isValid():
-        raise ValueError("Vektorbild kann nicht gelesen werden (kein gültiges SVG).")
+        raise ValueError(_("Cannot read vector image (not a valid SVG)."))
     return _render(renderer, size, region)
 
 
@@ -151,7 +171,7 @@ def load_symbol(symbol: Symbol, side_mm: float) -> tuple[Image.Image, float, tup
         renderer = QSvgRenderer(symbol.file) if linked else _svg_renderer(data)
         size = renderer.defaultSize()
         if not renderer.isValid() or size.isEmpty():
-            raise ValueError(f"Symbol {symbol.name} kann nicht gelesen werden (kein gültiges SVG).")
+            raise ValueError(_("Cannot read symbol {name} (not a valid SVG).").format(name=symbol.name))
         k = SYMBOL_PROBE_PX / max(size.width(), size.height())
         probe = (max(1, round(size.width() * k)), max(1, round(size.height() * k)))
         if box := files.ink_box(_render(renderer, probe, (0, 0, *probe))):
@@ -177,7 +197,7 @@ def svg_size(path: Path) -> tuple[float, float] | None:
     Wurzelelements, mit Einheiten px/mm/cm/in/pt/pc; None, wenn eine Angabe fehlt, relativ
     ist (%, em) oder die Datei sich nicht lesen lässt – dann zählt Qts Größe (viewBox)."""
     try:
-        _, root = next(ElementTree.iterparse(path, events=("start",)))
+        __, root = next(ElementTree.iterparse(path, events=("start",)))
     except (ElementTree.ParseError, OSError, StopIteration):
         return None
     sizes = []
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index e484dca..dbbb263 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -27,6 +27,7 @@ from ..printers import (UNTESTED_HINT, Printer, capabilities, choose, cups_print
 from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, Series, TextObject
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
+from ..i18n import N_, _, ngettext
 from ..labels import DPI, get_label, labels_for_model
 from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, change_label, exact_rect,
                       fill_anchored, frame_area, growing_axis, insert_placement, match_objects,
@@ -35,7 +36,8 @@ from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, change_label
 from ..printer import DEFAULT_MODEL, cut_interval, to_print_mode
 from ..render import (Renderer, RenderedObject, font_warnings, render_document,
                       set_svg_rasterizer)
-from ..settings import Settings, load_settings, network_entries, new_document, save_settings
+from ..settings import (Settings, load_settings, network_entries, new_document, save_settings,
+                        started_values)
 from ..shortcuts import effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
@@ -61,15 +63,14 @@ PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugri
 ZOOM_STEP = 10             # Prozentpunkte je Klick bzw. Kürzel
 NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
 _DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
-OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"
+OUTSIDE_HINT = N_("Object extends beyond the label")
 PASTE_OFFSET_MM = 2.0      # Einfügen/Duplizieren: versetzt nach rechts und unten
 PROGRESS_EVERY = 25        # Serie drucken: Fortschritt alle so viele Etiketten
-SHRUNK_HINT = "Bild auf {percent} verkleinert"                    # „37 %“
-CODES_HINT = " – Codes ggf. nicht mehr lesbar"                    # nur Strich (Codes)
-TURNED_HINT = "Bild um 90° gedreht, damit es 1:1 passt"
-NO_CLIPBOARD_IMAGE = "Kein Bild in der Zwischenablage."
-NO_SCREENSHOT = ("Bildschirmfoto nicht verfügbar (kein XDG-Portal) – mit dem System-Werkzeug in "
-                 "die Zwischenablage kopieren und mit Strg+V einfügen")
+# Hinweise: englisch (N_), angezeigt wird _(…)
+TURNED_HINT = N_("Image rotated by 90° so that it fits 1:1")
+NO_CLIPBOARD_IMAGE = N_("No image in the clipboard.")
+NO_SCREENSHOT = N_("Screenshot not available (no XDG portal) – copy it to the clipboard with the "
+                   "system tool and paste it with Ctrl+V")
 SYMBOL_MM = 15.0           # Symbol: längere Seite beim Einfügen (höchstens quer zum Band)
 LIBRARY_ERRORS = (OSError, zipfile.BadZipFile, KeyError, ValueError)   # Archiv fehlt/beschädigt
 HIDE_DELAY_MS = 300        # Bildschirmfoto: so lange nimmt der Desktop das Fenster weg
@@ -81,14 +82,19 @@ EDIT_BAR = (("tool.select", "tool-select"), ("tool.text", "tool-text"), None,
             None, ("edit.undo", "edit-undo"), ("edit.redo", "edit-redo"))
 _SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
 OBJECT_PANELS = ("text", "image", "barcode")   # Panel je Objektart (Text, Bild, Barcode)
+CHECKING_ROLL = N_("Checking the roll – please print again in a moment.")
+PRINTING_WAIT = N_("Printing – please wait.")
 
 
 def shrunk_hint(factor: float, mode: str) -> str:
     """Hinweis zum verkleinerten Bild: Prozent abgerundet (nie „100 %“, nie „0 %“); Codes
     werden nur bei Strich erwähnt – ein Foto wird gerastert, Codes sind dort nicht gemeint."""
     percent = math.floor(factor * 100 + 1e-9)
-    text = SHRUNK_HINT.format(percent=f"{percent} %" if percent else "< 1 %")
-    return text + CODES_HINT if mode == "line" else text
+    shown = _("{percent}%").format(percent=percent) if percent else _("< 1%")    # „37 %“
+    if mode == "line":
+        return _("Image reduced to {percent} – codes may no longer be readable").format(
+            percent=shown)
+    return _("Image reduced to {percent}").format(percent=shown)
 
 
 class MainWindow(QMainWindow):
@@ -148,7 +154,7 @@ class MainWindow(QMainWindow):
         self.shortcut_actions = build_actions(self, keys)
 
         # Werkzeugleiste + Panels aus der Registry
-        toolbar = QToolBar("Werkzeuge")
+        toolbar = QToolBar(_("Tools"))
         toolbar.setMovable(False)
         toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
         self.addToolBar(toolbar)
@@ -165,8 +171,8 @@ class MainWindow(QMainWindow):
             panel.edited.connect(self._commit)
             self.panels.addWidget(panel)
             self._panel_by_key[tool.key] = panel
-            action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
-            action.setToolTip(tool.tip or tool.title)
+            action = QAction(QIcon.fromTheme(tool.icon), _(tool.title).upper(), self)
+            action.setToolTip(_(tool.tip or tool.title))
             action.setCheckable(True)
             action.triggered.connect(lambda _=False, key=tool.key: self._tool_triggered(key))
             group.addAction(action)
@@ -179,9 +185,9 @@ class MainWindow(QMainWindow):
         spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
         toolbar.addWidget(spacer)
         self.settings_action = self._toolbar_action("app.settings", "preferences-system",
-                                                    "EINSTELLUNGEN", self.open_settings)
+                                                    _("SETTINGS"), self.open_settings)
         toolbar.addAction(self.settings_action)
-        self.print_action = self._toolbar_action("file.print", "document-print", "DRUCKEN",
+        self.print_action = self._toolbar_action("file.print", "document-print", _("PRINT"),
                                                  self.print_label)
         toolbar.addAction(self.print_action)
         toolbar.widgetForAction(self.print_action).setObjectName("print")
@@ -247,13 +253,15 @@ class MainWindow(QMainWindow):
         self.media_status.hide()
         self.statusBar().addWidget(self.media_status)
         self.statusBar().addWidget(self.result, 1)
-        self.cancel_button = QPushButton("ABBRECHEN")   # Serie: beim Vorbereiten und Drucken
+        self.cancel_button = QPushButton(_("CANCEL"))   # Serie: beim Vorbereiten und Drucken
         self.cancel_button.setObjectName("cancelPrint")
-        self.cancel_button.setToolTip("Serie abbrechen – ein schon gesendeter Teil (bis zu 10 "
-                                      "Etiketten, bei „Nur am Ende“ der ganze Auftrag) läuft zu Ende")
+        self.cancel_button.setToolTip(_("Cancel the series – a part already sent (up to 10 labels, "
+                                        "with “Only at the end” the whole job) is still printed"))
         self.cancel_button.clicked.connect(self.cancel_print)
         self.cancel_button.hide()
         self.statusBar().addWidget(self.cancel_button)
+        # Stand beim Start: der Einstellungsdialog zeigt danach, was erst ein Neustart ändert
+        self._started = started_values(self.settings)
         self.zoom_label = QLabel()
         for text, delta in (("−", -ZOOM_STEP), ("+", ZOOM_STEP)):
             button = QToolButton()
@@ -262,8 +270,9 @@ class MainWindow(QMainWindow):
             self.statusBar().addPermanentWidget(button)
             if text == "−":
                 self.statusBar().addPermanentWidget(self.zoom_label)
-        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z} %"))
-        self.zoom_label.setText(f"{self.canvas.zoom} %")
+        self.canvas.zoom_changed.connect(
+            lambda z: self.zoom_label.setText(_("{percent}%").format(percent=z)))
+        self.zoom_label.setText(_("{percent}%").format(percent=self.canvas.zoom))
 
         self._timer = QTimer(self)
         self._timer.setSingleShot(True)
@@ -387,7 +396,7 @@ class MainWindow(QMainWindow):
 
     def _build_edit_bar(self) -> None:
         """Bearbeitungsleiste unter der Werkzeugleiste: Werkzeug, Zwischenablage, Rückgängig."""
-        bar = QToolBar("Bearbeiten")
+        bar = QToolBar(_("Edit"))
         bar.setObjectName("editBar")
         bar.setMovable(False)
         bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
@@ -565,10 +574,10 @@ class MainWindow(QMainWindow):
         size, rendered = result.size, result.objects
         area = printable_area(self.doc, self.model, size)
         outside = outside_indices(rendered, size, self.doc.objects)
-        hints = ([OUTSIDE_HINT] if outside else []) + font_warnings(self.doc)
+        hints = ([_(OUTSIDE_HINT)] if outside else []) + font_warnings(self.doc)
         series_panel = self.panel("series")
         if self.doc.series is not None and series_panel.error:
-            hints.append(f"Serie: {series_panel.error}")
+            hints.append(_("Series: {error}").format(error=series_panel.error))
         series_panel.show_missing(series.missing(self.doc, series_panel.table.columns)
                                   if series_panel.table is not None else [])
         if hints and not self.result.text():
@@ -742,16 +751,18 @@ class MainWindow(QMainWindow):
             return message
         kept = self._keep if self._keep is not None else self.edit_session.index
         if kept is not None and index in (None, kept):
-            return f"{message} – mit Platzhaltern im Schreibmodus (kleinere Schrift wählen)"
-        return f"Zeile {self.panel('series').current_row()}: {message}"
+            return _("{message} – with placeholders in text editing (choose a smaller font)"
+                     ).format(message=message)
+        return _("Row {row}: {message}").format(row=self.panel("series").current_row(),
+                                                 message=message)
 
     def ask_series_file(self) -> str | None:
         """Dialog für die Tabelle einer Serie (in Tests ersetzbar); beginnt im Ordner der
         aktuellen Tabelle."""
         current = self.doc.series.source if self.doc.series is not None else None
-        path, _ = QFileDialog.getOpenFileName(
-            self, "Tabelle für die Serie", str(Path(current).parent) if current else "",
-            "Tabellen (*.csv *.xlsx *.xlsm *.tsv *.txt);;Alle Dateien (*)")
+        path, _filter = QFileDialog.getOpenFileName(
+            self, _("Table for the series"), str(Path(current).parent) if current else "",
+            _("Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"))
         return path or None
 
     def choose_series_table(self) -> None:
@@ -781,7 +792,8 @@ class MainWindow(QMainWindow):
             sample = obj.data == barcodes.SAMPLES.get(obj.kind)
             data = placeholder if sample else obj.data + placeholder
             if len(data) > MAX_BARCODE_DATA:
-                self._set_result(f"Inhalt zu lang (höchstens {MAX_BARCODE_DATA} Zeichen)", "error")
+                self._set_result(_("Content too long (at most {count} characters)").format(
+                    count=MAX_BARCODE_DATA), "error")
                 return
             self.doc.objects[selection[0]] = replace(obj, data=data)
             self._objects_changed(selection)
@@ -1106,7 +1118,7 @@ class MainWindow(QMainWindow):
 
     def ask_image_file(self) -> str | None:
         """Dateidialog „Bilder und PDF“ (in Tests ersetzbar); None = abgebrochen."""
-        path, _ = QFileDialog.getOpenFileName(self, "Bild einfügen", self._image_dir,
+        path, _filter = QFileDialog.getOpenFileName(self, _("Insert image"), self._image_dir,
                                               image_import.FILE_FILTER)
         if path:
             self._image_dir = str(Path(path).parent)
@@ -1114,8 +1126,9 @@ class MainWindow(QMainWindow):
 
     def ask_pdf_page(self, path: Path, count: int) -> int | None:
         """Seitenwahl für ein PDF mit mehreren Seiten (in Tests ersetzbar); None = abgebrochen."""
-        page, ok = QInputDialog.getInt(self, "PDF-Seite wählen",
-                                       f"{path.name} hat {count} Seiten. Welche einfügen?",
+        page, ok = QInputDialog.getInt(self, _("Choose PDF page"),
+                                       _("{name} has {count} pages. Which one to insert?").format(
+                                           name=path.name, count=count),
                                        1, 1, count)
         return page if ok else None
 
@@ -1150,7 +1163,7 @@ class MainWindow(QMainWindow):
         """„Aus Zwischenablage“: Bild der Zwischenablage in die Mitte des bedruckbaren Bereichs."""
         image = image_import.mime_image(QApplication.clipboard().mimeData())
         if image is None:
-            self._show_notice([NO_CLIPBOARD_IMAGE], "error")
+            self._show_notice([_(NO_CLIPBOARD_IMAGE)], "error")
             return
         self._insert_picture(image, CLIPBOARD)
 
@@ -1178,7 +1191,7 @@ class MainWindow(QMainWindow):
             return
         self.finish_editing()
         if not self.screenshot_available():
-            self._show_notice([NO_SCREENSHOT], "error")
+            self._show_notice([_(NO_SCREENSHOT)], "error")
             return
         self._shooting = self._shot_pending = True
         self.shortcut_actions["image.screenshot"].setEnabled(False)
@@ -1202,7 +1215,7 @@ class MainWindow(QMainWindow):
         try:
             self.take_screenshot()
         except Exception as e:  # Fenster sofort zurück; Meldung statt Traceback
-            self.screenshot_finished(None, f"{SCREENSHOT_FAILED} – {e}")
+            self.screenshot_finished(None, f"{_(SCREENSHOT_FAILED)} – {e}")
 
     def screenshot_finished(self, path: Path | None, error: str | None) -> None:
         """Antwort des Portals: Pfad → einfügen (300 dpi: 1 Bildschirmpixel = 1 Druckpunkt, wie
@@ -1221,7 +1234,7 @@ class MainWindow(QMainWindow):
         try:
             image, dpi = image_import.load_screenshot(Path(path))
         except (ValueError, OSError) as e:
-            self._show_notice([f"Bildschirmfoto: {e}"], "error")
+            self._show_notice([_("Screenshot: {error}").format(error=e)], "error")
             return
         self._insert_picture(image, SCREENSHOT, dpi=dpi)
 
@@ -1266,12 +1279,12 @@ class MainWindow(QMainWindow):
             image, dpi, crop, svg = image_import.load_symbol(symbol, self._symbol_mm())
         except (ValueError, OSError, KeyError, zipfile.BadZipFile,
                 Image.DecompressionBombError) as e:
-            self._show_notice([f"Symbol: {e}"], "error")
+            self._show_notice([_("Symbol: {error}").format(error=e)], "error")
             return
         obj = ImageObject.from_image(image, dpi, SYMBOL_SOURCE.format(name=symbol.name),
                                      crop=crop, svg=svg)
         # Größe passt schon quer zum Band – Drehen nach Einstellung gilt für Symbole nicht
-        self._insert_images([obj], at, [] if crop is not None else [CROP_FAILED], rotate=False)
+        self._insert_images([obj], at, [] if crop is not None else [_(CROP_FAILED)], rotate=False)
         self.settings.symbols_recent = clipart.add_recent(self.settings.symbols_recent, symbol.id)
         self._save_settings()
         if self.symbol_window is not None:
@@ -1318,7 +1331,7 @@ class MainWindow(QMainWindow):
 
     def _library_unreadable(self, error: Exception) -> None:
         """Archiv der Symbol-Bibliothek fehlt oder ist beschädigt: Meldung statt Traceback."""
-        self._set_result(f"Symbol-Bibliothek nicht lesbar: {error}", "error")
+        self._set_result(_("Symbol library unreadable: {error}").format(error=error), "error")
 
     def _favorites_changed(self, favorites: list[str]) -> None:
         self.settings.symbols_favorites = list(favorites)
@@ -1361,8 +1374,8 @@ class MainWindow(QMainWindow):
         if not self.settings.image_crop:
             return ImageObject.from_image(image, dpi, source, page, None, svg)
         crop = crop_box(image, dpi, ink=NOT_WHITE)
-        if crop is None and CROP_FAILED not in notes:
-            notes.append(CROP_FAILED)
+        if crop is None and _(CROP_FAILED) not in notes:
+            notes.append(_(CROP_FAILED))
         return ImageObject.from_image(image, dpi, source, page, crop, svg)
 
     def _insert_images(self, objects: list[ImageObject], at: tuple[float, float] | None,
@@ -1396,7 +1409,7 @@ class MainWindow(QMainWindow):
                     smallest, shrunk_mode = factor, obj.mode
             self._insert(objects)
             if turned:
-                notes.append(TURNED_HINT)
+                notes.append(_(TURNED_HINT))
             if smallest < 1:
                 notes.append(shrunk_hint(smallest, shrunk_mode))
         self._show_notice(notes, state)
@@ -1460,24 +1473,25 @@ class MainWindow(QMainWindow):
                     and chosen.uri != self.printer.uri)
         self.printers, self.printer = found or [], chosen
         if found is None:
-            text = "○ Druckerstatus unbekannt"
+            text = _("○ Printer status unknown")
         elif chosen is None and self.settings.printer:
-            text = "○ gewählter Drucker fehlt"
-            tip = f"{self.settings.printer} nicht gefunden – einschalten oder einen anderen wählen"
+            text = _("○ selected printer missing")
+            tip = _("{printer} not found – switch it on or choose another one").format(
+                printer=self.settings.printer)
         elif chosen is not None:
             text = f"● {chosen.name}"
             if chosen.model is None:
-                text += f" (als {self.model})"
-                tip = "Modell nicht erkannt – in den Einstellungen ein Ersatzmodell wählen"
+                text = _("● {name} (as {model})").format(name=chosen.name, model=self.model)
+                tip = _("Model not recognized – choose a fallback model in the settings")
             elif not capabilities(chosen.model).tested:
-                text += " · ungeprüft"
-                tip = f"{chosen.model}: {UNTESTED_HINT}"
+                text = _("● {name} · untested").format(name=chosen.name)
+                tip = f"{chosen.model}: {_(UNTESTED_HINT)}"
         elif busy:
-            text = "● Drucker belegt (andere Anwendung)"
+            text = _("● Printer busy (another application)")
         else:
-            text = "○ kein Drucker"
+            text = _("○ no printer")
         self.printer_status.setText(text)
-        self.printer_status.setToolTip(tip or "Drucker wählen")
+        self.printer_status.setToolTip(tip or _("Choose printer"))
         if chosen is not None and chosen.model and chosen.model != self.settings.last_model:
             self.settings.last_model = chosen.model     # gilt beim nächsten Start ohne Drucker
             self._save_settings()
@@ -1507,21 +1521,22 @@ class MainWindow(QMainWindow):
         """Menü am Druckerknopf: Automatisch, gefundene Drucker, Netzwerkdrucker eintragen."""
         menu = self.printer_menu
         menu.clear()
-        auto = menu.addAction("Automatisch (erster gefundener)")
+        auto = menu.addAction(_("Automatic (first found)"))
         auto.setCheckable(True)
         auto.setChecked(not self.settings.printer)
         auto.triggered.connect(lambda _=False: self.choose_printer(""))
         for printer in self.printers:
             untested = printer.model is not None and not capabilities(printer.model).tested
-            action = menu.addAction(printer.name + (" – ungeprüft" if untested else ""))
+            action = menu.addAction(_("{name} – untested").format(name=printer.name) if untested
+                                    else printer.name)
             action.setCheckable(True)
             action.setChecked(printer.uri == self.settings.printer)
-            action.setToolTip(UNTESTED_HINT if untested else printer.uri)
+            action.setToolTip(_(UNTESTED_HINT) if untested else printer.uri)
             action.triggered.connect(lambda _=False, uri=printer.uri: self.choose_printer(uri))
         if not self.printers:
-            menu.addAction("Kein Drucker gefunden").setEnabled(False)
+            menu.addAction(_("No printer found")).setEnabled(False)
         menu.addSeparator()
-        menu.addAction("Netzwerkdrucker eintragen …", self.open_settings)
+        menu.addAction(_("Add network printer …"), self.open_settings)
 
     def choose_printer(self, uri: str) -> None:
         """Drucker wählen (URI; "" = automatisch) – gespeichert."""
@@ -1547,7 +1562,7 @@ class MainWindow(QMainWindow):
         if self.model.startswith("cups:"):
             panel.set_driver_cuts(cups.queue_info(self.model[len("cups:"):]).cut_options, chosen)
         elif zpl.is_model(self.model):
-            panel.set_driver_cuts((zpl.CUT_OPTION,), chosen)
+            panel.set_driver_cuts((zpl.cut_option(),), chosen)
         else:
             panel.set_cutter(capabilities(self.model).cutter)
 
@@ -1573,11 +1588,13 @@ class MainWindow(QMainWindow):
             self.panel("paper").refresh()
             self.history.reset(self.doc)            # unberührt: kein Schritt zurück zum Unpassenden
             self.files.mark_unchanged()
-            self._set_result(f"Etikett {get_label(label).description} passt nicht zum {self.model} "
-                             f"– {get_label(self.doc.label_id).description} genommen", "warn")
+            self._set_result(_("Label {label} does not fit the {model} – using {new}").format(
+                label=get_label(label).description, model=self.model,
+                new=get_label(self.doc.label_id).description), "warn")
             return
-        self._set_result(f"Etikett {get_label(label).description} passt nicht zum Drucker "
-                         f"({self.model}) – im Reiter Papier ein anderes wählen", "error")
+        self._set_result(_("Label {label} does not fit the printer ({model}) – choose another one "
+                           "in the Paper tab").format(label=get_label(label).description,
+                                                      model=self.model), "error")
 
     def _run_pending_media_check(self) -> None:
         """Automatische Prüfung nachholen, sobald weder Druck noch Prüfung laufen."""
@@ -1595,7 +1612,8 @@ class MainWindow(QMainWindow):
         if name:
             favorite = favorites.find(name)
             if favorite is None:
-                self._set_result(f"Start-Favorit „{name}“ nicht gefunden – leeres Etikett", "error")
+                self._set_result(_("Start favorite “{name}” not found – empty label").format(
+                    name=name), "error")
             else:
                 self.files.open_favorite(favorite)
 
@@ -1623,7 +1641,7 @@ class MainWindow(QMainWindow):
                 self.shortcut_actions[entry[0]].setIcon(line_icon(entry[1], dark, hover=True))
 
     def open_settings(self) -> None:
-        dialog = SettingsDialog(self.settings, model=self.model, parent=self)
+        dialog = SettingsDialog(self.settings, model=self.model, parent=self, started=self._started)
         accepted = dialog.exec() == SettingsDialog.DialogCode.Accepted
         saved = dialog.saved
         dialog.deleteLater()                    # nicht bis zum Schließen des Fensters behalten
@@ -1644,7 +1662,7 @@ class MainWindow(QMainWindow):
                             without_conflicts(effective(self.settings.shortcuts))[0])
             self.files.refresh_lists()                  # „Beim Start“ im Reiter Datei
             self.refresh_printer()                      # Netzwerkdrucker, Ersatzmodell
-            self._set_result("Einstellungen gespeichert – gelten für neue Etiketten.", "ok")
+            self._set_result(_("Settings saved – they apply to new labels."), "ok")
 
     # --- Medium prüfen ----------------------------------------------------
     def is_printing(self) -> bool:
@@ -1701,15 +1719,15 @@ class MainWindow(QMainWindow):
 
     def confirm_outside(self) -> bool:
         answer = QMessageBox.question(
-            self, "Objekt ragt hinaus",
-            "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?",
+            self, _("Object sticks out"),
+            _("An object extends beyond the label and will be cut off. Print anyway?"),
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
             QMessageBox.StandardButton.No)
         return answer == QMessageBox.StandardButton.Yes
 
     def confirm_empty(self) -> bool:
         answer = QMessageBox.question(
-            self, "Leeres Etikett", "Das Etikett ist leer. Trotzdem drucken?",
+            self, _("Empty label"), _("The label is empty. Print anyway?"),
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
             QMessageBox.StandardButton.Cancel)
         return answer == QMessageBox.StandardButton.Yes
@@ -1735,12 +1753,12 @@ class MainWindow(QMainWindow):
             panel = self.panel("series")
             if panel.check_file():                  # Tabelle draußen geändert: Auswahl ist neu
                 self.render_now()
-                self._set_result(f"Serie: {panel.error}" if panel.error else
-                                 "Tabelle wurde geändert und neu eingelesen – Auswahl prüfen und "
-                                 "erneut drucken.", "error")
+                self._set_result(_("Series: {error}").format(error=panel.error) if panel.error
+                                 else _("The table has changed and was read again – check the "
+                                        "selection and print again."), "error")
                 return
             if panel.error:
-                self._set_result(f"Serie: {panel.error}", "error")
+                self._set_result(_("Series: {error}").format(error=panel.error), "error")
                 return
             self._print_series(self.doc, panel.table, panel.checked_rows())
             return
@@ -1757,16 +1775,16 @@ class MainWindow(QMainWindow):
         jede Zeile rendern (Fortschritt in der Statusleiste), Zeilen, die über das Etikett
         ragen, nennen und fragen – ein Auftrag. Scheitert eine Zeile, wird nichts gedruckt."""
         if not table.rows:
-            self._set_result("Tabelle hat keine Zeilen – nichts gedruckt.", "error")
+            self._set_result(_("The table has no rows – nothing printed."), "error")
             return
         if not rows:
-            self._set_result("Keine Zeile gewählt – nichts gedruckt.", "error")
+            self._set_result(_("No row selected – nothing printed."), "error")
             return
         if self.is_checking_media():
-            self._set_result("Rolle wird gerade geprüft – bitte gleich noch einmal drucken.", "error")
+            self._set_result(_(CHECKING_ROLL), "error")
             return
         if self.is_printing():
-            self._set_result("Druck läuft – bitte warten.", "error")
+            self._set_result(_(PRINTING_WAIT), "error")
             return
         if not self._can_print(doc):
             return
@@ -1783,16 +1801,17 @@ class MainWindow(QMainWindow):
         try:
             for done, (number, values) in enumerate(rows):
                 if done % PROGRESS_EVERY == 0 and len(rows) > PROGRESS_EVERY:
-                    self._set_result(f"Bereite {done + 1}/{len(rows)} vor …", "")
+                    self._set_result(_("Preparing {current}/{total} …").format(
+                        current=done + 1, total=len(rows)), "")
                     QApplication.processEvents()    # auch „Abbrechen“
                     if self._cancel_requested:
-                        self._set_result("Abgebrochen – nichts gedruckt", "")
+                        self._set_result(_("Cancelled – nothing printed"), "")
                         return
                 try:
                     result = renderer.render(fill_anchored(doc, table.columns, values, model),
                                              model)
                 except ValueError as e:
-                    self._set_result(f"Zeile {number}: {e}", "error")
+                    self._set_result(_("Row {row}: {message}").format(row=number, message=e), "error")
                     return
                 if outside_indices(result.objects, result.size, doc.objects):
                     outside.append(number)
@@ -1809,18 +1828,19 @@ class MainWindow(QMainWindow):
     def confirm_outside_rows(self, numbers: list[int]) -> bool:
         """Rückfrage: Zeilen, in denen etwas über das Etikett ragt (in Tests ersetzbar)."""
         shown = ", ".join(map(str, numbers[:10])) + (" …" if len(numbers) > 10 else "")
-        text = (f"Zeile {shown} ragt" if len(numbers) == 1 else f"Zeilen {shown} ragen")
+        text = ngettext("Row {rows} extends beyond the label and will be cut off. Print anyway?",
+                        "Rows {rows} extend beyond the label and will be cut off. Print anyway?",
+                        len(numbers)).format(rows=shown)
         return QMessageBox.question(
-            self, "Objekt ragt hinaus",
-            f"{text} über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?",
+            self, _("Object sticks out"), text,
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
             QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
 
     def ask_print_count(self, count: int) -> bool:
         """Rückfrage vor dem Drucken einer Serie (in Tests ersetzbar)."""
-        text = "1 Etikett drucken?" if count == 1 else f"{count} Etiketten drucken?"
+        text = ngettext("Print {count} label?", "Print {count} labels?", count).format(count=count)
         return QMessageBox.question(
-            self, "Serie drucken", text,
+            self, _("Print series"), text,
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
             QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes
 
@@ -1828,7 +1848,7 @@ class MainWindow(QMainWindow):
         """Anderes Etikett drucken (Favorit), ohne das offene anzutasten – gleiche Rückfragen;
         mit Serie alle Zeilen."""
         if self.is_printing():
-            self._set_result("Druck läuft – bitte warten.", "error")
+            self._set_result(_(PRINTING_WAIT), "error")
             return
         if doc.series is not None:
             try:
@@ -1837,7 +1857,8 @@ class MainWindow(QMainWindow):
                 self._set_result(str(e), "error")
                 return
             except Exception as e:  # fremde Datei: Meldung statt Traceback
-                self._set_result(f"Serie kann nicht gelesen werden ({type(e).__name__})", "error")
+                self._set_result(_("Cannot read the series ({error})").format(
+                    error=type(e).__name__), "error")
                 return
             self._print_series(doc, table, list(enumerate(table.rows, start=1)))
             return
@@ -1848,23 +1869,24 @@ class MainWindow(QMainWindow):
             self._set_result(str(e), "error")
             return
         except Exception as e:  # fremde Datei: Meldung statt Traceback
-            self._set_result(f"Etikett kann nicht gedruckt werden ({type(e).__name__})", "error")
+            self._set_result(_("Cannot print the label ({error})").format(
+                error=type(e).__name__), "error")
             return
         self._print(image, doc, outside)
 
     def _can_print(self, doc: Document) -> bool:
         """Vor dem Rendern prüfbar: gewählter Drucker da, Etikett passt zum Modell (Meldung)."""
         if self.printer is None and self.settings.printer:
-            self._set_result("Gewählter Drucker nicht gefunden – einschalten oder in der "
-                             "Statusleiste einen anderen wählen.", "error")
+            self._set_result(_("Selected printer not found – switch it on or choose another one "
+                               "in the status bar."), "error")
             return False
         if self.printer is None and not printers_mod.brother_model(self.model):
-            self._set_result("Kein Drucker für dieses Etikett – in der Statusleiste einen Drucker "
-                             "wählen.", "error")
+            self._set_result(_("No printer for this label – choose a printer in the status bar."),
+                             "error")
             return False
         if doc.label_id not in {label.id for label in labels_for_model(self.model)}:
-            self._set_result(f"Etikett „{doc.label_id}“ passt nicht zum Drucker ({self.model}).",
-                             "error")
+            self._set_result(_("Label “{label}” does not fit the printer ({model}).").format(
+                label=doc.label_id, model=self.model), "error")
             return False
         return True
 
@@ -1873,7 +1895,7 @@ class MainWindow(QMainWindow):
         """``image``: ein Druckbild oder eine Liste (Serie, ein Auftrag); ``model``/``printer``:
         festgehalten beim Start einer Serie (sonst die jetzigen)."""
         if self.is_checking_media():
-            self._set_result("Rolle wird gerade geprüft – bitte gleich noch einmal drucken.", "error")
+            self._set_result(_(CHECKING_ROLL), "error")
             return
         if model is None:
             if not self._can_print(doc):
@@ -1889,7 +1911,7 @@ class MainWindow(QMainWindow):
             return
         self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
         self.result.style().polish(self.result)
-        self.result.setText("Drucke …")
+        self.result.setText(_("Printing …"))
         options = (self.settings.printer_options.get(model, {})
                    if model.startswith("cups:") or zpl.is_model(model) else {})
         worker = PrintWorker(image, doc.label_id, model, cut_every,
@@ -1899,7 +1921,8 @@ class MainWindow(QMainWindow):
         worker.signals.done.connect(self._print_done)
         worker.signals.failed.connect(self._print_failed)
         worker.signals.progress.connect(
-            lambda done, total: self._set_result(f"Drucke … {done} von {total}", ""))
+            lambda done, total: self._set_result(
+                _("Printing … {done} of {total}").format(done=done, total=total), ""))
         worker.signals.cancelled.connect(self._print_cancelled)
         # übers Netz geht eine Serie als ein Auftrag hinaus (kein Status): nichts abzubrechen
         self.cancel_button.setVisible(isinstance(image, list) and len(image) > 1
@@ -1912,7 +1935,7 @@ class MainWindow(QMainWindow):
         self._cancel_requested = True
         if self._worker is not None:
             self._worker.cancel()
-            self._set_result("Wird abgebrochen …", "")
+            self._set_result(_("Cancelling …"), "")
 
     def _set_printing(self, printing: bool) -> None:
         self._printing = printing
@@ -1927,8 +1950,8 @@ class MainWindow(QMainWindow):
         missing = self.printer is None and bool(self.settings.printer)     # gewählter fehlt
         check.setEnabled(not self._printing and not network and not missing
                          and not self.is_checking_media())
-        check.setToolTip("Medium prüfen geht nur bei Brother-Druckern per USB" if network
-                         else "Eingelegte Rolle vom Drucker abfragen (druckt nichts)")
+        check.setToolTip(_("Check media only works with Brother printers via USB") if network
+                         else _("Ask the printer which roll is loaded (prints nothing)"))
 
     def _print_done(self, status: dict) -> None:
         ok = status.get("did_print") or status.get("outcome") in ("sent", "printed")
@@ -1936,11 +1959,13 @@ class MainWindow(QMainWindow):
         sent_only = status.get("outcome") == "sent" and not status.get("did_print")
         if status.get("job"):
             self.result.setProperty("state", "ok")
-            self.result.setText(f"An die Druckwarteschlange übergeben ✓ (Auftrag {status['job']})")
+            self.result.setText(_("Handed to the print queue ✓ (job {job})").format(
+                job=status["job"]))
             self._print_finished()
             return
-        self.result.setText(("Gesendet ✓ (der Drucker meldet keinen Status zurück)" if sent_only
-                             else "Gedruckt ✓") if ok else f"Status: {status.get('outcome')}")
+        self.result.setText((_("Sent ✓ (the printer reports no status)") if sent_only
+                             else _("Printed ✓")) if ok
+                            else _("Status: {outcome}").format(outcome=status.get("outcome")))
         self._print_finished()
 
     def _print_cancelled(self, message: str) -> None:
diff --git a/src/labelwerk/gui/media_worker.py b/src/labelwerk/gui/media_worker.py
index 1b5486b..6161023 100644
--- a/src/labelwerk/gui/media_worker.py
+++ b/src/labelwerk/gui/media_worker.py
@@ -3,6 +3,7 @@ from __future__ import annotations
 
 from PySide6.QtCore import QObject, QRunnable, Signal
 
+from ..i18n import _
 from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
 from ..media import MediaError, label_for_media, read_media
 
@@ -23,13 +24,13 @@ class MediaWorker(QRunnable):
         try:
             printer = self.printer or find_brother_lp()
             if printer is None:
-                self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
+                self.signals.failed.emit(_(BUSY_MESSAGE) if brother_busy() else _(PRINTER_NOT_FOUND))
                 return
             media = read_media(printer)
         except MediaError as e:
             self.signals.failed.emit(str(e))
             return
         except Exception as e:  # kein Absturz des Threads; Meldung statt Traceback
-            self.signals.failed.emit(f"Unerwarteter Fehler beim Prüfen der Rolle: {e}")
+            self.signals.failed.emit(_("Unexpected error while checking the roll: {error}").format(error=e))
             return
         self.signals.found.emit(media, label_for_media(media, self.model))
diff --git a/src/labelwerk/gui/panels/__init__.py b/src/labelwerk/gui/panels/__init__.py
index 8ef5b00..45fa779 100644
--- a/src/labelwerk/gui/panels/__init__.py
+++ b/src/labelwerk/gui/panels/__init__.py
@@ -29,6 +29,7 @@ class Panel(QWidget):
     def section(self, text: str) -> QLabel:
         label = QLabel(text.upper())
         label.setProperty("role", "section")
+        label.setWordWrap(True)                  # lange Titel (andere Sprachen) brechen um
         self.layout_.addWidget(label)
         return label
 
diff --git a/src/labelwerk/gui/panels/barcode.py b/src/labelwerk/gui/panels/barcode.py
index 467c689..23c5c56 100644
--- a/src/labelwerk/gui/panels/barcode.py
+++ b/src/labelwerk/gui/panels/barcode.py
@@ -21,6 +21,8 @@ from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, Q
 from ... import barcodes, series
 from ...document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, BarcodeObject,
                          Document)
+from ... import i18n
+from ...i18n import N_, _
 from ...labels import DPI
 from ...layout import Rect
 from ..symbols import SIZE, line_icon
@@ -28,15 +30,15 @@ from ..widgets import DoubleSpinBox, SpinBox
 from . import Panel
 from .position import PositionSection
 
-HINT = "Barcode oder QR-Code einfügen – Art wählen, Inhalt eintippen"
-LEVELS = (("L", "L – 7 %"), ("M", "M – 15 %"), ("Q", "Q – 25 %"), ("H", "H – 30 %"))
+HINT = N_("Insert a barcode or QR code – choose the type, type the content")
+LEVELS = (("L", N_("L – 7%")), ("M", N_("M – 15%")), ("Q", N_("Q – 25%")), ("H", N_("H – 30%")))
 _NUMBER = re.compile(r"\d*[.,]?\d*")
 _ROTATE = (("rotate_left", "object.rotate_left", "rotate-left"),     # (Attribut, Aktion, Symbol)
            ("rotate_right", "object.rotate_right", "rotate-right"))
 
 
 def _mm(value: float) -> str:
-    return f"{value:.1f}".replace(".", ",")
+    return i18n.number(value, 1)
 
 
 class ModuleSpin(SpinBox):
@@ -57,7 +59,7 @@ class ModuleSpin(SpinBox):
             self.lineEdit().setText(self.textFromValue(self.value()) + self.suffix())
 
     def textFromValue(self, value: int) -> str:
-        return f"{value * 25.4 / self.dpi:.2f}"
+        return i18n.number(value * 25.4 / self.dpi, 2)
 
     def _dots(self, text: str) -> int | None:
         """Getippte mm → Druckpunkte; None, wenn (noch) keine gültige Zahl."""
@@ -100,7 +102,7 @@ class BarcodePanel(Panel):
     frame_edited = Signal(str, float)   # Feld im Bereich „Position“ ("x" | "y" | "w" | "h"), mm
 
     def __init__(self, doc: Document):
-        super().__init__(doc, "Barcode")
+        super().__init__(doc, _("Barcode"))
         self.index: int | None = None   # bearbeiteter Barcode; None = keiner ausgewählt
         # Serie: Barcode mit dem Wert der Vorschau-Zeile (Hauptfenster), für den Prüfhinweis
         self.fill_preview: Callable[[BarcodeObject], BarcodeObject] | None = None
@@ -108,27 +110,27 @@ class BarcodePanel(Panel):
         self._updating = False
         self._typing = False            # Inhalt wird gerade getippt (ein Rückgängig-Schritt)
 
-        self.hint = QLabel(HINT)
+        self.hint = QLabel(_(HINT))
         self.hint.setObjectName("hint")
         self.hint.setWordWrap(True)
         self.layout_.addWidget(self.hint)
 
-        self.section("Art")
+        self.section(_("Type"))
         self.kind = QComboBox()
         for kind in BARCODE_KINDS:
-            self.kind.addItem(barcodes.TITLES[kind], kind)
-        self.kind.setToolTip("Art des Barcodes – für den gewählten bzw. den nächsten")
+            self.kind.addItem(_(barcodes.TITLES[kind]), kind)
+        self.kind.setToolTip(_("Type of barcode – for the selected one or the next one"))
         self.layout_.addWidget(self.kind)
-        self.insert = QPushButton("BARCODE EINFÜGEN")
-        self.insert.setToolTip("Barcode der gewählten Art einfügen")
+        self.insert = QPushButton(_("INSERT BARCODE"))
+        self.insert.setToolTip(_("Insert a barcode of the chosen type"))
         self.layout_.addWidget(self.insert)
 
-        self.section("Inhalt")
+        self.section(_("Content"))
         self.data = QLineEdit()
         self.data.setMaxLength(MAX_BARCODE_DATA)
         self._keep_undo = _KeepUndo(self)
         self.data.installEventFilter(self._keep_undo)
-        self.data.setToolTip("Inhalt des Codes; {Spalte} füllt die Serie")
+        self.data.setToolTip(_("Content of the code; {{column}} is filled by the series").format())
         self.layout_.addWidget(self.data)
         self.check = QLabel()
         self.check.setObjectName("hint")
@@ -136,27 +138,27 @@ class BarcodePanel(Panel):
         self.check.setTextFormat(Qt.TextFormat.PlainText)
         self.layout_.addWidget(self.check)
 
-        self.section("Größe")
+        self.section(_("Size"))
         self.size_box = QWidget()
         grid = QGridLayout(self.size_box)
         grid.setContentsMargins(0, 0, 0, 0)
         self.module = ModuleSpin()
         self.module.setKeyboardTracking(False)
-        self.module.setToolTip("Breite des schmalsten Strichs bzw. eines QR-Quadrats – in ganzen "
-                               "Druckpunkten (0,085 mm), damit der Code lesbar bleibt")
+        self.module.setToolTip(_("Width of the narrowest bar or of one QR square – in whole dots "
+                                 "(0.085 mm), so the code stays readable"))
         self.height = DoubleSpinBox()
         self.height.setSuffix(" mm")
         self.height.setDecimals(1)
         self.height.setSingleStep(0.5)
         self.height.setRange(*BARCODE_MM)
         self.height.setKeyboardTracking(False)
-        self.height.setToolTip("Höhe samt Klartext")
+        self.height.setToolTip(_("Height including the human-readable text"))
         self.error = QComboBox()
         for level, title in LEVELS:
-            self.error.addItem(title, level)
-        self.error.setToolTip("Fehlerkorrektur: höher = lesbar trotz Schmutz/Kratzern, aber größer")
-        self.module_label, self.height_label = QLabel("Modul"), QLabel("Höhe")
-        self.error_label = QLabel("Fehlerkorrektur")
+            self.error.addItem(_(title), level)
+        self.error.setToolTip(_("Error correction: higher = readable despite dirt/scratches, but larger"))
+        self.module_label, self.height_label = QLabel(_("Module")), QLabel(_("Height"))
+        self.error_label = QLabel(_("Error correction"))
         for row, (label, widget) in enumerate(((self.module_label, self.module),
                                                (self.height_label, self.height),
                                                (self.error_label, self.error))):
@@ -164,18 +166,18 @@ class BarcodePanel(Panel):
             grid.addWidget(widget, row, 1)
         grid.setColumnStretch(1, 1)
         self.layout_.addWidget(self.size_box)
-        self.text = QCheckBox("Klartext")
-        self.text.setToolTip("Inhalt unter dem Strichcode lesbar drucken")
+        self.text = QCheckBox(_("Human-readable text"))
+        self.text.setToolTip(_("Print the content readable below the barcode"))
         self.layout_.addWidget(self.text)
         self.quiet = QLabel()
         self.quiet.setObjectName("hint")
         self.quiet.setWordWrap(True)
         self.layout_.addWidget(self.quiet)
 
-        self.section("Drehen")
+        self.section(_("Rotate"))
         row = QHBoxLayout()
         row.setSpacing(4)
-        for attr, _, _ in _ROTATE:
+        for attr, __, ___ in _ROTATE:
             button = QToolButton()
             button.setObjectName("layoutButton")
             button.setAutoRaise(True)
@@ -186,7 +188,7 @@ class BarcodePanel(Panel):
         self.layout_.addLayout(row)
         self.set_icon_style(True)
 
-        self.section("Position (mm)")
+        self.section(_("Position (mm)"))
         self.position = PositionSection()
         self.position.edited.connect(self._frame_changed)
         self.layout_.addWidget(self.position)
@@ -200,23 +202,23 @@ class BarcodePanel(Panel):
         self.module.valueChanged.connect(lambda v: step(self._set, module=v))
         self.height.valueChanged.connect(lambda v: step(self._set, h_mm=round(v, 3)))
         self.text.clicked.connect(lambda on: step(self._set, text=on))
-        self.error.activated.connect(lambda _: step(self._set, error=self.error.currentData()))
+        self.error.activated.connect(lambda _index: step(self._set, error=self.error.currentData()))
 
     def use_actions(self, actions: dict[str, QAction]) -> None:
         """„Barcode einfügen“ und Drehen lösen ihre Aktionen aus (Kürzel im Tooltip); die Art
         zum Einfügen liest das Hauptfenster aus ``chosen_kind``."""
         insert = actions["barcode.insert"]
-        self.insert.clicked.connect(lambda _=False: insert.trigger())
+        self.insert.clicked.connect(lambda _checked=False: insert.trigger())
         self.insert.setToolTip(insert.toolTip())
         insert.changed.connect(lambda: self.insert.setToolTip(insert.toolTip()))
-        for attr, key, _ in _ROTATE:
+        for attr, key, __ in _ROTATE:
             button, rotate = getattr(self, attr), actions[key]
-            button.clicked.connect(lambda _=False, a=rotate: a.trigger())
+            button.clicked.connect(lambda _checked=False, a=rotate: a.trigger())
             button.setToolTip(rotate.toolTip())
             rotate.changed.connect(lambda b=button, a=rotate: b.setToolTip(a.toolTip()))
 
     def set_icon_style(self, dark_checked: bool) -> None:
-        for attr, _, icon in _ROTATE:
+        for attr, __, icon in _ROTATE:
             getattr(self, attr).setIcon(line_icon(icon, dark_checked, hover=True))
 
     @property
@@ -300,12 +302,14 @@ class BarcodePanel(Panel):
         else:
             completed = code.readable if obj.kind in ("ean13", "ean8") else ""
             given = "".join(obj.data.split())
-            self._set_check(f"Mit Prüfziffer: {completed}" if completed and completed != given
-                            else "")
-        side = "ringsum" if obj.kind == "qr" else "links und rechts je"
-        red = (" · Rot lesen viele Scanner schlecht" if obj.color == "red" and self.red_available
-               else "")
-        self.quiet.setText(f"Ruhezone: {side} {_mm(barcodes.quiet_mm(obj, self.module.dpi))} mm frei lassen{red}")
+            self._set_check(_("With check digit: {code}").format(code=completed)
+                            if completed and completed != given else "")
+        quiet = (_("Quiet zone: leave {mm} mm free all around") if obj.kind == "qr"
+                 else _("Quiet zone: leave {mm} mm free on the left and right each"))
+        text = quiet.format(mm=_mm(barcodes.quiet_mm(obj, self.module.dpi)))
+        if obj.color == "red" and self.red_available:
+            text += " · " + _("Many scanners read red poorly")
+        self.quiet.setText(text)
 
     def _set_check(self, text: str) -> None:
         self.check.setText(text)
diff --git a/src/labelwerk/gui/panels/file.py b/src/labelwerk/gui/panels/file.py
index dd63311..8b33cc9 100644
--- a/src/labelwerk/gui/panels/file.py
+++ b/src/labelwerk/gui/panels/file.py
@@ -14,14 +14,15 @@ from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem
 
 from ...document import Document
 from ...favorites import Favorite
+from ...i18n import N_, _
 from ...storage import exists
 from . import Panel
 
 PREVIEW = QSize(110, 46)            # Vorschau eines Favoriten (eingepasst)
 FAVORITE_ROWS = 5                   # so viele Favoriten sichtbar, mehr per Bildlauf
 RECENT_ROWS = 6
-FAVORITES_HINT = "Noch keine Favoriten – ein Etikett gestalten und „+ AKTUELL“ drücken."
-BROKEN = "nicht lesbar"
+FAVORITES_HINT = N_("No favorites yet – design a label and press “+ CURRENT”.")
+BROKEN = N_("unreadable")
 
 
 class _FavoriteRow(QWidget):
@@ -37,13 +38,13 @@ class _FavoriteRow(QWidget):
         if preview is not None:
             self.preview.setPixmap(preview)
         else:
-            self.preview.setText(BROKEN)
-        self.name = QLabel(f"{favorite.name}{'  ▸ Start' if start else ''}")
+            self.preview.setText(_(BROKEN))
+        self.name = QLabel(_("{name}  ▸ Start").format(name=favorite.name) if start else favorite.name)
         self.name.setTextFormat(Qt.TextFormat.PlainText)    # „<b>“ im Namen bleibt Text
         self.name.setWordWrap(True)
         self.print = QToolButton()
         self.print.setText("⎙")
-        self.print.setToolTip(f"„{favorite.name}“ drucken")
+        self.print.setToolTip(_("Print “{name}”").format(name=favorite.name))
         self.print.clicked.connect(on_print)
         row.addWidget(self.preview)
         row.addWidget(self.name, 1)
@@ -61,28 +62,28 @@ class FilePanel(Panel):
     recent_open = Signal(str)             # Pfad
 
     def __init__(self, doc: Document):
-        super().__init__(doc, "Datei")
+        super().__init__(doc, _("File"))
         self._favorites: list[Favorite] = []
         self._start: str | None = None
         self._printing = False
         self._recent: list[str] = []
         row = QHBoxLayout()
-        self.new = QPushButton("NEU")
-        self.open = QPushButton("ÖFFNEN …")
+        self.new = QPushButton(_("NEW"))
+        self.open = QPushButton(_("OPEN …"))
         row.addWidget(self.new)
         row.addWidget(self.open)
         self.layout_.addLayout(row)
-        self.save = QPushButton("SPEICHERN")
-        self.save_as = QPushButton("SPEICHERN UNTER …")
+        self.save = QPushButton(_("SAVE"))
+        self.save_as = QPushButton(_("SAVE AS …"))
         for button in (self.save, self.save_as):          # volle Breite: lange Beschriftung
             self.layout_.addWidget(button)
 
-        self.section("Favoriten")
-        self.add_favorite = QPushButton("+ AKTUELL")
-        self.add_favorite.setToolTip("Aktuelles Etikett als Favorit speichern")
+        self.section(_("Favorites"))
+        self.add_favorite = QPushButton(_("+ CURRENT"))
+        self.add_favorite.setToolTip(_("Save the current label as a favorite"))
         self.add_favorite.clicked.connect(self.favorite_add)
         self.layout_.addWidget(self.add_favorite)
-        self.favorites_hint = QLabel(FAVORITES_HINT)
+        self.favorites_hint = QLabel(_(FAVORITES_HINT))
         self.favorites_hint.setObjectName("hint")
         self.favorites_hint.setWordWrap(True)
         self.layout_.addWidget(self.favorites_hint)
@@ -93,7 +94,7 @@ class FilePanel(Panel):
         self.favorites.customContextMenuRequested.connect(self._favorite_context)
         self.layout_.addWidget(self.favorites)
 
-        self.section("Zuletzt geöffnet")
+        self.section(_("Recently opened"))
         self.recent = QListWidget()
         self.recent.setObjectName("recent")
         _open_on_click(self.recent, lambda row: self.open_recent_at(row))
@@ -105,7 +106,7 @@ class FilePanel(Panel):
         for button, key in ((self.new, "file.new"), (self.open, "file.open"),
                             (self.save, "file.save"), (self.save_as, "file.save_as")):
             action = actions[key]
-            button.clicked.connect(lambda _=False, a=action: a.trigger())
+            button.clicked.connect(lambda _checked=False, a=action: a.trigger())
             button.setToolTip(action.toolTip())
             action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))
 
@@ -114,7 +115,7 @@ class FilePanel(Panel):
                       start: str | None) -> None:
         """Liste neu füllen: (Favorit, Vorschau oder None = nicht lesbar); ``start`` = Name
         des Start-Favoriten."""
-        self._favorites = [f for f, _ in favorites]
+        self._favorites = [f for f, __ in favorites]
         self._start = start
         self.favorites.clear()
         for favorite, preview in favorites:
@@ -123,7 +124,7 @@ class FilePanel(Panel):
             item.setSizeHint(QSize(PREVIEW.width() + 120, PREVIEW.height() + 8))
             self.favorites.addItem(item)
             row = _FavoriteRow(favorite, preview, favorite.name == start,
-                               lambda _=False, f=favorite: self.favorite_print.emit(f))
+                               lambda _checked=False, f=favorite: self.favorite_print.emit(f))
             row.print.setEnabled(not self._printing)
             self.favorites.setItemWidget(item, row)
         self.favorites_hint.setVisible(not favorites)
@@ -154,14 +155,14 @@ class FilePanel(Panel):
         """Kontextmenü eines Favoriten."""
         favorite = self._favorites[row]
         menu = QMenu(self)
-        menu.addAction("Öffnen als neues Etikett", lambda: self.favorite_open.emit(favorite))
-        menu.addAction("Drucken", lambda: self.favorite_print.emit(favorite))
-        menu.addAction("Umbenennen …", lambda: self.favorite_rename.emit(favorite))
-        menu.addAction("Löschen …", lambda: self.favorite_remove.emit(favorite))
-        start = menu.addAction("Beim Start öffnen", lambda: self.favorite_start.emit(favorite))
+        menu.addAction(_("Open as new label"), lambda: self.favorite_open.emit(favorite))
+        menu.addAction(_("Print"), lambda: self.favorite_print.emit(favorite))
+        menu.addAction(_("Rename …"), lambda: self.favorite_rename.emit(favorite))
+        menu.addAction(_("Delete …"), lambda: self.favorite_remove.emit(favorite))
+        start = menu.addAction(_("Open at startup"), lambda: self.favorite_start.emit(favorite))
         start.setCheckable(True)
         start.setChecked(favorite.name == self._start)
-        menu.addAction("Ordner öffnen", lambda: self.favorites_folder.emit())
+        menu.addAction(_("Open folder"), lambda: self.favorites_folder.emit())
         return menu
 
     def _favorite_context(self, pos) -> None:
diff --git a/src/labelwerk/gui/panels/image.py b/src/labelwerk/gui/panels/image.py
index 60e635a..19f2ec7 100644
--- a/src/labelwerk/gui/panels/image.py
+++ b/src/labelwerk/gui/panels/image.py
@@ -18,16 +18,17 @@ from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QPu
 from ... import layout
 from ...document import Document, ImageObject
 from ...files import NOT_WHITE, crop_box, ink_box
+from ...i18n import N_, _
 from ...layout import Rect
-from ..image_import import is_symbol_source
+from ..image_import import is_symbol_source, source_title
 from ..symbols import SIZE, line_icon
 from ..widgets import SpinBox
 from . import Panel
 from .position import PositionSection
 
-HINT = ("Bild aus einer Datei, der Zwischenablage, als Bildschirmfoto oder Symbol einfügen – "
-        "oder aufs Etikett ziehen")
-CROP_FAILED = "Bild nicht zugeschnitten – nur weiße Fläche gefunden"
+HINT = N_("Insert an image from a file, the clipboard, as a screenshot or symbol – or drag it "
+          "onto the label")
+CROP_FAILED = N_("Image not cropped – only white area found")
 _SOURCE_PX = 240                    # Quelle: längere Namen in der Mitte gekürzt (Tooltip)
 _ROTATE = (("rotate_left", "object.rotate_left", "rotate-left"),     # (Attribut, Aktion, Symbol)
            ("rotate_right", "object.rotate_right", "rotate-right"))
@@ -39,40 +40,40 @@ class ImagePanel(Panel):
     message = Signal(str, str)          # Hinweis für die Statusleiste (Text, Zustand)
 
     def __init__(self, doc: Document):
-        super().__init__(doc, "Bild")
+        super().__init__(doc, _("Image"))
         self.index: int | None = None   # bearbeitetes Bild; None = keins ausgewählt
         self._updating = False
 
-        self.hint = QLabel(HINT)
+        self.hint = QLabel(_(HINT))
         self.hint.setObjectName("hint")
         self.hint.setWordWrap(True)
         self.layout_.addWidget(self.hint)
 
-        self.section("Einfügen")
-        self.from_file = QPushButton("AUS DATEI …")
-        self.from_file.setToolTip("Bild oder PDF-Seite einfügen")
-        self.from_clipboard = QPushButton("AUS ZWISCHENABLAGE")
-        self.from_clipboard.setToolTip("Bild aus der Zwischenablage einfügen")
+        self.section(_("Insert"))
+        self.from_file = QPushButton(_("FROM FILE …"))
+        self.from_file.setToolTip(_("Insert an image or PDF page"))
+        self.from_clipboard = QPushButton(_("FROM CLIPBOARD"))
+        self.from_clipboard.setToolTip(_("Insert an image from the clipboard"))
         self.from_clipboard.setEnabled(False)
         self.from_clipboard.clicked.connect(self.paste_requested)
-        self.screenshot = QPushButton("BILDSCHIRMFOTO")
-        self.screenshot.setToolTip("Bildschirmfoto einfügen")
-        self.symbol = QPushButton("SYMBOL")
-        self.symbol.setToolTip("Symbol einfügen …")
+        self.screenshot = QPushButton(_("SCREENSHOT"))
+        self.screenshot.setToolTip(_("Insert a screenshot"))
+        self.symbol = QPushButton(_("SYMBOL"))
+        self.symbol.setToolTip(_("Insert symbol …"))
         for button in (self.from_file, self.from_clipboard, self.screenshot, self.symbol):
             self.layout_.addWidget(button)
 
-        self.section("Quelle")
+        self.section(_("Source"))
         self.source = QLabel()
         self.source.setObjectName("imageSource")
         self.layout_.addWidget(self.source)
 
-        self.section("Umwandlung")
+        self.section(_("Conversion"))
         row = QHBoxLayout()
-        self.line = QRadioButton("Strich")
-        self.line.setToolTip("Harte Schwelle – für Codes, Schrift und Logos")
-        self.photo = QRadioButton("Foto")
-        self.photo.setToolTip("Graustufen als Rasterpunkte – für Fotos und Verläufe")
+        self.line = QRadioButton(_("Line art"))
+        self.line.setToolTip(_("Hard threshold – for codes, text and logos"))
+        self.photo = QRadioButton(_("Photo"))
+        self.photo.setToolTip(_("Grayscale as halftone dots – for photos and gradients"))
         self.mode_group = QButtonGroup(self)
         for button in (self.line, self.photo):
             self.mode_group.addButton(button)
@@ -80,11 +81,11 @@ class ImagePanel(Panel):
         row.addStretch()
         self.layout_.addLayout(row)
         row = QHBoxLayout()                    # „Schwelle [128]“, darunter der Regler
-        self.threshold_label = QLabel("Schwelle")
+        self.threshold_label = QLabel(_("Threshold"))
         self.threshold_value = SpinBox()
         self.threshold = QSlider(Qt.Orientation.Horizontal)
         for widget in (self.threshold_label, self.threshold, self.threshold_value):
-            widget.setToolTip("Höher = mehr Schwarz")
+            widget.setToolTip(_("Higher = darker"))
         self.threshold.setRange(0, 255)
         self.threshold_value.setRange(0, 255)
         self.threshold_value.setKeyboardTracking(False)
@@ -92,25 +93,25 @@ class ImagePanel(Panel):
         row.addWidget(self.threshold_value, 1)
         self.layout_.addLayout(row)
         self.layout_.addWidget(self.threshold)
-        self.invert = QCheckBox("Umkehren")
-        self.invert.setToolTip("Schwarz und Weiß tauschen")
+        self.invert = QCheckBox(_("Invert"))
+        self.invert.setToolTip(_("Swap black and white"))
         self.layout_.addWidget(self.invert)
 
-        self.section("Größe")
-        self.crop = QCheckBox("Zuschnitt automatisch")
-        self.crop.setToolTip("Auf den Inhalt zuschneiden (ohne Schnittmarken und Leerraum); "
-                             "aus = ganzes Bild")
-        self.keep_ratio = QCheckBox("Seitenverhältnis beibehalten")
-        self.keep_ratio.setToolTip("Anfasser und Felder skalieren das Bild ohne Verzerren")
-        self.original = QPushButton("ORIGINALGRÖSSE 1:1")
-        self.original.setToolTip("Druckgröße aus der Auflösung des Bilds (z. B. Briefmarke, Code)")
+        self.section(_("Size"))
+        self.crop = QCheckBox(_("Crop automatically"))
+        self.crop.setToolTip(_("Crop to the content (without crop marks and blank space); "
+                               "off = whole image"))
+        self.keep_ratio = QCheckBox(_("Keep aspect ratio"))
+        self.keep_ratio.setToolTip(_("Handles and fields scale the image without distortion"))
+        self.original = QPushButton(_("ORIGINAL SIZE 1:1"))
+        self.original.setToolTip(_("Print size from the resolution of the image (e.g. stamp, code)"))
         for widget in (self.crop, self.keep_ratio, self.original):
             self.layout_.addWidget(widget)
 
-        self.section("Drehen")
+        self.section(_("Rotate"))
         row = QHBoxLayout()
         row.setSpacing(4)
-        for attr, _, _ in _ROTATE:
+        for attr, __, ___ in _ROTATE:
             button = QToolButton()
             button.setObjectName("layoutButton")
             button.setAutoRaise(True)              # Symbol beim Darüberfahren: Modus „Active“
@@ -121,7 +122,7 @@ class ImagePanel(Panel):
         self.layout_.addLayout(row)
         self.set_icon_style(True)
 
-        self.section("Position (mm)")
+        self.section(_("Position (mm)"))
         self.position = PositionSection()
         self.position.edited.connect(self._frame_changed)
         self.layout_.addWidget(self.position)
@@ -148,18 +149,18 @@ class ImagePanel(Panel):
                             (self.screenshot, "image.screenshot"),
                             (self.symbol, "image.symbol")):
             action = actions[key]
-            button.clicked.connect(lambda _=False, a=action: a.trigger())
+            button.clicked.connect(lambda _checked=False, a=action: a.trigger())
             button.setToolTip(action.toolTip())
             action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))
         # Drehen: dieselben Aktionen wie im Reiter Layout (wirken auf die Auswahl = das Bild)
-        for attr, key, _ in _ROTATE:
+        for attr, key, __ in _ROTATE:
             button, rotate = getattr(self, attr), actions[key]
-            button.clicked.connect(lambda _=False, a=rotate: a.trigger())
+            button.clicked.connect(lambda _checked=False, a=rotate: a.trigger())
             button.setToolTip(rotate.toolTip())
             rotate.changed.connect(lambda b=button, a=rotate: b.setToolTip(a.toolTip()))
 
     def set_icon_style(self, dark_checked: bool) -> None:
-        for attr, _, icon in _ROTATE:
+        for attr, __, icon in _ROTATE:
             getattr(self, attr).setIcon(line_icon(icon, dark_checked, hover=True))
 
     @property
@@ -202,8 +203,9 @@ class ImagePanel(Panel):
                 self.show_frame(None)
                 return
             obj = self.obj
-            page = f" · Seite {obj.page}" if obj.page is not None else ""
-            self._show_source(f"{obj.source}{page}")
+            source = source_title(obj.source)
+            self._show_source(source if obj.page is None else
+                              _("{source} · page {page}").format(source=source, page=obj.page))
             (self.photo if obj.mode == "photo" else self.line).setChecked(True)
             self.threshold.setValue(obj.threshold)
             self.threshold_value.setValue(obj.threshold)
@@ -265,7 +267,7 @@ class ImagePanel(Panel):
             box = crop_box(self.obj.image(), self.obj.dpi, ink=NOT_WHITE)
         if box is None:
             self.refresh()                         # Haken wieder aus
-            self.message.emit(CROP_FAILED, "warn")
+            self.message.emit(_(CROP_FAILED), "warn")
             return
         self._change(lambda obj: layout.set_crop(obj, box))
 
diff --git a/src/labelwerk/gui/panels/layout.py b/src/labelwerk/gui/panels/layout.py
index 98303ae..47e8f67 100644
--- a/src/labelwerk/gui/panels/layout.py
+++ b/src/labelwerk/gui/panels/layout.py
@@ -10,40 +10,41 @@ from PySide6.QtGui import QAction
 from PySide6.QtWidgets import QHBoxLayout, QPushButton, QToolButton
 
 from ...document import Document
+from ...i18n import N_, _
 from ..symbols import SIZE, line_icon
 from . import Panel
 
 # Bereiche mit Knöpfen: (Aktion, Symbol)
 LAYOUT_SECTIONS = (
-    ("Gewählte Objekte ausrichten", tuple((f"align.{mode}", f"align-objects-{mode}") for mode in
+    (N_("Align selected objects"), tuple((f"align.{mode}", f"align-objects-{mode}") for mode in
                                           ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
-    ("Am Papier ausrichten", tuple((f"align.paper_{mode}", f"align-paper-{mode}") for mode in
+    (N_("Align to paper"), tuple((f"align.paper_{mode}", f"align-paper-{mode}") for mode in
                                    ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
-    ("Vergrößern/Verkleinern", (("size.maximize", "size-maximize"), ("size.same", "size-same"),
+    (N_("Resize"), (("size.maximize", "size-maximize"), ("size.same", "size-same"),
                                 ("size.width", "size-width"), ("size.height", "size-height"))),
-    ("Drehen", (("object.rotate_left", "rotate-left"), ("object.rotate_right", "rotate-right"))),
-    ("Reihenfolge", (("object.bring_forward", "order-forward"),
+    (N_("Rotate"), (("object.rotate_left", "rotate-left"), ("object.rotate_right", "rotate-right"))),
+    (N_("Order"), (("object.bring_forward", "order-forward"),
                      ("object.send_backward", "order-backward"))),
 )
-_ICONS = {key: icon for _, row in LAYOUT_SECTIONS for key, icon in row}
+_ICONS = {key: icon for __, row in LAYOUT_SECTIONS for key, icon in row}
 # Aneinander ausrichten und angleichen braucht mindestens zwei Objekte, alles andere eins
-_FROM_TWO = {key for key, _ in LAYOUT_SECTIONS[0][1]} | {"size.same", "size.width", "size.height"}
+_FROM_TWO = {key for key, __ in LAYOUT_SECTIONS[0][1]} | {"size.same", "size.width", "size.height"}
 MIN_SELECTED = {key: 2 if key in _FROM_TWO else 1 for key in _ICONS}
 # Am Papier in Bandrichtung ausrichten: je Achse der Leserichtung, in der das Etikett wächst
 _PAPER_AXIS = {f"align.paper_{mode}": axis for axis, modes in
                (("x", ("left", "hcenter", "right")), ("y", ("top", "vcenter", "bottom")))
                for mode in modes}
-GROWING_HINT = ("Bei automatischer Länge wächst das Etikett mit – "
-                "das Objekt sitzt mit gleichem Rand an beiden Enden")
-COLOR_TITLES = (("black", "SCHWARZ"), ("red", "ROT"))
-NO_RED = "Rot nur auf dem Etikett 62 mm Rot/Schwarz (DK-22251) mit einem QL-8xx"
+GROWING_HINT = N_("With automatic length the label grows along – "
+                  "the object keeps the same margin at both ends")
+COLOR_TITLES = (("black", N_("BLACK")), ("red", N_("RED")))
+NO_RED = N_("Red only on the 62 mm red/black label (DK-22251) with a QL-8xx")
 
 
 class LayoutPanel(Panel):
     color_chosen = Signal(str)          # Farbe für die Auswahl ("black" | "red")
 
     def __init__(self, doc: Document):
-        super().__init__(doc, "Layout")
+        super().__init__(doc, _("Layout"))
         self._dark = True
         self._count = 0
         self._red = False               # Etikett kann Rot
@@ -52,10 +53,11 @@ class LayoutPanel(Panel):
         for title, row in LAYOUT_SECTIONS:
             # lange Überschriften brechen an Leerzeichen um; ohne Leerzeichen nicht, sonst
             # reserviert Qt bei „/“ eine zweite Zeile
+            title = _(title)
             self.section(title).setWordWrap(" " in title)
             line = QHBoxLayout()
             line.setSpacing(4)
-            for key, _ in row:
+            for key, __ in row:
                 button = QToolButton()
                 button.setObjectName("layoutButton")
                 button.setAutoRaise(True)              # Symbol beim Darüberfahren: Modus „Active“
@@ -65,12 +67,12 @@ class LayoutPanel(Panel):
                 line.addWidget(button)
             line.addStretch()
             self.layout_.addLayout(line)
-        self.section("Farbe")
+        self.section(_("Color"))
         line = QHBoxLayout()
         self.colors: dict[str, QPushButton] = {}
         for color, title in COLOR_TITLES:
-            button = QPushButton(title)
-            button.clicked.connect(lambda _=False, c=color: self.color_chosen.emit(c))
+            button = QPushButton(_(title))
+            button.clicked.connect(lambda _checked=False, c=color: self.color_chosen.emit(c))
             self.colors[color] = button
             line.addWidget(button)
         self.layout_.addLayout(line)
@@ -103,14 +105,14 @@ class LayoutPanel(Panel):
     def _enable(self) -> None:
         for color, button in self.colors.items():          # Schwarz geht immer (zurück)
             button.setEnabled(self._count > 0 and (self._red or color == "black"))
-            button.setToolTip("" if self._red or color == "black" else NO_RED)
+            button.setToolTip("" if self._red or color == "black" else _(NO_RED))
         for key, button in self.buttons.items():
             target = button.defaultAction() or button
             growing = _PAPER_AXIS.get(key) == self._grow and self._grow is not None
             target.setEnabled(self._count >= MIN_SELECTED[key])
             if key in _PAPER_AXIS and button.defaultAction() is not None:
                 name = target.toolTip().split("\n")[0]
-                target.setToolTip(f"{name}\n{GROWING_HINT}" if growing else name)
+                target.setToolTip(f"{name}\n{_(GROWING_HINT)}" if growing else name)
 
     def set_icon_style(self, dark_checked: bool) -> None:
         self._dark = dark_checked
diff --git a/src/labelwerk/gui/panels/paper.py b/src/labelwerk/gui/panels/paper.py
index 4e66795..9be0f9f 100644
--- a/src/labelwerk/gui/panels/paper.py
+++ b/src/labelwerk/gui/panels/paper.py
@@ -10,6 +10,7 @@ from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout,
 
 from ... import layout
 from ...document import FRAME_LINE_MM, MAX_FRAME_MM, MAX_MARGIN_MM, Document, Frame
+from ...i18n import N_, _
 from ...labels import DPI, get_label, labels_for_model, length_limits, mm_text
 from ...media import Media
 from ...printer import DEFAULT_MODEL
@@ -17,12 +18,12 @@ from ...render import frame_mask
 from ..widgets import DoubleSpinBox
 from . import Panel
 
-_GROUPS = (("endless", "Endlos"), ("die_cut", "Gestanzt"), ("round", "Rund"))
-FRAME_TITLES = (("Kein", None), ("Einfach", "single"), ("Doppelt", "double"),
-                ("Dick-dünn", "thick_thin"), ("Gestrichelt", "dashed"), ("Gepunktet", "dotted"),
-                ("Nur Ecken", "corners"))
+_GROUPS = (("endless", N_("Continuous")), ("die_cut", N_("Die-cut")), ("round", N_("Round")))
+FRAME_TITLES = ((N_("No border"), None), (N_("Single"), "single"), (N_("Double"), "double"),
+                (N_("Thick-thin"), "thick_thin"), (N_("Dashed"), "dashed"), (N_("Dotted"), "dotted"),
+                (N_("Corners only"), "corners"))
 FRAME_ICON = QSize(56, 22)
-ROUND_TIP = "Auf runden Etiketten wird jeder Rahmen ein Kreis."
+ROUND_TIP = N_("On round labels every border becomes a circle.")
 
 
 def frame_icon(style: str | None) -> QIcon:
@@ -55,26 +56,26 @@ class PaperPanel(Panel):
     media_status_changed = Signal(str, str)   # Text, Zustand (ok/warn/error/"") für die Fußzeile
 
     def __init__(self, doc: Document, model: str = DEFAULT_MODEL):
-        super().__init__(doc, "Papier")
+        super().__init__(doc, _("Paper"))
         self.media: Media | None = None          # zuletzt erkannte Rolle
         self.media_label: str | None = None      # passendes Etikett dazu
         self.media_adjusted = False              # Etikett wurde automatisch angepasst
 
-        self.section("Etikett")
+        self.section(_("Label"))
         self.combo = QComboBox()
         self.model = model
         self._fill_labels()
         self.layout_.addWidget(self.combo)
-        self.check = QPushButton("MEDIUM PRÜFEN")
-        self.check.setToolTip("Eingelegte Rolle vom Drucker abfragen (druckt nichts)")
+        self.check = QPushButton(_("CHECK MEDIA"))
+        self.check.setToolTip(_("Ask the printer which roll is loaded (prints nothing)"))
         self.check.clicked.connect(self.check_media_requested)
         self.layout_.addWidget(self.check)
 
-        self.length_title = self.section("Länge")
+        self.length_title = self.section(_("Length"))
         self.length_box = QWidget()
         row = QHBoxLayout(self.length_box)
         row.setContentsMargins(0, 0, 0, 0)
-        self.length_auto = QCheckBox("Automatisch")
+        self.length_auto = QCheckBox(_("Automatic"))
         self.length = DoubleSpinBox()
         self.length.setSuffix(" mm")
         self.length.setDecimals(1)
@@ -89,46 +90,47 @@ class PaperPanel(Panel):
         self.fixed_size.setObjectName("fixedSize")
         self.layout_.addWidget(self.fixed_size)
 
-        self.section("Ausrichtung")
-        self.horizontal = QRadioButton("Horizontal")
-        self.horizontal.setToolTip("Etikett im Querformat – Leserichtung längs zum Band")
-        self.vertical = QRadioButton("Vertikal")
-        self.vertical.setToolTip("Etikett im Hochformat – Leserichtung quer zum Band")
+        self.section(_("Orientation"))
+        self.horizontal = QRadioButton(_("Horizontal"))
+        self.horizontal.setToolTip(_("Label in landscape – text runs along the tape"))
+        self.vertical = QRadioButton(_("Vertical"))
+        self.vertical.setToolTip(_("Label in portrait – text runs across the tape"))
         self.orientation_group = QButtonGroup(self)
         for button in (self.horizontal, self.vertical):
             self.orientation_group.addButton(button)
             self.layout_.addWidget(button)
-        self.section("Ränder")
+        self.section(_("Margins"))
         self.margin = DoubleSpinBox()
         self.margin.setSuffix(" mm")
         self.margin.setDecimals(1)
         self.margin.setSingleStep(0.5)
         self.margin.setRange(0.0, MAX_MARGIN_MM)
-        self.margin.setToolTip("Abstand zur Papierkante ringsum (quer lässt der Drucker ohnehin "
-                               "rund 1,5 mm frei)")
+        self.margin.setToolTip(_("Distance from the paper edge all around (across the tape the "
+                                 "printer leaves about 1.5 mm free anyway)"))
         self.layout_.addWidget(self.margin)
 
-        self.section("Rahmen")
+        self.section(_("Border"))
         self.frame_style = QComboBox()
         self.frame_style.setIconSize(FRAME_ICON)
         for title, style in FRAME_TITLES:
-            self.frame_style.addItem(frame_icon(style), title, style)
+            self.frame_style.addItem(frame_icon(style), _(title), style)
         self.layout_.addWidget(self.frame_style)
-        self.frame_rounded = QCheckBox("Abgerundet")
+        self.frame_rounded = QCheckBox(_("Rounded"))
         self.layout_.addWidget(self.frame_rounded)
         grid = QGridLayout()
         grid.setContentsMargins(0, 0, 0, 0)
         grid.setColumnStretch(1, 1)              # Felder füllen die Breite (wie die übrigen)
         defaults = Frame()
-        self.frame_line = _spin(*FRAME_LINE_MM, 0.1, "Strichstärke der Linie")
-        self.frame_inset = _spin(0.0, MAX_FRAME_MM, 0.5, "Abstand des Rahmens vom bedruckbaren Rand")
+        self.frame_line = _spin(*FRAME_LINE_MM, 0.1, _("Line width"))
+        self.frame_inset = _spin(0.0, MAX_FRAME_MM, 0.5,
+                                 _("Distance of the border from the printable edge"))
         self.frame_padding = _spin(0.0, MAX_FRAME_MM, 0.5,
-                                   "Abstand zwischen Rahmen und automatisch gesetztem Text")
+                                   _("Distance between the border and automatically placed text"))
         self.frame_labels: list[QLabel] = []
         for row, (title, box, value) in enumerate((
-                ("Linie", self.frame_line, defaults.line_mm),
-                ("Randabstand", self.frame_inset, defaults.inset_mm),
-                ("Innenabstand", self.frame_padding, defaults.padding_mm))):
+                (_("Line"), self.frame_line, defaults.line_mm),
+                (_("Inset"), self.frame_inset, defaults.inset_mm),
+                (_("Padding"), self.frame_padding, defaults.padding_mm))):
             box.setValue(value)
             label = QLabel(title)
             label.setToolTip(box.toolTip())
@@ -192,15 +194,15 @@ class PaperPanel(Panel):
             group = [lbl for lbl in labels if lbl.shape == shape]
             if not group:
                 continue
-            self.combo.addItem(f"— {title} —")
+            self.combo.addItem(f"— {_(title)} —")
             self.combo.model().item(self.combo.count() - 1).setEnabled(False)
             for lbl in group:
                 self.combo.addItem(lbl.description, lbl.id)
         self._unfit = None
         if self.combo.findData(self.doc.label_id) < 0:      # gewählt bleibt es, wählbar nicht
             self._unfit = self.doc.label_id
-            self.combo.addItem(f"{get_label(self.doc.label_id).description} – passt nicht zum "
-                               f"{self.model}", self.doc.label_id)
+            self.combo.addItem(_("{label} – does not fit the {model}").format(
+                label=get_label(self.doc.label_id).description, model=self.model), self.doc.label_id)
             self.combo.model().item(self.combo.count() - 1).setEnabled(False)
 
     def _set_length_range(self) -> None:
@@ -251,7 +253,7 @@ class PaperPanel(Panel):
     # --- Medium prüfen ----------------------------------------------------
     def set_checking(self, running: bool) -> None:
         self.check.setEnabled(not running)
-        self.check.setText("PRÜFE …" if running else "MEDIUM PRÜFEN")
+        self.check.setText(_("CHECKING …") if running else _("CHECK MEDIA"))
 
     def show_media(self, media: Media, label_id: str | None, adjusted: bool = False) -> None:
         self.media, self.media_label, self.media_adjusted = media, label_id, adjusted
@@ -269,14 +271,16 @@ class PaperPanel(Panel):
         if self.media is None:
             return
         if self.media.kind == "none":
-            self._set_media_status("Rolle: keine eingelegt", "warn")
+            self._set_media_status(_("Roll: none loaded"), "warn")
         elif self.media_label is None:
-            self._set_media_status(f"Rolle: {self.media.describe()} – kein passendes Etikett", "warn")
+            self._set_media_status(_("Roll: {media} – no matching label").format(
+                media=self.media.describe()), "warn")
         elif self.media_label == self.doc.label_id:
-            hint = " – Etikett angepasst" if self.media_adjusted else ""
-            self._set_media_status(f"Rolle: {self.media.describe()} ✓{hint}", "ok")
+            text = _("Roll: {media} ✓ – label adjusted") if self.media_adjusted else _("Roll: {media} ✓")
+            self._set_media_status(text.format(media=self.media.describe()), "ok")
         else:
-            self._set_media_status(f"Rolle: {self.media.describe()} – Auswahl passt nicht", "warn")
+            self._set_media_status(_("Roll: {media} – selection does not match").format(
+                media=self.media.describe()), "warn")
 
     def _set_media_status(self, text: str, state: str) -> None:
         self.media_status_changed.emit(text, state)
@@ -290,8 +294,8 @@ class PaperPanel(Panel):
         self.fixed_size.setVisible(not endless)
         w, h = label.size_mm
         w, h = mm_text(w), mm_text(h)
-        self.fixed_size.setText(f"Ø {w} mm · rund" if label.shape == "round"
-                                else f"{w} × {h} mm · gestanzt")
+        self.fixed_size.setText(_("Ø {width} mm · round").format(width=w) if label.shape == "round"
+                                else _("{width} × {height} mm · die-cut").format(width=w, height=h))
         self._update_frame_widgets()
 
     def _update_frame_widgets(self) -> None:
@@ -299,7 +303,7 @@ class PaperPanel(Panel):
         round_label = get_label(self.doc.label_id).shape == "round"
         corners = self.frame_style.findData("corners")
         self.frame_style.model().item(corners).setEnabled(not round_label)
-        self.frame_style.setToolTip(ROUND_TIP if round_label else "")
+        self.frame_style.setToolTip(_(ROUND_TIP) if round_label else "")
         active = self.doc.frame is not None
         self.frame_rounded.setEnabled(active and not round_label)
         for box in self._frame_boxes():
diff --git a/src/labelwerk/gui/panels/position.py b/src/labelwerk/gui/panels/position.py
index d922024..1016925 100644
--- a/src/labelwerk/gui/panels/position.py
+++ b/src/labelwerk/gui/panels/position.py
@@ -9,16 +9,17 @@ from PySide6.QtCore import Signal
 from PySide6.QtWidgets import QGridLayout, QLabel, QWidget
 
 from ...document import MAX_POSITION_MM
+from ...i18n import N_, _
 from ...layout import Rect
 from ..widgets import DoubleSpinBox
 
 POSITION_MM = (-MAX_POSITION_MM, MAX_POSITION_MM)   # Lage darf auch neben dem Etikett liegen (ragt hinaus)
 SIZE_MM = (1.0, 999.9)
-FRAME_ONLY = "Nur mit fester Rahmengröße änderbar"
-_FIELDS = (("x", "X", "Abstand vom linken Etikettrand"),
-           ("y", "Y", "Abstand vom oberen Etikettrand"),
-           ("w", "B", "Breite des Rahmens"),
-           ("h", "H", "Höhe des Rahmens"))
+FRAME_ONLY = N_("Only changeable with a fixed frame size")
+_FIELDS = (("x", "X", N_("Distance from the left edge of the label")),
+           ("y", "Y", N_("Distance from the top edge of the label")),
+           ("w", N_("W"), N_("Width of the frame")),         # B(reite)
+           ("h", N_("H"), N_("Height of the frame")))
 
 
 class PositionSection(QWidget):
@@ -33,7 +34,7 @@ class PositionSection(QWidget):
     def __init__(self, parent=None):
         super().__init__(parent)
         self._size_editable = True
-        self.spins = {key: DoubleSpinBox() for key, _, _ in _FIELDS}   # x, y, w, h
+        self.spins = {key: DoubleSpinBox() for key, __, ___ in _FIELDS}   # x, y, w, h
         grid = QGridLayout(self)
         grid.setContentsMargins(0, 0, 0, 0)
         for i, (key, text, tip) in enumerate(_FIELDS):
@@ -42,9 +43,9 @@ class PositionSection(QWidget):
             spin.setSingleStep(0.1)
             spin.setRange(*(POSITION_MM if key in "xy" else SIZE_MM))
             spin.setKeyboardTracking(False)        # erst nach Enter/Fokuswechsel/Pfeil übernehmen
-            spin.setToolTip(tip)
-            label = QLabel(text)
-            label.setToolTip(tip)
+            spin.setToolTip(_(tip))
+            label = QLabel(text if key in "xy" else _(text))
+            label.setToolTip(_(tip))
             grid.addWidget(label, i // 2, (i % 2) * 2)
             grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)
             spin.valueChanged.connect(lambda value, k=key: self._changed(k, value))
@@ -63,12 +64,13 @@ class PositionSection(QWidget):
     def set_size_editable(self, editable: bool) -> None:
         """Breite/Höhe änderbar bzw. nur Anzeige der Größe."""
         self._size_editable = editable
-        for spin, name in ((self.spins["w"], "Breite"), (self.spins["h"], "Höhe")):
+        for spin, tip in ((self.spins["w"], _("Width of the frame")),
+                          (self.spins["h"], _("Height of the frame"))):
             if spin.isReadOnly() == editable:
                 spin.setReadOnly(not editable)       # Pfeile bleiben sichtbar, wirken aber nicht
                 spin.style().unpolish(spin)          # Stylesheet: [readOnly="true"] neu anwenden
                 spin.style().polish(spin)
-            spin.setToolTip(f"{name} des Rahmens" + ("" if editable else f" – {FRAME_ONLY}"))
+            spin.setToolTip(tip if editable else f"{tip} – {_(FRAME_ONLY)}")
 
     def _changed(self, key: str, value: float) -> None:
         if key in "wh" and not self._size_editable:
diff --git a/src/labelwerk/gui/panels/series.py b/src/labelwerk/gui/panels/series.py
index e24208d..af06afa 100644
--- a/src/labelwerk/gui/panels/series.py
+++ b/src/labelwerk/gui/panels/series.py
@@ -18,15 +18,16 @@ from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QHeaderView,
 
 from ... import series
 from ...document import CUTS, MAX_DIGITS, MAX_NUMBER, MAX_SERIES_ROWS, Document, Numbering, Series
+from ...i18n import N_, _, ngettext
 from ...series import SeriesError, Table
 from ..widgets import SpinBox
 from . import Panel
 
-NO_SERIES = "Keine Serie"
-NUMBERING = "Nummerierung"
-CUT_TITLES = {"each": "Nach jedem Etikett", "end": "Nur am Ende"}
-NO_CUTTER = "Drucker ohne Abschneider – Etiketten von Hand abtrennen"
-DRIVER_CUTS = "Schneiden stellt der Druckertreiber ein (Druckerverwaltung des Systems)"
+NO_SERIES = N_("No series")
+NUMBERING = N_("Numbering")
+CUT_TITLES = {"each": N_("After each label"), "end": N_("Only at the end")}
+NO_CUTTER = N_("Printer without cutter – separate the labels by hand")
+DRIVER_CUTS = N_("Cutting is set by the printer driver (system printer settings)")
 SHOWN_COLUMNS = 3                   # Spalten in der Zeilentabelle (die Häkchen sitzen in der ersten)
 ROWS_HEIGHT = 180
 
@@ -37,7 +38,7 @@ class SeriesPanel(Panel):
     driver_cut_chosen = Signal(str, str)   # CUPS: Treiber-Option zum Schneiden, gewählter Wert
 
     def __init__(self, doc: Document):
-        super().__init__(doc, "Serie")
+        super().__init__(doc, _("Series"))
         self.table: Table | None = None
         self.error: str | None = None        # Tabelle nicht lesbar
         self._field_error: str | None = None  # Nummerierungsfeld ungültig (nicht übernommen)
@@ -46,47 +47,50 @@ class SeriesPanel(Panel):
         self._stamp = None                    # Änderungszeit der Datei beim Lesen
         self._current = 0                     # Vorschau-Zeile
 
-        self.section("Quelle")
-        self.table_button = QPushButton("TABELLE …")
-        self.table_button.setToolTip("CSV- oder Excel-Datei (.xlsx) – erste Zeile = Spaltennamen")
-        self.numbering_button = QPushButton("NUMMERIERUNG")
-        self.numbering_button.setToolTip("Zahlen ohne Datei: Spalte „Nummer“")
+        self.section(_("Source"))
+        self.table_button = QPushButton(_("TABLE …"))
+        self.table_button.setToolTip(_("CSV or Excel file (.xlsx) – first row = column names"))
+        self.numbering_button = QPushButton(_("NUMBERING"))
+        self.numbering_button.setToolTip(_("Numbers without a file: column “{column}”").format(
+            column=series.number_column()))
         for button in (self.table_button, self.numbering_button):   # volle Breite: lange Texte
             self.layout_.addWidget(button)
-        self.source_label = QLabel(NO_SERIES)
+        self.source_label = QLabel(_(NO_SERIES))
         self.source_label.setWordWrap(True)
         self.layout_.addWidget(self.source_label)
         self.sheet = QComboBox()
-        self.sheet.setToolTip("Blatt der Excel-Datei")
+        self.sheet.setToolTip(_("Sheet of the Excel file"))
         self.layout_.addWidget(self.sheet)
         self.numbering_box = QWidget()
         grid = QGridLayout(self.numbering_box)
         grid.setContentsMargins(0, 0, 0, 0)
         grid.setColumnStretch(1, 1)
-        self.start = self._spin(-MAX_NUMBER, MAX_NUMBER, "Erste Zahl")
-        self.step = self._spin(-MAX_NUMBER, MAX_NUMBER, "Abstand zur nächsten Zahl (nicht 0)")
-        self.count = self._spin(1, MAX_SERIES_ROWS, "Wie viele Etiketten")
-        self.digits = self._spin(0, MAX_DIGITS, "Mit Nullen auf so viele Stellen auffüllen (0 = nicht)")
-        for line, (title, box) in enumerate((("Start", self.start), ("Schritt", self.step),
-                                             ("Anzahl", self.count), ("Stellen", self.digits))):
+        self.start = self._spin(-MAX_NUMBER, MAX_NUMBER, _("First number"))
+        self.step = self._spin(-MAX_NUMBER, MAX_NUMBER, _("Step to the next number (not 0)"))
+        self.count = self._spin(1, MAX_SERIES_ROWS, _("How many labels"))
+        self.digits = self._spin(0, MAX_DIGITS,
+                                 _("Pad with zeros to this many digits (0 = no padding)"))
+        for line, (title, box) in enumerate(((_("Start"), self.start), (_("Step"), self.step),
+                                             (_("Count"), self.count), (_("Digits"), self.digits))):
             grid.addWidget(QLabel(title), line, 0)
             grid.addWidget(box, line, 1)
         self.layout_.addWidget(self.numbering_box)
-        self.remove_button = QPushButton("ENTFERNEN")
-        self.remove_button.setToolTip("Serie aus dem Etikett nehmen (Platzhalter bleiben stehen)")
+        self.remove_button = QPushButton(_("REMOVE"))
+        self.remove_button.setToolTip(_("Remove the series from the label (placeholders stay)"))
         self.layout_.addWidget(self.remove_button)
         self.error_label = QLabel()
         self.error_label.setObjectName("hint")
         self.error_label.setWordWrap(True)
         self.layout_.addWidget(self.error_label)
 
-        self.section("Spalten")
+        self.section(_("Columns"))
         self.columns = QListWidget()
-        self.columns.setToolTip("Doppelklick: als {Spalte} ins gewählte Textobjekt bzw. als neuer Text")
+        self.columns.setToolTip(_("Double-click: as {{column}} into the selected text object or as new "
+                                   "text").format())
         self.columns.setFixedHeight(90)
         self.layout_.addWidget(self.columns)
 
-        self.section("Zeilen")
+        self.section(_("Rows"))
         self.rows = QTableWidget(0, 0)
         self.rows.setFixedHeight(ROWS_HEIGHT)
         self.rows.verticalHeader().setVisible(False)
@@ -98,38 +102,38 @@ class SeriesPanel(Panel):
         self.rows.setTextElideMode(Qt.TextElideMode.ElideRight)
         self.layout_.addWidget(self.rows)
         row = QHBoxLayout()
-        self.all_button = QPushButton("ALLE")
-        self.none_button = QPushButton("KEINE")
+        self.all_button = QPushButton(_("ALL"))
+        self.none_button = QPushButton(_("NONE"))
         row.addWidget(self.all_button)
         row.addWidget(self.none_button)
         self.layout_.addLayout(row)
         self.count_label = QLabel()
         self.layout_.addWidget(self.count_label)
 
-        self.section("Vorschau")
+        self.section(_("Preview"))
         row = QHBoxLayout()
         self.prev_button = QToolButton()
         self.prev_button.setText("◀")
-        self.prev_button.setToolTip("Vorige Zeile auf der Arbeitsfläche")
+        self.prev_button.setToolTip(_("Previous row on the canvas"))
         self.row_label = QLabel()
         self.row_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
         self.next_button = QToolButton()
         self.next_button.setText("▶")
-        self.next_button.setToolTip("Nächste Zeile auf der Arbeitsfläche")
+        self.next_button.setToolTip(_("Next row on the canvas"))
         row.addWidget(self.prev_button)
         row.addWidget(self.row_label, 1)
         row.addWidget(self.next_button)
         self.layout_.addLayout(row)
 
-        self.cut_title = self.section("Schnitt")
+        self.cut_title = self.section(_("Cutting"))
         self.cut = QComboBox()
         for mode in CUTS:
-            self.cut.addItem(CUT_TITLES[mode], mode)
-        self.cut.setToolTip("Beim Drucken der Serie: nach jedem Etikett schneiden oder nur am Ende "
-                            "(Endlosband: zwischen den Etiketten bleiben einige mm Vorschub, "
-                            "ohne Trennmarke)")
+            self.cut.addItem(_(CUT_TITLES[mode]), mode)
+        self.cut.setToolTip(_("When printing the series: cut after each label or only at the end "
+                              "(continuous tape: a few mm of feed remain between the labels, "
+                              "without a separator mark)"))
         self.layout_.addWidget(self.cut)
-        self.no_cutter = QLabel(NO_CUTTER)
+        self.no_cutter = QLabel(_(NO_CUTTER))
         self.no_cutter.setObjectName("hint")
         self.no_cutter.setWordWrap(True)
         self.no_cutter.hide()
@@ -153,7 +157,7 @@ class SeriesPanel(Panel):
         # Doppelklick bzw. Enter (je nach Stil auch Einfachklick) – nur dieses Signal, sonst doppelt
         self.columns.itemActivated.connect(lambda item: self.insert_column.emit(item.text()))
         self.rows.itemChanged.connect(lambda _item: self._update_count())
-        self.rows.currentCellChanged.connect(lambda row, *_: self._go_to(row))
+        self.rows.currentCellChanged.connect(lambda row, *_args: self._go_to(row))
         self.all_button.clicked.connect(lambda: self._check_all(True))
         self.none_button.clicked.connect(lambda: self._check_all(False))
         self.prev_button.clicked.connect(lambda: self._go_to(self._current - 1))
@@ -183,10 +187,10 @@ class SeriesPanel(Panel):
             self._key = key
             self._load(value)
         if value is None:
-            self.source_label.setText(NO_SERIES)
+            self.source_label.setText(_(NO_SERIES))
             self.source_label.setToolTip("")
         elif value.numbering is not None:
-            self.source_label.setText(NUMBERING)
+            self.source_label.setText(_(NUMBERING))
             self.source_label.setToolTip("")
             n = value.numbering
             for box, v in ((self.start, n.start), (self.step, n.step), (self.count, n.count),
@@ -299,7 +303,8 @@ class SeriesPanel(Panel):
         if self.doc.series is not None and self._field_error:
             lines.append(self._field_error)
         if self.doc.series is not None and self.table is not None and self._missing:
-            lines.append("Unbekannte Spalte: " + ", ".join(self._missing))
+            lines.append(ngettext("Unknown column: {columns}", "Unknown columns: {columns}",
+                                  len(self._missing)).format(columns=", ".join(self._missing)))
         self.error_label.setText("\n".join(lines))
         self.error_label.setVisible(bool(lines))
 
@@ -344,7 +349,7 @@ class SeriesPanel(Panel):
         """Drucker mit bzw. ohne Abschneider: ohne gibt es keine Schnitt-Auswahl, nur den Hinweis."""
         self.cut_title.setVisible(cutter)
         self.cut.setVisible(cutter)
-        self.no_cutter.setText(NO_CUTTER)
+        self.no_cutter.setText(_(NO_CUTTER))
         self.no_cutter.setVisible(not cutter)
         self.driver_box.hide()
 
@@ -358,10 +363,10 @@ class SeriesPanel(Panel):
         for row, option in enumerate(options):
             combo = QComboBox()
             for choice, text in zip(option.choices, option.labels or option.choices):
-                combo.addItem(text, choice)
+                combo.addItem(text, choice)          # Treibertexte bleiben, Zebra schon übersetzt
             combo.setCurrentIndex(max(0, combo.findData(chosen.get(option.key, option.default))))
             combo.currentIndexChanged.connect(
-                lambda _=0, key=option.key, box=combo: self.driver_cut_chosen.emit(
+                lambda _unused=0, key=option.key, box=combo: self.driver_cut_chosen.emit(
                     key, box.currentData()))
             self.driver_grid.addWidget(QLabel(option.title), row, 0)
             self.driver_grid.addWidget(combo, row, 1)
@@ -369,7 +374,7 @@ class SeriesPanel(Panel):
         self.cut.hide()
         self.cut_title.setVisible(True)
         self.driver_box.setVisible(bool(options))
-        self.no_cutter.setText(DRIVER_CUTS)
+        self.no_cutter.setText(_(DRIVER_CUTS))
         self.no_cutter.setVisible(not options)
 
     def _apply_cut(self) -> None:
@@ -394,7 +399,8 @@ class SeriesPanel(Panel):
 
     def _update_count(self) -> None:
         total = self.rows.rowCount()
-        self.count_label.setText(f"{len(self.checked_rows())} von {total} gewählt" if total else "")
+        self.count_label.setText(_("{checked} of {total} selected").format(
+            checked=len(self.checked_rows()), total=total) if total else "")
 
     def _update_row_label(self) -> None:
         total = len(self.table.rows) if self.table is not None else 0
@@ -402,7 +408,8 @@ class SeriesPanel(Panel):
             self.rows.blockSignals(True)
             self.rows.setCurrentCell(self._current, 0)
             self.rows.blockSignals(False)
-        self.row_label.setText(f"Zeile {self._current + 1}/{total}" if total else "")
+        self.row_label.setText(_("Row {row}/{total}").format(row=self._current + 1, total=total)
+                                if total else "")
         self.prev_button.setEnabled(self._current > 0)
         self.next_button.setEnabled(self._current < total - 1)
 
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index fc6a647..150c96b 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -21,6 +21,8 @@ from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayo
 
 from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
 from ...fonts import DEFAULT_FAMILY
+from ... import i18n
+from ...i18n import N_, _, pgettext
 from ...layout import Rect
 from ...render import REF_PT
 from ..symbols import line_icon
@@ -31,7 +33,7 @@ _P = QTextFormat.Property
 
 SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
 DEFAULT_PT = 19
-HINT = "Auf das Etikett klicken, um einen Textrahmen anzulegen"
+HINT = N_("Click on the label to create a text frame")
 _ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                 "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}
 
@@ -89,7 +91,7 @@ class TextPanel(Panel):
             button.setIcon(_align_icon(key, dark_checked))
 
     def __init__(self, doc: Document):
-        super().__init__(doc, "Text")
+        super().__init__(doc, _("Text"))
         self.dark_checked_icons = True
         self.index: int | None = None   # bearbeitetes Objekt; None = kein Text ausgewählt
         self._editing = False           # Schreibmodus (``set_editing``)
@@ -101,7 +103,7 @@ class TextPanel(Panel):
         self._base = {"family": DEFAULT_FAMILY, "pt": float(DEFAULT_PT), "bold": True,
                       "italic": False, "underline": False}
 
-        self.hint = QLabel(HINT)
+        self.hint = QLabel(_(HINT))
         self.hint.setObjectName("hint")
         self.hint.setWordWrap(True)
         self.layout_.addWidget(self.hint)
@@ -117,7 +119,7 @@ class TextPanel(Panel):
         option.setWrapMode(QTextOption.WrapMode.NoWrap)
         self.edit.document().setDefaultTextOption(option)
 
-        self.section("Schrift")
+        self.section(pgettext("text panel", "Font"))
         self.family = QFontComboBox()
         self.layout_.addWidget(self.family)
         row = QHBoxLayout()
@@ -125,19 +127,19 @@ class TextPanel(Panel):
         self.size.setEditable(True)
         self.size.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)   # Eingaben nicht an die Liste anhängen
         self.size.addItems([str(s) for s in SIZES_PT])
-        self.size.setToolTip("Schriftgröße in pt")
-        self.grow = _button("A⁺", "Schrift größer", checkable=False)
-        self.shrink = _button("A⁻", "Schrift kleiner", checkable=False)
+        self.size.setToolTip(_("Font size in pt"))
+        self.grow = _button("A⁺", _("Larger font"), checkable=False)
+        self.shrink = _button("A⁻", _("Smaller font"), checkable=False)
         row.addWidget(self.size, 1)
         row.addWidget(self.grow)
         row.addWidget(self.shrink)
         self.layout_.addLayout(row)
 
-        self.section("Stil")
+        self.section(_("Style"))
         row = QHBoxLayout()
-        self.bold = _button("B", "Fett")            # Tooltip mit Kürzel: use_actions
-        self.italic = _button("I", "Kursiv")
-        self.underline = _button("U", "Unterstrichen")
+        self.bold = _button("B", _("Bold"))            # Tooltip mit Kürzel: use_actions
+        self.italic = _button("I", _("Italic"))
+        self.underline = _button("U", _("Underline"))
         for button, attr in ((self.bold, "bold"), (self.italic, "italic"),
                              (self.underline, "underline")):
             button.setProperty("style", attr)
@@ -147,12 +149,12 @@ class TextPanel(Panel):
             row.addWidget(button)
         self.layout_.addLayout(row)
 
-        self.section("Textposition")
+        self.section(_("Text alignment"))
         row = QHBoxLayout()
         self.align_group = QButtonGroup(self)
         self.align_buttons = {}
-        for key, tip in (("left", "Linksbündig"), ("center", "Zentriert"),
-                         ("right", "Rechtsbündig"), ("justify", "Blocksatz")):
+        for key, tip in (("left", _("Align left")), ("center", _("Centered")),
+                         ("right", _("Align right")), ("justify", _("Justified"))):
             button = _button("", tip)
             button.setIcon(_align_icon(key))
             button.setIconSize(QSize(16, 16))
@@ -162,10 +164,10 @@ class TextPanel(Panel):
             row.addWidget(button)
         self.layout_.addLayout(row)
 
-        self.fit = _button("FESTE RAHMENGRÖSSE", "Text automatisch so skalieren, dass er passt")
+        self.fit = _button(_("FIXED FRAME SIZE"), _("Scale the text automatically so that it fits"))
         self.layout_.addWidget(self.fit)
 
-        self.section("Position (mm)")
+        self.section(_("Position (mm)"))
         self.position = PositionSection()
         self.pos_x, self.pos_y, self.pos_w, self.pos_h = (self.position.spins[k] for k in "xywh")
         self.position.edited.connect(self._frame_changed)
@@ -186,7 +188,7 @@ class TextPanel(Panel):
         step = self._step     # Knöpfe und Felder: jede Änderung ein eigener Schritt
         self.family.currentFontChanged.connect(
             lambda font: step(self._format, family=font.family()))
-        self.size.activated.connect(lambda _: step(self._size_entered))
+        self.size.activated.connect(lambda _index: step(self._size_entered))
         self.size.lineEdit().editingFinished.connect(lambda: step(self._size_entered))
         self.grow.clicked.connect(lambda: step(self._step_size, +1))
         self.shrink.clicked.connect(lambda: step(self._step_size, -1))
@@ -194,8 +196,8 @@ class TextPanel(Panel):
         self.italic.clicked.connect(lambda on: step(self._format, italic=on))
         self.underline.clicked.connect(lambda on: step(self._format, underline=on))
         for key, button in self.align_buttons.items():
-            button.clicked.connect(lambda _=False, k=key: step(self._align, k))
-        self.fit.toggled.connect(lambda _: step(self._apply))
+            button.clicked.connect(lambda _checked=False, k=key: step(self._align, k))
+        self.fit.toggled.connect(lambda _checked: step(self._apply))
 
     def use_actions(self, actions: dict[str, QAction]) -> None:
         """Kürzel für Fett/Kursiv/Unterstrichen: wirken, solange das Panel den Fokus hat.
@@ -203,7 +205,7 @@ class TextPanel(Panel):
         for key, button in (("text.bold", self.bold), ("text.italic", self.italic),
                             ("text.underline", self.underline)):
             action = actions[key]
-            action.triggered.connect(lambda _=False, b=button: b.click())
+            action.triggered.connect(lambda _checked=False, b=button: b.click())
             self.addAction(action)
             button.setToolTip(action.toolTip())
             action.changed.connect(lambda b=button, a=action: b.setToolTip(a.toolTip()))
@@ -554,7 +556,7 @@ class TextPanel(Panel):
         for w in widgets:
             w.blockSignals(True)
         self.family.setCurrentFont(QFont(props["family"]))
-        self.size.setEditText("" if len(mixed) > 1 else f"{props['pt']:g}")
+        self.size.setEditText("" if len(mixed) > 1 else i18n.number(props["pt"]))
         self.bold.setChecked(props["bold"])
         self.italic.setChecked(props["italic"])
         self.underline.setChecked(props["underline"])
diff --git a/src/labelwerk/gui/print_worker.py b/src/labelwerk/gui/print_worker.py
index e877543..7dcd1a3 100644
--- a/src/labelwerk/gui/print_worker.py
+++ b/src/labelwerk/gui/print_worker.py
@@ -6,6 +6,7 @@ import threading
 from PIL import Image
 from PySide6.QtCore import QObject, QRunnable, Signal
 
+from ..i18n import _
 from ..detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp
 from ..printer import PrintCancelled, PrintError, print_image
 
@@ -40,7 +41,7 @@ class PrintWorker(QRunnable):
         try:
             printer = self.printer or find_brother_lp()
             if printer is None:
-                self.signals.failed.emit(BUSY_MESSAGE if brother_busy() else PRINTER_NOT_FOUND)
+                self.signals.failed.emit(_(BUSY_MESSAGE) if brother_busy() else _(PRINTER_NOT_FOUND))
                 return
             status = print_image(self.image, self.label_id, model=self.model, printer=printer,
                                  cut_every=self.cut_every, cancelled=self._cancel.is_set,
@@ -52,6 +53,6 @@ class PrintWorker(QRunnable):
             self.signals.failed.emit(str(e))
             return
         except Exception as e:  # kein Absturz des Threads; Meldung statt Traceback
-            self.signals.failed.emit(f"Unerwarteter Fehler beim Drucken: {e}")
+            self.signals.failed.emit(_("Unexpected error while printing: {error}").format(error=e))
             return
         self.signals.done.emit(status)
diff --git a/src/labelwerk/gui/screenshot.py b/src/labelwerk/gui/screenshot.py
index db776a2..0629c2d 100644
--- a/src/labelwerk/gui/screenshot.py
+++ b/src/labelwerk/gui/screenshot.py
@@ -15,13 +15,15 @@ from urllib.parse import unquote, urlparse
 from PySide6.QtCore import SLOT, QObject, Signal, Slot
 from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage
 
+from ..i18n import N_, _
+
 SERVICE = "org.freedesktop.portal.Desktop"
 OBJECT = "/org/freedesktop/portal/desktop"
 INTERFACE = "org.freedesktop.portal.Screenshot"
 REQUEST = "org.freedesktop.portal.Request"
 AVAILABLE_TIMEOUT_MS = 5_000      # Portal da? (startet es erst, dauert das meist < 1 s)
 CALL_TIMEOUT_MS = 10_000          # Antwort auf den Aufruf selbst (die Auswahl dauert beliebig)
-FAILED = "Bildschirmfoto fehlgeschlagen"
+FAILED = N_("Screenshot failed")
 _RESPONSE_SLOT = SLOT("response(uint,QVariantMap)")
 _NO_PORTAL = ("ServiceUnknown", "NameHasNoOwner", "UnknownObject", "UnknownInterface",
               "UnknownMethod", "ServiceNotFound")
@@ -44,10 +46,10 @@ def parse_response(code: int, results: dict) -> tuple[Path | None, str | None]:
     if code == 1:
         return None, None
     if code != 0:
-        return None, f"{FAILED} – vom System abgelehnt oder abgebrochen"
+        return None, _("Screenshot failed – rejected or cancelled by the system")
     uri = urlparse(str(results.get("uri") or ""))
     if uri.scheme != "file" or not uri.path:
-        return None, f"{FAILED} – keine Bilddatei erhalten"
+        return None, _("Screenshot failed – no image file received")
     return Path(unquote(uri.path)), None
 
 
@@ -56,12 +58,12 @@ def error_text(error_name: str) -> str:
     (die Fehlertexte von D-Bus sind englisch)."""
     short = error_name.rsplit(".", 1)[-1]
     if short in _NO_PORTAL:
-        return f"{FAILED} – kein Bildschirmfoto-Portal gefunden"
+        return _("Screenshot failed – no screenshot portal found")
     if short in _NO_ANSWER:
-        return f"{FAILED} – das Portal antwortet nicht"
+        return _("Screenshot failed – the portal does not answer")
     if short == "NotAllowed":
-        return f"{FAILED} – vom System nicht erlaubt"
-    return f"{FAILED} – Fehler des Portals"
+        return _("Screenshot failed – not allowed by the system")
+    return _("Screenshot failed – error of the portal")
 
 
 class _Request(QObject):
@@ -120,7 +122,7 @@ class ScreenshotPortal(QObject):
         self._spent.clear()
         bus = self.bus()
         if not bus.isConnected():
-            self.finished.emit(None, f"{FAILED} – keine Verbindung zum Sitzungsbus")
+            self.finished.emit(None, _("Screenshot failed – no connection to the session bus"))
             return
         token = f"labelwerk_{uuid.uuid4().hex}"
         self._request = _Request(self)
@@ -134,7 +136,7 @@ class ScreenshotPortal(QObject):
         try:
             handle = reply.arguments()[0].path()
         except (IndexError, AttributeError):
-            self._finish(None, f"{FAILED} – unerwartete Antwort des Portals")
+            self._finish(None, _("Screenshot failed – unexpected answer from the portal"))
             return
         if handle != self._path and not self._subscribe(handle):   # ältere Portale: eigener Pfad
             self._close(handle)                  # ohne Abo kommt keine Antwort: Auswahl schließen
@@ -149,7 +151,7 @@ class ScreenshotPortal(QObject):
         self._unsubscribe()
         if not self.bus().connect(SERVICE, path, REQUEST, "Response", self._request,
                                   _RESPONSE_SLOT):
-            self._finish(None, f"{FAILED} – Antwort des Portals nicht abonnierbar")
+            self._finish(None, _("Screenshot failed – cannot subscribe to the answer of the portal"))
             return False
         self._path = path
         return True
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 683a775..d238cbd 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -16,16 +16,19 @@ from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                                QTabWidget,
                                QVBoxLayout, QWidget)
 
-from .. import favorites, shortcuts, zpl
+from .. import favorites, i18n, shortcuts, zpl
 from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
+from ..i18n import N_, _
 from ..labels import get_label, labels_for_model
 from ..printer import DEFAULT_MODEL
 from ..printers import SUPPORTED_MODELS, capabilities
-from ..settings import Settings, save_settings, valid_host
+from ..settings import (Settings, restart_pending, save_settings, started_values,
+                        valid_host)
 from .widgets import DoubleSpinBox, SpinBox
 
-SCOPE_NAMES = {"global": "Global", "canvas": "Arbeitsfläche", "edit": "Schreibmodus"}
-FIXED_TIP = "Kürzel fest – nicht änderbar"
+# englisch (N_), angezeigt wird _(…)
+SCOPE_NAMES = {"global": N_("Global"), "canvas": N_("Canvas"), "edit": N_("Text editing")}
+FIXED_TIP = N_("Fixed shortcut – cannot be changed")
 CONFLICT_COLOR = QColor("#FF0000")
 COL_ACTION, COL_SCOPE, COL_KEYS, COL_RESET = range(4)
 DIALOG_SIZE = (760, 680)     # Wunschgröße: Kürzel-Tabelle mit ungekürzten Aktionsnamen
@@ -35,11 +38,15 @@ _PORTABLE = QKeySequence.SequenceFormat.PortableText
 _NATIVE = QKeySequence.SequenceFormat.NativeText
 
 
+RESTART_NOTICE = N_("Changes take effect after a restart")
+RESTART_STYLE = "color: #CC7A00; font-weight: 600;"     # wie Hinweise (QSS „warn“), auch ohne QSS
+
+
 class SettingsDialog(QDialog):
     def __init__(self, settings: Settings, path: str | Path | None = None,
-                 model: str = DEFAULT_MODEL, parent=None):
+                 model: str = DEFAULT_MODEL, parent=None, started: dict | None = None):
         super().__init__(parent)
-        self.setWindowTitle("Einstellungen")
+        self.setWindowTitle(_("Settings"))
         self.setMinimumSize(*MIN_SIZE)
         screen = (parent.screen() if parent is not None else self.screen())
         self.resize(initial_size(screen.availableGeometry().size()))
@@ -57,32 +64,32 @@ class SettingsDialog(QDialog):
         scroll.setWidget(general)
         scroll.setWidgetResizable(True)
         scroll.setFrameShape(QFrame.Shape.NoFrame)
-        self.tabs.addTab(scroll, "Allgemein")
+        self.tabs.addTab(scroll, _("General"))
         layout = QVBoxLayout(general)
 
-        form = self._section(layout, "Neues Etikett")
+        form = self._section(layout, _("New label"))
         self.label = QComboBox()
         for lbl in labels_for_model(model):
             self.label.addItem(lbl.description, lbl.id)
         if self.label.findData(settings.label_id) < 0:    # anderer Drucker: nicht still ersetzen
-            self.label.addItem(f"{get_label(settings.label_id).description} – passt nicht zum "
-                               f"{model}", settings.label_id)
+            self.label.addItem(_("{label} – does not fit the {model}").format(
+                label=get_label(settings.label_id).description, model=model), settings.label_id)
         self.label.setCurrentIndex(max(0, self.label.findData(settings.label_id)))
-        form.addRow("Etikett", self.label)
+        form.addRow(_("Label"), self.label)
         self.orientation = QComboBox()
-        self.orientation.addItem("Horizontal", "horizontal")
-        self.orientation.addItem("Vertikal", "vertical")
+        self.orientation.addItem(_("Horizontal"), "horizontal")
+        self.orientation.addItem(_("Vertical"), "vertical")
         self.orientation.setCurrentIndex(self.orientation.findData(settings.orientation))
-        form.addRow("Ausrichtung", self.orientation)
+        form.addRow(_("Orientation"), self.orientation)
         self.margin = DoubleSpinBox()
         self.margin.setSuffix(" mm")
         self.margin.setDecimals(1)
         self.margin.setSingleStep(0.5)
         self.margin.setRange(0.0, MAX_MARGIN_MM)
         self.margin.setValue(settings.margin_mm)
-        form.addRow("Ränder", self.margin)
+        form.addRow(_("Margins"), self.margin)
         row = QHBoxLayout()
-        self.font_auto = QCheckBox("Automatisch")
+        self.font_auto = QCheckBox(_("Automatic"))
         self.font_size = DoubleSpinBox()
         self.font_size.setDecimals(1)
         self.font_size.setSingleStep(0.5)
@@ -94,62 +101,63 @@ class SettingsDialog(QDialog):
         self.font_auto.toggled.connect(lambda auto: self.font_size.setEnabled(not auto))
         row.addWidget(self.font_auto)
         row.addWidget(self.font_size)
-        form.addRow("Schriftgröße", row)
+        form.addRow(_("Font size"), row)
         self.font_family = QFontComboBox()
         self.font_family.setCurrentFont(QFont(settings.font_family))
         # Nicht installierte Schrift nicht stillschweigend durch Ersatz überschreiben
         self._orig_family = settings.font_family
         self._family_touched = False
         self.font_family.currentFontChanged.connect(self._family_changed)
-        form.addRow("Schriftart", self.font_family)
+        form.addRow(_("Font"), self.font_family)
         self.start_favorite = QComboBox()
-        self.start_favorite.addItem("Leeres Etikett", None)
+        self.start_favorite.addItem(_("Empty label"), None)
         for favorite in favorites.favorites():
             self.start_favorite.addItem(favorite.name, favorite.name)
         if settings.start_favorite and self.start_favorite.findData(settings.start_favorite) < 0:
             # gelöscht oder umbenannt: sichtbar lassen, nicht still auf „leer“ setzen
-            self.start_favorite.addItem(f"{settings.start_favorite} (fehlt)", settings.start_favorite)
+            self.start_favorite.addItem(_("{name} (missing)").format(name=settings.start_favorite),
+                                        settings.start_favorite)
         self.start_favorite.setCurrentIndex(max(0, self.start_favorite.findData(settings.start_favorite)))
-        self.start_favorite.setToolTip("Etikett, mit dem labelwerk startet (Favorit als Vorlage)")
-        form.addRow("Beim Start", self.start_favorite)
+        self.start_favorite.setToolTip(_("Label labelwerk starts with (favorite as a template)"))
+        form.addRow(_("At startup"), self.start_favorite)
 
-        form = self._section(layout, "Bilder einfügen")
-        self.image_crop = QCheckBox("Automatisch zuschneiden (ohne Schnittmarken und Leerraum)")
+        form = self._section(layout, _("Inserting images"))
+        self.image_crop = QCheckBox(_("Crop automatically (without crop marks and blank space)"))
         self.image_crop.setChecked(settings.image_crop)
         form.addRow(self.image_crop)
-        self.image_rotate = QCheckBox("Drehen, wenn das Bild nur gedreht 1:1 passt")
-        self.image_rotate.setToolTip("Aus: zu große Bilder werden verkleinert – spart Band")
+        self.image_rotate = QCheckBox(_("Rotate if the image only fits 1:1 when rotated"))
+        self.image_rotate.setToolTip(_("Off: images that are too large are reduced – saves tape"))
         self.image_rotate.setChecked(settings.image_rotate)
         form.addRow(self.image_rotate)
 
-        form = self._section(layout, "Drucker")
-        self.check_media = QCheckBox("Rolle beim Start und beim Einschalten prüfen")
+        form = self._section(layout, _("Printer"))
+        self.check_media = QCheckBox(_("Check the roll at startup and when the printer is switched on"))
         self.check_media.setChecked(settings.check_media_on_start)
         form.addRow(self.check_media)
-        self.printer_model = _model_combo("Automatisch (erkannt)")
+        self.printer_model = _model_combo(_("Automatic (detected)"))
         self.printer_model.setCurrentIndex(max(0, self.printer_model.findData(settings.printer_model)))
-        self.printer_model.setToolTip("Nur nötig, wenn labelwerk das Modell nicht erkennt "
-                                      "(gilt dann und ohne angeschlossenen Drucker)")
-        form.addRow("Druckermodell", self.printer_model)
+        self.printer_model.setToolTip(_("Only needed if labelwerk does not recognize the model "
+                                        "(then applies, and without a connected printer)"))
+        form.addRow(_("Printer model"), self.printer_model)
         self.zebra_dpi = QComboBox()
-        self.zebra_dpi.addItem("Automatisch (erkannt)", 0)
+        self.zebra_dpi.addItem(_("Automatic (detected)"), 0)
         for dpi in zpl.RESOLUTIONS:
             self.zebra_dpi.addItem(f"{dpi} dpi", dpi)
         self.zebra_dpi.setCurrentIndex(max(0, self.zebra_dpi.findData(settings.zebra_dpi)))
-        self.zebra_dpi.setToolTip("Auflösung der Zebra-Drucker am USB, falls labelwerk sie nicht "
-                                  "richtig erkennt (sonst 203 dpi)")
-        form.addRow("Zebra-Auflösung", self.zebra_dpi)
+        self.zebra_dpi.setToolTip(_("Resolution of Zebra printers on USB, in case labelwerk does "
+                                    "not detect it correctly (otherwise 203 dpi)"))
+        form.addRow(_("Zebra resolution"), self.zebra_dpi)
         self.network = QTableWidget(0, 3)
-        self.network.setHorizontalHeaderLabels(["Name", "Adresse", "Modell"])
+        self.network.setHorizontalHeaderLabels([_("Name"), _("Address"), _("Model")])
         self.network.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
         self.network.verticalHeader().hide()
         self.network.setMinimumHeight(110)
         for entry in settings.network_printers:
             self._add_network(entry["name"], entry["host"], entry["model"])
         buttons = QHBoxLayout()
-        self.add_network = QPushButton("HINZUFÜGEN")
+        self.add_network = QPushButton(_("ADD"))
         self.add_network.clicked.connect(lambda: self._add_network("", "", "QL-720NW"))
-        self.remove_network = QPushButton("ENTFERNEN")
+        self.remove_network = QPushButton(_("REMOVE"))
         self.remove_network.clicked.connect(
             lambda: self.network.removeRow(self.network.currentRow())
             if self.network.currentRow() >= 0 else None)
@@ -159,23 +167,41 @@ class SettingsDialog(QDialog):
         box = QVBoxLayout()
         box.addWidget(self.network)
         box.addLayout(buttons)
-        form.addRow("Netzwerkdrucker", box)
+        form.addRow(_("Network printers"), box)
 
-        form = self._section(layout, "Ansicht")
+        form = self._section(layout, _("View"))
         self.zoom = SpinBox()
         self.zoom.setSuffix(" %")
         self.zoom.setRange(25, 400)
         self.zoom.setSingleStep(10)
         self.zoom.setValue(settings.start_zoom)
-        form.addRow("Startzoom", self.zoom)
+        form.addRow(_("Start zoom"), self.zoom)
         self.theme = QComboBox()
         self.theme.addItem("RawBlock", "rawblock")
-        self.theme.addItem("Klassisch", "classic")
+        self.theme.addItem(_("Classic"), "classic")
         self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
-        form.addRow("Design", self.theme)
-
-        hint = QLabel("„Neues Etikett“ gilt für neue Etiketten, der Startzoom ab dem nächsten "
-                      "Start, alles andere sofort.")
+        form.addRow(_("Theme"), self.theme)
+        self.language = QComboBox()
+        system = i18n.system_language()
+        self.language.addItem(_("Automatic (system language: {language})").format(
+            language=i18n.NAMES.get(system, system)), "")
+        for code in i18n.available():
+            self.language.addItem(i18n.NAMES.get(code, code), code)
+        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
+        form.addRow(_("Language"), self.language)
+        # Einstellungen, die erst nach einem Neustart wirken: farbiger Hinweis neben SPEICHERN
+        # (unten im Fenster – sichtbar in jedem Reiter), sobald eine davon geändert ist
+        self._started = started if started is not None else started_values(settings)
+        self.restart_hint = QLabel(_(RESTART_NOTICE))
+        self.restart_hint.setObjectName("restartNotice")
+        self.restart_hint.setStyleSheet(RESTART_STYLE)
+        self.restart_hint.setWordWrap(True)
+        self.restart_hint.hide()
+        self.language.currentIndexChanged.connect(self._update_restart_hint)
+        self.zoom.valueChanged.connect(self._update_restart_hint)
+
+        hint = QLabel(_("“New label” applies to new labels, start zoom and language from the next "
+                        "start, everything else immediately."))
         hint.setWordWrap(True)
         layout.addWidget(hint)
         layout.addStretch()
@@ -190,7 +216,11 @@ class SettingsDialog(QDialog):
         buttons.accepted.connect(self.accept)
         buttons.rejected.connect(self.reject)
         self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
-        outer.addWidget(buttons)
+        footer = QHBoxLayout()
+        footer.addWidget(self.restart_hint, 1)
+        footer.addWidget(buttons)
+        outer.addLayout(footer)
+        self._update_restart_hint()
         self._check_conflicts()
 
     def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
@@ -210,12 +240,11 @@ class SettingsDialog(QDialog):
     # --- Reiter „Tastenkürzel“ ------------------------------------------------------
     def _build_shortcut_tab(self, overrides: dict[str, str]) -> None:
         page = QWidget()
-        self.tabs.addTab(page, "Tastenkürzel")
+        self.tabs.addTab(page, _("Shortcuts"))
         layout = QVBoxLayout(page)
         hint = self.shortcut_hint = QLabel(
-            "Zeile anklicken und die neue Tastenkombination drücken. Esc bricht ab, "
-            "✕ im Feld entfernt das Kürzel. Esc, Enter und Tab lassen sich hier nicht "
-            "belegen (sie bedienen die Tabelle).")
+            _("Click a row and press the new key combination. Esc cancels, ✕ in the field removes "
+              "the shortcut. Esc, Enter and Tab cannot be assigned here (they operate the table)."))
         hint.setWordWrap(True)
         layout.addWidget(hint)
         self.key_hint = self._error_label()          # verworfene Eingabe
@@ -223,7 +252,7 @@ class SettingsDialog(QDialog):
         self._keys = shortcuts.effective(overrides)       # Aktions-ID → Kürzel (Qt-Format)
         self._rows = [a.id for a in shortcuts.ACTIONS]
         table = self.shortcut_table = QTableWidget(len(self._rows), 4)
-        table.setHorizontalHeaderLabels(["Aktion", "Bereich", "Kürzel", ""])
+        table.setHorizontalHeaderLabels([_("Action"), _("Scope"), _("Shortcut"), ""])
         table.verticalHeader().hide()
         table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
         table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
@@ -235,14 +264,15 @@ class SettingsDialog(QDialog):
             header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
         fixed = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
         for row, entry in enumerate(shortcuts.ACTIONS):
-            for column, text in ((COL_ACTION, entry.name), (COL_SCOPE, SCOPE_NAMES[entry.scope])):
+            for column, text in ((COL_ACTION, _(entry.name)),
+                                 (COL_SCOPE, _(SCOPE_NAMES[entry.scope]))):
                 item = QTableWidgetItem(text)
                 item.setFlags(fixed)
                 table.setItem(row, column, item)
             item = QTableWidgetItem()
             if entry.fixed:
                 item.setFlags(fixed)
-                item.setToolTip(FIXED_TIP)
+                item.setToolTip(_(FIXED_TIP))
             else:
                 item.setFlags(fixed | Qt.ItemFlag.ItemIsEditable)
             table.setItem(row, COL_KEYS, item)
@@ -258,7 +288,7 @@ class SettingsDialog(QDialog):
         table.cellActivated.connect(self._edit_row)
         layout.addWidget(table, 1)
         row = QHBoxLayout()
-        self.reset_all = QPushButton("Alle zurücksetzen")
+        self.reset_all = QPushButton(_("Reset all"))
         self.reset_all.clicked.connect(self._reset_all)
         row.addWidget(self.reset_all)
         row.addStretch()
@@ -277,8 +307,9 @@ class SettingsDialog(QDialog):
 
     def reject_keys(self, action_id: str, seq: str) -> None:
         """Eingabe taugt nicht als Kürzel (z. B. nur Umschalt): melden, Kürzel bleibt."""
-        self.key_hint.setText(f"„{_native(seq) or seq}“ ist kein gültiges Kürzel – "
-                              f"„{shortcuts.action(action_id).name}“ bleibt unverändert.")
+        self.key_hint.setText(_("“{keys}” is not a valid shortcut – “{action}” stays unchanged.")
+                              .format(keys=_native(seq) or seq,
+                                      action=_(shortcuts.action(action_id).name)))
         self.key_hint.show()
 
     def _show_keys(self, action_id: str) -> None:
@@ -297,9 +328,9 @@ class SettingsDialog(QDialog):
             self.shortcut_table.setCellWidget(row, COL_RESET, button)
 
     def _reset_widget(self, default: str) -> QPushButton:
-        button = QPushButton("Standard")
+        button = QPushButton(_("Default"))
         button.setObjectName("tableButton")
-        button.setToolTip(f"Standard: {_native(default) or 'kein Kürzel'}")
+        button.setToolTip(_("Default: {keys}").format(keys=_native(default) or _("no shortcut")))
         return button
 
     def reset_button(self, action_id: str) -> QPushButton | None:
@@ -318,14 +349,14 @@ class SettingsDialog(QDialog):
     def _check_conflicts(self) -> None:
         """Doppelt belegte Kürzel rot markieren; solange es sie gibt, ist Speichern gesperrt."""
         found = shortcuts.conflicts(self._keys)
-        clashing = {action_id for _, ids in found for action_id in ids}
+        clashing = {action_id for _seq, ids in found for action_id in ids}
         for row, action_id in enumerate(self._rows):
             color = CONFLICT_COLOR if action_id in clashing else None
             for column in (COL_ACTION, COL_SCOPE, COL_KEYS):
                 self.shortcut_table.item(row, column).setData(Qt.ItemDataRole.ForegroundRole, color)
-        lines = [f"{_native(seq)}: " + ", ".join(shortcuts.action(i).name for i in ids)
+        lines = [f"{_native(seq)}: " + ", ".join(_(shortcuts.action(i).name) for i in ids)
                  for seq, ids in found]
-        self.conflict_hint.setText("Tastenkürzel doppelt belegt – zum Speichern eines ändern:\n"
+        self.conflict_hint.setText(_("Shortcuts assigned twice – change one to save:") + "\n"
                                    + "\n".join(lines))
         self.conflict_hint.setVisible(bool(found))
         self.save_button.setEnabled(not found)
@@ -349,8 +380,9 @@ class SettingsDialog(QDialog):
             if not name and not host:
                 continue
             if not valid_host(host):
-                self.error.setText(f"Netzwerkdrucker {name or row + 1}: Adresse „{host}“ ungültig – "
-                                   "nur IP-Adresse oder Name, ohne „tcp://“ und Port")
+                self.error.setText(_("Network printer {name}: address “{host}” invalid – only an "
+                                     "IP address or name, without “tcp://” and port").format(
+                                         name=name or row + 1, host=host))
                 self.error.show()
                 return None
             entries.append({"name": name, "host": host,
@@ -360,6 +392,14 @@ class SettingsDialog(QDialog):
     def _family_changed(self, _font) -> None:
         self._family_touched = True
 
+    def restart_needed(self) -> bool:
+        """Wirkt eine gewählte Einstellung erst nach einem Neustart anders als jetzt? (Liest nur die
+        Felder der Neustart-Einstellungen – keine Prüfung anderer Felder.)"""
+        return restart_pending(self.language.currentData(), self.zoom.value(), self._started)
+
+    def _update_restart_hint(self) -> None:
+        self.restart_hint.setVisible(self.restart_needed())
+
     def values(self) -> Settings:
         return Settings(
             label_id=self.label.currentData(),
@@ -382,6 +422,7 @@ class SettingsDialog(QDialog):
             last_model=self._last_model,
             printer_options=dict(self._printer_options),
             zebra_dpi=self.zebra_dpi.currentData(),
+            language=self.language.currentData(),
             network_printers=self._network_values() or [],
             shortcuts={action_id: seq for action_id, seq in self._keys.items()
                        if not _same(seq, shortcuts.action(action_id).default)},
@@ -410,10 +451,12 @@ def _model_combo(automatic: str | None, zebra: bool = False) -> QComboBox:
     if automatic is not None:
         combo.addItem(automatic, "")
     for model in SUPPORTED_MODELS:
-        combo.addItem(model if capabilities(model).tested else f"{model} – ungeprüft", model)
+        combo.addItem(model if capabilities(model).tested
+                      else _("{model} – untested").format(model=model), model)
     if zebra:
         for dpi in zpl.RESOLUTIONS:
-            combo.addItem(f"Zebra (ZPL) {dpi} dpi – ungeprüft", zpl.model_for(dpi))
+            combo.addItem(_("Zebra (ZPL) {dpi} dpi – untested").format(dpi=dpi),
+                          zpl.model_for(dpi))
     return combo
 
 
diff --git a/src/labelwerk/gui/symbol_dialog.py b/src/labelwerk/gui/symbol_dialog.py
index cf309c0..042fcff 100644
--- a/src/labelwerk/gui/symbol_dialog.py
+++ b/src/labelwerk/gui/symbol_dialog.py
@@ -20,17 +20,18 @@ from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel
 
 from .. import clipart
 from ..clipart import Symbol
+from ..i18n import N_, _
 from .image_import import MIME_SYMBOL
 ICON_PX = 48
 ICON_CACHE = 800               # höchstens so viele Vorschauen gemerkt (je 96 × 96 × 4 Byte, ca. 30 MB)
-SPECIAL = (("zuletzt", "Zuletzt verwendet"), ("favoriten", "Favoriten"))
-ALL_SUBGROUPS = "Alle"
-EMPTY_OWN = ("Noch keine eigenen Symbole. SVG- oder PNG-Dateien in diesen Ordner legen "
-             "(Unterordner werden nicht gelesen):\n{path}")
-EMPTY_FAVORITES = "Noch keine Favoriten – Symbol wählen und ★ drücken."
-EMPTY_RECENT = "Noch nichts eingefügt."
-NO_RESULTS = "Nichts gefunden."
-FAVORITE = ("☆ FAVORIT", "★ FAVORIT")          # nicht / schon Favorit
+SPECIAL = (("zuletzt", N_("Recently used")), ("favoriten", N_("Favorites")))
+ALL_SUBGROUPS = N_("All")
+EMPTY_OWN = N_("No own symbols yet. Put SVG or PNG files into this folder "
+               "(subfolders are not read):\n{path}")
+EMPTY_FAVORITES = N_("No favorites yet – choose a symbol and press ★.")
+EMPTY_RECENT = N_("Nothing inserted yet.")
+NO_RESULTS = N_("Nothing found.")
+FAVORITE = (N_("☆ FAVORITE"), N_("★ FAVORITE"))          # nicht / schon Favorit
 WINDOW_SIZE = (720, 520)
 
 
@@ -121,14 +122,14 @@ class SymbolDialog(QWidget):
 
     def __init__(self, recent: list[str], favorites: list[str], parent=None):
         super().__init__(parent, Qt.WindowType.Tool)
-        self.setWindowTitle("Symbol einfügen")
+        self.setWindowTitle(_("Insert symbol"))
         self.resize(*WINDOW_SIZE)
         self.recent = list(recent)
         self.favorites = list(favorites)
         outer = QVBoxLayout(self)
         self.search = QLineEdit()
         self.search.setObjectName("symbolSearch")
-        self.search.setPlaceholderText("Suchen … (z. B. Erde, zerbrechlich, Haus)")
+        self.search.setPlaceholderText(_("Search … (e.g. earth, fragile, house)"))
         self.search.setClearButtonEnabled(True)
         outer.addWidget(self.search)
         row = QHBoxLayout()
@@ -136,9 +137,9 @@ class SymbolDialog(QWidget):
         self.groups = QListWidget()
         self.groups.setObjectName("symbolGroups")
         self.groups.setMaximumWidth(180)
-        self._group_keys = [key for key, _ in SPECIAL] + [key for key, _ in clipart.GROUPS]
-        for _, name in (*SPECIAL, *clipart.GROUPS):
-            self.groups.addItem(name)
+        self._group_keys = [key for key, __ in SPECIAL] + [key for key, __ in clipart.GROUPS]
+        for __, name in (*SPECIAL, *clipart.GROUPS):
+            self.groups.addItem(_(name))
         row.addWidget(self.groups)
         right = QVBoxLayout()
         row.addLayout(right, 1)
@@ -167,12 +168,12 @@ class SymbolDialog(QWidget):
         self.empty.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
         right.addWidget(self.empty)
         buttons = QHBoxLayout()
-        self.open_folder = QPushButton("ORDNER ÖFFNEN")
-        self.open_folder.setToolTip("Ordner für eigene Symbole öffnen (wird angelegt)")
-        self.favorite = QPushButton(FAVORITE[0])
+        self.open_folder = QPushButton(_("OPEN FOLDER"))
+        self.open_folder.setToolTip(_("Open the folder for your own symbols (created if needed)"))
+        self.favorite = QPushButton(_(FAVORITE[0]))
         self.favorite.setObjectName("formatButton")     # RawBlock: gedrückt schwarz
         self.favorite.setCheckable(True)
-        self.insert = QPushButton("EINFÜGEN")
+        self.insert = QPushButton(_("INSERT"))
         for button in (self.open_folder, self.favorite):
             buttons.addWidget(button)
         buttons.addStretch()
@@ -182,17 +183,17 @@ class SymbolDialog(QWidget):
         self.info.setWordWrap(True)
         right.addWidget(self.info)
 
-        self.search.textChanged.connect(lambda _: self.refresh())
+        self.search.textChanged.connect(lambda _text: self.refresh())
         self.search.returnPressed.connect(self.choose)            # erster Treffer ist gewählt
         self.search.installEventFilter(self)
-        self.groups.currentRowChanged.connect(lambda _: self._group_changed())
-        self.subgroup.currentIndexChanged.connect(lambda _: self.refresh())
+        self.groups.currentRowChanged.connect(lambda _row: self._group_changed())
+        self.subgroup.currentIndexChanged.connect(lambda _index: self.refresh())
         # nur doppelklicken – „activated“ käme nach dem Doppelklick noch einmal (bzw. bei
         # Einfachklick-Einstellung schon beim Auswählen); Enter: eventFilter
-        self.grid.doubleClicked.connect(lambda _: self.choose())
+        self.grid.doubleClicked.connect(lambda _index: self.choose())
         self.grid.installEventFilter(self)
         self.grid.customContextMenuRequested.connect(self._context_menu)
-        self.grid.selectionModel().currentChanged.connect(lambda *_: self._current_changed())
+        self.grid.selectionModel().currentChanged.connect(lambda *_args: self._current_changed())
         self.insert.clicked.connect(self.choose)
         self.favorite.clicked.connect(self._toggle_favorite)
         self.open_folder.clicked.connect(self.show_own_folder)
@@ -229,7 +230,7 @@ class SymbolDialog(QWidget):
             {s.subgroup for s in clipart.symbols(group)})
         self.subgroup.blockSignals(True)
         self.subgroup.clear()
-        self.subgroup.addItems([ALL_SUBGROUPS, *names] if len(names) > 1 else [])
+        self.subgroup.addItems([_(ALL_SUBGROUPS), *names] if len(names) > 1 else [])
         self.subgroup.setVisible(len(names) > 1)
         self.subgroup.blockSignals(False)
         self.open_folder.setVisible(group == "eigene")
@@ -252,7 +253,7 @@ class SymbolDialog(QWidget):
         else:
             pool = self._pool()
             sub = self.subgroup.currentText()
-            if sub and sub != ALL_SUBGROUPS:
+            if self.subgroup.currentIndex() > 0:             # 0 = alle
                 pool = [s for s in pool if s.subgroup == sub]
         self.subgroup.setEnabled(not text)
         self.model.set_symbols(pool)
@@ -264,9 +265,11 @@ class SymbolDialog(QWidget):
 
     def _empty_text(self, searching: bool) -> str:
         if searching:
-            return NO_RESULTS
-        return {"eigene": EMPTY_OWN.format(path=clipart.own_dir()),
-                "favoriten": EMPTY_FAVORITES, "zuletzt": EMPTY_RECENT}.get(self.group(), "")
+            return _(NO_RESULTS)
+        if self.group() == "eigene":
+            return _(EMPTY_OWN).format(path=clipart.own_dir())
+        text = {"favoriten": EMPTY_FAVORITES, "zuletzt": EMPTY_RECENT}.get(self.group())
+        return _(text) if text else ""
 
     def current(self) -> Symbol | None:
         index = self.grid.currentIndex()
@@ -278,7 +281,7 @@ class SymbolDialog(QWidget):
         self.favorite.setEnabled(symbol is not None)
         favorite = symbol is not None and symbol.id in self.favorites
         self.favorite.setChecked(favorite)
-        self.favorite.setText(FAVORITE[favorite])
+        self.favorite.setText(_(FAVORITE[favorite]))
         self.info.setText("" if symbol is None else
                           f"{symbol.name} · {symbol.source}"
                           + (f" · {symbol.license}" if symbol.license else ""))
@@ -298,9 +301,9 @@ class SymbolDialog(QWidget):
         """Kontextmenü eines Symbols: Einfügen, Zu Favoriten / Aus Favoriten entfernen."""
         self.grid.setCurrentIndex(index)
         menu = QMenu(self)
-        menu.addAction("Einfügen", self.choose)
+        menu.addAction(_("Insert"), self.choose)
         favorite = self.current() is not None and self.current().id in self.favorites
-        menu.addAction("Aus Favoriten entfernen" if favorite else "Zu Favoriten",
+        menu.addAction(_("Remove from favorites") if favorite else _("Add to favorites"),
                        self._toggle_favorite)
         return menu
 
diff --git a/src/labelwerk/gui/tools.py b/src/labelwerk/gui/tools.py
index f3faf45..9a2d15e 100644
--- a/src/labelwerk/gui/tools.py
+++ b/src/labelwerk/gui/tools.py
@@ -8,6 +8,7 @@ from dataclasses import dataclass
 from typing import Callable
 
 from ..document import Document
+from ..i18n import N_
 from .panels import Panel
 from .panels.barcode import BarcodePanel
 from .panels.file import FilePanel
@@ -21,20 +22,21 @@ from .panels.text import TextPanel
 @dataclass(frozen=True)
 class Tool:
     key: str
-    title: str
+    title: str                                 # englisch (N_), angezeigt wird _(title)
     icon: str                                  # Name im Freedesktop-Icon-Theme
     panel: Callable[[Document], Panel]
-    tip: str = ""                              # Tooltip (sonst der Titel)
+    tip: str = ""                              # Tooltip (sonst der Titel), englisch (N_)
 
 
 START_TOOL = "paper"                           # Reiter beim Start
 
 TOOLS = [
-    Tool("file", "Datei", "document-open", FilePanel, "Datei und Favoriten"),
-    Tool("paper", "Papier", "document-page-setup", PaperPanel),
-    Tool("text", "Text", "insert-text", TextPanel),
-    Tool("image", "Bild", "insert-image", ImagePanel),
-    Tool("barcode", "Barcode", "view-barcode-qr", BarcodePanel, "Barcodes und QR-Codes"),
-    Tool("layout", "Layout", "align-horizontal-left", LayoutPanel),
-    Tool("series", "Serie", "view-list-text", SeriesPanel, "Serien aus Tabelle oder Nummerierung"),
+    Tool("file", N_("File"), "document-open", FilePanel, N_("File and favorites")),
+    Tool("paper", N_("Paper"), "document-page-setup", PaperPanel),
+    Tool("text", N_("Text"), "insert-text", TextPanel),
+    Tool("image", N_("Image"), "insert-image", ImagePanel),
+    Tool("barcode", N_("Barcode"), "view-barcode-qr", BarcodePanel, N_("Barcodes and QR codes")),
+    Tool("layout", N_("Layout"), "align-horizontal-left", LayoutPanel),
+    Tool("series", N_("Series"), "view-list-text", SeriesPanel,
+         N_("Series from a table or numbering")),
 ]
diff --git a/src/labelwerk/gui/widgets.py b/src/labelwerk/gui/widgets.py
index dbcae3f..66f7828 100644
--- a/src/labelwerk/gui/widgets.py
+++ b/src/labelwerk/gui/widgets.py
@@ -3,6 +3,8 @@ from __future__ import annotations
 
 from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox
 
+from .. import i18n
+
 # Qt legt das Textfeld eines per Stylesheet gerahmten Zahlenfelds über den linken Rahmen;
 # ein Textrand hält die Zahl lesbar (Innenabstände im Stylesheet greifen dort nicht).
 TEXT_MARGIN = 10
@@ -15,6 +17,19 @@ class SpinBox(QSpinBox):
 
 
 class DoubleSpinBox(QDoubleSpinBox):
+    """Zeigt Zahlen mit dem Dezimaltrenner der Sprache (``QLocale``); getippt gelten Komma und
+    Punkt (ein Punkt wird in Deutsch zum Komma und umgekehrt)."""
+
     def __init__(self, parent=None):
         super().__init__(parent)
         self.lineEdit().setTextMargins(TEXT_MARGIN, 0, 0, 0)
+
+    def _own(self, text: str) -> str:
+        own = self.locale().decimalPoint()
+        return text.replace("." if own == "," else ",", own)
+
+    def validate(self, text: str, pos: int):
+        return super().validate(self._own(text), pos)
+
+    def valueFromText(self, text: str) -> float:
+        return super().valueFromText(self._own(text))
diff --git a/src/labelwerk/i18n.py b/src/labelwerk/i18n.py
new file mode 100644
index 0000000..733f802
--- /dev/null
+++ b/src/labelwerk/i18n.py
@@ -0,0 +1,253 @@
+"""Übersetzungen ohne Qt und ohne zusätzliche Bibliothek: Texte im Code sind englisch, je Sprache
+eine ``po/<code>.po`` im Paket (gelesen beim Start – keine ``.mo``-Dateien, kein Build-Schritt).
+
+``_("Text")`` übersetzt, ``ngettext`` mit Mehrzahl, ``pgettext`` mit Kontext (gleiches Wort,
+andere Bedeutung), ``N_`` markiert Texte in Tabellen auf Modulebene (übersetzt wird erst beim
+Anzeigen). Platzhalter sind benannt (``_("… {label} …").format(label=…)``), damit jede Sprache ihre
+Reihenfolge wählen kann. ``set_language`` gilt für alles danach (CLI und GUI setzen sie zuerst).
+"""
+from __future__ import annotations
+
+import ast
+import gettext
+import os
+import re
+import sys
+from dataclasses import dataclass, field
+from pathlib import Path
+
+PO_DIR = Path(__file__).resolve().parent / "po"
+SOURCE = "en"                               # Sprache der Texte im Code
+NAMES = {"de": "Deutsch", "en": "English"}  # Name einer Sprache in ihr selbst
+DECIMAL = {"de": ","}                       # Dezimaltrenner (sonst Punkt)
+# Regionen mit Dezimalkomma (Sprachteil von LC_NUMERIC/LANG) – für Zahlen im Etikett-Inhalt
+COMMA_REGIONS = frozenset({"de", "fr", "es", "it", "nl", "pt", "pl", "cs", "sk", "da", "sv", "nb",
+                           "nn", "fi", "ru", "uk", "tr", "hu", "ro", "hr", "sl", "el", "bg", "lt",
+                           "lv", "et", "id", "vi"})
+
+
+@dataclass
+class Catalog:
+    """Übersetzungen einer Sprache: (Kontext, Text) → Übersetzung bzw. Mehrzahlformen."""
+    language: str
+    messages: dict[tuple[str, str], list[str]] = field(default_factory=dict)
+    plural: str = "n != 1"
+
+    def plural_index(self, n: int) -> int:
+        try:
+            return int(gettext.c2py(self.plural)(n))
+        except (ValueError, SyntaxError):
+            raise PoError(f"Plural-Forms: {self.plural!r}") from None
+
+
+class PoError(ValueError):
+    """``.po``-Datei nicht lesbar."""
+
+
+_ESCAPE = re.compile(r'\\(?:([ntrabfv"\\?\'])|([0-7]{1,3})|x([0-9a-fA-F]+))')
+_SIMPLE = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", '"': '"',
+           "\\": "\\", "?": "?", "'": "'"}
+
+
+def unquote(text: str, where: str) -> str:
+    """Text in Anführungszeichen einer ``.po``-Zeile mit den Escapes von C (``\\n``, ``\\"``,
+    oktal, ``\\x``) – ohne Python-Syntax auszuwerten."""
+    text = text.strip()
+    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
+        raise PoError(f"{where}: quoted text expected")
+    body = text[1:-1]
+    if re.search(r'(?<!\\)(?:\\\\)*"', body):
+        raise PoError(f"{where}: unescaped quote")
+    rest = _ESCAPE.sub("", body)
+    if "\\" in rest:
+        raise PoError(f"{where}: invalid escape")
+    return _ESCAPE.sub(lambda m: _SIMPLE[m[1]] if m[1] else chr(int(m[2], 8)) if m[2]
+                       else chr(int(m[3], 16)), body)
+
+
+def parse_po(text: str, language: str = "") -> Catalog:
+    """Inhalt einer ``.po``-Datei; leere, unsichere (``#, fuzzy``) und veraltete (``#~``)
+    Übersetzungen zählen nicht."""
+    catalog = Catalog(language)
+    entry: dict[str, str] = {}
+    fuzzy = next_fuzzy = False
+    key = None
+
+    def finish():
+        nonlocal entry, fuzzy
+        if "msgid" in entry:
+            forms = [entry[k] for k in sorted(entry, key=_form_order) if k.startswith("msgstr")]
+            if entry["msgid"] == "" and "msgctxt" not in entry:
+                m = re.search(r"plural=([^;\n]+)", forms[0] if forms else "")
+                if m:
+                    catalog.plural = m[1].strip()
+                    catalog.plural_index(1)          # Ausdruck prüfen
+            elif forms and all(forms) and not fuzzy:
+                catalog.messages[(entry.get("msgctxt", ""), entry["msgid"])] = forms
+        entry, fuzzy = {}, False
+
+    for number, line in enumerate(text.splitlines(), start=1):
+        where = f"line {number}"
+        line = line.strip()
+        if line.startswith("#,") and "fuzzy" in line:
+            next_fuzzy = True
+        if not line or line.startswith("#"):
+            continue
+        if line.startswith('"'):
+            if key is None:
+                raise PoError(f"{where}: continuation without entry")
+            entry[key] += unquote(line, where)
+            continue
+        m = re.match(r"(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+(.*)$", line)
+        if m is None:
+            raise PoError(f"{where}: unknown line")
+        key = m[1]
+        if key in ("msgctxt", "msgid") and (any(k.startswith("msgstr") for k in entry)
+                                           or key == "msgctxt" and "msgid" in entry):
+            finish()
+        if key in ("msgctxt", "msgid") and not entry:
+            fuzzy, next_fuzzy = next_fuzzy, False
+        entry[key] = unquote(m[2], where)
+    finish()
+    return catalog
+
+
+def _form_order(key: str) -> int:
+    m = re.search(r"\[(\d+)\]", key)
+    return int(m[1]) if m else 0
+
+
+_catalog: Catalog | None = None
+_language = SOURCE
+
+
+def available() -> list[str]:
+    """Sprachen, die labelwerk kann: Englisch und jede mit ``.po``."""
+    return sorted({SOURCE, *(p.stem for p in PO_DIR.glob("*.po"))})
+
+
+def system_language(environ=None) -> str:
+    """Sprache des Systems wie bei GNU gettext: Gebietsschema aus ``LC_ALL`` › ``LC_MESSAGES`` ›
+    ``LANG``; ist es „C“/„POSIX“ (oder fehlt), Englisch – sonst zuerst die Liste ``LANGUAGE``
+    („de_AT:de:en“), dann das Gebietsschema; was labelwerk nicht kann, wird Englisch."""
+    env = os.environ if environ is None else environ
+    known = available()
+
+    def code(value: str) -> str:
+        return value.split(".")[0].split("@")[0].split("_")[0].lower()
+    locale = next((env[n] for n in ("LC_ALL", "LC_MESSAGES", "LANG") if env.get(n)), "")
+    if code(locale) in ("", "c", "posix"):
+        return SOURCE
+    for part in [*env.get("LANGUAGE", "").split(":"), locale]:
+        if code(part) in known:
+            return code(part)
+    return SOURCE
+
+
+def set_language(code: str = "") -> str:
+    """Sprache setzen ("" = Systemsprache); unbekannt oder ``.po`` defekt → Englisch (Hinweis auf
+    stderr). Zurück kommt die gültige Sprache."""
+    global _catalog, _language
+    code = code or system_language()
+    if code not in available():
+        code = SOURCE
+    _catalog, _language = None, code
+    if code != SOURCE:
+        try:
+            _catalog = parse_po((PO_DIR / f"{code}.po").read_text(encoding="utf-8-sig"), code)
+        except (OSError, PoError, UnicodeDecodeError) as e:
+            print(f"labelwerk: translation {code} unreadable ({e}) – using English", file=sys.stderr)
+            _language = SOURCE
+    return _language
+
+
+_all_cache: dict[tuple[str, str], tuple[str, ...]] = {}
+
+
+def all_translations(context: str, text: str) -> tuple[str, ...]:
+    """Ein Text in jeder Sprache, die labelwerk kann (Original zuerst) – für Namen, die in jeder
+    Sprache gelten sollen (Platzhalter ``{Nummer}``/``{Number}``)."""
+    key = (context, text)
+    if key not in _all_cache:
+        found = [text]
+        for code in available():
+            if code == SOURCE:
+                continue
+            try:
+                catalog = parse_po((PO_DIR / f"{code}.po").read_text(encoding="utf-8-sig"), code)
+            except (OSError, PoError, UnicodeDecodeError):
+                continue
+            for form in catalog.messages.get(key, []):
+                if form not in found:
+                    found.append(form)
+        _all_cache[key] = tuple(found)
+    return _all_cache[key]
+
+
+def language() -> str:
+    return _language
+
+
+def _(text: str) -> str:
+    return pgettext("", text)
+
+
+def NP_(context: str, text: str) -> str:
+    """Wie ``N_`` mit Kontext (übersetzt wird mit ``pgettext(context, text)``)."""
+    return text
+
+
+def N_(text: str) -> str:
+    """Nur markieren (für ``tools/i18n.py``); übersetzt wird beim Anzeigen mit ``_``."""
+    return text
+
+
+def pgettext(context: str, text: str) -> str:
+    if _catalog is None:
+        return text
+    forms = _catalog.messages.get((context, text))
+    return forms[0] if forms else text
+
+
+def ngettext(singular: str, plural: str, n: int) -> str:
+    if _catalog is not None:
+        forms = _catalog.messages.get(("", singular))
+        if forms:
+            index = _catalog.plural_index(n)
+            return forms[min(index, len(forms) - 1)]
+    return singular if n == 1 else plural
+
+
+def decimal() -> str:
+    """Dezimaltrenner der Sprache: „,“ bzw. „.“."""
+    return DECIMAL.get(_language, ".")
+
+
+def thousands(value: int) -> str:
+    """Ganze Zahl mit Tausendertrennung der Sprache: „1.000.000“ bzw. „1,000,000“."""
+    return f"{value:,}".replace(",", "." if decimal() == "," else ",")
+
+
+def parse_number(text: str) -> float:
+    """Zahl, wie getippt: Komma und Punkt gelten als Dezimaltrenner (ValueError sonst)."""
+    return float(text.strip().replace(",", "."))
+
+
+def content_decimal(environ=None) -> str:
+    """Dezimaltrenner für Zahlen im Etikett-Inhalt (Excel-Zellen einer Serie): wie die
+    Regionaleinstellung des Systems (``LC_ALL`` › ``LC_NUMERIC`` › ``LANG``), nicht die Sprache der
+    Oberfläche – dieselbe Datei druckt in Deutschland mit Komma, egal welche Sprache labelwerk zeigt."""
+    env = os.environ if environ is None else environ
+    for name in ("LC_ALL", "LC_NUMERIC", "LANG"):
+        value = env.get(name, "")
+        if value:
+            code = value.split(".")[0].split("@")[0].split("_")[0].lower()
+            return "," if code in COMMA_REGIONS else "."
+    return "."
+
+
+def number(value: float, digits: int | None = None) -> str:
+    """Zahl für Meldungen: ``digits`` Nachkommastellen (None: so kurz wie möglich, „:g“), mit dem
+    Dezimaltrenner der Sprache."""
+    text = f"{value:g}" if digits is None else f"{value:.{digits}f}"
+    return text.replace(".", decimal())
diff --git a/src/labelwerk/imaging.py b/src/labelwerk/imaging.py
index e093f90..119cefb 100644
--- a/src/labelwerk/imaging.py
+++ b/src/labelwerk/imaging.py
@@ -11,6 +11,8 @@ from __future__ import annotations
 
 from PIL import Image, ImageChops
 
+from .i18n import _
+
 MODES = ("line", "photo")      # Strich (harte Schwelle) | Foto (Rasterpunkte)
 MAX_DPI = 600                  # feiner druckt der QL nicht (300 dpi) – mehr kostet nur Speicher
 MAX_PIXELS = 6000              # längste Seite in Pixeln (Speicher; bei 300 dpi gut 50 cm)
@@ -57,9 +59,11 @@ def limit_size(img: Image.Image, dpi: float,
 def check(mode: str, threshold: int) -> None:
     """Umwandlung und Schwelle prüfen; ``ValueError`` mit verständlicher Meldung."""
     if mode not in MODES:
-        raise ValueError(f"Unbekannte Umwandlung {mode!r} – erlaubt: Strich, Foto (line, photo)")
+        raise ValueError(_("Unknown conversion {mode!r} – allowed: line art, photo (line, photo)").format(
+            mode=mode))
     if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 255:
-        raise ValueError(f"Schwelle muss eine ganze Zahl von 0 bis 255 sein, nicht {threshold!r}.")
+        raise ValueError(_("Threshold must be a whole number from 0 to 255, not {threshold!r}.").format(
+            threshold=threshold))
 
 
 def photo_curve(threshold: int) -> list[int]:
diff --git a/src/labelwerk/labels.py b/src/labelwerk/labels.py
index bd130f6..4e1765c 100644
--- a/src/labelwerk/labels.py
+++ b/src/labelwerk/labels.py
@@ -7,6 +7,8 @@ from dataclasses import dataclass
 
 from brother_ql.labels import Color, FormFactor, LabelsManager
 
+from . import i18n
+from .i18n import _
 from .printers import capabilities
 
 DPI = 300  # Druckauflösung der QL-Drucker
@@ -21,7 +23,6 @@ class Label:
     width: int              # druckbare Punkte quer zum Band (bei ``dpi``)
     height: int | None      # None = Endlosband
     tape_mm: int
-    description: str
     shape: str              # "endless", "die_cut" oder "round"
     size_mm: tuple[int, int]  # Nenngröße laut Etikett, z. B. (62, 29); Endlos: (62, 0)
     total_width: int        # physische Breite in Punkten (bedruckbarer Bereich liegt mittig)
@@ -29,18 +30,31 @@ class Label:
     two_color: bool = False   # Rot/Schwarz (DK-22251, „62red“)
     dpi: int = DPI            # Druckauflösung (Brother 300; andere aus der ID)
 
+    @property
+    def description(self) -> str:
+        """Anzeigename, beim Abruf in der eingestellten Sprache: „62 mm endlos“, „Ø 24 mm rund“,
+        „62 x 29 mm gestanzt“; andere Drucker „54 × 25 mm · 300 dpi“."""
+        if _SIZED.fullmatch(self.id):
+            w, h = self.size_mm
+            return f"{mm_text(w)} × {mm_text(h)} mm · {self.dpi} dpi"
+        if self.shape == "endless":
+            return _("{width} mm continuous").format(width=self.size_mm[0])
+        if self.shape == "round":
+            return _("Ø {width} mm round").format(width=self.size_mm[0])
+        return _("{width} × {height} mm die-cut").format(width=self.size_mm[0], height=self.size_mm[1])
+
 
 def _convert(raw) -> Label:
     w, h = raw.dots_printable
     endless = raw.form_factor in (FormFactor.ENDLESS, FormFactor.PTOUCH_ENDLESS)
     if endless:
-        desc, shape = f"{raw.tape_size[0]} mm endlos", "endless"
+        shape = "endless"
     elif raw.form_factor == FormFactor.ROUND_DIE_CUT:
-        desc, shape = f"Ø {raw.tape_size[0]} mm rund", "round"
+        shape = "round"
     else:
-        desc, shape = f"{raw.tape_size[0]} x {raw.tape_size[1]} mm gestanzt", "die_cut"
+        shape = "die_cut"
     total_w, total_h = raw.dots_total
-    return Label(raw.identifier, w, None if endless else h, raw.tape_size[0], desc,
+    return Label(raw.identifier, w, None if endless else h, raw.tape_size[0],
                  shape, tuple(raw.tape_size), total_w, None if endless else total_h,
                  raw.color == Color.BLACK_RED_WHITE)
 
@@ -60,7 +74,7 @@ def _mm(value: float) -> str:
 
 def mm_text(value: float) -> str:
     """Maß in mm zum Anzeigen: „62“, „101,6“."""
-    return _mm(value).replace(".", ",")
+    return _mm(value).replace(".", i18n.decimal())
 
 
 def sized_label(label_id: str) -> Label | None:
@@ -73,8 +87,7 @@ def sized_label(label_id: str) -> Label | None:
             and DPI_RANGE[0] <= dpi <= DPI_RANGE[1]) or label_id != sized_id(w, h, dpi):
         return None                          # auch „057x32mm@203“: nur eine Schreibweise je Etikett
     width, height = round(w * dpi / 25.4), round(h * dpi / 25.4)
-    text = f"{mm_text(w)} × {mm_text(h)} mm · {dpi} dpi"
-    return Label(label_id, width, height, round(w), text, "die_cut", (w, h), width, height,
+    return Label(label_id, width, height, round(w), "die_cut", (w, h), width, height,
                  False, dpi)
 
 
@@ -84,7 +97,7 @@ def get_label(label_id: str) -> Label:
     for raw in _all_raw():
         if raw.identifier == label_id:
             return _convert(raw)
-    raise ValueError(f"Unbekanntes Etikett: {label_id!r}")
+    raise ValueError(_("Unknown label: {label_id!r}").format(label_id=label_id))
 
 
 def labels_for_model(model: str) -> list[Label]:
@@ -113,7 +126,7 @@ def labels_for_model(model: str) -> list[Label]:
 
 def format_mm(dots: int, dpi: int = DPI) -> str:
     """Druckpunkte als mm-Angabe mit Dezimalkomma, z. B. "58,9"."""
-    return f"{dots * 25.4 / dpi:.1f}".replace(".", ",")
+    return i18n.number(dots * 25.4 / dpi, 1)
 
 
 def length_limits(model: str) -> tuple[int, int]:
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index 9756c6e..3c36240 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -18,6 +18,7 @@ from dataclasses import dataclass, field, replace
 from . import barcodes
 from .document import (BARCODE_MM, MAX_PT, MIN_PT, ROTATIONS, BarcodeObject, Document,
                        ImageObject, TextObject)
+from .i18n import _
 from .labels import DPI, get_label, length_limits
 from .render import (PT, REF_PT, RenderedObject, frame_box, span_dots, label_margins, label_size,
                      render_object)
@@ -178,7 +179,8 @@ def align(rects: list[Rect], mode: str, area: Rect | None = None) -> list[Rect]:
     ohne ``area`` bleibt, wo es ist.
     """
     if mode not in ALIGN_MODES:
-        raise ValueError(f"Unbekannte Ausrichtung {mode!r} – erlaubt: {', '.join(ALIGN_MODES)}")
+        raise ValueError(_("Unknown alignment {mode!r} – allowed: {allowed}").format(
+            mode=mode, allowed=", ".join(ALIGN_MODES)))
     if area is None:
         if len(rects) < 2:
             return list(rects)
@@ -197,7 +199,8 @@ def align(rects: list[Rect], mode: str, area: Rect | None = None) -> list[Rect]:
 def match_size(rects: list[Rect], mode: str) -> list[Rect]:
     """Größe an das erste Rechteck angleichen (``same``, ``width``, ``height``); Ecke bleibt."""
     if mode not in SIZE_MODES:
-        raise ValueError(f"Unbekannte Größenangleichung {mode!r} – erlaubt: {', '.join(SIZE_MODES)}")
+        raise ValueError(_("Unknown size matching {mode!r} – allowed: {allowed}").format(
+            mode=mode, allowed=", ".join(SIZE_MODES)))
     if not rects:
         return []
     ref = rects[0]
@@ -240,7 +243,7 @@ def _needs_size(obj: Object) -> bool:
 
 def _text_only(obj: Object) -> None:
     if not isinstance(obj, TextObject):
-        raise TypeError(f"Nur für Text-Objekte, nicht für {type(obj).__name__}.")
+        raise TypeError(_("Only for text objects, not for {type}.").format(type=type(obj).__name__))
 
 
 def place(obj: Object, rect: Rect, dpi: int = DPI) -> Object:
@@ -527,12 +530,12 @@ def new_barcode(doc: Document, model: str, area: Rect, kind: str,
         fits = module >= 1 and (kind == "qr" or h >= BARCODE_MM[0])
         if best is None or (fits, module) > best[:2]:  # gleich gut: ungedreht
             best = (fits, module, turn, h)
-    _, module, obj.rotation, h = best
+    __, module, obj.rotation, h = best
     obj.module = max(1, module)
     if kind != "qr":
         obj.h_mm = math.floor(min(max(h, BARCODE_MM[0]), obj.h_mm) * 1000 + _EPS) / 1000
     shown = barcode_rect(obj, dpi)
-    rect, _, _ = insert_placement(doc, model, area, (shown.w, shown.h), others=others,
+    rect, __, __ = insert_placement(doc, model, area, (shown.w, shown.h), others=others,
                                   rotate=False)
     obj.x_mm = round(rect.cx - shown.w / 2, _DECIMALS)
     obj.y_mm = round(rect.cy - shown.h / 2, _DECIMALS)
@@ -614,22 +617,22 @@ def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) ->
     """
     _text_only(obj)
     if factor <= 0:
-        raise ValueError(f"Faktor muss größer als 0 sein, nicht {factor!r}.")
+        raise ValueError(_("Factor must be greater than 0, not {factor!r}.").format(factor=factor))
     scaled = copy.deepcopy(obj)
     spans = [span for para in scaled.paragraphs for span in para.spans
              if span.size_pt is not None]
     if obj.size_pt is None:
         if base_pt is None:
-            raise ValueError("Text mit automatischer Schriftgröße braucht die wirksame "
-                             "Grundgröße (base_pt) zum Skalieren.")
+            raise ValueError(_("Text with automatic font size needs the effective base size "
+                               "(base_pt) for scaling."))
         if base_pt <= 0:
-            raise ValueError(f"Schriftgröße muss größer als 0 sein, nicht {base_pt!r}.")
+            raise ValueError(_("Font size must be greater than 0, not {size!r}.").format(size=base_pt))
         for span in spans:                     # Bezug 12 pt → Bezug Grundgröße
             span.size_pt = span.size_pt * base_pt / REF_PT
         scaled.size_pt = base_pt
     sizes = [scaled.size_pt, *(span.size_pt for span in spans)]
     if min(sizes) <= 0:
-        raise ValueError(f"Schriftgröße muss größer als 0 sein, nicht {min(sizes)!r}.")
+        raise ValueError(_("Font size must be greater than 0, not {size!r}.").format(size=min(sizes)))
     low, high = MIN_PT / min(sizes), MAX_PT / max(sizes)
     if low <= high:                            # Grenze nur in Richtung des Faktors
         factor = min(max(factor, min(low, 1.0)), max(high, 1.0))
@@ -746,7 +749,7 @@ def maximize_object(obj: Object, rendered: RenderedObject, area: Rect, doc: Docu
     factor = target.w / shown.w if shown.w else 1.0
     scaled = scale_text(obj, factor, base_pt=rendered.base_pt)
     best = None
-    for _ in range(6):                       # Schrift wächst nicht ganz linear: nachregeln
+    for __ in range(6):                       # Schrift wächst nicht ganz linear: nachregeln
         scaled.x_mm, scaled.y_mm = area.x, area.y
         size = object_rect(render_object(scaled, doc, model))
         if not (size.w and size.h):
@@ -876,8 +879,9 @@ def from_object(point: tuple[float, float], rendered: RenderedObject,
 def _unturned(frame: tuple[float, float, float, float], rotation: int) -> tuple[float, float]:
     """Rahmengröße (Breite, Höhe) vor der Drehung."""
     if rotation not in ROTATIONS:
-        raise ValueError(f"Unbekannte Drehung {rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
-    _, _, w, h = frame
+        raise ValueError(_("Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees").format(
+            rotation=rotation))
+    __, __, w, h = frame
     return (h, w) if rotation in (90, 270) else (w, h)
 
 
diff --git a/src/labelwerk/media.py b/src/labelwerk/media.py
index 7634cb8..3ea1ca1 100644
--- a/src/labelwerk/media.py
+++ b/src/labelwerk/media.py
@@ -8,6 +8,7 @@ from dataclasses import dataclass
 
 from brother_ql.reader import RESP_MEDIA_TYPES, interpret_response
 
+from .i18n import _
 from .labels import labels_for_model
 
 # Puffer leeren (Invalidate), initialisieren (ESC @), Status anfragen (ESC i S)
@@ -28,10 +29,11 @@ class Media:
 
     def describe(self) -> str:
         if self.kind == "none":
-            return "keine Rolle eingelegt"
+            return _("no roll loaded")
         if self.kind == "endless":
-            return f"{self.width_mm} mm endlos"
-        return f"{self.width_mm} × {self.length_mm} mm gestanzt"
+            return _("{width} mm continuous").format(width=self.width_mm)
+        return _("{width} × {length} mm die-cut").format(width=self.width_mm,
+                                                          length=self.length_mm)
 
 
 def read_media(printer: str, timeout: float = TIMEOUT_S) -> Media:
@@ -41,18 +43,19 @@ def read_media(printer: str, timeout: float = TIMEOUT_S) -> Media:
 
 def parse_media(data: bytes) -> Media:
     if len(data) > 11 and data[11] not in RESP_MEDIA_TYPES:
-        raise MediaError(f"Unbekannte Rolle (Code 0x{data[11]:02X})")
+        raise MediaError(_("Unknown roll (code 0x{code:02X})").format(code=data[11]))
     try:
         status = interpret_response(data)
     except Exception as e:  # brother_ql wirft je nach Fehler NameError, UnboundLocalError …
-        raise MediaError(f"Unverständliche Antwort vom Drucker: {e}") from None
+        raise MediaError(_("Unintelligible answer from the printer: {error}").format(error=e)) \
+            from None
     kind = _KINDS.get(status["media_type"])
     if kind is None:
-        raise MediaError(f"Unbekannte Rolle: {status['media_type']}")
+        raise MediaError(_("Unknown roll: {media}").format(media=status["media_type"]))
     if kind == "none" or status["media_width"] == 0:
         return Media(0, 0, "none")
     if status["errors"]:
-        raise MediaError("Drucker meldet: " + ", ".join(status["errors"]))
+        raise MediaError(_("Printer reports: {errors}").format(errors=", ".join(status["errors"])))
     return Media(status["media_width"], status["media_length"], kind)
 
 
@@ -75,23 +78,24 @@ def _open_device(path: str) -> int:
 def query_status(printer: str, timeout: float = TIMEOUT_S, opener=_open_device) -> bytes:
     """Statusabfrage senden und die 32-Byte-Antwort lesen – mit festem Zeitlimit, nie blockierend."""
     if not printer.startswith("file://"):
-        raise MediaError("Medium prüfen geht nur über /dev/usb/lpN (Backend linux_kernel).")
+        raise MediaError(_("Check media only works via /dev/usb/lpN (backend linux_kernel)."))
     try:
         fd = opener(printer[len("file://"):])
     except FileNotFoundError:
-        raise MediaError(f"Drucker nicht gefunden: {printer}") from None
+        raise MediaError(_("Printer not found: {printer}").format(printer=printer)) from None
     except PermissionError:
-        raise MediaError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?") from None
+        raise MediaError(_("No permission for {device} – is the user in group 'lp'?")
+                         .format(device=printer)) from None
     except OSError as e:
-        raise MediaError(f"Drucker nicht erreichbar: {e}") from None
+        raise MediaError(_("Printer not reachable: {error}").format(error=e)) from None
     try:
         os.write(fd, STATUS_REQUEST)
         data, deadline = b"", time.monotonic() + timeout
         while len(data) < 32:
             left = deadline - time.monotonic()
             if left <= 0:
-                raise MediaError("Keine Antwort vom Drucker auf die Statusabfrage.")
-            ready, _, _ = select.select([fd], [], [], min(left, 0.1))
+                raise MediaError(_("No answer from the printer to the status request."))
+            ready, __, __ = select.select([fd], [], [], min(left, 0.1))
             if ready:
                 try:
                     data += os.read(fd, 32 - len(data))
@@ -99,6 +103,6 @@ def query_status(printer: str, timeout: float = TIMEOUT_S, opener=_open_device)
                     pass
         return data
     except OSError as e:
-        raise MediaError(f"Fehler bei der Statusabfrage: {e}") from None
+        raise MediaError(_("Error during the status request: {error}").format(error=e)) from None
     finally:
         os.close(fd)
diff --git a/src/labelwerk/po/README.md b/src/labelwerk/po/README.md
new file mode 100644
index 0000000..5236517
--- /dev/null
+++ b/src/labelwerk/po/README.md
@@ -0,0 +1,27 @@
+# Übersetzungen
+
+labelwerk ist auf Englisch geschrieben; jede andere Sprache ist eine Datei `<code>.po` in diesem Ordner
+(gettext-Format, UTF-8). `labelwerk.pot` ist die Vorlage mit allen Texten – sie wird erzeugt, nicht von Hand
+bearbeitet.
+
+## Eine neue Sprache beisteuern
+
+1. `labelwerk.pot` nach `<code>.po` kopieren (z. B. `fr.po`) und im Kopf `Language: fr` sowie die
+   `Plural-Forms` der Sprache eintragen (Liste: GNU gettext, „Plural forms“).
+2. Jedes `msgstr` übersetzen – mit Poedit, Weblate oder einem Texteditor. Platzhalter in geschweiften
+   Klammern (`{label}`, `{count}` …) unverändert übernehmen; ihre Reihenfolge darf sich ändern.
+3. In `src/labelwerk/i18n.py` den Namen der Sprache in ihr selbst (`NAMES`, z. B. `"fr": "Français"`) und, falls
+   sie ein Dezimalkomma hat, `DECIMAL` ergänzen.
+4. Prüfen: `python tools/i18n.py check` (fehlende Übersetzungen, falsche Platzhalter, Zahl der Mehrzahlformen).
+   Die Sprache erscheint danach in Einstellungen → Ansicht → Sprache und bei `labelwerk --lang <code>`.
+
+Hinweise für Übersetzer stehen als `#.`-Kommentar über dem Text (z. B. was `{where}` enthält); eigene Notizen
+als `# …` und unsichere Übersetzungen (`#, fuzzy`) bleiben bei `tools/i18n.py update` erhalten.
+
+## Für Entwickler
+
+- Texte für Nutzer immer englisch und mit `_("…")` (bzw. `ngettext`, `pgettext`; Tabellen auf Modulebene mit
+  `N_` markieren und beim Anzeigen `_()`), Platzhalter benannt: `_("… {name} …").format(name=…)`.
+- Nach Textänderungen: `python tools/i18n.py update` (Vorlage neu, neue Texte in jede `.po`), dann die
+  deutschen Übersetzungen in `de.po` ergänzen. Der Test `test_every_text_is_translated` hält alles vollständig,
+  `test_no_german_text_outside_the_translation` findet deutsche Texte, die nicht übersetzt werden.
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
new file mode 100644
index 0000000..584cc26
--- /dev/null
+++ b/src/labelwerk/po/de.po
@@ -0,0 +1,3212 @@
+msgid ""
+msgstr ""
+"Content-Type: text/plain; charset=UTF-8\n"
+"Language: de\n"
+"Plural-Forms: nplurals=2; plural=(n != 1);\n"
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid " in object {number}"
+msgstr " in Objekt {number}"
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+msgid " in the border"
+msgstr " im Rahmen"
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+msgid " in the numbering"
+msgstr " in der Nummerierung"
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+msgid " in the series"
+msgstr " in der Serie"
+
+#: src/labelwerk/cli.py
+msgid "'auto' or 4–100 pt (default from the settings)"
+msgstr "'auto' oder 4–100 pt (Standard aus den Einstellungen)"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "+ CURRENT"
+msgstr "+ AKTUELL"
+
+#: src/labelwerk/cli.py
+msgid "--font (font file) and --font-family exclude each other."
+msgstr "--font (Schriftdatei) und --font-family schließen sich aus."
+
+#: src/labelwerk/cli.py
+msgid "-l auto (query the roll) only works with printers via USB."
+msgstr "-l auto (Rolle abfragen) geht nur bei Druckern per USB."
+
+#: src/labelwerk/gui/main_window.py
+msgid "< 1%"
+msgstr "< 1 %"
+
+#: src/labelwerk/series.py
+#: src/labelwerk/storage.py
+msgid "A series needs exactly one: table or numbering"
+msgstr "Serie braucht genau eins: Tabelle oder Nummerierung"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "ADD"
+msgstr "HINZUFÜGEN"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "ALL"
+msgstr "ALLE"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Action"
+msgstr "Aktion"
+
+#: src/labelwerk/shortcuts.py
+msgid "Actual size (100%)"
+msgstr "Echte Größe (100 %)"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Add network printer …"
+msgstr "Netzwerkdrucker eintragen …"
+
+#: src/labelwerk/shortcuts.py
+msgid "Add text tool"
+msgstr "Werkzeug Text anlegen"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Add to favorites"
+msgstr "Zu Favoriten"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Address"
+msgstr "Adresse"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "After each label"
+msgstr "Nach jedem Etikett"
+
+#: src/labelwerk/zpl.py
+msgid "After printing"
+msgstr "Nach dem Druck"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align bottom edges"
+msgstr "Aneinander unten ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align bottom on paper"
+msgstr "Am Papier unten ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align horizontal centers"
+msgstr "Aneinander waagrecht mittig ausrichten"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Align left"
+msgstr "Linksbündig"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align left edges"
+msgstr "Aneinander links ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align left on paper"
+msgstr "Am Papier links ausrichten"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Align right"
+msgstr "Rechtsbündig"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align right edges"
+msgstr "Aneinander rechts ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align right on paper"
+msgstr "Am Papier rechts ausrichten"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Align selected objects"
+msgstr "Gewählte Objekte ausrichten"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Align to paper"
+msgstr "Am Papier ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align top edges"
+msgstr "Aneinander oben ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align top on paper"
+msgstr "Am Papier oben ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Align vertical centers"
+msgstr "Aneinander senkrecht mittig ausrichten"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "All"
+msgstr "Alle"
+
+#: src/labelwerk/gui/main_window.py
+msgid "An object extends beyond the label and will be cut off. Print anyway?"
+msgstr "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
+
+#: src/labelwerk/zpl.py
+msgid "As set on the printer"
+msgstr "Wie am Drucker eingestellt"
+
+#: src/labelwerk/gui/main_window.py
+#: src/labelwerk/gui/panels/paper.py
+msgid "Ask the printer which roll is loaded (prints nothing)"
+msgstr "Eingelegte Rolle vom Drucker abfragen (druckt nichts)"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "At startup"
+msgstr "Beim Start"
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Automatic"
+msgstr "Automatisch"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Automatic (detected)"
+msgstr "Automatisch (erkannt)"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Automatic (first found)"
+msgstr "Automatisch (erster gefundener)"
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Automatic (system language: {language})"
+msgstr "Automatisch (Systemsprache: {language})"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "BLACK"
+msgstr "SCHWARZ"
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/tools.py
+msgid "Barcode"
+msgstr "Barcode"
+
+#: src/labelwerk/barcodes.py
+msgid "Barcode too short for the human-readable text – make it taller or turn the text off"
+msgstr "Barcode zu niedrig für den Klartext – höher ziehen oder Klartext aus"
+
+#: src/labelwerk/barcodes.py
+msgid "Barcode without content"
+msgstr "Barcode ohne Inhalt"
+
+#: src/labelwerk/gui/tools.py
+msgid "Barcodes and QR codes"
+msgstr "Barcodes und QR-Codes"
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/shortcuts.py
+msgid "Bold"
+msgstr "Fett"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Border"
+msgstr "Rahmen"
+
+#: src/labelwerk/render.py
+msgid "Border does not fit on the label – reduce inset, line width or padding"
+msgstr "Rahmen passt nicht aufs Etikett – Abstand, Strichstärke oder Innenabstand verkleinern"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Border “rounded” must be yes or no, not {rounded!r}"
+msgstr "„abgerundet“ des Rahmens muss ja oder nein sein, nicht {rounded!r}"
+
+#: src/labelwerk/shortcuts.py
+msgid "Bring forward"
+msgstr "Nach vorne"
+
+#: src/labelwerk/printers.py
+msgid "Brother printer"
+msgstr "Brother-Drucker"
+
+#: src/labelwerk/detect.py
+msgid ""
+"Brother printer is connected via USB but in use by another program\n"
+"(e.g. a VM with USB passthrough). Release it there and switch the printer\n"
+"off and on again."
+msgstr ""
+"Brother-Drucker ist per USB angeschlossen, aber von einem anderen Programm belegt\n"
+"(z. B. VM mit USB-Durchreichung). Dort freigeben und den Drucker kurz aus- und\n"
+"wieder einschalten."
+
+#: src/labelwerk/detect.py
+msgid ""
+"Brother printer not found under /dev/usb/lp*.\n"
+"Check: switched on, Editor Lite LED off, 'lsusb', 'lsmod | grep usblp'."
+msgstr ""
+"Brother-Drucker unter /dev/usb/lp* nicht gefunden.\n"
+"Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', 'lsmod | grep usblp'."
+
+#: src/labelwerk/cli.py
+msgid ""
+"Brother printer not found via USB (pyusb).\n"
+"Check: switched on, Editor Lite LED off, 'lsusb', access to the USB bus (udev rule).\n"
+"Specify manually with -p usb://0x04f9:0xPID"
+msgstr ""
+"Brother-Drucker per USB (pyusb) nicht gefunden.\n"
+"Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', Zugriff auf den USB-Bus (udev-Regel).\n"
+"Manuell angeben mit -p usb://0x04f9:0xPID"
+
+#: src/labelwerk/gui/main_window.py
+msgid "CANCEL"
+msgstr "ABBRECHEN"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "CHECK MEDIA"
+msgstr "MEDIUM PRÜFEN"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "CHECKING …"
+msgstr "PRÜFE …"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "CSV or Excel file (.xlsx) – first row = column names"
+msgstr "CSV- oder Excel-Datei (.xlsx) – erste Zeile = Spaltennamen"
+
+#: src/labelwerk/cups.py
+msgid "CUPS commands missing (install the package cups-client)"
+msgstr "CUPS-Befehle fehlen (Paket cups-client installieren)"
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "CUPS does not answer ({command})"
+msgstr "CUPS antwortet nicht ({command})"
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "CUPS: {command} failed"
+msgstr "CUPS: {command} gescheitert"
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "CUPS: {reason}"
+msgstr "CUPS: {reason}"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Cancel the series – a part already sent (up to 10 labels, with “Only at the end” the whole job) is still printed"
+msgstr "Serie abbrechen – ein schon gesendeter Teil (bis zu 10 Etiketten, bei „Nur am Ende“ der ganze Auftrag) läuft zu Ende"
+
+#: src/labelwerk/gui/main_window.py
+#: src/labelwerk/printer.py
+msgid "Cancelled – nothing printed"
+msgstr "Abgebrochen – nichts gedruckt"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Cancelled – {printed} of {total} label printed"
+msgid_plural "Cancelled – {printed} of {total} labels printed"
+msgstr[0] "Abgebrochen – {printed} von {total} Etikett gedruckt"
+msgstr[1] "Abgebrochen – {printed} von {total} Etiketten gedruckt"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Cancelling …"
+msgstr "Wird abgebrochen …"
+
+#: src/labelwerk/fonts.py
+#, python-brace-format
+msgid "Cannot load font “{path}” ({error})."
+msgstr "Schrift „{path}“ kann nicht geladen werden ({error})."
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Cannot print the label ({error})"
+msgstr "Etikett kann nicht gedruckt werden ({error})"
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Cannot read file: {name} (not a valid SVG)"
+msgstr "Datei kann nicht gelesen werden: {name} (kein gültiges SVG)"
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Cannot read file: {name} ({reason})"
+msgstr "Datei kann nicht gelesen werden: {name} ({reason})"
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Cannot read symbol {name} (not a valid SVG)."
+msgstr "Symbol {name} kann nicht gelesen werden (kein gültiges SVG)."
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Cannot read the series ({error})"
+msgstr "Serie kann nicht gelesen werden ({error})"
+
+#: src/labelwerk/gui/image_import.py
+msgid "Cannot read vector image (not a valid SVG)."
+msgstr "Vektorbild kann nicht gelesen werden (kein gültiges SVG)."
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Canvas"
+msgstr "Arbeitsfläche"
+
+#: src/labelwerk/shortcuts.py
+msgid "Center horizontally on paper"
+msgstr "Am Papier waagrecht mittig ausrichten"
+
+#: src/labelwerk/shortcuts.py
+msgid "Center vertically on paper"
+msgstr "Am Papier senkrecht mittig ausrichten"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Centered"
+msgstr "Zentriert"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Changes take effect after a restart"
+msgstr "Änderungen erst nach Neustart aktiv"
+
+#: src/labelwerk/media.py
+msgid "Check media only works via /dev/usb/lpN (backend linux_kernel)."
+msgstr "Medium prüfen geht nur über /dev/usb/lpN (Backend linux_kernel)."
+
+#: src/labelwerk/gui/main_window.py
+msgid "Check media only works with Brother printers via USB"
+msgstr "Medium prüfen geht nur bei Brother-Druckern per USB"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Check the roll at startup and when the printer is switched on"
+msgstr "Rolle beim Start und beim Einschalten prüfen"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Checking the roll – please print again in a moment."
+msgstr "Rolle wird gerade geprüft – bitte gleich noch einmal drucken."
+
+#: src/labelwerk/gui/main_window.py
+msgid "Choose PDF page"
+msgstr "PDF-Seite wählen"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Choose printer"
+msgstr "Drucker wählen"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Chosen printer {printer} not found – switch it on or specify it with -p."
+msgstr "Gewählter Drucker {printer} nicht gefunden – einschalten oder mit -p angeben."
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Classic"
+msgstr "Klassisch"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Click a row and press the new key combination. Esc cancels, ✕ in the field removes the shortcut. Esc, Enter and Tab cannot be assigned here (they operate the table)."
+msgstr "Zeile anklicken und die neue Tastenkombination drücken. Esc bricht ab, ✕ im Feld entfernt das Kürzel. Esc, Enter und Tab lassen sich hier nicht belegen (sie bedienen die Tabelle)."
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Click on the label to create a text frame"
+msgstr "Auf das Etikett klicken, um einen Textrahmen anzulegen"
+
+#: src/labelwerk/gui/image_import.py
+msgid "Clipboard"
+msgstr "Zwischenablage"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Code 128 cannot encode “{char}” (ASCII only, no umlauts)"
+msgstr "Code 128 kann „{char}“ nicht darstellen (nur ASCII ohne Umlaute)"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Code 39 cannot encode “{char}” (allowed: 0–9, A–Z, space and - . $ / + %)"
+msgstr "Code 39 kann „{char}“ nicht darstellen (erlaubt: 0–9, A–Z, Leerzeichen und - . $ / + %)"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Color"
+msgstr "Farbe"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Columns"
+msgstr "Spalten"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Connection to {host} aborted after {sent} bytes ({reason})"
+msgstr "Verbindung zu {host} abgebrochen nach {sent} Bytes ({reason})"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Content"
+msgstr "Inhalt"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Content must be text, not {type}"
+msgstr "Inhalt muss Text sein, nicht {type}"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Content of the code; {{column}} is filled by the series"
+msgstr "Inhalt des Codes; {{Spalte}} füllt die Serie"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Content too long (at most {count} characters)"
+msgstr "Inhalt zu lang (höchstens {count} Zeichen)"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Content too long ({count} characters, at most {limit})"
+msgstr "Inhalt zu lang ({count} Zeichen, höchstens {limit})"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Content too long for a QR code (error correction {error})"
+msgstr "Inhalt zu lang für einen QR-Code (Fehlerkorrektur {error})"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Continuous"
+msgstr "Endlos"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Conversion"
+msgstr "Umwandlung"
+
+#: src/labelwerk/shortcuts.py
+msgid "Copy"
+msgstr "Kopieren"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Corners only"
+msgstr "Nur Ecken"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Count"
+msgstr "Anzahl"
+
+#: src/labelwerk/printer.py
+msgid "Cover opened while printing."
+msgstr "Deckel während des Drucks geöffnet."
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Crop automatically"
+msgstr "Zuschnitt automatisch"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Crop automatically (without crop marks and blank space)"
+msgstr "Automatisch zuschneiden (ohne Schnittmarken und Leerraum)"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Crop to the content (without crop marks and blank space); off = whole image"
+msgstr "Auf den Inhalt zuschneiden (ohne Schnittmarken und Leerraum); aus = ganzes Bild"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Crop {crop} is not inside the image ({width} × {height} pixels)."
+msgstr "Ausschnitt {crop} liegt nicht im Bild ({width} × {height} Pixel)."
+
+#: src/labelwerk/shortcuts.py
+msgid "Cut"
+msgstr "Ausschneiden"
+
+#: src/labelwerk/zpl.py
+msgid "Cut (cutter only)"
+msgstr "Schneiden (nur mit Abschneider)"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Cut every n labels: n must be a whole number from 1, not {value!r}"
+msgstr "Schneiden alle n Etiketten: n muss eine ganze Zahl ab 1 sein, nicht {value!r}"
+
+#: src/labelwerk/printer.py
+msgid "Cutter jammed."
+msgstr "Schneidwerk blockiert."
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Cutting"
+msgstr "Schnitt"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Cutting is set by the printer driver (system printer settings)"
+msgstr "Schneiden stellt der Druckertreiber ein (Druckerverwaltung des Systems)"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Dashed"
+msgstr "Gestrichelt"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Default"
+msgstr "Standard"
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Default: {keys}"
+msgstr "Standard: {keys}"
+
+#: src/labelwerk/shortcuts.py
+msgid "Delete"
+msgstr "Löschen"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Delete favorite"
+msgstr "Favorit löschen"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Delete favorite “{name}”?"
+msgstr "Favorit „{name}“ löschen?"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Delete …"
+msgstr "Löschen …"
+
+#: src/labelwerk/desktop.py
+msgid "Design and print labels (Brother QL)"
+msgstr "Etiketten gestalten und drucken (Brother QL)"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Die-cut"
+msgstr "Gestanzt"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Different roll"
+msgstr "Andere Rolle"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Digits"
+msgstr "Stellen"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Digits of the numbering: 0 to {limit}"
+msgstr "Stellen der Nummerierung: 0 bis {limit}"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Distance between the border and automatically placed text"
+msgstr "Abstand zwischen Rahmen und automatisch gesetztem Text"
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Distance from the left edge of the label"
+msgstr "Abstand vom linken Etikettrand"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Distance from the paper edge all around (across the tape the printer leaves about 1.5 mm free anyway)"
+msgstr "Abstand zur Papierkante ringsum (quer lässt der Drucker ohnehin rund 1,5 mm frei)"
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Distance from the top edge of the label"
+msgstr "Abstand vom oberen Etikettrand"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Distance of the border from the edge must be between {low} and {high} mm"
+msgstr "Abstand zum Rand des Rahmens muss zwischen {low} und {high} mm liegen"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Distance of the border from the printable edge"
+msgstr "Abstand des Rahmens vom bedruckbaren Rand"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Dotted"
+msgstr "Gepunktet"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Double"
+msgstr "Doppelt"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Double-click: as {{column}} into the selected text object or as new text"
+msgstr "Doppelklick: als {{Spalte}} ins gewählte Textobjekt bzw. als neuer Text"
+
+#: src/labelwerk/gui/canvas.py
+msgid "Drag: set the length · Double-click: automatic"
+msgstr "Ziehen: Länge festlegen · Doppelklick: automatisch"
+
+#: src/labelwerk/gui/image_import.py
+msgid "Dropped image"
+msgstr "Abgelegtes Bild"
+
+#: src/labelwerk/shortcuts.py
+msgid "Duplicate"
+msgstr "Duplizieren"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Edit"
+msgstr "Bearbeiten"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Effective model: {model}"
+msgstr "Wirksames Modell: {model}"
+
+#: src/labelwerk/clipart.py
+msgid "Electrical"
+msgstr "Elektro"
+
+#: src/labelwerk/gui/main_window.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Empty label"
+msgstr "Leeres Etikett"
+
+#: src/labelwerk/shortcuts.py
+msgid "End text editing"
+msgstr "Schreibmodus beenden"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Entry{where} is not an object"
+msgstr "Eintrag{where} ist kein Objekt"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Error at label {first}–{last} of {total} (check the ones before too): {error}"
+msgstr "Fehler bei Etikett {first}–{last} von {total} (auch die davor prüfen): {error}"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Error correction"
+msgstr "Fehlerkorrektur"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Error correction: higher = readable despite dirt/scratches, but larger"
+msgstr "Fehlerkorrektur: höher = lesbar trotz Schmutz/Kratzern, aber größer"
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Error during the status request: {error}"
+msgstr "Fehler bei der Statusabfrage: {error}"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "FIXED FRAME SIZE"
+msgstr "FESTE RAHMENGRÖSSE"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "FROM CLIPBOARD"
+msgstr "AUS ZWISCHENABLAGE"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "FROM FILE …"
+msgstr "AUS DATEI …"
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Factor must be greater than 0, not {factor!r}."
+msgstr "Faktor muss größer als 0 sein, nicht {factor!r}."
+
+#: src/labelwerk/gui/file_session.py
+msgid "Favorite"
+msgstr "Favorit"
+
+#: src/labelwerk/favorites.py
+#, python-brace-format
+msgid "Favorite “{name}” already exists"
+msgstr "Favorit „{name}“ gibt es schon"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Favorite “{name}” already exists. Replace it?"
+msgstr "Favorit „{name}“ gibt es schon. Ersetzen?"
+
+#: src/labelwerk/favorites.py
+#, python-brace-format
+msgid "Favorite “{name}” not found"
+msgstr "Favorit „{name}“ nicht gefunden"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Favorite “{name}” saved"
+msgstr "Favorit „{name}“ gespeichert"
+
+#: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Favorites"
+msgstr "Favoriten"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Favorites folder not created ({reason})"
+msgstr "Favoriten-Ordner nicht angelegt ({reason})"
+
+#: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/tools.py
+msgid "File"
+msgstr "Datei"
+
+#: src/labelwerk/gui/tools.py
+msgid "File and favorites"
+msgstr "Datei und Favoriten"
+
+#: src/labelwerk/files.py
+#: src/labelwerk/gui/image_import.py
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "File not found: {path}"
+msgstr "Datei nicht gefunden: {path}"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "File not found: {path} – removed from the list"
+msgstr "Datei nicht gefunden: {path} – aus der Liste entfernt"
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "File type not supported: {suffix} – possible: {allowed}"
+msgstr "Dateityp nicht unterstützt: {suffix} – möglich: {allowed}"
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "File type not supported: {type} – possible: {allowed}"
+msgstr "Dateityp nicht unterstützt: {type} – möglich: {allowed}"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "First number"
+msgstr "Erste Zahl"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Fixed shortcut – cannot be changed"
+msgstr "Kürzel fest – nicht änderbar"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Font"
+msgstr "Schriftart"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Font size"
+msgstr "Schriftgröße"
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Font size converted from {old} dots to {new} pt."
+msgstr "Schriftgröße von {old} Druckpunkten auf {new} pt umgerechnet."
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Font size in pt"
+msgstr "Schriftgröße in pt"
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Font size must be greater than 0, not {size!r}."
+msgstr "Schriftgröße muss größer als 0 sein, nicht {size!r}."
+
+#: src/labelwerk/cli.py
+msgid "Font size: 'auto' or 4–100 (pt)"
+msgstr "Schriftgröße: 'auto' oder 4–100 (pt)"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Font “{family}” not found – replaced by “{replacement}”."
+msgstr "Schrift „{family}“ nicht gefunden – ersetzt durch „{replacement}“."
+
+#: src/labelwerk/clipart.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "General"
+msgstr "Allgemein"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Global"
+msgstr "Global"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Grayscale as halftone dots – for photos and gradients"
+msgstr "Graustufen als Rasterpunkte – für Fotos und Verläufe"
+
+#: src/labelwerk/gui/panels/position.py
+msgid "H"
+msgstr "H"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "H – 30%"
+msgstr "H – 30 %"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Handed over to CUPS (job {job})"
+msgstr "An CUPS übergeben (Auftrag {job})"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Handed to the print queue ✓ (job {job})"
+msgstr "An die Druckwarteschlange übergeben ✓ (Auftrag {job})"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Handles and fields scale the image without distortion"
+msgstr "Anfasser und Felder skalieren das Bild ohne Verzerren"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Hard threshold – for codes, text and logos"
+msgstr "Harte Schwelle – für Codes, Schrift und Logos"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Height"
+msgstr "Höhe"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Height including the human-readable text"
+msgstr "Höhe samt Klartext"
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Height of the frame"
+msgstr "Höhe des Rahmens"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Height {height!r} mm invalid – allowed: {low}–{high} mm"
+msgstr "Höhe {height!r} mm ungültig – erlaubt: {low}–{high} mm"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Higher = darker"
+msgstr "Höher = mehr Schwarz"
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Horizontal"
+msgstr "Horizontal"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "How many labels"
+msgstr "Wie viele Etiketten"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Human-readable text"
+msgstr "Klartext"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Human-readable text must be on or off, not {text!r}"
+msgstr "Klartext muss an oder aus sein, nicht {text!r}"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "INSERT"
+msgstr "EINFÜGEN"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "INSERT BARCODE"
+msgstr "BARCODE EINFÜGEN"
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/tools.py
+msgid "Image"
+msgstr "Bild"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Image data “{key}”{where} not readable"
+msgstr "Bilddaten „{key}“{where} nicht lesbar"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Image data{where} not readable (PNG only)"
+msgstr "Bilddaten{where} nicht lesbar (nur PNG)"
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Image is {width} × {height} mm, label {label!r} is at most {max_w} mm wide – shrink with --fit (codes may become unreadable)"
+msgstr "Motiv ist {width} × {height} mm, Etikett {label!r} ist höchstens {max_w} mm breit – mit --fit verkleinern (Codes evtl. nicht mehr lesbar)"
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Image is {width} × {height} mm, label {label!r} is at most {max_w} × {max_h} mm – shrink with --fit (codes may become unreadable)"
+msgstr "Motiv ist {width} × {height} mm, Etikett {label!r} ist höchstens {max_w} × {max_h} mm groß – mit --fit verkleinern (Codes evtl. nicht mehr lesbar)"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Image not cropped – only white area found"
+msgstr "Bild nicht zugeschnitten – nur weiße Fläche gefunden"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Image reduced to {percent}"
+msgstr "Bild auf {percent} verkleinert"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Image reduced to {percent} – codes may no longer be readable"
+msgstr "Bild auf {percent} verkleinert – Codes ggf. nicht mehr lesbar"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Image rotated by 90° so that it fits 1:1"
+msgstr "Bild um 90° gedreht, damit es 1:1 passt"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Image size must be greater than 0, not {width} × {height} mm."
+msgstr "Größe des Bilds muss größer als 0 sein, nicht {width} × {height} mm."
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Images and PDF ({patterns});;All files (*)"
+msgstr "Bilder und PDF ({patterns});;Alle Dateien (*)"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Image{where} too large ({width} × {height} pixels, at most {limit})"
+msgstr "Bild{where} zu groß ({width} × {height} Pixel, höchstens {limit})"
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Insert"
+msgstr "Einfügen"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Insert a barcode of the chosen type"
+msgstr "Barcode der gewählten Art einfügen"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Insert a barcode or QR code – choose the type, type the content"
+msgstr "Barcode oder QR-Code einfügen – Art wählen, Inhalt eintippen"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert a screenshot"
+msgstr "Bildschirmfoto einfügen"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert an image from a file, the clipboard, as a screenshot or symbol – or drag it onto the label"
+msgstr "Bild aus einer Datei, der Zwischenablage, als Bildschirmfoto oder Symbol einfügen – oder aufs Etikett ziehen"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert an image from the clipboard"
+msgstr "Bild aus der Zwischenablage einfügen"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert an image or PDF page"
+msgstr "Bild oder PDF-Seite einfügen"
+
+#: src/labelwerk/shortcuts.py
+msgid "Insert barcode"
+msgstr "Barcode einfügen"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Insert image"
+msgstr "Bild einfügen"
+
+#: src/labelwerk/shortcuts.py
+msgid "Insert image …"
+msgstr "Bild einfügen …"
+
+#: src/labelwerk/shortcuts.py
+msgid "Insert screenshot"
+msgstr "Bildschirmfoto einfügen"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Insert symbol"
+msgstr "Symbol einfügen"
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/shortcuts.py
+msgid "Insert symbol …"
+msgstr "Symbol einfügen …"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Inserting images"
+msgstr "Bilder einfügen"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Inset"
+msgstr "Randabstand"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Installed: {path}"
+msgstr "Installiert: {path}"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Invalid address: {uri}"
+msgstr "Ungültige Adresse: {uri}"
+
+#: src/labelwerk/favorites.py
+#, python-brace-format
+msgid "Invalid name for the favorite: “{name}” (not empty, not too long, without / and \\ and control characters, not starting with a dot)"
+msgstr "Name für den Favoriten ungültig: „{name}“ (nicht leer, nicht zu lang, ohne / und \\ und Steuerzeichen, nicht mit Punkt beginnend)"
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "Invalid queue name: {name!r}"
+msgstr "Ungültiger Name der Warteschlange: {name!r}"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Invalid series sheet: {sheet!r}"
+msgstr "Blatt der Serie ungültig: {sheet!r}"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Invalid series table: {source!r}"
+msgstr "Tabelle der Serie ungültig: {source!r}"
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Invalid shortcut {seq!r}"
+msgstr "Ungültiges Tastenkürzel {seq!r}"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Invalid value for “{key}”{where}: {value}"
+msgstr "Wert für „{key}“{where} ungültig: {value}"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Invert"
+msgstr "Umkehren"
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/shortcuts.py
+msgid "Italic"
+msgstr "Kursiv"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Justified"
+msgstr "Blocksatz"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Keep aspect ratio"
+msgstr "Seitenverhältnis beibehalten"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "L – 7%"
+msgstr "L – 7 %"
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Label"
+msgstr "Etikett"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Label in landscape – text runs along the tape"
+msgstr "Etikett im Querformat – Leserichtung längs zum Band"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Label in portrait – text runs across the tape"
+msgstr "Etikett im Hochformat – Leserichtung quer zum Band"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Label labelwerk starts with (favorite as a template)"
+msgstr "Etikett, mit dem labelwerk startet (Favorit als Vorlage)"
+
+#: src/labelwerk/desktop.py
+msgid "Label printing"
+msgstr "Etikettendruck"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Label too large (barcode contents together {total} characters, at most {limit})"
+msgstr "Etikett zu groß (Barcode-Inhalte zusammen {total} Zeichen, höchstens {limit})"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Label too large (objects together {dots:.0f} million dots, at most {limit})"
+msgstr "Etikett zu groß (Objekte zusammen {dots:.0f} Mio. Druckpunkte, höchstens {limit})"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Label too large ({count} objects, at most {limit})"
+msgstr "Etikett zu groß ({count} Objekte, höchstens {limit})"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Label {label!r} does not fit the printer ({model})."
+msgstr "Etikett {label!r} passt nicht zum Drucker ({model})."
+
+#: src/labelwerk/cli.py
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Label {label!r} does not fit the {model} – see 'labelwerk -m {model} labels'"
+msgstr "Etikett {label!r} passt nicht zum {model} – siehe 'labelwerk -m {model} labels'"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Label {label} does not fit the printer ({model}) – choose another one in the Paper tab"
+msgstr "Etikett {label} passt nicht zum Drucker ({model}) – im Reiter Papier ein anderes wählen"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Label {label} does not fit the {model} – using {new}"
+msgstr "Etikett {label} passt nicht zum {model} – {new} genommen"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Label “{label}” does not fit the printer ({model})."
+msgstr "Etikett „{label}“ passt nicht zum Drucker ({model})."
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Label “{label}” does not fit the {model} – using {new}"
+msgstr "Etikett „{label}“ passt nicht zum {model} – {new} genommen"
+
+#: src/labelwerk/desktop.py
+msgid "Label;Brother;QL;Printer;P-touch;"
+msgstr "Etikett;Label;Brother;QL;Drucker;P-touch;"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Language"
+msgstr "Sprache"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Larger font"
+msgstr "Schrift größer"
+
+#: src/labelwerk/gui/panels/layout.py
+#: src/labelwerk/gui/tools.py
+msgid "Layout"
+msgstr "Layout"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Length"
+msgstr "Länge"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Line"
+msgstr "Linie"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Line art"
+msgstr "Strich"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Line break in “{key}”{where} – lines are separate paragraphs"
+msgstr "Zeilenumbruch in „{key}“{where} – Zeilen sind eigene Absätze"
+
+#: src/labelwerk/render.py
+msgid "Line layout exists only for text objects."
+msgstr "Einen Zeilensatz gibt es nur für Text-Objekte."
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Line width"
+msgstr "Strichstärke der Linie"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Line width of the border must be between {low} and {high} mm"
+msgstr "Strichstärke des Rahmens muss zwischen {low} und {high} mm liegen"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Loaded: {media}"
+msgstr "Eingelegt: {media}"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Loaded: {media} (label {label})"
+msgstr "Eingelegt: {media} (Etikett {label})"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Loaded: {media} (no matching label)"
+msgstr "Eingelegt: {media} (kein passendes Etikett)"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "M – 15%"
+msgstr "M – 15 %"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Many scanners read red poorly"
+msgstr "Rot lesen viele Scanner schlecht"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Margin: number from 0 to {max} mm"
+msgstr "Rand: Zahl von 0 bis {max} mm"
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Margins"
+msgstr "Ränder"
+
+#: src/labelwerk/shortcuts.py
+msgid "Maximize on paper"
+msgstr "Auf Papier maximieren"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Model"
+msgstr "Modell"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Model not recognized – choose a fallback model in the settings"
+msgstr "Modell nicht erkannt – in den Einstellungen ein Ersatzmodell wählen"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Model {model} does not fit the printer {printer} – give cups:NAME for CUPS, zpl:203/300/600 for Zebra, otherwise a Brother QL."
+msgstr "Modell {model} passt nicht zum Drucker {printer} – für CUPS cups:NAME, für Zebra zpl:203/300/600, sonst ein Brother-QL angeben."
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Module"
+msgstr "Modul"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Module width {module!r} invalid – allowed: 1–{limit} dots"
+msgstr "Modulbreite {module!r} ungültig – erlaubt: 1–{limit} Druckpunkte"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move down (0.1 mm)"
+msgstr "Nach unten (0,1 mm)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move down (1 mm)"
+msgstr "Nach unten (1 mm)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move left (0.1 mm)"
+msgstr "Nach links (0,1 mm)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move left (1 mm)"
+msgstr "Nach links (1 mm)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move right (0.1 mm)"
+msgstr "Nach rechts (0,1 mm)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move right (1 mm)"
+msgstr "Nach rechts (1 mm)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move up (0.1 mm)"
+msgstr "Nach oben (0,1 mm)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Move up (1 mm)"
+msgstr "Nach oben (1 mm)"
+
+#: src/labelwerk/clipart.py
+msgid "My symbols"
+msgstr "Eigene"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "NEW"
+msgstr "NEU"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "NONE"
+msgstr "KEINE"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "NUMBERING"
+msgstr "NUMMERIERUNG"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Name"
+msgstr "Name"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Name of the favorite:"
+msgstr "Name des Favoriten:"
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Network printer {name}: address “{host}” invalid – only an IP address or name, without “tcp://” and port"
+msgstr "Netzwerkdrucker {name}: Adresse „{host}“ ungültig – nur IP-Adresse oder Name, ohne „tcp://“ und Port"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Network printer {printer} not reachable ({reason}) – switched on, in the same network, address correct?"
+msgstr "Netzwerkdrucker {printer} nicht erreichbar ({reason}) – eingeschaltet, im selben Netz, Adresse richtig?"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Network printers"
+msgstr "Netzwerkdrucker"
+
+#: src/labelwerk/gui/settings_dialog.py
+#: src/labelwerk/shortcuts.py
+msgid "New label"
+msgstr "Neues Etikett"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Next row on the canvas"
+msgstr "Nächste Zeile auf der Arbeitsfläche"
+
+#: src/labelwerk/cli.py
+msgid ""
+"No CUPS queue found (set up the printer in the printer settings).\n"
+"Specify with -p cups:NAME"
+msgstr ""
+"Keine CUPS-Warteschlange gefunden (Drucker in der Druckerverwaltung einrichten).\n"
+"Angeben mit -p cups:NAME"
+
+#: src/labelwerk/cli.py
+msgid ""
+"No Zebra printer found.\n"
+"Specify with -p zpl+file:///dev/usb/lpN or -p zpl+tcp://IP and -m zpl:203"
+msgstr ""
+"Kein Zebra-Drucker gefunden.\n"
+"Angeben mit -p zpl+file:///dev/usb/lpN bzw. -p zpl+tcp://IP und -m zpl:203"
+
+#: src/labelwerk/media.py
+msgid "No answer from the printer to the status request."
+msgstr "Keine Antwort vom Drucker auf die Statusabfrage."
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "No border"
+msgstr "Kein"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "No favorites yet – choose a symbol and press ★."
+msgstr "Noch keine Favoriten – Symbol wählen und ★ drücken."
+
+#: src/labelwerk/gui/panels/file.py
+msgid "No favorites yet – design a label and press “+ CURRENT”."
+msgstr "Noch keine Favoriten – ein Etikett gestalten und „+ AKTUELL“ drücken."
+
+#: src/labelwerk/gui/main_window.py
+msgid "No image in the clipboard."
+msgstr "Kein Bild in der Zwischenablage."
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "No label for the loaded roll ({media}) on the {model}."
+msgstr "Kein Etikett für die eingelegte Rolle ({media}) beim {model}."
+
+#: src/labelwerk/printer.py
+msgid "No labels to print"
+msgstr "Keine Etiketten zum Drucken"
+
+#: src/labelwerk/cli.py
+msgid ""
+"No network printer configured (GUI settings).\n"
+"Specify the address with -p tcp://IP"
+msgstr ""
+"Kein Netzwerkdrucker eingetragen (Einstellungen der GUI).\n"
+"Adresse angeben mit -p tcp://IP"
+
+#: src/labelwerk/gui/symbol_dialog.py
+#, python-brace-format
+msgid ""
+"No own symbols yet. Put SVG or PNG files into this folder (subfolders are not read):\n"
+"{path}"
+msgstr ""
+"Noch keine eigenen Symbole. SVG- oder PNG-Dateien in diesen Ordner legen (Unterordner werden nicht gelesen):\n"
+"{path}"
+
+#: src/labelwerk/media.py
+#: src/labelwerk/printer.py
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "No permission for {device} – is the user in group 'lp'?"
+msgstr "Keine Berechtigung für {device} – Benutzer in Gruppe 'lp'?"
+
+#: src/labelwerk/gui/main_window.py
+msgid "No printer for this label – choose a printer in the status bar."
+msgstr "Kein Drucker für dieses Etikett – in der Statusleiste einen Drucker wählen."
+
+#: src/labelwerk/gui/main_window.py
+msgid "No printer found"
+msgstr "Kein Drucker gefunden"
+
+#: src/labelwerk/cli.py
+msgid "No printer found."
+msgstr "Kein Drucker gefunden."
+
+#: src/labelwerk/cli.py
+#: src/labelwerk/printer.py
+msgid "No roll loaded."
+msgstr "Keine Rolle eingelegt."
+
+#: src/labelwerk/gui/main_window.py
+msgid "No row selected – nothing printed."
+msgstr "Keine Zeile gewählt – nichts gedruckt."
+
+#: src/labelwerk/gui/panels/series.py
+msgid "No series"
+msgstr "Keine Serie"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Not a Zebra address: {uri}"
+msgstr "Keine Zebra-Adresse: {uri}"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Note: {tools} did not work – the file association may only apply after logging in again."
+msgstr "Hinweis: {tools} hat nicht geklappt – Dateizuordnung gilt ggf. erst nach neuer Anmeldung."
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Nothing found."
+msgstr "Nichts gefunden."
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Nothing inserted yet."
+msgstr "Noch nichts eingefügt."
+
+#: src/labelwerk/cli.py
+msgid "Nothing to remove."
+msgstr "Nichts zu entfernen."
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Numbering"
+msgstr "Nummerierung"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering count: 1 to {limit}"
+msgstr "Anzahl der Nummerierung: 1 bis {limit}"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering start: whole number up to {limit}"
+msgstr "Start der Nummerierung: ganze Zahl bis {limit}"
+
+#: src/labelwerk/series.py
+msgid "Numbering step must not be 0"
+msgstr "Schritt der Nummerierung darf nicht 0 sein"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering step: whole number up to {limit}"
+msgstr "Schritt der Nummerierung: ganze Zahl bis {limit}"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering values too large (at most {limit})"
+msgstr "Zahlen der Nummerierung zu groß (höchstens {limit})"
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "Numbers without a file: column “{column}”"
+msgstr "Zahlen ohne Datei: Spalte „{column}“"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "OPEN FOLDER"
+msgstr "ORDNER ÖFFNEN"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "OPEN …"
+msgstr "ÖFFNEN …"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "ORIGINAL SIZE 1:1"
+msgstr "ORIGINALGRÖSSE 1:1"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Object extends beyond the label"
+msgstr "Objekt ragt über das Etikett hinaus"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Object sticks out"
+msgstr "Objekt ragt hinaus"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Off: images that are too large are reduced – saves tape"
+msgstr "Aus: zu große Bilder werden verkleinert – spart Band"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "On round labels every border becomes a circle."
+msgstr "Auf runden Etiketten wird jeder Rahmen ein Kreis."
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Only at the end"
+msgstr "Nur am Ende"
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Only changeable with a fixed frame size"
+msgstr "Nur mit fester Rahmengröße änderbar"
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Only for text objects, not for {type}."
+msgstr "Nur für Text-Objekte, nicht für {type}."
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Only needed if labelwerk does not recognize the model (then applies, and without a connected printer)"
+msgstr "Nur nötig, wenn labelwerk das Modell nicht erkennt (gilt dann und ohne angeschlossenen Drucker)"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Open as new label"
+msgstr "Öffnen als neues Etikett"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Open at startup"
+msgstr "Beim Start öffnen"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Open folder"
+msgstr "Ordner öffnen"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Open label"
+msgstr "Etikett öffnen"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Open the folder for your own symbols (created if needed)"
+msgstr "Ordner für eigene Symbole öffnen (wird angelegt)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Open …"
+msgstr "Öffnen …"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Opened: {name}"
+msgstr "Geöffnet: {name}"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Opened: {name} – {error}"
+msgstr "Geöffnet: {name} – {error}"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Order"
+msgstr "Reihenfolge"
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Orientation"
+msgstr "Ausrichtung"
+
+#: src/labelwerk/files.py
+msgid "PDF is encrypted"
+msgstr "PDF ist verschlüsselt"
+
+#: src/labelwerk/cli.py
+msgid "PDF page (default 1)"
+msgstr "PDF-Seite (Standard 1)"
+
+#: src/labelwerk/cli.py
+msgid "PDF, PNG or JPG"
+msgstr "PDF, PNG oder JPG"
+
+#: src/labelwerk/gui/main_window.py
+msgid "PRINT"
+msgstr "DRUCKEN"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Pad with zeros to this many digits (0 = no padding)"
+msgstr "Mit Nullen auf so viele Stellen auffüllen (0 = nicht)"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Padding"
+msgstr "Innenabstand"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Padding of the border must be between {low} and {high} mm"
+msgstr "Innenabstand des Rahmens muss zwischen {low} und {high} mm liegen"
+
+#: src/labelwerk/files.py
+msgid "Page must be at least 1."
+msgstr "Seite muss mindestens 1 sein."
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/tools.py
+msgid "Paper"
+msgstr "Papier"
+
+#: src/labelwerk/shortcuts.py
+msgid "Paste"
+msgstr "Einfügen"
+
+#: src/labelwerk/zpl.py
+msgid "Peel off (dispenser only)"
+msgstr "Ablösen (nur mit Spender)"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Photo"
+msgstr "Foto"
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/panels/text.py
+msgid "Position (mm)"
+msgstr "Position (mm)"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Preparing {current}/{total} …"
+msgstr "Bereite {current}/{total} vor …"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Preview"
+msgstr "Vorschau"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Preview cannot be saved: {path} ({error})"
+msgstr "Vorschau kann nicht gespeichert werden: {path} ({error})"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Preview: {path} ({width} × {height} mm)"
+msgstr "Vorschau: {path} ({width} × {height} mm)"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Previous row on the canvas"
+msgstr "Vorige Zeile auf der Arbeitsfläche"
+
+#: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/shortcuts.py
+msgid "Print"
+msgstr "Drucken"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Print series"
+msgstr "Serie drucken"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Print size from the resolution of the image (e.g. stamp, code)"
+msgstr "Druckgröße aus der Auflösung des Bilds (z. B. Briefmarke, Code)"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Print the content readable below the barcode"
+msgstr "Inhalt unter dem Strichcode lesbar drucken"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Print {count} label?"
+msgid_plural "Print {count} labels?"
+msgstr[0] "{count} Etikett drucken?"
+msgstr[1] "{count} Etiketten drucken?"
+
+#: src/labelwerk/gui/panels/file.py
+#, python-brace-format
+msgid "Print “{name}”"
+msgstr "„{name}“ drucken"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Printed ✓"
+msgstr "Gedruckt ✓"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Printer"
+msgstr "Drucker"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Printer error: {err}"
+msgstr "Druckerfehler: {err}"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Printer model"
+msgstr "Druckermodell"
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Printer not found: {printer}"
+msgstr "Drucker nicht gefunden: {printer}"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid ""
+"Printer not found: {printer}\n"
+"Check: switched on, Editor Lite LED off, 'lsusb', 'lsmod | grep usblp'."
+msgstr ""
+"Drucker nicht gefunden: {printer}\n"
+"Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', 'lsmod | grep usblp'."
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid ""
+"Printer not found: {printer}\n"
+"Check: switched on, Editor Lite LED off, 'lsusb'."
+msgstr ""
+"Drucker nicht gefunden: {printer}\n"
+"Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'."
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Printer not reachable: {error}"
+msgstr "Drucker nicht erreichbar: {error}"
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Printer reports: {errors}"
+msgstr "Drucker meldet: {errors}"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Printer without cutter – separate the labels by hand"
+msgstr "Drucker ohne Abschneider – Etiketten von Hand abtrennen"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Printer {printer} not ready ({reason}) – in use or busy? Wait a moment or switch it off and on."
+msgstr "Drucker {printer} nicht bereit ({reason}) – belegt oder gerade beschäftigt? Kurz warten bzw. aus- und einschalten."
+
+#: src/labelwerk/gui/main_window.py
+msgid "Printing – please wait."
+msgstr "Druck läuft – bitte warten."
+
+#: src/labelwerk/gui/main_window.py
+msgid "Printing …"
+msgstr "Drucke …"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Printing … {done} of {total}"
+msgstr "Drucke … {done} von {total}"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Q – 25%"
+msgstr "Q – 25 %"
+
+#: src/labelwerk/barcodes.py
+msgid "QR code"
+msgstr "QR-Code"
+
+#: src/labelwerk/cli.py
+msgid "Querying the roll only works with printers via USB."
+msgstr "Rolle abfragen geht nur bei Druckern per USB."
+
+#: src/labelwerk/gui/panels/barcode.py
+#, python-brace-format
+msgid "Quiet zone: leave {mm} mm free all around"
+msgstr "Ruhezone: ringsum {mm} mm frei lassen"
+
+#: src/labelwerk/gui/panels/barcode.py
+#, python-brace-format
+msgid "Quiet zone: leave {mm} mm free on the left and right each"
+msgstr "Ruhezone: links und rechts je {mm} mm frei lassen"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "RED"
+msgstr "ROT"
+
+#: src/labelwerk/gui/panels/series.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "REMOVE"
+msgstr "ENTFERNEN"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Recently opened"
+msgstr "Zuletzt geöffnet"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Recently used"
+msgstr "Zuletzt verwendet"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Red only on the 62 mm red/black label (DK-22251) with a QL-8xx"
+msgstr "Rot nur auf dem Etikett 62 mm Rot/Schwarz (DK-22251) mit einem QL-8xx"
+
+#: src/labelwerk/shortcuts.py
+msgid "Redo"
+msgstr "Wiederherstellen"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Remove from favorites"
+msgstr "Aus Favoriten entfernen"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Remove the series from the label (placeholders stay)"
+msgstr "Serie aus dem Etikett nehmen (Platzhalter bleiben stehen)"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Removed: {path}"
+msgstr "Entfernt: {path}"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Rename …"
+msgstr "Umbenennen …"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Replace favorite"
+msgstr "Favorit ersetzen"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Replace file"
+msgstr "Datei ersetzen"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Reset all"
+msgstr "Alle zurücksetzen"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Resize"
+msgstr "Größe ändern"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Resolution of Zebra printers on USB, in case labelwerk does not detect it correctly (otherwise 203 dpi)"
+msgstr "Auflösung der Zebra-Drucker am USB, falls labelwerk sie nicht richtig erkennt (sonst 203 dpi)"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Roll: none loaded"
+msgstr "Rolle: keine eingelegt"
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} – no matching label"
+msgstr "Rolle: {media} – kein passendes Etikett"
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} – selection does not match"
+msgstr "Rolle: {media} – Auswahl passt nicht"
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} ✓"
+msgstr "Rolle: {media} ✓"
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} ✓ – label adjusted"
+msgstr "Rolle: {media} ✓ – Etikett angepasst"
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/panels/layout.py
+msgid "Rotate"
+msgstr "Drehen"
+
+#: src/labelwerk/shortcuts.py
+msgid "Rotate 90° left"
+msgstr "90° nach links drehen"
+
+#: src/labelwerk/shortcuts.py
+msgid "Rotate 90° right"
+msgstr "90° nach rechts drehen"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Rotate if the image only fits 1:1 when rotated"
+msgstr "Drehen, wenn das Bild nur gedreht 1:1 passt"
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Rotation {rotate!r} not possible – allowed: auto, 0, 90, 180, 270"
+msgstr "Drehung {rotate!r} nicht möglich – erlaubt: auto, 0, 90, 180, 270"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Round"
+msgstr "Rund"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Rounded"
+msgstr "Abgerundet"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Row {rows} extends beyond the label and will be cut off. Print anyway?"
+msgid_plural "Rows {rows} extend beyond the label and will be cut off. Print anyway?"
+msgstr[0] "Zeile {rows} ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
+msgstr[1] "Zeilen {rows} ragen über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "Row {row}/{total}"
+msgstr "Zeile {row}/{total}"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Row {row}: {message}"
+msgstr "Zeile {row}: {message}"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Rows"
+msgstr "Zeilen"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "SAVE"
+msgstr "SPEICHERN"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "SAVE AS …"
+msgstr "SPEICHERN UNTER …"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "SCREENSHOT"
+msgstr "BILDSCHIRMFOTO"
+
+#: src/labelwerk/gui/main_window.py
+msgid "SETTINGS"
+msgstr "EINSTELLUNGEN"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "SYMBOL"
+msgstr "SYMBOL"
+
+#: src/labelwerk/clipart.py
+msgid "Safety"
+msgstr "Sicherheit"
+
+#: src/labelwerk/shortcuts.py
+msgid "Same height"
+msgstr "Gleiche Höhe"
+
+#: src/labelwerk/shortcuts.py
+msgid "Same size"
+msgstr "Gleiche Größe"
+
+#: src/labelwerk/shortcuts.py
+msgid "Same width"
+msgstr "Gleiche Breite"
+
+#: src/labelwerk/shortcuts.py
+msgid "Save"
+msgstr "Speichern"
+
+#: src/labelwerk/shortcuts.py
+msgid "Save as …"
+msgstr "Speichern unter …"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Save label"
+msgstr "Etikett speichern"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Save the current label as a favorite"
+msgstr "Aktuelles Etikett als Favorit speichern"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Saved: {name}"
+msgstr "Gespeichert: {name}"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Scale the text automatically so that it fits"
+msgstr "Text automatisch so skalieren, dass er passt"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Scope"
+msgstr "Bereich"
+
+#: src/labelwerk/gui/image_import.py
+msgid "Screenshot"
+msgstr "Bildschirmfoto"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed"
+msgstr "Bildschirmfoto fehlgeschlagen"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – cannot subscribe to the answer of the portal"
+msgstr "Bildschirmfoto fehlgeschlagen – Antwort des Portals nicht abonnierbar"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – error of the portal"
+msgstr "Bildschirmfoto fehlgeschlagen – Fehler des Portals"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – no connection to the session bus"
+msgstr "Bildschirmfoto fehlgeschlagen – keine Verbindung zum Sitzungsbus"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – no image file received"
+msgstr "Bildschirmfoto fehlgeschlagen – keine Bilddatei erhalten"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – no screenshot portal found"
+msgstr "Bildschirmfoto fehlgeschlagen – kein Bildschirmfoto-Portal gefunden"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – not allowed by the system"
+msgstr "Bildschirmfoto fehlgeschlagen – vom System nicht erlaubt"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – rejected or cancelled by the system"
+msgstr "Bildschirmfoto fehlgeschlagen – vom System abgelehnt oder abgebrochen"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – the portal does not answer"
+msgstr "Bildschirmfoto fehlgeschlagen – das Portal antwortet nicht"
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – unexpected answer from the portal"
+msgstr "Bildschirmfoto fehlgeschlagen – unerwartete Antwort des Portals"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Screenshot not available (no XDG portal) – copy it to the clipboard with the system tool and paste it with Ctrl+V"
+msgstr "Bildschirmfoto nicht verfügbar (kein XDG-Portal) – mit dem System-Werkzeug in die Zwischenablage kopieren und mit Strg+V einfügen"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Screenshot: {error}"
+msgstr "Bildschirmfoto: {error}"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Search … (e.g. earth, fragile, house)"
+msgstr "Suchen … (z. B. Erde, zerbrechlich, Haus)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Select all"
+msgstr "Alles auswählen"
+
+#: src/labelwerk/shortcuts.py
+msgid "Select tool"
+msgstr "Werkzeug Auswahl"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Selected printer not found – switch it on or choose another one in the status bar."
+msgstr "Gewählter Drucker nicht gefunden – einschalten oder in der Statusleiste einen anderen wählen."
+
+#: src/labelwerk/shortcuts.py
+msgid "Send backward"
+msgstr "Nach hinten"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Sending to {path} aborted after {sent} bytes ({reason})"
+msgstr "Senden an {path} abgebrochen nach {sent} Bytes ({reason})"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Sent ✓ (the printer reports no status)"
+msgstr "Gesendet ✓ (der Drucker meldet keinen Status zurück)"
+
+#: src/labelwerk/gui/panels/series.py
+#: src/labelwerk/gui/tools.py
+msgid "Series"
+msgstr "Serie"
+
+#: src/labelwerk/gui/tools.py
+msgid "Series from a table or numbering"
+msgstr "Serien aus Tabelle oder Nummerierung"
+
+#: src/labelwerk/gui/file_session.py
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Series: {error}"
+msgstr "Serie: {error}"
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Setting 'font_size' invalid ({value!r}) – automatic."
+msgstr "Einstellung 'font_size' ungültig ({value!r}) – automatisch."
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Setting 'shortcuts' invalid ({value!r}) – default shortcuts active."
+msgstr "Einstellung 'shortcuts' ungültig ({value!r}) – Standardkürzel aktiv."
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Setting {key!r} invalid ({value!r}) – using default {default!r}."
+msgstr "Einstellung {key!r} ungültig ({value!r}) – Standardwert {default!r} aktiv."
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Setting {key!r}: invalid entries discarded."
+msgstr "Einstellung {key!r}: ungültige Einträge verworfen."
+
+#: src/labelwerk/gui/settings_dialog.py
+#: src/labelwerk/shortcuts.py
+msgid "Settings"
+msgstr "Einstellungen"
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Settings could not be saved ({path}): {reason}"
+msgstr "Einstellungen konnten nicht gespeichert werden ({path}): {reason}"
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Settings not readable ({path}): {error} – using defaults."
+msgstr "Einstellungen nicht lesbar ({path}): {error} – Standardwerte aktiv."
+
+#: src/labelwerk/gui/main_window.py
+msgid "Settings saved – they apply to new labels."
+msgstr "Einstellungen gespeichert – gelten für neue Etiketten."
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Sheet of the Excel file"
+msgstr "Blatt der Excel-Datei"
+
+#: src/labelwerk/clipart.py
+msgid "Shipping"
+msgstr "Versand"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Shortcut"
+msgstr "Kürzel"
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut assigned twice: {keys} ({first}, {second}) – “{second}” has no shortcut now."
+msgstr "Tastenkürzel doppelt belegt: {keys} ({first}, {second}) – „{second}“ ohne Kürzel."
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for unknown action {action!r} ignored."
+msgstr "Tastenkürzel für unbekannte Aktion {action!r} ignoriert."
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for {action!r} invalid ({keys!r}) – default {default!r} active."
+msgstr "Tastenkürzel für {action!r} ungültig ({keys!r}) – Standard {default!r} aktiv."
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for {action!r} invalid ({keys}) – Esc, Enter and Tab cannot be assigned; default {default!r} active."
+msgstr "Tastenkürzel für {action!r} ungültig ({keys}) – Esc, Enter und Tab sind nicht belegbar; Standard {default!r} aktiv."
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for {action!r} is fixed ({default}) – setting ignored."
+msgstr "Tastenkürzel für {action!r} ist fest ({default}) – Einstellung ignoriert."
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Shortcuts"
+msgstr "Tastenkürzel"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Shortcuts assigned twice – change one to save:"
+msgstr "Tastenkürzel doppelt belegt – zum Speichern eines ändern:"
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Single"
+msgstr "Einfach"
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/panels/image.py
+msgid "Size"
+msgstr "Größe"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Smaller font"
+msgstr "Schrift kleiner"
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/panels/series.py
+msgid "Source"
+msgstr "Quelle"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Start"
+msgstr "Start"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Start favorite “{name}” not found – empty label"
+msgstr "Start-Favorit „{name}“ nicht gefunden – leeres Etikett"
+
+#: src/labelwerk/shortcuts.py
+msgid "Start text editing (Enter)"
+msgstr "Schreibmodus starten (Enter)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Start text editing (selected text)"
+msgstr "Schreibmodus starten (Text der Auswahl)"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Start zoom"
+msgstr "Startzoom"
+
+#: src/labelwerk/cli.py
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Status: {outcome}"
+msgstr "Status: {outcome}"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Step"
+msgstr "Schritt"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Step to the next number (not 0)"
+msgstr "Abstand zur nächsten Zahl (nicht 0)"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Style"
+msgstr "Stil"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Supported: {models}, Zebra zpl:203/300/600 (untested), CUPS queues cups:NAME (untested)"
+msgstr "Unterstützt: {models}, Zebra zpl:203/300/600 (ungeprüft), CUPS-Warteschlangen cups:NAME (ungeprüft)"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Swap black and white"
+msgstr "Schwarz und Weiß tauschen"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Symbol library unreadable: {error}"
+msgstr "Symbol-Bibliothek nicht lesbar: {error}"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Symbol: {error}"
+msgstr "Symbol: {error}"
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Symbol: {name}"
+msgstr "Symbol: {name}"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "TABLE …"
+msgstr "TABELLE …"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Table for the series"
+msgstr "Tabelle für die Serie"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Table not found: {path}"
+msgstr "Tabelle nicht gefunden: {path}"
+
+#: src/labelwerk/gui/main_window.py
+msgid "Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"
+msgstr "Tabellen (*.csv *.xlsx *.xlsm *.tsv *.txt);;Alle Dateien (*)"
+
+#: src/labelwerk/zpl.py
+msgid "Tear off"
+msgstr "Abreißen"
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/gui/tools.py
+msgid "Text"
+msgstr "Text"
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Text alignment"
+msgstr "Textposition"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Text does not fit on label {label_id!r} at font size {size} pt (at most {max_size} pt)."
+msgstr "Text passt nicht auf Etikett {label_id!r} bei Schriftgröße {size} pt (höchstens {max_size} pt)."
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Text does not fit on label {label_id!r} – not even at the smallest font size."
+msgstr "Text passt nicht auf Etikett {label_id!r} – auch nicht in der kleinsten Schriftgröße."
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Text editing"
+msgstr "Schreibmodus"
+
+#: src/labelwerk/layout.py
+msgid "Text with automatic font size needs the effective base size (base_pt) for scaling."
+msgstr "Text mit automatischer Schriftgröße braucht die wirksame Grundgröße (base_pt) zum Skalieren."
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "The PDF has only {count} page."
+msgid_plural "The PDF has only {count} pages."
+msgstr[0] "PDF hat nur {count} Seite(n)."
+msgstr[1] "PDF hat nur {count} Seite(n)."
+
+#: src/labelwerk/files.py
+msgid "The file has no printable content."
+msgstr "Datei enthält keinen druckbaren Inhalt."
+
+#: src/labelwerk/gui/main_window.py
+msgid "The label is empty. Print anyway?"
+msgstr "Das Etikett ist leer. Trotzdem drucken?"
+
+#: src/labelwerk/printer.py
+msgid "The label roll is empty."
+msgstr "Etikettenrolle ist leer."
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "The loaded roll does not match the label {label!r} – check the roll or choose another label."
+msgstr "Eingelegte Rolle passt nicht zum Etikett {label!r} – Rolle prüfen oder anderes Etikett wählen."
+
+#: src/labelwerk/gui/main_window.py
+msgid "The table has changed and was read again – check the selection and print again."
+msgstr "Tabelle wurde geändert und neu eingelesen – Auswahl prüfen und erneut drucken."
+
+#: src/labelwerk/gui/main_window.py
+msgid "The table has no rows – nothing printed."
+msgstr "Tabelle hat keine Zeilen – nichts gedruckt."
+
+#: src/labelwerk/printer.py
+msgid "The tape cannot be fed – roll empty or loaded incorrectly?"
+msgstr "Band kann nicht transportiert werden – Rolle leer oder falsch eingelegt?"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Theme"
+msgstr "Design"
+
+#: src/labelwerk/files.py
+msgid "There is no printable content between the crop marks."
+msgstr "Zwischen den Schnittmarken ist kein druckbarer Inhalt."
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Thick-thin"
+msgstr "Dick-dünn"
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Threshold"
+msgstr "Schwelle"
+
+#: src/labelwerk/imaging.py
+#, python-brace-format
+msgid "Threshold must be a whole number from 0 to 255, not {threshold!r}."
+msgstr "Schwelle muss eine ganze Zahl von 0 bis 255 sein, nicht {threshold!r}."
+
+#: src/labelwerk/gui/main_window.py
+msgid "Tools"
+msgstr "Werkzeuge"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Type"
+msgstr "Art"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Type of barcode – for the selected one or the next one"
+msgstr "Art des Barcodes – für den gewählten bzw. den nächsten"
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/shortcuts.py
+msgid "Underline"
+msgstr "Unterstrichen"
+
+#: src/labelwerk/shortcuts.py
+msgid "Undo"
+msgstr "Rückgängig"
+
+#: src/labelwerk/gui/media_worker.py
+#, python-brace-format
+msgid "Unexpected error while checking the roll: {error}"
+msgstr "Unerwarteter Fehler beim Prüfen der Rolle: {error}"
+
+#: src/labelwerk/gui/print_worker.py
+#, python-brace-format
+msgid "Unexpected error while printing: {error}"
+msgstr "Unerwarteter Fehler beim Drucken: {error}"
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Unintelligible answer from the printer: {error}"
+msgstr "Unverständliche Antwort vom Drucker: {error}"
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Unknown alignment {mode!r} – allowed: {allowed}"
+msgstr "Unbekannte Ausrichtung {mode!r} – erlaubt: {allowed}"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Unknown barcode type {kind!r}"
+msgstr "Unbekannte Barcode-Art {kind!r}"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown border style {style!r} – allowed: {allowed}"
+msgstr "Unbekannte Rahmenart {style!r} – erlaubt: {allowed}"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown color {color!r} – allowed: black, red"
+msgstr "Unbekannte Farbe {color!r} – erlaubt: schwarz, rot (black, red)"
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "Unknown column: {columns}"
+msgid_plural "Unknown columns: {columns}"
+msgstr[0] "Unbekannte Spalte: {columns}"
+msgstr[1] "Unbekannte Spalten: {columns}"
+
+#: src/labelwerk/imaging.py
+#, python-brace-format
+msgid "Unknown conversion {mode!r} – allowed: line art, photo (line, photo)"
+msgstr "Unbekannte Umwandlung {mode!r} – erlaubt: Strich, Foto (line, photo)"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Unknown cut {cut!r} – allowed: {allowed}"
+msgstr "Unbekannter Schnitt {cut!r} – erlaubt: {allowed}"
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Unknown cut {mode!r} – allowed: {allowed}"
+msgstr "Unbekannter Schnitt {mode!r} – erlaubt: {allowed}"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Unknown error correction {error!r} – allowed: L, M, Q, H"
+msgstr "Unbekannte Fehlerkorrektur {error!r} – erlaubt: L, M, Q, H"
+
+#: src/labelwerk/labels.py
+#, python-brace-format
+msgid "Unknown label: {label_id!r}"
+msgstr "Unbekanntes Etikett: {label_id!r}"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Unknown label{where}: {value}"
+msgstr "Etikett{where} unbekannt: {value}"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Unknown mode {mode!r} – allowed: {allowed}"
+msgstr "Unbekannter Modus {mode!r} – erlaubt: {allowed}"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Unknown object type{where}: {kind}"
+msgstr "Objektart{where} unbekannt: {kind}"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown orientation {orientation!r} – allowed: horizontal, vertical"
+msgstr "Unbekannte Ausrichtung {orientation!r} – erlaubt: horizontal, vertical"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Unknown printer model {model!r} – allowed: {models}, zpl:203/300/600 or cups:NAME"
+msgstr "Unbekanntes Druckermodell {model!r} – erlaubt: {models}, zpl:203/300/600 oder cups:NAME"
+
+#: src/labelwerk/printers.py
+#, python-brace-format
+msgid "Unknown printer model: {model!r}"
+msgstr "Unbekanntes Druckermodell: {model!r}"
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Unknown roll (code 0x{code:02X})"
+msgstr "Unbekannte Rolle (Code 0x{code:02X})"
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Unknown roll: {media}"
+msgstr "Unbekannte Rolle: {media}"
+
+#: src/labelwerk/barcodes.py
+#: src/labelwerk/layout.py
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees"
+msgstr "Unbekannte Drehung {rotation!r} – erlaubt: 0, 90, 180, 270 Grad"
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Unknown size matching {mode!r} – allowed: {allowed}"
+msgstr "Unbekannte Größenangleichung {mode!r} – erlaubt: {allowed}"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown text alignment {align!r} – allowed: left, center, right, justify"
+msgstr "Unbekannte Textposition {align!r} – erlaubt: links, zentriert, rechts, Blocksatz (left, center, right, justify)"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Unsaved changes"
+msgstr "Ungespeicherte Änderungen"
+
+#: src/labelwerk/gui/file_session.py
+msgid "Untitled"
+msgstr "Unbenannt"
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Value for “crop”{where} is not inside the image: {crop}"
+msgstr "Wert für „crop“{where} liegt nicht im Bild: {crop}"
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Vector image could not be rasterized ({got_w} × {got_h} instead of {width} × {height} pixels)."
+msgstr "Vektorbild konnte nicht gerastert werden ({got_w} × {got_h} statt {width} × {height} Pixel)."
+
+#: src/labelwerk/gui/image_import.py
+msgid "Vector image refers to other files – they are not saved with it."
+msgstr "Vektorbild verweist auf andere Dateien – die werden nicht mitgespeichert."
+
+#: src/labelwerk/render.py
+msgid "Vector image: crop enlarged too much – please scale it down or turn cropping off."
+msgstr "Vektorbild: Ausschnitt zu stark vergrößert – bitte kleiner skalieren oder den Zuschnitt ausschalten."
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Vertical"
+msgstr "Vertikal"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "View"
+msgstr "Ansicht"
+
+#: src/labelwerk/gui/panels/position.py
+msgid "W"
+msgstr "B"
+
+#: src/labelwerk/gui/panels/series.py
+msgid "When printing the series: cut after each label or only at the end (continuous tape: a few mm of feed remain between the labels, without a separator mark)"
+msgstr "Beim Drucken der Serie: nach jedem Etikett schneiden oder nur am Ende (Endlosband: zwischen den Etiketten bleiben einige mm Vorschub, ohne Trennmarke)"
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Width of the frame"
+msgstr "Breite des Rahmens"
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Width of the narrowest bar or of one QR square – in whole dots (0.085 mm), so the code stays readable"
+msgstr "Breite des schmalsten Strichs bzw. eines QR-Quadrats – in ganzen Druckpunkten (0,085 mm), damit der Code lesbar bleibt"
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "With automatic length the label grows along – the object keeps the same margin at both ends"
+msgstr "Bei automatischer Länge wächst das Etikett mit – das Objekt sitzt mit gleichem Rand an beiden Enden"
+
+#: src/labelwerk/gui/panels/barcode.py
+#, python-brace-format
+msgid "With check digit: {code}"
+msgstr "Mit Prüfziffer: {code}"
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Zebra (ZPL) {dpi} dpi – untested"
+msgstr "Zebra (ZPL) {dpi} dpi – ungeprüft"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer does not accept data ({sent} bytes sent) – paper, ribbon, paused?"
+msgstr "Zebra-Drucker nimmt keine Daten an ({sent} Bytes gesendet) – Papier, Farbband, Pause?"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer not found: {path} – switched on, cable?"
+msgstr "Zebra-Drucker nicht gefunden: {path} – eingeschaltet, Kabel?"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer not reachable: {path} ({reason})"
+msgstr "Zebra-Drucker nicht erreichbar: {path} ({reason})"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer {host} not reachable ({reason}) – switched on, in the same network, address correct?"
+msgstr "Zebra-Drucker {host} nicht erreichbar ({reason}) – eingeschaltet, im selben Netz, Adresse richtig?"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Zebra resolution"
+msgstr "Zebra-Auflösung"
+
+#: src/labelwerk/shortcuts.py
+msgid "Zoom in"
+msgstr "Vergrößern (Zoom)"
+
+#: src/labelwerk/shortcuts.py
+msgid "Zoom out"
+msgstr "Verkleinern (Zoom)"
+
+#: src/labelwerk/storage.py
+msgid "access error"
+msgstr "Fehler beim Zugriff"
+
+#: src/labelwerk/cli.py
+msgid "add labelwerk-gui to the launcher (Super key)"
+msgstr "labelwerk-gui im Starter (Super-Taste) eintragen"
+
+#: src/labelwerk/cli.py
+msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
+msgstr "auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (Warteschlange, siehe 'labelwerk printers'), zpl+file:///dev/usb/lpN bzw. zpl+tcp://IP (Zebra, mit -m zpl:203/300/600)"
+
+#: src/labelwerk/cli.py
+msgid "auto (default: detected, otherwise from the settings) or e.g. QL-700, zpl:300 (Zebra), cups:NAME; see 'labelwerk printers'"
+msgstr "auto (Standard: erkannt, sonst aus den Einstellungen) oder z. B. QL-700, zpl:300 (Zebra), cups:NAME; siehe 'labelwerk printers'"
+
+#: src/labelwerk/cli.py
+msgid "auto (default: rotate only if needed) or degrees clockwise"
+msgstr "auto (Standard: nur drehen wenn nötig) oder Grad im Uhrzeigersinn"
+
+#: src/labelwerk/cli.py
+msgid "bold (default) or --no-bold"
+msgstr "fett (Standard) bzw. --no-bold"
+
+#: src/labelwerk/cli.py
+msgid "default: from the printer (tcp:// → network)"
+msgstr "Standard: aus dem Drucker (tcp:// → network)"
+
+#: src/labelwerk/cli.py
+msgid "do not cut (Brother; for CUPS/Zebra the driver or the mode in the GUI settings decides)"
+msgstr "nicht schneiden (Brother; bei CUPS/Zebra stellt das der Treiber bzw. der Modus in den Einstellungen der GUI ein)"
+
+#: src/labelwerk/files.py
+msgid "file is damaged or incomplete"
+msgstr "Datei ist beschädigt oder unvollständig"
+
+#: src/labelwerk/storage.py
+msgid "folder missing"
+msgstr "Ordner fehlt"
+
+#: src/labelwerk/cli.py
+msgid "font family, e.g. 'Liberation Sans' (see 'labelwerk fonts')"
+msgstr "Schriftfamilie, z. B. 'Liberation Sans' (siehe 'labelwerk fonts')"
+
+#: src/labelwerk/files.py
+msgid "image has too many pixels"
+msgstr "Bild hat zu viele Pixel"
+
+#: src/labelwerk/files.py
+#: src/labelwerk/storage.py
+msgid "is a folder"
+msgstr "ist ein Ordner"
+
+#: src/labelwerk/cli.py
+msgid "italic"
+msgstr "kursiv"
+
+#: src/labelwerk/cli.py
+msgid "label, e.g. 62, or auto (roll loaded in the printer); default from the settings"
+msgstr "Etikett, z. B. 62, oder auto (eingelegte Rolle vom Drucker); Standard aus den Einstellungen"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "labelwerk labels (*{suffix})"
+msgstr "labelwerk-Etiketten (*{suffix})"
+
+#: src/labelwerk/cli.py
+msgid "labelwerk now appears in the launcher (wait a moment or log in again if needed); double-clicking a .labelwerk file opens it."
+msgstr "labelwerk erscheint jetzt im Starter (ggf. kurz warten oder neu anmelden); Doppelklick auf eine .labelwerk-Datei öffnet sie."
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "labelwerk was not added ({reason})."
+msgstr "labelwerk wurde nicht eingetragen ({reason})."
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "labelwerk was not removed ({reason})."
+msgstr "labelwerk wurde nicht entfernt ({reason})."
+
+#: src/labelwerk/desktop.py
+#, python-brace-format
+msgid "labelwerk-gui not found ({path}) – GUI installed? pip install -e \".[gui]\""
+msgstr "labelwerk-gui nicht gefunden ({path}) – GUI installiert? pip install -e \".[gui]\""
+
+#: src/labelwerk/cli.py
+msgid "language of the output (default: setting, otherwise the system)"
+msgstr "Sprache der Ausgabe (Standard: Einstellung, sonst die des Systems)"
+
+#: src/labelwerk/cli.py
+msgid "list found printers and supported models"
+msgstr "gefundene Drucker und unterstützte Modelle auflisten"
+
+#: src/labelwerk/cli.py
+msgid "list installed font families"
+msgstr "installierte Schriftfamilien auflisten"
+
+#: src/labelwerk/cli.py
+msgid "list the labels for the model"
+msgstr "Etiketten für das Modell auflisten"
+
+#: src/labelwerk/cli.py
+msgid "margin all around from the paper edge in mm (default from the settings)"
+msgstr "Rand ringsum ab Papierkante in mm (Standard aus den Einstellungen)"
+
+#: src/labelwerk/cli.py
+msgid "model not detected"
+msgstr "Modell nicht erkannt"
+
+#: src/labelwerk/storage.py
+msgid "name too long"
+msgstr "Name zu lang"
+
+#: src/labelwerk/printer.py
+msgid "no answer"
+msgstr "keine Antwort"
+
+#: src/labelwerk/storage.py
+msgid "no permission"
+msgstr "keine Berechtigung"
+
+#: src/labelwerk/files.py
+msgid "no read permission"
+msgstr "keine Leserechte"
+
+#: src/labelwerk/media.py
+msgid "no roll loaded"
+msgstr "keine Rolle eingelegt"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "no shortcut"
+msgstr "kein Kürzel"
+
+#: src/labelwerk/storage.py
+msgid "no space left on the disk"
+msgstr "kein Platz auf dem Datenträger"
+
+#: src/labelwerk/settings.py
+msgid "not a JSON object"
+msgstr "kein JSON-Objekt"
+
+#: src/labelwerk/storage.py
+msgid "not a labelwerk file"
+msgstr "keine labelwerk-Datei"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "not a labelwerk file (format version {version})"
+msgstr "keine labelwerk-Datei (Format-Version {version})"
+
+#: src/labelwerk/files.py
+msgid "not a readable image"
+msgstr "kein lesbares Bild"
+
+#: src/labelwerk/files.py
+msgid "not a valid PDF file"
+msgstr "keine gültige PDF-Datei"
+
+#: src/labelwerk/cli.py
+msgid "only save a preview, do not print"
+msgstr "nur Vorschau speichern, nicht drucken"
+
+#: src/labelwerk/cli.py
+msgid "path to a .ttf file"
+msgstr "Pfad zu einer .ttf-Datei"
+
+#: src/labelwerk/cli.py
+msgid "print a PDF/image 1:1"
+msgstr "PDF/Bild 1:1 drucken"
+
+#: src/labelwerk/cli.py
+msgid "print text"
+msgstr "Text drucken"
+
+#: src/labelwerk/cli.py
+msgid "query the roll loaded in the printer (prints nothing)"
+msgstr "eingelegte Rolle vom Drucker abfragen (druckt nichts)"
+
+#: src/labelwerk/files.py
+msgid "read error"
+msgstr "Lesefehler"
+
+#: src/labelwerk/cli.py
+msgid "remove the entry and icon again"
+msgstr "Eintrag und Icon wieder entfernen"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "saved with a newer labelwerk (format version {version}) – please update labelwerk"
+msgstr "mit einem neueren labelwerk gespeichert (Format-Version {version}) – bitte labelwerk aktualisieren"
+
+#: src/labelwerk/cli.py
+msgid "shrink if too large (codes may no longer be readable)"
+msgstr "verkleinern, falls zu groß (Codes evtl. nicht mehr lesbar)"
+
+#: src/labelwerk/cli.py
+msgid "tested"
+msgstr "geprüft"
+
+#: src/labelwerk/cli.py
+msgid "text position: left, center (default), right, justify"
+msgstr "Textposition: left, center (Standard), right, justify"
+
+#: src/labelwerk/cli.py
+msgid "text, line break with \\n"
+msgstr "Text, Zeilenumbruch mit \\n"
+
+#: src/labelwerk/cli.py
+msgid "underlined"
+msgstr "unterstrichen"
+
+#: src/labelwerk/gui/panels/file.py
+msgid "unreadable"
+msgstr "nicht lesbar"
+
+#: src/labelwerk/printers.py
+msgid "untested – feedback welcome"
+msgstr "ungeprüft – Rückmeldung erwünscht"
+
+#: src/labelwerk/cli.py
+msgid "vertical: portrait (reading direction across the tape), horizontal: landscape (along the tape); default from the settings"
+msgstr "vertical: Hochformat (Leserichtung quer zum Band), horizontal: Querformat (längs zum Band); Standard aus den Einstellungen"
+
+#: src/labelwerk/clipart.py
+msgid "your own file"
+msgstr "eigene Datei"
+
+#: src/labelwerk/desktop.py
+#, python-brace-format
+msgid "{app} label"
+msgstr "{app}-Etikett"
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "{checked} of {total} selected"
+msgstr "{checked} von {total} gewählt"
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "{label} – does not fit the {model}"
+msgstr "{label} – passt nicht zum {model}"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "{loaded} is loaded, the favorite is for {label}. Print anyway?"
+msgstr "Eingelegt ist {loaded}, der Favorit ist für {label}. Trotzdem drucken?"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{message} – with placeholders in text editing (choose a smaller font)"
+msgstr "{message} – mit Platzhaltern im Schreibmodus (kleinere Schrift wählen)"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "{model} (untested)"
+msgstr "{model} (ungeprüft)"
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "{model} – untested"
+msgstr "{model} – ungeprüft"
+
+#: src/labelwerk/gui/panels/file.py
+#, python-brace-format
+msgid "{name}  ▸ Start"
+msgstr "{name}  ▸ Start"
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "{name} (missing)"
+msgstr "{name} (fehlt)"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name} cannot be read"
+msgstr "{name} kann nicht gelesen werden"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} cannot be read ({reason})"
+msgstr "{name} kann nicht gelesen werden ({reason})"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{name} has {count} pages. Which one to insert?"
+msgstr "{name} hat {count} Seiten. Welche einfügen?"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} was not saved ({reason})"
+msgstr "{name} wurde nicht gespeichert ({reason})"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} was not saved: invalid characters in the text"
+msgstr "{name} wurde nicht gespeichert: ungültige Zeichen im Text"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} was not saved: invalid numbers in the label"
+msgstr "{name} wurde nicht gespeichert: ungültige Zahlen im Etikett"
+
+#: src/labelwerk/printers.py
+#, python-brace-format
+msgid "{name} · Network"
+msgstr "{name} · Netzwerk"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{name} – untested"
+msgstr "{name} – ungeprüft"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: Excel file not readable"
+msgstr "{name}: Excel-Datei nicht lesbar"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: cell too long (at most {limit} characters)"
+msgstr "{name}: Zelle zu lang (höchstens {limit} Zeichen)"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: file damaged"
+msgstr "{name}: Datei beschädigt"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: file damaged (nested too deeply)"
+msgstr "{name}: Datei beschädigt (zu tief verschachtelt)"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: file too large"
+msgstr "{name}: Datei zu groß"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: file too large (at most {size} MB)"
+msgstr "{name}: Datei zu groß (höchstens {size} MB)"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: file too large when unpacked"
+msgstr "{name}: Datei ausgepackt zu groß"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "{name}: label “{label}” does not fit the {model}"
+msgstr "{name}: Etikett „{label}“ passt nicht zum {model}"
+
+#: src/labelwerk/series.py
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: not a file"
+msgstr "{name}: keine Datei"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: not a labelwerk file (not UTF-8 text)"
+msgstr "{name}: keine labelwerk-Datei (kein UTF-8-Text)"
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: not a labelwerk file or damaged"
+msgstr "{name}: keine labelwerk-Datei oder beschädigt"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: not a table format – CSV or Excel (.xlsx)"
+msgstr "{name}: kein Tabellenformat – CSV oder Excel (.xlsx)"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: reading Excel files is disabled without protection (defusedxml missing)"
+msgstr "{name}: Excel-Dateien lesen ist ohne Schutz abgeschaltet (defusedxml fehlt)"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: sheet “{sheet}” missing"
+msgstr "{name}: Blatt „{sheet}“ fehlt"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table is empty"
+msgstr "{name}: Tabelle ist leer"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table not readable"
+msgstr "{name}: Tabelle nicht lesbar"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table not readable (UTF-16 damaged)"
+msgstr "{name}: Tabelle nicht lesbar (UTF-16 beschädigt)"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table not readable (not a text file)"
+msgstr "{name}: Tabelle nicht lesbar (keine Textdatei)"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: too many columns (at most {limit})"
+msgstr "{name}: zu viele Spalten (höchstens {limit})"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: too many empty rows (data up to row {limit}) – delete empty rows at the end of the sheet"
+msgstr "{name}: zu viele leere Zeilen (Daten bis Zeile {limit}) – leere Zeilen am Blattende löschen"
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: too many rows (at most {limit})"
+msgstr "{name}: zu viele Zeilen (höchstens {limit})"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid ""
+"{not_found}\n"
+"Specify manually with -p file:///dev/usb/lpN"
+msgstr ""
+"{not_found}\n"
+"Manuell angeben mit -p file:///dev/usb/lpN"
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "{path} is not a printer device"
+msgstr "{path} ist kein Druckergerät"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{percent}%"
+msgstr "{percent} %"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{printer} not found – switch it on or choose another one"
+msgstr "{printer} nicht gefunden – einschalten oder einen anderen wählen"
+
+#: src/labelwerk/gui/panels/image.py
+#, python-brace-format
+msgid "{source} · page {page}"
+msgstr "{source} · Seite {page}"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title} can only encode digits, not “{char}”"
+msgstr "{title} kann nur Ziffern darstellen, nicht „{char}“"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title} needs {short} or {length} digits ({count} entered)"
+msgstr "{title} braucht {short} oder {length} Ziffern ({count} eingegeben)"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title}: content too long ({count} characters, at most {limit})"
+msgstr "{title}: Inhalt zu lang ({count} Zeichen, höchstens {limit})"
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title}: wrong check digit – it should be {right}"
+msgstr "{title}: Prüfziffer falsch – richtig wäre {right}"
+
+#: src/labelwerk/labels.py
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "{width} mm continuous"
+msgstr "{width} mm endlos"
+
+#: src/labelwerk/labels.py
+#, python-brace-format
+msgid "{width} × {height} mm die-cut"
+msgstr "{width} x {height} mm gestanzt"
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "{width} × {height} mm · die-cut"
+msgstr "{width} × {height} mm · gestanzt"
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "{width} × {length} mm die-cut"
+msgstr "{width} × {length} mm gestanzt"
+
+#: src/labelwerk/labels.py
+#, python-brace-format
+msgid "Ø {width} mm round"
+msgstr "Ø {width} mm rund"
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Ø {width} mm · round"
+msgstr "Ø {width} mm · rund"
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "“New label” applies to new labels, start zoom and language from the next start, everything else immediately."
+msgstr "„Neues Etikett“ gilt für neue Etiketten, Startzoom und Sprache ab dem nächsten Start, alles andere sofort."
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "“{keys}” is not a valid shortcut – “{action}” stays unchanged."
+msgstr "„{keys}“ ist kein gültiges Kürzel – „{action}“ bleibt unverändert."
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "“{key}”{where} missing"
+msgstr "„{key}“{where} fehlt"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "“{name}” already exists. Replace it?"
+msgstr "„{name}“ gibt es schon. Ersetzen?"
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "“{name}” has been changed. Save the changes?"
+msgstr "„{name}“ wurde geändert. Änderungen speichern?"
+
+#: src/labelwerk/gui/main_window.py
+msgid "○ Printer status unknown"
+msgstr "○ Druckerstatus unbekannt"
+
+#: src/labelwerk/gui/main_window.py
+msgid "○ no printer"
+msgstr "○ kein Drucker"
+
+#: src/labelwerk/gui/main_window.py
+msgid "○ selected printer missing"
+msgstr "○ gewählter Drucker fehlt"
+
+#: src/labelwerk/gui/main_window.py
+msgid "● Printer busy (another application)"
+msgstr "● Drucker belegt (andere Anwendung)"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "● {name} (as {model})"
+msgstr "● {name} (als {model})"
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "● {name} · untested"
+msgstr "● {name} · ungeprüft"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "★ FAVORITE"
+msgstr "★ FAVORIT"
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "☆ FAVORITE"
+msgstr "☆ FAVORIT"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid ""
+"%(prog)s: error: %(message)s\n"
+msgstr ""
+"%(prog)s: Fehler: %(message)s\n"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "argument %(argument_name)s: %(message)s"
+msgstr "Angabe %(argument_name)s: %(message)s"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "expected one argument"
+msgstr "erwartet einen Wert"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "invalid %(type)s value: %(value)r"
+msgstr "ungültiger Wert (%(type)s): %(value)r"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "invalid choice: %(value)r (choose from %(choices)s)"
+msgstr "ungültige Wahl: %(value)r (möglich: %(choices)s)"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "options"
+msgstr "Optionen"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "positional arguments"
+msgstr "Argumente"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "show this help message and exit"
+msgstr "diese Hilfe zeigen und beenden"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "the following arguments are required: %s"
+msgstr "diese Angaben fehlen: %s"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "unrecognized arguments: %s"
+msgstr "unbekannte Angaben: %s"
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "usage: "
+msgstr "Aufruf: "
+
+#. Translators: column without a name in the table header: "Column 3"
+#: src/labelwerk/series.py
+msgctxt "series"
+msgid "Column"
+msgstr "Spalte"
+
+#. Translators: name of the numbering column, used as placeholder {Number} on labels
+#: src/labelwerk/series.py
+msgctxt "series"
+msgid "Number"
+msgstr "Nummer"
+
+#: src/labelwerk/gui/panels/text.py
+msgctxt "text panel"
+msgid "Font"
+msgstr "Schrift"
+
+#~ msgid "Restart needed"
+#~ msgstr "Neustart nötig"
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
new file mode 100644
index 0000000..4fda6c5
--- /dev/null
+++ b/src/labelwerk/po/labelwerk.pot
@@ -0,0 +1,3185 @@
+msgid ""
+msgstr ""
+"Content-Type: text/plain; charset=UTF-8\n"
+"Plural-Forms: nplurals=2; plural=(n != 1);\n"
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid " in object {number}"
+msgstr ""
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+msgid " in the border"
+msgstr ""
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+msgid " in the numbering"
+msgstr ""
+
+#. Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+#: src/labelwerk/storage.py
+msgid " in the series"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "'auto' or 4–100 pt (default from the settings)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "+ CURRENT"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "--font (font file) and --font-family exclude each other."
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "-l auto (query the roll) only works with printers via USB."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "< 1%"
+msgstr ""
+
+#: src/labelwerk/series.py
+#: src/labelwerk/storage.py
+msgid "A series needs exactly one: table or numbering"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "ADD"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "ALL"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Action"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Actual size (100%)"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Add network printer …"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Add text tool"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Add to favorites"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Address"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "After each label"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+msgid "After printing"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align bottom edges"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align bottom on paper"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align horizontal centers"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Align left"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align left edges"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align left on paper"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Align right"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align right edges"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align right on paper"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Align selected objects"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Align to paper"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align top edges"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align top on paper"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Align vertical centers"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "All"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "An object extends beyond the label and will be cut off. Print anyway?"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+msgid "As set on the printer"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#: src/labelwerk/gui/panels/paper.py
+msgid "Ask the printer which roll is loaded (prints nothing)"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "At startup"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Automatic"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Automatic (detected)"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Automatic (first found)"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Automatic (system language: {language})"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "BLACK"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/tools.py
+msgid "Barcode"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+msgid "Barcode too short for the human-readable text – make it taller or turn the text off"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+msgid "Barcode without content"
+msgstr ""
+
+#: src/labelwerk/gui/tools.py
+msgid "Barcodes and QR codes"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/shortcuts.py
+msgid "Bold"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Border"
+msgstr ""
+
+#: src/labelwerk/render.py
+msgid "Border does not fit on the label – reduce inset, line width or padding"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Border “rounded” must be yes or no, not {rounded!r}"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Bring forward"
+msgstr ""
+
+#: src/labelwerk/printers.py
+msgid "Brother printer"
+msgstr ""
+
+#: src/labelwerk/detect.py
+msgid ""
+"Brother printer is connected via USB but in use by another program\n"
+"(e.g. a VM with USB passthrough). Release it there and switch the printer\n"
+"off and on again."
+msgstr ""
+
+#: src/labelwerk/detect.py
+msgid ""
+"Brother printer not found under /dev/usb/lp*.\n"
+"Check: switched on, Editor Lite LED off, 'lsusb', 'lsmod | grep usblp'."
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid ""
+"Brother printer not found via USB (pyusb).\n"
+"Check: switched on, Editor Lite LED off, 'lsusb', access to the USB bus (udev rule).\n"
+"Specify manually with -p usb://0x04f9:0xPID"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "CANCEL"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "CHECK MEDIA"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "CHECKING …"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "CSV or Excel file (.xlsx) – first row = column names"
+msgstr ""
+
+#: src/labelwerk/cups.py
+msgid "CUPS commands missing (install the package cups-client)"
+msgstr ""
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "CUPS does not answer ({command})"
+msgstr ""
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "CUPS: {command} failed"
+msgstr ""
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "CUPS: {reason}"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Cancel the series – a part already sent (up to 10 labels, with “Only at the end” the whole job) is still printed"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#: src/labelwerk/printer.py
+msgid "Cancelled – nothing printed"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Cancelled – {printed} of {total} label printed"
+msgid_plural "Cancelled – {printed} of {total} labels printed"
+msgstr[0] ""
+msgstr[1] ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Cancelling …"
+msgstr ""
+
+#: src/labelwerk/fonts.py
+#, python-brace-format
+msgid "Cannot load font “{path}” ({error})."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Cannot print the label ({error})"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Cannot read file: {name} (not a valid SVG)"
+msgstr ""
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Cannot read file: {name} ({reason})"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Cannot read symbol {name} (not a valid SVG)."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Cannot read the series ({error})"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+msgid "Cannot read vector image (not a valid SVG)."
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Canvas"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Center horizontally on paper"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Center vertically on paper"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Centered"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Changes take effect after a restart"
+msgstr ""
+
+#: src/labelwerk/media.py
+msgid "Check media only works via /dev/usb/lpN (backend linux_kernel)."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Check media only works with Brother printers via USB"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Check the roll at startup and when the printer is switched on"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Checking the roll – please print again in a moment."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Choose PDF page"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Choose printer"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Chosen printer {printer} not found – switch it on or specify it with -p."
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Classic"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Click a row and press the new key combination. Esc cancels, ✕ in the field removes the shortcut. Esc, Enter and Tab cannot be assigned here (they operate the table)."
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Click on the label to create a text frame"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+msgid "Clipboard"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Code 128 cannot encode “{char}” (ASCII only, no umlauts)"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Code 39 cannot encode “{char}” (allowed: 0–9, A–Z, space and - . $ / + %)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Color"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Columns"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Connection to {host} aborted after {sent} bytes ({reason})"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Content"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Content must be text, not {type}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Content of the code; {{column}} is filled by the series"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Content too long (at most {count} characters)"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Content too long ({count} characters, at most {limit})"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Content too long for a QR code (error correction {error})"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Continuous"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Conversion"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Copy"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Corners only"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Count"
+msgstr ""
+
+#: src/labelwerk/printer.py
+msgid "Cover opened while printing."
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Crop automatically"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Crop automatically (without crop marks and blank space)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Crop to the content (without crop marks and blank space); off = whole image"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Crop {crop} is not inside the image ({width} × {height} pixels)."
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Cut"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+msgid "Cut (cutter only)"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Cut every n labels: n must be a whole number from 1, not {value!r}"
+msgstr ""
+
+#: src/labelwerk/printer.py
+msgid "Cutter jammed."
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Cutting"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Cutting is set by the printer driver (system printer settings)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Dashed"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Default"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Default: {keys}"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Delete"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Delete favorite"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Delete favorite “{name}”?"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Delete …"
+msgstr ""
+
+#: src/labelwerk/desktop.py
+msgid "Design and print labels (Brother QL)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Die-cut"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Different roll"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Digits"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Digits of the numbering: 0 to {limit}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Distance between the border and automatically placed text"
+msgstr ""
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Distance from the left edge of the label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Distance from the paper edge all around (across the tape the printer leaves about 1.5 mm free anyway)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Distance from the top edge of the label"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Distance of the border from the edge must be between {low} and {high} mm"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Distance of the border from the printable edge"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Dotted"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Double"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Double-click: as {{column}} into the selected text object or as new text"
+msgstr ""
+
+#: src/labelwerk/gui/canvas.py
+msgid "Drag: set the length · Double-click: automatic"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+msgid "Dropped image"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Duplicate"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Edit"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Effective model: {model}"
+msgstr ""
+
+#: src/labelwerk/clipart.py
+msgid "Electrical"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Empty label"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "End text editing"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Entry{where} is not an object"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Error at label {first}–{last} of {total} (check the ones before too): {error}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Error correction"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Error correction: higher = readable despite dirt/scratches, but larger"
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Error during the status request: {error}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "FIXED FRAME SIZE"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "FROM CLIPBOARD"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "FROM FILE …"
+msgstr ""
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Factor must be greater than 0, not {factor!r}."
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Favorite"
+msgstr ""
+
+#: src/labelwerk/favorites.py
+#, python-brace-format
+msgid "Favorite “{name}” already exists"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Favorite “{name}” already exists. Replace it?"
+msgstr ""
+
+#: src/labelwerk/favorites.py
+#, python-brace-format
+msgid "Favorite “{name}” not found"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Favorite “{name}” saved"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Favorites"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Favorites folder not created ({reason})"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/gui/tools.py
+msgid "File"
+msgstr ""
+
+#: src/labelwerk/gui/tools.py
+msgid "File and favorites"
+msgstr ""
+
+#: src/labelwerk/files.py
+#: src/labelwerk/gui/image_import.py
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "File not found: {path}"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "File not found: {path} – removed from the list"
+msgstr ""
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "File type not supported: {suffix} – possible: {allowed}"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "File type not supported: {type} – possible: {allowed}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "First number"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Fixed shortcut – cannot be changed"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Font"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Font size"
+msgstr ""
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Font size converted from {old} dots to {new} pt."
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Font size in pt"
+msgstr ""
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Font size must be greater than 0, not {size!r}."
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "Font size: 'auto' or 4–100 (pt)"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Font “{family}” not found – replaced by “{replacement}”."
+msgstr ""
+
+#: src/labelwerk/clipart.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "General"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Global"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Grayscale as halftone dots – for photos and gradients"
+msgstr ""
+
+#: src/labelwerk/gui/panels/position.py
+msgid "H"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "H – 30%"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Handed over to CUPS (job {job})"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Handed to the print queue ✓ (job {job})"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Handles and fields scale the image without distortion"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Hard threshold – for codes, text and logos"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Height"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Height including the human-readable text"
+msgstr ""
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Height of the frame"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Height {height!r} mm invalid – allowed: {low}–{high} mm"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Higher = darker"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Horizontal"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "How many labels"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Human-readable text"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Human-readable text must be on or off, not {text!r}"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "INSERT"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "INSERT BARCODE"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/tools.py
+msgid "Image"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Image data “{key}”{where} not readable"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Image data{where} not readable (PNG only)"
+msgstr ""
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Image is {width} × {height} mm, label {label!r} is at most {max_w} mm wide – shrink with --fit (codes may become unreadable)"
+msgstr ""
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Image is {width} × {height} mm, label {label!r} is at most {max_w} × {max_h} mm – shrink with --fit (codes may become unreadable)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Image not cropped – only white area found"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Image reduced to {percent}"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Image reduced to {percent} – codes may no longer be readable"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Image rotated by 90° so that it fits 1:1"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Image size must be greater than 0, not {width} × {height} mm."
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Images and PDF ({patterns});;All files (*)"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Image{where} too large ({width} × {height} pixels, at most {limit})"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Insert"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Insert a barcode of the chosen type"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Insert a barcode or QR code – choose the type, type the content"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert a screenshot"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert an image from a file, the clipboard, as a screenshot or symbol – or drag it onto the label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert an image from the clipboard"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Insert an image or PDF page"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Insert barcode"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Insert image"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Insert image …"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Insert screenshot"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Insert symbol"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/shortcuts.py
+msgid "Insert symbol …"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Inserting images"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Inset"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Installed: {path}"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Invalid address: {uri}"
+msgstr ""
+
+#: src/labelwerk/favorites.py
+#, python-brace-format
+msgid "Invalid name for the favorite: “{name}” (not empty, not too long, without / and \\ and control characters, not starting with a dot)"
+msgstr ""
+
+#: src/labelwerk/cups.py
+#, python-brace-format
+msgid "Invalid queue name: {name!r}"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Invalid series sheet: {sheet!r}"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Invalid series table: {source!r}"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Invalid shortcut {seq!r}"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Invalid value for “{key}”{where}: {value}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Invert"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/shortcuts.py
+msgid "Italic"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Justified"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Keep aspect ratio"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "L – 7%"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Label in landscape – text runs along the tape"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Label in portrait – text runs across the tape"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Label labelwerk starts with (favorite as a template)"
+msgstr ""
+
+#: src/labelwerk/desktop.py
+msgid "Label printing"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Label too large (barcode contents together {total} characters, at most {limit})"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Label too large (objects together {dots:.0f} million dots, at most {limit})"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Label too large ({count} objects, at most {limit})"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Label {label!r} does not fit the printer ({model})."
+msgstr ""
+
+#: src/labelwerk/cli.py
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Label {label!r} does not fit the {model} – see 'labelwerk -m {model} labels'"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Label {label} does not fit the printer ({model}) – choose another one in the Paper tab"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Label {label} does not fit the {model} – using {new}"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Label “{label}” does not fit the printer ({model})."
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Label “{label}” does not fit the {model} – using {new}"
+msgstr ""
+
+#: src/labelwerk/desktop.py
+msgid "Label;Brother;QL;Printer;P-touch;"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Language"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Larger font"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+#: src/labelwerk/gui/tools.py
+msgid "Layout"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Length"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Line"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Line art"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Line break in “{key}”{where} – lines are separate paragraphs"
+msgstr ""
+
+#: src/labelwerk/render.py
+msgid "Line layout exists only for text objects."
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Line width"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Line width of the border must be between {low} and {high} mm"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Loaded: {media}"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Loaded: {media} (label {label})"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Loaded: {media} (no matching label)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "M – 15%"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Many scanners read red poorly"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Margin: number from 0 to {max} mm"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Margins"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Maximize on paper"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Model"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Model not recognized – choose a fallback model in the settings"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Model {model} does not fit the printer {printer} – give cups:NAME for CUPS, zpl:203/300/600 for Zebra, otherwise a Brother QL."
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Module"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Module width {module!r} invalid – allowed: 1–{limit} dots"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move down (0.1 mm)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move down (1 mm)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move left (0.1 mm)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move left (1 mm)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move right (0.1 mm)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move right (1 mm)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move up (0.1 mm)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Move up (1 mm)"
+msgstr ""
+
+#: src/labelwerk/clipart.py
+msgid "My symbols"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "NEW"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "NONE"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "NUMBERING"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Name"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Name of the favorite:"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Network printer {name}: address “{host}” invalid – only an IP address or name, without “tcp://” and port"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Network printer {printer} not reachable ({reason}) – switched on, in the same network, address correct?"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Network printers"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#: src/labelwerk/shortcuts.py
+msgid "New label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Next row on the canvas"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid ""
+"No CUPS queue found (set up the printer in the printer settings).\n"
+"Specify with -p cups:NAME"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid ""
+"No Zebra printer found.\n"
+"Specify with -p zpl+file:///dev/usb/lpN or -p zpl+tcp://IP and -m zpl:203"
+msgstr ""
+
+#: src/labelwerk/media.py
+msgid "No answer from the printer to the status request."
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "No border"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "No favorites yet – choose a symbol and press ★."
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "No favorites yet – design a label and press “+ CURRENT”."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "No image in the clipboard."
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "No label for the loaded roll ({media}) on the {model}."
+msgstr ""
+
+#: src/labelwerk/printer.py
+msgid "No labels to print"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid ""
+"No network printer configured (GUI settings).\n"
+"Specify the address with -p tcp://IP"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+#, python-brace-format
+msgid ""
+"No own symbols yet. Put SVG or PNG files into this folder (subfolders are not read):\n"
+"{path}"
+msgstr ""
+
+#: src/labelwerk/media.py
+#: src/labelwerk/printer.py
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "No permission for {device} – is the user in group 'lp'?"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "No printer for this label – choose a printer in the status bar."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "No printer found"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "No printer found."
+msgstr ""
+
+#: src/labelwerk/cli.py
+#: src/labelwerk/printer.py
+msgid "No roll loaded."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "No row selected – nothing printed."
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "No series"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Not a Zebra address: {uri}"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Note: {tools} did not work – the file association may only apply after logging in again."
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Nothing found."
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Nothing inserted yet."
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "Nothing to remove."
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Numbering"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering count: 1 to {limit}"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering start: whole number up to {limit}"
+msgstr ""
+
+#: src/labelwerk/series.py
+msgid "Numbering step must not be 0"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering step: whole number up to {limit}"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Numbering values too large (at most {limit})"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "Numbers without a file: column “{column}”"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "OPEN FOLDER"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "OPEN …"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "ORIGINAL SIZE 1:1"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Object extends beyond the label"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Object sticks out"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Off: images that are too large are reduced – saves tape"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "On round labels every border becomes a circle."
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Only at the end"
+msgstr ""
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Only changeable with a fixed frame size"
+msgstr ""
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Only for text objects, not for {type}."
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Only needed if labelwerk does not recognize the model (then applies, and without a connected printer)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Open as new label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Open at startup"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Open folder"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Open label"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Open the folder for your own symbols (created if needed)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Open …"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Opened: {name}"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Opened: {name} – {error}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Order"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Orientation"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "PDF is encrypted"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "PDF page (default 1)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "PDF, PNG or JPG"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "PRINT"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Pad with zeros to this many digits (0 = no padding)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Padding"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Padding of the border must be between {low} and {high} mm"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "Page must be at least 1."
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/tools.py
+msgid "Paper"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Paste"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+msgid "Peel off (dispenser only)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Photo"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/panels/text.py
+msgid "Position (mm)"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Preparing {current}/{total} …"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Preview"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Preview cannot be saved: {path} ({error})"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Preview: {path} ({width} × {height} mm)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Previous row on the canvas"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+#: src/labelwerk/shortcuts.py
+msgid "Print"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Print series"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Print size from the resolution of the image (e.g. stamp, code)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Print the content readable below the barcode"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Print {count} label?"
+msgid_plural "Print {count} labels?"
+msgstr[0] ""
+msgstr[1] ""
+
+#: src/labelwerk/gui/panels/file.py
+#, python-brace-format
+msgid "Print “{name}”"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Printed ✓"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Printer"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Printer error: {err}"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Printer model"
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Printer not found: {printer}"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid ""
+"Printer not found: {printer}\n"
+"Check: switched on, Editor Lite LED off, 'lsusb', 'lsmod | grep usblp'."
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid ""
+"Printer not found: {printer}\n"
+"Check: switched on, Editor Lite LED off, 'lsusb'."
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Printer not reachable: {error}"
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Printer reports: {errors}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Printer without cutter – separate the labels by hand"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Printer {printer} not ready ({reason}) – in use or busy? Wait a moment or switch it off and on."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Printing – please wait."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Printing …"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Printing … {done} of {total}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Q – 25%"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+msgid "QR code"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "Querying the roll only works with printers via USB."
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+#, python-brace-format
+msgid "Quiet zone: leave {mm} mm free all around"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+#, python-brace-format
+msgid "Quiet zone: leave {mm} mm free on the left and right each"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "RED"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "REMOVE"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Recently opened"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Recently used"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Red only on the 62 mm red/black label (DK-22251) with a QL-8xx"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Redo"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Remove from favorites"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Remove the series from the label (placeholders stay)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Removed: {path}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Rename …"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Replace favorite"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Replace file"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Reset all"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "Resize"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Resolution of Zebra printers on USB, in case labelwerk does not detect it correctly (otherwise 203 dpi)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Roll: none loaded"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} – no matching label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} – selection does not match"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} ✓"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Roll: {media} ✓ – label adjusted"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/panels/layout.py
+msgid "Rotate"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Rotate 90° left"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Rotate 90° right"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Rotate if the image only fits 1:1 when rotated"
+msgstr ""
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "Rotation {rotate!r} not possible – allowed: auto, 0, 90, 180, 270"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Round"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Rounded"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Row {rows} extends beyond the label and will be cut off. Print anyway?"
+msgid_plural "Rows {rows} extend beyond the label and will be cut off. Print anyway?"
+msgstr[0] ""
+msgstr[1] ""
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "Row {row}/{total}"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Row {row}: {message}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Rows"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "SAVE"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "SAVE AS …"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "SCREENSHOT"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "SETTINGS"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "SYMBOL"
+msgstr ""
+
+#: src/labelwerk/clipart.py
+msgid "Safety"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Same height"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Same size"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Same width"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Save"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Save as …"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Save label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "Save the current label as a favorite"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "Saved: {name}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Scale the text automatically so that it fits"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Scope"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+msgid "Screenshot"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – cannot subscribe to the answer of the portal"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – error of the portal"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – no connection to the session bus"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – no image file received"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – no screenshot portal found"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – not allowed by the system"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – rejected or cancelled by the system"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – the portal does not answer"
+msgstr ""
+
+#: src/labelwerk/gui/screenshot.py
+msgid "Screenshot failed – unexpected answer from the portal"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Screenshot not available (no XDG portal) – copy it to the clipboard with the system tool and paste it with Ctrl+V"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Screenshot: {error}"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "Search … (e.g. earth, fragile, house)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Select all"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Select tool"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Selected printer not found – switch it on or choose another one in the status bar."
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Send backward"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Sending to {path} aborted after {sent} bytes ({reason})"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Sent ✓ (the printer reports no status)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+#: src/labelwerk/gui/tools.py
+msgid "Series"
+msgstr ""
+
+#: src/labelwerk/gui/tools.py
+msgid "Series from a table or numbering"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Series: {error}"
+msgstr ""
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Setting 'font_size' invalid ({value!r}) – automatic."
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Setting 'shortcuts' invalid ({value!r}) – default shortcuts active."
+msgstr ""
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Setting {key!r} invalid ({value!r}) – using default {default!r}."
+msgstr ""
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Setting {key!r}: invalid entries discarded."
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#: src/labelwerk/shortcuts.py
+msgid "Settings"
+msgstr ""
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Settings could not be saved ({path}): {reason}"
+msgstr ""
+
+#: src/labelwerk/settings.py
+#, python-brace-format
+msgid "Settings not readable ({path}): {error} – using defaults."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Settings saved – they apply to new labels."
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Sheet of the Excel file"
+msgstr ""
+
+#: src/labelwerk/clipart.py
+msgid "Shipping"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Shortcut"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut assigned twice: {keys} ({first}, {second}) – “{second}” has no shortcut now."
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for unknown action {action!r} ignored."
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for {action!r} invalid ({keys!r}) – default {default!r} active."
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for {action!r} invalid ({keys}) – Esc, Enter and Tab cannot be assigned; default {default!r} active."
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+#, python-brace-format
+msgid "Shortcut for {action!r} is fixed ({default}) – setting ignored."
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Shortcuts"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Shortcuts assigned twice – change one to save:"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Single"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+#: src/labelwerk/gui/panels/image.py
+msgid "Size"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Smaller font"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/panels/series.py
+msgid "Source"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Start"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Start favorite “{name}” not found – empty label"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Start text editing (Enter)"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Start text editing (selected text)"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Start zoom"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Status: {outcome}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Step"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "Step to the next number (not 0)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Style"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Supported: {models}, Zebra zpl:203/300/600 (untested), CUPS queues cups:NAME (untested)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Swap black and white"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Symbol library unreadable: {error}"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "Symbol: {error}"
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+#, python-brace-format
+msgid "Symbol: {name}"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "TABLE …"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Table for the series"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Table not found: {path}"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Tables (*.csv *.xlsx *.xlsm *.tsv *.txt);;All files (*)"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+msgid "Tear off"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/gui/tools.py
+msgid "Text"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgid "Text alignment"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Text does not fit on label {label_id!r} at font size {size} pt (at most {max_size} pt)."
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Text does not fit on label {label_id!r} – not even at the smallest font size."
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Text editing"
+msgstr ""
+
+#: src/labelwerk/layout.py
+msgid "Text with automatic font size needs the effective base size (base_pt) for scaling."
+msgstr ""
+
+#: src/labelwerk/files.py
+#, python-brace-format
+msgid "The PDF has only {count} page."
+msgid_plural "The PDF has only {count} pages."
+msgstr[0] ""
+msgstr[1] ""
+
+#: src/labelwerk/files.py
+msgid "The file has no printable content."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "The label is empty. Print anyway?"
+msgstr ""
+
+#: src/labelwerk/printer.py
+msgid "The label roll is empty."
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "The loaded roll does not match the label {label!r} – check the roll or choose another label."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "The table has changed and was read again – check the selection and print again."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "The table has no rows – nothing printed."
+msgstr ""
+
+#: src/labelwerk/printer.py
+msgid "The tape cannot be fed – roll empty or loaded incorrectly?"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Theme"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "There is no printable content between the crop marks."
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+msgid "Thick-thin"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+msgid "Threshold"
+msgstr ""
+
+#: src/labelwerk/imaging.py
+#, python-brace-format
+msgid "Threshold must be a whole number from 0 to 255, not {threshold!r}."
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "Tools"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Type"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Type of barcode – for the selected one or the next one"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+#: src/labelwerk/shortcuts.py
+msgid "Underline"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Undo"
+msgstr ""
+
+#: src/labelwerk/gui/media_worker.py
+#, python-brace-format
+msgid "Unexpected error while checking the roll: {error}"
+msgstr ""
+
+#: src/labelwerk/gui/print_worker.py
+#, python-brace-format
+msgid "Unexpected error while printing: {error}"
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Unintelligible answer from the printer: {error}"
+msgstr ""
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Unknown alignment {mode!r} – allowed: {allowed}"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Unknown barcode type {kind!r}"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown border style {style!r} – allowed: {allowed}"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown color {color!r} – allowed: black, red"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "Unknown column: {columns}"
+msgid_plural "Unknown columns: {columns}"
+msgstr[0] ""
+msgstr[1] ""
+
+#: src/labelwerk/imaging.py
+#, python-brace-format
+msgid "Unknown conversion {mode!r} – allowed: line art, photo (line, photo)"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "Unknown cut {cut!r} – allowed: {allowed}"
+msgstr ""
+
+#: src/labelwerk/printer.py
+#, python-brace-format
+msgid "Unknown cut {mode!r} – allowed: {allowed}"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "Unknown error correction {error!r} – allowed: L, M, Q, H"
+msgstr ""
+
+#: src/labelwerk/labels.py
+#, python-brace-format
+msgid "Unknown label: {label_id!r}"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Unknown label{where}: {value}"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Unknown mode {mode!r} – allowed: {allowed}"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Unknown object type{where}: {kind}"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown orientation {orientation!r} – allowed: horizontal, vertical"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Unknown printer model {model!r} – allowed: {models}, zpl:203/300/600 or cups:NAME"
+msgstr ""
+
+#: src/labelwerk/printers.py
+#, python-brace-format
+msgid "Unknown printer model: {model!r}"
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Unknown roll (code 0x{code:02X})"
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "Unknown roll: {media}"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#: src/labelwerk/layout.py
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees"
+msgstr ""
+
+#: src/labelwerk/layout.py
+#, python-brace-format
+msgid "Unknown size matching {mode!r} – allowed: {allowed}"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Unknown text alignment {align!r} – allowed: left, center, right, justify"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Unsaved changes"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+msgid "Untitled"
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "Value for “crop”{where} is not inside the image: {crop}"
+msgstr ""
+
+#: src/labelwerk/render.py
+#, python-brace-format
+msgid "Vector image could not be rasterized ({got_w} × {got_h} instead of {width} × {height} pixels)."
+msgstr ""
+
+#: src/labelwerk/gui/image_import.py
+msgid "Vector image refers to other files – they are not saved with it."
+msgstr ""
+
+#: src/labelwerk/render.py
+msgid "Vector image: crop enlarged too much – please scale it down or turn cropping off."
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Vertical"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "View"
+msgstr ""
+
+#: src/labelwerk/gui/panels/position.py
+msgid "W"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+msgid "When printing the series: cut after each label or only at the end (continuous tape: a few mm of feed remain between the labels, without a separator mark)"
+msgstr ""
+
+#: src/labelwerk/gui/panels/position.py
+msgid "Width of the frame"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+msgid "Width of the narrowest bar or of one QR square – in whole dots (0.085 mm), so the code stays readable"
+msgstr ""
+
+#: src/labelwerk/gui/panels/layout.py
+msgid "With automatic length the label grows along – the object keeps the same margin at both ends"
+msgstr ""
+
+#: src/labelwerk/gui/panels/barcode.py
+#, python-brace-format
+msgid "With check digit: {code}"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "Zebra (ZPL) {dpi} dpi – untested"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer does not accept data ({sent} bytes sent) – paper, ribbon, paused?"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer not found: {path} – switched on, cable?"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer not reachable: {path} ({reason})"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "Zebra printer {host} not reachable ({reason}) – switched on, in the same network, address correct?"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Zebra resolution"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Zoom in"
+msgstr ""
+
+#: src/labelwerk/shortcuts.py
+msgid "Zoom out"
+msgstr ""
+
+#: src/labelwerk/storage.py
+msgid "access error"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "add labelwerk-gui to the launcher (Super key)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "auto (default: detected, otherwise from the settings) or e.g. QL-700, zpl:300 (Zebra), cups:NAME; see 'labelwerk printers'"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "auto (default: rotate only if needed) or degrees clockwise"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "bold (default) or --no-bold"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "default: from the printer (tcp:// → network)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "do not cut (Brother; for CUPS/Zebra the driver or the mode in the GUI settings decides)"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "file is damaged or incomplete"
+msgstr ""
+
+#: src/labelwerk/storage.py
+msgid "folder missing"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "font family, e.g. 'Liberation Sans' (see 'labelwerk fonts')"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "image has too many pixels"
+msgstr ""
+
+#: src/labelwerk/files.py
+#: src/labelwerk/storage.py
+msgid "is a folder"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "italic"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "label, e.g. 62, or auto (roll loaded in the printer); default from the settings"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "labelwerk labels (*{suffix})"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "labelwerk now appears in the launcher (wait a moment or log in again if needed); double-clicking a .labelwerk file opens it."
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "labelwerk was not added ({reason})."
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "labelwerk was not removed ({reason})."
+msgstr ""
+
+#: src/labelwerk/desktop.py
+#, python-brace-format
+msgid "labelwerk-gui not found ({path}) – GUI installed? pip install -e \".[gui]\""
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "language of the output (default: setting, otherwise the system)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "list found printers and supported models"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "list installed font families"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "list the labels for the model"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "margin all around from the paper edge in mm (default from the settings)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "model not detected"
+msgstr ""
+
+#: src/labelwerk/storage.py
+msgid "name too long"
+msgstr ""
+
+#: src/labelwerk/printer.py
+msgid "no answer"
+msgstr ""
+
+#: src/labelwerk/storage.py
+msgid "no permission"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "no read permission"
+msgstr ""
+
+#: src/labelwerk/media.py
+msgid "no roll loaded"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "no shortcut"
+msgstr ""
+
+#: src/labelwerk/storage.py
+msgid "no space left on the disk"
+msgstr ""
+
+#: src/labelwerk/settings.py
+msgid "not a JSON object"
+msgstr ""
+
+#: src/labelwerk/storage.py
+msgid "not a labelwerk file"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "not a labelwerk file (format version {version})"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "not a readable image"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "not a valid PDF file"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "only save a preview, do not print"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "path to a .ttf file"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "print a PDF/image 1:1"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "print text"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "query the roll loaded in the printer (prints nothing)"
+msgstr ""
+
+#: src/labelwerk/files.py
+msgid "read error"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "remove the entry and icon again"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "saved with a newer labelwerk (format version {version}) – please update labelwerk"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "shrink if too large (codes may no longer be readable)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "tested"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "text position: left, center (default), right, justify"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "text, line break with \\n"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "underlined"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+msgid "unreadable"
+msgstr ""
+
+#: src/labelwerk/printers.py
+msgid "untested – feedback welcome"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgid "vertical: portrait (reading direction across the tape), horizontal: landscape (along the tape); default from the settings"
+msgstr ""
+
+#: src/labelwerk/clipart.py
+msgid "your own file"
+msgstr ""
+
+#: src/labelwerk/desktop.py
+#, python-brace-format
+msgid "{app} label"
+msgstr ""
+
+#: src/labelwerk/gui/panels/series.py
+#, python-brace-format
+msgid "{checked} of {total} selected"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "{label} – does not fit the {model}"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "{loaded} is loaded, the favorite is for {label}. Print anyway?"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{message} – with placeholders in text editing (choose a smaller font)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "{model} (untested)"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "{model} – untested"
+msgstr ""
+
+#: src/labelwerk/gui/panels/file.py
+#, python-brace-format
+msgid "{name}  ▸ Start"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "{name} (missing)"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name} cannot be read"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} cannot be read ({reason})"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{name} has {count} pages. Which one to insert?"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} was not saved ({reason})"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} was not saved: invalid characters in the text"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name} was not saved: invalid numbers in the label"
+msgstr ""
+
+#: src/labelwerk/printers.py
+#, python-brace-format
+msgid "{name} · Network"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{name} – untested"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: Excel file not readable"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: cell too long (at most {limit} characters)"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: file damaged"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: file damaged (nested too deeply)"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: file too large"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: file too large (at most {size} MB)"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: file too large when unpacked"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "{name}: label “{label}” does not fit the {model}"
+msgstr ""
+
+#: src/labelwerk/series.py
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: not a file"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: not a labelwerk file (not UTF-8 text)"
+msgstr ""
+
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "{name}: not a labelwerk file or damaged"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: not a table format – CSV or Excel (.xlsx)"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: reading Excel files is disabled without protection (defusedxml missing)"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: sheet “{sheet}” missing"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table is empty"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table not readable"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table not readable (UTF-16 damaged)"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: table not readable (not a text file)"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: too many columns (at most {limit})"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: too many empty rows (data up to row {limit}) – delete empty rows at the end of the sheet"
+msgstr ""
+
+#: src/labelwerk/series.py
+#, python-brace-format
+msgid "{name}: too many rows (at most {limit})"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid ""
+"{not_found}\n"
+"Specify manually with -p file:///dev/usb/lpN"
+msgstr ""
+
+#: src/labelwerk/zpl.py
+#, python-brace-format
+msgid "{path} is not a printer device"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{percent}%"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "{printer} not found – switch it on or choose another one"
+msgstr ""
+
+#: src/labelwerk/gui/panels/image.py
+#, python-brace-format
+msgid "{source} · page {page}"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title} can only encode digits, not “{char}”"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title} needs {short} or {length} digits ({count} entered)"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title}: content too long ({count} characters, at most {limit})"
+msgstr ""
+
+#: src/labelwerk/barcodes.py
+#, python-brace-format
+msgid "{title}: wrong check digit – it should be {right}"
+msgstr ""
+
+#: src/labelwerk/labels.py
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "{width} mm continuous"
+msgstr ""
+
+#: src/labelwerk/labels.py
+#, python-brace-format
+msgid "{width} × {height} mm die-cut"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "{width} × {height} mm · die-cut"
+msgstr ""
+
+#: src/labelwerk/media.py
+#, python-brace-format
+msgid "{width} × {length} mm die-cut"
+msgstr ""
+
+#: src/labelwerk/labels.py
+#, python-brace-format
+msgid "Ø {width} mm round"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Ø {width} mm · round"
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+msgid "“New label” applies to new labels, start zoom and language from the next start, everything else immediately."
+msgstr ""
+
+#: src/labelwerk/gui/settings_dialog.py
+#, python-brace-format
+msgid "“{keys}” is not a valid shortcut – “{action}” stays unchanged."
+msgstr ""
+
+#. Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+#: src/labelwerk/storage.py
+#, python-brace-format
+msgid "“{key}”{where} missing"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "“{name}” already exists. Replace it?"
+msgstr ""
+
+#: src/labelwerk/gui/file_session.py
+#, python-brace-format
+msgid "“{name}” has been changed. Save the changes?"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "○ Printer status unknown"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "○ no printer"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "○ selected printer missing"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+msgid "● Printer busy (another application)"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "● {name} (as {model})"
+msgstr ""
+
+#: src/labelwerk/gui/main_window.py
+#, python-brace-format
+msgid "● {name} · untested"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "★ FAVORITE"
+msgstr ""
+
+#: src/labelwerk/gui/symbol_dialog.py
+msgid "☆ FAVORITE"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid ""
+"%(prog)s: error: %(message)s\n"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "argument %(argument_name)s: %(message)s"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "expected one argument"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "invalid %(type)s value: %(value)r"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "invalid choice: %(value)r (choose from %(choices)s)"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "options"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "positional arguments"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "show this help message and exit"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "the following arguments are required: %s"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "unrecognized arguments: %s"
+msgstr ""
+
+#: src/labelwerk/cli.py
+msgctxt "argparse"
+msgid "usage: "
+msgstr ""
+
+#. Translators: column without a name in the table header: "Column 3"
+#: src/labelwerk/series.py
+msgctxt "series"
+msgid "Column"
+msgstr ""
+
+#. Translators: name of the numbering column, used as placeholder {Number} on labels
+#: src/labelwerk/series.py
+msgctxt "series"
+msgid "Number"
+msgstr ""
+
+#: src/labelwerk/gui/panels/text.py
+msgctxt "text panel"
+msgid "Font"
+msgstr ""
diff --git a/src/labelwerk/printer.py b/src/labelwerk/printer.py
index 743bb11..a130d9f 100644
--- a/src/labelwerk/printer.py
+++ b/src/labelwerk/printer.py
@@ -10,23 +10,25 @@ from brother_ql.raster import BrotherQLRaster
 from PIL import Image
 
 from .document import CUTS
+from .i18n import N_, _, ngettext
 from .labels import get_label, labels_for_model
 from .printers import DEFAULT_MODEL, backend_for, capabilities, route_fits
 
 DEFAULT_BACKEND = "linux_kernel"
 DEFAULT_PRINTER = "file:///dev/usb/lp0"
 
-# Fehlertexte aus brother_ql.reader -> verständliche Meldung
+# Fehlertexte aus brother_ql.reader -> verständliche Meldung (übersetzt beim Melden)
 _PRINTER_ERRORS = {
-    "Replace media error": "Eingelegte Rolle passt nicht zum Etikett {label!r} – "
-                           "Rolle prüfen oder anderes Etikett wählen.",
-    "No media when printing": "Keine Rolle eingelegt.",
-    "End of media (die-cut size only)": "Etikettenrolle ist leer.",
+    "Replace media error": N_("The loaded roll does not match the label {label!r} – "
+                              "check the roll or choose another label."),
+    "No media when printing": N_("No roll loaded."),
+    "End of media (die-cut size only)": N_("The label roll is empty."),
     "Media cannot be fed (also when the media end is detected)":
-        "Band kann nicht transportiert werden – Rolle leer oder falsch eingelegt?",
-    "Tape cutter jam": "Schneidwerk blockiert.",
-    "Cover opened while printing (Except QL-500)": "Deckel während des Drucks geöffnet.",
+        N_("The tape cannot be fed – roll empty or loaded incorrectly?"),
+    "Tape cutter jam": N_("Cutter jammed."),
+    "Cover opened while printing (Except QL-500)": N_("Cover opened while printing."),
 }
+_PRINTER_ERROR = N_("Printer error: {err}")      # andere Fehler von brother_ql
 
 
 class PrintError(Exception):
@@ -39,8 +41,9 @@ class PrintCancelled(Exception):
 
     def __init__(self, printed: int, total: int):
         self.printed, self.total = printed, total
-        super().__init__(f"Abgebrochen – {printed} von {total} Etiketten gedruckt" if printed
-                         else "Abgebrochen – nichts gedruckt")
+        super().__init__(ngettext("Cancelled – {printed} of {total} label printed",
+                                  "Cancelled – {printed} of {total} labels printed", total).format(
+            printed=printed, total=total) if printed else _("Cancelled – nothing printed"))
 
 
 MAX_CUT_EVERY = 255         # Brother ESC i A n: höchstens alle 255 Etiketten
@@ -51,6 +54,8 @@ MAX_CUT_EVERY = 255         # Brother ESC i A n: höchstens alle 255 Etiketten
 MAX_JOB_EACH = 10
 THRESHOLD = 70.0            # brother_ql: ein Punkt druckt ab (100 − THRESHOLD) % Schwarz
 CONNECT_TIMEOUT_S = 5       # Netzwerkdrucker: so lange auf die Verbindung warten
+_UNREACHABLE = N_("Network printer {printer} not reachable ({reason}) – switched on, in the same "
+                  "network, address correct?")
 
 
 _LEVEL = min(255, max(0, int((100.0 - THRESHOLD) / 100.0 * 255)))   # wie brother_ql.convert
@@ -71,7 +76,7 @@ def pure_colors(image: Image.Image) -> Image.Image:
     Schwarz-Weiß-Etikett (brother_ql nähme sonst nur sehr dunkle Punkte als Schwarz, Text würde
     dünner als in der Vorschau). Schwarze Tinte senkt alle Kanäle, rote nur Grün und Blau:
     Schwarz, wo Rot dunkel genug ist; Rot, wo sonst Grün dunkel genug ist."""
-    r, g, _ = image.convert("RGB").split()
+    r, g, __ = image.convert("RGB").split()
     black = r.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
     red = g.point(lambda v: 255 if 255 - v >= _LEVEL else 0, mode="1")
     out = Image.new("RGB", image.size, "white")
@@ -84,7 +89,8 @@ def cut_interval(mode: str, count: int) -> int:
     """Schneiden alle n Etiketten: „each“ → 1, „end“ → alle (bei mehr als 255 Etiketten
     zusätzlich nach je 255 – mehr kann der Drucker nicht)."""
     if mode not in CUTS:
-        raise ValueError(f"Unbekannter Schnitt {mode!r} – erlaubt: {', '.join(CUTS)}")
+        raise ValueError(_("Unknown cut {mode!r} – allowed: {allowed}").format(
+            mode=mode, allowed=", ".join(CUTS)))
     return 1 if mode == "each" else max(1, min(count, MAX_CUT_EVERY))
 
 
@@ -115,13 +121,13 @@ def build_instructions(
     (``cut_interval``) und am Ende. Etiketten Rot/Schwarz (62red) mit Rot-Ebene."""
     images = [images] if isinstance(images, Image.Image) else list(images)
     if not images:
-        raise ValueError("Keine Etiketten zum Drucken")
+        raise ValueError(_("No labels to print"))
     if not isinstance(cut_every, int) or isinstance(cut_every, bool) or cut_every < 1:
-        raise ValueError(f"Schneiden alle n Etiketten: n muss eine ganze Zahl ab 1 sein, "
-                         f"nicht {cut_every!r}")
+        raise ValueError(_("Cut every n labels: n must be a whole number from 1, not {value!r}")
+                         .format(value=cut_every))
     if label_id not in {label.id for label in labels_for_model(model)}:
-        raise ValueError(f"Etikett {label_id!r} passt nicht zum {model} – siehe "
-                         f"'labelwerk -m {model} labels'")
+        raise ValueError(_("Label {label!r} does not fit the {model} – see "
+                           "'labelwerk -m {model} labels'").format(label=label_id, model=model))
     qlr = _Raster(model, cut_every)
     qlr.exception_on_warning = True
     red = get_label(label_id).two_color          # nur Zweifarb-Modelle haben 62red (oben geprüft)
@@ -166,10 +172,12 @@ def print_image(
     backend = backend or backend_for(printer)
     images = [image] if isinstance(image, Image.Image) else list(image)
     if label_id not in {label.id for label in labels_for_model(model)}:
-        raise PrintError(f"Etikett {label_id!r} passt nicht zum Drucker ({model}).")
+        raise PrintError(_("Label {label!r} does not fit the printer ({model}).").format(
+            label=label_id, model=model))
     if not route_fits(backend, model):
-        raise PrintError(f"Modell {model} passt nicht zum Drucker {printer} – für CUPS cups:NAME, "
-                         "für Zebra zpl:203/300/600, sonst ein Brother-QL angeben.")
+        raise PrintError(_("Model {model} does not fit the printer {printer} – give cups:NAME for "
+                           "CUPS, zpl:203/300/600 for Zebra, otherwise a Brother QL.").format(
+            model=model, printer=printer))
     if backend == "cups":
         return _print_cups(printer[len("cups:"):], images, label_id, options, cancelled)
     if backend == "zpl":
@@ -193,8 +201,9 @@ def print_image(
             if start == 0:                  # noch nichts gedruckt: Meldung wie bei einem Etikett
                 raise
             # der Drucker meldet verzögert – der Fehler kann auch zu Etiketten davor gehören
-            raise PrintError(f"Fehler bei Etikett {start + 1}–{start + len(chunk)} von {len(images)} "
-                             f"(auch die davor prüfen): {e}") from None
+            raise PrintError(_("Error at label {first}–{last} of {total} (check the ones before "
+                               "too): {error}").format(first=start + 1, last=start + len(chunk),
+                                                       total=len(images), error=e)) from None
         if progress is not None:
             progress(start + len(chunk), len(images))
     return status
@@ -235,18 +244,19 @@ def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
     except OSError as e:                  # pyusb: USBError ist ein OSError
         if backend != "network":
             raise _usb_error(e, printer) from None
-        raise PrintError(f"Netzwerkdrucker {printer} nicht erreichbar ({e.strerror or e}) – "
-                         "eingeschaltet, im selben Netz, Adresse richtig?") from None
+        raise PrintError(_(_UNREACHABLE).format(printer=printer, reason=e.strerror or e)) \
+            from None
     except ValueError as e:
         if str(e) != "Device not found":  # pyusb
             raise
-        raise PrintError(f"Drucker nicht gefunden: {printer}\n"
-                         "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb'.") from None
+        raise PrintError(_("Printer not found: {printer}\n"
+                           "Check: switched on, Editor Lite LED off, 'lsusb'.").format(
+            printer=printer)) from None
 
     errors = (status.get("printer_state") or {}).get("errors") or []
     if errors:
         raise PrintError("\n".join(
-            _PRINTER_ERRORS.get(err, "Druckerfehler: {err}").format(label=label_id, err=err)
+            _(_PRINTER_ERRORS.get(err, _PRINTER_ERROR)).format(label=label_id, err=err)
             for err in errors))
     return status
 
@@ -254,22 +264,24 @@ def _send(data: bytes, label_id: str, printer: str, backend: str) -> dict:
 def _usb_error(e: OSError, printer: str) -> PrintError:
     """Verständliche Meldung für ein fehlendes, gesperrtes oder belegtes USB-Gerät."""
     if isinstance(e, PermissionError):
-        return PrintError(f"Keine Berechtigung für {printer} – Benutzer in Gruppe 'lp'?")
+        return PrintError(_("No permission for {device} – is the user in group 'lp'?")
+                          .format(device=printer))
     if isinstance(e, FileNotFoundError):
-        return PrintError(f"Drucker nicht gefunden: {printer}\n"
-                          "Prüfen: eingeschaltet, Editor-Lite-LED aus, 'lsusb', "
-                          "'lsmod | grep usblp'.")
-    return PrintError(f"Drucker {printer} nicht bereit ({e.strerror or e}) – belegt oder "
-                      "gerade beschäftigt? Kurz warten bzw. aus- und einschalten.")
+        return PrintError(_("Printer not found: {printer}\n"
+                            "Check: switched on, Editor Lite LED off, 'lsusb', "
+                            "'lsmod | grep usblp'.").format(printer=printer))
+    return PrintError(_("Printer {printer} not ready ({reason}) – in use or busy? Wait a moment "
+                        "or switch it off and on.").format(printer=printer,
+                                                           reason=e.strerror or e))
 
 
 def _reachable(printer: str) -> None:
     """Netzwerkdrucker vorab mit Zeitlimit ansprechen – brother_ql wartet sonst ohne Grenze
     (bei einer falschen Adresse rund zwei Minuten)."""
-    host, _, port = printer[len("tcp://"):].partition(":")
+    host, __, port = printer[len("tcp://"):].partition(":")
     try:
         socket.create_connection((host, int(port or 9100)), timeout=CONNECT_TIMEOUT_S).close()
     except (OSError, ValueError) as e:
-        reason = "keine Antwort" if isinstance(e, TimeoutError) else getattr(e, "strerror", None) or e
-        raise PrintError(f"Netzwerkdrucker {printer} nicht erreichbar ({reason}) – "
-                         "eingeschaltet, im selben Netz, Adresse richtig?") from None
+        reason = _("no answer") if isinstance(e, TimeoutError) \
+            else getattr(e, "strerror", None) or e
+        raise PrintError(_(_UNREACHABLE).format(printer=printer, reason=reason)) from None
diff --git a/src/labelwerk/printers.py b/src/labelwerk/printers.py
index 1f980b4..aaa9ff7 100644
--- a/src/labelwerk/printers.py
+++ b/src/labelwerk/printers.py
@@ -14,6 +14,8 @@ from pathlib import Path
 
 from brother_ql.models import ModelsManager
 
+from .i18n import N_, _
+
 BROTHER_VENDOR_ID = "04f9"
 SYS_ROOT = "/sys/class/usbmisc"             # Tests setzen ein leeres Verzeichnis
 DEFAULT_MODEL = "QL-600"
@@ -27,7 +29,7 @@ PRODUCT_IDS = {
     "209b": "QL-800", "209c": "QL-810W", "209d": "QL-820NWB", "2020": "QL-1050",
     "202a": "QL-1060N", "20a7": "QL-1100", "20a8": "QL-1110NWB", "20ab": "QL-1115NWB",
 }
-UNTESTED_HINT = "ungeprüft – Rückmeldung erwünscht"
+UNTESTED_HINT = N_("untested – feedback welcome")   # beim Anzeigen mit _() übersetzen
 
 
 def _models() -> dict:
@@ -88,7 +90,7 @@ def capabilities(model: str) -> Capabilities:
         return Capabilities(model, False, False, 104, GENERIC_LENGTH, False)
     m = _models().get(model)
     if m is None:
-        raise ValueError(f"Unbekanntes Druckermodell: {model!r}")
+        raise ValueError(_("Unknown printer model: {model!r}").format(model=model))
     return Capabilities(model, bool(m.cutting), bool(m.two_color),
                         104 if m.number_bytes_per_row >= 162 else 62,
                         tuple(m.min_max_length_dots), model in TESTED_MODELS)
@@ -140,7 +142,7 @@ def _read(path: Path) -> str:
 def _ieee1284_model(text: str) -> str | None:
     """„MFG:Brother;CMD:PT-CBP;MDL:QL-600;CLS:PRINTER;“ → „QL-600“."""
     for part in text.split(";"):
-        key, _, value = part.partition(":")
+        key, __, value = part.partition(":")
         if key.strip().upper() in ("MDL", "MODEL"):
             return value.strip()
     return None
@@ -160,7 +162,7 @@ def usb_printers(sys_root: str | Path | None = None,
                          or known_model(_read(node / "product"))
                          or PRODUCT_IDS.get(_read(node / "idProduct").lower()))
                 found.append(Printer(f"file://{dev_root}/{entry.name}", model,
-                                     f"{model or 'Brother-Drucker'} · {entry.name}"))
+                                     f"{model or _('Brother printer')} · {entry.name}"))
             break
     return found
 
@@ -200,10 +202,14 @@ def network_printers(entries: list[NetworkEntry]) -> list[Printer]:
     """Eingetragene Netzwerkdrucker: Brother (``tcp://``) bzw. Zebra (Modell „zpl:…“,
     ``zpl+tcp://``)."""
     from . import zpl
-    return [Printer(f"zpl+tcp://{e.host}:{NETWORK_PORT}", e.model, f"{e.name or e.host} · Netzwerk",
-                    "zebra") if zpl.is_model(e.model) else
-            Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, f"{e.name or e.host} · Netzwerk",
-                    "network") for e in entries]
+    return [Printer(f"zpl+tcp://{e.host}:{NETWORK_PORT}", e.model, _network_name(e), "zebra")
+            if zpl.is_model(e.model) else
+            Printer(f"tcp://{e.host}:{NETWORK_PORT}", e.model, _network_name(e), "network")
+            for e in entries]
+
+
+def _network_name(entry: NetworkEntry) -> str:
+    return _("{name} · Network").format(name=entry.name or entry.host)
 
 
 def choose(printers: list[Printer], wanted: str = "") -> Printer | None:
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 88cb032..98edc25 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -23,6 +23,8 @@ from . import barcodes, fonts, imaging
 from .document import (ALIGNMENTS, COLORS, FRAME_LINE_MM, FRAME_STYLES, MAX_FRAME_MM,
                        MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS, BarcodeObject,
                        Document, Frame, ImageObject, Paragraph, Span, TextObject)
+from . import i18n
+from .i18n import N_, _
 from .labels import DPI, get_label, length_limits
 from .printers import capabilities
 
@@ -42,17 +44,18 @@ class TextTooLarge(ValueError):
 
     def __init__(self, size_pt: float, max_pt: float | None, label_id: str):
         if max_pt is None:                     # passt nicht einmal in der kleinsten Größe
-            message = (f"Text passt nicht auf Etikett {label_id!r} – auch nicht in der "
-                       "kleinsten Schriftgröße.")
+            message = _("Text does not fit on label {label_id!r} – not even at the smallest font "
+                        "size.").format(label_id=label_id)
         else:
-            message = (f"Text passt nicht auf Etikett {label_id!r} bei Schriftgröße "
-                       f"{_fmt_pt(size_pt)} pt (höchstens {_fmt_pt(max_pt)} pt).")
+            message = _("Text does not fit on label {label_id!r} at font size {size} pt (at most "
+                        "{max_size} pt).").format(label_id=label_id, size=_fmt_pt(size_pt),
+                                                  max_size=_fmt_pt(max_pt))
         super().__init__(message)
         self.size_pt, self.max_pt = size_pt, max_pt
 
 
 def _fmt_pt(value: float) -> str:
-    return f"{value:g}".replace(".", ",")
+    return i18n.number(value)
 
 
 def render_text(text: str, label_id: str, size_pt: float | None = None,
@@ -73,7 +76,8 @@ def font_warnings(doc: Document) -> list[str]:
                 if span.family is None:
                     continue
                 match = fonts.resolve(span.family, span.bold, span.italic)
-                text = f"Schrift „{span.family}“ nicht gefunden – ersetzt durch „{match.family}“."
+                text = _("Font “{family}” not found – replaced by “{replacement}”.").format(
+                    family=span.family, replacement=match.family)
                 if match.family.casefold() != span.family.casefold() and text not in warnings:
                     warnings.append(text)
     return warnings
@@ -116,7 +120,7 @@ def text_layout(obj: TextObject, doc: Document, model: str = "QL-600") -> TextLa
     """Zeilensatz eines Objekts ohne Bild – derselbe, den ``render_object`` zeichnet
     (``RenderedObject.layout``)."""
     if not isinstance(obj, TextObject):
-        raise TypeError("Einen Zeilensatz gibt es nur für Text-Objekte.")
+        raise TypeError(_("Line layout exists only for text objects."))
     return _place(*_measure(obj, doc, model))[0]
 
 
@@ -391,7 +395,8 @@ class _Sheet:
 
 def _sheet(doc: Document, model: str) -> _Sheet:
     if doc.orientation not in ORIENTATIONS:
-        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
+        raise ValueError(_("Unknown orientation {orientation!r} – allowed: horizontal, vertical").format(
+            orientation=doc.orientation))
     label = get_label(doc.label_id)
     min_len, max_len = length_limits(model)
     # Rand ringsum ab Papierkante: der Streifen, den der Drucker dort nicht bedruckt, zählt mit
@@ -413,14 +418,14 @@ def _sheet(doc: Document, model: str) -> _Sheet:
                   label.two_color and capabilities(model).two_color, label.dpi)
 
 
-FRAME_TOO_BIG = "Rahmen passt nicht aufs Etikett – Abstand, Strichstärke oder Innenabstand verkleinern"
+FRAME_TOO_BIG = N_("Border does not fit on the label – reduce inset, line width or padding")
 
 
 def _check_room(sheet: _Sheet) -> None:
     """Rahmen ohne Innenraum → Meldung. Nur beim Rendern geprüft – Ränder und bedruckbarer
     Bereich bleiben auch dann bestimmbar (die GUI fragt sie außerhalb des Renderns ab)."""
     if sheet.frame is not None and min(sheet.room()) <= 0:
-        raise ValueError(FRAME_TOO_BIG)
+        raise ValueError(_(FRAME_TOO_BIG))
 
 
 def _dots(mm: float, dpi: int = DPI) -> int:
@@ -448,7 +453,7 @@ class Prepared:
 
 def _prepare(obj: TextObject | ImageObject | BarcodeObject, sheet: _Sheet) -> Prepared:
     if obj.color not in COLORS:
-        raise ValueError(f"Unbekannte Farbe {obj.color!r} – erlaubt: schwarz, rot (black, red)")
+        raise ValueError(_("Unknown color {color!r} – allowed: black, red").format(color=obj.color))
     if isinstance(obj, ImageObject):
         return _prepare_image(obj, sheet.dpi)
     if isinstance(obj, BarcodeObject):
@@ -456,10 +461,11 @@ def _prepare(obj: TextObject | ImageObject | BarcodeObject, sheet: _Sheet) -> Pr
         return Prepared(obj, 0, [], (0, 0, *frame), frame, dpi=sheet.dpi)
     for para in obj.paragraphs:
         if para.align not in ALIGNMENTS:
-            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
-                             "rechts, Blocksatz (left, center, right, justify)")
+            raise ValueError(_("Unknown text alignment {align!r} – allowed: left, center, right, "
+                               "justify").format(align=para.align))
     if obj.rotation not in ROTATIONS:
-        raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
+        raise ValueError(_("Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees").format(
+            rotation=obj.rotation))
     max_w, max_h = sheet.room(inner=not obj.positioned)   # frei platziert: Rahmen gilt nicht
     if obj.rotation in (90, 270):
         max_w, max_h = max_h, max_w
@@ -638,11 +644,12 @@ def _paint(lines: list, x0: int, y0: int, width: int, height: int,
 def _prepare_image(obj: ImageObject, dpi: int = DPI) -> Prepared:
     """Bild-Objekt prüfen und messen: Rahmen in Druckpunkten (ungedreht) aus ``w_mm``/``h_mm``."""
     if obj.rotation not in ROTATIONS:
-        raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
+        raise ValueError(_("Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees").format(
+            rotation=obj.rotation))
     imaging.check(obj.mode, obj.threshold)
     if not (obj.w_mm > 0 and obj.h_mm > 0):
-        raise ValueError(f"Größe des Bilds muss größer als 0 sein, nicht "
-                         f"{obj.w_mm:g} × {obj.h_mm:g} mm.")
+        raise ValueError(_("Image size must be greater than 0, not {width} × {height} mm.").format(
+            width=i18n.number(obj.w_mm), height=i18n.number(obj.h_mm)))
     frame = (max(1, _dots(obj.w_mm, dpi)), max(1, _dots(obj.h_mm, dpi)))
     return Prepared(obj, 0, [], (0, 0, *frame), frame, dpi=dpi)
 
@@ -716,12 +723,14 @@ def _vector_source(svg: bytes, png: bytes, crop: tuple[int, int, int, int] | Non
     fx, fy = w / (r - l), h / (b - t)
     full = (round(sheet[0] * fx), round(sheet[1] * fy))
     if max(full) > MAX_SHEET:
-        raise ValueError("Vektorbild: Ausschnitt zu stark vergrößert – bitte kleiner skalieren "
-                         "oder den Zuschnitt ausschalten.")
+        raise ValueError(_("Vector image: crop enlarged too much – please scale it down or turn "
+                           "cropping off."))
     picture = _svg_rasterizer(svg, full, (round(l * fx), round(t * fy), w, h))
     if picture.size != (w, h):
-        raise ValueError(f"Vektorbild konnte nicht gerastert werden ({picture.width} × "
-                         f"{picture.height} statt {w} × {h} Pixel).")
+        raise ValueError(_("Vector image could not be rasterized ({got_w} × {got_h} instead of "
+                           "{width} × {height} pixels).").format(got_w=picture.width,
+                                                                  got_h=picture.height,
+                                                                  width=w, height=h))
     return picture if picture.mode == "RGB" else picture.convert("RGB")
 
 
@@ -729,8 +738,8 @@ def _check_crop(crop: tuple[int, int, int, int], size: tuple[int, int]) -> None:
     """Ausschnitt (l, t, r, b) muss eine Fläche im Bild der Größe ``size`` sein."""
     l, t, r, b = crop
     if not (0 <= l < r <= size[0] and 0 <= t < b <= size[1]):
-        raise ValueError(f"Ausschnitt {crop} liegt nicht im Bild "
-                         f"({size[0]} × {size[1]} Pixel).")
+        raise ValueError(_("Crop {crop} is not inside the image ({width} × {height} pixels).").format(
+            crop=crop, width=size[0], height=size[1]))
 
 
 def _fitted(source: tuple[int, int], size: tuple[int, int], keep_ratio: bool) -> tuple[int, int]:
@@ -849,9 +858,9 @@ def _shape(obj: TextObject, base: int, mode: str = "L",
             start += len(span.text)
         rows.append((para, pieces))
 
-    widths = [sum(p.font.getlength(p.text, mode) for p in pieces) for _, pieces in rows]
+    widths = [sum(p.font.getlength(p.text, mode) for p in pieces) for __, pieces in rows]
     # Unterlängen großer Stücke brauchen Platz unter der Zeile; bei einheitlicher Schrift 0
-    min_descent = min(p.font.getmetrics()[1] for _, pieces in rows for p in pieces)
+    min_descent = min(p.font.getmetrics()[1] for __, pieces in rows for p in pieces)
     max_width = max(widths, default=0)
     ref = max_width if frame is None else frame
     top = 0.0
@@ -1010,8 +1019,8 @@ class TextLayout:
         Bezugskante passt; bei gemischten Ausrichtungen gilt die linke Kante.
         """
         if align not in ALIGNMENTS:
-            raise ValueError(f"Unbekannte Textposition {align!r} – erlaubt: links, zentriert, "
-                             "rechts, Blocksatz (left, center, right, justify)")
+            raise ValueError(_("Unknown text alignment {align!r} – allowed: left, center, right, "
+                               "justify").format(align=align))
         left = min(line.stops[0] for line in self.lines)
         right = max(line.stops[-1] for line in self.lines)
         share = {"left": 0.0, "justify": 0.0, "center": 0.5, "right": 1.0}[align]
@@ -1141,21 +1150,25 @@ def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
 # --- Zierrahmen ---------------------------------------------------------------------
 def _check_frame(frame: Frame) -> None:
     if frame.style not in FRAME_STYLES:
-        raise ValueError(f"Unbekannte Rahmenart {frame.style!r} – erlaubt: "
-                         f"{', '.join(FRAME_STYLES)}")
+        raise ValueError(_("Unknown border style {style!r} – allowed: {allowed}").format(
+            style=frame.style, allowed=", ".join(FRAME_STYLES)))
     if not isinstance(frame.rounded, bool):
-        raise ValueError(f"„abgerundet“ des Rahmens muss ja oder nein sein, nicht {frame.rounded!r}")
-    for value, (low, high), name in ((frame.line_mm, FRAME_LINE_MM, "Strichstärke"),
-                                     (frame.inset_mm, (0.0, MAX_FRAME_MM), "Abstand zum Rand"),
-                                     (frame.padding_mm, (0.0, MAX_FRAME_MM), "Innenabstand")):
+        raise ValueError(_("Border “rounded” must be yes or no, not {rounded!r}").format(
+            rounded=frame.rounded))
+    for value, (low, high), message in (
+            (frame.line_mm, FRAME_LINE_MM,
+             N_("Line width of the border must be between {low} and {high} mm")),
+            (frame.inset_mm, (0.0, MAX_FRAME_MM),
+             N_("Distance of the border from the edge must be between {low} and {high} mm")),
+            (frame.padding_mm, (0.0, MAX_FRAME_MM),
+             N_("Padding of the border must be between {low} and {high} mm"))):
         if (not isinstance(value, (int, float)) or isinstance(value, bool)
                 or not math.isfinite(value) or not low <= value <= high):
-            raise ValueError(f"{name} des Rahmens muss zwischen {_fmt_mm(low)} und "
-                             f"{_fmt_mm(high)} mm liegen")
+            raise ValueError(_(message).format(low=_fmt_mm(low), high=_fmt_mm(high)))
 
 
 def _fmt_mm(value: float) -> str:
-    return f"{value:g}".replace(".", ",")
+    return i18n.number(value)
 
 
 def _line(frame: Frame, dpi: int = DPI) -> int:
@@ -1184,7 +1197,7 @@ def _outer(sheet: _Sheet, width: int, height: int) -> tuple[int, int, int, int]:
 
 def _circle_room(sheet: _Sheet) -> int:
     """Seite des Quadrats im Kreisrahmen (Innenraum runder Etiketten) in Druckpunkten."""
-    x0, _, x1, _ = _outer(sheet, sheet.across, sheet.across)   # runde Etiketten sind quadratisch
+    x0, __, x1, __ = _outer(sheet, sheet.across, sheet.across)   # runde Etiketten sind quadratisch
     radius = (x1 - x0) / 2 - _band(sheet.frame, sheet.dpi) - sheet.dots(sheet.frame.padding_mm)
     return int(radius * math.sqrt(2)) if radius > 0 else 0
 
@@ -1224,7 +1237,7 @@ def _frame_mask(sheet: _Sheet, width: int, height: int) -> Image.Image | None:
     if style == "corners":
         leg = min(sheet.dots(FRAME_CORNER_MM), min(w, h) // 4)
         if leg < 2 * lw:                     # sonst blieben nur Quadrate (oder nichts)
-            raise ValueError(FRAME_TOO_BIG)
+            raise ValueError(_(FRAME_TOO_BIG))
         keep = Image.new("L", mask.size, 0)
         corners = ImageDraw.Draw(keep)
         for x, y in ((box[0], box[1]), (box[2] - leg, box[1]), (box[0], box[3] - leg),
diff --git a/src/labelwerk/series.py b/src/labelwerk/series.py
index 4158764..b04ad67 100644
--- a/src/labelwerk/series.py
+++ b/src/labelwerk/series.py
@@ -22,6 +22,8 @@ from pathlib import Path
 
 from .document import (CUTS, MAX_DIGITS, MAX_NUMBER, MAX_SERIES_ROWS, BarcodeObject, Document,
                        Numbering, Paragraph, Series, Span, TextObject)
+from . import i18n
+from .i18n import NP_, N_, _, pgettext
 from .storage import LINE_BREAKS
 
 MAX_BYTES = 20 * 1024 * 1024        # Tabellendatei
@@ -32,7 +34,10 @@ MAX_CELL = 100_000                  # Zeichen je Zelle (CSV)
 MAX_RAW_ROWS = 100_000              # Excel: Zeilen samt leeren (verirrte Zelle weit unten)
 CSV_SUFFIXES = (".csv", ".tsv", ".txt")
 EXCEL_SUFFIXES = (".xlsx", ".xlsm")
-NUMBER_COLUMN = "Nummer"
+# Translators: name of the numbering column, used as placeholder {Number} on labels
+NUMBER_COLUMN = NP_("series", "Number")   # Spalte der Nummerierung – in jeder Sprache gültig
+# Translators: column without a name in the table header: "Column 3"
+COLUMN_WORD = NP_("series", "Column")     # Spalte ohne Namen in der Kopfzeile: „Spalte 3“
 # bei Gleichstand gewinnt das frühere: Tab steht kaum je im Text, deutsches Excel nimmt „;“
 _SEPARATORS = ("\t", ";", ",", "|")
 _SNIFF_LINES = 20
@@ -64,7 +69,8 @@ def load_table(path: str | Path, sheet: str | None = None) -> Table:
         return _read_excel(path, sheet)
     if suffix in CSV_SUFFIXES:
         return _read_csv(path)
-    raise SeriesError(f"{path.name or path}: kein Tabellenformat – CSV oder Excel (.xlsx)")
+    raise SeriesError(_("{name}: not a table format – CSV or Excel (.xlsx)").format(
+        name=path.name or path))
 
 
 def sheet_names(path: str | Path) -> list[str]:
@@ -84,16 +90,17 @@ def _read_bytes(path: Path) -> bytes:
     try:
         info = os.stat(path)
         if not stat.S_ISREG(info.st_mode):
-            raise SeriesError(f"{path.name}: keine Datei")
+            raise SeriesError(_("{name}: not a file").format(name=path.name))
         if info.st_size > MAX_BYTES:
-            raise SeriesError(f"{path.name}: Datei zu groß (höchstens {MAX_BYTES // 2**20} MB)")
+            raise SeriesError(_("{name}: file too large (at most {size} MB)").format(
+                name=path.name, size=MAX_BYTES // 2**20))
         return path.read_bytes()
     except SeriesError:
         raise
     except FileNotFoundError as e:
-        raise SeriesError(f"Tabelle nicht gefunden: {path}") from e
+        raise SeriesError(_("Table not found: {path}").format(path=path)) from e
     except (OSError, ValueError) as e:         # ValueError: NUL-Zeichen im Pfad
-        raise SeriesError(f"{path.name or path} kann nicht gelesen werden") from e
+        raise SeriesError(_("{name} cannot be read").format(name=path.name or path)) from e
 
 
 def _decode(data: bytes, path: Path) -> str:
@@ -101,7 +108,8 @@ def _decode(data: bytes, path: Path) -> str:
         try:
             return data.decode("utf-16")
         except UnicodeDecodeError as e:
-            raise SeriesError(f"{path.name}: Tabelle nicht lesbar (UTF-16 beschädigt)") from e
+            raise SeriesError(_("{name}: table not readable (UTF-16 damaged)").format(
+                name=path.name)) from e
     for encoding in ("utf-8-sig", "cp1252"):
         try:
             return data.decode(encoding)
@@ -131,7 +139,7 @@ def _separator(text: str) -> str:
 def _read_csv(path: Path) -> Table:
     text = _decode(_read_bytes(path), path)
     if "\x00" in text:                                   # Binärdatei mit falscher Endung
-        raise SeriesError(f"{path.name}: Tabelle nicht lesbar (keine Textdatei)")
+        raise SeriesError(_("{name}: table not readable (not a text file)").format(name=path.name))
     reader = csv.reader(io.StringIO(text, newline=""), delimiter=_separator(text))
     limit = csv.field_size_limit()
     try:
@@ -139,9 +147,9 @@ def _read_csv(path: Path) -> Table:
         return _collect(reader, path)
     except csv.Error as e:
         if "field larger" in str(e):
-            raise SeriesError(f"{path.name}: Zelle zu lang (höchstens {MAX_CELL:,} Zeichen)"
-                              .replace(",", ".")) from e
-        raise SeriesError(f"{path.name}: Tabelle nicht lesbar") from e
+            raise SeriesError(_("{name}: cell too long (at most {limit} characters)").format(
+                name=path.name, limit=i18n.thousands(MAX_CELL))) from e
+        raise SeriesError(_("{name}: table not readable").format(name=path.name)) from e
     finally:
         csv.field_size_limit(limit)
 
@@ -150,18 +158,18 @@ def _open_excel(path: Path):
     """Arbeitsmappe aus den einmal gelesenen Bytes (kein zweites Öffnen des Pfads)."""
     import openpyxl
     if not openpyxl.DEFUSEDXML:                # ohne defusedxml wären XML-Angriffe möglich
-        raise SeriesError(f"{path.name}: Excel-Dateien lesen ist ohne Schutz abgeschaltet "
-                          "(defusedxml fehlt)")
+        raise SeriesError(_("{name}: reading Excel files is disabled without protection "
+                            "(defusedxml missing)").format(name=path.name))
     data = io.BytesIO(_read_bytes(path))
     try:
         with zipfile.ZipFile(data) as archive:
             if sum(info.file_size for info in archive.infolist()) > MAX_UNPACKED:
-                raise SeriesError(f"{path.name}: Datei ausgepackt zu groß")
+                raise SeriesError(_("{name}: file too large when unpacked").format(name=path.name))
         return openpyxl.load_workbook(data, read_only=True, data_only=True)
     except SeriesError:
         raise
     except Exception as e:  # openpyxl/zipfile werfen je nach Schaden verschiedene Fehler
-        raise SeriesError(f"{path.name}: Excel-Datei nicht lesbar") from e
+        raise SeriesError(_("{name}: Excel file not readable").format(name=path.name)) from e
 
 
 def _read_excel(path: Path, sheet: str | None) -> Table:
@@ -171,12 +179,13 @@ def _read_excel(path: Path, sheet: str | None) -> Table:
         if sheet is not None:
             chosen = next((ws for ws in sheets if ws.title == sheet), None)
             if chosen is None:
-                raise SeriesError(f"{path.name}: Blatt „{sheet}“ fehlt")
+                raise SeriesError(_("{name}: sheet “{sheet}” missing").format(name=path.name,
+                                                                              sheet=sheet))
         else:
             chosen = next((ws for ws in sheets if ws.sheet_state == "visible"),
                           sheets[0] if sheets else None)
         if chosen is None:
-            raise SeriesError(f"{path.name}: Tabelle ist leer")
+            raise SeriesError(_("{name}: table is empty").format(name=path.name))
         # leere Zeilen kosten auch: openpyxl liefert jede Lücke (Zelle in Zeile 1 048 576 → 35 s)
         width = MAX_COLUMNS + 1
         if chosen.max_column:                             # Dimension der Datei, falls angegeben
@@ -189,7 +198,7 @@ def _read_excel(path: Path, sheet: str | None) -> Table:
     except SeriesError:
         raise
     except Exception as e:
-        raise SeriesError(f"{path.name}: Excel-Datei nicht lesbar") from e
+        raise SeriesError(_("{name}: Excel file not readable").format(name=path.name)) from e
     finally:
         book.close()
 
@@ -198,9 +207,9 @@ def _limited(rows, path: Path):
     """Höchstens ``MAX_RAW_ROWS`` Zeilen (auch leere) – sonst Meldung statt minutenlangem Lesen."""
     for number, row in enumerate(rows, start=1):
         if number > MAX_RAW_ROWS:
-            raise SeriesError(f"{path.name}: zu viele leere Zeilen (Daten bis Zeile "
-                              f"{MAX_RAW_ROWS:,}".replace(",", ".") + ") – leere Zeilen am Blattende "
-                              "löschen")
+            raise SeriesError(_("{name}: too many empty rows (data up to row {limit}) – delete "
+                                "empty rows at the end of the sheet").format(
+                name=path.name, limit=i18n.thousands(MAX_RAW_ROWS)))
         yield row
 
 
@@ -234,13 +243,15 @@ def _number(value: int | float, number_format: str) -> str:
     match = re.search(r"(0+)(?:\.(0+))?", fmt.replace("#", "").replace(",", ""))
     if match and fmt not in ("General", "@"):
         decimals = len(match.group(2) or "")
-        text = f"{abs(value):.{decimals}f}".replace(".", ",")
-        whole, _, fraction = text.partition(",")
-        text = whole.zfill(len(match.group(1))) + ("," + fraction if fraction else "")
-        return ("-" if value < 0 and float(text.replace(",", ".")) else "") + text + suffix
+        point = i18n.content_decimal()
+        text = f"{abs(value):.{decimals}f}"
+        whole, __, fraction = text.partition(".")
+        negative = value < 0 and float(text) != 0
+        text = whole.zfill(len(match.group(1))) + (point + fraction if fraction else "")
+        return ("-" if negative else "") + text + suffix
     if isinstance(value, int) or (value.is_integer() and abs(value) < 1e21):
         return f"{value:.0f}" + suffix if isinstance(value, float) else str(value) + suffix
-    return f"{value:.15g}".replace(".", ",") + suffix
+    return f"{value:.15g}".replace(".", i18n.content_decimal()) + suffix
 
 
 def _collect(rows: Iterable[list], path: Path) -> Table:
@@ -256,18 +267,19 @@ def _collect(rows: Iterable[list], path: Path) -> Table:
             continue
         if header is None:
             if len(cells) > MAX_COLUMNS:
-                raise SeriesError(f"{path.name}: zu viele Spalten (höchstens {MAX_COLUMNS})")
+                raise SeriesError(_("{name}: too many columns (at most {limit})").format(
+                    name=path.name, limit=MAX_COLUMNS))
             header = cells
             continue
         if len(data) == MAX_ROWS:
-            raise SeriesError(f"{path.name}: zu viele Zeilen (höchstens {MAX_ROWS:,})"
-                              .replace(",", "."))
+            raise SeriesError(_("{name}: too many rows (at most {limit})").format(
+                name=path.name, limit=i18n.thousands(MAX_ROWS)))
         data.append(cells)
     if header is None:
-        raise SeriesError(f"{path.name}: Tabelle ist leer")
+        raise SeriesError(_("{name}: table is empty").format(name=path.name))
     columns: list[str] = []
     for number, name in enumerate(header, start=1):
-        name = name.strip() or f"Spalte {number}"
+        name = name.strip() or f"{pgettext('series', COLUMN_WORD)} {number}"
         unique, n = name, 2
         while unique in columns:
             unique, n = f"{name} ({n})", n + 1
@@ -283,42 +295,46 @@ def _whole(value) -> bool:
 
 def check_numbering(numbering: Numbering) -> None:
     """Grenzen der Nummerierung – auch die letzte Zahl bleibt bei höchstens ``MAX_NUMBER``."""
-    limit = f"{MAX_NUMBER:,}".replace(",", ".")
-    for value, name in ((numbering.start, "Start"), (numbering.step, "Schritt")):
+    limit = i18n.thousands(MAX_NUMBER)
+    for value, message in ((numbering.start, N_("Numbering start: whole number up to {limit}")),
+                           (numbering.step, N_("Numbering step: whole number up to {limit}"))):
         if not _whole(value) or abs(value) > MAX_NUMBER:
-            raise SeriesError(f"{name} der Nummerierung: ganze Zahl bis {limit}")
+            raise SeriesError(_(message).format(limit=limit))
     if numbering.step == 0:
-        raise SeriesError("Schritt der Nummerierung darf nicht 0 sein")
+        raise SeriesError(_("Numbering step must not be 0"))
     if not _whole(numbering.count) or not 1 <= numbering.count <= MAX_SERIES_ROWS:
-        raise SeriesError(f"Anzahl der Nummerierung: 1 bis {MAX_SERIES_ROWS:,}".replace(",", "."))
+        raise SeriesError(_("Numbering count: 1 to {limit}").format(
+            limit=i18n.thousands(MAX_SERIES_ROWS)))
     if not _whole(numbering.digits) or not 0 <= numbering.digits <= MAX_DIGITS:
-        raise SeriesError(f"Stellen der Nummerierung: 0 bis {MAX_DIGITS}")
+        raise SeriesError(_("Digits of the numbering: 0 to {limit}").format(limit=MAX_DIGITS))
     if abs(numbering.start + (numbering.count - 1) * numbering.step) > MAX_NUMBER:
-        raise SeriesError(f"Zahlen der Nummerierung zu groß (höchstens {limit})")
+        raise SeriesError(_("Numbering values too large (at most {limit})").format(limit=limit))
 
 
 def numbering_table(numbering: Numbering) -> Table:
-    """Spalte „Nummer“: ``start``, ``start + step`` … – mit Nullen auf ``digits`` Stellen."""
+    """Spalte „Nummer“ (Name in der Sprache, ``number_column``): ``start``, ``start + step`` … – mit
+    Nullen auf ``digits`` Stellen."""
     check_numbering(numbering)
 
     def text(n: int) -> str:
         digits = str(abs(n)).zfill(numbering.digits)
         return f"-{digits}" if n < 0 else digits
-    return Table([NUMBER_COLUMN], [[text(numbering.start + i * numbering.step)]
+    return Table([number_column()], [[text(numbering.start + i * numbering.step)]
                                    for i in range(numbering.count)])
 
 
 def check(value: Series) -> None:
     """Serie prüfen: genau eins von Tabelle und Nummerierung, bekannter Schnitt."""
     if (value.source is None) == (value.numbering is None):
-        raise SeriesError("Serie braucht genau eins: Tabelle oder Nummerierung")
+        raise SeriesError(_("A series needs exactly one: table or numbering"))
     if value.source is not None and (not isinstance(value.source, str) or not value.source
                                      or "\x00" in value.source):
-        raise SeriesError(f"Tabelle der Serie ungültig: {value.source!r}")
+        raise SeriesError(_("Invalid series table: {source!r}").format(source=value.source))
     if value.sheet is not None and not isinstance(value.sheet, str):
-        raise SeriesError(f"Blatt der Serie ungültig: {value.sheet!r}")
+        raise SeriesError(_("Invalid series sheet: {sheet!r}").format(sheet=value.sheet))
     if value.cut not in CUTS:
-        raise SeriesError(f"Unbekannter Schnitt {value.cut!r} – erlaubt: {', '.join(CUTS)}")
+        raise SeriesError(_("Unknown cut {cut!r} – allowed: {allowed}").format(
+            cut=value.cut, allowed=", ".join(CUTS)))
     if value.numbering is not None:
         check_numbering(value.numbering)
 
@@ -348,9 +364,32 @@ def placeholders(doc: Document) -> list[str]:
     return names
 
 
+def number_column() -> str:
+    """Name der Spalte der Nummerierung in der Sprache („Nummer“ / „Number“)."""
+    return pgettext("series", NUMBER_COLUMN)
+
+
+def _aliases(columns: list[str]) -> dict[str, str]:
+    """Namen in anderen Sprachen → Spalte: die Nummerierung heißt in jeder Sprache gleich gut
+    („{Nummer}“ = „{Number}“), ebenso Spalten ohne Namen („Spalte 3“ = „Column 3“) – Etiketten
+    bleiben gültig, wenn jemand die Sprache wechselt."""
+    numbers = i18n.all_translations("series", NUMBER_COLUMN)
+    words = i18n.all_translations("series", COLUMN_WORD)
+    out: dict[str, str] = {}
+    for column in columns:
+        if column in numbers:
+            out.update({name: column for name in numbers if name not in columns})
+        m = re.fullmatch(r"(\S+) (\d+)", column)
+        if m and m[1] in words:
+            out.update({f"{word} {m[2]}": column for word in words
+                        if f"{word} {m[2]}" not in columns})
+    return out
+
+
 def missing(doc: Document, columns: list[str]) -> list[str]:
-    """Platzhalter ohne passende Spalte."""
-    return [name for name in placeholders(doc) if name not in columns]
+    """Platzhalter ohne passende Spalte (Namen der Nummerierung in jeder Sprache zählen)."""
+    known = set(columns) | set(_aliases(columns))
+    return [name for name in placeholders(doc) if name not in known]
 
 
 def fill(doc: Document, columns: list[str], row: list[str], keep: int | None = None) -> Document:
@@ -364,6 +403,8 @@ def fill(doc: Document, columns: list[str], row: list[str], keep: int | None = N
     Wert werden Leerzeichen. ``keep``: Objekt, das unverändert bleibt (wird gerade bearbeitet).
     """
     values = {name: _BREAKS.sub(" ", value) for name, value in zip(columns, row)}
+    values.update({alias: values[column] for alias, column in _aliases(columns).items()
+                   if column in values})
     out = copy.copy(doc)
     out.objects = [obj if i == keep else _fill_text(obj, values) if isinstance(obj, TextObject)
                    else _fill_barcode(obj, values) if isinstance(obj, BarcodeObject) else obj
@@ -388,7 +429,7 @@ def _fill_text(obj: TextObject, values: dict[str, str]) -> TextObject:
 def _fill_paragraph(para: Paragraph, values: dict[str, str]) -> Paragraph:
     # Zeichen mit dem Index ihres Stücks; Ersetzen von hinten, damit Positionen gelten
     chars = [(c, i) for i, span in enumerate(para.spans) for c in span.text]
-    text = "".join(c for c, _ in chars)
+    text = "".join(c for c, __ in chars)
     matches = [m for m in _PLACEHOLDER.finditer(text) if m.group(1).strip() in values]
     if not matches:
         return para
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index f37cabb..718035f 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -14,12 +14,15 @@ from . import shortcuts as _shortcuts
 from .clipart import RECENT_LIMIT
 from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .fonts import DEFAULT_FAMILY
+from . import i18n
+from .i18n import N_, _
 from .labels import labels_for_model, sized_label
 from . import zpl
 from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model, is_model
 from .storage import RECENT_FILES
 
 THEMES = ("rawblock", "classic")
+RESTART_KEYS = ("language", "start_zoom")   # wirken erst nach einem Neustart (Hinweis in der GUI)
 SYMBOL_LISTS = ("symbols_recent", "symbols_favorites")
 
 
@@ -45,6 +48,7 @@ class Settings:
     network_printers: list[dict] = field(default_factory=list)   # {name, host, model}
     printer_options: dict[str, dict[str, str]] = field(default_factory=dict)  # Modell → Druck-Optionen
     zebra_dpi: int = 0                  # Auflösung der Zebras am USB, 0 = erkannt
+    language: str = ""                  # "" = Sprache des Systems, sonst "de", "en" …
     shortcuts: dict[str, str] = field(default_factory=dict)   # nur geänderte Kürzel, "" = keins
     warnings: list[str] = field(default_factory=list, compare=False, repr=False)
 
@@ -78,6 +82,7 @@ def _rules(model: str | None = None) -> dict:
                                      "zpl+tcp://"))),
         "printer_model": lambda v: v == "" or v in SUPPORTED_MODELS,
         "last_model": lambda v: v == "" or is_model(v),
+        "language": lambda v: v == "" or v in i18n.available(),
         "zebra_dpi": lambda v: v in (0, *zpl.RESOLUTIONS) and not isinstance(v, bool),
         "printer_options": lambda v: isinstance(v, dict),
         "network_printers": lambda v: isinstance(v, list),
@@ -85,6 +90,7 @@ def _rules(model: str | None = None) -> dict:
 
 
 _KEYS = (*_rules(), "shortcuts")
+_DISCARDED = N_("Setting {key!r}: invalid entries discarded.")
 
 
 def _option_word(value, empty: bool = False) -> bool:
@@ -99,10 +105,34 @@ def _printer_options(value: dict, warnings: list[str]) -> dict[str, dict[str, st
     valid = {k: {a: b for a, b in o.items() if _option_word(a) and _option_word(b, empty=True)}
              for k, o in value.items() if isinstance(k, str) and isinstance(o, dict)}
     if len(valid) != len(value) or any(len(valid[k]) != len(value[k]) for k in valid):
-        warnings.append("Einstellung 'printer_options': ungültige Einträge verworfen.")
+        warnings.append(_(_DISCARDED).format(key="printer_options"))
     return {k: o for k, o in valid.items() if o}
 
 
+def started_values(settings: Settings) -> dict:
+    """Was beim Start galt (für ``restart_pending``): die gesetzte Sprache und die Neustart-
+    Einstellungen."""
+    return {**{key: getattr(settings, key) for key in RESTART_KEYS}, "language": i18n.language()}
+
+
+def restart_pending(language: str, start_zoom: int, started: dict) -> bool:
+    """Wirkt eine Einstellung erst nach einem Neustart anders als jetzt? Sprache wirksam verglichen
+    ("" = Systemsprache), Start-Zoom mit dem Wert beim Start."""
+    effective = language if language in i18n.available() else i18n.system_language()
+    return effective != started["language"] or start_zoom != started["start_zoom"]
+
+
+def configured_language(path: str | Path | None = None) -> str:
+    """Eingestellte Sprache ("" = System) – vor allem anderen gelesen (die Meldungen beim Laden der
+    Einstellungen kommen schon in dieser Sprache); unlesbar oder ungültig → ""."""
+    try:
+        raw = json.loads(Path(path or settings_path()).read_text(encoding="utf-8"))
+    except (OSError, ValueError):
+        return ""
+    value = raw.get("language") if isinstance(raw, dict) else None
+    return value if isinstance(value, str) and value in i18n.available() else ""
+
+
 def settings_path() -> Path:
     base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
     return Path(base) / "labelwerk" / "settings.json"
@@ -116,11 +146,12 @@ def load_settings(path: str | Path | None = None, model: str | None = None) -> S
     try:
         raw = json.loads(path.read_text(encoding="utf-8"))
         if not isinstance(raw, dict):
-            raise ValueError("kein JSON-Objekt")
+            raise ValueError(_("not a JSON object"))
     except FileNotFoundError:
         return settings
     except (OSError, ValueError) as e:
-        settings.warnings.append(f"Einstellungen nicht lesbar ({path}): {e} – Standardwerte aktiv.")
+        settings.warnings.append(_("Settings not readable ({path}): {error} – using defaults.")
+                                 .format(path=path, error=e))
         return settings
     _migrate_font_size(raw, settings)
     if model is None:
@@ -145,8 +176,9 @@ def load_settings(path: str | Path | None = None, model: str | None = None) -> S
                 value = _printer_options(value, settings.warnings)
             setattr(settings, key, value)
         else:
-            settings.warnings.append(f"Einstellung {key!r} ungültig ({value!r}) – "
-                                     f"Standardwert {getattr(settings, key)!r} aktiv.")
+            settings.warnings.append(_("Setting {key!r} invalid ({value!r}) – using default "
+                                       "{default!r}.").format(key=key, value=value,
+                                                              default=getattr(settings, key)))
     if "shortcuts" in raw:                 # eigene Prüfung je Kürzel: gültige bleiben erhalten
         settings.shortcuts, warnings = _shortcuts.validate(raw["shortcuts"])
         settings.warnings.extend(warnings)
@@ -157,7 +189,7 @@ def _text_list(key: str, value: list, warnings: list[str]) -> list[str]:
     """Liste von Texten: ungültige Einträge einzeln verworfen (mit Hinweis), Doppelte entfernt."""
     valid = [i for i in value if isinstance(i, str) and i]
     if len(valid) != len(value):
-        warnings.append(f"Einstellung {key!r}: ungültige Einträge verworfen.")
+        warnings.append(_(_DISCARDED).format(key=key))
     return list(dict.fromkeys(valid))
 
 
@@ -171,7 +203,7 @@ def _network(value: list, warnings: list[str]) -> list[dict]:
                                              or zpl.is_model(e.get("model")))
              and isinstance(e.get("name", ""), str)]
     if len(valid) != len(value):
-        warnings.append("Einstellung 'network_printers': ungültige Einträge verworfen.")
+        warnings.append(_(_DISCARDED).format(key="network_printers"))
     return valid
 
 
@@ -204,10 +236,11 @@ def _migrate_font_size(raw: dict, settings: Settings) -> None:
         raw["font_size_pt"] = None
     elif _is_int(old) and old > 0:
         raw["font_size_pt"] = min(max(round(old * 72 / 300), int(MIN_PT)), int(MAX_PT))
-        settings.warnings.append(f"Schriftgröße von {old} Druckpunkten auf "
-                                 f"{raw['font_size_pt']} pt umgerechnet.")
+        settings.warnings.append(_("Font size converted from {old} dots to {new} pt.").format(
+            old=old, new=raw["font_size_pt"]))
     else:
-        settings.warnings.append(f"Einstellung 'font_size' ungültig ({old!r}) – automatisch.")
+        settings.warnings.append(_("Setting 'font_size' invalid ({value!r}) – automatic.").format(
+            value=old))
 
 
 def save_settings(settings: Settings, path: str | Path | None = None) -> Path:
@@ -224,8 +257,8 @@ def save_settings(settings: Settings, path: str | Path | None = None) -> Path:
         finally:
             tmp.unlink(missing_ok=True)
     except OSError as e:
-        raise OSError(f"Einstellungen konnten nicht gespeichert werden ({path}): "
-                      f"{e.strerror or e}") from e
+        raise OSError(_("Settings could not be saved ({path}): {reason}").format(
+            path=path, reason=e.strerror or e)) from e
     return path
 
 
diff --git a/src/labelwerk/shortcuts.py b/src/labelwerk/shortcuts.py
index f71c68a..99c16e1 100644
--- a/src/labelwerk/shortcuts.py
+++ b/src/labelwerk/shortcuts.py
@@ -14,77 +14,79 @@ from __future__ import annotations
 
 from dataclasses import dataclass
 
+from .i18n import N_, _
+
 SCOPES = ("global", "canvas", "edit")
 
 
 @dataclass(frozen=True)
 class Action:
     id: str          # z. B. "edit.copy"
-    name: str        # Anzeigename
+    name: str        # Anzeigename (englisch, mit N_ markiert – angezeigt wird _(name))
     default: str     # Standardkürzel, "" = keins
     scope: str       # global | canvas | edit
     fixed: bool = False   # Kürzel fest, in den Einstellungen nicht änderbar
 
 
 ACTIONS: tuple[Action, ...] = (
-    Action("file.new", "Neues Etikett", "Ctrl+N", "global"),
-    Action("file.open", "Öffnen …", "Ctrl+O", "global"),
-    Action("file.save", "Speichern", "Ctrl+S", "global"),
-    Action("file.save_as", "Speichern unter …", "Ctrl+Shift+S", "global"),
-    Action("file.print", "Drucken", "Ctrl+P", "global"),
-    Action("app.settings", "Einstellungen", "Ctrl+,", "global"),
-    Action("view.zoom_in", "Vergrößern (Zoom)", "Ctrl++", "global"),
-    Action("view.zoom_out", "Verkleinern (Zoom)", "Ctrl+-", "global"),
-    Action("view.zoom_reset", "Echte Größe (100 %)", "Ctrl+0", "global"),
-    Action("edit.undo", "Rückgängig", "Ctrl+Z", "global"),
-    Action("edit.redo", "Wiederherstellen", "Ctrl+Shift+Z", "global"),
-    Action("tool.select", "Werkzeug Auswahl", "Esc", "canvas"),
-    Action("tool.text", "Werkzeug Text anlegen", "T", "canvas"),
-    Action("image.insert", "Bild einfügen …", "Ctrl+Shift+I", "canvas"),
-    Action("image.screenshot", "Bildschirmfoto einfügen", "", "canvas"),
-    Action("image.symbol", "Symbol einfügen …", "", "canvas"),
-    Action("barcode.insert", "Barcode einfügen", "", "canvas"),
-    Action("edit.cut", "Ausschneiden", "Ctrl+X", "canvas"),
-    Action("edit.copy", "Kopieren", "Ctrl+C", "canvas"),
-    Action("edit.paste", "Einfügen", "Ctrl+V", "canvas"),
-    Action("edit.duplicate", "Duplizieren", "Ctrl+D", "canvas"),
-    Action("edit.delete", "Löschen", "Del", "canvas"),
-    Action("edit.select_all", "Alles auswählen", "Ctrl+A", "canvas"),
-    Action("object.nudge_left", "Nach links (0,1 mm)", "Left", "canvas"),
-    Action("object.nudge_right", "Nach rechts (0,1 mm)", "Right", "canvas"),
-    Action("object.nudge_up", "Nach oben (0,1 mm)", "Up", "canvas"),
-    Action("object.nudge_down", "Nach unten (0,1 mm)", "Down", "canvas"),
-    Action("object.nudge_left_coarse", "Nach links (1 mm)", "Shift+Left", "canvas"),
-    Action("object.nudge_right_coarse", "Nach rechts (1 mm)", "Shift+Right", "canvas"),
-    Action("object.nudge_up_coarse", "Nach oben (1 mm)", "Shift+Up", "canvas"),
-    Action("object.nudge_down_coarse", "Nach unten (1 mm)", "Shift+Down", "canvas"),
-    Action("object.rotate_left", "90° nach links drehen", "Ctrl+L", "canvas"),
-    Action("object.rotate_right", "90° nach rechts drehen", "Ctrl+R", "canvas"),
-    Action("object.bring_forward", "Nach vorne", "Ctrl+PgUp", "canvas"),
-    Action("object.send_backward", "Nach hinten", "Ctrl+PgDown", "canvas"),
-    Action("align.left", "Aneinander links ausrichten", "", "canvas"),
-    Action("align.hcenter", "Aneinander waagrecht mittig ausrichten", "", "canvas"),
-    Action("align.right", "Aneinander rechts ausrichten", "", "canvas"),
-    Action("align.top", "Aneinander oben ausrichten", "", "canvas"),
-    Action("align.vcenter", "Aneinander senkrecht mittig ausrichten", "", "canvas"),
-    Action("align.bottom", "Aneinander unten ausrichten", "", "canvas"),
-    Action("align.paper_left", "Am Papier links ausrichten", "", "canvas"),
-    Action("align.paper_hcenter", "Am Papier waagrecht mittig ausrichten", "", "canvas"),
-    Action("align.paper_right", "Am Papier rechts ausrichten", "", "canvas"),
-    Action("align.paper_top", "Am Papier oben ausrichten", "", "canvas"),
-    Action("align.paper_vcenter", "Am Papier senkrecht mittig ausrichten", "", "canvas"),
-    Action("align.paper_bottom", "Am Papier unten ausrichten", "", "canvas"),
-    Action("size.maximize", "Auf Papier maximieren", "", "canvas"),
-    Action("size.same", "Gleiche Größe", "", "canvas"),
-    Action("size.width", "Gleiche Breite", "", "canvas"),
-    Action("size.height", "Gleiche Höhe", "", "canvas"),
-    Action("text.start_edit", "Schreibmodus starten (Text der Auswahl)", "F2", "canvas"),
-    Action("text.start_edit_enter", "Schreibmodus starten (Enter)", "Return", "canvas",
+    Action("file.new", N_("New label"), "Ctrl+N", "global"),
+    Action("file.open", N_("Open …"), "Ctrl+O", "global"),
+    Action("file.save", N_("Save"), "Ctrl+S", "global"),
+    Action("file.save_as", N_("Save as …"), "Ctrl+Shift+S", "global"),
+    Action("file.print", N_("Print"), "Ctrl+P", "global"),
+    Action("app.settings", N_("Settings"), "Ctrl+,", "global"),
+    Action("view.zoom_in", N_("Zoom in"), "Ctrl++", "global"),
+    Action("view.zoom_out", N_("Zoom out"), "Ctrl+-", "global"),
+    Action("view.zoom_reset", N_("Actual size (100%)"), "Ctrl+0", "global"),
+    Action("edit.undo", N_("Undo"), "Ctrl+Z", "global"),
+    Action("edit.redo", N_("Redo"), "Ctrl+Shift+Z", "global"),
+    Action("tool.select", N_("Select tool"), "Esc", "canvas"),
+    Action("tool.text", N_("Add text tool"), "T", "canvas"),
+    Action("image.insert", N_("Insert image …"), "Ctrl+Shift+I", "canvas"),
+    Action("image.screenshot", N_("Insert screenshot"), "", "canvas"),
+    Action("image.symbol", N_("Insert symbol …"), "", "canvas"),
+    Action("barcode.insert", N_("Insert barcode"), "", "canvas"),
+    Action("edit.cut", N_("Cut"), "Ctrl+X", "canvas"),
+    Action("edit.copy", N_("Copy"), "Ctrl+C", "canvas"),
+    Action("edit.paste", N_("Paste"), "Ctrl+V", "canvas"),
+    Action("edit.duplicate", N_("Duplicate"), "Ctrl+D", "canvas"),
+    Action("edit.delete", N_("Delete"), "Del", "canvas"),
+    Action("edit.select_all", N_("Select all"), "Ctrl+A", "canvas"),
+    Action("object.nudge_left", N_("Move left (0.1 mm)"), "Left", "canvas"),
+    Action("object.nudge_right", N_("Move right (0.1 mm)"), "Right", "canvas"),
+    Action("object.nudge_up", N_("Move up (0.1 mm)"), "Up", "canvas"),
+    Action("object.nudge_down", N_("Move down (0.1 mm)"), "Down", "canvas"),
+    Action("object.nudge_left_coarse", N_("Move left (1 mm)"), "Shift+Left", "canvas"),
+    Action("object.nudge_right_coarse", N_("Move right (1 mm)"), "Shift+Right", "canvas"),
+    Action("object.nudge_up_coarse", N_("Move up (1 mm)"), "Shift+Up", "canvas"),
+    Action("object.nudge_down_coarse", N_("Move down (1 mm)"), "Shift+Down", "canvas"),
+    Action("object.rotate_left", N_("Rotate 90° left"), "Ctrl+L", "canvas"),
+    Action("object.rotate_right", N_("Rotate 90° right"), "Ctrl+R", "canvas"),
+    Action("object.bring_forward", N_("Bring forward"), "Ctrl+PgUp", "canvas"),
+    Action("object.send_backward", N_("Send backward"), "Ctrl+PgDown", "canvas"),
+    Action("align.left", N_("Align left edges"), "", "canvas"),
+    Action("align.hcenter", N_("Align horizontal centers"), "", "canvas"),
+    Action("align.right", N_("Align right edges"), "", "canvas"),
+    Action("align.top", N_("Align top edges"), "", "canvas"),
+    Action("align.vcenter", N_("Align vertical centers"), "", "canvas"),
+    Action("align.bottom", N_("Align bottom edges"), "", "canvas"),
+    Action("align.paper_left", N_("Align left on paper"), "", "canvas"),
+    Action("align.paper_hcenter", N_("Center horizontally on paper"), "", "canvas"),
+    Action("align.paper_right", N_("Align right on paper"), "", "canvas"),
+    Action("align.paper_top", N_("Align top on paper"), "", "canvas"),
+    Action("align.paper_vcenter", N_("Center vertically on paper"), "", "canvas"),
+    Action("align.paper_bottom", N_("Align bottom on paper"), "", "canvas"),
+    Action("size.maximize", N_("Maximize on paper"), "", "canvas"),
+    Action("size.same", N_("Same size"), "", "canvas"),
+    Action("size.width", N_("Same width"), "", "canvas"),
+    Action("size.height", N_("Same height"), "", "canvas"),
+    Action("text.start_edit", N_("Start text editing (selected text)"), "F2", "canvas"),
+    Action("text.start_edit_enter", N_("Start text editing (Enter)"), "Return", "canvas",
            fixed=True),
-    Action("text.end_edit", "Schreibmodus beenden", "Esc", "edit", fixed=True),
-    Action("text.bold", "Fett", "Ctrl+B", "edit"),
-    Action("text.italic", "Kursiv", "Ctrl+I", "edit"),
-    Action("text.underline", "Unterstrichen", "Ctrl+U", "edit"),
+    Action("text.end_edit", N_("End text editing"), "Esc", "edit", fixed=True),
+    Action("text.bold", N_("Bold"), "Ctrl+B", "edit"),
+    Action("text.italic", N_("Italic"), "Ctrl+I", "edit"),
+    Action("text.underline", N_("Underline"), "Ctrl+U", "edit"),
 )
 
 _BY_ID = {a.id: a for a in ACTIONS}
@@ -139,7 +141,7 @@ def normalize(seq: str) -> str:
         return ""
     parsed = _parse(seq) if isinstance(seq, str) else None
     if parsed is None:
-        raise ValueError(f"Ungültiges Tastenkürzel {seq!r}")
+        raise ValueError(_("Invalid shortcut {seq!r}").format(seq=seq))
     mods, key = parsed
     key = _KEY_ALIASES.get(key.casefold(), key.upper() if len(key) == 1 else key.capitalize())
     return "+".join([m for m in _MODIFIERS if m in mods] + [key])
@@ -192,8 +194,9 @@ def without_conflicts(mapping: dict[str, str]) -> tuple[dict[str, str], list[str
             kept.append((key, entry.id))
             continue
         clean[entry.id] = ""
-        warnings.append(f"Tastenkürzel doppelt belegt: {seq} ({_BY_ID[other].name}, "
-                        f"{entry.name}) – „{entry.name}“ ohne Kürzel.")
+        warnings.append(_("Shortcut assigned twice: {keys} ({first}, {second}) – “{second}” "
+                          "has no shortcut now.").format(keys=seq, first=_(_BY_ID[other].name),
+                                                         second=_(entry.name)))
     return clean, warnings
 
 
@@ -207,23 +210,28 @@ def validate(overrides) -> tuple[dict[str, str], list[str]]:
     Unbekannte Aktionen und ungültige Kürzel werden mit Warnung verworfen (Standard gilt);
     „“ ist erlaubt und heißt „kein Kürzel“."""
     if not isinstance(overrides, dict):
-        return {}, [f"Einstellung 'shortcuts' ungültig ({overrides!r}) – Standardkürzel aktiv."]
+        return {}, [_("Setting 'shortcuts' invalid ({value!r}) – default shortcuts active.")
+                    .format(value=overrides)]
     clean: dict[str, str] = {}
     warnings: list[str] = []
     for action_id, seq in overrides.items():
         if action_id not in _BY_ID:
-            warnings.append(f"Tastenkürzel für unbekannte Aktion {action_id!r} ignoriert.")
+            warnings.append(_("Shortcut for unknown action {action!r} ignored.")
+                            .format(action=action_id))
         elif not isinstance(seq, str) or not is_well_formed(seq):
-            warnings.append(f"Tastenkürzel für {action_id!r} ungültig ({seq!r}) – "
-                            f"Standard {_BY_ID[action_id].default!r} aktiv.")
+            warnings.append(_("Shortcut for {action!r} invalid ({keys!r}) – default {default!r} "
+                              "active.").format(action=action_id, keys=seq,
+                                                default=_BY_ID[action_id].default))
         elif (normalize(seq) in _RESERVED
               and normalize(seq) != normalize(_BY_ID[action_id].default)):
-            warnings.append(f"Tastenkürzel für {action_id!r} ungültig ({seq}) – Esc, Enter und "
-                            f"Tab sind nicht belegbar; Standard "
-                            f"{_BY_ID[action_id].default!r} aktiv.")
+            warnings.append(_("Shortcut for {action!r} invalid ({keys}) – Esc, Enter and Tab "
+                              "cannot be assigned; default {default!r} active.")
+                            .format(action=action_id, keys=seq,
+                                    default=_BY_ID[action_id].default))
         elif _BY_ID[action_id].fixed and normalize(seq) != normalize(_BY_ID[action_id].default):
-            warnings.append(f"Tastenkürzel für {action_id!r} ist fest "
-                            f"({_BY_ID[action_id].default}) – Einstellung ignoriert.")
+            warnings.append(_("Shortcut for {action!r} is fixed ({default}) – setting "
+                              "ignored.").format(action=action_id,
+                                                 default=_BY_ID[action_id].default))
         else:
             clean[action_id] = seq
     return clean, warnings
diff --git a/src/labelwerk/storage.py b/src/labelwerk/storage.py
index c93820f..4818ecc 100644
--- a/src/labelwerk/storage.py
+++ b/src/labelwerk/storage.py
@@ -30,6 +30,7 @@ from .document import (ALIGNMENTS, BARCODE_KINDS, BARCODE_MM, COLORS, CUTS, FRAM
                        MAX_NUMBER, MODULE_LIMIT, MAX_POSITION_MM, MAX_SERIES_ROWS, ORIENTATIONS,
                        QR_LEVELS, ROTATIONS, BarcodeObject, Document, Frame, ImageObject, Numbering,
                        Paragraph, Series, Span, TextObject)
+from .i18n import _
 from .imaging import MAX_PIXELS, MODES
 from .labels import get_label
 
@@ -133,16 +134,16 @@ class StorageError(ValueError):
 def os_reason(error: OSError) -> str:
     """Grund eines Datei-Fehlers auf Deutsch (statt englischem Text des Betriebssystems)."""
     if isinstance(error, FileNotFoundError):
-        return "Ordner fehlt"
+        return _("folder missing")
     if isinstance(error, IsADirectoryError):
-        return "ist ein Ordner"
+        return _("is a folder")
     if isinstance(error, PermissionError):
-        return "keine Berechtigung"
+        return _("no permission")
     if getattr(error, "errno", None) == 36:     # ENAMETOOLONG
-        return "Name zu lang"
+        return _("name too long")
     if getattr(error, "errno", None) == 28:     # ENOSPC
-        return "kein Platz auf dem Datenträger"
-    return "Fehler beim Zugriff"
+        return _("no space left on the disk")
+    return _("access error")
 
 
 def exists(path: str | Path) -> bool:
@@ -204,9 +205,11 @@ def save(doc: Document, path: str | Path) -> Path:
                           allow_nan=False) + "\n"
         text.encode("utf-8")                # einzelne Surrogates lassen sich nicht schreiben
     except UnicodeEncodeError as e:
-        raise OSError(f"{path.name} wurde nicht gespeichert: ungültige Zeichen im Text") from e
+        raise OSError(_("{name} was not saved: invalid characters in the text").format(
+            name=path.name)) from e
     except ValueError as e:
-        raise OSError(f"{path.name} wurde nicht gespeichert: ungültige Zahlen im Etikett") from e
+        raise OSError(_("{name} was not saved: invalid numbers in the label").format(
+            name=path.name)) from e
     tmp = None
     try:
         for attempt in range(100):          # freier Name für die temporäre Datei
@@ -227,7 +230,8 @@ def save(doc: Document, path: str | Path) -> Path:
         os.replace(tmp, target)
         tmp = None
     except OSError as e:
-        raise OSError(f"{path.name} wurde nicht gespeichert ({os_reason(e)})") from e
+        raise OSError(_("{name} was not saved ({reason})").format(name=path.name,
+                                                              reason=os_reason(e))) from e
     finally:
         if tmp is not None:
             Path(tmp).unlink(missing_ok=True)
@@ -243,31 +247,43 @@ def _check(value, kind: str, key: str, where: str):
         return None
     if not _KINDS[kind](value):
         if kind == "label":
-            raise StorageError(f"Etikett{where} unbekannt: {reprlib.repr(value)}")
-        raise StorageError(f"Wert für „{key}“{where} ungültig: {reprlib.repr(value)}")
+            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+            raise StorageError(_("Unknown label{where}: {value}").format(where=where,
+                                                                      value=reprlib.repr(value)))
+        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+        raise StorageError(_("Invalid value for “{key}”{where}: {value}").format(
+            key=key, where=where, value=reprlib.repr(value)))
     if kind == "span_text" and any(c in value for c in LINE_BREAKS):
-        raise StorageError(f"Zeilenumbruch in „{key}“{where} – Zeilen sind eigene Absätze")
+        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+        raise StorageError(_("Line break in “{key}”{where} – lines are separate paragraphs").format(
+            key=key, where=where))
     if kind == "bytes":
         try:
             return base64.b64decode(value, validate=True)
         except (binascii.Error, ValueError) as e:
-            raise StorageError(f"Bilddaten „{key}“{where} nicht lesbar") from e
+            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+            raise StorageError(_("Image data “{key}”{where} not readable").format(
+                key=key, where=where)) from e
     return value
 
 
 def _load(data, schema: dict, where: str, required: tuple[str, ...] = ()) -> dict:
     if not isinstance(data, dict):
-        raise StorageError(f"Eintrag{where} ist kein Objekt")
+        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+        raise StorageError(_("Entry{where} is not an object").format(where=where))
     for key in required:
         if key not in data:
-            raise StorageError(f"„{key}“{where} fehlt")
+            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+            raise StorageError(_("“{key}”{where} missing").format(key=key, where=where))
     return {key: _check(data[key], kind, key, where) for key, kind in schema.items() if key in data}
 
 
 def _list(data: dict, key: str, where: str) -> list:
     value = data.get(key, [])
     if not isinstance(value, list):
-        raise StorageError(f"Wert für „{key}“{where} ungültig: {reprlib.repr(value)}")
+        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+        raise StorageError(_("Invalid value for “{key}”{where}: {value}").format(
+            key=key, where=where, value=reprlib.repr(value)))
     return value
 
 
@@ -277,27 +293,34 @@ def _image(data: dict, where: str) -> ImageObject:
         with Image.open(io.BytesIO(values["png"]), formats=["PNG"]) as img:
             size = img.size
             if max(size) > MAX_PIXELS:
-                raise StorageError(f"Bild{where} zu groß ({size[0]} × {size[1]} Pixel, "
-                                   f"höchstens {MAX_PIXELS})")
+                # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+                raise StorageError(_("Image{where} too large ({width} × {height} pixels, at most "
+                                     "{limit})").format(where=where, width=size[0], height=size[1],
+                                                        limit=MAX_PIXELS))
             img.load()                      # ganz dekodieren: kaputte Daten fallen jetzt auf
     except StorageError:
         raise
     except Exception as e:  # Pillow wirft je nach Schaden verschiedene Fehler
-        raise StorageError(f"Bilddaten{where} nicht lesbar (nur PNG)") from e
+        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+        raise StorageError(_("Image data{where} not readable (PNG only)").format(where=where)) from e
     crop = values.get("crop")
     if crop is not None and not (0 <= crop[0] < crop[2] <= size[0]
                                  and 0 <= crop[1] < crop[3] <= size[1]):
-        raise StorageError(f"Wert für „crop“{where} liegt nicht im Bild: {crop}")
+        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+        raise StorageError(_("Value for “crop”{where} is not inside the image: {crop}").format(
+            where=where, crop=crop))
     return ImageObject(**values)
 
 
 def _series(data) -> Series:
-    values = _load(data, SERIES, " in der Serie")
+    # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+    values = _load(data, SERIES, _(" in the series"))
     numbering = data.get("numbering")
     if numbering is not None:
-        values["numbering"] = Numbering(**_load(numbering, NUMBERING, " in der Nummerierung"))
+        # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+        values["numbering"] = Numbering(**_load(numbering, NUMBERING, _(" in the numbering")))
     if (values.get("source") is None) == (numbering is None):
-        raise StorageError("Serie braucht genau eins: Tabelle oder Nummerierung")
+        raise StorageError(_("A series needs exactly one: table or numbering"))
     return Series(**values)
 
 
@@ -332,18 +355,20 @@ def _relative(source: str, base: str | Path) -> str:
 def from_dict(data, base: str | Path | None = None) -> Document:
     """``base``: Ordner der Datei – relative Tabellenpfade gelten von dort aus."""
     if not isinstance(data, dict) or data.get("format") != FORMAT:
-        raise StorageError("keine labelwerk-Datei")
+        raise StorageError(_("not a labelwerk file"))
     version = data.get("version")
     if not _int(version) or version < 1:
-        raise StorageError(f"keine labelwerk-Datei (Format-Version {reprlib.repr(version)})")
+        raise StorageError(_("not a labelwerk file (format version {version})").format(
+            version=reprlib.repr(version)))
     if version > VERSION:
-        raise StorageError(f"mit einem neueren labelwerk gespeichert (Format-Version {version}) "
-                           f"– bitte labelwerk aktualisieren")
+        raise StorageError(_("saved with a newer labelwerk (format version {version}) – please "
+                             "update labelwerk").format(version=version))
     document = data.get("document")
     values = _load(document, DOCUMENT, "")
     frame = document.get("frame")
     if frame is not None:                   # fehlt oder null: kein Rahmen
-        values["frame"] = Frame(**_load(frame, FRAME, " im Rahmen"))
+        # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+        values["frame"] = Frame(**_load(frame, FRAME, _(" in the border")))
     if document.get("series") is not None:  # fehlt oder null: keine Serie
         values["series"] = _series(document["series"])
         source = values["series"].source
@@ -352,10 +377,12 @@ def from_dict(data, base: str | Path | None = None) -> Document:
                                        source=str(Path(os.path.realpath(base)) / source))
     items = _list(document, "objects", "")
     if len(items) > MAX_OBJECTS:
-        raise StorageError(f"Etikett zu groß ({len(items)} Objekte, höchstens {MAX_OBJECTS})")
+        raise StorageError(_("Label too large ({count} objects, at most {limit})").format(
+            count=len(items), limit=MAX_OBJECTS))
     objects = []
     for number, item in enumerate(items, start=1):
-        where = f" in Objekt {number}"
+        # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
+        where = _(" in object {number}").format(number=number)
         kind = item.get("type") if isinstance(item, dict) else None
         if kind == "text":
             objects.append(_text_object(item, where))
@@ -364,16 +391,18 @@ def from_dict(data, base: str | Path | None = None) -> Document:
         elif kind == "barcode":
             objects.append(BarcodeObject(**_load(item, BARCODE, where, required=("kind", "data"))))
         else:
-            raise StorageError(f"Objektart{where} unbekannt: {reprlib.repr(kind)}")
+            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
+            raise StorageError(_("Unknown object type{where}: {kind}").format(where=where,
+                                                                               kind=reprlib.repr(kind)))
     total = sum(len(o.data) for o in objects if isinstance(o, BarcodeObject))
     if total > MAX_BARCODE_TOTAL:
-        raise StorageError(f"Etikett zu groß (Barcode-Inhalte zusammen {total} Zeichen, höchstens "
-                           f"{MAX_BARCODE_TOTAL})")
+        raise StorageError(_("Label too large (barcode contents together {total} characters, at "
+                             "most {limit})").format(total=total, limit=MAX_BARCODE_TOTAL))
     dpi = get_label(values.get("label_id", Document().label_id)).dpi
     dots = sum(_dots(o, dpi) for o in objects)
     if dots > MAX_FRAME_DOTS:
-        raise StorageError(f"Etikett zu groß (Objekte zusammen {dots / 1e6:.0f} Mio. Druckpunkte, "
-                           f"höchstens {MAX_FRAME_DOTS // 1_000_000})")
+        raise StorageError(_("Label too large (objects together {dots:.0f} million dots, at most "
+                             "{limit})").format(dots=dots / 1e6, limit=MAX_FRAME_DOTS // 1_000_000))
     return Document(**values, objects=objects)
 
 
@@ -394,7 +423,7 @@ def _dots(obj, dpi: int) -> float:
 
 
 def _reject_constant(name: str):
-    raise ValueError(f"{name} ist keine Zahl")
+    raise ValueError(f"{name} is not a number")      # nur intern (json)
 
 
 def load(path: str | Path) -> Document:
@@ -405,28 +434,31 @@ def load(path: str | Path) -> Document:
         if stat.S_ISDIR(info.st_mode):
             raise IsADirectoryError(path)
         if not stat.S_ISREG(info.st_mode):      # ein FIFO o. Ä. würde beim Lesen hängen
-            raise StorageError(f"{path.name}: keine Datei")
+            raise StorageError(_("{name}: not a file").format(name=path.name))
         if info.st_size > MAX_FILE_BYTES:
-            raise StorageError(f"{path.name}: Datei zu groß")
+            raise StorageError(_("{name}: file too large").format(name=path.name))
         text = path.read_text(encoding="utf-8-sig")       # auch mit BOM (Windows-Editoren)
     except FileNotFoundError as e:
-        raise StorageError(f"Datei nicht gefunden: {path}") from e
+        raise StorageError(_("File not found: {path}").format(path=path)) from e
     except OSError as e:
-        raise StorageError(f"{path.name} kann nicht gelesen werden ({os_reason(e)})") from e
+        raise StorageError(_("{name} cannot be read ({reason})").format(
+            name=path.name, reason=os_reason(e))) from e
     except UnicodeDecodeError as e:
-        raise StorageError(f"{path.name}: keine labelwerk-Datei (kein UTF-8-Text)") from e
+        raise StorageError(_("{name}: not a labelwerk file (not UTF-8 text)").format(
+            name=path.name)) from e
     try:
         data = json.loads(text, parse_constant=_reject_constant)   # NaN, Infinity
     except RecursionError as e:
-        raise StorageError(f"{path.name}: Datei beschädigt (zu tief verschachtelt)") from e
+        raise StorageError(_("{name}: file damaged (nested too deeply)").format(
+            name=path.name)) from e
     except ValueError as e:
-        raise StorageError(f"{path.name}: keine labelwerk-Datei oder beschädigt") from e
+        raise StorageError(_("{name}: not a labelwerk file or damaged").format(name=path.name)) from e
     try:
         return from_dict(data, path.parent)
     except StorageError as e:
         raise StorageError(f"{path.name}: {e}") from e
     except (TypeError, AttributeError, KeyError, RecursionError, OverflowError) as e:
-        raise StorageError(f"{path.name}: Datei beschädigt") from e   # Sicherheitsnetz
+        raise StorageError(_("{name}: file damaged").format(name=path.name)) from e   # Sicherheitsnetz
 
 
 def add_recent_file(recent: list[str], path: str, limit: int = RECENT_FILES) -> list[str]:
diff --git a/src/labelwerk/zpl.py b/src/labelwerk/zpl.py
index d1eab59..30ccc27 100644
--- a/src/labelwerk/zpl.py
+++ b/src/labelwerk/zpl.py
@@ -21,6 +21,7 @@ from urllib.parse import urlsplit
 from PIL import Image
 
 from .cups import CutOption
+from .i18n import N_, _
 from .labels import sized_id
 
 PREFIX = "zpl:"                    # Modell-ID: zpl:203, zpl:300, zpl:600 (Name wie beim Hersteller)
@@ -37,10 +38,17 @@ MAX_GRAPHIC = 99_999               # Bytes je ^GFA (ältere Firmware) – größ
 # gängige Etiketten (Breite × Höhe in mm): 2×1", 57×32, 3×2", 4×2", 4×3", 4×4", 4×6" …
 MEDIA = ((51, 25), (57, 32), (38, 25), (60, 40), (76, 51), (102, 51), (102, 76), (102, 102),
          (102, 152))
-# Nach dem Druck: "" = wie am Drucker eingestellt (kein ^MM), sonst ^MMT/C/P
-MODES = {"": "Wie am Drucker eingestellt", "T": "Abreißen", "C": "Schneiden (nur mit Abschneider)",
-         "P": "Ablösen (nur mit Spender)"}
-CUT_OPTION = CutOption("mode", "Nach dem Druck", tuple(MODES), "", tuple(MODES.values()))
+# Nach dem Druck: "" = wie am Drucker eingestellt (kein ^MM), sonst ^MMT/C/P; Titel und Namen nur
+# markiert – angezeigt übersetzt über ``cut_option()``
+MODES = {"": N_("As set on the printer"), "T": N_("Tear off"), "C": N_("Cut (cutter only)"),
+         "P": N_("Peel off (dispenser only)")}
+CUT_OPTION = CutOption("mode", N_("After printing"), tuple(MODES), "", tuple(MODES.values()))
+
+
+def cut_option() -> CutOption:
+    """``CUT_OPTION`` zum Anzeigen: Titel und Namen der Modi in der eingestellten Sprache."""
+    return CutOption(CUT_OPTION.key, _(CUT_OPTION.title), CUT_OPTION.choices, CUT_OPTION.default,
+                     tuple(_(text) for text in CUT_OPTION.labels))
 
 
 class ZplError(Exception):
@@ -76,7 +84,7 @@ def speaks_zpl(ieee1284: str) -> bool:
     """Versteht der Drucker ZPL? Nennt seine Kennung Befehlssätze (``CMD:``/``COMMAND SET:``)
     ohne ZPL (EPL-Geräte wie LP 2844, Kartendrucker), nicht; ohne Angabe: ja."""
     for part in ieee1284.split(";"):
-        key, _, value = part.partition(":")
+        key, __, value = part.partition(":")
         if key.strip().upper() in ("CMD", "COMMAND SET"):
             return "ZPL" in value.upper()
     return True
@@ -146,7 +154,8 @@ def fields(image: Image.Image) -> str:
 def label(image: Image.Image, mode: str = "") -> bytes:
     """ZPL eines Etiketts: ``^XA [^MM<Modus>] ^PW ^LL ^LH0,0 ^FO…^GFA…^FS ^PQ1 ^XZ``."""
     if mode not in MODES:
-        raise ValueError(f"Unbekannter Modus {mode!r} – erlaubt: {', '.join(m for m in MODES if m)}")
+        raise ValueError(_("Unknown mode {mode!r} – allowed: {allowed}").format(
+            mode=mode, allowed=", ".join(m for m in MODES if m)))
     head = f"^MM{mode}" if mode else ""
     return (f"^XA{head}^PW{image.width}^LL{image.height}^LH0,0{fields(image)}^PQ1^XZ\n"
             .encode("ascii"))
@@ -177,7 +186,7 @@ def send(data: bytes | Iterable[bytes], uri: str) -> None:
         return _send_device(chunks, uri[len("zpl+file://"):])
     if uri.startswith("zpl+tcp://"):
         return _send_network(chunks, uri)
-    raise ZplError(f"Keine Zebra-Adresse: {uri}")
+    raise ZplError(_("Not a Zebra address: {uri}").format(uri=uri))
 
 
 def _send_device(chunks: Iterable[bytes], path: str) -> None:
@@ -186,30 +195,34 @@ def _send_device(chunks: Iterable[bytes], path: str) -> None:
     try:
         fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
     except FileNotFoundError:
-        raise ZplError(f"Zebra-Drucker nicht gefunden: {path} – eingeschaltet, Kabel?") from None
+        raise ZplError(_("Zebra printer not found: {path} – switched on, cable?").format(
+            path=path)) from None
     except PermissionError:
-        raise ZplError(f"Keine Berechtigung für {path} – Benutzer in Gruppe 'lp'?") from None
+        raise ZplError(_("No permission for {device} – is the user in group 'lp'?").format(
+            device=path)) from None
     except OSError as e:
-        raise ZplError(f"Zebra-Drucker nicht erreichbar: {path} ({e.strerror or e})") from None
+        raise ZplError(_("Zebra printer not reachable: {path} ({reason})").format(
+            path=path, reason=e.strerror or e)) from None
     sent = 0
     try:
         if not _is_device(os.fstat(fd)):
-            raise ZplError(f"{path} ist kein Druckergerät")
+            raise ZplError(_("{path} is not a printer device").format(path=path))
         poller = select.poll()
         poller.register(fd, select.POLLOUT)
         for chunk in chunks:
             view = memoryview(chunk)
             while view:
                 if not poller.poll(WRITE_TIMEOUT_S * 1000):
-                    raise ZplError(f"Zebra-Drucker nimmt keine Daten an ({sent} Bytes gesendet) – "
-                                   "Papier, Farbband, Pause?")
+                    raise ZplError(_("Zebra printer does not accept data ({sent} bytes sent) – "
+                                     "paper, ribbon, paused?").format(sent=sent))
                 try:
                     n = os.write(fd, view[:CHUNK])
                 except BlockingIOError:
                     continue
                 view, sent = view[n:], sent + n
     except OSError as e:
-        raise ZplError(f"Senden an {path} abgebrochen nach {sent} Bytes ({e.strerror or e})") from None
+        raise ZplError(_("Sending to {path} aborted after {sent} bytes ({reason})").format(
+            path=path, sent=sent, reason=e.strerror or e)) from None
     finally:
         os.close(fd)
 
@@ -221,14 +234,15 @@ def _send_network(chunks: Iterable[bytes], uri: str) -> None:
     try:
         port = parts.port or PORT
     except ValueError:
-        raise ZplError(f"Ungültige Adresse: {uri}") from None
+        raise ZplError(_("Invalid address: {uri}").format(uri=uri)) from None
     if not parts.hostname:
-        raise ZplError(f"Ungültige Adresse: {uri}")
+        raise ZplError(_("Invalid address: {uri}").format(uri=uri))
     try:
         conn = socket.create_connection((parts.hostname, port), timeout=TIMEOUT_S)
     except OSError as e:
-        raise ZplError(f"Zebra-Drucker {parts.hostname} nicht erreichbar ({e.strerror or e}) – "
-                       "eingeschaltet, im selben Netz, Adresse richtig?") from None
+        raise ZplError(_("Zebra printer {host} not reachable ({reason}) – switched on, in the "
+                         "same network, address correct?").format(
+            host=parts.hostname, reason=e.strerror or e)) from None
     sent = 0
     with conn:
         conn.settimeout(WRITE_TIMEOUT_S)
@@ -239,5 +253,5 @@ def _send_network(chunks: Iterable[bytes], uri: str) -> None:
                     n = conn.send(view[:CHUNK])
                     view, sent = view[n:], sent + n
         except OSError as e:
-            raise ZplError(f"Verbindung zu {parts.hostname} abgebrochen nach {sent} Bytes "
-                           f"({e.strerror or e})") from None
+            raise ZplError(_("Connection to {host} aborted after {sent} bytes ({reason})").format(
+                host=parts.hostname, sent=sent, reason=e.strerror or e)) from None
diff --git a/tools/clipart/de.json b/tools/clipart/de.json
index 38024f7..5cd6fa7 100644
--- a/tools/clipart/de.json
+++ b/tools/clipart/de.json
@@ -1140,6 +1140,7 @@
     "M070": "Lampe nur in Leuchte mit Abdeckung verwenden",
     "M071": "Kippsicherung verwenden",
     "M072": "Dekontaminationsdusche benutzen",
+    "P035": "Benutzen mit genagelten Schuhen verboten",
     "P060": "Tragen von Straßenschuhen verboten",
     "P073": "Deckel nicht schließen, solange die Brenner in Betrieb sind",
     "P074": "Kindersitz-Einbau verboten",
diff --git a/tools/clipart/en.json b/tools/clipart/en.json
new file mode 100644
index 0000000..b0d598e
--- /dev/null
+++ b/tools/clipart/en.json
@@ -0,0 +1,373 @@
+{
+ "iso7000": {
+  "0621": "Fragile",
+  "0622": "Use no hooks",
+  "0623": "This way up",
+  "0624": "Keep away from heat",
+  "0625": "Sling here",
+  "0626": "Keep dry",
+  "0627": "Centre of gravity",
+  "0628": "Do not roll",
+  "0629": "Use no hand truck here",
+  "0630": "Stacking limitation",
+  "0631": "Clamp here",
+  "0632": "Temperature limits",
+  "2406": "Do not use forklift"
+ },
+ "iso7010_kinds": {
+  "W": "Warning signs",
+  "P": "Prohibition signs",
+  "M": "Mandatory signs",
+  "E": "Safe condition signs",
+  "F": "Fire safety signs"
+ },
+ "subgroups": {
+  "Elektro": "Electrical",
+  "Packzeichen (ISO 780)": "Packaging symbols (ISO 780)",
+  "Sonstiges": "Other"
+ },
+ "eigene": {
+  "erde": "Earth",
+  "schutzleiter": "Protective earth (PE)",
+  "masse": "Frame / chassis",
+  "wechselstrom": "Alternating current (AC)",
+  "gleichstrom": "Direct current (DC)",
+  "allstrom": "Direct and alternating current",
+  "hochspannung": "High voltage (lightning arrow)",
+  "gefahr_spannung": "Warning: electricity (warning triangle)",
+  "sicherung": "Fuse",
+  "motor": "Motor",
+  "generator": "Generator",
+  "transformator": "Transformer",
+  "steckdose": "Socket outlet",
+  "schalter": "Switch",
+  "taster": "Push button",
+  "lampe": "Lamp",
+  "batterie": "Battery",
+  "klemme": "Terminal",
+  "widerstand": "Resistor",
+  "kondensator": "Capacitor",
+  "diode": "Diode",
+  "schutzklasse_2": "Protection class II",
+  "schutzklasse_3": "Protection class III",
+  "nicht_stapeln": "Do not stack"
+ },
+ "iso7010": {
+  "E001": "Emergency exit (left hand)",
+  "E002": "Emergency exit (right hand)",
+  "E003": "First aid",
+  "E004": "Emergency telephone",
+  "E007": "Evacuation assembly point",
+  "E008": "Break to obtain access",
+  "E009": "Doctor",
+  "E010": "Automated external heart defibrillator",
+  "E011": "Eyewash station",
+  "E012": "Safety shower",
+  "E013": "Stretcher",
+  "E014": "Child seat presence and orientation detection system (CPOD)",
+  "E015": "Drinking water",
+  "E016": "Emergency window with escape ladder",
+  "E017": "Rescue window",
+  "E018": "Turn counterclockwise to open",
+  "E019": "Turn clockwise to open",
+  "E020": "Emergency stop",
+  "E021": "Area of refuge",
+  "E022": "Door opens by pushing on the left hand side",
+  "E023": "Door opens by pushing on the right hand side",
+  "E024": "Evacuation temporary refuge",
+  "E025": "Emergency hammer",
+  "E026": "Emergency exit for people unable to walk or with walking impairment (left hand)",
+  "E027": "Medical grab bag",
+  "E028": "Oxygen resuscitator",
+  "E029": "Emergency escape breathing device",
+  "E030": "Emergency exit for people unable to walk or with walking impairment (right hand)",
+  "E031": "Shipboard general alarm",
+  "E032": "Shipboard muster station",
+  "E033": "Door slides right to open",
+  "E034": "Door slides left to open",
+  "E035": "Liferaft knife",
+  "E036": "Lifeboat",
+  "E037": "Rescue boat",
+  "E038": "Liferaft",
+  "E039": "Davit-launched liferaft",
+  "E040": "Lifebuoy",
+  "E041": "Lifebuoy with line",
+  "E042": "Lifebuoy with light",
+  "E043": "Lifebuoy with line and light",
+  "E044": "Lifejacket",
+  "E045": "Child's lifejacket",
+  "E046": "Infant's lifejacket",
+  "E047": "Search and rescue transponder (SART)",
+  "E048": "Survival craft distress signals",
+  "E049": "Rocket parachute flares",
+  "E050": "Line-throwing appliance",
+  "E051": "Two-way VHF radiotelephone apparatus",
+  "E052": "Emergency position-indicating radio beacon (EPIRB)",
+  "E053": "Embarkation ladder",
+  "E054": "Marine evacuation slide",
+  "E055": "Marine evacuation chute",
+  "E056": "Immersion suit",
+  "E057": "Door opens by pulling on the left hand side",
+  "E058": "Door opens by pulling on the right hand side",
+  "E059": "Escape ladder",
+  "E060": "Evacuation chair",
+  "E061": "Water rescue equipment",
+  "E062": "Tsunami evacuation area",
+  "E063": "Tsunami evacuation building",
+  "E064": "First aid responder",
+  "E065": "Natural disaster outdoor refuge area",
+  "E067": "Evacuation mattress",
+  "E068": "Lifebuoy with light and smoke",
+  "E069": "Person overboard call point",
+  "E070": "Evacuation lift for people unable to use stairs",
+  "E071": "Rescue toboggan",
+  "E072": "Safe anchorage point",
+  "E073": "Emergency descent device",
+  "E074": "Emergency rations",
+  "E075": "Lifeguard",
+  "E076": "Evacuation equipment",
+  "F001": "Fire extinguisher",
+  "F002": "Fire hose reel",
+  "F003": "Fire ladder",
+  "F004": "Collection of firefighting equipment",
+  "F005": "Fire alarm call point",
+  "F006": "Fire emergency telephone",
+  "F007": "Fire door",
+  "F008": "Fixed fire extinguishing battery",
+  "F009": "Wheeled fire extinguisher",
+  "F010": "Portable foam applicator unit",
+  "F011": "Water fog applicator",
+  "F012": "Fixed fire extinguishing installation",
+  "F013": "Fixed fire extinguishing bottle",
+  "F014": "Remote release station",
+  "F015": "Fire monitor",
+  "F016": "Fire blanket",
+  "F017": "Firefighters' lift",
+  "F018": "Fire alarm flashing light",
+  "F019": "Unconnected fire hose",
+  "M001": "General mandatory action sign",
+  "M003": "Wear ear protection",
+  "M004": "Wear eye protection",
+  "M005": "Connect an earth terminal to the ground",
+  "M006": "Disconnect mains plug from electrical outlet",
+  "M007": "Opaque eye protection must be worn",
+  "M008": "Wear safety footwear",
+  "M009": "Wear protective gloves",
+  "M010": "Wear protective clothing",
+  "M011": "Wash your hands",
+  "M012": "Use handrail",
+  "M013": "Wear a face shield",
+  "M014": "Wear head protection",
+  "M015": "Wear high-visibility clothing",
+  "M016": "Wear a mask",
+  "M017": "Wear respiratory protection",
+  "M018": "Wear a safety harness",
+  "M019": "Wear a welding mask",
+  "M020": "Wear safety belts",
+  "M021": "Disconnect before carrying out maintenance or repair",
+  "M022": "Use barrier cream",
+  "M023": "Use footbridge",
+  "M024": "Use this walkway",
+  "M025": "Protect infants' eyes with opaque eye protection",
+  "M026": "Wear a protective apron",
+  "M027": "Check guard",
+  "M028": "Install locks and keep locked",
+  "M029": "Sound your horn",
+  "M030": "Place trash in the bin",
+  "M031": "Use the table saw guard",
+  "M032": "Use footwear with anti-static or anti-spark features",
+  "M033": "Close the chairlift safety bar",
+  "M034": "Open the chairlift safety bar",
+  "M035": "Leave the tow track after a fall",
+  "M036": "Keep ski tips up",
+  "M037": "Close and secure the hatches (lifeboat)",
+  "M038": "Start the engine (lifeboat)",
+  "M039": "Lower the lifeboat to the water",
+  "M040": "Lower the lifeboat to the water (davit)",
+  "M041": "Lower the rescue boat to the water",
+  "M042": "Release the lifeboat hooks",
+  "M043": "Start the lifeboat water spray",
+  "M044": "Start the lifeboat air supply",
+  "M045": "Release the gripes (lifeboat)",
+  "M046": "Secure gas cylinders",
+  "M047": "Use breathing equipment",
+  "M048": "Use gas detector",
+  "M049": "Use personal protective equipment for sport",
+  "M050": "Exit the toboggan to the left",
+  "M051": "Exit the toboggan to the right",
+  "M052": "Keep a safe distance between toboggans",
+  "M053": "Wear personal flotation device",
+  "M054": "Supervise children in aquatic activities",
+  "M056": "Ventilate before and during entering",
+  "M057": "Ensure continuous ventilation",
+  "M058": "Entry only with supervisor outside",
+  "M059": "Wear laboratory coat",
+  "M060": "Hold the trolley handle",
+  "M061": "Disinfect your hands",
+  "M062": "Disinfect surface",
+  "M063": "Remove ski pole straps from wrists",
+  "M064": "Hold two ski poles with a single hand",
+  "M065": "Children must be accompanied",
+  "M066": "Wear a sports helmet",
+  "M067": "Wear snow goggles",
+  "M068": "Lock moving mechanical parts",
+  "M069": "Tools must be tethered",
+  "M072": "Use decontamination shower",
+  "P001": "General prohibition sign",
+  "P002": "No smoking",
+  "P003": "No open flame",
+  "P004": "No thoroughfare",
+  "P005": "Not drinking water",
+  "P006": "No access for forklift trucks and other industrial vehicles",
+  "P007": "No access for people with active implanted cardiac devices",
+  "P009": "No climbing",
+  "P010": "Do not touch",
+  "P011": "Do not extinguish with water",
+  "P012": "No heavy load",
+  "P013": "No activated mobile phones",
+  "P014": "No access for people with metallic implants",
+  "P015": "No reaching in",
+  "P016": "Do not spray with water",
+  "P020": "Do not use lift in the event of fire",
+  "P021": "No dogs",
+  "P022": "No eating or drinking",
+  "P023": "Do not obstruct",
+  "P024": "Do not walk or stand here",
+  "P027": "Do not use this lift for people",
+  "P028": "Do not wear gloves",
+  "P031": "Do not alter the state of the switch",
+  "P032": "Not to be used for side grinding",
+  "P033": "Not to be used for wet grinding",
+  "P034": "Not to be used for free-hand and hand-held grinding",
+  "P035": "Do not wear metal-studded footwear",
+  "P036": "No children allowed",
+  "P037": "Do not leave the tow track",
+  "P038": "Do not swing the chair",
+  "P039": "No hot work",
+  "P040": "No fireworks",
+  "P041": "Do not lean",
+  "P042": "Not for pregnant women",
+  "P043": "Not for intoxicated persons",
+  "P044": "No use of smart glasses",
+  "P045": "No campfires",
+  "P046": "Do not lean out of the toboggan",
+  "P047": "Do not ram other toboggans",
+  "P048": "No running",
+  "P049": "No swimming",
+  "P050": "No snorkelling",
+  "P051": "No sub-aqua diving",
+  "P052": "No diving",
+  "P053": "No sailing",
+  "P054": "No windsurfing",
+  "P055": "No manually powered craft",
+  "P056": "No mechanically powered craft",
+  "P057": "No personal water craft",
+  "P058": "No towed water activities",
+  "P059": "No surf craft",
+  "P060": "No outdoor footwear",
+  "P061": "No jumping into water",
+  "P062": "No pushing into water",
+  "P063": "No body boarding",
+  "P064": "No surfing between the red and yellow flags",
+  "P065": "No kitesurfing",
+  "P066": "No parasailing",
+  "P067": "No sand yachting",
+  "P068": "Do not expose to direct sunlight or hot surfaces",
+  "P069": "Not to be serviced by users",
+  "P070": "Do not put fingers into hydromassage nozzles",
+  "P071": "Do not cross the barrier",
+  "P072": "No jumping down",
+  "P073": "Do not close the lid while burners are operating",
+  "P074": "Do not install a child seat",
+  "P075": "Do not stare at the light source",
+  "P076": "No skiing",
+  "P077": "No snowboarding",
+  "P078": "No sledging",
+  "P079": "No ice skating",
+  "P080": "No access for unauthorized persons",
+  "W001": "General warning sign",
+  "W002": "Explosive material",
+  "W003": "Radioactive material or ionizing radiation",
+  "W004": "Laser beam",
+  "W005": "Non-ionizing radiation",
+  "W006": "Magnetic field",
+  "W007": "Floor-level obstacle",
+  "W008": "Drop (fall)",
+  "W009": "Biological hazard",
+  "W010": "Low temperature/freezing conditions",
+  "W011": "Slippery surface",
+  "W012": "Electricity",
+  "W013": "Guard dog",
+  "W014": "Forklift trucks and other industrial vehicles",
+  "W015": "Overhead load",
+  "W016": "Toxic material",
+  "W017": "Hot surface",
+  "W018": "Automatic start-up",
+  "W019": "Crushing",
+  "W020": "Overhead obstacle",
+  "W021": "Flammable material",
+  "W022": "Sharp element",
+  "W023": "Corrosive substance",
+  "W024": "Crushing of hands",
+  "W025": "Counter-rotating rollers",
+  "W026": "Battery charging",
+  "W027": "Optical radiation",
+  "W028": "Oxidizing substance",
+  "W029": "Gas cylinder",
+  "W030": "Crushing of hands in press brake tool",
+  "W031": "Hand injury from workpiece at press brake",
+  "W032": "Rapid workpiece movement at press brake",
+  "W033": "Barbed wire",
+  "W034": "Bull",
+  "W035": "Falling objects",
+  "W036": "Fragile roof",
+  "W037": "Automated or remote-controlled vehicles",
+  "W038": "Sudden loud noise",
+  "W039": "Falling ice",
+  "W040": "Snow sliding off roof",
+  "W041": "Asphyxiating atmosphere",
+  "W042": "Arc flash",
+  "W043": "Thin ice",
+  "W044": "Slipway",
+  "W045": "Water skiing area",
+  "W046": "Surfers",
+  "W047": "Deep water",
+  "W048": "Shallow water",
+  "W049": "Submerged objects",
+  "W050": "Sudden drop in swimming pool depth",
+  "W051": "Unprotected edge",
+  "W052": "Unstable cliff edge",
+  "W053": "Unstable cliffs",
+  "W054": "Sharks",
+  "W055": "Sewage outfall",
+  "W056": "Tsunami hazard zone",
+  "W057": "Strong current",
+  "W058": "Boat traffic",
+  "W059": "Sand yachts",
+  "W060": "Incoming tide",
+  "W061": "Quicksand and mud",
+  "W062": "Kitesurfers",
+  "W063": "Parasailing",
+  "W064": "Strong wind",
+  "W065": "Large waves",
+  "W066": "Sudden drop to deep water",
+  "W067": "Crocodiles",
+  "W068": "Falling into water when boarding or leaving a floating surface",
+  "W069": "Jellyfish",
+  "W070": "Step down",
+  "W071": "Substance or mixture presenting a health hazard",
+  "W072": "Substance or mixture hazardous to the environment",
+  "W073": "Wildfire area",
+  "W074": "Tornado area",
+  "W075": "Active volcano",
+  "W076": "Debris flow",
+  "W077": "Flooding",
+  "W078": "Landslide",
+  "W079": "Hot contents",
+  "W080": "Hot steam",
+  "W082": "Hidden crevasses under snow",
+  "W083": "Avalanches",
+  "W084": "Thunderstorm",
+  "W085": "Cyclone area"
+ }
+}
diff --git a/tools/fetch_clipart.py b/tools/fetch_clipart.py
index 68dcd38..576c9eb 100644
--- a/tools/fetch_clipart.py
+++ b/tools/fetch_clipart.py
@@ -13,7 +13,9 @@ Was nicht passt, wird übersprungen und aufgelistet – außer bei den ausdrück
 ISO-7000-Zeichen: dann Abbruch. Der Stand der Commons-Dateien (SHA-1, Lizenz) steht in
 tools/clipart/commons.lock.json; weicht er ab, bricht das Skript ab (``--update`` schreibt ihn
 neu – danach die Änderungen prüfen). Deutsche Namen, Kategorien, Suchbegriffe:
-tools/clipart/de.json. Jede SVG wird mit Qt probehalber gerastert (leer/ungültig → übersprungen).
+tools/clipart/de.json, englische: tools/clipart/en.json (Pflicht für jedes Zeichen – die englischen
+Commons-Beschreibungen sind zu uneinheitlich). Jeder Eintrag hat ``names``/``subgroups`` je Sprache
+({"de", "en"}). Jede SVG wird mit Qt probehalber gerastert (leer/ungültig → übersprungen).
 
     .venv/bin/python tools/fetch_clipart.py [--cache ORDNER] [--update]
 
@@ -165,10 +167,15 @@ def tabler(de: dict, cache: Path | None) -> tuple[list[dict], dict[str, bytes],
                     continue
                 path = f"tabler/{style}/{name}.svg"
                 files[path] = compact(read(f"icons/{style}/{name}.svg").decode()).encode()
+                plain_name = name.replace("-", " ")
+                subgroup = de["categories"].get(category, category)
                 entries.append({
                     "id": f"tabler/{style}/{name}", "group": "allgemein",
-                    "subgroup": de["categories"].get(category, category),
-                    "name": name.replace("-", " ") + (" (gefüllt)" if style == "filled" else ""),
+                    "subgroup": subgroup,
+                    "name": plain_name + (" (gefüllt)" if style == "filled" else ""),
+                    "names": {"de": plain_name + (" (gefüllt)" if style == "filled" else ""),
+                              "en": plain_name + (" (filled)" if style == "filled" else "")},
+                    "subgroups": {"de": subgroup, "en": category or "Other"},
                     "keywords": sorted({*map(str, icon.get("tags", [])), *synonyms.get(name, [])}),
                     "file": path, "source": f"Tabler Icons {TABLER_VERSION}",
                     "url": "https://tabler.io/icons", "author": "Paweł Kuna", "license": "MIT"})
@@ -198,11 +205,11 @@ def category_files(cache: Path | None) -> list[str]:
         more = {"cmcontinue": answer["continue"]["cmcontinue"]}
 
 
-def file_info(titles: list[str], cache: Path | None) -> dict[str, dict]:
+def file_info(titles: list[str], cache: Path | None, language: str = "de") -> dict[str, dict]:
     info: dict[str, dict] = {}
     for start in range(0, len(titles), 40):
         pages = api(cache, action="query", titles="|".join(titles[start:start + 40]),
-                    prop="imageinfo", iiprop="url|sha1|extmetadata", iiextmetadatalanguage="de",
+                    prop="imageinfo", iiprop="url|sha1|extmetadata", iiextmetadatalanguage=language,
                     iiextmetadatafilter="ImageDescription|LicenseShortName|License|Artist|"
                                         "Restrictions")["query"]["pages"]
         for page in pages:
@@ -226,7 +233,7 @@ def problem(title: str, meta: dict | None) -> str | None:
     return None
 
 
-def commons(de: dict, cache: Path | None, lock: dict, update: bool
+def commons(de: dict, en: dict, cache: Path | None, lock: dict, update: bool
             ) -> tuple[list[dict], dict[str, bytes], list[str], dict]:
     listed = [(f"File:ISO 7000 - Ref-No {ref}.svg", f"iso7000/{ref}") for ref in de["iso7000"]]
     candidates: dict[str, list[str]] = {}
@@ -270,15 +277,22 @@ def commons(de: dict, cache: Path | None, lock: dict, update: bool
         code = ident.split("/")[1]
         if group == "versand":
             name, subgroup, standard = de["iso7000"][code], "Packzeichen (ISO 780)", "ISO 780"
+            name_en, subgroup_en = en["iso7000"][code], en["subgroups"][subgroup]
         else:
             subgroup, standard = de["iso7010_kinds"][code[0]], "ISO 7010"
+            subgroup_en = en["iso7010_kinds"][code[0]]
             description = plain(ext.get("ImageDescription", {}).get("value", ""))
             name = f"{de['iso7010'].get(code) or iso_name(description) or title[5:-4]} ({code})"
+            if code not in en["iso7010"]:
+                raise SystemExit(f"{title}: englischer Name fehlt in en.json (iso7010/{code})")
+            name_en = f"{en['iso7010'][code]} ({code})"
         path = f"commons/{ident}.svg"
         files[path] = svg
         entries.append({
             "id": ident, "group": group, "subgroup": subgroup, "name": name,
-            "keywords": [code, standard, subgroup], "file": path, "source": title[5:],
+            "names": {"de": name, "en": name_en},
+            "subgroups": {"de": subgroup, "en": subgroup_en},
+            "keywords": [code, standard, subgroup, subgroup_en], "file": path, "source": title[5:],
             "url": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
             "author": author(ext.get("Artist", {}).get("value", "")), "license": licence})
     if not update and set(lock) != set(new_lock):
@@ -288,20 +302,25 @@ def commons(de: dict, cache: Path | None, lock: dict, update: bool
 
 
 # --- eigene Zeichnungen ----------------------------------------------------------------------
-def own(de: dict) -> tuple[list[dict], dict[str, bytes]]:
+def own(de: dict, en: dict) -> tuple[list[dict], dict[str, bytes]]:
     entries, files = [], {}
     names = de["eigene"]
     found = {p.stem for p in (DATA / "eigene").glob("*.svg")}
     if found != set(names):
         raise SystemExit(f"tools/clipart/eigene und de.json passen nicht zusammen: "
                          f"{sorted(found ^ set(names))}")
+    if set(en["eigene"]) != set(names):
+        raise SystemExit(f"en.json und de.json (eigene) passen nicht zusammen: "
+                         f"{sorted(set(en['eigene']) ^ set(names))}")
     for stem, meta in sorted(names.items()):
         path = f"labelwerk/{stem}.svg"
         files[path] = (DATA / "eigene" / f"{stem}.svg").read_bytes()
+        subgroup = "Elektro" if meta["group"] == "elektro" else "Packzeichen (ISO 780)"
         entries.append({
-            "id": f"labelwerk/{stem}", "group": meta["group"],
-            "subgroup": "Elektro" if meta["group"] == "elektro" else "Packzeichen (ISO 780)",
-            "name": meta["name"], "keywords": meta["keywords"], "file": path,
+            "id": f"labelwerk/{stem}", "group": meta["group"], "subgroup": subgroup,
+            "name": meta["name"], "names": {"de": meta["name"], "en": en["eigene"][stem]},
+            "subgroups": {"de": subgroup, "en": en["subgroups"][subgroup]},
+            "keywords": meta["keywords"], "file": path,
             "source": "labelwerk (eigene Zeichnung)", "url": "", "author": "labelwerk",
             "license": OWN_LICENSE})
     return entries, files
@@ -354,9 +373,11 @@ def main() -> None:
                         help="geänderten Stand der Commons-Dateien übernehmen (commons.lock.json)")
     args = parser.parse_args()
     de = json.loads((DATA / "de.json").read_text(encoding="utf-8"))
+    en = json.loads((DATA / "en.json").read_text(encoding="utf-8"))
     lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
-    own_entries, own_files = own(de)
-    commons_entries, commons_files, skipped, new_lock = commons(de, args.cache, lock, args.update)
+    own_entries, own_files = own(de, en)
+    commons_entries, commons_files, skipped, new_lock = commons(de, en, args.cache, lock,
+                                                                 args.update)
     tabler_entries, tabler_files, tabler_licence = tabler(de, args.cache)
     entries = own_entries + commons_entries + tabler_entries
     files = {**own_files, **commons_files, **tabler_files}
diff --git a/tools/i18n.py b/tools/i18n.py
new file mode 100644
index 0000000..1693b5f
--- /dev/null
+++ b/tools/i18n.py
@@ -0,0 +1,296 @@
+"""Übersetzbare Texte einsammeln und die Sprachdateien pflegen.
+
+    python tools/i18n.py extract   # src/labelwerk/po/labelwerk.pot aus dem Code neu schreiben
+    python tools/i18n.py update    # neue Texte in jede .po übernehmen, entfallene als veraltet (#~)
+    python tools/i18n.py check     # wie der Test: .pot aktuell, jede Sprache vollständig
+
+Gefunden werden Aufrufe von ``_``, ``N_``, ``NP_``, ``ngettext`` und ``pgettext`` mit festem Text (AST,
+ohne den Code auszuführen); Kommentare „# Translators: …“ direkt darüber gehen als Hinweis mit (``#.``),
+Texte mit ``{name}`` bekommen ``#, python-brace-format`` (Weblate/Poedit prüfen dann die Platzhalter).
+``update`` behält, was Übersetzer eingetragen haben: Kommentare, unsichere (fuzzy) und veraltete Einträge. Die Ausgabe ist sortiert, ohne Datum und ohne Zeilennummern (Fundstelle = Datei) – sie
+ändert sich nur, wenn sich Texte ändern.
+"""
+from __future__ import annotations
+
+import ast
+import re
+import sys
+from dataclasses import dataclass, field
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parent.parent
+SRC = ROOT / "src" / "labelwerk"
+PO_DIR = SRC / "po"
+POT = PO_DIR / "labelwerk.pot"
+HEADER = {"de": "nplurals=2; plural=(n != 1);"}
+
+
+@dataclass
+class Message:
+    msgid: str
+    plural: str | None = None
+    context: str = ""
+    places: list[str] = field(default_factory=list)
+    notes: list[str] = field(default_factory=list)       # Hinweise für Übersetzer (#.)
+
+    @property
+    def brace_format(self) -> bool:
+        return bool(re.search(r"\{[^{}]*\}", self.msgid.replace("{{", "").replace("}}", "")))
+
+    @property
+    def key(self) -> tuple[str, str]:
+        return self.context, self.msgid
+
+
+def _text(node) -> str | None:
+    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
+
+
+def extract(src: Path = SRC) -> dict[tuple[str, str], Message]:
+    """Alle übersetzbaren Texte unter ``src``: (Kontext, Text) → Message mit Fundstellen."""
+    found: dict[tuple[str, str], Message] = {}
+    for path in sorted(src.rglob("*.py")):
+        source = path.read_text(encoding="utf-8")
+        lines = source.split("\n")           # wie der Parser zählt (nicht splitlines: U+2028 …)
+        tree = ast.parse(source, str(path))
+        for node in ast.walk(tree):
+            if not isinstance(node, ast.Call):
+                continue
+            name = node.func.id if isinstance(node.func, ast.Name) else \
+                node.func.attr if isinstance(node.func, ast.Attribute) else None
+            args = [_text(a) for a in node.args]
+            message = None
+            if name in ("_", "N_") and len(args) == 1 and args[0] is not None:
+                message = Message(args[0])
+            elif name in ("pgettext", "NP_") and len(args) == 2 and None not in args:
+                message = Message(args[1], context=args[0])
+            elif name == "ngettext" and len(args) >= 2 and None not in args[:2]:
+                message = Message(args[0], plural=args[1])
+            if message is None:
+                continue
+            place = str(path.relative_to(src.parent.parent))   # ohne Zeile: stabil beim Umbauen
+            number = node.lineno - 2                              # Kommentar direkt darüber
+            notes = []
+            while number >= 0 and lines[number].strip().startswith("#"):
+                notes.insert(0, lines[number].strip().lstrip("#").strip())
+                number -= 1
+            if any(n.startswith("Translators:") for n in notes):
+                note = " ".join(notes[next(i for i, n in enumerate(notes)
+                                           if n.startswith("Translators:")):])
+                message.notes.append(note)
+            known = found.setdefault(message.key, message)
+            for note in message.notes:
+                if note not in known.notes:
+                    known.notes.append(note)
+            if place not in known.places:
+                known.places.append(place)
+            if message.plural and not known.plural:
+                known.plural = message.plural
+    return found
+
+
+def _escape(char: str) -> str:
+    return {"\\": "\\\\", '"': '\\"', "\t": "\\t", "\r": "\\r"}.get(
+        char, f"\\{ord(char):03o}" if ord(char) < 32 and char != "\n" else char)
+
+
+def _quote(text: str) -> str:
+    escaped = "".join(map(_escape, text))
+    if "\n" not in escaped:
+        return f'"{escaped}"'
+    parts = escaped.split("\n")
+    lines = [p + "\\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
+    return '""\n' + "\n".join(f'"{line}"' for line in lines)
+
+
+def _entry(m: Message, translation: list[str] | None = None, places: bool = True,
+           comments: list[str] = (), flags: list[str] = ()) -> str:
+    out = [f"# {c}".rstrip() for c in comments]
+    if places:
+        out += [f"#. {n}" for n in m.notes] + [f"#: {p}" for p in m.places]
+    flags = [*flags, *(["python-brace-format"] if m.brace_format else [])]
+    if flags:
+        out.append("#, " + ", ".join(dict.fromkeys(flags)))
+    if m.context:
+        out.append(f"msgctxt {_quote(m.context)}")
+    out.append(f"msgid {_quote(m.msgid)}")
+    if m.plural is not None:
+        out.append(f"msgid_plural {_quote(m.plural)}")
+        forms = translation or ["", ""]
+        out += [f"msgstr[{i}] {_quote(f)}" for i, f in enumerate(forms)]
+    else:
+        out.append(f"msgstr {_quote((translation or [''])[0])}")
+    return "\n".join(out) + "\n"
+
+
+def pot_text(messages: dict) -> str:
+    head = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
+            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n')
+    return head + "".join("\n" + _entry(m) for _, m in sorted(messages.items()))
+
+
+def po_text(language: str, messages: dict, translations: dict, obsolete: dict,
+            raw: dict | None = None, header: str | None = None) -> str:
+    """Sprachdatei: Kopf (vorhandener bleibt), alle Texte des Codes mit Übersetzung, Kommentaren und
+    Markierungen der Übersetzer (``raw``), danach veraltete (``#~``)."""
+    head = header or ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
+                      f'"Language: {language}\\n"\n'
+                      f'"Plural-Forms: {HEADER.get(language, "nplurals=2; plural=(n != 1);")}\\n"\n')
+    raw = raw or {}
+    body = "".join("\n" + _entry(m, translations.get(k), comments=raw.get(k, {}).get("comments", []),
+                                 flags=[f for f in raw.get(k, {}).get("flags", [])
+                                        if f != "python-brace-format"])
+                   for k, m in sorted(messages.items()))
+    old = "".join("\n" + "\n".join("#~ " + line for line in _entry(m, t, places=False).splitlines())
+                  + "\n" for (m, t) in obsolete.values())
+    return head + body + old
+
+
+def read_raw(text: str) -> tuple[str, dict]:
+    """Rohe Einträge einer Sprachdatei, auch unsichere und veraltete: Kopf (Text) und
+    (Kontext, Text) → {comments, flags, forms, plural, obsolete}."""
+    sys.path.insert(0, str(ROOT / "src"))
+    from labelwerk.i18n import unquote
+    header, entries, block = "", {}, []
+
+    def finish(lines):
+        nonlocal header
+        if not lines:
+            return
+        obsolete = all(line.startswith("#~") for line in lines if line.strip())
+        lines = [line[2:].strip() if line.startswith("#~") else line for line in lines]
+        comments, flags, fields, key = [], [], {}, None
+        for line in lines:
+            if line.startswith("#,"):
+                flags += [f.strip() for f in line[2:].split(",") if f.strip()]
+            elif line.startswith("# ") or line == "#":
+                comments.append(line[2:])
+            elif line.startswith("#"):
+                continue                                    # #: und #. schreibt extract neu
+            elif line.startswith('"'):
+                fields[key] += unquote(line, "")
+            else:
+                key, __, value = line.partition(" ")
+                fields[key] = unquote(value, "")
+        if fields.get("msgid") == "" and "msgctxt" not in fields:
+            header = "\n".join(l for l in lines if not l.startswith("#")) + "\n"
+            return
+        forms = [fields[k] for k in sorted(fields) if k.startswith("msgstr")]
+        entries[(fields.get("msgctxt", ""), fields["msgid"])] = {
+            "comments": comments, "flags": flags, "forms": forms,
+            "plural": fields.get("msgid_plural"), "obsolete": obsolete}
+
+    for line in text.splitlines():
+        if not line.strip():
+            finish(block)
+            block = []
+        else:
+            block.append(line)
+    finish(block)
+    return header, entries
+
+
+def _load(language: str):
+    sys.path.insert(0, str(ROOT / "src"))
+    from labelwerk.i18n import parse_po
+    path = PO_DIR / f"{language}.po"
+    return parse_po(path.read_text(encoding="utf-8"), language) if path.exists() else None
+
+
+def languages() -> list[str]:
+    return sorted(p.stem for p in PO_DIR.glob("*.po"))
+
+
+def placeholders(text: str) -> list[str]:
+    """Benannte Platzhalter ``{name}``/``{name!r}``/``{name:.1f}`` und %-Angaben eines Texts."""
+    return sorted(re.findall(r"\{[^{}]*\}", text.replace("{{", "").replace("}}", ""))
+                  + re.findall(r"%(?:\([a-z_]+\))?[srd]", text))
+
+
+GERMAN = re.compile(r"[äöüÄÖÜß]|\b(der|das|und|nicht|kein|keine|ist|mit|für|oder|auf|bei|wird|"
+                    r"Etikett|Drucker|Datei|Fehler|Bild|Seite|Zeile|Spalte|Rand|Rahmen|Schrift|"
+                    r"Größe|Zwischenablage|Bildschirmfoto|Serie|Vorlage|Einstellung)\b")
+# Deutsche Texte, die bewusst keine Übersetzung sind (gespeichert/verglichen): Datei → Texte
+GERMAN_OK = {"src/labelwerk/gui/image_import.py": {"Abgelegtes Bild", "Zwischenablage",
+                                                   "Bildschirmfoto"}}
+
+
+def german_leftovers(src: Path = SRC) -> list[str]:
+    """Deutsch aussehende Texte außerhalb von ``_()`` & Co. (ohne Docstrings) – Nutzertexte, die
+    die Umstellung auf Englisch übersehen hat; Ausnahmen in ``GERMAN_OK``."""
+    calls, found = {"_", "N_", "pgettext", "ngettext"}, []
+    for path in sorted(src.rglob("*.py")):
+        tree = ast.parse(path.read_text(encoding="utf-8"))
+        skip = set()
+        for node in ast.walk(tree):
+            body = getattr(node, "body", None)
+            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) \
+                    and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
+                skip.add(id(body[0].value))
+            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in calls:
+                skip.update(id(a) for a in ast.walk(node))
+        where = str(path.relative_to(src.parent.parent))
+        for node in ast.walk(tree):
+            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip \
+                    and len(node.value) > 2 and GERMAN.search(node.value) \
+                    and node.value not in GERMAN_OK.get(where, ()):
+                found.append(f"{where}:{node.lineno}: {node.value[:80]!r}")
+    return found
+
+
+def problems(messages: dict | None = None) -> list[str]:
+    """Was der Test prüft: .pot aktuell, jede Sprache vollständig, Platzhalter gleich."""
+    messages = extract() if messages is None else messages
+    found = []
+    if not POT.exists() or POT.read_text(encoding="utf-8") != pot_text(messages):
+        found.append("labelwerk.pot veraltet – python tools/i18n.py extract")
+    for language in languages():
+        catalog = _load(language)
+        nplurals = int(re.search(r"nplurals\s*=\s*(\d+)", (PO_DIR / f"{language}.po").read_text(
+            encoding="utf-8-sig"))[1])
+        for key, m in sorted(messages.items()):
+            forms = catalog.messages.get(key)
+            if not forms:
+                found.append(f"{language}: fehlt {m.msgid!r}" + (f" ({m.context})" if m.context else ""))
+                continue
+            if m.plural is not None and len(forms) != nplurals:
+                found.append(f"{language}: {len(forms)} statt {nplurals} Mehrzahlformen in {m.msgid!r}")
+            for index, form in enumerate(forms):
+                original = m.msgid if index == 0 or m.plural is None else m.plural
+                if set(placeholders(form)) != set(placeholders(original)):
+                    found.append(f"{language}: Platzhalter anders in {m.msgid!r}: {form!r}")
+    return found
+
+
+def update() -> None:
+    """Vorlage neu; jede Sprachdatei: neue Texte dazu (leer), vorhandene Übersetzungen samt
+    Kommentaren und Markierungen (fuzzy) bleiben, entfallene werden veraltet (``#~``)."""
+    messages = extract()
+    POT.write_text(pot_text(messages), encoding="utf-8")
+    for language in languages():
+        path = PO_DIR / f"{language}.po"
+        header, raw = read_raw(path.read_text(encoding="utf-8-sig"))
+        translations = {k: e["forms"] for k, e in raw.items() if k in messages and any(e["forms"])}
+        obsolete = {k: (Message(k[1], plural=e["plural"], context=k[0]), e["forms"])
+                    for k, e in raw.items() if k not in messages and any(e["forms"])}
+        path.write_text(po_text(language, messages, translations, obsolete, raw, header or None),
+                        encoding="utf-8")
+
+
+def main(argv: list[str]) -> int:
+    command = argv[0] if argv else "check"
+    if command == "extract":
+        POT.write_text(pot_text(extract()), encoding="utf-8")
+        print(f"geschrieben: {POT}")
+        return 0
+    if command == "update":
+        update()
+        print("aktualisiert: " + ", ".join([POT.name, *(f"{lang}.po" for lang in languages())]))
+        return 0
+    found = problems()
+    print("\n".join(found) if found else "vollständig")
+    return 1 if found else 0
+
+
+if __name__ == "__main__":
+    sys.exit(main(sys.argv[1:]))
````

- [ ] **Step 3b: Symbol-Bibliothek aus dem geprüften Prototyp-Commit übernehmen** (binär, ca. 3 MB – nicht als Patch): `git checkout 07fbb7b84b06 -- src/labelwerk/clipart_data/clipart.zip` (der Commit liegt im selben Repository, Branch `proto-i18n-final`). Prüfen: `git status --short src/labelwerk/clipart_data/clipart.zip` zeigt `M  src/labelwerk/clipart_data/clipart.zip`.

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2529 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md src/labelwerk/barcodes.py src/labelwerk/cli.py src/labelwerk/clipart.py src/labelwerk/clipart_data/LICENSES.md src/labelwerk/clipart_data/clipart.zip src/labelwerk/cups.py src/labelwerk/desktop.py src/labelwerk/detect.py src/labelwerk/favorites.py src/labelwerk/files.py src/labelwerk/fonts.py src/labelwerk/gui/actions.py src/labelwerk/gui/app.py src/labelwerk/gui/canvas.py src/labelwerk/gui/file_session.py src/labelwerk/gui/image_import.py src/labelwerk/gui/main_window.py src/labelwerk/gui/media_worker.py src/labelwerk/gui/panels/__init__.py src/labelwerk/gui/panels/barcode.py src/labelwerk/gui/panels/file.py src/labelwerk/gui/panels/image.py src/labelwerk/gui/panels/layout.py src/labelwerk/gui/panels/paper.py src/labelwerk/gui/panels/position.py src/labelwerk/gui/panels/series.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/print_worker.py src/labelwerk/gui/screenshot.py src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/symbol_dialog.py src/labelwerk/gui/tools.py src/labelwerk/gui/widgets.py src/labelwerk/i18n.py src/labelwerk/imaging.py src/labelwerk/labels.py src/labelwerk/layout.py src/labelwerk/media.py src/labelwerk/po/README.md src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/printer.py src/labelwerk/printers.py src/labelwerk/render.py src/labelwerk/series.py src/labelwerk/settings.py src/labelwerk/shortcuts.py src/labelwerk/storage.py src/labelwerk/zpl.py tests/conftest.py tests/gui/conftest.py tests/gui/test_gui_barcode.py tests/gui/test_gui_editbar.py tests/gui/test_gui_language.py tests/gui/test_gui_layout.py tests/gui/test_gui_media.py tests/gui/test_gui_printers.py tests/gui/test_gui_screenshot.py tests/gui/test_gui_symbols.py tests/gui/test_gui_text_fit.py tests/test_cli.py tests/test_clipart.py tests/test_i18n.py tests/test_series.py tests/test_shortcuts.py tools/clipart/de.json tools/clipart/en.json tools/fetch_clipart.py tools/i18n.py
git commit -m "Übersetzungen: Quellsprache Englisch mit gettext ohne Abhängigkeit (i18n.py, po/de.po, tools/i18n.py), Sprachwahl in Einstellungen und CLI (--lang) mit Neustart-Hinweis neben SPEICHERN, Zahlen je Sprache, {Nummer}/{Number}, Symbole deutsch/englisch, Layout-Test je Sprache

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Abnahme (manuell, durch den Nutzer)

- [ ] Oberfläche auf Deutsch wie bisher (Texte unverändert; Reiter Layout: „Größe ändern“ statt „Vergrößern/Verkleinern“).
- [ ] Einstellungen → Ansicht → Sprache „English“: Hinweis „Änderungen erst nach Neustart aktiv“ neben SPEICHERN; nach Neustart alles englisch, Zahlen mit Punkt.
- [ ] `labelwerk --lang en print X -l 999` (englische Meldung), `labelwerk --help` auf Deutsch.
- [ ] Serie mit Nummerierung: `{Nummer}` und `{Number}` füllen beide; Symbol-Suche „earth“ findet „Erde“.
