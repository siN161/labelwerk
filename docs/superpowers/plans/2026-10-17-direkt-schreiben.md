# Direkt auf dem Etikett schreiben (Etappe 3d-1b) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Text direkt im Rahmen auf dem Etikett schreiben und markieren wie im P-touch Editor; das Feld INHALT entfällt, Vorschau = Druck auch beim Tippen.

**Architecture:** Das bestehende QTextEdit bleibt unsichtbar als Eingabepuffer (Tastatur, Eingabemethoden, Rückgängig, Formatierung); die Arbeitsfläche zeigt das echte Objektbild und zeichnet Schreibmarke/Markierung aus dem Kern-Zeilensatz (`TextLayout`), der auch das Rendern speist.

**Tech Stack:** Python ≥ 3.10, Pillow, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-17-direkt-schreiben-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-3d1b`), nach jedem Task volle Suite grün mit Exit-Code 0 (848 → 922 → 942 → 998); jeder Schritt vor der Planerstellung geprüft und korrigiert (Kern: Druckbild byte-gleich in 400 Zufallsdokumenten; GUI: Fokus, Eingabemethoden, Rückgängig, Anker je Tastendruck); GUI per Offscreen-Screenshots geprüft.

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
### Task 1: Kern – Zeilensatz als TextLayout (Schreibmarke, Treffer, Markierung, Anker beim Wachsen)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/render.py`
- Create: `tests/test_text_layout.py`

**Interfaces / Produces:** `render.text_layout(obj, doc, model) -> TextLayout` (derselbe Zeilensatz wie das Rendern; `RenderedObject.layout`); `TextLayout.caret(pos) -> (x, top, h)`, `hit(x, y) -> pos`, `selection_rects(a, b)`, `lines: list[LayoutLine]`, `anchor(align)`; Einheiten Druckpunkte relativ zum ungedrehten Rahmen; Positionen wie QTextDocument (Absatzwechsel = 1 Zeichen, Unterschneidung berücksichtigt, keine Positionen in Graphem-Clustern); `render.to_utf16/from_utf16`; `layout.to_object/from_object` (Druckpunkte, Drehung); `layout.anchor_after_edit(obj, old, new) -> (x_mm, y_mm)`, `layout.anchor_align(obj)`; Druckbild unverändert (byte-gleich).

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/test_text_layout.py b/tests/test_text_layout.py
new file mode 100644
index 0000000..154bc70
--- /dev/null
+++ b/tests/test_text_layout.py
@@ -0,0 +1,433 @@
+"""Zeilensatz als TextLayout: Schreibmarke, Treffer, Markierung, Anker beim Wachsen (Etappe 3d-1b)."""
+import copy
+import math
+from dataclasses import replace
+
+import pytest
+
+from labelwerk import fonts, layout
+from labelwerk.document import ROTATIONS, Document, Paragraph, Span, TextObject
+from labelwerk.render import (RenderedObject, from_utf16, render_object, text_layout,
+                              to_utf16)
+
+DEJAVU_BOLD = fonts.resolve(None, True, False).path
+_TOL = 2           # Druckpunkte: Kantenglättung, Neigung der Kursiven knapp über der Grundlinie
+_BAND = (8, 2)     # Tintenband über der Grundlinie: von 8 bis 2 Punkte darüber
+
+# Nur Buchstaben, deren Tinte knapp über der Grundlinie genau ein zusammenhängendes Stück
+# ist (E, L, T, I, Z) – so lässt sich jedes Zeichen im Druckbild wiederfinden; keine stark
+# unterschnittenen Paare wie „LT“ (dort reicht der Fuß des „L“ unter das „T“ – die Schreibmarke
+# steht wie in Qt am Ursprung des „T“, also über dem Fuß)
+_MIXED = TextObject([
+    Paragraph([Span("EL", size_pt=10), Span("TI", size_pt=30, italic=True),
+               Span("ZE", bold=False)], "left"),
+    Paragraph([Span("LITEZ ELITE ZIEL", underline=True)], "right"),
+    Paragraph([], "center"),
+    Paragraph([Span("EL TI  ZE"), Span("IE", size_pt=14)], "justify"),
+    Paragraph([Span("ZIEL", italic=True)], "center"),
+], size_pt=12, x_mm=3, y_mm=4)
+_SLANTED = TextObject([Paragraph([Span("EL"), Span("TIZE", italic=True), Span("LE")], "left")],
+                      size_pt=24, font_path=DEJAVU_BOLD, x_mm=2, y_mm=2)
+_FRAMED = TextObject([Paragraph([Span("ZIEL")], "left"), Paragraph([Span("LE")], "right")],
+                     size_pt=12, fit=True, x_mm=2, y_mm=2, w_mm=40, h_mm=15)
+_CASES = {
+    "gemischt": Document("62", length_mm=80, objects=[_MIXED]),
+    "Ersatzkursive": Document("62", length_mm=60, objects=[_SLANTED]),
+    "fester Rahmen": Document("62", length_mm=60, objects=[_FRAMED]),
+    "ohne Position": Document("62", objects=[TextObject.plain("ZIEL\nELITE LZ", align="right")]),
+    "ohne Position, längs": Document("29", orientation="horizontal",
+                                     objects=[TextObject.plain("LITE\nZE", align="left")]),
+}
+
+
+def _ink(rendered: RenderedObject):
+    return rendered.image.point(lambda v: 255 if v < 128 else 0)
+
+
+def _band_pieces(ink, top: int, bottom: int) -> list[tuple[int, int]]:
+    """Zusammenhängende Tintenstücke (links, rechts) in den Pixelzeilen ``top``..``bottom``."""
+    band = ink.crop((0, top, ink.width, bottom))
+    pieces: list[list[int]] = []
+    for x in range(band.width):
+        if band.crop((x, 0, x + 1, band.height)).getbbox() is None:
+            continue
+        if pieces and pieces[-1][1] == x:
+            pieces[-1][1] = x + 1
+        else:
+            pieces.append([x, x + 1])
+    return [tuple(p) for p in pieces]
+
+
+def _plain(text: str, size_pt: float = 12, align: str = "center", **placement) -> TextObject:
+    """Reiner Text mit Position, Drehung … (``TextObject.plain`` kennt keine Platzierung)."""
+    return replace(TextObject.plain(text, size_pt=size_pt, align=align), **placement)
+
+
+def _positions(obj: TextObject) -> int:
+    """Anzahl der Positionen (Zeichen + Absatzwechsel + Ende)."""
+    return len(obj.text) + 1
+
+
+# --- Schreibmarke im echten Druckbild ------------------------------------------------
+@pytest.mark.parametrize("name", _CASES)
+def test_caret_lies_between_ink_of_neighbouring_characters(name):
+    doc = _CASES[name]
+    obj = doc.objects[0]
+    rendered = render_object(obj, doc)
+    text = text_layout(obj, doc)
+    ink = _ink(rendered)
+    dx, dy = rendered.image_dx, rendered.image_dy      # Bild liegt bei Rahmen + (dx, dy)
+    start = 0
+    for line, para in zip(text.lines, obj.paragraphs):
+        chars = para.text
+        carets = [text.caret(start + j) for j in range(len(chars) + 1)]
+        xs = [x for x, _, _ in carets]
+        assert xs == sorted(xs)
+        inked = [j for j, c in enumerate(chars) if c != " "]
+        if inked:
+            row = round(line.baseline) - dy
+            pieces = _band_pieces(ink, row - _BAND[0], row - _BAND[1])
+            assert len(pieces) == len(inked), f"Zeile {chars!r}"
+            left = {j: p[0] + dx for j, p in zip(inked, pieces)}       # in Rahmenkoordinaten
+            right = {j: p[1] + dx for j, p in zip(inked, pieces)}
+            for j, (x, y, h) in enumerate(carets):
+                before = [right[k] for k in inked if k < j]
+                after = [left[k] for k in inked if k >= j]
+                if before:
+                    assert x >= before[-1] - _TOL, f"Position {j} in {chars!r}"
+                if after:
+                    assert x <= after[0] + _TOL, f"Position {j} in {chars!r}"
+                assert y <= line.baseline - _BAND[0] and y + h >= line.baseline
+        start += len(chars) + 1
+
+
+def test_caret_follows_kerning_under_the_t():
+    obj = _plain("To", size_pt=40, align="left", x_mm=2, y_mm=2)
+    doc = Document("62", length_mm=80, objects=[obj])
+    rendered, text = render_object(obj, doc), text_layout(obj, doc)
+    row = round(text.lines[0].baseline) - rendered.image_dy
+    # halbe x-Höhe: Stamm des „T“, dann linke und rechte Seite des „o“ (unter dem Dach)
+    stem, bowl, _ = _band_pieces(_ink(rendered), row - 50, row - 40)
+    x = text.caret(1)[0] - rendered.image_dx
+    assert stem[1] - _TOL <= x <= bowl[0] + _TOL
+
+
+def test_caret_follows_kerning_at_the_top_of_av():
+    obj = _plain("AV", size_pt=60, align="left", x_mm=2, y_mm=2)
+    doc = Document("62", length_mm=80, objects=[obj])
+    rendered, text = render_object(obj, doc), text_layout(obj, doc)
+    ink = _ink(rendered)
+    top = ink.getbbox()[1]
+    # oben: Spitze des „A“, dann die beiden Arme des „V“ – das „V“ beginnt über dem „A“
+    apex, arm, _ = _band_pieces(ink, top + 2, top + 8)
+    x = text.caret(1)[0] - rendered.image_dx
+    assert apex[1] - _TOL <= x <= arm[0] + _TOL
+    assert text.caret(2)[0] == pytest.approx(text.lines[0].stops[-1])
+
+
+def test_rendered_object_carries_the_same_layout():
+    doc = _CASES["gemischt"]
+    obj = doc.objects[0]
+    rendered, text = render_object(obj, doc), text_layout(obj, doc)
+    assert [rendered.layout.caret(p) for p in range(_positions(obj))] == \
+        [text.caret(p) for p in range(_positions(obj))]
+    assert (text.width, text.height) == (rendered.w, rendered.h)
+
+
+def test_layout_size_is_unrotated_frame():
+    obj = copy.deepcopy(_MIXED)
+    obj.rotation = 90
+    doc = Document("62", length_mm=80, objects=[obj])
+    rendered, text = render_object(obj, doc), text_layout(obj, doc)
+    assert (text.width, text.height) == (rendered.h, rendered.w)
+
+
+# --- Treffer --------------------------------------------------------------------------
+@pytest.mark.parametrize("name", _CASES)
+def test_hit_on_caret_gives_its_position(name):
+    doc = _CASES[name]
+    text = text_layout(doc.objects[0], doc)
+    for pos in range(_positions(doc.objects[0])):
+        x, y, h = text.caret(pos)
+        assert text.hit(x, y + h / 2) == pos
+
+
+def test_hit_beside_and_beyond_the_text():
+    obj = _plain("ZIEL\nLE\nTEIL", size_pt=12, align="center", x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    _, y, h = text.caret(5)                        # zweite Zeile „LE“: Positionen 5..7
+    assert text.hit(-1000, y + h / 2) == 5         # links daneben → Zeilenanfang
+    assert text.hit(10_000, y + h / 2) == 7        # rechts daneben → Zeilenende
+    x0 = text.caret(1)[0]
+    assert text.hit(x0, -1000) == 1                # darüber → erste Zeile
+    assert text.hit(text.caret(9)[0], 10_000) == 9  # darunter → letzte Zeile
+
+
+def test_hit_picks_nearest_character_boundary():
+    obj = _plain("EL", size_pt=20, align="left", x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    (x0, y, h), (x1, _, _) = text.caret(0), text.caret(1)
+    assert text.hit(x0 + (x1 - x0) * 0.4, y + h / 2) == 0
+    assert text.hit(x0 + (x1 - x0) * 0.6, y + h / 2) == 1
+
+
+def test_hit_skips_positions_inside_a_character_cluster():
+    obj = _plain("e\u0301x", size_pt=20, align="left", x_mm=2, y_mm=2)   # „é“ zerlegt
+    text = text_layout(obj, Document("62", objects=[obj]))
+    x, y, h = text.caret(1)
+    assert x == text.caret(2)[0]                   # Akzent hat keine eigene Breite
+    assert text.hit(x, y + h / 2) == 2             # hinter dem ganzen „é“
+
+
+def test_caret_positions_are_clamped():
+    obj = _plain("EL", size_pt=20, x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    assert text.caret(-5) == text.caret(0) and text.caret(99) == text.caret(2)
+
+
+# --- Leerer Absatz, leerer Rahmen -------------------------------------------------------
+@pytest.mark.parametrize("align", ["left", "center", "right", "justify"])
+def test_empty_paragraph_caret_follows_alignment(align):
+    obj = TextObject([Paragraph([Span("ZIELE", size_pt=30)], align), Paragraph([], align),
+                      Paragraph([Span("Z")], align)], size_pt=12, x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    first, end, empty = text.caret(0), text.caret(5), text.caret(6)
+    expected = {"left": first[0], "justify": first[0], "right": end[0],
+                "center": (first[0] + end[0]) / 2}[align]
+    assert empty[0] == pytest.approx(expected, abs=0.5)
+    assert empty[1] > first[1] + first[2] / 2           # unter der ersten Zeile
+    assert empty[2] == pytest.approx(text.caret(7)[2])  # Höhe der Grundgröße, nicht 30 pt
+    assert empty[2] < first[2] / 2
+
+
+@pytest.mark.parametrize("align", ["left", "center", "right"])
+def test_empty_object_caret_at_frame(align):
+    obj = _plain("", size_pt=12, align=align, x_mm=5, y_mm=5)
+    doc = Document("62", objects=[obj])
+    text, rendered = text_layout(obj, doc), render_object(obj, doc)
+    x, y, h = text.caret(0)
+    assert (rendered.w, rendered.h) == (text.width, text.height)
+    assert x == pytest.approx(0, abs=0.5) and y == pytest.approx(0, abs=1)
+    assert h == pytest.approx(text_layout(_plain("E", size_pt=12, x_mm=5, y_mm=5),
+                                          doc).caret(0)[2])
+    assert text.hit(30, 30) == 0 and text.selection_rects(0, 0) == []
+
+
+# --- Ausrichtung ------------------------------------------------------------------
+def _two_lines(align):
+    obj = _plain("ZIEL\nLE ZIELTEIL", size_pt=12, align=align, x_mm=2, y_mm=2)
+    return text_layout(obj, Document("62", objects=[obj]))
+
+
+def test_left_lines_start_together():
+    text = _two_lines("left")
+    assert text.caret(0)[0] == pytest.approx(text.caret(5)[0])
+
+
+def test_right_lines_end_together():
+    text = _two_lines("right")
+    assert text.caret(4)[0] == pytest.approx(text.caret(16)[0], abs=0.5)
+    assert text.caret(0)[0] > text.caret(5)[0] + 50
+
+
+def test_centered_lines_share_middle():
+    text = _two_lines("center")
+    assert (text.caret(0)[0] + text.caret(4)[0]) / 2 == \
+        pytest.approx((text.caret(5)[0] + text.caret(16)[0]) / 2, abs=0.5)
+
+
+def test_justify_stretches_gaps_evenly_to_block_width():
+    obj = TextObject([Paragraph([Span("EL TI  ZE"), Span("LT", size_pt=14)], "justify"),
+                      Paragraph([Span("LITEZ ELITE ZIELE LITE")], "left")], size_pt=12,
+                     x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    # Leerzeichen bei 2, 5, 6: Schreibmarke davor und danach – der gedehnte Abstand
+    gaps = [text.caret(p + 1)[0] - text.caret(p)[0] for p in (2, 5, 6)]
+    space = fonts.load(DEJAVU_BOLD, round(12 * 300 / 72)).getlength(" ")
+    assert gaps[0] == pytest.approx(gaps[1]) == pytest.approx(gaps[2])
+    assert gaps[0] > 2 * space
+    assert text.caret(11)[0] == pytest.approx(text.caret(34)[0], abs=1)   # füllt die Blockbreite
+
+
+def test_mixed_sizes_share_baseline_and_caret_heights_scale():
+    obj = TextObject([Paragraph([Span("E", size_pt=10), Span("E", size_pt=30)], "left")],
+                     size_pt=20, x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    (_, y_small, h_small), (_, y_big, h_big) = text.caret(1), text.caret(2)
+    assert h_big / h_small == pytest.approx(3, rel=0.1)
+    assert y_small > y_big
+    baseline = text.lines[0].baseline
+    assert y_big < y_small < baseline < y_small + h_small < y_big + h_big
+
+
+def test_caret_at_paragraph_start_uses_first_character_else_character_before():
+    obj = TextObject([Paragraph([Span("E", size_pt=10), Span("E", size_pt=30)], "left")],
+                     size_pt=20, x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    assert text.caret(0)[2] == text.caret(1)[2] < text.caret(2)[2]
+
+
+def test_line_boxes_span_from_stop_to_stop():
+    obj = TextObject([Paragraph([Span("EL TI  ZE")], "justify"),
+                      Paragraph([Span("LITEZ ELITE ZIELE")], "left")], size_pt=12, x_mm=2, y_mm=2)
+    line = text_layout(obj, Document("62", objects=[obj])).lines[0]
+    boxes = line.boxes()
+    assert len(boxes) == len("EL TI  ZE") == line.end - line.start
+    assert boxes == [(a, b) for a, b in zip(line.stops, line.stops[1:])]
+    assert boxes[2][1] - boxes[2][0] == pytest.approx(boxes[5][1] - boxes[5][0])   # gedehnte Lücken
+
+
+# --- Positionen wie Qt (UTF-16) ----------------------------------------------------
+_EMOJI = "a\U0001F600b\nc"      # 😀 außerhalb der BMP: in UTF-16 zwei Einheiten
+
+
+@pytest.mark.parametrize("pos, pos16", [(0, 0), (1, 1), (2, 3), (3, 4), (4, 5), (5, 6)])
+def test_utf16_positions(pos, pos16):
+    assert to_utf16(_EMOJI, pos) == pos16
+    assert from_utf16(_EMOJI, pos16) == pos
+
+
+def test_utf16_position_inside_surrogate_pair_is_before_the_character():
+    assert from_utf16(_EMOJI, 2) == 1
+    assert from_utf16(_EMOJI, 99) == len(_EMOJI) and to_utf16("ab", 9) == 2
+
+
+# --- Markierung ---------------------------------------------------------------------
+def test_selection_within_one_line():
+    text = _two_lines("left")
+    (x1, _, _), (x2, _, _) = text.caret(6), text.caret(9)
+    line = text.lines[1]
+    assert text.selection_rects(6, 9) == [pytest.approx((x1, line.top, x2 - x1, line.height))]
+    assert text.selection_rects(9, 6) == text.selection_rects(6, 9)
+    assert text.selection_rects(7, 7) == []
+
+
+def test_selection_over_lines_and_empty_paragraph():
+    obj = TextObject([Paragraph([Span("ZIEL")], "left"), Paragraph([], "left"),
+                      Paragraph([Span("LE")], "left")], size_pt=12, x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    rects = text.selection_rects(2, 7)             # „EL“, Wechsel, leerer Absatz, Wechsel, „L“
+    assert len(rects) == 3
+    first, empty, last = rects
+    assert first[0] == pytest.approx(text.caret(2)[0])
+    assert first[2] > text.caret(4)[0] - text.caret(2)[0]     # Absatzwechsel mitmarkiert
+    assert empty[2] > 0                                         # leerer Absatz sichtbar
+    assert last[0] == pytest.approx(text.caret(6)[0])
+    assert last[2] == pytest.approx(text.caret(7)[0] - text.caret(6)[0])
+    assert [r[1] for r in rects] == [line.top for line in text.lines]
+    # Markierung endet am Zeilenende (vor dem Wechsel): kein Rechteck für die nächste Zeile
+    assert len(text.selection_rects(0, 4)) == 1
+
+
+# --- Etikett ↔ Objekt -------------------------------------------------------------
+def test_object_coordinates_for_quarter_turn():
+    rendered = RenderedObject(None, 100, 200, 30, 50, 12.0)     # ungedreht 50 × 30
+    assert layout.from_object((0, 0), rendered, 90) == pytest.approx((130, 200))
+    assert layout.from_object((50, 0), rendered, 90) == pytest.approx((130, 250))
+    assert layout.from_object((0, 30), rendered, 90) == pytest.approx((100, 200))
+    assert layout.from_object((0, 0), rendered, 270) == pytest.approx((100, 250))
+    assert layout.from_object((0, 0), rendered, 180) == pytest.approx((130, 250))
+    assert layout.to_object((130, 250), rendered, 90) == pytest.approx((50, 0))
+
+
+@pytest.mark.parametrize("rotation", ROTATIONS)
+def test_object_coordinates_round_trip(rotation):
+    rendered = RenderedObject(None, 100, 200, 30, 50, 12.0)
+    for point in [(0, 0), (12.5, 3.25), (29, 49), (-4, 70)]:
+        there = layout.from_object(point, rendered, rotation)
+        assert layout.to_object(there, rendered, rotation) == pytest.approx(point)
+
+
+@pytest.mark.parametrize("rotation", ROTATIONS)
+def test_object_coordinates_follow_the_rotated_image(rotation):
+    obj = TextObject([Paragraph([Span("Ziel", size_pt=10), Span("EL", italic=True)], "left"),
+                      Paragraph([Span("xy", underline=True)], "right")],
+                     size_pt=16, x_mm=4, y_mm=3, rotation=rotation)
+    flat_obj = copy.deepcopy(obj)
+    flat_obj.rotation = 0
+    flat = render_object(flat_obj, Document("62", length_mm=50, objects=[flat_obj]))
+    turned = render_object(obj, Document("62", length_mm=50, objects=[obj]))
+    for iy in range(flat.image.height):
+        for ix in range(flat.image.width):
+            u, v = ix + flat.image_dx + 0.5, iy + flat.image_dy + 0.5   # Pixelmitte
+            lx, ly = layout.from_object((u, v), turned, rotation)
+            jx = math.floor(lx - turned.x - turned.image_dx)
+            jy = math.floor(ly - turned.y - turned.image_dy)
+            assert turned.image.getpixel((jx, jy)) == flat.image.getpixel((ix, iy))
+
+
+def test_invalid_rotation_for_object_coordinates():
+    with pytest.raises(ValueError, match="Drehung"):
+        layout.to_object((0, 0), RenderedObject(None, 0, 0, 1, 1, 12.0), 45)
+
+
+# --- Anker beim Wachsen ----------------------------------------------------------
+_EDITS = [                                     # nacheinander getippt
+    ["ace", "nun ice"],
+    ["hace", "nun ice"],                       # Oberlänge
+    ["hacegy", "nun ice"],                     # Unterlänge am Ende
+    ["hacegy", "jnun ice"],                    # „j“ am Zeilenanfang (ragt nach links)
+    ["hacegy", "jnun ice ende"],               # mehr Text am Ende
+]
+
+
+def _edge(text, align):
+    """Bezugspunkt in Objektkoordinaten, unabhängig von ``TextLayout.anchor``: Ausrichtungs-
+    kante der ersten Zeile auf ihrer Grundlinie."""
+    line = text.lines[0]
+    x = {"left": line.stops[0], "justify": line.stops[0], "right": line.stops[-1],
+         "center": (line.stops[0] + line.stops[-1]) / 2}[align]
+    return x, line.baseline
+
+
+@pytest.mark.parametrize("rotation", ROTATIONS)
+@pytest.mark.parametrize("align", ["left", "center", "right", "justify"])
+def test_text_stays_in_place_while_typing(align, rotation):
+    def build(paras):
+        # Zeile 1 ist immer die breiteste: ihre Kante ist die des Blocks
+        return TextObject([Paragraph([Span(t)], align) for t in paras], size_pt=20,
+                          x_mm=20, y_mm=15, rotation=rotation)
+
+    doc = Document("62", length_mm=100)
+    obj = build(_EDITS[0])
+    old = render_object(obj, doc)
+    fixed = layout.from_object(_edge(old.layout, align), old, rotation)
+    for paras in _EDITS[1:]:
+        edited = replace(build(paras), x_mm=obj.x_mm, y_mm=obj.y_mm)
+        edited.x_mm, edited.y_mm = layout.anchor_after_edit(edited, old,
+                                                            render_object(edited, doc))
+        obj, old = edited, render_object(edited, doc)
+        assert layout.from_object(_edge(old.layout, align), old, rotation) == \
+            pytest.approx(fixed, abs=1), paras
+
+
+def test_anchor_for_quarter_turn_keeps_top_right_of_left_text():
+    obj = _plain("ace", size_pt=20, align="left", x_mm=20, y_mm=15, rotation=90)
+    doc = Document("62", length_mm=100)
+    old = render_object(obj, doc)
+    edited = replace(obj, paragraphs=TextObject.plain("ace\nzweite Zeile", align="left").paragraphs)
+    new = render_object(edited, doc)
+    x, y = layout.anchor_after_edit(edited, old, new)
+    # gedreht: Textoberkante rechts, Zeilenanfang oben – neue Zeilen wachsen nach links
+    assert x < obj.x_mm - 3 and y == pytest.approx(obj.y_mm, abs=0.2)
+
+
+def test_layout_anchor_is_block_edge_on_first_ascender_line():
+    obj = TextObject([Paragraph([Span("kurz")], "right"), Paragraph([Span("viel laenger")], "right")],
+                     size_pt=12, x_mm=2, y_mm=2)
+    text = text_layout(obj, Document("62", objects=[obj]))
+    widest = text.lines[1]
+    assert text.anchor("right") == pytest.approx((widest.stops[-1], text.lines[0].top))
+    assert text.anchor("left") == pytest.approx((widest.stops[0], text.lines[0].top))
+    assert text.anchor("center")[0] == pytest.approx((widest.stops[0] + widest.stops[-1]) / 2)
+    with pytest.raises(ValueError, match="Textposition"):
+        text.anchor("middle")
+
+
+@pytest.mark.parametrize("aligns, expected", [
+    (["center", "center"], "center"), (["right"], "right"), (["justify"], "justify"),
+    (["center", "right"], "left"), ([], "left"),
+])
+def test_anchor_align_of_object(aligns, expected):
+    obj = TextObject([Paragraph([Span("A")], a) for a in aligns])
+    assert layout.anchor_align(obj) == expected
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/CLAUDE.md b/CLAUDE.md
index b987dd8..07bf4af 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -27,6 +27,9 @@ src/labelwerk/
               prepare_object, label_size(prepared=), finish_object (nur Geändertes neu); span_dots
               Zeilensatz mit gemeinsamer Grundlinie (pixelgleich zu Pillow multiline_text für reinen Text), font_warnings(doc)
               exakte Druckbreite @300 dpi, Schrift schrumpft automatisch, mehrzeilig zentriert
+              text_layout(obj, doc) -> TextLayout (derselbe Zeilensatz wie das Rendern, auch RenderedObject.layout):
+              caret/hit/selection_rects/anchor in Druckpunkten relativ zum ungedrehten Rahmen, Positionen wie QTextDocument
+              (in Codepunkten; to_utf16/from_utf16 rechnen in Qts UTF-16-Positionen um)
   fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei
   files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
               crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
@@ -39,6 +42,7 @@ src/labelwerk/
   media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
   layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
               growing_axis (Endlosband wächst mit), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
+              Schreibmodus: to_object/from_object (Etikett ↔ ungedrehtes Objekt, Druckpunkte), anchor_after_edit/anchor_align
   shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich), effective, conflicts, without_conflicts, validate
   desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
   gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index 85e0d38..b789bc6 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -2,13 +2,15 @@
 
 Alle Rechtecke in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts
 (wie ``TextObject.x_mm``/``y_mm``). Die GUI rechnet nur in Bildschirmkoordinaten um.
+Ausnahme Schreibmodus (``to_object``/``from_object``): Punkte in Druckpunkten wie
+``RenderedObject`` und ``TextLayout`` – so rechnet die Arbeitsfläche ohne Umweg über mm.
 """
 from __future__ import annotations
 
 import copy
 from dataclasses import dataclass, field, replace
 
-from .document import MAX_PT, MIN_PT, Document, TextObject
+from .document import MAX_PT, MIN_PT, ROTATIONS, Document, TextObject
 from .labels import DPI, get_label
 from .render import (PT, REF_PT, RenderedObject, span_dots, label_margins, label_size,
                      render_object)
@@ -510,3 +512,77 @@ def to_grid(obj: TextObject, x: bool = False, y: bool = False, w: bool = False,
 def _rounded(rect: Rect) -> Rect:
     """Rahmen fürs Modell: auf 1/1000 mm gerundet."""
     return Rect(*(round(v, _DECIMALS) for v in (rect.x, rect.y, rect.w, rect.h)))
+
+
+# --- Schreibmodus -------------------------------------------------------------------
+def to_object(point: tuple[float, float], rendered: RenderedObject,
+              rotation: int) -> tuple[float, float]:
+    """Punkt auf dem Etikett (Druckpunkte in Leserichtung) → Objektkoordinaten: Druckpunkte
+    relativ zur linken oberen Ecke des Rahmens vor der Drehung (wie ``TextLayout``).
+
+    ``rendered``: das gerenderte Objekt (Rahmen nach der Drehung), ``rotation`` seine Drehung.
+    Punkte außerhalb des Rahmens bleiben gültig (Treffer im überstehenden Text).
+    """
+    return _to_frame(point, (rendered.x, rendered.y, rendered.w, rendered.h), rotation)
+
+
+def from_object(point: tuple[float, float], rendered: RenderedObject,
+                rotation: int) -> tuple[float, float]:
+    """Umkehrung von ``to_object``: Objektkoordinaten → Punkt auf dem Etikett (Druckpunkte)."""
+    return _from_frame(point, (rendered.x, rendered.y, rendered.w, rendered.h), rotation)
+
+
+def _unturned(frame: tuple[float, float, float, float], rotation: int) -> tuple[float, float]:
+    """Rahmengröße (Breite, Höhe) vor der Drehung."""
+    if rotation not in ROTATIONS:
+        raise ValueError(f"Unbekannte Drehung {rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
+    _, _, w, h = frame
+    return (h, w) if rotation in (90, 270) else (w, h)
+
+
+def _from_frame(point: tuple[float, float], frame: tuple[float, float, float, float],
+                rotation: int) -> tuple[float, float]:
+    """Punkt im ungedrehten Rahmen → Etikett; ``frame`` (x, y, w, h) nach der Drehung, in
+    beliebiger Einheit. Gedreht wird im Uhrzeigersinn wie ``render._turn``."""
+    u, v = point
+    x, y = frame[:2]
+    w, h = _unturned(frame, rotation)
+    return {0: (x + u, y + v), 90: (x + h - v, y + u),
+            180: (x + w - u, y + h - v), 270: (x + v, y + w - u)}[rotation]
+
+
+def _to_frame(point: tuple[float, float], frame: tuple[float, float, float, float],
+              rotation: int) -> tuple[float, float]:
+    """Umkehrung von ``_from_frame``."""
+    px, py = point[0] - frame[0], point[1] - frame[1]
+    w, h = _unturned(frame, rotation)
+    return {0: (px, py), 90: (py, h - px), 180: (w - px, h - py), 270: (w - py, px)}[rotation]
+
+
+def anchor_align(obj: TextObject) -> str:
+    """Textposition, nach der sich der Rahmen beim Wachsen richtet (``anchor_after_edit``):
+    die gemeinsame der Absätze; haben sie verschiedene, bleibt die linke Kante („left“)."""
+    aligns = {para.align for para in obj.paragraphs}
+    return aligns.pop() if len(aligns) == 1 else "left"
+
+
+def anchor_after_edit(obj: TextObject, old: RenderedObject,
+                      new: RenderedObject) -> tuple[float, float]:
+    """Neue Position (``x_mm``, ``y_mm``) eines Objekts ohne feste Rahmengröße, nachdem sein
+    Text beim Tippen gewachsen oder geschrumpft ist – der Text bleibt stehen.
+
+    ``obj``: das bearbeitete Objekt, noch an der alten Position; ``old``: gerendert vor der
+    Bearbeitung, ``new``: ``obj`` gerendert. Fest bleibt der Punkt ``TextLayout.anchor`` zur
+    Textposition ``anchor_align(obj)``: in Leserichtung des Texts die linke Kante (links,
+    Blocksatz, gemischt), die rechte Kante (rechts) bzw. die Mitte (zentriert) und in der
+    Höhe die Oberkante der ersten Zeile – bei gedrehten Objekten entsprechend gedreht.
+    Nur für Objekte mit Position: eines ohne Position bleibt mittig auf dem Etikett, der
+    Aufrufer setzt dort keine Position.
+    """
+    align = anchor_align(obj)
+    start = exact_rect(obj, old)
+    # Lage des festen Punkts relativ zur linken oberen Ecke des Rahmens (Druckpunkte)
+    ox, oy = from_object(old.layout.anchor(align), old, obj.rotation)
+    nx, ny = from_object(new.layout.anchor(align), new, obj.rotation)
+    return (round(start.x + _mm(ox - old.x) - _mm(nx - new.x), _DECIMALS),
+            round(start.y + _mm(oy - old.y) - _mm(ny - new.y), _DECIMALS))
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 3404acb..8c83d24 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -3,11 +3,14 @@
 Der Zeilensatz verallgemeinert Pillows ``multiline_text`` auf formatierte Textstücke:
 gleicher Zeilenabstand (Unterkante von „A“ + 4 Punkte), gleiche Ausrichtungsrechnung –
 reiner Text sieht dadurch pixelgleich aus wie früher.
+Das Ergebnis (``TextLayout``) zeichnet das Rendern; dieselben Zahlen liefern der
+Arbeitsfläche Schreibmarke, Treffer und Markierung.
 """
 from __future__ import annotations
 
 import math
-from dataclasses import dataclass
+from dataclasses import dataclass, field
+from functools import cached_property
 
 from PIL import Image, ImageDraw, ImageOps
 
@@ -74,6 +77,7 @@ class RenderedObject:
     Tinte ab (Anschnitt: Kantenglättung, Unterstreichung, Glyphen wie „J“ reichen etwas über
     den Rahmen); seine linke obere Ecke liegt bei ``x + image_dx``, ``y + image_dy``
     (``image_dx``/``image_dy`` ≤ 0).
+    ``layout``: der Zeilensatz, aus dem das Bild gezeichnet wurde (Schreibmarke, Treffer).
     """
     image: Image.Image
     x: int
@@ -83,17 +87,29 @@ class RenderedObject:
     base_pt: float
     image_dx: int = 0
     image_dy: int = 0
+    layout: TextLayout | None = field(default=None, compare=False, repr=False)
 
 
 def render_object(obj: TextObject, doc: Document, model: str = "QL-600") -> RenderedObject:
     """Ein Objekt einzeln rendern (Arbeitsfläche); Position bezogen auf das Etikett von ``doc``."""
+    return _finish(*_measure(obj, doc, model))
+
+
+def text_layout(obj: TextObject, doc: Document, model: str = "QL-600") -> TextLayout:
+    """Zeilensatz eines Objekts ohne Bild – derselbe, den ``render_object`` zeichnet
+    (``RenderedObject.layout``)."""
+    return _place(*_measure(obj, doc, model))[0]
+
+
+def _measure(obj: TextObject, doc: Document, model: str) -> tuple[Prepared, _Sheet, int, int]:
+    """Objekt messen; Etikettgröße nur für ein Objekt ohne Position (mittig), sonst 0."""
     sheet = _sheet(doc, model)
     prep = _prepare(obj, sheet)
     width = height = 0
     if not obj.positioned:                     # mittig: braucht die Etikettgröße
         others = [_prepare(o, sheet) for o in doc.objects if o is not obj]
         width, height = _label_size(sheet, [prep, *others])
-    return _finish(prep, sheet, width, height)
+    return prep, sheet, width, height
 
 
 def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
@@ -267,12 +283,14 @@ def _label_size(sheet: _Sheet, preps: list[Prepared]) -> tuple[int, int]:
     return (feed, sheet.across) if sheet.horizontal else (sheet.across, feed)
 
 
-def _finish(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
-    """Objektbild zeichnen und auf dem Etikett (``width`` × ``height``) platzieren.
+def _place(prep: Prepared, sheet: _Sheet, width: int, height: int
+           ) -> tuple[TextLayout, tuple[int, int, int, int], tuple[int, int], tuple[int, int]]:
+    """Zeilensatz im Rahmen auf dem Etikett (``width`` × ``height``).
 
     Gerechnet wird ungedreht in einer Fläche ``area`` (positioniert: der eigene Rahmen,
-    sonst das Etikett – bei 90/270 mit getauschten Seiten); danach werden Bild, Rahmen und
-    Bildlage mit der Fläche gedreht.
+    sonst das Etikett – bei 90/270 mit getauschten Seiten). Zurück kommen der Zeilensatz
+    (relativ zum Rahmen), der Rahmen (x, y, w, h) in der Fläche, die Fläche (Breite, Höhe)
+    und die Lage der Fläche auf dem Etikett.
     """
     obj = prep.obj
     lines, (l, t, r, b) = prep.lines, prep.box
@@ -294,7 +312,17 @@ def _finish(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedO
         fl, ft, fr, fb = _block_box(lines)
         frame = (x0 + fl, y0 + ft, fr - fl, fb - ft)
         origin = (0, 0)
-    image, (ix, iy) = _paint(lines, x0 - frame[0], y0 - frame[1], *frame[2:],
+    text = TextLayout([para.text for para in obj.paragraphs], lines, x0 - frame[0],
+                      y0 - frame[1], frame[2], frame[3])
+    return text, frame, area, origin
+
+
+def _finish(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
+    """Objektbild aus dem Zeilensatz (``_place``) zeichnen und auf dem Etikett platzieren;
+    Bild, Rahmen und Bildlage werden mit der Fläche gedreht."""
+    obj = prep.obj
+    text, frame, area, origin = _place(prep, sheet, width, height)
+    image, (ix, iy) = _paint(text.pieces, text.x0, text.y0, *frame[2:],
                              at=(origin[0] + frame[0], origin[1] + frame[1]))
     picture = (frame[0] + ix, frame[1] + iy, image.width, image.height)
     if obj.rotation:
@@ -303,7 +331,7 @@ def _finish(prep: Prepared, sheet: _Sheet, width: int, height: int) -> RenderedO
         picture = _turn(picture, area, obj.rotation)
     base_pt = obj.size_pt if not obj.auto else prep.base / PT
     return RenderedObject(image, origin[0] + frame[0], origin[1] + frame[1], frame[2], frame[3],
-                          base_pt, picture[0] - frame[0], picture[1] - frame[1])
+                          base_pt, picture[0] - frame[0], picture[1] - frame[1], text)
 
 
 _TRANSPOSE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
@@ -411,6 +439,7 @@ class _Piece:
     slant: bool                # Ersatzkursive
     x: float = 0.0             # links, relativ zum Block
     y: float = 0.0             # Oberkante (Ascender-Linie), relativ zum Block
+    start: int = 0             # Stelle des ersten Zeichens im Absatz
 
 
 def _font_for(obj: TextObject, span: Span, dots: int):
@@ -429,11 +458,12 @@ def _shape(obj: TextObject, base: int, mode: str = "L",
     rows = []
     for para in obj.paragraphs:
         spans = para.spans or [Span("")]
-        pieces = []
+        pieces, start = [], 0
         for span in spans:
             dots = span_dots(obj, span, base)
             font, slant = _font_for(obj, span, dots)
-            pieces.append(_Piece(span.text, font, dots, span.underline, slant))
+            pieces.append(_Piece(span.text, font, dots, span.underline, slant, start=start))
+            start += len(span.text)
         rows.append((para, pieces))
 
     widths = [sum(p.font.getlength(p.text, mode) for p in pieces) for _, pieces in rows]
@@ -462,13 +492,17 @@ def _shape(obj: TextObject, base: int, mode: str = "L",
 
 
 def _justify(pieces: list[_Piece], max_width: float, mode: str) -> list[_Piece]:
-    """Wortabstände dehnen, bis die Zeile die Blockbreite füllt (ein Wort: linksbündig)."""
+    """Wortabstände dehnen, bis die Zeile die Blockbreite füllt (ein Wort: linksbündig).
+
+    Die Leerzeichen entfallen: jedes wird zur gedehnten Lücke vor dem folgenden Wort."""
     words: list[_Piece] = []
     gaps_before: list[bool] = []
     for p in pieces:
+        start = p.start
         for i, part in enumerate(p.text.split(" ")):
-            words.append(_Piece(part, p.font, p.dots, p.underline, p.slant))
+            words.append(_Piece(part, p.font, p.dots, p.underline, p.slant, start=start))
             gaps_before.append(i > 0)
+            start += len(part) + 1
     gaps = sum(gaps_before[1:])
     used = sum(w.font.getlength(w.text, mode) for w in words)
     extra = (max_width - used) / gaps if gaps else 0.0
@@ -481,6 +515,187 @@ def _justify(pieces: list[_Piece], max_width: float, mode: str) -> list[_Piece]:
     return words
 
 
+@dataclass(frozen=True)
+class LayoutLine:
+    """Eine Zeile (ein Absatz) des Zeilensatzes, Koordinaten wie ``TextLayout``.
+
+    ``stops``: x jeder Zeichengrenze (Zeichen + 1 Werte; Schreibmarke vor Zeichen i);
+    ``marks``: je Grenze Oberkante und Höhe der Schreibmarke – in der Schrift des Zeichens
+    davor, am Zeilenanfang des ersten Zeichens. Ein leerer Absatz hat kein Zeichen: dort gilt
+    die Standardschrift des Objekts in Grundgröße. Schreibt der Editor in einem anderen
+    Format weiter, skaliert die GUI die Marke um die Grundlinie (Höhe und Abstand
+    Oberkante–Grundlinie wachsen mit der Schriftgröße).
+    ``top``: Ascender-Linie der größten Schrift, ``baseline``: gemeinsame Grundlinie,
+    ``height``: bis zur tiefsten Unterlänge; ``break_width``: Breite des markierten
+    Absatzwechsels (ein Leerzeichen am Zeilenende).
+    """
+    start: int
+    stops: tuple[float, ...]
+    marks: tuple[tuple[float, float], ...]
+    top: float
+    baseline: float
+    height: float
+    break_width: float
+
+    @property
+    def end(self) -> int:
+        """Position nach dem letzten Zeichen (vor dem Absatzwechsel)."""
+        return self.start + len(self.stops) - 1
+
+    def boxes(self) -> list[tuple[float, float]]:
+        """Kästchen (x0, x1) je Zeichen; ein Leerzeichen im Blocksatz reicht über die
+        ganze gedehnte Lücke."""
+        return list(zip(self.stops, self.stops[1:]))
+
+
+@dataclass(eq=False)
+class TextLayout:
+    """Zeilensatz eines Textobjekts: das Rendern zeichnet ``pieces``, die Arbeitsfläche
+    bekommt daraus Schreibmarke, Treffer und Markierung (eine Berechnung, zwei Nutzer).
+
+    Koordinaten in Druckpunkten relativ zur linken oberen Ecke des Objektrahmens **vor** der
+    Drehung (``width`` × ``height``; bei 90/270° sind ``RenderedObject.w``/``h`` vertauscht –
+    ``layout.to_object``/``from_object`` rechnen vom und aufs Etikett um).
+    Positionen zählen wie im ``QTextDocument``: die Zeichen der Absätze hintereinander, jeder
+    Absatzwechsel zählt als ein Zeichen; Positionen außerhalb werden auf den Text begrenzt.
+    """
+    texts: list[str]               # Text je Absatz
+    pieces: list[list[_Piece]]     # gesetzte Stücke je Zeile, relativ zum Block
+    x0: int                        # Blockursprung im Rahmen
+    y0: int
+    width: int
+    height: int
+
+    @cached_property
+    def lines(self) -> list[LayoutLine]:
+        """Zeilen mit Zeichengrenzen – erst bei Bedarf gemessen (das Rendern braucht sie nicht)."""
+        lines, start = [], 0
+        for text, pieces in zip(self.texts, self.pieces):
+            lines.append(_layout_line(text, pieces, start, self.x0, self.y0))
+            start += len(text) + 1
+        return lines
+
+    def caret(self, pos: int) -> tuple[float, float, float]:
+        """Schreibmarke vor Zeichen ``pos``: (x, Oberkante, Höhe)."""
+        line = self._line_at(pos)
+        i = self._clamp(pos) - line.start
+        return (line.stops[i], *line.marks[i])
+
+    def hit(self, x: float, y: float) -> int:
+        """Nächste Zeichengrenze zum Punkt (``x``, ``y``).
+
+        Die Zeile wechselt in der Mitte zwischen Unterkante und nächster Oberkante; Punkte
+        über/unter dem Text treffen die erste/letzte Zeile, links/rechts daneben deren
+        Anfang/Ende. Grenzen ohne Breite (z. B. vor einem kombinierenden Akzent) zählen
+        nicht – getroffen wird die Stelle hinter dem ganzen Zeichen.
+        """
+        lines = self.lines
+        line = lines[sum(1 for above, below in zip(lines, lines[1:])
+                         if y >= (above.top + above.height + below.top) / 2)]
+        stops = line.stops
+        candidates = [k for k in range(len(stops))
+                      if k == len(stops) - 1 or stops[k] != stops[k + 1]]
+        return line.start + min(candidates, key=lambda k: abs(stops[k] - x))
+
+    def selection_rects(self, a: int, b: int) -> list[tuple[float, float, float, float]]:
+        """Markierung zwischen ``a`` und ``b`` (Reihenfolge egal): ein Rechteck
+        (x, y, w, h) je betroffener Zeile über die ganze Zeilenhöhe; ein markierter
+        Absatzwechsel verlängert seine Zeile um ``break_width``. Die Rechtecke folgen den
+        Zeichengrenzen – den nach rechts überhängenden Kopf der Ersatzkursive decken sie
+        nicht ab."""
+        a, b = sorted((self._clamp(a), self._clamp(b)))
+        rects = []
+        for line in self.lines:
+            if line.end < a or line.start > b:
+                continue
+            x1 = line.stops[max(a, line.start) - line.start]
+            x2 = line.stops[min(b, line.end) - line.start]
+            if b > line.end:
+                x2 += line.break_width
+            if x2 > x1:
+                rects.append((x1, line.top, x2 - x1, line.height))
+        return rects
+
+    def anchor(self, align: str) -> tuple[float, float]:
+        """Punkt, der beim Tippen stehen bleibt (``layout.anchor_after_edit``): senkrecht die
+        Oberkante (Ascender-Linie) der ersten Zeile, waagerecht die Bezugskante des Blocks –
+        Anfang (links, Blocksatz), Ende (rechts) bzw. Mitte (zentriert) der breitesten Zeile.
+
+        Bezug sind Schriftmaße, nicht die Tinte: eine Oberlänge oder ein „j“ am Zeilenanfang
+        verschiebt den Rahmen (Tintenbox), aber nicht den Text. Die Zeile, in die getippt
+        wird, bleibt stehen, solange sie die breiteste ist oder ihre Ausrichtung zur
+        Bezugskante passt; bei gemischten Ausrichtungen gilt die linke Kante.
+        """
+        if align not in ALIGNMENTS:
+            raise ValueError(f"Unbekannte Textposition {align!r} – erlaubt: links, zentriert, "
+                             "rechts, Blocksatz (left, center, right, justify)")
+        left = min(line.stops[0] for line in self.lines)
+        right = max(line.stops[-1] for line in self.lines)
+        share = {"left": 0.0, "justify": 0.0, "center": 0.5, "right": 1.0}[align]
+        return left + share * (right - left), self.lines[0].top
+
+    def _clamp(self, pos: int) -> int:
+        return min(max(pos, 0), self.lines[-1].end)
+
+    def _line_at(self, pos: int) -> LayoutLine:
+        pos = self._clamp(pos)
+        return next(line for line in self.lines if line.start <= pos <= line.end)
+
+
+def to_utf16(text: str, pos: int) -> int:
+    """Position in Zeichen (Codepunkte, wie ``TextLayout``) → Position in UTF-16-Einheiten
+    (wie ``QTextDocument``: Zeichen außerhalb der BMP zählen doppelt); ``text`` wie
+    ``TextObject.text`` (Absatzwechsel = „\\n“)."""
+    pos = min(max(pos, 0), len(text))
+    return pos + sum(1 for char in text[:pos] if ord(char) > 0xFFFF)
+
+
+def from_utf16(text: str, pos16: int) -> int:
+    """Umkehrung von ``to_utf16``; eine Position mitten in einem Ersatzzeichenpaar zählt als
+    die vor dem Zeichen."""
+    units = 0
+    for i, char in enumerate(text):
+        units += 2 if ord(char) > 0xFFFF else 1
+        if units > pos16:
+            return i
+    return len(text)
+
+
+def _layout_line(text: str, pieces: list[_Piece], start: int, x0: int, y0: int) -> LayoutLine:
+    """Zeichengrenzen und Schreibmarken einer Zeile aus ihren gesetzten Stücken."""
+    stops = [0.0] * (len(text) + 1)
+    for p in pieces:
+        t = p.text
+        prefix = [p.font.getlength(t[:k], "L") for k in range(len(t) + 1)]
+        for j in range(len(t) + 1):
+            # Ursprung von Zeichen j, wie gezeichnet – samt Unterschneidung zum Zeichen davor
+            # („To“: das „o“ rückt unter das „T“); ein Zeichen ohne eigene Breite (kombinierender
+            # Akzent) steht an der Grenze davor; das Ende ist die Länge des ganzen Stücks
+            if j == len(t) or prefix[j + 1] == prefix[j]:
+                advance = prefix[j]
+            else:
+                advance = prefix[j + 1] - p.font.getlength(t[j], "L")
+            stops[p.start + j] = x0 + p.x + advance
+    # Stück je Zeichen: das letzte, das davor beginnt – ein Leerzeichen im Blocksatz gehört
+    # so zum Wort davor (gleiches Textstück), ein leeres Stück zum folgenden
+    owner, i = [], 0
+    for k in range(len(text)):
+        while i + 1 < len(pieces) and pieces[i + 1].start <= k:
+            i += 1
+        owner.append(pieces[i])
+    marks = []
+    for j in range(len(text) + 1):
+        p = owner[j - 1] if j else owner[0] if owner else pieces[0]
+        ascent, descent = p.font.getmetrics()
+        marks.append((y0 + p.y, ascent + descent))
+    top = min(p.y for p in pieces)
+    baseline = max(p.y + p.font.getmetrics()[0] for p in pieces)
+    bottom = max(p.y + sum(p.font.getmetrics()) for p in pieces)
+    last = owner[-1] if owner else pieces[0]
+    return LayoutLine(start, tuple(stops), tuple(marks), y0 + top, y0 + baseline, bottom - top,
+                      last.font.getlength(" ", "L"))
+
+
 def _block_box(lines: list[list[_Piece]]) -> tuple[int, int, int, int]:
     """Tintenbox des Blocks (wie Pillow multiline_textbbox), auf ganze Punkte gerundet."""
     boxes = []
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `922 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/layout.py src/labelwerk/render.py tests/test_text_layout.py
git commit -m "Kern: Zeilensatz als TextLayout – Schreibmarke, Treffer, Markierung, Anker beim Wachsen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: GUI – Schreibmodus direkt auf dem Etikett (versteckter Editor, Schreibmarke, Markierung)

**Files:**
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Create: `src/labelwerk/gui/text_edit_mode.py`
- Create: `tests/gui/test_gui_edit_mode.py`

**Interfaces / Produces:** `gui/text_edit_mode.py` `TextEditSession` (`start(index, point)`, `end()`, `content_changed()`, `update_marks()`); `MainWindow.edit_text(index, point=None)`, `finish_editing(drop_empty=False)`; Canvas `set_editing`, `set_edit_marks`, `caret_line()`, `selection_rects()`, Signale `edit_pressed`, `edit_dragged`, `edit_double_clicked`, `edit_left`; Feld INHALT entfällt, Editor unsichtbar als Eingabepuffer.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_edit_mode.py b/tests/gui/test_gui_edit_mode.py
new file mode 100644
index 0000000..0ca3ffe
--- /dev/null
+++ b/tests/gui/test_gui_edit_mode.py
@@ -0,0 +1,250 @@
+"""Schreibmodus: direkt auf dem Etikett schreiben (Etappe 3d-1b)."""
+import pytest
+from PySide6.QtCore import QPointF, Qt
+from PySide6.QtGui import QMouseEvent
+from PySide6.QtTest import QTest
+from PySide6.QtWidgets import QApplication
+
+from labelwerk import layout
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.canvas import MM
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.settings import Settings
+
+NO_MOD = Qt.KeyboardModifier.NoModifier
+SHIFT = Qt.KeyboardModifier.ShiftModifier
+LEFT = Qt.MouseButton.LeftButton
+
+
+def _doc(orientation="vertical", rotation=0):
+    return Document("62", length_mm=40, orientation=orientation, objects=[
+        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4, rotation=rotation),
+        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=24)])
+
+
+def _window(qtbot, doc=None):
+    win = MainWindow(doc=doc if doc is not None else _doc(),
+                     settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    win.show()
+    win.activateWindow()
+    return win
+
+
+@pytest.fixture
+def window(qtbot):
+    return _window(qtbot)
+
+
+def _send(canvas, kind, pos, buttons, modifiers=NO_MOD):
+    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
+    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)),
+                        button, buttons, modifiers)
+    QApplication.sendEvent(canvas.viewport(), event)
+
+
+def _click(canvas, pos, modifiers=NO_MOD):
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, pos, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton, modifiers)
+
+
+def _double_click(canvas, pos):
+    _click(canvas, pos)
+    _send(canvas, QMouseEvent.Type.MouseButtonDblClick, pos, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)
+
+
+def _view_point(canvas, x_dots, y_dots):
+    """Punkt in Druckpunkten in Leserichtung → Ansichtskoordinaten."""
+    return canvas.viewportTransform().map(canvas.sheet.mapToScene(QPointF(x_dots, y_dots)))
+
+
+def _char_point(window, index, pos):
+    """Ansichtspunkt der Schreibmarke vor Zeichen ``pos`` (halbe Zeilenhöhe) im Objekt."""
+    rendered = window.rendered[index]
+    x, top, h = rendered.layout.caret(pos)
+    point = layout.from_object((x, top + h / 2), rendered, window.doc.objects[index].rotation)
+    return _view_point(window.canvas, *point)
+
+
+def _session(window):
+    return window.edit_session
+
+
+def _empty_area(canvas):
+    return canvas.view_rect(1).bottomRight() + QPointF(40, 40)
+
+
+# --- Start --------------------------------------------------------------------------
+def test_text_tool_click_starts_edit_mode_and_typing_lands_in_new_frame(window, qtbot):
+    window.shortcut_actions["tool.text"].trigger()
+    _click(window.canvas, _view_point(window.canvas, 30 * MM, 12 * MM))
+    session = _session(window)
+    assert session.active and session.index == 2
+    editor = window.panel("text").edit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    QTest.keyClicks(editor, "Neu")
+    assert window.doc.objects[2].text == "Neu"
+    assert window.rendered[2].layout.texts == ["Neu"]          # sofort gerendert, ohne Timer
+    assert window.canvas.objects[2].rendered is window.rendered[2]
+
+
+def test_double_click_starts_edit_mode_with_caret_at_click_point(window):
+    _double_click(window.canvas, _char_point(window, 1, 2))
+    session = _session(window)
+    assert session.active and session.index == 1
+    assert window.canvas.selection() == [1]
+    assert window.panel("text").edit.textCursor().position() == 2
+    assert window.panels.currentWidget() is window.panel("text")
+
+
+def test_double_click_on_rotated_text_hits_the_right_character(qtbot):
+    win = _window(qtbot, _doc(rotation=90))
+    _double_click(win.canvas, _char_point(win, 0, 3))
+    assert _session(win).index == 0
+    assert win.panel("text").edit.textCursor().position() == 3
+
+
+def test_click_into_selected_frame_does_not_start_edit_mode(window):
+    window.canvas.set_selection([0])
+    _click(window.canvas, window.canvas.view_rect(0).center())
+    assert not _session(window).active
+    assert window.canvas.selection() == [0]
+
+
+def test_editor_has_focus_while_editing(window, qtbot):
+    _double_click(window.canvas, _char_point(window, 0, 1))
+    editor = window.panel("text").edit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    _click(window.canvas, _char_point(window, 0, 3))         # Klick in den Rahmen
+    assert editor.hasFocus() and editor.textCursor().position() == 3
+    assert _session(window).active
+
+
+def test_contents_field_is_gone_from_the_panel(window):
+    panel = window.panel("text")
+    window.canvas.set_selection([0])
+    assert panel.edit.width() == 0 and panel.edit.height() == 0
+    assert panel.layout_.indexOf(panel.edit) == -1
+    sections = [label.text() for label in panel.findChildren(type(panel.hint))
+                if label.property("role") == "section"]
+    assert "INHALT" not in sections
+
+
+# --- Ende ---------------------------------------------------------------------------
+def test_esc_ends_edit_mode_and_keeps_the_frame_selected(window, qtbot):
+    _double_click(window.canvas, _char_point(window, 0, 1))
+    editor = window.panel("text").edit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    assert not _session(window).active
+    assert window.canvas.selection() == [0]
+    qtbot.waitUntil(window.canvas.hasFocus, timeout=1000)   # Objekt-Kürzel gelten wieder
+    assert window.canvas.editing() is None
+
+
+def test_click_outside_ends_edit_mode(window):
+    _double_click(window.canvas, _char_point(window, 0, 1))
+    _click(window.canvas, _empty_area(window.canvas))
+    assert not _session(window).active
+    assert window.canvas.selection() == []
+
+
+def test_click_on_other_object_ends_edit_mode_and_selects_it(window):
+    _double_click(window.canvas, _char_point(window, 0, 1))
+    _click(window.canvas, window.canvas.view_rect(1).center())
+    assert not _session(window).active
+    assert window.canvas.selection() == [1]
+
+
+def test_empty_new_frame_is_removed_when_edit_mode_ends(window, qtbot):
+    window.create_text(30, 12)
+    editor = window.panel("text").edit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
+    assert window.canvas.selection() == []
+
+
+# --- Darstellung --------------------------------------------------------------------
+def _expected_caret(window, index, pos):
+    rendered = window.rendered[index]
+    x, top, h = rendered.layout.caret(pos)
+    rotation = window.doc.objects[index].rotation
+    a = layout.from_object((x, top), rendered, rotation)
+    b = layout.from_object((x, top + h), rendered, rotation)
+    return _view_point(window.canvas, *a), _view_point(window.canvas, *b)
+
+
+@pytest.mark.parametrize("orientation, rotation", [("vertical", 0), ("horizontal", 0),
+                                                   ("vertical", 90), ("horizontal", 270)])
+def test_caret_drawn_where_the_layout_puts_it(qtbot, orientation, rotation):
+    win = _window(qtbot, _doc(orientation, rotation))
+    _double_click(win.canvas, _char_point(win, 0, 2))
+    line = win.canvas.caret_line()
+    start, end = _expected_caret(win, 0, 2)
+    assert line.p1().x() == pytest.approx(start.x(), abs=1)
+    assert line.p1().y() == pytest.approx(start.y(), abs=1)
+    assert line.p2().x() == pytest.approx(end.x(), abs=1)
+    assert line.p2().y() == pytest.approx(end.y(), abs=1)
+
+
+def test_caret_follows_typing_with_the_new_layout(window, qtbot):
+    _double_click(window.canvas, _char_point(window, 0, 2))
+    editor = window.panel("text").edit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    editor.moveCursor(editor.textCursor().MoveOperation.End)
+    QTest.keyClicks(editor, "XX")
+    start, _ = _expected_caret(window, 0, 6)
+    assert window.canvas.caret_line().p1().x() == pytest.approx(start.x(), abs=1)
+
+
+def test_empty_frame_caret_starts_at_click_point(window):
+    window.create_text(30, 12)
+    line = window.canvas.caret_line()
+    point = _view_point(window.canvas, 30 * MM, 12 * MM)
+    assert line.p1().x() == pytest.approx(point.x(), abs=1)
+    assert line.p1().y() == pytest.approx(point.y(), abs=1)
+    assert line.length() > 0
+
+
+def test_selection_is_drawn_over_the_marked_characters(window):
+    _double_click(window.canvas, _char_point(window, 0, 1))
+    editor = window.panel("text").edit
+    cursor = editor.textCursor()
+    cursor.setPosition(1)
+    cursor.setPosition(3, cursor.MoveMode.KeepAnchor)
+    editor.setTextCursor(cursor)
+    rects = window.canvas.selection_rects()
+    assert len(rects) == 1
+    left, right = _char_point(window, 0, 1).x(), _char_point(window, 0, 3).x()
+    assert rects[0].left() == pytest.approx(left, abs=1)
+    assert rects[0].right() == pytest.approx(right, abs=1)
+
+
+def test_edited_frame_has_no_handles(window):
+    _double_click(window.canvas, _char_point(window, 0, 1))
+    handles = window.canvas.handle_points(0)
+    assert window.canvas._handle_at(handles["br"]) is None
+
+
+def test_input_methods_get_the_caret_position_on_the_label(window, qtbot):
+    _double_click(window.canvas, _char_point(window, 0, 2))
+    editor = window.panel("text").edit
+    rect = editor.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
+    caret = window.canvas.caret_line()
+    on_screen = editor.mapToGlobal(rect.topLeft())
+    expected = window.canvas.viewport().mapToGlobal(caret.p1().toPoint())
+    assert abs(on_screen.x() - expected.x()) <= 1 and abs(on_screen.y() - expected.y()) <= 1
+    assert rect.height() == pytest.approx(caret.length(), abs=2)
+
+
+def test_hidden_editor_does_not_wrap_so_home_and_end_cover_the_paragraph(qtbot):
+    win = _window(qtbot, Document("62", length_mm=40, objects=[
+        TextObject("Max Mustermann Musterstraße", size_pt=10, x_mm=2, y_mm=2)]))
+    _double_click(win.canvas, _char_point(win, 0, 20))
+    editor = win.panel("text").edit
+    QTest.keyClick(editor, Qt.Key.Key_Home)
+    assert editor.textCursor().position() == 0
+    QTest.keyClick(editor, Qt.Key.Key_End)
+    assert editor.textCursor().position() == len("Max Mustermann Musterstraße")
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index 211cb3b..7a265d6 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -1,14 +1,19 @@
 """Arbeitsfläche: Etikett in echter Größe und Form, Objekte (auswählen, ziehen, einrasten,
-an Anfassern skalieren, Text anlegen), mm-Lineale, Zoom, Längen-Anfasser."""
+an Anfassern skalieren, Text anlegen), mm-Lineale, Zoom, Längen-Anfasser.
+
+Schreibmodus (``gui.text_edit_mode``): Der bearbeitete Rahmen ist durchgezogen und ohne
+Anfasser; Schreibmarke und Markierung kommen als Lage in Druckpunkten vom Schreibmodus
+(``set_edit_marks``), die Arbeitsfläche zeichnet sie nur und meldet Mausklicks hinein."""
 from __future__ import annotations
 
 import math
 
 from PIL import Image, ImageOps
-from PySide6.QtCore import QPointF, QRectF, Qt, Signal
+from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, Signal
 from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap,
                            QTransform)
-from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView
+from PySide6.QtWidgets import (QApplication, QGraphicsPixmapItem, QGraphicsRectItem,
+                               QGraphicsScene, QGraphicsView)
 
 from .. import layout
 from ..labels import DPI, Label, format_mm, length_limits
@@ -35,6 +40,8 @@ _HANDLE_CURSORS = {
 _GUIDE_COLOR = QColor("#E53935")
 _TAPE_COLOR = QColor("#BDBDBD")    # heller als die Arbeitsfläche, in jedem Design lesbar
 TOOL_MODES = ("select", "text")   # Auswahl-Pfeil, „Text anlegen“
+_EDIT_REACH_PX = 3                # Schreibmodus: Klick so knapp neben dem Rahmen zählt noch hinein
+_SELECTION_ALPHA = 90             # Markierung: Systemfarbe zu ≈ 35 % deckend
 
 
 def to_qimage(img: Image.Image) -> QImage:
@@ -92,7 +99,10 @@ class Canvas(QGraphicsView):
     objects_moved = Signal(list, list)         # Indizes, neue Rahmen (Rect, mm) nach dem Loslassen
     object_resized = Signal(int, object, str)  # Index, neuer Rahmen (Rect, mm), Anfasser („tl“ …)
     text_requested = Signal(float, float)      # „Text anlegen“: Klick aufs Etikett (mm, Leserichtung)
-    edit_requested = Signal(int)               # Text eines Objekts bearbeiten (Doppelklick)
+    edit_requested = Signal(int, object)       # Text bearbeiten (Doppelklick): Index, Klickpunkt
+                                               # (QPointF, Druckpunkte in Leserichtung) oder None
+    edit_pressed = Signal(object, bool)        # Schreibmodus: Klick in den Rahmen (Punkt, Umschalt)
+    edit_left = Signal()                       # Schreibmodus: Klick neben den Rahmen beendet ihn
     object_clicked = Signal(int)               # Klick auf ein Objekt (auch ein schon gewähltes)
     tool_changed = Signal(str)                 # Werkzeug: "select" | "text"
 
@@ -133,6 +143,13 @@ class Canvas(QGraphicsView):
         self._handle_offset = QPointF()
         self._handle_cursor = False
         self._tool = "select"
+        self._editing: int | None = None                   # Objekt im Schreibmodus
+        self._edit_frame = QRectF()                        # Rahmen, Schreibmarke, Markierung
+        self._caret: QLineF | None = None                  # (Druckpunkte in Leserichtung)
+        self._marked: list[QRectF] = []
+        self._caret_on = True
+        self._blink = QTimer(self)
+        self._blink.timeout.connect(self._toggle_caret)
         self._apply_zoom()
 
     # --- Inhalt -----------------------------------------------------------
@@ -181,6 +198,7 @@ class Canvas(QGraphicsView):
         ratios = keep_ratio if keep_ratio is not None else [True] * len(rendered)
         self.objects = [ObjectItem(i, obj, self._pixmaps[id(obj)][1], ratio, self.sheet)
                         for i, (obj, ratio) in enumerate(zip(rendered, ratios))]
+        self._show_edit_cursor()
         self._label_rect = Rect(0, 0, width / MM, height / MM)
         self._area = area if area is not None else self._label_rect
         self._grow = grow
@@ -266,6 +284,65 @@ class Canvas(QGraphicsView):
     def _selectable(self, index: int) -> bool:
         return 0 <= index < len(self.objects)
 
+    # --- Schreibmodus -----------------------------------------------------
+    def editing(self) -> int | None:
+        """Objekt im Schreibmodus (None = keins)."""
+        return self._editing
+
+    def set_editing(self, index: int | None) -> None:
+        """Schreibmodus für ein Objekt anzeigen bzw. mit None beenden: Rahmen durchgezogen,
+        keine Anfasser, Textcursor über dem Objekt; Klicks hinein melden ``edit_pressed``."""
+        self._editing = index
+        if index is None:
+            self._edit_frame, self._caret, self._marked = QRectF(), None, []
+            self._blink.stop()
+        self._show_edit_cursor()
+        self.viewport().update()
+
+    def set_edit_marks(self, frame: QRectF, caret: QLineF | None, marked: list[QRectF]) -> None:
+        """Rahmen, Schreibmarke und Markierung des Schreibmodus (Druckpunkte in Leserichtung,
+        wie ``sheet``). Die Schreibmarke erscheint sofort und blinkt im Systemtakt."""
+        self._edit_frame, self._caret, self._marked = QRectF(frame), caret, list(marked)
+        self._caret_on = True
+        flash = QApplication.cursorFlashTime()
+        if flash > 0:
+            self._blink.start(flash // 2)
+        else:
+            self._blink.stop()                             # Blinken abgeschaltet: steht still
+        self.viewport().update()
+
+    def caret_line(self) -> QLineF:
+        """Schreibmarke in Ansichtskoordinaten (leer außerhalb des Schreibmodus)."""
+        if self._caret is None or self.sheet is None:
+            return QLineF()
+        return QLineF(self._view_point(self._caret.x1(), self._caret.y1()),
+                      self._view_point(self._caret.x2(), self._caret.y2()))
+
+    def selection_rects(self) -> list[QRectF]:
+        """Markierung im Schreibmodus in Ansichtskoordinaten (ein Rechteck je Zeile)."""
+        return [self._view_rect(rect) for rect in self._marked] if self.sheet is not None else []
+
+    def edit_frame_rect(self) -> QRectF:
+        """Rahmen des Objekts im Schreibmodus in Ansichtskoordinaten."""
+        return self._view_rect(self._edit_frame) if self.sheet is not None else QRectF()
+
+    def _view_rect(self, rect: QRectF) -> QRectF:
+        return self.viewportTransform().mapRect(self.sheet.mapRectToScene(rect))
+
+    def _in_edit_frame(self, pos: QPointF) -> bool:
+        reach = _EDIT_REACH_PX
+        return self.edit_frame_rect().adjusted(-reach, -reach, reach, reach).contains(pos)
+
+    def _show_edit_cursor(self) -> None:
+        """Textcursor über dem bearbeiteten Objekt, sonst der Verschiebe-Cursor."""
+        for item in self.objects:
+            item.setCursor(Qt.CursorShape.IBeamCursor if item.index == self._editing
+                           else Qt.CursorShape.SizeAllCursor)
+
+    def _toggle_caret(self) -> None:
+        self._caret_on = not self._caret_on
+        self.viewport().update()
+
     def nudge(self, dx_mm: float, dy_mm: float) -> None:
         """Ausgewählte Objekte um dx/dy mm verschieben (Pfeiltasten; nicht während des Ziehens)."""
         if self._selection and self._drag not in ("move", "resize"):
@@ -294,7 +371,7 @@ class Canvas(QGraphicsView):
         if item is not None:
             self.set_selection([item.index])
             self.set_tool("select")
-            self.edit_requested.emit(item.index)
+            self.edit_requested.emit(item.index, self._reading(pos))
             return
         point = self._reading(pos)
         x, y = point.x() / MM, point.y() / MM
@@ -342,8 +419,8 @@ class Canvas(QGraphicsView):
     def _handle_at(self, pos: QPointF) -> tuple[int, str] | None:
         reach = HANDLE_PX / 2 + 1
         for index in reversed(self._selection):            # zuletzt gewähltes zuerst
-            if self.objects[index].is_empty():
-                continue                                   # Platzhalter hat keine Anfasser
+            if self.objects[index].is_empty() or index == self._editing:
+                continue                                   # Platzhalter, Schreibmodus: keine Anfasser
             for key, point in self.handle_points(index).items():
                 if abs(point.x() - pos.x()) <= reach and abs(point.y() - pos.y()) <= reach:
                     return index, key
@@ -381,8 +458,9 @@ class Canvas(QGraphicsView):
         return self.handle is not None and self.itemAt(event.position().toPoint()) is self.handle
 
     def is_dragging(self) -> bool:
-        """Längen-Anfasser oder Objekt wird gerade gezogen."""
-        return self._drag is not None
+        """Längen-Anfasser oder Objekt wird gerade gezogen (Markieren im Schreibmodus zählt
+        nicht – dabei ändert sich kein Objekt)."""
+        return self._drag in ("length", "move", "resize")
 
     def snap_length(self, scene_y: float) -> float:
         """Szene-y der Unterkante → Länge in mm (Raster 0,5 mm, innerhalb der Modellgrenzen)."""
@@ -396,6 +474,15 @@ class Canvas(QGraphicsView):
         pos = event.position()
         self._press = pos
         self._moved = False
+        # Werkzeug dieses Klicks – auch wenn das Ende des Schreibmodus es gleich umstellt
+        tool = self._tool
+        if self._editing is not None:
+            if self._in_edit_frame(pos):
+                self._drag = "text"
+                shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
+                self.edit_pressed.emit(self._reading(pos), shift)
+                return
+            self.edit_left.emit()                          # danach wirkt der Klick wie sonst
         if self._on_handle(event):
             self._drag = "length"
             # Versatz zwischen Cursor und Schnittkante merken, damit der Anfasser nicht springt
@@ -403,7 +490,7 @@ class Canvas(QGraphicsView):
             return
         if self.sheet is None:
             return
-        if self._tool == "text":
+        if tool == "text":
             self._create_text(pos)
             return
         hit = self._handle_at(pos)
@@ -500,6 +587,8 @@ class Canvas(QGraphicsView):
 
     def mouseReleaseEvent(self, event) -> None:
         drag, self._drag = self._drag, None
+        if drag == "text":
+            return
         if drag == "length":
             if self._moved:
                 self.drag_finished.emit()
@@ -530,10 +619,12 @@ class Canvas(QGraphicsView):
         if self._on_handle(event):
             self.length_changed.emit(None)
             return
+        if self._editing is not None and self._in_edit_frame(event.position()):
+            return
         item = self._object_at(event.position()) if self.sheet is not None else None
         if item is not None and event.button() == Qt.MouseButton.LeftButton:
             self.set_selection([item.index])
-            self.edit_requested.emit(item.index)
+            self.edit_requested.emit(item.index, self._reading(event.position()))
             return
         super().mouseDoubleClickEvent(event)
 
@@ -546,6 +637,7 @@ class Canvas(QGraphicsView):
         painter.resetTransform()
         vw, vh = self.viewport().width(), self.viewport().height()
         self._draw_selection(painter)
+        self._draw_editing(painter)
         self._draw_guides(painter, vw, vh)
         if self.outline is not None:
             box = self.label_view_rect()
@@ -564,6 +656,8 @@ class Canvas(QGraphicsView):
         border = QPen(Qt.GlobalColor.black, 1)
         half = HANDLE_PX / 2
         for index in self._selection:
+            if index == self._editing:
+                continue                                   # Schreibmodus: _draw_editing
             painter.setPen(frame)
             painter.setBrush(Qt.BrushStyle.NoBrush)
             painter.drawRect(self.view_rect(index))
@@ -575,6 +669,27 @@ class Canvas(QGraphicsView):
                 painter.drawRect(QRectF(point.x() - half, point.y() - half, HANDLE_PX, HANDLE_PX))
         painter.setBrush(Qt.BrushStyle.NoBrush)
 
+    def _draw_editing(self, painter: QPainter) -> None:
+        """Schreibmodus: durchgezogener Rahmen ohne Anfasser, Markierung in der Systemfarbe
+        (halbtransparent über dem Druckbild), blinkende Schreibmarke (1 Bildschirmpixel)."""
+        if self._editing is None or self.sheet is None:
+            return
+        painter.setPen(QPen(Qt.GlobalColor.black, 1))
+        painter.setBrush(Qt.BrushStyle.NoBrush)
+        painter.drawRect(self.edit_frame_rect())
+        color = QColor(self.palette().highlight().color())
+        color.setAlpha(_SELECTION_ALPHA)
+        for rect in self.selection_rects():
+            painter.fillRect(rect, color)
+        if self._caret is not None and self._caret_on:
+            painter.save()
+            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)   # scharf, 1 Pixel
+            painter.setPen(QPen(Qt.GlobalColor.black, 0))
+            line = self.caret_line()
+            painter.drawLine(QPointF(round(line.x1()), round(line.y1())),
+                             QPointF(round(line.x2()), round(line.y2())))
+            painter.restore()
+
     def _draw_guides(self, painter: QPainter, vw: int, vh: int) -> None:
         """Rote Hilfslinien über die ganze Ansicht, solange ein Objekt einrastet."""
         painter.setPen(QPen(_GUIDE_COLOR, 1))
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index aed2e06..db58158 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -32,6 +32,7 @@ from .panels.text import DEFAULT_PT
 from .print_worker import PrintWorker
 from .settings_dialog import SettingsDialog
 from .symbols import SIZE, line_icon
+from .text_edit_mode import TextEditSession
 from .tools import TOOLS, Tool
 
 RENDER_DELAY_MS = 150
@@ -200,6 +201,12 @@ class MainWindow(QMainWindow):
         self._printer_timer.timeout.connect(self.refresh_printer)
         self._printer_timer.start()
 
+        # Schreibmodus direkt auf dem Etikett (Editor des Text-Panels als Eingabepuffer)
+        self.edit_session = TextEditSession(self)
+        self.panel("text").changed.connect(self.edit_session.content_changed)
+        # Esc und Klick neben den Rahmen beenden ihn; ein leerer Rahmen entfällt dabei
+        for signal in (self.edit_session.end_requested, self.canvas.edit_left):
+            signal.connect(lambda: self.finish_editing(drop_empty=True))
         self.render_now()
         self.canvas.selection_changed.connect(self._on_selection)
         self.panel("text").frame_edited.connect(self._edit_frame)
@@ -239,8 +246,8 @@ class MainWindow(QMainWindow):
         handlers = {"edit.delete": self.delete_selected, "edit.select_all": self.canvas.select_all,
                     "edit.cut": self.cut_selected, "edit.copy": self.copy_selected,
                     "edit.paste": self.paste, "edit.duplicate": self.duplicate_selected,
-                    "tool.select": lambda: self.canvas.set_tool("select"),
-                    "tool.text": lambda: self.canvas.set_tool("text")}
+                    "tool.select": lambda: self._choose_tool("select"),
+                    "tool.text": lambda: self._choose_tool("text")}
         for key, handler in handlers.items():
             self.shortcut_actions[key].triggered.connect(lambda _=False, h=handler: h())
             self.canvas.addAction(self.shortcut_actions[key])
@@ -292,9 +299,17 @@ class MainWindow(QMainWindow):
         self.tool_actions[key].setChecked(True)
         self.panels.setCurrentWidget(self.panel(key))
 
+    def _choose_tool(self, tool: str) -> None:
+        """Auswahl-Pfeil oder „Text anlegen“ (Bearbeitungsleiste, Kürzel) – beendet den
+        Schreibmodus."""
+        self.finish_editing()
+        self.canvas.set_tool(tool)
+
     def _tool_triggered(self, key: str) -> None:
         """Werkzeug-Reiter: Panel zeigen; Text ohne Auswahl heißt „Text anlegen“, jedes
-        andere Panel arbeitet mit dem Auswahl-Pfeil."""
+        andere Panel arbeitet mit dem Auswahl-Pfeil (und beendet den Schreibmodus)."""
+        if key != "text":
+            self.finish_editing()
         self.panels.setCurrentWidget(self.panel(key))
         if key == "text":
             self._sync_tool()
@@ -316,6 +331,8 @@ class MainWindow(QMainWindow):
         if self._arranging:                         # Anlegen, Umnummerieren: nur mitführen
             self._follow_selection(indices)
             return
+        if self.edit_session.active and indices != [self.edit_session.index]:
+            self.finish_editing()                   # leere Rahmen entfallen gleich hier unten
         if not self._restoring:
             indices = self._drop_empty_frames(indices)
         self._follow_selection(indices)
@@ -429,6 +446,7 @@ class MainWindow(QMainWindow):
                                  grow=growing_axis(self.doc))
         self.panel("layout").set_growing(growing_axis(self.doc))
         self._update_frame()
+        self.edit_session.update_marks()            # Schreibmarke zum neuen Zeilensatz
 
     def _drop_stale_view(self) -> None:
         """Nach einem Renderfehler: Objektbilder, die nicht mehr zu ``doc.objects`` passen
@@ -559,10 +577,11 @@ class MainWindow(QMainWindow):
         self._commit()
 
     def create_text(self, x_mm: float, y_mm: float) -> None:
-        """Neuer leerer Textrahmen an x/y (mm, Leserichtung), ausgewählt, Schreibmarke ins Textfeld.
+        """Neuer leerer Textrahmen an x/y (mm, Leserichtung), ausgewählt, gleich im Schreibmodus.
 
         Schrift aus den Einstellungen (automatische Größe → 19 pt). Andere leere Texte sind
         unsichtbar und drucken nicht – sie entfallen dabei."""
+        self.finish_editing()
         self._structure_changing()
         self._commit()
         family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
@@ -581,15 +600,36 @@ class MainWindow(QMainWindow):
         self._commit()
         self.edit_text(index)
 
-    def edit_text(self, index: int) -> None:
-        """Text eines Objekts bearbeiten: auswählen, Text-Panel zeigen, Schreibmarke hinein."""
-        if index not in self.canvas.selection():
+    def edit_text(self, index: int, point=None) -> None:
+        """Schreibmodus für ein Objekt: auswählen, Text-Panel zeigen, Schreibmarke an
+        ``point`` (QPointF, Druckpunkte in Leserichtung – z. B. Doppelklick) bzw. ans Ende."""
+        if self.edit_session.active:
+            if self.edit_session.index == index:
+                return
+            self.finish_editing()
+        if not self._valid(index):
+            return
+        if self.canvas.selection() != [index]:
             self.canvas.set_selection([index])
         self._show_tool("text")
-        self.panel("text").edit.setFocus()
+        if self._timer.isActive():
+            self.render_now()                       # Klick trifft den aktuellen Zeilensatz
+        self.edit_session.start(index, point)
+
+    def finish_editing(self, drop_empty: bool = False) -> None:
+        """Schreibmodus beenden (Esc, Klick daneben, anderes Werkzeug, Befehl auf der Auswahl).
+        ``drop_empty``: ein leer gebliebener Rahmen entfällt sofort (Esc, Klick daneben) –
+        sonst wie bisher, sobald er die Auswahl verlässt."""
+        index = self.edit_session.end()
+        if index is None:
+            return
+        if (drop_empty and self._valid(index) and self.doc.objects[index].positioned
+                and self.doc.objects[index].is_empty()):
+            self.canvas.set_selection([])           # leerer Rahmen entfällt (_on_selection)
 
     def delete_selected(self) -> None:
         """Ausgewählte Objekte löschen (auch das letzte – das Etikett ist dann leer)."""
+        self.finish_editing()
         indices = self.canvas.selection()
         if not indices:
             return
@@ -603,6 +643,7 @@ class MainWindow(QMainWindow):
 
     def _edit_frame(self, key: str, value: float) -> None:
         """Zahl im Bereich „Position“ geändert: Objekt verschieben bzw. Rahmen ändern."""
+        self.finish_editing()
         index = self.panel("text").index
         if index is None or not self._valid(index):
             return
@@ -639,6 +680,7 @@ class MainWindow(QMainWindow):
         """Gewählte Objekte durch ``change(objekte, gerendert)`` ersetzen – ein Schritt.
 
         ``change`` läuft nach dem Rendern: Rahmen und ``self._area`` sind aktuell."""
+        self.finish_editing()
         if self._timer.isActive():
             self.render_now()                   # z. B. eben Getipptes: aktuelle Rahmen
         # leere Rahmen sind unsichtbar und drucken nicht: sie nehmen an Layout-Befehlen nicht teil
@@ -655,6 +697,7 @@ class MainWindow(QMainWindow):
 
     def reorder_selected(self, step: int) -> None:
         """Auswahl einen Platz nach vorne (1) bzw. hinten (−1); die Auswahl wandert mit."""
+        self.finish_editing()
         indices = self.canvas.selection()
         if not indices:
             return
@@ -698,6 +741,7 @@ class MainWindow(QMainWindow):
         return move(obj, object_rect(rendered), rendered)
 
     def _insert(self, objects: list[TextObject]) -> None:
+        self.finish_editing()
         self._structure_changing()
         self._commit()
         start = len(self.doc.objects)
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index 92ab462..9e0e8a2 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -3,6 +3,10 @@
 Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
 Formatierung auf den ganzen Text; sonst nur auf die Markierung. Bereich „Position“: Lage
 und (mit fester Rahmengröße) Größe des Rahmens in mm.
+
+Geschrieben wird direkt auf dem Etikett (``gui.text_edit_mode``): Der Editor ``edit`` ist
+dafür ein unsichtbarer Eingabepuffer (Kind des Panels, Größe 0, nicht im Layout) – er behält
+im Schreibmodus den Tastaturfokus, damit tote Tasten, Compose und Eingabemethoden wirken.
 """
 from __future__ import annotations
 
@@ -38,9 +42,18 @@ class PlainPasteEdit(QTextEdit):
 
     focus_left = Signal()            # Tippen ist abgeschlossen (ein Schritt für Rückgängig)
 
-    def __init__(self):
-        super().__init__()
+    def __init__(self, parent=None):
+        super().__init__(parent)
         self.setTabChangesFocus(True)      # Tab springt weiter, statt "\t" einzufügen
+        # eine Zeile je Absatz wie auf dem Etikett: Pos1/Ende gelten für den ganzen Absatz
+        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
+        # Schreibmodus: Lage der Schreibmarke auf dem Etikett für Eingabemethoden (→ QRect)
+        self.caret_rect = None
+
+    def inputMethodQuery(self, query):
+        if query == Qt.InputMethodQuery.ImCursorRectangle and self.caret_rect is not None:
+            return self.caret_rect()           # Kandidatenfenster an der Schreibmarke
+        return super().inputMethodQuery(query)
 
     def keyPressEvent(self, event) -> None:
         if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
@@ -97,12 +110,14 @@ class TextPanel(Panel):
         self.hint.setWordWrap(True)
         self.layout_.addWidget(self.hint)
 
-        self.section("Inhalt")
-        self.edit = PlainPasteEdit()
-        self.edit.setPlaceholderText("Text eingeben …")
-        # Absätze ohne eigene Ausrichtung stehen zentriert – wie bisher in labelwerk
-        self.edit.document().setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignHCenter))
-        self.layout_.addWidget(self.edit)
+        # unsichtbarer Eingabepuffer des Schreibmodus: fokussierbar, aber ohne Fläche
+        self.edit = PlainPasteEdit(self)
+        self.edit.setFixedSize(0, 0)
+        # Absätze ohne eigene Ausrichtung stehen zentriert – wie bisher in labelwerk; kein
+        # Umbruch im Editor (Größe 0), damit Pos1/Ende und Zeilen den Absätzen entsprechen
+        option = QTextOption(Qt.AlignmentFlag.AlignHCenter)
+        option.setWrapMode(QTextOption.WrapMode.NoWrap)
+        self.edit.document().setDefaultTextOption(option)
 
         self.section("Schrift")
         self.family = QFontComboBox()
diff --git a/src/labelwerk/gui/text_edit_mode.py b/src/labelwerk/gui/text_edit_mode.py
new file mode 100644
index 0000000..a96ea18
--- /dev/null
+++ b/src/labelwerk/gui/text_edit_mode.py
@@ -0,0 +1,189 @@
+"""Schreibmodus: Text direkt im Rahmen auf dem Etikett schreiben und markieren.
+
+Der Editor des Text-Panels bleibt als unsichtbarer Eingabepuffer erhalten und hat im
+Schreibmodus den Tastaturfokus; die Arbeitsfläche zeigt weiter das echte Objektbild aus dem
+Kern. Schreibmarke, Markierung und Mausklicks rechnet ``TextEditSession`` über den
+Zeilensatz desselben Renders (``RenderedObject.layout``) um – Vorschau = Druck gilt auch
+beim Tippen. Positionen: Editor in UTF-16-Einheiten, Zeilensatz in Zeichen
+(``render.to_utf16``/``from_utf16``).
+
+Start und Ende samt Rückgängig-Schritt steuert das Hauptfenster (``MainWindow.edit_text``,
+``finish_editing``); die Sitzung meldet nur, dass sie enden soll (``end_requested``).
+"""
+from __future__ import annotations
+
+from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRect, QRectF, Qt, Signal
+from PySide6.QtGui import QGuiApplication, QTextCursor, QTextDocument
+
+from .. import layout
+from ..render import PT, RenderedObject, TextLayout, from_utf16, to_utf16
+
+
+class TextEditSession(QObject):
+    """Schreibmodus für höchstens ein Textobjekt (``index``) des Hauptfensters."""
+
+    end_requested = Signal()          # Esc: Schreibmodus soll enden
+
+    def __init__(self, window):
+        super().__init__(window)
+        self._window = window
+        self._canvas = window.canvas
+        self._editor = window.panel("text").edit
+        self.index: int | None = None
+        self._canvas.edit_pressed.connect(self._press)
+        for signal in (self._editor.cursorPositionChanged, self._editor.selectionChanged):
+            signal.connect(self.update_marks)
+        self._editor.installEventFilter(self)
+
+    @property
+    def active(self) -> bool:
+        return self.index is not None
+
+    # --- Start / Ende -------------------------------------------------------
+    def start(self, index: int, point: QPointF | None = None) -> None:
+        """Schreibmodus für Objekt ``index`` (gewählt, im Text-Panel): Editor neu aus dem
+        Modell, Tastaturfokus hinein, Schreibmarke an ``point`` (Druckpunkte in Leserichtung,
+        z. B. Doppelklick) oder ans Textende."""
+        self._window.panel("text").refresh()      # Editor = Modell, eigenes Rückgängig ab hier
+        self.index = index
+        self._editor.caret_rect = self._caret_rect
+        self._canvas.set_editing(index)
+        self._canvas.setFocusProxy(self._editor)   # Klick auf die Fläche: Fokus bleibt im Editor
+        self._editor.setFocus()
+        cursor = self._editor.textCursor()
+        position = self._position_at(point) if point is not None else None
+        if position is None:
+            cursor.movePosition(QTextCursor.MoveOperation.End)
+        else:
+            cursor.setPosition(position)
+        self._editor.setTextCursor(cursor)
+        self.update_marks()
+
+    def end(self) -> int | None:
+        """Schreibmodus beenden (Markierung entfällt, Objekt-Kürzel gelten wieder); zurück
+        kommt der Index des bearbeiteten Objekts."""
+        index, self.index = self.index, None
+        if index is None:
+            return None
+        cursor = self._editor.textCursor()
+        cursor.clearSelection()                    # Formatieren wirkt wieder auf den ganzen Rahmen
+        self._editor.setTextCursor(cursor)
+        self._editor.caret_rect = None
+        self._canvas.set_editing(None)
+        self._canvas.setFocusProxy(None)
+        if self._editor.hasFocus():
+            self._canvas.setFocus()
+        return index
+
+    def content_changed(self) -> None:
+        """Text oder Format geändert: sofort neu rendern, damit Schreibmarke und Bild zum
+        selben Zeilensatz gehören."""
+        if self.active:
+            self._window.render_now()
+
+    # --- Anzeige ------------------------------------------------------------
+    def update_marks(self) -> None:
+        """Schreibmarke, Markierung und Rahmen aus Editor und aktuellem Zeilensatz an die
+        Arbeitsfläche geben. Passt der Zeilensatz (noch) nicht zum Editor – das Rendern
+        folgt gleich bzw. ist gescheitert –, bleibt die bisherige Anzeige."""
+        current = self._current()
+        if current is None:
+            return
+        rendered, text_layout, text, rotation = current
+        cursor = self._editor.textCursor()
+        pos = from_utf16(text, cursor.position())
+        anchor = from_utf16(text, cursor.anchor())
+        x, top, height = text_layout.caret(pos)
+        caret = QLineF(_label(rendered, rotation, x, top),
+                       _label(rendered, rotation, x, top + height))
+        marked = ([_label_rect(rendered, rotation, *rect)
+                   for rect in text_layout.selection_rects(anchor, pos)] if anchor != pos else [])
+        self._canvas.set_edit_marks(self._frame(rendered, rotation, x, top, height),
+                                    caret, marked)
+        if self._editor.hasFocus():
+            QGuiApplication.inputMethod().update(Qt.InputMethodQuery.ImCursorRectangle)
+
+    def _caret_rect(self) -> QRect:
+        """Schreibmarke auf der Arbeitsfläche in Koordinaten des (unsichtbaren) Editors."""
+        line = self._canvas.caret_line()
+        rect = QRectF(line.p1(), line.p2()).normalized()
+        top_left = self._editor.mapFromGlobal(
+            self._canvas.viewport().mapToGlobal(rect.topLeft().toPoint()))
+        return QRect(top_left.x(), top_left.y(), max(1, round(rect.width())),
+                     max(1, round(rect.height())))
+
+    def _frame(self, rendered: RenderedObject, rotation: int, x: float, top: float,
+               height: float) -> QRectF:
+        """Rahmen des Objekts; ein leerer Text bekommt einen Platzhalter (halbe Zeile breit)
+        um die Schreibmarke – je nach Textposition rechts, mittig oder links von ihr."""
+        if rendered.w and rendered.h:
+            return QRectF(rendered.x, rendered.y, rendered.w, rendered.h)
+        width = rendered.base_pt * PT / 2
+        obj = self._window.doc.objects[self.index]
+        align = obj.paragraphs[0].align if obj.paragraphs else "left"
+        left = x - {"center": width / 2, "right": width}.get(align, 0.0)
+        return _label_rect(rendered, rotation, left, top, width, height)
+
+    def _current(self) -> tuple[RenderedObject, TextLayout, str, int] | None:
+        """Gerendertes Objekt, sein Zeilensatz, Text des Editors und Drehung – nur wenn der
+        Zeilensatz zum Text im Editor passt."""
+        window, index = self._window, self.index
+        if index is None or not 0 <= index < min(len(window.rendered), len(window.doc.objects)):
+            return None
+        rendered = window.rendered[index]
+        text = editor_text(self._editor.document())
+        if rendered.layout is None or "\n".join(rendered.layout.texts) != text:
+            return None
+        return rendered, rendered.layout, text, window.doc.objects[index].rotation
+
+    # --- Maus und Tastatur ----------------------------------------------------
+    def _position_at(self, point: QPointF) -> int | None:
+        """Editor-Position (UTF-16) der Zeichengrenze am Punkt (Druckpunkte in Leserichtung)."""
+        current = self._current()
+        if current is None:
+            return None
+        rendered, text_layout, text, rotation = current
+        u, v = layout.to_object((point.x(), point.y()), rendered, rotation)
+        return to_utf16(text, text_layout.hit(u, v))
+
+    def _press(self, point: QPointF, extend: bool) -> None:
+        """Klick in den Rahmen: Schreibmarke dorthin (mit Umschalt: Markierung bis dorthin)."""
+        position = self._position_at(point)
+        if position is None:
+            return
+        cursor = self._editor.textCursor()
+        mode = QTextCursor.MoveMode.KeepAnchor if extend else QTextCursor.MoveMode.MoveAnchor
+        cursor.setPosition(position, mode)
+        self._editor.setTextCursor(cursor)
+        self._editor.setFocus()
+
+    def eventFilter(self, watched, event) -> bool:
+        if (self.active and watched is self._editor and event.type() == QEvent.Type.KeyPress
+                and event.key() == Qt.Key.Key_Escape):
+            self.end_requested.emit()
+            return True
+        return super().eventFilter(watched, event)
+
+
+def editor_text(document: QTextDocument) -> str:
+    """Text des Editors, wie ihn das Modell bekommt (``TextPanel.to_text_object``): Absätze
+    mit „\\n“, Zeilentrenner U+2028 als Absatz, Tab als Leerzeichen – je ein Zeichen, die
+    Positionen bleiben also gleich."""
+    lines = []
+    block = document.begin()
+    while block.isValid():
+        lines.append(block.text().replace("\t", " ").replace(" ", "\n"))
+        block = block.next()
+    return "\n".join(lines)
+
+
+def _label(rendered: RenderedObject, rotation: int, u: float, v: float) -> QPointF:
+    """Objektkoordinaten (ungedreht) → Punkt auf dem Etikett (Druckpunkte in Leserichtung)."""
+    return QPointF(*layout.from_object((u, v), rendered, rotation))
+
+
+def _label_rect(rendered: RenderedObject, rotation: int, u: float, v: float, w: float,
+                h: float) -> QRectF:
+    """Rechteck in Objektkoordinaten → Rechteck auf dem Etikett (Drehung um 90°-Schritte)."""
+    return QRectF(_label(rendered, rotation, u, v),
+                  _label(rendered, rotation, u + w, v + h)).normalized()
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `942 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/canvas.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/text_edit_mode.py tests/gui/test_gui_edit_mode.py
git commit -m "GUI: Schreibmodus direkt auf dem Etikett – versteckter Editor, Schreibmarke, Markierung

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: GUI – Schreibmodus: Markieren, Tastatur, ein Rückgängig-Schritt, Rahmen wächst an der richtigen Kante, Kürzel-Bereich

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-17-direkt-schreiben-design.md`
- Modify: `src/labelwerk/gui/actions.py`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/gui/text_edit_mode.py`
- Modify: `src/labelwerk/shortcuts.py`
- Modify: `tests/gui/test_gui_edit_mode.py`
- Modify: `tests/gui/test_gui_editbar.py`
- Modify: `tests/gui/test_gui_settings.py`
- Modify: `tests/gui/test_gui_textframe.py`
- Modify: `tests/test_settings.py`
- Modify: `tests/test_shortcuts.py`

**Interfaces / Produces:** Ziehen/Doppelklick/Umschalt+Klick markieren; Editor-Tasten im Schreibmodus, Tab wird geschluckt, Fokus bleibt im Editor (Editor und Panel-Scrollbereich NoFocus); eine Bearbeitung = ein Rückgängig-Schritt (Strg+Z wie Knopf, fällt in den Dokumentverlauf durch); leerer neuer Rahmen entfällt auf jedem Ausgang; Kürzel-Bereich `edit` („Schreibmodus“) ersetzt `text`, feste Aktion `text.end_edit` (Esc), `Action.fixed`; neue Texte linksbündig ab Klickpunkt; README/CLAUDE.md/Spec aktualisiert.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_edit_mode.py b/tests/gui/test_gui_edit_mode.py
index 0ca3ffe..c8d3728 100644
--- a/tests/gui/test_gui_edit_mode.py
+++ b/tests/gui/test_gui_edit_mode.py
@@ -3,11 +3,12 @@ import pytest
 from PySide6.QtCore import QPointF, Qt
 from PySide6.QtGui import QMouseEvent
 from PySide6.QtTest import QTest
-from PySide6.QtWidgets import QApplication
+from PySide6.QtWidgets import QApplication, QFontComboBox
 
 from labelwerk import layout
 from labelwerk.document import Document, TextObject
 from labelwerk.gui.canvas import MM
+from labelwerk.render import to_utf16
 from labelwerk.gui.main_window import MainWindow
 from labelwerk.settings import Settings
 
@@ -248,3 +249,416 @@ def test_hidden_editor_does_not_wrap_so_home_and_end_cover_the_paragraph(qtbot):
     assert editor.textCursor().position() == 0
     QTest.keyClick(editor, Qt.Key.Key_End)
     assert editor.textCursor().position() == len("Max Mustermann Musterstraße")
+
+
+# --- Bedienung: Maus ------------------------------------------------------------------
+CTRL = Qt.KeyboardModifier.ControlModifier
+
+
+def _plain(text, x_mm, y_mm, align="center", rotation=0, size_pt=14):
+    obj = TextObject.plain(text, size_pt=size_pt, align=align, bold=False)
+    obj.x_mm, obj.y_mm, obj.rotation = x_mm, y_mm, rotation
+    return obj
+
+
+def _plain_doc(*objects):
+    return Document("62", length_mm=60, objects=list(objects) or [
+        _plain("Max Mustermann", 4, 4), _plain("Zwei", 4, 24)])
+
+
+def _drag(canvas, start, end, modifiers=NO_MOD):
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, modifiers)
+
+
+def _editing(qtbot, doc=None, index=0, pos=1):
+    """Fenster mit Objekt ``index`` im Schreibmodus, Schreibmarke vor Zeichen ``pos``."""
+    win = _window(qtbot, doc if doc is not None else _plain_doc())
+    _double_click(win.canvas, _char_point(win, index, pos))
+    editor = win.panel("text").edit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    assert _session(win).index == index
+    return win, editor
+
+
+def _selection(editor):
+    cursor = editor.textCursor()
+    return cursor.selectionStart(), cursor.selectionEnd()
+
+
+def test_drag_inside_frame_selects_text_and_bold_formats_only_the_selection(qtbot):
+    win, editor = _editing(qtbot)
+    before = (win.doc.objects[0].x_mm, win.doc.objects[0].y_mm)
+    _drag(win.canvas, _char_point(win, 0, 4), _char_point(win, 0, 14))
+    assert _selection(editor) == (4, 14)
+    assert (win.doc.objects[0].x_mm, win.doc.objects[0].y_mm) == before   # nicht verschoben
+    QTest.keyClick(editor, Qt.Key.Key_B, CTRL)
+    spans = win.doc.objects[0].paragraphs[0].spans
+    assert [(s.text, s.bold) for s in spans] == [("Max ", False), ("Mustermann", True)]
+    assert _session(win).active
+
+
+def test_double_click_in_edit_mode_selects_a_word(qtbot):
+    win, editor = _editing(qtbot)
+    _double_click(win.canvas, _char_point(win, 0, 7))
+    assert editor.textCursor().selectedText() == "Mustermann"
+    assert _session(win).active
+
+
+def test_shift_click_extends_the_selection(qtbot):
+    win, editor = _editing(qtbot, pos=2)
+    _click(win.canvas, _char_point(win, 0, 9), SHIFT)
+    assert _selection(editor) == (2, 9)
+
+
+# --- Bedienung: Tastatur --------------------------------------------------------------
+def test_arrows_move_the_caret_in_edit_mode_and_the_object_outside(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    x = win.doc.objects[0].x_mm
+    QTest.keyClick(editor, Qt.Key.Key_Left)
+    assert editor.textCursor().position() == 2 and win.doc.objects[0].x_mm == x
+    QTest.keyClick(editor, Qt.Key.Key_Right, SHIFT)
+    assert _selection(editor) == (2, 3)
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    qtbot.waitUntil(win.canvas.hasFocus, timeout=1000)
+    QTest.keyClick(win.canvas, Qt.Key.Key_Left)
+    assert win.doc.objects[0].x_mm == pytest.approx(x - 0.1)
+
+
+def test_up_and_down_follow_the_lines_on_the_label(qtbot):
+    win, editor = _editing(qtbot, _plain_doc(_plain("iiii\nWWWW", 4, 4, align="left")), pos=1)
+    QTest.keyClick(editor, Qt.Key.Key_Down)
+    text_layout = win.rendered[0].layout
+    second = text_layout.lines[1]
+    expected = text_layout.hit(text_layout.caret(1)[0], second.top + second.height / 2)
+    assert editor.textCursor().position() == expected
+    QTest.keyClick(editor, Qt.Key.Key_Up, SHIFT)
+    assert _selection(editor) == (1, expected)
+    QTest.keyClick(editor, Qt.Key.Key_Up)
+    assert editor.textCursor().position() == 0                  # über der ersten Zeile: Anfang
+
+
+def test_home_end_and_enter(qtbot):
+    win, editor = _editing(qtbot, pos=5)
+    QTest.keyClick(editor, Qt.Key.Key_Home)
+    assert editor.textCursor().position() == 0
+    QTest.keyClick(editor, Qt.Key.Key_End)
+    assert editor.textCursor().position() == len("Max Mustermann")
+    QTest.keyClick(editor, Qt.Key.Key_Return)
+    QTest.keyClicks(editor, "x")
+    assert win.doc.objects[0].text == "Max Mustermann\nx"
+
+
+def test_ctrl_a_selects_the_whole_text_of_the_frame_only(qtbot):
+    win, editor = _editing(qtbot)
+    QTest.keyClick(editor, Qt.Key.Key_A, CTRL)
+    assert _selection(editor) == (0, len("Max Mustermann"))
+    assert win.canvas.selection() == [0] and _session(win).active
+
+
+def test_delete_and_backspace_delete_characters_not_the_object(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    QTest.keyClick(editor, Qt.Key.Key_Delete)
+    QTest.keyClick(editor, Qt.Key.Key_Backspace)
+    assert [o.text for o in win.doc.objects] == ["MaMustermann", "Zwei"]
+
+
+def test_copy_and_paste_text_in_edit_mode(qtbot):
+    win, editor = _editing(qtbot)
+    _double_click(win.canvas, _char_point(win, 0, 1))      # Wort „Max“
+    QTest.keyClick(editor, Qt.Key.Key_C, CTRL)
+    QTest.keyClick(editor, Qt.Key.Key_End)
+    QTest.keyClick(editor, Qt.Key.Key_V, CTRL)
+    assert [o.text for o in win.doc.objects] == ["Max MustermannMax", "Zwei"]
+
+
+def test_edit_bar_cut_and_paste_work_on_text_in_edit_mode(qtbot):
+    win, editor = _editing(qtbot)
+    _double_click(win.canvas, _char_point(win, 0, 1))
+    win.shortcut_actions["edit.cut"].trigger()
+    assert win.doc.objects[0].text == " Mustermann" and len(win.doc.objects) == 2
+    win.shortcut_actions["edit.paste"].trigger()
+    assert win.doc.objects[0].text == "Max Mustermann" and len(win.doc.objects) == 2
+
+
+def test_end_edit_is_a_fixed_action_of_edit_mode(window):
+    action = window.shortcut_actions["text.end_edit"]
+    assert action in window.panel("text").actions()
+    assert action.shortcut().toString() == "Esc"
+    assert not action.isEnabled()                              # nur im Schreibmodus
+    _double_click(window.canvas, _char_point(window, 0, 1))
+    assert action.isEnabled()
+    action.trigger()
+    assert not _session(window).active
+
+
+# --- Formatieren ----------------------------------------------------------------------
+def test_format_without_selection_in_edit_mode_applies_to_typing_only(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    win.panel("text").bold.click()
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)             # Fokus zurück an die Schreibmarke
+    QTest.keyClicks(editor, "X")
+    spans = win.doc.objects[0].paragraphs[0].spans
+    assert [(s.text, s.bold) for s in spans] == [("Max", False), ("X", True),
+                                                 (" Mustermann", False)]
+
+
+def test_format_outside_edit_mode_applies_to_the_whole_frame(window):
+    window.doc.objects[0] = _plain("Max Mustermann", 4, 4)
+    window.render_now()
+    window.canvas.set_selection([0])
+    window.panel("text").bold.click()
+    assert all(s.bold for s in window.doc.objects[0].paragraphs[0].spans)
+
+
+def test_size_for_typing_scales_the_caret(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    height = win.canvas.caret_line().length()
+    win.panel("text").set_size_pt(28)                         # 14 → 28 pt, nur fürs Weitertippen
+    assert win.doc.objects[0].text == "Max Mustermann"
+    assert win.canvas.caret_line().length() == pytest.approx(2 * height, abs=2)
+
+
+# --- Rückgängig -----------------------------------------------------------------------
+def test_one_finished_edit_is_one_undo_step(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    QTest.keyClicks(editor, "XY")
+    QTest.keyClick(editor, Qt.Key.Key_Backspace)
+    _double_click(win.canvas, _char_point(win, 0, 6))
+    QTest.keyClick(editor, Qt.Key.Key_I, CTRL)
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    assert win.doc.objects[0].text == "MaxX Mustermann"
+    win.shortcut_actions["edit.undo"].trigger()
+    assert win.doc.objects[0] == _plain_doc().objects[0]
+    win.shortcut_actions["edit.redo"].trigger()
+    assert win.doc.objects[0].text == "MaxX Mustermann"
+
+
+def test_ctrl_z_while_editing_is_the_editors_undo(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    QTest.keyClicks(editor, "X")
+    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
+    assert win.doc.objects[0].text == "Max Mustermann" and _session(win).active
+    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL | SHIFT)
+    assert win.doc.objects[0].text == "MaxX Mustermann"
+    win.shortcut_actions["edit.undo"].trigger()               # Knopf: ebenfalls im Editor
+    assert win.doc.objects[0].text == "Max Mustermann" and _session(win).active
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    assert not win.shortcut_actions["edit.undo"].isEnabled()  # nichts geändert: kein Schritt
+
+
+def test_new_frame_and_its_text_are_one_undo_step(window, qtbot):
+    window.shortcut_actions["tool.text"].trigger()
+    _click(window.canvas, _view_point(window.canvas, 30 * MM, 12 * MM))
+    editor = window.panel("text").edit
+    QTest.keyClicks(editor, "Neu")
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    window.shortcut_actions["edit.undo"].trigger()
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
+
+
+# --- Rahmen wächst --------------------------------------------------------------------
+def _anchor(window, index):
+    obj, rendered = window.doc.objects[index], window.rendered[index]
+    return layout.from_object(rendered.layout.anchor(layout.anchor_align(obj)), rendered,
+                              obj.rotation)
+
+
+@pytest.mark.parametrize("align, rotation", [("left", 0), ("right", 0), ("center", 0),
+                                             ("right", 90), ("left", 270)])
+def test_frame_grows_at_the_edge_of_the_alignment(qtbot, align, rotation):
+    doc = _plain_doc(_plain("Eins", 20, 10, align=align, rotation=rotation))
+    win, editor = _editing(qtbot, doc, pos=2)
+    before = _anchor(win, 0)
+    QTest.keyClick(editor, Qt.Key.Key_End)
+    QTest.keyClicks(editor, "Wjg")
+    after = _anchor(win, 0)
+    assert win.rendered[0].layout.texts == ["EinsWjg"]
+    assert after == pytest.approx(before, abs=1)              # ±1 Druckpunkt
+    QTest.keyClick(editor, Qt.Key.Key_Backspace)
+    assert _anchor(win, 0) == pytest.approx(before, abs=1)
+
+
+def test_unpositioned_text_stays_centred_while_typing(qtbot):
+    doc = Document("62", length_mm=40, objects=[TextObject.plain("Mitte", size_pt=14)])
+    win, editor = _editing(qtbot, doc, pos=2)
+    QTest.keyClicks(editor, "WWW")
+    assert not win.doc.objects[0].positioned
+
+
+def test_fixed_frame_keeps_its_frame_while_typing(qtbot):
+    obj = _plain("Fest", 4, 4)
+    obj.fit, obj.w_mm, obj.h_mm = True, 30.0, 10.0
+    win, editor = _editing(qtbot, _plain_doc(obj), pos=2)
+    QTest.keyClicks(editor, "WWW")
+    after = win.doc.objects[0]
+    assert (after.x_mm, after.y_mm, after.w_mm, after.h_mm) == (4, 4, 30.0, 10.0)
+
+
+def test_editor_keeps_focus_for_input_methods(qtbot):
+    win, editor = _editing(qtbot)
+    assert QApplication.focusWidget() is editor
+    assert editor.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
+    _click(win.canvas, _char_point(win, 0, 5))
+    assert QApplication.focusWidget() is editor
+    win.panel("text").italic.click()
+    assert QApplication.focusWidget() is editor
+
+
+
+# --- Neuer Text: linksbündig ab dem Klickpunkt ----------------------------------------
+def test_new_text_starts_left_aligned_at_the_click_point_and_grows_to_the_right(window, qtbot):
+    window.shortcut_actions["tool.text"].trigger()
+    click = _view_point(window.canvas, 30 * MM, 12 * MM)
+    _click(window.canvas, click)
+    dot = window.canvas.px_per_mm() / MM                   # Bildschirmpixel je Druckpunkt
+    line = window.canvas.caret_line()
+    assert line.p1().x() == pytest.approx(click.x(), abs=dot)
+    assert line.p1().y() == pytest.approx(click.y(), abs=dot)
+    editor = window.panel("text").edit
+    QTest.keyClicks(editor, "Neu")
+    obj, rendered = window.doc.objects[2], window.rendered[2]
+    assert [p.align for p in obj.paragraphs] == ["left"]
+    x, y = layout.from_object(rendered.layout.anchor("left"), rendered, 0)
+    assert (x, y) == pytest.approx((30 * MM, 12 * MM), abs=1)
+    assert rendered.x >= 30 * MM - 2 and rendered.w > 0          # wächst nach rechts
+
+
+# --- Fokus bleibt im Schreibmodus ---------------------------------------------------------
+@pytest.mark.parametrize("key", [Qt.Key.Key_Tab, Qt.Key.Key_Backtab])
+def test_tab_keeps_focus_in_the_text(qtbot, key):
+    win, editor = _editing(qtbot, pos=3)
+    QTest.keyClick(QApplication.focusWidget(), key)
+    assert QApplication.focusWidget() is editor
+    QTest.keyClicks(QApplication.focusWidget(), "x")
+    assert win.doc.objects[0].text == "Maxx Mustermann"           # Tab fügt nichts ein
+    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
+    assert not _session(win).active
+
+
+def test_click_on_panel_background_keeps_focus_in_the_text(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    panel = win.panel("text")
+    QTest.mouseClick(panel, LEFT, NO_MOD, panel.rect().bottomLeft() + QPointF(5, -5).toPoint())
+    assert QApplication.focusWidget() is editor
+    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
+    assert not _session(win).active
+
+
+def test_caret_is_hidden_while_the_text_has_no_focus(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    assert win.canvas.caret_shown()
+    size = win.panel("text").size.lineEdit()
+    size.setFocus()
+    qtbot.waitUntil(size.hasFocus, timeout=1000)
+    assert not win.canvas.caret_shown() and _session(win).active
+    editor.setFocus()
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    assert win.canvas.caret_shown()
+
+
+def test_hidden_editor_is_not_reachable_by_tab_outside_edit_mode(window, qtbot):
+    window.canvas.set_selection([0])
+    editor = window.panel("text").edit
+    assert editor.focusPolicy() == Qt.FocusPolicy.NoFocus
+    family = window.panel("text").family
+    family.setFocus()
+    qtbot.waitUntil(family.hasFocus, timeout=1000)
+    QTest.keyClick(family, Qt.Key.Key_Backtab)
+    assert QApplication.focusWidget() is not editor
+    QTest.keyClicks(QApplication.focusWidget(), "zz")
+    assert window.doc.objects[0].text == "Eins"
+
+
+def test_keyboard_in_font_box_while_editing_stays_in_the_box(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    family = win.panel("text").family
+    family.setFocus()
+    qtbot.waitUntil(family.hasFocus, timeout=1000)
+    start = family.currentIndex()
+    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)
+    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)
+    assert family.currentIndex() == start + 2
+    assert editor.textCursor().position() == 3 and not editor.hasFocus()
+    family.showPopup()
+    family.hidePopup()                                          # Auswahl fertig: weiter tippen
+    win.activateWindow()                                        # offscreen: Liste nahm sie mit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+
+
+# --- Leerer neuer Rahmen entfällt auf jedem Weg ---------------------------------------------
+@pytest.mark.parametrize("leave", [lambda w: w.shortcut_actions["tool.select"].trigger(),
+                                   lambda w: w.shortcut_actions["tool.text"].trigger(),
+                                   lambda w: w.tool_actions["paper"].trigger(),
+                                   lambda w: w.tool_actions["layout"].trigger()])
+def test_empty_new_frame_is_dropped_on_every_exit(window, leave):
+    window.create_text(30, 12)
+    leave(window)
+    assert not _session(window).active
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
+
+
+def test_undo_in_an_empty_new_frame_only_removes_the_frame(window):
+    window.canvas.set_selection([1])
+    window.nudge(1, 0)
+    window.create_text(30, 12)
+    window.shortcut_actions["edit.undo"].trigger()
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
+    assert window.doc.objects[1].x_mm == pytest.approx(5)          # Verschieben bleibt
+    window.shortcut_actions["edit.redo"].trigger()
+    assert len(window.doc.objects) == 2                           # kein leerer Rahmen zurück
+
+
+def test_keyboard_undo_falls_through_like_the_button(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    win.canvas.set_selection([0])
+    win.nudge(1, 0)                                              # Schritt im Dokument
+    _double_click(win.canvas, _char_point(win, 0, 3))
+    QTest.keyClicks(editor, "X")
+    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)                   # im Editor
+    assert win.doc.objects[0].text == "Max Mustermann" and _session(win).active
+    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)                   # weiter im Dokument
+    assert not _session(win).active
+    assert win.doc.objects[0].x_mm == pytest.approx(4)
+
+
+def test_keyboard_undo_with_nothing_to_undo_keeps_edit_mode(qtbot):
+    win, editor = _editing(qtbot, pos=3)
+    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
+    assert _session(win).active and win.doc.objects[0].text == "Max Mustermann"
+
+
+# --- Rahmen umschließt Schreibmarke und Markierung ----------------------------------------
+@pytest.mark.parametrize("rotation", [0, 90, 270])
+def test_edit_frame_encloses_caret_and_selection(qtbot, rotation):
+    win, editor = _editing(qtbot, _plain_doc(_plain("Max\nMustermann", 10, 10, rotation=rotation)),
+                           pos=2)
+    QTest.keyClick(editor, Qt.Key.Key_A, CTRL)
+    frame = win.canvas.edit_frame_rect().adjusted(-1, -1, 1, 1)
+    line = win.canvas.caret_line()
+    assert frame.contains(line.p1()) and frame.contains(line.p2())
+    assert win.canvas.selection_rects()
+    assert all(frame.contains(rect) for rect in win.canvas.selection_rects())
+
+
+# --- Zeichen außerhalb der BMP (UTF-16) ---------------------------------------------------
+def test_emoji_positions_for_click_caret_and_selection(qtbot):
+    text = "a\U0001F600b c"
+    win, editor = _editing(qtbot, _plain_doc(_plain(text, 4, 4, align="left")), pos=0)
+    for pos in range(len(text) + 1):
+        _click(win.canvas, _char_point(win, 0, pos))
+        assert editor.textCursor().position() == to_utf16(text, pos)
+        start, _ = _expected_caret(win, 0, pos)
+        assert win.canvas.caret_line().p1().x() == pytest.approx(start.x(), abs=1)
+    cursor = editor.textCursor()
+    cursor.setPosition(0)
+    cursor.setPosition(to_utf16(text, 2), cursor.MoveMode.KeepAnchor)   # „a😀“
+    editor.setTextCursor(cursor)
+    (rect,) = win.canvas.selection_rects()
+    assert rect.left() == pytest.approx(_char_point(win, 0, 0).x(), abs=1)
+    assert rect.right() == pytest.approx(_char_point(win, 0, 2).x(), abs=1)
+    QTest.keyClicks(editor, "Z")
+    assert win.doc.objects[0].text == "Zb c"
diff --git a/tests/gui/test_gui_editbar.py b/tests/gui/test_gui_editbar.py
index 8b43a29..9a2ea9f 100644
--- a/tests/gui/test_gui_editbar.py
+++ b/tests/gui/test_gui_editbar.py
@@ -354,8 +354,7 @@ def test_consecutive_nudges_are_one_step(window, qtbot):
 def test_undo_create_delete_paste_duplicate(window):
     steps = []
     window.create_text(30, 12)
-    steps.append(3)
-    window.panel("text").edit.setPlainText("Neu")            # Getipptes: eigener Schritt
+    window.panel("text").edit.setPlainText("Neu")            # Anlegen + Schreiben: ein Schritt
     steps.append(3)
     window.canvas.set_selection([0])
     window.delete_selected()
@@ -507,7 +506,11 @@ def test_frame_with_text_stays(window):
 def test_empty_frame_removed_while_pasting_is_part_of_the_paste_step(window):
     window.canvas.set_selection([0])
     window.copy_selected()
-    window.create_text(30, 12)
+    frame = TextObject.plain("", size_pt=14)                # gewählter leerer Rahmen außerhalb
+    frame.x_mm, frame.y_mm = 30, 12                         # des Schreibmodus (z. B. aus einer Datei)
+    window.doc.objects.append(frame)
+    window.render_now()
+    window.canvas.set_selection([2])
     window.paste()
     assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Eins"]
     assert window.canvas.selection() == [2]
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index 89962d6..7d9b8e0 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -186,10 +186,21 @@ def test_shortcut_table_lists_every_action_with_scope_and_keys(qtbot):
     native = QKeySequence("Ctrl+Shift+P").toString(QKeySequence.SequenceFormat.NativeText)
     assert table.item(row, 2).text() == native
     assert table.item(_row("edit.copy"), 1).text() == "Arbeitsfläche"
-    assert table.item(_row("text.bold"), 1).text() == "Text"
+    assert table.item(_row("text.bold"), 1).text() == "Schreibmodus"
     assert table.item(_row("align.left"), 2).text() == ""
 
 
+def test_fixed_shortcut_row_is_not_editable(qtbot):
+    from PySide6.QtCore import Qt
+    dialog = _shortcut_dialog(qtbot)
+    row = _row("text.end_edit")
+    table = dialog.shortcut_table
+    assert table.item(row, 1).text() == "Schreibmodus"
+    assert not table.item(row, 2).flags() & Qt.ItemFlag.ItemIsEditable
+    assert "fest" in table.item(row, 2).toolTip()
+    assert table.item(_row("text.bold"), 2).flags() & Qt.ItemFlag.ItemIsEditable
+
+
 def test_values_contain_only_changed_shortcuts(qtbot):
     dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P"}))
     dialog.set_shortcut("edit.copy", "Ctrl+Shift+C")
diff --git a/tests/gui/test_gui_textframe.py b/tests/gui/test_gui_textframe.py
index 3c29863..c3fe451 100644
--- a/tests/gui/test_gui_textframe.py
+++ b/tests/gui/test_gui_textframe.py
@@ -2,6 +2,7 @@
 import pytest
 from PySide6.QtTest import QTest
 
+from labelwerk import layout
 from labelwerk.document import Document, TextObject
 from labelwerk.gui.main_window import MainWindow
 from labelwerk.labels import DPI
@@ -103,7 +104,11 @@ def test_typing_goes_into_newly_created_text(window, qtbot):
     qtbot.waitUntil(editor.hasFocus, timeout=1000)
     QTest.keyClicks(editor, "Neu")
     assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Neu"]
-    assert (window.doc.objects[2].x_mm, window.doc.objects[2].y_mm) == (30, 12)
+    # neuer Text linksbündig: Zeilenanfang und Oberkante der Schrift bleiben am Klickpunkt
+    assert window.doc.objects[2].paragraphs[0].align == "left"
+    rendered = window.rendered[2]
+    x, y = layout.from_object(rendered.layout.anchor("left"), rendered, 0)
+    assert (x * DOT_MM, y * DOT_MM) == pytest.approx((30, 12), abs=DOT_MM)
 
 
 def test_deleting_last_object_leaves_label_empty(qtbot):
diff --git a/tests/test_settings.py b/tests/test_settings.py
index 849828e..8244d3c 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -176,3 +176,12 @@ def test_shortcuts_null_keeps_defaults_with_warning(tmp_path):
     s = load_settings(path)
     assert s.shortcuts == {} and s.label_id == "29"
     assert len(s.warnings) == 1 and "shortcuts" in s.warnings[0]
+
+
+def test_esc_from_settings_file_is_rejected(tmp_path):
+    from labelwerk.settings import load_settings
+    path = tmp_path / "settings.json"
+    path.write_text('{"shortcuts": {"file.print": "Esc"}}', encoding="utf-8")
+    settings = load_settings(path)
+    assert settings.shortcuts == {}
+    assert any("nicht belegbar" in w for w in settings.warnings)
diff --git a/tests/test_shortcuts.py b/tests/test_shortcuts.py
index 3345d50..b25b772 100644
--- a/tests/test_shortcuts.py
+++ b/tests/test_shortcuts.py
@@ -18,13 +18,13 @@ def test_actions_have_unique_dotted_ids_and_valid_scopes():
     assert all(re.fullmatch(r"[a-z]+(\.[a-z0-9_]+)+", i) for i in ids)
     assert all(a.scope in SCOPES for a in ACTIONS)
     assert all(a.name.strip() for a in ACTIONS)
-    assert SCOPES == ("global", "canvas", "text")
+    assert SCOPES == ("global", "canvas", "edit")
 
 
 def test_actions_cover_all_app_shortcuts():
     expected = {
         "file.print", "app.settings", "view.zoom_in", "view.zoom_out", "view.zoom_reset",
-        "text.bold", "text.italic", "text.underline", "tool.select", "tool.text",
+        "text.bold", "text.italic", "text.underline", "text.end_edit", "tool.select", "tool.text",
         "edit.cut", "edit.copy", "edit.paste", "edit.duplicate", "edit.delete",
         "edit.select_all", "edit.undo", "edit.redo",
         "object.nudge_left", "object.nudge_right", "object.nudge_up", "object.nudge_down",
@@ -122,12 +122,34 @@ def test_conflict_detected_case_insensitive():
     assert shortcuts.conflicts(mapping) == [("Ctrl+C", ["edit.copy", "edit.duplicate"])]
 
 
-def test_no_conflict_between_canvas_and_text():
-    # Strg+B auf der Arbeitsfläche stört Fett im Textfeld nicht – nie beide gleichzeitig aktiv
+def test_no_conflict_between_canvas_and_edit_mode():
+    # Strg+B auf der Arbeitsfläche stört Fett im Schreibmodus nicht – nie beide gleichzeitig aktiv
     mapping = shortcuts.effective({"edit.duplicate": "Ctrl+B"})
     assert shortcuts.conflicts(mapping) == []
 
 
+def test_edit_mode_conflicts_with_itself_and_global():
+    mapping = shortcuts.effective({"text.italic": "Ctrl+B"})
+    assert shortcuts.conflicts(mapping) == [("Ctrl+B", ["text.bold", "text.italic"])]
+    mapping = shortcuts.effective({"view.zoom_reset": "Ctrl+U"})
+    assert shortcuts.conflicts(mapping) == [("Ctrl+U", ["text.underline", "view.zoom_reset"])]
+
+
+def test_formatting_and_end_edit_belong_to_edit_mode():
+    for action_id in ("text.bold", "text.italic", "text.underline", "text.end_edit"):
+        assert shortcuts.action(action_id).scope == "edit"
+    end = shortcuts.action("text.end_edit")
+    assert (end.name, end.default, end.fixed) == ("Schreibmodus beenden", "Esc", True)
+    assert not shortcuts.action("text.bold").fixed
+
+
+def test_fixed_shortcut_cannot_be_overridden():
+    assert shortcuts.effective({"text.end_edit": "Ctrl+Q"})["text.end_edit"] == "Esc"
+    clean, warnings = shortcuts.validate({"text.end_edit": "Ctrl+Q", "text.bold": "Ctrl+Q"})
+    assert clean == {"text.bold": "Ctrl+Q"}
+    assert len(warnings) == 1 and "fest" in warnings[0]
+
+
 def test_global_conflicts_with_every_scope():
     mapping = shortcuts.effective({"file.print": "Ctrl+B"})
     assert shortcuts.conflicts(mapping) == [("Ctrl+B", ["file.print", "text.bold"])]
@@ -219,3 +241,24 @@ def test_without_conflicts_compares_normalized_forms():
     mapping = shortcuts.effective({"edit.duplicate": "ctrl+c"})
     clean, _ = shortcuts.without_conflicts(mapping)
     assert clean["edit.duplicate"] == ""
+
+
+def test_fixed_shortcut_always_keeps_its_key():
+    mapping = shortcuts.effective({})
+    mapping["file.print"] = "Esc"                  # global: kollidiert mit jedem Bereich
+    clean, warnings = shortcuts.without_conflicts(mapping)
+    assert clean["text.end_edit"] == "Esc"         # fest – gewinnt immer
+    assert clean["file.print"] == ""
+    assert clean["tool.select"] == "Esc"           # Arbeitsfläche: kein Konflikt mit dem Schreibmodus
+    assert len(warnings) == 1 and "Drucken" in warnings[0]
+
+
+@pytest.mark.parametrize("seq", ["Esc", "Return", "Enter", "Tab", "Shift+Tab", "Backtab"])
+def test_keys_reserved_for_editing_are_rejected(seq):
+    clean, warnings = shortcuts.validate({"file.print": seq})
+    assert clean == {}
+    assert len(warnings) == 1 and "nicht belegbar" in warnings[0]
+
+
+def test_reserved_key_is_fine_as_the_actions_own_default():
+    assert shortcuts.validate({"tool.select": "Esc"}) == ({"tool.select": "Esc"}, [])
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 07bf4af..6a0a0d5 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -14,7 +14,8 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Papier: Ausrichtung H/V, Ränder, Medium prüfen (GUI + `labelwerk media`), Einstellungen (`settings.json`, GUI-Dialog), Live-Druckererkennung.
 - Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.
 - Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
-- 830 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Direkt auf dem Etikett schreiben (Etappe 3d-1b): Schreibmodus (Text anlegen + Klick bzw. Doppelklick, Esc/Klick daneben beendet), Schreibmarke/Markierung aus dem Kern-Zeilensatz, Markieren mit Maus und Tastatur, eine Bearbeitung = ein Rückgängig-Schritt, Rahmen wächst an der Kante der Textposition; Feld INHALT entfällt.
+- 998 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -43,7 +44,8 @@ src/labelwerk/
   layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
               growing_axis (Endlosband wächst mit), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
               Schreibmodus: to_object/from_object (Etikett ↔ ungedrehtes Objekt, Druckpunkte), anchor_after_edit/anchor_align
-  shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich), effective, conflicts, without_conflicts, validate
+  shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
+              without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
   desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
   gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
     main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
@@ -51,7 +53,11 @@ src/labelwerk/
     tools.py        Werkzeug-Registry (Papier, Text, Layout; neue Werkzeuge als Eintrag)
     panels/         Eigenschaften-Panels je Werkzeug (paper, text mit Bereich Position)
     panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
-    canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom
+    canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
+                    Schreibmodus: zeichnet Rahmen/Schreibmarke/Markierung (set_edit_marks), meldet Klicks hinein (edit_*)
+    text_edit_mode.py TextEditSession: Schreibmodus – Editor des Text-Panels als unsichtbarer Eingabepuffer (Fokus, IME),
+                    Klick → Position über TextLayout.hit, Editor → Schreibmarke/Markierung, Auf/Ab nach Etikettzeilen,
+                    sofort rendern + anchor_after_edit; Start/Ende/Rückgängig-Schritt: MainWindow.edit_text/finish_editing
     actions.py      QActions aus shortcuts.ACTIONS – jedes Kürzel der App läuft hierüber (apply_shortcuts)
     history.py      Rückgängig/Wiederherstellen: Dokument-Schnappschüsse samt Auswahl, höchstens 100; amend (ohne eigenen Schritt)
     symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
@@ -94,7 +100,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Etappe 3d-1b Direkt auf dem Etikett schreiben, danach 3d-2 Werkzeug ‚Bild‘ (Roadmap 0/5) als neuer Eintrag in `gui/tools.py`, Objekt im selben Modell wie Text.
+Nächste Schritte: Etappe 3d-2 Werkzeug ‚Bild‘ (Roadmap 0/5) als neuer Eintrag in `gui/tools.py`, Objekt im selben Modell wie Text.
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -111,7 +117,7 @@ Umsetzung:
 - GUI bleibt dünn: Logik, die testbar ist, gehört in den Kern
 
 ## Roadmap danach
-0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (Feld INHALT entfällt; Schreibmarke/Markierung aus dem Kern-Zeilensatz auf der Arbeitsfläche) · 3d-2 Bild · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
+0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2 Bild · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
 1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
 2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
 3. Barcodes und QR-Codes
diff --git a/README.md b/README.md
index d3a3bcd..fe37e2b 100644
--- a/README.md
+++ b/README.md
@@ -49,9 +49,9 @@ Aufbau wie im P-touch Editor: Werkzeugleiste (Papier, Text, Layout), Bearbeitung
 
 Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil); gespeichert in `~/.config/labelwerk/settings.json`.
 
-Text: Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition – zeichenweise wie im P-touch Editor. Ohne Markierung gilt die Formatierung für den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.
+Text: Geschrieben wird direkt auf dem Etikett. Mit „A“ (Text anlegen) und einem Klick entsteht ein Rahmen, in den man sofort tippt (linksbündig ab dem Klickpunkt); ein Doppelklick auf einen Text setzt die Schreibmarke an die Klickstelle (ein einfacher Klick wählt den Rahmen nur). Im Schreibmodus markiert Ziehen Text, Doppelklick ein Wort, Umschalt+Klick erweitert; Pfeiltasten, Pos1/Ende, Entf, Enter, Strg+A/C/X/V und Strg+Z wirken auf den Text. **Esc** oder ein Klick neben den Rahmen beendet den Schreibmodus – die ganze Bearbeitung ist dann ein Schritt für Rückgängig. Ohne feste Rahmengröße wächst der Rahmen beim Tippen an der Kante seiner Textposition (links, rechts, Mitte). Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition wirken zeichenweise wie im P-touch Editor: im Schreibmodus auf die Markierung bzw. das Weitertippen, sonst auf den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.
 
-Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste (oder im Reiter „Text“ ohne Auswahl) und einem Klick aufs Etikett einen Rahmen anlegen – bleibt er leer, verschwindet er wieder, sobald man etwas anderes wählt. Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus; Lage und Größe landen auf 0,1 mm wie in den Feldern), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.
+Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste (oder im Reiter „Text“ ohne Auswahl) und einem Klick aufs Etikett einen Rahmen anlegen – bleibt er leer, verschwindet er wieder, sobald man den Schreibmodus verlässt. Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus; Lage und Größe landen auf 0,1 mm wie in den Feldern), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.
 
 Tastenkürzel (Standard):
 
@@ -65,9 +65,9 @@ Tastenkürzel (Standard):
 | Pfeiltasten · Umschalt+Pfeiltasten | verschieben um 0,1 mm · 1 mm |
 | Strg+L · Strg+R | 90° nach links · rechts drehen |
 | Strg+Bild↑ · Strg+Bild↓ | nach vorne · nach hinten |
-| Strg+B/I/U | fett/kursiv/unterstrichen (im Textfeld) |
+| Strg+B/I/U · Esc | fett/kursiv/unterstrichen · Schreibmodus beenden (im Schreibmodus) |
 
-Ausrichten, Größe angleichen und Maximieren haben ab Werk kein Kürzel. Alle Kürzel lassen sich unter „Einstellungen“ → „Tastenkürzel“ ändern (Zeile anklicken, neue Kombination drücken; Esc, Enter und Tab sind nicht belegbar). Doppelt belegte Kürzel werden rot markiert und sperren das Speichern; stehen in einer von Hand bearbeiteten `settings.json` doppelte, behält die erste Aktion ihr Kürzel und die Statusleiste meldet es.
+Ausrichten, Größe angleichen und Maximieren haben ab Werk kein Kürzel. Im Schreibmodus gelten die Tasten des Texts statt der Objekt-Kürzel (Pfeile bewegen die Schreibmarke, Entf löscht Zeichen); Esc zum Beenden ist fest. Alle Kürzel lassen sich unter „Einstellungen“ → „Tastenkürzel“ ändern (Zeile anklicken, neue Kombination drücken; Esc, Enter und Tab sind nicht belegbar). Doppelt belegte Kürzel werden rot markiert und sperren das Speichern; stehen in einer von Hand bearbeiteten `settings.json` doppelte, behält die erste Aktion ihr Kürzel und die Statusleiste meldet es.
 
 ## Architektur
 
diff --git a/docs/superpowers/specs/2026-10-17-direkt-schreiben-design.md b/docs/superpowers/specs/2026-10-17-direkt-schreiben-design.md
index c8c2658..d832b7c 100644
--- a/docs/superpowers/specs/2026-10-17-direkt-schreiben-design.md
+++ b/docs/superpowers/specs/2026-10-17-direkt-schreiben-design.md
@@ -8,25 +8,26 @@ Text wird wie im P-touch Editor **direkt im Rahmen auf dem Etikett** geschrieben
 
 ## Nicht enthalten
 
-Automatischer Zeilenumbruch, Rechtschreibprüfung, Suchen/Ersetzen, Bearbeiten mehrerer Rahmen gleichzeitig, Ziehen von Text per Drag & Drop.
+Automatischer Zeilenumbruch, Rechtschreibprüfung, Suchen/Ersetzen, Bearbeiten mehrerer Rahmen gleichzeitig, Ziehen von Text per Drag & Drop. Noch nicht übernommene Eingaben einer Eingabemethode (Vorschlagstext/Preedit, z. B. beim Japanisch-Tippen) erscheinen nicht auf dem Etikett – erst der übernommene Text; das Kandidatenfenster steht an der Schreibmarke.
 
 ## Bedienung
 
-- **Neuer Text:** Werkzeug „Text anlegen“ (A) + Klick aufs Etikett → neuer Rahmen an der Klickstelle, **sofort im Schreibmodus**.
+- **Neuer Text:** Werkzeug „Text anlegen“ (A) + Klick aufs Etikett → neuer Rahmen an der Klickstelle, **sofort im Schreibmodus**, **linksbündig**: Schreibmarke am Klickpunkt, der Text wächst nach rechts (wie P-touch/Textverarbeitung); die Textposition lässt sich danach ändern.
 - **Bestehender Text:** 1. Klick wählt den Rahmen (verschieben, Anfasser wie bisher). **Doppelklick** startet den Schreibmodus mit der Schreibmarke an der Klickstelle. Ein Klick in einen schon gewählten Rahmen startet ihn nicht.
 - **Im Schreibmodus:**
   - Ziehen markiert Text, Doppelklick markiert ein Wort, Umschalt+Klick erweitert die Markierung.
   - Tasten des Texteditors: Pfeile bewegen die Schreibmarke (mit Umschalt markieren), Pos1/Ende, Entf/Rücktaste, Enter = neue Zeile, Strg+A = ganzer Text des Rahmens, Strg+C/X/V mit Text (Einfügen nur als reiner Text), Strg+B/I/U, Strg+Z/Strg+Umschalt+Z innerhalb der Bearbeitung.
-  - **Esc** oder **Klick neben den Rahmen** beendet den Schreibmodus. Ziehen an einem anderen Rahmen beendet ihn und verschiebt dann diesen Rahmen.
+  - Tab bleibt ohne Wirkung (Tabulatoren druckt labelwerk nicht; der Fokus bleibt im Text). Strg+Z und der Knopf „Rückgängig“ gehen im Dokument weiter, wenn in der Bearbeitung nichts mehr zurückzunehmen ist; in einem leeren neuen Rahmen nimmt Rückgängig nur den Rahmen zurück.
+  - **Esc** oder **Klick neben den Rahmen** beendet den Schreibmodus (ebenso ein anderes Werkzeug oder ein anderer Reiter). Ziehen an einem anderen Rahmen beendet ihn und verschiebt dann diesen Rahmen.
   - Panel-Formatierung (Schrift, Größe, A⁺/A⁻, B/I/U, Textposition) wirkt auf die Markierung bzw. das Weitertippen; außerhalb des Schreibmodus wie bisher auf den ganzen Rahmen.
 - **Außerhalb des Schreibmodus** gelten die Objekt-Kürzel unverändert (Pfeile verschieben, Entf löscht den Rahmen …).
-- **Leerer Rahmen** entfällt beim Verlassen (wie bisher).
+- **Leerer Rahmen** entfällt beim Verlassen – auf jedem Weg.
 - **Rückgängig:** Eine abgeschlossene Bearbeitung ist **ein** Schritt im Dokument-Verlauf.
 
 ## Darstellung
 
-- Rahmen im Schreibmodus durchgezogen (statt gestrichelt), ohne Anfasser.
-- Schreibmarke: senkrechte Linie, 1 Bildschirmpixel breit, Höhe der Schrift an der Stelle, blinkt im Systemtakt (`QApplication.cursorFlashTime`).
+- Rahmen im Schreibmodus durchgezogen (statt gestrichelt), ohne Anfasser; er umfasst die Zeilen von Ober- bis Unterlänge, damit Schreibmarke und Markierung darin liegen.
+- Schreibmarke: senkrechte Linie, 1 Bildschirmpixel breit, Höhe der Schrift an der Stelle, blinkt im Systemtakt (`QApplication.cursorFlashTime`); sie fehlt, solange der Tastaturfokus woanders ist (z. B. im Feld „Schrift“).
 - Markierung: halbtransparente Systemfarbe für Markierungen (`palette().highlight()`, Alpha ≈ 35 %) über dem Druckbild.
 - Leerer Rahmen: Schreibmarke dort, wo die erste Zeile beginnen würde, Höhe der aktuellen Schriftgröße, Absatz-Ausrichtung gilt (zentriert → mittig).
 - Gedrehte Objekte (90/180/270°): Schreibmarke und Markierung drehen mit; Klicks werden zurückgerechnet.
diff --git a/src/labelwerk/gui/actions.py b/src/labelwerk/gui/actions.py
index 12f1481..f566293 100644
--- a/src/labelwerk/gui/actions.py
+++ b/src/labelwerk/gui/actions.py
@@ -1,7 +1,8 @@
 """QActions aus dem Kürzel-Verzeichnis (``shortcuts.ACTIONS``): eine je Aktion, Kürzel änderbar.
 
 Wer eine Aktion nutzt, verbindet ``triggered`` und hängt sie an das passende Widget
-(globale ans Hauptfenster, „canvas“ an die Arbeitsfläche, „text“ ans Textfeld).
+(globale ans Hauptfenster, „canvas“ an die Arbeitsfläche, „edit“ ans Text-Panel, in dem der
+Editor des Schreibmodus steckt).
 """
 from __future__ import annotations
 
@@ -13,7 +14,7 @@ from .. import shortcuts
 _CONTEXT = {
     "global": Qt.ShortcutContext.WindowShortcut,
     "canvas": Qt.ShortcutContext.WidgetWithChildrenShortcut,
-    "text": Qt.ShortcutContext.WidgetWithChildrenShortcut,
+    "edit": Qt.ShortcutContext.WidgetWithChildrenShortcut,
 }
 
 
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index 7a265d6..c7f1ffd 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -102,6 +102,8 @@ class Canvas(QGraphicsView):
     edit_requested = Signal(int, object)       # Text bearbeiten (Doppelklick): Index, Klickpunkt
                                                # (QPointF, Druckpunkte in Leserichtung) oder None
     edit_pressed = Signal(object, bool)        # Schreibmodus: Klick in den Rahmen (Punkt, Umschalt)
+    edit_dragged = Signal(object)              # Schreibmodus: Ziehen im Rahmen markiert (Punkt)
+    edit_double_clicked = Signal(object)       # Schreibmodus: Doppelklick markiert ein Wort
     edit_left = Signal()                       # Schreibmodus: Klick neben den Rahmen beendet ihn
     object_clicked = Signal(int)               # Klick auf ein Objekt (auch ein schon gewähltes)
     tool_changed = Signal(str)                 # Werkzeug: "select" | "text"
@@ -148,6 +150,7 @@ class Canvas(QGraphicsView):
         self._caret: QLineF | None = None                  # (Druckpunkte in Leserichtung)
         self._marked: list[QRectF] = []
         self._caret_on = True
+        self._caret_focus = True                           # Editor hat den Tastaturfokus
         self._blink = QTimer(self)
         self._blink.timeout.connect(self._toggle_caret)
         self._apply_zoom()
@@ -303,12 +306,26 @@ class Canvas(QGraphicsView):
         """Rahmen, Schreibmarke und Markierung des Schreibmodus (Druckpunkte in Leserichtung,
         wie ``sheet``). Die Schreibmarke erscheint sofort und blinkt im Systemtakt."""
         self._edit_frame, self._caret, self._marked = QRectF(frame), caret, list(marked)
+        self._restart_blink()
+
+    def set_caret_focus(self, focused: bool) -> None:
+        """Schreibmarke nur zeigen, solange der Editor den Tastaturfokus hat – sonst landet
+        Getipptes woanders (z. B. im Feld „Schrift“)."""
+        self._caret_focus = focused
+        self._restart_blink()
+
+    def caret_shown(self) -> bool:
+        """Wird im Schreibmodus eine Schreibmarke gezeigt (blinkend)?"""
+        return self._editing is not None and self._caret is not None and self._caret_focus
+
+    def _restart_blink(self) -> None:
+        """Schreibmarke sofort sichtbar, blinkt im Systemtakt; ohne Fokus aus."""
         self._caret_on = True
         flash = QApplication.cursorFlashTime()
-        if flash > 0:
+        if flash > 0 and self.caret_shown():
             self._blink.start(flash // 2)
         else:
-            self._blink.stop()                             # Blinken abgeschaltet: steht still
+            self._blink.stop()                             # aus oder Blinken abgeschaltet
         self.viewport().update()
 
     def caret_line(self) -> QLineF:
@@ -534,6 +551,9 @@ class Canvas(QGraphicsView):
             self._moved = True
             self.length_changed.emit(mm)
             return
+        if self._drag == "text":
+            self.edit_dragged.emit(self._reading(pos))
+            return
         if self._drag in ("move", "resize"):
             if not self._moved and (pos - self._press).manhattanLength() < _DRAG_START_PX:
                 return
@@ -620,6 +640,7 @@ class Canvas(QGraphicsView):
             self.length_changed.emit(None)
             return
         if self._editing is not None and self._in_edit_frame(event.position()):
+            self.edit_double_clicked.emit(self._reading(event.position()))
             return
         item = self._object_at(event.position()) if self.sheet is not None else None
         if item is not None and event.button() == Qt.MouseButton.LeftButton:
@@ -681,7 +702,7 @@ class Canvas(QGraphicsView):
         color.setAlpha(_SELECTION_ALPHA)
         for rect in self.selection_rects():
             painter.fillRect(rect, color)
-        if self._caret is not None and self._caret_on:
+        if self.caret_shown() and self._caret_on:
             painter.save()
             painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)   # scharf, 1 Pixel
             painter.setPen(QPen(Qt.GlobalColor.black, 0))
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index db58158..abcf6ee 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -161,6 +161,8 @@ class MainWindow(QMainWindow):
         layout.setSpacing(0)
         scroll = QScrollArea()                  # kleine Bildschirme: Panel rollt statt Fenster wächst
         scroll.setObjectName("panelScroll")
+        # Klick auf freie Panel-Fläche nimmt niemandem den Fokus (Schreibmodus tippt weiter)
+        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
         scroll.setWidget(self.panels)
         scroll.setWidgetResizable(True)
         scroll.setFrameShape(QFrame.Shape.NoFrame)
@@ -204,9 +206,7 @@ class MainWindow(QMainWindow):
         # Schreibmodus direkt auf dem Etikett (Editor des Text-Panels als Eingabepuffer)
         self.edit_session = TextEditSession(self)
         self.panel("text").changed.connect(self.edit_session.content_changed)
-        # Esc und Klick neben den Rahmen beenden ihn; ein leerer Rahmen entfällt dabei
-        for signal in (self.edit_session.end_requested, self.canvas.edit_left):
-            signal.connect(lambda: self.finish_editing(drop_empty=True))
+        self._connect_edit_mode()
         self.render_now()
         self.canvas.selection_changed.connect(self._on_selection)
         self.panel("text").frame_edited.connect(self._edit_frame)
@@ -256,6 +256,18 @@ class MainWindow(QMainWindow):
         self.shortcut_actions["edit.redo"].triggered.connect(self.redo)
         self.addActions([self.shortcut_actions["edit.undo"], self.shortcut_actions["edit.redo"]])
 
+    def _connect_edit_mode(self) -> None:
+        """Esc (Bereich „Schreibmodus“, fest) und Klick neben den Rahmen beenden den
+        Schreibmodus – ein leer gebliebener Rahmen entfällt dabei. Rückgängig, Zwischenablage
+        und ihre Knöpfe folgen im Schreibmodus dem Editor."""
+        end = self.shortcut_actions["text.end_edit"]
+        end.triggered.connect(lambda _=False: self.finish_editing())
+        self.panel("text").addAction(end)
+        self.canvas.edit_left.connect(lambda: self.finish_editing())
+        editor = self.panel("text").edit
+        for signal in (editor.copyAvailable, editor.undoAvailable, editor.redoAvailable):
+            signal.connect(self._update_edit_actions)
+
     def _connect_layout_actions(self) -> None:
         """Reiter „Layout“: Ausrichten, Größe angleichen, Drehen, Reihenfolge (auch per Kürzel)."""
         handlers = {"size.maximize": self.maximize_selected,
@@ -332,7 +344,7 @@ class MainWindow(QMainWindow):
             self._follow_selection(indices)
             return
         if self.edit_session.active and indices != [self.edit_session.index]:
-            self.finish_editing()                   # leere Rahmen entfallen gleich hier unten
+            self.finish_editing(drop_empty=False)   # leere Rahmen entfallen gleich hier unten
         if not self._restoring:
             indices = self._drop_empty_frames(indices)
         self._follow_selection(indices)
@@ -392,6 +404,18 @@ class MainWindow(QMainWindow):
             panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))
 
     def _update_edit_actions(self) -> None:
+        if self.edit_session.active:                # Knöpfe wirken auf den Text im Editor
+            editor = self.panel("text").edit
+            marked = editor.textCursor().hasSelection()
+            enabled = {"edit.cut": marked, "edit.copy": marked, "edit.paste": editor.canPaste(),
+                       "edit.duplicate": False, "edit.delete": False,
+                       "edit.undo": (editor.document().isUndoAvailable()
+                                     or self.history.can_undo(self.doc)),
+                       "edit.redo": editor.document().isRedoAvailable(), "text.end_edit": True}
+            for key, value in enabled.items():
+                self.shortcut_actions[key].setEnabled(value)
+            return
+        self.shortcut_actions["text.end_edit"].setEnabled(False)
         selected = bool(self.canvas.selection())
         for key in _SELECTION_ACTIONS:
             self.shortcut_actions[key].setEnabled(selected)
@@ -502,16 +526,38 @@ class MainWindow(QMainWindow):
         Vor jeder Aktion aufgerufen, wird noch nicht Festgehaltenes (Getipptes) ein eigener
         Schritt. Tippen im Textfeld wird ein Schritt, sobald der Fokus das Feld verlässt –
         nicht, während die Auswahl intern umgestellt wird (z. B. Textfeld gesperrt, weil ein
-        leerer Rahmen entfällt); das hält der Aufrufer selbst fest."""
-        if self._arranging:
+        leerer Rahmen entfällt); das hält der Aufrufer selbst fest. Im Schreibmodus gehört alles
+        zur laufenden Bearbeitung – sie wird beim Beenden ein Schritt (``finish_editing``)."""
+        if self._arranging or self.edit_session.active:
             return
         self.history.push(self.doc, merge, self.canvas.selection())
         self._update_edit_actions()
 
     def undo(self) -> None:
+        """Rückgängig – im Schreibmodus innerhalb der Bearbeitung (Editor); ist dort nichts
+        mehr zurückzunehmen, endet der Schreibmodus und es geht im Dokument weiter (Knopf und
+        Strg+Z gleich). Ein leerer neuer Rahmen entfällt dabei – das ist dann der ganze
+        Schritt."""
+        if self.edit_session.active:
+            editor = self.panel("text").edit
+            if editor.document().isUndoAvailable():
+                editor.undo()
+                return
+            obj = self.doc.objects[self.edit_session.index]
+            if obj.positioned and obj.is_empty():
+                selection = self.history.selection  # Auswahl vor dem Anlegen
+                self.finish_editing()
+                self.canvas.set_selection(selection)
+                return
+            if not self.history.can_undo(self.doc):
+                return                              # nichts zurückzunehmen: weiter schreiben
+            self.finish_editing()
         self._restore(self.history.undo(self.doc, self.canvas.selection()))
 
     def redo(self) -> None:
+        if self.edit_session.active:
+            self.panel("text").edit.redo()
+            return
         self._restore(self.history.redo(self.doc, self.canvas.selection()))
 
     def _restore(self, snapshot: Document | None) -> None:
@@ -585,7 +631,9 @@ class MainWindow(QMainWindow):
         self._structure_changing()
         self._commit()
         family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
-        obj = TextObject.plain("", size_pt=self.settings.font_size_pt or DEFAULT_PT, family=family)
+        # linksbündig: Schreibmarke am Klickpunkt, der Text wächst nach rechts (wie P-touch)
+        obj = TextObject.plain("", size_pt=self.settings.font_size_pt or DEFAULT_PT, align="left",
+                               family=family)
         obj.x_mm, obj.y_mm = round(x_mm, 1), round(y_mm, 1)
         self.doc.objects[:] = [o for o in self.doc.objects if not o.is_empty()]
         self.doc.objects.append(obj)
@@ -597,8 +645,7 @@ class MainWindow(QMainWindow):
         finally:
             self._arranging = False
         self.canvas.set_selection([index])
-        self._commit()
-        self.edit_text(index)
+        self.edit_text(index)                       # Anlegen und Schreiben: ein Schritt
 
     def edit_text(self, index: int, point=None) -> None:
         """Schreibmodus für ein Objekt: auswählen, Text-Panel zeigen, Schreibmarke an
@@ -606,26 +653,30 @@ class MainWindow(QMainWindow):
         if self.edit_session.active:
             if self.edit_session.index == index:
                 return
-            self.finish_editing()
+            self.finish_editing(drop_empty=False)   # entfällt gleich beim Wählen (Nummern!)
         if not self._valid(index):
             return
         if self.canvas.selection() != [index]:
             self.canvas.set_selection([index])
+            index = self.canvas.selection()[-1]     # ggf. umnummeriert (leerer Rahmen entfiel)
         self._show_tool("text")
         if self._timer.isActive():
             self.render_now()                       # Klick trifft den aktuellen Zeilensatz
         self.edit_session.start(index, point)
+        self._update_edit_actions()
 
-    def finish_editing(self, drop_empty: bool = False) -> None:
-        """Schreibmodus beenden (Esc, Klick daneben, anderes Werkzeug, Befehl auf der Auswahl).
-        ``drop_empty``: ein leer gebliebener Rahmen entfällt sofort (Esc, Klick daneben) –
-        sonst wie bisher, sobald er die Auswahl verlässt."""
+    def finish_editing(self, drop_empty: bool = True) -> None:
+        """Schreibmodus beenden (Esc, Klick daneben, anderes Werkzeug oder Reiter, Befehl auf
+        der Auswahl); die ganze Bearbeitung wird ein Rückgängig-Schritt. Ein leer gebliebener
+        Rahmen entfällt dabei – außer bei ``drop_empty=False``, wenn der Aufrufer gerade die
+        Auswahl ändert (dann entfällt er dort, ``_on_selection``)."""
         index = self.edit_session.end()
         if index is None:
             return
         if (drop_empty and self._valid(index) and self.doc.objects[index].positioned
                 and self.doc.objects[index].is_empty()):
             self.canvas.set_selection([])           # leerer Rahmen entfällt (_on_selection)
+        self._commit()
 
     def delete_selected(self) -> None:
         """Ausgewählte Objekte löschen (auch das letzte – das Etikett ist dann leer)."""
@@ -710,18 +761,29 @@ class MainWindow(QMainWindow):
 
     # --- Zwischenablage ---------------------------------------------------
     def copy_selected(self) -> None:
-        """Ausgewählte Objekte (in Zeichenreihenfolge) in die interne Zwischenablage kopieren."""
+        """Ausgewählte Objekte (in Zeichenreihenfolge) in die interne Zwischenablage kopieren –
+        im Schreibmodus den markierten Text in die Zwischenablage des Systems."""
+        if self.edit_session.active:
+            self.panel("text").edit.copy()
+            return
         indices = sorted(self.canvas.selection())
         if indices:
             self._clipboard = [self._placed_copy(i) for i in indices]
             self._update_edit_actions()
 
     def cut_selected(self) -> None:
+        if self.edit_session.active:
+            self.panel("text").edit.cut()
+            return
         self.copy_selected()
         self.delete_selected()
 
     def paste(self) -> None:
-        """Zwischenablage einfügen – jedes Mal 2 mm weiter versetzt; Eingefügtes ist ausgewählt."""
+        """Zwischenablage einfügen – jedes Mal 2 mm weiter versetzt; Eingefügtes ist ausgewählt.
+        Im Schreibmodus Text aus der Zwischenablage des Systems (als reiner Text)."""
+        if self.edit_session.active:
+            self.panel("text").edit.paste()
+            return
         if self._clipboard:
             self._clipboard = [_offset(obj) for obj in self._clipboard]
             self._insert(copy.deepcopy(self._clipboard))
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index 9e0e8a2..a5ad64b 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -1,8 +1,10 @@
 """Panel „Text“: bearbeitet den ausgewählten Textrahmen – zeichenweise wie im P-touch Editor.
 
 Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
-Formatierung auf den ganzen Text; sonst nur auf die Markierung. Bereich „Position“: Lage
-und (mit fester Rahmengröße) Größe des Rahmens in mm.
+Formatierung auf den ganzen Text; sonst nur auf die Markierung. Im Schreibmodus wirkt sie
+ohne Markierung aufs Weitertippen (Textposition: auf den Absatz der Schreibmarke) – außer
+der Rahmen ist noch leer. Bereich „Position“: Lage und (mit fester Rahmengröße) Größe des
+Rahmens in mm.
 
 Geschrieben wird direkt auf dem Etikett (``gui.text_edit_mode``): Der Editor ``edit`` ist
 dafür ein unsichtbarer Eingabepuffer (Kind des Panels, Größe 0, nicht im Layout) – er behält
@@ -86,6 +88,7 @@ def _align_icon(key: str, dark_checked: bool = True) -> QIcon:
 
 class TextPanel(Panel):
     frame_edited = Signal(str, float)   # Feld im Bereich „Position“ ("x" | "y" | "w" | "h"), mm
+    formatted = Signal()                # Knopf/Feld hat formatiert (Schreibmodus: Fokus zurück)
 
     def set_icon_style(self, dark_checked: bool) -> None:
         """Ausrichtungssymbole an das Design anpassen (weiß auf schwarz nur bei RawBlock)."""
@@ -97,6 +100,7 @@ class TextPanel(Panel):
         super().__init__(doc, "Text")
         self.dark_checked_icons = True
         self.index: int | None = None   # bearbeitetes Objekt; None = kein Text ausgewählt
+        self._editing = False           # Schreibmodus (``set_editing``)
         self._frame: Rect | None = None   # zuletzt angezeigter Rahmen (mm)
         self._updating = False
         self._formatting = False        # während einer Formatierung: contentsChanged nicht doppelt anwenden
@@ -113,6 +117,8 @@ class TextPanel(Panel):
         # unsichtbarer Eingabepuffer des Schreibmodus: fokussierbar, aber ohne Fläche
         self.edit = PlainPasteEdit(self)
         self.edit.setFixedSize(0, 0)
+        # nur der Schreibmodus gibt ihm den Fokus (setFocus) – nie Tab oder ein Klick
+        self.edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
         # Absätze ohne eigene Ausrichtung stehen zentriert – wie bisher in labelwerk; kein
         # Umbruch im Editor (Größe 0), damit Pos1/Ende und Zeilen den Absätzen entsprechen
         option = QTextOption(Qt.AlignmentFlag.AlignHCenter)
@@ -244,13 +250,24 @@ class TextPanel(Panel):
                 self.italic, self.underline, *self.align_buttons.values(), self.fit,
                 *self._frame_spins.values())
 
+    def set_editing(self, editing: bool) -> None:
+        """Schreibmodus an/aus: Formatieren ohne Markierung wirkt dann aufs Weitertippen."""
+        self._editing = editing
+
+    def _whole_text(self) -> bool:
+        """Wirkt eine Formatierung ohne Markierung auf den ganzen Text? Außerhalb des
+        Schreibmodus immer, im Schreibmodus nur bei noch leerem Rahmen."""
+        return not self._editing or self.edit.document().isEmpty()
+
     def _step(self, change, *args, **kwargs) -> None:
-        """Änderung als eigener Rückgängig-Schritt: vorher Getipptes festhalten, danach das Neue."""
+        """Änderung als eigener Rückgängig-Schritt: vorher Getipptes festhalten, danach das Neue.
+        (Im Schreibmodus gehört sie zur laufenden Bearbeitung – das regelt das Hauptfenster.)"""
         if self._updating:
             return
         self.edited.emit()
         change(*args, **kwargs)
         self.edited.emit()
+        self.formatted.emit()
 
     # --- Formatieren ------------------------------------------------------
     def _target(self) -> QTextCursor:
@@ -276,15 +293,18 @@ class TextPanel(Panel):
             fmt.setFontItalic(italic)
         if underline is not None:
             fmt.setFontUnderline(underline)
-        if not self.edit.textCursor().hasSelection():   # ganzer Text: Grundformat anpassen
+        selected = self.edit.textCursor().hasSelection()
+        whole = not selected and self._whole_text()
+        if whole:                                       # ganzer Text: Grundformat anpassen
             for key, value in (("family", family), ("pt", size), ("bold", bold),
                                ("italic", italic), ("underline", underline)):
                 if value is not None:
                     self._base[key] = value
         self._formatting = True
         try:
-            self._target().mergeCharFormat(fmt)
-            if not self.edit.textCursor().hasSelection():
+            if selected or whole:
+                self._target().mergeCharFormat(fmt)
+            if not selected:
                 self.edit.mergeCurrentCharFormat(fmt)   # Weitertippen in gleicher Formatierung
         finally:
             self._formatting = False
@@ -323,6 +343,13 @@ class TextPanel(Panel):
         if self._updating:
             return
         selected = self.edit.textCursor().hasSelection()
+        if not selected and not self._whole_text():     # Schreibmodus: nur fürs Weitertippen
+            pt = self._props(self.edit.currentCharFormat())["pt"]
+            fmt = QTextCharFormat()
+            fmt.setFontPointSize(min(max(self._step_pt(pt, direction), MIN_PT), MAX_PT))
+            self.edit.mergeCurrentCharFormat(fmt)
+            self._apply()
+            return
         cursor = self._target()
         start, end = cursor.selectionStart(), cursor.selectionEnd()
         document = self.edit.document()
@@ -360,8 +387,10 @@ class TextPanel(Panel):
         self._apply()
 
     def _align(self, key: str) -> None:
+        """Textposition der Absätze in der Markierung bzw. – im Schreibmodus ohne Markierung –
+        des Absatzes an der Schreibmarke; sonst aller Absätze."""
         cursor = self.edit.textCursor()
-        if not cursor.hasSelection():
+        if not cursor.hasSelection() and self._whole_text():
             cursor.select(QTextCursor.SelectionType.Document)
         fmt = cursor.blockFormat()
         fmt.setAlignment(_ALIGN_TO_QT[key])
@@ -567,6 +596,19 @@ class TextPanel(Panel):
         for w in widgets:
             w.blockSignals(False)
 
+    def typing_scale(self) -> float:
+        """Schriftgröße fürs Weitertippen relativ zur Schrift, nach der die Schreibmarke im
+        Zeilensatz bemessen ist (Zeichen davor, am Absatzanfang danach, leerer Absatz:
+        Grundgröße); 1.0 mit Markierung oder ohne eigenes Format fürs Weitertippen."""
+        cursor = self.edit.textCursor()
+        if cursor.hasSelection():
+            return 1.0
+        probe = QTextCursor(self.edit.document())     # Format im Text, nicht das zum Tippen
+        probe.setPosition(cursor.position())
+        here = (self._base["pt"] if probe.block().length() <= 1
+                else self._props(probe.charFormat())["pt"])
+        return self._props(self.edit.currentCharFormat())["pt"] / here
+
     def _selection_sizes(self) -> set[float]:
         """Verschiedene Größen innerhalb der Markierung (leer ohne Markierung)."""
         cursor = self.edit.textCursor()
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index ee5b87d..11abbf4 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -22,7 +22,8 @@ from ..printer import DEFAULT_MODEL
 from ..settings import Settings, save_settings
 from .widgets import DoubleSpinBox, SpinBox
 
-SCOPE_NAMES = {"global": "Global", "canvas": "Arbeitsfläche", "text": "Text"}
+SCOPE_NAMES = {"global": "Global", "canvas": "Arbeitsfläche", "edit": "Schreibmodus"}
+FIXED_TIP = "Kürzel fest – nicht änderbar"
 CONFLICT_COLOR = QColor("#FF0000")
 COL_ACTION, COL_SCOPE, COL_KEYS, COL_RESET = range(4)
 DIALOG_SIZE = (760, 680)     # Wunschgröße: Kürzel-Tabelle mit ungekürzten Aktionsnamen
@@ -172,7 +173,11 @@ class SettingsDialog(QDialog):
                 item.setFlags(fixed)
                 table.setItem(row, column, item)
             item = QTableWidgetItem()
-            item.setFlags(fixed | Qt.ItemFlag.ItemIsEditable)
+            if entry.fixed:
+                item.setFlags(fixed)
+                item.setToolTip(FIXED_TIP)
+            else:
+                item.setFlags(fixed | Qt.ItemFlag.ItemIsEditable)
             table.setItem(row, COL_KEYS, item)
             self._show_keys(entry.id)
         # gleiche Zeilenhöhe, ob mit Knopf „Standard“ oder ohne
diff --git a/src/labelwerk/gui/text_edit_mode.py b/src/labelwerk/gui/text_edit_mode.py
index a96ea18..0d2bf13 100644
--- a/src/labelwerk/gui/text_edit_mode.py
+++ b/src/labelwerk/gui/text_edit_mode.py
@@ -7,32 +7,55 @@ Zeilensatz desselben Renders (``RenderedObject.layout``) um – Vorschau = Druck
 beim Tippen. Positionen: Editor in UTF-16-Einheiten, Zeilensatz in Zeichen
 (``render.to_utf16``/``from_utf16``).
 
-Start und Ende samt Rückgängig-Schritt steuert das Hauptfenster (``MainWindow.edit_text``,
-``finish_editing``); die Sitzung meldet nur, dass sie enden soll (``end_requested``).
+Im Schreibmodus wirken die Tasten des Editors (Pfeile, Pos1/Ende, Entf, Strg+A/C/X/V/Z …);
+Auf/Ab folgen den Zeilen auf dem Etikett, Tab bleibt ohne Wirkung (Tabulatoren druckt
+labelwerk nicht, und der Fokus soll den Text nicht verlassen). Strg+Z geht wie der Knopf
+im Dokument weiter, wenn im Editor nichts mehr zurückzunehmen ist. Ein Rahmen ohne feste Größe wächst an der Kante
+seiner Textposition (``layout.anchor_after_edit``). Start und Ende samt Rückgängig-Schritt
+(eine Bearbeitung = ein Schritt) steuert das Hauptfenster (``MainWindow.edit_text``,
+``finish_editing``).
 """
 from __future__ import annotations
 
-from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRect, QRectF, Qt, Signal
-from PySide6.QtGui import QGuiApplication, QTextCursor, QTextDocument
+from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRect, QRectF, Qt, QTimer
+from PySide6.QtGui import QGuiApplication, QKeySequence, QTextCursor, QTextDocument
+from PySide6.QtWidgets import QAbstractButton, QApplication
 
 from .. import layout
 from ..render import PT, RenderedObject, TextLayout, from_utf16, to_utf16
 
+_VERTICAL = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}
+_TABS = (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
+
 
 class TextEditSession(QObject):
     """Schreibmodus für höchstens ein Textobjekt (``index``) des Hauptfensters."""
 
-    end_requested = Signal()          # Esc: Schreibmodus soll enden
-
     def __init__(self, window):
         super().__init__(window)
         self._window = window
         self._canvas = window.canvas
-        self._editor = window.panel("text").edit
+        self._panel = window.panel("text")
+        self._editor = self._panel.edit
         self.index: int | None = None
+        self._goal: tuple[float, int] | None = None   # Auf/Ab: Ziel-x und Position danach
+        self._quiet = False                       # Anzeige erst, wenn das Objekt steht
         self._canvas.edit_pressed.connect(self._press)
+        self._canvas.edit_dragged.connect(self._drag)
+        self._canvas.edit_double_clicked.connect(self._select_word)
         for signal in (self._editor.cursorPositionChanged, self._editor.selectionChanged):
             signal.connect(self.update_marks)
+        # nach einem Knopf des Panels bzw. wenn die Liste von „Schrift“/Größe zugeht oder
+        # dort Enter fällt, weiter an der Schreibmarke tippen – Pfeiltasten im Feld bleiben dort
+        self._panel.formatted.connect(self._return_focus_from_button)
+        self._popups = []
+        for combo in (self._panel.family, self._panel.size):
+            popup = combo.view().window()
+            popup.installEventFilter(self)
+            self._popups.append(popup)
+            if combo.lineEdit() is not None:
+                combo.lineEdit().returnPressed.connect(self._return_focus)
+        QApplication.instance().focusChanged.connect(self._focus_changed)
         self._editor.installEventFilter(self)
 
     @property
@@ -44,8 +67,10 @@ class TextEditSession(QObject):
         """Schreibmodus für Objekt ``index`` (gewählt, im Text-Panel): Editor neu aus dem
         Modell, Tastaturfokus hinein, Schreibmarke an ``point`` (Druckpunkte in Leserichtung,
         z. B. Doppelklick) oder ans Textende."""
-        self._window.panel("text").refresh()      # Editor = Modell, eigenes Rückgängig ab hier
+        self._panel.refresh()                      # Editor = Modell, eigenes Rückgängig ab hier
         self.index = index
+        self._goal = None
+        self._panel.set_editing(True)
         self._editor.caret_rect = self._caret_rect
         self._canvas.set_editing(index)
         self._canvas.setFocusProxy(self._editor)   # Klick auf die Fläche: Fokus bleibt im Editor
@@ -57,6 +82,7 @@ class TextEditSession(QObject):
         else:
             cursor.setPosition(position)
         self._editor.setTextCursor(cursor)
+        self._canvas.set_caret_focus(self._editor.hasFocus())
         self.update_marks()
 
     def end(self) -> int | None:
@@ -68,6 +94,7 @@ class TextEditSession(QObject):
         cursor = self._editor.textCursor()
         cursor.clearSelection()                    # Formatieren wirkt wieder auf den ganzen Rahmen
         self._editor.setTextCursor(cursor)
+        self._panel.set_editing(False)
         self._editor.caret_rect = None
         self._canvas.set_editing(None)
         self._canvas.setFocusProxy(None)
@@ -77,15 +104,39 @@ class TextEditSession(QObject):
 
     def content_changed(self) -> None:
         """Text oder Format geändert: sofort neu rendern, damit Schreibmarke und Bild zum
-        selben Zeilensatz gehören."""
-        if self.active:
-            self._window.render_now()
+        selben Zeilensatz gehören. Ein Rahmen mit Position und ohne feste Größe wächst dabei
+        an der Kante seiner Textposition (die Oberkante der ersten Zeile bleibt); ohne
+        Position bleibt der Text mittig, eine feste Rahmengröße passt ihn wie bisher ein."""
+        if not self.active:
+            return
+        window, index = self._window, self.index
+        obj = window.doc.objects[index]
+        anchored = obj.positioned and not obj.fit and index < len(window.rendered)
+        old = window.rendered[index] if anchored else None   # wie zuletzt angezeigt
+        self._quiet = True
+        try:
+            window.render_now()                        # neuer Text, noch an der alten Stelle
+            new = window.rendered[index] if index < len(window.rendered) else None
+            if (old is not None and new is not None and new is not old
+                    and old.layout is not None and new.layout is not None):
+                position = layout.anchor_after_edit(obj, old, new)
+                if position != (obj.x_mm, obj.y_mm):
+                    obj.x_mm, obj.y_mm = position
+                    window.render_now()
+                    # der Zeilensatz hängt nicht von der Lage ab (relativ zum Rahmen): die
+                    # schon gemessenen Zeichengrenzen weiter nutzen statt neu zu messen
+                    window.rendered[index].layout = new.layout
+        finally:
+            self._quiet = False
+        self.update_marks()
 
     # --- Anzeige ------------------------------------------------------------
     def update_marks(self) -> None:
         """Schreibmarke, Markierung und Rahmen aus Editor und aktuellem Zeilensatz an die
         Arbeitsfläche geben. Passt der Zeilensatz (noch) nicht zum Editor – das Rendern
         folgt gleich bzw. ist gescheitert –, bleibt die bisherige Anzeige."""
+        if self._quiet:
+            return
         current = self._current()
         if current is None:
             return
@@ -94,12 +145,18 @@ class TextEditSession(QObject):
         pos = from_utf16(text, cursor.position())
         anchor = from_utf16(text, cursor.anchor())
         x, top, height = text_layout.caret(pos)
+        scale = self._panel.typing_scale()
+        if abs(scale - 1) > 1e-6:                     # Weitertippen in anderer Größe (A⁺ …)
+            baseline = next(line.baseline for line in text_layout.lines
+                            if line.start <= pos <= line.end)
+            top, height = baseline - (baseline - top) * scale, height * scale
         caret = QLineF(_label(rendered, rotation, x, top),
                        _label(rendered, rotation, x, top + height))
-        marked = ([_label_rect(rendered, rotation, *rect)
+        frame = self._frame(rendered, text_layout, rotation, x, top, height)
+        # ein markierter Absatzwechsel am Ende der breitesten Zeile endet am Rahmen
+        marked = ([_label_rect(rendered, rotation, *rect).intersected(frame)
                    for rect in text_layout.selection_rects(anchor, pos)] if anchor != pos else [])
-        self._canvas.set_edit_marks(self._frame(rendered, rotation, x, top, height),
-                                    caret, marked)
+        self._canvas.set_edit_marks(frame, caret, marked)
         if self._editor.hasFocus():
             QGuiApplication.inputMethod().update(Qt.InputMethodQuery.ImCursorRectangle)
 
@@ -112,12 +169,20 @@ class TextEditSession(QObject):
         return QRect(top_left.x(), top_left.y(), max(1, round(rect.width())),
                      max(1, round(rect.height())))
 
-    def _frame(self, rendered: RenderedObject, rotation: int, x: float, top: float,
-               height: float) -> QRectF:
-        """Rahmen des Objekts; ein leerer Text bekommt einen Platzhalter (halbe Zeile breit)
-        um die Schreibmarke – je nach Textposition rechts, mittig oder links von ihr."""
+    def _frame(self, rendered: RenderedObject, text_layout: TextLayout, rotation: int,
+               x: float, top: float, height: float) -> QRectF:
+        """Rahmen im Schreibmodus: Tintenbox des Objekts samt den Zeilen von Ober- bis
+        Unterlänge, damit Schreibmarke und Markierung darin liegen. Ein leerer Text bekommt
+        einen Platzhalter (halbe Zeile breit) um die Schreibmarke – je nach Textposition
+        rechts, mittig oder links von ihr."""
         if rendered.w and rendered.h:
-            return QRectF(rendered.x, rendered.y, rendered.w, rendered.h)
+            lines = text_layout.lines
+            left = min(line.stops[0] for line in lines)
+            right = max(line.stops[-1] for line in lines)
+            bottom = max(line.top + line.height for line in lines)
+            box = _label_rect(rendered, rotation, left, lines[0].top, right - left,
+                              bottom - lines[0].top)
+            return box.united(QRectF(rendered.x, rendered.y, rendered.w, rendered.h))
         width = rendered.base_pt * PT / 2
         obj = self._window.doc.objects[self.index]
         align = obj.paragraphs[0].align if obj.paragraphs else "left"
@@ -148,20 +213,85 @@ class TextEditSession(QObject):
 
     def _press(self, point: QPointF, extend: bool) -> None:
         """Klick in den Rahmen: Schreibmarke dorthin (mit Umschalt: Markierung bis dorthin)."""
+        self._move_to(self._position_at(point), extend)
+        self._editor.setFocus()
+
+    def _drag(self, point: QPointF) -> None:
+        """Ziehen im Rahmen markiert vom Klickpunkt bis hierher."""
+        self._move_to(self._position_at(point), extend=True)
+
+    def _select_word(self, point: QPointF) -> None:
+        """Doppelklick im Schreibmodus markiert das Wort am Punkt."""
         position = self._position_at(point)
+        if position is None:
+            return
+        cursor = self._editor.textCursor()
+        cursor.setPosition(position)
+        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
+        self._editor.setTextCursor(cursor)
+
+    def _move_to(self, position: int | None, extend: bool) -> None:
         if position is None:
             return
         cursor = self._editor.textCursor()
         mode = QTextCursor.MoveMode.KeepAnchor if extend else QTextCursor.MoveMode.MoveAnchor
         cursor.setPosition(position, mode)
         self._editor.setTextCursor(cursor)
-        self._editor.setFocus()
+
+    def _vertical(self, step: int, extend: bool) -> None:
+        """Auf/Ab: in die Zeile darüber/darunter, so nah wie möglich an derselben Stelle auf
+        dem Etikett (der Editor kennt die Zeilen des Etiketts nicht). Über der ersten bzw.
+        unter der letzten Zeile geht es an den Anfang bzw. ans Ende."""
+        current = self._current()
+        if current is None:
+            return
+        _, text_layout, text, _ = current
+        position = self._editor.textCursor().position()
+        pos = from_utf16(text, position)
+        lines = text_layout.lines
+        row = next(i for i, line in enumerate(lines) if line.start <= pos <= line.end)
+        # mehrmals Auf/Ab hintereinander: die Spalte vom Anfang der Folge halten
+        x = (self._goal[0] if self._goal is not None and self._goal[1] == position
+             else text_layout.caret(pos)[0])
+        if 0 <= row + step < len(lines):
+            line = lines[row + step]
+            target = text_layout.hit(x, line.top + line.height / 2)
+        else:
+            target = 0 if step < 0 else lines[-1].end
+        self._move_to(to_utf16(text, target), extend)
+        self._goal = (x, self._editor.textCursor().position())
+
+    def _return_focus(self) -> None:
+        """Nach Formatieren im Panel weiter an der Schreibmarke tippen."""
+        if self.active:
+            self._editor.setFocus()
+
+    def _return_focus_from_button(self) -> None:
+        """Ein Knopf des Panels hat formatiert (Klick nahm ihm den Fokus): zurück zum Text.
+        Felder mit Tastaturbedienung (Schrift, Größe) behalten ihn."""
+        if isinstance(QApplication.focusWidget(), QAbstractButton):
+            self._return_focus()
+
+    def _focus_changed(self, _old, new) -> None:
+        if self.active:
+            self._canvas.set_caret_focus(new is self._editor)
 
     def eventFilter(self, watched, event) -> bool:
-        if (self.active and watched is self._editor and event.type() == QEvent.Type.KeyPress
-                and event.key() == Qt.Key.Key_Escape):
-            self.end_requested.emit()
-            return True
+        if watched in self._popups and event.type() == QEvent.Type.Hide:
+            QTimer.singleShot(0, self._return_focus)   # nachdem Qt den Fokus zurückgegeben hat
+        elif (self.active and watched is self._editor
+              and event.type() == QEvent.Type.KeyPress):
+            if event.key() in _TABS:
+                return True                             # Tab: ohne Wirkung, Fokus bleibt
+            if (event.matches(QKeySequence.StandardKey.Undo)
+                    and not self._editor.document().isUndoAvailable()):
+                self._window.undo()                     # wie der Knopf: weiter im Dokument
+                return True
+            if (event.key() in _VERTICAL
+                    and not event.modifiers() & ~Qt.KeyboardModifier.ShiftModifier):
+                self._vertical(_VERTICAL[event.key()],
+                               bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
+                return True
         return super().eventFilter(watched, event)
 
 
diff --git a/src/labelwerk/shortcuts.py b/src/labelwerk/shortcuts.py
index 3fde55b..26625a8 100644
--- a/src/labelwerk/shortcuts.py
+++ b/src/labelwerk/shortcuts.py
@@ -3,14 +3,16 @@
 Kürzel sind Texte im Qt-Format („Ctrl+Shift+Z“, „Del“, „Shift+Left“); „“ = kein Kürzel.
 Der Kern prüft nur Form und Doppelbelegung, die GUI wandelt mit ``QKeySequence`` um.
 Bereiche: ``global`` (überall), ``canvas`` (Arbeitsfläche hat den Fokus),
-``text`` (Textfeld hat den Fokus). Arbeitsfläche und Textfeld sind nie gleichzeitig aktiv,
-ein globales Kürzel kollidiert dagegen mit jedem Bereich.
+``edit`` (Schreibmodus: der Editor im Text-Panel hat den Fokus – Fett/Kursiv/Unterstrichen
+wirken auch, solange ein anderes Feld des Panels ihn hat). Arbeitsfläche und Schreibmodus
+sind nie gleichzeitig aktiv, ein globales Kürzel kollidiert dagegen mit jedem Bereich.
+Feste Kürzel (``fixed``, z. B. Esc beendet den Schreibmodus) lassen sich nicht ändern.
 """
 from __future__ import annotations
 
 from dataclasses import dataclass
 
-SCOPES = ("global", "canvas", "text")
+SCOPES = ("global", "canvas", "edit")
 
 
 @dataclass(frozen=True)
@@ -18,7 +20,8 @@ class Action:
     id: str          # z. B. "edit.copy"
     name: str        # Anzeigename
     default: str     # Standardkürzel, "" = keins
-    scope: str       # global | canvas | text
+    scope: str       # global | canvas | edit
+    fixed: bool = False   # Kürzel fest, in den Einstellungen nicht änderbar
 
 
 ACTIONS: tuple[Action, ...] = (
@@ -65,13 +68,16 @@ ACTIONS: tuple[Action, ...] = (
     Action("size.same", "Gleiche Größe", "", "canvas"),
     Action("size.width", "Gleiche Breite", "", "canvas"),
     Action("size.height", "Gleiche Höhe", "", "canvas"),
-    Action("text.bold", "Fett", "Ctrl+B", "text"),
-    Action("text.italic", "Kursiv", "Ctrl+I", "text"),
-    Action("text.underline", "Unterstrichen", "Ctrl+U", "text"),
+    Action("text.end_edit", "Schreibmodus beenden", "Esc", "edit", fixed=True),
+    Action("text.bold", "Fett", "Ctrl+B", "edit"),
+    Action("text.italic", "Kursiv", "Ctrl+I", "edit"),
+    Action("text.underline", "Unterstrichen", "Ctrl+U", "edit"),
 )
 
 _BY_ID = {a.id: a for a in ACTIONS}
 _MODIFIERS = ("Ctrl", "Alt", "Shift", "Meta")          # Reihenfolge wie Qt
+# bedienen Textfeld, Tabelle und Dialoge: als Kürzel nicht belegbar (außer als eigener Standard)
+_RESERVED = {"Esc", "Return", "Enter", "Tab", "Backtab", "Shift+Tab"}
 _KEY_ALIASES = {"del": "Del", "delete": "Del", "esc": "Esc", "escape": "Esc",
                 "ins": "Ins", "insert": "Ins", "pgup": "PgUp", "pageup": "PgUp",
                 "pgdown": "PgDown", "pagedown": "PgDown"}
@@ -128,9 +134,10 @@ def normalize(seq: str) -> str:
 
 # --- Verzeichnis anwenden -------------------------------------------------------------
 def effective(overrides: dict[str, str]) -> dict[str, str]:
-    """Wirksame Kürzel aller Aktionen: Standard, überschrieben durch ``overrides``."""
+    """Wirksame Kürzel aller Aktionen: Standard, überschrieben durch ``overrides`` (feste
+    Kürzel bleiben)."""
     mapping = {a.id: a.default for a in ACTIONS}
-    mapping.update({k: v for k, v in overrides.items() if k in _BY_ID})
+    mapping.update({k: v for k, v in overrides.items() if k in _BY_ID and not _BY_ID[k].fixed})
     return mapping
 
 
@@ -154,13 +161,14 @@ def conflicts(mapping: dict[str, str]) -> list[tuple[str, list[str]]]:
 
 
 def without_conflicts(mapping: dict[str, str]) -> tuple[dict[str, str], list[str]]:
-    """Doppelbelegungen auflösen (z. B. von Hand bearbeitete settings.json): Die Aktion, die im
-    Verzeichnis zuerst steht, behält das Kürzel, spätere bekommen keins. ``(Kürzel, Warnungen)``.
+    """Doppelbelegungen auflösen (z. B. von Hand bearbeitete settings.json): Feste Kürzel
+    bleiben immer; sonst behält die Aktion, die im Verzeichnis zuerst steht, das Kürzel,
+    spätere bekommen keins. ``(Kürzel, Warnungen)``.
     """
     clean = dict(mapping)
     kept: list[tuple[str, str]] = []                    # (normalisiertes Kürzel, Aktions-ID)
     warnings: list[str] = []
-    for entry in ACTIONS:
+    for entry in sorted(ACTIONS, key=lambda a: not a.fixed):   # feste zuerst, sonst stabil
         seq = clean.get(entry.id, "")
         if not seq or not is_well_formed(seq):
             continue
@@ -195,6 +203,14 @@ def validate(overrides) -> tuple[dict[str, str], list[str]]:
         elif not isinstance(seq, str) or not is_well_formed(seq):
             warnings.append(f"Tastenkürzel für {action_id!r} ungültig ({seq!r}) – "
                             f"Standard {_BY_ID[action_id].default!r} aktiv.")
+        elif (normalize(seq) in _RESERVED
+              and normalize(seq) != normalize(_BY_ID[action_id].default)):
+            warnings.append(f"Tastenkürzel für {action_id!r} ungültig ({seq}) – Esc, Enter und "
+                            f"Tab sind nicht belegbar; Standard "
+                            f"{_BY_ID[action_id].default!r} aktiv.")
+        elif _BY_ID[action_id].fixed and normalize(seq) != normalize(_BY_ID[action_id].default):
+            warnings.append(f"Tastenkürzel für {action_id!r} ist fest "
+                            f"({_BY_ID[action_id].default}) – Einstellung ignoriert.")
         else:
             clean[action_id] = seq
     return clean, warnings
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `998 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-17-direkt-schreiben-design.md src/labelwerk/gui/actions.py src/labelwerk/gui/canvas.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/text_edit_mode.py src/labelwerk/shortcuts.py tests/gui/test_gui_edit_mode.py tests/gui/test_gui_editbar.py tests/gui/test_gui_settings.py tests/gui/test_gui_textframe.py tests/test_settings.py tests/test_shortcuts.py
git commit -m "GUI: Schreibmodus – Markieren, Tastatur, ein Rückgängig-Schritt, Rahmen wächst an der richtigen Kante, Kürzel-Bereich

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Abnahme (manuell, durch den Nutzer)

- [ ] Text-Werkzeug „A“ + Klick → sofort tippen; Schreibmarke am Klickpunkt, Text wächst nach rechts.
- [ ] Esc / Klick daneben beendet; Doppelklick auf einen Text → Schreibmarke an der Klickstelle.
- [ ] Ziehen markiert, Doppelklick markiert ein Wort; B/I/U, Größe, Schrift wirken auf die Markierung.
- [ ] Pfeile/Pos1/Ende/Entf/Enter im Schreibmodus; außerhalb verschieben die Pfeile das Objekt.
- [ ] Strg+Z nach Esc nimmt die ganze Bearbeitung zurück.
- [ ] Rechtsbündig/zentriert: Text bleibt beim Tippen an seiner Kante; gedrehter Rahmen: Klick trifft die richtige Stelle.
- [ ] Umlaute, tote Tasten (^, ´), Einfügen aus der Zwischenablage.
- [ ] Testdruck.
