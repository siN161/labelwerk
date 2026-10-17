# Papier komplett + Einstellungen – Design (Etappe 1)

Stand: 2026-10-17 · Status: abgestimmt

## Ziel

Das Papier-Panel bekommt die Funktionen des P-touch Editors: **Ausrichtung** (Horizontal/Vertikal), **Ränder** und **Medium prüfen**. Dazu kommen **Einstellungen** (Standardwerte, gemeinsam für GUI und CLI) und eine **Live-Druckererkennung** in der GUI.

Leitlinien: labelwerk ist für alle Nutzer gedacht, viele Einstellungen sind ausdrücklich erwünscht (individuell anpassbar). Hauptanwendung des Projektinhabers: Versandetiketten (Adresse längs auf 62-mm-Band → Ausrichtung Horizontal).

## Etappen (Kontext)

1. **Diese Spec:** Papier komplett, Einstellungen, Live-Erkennung.
2. Verwendungsart (P-touch-Vorlagen wie Kabelfahne/-wickel) – eigene Spec; vorher die Arten im P-touch Editor für QL recherchieren.
3. Funktionsliste „P-touch → labelwerk“ (Text-Formatierung, Rahmen, Bild, Favoriten, Layout/freies Platzieren, Speichern) mit Prioritäten – eigene Specs.

## Nicht in dieser Etappe

Verwendungsart, Schriftart/-stil, mehrere Objekte, Speichern/Laden von Etiketten, Auswahl anderer Druckermodelle, `-l auto` in der CLI.

## Begriffe (wie P-touch)

- **Vertikal** (heutiges Verhalten): Band läuft im Bild von oben nach unten, Text steht quer zum Band.
- **Horizontal:** Band läuft von links nach rechts, Text steht **längs** zum Band (z. B. Adresse auf 62-mm-Band, Etikett ~90 mm lang). Bei gestanzten/runden Etiketten wird das Etikett um 90° gedreht gestaltet.

## Kern

### `document.py`

```python
@dataclass
class Document:
    label_id: str = "62"
    length_mm: float | None = None
    orientation: str = "vertical"   # "vertical" | "horizontal"
    margin_mm: float = 1.0          # Rand in Bandlaufrichtung (vorne/hinten)
    objects: list[TextObject] = field(default_factory=list)
```

Ungültige `orientation` → `ValueError` beim Rendern. `margin_mm` wird beim Rendern auf 0–20 mm begrenzt.

### `render.py` – `render_document(doc, model)`

- Gerendert wird in **Leserichtung**, danach für den Drucker gedreht. Rückgabe bleibt das fertige **Druckbild** (Breite = bedruckbare Bandbreite) – Vorschau = Druck.
- **Quer zum Band** gilt wie bisher ein fester Sicherheitsabstand von 1 mm (`MARGIN`); den Rest bestimmt der Drucker. **In Bandlaufrichtung** gilt `margin_mm`.
- **Vertikal:** wie heute; Höhe (Bandlauf) = automatisch (Text + 2 × `margin_mm`) oder `length_mm`; Breite = Bandbreite.
- **Horizontal:**
  - Leserichtungs-Bild: Höhe = bedruckbare Bandbreite, Breite = Länge (automatisch: Textbreite + 2 × `margin_mm`; fest: `length_mm`).
  - Automatische Schriftgröße: größte Größe, bei der der Textblock in die Bandbreite (minus 2 × 1 mm) passt – und bei fester Länge zusätzlich in die Länge.
  - Gestanzt/rund: Leserichtungs-Bild = bedruckbarer Bereich um 90° gedreht (z. B. 62x29: 271 × 696 Punkte).
  - Drehung zum Druckbild: `Image.rotate(90, expand=True)` (wie `files.fit_to_label` bei automatischer Drehung).
- Längengrenzen wie bisher (`length_limits`, QL-600: 150–11811 Punkte), gelten für die Bandlaufrichtung in beiden Ausrichtungen.
- `TextTooLarge` wie bisher, wenn eine feste Schriftgröße nicht passt.

### `settings.py` (neu)

- Datei: `$XDG_CONFIG_HOME/labelwerk/settings.json` (Standard `~/.config/labelwerk/settings.json`).
- `@dataclass Settings` mit Standardwerten = heutiges Verhalten:

| Feld | Standard | Bedeutung |
|---|---|---|
| `label_id` | `"62"` | Etikett für neue Etiketten, CLI ohne `-l` |
| `orientation` | `"vertical"` | Ausrichtung für neue Etiketten, CLI ohne `--orientation` |
| `margin_mm` | `1.0` | Ränder für neue Etiketten, CLI |
| `check_media_on_start` | `true` | GUI: Medium beim Start / beim Erscheinen des Druckers prüfen |
| `start_zoom` | `200` | GUI-Startzoom in % (25–400) |

- `load_settings(path=None) -> Settings`: fehlende Datei → Standardwerte; unbekannte Schlüssel werden ignoriert; ungültige Werte (falscher Typ, außerhalb des Bereichs, unbekanntes Etikett) → Standardwert für dieses Feld; kaputtes JSON → alle Standardwerte. Probleme werden als Liste von Hinweisen zurückgegeben (`Settings.warnings`), nie als Ausnahme.
- `save_settings(settings, path=None)`: schreibt JSON (UTF-8, eingerückt), legt Ordner an. Schreibfehler → `OSError` mit verständlicher Meldung (GUI zeigt sie an).
- `new_document(settings) -> Document`: neues Dokument mit Standardwerten und einem leeren `TextObject`.

### `media.py` (neu) – Medium prüfen

- `read_media(printer: str, backend="linux_kernel") -> Media`: öffnet den Drucker über `brother_ql.backends.helpers.get_printer`, sendet die Statusabfrage (`get_status`, Befehl `ESC i S` – **druckt nichts**) und liefert `Media(width_mm: int, length_mm: int, kind: str)`; `kind` ∈ `"endless"`, `"die_cut"`, `"none"`.
- `label_for_media(media, model) -> str | None`: passende Etikett-ID aus `labels_for_model(model)` (Endlos: Breite; gestanzt/rund: Breite × Länge; rund erkennt man an gleicher Breite und Länge und Formfaktor rund). Keine Rolle oder unbekannt → `None`.
- Fehler (kein Zugriff, keine Antwort, Drucker meldet Fehler) → `MediaError` (Unterklasse von `ValueError`) mit deutscher Meldung. Keine Rolle → `Media(kind="none")`.
- Tests mit nachgebauten 32-Byte-Statusantworten (über `brother_ql.reader.interpret_response`-kompatible Bytes) und einem Fake-Printer-Objekt; keine Hardware.

### CLI

- `print` / `print-file`: Standard für `-l` aus den Einstellungen (statt fest `62`).
- `print`: neue Optionen `--orientation horizontal|vertical` und `--margin MM` (Standard aus Einstellungen).
- Neuer Befehl `labelwerk media`: zeigt die eingelegte Rolle (z. B. „Eingelegt: 62 mm endlos (Etikett 62)“), Drucker automatisch wie bei `print`; Fehler → stderr, Exit 2.
- Hinweise aus `Settings.warnings` werden auf stderr ausgegeben, brechen aber nichts ab.

## GUI

### Papier-Panel

Reihenfolge wie P-touch:
1. **Etikett** (wie heute) + Knopf **„MEDIUM PRÜFEN“** + Statuszeile („Eingelegt: 62 mm endlos ✓“ / orange „Eingelegt ist 62 mm endlos – Auswahl passt nicht“ / „Kein Drucker“ …).
2. **Länge** (wie heute, nur Endlos).
3. **Ränder** (mm, 0–20, Schritt 0,5).
4. **Ausrichtung**: zwei Optionsknöpfe Horizontal / Vertikal.

Die Passt-nicht-Warnung erscheint, sobald ein Medium bekannt ist und die Auswahl abweicht; sie verschwindet, wenn die Auswahl passt oder der Drucker getrennt wird.

### Medium prüfen im Hintergrund

- `MediaWorker` (QRunnable) ruft `find_brother_lp` und `read_media`; Signale `found(media, label_id | None)` / `failed(str)`.
- Läuft nie gleichzeitig mit einem Druck (Knopf und Automatik gesperrt, solange gedruckt wird) und nie doppelt.
- Gefundenes passendes Etikett wird im Dokument gesetzt (Panel + Vorschau aktualisieren); unbekannte Rolle → Hinweis, Auswahl bleibt.

### Live-Druckererkennung

- `QTimer` alle 2 s → `refresh_printer()` (nur `/sys`-Zugriff, kein USB). Statusleiste aktualisiert sich bei Ein-/Ausschalten, Belegt (VM) und Trennen.
- Wechselt der Zustand von „kein/belegt“ zu „Drucker da“ und ist `check_media_on_start` an, startet „Medium prüfen“ automatisch (ebenso einmal beim Programmstart, wenn der Drucker schon da ist).

### Arbeitsfläche

- **Horizontal:** Die Ansicht zeigt das Etikett in Leserichtung (Szene unverändert in Druckkoordinaten, Ansicht um −90° gedreht). Lineale zeigen die Achsen in Leserichtung (waagrecht = Bandlaufrichtung). Größenangabe über dem Etikett in Leserichtung, z. B. „92,0 × 62 mm“.
- Längen-Anfasser sitzt bei Horizontal am **rechten** Ende und wird waagrecht gezogen (gleiche Logik, gedrehte Ansicht).

### Einstellungen

- Zahnrad-Knopf **„EINSTELLUNGEN“** rechts in der Werkzeugleiste → Dialog mit Abschnitten:
  - **Neues Etikett:** Etikett, Ausrichtung, Ränder.
  - **Drucker:** Medium beim Start prüfen.
  - **Ansicht:** Startzoom.
- „Speichern“ schreibt `settings.json`. Die Standardwerte greifen, wenn ein neues Etikett entsteht – in dieser Etappe beim **Start der GUI** (`new_document(settings)`), künftig auch bei „Neu“ (kommt mit Speichern/Laden in Etappe 3). Das gerade geöffnete Etikett bleibt unverändert; der Startzoom gilt ab dem nächsten Start. Schreibfehler → Meldung im Dialog.
- Beim Start: Hinweise aus `Settings.warnings` in der Statusleiste.
- Der Dialog ist so gebaut, dass weitere Einstellungen als neues Feld + neue Zeile im passenden Abschnitt dazukommen.

## Tests

- **Kern:** Rendern horizontal (Endlos automatisch/fest, gestanzt gedreht, Druckbild-Breite = Bandbreite, Drehrichtung über Markierungspixel), Ränder in beiden Ausrichtungen, Ränder-Grenzen; Settings laden/speichern/Standardwerte/kaputte Datei/ungültige Felder; `new_document`; `media.read_media` mit Fake-Drucker (62 endlos, 62x29, keine Rolle, Fehlerbit) und `label_for_media`.
- **CLI:** Standard-Etikett und -Ausrichtung aus Settings (über `XDG_CONFIG_HOME` in `tmp_path`), `--orientation`, `--margin`, `labelwerk media` mit gepatchtem `read_media`.
- **GUI (offscreen):** Ausrichtung umschalten ändert Vorschau und Anfasser-Position; Ränder ändern Vorschau; „Medium prüfen“ mit gepatchtem `read_media` wählt Etikett / zeigt Warnung / Fehler; kein Prüfen während Druck; Live-Erkennung: gepatchte Erkennung wechselt von None zu Drucker → Statusleiste aktualisiert und Prüfung läuft automatisch (Timer im Test direkt auslösen); Einstellungsdialog speichert in `tmp_path` und neues Dokument nutzt die Werte.
- **Kein Test spricht Hardware an.** Zusätzlich manuell (mit Zustimmung des Nutzers): `labelwerk media` am echten QL-600 – nur Statusabfrage, kein Druck.
