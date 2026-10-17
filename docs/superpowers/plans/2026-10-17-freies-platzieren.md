# Freies Platzieren (Etappe 3d-1) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Objekte frei auf dem Etikett anordnen wie im P-touch Editor – mehrere Textrahmen, Auswahl, Ziehen, Einrasten, Anfasser, Tastatur, Position in mm, Reiter „Layout“, Drehen, Reihenfolge, Zwischenablage, Rückgängig – und alle Tastenkürzel in den Einstellungen änderbar.

**Architecture:** Jedes Objekt wird im Kern einzeln gerendert (`render_object`); die Arbeitsfläche zeigt die Objektbilder einzeln (flüssiges Ziehen), der Druck setzt dieselben Bilder zusammen (Vorschau = Druck). Platzier-Logik (`layout.py`) und Kürzel-Verzeichnis (`shortcuts.py`) sind Qt-frei; die GUI ruft nur auf.

**Tech Stack:** Python ≥ 3.10, Pillow, PySide6, pytest, pytest-qt.

Spec: `docs/superpowers/specs/2026-10-17-freies-platzieren-design.md`

**Herkunft des Codes:** Prototyp in genau dieser Task-Reihenfolge (Branch `proto-3d1`), nach jedem Task volle Suite grün mit Exit-Code 0 (307 → 342 → 406 → 464 → 505 → 545 → 567 → 655 → 659 → 672 → 681); Pixelgleichheit gegen den eingefrorenen alten Algorithmus in 18 Fällen; GUI per Offscreen-Screenshots geprüft.

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
### Task 1: Kern – Objekte einzeln rendern (Position, Rahmen, Drehen, Zusammensetzen)

**Files:**
- Modify: `src/labelwerk/document.py`
- Modify: `src/labelwerk/render.py`
- Create: `tests/_render_before_3d.py`
- Create: `tests/test_placement_render.py`

**Interfaces / Produces:** `TextObject.x_mm/y_mm/w_mm/h_mm` (`float | None`), `.rotation` (0/90/180/270, `document.ROTATIONS`), `.positioned`; `render.RenderedObject(image: Image 'L', x, y, w, h: int Druckpunkte in Leserichtung, base_pt: float)`, `render.render_object(obj, doc, model='QL-600') -> RenderedObject`; `render_document` setzt die Objektbilder zusammen; ein einzelnes Objekt ohne Position ist pixelgleich zu vorher (eingefrorene Kopie `tests/_render_before_3d.py`).

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/_render_before_3d.py b/tests/_render_before_3d.py
new file mode 100644
index 0000000..bb9acaa
--- /dev/null
+++ b/tests/_render_before_3d.py
@@ -0,0 +1,287 @@
+"""Eingefrorene Kopie von render.py vor Etappe 3d-1 (Bezug für den Pixelvergleich).
+
+Nur die Importe sind auf absolut umgestellt; sonst unverändert. Nicht weiterentwickeln.
+"""
+from __future__ import annotations
+
+import math
+from dataclasses import dataclass
+
+from PIL import Image, ImageDraw
+
+from labelwerk import fonts
+from labelwerk.document import (ALIGNMENTS, MAX_MARGIN_MM, MIN_PT, ORIENTATIONS, Document, Paragraph,
+                                Span, TextObject)
+from labelwerk.labels import DPI, get_label, length_limits
+
+MARGIN = 12            # Punkte, ca. 1 mm
+PT = DPI / 72          # Druckpunkte pro typografischem Punkt
+REF_PT = 12.0          # Bezugsgröße für automatische Skalierung von Stücken mit eigener Größe
+MIN_DOTS = 8           # kleinste Schrift in Druckpunkten
+_LINE_GAP = 4          # wie Pillow multiline_text
+_SLANT = 0.2           # Ersatzkursive: Scherung, wenn die Schrift keine echte Kursive hat
+
+
+class TextTooLarge(ValueError):
+    """Text passt bei fester Schriftgröße nicht aufs Etikett."""
+
+    def __init__(self, size_pt: float, max_pt: float | None, label_id: str):
+        if max_pt is None:                     # passt nicht einmal in der kleinsten Größe
+            message = (f"Text passt nicht auf Etikett {label_id!r} – auch nicht in der "
+                       "kleinsten Schriftgröße.")
+        else:
+            message = (f"Text passt nicht auf Etikett {label_id!r} bei Schriftgröße "
+                       f"{_fmt_pt(size_pt)} pt (höchstens {_fmt_pt(max_pt)} pt).")
+        super().__init__(message)
+        self.size_pt, self.max_pt = size_pt, max_pt
+
+
+def _fmt_pt(value: float) -> str:
+    return f"{value:g}".replace(".", ",")
+
+
+def render_text(text: str, label_id: str, size_pt: float | None = None,
+                font_path: str | None = None) -> Image.Image:
+    """Reinen Text rendern (Standardformatierung)."""
+    obj = TextObject.plain(text, size_pt=size_pt, font_path=font_path)
+    return render_document(Document(label_id, objects=[obj]))
+
+
+def font_warnings(doc: Document) -> list[str]:
+    """Hinweise zu ersetzten Schriften (je Familie einmal)."""
+    warnings: list[str] = []
+    for obj in doc.objects:
+        for para in obj.paragraphs:
+            for span in para.spans:
+                if span.family is None:
+                    continue
+                match = fonts.resolve(span.family, span.bold, span.italic)
+                text = f"Schrift „{span.family}“ nicht gefunden – ersetzt durch „{match.family}“."
+                if match.family.casefold() != span.family.casefold() and text not in warnings:
+                    warnings.append(text)
+    return warnings
+
+
+def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
+    """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).
+
+    Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
+    wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
+    Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
+    """
+    if doc.orientation not in ORIENTATIONS:
+        raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
+    horizontal = doc.orientation == "horizontal"
+    label = get_label(doc.label_id)
+    min_len, max_len = length_limits(model)
+    margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
+    across = label.width                      # quer zum Band (fest)
+    feed = label.height                       # in Bandlaufrichtung; None = automatisch
+    if feed is None and doc.length_mm is not None:
+        feed = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
+    if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
+        margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
+    obj = doc.objects[0] if doc.objects else TextObject("")
+    for para in obj.paragraphs:
+        if para.align not in ALIGNMENTS:
+            raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
+                             "rechts, Blocksatz (left, center, right, justify)")
+
+    across_room = across - 2 * MARGIN
+    feed_room = (feed if feed else max_len) - 2 * margin
+    max_w, max_h = (feed_room, across_room) if horizontal else (across_room, feed_room)
+    base = _fit(obj, max(10, across // 5), max_w, max_h, doc.label_id)
+    lines = _shape(obj, base)
+    l, t, r, b = _block_box(lines)
+
+    text_w, text_h = r - l, b - t
+    if feed is None:
+        feed = min(max((text_w if horizontal else text_h) + 2 * margin, min_len), max_len)
+    width, height = (feed, across) if horizontal else (across, feed)
+    img = Image.new("RGB", (width, height), "white")
+    x0 = (width - text_w) // 2 - l
+    if any(para.align != "center" for para in obj.paragraphs):
+        # Textrahmen über die volle Breite in Leserichtung: Absätze richten sich am Rahmen aus
+        start = margin if horizontal else MARGIN
+        frame = width - 2 * start
+        lines = _shape(obj, base, frame=frame)
+        fl, ft, fr, fb = _block_box(lines)
+        x0 = min(max(start, -fl), width - fr)            # Tinte bleibt im Bild
+        t, text_h = ft, fb - ft
+    _draw(img, lines, x0, (height - text_h) // 2 - t)
+    return img.rotate(-90, expand=True) if horizontal else img
+
+
+# --- Schriftgrößen ----------------------------------------------------------
+def _span_dots(obj: TextObject, span: Span, base: int) -> int:
+    """Größe eines Stücks in Druckpunkten bei Grundgröße ``base`` (gemeinsam skaliert)."""
+    if span.size_pt is None:
+        return base
+    ref = obj.size_pt or REF_PT
+    return max(1, round(base * span.size_pt / ref))
+
+
+def _fit(obj: TextObject, auto_start: int, max_w: int, max_h: int, label_id: str) -> int:
+    """Grundgröße in Druckpunkten: fest, oder größte passende ≤ auto_start (Halbierung)."""
+    def fits(base: int) -> bool:
+        l, t, r, b = _block_box(_shape(obj, base, mode="1"))
+        return (r - l) <= max_w and (b - t) <= max_h
+
+    start = auto_start if obj.auto else round(obj.size_pt * PT)
+    if fits(start):
+        return start
+    best, lo, hi = None, MIN_DOTS, start - 1
+    while lo <= hi:
+        mid = (lo + hi) // 2
+        if fits(mid):
+            best, lo = mid, mid + 1
+        else:
+            hi = mid - 1
+    if not obj.auto:
+        # Meldung in der größten eingestellten Größe – die sieht der Nutzer im Editor
+        largest = max((span.size_pt or obj.size_pt for para in obj.paragraphs
+                       for span in para.spans), default=obj.size_pt)
+        max_pt = int(best / PT * largest / obj.size_pt) if best else None
+        if max_pt is not None and max_pt < MIN_PT:
+            max_pt = None                      # kleiner als erlaubt: zählt als „passt nicht“
+        raise TextTooLarge(largest, max_pt, label_id)
+    return best if best else MIN_DOTS          # passt nicht einmal klein – kleinste Größe zeigen
+
+
+# --- Zeilensatz ---------------------------------------------------------------
+@dataclass
+class _Piece:
+    text: str
+    font: object
+    dots: int
+    underline: bool
+    slant: bool                # Ersatzkursive
+    x: float = 0.0             # links, relativ zum Block
+    y: float = 0.0             # Oberkante (Ascender-Linie), relativ zum Block
+
+
+def _font_for(obj: TextObject, span: Span, dots: int):
+    if span.family is None and obj.font_path:
+        return fonts.load(obj.font_path, dots), span.italic   # feste Datei: Ersatzkursive
+    match = fonts.resolve(span.family, span.bold, span.italic)
+    return fonts.load(match.path, dots), span.italic and not match.italic
+
+
+def _shape(obj: TextObject, base: int, mode: str = "L",
+           frame: float | None = None) -> list[list[_Piece]]:
+    """Stücke mit Position im Block (mode „1“ zum Messen, „L“ zum Zeichnen – wie Pillow).
+
+    Ohne ``frame`` richten sich die Zeilen an der breitesten Zeile aus; mit ``frame``
+    (Rahmenbreite) an dieser Breite – Blocksatz dehnt weiter auf die breiteste Zeile."""
+    rows = []
+    for para in obj.paragraphs:
+        spans = para.spans or [Span("")]
+        pieces = []
+        for span in spans:
+            dots = _span_dots(obj, span, base)
+            font, slant = _font_for(obj, span, dots)
+            pieces.append(_Piece(span.text, font, dots, span.underline, slant))
+        rows.append((para, pieces))
+
+    widths = [sum(p.font.getlength(p.text, mode) for p in pieces) for _, pieces in rows]
+    # Unterlängen großer Stücke brauchen Platz unter der Zeile; bei einheitlicher Schrift 0
+    min_descent = min(p.font.getmetrics()[1] for _, pieces in rows for p in pieces)
+    max_width = max(widths, default=0)
+    ref = max_width if frame is None else frame
+    top = 0.0
+    lines = []
+    for (para, pieces), width in zip(rows, widths):
+        ascent = max(p.font.getmetrics()[0] for p in pieces)
+        spacing = max(p.font.getbbox("A", mode)[3] for p in pieces) + _LINE_GAP
+        if para.align == "justify":
+            pieces = _justify(pieces, max_width, mode)
+        else:
+            x = {"left": 0.0, "center": (ref - width) / 2.0,
+                 "right": ref - width}[para.align]
+            for p in pieces:
+                p.x = x
+                x += p.font.getlength(p.text, mode)
+        for p in pieces:
+            p.y = top + ascent - p.font.getmetrics()[0]    # gemeinsame Grundlinie
+        lines.append(pieces)
+        top += spacing + max(p.font.getmetrics()[1] for p in pieces) - min_descent
+    return lines
+
+
+def _justify(pieces: list[_Piece], max_width: float, mode: str) -> list[_Piece]:
+    """Wortabstände dehnen, bis die Zeile die Blockbreite füllt (ein Wort: linksbündig)."""
+    words: list[_Piece] = []
+    gaps_before: list[bool] = []
+    for p in pieces:
+        for i, part in enumerate(p.text.split(" ")):
+            words.append(_Piece(part, p.font, p.dots, p.underline, p.slant))
+            gaps_before.append(i > 0)
+    gaps = sum(gaps_before[1:])
+    used = sum(w.font.getlength(w.text, mode) for w in words)
+    extra = (max_width - used) / gaps if gaps else 0.0
+    x = 0.0
+    for word, gap in zip(words, gaps_before):
+        if gap:
+            x += extra
+        word.x = x
+        x += word.font.getlength(word.text, mode)
+    return words
+
+
+def _block_box(lines: list[list[_Piece]]) -> tuple[int, int, int, int]:
+    """Tintenbox des Blocks (wie Pillow multiline_textbbox), auf ganze Punkte gerundet."""
+    boxes = []
+    for pieces in lines:
+        for p in pieces:
+            l, t, r, b = p.font.getbbox(p.text, "1", anchor="la")
+            if p.underline:
+                b = max(b, p.font.getmetrics()[0] + _underline(p.dots)[0] + _underline(p.dots)[1])
+            if p.slant:
+                r += _SLANT * p.font.getmetrics()[0]
+                l -= _slant_pad(p)
+            boxes.append((p.x + l, p.y + t, p.x + r, p.y + b))
+    if not boxes:
+        return (0, 0, 0, 0)
+    return tuple(round(v) for v in (min(b[0] for b in boxes), min(b[1] for b in boxes),
+                                    max(b[2] for b in boxes), max(b[3] for b in boxes)))
+
+
+def _underline(dots: int) -> tuple[int, int]:
+    """(Abstand unter der Grundlinie, Stärke) in Druckpunkten."""
+    return max(1, round(dots * 0.10)), max(1, round(dots * 0.06))
+
+
+def _draw(img: Image.Image, lines: list[list[_Piece]], x0: int, y0: int) -> None:
+    draw = ImageDraw.Draw(img)
+    for pieces in lines:
+        for p in pieces:
+            x, y = x0 + p.x, y0 + p.y
+            if p.slant:
+                _draw_slanted(img, p, x, y)
+            else:
+                draw.text((x, y), p.text, fill="black", font=p.font, anchor="la")
+            if p.underline and p.text:
+                offset, thickness = _underline(p.dots)
+                base_y = round(y + p.font.getmetrics()[0] + offset)
+                length = p.font.getlength(p.text)
+                draw.rectangle((round(x), base_y, round(x + length), base_y + thickness - 1),
+                               fill="black")
+
+
+def _slant_pad(p: _Piece) -> int:
+    """Platz links für die Ersatzkursive: nach links gescherte Unterlänge und negative
+    linke Seitenpeilung."""
+    left = p.font.getbbox(p.text, anchor="la")[0] if p.text else 0
+    return math.ceil(_SLANT * p.font.getmetrics()[1]) + max(0, -left)
+
+
+def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
+    """Ersatzkursive: Stück einzeln zeichnen und um die Grundlinie nach rechts scheren."""
+    ascent, descent = p.font.getmetrics()
+    pad = _slant_pad(p)
+    width = pad + int(p.font.getlength(p.text) + _SLANT * ascent) + 2
+    mask = Image.new("L", (width, ascent + descent), 0)
+    ImageDraw.Draw(mask).text((pad, 0), p.text, fill=255, font=p.font, anchor="la")
+    sheared = mask.transform(mask.size, Image.Transform.AFFINE,
+                             (1, _SLANT, -_SLANT * ascent, 0, 1, 0), Image.Resampling.BICUBIC)
+    img.paste((0, 0, 0), (round(x) - pad, round(y)), sheared)
diff --git a/tests/test_placement_render.py b/tests/test_placement_render.py
new file mode 100644
index 0000000..7fe75b9
--- /dev/null
+++ b/tests/test_placement_render.py
@@ -0,0 +1,190 @@
+"""Objekte einzeln rendern und zusammensetzen (Etappe 3d-1)."""
+import pytest
+from PIL import Image
+
+import _render_before_3d as before
+from labelwerk.document import ROTATIONS, Document, Paragraph, Span, TextObject
+from labelwerk.labels import DPI
+from labelwerk.render import RenderedObject, render_document, render_object
+
+
+def _dots(mm):
+    return round(mm * DPI / 25.4)
+
+
+def _ink_box(img):
+    """Tintenbox (Pixel dunkler als 50 %)."""
+    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()
+
+
+def _reading(img, doc):
+    """Druckbild zurück in Leserichtung drehen."""
+    return img.rotate(90, expand=True) if doc.orientation == "horizontal" else img
+
+
+# --- Pixelgleichheit für ein Objekt ohne Position -------------------------------
+_MIXED = TextObject([Paragraph([Span("klein", size_pt=10), Span("GROSS", size_pt=30)], "left"),
+                     Paragraph([Span("rechts", italic=True, underline=True)], "right")],
+                    size_pt=20)
+_CASES = [
+    Document("62", objects=[TextObject("Hallo")]),
+    Document("62", objects=[TextObject("X1 -K3\nKlemme 24V")]),
+    Document("62", objects=[TextObject("A\nB", size_pt=48)]),
+    Document("62", objects=[TextObject.plain("Links\nmehr Text", align="left")]),
+    Document("62", objects=[TextObject.plain("Rechts\nmehr Text", align="right", size_pt=20)]),
+    Document("62", objects=[TextObject.plain("Block satz hier\nlange Zeile mit Worten",
+                                             align="justify")]),
+    Document("62", objects=[_MIXED]),
+    Document("62", objects=[TextObject("Fest", size_pt=30, fit=True)]),
+    Document("62", objects=[TextObject("")]),
+    Document("62", objects=[]),
+    Document("62", objects=[TextObject("Schräg")], margin_mm=5),
+    Document("29", objects=[TextObject("Sehr langer Text der schrumpft")]),
+    Document("62x29", objects=[TextObject.plain("Gestanzt", align="left")]),
+    Document("62", objects=[TextObject("Quer")], orientation="horizontal"),
+    Document("62", objects=[TextObject.plain("Längs links", align="left", size_pt=24)],
+             orientation="horizontal", length_mm=100),
+    Document("29", objects=[TextObject.plain("Rechts", align="right")], orientation="horizontal"),
+    Document("62", objects=[TextObject("Feste Länge", size_pt=20)], length_mm=40),
+    Document("12", objects=[TextObject.plain("Kursiv", italic=True)], orientation="horizontal"),
+]
+
+
+@pytest.mark.parametrize("doc", _CASES, ids=range(len(_CASES)))
+def test_unpositioned_object_is_pixel_identical_to_before(doc):
+    new = render_document(doc)
+    old = before.render_document(doc)
+    assert new.mode == old.mode and new.size == old.size
+    assert new.tobytes() == old.tobytes()
+
+
+# --- Modell -----------------------------------------------------------------
+def test_text_object_defaults_are_unpositioned():
+    obj = TextObject("A")
+    assert (obj.x_mm, obj.y_mm, obj.w_mm, obj.h_mm, obj.rotation) == (None, None, None, None, 0)
+    assert ROTATIONS == (0, 90, 180, 270)
+
+
+def test_invalid_rotation_raises():
+    with pytest.raises(ValueError, match="Drehung"):
+        render_document(Document("62", objects=[TextObject("A", rotation=45)]))
+
+
+# --- Position ---------------------------------------------------------------
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_positioned_ink_starts_at_position(orientation):
+    obj = TextObject("H", size_pt=20, x_mm=10, y_mm=5)
+    doc = Document("62", length_mm=60, orientation=orientation, objects=[obj])
+    left, top, _, _ = _ink_box(_reading(render_document(doc), doc))
+    # oben schließt die Tinte an den Rahmen an, links liegt nur die Vorbreite der Schrift davor
+    bearing = _ink_box(render_object(obj, doc).image)[0]
+    assert left == _dots(10) + bearing and bearing < 20 * 0.2 * 300 / 72
+    assert abs(top - _dots(5)) <= 1
+
+
+def test_render_object_reports_frame_on_label():
+    obj = TextObject("H", size_pt=20, x_mm=10, y_mm=5)
+    ro = render_object(obj, Document("62", length_mm=60, objects=[obj]))
+    assert isinstance(ro, RenderedObject)
+    assert (ro.x, ro.y) == (_dots(10), _dots(5))
+    assert ro.image.mode == "L" and ro.image.size == (ro.w, ro.h)
+    assert ro.base_pt == 20
+
+
+def test_positioned_object_never_raises_text_too_large():
+    obj = TextObject("W" * 60, size_pt=40, x_mm=0, y_mm=0)
+    img = render_document(Document("29", length_mm=50, objects=[obj]))
+    assert img.size == (306, _dots(50))
+
+
+def test_object_beyond_label_is_clipped():
+    objs = [TextObject("Unten", size_pt=40, x_mm=-5, y_mm=25),
+            TextObject("Rechts", size_pt=40, x_mm=55, y_mm=2)]
+    img = render_document(Document("62", length_mm=30, objects=objs))
+    assert img.size == (696, _dots(30))
+    assert _ink_box(img) is not None
+
+
+# --- Drehen -----------------------------------------------------------------
+@pytest.mark.parametrize("rotation, transpose", [(90, Image.Transpose.ROTATE_270),
+                                                 (180, Image.Transpose.ROTATE_180),
+                                                 (270, Image.Transpose.ROTATE_90)])
+def test_rotation_turns_object_image_clockwise(rotation, transpose):
+    doc = Document("62", length_mm=60)
+    upright = render_object(TextObject("Ab", size_pt=30, x_mm=5, y_mm=5), doc)
+    turned = render_object(TextObject("Ab", size_pt=30, x_mm=5, y_mm=5, rotation=rotation), doc)
+    if rotation == 180:
+        assert (turned.w, turned.h) == (upright.w, upright.h)
+    else:
+        assert (turned.w, turned.h) == (upright.h, upright.w)
+    assert (turned.x, turned.y) == (upright.x, upright.y)
+    assert turned.image.tobytes() == upright.image.transpose(transpose).tobytes()
+
+
+def test_rotated_object_is_placed_on_label():
+    obj = TextObject("Ab", size_pt=30, x_mm=5, y_mm=5, rotation=90)
+    doc = Document("62", length_mm=60, objects=[obj])
+    ro = render_object(obj, doc)
+    left, top, right, bottom = _ink_box(render_document(doc))
+    assert abs(left - ro.x) <= 1 and abs(top - ro.y) <= 1
+    assert bottom - top > right - left              # hochkant
+
+
+# --- Zusammensetzen -----------------------------------------------------------
+def test_later_object_does_not_erase_earlier_ink():
+    first = TextObject("H", size_pt=60, x_mm=5, y_mm=5)
+    second = TextObject("H", size_pt=60, x_mm=7, y_mm=6)   # Rahmen überdeckt das erste „H“
+    doc = Document("62", length_mm=40, objects=[first, second])
+    a = render_object(first, doc)
+    b = render_object(second, doc)
+    assert b.x < a.x + a.w and b.y < a.y + a.h
+    alone = render_document(Document("62", length_mm=40, objects=[first])).convert("L")
+    both = render_document(doc).convert("L")
+    ink = [(x, y) for y in range(alone.height) for x in range(alone.width)
+           if alone.getpixel((x, y)) < 128]
+    assert ink and all(both.getpixel(p) < 128 for p in ink)
+
+
+def test_auto_length_grows_with_farthest_object():
+    near = TextObject("A", size_pt=20, x_mm=5, y_mm=5)
+    far = TextObject("B", size_pt=20, x_mm=5, y_mm=60)
+    doc = Document("62", objects=[near, far])
+    ro = render_object(far, doc)
+    assert render_document(doc).height == ro.y + ro.h + _dots(doc.margin_mm)
+
+
+def test_auto_length_horizontal_uses_x():
+    obj = TextObject("B", size_pt=20, x_mm=70, y_mm=5)
+    doc = Document("62", orientation="horizontal", objects=[obj])
+    ro = render_object(obj, doc)
+    assert render_document(doc).height == ro.x + ro.w + _dots(doc.margin_mm)
+
+
+def test_auto_length_keeps_room_for_unpositioned_object():
+    centered = TextObject("Mitte\nzwei\ndrei", size_pt=40)
+    near = TextObject("A", size_pt=10, x_mm=1, y_mm=1)
+    alone = render_document(Document("62", objects=[centered]))
+    assert render_document(Document("62", objects=[centered, near])).height == alone.height
+
+
+# --- Feste Rahmengröße -----------------------------------------------------------
+def test_fit_into_frame():
+    obj = TextObject("Hallo Welt", size_pt=12, fit=True, x_mm=2, y_mm=3, w_mm=30, h_mm=8)
+    doc = Document("62", length_mm=40, objects=[obj])
+    ro = render_object(obj, doc)
+    assert (ro.x, ro.y, ro.w, ro.h) == (_dots(2), _dots(3), _dots(30), _dots(8))
+    left, top, right, bottom = _ink_box(ro.image)
+    assert left >= 0 and top >= 0 and right <= ro.w and bottom <= ro.h
+    assert right - left > ro.w * 0.8 or bottom - top > ro.h * 0.8    # füllt den Rahmen
+    bigger = render_object(TextObject("Hallo Welt", size_pt=12, fit=True, x_mm=2, y_mm=3,
+                                      w_mm=60, h_mm=16), doc)
+    assert bigger.base_pt > ro.base_pt
+
+
+# --- Grundgröße ---------------------------------------------------------------
+def test_base_pt_of_auto_object_reproduces_image():
+    doc = Document("62", objects=[TextObject("Hallo")])
+    ro = render_object(doc.objects[0], doc)
+    assert 4 < ro.base_pt < 100
+    fixed = Document("62", objects=[TextObject("Hallo", size_pt=ro.base_pt)])
+    assert render_document(fixed).tobytes() == render_document(doc).tobytes()
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/document.py b/src/labelwerk/document.py
index 7c21b67..641b9b6 100644
--- a/src/labelwerk/document.py
+++ b/src/labelwerk/document.py
@@ -5,6 +5,7 @@ from dataclasses import dataclass, field
 
 ORIENTATIONS = ("vertical", "horizontal")
 ALIGNMENTS = ("left", "center", "right", "justify")
+ROTATIONS = (0, 90, 180, 270)      # Grad im Uhrzeigersinn
 MAX_MARGIN_MM = 20.0
 MIN_PT, MAX_PT = 4.0, 100.0
 
@@ -38,6 +39,17 @@ class TextObject:
     size_pt: float | None = None    # Grundgröße; None = automatisch
     font_path: str | None = None    # feste TTF-Datei für Stücke ohne Familie (CLI --font)
     fit: bool = False               # „Feste Rahmengröße“: Grundgröße + Verhältnisse, gemeinsam skaliert
+    # Rahmen in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts
+    x_mm: float | None = None       # linke obere Ecke; None = mittig auf dem Etikett
+    y_mm: float | None = None
+    w_mm: float | None = None       # Rahmengröße nur bei fit; None = bedruckbarer Bereich
+    h_mm: float | None = None
+    rotation: int = 0               # 0 | 90 | 180 | 270
+
+    @property
+    def positioned(self) -> bool:
+        """Frei platziert (sonst mittig auf dem Etikett wie bisher)."""
+        return self.x_mm is not None or self.y_mm is not None
 
     @property
     def auto(self) -> bool:
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index ef85501..52da917 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -9,11 +9,11 @@ from __future__ import annotations
 import math
 from dataclasses import dataclass
 
-from PIL import Image, ImageDraw
+from PIL import Image, ImageDraw, ImageOps
 
 from . import fonts
-from .document import (ALIGNMENTS, MAX_MARGIN_MM, MIN_PT, ORIENTATIONS, Document, Paragraph,
-                       Span, TextObject)
+from .document import (ALIGNMENTS, MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, ROTATIONS,
+                       Document, Paragraph, Span, TextObject)
 from .labels import DPI, get_label, length_limits
 
 MARGIN = 12            # Punkte, ca. 1 mm
@@ -64,54 +64,200 @@ def font_warnings(doc: Document) -> list[str]:
     return warnings
 
 
+@dataclass
+class RenderedObject:
+    """Einzeln gerendertes Objekt in Druckpunkten, in Leserichtung.
+
+    ``image``: Graustufen (L), weißer Grund, Tinte schwarz, Größe ``w`` × ``h``;
+    ``x``/``y``: linke obere Ecke des Rahmens auf dem Etikett; ``base_pt``: wirksame Grundgröße.
+    """
+    image: Image.Image
+    x: int
+    y: int
+    w: int
+    h: int
+    base_pt: float
+
+
+def render_object(obj: TextObject, doc: Document, model: str = "QL-600") -> RenderedObject:
+    """Ein Objekt einzeln rendern (Arbeitsfläche); Position bezogen auf das Etikett von ``doc``."""
+    sheet = _sheet(doc, model)
+    prep = _prepare(obj, sheet)
+    width = height = 0
+    if not obj.positioned:                     # mittig: braucht die Etikettgröße
+        others = [_prepare(o, sheet) for o in doc.objects if o is not obj]
+        width, height = _label_size(sheet, [prep, *others])
+    return _finish(prep, sheet, width, height)
+
+
 def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
     """Dokument als Druckbild in exakter Auflösung (Vorschau = Druck).
 
+    Objekte werden einzeln gerendert und in Listenreihenfolge (hinten → vorne) aufgeklebt;
+    nur ihre Tinte deckt, über das Etikett ragende Teile werden abgeschnitten.
     Gerendert wird in Leserichtung; bei Ausrichtung „horizontal“ (Text längs zum Band)
     wird das Bild danach für den Drucker um 90° im Uhrzeigersinn gedreht – so kommt der
     Textanfang zuerst aus dem Drucker und das veränderliche Ende liegt in Leserichtung rechts.
     """
+    sheet = _sheet(doc, model)
+    preps = [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]]
+    width, height = _label_size(sheet, preps)
+    img = Image.new("RGB", (width, height), "white")
+    for prep in preps:
+        rendered = _finish(prep, sheet, width, height)
+        img.paste((0, 0, 0), (rendered.x, rendered.y), ImageOps.invert(rendered.image))
+    return img.rotate(-90, expand=True) if sheet.horizontal else img
+
+
+# --- Etikett und Objekte ------------------------------------------------------------
+@dataclass
+class _Sheet:
+    """Etikett in Druckpunkten; ``feed`` None = Länge automatisch (Endlosband)."""
+    label_id: str
+    horizontal: bool
+    across: int                # quer zum Band (fest)
+    feed: int | None           # in Bandlaufrichtung
+    margin: int                # Rand in Bandlaufrichtung
+    min_len: int
+    max_len: int
+
+    def room(self) -> tuple[int, int]:
+        """Bedruckbarer Bereich (Breite, Höhe) in Leserichtung; automatische Länge: Höchstlänge."""
+        across = self.across - 2 * MARGIN
+        feed = (self.feed or self.max_len) - 2 * self.margin
+        return (feed, across) if self.horizontal else (across, feed)
+
+
+def _sheet(doc: Document, model: str) -> _Sheet:
     if doc.orientation not in ORIENTATIONS:
         raise ValueError(f"Unbekannte Ausrichtung {doc.orientation!r} – erlaubt: horizontal, vertical")
-    horizontal = doc.orientation == "horizontal"
     label = get_label(doc.label_id)
     min_len, max_len = length_limits(model)
     margin = round(min(max(doc.margin_mm, 0.0), MAX_MARGIN_MM) * DPI / 25.4)
-    across = label.width                      # quer zum Band (fest)
-    feed = label.height                       # in Bandlaufrichtung; None = automatisch
+    feed = label.height
     if feed is None and doc.length_mm is not None:
-        feed = min(max(round(doc.length_mm * DPI / 25.4), min_len), max_len)
+        feed = min(max(_dots(doc.length_mm), min_len), max_len)
     if feed is not None:                      # feste Länge: Rand darf nicht alles aufbrauchen
         margin = min(margin, max(0, (feed - 2 * MARGIN) // 2))
-    obj = doc.objects[0] if doc.objects else TextObject("")
+    return _Sheet(doc.label_id, doc.orientation == "horizontal", label.width, feed, margin,
+                  min_len, max_len)
+
+
+def _dots(mm: float) -> int:
+    return round(mm * DPI / 25.4)
+
+
+@dataclass
+class _Prepared:
+    """Gemessenes Objekt: Grundgröße, Zeilen (an der breitesten Zeile ausgerichtet), Tintenbox."""
+    obj: TextObject
+    base: int
+    lines: list
+    box: tuple[int, int, int, int]
+    frame: tuple[int, int] | None      # feste Rahmengröße positionierter Objekte (ungedreht)
+
+    def size(self) -> tuple[int, int]:
+        """Rahmengröße nach dem Drehen."""
+        l, t, r, b = self.box
+        w, h = self.frame or (r - l, b - t)
+        return (h, w) if self.obj.rotation in (90, 270) else (w, h)
+
+
+def _prepare(obj: TextObject, sheet: _Sheet) -> _Prepared:
     for para in obj.paragraphs:
         if para.align not in ALIGNMENTS:
             raise ValueError(f"Unbekannte Textposition {para.align!r} – erlaubt: links, zentriert, "
                              "rechts, Blocksatz (left, center, right, justify)")
-
-    across_room = across - 2 * MARGIN
-    feed_room = (feed if feed else max_len) - 2 * margin
-    max_w, max_h = (feed_room, across_room) if horizontal else (across_room, feed_room)
-    base = _fit(obj, max(10, across // 5), max_w, max_h, doc.label_id)
+    if obj.rotation not in ROTATIONS:
+        raise ValueError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
+    max_w, max_h = sheet.room()
+    if obj.rotation in (90, 270):
+        max_w, max_h = max_h, max_w
+    auto_start = max(10, sheet.across // 5)
+    frame = None
+    if obj.positioned and obj.fit:
+        frame = (_dots(obj.w_mm) if obj.w_mm is not None else max_w,
+                 _dots(obj.h_mm) if obj.h_mm is not None else max_h)
+        if obj.w_mm is not None or obj.h_mm is not None:
+            auto_start = round(MAX_PT * PT)    # eigener Rahmen: Text füllt ihn aus
+        base = _fit(obj, auto_start, *frame, sheet.label_id)
+    elif obj.positioned and not obj.auto:
+        base = round(obj.size_pt * PT)         # darf hinausragen – kein TextTooLarge
+    else:
+        base = _fit(obj, auto_start, max_w, max_h, sheet.label_id)
     lines = _shape(obj, base)
-    l, t, r, b = _block_box(lines)
+    return _Prepared(obj, base, lines, _block_box(lines), frame)
+
 
-    text_w, text_h = r - l, b - t
+def _label_size(sheet: _Sheet, preps: list[_Prepared]) -> tuple[int, int]:
+    """Etikettgröße in Leserichtung; automatische Länge aus dem Platzbedarf der Objekte."""
+    feed = sheet.feed
     if feed is None:
-        feed = min(max((text_w if horizontal else text_h) + 2 * margin, min_len), max_len)
-    width, height = (feed, across) if horizontal else (across, feed)
-    img = Image.new("RGB", (width, height), "white")
-    x0 = (width - text_w) // 2 - l
-    if any(para.align != "center" for para in obj.paragraphs):
-        # Textrahmen über die volle Breite in Leserichtung: Absätze richten sich am Rahmen aus
-        start = margin if horizontal else MARGIN
-        frame = width - 2 * start
-        lines = _shape(obj, base, frame=frame)
+        needed = 0
+        for prep in preps:
+            w, h = prep.size()
+            size = w if sheet.horizontal else h
+            if prep.obj.positioned:
+                start = prep.obj.x_mm if sheet.horizontal else prep.obj.y_mm
+                needed = max(needed, _dots(start or 0) + size + sheet.margin)
+            else:
+                needed = max(needed, size + 2 * sheet.margin)
+        feed = min(max(needed, sheet.min_len), sheet.max_len)
+    return (feed, sheet.across) if sheet.horizontal else (sheet.across, feed)
+
+
+def _finish(prep: _Prepared, sheet: _Sheet, width: int, height: int) -> RenderedObject:
+    """Objektbild zeichnen und auf dem Etikett (``width`` × ``height``) platzieren."""
+    obj = prep.obj
+    lines, (l, t, r, b) = prep.lines, prep.box
+    if obj.positioned:
+        if prep.frame is None:                 # Rahmen = Tintenbox des Textes
+            w, h = r - l, b - t
+            image = _paint(lines, -l, -t, w, h)
+        else:                                  # Text im festen Rahmen ausgerichtet
+            w, h = prep.frame
+            x0, y0, lines = _align(obj, prep.base, lines, prep.box, 0, w, h)
+            image = _paint(lines, x0, y0, w, h)
+        x, y = _dots(obj.x_mm or 0), _dots(obj.y_mm or 0)
+    else:                                      # mittig auf dem Etikett wie bisher
+        start = sheet.margin if sheet.horizontal else MARGIN
+        x0, y0, lines = _align(obj, prep.base, lines, prep.box, start, width, height)
         fl, ft, fr, fb = _block_box(lines)
-        x0 = min(max(start, -fl), width - fr)            # Tinte bleibt im Bild
-        t, text_h = ft, fb - ft
-    _draw(img, lines, x0, (height - text_h) // 2 - t)
-    return img.rotate(-90, expand=True) if horizontal else img
+        x, y = x0 + fl, y0 + ft
+        image = _paint(lines, -fl, -ft, fr - fl, fb - ft)
+    if obj.rotation:
+        image = image.transpose(_TRANSPOSE[obj.rotation])
+        if not obj.positioned:
+            x, y = (width - image.width) // 2, (height - image.height) // 2
+    base_pt = obj.size_pt if not obj.auto else prep.base / PT
+    return RenderedObject(image, x, y, image.width, image.height, base_pt)
+
+
+_TRANSPOSE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
+              270: Image.Transpose.ROTATE_90}     # im Uhrzeigersinn
+
+
+def _align(obj: TextObject, base: int, lines: list, box: tuple[int, int, int, int],
+           start: int, width: int, height: int) -> tuple[int, int, list]:
+    """Ursprung des Textblocks in einem Rahmen ``width`` × ``height`` (Innenrand ``start``)."""
+    l, t, r, b = box
+    x0 = (width - (r - l)) // 2 - l
+    if any(para.align != "center" for para in obj.paragraphs):
+        # Absätze richten sich an der Rahmenbreite aus
+        lines = _shape(obj, base, frame=width - 2 * start)
+        fl, t, fr, b = _block_box(lines)
+        x0 = min(max(start, -fl), width - fr)            # Tinte bleibt im Rahmen
+    return x0, (height - (b - t)) // 2 - t, lines
+
+
+def _paint(lines: list, x0: int, y0: int, width: int, height: int) -> Image.Image:
+    """Zeilen in ein Graustufenbild zeichnen, Blockursprung bei (x0, y0)."""
+    # Rand, damit keine Zeichenkoordinate negativ wird (Pillow rundet dort anders)
+    pad = max((p.dots for pieces in lines for p in pieces), default=0)
+    px, py = pad + max(0, -x0), pad + max(0, -y0)
+    canvas = Image.new("L", (px + max(width, 1), py + max(height, 1)), 255)
+    _draw(canvas, lines, x0 + px, y0 + py)
+    return canvas.crop((px, py, px + width, py + height))
 
 
 # --- Schriftgrößen ----------------------------------------------------------
@@ -286,4 +432,4 @@ def _draw_slanted(img: Image.Image, p: _Piece, x: float, y: float) -> None:
     ImageDraw.Draw(mask).text((pad, 0), p.text, fill=255, font=p.font, anchor="la")
     sheared = mask.transform(mask.size, Image.Transform.AFFINE,
                              (1, _SLANT, -_SLANT * ascent, 0, 1, 0), Image.Resampling.BICUBIC)
-    img.paste((0, 0, 0), (round(x) - pad, round(y)), sheared)
+    img.paste(0, (round(x) - pad, round(y)), sheared)
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `342 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/document.py src/labelwerk/render.py tests/_render_before_3d.py tests/test_placement_render.py
git commit -m "Kern: Objekte einzeln rendern – Position, Rahmen, Drehen, Zusammensetzen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Kern – Platzier-Logik (`layout.py`)

**Files:**
- Create: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/render.py`
- Create: `tests/test_layout.py`

**Interfaces / Produces:** `layout.Rect(x, y, w, h)` (mm, frozen; `right`, `bottom`, `cx`, `cy`, `moved`, `at`), `object_rect`, `label_rect`, `printable_area(doc, model)`, `snap(moving, targets, area, tol, label=None) -> Snap(dx, dy, guides)`, `bounds`, `align`, `match_size`, `maximize`, `place(obj, rect)`, `scale_text(obj, factor, base_pt=None)`, `objects_outside(doc, model) -> list[int]`; `render.label_size`, `render.label_margins` (öffentlich).

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/test_layout.py b/tests/test_layout.py
new file mode 100644
index 0000000..d6cc9cc
--- /dev/null
+++ b/tests/test_layout.py
@@ -0,0 +1,360 @@
+"""Platzier-Logik ohne Qt: Einrasten, Ausrichten, Größe angleichen, Skalieren (Etappe 3d-1)."""
+import pytest
+
+from labelwerk import layout
+from labelwerk.document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
+from labelwerk.labels import DPI
+from labelwerk.layout import Rect, Snap
+from labelwerk.render import MARGIN, RenderedObject, render_document, render_object
+
+
+def _mm(dots):
+    return dots * 25.4 / DPI
+
+
+def _approx(rect, **kw):
+    """Rechteck mit Rundungsspielraum vergleichen (pytest.approx kennt keine Dataclasses)."""
+    return pytest.approx((rect.x, rect.y, rect.w, rect.h), **kw)
+
+
+def _t(rect):
+    return (rect.x, rect.y, rect.w, rect.h)
+
+
+def _reading_size(doc):
+    img = render_document(doc)
+    return img.size[::-1] if doc.orientation == "horizontal" else img.size
+
+
+# --- Rect -------------------------------------------------------------------------
+def test_rect_helpers():
+    r = Rect(1, 2, 10, 4)
+    assert (r.right, r.bottom, r.cx, r.cy) == (11, 6, 6, 4)
+
+
+def test_rect_is_frozen():
+    with pytest.raises(AttributeError):
+        Rect(0, 0, 1, 1).x = 5
+
+
+def test_rect_moved_and_resized():
+    r = Rect(1, 2, 10, 4)
+    assert r.moved(2, -1) == Rect(3, 1, 10, 4)
+    assert r.at(0, 0) == Rect(0, 0, 10, 4)
+
+
+def test_object_rect_converts_dots_to_mm():
+    rendered = RenderedObject(None, 118, 236, 354, 59, 12.0)
+    expected = Rect(_mm(118), _mm(236), _mm(354), _mm(59))
+    assert _t(layout.object_rect(rendered)) == _approx(expected)
+
+
+# --- Etikett und bedruckbarer Bereich ---------------------------------------------
+@pytest.mark.parametrize("doc", [
+    Document("62x29"),
+    Document("62x29", orientation="horizontal"),
+    Document("62", length_mm=50, margin_mm=3),
+    Document("62", length_mm=50, margin_mm=3, orientation="horizontal"),
+    Document("62", objects=[TextObject("Automatische Länge")]),
+    Document("62", objects=[TextObject("Längs", size_pt=30)], orientation="horizontal"),
+    Document("62", objects=[TextObject("A", size_pt=20, x_mm=70, y_mm=5)]),
+    Document("29", objects=[TextObject("B", size_pt=20, x_mm=90, y_mm=2)], orientation="horizontal"),
+], ids=range(8))
+def test_label_rect_matches_render_document(doc):
+    w, h = _reading_size(doc)
+    assert _t(layout.label_rect(doc)) == _approx(Rect(0, 0, _mm(w), _mm(h)))
+
+
+def test_printable_area_vertical_margins():
+    doc = Document("62x29", margin_mm=2)
+    label = layout.label_rect(doc)
+    feed = _mm(round(2 * DPI / 25.4))
+    area = layout.printable_area(doc)
+    assert _t(area) == _approx(Rect(_mm(MARGIN), feed, label.w - 2 * _mm(MARGIN),
+                                      label.h - 2 * feed))
+
+
+def test_printable_area_horizontal_swaps_margins():
+    doc = Document("62x29", margin_mm=2, orientation="horizontal")
+    label = layout.label_rect(doc)
+    feed = _mm(round(2 * DPI / 25.4))
+    area = layout.printable_area(doc)
+    assert _t(area) == _approx(Rect(feed, _mm(MARGIN), label.w - 2 * feed,
+                                      label.h - 2 * _mm(MARGIN)))
+
+
+def test_printable_area_is_centered_on_label():
+    doc = Document("62", length_mm=40, margin_mm=4)
+    area, label = layout.printable_area(doc), layout.label_rect(doc)
+    assert (area.cx, area.cy) == pytest.approx((label.cx, label.cy))
+
+
+# --- Einrasten --------------------------------------------------------------------
+_AREA = Rect(1, 1, 60, 28)
+_LABEL = Rect(0, 0, 62, 30)
+
+
+def test_snap_without_candidates_in_reach_does_nothing():
+    moving = Rect(20, 9, 5, 5)
+    assert layout.snap(moving, [], _AREA, 0.5) == Snap(0, 0, [])
+
+
+def test_snap_left_edge_to_area():
+    s = layout.snap(Rect(1.3, 9, 5, 5), [], _AREA, 0.5)
+    assert s.dx == pytest.approx(-0.3) and s.dy == 0
+    assert s.guides == [("x", 1)]
+
+
+def test_snap_right_and_bottom_edge_to_area():
+    s = layout.snap(Rect(55.8, 23.6, 5, 5), [], _AREA, 0.5)
+    assert (s.dx, s.dy) == pytest.approx((0.2, 0.4))
+    assert sorted(s.guides) == [("x", 61), ("y", 29)]
+
+
+def test_snap_center_to_label_center():
+    s = layout.snap(Rect(28.6, 12.3, 5, 5), [], _AREA, 0.5, label=_LABEL)
+    assert (s.dx, s.dy) == pytest.approx((-0.1, 0.2))
+    assert sorted(s.guides) == [("x", 31), ("y", 15)]
+
+
+def test_snap_to_label_edge():
+    s = layout.snap(Rect(0.2, 9, 5, 5), [], _AREA, 0.3, label=_LABEL)
+    assert s.dx == pytest.approx(-0.2) and s.guides == [("x", 0)]
+
+
+def test_snap_to_target_edges_and_centers():
+    target = Rect(30, 5, 10, 4)                    # Mitte (35, 7)
+    s = layout.snap(Rect(20.3, 4.8, 4, 3), [target], _AREA, 0.5)
+    assert s.dx == 0                               # waagrecht nichts in Reichweite
+    # Oberkante 4,8 → 5; Mitte 6,3 und Unterkante 7,8 liegen zu weit von 7 und 9
+    assert s.dy == pytest.approx(0.2) and s.guides == [("y", 5)]
+    s = layout.snap(Rect(32.8, 20, 4, 2), [target], _AREA, 0.5)
+    assert s.dx == pytest.approx(0.2) and s.guides == [("x", 35)]   # Mitte an Mitte
+
+
+def test_snap_picks_nearest_candidate():
+    targets = [Rect(10.4, 20, 5, 5), Rect(10.1, 20, 5, 5)]
+    s = layout.snap(Rect(10, 2, 2, 2), targets, _AREA, 0.5)
+    assert s.dx == pytest.approx(0.1) and s.guides == [("x", 10.1)]
+
+
+def test_snap_tolerance_boundary_is_inclusive():
+    assert layout.snap(Rect(1.5, 9, 5, 5), [], _AREA, 0.5).dx == pytest.approx(-0.5)
+    assert layout.snap(Rect(1.51, 9, 5, 5), [], _AREA, 0.5).dx == 0
+
+
+def test_snap_zero_tolerance_only_exact():
+    assert layout.snap(Rect(1, 9, 5, 5), [], _AREA, 0).guides == [("x", 1)]
+    assert layout.snap(Rect(1.01, 9, 5, 5), [], _AREA, 0) == Snap(0, 0, [])
+
+
+def test_snap_reports_all_lines_that_match_after_shift():
+    # gleich breit wie das Ziel: linke und rechte Kante (und Mitte) treffen gleichzeitig
+    target = Rect(30, 5, 10, 4)
+    s = layout.snap(Rect(30.2, 16, 10, 4), [target], _AREA, 0.5)
+    assert s.dx == pytest.approx(-0.2)
+    assert sorted(s.guides) == [("x", 30), ("x", 35), ("x", 40)]
+
+
+# --- Ausrichten -------------------------------------------------------------------
+_RECTS = [Rect(5, 2, 10, 4), Rect(20, 8, 6, 10), Rect(12, 15, 4, 2)]
+
+
+@pytest.mark.parametrize("mode, expected", [
+    ("left", [5, 5, 5]),
+    ("right", [16, 20, 22]),              # rechte Kanten auf 26
+    ("hcenter", [10.5, 12.5, 13.5]),      # Mitte der Auswahl 15,5
+])
+def test_align_horizontally_to_each_other(mode, expected):
+    out = layout.align(_RECTS, mode)
+    assert [r.x for r in out] == pytest.approx(expected)
+    assert [r.y for r in out] == [r.y for r in _RECTS]
+    assert [(r.w, r.h) for r in out] == [(r.w, r.h) for r in _RECTS]
+
+
+@pytest.mark.parametrize("mode, expected", [
+    ("top", [2, 2, 2]),
+    ("bottom", [14, 8, 16]),              # Unterkanten auf 18
+    ("vcenter", [8, 5, 9]),               # Mitte der Auswahl 10
+])
+def test_align_vertically_to_each_other(mode, expected):
+    out = layout.align(_RECTS, mode)
+    assert [r.y for r in out] == pytest.approx(expected)
+    assert [r.x for r in out] == [r.x for r in _RECTS]
+
+
+@pytest.mark.parametrize("mode, attr, value", [
+    ("left", "x", 1), ("right", "right", 61), ("hcenter", "cx", 31),
+    ("top", "y", 1), ("bottom", "bottom", 29), ("vcenter", "cy", 15),
+])
+def test_align_to_area(mode, attr, value):
+    out = layout.align(_RECTS, mode, area=_AREA)
+    assert [getattr(r, attr) for r in out] == pytest.approx([value] * 3)
+
+
+def test_bounds_encloses_all_rects():
+    assert layout.bounds(_RECTS) == Rect(5, 2, 21, 16)
+    assert layout.bounds([Rect(3, 4, 5, 6)]) == Rect(3, 4, 5, 6)
+
+
+def test_align_single_rect_without_area_is_noop():
+    assert layout.align([Rect(3, 4, 5, 6)], "left") == [Rect(3, 4, 5, 6)]
+    assert layout.align([], "left") == []
+
+
+def test_align_single_rect_to_area_moves():
+    assert layout.align([Rect(3, 4, 5, 6)], "right", area=_AREA) == [Rect(56, 4, 5, 6)]
+
+
+def test_align_unknown_mode_raises():
+    with pytest.raises(ValueError, match="Ausrichtung"):
+        layout.align(_RECTS, "diagonal")
+
+
+# --- Größe angleichen, maximieren -------------------------------------------------
+def test_match_size_uses_first_rect_as_reference():
+    out = layout.match_size(_RECTS, "same")
+    assert out[0] == _RECTS[0]
+    assert all((r.w, r.h) == (10, 4) for r in out)
+    assert [(r.x, r.y) for r in out] == [(r.x, r.y) for r in _RECTS]   # linke obere Ecke bleibt
+
+
+def test_match_width_and_height():
+    assert [(r.w, r.h) for r in layout.match_size(_RECTS, "width")] == [(10, 4), (10, 10), (10, 2)]
+    assert [(r.w, r.h) for r in layout.match_size(_RECTS, "height")] == [(10, 4), (6, 4), (4, 4)]
+
+
+def test_match_size_edge_cases():
+    assert layout.match_size([], "same") == []
+    with pytest.raises(ValueError, match="Größe"):
+        layout.match_size(_RECTS, "quadrat")
+
+
+def test_maximize_wide_rect_fills_width_centered():
+    r = layout.maximize(Rect(10, 10, 20, 5), _AREA)        # Seitenverhältnis 4:1
+    assert _t(r) == _approx(Rect(1, 15 - 7.5, 60, 15))
+
+
+def test_maximize_tall_rect_fills_height_centered():
+    r = layout.maximize(Rect(10, 10, 7, 14), _AREA)        # 1:2 → Höhe 28
+    assert _t(r) == _approx(Rect(31 - 7, 1, 14, 28))
+
+
+def test_maximize_degenerate_rect_is_only_centered():
+    assert layout.maximize(Rect(3, 3, 0, 5), _AREA) == Rect(31, 12.5, 0, 5)
+
+
+# --- Platzieren -------------------------------------------------------------------
+def test_place_sets_position_without_touching_original():
+    obj = TextObject("A", size_pt=12)
+    placed = layout.place(obj, Rect(4, 5, 30, 10))
+    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (4, 5, None, None)
+    assert obj.x_mm is None and placed is not obj
+    assert placed.paragraphs is not obj.paragraphs
+
+
+def test_place_fit_object_sets_frame_size():
+    obj = TextObject("A", size_pt=12, fit=True)
+    placed = layout.place(obj, Rect(4, 5, 30, 10))
+    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (4, 5, 30, 10)
+
+
+def test_place_rotated_fit_object_stores_unrotated_frame():
+    obj = TextObject("A", size_pt=12, fit=True, rotation=90)
+    placed = layout.place(obj, Rect(4, 5, 10, 30))
+    assert (placed.w_mm, placed.h_mm) == (30, 10)
+    doc = Document("62", length_mm=60, objects=[placed])
+    rect = layout.object_rect(render_object(placed, doc))
+    assert _t(rect) == _approx(Rect(4, 5, 10, 30), abs=_mm(1))
+
+
+# --- Text skalieren ---------------------------------------------------------------
+def _sizes(obj):
+    return obj.size_pt, [s.size_pt for p in obj.paragraphs for s in p.spans]
+
+
+def test_scale_text_scales_base_and_spans():
+    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=20)])], size_pt=10)
+    scaled = layout.scale_text(obj, 1.5)
+    assert _sizes(scaled) == (15, [None, 30])
+    assert _sizes(obj) == (10, [None, 20])                 # Original unverändert
+
+
+def test_scale_text_clamps_factor_to_keep_ratios():
+    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=40)])], size_pt=20)
+    assert _sizes(layout.scale_text(obj, 10)) == (50, [None, MAX_PT])
+    assert _sizes(layout.scale_text(obj, 0.01)) == (MIN_PT, [None, 8])
+
+
+def test_scale_text_at_limit_keeps_sizes():
+    # größtes Stück schon 100 pt: Vergrößern ändert nichts, Verhältnisse bleiben
+    obj = TextObject([Paragraph([Span("a", size_pt=5), Span("b", size_pt=100)])], size_pt=10)
+    assert _sizes(layout.scale_text(obj, 2)) == (10, [5, 100])
+    obj = TextObject([Paragraph([Span("a", size_pt=4), Span("b", size_pt=100)])], size_pt=50)
+    assert _sizes(layout.scale_text(obj, 0.5)) == (50, [4, 100])
+
+
+def test_scale_text_clamps_each_size_when_ratio_too_wide():
+    # Größen außerhalb 4–100 (z. B. von Hand bearbeitet): jede Größe für sich begrenzt
+    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=100)])], size_pt=2)
+    assert _sizes(layout.scale_text(obj, 1.5)) == (MIN_PT, [None, MAX_PT])
+
+
+def test_scale_text_rounds_to_tenth():
+    obj = TextObject("A", size_pt=10)
+    assert layout.scale_text(obj, 1.2345).size_pt == 12.3
+
+
+def test_scale_text_auto_size_uses_effective_base():
+    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=24)])])   # relativ zu 12 pt
+    scaled = layout.scale_text(obj, 2, base_pt=18)
+    # bisher wirksam: Grundgröße 18, Stück 24/12 × 18 = 36 → doppelt
+    assert _sizes(scaled) == (36, [None, 72])
+
+
+def test_scale_text_auto_size_without_base_raises():
+    with pytest.raises(ValueError, match="Schriftgröße"):
+        layout.scale_text(TextObject("A"), 2)
+
+
+def test_scale_text_rejects_non_positive_factor():
+    with pytest.raises(ValueError, match="Faktor"):
+        layout.scale_text(TextObject("A", size_pt=10), 0)
+
+
+def test_scale_text_renders_proportionally_larger():
+    obj = TextObject("Hallo", size_pt=10, x_mm=2, y_mm=2)
+    doc = Document("62", length_mm=80, objects=[obj])
+    small = render_object(obj, doc)
+    big = render_object(layout.scale_text(obj, 2), doc)
+    assert big.w == pytest.approx(2 * small.w, rel=0.08)
+
+
+# --- Objekte außerhalb ------------------------------------------------------------
+def test_objects_outside_none_for_centered_and_inside():
+    doc = Document("62", length_mm=40, objects=[TextObject("Mitte"),
+                                                 TextObject("A", size_pt=12, x_mm=5, y_mm=5)])
+    assert layout.objects_outside(doc) == []
+
+
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_objects_outside_lists_overhanging_indices(orientation):
+    doc = Document("62", length_mm=40, orientation=orientation, objects=[
+        TextObject("innen", size_pt=12, x_mm=5, y_mm=5),
+        TextObject("rechts", size_pt=12, x_mm=60, y_mm=5) if orientation == "vertical"
+        else TextObject("unten", size_pt=12, x_mm=5, y_mm=60),
+        TextObject("innen", size_pt=12, x_mm=2, y_mm=10),
+        TextObject("negativ", size_pt=12, x_mm=-1, y_mm=5),
+    ])
+    assert layout.objects_outside(doc) == [1, 3]
+
+
+def test_objects_outside_auto_length_grows_instead():
+    # automatische Länge: in Bandlaufrichtung wächst das Etikett mit
+    doc = Document("62", objects=[TextObject("weit unten", size_pt=12, x_mm=5, y_mm=150)])
+    assert layout.objects_outside(doc) == []
+
+
+def test_objects_outside_ignores_empty_objects():
+    doc = Document("62", length_mm=40, objects=[TextObject("", size_pt=12, x_mm=200, y_mm=200)])
+    assert layout.objects_outside(doc) == []
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
new file mode 100644
index 0000000..09b921f
--- /dev/null
+++ b/src/labelwerk/layout.py
@@ -0,0 +1,220 @@
+"""Platzier-Logik ohne Qt: Einrasten, Ausrichten, Größe angleichen, Skalieren.
+
+Alle Rechtecke in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts
+(wie ``TextObject.x_mm``/``y_mm``). Die GUI rechnet nur in Bildschirmkoordinaten um.
+"""
+from __future__ import annotations
+
+import copy
+from dataclasses import dataclass, field, replace
+
+from .document import MAX_PT, MIN_PT, Document, TextObject
+from .labels import DPI
+from .render import REF_PT, RenderedObject, label_margins, label_size, render_object
+
+ALIGN_MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom")
+SIZE_MODES = ("same", "width", "height")
+_EPS = 1e-6                # Rundungsspielraum beim Vergleich von mm-Werten
+
+
+def _mm(dots: float) -> float:
+    return dots * 25.4 / DPI
+
+
+@dataclass(frozen=True)
+class Rect:
+    """Rechteck in mm: linke obere Ecke ``x``/``y``, Breite ``w``, Höhe ``h``."""
+    x: float
+    y: float
+    w: float
+    h: float
+
+    @property
+    def right(self) -> float:
+        return self.x + self.w
+
+    @property
+    def bottom(self) -> float:
+        return self.y + self.h
+
+    @property
+    def cx(self) -> float:
+        return self.x + self.w / 2
+
+    @property
+    def cy(self) -> float:
+        return self.y + self.h / 2
+
+    def moved(self, dx: float, dy: float) -> "Rect":
+        return replace(self, x=self.x + dx, y=self.y + dy)
+
+    def at(self, x: float, y: float) -> "Rect":
+        return replace(self, x=x, y=y)
+
+
+@dataclass
+class Snap:
+    """Ergebnis des Einrastens: Verschiebung in mm und Hilfslinien ``("x" | "y", mm)``."""
+    dx: float = 0.0
+    dy: float = 0.0
+    guides: list[tuple[str, float]] = field(default_factory=list)
+
+
+# --- Etikett ----------------------------------------------------------------------
+def object_rect(rendered: RenderedObject) -> Rect:
+    """Rahmen eines gerenderten Objekts in mm."""
+    return Rect(_mm(rendered.x), _mm(rendered.y), _mm(rendered.w), _mm(rendered.h))
+
+
+def label_rect(doc: Document, model: str = "QL-600") -> Rect:
+    """Ganzes Etikett in mm (bei automatischer Länge so lang, wie ``render_document`` es macht)."""
+    w, h = label_size(doc, model)
+    return Rect(0.0, 0.0, _mm(w), _mm(h))
+
+
+def printable_area(doc: Document, model: str = "QL-600") -> Rect:
+    """Bedruckbarer Bereich: Etikett minus Rand in Bandlaufrichtung bzw. quer dazu."""
+    w, h = label_size(doc, model)
+    mx, my = label_margins(doc, model)
+    return Rect(_mm(mx), _mm(my), _mm(w - 2 * mx), _mm(h - 2 * my))
+
+
+# --- Einrasten --------------------------------------------------------------------
+def snap(moving: Rect, targets: list[Rect], area: Rect, tolerance_mm: float,
+         label: Rect | None = None) -> Snap:
+    """Kanten und Mitte von ``moving`` an nahe Linien einrasten lassen.
+
+    Kandidaten: Kanten und Mitte des bedruckbaren Bereichs, des Etiketts (falls angegeben)
+    und der anderen Objekte. Je Achse gewinnt der nächste Kandidat innerhalb der Toleranz
+    (Grenze eingeschlossen); ``guides`` nennt alle Linien, die nach dem Einrasten getroffen
+    werden.
+    """
+    frames = [area, *([label] if label else []), *targets]
+    dx, x_guides = _snap_axis((moving.x, moving.cx, moving.right),
+                              [v for r in frames for v in (r.x, r.cx, r.right)], tolerance_mm)
+    dy, y_guides = _snap_axis((moving.y, moving.cy, moving.bottom),
+                              [v for r in frames for v in (r.y, r.cy, r.bottom)], tolerance_mm)
+    return Snap(dx, dy, [("x", v) for v in x_guides] + [("y", v) for v in y_guides])
+
+
+def _snap_axis(points: tuple[float, ...], candidates: list[float],
+               tolerance: float) -> tuple[float, list[float]]:
+    """Kleinste Verschiebung eines Punkts auf einen Kandidaten und die danach getroffenen Linien."""
+    shifts = [c - p for p in points for c in candidates if abs(c - p) <= tolerance + _EPS]
+    if not shifts:
+        return 0.0, []
+    best = min(shifts, key=abs)
+    hits: list[float] = []
+    for cand in sorted(candidates):
+        hit = any(abs(p + best - cand) <= _EPS for p in points)
+        if hit and not (hits and cand - hits[-1] <= _EPS):
+            hits.append(cand)
+    return best, hits
+
+
+# --- Ausrichten, Größe ------------------------------------------------------------
+def bounds(rects: list[Rect]) -> Rect:
+    """Umgebendes Rechteck (z. B. der Auswahl); mindestens ein Rechteck nötig."""
+    x, y = min(r.x for r in rects), min(r.y for r in rects)
+    return Rect(x, y, max(r.right for r in rects) - x, max(r.bottom for r in rects) - y)
+
+
+def align(rects: list[Rect], mode: str, area: Rect | None = None) -> list[Rect]:
+    """Rechtecke ausrichten – mit ``area`` am Papier, sonst aneinander.
+
+    Bezug aneinander: äußerste Kante bzw. Mitte der Auswahl; ein einzelnes Rechteck
+    ohne ``area`` bleibt, wo es ist.
+    """
+    if mode not in ALIGN_MODES:
+        raise ValueError(f"Unbekannte Ausrichtung {mode!r} – erlaubt: {', '.join(ALIGN_MODES)}")
+    if area is None:
+        if len(rects) < 2:
+            return list(rects)
+        area = bounds(rects)
+    place = {
+        "left": lambda r: r.at(area.x, r.y),
+        "hcenter": lambda r: r.at(area.cx - r.w / 2, r.y),
+        "right": lambda r: r.at(area.right - r.w, r.y),
+        "top": lambda r: r.at(r.x, area.y),
+        "vcenter": lambda r: r.at(r.x, area.cy - r.h / 2),
+        "bottom": lambda r: r.at(r.x, area.bottom - r.h),
+    }[mode]
+    return [place(r) for r in rects]
+
+
+def match_size(rects: list[Rect], mode: str) -> list[Rect]:
+    """Größe an das erste Rechteck angleichen (``same``, ``width``, ``height``); Ecke bleibt."""
+    if mode not in SIZE_MODES:
+        raise ValueError(f"Unbekannte Größenangleichung {mode!r} – erlaubt: {', '.join(SIZE_MODES)}")
+    if not rects:
+        return []
+    ref = rects[0]
+    w = mode in ("same", "width")
+    h = mode in ("same", "height")
+    return [replace(r, w=ref.w if w else r.w, h=ref.h if h else r.h) for r in rects]
+
+
+def maximize(rect: Rect, area: Rect) -> Rect:
+    """Größtmöglich in ``area`` bei gleichem Seitenverhältnis, mittig darin."""
+    if rect.w > 0 and rect.h > 0:
+        factor = min(area.w / rect.w, area.h / rect.h)
+        rect = replace(rect, w=rect.w * factor, h=rect.h * factor)
+    return rect.at(area.cx - rect.w / 2, area.cy - rect.h / 2)
+
+
+# --- Objekte ----------------------------------------------------------------------
+def place(obj: TextObject, rect: Rect) -> TextObject:
+    """Kopie von ``obj`` an ``rect``; bei fester Rahmengröße auch Breite/Höhe (ungedreht)."""
+    placed = copy.deepcopy(obj)
+    placed.x_mm, placed.y_mm = rect.x, rect.y
+    if obj.fit:
+        w, h = (rect.h, rect.w) if obj.rotation in (90, 270) else (rect.w, rect.h)
+        placed.w_mm, placed.h_mm = w, h
+    return placed
+
+
+def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) -> TextObject:
+    """Kopie mit allen Schriftgrößen (Grundgröße und Stücke) × ``factor``, auf 4–100 pt begrenzt.
+
+    Der Faktor wird so begrenzt, dass die Verhältnisse erhalten bleiben; nur wenn die Größen
+    schon weiter auseinanderliegen als 4–100 pt, wird jede Größe für sich begrenzt.
+    ``base_pt``: wirksame Grundgröße (``RenderedObject.base_pt``) für Text mit automatischer
+    Größe – Stücke mit eigener Größe beziehen sich dann auf 12 pt und werden umgerechnet.
+    """
+    if factor <= 0:
+        raise ValueError(f"Faktor muss größer als 0 sein, nicht {factor!r}.")
+    scaled = copy.deepcopy(obj)
+    spans = [span for para in scaled.paragraphs for span in para.spans
+             if span.size_pt is not None]
+    if obj.size_pt is None:
+        if base_pt is None:
+            raise ValueError("Text mit automatischer Schriftgröße braucht die wirksame "
+                             "Grundgröße (base_pt) zum Skalieren.")
+        for span in spans:                     # Bezug 12 pt → Bezug Grundgröße
+            span.size_pt = span.size_pt * base_pt / REF_PT
+        scaled.size_pt = base_pt
+    sizes = [scaled.size_pt, *(span.size_pt for span in spans)]
+    low, high = MIN_PT / min(sizes), MAX_PT / max(sizes)
+    if low <= high:
+        factor = min(max(factor, low), high)
+
+    def resize(size: float) -> float:
+        return min(max(round(size * factor, 1), MIN_PT), MAX_PT)
+
+    scaled.size_pt = resize(scaled.size_pt)
+    for span in spans:
+        span.size_pt = resize(span.size_pt)
+    return scaled
+
+
+def objects_outside(doc: Document, model: str = "QL-600") -> list[int]:
+    """Indizes der Objekte, die über das Etikett ragen (leere Objekte zählen nicht)."""
+    width, height = label_size(doc, model)
+    outside = []
+    for i, obj in enumerate(doc.objects):
+        if obj.is_empty():
+            continue
+        r = render_object(obj, doc, model)
+        if r.x < 0 or r.y < 0 or r.x + r.w > width or r.y + r.h > height:
+            outside.append(i)
+    return outside
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index 52da917..d003f91 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -109,6 +109,18 @@ def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
     return img.rotate(-90, expand=True) if sheet.horizontal else img
 
 
+def label_size(doc: Document, model: str = "QL-600") -> tuple[int, int]:
+    """Etikettgröße (Breite, Höhe) in Druckpunkten in Leserichtung – wie ``render_document``."""
+    sheet = _sheet(doc, model)
+    return _label_size(sheet, [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]])
+
+
+def label_margins(doc: Document, model: str = "QL-600") -> tuple[int, int]:
+    """Ränder (links/rechts, oben/unten) in Druckpunkten in Leserichtung."""
+    sheet = _sheet(doc, model)
+    return (sheet.margin, MARGIN) if sheet.horizontal else (MARGIN, sheet.margin)
+
+
 # --- Etikett und Objekte ------------------------------------------------------------
 @dataclass
 class _Sheet:
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `406 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/layout.py src/labelwerk/render.py tests/test_layout.py
git commit -m "Kern: Platzier-Logik – Einrasten, Ausrichten, Größe angleichen, Skalieren

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Kern – Tastenkürzel-Verzeichnis, Einstellung `shortcuts`

**Files:**
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/settings.py`
- Create: `src/labelwerk/shortcuts.py`
- Modify: `tests/gui/test_gui_settings.py`
- Modify: `tests/test_settings.py`
- Create: `tests/test_shortcuts.py`

**Interfaces / Produces:** `shortcuts.Action(id, name, default, scope)`, `SCOPES = ('global', 'canvas', 'text')`, `ACTIONS` (alle Aktionen der App), `action(id)`, `is_well_formed`, `normalize`, `effective(overrides) -> dict[str, str]`, `conflicts(mapping) -> list[tuple[str, list[str]]]`, `validate(overrides) -> (dict, list[str])`; `Settings.shortcuts: dict[str, str]` (nur Abweichungen), `SettingsDialog.values()` behält sie.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index b30e982..a417f95 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -140,3 +140,11 @@ def test_saving_dialog_applies_theme_and_icons(qtbot, qapp, monkeypatch):
         assert win.panel("text").dark_checked_icons is False
     finally:
         qapp.setStyleSheet("")
+
+
+def test_dialog_keeps_shortcuts_when_saving(qtbot, tmp_path):
+    path = tmp_path / "settings.json"
+    dialog = SettingsDialog(Settings(shortcuts={"file.print": "Ctrl+Shift+P"}), path=path)
+    qtbot.addWidget(dialog)
+    dialog.accept()
+    assert load_settings(path).shortcuts == {"file.print": "Ctrl+Shift+P"}
diff --git a/tests/test_settings.py b/tests/test_settings.py
index a329c25..39c025c 100644
--- a/tests/test_settings.py
+++ b/tests/test_settings.py
@@ -129,3 +129,42 @@ def test_invalid_theme_falls_back_with_warning(tmp_path):
     path.write_text(json.dumps({"theme": "neon"}))
     s = load_settings(path)
     assert s.theme == "rawblock" and any("theme" in w for w in s.warnings)
+
+
+# --- Tastenkürzel -------------------------------------------------------------------
+def test_shortcuts_default_empty(tmp_path):
+    assert load_settings(tmp_path / "fehlt.json").shortcuts == {}
+    assert Settings().shortcuts == {}
+
+
+def test_shortcuts_roundtrip(tmp_path):
+    path = tmp_path / "settings.json"
+    save_settings(Settings(shortcuts={"file.print": "Ctrl+Shift+P", "edit.delete": ""}), path)
+    assert json.loads(path.read_text())["shortcuts"] == {"file.print": "Ctrl+Shift+P",
+                                                          "edit.delete": ""}
+    s = load_settings(path)
+    assert s.shortcuts == {"file.print": "Ctrl+Shift+P", "edit.delete": ""}
+    assert s.warnings == []
+
+
+def test_invalid_shortcuts_dropped_with_warning(tmp_path):
+    path = tmp_path / "settings.json"
+    path.write_text(json.dumps({"shortcuts": {"file.print": "Strg+P", "gibt.es_nicht": "Ctrl+Q",
+                                              "edit.copy": "Ctrl+Shift+C"}}))
+    s = load_settings(path)
+    assert s.shortcuts == {"edit.copy": "Ctrl+Shift+C"}
+    assert len(s.warnings) == 2
+
+
+def test_shortcuts_not_a_dict_gives_defaults_and_warning(tmp_path):
+    path = tmp_path / "settings.json"
+    path.write_text(json.dumps({"shortcuts": ["Ctrl+P"], "start_zoom": 150}))
+    s = load_settings(path)
+    assert s.shortcuts == {} and s.start_zoom == 150
+    assert len(s.warnings) == 1 and "shortcuts" in s.warnings[0]
+
+
+def test_settings_default_shortcuts_not_shared():
+    a, b = Settings(), Settings()
+    a.shortcuts["file.print"] = "F2"
+    assert b.shortcuts == {}
diff --git a/tests/test_shortcuts.py b/tests/test_shortcuts.py
new file mode 100644
index 0000000..299483b
--- /dev/null
+++ b/tests/test_shortcuts.py
@@ -0,0 +1,178 @@
+"""Tastenkürzel-Verzeichnis ohne Qt (Etappe 3d-1)."""
+import re
+
+import pytest
+
+from labelwerk import shortcuts
+from labelwerk.shortcuts import ACTIONS, SCOPES, Action
+
+
+def _ids():
+    return {a.id for a in ACTIONS}
+
+
+# --- Verzeichnis ------------------------------------------------------------------
+def test_actions_have_unique_dotted_ids_and_valid_scopes():
+    ids = [a.id for a in ACTIONS]
+    assert len(ids) == len(set(ids))
+    assert all(re.fullmatch(r"[a-z]+(\.[a-z0-9_]+)+", i) for i in ids)
+    assert all(a.scope in SCOPES for a in ACTIONS)
+    assert all(a.name.strip() for a in ACTIONS)
+    assert SCOPES == ("global", "canvas", "text")
+
+
+def test_actions_cover_all_app_shortcuts():
+    expected = {
+        "file.print", "app.settings", "view.zoom_in", "view.zoom_out", "view.zoom_reset",
+        "text.bold", "text.italic", "text.underline", "tool.select", "tool.text",
+        "edit.cut", "edit.copy", "edit.paste", "edit.duplicate", "edit.delete",
+        "edit.select_all", "edit.undo", "edit.redo",
+        "object.nudge_left", "object.nudge_right", "object.nudge_up", "object.nudge_down",
+        "object.nudge_left_coarse", "object.nudge_right_coarse",
+        "object.nudge_up_coarse", "object.nudge_down_coarse",
+        "object.rotate_left", "object.rotate_right",
+        "object.bring_forward", "object.send_backward",
+        "align.left", "align.hcenter", "align.right", "align.top", "align.vcenter",
+        "align.bottom", "align.paper_left", "align.paper_hcenter", "align.paper_right",
+        "align.paper_top", "align.paper_vcenter", "align.paper_bottom",
+    }
+    assert expected <= _ids()
+
+
+@pytest.mark.parametrize("action_id, default", [
+    ("text.bold", "Ctrl+B"), ("text.italic", "Ctrl+I"), ("text.underline", "Ctrl+U"),
+    ("edit.copy", "Ctrl+C"), ("edit.delete", "Del"), ("edit.redo", "Ctrl+Shift+Z"),
+    ("object.nudge_left", "Left"), ("object.nudge_up_coarse", "Shift+Up"),
+    ("align.paper_left", ""),
+])
+def test_known_defaults(action_id, default):
+    assert shortcuts.action(action_id).default == default
+
+
+def test_action_lookup_unknown_raises():
+    with pytest.raises(KeyError):
+        shortcuts.action("gibt.es_nicht")
+
+
+def test_all_defaults_are_well_formed_and_conflict_free():
+    defaults = shortcuts.effective({})
+    assert shortcuts.validate(defaults) == (defaults, [])
+    assert shortcuts.conflicts(defaults) == []
+
+
+# --- Wirksame Kürzel --------------------------------------------------------------
+def test_effective_without_overrides_is_defaults():
+    assert shortcuts.effective({}) == {a.id: a.default for a in ACTIONS}
+
+
+def test_effective_applies_overrides_and_empty_removes():
+    mapping = shortcuts.effective({"file.print": "Ctrl+Shift+P", "edit.delete": ""})
+    assert mapping["file.print"] == "Ctrl+Shift+P"
+    assert mapping["edit.delete"] == ""
+    assert mapping["edit.copy"] == "Ctrl+C"
+
+
+def test_effective_ignores_unknown_ids():
+    assert "gibt.es_nicht" not in shortcuts.effective({"gibt.es_nicht": "Ctrl+Q"})
+
+
+# --- Normalisieren ----------------------------------------------------------------
+@pytest.mark.parametrize("a, b", [
+    ("Ctrl+B", "ctrl+b"),
+    ("Ctrl+Shift+Z", "Shift+Ctrl+Z"),
+    ("Del", "Delete"),
+    ("Ctrl++", "ctrl++"),
+    ("Esc", "Escape"),
+    ("PgUp", "PageUp"),
+])
+def test_normalize_is_case_and_order_insensitive(a, b):
+    assert shortcuts.normalize(a) == shortcuts.normalize(b)
+
+
+def test_normalize_distinguishes_modifiers():
+    assert shortcuts.normalize("Ctrl+Z") != shortcuts.normalize("Ctrl+Shift+Z")
+    assert shortcuts.normalize("Left") != shortcuts.normalize("Shift+Left")
+
+
+@pytest.mark.parametrize("seq", ["Ctrl+B", "Del", "Shift+Left", "Ctrl++", "Ctrl+-", "Ctrl+,",
+                                 "Meta+Alt+F1", "+", "Ctrl+Shift+PgDown"])
+def test_well_formed(seq):
+    assert shortcuts.is_well_formed(seq)
+
+
+@pytest.mark.parametrize("seq", ["Ctrl+", "+B", "Ctrl++B", "Strg+B", "Ctrl+Ctrl+B", "Ctrl+Shift",
+                                 "Ctrl+B+C", " ", "Ctrl+ +B"])
+def test_malformed(seq):
+    assert not shortcuts.is_well_formed(seq)
+
+
+def test_empty_means_no_shortcut_and_is_allowed():
+    assert shortcuts.is_well_formed("")
+    assert shortcuts.normalize("") == ""
+
+
+# --- Konflikte --------------------------------------------------------------------
+def test_conflict_in_same_scope():
+    mapping = shortcuts.effective({"edit.duplicate": "Ctrl+C"})
+    assert shortcuts.conflicts(mapping) == [("Ctrl+C", ["edit.copy", "edit.duplicate"])]
+
+
+def test_conflict_detected_case_insensitive():
+    mapping = shortcuts.effective({"edit.duplicate": "ctrl+c"})
+    assert shortcuts.conflicts(mapping) == [("Ctrl+C", ["edit.copy", "edit.duplicate"])]
+
+
+def test_no_conflict_between_canvas_and_text():
+    # Strg+B auf der Arbeitsfläche stört Fett im Textfeld nicht – nie beide gleichzeitig aktiv
+    mapping = shortcuts.effective({"edit.duplicate": "Ctrl+B"})
+    assert shortcuts.conflicts(mapping) == []
+
+
+def test_global_conflicts_with_every_scope():
+    mapping = shortcuts.effective({"file.print": "Ctrl+B"})
+    assert shortcuts.conflicts(mapping) == [("Ctrl+B", ["file.print", "text.bold"])]
+    mapping = shortcuts.effective({"file.print": "Del"})
+    assert shortcuts.conflicts(mapping) == [("Del", ["edit.delete", "file.print"])]
+
+
+def test_empty_shortcuts_never_conflict():
+    mapping = shortcuts.effective({"edit.copy": "", "edit.cut": "", "file.print": ""})
+    assert shortcuts.conflicts(mapping) == []
+
+
+def test_conflicts_ignore_unknown_ids_and_report_each_sequence_once():
+    mapping = shortcuts.effective({"edit.cut": "Ctrl+C", "edit.duplicate": "Ctrl+C"})
+    mapping["gibt.es_nicht"] = "Ctrl+C"
+    assert shortcuts.conflicts(mapping) == [("Ctrl+C", ["edit.copy", "edit.cut", "edit.duplicate"])]
+
+
+# --- Prüfen -----------------------------------------------------------------------
+def test_validate_keeps_good_entries():
+    clean, warnings = shortcuts.validate({"file.print": "Ctrl+Shift+P", "edit.delete": ""})
+    assert clean == {"file.print": "Ctrl+Shift+P", "edit.delete": ""}
+    assert warnings == []
+
+
+def test_validate_drops_bad_entries_with_german_warnings():
+    clean, warnings = shortcuts.validate({
+        "gibt.es_nicht": "Ctrl+Q",
+        "edit.copy": 5,
+        "edit.cut": "Strg+X",
+        "edit.paste": "Ctrl+",
+        "file.print": "Ctrl+Shift+P",
+    })
+    assert clean == {"file.print": "Ctrl+Shift+P"}
+    assert len(warnings) == 4
+    assert "unbekannte Aktion" in warnings[0] and "gibt.es_nicht" in warnings[0]
+    assert all("ungültig" in w for w in warnings[1:])
+    assert all("Standard" in w for w in warnings[1:])
+
+
+def test_validate_rejects_non_dict():
+    clean, warnings = shortcuts.validate(["Ctrl+B"])
+    assert clean == {} and len(warnings) == 1
+
+
+def test_action_is_immutable():
+    with pytest.raises(AttributeError):
+        Action("a.b", "A", "", "global").default = "X"
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 871de4d..96f25ed 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -25,6 +25,7 @@ class SettingsDialog(QDialog):
         self.setWindowTitle("Einstellungen")
         self.path = path
         self.saved: Settings | None = None
+        self._shortcuts = dict(settings.shortcuts)     # hier (noch) nicht bearbeitet – bleibt erhalten
         layout = QVBoxLayout(self)
 
         form = self._section(layout, "Neues Etikett")
@@ -119,6 +120,7 @@ class SettingsDialog(QDialog):
             check_media_on_start=self.check_media.isChecked(),
             start_zoom=self.zoom.value(),
             theme=self.theme.currentData(),
+            shortcuts=dict(self._shortcuts),
         )
 
     def accept(self) -> None:
diff --git a/src/labelwerk/settings.py b/src/labelwerk/settings.py
index 8bdff06..ae73751 100644
--- a/src/labelwerk/settings.py
+++ b/src/labelwerk/settings.py
@@ -10,6 +10,7 @@ import os
 from dataclasses import dataclass, field
 from pathlib import Path
 
+from . import shortcuts as _shortcuts
 from .document import MAX_MARGIN_MM, MAX_PT, MIN_PT, ORIENTATIONS, Document, TextObject
 from .fonts import DEFAULT_FAMILY
 from .labels import labels_for_model
@@ -27,6 +28,7 @@ class Settings:
     check_media_on_start: bool = True
     start_zoom: int = 200
     theme: str = "rawblock"                # "rawblock" oder "classic" (Qt-Systemstil)
+    shortcuts: dict[str, str] = field(default_factory=dict)   # nur geänderte Kürzel, "" = keins
     warnings: list[str] = field(default_factory=list, compare=False, repr=False)
 
 
@@ -49,7 +51,7 @@ def _rules(model: str) -> dict:
     }
 
 
-_KEYS = tuple(_rules("QL-600"))
+_KEYS = (*_rules("QL-600"), "shortcuts")
 
 
 def settings_path() -> Path:
@@ -81,6 +83,9 @@ def load_settings(path: str | Path | None = None, model: str = "QL-600") -> Sett
         else:
             settings.warnings.append(f"Einstellung {key!r} ungültig ({value!r}) – "
                                      f"Standardwert {getattr(settings, key)!r} aktiv.")
+    if "shortcuts" in raw:                 # eigene Prüfung je Kürzel: gültige bleiben erhalten
+        settings.shortcuts, warnings = _shortcuts.validate(raw["shortcuts"])
+        settings.warnings.extend(warnings)
     return settings
 
 
diff --git a/src/labelwerk/shortcuts.py b/src/labelwerk/shortcuts.py
new file mode 100644
index 0000000..dcc4902
--- /dev/null
+++ b/src/labelwerk/shortcuts.py
@@ -0,0 +1,173 @@
+"""Tastenkürzel-Verzeichnis ohne Qt: alle Aktionen mit Standardkürzel und Bereich.
+
+Kürzel sind Texte im Qt-Format („Ctrl+Shift+Z“, „Del“, „Shift+Left“); „“ = kein Kürzel.
+Der Kern prüft nur Form und Doppelbelegung, die GUI wandelt mit ``QKeySequence`` um.
+Bereiche: ``global`` (überall), ``canvas`` (Arbeitsfläche hat den Fokus),
+``text`` (Textfeld hat den Fokus). Arbeitsfläche und Textfeld sind nie gleichzeitig aktiv,
+ein globales Kürzel kollidiert dagegen mit jedem Bereich.
+"""
+from __future__ import annotations
+
+from dataclasses import dataclass
+
+SCOPES = ("global", "canvas", "text")
+
+
+@dataclass(frozen=True)
+class Action:
+    id: str          # z. B. "edit.copy"
+    name: str        # Anzeigename
+    default: str     # Standardkürzel, "" = keins
+    scope: str       # global | canvas | text
+
+
+ACTIONS: tuple[Action, ...] = (
+    Action("file.print", "Drucken", "Ctrl+P", "global"),
+    Action("app.settings", "Einstellungen", "Ctrl+,", "global"),
+    Action("view.zoom_in", "Vergrößern (Zoom)", "Ctrl++", "global"),
+    Action("view.zoom_out", "Verkleinern (Zoom)", "Ctrl+-", "global"),
+    Action("view.zoom_reset", "Echte Größe (100 %)", "Ctrl+0", "global"),
+    Action("edit.undo", "Rückgängig", "Ctrl+Z", "global"),
+    Action("edit.redo", "Wiederherstellen", "Ctrl+Shift+Z", "global"),
+    Action("tool.select", "Werkzeug Auswahl", "Esc", "canvas"),
+    Action("tool.text", "Werkzeug Text anlegen", "T", "canvas"),
+    Action("edit.cut", "Ausschneiden", "Ctrl+X", "canvas"),
+    Action("edit.copy", "Kopieren", "Ctrl+C", "canvas"),
+    Action("edit.paste", "Einfügen", "Ctrl+V", "canvas"),
+    Action("edit.duplicate", "Duplizieren", "Ctrl+D", "canvas"),
+    Action("edit.delete", "Löschen", "Del", "canvas"),
+    Action("edit.select_all", "Alles auswählen", "Ctrl+A", "canvas"),
+    Action("object.nudge_left", "Nach links (0,1 mm)", "Left", "canvas"),
+    Action("object.nudge_right", "Nach rechts (0,1 mm)", "Right", "canvas"),
+    Action("object.nudge_up", "Nach oben (0,1 mm)", "Up", "canvas"),
+    Action("object.nudge_down", "Nach unten (0,1 mm)", "Down", "canvas"),
+    Action("object.nudge_left_coarse", "Nach links (1 mm)", "Shift+Left", "canvas"),
+    Action("object.nudge_right_coarse", "Nach rechts (1 mm)", "Shift+Right", "canvas"),
+    Action("object.nudge_up_coarse", "Nach oben (1 mm)", "Shift+Up", "canvas"),
+    Action("object.nudge_down_coarse", "Nach unten (1 mm)", "Shift+Down", "canvas"),
+    Action("object.rotate_left", "90° nach links drehen", "Ctrl+L", "canvas"),
+    Action("object.rotate_right", "90° nach rechts drehen", "Ctrl+R", "canvas"),
+    Action("object.bring_forward", "Nach vorne", "Ctrl+PgUp", "canvas"),
+    Action("object.send_backward", "Nach hinten", "Ctrl+PgDown", "canvas"),
+    Action("align.left", "Aneinander links ausrichten", "", "canvas"),
+    Action("align.hcenter", "Aneinander waagrecht mittig ausrichten", "", "canvas"),
+    Action("align.right", "Aneinander rechts ausrichten", "", "canvas"),
+    Action("align.top", "Aneinander oben ausrichten", "", "canvas"),
+    Action("align.vcenter", "Aneinander senkrecht mittig ausrichten", "", "canvas"),
+    Action("align.bottom", "Aneinander unten ausrichten", "", "canvas"),
+    Action("align.paper_left", "Am Papier links ausrichten", "", "canvas"),
+    Action("align.paper_hcenter", "Am Papier waagrecht mittig ausrichten", "", "canvas"),
+    Action("align.paper_right", "Am Papier rechts ausrichten", "", "canvas"),
+    Action("align.paper_top", "Am Papier oben ausrichten", "", "canvas"),
+    Action("align.paper_vcenter", "Am Papier senkrecht mittig ausrichten", "", "canvas"),
+    Action("align.paper_bottom", "Am Papier unten ausrichten", "", "canvas"),
+    Action("size.maximize", "Auf Papier maximieren", "", "canvas"),
+    Action("size.same", "Gleiche Größe", "", "canvas"),
+    Action("size.width", "Gleiche Breite", "", "canvas"),
+    Action("size.height", "Gleiche Höhe", "", "canvas"),
+    Action("text.bold", "Fett", "Ctrl+B", "text"),
+    Action("text.italic", "Kursiv", "Ctrl+I", "text"),
+    Action("text.underline", "Unterstrichen", "Ctrl+U", "text"),
+)
+
+_BY_ID = {a.id: a for a in ACTIONS}
+_MODIFIERS = ("Ctrl", "Alt", "Shift", "Meta")          # Reihenfolge wie Qt
+_KEY_ALIASES = {"del": "Del", "delete": "Del", "esc": "Esc", "escape": "Esc",
+                "ins": "Ins", "insert": "Ins", "pgup": "PgUp", "pageup": "PgUp",
+                "pgdown": "PgDown", "pagedown": "PgDown"}
+
+
+def action(action_id: str) -> Action:
+    """Aktion zur ID (``KeyError`` bei unbekannter ID)."""
+    return _BY_ID[action_id]
+
+
+# --- Form ---------------------------------------------------------------------------
+def _split(seq: str) -> tuple[list[str], str]:
+    """Kürzel in Umschalttasten und Taste zerlegen („Ctrl++“ = Strg und Plus)."""
+    if seq.endswith("++") or seq == "+":
+        return (seq[:-2].split("+") if len(seq) > 2 else []), "+"
+    *mods, key = seq.split("+")
+    return mods, key
+
+
+def _parse(seq: str) -> tuple[frozenset[str], str] | None:
+    """Umschalttasten (normiert) und Taste, oder None bei ungültiger Form."""
+    mods, key = _split(seq)
+    known = {m.casefold(): m for m in _MODIFIERS}
+    normed = [known.get(m.casefold()) for m in mods]
+    if None in normed or len(set(normed)) != len(normed):
+        return None                              # unbekannte oder doppelte Umschalttaste
+    if not key or key != key.strip() or key.casefold() in known:
+        return None                              # Taste fehlt oder ist nur eine Umschalttaste
+    return frozenset(normed), key
+
+
+def is_well_formed(seq: str) -> bool:
+    """True für ein Kürzel in Qt-Form oder „“ (kein Kürzel)."""
+    return seq == "" or _parse(seq) is not None
+
+
+def normalize(seq: str) -> str:
+    """Einheitliche Schreibweise (Groß/klein, Reihenfolge, Tastennamen) zum Vergleichen.
+
+    ``ValueError`` bei ungültiger Form."""
+    if seq == "":
+        return ""
+    parsed = _parse(seq)
+    if parsed is None:
+        raise ValueError(f"Ungültiges Tastenkürzel {seq!r}")
+    mods, key = parsed
+    key = _KEY_ALIASES.get(key.casefold(), key.upper() if len(key) == 1 else key.capitalize())
+    return "+".join([m for m in _MODIFIERS if m in mods] + [key])
+
+
+# --- Verzeichnis anwenden -------------------------------------------------------------
+def effective(overrides: dict[str, str]) -> dict[str, str]:
+    """Wirksame Kürzel aller Aktionen: Standard, überschrieben durch ``overrides``."""
+    mapping = {a.id: a.default for a in ACTIONS}
+    mapping.update({k: v for k, v in overrides.items() if k in _BY_ID})
+    return mapping
+
+
+def conflicts(mapping: dict[str, str]) -> list[tuple[str, list[str]]]:
+    """Doppelt belegte Kürzel: ``[(Kürzel, [Aktions-IDs])]``, nach Kürzel sortiert.
+
+    Kollision = gleiches Kürzel im selben Bereich oder ein globales gegen jeden Bereich.
+    Leere, ungültige Kürzel und unbekannte IDs werden übergangen.
+    """
+    groups: dict[str, list[str]] = {}
+    for action_id, seq in mapping.items():
+        if action_id in _BY_ID and seq and is_well_formed(seq):
+            groups.setdefault(normalize(seq), []).append(action_id)
+    result = []
+    for seq, ids in sorted(groups.items()):
+        clashing = {a for a in ids for b in ids
+                    if a != b and _clash(_BY_ID[a].scope, _BY_ID[b].scope)}
+        if clashing:
+            result.append((seq, sorted(clashing)))
+    return result
+
+
+def _clash(scope_a: str, scope_b: str) -> bool:
+    return scope_a == scope_b or "global" in (scope_a, scope_b)
+
+
+def validate(overrides) -> tuple[dict[str, str], list[str]]:
+    """Geänderte Kürzel aus den Einstellungen prüfen: ``(gültige, Warnungen)``.
+
+    Unbekannte Aktionen und ungültige Kürzel werden mit Warnung verworfen (Standard gilt);
+    „“ ist erlaubt und heißt „kein Kürzel“."""
+    if not isinstance(overrides, dict):
+        return {}, [f"Einstellung 'shortcuts' ungültig ({overrides!r}) – Standardkürzel aktiv."]
+    clean: dict[str, str] = {}
+    warnings: list[str] = []
+    for action_id, seq in overrides.items():
+        if action_id not in _BY_ID:
+            warnings.append(f"Tastenkürzel für unbekannte Aktion {action_id!r} ignoriert.")
+        elif not isinstance(seq, str) or not is_well_formed(seq):
+            warnings.append(f"Tastenkürzel für {action_id!r} ungültig ({seq!r}) – "
+                            f"Standard {_BY_ID[action_id].default!r} aktiv.")
+        else:
+            clean[action_id] = seq
+    return clean, warnings
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `464 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/settings_dialog.py src/labelwerk/settings.py src/labelwerk/shortcuts.py tests/gui/test_gui_settings.py tests/test_settings.py tests/test_shortcuts.py
git commit -m "Kern: Tastenkürzel-Verzeichnis und Einstellung shortcuts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: GUI – Objekte auf der Arbeitsfläche: Auswahl, Ziehen, Einrasten, Anfasser, Tastatur

**Files:**
- Create: `src/labelwerk/gui/actions.py`
- Modify: `src/labelwerk/gui/canvas.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/layout.py`
- Modify: `src/labelwerk/render.py`
- Create: `tests/gui/test_gui_actions.py`
- Modify: `tests/gui/test_gui_canvas.py`
- Modify: `tests/gui/test_gui_papier.py`
- Create: `tests/gui/test_gui_placement.py`
- Modify: `tests/test_layout.py`
- Modify: `tests/test_placement_render.py`

**Interfaces / Produces:** `canvas.ObjectItem`, `Canvas.set_document(label, size, rendered, orientation, area=None, keep_ratio=None)`, Signale `selection_changed(list)`, `objects_moved(list, list)`, `object_resized(int, Rect, str)`; `selection`, `set_selection`, `select_all`, `nudge`, `guides`, `is_dragging`; `render.compose(rendered, size, orientation)`; `layout.exact_rect`, `move`, `resize`, `fix_size`; `gui/actions.py`: `build_actions(parent, mapping) -> dict[str, QAction]`, `apply_shortcuts(actions, mapping)`; MainWindow rendert je Objekt mit Cache, Hinweis „Objekt ragt über das Etikett hinaus“.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_actions.py b/tests/gui/test_gui_actions.py
new file mode 100644
index 0000000..a629f0b
--- /dev/null
+++ b/tests/gui/test_gui_actions.py
@@ -0,0 +1,31 @@
+"""QActions aus dem Kürzel-Verzeichnis (Etappe 3d-1)."""
+from PySide6.QtCore import Qt
+from PySide6.QtGui import QKeySequence
+from PySide6.QtWidgets import QWidget
+
+from labelwerk import shortcuts
+from labelwerk.gui.actions import apply_shortcuts, build_actions
+
+
+def test_build_actions_creates_one_action_per_entry(qtbot):
+    parent = QWidget()
+    qtbot.addWidget(parent)
+    actions = build_actions(parent, shortcuts.effective({}))
+    assert list(actions) == [a.id for a in shortcuts.ACTIONS]
+    copy = actions["edit.copy"]
+    assert copy.text() == "Kopieren" and copy.parent() is parent
+    assert copy.shortcut() == QKeySequence("Ctrl+C")
+    assert copy.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
+    assert actions["file.print"].shortcutContext() == Qt.ShortcutContext.WindowShortcut
+    assert actions["align.left"].shortcut().isEmpty()
+
+
+def test_apply_shortcuts_changes_keys_and_tooltips(qtbot):
+    parent = QWidget()
+    qtbot.addWidget(parent)
+    actions = build_actions(parent, shortcuts.effective({}))
+    apply_shortcuts(actions, shortcuts.effective({"edit.copy": "Ctrl+Shift+C", "edit.cut": ""}))
+    assert actions["edit.copy"].shortcut() == QKeySequence("Ctrl+Shift+C")
+    assert "Ctrl+Shift+C" in actions["edit.copy"].toolTip()
+    assert actions["edit.cut"].shortcut().isEmpty()
+    assert actions["edit.cut"].toolTip() == "Ausschneiden"
diff --git a/tests/gui/test_gui_canvas.py b/tests/gui/test_gui_canvas.py
index 27835bd..a355f7a 100644
--- a/tests/gui/test_gui_canvas.py
+++ b/tests/gui/test_gui_canvas.py
@@ -3,7 +3,7 @@ import pytest
 from labelwerk.document import Document, TextObject
 from labelwerk.gui.canvas import Canvas
 from labelwerk.labels import get_label
-from labelwerk.render import render_document
+from labelwerk.render import label_size, render_object
 
 
 @pytest.fixture
@@ -13,9 +13,14 @@ def canvas(qtbot):
     return view
 
 
+def show(canvas, doc):
+    """Dokument so anzeigen, wie das Hauptfenster es tut (Objekte einzeln gerendert)."""
+    canvas.set_document(get_label(doc.label_id), label_size(doc),
+                        [render_object(obj, doc) for obj in doc.objects], doc.orientation)
+
+
 def _show(canvas, label_id):
-    doc = Document(label_id, objects=[TextObject("Test")])
-    canvas.set_document(get_label(label_id), render_document(doc))
+    show(canvas, Document(label_id, objects=[TextObject("Test")]))
 
 
 def test_die_cut_outline_has_physical_size(canvas):
@@ -76,7 +81,7 @@ def test_length_handle_does_not_jump_when_grabbed(qtbot, canvas):
     from PySide6.QtWidgets import QApplication
     from labelwerk.gui.canvas import MM
 
-    canvas.set_document(get_label("62"), render_document(Document("62", objects=[TextObject("Test")])))
+    show(canvas, Document("62", objects=[TextObject("Test")]))
     qtbot.addWidget(canvas)
     canvas.show()
     emitted = []
diff --git a/tests/gui/test_gui_papier.py b/tests/gui/test_gui_papier.py
index 3b35283..30e4888 100644
--- a/tests/gui/test_gui_papier.py
+++ b/tests/gui/test_gui_papier.py
@@ -7,7 +7,7 @@ from labelwerk.document import Document, TextObject
 from labelwerk.gui.canvas import MM, Canvas
 from labelwerk.gui.main_window import MainWindow
 from labelwerk.labels import get_label
-from labelwerk.render import render_document
+from labelwerk.render import label_size, render_document, render_object
 from labelwerk.settings import Settings
 
 
@@ -55,7 +55,8 @@ def test_horizontal_caption_reads_length_first(qtbot):
     view = Canvas()
     qtbot.addWidget(view)
     doc = Document("62", length_mm=50, orientation="horizontal", objects=[TextObject("A")])
-    view.set_document(get_label("62"), render_document(doc), "horizontal")
+    view.set_document(get_label("62"), label_size(doc), [render_object(o, doc) for o in doc.objects],
+                      "horizontal")
     assert view._caption == "50,0 × 62 mm"
 
 
diff --git a/tests/gui/test_gui_placement.py b/tests/gui/test_gui_placement.py
new file mode 100644
index 0000000..c8814a7
--- /dev/null
+++ b/tests/gui/test_gui_placement.py
@@ -0,0 +1,339 @@
+"""Arbeitsfläche mit Objekten: Auswahl, Ziehen, Einrasten, Anfasser, Tastatur (Etappe 3d-1)."""
+import pytest
+from PySide6.QtCore import QPointF, Qt
+from PySide6.QtGui import QImage, QKeySequence, QMouseEvent
+from PySide6.QtTest import QTest
+from PySide6.QtWidgets import QApplication
+
+from labelwerk import layout
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.canvas import ObjectItem, to_qimage
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.labels import DPI
+from labelwerk.render import render_document, render_object
+from labelwerk.settings import Settings
+
+NO_MOD = Qt.KeyboardModifier.NoModifier
+ALT = Qt.KeyboardModifier.AltModifier
+CTRL = Qt.KeyboardModifier.ControlModifier
+LEFT = Qt.MouseButton.LeftButton
+DOT_MM = 25.4 / DPI
+
+
+def _doc(orientation="vertical", length_mm=40):
+    return Document("62", length_mm=length_mm, orientation=orientation, objects=[
+        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
+        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=20)])
+
+
+def _window(qtbot, doc, settings=None):
+    win = MainWindow(doc=doc, settings=settings)
+    qtbot.addWidget(win)
+    win.show()
+    return win
+
+
+@pytest.fixture
+def window(qtbot):
+    return _window(qtbot, _doc())
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
+def _press_move(canvas, start, end, modifiers=NO_MOD):
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT, modifiers)
+    middle = (start + end) / 2
+    _send(canvas, QMouseEvent.Type.MouseMove, middle, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT, modifiers)
+
+
+def _drag(canvas, start, end, modifiers=NO_MOD):
+    _press_move(canvas, start, end, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, modifiers)
+
+
+def _center(canvas, index):
+    return canvas.view_rect(index).center()
+
+
+# --- Elemente ---------------------------------------------------------------------
+def test_canvas_shows_one_item_per_object(window):
+    items = window.canvas.objects
+    assert len(items) == 2 and all(isinstance(item, ObjectItem) for item in items)
+    assert [item.index for item in items] == [0, 1]
+
+
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_canvas_shows_the_object_images_that_are_printed(qtbot, orientation):
+    doc = _doc(orientation)
+    doc.objects.append(TextObject("Mitte"))
+    win = _window(qtbot, doc)
+    for obj, item in zip(doc.objects, win.canvas.objects):
+        rendered = render_object(obj, doc)
+        assert item.rendered.image.tobytes() == rendered.image.tobytes()
+        assert (item.pos().x(), item.pos().y()) == (rendered.x, rendered.y)
+        shown = item.pixmap().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
+        assert shown == to_qimage(rendered.image)
+    assert win.image.tobytes() == render_document(doc).tobytes()
+
+
+def test_horizontal_view_shows_objects_in_reading_direction(qtbot):
+    win = _window(qtbot, _doc("horizontal", length_mm=60))
+    first, second = win.canvas.view_rect(0), win.canvas.view_rect(1)
+    assert second.top() > first.bottom()                   # „Zwei“ steht unter „Eins“
+    assert first.width() > first.height()                  # Text liegt waagrecht
+
+
+def test_only_changed_objects_are_rendered_again(window, monkeypatch):
+    calls = []
+    real = render_object
+
+    def counting(obj, doc, model="QL-600"):
+        calls.append(obj.text)
+        return real(obj, doc, model)
+
+    monkeypatch.setattr("labelwerk.gui.main_window.render_object", counting)
+    window.render_now()
+    assert calls == []
+    window.doc.objects[1] = layout.place(window.doc.objects[1], layout.Rect(10, 25, 0, 0))
+    window.render_now()
+    assert calls == ["Zwei"]
+
+
+# --- Auswahl ----------------------------------------------------------------------
+def test_click_selects_ctrl_click_toggles_empty_click_clears(window):
+    canvas = window.canvas
+    seen = []
+    canvas.selection_changed.connect(seen.append)
+    _click(canvas, _center(canvas, 1))
+    assert canvas.selection() == [1]
+    _click(canvas, _center(canvas, 0), CTRL)
+    assert canvas.selection() == [1, 0]
+    _click(canvas, _center(canvas, 1), CTRL)
+    assert canvas.selection() == [0]
+    empty = canvas.view_rect(1).bottomRight() + QPointF(40, 40)
+    _click(canvas, empty)
+    assert canvas.selection() == []
+    assert seen == [[1], [1, 0], [0], []]
+
+
+def test_click_on_selected_object_of_many_selects_only_it(window):
+    canvas = window.canvas
+    canvas.select_all()
+    assert canvas.selection() == [0, 1]
+    _click(canvas, _center(canvas, 1))
+    assert canvas.selection() == [1]
+
+
+def test_selection_survives_rendering(window):
+    window.canvas.set_selection([1])
+    window.render_now()
+    assert window.canvas.selection() == [1]
+
+
+# --- Verschieben ------------------------------------------------------------------
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_drag_moves_object_and_updates_model_on_release(qtbot, orientation):
+    win = _window(qtbot, _doc(orientation, length_mm=60))
+    canvas = win.canvas
+    ppm = canvas.px_per_mm()
+    start = _center(canvas, 0)
+    end = start + QPointF(80, 40)                          # rechts und unten in Leserichtung
+    _press_move(canvas, start, end, ALT)
+    assert canvas.view_rect(0).center().x() == pytest.approx(end.x(), abs=1)
+    assert win.doc.objects[0].x_mm == 4                   # Modell erst beim Loslassen
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, ALT)
+    obj = win.doc.objects[0]
+    assert obj.x_mm == pytest.approx(4 + 80 / ppm, abs=0.01)
+    assert obj.y_mm == pytest.approx(4 + 40 / ppm, abs=0.01)
+    assert win.doc.objects[1].x_mm == 4
+    assert canvas.view_rect(0).center().x() == pytest.approx(end.x(), abs=1)
+
+
+def test_drag_moves_all_selected_objects(window):
+    canvas = window.canvas
+    canvas.select_all()
+    start = _center(canvas, 0)
+    _drag(canvas, start, start + QPointF(50, 0), ALT)
+    moved = 50 / canvas.px_per_mm()
+    assert [o.x_mm for o in window.doc.objects] == pytest.approx([4 + moved] * 2, abs=0.01)
+
+
+def test_click_without_moving_leaves_model_untouched(window):
+    before = [o.x_mm for o in window.doc.objects]
+    _click(window.canvas, _center(window.canvas, 0))
+    assert [o.x_mm for o in window.doc.objects] == before
+
+
+def test_first_drag_of_automatic_object_fixes_its_size(qtbot):
+    win = _window(qtbot, Document("62", objects=[TextObject("Hallo")]))
+    base_pt = win.canvas.objects[0].rendered.base_pt
+    start = _center(win.canvas, 0)
+    _drag(win.canvas, start, start + QPointF(0, 30), ALT)
+    obj = win.doc.objects[0]
+    assert obj.positioned and not obj.fit
+    assert obj.size_pt == round(base_pt, 1)
+
+
+def test_typing_keeps_position_of_moved_object(window, qtbot):
+    start = _center(window.canvas, 0)
+    _drag(window.canvas, start, start + QPointF(30, 0), ALT)
+    x = window.doc.objects[0].x_mm
+    window.panel("text").edit.setPlainText("Eins!")
+    assert window.doc.objects[0].text == "Eins!"
+    assert (window.doc.objects[0].x_mm, window.doc.objects[0].y_mm) == (x, 4)
+
+
+@pytest.mark.parametrize("modifiers", [NO_MOD, ALT])
+def test_drag_snaps_to_label_center_unless_alt(window, modifiers):
+    canvas = window.canvas
+    ppm = canvas.px_per_mm()
+    label = layout.label_rect(window.doc)
+    rect = layout.object_rect(canvas.objects[0].rendered)
+    # Mitte des Objekts landet 2 Bildschirmpixel neben der Etikettmitte (Toleranz 6 px)
+    dx = round((label.cx - rect.cx) * ppm) + 2
+    start = _center(canvas, 0)
+    _press_move(canvas, start, start + QPointF(dx, 0), modifiers)
+    guides = canvas.guides()
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, start + QPointF(dx, 0),
+          Qt.MouseButton.NoButton, modifiers)
+    printed = layout.object_rect(canvas.objects[0].rendered)
+    offset = printed.cx - label.cx
+    if modifiers == ALT:
+        assert offset == pytest.approx(2 / ppm, abs=0.6 / ppm)
+        assert guides == []
+    else:
+        assert abs(offset) <= DOT_MM                       # genauer geht der Druck nicht
+        assert ("x", pytest.approx(label.cx)) in guides
+    assert canvas.guides() == []                           # Hilfslinien nur beim Ziehen
+
+
+def test_render_waits_while_dragging(window):
+    canvas = window.canvas
+    start = _center(canvas, 0)
+    _press_move(canvas, start, start + QPointF(30, 0), ALT)
+    item = canvas.objects[0]
+    window.render_now()                                    # z. B. verzögertes Rendern
+    assert canvas.objects[0] is item and canvas.is_dragging()
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, start + QPointF(30, 0),
+          Qt.MouseButton.NoButton, ALT)
+    assert window.doc.objects[0].x_mm > 4
+
+
+# --- Anfasser ---------------------------------------------------------------------
+def test_selected_object_has_eight_handles(window):
+    window.canvas.set_selection([0])
+    handles = window.canvas.handle_points(0)
+    assert set(handles) == {"tl", "t", "tr", "r", "br", "b", "bl", "l"}
+    rect = window.canvas.view_rect(0)
+    assert handles["tl"] == rect.topLeft() and handles["br"] == rect.bottomRight()
+
+
+def test_corner_drag_scales_font(window):
+    canvas = window.canvas
+    canvas.set_selection([0])
+    rect = canvas.view_rect(0)
+    corner = canvas.handle_points(0)["br"]
+    _drag(canvas, corner, corner + QPointF(rect.width() / 2, rect.height() / 2))
+    obj = window.doc.objects[0]
+    assert obj.size_pt == pytest.approx(21, abs=0.6)
+    assert not obj.fit and (obj.x_mm, obj.y_mm) == pytest.approx((4, 4), abs=0.1)
+
+
+def test_edge_drag_turns_fixed_frame_on(window):
+    canvas = window.canvas
+    canvas.set_selection([0])
+    before = layout.object_rect(canvas.objects[0].rendered)
+    edge = canvas.handle_points(0)["r"]
+    _drag(canvas, edge, edge + QPointF(10 * canvas.px_per_mm(), 0))
+    obj = window.doc.objects[0]
+    assert obj.fit
+    assert obj.w_mm == pytest.approx(before.w + 10, abs=0.2)
+    assert obj.h_mm == pytest.approx(before.h, abs=0.01)
+    assert window.panel("text").fit.isChecked()            # Panel zeigt das Modell
+
+
+def test_handle_drag_on_fixed_frame_changes_frame(qtbot):
+    doc = _doc()
+    doc.objects[0] = TextObject("Eins", size_pt=14, fit=True, x_mm=4, y_mm=4, w_mm=20, h_mm=8)
+    win = _window(qtbot, doc)
+    canvas = win.canvas
+    canvas.set_selection([0])
+    ppm = canvas.px_per_mm()
+    corner = canvas.handle_points(0)["br"]
+    _drag(canvas, corner, corner + QPointF(10 * ppm, 2 * ppm))
+    obj = win.doc.objects[0]
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((30, 10), abs=0.2)
+    assert obj.size_pt == 14
+
+
+# --- Tastatur ---------------------------------------------------------------------
+def _focus(window, qtbot):
+    window.activateWindow()
+    window.canvas.setFocus()
+    qtbot.waitUntil(lambda: window.canvas.hasFocus(), timeout=1000)
+
+
+def test_arrow_keys_nudge_selected_object(window, qtbot):
+    window.canvas.set_selection([1])
+    _focus(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_Left)
+    assert window.doc.objects[1].x_mm == pytest.approx(3.9)
+    QTest.keyClick(window.canvas, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
+    assert window.doc.objects[1].y_mm == pytest.approx(21)
+    assert (window.doc.objects[0].x_mm, window.doc.objects[0].y_mm) == (4, 4)
+
+
+def test_arrow_keys_without_selection_do_nothing(window, qtbot):
+    _focus(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_Right)
+    assert [o.x_mm for o in window.doc.objects] == [4, 4]
+
+
+def test_delete_removes_selected_objects(window, qtbot):
+    window.canvas.set_selection([0])
+    _focus(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_Delete)
+    assert [o.text for o in window.doc.objects] == ["Zwei"]
+    assert window.canvas.selection() == []
+    assert window.panel("text").edit.toPlainText() == "Zwei"
+    assert len(window.canvas.objects) == 1
+
+
+def test_select_all_and_delete_leaves_an_empty_text(window, qtbot):
+    _focus(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_A, CTRL)
+    assert window.canvas.selection() == [0, 1]
+    QTest.keyClick(window.canvas, Qt.Key.Key_Delete)
+    assert len(window.doc.objects) == 1 and window.doc.objects[0].is_empty()
+    assert window.panel("text").edit.toPlainText() == ""
+
+
+def test_shortcuts_come_from_settings(qtbot):
+    win = _window(qtbot, _doc(), Settings(shortcuts={"object.nudge_left": "Ctrl+J"}))
+    assert win.actions["object.nudge_left"].shortcut() == QKeySequence("Ctrl+J")
+    win.canvas.set_selection([0])
+    _focus(win, qtbot)
+    QTest.keyClick(win.canvas, Qt.Key.Key_J, CTRL)
+    assert win.doc.objects[0].x_mm == pytest.approx(3.9)
+
+
+# --- Hinweise ---------------------------------------------------------------------
+def test_object_outside_label_shows_status_hint(qtbot):
+    doc = _doc()
+    doc.objects[1] = TextObject("Zwei", size_pt=14, x_mm=55, y_mm=20)
+    win = _window(qtbot, doc)
+    assert "Objekt ragt über das Etikett hinaus" in win.result.text()
+    win.canvas.set_selection([1])
+    win.canvas.nudge(-30, 0)
+    assert "ragt" not in win.result.text()
diff --git a/tests/test_layout.py b/tests/test_layout.py
index d6cc9cc..9eeadf3 100644
--- a/tests/test_layout.py
+++ b/tests/test_layout.py
@@ -358,3 +358,99 @@ def test_objects_outside_auto_length_grows_instead():
 def test_objects_outside_ignores_empty_objects():
     doc = Document("62", length_mm=40, objects=[TextObject("", size_pt=12, x_mm=200, y_mm=200)])
     assert layout.objects_outside(doc) == []
+
+
+# --- Verschieben und Anfasser (Arbeitsfläche) ---------------------------------------
+def _rendered(x_mm, y_mm, w_mm, h_mm, base_pt=12.0):
+    """Gerendertes Objekt wie von render_object: Position und Größe auf Druckpunkte gerundet."""
+    dots = [round(v * DPI / 25.4) for v in (x_mm, y_mm, w_mm, h_mm)]
+    return RenderedObject(None, *dots, base_pt)
+
+
+def test_exact_rect_uses_model_position_and_fixed_frame():
+    obj = TextObject("A", size_pt=12, fit=True, x_mm=4, y_mm=5, w_mm=20, h_mm=8, rotation=90)
+    assert layout.exact_rect(obj, _rendered(4, 5, 8, 20)) == Rect(4, 5, 8, 20)   # gedreht
+    free = TextObject("A", size_pt=12, x_mm=4, y_mm=5)
+    rendered = _rendered(4, 5, 10, 3)
+    assert layout.exact_rect(free, rendered) == Rect(4, 5, _mm(rendered.w), _mm(rendered.h))
+    centered = TextObject("A")
+    assert _t(layout.exact_rect(centered, rendered)) == _t(layout.object_rect(rendered))
+
+
+def test_fix_size_freezes_effective_size_and_turns_fit_off():
+    obj = TextObject([Paragraph([Span("a"), Span("b", size_pt=24)])], size_pt=12, fit=True)
+    fixed = layout.fix_size(obj, 18.04)
+    assert _sizes(fixed) == (18, [None, 36])               # Stück behält sein Verhältnis
+    assert not fixed.fit and obj.fit
+
+
+def test_move_shifts_model_position_by_exact_amount():
+    # Druckpunkte runden 4 mm auf 3,98 mm – die Verschiebung zählt, nicht der gerundete Wert
+    obj = TextObject("A", size_pt=12, x_mm=4, y_mm=5)
+    rendered = _rendered(4, 5, 10, 3)
+    moved = layout.move(obj, layout.object_rect(rendered).moved(-0.1, 1), rendered)
+    assert (moved.x_mm, moved.y_mm) == pytest.approx((3.9, 6))
+    assert (moved.size_pt, moved.fit, obj.x_mm) == (12, False, 4)
+
+
+@pytest.mark.parametrize("obj", [TextObject("Hallo"), TextObject("Hallo", size_pt=12, fit=True)],
+                         ids=["ohne Größe", "feste Rahmengröße"])
+def test_first_move_of_auto_object_keeps_its_image(obj):
+    doc = Document("62", objects=[obj])
+    before = render_object(obj, doc)
+    moved = layout.move(obj, layout.object_rect(before), before)
+    assert moved.positioned and not moved.auto
+    doc.objects = [moved]
+    after = render_object(moved, doc)
+    assert after.image.tobytes() == before.image.tobytes()
+    assert (after.x, after.y) == (before.x, before.y)
+
+
+def test_move_positioned_fit_object_keeps_frame():
+    obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8)
+    rendered = _rendered(1, 1, 20, 8, base_pt=30)
+    moved = layout.move(obj, layout.object_rect(rendered).moved(3, 4), rendered)
+    assert (moved.x_mm, moved.y_mm, moved.w_mm, moved.h_mm, moved.fit) == \
+        pytest.approx((4, 5, 20, 8, True))
+    assert moved.size_pt == 12
+
+
+def test_resize_fit_object_changes_frame():
+    obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8)
+    rendered = _rendered(1, 1, 20, 8, base_pt=30)
+    old = layout.object_rect(rendered)
+    for corner in (True, False):
+        new = Rect(old.x - 1, old.y, old.w + 5, old.h + 4)
+        resized = layout.resize(obj, new, rendered, corner=corner)
+        assert (resized.x_mm, resized.y_mm, resized.w_mm, resized.h_mm) == \
+            pytest.approx((0, 1, 25, 12))
+        assert resized.fit and resized.size_pt == 12
+
+
+def test_resize_corner_scales_text_without_frame():
+    obj = TextObject("A", size_pt=12, x_mm=1, y_mm=1)
+    rendered = _rendered(1, 1, 10, 5)
+    old = layout.object_rect(rendered)
+    bigger = Rect(old.x, old.y, old.w * 1.5, old.h * 1.5)
+    resized = layout.resize(obj, bigger, rendered, corner=True)
+    assert (resized.size_pt, resized.fit) == (18, False)
+    assert (resized.x_mm, resized.y_mm) == pytest.approx((1, 1))
+    assert resized.w_mm is None
+
+
+def test_resize_corner_of_auto_object_uses_effective_size():
+    rendered = _rendered(1, 1, 10, 5, base_pt=20)
+    old = layout.object_rect(rendered)
+    smaller = Rect(0, 0, old.w / 2, old.h / 2)
+    resized = layout.resize(TextObject("A"), smaller, rendered, corner=True)
+    assert (resized.size_pt, resized.x_mm, resized.y_mm) == (10, 0, 0)
+
+
+def test_resize_edge_turns_fixed_frame_on():
+    obj = TextObject("A", size_pt=12, x_mm=1, y_mm=1, rotation=90)
+    rendered = _rendered(1, 1, 5, 10)
+    old = layout.object_rect(rendered)
+    resized = layout.resize(obj, Rect(old.x, old.y, old.w, old.h + 8), rendered, corner=False)
+    assert resized.fit
+    assert (resized.x_mm, resized.y_mm, resized.w_mm, resized.h_mm) == \
+        pytest.approx((1, 1, old.h + 8, old.w), abs=0.001)             # ungedreht gespeichert
diff --git a/tests/test_placement_render.py b/tests/test_placement_render.py
index 7fe75b9..f9c7297 100644
--- a/tests/test_placement_render.py
+++ b/tests/test_placement_render.py
@@ -188,3 +188,14 @@ def test_base_pt_of_auto_object_reproduces_image():
     assert 4 < ro.base_pt < 100
     fixed = Document("62", objects=[TextObject("Hallo", size_pt=ro.base_pt)])
     assert render_document(fixed).tobytes() == render_document(doc).tobytes()
+
+
+# --- Zusammensetzen aus Objektbildern (Arbeitsfläche = Druck) -------------------------
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_compose_from_object_images_equals_render_document(orientation):
+    from labelwerk.render import compose, label_size
+    doc = Document("62", orientation=orientation, objects=[
+        TextObject("Mitte"), TextObject("oben", size_pt=14, x_mm=3, y_mm=2)])
+    rendered = [render_object(obj, doc) for obj in doc.objects]
+    image = compose(rendered, label_size(doc), orientation)
+    assert image.tobytes() == render_document(doc).tobytes()
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/actions.py b/src/labelwerk/gui/actions.py
new file mode 100644
index 0000000..12f1481
--- /dev/null
+++ b/src/labelwerk/gui/actions.py
@@ -0,0 +1,39 @@
+"""QActions aus dem Kürzel-Verzeichnis (``shortcuts.ACTIONS``): eine je Aktion, Kürzel änderbar.
+
+Wer eine Aktion nutzt, verbindet ``triggered`` und hängt sie an das passende Widget
+(globale ans Hauptfenster, „canvas“ an die Arbeitsfläche, „text“ ans Textfeld).
+"""
+from __future__ import annotations
+
+from PySide6.QtCore import QObject, Qt
+from PySide6.QtGui import QAction, QKeySequence
+
+from .. import shortcuts
+
+_CONTEXT = {
+    "global": Qt.ShortcutContext.WindowShortcut,
+    "canvas": Qt.ShortcutContext.WidgetWithChildrenShortcut,
+    "text": Qt.ShortcutContext.WidgetWithChildrenShortcut,
+}
+
+
+def build_actions(parent: QObject, mapping: dict[str, str]) -> dict[str, QAction]:
+    """Je Aktion des Verzeichnisses eine QAction mit Name, Bereich und Kürzel aus ``mapping``."""
+    actions = {}
+    for entry in shortcuts.ACTIONS:
+        action = QAction(entry.name, parent)
+        action.setObjectName(entry.id)
+        action.setShortcutContext(_CONTEXT[entry.scope])
+        actions[entry.id] = action
+    apply_shortcuts(actions, mapping)
+    return actions
+
+
+def apply_shortcuts(actions: dict[str, QAction], mapping: dict[str, str]) -> None:
+    """Kürzel (z. B. nach dem Speichern der Einstellungen) setzen; Tooltip nennt das Kürzel."""
+    for action_id, action in actions.items():
+        sequence = QKeySequence(mapping.get(action_id, ""))
+        action.setShortcut(sequence)
+        name = shortcuts.action(action_id).name
+        keys = sequence.toString(QKeySequence.SequenceFormat.NativeText)
+        action.setToolTip(f"{name} ({keys})" if keys else name)
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index 4f83f3a..606c9f4 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -1,21 +1,38 @@
-"""Arbeitsfläche: Etikett in echter Größe und Form, mm-Lineale, Zoom, Längen-Anfasser."""
+"""Arbeitsfläche: Etikett in echter Größe und Form, Objekte (auswählen, ziehen, einrasten,
+an Anfassern skalieren), mm-Lineale, Zoom, Längen-Anfasser."""
 from __future__ import annotations
 
 import math
 
 from PIL import Image, ImageOps
 from PySide6.QtCore import QPointF, QRectF, Qt, Signal
-from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
-from PySide6.QtWidgets import QGraphicsScene, QGraphicsView
+from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap,
+                           QTransform)
+from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView
 
+from .. import layout
 from ..labels import DPI, Label, format_mm, length_limits
+from ..layout import Rect
 from ..printer import DEFAULT_MODEL
+from ..render import RenderedObject
 
 MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm
 RULER = 22               # Linealbreite in Pixeln
 _CORNER = 2 * MM         # Eckenradius gestanzter Etiketten
 _MARGIN = 15 * MM        # grauer Rand um das Etikett
 START_ZOOM = 200         # Prozent; 100 % = echte Größe
+SNAP_PX = 6              # Einrasten: Abstand in Bildschirmpixeln
+HANDLE_PX = 8            # Kantenlänge eines Anfassers in Bildschirmpixeln
+_DRAG_START_PX = 3       # erst ab dieser Mausbewegung wird gezogen (Klick ≠ Verschieben)
+_MIN_FRAME = MM          # kleinster Rahmen beim Skalieren (1 mm)
+HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")   # Ecken und Kanten, im Uhrzeigersinn
+_HANDLE_CURSORS = {
+    "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
+    "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
+    "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
+    "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
+}
+_GUIDE_COLOR = QColor("#E53935")
 
 
 def to_qimage(img: Image.Image) -> QImage:
@@ -27,10 +44,43 @@ def to_qimage(img: Image.Image) -> QImage:
                   QImage.Format.Format_RGBA8888).copy()
 
 
+class ObjectItem(QGraphicsPixmapItem):
+    """Ein Objekt auf der Arbeitsfläche: sein Bild aus ``render_object`` an seiner Position.
+
+    Koordinaten in Druckpunkten in Leserichtung; das Elternelement (``Canvas.sheet``) dreht
+    bei „horizontal“ in Druckkoordinaten.
+    """
+
+    def __init__(self, index: int, rendered: RenderedObject, pixmap: QPixmap, keep_ratio: bool,
+                 parent: QGraphicsRectItem):
+        super().__init__(pixmap, parent)
+        self.index = index
+        self.rendered = rendered
+        self.keep_ratio = keep_ratio     # Ecken skalieren die Schrift: Seitenverhältnis bleibt
+        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
+        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
+        self.setPos(rendered.x, rendered.y)
+        self.setCursor(Qt.CursorShape.SizeAllCursor)
+
+    def is_empty(self) -> bool:
+        return self.rendered.w == 0 or self.rendered.h == 0
+
+    def frame(self) -> QRectF:
+        """Rahmen in Druckpunkten in Leserichtung (beim Ziehen samt Vorschau-Streckung)."""
+        return self.mapRectToParent(QRectF(0, 0, self.rendered.w, self.rendered.h))
+
+    def frame_mm(self) -> Rect:
+        f = self.frame()
+        return Rect(f.x() / MM, f.y() / MM, f.width() / MM, f.height() / MM)
+
+
 class Canvas(QGraphicsView):
     length_changed = Signal(object)   # neue Länge in mm (float) oder None = automatisch
     zoom_changed = Signal(int)        # Zoom in Prozent
-    drag_finished = Signal()          # Anfasser losgelassen (nach tatsächlichem Ziehen)
+    drag_finished = Signal()          # Längen-Anfasser losgelassen (nach tatsächlichem Ziehen)
+    selection_changed = Signal(list)  # Indizes der ausgewählten Objekte in der Reihenfolge der Wahl
+    objects_moved = Signal(list, list)         # Indizes, neue Rahmen (Rect, mm) nach dem Loslassen
+    object_resized = Signal(int, object, str)  # Index, neuer Rahmen (Rect, mm), Anfasser („tl“ …)
 
     def __init__(self, model: str = DEFAULT_MODEL):
         super().__init__()
@@ -39,6 +89,8 @@ class Canvas(QGraphicsView):
         self.setRenderHints(QPainter.RenderHint.Antialiasing
                             | QPainter.RenderHint.SmoothPixmapTransform)
         self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
+        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
+        self.viewport().setMouseTracking(True)             # Mauszeiger über den Anfassern
         min_len, max_len = length_limits(model)
         self.min_mm, self.max_mm = min_len / MM, max_len / MM
         self.zoom = START_ZOOM
@@ -46,27 +98,49 @@ class Canvas(QGraphicsView):
         self._scale = 1.0
         self.label: Label | None = None
         self.outline = self.printable = self.handle = None
+        self.sheet: QGraphicsRectItem | None = None        # Etikett in Leserichtung (Druckpunkte)
+        self.objects: list[ObjectItem] = []
+        self._pixmaps: dict[int, tuple[RenderedObject, QPixmap]] = {}
+        self._selection: list[int] = []
+        self._area = self._label_rect = Rect(0, 0, 0, 0)
+        self._guides: list[tuple[str, float]] = []
         self._caption = ""
-        self._dragging = False
+        self._drag: str | None = None                      # "length" | "move" | "resize"
         self._moved = False
         self._grab_offset = 0.0
+        self._press = QPointF()
+        self._grabbed = -1
+        self._start: dict[int, QPointF] = {}
+        self._resize_key = ""
+        self._start_frame = QRectF()
+        self._handle_offset = QPointF()
+        self._handle_cursor = False
         self._apply_zoom()
 
     # --- Inhalt -----------------------------------------------------------
-    def set_document(self, label: Label, image: Image.Image, orientation: str = "vertical") -> None:
-        """Etikett (physische Form) und Druckbild darin anzeigen.
+    def set_document(self, label: Label, size: tuple[int, int],
+                     rendered: list[RenderedObject], orientation: str = "vertical",
+                     area: Rect | None = None, keep_ratio: list[bool] | None = None) -> None:
+        """Etikett (physische Form) und die einzeln gerenderten Objekte darin anzeigen.
 
-        Die Szene ist immer in Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°,
-        damit das Etikett in Leserichtung erscheint.
+        ``size``: Etikett in Druckpunkten in Leserichtung (wie ``render.label_size``);
+        ``area``: bedruckbarer Bereich in mm (Einrasten); ``keep_ratio`` je Objekt: Ecken
+        skalieren die Schrift (ohne feste Rahmengröße). Die Szene ist immer in
+        Druckkoordinaten; bei „horizontal“ dreht die Ansicht um −90°, damit das Etikett in
+        Leserichtung erscheint – die Objekte liegen in ``sheet``, das in Leserichtung zählt.
         """
         if orientation != self.orientation:
             self.orientation = orientation
             self._apply_zoom()
+        self._cancel_object_drag()
         scene = self.scene()
         scene.clear()
         self.label = label
+        width, height = size
+        horizontal = orientation == "horizontal"
+        pw, ph = (height, width) if horizontal else (width, height)   # Druckbild
         tw = label.total_width
-        th = label.total_height or image.height
+        th = label.total_height or ph
         path = QPainterPath()
         if label.shape == "round":
             path.addEllipse(0, 0, tw, th)
@@ -76,12 +150,22 @@ class Canvas(QGraphicsView):
             path.addRect(0, 0, tw, th)
         self.outline = scene.addPath(path, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
 
-        ox, oy = (tw - image.width) / 2, (th - image.height) / 2
-        pixmap = scene.addPixmap(QPixmap.fromImage(to_qimage(image)))
-        pixmap.setPos(ox, oy)
+        ox, oy = (tw - pw) / 2, (th - ph) / 2
+        self.sheet = QGraphicsRectItem(0, 0, width, height)
+        self.sheet.setPen(QPen(Qt.PenStyle.NoPen))
+        # Leserichtung → Druck: bei „horizontal“ 90° im Uhrzeigersinn wie render_document
+        self.sheet.setTransform(QTransform().translate(ox + pw, oy).rotate(90) if horizontal
+                                else QTransform().translate(ox, oy))
+        scene.addItem(self.sheet)
+        self._pixmaps = {id(obj): (obj, self._pixmap(obj)) for obj in rendered}
+        ratios = keep_ratio if keep_ratio is not None else [True] * len(rendered)
+        self.objects = [ObjectItem(i, obj, self._pixmaps[id(obj)][1], ratio, self.sheet)
+                        for i, (obj, ratio) in enumerate(zip(rendered, ratios))]
+        self._label_rect = Rect(0, 0, width / MM, height / MM)
+        self._area = area if area is not None else self._label_rect
         dotted = QPen(QColor("#888888"), 1, Qt.PenStyle.DotLine)
         dotted.setCosmetic(True)
-        self.printable = scene.addRect(QRectF(ox, oy, image.width, image.height), dotted)
+        self.printable = scene.addRect(QRectF(ox, oy, pw, ph), dotted)
 
         self.handle = None
         if label.shape == "endless":
@@ -96,6 +180,83 @@ class Canvas(QGraphicsView):
             self.handle.setToolTip("Ziehen: Länge festlegen · Doppelklick: automatisch")
         self._caption = self._caption_for(th)
         scene.setSceneRect(-_MARGIN, -_MARGIN, tw + 2 * _MARGIN, th + 2 * _MARGIN)
+        self.set_selection([i for i in self._selection if self._selectable(i)])
+
+    def _pixmap(self, rendered: RenderedObject) -> QPixmap:
+        """Pixmap je Objektbild nur einmal erzeugen (unverändertes Objekt = dasselbe Bild).
+
+        Der Cache hält das Objektbild selbst fest, damit seine id nicht neu vergeben wird."""
+        cached = self._pixmaps.get(id(rendered))
+        if cached is not None and cached[0] is rendered:
+            return cached[1]
+        return QPixmap.fromImage(to_qimage(rendered.image))
+
+    # --- Auswahl ----------------------------------------------------------
+    def selection(self) -> list[int]:
+        return list(self._selection)
+
+    def set_selection(self, indices: list[int]) -> None:
+        chosen = list(dict.fromkeys(i for i in indices if self._selectable(i)))
+        if chosen != self._selection:
+            self._selection = chosen
+            self.viewport().update()
+            self.selection_changed.emit(self.selection())
+
+    def select_all(self) -> None:
+        self.set_selection(list(range(len(self.objects))))
+
+    def _selectable(self, index: int) -> bool:
+        return 0 <= index < len(self.objects) and not self.objects[index].is_empty()
+
+    def nudge(self, dx_mm: float, dy_mm: float) -> None:
+        """Ausgewählte Objekte um dx/dy mm verschieben (Pfeiltasten)."""
+        if self._selection:
+            frames = [self.objects[i].frame_mm().moved(dx_mm, dy_mm) for i in self._selection]
+            self.objects_moved.emit(self.selection(), frames)
+
+    # --- Geometrie --------------------------------------------------------
+    def px_per_mm(self) -> float:
+        """Bildschirmpixel je mm beim aktuellen Zoom."""
+        return self._scale * MM
+
+    def guides(self) -> list[tuple[str, float]]:
+        """Hilfslinien beim Ziehen: ("x" | "y", mm in Leserichtung)."""
+        return list(self._guides)
+
+    def view_rect(self, index: int) -> QRectF:
+        """Rahmen eines Objekts in Ansichtskoordinaten (Pixel)."""
+        frame = self.sheet.mapRectToScene(self.objects[index].frame())
+        return self.viewportTransform().mapRect(frame)
+
+    def handle_points(self, index: int) -> dict[str, QPointF]:
+        """Mittelpunkte der 8 Anfasser in Ansichtskoordinaten (Ansicht zeigt die Leserichtung)."""
+        r = self.view_rect(index)
+        cx, cy = r.center().x(), r.center().y()
+        return {"tl": r.topLeft(), "t": QPointF(cx, r.top()), "tr": r.topRight(),
+                "r": QPointF(r.right(), cy), "br": r.bottomRight(), "b": QPointF(cx, r.bottom()),
+                "bl": r.bottomLeft(), "l": QPointF(r.left(), cy)}
+
+    def _reading(self, pos: QPointF) -> QPointF:
+        """Ansichtspunkt → Druckpunkte in Leserichtung."""
+        return self.sheet.mapFromScene(self.viewportTransform().inverted()[0].map(pos))
+
+    def _view_point(self, x: float, y: float) -> QPointF:
+        """Druckpunkte in Leserichtung → Ansichtspunkt."""
+        return self.viewportTransform().map(self.sheet.mapToScene(QPointF(x, y)))
+
+    def _object_at(self, pos: QPointF) -> ObjectItem | None:
+        for item in self.items(pos.toPoint()):            # oberstes zuerst
+            if isinstance(item, ObjectItem) and not item.is_empty():
+                return item
+        return None
+
+    def _handle_at(self, pos: QPointF) -> tuple[int, str] | None:
+        reach = HANDLE_PX / 2 + 1
+        for index in reversed(self._selection):            # zuletzt gewähltes zuerst
+            for key, point in self.handle_points(index).items():
+                if abs(point.x() - pos.x()) <= reach and abs(point.y() - pos.y()) <= reach:
+                    return index, key
+        return None
 
     # --- Zoom -------------------------------------------------------------
     def set_zoom(self, percent: int) -> None:
@@ -124,12 +285,13 @@ class Canvas(QGraphicsView):
         else:
             super().wheelEvent(event)
 
-    # --- Länge ziehen -----------------------------------------------------
+    # --- Maus -------------------------------------------------------------
     def _on_handle(self, event) -> bool:
         return self.handle is not None and self.itemAt(event.position().toPoint()) is self.handle
 
     def is_dragging(self) -> bool:
-        return self._dragging
+        """Längen-Anfasser oder Objekt wird gerade gezogen."""
+        return self._drag is not None
 
     def snap_length(self, scene_y: float) -> float:
         """Szene-y der Unterkante → Länge in mm (Raster 0,5 mm, innerhalb der Modellgrenzen)."""
@@ -137,34 +299,133 @@ class Canvas(QGraphicsView):
         return min(max(mm, self.min_mm), self.max_mm)
 
     def mousePressEvent(self, event) -> None:
-        if event.button() == Qt.MouseButton.LeftButton and self._on_handle(event):
-            self._dragging = True
-            self._moved = False
+        if event.button() != Qt.MouseButton.LeftButton:
+            super().mousePressEvent(event)
+            return
+        pos = event.position()
+        self._press = pos
+        self._moved = False
+        if self._on_handle(event):
+            self._drag = "length"
             # Versatz zwischen Cursor und Schnittkante merken, damit der Anfasser nicht springt
-            self._grab_offset = self.mapToScene(event.position().toPoint()).y() - self.label_height()
+            self._grab_offset = self.mapToScene(pos.toPoint()).y() - self.label_height()
+            return
+        if self.sheet is None:
+            return
+        hit = self._handle_at(pos)
+        if hit is not None:
+            self._begin_resize(*hit, pos)
             return
-        super().mousePressEvent(event)
+        item = self._object_at(pos)
+        toggle = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
+        if item is None:
+            if not toggle:
+                self.set_selection([])
+        elif toggle:
+            chosen = self.selection()
+            self.set_selection([i for i in chosen if i != item.index] if item.index in chosen
+                               else [*chosen, item.index])
+        else:
+            if item.index not in self._selection:
+                self.set_selection([item.index])
+            self._drag = "move"
+            self._grabbed = item.index
+            self._start = {i: self.objects[i].pos() for i in self._selection}
+
+    def _begin_resize(self, index: int, key: str, pos: QPointF) -> None:
+        self._drag = "resize"
+        self._grabbed = index
+        self._resize_key = key
+        self._start_frame = self.objects[index].frame()
+        f = self._start_frame
+        x = f.left() if "l" in key else f.right() if "r" in key else f.center().x()
+        y = f.top() if "t" in key else f.bottom() if "b" in key else f.center().y()
+        self._handle_offset = QPointF(x, y) - self._reading(pos)   # Anfasser springt nicht
 
     def mouseMoveEvent(self, event) -> None:
-        if self._dragging:
-            mm = self.snap_length(
-                self.mapToScene(event.position().toPoint()).y() - self._grab_offset)
+        pos = event.position()
+        if self._drag == "length":
+            mm = self.snap_length(self.mapToScene(pos.toPoint()).y() - self._grab_offset)
             self.handle.setY(mm * MM - self.label_height())
             self._caption = self._caption_for(mm * MM)
             self.viewport().update()
             self._moved = True
             self.length_changed.emit(mm)
             return
+        if self._drag in ("move", "resize"):
+            if not self._moved and (pos - self._press).manhattanLength() < _DRAG_START_PX:
+                return
+            self._moved = True
+            snapping = not event.modifiers() & Qt.KeyboardModifier.AltModifier
+            if self._drag == "move":
+                self._drag_move(pos, snapping)
+            else:
+                self._drag_resize(pos)
+            self.viewport().update()
+            return
+        hit = self._handle_at(pos) if self.sheet is not None else None
+        if self._handle_cursor and hit is None:
+            self.viewport().unsetCursor()
         super().mouseMoveEvent(event)
+        if hit is not None:                                # Anfasser zeigt seine Richtung
+            self.viewport().setCursor(_HANDLE_CURSORS[hit[1]])
+        self._handle_cursor = hit is not None
+
+    def _drag_move(self, pos: QPointF, snapping: bool) -> None:
+        """Ausgewählte Bilder verschieben (Modell erst beim Loslassen), dabei einrasten."""
+        delta = self._reading(pos) - self._reading(self._press)
+        self._guides = []
+        if snapping:
+            dx, dy = delta.x() / MM, delta.y() / MM
+            frames = [self._start_rect(i).moved(dx, dy) for i in self._start]
+            targets = [item.frame_mm() for item in self.objects
+                       if item.index not in self._start and not item.is_empty()]
+            snap = layout.snap(layout.bounds(frames), targets, self._area,
+                               SNAP_PX / self.px_per_mm(), label=self._label_rect)
+            delta += QPointF(snap.dx * MM, snap.dy * MM)
+            self._guides = snap.guides
+        for index, start in self._start.items():
+            self.objects[index].setPos(start + delta)
+
+    def _start_rect(self, index: int) -> Rect:
+        start, rendered = self._start[index], self.objects[index].rendered
+        return Rect(start.x() / MM, start.y() / MM, rendered.w / MM, rendered.h / MM)
+
+    def _drag_resize(self, pos: QPointF) -> None:
+        """Vorschau beim Ziehen an einem Anfasser: Bild gestreckt, gerendert wird beim Loslassen."""
+        item = self.objects[self._grabbed]
+        frame = resized_frame(self._start_frame, self._resize_key,
+                              self._reading(pos) + self._handle_offset, item.keep_ratio)
+        item.setPos(frame.topLeft())
+        item.setTransform(QTransform.fromScale(frame.width() / item.rendered.w,
+                                               frame.height() / item.rendered.h))
 
     def mouseReleaseEvent(self, event) -> None:
-        if self._dragging:
-            self._dragging = False
+        drag, self._drag = self._drag, None
+        if drag == "length":
             if self._moved:
                 self.drag_finished.emit()
             return
+        if drag in ("move", "resize"):
+            self._guides = []
+            self.viewport().update()
+            index = self._grabbed
+            if drag == "move" and self._moved:
+                indices = list(self._start)
+                self.objects_moved.emit(indices, [self.objects[i].frame_mm() for i in indices])
+            elif drag == "resize" and self._moved:
+                self.object_resized.emit(index, self.objects[index].frame_mm(), self._resize_key)
+            elif drag == "move" and len(self._selection) > 1:
+                self.set_selection([index])                # Klick in die Auswahl: nur dieses
+            return
         super().mouseReleaseEvent(event)
 
+    def _cancel_object_drag(self) -> None:
+        """Neuer Inhalt während des Ziehens: Ziehen am alten Element abbrechen."""
+        if self._drag in ("move", "resize"):
+            self._drag = None
+            self._guides = []
+
     def mouseDoubleClickEvent(self, event) -> None:
         if self._on_handle(event):
             self.length_changed.emit(None)
@@ -174,11 +435,13 @@ class Canvas(QGraphicsView):
     def label_height(self) -> float:
         return self.outline.path().boundingRect().height() if self.outline else 0.0
 
-    # --- Lineale und Beschriftung -----------------------------------------
+    # --- Auswahlrahmen, Hilfslinien, Lineale ------------------------------
     def drawForeground(self, painter: QPainter, rect) -> None:
         painter.save()
         painter.resetTransform()
         vw, vh = self.viewport().width(), self.viewport().height()
+        self._draw_selection(painter)
+        self._draw_guides(painter, vw, vh)
         if self.outline is not None:
             box = self.label_view_rect()
             painter.setPen(Qt.GlobalColor.black)
@@ -190,6 +453,31 @@ class Canvas(QGraphicsView):
         self._draw_rulers(painter, vw, vh)
         painter.restore()
 
+    def _draw_selection(self, painter: QPainter) -> None:
+        """Ausgewählte Objekte: gestrichelter Rahmen mit 8 Anfassern (feste Pixelgröße)."""
+        frame = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
+        border = QPen(Qt.GlobalColor.black, 1)
+        half = HANDLE_PX / 2
+        for index in self._selection:
+            painter.setPen(frame)
+            painter.setBrush(Qt.BrushStyle.NoBrush)
+            painter.drawRect(self.view_rect(index))
+            painter.setPen(border)
+            painter.setBrush(Qt.GlobalColor.white)
+            for point in self.handle_points(index).values():
+                painter.drawRect(QRectF(point.x() - half, point.y() - half, HANDLE_PX, HANDLE_PX))
+        painter.setBrush(Qt.BrushStyle.NoBrush)
+
+    def _draw_guides(self, painter: QPainter, vw: int, vh: int) -> None:
+        """Rote Hilfslinien über die ganze Ansicht, solange ein Objekt einrastet."""
+        painter.setPen(QPen(_GUIDE_COLOR, 1))
+        for axis, mm in self._guides:
+            point = self._view_point(mm * MM, mm * MM)
+            if axis == "x":
+                painter.drawLine(QPointF(point.x(), 0), QPointF(point.x(), vh))
+            else:
+                painter.drawLine(QPointF(0, point.y()), QPointF(vw, point.y()))
+
     def label_view_rect(self) -> QRectF:
         """Etikett in Ansichtskoordinaten (berücksichtigt Zoom und Drehung)."""
         if self.outline is None:
@@ -229,3 +517,26 @@ class Canvas(QGraphicsView):
         painter.drawLine(0, RULER, vw, RULER)
         painter.drawLine(RULER, 0, RULER, vh)
         painter.fillRect(0, 0, RULER, RULER, Qt.GlobalColor.white)
+
+
+def resized_frame(start: QRectF, key: str, point: QPointF, keep_ratio: bool) -> QRectF:
+    """Rahmen nach Ziehen am Anfasser ``key`` auf ``point`` (Druckpunkte in Leserichtung).
+
+    Die gegenüberliegende Ecke bzw. Kante bleibt stehen; mindestens 1 mm. ``keep_ratio``:
+    Ecken behalten das Seitenverhältnis (Schrift skalieren).
+    """
+    left, top, right, bottom = start.left(), start.top(), start.right(), start.bottom()
+    if "l" in key:
+        left = min(point.x(), right - _MIN_FRAME)
+    if "r" in key:
+        right = max(point.x(), left + _MIN_FRAME)
+    if "t" in key:
+        top = min(point.y(), bottom - _MIN_FRAME)
+    if "b" in key:
+        bottom = max(point.y(), top + _MIN_FRAME)
+    if keep_ratio and len(key) == 2:
+        factor = max((right - left) / start.width(), (bottom - top) / start.height())
+        w, h = start.width() * factor, start.height() * factor
+        left, right = (right - w, right) if "l" in key else (left, left + w)
+        top, bottom = (bottom - h, bottom) if "t" in key else (top, top + h)
+    return QRectF(QPointF(left, top), QPointF(right, bottom))
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index af7c908..20c86ec 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -1,6 +1,8 @@
 """Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
 from __future__ import annotations
 
+import copy
+from dataclasses import dataclass
 from pathlib import Path
 
 from PySide6.QtCore import Qt, QThreadPool, QTimer
@@ -10,11 +12,14 @@ from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QS
 
 from ..desktop import APP_NAME
 from ..detect import brother_busy, find_brother_lp
-from ..document import Document
+from ..document import Document, TextObject
 from ..labels import get_label
+from ..layout import Rect, move, objects_outside, printable_area, resize
 from ..printer import DEFAULT_MODEL
-from ..render import font_warnings, render_document
+from ..render import RenderedObject, compose, font_warnings, label_size, render_object
 from ..settings import Settings, load_settings, new_document
+from ..shortcuts import effective
+from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
 from .media_worker import MediaWorker
 from .print_worker import PrintWorker
@@ -24,6 +29,18 @@ from .tools import TOOLS, Tool
 RENDER_DELAY_MS = 150
 MEDIA_STATUS_MAX_PX = 360   # Rollen-Hinweis in der Fußzeile; Rest per „…“ und Tooltip
 PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff
+NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
+_DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
+OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"
+
+
+@dataclass
+class _Cached:
+    """Gerendertes Objekt samt Stand, aus dem es entstand (Neu-Rendern nur bei Änderung)."""
+    obj: TextObject            # hält das Objekt fest, damit seine id nicht neu vergeben wird
+    snapshot: TextObject
+    key: tuple
+    rendered: RenderedObject
 
 
 class MainWindow(QMainWindow):
@@ -36,8 +53,10 @@ class MainWindow(QMainWindow):
         self.doc = doc if doc is not None else new_document(self.settings)
         self.model = model
         self.image = None
+        self.rendered: list[RenderedObject] = []    # Objektbilder auf der Arbeitsfläche = im Druck
+        self._cache: dict[int, _Cached] = {}
         self._render_error: str | None = None
-        self._font_warning: str | None = None
+        self._hint: str | None = None               # Hinweis (ragt hinaus, Schrift ersetzt)
         self._print_signals = None
         self._media_signals = None
         self._printer_present = False
@@ -84,6 +103,10 @@ class MainWindow(QMainWindow):
         self.apply_theme_icons()
         self.canvas.length_changed.connect(self._on_length_dragged)
         self.canvas.drag_finished.connect(self.render_now)
+        self.canvas.objects_moved.connect(self._move_objects)
+        self.canvas.object_resized.connect(self._resize_object)
+        self.actions = build_actions(self, effective(self.settings.shortcuts))
+        self._connect_canvas_actions()
         central = QWidget()
         layout = QHBoxLayout(central)
         layout.setContentsMargins(0, 0, 0, 0)
@@ -131,14 +154,33 @@ class MainWindow(QMainWindow):
     def panel(self, key: str):
         return self._panel_by_key[key]
 
+    def _connect_canvas_actions(self) -> None:
+        """Kürzel der Arbeitsfläche: Pfeiltasten, Löschen, Alles auswählen."""
+        for direction, (sx, sy) in _DIRECTIONS.items():
+            for suffix, step in NUDGE_MM.items():
+                action = self.actions[f"object.nudge_{direction}{suffix}"]
+                action.triggered.connect(
+                    lambda _=False, dx=sx * step, dy=sy * step: self.canvas.nudge(dx, dy))
+                self.canvas.addAction(action)
+        self.actions["edit.delete"].triggered.connect(self.delete_selected)
+        self.actions["edit.select_all"].triggered.connect(self.canvas.select_all)
+        self.canvas.addActions([self.actions["edit.delete"], self.actions["edit.select_all"]])
+
     # --- Rendern ----------------------------------------------------------
     def schedule_render(self) -> None:
         self._timer.start()
 
     def render_now(self) -> None:
         self._timer.stop()
+        if self.canvas.is_dragging():   # Ziehen nicht unterbrechen – nach dem Loslassen rendern
+            self._timer.start()
+            return
         try:
-            image = render_document(self.doc, self.model)
+            size = label_size(self.doc, self.model)
+            rendered = self._render_objects(size)
+            image = compose(rendered, size, self.doc.orientation)
+            area = printable_area(self.doc, self.model)
+            outside = objects_outside(self.doc, self.model)
         except ValueError as e:
             # letztes gültiges Bild bleibt in der Vorschau, wird aber nicht gedruckt
             self._render_error = str(e)
@@ -148,16 +190,65 @@ class MainWindow(QMainWindow):
         if self._render_error is not None and self.result.text() == self._render_error:
             self._set_result("", "")   # nur den Renderfehler löschen, kein Druckergebnis
         self._render_error = None
-        if self._font_warning is not None and self.result.text() == self._font_warning:
-            self._set_result("", "")   # alten Schrifthinweis nur löschen, wenn er noch dasteht
-        self._font_warning = None
-        warnings = font_warnings(self.doc)
-        if warnings and not self.result.text():
-            self._font_warning = " · ".join(warnings)
-            self._set_result(self._font_warning, "error")
+        if self._hint is not None and self.result.text() == self._hint:
+            self._set_result("", "")   # alten Hinweis nur löschen, wenn er noch dasteht
+        self._hint = None
+        hints = ([OUTSIDE_HINT] if outside else []) + font_warnings(self.doc)
+        if hints and not self.result.text():
+            self._hint = " · ".join(hints)
+            self._set_result(self._hint, "error")
         self.panel("text").show_error(None)
         self.image = image
-        self.canvas.set_document(get_label(self.doc.label_id), image, self.doc.orientation)
+        self.rendered = rendered
+        self.canvas.set_document(get_label(self.doc.label_id), size, rendered, self.doc.orientation,
+                                 area, keep_ratio=[not obj.fit for obj in self.doc.objects])
+
+    def _render_objects(self, size: tuple[int, int]) -> list[RenderedObject]:
+        """Objekte einzeln rendern; unveränderte kommen aus dem Cache.
+
+        Ein Objekt ohne Position steht mittig und hängt deshalb auch von der Etikettgröße ab.
+        """
+        doc = self.doc
+        context = (self.model, doc.label_id, doc.orientation, doc.margin_mm, doc.length_mm)
+        cache: dict[int, _Cached] = {}
+        for obj in doc.objects:
+            key = (context, None if obj.positioned else size)
+            entry = self._cache.get(id(obj))
+            if entry is None or entry.obj is not obj or entry.key != key or entry.snapshot != obj:
+                entry = _Cached(obj, copy.deepcopy(obj), key, render_object(obj, doc, self.model))
+            cache[id(obj)] = entry
+        self._cache = cache
+        return [cache[id(obj)].rendered for obj in doc.objects]
+
+    # --- Objekte auf der Arbeitsfläche ------------------------------------
+    def _move_objects(self, indices: list[int], rects: list[Rect]) -> None:
+        for index, rect in zip(indices, rects):
+            if index < len(self.rendered):
+                self.doc.objects[index] = move(self.doc.objects[index], rect, self.rendered[index])
+        self._objects_changed(indices)
+
+    def _resize_object(self, index: int, rect: Rect, handle: str) -> None:
+        if index < len(self.rendered):
+            self.doc.objects[index] = resize(self.doc.objects[index], rect, self.rendered[index],
+                                             corner=len(handle) == 2)
+        self._objects_changed([index])
+
+    def delete_selected(self) -> None:
+        """Ausgewählte Objekte löschen; ein leerer Text bleibt, damit das Text-Panel etwas hat."""
+        indices = self.canvas.selection()
+        if not indices:
+            return
+        self.canvas.set_selection([])
+        for index in sorted(indices, reverse=True):
+            del self.doc.objects[index]
+        if not self.doc.objects:
+            self.doc.objects.append(new_document(self.settings).objects[0])
+        self._objects_changed([0])
+
+    def _objects_changed(self, indices: list[int]) -> None:
+        if 0 in indices:
+            self.panel("text").refresh()   # Text-Panel bearbeitet (noch) das erste Objekt
+        self.render_now()
 
     def _on_length_dragged(self, length_mm) -> None:
         self.doc.length_mm = length_mm
@@ -227,6 +318,7 @@ class MainWindow(QMainWindow):
             from .app import apply_theme
             apply_theme(QApplication.instance(), self.settings.theme)
             self.apply_theme_icons()
+            apply_shortcuts(self.actions, effective(self.settings.shortcuts))
             self._set_result("Einstellungen gespeichert – gelten für neue Etiketten.", "ok")
 
     # --- Medium prüfen ----------------------------------------------------
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index 6a1353d..b87f274 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -348,8 +348,10 @@ class TextPanel(Panel):
                 spans.append(_span("", self._props(block.charFormat()), base_pt))
             paragraphs.append(Paragraph(spans, align))
             block = block.next()
-        return TextObject(paragraphs, size_pt=base_pt, font_path=self.obj.font_path,
-                          fit=self.fit.isChecked())
+        obj = self.obj                 # Rahmen und Drehung bleiben beim Tippen erhalten
+        return TextObject(paragraphs, size_pt=base_pt, font_path=obj.font_path,
+                          fit=self.fit.isChecked(), x_mm=obj.x_mm, y_mm=obj.y_mm,
+                          w_mm=obj.w_mm, h_mm=obj.h_mm, rotation=obj.rotation)
 
     def _apply(self) -> None:
         if self._updating or self._formatting:
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index 09b921f..23e9e9d 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -15,6 +15,7 @@ from .render import REF_PT, RenderedObject, label_margins, label_size, render_ob
 ALIGN_MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom")
 SIZE_MODES = ("same", "width", "height")
 _EPS = 1e-6                # Rundungsspielraum beim Vergleich von mm-Werten
+_DECIMALS = 3              # Positionen/Rahmen im Modell: auf 1/1000 mm
 
 
 def _mm(dots: float) -> float:
@@ -173,6 +174,77 @@ def place(obj: TextObject, rect: Rect) -> TextObject:
     return placed
 
 
+def fix_size(obj: TextObject, base_pt: float) -> TextObject:
+    """Kopie mit der wirksamen Grundgröße ``base_pt`` als fester Schriftgröße, ohne Rahmengröße.
+
+    Stücke mit eigener Größe behalten ihr Verhältnis; das Bild bleibt gleich.
+    """
+    base_pt = round(base_pt, 1)            # wie scale_text; Stücke rechnen mit derselben Größe
+    factor = 1.0 if obj.size_pt is None else base_pt / obj.size_pt
+    fixed = scale_text(obj, factor, base_pt=base_pt)
+    fixed.fit = False
+    return fixed
+
+
+def exact_rect(obj: TextObject, rendered: RenderedObject) -> Rect:
+    """Rahmen in mm, wie er im Modell steht (ohne Rundung auf Druckpunkte).
+
+    Position aus ``x_mm``/``y_mm``, Größe bei fester Rahmengröße aus ``w_mm``/``h_mm``
+    (gedreht), sonst wie gerendert; ein Objekt ohne Position steht, wo es gerendert wurde.
+    """
+    r = object_rect(rendered)
+    x, y = ((obj.x_mm or 0.0, obj.y_mm or 0.0) if obj.positioned else (r.x, r.y))
+    w, h = r.w, r.h
+    if obj.positioned and obj.fit and obj.w_mm is not None and obj.h_mm is not None:
+        w, h = (obj.h_mm, obj.w_mm) if obj.rotation in (90, 270) else (obj.w_mm, obj.h_mm)
+    return Rect(x, y, w, h)
+
+
+def _apply_change(obj: TextObject, rect: Rect, rendered: RenderedObject) -> Rect:
+    """Änderung gegenüber dem gerenderten Rahmen auf den Rahmen im Modell übertragen.
+
+    So verschieben Pfeiltasten genau um 0,1 mm, obwohl das Bild auf Druckpunkte gerundet ist;
+    Reste der Umrechnung werden auf 1/1000 mm gerundet.
+    """
+    shown, exact = object_rect(rendered), exact_rect(obj, rendered)
+    return Rect(*(round(e + n - s, _DECIMALS) for e, n, s in (
+        (exact.x, rect.x, shown.x), (exact.y, rect.y, shown.y),
+        (exact.w, rect.w, shown.w), (exact.h, rect.h, shown.h))))
+
+
+def move(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
+    """Kopie von ``obj``, verschoben auf ``rect`` (neue Lage des gerenderten Rahmens).
+
+    Die Größe bleibt. Ein automatisch großes Objekt ohne eigenen Rahmen bekommt beim ersten
+    Verschieben seine wirksame Größe (``rendered.base_pt``) als feste Schriftgröße – es sieht
+    danach genauso aus.
+    """
+    target = _apply_change(obj, rect, rendered)
+    if obj.size_pt is None or (obj.fit and not obj.positioned):
+        obj = fix_size(obj, rendered.base_pt)
+    moved = copy.deepcopy(obj)
+    moved.x_mm, moved.y_mm = target.x, target.y
+    return moved
+
+
+def resize(obj: TextObject, rect: Rect, rendered: RenderedObject, corner: bool) -> TextObject:
+    """Kopie nach Ziehen an einem Anfasser: gerenderter Rahmen → ``rect``.
+
+    Mit fester Rahmengröße ändert jeder Anfasser den Rahmen. Ohne skaliert eine Ecke
+    (``corner``) die Schrift, eine Kante schaltet die feste Rahmengröße ein.
+    """
+    target = _apply_change(obj, rect, rendered)
+    if obj.fit:
+        return place(obj, target)
+    if corner:
+        old = object_rect(rendered)
+        factor = ((rect.w * rect.h) / (old.w * old.h)) ** 0.5 if old.w and old.h else 1.0
+        return place(scale_text(obj, factor, base_pt=rendered.base_pt), target)
+    framed = copy.deepcopy(obj)
+    framed.fit = True
+    return place(framed, target)
+
+
 def scale_text(obj: TextObject, factor: float, base_pt: float | None = None) -> TextObject:
     """Kopie mit allen Schriftgrößen (Grundgröße und Stücke) × ``factor``, auf 4–100 pt begrenzt.
 
diff --git a/src/labelwerk/render.py b/src/labelwerk/render.py
index d003f91..7c3cc1f 100644
--- a/src/labelwerk/render.py
+++ b/src/labelwerk/render.py
@@ -102,11 +102,20 @@ def render_document(doc: Document, model: str = "QL-600") -> Image.Image:
     sheet = _sheet(doc, model)
     preps = [_prepare(obj, sheet) for obj in doc.objects or [TextObject("")]]
     width, height = _label_size(sheet, preps)
-    img = Image.new("RGB", (width, height), "white")
-    for prep in preps:
-        rendered = _finish(prep, sheet, width, height)
-        img.paste((0, 0, 0), (rendered.x, rendered.y), ImageOps.invert(rendered.image))
-    return img.rotate(-90, expand=True) if sheet.horizontal else img
+    return compose([_finish(prep, sheet, width, height) for prep in preps], (width, height),
+                   doc.orientation)
+
+
+def compose(rendered: list[RenderedObject], size: tuple[int, int],
+            orientation: str = "vertical") -> Image.Image:
+    """Druckbild aus einzeln gerenderten Objekten (``size`` = Etikett in Leserichtung).
+
+    Die Arbeitsfläche zeigt dieselben Objektbilder – so bleibt Vorschau = Druck.
+    """
+    img = Image.new("RGB", size, "white")
+    for obj in rendered:
+        img.paste((0, 0, 0), (obj.x, obj.y), ImageOps.invert(obj.image))
+    return img.rotate(-90, expand=True) if orientation == "horizontal" else img
 
 
 def label_size(doc: Document, model: str = "QL-600") -> tuple[int, int]:
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `505 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/actions.py src/labelwerk/gui/canvas.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/text.py src/labelwerk/layout.py src/labelwerk/render.py tests/gui/test_gui_actions.py tests/gui/test_gui_canvas.py tests/gui/test_gui_papier.py tests/gui/test_gui_placement.py tests/test_layout.py tests/test_placement_render.py
git commit -m "GUI: Objekte auf der Arbeitsfläche – Auswahl, Ziehen, Einrasten, Anfasser, Tastatur

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: GUI – Bearbeitungsleiste: Text anlegen, Zwischenablage, Rückgängig

**Files:**
- Modify: `src/labelwerk/gui/canvas.py`
- Create: `src/labelwerk/gui/history.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/__init__.py`
- Modify: `src/labelwerk/gui/panels/paper.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Create: `tests/gui/test_gui_editbar.py`
- Create: `tests/gui/test_gui_history.py`

**Interfaces / Produces:** `gui/history.py`: `History(doc)` mit `push(doc, merge=None)`, `undo(current)`, `redo(current)`, `can_undo`, `can_redo`, `reset`, Signal `changed`, höchstens 100 Schritte, `restore(target, snapshot)`; Canvas `tool()/set_tool()`, `tool_changed`, `text_requested(x_mm, y_mm)`, `edit_requested(i)`; MainWindow `create_text`, `edit_text`, `copy_selected`, `cut_selected`, `paste`, `duplicate_selected`, `nudge`, `undo`, `redo`, `edit_bar`; `Panel.edited`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_editbar.py b/tests/gui/test_gui_editbar.py
new file mode 100644
index 0000000..0ef6f2c
--- /dev/null
+++ b/tests/gui/test_gui_editbar.py
@@ -0,0 +1,400 @@
+"""Bearbeitungsleiste: Text anlegen, Zwischenablage, Rückgängig (Etappe 3d-1)."""
+import pytest
+from PySide6.QtCore import QPointF, Qt
+from PySide6.QtGui import QMouseEvent
+from PySide6.QtTest import QTest
+from PySide6.QtWidgets import QApplication, QToolBar
+
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.canvas import MM
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.settings import Settings
+
+NO_MOD = Qt.KeyboardModifier.NoModifier
+ALT = Qt.KeyboardModifier.AltModifier
+CTRL = Qt.KeyboardModifier.ControlModifier
+SHIFT = Qt.KeyboardModifier.ShiftModifier
+LEFT = Qt.MouseButton.LeftButton
+
+
+def _doc(orientation="vertical"):
+    return Document("62", length_mm=40, orientation=orientation, objects=[
+        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
+        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=20)])
+
+
+def _window(qtbot, doc=None, settings=None):
+    win = MainWindow(doc=doc if doc is not None else _doc(),
+                     settings=settings or Settings(check_media_on_start=False))
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
+def _drag(canvas, start, end, modifiers=ALT):
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT, modifiers)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, modifiers)
+
+
+def _view_point(canvas, x_mm, y_mm):
+    """Punkt in mm in Leserichtung → Ansichtskoordinaten."""
+    scene = canvas.sheet.mapToScene(QPointF(x_mm * MM, y_mm * MM))
+    return canvas.viewportTransform().map(scene)
+
+
+def _focus_canvas(window, qtbot):
+    window.activateWindow()
+    window.canvas.setFocus()
+    qtbot.waitUntil(lambda: window.canvas.hasFocus(), timeout=1000)
+
+
+def _positions(window):
+    return [(o.x_mm, o.y_mm) for o in window.doc.objects]
+
+
+# --- Leiste -----------------------------------------------------------------------
+def test_edit_bar_holds_tools_clipboard_and_history(window):
+    bar = window.edit_bar
+    assert isinstance(bar, QToolBar) and bar.objectName() == "editBar"
+    ids = [a.objectName() if not a.isSeparator() else "|" for a in bar.actions()]
+    assert ids == ["tool.select", "tool.text", "|", "edit.cut", "edit.copy", "edit.paste",
+                   "|", "edit.undo", "edit.redo"]
+    assert window.toolBarBreak(bar)                         # eigene Zeile unter den Werkzeugen
+    assert "Ctrl+Z" in window.actions["edit.undo"].toolTip()
+    text_button = bar.widgetForAction(window.actions["tool.text"])
+    assert text_button.text() == "A"
+
+
+def test_tool_modes_are_exclusive(window):
+    select, text = window.actions["tool.select"], window.actions["tool.text"]
+    assert select.isChecked() and not text.isChecked()
+    assert window.canvas.tool() == "select"
+    text.trigger()
+    assert window.canvas.tool() == "text" and text.isChecked() and not select.isChecked()
+    select.trigger()
+    assert window.canvas.tool() == "select" and select.isChecked()
+
+
+def test_t_and_esc_switch_tool_on_canvas(window, qtbot):
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_T)
+    assert window.canvas.tool() == "text" and window.actions["tool.text"].isChecked()
+    QTest.keyClick(window.canvas, Qt.Key.Key_Escape)
+    assert window.canvas.tool() == "select" and window.actions["tool.select"].isChecked()
+
+
+def test_clipboard_actions_follow_selection(window):
+    for key in ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete"):
+        assert not window.actions[key].isEnabled()
+    assert not window.actions["edit.paste"].isEnabled()
+    window.canvas.set_selection([0])
+    for key in ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete"):
+        assert window.actions[key].isEnabled()
+    window.actions["edit.copy"].trigger()
+    assert window.actions["edit.paste"].isEnabled()
+
+
+# --- Text anlegen -----------------------------------------------------------------
+@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
+def test_click_with_text_tool_creates_text_at_click_point(qtbot, orientation):
+    win = _window(qtbot, _doc(orientation))
+    win.actions["tool.text"].trigger()
+    _click(win.canvas, _view_point(win.canvas, 30, 12))
+    assert len(win.doc.objects) == 3
+    obj = win.doc.objects[2]
+    assert obj.is_empty() and not obj.fit
+    assert (obj.x_mm, obj.y_mm) == pytest.approx((30, 12), abs=0.1)
+    assert win.canvas.selection() == [2]
+    assert win.canvas.tool() == "select" and win.actions["tool.select"].isChecked()
+    assert win.panels.currentWidget() is win.panel("text")
+    qtbot.waitUntil(lambda: win.panel("text").edit.hasFocus(), timeout=1000)
+
+
+def test_new_text_uses_font_from_settings(qtbot):
+    win = _window(qtbot, settings=Settings(check_media_on_start=False, font_size_pt=24,
+                                           font_family="DejaVu Serif"))
+    win.create_text(10, 5)
+    obj = win.doc.objects[-1]
+    assert obj.size_pt == 24
+    assert obj.paragraphs[0].spans[0].family == "DejaVu Serif"
+
+
+def test_new_text_with_automatic_size_setting_gets_19_pt(qtbot):
+    win = _window(qtbot, settings=Settings(check_media_on_start=False, font_size_pt=None))
+    win.create_text(10, 5)
+    obj = win.doc.objects[-1]
+    assert obj.size_pt == 19 and obj.paragraphs[0].spans[0].family is None
+
+
+def test_new_empty_text_is_selected_with_a_visible_frame(window):
+    window.create_text(30, 12)
+    rect = window.canvas.view_rect(2)
+    assert rect.width() > 0 and rect.height() > 0      # Platzhalter, bis Text da ist
+    point = _view_point(window.canvas, 30, 12)
+    assert rect.topLeft().x() == pytest.approx(point.x(), abs=1)
+    assert rect.topLeft().y() == pytest.approx(point.y(), abs=1)
+
+
+def test_creating_text_removes_other_empty_texts(qtbot):
+    doc = _doc()
+    doc.objects.append(TextObject(""))
+    win = _window(qtbot, doc)
+    win.create_text(30, 12)
+    assert [o.text for o in win.doc.objects] == ["Eins", "Zwei", ""]
+    assert win.doc.objects[2].positioned and win.canvas.selection() == [2]
+
+
+def test_click_outside_label_with_text_tool_creates_nothing(window):
+    window.actions["tool.text"].trigger()
+    label = window.canvas.label_view_rect()
+    _click(window.canvas, label.bottomRight() + QPointF(20, 20))
+    assert len(window.doc.objects) == 2
+    assert window.canvas.tool() == "text"
+
+
+def test_click_on_object_with_text_tool_selects_it(window, qtbot):
+    window.actions["tool.text"].trigger()
+    _click(window.canvas, window.canvas.view_rect(1).center())
+    assert len(window.doc.objects) == 2
+    assert window.canvas.selection() == [1] and window.canvas.tool() == "select"
+    qtbot.waitUntil(lambda: window.panel("text").edit.hasFocus(), timeout=1000)
+
+
+def test_double_click_on_text_focuses_editor(window, qtbot):
+    window.tool_actions["paper"].trigger()
+    _double_click(window.canvas, window.canvas.view_rect(1).center())
+    assert window.canvas.selection() == [1]
+    assert window.panels.currentWidget() is window.panel("text")
+    qtbot.waitUntil(lambda: window.panel("text").edit.hasFocus(), timeout=1000)
+
+
+# --- Zwischenablage ---------------------------------------------------------------
+def test_copy_paste_offsets_by_2_mm_each_time(window, qtbot):
+    window.canvas.set_selection([1])
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_C, CTRL)
+    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Zwei"]
+    assert _positions(window)[2] == pytest.approx((6, 22))
+    assert window.canvas.selection() == [2]
+    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
+    assert _positions(window)[3] == pytest.approx((8, 24))
+    assert window.canvas.selection() == [3]
+    assert window.doc.objects[1].x_mm == 4                   # Original bleibt
+
+
+def test_paste_keeps_order_and_copies_are_independent(window):
+    window.canvas.set_selection([1, 0])
+    window.actions["edit.copy"].trigger()
+    window.doc.objects[0] = TextObject("geändert", size_pt=14, x_mm=4, y_mm=4)
+    window.actions["edit.paste"].trigger()
+    assert [o.text for o in window.doc.objects] == ["geändert", "Zwei", "Eins", "Zwei"]
+    assert window.canvas.selection() == [2, 3]
+
+
+def test_copy_of_centered_text_pastes_next_to_it(qtbot):
+    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Mitte")]))
+    shown = win.canvas.objects[0].frame_mm()
+    win.canvas.set_selection([0])
+    win.actions["edit.copy"].trigger()
+    win.actions["edit.paste"].trigger()
+    pasted = win.doc.objects[1]
+    assert pasted.positioned and pasted.size_pt is not None
+    assert (pasted.x_mm, pasted.y_mm) == pytest.approx((shown.x + 2, shown.y + 2), abs=0.01)
+    assert not win.doc.objects[0].positioned
+
+
+def test_cut_removes_and_paste_brings_back(window, qtbot):
+    window.canvas.set_selection([0])
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_X, CTRL)
+    assert [o.text for o in window.doc.objects] == ["Zwei"]
+    assert window.canvas.selection() == []
+    QTest.keyClick(window.canvas, Qt.Key.Key_V, CTRL)
+    assert [o.text for o in window.doc.objects] == ["Zwei", "Eins"]
+    assert _positions(window)[1] == pytest.approx((6, 6))
+
+
+def test_duplicate_leaves_clipboard_alone(window, qtbot):
+    window.canvas.set_selection([0])
+    window.actions["edit.copy"].trigger()
+    window.canvas.set_selection([1])
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_D, CTRL)
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Zwei"]
+    assert _positions(window)[2] == pytest.approx((6, 22))
+    assert window.canvas.selection() == [2]
+    window.actions["edit.paste"].trigger()
+    assert window.doc.objects[3].text == "Eins"
+
+
+# --- Rückgängig -------------------------------------------------------------------
+def _undo(window):
+    window.actions["edit.undo"].trigger()
+
+
+def _redo(window):
+    window.actions["edit.redo"].trigger()
+
+
+def test_undo_redo_drag(window):
+    start = window.canvas.view_rect(0).center()
+    _drag(window.canvas, start, start + QPointF(40, 0))
+    moved = window.doc.objects[0].x_mm
+    assert moved > 4
+    _undo(window)
+    assert window.doc.objects[0].x_mm == 4
+    assert window.canvas.objects[0].frame_mm().x == pytest.approx(
+        window.canvas.objects[1].frame_mm().x)           # Arbeitsfläche folgt
+    _redo(window)
+    assert window.doc.objects[0].x_mm == moved
+
+
+def test_undo_resize(window):
+    window.canvas.set_selection([0])
+    edge = window.canvas.handle_points(0)["r"]
+    _drag(window.canvas, edge, edge + QPointF(10 * window.canvas.px_per_mm(), 0), NO_MOD)
+    assert window.doc.objects[0].fit
+    _undo(window)
+    assert not window.doc.objects[0].fit and window.doc.objects[0].w_mm is None
+
+
+def test_consecutive_nudges_are_one_step(window, qtbot):
+    window.canvas.set_selection([1])
+    _focus_canvas(window, qtbot)
+    for _ in range(3):
+        QTest.keyClick(window.canvas, Qt.Key.Key_Right)
+    assert window.doc.objects[1].x_mm == pytest.approx(4.3)
+    QTest.keyClick(window.canvas, Qt.Key.Key_Z, CTRL)
+    assert window.doc.objects[1].x_mm == 4
+    QTest.keyClick(window.canvas, Qt.Key.Key_Z, CTRL | SHIFT)
+    assert window.doc.objects[1].x_mm == pytest.approx(4.3)
+
+
+def test_undo_create_delete_paste_duplicate(window):
+    steps = []
+    window.create_text(30, 12)
+    steps.append(3)
+    window.canvas.set_selection([0])
+    window.delete_selected()
+    steps.append(2)
+    window.canvas.set_selection([0])
+    window.actions["edit.copy"].trigger()
+    window.actions["edit.paste"].trigger()
+    steps.append(3)
+    window.actions["edit.duplicate"].trigger()
+    steps.append(4)
+    counts = []
+    for _ in steps:
+        counts.append(len(window.doc.objects))
+        _undo(window)
+    assert counts == list(reversed(steps))
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
+    assert not window.actions["edit.undo"].isEnabled()
+    _redo(window)
+    assert len(window.doc.objects) == 3 and window.actions["edit.redo"].isEnabled()
+
+
+def test_undo_cut(window):
+    window.canvas.set_selection([0])
+    window.actions["edit.cut"].trigger()
+    _undo(window)
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei"]
+
+
+def test_typing_is_one_step_when_editor_loses_focus(window, qtbot):
+    window.canvas.set_selection([0])
+    editor = window.panel("text").edit
+    window.activateWindow()
+    editor.setFocus()
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    QTest.keyClicks(editor, " und mehr")
+    _focus_canvas(window, qtbot)                            # Fokus verlässt das Textfeld
+    assert window.doc.objects[0].text == "Eins und mehr"
+    _undo(window)
+    assert window.doc.objects[0].text == "Eins"
+    assert editor.toPlainText() == "Eins"                   # Panel folgt
+    _redo(window)
+    assert editor.toPlainText() == "Eins und mehr"
+
+
+def test_format_button_is_its_own_step(window):
+    window.canvas.set_selection([0])
+    panel = window.panel("text")
+    panel.edit.setPlainText("Eins!")                        # Tippen, noch nicht festgehalten
+    panel.italic.click()
+    _undo(window)
+    assert window.doc.objects[0].text == "Eins!"
+    assert not window.doc.objects[0].paragraphs[0].spans[0].italic
+    _undo(window)
+    assert window.doc.objects[0].text == "Eins"
+
+
+def test_undo_button_is_enabled_by_pending_typing(window):
+    window.canvas.set_selection([0])
+    assert not window.actions["edit.undo"].isEnabled()
+    window.panel("text").edit.setPlainText("Neu")
+    assert window.actions["edit.undo"].isEnabled()
+    _undo(window)
+    assert window.doc.objects[0].text == "Eins"
+
+
+def test_paper_change_is_undoable(window):
+    paper = window.panel("paper")
+    paper.combo.setCurrentIndex(paper.combo.findData("62x29"))
+    assert window.doc.label_id == "62x29"
+    _undo(window)
+    assert window.doc.label_id == "62"
+    assert paper.combo.currentData() == "62"
+
+
+def test_ctrl_z_in_editor_uses_editor_undo(window, qtbot):
+    window.canvas.set_selection([0])
+    window.canvas.nudge(1, 0)                               # Schritt im Dokument
+    editor = window.panel("text").edit
+    window.activateWindow()
+    editor.setFocus()
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    editor.moveCursor(editor.textCursor().MoveOperation.End)
+    QTest.keyClicks(editor, "X")
+    assert window.doc.objects[0].text == "EinsX"
+    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
+    assert window.doc.objects[0].text == "Eins"             # Editor hat rückgängig gemacht
+    assert window.doc.objects[0].x_mm == pytest.approx(5)   # Dokument nicht
+    QTest.keyClick(editor, Qt.Key.Key_Z, CTRL)
+    assert editor.toPlainText() == "Eins"                   # Aufbau des Editors ist kein Schritt
+
+
+def test_undo_keeps_valid_selection(window):
+    window.canvas.set_selection([1])
+    window.canvas.nudge(1, 0)
+    _undo(window)
+    assert window.canvas.selection() == [1]
+    window.create_text(30, 12)
+    _undo(window)
+    assert window.canvas.selection() == []
diff --git a/tests/gui/test_gui_history.py b/tests/gui/test_gui_history.py
new file mode 100644
index 0000000..a65fadf
--- /dev/null
+++ b/tests/gui/test_gui_history.py
@@ -0,0 +1,130 @@
+"""Rückgängig/Wiederherstellen: Dokument-Schnappschüsse (Etappe 3d-1)."""
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.history import LIMIT, History, restore
+
+
+def _doc(text="A"):
+    return Document("62", objects=[TextObject(text)])
+
+
+def _texts(doc):
+    return [obj.text for obj in doc.objects]
+
+
+def test_undo_and_redo_step_through_pushed_states():
+    doc = _doc("A")
+    history = History(doc)
+    assert not history.can_undo() and not history.can_redo()
+    doc.objects[0] = TextObject("B")
+    history.push(doc)
+    doc.objects[0] = TextObject("C")
+    history.push(doc)
+    assert history.can_undo() and not history.can_redo()
+    assert _texts(history.undo(doc)) == ["B"]
+    assert _texts(history.undo(_doc("B"))) == ["A"]
+    assert history.undo(_doc("A")) is None
+    assert history.can_redo()
+    assert _texts(history.redo(_doc("A"))) == ["B"]
+    assert _texts(history.redo(_doc("B"))) == ["C"]
+    assert history.redo(_doc("C")) is None
+
+
+def test_push_without_change_is_no_step():
+    doc = _doc()
+    history = History(doc)
+    assert history.push(doc) is False
+    assert not history.can_undo()
+
+
+def test_undo_commits_pending_changes_first():
+    """Noch nicht festgehaltene Änderungen (z. B. Tippen) werden selbst ein Schritt."""
+    doc = _doc("A")
+    history = History(doc)
+    doc.objects[0] = TextObject("A getippt")
+    assert history.can_undo(doc) and not history.can_undo()
+    assert _texts(history.undo(doc)) == ["A"]
+    assert _texts(history.redo(_doc("A"))) == ["A getippt"]
+
+
+def test_new_change_after_undo_discards_redo():
+    doc = _doc("A")
+    history = History(doc)
+    history.push(_doc("B"))
+    history.undo(_doc("B"))
+    history.push(_doc("C"))
+    assert not history.can_redo()
+    assert history.redo(_doc("C")) is None
+    assert _texts(history.undo(_doc("C"))) == ["A"]
+
+
+def test_pending_change_blocks_redo():
+    history = History(_doc("A"))
+    history.push(_doc("B"))
+    history.undo(_doc("B"))
+    assert history.can_redo(_doc("A"))
+    assert not history.can_redo(_doc("A neu"))
+    assert history.redo(_doc("A neu")) is None
+
+
+def test_history_keeps_at_most_limit_steps():
+    history = History(_doc("0"))
+    for i in range(1, LIMIT + 11):
+        history.push(_doc(str(i)))
+    steps = 0
+    current = _doc(str(LIMIT + 10))
+    while (previous := history.undo(current)) is not None:
+        current = previous
+        steps += 1
+    assert LIMIT == 100 and steps == LIMIT
+    assert _texts(current) == ["10"]
+
+
+def test_consecutive_pushes_with_same_merge_key_form_one_step():
+    history = History(_doc("A"))
+    history.push(_doc("B"), merge="nudge")
+    history.push(_doc("C"), merge="nudge")
+    history.push(_doc("D"), merge="nudge")
+    assert _texts(history.undo(_doc("D"))) == ["A"]
+    history.redo(_doc("A"))
+    history.push(_doc("E"), merge="nudge")       # nach Rückgängig/Wiederherstellen: neuer Schritt
+    assert _texts(history.undo(_doc("E"))) == ["D"]
+
+
+def test_different_merge_key_starts_new_step():
+    history = History(_doc("A"))
+    history.push(_doc("B"), merge=("nudge", (0,)))
+    history.push(_doc("C"), merge=("nudge", (1,)))
+    assert _texts(history.undo(_doc("C"))) == ["B"]
+
+
+def test_snapshots_are_independent_copies():
+    doc = _doc("A")
+    history = History(doc)
+    doc.objects[0].paragraphs[0].spans[0].text = "verändert"   # Original nach dem Schnappschuss
+    history.push(doc)
+    restored = history.undo(doc)
+    assert _texts(restored) == ["A"]
+    restored.objects[0].paragraphs[0].spans[0].text = "kaputt"     # Kopie, nicht der Verlauf
+    assert _texts(history.redo(_doc("A"))) == ["verändert"]
+    assert _texts(history.undo(_doc("verändert"))) == ["A"]
+
+
+def test_changed_signal_reports_every_change(qtbot):
+    history = History(_doc("A"))
+    with qtbot.waitSignal(history.changed, timeout=100):
+        history.push(_doc("B"))
+    with qtbot.waitSignal(history.changed, timeout=100):
+        history.undo(_doc("B"))
+    with qtbot.waitSignal(history.changed, timeout=100):
+        history.reset(_doc("X"))
+    assert not history.can_undo() and not history.can_redo()
+
+
+def test_restore_keeps_the_document_object():
+    """Panels halten das Dokument fest – Rückgängig ändert es an Ort und Stelle."""
+    doc = Document("62", length_mm=40, objects=[TextObject("A")])
+    snapshot = Document("29", orientation="horizontal", margin_mm=3,
+                        objects=[TextObject("B"), TextObject("C")])
+    restore(doc, snapshot)
+    assert doc == snapshot and doc is not snapshot
+    assert (doc.label_id, doc.length_mm, doc.orientation) == ("29", None, "horizontal")
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index 606c9f4..d815536 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -1,5 +1,5 @@
 """Arbeitsfläche: Etikett in echter Größe und Form, Objekte (auswählen, ziehen, einrasten,
-an Anfassern skalieren), mm-Lineale, Zoom, Längen-Anfasser."""
+an Anfassern skalieren, Text anlegen), mm-Lineale, Zoom, Längen-Anfasser."""
 from __future__ import annotations
 
 import math
@@ -14,7 +14,7 @@ from .. import layout
 from ..labels import DPI, Label, format_mm, length_limits
 from ..layout import Rect
 from ..printer import DEFAULT_MODEL
-from ..render import RenderedObject
+from ..render import PT, RenderedObject
 
 MM = DPI / 25.4          # Szene-Einheiten (Druckpunkte) pro mm
 RULER = 22               # Linealbreite in Pixeln
@@ -33,6 +33,7 @@ _HANDLE_CURSORS = {
     "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
 }
 _GUIDE_COLOR = QColor("#E53935")
+TOOL_MODES = ("select", "text")   # Auswahl-Pfeil, „Text anlegen“
 
 
 def to_qimage(img: Image.Image) -> QImage:
@@ -65,9 +66,16 @@ class ObjectItem(QGraphicsPixmapItem):
     def is_empty(self) -> bool:
         return self.rendered.w == 0 or self.rendered.h == 0
 
+    def size(self) -> tuple[float, float]:
+        """Rahmengröße in Druckpunkten; ein leerer Text zeigt einen Platzhalter (eine Zeile hoch)."""
+        if self.is_empty():
+            line = self.rendered.base_pt * PT
+            return line / 2, line
+        return self.rendered.w, self.rendered.h
+
     def frame(self) -> QRectF:
         """Rahmen in Druckpunkten in Leserichtung (beim Ziehen samt Vorschau-Streckung)."""
-        return self.mapRectToParent(QRectF(0, 0, self.rendered.w, self.rendered.h))
+        return self.mapRectToParent(QRectF(0, 0, *self.size()))
 
     def frame_mm(self) -> Rect:
         f = self.frame()
@@ -81,6 +89,9 @@ class Canvas(QGraphicsView):
     selection_changed = Signal(list)  # Indizes der ausgewählten Objekte in der Reihenfolge der Wahl
     objects_moved = Signal(list, list)         # Indizes, neue Rahmen (Rect, mm) nach dem Loslassen
     object_resized = Signal(int, object, str)  # Index, neuer Rahmen (Rect, mm), Anfasser („tl“ …)
+    text_requested = Signal(float, float)      # „Text anlegen“: Klick aufs Etikett (mm, Leserichtung)
+    edit_requested = Signal(int)               # Text eines Objekts bearbeiten (Doppelklick)
+    tool_changed = Signal(str)                 # Werkzeug: "select" | "text"
 
     def __init__(self, model: str = DEFAULT_MODEL):
         super().__init__()
@@ -115,6 +126,7 @@ class Canvas(QGraphicsView):
         self._start_frame = QRectF()
         self._handle_offset = QPointF()
         self._handle_cursor = False
+        self._tool = "select"
         self._apply_zoom()
 
     # --- Inhalt -----------------------------------------------------------
@@ -206,7 +218,7 @@ class Canvas(QGraphicsView):
         self.set_selection(list(range(len(self.objects))))
 
     def _selectable(self, index: int) -> bool:
-        return 0 <= index < len(self.objects) and not self.objects[index].is_empty()
+        return 0 <= index < len(self.objects)
 
     def nudge(self, dx_mm: float, dy_mm: float) -> None:
         """Ausgewählte Objekte um dx/dy mm verschieben (Pfeiltasten)."""
@@ -214,6 +226,37 @@ class Canvas(QGraphicsView):
             frames = [self.objects[i].frame_mm().moved(dx_mm, dy_mm) for i in self._selection]
             self.objects_moved.emit(self.selection(), frames)
 
+    # --- Werkzeug ---------------------------------------------------------
+    def tool(self) -> str:
+        return self._tool
+
+    def set_tool(self, tool: str) -> None:
+        """Werkzeug wählen: Auswahl-Pfeil oder „Text anlegen“ (Klick aufs Etikett legt Text an)."""
+        if tool not in TOOL_MODES:
+            raise ValueError(f"Unbekanntes Werkzeug {tool!r}")
+        if tool != self._tool:
+            self._tool = tool
+            if tool == "text":
+                self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
+            else:
+                self.viewport().unsetCursor()
+            self.tool_changed.emit(tool)
+
+    def _create_text(self, pos: QPointF) -> None:
+        """„Text anlegen“: Klick auf ein Objekt wählt es, Klick aufs Etikett legt dort Text an."""
+        item = self._object_at(pos)
+        if item is not None:
+            self.set_selection([item.index])
+            self.set_tool("select")
+            self.edit_requested.emit(item.index)
+            return
+        point = self._reading(pos)
+        x, y = point.x() / MM, point.y() / MM
+        label = self._label_rect
+        if label.x <= x <= label.right and label.y <= y <= label.bottom:
+            self.set_tool("select")
+            self.text_requested.emit(x, y)
+
     # --- Geometrie --------------------------------------------------------
     def px_per_mm(self) -> float:
         """Bildschirmpixel je mm beim aktuellen Zoom."""
@@ -253,6 +296,8 @@ class Canvas(QGraphicsView):
     def _handle_at(self, pos: QPointF) -> tuple[int, str] | None:
         reach = HANDLE_PX / 2 + 1
         for index in reversed(self._selection):            # zuletzt gewähltes zuerst
+            if self.objects[index].is_empty():
+                continue                                   # Platzhalter hat keine Anfasser
             for key, point in self.handle_points(index).items():
                 if abs(point.x() - pos.x()) <= reach and abs(point.y() - pos.y()) <= reach:
                     return index, key
@@ -312,6 +357,9 @@ class Canvas(QGraphicsView):
             return
         if self.sheet is None:
             return
+        if self._tool == "text":
+            self._create_text(pos)
+            return
         hit = self._handle_at(pos)
         if hit is not None:
             self._begin_resize(*hit, pos)
@@ -366,10 +414,12 @@ class Canvas(QGraphicsView):
         hit = self._handle_at(pos) if self.sheet is not None else None
         if self._handle_cursor and hit is None:
             self.viewport().unsetCursor()
+            if self._tool == "text":
+                self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
         super().mouseMoveEvent(event)
-        if hit is not None:                                # Anfasser zeigt seine Richtung
+        if hit is not None and self._tool == "select":     # Anfasser zeigt seine Richtung
             self.viewport().setCursor(_HANDLE_CURSORS[hit[1]])
-        self._handle_cursor = hit is not None
+        self._handle_cursor = hit is not None and self._tool == "select"
 
     def _drag_move(self, pos: QPointF, snapping: bool) -> None:
         """Ausgewählte Bilder verschieben (Modell erst beim Loslassen), dabei einrasten."""
@@ -388,8 +438,8 @@ class Canvas(QGraphicsView):
             self.objects[index].setPos(start + delta)
 
     def _start_rect(self, index: int) -> Rect:
-        start, rendered = self._start[index], self.objects[index].rendered
-        return Rect(start.x() / MM, start.y() / MM, rendered.w / MM, rendered.h / MM)
+        start, (w, h) = self._start[index], self.objects[index].size()
+        return Rect(start.x() / MM, start.y() / MM, w / MM, h / MM)
 
     def _drag_resize(self, pos: QPointF) -> None:
         """Vorschau beim Ziehen an einem Anfasser: Bild gestreckt, gerendert wird beim Loslassen."""
@@ -430,6 +480,11 @@ class Canvas(QGraphicsView):
         if self._on_handle(event):
             self.length_changed.emit(None)
             return
+        item = self._object_at(event.position()) if self.sheet is not None else None
+        if item is not None and event.button() == Qt.MouseButton.LeftButton:
+            self.set_selection([item.index])
+            self.edit_requested.emit(item.index)
+            return
         super().mouseDoubleClickEvent(event)
 
     def label_height(self) -> float:
@@ -462,6 +517,8 @@ class Canvas(QGraphicsView):
             painter.setPen(frame)
             painter.setBrush(Qt.BrushStyle.NoBrush)
             painter.drawRect(self.view_rect(index))
+            if self.objects[index].is_empty():
+                continue                                   # leerer Text: nur der Platzhalter
             painter.setPen(border)
             painter.setBrush(Qt.GlobalColor.white)
             for point in self.handle_points(index).values():
diff --git a/src/labelwerk/gui/history.py b/src/labelwerk/gui/history.py
new file mode 100644
index 0000000..c396eb3
--- /dev/null
+++ b/src/labelwerk/gui/history.py
@@ -0,0 +1,94 @@
+"""Rückgängig/Wiederherstellen über Dokument-Schnappschüsse (``copy.deepcopy``).
+
+Nach jeder abgeschlossenen Aktion hält das Hauptfenster den Stand mit ``push`` fest.
+Änderungen, die noch nicht festgehalten sind (z. B. Tippen im Textfeld, das erst beim
+Verlassen des Felds ein Schritt wird), macht ``undo`` vorher selbst zu einem Schritt.
+"""
+from __future__ import annotations
+
+import copy
+from dataclasses import fields
+from typing import Hashable
+
+from PySide6.QtCore import QObject, Signal
+
+from ..document import Document
+
+LIMIT = 100   # höchstens so viele Schritte zurück
+
+
+class History(QObject):
+    changed = Signal()   # Rückgängig/Wiederherstellen ggf. jetzt (nicht mehr) möglich
+
+    def __init__(self, doc: Document, limit: int = LIMIT):
+        super().__init__()
+        self.limit = limit
+        self.reset(doc)
+
+    def reset(self, doc: Document) -> None:
+        """Neuer Ausgangsstand (z. B. neues oder geöffnetes Etikett) – ohne Schritte."""
+        self._states = [copy.deepcopy(doc)]
+        self._pos = 0
+        self._merge: Hashable | None = None
+        self.changed.emit()
+
+    def push(self, doc: Document, merge: Hashable | None = None) -> bool:
+        """Stand nach einer Aktion festhalten; False, wenn sich nichts geändert hat.
+
+        Aufeinanderfolgende Schritte mit gleichem ``merge`` (z. B. Pfeiltasten auf dieselbe
+        Auswahl) werden zu einem Schritt zusammengefasst.
+        """
+        if doc == self._states[self._pos]:
+            return False
+        snapshot = copy.deepcopy(doc)
+        if (merge is not None and merge == self._merge and self._pos > 0
+                and self._pos == len(self._states) - 1):
+            self._states[self._pos] = snapshot
+        else:
+            del self._states[self._pos + 1:]        # Wiederherstellen verfällt
+            self._states.append(snapshot)
+            del self._states[:-(self.limit + 1)]
+            self._pos = len(self._states) - 1
+        self._merge = merge
+        self.changed.emit()
+        return True
+
+    def can_undo(self, current: Document | None = None) -> bool:
+        return self._pos > 0 or self._pending(current)
+
+    def can_redo(self, current: Document | None = None) -> bool:
+        return self._pos < len(self._states) - 1 and not self._pending(current)
+
+    def undo(self, current: Document) -> Document | None:
+        """Stand vor dem letzten Schritt (Kopie) oder None; ``current`` = Dokument jetzt."""
+        self.push(current)
+        if self._pos == 0:
+            return None
+        return self._step(-1)
+
+    def redo(self, current: Document) -> Document | None:
+        """Rückgängig gemachten Schritt wiederholen (Kopie) oder None.
+
+        Hat sich ``current`` seitdem geändert, ist das ein neuer Schritt – nichts mehr zu
+        wiederholen."""
+        self.push(current)
+        if self._pos == len(self._states) - 1:
+            return None
+        return self._step(+1)
+
+    def _step(self, direction: int) -> Document:
+        self._pos += direction
+        self._merge = None
+        self.changed.emit()
+        return copy.deepcopy(self._states[self._pos])
+
+    def _pending(self, current: Document | None) -> bool:
+        return current is not None and current != self._states[self._pos]
+
+
+def restore(target: Document, snapshot: Document) -> None:
+    """``target`` an Ort und Stelle auf den Stand von ``snapshot`` setzen.
+
+    Panels halten das Dokument-Objekt fest; es wird deshalb nicht ersetzt."""
+    for f in fields(Document):
+        setattr(target, f.name, copy.deepcopy(getattr(snapshot, f.name)))
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 20c86ec..ba4a453 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -1,4 +1,4 @@
-"""Hauptfenster: Werkzeugleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
+"""Hauptfenster: Werkzeugleiste, Bearbeitungsleiste, Panel-Stapel, Arbeitsfläche, Statusleiste."""
 from __future__ import annotations
 
 import copy
@@ -13,15 +13,18 @@ from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QS
 from ..desktop import APP_NAME
 from ..detect import brother_busy, find_brother_lp
 from ..document import Document, TextObject
+from ..fonts import DEFAULT_FAMILY
 from ..labels import get_label
-from ..layout import Rect, move, objects_outside, printable_area, resize
+from ..layout import Rect, move, object_rect, objects_outside, printable_area, resize
 from ..printer import DEFAULT_MODEL
 from ..render import RenderedObject, compose, font_warnings, label_size, render_object
 from ..settings import Settings, load_settings, new_document
 from ..shortcuts import effective
 from .actions import apply_shortcuts, build_actions
 from .canvas import Canvas
+from .history import History, restore
 from .media_worker import MediaWorker
+from .panels.text import DEFAULT_PT
 from .print_worker import PrintWorker
 from .settings_dialog import SettingsDialog
 from .tools import TOOLS, Tool
@@ -32,6 +35,13 @@ PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugri
 NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
 _DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
 OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"
+PASTE_OFFSET_MM = 2.0      # Einfügen/Duplizieren: versetzt nach rechts und unten
+# Bearbeitungsleiste: Aktion, Symbol im Freedesktop-Theme, Text ohne Symbol; None = Trenner
+EDIT_BAR = (("tool.select", "edit-select", "↖"), ("tool.text", None, "A"), None,
+            ("edit.cut", "edit-cut", "AUSSCHNEIDEN"), ("edit.copy", "edit-copy", "KOPIEREN"),
+            ("edit.paste", "edit-paste", "EINFÜGEN"), None,
+            ("edit.undo", "edit-undo", "↶"), ("edit.redo", "edit-redo", "↷"))
+_SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
 
 
 @dataclass
@@ -62,6 +72,8 @@ class MainWindow(QMainWindow):
         self._printer_present = False
         self._printing = False
         self._media_check_pending = False
+        self._clipboard: list[TextObject] = []      # interne Zwischenablage (Kopien)
+        self._merge_next = None                     # Pfeiltasten: Schritte zusammenfassen
 
         # Werkzeugleiste + Panels aus der Registry
         toolbar = QToolBar("Werkzeuge")
@@ -77,6 +89,8 @@ class MainWindow(QMainWindow):
         for index, tool in enumerate(tools):
             panel = tool.panel(self.doc)
             panel.changed.connect(self.schedule_render)
+            panel.changed.connect(self._update_edit_actions)
+            panel.edited.connect(self._commit)
             self.panels.addWidget(panel)
             self._panel_by_key[tool.key] = panel
             action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
@@ -102,11 +116,17 @@ class MainWindow(QMainWindow):
         self.canvas.set_zoom(self.settings.start_zoom)
         self.apply_theme_icons()
         self.canvas.length_changed.connect(self._on_length_dragged)
-        self.canvas.drag_finished.connect(self.render_now)
+        self.canvas.drag_finished.connect(self._length_drag_finished)
         self.canvas.objects_moved.connect(self._move_objects)
         self.canvas.object_resized.connect(self._resize_object)
+        self.canvas.text_requested.connect(self.create_text)
+        self.canvas.edit_requested.connect(self.edit_text)
+        self.canvas.selection_changed.connect(self._update_edit_actions)
+        self.history = History(self.doc)
+        self.history.changed.connect(self._update_edit_actions)
         self.actions = build_actions(self, effective(self.settings.shortcuts))
         self._connect_canvas_actions()
+        self._build_edit_bar()
         central = QWidget()
         layout = QHBoxLayout(central)
         layout.setContentsMargins(0, 0, 0, 0)
@@ -147,6 +167,7 @@ class MainWindow(QMainWindow):
         self._printer_timer.start()
 
         self.render_now()
+        self._update_edit_actions()
         self.refresh_printer()
         if self.settings.warnings:
             self._set_result(" · ".join(self.settings.warnings), "error")
@@ -155,16 +176,70 @@ class MainWindow(QMainWindow):
         return self._panel_by_key[key]
 
     def _connect_canvas_actions(self) -> None:
-        """Kürzel der Arbeitsfläche: Pfeiltasten, Löschen, Alles auswählen."""
+        """Kürzel der Arbeitsfläche (Pfeiltasten, Zwischenablage, Werkzeug) und Rückgängig."""
         for direction, (sx, sy) in _DIRECTIONS.items():
             for suffix, step in NUDGE_MM.items():
                 action = self.actions[f"object.nudge_{direction}{suffix}"]
                 action.triggered.connect(
-                    lambda _=False, dx=sx * step, dy=sy * step: self.canvas.nudge(dx, dy))
+                    lambda _=False, dx=sx * step, dy=sy * step: self.nudge(dx, dy))
                 self.canvas.addAction(action)
-        self.actions["edit.delete"].triggered.connect(self.delete_selected)
-        self.actions["edit.select_all"].triggered.connect(self.canvas.select_all)
-        self.canvas.addActions([self.actions["edit.delete"], self.actions["edit.select_all"]])
+        handlers = {"edit.delete": self.delete_selected, "edit.select_all": self.canvas.select_all,
+                    "edit.cut": self.cut_selected, "edit.copy": self.copy_selected,
+                    "edit.paste": self.paste, "edit.duplicate": self.duplicate_selected,
+                    "tool.select": lambda: self.canvas.set_tool("select"),
+                    "tool.text": lambda: self.canvas.set_tool("text")}
+        for key, handler in handlers.items():
+            self.actions[key].triggered.connect(lambda _=False, h=handler: h())
+            self.canvas.addAction(self.actions[key])
+        # global: wirkt überall – außer im Textfeld, das Strg+Z selbst nutzt (eigenes Rückgängig)
+        self.actions["edit.undo"].triggered.connect(self.undo)
+        self.actions["edit.redo"].triggered.connect(self.redo)
+        self.addActions([self.actions["edit.undo"], self.actions["edit.redo"]])
+
+    def _build_edit_bar(self) -> None:
+        """Bearbeitungsleiste unter der Werkzeugleiste: Werkzeug, Zwischenablage, Rückgängig."""
+        bar = QToolBar("Bearbeiten")
+        bar.setObjectName("editBar")
+        bar.setMovable(False)
+        self.addToolBarBreak()
+        self.addToolBar(bar)
+        self.edit_bar = bar
+        modes = QActionGroup(self)                 # Auswahl-Pfeil oder „Text anlegen“
+        for key in ("tool.select", "tool.text"):
+            self.actions[key].setCheckable(True)
+            modes.addAction(self.actions[key])
+        self.actions["tool.select"].setChecked(True)
+        self.canvas.tool_changed.connect(lambda tool: self.actions[f"tool.{tool}"].setChecked(True))
+        for entry in EDIT_BAR:
+            if entry is None:
+                bar.addSeparator()
+                continue
+            key, icon_name, fallback = entry
+            action = self.actions[key]
+            icon = QIcon.fromTheme(icon_name) if icon_name else QIcon()
+            action.setIcon(icon)
+            action.setIconText(fallback)
+            bar.addAction(action)
+            button = bar.widgetForAction(action)
+            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly if icon.isNull()
+                                      else Qt.ToolButtonStyle.ToolButtonIconOnly)
+            if key == "tool.text":                 # „A“ wie im P-touch Editor, auch ohne Stylesheet
+                font = button.font()
+                font.setBold(True)
+                button.setFont(font)
+
+    def _show_tool(self, key: str) -> None:
+        """Panel eines Werkzeugs zeigen (wie ein Klick auf seinen Knopf)."""
+        self.tool_actions[key].setChecked(True)
+        self.panels.setCurrentWidget(self.panel(key))
+
+    def _update_edit_actions(self) -> None:
+        selected = bool(self.canvas.selection())
+        for key in _SELECTION_ACTIONS:
+            self.actions[key].setEnabled(selected)
+        self.actions["edit.paste"].setEnabled(bool(self._clipboard))
+        self.actions["edit.undo"].setEnabled(self.history.can_undo(self.doc))
+        self.actions["edit.redo"].setEnabled(self.history.can_redo(self.doc))
 
     # --- Rendern ----------------------------------------------------------
     def schedule_render(self) -> None:
@@ -220,30 +295,133 @@ class MainWindow(QMainWindow):
         self._cache = cache
         return [cache[id(obj)].rendered for obj in doc.objects]
 
+    # --- Rückgängig -------------------------------------------------------
+    def _commit(self, merge=None) -> None:
+        """Stand nach einer abgeschlossenen Aktion festhalten (ohne Änderung kein Schritt).
+
+        Vor jeder Aktion aufgerufen, wird noch nicht Festgehaltenes (Getipptes) ein eigener
+        Schritt. Tippen im Textfeld wird ein Schritt, sobald der Fokus das Feld verlässt."""
+        self.history.push(self.doc, merge)
+        self._update_edit_actions()
+
+    def undo(self) -> None:
+        self._restore(self.history.undo(self.doc))
+
+    def redo(self) -> None:
+        self._restore(self.history.redo(self.doc))
+
+    def _restore(self, snapshot: Document | None) -> None:
+        if snapshot is None:
+            return
+        restore(self.doc, snapshot)
+        for panel in self._panel_by_key.values():
+            panel.refresh()
+        self.render_now()                       # Auswahl bleibt, soweit es die Objekte noch gibt
+        self._update_edit_actions()
+
     # --- Objekte auf der Arbeitsfläche ------------------------------------
+    def nudge(self, dx_mm: float, dy_mm: float) -> None:
+        """Pfeiltasten: Auswahl verschieben; mehrere Schritte hintereinander = ein Rückgängig."""
+        self._merge_next = ("nudge", tuple(self.canvas.selection()))
+        try:
+            self.canvas.nudge(dx_mm, dy_mm)
+        finally:
+            self._merge_next = None
+
     def _move_objects(self, indices: list[int], rects: list[Rect]) -> None:
+        self._commit()
         for index, rect in zip(indices, rects):
             if index < len(self.rendered):
                 self.doc.objects[index] = move(self.doc.objects[index], rect, self.rendered[index])
         self._objects_changed(indices)
+        self._commit(self._merge_next)
 
     def _resize_object(self, index: int, rect: Rect, handle: str) -> None:
+        self._commit()
         if index < len(self.rendered):
             self.doc.objects[index] = resize(self.doc.objects[index], rect, self.rendered[index],
                                              corner=len(handle) == 2)
         self._objects_changed([index])
+        self._commit()
+
+    def create_text(self, x_mm: float, y_mm: float) -> None:
+        """Neuer leerer Textrahmen an x/y (mm, Leserichtung), ausgewählt, Schreibmarke ins Textfeld.
+
+        Schrift aus den Einstellungen (automatische Größe → 19 pt). Andere leere Texte sind
+        unsichtbar und drucken nicht – sie entfallen dabei."""
+        self._commit()
+        family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
+        obj = TextObject.plain("", size_pt=self.settings.font_size_pt or DEFAULT_PT, family=family)
+        obj.x_mm, obj.y_mm = round(x_mm, 1), round(y_mm, 1)
+        self.canvas.set_selection([])
+        self.doc.objects[:] = [o for o in self.doc.objects if not o.is_empty()]
+        self.doc.objects.append(obj)
+        index = len(self.doc.objects) - 1
+        self._objects_changed(list(range(len(self.doc.objects))))
+        self.canvas.set_selection([index])
+        self._commit()
+        self.edit_text(index)
+
+    def edit_text(self, index: int) -> None:
+        """Text eines Objekts bearbeiten: auswählen, Text-Panel zeigen, Schreibmarke hinein."""
+        if index not in self.canvas.selection():
+            self.canvas.set_selection([index])
+        self._show_tool("text")
+        self.panel("text").edit.setFocus()
 
     def delete_selected(self) -> None:
         """Ausgewählte Objekte löschen; ein leerer Text bleibt, damit das Text-Panel etwas hat."""
         indices = self.canvas.selection()
         if not indices:
             return
+        self._commit()
         self.canvas.set_selection([])
         for index in sorted(indices, reverse=True):
             del self.doc.objects[index]
         if not self.doc.objects:
             self.doc.objects.append(new_document(self.settings).objects[0])
         self._objects_changed([0])
+        self._commit()
+
+    # --- Zwischenablage ---------------------------------------------------
+    def copy_selected(self) -> None:
+        """Ausgewählte Objekte (in Zeichenreihenfolge) in die interne Zwischenablage kopieren."""
+        indices = sorted(self.canvas.selection())
+        if indices:
+            self._clipboard = [self._placed_copy(i) for i in indices]
+            self._update_edit_actions()
+
+    def cut_selected(self) -> None:
+        self.copy_selected()
+        self.delete_selected()
+
+    def paste(self) -> None:
+        """Zwischenablage einfügen – jedes Mal 2 mm weiter versetzt; Eingefügtes ist ausgewählt."""
+        if self._clipboard:
+            self._clipboard = [_offset(obj) for obj in self._clipboard]
+            self._insert(copy.deepcopy(self._clipboard))
+
+    def duplicate_selected(self) -> None:
+        """Auswahl 2 mm versetzt verdoppeln; die Zwischenablage bleibt unberührt."""
+        indices = sorted(self.canvas.selection())
+        if indices:
+            self._insert([_offset(self._placed_copy(i)) for i in indices])
+
+    def _placed_copy(self, index: int) -> TextObject:
+        """Kopie mit Position: ein mittiges Objekt bekommt seine Lage und Schriftgröße fest."""
+        obj = self.doc.objects[index]
+        if obj.positioned or index >= len(self.rendered):
+            return copy.deepcopy(obj)
+        rendered = self.rendered[index]
+        return move(obj, object_rect(rendered), rendered)
+
+    def _insert(self, objects: list[TextObject]) -> None:
+        self._commit()
+        start = len(self.doc.objects)
+        self.doc.objects.extend(objects)
+        self._objects_changed(list(range(start, len(self.doc.objects))))
+        self.canvas.set_selection(list(range(start, len(self.doc.objects))))
+        self._commit()
 
     def _objects_changed(self, indices: list[int]) -> None:
         if 0 in indices:
@@ -255,6 +433,11 @@ class MainWindow(QMainWindow):
         self.panel("paper").refresh()
         if not self.canvas.is_dragging():   # beim Ziehen erst nach dem Loslassen rendern
             self.schedule_render()
+            self._commit()                  # Doppelklick: automatische Länge
+
+    def _length_drag_finished(self) -> None:
+        self.render_now()
+        self._commit()
 
     def _show_media_status(self, text: str, state: str) -> None:
         self.media_status.setProperty("state", state)
@@ -345,6 +528,7 @@ class MainWindow(QMainWindow):
             self.doc.label_id = label_id
             self.panel("paper").refresh()
             self.schedule_render()
+            self._commit()
         self.panel("paper").show_media(media, label_id, adjusted)
 
     def _media_failed(self, message: str) -> None:
@@ -406,3 +590,11 @@ class MainWindow(QMainWindow):
         self.result.style().polish(self.result)
         self._set_printing(False)
         self.refresh_printer()
+
+
+def _offset(obj: TextObject) -> TextObject:
+    """Kopie, um ``PASTE_OFFSET_MM`` nach rechts und unten versetzt."""
+    moved = copy.deepcopy(obj)
+    moved.x_mm = round((obj.x_mm or 0.0) + PASTE_OFFSET_MM, 3)
+    moved.y_mm = round((obj.y_mm or 0.0) + PASTE_OFFSET_MM, 3)
+    return moved
diff --git a/src/labelwerk/gui/panels/__init__.py b/src/labelwerk/gui/panels/__init__.py
index 31e412a..ff36e3e 100644
--- a/src/labelwerk/gui/panels/__init__.py
+++ b/src/labelwerk/gui/panels/__init__.py
@@ -8,9 +8,14 @@ from ...document import Document
 
 
 class Panel(QWidget):
-    """Basis: hält das Dokument, sendet changed nach jeder Änderung."""
+    """Basis: hält das Dokument, sendet changed nach jeder Änderung.
+
+    ``edited`` meldet einen abgeschlossenen Stand für Rückgängig (das Hauptfenster hält ihn
+    fest; ohne Änderung seit dem letzten Stand ist das kein neuer Schritt).
+    """
 
     changed = Signal()
+    edited = Signal()
 
     def __init__(self, doc: Document, title: str):
         super().__init__()
diff --git a/src/labelwerk/gui/panels/paper.py b/src/labelwerk/gui/panels/paper.py
index dccc2a0..483dfdb 100644
--- a/src/labelwerk/gui/panels/paper.py
+++ b/src/labelwerk/gui/panels/paper.py
@@ -101,6 +101,7 @@ class PaperPanel(Panel):
         self._update_visibility()
         self._update_media_status()
         self.changed.emit()
+        self.edited.emit()           # jede Papier-Änderung ist ein eigener Schritt
 
     def refresh(self) -> None:
         for w in self._widgets():
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index b87f274..94f7d71 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -8,7 +8,7 @@ from __future__ import annotations
 import math
 from importlib import resources
 
-from PySide6.QtCore import QSize, Qt
+from PySide6.QtCore import QSize, Qt, Signal
 from PySide6.QtGui import (QFont, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextFormat,
                            QTextOption)
 from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayout, QLabel,
@@ -30,6 +30,8 @@ _ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.A
 class PlainPasteEdit(QTextEdit):
     """Rich-Text-Editor, der aus der Zwischenablage nur reinen Text übernimmt."""
 
+    focus_left = Signal()            # Tippen ist abgeschlossen (ein Schritt für Rückgängig)
+
     def __init__(self):
         super().__init__()
         self.setTabChangesFocus(True)      # Tab springt weiter, statt "\t" einzufügen
@@ -45,6 +47,10 @@ class PlainPasteEdit(QTextEdit):
         if source.hasText():
             self.textCursor().insertText(source.text())
 
+    def focusOutEvent(self, event) -> None:
+        super().focusOutEvent(event)
+        self.focus_left.emit()
+
 
 def _button(text: str, tip: str, checkable: bool = True) -> QPushButton:
     button = QPushButton(text)
@@ -147,21 +153,24 @@ class TextPanel(Panel):
         self.layout_.addStretch()
 
         self.refresh()
+        self.edit.focus_left.connect(self.edited)
         self.edit.document().contentsChanged.connect(self._apply)
         self.edit.currentCharFormatChanged.connect(self._sync_buttons)
         self.edit.cursorPositionChanged.connect(self._sync_buttons)
         self.edit.selectionChanged.connect(self._sync_buttons)
-        self.family.currentFontChanged.connect(lambda font: self._format(family=font.family()))
-        self.size.activated.connect(lambda _: self._size_entered())
-        self.size.lineEdit().editingFinished.connect(self._size_entered)
-        self.grow.clicked.connect(lambda: self._step_size(+1))
-        self.shrink.clicked.connect(lambda: self._step_size(-1))
-        self.bold.clicked.connect(lambda on: self._format(bold=on))
-        self.italic.clicked.connect(lambda on: self._format(italic=on))
-        self.underline.clicked.connect(lambda on: self._format(underline=on))
+        step = self._step     # Knöpfe und Felder: jede Änderung ein eigener Schritt
+        self.family.currentFontChanged.connect(
+            lambda font: step(self._format, family=font.family()))
+        self.size.activated.connect(lambda _: step(self._size_entered))
+        self.size.lineEdit().editingFinished.connect(lambda: step(self._size_entered))
+        self.grow.clicked.connect(lambda: step(self._step_size, +1))
+        self.shrink.clicked.connect(lambda: step(self._step_size, -1))
+        self.bold.clicked.connect(lambda on: step(self._format, bold=on))
+        self.italic.clicked.connect(lambda on: step(self._format, italic=on))
+        self.underline.clicked.connect(lambda on: step(self._format, underline=on))
         for key, button in self.align_buttons.items():
-            button.clicked.connect(lambda _=False, k=key: self._align(k))
-        self.fit.toggled.connect(lambda _: self._apply())
+            button.clicked.connect(lambda _=False, k=key: step(self._align, k))
+        self.fit.toggled.connect(lambda _: step(self._apply))
         for keys, button in ((QKeySequence.StandardKey.Bold, self.bold),
                              (QKeySequence.StandardKey.Italic, self.italic),
                              (QKeySequence.StandardKey.Underline, self.underline)):
@@ -172,6 +181,14 @@ class TextPanel(Panel):
     def obj(self) -> TextObject:
         return self.doc.objects[0]
 
+    def _step(self, change, *args, **kwargs) -> None:
+        """Änderung als eigener Rückgängig-Schritt: vorher Getipptes festhalten, danach das Neue."""
+        if self._updating:
+            return
+        self.edited.emit()
+        change(*args, **kwargs)
+        self.edited.emit()
+
     # --- Formatieren ------------------------------------------------------
     def _target(self) -> QTextCursor:
         """Markierung, sonst der ganze Text (wie ein ausgewählter Textrahmen)."""
@@ -380,6 +397,7 @@ class TextPanel(Panel):
                           "italic": first.italic if first else False,
                           "underline": first.underline if first else False}
             document = self.edit.document()
+            document.setUndoRedoEnabled(False)     # Aufbau ist kein Schritt im Editor
             document.clear()
             cursor = QTextCursor(document)
             cursor.setCharFormat(_char_format_of(self._base))
@@ -397,6 +415,7 @@ class TextPanel(Panel):
                            else _char_format_of(self._base))
                     cursor.setBlockCharFormat(fmt)
                     cursor.setCharFormat(fmt)
+            document.setUndoRedoEnabled(True)
             self.edit.setTextCursor(cursor)
             self.edit.setCurrentCharFormat(_char_format_of(self._props(cursor.charFormat())))
             self.fit.setChecked(obj.auto)
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index e79d056..f9df946 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -29,6 +29,10 @@ QToolBar QToolButton:hover, QToolBar QToolButton:checked {
     background: #000000;
     color: #FFFFFF;
 }
+/* Bearbeitungsleiste: kleinere Knöpfe, Trenner als schwarzer Strich */
+QToolBar#editBar { padding: 4px 6px; }
+QToolBar#editBar QToolButton { padding: 3px 10px; letter-spacing: 1px; }
+QToolBar#editBar::separator { background: #000000; width: 3px; margin: 2px 8px 5px 8px; }
 QToolBar QToolButton#print { background: #000000; color: #FFFFFF; }
 QToolBar QToolButton#print:hover { background: #FFFFFF; color: #000000; }
 QToolBar QToolButton:disabled, QToolBar QToolButton#print:disabled {
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `545 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/canvas.py src/labelwerk/gui/history.py src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/__init__.py src/labelwerk/gui/panels/paper.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/theme/rawblock.qss tests/gui/test_gui_editbar.py tests/gui/test_gui_history.py
git commit -m "GUI: Bearbeitungsleiste – Text anlegen, Zwischenablage, Rückgängig

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: GUI – Text-Panel bearbeitet den gewählten Rahmen, Bereich Position

**Files:**
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/layout.py`
- Modify: `tests/gui/test_gui_placement.py`
- Create: `tests/gui/test_gui_textframe.py`
- Modify: `tests/test_layout.py`

**Interfaces / Produces:** `TextPanel.index`, `set_object(index | None)`, `show_frame(Rect | None)`, Signal `frame_edited(key, value)`, `hint`, `pos_x/pos_y/pos_w/pos_h`; `layout.set_frame(obj, rect, rendered)`; Panel-Stapel in einem Scrollbereich.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_placement.py b/tests/gui/test_gui_placement.py
index c8814a7..56e81c4 100644
--- a/tests/gui/test_gui_placement.py
+++ b/tests/gui/test_gui_placement.py
@@ -306,16 +306,16 @@ def test_delete_removes_selected_objects(window, qtbot):
     QTest.keyClick(window.canvas, Qt.Key.Key_Delete)
     assert [o.text for o in window.doc.objects] == ["Zwei"]
     assert window.canvas.selection() == []
-    assert window.panel("text").edit.toPlainText() == "Zwei"
+    assert window.panel("text").index is None              # nichts mehr ausgewählt
     assert len(window.canvas.objects) == 1
 
 
-def test_select_all_and_delete_leaves_an_empty_text(window, qtbot):
+def test_select_all_and_delete_leaves_no_object(window, qtbot):
     _focus(window, qtbot)
     QTest.keyClick(window.canvas, Qt.Key.Key_A, CTRL)
     assert window.canvas.selection() == [0, 1]
     QTest.keyClick(window.canvas, Qt.Key.Key_Delete)
-    assert len(window.doc.objects) == 1 and window.doc.objects[0].is_empty()
+    assert window.doc.objects == [] and window.canvas.objects == []
     assert window.panel("text").edit.toPlainText() == ""
 
 
diff --git a/tests/gui/test_gui_textframe.py b/tests/gui/test_gui_textframe.py
new file mode 100644
index 0000000..3f54434
--- /dev/null
+++ b/tests/gui/test_gui_textframe.py
@@ -0,0 +1,195 @@
+"""Text-Panel bearbeitet den gewählten Rahmen, Bereich „Position“ (Etappe 3d-1)."""
+import pytest
+from PySide6.QtTest import QTest
+
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.labels import DPI
+from labelwerk.settings import Settings
+
+DOT_MM = 25.4 / DPI
+HINT = "Auf das Etikett klicken, um einen Textrahmen anzulegen"
+
+
+def _doc():
+    return Document("62", length_mm=40, objects=[
+        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
+        TextObject("Zwei", size_pt=14, x_mm=4, y_mm=20)])
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
+def _spins(panel):
+    return panel.pos_x, panel.pos_y, panel.pos_w, panel.pos_h
+
+
+def _values(panel):
+    return tuple(spin.value() for spin in _spins(panel))
+
+
+# --- Panel folgt der Auswahl -------------------------------------------------------
+def test_without_selection_panel_shows_hint(window):
+    panel = window.panel("text")
+    assert window.canvas.selection() == [] and panel.index is None
+    assert not panel.hint.isHidden() and panel.hint.text() == HINT
+    assert not panel.edit.isEnabled() and panel.edit.toPlainText() == ""
+    assert not panel.bold.isEnabled() and not panel.pos_x.isEnabled()
+
+
+def test_panel_edits_selected_object(window):
+    panel = window.panel("text")
+    window.canvas.set_selection([1])
+    assert panel.index == 1 and panel.hint.isHidden() and panel.edit.isEnabled()
+    assert panel.edit.toPlainText() == "Zwei"
+    panel.edit.setPlainText("Zwei!")
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei!"]
+    assert (window.doc.objects[1].x_mm, window.doc.objects[1].y_mm) == (4, 20)
+
+
+def test_panel_edits_last_selected_of_several(window):
+    panel = window.panel("text")
+    window.canvas.set_selection([1, 0])
+    assert panel.edit.toPlainText() == "Eins"
+    window.canvas.set_selection([0, 1])
+    assert panel.edit.toPlainText() == "Zwei"
+
+
+def test_single_object_is_selected_at_start(qtbot):
+    win = MainWindow(settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    assert win.canvas.selection() == [0] and win.panel("text").index == 0
+    assert win.panels.currentWidget() is win.panel("paper")        # Start wie bisher
+
+
+def test_selecting_switches_to_text_panel_and_paper_tab_keeps_selection(window):
+    assert window.panels.currentWidget() is window.panel("paper")
+    window.canvas.set_selection([0])
+    assert window.panels.currentWidget() is window.panel("text")
+    assert window.tool_actions["text"].isChecked()
+    window.tool_actions["paper"].trigger()
+    assert window.panels.currentWidget() is window.panel("paper")
+    assert window.canvas.selection() == [0]
+
+
+def test_text_tab_without_selection_starts_text_tool(window):
+    window.tool_actions["text"].trigger()
+    assert window.canvas.tool() == "text"
+    window.actions["tool.select"].trigger()
+    window.canvas.set_selection([0])
+    window.tool_actions["paper"].trigger()
+    window.tool_actions["text"].trigger()
+    assert window.canvas.tool() == "select"
+
+
+def test_typing_goes_into_newly_created_text(window, qtbot):
+    window.create_text(30, 12)
+    editor = window.panel("text").edit
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    QTest.keyClicks(editor, "Neu")
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zwei", "Neu"]
+    assert (window.doc.objects[2].x_mm, window.doc.objects[2].y_mm) == (30, 12)
+
+
+def test_deleting_last_object_leaves_label_empty(qtbot):
+    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Allein")]))
+    win.canvas.set_selection([0])
+    win.delete_selected()
+    assert win.doc.objects == [] and win.canvas.objects == []
+    assert win.panel("text").index is None and not win.panel("text").hint.isHidden()
+    assert win.doc.is_empty()
+    win.undo()
+    assert [o.text for o in win.doc.objects] == ["Allein"]
+
+
+# --- Bereich „Position“ ------------------------------------------------------------
+def test_position_shows_frame_of_selected_object(window):
+    window.canvas.set_selection([1])
+    shown = window.canvas.objects[1].frame_mm()
+    x, y, w, h = _values(window.panel("text"))
+    assert (x, y) == (4, 20)
+    assert (w, h) == pytest.approx((shown.w, shown.h), abs=0.05)
+    spin = window.panel("text").pos_x
+    assert (spin.decimals(), spin.singleStep()) == (1, 0.1)
+
+
+def test_position_of_centered_object_is_computed(qtbot):
+    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Mitte")]))
+    shown = win.canvas.objects[0].frame_mm()
+    x, y, _, _ = _values(win.panel("text"))
+    assert (x, y) == pytest.approx((shown.x, shown.y), abs=0.05)
+
+
+def test_editing_x_and_y_moves_object(window):
+    window.canvas.set_selection([1])
+    panel = window.panel("text")
+    panel.pos_x.setValue(10.5)
+    panel.pos_y.setValue(22)
+    obj = window.doc.objects[1]
+    assert (obj.x_mm, obj.y_mm) == (10.5, 22)
+    frame = window.canvas.objects[1].frame_mm()
+    assert (frame.x, frame.y) == pytest.approx((10.5, 22), abs=DOT_MM)
+    window.undo()
+    assert (window.doc.objects[1].x_mm, window.doc.objects[1].y_mm) == (10.5, 20)
+    assert panel.pos_y.value() == 20
+
+
+def test_editing_position_of_centered_object_positions_it(qtbot):
+    win = _window(qtbot, Document("62", length_mm=40, objects=[TextObject("Mitte")]))
+    base_pt = win.canvas.objects[0].rendered.base_pt
+    win.panel("text").pos_y.setValue(3)
+    obj = win.doc.objects[0]
+    assert obj.positioned and obj.y_mm == 3 and obj.size_pt == round(base_pt, 1)
+
+
+def test_width_and_height_only_editable_with_fixed_frame(window):
+    window.canvas.set_selection([0])
+    panel = window.panel("text")
+    assert panel.pos_w.isReadOnly() and panel.pos_h.isReadOnly()
+    assert not panel.pos_x.isReadOnly()
+    panel.fit.setChecked(True)
+    assert not panel.pos_w.isReadOnly() and not panel.pos_h.isReadOnly()
+    panel.pos_w.setValue(30)
+    obj = window.doc.objects[0]
+    assert obj.fit and obj.w_mm == 30 and (obj.x_mm, obj.y_mm) == (4, 4)
+    assert window.canvas.objects[0].frame_mm().w == pytest.approx(30, abs=DOT_MM)
+
+
+def test_turning_fixed_frame_on_keeps_current_frame_size(window):
+    window.canvas.set_selection([0])
+    shown = window.canvas.objects[0].frame_mm()
+    window.panel("text").fit.setChecked(True)
+    obj = window.doc.objects[0]
+    assert obj.fit and (obj.w_mm, obj.h_mm) == pytest.approx((shown.w, shown.h), abs=0.001)
+    frame = window.canvas.objects[0].frame_mm()
+    assert (frame.w, frame.h) == pytest.approx((shown.w, shown.h), abs=DOT_MM)
+
+
+def test_position_follows_nudge(window):
+    window.canvas.set_selection([1])
+    window.nudge(1, -0.5)
+    assert window.panel("text").pos_x.value() == 5
+    assert window.panel("text").pos_y.value() == 19.5
+
+
+def test_panels_scroll_instead_of_growing_the_window(window):
+    window.canvas.set_selection([0])
+    assert window.minimumSizeHint().height() < 600          # passt auch auf 768-px-Bildschirme
+    assert window.panels.parentWidget().parentWidget().objectName() == "panelScroll"
+
+
+def test_combos_are_blank_without_selection(window):
+    panel = window.panel("text")
+    assert panel.size.currentText() == "" and panel.family.currentText() == ""
+    window.canvas.set_selection([0])
+    assert panel.size.currentText() == "14" and panel.family.currentText()
diff --git a/tests/test_layout.py b/tests/test_layout.py
index 9eeadf3..8df4327 100644
--- a/tests/test_layout.py
+++ b/tests/test_layout.py
@@ -454,3 +454,34 @@ def test_resize_edge_turns_fixed_frame_on():
     assert resized.fit
     assert (resized.x_mm, resized.y_mm, resized.w_mm, resized.h_mm) == \
         pytest.approx((1, 1, old.h + 8, old.w), abs=0.001)             # ungedreht gespeichert
+
+
+# --- Zahlen im Panel „Position“ -----------------------------------------------------
+def test_set_frame_moves_object_without_fixed_frame():
+    obj = TextObject("A", size_pt=12, x_mm=4, y_mm=5)
+    placed = layout.set_frame(obj, Rect(10, 6, 99, 99), _rendered(4, 5, 10, 3))
+    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (10, 6, None, None)
+    assert (placed.size_pt, placed.fit, obj.x_mm) == (12, False, 4)
+
+
+def test_set_frame_positions_automatic_object_with_its_effective_size():
+    rendered = _rendered(20, 8, 10, 3, base_pt=23.04)
+    placed = layout.set_frame(TextObject("Hallo"), Rect(10, 6, 10, 3), rendered)
+    assert placed.positioned and (placed.x_mm, placed.y_mm) == (10, 6)
+    assert placed.size_pt == 23 and not placed.fit
+
+
+@pytest.mark.parametrize("positioned", [True, False])
+def test_set_frame_changes_fixed_frame(positioned):
+    obj = TextObject("A", size_pt=12, fit=True, w_mm=20 if positioned else None,
+                     h_mm=8 if positioned else None,
+                     x_mm=1 if positioned else None, y_mm=1 if positioned else None)
+    placed = layout.set_frame(obj, Rect(2, 3, 25, 12), _rendered(1, 1, 20, 8))
+    assert (placed.x_mm, placed.y_mm, placed.w_mm, placed.h_mm) == (2, 3, 25, 12)
+    assert placed.fit and placed.size_pt == 12
+
+
+def test_set_frame_stores_rotated_frame_unrotated():
+    obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8, rotation=90)
+    placed = layout.set_frame(obj, Rect(1, 1, 10, 30), _rendered(1, 1, 8, 20))
+    assert (placed.w_mm, placed.h_mm) == (30, 10)
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index ba4a453..cf8d959 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -2,20 +2,22 @@
 from __future__ import annotations
 
 import copy
-from dataclasses import dataclass
+from dataclasses import dataclass, replace
 from pathlib import Path
 
 from PySide6.QtCore import Qt, QThreadPool, QTimer
 from PySide6.QtGui import QAction, QActionGroup, QIcon
-from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox, QSizePolicy,
-                               QStackedWidget, QToolBar, QToolButton, QWidget)
+from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
+                               QScrollArea, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
+                               QWidget)
 
 from ..desktop import APP_NAME
 from ..detect import brother_busy, find_brother_lp
 from ..document import Document, TextObject
 from ..fonts import DEFAULT_FAMILY
 from ..labels import get_label
-from ..layout import Rect, move, object_rect, objects_outside, printable_area, resize
+from ..layout import (Rect, exact_rect, move, object_rect, objects_outside, printable_area,
+                      resize, set_frame)
 from ..printer import DEFAULT_MODEL
 from ..render import RenderedObject, compose, font_warnings, label_size, render_object
 from ..settings import Settings, load_settings, new_document
@@ -30,6 +32,7 @@ from .settings_dialog import SettingsDialog
 from .tools import TOOLS, Tool
 
 RENDER_DELAY_MS = 150
+PANEL_WIDTH = 280          # Eigenschaften-Panels; bei wenig Höhe rollbar
 MEDIA_STATUS_MAX_PX = 360   # Rollen-Hinweis in der Fußzeile; Rest per „…“ und Tooltip
 PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff
 NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
@@ -82,7 +85,7 @@ class MainWindow(QMainWindow):
         self.addToolBar(toolbar)
         self.panels = QStackedWidget()
         self.panels.setObjectName("panels")
-        self.panels.setFixedWidth(280)
+        self.panels.setFixedWidth(PANEL_WIDTH)
         self.tool_actions: dict[str, QAction] = {}
         self._panel_by_key = {}
         group = QActionGroup(self)
@@ -95,7 +98,7 @@ class MainWindow(QMainWindow):
             self._panel_by_key[tool.key] = panel
             action = QAction(QIcon.fromTheme(tool.icon), tool.title.upper(), self)
             action.setCheckable(True)
-            action.triggered.connect(lambda _=False, i=index: self.panels.setCurrentIndex(i))
+            action.triggered.connect(lambda _=False, key=tool.key: self._tool_triggered(key))
             group.addAction(action)
             toolbar.addAction(action)
             self.tool_actions[tool.key] = action
@@ -131,7 +134,14 @@ class MainWindow(QMainWindow):
         layout = QHBoxLayout(central)
         layout.setContentsMargins(0, 0, 0, 0)
         layout.setSpacing(0)
-        layout.addWidget(self.panels)
+        scroll = QScrollArea()                  # kleine Bildschirme: Panel rollt statt Fenster wächst
+        scroll.setObjectName("panelScroll")
+        scroll.setWidget(self.panels)
+        scroll.setWidgetResizable(True)
+        scroll.setFrameShape(QFrame.Shape.NoFrame)
+        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
+        scroll.setFixedWidth(PANEL_WIDTH + scroll.verticalScrollBar().sizeHint().width())
+        layout.addWidget(scroll)
         layout.addWidget(self.canvas, 1)
         self.setCentralWidget(central)
 
@@ -167,6 +177,11 @@ class MainWindow(QMainWindow):
         self._printer_timer.start()
 
         self.render_now()
+        if len(self.doc.objects) == 1:     # einziges Objekt: gleich bearbeitbar (Start wie bisher)
+            self.canvas.set_selection([0])
+            self._follow_selection([0])
+        self.canvas.selection_changed.connect(self._on_selection)
+        self.panel("text").frame_edited.connect(self._edit_frame)
         self._update_edit_actions()
         self.refresh_printer()
         if self.settings.warnings:
@@ -233,6 +248,32 @@ class MainWindow(QMainWindow):
         self.tool_actions[key].setChecked(True)
         self.panels.setCurrentWidget(self.panel(key))
 
+    def _tool_triggered(self, key: str) -> None:
+        """Werkzeug-Reiter: Panel zeigen; Text ohne Auswahl heißt „Text anlegen“."""
+        self.panels.setCurrentWidget(self.panel(key))
+        if key == "text" and not self.canvas.selection():
+            self.canvas.set_tool("text")
+
+    def _on_selection(self, indices: list[int]) -> None:
+        """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen (Papier-Reiter behält sie)."""
+        self._follow_selection(indices)
+        if indices:
+            self._show_tool("text")
+
+    def _follow_selection(self, indices: list[int]) -> None:
+        """Text-Panel bearbeitet das zuletzt gewählte Objekt."""
+        self.panel("text").set_object(indices[-1] if indices else None)
+        self._update_frame()
+
+    def _update_frame(self) -> None:
+        """Bereich „Position“: Rahmen des bearbeiteten Objekts, wie er gerendert ist."""
+        panel = self.panel("text")
+        index = panel.index
+        if index is None or index >= len(self.rendered) or index >= len(self.doc.objects):
+            panel.show_frame(None)
+        else:
+            panel.show_frame(exact_rect(self.doc.objects[index], self.rendered[index]))
+
     def _update_edit_actions(self) -> None:
         selected = bool(self.canvas.selection())
         for key in _SELECTION_ACTIONS:
@@ -277,6 +318,7 @@ class MainWindow(QMainWindow):
         self.rendered = rendered
         self.canvas.set_document(get_label(self.doc.label_id), size, rendered, self.doc.orientation,
                                  area, keep_ratio=[not obj.fit for obj in self.doc.objects])
+        self._update_frame()
 
     def _render_objects(self, size: tuple[int, int]) -> list[RenderedObject]:
         """Objekte einzeln rendern; unveränderte kommen aus dem Cache.
@@ -370,7 +412,7 @@ class MainWindow(QMainWindow):
         self.panel("text").edit.setFocus()
 
     def delete_selected(self) -> None:
-        """Ausgewählte Objekte löschen; ein leerer Text bleibt, damit das Text-Panel etwas hat."""
+        """Ausgewählte Objekte löschen (auch das letzte – das Etikett ist dann leer)."""
         indices = self.canvas.selection()
         if not indices:
             return
@@ -378,9 +420,19 @@ class MainWindow(QMainWindow):
         self.canvas.set_selection([])
         for index in sorted(indices, reverse=True):
             del self.doc.objects[index]
-        if not self.doc.objects:
-            self.doc.objects.append(new_document(self.settings).objects[0])
-        self._objects_changed([0])
+        self.render_now()
+        self._commit()
+
+    def _edit_frame(self, key: str, value: float) -> None:
+        """Zahl im Bereich „Position“ geändert: Objekt verschieben bzw. Rahmen ändern."""
+        index = self.panel("text").index
+        if index is None or index >= len(self.rendered):
+            return
+        self._commit()
+        obj = self.doc.objects[index]
+        rect = replace(exact_rect(obj, self.rendered[index]), **{key: round(value, 3)})
+        self.doc.objects[index] = set_frame(obj, rect, self.rendered[index])
+        self._objects_changed([index])
         self._commit()
 
     # --- Zwischenablage ---------------------------------------------------
@@ -424,8 +476,8 @@ class MainWindow(QMainWindow):
         self._commit()
 
     def _objects_changed(self, indices: list[int]) -> None:
-        if 0 in indices:
-            self.panel("text").refresh()   # Text-Panel bearbeitet (noch) das erste Objekt
+        if self.panel("text").index in indices:
+            self.panel("text").refresh()   # z. B. Anfasser schaltet feste Rahmengröße ein
         self.render_now()
 
     def _on_length_dragged(self, length_mm) -> None:
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index 94f7d71..f634f8c 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -1,7 +1,8 @@
-"""Panel „Text“: zeichenweise Formatierung wie im P-touch Editor.
+"""Panel „Text“: bearbeitet den ausgewählten Textrahmen – zeichenweise wie im P-touch Editor.
 
 Regel wie bei einem ausgewählten Textrahmen in P-touch: Ist nichts markiert, wirkt eine
-Formatierung auf den ganzen Text; sonst nur auf die Markierung.
+Formatierung auf den ganzen Text; sonst nur auf die Markierung. Bereich „Position“: Lage
+und (mit fester Rahmengröße) Größe des Rahmens in mm.
 """
 from __future__ import annotations
 
@@ -11,18 +12,24 @@ from importlib import resources
 from PySide6.QtCore import QSize, Qt, Signal
 from PySide6.QtGui import (QFont, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextFormat,
                            QTextOption)
-from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QHBoxLayout, QLabel,
-                               QPushButton, QTextEdit)
+from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QGridLayout, QHBoxLayout,
+                               QLabel, QPushButton, QTextEdit)
 
 from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
 from ...fonts import DEFAULT_FAMILY
+from ...layout import Rect
 from ...render import REF_PT
+from ..widgets import DoubleSpinBox
 from . import Panel
 
 _P = QTextFormat.Property
 
 SIZES_PT = (6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72)
 DEFAULT_PT = 19
+HINT = "Auf das Etikett klicken, um einen Textrahmen anzulegen"
+POSITION_MM = (-999.9, 999.9)    # Lage darf auch neben dem Etikett liegen (ragt hinaus)
+SIZE_MM = (1.0, 999.9)
+_FRAME_ONLY = "Nur mit fester Rahmengröße änderbar"
 _ALIGN_TO_QT = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                 "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}
 
@@ -72,6 +79,8 @@ def _align_icon(key: str, dark_checked: bool = True) -> QIcon:
 
 
 class TextPanel(Panel):
+    frame_edited = Signal(str, float)   # Feld im Bereich „Position“ ("x" | "y" | "w" | "h"), mm
+
     def set_icon_style(self, dark_checked: bool) -> None:
         """Ausrichtungssymbole an das Design anpassen (weiß auf schwarz nur bei RawBlock)."""
         self.dark_checked_icons = dark_checked
@@ -81,8 +90,8 @@ class TextPanel(Panel):
     def __init__(self, doc: Document):
         super().__init__(doc, "Text")
         self.dark_checked_icons = True
-        if not doc.objects:
-            doc.objects.append(TextObject(""))
+        self.index: int | None = None   # bearbeitetes Objekt; None = kein Text ausgewählt
+        self._frame: Rect | None = None   # zuletzt angezeigter Rahmen (mm)
         self._updating = False
         self._formatting = False        # während einer Formatierung: contentsChanged nicht doppelt anwenden
         self._shown_pt: float | None = float(DEFAULT_PT)   # zuletzt angezeigte Größe; None = gemischt
@@ -90,6 +99,11 @@ class TextPanel(Panel):
         self._base = {"family": DEFAULT_FAMILY, "pt": float(DEFAULT_PT), "bold": True,
                       "italic": False, "underline": False}
 
+        self.hint = QLabel(HINT)
+        self.hint.setObjectName("hint")
+        self.hint.setWordWrap(True)
+        self.layout_.addWidget(self.hint)
+
         self.section("Inhalt")
         self.edit = PlainPasteEdit()
         self.edit.setPlaceholderText("Text eingeben …")
@@ -145,6 +159,29 @@ class TextPanel(Panel):
         self.fit = _button("FESTE RAHMENGRÖSSE", "Text automatisch so skalieren, dass er passt")
         self.layout_.addWidget(self.fit)
 
+        self.section("Position (mm)")
+        grid = QGridLayout()
+        self.pos_x, self.pos_y, self.pos_w, self.pos_h = (DoubleSpinBox() for _ in range(4))
+        self._frame_spins = {"x": self.pos_x, "y": self.pos_y, "w": self.pos_w, "h": self.pos_h}
+        for i, (key, text, tip) in enumerate((("x", "X", "Abstand vom linken Etikettrand"),
+                                              ("y", "Y", "Abstand vom oberen Etikettrand"),
+                                              ("w", "B", "Breite des Rahmens"),
+                                              ("h", "H", "Höhe des Rahmens"))):
+            spin = self._frame_spins[key]
+            spin.setDecimals(1)
+            spin.setSingleStep(0.1)
+            spin.setRange(*(POSITION_MM if key in "xy" else SIZE_MM))
+            spin.setKeyboardTracking(False)        # erst nach Enter/Fokuswechsel/Pfeil übernehmen
+            spin.setToolTip(tip)
+            label = QLabel(text)
+            label.setToolTip(tip)
+            grid.addWidget(label, i // 2, (i % 2) * 2)
+            grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)
+            spin.valueChanged.connect(lambda value, k=key: self._frame_changed(k, value))
+        grid.setColumnStretch(1, 1)
+        grid.setColumnStretch(3, 1)
+        self.layout_.addLayout(grid)
+
         self.error = QLabel()
         self.error.setObjectName("error")
         self.error.setWordWrap(True)
@@ -179,7 +216,19 @@ class TextPanel(Panel):
 
     @property
     def obj(self) -> TextObject:
-        return self.doc.objects[0]
+        return self.doc.objects[self.index]
+
+    def set_object(self, index: int | None) -> None:
+        """Objekt bearbeiten (Index in ``doc.objects``) bzw. mit None keins (Hinweis)."""
+        if index != self.index:
+            self.index = index
+            self._frame = None
+            self.refresh()
+
+    def _editing_widgets(self):
+        return (self.edit, self.family, self.size, self.grow, self.shrink, self.bold,
+                self.italic, self.underline, *self.align_buttons.values(), self.fit,
+                *self._frame_spins.values())
 
     def _step(self, change, *args, **kwargs) -> None:
         """Änderung als eigener Rückgängig-Schritt: vorher Getipptes festhalten, danach das Neue."""
@@ -366,24 +415,41 @@ class TextPanel(Panel):
             paragraphs.append(Paragraph(spans, align))
             block = block.next()
         obj = self.obj                 # Rahmen und Drehung bleiben beim Tippen erhalten
+        fit = self.fit.isChecked()
+        w, h = obj.w_mm, obj.h_mm
+        if fit and not obj.fit and obj.positioned and self._frame is not None:
+            # feste Rahmengröße einschalten: Rahmen bleibt so groß, wie er gerade ist
+            w, h = round(self._frame.w, 3), round(self._frame.h, 3)
+            if obj.rotation in (90, 270):
+                w, h = h, w
         return TextObject(paragraphs, size_pt=base_pt, font_path=obj.font_path,
-                          fit=self.fit.isChecked(), x_mm=obj.x_mm, y_mm=obj.y_mm,
-                          w_mm=obj.w_mm, h_mm=obj.h_mm, rotation=obj.rotation)
+                          fit=fit, x_mm=obj.x_mm, y_mm=obj.y_mm,
+                          w_mm=w, h_mm=h, rotation=obj.rotation)
 
     def _apply(self) -> None:
-        if self._updating or self._formatting:
+        if self._updating or self._formatting or self.index is None:
             return
         self._updating = True
         try:
             self._fill_base_formats()
         finally:
             self._updating = False
-        self.doc.objects[0] = self.to_text_object()
+        self.doc.objects[self.index] = self.to_text_object()
         self._sync_buttons()
+        self._update_frame_editing()
         self.changed.emit()
 
     def refresh(self) -> None:
-        """Editor aus dem Modell aufbauen (Start mit Einstellungen, später „Öffnen“)."""
+        """Editor aus dem Modell aufbauen (Auswahl, Rückgängig, Ziehen an den Anfassern)."""
+        if self.index is not None and not 0 <= self.index < len(self.doc.objects):
+            self.index = None                      # Objekt gibt es nicht mehr
+        editing = self.index is not None
+        self.hint.setVisible(not editing)
+        for widget in self._editing_widgets():
+            widget.setEnabled(editing)
+        if not editing:
+            self._show_nothing()
+            return
         obj = self.obj
         self._updating = True
         try:
@@ -422,6 +488,51 @@ class TextPanel(Panel):
         finally:
             self._updating = False
         self._sync_buttons()
+        self._update_frame_editing()
+
+    def _show_nothing(self) -> None:
+        """Kein Text ausgewählt: leeres, gesperrtes Panel."""
+        self._updating = True
+        try:
+            document = self.edit.document()
+            document.setUndoRedoEnabled(False)
+            document.clear()
+            document.setUndoRedoEnabled(True)
+            self.fit.setChecked(False)
+        finally:
+            self._updating = False
+        for combo in (self.family, self.size):         # keine Schrift anzeigen, die nicht gilt
+            combo.blockSignals(True)
+            combo.setCurrentIndex(-1)
+            combo.setEditText("")
+            combo.blockSignals(False)
+        self.show_frame(None)
+
+    # --- Position -----------------------------------------------------------
+    def show_frame(self, rect: Rect | None) -> None:
+        """Rahmen des bearbeiteten Objekts in mm anzeigen (vom Hauptfenster nach dem Rendern)."""
+        self._frame = rect
+        for key, spin in self._frame_spins.items():
+            spin.blockSignals(True)
+            spin.setValue(getattr(rect, key) if rect is not None else 0.0)
+            spin.blockSignals(False)
+        self._update_frame_editing()
+
+    def _update_frame_editing(self) -> None:
+        """Breite/Höhe nur mit fester Rahmengröße änderbar, sonst Anzeige der Größe."""
+        fixed = self.index is not None and self.obj.fit
+        for spin in (self.pos_w, self.pos_h):
+            if spin.isReadOnly() == fixed:
+                spin.setReadOnly(not fixed)          # Pfeile bleiben sichtbar, wirken aber nicht
+                spin.style().unpolish(spin)          # Stylesheet: [readOnly="true"] neu anwenden
+                spin.style().polish(spin)
+            spin.setToolTip(("Breite" if spin is self.pos_w else "Höhe") + " des Rahmens"
+                            + ("" if fixed else f" – {_FRAME_ONLY}"))
+
+    def _frame_changed(self, key: str, value: float) -> None:
+        if self.index is None or (key in "wh" and not self.obj.fit):
+            return
+        self.frame_edited.emit(key, value)
 
     def _sync_buttons(self) -> None:
         """Knöpfe zeigen die Formatierung an der Schreibmarke."""
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index f9df946..997ca99 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -41,7 +41,7 @@ QToolBar QToolButton:disabled, QToolBar QToolButton#print:disabled {
     border-color: #CCCCCC;
 }
 
-#panels { border-right: 3px solid #000000; }
+#panelScroll { border: none; border-right: 3px solid #000000; }
 QLabel#panelTitle { font-size: 22px; font-weight: 900; padding: 4px 0 8px 0; }
 QLabel[role="section"] { font-weight: 900; letter-spacing: 1px; padding-top: 10px; }
 QLabel#fixedSize { font-family: "Space Mono", "DejaVu Sans Mono", monospace; }
@@ -81,7 +81,15 @@ QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top righ
 QComboBox::drop-down:hover { background: #000000; }
 QComboBox::down-arrow { image: url(@THEME@/arrow-down-black.svg); width: 10px; height: 7px; }
 QComboBox::down-arrow:hover { image: url(@THEME@/arrow-down-white.svg); }
-QSpinBox:disabled, QDoubleSpinBox:disabled { border-color: #CCCCCC; background: #F5F5F5; color: #999999; }
+/* nur Anzeige (z. B. Rahmengröße ohne feste Rahmengröße): weiß, Pfeile grau */
+QDoubleSpinBox[readOnly="true"] { background: #FFFFFF; }
+QDoubleSpinBox[readOnly="true"]::up-arrow { image: url(@THEME@/arrow-up-gray.svg); }
+QDoubleSpinBox[readOnly="true"]::down-arrow { image: url(@THEME@/arrow-down-gray.svg); }
+QDoubleSpinBox[readOnly="true"]::up-button:hover, QDoubleSpinBox[readOnly="true"]::down-button:hover { background: #FFFFFF; }
+QLabel#hint { border: 3px dashed #000000; padding: 8px; font-weight: 700; }
+QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { border-color: #CCCCCC; background: #F5F5F5; color: #999999; }
+QComboBox::drop-down:disabled { border-left-color: #CCCCCC; background: #F5F5F5; }
+QComboBox::down-arrow:disabled { image: url(@THEME@/arrow-down-gray.svg); }
 QComboBox QAbstractItemView { border: 3px solid #000000; selection-background-color: #000000; selection-color: #FFFFFF; }
 
 QCheckBox::indicator { width: 16px; height: 16px; border: 3px solid #000000; background: #FFFFFF; }
@@ -101,6 +109,7 @@ QPushButton#formatButton[style="italic"] { font-style: italic; }
 QPushButton#formatButton[style="underline"] { text-decoration: underline; }
 QTextEdit { background: #F0F0F0; border: 3px solid #000000; border-radius: 0; padding: 4px; }
 QTextEdit:focus { border-width: 5px; }
+QTextEdit:disabled { border-color: #CCCCCC; background: #F5F5F5; }
 QFontComboBox { min-width: 0; }
 
 QStatusBar { border-top: 3px solid #000000; }
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index 23e9e9d..e34f14f 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -227,6 +227,17 @@ def move(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
     return moved
 
 
+def set_frame(obj: TextObject, rect: Rect, rendered: RenderedObject) -> TextObject:
+    """Kopie mit dem Rahmen ``rect`` in mm, wie er im Modell steht (Zahlen im Panel „Position“).
+
+    Mit fester Rahmengröße gelten Lage und Größe, sonst nur die Lage. Ein automatisch großes
+    Objekt bekommt dabei seine wirksame Größe (``rendered.base_pt``) als feste Schriftgröße.
+    """
+    if not obj.fit and obj.size_pt is None:
+        obj = fix_size(obj, rendered.base_pt)
+    return place(obj, rect)
+
+
 def resize(obj: TextObject, rect: Rect, rendered: RenderedObject, corner: bool) -> TextObject:
     """Kopie nach Ziehen an einem Anfasser: gerenderter Rahmen → ``rect``.
 
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `567 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/layout.py tests/gui/test_gui_placement.py tests/gui/test_gui_textframe.py tests/test_layout.py
git commit -m "GUI: Text-Panel bearbeitet den gewählten Rahmen, Bereich Position

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: GUI – Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge

**Files:**
- Create: `src/labelwerk/gui/icons/align-objects-bottom-black.svg`
- Create: `src/labelwerk/gui/icons/align-objects-bottom-white.svg`
- Create: `src/labelwerk/gui/icons/align-objects-hcenter-black.svg`
- Create: `src/labelwerk/gui/icons/align-objects-hcenter-white.svg`
- Create: `src/labelwerk/gui/icons/align-objects-left-black.svg`
- Create: `src/labelwerk/gui/icons/align-objects-left-white.svg`
- Create: `src/labelwerk/gui/icons/align-objects-right-black.svg`
- Create: `src/labelwerk/gui/icons/align-objects-right-white.svg`
- Create: `src/labelwerk/gui/icons/align-objects-top-black.svg`
- Create: `src/labelwerk/gui/icons/align-objects-top-white.svg`
- Create: `src/labelwerk/gui/icons/align-objects-vcenter-black.svg`
- Create: `src/labelwerk/gui/icons/align-objects-vcenter-white.svg`
- Create: `src/labelwerk/gui/icons/align-paper-bottom-black.svg`
- Create: `src/labelwerk/gui/icons/align-paper-bottom-white.svg`
- Create: `src/labelwerk/gui/icons/align-paper-hcenter-black.svg`
- Create: `src/labelwerk/gui/icons/align-paper-hcenter-white.svg`
- Create: `src/labelwerk/gui/icons/align-paper-left-black.svg`
- Create: `src/labelwerk/gui/icons/align-paper-left-white.svg`
- Create: `src/labelwerk/gui/icons/align-paper-right-black.svg`
- Create: `src/labelwerk/gui/icons/align-paper-right-white.svg`
- Create: `src/labelwerk/gui/icons/align-paper-top-black.svg`
- Create: `src/labelwerk/gui/icons/align-paper-top-white.svg`
- Create: `src/labelwerk/gui/icons/align-paper-vcenter-black.svg`
- Create: `src/labelwerk/gui/icons/align-paper-vcenter-white.svg`
- Create: `src/labelwerk/gui/icons/order-backward-black.svg`
- Create: `src/labelwerk/gui/icons/order-backward-white.svg`
- Create: `src/labelwerk/gui/icons/order-forward-black.svg`
- Create: `src/labelwerk/gui/icons/order-forward-white.svg`
- Create: `src/labelwerk/gui/icons/rotate-left-black.svg`
- Create: `src/labelwerk/gui/icons/rotate-left-white.svg`
- Create: `src/labelwerk/gui/icons/rotate-right-black.svg`
- Create: `src/labelwerk/gui/icons/rotate-right-white.svg`
- Create: `src/labelwerk/gui/icons/size-height-black.svg`
- Create: `src/labelwerk/gui/icons/size-height-white.svg`
- Create: `src/labelwerk/gui/icons/size-maximize-black.svg`
- Create: `src/labelwerk/gui/icons/size-maximize-white.svg`
- Create: `src/labelwerk/gui/icons/size-same-black.svg`
- Create: `src/labelwerk/gui/icons/size-same-white.svg`
- Create: `src/labelwerk/gui/icons/size-width-black.svg`
- Create: `src/labelwerk/gui/icons/size-width-white.svg`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/__init__.py`
- Create: `src/labelwerk/gui/panels/layout.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Create: `src/labelwerk/gui/symbols.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `src/labelwerk/gui/tools.py`
- Modify: `src/labelwerk/layout.py`
- Create: `tests/gui/test_gui_layout.py`
- Modify: `tests/test_layout.py`

**Interfaces / Produces:** `layout.align_objects`, `match_objects`, `maximize_object`, `rotate(obj, rendered, ±90)`, `reorder(items, indices, step) -> (list, indices)`; `gui/symbols.py line_icon(name, dark, hover)`; `Panel.set_selection`, `use_actions`, `set_icon_style`; `panels/layout.py LayoutPanel.buttons[action_id]`; Werkzeug `layout` in `tools.py`; MainWindow `align_selected`, `match_selected`, `maximize_selected`, `rotate_selected`, `reorder_selected`; `Canvas.object_clicked`; 40 SVG-Symbole in `gui/icons/`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_layout.py b/tests/gui/test_gui_layout.py
new file mode 100644
index 0000000..5745872
--- /dev/null
+++ b/tests/gui/test_gui_layout.py
@@ -0,0 +1,297 @@
+"""Reiter „Layout“: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Etappe 3d-1)."""
+from importlib import resources
+
+import pytest
+from PySide6.QtCore import QPointF, QSize, Qt
+from PySide6.QtGui import QIcon, QMouseEvent
+from PySide6.QtTest import QTest
+from PySide6.QtWidgets import QApplication, QToolButton
+
+from labelwerk import layout
+from labelwerk.document import Document, TextObject
+from labelwerk.gui.main_window import MainWindow
+from labelwerk.gui.panels.layout import LAYOUT_SECTIONS
+from labelwerk.gui.tools import TOOLS
+from labelwerk.labels import DPI
+from labelwerk.settings import Settings
+
+DOT_MM = 25.4 / DPI
+NO_MOD = Qt.KeyboardModifier.NoModifier
+CTRL = Qt.KeyboardModifier.ControlModifier
+LEFT = Qt.MouseButton.LeftButton
+SELECTED_ALIGN = ("align.left", "align.hcenter", "align.right",
+                  "align.top", "align.vcenter", "align.bottom")
+PAPER_ALIGN = tuple(key.replace("align.", "align.paper_") for key in SELECTED_ALIGN)
+FROM_ONE = PAPER_ALIGN + ("size.maximize", "object.rotate_left", "object.rotate_right",
+                          "object.bring_forward", "object.send_backward")
+FROM_TWO = SELECTED_ALIGN + ("size.same", "size.width", "size.height")
+
+
+def _doc():
+    return Document("62", length_mm=40, objects=[
+        TextObject("Eins", size_pt=14, x_mm=4, y_mm=4),
+        TextObject("Zweiter", size_pt=14, x_mm=12, y_mm=18),
+        TextObject("Drei", size_pt=14, fit=True, x_mm=8, y_mm=30, w_mm=20, h_mm=6)])
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
+def _panel(window):
+    return window.panel("layout")
+
+
+def _press(window, key):
+    """Knopf im Reiter „Layout“ drücken."""
+    button = _panel(window).buttons[key]
+    assert button.isEnabled(), key
+    button.click()
+
+
+def _frames(window):
+    return [layout.exact_rect(o, r) for o, r in zip(window.doc.objects, window.rendered)]
+
+
+# --- Reiter -----------------------------------------------------------------------
+def test_layout_tool_follows_text(window):
+    assert [tool.key for tool in TOOLS][:3] == ["paper", "text", "layout"]
+    window.tool_actions["layout"].trigger()
+    assert window.panels.currentWidget() is _panel(window)
+
+
+def test_selecting_keeps_layout_panel(window):
+    window.tool_actions["layout"].trigger()
+    window.canvas.set_selection([0])
+    window.canvas.set_selection([0, 1])
+    assert window.panels.currentWidget() is _panel(window)
+    assert window.tool_actions["layout"].isChecked()
+    assert window.panel("text").index == 1                  # Text-Panel folgt trotzdem
+
+
+def test_panel_has_sections_like_p_touch(window):
+    titles = [title for title, _ in LAYOUT_SECTIONS]
+    assert titles == ["Gewählte Objekte ausrichten", "Am Papier ausrichten",
+                      "Vergrößern/Verkleinern", "Drehen", "Reihenfolge"]
+    keys = [key for _, row in LAYOUT_SECTIONS for key, _ in row]
+    assert set(keys) == set(FROM_ONE + FROM_TWO) and len(keys) == 20
+    assert set(_panel(window).buttons) == set(keys)
+
+
+def test_buttons_are_icons_with_tooltips_from_actions(window):
+    folder = resources.files("labelwerk.gui") / "icons"
+    for _, row in LAYOUT_SECTIONS:
+        for key, icon in row:
+            button = _panel(window).buttons[key]
+            assert isinstance(button, QToolButton)
+            assert button.defaultAction() is window.actions[key]
+            assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
+            assert not button.icon().isNull()
+            for color in ("black", "white"):
+                assert (folder / f"{icon}-{color}.svg").is_file()
+    tip = _panel(window).buttons["object.rotate_right"].toolTip()
+    assert "rechts" in tip and "Ctrl+R" in tip
+
+
+@pytest.mark.parametrize("selection, enabled", [
+    ([], ()), ([0], FROM_ONE), ([0, 1], FROM_ONE + FROM_TWO)])
+def test_buttons_enabled_by_selection_count(window, selection, enabled):
+    window.canvas.set_selection(selection)
+    for key, button in _panel(window).buttons.items():
+        assert button.isEnabled() == (key in enabled), key
+
+
+# --- Ausrichten -------------------------------------------------------------------
+@pytest.mark.parametrize("mode, attr", [("left", "x"), ("hcenter", "cx"), ("right", "right"),
+                                        ("top", "y"), ("vcenter", "cy"), ("bottom", "bottom")])
+def test_align_selected_moves_only_selected(window, mode, attr):
+    before = _frames(window)
+    window.canvas.set_selection([0, 1])
+    _press(window, f"align.{mode}")
+    expected = getattr(layout.align(before[:2], mode)[0], attr)
+    after = _frames(window)
+    assert [getattr(r, attr) for r in after[:2]] == pytest.approx([expected] * 2, abs=0.001)
+    assert after[2] == before[2]
+    assert window.canvas.selection() == [0, 1]
+
+
+@pytest.mark.parametrize("mode, attr", [("left", "x"), ("hcenter", "cx"), ("right", "right"),
+                                        ("top", "y"), ("vcenter", "cy"), ("bottom", "bottom")])
+def test_align_to_paper(window, mode, attr):
+    area = layout.printable_area(window.doc)
+    window.canvas.set_selection([2])
+    _press(window, f"align.paper_{mode}")
+    assert getattr(_frames(window)[2], attr) == pytest.approx(getattr(area, attr), abs=0.001)
+
+
+def test_maximize(window):
+    area = layout.printable_area(window.doc)
+    window.canvas.set_selection([2])
+    _press(window, "size.maximize")
+    obj = window.doc.objects[2]
+    assert max(obj.w_mm / area.w, obj.h_mm / area.h) == pytest.approx(1)
+    assert (obj.x_mm + obj.w_mm / 2, obj.y_mm + obj.h_mm / 2) == pytest.approx(
+        (area.cx, area.cy), abs=0.001)
+
+
+@pytest.mark.parametrize("mode", ["same", "width", "height"])
+def test_same_size_scales_text_without_fixed_frame(qtbot, mode):
+    doc = Document("62", length_mm=40, objects=[TextObject("Wort", size_pt=28, x_mm=2, y_mm=2),
+                                                 TextObject("Wort", size_pt=14, x_mm=2, y_mm=25)])
+    win = _window(qtbot, doc)
+    win.canvas.set_selection([0, 1])                        # Bezug: zuerst gewähltes
+    _press(win, f"size.{mode}")
+    obj = win.doc.objects[1]
+    assert obj.size_pt == pytest.approx(28, abs=0.6) and not obj.fit
+    assert (obj.x_mm, obj.y_mm) == (2, 25)
+
+
+@pytest.mark.parametrize("mode, size", [("same", (20, 6)), ("width", (20, 3)),
+                                        ("height", (10, 6))])
+def test_same_size_sets_fixed_frame(qtbot, mode, size):
+    doc = Document("62", length_mm=40, objects=[
+        TextObject("A", size_pt=14, fit=True, x_mm=2, y_mm=2, w_mm=20, h_mm=6),
+        TextObject("B", size_pt=14, fit=True, x_mm=2, y_mm=25, w_mm=10, h_mm=3)])
+    win = _window(qtbot, doc)
+    win.canvas.set_selection([0, 1])
+    _press(win, f"size.{mode}")
+    obj = win.doc.objects[1]
+    assert (obj.w_mm, obj.h_mm) == size and (obj.x_mm, obj.y_mm) == (2, 25)
+
+
+# --- Drehen -----------------------------------------------------------------------
+@pytest.mark.parametrize("key, rotation", [("object.rotate_right", 90),
+                                           ("object.rotate_left", 270)])
+def test_rotate_keeps_center(window, key, rotation):
+    window.canvas.set_selection([1])
+    before = window.canvas.objects[1].frame_mm()
+    _press(window, key)
+    after = window.canvas.objects[1].frame_mm()
+    assert window.doc.objects[1].rotation == rotation
+    assert (after.w, after.h) == pytest.approx((before.h, before.w), abs=DOT_MM)
+    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=DOT_MM)
+
+
+def test_rotate_shortcut_on_canvas(window, qtbot):
+    window.canvas.set_selection([0])
+    window.activateWindow()
+    window.canvas.setFocus()
+    qtbot.waitUntil(window.canvas.hasFocus, timeout=1000)
+    QTest.keyClick(window.canvas, Qt.Key.Key_R, CTRL)
+    assert window.doc.objects[0].rotation == 90
+
+
+def _send(canvas, kind, pos, buttons):
+    button = LEFT if kind != QMouseEvent.Type.MouseMove else Qt.MouseButton.NoButton
+    event = QMouseEvent(kind, QPointF(pos), canvas.viewport().mapToGlobal(QPointF(pos)),
+                        button, buttons, NO_MOD)
+    QApplication.sendEvent(canvas.viewport(), event)
+
+
+def _drag(canvas, start, end):
+    _send(canvas, QMouseEvent.Type.MouseButtonPress, start, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, (start + end) / 2, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseMove, end, LEFT)
+    _send(canvas, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
+
+
+def _rotated(window, index):
+    window.canvas.set_selection([index])
+    _press(window, "object.rotate_right")
+    return window.canvas.objects[index].frame_mm()
+
+
+def test_edge_handle_of_rotated_text_turns_fixed_frame_on(window):
+    canvas = window.canvas
+    before = _rotated(window, 0)
+    edge = canvas.handle_points(0)["b"]                    # Höhe auf dem Etikett = Breite ungedreht
+    _drag(canvas, edge, edge + QPointF(0, 10 * canvas.px_per_mm()))
+    obj = window.doc.objects[0]
+    assert obj.fit and obj.rotation == 90
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((before.h + 10, before.w), abs=0.2)
+    after = canvas.objects[0].frame_mm()
+    assert (after.x, after.y, after.w, after.h) == pytest.approx(
+        (before.x, before.y, before.w, before.h + 10), abs=0.2)
+
+
+def test_edge_handle_of_rotated_fixed_frame(window):
+    canvas = window.canvas
+    before = _rotated(window, 2)                            # 20 × 6 mm, gedreht 6 × 20
+    assert (before.w, before.h) == pytest.approx((6, 20), abs=DOT_MM)
+    edge = canvas.handle_points(2)["r"]
+    _drag(canvas, edge, edge + QPointF(4 * canvas.px_per_mm(), 0))
+    obj = window.doc.objects[2]
+    assert (obj.w_mm, obj.h_mm) == pytest.approx((20, 10), abs=0.2)
+    assert canvas.objects[2].frame_mm().w == pytest.approx(10, abs=0.2)
+
+
+def test_corner_handle_of_rotated_text_scales_font(window):
+    canvas = window.canvas
+    before = _rotated(window, 0)
+    corner = canvas.handle_points(0)["br"]
+    rect = canvas.view_rect(0)
+    _drag(canvas, corner, corner + QPointF(rect.width() / 2, rect.height() / 2))
+    obj = window.doc.objects[0]
+    assert obj.size_pt == pytest.approx(21, abs=0.6) and not obj.fit
+    after = canvas.objects[0].frame_mm()
+    assert (after.x, after.y) == pytest.approx((before.x, before.y), abs=0.2)
+    assert after.w == pytest.approx(before.w * 1.5, rel=0.08)
+
+
+# --- Reihenfolge ------------------------------------------------------------------
+def test_bring_forward_and_send_backward_follow_selection(window):
+    window.canvas.set_selection([0])
+    _press(window, "object.bring_forward")
+    assert [o.text for o in window.doc.objects] == ["Zweiter", "Eins", "Drei"]
+    assert window.canvas.selection() == [1]
+    _press(window, "object.bring_forward")
+    assert [o.text for o in window.doc.objects] == ["Zweiter", "Drei", "Eins"]
+    assert window.canvas.selection() == [2]
+    _press(window, "object.send_backward")
+    assert [o.text for o in window.doc.objects] == ["Zweiter", "Eins", "Drei"]
+    assert window.canvas.selection() == [1]
+    assert window.panel("text").edit.toPlainText() == "Eins"   # Panel folgt dem Objekt
+
+
+def test_order_of_several_selected(window):
+    window.canvas.set_selection([1, 0])
+    _press(window, "object.bring_forward")
+    assert [o.text for o in window.doc.objects] == ["Drei", "Eins", "Zweiter"]
+    assert window.canvas.selection() == [2, 1]
+
+
+# --- Rückgängig -------------------------------------------------------------------
+@pytest.mark.parametrize("key", FROM_ONE + FROM_TWO)
+def test_each_operation_is_one_undo_step(window, key):
+    window.canvas.set_selection([1, 2] if key in FROM_TWO else [1])
+    before = [o.text for o in window.doc.objects], _frames(window)
+    _press(window, key)
+    assert window.actions["edit.undo"].isEnabled()
+    window.actions["edit.undo"].trigger()
+    assert ([o.text for o in window.doc.objects], _frames(window)) == before
+    assert not window.actions["edit.undo"].isEnabled()
+
+
+# --- Symbole je Design ------------------------------------------------------------
+def _color(icon: QIcon, mode=QIcon.Mode.Normal, state=QIcon.State.Off):
+    image = icon.pixmap(QSize(16, 16), mode, state).toImage()
+    pixels = [image.pixelColor(x, y) for x in range(16) for y in range(16)]
+    ink = [c for c in pixels if c.alpha() > 200]
+    return {(c.red(), c.green(), c.blue()) for c in ink}
+
+
+def test_icons_turn_white_on_hover_only_in_rawblock(window):
+    button = _panel(window).buttons["align.left"]
+    assert _color(button.icon()) == {(0, 0, 0)}
+    assert _color(button.icon(), QIcon.Mode.Active) == {(255, 255, 255)}
+    window.panel("layout").set_icon_style(False)
+    assert _color(button.icon(), QIcon.Mode.Active) == {(0, 0, 0)}
diff --git a/tests/test_layout.py b/tests/test_layout.py
index 8df4327..8d69364 100644
--- a/tests/test_layout.py
+++ b/tests/test_layout.py
@@ -485,3 +485,134 @@ def test_set_frame_stores_rotated_frame_unrotated():
     obj = TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=20, h_mm=8, rotation=90)
     placed = layout.set_frame(obj, Rect(1, 1, 10, 30), _rendered(1, 1, 8, 20))
     assert (placed.w_mm, placed.h_mm) == (30, 10)
+
+
+# --- Reiter „Layout“: Objekte ausrichten, angleichen, drehen, Reihenfolge -----------
+def _frame(obj, doc=None):
+    rendered = render_object(obj, doc or Document("62", length_mm=40, objects=[obj]))
+    return layout.exact_rect(obj, rendered), rendered
+
+
+def _three():
+    return [TextObject("A", size_pt=12, x_mm=4, y_mm=4),
+            TextObject("Breiter", size_pt=12, x_mm=10, y_mm=15),
+            TextObject("B", size_pt=12, fit=True, x_mm=7, y_mm=25, w_mm=20, h_mm=6)]
+
+
+def _rendered_of(objs):
+    doc = Document("62", length_mm=40, objects=objs)
+    return [render_object(obj, doc) for obj in objs]
+
+
+@pytest.mark.parametrize("mode, attr", [("left", "x"), ("right", "right"), ("hcenter", "cx"),
+                                        ("top", "y"), ("bottom", "bottom"), ("vcenter", "cy")])
+def test_align_objects_to_each_other(mode, attr):
+    objs = _three()
+    rendered = _rendered_of(objs)
+    before = [layout.exact_rect(o, r) for o, r in zip(objs, rendered)]
+    aligned = layout.align_objects(objs, rendered, mode)
+    expected = getattr(layout.align(before, mode)[0], attr)
+    after = [layout.exact_rect(o, r) for o, r in zip(aligned, _rendered_of(aligned))]
+    assert [getattr(r, attr) for r in after] == pytest.approx([expected] * 3, abs=0.001)
+    other = "y" if attr in ("x", "right", "cx") else "x"     # andere Achse bleibt
+    assert [getattr(r, other) for r in after] == pytest.approx([getattr(r, other) for r in before])
+    assert (objs[0].x_mm, objs[0].y_mm) == (4, 4)            # Eingabe bleibt unverändert
+
+
+def test_align_objects_to_paper_uses_area():
+    objs = _three()
+    area = Rect(1, 1.5, 38, 59)
+    aligned = layout.align_objects(objs, _rendered_of(objs), "right", area)
+    after = [layout.exact_rect(o, r) for o, r in zip(aligned, _rendered_of(aligned))]
+    assert [r.right for r in after] == pytest.approx([39] * 3, abs=0.001)
+
+
+def test_align_objects_positions_centered_object_with_its_size():
+    obj = TextObject("Mitte")
+    doc = Document("62", length_mm=40, objects=[obj])
+    rendered = render_object(obj, doc)
+    [aligned] = layout.align_objects([obj], [rendered], "top", Rect(1, 1.5, 38, 59))
+    assert aligned.positioned and aligned.y_mm == pytest.approx(1.5)
+    assert aligned.size_pt == pytest.approx(rendered.base_pt, abs=0.05)
+
+
+def test_match_objects_sets_fixed_frame_to_reference():
+    objs = [TextObject("A", size_pt=12, fit=True, x_mm=1, y_mm=1, w_mm=30, h_mm=10),
+            TextObject("B", size_pt=12, fit=True, x_mm=5, y_mm=20, w_mm=10, h_mm=4)]
+    rendered = _rendered_of(objs)
+    for mode, size in (("same", (30, 10)), ("width", (30, 4)), ("height", (10, 10))):
+        ref, other = layout.match_objects(objs, rendered, mode)
+        assert ref == objs[0]
+        assert (other.w_mm, other.h_mm, other.x_mm, other.y_mm) == (*size, 5, 20)
+
+
+@pytest.mark.parametrize("mode", ["same", "width", "height"])
+def test_match_objects_scales_text_without_fixed_frame(mode):
+    objs = [TextObject("Wort", size_pt=24, x_mm=1, y_mm=1),
+            TextObject("Wort", size_pt=12, x_mm=5, y_mm=30)]
+    ref, other = layout.match_objects(objs, _rendered_of(objs), mode)
+    assert other.size_pt == pytest.approx(24, abs=0.5) and not other.fit
+    assert (other.x_mm, other.y_mm) == (5, 30)                # Ecke bleibt
+
+
+def test_match_objects_keeps_aspect_for_width():
+    objs = [TextObject("Langer Text", size_pt=12, x_mm=1, y_mm=1),
+            TextObject("Kurz", size_pt=12, x_mm=1, y_mm=20)]
+    rendered = _rendered_of(objs)
+    _, other = layout.match_objects(objs, rendered, "width")
+    after = layout.object_rect(_rendered_of([objs[0], other])[1])
+    assert after.w == pytest.approx(layout.object_rect(rendered[0]).w, rel=0.05)
+    assert other.size_pt > 12
+
+
+@pytest.mark.parametrize("fit", [False, True])
+def test_maximize_object_fills_area_centered(fit):
+    obj = TextObject("Wort", size_pt=12, fit=fit, x_mm=2, y_mm=2,
+                     w_mm=10 if fit else None, h_mm=4 if fit else None)
+    doc = Document("62", length_mm=40, objects=[obj])
+    area = layout.printable_area(doc)
+    big = layout.maximize_object(obj, render_object(obj, doc), area, doc)
+    r = layout.object_rect(render_object(big, doc))
+    assert r.x >= area.x - 0.1 and r.right <= area.right + 0.1
+    assert r.y >= area.y - 0.1 and r.bottom <= area.bottom + 0.1
+    assert max(r.w / area.w, r.h / area.h) == pytest.approx(1, abs=0.06)
+    assert (r.cx, r.cy) == pytest.approx((area.cx, area.cy), abs=0.2)
+
+
+@pytest.mark.parametrize("fit", [False, True])
+@pytest.mark.parametrize("start, degrees, end", [(0, 90, 90), (0, -90, 270), (270, 90, 0),
+                                                 (90, -90, 0), (180, 90, 270)])
+def test_rotate_keeps_center(fit, start, degrees, end):
+    obj = TextObject("Drehen", size_pt=12, fit=fit, x_mm=10, y_mm=10, rotation=start,
+                     w_mm=20 if fit else None, h_mm=6 if fit else None)
+    before, rendered = _frame(obj)
+    turned = layout.rotate(obj, rendered, degrees)
+    after, _ = _frame(turned)
+    assert turned.rotation == end
+    assert (after.w, after.h) == pytest.approx((before.h, before.w), abs=0.1)
+    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=0.1)
+    if fit:
+        assert (turned.w_mm, turned.h_mm) == pytest.approx((20, 6))
+
+
+def test_rotate_positions_centered_object():
+    obj = TextObject("Mitte")
+    before, rendered = _frame(obj)
+    turned = layout.rotate(obj, rendered, 90)
+    after, _ = _frame(turned)
+    assert turned.positioned and turned.size_pt is not None
+    assert (after.cx, after.cy) == pytest.approx((before.cx, before.cy), abs=0.1)
+
+
+@pytest.mark.parametrize("indices, step, order, moved", [
+    ([0], 1, "BACD", [1]),
+    ([3], 1, "ABCD", [3]),                  # ganz vorne bleibt vorne
+    ([1, 2], 1, "ADBC", [2, 3]),
+    ([2, 3], 1, "ABCD", [2, 3]),            # blockiert vom vordersten
+    ([2, 0], -1, "ACBD", [1, 0]),           # Indizes in der Reihenfolge der Wahl
+    ([1], -1, "BACD", [0]),
+    ([], 1, "ABCD", []),
+])
+def test_reorder(indices, step, order, moved):
+    items, new = layout.reorder(list("ABCD"), indices, step)
+    assert "".join(items) == order and new == moved
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/icons/align-objects-bottom-black.svg b/src/labelwerk/gui/icons/align-objects-bottom-black.svg
new file mode 100644
index 0000000..9b092c2
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-bottom-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="13" width="16" height="2" fill="#000000"/><rect x="3" y="1" width="4" height="11" fill="#000000"/><rect x="9" y="5" width="4" height="7" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-bottom-white.svg b/src/labelwerk/gui/icons/align-objects-bottom-white.svg
new file mode 100644
index 0000000..fbb065a
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-bottom-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="13" width="16" height="2" fill="#FFFFFF"/><rect x="3" y="1" width="4" height="11" fill="#FFFFFF"/><rect x="9" y="5" width="4" height="7" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-hcenter-black.svg b/src/labelwerk/gui/icons/align-objects-hcenter-black.svg
new file mode 100644
index 0000000..68b563d
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-hcenter-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="7" y="0" width="2" height="16" fill="#000000"/><rect x="1" y="3" width="14" height="4" fill="#000000"/><rect x="3" y="9" width="10" height="4" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-hcenter-white.svg b/src/labelwerk/gui/icons/align-objects-hcenter-white.svg
new file mode 100644
index 0000000..ecd30f9
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-hcenter-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="7" y="0" width="2" height="16" fill="#FFFFFF"/><rect x="1" y="3" width="14" height="4" fill="#FFFFFF"/><rect x="3" y="9" width="10" height="4" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-left-black.svg b/src/labelwerk/gui/icons/align-objects-left-black.svg
new file mode 100644
index 0000000..e27c1b3
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-left-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1" y="0" width="2" height="16" fill="#000000"/><rect x="4" y="3" width="11" height="4" fill="#000000"/><rect x="4" y="9" width="7" height="4" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-left-white.svg b/src/labelwerk/gui/icons/align-objects-left-white.svg
new file mode 100644
index 0000000..1ccf92c
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-left-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1" y="0" width="2" height="16" fill="#FFFFFF"/><rect x="4" y="3" width="11" height="4" fill="#FFFFFF"/><rect x="4" y="9" width="7" height="4" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-right-black.svg b/src/labelwerk/gui/icons/align-objects-right-black.svg
new file mode 100644
index 0000000..a982e88
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-right-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="13" y="0" width="2" height="16" fill="#000000"/><rect x="1" y="3" width="11" height="4" fill="#000000"/><rect x="5" y="9" width="7" height="4" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-right-white.svg b/src/labelwerk/gui/icons/align-objects-right-white.svg
new file mode 100644
index 0000000..0f24d94
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-right-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="13" y="0" width="2" height="16" fill="#FFFFFF"/><rect x="1" y="3" width="11" height="4" fill="#FFFFFF"/><rect x="5" y="9" width="7" height="4" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-top-black.svg b/src/labelwerk/gui/icons/align-objects-top-black.svg
new file mode 100644
index 0000000..56e8f89
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-top-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="1" width="16" height="2" fill="#000000"/><rect x="3" y="4" width="4" height="11" fill="#000000"/><rect x="9" y="4" width="4" height="7" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-top-white.svg b/src/labelwerk/gui/icons/align-objects-top-white.svg
new file mode 100644
index 0000000..0448543
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-top-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="1" width="16" height="2" fill="#FFFFFF"/><rect x="3" y="4" width="4" height="11" fill="#FFFFFF"/><rect x="9" y="4" width="4" height="7" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-vcenter-black.svg b/src/labelwerk/gui/icons/align-objects-vcenter-black.svg
new file mode 100644
index 0000000..5f1c8f6
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-vcenter-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="7" width="16" height="2" fill="#000000"/><rect x="3" y="1" width="4" height="14" fill="#000000"/><rect x="9" y="3" width="4" height="10" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-objects-vcenter-white.svg b/src/labelwerk/gui/icons/align-objects-vcenter-white.svg
new file mode 100644
index 0000000..4d6ef67
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-objects-vcenter-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="7" width="16" height="2" fill="#FFFFFF"/><rect x="3" y="1" width="4" height="14" fill="#FFFFFF"/><rect x="9" y="3" width="4" height="10" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-bottom-black.svg b/src/labelwerk/gui/icons/align-paper-bottom-black.svg
new file mode 100644
index 0000000..f6556a1
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-bottom-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#000000" stroke-width="1"/><rect x="4" y="10" width="8" height="4" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-bottom-white.svg b/src/labelwerk/gui/icons/align-paper-bottom-white.svg
new file mode 100644
index 0000000..5bcdda3
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-bottom-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="4" y="10" width="8" height="4" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-hcenter-black.svg b/src/labelwerk/gui/icons/align-paper-hcenter-black.svg
new file mode 100644
index 0000000..bfa3de3
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-hcenter-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#000000" stroke-width="1"/><rect x="7" y="1" width="2" height="2" fill="#000000"/><rect x="7" y="13" width="2" height="2" fill="#000000"/><rect x="6" y="4" width="4" height="8" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-hcenter-white.svg b/src/labelwerk/gui/icons/align-paper-hcenter-white.svg
new file mode 100644
index 0000000..235e235
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-hcenter-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="7" y="1" width="2" height="2" fill="#FFFFFF"/><rect x="7" y="13" width="2" height="2" fill="#FFFFFF"/><rect x="6" y="4" width="4" height="8" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-left-black.svg b/src/labelwerk/gui/icons/align-paper-left-black.svg
new file mode 100644
index 0000000..a0ad362
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-left-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#000000" stroke-width="1"/><rect x="2" y="4" width="4" height="8" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-left-white.svg b/src/labelwerk/gui/icons/align-paper-left-white.svg
new file mode 100644
index 0000000..b4657ab
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-left-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="2" y="4" width="4" height="8" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-right-black.svg b/src/labelwerk/gui/icons/align-paper-right-black.svg
new file mode 100644
index 0000000..5b8721c
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-right-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#000000" stroke-width="1"/><rect x="10" y="4" width="4" height="8" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-right-white.svg b/src/labelwerk/gui/icons/align-paper-right-white.svg
new file mode 100644
index 0000000..f1ec762
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-right-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="10" y="4" width="4" height="8" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-top-black.svg b/src/labelwerk/gui/icons/align-paper-top-black.svg
new file mode 100644
index 0000000..f839125
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-top-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#000000" stroke-width="1"/><rect x="4" y="2" width="8" height="4" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-top-white.svg b/src/labelwerk/gui/icons/align-paper-top-white.svg
new file mode 100644
index 0000000..254732f
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-top-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="4" y="2" width="8" height="4" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-vcenter-black.svg b/src/labelwerk/gui/icons/align-paper-vcenter-black.svg
new file mode 100644
index 0000000..6067a4d
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-vcenter-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#000000" stroke-width="1"/><rect x="1" y="7" width="2" height="2" fill="#000000"/><rect x="13" y="7" width="2" height="2" fill="#000000"/><rect x="4" y="6" width="8" height="4" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/align-paper-vcenter-white.svg b/src/labelwerk/gui/icons/align-paper-vcenter-white.svg
new file mode 100644
index 0000000..22282a7
--- /dev/null
+++ b/src/labelwerk/gui/icons/align-paper-vcenter-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="1" y="7" width="2" height="2" fill="#FFFFFF"/><rect x="13" y="7" width="2" height="2" fill="#FFFFFF"/><rect x="4" y="6" width="8" height="4" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/order-backward-black.svg b/src/labelwerk/gui/icons/order-backward-black.svg
new file mode 100644
index 0000000..b4da87e
--- /dev/null
+++ b/src/labelwerk/gui/icons/order-backward-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1" y="1" width="9" height="9" fill="#000000"/><rect x="6.5" y="6.5" width="8" height="8" fill="#FFFFFF" stroke="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/order-backward-white.svg b/src/labelwerk/gui/icons/order-backward-white.svg
new file mode 100644
index 0000000..fb27434
--- /dev/null
+++ b/src/labelwerk/gui/icons/order-backward-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1" y="1" width="9" height="9" fill="#FFFFFF"/><rect x="6.5" y="6.5" width="8" height="8" fill="#000000" stroke="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/order-forward-black.svg b/src/labelwerk/gui/icons/order-forward-black.svg
new file mode 100644
index 0000000..f400229
--- /dev/null
+++ b/src/labelwerk/gui/icons/order-forward-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="8" height="8" fill="#FFFFFF" stroke="#000000"/><rect x="6" y="6" width="9" height="9" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/order-forward-white.svg b/src/labelwerk/gui/icons/order-forward-white.svg
new file mode 100644
index 0000000..617f844
--- /dev/null
+++ b/src/labelwerk/gui/icons/order-forward-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="8" height="8" fill="#000000" stroke="#FFFFFF"/><rect x="6" y="6" width="9" height="9" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/rotate-left-black.svg b/src/labelwerk/gui/icons/rotate-left-black.svg
new file mode 100644
index 0000000..08e13e6
--- /dev/null
+++ b/src/labelwerk/gui/icons/rotate-left-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M11.5 12.5 A5 5 0 1 0 3 9" fill="none" stroke="#000000" stroke-width="2"/><path d="M-0.2 8 L6.2 8 L3 12.5 Z" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/rotate-left-white.svg b/src/labelwerk/gui/icons/rotate-left-white.svg
new file mode 100644
index 0000000..133096b
--- /dev/null
+++ b/src/labelwerk/gui/icons/rotate-left-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M11.5 12.5 A5 5 0 1 0 3 9" fill="none" stroke="#FFFFFF" stroke-width="2"/><path d="M-0.2 8 L6.2 8 L3 12.5 Z" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/rotate-right-black.svg b/src/labelwerk/gui/icons/rotate-right-black.svg
new file mode 100644
index 0000000..8e1561e
--- /dev/null
+++ b/src/labelwerk/gui/icons/rotate-right-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M4.5 12.5 A5 5 0 1 1 13 9" fill="none" stroke="#000000" stroke-width="2"/><path d="M9.8 8 L16.2 8 L13 12.5 Z" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/rotate-right-white.svg b/src/labelwerk/gui/icons/rotate-right-white.svg
new file mode 100644
index 0000000..7f1d63e
--- /dev/null
+++ b/src/labelwerk/gui/icons/rotate-right-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M4.5 12.5 A5 5 0 1 1 13 9" fill="none" stroke="#FFFFFF" stroke-width="2"/><path d="M9.8 8 L16.2 8 L13 12.5 Z" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/size-height-black.svg b/src/labelwerk/gui/icons/size-height-black.svg
new file mode 100644
index 0000000..4e64647
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-height-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="0" width="16" height="1" fill="#000000"/><rect x="0" y="15" width="16" height="1" fill="#000000"/><rect x="3" y="2" width="4" height="12" fill="#000000"/><rect x="9" y="2" width="4" height="12" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/size-height-white.svg b/src/labelwerk/gui/icons/size-height-white.svg
new file mode 100644
index 0000000..5e5fc7e
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-height-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="0" width="16" height="1" fill="#FFFFFF"/><rect x="0" y="15" width="16" height="1" fill="#FFFFFF"/><rect x="3" y="2" width="4" height="12" fill="#FFFFFF"/><rect x="9" y="2" width="4" height="12" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/size-maximize-black.svg b/src/labelwerk/gui/icons/size-maximize-black.svg
new file mode 100644
index 0000000..817551a
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-maximize-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#000000" stroke-width="1"/><rect x="5" y="5" width="6" height="6" fill="#000000"/><path d="M1 8 L4 5 L4 11 Z" fill="#000000"/><path d="M15 8 L12 5 L12 11 Z" fill="#000000"/><path d="M8 1 L5 4 L11 4 Z" fill="#000000"/><path d="M8 15 L5 12 L11 12 Z" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/size-maximize-white.svg b/src/labelwerk/gui/icons/size-maximize-white.svg
new file mode 100644
index 0000000..cad5716
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-maximize-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0.5" y="0.5" width="15" height="15" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="5" y="5" width="6" height="6" fill="#FFFFFF"/><path d="M1 8 L4 5 L4 11 Z" fill="#FFFFFF"/><path d="M15 8 L12 5 L12 11 Z" fill="#FFFFFF"/><path d="M8 1 L5 4 L11 4 Z" fill="#FFFFFF"/><path d="M8 15 L5 12 L11 12 Z" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/size-same-black.svg b/src/labelwerk/gui/icons/size-same-black.svg
new file mode 100644
index 0000000..e8b18cd
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-same-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1" y="4" width="6" height="6" fill="#000000"/><rect x="9" y="4" width="6" height="6" fill="#000000"/><rect x="1" y="1" width="14" height="1" fill="#000000"/><rect x="1" y="0" width="1" height="3" fill="#000000"/><rect x="14" y="0" width="1" height="3" fill="#000000"/><rect x="1" y="13" width="14" height="1" fill="#000000"/><rect x="1" y="12" width="1" height="3" fill="#000000"/><rect x="14" y="12" width="1" height="3" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/size-same-white.svg b/src/labelwerk/gui/icons/size-same-white.svg
new file mode 100644
index 0000000..71df563
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-same-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1" y="4" width="6" height="6" fill="#FFFFFF"/><rect x="9" y="4" width="6" height="6" fill="#FFFFFF"/><rect x="1" y="1" width="14" height="1" fill="#FFFFFF"/><rect x="1" y="0" width="1" height="3" fill="#FFFFFF"/><rect x="14" y="0" width="1" height="3" fill="#FFFFFF"/><rect x="1" y="13" width="14" height="1" fill="#FFFFFF"/><rect x="1" y="12" width="1" height="3" fill="#FFFFFF"/><rect x="14" y="12" width="1" height="3" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/size-width-black.svg b/src/labelwerk/gui/icons/size-width-black.svg
new file mode 100644
index 0000000..de7815f
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-width-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="0" width="1" height="16" fill="#000000"/><rect x="15" y="0" width="1" height="16" fill="#000000"/><rect x="2" y="3" width="12" height="4" fill="#000000"/><rect x="2" y="9" width="12" height="4" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/size-width-white.svg b/src/labelwerk/gui/icons/size-width-white.svg
new file mode 100644
index 0000000..45357e7
--- /dev/null
+++ b/src/labelwerk/gui/icons/size-width-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="0" y="0" width="1" height="16" fill="#FFFFFF"/><rect x="15" y="0" width="1" height="16" fill="#FFFFFF"/><rect x="2" y="3" width="12" height="4" fill="#FFFFFF"/><rect x="2" y="9" width="12" height="4" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index cf8d959..ea9875f 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -16,8 +16,9 @@ from ..detect import brother_busy, find_brother_lp
 from ..document import Document, TextObject
 from ..fonts import DEFAULT_FAMILY
 from ..labels import get_label
-from ..layout import (Rect, exact_rect, move, object_rect, objects_outside, printable_area,
-                      resize, set_frame)
+from ..layout import (ALIGN_MODES, SIZE_MODES, Rect, align_objects, exact_rect, match_objects,
+                      maximize_object, move, object_rect, objects_outside, printable_area,
+                      reorder, resize, rotate, set_frame)
 from ..printer import DEFAULT_MODEL
 from ..render import RenderedObject, compose, font_warnings, label_size, render_object
 from ..settings import Settings, load_settings, new_document
@@ -45,6 +46,7 @@ EDIT_BAR = (("tool.select", "edit-select", "↖"), ("tool.text", None, "A"), Non
             ("edit.paste", "edit-paste", "EINFÜGEN"), None,
             ("edit.undo", "edit-undo", "↶"), ("edit.redo", "edit-redo", "↷"))
 _SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
+SELECTION_PANELS = ("text", "layout")   # arbeiten mit der Auswahl: Wählen wechselt nicht weg
 
 
 @dataclass
@@ -117,7 +119,6 @@ class MainWindow(QMainWindow):
         # Arbeitsfläche
         self.canvas = Canvas(model)
         self.canvas.set_zoom(self.settings.start_zoom)
-        self.apply_theme_icons()
         self.canvas.length_changed.connect(self._on_length_dragged)
         self.canvas.drag_finished.connect(self._length_drag_finished)
         self.canvas.objects_moved.connect(self._move_objects)
@@ -129,7 +130,11 @@ class MainWindow(QMainWindow):
         self.history.changed.connect(self._update_edit_actions)
         self.actions = build_actions(self, effective(self.settings.shortcuts))
         self._connect_canvas_actions()
+        self._connect_layout_actions()
         self._build_edit_bar()
+        for panel in self._panel_by_key.values():
+            panel.use_actions(self.actions)
+        self.apply_theme_icons()
         central = QWidget()
         layout = QHBoxLayout(central)
         layout.setContentsMargins(0, 0, 0, 0)
@@ -211,6 +216,22 @@ class MainWindow(QMainWindow):
         self.actions["edit.redo"].triggered.connect(self.redo)
         self.addActions([self.actions["edit.undo"], self.actions["edit.redo"]])
 
+    def _connect_layout_actions(self) -> None:
+        """Reiter „Layout“: Ausrichten, Größe angleichen, Drehen, Reihenfolge (auch per Kürzel)."""
+        handlers = {"size.maximize": self.maximize_selected,
+                    "object.rotate_left": lambda: self.rotate_selected(-90),
+                    "object.rotate_right": lambda: self.rotate_selected(90),
+                    "object.bring_forward": lambda: self.reorder_selected(1),
+                    "object.send_backward": lambda: self.reorder_selected(-1)}
+        for mode in ALIGN_MODES:
+            handlers[f"align.{mode}"] = lambda m=mode: self.align_selected(m)
+            handlers[f"align.paper_{mode}"] = lambda m=mode: self.align_selected(m, paper=True)
+        for mode in SIZE_MODES:
+            handlers[f"size.{mode}"] = lambda m=mode: self.match_selected(m)
+        for key, handler in handlers.items():
+            self.actions[key].triggered.connect(lambda _=False, h=handler: h())
+            self.canvas.addAction(self.actions[key])
+
     def _build_edit_bar(self) -> None:
         """Bearbeitungsleiste unter der Werkzeugleiste: Werkzeug, Zwischenablage, Rückgängig."""
         bar = QToolBar("Bearbeiten")
@@ -255,13 +276,20 @@ class MainWindow(QMainWindow):
             self.canvas.set_tool("text")
 
     def _on_selection(self, indices: list[int]) -> None:
-        """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen (Papier-Reiter behält sie)."""
+        """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen – außer ein Panel, das mit
+        der Auswahl arbeitet (Text, Layout), ist schon zu sehen."""
         self._follow_selection(indices)
         if indices:
+            self._show_object_panel()
+
+    def _show_object_panel(self) -> None:
+        if not any(self.panels.currentWidget() is self.panel(key) for key in SELECTION_PANELS):
             self._show_tool("text")
 
     def _follow_selection(self, indices: list[int]) -> None:
-        """Text-Panel bearbeitet das zuletzt gewählte Objekt."""
+        """Panels erfahren die Auswahl; das Text-Panel bearbeitet das zuletzt gewählte Objekt."""
+        for panel in self._panel_by_key.values():
+            panel.set_selection(indices)
         self.panel("text").set_object(indices[-1] if indices else None)
         self._update_frame()
 
@@ -435,6 +463,52 @@ class MainWindow(QMainWindow):
         self._objects_changed([index])
         self._commit()
 
+    # --- Reiter „Layout“ ---------------------------------------------------
+    def align_selected(self, mode: str, paper: bool = False) -> None:
+        """Auswahl aneinander bzw. am bedruckbaren Bereich ausrichten."""
+        area = printable_area(self.doc, self.model) if paper else None
+        self._change_selected(lambda objs, rendered: align_objects(objs, rendered, mode, area))
+
+    def match_selected(self, mode: str) -> None:
+        """Größe, Breite oder Höhe an das zuerst gewählte Objekt angleichen."""
+        self._change_selected(lambda objs, rendered: match_objects(objs, rendered, mode))
+
+    def maximize_selected(self) -> None:
+        """Jedes gewählte Objekt so groß wie möglich mittig in den bedruckbaren Bereich."""
+        area = printable_area(self.doc, self.model)
+        self._change_selected(lambda objs, rendered: [
+            maximize_object(obj, r, area, self.doc, self.model) for obj, r in zip(objs, rendered)])
+
+    def rotate_selected(self, degrees: int) -> None:
+        """Auswahl um 90° drehen (−90 = links); die Mitte jedes Objekts bleibt."""
+        self._change_selected(lambda objs, rendered: [
+            rotate(obj, r, degrees) for obj, r in zip(objs, rendered)])
+
+    def _change_selected(self, change) -> None:
+        """Gewählte Objekte durch ``change(objekte, gerendert)`` ersetzen – ein Schritt."""
+        if self._timer.isActive():
+            self.render_now()                   # z. B. eben Getipptes: aktuelle Rahmen
+        indices = [i for i in self.canvas.selection() if i < len(self.rendered)]
+        if not indices:
+            return
+        self._commit()
+        changed = change([self.doc.objects[i] for i in indices], [self.rendered[i] for i in indices])
+        for index, obj in zip(indices, changed):
+            self.doc.objects[index] = obj
+        self._objects_changed(indices)
+        self._commit()
+
+    def reorder_selected(self, step: int) -> None:
+        """Auswahl einen Platz nach vorne (1) bzw. hinten (−1); die Auswahl wandert mit."""
+        indices = self.canvas.selection()
+        if not indices:
+            return
+        self._commit()
+        self.doc.objects[:], moved = reorder(self.doc.objects, indices, step)
+        self.render_now()
+        self.canvas.set_selection(moved)
+        self._commit()
+
     # --- Zwischenablage ---------------------------------------------------
     def copy_selected(self) -> None:
         """Ausgewählte Objekte (in Zeichenreihenfolge) in die interne Zwischenablage kopieren."""
@@ -543,7 +617,9 @@ class MainWindow(QMainWindow):
     # --- Einstellungen ----------------------------------------------------
     def apply_theme_icons(self) -> None:
         """Symbole, die vom Design abhängen (weiß auf schwarz nur bei RawBlock)."""
-        self.panel("text").set_icon_style(self.settings.theme == "rawblock")
+        dark = self.settings.theme == "rawblock"
+        for panel in self._panel_by_key.values():
+            panel.set_icon_style(dark)
 
     def open_settings(self) -> None:
         dialog = SettingsDialog(self.settings, model=self.model, parent=self)
diff --git a/src/labelwerk/gui/panels/__init__.py b/src/labelwerk/gui/panels/__init__.py
index ff36e3e..8ef5b00 100644
--- a/src/labelwerk/gui/panels/__init__.py
+++ b/src/labelwerk/gui/panels/__init__.py
@@ -2,6 +2,7 @@
 from __future__ import annotations
 
 from PySide6.QtCore import Signal
+from PySide6.QtGui import QAction
 from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
 
 from ...document import Document
@@ -36,3 +37,12 @@ class Panel(QWidget):
 
     def show_error(self, message: str | None) -> None:
         """Fehlermeldung anzeigen bzw. mit None löschen (nur wo sinnvoll)."""
+
+    def set_selection(self, indices: list[int]) -> None:
+        """Auswahl auf der Arbeitsfläche hat sich geändert (Indizes in der Reihenfolge der Wahl)."""
+
+    def use_actions(self, actions: dict[str, QAction]) -> None:
+        """Aktionen des Hauptfensters (``gui.actions``) für eigene Knöpfe übernehmen."""
+
+    def set_icon_style(self, dark_checked: bool) -> None:
+        """Symbole an das Design anpassen (weiß auf schwarz nur bei RawBlock)."""
diff --git a/src/labelwerk/gui/panels/layout.py b/src/labelwerk/gui/panels/layout.py
new file mode 100644
index 0000000..847f01a
--- /dev/null
+++ b/src/labelwerk/gui/panels/layout.py
@@ -0,0 +1,75 @@
+"""Panel „Layout“: gewählte Objekte ausrichten, Größe angleichen, drehen, Reihenfolge – wie P-touch.
+
+Die Knöpfe lösen die Aktionen des Hauptfensters aus (Kürzel-Verzeichnis, Kürzel im Tooltip);
+gerechnet wird im Kern (``layout``). Ohne passende Auswahl sind die Knöpfe gesperrt.
+"""
+from __future__ import annotations
+
+from PySide6.QtGui import QAction
+from PySide6.QtWidgets import QHBoxLayout, QToolButton
+
+from ...document import Document
+from ..symbols import SIZE, line_icon
+from . import Panel
+
+# Bereiche mit Knöpfen: (Aktion, Symbol)
+LAYOUT_SECTIONS = (
+    ("Gewählte Objekte ausrichten", tuple((f"align.{mode}", f"align-objects-{mode}") for mode in
+                                          ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
+    ("Am Papier ausrichten", tuple((f"align.paper_{mode}", f"align-paper-{mode}") for mode in
+                                   ("left", "hcenter", "right", "top", "vcenter", "bottom"))),
+    ("Vergrößern/Verkleinern", (("size.maximize", "size-maximize"), ("size.same", "size-same"),
+                                ("size.width", "size-width"), ("size.height", "size-height"))),
+    ("Drehen", (("object.rotate_left", "rotate-left"), ("object.rotate_right", "rotate-right"))),
+    ("Reihenfolge", (("object.bring_forward", "order-forward"),
+                     ("object.send_backward", "order-backward"))),
+)
+_ICONS = {key: icon for _, row in LAYOUT_SECTIONS for key, icon in row}
+# Aneinander ausrichten und angleichen braucht mindestens zwei Objekte, alles andere eins
+_FROM_TWO = {key for key, _ in LAYOUT_SECTIONS[0][1]} | {"size.same", "size.width", "size.height"}
+MIN_SELECTED = {key: 2 if key in _FROM_TWO else 1 for key in _ICONS}
+
+
+class LayoutPanel(Panel):
+    def __init__(self, doc: Document):
+        super().__init__(doc, "Layout")
+        self._dark = True
+        self._count = 0
+        self.buttons: dict[str, QToolButton] = {}
+        for title, row in LAYOUT_SECTIONS:
+            # lange Überschriften brechen an Leerzeichen um; ohne Leerzeichen nicht, sonst
+            # reserviert Qt bei „/“ eine zweite Zeile
+            self.section(title).setWordWrap(" " in title)
+            line = QHBoxLayout()
+            line.setSpacing(4)
+            for key, _ in row:
+                button = QToolButton()
+                button.setObjectName("layoutButton")
+                button.setAutoRaise(True)              # Symbol beim Darüberfahren: Modus „Active“
+                button.setIconSize(SIZE)
+                button.setEnabled(False)
+                self.buttons[key] = button
+                line.addWidget(button)
+            line.addStretch()
+            self.layout_.addLayout(line)
+        self.layout_.addStretch()
+
+    def use_actions(self, actions: dict[str, QAction]) -> None:
+        for key, button in self.buttons.items():
+            button.setDefaultAction(actions[key])
+        self.set_icon_style(self._dark)
+        self._enable()
+
+    def set_selection(self, indices: list[int]) -> None:
+        self._count = len(indices)
+        self._enable()
+
+    def _enable(self) -> None:
+        for key, button in self.buttons.items():
+            (button.defaultAction() or button).setEnabled(self._count >= MIN_SELECTED[key])
+
+    def set_icon_style(self, dark_checked: bool) -> None:
+        self._dark = dark_checked
+        for key, button in self.buttons.items():
+            target = button.defaultAction() or button
+            target.setIcon(line_icon(_ICONS[key], dark_checked, hover=True))
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index f634f8c..f8a13fe 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -7,8 +7,6 @@ und (mit fester Rahmengröße) Größe des Rahmens in mm.
 from __future__ import annotations
 
 import math
-from importlib import resources
-
 from PySide6.QtCore import QSize, Qt, Signal
 from PySide6.QtGui import (QFont, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextFormat,
                            QTextOption)
@@ -19,6 +17,7 @@ from ...document import MAX_PT, MIN_PT, Document, Paragraph, Span, TextObject
 from ...fonts import DEFAULT_FAMILY
 from ...layout import Rect
 from ...render import REF_PT
+from ..symbols import line_icon
 from ..widgets import DoubleSpinBox
 from . import Panel
 
@@ -68,14 +67,8 @@ def _button(text: str, tip: str, checkable: bool = True) -> QPushButton:
 
 
 def _align_icon(key: str, dark_checked: bool = True) -> QIcon:
-    """Liniensymbol: schwarz im Normalzustand, weiß auf dem schwarzen Hintergrund gewählter Knöpfe
-    (RawBlock); im klassischen Design bleibt der gewählte Knopf hell, also auch schwarz."""
-    folder = resources.files("labelwerk.gui") / "icons"
-    icon = QIcon()
-    for color, state in (("black", QIcon.State.Off), ("white" if dark_checked else "black", QIcon.State.On)):
-        path = str(folder / f"align-{key}-{color}.svg")
-        icon.addFile(path, QSize(), QIcon.Mode.Normal, state)
-    return icon
+    """Liniensymbol der Textposition; gewählt weiß auf schwarz nur bei RawBlock."""
+    return line_icon(f"align-{key}", dark_checked)
 
 
 class TextPanel(Panel):
diff --git a/src/labelwerk/gui/symbols.py b/src/labelwerk/gui/symbols.py
new file mode 100644
index 0000000..fc17200
--- /dev/null
+++ b/src/labelwerk/gui/symbols.py
@@ -0,0 +1,33 @@
+"""Eigene Liniensymbole (``gui/icons/<name>-black.svg`` / ``-white.svg``, 16 × 16).
+
+Schwarz im Normalzustand; im Design RawBlock weiß, wo der Knopf schwarz hinterlegt ist
+(gewählt bzw. beim Darüberfahren). Im klassischen Design bleibt der Knopf hell, also schwarz.
+"""
+from __future__ import annotations
+
+from importlib import resources
+
+from PySide6.QtCore import QSize
+from PySide6.QtGui import QIcon
+
+SIZE = QSize(16, 16)
+
+
+def line_icon(name: str, dark: bool = True, hover: bool = False) -> QIcon:
+    """Symbol ``name``; ``dark``: gewählt weiß auf schwarz (RawBlock).
+
+    ``hover``: auch beim Darüberfahren weiß – für Knöpfe, die dann schwarz werden und den
+    Modus „Active“ nur beim Darüberfahren nutzen (QToolButton mit autoRaise, Werkzeugleisten).
+    """
+    folder = resources.files("labelwerk.gui") / "icons"
+
+    def path(color: str) -> str:
+        return str(folder / f"{name}-{color}.svg")
+    light = "white" if dark else "black"
+    icon = QIcon()
+    icon.addFile(path("black"), QSize(), QIcon.Mode.Normal, QIcon.State.Off)
+    icon.addFile(path(light), QSize(), QIcon.Mode.Normal, QIcon.State.On)
+    if hover:
+        icon.addFile(path(light), QSize(), QIcon.Mode.Active, QIcon.State.Off)
+        icon.addFile(path(light), QSize(), QIcon.Mode.Active, QIcon.State.On)
+    return icon
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index 997ca99..2c5cfd5 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -107,10 +107,14 @@ QPushButton#formatButton { padding: 4px 8px; min-width: 22px; }
 QPushButton#formatButton:checked { background: #000000; color: #FFFFFF; }
 QPushButton#formatButton[style="italic"] { font-style: italic; }
 QPushButton#formatButton[style="underline"] { text-decoration: underline; }
-QTextEdit { background: #F0F0F0; border: 3px solid #000000; border-radius: 0; padding: 4px; }
+QTextEdit { background: #F0F0F0; border: 3px solid #000000; border-radius: 0; padding: 6px; }
 QTextEdit:focus { border-width: 5px; }
 QTextEdit:disabled { border-color: #CCCCCC; background: #F5F5F5; }
 QFontComboBox { min-width: 0; }
+/* Reiter Layout: Symbolknöpfe; beim Darüberfahren schwarz, das Symbol wird dann weiß */
+QToolButton#layoutButton { background: #FFFFFF; border: 3px solid #000000; border-radius: 0; padding: 6px; }
+QToolButton#layoutButton:hover { background: #000000; }
+QToolButton#layoutButton:disabled { background: #F0F0F0; border-color: #CCCCCC; }
 
 QStatusBar { border-top: 3px solid #000000; }
 QStatusBar QLabel[state="ok"] { color: #008000; font-weight: 700; }
diff --git a/src/labelwerk/gui/tools.py b/src/labelwerk/gui/tools.py
index 477841b..01d7666 100644
--- a/src/labelwerk/gui/tools.py
+++ b/src/labelwerk/gui/tools.py
@@ -9,6 +9,7 @@ from typing import Callable
 
 from ..document import Document
 from .panels import Panel
+from .panels.layout import LayoutPanel
 from .panels.paper import PaperPanel
 from .panels.text import TextPanel
 
@@ -24,4 +25,5 @@ class Tool:
 TOOLS = [
     Tool("paper", "Papier", "document-page-setup", PaperPanel),
     Tool("text", "Text", "insert-text", TextPanel),
+    Tool("layout", "Layout", "align-horizontal-left", LayoutPanel),
 ]
diff --git a/src/labelwerk/layout.py b/src/labelwerk/layout.py
index e34f14f..50068a0 100644
--- a/src/labelwerk/layout.py
+++ b/src/labelwerk/layout.py
@@ -301,3 +301,96 @@ def objects_outside(doc: Document, model: str = "QL-600") -> list[int]:
         if r.x < 0 or r.y < 0 or r.x + r.w > width or r.y + r.h > height:
             outside.append(i)
     return outside
+
+
+# --- Reiter „Layout“ ----------------------------------------------------------------
+def align_objects(objs: list[TextObject], rendered: list[RenderedObject], mode: str,
+                  area: Rect | None = None) -> list[TextObject]:
+    """Kopien der Objekte, ausgerichtet wie ``align`` – mit ``area`` am Papier, sonst aneinander.
+
+    Gerechnet wird mit den Rahmen, wie sie im Modell stehen (``exact_rect``); ein Objekt ohne
+    Position bekommt seine Lage und wirksame Schriftgröße fest.
+    """
+    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
+    return [set_frame(o, _rounded(rect), r)
+            for o, r, rect in zip(objs, rendered, align(rects, mode, area))]
+
+
+def match_objects(objs: list[TextObject], rendered: list[RenderedObject],
+                  mode: str) -> list[TextObject]:
+    """Kopien mit der Größe des ersten Objekts (``same``, ``width``, ``height``); Ecke bleibt.
+
+    Mit fester Rahmengröße wird der Rahmen gesetzt. Text ohne feste Rahmengröße wird
+    skaliert (Seitenverhältnis bleibt): bei „gleicher Größe“ mit dem Mittel aus Breiten-
+    und Höhenverhältnis, sonst nach dem angeglichenen Maß.
+    """
+    rects = [exact_rect(o, r) for o, r in zip(objs, rendered)]
+    result = [copy.deepcopy(objs[0])] if objs else []
+    for obj, r, old, new in zip(objs[1:], rendered[1:], rects[1:], match_size(rects, mode)[1:]):
+        if obj.fit:
+            result.append(set_frame(obj, _rounded(new), r))
+            continue
+        fx = new.w / old.w if old.w else 1.0
+        fy = new.h / old.h if old.h else 1.0
+        factor = {"same": (fx * fy) ** 0.5, "width": fx, "height": fy}[mode]
+        result.append(place(scale_text(obj, factor, base_pt=r.base_pt), _rounded(old)))
+    return result
+
+
+def maximize_object(obj: TextObject, rendered: RenderedObject, area: Rect, doc: Document,
+                    model: str = "QL-600") -> TextObject:
+    """Kopie, so groß wie möglich mittig in ``area`` (Seitenverhältnis bleibt).
+
+    Mit fester Rahmengröße wird der Rahmen gesetzt; sonst wird die Schrift skaliert und
+    das Ergebnis gerendert, damit es sicher hineinpasst und genau mittig steht.
+    """
+    if obj.fit:
+        return set_frame(obj, _rounded(maximize(exact_rect(obj, rendered), area)), rendered)
+    shown = object_rect(rendered)
+    factor = maximize(shown, area).w / shown.w if shown.w else 1.0
+    scaled = scale_text(obj, factor, base_pt=rendered.base_pt)
+    for _ in range(5):                       # Schrift wächst nicht ganz linear: nachregeln
+        scaled.x_mm, scaled.y_mm = area.x, area.y
+        size = object_rect(render_object(scaled, doc, model))
+        over = min(area.w / size.w, area.h / size.h) if size.w and size.h else 1.0
+        if over >= 1 or scaled.size_pt <= MIN_PT:
+            break
+        scaled = scale_text(scaled, over * 0.995)
+    return place(scaled, _rounded(Rect(area.cx - size.w / 2, area.cy - size.h / 2,
+                                       size.w, size.h)))
+
+
+def rotate(obj: TextObject, rendered: RenderedObject, degrees: int) -> TextObject:
+    """Kopie, um ``degrees`` (±90, im Uhrzeigersinn) gedreht; die Mitte des Rahmens bleibt.
+
+    Ein Objekt ohne Position bekommt seine Lage und wirksame Schriftgröße fest.
+    """
+    old = exact_rect(obj, rendered)
+    if not obj.fit and obj.size_pt is None:
+        obj = fix_size(obj, rendered.base_pt)
+    turned = copy.deepcopy(obj)
+    turned.rotation = (obj.rotation + degrees) % 360
+    w, h = (old.h, old.w) if degrees % 180 else (old.w, old.h)
+    return place(turned, _rounded(Rect(old.cx - w / 2, old.cy - h / 2, w, h)))
+
+
+def reorder(items: list, indices: list[int], step: int) -> tuple[list, list[int]]:
+    """Ausgewählte Einträge um einen Platz nach vorne (``step`` 1) bzw. hinten (−1) schieben.
+
+    Liste = Zeichenreihenfolge (hinten → vorne). Ein Eintrag rückt nur an einem nicht
+    ausgewählten vorbei; Ausgewählte am Ende bleiben stehen. Liefert die neue Liste und die
+    neuen Plätze von ``indices`` (in derselben Reihenfolge).
+    """
+    order = list(range(len(items)))
+    chosen = set(indices)
+    positions = range(len(order) - 2, -1, -1) if step > 0 else range(1, len(order))
+    for pos in positions:
+        other = pos + (1 if step > 0 else -1)
+        if order[pos] in chosen and order[other] not in chosen:
+            order[pos], order[other] = order[other], order[pos]
+    return [items[i] for i in order], [order.index(i) for i in indices]
+
+
+def _rounded(rect: Rect) -> Rect:
+    """Rahmen fürs Modell: auf 1/1000 mm gerundet."""
+    return Rect(*(round(v, _DECIMALS) for v in (rect.x, rect.y, rect.w, rect.h)))
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `655 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/icons/align-objects-bottom-black.svg src/labelwerk/gui/icons/align-objects-bottom-white.svg src/labelwerk/gui/icons/align-objects-hcenter-black.svg src/labelwerk/gui/icons/align-objects-hcenter-white.svg src/labelwerk/gui/icons/align-objects-left-black.svg src/labelwerk/gui/icons/align-objects-left-white.svg src/labelwerk/gui/icons/align-objects-right-black.svg src/labelwerk/gui/icons/align-objects-right-white.svg src/labelwerk/gui/icons/align-objects-top-black.svg src/labelwerk/gui/icons/align-objects-top-white.svg src/labelwerk/gui/icons/align-objects-vcenter-black.svg src/labelwerk/gui/icons/align-objects-vcenter-white.svg src/labelwerk/gui/icons/align-paper-bottom-black.svg src/labelwerk/gui/icons/align-paper-bottom-white.svg src/labelwerk/gui/icons/align-paper-hcenter-black.svg src/labelwerk/gui/icons/align-paper-hcenter-white.svg src/labelwerk/gui/icons/align-paper-left-black.svg src/labelwerk/gui/icons/align-paper-left-white.svg src/labelwerk/gui/icons/align-paper-right-black.svg src/labelwerk/gui/icons/align-paper-right-white.svg src/labelwerk/gui/icons/align-paper-top-black.svg src/labelwerk/gui/icons/align-paper-top-white.svg src/labelwerk/gui/icons/align-paper-vcenter-black.svg src/labelwerk/gui/icons/align-paper-vcenter-white.svg src/labelwerk/gui/icons/order-backward-black.svg src/labelwerk/gui/icons/order-backward-white.svg src/labelwerk/gui/icons/order-forward-black.svg src/labelwerk/gui/icons/order-forward-white.svg src/labelwerk/gui/icons/rotate-left-black.svg src/labelwerk/gui/icons/rotate-left-white.svg src/labelwerk/gui/icons/rotate-right-black.svg src/labelwerk/gui/icons/rotate-right-white.svg src/labelwerk/gui/icons/size-height-black.svg src/labelwerk/gui/icons/size-height-white.svg src/labelwerk/gui/icons/size-maximize-black.svg src/labelwerk/gui/icons/size-maximize-white.svg src/labelwerk/gui/icons/size-same-black.svg src/labelwerk/gui/icons/size-same-white.svg src/labelwerk/gui/icons/size-width-black.svg src/labelwerk/gui/icons/size-width-white.svg src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/__init__.py src/labelwerk/gui/panels/layout.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/symbols.py src/labelwerk/gui/theme/rawblock.qss src/labelwerk/gui/tools.py src/labelwerk/layout.py tests/gui/test_gui_layout.py tests/test_layout.py
git commit -m "GUI: Reiter Layout – Ausrichten, Größe angleichen, Drehen, Reihenfolge

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: GUI – Bearbeitungsleiste mit eigenen Symbolen

**Files:**
- Modify: `src/labelwerk/gui/canvas.py`
- Create: `src/labelwerk/gui/icons/edit-copy-black.svg`
- Create: `src/labelwerk/gui/icons/edit-copy-white.svg`
- Create: `src/labelwerk/gui/icons/edit-cut-black.svg`
- Create: `src/labelwerk/gui/icons/edit-cut-white.svg`
- Create: `src/labelwerk/gui/icons/edit-paste-black.svg`
- Create: `src/labelwerk/gui/icons/edit-paste-white.svg`
- Create: `src/labelwerk/gui/icons/edit-redo-black.svg`
- Create: `src/labelwerk/gui/icons/edit-redo-white.svg`
- Create: `src/labelwerk/gui/icons/edit-undo-black.svg`
- Create: `src/labelwerk/gui/icons/edit-undo-white.svg`
- Create: `src/labelwerk/gui/icons/tool-select-black.svg`
- Create: `src/labelwerk/gui/icons/tool-select-white.svg`
- Create: `src/labelwerk/gui/icons/tool-text-black.svg`
- Create: `src/labelwerk/gui/icons/tool-text-white.svg`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `tests/gui/test_gui_editbar.py`

**Interfaces / Produces:** 14 SVG-Symbole (Auswahl, Text, Ausschneiden, Kopieren, Einfügen, Rückgängig, Wiederherstellen; schwarz/weiß); Strg+A beendet das Text-Werkzeug.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_editbar.py b/tests/gui/test_gui_editbar.py
index 0ef6f2c..8db3a2a 100644
--- a/tests/gui/test_gui_editbar.py
+++ b/tests/gui/test_gui_editbar.py
@@ -1,10 +1,13 @@
 """Bearbeitungsleiste: Text anlegen, Zwischenablage, Rückgängig (Etappe 3d-1)."""
+from importlib import resources
+
 import pytest
-from PySide6.QtCore import QPointF, Qt
-from PySide6.QtGui import QMouseEvent
+from PySide6.QtCore import QPointF, QSize, Qt
+from PySide6.QtGui import QIcon, QMouseEvent
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication, QToolBar
 
+from labelwerk import shortcuts
 from labelwerk.document import Document, TextObject
 from labelwerk.gui.canvas import MM
 from labelwerk.gui.main_window import MainWindow
@@ -86,8 +89,60 @@ def test_edit_bar_holds_tools_clipboard_and_history(window):
                    "|", "edit.undo", "edit.redo"]
     assert window.toolBarBreak(bar)                         # eigene Zeile unter den Werkzeugen
     assert "Ctrl+Z" in window.actions["edit.undo"].toolTip()
-    text_button = bar.widgetForAction(window.actions["tool.text"])
-    assert text_button.text() == "A"
+
+
+def test_edit_bar_buttons_show_own_icons_only(window):
+    folder = resources.files("labelwerk.gui") / "icons"
+    for action in window.edit_bar.actions():
+        if action.isSeparator():
+            continue
+        button = window.edit_bar.widgetForAction(action)
+        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
+        assert not action.icon().isNull()
+        name = shortcuts.action(action.objectName()).name
+        assert action.toolTip().startswith(name)
+    for name in ("tool-select", "tool-text", "edit-cut", "edit-copy", "edit-paste",
+                 "edit-undo", "edit-redo"):
+        for color in ("black", "white"):
+            assert (folder / f"{name}-{color}.svg").is_file()
+    assert "(T)" in window.actions["tool.text"].toolTip()
+
+
+def _ink(icon, mode=QIcon.Mode.Normal, state=QIcon.State.Off):
+    image = icon.pixmap(QSize(16, 16), mode, state).toImage()
+    pixels = [image.pixelColor(x, y) for x in range(16) for y in range(16)]
+    return {(c.red(), c.green(), c.blue()) for c in pixels if c.alpha() > 200}
+
+
+def test_edit_bar_icons_follow_theme(qtbot):
+    win = _window(qtbot, settings=Settings(check_media_on_start=False, theme="rawblock"))
+    icon = win.actions["tool.select"].icon()
+    assert _ink(icon) == {(0, 0, 0)}
+    assert _ink(icon, state=QIcon.State.On) == {(255, 255, 255)}      # gewählt: weiß auf schwarz
+    assert _ink(icon, QIcon.Mode.Active) == {(255, 255, 255)}         # darüber: weiß auf schwarz
+    win.settings = Settings(check_media_on_start=False, theme="classic")
+    win.apply_theme_icons()
+    icon = win.actions["tool.select"].icon()
+    assert _ink(icon, state=QIcon.State.On) == {(0, 0, 0)}
+
+
+def test_click_on_selected_object_leaves_paper_tab_but_not_layout(window):
+    window.canvas.set_selection([0])
+    window.tool_actions["paper"].trigger()
+    _click(window.canvas, window.canvas.view_rect(0).center())
+    assert window.panels.currentWidget() is window.panel("text")
+    window.tool_actions["layout"].trigger()
+    _click(window.canvas, window.canvas.view_rect(0).center())
+    assert window.panels.currentWidget() is window.panel("layout")
+    assert window.tool_actions["layout"].isChecked()
+
+
+def test_select_all_ends_text_tool(window, qtbot):
+    window.actions["tool.text"].trigger()
+    _focus_canvas(window, qtbot)
+    QTest.keyClick(window.canvas, Qt.Key.Key_A, CTRL)
+    assert window.canvas.selection() == [0, 1]
+    assert window.canvas.tool() == "select" and window.actions["tool.select"].isChecked()
 
 
 def test_tool_modes_are_exclusive(window):
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/canvas.py b/src/labelwerk/gui/canvas.py
index d815536..f6de376 100644
--- a/src/labelwerk/gui/canvas.py
+++ b/src/labelwerk/gui/canvas.py
@@ -91,6 +91,7 @@ class Canvas(QGraphicsView):
     object_resized = Signal(int, object, str)  # Index, neuer Rahmen (Rect, mm), Anfasser („tl“ …)
     text_requested = Signal(float, float)      # „Text anlegen“: Klick aufs Etikett (mm, Leserichtung)
     edit_requested = Signal(int)               # Text eines Objekts bearbeiten (Doppelklick)
+    object_clicked = Signal(int)               # Klick auf ein Objekt (auch ein schon gewähltes)
     tool_changed = Signal(str)                 # Werkzeug: "select" | "text"
 
     def __init__(self, model: str = DEFAULT_MODEL):
@@ -215,6 +216,8 @@ class Canvas(QGraphicsView):
             self.selection_changed.emit(self.selection())
 
     def select_all(self) -> None:
+        """Alle Objekte wählen; „Text anlegen“ endet dabei (zurück zum Auswahl-Pfeil)."""
+        self.set_tool("select")
         self.set_selection(list(range(len(self.objects))))
 
     def _selectable(self, index: int) -> bool:
@@ -376,6 +379,7 @@ class Canvas(QGraphicsView):
         else:
             if item.index not in self._selection:
                 self.set_selection([item.index])
+            self.object_clicked.emit(item.index)
             self._drag = "move"
             self._grabbed = item.index
             self._start = {i: self.objects[i].pos() for i in self._selection}
diff --git a/src/labelwerk/gui/icons/edit-copy-black.svg b/src/labelwerk/gui/icons/edit-copy-black.svg
new file mode 100644
index 0000000..d3ed421
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-copy-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="8" height="10" fill="#FFFFFF" stroke="#000000" stroke-width="1"/><rect x="6.5" y="4.5" width="8" height="10" fill="#FFFFFF" stroke="#000000" stroke-width="1"/><rect x="8" y="7" width="5" height="1" fill="#000000"/><rect x="8" y="9" width="5" height="1" fill="#000000"/><rect x="8" y="11" width="3" height="1" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-copy-white.svg b/src/labelwerk/gui/icons/edit-copy-white.svg
new file mode 100644
index 0000000..2451ddc
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-copy-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="8" height="10" fill="#000000" stroke="#FFFFFF" stroke-width="1"/><rect x="6.5" y="4.5" width="8" height="10" fill="#000000" stroke="#FFFFFF" stroke-width="1"/><rect x="8" y="7" width="5" height="1" fill="#FFFFFF"/><rect x="8" y="9" width="5" height="1" fill="#FFFFFF"/><rect x="8" y="11" width="3" height="1" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-cut-black.svg b/src/labelwerk/gui/icons/edit-cut-black.svg
new file mode 100644
index 0000000..f94e4cb
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-cut-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="4" cy="12.5" r="2.3" fill="none" stroke="#000000" stroke-width="1.4"/><circle cx="12" cy="12.5" r="2.3" fill="none" stroke="#000000" stroke-width="1.4"/><path d="M5.4 10.6 L11.5 1 M10.6 10.6 L4.5 1" stroke="#000000" stroke-width="1.6"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-cut-white.svg b/src/labelwerk/gui/icons/edit-cut-white.svg
new file mode 100644
index 0000000..d5f4eb3
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-cut-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="4" cy="12.5" r="2.3" fill="none" stroke="#FFFFFF" stroke-width="1.4"/><circle cx="12" cy="12.5" r="2.3" fill="none" stroke="#FFFFFF" stroke-width="1.4"/><path d="M5.4 10.6 L11.5 1 M10.6 10.6 L4.5 1" stroke="#FFFFFF" stroke-width="1.6"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-paste-black.svg b/src/labelwerk/gui/icons/edit-paste-black.svg
new file mode 100644
index 0000000..6e52876
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-paste-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="2.5" y="2.5" width="11" height="12" fill="none" stroke="#000000" stroke-width="1"/><rect x="5" y="1" width="6" height="3" fill="#000000"/><rect x="5" y="7" width="6" height="1" fill="#000000"/><rect x="5" y="9" width="6" height="1" fill="#000000"/><rect x="5" y="11" width="4" height="1" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-paste-white.svg b/src/labelwerk/gui/icons/edit-paste-white.svg
new file mode 100644
index 0000000..904a942
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-paste-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="2.5" y="2.5" width="11" height="12" fill="none" stroke="#FFFFFF" stroke-width="1"/><rect x="5" y="1" width="6" height="3" fill="#FFFFFF"/><rect x="5" y="7" width="6" height="1" fill="#FFFFFF"/><rect x="5" y="9" width="6" height="1" fill="#FFFFFF"/><rect x="5" y="11" width="4" height="1" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-redo-black.svg b/src/labelwerk/gui/icons/edit-redo-black.svg
new file mode 100644
index 0000000..26c9f9f
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-redo-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M12 6 H6 A4 4 0 0 0 6 14 H11" fill="none" stroke="#000000" stroke-width="2"/><path d="M15.5 6 L11 2 L11 10 Z" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-redo-white.svg b/src/labelwerk/gui/icons/edit-redo-white.svg
new file mode 100644
index 0000000..7e081d0
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-redo-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M12 6 H6 A4 4 0 0 0 6 14 H11" fill="none" stroke="#FFFFFF" stroke-width="2"/><path d="M15.5 6 L11 2 L11 10 Z" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-undo-black.svg b/src/labelwerk/gui/icons/edit-undo-black.svg
new file mode 100644
index 0000000..96123ee
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-undo-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M4 6 H10 A4 4 0 0 1 10 14 H5" fill="none" stroke="#000000" stroke-width="2"/><path d="M0.5 6 L5 2 L5 10 Z" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/edit-undo-white.svg b/src/labelwerk/gui/icons/edit-undo-white.svg
new file mode 100644
index 0000000..13c215e
--- /dev/null
+++ b/src/labelwerk/gui/icons/edit-undo-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M4 6 H10 A4 4 0 0 1 10 14 H5" fill="none" stroke="#FFFFFF" stroke-width="2"/><path d="M0.5 6 L5 2 L5 10 Z" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/tool-select-black.svg b/src/labelwerk/gui/icons/tool-select-black.svg
new file mode 100644
index 0000000..492b098
--- /dev/null
+++ b/src/labelwerk/gui/icons/tool-select-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1 L3 14 L6.3 10.8 L8.6 15.3 L10.6 14.3 L8.4 9.9 L13 9.9 Z" fill="#000000"/></svg>
diff --git a/src/labelwerk/gui/icons/tool-select-white.svg b/src/labelwerk/gui/icons/tool-select-white.svg
new file mode 100644
index 0000000..71cbf6d
--- /dev/null
+++ b/src/labelwerk/gui/icons/tool-select-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3 1 L3 14 L6.3 10.8 L8.6 15.3 L10.6 14.3 L8.4 9.9 L13 9.9 Z" fill="#FFFFFF"/></svg>
diff --git a/src/labelwerk/gui/icons/tool-text-black.svg b/src/labelwerk/gui/icons/tool-text-black.svg
new file mode 100644
index 0000000..583a74e
--- /dev/null
+++ b/src/labelwerk/gui/icons/tool-text-black.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill-rule="evenodd" fill="#000000" d="M6.7 1 L9.3 1 L14.5 15 L11.9 15 L10.7 11.6 L5.3 11.6 L4.1 15 L1.5 15 Z M6.1 9.4 L9.9 9.4 L8 4 Z"/></svg>
diff --git a/src/labelwerk/gui/icons/tool-text-white.svg b/src/labelwerk/gui/icons/tool-text-white.svg
new file mode 100644
index 0000000..57bad6c
--- /dev/null
+++ b/src/labelwerk/gui/icons/tool-text-white.svg
@@ -0,0 +1 @@
+<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill-rule="evenodd" fill="#FFFFFF" d="M6.7 1 L9.3 1 L14.5 15 L11.9 15 L10.7 11.6 L5.3 11.6 L4.1 15 L1.5 15 Z M6.1 9.4 L9.9 9.4 L8 4 Z"/></svg>
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index ea9875f..31caa7e 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -30,6 +30,7 @@ from .media_worker import MediaWorker
 from .panels.text import DEFAULT_PT
 from .print_worker import PrintWorker
 from .settings_dialog import SettingsDialog
+from .symbols import SIZE, line_icon
 from .tools import TOOLS, Tool
 
 RENDER_DELAY_MS = 150
@@ -40,11 +41,10 @@ NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit U
 _DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
 OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"
 PASTE_OFFSET_MM = 2.0      # Einfügen/Duplizieren: versetzt nach rechts und unten
-# Bearbeitungsleiste: Aktion, Symbol im Freedesktop-Theme, Text ohne Symbol; None = Trenner
-EDIT_BAR = (("tool.select", "edit-select", "↖"), ("tool.text", None, "A"), None,
-            ("edit.cut", "edit-cut", "AUSSCHNEIDEN"), ("edit.copy", "edit-copy", "KOPIEREN"),
-            ("edit.paste", "edit-paste", "EINFÜGEN"), None,
-            ("edit.undo", "edit-undo", "↶"), ("edit.redo", "edit-redo", "↷"))
+# Bearbeitungsleiste: Aktion und eigenes Symbol (gui/icons); None = Trenner
+EDIT_BAR = (("tool.select", "tool-select"), ("tool.text", "tool-text"), None,
+            ("edit.cut", "edit-cut"), ("edit.copy", "edit-copy"), ("edit.paste", "edit-paste"),
+            None, ("edit.undo", "edit-undo"), ("edit.redo", "edit-redo"))
 _SELECTION_ACTIONS = ("edit.cut", "edit.copy", "edit.duplicate", "edit.delete")
 SELECTION_PANELS = ("text", "layout")   # arbeiten mit der Auswahl: Wählen wechselt nicht weg
 
@@ -126,6 +126,7 @@ class MainWindow(QMainWindow):
         self.canvas.text_requested.connect(self.create_text)
         self.canvas.edit_requested.connect(self.edit_text)
         self.canvas.selection_changed.connect(self._update_edit_actions)
+        self.canvas.object_clicked.connect(self._show_object_panel)
         self.history = History(self.doc)
         self.history.changed.connect(self._update_edit_actions)
         self.actions = build_actions(self, effective(self.settings.shortcuts))
@@ -237,6 +238,8 @@ class MainWindow(QMainWindow):
         bar = QToolBar("Bearbeiten")
         bar.setObjectName("editBar")
         bar.setMovable(False)
+        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
+        bar.setIconSize(SIZE)
         self.addToolBarBreak()
         self.addToolBar(bar)
         self.edit_bar = bar
@@ -249,20 +252,8 @@ class MainWindow(QMainWindow):
         for entry in EDIT_BAR:
             if entry is None:
                 bar.addSeparator()
-                continue
-            key, icon_name, fallback = entry
-            action = self.actions[key]
-            icon = QIcon.fromTheme(icon_name) if icon_name else QIcon()
-            action.setIcon(icon)
-            action.setIconText(fallback)
-            bar.addAction(action)
-            button = bar.widgetForAction(action)
-            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly if icon.isNull()
-                                      else Qt.ToolButtonStyle.ToolButtonIconOnly)
-            if key == "tool.text":                 # „A“ wie im P-touch Editor, auch ohne Stylesheet
-                font = button.font()
-                font.setBold(True)
-                button.setFont(font)
+            else:
+                bar.addAction(self.actions[entry[0]])   # Symbol setzt apply_theme_icons
 
     def _show_tool(self, key: str) -> None:
         """Panel eines Werkzeugs zeigen (wie ein Klick auf seinen Knopf)."""
@@ -283,6 +274,7 @@ class MainWindow(QMainWindow):
             self._show_object_panel()
 
     def _show_object_panel(self) -> None:
+        """Vom Papier-Reiter zum Panel des Objekts (auch beim Klick auf ein schon gewähltes)."""
         if not any(self.panels.currentWidget() is self.panel(key) for key in SELECTION_PANELS):
             self._show_tool("text")
 
@@ -620,6 +612,9 @@ class MainWindow(QMainWindow):
         dark = self.settings.theme == "rawblock"
         for panel in self._panel_by_key.values():
             panel.set_icon_style(dark)
+        for entry in EDIT_BAR:
+            if entry is not None:
+                self.actions[entry[0]].setIcon(line_icon(entry[1], dark, hover=True))
 
     def open_settings(self) -> None:
         dialog = SettingsDialog(self.settings, model=self.model, parent=self)
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `659 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/canvas.py src/labelwerk/gui/icons/edit-copy-black.svg src/labelwerk/gui/icons/edit-copy-white.svg src/labelwerk/gui/icons/edit-cut-black.svg src/labelwerk/gui/icons/edit-cut-white.svg src/labelwerk/gui/icons/edit-paste-black.svg src/labelwerk/gui/icons/edit-paste-white.svg src/labelwerk/gui/icons/edit-redo-black.svg src/labelwerk/gui/icons/edit-redo-white.svg src/labelwerk/gui/icons/edit-undo-black.svg src/labelwerk/gui/icons/edit-undo-white.svg src/labelwerk/gui/icons/tool-select-black.svg src/labelwerk/gui/icons/tool-select-white.svg src/labelwerk/gui/icons/tool-text-black.svg src/labelwerk/gui/icons/tool-text-white.svg src/labelwerk/gui/main_window.py tests/gui/test_gui_editbar.py
git commit -m "GUI: Bearbeitungsleiste mit eigenen Symbolen

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: GUI – Einstellungen mit Reiter Tastenkürzel

**Files:**
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `src/labelwerk/gui/panels/text.py`
- Modify: `src/labelwerk/gui/settings_dialog.py`
- Modify: `src/labelwerk/gui/theme/rawblock.qss`
- Modify: `tests/gui/conftest.py`
- Modify: `tests/gui/test_gui_settings.py`
- Modify: `tests/gui/test_gui_text.py`
- Modify: `tests/gui/test_gui_window.py`

**Interfaces / Produces:** SettingsDialog mit Reitern „Allgemein“/„Tastenkürzel“ (Tabelle, Kürzel-Editor, „Standard“, „Alle zurücksetzen“, Konflikte rot + Speichern gesperrt); alle Kürzel der App laufen über `gui/actions.py` (auch Drucken, Einstellungen, Zoom, B/I/U); `open_settings` gibt den Dialog frei (`deleteLater`); Fixture `no_leftover_theme` in `tests/gui/conftest.py`.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/conftest.py b/tests/gui/conftest.py
index 440dacf..add7028 100644
--- a/tests/gui/conftest.py
+++ b/tests/gui/conftest.py
@@ -9,6 +9,13 @@ except ImportError:  # reine CLI-Umgebung: GUI-Tests überspringen
 else:
     import pytest
 
+    @pytest.fixture(autouse=True)
+    def no_leftover_theme(qapp):
+        """Speichern der Einstellungen setzt das Design der ganzen Anwendung – danach zurück,
+        damit jeder Test im Qt-Grundstil startet."""
+        yield
+        qapp.setStyleSheet("")
+
     @pytest.fixture(autouse=True)
     def no_printer(monkeypatch):
         """Kein Test liest echte Druckerdaten aus /sys."""
diff --git a/tests/gui/test_gui_settings.py b/tests/gui/test_gui_settings.py
index a417f95..62aa34b 100644
--- a/tests/gui/test_gui_settings.py
+++ b/tests/gui/test_gui_settings.py
@@ -148,3 +148,151 @@ def test_dialog_keeps_shortcuts_when_saving(qtbot, tmp_path):
     qtbot.addWidget(dialog)
     dialog.accept()
     assert load_settings(path).shortcuts == {"file.print": "Ctrl+Shift+P"}
+
+
+# --- Reiter „Tastenkürzel“ ----------------------------------------------------------
+def _shortcut_dialog(qtbot, settings=None, path=None):
+    dialog = SettingsDialog(settings or Settings(), path=path)
+    qtbot.addWidget(dialog)
+    return dialog
+
+
+def _row(action_id):
+    from labelwerk import shortcuts
+    return [a.id for a in shortcuts.ACTIONS].index(action_id)
+
+
+def _is_red(dialog, action_id):
+    item = dialog.shortcut_table.item(_row(action_id), 0)
+    return item.foreground().color().name() == "#ff0000"
+
+
+def test_dialog_has_tabs_general_and_shortcuts(qtbot):
+    dialog = _shortcut_dialog(qtbot)
+    tabs = dialog.tabs
+    assert [tabs.tabText(i) for i in range(tabs.count())] == ["Allgemein", "Tastenkürzel"]
+    assert tabs.widget(0).isAncestorOf(dialog.label)        # bisherige Felder unter „Allgemein“
+
+
+def test_shortcut_table_lists_every_action_with_scope_and_keys(qtbot):
+    from PySide6.QtGui import QKeySequence
+    from labelwerk import shortcuts
+    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P"}))
+    table = dialog.shortcut_table
+    assert table.rowCount() == len(shortcuts.ACTIONS)
+    assert [table.horizontalHeaderItem(c).text() for c in range(3)] == ["Aktion", "Bereich", "Kürzel"]
+    row = _row("file.print")
+    assert (table.item(row, 0).text(), table.item(row, 1).text()) == ("Drucken", "Global")
+    native = QKeySequence("Ctrl+Shift+P").toString(QKeySequence.SequenceFormat.NativeText)
+    assert table.item(row, 2).text() == native
+    assert table.item(_row("edit.copy"), 1).text() == "Arbeitsfläche"
+    assert table.item(_row("text.bold"), 1).text() == "Text"
+    assert table.item(_row("align.left"), 2).text() == ""
+
+
+def test_values_contain_only_changed_shortcuts(qtbot):
+    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P"}))
+    dialog.set_shortcut("edit.copy", "Ctrl+Shift+C")
+    dialog.set_shortcut("edit.cut", "")                     # Kürzel geleert
+    dialog.set_shortcut("edit.paste", "Ctrl+V")             # = Standard
+    assert dialog.values().shortcuts == {"file.print": "Ctrl+Shift+P",
+                                         "edit.copy": "Ctrl+Shift+C", "edit.cut": ""}
+
+
+def test_shortcut_cell_edits_with_key_sequence_edit(qtbot):
+    from PySide6.QtCore import Qt
+    from PySide6.QtTest import QTest
+    from PySide6.QtWidgets import QKeySequenceEdit
+    dialog = _shortcut_dialog(qtbot)
+    dialog.show()
+    dialog.activateWindow()
+    dialog.tabs.setCurrentIndex(1)
+    table = dialog.shortcut_table
+    table.cellClicked.emit(_row("file.print"), 0)           # Klick irgendwo in die Zeile
+    editor = table.findChild(QKeySequenceEdit)
+    assert editor is not None and editor.isClearButtonEnabled()
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    assert editor.maximumSequenceLength() == 1                 # genau eine Tastenkombination
+    QTest.keyClick(editor, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier
+                   | Qt.KeyboardModifier.AltModifier)
+    qtbot.waitUntil(lambda: dialog.shortcut("file.print") == "Ctrl+Alt+P", timeout=2000)
+    assert dialog.values().shortcuts == {"file.print": "Ctrl+Alt+P"}
+
+
+def test_escape_cancels_shortcut_editing(qtbot):
+    from PySide6.QtCore import Qt
+    from PySide6.QtTest import QTest
+    from PySide6.QtWidgets import QKeySequenceEdit
+    dialog = _shortcut_dialog(qtbot)
+    dialog.show()
+    dialog.activateWindow()
+    dialog.tabs.setCurrentIndex(1)
+    dialog.shortcut_table.cellClicked.emit(_row("edit.copy"), 2)
+    editor = dialog.shortcut_table.findChild(QKeySequenceEdit)
+    qtbot.waitUntil(editor.hasFocus, timeout=1000)
+    QTest.keyClick(editor, Qt.Key.Key_Escape)
+    qtbot.waitUntil(lambda: not editor.isVisible(), timeout=1000)
+    assert dialog.shortcut("edit.copy") == "Ctrl+C"
+
+
+def test_conflict_marks_rows_red_and_blocks_saving(qtbot):
+    dialog = _shortcut_dialog(qtbot)
+    assert dialog.save_button.isEnabled() and dialog.conflict_hint.isHidden()
+    dialog.set_shortcut("app.settings", "Ctrl+P")           # wie „Drucken“
+    assert _is_red(dialog, "app.settings") and _is_red(dialog, "file.print")
+    assert not _is_red(dialog, "edit.copy")
+    assert not dialog.save_button.isEnabled()
+    assert not dialog.conflict_hint.isHidden()
+    assert "Drucken" in dialog.conflict_hint.text()
+    assert "Einstellungen" in dialog.conflict_hint.text()
+    dialog.set_shortcut("app.settings", "Ctrl+Shift+E")
+    assert not _is_red(dialog, "file.print")
+    assert dialog.save_button.isEnabled() and dialog.conflict_hint.isHidden()
+
+
+def test_same_key_in_canvas_and_text_is_no_conflict(qtbot):
+    dialog = _shortcut_dialog(qtbot)
+    dialog.set_shortcut("text.bold", "Ctrl+D")             # „Duplizieren“ gilt nur auf der Fläche
+    assert dialog.save_button.isEnabled()
+
+
+def test_conflict_with_saved_settings_is_shown_on_open(qtbot):
+    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"edit.copy": "Ctrl+X"}))
+    assert _is_red(dialog, "edit.cut") and not dialog.save_button.isEnabled()
+
+
+def test_standard_button_resets_one_row(qtbot):
+    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P",
+                                                         "edit.copy": ""}))
+    assert dialog.reset_button("edit.paste") is None            # schon Standard
+    dialog.reset_button("file.print").click()
+    assert dialog.shortcut("file.print") == "Ctrl+P"
+    assert dialog.reset_button("file.print") is None
+    assert dialog.values().shortcuts == {"edit.copy": ""}
+
+
+def test_reset_all(qtbot):
+    dialog = _shortcut_dialog(qtbot, Settings(shortcuts={"file.print": "Ctrl+Shift+P",
+                                                         "edit.copy": "Ctrl+X"}))
+    assert not dialog.save_button.isEnabled()
+    dialog.reset_all.click()
+    assert dialog.values().shortcuts == {}
+    assert dialog.save_button.isEnabled() and not _is_red(dialog, "edit.cut")
+
+
+def test_saved_shortcut_takes_effect_in_window(qtbot, monkeypatch):
+    from PySide6.QtGui import QKeySequence
+    win = MainWindow(settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+
+    def fake_exec(dialog):
+        dialog.set_shortcut("file.print", "Ctrl+Shift+P")
+        dialog.set_shortcut("text.bold", "Ctrl+Shift+B")
+        dialog.accept()
+        return QDialog.DialogCode.Accepted
+    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
+    win.settings_action.trigger()
+    assert win.settings.shortcuts == {"file.print": "Ctrl+Shift+P", "text.bold": "Ctrl+Shift+B"}
+    assert win.actions["file.print"].shortcut() == QKeySequence("Ctrl+Shift+P")
+    assert win.actions["text.bold"].shortcut() == QKeySequence("Ctrl+Shift+B")
+    assert win.actions["text.bold"] in win.panel("text").actions()   # B/I/U über die Aktionen
diff --git a/tests/gui/test_gui_text.py b/tests/gui/test_gui_text.py
index f3d04be..386fce6 100644
--- a/tests/gui/test_gui_text.py
+++ b/tests/gui/test_gui_text.py
@@ -205,13 +205,30 @@ def test_refresh_keeps_format_of_empty_paragraph(window):
     assert paragraphs[1].spans[0].size_pt == 40
 
 
-def test_shortcuts_are_scoped_to_panel(window):
+def test_format_shortcuts_are_actions_scoped_to_panel(window):
     from PySide6.QtCore import Qt
     from PySide6.QtGui import QShortcut
     panel = window.panel("text")
-    shortcuts = panel.findChildren(QShortcut)
-    assert len(shortcuts) == 3
-    assert all(s.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut for s in shortcuts)
+    assert panel.findChildren(QShortcut) == []              # alles über das Kürzel-Verzeichnis
+    actions = [window.actions[key] for key in ("text.bold", "text.italic", "text.underline")]
+    assert all(a in panel.actions() for a in actions)
+    assert all(a.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
+               for a in actions)
+
+
+def test_ctrl_b_in_editor_makes_selection_bold(window, qtbot):
+    from PySide6.QtCore import Qt
+    from PySide6.QtTest import QTest
+    panel = window.panel("text")
+    window.tool_actions["text"].trigger()
+    panel.edit.setPlainText("aaa bbb")
+    window.activateWindow()
+    panel.edit.setFocus()
+    qtbot.waitUntil(panel.edit.hasFocus, timeout=1000)
+    _select(panel, 4, 7)
+    QTest.keyClick(panel.edit, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
+    first, second = panel.to_text_object().paragraphs[0].spans
+    assert (first.text, second.text) == ("aaa ", "bbb") and first.bold != second.bold
 
 
 def test_format_change_is_one_undo_step(window):
diff --git a/tests/gui/test_gui_window.py b/tests/gui/test_gui_window.py
index afd463f..979a41d 100644
--- a/tests/gui/test_gui_window.py
+++ b/tests/gui/test_gui_window.py
@@ -361,3 +361,30 @@ def test_font_replacement_hint_in_status_bar(window):
     window.doc.objects[0] = TextObject([Paragraph([Span("Hallo")])])
     window.render_now()
     assert window.result.text() == ""
+
+
+def test_global_actions_come_from_shortcut_registry(window, monkeypatch):
+    """Drucken, Einstellungen und Zoom sind Aktionen des Kürzel-Verzeichnisses."""
+    from PySide6.QtGui import QKeySequence
+    assert window.print_action is window.actions["file.print"]
+    assert window.settings_action is window.actions["app.settings"]
+    assert window.print_action.shortcut() == QKeySequence("Ctrl+P")
+    assert "Ctrl+P" in window.print_action.toolTip()
+    asked = []                                              # leeres Etikett: Rückfrage = Druck läuft
+    monkeypatch.setattr(QMessageBox, "question",
+                        lambda *a, **kw: asked.append(a) or QMessageBox.StandardButton.Cancel)
+    window.panel("text").edit.setPlainText("")
+    window.actions["file.print"].trigger()
+    assert asked
+    window.canvas.set_zoom(100)
+    window.actions["view.zoom_in"].trigger()
+    assert window.canvas.zoom == 110
+    window.actions["view.zoom_out"].trigger()
+    window.actions["view.zoom_out"].trigger()
+    assert window.canvas.zoom == 90
+    window.actions["view.zoom_reset"].trigger()
+    assert window.canvas.zoom == 100
+    from PySide6.QtWidgets import QWidget
+    window_actions = QWidget.actions(window)                # self.actions ist das Verzeichnis
+    assert all(window.actions[key] in window_actions
+               for key in ("view.zoom_in", "view.zoom_out", "view.zoom_reset", "edit.undo"))
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

```diff
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 31caa7e..7911659 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -37,6 +37,7 @@ RENDER_DELAY_MS = 150
 PANEL_WIDTH = 280          # Eigenschaften-Panels; bei wenig Höhe rollbar
 MEDIA_STATUS_MAX_PX = 360   # Rollen-Hinweis in der Fußzeile; Rest per „…“ und Tooltip
 PRINTER_POLL_MS = 2000     # Druckererkennung: nur Blick in /sys, kein USB-Zugriff
+ZOOM_STEP = 10             # Prozentpunkte je Klick bzw. Kürzel
 NUDGE_MM = {"": 0.1, "_coarse": 1.0}                  # Pfeiltasten fein / mit Umschalt
 _DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
 OUTSIDE_HINT = "Objekt ragt über das Etikett hinaus"
@@ -79,6 +80,8 @@ class MainWindow(QMainWindow):
         self._media_check_pending = False
         self._clipboard: list[TextObject] = []      # interne Zwischenablage (Kopien)
         self._merge_next = None                     # Pfeiltasten: Schritte zusammenfassen
+        # alle Kürzel kommen aus dem Verzeichnis (shortcuts.ACTIONS) und sind änderbar
+        self.actions = build_actions(self, effective(self.settings.shortcuts))
 
         # Werkzeugleiste + Panels aus der Registry
         toolbar = QToolBar("Werkzeuge")
@@ -108,11 +111,11 @@ class MainWindow(QMainWindow):
         spacer = QWidget()
         spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
         toolbar.addWidget(spacer)
-        self.settings_action = QAction(QIcon.fromTheme("preferences-system"), "EINSTELLUNGEN", self)
-        self.settings_action.triggered.connect(self.open_settings)
+        self.settings_action = self._toolbar_action("app.settings", "preferences-system",
+                                                    "EINSTELLUNGEN", self.open_settings)
         toolbar.addAction(self.settings_action)
-        self.print_action = QAction(QIcon.fromTheme("document-print"), "DRUCKEN", self)
-        self.print_action.triggered.connect(self.print_label)
+        self.print_action = self._toolbar_action("file.print", "document-print", "DRUCKEN",
+                                                 self.print_label)
         toolbar.addAction(self.print_action)
         toolbar.widgetForAction(self.print_action).setObjectName("print")
 
@@ -129,7 +132,7 @@ class MainWindow(QMainWindow):
         self.canvas.object_clicked.connect(self._show_object_panel)
         self.history = History(self.doc)
         self.history.changed.connect(self._update_edit_actions)
-        self.actions = build_actions(self, effective(self.settings.shortcuts))
+        self._connect_view_actions()
         self._connect_canvas_actions()
         self._connect_layout_actions()
         self._build_edit_bar()
@@ -161,7 +164,7 @@ class MainWindow(QMainWindow):
         self.statusBar().addWidget(self.media_status)
         self.statusBar().addWidget(self.result, 1)
         self.zoom_label = QLabel()
-        for text, delta in (("−", -10), ("+", 10)):
+        for text, delta in (("−", -ZOOM_STEP), ("+", ZOOM_STEP)):
             button = QToolButton()
             button.setText(text)
             button.clicked.connect(lambda _=False, d=delta: self.canvas.set_zoom(self.canvas.zoom + d))
@@ -196,6 +199,23 @@ class MainWindow(QMainWindow):
     def panel(self, key: str):
         return self._panel_by_key[key]
 
+    def _toolbar_action(self, key: str, icon: str, text: str, handler) -> QAction:
+        """Aktion aus dem Verzeichnis als Knopf der Werkzeugleiste (Kürzel bleibt änderbar)."""
+        action = self.actions[key]
+        action.setIcon(QIcon.fromTheme(icon))
+        action.setText(text)
+        action.triggered.connect(lambda _=False: handler())
+        return action
+
+    def _connect_view_actions(self) -> None:
+        """Zoom per Kürzel – wie die Knöpfe −/+ in der Statusleiste."""
+        handlers = {"view.zoom_in": lambda: self.canvas.set_zoom(self.canvas.zoom + ZOOM_STEP),
+                    "view.zoom_out": lambda: self.canvas.set_zoom(self.canvas.zoom - ZOOM_STEP),
+                    "view.zoom_reset": lambda: self.canvas.set_zoom(100)}
+        for key, handler in handlers.items():
+            self.actions[key].triggered.connect(lambda _=False, h=handler: h())
+            self.addAction(self.actions[key])
+
     def _connect_canvas_actions(self) -> None:
         """Kürzel der Arbeitsfläche (Pfeiltasten, Zwischenablage, Werkzeug) und Rückgängig."""
         for direction, (sx, sy) in _DIRECTIONS.items():
@@ -618,8 +638,11 @@ class MainWindow(QMainWindow):
 
     def open_settings(self) -> None:
         dialog = SettingsDialog(self.settings, model=self.model, parent=self)
-        if dialog.exec() == SettingsDialog.DialogCode.Accepted and dialog.saved is not None:
-            self.settings = dialog.saved
+        accepted = dialog.exec() == SettingsDialog.DialogCode.Accepted
+        saved = dialog.saved
+        dialog.deleteLater()                    # nicht bis zum Schließen des Fensters behalten
+        if accepted and saved is not None:
+            self.settings = saved
             from PySide6.QtWidgets import QApplication
             from .app import apply_theme
             apply_theme(QApplication.instance(), self.settings.theme)
diff --git a/src/labelwerk/gui/panels/text.py b/src/labelwerk/gui/panels/text.py
index f8a13fe..df978fe 100644
--- a/src/labelwerk/gui/panels/text.py
+++ b/src/labelwerk/gui/panels/text.py
@@ -8,7 +8,7 @@ from __future__ import annotations
 
 import math
 from PySide6.QtCore import QSize, Qt, Signal
-from PySide6.QtGui import (QFont, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextFormat,
+from PySide6.QtGui import (QAction, QFont, QIcon, QTextCharFormat, QTextCursor, QTextFormat,
                            QTextOption)
 from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFontComboBox, QGridLayout, QHBoxLayout,
                                QLabel, QPushButton, QTextEdit)
@@ -201,11 +201,13 @@ class TextPanel(Panel):
         for key, button in self.align_buttons.items():
             button.clicked.connect(lambda _=False, k=key: step(self._align, k))
         self.fit.toggled.connect(lambda _: step(self._apply))
-        for keys, button in ((QKeySequence.StandardKey.Bold, self.bold),
-                             (QKeySequence.StandardKey.Italic, self.italic),
-                             (QKeySequence.StandardKey.Underline, self.underline)):
-            QShortcut(keys, self, context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
-                      activated=button.click)
+
+    def use_actions(self, actions: dict[str, QAction]) -> None:
+        """Kürzel für Fett/Kursiv/Unterstrichen: wirken, solange das Panel den Fokus hat."""
+        for key, button in (("text.bold", self.bold), ("text.italic", self.italic),
+                            ("text.underline", self.underline)):
+            actions[key].triggered.connect(lambda _=False, b=button: b.click())
+            self.addAction(actions[key])
 
     @property
     def obj(self) -> TextObject:
diff --git a/src/labelwerk/gui/settings_dialog.py b/src/labelwerk/gui/settings_dialog.py
index 96f25ed..2ea4f7a 100644
--- a/src/labelwerk/gui/settings_dialog.py
+++ b/src/labelwerk/gui/settings_dialog.py
@@ -1,4 +1,5 @@
-"""Dialog „Einstellungen“: Standardwerte für neue Etiketten, Drucker, Ansicht.
+"""Dialog „Einstellungen“: Reiter „Allgemein“ (Standardwerte für neue Etiketten, Drucker,
+Ansicht) und „Tastenkürzel“ (alle Aktionen aus ``shortcuts.ACTIONS``).
 
 Neue Einstellung = Feld in settings.Settings + eine Zeile im passenden Abschnitt hier.
 """
@@ -6,27 +7,43 @@ from __future__ import annotations
 
 from pathlib import Path
 
-from PySide6.QtGui import QFont
-from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFontComboBox,
-                               QFormLayout,
-                               QGroupBox, QHBoxLayout, QLabel, QVBoxLayout)
+from PySide6.QtCore import Qt
+from PySide6.QtGui import QColor, QFont, QKeySequence
+from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
+                               QDialogButtonBox, QFontComboBox, QFormLayout, QGroupBox,
+                               QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QPushButton,
+                               QStyledItemDelegate, QTableWidget, QTableWidgetItem, QTabWidget,
+                               QVBoxLayout, QWidget)
 
+from .. import shortcuts
 from ..document import MAX_MARGIN_MM, MAX_PT, MIN_PT
 from ..labels import labels_for_model
 from ..printer import DEFAULT_MODEL
 from ..settings import Settings, save_settings
 from .widgets import DoubleSpinBox, SpinBox
 
+SCOPE_NAMES = {"global": "Global", "canvas": "Arbeitsfläche", "text": "Text"}
+CONFLICT_COLOR = QColor("#FF0000")
+COL_ACTION, COL_SCOPE, COL_KEYS, COL_RESET = range(4)
+DIALOG_SIZE = (760, 680)
+_PORTABLE = QKeySequence.SequenceFormat.PortableText
+_NATIVE = QKeySequence.SequenceFormat.NativeText
+
 
 class SettingsDialog(QDialog):
     def __init__(self, settings: Settings, path: str | Path | None = None,
                  model: str = DEFAULT_MODEL, parent=None):
         super().__init__(parent)
         self.setWindowTitle("Einstellungen")
+        self.resize(*DIALOG_SIZE)                    # Kürzel-Tabelle: Aktionsnamen ungekürzt
         self.path = path
         self.saved: Settings | None = None
-        self._shortcuts = dict(settings.shortcuts)     # hier (noch) nicht bearbeitet – bleibt erhalten
-        layout = QVBoxLayout(self)
+        outer = QVBoxLayout(self)
+        self.tabs = QTabWidget()
+        outer.addWidget(self.tabs)
+        general = QWidget()
+        self.tabs.addTab(general, "Allgemein")
+        layout = QVBoxLayout(general)
 
         form = self._section(layout, "Neues Etikett")
         self.label = QComboBox()
@@ -89,16 +106,20 @@ class SettingsDialog(QDialog):
         hint = QLabel("Gilt für neue Etiketten bzw. ab dem nächsten Start.")
         hint.setWordWrap(True)
         layout.addWidget(hint)
-        self.error = QLabel()
-        self.error.setObjectName("error")
-        self.error.setWordWrap(True)
-        self.error.hide()
-        layout.addWidget(self.error)
+        layout.addStretch()
+
+        self._build_shortcut_tab(settings.shortcuts)
+        self.conflict_hint = self._error_label()     # Kürzel doppelt belegt (Speichern gesperrt)
+        outer.addWidget(self.conflict_hint)
+        self.error = self._error_label()             # Speichern fehlgeschlagen
+        outer.addWidget(self.error)
         buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                    | QDialogButtonBox.StandardButton.Cancel)
         buttons.accepted.connect(self.accept)
         buttons.rejected.connect(self.reject)
-        layout.addWidget(buttons)
+        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
+        outer.addWidget(buttons)
+        self._check_conflicts()
 
     def _section(self, layout: QVBoxLayout, title: str) -> QFormLayout:
         box = QGroupBox(title.upper())
@@ -106,6 +127,122 @@ class SettingsDialog(QDialog):
         layout.addWidget(box)
         return form
 
+    @staticmethod
+    def _error_label() -> QLabel:
+        label = QLabel()
+        label.setObjectName("error")
+        label.setWordWrap(True)
+        label.hide()
+        return label
+
+    # --- Reiter „Tastenkürzel“ ------------------------------------------------------
+    def _build_shortcut_tab(self, overrides: dict[str, str]) -> None:
+        page = QWidget()
+        self.tabs.addTab(page, "Tastenkürzel")
+        layout = QVBoxLayout(page)
+        hint = QLabel("Zeile anklicken und die neue Tastenkombination drücken. "
+                      "Esc bricht ab, ✕ im Feld entfernt das Kürzel.")
+        hint.setWordWrap(True)
+        layout.addWidget(hint)
+        self._keys = shortcuts.effective(overrides)       # Aktions-ID → Kürzel (Qt-Format)
+        self._rows = [a.id for a in shortcuts.ACTIONS]
+        table = self.shortcut_table = QTableWidget(len(self._rows), 4)
+        table.setHorizontalHeaderLabels(["Aktion", "Bereich", "Kürzel", ""])
+        table.verticalHeader().hide()
+        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
+        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
+        table.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
+        table.setItemDelegateForColumn(COL_KEYS, _KeyDelegate(self))
+        header = table.horizontalHeader()
+        header.setSectionResizeMode(COL_ACTION, QHeaderView.ResizeMode.Stretch)
+        for column in (COL_SCOPE, COL_KEYS, COL_RESET):
+            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
+        fixed = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
+        for row, entry in enumerate(shortcuts.ACTIONS):
+            for column, text in ((COL_ACTION, entry.name), (COL_SCOPE, SCOPE_NAMES[entry.scope])):
+                item = QTableWidgetItem(text)
+                item.setFlags(fixed)
+                table.setItem(row, column, item)
+            item = QTableWidgetItem()
+            item.setFlags(fixed | Qt.ItemFlag.ItemIsEditable)
+            table.setItem(row, COL_KEYS, item)
+            self._show_keys(entry.id)
+        # gleiche Zeilenhöhe, ob mit Knopf „Standard“ oder ohne
+        probe = self._reset_widget("")
+        probe.ensurePolished()
+        rows = table.verticalHeader()
+        rows.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
+        rows.setDefaultSectionSize(max(rows.defaultSectionSize(), probe.sizeHint().height()))
+        # Klick auf eine Zeile (oder Enter) bearbeitet ihr Kürzel
+        table.cellClicked.connect(self._edit_row)
+        table.cellActivated.connect(self._edit_row)
+        layout.addWidget(table, 1)
+        row = QHBoxLayout()
+        self.reset_all = QPushButton("Alle zurücksetzen")
+        self.reset_all.clicked.connect(self._reset_all)
+        row.addWidget(self.reset_all)
+        row.addStretch()
+        layout.addLayout(row)
+
+    def shortcut(self, action_id: str) -> str:
+        """Kürzel einer Aktion, wie es gespeichert würde („“ = keins)."""
+        return self._keys[action_id]
+
+    def set_shortcut(self, action_id: str, seq: str) -> None:
+        """Kürzel einer Aktion ändern (Tabelle, Standard-Knopf); Konflikte neu prüfen."""
+        self._keys[action_id] = seq
+        self._show_keys(action_id)
+        self._check_conflicts()
+
+    def _show_keys(self, action_id: str) -> None:
+        row = self._rows.index(action_id)
+        seq = self._keys[action_id]
+        item = self.shortcut_table.item(row, COL_KEYS)
+        item.setText(_native(seq))
+        item.setData(Qt.ItemDataRole.UserRole, seq)
+        # Knopf „Standard“ nur, wo das Kürzel abweicht – sonst wäre die Spalte voller grauer Knöpfe
+        default = shortcuts.action(action_id).default
+        if _same(seq, default):
+            self.shortcut_table.removeCellWidget(row, COL_RESET)
+        elif self.reset_button(action_id) is None:
+            button = self._reset_widget(default)
+            button.clicked.connect(lambda _=False: self.set_shortcut(action_id, default))
+            self.shortcut_table.setCellWidget(row, COL_RESET, button)
+
+    def _reset_widget(self, default: str) -> QPushButton:
+        button = QPushButton("Standard")
+        button.setObjectName("tableButton")
+        button.setToolTip(f"Standard: {_native(default) or 'kein Kürzel'}")
+        return button
+
+    def reset_button(self, action_id: str) -> QPushButton | None:
+        """Knopf „Standard“ einer Zeile (None, solange das Standardkürzel gilt)."""
+        return self.shortcut_table.cellWidget(self._rows.index(action_id), COL_RESET)
+
+    def _edit_row(self, row: int, _column: int = COL_KEYS) -> None:
+        self.shortcut_table.editItem(self.shortcut_table.item(row, COL_KEYS))
+
+    def _reset_all(self) -> None:
+        for entry in shortcuts.ACTIONS:
+            self._keys[entry.id] = entry.default
+            self._show_keys(entry.id)
+        self._check_conflicts()
+
+    def _check_conflicts(self) -> None:
+        """Doppelt belegte Kürzel rot markieren; solange es sie gibt, ist Speichern gesperrt."""
+        found = shortcuts.conflicts(self._keys)
+        clashing = {action_id for _, ids in found for action_id in ids}
+        for row, action_id in enumerate(self._rows):
+            color = CONFLICT_COLOR if action_id in clashing else None
+            for column in (COL_ACTION, COL_SCOPE, COL_KEYS):
+                self.shortcut_table.item(row, column).setData(Qt.ItemDataRole.ForegroundRole, color)
+        lines = [f"{_native(seq)}: " + ", ".join(shortcuts.action(i).name for i in ids)
+                 for seq, ids in found]
+        self.conflict_hint.setText("Tastenkürzel doppelt belegt – zum Speichern eines ändern:\n"
+                                   + "\n".join(lines))
+        self.conflict_hint.setVisible(bool(found))
+        self.save_button.setEnabled(not found)
+
     def _family_changed(self, _font) -> None:
         self._family_touched = True
 
@@ -120,10 +257,13 @@ class SettingsDialog(QDialog):
             check_media_on_start=self.check_media.isChecked(),
             start_zoom=self.zoom.value(),
             theme=self.theme.currentData(),
-            shortcuts=dict(self._shortcuts),
+            shortcuts={action_id: seq for action_id, seq in self._keys.items()
+                       if not _same(seq, shortcuts.action(action_id).default)},
         )
 
     def accept(self) -> None:
+        if not self.save_button.isEnabled():
+            return                                   # Kürzel doppelt belegt (Hinweis steht da)
         settings = self.values()
         try:
             save_settings(settings, self.path)
@@ -133,3 +273,42 @@ class SettingsDialog(QDialog):
             return                                   # Dialog bleibt offen
         self.saved = settings
         super().accept()
+
+
+class _KeyDelegate(QStyledItemDelegate):
+    """Spalte „Kürzel“: Bearbeiten mit ``QKeySequenceEdit`` – genau eine Tastenkombination,
+    ✕ leert. Esc bricht ab (die Tabelle schließt den Editor ohne Übernahme)."""
+
+    def __init__(self, dialog: SettingsDialog):
+        super().__init__(dialog)
+        self._dialog = dialog
+
+    def createEditor(self, parent, option, index) -> QKeySequenceEdit:
+        editor = QKeySequenceEdit(parent)
+        editor.setMaximumSequenceLength(1)
+        editor.setClearButtonEnabled(True)
+        # Kombination erfasst: Fokus zurück an die Tabelle – das übernimmt und schließt den
+        # Editor auf dem üblichen Weg (wie ein Klick daneben)
+        editor.editingFinished.connect(self._dialog.shortcut_table.setFocus)
+        return editor
+
+    def setEditorData(self, editor: QKeySequenceEdit, index) -> None:
+        editor.setKeySequence(QKeySequence(index.data(Qt.ItemDataRole.UserRole)))
+
+    def setModelData(self, editor: QKeySequenceEdit, model, index) -> None:
+        seq = editor.keySequence().toString(_PORTABLE)
+        if shortcuts.is_well_formed(seq):
+            self._dialog.set_shortcut(self._dialog._rows[index.row()], seq)
+
+
+def _native(seq: str) -> str:
+    """Kürzel zum Anzeigen (z. B. „Strg+P“ mit deutscher Qt-Übersetzung)."""
+    return QKeySequence(seq).toString(_NATIVE)
+
+
+def _same(a: str, b: str) -> bool:
+    """Gleiches Kürzel trotz anderer Schreibweise („ctrl+p“ = „Ctrl+P“)."""
+    try:
+        return shortcuts.normalize(a) == shortcuts.normalize(b)
+    except ValueError:
+        return a == b
diff --git a/src/labelwerk/gui/theme/rawblock.qss b/src/labelwerk/gui/theme/rawblock.qss
index 2c5cfd5..03e60a5 100644
--- a/src/labelwerk/gui/theme/rawblock.qss
+++ b/src/labelwerk/gui/theme/rawblock.qss
@@ -116,6 +116,42 @@ QToolButton#layoutButton { background: #FFFFFF; border: 3px solid #000000; borde
 QToolButton#layoutButton:hover { background: #000000; }
 QToolButton#layoutButton:disabled { background: #F0F0F0; border-color: #CCCCCC; }
 
+/* Einstellungen: Reiter und Kürzel-Tabelle */
+QTabWidget::pane { border: 3px solid #000000; top: -3px; }
+QTabBar::tab {
+    background: #FFFFFF;
+    border: 3px solid #000000;
+    padding: 6px 14px;
+    margin-right: -3px;
+    font-weight: 700;
+    letter-spacing: 1px;
+}
+QTabBar::tab:selected { background: #000000; color: #FFFFFF; }
+QTabBar::tab:hover:!selected { background: #E8E8E8; }
+QTableWidget {
+    border: 3px solid #000000;
+    gridline-color: #CCCCCC;
+    selection-background-color: #000000;
+    selection-color: #FFFFFF;
+}
+QHeaderView::section {
+    background: #000000;
+    color: #FFFFFF;
+    border: none;
+    border-right: 1px solid #FFFFFF;
+    padding: 4px 8px;
+    font-weight: 700;
+    letter-spacing: 1px;
+}
+QPushButton#tableButton { border-width: 2px; padding: 1px 8px; margin: 1px 2px; letter-spacing: 0; }
+QKeySequenceEdit QLineEdit {
+    background: #F0F0F0;
+    border: 3px solid #000000;
+    border-radius: 0;
+    padding: 0 4px;
+    font-family: "Space Mono", "DejaVu Sans Mono", monospace;
+}
+
 QStatusBar { border-top: 3px solid #000000; }
 QStatusBar QLabel[state="ok"] { color: #008000; font-weight: 700; }
 QStatusBar QLabel[state="error"] { color: #FF0000; font-weight: 700; }
```

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `672 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add src/labelwerk/gui/main_window.py src/labelwerk/gui/panels/text.py src/labelwerk/gui/settings_dialog.py src/labelwerk/gui/theme/rawblock.qss tests/gui/conftest.py tests/gui/test_gui_settings.py tests/gui/test_gui_text.py tests/gui/test_gui_window.py
git commit -m "GUI: Einstellungen mit Reiter Tastenkürzel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Rückfrage bei überstehenden Objekten, Auswahl im Verlauf, Doku

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-17-freies-platzieren-design.md`
- Modify: `src/labelwerk/gui/history.py`
- Modify: `src/labelwerk/gui/main_window.py`
- Modify: `tests/gui/test_gui_editbar.py`
- Modify: `tests/gui/test_gui_history.py`
- Modify: `tests/gui/test_gui_layout.py`
- Modify: `tests/gui/test_gui_window.py`

**Interfaces / Produces:** `MainWindow.confirm_outside() -> bool` (patchbar wie `confirm_empty`); Verlauf speichert die Auswahl je Zustand; README/CLAUDE.md/Spec aktualisiert.

- [ ] **Step 1: Tests – Patch anwenden**

```diff
diff --git a/tests/gui/test_gui_editbar.py b/tests/gui/test_gui_editbar.py
index 8db3a2a..3509c97 100644
--- a/tests/gui/test_gui_editbar.py
+++ b/tests/gui/test_gui_editbar.py
@@ -445,11 +445,16 @@ def test_ctrl_z_in_editor_uses_editor_undo(window, qtbot):
     assert editor.toPlainText() == "Eins"                   # Aufbau des Editors ist kein Schritt
 
 
-def test_undo_keeps_valid_selection(window):
+def test_undo_restores_selection_of_the_state(window):
     window.canvas.set_selection([1])
     window.canvas.nudge(1, 0)
     _undo(window)
     assert window.canvas.selection() == [1]
     window.create_text(30, 12)
+    assert window.canvas.selection() == [2]
     _undo(window)
-    assert window.canvas.selection() == []
+    assert window.canvas.selection() == [1]                 # Auswahl vor dem Anlegen
+    window.canvas.set_selection([0])
+    window.delete_selected()
+    _undo(window)
+    assert window.canvas.selection() == [0]                 # Gelöschtes ist wieder gewählt
diff --git a/tests/gui/test_gui_history.py b/tests/gui/test_gui_history.py
index a65fadf..8eed104 100644
--- a/tests/gui/test_gui_history.py
+++ b/tests/gui/test_gui_history.py
@@ -128,3 +128,39 @@ def test_restore_keeps_the_document_object():
     restore(doc, snapshot)
     assert doc == snapshot and doc is not snapshot
     assert (doc.label_id, doc.length_mm, doc.orientation) == ("29", None, "horizontal")
+
+
+# --- Auswahl je Stand -------------------------------------------------------------
+def test_undo_and_redo_restore_selection_of_each_state():
+    history = History(_doc("A"))
+    history.push(_doc("A"), selection=[0])          # nur Auswahl geändert: kein Schritt
+    assert not history.can_undo()
+    history.push(_doc("B"), selection=[1])
+    history.undo(_doc("B"), selection=[1])
+    assert history.selection == [0]
+    history.redo(_doc("A"), selection=[0])
+    assert history.selection == [1]
+
+
+def test_selection_is_a_copy():
+    history = History(_doc("A"))
+    chosen = [0]
+    history.push(_doc("B"), selection=chosen)
+    chosen.append(1)
+    assert history.selection == [0]
+
+
+def test_reset_clears_selection():
+    history = History(_doc("A"))
+    history.push(_doc("B"), selection=[0])
+    history.reset(_doc("C"))
+    assert history.selection == []
+
+
+def test_select_updates_current_state_only_without_pending_change():
+    history = History(_doc("A"))
+    history.select(_doc("A"), [0])
+    history.select(_doc("A geändert"), [5])         # gehört schon zum nächsten Schritt
+    history.push(_doc("B"), selection=[1])
+    history.undo(_doc("B"), selection=[1])
+    assert history.selection == [0]
diff --git a/tests/gui/test_gui_layout.py b/tests/gui/test_gui_layout.py
index 5745872..c5eec8a 100644
--- a/tests/gui/test_gui_layout.py
+++ b/tests/gui/test_gui_layout.py
@@ -262,6 +262,31 @@ def test_bring_forward_and_send_backward_follow_selection(window):
     assert window.panel("text").edit.toPlainText() == "Eins"   # Panel folgt dem Objekt
 
 
+def test_undo_and_redo_of_reorder_keep_selection_on_same_objects(window):
+    window.canvas.set_selection([0])
+    _press(window, "object.bring_forward")
+    assert window.canvas.selection() == [1]
+    window.actions["edit.undo"].trigger()
+    assert [o.text for o in window.doc.objects] == ["Eins", "Zweiter", "Drei"]
+    assert [window.doc.objects[i].text for i in window.canvas.selection()] == ["Eins"]
+    assert window.panel("text").edit.toPlainText() == "Eins"
+    window.actions["edit.redo"].trigger()
+    assert [window.doc.objects[i].text for i in window.canvas.selection()] == ["Eins"]
+
+
+def test_undo_keeps_panel(window):
+    """Rückgängig wechselt nicht vom Reiter Layout weg, auch wenn sich die Auswahl ändert."""
+    window.canvas.set_selection([0])
+    window.tool_actions["layout"].trigger()
+    window.canvas.set_selection([])
+    window.canvas.set_selection([2])
+    _press(window, "object.send_backward")
+    window._show_tool("paper")
+    window.actions["edit.undo"].trigger()
+    assert window.panels.currentWidget() is window.panel("paper")
+    assert [window.doc.objects[i].text for i in window.canvas.selection()] == ["Drei"]
+
+
 def test_order_of_several_selected(window):
     window.canvas.set_selection([1, 0])
     _press(window, "object.bring_forward")
diff --git a/tests/gui/test_gui_window.py b/tests/gui/test_gui_window.py
index 979a41d..f575aca 100644
--- a/tests/gui/test_gui_window.py
+++ b/tests/gui/test_gui_window.py
@@ -388,3 +388,49 @@ def test_global_actions_come_from_shortcut_registry(window, monkeypatch):
     window_actions = QWidget.actions(window)                # self.actions ist das Verzeichnis
     assert all(window.actions[key] in window_actions
                for key in ("view.zoom_in", "view.zoom_out", "view.zoom_reset", "edit.undo"))
+
+
+# --- Rückfrage: Objekt ragt über das Etikett --------------------------------------
+def _outside_window(qtbot):
+    from labelwerk.document import Document, TextObject
+    from labelwerk.settings import Settings
+    doc = Document("62", length_mm=30, objects=[TextObject("Rand", size_pt=20, x_mm=55, y_mm=5)])
+    win = MainWindow(doc=doc, settings=Settings(check_media_on_start=False))
+    qtbot.addWidget(win)
+    return win
+
+
+def test_print_with_outside_object_asks_and_no_does_not_print(qtbot, monkeypatch):
+    win = _outside_window(qtbot)
+    asked = []
+    monkeypatch.setattr(QMessageBox, "question",
+                        lambda *a, **kw: asked.append(a) or QMessageBox.StandardButton.No)
+    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
+                        lambda *a, **kw: pytest.fail("darf nicht drucken"))
+    win.print_label()
+    (_, title, text, buttons, default), = asked
+    assert text == "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?"
+    assert buttons == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
+    assert default == QMessageBox.StandardButton.No
+    assert not win.is_printing() and win.print_action.isEnabled()
+
+
+def test_print_with_outside_object_yes_prints(qtbot, monkeypatch):
+    win = _outside_window(qtbot)
+    monkeypatch.setattr(MainWindow, "confirm_outside", lambda self: True)
+    monkeypatch.setattr("labelwerk.gui.print_worker.find_brother_lp", lambda: "file:///dev/usb/lp0")
+    sent = []
+    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
+                        lambda *a, **kw: sent.append(a) or {"did_print": True})
+    win.print_label()
+    qtbot.waitUntil(lambda: win.print_action.isEnabled(), timeout=3000)
+    assert sent and win.result.text() == "Gedruckt ✓"
+
+
+def test_print_inside_label_does_not_ask(window, qtbot, monkeypatch):
+    monkeypatch.setattr(MainWindow, "confirm_outside", lambda self: pytest.fail("keine Rückfrage"))
+    monkeypatch.setattr("labelwerk.gui.print_worker.print_image",
+                        lambda *a, **kw: {"did_print": True})
+    window.panel("text").edit.setPlainText("Hallo")
+    window.print_label()
+    qtbot.waitUntil(lambda: window.print_action.isEnabled(), timeout=3000)
```

- [ ] **Step 2: Rot prüfen** – Run: `.venv/bin/python -m pytest -q` – Expected: die neuen bzw. geänderten Tests schlagen fehl (fehlende Namen/Attribute oder falsche Werte), alle übrigen bestehen.

- [ ] **Step 3: Implementierung – Patch anwenden**

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 3250907..4961ab1 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -13,7 +13,8 @@ Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62
 - `labelwerk install-desktop` trägt die GUI mit Icon im Starter ein (XDG, `~/.local/share`); App-ID `labelwerk`.
 - Papier: Ausrichtung H/V, Ränder, Medium prüfen (GUI + `labelwerk media`), Einstellungen (`settings.json`, GUI-Dialog), Live-Druckererkennung.
 - Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.
-- 280 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
+- Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
+- 681 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).
 
 ## Architektur
 ```
@@ -32,15 +33,21 @@ src/labelwerk/
   document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit)
   settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic)
   media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
+  layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, objects_outside
+  shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich), effective, conflicts, validate
   desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
   gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
-    main_window.py  Hauptfenster, Werkzeugleiste, Statusleiste
-    tools.py        Werkzeug-Registry (Papier, Text; neue Werkzeuge als Eintrag)
-    panels/         Eigenschaften-Panels je Werkzeug (paper, text)
-    canvas.py       Etikett in echter Größe, Lineale, Zug-Anfasser, Zoom
+    main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen
+    tools.py        Werkzeug-Registry (Papier, Text, Layout; neue Werkzeuge als Eintrag)
+    panels/         Eigenschaften-Panels je Werkzeug (paper, text mit Bereich Position)
+    panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
+    canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom
+    actions.py      QActions aus shortcuts.ACTIONS – jedes Kürzel der App läuft hierüber (apply_shortcuts)
+    history.py      Rückgängig/Wiederherstellen: Dokument-Schnappschüsse samt Auswahl, höchstens 100
+    symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
     print_worker.py Drucken im Hintergrund-Thread
     media_worker.py  Medium prüfen im Hintergrund
-    settings_dialog.py Einstellungen (inkl. Design: RawBlock/Klassisch, sofort wirksam über app.apply_theme)
+    settings_dialog.py Einstellungen: Reiter Allgemein (inkl. Design, sofort wirksam über app.apply_theme) und Tastenkürzel (Konflikte sperren Speichern)
     theme/          QSS-Stylesheet (rawblock.qss)
     icons/          labelwerk.svg (Platzhalter; eigenes Logo: SVG Tiny, quadratisch, Text als Pfade, ab 16 px erkennbar)
   cli.py      labelwerk labels | labelwerk media | labelwerk fonts | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
@@ -77,7 +84,7 @@ labelwerk print "X1 -K3\nKlemme 24V" -l 62
 ## GUI (MVP umgesetzt)
 Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).
 
-Nächste Schritte: Etappe 2 (Roadmap 0) bzw. Werkzeug ‚Bild‘ (Roadmap 5) als neuer Eintrag in `gui/tools.py`.
+Nächste Schritte: Etappe 3d-2 Werkzeug ‚Bild‘ (Roadmap 0/5) als neuer Eintrag in `gui/tools.py`, Objekt im selben Modell wie Text.
 
 Anforderungen MVP:
 - Mehrzeiliges Textfeld
@@ -94,7 +101,7 @@ Umsetzung:
 - GUI bleibt dünn: Logik, die testbar ist, gehört in den Kern
 
 ## Roadmap danach
-0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (Spec 2026-10-17-freies-platzieren) · 3d-2 Bild · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
+0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-2 Bild · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
 1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
 2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
 3. Barcodes und QR-Codes
diff --git a/README.md b/README.md
index a756591..a30338f 100644
--- a/README.md
+++ b/README.md
@@ -45,11 +45,15 @@ labelwerk-gui
 labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entfernt den Eintrag wieder
 ```
 
-Aufbau wie im P-touch Editor: Werkzeugleiste (Papier, Text), Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.
+Aufbau wie im P-touch Editor: Werkzeugleiste (Papier, Text, Layout), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.
 
 Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil); gespeichert in `~/.config/labelwerk/settings.json`.
 
-Text: Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition – zeichenweise wie im P-touch Editor. Ohne Markierung gilt die Formatierung für den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend aufs Etikett.
+Text: Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition – zeichenweise wie im P-touch Editor. Ohne Markierung gilt die Formatierung für den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.
+
+Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste und einem Klick aufs Etikett einen Rahmen anlegen; Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.
+
+Tastenkürzel: Alle Kürzel lassen sich unter „Einstellungen“ → „Tastenkürzel“ ändern (Zeile anklicken, neue Kombination drücken). Doppelt belegte Kürzel werden rot markiert und sperren das Speichern.
 
 ## Architektur
 
@@ -63,6 +67,8 @@ document.py Etikett-Dokument (Etikett, Länge, Objekte)
 settings.py Einstellungen (JSON)
 fonts.py    Schriften (fontconfig)
 media.py    Medium prüfen (Statusabfrage des Druckers)
+layout.py   Platzieren: Einrasten, Ausrichten, Größe angleichen, ragt hinaus
+shortcuts.py Tastenkürzel-Verzeichnis (Standard, Konflikte, Prüfung)
 gui/        PySide6-Oberfläche (nur Anzeige/Bearbeitung, kein Druckcode)
 ```
 
diff --git a/docs/superpowers/specs/2026-10-17-freies-platzieren-design.md b/docs/superpowers/specs/2026-10-17-freies-platzieren-design.md
index ceee3d2..88ab293 100644
--- a/docs/superpowers/specs/2026-10-17-freies-platzieren-design.md
+++ b/docs/superpowers/specs/2026-10-17-freies-platzieren-design.md
@@ -102,7 +102,7 @@ Ohne Auswahl sind die Knöpfe gesperrt.
 
 ### Rückgängig
 
-Dokument-Schnappschüsse (`copy.deepcopy(doc)`) nach jeder abgeschlossenen Aktion (Verschieben, Anfasser, Anlegen, Löschen, Einfügen, Ausrichten, Drehen, Reihenfolge, Panel-Änderung – Tippen wird zu einem Schritt zusammengefasst, wenn der Fokus das Textfeld verlässt), höchstens 100. Im Textfeld gilt das Rückgängig des Editors.
+Dokument-Schnappschüsse (`copy.deepcopy(doc)`) nach jeder abgeschlossenen Aktion (Verschieben, Anfasser, Anlegen, Löschen, Einfügen, Ausrichten, Drehen, Reihenfolge, Panel-Änderung – Tippen wird zu einem Schritt zusammengefasst, wenn der Fokus das Textfeld verlässt), höchstens 100. Im Textfeld gilt das Rückgängig des Editors. Mit jedem Stand wird die Auswahl gespeichert, die zuletzt zu ihm galt; Rückgängig/Wiederherstellen stellt sie wieder her (dieselben Objekte, auch nach „Reihenfolge“) und wechselt dabei nicht den Reiter.
 
 ### Einstellungen: Reiter
 
diff --git a/src/labelwerk/gui/history.py b/src/labelwerk/gui/history.py
index c396eb3..df5468e 100644
--- a/src/labelwerk/gui/history.py
+++ b/src/labelwerk/gui/history.py
@@ -3,11 +3,15 @@
 Nach jeder abgeschlossenen Aktion hält das Hauptfenster den Stand mit ``push`` fest.
 Änderungen, die noch nicht festgehalten sind (z. B. Tippen im Textfeld, das erst beim
 Verlassen des Felds ein Schritt wird), macht ``undo`` vorher selbst zu einem Schritt.
+
+Zu jedem Stand gehört die Auswahl (Indizes), die zuletzt dazu galt: Nach Rückgängig/
+Wiederherstellen zeigt ``selection`` sie, damit die Auswahl auf denselben Objekten liegt –
+auch wenn sich die Reihenfolge geändert hat.
 """
 from __future__ import annotations
 
 import copy
-from dataclasses import fields
+from dataclasses import dataclass, field, fields
 from typing import Hashable
 
 from PySide6.QtCore import QObject, Signal
@@ -17,6 +21,12 @@ from ..document import Document
 LIMIT = 100   # höchstens so viele Schritte zurück
 
 
+@dataclass
+class _State:
+    doc: Document
+    selection: list[int] = field(default_factory=list)
+
+
 class History(QObject):
     changed = Signal()   # Rückgängig/Wiederherstellen ggf. jetzt (nicht mehr) möglich
 
@@ -27,26 +37,41 @@ class History(QObject):
 
     def reset(self, doc: Document) -> None:
         """Neuer Ausgangsstand (z. B. neues oder geöffnetes Etikett) – ohne Schritte."""
-        self._states = [copy.deepcopy(doc)]
+        self._states = [_State(copy.deepcopy(doc))]
         self._pos = 0
         self._merge: Hashable | None = None
         self.changed.emit()
 
-    def push(self, doc: Document, merge: Hashable | None = None) -> bool:
+    @property
+    def selection(self) -> list[int]:
+        """Auswahl, die zum aktuellen Stand gehört (Kopie)."""
+        return list(self._states[self._pos].selection)
+
+    def select(self, current: Document, selection: list[int]) -> None:
+        """Auswahl geändert (kein Schritt): gilt für den aktuellen Stand – nur wenn ``current``
+        ihm noch entspricht, sonst gehört sie zum nächsten ``push``."""
+        if current == self._states[self._pos].doc:
+            self._states[self._pos].selection = list(selection)
+
+    def push(self, doc: Document, merge: Hashable | None = None,
+             selection: list[int] = ()) -> bool:
         """Stand nach einer Aktion festhalten; False, wenn sich nichts geändert hat.
 
-        Aufeinanderfolgende Schritte mit gleichem ``merge`` (z. B. Pfeiltasten auf dieselbe
-        Auswahl) werden zu einem Schritt zusammengefasst.
+        ``selection`` ist die Auswahl dazu – ohne Änderung am Dokument wird nur sie für den
+        aktuellen Stand übernommen. Aufeinanderfolgende Schritte mit gleichem ``merge``
+        (z. B. Pfeiltasten auf dieselbe Auswahl) werden zu einem Schritt zusammengefasst.
         """
-        if doc == self._states[self._pos]:
+        state = _State(self._states[self._pos].doc, list(selection))
+        if doc == state.doc:
+            self._states[self._pos] = state
             return False
-        snapshot = copy.deepcopy(doc)
+        state.doc = copy.deepcopy(doc)
         if (merge is not None and merge == self._merge and self._pos > 0
                 and self._pos == len(self._states) - 1):
-            self._states[self._pos] = snapshot
+            self._states[self._pos] = state
         else:
             del self._states[self._pos + 1:]        # Wiederherstellen verfällt
-            self._states.append(snapshot)
+            self._states.append(state)
             del self._states[:-(self.limit + 1)]
             self._pos = len(self._states) - 1
         self._merge = merge
@@ -59,19 +84,20 @@ class History(QObject):
     def can_redo(self, current: Document | None = None) -> bool:
         return self._pos < len(self._states) - 1 and not self._pending(current)
 
-    def undo(self, current: Document) -> Document | None:
-        """Stand vor dem letzten Schritt (Kopie) oder None; ``current`` = Dokument jetzt."""
-        self.push(current)
+    def undo(self, current: Document, selection: list[int] = ()) -> Document | None:
+        """Stand vor dem letzten Schritt (Kopie) oder None; ``current`` = Dokument jetzt,
+        ``selection`` = Auswahl jetzt. Die Auswahl des neuen Stands steht in ``selection``."""
+        self.push(current, selection=selection)
         if self._pos == 0:
             return None
         return self._step(-1)
 
-    def redo(self, current: Document) -> Document | None:
+    def redo(self, current: Document, selection: list[int] = ()) -> Document | None:
         """Rückgängig gemachten Schritt wiederholen (Kopie) oder None.
 
         Hat sich ``current`` seitdem geändert, ist das ein neuer Schritt – nichts mehr zu
         wiederholen."""
-        self.push(current)
+        self.push(current, selection=selection)
         if self._pos == len(self._states) - 1:
             return None
         return self._step(+1)
@@ -80,10 +106,10 @@ class History(QObject):
         self._pos += direction
         self._merge = None
         self.changed.emit()
-        return copy.deepcopy(self._states[self._pos])
+        return copy.deepcopy(self._states[self._pos].doc)
 
     def _pending(self, current: Document | None) -> bool:
-        return current is not None and current != self._states[self._pos]
+        return current is not None and current != self._states[self._pos].doc
 
 
 def restore(target: Document, snapshot: Document) -> None:
diff --git a/src/labelwerk/gui/main_window.py b/src/labelwerk/gui/main_window.py
index 7911659..3627e3b 100644
--- a/src/labelwerk/gui/main_window.py
+++ b/src/labelwerk/gui/main_window.py
@@ -80,6 +80,8 @@ class MainWindow(QMainWindow):
         self._media_check_pending = False
         self._clipboard: list[TextObject] = []      # interne Zwischenablage (Kopien)
         self._merge_next = None                     # Pfeiltasten: Schritte zusammenfassen
+        self._restoring = False                     # Rückgängig setzt gerade die Auswahl
+        self._outside: list[int] = []               # Objekte, die über das Etikett ragen
         # alle Kürzel kommen aus dem Verzeichnis (shortcuts.ACTIONS) und sind änderbar
         self.actions = build_actions(self, effective(self.settings.shortcuts))
 
@@ -290,6 +292,9 @@ class MainWindow(QMainWindow):
         """Auswahl auf der Arbeitsfläche: Panel des Objekts zeigen – außer ein Panel, das mit
         der Auswahl arbeitet (Text, Layout), ist schon zu sehen."""
         self._follow_selection(indices)
+        if self._restoring:                         # Rückgängig wechselt nicht den Reiter
+            return
+        self.history.select(self.doc, indices)
         if indices:
             self._show_object_panel()
 
@@ -356,6 +361,7 @@ class MainWindow(QMainWindow):
         self.panel("text").show_error(None)
         self.image = image
         self.rendered = rendered
+        self._outside = outside
         self.canvas.set_document(get_label(self.doc.label_id), size, rendered, self.doc.orientation,
                                  area, keep_ratio=[not obj.fit for obj in self.doc.objects])
         self._update_frame()
@@ -383,22 +389,29 @@ class MainWindow(QMainWindow):
 
         Vor jeder Aktion aufgerufen, wird noch nicht Festgehaltenes (Getipptes) ein eigener
         Schritt. Tippen im Textfeld wird ein Schritt, sobald der Fokus das Feld verlässt."""
-        self.history.push(self.doc, merge)
+        self.history.push(self.doc, merge, self.canvas.selection())
         self._update_edit_actions()
 
     def undo(self) -> None:
-        self._restore(self.history.undo(self.doc))
+        self._restore(self.history.undo(self.doc, self.canvas.selection()))
 
     def redo(self) -> None:
-        self._restore(self.history.redo(self.doc))
+        self._restore(self.history.redo(self.doc, self.canvas.selection()))
 
     def _restore(self, snapshot: Document | None) -> None:
+        """Stand zurückholen – samt der Auswahl, die zu ihm gehörte (dieselben Objekte)."""
         if snapshot is None:
             return
-        restore(self.doc, snapshot)
-        for panel in self._panel_by_key.values():
-            panel.refresh()
-        self.render_now()                       # Auswahl bleibt, soweit es die Objekte noch gibt
+        selection = self.history.selection
+        self._restoring = True       # Auswahl, die beim Neuzeichnen entfällt, nicht festhalten
+        try:
+            restore(self.doc, snapshot)
+            for panel in self._panel_by_key.values():
+                panel.refresh()
+            self.render_now()
+            self.canvas.set_selection(selection)        # ungültige Indizes entfallen
+        finally:
+            self._restoring = False
         self._update_edit_actions()
 
     # --- Objekte auf der Arbeitsfläche ------------------------------------
@@ -435,9 +448,9 @@ class MainWindow(QMainWindow):
         family = None if self.settings.font_family == DEFAULT_FAMILY else self.settings.font_family
         obj = TextObject.plain("", size_pt=self.settings.font_size_pt or DEFAULT_PT, family=family)
         obj.x_mm, obj.y_mm = round(x_mm, 1), round(y_mm, 1)
-        self.canvas.set_selection([])
         self.doc.objects[:] = [o for o in self.doc.objects if not o.is_empty()]
         self.doc.objects.append(obj)
+        self.canvas.set_selection([])     # erst nach der Änderung: Auswahl davor bleibt im Stand
         index = len(self.doc.objects) - 1
         self._objects_changed(list(range(len(self.doc.objects))))
         self.canvas.set_selection([index])
@@ -457,9 +470,9 @@ class MainWindow(QMainWindow):
         if not indices:
             return
         self._commit()
-        self.canvas.set_selection([])
         for index in sorted(indices, reverse=True):
             del self.doc.objects[index]
+        self.canvas.set_selection([])     # erst nach der Änderung: Auswahl davor bleibt im Stand
         self.render_now()
         self._commit()
 
@@ -686,6 +699,14 @@ class MainWindow(QMainWindow):
         self.panel("paper").set_checking(False)
         self._run_pending_media_check()
 
+    def confirm_outside(self) -> bool:
+        answer = QMessageBox.question(
+            self, "Objekt ragt hinaus",
+            "Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?",
+            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
+            QMessageBox.StandardButton.No)
+        return answer == QMessageBox.StandardButton.Yes
+
     def confirm_empty(self) -> bool:
         answer = QMessageBox.question(
             self, "Leeres Etikett", "Das Etikett ist leer. Trotzdem drucken?",
@@ -706,6 +727,9 @@ class MainWindow(QMainWindow):
         if self.doc.is_empty() and not self.confirm_empty():
             self._set_printing(False)
             return
+        if self._outside and not self.confirm_outside():
+            self._set_printing(False)
+            return
         self.result.setProperty("state", "")  # altes Rot/Grün nicht stehen lassen
         self.result.style().polish(self.result)
         self.result.setText("Drucke …")
````

- [ ] **Step 4: Grün prüfen** – Run (dreimal): `.venv/bin/python -m pytest -q > /tmp/claude-1000/lw.txt 2>&1; echo "exit $?"` – Expected: `681 passed`, `exit 0`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-10-17-freies-platzieren-design.md src/labelwerk/gui/history.py src/labelwerk/gui/main_window.py tests/gui/test_gui_editbar.py tests/gui/test_gui_history.py tests/gui/test_gui_layout.py tests/gui/test_gui_window.py
git commit -m "Freies Platzieren: Rückfrage bei überstehenden Objekten, Doku

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Abnahme (manuell, durch den Nutzer)

- [ ] Neues Etikett: Text tippen, Rahmen mit der Maus verschieben – rastet an Etikettmitte/Rändern ein (rote Linie), Alt hält das Einrasten aus.
- [ ] Werkzeug „A“ + Klick → zweiter Textrahmen; Absender klein links oben, Empfänger groß darunter (Versandetikett).
- [ ] Ecke ziehen skaliert die Schrift, Kante schaltet „Feste Rahmengröße“ ein; Position X/Y im Panel eintippen.
- [ ] Pfeiltasten (0,1 mm / mit Umschalt 1 mm), Entf, Strg+C/V/D, Strg+Z/Strg+Umschalt+Z.
- [ ] Reiter LAYOUT: am Papier zentrieren, zwei Objekte links ausrichten, gleiche Größe, drehen, Reihenfolge.
- [ ] Einstellungen → Tastenkürzel: ein Kürzel ändern, Konflikt erzeugen (Speichern gesperrt), zurücksetzen.
- [ ] Objekt über den Rand schieben → Hinweis; Drucken fragt nach. Horizontal-Ausrichtung: Verschieben funktioniert genauso.
- [ ] Testdruck auf DK-22205.
