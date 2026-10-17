# Text-Formatierung (Etappe 3a/3b) – Design

Stand: 2026-10-17 · Status: abgestimmt

## Ziel

Text wie im P-touch Editor formatieren – **zeichenweise**: Schriftart, Größe (pt), fett, kursiv, unterstrichen; Ausrichtung je Absatz (links, zentriert, rechts, Blocksatz); „Feste Rahmengröße“ (= automatische Größe). Hauptnutzen: Versandetiketten (linksbündige Adresse, kleine Absenderzeile, große Empfängerzeilen).

Aufteilung: **3a Kern + CLI**, **3b GUI-Editor**. Danach Etappe 3c „Neu/Öffnen/Speichern“ (eigene Spec) – das Textmodell ist dafür JSON-tauglich.

## Nicht enthalten

Effekte (Umriss, Schatten …), vertikaler Text (gestapelte Zeichen), automatischer Zeilenumbruch, freie Position des Textblocks (kommt mit „Freies Platzieren“), Zeichenabstand, Durchstreichen.

## 3a – Kern

### Modell (`document.py`)

```python
@dataclass
class Span:
    text: str
    family: str | None = None      # None = Standardschrift (DejaVu Sans)
    size_pt: float | None = None   # None = Grundgröße des Textobjekts
    bold: bool = True              # heutiges Aussehen bleibt Standard
    italic: bool = False
    underline: bool = False

@dataclass
class Paragraph:
    spans: list[Span]
    align: str = "center"          # left | center | right | justify

@dataclass
class TextObject:
    paragraphs: list[Paragraph]
    size_pt: float | None = None   # Grundgröße; None = automatisch („Feste Rahmengröße“)
    font_path: str | None = None   # wie bisher: feste TTF-Datei für Spans ohne family (CLI --font)
```

- Abwärtskompatibel: `TextObject("Hallo\nWelt", font_size_pt=…)`-artige Erzeugung über eine Fabrik `TextObject.plain(text, size_pt=None, align="center", family=None, bold=True, italic=False, underline=False, font_path=None)`; `TextObject.text` (Property) liefert den reinen Text (Absätze mit `\n` verbunden) für `is_empty()` und Tests. Bestehende Aufrufer werden auf `plain(...)` umgestellt.
- `ALIGNMENTS = ("left", "center", "right", "justify")`; unbekannte Ausrichtung → `ValueError` beim Rendern.
- Größen: `PT = 300 / 72` Druckpunkte pro pt. Erlaubt 4–100 pt.

### Schriften (`fonts.py`, neu, Qt-frei)

- `families() -> list[str]`: installierte Familien über `fc-list : family` (erste Bezeichnung je Zeile, sortiert, eindeutig), gecacht. Ohne fontconfig → `["DejaVu Sans"]`.
- `resolve(family, bold, italic) -> FontMatch(path, family, exact)`: über `fc-match -f "%{file}|%{family}" "<family>:weight=<bold?200:80>:slant=<italic?100:0>"`; `exact = False`, wenn fontconfig eine andere Familie liefert. Ohne fontconfig → bisherige DejaVu-Kandidaten (Bold/Oblique-Varianten). Gecacht (`functools.lru_cache`).
- `load(path, size_dots) -> ImageFont` gecacht.
- Standardfamilie: `"DejaVu Sans"`.

### Setzen (`render.py`)

- Für jeden Absatz: jedes Span mit seiner Schrift messen (`font.getlength`, `font.getmetrics`); Zeile = Spans hintereinander auf **gemeinsamer Grundlinie**; Zeilenhöhe = max(Ascent) + max(Descent) + Zeilenabstand. Leerer Absatz → Höhe der Grundschrift.
- **Kompatibilität:** Reiner Text mit Standardwerten (DejaVu Sans Bold, zentriert, automatisch) ergibt **pixelgleich** dasselbe Bild wie vor 3a (Zeilenabstand wie Pillows `multiline_text`, Test vergleicht Bytes mit einem vorher gespeicherten Referenzbild, das im Test mit dem alten Algorithmus erzeugt wird – siehe Plan).
- Ausrichtung je Absatz innerhalb des Textblocks; Blocksatz verteilt den Restplatz gleichmäßig auf die Wortzwischenräume der Zeile (ein Wort → linksbündig). Der Textblock steht als Ganzes mittig auf dem Etikett (wie bisher).
- Unterstreichung: Linie unter der Grundlinie (Abstand ≈ 10 % der Schriftgröße, Stärke ≈ 6 %, mind. 1 Punkt), über die Breite des Spans.
- **Automatisch** (`size_pt is None`): effektive Größe = (`span.size_pt` oder Referenz 12 pt) × Faktor f; f per Halbierung so groß wie möglich, sodass der Block passt; Obergrenze: Referenzgröße × f ≤ 1/5 der Bandbreite (wie bisher).
- **Fest**: Spans ohne Größe nutzen `size_pt` des Objekts; passt es nicht → `TextTooLarge` mit größter passender Grundgröße in pt („höchstens 14 pt“).
- Ränder, Ausrichtung horizontal/vertikal, Längengrenzen wie Etappe 1.
- Ersatzschriften: neue Funktion `font_warnings(doc) -> list[str]` liefert Hinweise „Schrift X nicht gefunden – ersetzt durch Y“ (je Familie einmal); `render_document` bleibt unverändert in der Signatur. Die GUI zeigt die Hinweise in der Statusleiste, die CLI auf stderr.

### CLI

- `print`: `-s/--font-size auto|4–100` (pt), `--align left|center|right|justify` (Standard center), `--font-family NAME`, `--bold/--no-bold` (Standard fett), `--italic`, `--underline`; `--font PFAD` bleibt.
- Neuer Befehl `labelwerk fonts`: listet installierte Schriftfamilien.

### Einstellungen

- Feld `font_size` → `font_size_pt` (`null` oder 4–100). Altes Feld `font_size` (Druckpunkte) wird beim Laden einmalig umgerechnet (`round(dots × 72 / 300)`, auf 4–100 begrenzt), mit Hinweis; beim nächsten Speichern steht nur noch `font_size_pt` in der Datei.
- Neu: `font_family` (Standard `"DejaVu Sans"`).

## 3b – GUI

### Text-Panel (Aufbau wie P-touch)

- **Inhalt:** `QTextEdit` (Rich Text) statt `QPlainTextEdit`; Einfügen aus der Zwischenablage nur als reiner Text.
- **Schrift:** `QFontComboBox` (Familie), Größenfeld in pt (editierbare Liste 6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72), Knöpfe **A⁺ / A⁻** (nächste Stufe der Liste, auf Markierung bzw. Schreibmarke).
- **Stil:** Umschaltknöpfe **B / I / U** (Strg+B/I/U), wirken auf Markierung bzw. Weitertippen, zeigen den Zustand an der Schreibmarke.
- **Textposition:** vier exklusive Knöpfe links / zentriert / rechts / Blocksatz; wirken auf die Absätze der Markierung.
- **Feste Rahmengröße:** Umschaltknopf (ersetzt „Automatisch“); an = automatische Größe.
- Fehlerhinweis (TextTooLarge) wie bisher im Panel.

### Übersetzung Editor → Kern

- `QTextDocument`-Blöcke → `Paragraph` (Ausrichtung aus dem Blockformat), Fragmente → `Span` (Familie, Punktgröße, fett = Gewicht ≥ Bold, kursiv, unterstrichen). Familie gleich Standard → `family=None`; Punktgröße gleich Grundgröße → `size_pt=None`.
- Umgekehrt `refresh()`: Dokument aus dem Modell aufbauen (für Start mit Einstellungen und später „Öffnen“).

## Tests

- **Kern:** gemeinsame Grundlinie bei gemischten Größen; links/rechts bündig (gleiche Tintenkante), Blocksatz füllt die Zeile; Unterstreichung unter der Grundlinie; Automatik erhält Größenverhältnisse; fett/kursiv lösen auf andere Dateien auf; unbekannte Familie → Ersatz + Hinweis; reiner Text pixelgleich zu vorher; `TextTooLarge` in pt.
- **CLI:** neue Optionen, `labelwerk fonts`; Einstellungen: Umrechnung `font_size` → `font_size_pt`, `font_family`.
- **GUI (offscreen):** Wort markieren + B → drei Spans, nur das mittlere fett; Ausrichtung landet im richtigen Absatz; A⁺/A⁻ nur auf Markierung; Feste Rahmengröße an/aus; Knopfzustand folgt Schreibmarke; Einfügen als reiner Text; Start mit Einstellungen (Familie, pt).
