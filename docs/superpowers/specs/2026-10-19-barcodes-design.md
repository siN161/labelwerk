# Barcodes und QR-Codes – Design

Stand: 2026-10-19 · Status: Antworten des Nutzers 1a 2a 3a 4a 5a 6a 7a 8a 9a (jeweils die Empfehlung);
Spec danach ohne eigene Freigabe geschrieben – zur Prüfung mit der Abnahme.

## Ziel

Strichcodes und QR-Codes als eigenes Objekt aufs Etikett (wie im P-touch Editor): Betriebsmittel, Lagerplätze,
Artikel (EAN), Links. Der Code wird in ganzen Druckpunkten gezeichnet, damit er bei 300 dpi sicher lesbar
bleibt. Platzhalter `{Spalte}` aus der Serie gehen auch im Inhalt.

## Entscheidungen (Antworten)

1. Codes: **QR, Code 128, Code 39, EAN-13, EAN-8** – QR über `segno` (BSD-3-Clause, reines Python), die
   Strichcodes selbst kodiert (Tabellen aus den Normen, ohne Abhängigkeit).
2. **Klartext** unter Strichcodes standardmäßig an, abschaltbar (QR nie).
3. **Größe:** Modulbreite in ganzen Druckpunkten (schmalster Strich bzw. QR-Quadrat), Höhe frei; Anfasser und
   Felder rasten auf ganze Punkte ein.
4. **Platzhalter** `{Spalte}` im Inhalt – gleich mit dazu.
5. **QR-Fehlerkorrektur** Standard M, wählbar L/M/Q/H.
6. **QR-Inhalt:** freier Text (Links gehen damit).
7. Eigener **Reiter BARCODE** (nach Bild) mit Knopf „Barcode einfügen“ und Panel.
8. **Falscher Inhalt:** Hinweis im Panel; die Arbeitsfläche zeigt den letzten gültigen Stand (wie bei jedem
   Renderfehler), Drucken meldet den Fehler. EAN mit 12 bzw. 7 Ziffern: Prüfziffer wird ergänzt.
9. **CLI** später.

## Nicht enthalten

ITF, Codabar, DataMatrix, PDF417, GS1-128 (FNC1), Micro-QR, Helfer für WLAN/Visitenkarte, Prüfziffer bei
Code 39, Klartext über dem Code, Logo im QR-Code, Barcodes in der CLI, Ruhezone als Teil des Rahmens.

## 1 – Kern (Qt-frei)

- **Datenmodell** (`document.py`): `BarcodeObject` (dataclass, kw_only):
  - `kind` (`BARCODE_KINDS` = qr, code128, code39, ean13, ean8; Standard qr), `data` (Inhalt, Text),
  - `x_mm`/`y_mm` (linke obere Ecke nach dem Drehen, immer gesetzt – wie Bilder), `rotation` 0/90/180/270,
  - `module` (Druckpunkte je Modul, 1–`MAX_MODULE` = 20; Standard 3),
  - `h_mm` (Höhe des Strichcodes samt Klartext, ungedreht; Standard 10; QR: unbenutzt – quadratisch),
  - `text` (Klartext, Standard an; QR: unbenutzt), `error` (QR-Fehlerkorrektur `QR_LEVELS` L/M/Q/H,
    Standard M).
  - `positioned` immer True, `is_empty()` immer False (ein Barcode ohne Inhalt ist ein Fehler, kein
    unsichtbarer Rahmen).
  - Die Breite folgt aus dem Inhalt (Zahl der Module × `module`) – es gibt kein `w_mm`.
- **Kodieren** (`barcodes.py`): `encode(kind, data, error="M") -> Code` (gecacht) mit
  `Code(modules: list[str] | Matrix, text, groups)`:
  - QR: `segno.make_qr(data, error=…, boost_error=False)` (Matrix ohne Rand); zu lang →
    `BarcodeError` „Inhalt zu lang für einen QR-Code (Fehlerkorrektur M)“.
  - Code 128: Zeichen ASCII 32–126 (sonst „Code 128 kann „ä“ nicht darstellen“); Zeichensätze B/C mit
    kürzester Folge (dynamische Programmierung über Wechsel B↔C), Prüfzeichen Modulo 103, Stopp.
  - Code 39: 0–9, A–Z, Leerzeichen, `- . $ / + %`; Kleinbuchstaben werden groß; Start/Stopp `*` automatisch
    (`*` im Inhalt ist ein Fehler); breit = 3 × schmal, Lücke zwischen Zeichen = 1 Modul.
  - EAN-13/EAN-8: nur Ziffern (Leerzeichen werden übergangen); 12 bzw. 7 Ziffern → Prüfziffer ergänzt; 13
    bzw. 8 Ziffern → Prüfziffer geprüft („Prüfziffer falsch – richtig wäre 7“); sonst „EAN-13 braucht 12
    oder 13 Ziffern (4 eingegeben)“. Randzeichen links/Mitte/rechts, Zeichensätze L/G/R nach der ersten
    Ziffer.
  - Leerer Inhalt → „Barcode ohne Inhalt“; Strichcodes höchstens `MAX_LINEAR` = 80 Zeichen, jeder Inhalt
    höchstens `MAX_DATA` = 2000 Zeichen.
  - `BarcodeError(ValueError)` mit deutscher Meldung; `check(obj)` prüft auch `kind`, `module`, `h_mm`,
    `error`, `rotation`.
- **Maße** (`barcodes.size(obj) -> (w, h)` in Druckpunkten, ungedreht): QR `n × module` im Quadrat;
  Strichcodes `Module × module` breit (EAN-13 mit Klartext: 7 Module links für die erste Ziffer dazu),
  `_dots(h_mm)` hoch.
- **Zeichnen** (`barcodes.draw(obj) -> Image "L"`): Module als exakte Rechtecke, weißer Grund, keine
  Kantenglättung in den Strichen. Klartext (Strichcodes, `text`): DejaVu Sans (fontconfig wie Text), Höhe
  rund 9 Module, mindestens 6 pt, verkleinert, bis jede Gruppe in ihre Breite passt; Code 128/39 mittig unter
  dem Code; EAN in der üblichen Anordnung (erste Ziffer links vor dem Code, je 6 bzw. 4 Ziffern zwischen den
  verlängerten Randzeichen). Strichhöhe unter 1 mm → „Barcode zu niedrig – höher ziehen oder Klartext aus“.
- **Rendern** (`render.py`): `_prepare` misst Barcodes über `barcodes.size` (Rahmen fest, wie Bilder),
  `_finish` zeichnet und dreht wie bei Bildern; Renderfehler sind `BarcodeError` (ValueError) – wie
  `TextTooLarge`.
- **Layout** (`layout.py`): Barcodes haben einen festen Rahmen aus Modulbreite und Höhe:
  - `exact_rect`: Lage aus dem Modell, Breite wie gerendert, Höhe aus `h_mm` (Strichcodes).
  - `place`/`set_frame` (Felder, Ausrichten, Angleichen, Drehen): Breite → `module` = gerundet
    (Breite ÷ Module, 1–20), QR: Breite und Höhe gleich (das zuletzt geänderte Maß zählt); Höhe → `h_mm`.
  - `resize` (Anfasser): QR hält das Quadrat (`keep_aspect`), die festgehaltene Seite bleibt beim Einrasten
    stehen; Strichcodes: waagerecht rastet `module`, senkrecht `h_mm` frei.
  - `maximize_object`: größtmögliche Modulbreite, die hineinpasst (abgerundet), mittig.
  - `to_grid`: nur vorhandene Felder (`h_mm`); Schrift-Funktionen: TypeError wie bei Bildern.
- **Serie** (`series.py`): `placeholders`, `missing`, `fill` sehen auch `BarcodeObject.data`; gefüllt wird
  der Inhalt (Kopie nur bei Platzhaltern, sonst dasselbe Objekt). Ein Barcode behält je Zeile seine linke obere
  Ecke (die Breite kann wechseln).
- **Speichern** (`storage.py`): `"type": "barcode"`, Schema `BARCODE` mit Arten `barcode_kind`,
  `barcode_data` (≤ `MAX_DATA`), `module`, `qr_level`; Größe für die Grenze „Etikett zu groß“ aus
  `barcodes.size` (ungültiger Inhalt zählt 0 – das Rendern meldet ihn). Format-Version bleibt 1 (ältere
  labelwerk melden „Objektart unbekannt“).

## 2 – GUI

- **Reiter BARCODE** (Symbol `view-barcode-qr`), Panel „Barcode“:
  - Hinweis ohne Auswahl: „Barcode oder QR-Code einfügen – Art wählen, Inhalt eintippen“.
  - **Einfügen:** Knopf BARCODE EINFÜGEN (Aktion `barcode.insert`, Kürzel änderbar, Standard leer) – Art aus
    der Auswahl darüber, Beispielinhalt je Art (QR „labelwerk“, Code 128/39 „ABC-123“, EAN-13
    „590123412345“, EAN-8 „9638507“), mittig im Innenraum bzw. bedruckbaren Bereich; passt er nicht, wird
    er kleiner (Modulbreite, Höhe) bzw. gedreht wie Symbole (`insert_placement`). Danach ausgewählt, das
    Inhaltsfeld hat den Fokus mit markiertem Text (Tippen ersetzt das Beispiel).
  - **Art** (Auswahl: QR-Code, Code 128, Code 39, EAN-13, EAN-8): wirkt auf den gewählten Barcode; stand dort
    noch der Beispielinhalt der alten Art, kommt der der neuen.
  - **Inhalt** (einzeiliges Feld): jede Eingabe sofort auf der Arbeitsfläche, eine Bearbeitung = ein
    Rückgängig-Schritt; darunter Fehler bzw. Hinweis (`#hint`): Meldung von `barcodes.check`, z. B.
    Prüfziffer.
  - **Größe:** Modul (Zahlenfeld 1–20 Punkte, angezeigt in mm: „0,25 mm“), Höhe (mm, nur Strichcodes),
    Klartext (nur Strichcodes), Fehlerkorrektur (nur QR: „L – 7 %“, „M – 15 %“, „Q – 25 %“, „H – 30 %“);
    Hinweis Ruhezone („links und rechts je 2,5 mm frei lassen“: 10 Module bei Strichcodes, 4 bei QR).
  - **Drehen** (Aktionen wie im Reiter Layout), **Position (mm)** mit änderbarer Größe (rastet ein).
- **Arbeitsfläche:** Barcodes wie Bilder (Auswahl, Ziehen, Anfasser; QR: Ecken und Kanten halten das
  Quadrat). Doppelklick auf einen Barcode: Reiter BARCODE, Fokus ins Inhaltsfeld.
- **Serie:** Spalte einfügen (Doppelklick in der Spaltenliste) bei gewähltem Barcode: Beispielinhalt wird durch
  `{Spalte}` ersetzt, sonst angehängt (ohne Leerzeichen). Vorschau und Druck füllen den Inhalt je Zeile;
  ein ungültiger Wert meldet „Zeile n: …“ (wie bei Text).
- **Drucken:** keine Änderung – ungültiger Barcode verhindert den Druck mit der Meldung des Renderfehlers.

## Tests

- Kern: Code-128-Tabelle (107 Muster, je 11 Module, 3 Striche/3 Lücken), kürzeste Zeichensatzfolge (Ziffern-
  läufe, ungerade Ziffern), Prüfzeichen; Code 39 (Muster, Kleinbuchstaben, ungültige Zeichen); EAN
  (Prüfziffer ergänzen/prüfen, Leerzeichen); QR (Stufe, zu lang); Maße und Zeichnen (ganze Punkte, Klartext,
  zu niedrig); Rendern/Drehen; Layout (Anfasser, Felder, Maximieren, Drehen, Angleichen, Raster);
  Serie (Platzhalter im Inhalt); Speichern/Laden mit Grenzen.
- **Lesbarkeit:** jede Art wird gerendert (auch gedreht, mit/ohne Klartext) und mit `zxing-cpp`
  (Apache-2.0, nur Entwicklung: `[dev]`) dekodiert – Inhalt muss gleich sein. Ohne zxing-cpp (z. B. Python
  ohne passendes Wheel) werden diese Tests übersprungen.
- GUI: Panel (Einfügen, Art wechseln, Inhalt live, Fehlerhinweis, Modul/Höhe/Klartext/Fehlerkorrektur),
  Anfasser rasten ein, Doppelklick → Inhaltsfeld, Spalte einfügen, Serie druckt gefüllte Barcodes (Druck
  gefälscht), Rückgängig.
