# Bild-Objekt (Etappe 3d-2a) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bilder (Datei, Zwischenablage, Ablegen) als frei platzierbare Objekte aufs Etikett – 1:1, zugeschnitten, in Schwarz/Weiß umgerechnet; vorher Renderer und Hauptfenster entflechten.

**Architecture:** `ImageObject` im Qt-freien Kern speichert das farbige Original (PNG); Laden/Zuschnitt in `files.py`, Umrechnung in `imaging.py`, Rendern über den neuen inkrementellen `render.Renderer`; die GUI (Reiter BILD) importiert Dateien/SVG/Zwischenablage und nutzt dieselben Platzier-Funktionen wie für Text.

**Tech Stack:** Python ≥ 3.10, Pillow, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-17-bild-objekt-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-3d2a`), nach jedem Task volle Suite grün mit Exit-Code 0 (1009 → 1027 → 1193 → 1309); jeder Schritt vor der Planerstellung geprüft und korrigiert (Umbau: 2118 Render- und 4000 Bedienschritte identisch zu vorher; Kern: Text-Druckbild und print-file byte-gleich, Codes 1:1 bit-genau; GUI: Zwischenablage, Ablegen, Rückgängig je Regler, Anfasser); GUI per Offscreen-Screenshots geprüft.

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Kern bleibt **Qt-frei** (`document.py`, `render.py`, `layout.py`, `shortcuts.py`, `settings.py`); keine Drucklogik in der GUI.
- **Vorschau = Druck**; ein einzelnes Objekt ohne Position ergibt **pixelgleich** das bisherige Bild.
- Koordinaten in mm in Leserichtung, Ursprung linke obere Ecke des Etiketts; Schriftgrößen in pt (4–100).
- Benutzer-Meldungen und Kommentare auf Deutsch; keine Tracebacks für Nutzer.
- Tests ohne Hardware und ohne echte Nutzer-Einstellungen; jedes Widget in GUI-Tests bei `qtbot.addWidget` anmelden.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---
### Task 1: Umbau – inkrementeller Renderer im Kern, Schreibmodus-Befehle in der Sitzung, Bereich Position als Widget

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/gui/main_window.py`
- Create: `src/labelwerk/gui/panels/position.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/text_edit_mode.py`
- Modify: `src/labelwerk/render.py`
- Modify: `tests/gui/test_gui_edit_mode.py`
- Create: `tests/gui/test_gui_position.py`
- Modify: `tests/gui/test_gui_textframe.py`
- Create: `tests/test_renderer.py`

**Interfaces / Produces:** `render.Renderer().render(doc, model) -> Rendered(size, objects, image)` (Qt-frei, rendert nur Geändertes, gleiche Cache-Schlüssel wie vorher); `TextEditSession.undo/redo/copy/cut/paste() -> bool`, `update_actions(actions) -> bool`; `gui/panels/position.py` `PositionSection` (`spins`, `show_frame(rect, editable_size)`, `set_size_editable`, Signal `edited(key, value)`); verhaltensneutral.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_edit_mode.py b/tests/gui/test_gui_edit_mode.py
index 8fc5260..884d08e 100644
--- a/tests/gui/test_gui_edit_mode.py
+++ b/tests/gui/test_gui_edit_mode.py
@@ -383,6 +383,17 @@ def test_edit_bar_cut_and_paste_work_on_text_in_edit_mode(qtbot):
     assert win.doc.objects[0].text == "Max Mustermann" and len(win.doc.objects) == 2
 
 
+@pytest.mark.parametrize("name", ["copy", "cut", "paste"])
+def test_clipboard_command_ending_edit_mode_does_not_fall_through_to_objects(qtbot, name):
+    """Endet der Schreibmodus während des Befehls, gilt der Befehl trotzdem als erledigt –
+    Ausschneiden nimmt dann nicht das ganze Objekt mit."""
+    win, editor = _editing(qtbot)
+    _double_click(win.canvas, _char_point(win, 0, 1))
+    setattr(editor, name, win.finish_editing)               # beendet den Schreibmodus sofort
+    assert getattr(_session(win), name)() is True
+    assert not _session(win).active and len(win.doc.objects) == 2
+
+
 def test_end_edit_is_a_fixed_action_of_edit_mode(window):
     action = window.shortcut_actions["text.end_edit"]
     assert action in window.panel("text").actions()
diff --git a/tests/gui/test_gui_position.py b/tests/gui/test_gui_position.py
new file mode 100644
index 0000000..e3e60ba
--- /dev/null
+++ b/tests/gui/test_gui_position.py
@@ -0,0 +1,39 @@
+"""Bereich „Position“ als eigenes Widget (gemeinsam für Text- und Bild-Panel)."""
+from labelwerk.gui.panels.position import PositionSection
+from labelwerk.layout import Rect
+
+
+def _section(qtbot) -> tuple[PositionSection, list]:
+    section = PositionSection()
+    qtbot.addWidget(section)
+    seen = []
+    section.edited.connect(lambda key, value: seen.append((key, value)))
+    return section, seen
+
+
+def test_show_frame_sets_values_without_signal(qtbot):
+    section, seen = _section(qtbot)
+    section.show_frame(Rect(1.5, 2, 30, 8.2), editable_size=True)
+    assert [s.value() for s in section.spins.values()] == [1.5, 2, 30, 8.2]
+    section.show_frame(None, editable_size=True)
+    assert [s.value() for s in section.spins.values()] == [0, 0, 1, 1]   # Mindestgröße 1 mm
+    assert seen == []
+
+
+def test_editable_size_reports_all_fields(qtbot):
+    section, seen = _section(qtbot)
+    section.show_frame(Rect(1, 2, 30, 8), editable_size=True)
+    assert not section.spins["w"].isReadOnly()
+    section.spins["x"].setValue(4)
+    section.spins["w"].setValue(25)
+    assert seen == [("x", 4), ("w", 25)]
+
+
+def test_fixed_size_only_shows_width_and_height(qtbot):
+    section, seen = _section(qtbot)
+    section.show_frame(Rect(1, 2, 30, 8), editable_size=False)
+    assert section.spins["w"].isReadOnly() and section.spins["h"].isReadOnly()
+    assert "Nur mit fester Rahmengröße" in section.spins["w"].toolTip()
+    section.spins["h"].setValue(12)
+    section.spins["y"].setValue(3)
+    assert seen == [("y", 3)]
diff --git a/tests/gui/test_gui_textframe.py b/tests/gui/test_gui_textframe.py
index c3fe451..1eac7bf 100644
--- a/tests/gui/test_gui_textframe.py
+++ b/tests/gui/test_gui_textframe.py
@@ -177,6 +177,17 @@ def test_width_and_height_only_editable_with_fixed_frame(window):
     assert window.canvas.objects[0].frame_mm().w == pytest.approx(30, abs=DOT_MM)
 
 
+def test_size_edit_without_fixed_frame_is_ignored_by_the_panel(window):
+    """Auch wenn der Bereich Position eine Größe meldet: ohne feste Rahmengröße nicht."""
+    window.canvas.set_selection([0])
+    panel = window.panel("text")
+    seen = []
+    panel.frame_edited.connect(lambda key, value: seen.append((key, value)))
+    panel._frame_changed("w", 30)
+    panel._frame_changed("x", 6)
+    assert seen == [("x", 6)]
+
+
 def test_turning_fixed_frame_on_keeps_current_frame_size(window):
     window.canvas.set_selection([0])
     shown = window.canvas.objects[0].frame_mm()
diff --git a/tests/test_renderer.py b/tests/test_renderer.py
new file mode 100644
index 0000000..24dec53
--- /dev/null
+++ b/tests/test_renderer.py
@@ -0,0 +1,173 @@
+"""Inkrementeller Renderer (``render.Renderer``): nur Geändertes neu, Druckbild = render_document."""
+import copy
+import random
+
+import pytest
+
+from labelwerk import render
+from labelwerk.document import Document, Paragraph, Span, TextObject
+from labelwerk.render import Rendered, Renderer, label_size, render_document, render_object
+
+
+def _doc(**kw) -> Document:
+    return Document("62", length_mm=40, objects=[
+        TextObject("Eins", size_pt=12, x_mm=3, y_mm=4),
+        TextObject("Zwei", size_pt=14, x_mm=6, y_mm=20)], **kw)
+
+
+@pytest.fixture
+def calls(monkeypatch):
+    """Zählt das Messen (``_prepare``) und Zeichnen (``_finish``) je Objekttext."""
+    seen = []
+    for name in ("_prepare", "_finish"):
+        real = getattr(render, name)
+
+        def counting(item, *args, _real=real, _name=name, **kwargs):
+            seen.append((_name, getattr(item, "obj", item).text))
+            return _real(item, *args, **kwargs)
+        monkeypatch.setattr(render, name, counting)
+    return seen
+
+
+def test_render_gives_size_objects_and_print_image():
+    doc = _doc()
+    result = Renderer().render(doc, "QL-600")
+    assert isinstance(result, Rendered)
+    assert result.size == label_size(doc)
+    assert result.objects == [render_object(obj, doc) for obj in doc.objects]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_unchanged_document_renders_nothing_and_keeps_image(calls):
+    renderer, doc = Renderer(), _doc()
+    first = renderer.render(doc, "QL-600")
+    calls.clear()
+    second = renderer.render(doc, "QL-600")
+    assert calls == []
+    assert second.image is first.image
+    assert all(a is b for a, b in zip(second.objects, first.objects))
+
+
+def test_only_changed_object_is_rendered_again(calls):
+    renderer, doc = Renderer(), _doc()
+    renderer.render(doc, "QL-600")
+    calls.clear()
+    doc.objects[1].x_mm = 10                       # in place geändert: Schnappschuss erkennt es
+    result = renderer.render(doc, "QL-600")
+    assert calls == [("_prepare", "Zwei"), ("_finish", "Zwei")]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_replaced_object_is_rendered_again(calls):
+    renderer, doc = Renderer(), _doc()
+    renderer.render(doc, "QL-600")
+    calls.clear()
+    doc.objects[0] = TextObject("Neu", size_pt=12, x_mm=3, y_mm=4)
+    renderer.render(doc, "QL-600")
+    assert calls == [("_prepare", "Neu"), ("_finish", "Neu")]
+
+
+def test_object_replaced_by_equal_copy_is_rendered_again(calls):
+    """Gleicher Inhalt, aber ein anderes Objekt: neu messen (der Cache hält das alte fest)."""
+    renderer, doc = Renderer(), _doc()
+    renderer.render(doc, "QL-600")
+    calls.clear()
+    doc.objects[0] = copy.deepcopy(doc.objects[0])
+    result = renderer.render(doc, "QL-600")
+    assert calls == [("_prepare", "Eins"), ("_finish", "Eins")]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_same_object_twice_in_list_renders_twice():
+    doc = _doc()
+    doc.objects.append(doc.objects[0])
+    renderer = Renderer()
+    result = renderer.render(doc, "QL-600")
+    assert len(result.objects) == 3 and result.objects[2] == result.objects[0]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+    doc.objects[0].x_mm = 12                       # beide Einträge ändern sich mit
+    result = renderer.render(doc, "QL-600")
+    assert result.objects[2] == result.objects[0]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_context_change_renders_everything_again(calls):
+    renderer, doc = Renderer(), _doc()
+    renderer.render(doc, "QL-600")
+    calls.clear()
+    doc.margin_mm = 4
+    result = renderer.render(doc, "QL-600")
+    assert sorted(calls) == [("_finish", "Eins"), ("_finish", "Zwei"),
+                             ("_prepare", "Eins"), ("_prepare", "Zwei")]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_growing_label_redraws_unpositioned_objects_without_measuring_again(calls):
+    renderer = Renderer()
+    doc = _doc()
+    doc.length_mm = None                           # automatische Länge: wächst mit
+    doc.objects.append(TextObject("Mitte"))        # ohne Position: hängt an der Etikettgröße
+    before = renderer.render(doc, "QL-600")
+    calls.clear()
+    doc.objects[1].y_mm = 80
+    result = renderer.render(doc, "QL-600")
+    assert result.size != before.size
+    assert sorted(calls) == [("_finish", "Mitte"), ("_finish", "Zwei"), ("_prepare", "Zwei")]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_failed_render_keeps_cache(calls):
+    renderer, doc = Renderer(), _doc()
+    renderer.render(doc, "QL-600")
+    doc.objects.append(TextObject("Viel zu groß", size_pt=200))   # ohne Position: zu groß
+    with pytest.raises(ValueError):
+        renderer.render(doc, "QL-600")
+    del doc.objects[-1]
+    calls.clear()
+    renderer.render(doc, "QL-600")
+    assert calls == []
+
+
+def test_empty_document_is_byte_identical():
+    for doc in (Document("62"), Document("62", objects=[TextObject("")]),
+                Document("29", orientation="horizontal")):
+        result = Renderer().render(doc, "QL-600")
+        assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_random_documents_are_byte_identical_also_incrementally():
+    rng = random.Random(7)
+    renderer = Renderer()
+    doc = Document("62")
+    for _ in range(60):
+        doc.label_id = rng.choice([doc.label_id] * 4 + ["62", "29", "62x29"])
+        doc.orientation = rng.choice([doc.orientation] * 4 + ["vertical", "horizontal"])
+        doc.length_mm = rng.choice([doc.length_mm] * 4 + [None, 50])
+        action = rng.random()
+        if action < 0.4 or not doc.objects:
+            text = "".join(rng.choice("JjfgQyAa W_") for _ in range(rng.randint(1, 8)))
+            positioned = rng.random() < 0.7
+            doc.objects.append(TextObject(
+                [Paragraph([Span(text, bold=rng.random() < 0.5)],
+                           rng.choice(["left", "center", "right"]))],
+                size_pt=rng.choice([8, 10, 14]),
+                x_mm=rng.uniform(0, 30) if positioned else None,
+                y_mm=rng.uniform(0, 20) if positioned else None,
+                rotation=rng.choice([0, 0, 90, 180, 270])))
+        elif action < 0.7:
+            obj = rng.choice(doc.objects)
+            if obj.positioned:
+                obj.x_mm = rng.uniform(0, 30)
+        elif action < 0.85:
+            del doc.objects[rng.randrange(len(doc.objects))]
+        else:
+            rng.shuffle(doc.objects)
+        try:
+            expected = render_document(doc)
+        except ValueError:
+            with pytest.raises(ValueError):
+                renderer.render(doc, "QL-600")
+            continue
+        result = renderer.render(doc, "QL-600")
+        assert result.image.size == expected.size
+        assert result.image.tobytes() == expected.tobytes()
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 5e07389..d1c1677 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -15,7 +15,7 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.
 - Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
 - Direkt auf dem Etikett schreiben (Etappe 3d-1b): Schreibmodus (Text anlegen + Klick bzw. Doppelklick, Esc/Klick daneben beendet), Schreibmarke/Markierung aus dem Kern-Zeilensatz, Markieren mit Maus und Tastatur, eine Bearbeitung = ein Rückgängig-Schritt, Rahmen wächst an der Kante der Textposition; Feld INHALT entfällt.
-- 1008 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- 1027 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -24,8 +24,10 @@ src/labelwerk/
               filtert für QL-600: >62 mm, PT-Bänder, Rot/Schwarz-Etiketten
   render.py   render_text(text, label_id, size_pt, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
               render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
-              compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise für die GUI:
-              prepare_object, label_size(prepared=), finish_object (nur Geändertes neu); span_dots
+              compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise:
+              prepare_object, label_size(prepared=), finish_object; span_dots
+              Renderer (Qt-frei, für die GUI): render(doc, model) -> Rendered(size, objects, image) – Objekt-Cache,
+              rendert nur Geändertes neu (Objekt + Kontext, ohne Position auch Etikettgröße), Druckbild = render_document
               Zeilensatz mit gemeinsamer Grundlinie (pixelgleich zu Pillow multiline_text für reinen Text), font_warnings(doc)
               exakte Druckbreite @300 dpi, Schrift schrumpft automatisch, mehrzeilig zentriert
               text_layout(obj, doc) -> TextLayout (derselbe Zeilensatz wie das Rendern, auch RenderedObject.layout):
@@ -49,15 +51,17 @@ src/labelwerk/
   desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
   gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
     main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
-                    shortcut_actions (Aktions-ID → QAction); Render-Cache je Objekt; leere Textrahmen entfallen beim Abwählen
+                    shortcut_actions (Aktions-ID → QAction); rendert über render.Renderer; leere Textrahmen entfallen beim Abwählen
     tools.py        Werkzeug-Registry (Papier, Text, Layout; neue Werkzeuge als Eintrag)
     panels/         Eigenschaften-Panels je Werkzeug (paper, text mit Bereich Position)
+    panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
     panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
     canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
                     Schreibmodus: zeichnet Rahmen/Schreibmarke/Markierung (set_edit_marks), meldet Klicks hinein (edit_*)
     text_edit_mode.py TextEditSession: Schreibmodus – Editor des Text-Panels als unsichtbarer Eingabepuffer (Fokus, IME),
                     Klick → Position über TextLayout.hit, Editor → Schreibmarke/Markierung, Auf/Ab nach Etikettzeilen,
-                    sofort rendern + anchor_after_edit; Start/Ende/Rückgängig-Schritt: MainWindow.edit_text/finish_editing
+                    sofort rendern + anchor_after_edit; Start/Ende/Rückgängig-Schritt: MainWindow.edit_text/finish_editing;
+                    Befehle im Schreibmodus (undo/redo/copy/cut/paste/update_actions -> bool „erledigt“), MainWindow delegiert
     actions.py      QActions aus shortcuts.ACTIONS – jedes Kürzel der App läuft hierüber (apply_shortcuts)
     history.py      Rückgängig/Wiederherstellen: Dokument-Schnappschüsse samt Auswahl, höchstens 100; amend (ohne eigenen Schritt)
     symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index dc4d255..243eec1 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -2,7 +2,7 @@
 from __future__ import annotations
 
 import copy
-from dataclasses import dataclass, replace
+from dataclasses import replace
 from pathlib import Path
 
 from PySide6.QtCore import Qt, QThreadPool, QTimer
@@ -21,8 +21,7 @@ from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect,
                       match_objects, maximize_object, move, object_rect, outside_indices,
                       printable_area, reorder, resize, rotate, set_frame, to_grid)
 from ..printer import DEFAULT_MODEL
-from ..render import (Prepared, RenderedObject, compose, finish_object, font_warnings,
-                      label_size, prepare_object)
+from ..render import Renderer, RenderedObject, font_warnings
 from ..settings import Settings, load_settings, new_document
 from ..shortcuts import effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
@@ -53,20 +52,6 @@ _SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
 SELECTION_PANELS = ("text", "layout")   # arbeiten mit der Auswahl: Wählen wechselt nicht weg
 
 
-@dataclass
-class _Cached:
-    """Gemessenes und gerendertes Objekt samt Stand, aus dem es entstand.
-
-    Gemessen wird nur bei Änderung des Objekts bzw. des Etiketts; gezeichnet zusätzlich,
-    wenn sich bei einem Objekt ohne Position (steht mittig) die Etikettgröße ändert."""
-    obj: TextObject            # hält das Objekt fest, damit seine id nicht neu vergeben wird
-    snapshot: TextObject
-    context: tuple
-    prepared: Prepared
-    size: tuple | None = None                  # Etikettgröße des Bilds (None = mit Position)
-    rendered: RenderedObject | None = None
-
-
 class MainWindow(QMainWindow):
     def __init__(self, doc: Document | None = None, tools: list[Tool] = TOOLS,
                  model: str = DEFAULT_MODEL, settings: Settings | None = None):
@@ -80,7 +65,7 @@ class MainWindow(QMainWindow):
         self._shown_size = (0, 0)                   # Etikettgröße der letzten gültigen Anzeige
         self._structure_dirty = False               # Objektliste seit der letzten Anzeige umgebaut
         self.rendered: list[RenderedObject] = []    # Objektbilder auf der Arbeitsfläche = im Druck
-        self._cache: dict[int, _Cached] = {}
+        self.renderer = Renderer()                  # rendert nur geänderte Objekte neu
         self._render_error: str | None = None
         self._hint: str | None = None               # Hinweis (ragt hinaus, Schrift ersetzt)
         self._print_signals = None
@@ -94,7 +79,6 @@ class MainWindow(QMainWindow):
         self._arranging = False                     # Auswahl wird intern umgestellt (Anlegen …)
         self._outside: list[int] = []               # Objekte, die über das Etikett ragen
         self._area = Rect(0, 0, 0, 0)               # bedruckbarer Bereich (mm), mit dem Bild
-        self._composed: tuple = (None, [], None)    # Druckbild und woraus es entstand
         # alle Kürzel kommen aus dem Verzeichnis (shortcuts.ACTIONS) und sind änderbar;
         # doppelt belegte (von Hand bearbeitete Datei): die spätere Aktion bleibt ohne Kürzel
         keys, key_warnings = without_conflicts(effective(self.settings.shortcuts))
@@ -410,19 +394,7 @@ class MainWindow(QMainWindow):
             panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))
 
     def _update_edit_actions(self) -> None:
-        if self.edit_session.active:                # Knöpfe wirken auf den Text im Editor
-            editor = self.panel("text").edit
-            marked = editor.textCursor().hasSelection()
-            enabled = {"edit.cut": marked, "edit.copy": marked, "edit.paste": editor.canPaste(),
-                       "edit.duplicate": False, "edit.delete": False,
-                       "edit.undo": (editor.document().isUndoAvailable()
-                                     or self.history.can_undo(self.doc)),
-                       "edit.redo": (editor.document().isRedoAvailable()
-                                     or self.history.can_redo(self.doc)),
-                       "text.end_edit": True, "text.start_edit": False,
-                       "text.start_edit_enter": False}
-            for key, value in enabled.items():
-                self.shortcut_actions[key].setEnabled(value)
+        if self.edit_session.update_actions(self.shortcut_actions):   # wirken auf den Editor
             return
         self.shortcut_actions["text.end_edit"].setEnabled(False)
         single = len(self.canvas.selection()) == 1
@@ -445,12 +417,9 @@ class MainWindow(QMainWindow):
             self._timer.start()
             return
         try:
-            # jedes Objekt höchstens einmal messen und zeichnen; Größe, Fläche und
-            # „ragt hinaus“ folgen aus den gerenderten Objekten
-            entries = self._prepare_objects()
-            size = label_size(self.doc, self.model, prepared=[e.prepared for e in entries])
-            rendered = self._render_objects(entries, size)
-            image = self._compose(rendered, size)
+            # jedes Objekt höchstens einmal messen und zeichnen; Fläche und „ragt hinaus“
+            # folgen aus den gerenderten Objekten
+            result = self.renderer.render(self.doc, self.model)
         except ValueError as e:
             # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
             self._render_error = str(e)
@@ -464,6 +433,7 @@ class MainWindow(QMainWindow):
         if self._hint is not None and self.result.text() == self._hint:
             self._set_result("", "")   # alten Hinweis nur löschen, wenn er noch dasteht
         self._hint = None
+        size, rendered = result.size, result.objects
         area = printable_area(self.doc, self.model, size)
         outside = outside_indices(rendered, size, self.doc.objects)
         hints = ([OUTSIDE_HINT] if outside else []) + font_warnings(self.doc)
@@ -471,7 +441,7 @@ class MainWindow(QMainWindow):
             self._hint = " · ".join(hints)
             self._set_result(self._hint, "error")
         self.panel("text").show_error(None)
-        self.image = image
+        self.image = result.image
         self.rendered = rendered
         self._shown_size = size
         self._structure_dirty = False
@@ -497,40 +467,6 @@ class MainWindow(QMainWindow):
                                  self.doc.orientation,
                                  self._area, keep_ratio=[], grow=growing_axis(self.doc))
 
-    def _prepare_objects(self) -> list[_Cached]:
-        """Objekte messen; unveränderte kommen aus dem Cache."""
-        doc = self.doc
-        context = (self.model, doc.label_id, doc.orientation, doc.margin_mm, doc.length_mm)
-        cache: dict[int, _Cached] = {}
-        for obj in doc.objects:
-            entry = self._cache.get(id(obj))
-            if (entry is None or entry.obj is not obj or entry.context != context
-                    or entry.snapshot != obj):
-                entry = _Cached(obj, copy.deepcopy(obj), context,
-                                prepare_object(obj, doc, self.model))
-            cache[id(obj)] = entry
-        self._cache = cache
-        return [cache[id(obj)] for obj in doc.objects]
-
-    def _render_objects(self, entries: list[_Cached], size: tuple[int, int]) -> list[RenderedObject]:
-        """Gemessene Objekte zeichnen; ein Objekt ohne Position steht mittig und wird deshalb
-        auch neu gezeichnet, wenn sich die Etikettgröße ändert."""
-        for entry in entries:
-            key = None if entry.obj.positioned else size
-            if entry.rendered is None or entry.size != key:
-                entry.rendered = finish_object(entry.prepared, self.doc, size, self.model)
-                entry.size = key
-        return [entry.rendered for entry in entries]
-
-    def _compose(self, rendered: list[RenderedObject], size: tuple[int, int]):
-        """Druckbild – unverändert, solange dieselben Objektbilder auf derselben Größe liegen."""
-        key = (size, self.doc.orientation)
-        if (self.image is None or key != self._composed[0]
-                or len(rendered) != len(self._composed[1])
-                or any(a is not b for a, b in zip(rendered, self._composed[1]))):
-            self._composed = (key, list(rendered), compose(rendered, size, self.doc.orientation))
-        return self._composed[2]
-
     # --- Rückgängig -------------------------------------------------------
     def _commit(self, merge=None) -> None:
         """Stand nach einer abgeschlossenen Aktion festhalten (ohne Änderung kein Schritt).
@@ -545,38 +481,15 @@ class MainWindow(QMainWindow):
         self._update_edit_actions()
 
     def undo(self) -> None:
-        """Rückgängig – im Schreibmodus innerhalb der Bearbeitung (Editor); ist dort nichts
-        mehr zurückzunehmen, endet der Schreibmodus und es geht im Dokument weiter (Knopf und
-        Strg+Z gleich). Ein leerer neuer Rahmen entfällt dabei – das ist dann der ganze
-        Schritt."""
-        if self.edit_session.active:
-            editor = self.panel("text").edit
-            if editor.document().isUndoAvailable():
-                editor.undo()
-                return
-            obj = self.doc.objects[self.edit_session.index]
-            if obj.positioned and obj.is_empty():
-                selection = self.history.selection  # Auswahl vor dem Anlegen
-                self.finish_editing()
-                self.canvas.set_selection(selection)
-                return
-            if not self.history.can_undo(self.doc):
-                return                              # nichts zurückzunehmen: weiter schreiben
-            self.finish_editing()
-        self._restore(self.history.undo(self.doc, self.canvas.selection()))
+        """Rückgängig – im Schreibmodus erst innerhalb der Bearbeitung (``TextEditSession.undo``),
+        dann im Dokument (Knopf und Strg+Z gleich)."""
+        if not self.edit_session.undo():
+            self._restore(self.history.undo(self.doc, self.canvas.selection()))
 
     def redo(self) -> None:
-        """Wiederherstellen – im Schreibmodus im Editor; hat er nichts mehr, endet der
-        Schreibmodus und es geht im Dokument weiter (wie bei ``undo``)."""
-        if self.edit_session.active:
-            editor = self.panel("text").edit
-            if editor.document().isRedoAvailable():
-                editor.redo()
-                return
-            if not self.history.can_redo(self.doc):
-                return                              # nichts zu wiederholen: weiter schreiben
-            self.finish_editing()
-        self._restore(self.history.redo(self.doc, self.canvas.selection()))
+        """Wiederherstellen – im Schreibmodus erst im Editor, dann im Dokument (wie ``undo``)."""
+        if not self.edit_session.redo():
+            self._restore(self.history.redo(self.doc, self.canvas.selection()))
 
     def _restore(self, snapshot: Document | None) -> None:
         """Stand zurückholen – samt der Auswahl, die zu ihm gehörte (dieselben Objekte)."""
@@ -787,8 +700,7 @@ class MainWindow(QMainWindow):
     def copy_selected(self) -> None:
         """Ausgewählte Objekte (in Zeichenreihenfolge) in die interne Zwischenablage kopieren –
         im Schreibmodus den markierten Text in die Zwischenablage des Systems."""
-        if self.edit_session.active:
-            self.panel("text").edit.copy()
+        if self.edit_session.copy():
             self._update_edit_actions()             # Einfügen ist jetzt möglich
             return
         indices = sorted(self.canvas.selection())
@@ -797,19 +709,14 @@ class MainWindow(QMainWindow):
             self._update_edit_actions()
 
     def cut_selected(self) -> None:
-        if self.edit_session.active:
-            self.panel("text").edit.cut()
-            return
-        self.copy_selected()
-        self.delete_selected()
+        if not self.edit_session.cut():
+            self.copy_selected()
+            self.delete_selected()
 
     def paste(self) -> None:
         """Zwischenablage einfügen – jedes Mal 2 mm weiter versetzt; Eingefügtes ist ausgewählt.
         Im Schreibmodus Text aus der Zwischenablage des Systems (als reiner Text)."""
-        if self.edit_session.active:
-            self.panel("text").edit.paste()
-            return
-        if self._clipboard:
+        if not self.edit_session.paste() and self._clipboard:
             self._clipboard = [_offset(obj) for obj in self._clipboard]
             self._insert(copy.deepcopy(self._clipboard))
 
diff --git a/src/labelwerk/gui/panels/position.py b/src/labelwerk/gui/panels/position.py
new file mode 100644
index 0000000..7e1dd65
--- /dev/null
+++ b/src/labelwerk/gui/panels/position.py
@@ -0,0 +1,75 @@
+"""Bereich „Position“ der Objekt-Panels: Lage (X/Y) und Größe (B/H) des Rahmens in mm.
+
+Gemeinsames Widget für alle Objektarten; das Panel zeigt damit den Rahmen, wie ihn das
+Hauptfenster gerendert hat (``show_frame``), und meldet geänderte Felder (``edited``).
+"""
+from __future__ import annotations
+
+from PySide6.QtCore import Signal
+from PySide6.QtWidgets import QGridLayout, QLabel, QWidget
+
+from ...layout import Rect
+from ..widgets import DoubleSpinBox
+
+POSITION_MM = (-999.9, 999.9)    # Lage darf auch neben dem Etikett liegen (ragt hinaus)
+SIZE_MM = (1.0, 999.9)
+FRAME_ONLY = "Nur mit fester Rahmengröße änderbar"
+_FIELDS = (("x", "X", "Abstand vom linken Etikettrand"),
+           ("y", "Y", "Abstand vom oberen Etikettrand"),
+           ("w", "B", "Breite des Rahmens"),
+           ("h", "H", "Höhe des Rahmens"))
+
+
+class PositionSection(QWidget):
+    """Vier Zahlenfelder X/Y/B/H (mm, 0,1 mm genau). Breite und Höhe lassen sich nur ändern,
+    wenn das Objekt eine änderbare Größe hat (``set_size_editable``) – sonst zeigen sie sie
+    nur an (Pfeile sichtbar, ohne Wirkung). Der Besitzer ruft ``set_size_editable`` (oder
+    ``show_frame``) jedes Mal auf, wenn sich bei seinem Objekt ändert, ob die Größe änderbar
+    ist (z. B. feste Rahmengröße an/aus) – sonst meldet der Bereich veraltet."""
+
+    edited = Signal(str, float)     # Feld ("x" | "y" | "w" | "h") und neuer Wert in mm
+
+    def __init__(self, parent=None):
+        super().__init__(parent)
+        self._size_editable = True
+        self.spins = {key: DoubleSpinBox() for key, _, _ in _FIELDS}   # x, y, w, h
+        grid = QGridLayout(self)
+        grid.setContentsMargins(0, 0, 0, 0)
+        for i, (key, text, tip) in enumerate(_FIELDS):
+            spin = self.spins[key]
+            spin.setDecimals(1)
+            spin.setSingleStep(0.1)
+            spin.setRange(*(POSITION_MM if key in "xy" else SIZE_MM))
+            spin.setKeyboardTracking(False)        # erst nach Enter/Fokuswechsel/Pfeil übernehmen
+            spin.setToolTip(tip)
+            label = QLabel(text)
+            label.setToolTip(tip)
+            grid.addWidget(label, i // 2, (i % 2) * 2)
+            grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)
+            spin.valueChanged.connect(lambda value, k=key: self._changed(k, value))
+        grid.setColumnStretch(1, 1)
+        grid.setColumnStretch(3, 1)
+        self.set_size_editable(False)
+
+    def show_frame(self, rect: Rect | None, editable_size: bool) -> None:
+        """Rahmen in mm anzeigen (None = Nullen), ohne ``edited`` auszulösen."""
+        for key, spin in self.spins.items():
+            spin.blockSignals(True)
+            spin.setValue(getattr(rect, key) if rect is not None else 0.0)
+            spin.blockSignals(False)
+        self.set_size_editable(editable_size)
+
+    def set_size_editable(self, editable: bool) -> None:
+        """Breite/Höhe änderbar bzw. nur Anzeige der Größe."""
+        self._size_editable = editable
+        for spin, name in ((self.spins["w"], "Breite"), (self.spins["h"], "Höhe")):
+            if spin.isReadOnly() == editable:
+                spin.setReadOnly(not editable)       # Pfeile bleiben sichtbar, wirken aber nicht
+                spin.style().unpolish(spin)          # Stylesheet: [readOnly="true"] neu anwenden
+                spin.style().polish(spin)
+            spin.setToolTip(f"{name} des Rahmens" + ("" if editable else f" – {FRAME_ONLY}"))
+
+    def _changed(self, key: str, value: float) -> None:
+        if key in "wh" and not self._size_editable:
+            return
+        self.edited.emit(key, value)
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index 984deb9..e9c5928 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -3,8 +3,8 @@
 Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
 Formatierung auf den ganzen Text; sonst nur auf die Markierung. Im Schreibmodus wirkt sie
 ohne Markierung aufs Weitertippen (Textposition: auf den Absatz der Schreibmarke) – außer
-der Rahmen ist noch leer. Bereich „Position“: Lage und (mit fester Rahmengröße) Größe des
-Rahmens in mm.
+der Rahmen ist noch leer. Bereich „Position“ (``panels.position``): Lage und (mit fester
+Rahmengröße) Größe des Rahmens in mm.
 
 Geschrieben wird direkt auf dem Etikett (``gui.text_edit_mode``): Der Editor ``edit`` ist
 dafür ein unsichtbarer Eingabepuffer (Kind des Panels, Größe 0, nicht im Layout) – er behält
@@ -16,25 +16,22 @@ import math
 from PySide6.QtCore import QSize, Qt, Signal
 from PySide6.QtGui import (QAction, QFont, QIcon, QTextCharFormat, QTextCursor, QTextFormat,
                            QTextOption)
-from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QGridLayout, QHBoxLayout,
-                               QLabel, QPushButton, QTextEdit)
+from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayout, QLabel,
+                               QPushButton, QTextEdit)
 
 from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
 from ...fonts import DEFAULT_FAMILY
 from ...layout import Rect
 from ...render import REF_PT
 from ..symbols import line_icon
-from ..widgets import DoubleSpinBox
 from . import Panel
+from .position import PositionSection
 
 _P = QTextFormat.Property
 
 SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
 DEFAULT_PT = 19
 HINT = "Auf das Etikett klicken, um einen Textrahmen anzulegen"
-POSITION_MM = (-999.9, 999.9)    # Lage darf auch neben dem Etikett liegen (ragt hinaus)
-SIZE_MM = (1.0, 999.9)
-_FRAME_ONLY = "Nur mit fester Rahmengröße änderbar"
 _ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                 "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}
 
@@ -169,27 +166,10 @@ class TextPanel(Panel):
         self.layout_.addWidget(self.fit)
 
         self.section("Position (mm)")
-        grid = QGridLayout()
-        self.pos_x, self.pos_y, self.pos_w, self.pos_h = (DoubleSpinBox() for _ in range(4))
-        self._frame_spins = {"x": self.pos_x, "y": self.pos_y, "w": self.pos_w, "h": self.pos_h}
-        for i, (key, text, tip) in enumerate((("x", "X", "Abstand vom linken Etikettrand"),
-                                              ("y", "Y", "Abstand vom oberen Etikettrand"),
-                                              ("w", "B", "Breite des Rahmens"),
-                                              ("h", "H", "Höhe des Rahmens"))):
-            spin = self._frame_spins[key]
-            spin.setDecimals(1)
-            spin.setSingleStep(0.1)
-            spin.setRange(*(POSITION_MM if key in "xy" else SIZE_MM))
-            spin.setKeyboardTracking(False)        # erst nach Enter/Fokuswechsel/Pfeil übernehmen
-            spin.setToolTip(tip)
-            label = QLabel(text)
-            label.setToolTip(tip)
-            grid.addWidget(label, i // 2, (i % 2) * 2)
-            grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)
-            spin.valueChanged.connect(lambda value, k=key: self._frame_changed(k, value))
-        grid.setColumnStretch(1, 1)
-        grid.setColumnStretch(3, 1)
-        self.layout_.addLayout(grid)
+        self.position = PositionSection()
+        self.pos_x, self.pos_y, self.pos_w, self.pos_h = (self.position.spins[k] for k in "xywh")
+        self.position.edited.connect(self._frame_changed)
+        self.layout_.addWidget(self.position)
 
         self.error = QLabel()
         self.error.setObjectName("error")
@@ -242,7 +222,7 @@ class TextPanel(Panel):
     def _editing_widgets(self):
         return (self.edit, self.family, self.size, self.grow, self.shrink, self.bold,
                 self.italic, self.underline, *self.align_buttons.values(), self.fit,
-                *self._frame_spins.values())
+                *self.position.spins.values())
 
     def set_editing(self, editing: bool) -> None:
         """Schreibmodus an/aus: Formatieren ohne Markierung wirkt dann aufs Weitertippen."""
@@ -549,26 +529,18 @@ class TextPanel(Panel):
     def show_frame(self, rect: Rect | None) -> None:
         """Rahmen des bearbeiteten Objekts in mm anzeigen (vom Hauptfenster nach dem Rendern)."""
         self._frame = rect
-        for key, spin in self._frame_spins.items():
-            spin.blockSignals(True)
-            spin.setValue(getattr(rect, key) if rect is not None else 0.0)
-            spin.blockSignals(False)
-        self._update_frame_editing()
+        self.position.show_frame(rect, self._fixed_frame())
 
     def _update_frame_editing(self) -> None:
         """Breite/Höhe nur mit fester Rahmengröße änderbar, sonst Anzeige der Größe."""
-        fixed = self.index is not None and self.obj.fit
-        for spin in (self.pos_w, self.pos_h):
-            if spin.isReadOnly() == fixed:
-                spin.setReadOnly(not fixed)          # Pfeile bleiben sichtbar, wirken aber nicht
-                spin.style().unpolish(spin)          # Stylesheet: [readOnly="true"] neu anwenden
-                spin.style().polish(spin)
-            spin.setToolTip(("Breite" if spin is self.pos_w else "Höhe") + " des Rahmens"
-                            + ("" if fixed else f" – {_FRAME_ONLY}"))
+        self.position.set_size_editable(self._fixed_frame())
+
+    def _fixed_frame(self) -> bool:
+        return self.index is not None and self.obj.fit
 
     def _frame_changed(self, key: str, value: float) -> None:
         if self.index is None or (key in "wh" and not self.obj.fit):
-            return
+            return                                  # Größe nur mit fester Rahmengröße
         self.frame_edited.emit(key, value)
 
     def _sync_buttons(self) -> None:
diff --git a/src/labelwerk/gui/text_edit_mode.py b/src/labelwerk/gui/text_edit_mode.py
index 0499c0e..d07efc2 100644
--- a/src/labelwerk/gui/text_edit_mode.py
+++ b/src/labelwerk/gui/text_edit_mode.py
@@ -14,7 +14,8 @@ gehen wie die Knöpfe im Dokument weiter, wenn im Editor nichts mehr zurück- bz
 wiederherzustellen ist. Ein Rahmen ohne feste Größe wächst an der Kante
 seiner Textposition (``layout.anchor_after_edit``). Start und Ende samt Rückgängig-Schritt
 (eine Bearbeitung = ein Schritt) steuert das Hauptfenster (``MainWindow.edit_text``,
-``finish_editing``).
+``finish_editing``); Rückgängig, Zwischenablage und die Freigabe ihrer Knöpfe gibt es im
+Schreibmodus an die Sitzung weiter (``undo``, ``copy`` … ``update_actions``).
 """
 from __future__ import annotations
 
@@ -131,6 +132,85 @@ class TextEditSession(QObject):
             self._quiet = False
         self.update_marks()
 
+    # --- Befehle (Knöpfe, Kürzel) --------------------------------------------
+    # Rückgabe True = im Schreibmodus erledigt; False = das Hauptfenster führt den Befehl
+    # auf dem Dokument bzw. der Auswahl aus.
+    def undo(self) -> bool:
+        """Rückgängig im Editor; ist dort nichts mehr zurückzunehmen, endet der Schreibmodus
+        und es geht im Dokument weiter (False). Ein leerer neuer Rahmen entfällt dabei – das
+        ist dann der ganze Schritt. Hat auch das Dokument nichts: weiter schreiben."""
+        if not self.active:
+            return False
+        if self._editor.document().isUndoAvailable():
+            self._editor.undo()
+            return True
+        window = self._window
+        obj = window.doc.objects[self.index]
+        if obj.positioned and obj.is_empty():
+            selection = window.history.selection    # Auswahl vor dem Anlegen
+            window.finish_editing()
+            self._canvas.set_selection(selection)
+            return True
+        if not window.history.can_undo(window.doc):
+            return True                             # nichts zurückzunehmen: weiter schreiben
+        window.finish_editing()
+        return False
+
+    def redo(self) -> bool:
+        """Wiederherstellen im Editor; hat er nichts mehr, endet der Schreibmodus und es geht
+        im Dokument weiter (False) – wie bei ``undo``."""
+        if not self.active:
+            return False
+        if self._editor.document().isRedoAvailable():
+            self._editor.redo()
+            return True
+        window = self._window
+        if not window.history.can_redo(window.doc):
+            return True                             # nichts zu wiederholen: weiter schreiben
+        window.finish_editing()
+        return False
+
+    def copy(self) -> bool:
+        """Markierten Text in die Zwischenablage des Systems kopieren."""
+        active = self.active          # vorher merken: endet die Sitzung dabei, gilt er trotzdem
+        if active:
+            self._editor.copy()
+        return active
+
+    def cut(self) -> bool:
+        """Markierten Text ausschneiden (Zwischenablage des Systems)."""
+        active = self.active          # vorher merken: endet die Sitzung dabei, gilt er trotzdem
+        if active:
+            self._editor.cut()
+        return active
+
+    def paste(self) -> bool:
+        """Text aus der Zwischenablage des Systems einfügen (als reiner Text)."""
+        active = self.active          # vorher merken: endet die Sitzung dabei, gilt er trotzdem
+        if active:
+            self._editor.paste()
+        return active
+
+    def update_actions(self, actions: dict) -> bool:
+        """Im Schreibmodus wirken die Knöpfe auf den Text im Editor: Freigabe der Aktionen
+        (``gui.actions``) danach setzen; Rückgängig/Wiederherstellen auch, wenn erst das
+        Dokument wieder etwas hat."""
+        if not self.active:
+            return False
+        editor, window = self._editor, self._window
+        marked = editor.textCursor().hasSelection()
+        enabled = {"edit.cut": marked, "edit.copy": marked, "edit.paste": editor.canPaste(),
+                   "edit.duplicate": False, "edit.delete": False,
+                   "edit.undo": (editor.document().isUndoAvailable()
+                                 or window.history.can_undo(window.doc)),
+                   "edit.redo": (editor.document().isRedoAvailable()
+                                 or window.history.can_redo(window.doc)),
+                   "text.end_edit": True, "text.start_edit": False,
+                   "text.start_edit_enter": False}
+        for key, value in enabled.items():
+            actions[key].setEnabled(value)
+        return True
+
     # --- Anzeige ------------------------------------------------------------
     def update_marks(self) -> None:
         """Schreibmarke, Markierung und Rahmen aus Editor und aktuellem Zeilensatz an die
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 8c83d24..4cff4f9 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -8,6 +8,7 @@ Arbeitsfläche Schreibmarke, Treffer und Markierung.
 """
 from __future__ import annotations
 
+import copy
 import math
 from dataclasses import dataclass, field
 from functools import cached_property
@@ -170,6 +171,83 @@ def finish_object(prep: Prepared, doc: Document, size: tuple[int, int],
     return _finish(prep, _sheet(doc, model), *size)
 
 
+@dataclass
+class Rendered:
+    """Ergebnis von ``Renderer.render``: Etikettgröße (Druckpunkte in Leserichtung), die
+    einzelnen Objektbilder (je Objekt in ``doc.objects``) und das Druckbild daraus."""
+    size: tuple[int, int]
+    objects: list[RenderedObject]
+    image: Image.Image
+
+
+@dataclass
+class _Cached:
+    """Gemessenes und gerendertes Objekt samt Stand, aus dem es entstand."""
+    obj: TextObject            # hält das Objekt fest, damit seine id nicht neu vergeben wird
+    snapshot: TextObject
+    context: tuple
+    prepared: Prepared
+    size: tuple | None = None                  # Etikettgröße des Bilds (None = mit Position)
+    rendered: RenderedObject | None = None
+
+
+class Renderer:
+    """Rendert ein Dokument wiederholt und dabei nur, was sich geändert hat (Arbeitsfläche).
+
+    Gemessen wird ein Objekt nur, wenn es selbst oder sein Kontext (Modell, Etikett,
+    Ausrichtung, Rand, Länge) sich ändert; gezeichnet zusätzlich, wenn sich bei einem Objekt
+    ohne Position (steht mittig) die Etikettgröße ändert. Das Druckbild wird nur neu
+    zusammengesetzt, wenn sich ein Objektbild oder die Größe ändert. Ergebnis wie
+    ``render_document`` – Vorschau = Druck.
+    """
+
+    def __init__(self):
+        self._cache: dict[int, _Cached] = {}
+        self._composed: tuple = (None, [], None)   # Druckbild und woraus es entstand
+
+    def render(self, doc: Document, model: str = "QL-600") -> Rendered:
+        """Dokument rendern; ``ValueError`` (z. B. ``TextTooLarge``) lässt den Cache stehen."""
+        entries = self._prepare_all(doc, model)
+        size = label_size(doc, model, prepared=[e.prepared for e in entries])
+        objects = self._draw(entries, doc, model, size)
+        return Rendered(size, objects, self._compose(objects, size, doc.orientation))
+
+    def _prepare_all(self, doc: Document, model: str) -> list[_Cached]:
+        """Objekte messen; unveränderte kommen aus dem Cache."""
+        context = (model, doc.label_id, doc.orientation, doc.margin_mm, doc.length_mm)
+        cache: dict[int, _Cached] = {}
+        for obj in doc.objects:
+            entry = self._cache.get(id(obj))
+            if (entry is None or entry.obj is not obj or entry.context != context
+                    or entry.snapshot != obj):
+                entry = _Cached(obj, copy.deepcopy(obj), context,
+                                prepare_object(obj, doc, model))
+            cache[id(obj)] = entry
+        self._cache = cache
+        return [cache[id(obj)] for obj in doc.objects]
+
+    @staticmethod
+    def _draw(entries: list[_Cached], doc: Document, model: str,
+              size: tuple[int, int]) -> list[RenderedObject]:
+        """Gemessene Objekte zeichnen; ein Objekt ohne Position steht mittig und wird deshalb
+        auch neu gezeichnet, wenn sich die Etikettgröße ändert."""
+        for entry in entries:
+            key = None if entry.obj.positioned else size
+            if entry.rendered is None or entry.size != key:
+                entry.rendered = finish_object(entry.prepared, doc, size, model)
+                entry.size = key
+        return [entry.rendered for entry in entries]
+
+    def _compose(self, objects: list[RenderedObject], size: tuple[int, int],
+                 orientation: str) -> Image.Image:
+        """Druckbild – unverändert, solange dieselben Objektbilder auf derselben Größe liegen."""
+        key = (size, orientation)
+        if (key != self._composed[0] or len(objects) != len(self._composed[1])
+                or any(a is not b for a, b in zip(objects, self._composed[1]))):
+            self._composed = (key, list(objects), compose(objects, size, orientation))
+        return self._composed[2]
+
+
 def label_margins(doc: Document, model: str = "QL-600") -> tuple[int, int]:
     """Ränder (links/rechts, oben/unten) in Druckpunkten in Leserichtung."""
     sheet = _sheet(doc, model)
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1027 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/position.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/text_edit_mode.py src/labelwerk/render.py tests/gui/test_gui_edit_mode.py tests/gui/test_gui_position.py tests/gui/test_gui_textframe.py tests/test_renderer.py
git commit -m "Umbau: inkrementeller Renderer im Kern, Schreibmodus-Befehle in der Sitzung, Bereich Position als Widget

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Kern – Bild-Objekt: laden, zuschneiden, Schwarz/Weiß-Umwandlung, rendern, platzieren

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-10-17-bild-objekt-design.md`
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/files.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Create: `src/labelwerk/imaging.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/render.py`
- Modify: `tests/test_files.py`
- Create: `tests/test_image_object.py`
- Create: `tests/test_imaging.py`
- Modify: `tests/test_layout.py`
- Modify: `tests/test_renderer.py`

**Interfaces / Produces:** `document.ImageObject` (png, source, page, crop, x/y/w/h_mm, rotation, mode line|photo, threshold, invert, keep_ratio, dpi; `from_image`, `box()`, `natural_mm()`, `limit_resolution()`); `files.load_image(path, page) -> (RGB, dpi)`, `files.crop_box(img, dpi, ink)`, `files.page_count`; `imaging.to_layers/photo_curve/to_8bit/limit_size/on_white`; Rendern von Bildern im Renderer; `layout.keep_aspect(old, new, handle)`, Bilder als feste Rahmen in allen Layout-Funktionen; deutsche Lesefehler.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/test_files.py b/tests/test_files.py
index ba2b1ae..efc869e 100644
--- a/tests/test_files.py
+++ b/tests/test_files.py
@@ -1,7 +1,8 @@
 import pytest
 from PIL import Image, ImageDraw
 
-from labelwerk.files import crop, fit_to_label, load_file
+from labelwerk.files import NOT_WHITE, crop, crop_box, fit_to_label, load_file, load_image
+from labelwerk.imaging import MAX_PIXELS
 
 
 def _page(w=600, h=300):
@@ -166,6 +167,71 @@ def test_corrupt_png_gives_clear_error(tmp_path):
         load_file(path)
 
 
+@pytest.mark.parametrize("load", [load_file, load_image])
+def test_read_errors_have_german_reasons(tmp_path, load):
+    """Kein englischer Fehlertext (Errno, PDFium, Pillow) in der Meldung."""
+    (tmp_path / "ordner.png").mkdir()
+    (tmp_path / "kaputt.pdf").write_bytes(b"%PDF-1.4 kaputt")
+    (tmp_path / "kaputt.png").write_bytes(b"kein png")
+    cases = [("ordner.png", "ist ein Ordner"), ("kaputt.pdf", "keine gültige PDF-Datei"),
+             ("kaputt.png", "kein lesbares Bild")]
+    for name, reason in cases:
+        with pytest.raises(ValueError) as info:
+            load(tmp_path / name)
+        message = str(info.value)
+        assert message == f"Datei kann nicht gelesen werden: {name} ({reason})"
+
+
+def test_unreadable_file_without_permission(tmp_path, monkeypatch):
+    path = tmp_path / "gesperrt.png"
+    _page().save(path)
+
+    def denied(*args, **kwargs):
+        raise PermissionError(13, "Permission denied")
+    monkeypatch.setattr(Image, "open", denied)
+    with pytest.raises(ValueError, match=r"gesperrt.png \(keine Leserechte\)$"):
+        load_image(path)
+    with pytest.raises(ValueError, match=r"gesperrt.png \(keine Leserechte\)$"):
+        load_file(path)
+
+
+def test_truncated_image_has_german_reason(tmp_path):
+    import io
+    buffer = io.BytesIO()
+    Image.effect_noise((200, 200), 50).convert("RGB").save(buffer, "JPEG")
+    path = tmp_path / "halb.jpg"
+    path.write_bytes(buffer.getvalue()[:2000])
+    with pytest.raises(ValueError, match=r"halb.jpg \(Datei ist beschädigt oder unvollständig\)$"):
+        load_image(path)
+
+
+def test_broken_image_data_has_german_reason(tmp_path):
+    import io
+    buffer = io.BytesIO()
+    Image.new("RGB", (50, 50), "red").save(buffer, "PNG")
+    data = bytearray(buffer.getvalue())
+    data[60:80] = b"\xff" * 20                            # Bilddaten im IDAT zerstört
+    path = tmp_path / "kaputt2.png"
+    path.write_bytes(bytes(data))
+    with pytest.raises(ValueError, match=r"kaputt2.png \(Datei ist beschädigt oder unvollständig\)$"):
+        load_image(path)
+
+
+def test_encrypted_pdf_has_own_reason(tmp_path, monkeypatch):
+    import pypdfium2 as pdfium
+    import pypdfium2.raw as raw
+    path = tmp_path / "geheim.pdf"
+    _page().save(path, "PDF", resolution=300)
+
+    def locked(*args, **kwargs):
+        raise pdfium.PdfiumError("Failed to load document (PDFium: Incorrect password error).",
+                                 raw.FPDF_ERR_PASSWORD)
+    monkeypatch.setattr(pdfium, "PdfDocument", locked)
+    for load in (load_file, load_image):
+        with pytest.raises(ValueError, match=r"geheim.pdf \(PDF ist verschlüsselt\)$"):
+            load(path)
+
+
 def test_page_below_one_has_own_message(tmp_path):
     path = tmp_path / "seite.pdf"
     _page().save(path, "PDF", resolution=300)
@@ -215,3 +281,231 @@ def test_rotate_0_with_fit_keeps_orientation():
 def test_invalid_rotation():
     with pytest.raises(ValueError, match="Drehung"):
         fit_to_label(_motif(40, 20), "62", rotate=45)
+
+
+# --- Bilder als Objekt (load_image, crop_box) -----------------------------------------
+def _pixels(img: Image.Image) -> list:
+    """Pixel einer Zeile von links nach rechts."""
+    return [img.getpixel((x, 0)) for x in range(img.width)]
+
+
+def _colour(w=60, h=30):
+    """Farbbild: links rot, rechts weiß, schwarzer Punkt oben links."""
+    img = Image.new("RGB", (w, h), "white")
+    img.paste((255, 0, 0), (0, 0, w // 2, h))
+    img.putpixel((0, 0), (0, 0, 0))
+    return img
+
+
+@pytest.mark.parametrize("suffix, kwargs, expected_dpi", [
+    (".png", {}, 300), (".gif", {}, 300), (".webp", {"lossless": True}, 300),
+    (".jpg", {"quality": 100}, 300),
+    (".bmp", {}, 96)])                                    # BMP hat immer eine Angabe (Pillow: 96)
+def test_load_image_keeps_colour_and_size(tmp_path, suffix, kwargs, expected_dpi):
+    path = tmp_path / f"bild{suffix}"
+    _colour().save(path, **kwargs)
+    img, dpi = load_image(path)
+    assert img.mode == "RGB" and img.size == (60, 30)
+    assert dpi == pytest.approx(expected_dpi, abs=0.1)    # ohne Angabe 300 dpi
+    r, g, b = img.getpixel((40, 15))
+    assert min(r, g, b) > 240                             # weiß bleibt weiß
+    r, g, b = img.getpixel((10, 15))
+    assert r > 200 and g < 60 and b < 60                  # rot bleibt rot
+
+
+@pytest.mark.parametrize("suffix", [".png", ".jpg", ".bmp"])
+def test_load_image_reports_dpi_without_resampling(tmp_path, suffix):
+    path = tmp_path / f"bild{suffix}"
+    _colour().save(path, dpi=(600, 600))
+    img, dpi = load_image(path)
+    assert img.size == (60, 30)
+    assert dpi == pytest.approx(600, abs=0.5)
+
+
+def test_load_image_follows_exif_orientation(tmp_path):
+    path = tmp_path / "handy.jpg"
+    exif = Image.Exif()
+    exif[0x0112] = 6                                      # Kamera hochkant: 90° drehen
+    _colour().save(path, exif=exif)
+    img, _ = load_image(path)
+    assert img.size == (30, 60)
+
+
+def test_load_image_gif_uses_first_frame(tmp_path):
+    path = tmp_path / "animiert.gif"
+    frames = [Image.new("RGB", (8, 8), c) for c in ("black", "white", "white")]
+    frames[0].save(path, save_all=True, append_images=frames[1:])
+    img, _ = load_image(path)
+    assert img.getpixel((4, 4)) == (0, 0, 0)
+
+
+def test_load_image_transparency_becomes_white(tmp_path):
+    path = tmp_path / "frei.png"
+    img = Image.new("RGBA", (4, 1), (0, 0, 0, 0))
+    img.putpixel((3, 0), (0, 0, 255, 255))
+    img.save(path)
+    loaded, _ = load_image(path)
+    assert _pixels(loaded) == [(255, 255, 255)] * 3 + [(0, 0, 255)]
+
+
+def _pdf(path, pages):
+    """PDF aus Pillow, 300 dpi; Seite i hat einen schwarzen Block bei x = 100 · i."""
+    imgs = []
+    for i in range(pages):
+        img = Image.new("RGB", (600, 300), "white")
+        img.paste((0, 0, 0), (100 * i, 0, 100 * i + 50, 50))
+        imgs.append(img)
+    imgs[0].save(path, "PDF", resolution=300, save_all=True, append_images=imgs[1:])
+
+
+def test_load_image_pdf_page_selection(tmp_path):
+    path = tmp_path / "zwei.pdf"
+    _pdf(path, 2)
+    first, dpi = load_image(path)
+    second, _ = load_image(path, page=2)
+    assert dpi == 300 and first.mode == "RGB"
+    assert abs(first.width - 600) <= 1 and abs(first.height - 300) <= 1
+    assert first.getpixel((25, 25)) == (0, 0, 0) and first.getpixel((125, 25)) != (0, 0, 0)
+    assert second.getpixel((125, 25)) == (0, 0, 0) and second.getpixel((25, 25)) != (0, 0, 0)
+
+
+@pytest.mark.parametrize("page, message", [(3, "nur 2 Seite"), (0, "mindestens 1")])
+def test_load_image_pdf_missing_page(tmp_path, page, message):
+    path = tmp_path / "zwei.pdf"
+    _pdf(path, 2)
+    with pytest.raises(ValueError, match=message):
+        load_image(path, page=page)
+
+
+def test_load_image_huge_pdf_page_is_capped(tmp_path):
+    path = tmp_path / "plakat.pdf"
+    Image.new("RGB", (100, 50), "white").save(path, "PDF", resolution=2)   # 50 × 25 Zoll
+    img, dpi = load_image(path)
+    assert max(img.size) <= MAX_PIXELS
+    assert img.width / dpi == pytest.approx(50, rel=0.01)                  # Druckgröße bleibt
+
+
+def test_load_image_huge_raster_is_capped(tmp_path):
+    path = tmp_path / "lang.png"
+    Image.new("RGB", (MAX_PIXELS * 2, 10), "white").save(path)
+    img, dpi = load_image(path)
+    assert img.width == MAX_PIXELS and dpi == pytest.approx(150)
+
+
+@pytest.mark.parametrize("name", ["logo.svg", "notiz.txt", "ohne"])
+def test_load_image_unsupported_type(tmp_path, name):
+    (tmp_path / name).write_text("x")
+    with pytest.raises(ValueError, match="nicht unterstützt"):
+        load_image(tmp_path / name)
+
+
+def test_load_image_missing_and_broken(tmp_path):
+    with pytest.raises(FileNotFoundError, match="nicht gefunden"):
+        load_image(tmp_path / "fehlt.png")
+    (tmp_path / "kaputt.png").write_bytes(b"kein Bild")
+    with pytest.raises(ValueError, match="kann nicht gelesen werden"):
+        load_image(tmp_path / "kaputt.png")
+
+
+@pytest.mark.parametrize("img", [
+    _with_marks(), _with_marks(dotted=True), _with_marks(corners=("tl", "tr", "bl")),
+    _page()], ids=["Marken", "gepunktet", "drei Marken", "Inhalt"])
+def test_crop_box_is_what_crop_cuts(img):
+    box = crop_box(img)
+    assert img.crop(box).tobytes() == crop(img).tobytes()
+    assert crop_box(img.convert("RGB")) == box            # Farbe: dieselbe Logik
+
+
+def test_crop_box_scales_marks_with_resolution():
+    img = _with_marks()
+    big = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
+    l, t, r, b = crop_box(img)
+    assert crop_box(big, dpi=600) == pytest.approx((2 * l, 2 * t, 2 * r, 2 * b), abs=2)
+
+
+def test_crop_box_without_content_is_none():
+    assert crop_box(Image.new("RGB", (10, 10), "white")) is None
+    assert crop_box(Image.new("RGB", (10, 10), "white"), ink=NOT_WHITE) is None
+    assert crop_box(Image.new("RGB", (10, 10), (250, 250, 250)), ink=NOT_WHITE) is None
+    with pytest.raises(ValueError, match="keinen druckbaren Inhalt"):
+        crop(Image.new("L", (10, 10), 255))                # print-file: Meldung wie bisher
+
+
+def test_crop_box_not_white_keeps_light_photo_nearly_whole():
+    photo = Image.new("RGB", (300, 200), (200, 200, 200))   # hell, ohne Weiß
+    photo.paste((0, 0, 0), (140, 90, 160, 110))
+    assert crop_box(photo) == (140, 90, 160, 110)         # Schwelle 128: nur der Punkt
+    assert crop_box(photo, ink=NOT_WHITE) == (0, 0, 300, 200)
+
+
+def test_crop_box_not_white_finds_yellow_logo():
+    logo = Image.new("RGB", (300, 300), "white")
+    logo.paste((255, 220, 0), (50, 60, 250, 240))
+    assert crop_box(logo) is None                         # Gelb ist heller als 128
+    assert crop_box(logo, ink=NOT_WHITE) == (50, 60, 250, 240)
+
+
+@pytest.mark.parametrize("ink", [128, NOT_WHITE])
+def test_crop_box_flattens_transparency_first(ink):
+    rgba = Image.new("RGBA", (100, 100), (0, 0, 0, 0))     # durchsichtiges Schwarz
+    rgba.paste((0, 0, 0, 255), (40, 30, 60, 70))
+    assert crop_box(rgba, ink=ink) == (40, 30, 60, 70)
+    pal = rgba.convert("P")
+    pal.info["transparency"] = pal.getpixel((0, 0))
+    assert crop_box(pal, ink=ink) == (40, 30, 60, 70)
+
+
+def _png16(path, dpi=None):
+    """16-Bit-Graustufen-PNG mit Verlauf 0–65535 (256 × 1)."""
+    img = Image.new("I;16", (256, 1))
+    img.putdata([v * 257 for v in range(256)])
+    img.save(path, **({"dpi": dpi} if dpi else {}))
+
+
+def test_load_image_scales_16_bit_gray(tmp_path):
+    _png16(tmp_path / "tief.png")
+    img, _ = load_image(tmp_path / "tief.png")
+    assert _pixels(img) == [(v, v, v) for v in range(256)]
+
+
+def test_load_file_scales_16_bit_gray(tmp_path):
+    _png16(tmp_path / "tief.png")
+    assert _pixels(load_file(tmp_path / "tief.png")) == list(range(256))
+
+
+def test_load_image_rounds_dpi_from_file(tmp_path):
+    path = tmp_path / "bild.png"
+    _colour().save(path, dpi=(300, 300))                  # PNG speichert Punkte je Meter
+    assert Image.open(path).info["dpi"][0] != 300
+    assert load_image(path)[1] == 300
+
+
+def test_load_image_anisotropic_dpi_keeps_print_size(tmp_path):
+    path = tmp_path / "fax.png"
+    Image.new("RGB", (204, 98), "white").save(path, dpi=(204, 98))   # 1 × 1 Zoll
+    img, dpi = load_image(path)
+    assert dpi == pytest.approx(204, abs=0.02) and img.size == (204, 204)
+
+
+def test_load_image_anisotropic_dpi_limits_before_resizing(tmp_path, monkeypatch):
+    path = tmp_path / "gross.png"
+    Image.new("RGB", (2400, 600), "white").save(path, dpi=(1200, 300))   # 2 × 2 Zoll
+    sizes = []
+    original = Image.Image.resize
+
+    def spy(self, size, *args, **kwargs):
+        sizes.append(tuple(size))
+        return original(self, size, *args, **kwargs)
+    monkeypatch.setattr(Image.Image, "resize", spy)
+    img, dpi = load_image(path)
+    assert img.size == (1200, 1200) and dpi == 600
+    assert all(w <= 1200 and h <= 1200 for w, h in sizes)      # nie erst auf 2400 × 2400 hoch
+
+
+def test_load_image_anisotropic_dpi_follows_exif_rotation(tmp_path):
+    path = tmp_path / "handy.jpg"
+    exif = Image.Exif()
+    exif[0x0112] = 6                                      # hochkant: 90° drehen
+    Image.new("RGB", (100, 200), "white").save(path, exif=exif, dpi=(100, 200))  # 1 × 1 Zoll
+    img, dpi = load_image(path)
+    assert dpi == 200 and img.size == (200, 200)
diff --git a/tests/test_image_object.py b/tests/test_image_object.py
new file mode 100644
index 0000000..b1115a8
--- /dev/null
+++ b/tests/test_image_object.py
@@ -0,0 +1,231 @@
+"""Bild-Objekt (Etappe 3d-2a): Modell und Rendern."""
+import io
+import random
+
+import pytest
+from PIL import Image
+
+from labelwerk.document import Document, ImageObject, TextObject
+from labelwerk.imaging import MAX_PIXELS
+from labelwerk.labels import DPI
+from labelwerk.render import (MARGIN, Renderer, font_warnings, label_size, render_document,
+                              render_object, text_layout)
+
+
+def _dots(mm):
+    return round(mm * DPI / 25.4)
+
+
+def _source(w=600, h=300) -> Image.Image:
+    """Weißes Bild mit schwarzem Quadrat oben links (ein Zehntel der Breite)."""
+    img = Image.new("RGB", (w, h), "white")
+    img.paste((0, 0, 0), (0, 0, w // 10, w // 10))
+    return img
+
+
+def _image(**kw) -> ImageObject:
+    obj = ImageObject.from_image(_source(), 300, "test.png")
+    for key, value in kw.items():
+        setattr(obj, key, value)
+    return obj
+
+
+def _decoded(obj: ImageObject) -> Image.Image:
+    return Image.open(io.BytesIO(obj.png))
+
+
+# --- Modell -------------------------------------------------------------------------
+def test_defaults():
+    obj = _image()
+    assert (obj.mode, obj.threshold, obj.invert, obj.keep_ratio, obj.rotation) == \
+        ("line", 128, False, True, 0)
+    assert (obj.source, obj.page, obj.crop, obj.x_mm, obj.y_mm) == ("test.png", None, None, 0, 0)
+    assert not obj.is_empty() and obj.positioned
+
+
+def test_from_image_is_one_to_one_from_dpi():
+    obj = ImageObject.from_image(_source(), 300, "a.png")
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((50.8, 25.4))
+    half = ImageObject.from_image(_source(), 600, "a.png")
+    assert (half.w_mm, half.h_mm) == pytest.approx((25.4, 12.7))
+
+
+def test_from_image_stores_colour_original_as_png():
+    src = _source()
+    src.putpixel((300, 150), (255, 0, 0))
+    obj = ImageObject.from_image(src, 300, "a.png")
+    assert _decoded(obj).format == "PNG"
+    assert obj.image().mode == "RGB" and obj.image().tobytes() == src.tobytes()
+
+
+def test_from_image_flattens_transparency():
+    src = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
+    obj = ImageObject.from_image(src, 300, "Zwischenablage")
+    assert _decoded(obj).getextrema() == ((255, 255),) * 3
+
+
+def test_from_image_size_comes_from_crop():
+    obj = ImageObject.from_image(_source(), 300, "marke.pdf", page=2, crop=[0, 0, 60, 30])
+    assert obj.crop == (0, 0, 60, 30) and obj.page == 2
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((5.08, 2.54))
+    assert _decoded(obj).size == (600, 300)                # Original bleibt ganz
+
+
+def test_from_image_caps_huge_images_and_their_crop():
+    src = Image.new("RGB", (MAX_PIXELS * 2, 20), "white")
+    obj = ImageObject.from_image(src, 300, "lang.png", crop=(100, 0, 2100, 20))
+    assert _decoded(obj).size == (MAX_PIXELS, 10)
+    assert obj.crop == (50, 0, 1050, 10)
+    assert obj.w_mm == pytest.approx(2000 / 300 * 25.4)    # Druckgröße bleibt
+
+
+def test_repr_leaves_out_png_bytes():
+    assert "png=" not in repr(_image()) and "test.png" in repr(_image())
+
+
+def test_document_holds_text_and_images():
+    doc = Document("62", objects=[TextObject(""), _image()])
+    assert not doc.is_empty()
+
+
+# --- Rendern ------------------------------------------------------------------------
+def _doc(*objects, **kw) -> Document:
+    return Document("62", length_mm=80, objects=list(objects), **kw)
+
+
+def test_render_places_frame_one_to_one():
+    obj = _image(x_mm=2, y_mm=3)
+    r = render_object(obj, _doc(obj))
+    assert (r.x, r.y, r.w, r.h) == (_dots(2), _dots(3), 600, 300)
+    assert (r.image_dx, r.image_dy, r.layout) == (0, 0, None)
+    assert r.image.mode == "L" and r.image.size == (600, 300)
+    assert r.image.getpixel((5, 5)) == 0 and r.image.getpixel((300, 150)) == 255
+
+
+@pytest.mark.parametrize("rotation, corner", [(90, (295, 5)), (180, (595, 295)),
+                                              (270, (5, 595))])
+def test_render_rotation_turns_clockwise(rotation, corner):
+    obj = _image(rotation=rotation)
+    r = render_object(obj, _doc(obj))
+    size = (300, 600) if rotation in (90, 270) else (600, 300)
+    assert (r.w, r.h) == size and r.image.size == size
+    assert r.image.getpixel(corner) == 0                   # Quadrat oben links, gedreht
+    assert r.image.getpixel((5, 5)) == 255
+
+
+def test_keep_ratio_fits_into_wrong_frame_and_centres():
+    obj = _image(w_mm=50.8, h_mm=50.8)                      # Rahmen quadratisch, Bild 2:1
+    r = render_object(obj, _doc(obj))
+    assert r.image.size == (600, 600)
+    assert r.image.getpixel((5, 5)) == 255                 # oben 150 Punkte frei
+    assert r.image.getpixel((5, 155)) == 0                 # Quadrat beginnt bei 150
+    assert r.image.getpixel((5, 215)) == 255               # 60 hoch
+    obj.keep_ratio = False                                  # verzerrt: Quadrat doppelt so hoch
+    r = render_object(obj, _doc(obj))
+    assert r.image.getpixel((5, 5)) == 0 and r.image.getpixel((5, 110)) == 0
+    assert r.image.getpixel((5, 125)) == 255
+
+
+def test_render_scales_to_frame():
+    obj = _image(w_mm=25.4, h_mm=12.7)
+    r = render_object(obj, _doc(obj))
+    assert r.image.size == (300, 150)
+    assert r.image.getpixel((25, 25)) == 0 and r.image.getpixel((35, 35)) == 255
+
+
+def test_render_uses_crop():
+    obj = _image(crop=(0, 0, 60, 60), w_mm=5.08, h_mm=5.08)
+    r = render_object(obj, _doc(obj))
+    assert r.image.size == (60, 60) and r.image.getextrema() == (0, 0)
+
+
+def test_render_threshold_invert_and_photo():
+    src = Image.new("RGB", (100, 100), (150, 150, 150))
+    obj = ImageObject.from_image(src, 300, "grau.png")
+    doc = _doc(obj)
+    assert render_object(obj, doc).image.getextrema() == (255, 255)    # heller als 128
+    obj.threshold = 160
+    assert render_object(obj, doc).image.getextrema() == (0, 0)
+    obj.invert = True
+    assert render_object(obj, doc).image.getextrema() == (255, 255)
+    obj.invert, obj.mode, obj.threshold = False, "photo", 128
+    assert render_object(obj, doc).image.getextrema() == (0, 255)      # Punkte gestreut
+
+
+def _modules(module_px: int, n: int = 21, seed: int = 3) -> tuple[Image.Image, list]:
+    """Zufallsmuster aus ``n`` × ``n`` Modulen (wie ein QR-Code), je ``module_px`` Pixel."""
+    rng = random.Random(seed)
+    cells = [[rng.random() < 0.5 for _ in range(n)] for _ in range(n)]
+    img = Image.new("RGB", (n * module_px, n * module_px), "white")
+    for y, row in enumerate(cells):
+        for x, dark in enumerate(row):
+            if dark:
+                img.paste((0, 0, 0), (x * module_px, y * module_px,
+                                      (x + 1) * module_px, (y + 1) * module_px))
+    return img, cells
+
+
+@pytest.mark.parametrize("module_px, dpi", [(4, 300), (2, 150)])       # 1:1 und 2× vergrößert
+def test_codes_stay_bit_exact_at_one_to_one_and_double_size(module_px, dpi):
+    img, _ = _modules(module_px)
+    obj = ImageObject.from_image(img, dpi, "qr.png")
+    r = render_object(obj, _doc(obj))
+    ideal = img.convert("L").resize(r.image.size, Image.Resampling.NEAREST)
+    assert r.image.tobytes() == ideal.tobytes()
+
+
+def test_large_image_is_reduced_before_lanczos():
+    """Stark verkleinert: erst ganzzahlig reduzieren, dann Lanczos (``reducing_gap=2``)."""
+    from labelwerk import render
+    src = Image.radial_gradient("L").convert("RGB").resize((1800, 1200))
+    obj = ImageObject.from_image(src, 600, "gross.png")
+    obj.w_mm, obj.h_mm = 25.4, 25.4 * 2 / 3                # 300 × 200 Punkte
+    render._scaled_source.cache_clear()
+    picture = render._scaled_source(obj.png, None, (300, 200), True)
+    expected = src.resize((300, 200), Image.Resampling.LANCZOS, reducing_gap=2.0)
+    assert picture.tobytes() == expected.tobytes()
+
+
+@pytest.mark.parametrize("field, value, message", [
+    ("mode", "farbe", "Umwandlung"), ("threshold", 300, "Schwelle"),
+    ("rotation", 45, "Drehung"), ("crop", (0, 0, 700, 10), "Ausschnitt"),
+    ("crop", (10, 10, 10, 20), "Ausschnitt"), ("w_mm", 0, "Größe")])
+def test_invalid_image_settings_raise_at_render(field, value, message):
+    obj = _image(**{field: value})
+    with pytest.raises(ValueError, match=message):
+        render_object(obj, _doc(obj))
+
+
+def test_image_grows_auto_length():
+    obj = _image(x_mm=1, y_mm=10)
+    doc = Document("62", objects=[obj])
+    margin = round(1.0 * DPI / 25.4)
+    assert label_size(doc) == (696, _dots(10) + 300 + margin)
+
+
+def test_preview_equals_print_with_text_and_images():
+    for orientation in ("vertical", "horizontal"):
+        doc = _doc(TextObject("Absender", size_pt=12, x_mm=2, y_mm=2),
+                   _image(x_mm=10, y_mm=10, rotation=90),
+                   _image(x_mm=30, y_mm=5, mode="photo", invert=True),
+                   orientation=orientation)
+        printed = render_document(doc)
+        assert Renderer().render(doc).image.tobytes() == printed.tobytes()
+        assert printed.size == ((label_size(doc)[::-1]) if orientation == "horizontal"
+                                else label_size(doc))
+
+
+def test_image_ink_lands_on_the_label():
+    obj = _image(x_mm=2, y_mm=3)
+    img = render_document(_doc(obj))
+    x, y = _dots(2), _dots(3)
+    assert img.getpixel((x + 5, y + 5)) == (0, 0, 0)
+    assert img.getpixel((x + 300, y + 150)) == (255, 255, 255)
+    assert img.getpixel((MARGIN, MARGIN)) == (255, 255, 255)
+
+
+def test_text_helpers_skip_or_refuse_images():
+    obj = _image()
+    assert font_warnings(_doc(obj)) == []
+    with pytest.raises(TypeError, match="Text"):
+        text_layout(obj, _doc(obj))
diff --git a/tests/test_imaging.py b/tests/test_imaging.py
new file mode 100644
index 0000000..54d3782
--- /dev/null
+++ b/tests/test_imaging.py
@@ -0,0 +1,147 @@
+"""Bilder für den Druck: Schwarz/Weiß-Umwandlung und Größenbegrenzung (``imaging``)."""
+import struct
+
+import pytest
+from PIL import Image
+
+from labelwerk.imaging import MAX_DPI, MAX_PIXELS, limit_size, on_white, to_8bit, to_layers
+
+
+def _pixels(img: Image.Image) -> list:
+    """Pixel einer Zeile von links nach rechts."""
+    return [img.getpixel((x, 0)) for x in range(img.width)]
+
+
+def _gradient() -> Image.Image:
+    """Graustufen 0–255 nebeneinander (eine Zeile)."""
+    img = Image.new("L", (256, 1))
+    img.putdata(list(range(256)))
+    return img
+
+
+def _ink(layer: Image.Image) -> int:
+    """Anzahl bedruckter (schwarzer) Punkte einer Ebene."""
+    return layer.histogram()[0]
+
+
+def test_line_mode_is_a_hard_threshold():
+    layers = to_layers(_gradient(), "line", 128, False)
+    assert list(layers) == ["black"]
+    black = layers["black"]
+    assert black.mode == "1" and black.size == (256, 1)
+    assert [black.getpixel((x, 0)) for x in (0, 127, 128, 255)] == [0, 0, 255, 255]
+
+
+@pytest.mark.parametrize("threshold, ink", [(0, 0), (1, 1), (128, 128), (200, 200), (255, 255)])
+def test_higher_threshold_prints_more(threshold, ink):
+    assert _ink(to_layers(_gradient(), "line", threshold, False)["black"]) == ink
+
+
+def test_invert_swaps_ink_and_paper():
+    normal = to_layers(_gradient(), "line", 100, False)["black"]
+    inverted = to_layers(_gradient(), "line", 100, True)["black"]
+    assert _ink(inverted) == 256 - _ink(normal)
+    assert inverted.getpixel((0, 0)) == 255 and inverted.getpixel((255, 0)) == 0
+
+
+def test_colour_counts_by_brightness():
+    img = Image.new("RGB", (2, 1))
+    img.putdata([(255, 0, 0), (255, 255, 0)])            # Rot dunkel, Gelb hell
+    black = to_layers(img, "line", 128, False)["black"]
+    assert [black.getpixel((x, 0)) for x in (0, 1)] == [0, 255]
+
+
+@pytest.mark.parametrize("gray, low, high", [(128, 0.4, 0.6), (64, 0.7, 0.8), (192, 0.2, 0.3)])
+def test_photo_mode_dithers_gray_into_dots(gray, low, high):
+    black = to_layers(Image.new("L", (100, 100), gray), "photo", 128, False)["black"]
+    assert black.mode == "1"
+    assert low <= _ink(black) / 10000 <= high
+
+
+def test_photo_threshold_darkens_mid_grey_monotonically():
+    img = Image.new("L", (100, 100), 128)
+    inks = [_ink(to_layers(img, "photo", t, False)["black"]) for t in (0, 64, 128, 192, 255)]
+    assert inks == sorted(inks) and len(set(inks)) == len(inks)
+    assert inks[0] < 2000 and inks[-1] > 8000
+
+
+def test_photo_threshold_128_is_plain_dithering():
+    img = _gradient().resize((256, 40))
+    black = to_layers(img, "photo", 128, False)["black"]
+    assert black.tobytes() == img.convert("1", dither=Image.Dither.FLOYDSTEINBERG).tobytes()
+
+
+@pytest.mark.parametrize("threshold", [0, 1, 64, 128, 192, 254, 255])
+def test_photo_keeps_white_and_black(threshold):
+    """Weißes Papier bekommt nie Punkte, Schwarz bleibt voll – bei jeder Schwelle."""
+    white, black = Image.new("L", (20, 20), 255), Image.new("L", (20, 20), 0)
+    assert _ink(to_layers(white, "photo", threshold, False)["black"]) == 0
+    assert _ink(to_layers(black, "photo", threshold, False)["black"]) == 400
+    assert _ink(to_layers(white, "photo", threshold, True)["black"]) == 400
+
+
+@pytest.mark.parametrize("mode, threshold, message", [
+    ("grau", 128, "Umwandlung"), ("line", -1, "Schwelle"), ("photo", 256, "Schwelle"),
+    ("line", 12.5, "Schwelle"), ("line", True, "Schwelle")])
+def test_invalid_settings_raise(mode, threshold, message):
+    with pytest.raises(ValueError, match=message):
+        to_layers(_gradient(), mode, threshold, False)
+
+
+def test_on_white_flattens_transparency():
+    img = Image.new("RGBA", (2, 1))
+    img.putdata([(0, 0, 0, 0), (255, 0, 0, 255)])
+    flat = on_white(img)
+    assert flat.mode == "RGB"
+    assert _pixels(flat) == [(255, 255, 255), (255, 0, 0)]
+
+
+def test_on_white_palette_with_transparency_and_gray():
+    pal = Image.new("P", (2, 1))
+    pal.putpalette([0, 0, 0, 0, 0, 255])
+    pal.putdata([0, 1])
+    pal.info["transparency"] = 0
+    assert _pixels(on_white(pal)) == [(255, 255, 255), (0, 0, 255)]
+    assert on_white(Image.new("L", (1, 1), 7)).getpixel((0, 0)) == (7, 7, 7)
+    assert on_white(Image.new("LA", (1, 1), (0, 0))).getpixel((0, 0)) == (255, 255, 255)
+
+
+def _gray16(mode: str) -> Image.Image:
+    """Verlauf 0–65535 in 16 Bit (wie ein 16-Bit-PNG) bzw. 32 Bit (``"I"``)."""
+    values = [v * 257 for v in range(256)]
+    if mode == "I":
+        img = Image.new("I", (256, 1))
+        img.putdata(values)
+        return img
+    order = ">" if mode == "I;16B" else "<"
+    return Image.frombytes(mode, (256, 1), struct.pack(f"{order}256H", *values))
+
+
+@pytest.mark.parametrize("mode", ["I;16", "I;16B", "I"])
+def test_16_bit_gray_is_scaled_not_clipped(mode):
+    img = _gray16(mode)
+    assert _pixels(to_8bit(img)) == list(range(256))
+    assert to_8bit(img).mode == "L"
+    assert _pixels(on_white(img)) == [(v, v, v) for v in range(256)]
+
+
+def test_to_8bit_leaves_other_modes_alone():
+    img = Image.new("RGB", (2, 2))
+    assert to_8bit(img) is img
+
+
+def test_limit_size_leaves_normal_images_alone():
+    img = Image.new("RGB", (600, 300))
+    assert limit_size(img, 300) == (img, 300)
+
+
+def test_limit_size_caps_resolution_keeping_print_size():
+    img, dpi = limit_size(Image.new("RGB", (2400, 1200)), 1200)
+    assert (img.size, dpi) == ((1200, 600), MAX_DPI)
+
+
+def test_limit_size_caps_longest_side_keeping_print_size():
+    img, dpi = limit_size(Image.new("RGB", (100, MAX_PIXELS + 1000)), 300)
+    assert img.height == MAX_PIXELS
+    assert img.height / dpi == pytest.approx((MAX_PIXELS + 1000) / 300, rel=1e-3)
+    assert img.width / dpi == pytest.approx(100 / 300, rel=0.02)
diff --git a/tests/test_layout.py b/tests/test_layout.py
index d7950d4..0de7c7d 100644
--- a/tests/test_layout.py
+++ b/tests/test_layout.py
@@ -2,7 +2,7 @@
 import pytest
 
 from labelwerk import layout, render
-from labelwerk.document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
+from labelwerk.document import MAX_PT, MIN_PT, Document, ImageObject, Paragraph, Span, TextObject
 from labelwerk.labels import DPI
 from labelwerk.layout import Rect, Snap
 from labelwerk.render import MARGIN, RenderedObject, render_document, render_object
@@ -427,9 +427,9 @@ def test_resize_fit_object_changes_frame():
     obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8)
     rendered = _rendered(1, 1, 20, 8, base_pt=30)
     old = layout.object_rect(rendered)
-    for corner in (True, False):
+    for handle in ("bl", "b"):
         new = Rect(old.x - 1, old.y, old.w + 5, old.h + 4)
-        resized = layout.resize(obj, new, rendered, corner=corner)
+        resized = layout.resize(obj, new, rendered, handle)
         assert (resized.x_mm, resized.y_mm, resized.w_mm, resized.h_mm) == \
             pytest.approx((0, 1, 25, 12))
         assert resized.fit and resized.size_pt == 12
@@ -440,7 +440,7 @@ def test_resize_corner_scales_text_without_frame():
     rendered = _rendered(1, 1, 10, 5)
     old = layout.object_rect(rendered)
     bigger = Rect(old.x, old.y, old.w * 1.5, old.h * 1.5)
-    resized = layout.resize(obj, bigger, rendered, corner=True)
+    resized = layout.resize(obj, bigger, rendered, "br")
     assert (resized.size_pt, resized.fit) == (18, False)
     assert (resized.x_mm, resized.y_mm) == pytest.approx((1, 1))
     assert resized.w_mm is None
@@ -450,7 +450,7 @@ def test_resize_corner_of_auto_object_uses_effective_size():
     rendered = _rendered(1, 1, 10, 5, base_pt=20)
     old = layout.object_rect(rendered)
     smaller = Rect(0, 0, old.w / 2, old.h / 2)
-    resized = layout.resize(TextObject("A"), smaller, rendered, corner=True)
+    resized = layout.resize(TextObject("A"), smaller, rendered, "tl")
     assert (resized.size_pt, resized.x_mm, resized.y_mm) == (10, 0, 0)
 
 
@@ -458,7 +458,7 @@ def test_resize_edge_turns_fixed_frame_on():
     obj = TextObject("A", size_pt=12, x_mm=1, y_mm=1, rotation=90)
     rendered = _rendered(1, 1, 5, 10)
     old = layout.object_rect(rendered)
-    resized = layout.resize(obj, Rect(old.x, old.y, old.w, old.h + 8), rendered, corner=False)
+    resized = layout.resize(obj, Rect(old.x, old.y, old.w, old.h + 8), rendered, "b")
     assert resized.fit
     assert (resized.x_mm, resized.y_mm, resized.w_mm, resized.h_mm) == \
         pytest.approx((1, 1, old.h + 8, old.w), abs=0.001)             # ungedreht gespeichert
@@ -836,7 +836,7 @@ def test_edge_resize_of_auto_size_text_then_move_keeps_frame():
     obj = TextObject("A", x_mm=1, y_mm=1)                    # size_pt None
     rendered = _rendered(1, 1, 10, 5, base_pt=20)
     old = layout.object_rect(rendered)
-    framed = layout.resize(obj, Rect(old.x, old.y, old.w + 10, old.h), rendered, corner=False)
+    framed = layout.resize(obj, Rect(old.x, old.y, old.w + 10, old.h), rendered, "r")
     assert framed.fit and framed.size_pt == 20
     moved = layout.move(framed, Rect(old.x + 2, old.y, old.w + 10, old.h),
                         _rendered(1, 1, 20, 5, base_pt=20))
@@ -886,3 +886,203 @@ def test_snap_to_start_margin_on_auto_length(grow, moving):
     axis = "y" if grow == "y" else "x"
     assert (s.dy if grow == "y" else s.dx) == pytest.approx(-0.4)
     assert (axis, 1.0) in s.guides
+
+
+# --- Bilder (Etappe 3d-2a) ----------------------------------------------------------
+def _picture(x_mm=10, y_mm=5, w_mm=20, h_mm=10, **kw):
+    from PIL import Image
+    obj = ImageObject.from_image(Image.new("RGB", (40, 20), "black"), 300, "bild.png")
+    obj.x_mm, obj.y_mm, obj.w_mm, obj.h_mm = x_mm, y_mm, w_mm, h_mm
+    for key, value in kw.items():
+        setattr(obj, key, value)
+    return obj
+
+
+def test_exact_rect_of_image_is_its_frame():
+    assert layout.exact_rect(_picture(), _rendered(10, 5, 20, 10)) == Rect(10, 5, 20, 10)
+    turned = _picture(rotation=90)
+    assert layout.exact_rect(turned, _rendered(10, 5, 10, 20)) == Rect(10, 5, 10, 20)
+
+
+def test_move_image_keeps_size():
+    obj = _picture()
+    rendered = _rendered(10, 5, 20, 10)
+    moved = layout.move(obj, layout.object_rect(rendered).moved(1.5, -0.5), rendered)
+    assert _model_frame(moved) == pytest.approx((11.5, 4.5, 20, 10))
+    assert isinstance(moved, ImageObject) and moved.png is obj.png and obj.x_mm == 10
+
+
+def test_set_frame_of_image_sets_position_and_size():
+    obj = _picture(rotation=270)
+    placed = layout.set_frame(obj, Rect(1, 2, 8, 30), _rendered(10, 5, 10, 20))
+    assert _model_frame(placed) == (1, 2, 30, 8)                   # ungedreht gespeichert
+
+
+@pytest.mark.parametrize("handle, new, expected", [
+    ("br", Rect(10, 5, 40, 12), (10, 5, 40, 20)),     # rechts unten gezogen: größeres Maß zählt
+    ("bl", Rect(0, 5, 30, 25), (-20, 5, 50, 25)),     # links unten: rechte obere Ecke bleibt
+    ("tl", Rect(14, 1, 16, 14), (2, 1, 28, 14)),      # links oben: rechte untere Ecke bleibt
+])
+def test_resize_image_corner_keeps_ratio(handle, new, expected):
+    obj = _picture()
+    rendered = _rendered(10, 5, 20, 10)
+    shown = layout.object_rect(rendered)
+    delta = Rect(new.x - 10 + shown.x, new.y - 5 + shown.y, new.w - 20 + shown.w,
+                 new.h - 10 + shown.h)                 # relativ zum gerundeten Rahmen
+    resized = layout.resize(obj, delta, rendered, handle)
+    assert _model_frame(resized) == pytest.approx(expected, abs=0.002)
+    assert resized.w_mm / resized.h_mm == pytest.approx(2)
+
+
+def test_resize_image_edge_with_keep_ratio_scales_uniformly_around_centre():
+    obj = _picture()
+    rendered = _rendered(10, 5, 20, 10)
+    old = layout.object_rect(rendered)
+    wider = layout.resize(obj, Rect(old.x, old.y, old.w + 10, old.h), rendered, "r")
+    assert _model_frame(wider) == pytest.approx((10, 2.5, 30, 15), abs=0.002)   # Mitte senkrecht
+    taller = layout.resize(obj, Rect(old.x, old.y - 5, old.w, old.h + 5), rendered, "t")
+    assert _model_frame(taller) == pytest.approx((5, 0, 30, 15), abs=0.002)     # Mitte waagerecht
+
+
+HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")
+
+
+def _dragged(rect: Rect, handle: str, amount: float) -> Rect:
+    """``rect`` nach Ziehen am Anfasser ``handle`` um ``amount`` mm nach außen."""
+    left, top, right, bottom = rect.x, rect.y, rect.right, rect.bottom
+    left -= amount if "l" in handle else 0
+    right += amount if "r" in handle else 0
+    top -= amount if "t" in handle else 0
+    bottom += amount if "b" in handle else 0
+    return Rect(left, top, right - left, bottom - top)
+
+
+@pytest.mark.parametrize("handle", HANDLES)
+def test_keep_aspect_fixes_what_the_handle_says(handle):
+    """Ecke: gegenüberliegende Ecke bleibt; Kante: gegenüberliegende Kante bleibt, quer dazu
+    die Mitte – unabhängig davon, welches Maß sich (in Rechenrauschen) mehr geändert hat."""
+    old = Rect(10, 20, 40, 20)
+    new = layout.keep_aspect(old, _dragged(old, handle, 4), handle)
+    assert new.w / new.h == pytest.approx(2)
+    assert new.w > old.w
+    for edge, opposite in (("l", "right"), ("r", "x"), ("t", "bottom"), ("b", "y")):
+        if edge in handle:
+            assert getattr(new, opposite) == pytest.approx(getattr(old, opposite))
+    if handle in ("t", "b"):
+        assert new.cx == pytest.approx(old.cx)
+    if handle in ("l", "r"):
+        assert new.cy == pytest.approx(old.cy)
+
+
+def test_keep_aspect_edge_ignores_noise_in_the_other_axis():
+    old = Rect(10, 20, 40, 20)
+    noisy = Rect(10, 20 - 1e-9, 40 + 1e-12, 26 + 1e-9)       # unten gezogen, quer nur Rauschen
+    new = layout.keep_aspect(old, noisy, "b")
+    assert (new.y, new.h, new.cx) == pytest.approx((20, 26, old.cx))
+
+
+@pytest.mark.parametrize("rotation", [0, 90])
+@pytest.mark.parametrize("handle", HANDLES)
+def test_resize_image_result_matches_preview(handle, rotation):
+    """Die Vorschau (``keep_aspect`` auf dem gezeigten Rahmen) ist das Ergebnis (±1 Punkt)."""
+    obj = _picture(x_mm=20, y_mm=12, rotation=rotation)
+    _, rendered = _frame(obj)
+    shown = layout.object_rect(rendered)
+    preview = layout.keep_aspect(shown, _dragged(shown, handle, 3.3), handle)
+    resized = layout.resize(obj, preview, rendered, handle)
+    after, _ = _frame(resized)
+    for a, b in zip((after.x, after.y, after.right, after.bottom),
+                    (preview.x, preview.y, preview.right, preview.bottom)):
+        assert a == pytest.approx(b, abs=DOT_MM * 1.01)
+
+
+@pytest.mark.parametrize("handle", ["br", "r"])
+def test_resize_image_without_keep_ratio_distorts(handle):
+    obj = _picture(keep_ratio=False)
+    rendered = _rendered(10, 5, 20, 10)
+    old = layout.object_rect(rendered)
+    resized = layout.resize(obj, Rect(old.x, old.y, old.w + 10, old.h), rendered, handle)
+    assert _model_frame(resized) == pytest.approx((10, 5, 30, 10), abs=0.002)
+
+
+@pytest.mark.parametrize("degrees, end", [(90, 90), (-90, 270)])
+def test_rotate_image_keeps_centre(degrees, end):
+    obj = _picture(x_mm=10, y_mm=10)
+    before, rendered = _frame(obj)
+    turned = layout.rotate(obj, rendered, degrees)
+    after, _ = _frame(turned)
+    assert turned.rotation == end and (turned.w_mm, turned.h_mm) == (20, 10)
+    assert (after.w, after.h) == pytest.approx((10, 20), abs=0.1)
+    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=0.1)
+
+
+def _text_and_image():
+    return [TextObject("Text", size_pt=12, x_mm=4, y_mm=4), _picture(x_mm=20, y_mm=12),
+            TextObject("Rahmen", size_pt=12, fit=True, x_mm=7, y_mm=25, w_mm=20, h_mm=6)]
+
+
+@pytest.mark.parametrize("mode, attr", [("left", "x"), ("right", "right"), ("vcenter", "cy")])
+def test_align_mixed_text_and_images(mode, attr):
+    objs = _text_and_image()
+    aligned = layout.align_objects(objs, _rendered_of(objs), mode)
+    rects = [layout.exact_rect(o, r) for o, r in zip(aligned, _rendered_of(aligned))]
+    assert len({round(getattr(r, attr), 1) for r in rects}) == 1
+    assert (aligned[1].w_mm, aligned[1].h_mm) == (20, 10)
+
+
+def test_match_size_image_to_text_keeps_image_ratio():
+    objs = [TextObject("Rahmen", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=30, h_mm=6),
+            _picture(x_mm=5, y_mm=20)]
+    rendered = _rendered_of(objs)
+    # Breite × 1,5, Höhe × 0,6; „gleiche Größe“: Mittel aus beiden Faktoren
+    for mode, width in (("width", 30), ("height", 12), ("same", 20 * (1.5 * 0.6) ** 0.5)):
+        _, image = layout.match_objects(objs, rendered, mode)
+        assert (image.x_mm, image.y_mm) == (5, 20)              # Ecke bleibt
+        assert (image.w_mm, image.h_mm) == pytest.approx((width, width / 2), abs=0.002)
+
+
+def test_match_size_image_without_keep_ratio_takes_frame():
+    objs = [TextObject("Rahmen", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=30, h_mm=6),
+            _picture(x_mm=5, y_mm=20, keep_ratio=False)]
+    _, image = layout.match_objects(objs, _rendered_of(objs), "same")
+    assert _model_frame(image) == (5, 20, 30, 6)
+
+
+def test_match_size_text_to_image_scales_text():
+    objs = [_picture(x_mm=1, y_mm=1, w_mm=40, h_mm=20),
+            TextObject("Wort", size_pt=10, x_mm=5, y_mm=30)]
+    ref, text = layout.match_objects(objs, _rendered_of(objs), "width")
+    assert ref is objs[0] and text.size_pt > 10 and not text.fit
+
+
+@pytest.mark.parametrize("keep_ratio", [True, False])
+def test_maximize_image_fills_area_centred(keep_ratio):
+    obj = _picture(keep_ratio=keep_ratio)
+    doc = Document("62", length_mm=40, objects=[obj])
+    area = layout.printable_area(doc)
+    big = layout.maximize_object(obj, render_object(obj, doc), area, doc)
+    assert big.w_mm / big.h_mm == pytest.approx(2)
+    assert big.w_mm == pytest.approx(area.w, abs=0.002)
+    assert (big.x_mm + big.w_mm / 2, big.y_mm + big.h_mm / 2) == \
+        pytest.approx((area.cx, area.cy), abs=0.002)
+
+
+def test_outside_counts_images():
+    doc = Document("62", length_mm=40, objects=[TextObject("A", size_pt=12, x_mm=2, y_mm=2),
+                                                _picture(x_mm=50, y_mm=5)])
+    assert layout.objects_outside(doc) == [1]
+
+
+def test_to_grid_rounds_image_frame():
+    obj = layout.to_grid(_picture(x_mm=1.234, w_mm=20.06), x=True, w=True)
+    assert (obj.x_mm, obj.w_mm) == (1.2, 20.1)
+
+
+def test_text_only_helpers_refuse_images():
+    obj = _picture()
+    rendered = _rendered(10, 5, 20, 10)
+    for call in (lambda: layout.scale_text(obj, 2), lambda: layout.fix_size(obj, 12),
+                 lambda: layout.anchor_after_edit(obj, rendered, rendered),
+                 lambda: layout.anchor_align(obj)):
+        with pytest.raises(TypeError, match="Text"):
+            call()
diff --git a/tests/test_renderer.py b/tests/test_renderer.py
index 24dec53..e7d8a35 100644
--- a/tests/test_renderer.py
+++ b/tests/test_renderer.py
@@ -5,7 +5,7 @@ import random
 import pytest
 
 from labelwerk import render
-from labelwerk.document import Document, Paragraph, Span, TextObject
+from labelwerk.document import Document, ImageObject, Paragraph, Span, TextObject
 from labelwerk.render import Rendered, Renderer, label_size, render_document, render_object
 
 
@@ -171,3 +171,111 @@ def test_random_documents_are_byte_identical_also_incrementally():
         result = renderer.render(doc, "QL-600")
         assert result.image.size == expected.size
         assert result.image.tobytes() == expected.tobytes()
+
+
+# --- Bilder -------------------------------------------------------------------------
+def _with_images() -> Document:
+    from PIL import Image
+    doc = _doc()
+    for x in (20, 40):
+        img = Image.new("RGB", (200, 100), (120, 120, 120))
+        doc.objects.append(ImageObject.from_image(img, 300, "grau.png"))
+        doc.objects[-1].x_mm, doc.objects[-1].y_mm = x, 25
+    return doc
+
+
+@pytest.fixture
+def finished(monkeypatch):
+    """Zählt das Zeichnen (``_finish``) je Objekt (Index in ``_with_images``)."""
+    seen = []
+    real = render._finish
+
+    def counting(prep, *args, **kwargs):
+        seen.append(prep.obj)
+        return real(prep, *args, **kwargs)
+    monkeypatch.setattr(render, "_finish", counting)
+    return seen
+
+
+def test_changing_threshold_redraws_only_that_image(finished):
+    renderer, doc = Renderer(), _with_images()
+    renderer.render(doc, "QL-600")
+    finished.clear()
+    doc.objects[3].threshold = 100
+    result = renderer.render(doc, "QL-600")
+    assert finished == [doc.objects[3]]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+@pytest.mark.parametrize("change", [
+    {"mode": "photo"}, {"invert": True}, {"keep_ratio": False}, {"rotation": 90},
+    {"crop": (0, 0, 50, 50)}, {"w_mm": 5.0}, {"x_mm": 1.0}, {"page": 2}, {"source": "neu.png"}])
+def test_every_image_setting_is_part_of_the_cache_key(finished, change):
+    renderer, doc = Renderer(), _with_images()
+    renderer.render(doc, "QL-600")
+    finished.clear()
+    for key, value in change.items():
+        setattr(doc.objects[2], key, value)
+    renderer.render(doc, "QL-600")
+    assert finished == [doc.objects[2]]
+
+
+def test_new_png_bytes_redraw_the_image(finished):
+    from PIL import Image
+    renderer, doc = Renderer(), _with_images()
+    renderer.render(doc, "QL-600")
+    finished.clear()
+    doc.objects[2].png = ImageObject.from_image(Image.new("RGB", (200, 100)), 300, "x").png
+    result = renderer.render(doc, "QL-600")
+    assert finished == [doc.objects[2]]
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_unchanged_images_render_nothing(finished):
+    renderer, doc = Renderer(), _with_images()
+    first = renderer.render(doc, "QL-600")
+    finished.clear()
+    assert renderer.render(doc, "QL-600").image is first.image
+    assert finished == []
+
+
+def test_threshold_change_does_not_decode_or_scale_again():
+    render._scaled_source.cache_clear()
+    doc = _with_images()
+    renderer = Renderer()
+    renderer.render(doc, "QL-600")
+    misses = render._scaled_source.cache_info().misses
+    doc.objects[2].threshold = 90
+    renderer.render(doc, "QL-600")
+    assert render._scaled_source.cache_info().misses == misses
+
+
+def test_random_changes_with_images_stay_byte_identical():
+    from PIL import Image
+    rng = random.Random(11)
+    source = Image.radial_gradient("L").convert("RGB").resize((120, 80))
+    renderer = Renderer()
+    doc = Document("62", length_mm=None)
+    for _ in range(40):
+        doc.orientation = rng.choice([doc.orientation] * 4 + ["vertical", "horizontal"])
+        action = rng.random()
+        if action < 0.3 or not doc.objects:
+            if rng.random() < 0.5:
+                obj = ImageObject.from_image(source, rng.choice([150, 300, 600]), "verlauf.png")
+                obj.x_mm, obj.y_mm = rng.uniform(0, 30), rng.uniform(0, 30)
+            else:
+                obj = TextObject("Ab", size_pt=10, x_mm=rng.uniform(0, 30), y_mm=5)
+            doc.objects.append(obj)
+        elif action < 0.8:
+            obj = rng.choice(doc.objects)
+            if isinstance(obj, ImageObject):
+                setattr(obj, *rng.choice([
+                    ("threshold", rng.randint(0, 255)), ("mode", rng.choice(["line", "photo"])),
+                    ("invert", rng.random() < 0.5), ("rotation", rng.choice([0, 90, 180, 270])),
+                    ("keep_ratio", rng.random() < 0.5), ("w_mm", rng.uniform(3, 20)),
+                    ("crop", rng.choice([None, (10, 10, 60, 40)]))]))
+            else:
+                obj.x_mm = rng.uniform(0, 30)
+        else:
+            del doc.objects[rng.randrange(len(doc.objects))]
+        assert renderer.render(doc, "QL-600").image.tobytes() == render_document(doc).tobytes()
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index d1c1677..a67a336 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -15,7 +15,7 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.
 - Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
 - Direkt auf dem Etikett schreiben (Etappe 3d-1b): Schreibmodus (Text anlegen + Klick bzw. Doppelklick, Esc/Klick daneben beendet), Schreibmarke/Markierung aus dem Kern-Zeilensatz, Markieren mit Maus und Tastatur, eine Bearbeitung = ein Rückgängig-Schritt, Rahmen wächst an der Kante der Textposition; Feld INHALT entfällt.
-- 1027 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- 1193 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -33,19 +33,29 @@ src/labelwerk/
               text_layout(obj, doc) -> TextLayout (derselbe Zeilensatz wie das Rendern, auch RenderedObject.layout):
               caret/hit/selection_rects/anchor in Druckpunkten relativ zum ungedrehten Rahmen, Positionen wie QTextDocument
               (in Codepunkten; to_utf16/from_utf16 rechnen in Qts UTF-16-Positionen um)
+              ImageObject: Ausschnitt → Rahmen in Druckpunkten (Lanczos, keep_ratio eingepasst) → imaging.to_layers → gedreht;
+              decodiert/skaliert gecacht (_source/_scaled_source, Schlüssel PNG-Bytes + Ausschnitt + Größe)
   fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei
   files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
               crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
+              load_image(path, page) -> (RGB-Bild, dpi) für Bild-Objekte (PNG/JPG/GIF/BMP/WebP/PDF, Transparenz → weiß, EXIF-Lage);
+              crop_box(img, dpi, ink) -> (l, t, r, b) | None, dieselbe Logik wie crop() (Bilder: ink=NOT_WHITE)
+  imaging.py  Bilder ohne Qt: to_layers(img, mode line|photo, threshold, invert) -> {"black": Bild "1"} (später "red" für QL-8xx),
+              on_white, to_8bit (16-Bit-Graustufen skalieren), limit_size (höchstens 600 dpi bzw. 6000 px längste Seite,
+              Druckgröße bleibt); Foto: Gammakurve photo_curve (Weiß/Schwarz fest), dann Floyd-Steinberg
   printer.py  build_instructions(image, label_id, model) -> bytes (Brother-Raster)
               print_image(...) -> status-dict von brother_ql.backends.helpers.send
   detect.py   find_brother_lp() -> "file:///dev/usb/lpN" | None
   document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit);
               TextObject: Position x_mm/y_mm (None = mittig wie bisher), Rahmen w_mm/h_mm (mit fit), Drehen rotation 0/90/180/270
+              ImageObject: png (Farboriginal), source/page/crop, Rahmen x/y/w/h_mm immer gesetzt, rotation, mode/threshold/invert,
+              keep_ratio; from_image(img, dpi, source, page, crop) setzt 1:1-Größe
   settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic)
   media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
   layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
               growing_axis (Endlosband wächst mit), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
               Schreibmodus: to_object/from_object (Etikett ↔ ungedrehtes Objekt, Druckpunkte), anchor_after_edit/anchor_align
+              Bilder wie Text mit fester Rahmengröße; keep_aspect (Anfasser mit keep_ratio); Schrift-Funktionen: TypeError bei Bildern
   shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
               without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
   desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
diff --git a/docs/superpowers/specs/2026-10-17-bild-objekt-design.md b/docs/superpowers/specs/2026-10-17-bild-objekt-design.md
index 026c591..c636d62 100644
--- a/docs/superpowers/specs/2026-10-17-bild-objekt-design.md
+++ b/docs/superpowers/specs/2026-10-17-bild-objekt-design.md
@@ -29,12 +29,12 @@ Bildschirmfoto und Symbole (2b/2c), Bildbearbeitung (Freistellen, Retusche), Zus
   - `mode: "line" | "photo"` (Standard „line“), `threshold: int` 0–255 (Standard 128), `invert: bool`,
   - `keep_ratio: bool = True`.
   - `is_empty()` → False. `Document.objects: list[TextObject | ImageObject]`.
-- **Laden** (`files.py`, Qt-frei): `load_image(path, page=1) -> (Image RGB, dpi)` für PNG/JPG/GIF(erstes Bild)/BMP/WebP/PDF; Transparenz auf Weiß. **SVG** rastert die GUI (QSvgRenderer, 300 dpi aus viewBox/Größe; 1 px = 1/96 in) und reicht PNG-Bytes weiter – der Kern bleibt Qt-frei. Sehr große Bilder werden beim Einfügen auf höchstens 600 dpi bezogen auf ihre Druckgröße bzw. 6000 px längste Seite verkleinert (Speicher).
-- **Automatischer Zuschnitt** beim Einfügen: `files.crop_box(img) -> (l, t, r, b)` (dieselbe Logik wie `crop()` – Schnittmarken, Leerraum; `crop()` nutzt sie), Ergebnis in `ImageObject.crop`. Panel-Schalter „Zuschnitt“ (an/aus = automatisch/ganzes Original).
+- **Laden** (`files.py`, Qt-frei): `load_image(path, page=1) -> (Image RGB, dpi)` für PNG/JPG/GIF(erstes Bild)/BMP/WebP/PDF; Transparenz auf Weiß; 16-Bit-Graustufen werden auf 8 Bit skaliert (nicht abgeschnitten); DPI aus der Datei auf 0,01 gerundet, quer verschiedene DPI (Fax 204 × 98) → Höhe skaliert, Druckgröße stimmt. **SVG** rastert die GUI (QSvgRenderer, 300 dpi aus viewBox/Größe; 1 px = 1/96 in) und reicht PNG-Bytes weiter – der Kern bleibt Qt-frei. Sehr große Bilder werden beim Einfügen auf höchstens 600 dpi bezogen auf ihre Druckgröße bzw. 6000 px längste Seite verkleinert (Speicher).
+- **Automatischer Zuschnitt** beim Einfügen: `files.crop_box(img, dpi, ink) -> (l, t, r, b) | None` (dieselbe Logik wie `crop()` – Schnittmarken, Leerraum; `crop()` nutzt sie mit `ink=128` unverändert). Bilder: Transparenz zuerst auf Weiß, Inhalt ist alles „nicht weiß“ (`ink=NOT_WHITE` = 245), damit helle Fotos und gelbe Logos ganz bleiben; ohne Inhalt `None` → ganzes Bild. Ergebnis in `ImageObject.crop`. Panel-Schalter „Zuschnitt“ (an/aus = automatisch/ganzes Original).
 - **Größe beim Einfügen:** 1:1 aus der DPI-Angabe (ohne Angabe 300 dpi; PDF in Originalgröße). Passt das Bild nicht in den bedruckbaren Bereich, wird es proportional eingepasst (Hinweis in der Statusleiste „Bild auf N % verkleinert – Codes ggf. nicht mehr lesbar“). Position: Klick-/Ablagepunkt bzw. Mitte des bedruckbaren Bereichs.
-- **Umrechnung** (`imaging.py`, neu, Qt-frei): `to_layers(img, mode, threshold, invert) -> dict[str, Image "1"]` mit Ebene `"black"`; `mode="line"`: Graustufe → harte Schwelle; `"photo"`: Helligkeit um `threshold-128` verschoben, dann Floyd-Steinberg. Schnittstelle für später `"red"` (Zweifarbdruck QL-8xx) dokumentiert, aber nicht gebaut.
-- **Rendern:** `render_object` kennt `ImageObject`: Ausschnitt → auf Rahmengröße in Druckpunkten skalieren (Lanczos; bei `keep_ratio` kein Verzerren – Rahmen hat das Seitenverhältnis) → `to_layers` → Ebene „black“ als Objektbild (Tinte schwarz) → drehen wie Text. Ergebnis gecacht (Renderer). `RenderedObject.layout` = None.
-- **Platzier-Logik:** `layout` behandelt `ImageObject` wie Text mit fester Rahmengröße (move/resize/set_frame/rotate/align/match_size/maximize); Ecken skalieren proportional bei `keep_ratio`, Kanten verzerren nur ohne `keep_ratio` (mit `keep_ratio` wirken Kanten wie Ecken in einer Achse und halten das Verhältnis).
+- **Umrechnung** (`imaging.py`, neu, Qt-frei): `to_layers(img, mode, threshold, invert) -> dict[str, Image "1"]` mit Ebene `"black"`; `mode="line"`: Graustufe → harte Schwelle; `"photo"`: Gammakurve `v' = 255 · (v/255) ** g` mit `g = 2 ** ((threshold − 128) / 64)` (höhere Schwelle → dunkler, 128 = unverändert; 0 und 255 bleiben fest – weißes Papier bekommt nie Punkte, Schwarz bleibt voll), dann Floyd-Steinberg. Schnittstelle für später `"red"` (Zweifarbdruck QL-8xx) dokumentiert, aber nicht gebaut.
+- **Rendern:** `render_object` kennt `ImageObject`: Ausschnitt → auf Rahmengröße in Druckpunkten skalieren (Lanczos mit `reducing_gap=2`: stark verkleinert erst ganzzahlig reduzieren – 1:1, vergrößert und bis 2× verkleinert unverändert exakt; bei `keep_ratio` kein Verzerren – Rahmen hat das Seitenverhältnis) → `to_layers` → Ebene „black“ als Objektbild (Tinte schwarz) → drehen wie Text. Ergebnis gecacht (Renderer). `RenderedObject.layout` = None.
+- **Platzier-Logik:** `layout` behandelt `ImageObject` wie Text mit fester Rahmengröße (move/resize/set_frame/rotate/align/match_size/maximize); Ecken skalieren proportional bei `keep_ratio`, Kanten verzerren nur ohne `keep_ratio` (mit `keep_ratio` wirken Kanten wie Ecken in einer Achse und halten das Verhältnis). Was fest bleibt, folgt allein aus dem Anfasser (`keep_aspect(old, new, handle)`, Vorschau und Ergebnis gleich): Ecke → gegenüberliegende Ecke, Kante → gegenüberliegende Kante, quer dazu die Mitte.
 
 ## 2 – GUI
 
@@ -53,6 +53,6 @@ Bildschirmfoto und Symbole (2b/2c), Bildbearbeitung (Freistellen, Retusche), Zus
 ## Tests
 
 - **Umbau:** Renderer-Tests ohne Qt (nur Geändertes neu, Etikettgröße als Schlüssel bei Objekten ohne Position, Druckbild byte-gleich zu vorher); bestehende GUI-Tests unverändert grün.
-- **Kern:** `load_image` je Format (aus Pillow erzeugte Testdateien, PDF via Pillow), Transparenz → Weiß, DPI → Größe; `crop_box` = bisheriges `crop()`; `to_layers` Strich/Foto/Schwelle/Umkehren; `render_object` für Bilder: Größe, Drehung, `keep_ratio`, Ecken-/Kanten-Skalierung, Vorschau = Druck; Layout-Funktionen mit gemischten Text/Bild-Auswahlen; große Bilder werden begrenzt.
+- **Kern:** `load_image` je Format (aus Pillow erzeugte Testdateien, PDF via Pillow), Transparenz → Weiß, DPI → Größe; `crop_box` = bisheriges `crop()` (Standard-`ink`), „nicht weiß“ für Bilder, `None` ohne Inhalt; 16-Bit-Graustufen; `to_layers` Strich/Foto/Schwelle/Umkehren (Foto: Weiß/Schwarz bleiben bei jeder Schwelle); `render_object` für Bilder: Größe, Drehung, `keep_ratio`, Ecken-/Kanten-Skalierung, Vorschau = Druck; Layout-Funktionen mit gemischten Text/Bild-Auswahlen; große Bilder werden begrenzt.
 - **GUI (offscreen):** Bild aus Datei (Dialog gepatcht) erscheint 1:1 in der Mitte, zu großes Bild wird eingepasst + Hinweis; Strg+V mit Bild in der Zwischenablage; Strg+V nach internem Kopieren fügt Objekte ein; Strg+V mit Text → Textrahmen; Ablegen einer Datei; Panel-Einstellungen ändern das Druckbild; Auswahl eines Bildes zeigt BILD-Panel; Rückgängig je Aktion; Layout „gleiche Größe“ Text+Bild; Doppelklick auf Bild startet keinen Schreibmodus; SVG wird gerastert.
 - Keine echten Briefmarken/Adressen im Repo; Testbilder werden im Test erzeugt.
diff --git a/src/labelwerk/document.py b/src/labelwerk/document.py
index 9c95419..042a140 100644
--- a/src/labelwerk/document.py
+++ b/src/labelwerk/document.py
@@ -1,8 +1,13 @@
 """Etikett-Dokument: Etikett und Liste von Objekten (UI-unabhängig, JSON-tauglich)."""
 from __future__ import annotations
 
+import io
 from dataclasses import dataclass, field
 
+from PIL import Image
+
+from .imaging import limit_size, on_white
+
 ORIENTATIONS = ("vertical", "horizontal")
 ALIGNMENTS = ("left", "center", "right", "justify")
 ROTATIONS = (0, 90, 180, 270)      # Grad im Uhrzeigersinn
@@ -78,13 +83,72 @@ class TextObject:
         return not self.text.strip()
 
 
+@dataclass(kw_only=True)
+class ImageObject:
+    """Bild auf dem Etikett; Schwarz/Weiß erst beim Rendern (``imaging.to_layers``).
+
+    Anlegen meist mit ``ImageObject.from_image``. Der Rahmen ist immer gesetzt – wie bei
+    Text mit fester Rahmengröße: ``x_mm``/``y_mm`` linke obere Ecke auf dem Etikett (nach
+    dem Drehen), ``w_mm``/``h_mm`` Größe vor dem Drehen.
+    """
+    png: bytes = field(repr=False)  # Original in Farbe (auf Weiß), verlustfrei als PNG
+    source: str = ""                # Dateiname oder „Zwischenablage“
+    page: int | None = None         # PDF-Seite
+    crop: tuple[int, int, int, int] | None = None   # Ausschnitt (l, t, r, b) in Pixeln; None = ganz
+    x_mm: float = 0.0
+    y_mm: float = 0.0
+    w_mm: float
+    h_mm: float
+    rotation: int = 0               # 0 | 90 | 180 | 270
+    mode: str = "line"              # line (Strich, harte Schwelle) | photo (Foto, gerastert)
+    threshold: int = 128            # 0–255; höher = mehr Tinte
+    invert: bool = False
+    keep_ratio: bool = True         # Seitenverhältnis beibehalten (Ecken/Kanten skalieren gleich)
+
+    def __post_init__(self) -> None:
+        if self.crop is not None:                # JSON liefert eine Liste
+            self.crop = tuple(int(v) for v in self.crop)
+
+    @property
+    def positioned(self) -> bool:
+        """Ein Bild hat immer eine Position (anders als Text, der mittig stehen kann)."""
+        return True
+
+    def is_empty(self) -> bool:
+        return False
+
+    @classmethod
+    def from_image(cls, img: Image.Image, dpi: float, source: str, page: int | None = None,
+                   crop: tuple[int, int, int, int] | None = None) -> "ImageObject":
+        """Bild 1:1 nach ``dpi`` (Größe des Ausschnitts ``crop``, sonst des ganzen Bilds).
+
+        Transparenz wird weiß; sehr große Bilder werden begrenzt (``imaging.limit_size``) –
+        der Ausschnitt rechnet mit, die Druckgröße bleibt.
+        """
+        l, t, r, b = crop if crop is not None else (0, 0, *img.size)
+        mm = 25.4 / dpi                          # Druckgröße aus dem Original
+        rgb, _ = limit_size(on_white(img), dpi)
+        if crop is not None and rgb.size != img.size:
+            fx, fy = rgb.width / img.width, rgb.height / img.height
+            crop = (round(l * fx), round(t * fy), round(r * fx), round(b * fy))
+        buffer = io.BytesIO()
+        rgb.save(buffer, "PNG", compress_level=1)   # große Fotos rund 4× schneller
+        return cls(png=buffer.getvalue(), source=source, page=page, crop=crop,
+                   w_mm=(r - l) * mm, h_mm=(b - t) * mm)
+
+    def image(self) -> Image.Image:
+        """Das Original als RGB-Bild."""
+        with Image.open(io.BytesIO(self.png)) as img:
+            return img.convert("RGB")
+
+
 @dataclass
 class Document:
     label_id: str = "62"
     length_mm: float | None = None    # nur Endlosband; None = automatisch
     orientation: str = "vertical"     # "vertical" (Text quer zum Band) | "horizontal" (längs)
     margin_mm: float = 1.0            # Rand in Bandlaufrichtung (vorne/hinten)
-    objects: list[TextObject] = field(default_factory=list)
+    objects: list[TextObject | ImageObject] = field(default_factory=list)
 
     def is_empty(self) -> bool:
         """True, wenn kein Objekt sichtbaren Inhalt hat."""
diff --git a/src/labelwerk/files.py b/src/labelwerk/files.py
index 37f0450..6dbfbb3 100644
--- a/src/labelwerk/files.py
+++ b/src/labelwerk/files.py
@@ -1,45 +1,132 @@
-"""Lädt fertige Dateien (PDF, PNG, JPG) und bringt sie 1:1 aufs Etikett."""
+"""Lädt fertige Dateien (PDF, PNG, JPG) und bringt sie 1:1 aufs Etikett; lädt Bilder für
+Bild-Objekte (``load_image``)."""
 from __future__ import annotations
 
+import struct
+import zlib
+from contextlib import contextmanager
 from pathlib import Path
 
 from PIL import Image, ImageOps
 
+from .imaging import MAX_PIXELS, limit_size, on_white, to_8bit
 from .labels import DPI, format_mm, get_label, length_limits
 from .render import MARGIN
 
 _IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
+# Bild-Objekte: zusätzlich GIF (erstes Bild), BMP, WebP; SVG rastert die Oberfläche
+_OBJECT_SUFFIXES = (*_IMAGE_SUFFIXES, ".gif", ".bmp", ".webp")
 
 INK = 128            # dunkler gilt als bedruckt
+NOT_WHITE = 245      # Bild-Objekte: alles, was nicht (fast) weiß ist, gehört zum Inhalt
+_PDFIUM_PASSWORD = 4   # FPDF_ERR_PASSWORD
 MM = DPI / 25.4      # Punkte pro mm
 
 
 def load_file(path: str | Path, page: int = 1) -> Image.Image:
     """Datei als Graustufenbild bei 300 dpi (Größe in mm bleibt erhalten)."""
+    path = _checked(path, _IMAGE_SUFFIXES, "PDF, PNG, JPG", page)
+    with _readable(path):
+        return _load_pdf(path, page) if path.suffix.lower() == ".pdf" else _load_image(path)
+
+
+def load_image(path: str | Path, page: int = 1) -> tuple[Image.Image, float]:
+    """Bild für ein Bild-Objekt: (RGB-Bild in Originalauflösung, dpi).
+
+    PNG, JPG, GIF (erstes Bild), BMP, WebP und PDF (Seite ``page``, gerendert bei 300 dpi).
+    Transparenz wird weiß, die EXIF-Lage (Handyfotos) wird angewandt; ohne DPI-Angabe
+    gelten 300 dpi (auf 0,01 gerundet: PNG speichert Punkte je Meter). Ist die Auflösung
+    hoch und quer verschieden (Fax: 204 × 98 dpi), wird die Höhe passend skaliert – die
+    Druckgröße stimmt, ``dpi`` ist die waagrechte. Sehr große Bilder werden begrenzt
+    (``imaging.limit_size``: höchstens 600 dpi bzw. 6000 px längste Seite) – PDF-Seiten
+    werden gleich passend gerendert.
+    """
+    path = _checked(path, _OBJECT_SUFFIXES, "PNG, JPG, GIF, BMP, WebP, PDF", page)
+    with _readable(path):
+        if path.suffix.lower() == ".pdf":
+            return _load_pdf_page(path, page)
+        with Image.open(path) as src:                  # GIF: erstes Bild
+            x_dpi, y_dpi = _file_dpi(src)
+            if src.getexif().get(0x0112, 1) in (5, 6, 7, 8):   # EXIF dreht um 90°
+                x_dpi, y_dpi = y_dpi, x_dpi
+            img = on_white(ImageOps.exif_transpose(src))   # Handyfotos: Lage aus EXIF
+        return limit_size(img, x_dpi, x_dpi / y_dpi)    # Höhe passend, Grenzen vor dem Strecken
+
+
+def _file_dpi(src: Image.Image) -> tuple[float, float]:
+    """Auflösung (waagrecht, senkrecht) aus der Datei, auf 0,01 gerundet; fehlt sie oder
+    ist sie 0, gelten 300 dpi."""
+    dpi = src.info.get("dpi", (DPI, DPI))
+    return tuple(round(float(v), 2) or float(DPI) for v in dpi[:2])
+
+
+def _checked(path: str | Path, suffixes: tuple[str, ...], allowed: str, page: int) -> Path:
+    """Dateityp, Vorhandensein und Seitenzahl prüfen."""
     path = Path(path)
     suffix = path.suffix.lower()
-    if suffix != ".pdf" and suffix not in _IMAGE_SUFFIXES:
-        raise ValueError(f"Dateityp nicht unterstützt: {suffix or path.name} – möglich: PDF, PNG, JPG")
+    if suffix != ".pdf" and suffix not in suffixes:
+        raise ValueError(f"Dateityp nicht unterstützt: {suffix or path.name} – möglich: {allowed}")
     if not path.exists():
         raise FileNotFoundError(f"Datei nicht gefunden: {path}")
     if suffix == ".pdf" and page < 1:
         raise ValueError("Seite muss mindestens 1 sein.")
+    return path
+
+
+@contextmanager
+def _readable(path: Path):
+    """Lesefehler als verständliche deutsche Meldung (``ValueError``, fehlende Datei
+    ``FileNotFoundError``) – ohne englischen Text aus Betriebssystem, Pillow oder PDFium."""
     try:
-        return _load_pdf(path, page) if suffix == ".pdf" else _load_image(path)
+        yield
     except FileNotFoundError:
-        raise
-    except (OSError, RuntimeError, Image.DecompressionBombError) as e:
-        raise ValueError(f"Datei kann nicht gelesen werden: {path.name} ({e})") from e
+        raise FileNotFoundError(f"Datei nicht gefunden: {path}") from None
+    except (OSError, RuntimeError, SyntaxError, struct.error, zlib.error,
+            Image.DecompressionBombError) as e:
+        raise ValueError(f"Datei kann nicht gelesen werden: {path.name} ({_reason(e)})") from e
+
+
+def _reason(error: Exception) -> str:
+    """Grund eines Lesefehlers auf Deutsch."""
+    if isinstance(error, IsADirectoryError):
+        return "ist ein Ordner"
+    if isinstance(error, PermissionError):
+        return "keine Leserechte"
+    if isinstance(error, Image.DecompressionBombError):
+        return "Bild hat zu viele Pixel"
+    if isinstance(error, Image.UnidentifiedImageError):
+        return "kein lesbares Bild"
+    if isinstance(error, RuntimeError):            # PDFium (pypdfium2.PdfiumError)
+        if getattr(error, "err_code", None) == _PDFIUM_PASSWORD:
+            return "PDF ist verschlüsselt"
+        return "keine gültige PDF-Datei"
+    if (isinstance(error, (SyntaxError, struct.error, zlib.error))
+            or any(word in str(error) for word in ("truncated", "broken", "corrupt"))):
+        return "Datei ist beschädigt oder unvollständig"
+    return "Lesefehler"
 
 
 def _load_pdf(path: Path, page: int) -> Image.Image:
+    with _pdf_page(path, page) as pdf_page:
+        return pdf_page.render(scale=DPI / 72).to_pil().convert("L")
+
+
+def _load_pdf_page(path: Path, page: int) -> tuple[Image.Image, float]:
+    """PDF-Seite in Farbe bei 300 dpi – bei sehr großen Seiten gröber (``MAX_PIXELS``)."""
+    with _pdf_page(path, page) as pdf_page:
+        dpi = min(DPI, MAX_PIXELS * 72 / max(pdf_page.get_size()))
+        return pdf_page.render(scale=dpi / 72).to_pil().convert("RGB"), dpi
+
+
+@contextmanager
+def _pdf_page(path: Path, page: int):
     import pypdfium2 as pdfium
 
     pdf = pdfium.PdfDocument(path)
     try:
         if not 1 <= page <= len(pdf):
             raise ValueError(f"PDF hat nur {len(pdf)} Seite(n).")
-        return pdf[page - 1].render(scale=DPI / 72).to_pil().convert("L")
+        yield pdf[page - 1]
     finally:
         pdf.close()
 
@@ -47,7 +134,7 @@ def _load_pdf(path: Path, page: int) -> Image.Image:
 def _load_image(path: Path) -> Image.Image:
     with Image.open(path) as src:
         dpi = float(src.info.get("dpi", (DPI, DPI))[0]) or DPI
-        img = src.convert("RGBA")
+        img = to_8bit(src).convert("RGBA")             # 16-Bit-Graustufen skalieren
     img = Image.alpha_composite(Image.new("RGBA", img.size, "white"), img).convert("L")
     if round(dpi) != DPI:
         f = DPI / dpi
@@ -58,17 +145,40 @@ def _load_image(path: Path) -> Image.Image:
 
 def crop(img: Image.Image) -> Image.Image:
     """Auf den Inhalt zuschneiden; liegen vier Eck-Schnittmarken außen, ohne die Marken."""
-    ink = img.point(lambda v: 255 if v < INK else 0)
+    return img.crop(_content_box(img, DPI, INK))
+
+
+def crop_box(img: Image.Image, dpi: float = DPI,
+             ink: int = INK) -> tuple[int, int, int, int] | None:
+    """Ausschnitt (l, t, r, b) mit dem Inhalt; liegen vier Eck-Schnittmarken außen, ohne die
+    Marken und den Leerraum dazwischen – None, wenn das Bild keinen Inhalt hat.
+
+    Inhalt ist, was dunkler als ``ink`` ist (Standard wie ``crop()``; Bild-Objekte nehmen
+    ``NOT_WHITE``, damit helle Fotos und gelbe Logos nicht abgeschnitten werden). Bilder in
+    Farbe zählen nach ihrer Helligkeit, Transparenz zuerst auf Weiß; ``dpi``: Auflösung des
+    Bilds (Maße der Marken in mm).
+    """
+    try:
+        return _content_box(img, dpi, ink)
+    except ValueError:
+        return None
+
+
+def _content_box(img: Image.Image, dpi: float, level: int) -> tuple[int, int, int, int]:
+    """``crop_box``, ohne Inhalt aber ``ValueError`` mit Meldung (für ``crop()``)."""
+    gray = img if img.mode == "L" else on_white(img).convert("L")
+    ink = gray.point(lambda v: 255 if v < level else 0)
     box = ink.getbbox()
     if box is None:
         raise ValueError("Datei enthält keinen druckbaren Inhalt.")
     content = ink.crop(box)
-    tl = _corner_mark(content)
-    tr = _corner_mark(ImageOps.mirror(content))
-    bl = _corner_mark(ImageOps.flip(content))
-    br = _corner_mark(content.rotate(180))
+    mm = dpi / 25.4
+    tl = _corner_mark(content, mm)
+    tr = _corner_mark(ImageOps.mirror(content), mm)
+    bl = _corner_mark(ImageOps.flip(content), mm)
+    br = _corner_mark(content.rotate(180), mm)
     if None in (tl, tr, bl, br):
-        return img.crop(box)
+        return box
     w, h = content.size
     left, top = max(tl[0], bl[0]), max(tl[1], tr[1])
     right, bottom = w - max(tr[0], br[0]), h - max(bl[1], br[1])
@@ -76,17 +186,18 @@ def crop(img: Image.Image) -> Image.Image:
     trimmed = ink.crop(inner).getbbox()  # Leerraum innerhalb der Marken entfernen
     if trimmed is None:
         raise ValueError("Zwischen den Schnittmarken ist kein druckbarer Inhalt.")
-    return img.crop((inner[0] + trimmed[0], inner[1] + trimmed[1],
-                     inner[0] + trimmed[2], inner[1] + trimmed[3]))
+    return (inner[0] + trimmed[0], inner[1] + trimmed[1],
+            inner[0] + trimmed[2], inner[1] + trimmed[3])
 
 
-def _corner_mark(ink: Image.Image) -> tuple[int, int] | None:
+def _corner_mark(ink: Image.Image, mm: float = MM) -> tuple[int, int] | None:
     """Innenkante (x, y) eines Schnittmarken-Kreuzes in der Ecke oben links, sonst None.
 
     Linien müssen am Rand des Inhalts beginnen, auf den ersten 3 mm zu 40 % dunkel
     (auch gepunktet) und höchstens 1 mm dick sein – so gilt Text oder ein Logo nicht als Marke.
+    ``mm``: Pixel je mm.
     """
-    span, window = round(3 * MM), round(10 * MM)
+    span, window = round(3 * mm), round(10 * mm)
     w, h = ink.size
     px = ink.load()
     need = 0.4 * span
@@ -94,7 +205,7 @@ def _corner_mark(ink: Image.Image) -> tuple[int, int] | None:
             if sum(px[x, y] > 0 for x in range(min(span, w))) >= need]
     cols = [x for x in range(min(window, w))
             if sum(px[x, y] > 0 for y in range(min(span, h))) >= need]
-    if not rows or not cols or rows[-1] - rows[0] > MM or cols[-1] - cols[0] > MM:
+    if not rows or not cols or rows[-1] - rows[0] > mm or cols[-1] - cols[0] > mm:
         return None
     return cols[-1] + 2, rows[-1] + 2
 
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 243eec1..d017d29 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -544,8 +544,7 @@ class MainWindow(QMainWindow):
         if not self._valid(index):
             return
         self._commit()
-        resized = resize(self.doc.objects[index], rect, self.rendered[index],
-                         corner=len(handle) == 2)
+        resized = resize(self.doc.objects[index], rect, self.rendered[index], handle)
         # nur die gezogenen Kanten auf 0,1 mm (wie die Felder) – die anderen bleiben genau
         self.doc.objects[index] = to_grid(resized, x="l" in handle, y="t" in handle,
                                           w="l" in handle or "r" in handle,
diff --git a/src/labelwerk/imaging.py b/src/labelwerk/imaging.py
new file mode 100644
index 0000000..e093f90
--- /dev/null
+++ b/src/labelwerk/imaging.py
@@ -0,0 +1,94 @@
+"""Bilder für den Druck aufbereiten (ohne Qt): auf Weiß legen, Größe begrenzen, in
+Druckebenen umwandeln.
+
+Druckebenen (``to_layers``) sind Bilder im Modus „1“ wie gedruckt: schwarz (0) = Tinte,
+weiß (255) = Papier. Heute gibt es nur die Ebene ``"black"``. Für den Zweifarbdruck der
+QL-8xx kommt später eine Ebene ``"red"`` hinzu – aus dem Farbbild (rote Töne → rot, der
+Rest → schwarz); der Druck setzt dann beide Ebenen zusammen (brother_ql ``red=True``).
+Deshalb bleibt das Original in Farbe, bis ``to_layers`` es umwandelt.
+"""
+from __future__ import annotations
+
+from PIL import Image, ImageChops
+
+MODES = ("line", "photo")      # Strich (harte Schwelle) | Foto (Rasterpunkte)
+MAX_DPI = 600                  # feiner druckt der QL nicht (300 dpi) – mehr kostet nur Speicher
+MAX_PIXELS = 6000              # längste Seite in Pixeln (Speicher; bei 300 dpi gut 50 cm)
+
+
+_GRAY_16 = ("I", "I;16", "I;16B", "I;16L", "I;16N")   # Graustufen mit 16 Bit (PNG, TIFF)
+
+
+def to_8bit(img: Image.Image) -> Image.Image:
+    """Graustufen mit 16 Bit auf 8 Bit skalieren (0–65535 → 0–255); Pillow würde beim
+    Umwandeln abschneiden – das Bild käme fast weiß an. Andere Bilder unverändert."""
+    if img.mode in _GRAY_16:
+        return img.convert("I").point(lambda v: v / 257).convert("L")
+    return img
+
+
+def on_white(img: Image.Image) -> Image.Image:
+    """Bild als RGB; Transparenz (Alphakanal, transparente Palettenfarbe) wird weiß."""
+    img = to_8bit(img)
+    if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info:
+        rgba = img.convert("RGBA")
+        return Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba).convert("RGB")
+    if img.mode == "F":                       # Fließkomma-Graustufen
+        img = img.convert("L")
+    return img.convert("RGB")
+
+
+def limit_size(img: Image.Image, dpi: float,
+               stretch: float = 1.0) -> tuple[Image.Image, float]:
+    """Sehr große Bilder verkleinern: höchstens ``MAX_DPI`` bezogen auf die Druckgröße und
+    höchstens ``MAX_PIXELS`` auf der längsten Seite. Die Druckgröße bleibt (die Auflösung
+    sinkt mit); ein Bild in Grenzen kommt unverändert zurück. ``stretch``: Faktor für die
+    Höhe (ungleiche Auflösung) – gerechnet wird mit der gestreckten Größe, in einem
+    Schritt vom Original aus (kein Hochskalieren vorab); auch bei ``factor`` 1 wird dann
+    gestreckt."""
+    height = max(1, round(img.height * stretch))
+    factor = min(1.0, MAX_DPI / dpi, MAX_PIXELS / max(img.width, height))
+    if factor >= 1.0 and height == img.height:
+        return img, dpi
+    size = (max(1, round(img.width * factor)), max(1, round(height * factor)))
+    return img.resize(size, Image.Resampling.LANCZOS, reducing_gap=3.0), dpi * factor
+
+
+def check(mode: str, threshold: int) -> None:
+    """Umwandlung und Schwelle prüfen; ``ValueError`` mit verständlicher Meldung."""
+    if mode not in MODES:
+        raise ValueError(f"Unbekannte Umwandlung {mode!r} – erlaubt: Strich, Foto (line, photo)")
+    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 255:
+        raise ValueError(f"Schwelle muss eine ganze Zahl von 0 bis 255 sein, nicht {threshold!r}.")
+
+
+def photo_curve(threshold: int) -> list[int]:
+    """Helligkeitskurve für ``"photo"`` (Tabelle 0–255): ``v' = 255 · (v / 255) ** g`` mit
+    ``g = 2 ** ((threshold − 128) / 64)`` – höhere Schwelle → dunkler, 128 = unverändert;
+    0 und 255 bleiben fest (Papier bleibt weiß, Schwarz bleibt voll)."""
+    gamma = 2 ** ((threshold - 128) / 64)
+    return [round(255 * (v / 255) ** gamma) for v in range(256)]
+
+
+def to_layers(img: Image.Image, mode: str, threshold: int,
+              invert: bool) -> dict[str, Image.Image]:
+    """Bild in Druckebenen umwandeln (siehe Modulbeschreibung), gleiche Größe wie ``img``.
+
+    ``"line"``: Graustufe, dunkler als ``threshold`` wird Tinte (harte Schwelle – Codes,
+    Schrift, Logos). ``"photo"``: Gammakurve (``photo_curve``: 128 = unverändert, Weiß und
+    Schwarz bleiben), dann Floyd-Steinberg-Rasterung (Fotos, Verläufe) – weißes Papier
+    bekommt nie Punkte. Beide Male gilt: höhere Schwelle → mehr Tinte. ``invert`` tauscht
+    zuletzt Tinte und Papier.
+    """
+    check(mode, threshold)
+    gray = img.convert("L")
+    if mode == "line":
+        black = gray.point([0 if v < threshold else 255 for v in range(256)])
+        black = black.convert("1", dither=Image.Dither.NONE)
+    else:
+        if threshold != 128:
+            gray = gray.point(photo_curve(threshold))
+        black = gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
+    if invert:
+        black = ImageChops.invert(black)
+    return {"black": black}
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index b789bc6..c13576d 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -4,13 +4,16 @@ Alle Rechtecke in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts
 (wie ``TextObject.x_mm``/``y_mm``). Die GUI rechnet nur in Bildschirmkoordinaten um.
 Ausnahme Schreibmodus (``to_object``/``from_object``): Punkte in Druckpunkten wie
 ``RenderedObject`` und ``TextLayout`` – so rechnet die Arbeitsfläche ohne Umweg über mm.
+
+Bild-Objekte verhalten sich wie Text mit fester Rahmengröße (``_framed``); Funktionen nur
+für Schrift (``scale_text``, ``fix_size``, Schreibmodus) weisen sie mit ``TypeError`` ab.
 """
 from __future__ import annotations
 
 import copy
 from dataclasses import dataclass, field, replace
 
-from .document import MAX_PT, MIN_PT, ROTATIONS, Document, TextObject
+from .document import MAX_PT, MIN_PT, ROTATIONS, Document, ImageObject, TextObject
 from .labels import DPI, get_label
 from .render import (PT, REF_PT, RenderedObject, span_dots, label_margins, label_size,
                      render_object)
@@ -198,11 +201,30 @@ def maximize(rect: Rect, area: Rect, grow: str | None = None) -> Rect:
 
 
 # --- Objekte ----------------------------------------------------------------------
-def place(obj: TextObject, rect: Rect) -> TextObject:
-    """Kopie von ``obj`` an ``rect``; bei fester Rahmengröße auch Breite/Höhe (ungedreht)."""
+Object = TextObject | ImageObject
+
+
+def _framed(obj: Object) -> bool:
+    """Fester Rahmen in ``w_mm``/``h_mm``: Bild oder Text mit fester Rahmengröße."""
+    return isinstance(obj, ImageObject) or obj.fit
+
+
+def _needs_size(obj: Object) -> bool:
+    """Text mit automatischer Schriftgröße ohne festen Rahmen: bekommt beim Platzieren seine
+    wirksame Größe fest (``fix_size``)."""
+    return isinstance(obj, TextObject) and not obj.fit and obj.size_pt is None
+
+
+def _text_only(obj: Object) -> None:
+    if not isinstance(obj, TextObject):
+        raise TypeError(f"Nur für Text-Objekte, nicht für {type(obj).__name__}.")
+
+
+def place(obj: Object, rect: Rect) -> Object:
+    """Kopie von ``obj`` an ``rect``; bei festem Rahmen auch Breite/Höhe (ungedreht)."""
     placed = copy.deepcopy(obj)
     placed.x_mm, placed.y_mm = rect.x, rect.y
-    if obj.fit:
+    if _framed(obj):
         w, h = (rect.h, rect.w) if obj.rotation in (90, 270) else (rect.w, rect.h)
         placed.w_mm, placed.h_mm = w, h
     return placed
@@ -214,6 +236,7 @@ def fix_size(obj: TextObject, base_pt: float) -> TextObject:
     Stücke mit eigener Größe behalten ihr Verhältnis; das Bild bleibt gleich: Jede Größe
     bekommt die kürzeste Dezimalzahl (ab 0,1 pt), die dieselbe Druckgröße ergibt.
     """
+    _text_only(obj)
     base_dots = round(base_pt * PT)
     fixed = copy.deepcopy(obj)
     fixed.size_pt, fixed.fit = round(base_pt, 1), False   # ergibt wieder base_dots
@@ -229,21 +252,22 @@ def fix_size(obj: TextObject, base_pt: float) -> TextObject:
     return fixed
 
 
-def exact_rect(obj: TextObject, rendered: RenderedObject) -> Rect:
+def exact_rect(obj: Object, rendered: RenderedObject) -> Rect:
     """Rahmen in mm, wie er im Modell steht (ohne Rundung auf Druckpunkte).
 
-    Position aus ``x_mm``/``y_mm``, Größe bei fester Rahmengröße aus ``w_mm``/``h_mm``
-    (gedreht), sonst wie gerendert; ein Objekt ohne Position steht, wo es gerendert wurde.
+    Position aus ``x_mm``/``y_mm``, Größe bei festem Rahmen (Bild, feste Rahmengröße) aus
+    ``w_mm``/``h_mm`` (gedreht), sonst wie gerendert; ein Objekt ohne Position steht, wo es
+    gerendert wurde.
     """
     r = object_rect(rendered)
     x, y = ((obj.x_mm or 0.0, obj.y_mm or 0.0) if obj.positioned else (r.x, r.y))
     w, h = r.w, r.h
-    if obj.positioned and obj.fit and obj.w_mm is not None and obj.h_mm is not None:
+    if obj.positioned and _framed(obj) and obj.w_mm is not None and obj.h_mm is not None:
         w, h = (obj.h_mm, obj.w_mm) if obj.rotation in (90, 270) else (obj.w_mm, obj.h_mm)
     return Rect(x, y, w, h)
 
 
-def _apply_change(obj: TextObject, rect: Rect, rendered: RenderedObject) -> Rect:
+def _apply_change(obj: Object, rect: Rect, rendered: RenderedObject) -> Rect:
     """Änderung gegenüber dem gerenderten Rahmen auf den Rahmen im Modell übertragen.
 
     So verschieben Pfeiltasten genau um 0,1 mm, obwohl das Bild auf Druckpunkte gerundet ist;
@@ -255,7 +279,7 @@ def _apply_change(obj: TextObject, rect: Rect, rendered: RenderedObject) -> Rect
         (exact.w, rect.w, shown.w), (exact.h, rect.h, shown.h))))
 
 
-def move(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
+def move(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
     """Kopie von ``obj``, verschoben auf ``rect`` (neue Lage des gerenderten Rahmens).
 
     Die Größe bleibt. Ein automatisch großes Objekt ohne eigenen Rahmen bekommt beim ersten
@@ -263,31 +287,39 @@ def move(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
     danach genauso aus.
     """
     target = _apply_change(obj, rect, rendered)
-    if obj.size_pt is None or (obj.fit and not obj.positioned):
+    if isinstance(obj, TextObject) and (obj.size_pt is None or (obj.fit and not obj.positioned)):
         obj = fix_size(obj, rendered.base_pt)
     moved = copy.deepcopy(obj)
     moved.x_mm, moved.y_mm = target.x, target.y
     return moved
 
 
-def set_frame(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
+def set_frame(obj: Object, rect: Rect, rendered: RenderedObject) -> Object:
     """Kopie mit dem Rahmen ``rect`` in mm, wie er im Modell steht (Zahlen im Panel „Position“).
 
-    Mit fester Rahmengröße gelten Lage und Größe, sonst nur die Lage. Ein automatisch großes
-    Objekt bekommt dabei seine wirksame Größe (``rendered.base_pt``) als feste Schriftgröße.
+    Mit festem Rahmen (Bild, feste Rahmengröße) gelten Lage und Größe, sonst nur die Lage. Ein
+    automatisch großes Objekt bekommt dabei seine wirksame Größe (``rendered.base_pt``) als
+    feste Schriftgröße.
     """
-    if not obj.fit and obj.size_pt is None:
+    if _needs_size(obj):
         obj = fix_size(obj, rendered.base_pt)
     return place(obj, rect)
 
 
-def resize(obj: TextObject, rect: Rect, rendered: RenderedObject, corner: bool) -> TextObject:
-    """Kopie nach Ziehen an einem Anfasser: gerenderter Rahmen → ``rect``.
+def resize(obj: Object, rect: Rect, rendered: RenderedObject, handle: str) -> Object:
+    """Kopie nach Ziehen am Anfasser ``handle`` („tl“, „t“, … „l“): gerenderter Rahmen → ``rect``.
 
-    Mit fester Rahmengröße ändert jeder Anfasser den Rahmen. Ohne skaliert eine Ecke
-    (``corner``) die Schrift, eine Kante schaltet die feste Rahmengröße ein.
+    Mit fester Rahmengröße ändert jeder Anfasser den Rahmen. Ohne skaliert eine Ecke die
+    Schrift, eine Kante schaltet die feste Rahmengröße ein.
+    Ein Bild mit ``keep_ratio`` behält dabei sein Seitenverhältnis (``keep_aspect``, dieselbe
+    Regel wie die Vorschau der Arbeitsfläche), ohne verzerren Kanten und Ecken den Rahmen.
     """
+    corner = len(handle) == 2
     target = _apply_change(obj, rect, rendered)
+    if isinstance(obj, ImageObject):
+        if obj.keep_ratio:
+            target = _rounded(keep_aspect(exact_rect(obj, rendered), target, handle))
+        return place(obj, target)
     if obj.fit:
         return place(obj, target)
     if corner:
@@ -300,6 +332,32 @@ def resize(obj: TextObject, rect: Rect, rendered: RenderedObject, corner: bool)
     return place(framed, target)
 
 
+def keep_aspect(old: Rect, new: Rect, handle: str) -> Rect:
+    """Rahmen ``new`` (nach Ziehen am Anfasser ``handle``) mit dem Seitenverhältnis von ``old``.
+
+    Was fest bleibt, folgt allein aus dem Anfasser (Vorschau und Ergebnis rechnen gleich):
+    Ecke – das stärker gewachsene Maß zählt, die gegenüberliegende Ecke bleibt. Kante – das
+    gezogene Maß zählt, die gegenüberliegende Kante bleibt, quer dazu die Mitte (links/rechts:
+    senkrecht mittig, oben/unten: waagerecht mittig).
+    """
+    if old.w <= 0 or old.h <= 0:
+        return new
+    across, along = "l" in handle or "r" in handle, "t" in handle or "b" in handle
+    fx, fy = new.w / old.w, new.h / old.h
+    factor = max(fx, fy) if across and along else fx if across else fy
+    w, h = old.w * factor, old.h * factor
+
+    def start(old0: float, old1: float, size: float, moves_start: bool, moves_end: bool) -> float:
+        if moves_start:
+            return old1 - size                 # Ende bleibt
+        if moves_end:
+            return old0                        # Anfang bleibt
+        return (old0 + old1 - size) / 2        # quer zur gezogenen Kante: Mitte bleibt
+
+    return Rect(start(old.x, old.right, w, "l" in handle, "r" in handle),
+                start(old.y, old.bottom, h, "t" in handle, "b" in handle), w, h)
+
+
 def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) -> TextObject:
     """Kopie mit allen Schriftgrößen (Grundgröße und Stücke) × ``factor``, auf 4–100 pt begrenzt.
 
@@ -308,6 +366,7 @@ def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) ->
     ``base_pt``: wirksame Grundgröße (``RenderedObject.base_pt``) für Text mit automatischer
     Größe – Stücke mit eigener Größe beziehen sich dann auf 12 pt und werden umgerechnet.
     """
+    _text_only(obj)
     if factor <= 0:
         raise ValueError(f"Faktor muss größer als 0 sein, nicht {factor!r}.")
     scaled = copy.deepcopy(obj)
@@ -340,7 +399,7 @@ def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) ->
 
 
 def outside_indices(rendered: list[RenderedObject], size: tuple[int, int],
-                    objects: list[TextObject] | None = None) -> list[int]:
+                    objects: list[Object] | None = None) -> list[int]:
     """Indizes der schon gerenderten Objekte, deren Rahmen über das Etikett ``size``
     (Druckpunkte in Leserichtung, wie ``render.label_size``) ragt – ohne neu zu rendern.
 
@@ -369,8 +428,8 @@ def objects_outside(doc: Document, model: str = "QL-600") -> list[int]:
 
 
 # --- Reiter „Layout“ ----------------------------------------------------------------
-def align_objects(objs: list[TextObject], rendered: list[RenderedObject], mode: str,
-                  area: Rect | None = None, grow: str | None = None) -> list[TextObject]:
+def align_objects(objs: list[Object], rendered: list[RenderedObject], mode: str,
+                  area: Rect | None = None, grow: str | None = None) -> list[Object]:
     """Kopien der Objekte, ausgerichtet wie ``align`` – mit ``area`` am Papier, sonst aneinander.
 
     Gerechnet wird mit den Rahmen, wie sie im Modell stehen (``exact_rect``); ein Objekt ohne
@@ -391,40 +450,46 @@ def align_objects(objs: list[TextObject], rendered: list[RenderedObject], mode:
     return [set_frame(o, _rounded(rect), r) for o, r, rect in zip(objs, rendered, moved)]
 
 
-def match_objects(objs: list[TextObject], rendered: list[RenderedObject],
-                  mode: str) -> list[TextObject]:
+def match_objects(objs: list[Object], rendered: list[RenderedObject],
+                  mode: str) -> list[Object]:
     """Kopien mit der Größe des ersten Objekts (``same``, ``width``, ``height``); Ecke bleibt.
     Das erste (Bezug) bleibt unverändert dasselbe Objekt – so muss es nicht neu gerendert werden.
 
-    Mit fester Rahmengröße wird der Rahmen gesetzt. Text ohne feste Rahmengröße wird
-    skaliert (Seitenverhältnis bleibt): bei „gleicher Größe“ mit dem Mittel aus Breiten-
-    und Höhenverhältnis, sonst nach dem angeglichenen Maß. Hat der Bezug keine Fläche
-    (leerer Text), bleibt alles unverändert.
+    Mit fester Rahmengröße (auch Bild ohne ``keep_ratio``) wird der Rahmen gesetzt. Text ohne
+    feste Rahmengröße und Bilder mit ``keep_ratio`` werden skaliert (Seitenverhältnis
+    bleibt): bei „gleicher Größe“ mit dem Mittel aus Breiten- und Höhenverhältnis, sonst nach
+    dem angeglichenen Maß. Hat der Bezug keine Fläche (leerer Text), bleibt alles unverändert.
     """
     rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
     if not rects or rects[0].w <= 0 or rects[0].h <= 0:
         return list(objs)           # leerer Bezug (unsichtbarer Rahmen): nichts angleichen
     result = objs[:1]
     for obj, r, old, new in zip(objs[1:], rendered[1:], rects[1:], match_size(rects, mode)[1:]):
-        if obj.fit:
+        uniform = obj.keep_ratio if isinstance(obj, ImageObject) else not obj.fit
+        if not uniform:
             result.append(set_frame(obj, _rounded(new), r))
             continue
         fx = new.w / old.w if old.w else 1.0
         fy = new.h / old.h if old.h else 1.0
         factor = {"same": (fx * fy) ** 0.5, "width": fx, "height": fy}[mode]
-        result.append(place(scale_text(obj, factor, base_pt=r.base_pt), _rounded(old)))
+        if isinstance(obj, ImageObject):
+            result.append(place(obj, _rounded(Rect(old.x, old.y, old.w * factor,
+                                                   old.h * factor))))
+        else:
+            result.append(place(scale_text(obj, factor, base_pt=r.base_pt), _rounded(old)))
     return result
 
 
-def maximize_object(obj: TextObject, rendered: RenderedObject, area: Rect, doc: Document,
-                    model: str = "QL-600") -> TextObject:
+def maximize_object(obj: Object, rendered: RenderedObject, area: Rect, doc: Document,
+                    model: str = "QL-600") -> Object:
     """Kopie, so groß wie möglich mittig in ``area`` (Seitenverhältnis bleibt).
 
-    Mit fester Rahmengröße wird der Rahmen gesetzt; sonst wird die Schrift skaliert und
-    das Ergebnis gerendert, damit es sicher hineinpasst und genau mittig steht.
+    Mit festem Rahmen (Bild, feste Rahmengröße) wird der Rahmen gesetzt; sonst wird die
+    Schrift skaliert und das Ergebnis gerendert, damit es sicher hineinpasst und genau
+    mittig steht.
     """
     grow = growing_axis(doc)
-    if obj.fit:
+    if _framed(obj):
         return set_frame(obj, _rounded(maximize(exact_rect(obj, rendered), area, grow)),
                          rendered)
     shown = object_rect(rendered)
@@ -459,13 +524,13 @@ def _sizes_of(obj: TextObject) -> list[float | None]:
     return [obj.size_pt, *(span.size_pt for para in obj.paragraphs for span in para.spans)]
 
 
-def rotate(obj: TextObject, rendered: RenderedObject, degrees: int) -> TextObject:
+def rotate(obj: Object, rendered: RenderedObject, degrees: int) -> Object:
     """Kopie, um ``degrees`` (±90, im Uhrzeigersinn) gedreht; die Mitte des Rahmens bleibt.
 
     Ein Objekt ohne Position bekommt seine Lage und wirksame Schriftgröße fest.
     """
     old = exact_rect(obj, rendered)
-    if not obj.fit and obj.size_pt is None:
+    if _needs_size(obj):
         obj = fix_size(obj, rendered.base_pt)
     turned = copy.deepcopy(obj)
     turned.rotation = (obj.rotation + degrees) % 360
@@ -490,8 +555,8 @@ def reorder(items: list, indices: list[int], step: int) -> tuple[list, list[int]
     return [items[i] for i in order], [order.index(i) for i in indices]
 
 
-def to_grid(obj: TextObject, x: bool = False, y: bool = False, w: bool = False,
-            h: bool = False) -> TextObject:
+def to_grid(obj: Object, x: bool = False, y: bool = False, w: bool = False,
+            h: bool = False) -> Object:
     """Kopie mit den gewählten Werten auf ``GRID_MM`` gerundet – so, wie die Felder im Panel
     sie zeigen (nach Ziehen/Skalieren mit der Maus; Pfeiltasten verschieben genau).
 
@@ -562,6 +627,7 @@ def _to_frame(point: tuple[float, float], frame: tuple[float, float, float, floa
 def anchor_align(obj: TextObject) -> str:
     """Textposition, nach der sich der Rahmen beim Wachsen richtet (``anchor_after_edit``):
     die gemeinsame der Absätze; haben sie verschiedene, bleibt die linke Kante („left“)."""
+    _text_only(obj)
     aligns = {para.align for para in obj.paragraphs}
     return aligns.pop() if len(aligns) == 1 else "left"
 
@@ -579,7 +645,7 @@ def anchor_after_edit(obj: TextObject, old: RenderedObject,
     Nur für Objekte mit Position: eines ohne Position bleibt mittig auf dem Etikett, der
     Aufrufer setzt dort keine Position.
     """
-    align = anchor_align(obj)
+    align = anchor_align(obj)                  # nur Text (TypeError bei Bildern)
     start = exact_rect(obj, old)
     # Lage des festen Punkts relativ zur linken oberen Ecke des Rahmens (Druckpunkte)
     ox, oy = from_object(old.layout.anchor(align), old, obj.rotation)
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 4cff4f9..1402a33 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -5,19 +5,22 @@ gleicher Zeilenabstand (Unterkante von „A“ + 4 Punkte), gleiche Ausrichtungs
 reiner Text sieht dadurch pixelgleich aus wie früher.
 Das Ergebnis (``TextLayout``) zeichnet das Rendern; dieselben Zahlen liefern der
 Arbeitsfläche Schreibmarke, Treffer und Markierung.
+Bild-Objekte werden auf ihren Rahmen skaliert und in Schwarz/Weiß umgewandelt
+(``imaging.to_layers``).
 """
 from __future__ import annotations
 
 import copy
+import io
 import math
 from dataclasses import dataclass, field
-from functools import cached_property
+from functools import cached_property, lru_cache
 
 from PIL import Image, ImageDraw, ImageOps
 
-from . import fonts
+from . import fonts, imaging
 from .document import (ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS,
-                       Document, Paragraph, Span, TextObject)
+                       Document, ImageObject, Paragraph, Span, TextObject)
 from .labels import DPI, get_label, length_limits
 
 MARGIN = 12            # Punkte, ca. 1 mm
@@ -57,6 +60,8 @@ def font_warnings(doc: Document) -> list[str]:
     """Hinweise zu ersetzten Schriften (je Familie einmal)."""
     warnings: list[str] = []
     for obj in doc.objects:
+        if not isinstance(obj, TextObject):
+            continue
         for para in obj.paragraphs:
             for span in para.spans:
                 if span.family is None:
@@ -73,12 +78,13 @@ class RenderedObject:
     """Einzeln gerendertes Objekt in Druckpunkten, in Leserichtung.
 
     ``x``/``y``/``w``/``h``: Rahmen auf dem Etikett (Auswahl, Einrasten, Layout);
-    ``base_pt``: wirksame Grundgröße.
+    ``base_pt``: wirksame Grundgröße (Bild-Objekte: 0).
     ``image``: Graustufen (L), weißer Grund, Tinte schwarz – deckt den Rahmen und die ganze
     Tinte ab (Anschnitt: Kantenglättung, Unterstreichung, Glyphen wie „J“ reichen etwas über
     den Rahmen); seine linke obere Ecke liegt bei ``x + image_dx``, ``y + image_dy``
-    (``image_dx``/``image_dy`` ≤ 0).
-    ``layout``: der Zeilensatz, aus dem das Bild gezeichnet wurde (Schreibmarke, Treffer).
+    (``image_dx``/``image_dy`` ≤ 0; Bild-Objekte: genau der Rahmen, 0).
+    ``layout``: der Zeilensatz, aus dem das Bild gezeichnet wurde (Schreibmarke, Treffer);
+    None bei Bild-Objekten.
     """
     image: Image.Image
     x: int
@@ -91,7 +97,8 @@ class RenderedObject:
     layout: TextLayout | None = field(default=None, compare=False, repr=False)
 
 
-def render_object(obj: TextObject, doc: Document, model: str = "QL-600") -> RenderedObject:
+def render_object(obj: TextObject | ImageObject, doc: Document,
+                  model: str = "QL-600") -> RenderedObject:
     """Ein Objekt einzeln rendern (Arbeitsfläche); Position bezogen auf das Etikett von ``doc``."""
     return _finish(*_measure(obj, doc, model))
 
@@ -99,10 +106,13 @@ def render_object(obj: TextObject, doc: Document, model: str = "QL-600") -> Rend
 def text_layout(obj: TextObject, doc: Document, model: str = "QL-600") -> TextLayout:
     """Zeilensatz eines Objekts ohne Bild – derselbe, den ``render_object`` zeichnet
     (``RenderedObject.layout``)."""
+    if not isinstance(obj, TextObject):
+        raise TypeError("Einen Zeilensatz gibt es nur für Text-Objekte.")
     return _place(*_measure(obj, doc, model))[0]
 
 
-def _measure(obj: TextObject, doc: Document, model: str) -> tuple[Prepared, _Sheet, int, int]:
+def _measure(obj: TextObject | ImageObject, doc: Document,
+             model: str) -> tuple[Prepared, _Sheet, int, int]:
     """Objekt messen; Etikettgröße nur für ein Objekt ohne Position (mittig), sonst 0."""
     sheet = _sheet(doc, model)
     prep = _prepare(obj, sheet)
@@ -155,7 +165,8 @@ def label_size(doc: Document, model: str = "QL-600",
     return _label_size(sheet, prepared)
 
 
-def prepare_object(obj: TextObject, doc: Document, model: str = "QL-600") -> Prepared:
+def prepare_object(obj: TextObject | ImageObject, doc: Document,
+                   model: str = "QL-600") -> Prepared:
     """Objekt messen (Grundgröße, Zeilen, Rahmengröße) – unabhängig von der Etikettgröße.
 
     Zusammen mit ``label_size(..., prepared=)`` und ``finish_object`` rendert die
@@ -183,8 +194,8 @@ class Rendered:
 @dataclass
 class _Cached:
     """Gemessenes und gerendertes Objekt samt Stand, aus dem es entstand."""
-    obj: TextObject            # hält das Objekt fest, damit seine id nicht neu vergeben wird
-    snapshot: TextObject
+    obj: TextObject | ImageObject  # hält das Objekt fest, damit seine id nicht neu vergeben wird
+    snapshot: TextObject | ImageObject     # Bilder: die PNG-Bytes werden geteilt, nicht kopiert
     context: tuple
     prepared: Prepared
     size: tuple | None = None                  # Etikettgröße des Bilds (None = mit Position)
@@ -199,6 +210,11 @@ class Renderer:
     ohne Position (steht mittig) die Etikettgröße ändert. Das Druckbild wird nur neu
     zusammengesetzt, wenn sich ein Objektbild oder die Größe ändert. Ergebnis wie
     ``render_document`` – Vorschau = Druck.
+
+    Schlüssel ist der ganze Objektinhalt (Schnappschuss) – bei Bildern also auch alle
+    Einstellungen. Das bleibt billig: ``copy.deepcopy`` teilt unveränderliche PNG-Bytes, und
+    der Vergleich derselben Bytes ist ein Identitätsvergleich. Ändert sich nur die
+    Umwandlung (Schwelle, Foto, Umkehren), kommt das skalierte Bild aus ``_scaled_source``.
     """
 
     def __init__(self):
@@ -294,8 +310,9 @@ def _dots(mm: float) -> int:
 
 @dataclass
 class Prepared:
-    """Gemessenes Objekt: Grundgröße, Zeilen (an der breitesten Zeile ausgerichtet), Tintenbox."""
-    obj: TextObject
+    """Gemessenes Objekt: Grundgröße, Zeilen (an der breitesten Zeile ausgerichtet), Tintenbox.
+    Bild-Objekte: keine Zeilen, Tintenbox = Rahmen."""
+    obj: TextObject | ImageObject
     base: int
     lines: list
     box: tuple[int, int, int, int]
@@ -308,7 +325,9 @@ class Prepared:
         return (h, w) if self.obj.rotation in (90, 270) else (w, h)
 
 
-def _prepare(obj: TextObject, sheet: _Sheet) -> Prepared:
+def _prepare(obj: TextObject | ImageObject, sheet: _Sheet) -> Prepared:
+    if isinstance(obj, ImageObject):
+        return _prepare_image(obj)
     for para in obj.paragraphs:
         if para.align not in ALIGNMENTS:
             raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
@@ -399,6 +418,8 @@ def _finish(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedO
     """Objektbild aus dem Zeilensatz (``_place``) zeichnen und auf dem Etikett platzieren;
     Bild, Rahmen und Bildlage werden mit der Fläche gedreht."""
     obj = prep.obj
+    if isinstance(obj, ImageObject):
+        return _finish_image(prep)
     text, frame, area, origin = _place(prep, sheet, width, height)
     image, (ix, iy) = _paint(text.pieces, text.x0, text.y0, *frame[2:],
                              at=(origin[0] + frame[0], origin[1] + frame[1]))
@@ -471,6 +492,77 @@ def _paint(lines: list, x0: int, y0: int, width: int, height: int,
     return canvas.crop((left, top, right, bottom)), (left - px, top - py)
 
 
+# --- Bild-Objekte -------------------------------------------------------------------
+def _prepare_image(obj: ImageObject) -> Prepared:
+    """Bild-Objekt prüfen und messen: Rahmen in Druckpunkten (ungedreht) aus ``w_mm``/``h_mm``."""
+    if obj.rotation not in ROTATIONS:
+        raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
+    imaging.check(obj.mode, obj.threshold)
+    if not (obj.w_mm > 0 and obj.h_mm > 0):
+        raise ValueError(f"Größe des Bilds muss größer als 0 sein, nicht "
+                         f"{obj.w_mm:g} × {obj.h_mm:g} mm.")
+    frame = (max(1, _dots(obj.w_mm)), max(1, _dots(obj.h_mm)))
+    return Prepared(obj, 0, [], (0, 0, *frame), frame)
+
+
+def _finish_image(prep: Prepared) -> RenderedObject:
+    """Bild auf den Rahmen skalieren, in Schwarz/Weiß umwandeln und drehen (wie Text).
+
+    Mit ``keep_ratio`` wird nicht verzerrt: Passt das Seitenverhältnis des Rahmens nicht,
+    steht das Bild eingepasst in seiner Mitte (der Rest bleibt Papier, auch mit ``invert``).
+    """
+    obj = prep.obj
+    w, h = prep.frame
+    crop = tuple(obj.crop) if obj.crop is not None else None
+    picture = _scaled_source(obj.png, crop, (w, h), obj.keep_ratio)
+    black = imaging.to_layers(picture, obj.mode, obj.threshold, obj.invert)["black"]
+    image = Image.new("L", (w, h), 255)
+    image.paste(black.convert("L"), ((w - picture.width) // 2, (h - picture.height) // 2))
+    frame = (0, 0, w, h)
+    if obj.rotation:
+        image = image.transpose(_TRANSPOSE[obj.rotation])
+        frame = _turn(frame, (w, h), obj.rotation)
+    return RenderedObject(image, _dots(obj.x_mm), _dots(obj.y_mm), frame[2], frame[3], 0.0)
+
+
+@lru_cache(maxsize=2)
+def _source(png: bytes, crop: tuple[int, int, int, int] | None) -> Image.Image:
+    """Original (RGB), auf den Ausschnitt zugeschnitten.
+
+    Gecacht, damit Ziehen am Anfasser nicht jedes Mal dekodiert: Python merkt sich den Hash
+    eines ``bytes``-Objekts, der Schlüssel kostet nach dem ersten Mal fast nichts.
+    Das Ergebnis wird geteilt und darf nicht verändert werden.
+    """
+    with Image.open(io.BytesIO(png)) as img:
+        img = img.convert("RGB")
+    if crop is not None:
+        l, t, r, b = crop
+        if not (0 <= l < r <= img.width and 0 <= t < b <= img.height):
+            raise ValueError(f"Ausschnitt {crop} liegt nicht im Bild "
+                             f"({img.width} × {img.height} Pixel).")
+        img = img.crop(crop)
+    return img
+
+
+@lru_cache(maxsize=8)
+def _scaled_source(png: bytes, crop: tuple[int, int, int, int] | None, size: tuple[int, int],
+                   keep_ratio: bool) -> Image.Image:
+    """Ausschnitt auf ``size`` skaliert (Lanczos); mit ``keep_ratio`` eingepasst, nicht
+    verzerrt. Gecacht: Schwelle, Foto und Umkehren ändern nur die Umwandlung danach."""
+    src = _source(png, crop)
+    w, h = size
+    if keep_ratio:
+        scale = min(w / src.width, h / src.height)
+        fitted = (max(1, round(src.width * scale)), max(1, round(src.height * scale)))
+        if abs(fitted[0] - w) > 1 or abs(fitted[1] - h) > 1:   # sonst nur Rundung: füllen
+            w, h = fitted
+    if src.size == (w, h):
+        return src
+    # reducing_gap: stark verkleinert erst ganzzahlig reduzieren (schnell), dann Lanczos;
+    # vergrößert und bis 2× verkleinert genau wie reines Lanczos (Codes bleiben exakt)
+    return src.resize((w, h), Image.Resampling.LANCZOS, reducing_gap=2.0)
+
+
 # --- Schriftgrößen ----------------------------------------------------------
 def span_dots(obj: TextObject, span: Span, base: int) -> int:
     """Größe eines Stücks in Druckpunkten bei Grundgröße ``base`` (gemeinsam skaliert)."""
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1193 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-17-bild-objekt-design.md src/labelwerk/document.py src/labelwerk/files.py src/labelwerk/gui/main_window.py src/labelwerk/imaging.py src/labelwerk/layout.py src/labelwerk/render.py tests/test_files.py tests/test_image_object.py tests/test_imaging.py tests/test_layout.py tests/test_renderer.py
git commit -m "Kern: Bild-Objekt – laden, zuschneiden, Schwarz/Weiß-Umwandlung, rendern, platzieren

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: GUI – Werkzeug Bild: aus Datei, Zwischenablage, Ablegen, Bild-Panel

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-17-bild-objekt-design.md`
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/files.py`
- Modify: `src/labelwerk/gui/canvas.py`
- Create: `src/labelwerk/gui/image_import.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Create: `src/labelwerk/gui/panels/image.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/gui/tools.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/shortcuts.py`
- Modify: `tests/gui/conftest.py`
- Create: `tests/gui/test_gui_image.py`
- Modify: `tests/gui/test_gui_layout.py`
- Modify: `tests/test_image_object.py`
- Create: `tests/test_image_place.py`

**Interfaces / Produces:** Reiter BILD (`panels/image.py` `ImagePanel`), `gui/image_import.py` (load, load_svg, svg_size, MIME-Helfer, `MIME_OBJECTS`), `MainWindow.insert_image_file(s)`, `paste_image`, `ask_image_file`/`ask_pdf_page`; Strg+V-Reihenfolge eigene Objekte › Dateien › Text › Bild; Ablegen auf der Arbeitsfläche; Aktion `image.insert` (Strg+Umschalt+I); `layout.insert_frame`, `set_crop`, `original_size`, `set_keep_ratio`, `proportional`; Doku.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/conftest.py b/tests/gui/conftest.py
index 61daf93..c72b972 100644
--- a/tests/gui/conftest.py
+++ b/tests/gui/conftest.py
@@ -16,6 +16,12 @@ else:
         yield
         qapp.setStyleSheet("")
 
+    @pytest.fixture(autouse=True)
+    def empty_clipboard(qapp):
+        """Jeder Test beginnt mit leerer Zwischenablage des Systems – „Einfügen“ folgt ihr."""
+        qapp.clipboard().clear()
+        yield
+
     @pytest.fixture(autouse=True)
     def no_printer(monkeypatch):
         """Kein Test liest echte Druckerdaten aus /sys."""
diff --git a/tests/gui/test_gui_image.py b/tests/gui/test_gui_image.py
new file mode 100644
index 0000000..27e29ad
--- /dev/null
+++ b/tests/gui/test_gui_image.py
@@ -0,0 +1,782 @@
+"""Werkzeug „Bild“ (Etappe 3d-2a): einfügen aus Datei, Zwischenablage und per Ablegen,
+Bild-Panel, Bilder auf der Arbeitsfläche wie Text."""
+import io
+
+import pytest
+from PIL import Image, ImageDraw
+from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
+from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage, QMouseEvent
+from PySide6.QtTest import QTest
+from PySide6.QtWidgets import QApplication
+
+from labelwerk import layout, shortcuts
+from labelwerk.document import Document, ImageObject, TextObject
+from labelwerk.gui.image_import import CLIPBOARD, MIME_OBJECTS
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.gui.tools import TOOLS
+from labelwerk.settings import Settings
+
+NO_MOD = Qt.KeyboardModifier.NoModifier
+CTRL = Qt.KeyboardModifier.ControlModifier
+LEFT = Qt.MouseButton.LeftButton
+MM = 300 / 25.4                                # Pixel je mm bei 300 dpi
+
+
+def _picture(w=300, h=150, border=30, gray=0) -> Image.Image:
+    """Weißes Bild mit Rand ``border`` und einem Schachbrett (wie ein QR-Code) darin."""
+    img = Image.new("RGB", (w, h), "white")
+    draw = ImageDraw.Draw(img)
+    draw.rectangle((border, border, w - border - 1, h - border - 1), fill=(gray,) * 3)
+    for y in range(border, h - border, 10):
+        for x in range(border + (y // 10) % 2 * 10, w - border, 20):
+            draw.rectangle((x, y, x + 9, y + 9), fill="white")
+    return img
+
+
+def _file(tmp_path, img=None, name="code.png", dpi=300):
+    path = tmp_path / name
+    (img or _picture()).save(path, dpi=(dpi, dpi))
+    return path
+
+
+def _qimage(img: Image.Image) -> QImage:
+    buffer = io.BytesIO()
+    img.save(buffer, "PNG")
+    return QImage.fromData(buffer.getvalue())
+
+
+def _doc():
+    return Document("62", length_mm=40, objects=[TextObject("Eins", size_pt=14, x_mm=4, y_mm=4)])
+
+
+def _window(qtbot, doc=None):
+    win = MainWindow(doc=doc if doc is not None else _doc(),
+                     settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    win.show()
+    return win
+
+
+@pytest.fixture
+def window(qtbot):
+    return _window(qtbot)
+
+
+def _insert_file(win, path, page=None):
+    win.ask_image_file = lambda: str(path)
+    win.ask_pdf_page = lambda path, count: page
+    win.panel("image").from_file.click()
+
+
+def _with_image(qtbot, tmp_path, img=None, **settings):
+    win = _window(qtbot)
+    _insert_file(win, _file(tmp_path, img))
+    for key, value in settings.items():
+        setattr(win.doc.objects[1], key, value)
+    win.render_now()
+    return win
+
+
+def _send(canvas, kind, pos, buttons, modifiers=NO_MOD):
+    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
+    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)),
+                        button, buttons, modifiers)
+    QApplication.sendEvent(canvas.viewport(), event)
+
+
+def _click(canvas, pos):
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, pos, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)
+
+
+def _double_click(canvas, pos):
+    _click(canvas, pos)
+    _send(canvas, QMouseEvent.Type.MouseButtonDblClick, pos, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)
+
+
+def _drag(canvas, start, end):
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
+
+
+def _focus_canvas(win, qtbot):
+    win.activateWindow()
+    win.canvas.setFocus()
+    qtbot.waitUntil(lambda: win.canvas.hasFocus(), timeout=1000)
+
+
+def _drop(canvas, mime, pos, process=True):
+    """Ablegen; verarbeitet wird erst nach dem Ereignis (``process``: gleich abwarten)."""
+    for event in (QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD),
+                  QDropEvent(pos, Qt.DropAction.CopyAction, mime, LEFT, NO_MOD)):
+        QApplication.sendEvent(canvas.viewport(), event)
+    if process:
+        QTest.qWait(0)
+
+
+def _ink(win, index):
+    return win.rendered[index].image.histogram()[0]
+
+
+def _status(win):
+    return win.result.text()
+
+
+# --- Werkzeug und Panel -------------------------------------------------------------
+def test_image_tool_comes_after_text(window):
+    assert [tool.key for tool in TOOLS] == ["paper", "text", "image", "layout"]
+    window.tool_actions["image"].trigger()
+    assert window.panels.currentWidget() is window.panel("image")
+    assert window.canvas.tool() == "select"
+    panel = window.panel("image")
+    assert panel.hint.isVisible() and not panel.threshold.isEnabled()
+
+
+def test_insert_action_is_in_the_shortcut_registry(window):
+    entry = shortcuts.action("image.insert")
+    assert (entry.default, entry.scope) == ("Ctrl+Shift+I", "canvas")
+    assert window.shortcut_actions["image.insert"] in window.canvas.actions()
+    assert "Ctrl+Shift+I" in window.panel("image").from_file.toolTip()
+
+
+# --- Aus Datei ----------------------------------------------------------------------
+def test_file_is_inserted_one_to_one_centred_cropped_and_selected(window, tmp_path):
+    _insert_file(window, _file(tmp_path))
+    obj = window.doc.objects[1]
+    assert isinstance(obj, ImageObject) and obj.source == "code.png"
+    assert obj.crop == (30, 30, 270, 120)                    # Rand fällt weg
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((240 / MM, 90 / MM))
+    rect = layout.exact_rect(obj, window.rendered[1])
+    area = window._area
+    assert (rect.cx, rect.cy) == pytest.approx((area.cx, area.cy), abs=0.01)
+    assert window.canvas.selection() == [1]
+    assert window.panels.currentWidget() is window.panel("image")
+    assert window.panel("image").index == 1
+    window.undo()                                            # ein Schritt
+    assert len(window.doc.objects) == 1
+
+
+def test_cancelled_file_dialog_inserts_nothing(window):
+    window.ask_image_file = lambda: None
+    window.panel("image").from_file.click()
+    assert len(window.doc.objects) == 1 and not window.history.can_undo(window.doc)
+
+
+def test_too_large_image_is_fitted_with_hint(window, tmp_path):
+    _insert_file(window, _file(tmp_path, _picture(3000, 400, border=0)))
+    obj = window.doc.objects[1]
+    area = window._area
+    assert obj.w_mm == pytest.approx(area.w, abs=0.01)
+    assert obj.w_mm / obj.h_mm == pytest.approx(3000 / 400, rel=1e-4)
+    percent = round(area.w / (3000 / MM) * 100)
+    assert _status(window) == f"Bild auf {percent} % verkleinert – Codes ggf. nicht mehr lesbar"
+    # eingepasst: höchstens 600 dpi bezogen auf die neue Druckgröße, 1:1-Größe bleibt
+    assert obj.image().width == pytest.approx(600 * obj.w_mm / 25.4, abs=1)
+    assert obj.natural_mm() == pytest.approx((3000 / MM, 400 / MM), abs=0.05)   # ganze Pixel
+
+
+def test_shrink_hint_never_says_zero_percent(window, tmp_path):
+    _insert_file(window, _file(tmp_path, _picture(3000, 30, border=0), dpi=4))    # 19 m
+    assert window.doc.objects[1].w_mm == pytest.approx(window._area.w, abs=0.01)
+    assert _status(window).startswith("Bild auf < 1 % verkleinert")
+
+
+def _pdf(tmp_path):
+    path = tmp_path / "marken.pdf"
+    pages = [_picture(300, 150), _picture(150, 150)]
+    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=300)
+    return path
+
+
+def test_pdf_with_several_pages_asks_for_the_page(window, tmp_path):
+    asked = []
+    window.ask_image_file = lambda: str(_pdf(tmp_path))
+    window.ask_pdf_page = lambda path, count: asked.append(count) or 2
+    window.panel("image").from_file.click()
+    obj = window.doc.objects[1]
+    assert asked == [2]
+    assert (obj.source, obj.page) == ("marken.pdf", 2)
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((90 / MM, 90 / MM), abs=0.6)   # PDF: Kanten geglättet
+    assert window.panel("image").source.text() == "marken.pdf · Seite 2"
+
+
+def test_cancelled_page_dialog_inserts_nothing(window, tmp_path):
+    _insert_file(window, _pdf(tmp_path), page=None)
+    assert len(window.doc.objects) == 1
+
+
+def test_svg_size_units_are_case_insensitive(tmp_path):
+    from labelwerk.gui.image_import import svg_size
+    path = tmp_path / "gross.svg"
+    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="25.4MM" height="1IN"/>')
+    assert svg_size(path) == pytest.approx((96, 96))
+
+
+def test_svg_is_rasterized_at_300_dpi(window, tmp_path):
+    path = tmp_path / "logo.svg"
+    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="96" height="48">'
+                    '<rect width="96" height="48" fill="black"/></svg>')
+    _insert_file(window, path)
+    obj = window.doc.objects[1]
+    assert obj.source == "logo.svg"
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((25.4, 12.7), abs=0.1)   # 1 in × ½ in
+    assert obj.image().size == (300, 150)
+    assert _ink(window, 1) > 0.9 * 300 * 150
+
+
+@pytest.mark.parametrize("width, height", [("25.4mm", "12.7mm"), ("1in", "0.5in"),
+                                           ("2.54cm", "36pt"), ("6pc", "48px")])
+def test_svg_with_physical_units_keeps_its_size(window, tmp_path, width, height):
+    """mm/cm/in/pt/pc nach CSS (96 px je Zoll) – Qt rechnete mit 90 dpi (6 % zu klein)."""
+    path = tmp_path / "masse.svg"
+    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
+                    'viewBox="0 0 20 10"><rect width="20" height="10" fill="black"/></svg>')
+    _insert_file(window, path)
+    obj = window.doc.objects[1]
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((25.4, 12.7), abs=0.1)
+    assert obj.image().size == (300, 150)
+    assert _ink(window, 1) > 0.9 * 300 * 150
+
+
+@pytest.mark.parametrize("name, content, message", [
+    ("kaputt.png", b"kein bild", "kann nicht gelesen werden"),
+    ("notiz.txt", b"text", "Dateityp nicht unterstützt"),
+    ("kaputt.svg", b"<svg", "kann nicht gelesen werden"),
+])
+def test_unreadable_files_show_a_message(window, tmp_path, name, content, message):
+    path = tmp_path / name
+    path.write_bytes(content)
+    _insert_file(window, path)
+    assert len(window.doc.objects) == 1
+    assert message in _status(window)
+    assert window.result.property("state") == "error"
+
+
+def test_unsupported_type_message_lists_all_image_types(window, tmp_path):
+    path = tmp_path / "notiz.txt"
+    path.write_text("x")
+    _insert_file(window, path)
+    assert _status(window) == ("Dateityp nicht unterstützt: .txt – möglich: "
+                               "PNG, JPG, GIF, BMP, WebP, SVG, PDF")
+
+
+def test_file_dialog_filter_accepts_uppercase_names():
+    from labelwerk.gui.image_import import FILE_FILTER
+    for pattern in ("*.png", "*.PNG", "*.jpeg", "*.JPEG", "*.svg", "*.SVG", "*.PDF"):
+        assert f" {pattern}" in FILE_FILTER or f"({pattern}" in FILE_FILTER
+
+
+def test_missing_file_and_missing_page_show_a_message(window, tmp_path):
+    window.insert_image_files([tmp_path / "fehlt.png"])
+    assert "nicht gefunden" in _status(window)
+    window.insert_image_files([_pdf(tmp_path)], page=5)
+    assert "nur 2 Seite" in _status(window)
+    assert len(window.doc.objects) == 1
+
+
+def test_light_image_is_kept_whole(window, tmp_path):
+    """Helles Foto ohne Weiß: alles ist Inhalt („nicht weiß“), nichts wird abgeschnitten."""
+    _insert_file(window, _file(tmp_path, Image.new("RGB", (300, 150), (220, 220, 220))))
+    obj = window.doc.objects[1]
+    assert obj.crop == (0, 0, 300, 150) and (obj.w_mm, obj.h_mm) == pytest.approx((300 / MM, 150 / MM))
+    assert "zugeschnitten" not in _status(window)
+
+
+def test_yellow_logo_is_cropped_to_the_logo(window, tmp_path):
+    img = Image.new("RGB", (300, 150), "white")
+    img.paste((255, 220, 0), (40, 30, 200, 120))
+    _insert_file(window, _file(tmp_path, img))
+    assert window.doc.objects[1].crop == (40, 30, 200, 120)
+
+
+def test_white_image_is_not_cropped_with_hint(window, tmp_path):
+    _insert_file(window, _file(tmp_path, Image.new("RGB", (300, 150), "white")))
+    obj = window.doc.objects[1]
+    assert obj.crop is None and (obj.w_mm, obj.h_mm) == pytest.approx((300 / MM, 150 / MM))
+    assert _status(window) == "Bild nicht zugeschnitten – nur weiße Fläche gefunden"
+    panel = window.panel("image")
+    assert not panel.crop.isChecked()
+    panel.crop.click()                                      # Zuschnitt: findet nichts
+    assert not panel.crop.isChecked() and window.doc.objects[1].crop is None
+    assert _status(window) == "Bild nicht zugeschnitten – nur weiße Fläche gefunden"
+
+
+# --- Zwischenablage -----------------------------------------------------------------
+def test_clipboard_button_follows_the_clipboard(window):
+    button = window.panel("image").from_clipboard
+    assert not button.isEnabled()
+    QApplication.clipboard().setImage(_qimage(_picture()))
+    assert button.isEnabled()
+    QApplication.clipboard().setText("nur Text")
+    assert not button.isEnabled()
+
+
+def test_blank_text_clipboard_does_not_enable_paste(window):
+    QApplication.clipboard().setText("  \n\t ")
+    assert not window.shortcut_actions["edit.paste"].isEnabled()
+
+
+def test_clipboard_image_via_panel(window):
+    QApplication.clipboard().setImage(_qimage(_picture()))
+    window.panel("image").from_clipboard.click()
+    obj = window.doc.objects[1]
+    assert isinstance(obj, ImageObject) and obj.source == CLIPBOARD
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((240 / MM, 90 / MM))   # 300 dpi, zugeschnitten
+    assert window.canvas.selection() == [1]
+
+
+def test_clipboard_without_image_shows_a_message(window):
+    QApplication.clipboard().setText("nur Text")
+    window.paste_image()
+    assert len(window.doc.objects) == 1
+    assert _status(window) == "Kein Bild in der Zwischenablage."
+
+
+def test_ctrl_v_pastes_clipboard_image(window, qtbot):
+    QApplication.clipboard().setImage(_qimage(_picture()))
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
+    assert isinstance(window.doc.objects[1], ImageObject)
+
+
+def test_copy_marks_the_system_clipboard_and_ctrl_v_pastes_objects(window, qtbot):
+    window.canvas.set_selection([0])
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_C, CTRL)
+    mime = QApplication.clipboard().mimeData()
+    assert mime.hasFormat(MIME_OBJECTS) and mime.text() == "Eins"
+    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
+    assert [type(o) for o in window.doc.objects] == [TextObject, TextObject]
+    assert window.doc.objects[1].x_mm == pytest.approx(6)    # Objekt, kein neuer Textrahmen
+
+
+def test_other_clipboard_content_wins_over_older_copy(window, qtbot):
+    window.canvas.set_selection([0])
+    window.copy_selected()
+    QApplication.clipboard().setImage(_qimage(_picture()))
+    window.paste()
+    assert isinstance(window.doc.objects[1], ImageObject)
+
+
+def test_paste_uses_last_copy_when_system_clipboard_is_empty(window):
+    window.canvas.set_selection([0])
+    window.copy_selected()
+    QApplication.clipboard().clear()                          # z. B. Zwischenablage nicht erreichbar
+    assert window.shortcut_actions["edit.paste"].isEnabled()
+    window.paste()
+    assert [o.text for o in window.doc.objects] == ["Eins", "Eins"]
+
+
+def test_ctrl_v_with_text_creates_text_frame(window, qtbot):
+    QApplication.clipboard().setText("Hallo\r\nWelt\n")
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
+    obj = window.doc.objects[1]
+    assert isinstance(obj, TextObject) and obj.text == "Hallo\nWelt"
+    assert all(p.align == "left" for p in obj.paragraphs)
+    area = window._area
+    assert (obj.x_mm, obj.y_mm) == pytest.approx((area.x, area.y), abs=0.05)
+    assert window.canvas.selection() == [1] and not window.edit_session.active
+    window.undo()
+    assert len(window.doc.objects) == 1
+
+
+def test_paste_follows_the_system_clipboard(window):
+    paste = window.shortcut_actions["edit.paste"]
+    assert not paste.isEnabled()
+    QApplication.clipboard().setText("Text")
+    assert paste.isEnabled()
+    QApplication.clipboard().clear()
+    assert not paste.isEnabled()
+
+
+def test_copied_image_pastes_offset(window, tmp_path):
+    _insert_file(window, _file(tmp_path))
+    before = window.doc.objects[1]
+    window.copy_selected()
+    window.paste()
+    pasted = window.doc.objects[2]
+    assert isinstance(pasted, ImageObject) and pasted.png is before.png
+    assert (pasted.x_mm, pasted.y_mm) == pytest.approx((before.x_mm + 2, before.y_mm + 2))
+
+
+def _set_clipboard(text=None, image=None, files=()):
+    mime = QMimeData()
+    if text is not None:
+        mime.setText(text)
+    if image is not None:
+        mime.setImageData(_qimage(image))
+    if files:
+        mime.setUrls([QUrl.fromLocalFile(str(path)) for path in files])
+    QApplication.clipboard().setMimeData(mime)
+
+
+def test_ctrl_v_with_local_files_inserts_the_images(window, tmp_path):
+    path = _file(tmp_path)
+    _set_clipboard(text=str(path), files=[path])           # wie aus dem Dateimanager
+    assert window.shortcut_actions["edit.paste"].isEnabled()
+    window.paste()
+    obj = window.doc.objects[1]
+    assert isinstance(obj, ImageObject) and obj.source == "code.png"
+
+
+def test_ctrl_v_with_other_local_file_says_so(window, tmp_path):
+    path = tmp_path / "liste.csv"
+    path.write_text("a;b")
+    _set_clipboard(files=[path])
+    window.paste()
+    assert len(window.doc.objects) == 1
+    assert _status(window).startswith("Dateityp nicht unterstützt: .csv")
+
+
+def test_ctrl_v_text_wins_over_image(window):
+    """Tabellenzellen bringen auch ein Bild mit – Strg+V nimmt den Text; das Bild gibt es über
+    „Aus Zwischenablage“."""
+    _set_clipboard(text="A1\tB1", image=_picture())
+    window.paste()
+    obj = window.doc.objects[1]
+    assert isinstance(obj, TextObject) and obj.text == "A1 B1"
+    assert window.panel("image").from_clipboard.isEnabled()
+    window.panel("image").from_clipboard.click()
+    assert isinstance(window.doc.objects[2], ImageObject)
+
+
+def test_ctrl_v_image_only_inserts_image(window):
+    _set_clipboard(image=_picture())
+    window.paste()
+    assert isinstance(window.doc.objects[1], ImageObject)
+
+
+def test_ctrl_v_text_only_inserts_text(window):
+    _set_clipboard(text="Nur Text")
+    window.paste()
+    assert window.doc.objects[1].text == "Nur Text"
+
+
+def test_repeated_text_paste_is_offset_like_objects(window):
+    QApplication.clipboard().setText("Hallo")
+    for _ in range(3):
+        window.paste()
+    area = window._area
+    xs = [(o.x_mm, o.y_mm) for o in window.doc.objects[1:]]
+    assert xs == [pytest.approx((area.x + 2 * i, area.y + 2 * i), abs=0.01) for i in range(3)]
+    QApplication.clipboard().setText("Neu")                 # neuer Inhalt: wieder links oben
+    window.paste()
+    assert (window.doc.objects[4].x_mm, window.doc.objects[4].y_mm) == \
+        pytest.approx((area.x, area.y), abs=0.01)
+
+
+def test_copied_image_leaves_no_text_on_the_system_clipboard(window, tmp_path):
+    _insert_file(window, _file(tmp_path))
+    window.copy_selected()
+    mime = QApplication.clipboard().mimeData()
+    assert mime.hasFormat(MIME_OBJECTS) and not mime.hasText()
+
+
+class _SpyMime(QMimeData):
+    """Zwischenablage, die mitschreibt, ob ihre Daten gelesen werden."""
+
+    def __init__(self):
+        super().__init__()
+        self.reads = []
+        self.setText("Text")
+
+    def text(self):
+        self.reads.append("text")
+        return super().text()
+
+    def imageData(self):
+        self.reads.append("image")
+        return super().imageData()
+
+    def urls(self):
+        self.reads.append("urls")
+        return super().urls()
+
+
+def test_edit_actions_do_not_read_clipboard_data(window, monkeypatch):
+    from PySide6.QtGui import QClipboard
+    spy = _SpyMime()
+    monkeypatch.setattr(QClipboard, "mimeData", lambda self, *args: spy)
+    window._clipboard_changed()                             # einmal beim Ändern: ohne Daten
+    spy.reads.clear()
+    window.canvas.set_selection([0])
+    for _ in range(3):
+        window._update_edit_actions()
+        window.nudge(0.1, 0)                                # jeder Schritt prüft die Knöpfe
+    assert window.shortcut_actions["edit.paste"].isEnabled()
+    assert spy.reads == []
+
+
+# --- Ablegen ------------------------------------------------------------------------
+def _point(win, x_mm, y_mm):
+    return win.canvas._view_point(x_mm * MM, y_mm * MM)
+
+
+def test_dropped_file_lands_at_drop_point(window, tmp_path):
+    mime = QMimeData()
+    mime.setUrls([QUrl.fromLocalFile(str(_file(tmp_path)))])
+    _drop(window.canvas, mime, _point(window, 30, 25))
+    obj = window.doc.objects[1]
+    rect = layout.exact_rect(obj, window.rendered[1])
+    assert (rect.cx, rect.cy) == pytest.approx((30, 25), abs=0.2)
+    assert window.canvas.selection() == [1]
+
+
+def test_dropped_image_data_is_inserted(window):
+    mime = QMimeData()
+    mime.setImageData(_qimage(_picture()))
+    _drop(window.canvas, mime, _point(window, 30, 20))
+    assert isinstance(window.doc.objects[1], ImageObject)
+
+
+def test_dropping_several_files_offsets_each_by_2_mm(window, tmp_path):
+    mime = QMimeData()
+    mime.setUrls([QUrl.fromLocalFile(str(_file(tmp_path, name=n))) for n in ("a.png", "b.png")])
+    _drop(window.canvas, mime, _point(window, 30, 25))
+    first, second = window.doc.objects[1:]
+    assert (second.x_mm - first.x_mm, second.y_mm - first.y_mm) == pytest.approx((2, 2))
+    assert window.canvas.selection() == [1, 2]
+
+
+def test_dropped_pdf_asks_for_the_page_after_the_drop(window, tmp_path):
+    asked = []
+    window.ask_pdf_page = lambda path, count: asked.append(count) or 2
+    mime = QMimeData()
+    mime.setUrls([QUrl.fromLocalFile(str(_pdf(tmp_path)))])
+    _drop(window.canvas, mime, _point(window, 30, 25), process=False)
+    assert asked == [] and len(window.doc.objects) == 1     # kein Dialog im Ablegen
+    del mime                                               # Daten sind schon kopiert
+    QTest.qWait(0)
+    assert asked == [2] and window.doc.objects[1].page == 2
+
+
+def test_dropped_unsupported_file_shows_message(window, tmp_path):
+    path = tmp_path / "notiz.txt"
+    path.write_text("x")
+    mime = QMimeData()
+    mime.setUrls([QUrl.fromLocalFile(str(path))])
+    _drop(window.canvas, mime, _point(window, 30, 20))
+    assert len(window.doc.objects) == 1 and "Dateityp" in _status(window)
+
+
+# --- Bild-Panel: Umwandlung, Größe --------------------------------------------------
+def test_panel_shows_selected_image(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    panel = win.panel("image")
+    assert panel.source.text() == "code.png"
+    assert panel.line.isChecked() and panel.threshold.value() == 128
+    assert panel.threshold_value.value() == 128
+    assert panel.crop.isChecked() and panel.keep_ratio.isChecked() and not panel.invert.isChecked()
+    assert not panel.position.spins["w"].isReadOnly()        # Größe immer änderbar
+
+
+def test_threshold_changes_image_and_is_undoable(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path, _picture(gray=150))
+    assert _ink(win, 1) == 0                                 # Grau 150 > Schwelle 128
+    win.panel("image").threshold_value.setValue(200)
+    win.render_now()
+    assert win.doc.objects[1].threshold == 200 and _ink(win, 1) > 0
+    win.undo()
+    assert win.doc.objects[1].threshold == 128 and win.panel("image").threshold.value() == 128
+
+
+def test_dragging_the_threshold_slider_is_one_step(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    slider = win.panel("image").threshold
+    slider.setSliderDown(True)
+    for value in (140, 160, 180):
+        slider.setValue(value)
+    slider.setSliderDown(False)
+    assert win.doc.objects[1].threshold == 180
+    assert win.panel("image").threshold_value.value() == 180
+    win.undo()
+    assert win.doc.objects[1].threshold == 128
+
+
+def test_invert_and_photo_change_the_image(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path, _picture(gray=100))
+    panel = win.panel("image")
+    line = win.rendered[1].image.tobytes()
+    panel.invert.click()
+    win.render_now()
+    assert win.doc.objects[1].invert and win.rendered[1].image.tobytes() != line
+    panel.invert.click()
+    win.render_now()
+    ink = _ink(win, 1)
+    panel.photo.click()
+    win.render_now()
+    assert win.doc.objects[1].mode == "photo" and 0 < _ink(win, 1) < ink   # Grau gerastert
+    win.undo()
+    assert win.doc.objects[1].mode == "line" and panel.line.isChecked()
+
+
+def test_crop_off_shows_whole_image_in_place(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    before = win.doc.objects[1]
+    win.panel("image").crop.click()
+    obj = win.doc.objects[1]
+    assert obj.crop is None and (obj.w_mm, obj.h_mm) == pytest.approx((300 / MM, 150 / MM))
+    assert obj.x_mm == pytest.approx(before.x_mm - 30 / MM, abs=0.01)
+    win.undo()
+    assert win.doc.objects[1].crop == (30, 30, 270, 120)
+
+
+def test_original_size_and_keep_ratio(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path, w_mm=40.0, h_mm=40.0, keep_ratio=False)
+    panel = win.panel("image")
+    panel.refresh()
+    assert not panel.keep_ratio.isChecked()
+    panel.keep_ratio.click()
+    obj = win.doc.objects[1]
+    assert obj.keep_ratio and (obj.w_mm, obj.h_mm) == pytest.approx((40, 15))
+    panel.original.click()
+    obj = win.doc.objects[1]
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((240 / MM, 90 / MM))
+    win.undo()
+    assert win.doc.objects[1].w_mm == pytest.approx(40)
+
+
+def test_width_field_keeps_ratio(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    win.panel("image").position.spins["w"].setValue(40)
+    obj = win.doc.objects[1]
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((40, 15))
+    win.doc.objects[1].keep_ratio = False
+    win.panel("image").position.spins["h"].setValue(20)
+    obj = win.doc.objects[1]
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((40, 20))
+
+
+# --- Auswahl, Schreibmodus, Layout --------------------------------------------------
+def test_selection_switches_between_text_and_image_panel(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    win.canvas.set_selection([0])
+    assert win.panels.currentWidget() is win.panel("text")
+    assert win.panel("image").index is None
+    win.canvas.set_selection([1])
+    assert win.panels.currentWidget() is win.panel("image")
+    assert win.tool_actions["image"].isChecked() and win.panel("text").index is None
+    win.tool_actions["layout"].trigger()
+    win.canvas.set_selection([0, 1])
+    assert win.panels.currentWidget() is win.panel("layout")
+
+
+def test_clicking_an_image_shows_image_panel(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    win.canvas.set_selection([])
+    win.tool_actions["paper"].trigger()
+    _click(win.canvas, win.canvas.view_rect(1).center())
+    assert win.canvas.selection() == [1]
+    assert win.panels.currentWidget() is win.panel("image")
+
+
+def test_double_click_and_f2_on_image_do_not_start_edit_mode(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    _double_click(win.canvas, win.canvas.view_rect(1).center())
+    assert not win.edit_session.active and win.canvas.editing() is None
+    assert not win.shortcut_actions["text.start_edit"].isEnabled()
+    win.edit_selected()
+    assert not win.edit_session.active
+
+
+def test_undo_with_image_and_text_keeps_panels_working(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    win.canvas.set_selection([0])
+    win.delete_selected()                                    # Bild rutscht auf Platz 0
+    win.canvas.set_selection([0])
+    assert win.panel("image").index == 0
+    win.undo()
+    win.undo()
+    assert [type(o) for o in win.doc.objects] == [TextObject]
+
+
+def test_layout_same_height_for_text_and_image(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    win.canvas.set_selection([0, 1])
+    win.match_selected("height")
+    text, image = (layout.exact_rect(o, r) for o, r in zip(win.doc.objects, win.rendered))
+    assert image.h == pytest.approx(text.h, abs=0.01)
+    assert image.w / image.h == pytest.approx(240 / 90, abs=0.01)
+
+
+def test_rotate_and_reorder_images(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    before = layout.exact_rect(win.doc.objects[1], win.rendered[1])
+    win.rotate_selected(90)
+    obj = win.doc.objects[1]
+    rect = layout.exact_rect(obj, win.rendered[1])
+    assert obj.rotation == 90 and (rect.w, rect.h) == pytest.approx((before.h, before.w), abs=0.01)
+    win.reorder_selected(-1)
+    assert isinstance(win.doc.objects[0], ImageObject) and win.canvas.selection() == [0]
+
+
+@pytest.mark.parametrize("handle", ["br", "r", "b"])
+def test_handles_keep_image_ratio(qtbot, tmp_path, handle):
+    win = _with_image(qtbot, tmp_path)
+    canvas = win.canvas
+    point = canvas.handle_points(1)[handle]
+    shift = 10 * canvas.px_per_mm()
+    _drag(canvas, point, point + QPointF(shift if "r" in handle else 0,
+                                         shift if "b" in handle else 0))
+    obj = win.doc.objects[1]
+    assert obj.w_mm / obj.h_mm == pytest.approx(240 / 90, rel=0.01)
+    assert obj.w_mm > 240 / MM + 5
+
+
+def test_edge_without_keep_ratio_distorts(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path, keep_ratio=False)
+    canvas = win.canvas
+    point = canvas.handle_points(1)["r"]
+    _drag(canvas, point, point + QPointF(10 * canvas.px_per_mm(), 0))
+    obj = win.doc.objects[1]
+    assert obj.w_mm == pytest.approx(240 / MM + 10, abs=0.2)
+    assert obj.h_mm == pytest.approx(90 / MM, abs=0.01)
+
+
+def test_resize_preview_keeps_ratio_at_the_edge(qtbot, tmp_path):
+    win = _with_image(qtbot, tmp_path)
+    canvas = win.canvas
+    point = canvas.handle_points(1)["r"]
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, point, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, point + QPointF(30, 0), LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, point + QPointF(60, 0), LEFT)
+    frame = canvas.objects[1].frame()
+    assert frame.width() / frame.height() == pytest.approx(240 / 90, rel=0.01)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, point + QPointF(60, 0),
+          Qt.MouseButton.NoButton)
+
+
+@pytest.mark.parametrize("orientation, rotation", [("vertical", 0), ("vertical", 90),
+                                                   ("horizontal", 0), ("horizontal", 270)])
+@pytest.mark.parametrize("handle", ["tl", "t", "tr", "r", "br", "b", "bl", "l"])
+def test_image_does_not_jump_after_releasing_a_handle(qtbot, tmp_path, handle, orientation,
+                                                      rotation):
+    """Vorschau beim Ziehen = Rahmen nach dem Loslassen, an allen Anfassern – bis auf das
+    Einrasten der gezogenen Kanten auf 0,1 mm (``to_grid``) und ½ Druckpunkt Rundung."""
+    win = _window(qtbot, Document("62", length_mm=60, orientation=orientation,
+                                  objects=[TextObject("Eins", size_pt=14, x_mm=4, y_mm=4)]))
+    _insert_file(win, _file(tmp_path))
+    win.doc.objects[1].rotation = rotation
+    win.render_now()
+    canvas = win.canvas
+    point = canvas.handle_points(1)[handle]
+    centre = canvas.view_rect(1).center()
+    step = 3.3 * canvas.px_per_mm()
+    sign = lambda d: (d > 1) - (d < -1)                        # noqa: E731
+    end = point + QPointF(sign(point.x() - centre.x()) * step,
+                          sign(point.y() - centre.y()) * step)
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, point, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, (point + end) / 2, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT)
+    preview = canvas.objects[1].frame()
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
+    win.render_now()
+    after = layout.exact_rect(win.doc.objects[1], win.rendered[1])     # Rahmen im Modell, mm
+    assert max(after.w, after.h) > 240 / MM + 3                # gewachsen
+    for a, b in ((after.x, preview.left()), (after.y, preview.top()),
+                 (after.right, preview.right()), (after.bottom, preview.bottom())):
+        assert a * MM == pytest.approx(b, abs=0.1 * MM + 0.5)
diff --git a/tests/gui/test_gui_layout.py b/tests/gui/test_gui_layout.py
index a311bdb..3b2b8ec 100644
--- a/tests/gui/test_gui_layout.py
+++ b/tests/gui/test_gui_layout.py
@@ -63,8 +63,8 @@ def _frames(window):
 
 
 # --- Reiter -----------------------------------------------------------------------
-def test_layout_tool_follows_text(window):
-    assert [tool.key for tool in TOOLS][:3] == ["paper", "text", "layout"]
+def test_layout_tool_follows_text_and_image(window):
+    assert [tool.key for tool in TOOLS][:4] == ["paper", "text", "image", "layout"]
     window.tool_actions["layout"].trigger()
     assert window.panels.currentWidget() is _panel(window)
 
diff --git a/tests/test_image_object.py b/tests/test_image_object.py
index b1115a8..12ca34c 100644
--- a/tests/test_image_object.py
+++ b/tests/test_image_object.py
@@ -83,6 +83,23 @@ def test_repr_leaves_out_png_bytes():
     assert "png=" not in repr(_image()) and "test.png" in repr(_image())
 
 
+def test_limit_resolution_after_shrinking_keeps_natural_size_and_crop():
+    obj = ImageObject.from_image(_source(1200, 600), 300, "foto.jpg", crop=(0, 0, 600, 600))
+    natural = obj.natural_mm()
+    obj.w_mm, obj.h_mm = obj.w_mm / 4, obj.h_mm / 4          # eingepasst: 1200 dpi
+    limited = obj.limit_resolution()
+    assert _decoded(limited).size == (600, 300)               # höchstens 600 dpi
+    assert limited.crop == (0, 0, 300, 300) and limited.dpi == pytest.approx(150)
+    assert limited.natural_mm() == pytest.approx(natural)     # „Originalgröße“ bleibt 1:1
+    assert (limited.w_mm, limited.h_mm) == (obj.w_mm, obj.h_mm)
+    assert obj.limit_resolution().limit_resolution().png == limited.png
+
+
+def test_limit_resolution_leaves_fine_images_alone():
+    obj = _image(w_mm=25.4, h_mm=12.7)                        # 600 dpi: noch in Grenzen
+    assert obj.limit_resolution() is obj
+
+
 def test_document_holds_text_and_images():
     doc = Document("62", objects=[TextObject(""), _image()])
     assert not doc.is_empty()
diff --git a/tests/test_image_place.py b/tests/test_image_place.py
new file mode 100644
index 0000000..7e6416a
--- /dev/null
+++ b/tests/test_image_place.py
@@ -0,0 +1,135 @@
+"""Bild-Objekt einfügen und einstellen (Etappe 3d-2a, ohne Qt): Größe 1:1, Platz beim
+Einfügen, Zuschnitt umschalten, Seitenverhältnis."""
+import pytest
+from PIL import Image
+
+from labelwerk import files, layout
+from labelwerk.document import Document, ImageObject
+from labelwerk.imaging import MAX_PIXELS
+from labelwerk.layout import Rect
+
+
+def _image(w=600, h=300, dpi=300, crop=None, **kw) -> ImageObject:
+    obj = ImageObject.from_image(Image.new("RGB", (w, h), "white"), dpi, "a.png", crop=crop)
+    for key, value in kw.items():
+        setattr(obj, key, value)
+    return obj
+
+
+# --- Modell: Auflösung, Ausschnitt, Größe 1:1 -----------------------------------------
+def test_from_image_keeps_dpi_for_one_to_one():
+    obj = _image(dpi=150)
+    assert obj.dpi == 150
+    assert obj.box() == (0, 0, 600, 300)
+    assert obj.natural_mm() == pytest.approx((101.6, 50.8))
+
+
+def test_natural_size_follows_crop():
+    obj = _image(crop=(60, 30, 360, 180))
+    assert obj.box() == (60, 30, 360, 180)
+    assert obj.natural_mm() == pytest.approx((25.4, 12.7))
+
+
+def test_limited_image_keeps_its_print_size():
+    big = ImageObject.from_image(Image.new("RGB", (2 * MAX_PIXELS, 100), "white"), 300, "a.png")
+    assert big.dpi == pytest.approx(150)
+    assert big.natural_mm() == pytest.approx((big.w_mm, big.h_mm))
+
+
+def test_page_count_of_pdf(tmp_path):
+    path = tmp_path / "zwei.pdf"
+    pages = [Image.new("RGB", (100, 100), "white") for _ in range(2)]
+    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=72)
+    assert files.page_count(path) == 2
+
+
+def test_page_count_of_unreadable_pdf_is_a_clear_error(tmp_path):
+    path = tmp_path / "kaputt.pdf"
+    path.write_bytes(b"kein pdf")
+    with pytest.raises(ValueError, match="kann nicht gelesen werden"):
+        files.page_count(path)
+
+
+# --- Einfügen: Platz und Größe -------------------------------------------------------
+AREA = Rect(1.5, 1.0, 59.0, 38.0)          # z. B. 62 mm × 40 mm, feste Länge
+
+
+def test_insert_frame_centres_image_one_to_one():
+    rect, factor = layout.insert_frame(Document("62", length_mm=40), "QL-600", AREA, (20, 10))
+    assert factor == 1
+    assert (rect.w, rect.h) == (20, 10)
+    assert (rect.cx, rect.cy) == pytest.approx((AREA.cx, AREA.cy))
+
+
+def test_insert_frame_shrinks_large_images_proportionally():
+    rect, factor = layout.insert_frame(Document("62", length_mm=40), "QL-600", AREA, (118, 19))
+    assert factor == pytest.approx(0.5)
+    assert (rect.w, rect.h) == pytest.approx((59, 9.5))
+    assert (rect.x, rect.cy) == pytest.approx((AREA.x, AREA.cy))
+
+
+def test_insert_frame_at_point_stays_inside_area():
+    doc = Document("62", length_mm=40)
+    rect, _ = layout.insert_frame(doc, "QL-600", AREA, (20, 10), at=(30, 20))
+    assert (rect.cx, rect.cy) == pytest.approx((30, 20))
+    rect, _ = layout.insert_frame(doc, "QL-600", AREA, (20, 10), at=(58, 0))
+    assert (rect.right, rect.y) == pytest.approx((AREA.right, AREA.y))
+
+
+def test_insert_frame_on_growing_tape_only_limits_across():
+    doc = Document("62", length_mm=None)                     # Endlos, automatische Länge
+    area = Rect(1.5, 1.0, 59.0, 10.0)
+    rect, factor = layout.insert_frame(doc, "QL-600", area, (40, 80))
+    assert factor == 1 and (rect.w, rect.h) == (40, 80)
+    assert rect.y == pytest.approx(area.y)                   # nicht vor den Anfang
+    assert rect.cx == pytest.approx(area.cx)
+    rect, factor = layout.insert_frame(doc, "QL-600", area, (40, 5000))
+    assert factor < 1 and rect.h < 1000                      # höchstens die größte Länge
+
+
+# --- Zuschnitt umschalten: Maßstab und Lage des Inhalts bleiben ------------------------
+def test_set_crop_keeps_scale_and_content_in_place():
+    obj = _image(x_mm=10, y_mm=5)                            # 50,8 × 25,4 mm
+    cropped = layout.set_crop(obj, (60, 30, 360, 180))
+    assert cropped.crop == (60, 30, 360, 180)
+    assert (cropped.w_mm, cropped.h_mm) == pytest.approx((25.4, 12.7))
+    assert (cropped.x_mm, cropped.y_mm) == pytest.approx((15.08, 7.54))
+    back = layout.set_crop(cropped, None)
+    assert back.crop is None
+    assert (back.x_mm, back.y_mm, back.w_mm, back.h_mm) == pytest.approx((10, 5, 50.8, 25.4))
+    assert obj.crop is None                                  # Original bleibt
+
+
+@pytest.mark.parametrize("rotation", [90, 180, 270])
+def test_set_crop_of_rotated_image_keeps_content_in_place(rotation):
+    obj = _image(x_mm=10, y_mm=5, rotation=rotation)
+    back = layout.set_crop(layout.set_crop(obj, (60, 30, 360, 180)), None)
+    assert (back.x_mm, back.y_mm) == pytest.approx((10, 5))
+    cropped = layout.set_crop(obj, (0, 0, 300, 150))         # linke obere Hälfte
+    w, h = 25.4, 12.7
+    # wo die linke obere Ecke des Bilds nach dem Drehen liegt, bleibt der Ausschnitt
+    expected = {90: (10 + 25.4 - h, 5), 180: (10 + 50.8 - w, 5 + 25.4 - h),
+                270: (10, 5 + 50.8 - w)}[rotation]
+    assert (cropped.x_mm, cropped.y_mm) == pytest.approx(expected)
+
+
+# --- Originalgröße, Seitenverhältnis, Größe im Panel ---------------------------------
+def test_original_size_is_one_to_one_and_keeps_corner():
+    obj = _image(x_mm=3, y_mm=4, w_mm=10, h_mm=30, crop=(0, 0, 300, 300))
+    original = layout.original_size(obj)
+    assert (original.x_mm, original.y_mm, original.w_mm, original.h_mm) == \
+        pytest.approx((3, 4, 25.4, 25.4))
+
+
+def test_keep_ratio_on_restores_ratio_from_width():
+    obj = _image(w_mm=40, h_mm=40, keep_ratio=False)          # verzerrt (2:1-Bild)
+    kept = layout.set_keep_ratio(obj, True)
+    assert kept.keep_ratio and (kept.w_mm, kept.h_mm) == pytest.approx((40, 20))
+    free = layout.set_keep_ratio(kept, False)
+    assert not free.keep_ratio and (free.w_mm, free.h_mm) == (kept.w_mm, kept.h_mm)
+
+
+@pytest.mark.parametrize("key, value, expected", [("w", 20, (2, 3, 20, 5)),
+                                                  ("h", 20, (2, 3, 80, 20))])
+def test_proportional_keeps_corner_and_ratio(key, value, expected):
+    assert layout.proportional(Rect(2, 3, 40, 10), key, value) == Rect(*expected)
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index a67a336..88295e8 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -15,7 +15,8 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.
 - Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
 - Direkt auf dem Etikett schreiben (Etappe 3d-1b): Schreibmodus (Text anlegen + Klick bzw. Doppelklick, Esc/Klick daneben beendet), Schreibmarke/Markierung aus dem Kern-Zeilensatz, Markieren mit Maus und Tastatur, eine Bearbeitung = ein Rückgängig-Schritt, Rahmen wächst an der Kante der Textposition; Feld INHALT entfällt.
-- 1193 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Bild-Objekt (Etappe 3d-2a): Werkzeug Bild – aus Datei (PNG/JPG/GIF/BMP/WebP/SVG/PDF-Seite), Zwischenablage, Ablegen; 1:1, automatisch zugeschnitten, zu große eingepasst; Umwandlung Strich/Foto, Schwelle, Umkehren, Zuschnitt, Originalgröße, Seitenverhältnis; Strg+V: Objekte (MIME application/x-labelwerk-objects) › lokale Dateien › Text als Textrahmen › Bild.
+- 1309 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -39,7 +40,7 @@ src/labelwerk/
   files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
               crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
               load_image(path, page) -> (RGB-Bild, dpi) für Bild-Objekte (PNG/JPG/GIF/BMP/WebP/PDF, Transparenz → weiß, EXIF-Lage);
-              crop_box(img, dpi, ink) -> (l, t, r, b) | None, dieselbe Logik wie crop() (Bilder: ink=NOT_WHITE)
+              crop_box(img, dpi, ink) -> (l, t, r, b) | None, dieselbe Logik wie crop() (Bilder: ink=NOT_WHITE); page_count(path) (PDF-Seitenwahl)
   imaging.py  Bilder ohne Qt: to_layers(img, mode line|photo, threshold, invert) -> {"black": Bild "1"} (später "red" für QL-8xx),
               on_white, to_8bit (16-Bit-Graustufen skalieren), limit_size (höchstens 600 dpi bzw. 6000 px längste Seite,
               Druckgröße bleibt); Foto: Gammakurve photo_curve (Weiß/Schwarz fest), dann Floyd-Steinberg
@@ -49,24 +50,36 @@ src/labelwerk/
   document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit);
               TextObject: Position x_mm/y_mm (None = mittig wie bisher), Rahmen w_mm/h_mm (mit fit), Drehen rotation 0/90/180/270
               ImageObject: png (Farboriginal), source/page/crop, Rahmen x/y/w/h_mm immer gesetzt, rotation, mode/threshold/invert,
-              keep_ratio; from_image(img, dpi, source, page, crop) setzt 1:1-Größe
+              keep_ratio, dpi (Auflösung der PNG-Bytes); from_image(img, dpi, source, page, crop) setzt 1:1-Größe;
+              box() (Ausschnitt in Pixeln), natural_mm() (Größe 1:1)
   settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic)
   media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
   layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
               growing_axis (Endlosband wächst mit), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
               Schreibmodus: to_object/from_object (Etikett ↔ ungedrehtes Objekt, Druckpunkte), anchor_after_edit/anchor_align
               Bilder wie Text mit fester Rahmengröße; keep_aspect (Anfasser mit keep_ratio); Schrift-Funktionen: TypeError bei Bildern
+              Bild einfügen/einstellen: insert_frame (Mitte bzw. Ablagepunkt, zu groß → proportional eingepasst, Endlosband
+              nur quer), set_crop (Maßstab und Lage des Inhalts bleiben), original_size, set_keep_ratio, proportional
   shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
               without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
   desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
   gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
     main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
-                    shortcut_actions (Aktions-ID → QAction); rendert über render.Renderer; leere Textrahmen entfallen beim Abwählen
-    tools.py        Werkzeug-Registry (Papier, Text, Layout; neue Werkzeuge als Eintrag)
-    panels/         Eigenschaften-Panels je Werkzeug (paper, text mit Bereich Position)
+                    shortcut_actions (Aktions-ID → QAction); rendert über render.Renderer; leere Textrahmen entfallen beim Abwählen;
+                    Bilder einfügen (insert_image_files, paste_image, Ablegen; Dialoge ask_image_file/ask_pdf_page ersetzbar),
+                    Strg+V nach Zwischenablage des Systems (eigene Kopie › Dateien › Text › Bild; Stand beim Ändern gemerkt,
+                    Daten erst beim Einfügen gelesen); Auswahl zeigt Panel der Objektart
+    tools.py        Werkzeug-Registry (Papier, Text, Bild, Layout; neue Werkzeuge als Eintrag)
+    panels/         Eigenschaften-Panels je Werkzeug (paper, text und image mit Bereich Position)
+    panels/image.py Reiter Bild: Aus Datei/Aus Zwischenablage, Quelle, Strich/Foto, Schwelle (Regler = ein Schritt), Umkehren,
+                    Zuschnitt (Fallback ohne Inhalt: ganzes Bild + Hinweis), Originalgröße 1:1, Seitenverhältnis, Position
+    image_import.py Bilder beschaffen: load (SVG per QSvgRenderer bei 300 dpi, Maße mit Einheit selbst gelesen: svg_size; sonst files.load_image), page_count,
+                    mime_image/mime_files/mime_text (Zwischenablage, Ablegen; ohne Auflösung 300 dpi), MIME_OBJECTS
     panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
     panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
     canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
+                    Ablegen von Dateien/Bilddaten (Daten im dropEvent kopiert, Signal dropped danach, mm); Anfasser-Vorschau mit
+                    keep_aspect (Bild, dieselbe Regel wie layout.resize: fest ist, was der Anfasser sagt)
                     Schreibmodus: zeichnet Rahmen/Schreibmarke/Markierung (set_edit_marks), meldet Klicks hinein (edit_*)
     text_edit_mode.py TextEditSession: Schreibmodus – Editor des Text-Panels als unsichtbarer Eingabepuffer (Fokus, IME),
                     Klick → Position über TextLayout.hit, Editor → Schreibmarke/Markierung, Auf/Ab nach Etikettzeilen,
@@ -114,7 +127,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Etappe 3d-2 Werkzeug ‚Bild‘ (Roadmap 0/5) als neuer Eintrag in `gui/tools.py`, Objekt im selben Modell wie Text.
+Nächste Schritte: Etappe 3d-2b Bildschirmfoto (XDG-Portal), danach 3d-2c Symbole/ClipArt (Roadmap 0/5).
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -131,7 +144,7 @@ Umsetzung:
 - GUI bleibt dünn: Logik, die testbar ist, gehört in den Kern
 
 ## Roadmap danach
-0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2 Bild · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
+0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto · 3d-2c Symbole/ClipArt · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
 1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
 2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
 3. Barcodes und QR-Codes
diff --git a/README.md b/README.md
index f1ec5a1..21024e9 100644
--- a/README.md
+++ b/README.md
@@ -45,7 +45,7 @@ labelwerk-gui
 labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entfernt den Eintrag wieder
 ```
 
-Aufbau wie im P-touch Editor: Werkzeugleiste (Papier, Text, Layout), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.
+Aufbau wie im P-touch Editor: Werkzeugleiste (Papier, Text, Bild, Layout), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.
 
 Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil); gespeichert in `~/.config/labelwerk/settings.json`.
 
@@ -53,6 +53,8 @@ Text: Geschrieben wird direkt auf dem Etikett. Mit dem Knopf „A“ (Text anleg
 
 Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste (oder im Reiter „Text“ ohne Auswahl) und einem Klick aufs Etikett einen Rahmen anlegen – bleibt er leer, verschwindet er wieder, sobald man den Schreibmodus verlässt. Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus; Lage und Größe landen auf 0,1 mm wie in den Feldern), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.
 
+Bild: Im Reiter „Bild“ fügt „Aus Datei …“ (Strg+Umschalt+I) PNG, JPG, GIF, BMP, WebP, SVG oder eine PDF-Seite ein (bei mehreren Seiten fragt ein Dialog nach der Seite), „Aus Zwischenablage“ ein kopiertes Bild. Bilddateien und Bilder lassen sich auch aufs Etikett ziehen (landen an der Ablagestelle). Strg+V auf der Arbeitsfläche fügt ein, was die Zwischenablage oben hat: in labelwerk kopierte Objekte, sonst kopierte Bilddateien (Dateimanager), sonst Text als neuen Textrahmen (auch wenn ein Bild dabei ist, etwa bei Tabellenzellen – das Bild fügt „Aus Zwischenablage“ ein), sonst ein Bild. Bilder kommen in Originalgröße 1:1 (aus der Auflösung der Datei, sonst 300 dpi) und automatisch zugeschnitten (Schnittmarken und weißer Rand fallen weg – z. B. bei der Internetmarke); zu große werden proportional eingepasst, die Statusleiste nennt den Faktor (Codes ggf. nicht mehr lesbar). Das Panel stellt die Umwandlung in Schwarz/Weiß ein: Strich (harte Schwelle – Codes, Schrift, Logos) oder Foto (Rasterpunkte), Schwelle (höher = mehr Schwarz), Umkehren; dazu Zuschnitt an/aus, Originalgröße 1:1 und Seitenverhältnis beibehalten (dann halten auch die Kanten-Anfasser das Verhältnis). Bilder lassen sich verschieben, skalieren, drehen, ausrichten, kopieren und rückgängig machen wie Text; ein Doppelklick auf ein Bild startet keinen Schreibmodus.
+
 Tastenkürzel (Standard):
 
 | Kürzel | Aktion |
@@ -61,8 +63,9 @@ Tastenkürzel (Standard):
 | Strg+Z · Strg+Umschalt+Z | Rückgängig · Wiederherstellen |
 | Strg++ · Strg+− · Strg+0 | Zoom größer · kleiner · echte Größe |
 | T · Esc | Werkzeug „Text anlegen“ · Auswahl-Pfeil (Arbeitsfläche) |
+| Strg+Umschalt+I | Bild einfügen … (Arbeitsfläche) |
 | F2 · Enter | Schreibmodus für den gewählten Text starten (Arbeitsfläche) |
-| Strg+X/C/V · Strg+D · Entf · Strg+A | Ausschneiden/Kopieren/Einfügen · Duplizieren · Löschen · alles wählen |
+| Strg+X/C/V · Strg+D · Entf · Strg+A | Ausschneiden/Kopieren/Einfügen (Objekte, Bild oder Text) · Duplizieren · Löschen · alles wählen |
 | Pfeiltasten · Umschalt+Pfeiltasten | verschieben um 0,1 mm · 1 mm |
 | Strg+L · Strg+R | 90° nach links · rechts drehen |
 | Strg+Bild↑ · Strg+Bild↓ | nach vorne · nach hinten |
@@ -82,6 +85,7 @@ document.py Etikett-Dokument (Etikett, Länge, Objekte)
 settings.py Einstellungen (JSON)
 fonts.py    Schriften (fontconfig)
 media.py    Medium prüfen (Statusabfrage des Druckers)
+imaging.py  Bilder: Schwarz/Weiß-Umwandlung (Strich/Foto), Größe begrenzen
 layout.py   Platzieren: Einrasten, Ausrichten, Größe angleichen, ragt hinaus
 shortcuts.py Tastenkürzel-Verzeichnis (Standard, Konflikte, Prüfung)
 gui/        PySide6-Oberfläche (nur Anzeige/Bearbeitung, kein Druckcode)
diff --git a/docs/superpowers/specs/2026-10-17-bild-objekt-design.md b/docs/superpowers/specs/2026-10-17-bild-objekt-design.md
index c636d62..d6ee0fc 100644
--- a/docs/superpowers/specs/2026-10-17-bild-objekt-design.md
+++ b/docs/superpowers/specs/2026-10-17-bild-objekt-design.md
@@ -29,9 +29,9 @@ Bildschirmfoto und Symbole (2b/2c), Bildbearbeitung (Freistellen, Retusche), Zus
   - `mode: "line" | "photo"` (Standard „line“), `threshold: int` 0–255 (Standard 128), `invert: bool`,
   - `keep_ratio: bool = True`.
   - `is_empty()` → False. `Document.objects: list[TextObject | ImageObject]`.
-- **Laden** (`files.py`, Qt-frei): `load_image(path, page=1) -> (Image RGB, dpi)` für PNG/JPG/GIF(erstes Bild)/BMP/WebP/PDF; Transparenz auf Weiß; 16-Bit-Graustufen werden auf 8 Bit skaliert (nicht abgeschnitten); DPI aus der Datei auf 0,01 gerundet, quer verschiedene DPI (Fax 204 × 98) → Höhe skaliert, Druckgröße stimmt. **SVG** rastert die GUI (QSvgRenderer, 300 dpi aus viewBox/Größe; 1 px = 1/96 in) und reicht PNG-Bytes weiter – der Kern bleibt Qt-frei. Sehr große Bilder werden beim Einfügen auf höchstens 600 dpi bezogen auf ihre Druckgröße bzw. 6000 px längste Seite verkleinert (Speicher).
+- **Laden** (`files.py`, Qt-frei): `load_image(path, page=1) -> (Image RGB, dpi)` für PNG/JPG/GIF(erstes Bild)/BMP/WebP/PDF; Transparenz auf Weiß; 16-Bit-Graustufen werden auf 8 Bit skaliert (nicht abgeschnitten); DPI aus der Datei auf 0,01 gerundet, quer verschiedene DPI (Fax 204 × 98) → Höhe skaliert, Druckgröße stimmt. **SVG** rastert die GUI (QSvgRenderer, 300 dpi; Größe aus `width`/`height` mit Einheit px/mm/cm/in/pt/pc nach CSS – 1 px = 1/96 in, selbst gelesen, weil Qt mit 90 dpi rechnet –, ohne Einheit aus Qts Größe/viewBox) und reicht PNG-Bytes weiter – der Kern bleibt Qt-frei. Sehr große Bilder werden beim Einfügen auf höchstens 600 dpi bezogen auf ihre Druckgröße bzw. 6000 px längste Seite verkleinert (Speicher).
 - **Automatischer Zuschnitt** beim Einfügen: `files.crop_box(img, dpi, ink) -> (l, t, r, b) | None` (dieselbe Logik wie `crop()` – Schnittmarken, Leerraum; `crop()` nutzt sie mit `ink=128` unverändert). Bilder: Transparenz zuerst auf Weiß, Inhalt ist alles „nicht weiß“ (`ink=NOT_WHITE` = 245), damit helle Fotos und gelbe Logos ganz bleiben; ohne Inhalt `None` → ganzes Bild. Ergebnis in `ImageObject.crop`. Panel-Schalter „Zuschnitt“ (an/aus = automatisch/ganzes Original).
-- **Größe beim Einfügen:** 1:1 aus der DPI-Angabe (ohne Angabe 300 dpi; PDF in Originalgröße). Passt das Bild nicht in den bedruckbaren Bereich, wird es proportional eingepasst (Hinweis in der Statusleiste „Bild auf N % verkleinert – Codes ggf. nicht mehr lesbar“). Position: Klick-/Ablagepunkt bzw. Mitte des bedruckbaren Bereichs.
+- **Größe beim Einfügen:** 1:1 aus der DPI-Angabe (ohne Angabe 300 dpi; PDF in Originalgröße). Passt das Bild nicht in den bedruckbaren Bereich, wird es proportional eingepasst (Hinweis in der Statusleiste „Bild auf N % verkleinert – Codes ggf. nicht mehr lesbar“, nie „0 %“, sondern „< 1 %“) und danach erneut auf 600 dpi bezogen auf die neue Druckgröße begrenzt (Größe 1:1 bleibt für „Originalgröße“). Position: Klick-/Ablagepunkt bzw. Mitte des bedruckbaren Bereichs.
 - **Umrechnung** (`imaging.py`, neu, Qt-frei): `to_layers(img, mode, threshold, invert) -> dict[str, Image "1"]` mit Ebene `"black"`; `mode="line"`: Graustufe → harte Schwelle; `"photo"`: Gammakurve `v' = 255 · (v/255) ** g` mit `g = 2 ** ((threshold − 128) / 64)` (höhere Schwelle → dunkler, 128 = unverändert; 0 und 255 bleiben fest – weißes Papier bekommt nie Punkte, Schwarz bleibt voll), dann Floyd-Steinberg. Schnittstelle für später `"red"` (Zweifarbdruck QL-8xx) dokumentiert, aber nicht gebaut.
 - **Rendern:** `render_object` kennt `ImageObject`: Ausschnitt → auf Rahmengröße in Druckpunkten skalieren (Lanczos mit `reducing_gap=2`: stark verkleinert erst ganzzahlig reduzieren – 1:1, vergrößert und bis 2× verkleinert unverändert exakt; bei `keep_ratio` kein Verzerren – Rahmen hat das Seitenverhältnis) → `to_layers` → Ebene „black“ als Objektbild (Tinte schwarz) → drehen wie Text. Ergebnis gecacht (Renderer). `RenderedObject.layout` = None.
 - **Platzier-Logik:** `layout` behandelt `ImageObject` wie Text mit fester Rahmengröße (move/resize/set_frame/rotate/align/match_size/maximize); Ecken skalieren proportional bei `keep_ratio`, Kanten verzerren nur ohne `keep_ratio` (mit `keep_ratio` wirken Kanten wie Ecken in einer Achse und halten das Verhältnis). Was fest bleibt, folgt allein aus dem Anfasser (`keep_aspect(old, new, handle)`, Vorschau und Ergebnis gleich): Ecke → gegenüberliegende Ecke, Kante → gegenüberliegende Kante, quer dazu die Mitte.
@@ -44,8 +44,8 @@ Bildschirmfoto und Symbole (2b/2c), Bildbearbeitung (Freistellen, Retusche), Zus
   - PDF mit mehreren Seiten: Seitenwahl im Dialog nach dem Öffnen (Spinbox, Vorgabe 1).
 - **Einfügen:**
   - Datei/Zwischenablage über das Panel → Bild in die Mitte des bedruckbaren Bereichs.
-  - **Strg+V auf der Arbeitsfläche:** liegt die interne Objekt-Zwischenablage oben (labelwerk-Markierung im System-Clipboard), werden Objekte eingefügt (wie bisher); sonst ein Bild aus der System-Zwischenablage; sonst Text → neuer Textrahmen mit diesem Text. Kopieren/Ausschneiden von Objekten setzt dafür einen eigenen MIME-Typ `application/x-labelwerk-objects` in die System-Zwischenablage.
-  - **Ziehen & Ablegen** von Bilddateien (und Bilddaten) auf die Arbeitsfläche → Bild an der Ablagestelle.
+  - **Strg+V auf der Arbeitsfläche** (Reihenfolge festgelegt): (1) liegt die interne Objekt-Zwischenablage oben (labelwerk-Markierung im System-Clipboard, bei leerer Zwischenablage die letzte Kopie), werden Objekte eingefügt (wie bisher, je 2 mm versetzt); (2) lokale Datei-URLs (Dateimanager) → wie „Aus Datei“, andere Dateitypen mit Meldung; (3) Text → neuer Textrahmen mit diesem Text (wiederholt eingefügt je 2 mm versetzt) – **Text gewinnt, wenn zugleich ein Bild dabei ist** (Tabellenzellen bringen ein Bild mit; das Bild bleibt über „Aus Zwischenablage“ erreichbar); (4) Bild; sonst nichts. Freigabe der Knöpfe aus dem beim Ändern der Zwischenablage gemerkten Stand (ohne Daten zu holen). Kopieren/Ausschneiden von Objekten setzt dafür einen eigenen MIME-Typ `application/x-labelwerk-objects` in die System-Zwischenablage.
+  - **Ziehen & Ablegen** von Bilddateien (und Bilddaten) auf die Arbeitsfläche → Bild an der Ablagestelle; mehrere Dateien je 2 mm versetzt. Die Daten werden im Ablegen kopiert und erst danach verarbeitet (PDF-Seitendialog nicht im `dropEvent`).
 - Auswahl eines Bildes zeigt das BILD-Panel (wie Text → TEXT). Doppelklick auf ein Bild: kein Schreibmodus (nichts).
 - Layout-Reiter, Drehen, Reihenfolge, Ausrichten, Kopieren/Einfügen, Rückgängig funktionieren für Bilder wie für Text.
 - Fehler (Datei unlesbar, kein Bild in der Zwischenablage, PDF-Seite fehlt): verständliche Meldung in der Statusleiste, kein Traceback.
diff --git a/src/labelwerk/document.py b/src/labelwerk/document.py
index 042a140..e009121 100644
--- a/src/labelwerk/document.py
+++ b/src/labelwerk/document.py
@@ -2,11 +2,11 @@
 from __future__ import annotations
 
 import io
-from dataclasses import dataclass, field
+from dataclasses import dataclass, field, replace
 
 from PIL import Image
 
-from .imaging import limit_size, on_white
+from .imaging import MAX_DPI, limit_size, on_white
 
 ORIENTATIONS = ("vertical", "horizontal")
 ALIGNMENTS = ("left", "center", "right", "justify")
@@ -104,6 +104,7 @@ class ImageObject:
     threshold: int = 128            # 0–255; höher = mehr Tinte
     invert: bool = False
     keep_ratio: bool = True         # Seitenverhältnis beibehalten (Ecken/Kanten skalieren gleich)
+    dpi: float = 300.0              # Auflösung von ``png`` – ergibt die Größe 1:1 (``natural_mm``)
 
     def __post_init__(self) -> None:
         if self.crop is not None:                # JSON liefert eine Liste
@@ -123,18 +124,43 @@ class ImageObject:
         """Bild 1:1 nach ``dpi`` (Größe des Ausschnitts ``crop``, sonst des ganzen Bilds).
 
         Transparenz wird weiß; sehr große Bilder werden begrenzt (``imaging.limit_size``) –
-        der Ausschnitt rechnet mit, die Druckgröße bleibt.
+        der Ausschnitt rechnet mit, die Druckgröße bleibt (``dpi`` = Auflösung danach).
         """
         l, t, r, b = crop if crop is not None else (0, 0, *img.size)
         mm = 25.4 / dpi                          # Druckgröße aus dem Original
-        rgb, _ = limit_size(on_white(img), dpi)
+        rgb, stored_dpi = limit_size(on_white(img), dpi)
         if crop is not None and rgb.size != img.size:
             fx, fy = rgb.width / img.width, rgb.height / img.height
             crop = (round(l * fx), round(t * fy), round(r * fx), round(b * fy))
-        buffer = io.BytesIO()
-        rgb.save(buffer, "PNG", compress_level=1)   # große Fotos rund 4× schneller
-        return cls(png=buffer.getvalue(), source=source, page=page, crop=crop,
-                   w_mm=(r - l) * mm, h_mm=(b - t) * mm)
+        return cls(png=_png(rgb), source=source, page=page, crop=crop,
+                   w_mm=(r - l) * mm, h_mm=(b - t) * mm, dpi=stored_dpi)
+
+    def limit_resolution(self) -> "ImageObject":
+        """Kopie mit höchstens ``MAX_DPI`` bezogen auf die jetzige Druckgröße (``w_mm``/
+        ``h_mm``) – z. B. nach dem Einpassen eines Handyfotos. Größe 1:1 (``natural_mm``) und
+        Ausschnitt rechnen mit; ein Bild in Grenzen kommt unverändert zurück (dasselbe Objekt)."""
+        l, t, r, b = self.box()
+        dpi = max((r - l) / self.w_mm, (b - t) / self.h_mm) * 25.4
+        if dpi <= MAX_DPI:
+            return self
+        img = self.image()
+        small, _ = limit_size(img, dpi)
+        fx, fy = small.width / img.width, small.height / img.height
+        crop = (None if self.crop is None
+                else (round(l * fx), round(t * fy), round(r * fx), round(b * fy)))
+        return replace(self, png=_png(small), crop=crop, dpi=self.dpi * fx)
+
+    def box(self) -> tuple[int, int, int, int]:
+        """Ausschnitt (l, t, r, b) in Pixeln – ohne ``crop`` das ganze Bild."""
+        if self.crop is not None:
+            return self.crop
+        with Image.open(io.BytesIO(self.png)) as img:   # liest nur den Kopf der Datei
+            return (0, 0, *img.size)
+
+    def natural_mm(self) -> tuple[float, float]:
+        """Größe 1:1 (Breite, Höhe in mm, ungedreht) des Ausschnitts aus ``dpi``."""
+        l, t, r, b = self.box()
+        return (r - l) * 25.4 / self.dpi, (b - t) * 25.4 / self.dpi
 
     def image(self) -> Image.Image:
         """Das Original als RGB-Bild."""
@@ -142,6 +168,13 @@ class ImageObject:
             return img.convert("RGB")
 
 
+def _png(img: Image.Image) -> bytes:
+    """Bild als PNG-Bytes (verlustfrei)."""
+    buffer = io.BytesIO()
+    img.save(buffer, "PNG", compress_level=1)    # große Fotos rund 4× schneller
+    return buffer.getvalue()
+
+
 @dataclass
 class Document:
     label_id: str = "62"
diff --git a/src/labelwerk/files.py b/src/labelwerk/files.py
index 6dbfbb3..2629fde 100644
--- a/src/labelwerk/files.py
+++ b/src/labelwerk/files.py
@@ -60,6 +60,19 @@ def _file_dpi(src: Image.Image) -> tuple[float, float]:
     return tuple(round(float(v), 2) or float(DPI) for v in dpi[:2])
 
 
+def page_count(path: str | Path) -> int:
+    """Seitenzahl einer PDF-Datei (für die Seitenwahl vor ``load_image``)."""
+    path = _checked(path, (), "PDF", 1)
+    with _readable(path):
+        import pypdfium2 as pdfium
+
+        pdf = pdfium.PdfDocument(path)
+        try:
+            return len(pdf)
+        finally:
+            pdf.close()
+
+
 def _checked(path: str | Path, suffixes: tuple[str, ...], allowed: str, page: int) -> Path:
     """Dateityp, Vorhandensein und Seitenzahl prüfen."""
     path = Path(path)
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index c7f1ffd..6b2b29e 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -1,5 +1,5 @@
 """Arbeitsfläche: Etikett in echter Größe und Form, Objekte (auswählen, ziehen, einrasten,
-an Anfassern skalieren, Text anlegen), mm-Lineale, Zoom, Längen-Anfasser.
+an Anfassern skalieren, Text anlegen, Bilder ablegen), mm-Lineale, Zoom, Längen-Anfasser.
 
 Schreibmodus (``gui.text_edit_mode``): Der bearbeitete Rahmen ist durchgezogen und ohne
 Anfasser; Schreibmarke und Markierung kommen als Lage in Druckpunkten vom Schreibmodus
@@ -16,6 +16,7 @@ from PySide6.QtWidgets import (QApplication, QGraphicsPixmapItem, QGraphicsRectI
                                QGraphicsScene, QGraphicsView)
 
 from .. import layout
+from . import image_import
 from ..labels import DPI, Label, format_mm, length_limits
 from ..layout import Rect
 from ..printer import DEFAULT_MODEL
@@ -61,11 +62,12 @@ class ObjectItem(QGraphicsPixmapItem):
     """
 
     def __init__(self, index: int, rendered: RenderedObject, pixmap: QPixmap, keep_ratio: bool,
-                 parent: QGraphicsRectItem):
+                 parent: QGraphicsRectItem, keep_aspect: bool = False):
         super().__init__(pixmap, parent)
         self.index = index
         self.rendered = rendered
         self.keep_ratio = keep_ratio     # Ecken skalieren die Schrift: Seitenverhältnis bleibt
+        self.keep_aspect = keep_aspect   # auch Kanten halten das Verhältnis (Bild)
         self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
         self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
         self.setPos(rendered.x, rendered.y)
@@ -107,6 +109,8 @@ class Canvas(QGraphicsView):
     edit_left = Signal()                       # Schreibmodus: Klick neben den Rahmen beendet ihn
     object_clicked = Signal(int)               # Klick auf ein Objekt (auch ein schon gewähltes)
     tool_changed = Signal(str)                 # Werkzeug: "select" | "text"
+    dropped = Signal(object, object, float, float)  # abgelegt: Dateien (list[Path]), Bild
+                                               # (PIL oder None), Ablagepunkt (mm, Leserichtung)
 
     def __init__(self, model: str = DEFAULT_MODEL):
         super().__init__()
@@ -117,6 +121,7 @@ class Canvas(QGraphicsView):
         self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
         self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
         self.viewport().setMouseTracking(True)             # Mauszeiger über den Anfassern
+        self.setAcceptDrops(True)                          # Bilder und Bilddateien ablegen
         min_len, max_len = length_limits(model)
         self.min_mm, self.max_mm = min_len / MM, max_len / MM
         self.zoom = START_ZOOM
@@ -159,12 +164,13 @@ class Canvas(QGraphicsView):
     def set_document(self, label: Label, size: tuple[int, int],
                      rendered: list[RenderedObject], orientation: str = "vertical",
                      area: Rect | None = None, keep_ratio: list[bool] | None = None,
-                     grow: str | None = None) -> None:
+                     grow: str | None = None, keep_aspect: list[bool] | None = None) -> None:
         """Etikett (physische Form) und die einzeln gerenderten Objekte darin anzeigen.
 
         ``size``: Etikett in Druckpunkten in Leserichtung (wie ``render.label_size``);
         ``area``: bedruckbarer Bereich in mm (Einrasten); ``keep_ratio`` je Objekt: Ecken
-        skalieren die Schrift (ohne feste Rahmengröße); ``grow``: Achse, in der das Etikett
+        skalieren die Schrift (ohne feste Rahmengröße); ``keep_aspect`` je Objekt: auch
+        Kanten halten das Seitenverhältnis (Bild); ``grow``: Achse, in der das Etikett
         mitwächst (``layout.growing_axis``) – dort rastet nur der Anfang ein. Die Szene ist immer in
         Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°, damit das Etikett in
         Leserichtung erscheint – die Objekte liegen in ``sheet``, das in Leserichtung zählt.
@@ -199,8 +205,9 @@ class Canvas(QGraphicsView):
         scene.addItem(self.sheet)
         self._pixmaps = {id(obj): (obj, self._pixmap(obj)) for obj in rendered}
         ratios = keep_ratio if keep_ratio is not None else [True] * len(rendered)
-        self.objects = [ObjectItem(i, obj, self._pixmaps[id(obj)][1], ratio, self.sheet)
-                        for i, (obj, ratio) in enumerate(zip(rendered, ratios))]
+        aspects = keep_aspect if keep_aspect is not None else [False] * len(rendered)
+        self.objects = [ObjectItem(i, obj, self._pixmaps[id(obj)][1], ratio, self.sheet, aspect)
+                        for i, (obj, ratio, aspect) in enumerate(zip(rendered, ratios, aspects))]
         self._show_edit_cursor()
         self._label_rect = Rect(0, 0, width / MM, height / MM)
         self._area = area if area is not None else self._label_rect
@@ -600,7 +607,8 @@ class Canvas(QGraphicsView):
         """Vorschau beim Ziehen an einem Anfasser: Bild gestreckt, gerendert wird beim Loslassen."""
         item = self.objects[self._grabbed]
         frame = resized_frame(self._start_frame, self._resize_key,
-                              self._reading(pos) + self._handle_offset, item.keep_ratio)
+                              self._reading(pos) + self._handle_offset, item.keep_ratio,
+                              item.keep_aspect)
         item.setPos(frame.topLeft())
         item.setTransform(QTransform.fromScale(frame.width() / item.rendered.w,
                                                frame.height() / item.rendered.h))
@@ -652,6 +660,34 @@ class Canvas(QGraphicsView):
     def label_height(self) -> float:
         return self.outline.path().boundingRect().height() if self.outline else 0.0
 
+    # --- Ablegen ----------------------------------------------------------
+    def _accepts(self, event) -> bool:
+        mime = event.mimeData()
+        return self.sheet is not None and (mime.hasImage() or any(
+            url.isLocalFile() for url in mime.urls()))
+
+    def dragEnterEvent(self, event) -> None:
+        if self._accepts(event):
+            event.acceptProposedAction()
+        else:
+            event.ignore()
+
+    def dragMoveEvent(self, event) -> None:
+        self.dragEnterEvent(event)          # nicht an die Szene: sie kennt keine Ablageziele
+
+    def dropEvent(self, event) -> None:
+        if not self._accepts(event):
+            event.ignore()
+            return
+        event.acceptProposedAction()
+        point = self._reading(event.position())
+        # Daten jetzt kopieren (QMimeData lebt nur während des Ablegens), verarbeiten erst
+        # danach: ein Dialog (PDF-Seite) im dropEvent hielte die Quelle des Ziehens fest
+        paths = image_import.mime_files(event.mimeData())
+        image = None if paths else image_import.mime_image(event.mimeData())
+        x, y = point.x() / MM, point.y() / MM
+        QTimer.singleShot(0, self, lambda: self.dropped.emit(paths, image, x, y))
+
     # --- Auswahlrahmen, Hilfslinien, Lineale ------------------------------
     def drawForeground(self, painter: QPainter, rect) -> None:
         painter.save()
@@ -762,11 +798,13 @@ class Canvas(QGraphicsView):
         painter.fillRect(0, 0, RULER, RULER, Qt.GlobalColor.white)
 
 
-def resized_frame(start: QRectF, key: str, point: QPointF, keep_ratio: bool) -> QRectF:
+def resized_frame(start: QRectF, key: str, point: QPointF, keep_ratio: bool,
+                  keep_aspect: bool = False) -> QRectF:
     """Rahmen nach Ziehen am Anfasser ``key`` auf ``point`` (Druckpunkte in Leserichtung).
 
     Die gegenüberliegende Ecke bzw. Kante bleibt stehen; mindestens 1 mm. ``keep_ratio``:
-    Ecken behalten das Seitenverhältnis (Schrift skalieren).
+    Ecken behalten das Seitenverhältnis (Schrift skalieren); ``keep_aspect``: Ecken und
+    Kanten wie beim Loslassen (``layout.keep_aspect``, Bild).
     """
     left, top, right, bottom = start.left(), start.top(), start.right(), start.bottom()
     if "l" in key:
@@ -777,6 +815,10 @@ def resized_frame(start: QRectF, key: str, point: QPointF, keep_ratio: bool) ->
         top = min(point.y(), bottom - _MIN_FRAME)
     if "b" in key:
         bottom = max(point.y(), top + _MIN_FRAME)
+    if keep_aspect:
+        old = Rect(start.x(), start.y(), start.width(), start.height())
+        new = layout.keep_aspect(old, Rect(left, top, right - left, bottom - top), key)
+        return QRectF(new.x, new.y, new.w, new.h)
     if keep_ratio and len(key) == 2:
         factor = max((right - left) / start.width(), (bottom - top) / start.height())
         w, h = start.width() * factor, start.height() * factor
diff --git a/src/labelwerk/gui/image_import.py b/src/labelwerk/gui/image_import.py
new file mode 100644
index 0000000..53dc2bf
--- /dev/null
+++ b/src/labelwerk/gui/image_import.py
@@ -0,0 +1,128 @@
+"""Bilder für das Werkzeug „Bild“ beschaffen: Datei, Zwischenablage, Ablegen.
+
+SVG rastert Qt (``QSvgRenderer``) – so bleibt der Kern Qt-frei; alle anderen Dateien lädt
+``files.load_image``. Bilder aus der Zwischenablage oder abgelegte Bilddaten haben keine
+verlässliche Auflösung und gelten als 300 dpi.
+"""
+from __future__ import annotations
+
+import io
+import re
+from pathlib import Path
+from xml.etree import ElementTree
+
+from PIL import Image
+from PySide6.QtCore import QBuffer, QIODevice, QMimeData, Qt
+from PySide6.QtGui import QImage, QPainter, QPixmap
+from PySide6.QtSvg import QSvgRenderer
+
+from .. import files
+from ..imaging import MAX_PIXELS, on_white
+from ..labels import DPI
+
+SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".pdf")
+ALLOWED = "PNG, JPG, GIF, BMP, WebP, SVG, PDF"  # für Meldungen
+FILE_FILTER = ("Bilder und PDF (" + " ".join(f"*{s} *{s.upper()}" for s in SUFFIXES) + ");;"
+               "Alle Dateien (*)")              # Großschreibung: Kameras, Windows
+CLIPBOARD = "Zwischenablage"                    # Quelle eines eingefügten Bilds
+DROPPED = "Abgelegtes Bild"
+MIME_OBJECTS = "application/x-labelwerk-objects"   # kopierte Objekte (Kennung der Kopie)
+SVG_DPI = 96                                    # SVG: 1 px = 1/96 in
+
+
+def page_count(path: Path) -> int:
+    """Seitenzahl (PDF), sonst 1 – Fehler wie beim Laden (``ValueError``, ``FileNotFoundError``)."""
+    return files.page_count(path) if Path(path).suffix.lower() == ".pdf" else 1
+
+
+def load(path: Path, page: int = 1) -> tuple[Image.Image, float]:
+    """Bild aus einer Datei: (RGB-Bild, dpi); SVG wird hier gerastert, der Rest im Kern.
+    Andere Dateitypen: ``ValueError`` mit allen möglichen Typen (samt SVG)."""
+    path = Path(path)
+    if path.suffix.lower() not in SUFFIXES:
+        raise ValueError(f"Dateityp nicht unterstützt: {path.suffix or path.name} – "
+                         f"möglich: {ALLOWED}")
+    if path.suffix.lower() == ".svg":
+        return load_svg(path)
+    return files.load_image(path, page)
+
+
+def load_svg(path: Path) -> tuple[Image.Image, float]:
+    """SVG bei 300 dpi auf Weiß rastern (Größe aus width/height samt Einheit, sonst Qts
+    Größe/viewBox; 1 px = 1/96 in); sehr große Zeichnungen gröber, höchstens
+    ``MAX_PIXELS`` auf der längsten Seite."""
+    if not path.exists():
+        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
+    renderer = QSvgRenderer(str(path))
+    size = renderer.defaultSize()
+    if not renderer.isValid() or size.isEmpty():
+        raise ValueError(f"Datei kann nicht gelesen werden: {path.name} (kein gültiges SVG)")
+    # Qt rechnet mm/in/pt mit 90 dpi – Maße mit Einheit deshalb selbst lesen (CSS: 96 px/in)
+    width, height = svg_size(path) or (size.width(), size.height())
+    dpi = min(DPI, MAX_PIXELS * SVG_DPI / max(width, height))
+    image = QImage(max(1, round(width * dpi / SVG_DPI)),
+                   max(1, round(height * dpi / SVG_DPI)), QImage.Format.Format_RGB32)
+    image.fill(Qt.GlobalColor.white)
+    painter = QPainter(image)
+    renderer.render(painter)
+    painter.end()
+    return to_pil(image), dpi
+
+
+_UNITS = {"": 1.0, "px": 1.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "pt": 96 / 72,
+          "pc": 16.0}                           # CSS-Pixel je Einheit (96 px = 1 in)
+_LENGTH = re.compile(r"\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z]*)\s*$")
+
+
+def svg_size(path: Path) -> tuple[float, float] | None:
+    """Breite und Höhe der Zeichnung in CSS-Pixeln (1/96 in) aus ``width``/``height`` des
+    Wurzelelements, mit Einheiten px/mm/cm/in/pt/pc; None, wenn eine Angabe fehlt, relativ
+    ist (%, em) oder die Datei sich nicht lesen lässt – dann zählt Qts Größe (viewBox)."""
+    try:
+        _, root = next(ElementTree.iterparse(path, events=("start",)))
+    except (ElementTree.ParseError, OSError, StopIteration):
+        return None
+    sizes = []
+    for name in ("width", "height"):
+        match = _LENGTH.match(root.get(name, ""))
+        if match is None or match[2].lower() not in _UNITS or float(match[1]) <= 0:
+            return None
+        sizes.append(float(match[1]) * _UNITS[match[2].lower()])
+    return sizes[0], sizes[1]
+
+
+def to_pil(image: QImage) -> Image.Image:
+    """QImage → RGB-Bild (Transparenz wird weiß)."""
+    buffer = QBuffer()
+    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
+    image.save(buffer, "PNG")
+    with Image.open(io.BytesIO(bytes(buffer.data()))) as img:
+        return on_white(img)
+
+
+def mime_image(mime: QMimeData | None) -> Image.Image | None:
+    """Bilddaten aus der Zwischenablage bzw. einem Ablegen, sonst None."""
+    if mime is None or not mime.hasImage():
+        return None
+    data = mime.imageData()
+    if isinstance(data, QPixmap):
+        data = data.toImage()
+    if not isinstance(data, QImage) or data.isNull():
+        return None
+    return to_pil(data)
+
+
+def mime_files(mime: QMimeData | None) -> list[Path]:
+    """Lokale Dateien aus einem Ablegen (Dateimanager)."""
+    if mime is None or not mime.hasUrls():
+        return []
+    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]
+
+
+def mime_text(mime: QMimeData | None) -> str:
+    """Text aus der Zwischenablage, wie ein Textrahmen ihn bekommt: Zeilenenden als „\\n“,
+    Tabulatoren als Leerzeichen, ohne Leerzeilen am Ende; leer ohne Text."""
+    if mime is None or not mime.hasText():
+        return ""
+    text = mime.text().replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
+    return text.rstrip("\n") if text.strip() else ""
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index d017d29..906803c 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -2,24 +2,28 @@
 from __future__ import annotations
 
 import copy
-from dataclasses import replace
+import uuid
+from dataclasses import dataclass, replace
 from pathlib import Path
 
-from PySide6.QtCore import Qt, QThreadPool, QTimer
+from PIL import Image
+from PySide6.QtCore import QMimeData, Qt, QThreadPool, QTimer
 from PySide6.QtGui import QAction, QActionGroup, QIcon
-from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
-                               QMessageBox,
+from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
+                               QLabel, QMainWindow, QMessageBox,
                                QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                                QWidget)
 
 from ..desktop import APP_NAME
 from ..detect import brother_busy, find_brother_lp
-from ..document import Document, TextObject
+from ..document import Document, ImageObject, TextObject
+from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
-from ..labels import get_label
+from ..labels import DPI, get_label
 from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, growing_axis,
-                      match_objects, maximize_object, move, object_rect, outside_indices,
-                      printable_area, reorder, resize, rotate, set_frame, to_grid)
+                      insert_frame, match_objects, maximize_object, move, object_rect,
+                      outside_indices, printable_area, proportional, reorder, resize, rotate,
+                      set_frame, to_grid)
 from ..printer import DEFAULT_MODEL
 from ..render import Renderer, RenderedObject, font_warnings
 from ..settings import Settings, load_settings, new_document
@@ -27,7 +31,10 @@ from ..shortcuts import effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
 from .history import History, restore
+from . import image_import
+from .image_import import CLIPBOARD, DROPPED, MIME_OBJECTS
 from .media_worker import MediaWorker
+from .panels.image import CROP_FAILED
 from .panels.text import DEFAULT_PT
 from .print_worker import PrintWorker
 from .settings_dialog import SettingsDialog
@@ -44,12 +51,14 @@ NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit U
 _DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
 OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"
 PASTE_OFFSET_MM = 2.0      # Einfügen/Duplizieren: versetzt nach rechts und unten
+SHRUNK_HINT = "Bild auf {percent} verkleinert – Codes ggf. nicht mehr lesbar"   # „37 %“
+NO_CLIPBOARD_IMAGE = "Kein Bild in der Zwischenablage."
 # Bearbeitungsleiste: Aktion und eigenes Symbol (gui/icons); None = Trenner
 EDIT_BAR = (("tool.select", "tool-select"), ("tool.text", "tool-text"), None,
             ("edit.cut", "edit-cut"), ("edit.copy", "edit-copy"), ("edit.paste", "edit-paste"),
             None, ("edit.undo", "edit-undo"), ("edit.redo", "edit-redo"))
 _SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
-SELECTION_PANELS = ("text", "layout")   # arbeiten mit der Auswahl: Wählen wechselt nicht weg
+OBJECT_PANELS = ("text", "image")       # Panel je Objektart (Text, Bild)
 
 
 class MainWindow(QMainWindow):
@@ -73,7 +82,12 @@ class MainWindow(QMainWindow):
         self._printer_present = False
         self._printing = False
         self._media_check_pending = False
-        self._clipboard: list[TextObject] = []      # interne Zwischenablage (Kopien)
+        self._clipboard: list[TextObject | ImageObject] = []   # interne Zwischenablage (Kopien)
+        self._clipboard_token = ""                  # Kennung der Kopie im System (MIME_OBJECTS)
+        self._system = _ClipboardState()            # Zwischenablage des Systems (beim Ändern)
+        self._text_pastes = 0                       # Text eingefügt seit dem letzten Ändern
+        self._notice: str | None = None             # Meldung zum Einfügen von Bildern
+        self._image_dir = ""                        # Ordner des zuletzt eingefügten Bilds
         self._merge_next = None                     # Pfeiltasten: Schritte zusammenfassen
         self._restoring = False                     # Rückgängig setzt gerade die Auswahl
         self._arranging = False                     # Auswahl wird intern umgestellt (Anlegen …)
@@ -131,6 +145,7 @@ class MainWindow(QMainWindow):
         self.canvas.edit_requested.connect(self.edit_text)
         self.canvas.selection_changed.connect(self._update_edit_actions)
         self.canvas.object_clicked.connect(self._show_object_panel)
+        self.canvas.dropped.connect(self._dropped)
         self.history = History(self.doc)
         self.history.changed.connect(self._update_edit_actions)
         self._connect_view_actions()
@@ -194,8 +209,12 @@ class MainWindow(QMainWindow):
         self._connect_edit_mode()
         self.render_now()
         self.canvas.selection_changed.connect(self._on_selection)
-        self.panel("text").frame_edited.connect(self._edit_frame)
-        self._update_edit_actions()
+        for key in OBJECT_PANELS:
+            self.panel(key).frame_edited.connect(
+                lambda field, value, k=key: self._edit_frame(k, field, value))
+        self.panel("image").paste_requested.connect(self.paste_image)
+        self.panel("image").message.connect(self._set_result)
+        self._clipboard_changed()
         self.refresh_printer()
         if self.settings.warnings or key_warnings:
             self._set_result(" · ".join(self.settings.warnings + key_warnings), "error")
@@ -232,7 +251,8 @@ class MainWindow(QMainWindow):
                     "edit.cut": self.cut_selected, "edit.copy": self.copy_selected,
                     "edit.paste": self.paste, "edit.duplicate": self.duplicate_selected,
                     "tool.select": lambda: self._choose_tool("select"),
-                    "tool.text": lambda: self._choose_tool("text")}
+                    "tool.text": lambda: self._choose_tool("text"),
+                    "image.insert": self.insert_image_file}
         handlers["text.start_edit"] = handlers["text.start_edit_enter"] = self.edit_selected
         for key, handler in handlers.items():
             self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
@@ -254,9 +274,9 @@ class MainWindow(QMainWindow):
         editor = self.panel("text").edit
         for signal in (editor.copyAvailable, editor.undoAvailable, editor.redoAvailable):
             signal.connect(self._update_edit_actions)
-        # Einfügen-Knopf folgt der Zwischenablage des Systems (PySide trennt die Verbindung
+        # Einfügen-Knöpfe folgen der Zwischenablage des Systems (PySide trennt die Verbindung
         # mit dem Fenster, ein späteres Ändern der Zwischenablage trifft nichts Gelöschtes)
-        QApplication.clipboard().dataChanged.connect(self._update_edit_actions)
+        QApplication.clipboard().dataChanged.connect(self._clipboard_changed)
 
     def _connect_layout_actions(self) -> None:
         """Reiter „Layout“: Ausrichten, Größe angleichen, Drehen, Reihenfolge (auch per Kürzel)."""
@@ -327,9 +347,9 @@ class MainWindow(QMainWindow):
             self.canvas.set_tool("text")
 
     def _on_selection(self, indices: list[int]) -> None:
-        """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen – außer ein Panel, das mit
-        der Auswahl arbeitet (Text, Layout), ist schon zu sehen. Ein leerer Textrahmen, den
-        die Auswahl verlässt, entfällt."""
+        """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen (Text oder Bild) – außer
+        der Reiter „Layout“ ist zu sehen. Ein leerer Textrahmen, den die Auswahl verlässt,
+        entfällt."""
         if self._arranging:                         # Anlegen, Umnummerieren: nur mitführen
             self._follow_selection(indices)
             return
@@ -373,37 +393,49 @@ class MainWindow(QMainWindow):
         return indices
 
     def _show_object_panel(self) -> None:
-        """Vom Papier-Reiter zum Panel des Objekts (auch beim Klick auf ein schon gewähltes)."""
-        if not any(self.panels.currentWidget() is self.panel(key) for key in SELECTION_PANELS):
-            self._show_tool("text")
+        """Zum Panel des zuletzt gewählten Objekts – Text oder Bild (auch beim Klick auf ein
+        schon gewähltes); der Reiter „Layout“ arbeitet mit jeder Auswahl und bleibt."""
+        if self.panels.currentWidget() is self.panel("layout"):
+            return
+        selection = self.canvas.selection()
+        if selection and 0 <= selection[-1] < len(self.doc.objects):
+            key = _panel_for(self.doc.objects[selection[-1]])
+            if self.panels.currentWidget() is not self.panel(key):
+                self._show_tool(key)
 
     def _follow_selection(self, indices: list[int]) -> None:
-        """Panels erfahren die Auswahl; das Text-Panel bearbeitet das zuletzt gewählte Objekt."""
+        """Panels erfahren die Auswahl; das Panel seiner Art bearbeitet das zuletzt gewählte
+        Objekt, das andere keins."""
         for panel in self._panel_by_key.values():
             panel.set_selection(indices)
-        self.panel("text").set_object(indices[-1] if indices else None)
+        last = indices[-1] if indices and indices[-1] < len(self.doc.objects) else None
+        kind = _panel_for(self.doc.objects[last]) if last is not None else None
+        for key in OBJECT_PANELS:
+            self.panel(key).set_object(last if kind == key else None)
         self._update_frame()
 
     def _update_frame(self) -> None:
         """Bereich „Position“: Rahmen des bearbeiteten Objekts, wie er gerendert ist."""
-        panel = self.panel("text")
-        index = panel.index
-        if index is None or index >= len(self.rendered) or index >= len(self.doc.objects):
-            panel.show_frame(None)
-        else:
-            panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))
+        for key in OBJECT_PANELS:
+            panel = self.panel(key)
+            index = panel.index
+            if index is None or not self._valid(index):
+                panel.show_frame(None)
+            else:
+                panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))
 
     def _update_edit_actions(self) -> None:
         if self.edit_session.update_actions(self.shortcut_actions):   # wirken auf den Editor
             return
         self.shortcut_actions["text.end_edit"].setEnabled(False)
-        single = len(self.canvas.selection()) == 1
+        selection = self.canvas.selection()
+        single_text = (len(selection) == 1 and selection[0] < len(self.doc.objects)
+                       and isinstance(self.doc.objects[selection[0]], TextObject))
         for key in ("text.start_edit", "text.start_edit_enter"):
-            self.shortcut_actions[key].setEnabled(single)
-        selected = bool(self.canvas.selection())
+            self.shortcut_actions[key].setEnabled(single_text)
         for key in _SELECTION_ACTIONS:
-            self.shortcut_actions[key].setEnabled(selected)
-        self.shortcut_actions["edit.paste"].setEnabled(bool(self._clipboard))
+            self.shortcut_actions[key].setEnabled(bool(selection))
+        self.shortcut_actions["edit.paste"].setEnabled(self._can_paste())
         self.shortcut_actions["edit.undo"].setEnabled(self.history.can_undo(self.doc))
         self.shortcut_actions["edit.redo"].setEnabled(self.history.can_redo(self.doc))
 
@@ -447,9 +479,15 @@ class MainWindow(QMainWindow):
         self._structure_dirty = False
         self._outside = outside
         self._area = area
+        # Anfasser: Ecken halten das Seitenverhältnis bei Text ohne feste Rahmengröße und bei
+        # Bildern mit „Seitenverhältnis beibehalten“ – Bilder dann auch an den Kanten
+        images = [isinstance(obj, ImageObject) for obj in self.doc.objects]
         self.canvas.set_document(get_label(self.doc.label_id), size, rendered, self.doc.orientation,
-                                 area, keep_ratio=[not obj.fit for obj in self.doc.objects],
-                                 grow=growing_axis(self.doc))
+                                 area, keep_ratio=[obj.keep_ratio if image else not obj.fit
+                                                   for obj, image in zip(self.doc.objects, images)],
+                                 grow=growing_axis(self.doc),
+                                 keep_aspect=[image and obj.keep_ratio
+                                              for obj, image in zip(self.doc.objects, images)])
         self.panel("layout").set_growing(growing_axis(self.doc))
         self._update_frame()
         self.edit_session.update_marks()            # Schreibmarke zum neuen Zeilensatz
@@ -560,10 +598,7 @@ class MainWindow(QMainWindow):
         self.finish_editing()
         self._structure_changing()
         self._commit()
-        family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
-        # linksbündig: Schreibmarke am Klickpunkt, der Text wächst nach rechts (wie P-touch)
-        obj = TextObject.plain("", size_pt=self.settings.font_size_pt or DEFAULT_PT, align="left",
-                               family=family)
+        obj = self._new_text("")
         obj.x_mm, obj.y_mm = round(x_mm, 1), round(y_mm, 1)
         self.doc.objects[:] = [o for o in self.doc.objects if not o.is_empty()]
         self.doc.objects.append(obj)
@@ -577,6 +612,13 @@ class MainWindow(QMainWindow):
         self.canvas.set_selection([index])
         self.edit_text(index)                       # Anlegen und Schreiben: ein Schritt
 
+    def _new_text(self, text: str) -> TextObject:
+        """Neuer Text mit der Schrift aus den Einstellungen (automatische Größe → 19 pt),
+        linksbündig: Er wächst von seiner Position nach rechts (wie P-touch)."""
+        family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
+        return TextObject.plain(text, size_pt=self.settings.font_size_pt or DEFAULT_PT,
+                                align="left", family=family)
+
     def edit_selected(self) -> None:
         """F2/Enter: Schreibmodus für das einzige gewählte Objekt, Schreibmarke am Textende."""
         selection = self.canvas.selection()
@@ -585,7 +627,11 @@ class MainWindow(QMainWindow):
 
     def edit_text(self, index: int, point=None) -> None:
         """Schreibmodus für ein Objekt: auswählen, Text-Panel zeigen, Schreibmarke an
-        ``point`` (QPointF, Druckpunkte in Leserichtung – z. B. Doppelklick) bzw. ans Ende."""
+        ``point`` (QPointF, Druckpunkte in Leserichtung – z. B. Doppelklick) bzw. ans Ende.
+        Bilder haben keinen Schreibmodus."""
+        if 0 <= index < len(self.doc.objects) and not isinstance(self.doc.objects[index],
+                                                                 TextObject):
+            return
         if self.edit_session.active:
             if self.edit_session.index == index:
                 return
@@ -628,15 +674,20 @@ class MainWindow(QMainWindow):
         self.render_now()
         self._commit()
 
-    def _edit_frame(self, key: str, value: float) -> None:
-        """Zahl im Bereich „Position“ geändert: Objekt verschieben bzw. Rahmen ändern."""
+    def _edit_frame(self, panel: str, key: str, value: float) -> None:
+        """Zahl im Bereich „Position“ des Panels ``panel`` geändert: Objekt verschieben bzw.
+        Rahmen ändern; ein Bild mit „Seitenverhältnis beibehalten“ ändert beide Maße."""
         self.finish_editing()
-        index = self.panel("text").index
+        index = self.panel(panel).index
         if index is None or not self._valid(index):
             return
         self._commit()
         obj = self.doc.objects[index]
-        rect = replace(exact_rect(obj, self.rendered[index]), **{key: round(value, 3)})
+        exact = exact_rect(obj, self.rendered[index])
+        if isinstance(obj, ImageObject) and obj.keep_ratio and key in "wh":
+            rect = proportional(exact, key, round(value, 3))
+        else:
+            rect = replace(exact, **{key: round(value, 3)})
         self.doc.objects[index] = set_frame(obj, rect, self.rendered[index])
         self._objects_changed([index])
         self._commit()
@@ -705,19 +756,80 @@ class MainWindow(QMainWindow):
         indices = sorted(self.canvas.selection())
         if indices:
             self._clipboard = [self._placed_copy(i) for i in indices]
+            self._announce_copy()
             self._update_edit_actions()
 
+    def _announce_copy(self) -> None:
+        """Kopie in der Zwischenablage des Systems kennzeichnen (``MIME_OBJECTS`` mit eigener
+        Kennung, dazu der Text der Textobjekte für andere Programme). Die Objekte selbst
+        bleiben in der internen Zwischenablage; kopiert jemand danach etwas anderes, fügt
+        Strg+V das ein."""
+        self._clipboard_token = uuid.uuid4().hex
+        mime = QMimeData()
+        mime.setData(MIME_OBJECTS, self._clipboard_token.encode())
+        text = "\n".join(obj.text for obj in self._clipboard
+                         if isinstance(obj, TextObject) and not obj.is_empty())
+        if text:
+            mime.setText(text)
+        QApplication.clipboard().setMimeData(mime)
+        self._system = _ClipboardState(token=self._clipboard_token, text=bool(text),
+                                       empty=False)    # auch ohne (verspätetes) dataChanged
+
     def cut_selected(self) -> None:
         if not self.edit_session.cut():
             self.copy_selected()
             self.delete_selected()
 
     def paste(self) -> None:
-        """Zwischenablage einfügen – jedes Mal 2 mm weiter versetzt; Eingefügtes ist ausgewählt.
-        Im Schreibmodus Text aus der Zwischenablage des Systems (als reiner Text)."""
-        if not self.edit_session.paste() and self._clipboard:
+        """Einfügen, was die Zwischenablage des Systems oben hat, in dieser Reihenfolge:
+        hier kopierte Objekte (jedes Mal 2 mm weiter versetzt; ist die Zwischenablage leer,
+        die zuletzt kopierten) › lokale Dateien (wie „Aus Datei“) › Text (neuer Textrahmen –
+        auch wenn ein Bild dabei ist, z. B. Tabellenzellen; das Bild bleibt über „Aus
+        Zwischenablage“ erreichbar) › Bild (Mitte des bedruckbaren Bereichs). Eingefügtes ist
+        ausgewählt. Im Schreibmodus Text in den Text (als reiner Text). Nur hier werden die
+        Daten der Zwischenablage gelesen."""
+        if self.edit_session.paste():
+            return
+        if self._owns_clipboard() or (self._clipboard and self._system.empty):
             self._clipboard = [_offset(obj) for obj in self._clipboard]
             self._insert(copy.deepcopy(self._clipboard))
+            return
+        mime = QApplication.clipboard().mimeData()
+        if paths := image_import.mime_files(mime):
+            self.insert_image_files(paths)
+        elif text := image_import.mime_text(mime):
+            self._paste_text(text)
+        elif (image := image_import.mime_image(mime)) is not None:
+            self._insert_picture(image, CLIPBOARD)
+
+    def _owns_clipboard(self) -> bool:
+        """Liegt die zuletzt hier kopierte Auswahl oben in der Zwischenablage des Systems?"""
+        return bool(self._clipboard) and self._system.token == self._clipboard_token
+
+    def _can_paste(self) -> bool:
+        system = self._system
+        return (self._owns_clipboard() or (bool(self._clipboard) and system.empty)
+                or system.files or system.text or system.image)
+
+    def _clipboard_changed(self) -> None:
+        """Zwischenablage des Systems geändert: Stand einmal merken (ohne Bild- und Textdaten
+        zu holen – die liest erst ``paste``), Knöpfe „Einfügen“ und „Aus Zwischenablage“."""
+        self._system = _ClipboardState.of(QApplication.clipboard().mimeData())
+        self._text_pastes = 0
+        self.panel("image").set_clipboard_image(self._system.image)
+        self._update_edit_actions()
+
+    def _paste_text(self, text: str) -> None:
+        """Text aus der Zwischenablage als neuer Textrahmen links oben im bedruckbaren
+        Bereich (wie „Text anlegen“), ausgewählt – ohne Schreibmodus. Derselbe Text noch
+        einmal eingefügt: jedes Mal 2 mm weiter versetzt (wie Objekte)."""
+        if self._timer.isActive():
+            self.render_now()                       # aktueller bedruckbarer Bereich
+        obj = self._new_text(text)
+        shift = self._text_pastes * PASTE_OFFSET_MM
+        obj.x_mm, obj.y_mm = round(self._area.x + shift, 3), round(self._area.y + shift, 3)
+        self._text_pastes += 1
+        self._insert([obj])
 
     def duplicate_selected(self) -> None:
         """Auswahl 2 mm versetzt verdoppeln; die Zwischenablage bleibt unberührt."""
@@ -725,7 +837,7 @@ class MainWindow(QMainWindow):
         if indices:
             self._insert([_offset(self._placed_copy(i)) for i in indices])
 
-    def _placed_copy(self, index: int) -> TextObject:
+    def _placed_copy(self, index: int) -> TextObject | ImageObject:
         """Kopie mit Position: ein mittiges Objekt bekommt seine Lage und Schriftgröße fest."""
         obj = self.doc.objects[index]
         if obj.positioned or index >= len(self.rendered):
@@ -733,7 +845,7 @@ class MainWindow(QMainWindow):
         rendered = self.rendered[index]
         return move(obj, object_rect(rendered), rendered)
 
-    def _insert(self, objects: list[TextObject]) -> None:
+    def _insert(self, objects: list[TextObject | ImageObject]) -> None:
         self.finish_editing()
         self._structure_changing()
         self._commit()
@@ -743,9 +855,123 @@ class MainWindow(QMainWindow):
         self.canvas.set_selection(list(range(start, len(self.doc.objects))))
         self._commit()
 
+    # --- Bilder einfügen ---------------------------------------------------
+    def insert_image_file(self) -> None:
+        """„Bild einfügen …“: Datei wählen; das Bild kommt in die Mitte des bedruckbaren
+        Bereichs."""
+        path = self.ask_image_file()
+        if path:
+            self.insert_image_files([Path(path)])
+
+    def ask_image_file(self) -> str | None:
+        """Dateidialog „Bilder und PDF“ (in Tests ersetzbar); None = abgebrochen."""
+        path, _ = QFileDialog.getOpenFileName(self, "Bild einfügen", self._image_dir,
+                                              image_import.FILE_FILTER)
+        if path:
+            self._image_dir = str(Path(path).parent)
+        return path or None
+
+    def ask_pdf_page(self, path: Path, count: int) -> int | None:
+        """Seitenwahl für ein PDF mit mehreren Seiten (in Tests ersetzbar); None = abgebrochen."""
+        page, ok = QInputDialog.getInt(self, "PDF-Seite wählen",
+                                       f"{path.name} hat {count} Seiten. Welche einfügen?",
+                                       1, 1, count)
+        return page if ok else None
+
+    def insert_image_files(self, paths: list, at: tuple[float, float] | None = None,
+                           page: int | None = None) -> None:
+        """Bilddateien einfügen – mittig auf ``at`` (mm, Ablagepunkt) bzw. in der Mitte des
+        bedruckbaren Bereichs. Bei einem PDF mit mehreren Seiten wird die Seite erfragt
+        (``page`` gibt sie vor). Fehler stehen verständlich in der Statusleiste; was sich
+        laden ließ, wird eingefügt (ein Schritt)."""
+        objects, notes, failed = [], [], False
+        for path in map(Path, paths):
+            pdf = path.suffix.lower() == ".pdf"
+            try:
+                number = page or (self._choose_page(path) if pdf else 1)
+                if number is None:
+                    continue                        # Seitenwahl abgebrochen
+                image, dpi = image_import.load(path, number)
+            except (ValueError, OSError) as e:
+                notes.append(str(e))
+                failed = True
+                continue
+            objects.append(self._new_image(image, dpi, path.name, number if pdf else None, notes))
+        self._insert_images(objects, at, notes, "error" if failed else "warn")
+
+    def _choose_page(self, path: Path) -> int | None:
+        count = image_import.page_count(path)
+        return 1 if count <= 1 else self.ask_pdf_page(path, count)
+
+    def paste_image(self) -> None:
+        """„Aus Zwischenablage“: Bild der Zwischenablage in die Mitte des bedruckbaren Bereichs."""
+        image = image_import.mime_image(QApplication.clipboard().mimeData())
+        if image is None:
+            self._show_notice([NO_CLIPBOARD_IMAGE], "error")
+            return
+        self._insert_picture(image, CLIPBOARD)
+
+    def _dropped(self, paths: list[Path], image: Image.Image | None, x_mm: float,
+                 y_mm: float) -> None:
+        """Bilddateien oder Bilddaten auf die Arbeitsfläche abgelegt: an der Ablagestelle
+        (kommt nach dem Ablegen, ``Canvas.dropped`` – ein PDF-Seitendialog ist dann möglich)."""
+        if paths:
+            self.insert_image_files(paths, at=(x_mm, y_mm))
+        elif image is not None:
+            self._insert_picture(image, DROPPED, at=(x_mm, y_mm))
+
+    def _insert_picture(self, image: Image.Image, source: str,
+                        at: tuple[float, float] | None = None) -> None:
+        """Bild ohne Auflösungsangabe (Zwischenablage, Bilddaten) mit 300 dpi einfügen."""
+        notes: list[str] = []
+        self._insert_images([self._new_image(image, DPI, source, None, notes)], at, notes)
+
+    def _new_image(self, image: Image.Image, dpi: float, source: str, page: int | None,
+                   notes: list[str]) -> ImageObject:
+        """Bild-Objekt 1:1, automatisch zugeschnitten (alles, was nicht weiß ist); ist das
+        Bild ganz weiß, bleibt es ganz – mit Hinweis in ``notes``."""
+        crop = crop_box(image, dpi, ink=NOT_WHITE)
+        if crop is None and CROP_FAILED not in notes:
+            notes.append(CROP_FAILED)
+        return ImageObject.from_image(image, dpi, source, page, crop)
+
+    def _insert_images(self, objects: list[ImageObject], at: tuple[float, float] | None,
+                       notes: list[str], state: str = "warn") -> None:
+        """Bilder platzieren (``layout.insert_frame``: mittig, zu große proportional
+        verkleinert und danach auf höchstens 600 dpi der neuen Größe begrenzt; mehrere je
+        2 mm versetzt) und einfügen – ein Schritt, ausgewählt."""
+        if objects:
+            if self._timer.isActive():
+                self.render_now()                   # aktueller bedruckbarer Bereich
+            smallest = 1.0
+            for number, obj in enumerate(objects):
+                rect, factor = insert_frame(self.doc, self.model, self._area,
+                                            (obj.w_mm, obj.h_mm), at)
+                shift = number * PASTE_OFFSET_MM
+                obj.x_mm, obj.y_mm = rect.x + shift, rect.y + shift
+                obj.w_mm, obj.h_mm = rect.w, rect.h
+                if factor < 1:
+                    objects[number] = obj.limit_resolution()
+                smallest = min(smallest, factor)
+            self._insert(objects)
+            if smallest < 1:
+                percent = round(smallest * 100)
+                notes.append(SHRUNK_HINT.format(percent=f"{percent} %" if percent else "< 1 %"))
+        self._show_notice(notes, state)
+
+    def _show_notice(self, notes: list[str], state: str) -> None:
+        """Meldungen zum Einfügen in der Statusleiste; ohne Meldung verschwindet eine ältere."""
+        if notes:
+            self._notice = " · ".join(notes)
+            self._set_result(self._notice, state)
+        elif self._notice is not None and self.result.text() == self._notice:
+            self._set_result("", "")
+            self._notice = None
+
     def _objects_changed(self, indices: list[int]) -> None:
-        if self.panel("text").index in indices:
-            self.panel("text").refresh()   # z. B. Anfasser schaltet feste Rahmengröße ein
+        for key in OBJECT_PANELS:
+            if self.panel(key).index in indices:
+                self.panel(key).refresh()   # z. B. Anfasser schaltet feste Rahmengröße ein
         self.render_now()
 
     def _on_length_dragged(self, length_mm) -> None:
@@ -940,7 +1166,33 @@ class MainWindow(QMainWindow):
         self.refresh_printer()
 
 
-def _offset(obj: TextObject) -> TextObject:
+def _panel_for(obj: TextObject | ImageObject) -> str:
+    """Panel, das ein Objekt bearbeitet."""
+    return "image" if isinstance(obj, ImageObject) else "text"
+
+
+@dataclass(frozen=True)
+class _ClipboardState:
+    """Was die Zwischenablage des Systems anbietet – gemerkt beim Ändern, damit das Freigeben
+    der Knöpfe (bei jedem Schritt) keine Daten holt. ``token``: Kennung einer hier kopierten
+    Auswahl (``MIME_OBJECTS``, wenige Bytes)."""
+    token: str = ""
+    files: bool = False
+    text: bool = False
+    image: bool = False
+    empty: bool = True
+
+    @classmethod
+    def of(cls, mime: QMimeData | None) -> "_ClipboardState":
+        if mime is None or not mime.formats():
+            return cls()
+        token = (bytes(mime.data(MIME_OBJECTS)).decode(errors="replace")
+                 if mime.hasFormat(MIME_OBJECTS) else "")
+        return cls(token=token, files=bool(image_import.mime_files(mime)),
+                   text=bool(image_import.mime_text(mime)), image=mime.hasImage(), empty=False)
+
+
+def _offset(obj: TextObject | ImageObject) -> TextObject | ImageObject:
     """Kopie, um ``PASTE_OFFSET_MM`` nach rechts und unten versetzt."""
     moved = copy.deepcopy(obj)
     moved.x_mm = round((obj.x_mm or 0.0) + PASTE_OFFSET_MM, 3)
diff --git a/src/labelwerk/gui/panels/image.py b/src/labelwerk/gui/panels/image.py
new file mode 100644
index 0000000..c9b6a24
--- /dev/null
+++ b/src/labelwerk/gui/panels/image.py
@@ -0,0 +1,232 @@
+"""Panel „Bild“: Bilder einfügen (Datei, Zwischenablage) und das gewählte Bild einstellen.
+
+Umwandlung in Schwarz/Weiß (Strich = harte Schwelle, Foto = Rasterpunkte), Schwelle,
+Umkehren, Zuschnitt (automatisch an/aus), Originalgröße 1:1, Seitenverhältnis und der
+Bereich „Position“ (``panels.position``, Größe immer änderbar). Gerechnet wird im Kern
+(``layout.set_crop`` …); Einfügen und Rahmenfelder führt das Hauptfenster aus.
+"""
+from __future__ import annotations
+
+from dataclasses import replace
+
+from PySide6.QtCore import Qt, Signal
+from PySide6.QtGui import QAction
+from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QPushButton,
+                               QRadioButton, QSlider)
+
+from ... import layout
+from ...document import Document, ImageObject
+from ...files import NOT_WHITE, crop_box
+from ...layout import Rect
+from ..widgets import SpinBox
+from . import Panel
+from .position import PositionSection
+
+HINT = "Bild aus einer Datei oder der Zwischenablage einfügen – oder aufs Etikett ziehen"
+CROP_FAILED = "Bild nicht zugeschnitten – nur weiße Fläche gefunden"
+_SOURCE_PX = 240                    # Quelle: längere Namen in der Mitte gekürzt (Tooltip)
+
+
+class ImagePanel(Panel):
+    frame_edited = Signal(str, float)   # Feld im Bereich „Position“ ("x" | "y" | "w" | "h"), mm
+    paste_requested = Signal()          # „Aus Zwischenablage“
+    message = Signal(str, str)          # Hinweis für die Statusleiste (Text, Zustand)
+
+    def __init__(self, doc: Document):
+        super().__init__(doc, "Bild")
+        self.index: int | None = None   # bearbeitetes Bild; None = keins ausgewählt
+        self._updating = False
+
+        self.hint = QLabel(HINT)
+        self.hint.setObjectName("hint")
+        self.hint.setWordWrap(True)
+        self.layout_.addWidget(self.hint)
+
+        self.section("Einfügen")
+        self.from_file = QPushButton("AUS DATEI …")
+        self.from_file.setToolTip("Bild oder PDF-Seite einfügen")
+        self.from_clipboard = QPushButton("AUS ZWISCHENABLAGE")
+        self.from_clipboard.setToolTip("Bild aus der Zwischenablage einfügen")
+        self.from_clipboard.setEnabled(False)
+        self.from_clipboard.clicked.connect(self.paste_requested)
+        for button in (self.from_file, self.from_clipboard):
+            self.layout_.addWidget(button)
+
+        self.section("Quelle")
+        self.source = QLabel()
+        self.source.setObjectName("imageSource")
+        self.layout_.addWidget(self.source)
+
+        self.section("Umwandlung")
+        row = QHBoxLayout()
+        self.line = QRadioButton("Strich")
+        self.line.setToolTip("Harte Schwelle – für Codes, Schrift und Logos")
+        self.photo = QRadioButton("Foto")
+        self.photo.setToolTip("Graustufen als Rasterpunkte – für Fotos und Verläufe")
+        self.mode_group = QButtonGroup(self)
+        for button in (self.line, self.photo):
+            self.mode_group.addButton(button)
+            row.addWidget(button)
+        row.addStretch()
+        self.layout_.addLayout(row)
+        row = QHBoxLayout()                    # „Schwelle [128]“, darunter der Regler
+        self.threshold_label = QLabel("Schwelle")
+        self.threshold_value = SpinBox()
+        self.threshold = QSlider(Qt.Orientation.Horizontal)
+        for widget in (self.threshold_label, self.threshold, self.threshold_value):
+            widget.setToolTip("Höher = mehr Schwarz")
+        self.threshold.setRange(0, 255)
+        self.threshold_value.setRange(0, 255)
+        self.threshold_value.setKeyboardTracking(False)
+        row.addWidget(self.threshold_label)
+        row.addWidget(self.threshold_value, 1)
+        self.layout_.addLayout(row)
+        self.layout_.addWidget(self.threshold)
+        self.invert = QCheckBox("Umkehren")
+        self.invert.setToolTip("Schwarz und Weiß tauschen")
+        self.layout_.addWidget(self.invert)
+
+        self.section("Größe")
+        self.crop = QCheckBox("Zuschnitt automatisch")
+        self.crop.setToolTip("Auf den Inhalt zuschneiden (ohne Schnittmarken und Leerraum); "
+                             "aus = ganzes Bild")
+        self.keep_ratio = QCheckBox("Seitenverhältnis beibehalten")
+        self.keep_ratio.setToolTip("Anfasser und Felder skalieren das Bild ohne Verzerren")
+        self.original = QPushButton("ORIGINALGRÖSSE 1:1")
+        self.original.setToolTip("Druckgröße aus der Auflösung des Bilds (z. B. Briefmarke, Code)")
+        for widget in (self.crop, self.keep_ratio, self.original):
+            self.layout_.addWidget(widget)
+
+        self.section("Position (mm)")
+        self.position = PositionSection()
+        self.position.edited.connect(self._frame_changed)
+        self.layout_.addWidget(self.position)
+        self.layout_.addStretch()
+
+        self.refresh()
+        step = self._step               # jede Einstellung ein eigener Rückgängig-Schritt
+        self.line.clicked.connect(lambda: step(self._set, mode="line"))
+        self.photo.clicked.connect(lambda: step(self._set, mode="photo"))
+        self.threshold.valueChanged.connect(self._threshold_moved)
+        # Ziehen am Regler: ein Schritt vom Drücken bis zum Loslassen
+        self.threshold.sliderPressed.connect(self._edited)
+        self.threshold.sliderReleased.connect(self._edited)
+        self.threshold_value.valueChanged.connect(lambda v: step(self._set, threshold=v))
+        self.invert.clicked.connect(lambda on: step(self._set, invert=on))
+        self.crop.clicked.connect(lambda on: step(self._set_crop, on))
+        self.keep_ratio.clicked.connect(
+            lambda on: step(self._change, lambda obj: layout.set_keep_ratio(obj, on)))
+        self.original.clicked.connect(lambda: step(self._change, layout.original_size))
+
+    def use_actions(self, actions: dict[str, QAction]) -> None:
+        """„Aus Datei …“ löst die Aktion „Bild einfügen …“ aus (Kürzel im Tooltip)."""
+        action = actions["image.insert"]
+        self.from_file.clicked.connect(lambda: action.trigger())
+        self.from_file.setToolTip(action.toolTip())
+        action.changed.connect(lambda: self.from_file.setToolTip(action.toolTip()))
+
+    @property
+    def obj(self) -> ImageObject:
+        return self.doc.objects[self.index]
+
+    def set_object(self, index: int | None) -> None:
+        """Bild bearbeiten (Index in ``doc.objects``) bzw. mit None keins."""
+        if index != self.index:
+            self.index = index
+            self.refresh()
+
+    def set_clipboard_image(self, available: bool) -> None:
+        """Enthält die Zwischenablage ein Bild? („Aus Zwischenablage“ nur dann aktiv)."""
+        self.from_clipboard.setEnabled(available)
+
+    def _settings_widgets(self):
+        return (self.line, self.photo, self.threshold_label, self.threshold, self.threshold_value,
+                self.invert, self.crop, self.keep_ratio, self.original, self.position)
+
+    # --- Modell → Panel -----------------------------------------------------
+    def refresh(self) -> None:
+        if self.index is not None and not (0 <= self.index < len(self.doc.objects)
+                                           and isinstance(self.obj, ImageObject)):
+            self.index = None                      # Objekt gibt es nicht mehr (Rückgängig …)
+        selected = self.index is not None
+        self.hint.setVisible(not selected)
+        for widget in self._settings_widgets():
+            widget.setEnabled(selected)
+        self._updating = True
+        try:
+            if not selected:
+                self._show_source("")
+                self.line.setChecked(True)
+                self.threshold.setValue(128)
+                self.threshold_value.setValue(128)
+                for box in (self.invert, self.crop, self.keep_ratio):
+                    box.setChecked(False)
+                self.show_frame(None)
+                return
+            obj = self.obj
+            page = f" · Seite {obj.page}" if obj.page is not None else ""
+            self._show_source(f"{obj.source}{page}")
+            (self.photo if obj.mode == "photo" else self.line).setChecked(True)
+            self.threshold.setValue(obj.threshold)
+            self.threshold_value.setValue(obj.threshold)
+            self.invert.setChecked(obj.invert)
+            self.crop.setChecked(obj.crop is not None)
+            self.keep_ratio.setChecked(obj.keep_ratio)
+        finally:
+            self._updating = False
+
+    def _show_source(self, text: str) -> None:
+        metrics = self.source.fontMetrics()
+        self.source.setText(metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, _SOURCE_PX))
+        self.source.setToolTip(text)
+
+    def show_frame(self, rect: Rect | None) -> None:
+        """Rahmen des Bilds in mm anzeigen (vom Hauptfenster nach dem Rendern)."""
+        self.position.show_frame(rect, editable_size=True)
+
+    # --- Panel → Modell -----------------------------------------------------
+    def _edited(self) -> None:
+        if not self._updating and self.index is not None:
+            self.edited.emit()
+
+    def _step(self, change, *args, **kwargs) -> None:
+        """Änderung als eigener Rückgängig-Schritt (vorher Offenes festhalten, danach das Neue)."""
+        if self._updating or self.index is None:
+            return
+        self.edited.emit()
+        change(*args, **kwargs)
+        self.edited.emit()
+
+    def _change(self, change) -> None:
+        self.doc.objects[self.index] = change(self.obj)
+        self.refresh()
+        self.changed.emit()
+
+    def _set(self, **values) -> None:
+        self._change(lambda obj: replace(obj, **values))
+
+    def _threshold_moved(self, value: int) -> None:
+        """Regler: Zahl mitführen; beim Ziehen nur anzeigen (Schritt bis zum Loslassen)."""
+        if self._updating or self.index is None:
+            return
+        if self.threshold.isSliderDown():
+            self._set(threshold=value)
+        else:
+            self._step(self._set, threshold=value)
+
+    def _set_crop(self, on: bool) -> None:
+        """Zuschnitt an (auf den Inhalt: alles, was nicht weiß ist) bzw. aus (ganzes Bild);
+        ist das Bild ganz weiß, bleibt es ganz – mit Hinweis."""
+        if not on:
+            self._change(lambda obj: layout.set_crop(obj, None))
+            return
+        box = crop_box(self.obj.image(), self.obj.dpi, ink=NOT_WHITE)
+        if box is None:
+            self.refresh()                         # Haken wieder aus
+            self.message.emit(CROP_FAILED, "warn")
+            return
+        self._change(lambda obj: layout.set_crop(obj, box))
+
+    def _frame_changed(self, key: str, value: float) -> None:
+        if self.index is not None:
+            self.frame_edited.emit(key, value)
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index e9c5928..fc6a647 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -458,8 +458,9 @@ class TextPanel(Panel):
 
     def refresh(self) -> None:
         """Editor aus dem Modell aufbauen (Auswahl, Rückgängig, Ziehen an den Anfassern)."""
-        if self.index is not None and not 0 <= self.index < len(self.doc.objects):
-            self.index = None                      # Objekt gibt es nicht mehr
+        if self.index is not None and not (0 <= self.index < len(self.doc.objects)
+                                           and isinstance(self.obj, TextObject)):
+            self.index = None                      # Objekt gibt es nicht mehr (Rückgängig …)
         editing = self.index is not None
         self.hint.setVisible(not editing)
         for widget in self._editing_widgets():
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index 03e60a5..3f708e1 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -94,6 +94,13 @@ QComboBox QAbstractItemView { border: 3px solid #000000; selection-background-co
 
 QCheckBox::indicator { width: 16px; height: 16px; border: 3px solid #000000; background: #FFFFFF; }
 QCheckBox::indicator:checked { background: #000000; }
+QCheckBox:disabled, QRadioButton:disabled, QLabel:disabled { color: #999999; }
+QCheckBox::indicator:disabled { border-color: #CCCCCC; background: #F5F5F5; }
+/* Schieberegler (Schwelle): schwarze Linie, eckiger Griff */
+QSlider::groove:horizontal { height: 3px; background: #000000; }
+QSlider::handle:horizontal { width: 12px; margin: -9px 0; background: #000000; border: none; }
+QSlider::handle:horizontal:hover { background: #FFFFFF; border: 3px solid #000000; width: 6px; }
+QSlider::groove:horizontal:disabled, QSlider::handle:horizontal:disabled { background: #CCCCCC; }
 
 QLabel#error { color: #FF0000; border: 3px solid #FF0000; padding: 6px; }
 QLabel#mediaStatus { padding: 0 10px; border-left: 2px solid #000000; font-weight: 700; }
@@ -155,6 +162,7 @@ QKeySequenceEdit QLineEdit {
 QStatusBar { border-top: 3px solid #000000; }
 QStatusBar QLabel[state="ok"] { color: #008000; font-weight: 700; }
 QStatusBar QLabel[state="error"] { color: #FF0000; font-weight: 700; }
+QStatusBar QLabel[state="warn"] { color: #CC7A00; font-weight: 700; }
 QStatusBar QToolButton { border: 2px solid #000000; padding: 0 8px; font-weight: 700; }
 QStatusBar QToolButton:hover { background: #000000; color: #FFFFFF; }
 
diff --git a/src/labelwerk/gui/tools.py b/src/labelwerk/gui/tools.py
index 01d7666..0f1a8db 100644
--- a/src/labelwerk/gui/tools.py
+++ b/src/labelwerk/gui/tools.py
@@ -1,6 +1,6 @@
 """Werkzeug-Registry: Werkzeugleiste und Panel-Stapel werden daraus erzeugt.
 
-Ein neues Werkzeug (Rahmen, Barcode, Bild …) ist ein neuer Eintrag in TOOLS.
+Ein neues Werkzeug (Rahmen, Barcode …) ist ein neuer Eintrag in TOOLS.
 """
 from __future__ import annotations
 
@@ -9,6 +9,7 @@ from typing import Callable
 
 from ..document import Document
 from .panels import Panel
+from .panels.image import ImagePanel
 from .panels.layout import LayoutPanel
 from .panels.paper import PaperPanel
 from .panels.text import TextPanel
@@ -25,5 +26,6 @@ class Tool:
 TOOLS = [
     Tool("paper", "Papier", "document-page-setup", PaperPanel),
     Tool("text", "Text", "insert-text", TextPanel),
+    Tool("image", "Bild", "insert-image", ImagePanel),
     Tool("layout", "Layout", "align-horizontal-left", LayoutPanel),
 ]
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index c13576d..7899c24 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -14,7 +14,7 @@ import copy
 from dataclasses import dataclass, field, replace
 
 from .document import MAX_PT, MIN_PT, ROTATIONS, Document, ImageObject, TextObject
-from .labels import DPI, get_label
+from .labels import DPI, get_label, length_limits
 from .render import (PT, REF_PT, RenderedObject, span_dots, label_margins, label_size,
                      render_object)
 
@@ -358,6 +358,87 @@ def keep_aspect(old: Rect, new: Rect, handle: str) -> Rect:
                 start(old.y, old.bottom, h, "t" in handle, "b" in handle), w, h)
 
 
+# --- Bild-Objekte: einfügen und einstellen ---------------------------------------
+def insert_frame(doc: Document, model: str, area: Rect, size: tuple[float, float],
+                 at: tuple[float, float] | None = None) -> tuple[Rect, float]:
+    """Rahmen für ein neues Objekt der Größe ``size`` (mm) und den Faktor, um den es dafür
+    proportional verkleinert wurde (1 = 1:1).
+
+    Mittig auf ``at`` (Klick-/Ablagepunkt) bzw. in der Mitte von ``area`` (bedruckbarer
+    Bereich), in den Bereich geschoben. In der Achse, in der das Etikett mitwächst
+    (``growing_axis``), begrenzt nur die größte Etikettlänge, und das Objekt beginnt nicht
+    vor dem Anfang des Bereichs.
+    """
+    grow = growing_axis(doc)
+    limit_w, limit_h = area.w, area.h
+    if grow is not None:
+        mx, my = label_margins(doc, model)
+        longest = _mm(length_limits(model)[1] - 2 * (mx if grow == "x" else my))
+        limit_w, limit_h = (longest, area.h) if grow == "x" else (area.w, longest)
+    w, h = size
+    factor = min(1.0, limit_w / w, limit_h / h) if w > 0 and h > 0 else 1.0
+    w, h = w * factor, h * factor
+    cx, cy = at if at is not None else (area.cx, area.cy)
+
+    def inside(start: float, low: float, high: float, open_end: bool) -> float:
+        start = max(start, low)
+        return start if open_end else min(start, max(low, high))
+
+    x = inside(cx - w / 2, area.x, area.right - w, grow == "x")
+    y = inside(cy - h / 2, area.y, area.bottom - h, grow == "y")
+    return _rounded(Rect(x, y, w, h)), factor
+
+
+def _image_point(obj: ImageObject, u: float, v: float) -> tuple[float, float]:
+    """Punkt im ungedrehten Rahmen (mm ab seiner linken oberen Ecke) → Etikett (mm)."""
+    w, h = obj.w_mm, obj.h_mm
+    du, dv = {0: (u, v), 90: (h - v, u), 180: (w - u, h - v), 270: (v, w - u)}[obj.rotation]
+    return obj.x_mm + du, obj.y_mm + dv
+
+
+def set_crop(obj: ImageObject, crop: tuple[int, int, int, int] | None) -> ImageObject:
+    """Kopie mit dem Ausschnitt ``crop`` (None = ganzes Bild). Maßstab und Lage des Inhalts
+    auf dem Etikett bleiben: Der Rahmen schrumpft auf den Ausschnitt bzw. wächst ums Bild."""
+    l, t, r, b = obj.box()
+    nl, nt, nr, nb = crop if crop is not None else replace(obj, crop=None).box()
+    sx, sy = obj.w_mm / (r - l), obj.h_mm / (b - t)          # mm je Pixel (ungedreht)
+    u0, v0 = (nl - l) * sx, (nt - t) * sy
+    w, h = (nr - nl) * sx, (nb - nt) * sy
+    corners = [_image_point(obj, u0, v0), _image_point(obj, u0 + w, v0 + h)]
+    changed = copy.deepcopy(obj)
+    changed.crop = crop
+    changed.x_mm = round(min(p[0] for p in corners), _DECIMALS)
+    changed.y_mm = round(min(p[1] for p in corners), _DECIMALS)
+    changed.w_mm, changed.h_mm = round(w, _DECIMALS), round(h, _DECIMALS)
+    return changed
+
+
+def original_size(obj: ImageObject) -> ImageObject:
+    """Kopie in Größe 1:1 (``ImageObject.natural_mm``); die linke obere Ecke bleibt."""
+    changed = copy.deepcopy(obj)
+    changed.w_mm, changed.h_mm = (round(v, _DECIMALS) for v in obj.natural_mm())
+    return changed
+
+
+def set_keep_ratio(obj: ImageObject, keep: bool) -> ImageObject:
+    """Kopie mit „Seitenverhältnis beibehalten“; beim Einschalten folgt die Höhe der Breite
+    (das Bild füllt seinen Rahmen wieder ganz). Die linke obere Ecke bleibt."""
+    changed = copy.deepcopy(obj)
+    changed.keep_ratio = keep
+    if keep:
+        l, t, r, b = obj.box()
+        changed.h_mm = round(obj.w_mm * (b - t) / (r - l), _DECIMALS)
+    return changed
+
+
+def proportional(rect: Rect, key: str, value: float) -> Rect:
+    """``rect`` mit Breite (``key`` „w“) bzw. Höhe („h“) ``value``, das andere Maß im selben
+    Verhältnis; die linke obere Ecke bleibt (Feld im Bereich „Position“)."""
+    old = rect.w if key == "w" else rect.h
+    factor = value / old if old > 0 else 1.0
+    return _rounded(Rect(rect.x, rect.y, rect.w * factor, rect.h * factor))
+
+
 def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) -> TextObject:
     """Kopie mit allen Schriftgrößen (Grundgröße und Stücke) × ``factor``, auf 4–100 pt begrenzt.
 
diff --git a/src/labelwerk/shortcuts.py b/src/labelwerk/shortcuts.py
index 7976d8e..5bd2487 100644
--- a/src/labelwerk/shortcuts.py
+++ b/src/labelwerk/shortcuts.py
@@ -36,6 +36,7 @@ ACTIONS: tuple[Action, ...] = (
     Action("edit.redo", "Wiederherstellen", "Ctrl+Shift+Z", "global"),
     Action("tool.select", "Werkzeug Auswahl", "Esc", "canvas"),
     Action("tool.text", "Werkzeug Text anlegen", "T", "canvas"),
+    Action("image.insert", "Bild einfügen …", "Ctrl+Shift+I", "canvas"),
     Action("edit.cut", "Ausschneiden", "Ctrl+X", "canvas"),
     Action("edit.copy", "Kopieren", "Ctrl+C", "canvas"),
     Action("edit.paste", "Einfügen", "Ctrl+V", "canvas"),
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1309 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-17-bild-objekt-design.md src/labelwerk/document.py src/labelwerk/files.py src/labelwerk/gui/canvas.py src/labelwerk/gui/image_import.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/image.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/gui/tools.py src/labelwerk/layout.py src/labelwerk/shortcuts.py tests/gui/conftest.py tests/gui/test_gui_image.py tests/gui/test_gui_layout.py tests/test_image_object.py tests/test_image_place.py
git commit -m "GUI: Werkzeug Bild – aus Datei, Zwischenablage, Ablegen, Bild-Panel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Abnahme (manuell, durch den Nutzer)

- [ ] BILD → „Aus Datei …“: Internetmarke (PDF) → zugeschnitten, 1:1, frei verschiebbar neben dem Absender; Testdruck, Code mit dem Handy prüfen.
- [ ] PNG/JPG/SVG (Inkscape, mm) einfügen → richtige Größe; zu großes Bild → eingepasst + Hinweis.
- [ ] Strg+V: Bildschirmfoto aus der Zwischenablage → Bild; Text → Textrahmen; kopierte Datei → Bild; eigene Objekte → Objekte.
- [ ] Datei aus dem Dateimanager auf das Etikett ziehen.
- [ ] Strich/Foto, Schwelle, Umkehren, Zuschnitt, 1:1, Seitenverhältnis; jede Änderung einzeln rückgängig.
- [ ] Anfasser (Ecken/Kanten) halten das Seitenverhältnis; Layout: gleiche Größe, Ausrichten, Drehen mit Text+Bild.
