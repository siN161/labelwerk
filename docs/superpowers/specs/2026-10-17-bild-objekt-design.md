# Bild-Objekt (Etappe 3d-2a) – Design

Stand: 2026-10-17 · Status: abgestimmt (Umfang und Aufteilung mit dem Nutzer; Einzelheiten nach Freigabe „zieh alles durch“ vom Entwickler festgelegt und hier dokumentiert)

## Ziel

Bilder als Objekte frei aufs Etikett setzen – wie Text: auswählen, verschieben, skalieren, drehen, ausrichten, Rückgängig. Quellen: **Datei** (PNG, JPG, GIF, BMP, WebP, SVG, PDF-Seite) und **Zwischenablage**. Hauptfall: die Internetmarke (PDF) zugeschnitten 1:1 neben einen Absenderblock setzen.

Aufteilung der Etappe 3d-2: **2a** Bild-Objekt (dieses Dokument, inkl. vorbereitendem Umbau) · **2b** Bildschirmfoto (XDG-Portal) · **2c** Symbole/ClipArt (Bibliothek, Lizenzen).

## Nicht enthalten

Bildschirmfoto und Symbole (2b/2c), Bildbearbeitung (Freistellen, Retusche), Zuschneiden per Maus (nur automatisch + „Original“), Zweifarbdruck (nur Schnittstelle vorbereitet), Bilder in der CLI-`print` (CLI `print-file` bleibt).

## 0 – Vorbereitender Umbau (verhaltensneutral)

- **Inkrementeller Renderer im Kern:** `render.Renderer` (Qt-frei) übernimmt den Objekt-Cache aus `MainWindow` (`_Cached`, `_prepare_objects`, `_render_objects`, `_compose`): `Renderer.render(doc, model) -> Rendered(size, objects: list[RenderedObject], image)`; rendert nur geänderte Objekte (Schlüssel wie bisher: Objektinhalt + Kontext, bei Objekten ohne Position zusätzlich Etikettgröße). Testbar ohne Qt.
- **Schreibmodus-Zweige** aus `MainWindow.undo/redo/copy/cut/paste/_update_edit_actions` in `TextEditSession` (`session.undo() -> bool` „erledigt“ usw.).
- **Bereich „Position“** als eigenes Widget `gui/panels/position.py` (X/Y/B/H), von Text- und Bild-Panel genutzt.
- Alle bestehenden Tests bleiben grün; Druckbild byte-gleich.

## 1 – Modell und Kern

- `document.ImageObject`:
  - `png: bytes` – Originalbild **in Farbe** (RGB/RGBA→RGB auf Weiß), verlustfrei als PNG (JSON-tauglich für 3c),
  - `source: str` (Dateiname oder „Zwischenablage“), `page: int | None` (PDF),
  - `crop: tuple[int, int, int, int] | None` – Ausschnitt im Original in Pixeln (None = ganzes Bild),
  - `x_mm, y_mm, w_mm, h_mm` (Rahmen; immer gesetzt), `rotation` (0/90/180/270),
  - `mode: "line" | "photo"` (Standard „line“), `threshold: int` 0–255 (Standard 128), `invert: bool`,
  - `keep_ratio: bool = True`.
  - `is_empty()` → False. `Document.objects: list[TextObject | ImageObject]`.
- **Laden** (`files.py`, Qt-frei): `load_image(path, page=1) -> (Image RGB, dpi)` für PNG/JPG/GIF(erstes Bild)/BMP/WebP/PDF; Transparenz auf Weiß; 16-Bit-Graustufen werden auf 8 Bit skaliert (nicht abgeschnitten); DPI aus der Datei auf 0,01 gerundet, quer verschiedene DPI (Fax 204 × 98) → Höhe skaliert, Druckgröße stimmt. **SVG** rastert die GUI (QSvgRenderer, 300 dpi; Größe aus `width`/`height` mit Einheit px/mm/cm/in/pt/pc nach CSS – 1 px = 1/96 in, selbst gelesen, weil Qt mit 90 dpi rechnet –, ohne Einheit aus Qts Größe/viewBox) und reicht PNG-Bytes weiter – der Kern bleibt Qt-frei. Sehr große Bilder werden beim Einfügen auf höchstens 600 dpi bezogen auf ihre Druckgröße bzw. 6000 px längste Seite verkleinert (Speicher).
- **Automatischer Zuschnitt** beim Einfügen: `files.crop_box(img, dpi, ink) -> (l, t, r, b) | None` (dieselbe Logik wie `crop()` – Schnittmarken, Leerraum; `crop()` nutzt sie mit `ink=128` unverändert). Bilder: Transparenz zuerst auf Weiß, Inhalt ist alles „nicht weiß“ (`ink=NOT_WHITE` = 245), damit helle Fotos und gelbe Logos ganz bleiben; ohne Inhalt `None` → ganzes Bild. Ergebnis in `ImageObject.crop`. Panel-Schalter „Zuschnitt“ (an/aus = automatisch/ganzes Original).
- **Größe beim Einfügen:** 1:1 aus der DPI-Angabe (ohne Angabe 300 dpi; PDF in Originalgröße). Passt das Bild nicht in den bedruckbaren Bereich, wird es proportional eingepasst (Hinweis in der Statusleiste „Bild auf N % verkleinert – Codes ggf. nicht mehr lesbar“, nie „0 %“, sondern „< 1 %“) und danach erneut auf 600 dpi bezogen auf die neue Druckgröße begrenzt (Größe 1:1 bleibt für „Originalgröße“). Position: Klick-/Ablagepunkt bzw. Mitte des bedruckbaren Bereichs.
- **Umrechnung** (`imaging.py`, neu, Qt-frei): `to_layers(img, mode, threshold, invert) -> dict[str, Image "1"]` mit Ebene `"black"`; `mode="line"`: Graustufe → harte Schwelle; `"photo"`: Gammakurve `v' = 255 · (v/255) ** g` mit `g = 2 ** ((threshold − 128) / 64)` (höhere Schwelle → dunkler, 128 = unverändert; 0 und 255 bleiben fest – weißes Papier bekommt nie Punkte, Schwarz bleibt voll), dann Floyd-Steinberg. Schnittstelle für später `"red"` (Zweifarbdruck QL-8xx) dokumentiert, aber nicht gebaut.
- **Rendern:** `render_object` kennt `ImageObject`: Ausschnitt → auf Rahmengröße in Druckpunkten skalieren (Lanczos mit `reducing_gap=2`: stark verkleinert erst ganzzahlig reduzieren – 1:1, vergrößert und bis 2× verkleinert unverändert exakt; bei `keep_ratio` kein Verzerren – Rahmen hat das Seitenverhältnis) → `to_layers` → Ebene „black“ als Objektbild (Tinte schwarz) → drehen wie Text. Ergebnis gecacht (Renderer). `RenderedObject.layout` = None.
- **Platzier-Logik:** `layout` behandelt `ImageObject` wie Text mit fester Rahmengröße (move/resize/set_frame/rotate/align/match_size/maximize); Ecken skalieren proportional bei `keep_ratio`, Kanten verzerren nur ohne `keep_ratio` (mit `keep_ratio` wirken Kanten wie Ecken in einer Achse und halten das Verhältnis). Was fest bleibt, folgt allein aus dem Anfasser (`keep_aspect(old, new, handle)`, Vorschau und Ergebnis gleich): Ecke → gegenüberliegende Ecke, Kante → gegenüberliegende Kante, quer dazu die Mitte.

## 2 – GUI

- **Werkzeug „Bild“** (Reiter BILD in `tools.py`, nach TEXT), Panel `panels/image.py`:
  - Knöpfe **„Aus Datei …“** (Dateidialog mit Filter „Bilder und PDF“) und **„Aus Zwischenablage“** (aktiv, wenn die Zwischenablage ein Bild enthält).
  - Für ein gewähltes Bild: Quelle (Name, Seite), **Umwandlung** Strich/Foto, **Schwelle** (Regler 0–255 + Zahl), **Umkehren**, **Zuschnitt** (automatisch an/aus), **Originalgröße 1:1**, **Seitenverhältnis beibehalten**, Bereich **Position** (gemeinsames Widget).
  - PDF mit mehreren Seiten: Seitenwahl im Dialog nach dem Öffnen (Spinbox, Vorgabe 1).
- **Einfügen:**
  - Datei/Zwischenablage über das Panel → Bild in die Mitte des bedruckbaren Bereichs.
  - **Strg+V auf der Arbeitsfläche** (Reihenfolge festgelegt): (1) liegt die interne Objekt-Zwischenablage oben (labelwerk-Markierung im System-Clipboard, bei leerer Zwischenablage die letzte Kopie), werden Objekte eingefügt (wie bisher, je 2 mm versetzt); (2) lokale Datei-URLs (Dateimanager) → wie „Aus Datei“, andere Dateitypen mit Meldung; (3) Text → neuer Textrahmen mit diesem Text (wiederholt eingefügt je 2 mm versetzt) – **Text gewinnt, wenn zugleich ein Bild dabei ist** (Tabellenzellen bringen ein Bild mit; das Bild bleibt über „Aus Zwischenablage“ erreichbar); (4) Bild; sonst nichts. Freigabe der Knöpfe aus dem beim Ändern der Zwischenablage gemerkten Stand (ohne Daten zu holen). Kopieren/Ausschneiden von Objekten setzt dafür einen eigenen MIME-Typ `application/x-labelwerk-objects` in die System-Zwischenablage.
  - **Ziehen & Ablegen** von Bilddateien (und Bilddaten) auf die Arbeitsfläche → Bild an der Ablagestelle; mehrere Dateien je 2 mm versetzt. Die Daten werden im Ablegen kopiert und erst danach verarbeitet (PDF-Seitendialog nicht im `dropEvent`).
- Auswahl eines Bildes zeigt das BILD-Panel (wie Text → TEXT). Doppelklick auf ein Bild: kein Schreibmodus (nichts).
- Layout-Reiter, Drehen, Reihenfolge, Ausrichten, Kopieren/Einfügen, Rückgängig funktionieren für Bilder wie für Text.
- Fehler (Datei unlesbar, kein Bild in der Zwischenablage, PDF-Seite fehlt): verständliche Meldung in der Statusleiste, kein Traceback.

## Tests

- **Umbau:** Renderer-Tests ohne Qt (nur Geändertes neu, Etikettgröße als Schlüssel bei Objekten ohne Position, Druckbild byte-gleich zu vorher); bestehende GUI-Tests unverändert grün.
- **Kern:** `load_image` je Format (aus Pillow erzeugte Testdateien, PDF via Pillow), Transparenz → Weiß, DPI → Größe; `crop_box` = bisheriges `crop()` (Standard-`ink`), „nicht weiß“ für Bilder, `None` ohne Inhalt; 16-Bit-Graustufen; `to_layers` Strich/Foto/Schwelle/Umkehren (Foto: Weiß/Schwarz bleiben bei jeder Schwelle); `render_object` für Bilder: Größe, Drehung, `keep_ratio`, Ecken-/Kanten-Skalierung, Vorschau = Druck; Layout-Funktionen mit gemischten Text/Bild-Auswahlen; große Bilder werden begrenzt.
- **GUI (offscreen):** Bild aus Datei (Dialog gepatcht) erscheint 1:1 in der Mitte, zu großes Bild wird eingepasst + Hinweis; Strg+V mit Bild in der Zwischenablage; Strg+V nach internem Kopieren fügt Objekte ein; Strg+V mit Text → Textrahmen; Ablegen einer Datei; Panel-Einstellungen ändern das Druckbild; Auswahl eines Bildes zeigt BILD-Panel; Rückgängig je Aktion; Layout „gleiche Größe“ Text+Bild; Doppelklick auf Bild startet keinen Schreibmodus; SVG wird gerastert.
- Keine echten Briefmarken/Adressen im Repo; Testbilder werden im Test erzeugt.
