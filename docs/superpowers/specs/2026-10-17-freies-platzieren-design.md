# Freies Platzieren (Etappe 3d-1) – Design

Stand: 2026-10-17 · Status: abgestimmt

## Ziel

Objekte frei auf dem Etikett anordnen wie im P-touch Editor: mehrere Textrahmen, auswählen, mit der Maus verschieben, an Anfassern skalieren, einrasten, per Tastatur und Zahlen positionieren, ausrichten (Reiter „Layout“), drehen (90°), Reihenfolge ändern, Kopieren/Einfügen, Rückgängig. Alle Tastenkürzel sind in den Einstellungen änderbar.

Grundlage für 3d-2 (Werkzeug „Bild“: PNG/JPG/PDF mit Zuschnitt wie `print-file`) – das Bild-Objekt reiht sich in dasselbe Modell ein.

## Nicht enthalten

Bild-Objekt (3d-2), Favoriten und Neu/Öffnen/Speichern (3c), Zierrahmen ums Etikett (eigene Etappe), Linie/Rechteck/Tabelle, freie Drehwinkel, Gruppieren, Ebenenliste, Bildschirmfoto/ClipArt/Symbole.

## Architektur

Jedes Objekt wird **einzeln** vom Kern gerendert (`render_object`). Die Arbeitsfläche zeigt jedes Objektbild als eigenes Element an seiner Position – Ziehen verschiebt nur dieses Bild (flüssig). Der Druck setzt mit `render_document` aus denselben Objektbildern zusammen: **Vorschau = Druck** bleibt erhalten. Qt zeichnet keinen Text selbst.

Platzier-Logik (Einrasten, Ausrichten, Skalieren, „ragt hinaus“) und Kürzel-Verzeichnis liegen Qt-frei im Kern; die GUI ruft nur auf.

## Kern

### Modell (`document.py`)

`TextObject` bekommt:

```python
x_mm: float | None = None      # linke obere Ecke des Rahmens in Leserichtung; None = mittig (wie bisher)
y_mm: float | None = None
w_mm: float | None = None      # Rahmengröße nur bei fit („Feste Rahmengröße“); None = bedruckbarer Bereich
h_mm: float | None = None
rotation: int = 0              # 0 | 90 | 180 | 270, Grad im Uhrzeigersinn
```

- **Koordinaten** in mm in Leserichtung, Ursprung = linke obere Ecke des Etiketts (inkl. Rand). Bei „horizontal“ ist x die Bandlaufrichtung (wie die gedrehte Arbeitsfläche).
- **Ohne Position** (`x_mm is None`): Objekt mittig auf dem Etikett – genau wie heute (CLI, Altbestand). Ein einzelnes Objekt ohne Position ergibt **pixelgleich** das heutige Bild.
- **Ohne feste Rahmengröße:** Rahmen = Größe des Textes. Ein positioniertes Objekt hat immer eine feste Schriftgröße (`size_pt` gesetzt); beim ersten Verschieben eines automatisch großen Objekts setzt die GUI die aktuell wirksame Größe als `size_pt` (Kern liefert sie, siehe `RenderedObject.base_pt`).
- **Mit fester Rahmengröße** (`fit`): Text wird in den Rahmen `w_mm × h_mm` eingepasst (Verhältnisse bleiben, wie heute); Textposition wirkt innerhalb des Rahmens. `w_mm/h_mm = None` = bedruckbarer Bereich (heutiges Verhalten).
- **Drehen:** Das Objektbild wird gedreht; Rahmenbreite und -höhe tauschen bei 90/270. Die Position bleibt die linke obere Ecke des gedrehten Rahmens.
- **Reihenfolge:** Listenreihenfolge in `doc.objects` = Zeichenreihenfolge (hinten → vorne).
- `Document.objects` bleibt `list[TextObject]` (3d-2 ergänzt `ImageObject`).

### Rendern (`render.py`)

- `render_object(obj, doc, model) -> RenderedObject(image, x, y, w, h, base_pt)` – Bild in Druckpunkten (L/RGB, weißer Grund, wird beim Zusammensetzen mit „multiply“/Maske aufgeklebt, damit sich Objekte nicht gegenseitig weiß überdecken), Position in Druckpunkten in Leserichtung (bei Objekten ohne Position: mittig auf dem Etikett berechnet), `base_pt` = wirksame Grundgröße.
- `render_document(doc, model)`: Etikettgröße bestimmen, Objektbilder in Listenreihenfolge aufkleben, bei „horizontal“ drehen (wie heute). Über das Etikett ragende Teile werden abgeschnitten.
- **Automatische Länge (Endlosband):** Länge = max(fernste Kante positionierter Objekte in Bandlaufrichtung + Rand, Größe nicht positionierter Objekte + 2 × Rand), begrenzt auf die Modellgrenzen. Feste Länge wie heute.
- `TextTooLarge` bei fester Größe nur noch für Objekte ohne Position (heutiges Verhalten); positionierte Objekte dürfen hinausragen (→ Hinweis statt Fehler).

### Platzier-Logik (`layout.py`, neu, ohne Qt)

Rechtecke als `Rect(x, y, w, h)` in mm.

- `object_rect(rendered) -> Rect`, `printable_area(doc, model) -> Rect` (Etikett minus Ränder, quer `render.MARGIN`).
- `snap(moving: Rect, targets: list[Rect], area: Rect, tolerance_mm) -> (dx, dy, guides)`: Kanten und Mitte des bewegten Rechtecks rasten an Etikettkanten/-mitte, bedruckbarem Bereich und Kanten/Mitten anderer Objekte ein; `guides` = Hilfslinien (senkrecht x / waagrecht y) zum Anzeigen. Toleranz kommt von der GUI (6 Bildschirmpixel → mm je nach Zoom).
- `align(rects, mode, area=None) -> list[Rect]`: `mode` ∈ left, hcenter, right, top, vcenter, bottom; mit `area` am Papier (bedruckbarer Bereich), sonst aneinander (Bezug: äußerste Kante bzw. Mitte der Auswahl).
- `match_size(rects, mode) -> list[Rect]`: `mode` ∈ same (Größe), width, height – Bezug ist das zuerst gewählte Objekt; `maximize(rect, area) -> Rect` (auf bedruckbaren Bereich, Seitenverhältnis bleibt).
- `scale_text(obj, factor) -> TextObject`: alle Größen (Grundgröße und Stücke) × factor, begrenzt auf 4–100 pt (Ecke ziehen, Größe angleichen bei Text ohne feste Rahmengröße).
- `objects_outside(doc, model) -> list[int]`: Indizes der Objekte, die über das Etikett ragen.

### Tastenkürzel (`shortcuts.py`, neu, ohne Qt)

- `ACTIONS`: Verzeichnis aller Aktionen – `Action(id, name, default, scope)`; `scope` ∈ global, canvas, text. Erfasst alle Kürzel der App: Drucken, Zoom, B/I/U, Auswahl/Text-Werkzeug, Ausschneiden/Kopieren/Einfügen/Duplizieren, Löschen, Rückgängig/Wiederherstellen, Pfeiltasten (fein/grob), Ausrichten, Drehen, Reihenfolge, Alles auswählen.
- `effective(overrides) -> dict[id, str]`, `conflicts(mapping) -> list[(seq, [ids])]` (gleiches Kürzel im selben Bereich bzw. global gegen jeden Bereich), `validate(overrides) -> (clean, warnings)` (unbekannte IDs/ungültige Kürzel → Warnung, ignoriert).
- Kürzel als Text im Qt-Format („Ctrl+Shift+Z“, „Del“); geprüft wird in der GUI mit `QKeySequence`, im Kern nur Form/Duplikate.

### Einstellungen

- Neues Feld `shortcuts: dict[str, str]` (nur geänderte Kürzel; Standard `{}`), geprüft mit `shortcuts.validate`.

## GUI

### Arbeitsfläche (`canvas.py`)

- Jedes Objekt ist ein Element (`ObjectItem`, Pixmap aus `render_object`) in Druckkoordinaten; Neu-Rendern nur des geänderten Objekts (verzögert wie heute).
- **Auswahl:** Klick wählt, Strg+Klick ergänzt/entfernt, Klick ins Leere hebt auf, Strg+A alles. Ausgewählte Objekte: gestrichelter Rahmen mit 8 Anfassern.
- **Verschieben** mit der Maus (flüssig), Modell erst beim Loslassen. **Einrasten** über `layout.snap`, rote Hilfslinie; Alt hält Einrasten aus.
- **Anfasser:** ohne feste Rahmengröße skalieren die Ecken die Schrift (`scale_text`, Vorschau beim Ziehen gestreckt, beim Loslassen neu gerendert); Kanten schalten „Feste Rahmengröße“ ein und ändern Breite/Höhe. Mit fester Rahmengröße ändern alle Anfasser den Rahmen.
- **Text anlegen:** Werkzeug „Text anlegen“ aktiv (Knopf „A“ in der Bearbeitungsleiste) + Klick aufs Etikett → neuer leerer Rahmen dort (Schriftgröße aus den Einstellungen), Schreibmarke ins Textfeld, Werkzeug springt zurück auf Auswahl. Doppelklick auf einen Textrahmen → Schreibmarke ins Textfeld.
- **Tastatur** (wenn die Arbeitsfläche den Fokus hat): Pfeile 0,1 mm, Umschalt+Pfeile 1 mm, Entf löschen, Strg+X/C/V (interne Zwischenablage, Einfügen 2 mm versetzt), Strg+D duplizieren, Strg+Z / Strg+Umschalt+Z.
- Länge ziehen (Endlosband) und Zoom bleiben wie bisher; horizontale Ausrichtung funktioniert über die gedrehte Ansicht gleich.

### Bearbeitungsleiste (neu, unter der Werkzeugleiste)

Auswahl-Pfeil, „A“ (Text anlegen) · Ausschneiden, Kopieren, Einfügen · Rückgängig, Wiederherstellen. Aktionen aus dem Kürzel-Verzeichnis, Tooltips mit Kürzel.

### Panels

- **Text-Panel** bearbeitet den ausgewählten Textrahmen (bei mehreren ausgewählten: das zuletzt gewählte). Ohne ausgewählten Text: Hinweis „Auf das Etikett klicken, um einen Textrahmen anzulegen“ und Werkzeug „Text anlegen“ aktiv.
- **Bereich „Position“** im Text-Panel: X, Y, Breite, Höhe in mm (0,1 mm Schritt). Breite/Höhe nur mit fester Rahmengröße editierbar, sonst Anzeige.
- Auswahl eines Objekts auf der Arbeitsfläche schaltet auf das Panel seines Werkzeugs.

### Reiter „Layout“ (neues Werkzeug in `tools.py`)

Wie P-touch, Knöpfe mit Liniensymbolen:
- **Gewählte Objekte ausrichten:** links, waagrecht mittig, rechts, oben, senkrecht mittig, unten (ab 2 Objekten).
- **Am Papier ausrichten:** dieselben sechs, Bezug bedruckbarer Bereich.
- **Vergrößern/Verkleinern:** auf Papier maximieren, gleiche Größe, gleiche Breite, gleiche Höhe.
- **Drehen:** 90° links, 90° rechts.
- **Reihenfolge:** nach vorne, nach hinten.
Ohne Auswahl sind die Knöpfe gesperrt.

### Rückgängig

Dokument-Schnappschüsse (`copy.deepcopy(doc)`) nach jeder abgeschlossenen Aktion (Verschieben, Anfasser, Anlegen, Löschen, Einfügen, Ausrichten, Drehen, Reihenfolge, Panel-Änderung – Tippen wird zu einem Schritt zusammengefasst, wenn der Fokus das Textfeld verlässt), höchstens 100. Im Textfeld gilt das Rückgängig des Editors.

### Einstellungen: Reiter

Der Einstellungsdialog bekommt Reiter **Allgemein** (bisheriger Inhalt) und **Tastenkürzel**: Tabelle Aktion | Bereich | Kürzel (Klick → `QKeySequenceEdit`), Knopf „Standard“ je Zeile und „Alle zurücksetzen“. Doppelte Kürzel werden rot markiert, Speichern ist dann gesperrt (Hinweis nennt die andere Aktion). Wirkt sofort nach dem Speichern.

## Fehlerfälle

- Objekt ragt über das Etikett: Hinweis in der Statusleiste; Drucken fragt nach („Objekt ragt über das Etikett hinaus und wird abgeschnitten. Trotzdem drucken?“).
- Leeres Etikett / kein Objekt: Hinweis „leerer Druck“ wie bisher.
- Ungültige Kürzel in `settings.json`: Warnung, Standard gilt.

## Tests

- **Kern:** einzelnes Objekt ohne Position pixelgleich zu vorher; Position in beiden Ausrichtungen (Tintenkante an x/y); Drehen 90/180/270 (Rahmen getauscht); Reihenfolge (oberes Objekt überdeckt Schwarz nicht mit Weiß); automatische Länge aus dem fernsten Objekt; Abschneiden; feste Rahmengröße mit w/h; `snap` (Kante, Mitte, Toleranz, Hilfslinien); `align` (aneinander, am Papier); `match_size`, `maximize`; `scale_text` (Grenzen 4–100); `objects_outside`; Kürzel `effective`/`conflicts`/`validate`; Einstellungen `shortcuts`.
- **GUI (offscreen):** Klick wählt, Strg+Klick, Ziehen per QTest verschiebt (Modell nach Loslassen), Einrasten an der Mitte, Ecke skaliert Schrift, Kante schaltet feste Rahmengröße ein, Text anlegen per Klick, Pfeiltasten 0,1/1 mm, Entf, Kopieren/Einfügen/Duplizieren, Rückgängig/Wiederherstellen, Panel X/Y wirkt, Layout-Knöpfe, Drehen, Reihenfolge, Kürzel-Reiter (Ändern, Konflikt sperrt Speichern, sofortige Wirkung), Druck-Rückfrage bei „ragt hinaus“.
- Jedes Widget bei `qtbot.addWidget`; immer den Exit-Code von pytest prüfen.
