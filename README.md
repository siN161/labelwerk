# labelwerk

Etiketten gestalten und drucken auf **Brother-QL-Druckern unter Linux** – ohne P-touch Editor, ohne Wine.

Getestet mit: QL-600 (USB). Andere QL-Modelle sollten funktionieren, Rückmeldungen willkommen.

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

## Benutzung

```bash
labelwerk labels                                   # verfügbare Etiketten
labelwerk print "X1 -K3\nKlemme 24V" -l 62x29 --preview vorschau.png
labelwerk print "X1 -K3\nKlemme 24V" -l 62x29      # drucken (Drucker wird automatisch erkannt)
labelwerk print-file internetmarke.pdf -l 62       # PDF/PNG/JPG 1:1 drucken
labelwerk media                                            # eingelegte Rolle anzeigen (druckt nichts)
labelwerk fonts                                            # installierte Schriften
labelwerk print "Max Mustermann\nMusterstr. 5" --align left --font-family "Liberation Sans" -s 14
labelwerk print "Max Mustermann\nMusterstr. 5\n12345 Musterstadt" --orientation horizontal -s 19
```

Optionen: `-s` Schriftgröße (`auto` oder 8–400), `--font` eigene TTF, `-b pyusb` alternatives USB-Backend, `--no-cut`.
`print-file` schneidet auf den Inhalt zu (Schnittmarken, z. B. der Internetmarke, und Leerraum fallen weg), dreht bei Bedarf und druckt 1:1; `--rotate 0|90|180|270` legt die Drehung fest (Grad im Uhrzeigersinn), `--fit` verkleinert zu große Motive, `--page N` wählt die PDF-Seite. Internetmarke quer wie im PDF: `--rotate 0 --fit`.

## Grafische Oberfläche

```bash
pip install -e ".[gui]"
labelwerk-gui
labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entfernt den Eintrag wieder
```

Aufbau wie im P-touch Editor: Werkzeugleiste (Papier, Text, Layout), Bearbeitungsleiste, Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.

Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI) und wählst das Design (RawBlock oder Klassisch = Qt-Systemstil); gespeichert in `~/.config/labelwerk/settings.json`.

Text: Schriftart, Größe (pt), fett/kursiv/unterstrichen und Textposition – zeichenweise wie im P-touch Editor. Ohne Markierung gilt die Formatierung für den ganzen Text. „Feste Rahmengröße“ skaliert den Text passend in den Rahmen. Unter „Position“ stehen X, Y, Breite und Höhe in mm.

Freies Platzieren: Mehrere Textrahmen pro Etikett. Mit „A“ in der Bearbeitungsleiste (oder im Reiter „Text“ ohne Auswahl) und einem Klick aufs Etikett einen Rahmen anlegen – bleibt er leer, verschwindet er wieder, sobald man etwas anderes wählt. Klick wählt, Strg+Klick ergänzt. Ziehen verschiebt (rastet an Kanten und Mitten ein, Alt hält das Einrasten aus; Lage und Größe landen auf 0,1 mm wie in den Feldern), Ecken skalieren die Schrift, Kanten ändern den Rahmen. Pfeiltasten verschieben um 0,1 mm (mit Umschalt 1 mm). Die Bearbeitungsleiste bietet Ausschneiden, Kopieren, Einfügen, Rückgängig und Wiederherstellen. Der Reiter „Layout“ richtet aus (aneinander oder am Papier), gleicht Größen an, dreht um 90° und ändert die Reihenfolge. Ragt ein Objekt über das Etikett, fragt „Drucken“ nach.

Tastenkürzel (Standard):

| Kürzel | Aktion |
|---|---|
| Strg+P · Strg+, | Drucken · Einstellungen |
| Strg+Z · Strg+Umschalt+Z | Rückgängig · Wiederherstellen |
| Strg++ · Strg+− · Strg+0 | Zoom größer · kleiner · echte Größe |
| T · Esc | Werkzeug „Text anlegen“ · Auswahl-Pfeil (Arbeitsfläche) |
| Strg+X/C/V · Strg+D · Entf · Strg+A | Ausschneiden/Kopieren/Einfügen · Duplizieren · Löschen · alles wählen |
| Pfeiltasten · Umschalt+Pfeiltasten | verschieben um 0,1 mm · 1 mm |
| Strg+L · Strg+R | 90° nach links · rechts drehen |
| Strg+Bild↑ · Strg+Bild↓ | nach vorne · nach hinten |
| Strg+B/I/U | fett/kursiv/unterstrichen (im Textfeld) |

Ausrichten, Größe angleichen und Maximieren haben ab Werk kein Kürzel. Alle Kürzel lassen sich unter „Einstellungen“ → „Tastenkürzel“ ändern (Zeile anklicken, neue Kombination drücken; Esc, Enter und Tab sind nicht belegbar). Doppelt belegte Kürzel werden rot markiert und sperren das Speichern; stehen in einer von Hand bearbeiteten `settings.json` doppelte, behält die erste Aktion ihr Kürzel und die Statusleiste meldet es.

## Architektur

```
render.py   Inhalt → Bild in exakter Druckbreite (300 dpi)
files.py    PDF/Bild → zugeschnitten, 1:1 aufs Etikett gesetzt
labels.py   Etikettentypen je Modell
printer.py  Bild → Brother-Rasterdaten → Drucker (via brother_ql)
cli.py      Kommandozeile
document.py Etikett-Dokument (Etikett, Länge, Objekte)
settings.py Einstellungen (JSON)
fonts.py    Schriften (fontconfig)
media.py    Medium prüfen (Statusabfrage des Druckers)
layout.py   Platzieren: Einrasten, Ausrichten, Größe angleichen, ragt hinaus
shortcuts.py Tastenkürzel-Verzeichnis (Standard, Konflikte, Prüfung)
gui/        PySide6-Oberfläche (nur Anzeige/Bearbeitung, kein Druckcode)
```

Die Kernlogik ist UI-unabhängig – eine GUI setzt nur auf `render`, `files`, `labels`, `printer` und `detect` auf.

## Lizenz

GPL-3.0-or-later (abhängig von [brother_ql-inventree](https://github.com/matmair/brother_ql-inventree), GPLv3+).
