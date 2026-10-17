# GUI-MVP – Design

Stand: 2026-10-17 · Status: abgestimmt

## Ziel

Desktop-GUI (PySide6) für labelwerk nach dem Vorbild des **P-touch Editors (Express-Modus)**: Werkzeugleiste oben, kontextabhängiges Eigenschaften-Panel links, Arbeitsfläche mit mm-Linealen, Statusleiste mit Drucker und Zoom.

Langfristig wird labelwerk ein **frei platzierbarer Editor** (mehrere Objekte – Text, Rahmen, Barcode, Bild – mit der Maus verschiebbar). Das MVP enthält davon nur **ein Textobjekt**, legt aber Struktur und Datenmodell so an, dass weitere Objekte und Werkzeuge ohne Umbau dazukommen.

## Nicht im MVP

Verschieben von Objekten mit der Maus (die Etikettlänge ist per Maus ziehbar, siehe unten), Auswahl-Anfasser, mehrere Objekte, Rahmen/Barcode/Bild, Drehen, Speichern/Laden, Modell-/Druckerauswahl (fest QL-600, automatisch erkannt).

## Architektur: Kern rendert, GUI zeigt an

Es gibt genau **einen Renderer** (PIL, im Kern). Die Vorschau zeigt dasselbe Bild, das gedruckt wird → Vorschau = Druck. Der Kern bleibt Qt-frei; CLI, spätere Web-UI und Tests nutzen ihn direkt. Qt-natives Zeichnen wurde verworfen (zweiter Renderer, abweichende Schriftmetriken, Drucklogik in der UI).

### Kern: `src/labelwerk/document.py` (neu)

```python
@dataclass
class TextObject:
    text: str = ""
    font_size: int | None = None      # None = automatisch
    font_path: str | None = None

@dataclass
class Document:
    label_id: str = "62"
    length_mm: float | None = None    # nur Endlosband; None = automatisch
    objects: list[TextObject] = field(default_factory=list)
```

Später kommen Position (`x_mm`, `y_mm`), Drehung, Ausrichtung und weitere Objekttypen hinzu.

### Kern: `render.py`

- `render_document(doc) -> PIL.Image` ist der eigentliche Renderer. Im MVP wird das erste (einzige) `TextObject` wie bisher zentriert und ggf. automatisch verkleinert.
- `render_text(text, label_id, font_size, font_path)` bleibt als dünne Hülle (`Document` mit einem `TextObject`) – CLI und bestehende Tests bleiben unverändert.
- **Feste Länge** (`length_mm`, nur Endlosband): Bildhöhe = Länge in Punkten (300 dpi), Text vertikal zentriert. Bei automatischer Schriftgröße schrumpft der Text auch auf die Länge; ist er bei fester Schriftgröße höher als die Länge, wird `TextTooLarge` geworfen.
- **Längengrenzen** (Endlos): Das Modell erlaubt 12,7–1000 mm (`min_max_length_dots` aus `brother_ql.models`, QL-600: 150–11811 Punkte). Eine automatische Länge wird auf das Minimum angehoben; eine feste Länge außerhalb der Grenzen wird auf die Grenze gesetzt.
- `length_mm` bei gestanztem oder rundem Etikett wird ignoriert (Größe ist durch das Etikett vorgegeben); die GUI bietet das Feld dann gar nicht an (siehe Papier-Panel).
- Leeres Dokument / leerer Text: weißes Etikett (Endlos: Mindestlänge 12,7 mm wie jede automatische Länge). `Document.is_empty()` meldet, ob kein Objekt sichtbaren Inhalt hat (Text nur aus Leerzeichen zählt als leer) – Grundlage für die Warnung vor dem Druck.

### Kern: `labels.py`

`Label` wird um die Angaben für die Darstellung erweitert (Daten aus `brother_ql`):

- `shape`: `"endless"`, `"die_cut"` oder `"round"`
- `total_width`, `total_height`: physische Größe in Punkten (`dots_total`; bei Endlos `total_height = None`)

Der bedruckbare Bereich (`width`/`height`, wie bisher) liegt mittig im physischen Etikett.

## GUI: Paket `src/labelwerk/gui/`

| Datei | Aufgabe |
|---|---|
| `app.py` | `main()` für Einstiegspunkt `labelwerk-gui`; `QApplication`, Theme laden, Hauptfenster |
| `main_window.py` | Hält das `Document`; setzt Werkzeugleiste, Panel-Stapel (`QStackedWidget`), Arbeitsfläche, Statusleiste zusammen; gedrosseltes Neu-Rendern |
| `tools.py` | Werkzeug-Registry: Liste von `Tool(name, icon, panel_factory)`. Werkzeugleiste und Panel-Stapel werden daraus erzeugt. Neues Feature = neuer Eintrag. |
| `panels/paper.py` | Etikett-Auswahl (aus `labels_for_model("QL-600")`, Standard `62`), gruppiert nach Endlos / gestanzt / rund. Endlos: Länge „automatisch“ oder fester mm-Wert. Gestanzt/rund: statt des Längenfelds eine feste Angabe, z. B. „62 × 29 mm · gestanzt“ bzw. „Ø 24 mm · rund“ |
| `panels/text.py` | Mehrzeiliges Textfeld; Schriftgröße „automatisch“ oder fester Wert; Hinweisfeld für Fehler (z. B. „höchstens 30“ aus `TextTooLarge.max_size`) |
| `canvas.py` | `QGraphicsView` mit mm-Linealen oben/links und Zoom (100 % = reale Größe über `logicalDpi`). Zeichnet das **physische Etikett** passend zur Form (siehe „Darstellung der Etiketten“), darin das Vorschaubild im bedruckbaren Bereich |
| `print_worker.py` | `QRunnable` im `QThreadPool`; Signale `done(status: dict)`, `failed(meldung: str)` |
| `theme/rawblock.qss` | Optik, als Paketdaten ausgeliefert |

Panels bekommen das `Document`, ändern ihren Teil und senden `changed`.

### Datenfluss

1. Panel ändert `Document` → `changed`.
2. Hauptfenster startet einen Single-Shot-`QTimer` (~150 ms); bei Ablauf `render_document(doc)`.
3. Erfolg: Arbeitsfläche zeigt das Bild (PIL → `QImage` → `QPixmap`), Hinweise im Panel werden gelöscht.
4. `ValueError` (inkl. `TextTooLarge`): Meldung im Text-Panel (im MVP die einzige Fehlerquelle, da Etiketten nur aus der Liste wählbar sind); die Vorschau behält den letzten gültigen Stand.

### Darstellung der Etiketten

Wie im P-touch Editor sieht man das Etikett in echter Größe und Form auf einer grauen Fläche:

- **Gestanzt:** weißes Rechteck in physischer Größe (`total_width` × `total_height`) mit leicht abgerundeten Ecken (wie die DK-Etiketten), darin der bedruckbare Bereich als gepunktete Linie.
- **Rund:** weißer Kreis in physischer Größe, bedruckbarer Bereich gepunktet.
- **Endlos:** weißer Streifen in Bandbreite (`total_width`) und aktueller Länge; Schnittkanten oben und unten als gestrichelte Linie.
- **Länge per Ziehen (nur Endlos):** Die untere Schnittkante hat einen Anfasser. Ziehen mit der Maus setzt `length_mm` (Raster 0,5 mm, innerhalb der Längengrenzen); während des Ziehens zeigt eine Beschriftung die aktuelle Länge. Das Längenfeld im Papier-Panel springt dabei auf „fest“ und zeigt denselben Wert – beide Wege bearbeiten dasselbe Feld im `Document`. Doppelklick auf den Anfasser stellt wieder auf „automatisch“.
- Über dem Etikett eine Größenangabe (z. B. „62 × 29 mm“), wie „62mm“ im P-touch Editor.

Die abgerundeten Ecken zeigen das Etikett, nicht die Bedienelemente – das Theme bleibt eckig.

### Drucken

1. Ist `Document.is_empty()`, fragt ein Dialog „Das Etikett ist leer. Trotzdem drucken?“ (Standardknopf: Abbrechen). Abbrechen → nichts passiert.
2. Knopf „Drucken“ sperrt sich.
3. Worker: `find_brother_lp()`; kein Drucker → `failed` mit `detect.PRINTER_NOT_FOUND` bzw. `detect.BUSY_MESSAGE` (ohne CLI-Hinweis `-p …`). Sonst `print_image(...)` mit dem zuletzt gerenderten Bild.
4. `PrintError` → `failed(str(e))`; Erfolg → `done(status)`.
5. Statusleiste zeigt Ergebnis bzw. Fehler; Knopf wird wieder freigegeben.

Druckererkennung läuft beim Start (Anzeige „QL-600 · lp1“ bzw. „kein Drucker“ in der Statusleiste) und erneut vor jedem Druck.

## Optik

RawBlock (`docs/design/rawblock-DESIGN.md`) dient als **Inspiration, nicht als Regelwerk**: Schwarz/Weiß, kräftige Rahmen, keine Rundungen, Großbuchstaben bei Schaltflächen und Abschnittstiteln, Farben nur für Status (Grün/Orange/Rot). Abweichungen sind erlaubt, z. B. Icons in der Werkzeugleiste. Alle Optik steckt in `theme/rawblock.qss`; ohne Theme läuft die GUI im System-Look. Schriften: Systemschriften mit Fallback, keine mitgelieferten Fonts im MVP.

## Abhängigkeiten

- `pyproject.toml`: Extra `gui = ["PySide6>=6.6"]`; `dev` ergänzt um `pytest-qt>=4` **und** `PySide6>=6.6` (pytest-qt braucht eine Qt-Bindung, sonst stört es die ganze Suite); Skript `labelwerk-gui = "labelwerk.gui.app:main"`.
- PySide6 ist LGPL und damit GPL-kompatibel.

## Tests

- **Kern (ohne Qt):** `render_document` liefert für ein Text-Dokument dasselbe Bild wie `render_text`; feste Länge setzt die Bildhöhe; zu hoher Text bei fester Länge und fester Schriftgröße wirft `TextTooLarge`; `length_mm` bei gestanztem Etikett wird ignoriert; Längengrenzen (zu kurzer automatischer Text → 150 Punkte, feste Länge 2000 mm → 11811 Punkte); `Document.is_empty()` für kein Objekt / leeren Text / nur Leerzeichen / echten Text; `Label.shape` und physische Größe für `62`, `62x29`, `d24`.
- **GUI (`pytest-qt`, `QT_QPA_PLATFORM=offscreen`):**
  - Registry erzeugt je Werkzeug eine Schaltfläche und ein Panel.
  - Tippen im Text-Panel aktualisiert die Vorschau.
  - Etikett-Wechsel ändert die Vorschaugröße.
  - Zu große feste Schriftgröße zeigt Hinweis im Panel.
  - Papier-Panel: Längenfeld nur bei Endlosband, bei `62x29` stattdessen „62 × 29 mm · gestanzt“.
  - Arbeitsfläche: Etikettumriss hat die physische Größe (z. B. `62x29` → 732 × 341 Punkte) bzw. ist bei `d24` ein Kreis.
  - Länge ziehen: Anfasser um eine Strecke verschieben setzt `length_mm` (gerastert) und das Panel zeigt „fest“ mit diesem Wert; Ziehen unter 12,7 mm bleibt bei 12,7 mm; Doppelklick setzt auf automatisch.
  - Leeres Etikett: Drucken fragt nach; Abbrechen ruft `print_image` nicht auf.
  - Drucken mit ersetztem `print_image`: Erfolg in der Statusleiste, Knopf wieder frei; `PrintError` erscheint als Meldung.
- GUI-Tests nutzen `pytest.importorskip("PySide6")`, damit reine CLI-Umgebungen grün bleiben.
- Kein Test spricht echte Hardware an (`find_brother_lp` und `print_image` per `monkeypatch`).
- **CI:** `pip install -e ".[dev,gui]"`, `QT_QPA_PLATFORM=offscreen`, Systempakete `libegl1 libxkbcommon0` zusätzlich zu `fonts-dejavu-core`.
- **Manuell:** abschließend ein echter Druck aus der GUI auf dem QL-600 (DK-22205, `62`).
