# Direkt auf dem Etikett schreiben (Etappe 3d-1b) – Design

Stand: 2026-10-17 · Status: abgestimmt

## Ziel

Text wird wie im P-touch Editor **direkt im Rahmen auf dem Etikett** geschrieben und markiert. Das Feld INHALT im Text-Panel entfällt. Vorschau = Druck gilt auch beim Tippen.

## Nicht enthalten

Automatischer Zeilenumbruch, Rechtschreibprüfung, Suchen/Ersetzen, Bearbeiten mehrerer Rahmen gleichzeitig, Ziehen von Text per Drag & Drop.

## Bedienung

- **Neuer Text:** Werkzeug „Text anlegen“ (A) + Klick aufs Etikett → neuer Rahmen an der Klickstelle, **sofort im Schreibmodus**.
- **Bestehender Text:** 1. Klick wählt den Rahmen (verschieben, Anfasser wie bisher). **Doppelklick** startet den Schreibmodus mit der Schreibmarke an der Klickstelle. Ein Klick in einen schon gewählten Rahmen startet ihn nicht.
- **Im Schreibmodus:**
  - Ziehen markiert Text, Doppelklick markiert ein Wort, Umschalt+Klick erweitert die Markierung.
  - Tasten des Texteditors: Pfeile bewegen die Schreibmarke (mit Umschalt markieren), Pos1/Ende, Entf/Rücktaste, Enter = neue Zeile, Strg+A = ganzer Text des Rahmens, Strg+C/X/V mit Text (Einfügen nur als reiner Text), Strg+B/I/U, Strg+Z/Strg+Umschalt+Z innerhalb der Bearbeitung.
  - **Esc** oder **Klick neben den Rahmen** beendet den Schreibmodus. Ziehen an einem anderen Rahmen beendet ihn und verschiebt dann diesen Rahmen.
  - Panel-Formatierung (Schrift, Größe, A⁺/A⁻, B/I/U, Textposition) wirkt auf die Markierung bzw. das Weitertippen; außerhalb des Schreibmodus wie bisher auf den ganzen Rahmen.
- **Außerhalb des Schreibmodus** gelten die Objekt-Kürzel unverändert (Pfeile verschieben, Entf löscht den Rahmen …).
- **Leerer Rahmen** entfällt beim Verlassen (wie bisher).
- **Rückgängig:** Eine abgeschlossene Bearbeitung ist **ein** Schritt im Dokument-Verlauf.

## Darstellung

- Rahmen im Schreibmodus durchgezogen (statt gestrichelt), ohne Anfasser.
- Schreibmarke: senkrechte Linie, 1 Bildschirmpixel breit, Höhe der Schrift an der Stelle, blinkt im Systemtakt (`QApplication.cursorFlashTime`).
- Markierung: halbtransparente Systemfarbe für Markierungen (`palette().highlight()`, Alpha ≈ 35 %) über dem Druckbild.
- Leerer Rahmen: Schreibmarke dort, wo die erste Zeile beginnen würde, Höhe der aktuellen Schriftgröße, Absatz-Ausrichtung gilt (zentriert → mittig).
- Gedrehte Objekte (90/180/270°): Schreibmarke und Markierung drehen mit; Klicks werden zurückgerechnet.

## Rahmen wächst beim Tippen

- **Ohne feste Rahmengröße** wächst der Rahmen mit dem Text; die feste Kante richtet sich nach der Textposition: linksbündig/Blocksatz → linke Kante bleibt, rechtsbündig → rechte Kante, zentriert → Mitte (in Leserichtung des Texts, bei gedrehten Objekten entsprechend gedreht). Haben die Absätze verschiedene Textpositionen, bleibt die linke Kante.
- In der Höhe bleibt die obere Kante (in Leserichtung).
- **Mit fester Rahmengröße** wird der Text wie bisher in den Rahmen eingepasst.
- Ein Objekt **ohne Position** (Start-Text) bleibt mittig auf dem Etikett.

## Architektur (Ansatz A: unsichtbarer Editor als Eingabepuffer)

Das bestehende `QTextEdit` des Text-Panels (inkl. Grundformat, zeichenweiser Formatierung, Einfügen als reiner Text) bleibt **unsichtbar** als Eingabepuffer erhalten und behält im Schreibmodus den Tastaturfokus (damit funktionieren tote Tasten, Compose und Eingabemethoden). Die Arbeitsfläche zeigt weiterhin das echte Objektbild aus dem Kern und zeichnet Schreibmarke/Markierung darüber; deren Lage liefert der Kern aus **demselben** Zeilensatz wie das Rendern.

### Kern (`render.py`, Qt-frei)

- `text_layout(obj, doc, model="QL-600") -> TextLayout`: Ergebnis des Zeilensatzes, das auch das Rendern verwendet (eine Berechnung, zwei Nutzer). Enthält je Zeichen das Kästchen (x0, x1) und je Zeile Oberkante, Grundlinie, Höhe – in Druckpunkten relativ zur linken oberen Ecke des Objektrahmens **vor** der Drehung.
- `TextLayout.caret(pos) -> (x, y, h)`: Schreibmarke vor Zeichen `pos` (auch Zeilenende, leerer Absatz).
- `TextLayout.hit(x, y) -> pos`: nächste Zeichengrenze zu einem Punkt; Punkte über/unter dem Text → erste/letzte Zeile, links/rechts daneben → Zeilenanfang/-ende.
- `TextLayout.selection_rects(a, b) -> list[tuple[x, y, w, h]]`: ein Rechteck je betroffener Zeile.
- **Positionen** zählen wie im `QTextDocument`: Zeichen der Absätze hintereinander, jeder Absatzwechsel zählt als ein Zeichen.
- `layout.to_object(point, rendered, rotation)` / `layout.from_object(...)`: Umrechnung zwischen Etikettkoordinaten und ungedrehten Objektkoordinaten (0/90/180/270°).
- `layout.anchor_after_edit(old_rect, new_size, align, rotation) -> (x_mm, y_mm)`: neue Position nach dem Wachsen gemäß Abschnitt „Rahmen wächst“.

### GUI

- `gui/text_edit_mode.py`: `TextEditSession` – Start/Ende des Schreibmodus, Zuordnung Maus → Editor-Position (über `TextLayout.hit`), Synchronisation Editor-Markierung ↔ Anzeige, Abschluss als ein Verlaufsschritt, Anker-Regel beim Wachsen.
- `canvas.py`: Signale für Doppelklick/Ziehen im Schreibmodus; zeichnet Schreibmarke (blinkend), Markierung und durchgezogenen Rahmen in `drawForeground`; im Schreibmodus keine Objekt-Verschiebung im bearbeiteten Rahmen.
- `panels/text.py`: Feld INHALT entfällt aus dem Layout; der Editor bleibt als unsichtbares Kind-Widget (fokussierbar, Größe 0) bestehen.
- `shortcuts.py`: neuer Bereich `"edit"` („Schreibmodus“) für die Kürzel, die nur im Schreibmodus gelten; Esc/Enter fest. Konfliktprüfung: `edit` kollidiert nur mit `global`.

## Fehlerfälle

- Klick in einen Rahmen, dessen Text die Etikettgrenze überragt: Treffer werden trotzdem richtig zugeordnet (Objektkoordinaten, nicht Etikettkoordinaten).
- `TextTooLarge` während des Tippens (Objekt ohne Position, feste Größe): Hinweis wie bisher, Schreibmodus bleibt aktiv.

## Tests

- **Kern:** Schreibmarke an jeder Position eines gemischt formatierten Texts liegt zwischen den Tintenspalten der Nachbarzeichen im echten Druckbild; `hit(caret(p)) == p`; leerer Absatz; links/zentriert/rechts/Blocksatz; Drehung 0/90/180/270; gemischte Größen auf einer Grundlinie; `anchor_after_edit` je Ausrichtung und Drehung; Rendern unverändert (Pixelgleichheits-Tests bleiben grün).
- **GUI (offscreen):** Text-Werkzeug + Klick → Tippen landet im neuen Rahmen; Doppelklick setzt die Schreibmarke an die Klickstelle; Ziehen markiert, B macht nur die Markierung fett; Pfeile im Schreibmodus bewegen die Schreibmarke statt das Objekt; Esc beendet, eine Bearbeitung = ein Rückgängig-Schritt; Klick daneben beendet, leerer Rahmen entfällt; gedrehter Rahmen: Klick trifft richtig; Rahmen wächst an der richtigen Kante; Feld INHALT nicht sichtbar; Kürzel-Bereich „Schreibmodus“ im Einstellungsdialog.
- Jedes Widget bei `qtbot.addWidget`; Exit-Code von pytest prüfen.
