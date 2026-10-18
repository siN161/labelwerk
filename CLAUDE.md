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
- Direkt auf dem Etikett schreiben (Etappe 3d-1b): Schreibmodus (Text anlegen + Klick bzw. Doppelklick, Esc/Klick daneben beendet), Schreibmarke/Markierung aus dem Kern-Zeilensatz, Markieren mit Maus und Tastatur, eine Bearbeitung = ein Rückgängig-Schritt, Rahmen wächst an der Kante der Textposition; Feld INHALT entfällt.
- Bild-Objekt (Etappe 3d-2a): Werkzeug Bild – aus Datei (PNG/JPG/GIF/BMP/WebP/SVG/PDF-Seite), Zwischenablage, Ablegen; 1:1, automatisch zugeschnitten, zu große eingepasst (Einstellungen: automatisch zuschneiden an, drehen statt verkleinern aus); Umwandlung Strich/Foto, Schwelle, Umkehren, Zuschnitt, Originalgröße, Seitenverhältnis, Drehen; Strg+V: Objekte (MIME application/x-labelwerk-objects) › lokale Dateien › Text als Textrahmen › Bild.
- Bildschirmfoto (Etappe 3d-2b): Knopf BILDSCHIRMFOTO im Reiter Bild – labelwerk blendet sich aus, der Desktop zeigt seine Auswahl (XDG-Portal), das Bild kommt mit 300 dpi aufs Etikett; ohne Portal Hinweis auf Zwischenablage + Strg+V.
- SVG-Dateien sind Vektorbilder: in jeder Größe scharf gerastert (Etappe 3d-2c).
- Symbole/ClipArt (Etappe 3d-2c): Knopf SYMBOL im Reiter Bild – Fenster „Symbol einfügen“ (bleibt offen; Suche über die ganze Bibliothek, Gruppen Zuletzt verwendet/Favoriten/Elektro/Versand/Sicherheit/Allgemein/Eigene, Doppelklick/Enter/Ziehen fügt ein); Symbole 15 mm, Vektor, zugeschnitten.
- Zierrahmen ums Etikett: Reiter PAPIER → Rahmen (Einfach, Doppelt, Dick-dünn, Gestrichelt, Gepunktet, Nur Ecken; abgerundet,
  Linie, Randabstand, Innenabstand); runde Etiketten: Kreis; automatischer Text, Ausrichten/Maximieren und neue Bilder/Symbole
  bleiben im Innenraum.
- Serien (Etappe 3e): Reiter SERIE – Tabelle (CSV/Excel) oder Nummerierung, Platzhalter {Spalte} im Text (Spaltenliste fügt
  ein), Zeilen mit Häkchen, Vorschau ◀ Zeile n/N ▶ auf der Arbeitsfläche, DRUCKEN druckt die gewählten Zeilen in einem
  Auftrag (Schnitt nach jedem Etikett oder nur am Ende); die Datei merkt sich die Tabelle und liest sie neu.
- Datei und Favoriten (Etappe 3c): Reiter DATEI – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“); `labelwerk install-desktop` meldet *.labelwerk an (Doppelklick öffnet).
- 1973 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).

## Architektur
```
src/labelwerk/
  labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager);
              filtert für QL-600: >62 mm, PT-Bänder, Rot/Schwarz-Etiketten
  render.py   render_text(text, label_id, size_pt, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
              render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
              compose(rendered, size, orientation) -> Druckbild; label_size/label_margins; schrittweise:
              prepare_object, label_size(prepared=), finish_object; span_dots
              Renderer (Qt-frei, für die GUI): render(doc, model) -> Rendered(size, objects, image, frame) – Objekt-Cache,
              rendert nur Geändertes neu (Objekt + Kontext, ohne Position auch Etikettgröße), Druckbild = render_document
              Zeilensatz mit gemeinsamer Grundlinie (pixelgleich zu Pillow multiline_text für reinen Text), font_warnings(doc)
              exakte Druckbreite @300 dpi, Schrift schrumpft automatisch, mehrzeilig zentriert
              text_layout(obj, doc) -> TextLayout (derselbe Zeilensatz wie das Rendern, auch RenderedObject.layout):
              caret/hit/selection_rects/anchor in Druckpunkten relativ zum ungedrehten Rahmen, Positionen wie QTextDocument
              (in Codepunkten; to_utf16/from_utf16 rechnen in Qts UTF-16-Positionen um)
              ImageObject: Ausschnitt → Rahmen in Druckpunkten (Lanczos, keep_ratio eingepasst) → imaging.to_layers → gedreht;
              decodiert/skaliert gecacht (_source/_scaled_source, Schlüssel PNG-Bytes + Ausschnitt + Größe)
              Vektorbilder (ImageObject.svg): set_svg_rasterizer(fn(svg, size, region)) – die GUI meldet Qt an; gerastert
              wird das Blatt so groß, dass der Ausschnitt den Rahmen füllt (scharf in jeder Größe, _vector_source gecacht);
              ohne Raster-Funktion gilt die Vorschau-PNG
              Zierrahmen (doc.frame): frame_mask(doc, model, size) (Maske „L“, in compose unter den Objekten), frame_box (Innenraum
              in Druckpunkten); Außenkante = bedruckbarer Bereich − inset_mm, rund: Kreis; automatisch gesetzter Text und die
              automatische Länge rechnen mit dem Innenraum (_Sheet.inset/room), frei platzierte Objekte nicht; ohne Innenraum
              „Rahmen passt nicht aufs Etikett“ (nur beim Rendern geprüft: _check_room; Endlosband wird lang genug)
  fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei
  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi)
              crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
              load_image(path, page, dpi=None) -> (RGB-Bild, dpi) für Bild-Objekte (PNG/JPG/GIF/BMP/WebP/PDF, Transparenz → weiß, EXIF-Lage; dpi gesetzt: Dateiauflösung gilt nicht, quadratisch diese dpi);
              crop_box(img, dpi, ink) -> (l, t, r, b) | None, dieselbe Logik wie crop() (Bilder: ink=NOT_WHITE); page_count(path) (PDF-Seitenwahl)
              ink_box(img) -> (l, t, r, b) | None, alles Nicht-Weiße ohne Schnittmarken-Erkennung (Symbole: Einfügen und Panel-Zuschnitt, Schwelle INK_LEVEL)
  imaging.py  Bilder ohne Qt: to_layers(img, mode line|photo, threshold, invert) -> {"black": Bild "1"} (später "red" für QL-8xx),
              on_white, to_8bit (16-Bit-Graustufen skalieren), limit_size (höchstens 600 dpi bzw. 6000 px längste Seite,
              Druckgröße bleibt); Foto: Gammakurve photo_curve (Weiß/Schwarz fest), dann Floyd-Steinberg
  printer.py  build_instructions(image | [images], label_id, model, cut, cut_every) -> bytes (Brother-Raster, mehrere
              Etiketten = ein Auftrag; _Raster: schneiden alle n über ESC i A n, Folgeseiten markiert, bytearray statt
              bytes += – sonst quadratisch langsam), cut_interval(each|end, Anzahl)
              print_image(image | [images], ..., cut_every) -> status-dict; Serien in Teilaufträgen (MAX_JOB_EACH bzw.
              cut_every Etiketten), jeder geprüft – Fehler nennt „Etikett k–m von N“; to_print_mode (1 Bit, bitgleich
              zur Schwelle von brother_ql: 100 − THRESHOLD %)
  detect.py   find_brother_lp() -> "file:///dev/usb/lpN" | None
  document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit);
              TextObject: Position x_mm/y_mm (None = mittig wie bisher), Rahmen w_mm/h_mm (mit fit), Drehen rotation 0/90/180/270
              ImageObject: png (Farboriginal), source/page/crop, Rahmen x/y/w/h_mm immer gesetzt, rotation, mode/threshold/invert,
              keep_ratio, dpi (Auflösung der PNG-Bytes), svg (Vektorbild, png = Vorschau); from_image(img, dpi, source, page,
              crop, svg) setzt 1:1-Größe;
              box() (Ausschnitt in Pixeln), natural_mm() (Größe 1:1)
              Series (frozen): source (CSV/XLSX-Pfad) | numbering (Numbering start/step/count/digits), sheet, cut each|end;
              Document.series (None = Einzeletikett)
              Frame (frozen): style FRAME_STYLES (single/double/thick_thin/dashed/dotted/corners), rounded, line_mm 0,1–3,
              inset_mm/padding_mm 0–10; Document.frame (None = kein Rahmen)
  settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic), `image_crop`/`image_rotate` (Bilder einfügen),
              `symbols_recent` (höchstens 24)/`symbols_favorites` (Symbol-ids), `recent_files` (höchstens 10)/`start_favorite`
              (der Einstellungsdialog reicht sie durch)
  storage.py  Etiketten als Datei (*.labelwerk, JSON versioniert, Bilder Base64): to_dict/from_dict, save (atomar), load;
              Schemata SPAN/PARAGRAPH/TEXT/IMAGE/DOCUMENT (jedes Dataclass-Feld, Test hält gleich); Dateien sind fremde Eingabe:
              Prüfung je Feld nach Art, Wertebereich (endlich, Grenzen) und Struktur → StorageError (deutsch, mit Dateiname),
              Bilddaten nur PNG (ganz dekodiert, höchstens MAX_PIXELS), Rahmen als eigener Eintrag „frame“ (Schema FRAME, null = keiner), Serie „series“ (SERIES/NUMBERING,
              genau Tabelle oder Nummerierung; Tabelle im Ordner der Datei wird relativ gespeichert: to_dict/from_dict(base)), Etikett bekannt; Grenzen: Datei ≤ 32 MB und regulär (kein FIFO),
              ≤ 500 Objekte, Rahmenflächen ≤ 100 Mio. Druckpunkte (sonst „Etikett zu groß“), Lage ±MAX_POSITION_MM (document.py, wie die
              GUI-Positionsfelder), font_path nur für vorhandene reguläre Datei; exists() (wirft nie); unbekannte Felder übergangen,
              fehlende = Standard; save atomar (Symlink verfolgt, Rechte bleiben/umask, fsync); add_recent_file
  series.py   Serien ohne Qt: load_table(path, sheet) -> Table(columns, rows) (CSV: Kodierung inkl. UTF-16, Trennzeichen aus den
              ersten 20 Zeilen; XLSX über openpyxl + defusedxml aus einmal gelesenen Bytes, nur Arbeitsblätter, erstes sichtbares,
              Zahlenformate 000/%/0,00; fremde Eingabe: Größe, ausgepackte Größe, Zeilen/Spalten/Zelllänge begrenzt, gestreamt,
              leere Zeilen und leere Zellen am Zeilenende entfallen → SeriesError deutsch), sheet_names, numbering_table
              (Spalte „Nummer“), check, table_for(series, base); Endungen .csv/.tsv/.txt bzw. .xlsx/.xlsm; Excel höchstens
              MAX_RAW_ROWS Zeilen samt leeren; Table.sheet/sheets (gelesenes Blatt, alle Arbeitsblätter);
              Platzhalter {Spalte} (Leerzeichen in den Klammern egal):
              placeholders, missing, fill(doc, columns, row, keep) – nur zum Lesen: unveränderte Objekte bleiben dieselben
  favorites.py Favoriten = *.labelwerk in $XDG_DATA_HOME/labelwerk/favoriten: favorites, find, add (overwrite), rename, remove
  clipart.py  Symbol-Bibliothek ohne Qt: catalog() aus clipart_data/clipart.zip (catalog.json + SVGs, einmal ganz gelesen;
              erzeugt von tools/fetch_clipart.py: Tabler Icons MIT ohne Marken (Kategorien Brand und Laundry/Pflegesymbole + Sperrliste tabler_skip, u. a. Michelin),
              ISO 7000/7010 von Wikimedia Commons nur gemeinfrei/CC0 ohne Einschränkungen (Stand fest: tools/clipart/commons.lock.json,
              --update), eigene Zeichnungen tools/clipart/eigene (CC0); deutsche Namen/Synonyme tools/clipart/de.json;
              Lizenzen clipart_data/LICENSES.md, auch in pyproject license-files) – im Zweifel weglassen (Lizenz, Marke),
              GROUPS (elektro, versand, sicherheit, allgemein, eigene), symbols(group), search(text, group) (Teilwort, ä=ae;
              Rang: genaues Wort/Kürzel › Namenswort beginnt › Suchbegriff beginnt › im Namen › sonst), find/resolve(ids), data, is_vector, own_dir/own_symbols ($XDG_DATA_HOME/labelwerk/symbole,
              SVG/PNG, ohne versteckte), add_recent; Archiv fehlt/defekt: OSError/BadZipFile/KeyError/ValueError (GUI: Meldung „Symbol-Bibliothek nicht lesbar“)
  media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
  layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
              growing_axis (Endlosband wächst mit), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
              Schreibmodus: to_object/from_object (Etikett ↔ ungedrehtes Objekt, Druckpunkte), anchor_after_edit/anchor_align
              Bilder wie Text mit fester Rahmengröße; keep_aspect (Anfasser mit keep_ratio); Schrift-Funktionen: TypeError bei Bildern
              Bild einfügen/einstellen: insert_frame (Mitte bzw. Ablagepunkt, zu groß → proportional eingepasst, Endlosband
              nur quer), set_crop (Maßstab und Lage des Inhalts bleiben), original_size, set_keep_ratio, proportional
              frame_area(doc, model, size) -> Rect | None (Innenraum des Zierrahmens in mm); snap(..., inner=) rastet auch daran ein
              fill_anchored(doc, columns, row, model, keep): series.fill, frei platzierte Texte ohne feste Rahmengröße behalten
              den Punkt ihrer Textposition (mittig/rechts gelten für jede Zeile) – Vorschau und Druck der Serie
  shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
              without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
  desktop.py  .desktop-Eintrag (Exec … %f, MimeType) + Icon + Dateityp application/x-labelwerk (*.labelwerk, mime/packages,
              Icon) installieren/entfernen (XDG_DATA_HOME), Exec-Pfad gequotet; update_databases (update-mime-/-desktop-database, gescheiterte → Hinweis)
              (which/run ersetzbar – Tests starten keine Programme); APP_ID
  gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
    main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
                    shortcut_actions (Aktions-ID → QAction); rendert über render.Renderer; leere Textrahmen entfallen beim Abwählen;
                    Bilder einfügen (insert_image_files, paste_image, Ablegen; Dialoge ask_image_file/ask_pdf_page ersetzbar),
                    Bildschirmfoto (insert_screenshot: ausblenden, Portal, wieder zeigen; Haken screenshot_available/take_screenshot,
                    Antwort screenshot_finished; 5 min Sicherheitsnetz), Symbole (open_symbols, insert_symbol: SYMBOL_MM 15 mm,
                    höchstens quer zum Band; Zuletzt verwendet/Favoriten still gespeichert), Strg+V nach Zwischenablage des Systems (eigene Kopie › Dateien › Text › Bild; Stand beim Ändern gemerkt,
                    Daten erst beim Einfügen gelesen); Auswahl zeigt Panel der Objektart; Ausrichten/Maximieren „am Etikett“
                    sowie Bilder/Symbole einfügen nutzen mit Zierrahmen seinen Innenraum (_paper_area);
                    accept_pending_input (getippte Zahl ohne Enter vor Drucken/Speichern/Rückgängig übernehmen);
                    Serie: _view_doc (Arbeitsfläche = gefüllte Vorschau-Zeile, Objekt im Schreibmodus mit Platzhaltern: edit_text
                    rendert vorher mit _keep, finish_editing danach), _series_error („Zeile n:“), choose_series_table/ask_series_file,
                    insert_column (Reiter SERIE bleibt), _print_series (Prüfungen und ask_print_count vor dem Rendern, eigener
                    Renderer, confirm_outside_rows, 1 Bit, ein Auftrag mit cut_interval), print_document druckt Serien-Favoriten
                    ganz; start(path) (Datei bzw. Start-Favorit),
                    print_document(doc) (anderes Etikett drucken, gleiche Rückfragen); closeEvent fragt bei Änderungen
    panels/series.py Reiter Serie: Quelle (TABELLE …/NUMMERIERUNG/ENTFERNEN, Blatt, Start/Schritt/Anzahl/Stellen – ungültig: nicht
                    übernommen), Spalten (itemActivated → insert_column), Zeilen mit Häkchen (checked_rows), Vorschau-Zeile (preview,
                    current_row), Schnitt; liest nur bei geänderter Quelle/Blatt/Nummerierung, check_file (Datei geändert, vor dem
                    Drucken), reload (Öffnen); Fehler und unbekannte Platzhalter als Hinweis
    tools.py        Werkzeug-Registry (Datei, Papier, Text, Bild, Layout, Serie; neue Werkzeuge als Eintrag; START_TOOL = Papier)
    file_session.py FileSession: Neu/Öffnen/Speichern, modified/update_title („•“), maybe_save (Rückfrage), Dokument an Ort und
                    Stelle ersetzen (Verlauf neu), Etikett muss zum Drucker passen, origin new|file|favorite (nur „new“ folgt
                    der geprüften Rolle, may_follow_roll; Speichern macht daraus „file“; modified() ohne leere Textrahmen; Neu nimmt die eingelegte Rolle), Favoriten (Vorlage öffnen, drucken über
                    MainWindow.print_document, andere Rolle → Rückfrage, umbenennen/löschen/Start), Zuletzt geöffnet (Pfade
                    aufgelöst); Dialoge ask_* ersetzbar (Speichern-Dialog ergänzt die Endung selbst)
    panels/file.py  Reiter Datei: Knöpfe (Aktionen file.*), Favoriten mit Vorschau und ⎙ je Zeile, Kontextmenü, Zuletzt geöffnet
    panels/         Eigenschaften-Panels je Werkzeug (paper, text und image mit Bereich Position)
    panels/paper.py Reiter Papier: Etikett, Länge, Ausrichtung, Ränder, Rahmen (Arten mit Vorschau aus dem Kern: frame_icon;
                    Felder ohne Tastatur-Mitlauf = ein Schritt, Werte bleiben bei „Kein“ stehen; rund: ohne „Nur Ecken“/abgerundet)
    symbol_dialog.py Fenster „Symbol einfügen“ (SymbolDialog, Werkzeugfenster, nicht modal; Enter/Esc/Kontextmenü): Suche, Gruppen + Untergruppe, Raster über
                    SymbolModel (Vorschau erst bei Bedarf gerastert), Ziehen (MIME_SYMBOL = id), ★ Favorit, Ordner öffnen (open_url ersetzbar)
    panels/image.py Reiter Bild: Aus Datei/Aus Zwischenablage/Bildschirmfoto/Symbol, Quelle, Strich/Foto, Schwelle (Regler = ein Schritt), Umkehren,
                    Zuschnitt (Symbole: Tintenbox, sonst Schnittmarken-Erkennung; Fallback ohne Inhalt: ganzes Bild + Hinweis), Originalgröße 1:1, Seitenverhältnis, Drehen (Aktionen), Position
    image_import.py Bilder beschaffen: rasterize_svg (Raster-Funktion für Vektorbilder); load (SVG per QSvgRenderer bei 300 dpi, Maße mit Einheit selbst gelesen: svg_size; sonst files.load_image), load_symbol (Symbol: Vorschau 600 dpi bei SYMBOL_MM,
                    auf die Tinte zugeschnitten, SVG-Bytes), SYMBOL_SOURCE/is_symbol_source (Panel schneidet Symbole mit files.ink_box zu), MIME_SYMBOL; load_screenshot (Bildschirmfoto: 300 dpi, Dateiangabe gilt nicht;
                    Quelle SCREENSHOT), page_count,
                    mime_image/mime_files/mime_text (Zwischenablage, Ablegen; ohne Auflösung 300 dpi), MIME_OBJECTS
    screenshot.py   Bildschirmfoto über das XDG-Portal (QtDBus, interaktiv): ScreenshotPortal (available, take, Signal
                    finished(Pfad | None, Fehler | None); Empfänger je Aufnahme, veraltete Antworten zählen nicht), request_path,
                    parse_response, error_text; GUI-Tests: Sitzungsbus-Adresse ins Leere + session_bus ersetzt (conftest);
                    Tests gegen tests/gui/fake_portal.py auf privatem dbus-daemon mit eigener Config ohne servicedir
    panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
    panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen)
    canvas.py       Etikett in echter Größe, Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
                    Zierrahmen (frame_item unter den Objekten, keine Klicks; Einrasten am Innenraum);
                    Ablegen von Dateien/Bilddaten (Daten im dropEvent kopiert, Signal dropped danach, mm) und Symbolen (symbol_dropped); Anfasser-Vorschau mit
                    keep_aspect (Bild, dieselbe Regel wie layout.resize: fest ist, was der Anfasser sagt)
                    Schreibmodus: zeichnet Rahmen/Schreibmarke/Markierung (set_edit_marks), meldet Klicks hinein (edit_*)
    text_edit_mode.py TextEditSession: Schreibmodus – Editor des Text-Panels als unsichtbarer Eingabepuffer (Fokus, IME),
                    Klick → Position über TextLayout.hit, Editor → Schreibmarke/Markierung, Auf/Ab nach Etikettzeilen,
                    sofort rendern + anchor_after_edit; Start/Ende/Rückgängig-Schritt: MainWindow.edit_text/finish_editing;
                    Befehle im Schreibmodus (undo/redo/copy/cut/paste/update_actions -> bool „erledigt“), MainWindow delegiert
    actions.py      QActions aus shortcuts.ACTIONS – jedes Kürzel der App läuft hierüber (apply_shortcuts)
    history.py      Rückgängig/Wiederherstellen: Dokument-Schnappschüsse samt Auswahl, höchstens 100; amend (ohne eigenen Schritt)
    symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
    print_worker.py Drucken im Hintergrund-Thread
    media_worker.py  Medium prüfen im Hintergrund
    settings_dialog.py Einstellungen: Reiter Allgemein (inkl. Design, sofort wirksam über app.apply_theme) und Tastenkürzel (Konflikte sperren Speichern)
    theme/          QSS-Stylesheet (rawblock.qss)
    icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
  cli.py      labelwerk labels | labelwerk media | labelwerk fonts | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
```
Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.

Abhängigkeiten: `brother_ql-inventree>=1.3` (GPLv3+, Import als `brother_ql`), `pillow>=10.1`, `pypdfium2>=4`,
`openpyxl>=3.1` (MIT, Excel), `defusedxml>=0.7` (PSF, sicheres XML für openpyxl). Build: hatchling, src-Layout.

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
- Pillow erkennt Formate am Inhalt: `Image.open` immer mit `formats=[…]` – EPS liefe sonst durch Ghostscript (auch bei „.png“).
- D-Bus in Tests: nie `dbus-daemon --session`/`dbus-run-session` – deren Standard-Config startet echte Dienste (Portal öffnet Auswahl auf dem Bildschirm); eigene busconfig ohne servicedir.
- GUI-Tests: Rückfrage „Änderungen speichern?“ ist sitzungsweit ersetzt (conftest, Antwort verwerfen) – sonst hinge ein echter Dialog beim Schließen.
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

Nächste Schritte: offen – Barcodes/QR (Roadmap 3), Drucker-Kompatibilität (6), Übersetzungen (7), Paketierung (8).

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
0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto (erledigt, Spec 2026-10-18-bildschirmfoto) · 3d-2c Symbole/ClipArt (erledigt, Spec 2026-10-18-symbole) · 3c Neu/Öffnen/Speichern + Favoriten (erledigt, Spec 2026-10-18-dateien-favoriten) · Zierrahmen ums Etikett (erledigt, Spec 2026-10-18-zierrahmen) · 3e Serien aus CSV/Excel und Nummerierung (erledigt, Spec 2026-10-18-serien) · später Barcode/QR, Rahmen.
1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
3. Barcodes und QR-Codes
4. Vorlagen (YAML/JSON) und Serien aus CSV/Excel (.xlsx) (z. B. Klemmen-/Betriebsmittelkennzeichnung)
5. Importe:
   - Bilder (PNG/JPG/SVG) als Objekt aufs Etikett, Umwandlung in Schwarz/Weiß
   - Fertiges Bild/PDF 1:1 drucken, ohne Editor (auch per CLI)
   - P-touch-Etiketten (.lbx = ZIP mit XML): Text, Rahmen, Barcodes, Bilder übernehmen
6. Drucker-Kompatibilität (vor Veröffentlichung, QL-Familie):
   - Modell automatisch erkennen (USB-Produkt-ID, z. B. `20c0` → QL-600; sonst Statusabfrage) + Modell-Feld in den Einstellungen als Rückfallebene; alle festen „QL-600“-Annahmen (GUI, Einstellungen, Etikettenliste, Medium prüfen, `DEFAULT_MODEL`) lesen das Modell aus einer Quelle.
   - Fähigkeiten statt Modellnamen: Etiketten, Breite, Abschneider, Zweifarbdruck, Mindestlänge aus `brother_ql` (`ModelsManager`, `LabelsManager`).
   - Golden-Tests je Modell: Testetikett → Rasterdaten mit Referenz vergleichen (beweist, was gesendet wird – nicht, was gedruckt wird).
   - README: Kompatibilitätstabelle *geprüft* (QL-600 + DK-22205) / *sollte funktionieren* (62-mm-QL ohne Rot: QL-570/580N/700/710W/720NW …) / *nicht unterstützt*; nach Veröffentlichung Vorlage „Druckerbericht“ für Rückmeldungen.
   - Netzwerkdrucker (`tcp://IP`) in der GUI wählbar.
   - Später, nur mit Testgerät: breite QL-1050/1100 (102 mm), Zweifarbdruck QL-8xx (Objektfarbe), P-touch-Bandgeräte PT-… (TZe-Bänder).
7. Übersetzungen (vor Veröffentlichung, mindestens **Englisch**):
   - GUI: Qt-Übersetzungen (`self.tr(...)`/`QCoreApplication.translate`, `pyside6-lupdate` → `.ts`, `pyside6-lrelease` → `.qm`, `QTranslator` beim Start; Sprache aus dem System, wählbar in den Einstellungen).
   - Kern und CLI: `gettext` (Meldungen wie `TextTooLarge`, Druckerfehler, CLI-Hilfe), gemeinsame Sprachwahl mit der GUI.
   - Quellsprache festlegen (Deutsch beibehalten oder auf Englisch umstellen) – zusammen mit Punkt 9 (README/Kommentare auf Englisch) entscheiden.
   - Tests: jede Meldung übersetzt (keine fehlenden Einträge), Layout hält längere Texte aus (Panels, Knöpfe).
8. Paketierung: AppImage und/oder Flatpak (USB-Zugriff bei Flatpak beachten)
9. Vor Veröffentlichung: README/Kommentare auf Englisch, LICENSE (GPLv3) prüfen, Repo öffentlich schalten.
   **Namen vorher festlegen** (danach teuer: PyPI-Name, Flatpak-ID `io.github.siN161.<name>`, Repo-Links). Kein „Brother“/„P-touch“/„QL“ im Produktnamen.
   Umbenennen – Checkliste:
   - Nur Anzeigename: `APP_NAME` in `src/labelwerk/desktop.py` (Fenster, Starter, CLI-Hilfe).
   - Technischer Name: `APP_ID` (desktop.py), Paketordner `src/labelwerk/` + alle Importe (`git grep labelwerk`), `pyproject.toml` (`name`, `[project.scripts]`, `packages`), Icon-Dateiname `gui/icons/<id>.svg`, README/CLAUDE.md, GitHub-Repo.
   - Danach: alten Starter mit `labelwerk install-desktop --remove` entfernen, neu installieren (`pip install -e ".[gui]"`, `<name> install-desktop`).
