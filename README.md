# labelwerk

Etiketten gestalten und drucken auf **Brother-QL-Druckern unter Linux** – ohne P-touch Editor, ohne Wine.

Getestet mit: QL-600 (USB). Andere QL-Modelle sollten funktionieren, Rückmeldungen willkommen.

## Welche Drucker funktionieren?

| Stand | Drucker |
|---|---|
| **geprüft** | QL-600 mit DK-22205 (62 mm endlos), USB |
| **sollte funktionieren** (ungeprüft) | QL-500, QL-550, QL-560, QL-570, QL-580N, QL-650TD, QL-700, QL-710W, QL-720NW, QL-800, QL-810W, QL-820NWB – Etiketten bis 62 mm, USB oder Netzwerk |
| **sollte funktionieren** (ungeprüft) | breite Modelle QL-1050, QL-1060N, QL-1100, QL-1110NWB, QL-1115NWB – Etiketten bis 102/104 mm |
| **ungeprüft** | Rot/Schwarz-Druck (QL-8xx mit DK-22251 „62red“): Farbe je Objekt im Reiter Layout |
| **ungeprüft** | Zebra-Etikettendrucker direkt in ZPL (USB oder Netzwerk, 203/300/600 dpi, feste Etiketten) |
| **ungeprüft** | jeder in CUPS eingerichtete Etikettendrucker (z. B. Dymo LabelWriter): Etiketten und Auflösung aus dem Treiber |
| **nicht unterstützt** | P-touch-Bandgeräte (PT-…), Bluetooth-Drucker (Niimbot, Phomemo), Endlosband bei anderen Herstellern |

labelwerk erkennt das Modell des angeschlossenen Druckers selbst (`labelwerk printers` zeigt, was es
findet); Etiketten, Abschneider und Farben richten sich danach. Wird ein Modell nicht erkannt, lässt
es sich in den Einstellungen festlegen. Netzwerkdrucker (WLAN/LAN-Modelle) trägst du in den
Einstellungen mit IP-Adresse ein; „Medium prüfen“ geht nur per USB. Hast du ein ungeprüftes Modell
ausprobiert, freue ich mich über eine Rückmeldung (Issue mit Modell, Rolle und Ergebnis).

**Andere Hersteller:** Zebra-Drucker am USB erkennt labelwerk selbst (Auflösung aus der Kennung des
Druckers, sonst 203 dpi); Netzwerk-Zebras trägst du in den Einstellungen mit Modell „Zebra (ZPL)“ und
Auflösung ein. Drucker, die in der Druckerverwaltung des Systems (CUPS) eingerichtet sind, stehen im
Druckermenü als „Name · CUPS“ – sie werden nie automatisch gewählt. Bürodrucker (Standardpapier A4,
Letter …) blendet labelwerk dort aus; Einstellungen → Drucker → „Alle CUPS-Drucker zeigen“ holt sie zurück
(ein gewählter bleibt immer sichtbar).
Gedruckt wird in der echten Auflösung des Druckers, damit Barcodes scharf bleiben. Schneiden stellst du
im Reiter SERIE ein: bei CUPS die Schnitt-Optionen des Treibers, bei Zebra Abreißen/Schneiden/Ablösen.
Grenzen: Der Treiber kann einen unbedruckbaren Rand haben (Rand im Reiter PAPIER vergrößern), „Medium
prüfen“ und Abbrechen gibt es nur bei Brother per USB.

## Installation

```bash
git clone https://github.com/siN161/labelwerk.git
cd labelwerk
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Drucker-Zugriff ohne root (danach neu einloggen):

```bash
sudo usermod -aG lp "$USER"
```

Beim QL-600 muss die **Editor-Lite-LED aus** sein, sonst meldet er sich als USB-Speicher.

## Sprachen

labelwerk spricht Deutsch und Englisch (Oberfläche, Kommandozeile, Meldungen) und nimmt die Sprache des
Systems; umstellen in Einstellungen → Ansicht → Sprache (wirkt nach einem Neustart) bzw. mit
`labelwerk --lang en …`. Weitere Sprachen sind willkommen – Anleitung in
`src/labelwerk/po/README.md`.

## Benutzung

```bash
labelwerk labels                                   # verfügbare Etiketten
labelwerk print "X1 -K3\nKlemme 24V" -l 62x29 --preview vorschau.png
labelwerk print "X1 -K3\nKlemme 24V" -l 62x29      # drucken (Drucker wird automatisch erkannt)
labelwerk print-file internetmarke.pdf -l 62       # PDF/PNG/JPG 1:1 drucken
labelwerk media                                            # eingelegte Rolle anzeigen (druckt nichts)
labelwerk printers                                         # gefundene Drucker und unterstützte Modelle
labelwerk printers --all                                   # auch CUPS-Bürodrucker
labelwerk print "Regal 4" -l auto                          # Etikett nach der eingelegten Rolle
labelwerk fonts                                            # Schriften mit deutschen Zeichen
labelwerk fonts --all                                      # alle (auch Kopien, Symbolschriften)
labelwerk print "Max Mustermann\nMusterstr. 5" --align left --font-family "Liberation Sans" -s 14
labelwerk print "Max Mustermann\nMusterstr. 5\n12345 Musterstadt" --orientation horizontal -s 19
```

Optionen: `-s` Schriftgröße (`auto` oder 8–400), `--font` eigene TTF, `-m QL-700` Modell (Standard: erkannt), `-p tcp://IP` Netzwerkdrucker, `-b pyusb` alternatives USB-Backend, `--no-cut`.
Andere Hersteller: `-p cups:NAME` (Warteschlange, Etiketten mit `labelwerk -m cups:NAME labels`), Zebra `-p zpl+file:///dev/usb/lp2` bzw. `-p zpl+tcp://IP` mit `-m zpl:203|300|600`; Etiketten heißen dort `57x32mm@203` (Breite × Höhe @ dpi).
`print-file` schneidet auf den Inhalt zu (Schnittmarken, z. B. der Internetmarke, und Leerraum fallen weg), dreht bei Bedarf und druckt 1:1; `--rotate 0|90|180|270` legt die Drehung fest (Grad im Uhrzeigersinn), `--fit` verkleinert zu große Motive, `--page N` wählt die PDF-Seite. Internetmarke quer wie im PDF: `--rotate 0 --fit`.

## Grafische Oberfläche

```bash
pip install -e ".[gui]"
labelwerk-gui
labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entfernt den Eintrag wieder
```

Aufbau wie im P-touch Editor: Werkzeugleiste (Datei, Papier, Text, Bild, Barcode, Layout, Serie), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Unten links steht der Drucker: ein Klick wählt einen anderen (bei mehreren) oder trägt einen Netzwerkdrucker ein; während eine Serie vorbereitet oder gedruckt wird, bricht ABBRECHEN sie ab (beim Drucken nach dem laufenden Teil, bis zu 10 Etiketten). Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.

Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). Der Rand zählt ab Papierkante: Die Streifen, die der Drucker ohnehin freilässt (quer ~1,5 mm, längs zum Endlosband ~3 mm), zählen mit und sind auf der Arbeitsfläche hellgrau. Die Lineale zählen ab Papierkante, die Felder unter „Position“ ab dem bedruckbaren Bereich. Die Länge eines Endlosband-Etiketts ist das abgeschnittene Stück (Dateien älterer Versionen drucken dadurch ~6 mm kürzer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil), den Reiter beim Start (fest oder „Zuletzt benutzter“) und den Standard für neue Bilder (Strich/Foto, Schwelle); gespeichert in `~/.config/labelwerk/settings.json`.

Text: Geschrieben wird direkt auf dem Etikett. Mit dem Knopf „A“ (Text anlegen, Taste T) und einem Klick entsteht ein Rahmen, in den man sofort tippt (linksbündig ab dem Klickpunkt); ein Doppelklick auf einen Text setzt die Schreibmarke an die Klickstelle (ein einfacher Klick wählt den Rahmen nur); bei gewähltem Rahmen startet **F2** oder **Enter** den Schreibmodus mit der Schreibmarke am Textende. Im Schreibmodus markiert Ziehen Text, Doppelklick ein Wort, Umschalt+Klick erweitert; Pfeiltasten, Pos1/Ende, Entf, Enter, Strg+A/C/X/V und Strg+Z wirken auf den Text. **Esc** oder ein Klick neben den Rahmen beendet den Schreibmodus – die ganze Bearbeitung ist dann ein Schritt für Rückgängig. Ohne feste Rahmengröße wächst der Rahmen beim Tippen an der Kante seiner Textposition (links, rechts, Mitte). Die Schriftauswahl zeigt jede Schrift in ihrer Schrift und nur Schriften mit deutschen Zeichen, ohne Kopien und Symbolschriften (Einstellungen → „Alle Schriften zeigen“ zeigt alle); eine Schrift aus einer Datei, die dort fehlt, bleibt sichtbar. Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition wirken zeichenweise wie im P-touch Editor: im Schreibmodus auf die Markierung bzw. das Weitertippen, sonst auf den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.

Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste (oder im Reiter „Text“ ohne Auswahl) und einem Klick aufs Etikett einen Rahmen anlegen – bleibt er leer, verschwindet er wieder, sobald man den Schreibmodus verlässt. Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus; Lage und Größe landen auf 0,1 mm wie in den Feldern), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.

Bild: Im Reiter „Bild“ fügt „Aus Datei …“ (Strg+Umschalt+I) PNG, JPG, GIF, BMP, WebP, SVG oder eine PDF-Seite ein (bei mehreren Seiten fragt ein Dialog nach der Seite), „Aus Zwischenablage“ ein kopiertes Bild. Bilddateien und Bilder lassen sich auch aufs Etikett ziehen (landen an der Ablagestelle). Strg+V auf der Arbeitsfläche fügt ein, was die Zwischenablage oben hat: in labelwerk kopierte Objekte, sonst kopierte Bilddateien (Dateimanager), sonst Text als neuen Textrahmen (auch wenn ein Bild dabei ist, etwa bei Tabellenzellen – das Bild fügt „Aus Zwischenablage“ ein), sonst ein Bild. Bilder kommen in Originalgröße 1:1 (aus der Auflösung der Datei, sonst 300 dpi) und automatisch zugeschnitten (Schnittmarken und weißer Rand fallen weg – z. B. bei der Internetmarke); zu große werden proportional eingepasst, die Statusleiste nennt den Faktor (Codes ggf. nicht mehr lesbar). Das Panel stellt die Umwandlung in Schwarz/Weiß ein: Strich (harte Schwelle – Codes, Schrift, Logos) oder Foto (Rasterpunkte), Schwelle (höher = mehr Schwarz), Umkehren; dazu Zuschnitt an/aus, Originalgröße 1:1 und Seitenverhältnis beibehalten (dann halten auch die Kanten-Anfasser das Verhältnis). Bilder lassen sich verschieben, skalieren, drehen, ausrichten, kopieren und rückgängig machen wie Text; ein Doppelklick auf ein Bild startet keinen Schreibmodus.

Barcode: Im Reiter „Barcode“ wählst du die Art (QR-Code, Code 128, Code 39, EAN-13, EAN-8) und fügst mit „Barcode einfügen“ einen Code mit Beispielinhalt ein – den Inhalt tippst du gleich darüber (jede Eingabe sofort auf dem Etikett). Gezeichnet wird in ganzen Druckpunkten, damit der Code bei 300 dpi lesbar bleibt: „Modul“ ist die Breite des schmalsten Strichs bzw. eines QR-Quadrats, Anfasser und Felder rasten darauf ein; Strichcodes haben dazu Höhe und Klartext, QR-Codes die Fehlerkorrektur (L/M/Q/H). Falscher Inhalt (z. B. Buchstaben im EAN) steht als Hinweis im Panel, der Barcode erscheint schraffiert (bleibt wählbar) und das Etikett wird nicht gedruckt; bei EAN mit 12 bzw. 7 Ziffern wird die Prüfziffer ergänzt. In einer Serie geht `{Spalte}` auch im Inhalt (Doppelklick auf die Spalte ersetzt den Beispielinhalt). Lass um den Code die angezeigte Ruhezone frei.

Tastenkürzel (Standard):

| Kürzel | Aktion |
|---|---|
| Strg+P · Strg+, | Drucken · Einstellungen |
| Strg+Z · Strg+Umschalt+Z | Rückgängig · Wiederherstellen |
| Strg++ · Strg+− · Strg+0 | Zoom größer · kleiner · echte Größe |
| T · Esc | Werkzeug „Text anlegen“ · Auswahl-Pfeil (Arbeitsfläche) |
| Strg+Umschalt+I | Bild einfügen … (Arbeitsfläche) |
| F2 · Enter | Schreibmodus für den gewählten Text starten (Arbeitsfläche) |
| Strg+X/C/V · Strg+D · Entf · Strg+A | Ausschneiden/Kopieren/Einfügen (Objekte, Bild oder Text) · Duplizieren · Löschen · alles wählen |
| Pfeiltasten · Umschalt+Pfeiltasten | verschieben um 0,1 mm · 1 mm |
| Strg+L · Strg+R | 90° nach links · rechts drehen |
| Strg+Bild↑ · Strg+Bild↓ | nach vorne · nach hinten |
| Strg+B/I/U · Esc | fett/kursiv/unterstrichen · Schreibmodus beenden (im Schreibmodus) |

Ausrichten, Größe angleichen und Maximieren haben ab Werk kein Kürzel. Im Schreibmodus gelten die Tasten des Texts statt der Objekt-Kürzel (Pfeile bewegen die Schreibmarke, Entf löscht Zeichen); Esc zum Beenden ist fest. Alle Kürzel lassen sich unter „Einstellungen“ → „Tastenkürzel“ ändern (Zeile anklicken, neue Kombination drücken; Esc, Enter und Tab sind nicht belegbar). Doppelt belegte Kürzel werden rot markiert und sperren das Speichern; stehen in einer von Hand bearbeiteten `settings.json` doppelte, behält die erste Aktion ihr Kürzel und die Statusleiste meldet es.

## Architektur

```
render.py   Inhalt → Bild in exakter Druckbreite (Auflösung des Etiketts: Brother 300 dpi)
files.py    PDF/Bild → zugeschnitten, 1:1 aufs Etikett gesetzt
labels.py   Etikettentypen je Modell, Etiketten anderer Drucker „BxHmm@dpi“
printer.py  Bild → Brother-Rasterdaten → Drucker (via brother_ql)
printers.py Drucker erkennen (Modell), Fähigkeiten je Modell, Netzwerkdrucker
cups.py     CUPS-Warteschlangen (lpstat/lpoptions/lp): Etiketten aus dem Treiber, Druck als PDF
zpl.py      Zebra direkt: Bild → ZPL (^GFA, komprimiert), Senden an USB/TCP
cli.py      Kommandozeile
document.py Etikett-Dokument (Etikett, Länge, Objekte)
settings.py Einstellungen (JSON)
fonts.py    Schriften (fontconfig)
media.py    Medium prüfen (Statusabfrage des Druckers)
imaging.py  Bilder: Schwarz/Weiß-Umwandlung (Strich/Foto), Größe begrenzen
barcodes.py Barcodes: Code 128/39, EAN-13/8 (eigene Kodierung), QR (segno), in ganzen Druckpunkten
layout.py   Platzieren: Einrasten, Ausrichten, Größe angleichen, ragt hinaus
shortcuts.py Tastenkürzel-Verzeichnis (Standard, Konflikte, Prüfung)
gui/        PySide6-Oberfläche (nur Anzeige/Bearbeitung, kein Druckcode)
```

Die Kernlogik ist UI-unabhängig – eine GUI setzt nur auf `render`, `files`, `labels`, `printer`, `printers`, `detect`, `settings` und `media` auf.

## Lizenz

GPL-3.0-or-later (abhängig von [brother_ql-inventree](https://github.com/matmair/brother_ql-inventree), GPLv3+;
QR-Codes mit [segno](https://github.com/heuer/segno), BSD-3-Clause).
