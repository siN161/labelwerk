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
4. **b – Reiter PAKET** (Überschrift „Paketmarke“) in der GUI **und** CLI `labelwerk parcel`.
5. **a – Typ automatisch erkennen** (Text, Seitengröße), von Hand änderbar.
6. **a – Kanten an die echte Marke anpassen:** Bereiche rücken nach außen bis zum nächsten weißen Rand.
7. **b – eigene Typen gleich mit:** Bereiche auf einer Marke aufziehen, als eigenen Typ speichern.
8. **a – Deutschland zuerst, Gerüst für Länder:** Länder/Dienste/Typen sind Daten (JSON), nachpflegbar ohne Code.

## Nicht enthalten

Marken kaufen/abrufen (kein Konto, kein Netz), andere Länder mit Daten (nur das Gerüst), DPD/GLS/UPS (ohne
Beispiele), Briefmarken/Internetmarke (geht schon über `print-file`), Texterkennung (OCR).

## 1 – Daten: Markentypen (`src/labelwerk/parcel_data/`)

- **Katalog** `catalog.json` (Format in `parcel_data/README.md`): Länder (`DE` mit Namen {de, en}) → Dienste (`dhl`,
  `hermes`, Namen) → Typen. Ein Typ: `id` („dhl-privat-1“), `names` {de, en}, `country`, `carrier`,
  `source` (`sizes_mm`: mögliche Seitengrößen, ± 4 mm, auch quer; `raster` für Bildmarken: Auflösung und Lage auf der
  Seite), `detect` (`all`/`any`/`none`: Begriffe im PDF-Text), `verified` (bool), `layouts`.
- **Layout** je Ausgabe-Format (`"62"` = Referenz 62 mm endlos: Seite quer, x längs des Bands; `"100x150"` falls
  vorhanden, hochkant): Liste von Ausgabe-Etiketten (Retoure: zwei), je Etikett `size_mm` und Stücke in
  Malreihenfolge: `page`, `src` [x0, y0, x1, y1] mm auf der Marke, `rotation` (im Uhrzeigersinn 0/90/180/270),
  `dst` [x0, y0, x1, y1] mm – Rechteck nach dem Drehen, das Stück wird genau darauf skaliert (paketikett skaliert
  leicht ungleich) –, `kind` (`barcode` | `text`; vergrößerte Stücke > 1,03 gelten als Barcode).
- **Werte** aus der Testblatt-Auswertung (Kanten auf 0,25 mm, Ausschnitte auf die Seite begrenzt), DHL Privat 1/1a am
  echten Original geschärft (`verified: true`). 1a gibt es zweimal: Eingang A4 (`dhl-privat-1a`) und Marke 100 × 150
  (`dhl-privat-1a-100x150`). Amazon-PDF-Typen auch im Letter-Format. Amazon-GIF (`dhl-retour-3`): Bild bei 300 dpi
  an geschätzter Stelle der A4-Seite (x −2,5 mm, y 189,4 mm). Herkunft und „Neuen Typ beisteuern“ in
  `parcel_data/README.md` (Verfahren, keine Kopie fremden Codes).
- **Eigene Typen:** `$XDG_DATA_HOME/labelwerk/paketmarken/<id>.json` – nur `pieces` (ohne `dst`, `arrange` ordnet an),
  `source`, `detect`, `names`; fremde Eingabe (`own_from_dict`: Kennung, Namen, Größen, Begriffe, Stücke geprüft →
  `ParcelError`, kaputte Dateien übergangen mit Hinweis `own_warnings`).

## 2 – Kern: `parcel.py` (ohne Qt)

- `countries()`, `carriers(country)`, `types(country=None)` (mitgelieferte des Lands + eigene), `find(type_id)`,
  `own_dir()`, `own_types()`, `own_warnings()`, `own_from_dict(data)`, `own_to_dict(type)`, `save_own(type)`,
  `remove_own(id)`; `ParcelType` (`name` in der Sprache, `verified`, `own`, `layouts`, `pieces`), `Piece`, `Sheet`.
- `load(path)` → `Source` (Seitengrößen in mm und Text je Seite; `page(n, dpi, type)` rendert bei Bedarf in der
  Seitenfläche des Typs, außen weiß, eine Seite gemerkt, höchstens 80 Mio. Pixel); PNG/JPG/GIF als eine Seite über
  `files.load_image` (Transparenz, 16 Bit, EXIF, Größe begrenzt; Pixel vor dem Dekodieren ≤ 50 Mio.; dpi < 50 oder
  > 1200 gilt als fehlend). Fremde Eingabe: Endung, ≤ 32 MB, 1–20 Seiten (0 Seiten: eigene Meldung) → `ParcelError`.
- `placement(source, type, n)` → `Placement`: Seite in der Seitenfläche des Typs (erste `sizes_mm`) – passende Größe
  wie sie ist (Letter oben links auf A4, weiß aufgefüllt), quer liegende gedreht (die Drehung, bei der mehr Tinte in
  den Bereichen liegt; liegen beide gleich auf: „Richtung nicht eindeutig“), Bild nach Bild-Regel (Seitenverhältnis
  der erwarteten Pixel ±3 %) bzw. auf eine Seitengröße gestreckt (±3 %); sonst `ParcelError` („passt nicht zum Typ“) –
  `convert` prüft das vorab.
- `detect(source, country, label_id=None, own=None)` → [(Typ, Punktzahl)], bester zuerst: Seitengröße muss passen
  (Bildmarken: Typ mit Bild-Regel), `all` muss vorkommen; Gleichstand: geprüfte vor ungeprüften, mit `label_id` der
  Typ mit passendem Layout (ab 95 mm: 100×150), sonst Katalogreihenfolge; nichts → []. Bilder: nur der Rastertyp
  mit passendem Seitenverhältnis (Amazon-GIF), sonst nichts → `--type` bzw. Auswahl. `ambiguous(found)`: gleichauf
  liegende Spitze ohne geprüften Sieger → diese Typen (CLI druckt dann nicht, sondern verlangt `--type`).
- `snap(img, box_mm, dpi)`: Kanten, die Inhalt durchschneiden, nach außen bis zur ersten ganz weißen Linie, höchstens
  3 mm (Antwort 6a) – **nur für ungeprüfte Typen** (am echten DHL-Original verschlechterte es geprüfte Kanten von 5,2
  auf 8,2 % Abweichung) und nie neu in den Ausschnitt eines anderen Stücks (`_alone`).
- `convert(source, type, label_id, model)` → `Conversion(documents, notes, layout, scale)`: je Ausgabe-Etikett ein
  `Document` (Rand 0, Stücke als `ImageObject`, Strich/Schwelle 128, Seitenverhältnis frei, vorab gedreht); Inhalt
  auf seine Fläche beschnitten, quer mittig. **Skalierung:** Endlosband – Inhalt füllt die bedruckbare Breite (breiter
  → größer, Antwort 2a), Länge = Inhalt + Vorschub, höchstens Modellgrenze; festes Etikett – passt hinein, die Lage
  (längs/quer) mit dem größeren Maßstab gewinnt. Ab 95 mm bedruckbarer Breite und mit `"100x150"`-Layout → dieses.
  Spätere Stücke (Malreihenfolge) machen frühere dort weiß, wo sie liegen (sonst verdeckt Tinte darunter z. B. den
  DataMatrix-Code); Ausschnitte außerhalb der Seite sind weiß. Fehlt das Layout fürs Format (nur 100×150, aber
  schmales Band), ordnet `arrange` die Stücke neu an (Layout „arranged“, Barcodes 1:1).
  Barcode-Stücke unter 97 % → Hinweis „Barcodes verkleinert auf n % – vor dem Versand prüfen, ob sie sich lesen
  lassen.“ Runde Etiketten → `ParcelError`. Marke gerendert in Druckerauflösung × größtem Maßstab (≤ 600 dpi).
- `arrange(pieces, across_mm)` (eigene Typen): Stücke nacheinander in Spalten längs des Bands bis zur Breite, Texte
  höchstens so verkleinert, dass sie quer passen, Barcodes 1:1 (nur zu breite kleiner); eigene Typen werden nie
  vergrößert.

## 3 – Oberfläche: Reiter PAKET (Panel-Überschrift „Paketmarke“)

Der Reiter heißt kurz „PAKET“ (Tooltip „Paketmarke …“), damit die Werkzeugleiste auf Deutsch nicht überläuft;
EINSTELLUNGEN und DRUCKEN stehen in einer eigenen Leiste rechts und laufen nie über (nur Reiterknöpfe dürfen es).

- **Werkzeug** `parcel` in `gui/tools.py` (auch `START_TOOLS`/`HIDEABLE_TOOLS`); Panel `panels/parcel.py`:
  Land (Auswahl, Standard aus der Region, nur Länder mit Typen + „Nur eigene Typen“), MARKE ÖFFNEN … (Dateidialog mit
  Vorschau; PDF/PNG/JPG/GIF, Ablegen auf Panel oder Arbeitsfläche), Typliste nach Dienst gruppiert (etwa 7 Einträge
  sichtbar), ✓ an den Typen mit der höchsten Punktzahl, „ungeprüft“-Kennzeichen; vorgewählt der beste – bei
  Gleichstand ohne geprüften Sieger (`parcel.ambiguous`) oder ohne Treffer nichts (Hinweis nennt die Kandidaten),
  bei Gleichstand mit Sieger Hinweis „bitte Auswahl prüfen“; Hinweise aus der Umwandlung, Fehler (`ParcelError`,
  Renderfehler) und beschädigte eigene Typen im Panel.
- **Nur Ansicht:** Mit geladener Marke zeigt die Arbeitsfläche das gewählte Etikett der Umwandlung (◀ n/N ▶) bzw. –
  ohne Umwandlung – ein leeres Etikett; Aktionen des Bereichs Arbeitsfläche und Rückgängig/Wiederherstellen sind
  gesperrt, Einfügen/Symbol/Bild/Ablegen von Bilddaten ändern nichts (Hinweis „nur Ansicht – IM EDITOR ÖFFNEN oder
  anderen Reiter wählen“); eine abgelegte Datei lädt die Marke. Anderer Reiter: wieder das Dokument.
- **DRUCKEN** (Panel, Werkzeugleiste, Strg+P): alle Etiketten in einem Auftrag, Schnitt nach jedem; ohne Umwandlung
  nichts, Meldung „Erst den Markentyp wählen“ bzw. der Fehler. **IM EDITOR ÖFFNEN:** Etikett als normales Dokument
  (Stücke verschiebbar), gilt als geändert (Rückfrage beim Schließen/Neu); Rückfrage bei Änderungen wie Neu.
- **Eigener Typ:** EIGENER TYP … öffnet die Marke groß in einem Fenster (Splitter Marke/Einstellungen); Bereiche
  aufziehen, verschieben (auf der Seite begrenzt), Entf löscht; Drehung 0/90/180/270, „Barcode – nicht verkleinern“,
  Name (höchstens 200 Zeichen), „Erkennen an“; Hinweis bei überlappenden Bereichen; Vorschau des Ergebnisses
  (entprellt, beim Loslassen sofort; der Name ändert sie nicht); SPEICHERN nur mit gültigem Typ
  (`own_from_dict`), sonst der Grund in der Vorschau. Gewählter eigener Typ: Knöpfe UMBENENNEN …/LÖSCHEN unter der
  Liste (auch Kontextmenü); Umbenennen behält die aktuelle Wahl. Eigene Typen erscheinen am Ende der Liste und
  werden auch erkannt (Seitengröße + optional Textmuster).

## 4 – Kommandozeile

`labelwerk parcel DATEI [--type ID|auto] [--country DE] [-l ETIKETT] [-m MODELL] [-p DRUCKER] [--preview AUS.png]`
(nennt den erkannten Typ und gleich gute andere, Hinweise auf stderr; drucken: alle Etiketten in einem Auftrag),
`labelwerk parcel --list [--country DE]` (Typen mit geprüft/ungeprüft/eigener). `--preview` mit mehreren Etiketten:
`AUS-1.png`, `AUS-2.png`.

## 5 – Werkzeug für neue Typen (`tools/parcel/`)

`make_sheets.py` (Testblätter, Qt), `analyze.py` (QR-Codes im Ergebnis → Bereiche), `extract.py` (genaue Bereiche
je Typ: fehlende Stücke per Kreuzkorrelation, Kanten per Nachbau-Vergleich), `assemble.py` (→ templates.json),
`catalog.py` (→ catalog.json mit Erkennung); nur zum Pflegen, braucht numpy/scipy/zxing-cpp, keine Laufzeit-
Abhängigkeit; Datenordner über `LABELWERK_PARCEL_DIR`, echte Marken nur lokal (`Original/originale.json`).
Anleitung „Neuen Typ beisteuern“ in `parcel_data/README.md`, Überblick `tools/parcel/README.md`.

## Tests

Katalog-Schema (jeder Typ gültig, Stücke innerhalb der Quelle, Etikett-Längen), `detect` mit erzeugten PDFs
(pypdfium2/Pillow, Texte und Größen), `snap`, `convert` (Lage/Drehung/Maßstab der Stücke, Barcodes 1:1 – gelesen mit
zxing-cpp, breiteres Band größer, gestanzt kleiner + Hinweis), `arrange`, eigene Typen (Speichern/Laden/fremde
Eingabe), CLI, GUI-Reiter (Öffnen, Erkennen, Vorschau, Drucken ersetzt, Editor), eigenes-Typ-Fenster; keine echten
Marken des Nutzers in Tests (nur erzeugte Testmarken).
