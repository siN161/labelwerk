# Paketmarken-Typen (`catalog.json`)

Welche Bereiche einer Paketmarke (DHL, Hermes …) auf das Etikett kommen und wohin, steht hier als Daten –
labelwerk (`parcel.py`) liest nur diese Datei. Neue Länder, Dienste und Typen brauchen keinen Code.

## Herkunft

Die Bereiche (`src`) sind gemessene Tatsachen über die Marken; die Anordnung (`dst`) ist nach dem Vorbild
von paketikett.de nachgemessen. Ermittelt wurden beide mit Testblättern
(`tools/parcel/make_sheets.py`: 10-mm-Raster, in jeder Zelle ein QR-Code mit ihrer Lage), die ein
Umwandlungsdienst (paketikett.de) wie eine Marke verarbeitet hat; `tools/parcel/analyze.py` und
`extract.py` lesen aus dem Ergebnis ab, welcher Bereich mit welcher Drehung und welchem Maßstab wohin
kam. Es wurde kein Code des Dienstes übernommen. `verified: true` heißt: an einer echten Marke
nachgeprüft (Original und Ergebnis); alle anderen Typen sind „ungeprüft“ – labelwerk rückt ihre Kanten
an der echten Marke bis zum nächsten weißen Rand (höchstens 3 mm).

## Format

```json
{"version": 1,
 "countries": {"DE": {"names": {"de": "Deutschland", "en": "Germany"},
                      "carriers": {"dhl": {"de": "DHL", "en": "DHL"}}}},
 "types": [{
   "id": "dhl-privat-1", "country": "DE", "carrier": "dhl",
   "names": {"de": "…", "en": "…"}, "verified": true,
   "source": {"sizes_mm": [[210, 297]], "raster": {"dpi": 300, "x_mm": 0, "y_mm": 0, "px": [1800, 1200]}},
   "detect": {"all": ["DHL"], "any": ["Online Frankierung"], "none": ["Warenpost"]},
   "layouts": {"62": [{"size_mm": [180, 62], "pieces": [
       {"page": 1, "src": [x0, y0, x1, y1], "rotation": 90, "dst": [x0, y0, x1, y1], "kind": "barcode"}]}]}
 }]}
```

- **source**: mögliche Seitengrößen der Marke in mm (± 4 mm, auch quer); `raster` nur für Marken, die als
  Bild kommen (z. B. GIF): in dieser Auflösung (`dpi`) an diese Stelle der Seite gelegt (`x_mm`, `y_mm`); `px`
  ist die erwartete Pixelgröße (Breite, Höhe) – nur Bilder mit diesem Seitenverhältnis gelten als dieser Typ.
- **detect**: Begriffe im Text der PDF – `all` müssen vorkommen, `any` zählen dafür, `none` dagegen.
- **layouts**: `"62"` = Referenz 62 mm endlos (Seite quer: x längs des Bands, y quer), `"100x150"` =
  Etikett 100 × 150 mm (hochkant). Je Layout ein oder mehrere Ausgabe-Etiketten (Retoure: zwei).
- **pieces** (Malreihenfolge = Reihenfolge, spätere liegen oben): `src` Rechteck auf der Marke in mm (Ursprung
  oben links), `rotation` Drehung im Uhrzeigersinn, `dst` Rechteck nach dem Drehen auf dem Ausgabe-Etikett in
  mm (das Stück wird genau darauf skaliert), `kind` `barcode` (nicht verkleinert gemeint) oder `text`.

labelwerk skaliert das Layout auf die bedruckbare Breite des Etiketts (breiteres Band → größer) bzw. passt es in
ein festes Etikett ein; Barcodes unter 97 % ergeben einen Hinweis.

## Neuen Typ beisteuern

Arbeitsordner außerhalb des Repositorys, z. B. `export LABELWERK_PARCEL_DIR=~/paketmarken-pflege`:

1. Testblätter erzeugen: `QT_QPA_PLATFORM=offscreen python tools/parcel/make_sheets.py`.
2. Das passende Blatt beim Dienst als Marke dieses Typs umwandeln, Ergebnis in den Arbeitsordner legen.
3. In `tools/parcel/extract.py` den Typ in `TYPES` eintragen, dann `python tools/parcel/extract.py TYPID` und
   `python tools/parcel/assemble.py` (braucht numpy, scipy, zxing-cpp – nur zum Pflegen, nicht für labelwerk).
4. `python tools/parcel/catalog.py "$LABELWERK_PARCEL_DIR/templates.json" src/labelwerk/parcel_data/catalog.json`
   (Erkennungsbegriffe dort ergänzen), Vergleichsbilder in `check/` ansehen, Tests laufen lassen.

## Eigene Typen

In labelwerk angelegte Typen liegen als `$XDG_DATA_HOME/labelwerk/paketmarken/<id>.json` – nur Bereiche, die
Anordnung macht labelwerk selbst (Spalten längs des Bands, Barcodes 1:1, Texte höchstens auf Bandbreite verkleinert):

```json
{"version": 1, "id": "meine-marke", "names": {"de": "Meine Marke"},
 "source": {"sizes_mm": [[210, 297]]}, "detect": {"all": ["Meine Firma"]},
 "pieces": [{"page": 1, "src": [10, 10, 110, 60], "rotation": 0, "kind": "text"}]}
```

Geprüft beim Lesen: Kennung (Kleinbuchstaben, Ziffern, Bindestrich; keine mitgelieferte), Namen, Seitengrößen
(5–2000 mm), Begriffe, 1–30 Bereiche mit Kanten ≥ 1 mm innerhalb der Seite, Drehung 0/90/180/270, Art
`barcode`/`text`. Kaputte Dateien werden übergangen (Hinweis).

Echte Marken enthalten Namen und Adressen – sie gehören nie ins Repository.
