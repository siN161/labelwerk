# Neu/Öffnen/Speichern + Favoriten (Etappe 3c) – Design

Stand: 2026-10-18 · Status: abgestimmt (Favoriten = Vorlagen + Schnellzugriff + Zuletzt geöffnet, Reiter ★,
Start mit Favorit)

## Ziel

Etiketten als Datei speichern und wieder öffnen; oft gebrauchte Etiketten (Absender, Regal, Kabel …) als
**Favoriten** mit Vorschau griffbereit – ein Klick ergibt ein neues Etikett nach dieser Vorlage, ⎙ druckt
direkt; zuletzt geöffnete Dateien; optional mit einem Favoriten starten.

## Nicht enthalten

Etiketten gespeicherter Dateien über die CLI drucken (später), automatisches Speichern/Wiederherstellen,
Unterordner bei Favoriten, Import fremder Formate (P-touch `.lbx`: Roadmap 5), Serien (3e).

## 1 – Dateiformat und Kern (`storage.py`, Qt-frei)

- Datei `*.labelwerk`: JSON (UTF-8), `{"format": "labelwerk", "version": 1, "document": {…}}`.
  - `document`: Etikett (`label_id`, `orientation`, `margin_mm`, `length_mm`) und `objects` – jedes Objekt mit
    `"type": "text" | "image"` und allen Feldern der Dataclass (Text: Absätze/Stücke samt Formatierung,
    Rahmen, Drehung, `fit` …; Bild: `png` und ggf. `svg` Base64, Ausschnitt, Rahmen, Umwandlung, `dpi` …).
  - Unbekannte Felder werden beim Laden ignoriert (vorwärtsverträglich innerhalb einer Version); fehlende
    bekommen den Standardwert der Dataclass.
- `to_dict(doc) -> dict`, `from_dict(data) -> Document`, `save(doc, path)` (atomar: temporäre Datei +
  `os.replace`), `load(path) -> Document`.
- Dateien sind **fremde Eingabe**. Fehler beim Laden → `StorageError` mit deutscher Meldung: keine
  labelwerk-Datei, kaputtes oder zu tief verschachteltes JSON, NaN/Infinity, Version neuer als bekannt („mit
  neuerem labelwerk gespeichert“), falsche Struktur, fehlende Pflichtfelder, Werte außerhalb der Grenzen
  (Lage ±10 000 mm, Größen > 0 und ≤ 1000 mm, Schrift ≤ 1000 pt, Ränder, dpi, Schwelle, Seite, Drehung als
  ganze Zahl, Ausschnitt im Bild), Zeilenumbrüche in Textstücken, unbekanntes Etikett, Bilddaten **nur PNG**
  (Pillow erkennt Formate sonst am Inhalt – EPS liefe durch Ghostscript), ganz dekodiert und höchstens
  6000 Pixel je Seite. Was angenommen wird, scheitert beim Rendern höchstens mit verständlicher Meldung.
  Speichern atomar, Symlinks verfolgt, Rechte bleiben (neu: umask). Gleiches Format-Pinning für alle
  Bild-Importe (`Image.open(..., formats=…)`).
- **Favoriten** (`favorites.py`, Qt-frei): Ordner `$XDG_DATA_HOME/labelwerk/favoriten` (Standard
  `~/.local/share/labelwerk/favoriten`); `favorites() -> list[Favorite]` (Name = Dateiname ohne Endung,
  Pfad; sortiert ohne Groß/Klein), `add(doc, name)` (Name prüfen: nicht leer, keine `/`, vorhandener Name →
  Rückfrage in der GUI), `rename`, `remove`.
- **Einstellungen:** `recent_files: list[str]` (höchstens 10, neueste zuerst, ohne Doppelte) und
  `start_favorite: str | None` (Name eines Favoriten; None = leeres Etikett).

## 2 – GUI

- **Reiter ★** ganz links (vor PAPIER), Titel nur „★“, Tooltip „Datei und Favoriten“:
  - Knöpfe NEU (Strg+N), ÖFFNEN … (Strg+O), SPEICHERN (Strg+S), SPEICHERN UNTER … (Strg+Umschalt+S) – Aktionen
    `file.new`, `file.open`, `file.save`, `file.save_as` im Kürzel-Verzeichnis (global, änderbar).
  - **Favoriten:** Knopf „+ AKTUELL“ (aktuelles Etikett als Favorit; Name erfragen, vorgeschlagen: Dateiname
    bzw. erster Text); Liste mit Vorschau (aus dem Kern gerendert, gecacht) und Namen; Klick → als **neues,
    unbenanntes** Etikett öffnen (Original unverändert); Knopf ⎙ je Favorit druckt direkt (dieselben
    Rückfragen/Prüfungen wie DRUCKEN, das offene Etikett bleibt unberührt); Kontextmenü: Umbenennen, Löschen
    (Rückfrage), Beim Start öffnen (an/aus), Ordner öffnen. Leer: Hinweis, wie man einen Favoriten anlegt.
  - **Zuletzt geöffnet:** die letzten 10 Dateien (Name, Ordner im Tooltip); fehlt eine Datei, ist der Eintrag
    ausgegraut; Klick darauf meldet das und nimmt sie aus der Liste.
- **Speichern:** ohne Pfad wie „Speichern unter“; Dialog mit Filter „labelwerk-Etiketten (*.labelwerk)“, Endung
  wird ergänzt; Ordner des letzten Speicherns/Öffnens gemerkt (Sitzung). Nach Erfolg Meldung in der
  Statusleiste, Datei in „Zuletzt geöffnet“.
- **Rolle (Medium prüfen):** nur ein **neues** Etikett folgt der eingelegten Rolle (war es unberührt, bleibt es
  ohne „•“); eine geöffnete Datei oder ein Favorit behält ihr Etikett, das Papier-Panel zeigt „passt nicht“.
  Neu nimmt die eingelegte Rolle, wenn bekannt. Öffnen/Favorit: Etikett muss zum Drucker passen. ⎙ eines
  Favoriten für eine andere eingelegte Rolle fragt vorher; während eines Drucks sind die ⎙ gesperrt.
- **Ungespeicherte Änderungen:** Fenstertitel „Name – labelwerk“ bzw. „Unbenannt – labelwerk“, mit „•“ vor dem
  Namen, wenn geändert (Vergleich mit dem Stand beim Laden/Speichern, Rückgängig bis dahin = unverändert).
  Vor Neu, Öffnen, Favorit öffnen, Zuletzt geöffnet und Schließen: Rückfrage Speichern / Verwerfen / Abbrechen
  (ersetzbar für Tests). Öffnen/Neu setzt den Rückgängig-Verlauf zurück.
- **Start:** `labelwerk-gui [DATEI]` öffnet die Datei; sonst `start_favorite` als neues Etikett (fehlt er:
  leeres Etikett + Hinweis), sonst leer. Einstellungen → Allgemein → „Neues Etikett“: Auswahl „Beim Start“
  (Leeres Etikett / Favoriten).
- **Desktop:** `labelwerk install-desktop` meldet den Dateityp an (MIME `application/x-labelwerk`, Endung
  `.labelwerk`, Datei unter `$XDG_DATA_HOME/mime/packages/`, `update-mime-database` falls vorhanden) und trägt
  `MimeType=` und `%f` im `.desktop` ein – Doppelklick im Dateimanager öffnet in labelwerk. `--remove` entfernt
  beides.
- Fehler (Lesen/Schreiben, kaputte Datei) → verständliche Meldung (Statusleiste bzw. Dialog), kein Traceback;
  das offene Etikett bleibt dann unverändert.

## Tests

- Kern: Rundweg Speichern/Laden für Text (Absätze, Stücke, Formatierung, Rahmen, Drehung, fit, Position None) und
  Bilder (Pixel und Vektor, Ausschnitt, Umwandlung) – geladenes Dokument gleich dem gespeicherten und
  **byte-gleiches Druckbild**; atomares Speichern; Fehlerfälle (kein JSON, fremdes Format, neuere Version,
  ungültige Werte, kaputte Bilddaten) mit deutscher Meldung; unbekannte Felder ignoriert.
- Favoriten: anlegen/umbenennen/löschen/sortieren über `tmp_path`, ungültige Namen; Einstellungen
  `recent_files`/`start_favorite` (Grenzen, Rundweg, Dialog reicht sie durch).
- GUI (Dialoge/Rückfragen ersetzt): Knöpfe und Kürzel, Speichern/Speichern unter/Öffnen, Titel mit „•“,
  Rückfrage bei Änderungen (Speichern/Verwerfen/Abbrechen), Favorit anlegen/öffnen als unbenannt/drucken
  (Drucken gefälscht)/umbenennen/löschen/Beim Start, Zuletzt geöffnet inkl. fehlender Datei, Start mit Datei-
  Argument und mit Favorit, Fehlermeldungen; install-desktop schreibt MIME-Datei und MimeType (über `tmp_path`).
