# labelwerk – Projektkontext für Claude Code

## Ziel
Open-Source-Software (GPL-3.0-or-later), um auf **Brother-QL-Etikettendruckern unter Linux** Etiketten zu gestalten und zu drucken – als Ersatz für den Windows-only P-touch Editor. Später öffentlich auf GitHub, aktuell **privates Repo**.

Primäre Hardware: **Brother QL-600G** (USB, `04f9:20c0`), Rolle **DK-22205 (62 mm endlos, `-l 62`)**.

## Stand (funktioniert)
- CLI druckt erfolgreich auf dem QL-600 (verifiziert mit `-l 62`).
- `labelwerk print-file` druckt PDF/PNG/JPG 1:1 (z. B. Internetmarke auf `-l 62`).
- Druckererkennung automatisch über `/sys/class/usbmisc/lp*` (Vendor-ID `04f9`), Gerät liegt aktuell auf `/dev/usb/lp1`.
- 67 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).

## Architektur
```
src/labelwerk/
  labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager);
              filtert für QL-600: >62 mm, PT-Bänder, Rot/Schwarz-Etiketten
  render.py   render_text(text, label_id, font_size, font_path) -> PIL.Image
              exakte Druckbreite @300 dpi, Schrift schrumpft automatisch, mehrzeilig zentriert
  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
              crop(img) -> auf Schnittmarken bzw. Inhalt; fit_to_label(img, label_id, fit) -> 1:1, ggf. gedreht
  printer.py  build_instructions(image, label_id, model) -> bytes (Brother-Raster)
              print_image(...) -> status-dict von brother_ql.backends.helpers.send
  detect.py   find_brother_lp() -> "file:///dev/usb/lpN" | None
  cli.py      labelwerk labels | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] | labelwerk print-file DATEI -l 62 [--fit] [--page N]
```
Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `detect` auf – keine Drucklogik in der UI.

Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`), `pillow>=10`, `pypdfium2>=4`. Build: hatchling, src-Layout.

## Konventionen
- **TDD**: erst fehlschlagenden Test schreiben, dann implementieren. Tests laufen **ohne Drucker** (Rasterdaten prüfen, sysfs per `tmp_path` faken, Druckfunktionen per `monkeypatch` ersetzen). Kein Test darf echte Hardware ansprechen.
- Benutzer-Meldungen und Kommentare auf Deutsch (vor Veröffentlichung ggf. auf Englisch umstellen).
- Fehler für Nutzer verständlich abfangen, keine Tracebacks (Exit-Code 2 bei Hardware-/Rechteproblemen).

## Hardware-Wissen (hart erarbeitet)
- QL-600: **Editor-Lite-LED muss aus sein**, sonst meldet er sich als USB-Massenspeicher.
- Benutzer braucht Gruppe `lp` für `/dev/usb/lpN` (`crw-rw---- root lp`). Erledigt.
- `Replace media error` = angefordertes Etikett passt nicht zur eingelegten Rolle (Drucker erkennt die DK-Rolle per Sensor).
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

## Nächstes Ziel: GUI (MVP)
Desktop-GUI mit **PySide6** (LGPL, GPL-kompatibel).

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
1. Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)
2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → `-l` optional, Vorauswahl in der GUI
3. Barcodes und QR-Codes
4. Vorlagen (YAML/JSON) und Serien aus CSV/Excel (.xlsx) (z. B. Klemmen-/Betriebsmittelkennzeichnung)
5. Importe:
   - Bilder (PNG/JPG/SVG) als Objekt aufs Etikett, Umwandlung in Schwarz/Weiß
   - Fertiges Bild/PDF 1:1 drucken, ohne Editor (auch per CLI)
   - P-touch-Etiketten (.lbx = ZIP mit XML): Text, Rahmen, Barcodes, Bilder übernehmen
6. Paketierung: AppImage und/oder Flatpak (USB-Zugriff bei Flatpak beachten)
7. Vor Veröffentlichung: README/Kommentare auf Englisch, LICENSE (GPLv3) prüfen, Repo öffentlich schalten
