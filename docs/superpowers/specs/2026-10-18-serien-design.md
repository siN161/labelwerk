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
  - Erste Zeile = Spaltennamen (leer → „Spalte N“, doppelte → „Name (2)“); leere Zeilen entfallen (auch
    mittendrin – die Zeilennummern in labelwerk zählen sie nicht), leere Zellen am Zeilenende auch (nur
    formatierte Excel-Zellen, `;;;` aus Excel-CSV); höchstens 10 000 Zeilen und 200 Spalten, Zellen bis
    100 000 Zeichen; gelesen wird gestreamt (Grenzen greifen sofort).
  - Endungen: `.csv`, `.tsv`, `.txt` (Text) bzw. `.xlsx`, `.xlsm` (Excel); Excel höchstens 100 000 Zeilen samt
    leeren (eine verirrte Zelle weit unten → Meldung statt minutenlangem Lesen).
  - CSV: Trennzeichen aus den ersten 20 Zeilen (gleiche Feldzahl > 1; Tab vor `;` vor `,` vor `|`); UTF-16 mit
    BOM („Unicode-Text“). Excel: nur Arbeitsblätter (keine Diagrammblätter), Standard = erstes sichtbare;
    Zahlenformate führende Nullen (000), Prozent, feste Nachkommastellen; ohne aktives defusedxml kein Excel.
  - Fehler → `SeriesError` (deutsch, mit Dateiname): nicht gefunden, nicht lesbar, kein Tabellenformat,
    Blatt fehlt, zu groß.
  - `numbering_table(n) -> Table` mit der Spalte „Nummer“ (auch die letzte Zahl höchstens 10⁹).
  - `table_for(series, base=None) -> Table` (Datei bzw. Nummerierung).
- **Platzhalter:** `placeholders(doc) -> list[str]` (Namen in Textobjekten, Reihenfolge des Auftretens),
  `fill(doc, columns, row, keep=None) -> Document` (Kopie; `{Name}` einer vorhandenen Spalte → Zellwert, die
  Formatierung des Stücks, in dem der Platzhalter beginnt, gilt für den Wert; über Stückgrenzen hinweg möglich;
  unbekannte Namen bleiben stehen; Leerzeichen in den Klammern zählen nicht; `keep` = Index eines Objekts,
  das unverändert bleibt – Schreibmodus). Das Ergebnis ist nur zum Lesen: unveränderte Objekte sind dieselben
  wie im Original (Renderer-Cache), nur gefüllte Textobjekte neu. `layout.fill_anchored` (Vorschau und Druck):
  frei platzierte Texte ohne feste Rahmengröße behalten den Punkt ihrer Textposition wie beim Tippen –
  „mittig“/„rechts“ gelten für jede Zeile.
  `missing(doc, columns) -> list[str]` (Platzhalter ohne Spalte).
- **Drucken mehrerer Etiketten** (`printer.py`): `build_instructions(images, label_id, model, cut=True,
  cut_every=1)` nimmt eine Liste (ein Bild bleibt erlaubt); `cut_every` = n schneidet alle n Etiketten
  (Brother `ESC i A n`, 1–255) und am Ende. „Nur am Ende“ = `cut_every = min(Anzahl, 255)`. `print_image`
  nimmt auch eine Liste: Teilaufträge (50 Etiketten bei „nach jedem“, sonst `cut_every`), jeder mit eigener
  Statusprüfung – der Drucker meldet Fehler nur kurz nach dem Senden; ein Fehler bricht ab („Etikett k–m von
  N“). Rasterdaten in einem `bytearray` (lange Serien), Folgeseiten markiert (ESC i z n9 = 1).
- **Speichern** (`storage.py`): Eintrag `series` (null = keine), Schema `SERIES`/`NUMBERING` mit Grenzen;
  `source` absolut – liegt die Tabelle im Ordner der Datei (oder darunter), relativ dazu (kein Benutzername in
  weitergegebenen Etiketten); nie leer, kein NUL.

## 2 – GUI

- **Reiter SERIE** (nach LAYOUT), Panel „Serie“:
  - Quelle: Knöpfe **TABELLE …** (Dialog CSV/XLSX) und **NUMMERIERUNG**; Dateiname, Blatt-Auswahl (Excel),
    Felder Start/Schritt/Anzahl/Stellen (Nummerierung); **ENTFERNEN** (Serie aus dem Etikett nehmen).
  - **Spalten:** Liste der Spaltennamen; Doppelklick/Enter fügt `{Spalte}` ein – ans Ende des gewählten
    Textobjekts (mit Leerzeichen davor, wenn nötig), sonst als neuer Textrahmen links oben im Innenraum; der
    Reiter SERIE bleibt dabei offen (auch beim Klick auf Objekte). An einer Stelle im Text: dort `{Spalte}`
    tippen. Hinweis bei Platzhaltern ohne Spalte („Unbekannte Spalte: X“).
  - **Zeilen:** Tabelle (erste Spalten) mit Häkchen je Zeile, „Alle“/„Keine“, Anzahl gewählt.
  - **Vorschau:** ◀ Zeile n/N ▶ – die Arbeitsfläche zeigt das Etikett mit dieser Zeile; Klick auf eine Zeile
    der Tabelle springt dorthin.
  - **Schnitt:** Auswahl „Nach jedem Etikett“ / „Nur am Ende“ (gespeichert in `Series.cut`).
- **Arbeitsfläche:** zeigt mit Serie das gefüllte Etikett der Vorschau-Zeile; das Objekt im Schreibmodus
  zeigt seine Platzhalter (vor der Schreibmarke gerendert, Marke ans Ende – die Lage bleibt), danach wieder
  die Werte. Auswahl, Ziehen und Layout wirken auf das Etikett selbst. Renderfehler nennen die Zeile („Zeile
  n: …“) bzw. im Schreibmodus die Platzhalter.
- **DRUCKEN** mit Serie: Tabelle seit dem Lesen geändert → neu einlesen, Hinweis, nicht drucken; Tabelle ohne
  Zeilen / keine gewählt → Meldung; Rolle wird geprüft / Druck läuft → Meldung; dann Rückfrage „N Etiketten
  drucken?“ (auch bei 1), erst danach jede Zeile rendern (automatische Länge je Zeile, 1 Bit, Fortschritt in
  der Statusleiste); Fehler einer Zeile → „Zeile n: …“, nichts gedruckt; Zeilen, die über das Etikett ragen,
  werden genannt und erfragt; ein Auftrag (Teilaufträge im Drucker-Modul).
- **Datei/Favorit:** beim Öffnen wird die Tabelle neu eingelesen (alle Zeilen gewählt, Vorschau Zeile 1); fehlt
  sie → Hinweis, Serie bleibt im Etikett (Panel zeigt den Pfad, TABELLE … wählt neu – der Dialog beginnt im
  Ordner der Tabelle). Rückgängig liest nicht neu. Fehlt das gewählte Excel-Blatt, bleibt die Blattauswahl.
  Nummerierungsfelder: ungültige Werte (Schritt 0, Zahlen zu groß) werden nicht übernommen, Hinweis. Direktdruck eines Favoriten mit Serie druckt alle Zeilen
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
