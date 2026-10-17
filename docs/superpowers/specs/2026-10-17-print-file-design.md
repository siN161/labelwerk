# PDF/Bild direkt drucken – Design

Stand: 2026-10-17 · Status: abgestimmt · kommt **vor** dem GUI-MVP

## Ziel

Eine fertige Datei (PDF, PNG, JPG) 1:1 auf ein Etikett drucken, ohne Editor. Auslöser: Internetmarke der Deutschen Post (A4-PDF, Marke 90 × 47 mm zwischen vier Schnittmarken, DataMatrix-Code) auf 62-mm-Endlosband.

**1:1 ist Pflicht**, nicht Komfort: Frankier- und Barcodes müssen in Originalgröße bleiben. Verkleinern nur auf ausdrücklichen Wunsch (`--fit`).

## Nicht enthalten

SVG (kommt mit dem Werkzeug „Bild“), mehrere Seiten in einem Lauf, Vergrößern, GUI (bekommt später „Öffnen“ auf denselben Kern).

## Kern: `src/labelwerk/files.py` (neu, ohne Qt)

Alle Bilder intern bei **300 dpi** (Druckauflösung), Graustufen.

### `load_file(path, page=1) -> PIL.Image`

- **PDF** (Endung `.pdf`): Seite `page` mit `pypdfium2` bei 300 dpi rastern. Seite außerhalb des Bereichs → `ValueError` („PDF hat nur N Seiten“).
- **PNG/JPG** (`.png`, `.jpg`, `.jpeg`): mit PIL laden; Transparenz auf Weiß legen. Hat die Datei eine DPI-Angabe ≠ 300, auf 300 dpi umrechnen (Größe in mm bleibt gleich); ohne Angabe gilt 300 dpi.
- Andere Endung → `ValueError` („Dateityp nicht unterstützt: .xyz – möglich: PDF, PNG, JPG“).
- Datei fehlt → `FileNotFoundError` (CLI meldet verständlich).

### `crop(img) -> PIL.Image`

1. Bedruckten Bereich bestimmen (Pixel dunkler als Schwellwert). Leer → `ValueError` („Datei enthält keinen druckbaren Inhalt“).
2. **Schnittmarken erkennen:** In allen vier Ecken des bedruckten Bereichs je ein Kreuz aus einer waagrechten und einer senkrechten dünnen Linie (durchgezogen oder gepunktet). Gefunden in allen vier Ecken → auf das Rechteck zwischen den Kreuzungspunkten zuschneiden (Marken liegen damit außerhalb).
3. Sonst auf den bedruckten Bereich zuschneiden.
4. **Leerraum entfernen:** Nach dem Zuschnitt auf die Marken zusätzlich auf den bedruckten Inhalt dazwischen zuschneiden (Internetmarke: 89,9 × 46,8 → 69,9 × 33,8 mm; gedreht 72 statt 92 mm Band). Nichts zwischen den Marken → `ValueError`.

Erkennungsregel für ein Eckkreuz (Ecke des bedruckten Bereichs, Fenster 10 × 10 mm): Es gibt Zeilen, die **am Rand des bedruckten Bereichs beginnen** und auf den ersten 3 mm zu mindestens 40 % dunkel sind (waagrechte Linie, auch gepunktet), und ebenso Spalten (senkrechte Linie). Beide Gruppen sind höchstens 1 mm dick. Zugeschnitten wird an der Innenkante der Linien plus 1 Pixel, damit kein Kantenrest der Marke bleibt. Text oder Logos in Ecknähe gelten so nicht als Marke (beginnen nicht an beiden Rändern bzw. sind dicker als 1 mm). Geprüft am echten Beispiel: 89,9 × 46,8 mm.

### `fit_to_label(img, label_id, fit=False, model="QL-600", rotate="auto") -> PIL.Image`

Ergebnis hat genau das Format, das `build_instructions` erwartet (Breite = bedruckbare Breite des Etiketts; bei gestanzt auch exakte Höhe).

- **Drehen (`rotate="auto"`, Standard) nur wenn nötig:** Passt das Motiv ungedreht, bleibt es so. Passt es nur gedreht, wird es um 90° gegen den Uhrzeigersinn gedreht (`Image.rotate(90, expand=True)`).
- **Feste Drehung** (`rotate` = 0, 90, 180, 270 – Grad im Uhrzeigersinn, CLI `--rotate`): genau so drehen, nie zusätzlich. Passt es nicht → Fehler bzw. mit `fit` Verkleinern in dieser Lage. Beispiel Internetmarke quer wie im PDF: `--rotate 0 --fit` (≈ 82 %). Andere Werte → `ValueError`.
- **Endlosband:** Motiv waagrecht mittig auf volle Druckbreite; Länge = Motivhöhe + 2 × Rand (Rand wie `render.MARGIN`), mindestens die Modellgrenze (QL-600: 150 Punkte = 12,7 mm), höchstens 11811 Punkte (1000 mm).
- **Gestanzt / rund:** Motiv muss in den bedruckbaren Bereich passen (ggf. gedreht); mittig setzen.
- **Zu groß:** Ohne `fit` → `ValueError` mit Maßen in mm, z. B. „Motiv ist 120,0 × 70,0 mm, Etikett '62' ist höchstens 58,9 mm breit – mit --fit verkleinern (Codes evtl. nicht mehr lesbar)“. Mit `fit` → proportional (Lanczos) auf die größte passende Größe verkleinern; bei `auto` in der Lage (gedreht/ungedreht), die größer bleibt.

Die Schwarz/Weiß-Umwandlung bleibt in `build_instructions` (Schwellwert, kein Dithering).

## CLI: `labelwerk print-file`

```
labelwerk print-file DATEI [-l 62] [--page N] [--rotate auto|0|90|180|270] [--fit] [--preview out.png]
                           [-p auto|…] [-b linux_kernel|pyusb|network] [--no-cut]
```

- Ablauf: `load_file` → `crop` → `fit_to_label` → Vorschau speichern oder drucken.
- Druckerwahl, `auto`-Erkennung und `PrintError`-Behandlung wie bei `print` – gemeinsamer Code, nicht kopiert (Parser-Optionen und Druckteil in Hilfsfunktionen auslagern).
- `--preview` gibt zusätzlich die Etikettgröße in mm aus, z. B. „Vorschau: out.png (58,9 × 91,0 mm)“.
- Fehler (`ValueError`, `FileNotFoundError`) → Meldung auf stderr, Exit-Code 2.

## Abhängigkeiten

`pypdfium2>=4` als feste Abhängigkeit (Apache-2.0/BSD-3, GPL-kompatibel; Wheels ohne Systembibliotheken).

## Tests

Nur künstliche Testdateien, **keine echten Briefmarken oder Adressen** im Repo.

- `load_file`: von PIL erzeugtes PDF (`img.save(..., "PDF", resolution=300)`) hat nach dem Laden dieselbe Größe in Punkten; PNG mit 600 dpi wird auf halbe Pixelgröße umgerechnet; PNG mit Transparenz wird weiß; `--page` außerhalb → Fehler; `.txt` → Fehler.
- `crop`: Bild mit vier gezeichneten Eckkreuzen (durchgezogen und gepunktet) → nur der Inhalt zwischen den Marken (ohne Marken und Leerraum); ohne Marken → Inhaltsbereich; Text nahe einer Ecke wird nicht als Marke erkannt; leeres Bild → Fehler.
- `fit_to_label`: Drehrichtung auto (gegen Uhrzeigersinn), `rotate=90/180` (im Uhrzeigersinn), `rotate=0` zu breit → Fehler, `rotate=0` + `fit` bleibt quer; ungültige Drehung → Fehler; 90 × 47 mm auf `62` → gedreht, Breite 696, Länge 1063 + 2 × Rand; 40 × 20 mm auf `62` → nicht gedreht; sehr kurzes Motiv → Mindestlänge 150; zu großes Motiv → Fehler mit mm-Angaben; mit `fit` → passt, Seitenverhältnis erhalten; gestanzt `62x29` → exakte Größe 696 × 271.
- CLI: `print-file` mit `--preview` schreibt PNG und nennt mm-Größe; Druck mit ersetztem `print_image` übergibt ein Bild mit Breite 696; unbekannter Dateityp → Exit 2.
- **Manuell:** echte Internetmarke auf DK-22205 drucken, Code mit Handy-Scanner prüfen.
