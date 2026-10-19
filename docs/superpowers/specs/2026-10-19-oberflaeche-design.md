# Oberfläche: Reiter ausblenden, Dateiauswahl mit Vorschau – Design

Stand: 2026-10-19 · Status: Antworten des Nutzers 1a, 2c, 3a; Spec danach ohne eigene Freigabe geschrieben – zur
Prüfung mit der Abnahme.

## Anlass

- Nicht jeder braucht jeden Reiter (Barcode, Serie, Layout …) – die Leiste soll sich verkleinern lassen.
- Bilder einfügen: der Dateidialog zeigt keine Vorschau. labelwerk nutzt den einfachen Qt-Dialog; den Dialog des
  Desktops (COSMIC) bekommt es nicht, weil `QT_QPA_PLATFORMTHEME=qt5ct` nur für Qt 5 gilt.

## Entscheidungen (Antworten)

1. **a – Reiter ausblenden** über Häkchen in den Einstellungen; DATEI und PAPIER bleiben immer sichtbar; Objekte
   ausgeblendeter Reiter bleiben bearbeitbar (ihr Bereich erscheint bei Auswahl), Tastenkürzel wirken weiter.
2. **c – eigener Dialog mit Vorschau** als Standard, Einstellung „Dateiauswahl des Systems verwenden“.
3. **a – eigene kleine Etappe** nach den Abnahme-Korrekturen, vor den Paketmarken.

## 1 – Reiter ausblenden

- **Einstellung** `hidden_tools: list[str] = []` (Werkzeug-Schlüssel; `file`/`paper` und Unbekanntes werden still
  verworfen), `HIDEABLE_TOOLS` im Kern (Test hält es gleich mit `gui/tools.py`).
- **Dialog** → Ansicht: „Reiter in der Leiste“ mit Häkchen je Reiter (DATEI, PAPIER gesetzt und gesperrt), sofort
  wirksam nach SPEICHERN.
- **Hauptfenster:** ausgeblendete Werkzeugknöpfe unsichtbar; Auswahl eines Objekts, dessen Reiter ausgeblendet ist,
  zeigt dessen Bereich trotzdem (kein Knopf hervorgehoben); Tastenkürzel (z. B. Barcode einfügen) wirken weiter;
  Reiter beim Start bzw. zuletzt benutzter ausgeblendet → PAPIER.
- **SERIE erscheint trotzdem**, solange sie gebraucht wird: das Etikett hat eine Serie oder der Drucker bietet
  Schnitt-Optionen im Reiter SERIE (CUPS-Treiber, Zebra-Modus); Erläuterung im Dialog unter den Häkchen.
- **Zurückfallen:** nach SPEICHERN nur, wenn sich die ausgeblendeten Reiter geändert haben und das gezeigte Panel
  weder zur Auswahl noch zum Schreibmodus gehört; wird die Auswahl leer und das gezeigte Panel ist ausgeblendet →
  zuletzt benutzter sichtbarer Reiter (sonst PAPIER), danach Werkzeug wie üblich (kein „Text anlegen“ ohne Reiter).
- **Reiter beim Start** im Dialog: ausgeblendete Reiter gesperrt (an die Häkchen gekoppelt); wird der gewählte gerade
  ausgeblendet → „Zuletzt benutzter“.
- Ohne LAYOUT sind Ausrichten/Größe angleichen nur über eigene Tastenkürzel erreichbar, die Farbe nicht (README).

## 2 – Dateiauswahl mit Vorschau

- **Eigener Dialog** `gui/file_dialog.py`: `QFileDialog` (nicht nativ) mit Vorschau-Bereich rechts, für alle
  Öffnen-Dialoge (Etikett öffnen, Bild einfügen, Tabelle der Serie, später Paketmarke). Speichern bleibt wie bisher
  (ohne Vorschau).
  - Vorschau je Datei, beim Markieren: Bilder (PNG/JPG/GIF/BMP/WebP, verkleinert gelesen, EXIF-Lage), SVG,
    PDF (Seite gerendert, bei mehreren Seiten Seitenwahl ◀ n/N ▶ – die gewählte Seite gilt, die Seitenfrage danach
    entfällt), `*.labelwerk` (Etikett gerendert wie bei Favoriten), Tabellen (erste Zeilen); sonst Name und Größe.
  - Grenzen wie beim Einfügen (Dateigröße, Pixel); Fehler → „Keine Vorschau“, nie ein Absturz; große Dateien
    blockieren nicht spürbar (verkleinertes Lesen, PDF nur die gewählte Seite klein).
  - Merkt Ordner wie bisher; Ablegen/Doppelklick wie gewohnt.
- **Einstellung** `system_file_dialog: bool = False` – „Dateiauswahl des Systems verwenden“ (Dialog → Ansicht).
  An: Dateiauswahl des Desktops über das XDG-Portal (`org.freedesktop.portal.FileChooser`, QtDBus wie das
  Bildschirmfoto); ohne Portal Qt-Dialog. Vorschau und PDF-Seitenwahl dann wie vom Desktop (Seitenfrage danach wie
  bisher).
- **Tests:** Vorschau je Dateiart (erzeugte Dateien), defekte Datei, PDF-Seitenwahl ersetzt die Seitenfrage,
  Einstellung schaltet den Weg; Portal gegen ein Test-Portal auf privatem Bus (eigene Config ohne servicedir, wie
  tests/gui/fake_portal.py) – nie das echte Portal.

## Nicht enthalten

Reihenfolge der Reiter ändern, eigene Reiter, Vorschau im Speichern-Dialog, Miniaturansicht-Raster (nur eine große
Vorschau).
