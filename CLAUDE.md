# labelwerk – Projektkontext für Claude Code

## Ziel
Open-Source-Software (GPL-3.0-or-later), um auf **Brother-QL-Etikettendruckern unter Linux** Etiketten zu gestalten und zu drucken – als Ersatz für den Windows-only P-touch Editor. Später öffentlich auf GitHub, aktuell **privates Repo**.

Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62 mm endlos, `-l 62`)**.

## Stand (funktioniert)
- CLI druckt erfolgreich auf dem QL-600 (verifiziert mit `-l 62`).
- `labelwerk print-file` druckt PDF/PNG/JPG 1:1 (z. B. Internetmarke auf `-l 62`).
- Druckererkennung automatisch über `/sys/class/usbmisc/lp*` (Vendor-ID `04f9`), Gerät liegt aktuell auf `/dev/usb/lp1`.
- GUI-MVP: `labelwerk-gui` (Papier/Text, Live-Vorschau, Etikettform, Länge ziehen, Drucken im Hintergrund).
- `labelwerk install-desktop` trägt die GUI mit Icon im Starter ein (XDG, `~/.local/share`); App-ID `labelwerk`.
- Papier: Ausrichtung H/V, Ränder, Medium prüfen (GUI + `labelwerk media`), Einstellungen (`settings.json`, GUI-Dialog), Live-Druckererkennung.
- 204 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).

## Architektur
```
src/labelwerk/
  labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager);
              filtert für QL-600: >62 mm, PT-Bänder, Rot/Schwarz-Etiketten
  render.py   render_text(text, label_id, font_size, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
              exakte Druckbreite @300 dpi, Schrift schrumpft automatisch, mehrzeilig zentriert
  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
              crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
  printer.py  build_instructions(image, label_id, model) -> bytes (Brother-Raster)
              print_image(...) -> status-dict von brother_ql.backends.helpers.send
  detect.py   find_brother_lp() -> "file:///dev/usb/lpN" | None
  document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig
  settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings)
  media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
  desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
  gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
    main_window.py  Hauptfenster, Werkzeugleiste, Statusleiste
    tools.py        Werkzeug-Registry (Papier, Text; neue Werkzeuge als Eintrag)
    panels/         Eigenschaften-Panels je Werkzeug (paper, text)
    canvas.py       Etikett in echter Größe, Lineale, Zug-Anfasser, Zoom
    print_worker.py Drucken im Hintergrund-Thread
    media_worker.py  Medium prüfen im Hintergrund
    settings_dialog.py Einstellungen
    theme/          QSS-Stylesheet (rawblock.qss)
    icons/          labelwerk.svg (Platzhalter; eigenes Logo: SVG Tiny, quadratisch, Text als Pfade, ab 16 px erkennbar)
  cli.py      labelwerk labels | labelwerk media | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
```
Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.

Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`), `pillow>=10`, `pypdfium2>=4`. Build: hatchling, src-Layout.

## Konventionen
- **TDD**: erst fehlschlagenden Test schreiben, dann implementieren. Tests laufen **ohne Drucker** (Rasterdaten prüfen, sysfs per `tmp_path` faken, Druckfunktionen per `monkeypatch` ersetzen). Kein Test darf echte Hardware ansprechen.
- Benutzer-Meldungen und Kommentare auf Deutsch (vor Veröffentlichung ggf. auf Englisch umstellen).
- Fehler für Nutzer verständlich abfangen, keine Tracebacks (Exit-Code 2 bei Hardware-/Rechteproblemen).

## Hardware-Wissen (hart erarbeitet)
- QL-600: **Editor-Lite-LED muss aus sein**, sonst meldet er sich als USB-Massenspeicher.
- Läuft die Windows-VM mit USB-Durchreichung, belegt sie den Drucker (Interface-Treiber `usbfs` statt `usblp`, kein `/dev/usb/lp*`). labelwerk erkennt das (`detect.brother_busy`) und meldet es. Abhilfe: in der VM freigeben, Drucker aus/an.
- Gruppe `lp` gilt erst nach neuer Anmeldung; bis dahin im Terminal `newgrp lp`.
- Benutzer braucht Gruppe `lp` für `/dev/usb/lpN` (`crw-rw---- root lp`). Erledigt.
- `Replace media error` = angefordertes Etikett passt nicht zur eingelegten Rolle (Drucker erkennt die DK-Rolle per Sensor).
- Statusabfrage (Medium prüfen): Invalidate (200 × 0x00) + ESC @ + ESC i S, Antwort 32 Bytes sofort; brother_ql-Lesen nicht verwenden (kann ohne Zeitlimit blockieren).
- Backends: `linux_kernel` (Standard, `/dev/usb/lpN`), `pyusb` (`usb://0x04f9:0x20c0`), `network`.

## Entwicklung
```bash
cd ~/ql-label/labelwerk
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
labelwerk print "X1 -K3\nKlemme 24V" -l 62 --preview vorschau.png
labelwerk print "X1 -K3\nKlemme 24V" -l 62
```

## GUI (MVP umgesetzt)
Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).

Nächste Schritte: Etappe 2 (Roadmap 0) bzw. Werkzeug ‚Bild‘ (Roadmap 5) als neuer Eintrag in `gui/tools.py`.

Anforderungen MVP:
- Mehrzeiliges Textfeld
- Etikett-Auswahl (Dropdown aus `labels_for_model("QL-600")`, Standard `62`)
- Schriftgröße: „automatisch“ oder fester Wert
- **Live-Vorschau** (PIL-Image → QPixmap), aktualisiert beim Tippen
- Druck-Button; Druck läuft in einem Worker-Thread (`QThread`/`QThreadPool`), UI darf nicht blockieren
- Statusleiste: erkannter Drucker (`find_brother_lp`), Druckergebnis, verständliche Fehler (kein Drucker, keine Rechte, falsche Rolle)

Umsetzung:
- Paket `src/labelwerk/gui/`, Einstiegspunkt `labelwerk-gui` in `pyproject.toml`
- PySide6 als optionale Abhängigkeit `[gui]`, damit die CLI schlank bleibt
- Tests mit `pytest-qt` (in `[dev]` aufnehmen); CI braucht `QT_QPA_PLATFORM=offscreen`
- GUI bleibt dünn: Logik, die testbar ist, gehört in den Kern

## Roadmap danach
0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart (P-touch-Vorlagen recherchieren) · 3 Funktionsliste P-touch → labelwerk (Text-Formatierung, Rahmen, Bild, Favoriten, Layout/freies Platzieren, Speichern/Neu).
1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
3. Barcodes und QR-Codes
4. Vorlagen (YAML/JSON) und Serien aus CSV/Excel (.xlsx) (z. B. Klemmen-/Betriebsmittelkennzeichnung)
5. Importe:
   - Bilder (PNG/JPG/SVG) als Objekt aufs Etikett, Umwandlung in Schwarz/Weiß
   - Fertiges Bild/PDF 1:1 drucken, ohne Editor (auch per CLI)
   - P-touch-Etiketten (.lbx = ZIP mit XML): Text, Rahmen, Barcodes, Bilder übernehmen
6. Paketierung: AppImage und/oder Flatpak (USB-Zugriff bei Flatpak beachten)
7. Vor Veröffentlichung: README/Kommentare auf Englisch, LICENSE (GPLv3) prüfen, Repo öffentlich schalten.
   **Namen vorher festlegen** (danach teuer: PyPI-Name, Flatpak-ID `io.github.siN161.<name>`, Repo-Links). Kein „Brother“/„P-touch“/„QL“ im Produktnamen.
   Umbenennen – Checkliste:
   - Nur Anzeigename: `APP_NAME` in `src/labelwerk/desktop.py` (Fenster, Starter, CLI-Hilfe).
   - Technischer Name: `APP_ID` (desktop.py), Paketordner `src/labelwerk/` + alle Importe (`git grep labelwerk`), `pyproject.toml` (`name`, `[project.scripts]`, `packages`), Icon-Dateiname `gui/icons/<id>.svg`, README/CLAUDE.md, GitHub-Repo.
   - Danach: alten Starter mit `labelwerk install-desktop --remove` entfernen, neu installieren (`pip install -e ".[gui]"`, `<name> install-desktop`).
