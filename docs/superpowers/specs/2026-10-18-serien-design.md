# Serien aus CSV/Excel und Nummerierung (Etappe 3e) – Design

Stand: 2026-10-18 · Status: Antworten des Nutzers 1a 2a 3a 4c 5a 6a 7a; Spec nach „Zieh durch“ ohne eigene
Freigabe geschrieben – zur Prüfung mit der Abnahme.

## Ziel

Viele gleich aufgebaute Etiketten auf einmal (Klemmen, Betriebsmittel, Regale, Adressen): Ein Etikett mit
Platzhaltern `{Spalte}` wird für jede gewählte Zeile einer Tabelle (CSV oder Excel) bzw. einer Nummerierung
(X1, X2 …) gefüllt und in einem Auftrag gedruckt.

## Entscheidungen (Antworten)

1. Dateiformate: **CSV und Excel (.xlsx)**.
2. Spalten aufs Etikett: **Platzhalter im Text** `{Spalte}`, eingefügt über eine Spaltenliste.
3. Auswahl: **Tabelle mit Häkchen je Zeile**, „Alle“/„Keine“.
4. Schnitt beim Drucken: **wählbar** – nach jedem Etikett (Standard) oder nur am Ende.
5. **Nummerierung ohne Datei** (Start, Schritt, Anzahl, Stellen) gleich mit dazu.
6. Die `.labelwerk`-Datei **merkt sich den Pfad** der Tabelle und liest sie beim Öffnen neu ein.
7. Vorschau: **Blättern durch die Zeilen** (◀ Zeile 3/40 ▶), die Arbeitsfläche zeigt die echte Zeile.

## Nicht enthalten

ODS, Bilder oder Barcodes aus Spalten, Serien über die CLI, Filter/Sortieren in der Tabelle, Speichern der
Häkchen (nach dem Öffnen ist jede Zeile gewählt), mehrere Etiketten nebeneinander.

## 1 – Kern (Qt-frei)

- **Datenmodell** (`document.py`):
  - `Numbering(start=1, step=1, count=10, digits=0)` (frozen): Zahlen `start + i·step`, i < `count`, mit
    führenden Nullen auf `digits` Stellen; Grenzen: `count` 1–10 000, `step` ≠ 0, |Werte| ≤ 10⁹, `digits` 0–10.
  - `Series(source=None, sheet=None, numbering=None, cut="each")` (frozen): genau eins von `source`
    (Pfad der Tabelle) und `numbering`; `sheet` = Tabellenblatt (Excel, None = erstes); `cut` = `"each"` |
    `"end"`.
  - `Document.series: Series | None = None`.
- **Tabellen** (`series.py`): `Table(columns: list[str], rows: list[list[str]])`.
  - `load_table(path, sheet=None) -> Table`; `sheet_names(path) -> list[str]` (CSV: leer).
  - CSV: höchstens 20 MB; UTF-8 (mit/ohne BOM), sonst Windows-1252; Trennzeichen erkannt (`;` `,` Tab `|`,
    sonst `;`); Zeilenumbrüche in Zellen → Leerzeichen.
  - XLSX über `openpyxl` (MIT; mit `defusedxml`, PSF – gegen XML-Angriffe), nur lesend, Werte statt Formeln;
    höchstens 20 MB. Zahlen: ganze ohne „,0“, sonst mit Komma (1,5); Datum TT.MM.JJJJ (mit Uhrzeit, wenn
    nicht 0:00); leere Zellen leer.
  - Erste Zeile = Spaltennamen (leer → „Spalte N“, doppelte → „Name (2)“); leere Zeilen am Ende entfallen;
    höchstens 10 000 Zeilen und 200 Spalten.
  - Fehler → `SeriesError` (deutsch, mit Dateiname): nicht gefunden, nicht lesbar, kein Tabellenformat,
    Blatt fehlt, zu groß.
  - `numbering_table(n) -> Table` mit der Spalte „Nummer“.
  - `table_for(series, base=None) -> Table` (Datei bzw. Nummerierung).
- **Platzhalter:** `placeholders(doc) -> list[str]` (Namen in Textobjekten, Reihenfolge des Auftretens),
  `fill(doc, columns, row, keep=None) -> Document` (Kopie; `{Name}` einer vorhandenen Spalte → Zellwert, die
  Formatierung des Stücks, in dem der Platzhalter beginnt, gilt für den Wert; über Stückgrenzen hinweg möglich;
  unbekannte Namen bleiben stehen; `keep` = Index eines Objekts, das unverändert bleibt – Schreibmodus).
  `missing(doc, columns) -> list[str]` (Platzhalter ohne Spalte).
- **Drucken mehrerer Etiketten** (`printer.py`): `build_instructions(images, label_id, model, cut=True,
  cut_every=1)` nimmt eine Liste (ein Bild bleibt erlaubt); `cut_every` = n schneidet alle n Etiketten
  (Brother `ESC i A n`, 1–255) und am Ende. „Nur am Ende“ = `cut_every = min(Anzahl, 255)`. `print_images`
  wie `print_image` für eine Liste.
- **Speichern** (`storage.py`): Eintrag `series` (null = keine), Schema `SERIES`/`NUMBERING` mit Grenzen;
  `source` als Text (Pfad wie gewählt, absolut).

## 2 – GUI

- **Reiter SERIE** (nach LAYOUT), Panel „Serie“:
  - Quelle: Knöpfe **TABELLE …** (Dialog CSV/XLSX) und **NUMMERIERUNG**; Dateiname, Blatt-Auswahl (Excel),
    Felder Start/Schritt/Anzahl/Stellen (Nummerierung); **ENTFERNEN** (Serie aus dem Etikett nehmen).
  - **Spalten:** Liste der Spaltennamen; Doppelklick/Enter fügt `{Spalte}` ein – im Schreibmodus an der
    Schreibmarke, sonst in das gewählte Textobjekt (Ende, Schreibmodus startet), sonst als neuer Textrahmen
    links oben im Innenraum. Hinweis bei Platzhaltern ohne Spalte („Unbekannte Spalte: X“).
  - **Zeilen:** Tabelle (erste Spalten) mit Häkchen je Zeile, „Alle“/„Keine“, Anzahl gewählt.
  - **Vorschau:** ◀ Zeile n/N ▶ – die Arbeitsfläche zeigt das Etikett mit dieser Zeile; Klick auf eine Zeile
    der Tabelle springt dorthin.
  - **Schnitt:** Auswahl „Nach jedem Etikett“ / „Nur am Ende“ (gespeichert in `Series.cut`).
- **Arbeitsfläche:** zeigt mit Serie das gefüllte Etikett der Vorschau-Zeile; das Objekt im Schreibmodus
  zeigt seine Platzhalter (Schreibmarke passt). Auswahl, Ziehen und Layout wirken auf das Etikett selbst.
- **DRUCKEN** mit Serie druckt alle gewählten Zeilen in einem Auftrag – vorher Rückfrage „N Etiketten
  drucken?“ (auch bei 1), dieselben Prüfungen wie bisher (leer, ragt über – an der Vorschau-Zeile); jedes
  Etikett wird für sich gerendert (automatische Länge je Zeile). Fehler beim Rendern einer Zeile →
  Meldung mit Zeilennummer, nichts gedruckt.
- **Datei/Favorit:** beim Öffnen wird die Tabelle neu eingelesen; fehlt sie → Hinweis, Serie bleibt im Etikett
  (Panel zeigt den Pfad, TABELLE … wählt neu). Direktdruck eines Favoriten mit Serie druckt alle Zeilen
  (Rückfrage mit Anzahl).

## Tests

- Kern: CSV (Trennzeichen, Kodierungen, BOM, Anführungszeichen, Umbrüche, leere/doppelte Spaltennamen,
  Grenzen), XLSX (Zahlen, Datum, leere Zellen, Blätter, Formeln als Werte) – Testdateien in `tmp_path`
  erzeugt; Nummerierung; Platzhalter (über Stückgrenzen, unbekannte, Formatierung, `keep`); Rasterdaten für
  mehrere Etiketten mit Schnitt nach jedem bzw. am Ende (Befehle `ESC i A n`, `ESC i K`, Seitenende
  `0x0C`/`0x1A`), ohne Drucker; Speichern/Laden mit Grenzen.
- GUI (Dialoge ersetzt): Panel, Spalte einfügen (drei Wege), Häkchen, Blättern zeigt gefüllte Zeile,
  Schreibmodus zeigt Platzhalter, Drucken mehrerer Etiketten (Druck gefälscht) mit Rückfrage und Schnitt,
  Öffnen mit fehlender Tabelle, Rückgängig.
