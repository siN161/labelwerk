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
labelwerk print "Max Mustermann\nMusterstr. 5\n12345 Musterstadt" --orientation horizontal -s 80
```

Optionen: `-s` Schriftgröße, `--font` eigene TTF, `-b pyusb` alternatives USB-Backend, `--no-cut`.
`print-file` schneidet auf den Inhalt zu (Schnittmarken, z. B. der Internetmarke, und Leerraum fallen weg), dreht bei Bedarf und druckt 1:1; `--rotate 0|90|180|270` legt die Drehung fest (Grad im Uhrzeigersinn), `--fit` verkleinert zu große Motive, `--page N` wählt die PDF-Seite. Internetmarke quer wie im PDF: `--rotate 0 --fit`.

## Grafische Oberfläche

```bash
pip install -e ".[gui]"
labelwerk-gui
labelwerk install-desktop    # im Starter (Super-Taste) eintragen; --remove entfernt den Eintrag wieder
```

Aufbau wie im P-touch Editor: Werkzeugleiste (Papier, Text), Eigenschaften links, Etikett in echter Größe und Form mit mm-Linealen. Bei Endlosband lässt sich die Länge am Anfasser unter dem Etikett ziehen (Doppelklick = automatisch). Zoom mit Strg+Mausrad oder −/+ unten rechts.

Papier: Etikett, Länge, Ränder und Ausrichtung (Horizontal = Text längs zum Band, z. B. Versandetikett; Vertikal = quer). „Medium prüfen“ liest die eingelegte Rolle vom Drucker und wählt das passende Etikett. Der Drucker wird live erkannt (Einschalten genügt). Unter „Einstellungen“ legst du Standardwerte für neue Etiketten fest (gilt auch für die CLI); gespeichert in `~/.config/labelwerk/settings.json`.

## Architektur

```
render.py   Inhalt → Bild in exakter Druckbreite (300 dpi)
files.py    PDF/Bild → zugeschnitten, 1:1 aufs Etikett gesetzt
labels.py   Etikettentypen je Modell
printer.py  Bild → Brother-Rasterdaten → Drucker (via brother_ql)
cli.py      Kommandozeile
document.py Etikett-Dokument (Etikett, Länge, Objekte)
settings.py Einstellungen (JSON)
media.py    Medium prüfen (Statusabfrage des Druckers)
gui/        PySide6-Oberfläche (nur Anzeige/Bearbeitung, kein Druckcode)
```

Die Kernlogik ist UI-unabhängig – eine GUI setzt nur auf `render`, `files`, `labels`, `printer` und `detect` auf.

## Lizenz

GPL-3.0-or-later (abhängig von [brother_ql-inventree](https://github.com/matmair/brother_ql-inventree), GPLv3+).
