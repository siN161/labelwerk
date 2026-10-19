# Korrekturen aus der Abnahme – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Befunde aus der Abnahme des Nutzers beheben: Rand und Länge längs zum Endlosband (Vorschub des Druckers), kürzere Schriftliste, Reiter beim Start, Standard für neue Bilder, Bürodrucker ausblenden.

**Architecture:** Kern zuerst (labels/render/fonts/settings/cups/printers), Oberfläche dünn darauf (Arbeitsfläche, Reiter PAPIER/TEXT/BILD, Einstellungsdialog, Druckermenü), CLI-Optionen `--all`.

**Tech Stack:** Python ≥ 3.10, Pillow, pypdfium2, brother_ql-inventree 1.3.x, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-19-abnahme-korrekturen-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-ab-lin`), nach jedem Task volle Suite grün mit Exit-Code 0 (2536 → 2562 → 2583 → 2621 → 2665 → 2676); jeder Teil von einem Reviewer geprüft und korrigiert, danach ein Gesamtreview (Task 5).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Kern bleibt **Qt-frei** (`labels.py`, `render.py`, `layout.py`, `fonts.py`, `settings.py`, `cups.py`, `printers.py`, `cli.py`); kein Test erreicht echte Hardware, CUPS oder das Netz (`cups._run` ist in tests/conftest.py ersetzt); **nie den echten Drucker ansprechen**; keine echte Einstellungsdatei (conftest lenkt `XDG_CONFIG_HOME` um).
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten, ohne echte Dialoge; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen englisch mit `_()`, Deutsch in `po/de.po` (in den Patches enthalten); Kommentare deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Rand und Länge längs zum Endlosband

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/paper.py`
- Modify: `src/labelwerk/labels.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/render.py`
- Modify: `tests/_render_before_3d.py`
- Modify: `tests/gui/test_gui_layout.py`
- Modify: `tests/gui/test_gui_papier.py`
- Modify: `tests/gui/test_gui_placement.py`
- Modify: `tests/gui/test_gui_tape.py`
- Modify: `tests/gui/test_gui_window.py`
- Modify: `tests/test_document.py`
- Create: `tests/test_feed_margin.py`
- Modify: `tests/test_frame.py`
- Modify: `tests/test_image_object.py`
- Modify: `tests/test_layout.py`
- Modify: `tests/test_placement_render.py`
- Modify: `tests/test_rich_text.py`

**Interfaces / Produces:** `labels.Label.feed_margin`; `render._sheet` (Rand längs = max(0, Rand − feed_margin), `length_mm` = Stücklänge); `layout.align_objects(…, min_length=)`; Arbeitsfläche: ganzes Stück, Druckerstreifen hellgrau; Reiter PAPIER: Hinweis unter Rand (`objectName` note), Tooltip mit echten Streifen, Längenbereich vor dem Wert.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/_render_before_3d.py b/tests/_render_before_3d.py
index 0b2c0cb..a320588 100644
--- a/tests/_render_before_3d.py
+++ b/tests/_render_before_3d.py
@@ -79,11 +79,13 @@ def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
     side = max(0, margin - (label.total_width - label.width) // 2)
     if label.height is not None:
         margin = max(0, margin - (label.total_height - label.height) // 2)
+    # später: längs zählt der Vorschub des Druckers mit, feste Länge = abgeschnittenes Stück
+    margin = max(0, margin - label.feed_margin)
     across = label.width                      # quer zum Band (fest)
     side = min(side, max(0, (across - 2 * MARGIN) // 2))
     feed = label.height                       # in Bandlaufrichtung; None = automatisch
     if feed is None and doc.length_mm is not None:
-        feed = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
+        feed = min(max(round(doc.length_mm * DPI / 25.4) - 2 * label.feed_margin, min_len), max_len)
     if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
         margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
     obj = doc.objects[0] if doc.objects else TextObject("")
diff --git a/tests/gui/test_gui_layout.py b/tests/gui/test_gui_layout.py
index 6714691..55c86cf 100644
--- a/tests/gui/test_gui_layout.py
+++ b/tests/gui/test_gui_layout.py
@@ -386,10 +386,11 @@ def test_paper_align_along_growing_axis_is_enabled_with_hint(qtbot, orientation,
     assert hint not in panel.buttons[f"align.paper_{growing[0]}"].defaultAction().toolTip()
 
 
+@pytest.mark.parametrize("margin", [3, 6])             # 3 mm: Etikett auf Mindestlänge geklemmt
 @pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
-def test_paper_align_along_growing_axis_gives_equal_margins(qtbot, orientation):
+def test_paper_align_along_growing_axis_gives_equal_margins(qtbot, orientation, margin):
     vertical = orientation == "vertical"
-    doc = Document("62", length_mm=None, orientation=orientation, margin_mm=3, objects=[
+    doc = Document("62", length_mm=None, orientation=orientation, margin_mm=margin, objects=[
         TextObject("Zeile 1\nZeile 2", size_pt=14, x_mm=5, y_mm=6)])
     win = _window(qtbot, doc)
     win.canvas.set_selection([0])
diff --git a/tests/gui/test_gui_papier.py b/tests/gui/test_gui_papier.py
index 6b99586..4c52097 100644
--- a/tests/gui/test_gui_papier.py
+++ b/tests/gui/test_gui_papier.py
@@ -39,7 +39,7 @@ def test_margin_changes_document_and_length(window):
     paper.margin.setValue(5.0)
     window.render_now()
     assert window.doc.margin_mm == 5.0
-    assert window.image.height == before + 2 * (59 - 12)
+    assert window.image.height == before + 2 * (59 - 35)   # 1 mm lag ganz im Vorschub
 
 
 def test_horizontal_view_shows_handle_right_of_label(window):
@@ -99,3 +99,69 @@ def test_settings_warnings_appear_in_status_bar(qtbot):
     win = MainWindow(settings=Settings(warnings=["Einstellung 'start_zoom' ungültig"]))
     qtbot.addWidget(win)
     assert "start_zoom" in win.result.text()
+
+
+# --- Vorschub des Druckers längs zum Endlosband ------------------------------------------
+def test_margin_hint_when_margin_is_inside_the_printer_strip(window):
+    paper = window.panel("paper")
+    paper.margin.setValue(1.0)
+    assert paper.margin_hint.isVisibleTo(paper)
+    assert paper.margin_hint.text() == "Längs zum Band lässt der Drucker 3,0 mm frei."
+    # dezent wie eine Erläuterung (steht beim Standardrand immer da), nicht der Hinweis-Kasten
+    assert paper.margin_hint.objectName() != "hint" and "color" in paper.margin_hint.styleSheet()
+    paper.margin.setValue(3.0)                          # 35 Punkte: genau der Vorschub
+    assert not paper.margin_hint.isVisibleTo(paper)
+    paper.margin.setValue(1.0)
+    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))   # gestanzt: kein Vorschub
+    assert not paper.margin_hint.isVisibleTo(paper)
+
+
+@pytest.mark.parametrize("label, across, along", [("62", "1,5", "3,0"), ("62x29", "1,5", "3,0"),
+                                                  ("29", "1,5", "3,0"), ("d24", "2,0", "2,0")])
+def test_margin_tooltip_names_the_real_printer_strips(window, label, across, along):
+    paper = window.panel("paper")
+    paper.combo.setCurrentIndex(paper.combo.findData(label))
+    tip = paper.margin.toolTip()
+    assert f"quer rund {across} mm" in tip and f"längs rund {along} mm" in tip, tip
+
+
+def test_margin_tooltip_without_printer_strips(window):
+    window.doc.label_id = "57x32mm@203"                 # anderer Hersteller: ganz bedruckbar
+    paper = window.panel("paper")
+    paper.refresh()
+    assert paper.margin.toolTip() == "Abstand zur Papierkante ringsum"
+
+
+def test_refresh_sets_length_range_of_the_label_before_the_value(window):
+    """Etikett „18“ (Vorschub 14 Punkte) erlaubt kürzere Stücke als „62“ – der Wert der Datei
+    darf beim Anzeigen nicht an der Grenze des vorigen Etiketts hängen bleiben."""
+    paper = window.panel("paper")
+    window.doc.label_id, window.doc.length_mm = "18", 16.0
+    paper.refresh()
+    assert paper.length.value() == 16.0
+    paper.margin.setValue(2.0)
+    assert window.doc.length_mm == 16.0
+
+
+def test_length_field_means_the_cut_piece(window):
+    paper = window.panel("paper")
+    feed = 2 * 35 * 25.4 / 300
+    assert paper.length.minimum() == pytest.approx(round(12.7 + feed, 1))
+    assert paper.length.maximum() == pytest.approx(round(1000.0 + feed, 1), abs=0.1)
+    paper.length_auto.setChecked(False)
+    paper.length.setValue(50.0)
+    window.render_now()
+    assert window.doc.length_mm == 50.0
+    assert window.image.height == round(50 * MM) - 2 * 35
+
+
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_canvas_shows_printer_strip_before_and_after_the_print_image(window, orientation):
+    paper = window.panel("paper")
+    (paper.horizontal if orientation == "horizontal" else paper.vertical).setChecked(True)
+    window.render_now()
+    canvas = window.canvas
+    outline = canvas.outline.sceneBoundingRect()
+    sheet = canvas.sheet.mapRectToScene(canvas.sheet.rect())
+    assert sheet.top() - outline.top() == pytest.approx(35)        # Szene-y = Bandrichtung
+    assert outline.bottom() - sheet.bottom() == pytest.approx(35)
diff --git a/tests/gui/test_gui_placement.py b/tests/gui/test_gui_placement.py
index f4a4a83..47945b3 100644
--- a/tests/gui/test_gui_placement.py
+++ b/tests/gui/test_gui_placement.py
@@ -390,7 +390,7 @@ def test_object_outside_label_shows_status_hint(qtbot):
 
 def test_no_snapping_to_moving_end_of_auto_length_label(qtbot):
     doc = _doc(length_mm=None)
-    doc.margin_mm = 5                                       # Bandende 5 mm hinter „Zwei“
+    doc.margin_mm = 8                                       # Bandende 5 mm hinter „Zwei“ (8 − 3 mm Vorschub)
     win = _window(qtbot, doc)
     canvas = win.canvas
     ppm = canvas.px_per_mm()
diff --git a/tests/gui/test_gui_tape.py b/tests/gui/test_gui_tape.py
index dfa6456..c1d6b23 100644
--- a/tests/gui/test_gui_tape.py
+++ b/tests/gui/test_gui_tape.py
@@ -1,6 +1,6 @@
 """Arbeitsfläche: Restband, geschlossener Anfang, Schnittlinie am Ende, Randlinien (Abnahme 3d-1)."""
 import pytest
-from PySide6.QtCore import Qt
+from PySide6.QtCore import QPointF, Qt
 from PySide6.QtTest import QTest
 
 from labelwerk import layout
@@ -38,7 +38,8 @@ def test_tape_is_not_part_of_label_size_or_print_image(qtbot):
     win = _window(qtbot)
     before = render_document(win.doc).size
     assert win._shown_size == (before[0], before[1])
-    assert win.canvas.outline.sceneBoundingRect().height() == pytest.approx(before[1])
+    # das Stück: Druckbild plus Vorschub des Druckers an beiden Enden
+    assert win.canvas.outline.sceneBoundingRect().height() == pytest.approx(before[1] + 2 * 35)
     assert win.canvas.tape_rect().bottom() > before[1]
 
 
@@ -75,9 +76,10 @@ def test_canvas_draws_all_four_margins(qtbot, label, orientation):
     # Fläche in Leserichtung → Szene: gleiche Größe wie der Bereich, Rand in Bandrichtung sichtbar
     along = (area.y, win._shown_size[1] * 25.4 / 300 - area.bottom) if orientation == "vertical" \
         else (area.x, win._shown_size[0] * 25.4 / 300 - area.right)
-    # Rand 3 mm ab Papierkante: bei gestanzten Etiketten zählt der unbedruckbare Streifen mit
+    # Rand 3 mm ab Papierkante: der unbedruckbare Streifen (gestanzt) bzw. der Vorschub des
+    # Druckers (Endlosband) zählt mit
     label_ = get_label(label)
-    edge = 0 if label_.height is None else (label_.total_height - label_.height) // 2
+    edge = label_.feed_margin if label_.height is None else (label_.total_height - label_.height) // 2
     expected = max(0, round(3 * 300 / 25.4) - edge) * 25.4 / 300
     assert along[0] == pytest.approx(expected, abs=0.1)
     assert along[1] == pytest.approx(expected, abs=0.1)
@@ -100,3 +102,35 @@ def test_orientation_names_are_plain(qtbot):
     panel = win.panel("paper")
     assert "Querformat" in panel.horizontal.toolTip() and "Hochformat" in panel.vertical.toolTip()
     assert "Text" not in panel.horizontal.toolTip() + panel.vertical.toolTip()
+
+
+@pytest.mark.parametrize("label", ["62", "62x29"])
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_canvas_shades_strips_the_printer_does_not_print(qtbot, label, orientation):
+    """Quer (total_width − width) / 2, längs der Vorschub bzw. der Rand des gestanzten Etiketts:
+    hellgrau, nur Anzeige – keine Klicks, unter dem Inhalt, nicht im Druckbild (Szene-y =
+    Bandrichtung, auch bei „horizontal“)."""
+    win = _window(qtbot, label=label, orientation=orientation, length=None)
+    canvas = win.canvas
+    strips = canvas.unprintable
+    assert strips.acceptedMouseButtons() == Qt.MouseButton.NoButton
+    lbl = get_label(label)
+    box = canvas.outline.sceneBoundingRect()
+    across = (lbl.total_width - lbl.width) / 2
+    along = lbl.feed_margin if lbl.height is None else (lbl.total_height - lbl.height) / 2
+    path, mid = strips.path(), box.center()
+    assert path.contains(QPointF(box.left() + across / 2, mid.y()))
+    assert path.contains(QPointF(box.right() - across / 2, mid.y()))
+    assert path.contains(QPointF(mid.x(), box.top() + along / 2))
+    assert path.contains(QPointF(mid.x(), box.bottom() - along / 2))
+    assert not path.contains(mid)
+    assert not path.contains(QPointF(box.left() + across + 1, box.top() + along + 1))
+    stack = canvas.scene().items()                      # oben zuerst
+    assert stack.index(canvas.sheet) < stack.index(strips) < stack.index(canvas.outline)
+    assert render_document(win.doc).size == (win._shown_size if orientation == "vertical"
+                                              else win._shown_size[::-1])
+
+
+def test_round_label_has_no_shaded_strip_inside_the_circle(qtbot):
+    win = _window(qtbot, label="d24")
+    assert not win.canvas.unprintable.path().contains(win.canvas.outline.sceneBoundingRect().center())
diff --git a/tests/gui/test_gui_window.py b/tests/gui/test_gui_window.py
index a47f64b..7adf5d0 100644
--- a/tests/gui/test_gui_window.py
+++ b/tests/gui/test_gui_window.py
@@ -65,7 +65,8 @@ def test_fixed_length_sets_preview_height(window):
     paper.length_auto.setChecked(False)
     paper.length.setValue(50.0)
     window.render_now()
-    assert window.image.height == round(50 * MM)
+    assert window.image.height == round(50 * MM) - 2 * 35          # Druckbild ohne Vorschub
+    assert window.canvas.label_height() == round(50 * MM)           # Arbeitsfläche: das Stück
 
 
 def _mouse(view, kind, scene_point, buttons):
@@ -95,9 +96,9 @@ def test_dragging_handle_sets_fixed_length(window):
     assert paper.length.value() == 40.0
 
 
-def test_dragging_below_minimum_stops_at_12_7_mm(window):
-    _drag_handle(window, 2 * MM)
-    assert window.doc.length_mm == pytest.approx(12.7, abs=0.01)
+def test_dragging_below_minimum_stops_at_12_7_mm_plus_feed(window):
+    _drag_handle(window, 2 * MM)        # Druckbild 12,7 mm, das Stück hat 2 × 35 Punkte Vorschub
+    assert window.doc.length_mm == pytest.approx(12.7 + 2 * 35 / MM, abs=0.01)
 
 
 def test_double_click_on_handle_resets_to_automatic(window):
@@ -215,7 +216,7 @@ def test_drag_without_motion_does_not_drift_and_renders_only_on_release(window,
     end = QPointF(start.x(), start.y() + 10 * MM)
     _mouse(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
     assert not canvas.is_dragging()
-    assert window.image.height == round(first * MM)
+    assert window.image.height == round(first * MM) - 2 * 35
     assert canvas.label_height() == pytest.approx(round(first * MM))
 
 
diff --git a/tests/test_document.py b/tests/test_document.py
index 221c9a8..de7e91c 100644
--- a/tests/test_document.py
+++ b/tests/test_document.py
@@ -16,7 +16,7 @@ def test_render_document_equals_render_text():
 
 def test_fixed_length_sets_height():
     doc = Document("62", length_mm=50, objects=[TextObject("Hallo")])
-    assert render_document(doc).height == 591
+    assert render_document(doc).height == 591 - 2 * 35   # Stück 50 mm: Vorschub an beiden Enden
 
 
 def test_length_is_clamped_to_model_limits():
@@ -79,7 +79,7 @@ def test_horizontal_auto_font_matches_vertical():
 
 def test_horizontal_fixed_length():
     doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("Hallo")])
-    assert render_document(doc).size == (696, 591)
+    assert render_document(doc).size == (696, 591 - 2 * 35)
 
 
 def test_horizontal_die_cut_keeps_print_size():
@@ -89,9 +89,10 @@ def test_horizontal_die_cut_keeps_print_size():
 
 def test_margin_extends_auto_length():
     def height(margin):
-        doc = Document("62", margin_mm=margin, objects=[TextObject("A", size_pt=48)])
+        doc = Document("62", margin_mm=margin, objects=[TextObject("A", size_pt=100)])
         return render_document(doc).height
-    assert height(5) - height(1) == 2 * (59 - 12)        # 5 mm = 59 Punkte, 1 mm = 12
+    # 5 mm = 59 Punkte, davon 35 Vorschub des Druckers; 1 mm liegt ganz im Vorschub
+    assert height(5) - height(1) == 2 * (59 - 35)
 
 
 def test_margin_is_clamped_to_20_mm():
@@ -140,10 +141,12 @@ def test_margin_larger_than_die_cut_label_is_limited():
 
 def test_margin_applies_on_every_side():
     from labelwerk.render import label_margins
-    # ab Papierkante: quer lässt der Drucker 18 Punkte (1,5 mm) frei, gestanzt 62x29 längs 35
-    assert label_margins(Document("62")) == (0, 12)                # 1 mm: quer schon im Streifen
-    assert label_margins(Document("62", margin_mm=3)) == (35 - 18, 35)
-    assert label_margins(Document("62", orientation="horizontal", margin_mm=2)) == (24, 6)
+    # ab Papierkante: quer lässt der Drucker 18 Punkte (1,5 mm) frei, längs (Endlosband) 35
+    # Punkte Vorschub, gestanzt 62x29 längs 35
+    assert label_margins(Document("62")) == (0, 0)                 # 1 mm: schon im Streifen
+    assert label_margins(Document("62", margin_mm=3)) == (35 - 18, 0)
+    assert label_margins(Document("62", margin_mm=4)) == (47 - 18, 47 - 35)
+    assert label_margins(Document("62", orientation="horizontal", margin_mm=2)) == (0, 6)
     assert label_margins(Document("62x29", margin_mm=4)) == (47 - 18, 47 - 35)
     assert label_margins(Document("62x29")) == (0, 0)
 
diff --git a/tests/test_feed_margin.py b/tests/test_feed_margin.py
new file mode 100644
index 0000000..bbf32c7
--- /dev/null
+++ b/tests/test_feed_margin.py
@@ -0,0 +1,54 @@
+"""Längs zum Endlosband lässt der Brother-Drucker an Anfang und Ende je ``feed_margin`` Punkte frei
+(brother_ql, ESC i d: 35 Punkte ≈ 3 mm). Der Rand zählt diesen Streifen mit (wie quer den
+unbedruckbaren Streifen), eine feste Länge meint das abgeschnittene Stück."""
+import pytest
+
+from labelwerk.document import Document, TextObject
+from labelwerk.labels import get_label, length_limits, sized_id
+from labelwerk.render import label_margins, label_size, render_document
+
+
+def test_feed_margin_of_labels():
+    assert get_label("62").feed_margin == 35            # Endlosband: Vorschub des Druckers
+    assert get_label("29").feed_margin == 35
+    assert get_label("62x29").feed_margin == 0          # gestanzt: das Etikett selbst begrenzt
+    assert get_label("d24").feed_margin == 0
+    assert get_label(sized_id(57, 32, 203)).feed_margin == 0   # andere Hersteller
+
+
+@pytest.mark.parametrize("orientation, along", [("vertical", 1), ("horizontal", 0)])
+def test_margin_along_tape_counts_printer_strip(orientation, along):
+    small = Document("62", orientation=orientation, margin_mm=1.0, objects=[TextObject("A")])
+    assert label_margins(small)[along] == 0             # 1 mm liegt im Streifen des Druckers
+    wide = Document("62", orientation=orientation, margin_mm=5.0, objects=[TextObject("A")])
+    assert label_margins(wide)[along] == round(5 * 300 / 25.4) - 35
+    assert label_margins(wide)[1 - along] == round(5 * 300 / 25.4) - 18   # quer wie bisher
+
+
+def test_margin_on_die_cut_unchanged():
+    doc = Document("62x29", margin_mm=3.0, objects=[TextObject("A")])
+    label = get_label("62x29")
+    m = round(3 * 300 / 25.4)
+    assert label_margins(doc) == (m - (label.total_width - label.width) // 2,
+                                  m - (label.total_height - label.height) // 2)
+
+
+def test_fixed_length_is_the_cut_piece():
+    doc = Document("62", length_mm=50.0, objects=[TextObject("A")])
+    assert label_size(doc)[1] == round(50 * 300 / 25.4) - 2 * 35
+    assert render_document(doc).size[1] == round(50 * 300 / 25.4) - 2 * 35
+
+
+def test_fixed_length_stays_within_model_limits():
+    min_len, max_len = length_limits("QL-600")
+    short = Document("62", length_mm=1.0, objects=[TextObject("A")])
+    assert label_size(short)[1] == min_len              # Grenzen gelten für das Druckbild
+    long = Document("62", length_mm=5000.0, objects=[TextObject("A")])
+    assert label_size(long)[1] == max_len
+
+
+def test_automatic_length_adds_no_margin_inside_printer_strip():
+    text = Document("62", margin_mm=1.0, objects=[TextObject("A", size_pt=60)])
+    wide = Document("62", margin_mm=5.0, objects=[TextObject("A", size_pt=60)])
+    # 5 mm: 2 × (59 − 35) Punkte mehr als 1 mm (dort ist der Rand ganz im Streifen)
+    assert label_size(wide)[1] - label_size(text)[1] == 2 * (round(5 * 300 / 25.4) - 35)
diff --git a/tests/test_frame.py b/tests/test_frame.py
index 59a496a..37732d8 100644
--- a/tests/test_frame.py
+++ b/tests/test_frame.py
@@ -128,7 +128,10 @@ def test_auto_length_grows_by_the_frame():
     framed = label_size(Document("62", objects=text, frame=Frame("single")))
     assert framed == (plain[0], plain[1] + 2 * (LW + 12))        # Linie + 1 mm Innenabstand
     img = _image(Frame("single"), label="62", objects=text, margin_mm=1)
-    assert _black(img, 300, framed[1] - 13) and not _black(img, 300, framed[1] - 12)
+    assert _black(img, 300, framed[1] - 1)             # längs liegt 1 mm im Vorschub des Druckers
+    img = _image(Frame("single"), label="62", objects=text, margin_mm=4)
+    framed = label_size(Document("62", objects=text, frame=Frame("single"), margin_mm=4))
+    assert _black(img, 300, framed[1] - 13) and not _black(img, 300, framed[1] - 12)   # 47 − 35
 
 
 def test_automatic_text_stays_inside_the_frame_and_shrinks():
@@ -257,9 +260,9 @@ def test_corner_radius_is_two_millimetres():
 
 def test_corner_radius_is_at_most_a_quarter_of_the_shorter_side():
     doc = Document("12", objects=[TextObject("A", size_pt=6)], frame=Frame("single", rounded=True),
-                   margin_mm=2.5)                      # 30 Punkte: quer 30 − 18 = 12, längs 30
+                   margin_mm=2.5)                      # 30 Punkte: quer 30 − 18 = 12, längs 30 − 35
     img = render_document(doc)                         # quer 82 Punkte → Radius 20
-    assert _first_black(img, 12, 30) == 30 + 16
+    assert _first_black(img, 12, 0) == 16
 
 
 def test_double_rounded_lines_stay_concentric():
@@ -277,7 +280,7 @@ def test_round_label_inner_room_is_the_square_in_the_circle():
 
 def test_corners_without_room_give_a_message():
     with pytest.raises(ValueError, match="Rahmen passt nicht aufs Etikett"):
-        render_document(Document("62", frame=Frame("corners", inset_mm=5.5, line_mm=0.1,
+        render_document(Document("62", frame=Frame("corners", inset_mm=6.2, line_mm=0.1,
                                                     padding_mm=0)))
 
 
diff --git a/tests/test_image_object.py b/tests/test_image_object.py
index 12ca34c..87fe63b 100644
--- a/tests/test_image_object.py
+++ b/tests/test_image_object.py
@@ -216,8 +216,7 @@ def test_invalid_image_settings_raise_at_render(field, value, message):
 def test_image_grows_auto_length():
     obj = _image(x_mm=1, y_mm=10)
     doc = Document("62", objects=[obj])
-    margin = round(1.0 * DPI / 25.4)
-    assert label_size(doc) == (696, _dots(10) + 300 + margin)
+    assert label_size(doc) == (696, _dots(10) + 300)    # 1 mm Rand liegt im Vorschub des Druckers
 
 
 def test_preview_equals_print_with_text_and_images():
diff --git a/tests/test_layout.py b/tests/test_layout.py
index a28745f..3b707fa 100644
--- a/tests/test_layout.py
+++ b/tests/test_layout.py
@@ -881,6 +881,30 @@ def test_align_to_paper_along_growing_axis_puts_group_at_start_margin(orientatio
         assert gap(rects) == pytest.approx(gap(old), abs=0.1)             # Abstand bleibt
 
 
+@pytest.mark.parametrize("orientation, modes", [
+    ("vertical", ("top", "vcenter", "bottom")), ("horizontal", ("left", "hcenter", "right"))])
+def test_align_to_paper_along_growing_axis_centers_short_content_on_minimum_length(orientation,
+                                                                                  modes):
+    """Inhalt + Rand kürzer als die Mindestlänge: das Etikett bleibt so lang – die Auswahl
+    steht mittig darin (gleiche Ränder an beiden Enden)."""
+    vertical = orientation == "vertical"
+    min_mm = _mm(layout.length_limits("QL-600")[0])
+    for mode in modes:
+        doc = Document("62", orientation=orientation, margin_mm=3,
+                       objects=[TextObject("A", size_pt=10, x_mm=7, y_mm=9)])
+        rendered = [render_object(o, doc) for o in doc.objects]
+        area = layout.printable_area(doc)
+        moved = layout.align_objects(doc.objects, rendered, mode, area,
+                                     grow=layout.growing_axis(doc), min_length=min_mm)
+        doc.objects = moved
+        box = layout.object_rect(render_object(moved[0], doc))
+        start, end = (box.y, box.bottom) if vertical else (box.x, box.right)
+        w, h = layout.label_size(doc)
+        length = _mm(h if vertical else w)
+        assert length == pytest.approx(min_mm)
+        assert length - end == pytest.approx(start, abs=2 * 25.4 / DPI)
+
+
 @pytest.mark.parametrize("grow, across", [
     ("y", ("left", "hcenter", "right")), ("x", ("top", "vcenter", "bottom"))])
 def test_align_to_paper_across_still_works_on_growing_label(grow, across):
diff --git a/tests/test_placement_render.py b/tests/test_placement_render.py
index 6f929de..aef6277 100644
--- a/tests/test_placement_render.py
+++ b/tests/test_placement_render.py
@@ -5,14 +5,19 @@ from PIL import Image
 import _render_before_3d as before
 from labelwerk.document import ROTATIONS, Document, Paragraph, Span, TextObject
 from labelwerk.labels import DPI, length_limits
-from labelwerk.render import (RenderedObject, finish_object, label_size, prepare_object,
-                             render_document, render_object)
+from labelwerk.render import (RenderedObject, finish_object, label_margins, label_size,
+                             prepare_object, render_document, render_object)
 
 
 def _dots(mm):
     return round(mm * DPI / 25.4)
 
 
+def _along(doc):
+    """Rand in Bandlaufrichtung (der Vorschub des Druckers zählt mit)."""
+    return label_margins(doc)[0 if doc.orientation == "horizontal" else 1]
+
+
 def _ink_box(img):
     """Tintenbox (Pixel dunkler als 50 %)."""
     return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()
@@ -95,14 +100,14 @@ def test_render_object_reports_frame_on_label():
 def test_positioned_object_never_raises_text_too_large():
     obj = TextObject("W" * 60, size_pt=40, x_mm=0, y_mm=0)
     img = render_document(Document("29", length_mm=50, objects=[obj]))
-    assert img.size == (306, _dots(50))
+    assert img.size == (306, _dots(50) - 2 * 35)        # Stück 50 mm, Vorschub an beiden Enden
 
 
 def test_object_beyond_label_is_clipped():
     objs = [TextObject("Unten", size_pt=40, x_mm=-5, y_mm=25),
             TextObject("Rechts", size_pt=40, x_mm=55, y_mm=2)]
     img = render_document(Document("62", length_mm=30, objects=objs))
-    assert img.size == (696, _dots(30))
+    assert img.size == (696, _dots(30) - 2 * 35)
     assert _ink_box(img) is not None
 
 
@@ -151,14 +156,14 @@ def test_auto_length_grows_with_farthest_object():
     far = TextObject("B", size_pt=20, x_mm=5, y_mm=60)
     doc = Document("62", objects=[near, far])
     ro = render_object(far, doc)
-    assert render_document(doc).height == ro.y + ro.h + _dots(doc.margin_mm)
+    assert render_document(doc).height == ro.y + ro.h + _along(doc)
 
 
 def test_auto_length_horizontal_uses_x():
     obj = TextObject("B", size_pt=20, x_mm=70, y_mm=5)
     doc = Document("62", orientation="horizontal", objects=[obj])
     ro = render_object(obj, doc)
-    assert render_document(doc).height == ro.x + ro.w + _dots(doc.margin_mm)
+    assert render_document(doc).height == ro.x + ro.w + _along(doc)
 
 
 def test_auto_length_keeps_room_for_unpositioned_object():
@@ -266,7 +271,7 @@ def test_fit_without_feed_size_uses_text_extent_on_auto_length(orientation, fram
     ro = render_object(obj, doc)
     length = render_document(doc).height
     start, extent = (ro.y, ro.h) if orientation == "vertical" else (ro.x, ro.w)
-    assert length == max(start + extent + _dots(doc.margin_mm), length_limits("QL-600")[0])
+    assert length == max(start + extent + _along(doc), length_limits("QL-600")[0])
     assert length < _dots(60)                       # nicht die Höchstlänge
     ink = _ink_box(ro.image)
     assert ink[3] - ink[1] > 0.8 * ro.h or ink[2] - ink[0] > 0.8 * ro.w   # Text füllt den Rahmen
diff --git a/tests/test_rich_text.py b/tests/test_rich_text.py
index 8d64611..2478821 100644
--- a/tests/test_rich_text.py
+++ b/tests/test_rich_text.py
@@ -14,7 +14,8 @@ def _ink(img):
 
 
 def _old_render(text: str, size: int | None = None) -> Image.Image:
-    """Der Algorithmus vor Etappe 3a (Pillow multiline_text, zentriert), Etikett 62 vertikal."""
+    """Der Algorithmus vor Etappe 3a (Pillow multiline_text, zentriert), Etikett 62 vertikal;
+    Rand 1 mm: quer und längs ganz im Streifen, den der Drucker freilässt (kein eigener Rand)."""
     def box(font):
         probe = ImageDraw.Draw(Image.new("1", (1, 1)))
         return tuple(round(v) for v in probe.multiline_textbbox((0, 0), text, font=font,
@@ -22,13 +23,13 @@ def _old_render(text: str, size: int | None = None) -> Image.Image:
 
     def fits(s):
         l, t, r, b = box(fonts.load(DEJAVU_BOLD, s))
-        return r - l <= 696 and b - t <= 11811 - 24     # quer kein Rand: Drucker lässt 1,5 mm
+        return r - l <= 696 and b - t <= 11811     # kein Rand: Drucker lässt 1,5 mm bzw. 3 mm
 
     start = size or max(10, 696 // 5)
     best = start if fits(start) else max(s for s in range(8, start) if fits(s))
     font = fonts.load(DEJAVU_BOLD, best)
     l, t, r, b = box(font)
-    height = min(max(b - t + 24, 150), 11811)
+    height = min(max(b - t, 150), 11811)
     img = Image.new("RGB", (696, height), "white")
     ImageDraw.Draw(img).multiline_text(((696 - (r - l)) // 2 - l, (height - (b - t)) // 2 - t),
                                        text, fill="black", font=font, align="center")
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen bzw. geänderten Tests (tests/test_feed_margin.py, Fälle in tests/gui/test_gui_papier.py u. a.) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 0574c7f..143f604 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -11,7 +11,9 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Druckererkennung automatisch über `/sys/class/usbmisc/lp*` (Vendor-ID `04f9`), Gerät liegt aktuell auf `/dev/usb/lp1`.
 - GUI-MVP: `labelwerk-gui` (Papier/Text, Live-Vorschau, Etikettform, Länge ziehen, Drucken im Hintergrund).
 - `labelwerk install-desktop` trägt die GUI mit Icon im Starter ein (XDG, `~/.local/share`); App-ID `labelwerk`.
-- Papier: Ausrichtung H/V, Ränder (ringsum ab Papierkante; quer lässt der Drucker ~1,5 mm frei), Medium prüfen (GUI + `labelwerk media`), Einstellungen (`settings.json`, GUI-Dialog), Live-Druckererkennung.
+- Papier: Ausrichtung H/V, Ränder (ringsum ab Papierkante; die Streifen, die der Drucker freilässt, zählen mit: quer
+  ~1,5 mm, längs zum Endlosband ~3 mm Vorschub – Hinweis unter Rand; feste Länge = abgeschnittenes Stück samt
+  Vorschub, ältere Dateien drucken dadurch ~6 mm kürzer; Arbeitsfläche zeigt die Streifen hellgrau), Medium prüfen (GUI + `labelwerk media`), Einstellungen (`settings.json`, GUI-Dialog), Live-Druckererkennung.
 - Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.
 - Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
 - Direkt auf dem Etikett schreiben (Etappe 3d-1b): Schreibmodus (Text anlegen + Klick bzw. Doppelklick, Esc/Klick daneben beendet), Schreibmarke/Markierung aus dem Kern-Zeilensatz, Markieren mit Maus und Tastatur, eine Bearbeitung = ein Rückgängig-Schritt, Rahmen wächst an der Kante der Textposition; Feld INHALT entfällt.
@@ -56,12 +58,14 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 src/labelwerk/
   labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager): labels_for_model nach
               printers.capabilities (Breite, restricted_to_models, ohne PT-Bänder, 62red nur Zweifarb-Modelle);
-              Label.two_color, Label.dpi (Brother 300); Etiketten anderer Drucker als ID „BxHmm@dpi“ (sized_id/sized_label,
+              Label.two_color, Label.dpi (Brother 300), Label.feed_margin (Endlosband: Vorschub des Druckers an
+              Anfang und Ende, brother_ql, 35 Punkte; sonst 0); Etiketten anderer Drucker als ID „BxHmm@dpi“ (sized_id/sized_label,
               fest, ganz bedruckbar, eine Schreibweise; get_label versteht sie ohne Drucker), mm_text (Maß mit Komma);
               cups:NAME → Etiketten des Treibers, zpl:DPI → zpl.MEDIA
   render.py   render_text(text, label_id, size_pt, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
               render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
-              compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise:
+              compose(rendered, size, orientation) -> Druckbild; label_size/label_margins (_sheet: Rand längs ohne
+              feed_margin, length_mm = Stück → Druckbild = Länge − 2·feed_margin); schrittweise:
               prepare_object, label_size(prepared=), finish_object; span_dots
               Renderer (Qt-frei, für die GUI): render(doc, model, placeholders) -> Rendered(size, objects, image, frame,
               errors) – placeholders (Arbeitsfläche): Barcode, der sich nicht kodieren lässt → schraffierter Platzhalter
@@ -179,7 +183,8 @@ src/labelwerk/
               SVG/PNG, ohne versteckte), add_recent; Archiv fehlt/defekt: OSError/BadZipFile/KeyError/ValueError (GUI: Meldung „Symbol-Bibliothek nicht lesbar“)
   media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
   layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
-              growing_axis (Endlosband wächst mit), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
+              growing_axis (Endlosband wächst mit; align_objects am Papier: Anfang des Bereichs, auf Mindestlänge mittig –
+              min_length), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
               Schreibmodus: to_object/from_object (Etikett ↔ ungedrehtes Objekt, Druckpunkte), anchor_after_edit/anchor_align
               Bilder wie Text mit fester Rahmengröße; keep_aspect (Anfasser mit keep_ratio); Schrift-Funktionen: TypeError bei Bildern
               Bild einfügen/einstellen: insert_frame (Mitte bzw. Ablagepunkt, zu groß → proportional eingepasst, Endlosband
@@ -250,7 +255,8 @@ src/labelwerk/
     panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
     panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen), Farbe (SCHWARZ immer,
                     ROT nur 62red auf einem Zweifarb-Modell: set_red_available; Signal color_chosen)
-    canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
+    canvas.py       Etikett in echter Größe (Endlosband: Stück mit Vorschub, Länge ziehen = Stück), unbedruckbare Streifen
+                    hellgrau (unprintable, keine Klicks), Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
                     Zierrahmen (frame_item unter den Objekten, keine Klicks; Einrasten am Innenraum);
                     Ablegen von Dateien/Bilddaten (Daten im dropEvent kopiert, Signal dropped danach, mm) und Symbolen (symbol_dropped); Anfasser-Vorschau mit
                     keep_aspect (Bild, dieselbe Regel wie layout.resize: fest ist, was der Anfasser sagt)
diff --git a/README.md b/README.md
index c62e65f..dbb880a 100644
--- a/README.md
+++ b/README.md
@@ -84,7 +84,7 @@ labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entf
 
 Aufbau wie im P-touch Editor: Werkzeugleiste (Datei, Papier, Text, Bild, Barcode, Layout, Serie), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Unten links steht der Drucker: ein Klick wählt einen anderen (bei mehreren) oder trägt einen Netzwerkdrucker ein; während eine Serie vorbereitet oder gedruckt wird, bricht ABBRECHEN sie ab (beim Drucken nach dem laufenden Teil, bis zu 10 Etiketten). Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.
 
-Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil); gespeichert in `~/.config/labelwerk/settings.json`.
+Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). Der Rand zählt ab Papierkante: Die Streifen, die der Drucker ohnehin freilässt (quer ~1,5 mm, längs zum Endlosband ~3 mm), zählen mit und sind auf der Arbeitsfläche hellgrau. Die Länge eines Endlosband-Etiketts ist das abgeschnittene Stück (Dateien älterer Versionen drucken dadurch ~6 mm kürzer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil); gespeichert in `~/.config/labelwerk/settings.json`.
 
 Text: Geschrieben wird direkt auf dem Etikett. Mit dem Knopf „A“ (Text anlegen, Taste T) und einem Klick entsteht ein Rahmen, in den man sofort tippt (linksbündig ab dem Klickpunkt); ein Doppelklick auf einen Text setzt die Schreibmarke an die Klickstelle (ein einfacher Klick wählt den Rahmen nur); bei gewähltem Rahmen startet **F2** oder **Enter** den Schreibmodus mit der Schreibmarke am Textende. Im Schreibmodus markiert Ziehen Text, Doppelklick ein Wort, Umschalt+Klick erweitert; Pfeiltasten, Pos1/Ende, Entf, Enter, Strg+A/C/X/V und Strg+Z wirken auf den Text. **Esc** oder ein Klick neben den Rahmen beendet den Schreibmodus – die ganze Bearbeitung ist dann ein Schritt für Rückgängig. Ohne feste Rahmengröße wächst der Rahmen beim Tippen an der Kante seiner Textposition (links, rechts, Mitte). Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition wirken zeichenweise wie im P-touch Editor: im Schreibmodus auf die Markierung bzw. das Weitertippen, sonst auf den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.
 
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index 8970f57..9d111ce 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -125,8 +125,9 @@ def _parser() -> argparse.ArgumentParser:
                     help=_("vertical: portrait (reading direction across the tape), horizontal: "
                            "landscape (along the tape); default from the settings"))
     pr.add_argument("--margin", type=_margin, metavar="MM",
-                    help=_("margin all around from the paper edge in mm (default from the "
-                           "settings)"))
+                    help=_("margin all around from the paper edge in mm – the strips the printer "
+                           "leaves free count (about 1.5 mm across, 3 mm along a continuous "
+                           "tape; default from the settings)"))
     _add_output_options(pr)
 
     pf = sub.add_parser("print-file", help=_("print a PDF/image 1:1"))
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index e97815f..c6a5f40 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -41,6 +41,7 @@ _HANDLE_CURSORS = {
 }
 _GUIDE_COLOR = QColor("#E53935")
 _TAPE_COLOR = QColor("#BDBDBD")    # heller als die Arbeitsfläche, in jedem Design lesbar
+_UNPRINTABLE_COLOR = QColor("#EBEBEB")   # unbedruckbarer Streifen: zwischen Etikett und Restband
 TOOL_MODES = ("select", "text")   # Auswahl-Pfeil, „Text anlegen“
 _EDIT_REACH_PX = 3                # Schreibmodus: Klick so knapp neben dem Rahmen zählt noch hinein
 _SELECTION_ALPHA = 90             # Markierung: Systemfarbe zu ≈ 35 % deckend
@@ -198,7 +199,7 @@ class Canvas(QGraphicsView):
         horizontal = orientation == "horizontal"
         pw, ph = (height, width) if horizontal else (width, height)   # Druckbild
         tw = label.total_width
-        th = label.total_height or ph
+        th = label.total_height or ph + 2 * label.feed_margin   # Endlosband: Stück mit Vorschub
         path = QPainterPath()
         if label.shape == "round":
             path.addEllipse(0, 0, tw, th)
@@ -209,6 +210,13 @@ class Canvas(QGraphicsView):
         self.outline = scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
 
         ox, oy = (tw - pw) / 2, (th - ph) / 2
+        # Streifen, die der Drucker nicht bedruckt (quer, längs Vorschub bzw. Etikettrand):
+        # hellgrau, nur Anzeige – unter dem Etikettinhalt, ohne Klicks, nicht im Druckbild
+        printed = QPainterPath()
+        printed.addRect(QRectF(ox, oy, pw, ph))
+        self.unprintable = scene.addPath(path.subtracted(printed), QPen(Qt.PenStyle.NoPen),
+                                         QBrush(_UNPRINTABLE_COLOR))
+        self.unprintable.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
         self.sheet = QGraphicsRectItem(0, 0, width, height)
         self.sheet.setPen(QPen(Qt.PenStyle.NoPen))
         # Leserichtung → Druck: bei „horizontal“ 90° im Uhrzeigersinn wie render_document
@@ -517,9 +525,11 @@ class Canvas(QGraphicsView):
         return self._drag in ("length", "move", "resize")
 
     def snap_length(self, scene_y: float) -> float:
-        """Szene-y der Unterkante → Länge in mm (Raster 0,5 mm, innerhalb der Modellgrenzen)."""
+        """Szene-y der Unterkante → Länge des Stücks in mm (Raster 0,5 mm, innerhalb der
+        Modellgrenzen – sie gelten für das Druckbild, das Stück hat den Vorschub dazu)."""
         mm = round(scene_y / self.mm * 2) / 2
-        return min(max(mm, self.min_mm), self.max_mm)
+        feed = 2 * self.label.feed_margin / self.mm if self.label is not None else 0.0
+        return min(max(mm, self.min_mm + feed), self.max_mm + feed)
 
     def mousePressEvent(self, event) -> None:
         if event.button() != Qt.MouseButton.LeftButton:
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 4efada7..efb7bb7 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -28,7 +28,7 @@ from ..document import MAX_BARCODE_DATA, BarcodeObject, Document, ImageObject, S
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
 from ..i18n import N_, _, ngettext
-from ..labels import DPI, get_label, labels_for_model
+from ..labels import DPI, get_label, labels_for_model, length_limits
 from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, change_label, exact_rect,
                       fill_anchored, frame_area, growing_axis, insert_placement, match_objects,
                       maximize_object, move, new_barcode, object_rect, objects_outside, outside_indices,
@@ -919,8 +919,11 @@ class MainWindow(QMainWindow):
     def align_selected(self, mode: str, paper: bool = False) -> None:
         """Auswahl aneinander bzw. am bedruckbaren Bereich (mit Zierrahmen: an seinem
         Innenraum) ausrichten."""
+        label = get_label(self.doc.label_id)
+        min_length = length_limits(self.model)[0] * 25.4 / label.dpi
         self._change_selected(lambda objs, rendered: align_objects(
-            objs, rendered, mode, self._paper_area() if paper else None, growing_axis(self.doc)))
+            objs, rendered, mode, self._paper_area() if paper else None, growing_axis(self.doc),
+            min_length))
 
     def _paper_area(self) -> Rect:
         """Fläche für „am Etikett“ (Ausrichten, Maximieren): Innenraum des Zierrahmens, sonst
diff --git a/src/labelwerk/gui/panels/paper.py b/src/labelwerk/gui/panels/paper.py
index 9be0f9f..ed171f4 100644
--- a/src/labelwerk/gui/panels/paper.py
+++ b/src/labelwerk/gui/panels/paper.py
@@ -11,7 +11,7 @@ from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout,
 from ... import layout
 from ...document import FRAME_LINE_MM, MAX_FRAME_MM, MAX_MARGIN_MM, Document, Frame
 from ...i18n import N_, _
-from ...labels import DPI, get_label, labels_for_model, length_limits, mm_text
+from ...labels import DPI, format_mm, get_label, labels_for_model, length_limits, mm_text
 from ...media import Media
 from ...printer import DEFAULT_MODEL
 from ...render import frame_mask
@@ -24,6 +24,7 @@ FRAME_TITLES = ((N_("No border"), None), (N_("Single"), "single"), (N_("Double")
                 (N_("Corners only"), "corners"))
 FRAME_ICON = QSize(56, 22)
 ROUND_TIP = N_("On round labels every border becomes a circle.")
+NOTE_STYLE = "color: #666666; font-size: 11px; font-weight: 400; border: none; padding: 0;"
 
 
 def frame_icon(style: str | None) -> QIcon:
@@ -105,9 +106,12 @@ class PaperPanel(Panel):
         self.margin.setDecimals(1)
         self.margin.setSingleStep(0.5)
         self.margin.setRange(0.0, MAX_MARGIN_MM)
-        self.margin.setToolTip(_("Distance from the paper edge all around (across the tape the "
-                                 "printer leaves about 1.5 mm free anyway)"))
         self.layout_.addWidget(self.margin)
+        self.margin_hint = QLabel()                 # Rand längs kleiner als der Vorschub
+        self.margin_hint.setObjectName("note")
+        self.margin_hint.setStyleSheet(NOTE_STYLE)   # dezent, in jedem Design
+        self.margin_hint.setWordWrap(True)
+        self.layout_.addWidget(self.margin_hint)
 
         self.section(_("Border"))
         self.frame_style = QComboBox()
@@ -206,8 +210,14 @@ class PaperPanel(Panel):
             self.combo.model().item(self.combo.count() - 1).setEnabled(False)
 
     def _set_length_range(self) -> None:
+        """Länge des Stücks: Grenzen des Modells (für das Druckbild) plus Vorschub an beiden
+        Enden."""
         min_len, max_len = length_limits(self.model)
-        self.length.setRange(round(min_len * 25.4 / DPI, 1), round(max_len * 25.4 / DPI, 1))
+        feed = 2 * get_label(self.doc.label_id).feed_margin
+        blocked = self.length.blockSignals(True)
+        self.length.setRange(round((min_len + feed) * 25.4 / DPI, 1),
+                             round((max_len + feed) * 25.4 / DPI, 1))
+        self.length.blockSignals(blocked)
 
     def _apply(self) -> None:
         layout.change_label(self.doc, self.combo.currentData())
@@ -232,6 +242,7 @@ class PaperPanel(Panel):
                 self._unfit is not None and self._unfit != self.doc.label_id):
             self._fill_labels()          # andere Datei bzw. passendes Etikett: Liste neu
         self.combo.setCurrentIndex(self.combo.findData(self.doc.label_id))
+        self._set_length_range()                     # Grenzen des Etiketts vor seinem Wert
         self.length_auto.setChecked(self.doc.length_mm is None)
         if self.doc.length_mm is not None:
             self.length.setValue(self.doc.length_mm)
@@ -291,6 +302,18 @@ class PaperPanel(Panel):
         self.length_title.setVisible(endless)
         self.length_box.setVisible(endless)
         self.length.setEnabled(not self.length_auto.isChecked())
+        self._set_length_range()                       # Vorschub hängt am Etikett
+        strip = label.feed_margin
+        self.margin_hint.setVisible(endless and round(self.doc.margin_mm * label.dpi / 25.4) < strip)
+        self.margin_hint.setText(_("Along the tape the printer leaves {mm} mm free.").format(
+            mm=format_mm(strip, label.dpi)))
+        across = (label.total_width - label.width) // 2
+        along = strip if endless else (label.total_height - label.height) // 2
+        self.margin.setToolTip(
+            _("Distance from the paper edge all around (the printer leaves about {across} mm free "
+              "across the tape and about {along} mm along it anyway)").format(
+                across=format_mm(across, label.dpi), along=format_mm(along, label.dpi))
+            if across or along else _("Distance from the paper edge all around"))
         self.fixed_size.setVisible(not endless)
         w, h = label.size_mm
         w, h = mm_text(w), mm_text(h)
diff --git a/src/labelwerk/labels.py b/src/labelwerk/labels.py
index 4e1765c..eb064b3 100644
--- a/src/labelwerk/labels.py
+++ b/src/labelwerk/labels.py
@@ -29,6 +29,8 @@ class Label:
     total_height: int | None  # physische Höhe in Punkten; None = Endlosband
     two_color: bool = False   # Rot/Schwarz (DK-22251, „62red“)
     dpi: int = DPI            # Druckauflösung (Brother 300; andere aus der ID)
+    feed_margin: int = 0      # Endlosband: Streifen, den der Drucker an Anfang und Ende längs
+                              # freilässt (brother_ql, ESC i d; 35 Punkte ≈ 3 mm)
 
     @property
     def description(self) -> str:
@@ -56,7 +58,7 @@ def _convert(raw) -> Label:
     total_w, total_h = raw.dots_total
     return Label(raw.identifier, w, None if endless else h, raw.tape_size[0],
                  shape, tuple(raw.tape_size), total_w, None if endless else total_h,
-                 raw.color == Color.BLACK_RED_WHITE)
+                 raw.color == Color.BLACK_RED_WHITE, feed_margin=raw.feed_margin if endless else 0)
 
 
 def _all_raw():
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index 3c36240..df23cd7 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -678,7 +678,8 @@ def objects_outside(doc: Document, model: str = "QL-600") -> list[int]:
 
 # --- Reiter „Layout“ ----------------------------------------------------------------
 def align_objects(objs: list[Object], rendered: list[RenderedObject], mode: str,
-                  area: Rect | None = None, grow: str | None = None) -> list[Object]:
+                  area: Rect | None = None, grow: str | None = None,
+                  min_length: float = 0.0) -> list[Object]:
     """Kopien der Objekte, ausgerichtet wie ``align`` – mit ``area`` am Papier, sonst aneinander.
 
     Gerechnet wird mit den Rahmen, wie sie im Modell stehen (``exact_rect``); ein Objekt ohne
@@ -686,13 +687,17 @@ def align_objects(objs: list[Object], rendered: list[RenderedObject], mode: str,
     ``grow`` (``growing_axis``): Am Papier sitzt die Auswahl in dieser Achse bei jedem Modus
     (Anfang, Mitte, Ende) mit ihrem Umriss am Anfang des Bereichs (Rand in Bandrichtung) –
     das Etikett wächst bis Inhalt plus Rand, die Ränder an beiden Enden sind dann gleich.
+    Ist das kürzer als die Mindestlänge ``min_length`` (mm, Druckbild), bleibt das Etikett so
+    lang – die Auswahl steht dann mittig darin.
     """
     rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
     if area is not None and grow == ("x" if mode in ("left", "hcenter", "right") else "y"):
         if not rects:
             return []
         box = bounds(rects)
-        shift = (area.x - box.x, 0.0) if grow == "x" else (0.0, area.y - box.y)
+        start, extent = (area.x, box.w) if grow == "x" else (area.y, box.h)
+        start = max(start, (min_length - extent) / 2)    # Rand an beiden Enden gleich
+        shift = (start - box.x, 0.0) if grow == "x" else (0.0, start - box.y)
         moved = [r.at(r.x + shift[0], r.y + shift[1]) for r in rects]
     else:
         moved = align(rects, mode, area)
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index c927589..92eb974 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -150,6 +150,11 @@ msgstr "Aneinander senkrecht mittig ausrichten"
 msgid "All"
 msgstr "Alle"
 
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Along the tape the printer leaves {mm} mm free."
+msgstr "Längs zum Band lässt der Drucker {mm} mm frei."
+
 #: src/labelwerk/gui/main_window.py
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
@@ -591,8 +596,13 @@ msgid "Distance from the left edge of the label"
 msgstr "Abstand vom linken Etikettrand"
 
 #: src/labelwerk/gui/panels/paper.py
-msgid "Distance from the paper edge all around (across the tape the printer leaves about 1.5 mm free anyway)"
-msgstr "Abstand zur Papierkante ringsum (quer lässt der Drucker ohnehin rund 1,5 mm frei)"
+msgid "Distance from the paper edge all around"
+msgstr "Abstand zur Papierkante ringsum"
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Distance from the paper edge all around (the printer leaves about {across} mm free across the tape and about {along} mm along it anyway)"
+msgstr "Abstand zur Papierkante ringsum (der Drucker lässt ohnehin quer rund {across} mm und längs rund {along} mm frei)"
 
 #: src/labelwerk/gui/panels/position.py
 msgid "Distance from the top edge of the label"
@@ -2682,8 +2692,8 @@ msgid "list the labels for the model"
 msgstr "Etiketten für das Modell auflisten"
 
 #: src/labelwerk/cli.py
-msgid "margin all around from the paper edge in mm (default from the settings)"
-msgstr "Rand ringsum ab Papierkante in mm (Standard aus den Einstellungen)"
+msgid "margin all around from the paper edge in mm – the strips the printer leaves free count (about 1.5 mm across, 3 mm along a continuous tape; default from the settings)"
+msgstr "Rand ringsum ab Papierkante in mm – die Streifen, die der Drucker freilässt, zählen mit (quer rund 1,5 mm, längs zum Endlosband 3 mm; Standard aus den Einstellungen)"
 
 #: src/labelwerk/cli.py
 msgid "model not detected"
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index 6a7b1b6..a2cb381 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -149,6 +149,11 @@ msgstr ""
 msgid "All"
 msgstr ""
 
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Along the tape the printer leaves {mm} mm free."
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr ""
@@ -582,7 +587,12 @@ msgid "Distance from the left edge of the label"
 msgstr ""
 
 #: src/labelwerk/gui/panels/paper.py
-msgid "Distance from the paper edge all around (across the tape the printer leaves about 1.5 mm free anyway)"
+msgid "Distance from the paper edge all around"
+msgstr ""
+
+#: src/labelwerk/gui/panels/paper.py
+#, python-brace-format
+msgid "Distance from the paper edge all around (the printer leaves about {across} mm free across the tape and about {along} mm along it anyway)"
 msgstr ""
 
 #: src/labelwerk/gui/panels/position.py
@@ -2661,7 +2671,7 @@ msgid "list the labels for the model"
 msgstr ""
 
 #: src/labelwerk/cli.py
-msgid "margin all around from the paper edge in mm (default from the settings)"
+msgid "margin all around from the paper edge in mm – the strips the printer leaves free count (about 1.5 mm across, 3 mm along a continuous tape; default from the settings)"
 msgstr ""
 
 #: src/labelwerk/cli.py
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 98edc25..d1b6351 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -404,9 +404,10 @@ def _sheet(doc: Document, model: str) -> _Sheet:
     side = max(0, margin - (label.total_width - label.width) // 2)
     if label.height is not None and label.total_height is not None:
         margin = max(0, margin - (label.total_height - label.height) // 2)
+    margin = max(0, margin - label.feed_margin)     # längs lässt der Drucker den Vorschub frei
     feed = label.height
-    if feed is None and doc.length_mm is not None:
-        feed = min(max(_dots(doc.length_mm, label.dpi), min_len), max_len)
+    if feed is None and doc.length_mm is not None:  # Länge = abgeschnittenes Stück mit Vorschub
+        feed = min(max(_dots(doc.length_mm, label.dpi) - 2 * label.feed_margin, min_len), max_len)
     keep = round(MARGIN * label.dpi / DPI)                          # Rand darf nicht alles
     side = min(side, max(0, (label.width - 2 * keep) // 2))        # aufbrauchen (quer, feste
     if feed is not None:                                            # Länge): 1 mm bleibt
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2562 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md src/labelwerk/cli.py src/labelwerk/gui/canvas.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/paper.py src/labelwerk/labels.py src/labelwerk/layout.py src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/render.py tests/_render_before_3d.py tests/gui/test_gui_layout.py tests/gui/test_gui_papier.py tests/gui/test_gui_placement.py tests/gui/test_gui_tape.py tests/gui/test_gui_window.py tests/test_document.py tests/test_feed_margin.py tests/test_frame.py tests/test_image_object.py tests/test_layout.py tests/test_placement_render.py tests/test_rich_text.py
git commit -m "Rand längs zum Endlosband: Vorschub des Druckers zählt mit, feste Länge = abgeschnittenes Stück, Streifen hellgrau, Hinweis unter Rand, Ausrichten bei Mindestlänge

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Schriftliste

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/fonts.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/gui/widgets.py`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/render.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/gui/test_gui_edit_mode.py`
- Create: `tests/gui/test_gui_font_combo.py`
- Modify: `tests/gui/test_gui_settings.py`
- Modify: `tests/gui/test_gui_text.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_fonts.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `fonts.families(all=False)` mit Filtern (lang=de, ohne Farb-/Powerline-/Symbol-/regionale CJK-Schriften), `fonts.canonical`; `settings.fonts_all`; `gui.widgets.FontCombo` (Signal `family_chosen`, `set_families`, `set_current_family`) im Reiter TEXT und im Einstellungsdialog; `MainWindow.apply_font_list`; CLI `labelwerk fonts --all`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_edit_mode.py b/tests/gui/test_gui_edit_mode.py
index 884d08e..85fa237 100644
--- a/tests/gui/test_gui_edit_mode.py
+++ b/tests/gui/test_gui_edit_mode.py
@@ -3,7 +3,7 @@ import pytest
 from PySide6.QtCore import QPointF, Qt
 from PySide6.QtGui import QMouseEvent
 from PySide6.QtTest import QTest
-from PySide6.QtWidgets import QApplication, QFontComboBox
+from PySide6.QtWidgets import QApplication
 
 from labelwerk import layout
 from labelwerk.document import Document, TextObject
diff --git a/tests/gui/test_gui_font_combo.py b/tests/gui/test_gui_font_combo.py
new file mode 100644
index 0000000..1122276
--- /dev/null
+++ b/tests/gui/test_gui_font_combo.py
@@ -0,0 +1,107 @@
+"""Schriftauswahl FontCombo: Liste aus fonts.families, jede Schrift in ihrer Schrift, fremde Schrift
+bleibt sichtbar."""
+from PySide6.QtCore import Qt
+
+from labelwerk.gui.widgets import FontCombo
+
+
+def _combo(qtbot, names=("DejaVu Sans", "DejaVu Serif", "Liberation Sans")):
+    combo = FontCombo(list(names))
+    qtbot.addWidget(combo)
+    return combo
+
+
+def _items(combo):
+    return [combo.itemText(i) for i in range(combo.count())]
+
+
+def test_lists_families_each_in_its_own_font(qtbot):
+    combo = _combo(qtbot)
+    assert _items(combo) == ["DejaVu Sans", "DejaVu Serif", "Liberation Sans"]
+    assert combo.itemData(1, Qt.ItemDataRole.FontRole).family() == "DejaVu Serif"
+
+
+def test_default_list_comes_from_fonts(qtbot, monkeypatch):
+    from labelwerk import fonts
+    monkeypatch.setattr(fonts, "families", lambda all=False: ["B", "C"] if all else ["B"])
+    combo = FontCombo()
+    qtbot.addWidget(combo)
+    assert _items(combo) == ["B"]
+    assert "Sans Serif" not in _items(combo)                   # keine Qt-Sammelnamen
+
+
+def test_unknown_family_is_shown_on_top_and_chosen(qtbot):
+    combo = _combo(qtbot)
+    combo.set_current_family("GibtsGarNicht 4711")
+    assert combo.current_family() == "GibtsGarNicht 4711" and combo.currentIndex() == 0
+    assert combo.count() == 4
+    combo.set_current_family("GanzAnders")                       # nur ein fremder Eintrag
+    assert _items(combo)[0] == "GanzAnders" and combo.count() == 4
+    combo.set_current_family("DejaVu Serif")                     # fremder Eintrag entfällt
+    assert _items(combo) == ["DejaVu Sans", "DejaVu Serif", "Liberation Sans"]
+    assert combo.current_family() == "DejaVu Serif"
+
+
+def test_family_chosen_signal(qtbot):
+    combo = _combo(qtbot)
+    combo.set_current_family("DejaVu Sans")
+    with qtbot.waitSignal(combo.family_chosen) as blocker:
+        combo.setCurrentIndex(2)                                 # wie eine Wahl in der Liste
+    assert blocker.args == ["Liberation Sans"]
+    with qtbot.waitSignal(combo.family_chosen) as blocker:
+        combo.set_current_family("DejaVu Serif")
+    assert blocker.args == ["DejaVu Serif"]
+    with qtbot.assertNotEmitted(combo.family_chosen):
+        combo.set_current_family("DejaVu Serif")                 # unverändert
+        combo.setCurrentIndex(-1)                                # leer: keine Schrift
+
+
+def test_empty_shows_nothing(qtbot):
+    combo = _combo(qtbot)
+    combo.set_current_family("DejaVu Serif")
+    combo.setCurrentIndex(-1)
+    assert combo.currentText() == "" and combo.current_family() is None
+
+
+def test_set_families_keeps_current_choice(qtbot):
+    combo = _combo(qtbot)
+    combo.set_current_family("Liberation Sans")
+    with qtbot.assertNotEmitted(combo.family_chosen):
+        combo.set_families(["DejaVu Sans"])
+    assert combo.current_family() == "Liberation Sans"           # bleibt (jetzt als fremde Schrift)
+    assert _items(combo) == ["Liberation Sans", "DejaVu Sans"]
+    combo.set_families(["DejaVu Sans", "Liberation Sans"])
+    assert _items(combo) == ["DejaVu Sans", "Liberation Sans"]
+    assert combo.current_family() == "Liberation Sans"
+
+
+def test_set_none_shows_nothing_without_signal(qtbot):
+    combo = _combo(qtbot)
+    combo.set_current_family("DejaVu Serif")
+    with qtbot.assertNotEmitted(combo.family_chosen):
+        combo.set_current_family(None)
+    assert combo.current_family() is None
+    with qtbot.waitSignal(combo.family_chosen) as blocker:
+        combo.set_current_family("DejaVu Serif")                 # wieder gewählt: meldet
+    assert blocker.args == ["DejaVu Serif"]
+
+
+def test_old_qt_name_with_foundry_shows_installed_family(qtbot, monkeypatch):
+    from labelwerk import fonts
+    monkeypatch.setattr(fonts, "families", lambda all=False: ["C059", "DejaVu Sans"])
+    combo = _combo(qtbot, ("C059", "DejaVu Sans"))
+    combo.set_current_family("C059 [UKWN]")
+    assert combo.current_family() == "C059" and combo.count() == 2   # kein fremder Eintrag
+    combo.set_current_family("Sans Serif")                           # Sammelname bleibt fremd
+    assert combo.current_family() == "Sans Serif" and combo.count() == 3
+
+
+def test_long_font_names_do_not_widen_the_panel(qtbot):
+    from labelwerk.gui.app import load_theme
+    from labelwerk.gui.main_window import PANEL_WIDTH
+    short = _combo(qtbot, ("A",))
+    long = _combo(qtbot, ("A", "Ein sehr langer Schriftname Extra Condensed Semibold Italic Display"))
+    for combo in (short, long):
+        combo.setStyleSheet(load_theme())
+        combo.ensurePolished()
+    assert long.minimumSizeHint().width() == short.minimumSizeHint().width() < PANEL_WIDTH
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index 92628a2..6835fa5 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -72,12 +72,11 @@ def test_qt_dialog_buttons_are_german(qapp):
 
 
 def test_dialog_font_family_roundtrip(qtbot, tmp_path):
-    from PySide6.QtGui import QFont
     path = tmp_path / "settings.json"
     dialog = SettingsDialog(Settings(font_family="Liberation Sans"), path=path)
     qtbot.addWidget(dialog)
     assert dialog.values().font_family == "Liberation Sans"
-    dialog.font_family.setCurrentFont(QFont("DejaVu Sans"))
+    dialog.font_family.set_current_family("DejaVu Sans")
     dialog.accept()
     assert load_settings(path).font_family == "DejaVu Sans"
 
@@ -89,12 +88,39 @@ def test_unknown_font_family_survives_unchanged_dialog(qtbot):
 
 
 def test_changed_font_family_is_taken_over(qtbot):
-    from PySide6.QtGui import QFont
     dlg = SettingsDialog(Settings(font_family="GibtsGarNicht 4711"))
     qtbot.addWidget(dlg)
     dlg.font_family.setCurrentIndex(0)
     dlg.font_family.setCurrentIndex(1)
-    assert dlg.values().font_family == dlg.font_family.currentFont().family() != "GibtsGarNicht 4711"
+    assert dlg.values().font_family == dlg.font_family.current_family() != "GibtsGarNicht 4711"
+
+
+def test_all_fonts_option_fills_the_list_at_once(qtbot, monkeypatch):
+    from labelwerk import fonts
+    monkeypatch.setattr(fonts, "families",
+                        lambda all=False: ["DejaVu Sans", "Zapf X"] if all else ["DejaVu Sans"])
+    dlg = SettingsDialog(Settings(font_family="DejaVu Sans"))
+    qtbot.addWidget(dlg)
+    assert not dlg.fonts_all.isChecked() and dlg.font_family.count() == 1
+    dlg.fonts_all.setChecked(True)                               # sofort in der Liste
+    assert dlg.font_family.count() == 2 and dlg.font_family.current_family() == "DejaVu Sans"
+    assert dlg.values().fonts_all is True and dlg.values().font_family == "DejaVu Sans"
+    assert not dlg.restart_needed()                              # wirkt ohne Neustart
+
+
+def test_saved_all_fonts_option_applies_to_text_panel(qtbot, monkeypatch):
+    from labelwerk import fonts
+    monkeypatch.setattr(fonts, "families",
+                        lambda all=False: ["DejaVu Sans", "Zapf X"] if all else ["DejaVu Sans"])
+    win = MainWindow(settings=Settings(check_media_on_start=False, fonts_all=True))
+    qtbot.addWidget(win)
+    family = win.panel("text").family
+    assert [family.itemText(i) for i in range(family.count())] == ["DejaVu Sans", "Zapf X"]
+    monkeypatch.setattr(SettingsDialog, "exec", lambda self: (
+        self.fonts_all.setChecked(False), self.accept(), QDialog.DialogCode.Accepted)[-1])
+    win.open_settings()
+    assert win.settings.fonts_all is False
+    assert [family.itemText(i) for i in range(family.count())] == ["DejaVu Sans"]
 
 
 def test_dialog_keeps_fractional_font_size(qtbot):
diff --git a/tests/gui/test_gui_text.py b/tests/gui/test_gui_text.py
index 100d76f..f0298dd 100644
--- a/tests/gui/test_gui_text.py
+++ b/tests/gui/test_gui_text.py
@@ -117,7 +117,7 @@ def test_start_uses_settings_family_and_size(qtbot):
     win.canvas.set_selection([0])
     panel = win.panel("text")
     assert panel.size.currentText() == "24"
-    assert panel.family.currentFont().family() == "Liberation Sans"
+    assert panel.family.current_family() == "Liberation Sans"
     assert not panel.fit.isChecked()
 
 
@@ -129,7 +129,7 @@ def test_unformatted_text_uses_base_format_not_widget_font(window):
     span = window.doc.objects[0].paragraphs[0].spans[0]
     assert span.family is None and span.size_pt is None and span.bold
     assert panel.size.currentText() == "19"
-    assert panel.family.currentFont().family() == "DejaVu Sans"
+    assert panel.family.current_family() == "DejaVu Sans"
     window.render_now()
     assert window.panel("text").error.isHidden()
 
@@ -347,3 +347,38 @@ def test_style_buttons_show_their_style_without_stylesheet(qtbot):
     assert panel.bold.font().bold()
     assert panel.italic.font().italic()
     assert panel.underline.font().underline()
+
+
+# --- Schriftliste (Abnahme-Korrekturen) ------------------------------------------
+def _families(window):
+    return [(s.text, s.family) for s in window.doc.objects[0].paragraphs[0].spans if s.text.strip()]
+
+
+def test_mixed_fonts_in_selection_leave_font_field_empty_and_choice_sets_all(window):
+    panel = window.panel("text")
+    panel.edit.setPlainText("aaa bbb")
+    _select(panel, 4, 7)
+    panel.family.set_current_family("DejaVu Serif")             # wie eine Wahl in der Liste
+    assert _families(window) == [("aaa ", None), ("bbb", "DejaVu Serif")]
+    _select(panel, 0, 7)
+    assert panel.family.currentText() == "" and panel.family.current_family() is None
+    document = panel.edit.document()
+    document.clearUndoRedoStacks()
+    panel.family.set_current_family("DejaVu Serif")
+    assert {family for __, family in _families(window)} == {"DejaVu Serif"}
+    assert panel.family.current_family() == "DejaVu Serif"
+    steps = 0
+    while document.isUndoAvailable():
+        document.undo()
+        steps += 1
+    assert steps == 1
+
+
+def test_same_font_in_selection_is_shown(window):
+    panel = window.panel("text")
+    panel.edit.setPlainText("aaa bbb")
+    _select(panel, 0, 7)
+    panel.family.set_current_family("DejaVu Serif")
+    _select(panel, 0, 3)
+    _select(panel, 0, 7)
+    assert panel.family.current_family() == "DejaVu Serif"
diff --git a/tests/test_cli.py b/tests/test_cli.py
index 48413b1..6a75c5d 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -323,6 +323,15 @@ def test_fonts_command_lists_families(capsys):
     assert "DejaVu Sans" in capsys.readouterr().out.splitlines()
 
 
+def test_fonts_command_short_list_and_all(monkeypatch, capsys):
+    from labelwerk import cli
+    monkeypatch.setattr(cli, "families", lambda all=False: ["A", "B"] if all else ["A"])
+    assert main(["fonts"]) == 0
+    assert capsys.readouterr().out.splitlines() == ["A"]
+    assert main(["fonts", "--all"]) == 0
+    assert capsys.readouterr().out.splitlines() == ["A", "B"]
+
+
 def test_align_invalid_is_argparse_error():
     with pytest.raises(SystemExit) as e:
         main(["print", "X", "--align", "mittig"])
diff --git a/tests/test_fonts.py b/tests/test_fonts.py
index 5793b38..80e6aee 100644
--- a/tests/test_fonts.py
+++ b/tests/test_fonts.py
@@ -33,13 +33,13 @@ def test_unknown_family_is_substituted():
 def test_without_fontconfig_falls_back_to_dejavu(monkeypatch):
     monkeypatch.setattr(fonts, "_run", lambda *a: None)
     fonts.resolve.cache_clear()
-    fonts.families.cache_clear()
+    fonts._families.cache_clear()
     try:
         assert fonts.families() == ["DejaVu Sans"]
         assert fonts.resolve(None, True, False).path.endswith("DejaVuSans-Bold.ttf")
     finally:
         fonts.resolve.cache_clear()
-        fonts.families.cache_clear()
+        fonts._families.cache_clear()
 
 
 def test_load_is_cached():
@@ -101,3 +101,87 @@ def test_render_document_with_unloadable_font_raises_valueerror(monkeypatch):
     with pytest.raises(ValueError, match="kann nicht geladen werden"):
         render_document(Document("62", objects=[TextObject.plain("Hallo")]))
     fonts.load.cache_clear()
+
+
+# --- kurze Liste (fontconfig-Ausgabe gefälscht) --------------------------------------
+_GERMAN = "\n".join([
+    "DejaVu Sans|False", "DejaVu Sans|False", "Liberation Sans|False", "Fira Sans Condensed|False",
+    "DejaVu Sans Mono for Powerline|False", "Ubuntu Mono derivative Powerline|False",
+    "Hack Nerd Font|False", "Hack Nerd Font Mono|False", "Twemoji|True",
+    "D050000L|False", "Standard Symbols PS|False", "OpenSymbol|False", "Wingdings 3|False",
+    "AR PL UKai TW MBE|False", "AR PL UMing CN|False", "Noto Sans CJK JP|False",
+    "Noto Serif CJK TC|False", "Noto Sans Mono CJK KR|False", "Noto Sans|", "Ubuntu|False", ""])
+_ALL = "Sans Serif\nNoto Sans Arabic\nDejaVu Sans\nNoto Sans CJK JP\nDejaVu Sans\n"
+
+
+@pytest.fixture
+def fake_fc(monkeypatch):
+    calls = []
+
+    def run(*args):
+        calls.append(args)
+        return _ALL if args[-1] == ":" else _GERMAN
+    monkeypatch.setattr(fonts, "_run", run)
+    fonts._families.cache_clear()
+    yield calls
+    fonts._families.cache_clear()
+
+
+def test_short_list_only_german_fonts_without_copies_symbols_and_cjk_regions(fake_fc):
+    assert fonts.families() == ["DejaVu Sans", "Fira Sans Condensed", "Liberation Sans",
+                                "Noto Sans", "Ubuntu"]
+    assert fake_fc[0][-1] == ":lang=de"                  # nur Schriften mit deutschen Zeichen
+
+
+def test_all_fonts_lists_every_family(fake_fc):
+    assert fonts.families(all=True) == ["DejaVu Sans", "Noto Sans Arabic", "Noto Sans CJK JP",
+                                        "Sans Serif"]
+    assert fake_fc[0][-1] == ":"
+
+
+def test_short_list_keeps_default_when_everything_is_filtered(monkeypatch):
+    monkeypatch.setattr(fonts, "_run", lambda *a: "Hack Nerd Font|False\n")
+    fonts._families.cache_clear()
+    try:
+        assert fonts.families() == [fonts.DEFAULT_FAMILY]
+    finally:
+        fonts._families.cache_clear()
+
+
+@needs_fontconfig
+def test_short_list_is_part_of_all_fonts():
+    short = fonts.families()
+    assert short and set(short) <= set(fonts.families(all=True))
+    assert not [n for n in short if "Powerline" in n]
+
+
+def test_families_cache_one_entry_per_list_however_called(fake_fc):
+    for call in (lambda: fonts.families(), lambda: fonts.families(False),
+                 lambda: fonts.families(all=False), lambda: fonts.families(True),
+                 lambda: fonts.families(all=True), lambda: fonts.families(all=1)):
+        call()
+    assert len(fake_fc) == 2                         # je Liste ein fc-list-Aufruf
+
+
+# --- alte Qt-Namen „Name [Hersteller]“ (aus QFontComboBox in Dateien/Einstellungen) --------
+def test_canonical_strips_foundry_of_installed_family(monkeypatch):
+    monkeypatch.setattr(fonts, "families",
+                        lambda all=False: ["C059", "Nimbus Sans", "Foo [Bar]"] if all else ["C059"])
+    assert fonts.canonical("C059 [UKWN]") == "C059"
+    assert fonts.canonical("Nimbus Sans [urw]") == "Nimbus Sans"   # auch nicht in der kurzen Liste
+    assert fonts.canonical("Foo [Bar]") == "Foo [Bar]"             # heißt wirklich so
+    assert fonts.canonical("Fehlt [urw]") == "Fehlt [urw]"         # Name ohne Hersteller fehlt auch
+    assert fonts.canonical("Sans Serif") == "Sans Serif"           # Qt-Sammelname bleibt fremd
+    assert fonts.canonical(None) is None
+
+
+@needs_fontconfig
+def test_resolve_and_warnings_understand_qt_foundry_names():
+    from labelwerk.document import Document, Paragraph, Span, TextObject
+    from labelwerk.render import font_warnings
+    fonts.resolve.cache_clear()
+    assert fonts.resolve("DejaVu Serif [PfEd]", False, False).family == "DejaVu Serif"
+    doc = Document(objects=[TextObject([Paragraph([Span("A", family="DejaVu Serif [PfEd]"),
+                                                   Span("B", family="Sans Serif")])])])
+    warnings = font_warnings(doc)
+    assert len(warnings) == 1 and "Sans Serif" in warnings[0]       # nur der Sammelname
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 9bc6f68..da9144a 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -344,3 +344,13 @@ def test_one_bad_printer_option_keeps_the_others(tmp_path):
         "cups:Dymo": {"CutMedia": "EndOfJob", "X": "a b"}, "zpl:203": "kaputt"}}))
     s = load_settings(path)
     assert s.printer_options == {"cups:Dymo": {"CutMedia": "EndOfJob"}} and s.warnings
+
+
+def test_fonts_all_default_and_validation(tmp_path):
+    path = tmp_path / "s.json"
+    assert load_settings(path).fonts_all is False              # kurze Schriftliste
+    save_settings(Settings(fonts_all=True), path)
+    assert load_settings(path).fonts_all is True
+    path.write_text(json.dumps({"fonts_all": "ja"}))
+    s = load_settings(path)
+    assert s.fonts_all is False and s.warnings
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_font_combo.py, Fälle in tests/test_fonts.py, tests/test_settings.py, tests/test_cli.py) schlagen fehl (ImportError `FontCombo` u. a.), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 143f604..9faa757 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -98,7 +98,10 @@ src/labelwerk/
               po/<code>.po im Paket, po/labelwerk.pot erzeugt von tools/i18n.py (extract mit „# Translators:“-
               Hinweisen und python-brace-format, update behält Kommentare/fuzzy/veraltete, check prüft auch
               Mehrzahlformen, german_leftovers); Anleitung po/README.md
-  fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei
+  fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei;
+              families() = kurze Liste (:lang=de, ohne Farbschriften, Powerline/Nerd-Font-Kopien, Symbolschriften,
+              CJK-Regionsvarianten), families(all=True) alle (Einstellung `fonts_all`, CLI fonts --all); canonical:
+              alte Qt-Namen „Name [Hersteller]“ → „Name“ (resolve, font_warnings, FontCombo)
   files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
               crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
               load_image(path, page, dpi=None) -> (RGB-Bild, dpi) für Bild-Objekte (PNG/JPG/GIF/BMP/WebP/PDF, Transparenz → weiß, EXIF-Lage; dpi gesetzt: Dateiauflösung gilt nicht, quadratisch diese dpi);
@@ -267,6 +270,10 @@ src/labelwerk/
                     Befehle im Schreibmodus (undo/redo/copy/cut/paste/update_actions -> bool „erledigt“), MainWindow delegiert
     actions.py      QActions aus shortcuts.ACTIONS – jedes Kürzel der App läuft hierüber (apply_shortcuts)
     history.py      Rückgängig/Wiederherstellen: Dokument-Schnappschüsse samt Auswahl, höchstens 100; amend (ohne eigenen Schritt)
+    widgets.py      SpinBox/DoubleSpinBox (Dezimaltrenner der Sprache), FontCombo (Schriftauswahl aus fonts.families,
+                    jede Schrift in ihrer Schrift, fremde Schrift bleibt oben gewählt, None = leer bei gemischten Schriften;
+                    Breite unabhängig von den Namen; Signal family_chosen) – Reiter Text
+                    und Einstellungen
     symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
     print_worker.py Drucken im Hintergrund-Thread (cancel(): threading.Event; Signale progress, cancelled)
     media_worker.py  Medium prüfen im Hintergrund (MediaWorker(model, printer): URI des gewählten USB-Druckers; Ergebnis eines
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index 9d111ce..957c9c1 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -141,7 +141,9 @@ def _parser() -> argparse.ArgumentParser:
 
     sub.add_parser("media", help=_("query the roll loaded in the printer (prints nothing)"))
     sub.add_parser("printers", help=_("list found printers and supported models"))
-    sub.add_parser("fonts", help=_("list installed font families"))
+    fo = sub.add_parser("fonts", help=_("list installed font families with German characters"))
+    fo.add_argument("--all", action="store_true",
+                    help=_("all font families, also copies, symbol fonts and other scripts"))
 
     di = sub.add_parser("install-desktop",
                         help=_("add labelwerk-gui to the launcher (Super key)"))
@@ -406,7 +408,7 @@ def main(argv: list[str] | None = None) -> int:
     if args.cmd == "printers":
         return _show_printers(args.model)
     if args.cmd == "fonts":
-        print("\n".join(families()))
+        print("\n".join(families(all=args.all)))
         return 0
 
     if args.cmd == "print" and args.font and args.font_family:
diff --git a/src/labelwerk/fonts.py b/src/labelwerk/fonts.py
index ab47ddc..4f5e193 100644
--- a/src/labelwerk/fonts.py
+++ b/src/labelwerk/fonts.py
@@ -4,6 +4,7 @@ Ohne fontconfig (fc-list/fc-match) wird auf DejaVu Sans zurückgefallen.
 """
 from __future__ import annotations
 
+import re
 import shutil
 import subprocess
 from dataclasses import dataclass
@@ -37,15 +38,55 @@ def _run(*args: str) -> str | None:
         return None
 
 
-@lru_cache(maxsize=1)
-def families() -> list[str]:
-    """Installierte Schriftfamilien, sortiert."""
+# Kurze Liste: keine Kopien (Powerline/Nerd Fonts sind nachgerüstete Programmierschriften), keine
+# reinen Symbolschriften (Zeichen auf lateinischen Plätzen), keine Regionsvarianten der CJK-Schriften
+# (für deutschen Text gleich)
+_HIDDEN = re.compile(
+    r"powerline|nerd font"
+    r"|^(d050000l|standard symbols (ps|l)|dingbats|symbol|opensymbol|symbola|webdings"
+    r"|wingdings( \d)?|font awesome.*|material (icons|symbols).*|noto sans symbols.*)$"
+    r"|\b(cjk|ukai|uming)\b.*\b(cn|hk|tw|jp|kr|sc|tc|mbe)$", re.IGNORECASE)
+
+
+def families(all: bool = False) -> list[str]:
+    """Installierte Schriftfamilien, sortiert. Standard ist die kurze Liste: nur Schriften mit
+    allen deutschen Zeichen (fontconfig ``:lang=de``), ohne Farb-/Emoji-Schriften, Kopien,
+    Symbolschriften und CJK-Regionsvarianten; ``all``: jede Familie. Gemerkt (je Liste einmal,
+    gleich wie aufgerufen; Tests leeren ``_families.cache_clear()``)."""
+    return list(_families(bool(all)))
+
+
+@lru_cache(maxsize=None)
+def _families(all: bool) -> tuple[str, ...]:
     # %{family[0]}: erster Familienname je Schrift, ohne fontconfig-Maskierung
-    out = _run("fc-list", "-f", "%{family[0]}\\n", ":")
-    if not out:
-        return [DEFAULT_FAMILY]
-    names = {line.strip() for line in out.splitlines() if line.strip()}
-    return sorted(names, key=str.casefold)
+    if all:
+        out = _run("fc-list", "-f", "%{family[0]}\\n", ":")
+        names = {line.strip() for line in (out or "").splitlines() if line.strip()}
+    else:
+        out = _run("fc-list", "-f", "%{family[0]}|%{color}\\n", ":lang=de")
+        rows = [line.rsplit("|", 1) for line in (out or "").splitlines() if "|" in line]
+        color = {name.strip() for name, flag in rows if flag.strip() == "True"}
+        names = {name.strip() for name, __ in rows if name.strip()} - color
+        names = {name for name in names if not _HIDDEN.search(name)}
+    if not names:
+        return (DEFAULT_FAMILY,)
+    return tuple(sorted(names, key=str.casefold))
+
+
+# Qt (QFontComboBox) nannte gleichnamige Schriften „Name [Hersteller]“ – so steht es in älteren
+# Dateien, Favoriten und Einstellungen
+_FOUNDRY = re.compile(r"(.+?) \[[^\[\]]+\]")
+
+
+def canonical(family: str | None) -> str | None:
+    """Familienname ohne Qts Herstellerzusatz („C059 [UKWN]“ → „C059“), wenn es die Familie so
+    gibt (und nicht wirklich mit Klammer heißt); sonst unverändert – auch Qt-Sammelnamen wie
+    „Sans Serif“ (die bleiben fremd und werden ersetzt)."""
+    m = _FOUNDRY.fullmatch(family) if family else None
+    if m is None:
+        return family
+    installed = families(all=True)
+    return m[1] if m[1] in installed and family not in installed else family
 
 
 def _escape(name: str) -> str:
@@ -56,7 +97,7 @@ def _escape(name: str) -> str:
 @lru_cache(maxsize=256)
 def resolve(family: str | None, bold: bool, italic: bool) -> FontMatch:
     """Datei zu Familie + fett/kursiv; fontconfig ersetzt Fehlendes durch Ähnliches."""
-    family = family or DEFAULT_FAMILY
+    family = canonical(family) or DEFAULT_FAMILY
     # maskiert; ein führendes "-" wird zu "\\-" und ist so keine Option
     pattern = _escape(family) + (":bold" if bold else ":weight=regular") + (":italic" if italic else ":roman")
     out = _run("fc-match", "-f", "%{file}|%{family}|%{style}", pattern)
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index efb7bb7..afd88b3 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -17,7 +17,7 @@ from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFileD
                                QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                                QWidget)
 
-from .. import barcodes, clipart, favorites, series
+from .. import barcodes, clipart, favorites, fonts, series
 from ..desktop import APP_NAME
 from ..detect import brother_busy
 from .. import cups, zpl
@@ -220,6 +220,7 @@ class MainWindow(QMainWindow):
         for panel in self._panel_by_key.values():
             panel.use_actions(self.shortcut_actions)
         self.apply_theme_icons()
+        self.apply_font_list()
         central = QWidget()
         layout = QHBoxLayout(central)
         layout.setContentsMargins(0, 0, 0, 0)
@@ -1643,6 +1644,11 @@ class MainWindow(QMainWindow):
             if entry is not None:
                 self.shortcut_actions[entry[0]].setIcon(line_icon(entry[1], dark, hover=True))
 
+    def apply_font_list(self) -> None:
+        """Schriftauswahl im Reiter Text: kurze Liste oder alle (Einstellung „Alle Schriften“)."""
+        if "text" in self._panel_by_key:
+            self._panel_by_key["text"].family.set_families(fonts.families(all=self.settings.fonts_all))
+
     def open_settings(self) -> None:
         dialog = SettingsDialog(self.settings, model=self.model, parent=self, started=self._started)
         accepted = dialog.exec() == SettingsDialog.DialogCode.Accepted
@@ -1661,6 +1667,7 @@ class MainWindow(QMainWindow):
             from .app import apply_theme
             apply_theme(QApplication.instance(), self.settings.theme)
             self.apply_theme_icons()
+            self.apply_font_list()
             apply_shortcuts(self.shortcut_actions,
                             without_conflicts(effective(self.settings.shortcuts))[0])
             self.files.refresh_lists()                  # „Beim Start“ im Reiter Datei
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index 150c96b..5c2cdea 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -16,16 +16,17 @@ import math
 from PySide6.QtCore import QSize, Qt, Signal
 from PySide6.QtGui import (QAction, QFont, QIcon, QTextCharFormat, QTextCursor, QTextFormat,
                            QTextOption)
-from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayout, QLabel,
+from PySide6.QtWidgets import (QButtonGroup, QComboBox, QHBoxLayout, QLabel,
                                QPushButton, QTextEdit)
 
 from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
 from ...fonts import DEFAULT_FAMILY
-from ... import i18n
+from ... import fonts, i18n
 from ...i18n import N_, _, pgettext
 from ...layout import Rect
 from ...render import REF_PT
 from ..symbols import line_icon
+from ..widgets import FontCombo
 from . import Panel
 from .position import PositionSection
 
@@ -120,7 +121,7 @@ class TextPanel(Panel):
         self.edit.document().setDefaultTextOption(option)
 
         self.section(pgettext("text panel", "Font"))
-        self.family = QFontComboBox()
+        self.family = FontCombo()        # kurze Liste; MainWindow.apply_font_list nach Einstellung
         self.layout_.addWidget(self.family)
         row = QHBoxLayout()
         self.size = QComboBox()
@@ -186,8 +187,7 @@ class TextPanel(Panel):
         self.edit.cursorPositionChanged.connect(self._sync_buttons)
         self.edit.selectionChanged.connect(self._sync_buttons)
         step = self._step     # Knöpfe und Felder: jede Änderung ein eigener Schritt
-        self.family.currentFontChanged.connect(
-            lambda font: step(self._format, family=font.family()))
+        self.family.family_chosen.connect(lambda family: step(self._format, family=family))
         self.size.activated.connect(lambda _index: step(self._size_entered))
         self.size.lineEdit().editingFinished.connect(lambda: step(self._size_entered))
         self.grow.clicked.connect(lambda: step(self._step_size, +1))
@@ -519,8 +519,8 @@ class TextPanel(Panel):
             document.clear()
             document.setUndoRedoEnabled(True)
             self.fit.setChecked(False)
-            # keine Schrift anzeigen, die nicht gilt – ohne blockierte Signale, sonst hält
-            # QFontComboBox die alte Schrift intern fest und zeigt sie beim Wiederwählen nicht
+            # keine Schrift anzeigen, die nicht gilt – ohne blockierte Signale: die Felder merken
+            # sich „leer“ und zeigen beim Wiederwählen dieselbe Schrift wieder an
             for combo in (self.family, self.size):
                 combo.setCurrentIndex(-1)
                 combo.setEditText("")
@@ -550,12 +550,14 @@ class TextPanel(Panel):
         """Knöpfe zeigen die Formatierung an der Schreibmarke."""
         props = self._props(self.edit.currentCharFormat())
         mixed = self._selection_sizes()
+        mixed_families = len({fonts.canonical(f) for f in self._selection_values("family")}) > 1
         self._shown_pt = None if len(mixed) > 1 else props["pt"]
         widgets = (self.family, self.size, self.bold, self.italic, self.underline,
                    *self.align_buttons.values())
         for w in widgets:
             w.blockSignals(True)
-        self.family.setCurrentFont(QFont(props["family"]))
+        # gemischte Schriften: Feld leer (wie die Größe); eine Wahl setzt dann alle auf sie
+        self.family.set_current_family(None if mixed_families else props["family"])
         self.size.setEditText("" if len(mixed) > 1 else i18n.number(props["pt"]))
         self.bold.setChecked(props["bold"])
         self.italic.setChecked(props["italic"])
@@ -580,11 +582,16 @@ class TextPanel(Panel):
 
     def _selection_sizes(self) -> set[float]:
         """Verschiedene Größen innerhalb der Markierung (leer ohne Markierung)."""
+        return {round(pt, 2) for pt in self._selection_values("pt")}
+
+    def _selection_values(self, key: str) -> set:
+        """Verschiedene Werte einer Formatierung (``_props``-Schlüssel) innerhalb der Markierung
+        (leer ohne Markierung)."""
         cursor = self.edit.textCursor()
         if not cursor.hasSelection():
             return set()
         start, end = cursor.selectionStart(), cursor.selectionEnd()
-        sizes = set()
+        values = set()
         block = self.edit.document().findBlock(start)
         while block.isValid() and block.position() < end:
             it = block.begin()
@@ -592,10 +599,10 @@ class TextPanel(Panel):
                 fragment = it.fragment()
                 if (fragment.isValid() and fragment.position() < end
                         and fragment.position() + fragment.length() > start):
-                    sizes.add(round(self._props(fragment.charFormat())["pt"], 2))
+                    values.add(self._props(fragment.charFormat())[key])
                 it += 1
             block = block.next()
-        return sizes
+        return values
 
     def show_error(self, message: str | None) -> None:
         self.error.setText(message or "")
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index d238cbd..4feb10d 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -8,15 +8,15 @@ from __future__ import annotations
 from pathlib import Path
 
 from PySide6.QtCore import QSize, Qt
-from PySide6.QtGui import QColor, QFont, QKeySequence
+from PySide6.QtGui import QColor, QKeySequence
 from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
-                               QDialogButtonBox, QFontComboBox, QFormLayout, QFrame, QGroupBox,
+                               QDialogButtonBox, QFormLayout, QFrame, QGroupBox,
                                QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QPushButton,
                                QScrollArea, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
                                QTabWidget,
                                QVBoxLayout, QWidget)
 
-from .. import favorites, i18n, shortcuts, zpl
+from .. import favorites, fonts, i18n, shortcuts, zpl
 from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
 from ..i18n import N_, _
 from ..labels import get_label, labels_for_model
@@ -24,7 +24,7 @@ from ..printer import DEFAULT_MODEL
 from ..printers import SUPPORTED_MODELS, capabilities
 from ..settings import (Settings, restart_pending, save_settings, started_values,
                         valid_host)
-from .widgets import DoubleSpinBox, SpinBox
+from .widgets import DoubleSpinBox, FontCombo, SpinBox
 
 # englisch (N_), angezeigt wird _(…)
 SCOPE_NAMES = {"global": N_("Global"), "canvas": N_("Canvas"), "edit": N_("Text editing")}
@@ -102,12 +102,12 @@ class SettingsDialog(QDialog):
         row.addWidget(self.font_auto)
         row.addWidget(self.font_size)
         form.addRow(_("Font size"), row)
-        self.font_family = QFontComboBox()
-        self.font_family.setCurrentFont(QFont(settings.font_family))
+        self.font_family = FontCombo(fonts.families(all=settings.fonts_all))
+        self.font_family.set_current_family(settings.font_family)
         # Nicht installierte Schrift nicht stillschweigend durch Ersatz überschreiben
         self._orig_family = settings.font_family
         self._family_touched = False
-        self.font_family.currentFontChanged.connect(self._family_changed)
+        self.font_family.family_chosen.connect(self._family_changed)
         form.addRow(_("Font"), self.font_family)
         self.start_favorite = QComboBox()
         self.start_favorite.addItem(_("Empty label"), None)
@@ -189,6 +189,13 @@ class SettingsDialog(QDialog):
             self.language.addItem(i18n.NAMES.get(code, code), code)
         self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
         form.addRow(_("Language"), self.language)
+        self.fonts_all = QCheckBox(_("Show all fonts"))
+        self.fonts_all.setToolTip(_("Also copies, symbol fonts and fonts without German characters "
+                                    "– otherwise only fonts that can write German"))
+        self.fonts_all.setChecked(settings.fonts_all)
+        self.fonts_all.toggled.connect(
+            lambda on: self.font_family.set_families(fonts.families(all=on)))
+        form.addRow(self.fonts_all)
         # Einstellungen, die erst nach einem Neustart wirken: farbiger Hinweis neben SPEICHERN
         # (unten im Fenster – sichtbar in jedem Reiter), sobald eine davon geändert ist
         self._started = started if started is not None else started_values(settings)
@@ -389,7 +396,7 @@ class SettingsDialog(QDialog):
                             "model": self.network.cellWidget(row, 2).currentData()})
         return entries
 
-    def _family_changed(self, _font) -> None:
+    def _family_changed(self, _family) -> None:
         self._family_touched = True
 
     def restart_needed(self) -> bool:
@@ -406,8 +413,9 @@ class SettingsDialog(QDialog):
             orientation=self.orientation.currentData(),
             margin_mm=self.margin.value(),
             font_size_pt=None if self.font_auto.isChecked() else self.font_size.value(),
-            font_family=(self.font_family.currentFont().family() if self._family_touched
+            font_family=(self.font_family.current_family() if self._family_touched
                          else self._orig_family),
+            fonts_all=self.fonts_all.isChecked(),
             check_media_on_start=self.check_media.isChecked(),
             start_zoom=self.zoom.value(),
             theme=self.theme.currentData(),
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index 4f82425..1558d2e 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -117,7 +117,7 @@ QPushButton#formatButton[style="underline"] { text-decoration: underline; }
 QTextEdit { background: #F0F0F0; border: 3px solid #000000; border-radius: 0; padding: 6px; }
 QTextEdit:focus { border-width: 5px; }
 QTextEdit:disabled { border-color: #CCCCCC; background: #F5F5F5; }
-QFontComboBox { min-width: 0; }
+FontCombo { min-width: 0; }
 /* Reiter Layout: Symbolknöpfe; beim Darüberfahren schwarz, das Symbol wird dann weiß */
 QToolButton#layoutButton { background: #FFFFFF; border: 3px solid #000000; border-radius: 0; padding: 6px; }
 QToolButton#layoutButton:hover { background: #000000; }
diff --git a/src/labelwerk/gui/widgets.py b/src/labelwerk/gui/widgets.py
index 66f7828..d45952d 100644
--- a/src/labelwerk/gui/widgets.py
+++ b/src/labelwerk/gui/widgets.py
@@ -1,9 +1,11 @@
 """Kleine Widget-Anpassungen, die für alle Panels und Dialoge gelten."""
 from __future__ import annotations
 
-from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox
+from PySide6.QtCore import Qt, Signal
+from PySide6.QtGui import QFont
+from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox
 
-from .. import i18n
+from .. import fonts, i18n
 
 # Qt legt das Textfeld eines per Stylesheet gerahmten Zahlenfelds über den linken Rahmen;
 # ein Textrand hält die Zahl lesbar (Innenabstände im Stylesheet greifen dort nicht).
@@ -33,3 +35,82 @@ class DoubleSpinBox(QDoubleSpinBox):
 
     def valueFromText(self, text: str) -> float:
         return super().valueFromText(self._own(text))
+
+
+MIN_FONT_CHARS = 8                              # Schriftauswahl: so viele Zeichen mindestens breit
+
+
+class FontCombo(QComboBox):
+    """Schriftauswahl aus ``fonts.families`` (statt QFontComboBox: keine Qt-Sammelnamen wie
+    „Sans Serif“, nur die kurze Liste), jede Schrift in ihrer Schrift. Eine Schrift, die nicht in
+    der Liste steht (aus Datei oder Einstellung), erscheint oben und gewählt – nichts geht
+    verloren. ``family_chosen`` meldet jede andere Schrift (Wahl in der Liste oder
+    ``set_current_family``), nie „leer“."""
+    family_chosen = Signal(str)
+
+    def __init__(self, names: list[str] | None = None, parent=None):
+        super().__init__(parent)
+        # Breite unabhängig von den Namen (wie QFontComboBox) – lange Namen weiten das Panel nicht
+        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
+        self.setMinimumContentsLength(MIN_FONT_CHARS)
+        self._extra: str | None = None          # fremde Schrift oben in der Liste
+        self._last: str | None = None           # zuletzt gemeldete bzw. gesetzte Schrift
+        self.set_families(fonts.families() if names is None else names)
+        self.currentIndexChanged.connect(self._index_changed)
+
+    def current_family(self) -> str | None:
+        return self.currentText() if self.currentIndex() >= 0 else None
+
+    def set_families(self, names: list[str]) -> None:
+        """Liste neu füllen; die gewählte Schrift bleibt (notfalls als fremde Schrift oben)."""
+        current = self.current_family()
+        blocked = self.blockSignals(True)
+        try:
+            self.clear()
+            self._extra = None
+            size = self.font().pointSizeF()
+            for name in names:
+                font = QFont(name)
+                if size > 0:
+                    font.setPointSizeF(size)
+                self.addItem(name)
+                self.setItemData(self.count() - 1, font, Qt.ItemDataRole.FontRole)
+            self._select(current)
+        finally:
+            self.blockSignals(blocked)
+
+    def set_current_family(self, name: str | None) -> None:
+        """Schrift anzeigen (None = leer, z. B. gemischte Schriften); meldet ``family_chosen``,
+        wenn sich eine Schrift ändert (außer bei blockierten Signalen)."""
+        name = fonts.canonical(name)            # alter Qt-Name „C059 [UKWN]“ → „C059“
+        changed = name != self._last
+        blocked = self.blockSignals(True)
+        try:
+            self._select(name)
+        finally:
+            self.blockSignals(blocked)
+        if changed and name is not None and not blocked:
+            self.family_chosen.emit(name)
+
+    def _select(self, name: str | None) -> None:
+        if name is None:
+            self.setCurrentIndex(-1)
+            self._last = None
+            return
+        if self._extra is not None and self._extra != name:
+            self.removeItem(0)                  # nur ein fremder Eintrag
+            self._extra = None
+        index = self.findText(name, Qt.MatchFlag.MatchExactly)
+        if index < 0:
+            self.insertItem(0, name)
+            self._extra = name
+            index = 0
+        self.setCurrentIndex(index)
+        self._last = name
+
+    def _index_changed(self, index: int) -> None:
+        name = self.current_family()
+        if name != self._last:
+            self._last = name
+            if name is not None:
+                self.family_chosen.emit(name)
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index 92eb974..95b920e 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -155,6 +155,10 @@ msgstr "Alle"
 msgid "Along the tape the printer leaves {mm} mm free."
 msgstr "Längs zum Band lässt der Drucker {mm} mm frei."
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Also copies, symbol fonts and fonts without German characters – otherwise only fonts that can write German"
+msgstr "Auch Kopien, Symbolschriften und Schriften ohne deutsche Zeichen – sonst nur Schriften, die Deutsch schreiben können"
+
 #: src/labelwerk/gui/main_window.py
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
@@ -2155,6 +2159,10 @@ msgstr "Tastenkürzel"
 msgid "Shortcuts assigned twice – change one to save:"
 msgstr "Tastenkürzel doppelt belegt – zum Speichern eines ändern:"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Show all fonts"
+msgstr "Alle Schriften zeigen"
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Single"
 msgstr "Einfach"
@@ -2594,6 +2602,10 @@ msgstr "Fehler beim Zugriff"
 msgid "add labelwerk-gui to the launcher (Super key)"
 msgstr "labelwerk-gui im Starter (Super-Taste) eintragen"
 
+#: src/labelwerk/cli.py
+msgid "all font families, also copies, symbol fonts and other scripts"
+msgstr "alle Schriftfamilien, auch Kopien, Symbolschriften und andere Schriftsysteme"
+
 #: src/labelwerk/cli.py
 msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
 msgstr "auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (Warteschlange, siehe 'labelwerk printers'), zpl+file:///dev/usb/lpN bzw. zpl+tcp://IP (Zebra, mit -m zpl:203/300/600)"
@@ -2684,8 +2696,8 @@ msgid "list found printers and supported models"
 msgstr "gefundene Drucker und unterstützte Modelle auflisten"
 
 #: src/labelwerk/cli.py
-msgid "list installed font families"
-msgstr "installierte Schriftfamilien auflisten"
+msgid "list installed font families with German characters"
+msgstr "installierte Schriftfamilien mit deutschen Zeichen auflisten"
 
 #: src/labelwerk/cli.py
 msgid "list the labels for the model"
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index a2cb381..3125ac7 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -154,6 +154,10 @@ msgstr ""
 msgid "Along the tape the printer leaves {mm} mm free."
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Also copies, symbol fonts and fonts without German characters – otherwise only fonts that can write German"
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "An object extends beyond the label and will be cut off. Print anyway?"
 msgstr ""
@@ -2134,6 +2138,10 @@ msgstr ""
 msgid "Shortcuts assigned twice – change one to save:"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Show all fonts"
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "Single"
 msgstr ""
@@ -2573,6 +2581,10 @@ msgstr ""
 msgid "add labelwerk-gui to the launcher (Super key)"
 msgstr ""
 
+#: src/labelwerk/cli.py
+msgid "all font families, also copies, symbol fonts and other scripts"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
 msgstr ""
@@ -2663,7 +2675,7 @@ msgid "list found printers and supported models"
 msgstr ""
 
 #: src/labelwerk/cli.py
-msgid "list installed font families"
+msgid "list installed font families with German characters"
 msgstr ""
 
 #: src/labelwerk/cli.py
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index d1b6351..7bc2d74 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -78,7 +78,8 @@ def font_warnings(doc: Document) -> list[str]:
                 match = fonts.resolve(span.family, span.bold, span.italic)
                 text = _("Font “{family}” not found – replaced by “{replacement}”.").format(
                     family=span.family, replacement=match.family)
-                if match.family.casefold() != span.family.casefold() and text not in warnings:
+                if (match.family.casefold() != fonts.canonical(span.family).casefold()
+                        and text not in warnings):
                     warnings.append(text)
     return warnings
 
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 718035f..1cca212 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -33,6 +33,7 @@ class Settings:
     margin_mm: float = 1.0
     font_size_pt: float | None = None      # None = automatisch
     font_family: str = DEFAULT_FAMILY
+    fonts_all: bool = False                # Schriftauswahl: alle Familien statt der kurzen Liste
     check_media_on_start: bool = True
     start_zoom: int = 200
     theme: str = "rawblock"                # "rawblock" oder "classic" (Qt-Systemstil)
@@ -68,6 +69,7 @@ def _rules(model: str | None = None) -> dict:
         "font_size_pt": lambda v: v is None or ((_is_int(v) or isinstance(v, float))
                                                 and MIN_PT <= v <= MAX_PT),
         "font_family": lambda v: isinstance(v, str) and bool(v.strip()),
+        "fonts_all": lambda v: isinstance(v, bool),
         "check_media_on_start": lambda v: isinstance(v, bool),
         "start_zoom": lambda v: _is_int(v) and 25 <= v <= 400,
         "theme": lambda v: v in THEMES,
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2583 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/cli.py src/labelwerk/fonts.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/gui/widgets.py src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/render.py src/labelwerk/settings.py tests/gui/test_gui_edit_mode.py tests/gui/test_gui_font_combo.py tests/gui/test_gui_settings.py tests/gui/test_gui_text.py tests/test_cli.py tests/test_fonts.py tests/test_settings.py
git commit -m "Schriftliste: nur Schriften mit deutschen Zeichen ohne Kopien/Symbol-/regionale CJK-Schriften, Einstellung „Alle Schriften zeigen“, FontCombo statt QFontComboBox, alte Qt-Namen zur Familie, labelwerk fonts --all

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Reiter beim Start und Standard für neue Bilder

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/image.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/gui/test_gui_image.py`
- Modify: `tests/gui/test_gui_language.py`
- Modify: `tests/gui/test_gui_screenshot.py`
- Modify: `tests/gui/test_gui_settings.py`
- Create: `tests/gui/test_gui_start_tool.py`
- Modify: `tests/test_i18n.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `settings.start_tool`/`last_tool`/`image_mode`/`image_threshold`, `START_TOOLS`, `QUIET_KEYS`, `RESTART_KEYS` mit `start_tool`, `restart_pending(language, start_zoom, start_tool, started)`; `MainWindow._start_tool`, `_remember_tool`, `_new_image` setzt Art/Schwelle; `ImagePanel.set_defaults`; Einstellungsdialog: Reiter beim Start, Umwandlung/Schwelle.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_image.py b/tests/gui/test_gui_image.py
index bc72ed7..18732c1 100644
--- a/tests/gui/test_gui_image.py
+++ b/tests/gui/test_gui_image.py
@@ -922,3 +922,41 @@ def test_insert_on_growing_tape_goes_behind_existing_text(qtbot):
     text, image = (layout.object_rect(r) for r in win.rendered)
     assert image.y >= text.bottom + 2 - 0.2
     assert layout.label_rect(win.doc).h > before
+
+
+# --- Standard für neue Bilder (Einstellungen) ---------------------------------------
+def test_new_images_take_mode_and_threshold_from_the_settings(qtbot, tmp_path):
+    win = _window(qtbot, image_mode="photo", image_threshold=90)
+    _insert_file(win, _file(tmp_path))                              # aus Datei
+    QApplication.clipboard().setImage(_qimage(_picture()))
+    win.panel("image").from_clipboard.click()                       # aus der Zwischenablage
+    mime = QMimeData()
+    mime.setImageData(_qimage(_picture()))
+    _drop(win.canvas, mime, QPointF(win.canvas.viewport().rect().center()))   # abgelegt
+    assert len(win.doc.objects) == 4
+    assert [(o.mode, o.threshold) for o in win.doc.objects[1:]] == [("photo", 90)] * 3
+
+
+def test_ctrl_v_image_takes_the_image_default(qtbot):
+    win = _window(qtbot, image_mode="photo", image_threshold=60)
+    QApplication.clipboard().setImage(_qimage(_picture()))
+    win.paste()
+    obj = win.doc.objects[1]
+    assert isinstance(obj, ImageObject) and (obj.mode, obj.threshold) == ("photo", 60)
+
+
+def test_symbols_stay_line_art_whatever_the_image_default(qtbot):
+    from labelwerk import clipart
+    win = _window(qtbot, image_mode="photo", image_threshold=40)
+    win.insert_symbol(clipart.find("labelwerk/motor"))
+    assert (win.doc.objects[1].mode, win.doc.objects[1].threshold) == ("line", 128)
+
+
+def test_image_panel_without_selection_shows_the_default(qtbot):
+    win = _window(qtbot, image_mode="photo", image_threshold=90)
+    panel = win.panel("image")
+    panel.refresh()
+    assert panel.photo.isChecked() and panel.threshold.value() == 90
+    assert panel.threshold_value.value() == 90
+    panel.set_defaults("line", 200)                                  # nach dem Speichern
+    assert panel.line.isChecked() and panel.threshold.value() == 200
diff --git a/tests/gui/test_gui_language.py b/tests/gui/test_gui_language.py
index 1b4edbd..b8a679e 100644
--- a/tests/gui/test_gui_language.py
+++ b/tests/gui/test_gui_language.py
@@ -42,7 +42,8 @@ def test_restart_notice_stays_next_to_save(qtbot, tmp_path):
     """Der Hinweis steht unten neben SPEICHERN – auch im Reiter Tastenkürzel sichtbar – und
     vergleicht mit dem Stand beim Start: wieder zurückgestellt, kein Hinweis."""
     dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
-                            started={"language": "en", "start_zoom": 200})
+                            started={"language": "en", "start_zoom": 200,
+                                     "start_tool": "paper"})
     qtbot.addWidget(dialog)
     dialog.show()
     assert dialog.restart_hint.isHidden()
@@ -57,7 +58,8 @@ def test_restart_notice_stays_next_to_save(qtbot, tmp_path):
 def test_saved_but_not_restarted_still_shows_the_notice(qtbot, tmp_path):
     """Gespeichert, aber noch nicht neu gestartet: beim nächsten Öffnen steht der Hinweis gleich da."""
     dialog = SettingsDialog(Settings(language="en"), tmp_path / "s.json",
-                            started={"language": "de", "start_zoom": 200})
+                            started={"language": "de", "start_zoom": 200,
+                                     "start_tool": "paper"})
     qtbot.addWidget(dialog)
     assert not dialog.restart_hint.isHidden()
 
diff --git a/tests/gui/test_gui_screenshot.py b/tests/gui/test_gui_screenshot.py
index dee9850..1e41b5e 100644
--- a/tests/gui/test_gui_screenshot.py
+++ b/tests/gui/test_gui_screenshot.py
@@ -246,3 +246,12 @@ def test_screenshot_ends_text_editing_first(qtbot, portal):
     assert win.edit_session.active
     _start(win, qtbot, portal)
     assert not win.edit_session.active
+
+
+def test_screenshot_takes_the_image_default(qtbot, portal, tmp_path):
+    win = _window(qtbot, image_mode="photo", image_threshold=60)
+    _start(win, qtbot, portal)
+    assert win._shot_pending
+    win.screenshot_finished(_shot(tmp_path), None)
+    obj = win.doc.objects[1]
+    assert (obj.mode, obj.threshold) == ("photo", 60)
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index 6835fa5..46c84b4 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -410,3 +410,60 @@ def test_dialog_keeps_recent_files_and_start_favorite(qtbot):
     qtbot.addWidget(dialog)
     values = dialog.values()
     assert (values.recent_files, values.start_favorite) == (["/a.labelwerk"], "Absender")
+
+
+def test_dialog_start_tool_choice(qtbot, tmp_path):
+    path = tmp_path / "s.json"
+    dialog = SettingsDialog(Settings(start_tool="series", last_tool="image"), path)
+    qtbot.addWidget(dialog)
+    combo = dialog.start_tool
+    assert combo.currentData() == "series"
+    assert [combo.itemData(i) for i in range(combo.count())] == [
+        "last", "file", "paper", "text", "image", "barcode", "layout", "series"]
+    assert combo.itemText(0) == "Zuletzt benutzter" and combo.itemText(2) == "Papier"
+    assert dialog.restart_hint.isHidden()
+    combo.setCurrentIndex(combo.findData("last"))
+    assert not dialog.restart_hint.isHidden()                       # wirkt erst beim Start
+    dialog.accept()
+    saved = load_settings(path)
+    assert (saved.start_tool, saved.last_tool) == ("last", "image")  # zuletzt benutzter bleibt
+
+
+def test_dialog_image_defaults(qtbot, tmp_path):
+    path = tmp_path / "s.json"
+    dialog = SettingsDialog(Settings(image_mode="photo", image_threshold=90), path)
+    qtbot.addWidget(dialog)
+    assert dialog.image_mode.currentData() == "photo" and dialog.image_threshold.value() == 90
+    assert [dialog.image_mode.itemText(i) for i in range(2)] == ["Strich", "Foto"]
+    dialog.image_mode.setCurrentIndex(dialog.image_mode.findData("line"))
+    dialog.image_threshold.setValue(150)
+    assert dialog.restart_hint.isHidden()                           # sofort wirksam
+    dialog.accept()
+    saved = load_settings(path)
+    assert (saved.image_mode, saved.image_threshold) == ("line", 150)
+
+
+def test_saved_image_defaults_apply_at_once(qtbot, monkeypatch):
+    from labelwerk.document import Document, TextObject
+    from labelwerk.gui import main_window as mw
+    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
+                     settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+
+    class Dialog:
+        DialogCode = mw.SettingsDialog.DialogCode
+
+        def __init__(self, settings, **kwargs):
+            self.saved = Settings(**{**vars(settings), "image_mode": "photo",
+                                     "image_threshold": 70, "warnings": []})
+
+        def exec(self):
+            return self.DialogCode.Accepted
+
+        def deleteLater(self):
+            pass
+
+    monkeypatch.setattr(mw, "SettingsDialog", Dialog)
+    win.open_settings()
+    panel = win.panel("image")
+    assert panel.photo.isChecked() and panel.threshold.value() == 70
diff --git a/tests/gui/test_gui_start_tool.py b/tests/gui/test_gui_start_tool.py
new file mode 100644
index 0000000..911671f
--- /dev/null
+++ b/tests/gui/test_gui_start_tool.py
@@ -0,0 +1,134 @@
+"""Reiter beim Start (Einstellung „Reiter beim Start“: fester Reiter oder zuletzt benutzter)."""
+import pytest
+
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.gui.tools import START_TOOL, TOOLS
+from labelwerk.settings import START_TOOLS, Settings, load_settings
+
+
+def _window(qtbot, **settings):
+    win = MainWindow(doc=Document("62", objects=[TextObject("A")]),
+                     settings=Settings(check_media_on_start=False, **settings))
+    qtbot.addWidget(win)
+    return win
+
+
+def _current(win) -> str:
+    return next(key for key, action in win.tool_actions.items() if action.isChecked())
+
+
+def test_start_tools_are_the_tools_of_the_window():
+    assert list(START_TOOLS[1:]) == [tool.key for tool in TOOLS]
+
+
+def test_default_start_tool_is_paper(qtbot):
+    win = _window(qtbot)
+    assert START_TOOL == "paper" and _current(win) == "paper"
+    assert win.panels.currentWidget() is win.panel("paper")
+
+
+@pytest.mark.parametrize("key", ["series", "text", "file"])
+def test_fixed_start_tool(qtbot, key):
+    win = _window(qtbot, start_tool=key, last_tool="image")
+    assert _current(win) == key and win.panels.currentWidget() is win.panel(key)
+
+
+def test_last_used_tool(qtbot):
+    win = _window(qtbot, start_tool="last", last_tool="barcode")
+    assert _current(win) == "barcode" and win.panels.currentWidget() is win.panel("barcode")
+
+
+def test_last_used_without_a_value_starts_with_paper(qtbot):
+    assert _current(_window(qtbot, start_tool="last")) == "paper"
+
+
+def test_switching_tabs_remembers_the_last_tool_and_saves_it_on_close(qtbot, monkeypatch):
+    from labelwerk.gui import main_window as mw
+    saved = []
+    monkeypatch.setattr(mw, "save_settings", lambda settings, *a: saved.append(settings.last_tool))
+    win = _window(qtbot)
+    win.tool_actions["series"].trigger()
+    assert win.settings.last_tool == "series"
+    win._show_tool("barcode")                                         # auch ohne Klick
+    assert win.settings.last_tool == "barcode"
+    assert saved == [] and win.result.text() == ""                    # im Speicher, still
+    win.close()
+    assert saved == ["barcode"]                                       # beim Schließen, einmal
+
+
+def test_last_tool_is_not_saved_on_close_when_unchanged(qtbot, monkeypatch):
+    from labelwerk.gui import main_window as mw
+    saved = []
+    monkeypatch.setattr(mw, "save_settings", lambda settings, *a: saved.append(settings.last_tool))
+    win = _window(qtbot, start_tool="last", last_tool="image")
+    win.tool_actions["text"].trigger()
+    win.tool_actions["image"].trigger()                               # wieder wie beim Start
+    win.close()
+    assert saved == []
+
+
+def test_last_tool_reaches_the_file_on_close(qtbot):
+    win = _window(qtbot)
+    win.tool_actions["layout"].trigger()
+    assert load_settings().last_tool != "layout"
+    win.close()
+    assert load_settings().last_tool == "layout"
+
+
+def test_save_error_on_close_is_ignored(qtbot, monkeypatch):
+    from labelwerk.gui import main_window as mw
+
+    def fail(*args):
+        raise OSError("Datenträger voll")
+    monkeypatch.setattr(mw, "save_settings", fail)
+    win = _window(qtbot)
+    win.tool_actions["layout"].trigger()
+    win.close()                                                       # kein Absturz
+    assert not win.isVisible()
+
+
+def test_close_cancelled_saves_nothing(qtbot, monkeypatch):
+    from labelwerk.gui import main_window as mw
+    saved = []
+    monkeypatch.setattr(mw, "save_settings", lambda settings, *a: saved.append(settings.last_tool))
+    win = _window(qtbot)
+    win.show()
+    win.tool_actions["layout"].trigger()
+    monkeypatch.setattr(win.files, "maybe_save", lambda: False)       # Rückfrage: Abbrechen
+    win.close()
+    assert saved == [] and win.isVisible()
+    monkeypatch.setattr(win.files, "maybe_save", lambda: True)
+    win.close()
+    assert saved == ["layout"]
+
+
+def test_start_in_text_tab_creates_text(qtbot):
+    win = _window(qtbot, start_tool="text")
+    assert win.canvas.tool() == "text"
+    assert _window(qtbot, start_tool="image").canvas.tool() == "select"
+
+
+def test_settings_dialog_keeps_the_last_tool(qtbot, monkeypatch):
+    """Der Dialog verändert den zuletzt benutzten Reiter nicht (auch wenn er sich ändert,
+    während der Dialog offen ist)."""
+    from labelwerk.gui import main_window as mw
+    win = _window(qtbot)
+    win.tool_actions["layout"].trigger()
+
+    class Dialog:
+        DialogCode = mw.SettingsDialog.DialogCode
+
+        def __init__(self, settings, **kwargs):
+            self.saved = Settings(**{**vars(settings), "last_tool": "file", "warnings": []})
+
+        def exec(self):
+            win.tool_actions["text"].trigger()                     # während der Dialog offen ist
+            return self.DialogCode.Accepted
+
+        def deleteLater(self):
+            pass
+
+    monkeypatch.setattr(mw, "SettingsDialog", Dialog)
+    win.open_settings()
+    assert win.settings.last_tool == "text"
diff --git a/tests/test_i18n.py b/tests/test_i18n.py
index 1b84556..c153ec4 100644
--- a/tests/test_i18n.py
+++ b/tests/test_i18n.py
@@ -202,7 +202,9 @@ def test_numbers_in_label_content_follow_the_region():
 
 def test_restart_pending():
     from labelwerk.settings import restart_pending
-    started = {"language": "de", "start_zoom": 200}
-    assert not restart_pending("", 200, started)            # Automatisch = Systemsprache (de)
-    assert not restart_pending("de", 200, started)
-    assert restart_pending("en", 200, started) and restart_pending("de", 150, started)
+    started = {"language": "de", "start_zoom": 200, "start_tool": "paper"}
+    assert not restart_pending("", 200, "paper", started)   # Automatisch = Systemsprache (de)
+    assert not restart_pending("de", 200, "paper", started)
+    assert restart_pending("en", 200, "paper", started)
+    assert restart_pending("de", 150, "paper", started)
+    assert restart_pending("de", 200, "last", started)
diff --git a/tests/test_settings.py b/tests/test_settings.py
index da9144a..2407f62 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -354,3 +354,65 @@ def test_fonts_all_default_and_validation(tmp_path):
     path.write_text(json.dumps({"fonts_all": "ja"}))
     s = load_settings(path)
     assert s.fonts_all is False and s.warnings
+
+
+def test_image_defaults_for_new_images(tmp_path):
+    s = Settings()
+    assert (s.image_mode, s.image_threshold) == ("line", 128)  # wie bisher: Strich, Mitte
+    path = tmp_path / "s.json"
+    save_settings(Settings(image_mode="photo", image_threshold=90), path)
+    loaded = load_settings(path)
+    assert (loaded.image_mode, loaded.image_threshold) == ("photo", 90)
+    assert loaded.warnings == []
+
+
+@pytest.mark.parametrize("raw", [{"image_mode": "grau"}, {"image_threshold": 256},
+                                 {"image_threshold": -1}, {"image_threshold": True},
+                                 {"image_threshold": 12.5}, {"image_threshold": "90"}])
+def test_invalid_image_defaults_fall_back_with_warning(tmp_path, raw):
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps(raw))
+    s = load_settings(path)
+    assert (s.image_mode, s.image_threshold) == ("line", 128)
+    assert len(s.warnings) == 1 and next(iter(raw)) in s.warnings[0]
+
+
+# --- Reiter beim Start --------------------------------------------------------------
+def test_start_tool_defaults_and_roundtrip(tmp_path):
+    from labelwerk.settings import START_TOOLS
+    s = Settings()
+    assert (s.start_tool, s.last_tool) == ("paper", "")         # wie bisher: Papier
+    assert START_TOOLS[0] == "last" and "paper" in START_TOOLS
+    path = tmp_path / "s.json"
+    save_settings(Settings(start_tool="last", last_tool="series"), path)
+    loaded = load_settings(path)
+    assert (loaded.start_tool, loaded.last_tool) == ("last", "series")
+    assert loaded.warnings == []
+
+
+@pytest.mark.parametrize("raw", [{"start_tool": "druck"}, {"start_tool": ""}, {"start_tool": 3}])
+def test_invalid_start_tool_falls_back_with_warning(tmp_path, raw):
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps(raw))
+    s = load_settings(path)
+    assert s.start_tool == "paper"
+    assert len(s.warnings) == 1 and "start_tool" in s.warnings[0]
+
+
+@pytest.mark.parametrize("value", ["last", "druck", 3, None])
+def test_invalid_last_tool_is_dropped_quietly(tmp_path, value):
+    """Zuletzt benutzter Reiter ist nur ein gemerkter Wert: ungültig → leer, ohne Hinweis."""
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps({"last_tool": value}))
+    s = load_settings(path)
+    assert s.last_tool == "" and s.warnings == []
+
+
+def test_start_tool_needs_a_restart():
+    from labelwerk.settings import RESTART_KEYS, restart_pending, started_values
+    assert "start_tool" in RESTART_KEYS
+    started = started_values(Settings(start_tool="paper"))
+    assert started["start_tool"] == "paper"
+    language = started["language"]
+    assert not restart_pending(language, 200, "paper", started)
+    assert restart_pending(language, 200, "last", started)
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_start_tool.py, Fälle in tests/test_settings.py, tests/gui/test_gui_image.py, tests/gui/test_gui_settings.py) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 9faa757..4cc5b64 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -47,10 +47,11 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   zpl+file://, zpl+tcp:// mit -m zpl:203.
 - Übersetzungen (Etappe 7): Deutsch und Englisch – Quellsprache im Code Englisch (`_()`), Deutsch in
   `src/labelwerk/po/de.po`; Sprache des Systems, Einstellung „Sprache“ (nach Neustart; farbiger Hinweis
-  „Änderungen erst nach Neustart aktiv“ im Einstellungsfenster neben SPEICHERN, für Sprache und Start-Zoom),
+  „Änderungen erst nach Neustart aktiv“ im Einstellungsfenster neben SPEICHERN, für Sprache, Start-Zoom und Reiter beim Start),
   CLI `--lang` (auch argparse-Texte); Zahlen mit dem Dezimaltrenner der Sprache (Eingabe Komma und Punkt),
   Excel-Zahlen im Etikett nach der Region des Systems; `{Nummer}`/`{Number}` und „Spalte n“/„Column n“ in
   jeder Sprache; Symbole mit deutschen und englischen Namen (Suche in beiden); Layout-Test je Sprache.
+- Einstellungen: Reiter beim Start (fest oder zuletzt benutzter), Standard für neue Bilder (Strich/Foto, Schwelle).
 - 2536 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
@@ -146,13 +147,16 @@ src/labelwerk/
               Strichcodes), rotation, text, error (QR_LEVELS); kein w_mm – Breite aus dem Inhalt; nie leer
               Frame (frozen): style FRAME_STYLES (single/double/thick_thin/dashed/dotted/corners), rounded, line_mm 0,1–3,
               inset_mm/padding_mm 0–10; Document.frame (None = kein Rahmen)
-  settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic), `image_crop`/`image_rotate` (Bilder einfügen),
+  settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic), `image_crop`/`image_rotate`/`image_mode`/
+              `image_threshold` (Bilder einfügen: Zuschnitt, Drehen, Strich/Foto, Schwelle neuer Bilder; Symbole nicht),
+              `start_tool` (Reiter beim Start: START_TOOLS = „last“ + Werkzeug-Schlüssel, gleich mit gui/tools.py TOOLS – Test)/
+              `last_tool` (zuletzt benutzter Reiter: GUI merkt ihn im Speicher, schreibt beim Schließen; ungültig → "" ohne Hinweis, QUIET_KEYS),
               `symbols_recent` (höchstens 24)/`symbols_favorites` (Symbol-ids), `recent_files` (höchstens 10)/`start_favorite`
               (der Einstellungsdialog reicht sie durch); Drucker: `printer` (gewählte URI, "" = automatisch), `printer_model`
               (Ersatz), `last_model` (zuletzt erkannt), `network_printers` ({name, host, model}; valid_host: IPv4/Name ohne
               Port/Schema/Steuerzeichen; Modell auch zpl:…), network_entries(settings); `printer_options` (Modell →
               Druck-Optionen: CUPS-Schnitt-Optionen, Zebra-Modus; je Eintrag geprüft, leerer Wert erlaubt), `zebra_dpi`
-              (0 = erkannt), `language` ("" = System); RESTART_KEYS (language, start_zoom), started_values/
+              (0 = erkannt), `language` ("" = System); RESTART_KEYS (language, start_zoom, start_tool), started_values/
               restart_pending (wirksamer Vergleich mit dem Start), configured_language (vor allem anderen gelesen);
               load_settings(path, model=None): Etikett muss nur ein bekanntes Etikett sein (auch
               „BxHmm@dpi“; ob es zum Drucker passt, prüfen GUI und CLI)
@@ -246,7 +250,8 @@ src/labelwerk/
     symbol_dialog.py Fenster „Symbol einfügen“ (SymbolDialog, Werkzeugfenster, nicht modal; Enter/Esc/Kontextmenü): Suche, Gruppen + Untergruppe, Raster über
                     SymbolModel (Vorschau erst bei Bedarf gerastert), Ziehen (MIME_SYMBOL = id), ★ Favorit, Ordner öffnen (open_url ersetzbar)
     panels/image.py Reiter Bild: Aus Datei/Aus Zwischenablage/Bildschirmfoto/Symbol, Quelle, Strich/Foto, Schwelle (Regler = ein Schritt), Umkehren,
-                    Zuschnitt (Symbole: Tintenbox, sonst Schnittmarken-Erkennung; Fallback ohne Inhalt: ganzes Bild + Hinweis), Originalgröße 1:1, Seitenverhältnis, Drehen (Aktionen), Position
+                    Zuschnitt (Symbole: Tintenbox, sonst Schnittmarken-Erkennung; Fallback ohne Inhalt: ganzes Bild + Hinweis), Originalgröße 1:1, Seitenverhältnis, Drehen (Aktionen), Position;
+                    ohne Auswahl Standard für neue Bilder (set_defaults aus den Einstellungen)
     image_import.py Bilder beschaffen: rasterize_svg (Raster-Funktion für Vektorbilder); load (SVG per QSvgRenderer bei 300 dpi, Maße mit Einheit selbst gelesen: svg_size; sonst files.load_image), load_symbol (Symbol: Vorschau 600 dpi bei SYMBOL_MM,
                     auf die Tinte zugeschnitten, SVG-Bytes), SYMBOL_SOURCE/is_symbol_source (Panel schneidet Symbole mit files.ink_box zu), MIME_SYMBOL; load_screenshot (Bildschirmfoto: 300 dpi, Dateiangabe gilt nicht;
                     Quelle SCREENSHOT), page_count,
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index afd88b3..e3ad36a 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -178,9 +178,12 @@ class MainWindow(QMainWindow):
             group.addAction(action)
             toolbar.addAction(action)
             self.tool_actions[tool.key] = action
-        start = START_TOOL if START_TOOL in self.tool_actions else next(iter(self.tool_actions))
+        start = self._start_tool()
         self.tool_actions[start].setChecked(True)
         self.panels.setCurrentWidget(self._panel_by_key[start])
+        self.panels.currentChanged.connect(self._remember_tool)    # erst nach dem Start-Reiter
+        self._stored_tool = self.settings.last_tool   # zuletzt benutzter Reiter, wie in der Datei
+        self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
         spacer = QWidget()
         spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
         toolbar.addWidget(spacer)
@@ -263,6 +266,7 @@ class MainWindow(QMainWindow):
         self.statusBar().addWidget(self.cancel_button)
         # Stand beim Start: der Einstellungsdialog zeigt danach, was erst ein Neustart ändert
         self._started = started_values(self.settings)
+        self._sync_tool()                           # Start im Reiter Text: „Text anlegen“
         self.zoom_label = QLabel()
         for text, delta in (("−", -ZOOM_STEP), ("+", ZOOM_STEP)):
             button = QToolButton()
@@ -417,6 +421,25 @@ class MainWindow(QMainWindow):
             else:
                 bar.addAction(self.shortcut_actions[entry[0]])   # Symbol setzt apply_theme_icons
 
+    def _start_tool(self) -> str:
+        """Reiter beim Start: Einstellung ``start_tool`` („last“ = zuletzt benutzter); ohne
+        gültigen Wert ``START_TOOL``."""
+        wanted = self.settings.start_tool
+        if wanted == "last":
+            wanted = self.settings.last_tool
+        for key in (wanted, START_TOOL):
+            if key in self.tool_actions:
+                return key
+        return next(iter(self.tool_actions))
+
+    def _remember_tool(self, _index: int = 0) -> None:
+        """Gezeigten Reiter als zuletzt benutzten merken (``last_tool``) – nur im Speicher: jeder
+        Klick auf ein Objekt kann den Reiter wechseln; auf die Platte kommt er beim Schließen."""
+        key = next((k for k, panel in self._panel_by_key.items()
+                    if panel is self.panels.currentWidget()), "")
+        if key:
+            self.settings.last_tool = key
+
     def _show_tool(self, key: str) -> None:
         """Panel eines Werkzeugs zeigen (wie ein Klick auf seinen Knopf)."""
         self.tool_actions[key].setChecked(True)
@@ -1345,6 +1368,7 @@ class MainWindow(QMainWindow):
         """Einstellungen still speichern (Zuletzt verwendet, Favoriten); Fehler in die Statusleiste."""
         try:
             save_settings(self.settings)
+            self._stored_tool = self.settings.last_tool
         except OSError as e:
             self._set_result(str(e), "error")
 
@@ -1374,13 +1398,16 @@ class MainWindow(QMainWindow):
                    notes: list[str], svg: bytes | None = None) -> ImageObject:
         """Bild-Objekt 1:1, automatisch zugeschnitten (alles, was nicht weiß ist; Einstellung
         ``image_crop``); ist das Bild ganz weiß, bleibt es ganz – mit Hinweis in ``notes``.
-        Mit ``svg`` ein Vektorbild (``image`` ist dessen Vorschau)."""
-        if not self.settings.image_crop:
-            return ImageObject.from_image(image, dpi, source, page, None, svg)
-        crop = crop_box(image, dpi, ink=NOT_WHITE)
-        if crop is None and _(CROP_FAILED) not in notes:
-            notes.append(_(CROP_FAILED))
-        return ImageObject.from_image(image, dpi, source, page, crop, svg)
+        Mit ``svg`` ein Vektorbild (``image`` ist dessen Vorschau). Strich/Foto und Schwelle aus
+        den Einstellungen (``image_mode``, ``image_threshold``)."""
+        crop = None
+        if self.settings.image_crop:
+            crop = crop_box(image, dpi, ink=NOT_WHITE)
+            if crop is None and _(CROP_FAILED) not in notes:
+                notes.append(_(CROP_FAILED))
+        obj = ImageObject.from_image(image, dpi, source, page, crop, svg)
+        obj.mode, obj.threshold = self.settings.image_mode, self.settings.image_threshold
+        return obj
 
     def _insert_images(self, objects: list[ImageObject], at: tuple[float, float] | None,
                        notes: list[str], state: str = "warn", rotate: bool | None = None) -> None:
@@ -1632,6 +1659,12 @@ class MainWindow(QMainWindow):
         self._shot_pending = False                  # keine Auswahl und kein Einfügen mehr
         if self._shooting:
             self._end_shooting()
+        if self.settings.last_tool != self._stored_tool:   # zuletzt benutzter Reiter, still
+            try:
+                save_settings(self.settings)
+                self._stored_tool = self.settings.last_tool
+            except OSError:
+                pass                                # beim Beenden: nichts mehr zu melden
         super().closeEvent(event)
 
     # --- Einstellungen ----------------------------------------------------
@@ -1658,6 +1691,7 @@ class MainWindow(QMainWindow):
             # während der Dialog offen war, kann sich Drucker/letztes Modell geändert haben
             saved.printer, saved.last_model = self.settings.printer, self.settings.last_model
             saved.printer_options = self.settings.printer_options
+            saved.last_tool = self.settings.last_tool
             if saved.printer.startswith(("tcp://", "zpl+tcp://")) and saved.printer not in {
                     p.uri for p in network_printers(network_entries(saved))}:
                 saved.printer = ""                  # Netzwerkdrucker entfernt/geändert: automatisch
@@ -1671,6 +1705,7 @@ class MainWindow(QMainWindow):
             apply_shortcuts(self.shortcut_actions,
                             without_conflicts(effective(self.settings.shortcuts))[0])
             self.files.refresh_lists()                  # „Beim Start“ im Reiter Datei
+            self.panel("image").set_defaults(self.settings.image_mode, self.settings.image_threshold)
             self.refresh_printer()                      # Netzwerkdrucker, Ersatzmodell
             self._set_result(_("Settings saved – they apply to new labels."), "ok")
 
diff --git a/src/labelwerk/gui/panels/image.py b/src/labelwerk/gui/panels/image.py
index 19f2ec7..b1d1beb 100644
--- a/src/labelwerk/gui/panels/image.py
+++ b/src/labelwerk/gui/panels/image.py
@@ -20,6 +20,7 @@ from ...document import Document, ImageObject
 from ...files import NOT_WHITE, crop_box, ink_box
 from ...i18n import N_, _
 from ...layout import Rect
+from ...settings import Settings
 from ..image_import import is_symbol_source, source_title
 from ..symbols import SIZE, line_icon
 from ..widgets import SpinBox
@@ -42,6 +43,8 @@ class ImagePanel(Panel):
     def __init__(self, doc: Document):
         super().__init__(doc, _("Image"))
         self.index: int | None = None   # bearbeitetes Bild; None = keins ausgewählt
+        # ohne Auswahl gezeigt: Standard für neue Bilder (set_defaults; vorher der aus Settings)
+        self._defaults = (Settings.image_mode, Settings.image_threshold)
         self._updating = False
 
         self.hint = QLabel(_(HINT))
@@ -183,6 +186,11 @@ class ImagePanel(Panel):
                 self.rotate_right, self.position)
 
     # --- Modell → Panel -----------------------------------------------------
+    def set_defaults(self, mode: str, threshold: int) -> None:
+        """Standard für neue Bilder (Einstellungen) – zeigt das Panel ohne Auswahl."""
+        self._defaults = (mode, threshold)
+        self.refresh()
+
     def refresh(self) -> None:
         if self.index is not None and not (0 <= self.index < len(self.doc.objects)
                                            and isinstance(self.obj, ImageObject)):
@@ -195,9 +203,10 @@ class ImagePanel(Panel):
         try:
             if not selected:
                 self._show_source("")
-                self.line.setChecked(True)
-                self.threshold.setValue(128)
-                self.threshold_value.setValue(128)
+                mode, threshold = self._defaults
+                (self.photo if mode == "photo" else self.line).setChecked(True)
+                self.threshold.setValue(threshold)
+                self.threshold_value.setValue(threshold)
                 for box in (self.invert, self.crop, self.keep_ratio):
                     box.setChecked(False)
                 self.show_frame(None)
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 4feb10d..01cfd96 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -24,6 +24,7 @@ from ..printer import DEFAULT_MODEL
 from ..printers import SUPPORTED_MODELS, capabilities
 from ..settings import (Settings, restart_pending, save_settings, started_values,
                         valid_host)
+from .tools import TOOLS
 from .widgets import DoubleSpinBox, FontCombo, SpinBox
 
 # englisch (N_), angezeigt wird _(…)
@@ -56,6 +57,7 @@ class SettingsDialog(QDialog):
         self._recent_files = settings.recent_files                             # nur durchgereicht
         self._printer, self._last_model = settings.printer, settings.last_model   # nur durchgereicht
         self._printer_options = settings.printer_options                          # nur durchgereicht
+        self._last_tool = settings.last_tool                                      # nur durchgereicht
         outer = QVBoxLayout(self)
         self.tabs = QTabWidget()
         outer.addWidget(self.tabs)
@@ -129,6 +131,17 @@ class SettingsDialog(QDialog):
         self.image_rotate.setToolTip(_("Off: images that are too large are reduced – saves tape"))
         self.image_rotate.setChecked(settings.image_rotate)
         form.addRow(self.image_rotate)
+        self.image_mode = QComboBox()
+        self.image_mode.addItem(_("Line art"), "line")
+        self.image_mode.addItem(_("Photo"), "photo")
+        self.image_mode.setCurrentIndex(max(0, self.image_mode.findData(settings.image_mode)))
+        self.image_mode.setToolTip(_("Conversion of new images (symbols stay line art)"))
+        form.addRow(_("Conversion"), self.image_mode)
+        self.image_threshold = SpinBox()
+        self.image_threshold.setRange(0, 255)
+        self.image_threshold.setValue(settings.image_threshold)
+        self.image_threshold.setToolTip(_("Threshold of new images – higher = darker"))
+        form.addRow(_("Threshold"), self.image_threshold)
 
         form = self._section(layout, _("Printer"))
         self.check_media = QCheckBox(_("Check the roll at startup and when the printer is switched on"))
@@ -176,6 +189,12 @@ class SettingsDialog(QDialog):
         self.zoom.setSingleStep(10)
         self.zoom.setValue(settings.start_zoom)
         form.addRow(_("Start zoom"), self.zoom)
+        self.start_tool = QComboBox()
+        self.start_tool.addItem(_("Last used"), "last")
+        for tool in TOOLS:
+            self.start_tool.addItem(_(tool.title), tool.key)
+        self.start_tool.setCurrentIndex(max(0, self.start_tool.findData(settings.start_tool)))
+        form.addRow(_("Tab at startup"), self.start_tool)
         self.theme = QComboBox()
         self.theme.addItem("RawBlock", "rawblock")
         self.theme.addItem(_("Classic"), "classic")
@@ -206,9 +225,10 @@ class SettingsDialog(QDialog):
         self.restart_hint.hide()
         self.language.currentIndexChanged.connect(self._update_restart_hint)
         self.zoom.valueChanged.connect(self._update_restart_hint)
+        self.start_tool.currentIndexChanged.connect(self._update_restart_hint)
 
-        hint = QLabel(_("“New label” applies to new labels, start zoom and language from the next "
-                        "start, everything else immediately."))
+        hint = QLabel(_("“New label” applies to new labels, start zoom, tab at startup and language "
+                        "from the next start, everything else immediately."))
         hint.setWordWrap(True)
         layout.addWidget(hint)
         layout.addStretch()
@@ -402,7 +422,8 @@ class SettingsDialog(QDialog):
     def restart_needed(self) -> bool:
         """Wirkt eine gewählte Einstellung erst nach einem Neustart anders als jetzt? (Liest nur die
         Felder der Neustart-Einstellungen – keine Prüfung anderer Felder.)"""
-        return restart_pending(self.language.currentData(), self.zoom.value(), self._started)
+        return restart_pending(self.language.currentData(), self.zoom.value(),
+                               self.start_tool.currentData(), self._started)
 
     def _update_restart_hint(self) -> None:
         self.restart_hint.setVisible(self.restart_needed())
@@ -418,9 +439,13 @@ class SettingsDialog(QDialog):
             fonts_all=self.fonts_all.isChecked(),
             check_media_on_start=self.check_media.isChecked(),
             start_zoom=self.zoom.value(),
+            start_tool=self.start_tool.currentData(),
+            last_tool=self._last_tool,
             theme=self.theme.currentData(),
             image_crop=self.image_crop.isChecked(),
             image_rotate=self.image_rotate.isChecked(),
+            image_mode=self.image_mode.currentData(),
+            image_threshold=self.image_threshold.value(),
             symbols_recent=list(self._symbols[0]),
             symbols_favorites=list(self._symbols[1]),
             recent_files=list(self._recent_files),
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index 95b920e..e1ea9cc 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -479,9 +479,14 @@ msgid "Continuous"
 msgstr "Endlos"
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Conversion"
 msgstr "Umwandlung"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Conversion of new images (symbols stay line art)"
+msgstr "Umwandlung neuer Bilder (Symbole bleiben Strich)"
+
 #: src/labelwerk/shortcuts.py
 msgid "Copy"
 msgstr "Kopieren"
@@ -1162,6 +1167,10 @@ msgstr "Sprache"
 msgid "Larger font"
 msgstr "Schrift größer"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Last used"
+msgstr "Zuletzt benutzter"
+
 #: src/labelwerk/gui/panels/layout.py
 #: src/labelwerk/gui/tools.py
 msgid "Layout"
@@ -1176,6 +1185,7 @@ msgid "Line"
 msgstr "Linie"
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Line art"
 msgstr "Strich"
 
@@ -1620,6 +1630,7 @@ msgid "Peel off (dispenser only)"
 msgstr "Ablösen (nur mit Spender)"
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Photo"
 msgstr "Foto"
 
@@ -2248,6 +2259,10 @@ msgstr "Symbol: {name}"
 msgid "TABLE …"
 msgstr "TABELLE …"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Tab at startup"
+msgstr "Reiter beim Start"
+
 #: src/labelwerk/gui/main_window.py
 msgid "Table for the series"
 msgstr "Tabelle für die Serie"
@@ -2341,6 +2356,7 @@ msgid "Thick-thin"
 msgstr "Dick-dünn"
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Threshold"
 msgstr "Schwelle"
 
@@ -2349,6 +2365,10 @@ msgstr "Schwelle"
 msgid "Threshold must be a whole number from 0 to 255, not {threshold!r}."
 msgstr "Schwelle muss eine ganze Zahl von 0 bis 255 sein, nicht {threshold!r}."
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Threshold of new images – higher = darker"
+msgstr "Schwelle neuer Bilder – höher = mehr Schwarz"
+
 #: src/labelwerk/gui/main_window.py
 msgid "Tools"
 msgstr "Werkzeuge"
@@ -3102,8 +3122,8 @@ msgid "Ø {width} mm · round"
 msgstr "Ø {width} mm · rund"
 
 #: src/labelwerk/gui/settings_dialog.py
-msgid "“New label” applies to new labels, start zoom and language from the next start, everything else immediately."
-msgstr "„Neues Etikett“ gilt für neue Etiketten, Startzoom und Sprache ab dem nächsten Start, alles andere sofort."
+msgid "“New label” applies to new labels, start zoom, tab at startup and language from the next start, everything else immediately."
+msgstr "„Neues Etikett“ gilt für neue Etiketten, Startzoom, Reiter beim Start und Sprache ab dem nächsten Start, alles andere sofort."
 
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index 3125ac7..17e809a 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -470,9 +470,14 @@ msgid "Continuous"
 msgstr ""
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Conversion"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Conversion of new images (symbols stay line art)"
+msgstr ""
+
 #: src/labelwerk/shortcuts.py
 msgid "Copy"
 msgstr ""
@@ -1153,6 +1158,10 @@ msgstr ""
 msgid "Larger font"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Last used"
+msgstr ""
+
 #: src/labelwerk/gui/panels/layout.py
 #: src/labelwerk/gui/tools.py
 msgid "Layout"
@@ -1167,6 +1176,7 @@ msgid "Line"
 msgstr ""
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Line art"
 msgstr ""
 
@@ -1603,6 +1613,7 @@ msgid "Peel off (dispenser only)"
 msgstr ""
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Photo"
 msgstr ""
 
@@ -2227,6 +2238,10 @@ msgstr ""
 msgid "TABLE …"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Tab at startup"
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "Table for the series"
 msgstr ""
@@ -2320,6 +2335,7 @@ msgid "Thick-thin"
 msgstr ""
 
 #: src/labelwerk/gui/panels/image.py
+#: src/labelwerk/gui/settings_dialog.py
 msgid "Threshold"
 msgstr ""
 
@@ -2328,6 +2344,10 @@ msgstr ""
 msgid "Threshold must be a whole number from 0 to 255, not {threshold!r}."
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Threshold of new images – higher = darker"
+msgstr ""
+
 #: src/labelwerk/gui/main_window.py
 msgid "Tools"
 msgstr ""
@@ -3079,7 +3099,7 @@ msgid "Ø {width} mm · round"
 msgstr ""
 
 #: src/labelwerk/gui/settings_dialog.py
-msgid "“New label” applies to new labels, start zoom and language from the next start, everything else immediately."
+msgid "“New label” applies to new labels, start zoom, tab at startup and language from the next start, everything else immediately."
 msgstr ""
 
 #: src/labelwerk/gui/settings_dialog.py
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 1cca212..a403e2b 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -16,14 +16,18 @@ from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, Tex
 from .fonts import DEFAULT_FAMILY
 from . import i18n
 from .i18n import N_, _
+from .imaging import MODES
 from .labels import labels_for_model, sized_label
 from . import zpl
 from .printers import SUPPORTED_MODELS, NetworkEntry, effective_model, is_model
 from .storage import RECENT_FILES
 
 THEMES = ("rawblock", "classic")
-RESTART_KEYS = ("language", "start_zoom")   # wirken erst nach einem Neustart (Hinweis in der GUI)
+RESTART_KEYS = ("language", "start_zoom", "start_tool")   # wirken erst nach einem Neustart (Hinweis)
+# Reiter beim Start: „last“ = zuletzt benutzter, sonst Schlüssel der Werkzeuge (gui/tools.py TOOLS)
+START_TOOLS = ("last", "file", "paper", "text", "image", "barcode", "layout", "series")
 SYMBOL_LISTS = ("symbols_recent", "symbols_favorites")
+QUIET_KEYS = ("last_tool",)   # nur gemerkt, nicht vom Nutzer eingestellt: ungültig → Standard ohne Hinweis
 
 
 @dataclass
@@ -36,9 +40,13 @@ class Settings:
     fonts_all: bool = False                # Schriftauswahl: alle Familien statt der kurzen Liste
     check_media_on_start: bool = True
     start_zoom: int = 200
+    start_tool: str = "paper"              # Reiter beim Start (START_TOOLS; "last" = zuletzt benutzter)
+    last_tool: str = ""                    # zuletzt benutzter Reiter (still gespeichert)
     theme: str = "rawblock"                # "rawblock" oder "classic" (Qt-Systemstil)
     image_crop: bool = True                # Bilder beim Einfügen auf den Inhalt zuschneiden
     image_rotate: bool = False             # Bilder drehen, wenn sie nur gedreht 1:1 passen
+    image_mode: str = "line"               # neue Bilder: Strich ("line") oder Foto ("photo")
+    image_threshold: int = 128             # neue Bilder: Schwelle 0–255
     symbols_recent: list[str] = field(default_factory=list)      # Symbol-ids, neueste zuerst
     symbols_favorites: list[str] = field(default_factory=list)   # Symbol-ids
     recent_files: list[str] = field(default_factory=list)   # Zuletzt geöffnet (Pfade), neueste zuerst
@@ -75,6 +83,10 @@ def _rules(model: str | None = None) -> dict:
         "theme": lambda v: v in THEMES,
         "image_crop": lambda v: isinstance(v, bool),
         "image_rotate": lambda v: isinstance(v, bool),
+        "image_mode": lambda v: v in MODES,
+        "image_threshold": lambda v: _is_int(v) and 0 <= v <= 255,
+        "start_tool": lambda v: v in START_TOOLS,
+        "last_tool": lambda v: v == "" or (v in START_TOOLS and v != "last"),
         "symbols_recent": lambda v: isinstance(v, list),
         "symbols_favorites": lambda v: isinstance(v, list),
         "recent_files": lambda v: isinstance(v, list),
@@ -117,11 +129,12 @@ def started_values(settings: Settings) -> dict:
     return {**{key: getattr(settings, key) for key in RESTART_KEYS}, "language": i18n.language()}
 
 
-def restart_pending(language: str, start_zoom: int, started: dict) -> bool:
+def restart_pending(language: str, start_zoom: int, start_tool: str, started: dict) -> bool:
     """Wirkt eine Einstellung erst nach einem Neustart anders als jetzt? Sprache wirksam verglichen
-    ("" = Systemsprache), Start-Zoom mit dem Wert beim Start."""
+    ("" = Systemsprache), Start-Zoom und Reiter beim Start mit dem Wert beim Start."""
     effective = language if language in i18n.available() else i18n.system_language()
-    return effective != started["language"] or start_zoom != started["start_zoom"]
+    return (effective != started["language"] or start_zoom != started["start_zoom"]
+            or start_tool != started["start_tool"])
 
 
 def configured_language(path: str | Path | None = None) -> str:
@@ -177,7 +190,7 @@ def load_settings(path: str | Path | None = None, model: str | None = None) -> S
             elif key == "printer_options":
                 value = _printer_options(value, settings.warnings)
             setattr(settings, key, value)
-        else:
+        elif key not in QUIET_KEYS:
             settings.warnings.append(_("Setting {key!r} invalid ({value!r}) – using default "
                                        "{default!r}.").format(key=key, value=value,
                                                               default=getattr(settings, key)))
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2621 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/image.py src/labelwerk/gui/settings_dialog.py src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/settings.py tests/gui/test_gui_image.py tests/gui/test_gui_language.py tests/gui/test_gui_screenshot.py tests/gui/test_gui_settings.py tests/gui/test_gui_start_tool.py tests/test_i18n.py tests/test_settings.py
git commit -m "Reiter beim Start (fest oder zuletzt benutzter) und Standard für neue Bilder (Strich/Foto, Schwelle) in den Einstellungen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Bürodrucker ausblenden

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/cli.py`
- Modify: `src/labelwerk/cups.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/printers.py`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/gui/test_gui_cups.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_cups.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `cups.Queue.office`, `cups.is_office(default)`, Einordnung über die PPD bzw. `lpoptions` (parallel, Gesamtfrist, gemerkt), `queues(…, classify=)`; `printers.cups_printers(…, office=, hidden=)`; `settings.cups_all`; Einstellungsdialog „Alle CUPS-Drucker zeigen“; CLI `labelwerk printers --all` und Hinweis auf ausgeblendete.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_cups.py b/tests/gui/test_gui_cups.py
index d58c25b..29c6feb 100644
--- a/tests/gui/test_gui_cups.py
+++ b/tests/gui/test_gui_cups.py
@@ -92,3 +92,50 @@ def test_queues_are_never_chosen_automatically(qtbot, monkeypatch, queue):
     assert win.printer is None and win.model == "QL-600"     # Bürodrucker im Netz bleiben aus
     assert "cups:Dymo" in [p.uri for p in win.printers]
     assert load_settings().last_model in ("", "QL-600")
+
+
+@pytest.fixture
+def office(monkeypatch):
+    """„Dymo“ (Etiketten) und „Buero“ (A4/Letter, ein Bürodrucker)."""
+    def run(*args, **kw):
+        if args[0] == "lpstat":
+            return ("Dymo\nBuero\n" if args[1] == "-e" else
+                    "device for Dymo: usb://DYMO/LabelWriter%20450\n"
+                    "device for Buero: ipp://10.0.0.7/ipp/print\n")
+        if args[0] == "lpoptions":
+            return OPTIONS if args[2] == "Dymo" else "PageSize/Media Size: Letter *A4\n"
+        return ""
+    monkeypatch.setattr(cups, "_run", run)
+
+
+def _menu(win):
+    win._fill_printer_menu()
+    return [a.text() for a in win.printer_menu.actions() if a.text()]
+
+
+def test_office_printers_are_hidden_in_the_menu(qtbot, monkeypatch, office):
+    win = _window(qtbot, monkeypatch, [QL600])
+    assert "Dymo · CUPS – ungeprüft" in _menu(win)
+    assert not any("Buero" in t for t in _menu(win))
+
+
+def test_office_printers_with_the_setting(qtbot, monkeypatch, office):
+    win = _window(qtbot, monkeypatch, [QL600], cups_all=True)
+    assert "Buero · CUPS – ungeprüft" in _menu(win)
+
+
+def test_chosen_office_printer_stays_in_the_menu(qtbot, monkeypatch, office):
+    win = _window(qtbot, monkeypatch, [QL600], printer="cups:Buero")
+    assert "Buero · CUPS – ungeprüft" in _menu(win) and win.printer.uri == "cups:Buero"
+
+
+def test_show_all_cups_printers_in_the_settings(qtbot, tmp_path):
+    from labelwerk.gui.settings_dialog import SettingsDialog
+    from labelwerk.settings import Settings
+    path = tmp_path / "s.json"
+    dialog = SettingsDialog(Settings(), path)
+    qtbot.addWidget(dialog)
+    assert not dialog.cups_all.isChecked()
+    dialog.cups_all.setChecked(True)
+    dialog.accept()
+    assert load_settings(path).cups_all is True
diff --git a/tests/test_cli.py b/tests/test_cli.py
index 6a75c5d..e6488f9 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -574,6 +574,77 @@ def test_model_and_route_mismatch_is_a_message(capsys):
     assert "passt nicht zum Drucker" in capsys.readouterr().err
 
 
+@pytest.fixture
+def office_queue(monkeypatch):
+    """„Etiketten“ (Dymo-Größen) und „Buero“ (A4/Letter) in CUPS."""
+    from labelwerk import cups
+    calls = []
+
+    def run(*args, **kw):
+        calls.append(args)
+        if args[0] == "lpstat":
+            return ("Buero\nEtiketten\n" if args[1] == "-e" else
+                    "device for Buero: ipp://10.0.0.9/ipp/print\n"
+                    "device for Etiketten: usb://DYMO/LabelWriter%20450\n")
+        if args[0] == "lpoptions":
+            return ("PageSize/Media Size: Letter *A4\n" if args[2] == "Buero"
+                    else "PageSize/Media Size: *57x32mm\n")
+        return "request id is Etiketten-3 (1 file(s))\n" if args[0] == "lp" else ""
+    monkeypatch.setattr(cups, "_run", run)
+    return calls
+
+
+def test_office_printers_are_not_listed(office_queue, capsys):
+    assert main(["printers"]) == 0
+    out = capsys.readouterr().out
+    assert "Etiketten · CUPS" in out and "Buero ·" not in out
+    assert ("1 Bürodrucker ausgeblendet – „labelwerk printers --all“ zeigt ihn, drucken mit "
+            "-p cups:NAME") in out
+
+
+def test_all_printers_option_lists_office_printers_without_asking(office_queue, capsys):
+    assert main(["printers", "--all"]) == 0
+    out = capsys.readouterr().out
+    assert "Buero · CUPS" in out and "ausgeblendet" not in out
+    assert not any(c[0] == "lpoptions" for c in office_queue)    # nichts einzuordnen
+
+
+def test_office_printers_are_listed_with_the_setting(office_queue, capsys):
+    _write_settings(cups_all=True)
+    assert main(["printers"]) == 0
+    assert "Buero · CUPS" in capsys.readouterr().out
+    assert not any(c[0] == "lpoptions" for c in office_queue)
+
+
+def test_chosen_office_printer_is_listed(office_queue, capsys):
+    _write_settings(printer="cups:Buero")
+    assert main(["printers"]) == 0
+    assert "Buero · CUPS" in capsys.readouterr().out
+
+
+def test_backend_cups_skips_office_printers(office_queue, capsys):
+    assert main(["print", "Hallo", "-b", "cups", "-l", "57x32mm@300"]) == 0
+    assert "Auftrag Etiketten-3" in capsys.readouterr().out
+
+
+def test_explicit_queue_is_not_classified(office_queue, capsys):
+    assert main(["print", "Hallo", "-p", "cups:Buero", "-l", "57x32mm@300"]) == 0
+    assert ("lpoptions", "-p", "Etiketten", "-l") not in office_queue   # nur Buero (Etiketten)
+
+
+def test_backend_cups_names_hidden_office_printers(monkeypatch, capsys):
+    from labelwerk import cups
+
+    def run(*args, **kw):
+        if args[0] == "lpstat":
+            return "Buero\n" if args[1] == "-e" else ""
+        return "PageSize/Media Size: Letter *A4\n" if args[0] == "lpoptions" else ""
+    monkeypatch.setattr(cups, "_run", run)
+    assert main(["print", "Hallo", "-b", "cups", "-l", "62"]) == 2
+    err = capsys.readouterr().err
+    assert "Keine CUPS-Warteschlange" in err and "Bürodrucker ausgeblendet: Buero" in err
+
+
 def test_backend_cups_takes_the_first_queue(cups_queue, capsys):
     assert main(["print", "Hallo", "-b", "cups", "-l", "57x32mm@300"]) == 0
     assert "Auftrag Buero-7" in capsys.readouterr().out
diff --git a/tests/test_cups.py b/tests/test_cups.py
index 08feac2..88e9fa7 100644
--- a/tests/test_cups.py
+++ b/tests/test_cups.py
@@ -41,6 +41,8 @@ def fake(monkeypatch, tmp_path):
     def run(*args, **kw):
         calls.append(args)
         key = " ".join(args[:2]) if args[0] == "lpstat" else args[0]
+        if args[0] == "lpoptions" and f"lpoptions {args[2]}" in outputs:
+            key = f"lpoptions {args[2]}"                   # je Warteschlange eigene Ausgabe
         out = outputs[key]
         if isinstance(out, Exception):
             raise out
@@ -69,7 +71,7 @@ def test_queues_are_read_in_the_background(fake, monkeypatch):
     assert cups.queues() == []                         # die Oberfläche wartet nicht
     cups._queues_thread.join(5)
     assert [q.name for q in cups.queues()][0] == "Dymo_LabelWriter_450"
-    assert len(calls) == 2                             # gemerkt, nicht jedes Mal gefragt
+    assert len(calls) == 2 + 3        # lpstat -e/-v, je Warteschlange lpoptions; gemerkt, nicht jedes Mal
 
 
 def test_localized_output_is_understood(fake):
@@ -204,6 +206,118 @@ def test_missing_commands_and_failures(monkeypatch):
         REAL_RUN("lp", "-d", "x")
 
 
+# --- Bürodrucker ------------------------------------------------------------------------------
+# Papiergrößen wie von lpoptions -l (Standard mit „*“), Namen aus echten Treibern
+CANON = ("PageSize/Media Size: 3.5x5 4x6 4x6.Borderless 55x91mm 89x89mm 5x7 8x10 *A4 A4.Borderless "
+         "A5 B5 Env10 EnvDL Letter Legal\n")                   # driverless: Standard A4
+ZEBRA = ("PageSize/Media Size: A4 A5 A5Rotated w90h18 w162h90 w216h360 *w288h360 w288h432 "
+         "w576h468\n")                                          # sample.drv zebra.ppd
+PTOUCH_QL = "PageSize/Media Size: 12mm 29mm 62mm 17x54mm 29x90mm 62x29mm 62x100mm *Custom\n"
+GENERIC = "PageSize/Media Size: *Letter Legal Executive Tabloid A3 A4 A5 B5 EnvDL\n"
+
+
+@pytest.mark.parametrize("default, office", [
+    ("A4", True), ("A4.Borderless", True), ("Letter", True), ("A5", True), ("B5", True),
+    ("iso_a4_210x297mm", True), ("na_letter_8.5x11in", True), ("Legal", True), ("Executive", True),
+    ("w288h360", False), ("Custom", False), ("62mm", False), ("tz-24", False), ("w167h288", False),
+    ("A6", False), ("4x6", False), ("A40", False), ("", None)])
+def test_office_printers_are_recognized_by_their_default_paper(default, office):
+    assert cups.is_office(default) is office
+
+
+@pytest.mark.parametrize("options, office", [(CANON, True), (ZEBRA, False), (PTOUCH_QL, False),
+                                             (GENERIC, True), ("Resolution/Output: *300dpi\n", None)])
+def test_queues_know_office_printers_by_their_default(fake, options, office):
+    _, outputs, _ = fake
+    outputs["lpoptions Buero"] = options
+    assert cups.queues()[1].office is office
+
+
+@pytest.mark.parametrize("default, office", [("A4", True), ("w288h360", False), ("Custom", False)])
+def test_the_ppd_is_read_first(fake, default, office):
+    calls, _, ppd_dir = fake
+    (ppd_dir / "Buero.ppd").write_text(f'*PPD-Adobe: "4.3"\n*DefaultPageSize: {default}\n'
+                                       '*PageSize A4/A4: "<</PageSize[595 842]>>setpagedevice"\n')
+    assert cups.queues()[1].office is office
+    assert ("lpoptions", "-p", "Buero", "-l") not in calls
+
+
+def test_silent_queue_is_unknown(fake):
+    _, outputs, _ = fake
+    outputs["lpoptions QL600"] = cups.CupsError("CUPS antwortet nicht (lpoptions)")
+    assert [q.office for q in cups.queues()] == [False, False, None]   # keine Antwort: angezeigt
+
+
+def test_office_check_is_remembered(fake, monkeypatch):
+    calls, outputs, _ = fake
+    outputs["lpoptions Buero"] = GENERIC
+    cups.queues()
+    cups.queues(max_age=0)                             # Liste neu, Einordnung gemerkt
+    assert sum(c[0] == "lpoptions" for c in calls) == 3
+    monkeypatch.setattr(cups, "INFO_MAX_AGE_S", 0)
+    cups.queues(max_age=0)                             # zu alt: neu gefragt
+    assert sum(c[0] == "lpoptions" for c in calls) == 6
+
+
+def test_silent_queue_is_asked_again_only_after_a_while(fake, monkeypatch):
+    calls, outputs, _ = fake
+    outputs["lpoptions QL600"] = cups.CupsError("CUPS antwortet nicht (lpoptions)")
+    cups.queues()
+    cups.queues(max_age=0)
+    assert sum(c[:3] == ("lpoptions", "-p", "QL600") for c in calls) == 1
+    monkeypatch.setattr(cups, "FAILED_MAX_AGE_S", 0)
+    cups.queues(max_age=0)
+    assert sum(c[:3] == ("lpoptions", "-p", "QL600") for c in calls) == 2
+
+
+def test_slow_queues_do_not_hold_up_the_list(fake, monkeypatch):
+    """lpoptions je Warteschlange parallel, zusammen höchstens TIMEOUT_S; wer nicht rechtzeitig
+    antwortet, ist unbekannt (angezeigt) – die Antwort zählt, sobald sie da ist."""
+    import threading
+    import time
+    _, outputs, _ = fake
+    release = threading.Event()
+    real = cups._run
+
+    def run(*args, **kw):
+        if args[0] == "lpoptions":
+            release.wait(5)                            # alle hängen
+        return real(*args, **kw)
+    monkeypatch.setattr(cups, "_run", run)
+    monkeypatch.setattr(cups, "TIMEOUT_S", 0.3)
+    outputs["lpoptions Buero"] = GENERIC
+    start = time.monotonic()
+    assert [q.office for q in cups.queues()] == [None, None, None]
+    assert time.monotonic() - start < 1.5              # nicht 3 × nacheinander gewartet
+    release.set()
+    for _ in range(50):                                # späte Antworten werden gemerkt
+        if all(cups._office_cache.get(n, (0, None, False))[2]
+               for n in ("Dymo_LabelWriter_450", "Buero", "QL600")):
+            break
+        time.sleep(0.05)
+    assert [q.office for q in cups.queues(max_age=0)] == [False, True, False]
+
+
+def test_without_classify_nothing_is_asked(fake):
+    calls, _, _ = fake
+    assert [q.office for q in cups.queues(wait=True, classify=False)] == [None, None, None]
+    assert not any(c[0] == "lpoptions" for c in calls)
+
+
+def test_office_printers_are_hidden_unless_wanted_or_chosen(fake):
+    calls, outputs, _ = fake
+    outputs["lpoptions Buero"] = CANON
+    hidden = []
+    assert [p.uri for p in printers.cups_printers([], hidden=hidden)] == [
+        "cups:Dymo_LabelWriter_450", "cups:QL600"]
+    assert hidden == ["Buero"]
+    assert "cups:Buero" in [p.uri for p in printers.cups_printers([], keep="cups:Buero")]
+    cups.forget()
+    calls.clear()
+    assert "cups:Buero" in [p.uri for p in printers.cups_printers([], wait=True, office=True)]
+    assert not any(c[0] == "lpoptions" for c in calls)  # alle zeigen: keine Einordnung nötig
+
+
 # --- Drucker und Modelle -----------------------------------------------------------------------
 def test_queues_are_printers_without_doubling_the_brother(fake):
     direct = [printers.Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1", "usb")]
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 2407f62..b7239d3 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -309,6 +309,16 @@ def test_cups_printer_and_its_options_are_kept(tmp_path):
     assert s.printer_options == {"cups:Dymo": {"CutMedia": "EndOfJob"}} and s.warnings == []
 
 
+def test_show_all_cups_printers(tmp_path):
+    path = tmp_path / "settings.json"
+    assert Settings().cups_all is False                # Bürodrucker standardmäßig ausgeblendet
+    save_settings(Settings(cups_all=True), path)
+    assert load_settings(path).cups_all is True
+    path.write_text(json.dumps({"cups_all": "ja"}))
+    s = load_settings(path)
+    assert s.cups_all is False and any("cups_all" in w for w in s.warnings)
+
+
 @pytest.mark.parametrize("bad", [[], {"cups:Dymo": "x"}, {"cups:Dymo": {"CutMedia": 3}},
                                  {"cups:Dymo": {"CutMedia": "Off -o x=y"}},
                                  {"cups:Dymo": {"": "x"}}])
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (Fälle in tests/test_cups.py, tests/test_cli.py, tests/test_settings.py, tests/gui/test_gui_cups.py) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 4cc5b64..bee73e7 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -127,9 +127,14 @@ src/labelwerk/
               SUPPORTED_MODELS (QL ohne PT), TESTED_MODELS, backend_for(uri) (… | cups | zpl), is_model (QL, cups:NAME,
               zpl:203/300/600), zebra_printers() (sysfs Vendor 0a5f, dpi aus der Kennung, sonst 203; source zebra),
               Netzwerkeintrag mit Modell zpl:… → zpl+tcp://, cups_printers(direct, keep, wait) (Brother-QL-Warteschlange
-              nicht doppelt, außer gewählt); choose automatisch nie CUPS
+              nicht doppelt, Bürodrucker nur mit office=True – Einstellung cups_all; eingeordnet nur ohne
+              office –, gewählte bleibt immer, hidden sammelt Ausgeblendete);
+              choose automatisch nie CUPS
   cups.py     CUPS ohne Qt: _run (lpstat/lpoptions/lp, Zeitlimit, LC_MESSAGES=C; Tests ersetzen _run, BACKGROUND aus),
-              queues() (Hintergrund-Thread, 30 s; wait=True für die CLI), queue_info(name) -> QueueInfo(media, dpi,
+              queues() (Hintergrund-Thread, 30 s; wait=True für die CLI; classify: Bürodrucker einordnen –
+              Queue.office nach der STANDARD-Papiergröße, is_office: A3–A5/B5/Letter/Legal … bzw. IPP-Namen;
+              Standard aus PPD *DefaultPageSize, sonst lpoptions „*“; je Warteschlange ein Thread, zusammen
+              höchstens TIMEOUT_S, 5 min gemerkt; ohne Antwort None = angezeigt, kurz gemerkt), queue_info(name) -> QueueInfo(media, dpi,
               cut_options, source ppd|options|list; 5 min gemerkt, Fehler nicht), PPD aus PPD_DIR, valid_name,
               print_images(name, images, w, h, dpi, options) -> Job (ein PDF, media=/PageSize=, print-scaling=none)
   zpl.py      Zebra ohne Qt: graphic(img) (^GFA, Zebra-ASCII-Kompression, „:“ = gleiche Zeile), build(images, mode T|C|P),
@@ -156,7 +161,8 @@ src/labelwerk/
               (Ersatz), `last_model` (zuletzt erkannt), `network_printers` ({name, host, model}; valid_host: IPv4/Name ohne
               Port/Schema/Steuerzeichen; Modell auch zpl:…), network_entries(settings); `printer_options` (Modell →
               Druck-Optionen: CUPS-Schnitt-Optionen, Zebra-Modus; je Eintrag geprüft, leerer Wert erlaubt), `zebra_dpi`
-              (0 = erkannt), `language` ("" = System); RESTART_KEYS (language, start_zoom, start_tool), started_values/
+              (0 = erkannt), `cups_all` (auch CUPS-Bürodrucker im Druckermenü/`labelwerk printers`; Dialog → Drucker),
+              `language` ("" = System); RESTART_KEYS (language, start_zoom, start_tool), started_values/
               restart_pending (wirksamer Vergleich mit dem Start), configured_language (vor allem anderen gelesen);
               load_settings(path, model=None): Etikett muss nur ein bekanntes Etikett sein (auch
               „BxHmm@dpi“; ob es zum Drucker passt, prüfen GUI und CLI)
@@ -289,7 +295,7 @@ src/labelwerk/
                     Tastenkürzel (Konflikte sperren Speichern); restart_hint neben SPEICHERN (Stand beim Start: started)
     theme/          QSS-Stylesheet (rawblock.qss)
     icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
-  cli.py      labelwerk labels | labelwerk media | labelwerk printers | labelwerk fonts | -m auto (Modell des Zieldruckers:
+  cli.py      labelwerk labels | labelwerk media | labelwerk printers [--all] (Bürodrucker; sonst Zeile „n ausgeblendet“) | labelwerk fonts | -m auto (Modell des Zieldruckers:
               -p bzw. gewählter/erster) | -l auto (Rolle des Zieldruckers per USB) | Etikett muss zum Modell passen | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
 ```
 Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `printers`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.
diff --git a/src/labelwerk/cli.py b/src/labelwerk/cli.py
index 957c9c1..c13fe9e 100644
--- a/src/labelwerk/cli.py
+++ b/src/labelwerk/cli.py
@@ -14,7 +14,7 @@ from . import printers
 from .detect import BUSY_MESSAGE, PRINTER_NOT_FOUND, brother_busy, find_brother_lp, find_brother_usb
 from .files import crop, fit_to_label, load_file
 from .fonts import DEFAULT_FAMILY, families
-from .i18n import NP_, N_, _, pgettext
+from .i18n import NP_, N_, _, ngettext, pgettext
 from .document import ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .labels import format_mm, get_label, labels_for_model
 from .media import MediaError, label_for_media, read_media
@@ -140,7 +140,9 @@ def _parser() -> argparse.ArgumentParser:
     _add_output_options(pf)
 
     sub.add_parser("media", help=_("query the roll loaded in the printer (prints nothing)"))
-    sub.add_parser("printers", help=_("list found printers and supported models"))
+    pp = sub.add_parser("printers", help=_("list found printers and supported models"))
+    pp.add_argument("--all", dest="show_all", action="store_true",
+                    help=_("also list office printers (CUPS queues with A4/Letter paper)"))
     fo = sub.add_parser("fonts", help=_("list installed font families with German characters"))
     fo.add_argument("--all", action="store_true",
                     help=_("all font families, also copies, symbol fonts and other scripts"))
@@ -179,9 +181,10 @@ def _target(args: argparse.Namespace, settings) -> printers.Printer | None:
     # CUPS nur fragen, wenn es darum geht (lpstat kann dauern)
     with_cups = (wanted.startswith("cups:") or backend == "cups"
                  or wanted == "auto" and settings.printer.startswith("cups:"))
-    found = _all_printers(settings, cups=with_cups)
-    if wanted != "auto":
-        return printers.printer_for(wanted, found)
+    if wanted != "auto":                            # angegeben: nichts einzuordnen
+        return printers.printer_for(wanted, _all_printers(settings, cups=with_cups, office=True))
+    args.hidden_office = []                         # ausgeblendete Bürodrucker (Meldung)
+    found = _all_printers(settings, cups=with_cups, hidden=args.hidden_office)
     if backend in ("network", "cups", "zebra"):
         found = [p for p in found if p.source == backend]
         if backend == "cups" and not settings.printer.startswith("cups:"):
@@ -191,11 +194,16 @@ def _target(args: argparse.Namespace, settings) -> printers.Printer | None:
     return printers.choose(found, settings.printer)
 
 
-def _all_printers(settings, cups: bool = True) -> list[printers.Printer]:
-    """Direkt per USB, eingetragene Netzwerkdrucker und (``cups``) Warteschlangen von CUPS."""
+def _all_printers(settings, cups: bool = True, office: bool | None = None,
+                  hidden: list[str] | None = None) -> list[printers.Printer]:
+    """Direkt per USB, eingetragene Netzwerkdrucker und (``cups``) Warteschlangen von CUPS;
+    Bürodrucker nur mit ``office`` (None = Einstellung ``cups_all``), ausgeblendete sammelt
+    ``hidden``."""
     direct = (printers.usb_printers() + printers.zebra_printers(dpi=settings.zebra_dpi)
               + printers.network_printers(network_entries(settings)))
-    return direct + (printers.cups_printers(direct, wait=True) if cups else [])
+    office = settings.cups_all if office is None else office
+    return direct + (printers.cups_printers(direct, keep=settings.printer, wait=True,
+                                            office=office, hidden=hidden) if cups else [])
 
 
 def _resolve_model(model: str, target: printers.Printer | None, settings) -> str:
@@ -257,6 +265,9 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
             busy = args.backend in (None, "linux_kernel") and brother_busy()
             print(_(BUSY_MESSAGE) if busy else _(_NOT_DETECTED[args.backend or "linux_kernel"])
                   .format(not_found=_(PRINTER_NOT_FOUND)), file=sys.stderr)
+            if args.backend == "cups" and getattr(args, "hidden_office", None):
+                print(_("Office printers hidden: {names} – print with -p cups:NAME").format(
+                    names=", ".join(args.hidden_office)), file=sys.stderr)
             return 2
 
     try:
@@ -275,10 +286,11 @@ def _send(img: Image.Image, args: argparse.Namespace) -> int:
     return 0 if ok else 1
 
 
-def _show_printers(model: str) -> int:
-    """Gefundene Drucker (USB, eingetragene Netzwerkdrucker, CUPS-Warteschlangen) und unterstützte
-    Modelle."""
-    found = _all_printers(load_settings())
+def _show_printers(model: str, show_all: bool = False) -> int:
+    """Gefundene Drucker (USB, eingetragene Netzwerkdrucker, CUPS-Warteschlangen – Bürodrucker nur
+    mit ``show_all`` bzw. Einstellung ``cups_all``) und unterstützte Modelle."""
+    hidden = []
+    found = _all_printers(load_settings(), office=True if show_all else None, hidden=hidden)
     for p in found:
         caps = printers.capabilities(p.model) if p.model else None
         state = (_("model not detected") if caps is None else
@@ -286,6 +298,11 @@ def _show_printers(model: str) -> int:
         print(f"{p.name:<28} {p.uri:<30} {state}")
     if not found:
         print(_("No printer found."))
+    if hidden:
+        print(ngettext("{count} office printer hidden – “labelwerk printers --all” shows it, "
+                       "print with -p cups:NAME",
+                       "{count} office printers hidden – “labelwerk printers --all” shows them, "
+                       "print with -p cups:NAME", len(hidden)).format(count=len(hidden)))
     print(_("Effective model: {model}").format(model=model))
     models = ", ".join(m if printers.capabilities(m).tested
                        else _("{model} (untested)").format(model=m)
@@ -406,7 +423,7 @@ def main(argv: list[str] | None = None) -> int:
     if args.cmd == "media":
         return _show_media(args.model, args.target)
     if args.cmd == "printers":
-        return _show_printers(args.model)
+        return _show_printers(args.model, args.show_all)
     if args.cmd == "fonts":
         print("\n".join(families(all=args.all)))
         return 0
diff --git a/src/labelwerk/cups.py b/src/labelwerk/cups.py
index 968d896..8957871 100644
--- a/src/labelwerk/cups.py
+++ b/src/labelwerk/cups.py
@@ -4,7 +4,8 @@ Befehle ``lpstat``, ``lpoptions`` und ``lp``.
 Etikettengrößen und Auflösung kommen aus dem Treiber (PPD: ``*PaperDimension``,
 ``*DefaultResolution``), sonst aus den Namen der Größen (``lpoptions -l``: „62x29mm“, „w288h432“
 in Punkt), sonst aus einer Liste je Hersteller (Dymo, Zebra). Schnitt-Optionen sind die
-Treiber-Optionen mit „Cut“ im Namen. Jeder Aufruf hat ein Zeitlimit, Meldungen kommen englisch
+Treiber-Optionen mit „Cut“ im Namen. Bürodrucker (Papiergrößen A4, Letter …) erkennt die Liste der
+Warteschlangen, damit das Druckermenü sie ausblenden kann. Jeder Aufruf hat ein Zeitlimit, Meldungen kommen englisch
 (``LC_MESSAGES=C``, Namen bleiben UTF-8); Fehler werden zur übersetzten ``CupsError``. Die Liste
 der Warteschlangen fragt ein Hintergrund-Thread ab – die Oberfläche wartet nie auf CUPS.
 """
@@ -37,6 +38,11 @@ _QUEUE_NAME = re.compile(r"[^\s/\\#'\"-][^\s/\\#'\"]{0,126}")
 # Schnitt-Option: „Cut…“ als Wort oder in CamelCase („DymoCutOptions“), „Schneiden“/„Schnitt…“ –
 # nicht „Execute“, nicht „Schnittstelle“
 _CUT = re.compile(r"(?:\b[Cc]ut|(?<=[a-z])Cut|\b[Ss]chn(?:itt|eid))(?!stelle)")
+# Papiergröße eines Bürodruckers (``PageSize``): A3–A5, B5, Letter, Legal, Executive, Tabloid/Ledger,
+# auch als IPP-Name („iso_a4_210x297mm“, „na_letter_8.5x11in“) und mit Zusatz („A4.Borderless“,
+# „A4Small“) – nicht A6 (Versandetikett) und nicht „A40“
+_OFFICE = re.compile(r"(?:iso_|na_|jis_)?(?:a[345]|b5|letter|legal|executive|tabloid|ledger)(?!\d)",
+                     re.I)
 PT_MM = 25.4 / 72
 # Rückfall: gängige Etiketten je Hersteller (Breite, Höhe in mm)
 MEDIA_LISTS = {
@@ -54,9 +60,11 @@ class CupsError(Exception):
 
 @dataclass(frozen=True)
 class Queue:
-    """Eine Warteschlange: Name und Geräte-URI (z. B. usb://DYMO/LabelWriter%20450)."""
+    """Eine Warteschlange: Name und Geräte-URI (z. B. usb://DYMO/LabelWriter%20450);
+    ``office``: Bürodrucker (Papiergrößen wie A4/Letter), None = unbekannt (CUPS ohne Antwort)."""
     name: str
     device: str = ""
+    office: bool | None = None
 
 
 @dataclass(frozen=True)
@@ -129,11 +137,13 @@ _lock = threading.Lock()
 _queues_cache: tuple[float | None, list[Queue]] = (None, [])
 _queues_thread: threading.Thread | None = None
 _info_cache: dict[str, tuple[float, QueueInfo]] = {}
+_office_cache: dict[str, tuple[float, bool | None, bool]] = {}   # Zeit, Bürodrucker, Antwort
 
 
-def read_queues() -> list[Queue]:
-    """Eingerichtete Warteschlangen (``lpstat -e``, Geräte aus ``lpstat -v``) – wartet auf CUPS;
-    ohne CUPS keine, ohne Geräteliste ohne Geräte."""
+def read_queues(classify: bool = True) -> list[Queue]:
+    """Eingerichtete Warteschlangen (``lpstat -e``, Geräte aus ``lpstat -v``; ``classify``:
+    Bürodrucker einordnen, ``office``) – wartet auf CUPS; ohne CUPS keine, ohne Geräteliste ohne
+    Geräte."""
     try:
         names = [n.strip() for n in _run("lpstat", "-e").splitlines() if valid_name(n.strip())]
     except CupsError:
@@ -146,16 +156,81 @@ def read_queues() -> list[Queue]:
                 devices[m[1]] = m[2]
     except CupsError:
         pass
-    return [Queue(n, devices.get(n, "")) for n in names]
+    office = _classify(names) if classify else {}
+    return [Queue(n, devices.get(n, ""), office.get(n)) for n in names]
 
 
-def queues(max_age: float = QUEUE_MAX_AGE_S, wait: bool = False) -> list[Queue]:
+def is_office(default: str) -> bool | None:
+    """Bürodrucker nach der Standard-Papiergröße des Treibers: A4, Letter … (auch wenn ein
+    Etikettendrucker A4 in der Liste hat, z. B. der Zebra-Treiber von CUPS, ist sein Standard ein
+    Etikett); ohne Standard unbekannt (None)."""
+    return bool(_OFFICE.match(default)) if default else None
+
+
+def _default_size(name: str) -> str:
+    """Standard-Papiergröße einer Warteschlange: aus der PPD (``*DefaultPageSize``), sonst
+    ``lpoptions`` (Wert mit „*“); ohne Antwort ``CupsError``."""
+    try:
+        if not valid_name(name):
+            raise OSError("invalid queue name")      # intern, nie angezeigt
+        m = re.search(r"^\*DefaultPageSize:\s*(\S+)", (PPD_DIR / f"{name}.ppd").read_text(
+            errors="replace"), re.M)
+        if m:
+            return m[1]
+    except OSError:                                  # nicht lesbar (Rechte) oder ohne PPD
+        pass
+    options = _options(name)
+    return options["PageSize"][2] if _choices(options, "PageSize") else ""
+
+
+def _classify(names: list[str]) -> dict[str, bool | None]:
+    """``is_office`` je Warteschlange; gemerkt (``INFO_MAX_AGE_S``, ohne Antwort
+    ``FAILED_MAX_AGE_S``). Ungemerkte fragt je ein Thread, alle zusammen höchstens ``TIMEOUT_S``
+    lang – wer bis dahin nicht antwortet, ist unbekannt (None); seine Antwort zählt beim
+    nächsten Lesen."""
+    now, result, ask = time.monotonic(), {}, []
+    with _lock:
+        for name in names:
+            stamp, office, answered = _office_cache.get(name, (None, None, False))
+            if stamp is not None and now - stamp < (INFO_MAX_AGE_S if answered
+                                                    else FAILED_MAX_AGE_S):
+                result[name] = office
+            else:
+                ask.append(name)
+    threads = [threading.Thread(target=_classify_one, args=(name,), daemon=True) for name in ask]
+    for thread in threads:
+        thread.start()
+    deadline = now + TIMEOUT_S
+    for thread in threads:
+        thread.join(max(0.0, deadline - time.monotonic()))
+    with _lock:
+        for name in ask:
+            stamp, office, answered = _office_cache.get(name, (None, None, False))
+            if stamp is None or stamp < now:          # nicht rechtzeitig: kurz als unbekannt
+                _office_cache[name] = (now, None, False)
+                office = None
+            result[name] = office
+    return result
+
+
+def _classify_one(name: str) -> None:
+    try:
+        office, answered = is_office(_default_size(name)), True
+    except CupsError:
+        office, answered = None, False
+    with _lock:
+        _office_cache[name] = (time.monotonic(), office, answered)
+
+
+def queues(max_age: float = QUEUE_MAX_AGE_S, wait: bool = False,
+           classify: bool = True) -> list[Queue]:
     """Warteschlangen, wie zuletzt gelesen (höchstens ``max_age`` Sekunden alt); ist die Liste
     älter, liest ein Hintergrund-Thread sie neu – ``queues()`` wartet nicht (die GUI fragt alle
-    2 s; der erste Aufruf liefert noch keine). ``wait``: neu lesen und warten (CLI)."""
+    2 s; der erste Aufruf liefert noch keine). ``wait``: neu lesen und warten (CLI);
+    ``classify``: Bürodrucker einordnen (der Hintergrund-Thread tut es immer)."""
     global _queues_cache, _queues_thread
     if wait or not BACKGROUND:
-        found = read_queues()
+        found = read_queues(classify)
         with _lock:
             _queues_cache = (time.monotonic(), found)
         return list(found)
@@ -181,6 +256,7 @@ def forget() -> None:
     with _lock:
         _queues_cache = (None, [])
         _info_cache.clear()
+        _office_cache.clear()
 
 
 def queue_info(name: str) -> QueueInfo:
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index e3ad36a..761df76 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -1495,7 +1495,8 @@ class MainWindow(QMainWindow):
         try:
             direct = (usb_printers() + zebra_printers(dpi=self.settings.zebra_dpi)
                       + network_printers(network_entries(self.settings)))
-            found = direct + cups_printers(direct, keep=self.settings.printer)
+            found = direct + cups_printers(direct, keep=self.settings.printer,
+                                           office=self.settings.cups_all)
             busy = not any(p.source == "usb" for p in found) and brother_busy()
         except OSError:
             found, busy = None, False
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 01cfd96..02cd5f8 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -160,6 +160,11 @@ class SettingsDialog(QDialog):
         self.zebra_dpi.setToolTip(_("Resolution of Zebra printers on USB, in case labelwerk does "
                                     "not detect it correctly (otherwise 203 dpi)"))
         form.addRow(_("Zebra resolution"), self.zebra_dpi)
+        self.cups_all = QCheckBox(_("Show all CUPS printers (office printers too)"))
+        self.cups_all.setToolTip(_("Off: queues with office paper (A4, Letter …) do not appear in "
+                                   "the printer menu"))
+        self.cups_all.setChecked(settings.cups_all)
+        form.addRow(self.cups_all)
         self.network = QTableWidget(0, 3)
         self.network.setHorizontalHeaderLabels([_("Name"), _("Address"), _("Model")])
         self.network.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
@@ -455,6 +460,7 @@ class SettingsDialog(QDialog):
             last_model=self._last_model,
             printer_options=dict(self._printer_options),
             zebra_dpi=self.zebra_dpi.currentData(),
+            cups_all=self.cups_all.isChecked(),
             language=self.language.currentData(),
             network_printers=self._network_values() or [],
             shortcuts={action_id: seq for action_id, seq in self._keys.items()
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index e1ea9cc..4a37cee 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -1519,6 +1519,15 @@ msgstr "Objekt ragt hinaus"
 msgid "Off: images that are too large are reduced – saves tape"
 msgstr "Aus: zu große Bilder werden verkleinert – spart Band"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Off: queues with office paper (A4, Letter …) do not appear in the printer menu"
+msgstr "Aus: Warteschlangen mit Büropapier (A4, Letter …) erscheinen nicht im Druckermenü"
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Office printers hidden: {names} – print with -p cups:NAME"
+msgstr "Bürodrucker ausgeblendet: {names} – drucken mit -p cups:NAME"
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "On round labels every border becomes a circle."
 msgstr "Auf runden Etiketten wird jeder Rahmen ein Kreis."
@@ -2170,6 +2179,10 @@ msgstr "Tastenkürzel"
 msgid "Shortcuts assigned twice – change one to save:"
 msgstr "Tastenkürzel doppelt belegt – zum Speichern eines ändern:"
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Show all CUPS printers (office printers too)"
+msgstr "Alle CUPS-Drucker zeigen (auch Bürodrucker)"
+
 #: src/labelwerk/gui/settings_dialog.py
 msgid "Show all fonts"
 msgstr "Alle Schriften zeigen"
@@ -2626,6 +2639,10 @@ msgstr "labelwerk-gui im Starter (Super-Taste) eintragen"
 msgid "all font families, also copies, symbol fonts and other scripts"
 msgstr "alle Schriftfamilien, auch Kopien, Symbolschriften und andere Schriftsysteme"
 
+#: src/labelwerk/cli.py
+msgid "also list office printers (CUPS queues with A4/Letter paper)"
+msgstr "auch Bürodrucker zeigen (CUPS-Warteschlangen mit A4/Letter-Papier)"
+
 #: src/labelwerk/cli.py
 msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
 msgstr "auto (Standard), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (Warteschlange, siehe 'labelwerk printers'), zpl+file:///dev/usb/lpN bzw. zpl+tcp://IP (Zebra, mit -m zpl:203/300/600)"
@@ -2859,6 +2876,13 @@ msgstr "{app}-Etikett"
 msgid "{checked} of {total} selected"
 msgstr "{checked} von {total} gewählt"
 
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "{count} office printer hidden – “labelwerk printers --all” shows it, print with -p cups:NAME"
+msgid_plural "{count} office printers hidden – “labelwerk printers --all” shows them, print with -p cups:NAME"
+msgstr[0] "{count} Bürodrucker ausgeblendet – „labelwerk printers --all“ zeigt ihn, drucken mit -p cups:NAME"
+msgstr[1] "{count} Bürodrucker ausgeblendet – „labelwerk printers --all“ zeigt sie, drucken mit -p cups:NAME"
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index 17e809a..1e012a4 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -1502,6 +1502,15 @@ msgstr ""
 msgid "Off: images that are too large are reduced – saves tape"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Off: queues with office paper (A4, Letter …) do not appear in the printer menu"
+msgstr ""
+
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "Office printers hidden: {names} – print with -p cups:NAME"
+msgstr ""
+
 #: src/labelwerk/gui/panels/paper.py
 msgid "On round labels every border becomes a circle."
 msgstr ""
@@ -2149,6 +2158,10 @@ msgstr ""
 msgid "Shortcuts assigned twice – change one to save:"
 msgstr ""
 
+#: src/labelwerk/gui/settings_dialog.py
+msgid "Show all CUPS printers (office printers too)"
+msgstr ""
+
 #: src/labelwerk/gui/settings_dialog.py
 msgid "Show all fonts"
 msgstr ""
@@ -2605,6 +2618,10 @@ msgstr ""
 msgid "all font families, also copies, symbol fonts and other scripts"
 msgstr ""
 
+#: src/labelwerk/cli.py
+msgid "also list office printers (CUPS queues with A4/Letter paper)"
+msgstr ""
+
 #: src/labelwerk/cli.py
 msgid "auto (default), file:///dev/usb/lpN, usb://0x04f9:0xPID, tcp://IP, cups:NAME (queue, see 'labelwerk printers'), zpl+file:///dev/usb/lpN or zpl+tcp://IP (Zebra, with -m zpl:203/300/600)"
 msgstr ""
@@ -2838,6 +2855,13 @@ msgstr ""
 msgid "{checked} of {total} selected"
 msgstr ""
 
+#: src/labelwerk/cli.py
+#, python-brace-format
+msgid "{count} office printer hidden – “labelwerk printers --all” shows it, print with -p cups:NAME"
+msgid_plural "{count} office printers hidden – “labelwerk printers --all” shows them, print with -p cups:NAME"
+msgstr[0] ""
+msgstr[1] ""
+
 #: src/labelwerk/gui/panels/paper.py
 #: src/labelwerk/gui/settings_dialog.py
 #, python-brace-format
diff --git a/src/labelwerk/printers.py b/src/labelwerk/printers.py
index aaa9ff7..6b43e56 100644
--- a/src/labelwerk/printers.py
+++ b/src/labelwerk/printers.py
@@ -254,15 +254,26 @@ def effective_model(printer: Printer | None, fallback: str = "", last: str = "")
     return DEFAULT_MODEL
 
 
-def cups_printers(direct: list[Printer], keep: str = "", wait: bool = False) -> list[Printer]:
+def cups_printers(direct: list[Printer], keep: str = "", wait: bool = False,
+                  office: bool = False, hidden: list[str] | None = None) -> list[Printer]:
     """Warteschlangen von CUPS als Drucker; ein Brother-QL bzw. Zebra, den labelwerk direkt per USB
-    findet, erscheint nicht noch einmal über seine Warteschlange – außer sie ist gewählt (``keep``).
-    ``wait``: auf CUPS warten (CLI), sonst die zuletzt gelesene Liste (``cups.queues``)."""
+    findet, erscheint nicht noch einmal über seine Warteschlange, Bürodrucker (A4/Letter) nur mit
+    ``office`` – außer die Warteschlange ist gewählt (``keep``). ``wait``: auf CUPS warten (CLI;
+    eingeordnet wird nur ohne ``office``), sonst die zuletzt gelesene Liste (``cups.queues``).
+    ``hidden``: sammelt die Namen ausgeblendeter Bürodrucker."""
     from . import cups
     doubles = tuple(prefix for prefix, here in (
         ("usb://brother/ql", any(p.source == "usb" and p.model in SUPPORTED_MODELS for p in direct)),
         ("usb://zebra", any(p.source == "zebra" and p.uri.startswith("zpl+file://")
                             for p in direct))) if here)
-    return [Printer(CUPS + q.name, CUPS + q.name, f"{q.name} · CUPS", "cups")
-            for q in cups.queues(wait=wait)
-            if CUPS + q.name == keep or not (doubles and q.device.lower().startswith(doubles))]
+    found = []
+    for q in cups.queues(wait=wait, classify=not office):
+        if CUPS + q.name != keep:
+            if doubles and q.device.lower().startswith(doubles):
+                continue
+            if q.office and not office:
+                if hidden is not None:
+                    hidden.append(q.name)
+                continue
+        found.append(Printer(CUPS + q.name, CUPS + q.name, f"{q.name} · CUPS", "cups"))
+    return found
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index a403e2b..37190b4 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -57,6 +57,7 @@ class Settings:
     network_printers: list[dict] = field(default_factory=list)   # {name, host, model}
     printer_options: dict[str, dict[str, str]] = field(default_factory=dict)  # Modell → Druck-Optionen
     zebra_dpi: int = 0                  # Auflösung der Zebras am USB, 0 = erkannt
+    cups_all: bool = False              # Druckermenü: auch CUPS-Bürodrucker (A4/Letter) zeigen
     language: str = ""                  # "" = Sprache des Systems, sonst "de", "en" …
     shortcuts: dict[str, str] = field(default_factory=dict)   # nur geänderte Kürzel, "" = keins
     warnings: list[str] = field(default_factory=list, compare=False, repr=False)
@@ -99,6 +100,7 @@ def _rules(model: str | None = None) -> dict:
         "language": lambda v: v == "" or v in i18n.available(),
         "zebra_dpi": lambda v: v in (0, *zpl.RESOLUTIONS) and not isinstance(v, bool),
         "printer_options": lambda v: isinstance(v, dict),
+        "cups_all": lambda v: isinstance(v, bool),
         "network_printers": lambda v: isinstance(v, list),
     }
 
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2665 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/cli.py src/labelwerk/cups.py src/labelwerk/gui/main_window.py src/labelwerk/gui/settings_dialog.py src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/printers.py src/labelwerk/settings.py tests/gui/test_gui_cups.py tests/test_cli.py tests/test_cups.py tests/test_settings.py
git commit -m "Bürodrucker ausblenden: CUPS-Warteschlangen mit Büro-Standardgröße nicht im Druckermenü, Einstellung „Alle CUPS-Drucker zeigen“, labelwerk printers --all

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Zusammenspiel, stilles Speichern, Doku

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-19-abnahme-korrekturen-design.md`
- Modify: `src/labelwerk/cups.py`
- Modify: `src/labelwerk/gui/file_session.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/paper.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/po/de.po`
- Modify: `src/labelwerk/po/labelwerk.pot`
- Modify: `src/labelwerk/settings.py`
- Modify: `tests/gui/test_gui_papier.py`
- Modify: `tests/gui/test_gui_settings.py`
- Modify: `tests/gui/test_gui_start_tool.py`
- Modify: `tests/test_cups.py`
- Modify: `tests/test_settings.py`

**Interfaces / Produces:** `settings.update_settings(path, base, **felder)`; `MainWindow._save_settings(*keys)`, `closeEvent` schreibt `last_tool` darüber; Rand-Hinweis mit Folgerung; Bürodrucker-Einordnung behält bekannten Wert; „Alle Schriften zeigen“ unter der Schriftart; Schriftliste beim Start einmal; README, CLAUDE.md, Spec.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_papier.py b/tests/gui/test_gui_papier.py
index 4c52097..60cec37 100644
--- a/tests/gui/test_gui_papier.py
+++ b/tests/gui/test_gui_papier.py
@@ -106,7 +106,8 @@ def test_margin_hint_when_margin_is_inside_the_printer_strip(window):
     paper = window.panel("paper")
     paper.margin.setValue(1.0)
     assert paper.margin_hint.isVisibleTo(paper)
-    assert paper.margin_hint.text() == "Längs zum Band lässt der Drucker 3,0 mm frei."
+    assert paper.margin_hint.text() == ("Längs zum Band lässt der Drucker 3,0 mm frei – ein kleinerer "
+                                        "Rand wirkt dort nicht.")
     # dezent wie eine Erläuterung (steht beim Standardrand immer da), nicht der Hinweis-Kasten
     assert paper.margin_hint.objectName() != "hint" and "color" in paper.margin_hint.styleSheet()
     paper.margin.setValue(3.0)                          # 35 Punkte: genau der Vorschub
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index 46c84b4..c35dd4b 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -108,6 +108,17 @@ def test_all_fonts_option_fills_the_list_at_once(qtbot, monkeypatch):
     assert not dlg.restart_needed()                              # wirkt ohne Neustart
 
 
+def test_all_fonts_option_sits_under_the_font(qtbot):
+    """„Alle Schriften zeigen“ steht direkt unter der Schriftart (Bereich NEUES ETIKETT)."""
+    from PySide6.QtWidgets import QFormLayout
+    dlg = SettingsDialog(Settings())
+    qtbot.addWidget(dlg)
+    form = dlg.font_family.parentWidget().layout()
+    assert isinstance(form, QFormLayout) and form is dlg.fonts_all.parentWidget().layout()
+    row, __ = form.getWidgetPosition(dlg.font_family)
+    assert form.getWidgetPosition(dlg.fonts_all)[0] == row + 1
+
+
 def test_saved_all_fonts_option_applies_to_text_panel(qtbot, monkeypatch):
     from labelwerk import fonts
     monkeypatch.setattr(fonts, "families",
@@ -467,3 +478,18 @@ def test_saved_image_defaults_apply_at_once(qtbot, monkeypatch):
     win.open_settings()
     panel = win.panel("image")
     assert panel.photo.isChecked() and panel.threshold.value() == 70
+
+
+def test_font_list_is_read_once_at_startup(qtbot, monkeypatch):
+    """Mit „Alle Schriften“ liest der Start nur die volle Liste (nicht erst die kurze)."""
+    from labelwerk import fonts
+    calls = []
+
+    def families(all=False):
+        calls.append(all)
+        return ["DejaVu Sans", "Zapf X"] if all else ["DejaVu Sans"]
+    monkeypatch.setattr(fonts, "families", families)
+    win = MainWindow(settings=Settings(check_media_on_start=False, fonts_all=True))
+    qtbot.addWidget(win)
+    assert calls == [True]
+    assert win.panel("text").family.count() == 2
diff --git a/tests/gui/test_gui_start_tool.py b/tests/gui/test_gui_start_tool.py
index 911671f..8e22523 100644
--- a/tests/gui/test_gui_start_tool.py
+++ b/tests/gui/test_gui_start_tool.py
@@ -46,7 +46,7 @@ def test_last_used_without_a_value_starts_with_paper(qtbot):
 def test_switching_tabs_remembers_the_last_tool_and_saves_it_on_close(qtbot, monkeypatch):
     from labelwerk.gui import main_window as mw
     saved = []
-    monkeypatch.setattr(mw, "save_settings", lambda settings, *a: saved.append(settings.last_tool))
+    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: saved.append(f["last_tool"]))
     win = _window(qtbot)
     win.tool_actions["series"].trigger()
     assert win.settings.last_tool == "series"
@@ -60,7 +60,7 @@ def test_switching_tabs_remembers_the_last_tool_and_saves_it_on_close(qtbot, mon
 def test_last_tool_is_not_saved_on_close_when_unchanged(qtbot, monkeypatch):
     from labelwerk.gui import main_window as mw
     saved = []
-    monkeypatch.setattr(mw, "save_settings", lambda settings, *a: saved.append(settings.last_tool))
+    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: saved.append(f["last_tool"]))
     win = _window(qtbot, start_tool="last", last_tool="image")
     win.tool_actions["text"].trigger()
     win.tool_actions["image"].trigger()                               # wieder wie beim Start
@@ -79,9 +79,9 @@ def test_last_tool_reaches_the_file_on_close(qtbot):
 def test_save_error_on_close_is_ignored(qtbot, monkeypatch):
     from labelwerk.gui import main_window as mw
 
-    def fail(*args):
+    def fail(*args, **fields):
         raise OSError("Datenträger voll")
-    monkeypatch.setattr(mw, "save_settings", fail)
+    monkeypatch.setattr(mw, "update_settings", fail)
     win = _window(qtbot)
     win.tool_actions["layout"].trigger()
     win.close()                                                       # kein Absturz
@@ -91,7 +91,7 @@ def test_save_error_on_close_is_ignored(qtbot, monkeypatch):
 def test_close_cancelled_saves_nothing(qtbot, monkeypatch):
     from labelwerk.gui import main_window as mw
     saved = []
-    monkeypatch.setattr(mw, "save_settings", lambda settings, *a: saved.append(settings.last_tool))
+    monkeypatch.setattr(mw, "update_settings", lambda *a, **f: saved.append(f["last_tool"]))
     win = _window(qtbot)
     win.show()
     win.tool_actions["layout"].trigger()
@@ -132,3 +132,26 @@ def test_settings_dialog_keeps_the_last_tool(qtbot, monkeypatch):
     monkeypatch.setattr(mw, "SettingsDialog", Dialog)
     win.open_settings()
     assert win.settings.last_tool == "text"
+
+
+def test_last_tool_on_close_keeps_settings_saved_by_another_instance(qtbot):
+    """Zweite Instanz (Doppelklick auf eine Datei) ändert das Design und speichert; schließt
+    danach die erste, bleibt das Design – nur der Reiter kommt dazu."""
+    from labelwerk.settings import save_settings
+    save_settings(Settings(theme="rawblock"))
+    win = _window(qtbot, theme="rawblock")
+    win.tool_actions["layout"].trigger()
+    save_settings(Settings(theme="classic"))                       # zweite Instanz
+    win.close()
+    s = load_settings()
+    assert (s.theme, s.last_tool) == ("classic", "layout")
+
+
+def test_silent_saves_keep_settings_saved_by_another_instance(qtbot, tmp_path):
+    """Stilles Speichern (Zuletzt geöffnet, Drucker gewählt) schreibt nur sein Feld."""
+    from labelwerk.settings import save_settings
+    win = _window(qtbot, theme="rawblock")
+    save_settings(Settings(theme="classic"))                       # zweite Instanz
+    win.choose_printer("tcp://192.0.2.1")
+    s = load_settings()
+    assert (s.theme, s.printer) == ("classic", "tcp://192.0.2.1")
diff --git a/tests/test_cups.py b/tests/test_cups.py
index 88e9fa7..f3c1532 100644
--- a/tests/test_cups.py
+++ b/tests/test_cups.py
@@ -270,6 +270,47 @@ def test_silent_queue_is_asked_again_only_after_a_while(fake, monkeypatch):
     assert sum(c[:3] == ("lpoptions", "-p", "QL600") for c in calls) == 2
 
 
+def test_known_office_printer_stays_hidden_when_cups_is_slow_later(fake, monkeypatch):
+    """Nach 5 Minuten neu gefragt, antwortet CUPS nicht (Zeitlimit oder Fehler): der bekannte
+    Wert bleibt (sonst tauchte der Bürodrucker kurz im Menü auf); erst kurz danach neu fragen."""
+    import threading
+    calls, outputs, _ = fake
+    outputs["lpoptions Buero"] = GENERIC
+    assert cups.queues()[1].office is True
+    monkeypatch.setattr(cups, "INFO_MAX_AGE_S", 0)
+    outputs["lpoptions Buero"] = cups.CupsError("CUPS antwortet nicht (lpoptions)")
+    assert cups.queues(max_age=0)[1].office is True              # Fehler: bekannt bleibt
+    release = threading.Event()
+    real = cups._run
+
+    def run(*args, **kw):
+        if args[0] == "lpoptions":
+            release.wait(5)                                     # hängt
+        return real(*args, **kw)
+    monkeypatch.setattr(cups, "_run", run)
+    monkeypatch.setattr(cups, "TIMEOUT_S", 0.2)
+    monkeypatch.setattr(cups, "INFO_MAX_AGE_S", 300)
+    monkeypatch.setattr(cups, "FAILED_MAX_AGE_S", 0)
+    assert cups.queues(max_age=0)[1].office is True              # Zeitlimit: bekannt bleibt
+    release.set()
+
+
+def test_known_value_is_asked_again_soon_after_a_failed_answer(fake, monkeypatch):
+    calls, outputs, _ = fake
+    outputs["lpoptions Buero"] = GENERIC
+    cups.queues()
+    monkeypatch.setattr(cups, "INFO_MAX_AGE_S", 0)
+    outputs["lpoptions Buero"] = cups.CupsError("CUPS antwortet nicht (lpoptions)")
+    cups.queues(max_age=0)
+    asked = sum(c[:3] == ("lpoptions", "-p", "Buero") for c in calls)
+    monkeypatch.setattr(cups, "INFO_MAX_AGE_S", 300)            # sonst fünf Minuten gemerkt …
+    cups.queues(max_age=0)
+    assert sum(c[:3] == ("lpoptions", "-p", "Buero") for c in calls) == asked   # … kurz: gemerkt
+    monkeypatch.setattr(cups, "FAILED_MAX_AGE_S", 0)
+    outputs["lpoptions Buero"] = PTOUCH_QL
+    assert cups.queues(max_age=0)[1].office is False             # danach wieder gefragt
+
+
 def test_slow_queues_do_not_hold_up_the_list(fake, monkeypatch):
     """lpoptions je Warteschlange parallel, zusammen höchstens TIMEOUT_S; wer nicht rechtzeitig
     antwortet, ist unbekannt (angezeigt) – die Antwort zählt, sobald sie da ist."""
@@ -291,7 +332,7 @@ def test_slow_queues_do_not_hold_up_the_list(fake, monkeypatch):
     assert time.monotonic() - start < 1.5              # nicht 3 × nacheinander gewartet
     release.set()
     for _ in range(50):                                # späte Antworten werden gemerkt
-        if all(cups._office_cache.get(n, (0, None, False))[2]
+        if all(cups._office_cache.get(n, (0, None, False, False))[2]
                for n in ("Dymo_LabelWriter_450", "Buero", "QL600")):
             break
         time.sleep(0.05)
diff --git a/tests/test_settings.py b/tests/test_settings.py
index b7239d3..e8bab34 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -426,3 +426,53 @@ def test_start_tool_needs_a_restart():
     language = started["language"]
     assert not restart_pending(language, 200, "paper", started)
     assert restart_pending(language, 200, "last", started)
+
+
+# --- stilles Speichern einzelner Felder ------------------------------------------------
+def test_update_settings_keeps_what_another_instance_saved(tmp_path):
+    """Instanz A merkt sich still den Reiter; Instanz B hat inzwischen das Design gespeichert –
+    A schreibt nur ihr Feld und lässt B's Änderung stehen."""
+    from labelwerk.settings import update_settings
+    path = tmp_path / "s.json"
+    save_settings(Settings(theme="rawblock"), path)
+    a = load_settings(path)                                    # Instanz A startet
+    save_settings(Settings(theme="classic"), path)              # Instanz B speichert
+    a.last_tool = "series"
+    update_settings(path, last_tool=a.last_tool)
+    s = load_settings(path)
+    assert (s.theme, s.last_tool) == ("classic", "series")
+
+
+def test_update_settings_keeps_unknown_and_invalid_entries(tmp_path):
+    """Felder einer neueren Version oder ungültige Werte bleiben in der Datei, wie sie sind."""
+    from labelwerk.settings import update_settings
+    path = tmp_path / "s.json"
+    path.write_text(json.dumps({"theme": "classic", "neu": [1, 2], "start_zoom": 9999}))
+    update_settings(path, recent_files=["/a.labelwerk"])
+    raw = json.loads(path.read_text())
+    assert raw == {"theme": "classic", "neu": [1, 2], "start_zoom": 9999,
+                   "recent_files": ["/a.labelwerk"]}
+
+
+def test_update_settings_without_file_writes_base(tmp_path):
+    from labelwerk.settings import update_settings
+    path = tmp_path / "neu" / "s.json"
+    update_settings(path, base=Settings(theme="classic"), last_tool="text")
+    s = load_settings(path)
+    assert (s.theme, s.last_tool) == ("classic", "text")
+
+
+def test_update_settings_with_unreadable_file_writes_base(tmp_path):
+    """Kaputte Datei: nichts zum Zusammenführen – der Stand im Speicher (``base``) gilt."""
+    from labelwerk.settings import update_settings
+    path = tmp_path / "s.json"
+    path.write_text("{kaputt")
+    update_settings(path, base=Settings(theme="classic"), last_tool="text")
+    s = load_settings(path)
+    assert (s.theme, s.last_tool, s.warnings) == ("classic", "text", [])
+
+
+def test_update_settings_rejects_unknown_fields(tmp_path):
+    from labelwerk.settings import update_settings
+    with pytest.raises(KeyError):
+        update_settings(tmp_path / "s.json", gibtsnicht=1)
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (Fälle in tests/test_settings.py, tests/test_cups.py, tests/gui/test_gui_start_tool.py, tests/gui/test_gui_settings.py, tests/gui/test_gui_papier.py) schlagen fehl, alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index bee73e7..17a0f17 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -52,7 +52,16 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
   Excel-Zahlen im Etikett nach der Region des Systems; `{Nummer}`/`{Number}` und „Spalte n“/„Column n“ in
   jeder Sprache; Symbole mit deutschen und englischen Namen (Suche in beiden); Layout-Test je Sprache.
 - Einstellungen: Reiter beim Start (fest oder zuletzt benutzter), Standard für neue Bilder (Strich/Foto, Schwelle).
-- 2536 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Schriftliste (Abnahme-Korrekturen): nur Schriften mit deutschen Zeichen, ohne Kopien (Powerline/Nerd Font),
+  Symbol-/Farbschriften und CJK-Regionsvarianten, jede in ihrer Schrift (FontCombo statt QFontComboBox, keine
+  Qt-Sammelnamen wie „Sans Serif“); Einstellung „Alle Schriften zeigen“ (`fonts_all`, sofort), CLI `fonts --all`;
+  alte Qt-Namen „Name [Hersteller]“ werden zur installierten Familie.
+- Bürodrucker: CUPS-Warteschlangen mit Büro-Standardpapier (A4, Letter …) sind im Druckermenü und in
+  `labelwerk printers` ausgeblendet (Einstellung „Alle CUPS-Drucker zeigen“ = `cups_all`, CLI `printers --all`,
+  gewählte bleibt sichtbar).
+- Stilles Speichern (Zuletzt geöffnet/verwendet, Favoriten, gewählter Drucker, letzter Reiter) schreibt nur sein
+  Feld (`settings.update_settings`) – was eine zweite Instanz gespeichert hat, bleibt.
+- 2676 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -126,7 +135,7 @@ src/labelwerk/
               zuletzt › QL-600), capabilities(model) (cutter, two_color, max_tape_mm 62/104, length_limits, tested),
               SUPPORTED_MODELS (QL ohne PT), TESTED_MODELS, backend_for(uri) (… | cups | zpl), is_model (QL, cups:NAME,
               zpl:203/300/600), zebra_printers() (sysfs Vendor 0a5f, dpi aus der Kennung, sonst 203; source zebra),
-              Netzwerkeintrag mit Modell zpl:… → zpl+tcp://, cups_printers(direct, keep, wait) (Brother-QL-Warteschlange
+              Netzwerkeintrag mit Modell zpl:… → zpl+tcp://, cups_printers(direct, keep, wait, office, hidden) (Brother-QL-Warteschlange
               nicht doppelt, Bürodrucker nur mit office=True – Einstellung cups_all; eingeordnet nur ohne
               office –, gewählte bleibt immer, hidden sammelt Ausgeblendete);
               choose automatisch nie CUPS
@@ -134,7 +143,7 @@ src/labelwerk/
               queues() (Hintergrund-Thread, 30 s; wait=True für die CLI; classify: Bürodrucker einordnen –
               Queue.office nach der STANDARD-Papiergröße, is_office: A3–A5/B5/Letter/Legal … bzw. IPP-Namen;
               Standard aus PPD *DefaultPageSize, sonst lpoptions „*“; je Warteschlange ein Thread, zusammen
-              höchstens TIMEOUT_S, 5 min gemerkt; ohne Antwort None = angezeigt, kurz gemerkt), queue_info(name) -> QueueInfo(media, dpi,
+              höchstens TIMEOUT_S, 5 min gemerkt; ohne Antwort: früherer Wert bleibt, sonst None = angezeigt, kurz gemerkt), queue_info(name) -> QueueInfo(media, dpi,
               cut_options, source ppd|options|list; 5 min gemerkt, Fehler nicht), PPD aus PPD_DIR, valid_name,
               print_images(name, images, w, h, dpi, options) -> Job (ein PDF, media=/PageSize=, print-scaling=none)
   zpl.py      Zebra ohne Qt: graphic(img) (^GFA, Zebra-ASCII-Kompression, „:“ = gleiche Zeile), build(images, mode T|C|P),
@@ -162,10 +171,12 @@ src/labelwerk/
               Port/Schema/Steuerzeichen; Modell auch zpl:…), network_entries(settings); `printer_options` (Modell →
               Druck-Optionen: CUPS-Schnitt-Optionen, Zebra-Modus; je Eintrag geprüft, leerer Wert erlaubt), `zebra_dpi`
               (0 = erkannt), `cups_all` (auch CUPS-Bürodrucker im Druckermenü/`labelwerk printers`; Dialog → Drucker),
-              `language` ("" = System); RESTART_KEYS (language, start_zoom, start_tool), started_values/
+              `fonts_all` (alle Schriften in den Auswahlen, sofort), `language` ("" = System); RESTART_KEYS (language, start_zoom, start_tool), started_values/
               restart_pending (wirksamer Vergleich mit dem Start), configured_language (vor allem anderen gelesen);
               load_settings(path, model=None): Etikett muss nur ein bekanntes Etikett sein (auch
-              „BxHmm@dpi“; ob es zum Drucker passt, prüfen GUI und CLI)
+              „BxHmm@dpi“; ob es zum Drucker passt, prüfen GUI und CLI); save_settings schreibt alles,
+              update_settings(path, base, **felder) nur diese Felder in die neu gelesene Datei (Rest bleibt wie dort,
+              auch Unbekanntes; fehlt/kaputt: base) – stilles Speichern der GUI (MainWindow._save_settings(*keys))
   storage.py  Etiketten als Datei (*.labelwerk, JSON versioniert, Bilder Base64): to_dict/from_dict, save (atomar), load;
               Schemata SPAN/PARAGRAPH/TEXT/IMAGE/BARCODE/DOCUMENT (jedes Dataclass-Feld, Test hält gleich); Dateien sind fremde Eingabe:
               Prüfung je Feld nach Art, Wertebereich (endlich, Grenzen) und Struktur → StorageError (übersetzt, mit Dateiname),
@@ -291,11 +302,13 @@ src/labelwerk/
                     inzwischen gewechselten Druckers zählt nicht)
     settings_dialog.py Einstellungen: Reiter Allgemein (rollt; inkl. Design, sofort wirksam über app.apply_theme; Drucker:
                     Druckermodell als Ersatz, Zebra-Auflösung, Netzwerkdrucker-Tabelle mit Prüfung der Adresse und Modell
-                    Brother/Zebra; Etikett eines anderen Druckers bleibt; Ansicht: Start-Zoom, Design, Sprache) und
+                    Brother/Zebra, „Alle CUPS-Drucker zeigen“; Etikett eines anderen Druckers bleibt; Neues Etikett: …,
+                    Schriftart (FontCombo) mit „Alle Schriften zeigen“ darunter (sofort); Bilder einfügen: Zuschnitt, Drehen,
+                    Umwandlung Strich/Foto, Schwelle; Ansicht: Start-Zoom, Reiter beim Start, Design, Sprache) und
                     Tastenkürzel (Konflikte sperren Speichern); restart_hint neben SPEICHERN (Stand beim Start: started)
     theme/          QSS-Stylesheet (rawblock.qss)
     icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
-  cli.py      labelwerk labels | labelwerk media | labelwerk printers [--all] (Bürodrucker; sonst Zeile „n ausgeblendet“) | labelwerk fonts | -m auto (Modell des Zieldruckers:
+  cli.py      labelwerk labels | labelwerk media | labelwerk printers [--all] (Bürodrucker; sonst Zeile „n ausgeblendet“) | labelwerk fonts [--all] | -m auto (Modell des Zieldruckers:
               -p bzw. gewählter/erster) | -l auto (Rolle des Zieldruckers per USB) | Etikett muss zum Modell passen | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
 ```
 Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `printers`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.
diff --git a/README.md b/README.md
index dbb880a..a35e860 100644
--- a/README.md
+++ b/README.md
@@ -25,7 +25,9 @@ ausprobiert, freue ich mich über eine Rückmeldung (Issue mit Modell, Rolle und
 **Andere Hersteller:** Zebra-Drucker am USB erkennt labelwerk selbst (Auflösung aus der Kennung des
 Druckers, sonst 203 dpi); Netzwerk-Zebras trägst du in den Einstellungen mit Modell „Zebra (ZPL)“ und
 Auflösung ein. Drucker, die in der Druckerverwaltung des Systems (CUPS) eingerichtet sind, stehen im
-Druckermenü als „Name · CUPS“ – sie werden nie automatisch gewählt (darunter sind oft Bürodrucker).
+Druckermenü als „Name · CUPS“ – sie werden nie automatisch gewählt. Bürodrucker (Standardpapier A4,
+Letter …) blendet labelwerk dort aus; Einstellungen → Drucker → „Alle CUPS-Drucker zeigen“ holt sie zurück
+(ein gewählter bleibt immer sichtbar).
 Gedruckt wird in der echten Auflösung des Druckers, damit Barcodes scharf bleiben. Schneiden stellst du
 im Reiter SERIE ein: bei CUPS die Schnitt-Optionen des Treibers, bei Zebra Abreißen/Schneiden/Ablösen.
 Grenzen: Der Treiber kann einen unbedruckbaren Rand haben (Rand im Reiter PAPIER vergrößern), „Medium
@@ -64,8 +66,10 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62x29      # drucken (Drucker wird autom
 labelwerk print-file internetmarke.pdf -l 62       # PDF/PNG/JPG 1:1 drucken
 labelwerk media                                            # eingelegte Rolle anzeigen (druckt nichts)
 labelwerk printers                                         # gefundene Drucker und unterstützte Modelle
+labelwerk printers --all                                   # auch CUPS-Bürodrucker
 labelwerk print "Regal 4" -l auto                          # Etikett nach der eingelegten Rolle
-labelwerk fonts                                            # installierte Schriften
+labelwerk fonts                                            # Schriften mit deutschen Zeichen
+labelwerk fonts --all                                      # alle (auch Kopien, Symbolschriften)
 labelwerk print "Max Mustermann\nMusterstr. 5" --align left --font-family "Liberation Sans" -s 14
 labelwerk print "Max Mustermann\nMusterstr. 5\n12345 Musterstadt" --orientation horizontal -s 19
 ```
@@ -84,9 +88,9 @@ labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entf
 
 Aufbau wie im P-touch Editor: Werkzeugleiste (Datei, Papier, Text, Bild, Barcode, Layout, Serie), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Unten links steht der Drucker: ein Klick wählt einen anderen (bei mehreren) oder trägt einen Netzwerkdrucker ein; während eine Serie vorbereitet oder gedruckt wird, bricht ABBRECHEN sie ab (beim Drucken nach dem laufenden Teil, bis zu 10 Etiketten). Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.
 
-Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). Der Rand zählt ab Papierkante: Die Streifen, die der Drucker ohnehin freilässt (quer ~1,5 mm, längs zum Endlosband ~3 mm), zählen mit und sind auf der Arbeitsfläche hellgrau. Die Länge eines Endlosband-Etiketts ist das abgeschnittene Stück (Dateien älterer Versionen drucken dadurch ~6 mm kürzer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil); gespeichert in `~/.config/labelwerk/settings.json`.
+Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). Der Rand zählt ab Papierkante: Die Streifen, die der Drucker ohnehin freilässt (quer ~1,5 mm, längs zum Endlosband ~3 mm), zählen mit und sind auf der Arbeitsfläche hellgrau. Die Lineale zählen ab Papierkante, die Felder unter „Position“ ab dem bedruckbaren Bereich. Die Länge eines Endlosband-Etiketts ist das abgeschnittene Stück (Dateien älterer Versionen drucken dadurch ~6 mm kürzer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil), den Reiter beim Start (fest oder „Zuletzt benutzter“) und den Standard für neue Bilder (Strich/Foto, Schwelle); gespeichert in `~/.config/labelwerk/settings.json`.
 
-Text: Geschrieben wird direkt auf dem Etikett. Mit dem Knopf „A“ (Text anlegen, Taste T) und einem Klick entsteht ein Rahmen, in den man sofort tippt (linksbündig ab dem Klickpunkt); ein Doppelklick auf einen Text setzt die Schreibmarke an die Klickstelle (ein einfacher Klick wählt den Rahmen nur); bei gewähltem Rahmen startet **F2** oder **Enter** den Schreibmodus mit der Schreibmarke am Textende. Im Schreibmodus markiert Ziehen Text, Doppelklick ein Wort, Umschalt+Klick erweitert; Pfeiltasten, Pos1/Ende, Entf, Enter, Strg+A/C/X/V und Strg+Z wirken auf den Text. **Esc** oder ein Klick neben den Rahmen beendet den Schreibmodus – die ganze Bearbeitung ist dann ein Schritt für Rückgängig. Ohne feste Rahmengröße wächst der Rahmen beim Tippen an der Kante seiner Textposition (links, rechts, Mitte). Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition wirken zeichenweise wie im P-touch Editor: im Schreibmodus auf die Markierung bzw. das Weitertippen, sonst auf den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.
+Text: Geschrieben wird direkt auf dem Etikett. Mit dem Knopf „A“ (Text anlegen, Taste T) und einem Klick entsteht ein Rahmen, in den man sofort tippt (linksbündig ab dem Klickpunkt); ein Doppelklick auf einen Text setzt die Schreibmarke an die Klickstelle (ein einfacher Klick wählt den Rahmen nur); bei gewähltem Rahmen startet **F2** oder **Enter** den Schreibmodus mit der Schreibmarke am Textende. Im Schreibmodus markiert Ziehen Text, Doppelklick ein Wort, Umschalt+Klick erweitert; Pfeiltasten, Pos1/Ende, Entf, Enter, Strg+A/C/X/V und Strg+Z wirken auf den Text. **Esc** oder ein Klick neben den Rahmen beendet den Schreibmodus – die ganze Bearbeitung ist dann ein Schritt für Rückgängig. Ohne feste Rahmengröße wächst der Rahmen beim Tippen an der Kante seiner Textposition (links, rechts, Mitte). Die Schriftauswahl zeigt jede Schrift in ihrer Schrift und nur Schriften mit deutschen Zeichen, ohne Kopien und Symbolschriften (Einstellungen → „Alle Schriften zeigen“ zeigt alle); eine Schrift aus einer Datei, die dort fehlt, bleibt sichtbar. Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition wirken zeichenweise wie im P-touch Editor: im Schreibmodus auf die Markierung bzw. das Weitertippen, sonst auf den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.
 
 Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste (oder im Reiter „Text“ ohne Auswahl) und einem Klick aufs Etikett einen Rahmen anlegen – bleibt er leer, verschwindet er wieder, sobald man den Schreibmodus verlässt. Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus; Lage und Größe landen auf 0,1 mm wie in den Feldern), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.
 
diff --git a/docs/superpowers/specs/2026-10-19-abnahme-korrekturen-design.md b/docs/superpowers/specs/2026-10-19-abnahme-korrekturen-design.md
index a153473..13a6bbc 100644
--- a/docs/superpowers/specs/2026-10-19-abnahme-korrekturen-design.md
+++ b/docs/superpowers/specs/2026-10-19-abnahme-korrekturen-design.md
@@ -1,7 +1,7 @@
 # Korrekturen aus der Abnahme – Design
 
 Stand: 2026-10-19 · Status: Antworten des Nutzers 1a, 2a, 3b, 4b, 5b, 6a; Spec danach ohne eigene Freigabe
-geschrieben – zur Prüfung mit der Abnahme.
+geschrieben – zur Prüfung mit der Abnahme. Nach Prototyp und Reviews an die Umsetzung angeglichen.
 
 ## Anlass (Abnahme 2026-10-19)
 
@@ -42,34 +42,46 @@ Schriftvorschau-Gruppen/„Zuletzt verwendet“ (2b), `print-file`-Ränder (1:1-
   + Rand.
 - **Arbeitsfläche:** Endlosband zeigt das ganze Stück: Druckbild mittig, davor und dahinter der Streifen des Druckers
   (wie quer `total_width`); Länge ziehen, Größenangabe beim Ziehen und Feld „Länge“ meinen das Stück. Grenzen des
-  Felds/Ziehens = Modellgrenzen + 2 × feed_margin.
+  Felds/Ziehens = Modellgrenzen + 2 × feed_margin. Die Streifen, die der Drucker nicht bedruckt (längs und quer), sind
+  hellgrau (nur Anzeige, keine Klicks). Lineale zählen ab Papierkante, Positionsfelder ab dem Druckbild.
+- **Ausrichten am Etikett:** klemmt die automatische Länge an der Mindestlänge (Inhalt + Rand kürzer), steht die
+  Auswahl mittig im Bereich der Mindestlänge (`layout.align_objects(…, min_length=)`).
 - **Reiter PAPIER:** unter „Rand“ ein Hinweis, sichtbar bei Endlosband mit Rand unter dem Streifen des Druckers:
-  „Längs zum Band lässt der Drucker {mm} mm frei – weniger geht nicht.“ (Wert aus `feed_margin`, mit Komma je Sprache.)
-  Tooltip des Felds nennt beide Streifen.
+  „Längs zum Band lässt der Drucker {mm} mm frei – ein kleinerer Rand wirkt dort nicht.“ (Wert aus `feed_margin`, mit
+  Komma je Sprache; dezente graue Zeile, kein Warnstil – beim Standardrand 1 mm steht sie immer da.) Tooltip des Felds
+  nennt die echten Streifen des Etiketts.
 - **Dateien:** `length_mm` alter Dateien bedeutet jetzt das Stück (Druck ~6 mm kürzer als vorher, dafür wie
   eingestellt) – kein Umrechnen, Hinweis in der Doku.
 - **Tests:** Rand längs/quer in Druckpunkten (1 mm → 0 + Drucker, 5 mm → 5 mm − Streifen), feste Länge → Druckbild
-  um 2 × 35 Punkte kürzer, Grenzen; Golden-Referenzen neu (`tools/golden.py`), Arbeitsfläche (Stückhöhe, Ziehen,
-  Größenangabe), Hinweis im Panel.
+  um 2 × 35 Punkte kürzer, Grenzen; Golden-Referenzen bleiben (sie hashen feste Testbilder, nicht `render`),
+  Arbeitsfläche (Stückhöhe, Ziehen, Größenangabe, Streifen), Hinweis im Panel, Feld „Länge“ nach Etikettwechsel
+  (Grenzen vor dem Wert).
 
 ## 2 – Schriftliste
 
 - **Kern (`fonts.py`):** `families(all=False)`: kurze Liste = fontconfig `:lang=de` (deutsche Zeichen), ohne
-  Farbschriften (`color`), ohne Kopien (Name enthält „Powerline“), ohne reine Symbolschriften (Liste: D050000L,
+  Farbschriften (`color`), ohne Kopien (Name enthält „Powerline“ oder „Nerd Font“), ohne reine Symbolschriften (Liste: D050000L,
   Standard Symbols PS, Dingbats, Symbol, OpenSymbol, Webdings, Wingdings …), ohne regionale CJK-Varianten (Namen auf
   CJK/UKai/UMing mit Regionskürzel). `all=True`: alle Familien wie bisher. Ohne fontconfig: `[DEFAULT_FAMILY]`.
-- **Einstellung** `fonts_all: bool = False` – Einstellungen → Ansicht „Alle Schriften zeigen“, sofort wirksam.
+  Je Liste einmal gelesen (Cache unabhängig von der Aufrufform). `canonical(name)`: alte Qt-Namen „Name [Hersteller]“
+  aus Dateien/Einstellungen werden zur installierten Familie (Rendern, Hinweise, Auswahl); „Sans Serif“ & Co. bleiben
+  fremd (Hinweis wie bisher).
+- **Einstellung** `fonts_all: bool = False` – Einstellungen → Neues Etikett, direkt unter der Schriftart „Alle Schriften
+  zeigen“, sofort wirksam.
 - **Oberfläche:** eigene Auswahl `FontCombo` (QComboBox) statt QFontComboBox im Reiter TEXT und in den Einstellungen
   (Standardschrift): Einträge aus `fonts.families`, jeder in seiner Schrift dargestellt; eine Schrift aus Datei oder
   Einstellung, die nicht in der Liste steht, erscheint trotzdem (oben, gewählt) – nichts geht verloren. Keine
-  Qt-Sammelnamen mehr.
+  Qt-Sammelnamen mehr. Gemischte Schriften in der Markierung lassen das Feld leer (wie die Größe); eine Wahl setzt
+  dann alle. Das Text-Panel füllt die Liste nicht selbst (`MainWindow.apply_font_list`: beim Start und nach den
+  Einstellungen) – ein fc-list-Aufruf je Liste.
 - **CLI:** `labelwerk fonts` zeigt die kurze Liste, `labelwerk fonts --all` alle.
 - **Tests:** Filter mit gefälschter fc-list-Ausgabe, FontCombo (Signal, fremde Schrift bleibt), Einstellung.
 
 ## 3 – Reiter beim Start
 
-- **Einstellungen:** `start_tool: str = "paper"` (Werkzeug-Schlüssel oder „last“; Standard wie bisher Papier), `last_tool: str = ""` (still
-  gespeichert beim Reiterwechsel, wie `symbols_recent`). Dialog → Ansicht „Reiter beim Start“: Zuletzt benutzter,
+- **Einstellungen:** `start_tool: str = "paper"` (Werkzeug-Schlüssel oder „last“; Standard wie bisher Papier),
+  `last_tool: str = ""` (jeder sichtbare Reiterwechsel im Speicher; in die Datei beim Schließen des Fensters, nur
+  dieses Feld über `update_settings`; ungültig → "" ohne Hinweis). Dialog → Ansicht „Reiter beim Start“: Zuletzt benutzter,
   Datei, Papier, Text, Bild, Barcode, Layout, Serie. Teil von `RESTART_KEYS` (Hinweis neben SPEICHERN).
 - **Start:** gewählter Reiter; „Zuletzt benutzter“ ohne gültigen Wert → `START_TOOL` (Papier). Unbekannte Schlüssel
   in der Datei → Standard (wie andere Felder).
@@ -84,15 +96,26 @@ Schriftvorschau-Gruppen/„Zuletzt verwendet“ (2b), `print-file`-Ränder (1:1-
 
 ## 5 – Bürodrucker ausblenden
 
-- **Kern (`cups.py`):** beim Lesen der Warteschlangen (Hintergrund-Thread) je Warteschlange `lpoptions -p NAME -l`
-  (gemerkt `INFO_MAX_AGE_S`): **Bürodrucker**, wenn die Papiergrößen A3/A4/A5/B5, Letter, Legal, Executive, Tabloid
-  bzw. ihre IPP-Namen (`iso_a4_…`, `na_letter_…`) enthalten. Keine Antwort → unbekannt → angezeigt. `Queue.office`.
+- **Kern (`cups.py`):** beim Lesen der Warteschlangen (Hintergrund-Thread) je Warteschlange die **Standard**-Papiergröße
+  (PPD `*DefaultPageSize`, sonst `lpoptions -p NAME -l` Wert mit „*“): **Bürodrucker**, wenn sie A3/A4/A5/B5, Letter,
+  Legal, Executive, Tabloid/Ledger bzw. ihr IPP-Name ist (ein Zebra-Treiber mit A4 in der Liste, Standard Etikett,
+  bleibt Etikettendrucker). Abfragen parallel, zusammen höchstens `TIMEOUT_S`; gemerkt `INFO_MAX_AGE_S`. Keine Antwort →
+  früherer Wert bleibt, sonst unbekannt → angezeigt (kurz gemerkt). `Queue.office`; eingeordnet wird nur, wo gefiltert
+  wird (`classify`).
 - **`printers.cups_printers(…, office=False)`:** Bürodrucker nur mit `office=True`; die gewählte Warteschlange bleibt
   immer sichtbar (`keep`).
 - **Einstellung** `cups_all: bool = False` – Einstellungen → Drucker „Alle CUPS-Drucker zeigen (auch Bürodrucker)“.
-  GUI-Menü und `labelwerk printers` folgen ihr; `-p cups:NAME` geht immer.
+  GUI-Menü und `labelwerk printers` folgen ihr; `labelwerk printers --all` zeigt alle, sonst eine Zeile „n Bürodrucker
+  ausgeblendet“; `-b cups` ohne Etikett-Warteschlange nennt die ausgeblendeten; `-p cups:NAME` geht immer.
 - **Tests:** Erkennung mit gefälschtem `_run`, Liste mit/ohne Einstellung, gewählter Bürodrucker bleibt.
 
+## Stilles Speichern (aus dem Gesamtreview)
+
+`settings.update_settings(path, base, **felder)`: liest die Datei neu, setzt nur diese Felder, schreibt (Unbekanntes
+und Ungültiges bleibt wie dort; fehlt/kaputt: `base`). Die GUI speichert still nur die geänderten Felder (Zuletzt
+geöffnet/verwendet, Favoriten, Start-Favorit, gewählter Drucker, letztes Modell, Druck-Optionen, letzter Reiter) – was
+eine zweite Instanz gespeichert hat, bleibt. SPEICHERN im Einstellungsdialog schreibt weiter alles.
+
 ## Abschluss
 
 po/de.po ergänzt, Layout-Test hält die neuen Felder aus, CLAUDE.md/README aktualisiert, Python-3.10-Prüfung (Docker).
diff --git a/src/labelwerk/cups.py b/src/labelwerk/cups.py
index 8957871..7a133e1 100644
--- a/src/labelwerk/cups.py
+++ b/src/labelwerk/cups.py
@@ -137,7 +137,8 @@ _lock = threading.Lock()
 _queues_cache: tuple[float | None, list[Queue]] = (None, [])
 _queues_thread: threading.Thread | None = None
 _info_cache: dict[str, tuple[float, QueueInfo]] = {}
-_office_cache: dict[str, tuple[float, bool | None, bool]] = {}   # Zeit, Bürodrucker, Antwort
+# Zeit, Bürodrucker, je geantwortet, letzte Frage beantwortet
+_office_cache: dict[str, tuple[float, bool | None, bool, bool]] = {}
 
 
 def read_queues(classify: bool = True) -> list[Queue]:
@@ -191,8 +192,8 @@ def _classify(names: list[str]) -> dict[str, bool | None]:
     now, result, ask = time.monotonic(), {}, []
     with _lock:
         for name in names:
-            stamp, office, answered = _office_cache.get(name, (None, None, False))
-            if stamp is not None and now - stamp < (INFO_MAX_AGE_S if answered
+            stamp, office, __, fresh = _office_cache.get(name, (None, None, False, False))
+            if stamp is not None and now - stamp < (INFO_MAX_AGE_S if fresh
                                                     else FAILED_MAX_AGE_S):
                 result[name] = office
             else:
@@ -205,21 +206,31 @@ def _classify(names: list[str]) -> dict[str, bool | None]:
         thread.join(max(0.0, deadline - time.monotonic()))
     with _lock:
         for name in ask:
-            stamp, office, answered = _office_cache.get(name, (None, None, False))
-            if stamp is None or stamp < now:          # nicht rechtzeitig: kurz als unbekannt
-                _office_cache[name] = (now, None, False)
-                office = None
+            stamp, office, __, __ = _office_cache.get(name, (None, None, False, False))
+            if stamp is None or stamp < now:          # nicht rechtzeitig
+                office = _unanswered(name, now)
             result[name] = office
     return result
 
 
 def _classify_one(name: str) -> None:
     try:
-        office, answered = is_office(_default_size(name)), True
+        office = is_office(_default_size(name))
     except CupsError:
-        office, answered = None, False
+        with _lock:
+            _unanswered(name, time.monotonic())
+        return
     with _lock:
-        _office_cache[name] = (time.monotonic(), office, answered)
+        _office_cache[name] = (time.monotonic(), office, True, True)
+
+
+def _unanswered(name: str, now: float) -> bool | None:
+    """Keine Antwort (Zeitlimit, Fehler) – unter ``_lock``: ein früher bekannter Wert bleibt (ein
+    Bürodrucker taucht nicht kurz im Menü auf), gefragt wird wie ohne Antwort schon nach
+    ``FAILED_MAX_AGE_S`` wieder; ohne frühere Antwort unbekannt (None)."""
+    __, office, answered, __ = _office_cache.get(name, (None, None, False, False))
+    _office_cache[name] = (now, office if answered else None, answered, False)
+    return office if answered else None
 
 
 def queues(max_age: float = QUEUE_MAX_AGE_S, wait: bool = False,
diff --git a/src/labelwerk/gui/file_session.py b/src/labelwerk/gui/file_session.py
index 6efdf94..922a01c 100644
--- a/src/labelwerk/gui/file_session.py
+++ b/src/labelwerk/gui/file_session.py
@@ -279,14 +279,14 @@ class FileSession(QObject):
     def _remember(self, path: Path) -> None:
         settings = self.window.settings
         settings.recent_files = storage.add_recent_file(settings.recent_files, str(path))
-        self.window._save_settings()
+        self.window._save_settings("recent_files")
         self.refresh_lists()
 
     def open_recent(self, path: str) -> None:
         if not exists(path):
             settings = self.window.settings
             settings.recent_files = [p for p in settings.recent_files if p != path]
-            self.window._save_settings()
+            self.window._save_settings("recent_files")
             self.refresh_lists()
             self.window._set_result(
                 _("File not found: {path} – removed from the list").format(path=path), "error")
@@ -364,7 +364,7 @@ class FileSession(QObject):
             return
         if self.window.settings.start_favorite == favorite.name:
             self.window.settings.start_favorite = renamed.name
-            self.window._save_settings()
+            self.window._save_settings("start_favorite")
         self.refresh_lists()
 
     def remove_favorite(self, favorite: Favorite) -> None:
@@ -377,13 +377,13 @@ class FileSession(QObject):
             return
         if self.window.settings.start_favorite == favorite.name:
             self.window.settings.start_favorite = None
-            self.window._save_settings()
+            self.window._save_settings("start_favorite")
         self.refresh_lists()
 
     def toggle_start_favorite(self, favorite: Favorite) -> None:
         settings = self.window.settings
         settings.start_favorite = None if settings.start_favorite == favorite.name else favorite.name
-        self.window._save_settings()
+        self.window._save_settings("start_favorite")
         self.refresh_lists()
 
     def open_favorites_folder(self) -> None:
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 761df76..6506c47 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -37,7 +37,7 @@ from ..printer import DEFAULT_MODEL, cut_interval, to_print_mode
 from ..render import (Renderer, RenderedObject, font_warnings, render_document,
                       set_svg_rasterizer)
 from ..settings import (Settings, load_settings, network_entries, new_document, save_settings,
-                        started_values)
+                        started_values, update_settings)
 from ..shortcuts import effective, without_conflicts
 from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
@@ -1313,7 +1313,7 @@ class MainWindow(QMainWindow):
         # Größe passt schon quer zum Band – Drehen nach Einstellung gilt für Symbole nicht
         self._insert_images([obj], at, [] if crop is not None else [_(CROP_FAILED)], rotate=False)
         self.settings.symbols_recent = clipart.add_recent(self.settings.symbols_recent, symbol.id)
-        self._save_settings()
+        self._save_settings("symbols_recent")
         if self.symbol_window is not None:
             self.symbol_window.set_recent(self.settings.symbols_recent)
 
@@ -1362,13 +1362,18 @@ class MainWindow(QMainWindow):
 
     def _favorites_changed(self, favorites: list[str]) -> None:
         self.settings.symbols_favorites = list(favorites)
-        self._save_settings()
+        self._save_settings("symbols_favorites")
 
-    def _save_settings(self) -> None:
-        """Einstellungen still speichern (Zuletzt verwendet, Favoriten); Fehler in die Statusleiste."""
+    def _save_settings(self, *keys: str) -> None:
+        """Einstellungen still speichern (Zuletzt verwendet, Favoriten, Drucker …): nur die Felder
+        ``keys`` (``update_settings`` – was eine zweite Instanz gespeichert hat, bleibt); ohne
+        ``keys`` alles. Fehler in die Statusleiste."""
         try:
-            save_settings(self.settings)
-            self._stored_tool = self.settings.last_tool
+            if keys:
+                update_settings(base=self.settings, **{key: getattr(self.settings, key) for key in keys})
+            else:
+                save_settings(self.settings)
+                self._stored_tool = self.settings.last_tool
         except OSError as e:
             self._set_result(str(e), "error")
 
@@ -1526,7 +1531,7 @@ class MainWindow(QMainWindow):
         self.printer_status.setToolTip(tip or _("Choose printer"))
         if chosen is not None and chosen.model and chosen.model != self.settings.last_model:
             self.settings.last_model = chosen.model     # gilt beim nächsten Start ohne Drucker
-            self._save_settings()
+            self._save_settings("last_model")
         if not self._fixed_model:
             model = effective_model(chosen, self.settings.printer_model, self.settings.last_model)
             if model != self.model:
@@ -1573,7 +1578,7 @@ class MainWindow(QMainWindow):
     def choose_printer(self, uri: str) -> None:
         """Drucker wählen (URI; "" = automatisch) – gespeichert."""
         self.settings.printer = uri
-        self._save_settings()
+        self._save_settings("printer")
         self.refresh_printer()
 
     def set_model(self, model: str) -> None:
@@ -1607,7 +1612,7 @@ class MainWindow(QMainWindow):
         """Schnitt-Option bzw. Modus gewählt – gilt für diesen Drucker (Einstellungen)."""
         if self.model.startswith("cups:") or zpl.is_model(self.model):
             self.settings.printer_options.setdefault(self._options_key(), {})[key] = value
-            self._save_settings()
+            self._save_settings("printer_options")
 
     def _fit_label(self) -> None:
         """Passt das Etikett nicht zum Modell: ein neues, unberührtes Etikett nimmt ein passendes
@@ -1662,7 +1667,7 @@ class MainWindow(QMainWindow):
             self._end_shooting()
         if self.settings.last_tool != self._stored_tool:   # zuletzt benutzter Reiter, still
             try:
-                save_settings(self.settings)
+                update_settings(base=self.settings, last_tool=self.settings.last_tool)
                 self._stored_tool = self.settings.last_tool
             except OSError:
                 pass                                # beim Beenden: nichts mehr zu melden
diff --git a/src/labelwerk/gui/panels/paper.py b/src/labelwerk/gui/panels/paper.py
index ed171f4..1366e74 100644
--- a/src/labelwerk/gui/panels/paper.py
+++ b/src/labelwerk/gui/panels/paper.py
@@ -305,8 +305,8 @@ class PaperPanel(Panel):
         self._set_length_range()                       # Vorschub hängt am Etikett
         strip = label.feed_margin
         self.margin_hint.setVisible(endless and round(self.doc.margin_mm * label.dpi / 25.4) < strip)
-        self.margin_hint.setText(_("Along the tape the printer leaves {mm} mm free.").format(
-            mm=format_mm(strip, label.dpi)))
+        self.margin_hint.setText(_("Along the tape the printer leaves {mm} mm free – a smaller "
+                                   "margin has no effect there.").format(mm=format_mm(strip, label.dpi)))
         across = (label.total_width - label.width) // 2
         along = strip if endless else (label.total_height - label.height) // 2
         self.margin.setToolTip(
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index 5c2cdea..b1c087e 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -121,7 +121,7 @@ class TextPanel(Panel):
         self.edit.document().setDefaultTextOption(option)
 
         self.section(pgettext("text panel", "Font"))
-        self.family = FontCombo()        # kurze Liste; MainWindow.apply_font_list nach Einstellung
+        self.family = FontCombo([])      # gefüllt von MainWindow.apply_font_list (kurz oder alle)
         self.layout_.addWidget(self.family)
         row = QHBoxLayout()
         self.size = QComboBox()
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 02cd5f8..7a871ee 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -111,6 +111,13 @@ class SettingsDialog(QDialog):
         self._family_touched = False
         self.font_family.family_chosen.connect(self._family_changed)
         form.addRow(_("Font"), self.font_family)
+        self.fonts_all = QCheckBox(_("Show all fonts"))
+        self.fonts_all.setToolTip(_("Also copies, symbol fonts and fonts without German characters "
+                                    "– otherwise only fonts that can write German"))
+        self.fonts_all.setChecked(settings.fonts_all)
+        self.fonts_all.toggled.connect(
+            lambda on: self.font_family.set_families(fonts.families(all=on)))
+        form.addRow(self.fonts_all)
         self.start_favorite = QComboBox()
         self.start_favorite.addItem(_("Empty label"), None)
         for favorite in favorites.favorites():
@@ -213,13 +220,6 @@ class SettingsDialog(QDialog):
             self.language.addItem(i18n.NAMES.get(code, code), code)
         self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
         form.addRow(_("Language"), self.language)
-        self.fonts_all = QCheckBox(_("Show all fonts"))
-        self.fonts_all.setToolTip(_("Also copies, symbol fonts and fonts without German characters "
-                                    "– otherwise only fonts that can write German"))
-        self.fonts_all.setChecked(settings.fonts_all)
-        self.fonts_all.toggled.connect(
-            lambda on: self.font_family.set_families(fonts.families(all=on)))
-        form.addRow(self.fonts_all)
         # Einstellungen, die erst nach einem Neustart wirken: farbiger Hinweis neben SPEICHERN
         # (unten im Fenster – sichtbar in jedem Reiter), sobald eine davon geändert ist
         self._started = started if started is not None else started_values(settings)
diff --git a/src/labelwerk/po/de.po b/src/labelwerk/po/de.po
index 4a37cee..5a7d8be 100644
--- a/src/labelwerk/po/de.po
+++ b/src/labelwerk/po/de.po
@@ -152,8 +152,8 @@ msgstr "Alle"
 
 #: src/labelwerk/gui/panels/paper.py
 #, python-brace-format
-msgid "Along the tape the printer leaves {mm} mm free."
-msgstr "Längs zum Band lässt der Drucker {mm} mm frei."
+msgid "Along the tape the printer leaves {mm} mm free – a smaller margin has no effect there."
+msgstr "Längs zum Band lässt der Drucker {mm} mm frei – ein kleinerer Rand wirkt dort nicht."
 
 #: src/labelwerk/gui/settings_dialog.py
 msgid "Also copies, symbol fonts and fonts without German characters – otherwise only fonts that can write German"
diff --git a/src/labelwerk/po/labelwerk.pot b/src/labelwerk/po/labelwerk.pot
index 1e012a4..2b40165 100644
--- a/src/labelwerk/po/labelwerk.pot
+++ b/src/labelwerk/po/labelwerk.pot
@@ -151,7 +151,7 @@ msgstr ""
 
 #: src/labelwerk/gui/panels/paper.py
 #, python-brace-format
-msgid "Along the tape the printer leaves {mm} mm free."
+msgid "Along the tape the printer leaves {mm} mm free – a smaller margin has no effect there."
 msgstr ""
 
 #: src/labelwerk/gui/settings_dialog.py
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 37190b4..8554048 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -261,8 +261,31 @@ def _migrate_font_size(raw: dict, settings: Settings) -> None:
 
 
 def save_settings(settings: Settings, path: str | Path | None = None) -> Path:
+    return _write({key: getattr(settings, key) for key in _KEYS}, path)
+
+
+def update_settings(path: str | Path | None = None, base: Settings | None = None, **fields) -> Path:
+    """Nur ``fields`` in die Datei schreiben (stilles Speichern: Zuletzt verwendet, Favoriten,
+    gewählter Drucker …): die Datei wird neu gelesen, alles andere bleibt, wie es dort steht –
+    auch was eine zweite Instanz inzwischen gespeichert hat oder eine neuere Version kennt.
+    Fehlt die Datei oder ist sie nicht lesbar, gilt ``base`` (Stand im Speicher) bzw. der Standard."""
+    unknown = [key for key in fields if key not in _KEYS]
+    if unknown:
+        raise KeyError(unknown[0])
+    target = Path(path) if path else settings_path()
+    try:
+        data = json.loads(target.read_text(encoding="utf-8"))
+        if not isinstance(data, dict):
+            raise ValueError("not a JSON object")          # intern, nie angezeigt
+    except (OSError, ValueError):
+        source = base if base is not None else Settings()
+        data = {key: getattr(source, key) for key in _KEYS}
+    data.update(fields)
+    return _write(data, target)
+
+
+def _write(data: dict, path: str | Path | None) -> Path:
     path = Path(path) if path else settings_path()
-    data = {key: getattr(settings, key) for key in _KEYS}
     try:
         path.parent.mkdir(parents=True, exist_ok=True)
         # erst daneben schreiben, dann ersetzen: ein Absturz mitten im Schreiben lässt die alte
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `2676 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-19-abnahme-korrekturen-design.md src/labelwerk/cups.py src/labelwerk/gui/file_session.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/paper.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/settings_dialog.py src/labelwerk/po/de.po src/labelwerk/po/labelwerk.pot src/labelwerk/settings.py tests/gui/test_gui_papier.py tests/gui/test_gui_settings.py tests/gui/test_gui_start_tool.py tests/test_cups.py tests/test_settings.py
git commit -m "Abnahme-Korrekturen zusammen: stilles Speichern ohne fremde Änderungen zu überschreiben (update_settings), Rand-Hinweis mit Folgerung, Bürodrucker-Einordnung behält bekannten Wert, „Alle Schriften zeigen“ unter der Schriftart, Schriftliste beim Start einmal, README/CLAUDE.md/Spec

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Abnahme (manuell, durch den Nutzer)

- [ ] 62 mm endlos, Rand 1 mm und 5 mm: längs ~3 mm bzw. 5 mm bis zur Schnittkante; feste Länge 50 mm ergibt ein 50-mm-Stück.
- [ ] Reiter TEXT: Schriftliste kurz, jede Schrift in ihrer Schrift; Einstellungen → „Alle Schriften zeigen“.
- [ ] Einstellungen: Reiter beim Start (fest / zuletzt benutzter), Bilder Strich/Foto + Schwelle für neue Bilder.
- [ ] Druckermenü ohne Canon-Bürodrucker; Einstellung „Alle CUPS-Drucker zeigen“ holt ihn zurück; `labelwerk printers` nennt ausgeblendete.
