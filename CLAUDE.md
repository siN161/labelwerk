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
- Text-Formatierung zeichenweise (GUI-Editor wie P-touch, CLI --align/--font-family/--bold/--italic/--underline, labelwerk fonts), Größen in pt.
- Freies Platzieren (Etappe 3d-1): mehrere Objekte, Auswahl, Ziehen mit Einrasten, Anfasser, Bearbeitungsleiste, Reiter Layout, Drehen, Reihenfolge, Zwischenablage, Rückgängig, Tastenkürzel änderbar (Einstellungen → Tastenkürzel).
- 811 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).

## Architektur
```
src/labelwerk/
  labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager);
              filtert für QL-600: >62 mm, PT-Bänder, Rot/Schwarz-Etiketten
  render.py   render_text(text, label_id, size_pt, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
              render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
              compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise für die GUI:
              prepare_object, label_size(prepared=), finish_object (nur Geändertes neu); span_dots
              Zeilensatz mit gemeinsamer Grundlinie (pixelgleich zu Pillow multiline_text für reinen Text), font_warnings(doc)
              exakte Druckbreite @300 dpi, Schrift schrumpft automatisch, mehrzeilig zentriert
  fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei
  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
              crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
  printer.py  build_instructions(image, label_id, model) -> bytes (Brother-Raster)
              print_image(...) -> status-dict von brother_ql.backends.helpers.send
  detect.py   find_brother_lp() -> "file:///dev/usb/lpN" | None
  document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit);
              TextObject: Position x_mm/y_mm (None = mittig wie bisher), Rahmen w_mm/h_mm (mit fit), Drehen rotation 0/90/180/270
  settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic)
  media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
  layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
              growing_axis (Endlosband wächst mit), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
  shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich), effective, conflicts, without_conflicts, validate
  desktop.py  .desktop-Eintrag + Icon installieren/entfernen (XDG_DATA_HOME), APP_ID
  gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
    main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
                    shortcut_actions (Aktions-ID → QAction); Render-Cache je Objekt; leere Textrahmen entfallen beim Abwählen
    tools.py        Werkzeug-Registry (Papier, Text, Layout; neue Werkzeuge als Eintrag)
    panels/         Eigenschaften-Panels je Werkzeug (paper, text mit Bereich Position)
    panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
    canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom
    actions.py      QActions aus shortcuts.ACTIONS – jedes Kürzel der App läuft hierüber (apply_shortcuts)
    history.py      Rückgängig/Wiederherstellen: Dokument-Schnappschüsse samt Auswahl, höchstens 100; amend (ohne eigenen Schritt)
    symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
    print_worker.py Drucken im Hintergrund-Thread
    media_worker.py  Medium prüfen im Hintergrund
    settings_dialog.py Einstellungen: Reiter Allgemein (inkl. Design, sofort wirksam über app.apply_theme) und Tastenkürzel (Konflikte sperren Speichern)
    theme/          QSS-Stylesheet (rawblock.qss)
    icons/          labelwerk.svg (Platzhalter; eigenes Logo: SVG Tiny, quadratisch, Text als Pfade, ab 16 px erkennbar)
  cli.py      labelwerk labels | labelwerk media | labelwerk fonts | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
```
Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.

Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`), `pillow>=10.1`, `pypdfium2>=4`. Build: hatchling, src-Layout.

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
- GUI-Tests: jedes Widget bei `qtbot.addWidget` anmelden (sonst Absturz beim Beenden); immer Exit-Code von pytest prüfen, nicht nur „passed“.
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

Nächste Schritte: Etappe 3d-2 Werkzeug ‚Bild‘ (Roadmap 0/5) als neuer Eintrag in `gui/tools.py`, Objekt im selben Modell wie Text.

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
0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-2 Bild · 3c Neu/Öffnen/Speichern + Favoriten · Zierrahmen ums Etikett (P-touch „Rahmen“) · 3e Serien aus CSV/Excel · später Barcode/QR, Rahmen.
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
