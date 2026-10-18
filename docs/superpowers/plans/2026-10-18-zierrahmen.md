# Zierrahmen ums Etikett – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Zierrahmen ums Etikett wie der P-touch „Rahmen“: sechs Linienarten, abgerundet, Strichstärke und Abstände einstellbar, Kreis auf runden Etiketten; automatisch gesetzter Inhalt bleibt im Innenraum.

**Architecture:** `Document.frame` (Qt-frei); der Kern zeichnet den Rahmen als Maske ins Druckbild (Vorschau = Druck) und rechnet automatischen Text und automatische Länge mit dem Innenraum; die GUI zeigt die Maske auf der Arbeitsfläche, stellt den Rahmen im Reiter Papier ein und nutzt den Innenraum beim Ausrichten, Maximieren, Einfügen und Einrasten.

**Tech Stack:** Python ≥ 3.10, Pillow, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-18-zierrahmen-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-frame`), nach jedem Task volle Suite grün mit Exit-Code 0 (1714 → 1785 → 1809); jeder Schritt von einem Reviewer geprüft und korrigiert (Kern: „Nur Ecken“ ohne Platz, Innenraum beim Endlosband, Eckstriche, strengere Tests gegen Mutationen; GUI: getippte Zahl bei Drucken/Speichern, geglätteter Rahmen, Feldbreiten in beiden Designs, Werte bei „Kein“, Einfügen im Innenraum).

**Patches anwenden:** Jeder Task enthält zwei Patches (Tests, Implementierung) im `git diff`-Format. Den Block **byte-genau** in eine Datei außerhalb des Repos schreiben (z. B. per Skript aus diesem Plan extrahieren) und im Repo-Wurzelverzeichnis anwenden: `git apply --whitespace=nowarn /pfad/patch.diff`. Schlägt `git apply` fehl: nicht von Hand nachbauen, sondern melden (BLOCKED).

## Global Constraints

- Neue Felder im Dokument gehören ins Speicherformat (Schema-Test); Dateien sind fremde Eingabe.
- Kern bleibt **Qt-frei** (`document.py`, `render.py`, `layout.py`, `storage.py`); **Vorschau = Druck**.
- Tests ohne Netz, ohne Hardware, ohne echte Nutzerdaten, ohne echte Dialoge; jedes Widget bei `qtbot.addWidget` anmelden.
- Benutzer-Meldungen und Kommentare auf Deutsch.
- Tests: `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – **Exit-Code 0** prüfen, nicht nur „passed“.
- Commit-Nachrichten auf Deutsch, Trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (bzw. das Modell, das den Task umsetzt).

---

### Task 1: Kern – Zierrahmen: Arten, Kreis, Innenraum, Speichern

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/render.py`
- Modify: `src/labelwerk/storage.py`
- Create: `tests/test_frame.py`
- Modify: `tests/test_storage.py`

**Interfaces / Produces:** `document.Frame` (frozen; `FRAME_STYLES`, `FRAME_LINE_MM`, `MAX_FRAME_MM`), `Document.frame`; `render.frame_mask(doc, model, size)`, `render.frame_box(doc, model, size)`, `compose(..., frame)`, `_Sheet.inset/room(inner)`, `_check_room`; `layout.frame_area(doc, model, size)`; `storage.FRAME`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/test_frame.py b/tests/test_frame.py
new file mode 100644
index 0000000..fbfa2ac
--- /dev/null
+++ b/tests/test_frame.py
@@ -0,0 +1,334 @@
+"""Zierrahmen ums Etikett: Arten, Lage im bedruckbaren Bereich, Innenraum, runde Etiketten."""
+import pytest
+
+from labelwerk import layout
+from labelwerk.document import FRAME_STYLES, Document, Frame, TextObject
+from labelwerk.render import Renderer, frame_box, label_size, render_document
+
+# 62x29 senkrecht: 696 × 271 Punkte, Ränder 12 (quer) und 12 (1 mm in Bandlaufrichtung) –
+# Außenkante des Rahmens: x 12 … 683, y 12 … 258; 0,5 mm = 6 Punkte
+LEFT, TOP, RIGHT, BOTTOM = 12, 12, 683, 258
+LW = 6
+
+
+def _image(frame, label="62x29", objects=None, **kw):
+    return render_document(Document(label, objects=objects or [], frame=frame, **kw))
+
+
+def _black(img, x, y) -> bool:
+    return img.getpixel((x, y))[0] == 0
+
+
+def _row(img, y, x0, x1) -> list[bool]:
+    return [_black(img, x, y) for x in range(x0, x1)]
+
+
+def _runs(values: list[bool]) -> int:
+    """Anzahl schwarzer Abschnitte."""
+    return sum(1 for i, v in enumerate(values) if v and (i == 0 or not values[i - 1]))
+
+
+def test_without_frame_the_label_stays_white():
+    assert _image(None).getextrema() == ((255, 255),) * 3
+
+
+def test_single_frame_lies_on_the_printable_edge():
+    img = _image(Frame("single"))
+    for x in (LEFT, LEFT + LW - 1, RIGHT - LW + 1, RIGHT):
+        assert _black(img, x, 130)
+    for x in (LEFT - 1, LEFT + LW, RIGHT - LW, RIGHT + 1):
+        assert not _black(img, x, 130)
+    for y in (TOP, TOP + LW - 1, BOTTOM - LW + 1, BOTTOM):
+        assert _black(img, 300, y)
+    for y in (TOP - 1, TOP + LW, BOTTOM - LW, BOTTOM + 1):
+        assert not _black(img, 300, y)
+
+
+def test_inset_moves_the_frame_inwards():
+    img = _image(Frame("single", inset_mm=2))          # 24 Punkte
+    assert not _black(img, LEFT + 23, 130) and _black(img, LEFT + 24, 130)
+
+
+def test_line_width_follows_line_mm():
+    img = _image(Frame("single", line_mm=1))           # 12 Punkte
+    assert _black(img, LEFT + 11, 130) and not _black(img, LEFT + 12, 130)
+    thin = _image(Frame("single", line_mm=0.1))        # 1 Punkt
+    assert _black(thin, LEFT, 130) and not _black(thin, LEFT + 1, 130)
+
+
+def test_double_frame_has_two_lines_with_a_gap():
+    img = _image(Frame("double"))
+    assert _row(img, 130, LEFT, LEFT + 3 * LW + 1) == [True] * LW + [False] * LW + [True] * LW + [False]
+
+
+def test_thick_thin_frame_is_thick_outside():
+    img = _image(Frame("thick_thin"))
+    assert _row(img, 130, LEFT, LEFT + 4 * LW + 1) == ([True] * 2 * LW + [False] * LW + [True] * LW
+                                                        + [False])
+
+
+@pytest.mark.parametrize("style", ["dashed", "dotted"])
+def test_dashed_and_dotted_frames_are_interrupted_lines_on_the_band(style):
+    img = _image(Frame(style))
+    top = _row(img, TOP + LW // 2, LEFT, RIGHT + 1)
+    assert _runs(top) >= 20 and not all(top)
+    assert _black(img, LEFT + LW // 2, TOP + LW // 2)            # Ecke ist besetzt
+    inner = img.crop((LEFT + LW, TOP + LW, RIGHT - LW + 1, BOTTOM - LW + 1))
+    assert inner.getextrema() == ((255, 255),) * 3                # nichts innerhalb der Linie
+    outside = [_black(img, x, TOP - 1) for x in range(0, 696)]
+    assert not any(outside)
+
+
+def test_dashes_are_longer_than_dots():
+    dashed = _row(_image(Frame("dashed")), TOP + LW // 2, LEFT, RIGHT + 1)
+    dotted = _row(_image(Frame("dotted")), TOP + LW // 2, LEFT, RIGHT + 1)
+    assert sum(dashed) > sum(dotted)
+    assert _runs(dotted) > _runs(dashed)
+
+
+def test_corners_frame_only_draws_the_corners():
+    img = _image(Frame("corners"))                     # Schenkel 4 mm = 47 Punkte
+    assert _black(img, LEFT, TOP + 46) and not _black(img, LEFT, TOP + 47)
+    assert _black(img, LEFT + 46, TOP) and not _black(img, LEFT + 47, TOP)
+    assert not _black(img, LEFT, 130) and not _black(img, 300, TOP)
+    assert _black(img, RIGHT, BOTTOM) and _black(img, RIGHT, TOP) and _black(img, LEFT, BOTTOM)
+
+
+def test_corner_legs_are_at_most_a_quarter_of_the_shorter_side():
+    img = _image(Frame("corners"), label="23x23")      # 202 × 202, Rahmen 178 → Schenkel 44
+    assert _black(img, LEFT, TOP + 43) and not _black(img, LEFT, TOP + 44)
+
+
+@pytest.mark.parametrize("style", ["single", "double", "thick_thin", "dashed", "dotted", "corners"])
+def test_rounded_frames_leave_the_corner_free(style):
+    img = _image(Frame(style, rounded=True))           # Eckradius 2 mm = 24 Punkte
+    assert not _black(img, LEFT, TOP) and not _black(img, LEFT + 2, TOP + 2)
+    assert any(_black(img, x, y) for x in range(LEFT, LEFT + LW) for y in range(TOP + 24, TOP + 60))
+
+
+def test_round_label_gets_a_circle():
+    img = _image(Frame("single"), label="d24")        # 236 × 236, Ränder 12
+    assert _black(img, 12, 118) and _black(img, 118, 12) and _black(img, 223, 118)
+    assert not _black(img, 30, 30)                     # Ecke außerhalb des Kreises
+    assert not _black(img, 118, 118)
+
+
+@pytest.mark.parametrize("style", ["corners", "dashed"])
+def test_round_label_ignores_corners_and_rounding(style):
+    rounded = _image(Frame(style, rounded=True), label="d24")
+    plain = _image(Frame("single" if style == "corners" else style), label="d24")
+    assert rounded.tobytes() == plain.tobytes()
+
+
+def test_auto_length_grows_by_the_frame():
+    text = [TextObject("Hallo\nWelt\nZeile drei", size_pt=20)]     # feste Größe: nur der Rahmen zählt
+    plain = label_size(Document("62", objects=text))
+    framed = label_size(Document("62", objects=text, frame=Frame("single")))
+    assert framed == (plain[0], plain[1] + 2 * (LW + 12))        # Linie + 1 mm Innenabstand
+    img = _image(Frame("single"), label="62", objects=text)
+    assert _black(img, 300, framed[1] - 13) and not _black(img, 300, framed[1] - 12)
+
+
+def test_automatic_text_stays_inside_the_frame_and_shrinks():
+    objects = [TextObject("WWWWWWWWWWWWWWWWWWWW")]
+    plain = Renderer().render(Document("62x29", objects=objects))
+    framed = Renderer().render(Document("62x29", objects=objects, frame=Frame("single")))
+    assert framed.objects[0].base_pt < plain.objects[0].base_pt
+    inner = 12 + LW + 12
+    img = framed.image
+    for x in list(range(LEFT + LW, inner)) + list(range(696 - inner, RIGHT - LW + 1)):
+        assert not any(_black(img, x, y) for y in range(TOP + LW, BOTTOM - LW + 1)), x
+
+
+def test_text_alignment_starts_at_the_inner_edge():
+    """Linksbündig beginnt am Innenraum: Rand + Linie + Innenabstand statt nur am Rand."""
+    from labelwerk.document import Paragraph, Span
+
+    def left_ink(frame):
+        obj = TextObject([Paragraph([Span("links")], "left")], size_pt=12)
+        img = _image(frame, objects=[obj]).convert("L")
+        start = LEFT + LW if frame else 0              # mit Rahmen: die Linie nicht mitzählen
+        inside = img.crop((start, TOP + LW, RIGHT - LW + 1, BOTTOM - LW + 1))
+        return start + inside.point(lambda v: 255 - v).getbbox()[0]
+    assert left_ink(Frame("single")) - left_ink(None) == LW + 12
+
+
+def test_positioned_objects_keep_their_place():
+    objects = [TextObject("A", size_pt=12, x_mm=5, y_mm=5)]
+    plain = Renderer().render(Document("62x29", objects=objects)).objects[0]
+    framed = Renderer().render(Document("62x29", objects=objects, frame=Frame("single"))).objects[0]
+    assert (framed.x, framed.y, framed.w, framed.h) == (plain.x, plain.y, plain.w, plain.h)
+
+
+def test_frame_that_leaves_no_room_gives_a_message():
+    with pytest.raises(ValueError, match="Rahmen passt nicht aufs Etikett"):
+        _image(Frame("single", inset_mm=10, padding_mm=10), label="d12")
+
+
+@pytest.mark.parametrize("frame, message", [
+    (Frame("wave"), "Unbekannte Rahmenart"),
+    (Frame("single", line_mm=5), "Strichstärke"),
+    (Frame("single", line_mm=0), "Strichstärke"),
+    (Frame("single", inset_mm=-1), "Abstand zum Rand"),
+    (Frame("single", padding_mm=11), "Innenabstand"),
+    (Frame("single", line_mm=float("nan")), "Strichstärke"),
+])
+def test_invalid_frames_give_german_messages(frame, message):
+    with pytest.raises(ValueError, match=message):
+        _image(frame)
+
+
+@pytest.mark.parametrize("style", FRAME_STYLES)
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_renderer_matches_the_print_image(style, orientation):
+    doc = Document("62", objects=[TextObject("Text"), TextObject("B", size_pt=10, x_mm=3, y_mm=2)],
+                   orientation=orientation, frame=Frame(style, rounded=True))
+    renderer = Renderer()
+    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()
+    doc.frame = Frame("double", padding_mm=3)
+    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()
+    doc.frame = None
+    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()
+
+
+def test_frame_box_is_the_inner_room():
+    doc = Document("62x29", frame=Frame("single"))
+    assert frame_box(doc, size=(696, 271)) == (30, 30, 696 - 60, 271 - 60)
+    assert frame_box(Document("62x29"), size=(696, 271)) is None
+    wide = Document("62x29", orientation="horizontal", margin_mm=3, frame=Frame("double"))
+    pad = 3 * LW + 12
+    assert frame_box(wide, size=(271, 696)) == (35 + pad, 12 + pad, 271 - 70 - 2 * pad,
+                                                696 - 24 - 2 * pad)
+
+
+def test_frame_area_in_mm():
+    doc = Document("62x29", frame=Frame("single"))
+    area = layout.frame_area(doc, size=(696, 271))
+    assert area == layout.Rect(30 * 25.4 / 300, 30 * 25.4 / 300, 636 * 25.4 / 300, 211 * 25.4 / 300)
+    assert layout.frame_area(Document("62x29"), size=(696, 271)) is None
+
+
+# --- Nachbesserungen nach dem Review ------------------------------------------------------
+def test_dashed_corner_is_filled_to_the_outer_edge():
+    img = _image(Frame("dashed", line_mm=2))
+    for x, y in ((LEFT, TOP), (RIGHT, TOP), (LEFT, BOTTOM), (RIGHT, BOTTOM)):
+        assert _black(img, x, y)
+
+
+def _lengths_of_runs(values: list[bool]) -> tuple[list[int], list[int]]:
+    """Längen der schwarzen und der weißen Abschnitte (ohne den ersten und letzten)."""
+    runs, current, length = [], values[0], 0
+    for v in values:
+        if v == current:
+            length += 1
+        else:
+            runs.append((current, length))
+            current, length = v, 1
+    runs.append((current, length))
+    inner = runs[1:-1]
+    return [n for black, n in inner if black], [n for black, n in inner if not black]
+
+
+def test_dashes_are_three_line_widths_with_gaps_of_two():
+    lw = 12                                            # 1 mm
+    row = _row(_image(Frame("dashed", line_mm=1)), TOP + lw // 2, LEFT, RIGHT + 1)
+    dashes, gaps = _lengths_of_runs(row)
+    assert all(abs(n - 3 * lw) <= 2 for n in dashes), dashes
+    assert all(abs(n - 2 * lw) <= 2 for n in gaps), gaps
+
+
+def test_dots_are_two_line_widths_apart():
+    lw = 12
+    row = _row(_image(Frame("dotted", line_mm=1)), TOP + lw // 2, LEFT, RIGHT + 1)
+    starts = [i for i, v in enumerate(row) if v and (i == 0 or not row[i - 1])]
+    steps = [b - a for a, b in zip(starts, starts[1:])]
+    assert all(abs(step - 2 * lw) <= 1 for step in steps), steps
+
+
+def _first_black(img, x, y0):
+    return next(y for y in range(y0, img.height) if _black(img, x, y))
+
+
+def test_corner_radius_is_two_millimetres():
+    img = _image(Frame("single", rounded=True))        # Radius 24 Punkte, Linie 6
+    assert _first_black(img, LEFT, TOP) == TOP + 20    # Bogen trifft die Kante kurz vor 24
+
+
+def test_corner_radius_is_at_most_a_quarter_of_the_shorter_side():
+    doc = Document("12", objects=[TextObject("A", size_pt=6)], frame=Frame("single", rounded=True))
+    img = render_document(doc)                         # quer 82 Punkte → Radius 20
+    assert _first_black(img, 12, 12) == 12 + 16
+
+
+def test_double_rounded_lines_stay_concentric():
+    img = _image(Frame("double", rounded=True))
+    diagonal = [_black(img, LEFT + t, TOP + t) for t in range(0, 40)]
+    dashes, gaps = _lengths_of_runs([False] + diagonal + [False])
+    assert len(dashes) == 2 and 3 <= gaps[0] <= 6, (dashes, gaps)
+
+
+def test_round_label_inner_room_is_the_square_in_the_circle():
+    # Ø 212, Linie 6, Innenabstand 12 → Radius 88 → Quadrat 124
+    assert frame_box(Document("d24", frame=Frame()), size=(236, 236)) == (56, 56, 124, 124)
+
+
+def test_corners_without_room_give_a_message():
+    with pytest.raises(ValueError, match="Rahmen passt nicht aufs Etikett"):
+        render_document(Document("62", frame=Frame("corners", inset_mm=5.5, line_mm=0.1,
+                                                    padding_mm=0)))
+
+
+def test_endless_label_keeps_room_inside_the_frame():
+    """Leeres Endlosband oder nur frei platzierte Objekte: das Etikett wird lang genug, dass im
+    Rahmen Platz bleibt – nie ein negativer Innenraum."""
+    for objects in ([], [TextObject("A", size_pt=10, x_mm=2, y_mm=1)]):
+        doc = Document("62", objects=objects, frame=Frame("single", inset_mm=10, padding_mm=10,
+                                                          line_mm=3))
+        size = label_size(doc)
+        assert frame_box(doc, size=size)[3] >= 1
+        render_document(doc)
+
+
+def test_frame_check_only_on_the_render_path():
+    """Ränder und bedruckbarer Bereich lassen sich auch ohne Platz im Rahmen bestimmen –
+    die GUI ruft sie außerhalb des Renderns auf."""
+    from labelwerk.render import label_margins
+    doc = Document("d12", objects=[TextObject("A")], frame=Frame("single", inset_mm=10))
+    assert label_margins(doc) == (12, 12)
+    assert layout.printable_area(doc, size=(94, 94)).w > 0
+    with pytest.raises(ValueError, match="Rahmen passt nicht"):
+        Renderer().render(doc)
+
+
+def test_rounded_must_be_a_bool():
+    with pytest.raises(ValueError, match="abgerundet"):
+        _image(Frame("single", rounded="ja"))
+
+
+def test_renderer_follows_padding_on_a_fixed_label():
+    """Innenabstand ändert die automatische Schrift auf festem Etikett – derselbe Renderer
+    muss neu messen (Rahmen gehört zum Kontext)."""
+    doc = Document("62x29", objects=[TextObject("WWWWWWWWWWWWWWWWWWWW")], frame=Frame("single"))
+    renderer = Renderer()
+    first = renderer.render(doc).objects[0].base_pt
+    doc.frame = Frame("single", padding_mm=8)
+    result = renderer.render(doc)
+    assert result.objects[0].base_pt < first
+    assert result.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_renderer_follows_the_margin_at_the_same_size():
+    doc = Document("62x29", objects=[TextObject("A", size_pt=10, x_mm=20, y_mm=10)],
+                   frame=Frame("single"))
+    renderer = Renderer()
+    renderer.render(doc)
+    doc.margin_mm = 3
+    assert renderer.render(doc).image.tobytes() == render_document(doc).tobytes()
+
+
+def test_positioned_fit_object_ignores_the_frame():
+    obj = TextObject("Rahmen", fit=True, x_mm=2, y_mm=2)
+    plain = Renderer().render(Document("62x29", objects=[obj])).objects[0]
+    framed = Renderer().render(Document("62x29", objects=[obj], frame=Frame("double", padding_mm=5))
+                               ).objects[0]
+    assert (framed.base_pt, framed.w, framed.h) == (plain.base_pt, plain.w, plain.h)
diff --git a/tests/test_storage.py b/tests/test_storage.py
index 4717188..41ade63 100644
--- a/tests/test_storage.py
+++ b/tests/test_storage.py
@@ -6,7 +6,7 @@ import pytest
 from PIL import Image, ImageDraw
 
 from labelwerk import storage
-from labelwerk.document import Document, ImageObject, Paragraph, Span, TextObject
+from labelwerk.document import Document, Frame, ImageObject, Paragraph, Span, TextObject
 from labelwerk.render import render_document
 from labelwerk.storage import StorageError, load, save
 
@@ -33,7 +33,9 @@ def _document():
                                     svg=SVG)
     vector.x_mm, vector.y_mm = 5, 20
     return Document("62", length_mm=45, orientation="horizontal", margin_mm=2,
-                    objects=[text, centred, image, vector])
+                    objects=[text, centred, image, vector],
+                    frame=Frame("thick_thin", rounded=True, line_mm=0.4, inset_mm=1.5,
+                                padding_mm=2))
 
 
 def test_roundtrip_gives_the_same_document(tmp_path):
@@ -160,7 +162,8 @@ def test_schemas_cover_every_dataclass_field():
     for cls, schema, extra in ((Span, storage.SPAN, set()), (Paragraph, storage.PARAGRAPH, {"spans"}),
                                (TextObject, storage.TEXT, {"paragraphs"}),
                                (ImageObject, storage.IMAGE, set()),
-                               (Document, storage.DOCUMENT, {"objects"})):
+                               (Frame, storage.FRAME, set()),
+                               (Document, storage.DOCUMENT, {"objects", "frame"})):
         assert {f.name for f in fields(cls)} == set(schema) | extra, cls.__name__
 
 
@@ -261,6 +264,13 @@ def test_deeply_nested_json_is_refused(tmp_path):
     (lambda d: d["document"].update(length_mm=0), "length_mm"),
     (lambda d: d["document"].update(margin_mm=99), "margin_mm"),
     (lambda d: d["document"].update(label_id="999"), "Etikett"),
+    (lambda d: d["document"].update(frame="dick"), "Rahmen"),
+    (lambda d: d["document"]["frame"].update(style="welle"), "style"),
+    (lambda d: d["document"]["frame"].update(line_mm=5), "line_mm"),
+    (lambda d: d["document"]["frame"].update(line_mm=0), "line_mm"),
+    (lambda d: d["document"]["frame"].update(inset_mm=-1), "inset_mm"),
+    (lambda d: d["document"]["frame"].update(padding_mm=10.5), "padding_mm"),
+    (lambda d: d["document"]["frame"].update(rounded="ja"), "rounded"),
     (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="a\nb"),
      "Zeilenumbruch"),
     (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="a b"),
@@ -404,3 +414,33 @@ def test_position_limit_is_the_one_of_the_position_fields():
     data["document"]["objects"][0]["x_mm"] = MAX_POSITION_MM + 0.1
     with pytest.raises(StorageError, match="x_mm"):
         storage.from_dict(data)
+
+
+# --- Zierrahmen ---------------------------------------------------------------------------
+def test_frame_is_saved_as_its_own_entry(tmp_path):
+    path = save(_document(), tmp_path / "r.labelwerk")
+    frame = json.loads(path.read_text())["document"]["frame"]
+    assert frame == {"style": "thick_thin", "rounded": True, "line_mm": 0.4, "inset_mm": 1.5,
+                     "padding_mm": 2}
+
+
+@pytest.mark.parametrize("value", ["missing", None])
+def test_without_frame_entry_there_is_no_frame(tmp_path, value):
+    data = _valid()
+    if value == "missing":
+        data["document"].pop("frame", None)
+    else:
+        data["document"]["frame"] = None
+    assert load(_write(tmp_path, data)).frame is None
+
+
+def test_frame_fields_missing_get_defaults(tmp_path):
+    data = _valid()
+    data["document"]["frame"] = {"style": "dotted"}
+    assert load(_write(tmp_path, data)).frame == Frame("dotted")
+
+
+def test_document_without_frame_saves_null(tmp_path):
+    path = save(Document("62"), tmp_path / "leer.labelwerk")
+    assert json.loads(path.read_text())["document"]["frame"] is None
+    assert load(path).frame is None
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/test_frame.py, neue Fälle in tests/test_storage.py) schlagen fehl (ImportError `Frame`/`frame_box` bzw. fehlendes Schema), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index c0e6a57..9dbe353 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -20,7 +20,7 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - SVG-Dateien sind Vektorbilder: in jeder Größe scharf gerastert (Etappe 3d-2c).
 - Symbole/ClipArt (Etappe 3d-2c): Knopf SYMBOL im Reiter Bild – Fenster „Symbol einfügen“ (bleibt offen; Suche über die ganze Bibliothek, Gruppen Zuletzt verwendet/Favoriten/Elektro/Versand/Sicherheit/Allgemein/Eigene, Doppelklick/Enter/Ziehen fügt ein); Symbole 15 mm, Vektor, zugeschnitten.
 - Datei und Favoriten (Etappe 3c): Reiter DATEI – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“); `labelwerk install-desktop` meldet *.labelwerk an (Doppelklick öffnet).
-- 1714 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- 1785 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -43,6 +43,10 @@ src/labelwerk/
               Vektorbilder (ImageObject.svg): set_svg_rasterizer(fn(svg, size, region)) – die GUI meldet Qt an; gerastert
               wird das Blatt so groß, dass der Ausschnitt den Rahmen füllt (scharf in jeder Größe, _vector_source gecacht);
               ohne Raster-Funktion gilt die Vorschau-PNG
+              Zierrahmen (doc.frame): frame_mask(doc, model, size) (Maske „L“, in compose unter den Objekten), frame_box (Innenraum
+              in Druckpunkten); Außenkante = bedruckbarer Bereich − inset_mm, rund: Kreis; automatisch gesetzter Text und die
+              automatische Länge rechnen mit dem Innenraum (_Sheet.inset/room), frei platzierte Objekte nicht; ohne Innenraum
+              „Rahmen passt nicht aufs Etikett“ (nur beim Rendern geprüft: _check_room; Endlosband wird lang genug)
   fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei
   files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
               crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
@@ -61,13 +65,15 @@ src/labelwerk/
               keep_ratio, dpi (Auflösung der PNG-Bytes), svg (Vektorbild, png = Vorschau); from_image(img, dpi, source, page,
               crop, svg) setzt 1:1-Größe;
               box() (Ausschnitt in Pixeln), natural_mm() (Größe 1:1)
+              Frame (frozen): style FRAME_STYLES (single/double/thick_thin/dashed/dotted/corners), rounded, line_mm 0,1–3,
+              inset_mm/padding_mm 0–10; Document.frame (None = kein Rahmen)
   settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic), `image_crop`/`image_rotate` (Bilder einfügen),
               `symbols_recent` (höchstens 24)/`symbols_favorites` (Symbol-ids), `recent_files` (höchstens 10)/`start_favorite`
               (der Einstellungsdialog reicht sie durch)
   storage.py  Etiketten als Datei (*.labelwerk, JSON versioniert, Bilder Base64): to_dict/from_dict, save (atomar), load;
               Schemata SPAN/PARAGRAPH/TEXT/IMAGE/DOCUMENT (jedes Dataclass-Feld, Test hält gleich); Dateien sind fremde Eingabe:
               Prüfung je Feld nach Art, Wertebereich (endlich, Grenzen) und Struktur → StorageError (deutsch, mit Dateiname),
-              Bilddaten nur PNG (ganz dekodiert, höchstens MAX_PIXELS), Etikett bekannt; Grenzen: Datei ≤ 32 MB und regulär (kein FIFO),
+              Bilddaten nur PNG (ganz dekodiert, höchstens MAX_PIXELS), Rahmen als eigener Eintrag „frame“ (Schema FRAME, null = keiner), Etikett bekannt; Grenzen: Datei ≤ 32 MB und regulär (kein FIFO),
               ≤ 500 Objekte, Rahmenflächen ≤ 100 Mio. Druckpunkte (sonst „Etikett zu groß“), Lage ±MAX_POSITION_MM (document.py, wie die
               GUI-Positionsfelder), font_path nur für vorhandene reguläre Datei; exists() (wirft nie); unbekannte Felder übergangen,
               fehlende = Standard; save atomar (Symlink verfolgt, Rechte bleiben/umask, fsync); add_recent_file
@@ -87,6 +93,7 @@ src/labelwerk/
               Bilder wie Text mit fester Rahmengröße; keep_aspect (Anfasser mit keep_ratio); Schrift-Funktionen: TypeError bei Bildern
               Bild einfügen/einstellen: insert_frame (Mitte bzw. Ablagepunkt, zu groß → proportional eingepasst, Endlosband
               nur quer), set_crop (Maßstab und Lage des Inhalts bleiben), original_size, set_keep_ratio, proportional
+              frame_area(doc, model, size) -> Rect | None (Innenraum des Zierrahmens in mm)
   shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
               without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
   desktop.py  .desktop-Eintrag (Exec … %f, MimeType) + Icon + Dateityp application/x-labelwerk (*.labelwerk, mime/packages,
diff --git a/src/labelwerk/document.py b/src/labelwerk/document.py
index 9b42af2..75e923d 100644
--- a/src/labelwerk/document.py
+++ b/src/labelwerk/document.py
@@ -14,6 +14,10 @@ ROTATIONS = (0, 90, 180, 270)      # Grad im Uhrzeigersinn
 MAX_MARGIN_MM = 20.0
 MAX_POSITION_MM = 999.9            # Lage eines Objekts (Positionsfelder der GUI, auch neben dem Etikett)
 MIN_PT, MAX_PT = 4.0, 100.0
+# Zierrahmen: einfach, doppelt, dick-dünn, gestrichelt, gepunktet, nur Ecken
+FRAME_STYLES = ("single", "double", "thick_thin", "dashed", "dotted", "corners")
+FRAME_LINE_MM = (0.1, 3.0)          # Strichstärke
+MAX_FRAME_MM = 10.0                 # Abstand zum Rand, Innenabstand
 
 
 @dataclass
@@ -183,6 +187,16 @@ def _png(img: Image.Image) -> bytes:
     return buffer.getvalue()
 
 
+@dataclass(frozen=True)
+class Frame:
+    """Zierrahmen ums Etikett (wie der P-touch „Rahmen“) im bedruckbaren Bereich."""
+    style: str = "single"           # FRAME_STYLES
+    rounded: bool = False           # abgerundete Ecken (nicht bei runden Etiketten)
+    line_mm: float = 0.5            # Strichstärke
+    inset_mm: float = 0.0           # Abstand vom bedruckbaren Rand
+    padding_mm: float = 1.0         # Abstand zum Inhalt (automatisch gesetzter Text, Länge)
+
+
 @dataclass
 class Document:
     label_id: str = "62"
@@ -190,6 +204,7 @@ class Document:
     orientation: str = "vertical"     # "vertical" (Text quer zum Band) | "horizontal" (längs)
     margin_mm: float = 1.0            # Rand in Bandlaufrichtung (vorne/hinten)
     objects: list[TextObject | ImageObject] = field(default_factory=list)
+    frame: Frame | None = None        # Zierrahmen; None = keiner
 
     def is_empty(self) -> bool:
         """True, wenn kein Objekt sichtbaren Inhalt hat."""
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index 84e58b3..78f069a 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -15,7 +15,7 @@ from dataclasses import dataclass, field, replace
 
 from .document import MAX_PT, MIN_PT, ROTATIONS, Document, ImageObject, TextObject
 from .labels import DPI, get_label, length_limits
-from .render import (PT, REF_PT, RenderedObject, span_dots, label_margins, label_size,
+from .render import (PT, REF_PT, RenderedObject, frame_box, span_dots, label_margins, label_size,
                      render_object)
 
 ALIGN_MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom")
@@ -777,3 +777,10 @@ def anchor_after_edit(obj: TextObject, old: RenderedObject,
     nx, ny = from_object(new.layout.anchor(align), new, obj.rotation)
     return (round(start.x + _mm(ox - old.x) - _mm(nx - new.x), _DECIMALS),
             round(start.y + _mm(oy - old.y) - _mm(ny - new.y), _DECIMALS))
+
+
+def frame_area(doc: Document, model: str = "QL-600",
+               size: tuple[int, int] | None = None) -> Rect | None:
+    """Innenraum des Zierrahmens in mm (Ausrichten am Etikett, Einrasten); None ohne Rahmen."""
+    box = frame_box(doc, model, size)
+    return None if box is None else Rect(*(_mm(v) for v in box))
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index e98ff66..de70881 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -17,11 +17,12 @@ from collections.abc import Callable
 from dataclasses import dataclass, field
 from functools import cached_property, lru_cache
 
-from PIL import Image, ImageDraw, ImageOps
+from PIL import Image, ImageChops, ImageDraw, ImageOps
 
 from . import fonts, imaging
-from .document import (ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS,
-                       Document, ImageObject, Paragraph, Span, TextObject)
+from .document import (ALIGNMENTS, FRAME_LINE_MM, FRAME_STYLES, MAX_FRAME_MM, MAX_MARGIN_MM,
+                       MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS, Document, Frame, ImageObject,
+                       Paragraph, Span, TextObject)
 from .labels import DPI, get_label, length_limits
 
 MARGIN = 12            # Punkte, ca. 1 mm
@@ -30,6 +31,8 @@ REF_PT = 12.0          # Bezugsgröße für automatische Skalierung von Stücken
 MIN_DOTS = 8           # kleinste Schrift in Druckpunkten
 _LINE_GAP = 4          # wie Pillow multiline_text
 _SLANT = 0.2           # Ersatzkursive: Scherung, wenn die Schrift keine echte Kursive hat
+FRAME_RADIUS_MM = 2.0  # Eckradius abgerundeter Rahmen (höchstens ¼ der kürzeren Seite)
+FRAME_CORNER_MM = 4.0  # Schenkel bei „nur Ecken“ (höchstens ¼ der kürzeren Seite)
 
 
 class TextTooLarge(ValueError):
@@ -134,19 +137,23 @@ def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
     Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
     """
     sheet = _sheet(doc, model)
+    _check_room(sheet)
     preps = [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]]
     width, height = _label_size(sheet, preps)
     return compose([_finish(prep, sheet, width, height) for prep in preps], (width, height),
-                   doc.orientation)
+                   doc.orientation, _frame_mask(sheet, width, height))
 
 
 def compose(rendered: list[RenderedObject], size: tuple[int, int],
-            orientation: str = "vertical") -> Image.Image:
-    """Druckbild aus einzeln gerenderten Objekten (``size`` = Etikett in Leserichtung).
+            orientation: str = "vertical", frame: Image.Image | None = None) -> Image.Image:
+    """Druckbild aus einzeln gerenderten Objekten (``size`` = Etikett in Leserichtung);
+    ``frame``: Maske des Zierrahmens (``frame_mask``), liegt unter den Objekten.
 
     Die Arbeitsfläche zeigt dieselben Objektbilder – so bleibt Vorschau = Druck.
     """
     img = Image.new("RGB", size, "white")
+    if frame is not None:
+        img.paste((0, 0, 0), (0, 0), frame)
     for obj in rendered:
         img.paste((0, 0, 0), (obj.x + obj.image_dx, obj.y + obj.image_dy),
                   ImageOps.invert(obj.image))
@@ -183,6 +190,26 @@ def finish_object(prep: Prepared, doc: Document, size: tuple[int, int],
     return _finish(prep, _sheet(doc, model), *size)
 
 
+def frame_mask(doc: Document, model: str = "QL-600",
+               size: tuple[int, int] | None = None) -> Image.Image | None:
+    """Zierrahmen als Maske (Modus „L“, 255 = Tinte) in Leserichtung; None ohne Rahmen."""
+    if doc.frame is None:
+        return None
+    return _frame_mask(_sheet(doc, model), *(size if size is not None else label_size(doc, model)))
+
+
+def frame_box(doc: Document, model: str = "QL-600",
+              size: tuple[int, int] | None = None) -> tuple[int, int, int, int] | None:
+    """Innenraum des Rahmens (x, y, Breite, Höhe) in Druckpunkten in Leserichtung – dort steht
+    automatisch gesetzter Text; None ohne Rahmen."""
+    if doc.frame is None:
+        return None
+    sheet = _sheet(doc, model)
+    width, height = size if size is not None else label_size(doc, model)
+    ix, iy = sheet.inset()
+    return ix, iy, width - 2 * ix, height - 2 * iy
+
+
 @dataclass
 class Rendered:
     """Ergebnis von ``Renderer.render``: Etikettgröße (Druckpunkte in Leserichtung), die
@@ -220,19 +247,29 @@ class Renderer:
 
     def __init__(self):
         self._cache: dict[int, _Cached] = {}
-        self._composed: tuple = (None, [], None)   # Druckbild und woraus es entstand
+        self._composed: tuple = (None, [], None, None)   # Druckbild und woraus es entstand
+        self._frame: tuple = (None, None)                # Rahmen-Maske und wofür
 
     def render(self, doc: Document, model: str = "QL-600") -> Rendered:
         """Dokument rendern; ``ValueError`` (z. B. ``TextTooLarge``) lässt den Cache stehen."""
+        _check_room(_sheet(doc, model))
         entries = self._prepare_all(doc, model)
         size = label_size(doc, model, prepared=[e.prepared for e in entries])
         objects = self._draw(entries, doc, model, size)
-        return Rendered(size, objects, self._compose(objects, size, doc.orientation))
+        frame = self._frame_mask(doc, model, size)
+        return Rendered(size, objects, self._compose(objects, size, doc.orientation, frame))
+
+    def _frame_mask(self, doc: Document, model: str, size: tuple[int, int]) -> Image.Image | None:
+        """Rahmen-Maske – neu nur, wenn sich Rahmen oder Etikett ändern."""
+        key = (size, model, doc.label_id, doc.orientation, doc.margin_mm, doc.frame)
+        if key != self._frame[0]:
+            self._frame = (key, frame_mask(doc, model, size))
+        return self._frame[1]
 
     def _prepare_all(self, doc: Document, model: str) -> list[_Cached]:
         """Objekte messen; unveränderte kommen aus dem Cache."""
         context = (model, doc.label_id, doc.orientation, doc.margin_mm, doc.length_mm,
-                   _svg_generation)
+                   doc.frame, _svg_generation)
         cache: dict[int, _Cached] = {}
         for obj in doc.objects:
             entry = self._cache.get(id(obj))
@@ -257,19 +294,21 @@ class Renderer:
         return [entry.rendered for entry in entries]
 
     def _compose(self, objects: list[RenderedObject], size: tuple[int, int],
-                 orientation: str) -> Image.Image:
-        """Druckbild – unverändert, solange dieselben Objektbilder auf derselben Größe liegen."""
+                 orientation: str, frame: Image.Image | None) -> Image.Image:
+        """Druckbild – unverändert, solange dieselben Objektbilder und derselbe Rahmen auf
+        derselben Größe liegen."""
         key = (size, orientation)
-        if (key != self._composed[0] or len(objects) != len(self._composed[1])
+        if (key != self._composed[0] or frame is not self._composed[3]
+                or len(objects) != len(self._composed[1])
                 or any(a is not b for a, b in zip(objects, self._composed[1]))):
-            self._composed = (key, list(objects), compose(objects, size, orientation))
+            self._composed = (key, list(objects), compose(objects, size, orientation, frame),
+                              frame)
         return self._composed[2]
 
 
 def label_margins(doc: Document, model: str = "QL-600") -> tuple[int, int]:
     """Ränder (links/rechts, oben/unten) in Druckpunkten in Leserichtung."""
-    sheet = _sheet(doc, model)
-    return (sheet.margin, MARGIN) if sheet.horizontal else (MARGIN, sheet.margin)
+    return _sheet(doc, model).margins()
 
 
 # --- Etikett und Objekte ------------------------------------------------------------
@@ -283,12 +322,34 @@ class _Sheet:
     margin: int                # Rand in Bandlaufrichtung
     min_len: int
     max_len: int
-
-    def room(self) -> tuple[int, int]:
-        """Bedruckbarer Bereich (Breite, Höhe) in Leserichtung; automatische Länge: Höchstlänge."""
-        across = self.across - 2 * MARGIN
-        feed = (self.feed or self.max_len) - 2 * self.margin
-        return (feed, across) if self.horizontal else (across, feed)
+    frame: Frame | None = None
+    round: bool = False        # rundes Etikett: Rahmen ist ein Kreis
+
+    def margins(self) -> tuple[int, int]:
+        """Ränder (links/rechts, oben/unten) in Leserichtung."""
+        return (self.margin, MARGIN) if self.horizontal else (MARGIN, self.margin)
+
+    def inset(self) -> tuple[int, int]:
+        """Abstand des Innenraums vom Etikettrand (links/rechts, oben/unten) in Leserichtung:
+        die Ränder, mit Rahmen zusätzlich Abstand, Linie und Innenabstand (rund: Quadrat im
+        Kreis)."""
+        mx, my = self.margins()
+        if self.frame is None:
+            return mx, my
+        if self.round:
+            inset = (self.across - _circle_room(self)) // 2
+            return inset, inset
+        pad = _dots(self.frame.inset_mm) + _band(self.frame, False) + _dots(self.frame.padding_mm)
+        return mx + pad, my + pad
+
+    def room(self, inner: bool = True) -> tuple[int, int]:
+        """Bedruckbarer Bereich (Breite, Höhe) in Leserichtung; automatische Länge: Höchstlänge.
+        ``inner``: mit Rahmen nur sein Innenraum (für automatisch gesetzten Text)."""
+        width, height = self.across, self.feed or self.max_len
+        if self.horizontal:
+            width, height = height, width
+        ix, iy = self.inset() if inner else self.margins()
+        return width - 2 * ix, height - 2 * iy
 
 
 def _sheet(doc: Document, model: str) -> _Sheet:
@@ -302,8 +363,20 @@ def _sheet(doc: Document, model: str) -> _Sheet:
         feed = min(max(_dots(doc.length_mm), min_len), max_len)
     if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
         margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
+    if doc.frame is not None:
+        _check_frame(doc.frame)
     return _Sheet(doc.label_id, doc.orientation == "horizontal", label.width, feed, margin,
-                  min_len, max_len)
+                  min_len, max_len, doc.frame, label.shape == "round")
+
+
+FRAME_TOO_BIG = "Rahmen passt nicht aufs Etikett – Abstand, Strichstärke oder Innenabstand verkleinern"
+
+
+def _check_room(sheet: _Sheet) -> None:
+    """Rahmen ohne Innenraum → Meldung. Nur beim Rendern geprüft – Ränder und bedruckbarer
+    Bereich bleiben auch dann bestimmbar (die GUI fragt sie außerhalb des Renderns ab)."""
+    if sheet.frame is not None and min(sheet.room()) <= 0:
+        raise ValueError(FRAME_TOO_BIG)
 
 
 def _dots(mm: float) -> int:
@@ -336,7 +409,7 @@ def _prepare(obj: TextObject | ImageObject, sheet: _Sheet) -> Prepared:
                              "rechts, Blocksatz (left, center, right, justify)")
     if obj.rotation not in ROTATIONS:
         raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
-    max_w, max_h = sheet.room()
+    max_w, max_h = sheet.room(inner=not obj.positioned)   # frei platziert: Rahmen gilt nicht
     if obj.rotation in (90, 270):
         max_w, max_h = max_h, max_w
     auto_start = max(10, sheet.across // 5)
@@ -367,6 +440,8 @@ def _label_size(sheet: _Sheet, preps: list[Prepared]) -> tuple[int, int]:
     """Etikettgröße in Leserichtung; automatische Länge aus dem Platzbedarf der Objekte."""
     feed = sheet.feed
     if feed is None:
+        ix, iy = sheet.inset()
+        along = ix if sheet.horizontal else iy     # Rand (+ Rahmen) in Bandlaufrichtung
         needed = 0
         for prep in preps:
             if prep.obj.positioned and prep.obj.is_empty():
@@ -375,9 +450,11 @@ def _label_size(sheet: _Sheet, preps: list[Prepared]) -> tuple[int, int]:
             size = w if sheet.horizontal else h
             if prep.obj.positioned:
                 start = prep.obj.x_mm if sheet.horizontal else prep.obj.y_mm
-                needed = max(needed, _dots(start or 0) + size + sheet.margin)
+                needed = max(needed, _dots(start or 0) + size + along)
             else:
-                needed = max(needed, size + 2 * sheet.margin)
+                needed = max(needed, size + 2 * along)
+        if sheet.frame is not None:            # im Rahmen bleibt immer Platz (kein Innenraum ≤ 0)
+            needed = max(needed, 2 * along + 1)
         feed = min(max(needed, sheet.min_len), sheet.max_len)
     return (feed, sheet.across) if sheet.horizontal else (sheet.across, feed)
 
@@ -405,8 +482,9 @@ def _place(prep: Prepared, sheet: _Sheet, width: int, height: int
         origin = (_dots(obj.x_mm or 0), _dots(obj.y_mm or 0))
     else:                                      # mittig auf dem Etikett wie bisher
         area = (height, width) if turned else (width, height)
-        # Innenrand der Textzeilen: Rand in Bandlaufrichtung, wenn sie längs zum Band laufen
-        start = sheet.margin if sheet.horizontal != turned else MARGIN
+        # Innenrand der Textzeilen: Rand (mit Rahmen: Innenraum) in Richtung der Zeilen
+        ix, iy = sheet.inset()
+        start = iy if turned else ix
         x0, y0, lines = _align(obj, prep.base, lines, prep.box, start, *area)
         fl, ft, fr, fb = _block_box(lines)
         frame = (x0 + fl, y0 + ft, fr - fl, fb - ft)
@@ -980,3 +1058,206 @@ def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
     sheared = mask.transform(mask.size, Image.Transform.AFFINE,
                              (1, _SLANT, -_SLANT * ascent, 0, 1, 0), Image.Resampling.BICUBIC)
     img.paste(0, (round(x) - pad, round(y)), sheared)
+
+
+# --- Zierrahmen ---------------------------------------------------------------------
+def _check_frame(frame: Frame) -> None:
+    if frame.style not in FRAME_STYLES:
+        raise ValueError(f"Unbekannte Rahmenart {frame.style!r} – erlaubt: "
+                         f"{', '.join(FRAME_STYLES)}")
+    if not isinstance(frame.rounded, bool):
+        raise ValueError(f"„abgerundet“ des Rahmens muss ja oder nein sein, nicht {frame.rounded!r}")
+    for value, (low, high), name in ((frame.line_mm, FRAME_LINE_MM, "Strichstärke"),
+                                     (frame.inset_mm, (0.0, MAX_FRAME_MM), "Abstand zum Rand"),
+                                     (frame.padding_mm, (0.0, MAX_FRAME_MM), "Innenabstand")):
+        if (not isinstance(value, (int, float)) or isinstance(value, bool)
+                or not math.isfinite(value) or not low <= value <= high):
+            raise ValueError(f"{name} des Rahmens muss zwischen {_fmt_mm(low)} und "
+                             f"{_fmt_mm(high)} mm liegen")
+
+
+def _fmt_mm(value: float) -> str:
+    return f"{value:g}".replace(".", ",")
+
+
+def _line(frame: Frame) -> int:
+    """Strichstärke in Druckpunkten (mindestens 1)."""
+    return max(1, _dots(frame.line_mm))
+
+
+def _band(frame: Frame, round_label: bool) -> int:
+    """Breite aller Linien zusammen (doppelt: Linie, Lücke, Linie; dick-dünn: 2, 1, 1)."""
+    lw = _line(frame)
+    return {"double": 3 * lw, "thick_thin": 4 * lw}.get(frame.style, lw)
+
+
+def _outer(sheet: _Sheet, width: int, height: int) -> tuple[int, int, int, int]:
+    """Außenkante des Rahmens (x0, y0, x1, y1; Ende ausschließlich) in Leserichtung; rund:
+    das Quadrat um den Kreis."""
+    mx, my = sheet.margins()
+    inset = _dots(sheet.frame.inset_mm)
+    x0, y0, x1, y1 = mx + inset, my + inset, width - mx - inset, height - my - inset
+    if sheet.round:
+        d = min(x1 - x0, y1 - y0)
+        x0, y0 = x0 + (x1 - x0 - d) // 2, y0 + (y1 - y0 - d) // 2
+        x1, y1 = x0 + d, y0 + d
+    return x0, y0, x1, y1
+
+
+def _circle_room(sheet: _Sheet) -> int:
+    """Seite des Quadrats im Kreisrahmen (Innenraum runder Etiketten) in Druckpunkten."""
+    x0, _, x1, _ = _outer(sheet, sheet.across, sheet.across)   # runde Etiketten sind quadratisch
+    radius = (x1 - x0) / 2 - _band(sheet.frame, True) - _dots(sheet.frame.padding_mm)
+    return int(radius * math.sqrt(2)) if radius > 0 else 0
+
+
+def _frame_mask(sheet: _Sheet, width: int, height: int) -> Image.Image | None:
+    """Zierrahmen als Maske (255 = Tinte): Linien liegen ganz innerhalb der Außenkante."""
+    frame = sheet.frame
+    if frame is None:
+        return None
+    lw = _line(frame)
+    box = _outer(sheet, width, height)
+    w, h = box[2] - box[0], box[3] - box[1]
+    style = "single" if sheet.round and frame.style == "corners" else frame.style
+    radius = (min(_dots(FRAME_RADIUS_MM), min(w, h) // 4)
+              if frame.rounded and not sheet.round else 0)
+    mask = Image.new("L", (width, height), 0)
+    draw = ImageDraw.Draw(mask)
+
+    def ring(offset: int, thickness: int) -> None:
+        xy = (box[0] + offset, box[1] + offset, box[2] - 1 - offset, box[3] - 1 - offset)
+        if xy[2] < xy[0] or xy[3] < xy[1]:
+            return
+        if sheet.round:
+            draw.ellipse(xy, outline=255, width=thickness)
+        else:
+            draw.rounded_rectangle(xy, radius=max(0, radius - offset), outline=255,
+                                   width=thickness)
+
+    if style == "double":
+        ring(0, lw)
+        ring(2 * lw, lw)
+    elif style == "thick_thin":
+        ring(0, 2 * lw)
+        ring(3 * lw, lw)
+    else:
+        ring(0, lw)
+    if style == "corners":
+        leg = min(_dots(FRAME_CORNER_MM), min(w, h) // 4)
+        if leg < 2 * lw:                     # sonst blieben nur Quadrate (oder nichts)
+            raise ValueError(FRAME_TOO_BIG)
+        keep = Image.new("L", mask.size, 0)
+        corners = ImageDraw.Draw(keep)
+        for x, y in ((box[0], box[1]), (box[2] - leg, box[1]), (box[0], box[3] - leg),
+                     (box[2] - leg, box[3] - leg)):
+            corners.rectangle((x, y, x + leg - 1, y + leg - 1), fill=255)
+        mask = ImageChops.darker(mask, keep)
+    elif style == "dashed":
+        mask = ImageChops.darker(mask, _dashes(sheet.round, box, radius, lw, mask.size))
+    elif style == "dotted":
+        mask = _dots_mask(sheet.round, box, radius, lw, mask.size)
+    return mask
+
+
+def _sides(box: tuple[int, int, int, int], radius: int, lw: int) -> list[list[tuple[float, float]]]:
+    """Mittellinie eines (abgerundeten) Rechteckrahmens in vier Seiten, je von Eckmitte zu
+    Eckmitte – Striche und Punkte verteilen sich je Seite gleichmäßig, die Ecken sind besetzt."""
+    half = lw / 2
+    x0, y0, x1, y1 = box[0] + half, box[1] + half, box[2] - half, box[3] - half
+    r = max(radius - half, 0.0)
+    centres = {"tl": (x0 + r, y0 + r), "tr": (x1 - r, y0 + r), "br": (x1 - r, y1 - r),
+               "bl": (x0 + r, y1 - r)}
+
+    def arc(corner: str, a0: float, a1: float) -> list[tuple[float, float]]:
+        cx, cy = centres[corner]
+        steps = max(1, math.ceil(r * math.radians(abs(a1 - a0)) / 0.5))
+        return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
+                 cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps)))
+                for i in range(steps + 1)]
+    return [arc("tl", 225, 270) + arc("tr", 270, 315),
+            arc("tr", 315, 360) + arc("br", 0, 45),
+            arc("br", 45, 90) + arc("bl", 90, 135),
+            arc("bl", 135, 180) + arc("tl", 180, 225)]
+
+
+def _lengths(path: list[tuple[float, float]]) -> list[float]:
+    out = [0.0]
+    for (ax, ay), (bx, by) in zip(path, path[1:]):
+        out.append(out[-1] + math.hypot(bx - ax, by - ay))
+    return out
+
+
+def _point(path, lengths, s: float) -> tuple[float, float]:
+    """Punkt der Mittellinie bei Bogenlänge ``s``."""
+    s = min(max(s, 0.0), lengths[-1])
+    for i in range(1, len(path)):
+        if lengths[i] >= s:
+            span = lengths[i] - lengths[i - 1] or 1.0
+            t = (s - lengths[i - 1]) / span
+            (ax, ay), (bx, by) = path[i - 1], path[i]
+            return ax + (bx - ax) * t, ay + (by - ay) * t
+    return path[-1]
+
+
+def _piece(path, lengths, s0: float, s1: float) -> list[tuple[float, float]]:
+    """Stück der Mittellinie zwischen den Bogenlängen ``s0`` und ``s1``."""
+    s0, s1 = max(s0, 0.0), min(s1, lengths[-1])
+    inner = [p for p, s in zip(path, lengths) if s0 < s < s1]
+    return [_point(path, lengths, s0), *inner, _point(path, lengths, s1)]
+
+
+def _dashes(round_label: bool, box, radius: int, lw: int, size) -> Image.Image:
+    """Striche (3 × Strichstärke, Lücke 2 ×, je Seite gleichmäßig) als Maske – breiter als die
+    Linie, geschnitten mit ihr ergeben sich saubere Kanten."""
+    keep = Image.new("L", size, 0)
+    draw = ImageDraw.Draw(keep)
+    if round_label:                          # Kreis: Tortenstücke vom Mittelpunkt aus
+        d = box[2] - box[0]
+        n = max(4, round(math.pi * (d - lw) / (5 * lw)))
+        pad = 2 * lw
+        wedge = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
+        for k in range(n):
+            mid = -90 + 360 * k / n
+            draw.pieslice(wedge, mid - 108 / n, mid + 108 / n, fill=255)   # 60 % der Teilung
+        return keep
+    if radius == 0:                          # Eckstriche bis in die äußere Ecke
+        for x, y in ((box[0], box[1]), (box[2] - lw, box[1]), (box[0], box[3] - lw),
+                     (box[2] - lw, box[3] - lw)):
+            draw.rectangle((x, y, x + lw - 1, y + lw - 1), fill=255)
+    for side in _sides(box, radius, lw):
+        lengths = _lengths(side)
+        total = lengths[-1]
+        m = max(1, round(total / (5 * lw)))
+        period, dash = total / m, 0.6 * total / m
+        for k in range(m + 1):
+            centre = k * period
+            piece = _piece(side, lengths, centre - dash / 2, centre + dash / 2)
+            draw.line(piece, fill=255, width=lw + 4, joint="curve")
+    return keep
+
+
+def _dots_mask(round_label: bool, box, radius: int, lw: int, size) -> Image.Image:
+    """Runde Punkte (Durchmesser = Strichstärke, Abstand 2 ×) auf der Mittellinie."""
+    mask = Image.new("L", size, 0)
+    draw = ImageDraw.Draw(mask)
+    half = lw / 2
+    points = []
+    if round_label:
+        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
+        r = (box[2] - box[0]) / 2 - half
+        n = max(8, round(2 * math.pi * r / (2 * lw)))
+        points = [(cx + r * math.cos(2 * math.pi * k / n - math.pi / 2),
+                   cy + r * math.sin(2 * math.pi * k / n - math.pi / 2)) for k in range(n)]
+    else:
+        for side in _sides(box, radius, lw):
+            lengths = _lengths(side)
+            m = max(1, round(lengths[-1] / (2 * lw)))
+            points += [_point(side, lengths, lengths[-1] * k / m) for k in range(m)]
+    for x, y in points:
+        if lw <= 2:
+            draw.rectangle((math.floor(x - half), math.floor(y - half),
+                            math.floor(x - half) + lw - 1, math.floor(y - half) + lw - 1), fill=255)
+        else:
+            draw.ellipse((x - half, y - half, x + half - 1, y + half - 1), fill=255)
+    return mask
diff --git a/src/labelwerk/storage.py b/src/labelwerk/storage.py
index edae656..57dfbb8 100644
--- a/src/labelwerk/storage.py
+++ b/src/labelwerk/storage.py
@@ -23,8 +23,9 @@ from pathlib import Path
 
 from PIL import Image
 
-from .document import (ALIGNMENTS, MAX_MARGIN_MM, MAX_POSITION_MM, ORIENTATIONS, ROTATIONS,
-                       Document, ImageObject, Paragraph, Span, TextObject)
+from .document import (ALIGNMENTS, FRAME_LINE_MM, FRAME_STYLES, MAX_FRAME_MM, MAX_MARGIN_MM,
+                       MAX_POSITION_MM, ORIENTATIONS, ROTATIONS, Document, Frame, ImageObject,
+                       Paragraph, Span, TextObject)
 from .imaging import MAX_PIXELS, MODES
 from .labels import get_label
 
@@ -51,8 +52,10 @@ IMAGE = {"png": "bytes", "source": "str", "page": "page?", "crop": "crop", "x_mm
          "y_mm": "pos", "w_mm": "size", "h_mm": "size", "rotation": "rotation", "mode": "mode",
          "threshold": "threshold", "invert": "bool", "keep_ratio": "bool", "dpi": "dpi",
          "svg": "bytes?"}
+FRAME = {"style": "frame_style", "rounded": "bool", "line_mm": "frame_line",
+         "inset_mm": "frame_mm", "padding_mm": "frame_mm"}
 DOCUMENT = {"label_id": "label", "length_mm": "size?", "orientation": "orientation",
-            "margin_mm": "margin"}                                # dazu „objects“
+            "margin_mm": "margin"}                                # dazu „objects“, „frame“
 
 
 def _num(v) -> bool:
@@ -95,6 +98,9 @@ _KINDS = {
     "align": lambda v: v in ALIGNMENTS, "orientation": lambda v: v in ORIENTATIONS,
     "rotation": lambda v: _int(v) and v in ROTATIONS,
     "mode": lambda v: v in MODES, "label": _label,
+    "frame_style": lambda v: v in FRAME_STYLES,
+    "frame_line": lambda v: _num(v) and FRAME_LINE_MM[0] <= v <= FRAME_LINE_MM[1],
+    "frame_mm": lambda v: _num(v) and 0 <= v <= MAX_FRAME_MM,
     "crop": lambda v: v is None or (isinstance(v, list) and len(v) == 4 and all(map(_int, v))),
 }
 
@@ -148,8 +154,9 @@ def to_dict(doc: Document) -> dict:
                 for p in obj.paragraphs]})
         else:
             objects.append({"type": "image", **_dump(obj, IMAGE)})
+    frame = None if doc.frame is None else _dump(doc.frame, FRAME)
     return {"format": FORMAT, "version": VERSION,
-            "document": {**_dump(doc, DOCUMENT), "objects": objects}}
+            "document": {**_dump(doc, DOCUMENT), "objects": objects, "frame": frame}}
 
 
 def save(doc: Document, path: str | Path) -> Path:
@@ -281,6 +288,9 @@ def from_dict(data) -> Document:
                            f"– bitte labelwerk aktualisieren")
     document = data.get("document")
     values = _load(document, DOCUMENT, "")
+    frame = document.get("frame")
+    if frame is not None:                   # fehlt oder null: kein Rahmen
+        values["frame"] = Frame(**_load(frame, FRAME, " im Rahmen"))
     items = _list(document, "objects", "")
     if len(items) > MAX_OBJECTS:
         raise StorageError(f"Etikett zu groß ({len(items)} Objekte, höchstens {MAX_OBJECTS})")
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1785 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/document.py src/labelwerk/layout.py src/labelwerk/render.py src/labelwerk/storage.py tests/test_frame.py tests/test_storage.py
git commit -m "Kern: Zierrahmen ums Etikett – Arten, Kreis auf runden Etiketten, Innenraum für automatischen Text und Länge, Speichern

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: GUI – Bereich Rahmen im Reiter Papier, Arbeitsfläche, Innenraum

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/file_session.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/paper.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/render.py`
- Create: `tests/gui/test_gui_frame.py`
- Modify: `tests/test_frame.py`
- Modify: `tests/test_layout.py`

**Interfaces / Produces:** `Rendered.frame`; `layout.snap(..., inner=)`; `PaperPanel` (Reihenfolge Etikett · Länge · Ausrichtung · Ränder · Rahmen; `frame_style`, `frame_rounded`, `frame_line`, `frame_inset`, `frame_padding`, `frame_labels`, `frame_icon`); `Canvas.set_document(..., frame=, inner=)`, `Canvas.frame_item`; `MainWindow.accept_pending_input`, `_paper_area`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_frame.py b/tests/gui/test_gui_frame.py
new file mode 100644
index 0000000..018565b
--- /dev/null
+++ b/tests/gui/test_gui_frame.py
@@ -0,0 +1,278 @@
+"""Zierrahmen in der GUI: Bereich „Rahmen“ im Reiter Papier, Arbeitsfläche, Ausrichten am Innenraum."""
+import pytest
+from PIL import Image
+from PySide6.QtCore import QPointF, Qt
+from PySide6.QtGui import QMouseEvent
+from PySide6.QtWidgets import QApplication, QLabel
+
+from labelwerk import layout, storage
+from labelwerk.document import Document, Frame, ImageObject, TextObject
+from labelwerk.gui import main_window
+from labelwerk.gui.app import apply_theme
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.render import render_document
+from labelwerk.settings import Settings
+
+STYLES = ["Kein", "Einfach", "Doppelt", "Dick-dünn", "Gestrichelt", "Gepunktet", "Nur Ecken"]
+
+
+def _window(qtbot, doc=None):
+    win = MainWindow(doc=doc or Document("62x29", objects=[TextObject("Hallo")]),
+                     settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    win.show()
+    win.render_now()
+    return win
+
+
+def _choose(paper, title):
+    paper.frame_style.setCurrentIndex(paper.frame_style.findText(title))
+
+
+def test_frame_section_lists_the_styles_with_previews(qtbot):
+    paper = _window(qtbot).panel("paper")
+    combo = paper.frame_style
+    assert [combo.itemText(i) for i in range(combo.count())] == STYLES
+    assert all(not combo.itemIcon(i).isNull() for i in range(1, combo.count()))
+    assert combo.currentText() == "Kein"
+    for widget in (paper.frame_rounded, paper.frame_line, paper.frame_inset, paper.frame_padding):
+        assert not widget.isEnabled()
+
+
+def test_choosing_a_style_sets_the_frame_and_shows_it(qtbot):
+    win = _window(qtbot)
+    paper = win.panel("paper")
+    _choose(paper, "Doppelt")
+    win.render_now()
+    assert win.doc.frame == Frame("double")
+    assert all(w.isEnabled() for w in (paper.frame_rounded, paper.frame_line, paper.frame_inset,
+                                       paper.frame_padding))
+    assert win.image.tobytes() == render_document(win.doc).tobytes()
+    assert win.image.getpixel((12, 130))[0] == 0
+    _choose(paper, "Kein")
+    assert win.doc.frame is None
+
+
+def test_fields_change_the_frame(qtbot):
+    win = _window(qtbot)
+    paper = win.panel("paper")
+    _choose(paper, "Einfach")
+    paper.frame_rounded.setChecked(True)
+    paper.frame_line.setValue(1.2)
+    paper.frame_inset.setValue(2.0)
+    paper.frame_padding.setValue(0.5)
+    assert win.doc.frame == Frame("single", rounded=True, line_mm=1.2, inset_mm=2.0, padding_mm=0.5)
+
+
+def test_field_limits_follow_the_core(qtbot):
+    from labelwerk.document import FRAME_LINE_MM, MAX_FRAME_MM
+    from labelwerk.gui.panels.paper import PaperPanel
+    paper = PaperPanel(Document())
+    qtbot.addWidget(paper)
+    assert (paper.frame_line.minimum(), paper.frame_line.maximum()) == FRAME_LINE_MM
+    assert paper.frame_inset.maximum() == paper.frame_padding.maximum() == MAX_FRAME_MM
+    assert not paper.frame_line.keyboardTracking()       # erst bei Enter/Verlassen ein Schritt
+
+
+def test_each_change_is_one_undo_step(qtbot):
+    win = _window(qtbot)
+    paper = win.panel("paper")
+    _choose(paper, "Gestrichelt")
+    paper.frame_line.setValue(1.0)
+    win.shortcut_actions["edit.undo"].trigger()
+    assert win.doc.frame == Frame("dashed")
+    assert paper.frame_line.value() == 0.5
+    win.shortcut_actions["edit.undo"].trigger()
+    assert win.doc.frame is None and paper.frame_style.currentText() == "Kein"
+
+
+def test_refresh_shows_the_frame_of_an_opened_label(qtbot):
+    doc = Document("62x29", objects=[TextObject("A")],
+                   frame=Frame("dotted", rounded=True, line_mm=0.3, inset_mm=1, padding_mm=2))
+    paper = _window(qtbot, doc).panel("paper")
+    assert paper.frame_style.currentText() == "Gepunktet"
+    assert paper.frame_rounded.isChecked()
+    assert (paper.frame_line.value(), paper.frame_inset.value(), paper.frame_padding.value()) == (
+        0.3, 1.0, 2.0)
+
+
+def test_round_labels_offer_no_corners_and_no_rounding(qtbot):
+    win = _window(qtbot, Document("d24", objects=[TextObject("A")], frame=Frame("single")))
+    paper = win.panel("paper")
+    corners = paper.frame_style.findText("Nur Ecken")
+    assert not paper.frame_style.model().item(corners).isEnabled()
+    assert not paper.frame_rounded.isEnabled()
+    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
+    assert paper.frame_style.model().item(corners).isEnabled() and paper.frame_rounded.isEnabled()
+
+
+def test_canvas_shows_the_frame_but_it_takes_no_clicks(qtbot):
+    win = _window(qtbot)
+    assert win.canvas.frame_item is None
+    _choose(win.panel("paper"), "Einfach")
+    win.render_now()
+    item = win.canvas.frame_item
+    assert item is not None and not item.pixmap().isNull()
+    assert item.acceptedMouseButtons() == Qt.MouseButton.NoButton
+    assert item.zValue() < min(o.zValue() for o in win.canvas.objects)
+    assert (item.pixmap().width(), item.pixmap().height()) == win._shown_size
+
+
+def test_frame_error_is_shown_like_other_render_errors(qtbot):
+    win = _window(qtbot, Document("d12", objects=[TextObject("A")]))
+    paper = win.panel("paper")
+    _choose(paper, "Einfach")
+    paper.frame_inset.setValue(10)
+    win.render_now()
+    assert "Rahmen passt nicht" in win.result.text()
+
+
+def test_align_to_paper_uses_the_inner_room(qtbot):
+    doc = Document("62x29", objects=[TextObject("A", size_pt=12, x_mm=20, y_mm=10)],
+                   frame=Frame("single"))
+    win = _window(qtbot, doc)
+    inner = layout.frame_area(win.doc)
+    win.canvas.set_selection([0])
+    win.align_selected("left", paper=True)
+    frame = layout.exact_rect(win.doc.objects[0], win.rendered[0])
+    assert frame.x == pytest.approx(inner.x, abs=0.001)
+
+
+def test_maximize_uses_the_inner_room(qtbot):
+    doc = Document("62x29", objects=[TextObject("A", size_pt=12, x_mm=20, y_mm=10)],
+                   frame=Frame("single"))
+    win = _window(qtbot, doc)
+    inner = layout.frame_area(win.doc)
+    win.canvas.set_selection([0])
+    win.maximize_selected()
+    frame = layout.exact_rect(win.doc.objects[0], win.rendered[0])
+    assert inner.x - 0.001 <= frame.x and frame.right <= inner.right + 0.001
+    assert inner.y - 0.001 <= frame.y and frame.bottom <= inner.bottom + 0.001
+
+
+def _send(canvas, kind, pos, buttons):
+    button = (Qt.MouseButton.LeftButton if kind != QMouseEvent.Type.MouseMove
+              else Qt.MouseButton.NoButton)
+    QApplication.sendEvent(canvas.viewport(), QMouseEvent(
+        kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)), button, buttons,
+        Qt.KeyboardModifier.NoModifier))
+
+
+def test_canvas_snaps_to_the_inner_room(qtbot):
+    win = _window(qtbot, Document("62x29", objects=[TextObject("A", size_pt=12, x_mm=20, y_mm=10)],
+                                  frame=Frame("single", padding_mm=3)))
+    canvas = win.canvas
+    inner = layout.frame_area(win.doc)
+    rect = layout.object_rect(canvas.objects[0].rendered)
+    start = canvas.view_rect(0).center()
+    end = start + QPointF(round((inner.x - rect.x) * canvas.px_per_mm()) + 2, 0)   # 2 px daneben
+    left = Qt.MouseButton.LeftButton
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, left)
+    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, left)
+    _send(canvas, QMouseEvent.Type.MouseMove, end, left)
+    assert ("x", pytest.approx(inner.x)) in canvas.guides()
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
+    assert layout.object_rect(canvas.objects[0].rendered).x == pytest.approx(inner.x, abs=0.1)
+    win.panel("paper").frame_style.setCurrentIndex(0)
+    win.render_now()
+    assert win.canvas._inner is None
+
+
+# --- Nachbesserungen nach dem Review ------------------------------------------------------
+def _type(box, value):
+    """Wert ins Feld tippen, ohne Enter (Feld hat den Fokus, meldet aber noch nichts)."""
+    box.lineEdit().selectAll()
+    box.lineEdit().insert(box.textFromValue(value))
+
+
+def test_typed_value_counts_when_printing_right_away(qtbot, monkeypatch):
+    win = _window(qtbot)
+    paper = win.panel("paper")
+    _choose(paper, "Einfach")
+    _type(paper.frame_line, 2.0)
+    monkeypatch.setattr(main_window.QApplication, "focusWidget", lambda: paper.frame_line)
+    printed = []
+    monkeypatch.setattr(win, "_print", lambda image, doc, outside: printed.append(doc.frame))
+    win.print_label()
+    assert printed == [Frame("single", line_mm=2.0)]
+
+
+def test_typed_value_counts_when_saving_right_away(qtbot, monkeypatch, tmp_path):
+    win = _window(qtbot)
+    paper = win.panel("paper")
+    _choose(paper, "Einfach")
+    _type(paper.frame_padding, 4.0)
+    monkeypatch.setattr(main_window.QApplication, "focusWidget", lambda: paper.frame_padding)
+    win.files.ask_save_file = lambda suggested: str(tmp_path / "r.labelwerk")
+    win.shortcut_actions["file.save"].trigger()
+    assert storage.load(tmp_path / "r.labelwerk").frame == Frame("single", padding_mm=4.0)
+
+
+def test_canvas_frame_is_smoothed_and_reused(qtbot):
+    win = _window(qtbot)
+    _choose(win.panel("paper"), "Einfach")
+    win.render_now()
+    item = win.canvas.frame_item
+    assert item.transformationMode() == Qt.TransformationMode.SmoothTransformation
+    pixmap = item.pixmap().cacheKey()
+    win.doc.objects[0] = TextObject("Anders")
+    win.render_now()                                   # Rahmen unverändert: Bild bleibt
+    assert win.canvas.frame_item.pixmap().cacheKey() == pixmap
+
+
+@pytest.mark.parametrize("theme", ["rawblock", "classic"])
+def test_frame_fields_are_not_cut_off(qtbot, theme):
+    apply_theme(QApplication.instance(), theme)
+    try:
+        win = _window(qtbot)
+        win.resize(1200, 900)
+        win.tool_actions["paper"].trigger()
+        QApplication.processEvents()
+        paper = win.panel("paper")
+        for box in (paper.frame_line, paper.frame_inset, paper.frame_padding):
+            longest = box.textFromValue(box.maximum()) + box.suffix()        # „10.0 mm“
+            edit = box.lineEdit()
+            room = edit.width() - edit.textMargins().left() - edit.textMargins().right()
+            assert room >= edit.fontMetrics().horizontalAdvance(longest), longest
+        for label in paper.frame_labels:
+            assert isinstance(label, QLabel) and label.width() >= label.sizeHint().width()
+    finally:
+        apply_theme(QApplication.instance(), "classic")
+
+
+def test_values_stay_when_switching_to_none_and_back(qtbot):
+    win = _window(qtbot)
+    paper = win.panel("paper")
+    _choose(paper, "Einfach")
+    paper.frame_line.setValue(1.5)
+    _choose(paper, "Kein")
+    paper.refresh()                                    # z. B. Rückgängig eines anderen Schritts
+    _choose(paper, "Einfach")
+    assert win.doc.frame == Frame("single", line_mm=1.5)
+
+
+def test_inserted_images_and_symbols_fit_the_inner_room(qtbot):
+    win = _window(qtbot, Document("62x29", objects=[], frame=Frame("double")))
+    inner = layout.frame_area(win.doc)
+    big = ImageObject.from_image(Image.new("RGB", (3000, 3000), "black"), 300, "gross.png")
+    win._insert_images([big], None, [])
+    obj = win.doc.objects[-1]
+    assert inner.y - 0.001 <= obj.y_mm and obj.y_mm + obj.h_mm <= inner.bottom + 0.001
+    assert win._symbol_mm() <= min(inner.w, inner.h)
+
+
+def test_round_label_explains_the_circle(qtbot):
+    win = _window(qtbot, Document("d24", objects=[TextObject("A")], frame=Frame("single")))
+    paper = win.panel("paper")
+    assert "Kreis" in paper.frame_style.toolTip()
+    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
+    assert "Kreis" not in paper.frame_style.toolTip()
+
+
+def test_paper_sections_put_orientation_above_margins_and_frame(qtbot):
+    paper = _window(qtbot).panel("paper")
+    layout_ = paper.layout_
+    sections = [layout_.itemAt(i).widget().text() for i in range(layout_.count())
+                if isinstance(layout_.itemAt(i).widget(), QLabel)
+                and layout_.itemAt(i).widget().property("role") == "section"]
+    assert sections == ["ETIKETT", "LÄNGE", "AUSRICHTUNG", "RÄNDER", "RAHMEN"]
diff --git a/tests/test_frame.py b/tests/test_frame.py
index fbfa2ac..6cc3c07 100644
--- a/tests/test_frame.py
+++ b/tests/test_frame.py
@@ -332,3 +332,9 @@ def test_positioned_fit_object_ignores_the_frame():
     framed = Renderer().render(Document("62x29", objects=[obj], frame=Frame("double", padding_mm=5))
                                ).objects[0]
     assert (framed.base_pt, framed.w, framed.h) == (plain.base_pt, plain.w, plain.h)
+def test_renderer_reports_the_frame_mask():
+    from labelwerk.render import frame_mask
+    doc = Document("62x29", objects=[TextObject("A")], frame=Frame("double"))
+    result = Renderer().render(doc)
+    assert result.frame.tobytes() == frame_mask(doc, size=result.size).tobytes()
+    assert Renderer().render(Document("62x29")).frame is None
diff --git a/tests/test_layout.py b/tests/test_layout.py
index 0de7c7d..17cfe7e 100644
--- a/tests/test_layout.py
+++ b/tests/test_layout.py
@@ -124,6 +124,20 @@ def test_snap_center_to_label_center():
     assert sorted(s.guides) == [("x", 31), ("y", 15)]
 
 
+def test_snap_to_frame_inner_room():
+    inner = Rect(3, 3, 56, 24)
+    s = layout.snap(Rect(3.2, 9, 5, 5), [], _AREA, 0.5, inner=inner)
+    assert s.dx == pytest.approx(-0.2) and s.guides == [("x", 3)]
+    s = layout.snap(Rect(53.9, 9, 5, 5), [], _AREA, 0.5, inner=inner)      # rechte Innenkante 59
+    assert s.dx == pytest.approx(0.1)
+
+
+def test_snap_inner_room_offers_only_its_start_in_the_growing_axis():
+    inner = Rect(3, 3, 56, 24)
+    s = layout.snap(Rect(53.9, 9, 5, 5), [], _AREA, 0.5, inner=inner, grow="x")
+    assert s.dx == 0
+
+
 def test_snap_to_label_edge():
     s = layout.snap(Rect(0.2, 9, 5, 5), [], _AREA, 0.3, label=_LABEL)
     assert s.dx == pytest.approx(-0.2) and s.guides == [("x", 0)]
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: Die neuen Tests (tests/gui/test_gui_frame.py, neue Fälle in tests/test_layout.py und tests/test_frame.py) schlagen fehl (fehlende Attribute `frame_style`, `frame_item`, Parameter `inner` …), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 9dbe353..f60edbb 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -19,8 +19,11 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - Bildschirmfoto (Etappe 3d-2b): Knopf BILDSCHIRMFOTO im Reiter Bild – labelwerk blendet sich aus, der Desktop zeigt seine Auswahl (XDG-Portal), das Bild kommt mit 300 dpi aufs Etikett; ohne Portal Hinweis auf Zwischenablage + Strg+V.
 - SVG-Dateien sind Vektorbilder: in jeder Größe scharf gerastert (Etappe 3d-2c).
 - Symbole/ClipArt (Etappe 3d-2c): Knopf SYMBOL im Reiter Bild – Fenster „Symbol einfügen“ (bleibt offen; Suche über die ganze Bibliothek, Gruppen Zuletzt verwendet/Favoriten/Elektro/Versand/Sicherheit/Allgemein/Eigene, Doppelklick/Enter/Ziehen fügt ein); Symbole 15 mm, Vektor, zugeschnitten.
+- Zierrahmen ums Etikett: Reiter PAPIER → Rahmen (Einfach, Doppelt, Dick-dünn, Gestrichelt, Gepunktet, Nur Ecken; abgerundet,
+  Linie, Randabstand, Innenabstand); runde Etiketten: Kreis; automatischer Text, Ausrichten/Maximieren und neue Bilder/Symbole
+  bleiben im Innenraum.
 - Datei und Favoriten (Etappe 3c): Reiter DATEI – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“); `labelwerk install-desktop` meldet *.labelwerk an (Doppelklick öffnet).
-- 1785 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- 1809 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -31,7 +34,7 @@ src/labelwerk/
               render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
               compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise:
               prepare_object, label_size(prepared=), finish_object; span_dots
-              Renderer (Qt-frei, für die GUI): render(doc, model) -> Rendered(size, objects, image) – Objekt-Cache,
+              Renderer (Qt-frei, für die GUI): render(doc, model) -> Rendered(size, objects, image, frame) – Objekt-Cache,
               rendert nur Geändertes neu (Objekt + Kontext, ohne Position auch Etikettgröße), Druckbild = render_document
               Zeilensatz mit gemeinsamer Grundlinie (pixelgleich zu Pillow multiline_text für reinen Text), font_warnings(doc)
               exakte Druckbreite @300 dpi, Schrift schrumpft automatisch, mehrzeilig zentriert
@@ -93,7 +96,7 @@ src/labelwerk/
               Bilder wie Text mit fester Rahmengröße; keep_aspect (Anfasser mit keep_ratio); Schrift-Funktionen: TypeError bei Bildern
               Bild einfügen/einstellen: insert_frame (Mitte bzw. Ablagepunkt, zu groß → proportional eingepasst, Endlosband
               nur quer), set_crop (Maßstab und Lage des Inhalts bleiben), original_size, set_keep_ratio, proportional
-              frame_area(doc, model, size) -> Rect | None (Innenraum des Zierrahmens in mm)
+              frame_area(doc, model, size) -> Rect | None (Innenraum des Zierrahmens in mm); snap(..., inner=) rastet auch daran ein
   shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
               without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
   desktop.py  .desktop-Eintrag (Exec … %f, MimeType) + Icon + Dateityp application/x-labelwerk (*.labelwerk, mime/packages,
@@ -106,7 +109,9 @@ src/labelwerk/
                     Bildschirmfoto (insert_screenshot: ausblenden, Portal, wieder zeigen; Haken screenshot_available/take_screenshot,
                     Antwort screenshot_finished; 5 min Sicherheitsnetz), Symbole (open_symbols, insert_symbol: SYMBOL_MM 15 mm,
                     höchstens quer zum Band; Zuletzt verwendet/Favoriten still gespeichert), Strg+V nach Zwischenablage des Systems (eigene Kopie › Dateien › Text › Bild; Stand beim Ändern gemerkt,
-                    Daten erst beim Einfügen gelesen); Auswahl zeigt Panel der Objektart; start(path) (Datei bzw. Start-Favorit),
+                    Daten erst beim Einfügen gelesen); Auswahl zeigt Panel der Objektart; Ausrichten/Maximieren „am Etikett“
+                    sowie Bilder/Symbole einfügen nutzen mit Zierrahmen seinen Innenraum (_paper_area);
+                    accept_pending_input (getippte Zahl ohne Enter vor Drucken/Speichern/Rückgängig übernehmen); start(path) (Datei bzw. Start-Favorit),
                     print_document(doc) (anderes Etikett drucken, gleiche Rückfragen); closeEvent fragt bei Änderungen
     tools.py        Werkzeug-Registry (Datei, Papier, Text, Bild, Layout; neue Werkzeuge als Eintrag; START_TOOL = Papier)
     file_session.py FileSession: Neu/Öffnen/Speichern, modified/update_title („•“), maybe_save (Rückfrage), Dokument an Ort und
@@ -116,6 +121,8 @@ src/labelwerk/
                     aufgelöst); Dialoge ask_* ersetzbar (Speichern-Dialog ergänzt die Endung selbst)
     panels/file.py  Reiter Datei: Knöpfe (Aktionen file.*), Favoriten mit Vorschau und ⎙ je Zeile, Kontextmenü, Zuletzt geöffnet
     panels/         Eigenschaften-Panels je Werkzeug (paper, text und image mit Bereich Position)
+    panels/paper.py Reiter Papier: Etikett, Länge, Ausrichtung, Ränder, Rahmen (Arten mit Vorschau aus dem Kern: frame_icon;
+                    Felder ohne Tastatur-Mitlauf = ein Schritt, Werte bleiben bei „Kein“ stehen; rund: ohne „Nur Ecken“/abgerundet)
     symbol_dialog.py Fenster „Symbol einfügen“ (SymbolDialog, Werkzeugfenster, nicht modal; Enter/Esc/Kontextmenü): Suche, Gruppen + Untergruppe, Raster über
                     SymbolModel (Vorschau erst bei Bedarf gerastert), Ziehen (MIME_SYMBOL = id), ★ Favorit, Ordner öffnen (open_url ersetzbar)
     panels/image.py Reiter Bild: Aus Datei/Aus Zwischenablage/Bildschirmfoto/Symbol, Quelle, Strich/Foto, Schwelle (Regler = ein Schritt), Umkehren,
@@ -131,6 +138,7 @@ src/labelwerk/
     panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
     panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
     canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
+                    Zierrahmen (frame_item unter den Objekten, keine Klicks; Einrasten am Innenraum);
                     Ablegen von Dateien/Bilddaten (Daten im dropEvent kopiert, Signal dropped danach, mm) und Symbolen (symbol_dropped); Anfasser-Vorschau mit
                     keep_aspect (Bild, dieselbe Regel wie layout.resize: fest ist, was der Anfasser sagt)
                     Schreibmodus: zeichnet Rahmen/Schreibmarke/Markierung (set_edit_marks), meldet Klicks hinein (edit_*)
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index c4b3953..a49c92c 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -137,6 +137,10 @@ class Canvas(QGraphicsView):
         self._pixmaps: dict[int, tuple[RenderedObject, QPixmap]] = {}
         self._selection: list[int] = []
         self._area = self._label_rect = Rect(0, 0, 0, 0)
+        self._inner: Rect | None = None                    # Innenraum des Zierrahmens (mm)
+        self.frame_item: QGraphicsPixmapItem | None = None # Zierrahmen (unter den Objekten)
+        self._frame_source: Image.Image | None = None      # Maske, aus der _frame_pixmap entstand
+        self._frame_pixmap = QPixmap()
         self._grow: str | None = None                      # mitwachsende Achse (Endlosband)
         self._guides: list[tuple[str, float]] = []
         self._caption = ""
@@ -165,14 +169,17 @@ class Canvas(QGraphicsView):
     def set_document(self, label: Label, size: tuple[int, int],
                      rendered: list[RenderedObject], orientation: str = "vertical",
                      area: Rect | None = None, keep_ratio: list[bool] | None = None,
-                     grow: str | None = None, keep_aspect: list[bool] | None = None) -> None:
+                     grow: str | None = None, keep_aspect: list[bool] | None = None,
+                     frame: Image.Image | None = None, inner: Rect | None = None) -> None:
         """Etikett (physische Form) und die einzeln gerenderten Objekte darin anzeigen.
 
         ``size``: Etikett in Druckpunkten in Leserichtung (wie ``render.label_size``);
         ``area``: bedruckbarer Bereich in mm (Einrasten); ``keep_ratio`` je Objekt: Ecken
         skalieren die Schrift (ohne feste Rahmengröße); ``keep_aspect`` je Objekt: auch
         Kanten halten das Seitenverhältnis (Bild); ``grow``: Achse, in der das Etikett
-        mitwächst (``layout.growing_axis``) – dort rastet nur der Anfang ein. Die Szene ist immer in
+        mitwächst (``layout.growing_axis``) – dort rastet nur der Anfang ein; ``frame``: Maske des
+        Zierrahmens (``Rendered.frame``), liegt unter den Objekten und nimmt keine Klicks;
+        ``inner``: sein Innenraum in mm (Einrasten). Die Szene ist immer in
         Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°, damit das Etikett in
         Leserichtung erscheint – die Objekte liegen in ``sheet``, das in Leserichtung zählt.
         """
@@ -204,6 +211,16 @@ class Canvas(QGraphicsView):
         self.sheet.setTransform(QTransform().translate(ox + pw, oy).rotate(90) if horizontal
                                 else QTransform().translate(ox, oy))
         scene.addItem(self.sheet)
+        self.frame_item = None
+        if frame is not None:
+            if frame is not self._frame_source:  # der Renderer liefert unverändert dieselbe Maske
+                self._frame_source = frame
+                self._frame_pixmap = QPixmap.fromImage(to_qimage(ImageOps.invert(frame)))
+            self.frame_item = QGraphicsPixmapItem(self._frame_pixmap, self.sheet)
+            self.frame_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
+            self.frame_item.setZValue(-1)
+            self.frame_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
+        self._inner = inner
         self._pixmaps = {id(obj): (obj, self._pixmap(obj)) for obj in rendered}
         ratios = keep_ratio if keep_ratio is not None else [True] * len(rendered)
         aspects = keep_aspect if keep_aspect is not None else [False] * len(rendered)
@@ -220,6 +237,7 @@ class Canvas(QGraphicsView):
             self.printable = QGraphicsRectItem(QRectF(area.x * MM, area.y * MM,
                                                       area.w * MM, area.h * MM), self.sheet)
             self.printable.setPen(dotted)
+            self.printable.setZValue(-2)                 # unter dem Zierrahmen
         else:
             self.printable = scene.addRect(QRectF(ox, oy, pw, ph), dotted)
 
@@ -594,7 +612,7 @@ class Canvas(QGraphicsView):
                        if item.index not in self._start and not item.is_empty()]
             snap = layout.snap(layout.bounds(frames), targets, self._area,
                                SNAP_PX / self.px_per_mm(), label=self._label_rect,
-                               grow=self._grow)
+                               grow=self._grow, inner=self._inner)
             delta += QPointF(snap.dx * MM, snap.dy * MM)
             self._guides = snap.guides
         for index, start in self._start.items():
diff --git a/src/labelwerk/gui/file_session.py b/src/labelwerk/gui/file_session.py
index 4efb4c9..81a6b1c 100644
--- a/src/labelwerk/gui/file_session.py
+++ b/src/labelwerk/gui/file_session.py
@@ -145,6 +145,7 @@ class FileSession(QObject):
     def maybe_save(self) -> bool:
         """Vor Neu/Öffnen/Schließen: bei Änderungen fragen; False = abbrechen (der Schreibmodus
         läuft dann weiter). Das Dokument ist auch beim Tippen aktuell."""
+        self.window.accept_pending_input()
         if not self.modified():
             return True
         answer = self.ask_save_changes()
@@ -215,11 +216,13 @@ class FileSession(QObject):
         return True
 
     def save(self) -> bool:
+        self.window.accept_pending_input()          # eben getippte Zahl gehört dazu
         if self.path is None:
             return self.save_as()
         return self._write(self.path)
 
     def save_as(self) -> bool:
+        self.window.accept_pending_input()
         suggested = str(self.path) if self.path is not None else str(
             Path(self._dir or Path.home()) / f"{self.suggested_name() or UNTITLED}{SUFFIX}")
         path = self.ask_save_file(suggested)
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index eaa7fcc..b4b4a73 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -11,7 +11,8 @@ from pathlib import Path
 from PIL import Image
 from PySide6.QtCore import QMimeData, Qt, QThreadPool, QTimer
 from PySide6.QtGui import QAction, QActionGroup, QIcon
-from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
+from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QFileDialog, QFrame, QHBoxLayout,
+                               QInputDialog,
                                QLabel, QMainWindow, QMessageBox,
                                QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                                QWidget)
@@ -23,10 +24,10 @@ from ..document import Document, ImageObject, TextObject
 from ..files import NOT_WHITE, crop_box
 from ..fonts import DEFAULT_FAMILY
 from ..labels import DPI, get_label
-from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, growing_axis,
-                      insert_placement, match_objects, maximize_object, move, object_rect,
-                      objects_outside, outside_indices, printable_area, proportional, reorder, resize, rotate,
-                      set_frame, to_grid)
+from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, frame_area,
+                      growing_axis, insert_placement, match_objects, maximize_object, move,
+                      object_rect, objects_outside, outside_indices, printable_area, proportional,
+                      reorder, resize, rotate, set_frame, to_grid)
 from ..printer import DEFAULT_MODEL
 from ..render import (Renderer, RenderedObject, font_warnings, render_document,
                       set_svg_rasterizer)
@@ -124,6 +125,8 @@ class MainWindow(QMainWindow):
         self._arranging = False                     # Auswahl wird intern umgestellt (Anlegen …)
         self._outside: list[int] = []               # Objekte, die über das Etikett ragen
         self._area = Rect(0, 0, 0, 0)               # bedruckbarer Bereich (mm), mit dem Bild
+        self._inner: Rect | None = None             # Innenraum des Zierrahmens (mm), mit dem Bild
+        self._shown_frame = None                    # Rahmen-Maske der letzten gültigen Anzeige
         # alle Kürzel kommen aus dem Verzeichnis (shortcuts.ACTIONS) und sind änderbar;
         # doppelt belegte (von Hand bearbeitete Datei): die spätere Aktion bleibt ohne Kürzel
         keys, key_warnings = without_conflicts(effective(self.settings.shortcuts))
@@ -530,6 +533,8 @@ class MainWindow(QMainWindow):
         self._structure_dirty = False
         self._outside = outside
         self._area = area
+        self._inner = frame_area(self.doc, self.model, size)
+        self._shown_frame = result.frame
         # Anfasser: Ecken halten das Seitenverhältnis bei Text ohne feste Rahmengröße und bei
         # Bildern mit „Seitenverhältnis beibehalten“ – Bilder dann auch an den Kanten
         images = [isinstance(obj, ImageObject) for obj in self.doc.objects]
@@ -538,7 +543,8 @@ class MainWindow(QMainWindow):
                                                    for obj, image in zip(self.doc.objects, images)],
                                  grow=growing_axis(self.doc),
                                  keep_aspect=[image and obj.keep_ratio
-                                              for obj, image in zip(self.doc.objects, images)])
+                                              for obj, image in zip(self.doc.objects, images)],
+                                 frame=result.frame, inner=self._inner)
         self.panel("layout").set_growing(growing_axis(self.doc))
         self._update_frame()
         self.edit_session.update_marks()            # Schreibmarke zum neuen Zeilensatz
@@ -554,7 +560,8 @@ class MainWindow(QMainWindow):
         self.rendered = []
         self.canvas.set_document(get_label(self.doc.label_id), self._shown_size, [],
                                  self.doc.orientation,
-                                 self._area, keep_ratio=[], grow=growing_axis(self.doc))
+                                 self._area, keep_ratio=[], grow=growing_axis(self.doc),
+                                 frame=self._shown_frame, inner=self._inner)
 
     # --- Rückgängig -------------------------------------------------------
     def _commit(self, merge=None) -> None:
@@ -572,11 +579,13 @@ class MainWindow(QMainWindow):
     def undo(self) -> None:
         """Rückgängig – im Schreibmodus erst innerhalb der Bearbeitung (``TextEditSession.undo``),
         dann im Dokument (Knopf und Strg+Z gleich)."""
+        self.accept_pending_input()                 # eben Getipptes ist der letzte Schritt
         if not self.edit_session.undo():
             self._restore(self.history.undo(self.doc, self.canvas.selection()))
 
     def redo(self) -> None:
         """Wiederherstellen – im Schreibmodus erst im Editor, dann im Dokument (wie ``undo``)."""
+        self.accept_pending_input()
         if not self.edit_session.redo():
             self._restore(self.history.redo(self.doc, self.canvas.selection()))
 
@@ -745,19 +754,26 @@ class MainWindow(QMainWindow):
 
     # --- Reiter „Layout“ ---------------------------------------------------
     def align_selected(self, mode: str, paper: bool = False) -> None:
-        """Auswahl aneinander bzw. am bedruckbaren Bereich ausrichten."""
+        """Auswahl aneinander bzw. am bedruckbaren Bereich (mit Zierrahmen: an seinem
+        Innenraum) ausrichten."""
         self._change_selected(lambda objs, rendered: align_objects(
-            objs, rendered, mode, self._area if paper else None, growing_axis(self.doc)))
+            objs, rendered, mode, self._paper_area() if paper else None, growing_axis(self.doc)))
+
+    def _paper_area(self) -> Rect:
+        """Fläche für „am Etikett“ (Ausrichten, Maximieren): Innenraum des Zierrahmens, sonst
+        der bedruckbare Bereich."""
+        return self._inner if self._inner is not None else self._area
 
     def match_selected(self, mode: str) -> None:
         """Größe, Breite oder Höhe an das zuerst gewählte Objekt angleichen."""
         self._change_selected(lambda objs, rendered: match_objects(objs, rendered, mode))
 
     def maximize_selected(self) -> None:
-        """Jedes gewählte Objekt so groß wie möglich mittig in den bedruckbaren Bereich
-        (auf Endlosband mit automatischer Länge nur quer – ``maximize_object``)."""
+        """Jedes gewählte Objekt so groß wie möglich mittig in den bedruckbaren Bereich bzw. den
+        Innenraum des Zierrahmens (auf Endlosband mit automatischer Länge nur quer –
+        ``maximize_object``)."""
         self._change_selected(lambda objs, rendered: [
-            maximize_object(obj, r, self._area, self.doc, self.model)
+            maximize_object(obj, r, self._paper_area(), self.doc, self.model)
             for obj, r in zip(objs, rendered)])
 
     def rotate_selected(self, degrees: int) -> None:
@@ -1091,8 +1107,8 @@ class MainWindow(QMainWindow):
         """Größe neuer Symbole: ``SYMBOL_MM``, höchstens der bedruckbare Bereich quer zum Band
         (in der mitwachsenden Achse begrenzt das Etikett nicht)."""
         grow = growing_axis(self.doc)
-        cross = (self._area.h if grow == "x" else self._area.w if grow == "y"
-                 else min(self._area.w, self._area.h))
+        area = self._paper_area()                   # mit Zierrahmen: sein Innenraum
+        cross = area.h if grow == "x" else area.w if grow == "y" else min(area.w, area.h)
         return max(1.0, math.floor(min(SYMBOL_MM, cross) * 1000) / 1000)   # nie knapp zu groß
 
     def _symbol_dropped(self, symbol_id: str, x_mm: float, y_mm: float) -> None:
@@ -1168,10 +1184,9 @@ class MainWindow(QMainWindow):
             others = [object_rect(r) for o, r in zip(self.doc.objects, self.rendered)
                       if not o.is_empty()]
             for number, obj in enumerate(objects):
-                rect, rotation, factor = insert_placement(self.doc, self.model, self._area,
-                                                          (obj.w_mm, obj.h_mm), at, others,
-                                                          rotate=self.settings.image_rotate
-                                                          if rotate is None else rotate)
+                rect, rotation, factor = insert_placement(
+                    self.doc, self.model, self._paper_area(), (obj.w_mm, obj.h_mm), at, others,
+                    rotate=self.settings.image_rotate if rotate is None else rotate)
                 others.append(rect)
                 shift = number * PASTE_OFFSET_MM if at is not None or not growing_axis(
                     self.doc) else 0.0
@@ -1379,7 +1394,16 @@ class MainWindow(QMainWindow):
             QMessageBox.StandardButton.Cancel)
         return answer == QMessageBox.StandardButton.Yes
 
+    def accept_pending_input(self) -> None:
+        """Eben getippte Zahl übernehmen: Zahlenfelder ohne Tastatur-Mitlauf melden ihren Wert
+        erst bei Enter oder beim Verlassen – DRUCKEN in der Werkzeugleiste und Kürzel nehmen
+        den Fokus nicht. Vor Drucken, Speichern und Rückgängig aufrufen."""
+        widget = QApplication.focusWidget()
+        if isinstance(widget, QAbstractSpinBox):
+            widget.interpretText()
+
     def print_label(self) -> None:
+        self.accept_pending_input()
         if self._timer.isActive():
             self.render_now()
         if self._render_error is not None:
diff --git a/src/labelwerk/gui/panels/paper.py b/src/labelwerk/gui/panels/paper.py
index 22fb135..a2ffdd3 100644
--- a/src/labelwerk/gui/panels/paper.py
+++ b/src/labelwerk/gui/panels/paper.py
@@ -1,18 +1,52 @@
-"""Panel „Papier“: Etikett, Länge (Endlosband), Ränder und Ausrichtung – wie im P-touch Editor."""
+"""Panel „Papier“: Etikett, Länge (Endlosband), Ränder, Zierrahmen und Ausrichtung – wie im
+P-touch Editor."""
 from __future__ import annotations
 
-from PySide6.QtCore import Signal
-from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QHBoxLayout,
+from PIL import Image, ImageOps
+from PySide6.QtCore import QSize, Signal
+from PySide6.QtGui import QIcon, QImage, QPixmap
+from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
                                QLabel, QPushButton, QRadioButton, QWidget)
 
-from ...document import MAX_MARGIN_MM, Document
+from ...document import FRAME_LINE_MM, MAX_FRAME_MM, MAX_MARGIN_MM, Document, Frame
 from ...labels import DPI, get_label, labels_for_model, length_limits
 from ...media import Media
 from ...printer import DEFAULT_MODEL
+from ...render import frame_mask
 from ..widgets import DoubleSpinBox
 from . import Panel
 
 _GROUPS = (("endless", "Endlos"), ("die_cut", "Gestanzt"), ("round", "Rund"))
+FRAME_TITLES = (("Kein", None), ("Einfach", "single"), ("Doppelt", "double"),
+                ("Dick-dünn", "thick_thin"), ("Gestrichelt", "dashed"), ("Gepunktet", "dotted"),
+                ("Nur Ecken", "corners"))
+FRAME_ICON = QSize(56, 22)
+ROUND_TIP = "Auf runden Etiketten wird jeder Rahmen ein Kreis."
+
+
+def frame_icon(style: str | None) -> QIcon:
+    """Vorschau einer Rahmenart auf weißem Etikett – aus dem Kern gezeichnet (dicke Linie,
+    damit sie klein lesbar bleibt); None = leeres Etikett („Kein“, gleich hoch)."""
+    size = (FRAME_ICON.width(), FRAME_ICON.height())
+    if style is None:
+        small = Image.new("L", size, 255)
+    else:
+        doc = Document("62x29", frame=Frame(style, line_mm=1.5, padding_mm=0))
+        small = ImageOps.invert(frame_mask(doc)).resize(size, Image.Resampling.BOX)
+    rgb = small.convert("RGB")                  # deckend weiß – auch auf dunkler Palette
+    image = QImage(rgb.tobytes(), rgb.width, rgb.height, 3 * rgb.width, QImage.Format.Format_RGB888)
+    return QIcon(QPixmap.fromImage(image.copy()))
+
+
+def _spin(low: float, high: float, step: float, tip: str) -> DoubleSpinBox:
+    box = DoubleSpinBox()
+    box.setSuffix(" mm")
+    box.setDecimals(1)
+    box.setSingleStep(step)
+    box.setRange(low, high)
+    box.setToolTip(tip)
+    box.setKeyboardTracking(False)          # erst bei Enter/Verlassen: ein Rückgängig-Schritt
+    return box
 
 
 class PaperPanel(Panel):
@@ -62,15 +96,6 @@ class PaperPanel(Panel):
         self.fixed_size.setObjectName("fixedSize")
         self.layout_.addWidget(self.fixed_size)
 
-        self.section("Ränder")
-        self.margin = DoubleSpinBox()
-        self.margin.setSuffix(" mm")
-        self.margin.setDecimals(1)
-        self.margin.setSingleStep(0.5)
-        self.margin.setRange(0.0, MAX_MARGIN_MM)
-        self.margin.setToolTip("Abstand vorne/hinten in Bandlaufrichtung")
-        self.layout_.addWidget(self.margin)
-
         self.section("Ausrichtung")
         self.horizontal = QRadioButton("Horizontal")
         self.horizontal.setToolTip("Etikett im Querformat – Leserichtung längs zum Band")
@@ -80,6 +105,45 @@ class PaperPanel(Panel):
         for button in (self.horizontal, self.vertical):
             self.orientation_group.addButton(button)
             self.layout_.addWidget(button)
+        self.section("Ränder")
+        self.margin = DoubleSpinBox()
+        self.margin.setSuffix(" mm")
+        self.margin.setDecimals(1)
+        self.margin.setSingleStep(0.5)
+        self.margin.setRange(0.0, MAX_MARGIN_MM)
+        self.margin.setToolTip("Abstand vorne/hinten in Bandlaufrichtung")
+        self.layout_.addWidget(self.margin)
+
+        self.section("Rahmen")
+        self.frame_style = QComboBox()
+        self.frame_style.setIconSize(FRAME_ICON)
+        for title, style in FRAME_TITLES:
+            self.frame_style.addItem(frame_icon(style), title, style)
+        self.layout_.addWidget(self.frame_style)
+        self.frame_rounded = QCheckBox("Abgerundet")
+        self.layout_.addWidget(self.frame_rounded)
+        grid = QGridLayout()
+        grid.setContentsMargins(0, 0, 0, 0)
+        grid.setColumnStretch(1, 1)              # Felder füllen die Breite (wie die übrigen)
+        defaults = Frame()
+        self.frame_line = _spin(*FRAME_LINE_MM, 0.1, "Strichstärke der Linie")
+        self.frame_inset = _spin(0.0, MAX_FRAME_MM, 0.5, "Abstand des Rahmens vom bedruckbaren Rand")
+        self.frame_padding = _spin(0.0, MAX_FRAME_MM, 0.5,
+                                   "Abstand zwischen Rahmen und automatisch gesetztem Text")
+        self.frame_labels: list[QLabel] = []
+        for row, (title, box, value) in enumerate((
+                ("Linie", self.frame_line, defaults.line_mm),
+                ("Randabstand", self.frame_inset, defaults.inset_mm),
+                ("Innenabstand", self.frame_padding, defaults.padding_mm))):
+            box.setValue(value)
+            label = QLabel(title)
+            label.setToolTip(box.toolTip())
+            self.frame_labels.append(label)
+            grid.addWidget(label, row, 0)
+            grid.addWidget(box, row, 1)
+        self.layout_.addLayout(grid)
+        self._last_frame = defaults               # Werte bleiben bei „Kein“ für später stehen
+
         self.layout_.addStretch()
 
         self.refresh()
@@ -88,9 +152,28 @@ class PaperPanel(Panel):
         self.length.valueChanged.connect(self._apply)
         self.margin.valueChanged.connect(self._apply)
         self.horizontal.toggled.connect(self._apply)
+        self.frame_style.currentIndexChanged.connect(self._apply_frame)
+        self.frame_rounded.toggled.connect(self._apply_frame)
+        for box in self._frame_boxes():
+            box.valueChanged.connect(self._apply_frame)
 
     def _widgets(self):
-        return (self.combo, self.length_auto, self.length, self.margin, self.horizontal, self.vertical)
+        return (self.combo, self.length_auto, self.length, self.margin, self.horizontal, self.vertical,
+                self.frame_style, self.frame_rounded, *self._frame_boxes())
+
+    def _frame_boxes(self) -> tuple[DoubleSpinBox, ...]:
+        return (self.frame_line, self.frame_inset, self.frame_padding)
+
+    def _apply_frame(self) -> None:
+        """Rahmen aus den Feldern; „Kein“ = kein Rahmen (die Felder bleiben für später stehen)."""
+        style = self.frame_style.currentData()
+        frame = Frame(style or self._last_frame.style, self.frame_rounded.isChecked(),
+                      self.frame_line.value(), self.frame_inset.value(), self.frame_padding.value())
+        self._last_frame = frame
+        self.doc.frame = None if style is None else frame
+        self._update_frame_widgets()
+        self.changed.emit()
+        self.edited.emit()           # jede Rahmen-Änderung ist ein eigener Schritt
 
     def _apply(self) -> None:
         self.doc.label_id = self.combo.currentData()
@@ -112,6 +195,14 @@ class PaperPanel(Panel):
             self.length.setValue(self.doc.length_mm)
         self.margin.setValue(self.doc.margin_mm)
         (self.horizontal if self.doc.orientation == "horizontal" else self.vertical).setChecked(True)
+        if self.doc.frame is not None:
+            self._last_frame = self.doc.frame
+        frame = self._last_frame                     # ohne Rahmen: zuletzt gewählte Werte
+        self.frame_style.setCurrentIndex(self.frame_style.findData(
+            None if self.doc.frame is None else frame.style))
+        self.frame_rounded.setChecked(frame.rounded)
+        for box, value in zip(self._frame_boxes(), (frame.line_mm, frame.inset_mm, frame.padding_mm)):
+            box.setValue(value)
         for w in self._widgets():
             w.blockSignals(False)
         self._update_visibility()
@@ -160,3 +251,15 @@ class PaperPanel(Panel):
         w, h = label.size_mm
         self.fixed_size.setText(f"Ø {w} mm · rund" if label.shape == "round"
                                 else f"{w} × {h} mm · gestanzt")
+        self._update_frame_widgets()
+
+    def _update_frame_widgets(self) -> None:
+        """Felder nur mit Rahmen; runde Etiketten: Kreis – keine Ecken, nicht abgerundet."""
+        round_label = get_label(self.doc.label_id).shape == "round"
+        corners = self.frame_style.findData("corners")
+        self.frame_style.model().item(corners).setEnabled(not round_label)
+        self.frame_style.setToolTip(ROUND_TIP if round_label else "")
+        active = self.doc.frame is not None
+        self.frame_rounded.setEnabled(active and not round_label)
+        for box in self._frame_boxes():
+            box.setEnabled(active)
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index 78f069a..e4a54fe 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -105,16 +105,16 @@ def printable_area(doc: Document, model: str = "QL-600",
 
 # --- Einrasten --------------------------------------------------------------------
 def snap(moving: Rect, targets: list[Rect], area: Rect, tolerance_mm: float,
-         label: Rect | None = None, grow: str | None = None) -> Snap:
+         label: Rect | None = None, grow: str | None = None, inner: Rect | None = None) -> Snap:
     """Kanten und Mitte von ``moving`` an nahe Linien einrasten lassen.
 
-    Kandidaten: Kanten und Mitte des bedruckbaren Bereichs, des Etiketts (falls angegeben)
-    und der anderen Objekte. Je Achse gewinnt der nächste Kandidat innerhalb der Toleranz
+    Kandidaten: Kanten und Mitte des bedruckbaren Bereichs, des Etiketts und des Innenraums
+    eines Zierrahmens (``inner``, falls angegeben) und der anderen Objekte. Je Achse gewinnt der nächste Kandidat innerhalb der Toleranz
     (Grenze eingeschlossen); ``guides`` nennt alle Linien, die nach dem Einrasten getroffen
     werden. ``grow`` (``growing_axis``): In dieser Achse bieten Etikett und Bereich nur
     ihren Anfang an – Mitte und Ende wandern mit dem Objekt.
     """
-    sheets = [area, *([label] if label is not None else [])]
+    sheets = [area, *(r for r in (label, inner) if r is not None)]
     x_lines = [v for r in sheets for v in ((r.x,) if grow == "x" else (r.x, r.cx, r.right))]
     y_lines = [v for r in sheets for v in ((r.y,) if grow == "y" else (r.y, r.cy, r.bottom))]
     dx, x_guides = _snap_axis((moving.x, moving.cx, moving.right),
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index de70881..c0d3571 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -217,6 +217,7 @@ class Rendered:
     size: tuple[int, int]
     objects: list[RenderedObject]
     image: Image.Image
+    frame: Image.Image | None = None       # Zierrahmen als Maske (``frame_mask``), Arbeitsfläche
 
 
 @dataclass
@@ -257,7 +258,7 @@ class Renderer:
         size = label_size(doc, model, prepared=[e.prepared for e in entries])
         objects = self._draw(entries, doc, model, size)
         frame = self._frame_mask(doc, model, size)
-        return Rendered(size, objects, self._compose(objects, size, doc.orientation, frame))
+        return Rendered(size, objects, self._compose(objects, size, doc.orientation, frame), frame)
 
     def _frame_mask(self, doc: Document, model: str, size: tuple[int, int]) -> Image.Image | None:
         """Rahmen-Maske – neu nur, wenn sich Rahmen oder Etikett ändern."""
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `1809 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md src/labelwerk/gui/canvas.py src/labelwerk/gui/file_session.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/paper.py src/labelwerk/layout.py src/labelwerk/render.py tests/gui/test_gui_frame.py tests/test_frame.py tests/test_layout.py
git commit -m "GUI: Reiter Papier – Bereich Rahmen mit Vorschau der Arten, Rahmen auf der Arbeitsfläche, Ausrichten und Einrasten am Innenraum

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Abnahme (manuell, durch den Nutzer)

- [ ] Reiter PAPIER: Reihenfolge Etikett · Länge · Ausrichtung · Ränder · Rahmen.
- [ ] Rahmen: jede Art durchprobieren (Vorschau in der Liste), abgerundet, Linie/Randabstand/Innenabstand; automatischer Text bleibt innerhalb, Endlosband wird länger.
- [ ] Rundes Etikett: Kreis, „Nur Ecken“ und „abgerundet“ gesperrt.
- [ ] Zahl tippen und direkt DRUCKEN bzw. Strg+S: der getippte Wert gilt.
- [ ] Probedruck auf DK-22205 (62 mm) mit einfachem und gepunktetem Rahmen; Speichern/Öffnen behält den Rahmen.
