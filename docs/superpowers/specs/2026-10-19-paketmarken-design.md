# Paketmarken umwandeln – Design

Stand: 2026-10-19 · Status: Antworten des Nutzers 1a, 2a (+ breitere Bänder größer), 3b, 4b, 5a, 6a, 7b, 8a (Gerüst
für Länder, nachpflegbar); Spec danach ohne eigene Freigabe geschrieben – zur Prüfung mit der Abnahme.

## Ziel

Paketmarken aus dem Internet (DHL, Hermes …), die als A4/A5/100×150-PDF kommen, auf dem Etikettendrucker drucken:
Land wählen → passende Markentypen → Marke öffnen (Typ wird erkannt) → Vorschau → drucken. Wie paketikett.de: die
Marke wird in Stücke geschnitten und neu angeordnet, **Barcodes bleiben in Originalgröße**, Adressen und Infotexte
werden kleiner. Eigene Typen lassen sich auf einer Marke aufziehen.

## Grundlage (Analyse 2026-10-19)

Testblätter mit QR-Raster (je Zelle ein Code „Blatt x y“) bei paketikett.de umgewandelt (19 Typen + 2 Varianten),
ausgewertet: **feste Bereiche je Typ** (Blatt mit wenigen Codes ergibt dieselben), 3–7 Stücke, Drehung 0/90/270°,
Maßstab 0,58–1,1, Barcode-Stücke 1,0; Ausgabe 300 dpi, 60–62 mm hoch, 145–284 mm lang (Typ 1a: 100 × 150 mm);
Amazon/Hermes-Retoure zwei Etiketten. Gegenprobe am echten DHL-Original des Nutzers: Lage/Drehung/Maßstab stimmen,
Kanten der Testblatt-Auswertung ±1–3 mm (→ Antwort 6a). Die Bereiche sind Tatsachen über das Layout der Marken;
von paketikett wird kein Code übernommen. Originale des Nutzers kommen nicht ins Repo.

## Entscheidungen (Antworten)

1. **a – alle Typen zum Start** (DHL Privat 1/1a/2/3/4/4a/4b, Business 1–5, Retour 1–4, Hermes 1–3); ohne
   geprüftes Original „ungeprüft“ (wie Druckermodelle).
2. **a – Anordnung wie paketikett** auf 62 mm endlos, Barcodes 100 %; **auf breiteren Bändern/Etiketten größer**
   (Layout auf die bedruckbare Breite skaliert).
3. **b – Ausgabe je Drucker:** 62 mm endlos (Brother) bzw. 100 × 150 mm (4×6-Etiketten, Zebra/CUPS); allgemein das
   Etikett des gewählten Druckers.
4. **b – Reiter PAKETMARKE** in der GUI **und** CLI `labelwerk parcel`.
5. **a – Typ automatisch erkennen** (Text, Seitengröße), von Hand änderbar.
6. **a – Kanten an die echte Marke anpassen:** Bereiche rücken nach außen bis zum nächsten weißen Rand.
7. **b – eigene Typen gleich mit:** Bereiche auf einer Marke aufziehen, als eigenen Typ speichern.
8. **a – Deutschland zuerst, Gerüst für Länder:** Länder/Dienste/Typen sind Daten (JSON), nachpflegbar ohne Code.

## Nicht enthalten

Marken kaufen/abrufen (kein Konto, kein Netz), andere Länder mit Daten (nur das Gerüst), DPD/GLS/UPS (ohne
Beispiele), Briefmarken/Internetmarke (geht schon über `print-file`), Texterkennung (OCR).

## 1 – Daten: Markentypen (`src/labelwerk/parcel_data/`)

- **Katalog** `catalog.json`: Länder (`DE` mit Namen {de, en}) → Dienste (`dhl`, `hermes`, Namen) → Typen. Ein Typ:
  `id` („dhl-privat-1“), `names` {de, en}, `country`, `carrier`, `source` (Seitengröße in mm, z. B. 210 × 297, mit
  Toleranz; Seiten des PDFs), `detect` (Textmuster, Seitengröße, Gewicht), `verified` (bool), `layouts`.
- **Layout** je Ausgabe-Format (`"62"` = Referenz 62 mm endlos, `"100x150"` falls vorhanden): Liste von Etiketten
  (Retoure: zwei), je Etikett Länge in mm und Stücke: `page`, `src` [x0, y0, x1, y1] mm auf der Marke, `rotation`
  (0/90/180/270), `dst` [x, y] mm (linke obere Ecke auf dem Etikett, Leserichtung), `scale`, `kind`
  (`barcode` | `text` – Barcodes nie verkleinern).
- **Werte** aus der Testblatt-Auswertung (Kanten auf 0,5 mm), DHL Privat 1/1a am echten Original geschärft
  (`verified: true`). Herkunft in `parcel_data/README.md` (Verfahren, keine Kopie fremden Codes).
- **Eigene Typen:** `$XDG_DATA_HOME/labelwerk/paketmarken/*.json`, gleiches Format, `own: true`; fremde Eingabe
  (geprüft wie Dateien: Grenzen, Struktur → `ParcelError`, kein Traceback).

## 2 – Kern: `parcel.py` (ohne Qt)

- `catalog(country=None)`, `countries()`, `find(type_id)`, `own_types()`, `save_own(type)`, `remove_own(id)`.
- `load(path)` → `Source` (Seiten als Bilder in Druckerauflösung über pypdfium2, Seitengrößen in mm, Text je Seite);
  PNG/JPG/GIF als eine Seite (Amazon-GIF). Fremde Eingabe: Größe, Seitenzahl begrenzt.
- `detect(source, country)` → Typen mit Punktzahl (Textmuster, Seitengröße), bester zuerst; nichts → [].
- `snap(img, box_px)`: Kanten eines Stücks nach außen bis zur ersten ganz weißen Zeile/Spalte, höchstens 3 mm; ohne
  weiße Linie bleibt die Kante (Antwort 6a).
- `convert(source, type, label_id, model)` → `Document`(e) (je Etikett eins): Stücke als `ImageObject` (Strich,
  Schwelle 128, 1:1 bei `scale` 1), Länge fest. **Skalierung:** Layout `"62"` gilt für die bedruckbare Breite von
  62 mm endlos; anderes Band/Etikett: Layout mit Faktor bedruckbare Breite ÷ Referenz (breiter → größer, Antwort 2a);
  Etikett ab 95 mm Breite und Typ mit `"100x150"`-Layout → dieses; festes (gestanztes) Etikett zu kurz → so weit
  verkleinert, dass es passt. Barcode-Stücke unter 100 % → Hinweis „Barcodes verkleinert – vor dem Versand
  prüfen, ob sie lesbar sind“.
- `arrange(pieces, across_mm)` (eigene Typen ohne `dst`): Stücke nacheinander in Spalten längs des Bands, je Spalte so
  hoch wie die Breite, Text-Stücke höchstens so verkleinert, dass sie passen, Barcodes 1:1 (zu breit → gedreht, sonst
  Hinweis).

## 3 – Oberfläche: Reiter PAKETMARKE

- **Werkzeug** `parcel` in `gui/tools.py` (auch `START_TOOLS`); Panel `panels/parcel.py`:
  Land (Auswahl, Standard aus der Sprache/Region, nur Länder mit Typen + „Eigene“), MARKE ÖFFNEN … (PDF/PNG/JPG/GIF,
  Ablegen auf das Panel), erkannter Typ vorgewählt (Liste nach Dienst gruppiert, „ungeprüft“-Kennzeichen), Vorschau
  auf der Arbeitsfläche (erstes Etikett; mehrere: ◀ n/N ▶ wie Serie), DRUCKEN (alle Etiketten in einem Auftrag, Schnitt
  nach jedem), IM EDITOR ÖFFNEN (Etikett als normales Dokument, Stücke verschiebbar; Rückfrage bei Änderungen wie
  Neu).
- **Eigener Typ:** EIGENEN TYP ANLEGEN … öffnet die Marke groß in einem Fenster; Bereiche aufziehen (Rechteck, Drehung
  0/90/180/270, Häkchen „Barcode – nicht verkleinern“), Name, Speichern → `arrange` ordnet an; Umbenennen/Löschen in
  der Liste. Eigene Typen erscheinen unter „Eigene“ und werden auch erkannt (Seitengröße + optional Textmuster aus
  dem Fenster).
- Nichts wird gedruckt, solange kein Typ gewählt ist; Fehler als Hinweis im Panel.

## 4 – Kommandozeile

`labelwerk parcel DATEI [--type ID|auto] [--country DE] [-l ETIKETT] [-m MODELL] [-p DRUCKER] [--preview AUS.png]`,
`labelwerk parcel --list [--country DE]` (Typen mit Erkennung/ungeprüft). `--preview` mit mehreren Etiketten:
`AUS-1.png`, `AUS-2.png`.

## 5 – Werkzeug für neue Typen (`tools/parcel/`)

`make_sheets.py` (Testblätter, Qt), `analyze.py` (Auswertung der umgewandelten Blätter → Layout-JSON; nur zum
Pflegen, braucht numpy/scipy/zxing-cpp, keine Laufzeit-Abhängigkeit), Anleitung „Neuen Markentyp beisteuern“ in
`parcel_data/README.md`.

## Tests

Katalog-Schema (jeder Typ gültig, Stücke innerhalb der Quelle, Etikett-Längen), `detect` mit erzeugten PDFs
(pypdfium2/Pillow, Texte und Größen), `snap`, `convert` (Lage/Drehung/Maßstab der Stücke, Barcodes 1:1 – gelesen mit
zxing-cpp, breiteres Band größer, gestanzt kleiner + Hinweis), `arrange`, eigene Typen (Speichern/Laden/fremde
Eingabe), CLI, GUI-Reiter (Öffnen, Erkennen, Vorschau, Drucken ersetzt, Editor), eigenes-Typ-Fenster; keine echten
Marken des Nutzers in Tests (nur erzeugte Testmarken).
