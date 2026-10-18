# Symbole/ClipArt (Etappe 3d-2c) – Design

Stand: 2026-10-18 · Status: abgestimmt (Kategorien, Umfang, Extras, Ansatz A „Vektor bleibt erhalten“)

## Ziel

Fertige Symbole aufs Etikett setzen wie im P-touch Editor („ClipArt“): Elektro/Betrieb, Versand/Verpackung,
Sicherheitszeichen und allgemeine Icons, dazu eigene Symbole, Zuletzt verwendet und Favoriten. Symbole sind
Bild-Objekte (verschieben, skalieren, drehen, ausrichten, Strich/Foto, Rückgängig wie Bilder) und bleiben
**in jeder Größe pixelscharf**.

## Nicht enthalten

Symbole bearbeiten (Strichstärke, Farben, Zusammensetzen), Download weiterer Sammlungen aus der App,
Online-Suche, Text in Symbolen, Zweifarbdruck (Farbe bleibt nur erhalten).

## 1 – Vektor-Bilder (Kern, Qt-frei)

- `ImageObject` bekommt `svg: bytes | None = None` (repr=False). Gesetzt → das Objekt ist ein Vektorbild;
  `png` bleibt Vorschau/Rückfall und bestimmt wie bisher Ausschnitt (`crop`, Pixel der PNG) und Größe 1:1
  (`dpi`).
- `render.set_svg_rasterizer(fn | None)`: Raster-Funktion `fn(svg: bytes, size: (w, h)) -> PIL.Image RGB`
  (auf Weiß). Die GUI meldet beim Start eine an (`gui/image_import`: QSvgRenderer); Tests eine Ersatzfunktion;
  ohne Funktion (CLI) gilt die PNG wie bei jedem Bild.
- Rendern eines Vektorbilds: das ganze SVG so groß rastern, dass der Ausschnitt genau den Rahmen in
  Druckpunkten füllt (Faktor = Rahmen / Ausschnitt der PNG), dann den Ausschnitt nehmen – kein Skalieren
  eines Pixelbilds, scharf in jeder Größe; danach wie Bilder (`to_layers`, drehen). Gecacht wie `_scaled_source`
  (Schlüssel SVG-Bytes + Ausschnitt + Größe). Vorschau = Druck (der Druck nimmt das Bild des Renderers).
- „Originalgröße 1:1“ gilt für Vektorbilder als Standardgröße (die `dpi` der Vorschau-PNG legt sie fest).
- Auch SVG-Dateien aus „Aus Datei …“ (3d-2a) werden so Vektorbilder (gleicher Weg; Größe wie bisher aus
  width/height).

## 2 – Bibliothek (Daten, Kern)

- **Quellen** (alle GPL-verträglich; je Symbol Quelle, Autor, Lizenz im Katalog):
  - Allgemein: **Tabler Icons 3.49.0** (MIT), Varianten outline und filled; Lizenztext mitgeliefert.
  - Versand/Verpackung: Packzeichen nach ISO 780 (ISO-7000-Grafiken) von **Wikimedia Commons**, nur Dateien
    mit Lizenz „Public domain“/CC0 laut Commons-API; Datei-URL je Symbol.
  - Sicherheit: **ISO 7010** (Warn-, Verbots-, Gebots-, Rettungs-, Brandschutzzeichen) von Wikimedia Commons,
    Regel wie oben.
  - Elektro/Betrieb: **selbst gezeichnete** SVGs (Lizenz des Projekts, GPL-3.0-or-later), ca. 25: Schutzleiter,
    Erde, Funktionserde, AC, DC, AC/DC, Blitz/Hochspannung, Sicherung, Motor, Generator, Transformator,
    Steckdose, Schalter, Taster, Lampe, Batterie, Klemme, Schirm/Masse, Schutzklasse I/II/III, Spannungsfrei,
    Gefahr elektrische Spannung (eigene Zeichnung, nicht ISO-Datei).
- **Ablage:** `src/labelwerk/clipart/` – `catalog.json` (id, Gruppe, deutscher Name, Suchbegriffe, Quelle,
  Lizenz, Datei), Sammlungen gepackt (`tabler.zip`, `commons.zip`, `elektro/*.svg`), `LICENSES.md`.
  Insgesamt höchstens ca. 6 MB. Mit dem Paket ausgeliefert (hatchling: Daten im Paket).
- **Erzeugen:** `tools/fetch_clipart.py` lädt reproduzierbar (Tabler per npm-Tarball mit fester Version und
  SHA-256; Commons per API mit Dateiliste, prüft die Lizenz je Datei, bricht bei anderer Lizenz ab), schreibt
  Katalog und Archive. Nicht Teil der Tests (Netz); das Ergebnis wird eingecheckt.
- **Kern `clipart.py`:**
  - `groups() -> list[Group]` in fester Reihenfolge: Elektro, Versand, Sicherheit, Allgemein (+ Eigene).
  - `search(text, group=None) -> list[Symbol]`: Teilwort, ohne Groß/Klein und Umlaut-Varianten (ae/ä),
    über deutschen Namen, Suchbegriffe (Fachsymbole deutsch; Tabler englische Namen/Tags plus eine
    mitgelieferte Liste von ca. 200 häufigen deutschen Wörtern → Tabler-Namen, z. B. „Haus“ → home).
  - `svg(symbol) -> bytes`; `own_symbols(dir)` für SVG/PNG im eigenen Ordner (Name = Dateiname).
  - Eigener Ordner: `$XDG_DATA_HOME/labelwerk/symbole` (Standard `~/.local/share/labelwerk/symbole`); fehlt er,
    ist die Gruppe leer (Hinweis im Dialog mit Pfad, Knopf „Ordner öffnen“ legt ihn an).
- **Einstellungen:** `symbols_recent: list[str]` (höchstens 24, neueste zuerst) und `symbols_favorites:
  list[str]` (ids; unbekannte ids werden beim Anzeigen übergangen, nicht gelöscht).

## 3 – GUI

- Reiter Bild, Bereich „Einfügen“: Knopf **SYMBOL …** (Aktion `image.symbol` „Symbol einfügen …“, ohne
  Standardkürzel, in den Einstellungen belegbar).
- Fenster **„Symbol einfügen“** (nicht modal, bleibt offen, eine Instanz; Größe gemerkt nur für die Sitzung):
  - oben Suche (wirkt sofort, über alle Gruppen bzw. die gewählte),
  - links Gruppen: Zuletzt verwendet, Favoriten, Eigene, Elektro, Versand, Sicherheit, Allgemein,
  - rechts Raster (Vorschau ca. 48 px, Tooltip: Name, Quelle, Lizenz), Bildlauf, große Gruppen schrittweise
    geladen (kein Einfrieren bei ca. 5000 Icons),
  - Einfügen: Doppelklick, Enter oder Ziehen aufs Etikett (an der Ablagestelle); ★-Knopf bzw. Kontextmenü
    „Zu Favoriten“/„Aus Favoriten entfernen“,
  - Tabler-Icons zeigen outline; filled als eigene Einträge (Name mit „gefüllt“).
- **Einfügen:** Bild-Objekt (Vektorbild) mit Quelle „Symbol: Name“, längere Seite **15 mm** (höchstens der
  bedruckbare Bereich quer zum Band), Strich, Seitenverhältnis an, Zuschnitt auf den Inhalt (immer, unabhängig
  von der Einstellung – Symbole haben Ränder im viewBox); Platzierung wie Bilder (`insert_placement`: Mitte,
  Endlosband hinter vorhandenem Inhalt; Drehen nach Einstellung entfällt, 15 mm passen immer). Ausgewählt,
  ein Rückgängig-Schritt; „Zuletzt verwendet“ wird aktualisiert und gespeichert.
- Farbige Zeichen (ISO 7010) werden über Strich/Schwelle schwarz-weiß; das Original bleibt farbig.
- Fehler (Archiv defekt, eigene Datei unlesbar) → Meldung in der Statusleiste, kein Traceback.

## Tests

- Kern: Vektorbild rendert mit Ersatz-Rasterer in jeder Rahmengröße ohne Skalieren eines Pixelbilds (z. B.
  1-Pixel-Linien bleiben 1 Druckpunkt dünn bei 8 mm und 55 mm), Ausschnitt korrekt, Drehung, ohne Rasterer
  Rückfall auf PNG, Cache; Dokumente ohne `svg` byte-gleich wie bisher.
- Katalog: jede Gruppe nicht leer; **jedes Symbol hat Quelle und Lizenz aus der erlaubten Liste**
  (MIT, Public domain, CC0, GPL-3.0-or-later) und eine lesbare SVG im Archiv; ids eindeutig; Suche deutsch
  (Umlaute, Teilwort), englisch, Synonymliste; eigener Ordner über `tmp_path`.
- Einstellungen: Zuletzt verwendet (Reihenfolge, Grenze 24, ohne Doppelte), Favoriten (Rundweg, ungültige
  Werte → Warnung).
- GUI: Knopf/Aktion, Fenster (Suche, Gruppen, Favoriten setzen/entfernen, Doppelklick/Enter/Ziehen fügt ein,
  eine Instanz), eingefügtes Symbol 15 mm, Vektor, Quelle, ausgewählt, Rückgängig, Zuletzt verwendet; SVG aus
  „Aus Datei …“ ist Vektorbild; Vorschau = Druck.
