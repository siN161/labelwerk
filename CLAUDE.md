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
- Papier: Ausrichtung H/V, Ränder (ringsum ab Papierkante; die Streifen, die der Drucker freilässt, zählen mit: quer
  ~1,5 mm, längs zum Endlosband ~3 mm Vorschub – Hinweis unter Rand; feste Länge = abgeschnittenes Stück samt
  Vorschub, ältere Dateien drucken dadurch ~6 mm kürzer; Arbeitsfläche zeigt die Streifen hellgrau), Medium prüfen (GUI + `labelwerk media`), Einstellungen (`settings.json`, GUI-Dialog), Live-Druckererkennung.
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
  Auftrag (Schnitt nach jedem Etikett oder nur am Ende); die Datei merkt sich die Tabelle und liest sie neu;
  ABBRECHEN in der Statusleiste (beim Vorbereiten sofort, beim Drucken vor dem nächsten Teil – bis zu 10 Etiketten).
- Barcodes und QR-Codes: Reiter BARCODE – Art (QR, Code 128, Code 39, EAN-13, EAN-8), BARCODE EINFÜGEN (Beispielinhalt,
  Inhalt markiert im Fokus), Inhalt live (ein Rückgängig-Schritt), Modulbreite in ganzen Druckpunkten (Anfasser/Felder
  rasten ein; QR quadratisch), Höhe/Klartext bzw. Fehlerkorrektur, Prüfhinweise (EAN-Prüfziffer), Ruhezone; ungültiger
  Inhalt = schraffierter Platzhalter auf der Arbeitsfläche (wählbar, Meldung, kein Druck); {Spalte} der Serie auch im
  Inhalt (Prüfhinweis und Anfasser rechnen mit der Vorschau-Zeile); Doppelklick/F2/Enter → Inhaltsfeld (Strg+Z dort =
  Rückgängig des Etiketts).
- Drucker-Kompatibilität (Roadmap 6): Modell automatisch erkannt (IEEE-1284-Kennung, USB-Produktname, Produkt-ID),
  alle QL aus brother_ql inkl. 102 mm; Statusleiste: Druckerknopf mit Auswahl (Automatisch, gefundene, Netzwerkdrucker
  eintragen), „ungeprüft“ für andere Modelle; Modellwechsel: Etiketten, Längen, Schnitt (ohne Abschneider ausgeblendet),
  Farbe; Netzwerkdrucker per IP in den Einstellungen (Medium prüfen nur USB); Rot/Schwarz je Objekt (Reiter Layout →
  Farbe, nur 62red auf QL-8xx, ungeprüft); CLI -m/-l auto, labelwerk printers; Referenztests je Modell (tests/golden).
- Datei und Favoriten (Etappe 3c): Reiter DATEI – Neu/Öffnen/Speichern (*.labelwerk, Strg+N/O/S, Strg+Umschalt+S), Titel mit „•“ bei Änderungen, Rückfrage Speichern/Verwerfen/Abbrechen; Favoriten mit Vorschau (Klick = neues Etikett nach Vorlage, ⎙ druckt direkt, Umbenennen/Löschen/Beim Start), Zuletzt geöffnet; `labelwerk-gui DATEI`, Start-Favorit (Einstellungen „Beim Start“); `labelwerk install-desktop` meldet *.labelwerk an (Doppelklick öffnet).
- Drucker anderer Hersteller (Etappe 6b, alles ungeprüft): Auflösung je Etikett (Etiketten „57x32mm@203“, Rendern/Layout/
  Barcodes/Arbeitsfläche in Druckerauflösung, Barcode-Maße in mm, Etikettwechsel rechnet Module um); CUPS-Warteschlangen
  im Druckermenü (nie automatisch), Etiketten/Auflösung aus dem Treiber, Druck als PDF in einem Auftrag, Schnitt-Optionen
  des Treibers im Reiter SERIE; Zebra direkt (ZPL, USB/Netzwerk, Modus Abreißen/Schneiden/Ablösen); CLI -p cups:NAME,
  zpl+file://, zpl+tcp:// mit -m zpl:203.
- Übersetzungen (Etappe 7): Deutsch und Englisch – Quellsprache im Code Englisch (`_()`), Deutsch in
  `src/labelwerk/po/de.po`; Sprache des Systems, Einstellung „Sprache“ (nach Neustart; farbiger Hinweis
  „Änderungen erst nach Neustart aktiv“ im Einstellungsfenster neben SPEICHERN, für Sprache, Start-Zoom und Reiter beim Start),
  CLI `--lang` (auch argparse-Texte); Zahlen mit dem Dezimaltrenner der Sprache (Eingabe Komma und Punkt),
  Excel-Zahlen im Etikett nach der Region des Systems; `{Nummer}`/`{Number}` und „Spalte n“/„Column n“ in
  jeder Sprache; Symbole mit deutschen und englischen Namen (Suche in beiden); Layout-Test je Sprache.
- Einstellungen: Reiter beim Start (fest oder zuletzt benutzter), Standard für neue Bilder (Strich/Foto, Schwelle),
  Reiter ausblenden (Ansicht → „Reiter in der Leiste“; DATEI/PAPIER immer; Objekte ausgeblendeter Reiter bleiben
  bearbeitbar – Auswahl zeigt ihr Panel, Tastenkürzel wirken).
- Dateiauswahl mit Vorschau (Etappe Oberfläche): eigener Öffnen-Dialog (Bild einfügen, Etikett öffnen, Tabelle
  der Serie) mit Vorschau rechts (Bilder, SVG, PDF mit Seitenwahl – keine Seitenfrage danach –, Etiketten,
  Tabellen; im Hintergrund gelesen); Einstellung „Dateiauswahl des Systems verwenden“ (nach Neustart: Qt-Platform-
  Theme xdgdesktopportal als Argument = Dialog des Desktops über das XDG-Portal; ohne Qt-Plugin gesperrt).
- Schriftliste (Abnahme-Korrekturen): nur Schriften mit deutschen Zeichen, ohne Kopien (Powerline/Nerd Font),
  Symbol-/Farbschriften und CJK-Regionsvarianten, jede in ihrer Schrift (FontCombo statt QFontComboBox, keine
  Qt-Sammelnamen wie „Sans Serif“); Einstellung „Alle Schriften zeigen“ (`fonts_all`, sofort), CLI `fonts --all`;
  alte Qt-Namen „Name [Hersteller]“ werden zur installierten Familie.
- Bürodrucker: CUPS-Warteschlangen mit Büro-Standardpapier (A4, Letter …) sind im Druckermenü und in
  `labelwerk printers` ausgeblendet (Einstellung „Alle CUPS-Drucker zeigen“ = `cups_all`, CLI `printers --all`,
  gewählte bleibt sichtbar).
- Stilles Speichern (Zuletzt geöffnet/verwendet, Favoriten, gewählter Drucker, letzter Reiter) schreibt nur sein
  Feld (`settings.update_settings`) – was eine zweite Instanz gespeichert hat, bleibt.
- Paketmarken (Etappe Paketmarken, Kern + CLI): `labelwerk parcel MARKE [--type ID|auto] [--country DE] [-l …]
  [--preview]`, `parcel --list`; 19 Typen DE (DHL privat/Business/Warenpost/Retoure, Hermes, Amazon-Retoure) aus
  Testblättern bei paketikett.de ermittelt (`parcel_data/catalog.json`, Werkzeuge `tools/parcel/`), DHL national 1/1a
  am echten Original geprüft (DataMatrix + 2 ITF lesbar); erkennt Typ an Text/Seitengröße (Gleichstand ungeprüfter
  Typen → `--type` verlangt), schneidet/dreht/skaliert die Stücke (Barcodes 1:1, verdeckte Teile weiß), quer
  liegende Marken gedreht, breiteres Band → größer, 100×150-Layout ab 95 mm (fehlt das Layout: neu angeordnet);
  eigene Typen in `$XDG_DATA_HOME/labelwerk/paketmarken`.
- 2886 Tests grün (`pytest -q`), GitHub Actions CI (`.github/workflows/tests.yml`).

## Architektur
```
src/labelwerk/
  labels.py   Etikettentypen je Modell (Daten aus brother_ql.labels.LabelsManager): labels_for_model nach
              printers.capabilities (Breite, restricted_to_models, ohne PT-Bänder, 62red nur Zweifarb-Modelle);
              Label.two_color, Label.dpi (Brother 300), Label.feed_margin (Endlosband: Vorschub des Druckers an
              Anfang und Ende, brother_ql, 35 Punkte; sonst 0); Etiketten anderer Drucker als ID „BxHmm@dpi“ (sized_id/sized_label,
              fest, ganz bedruckbar, eine Schreibweise; get_label versteht sie ohne Drucker), mm_text (Maß mit Komma);
              cups:NAME → Etiketten des Treibers, zpl:DPI → zpl.MEDIA
  render.py   render_text(text, label_id, size_pt, font_path) -> PIL.Image; render_document(doc, model) -> PIL.Image
              render_object(obj, doc, model) -> RenderedObject (Bild mit Anschnitt image_dx/dy, Rahmen x/y/w/h, base_pt);
              compose(rendered, size, orientation) -> Druckbild; label_size/label_margins (_sheet: Rand längs ohne
              feed_margin, length_mm = Stück → Druckbild = Länge − 2·feed_margin); schrittweise:
              prepare_object, label_size(prepared=), finish_object; span_dots
              Renderer (Qt-frei, für die GUI): render(doc, model, placeholders) -> Rendered(size, objects, image, frame,
              errors) – placeholders (Arbeitsfläche): Barcode, der sich nicht kodieren lässt → schraffierter Platzhalter
              (barcodes.placeholder_size/placeholder), errors nennt ihn; Objekt-Cache,
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
  barcodes.py Barcodes ohne Qt: encode(kind, data, error) -> Code (gecacht; Code 128 B/C mit kürzester Folge, Code 39,
              EAN-13/8 mit Prüfziffer ergänzt/geprüft – Tabellen aus den Normen; QR über segno, boost_error aus),
              check(obj), modules(obj), size(obj) (Druckpunkte, ungedreht), draw(obj) (L, ganze Punkte je Modul, Klartext
              DejaVu Sans ~9 Module, EAN mit verlängerten Randzeichen), quiet_mm, TITLES/SAMPLES/INSERT_MODULE;
              BarcodeError (ValueError, übersetzt); Tests lesen jede Art mit zxing-cpp (nur [dev], Python ≥ 3.12)
  i18n.py     Übersetzungen ohne Qt: _/N_/NP_/ngettext/pgettext, set_language ("" = System wie GNU: Gebiets-
              schema LC_ALL › LC_MESSAGES › LANG, „C“ = Englisch, sonst LANGUAGE-Liste), available/NAMES/DECIMAL,
              eigener .po-Leser (parse_po, unquote mit C-Escapes; Kontext, Mehrzahl über gettext.c2py,
              fuzzy/veraltet zählen nicht, BOM egal), decimal/number/thousands/parse_number, content_decimal
              (Region für Etikett-Inhalt), all_translations (Namen in jeder Sprache, z. B. Platzhalter);
              po/<code>.po im Paket, po/labelwerk.pot erzeugt von tools/i18n.py (extract mit „# Translators:“-
              Hinweisen und python-brace-format, update behält Kommentare/fuzzy/veraltete, check prüft auch
              Mehrzahlformen, german_leftovers); Anleitung po/README.md
  fonts.py    Schriften über fontconfig (families, resolve, load), Ersatzkursive bei fehlender Kursiv-Datei;
              families() = kurze Liste (:lang=de, ohne Farbschriften, Powerline/Nerd-Font-Kopien, Symbolschriften,
              CJK-Regionsvarianten), families(all=True) alle (Einstellung `fonts_all`, CLI fonts --all); canonical:
              alte Qt-Namen „Name [Hersteller]“ → „Name“ (resolve, font_warnings, FontCombo)
  files.py    load_file(path, page) -> PIL.Image (PDF via pypdfium2 / PNG / JPG, 300 dpi); PDFIUM_LOCK (RLock: jeder
              PDFium-Aufruf in files, gui/file_dialog und parcel – PDFium ist nicht threadsicher)
              crop(img) -> auf Inhalt, ohne Schnittmarken/Leerraum; fit_to_label(img, label_id, fit, rotate) -> 1:1, auto/feste Drehung
              load_image(path, page, dpi=None) -> (RGB-Bild, dpi) für Bild-Objekte (PNG/JPG/GIF/BMP/WebP/PDF, Transparenz → weiß, EXIF-Lage; dpi gesetzt: Dateiauflösung gilt nicht, quadratisch diese dpi);
              crop_box(img, dpi, ink) -> (l, t, r, b) | None, dieselbe Logik wie crop() (Bilder: ink=NOT_WHITE); page_count(path) (PDF-Seitenwahl)
              ink_box(img) -> (l, t, r, b) | None, alles Nicht-Weiße ohne Schnittmarken-Erkennung (Symbole: Einfügen und Panel-Zuschnitt, Schwelle INK_LEVEL)
  imaging.py  Bilder ohne Qt: to_layers(img, mode line|photo, threshold, invert) -> {"black": Bild "1"} (später "red" für QL-8xx),
              on_white, to_8bit (16-Bit-Graustufen skalieren), limit_size (höchstens 600 dpi bzw. 6000 px längste Seite,
              Druckgröße bleibt); Foto: Gammakurve photo_curve (Weiß/Schwarz fest), dann Floyd-Steinberg
  printer.py  (cups:NAME → cups.print_images, zpl+… → zpl.build/send: je ein Auftrag, Status „sent“)
              build_instructions(image | [images], label_id, model, cut, cut_every) -> bytes (Brother-Raster, mehrere
              Etiketten = ein Auftrag; _Raster: schneiden alle n über ESC i A n, Folgeseiten markiert, bytearray statt
              bytes += – sonst quadratisch langsam), cut_interval(each|end, Anzahl)
              print_image(image | [images], ..., cut_every, cancelled, progress) -> status-dict; Serien in Teilaufträgen
              (MAX_JOB_EACH = 10 bzw. cut_every Etiketten), jeder geprüft – Fehler nennt „Etikett k–m von N“; vor jedem
              Teil cancelled() → PrintCancelled(printed, total) (kein PrintError), nach jedem progress(k, N); to_print_mode (1 Bit, bitgleich
              zur Schwelle von brother_ql: 100 − THRESHOLD %)
  detect.py   find_brother_lp() -> "file:///dev/usb/lpN" | None
  printers.py Drucker ohne Qt: Printer(uri, model, name, source usb|network), usb_printers() (sysfs: IEEE-1284 „MDL:“,
              product, idProduct → PRODUCT_IDS; SYS_ROOT in Tests leer), network_printers(NetworkEntry), choose (gewählt –
              fehlt er: None, kein Ersatz; automatisch: USB mit Modell › USB › erster), printer_for(uri) (usb://…:0xPID → Modell), effective_model (erkannt › Ersatz ›
              zuletzt › QL-600), capabilities(model) (cutter, two_color, max_tape_mm 62/104, length_limits, tested),
              SUPPORTED_MODELS (QL ohne PT), TESTED_MODELS, backend_for(uri) (… | cups | zpl), is_model (QL, cups:NAME,
              zpl:203/300/600), zebra_printers() (sysfs Vendor 0a5f, dpi aus der Kennung, sonst 203; source zebra),
              Netzwerkeintrag mit Modell zpl:… → zpl+tcp://, cups_printers(direct, keep, wait, office, hidden) (Brother-QL-Warteschlange
              nicht doppelt, Bürodrucker nur mit office=True – Einstellung cups_all; eingeordnet nur ohne
              office –, gewählte bleibt immer, hidden sammelt Ausgeblendete);
              choose automatisch nie CUPS
  cups.py     CUPS ohne Qt: _run (lpstat/lpoptions/lp, Zeitlimit, LC_MESSAGES=C; Tests ersetzen _run, BACKGROUND aus),
              queues() (Hintergrund-Thread, 30 s; wait=True für die CLI; classify: Bürodrucker einordnen –
              Queue.office nach der STANDARD-Papiergröße, is_office: A3–A5/B5/Letter/Legal … bzw. IPP-Namen;
              Standard aus PPD *DefaultPageSize, sonst lpoptions „*“; je Warteschlange ein Thread, zusammen
              höchstens TIMEOUT_S, 5 min gemerkt; ohne Antwort: früherer Wert bleibt, sonst None = angezeigt, kurz gemerkt), queue_info(name) -> QueueInfo(media, dpi,
              cut_options, source ppd|options|list; 5 min gemerkt, Fehler nicht), PPD aus PPD_DIR, valid_name,
              print_images(name, images, w, h, dpi, options) -> Job (ein PDF, media=/PageSize=, print-scaling=none)
  zpl.py      Zebra ohne Qt: graphic(img) (^GFA, Zebra-ASCII-Kompression, „:“ = gleiche Zeile), build(images, mode T|C|P),
              send(data, uri) (zpl+file:// bzw. zpl+tcp://, Zeitlimit) → ZplError; MEDIA, CUT_OPTION (Reiter SERIE),
              Referenz-Hashes in tests/golden wie Brother
  document.py Etikett-Dokument (Etikett, Länge, Objekte), UI-unabhängig; Span/Paragraph/TextObject (zeichenweise Formatierung, fit);
              TextObject: Position x_mm/y_mm (None = mittig wie bisher), Rahmen w_mm/h_mm (mit fit), Drehen rotation 0/90/180/270
              ImageObject: png (Farboriginal), source/page/crop, Rahmen x/y/w/h_mm immer gesetzt, rotation, mode/threshold/invert,
              keep_ratio, dpi (Auflösung der PNG-Bytes), svg (Vektorbild, png = Vorschau); from_image(img, dpi, source, page,
              crop, svg) setzt 1:1-Größe;
              box() (Ausschnitt in Pixeln), natural_mm() (Größe 1:1)
              Series (frozen): source (CSV/XLSX-Pfad) | numbering (Numbering start/step/count/digits), sheet, cut each|end;
              Document.series (None = Einzeletikett)
              BarcodeObject: kind (BARCODE_KINDS), data, x/y_mm, module (Druckpunkte 1–20), h_mm (2–100, nur
              Strichcodes), rotation, text, error (QR_LEVELS); kein w_mm – Breite aus dem Inhalt; nie leer
              Frame (frozen): style FRAME_STYLES (single/double/thick_thin/dashed/dotted/corners), rounded, line_mm 0,1–3,
              inset_mm/padding_mm 0–10; Document.frame (None = kein Rahmen)
  settings.py Einstellungen (JSON, $XDG_CONFIG_HOME/labelwerk/settings.json), new_document(settings); Feld `theme` (rawblock/classic), `image_crop`/`image_rotate`/`image_mode`/
              `image_threshold` (Bilder einfügen: Zuschnitt, Drehen, Strich/Foto, Schwelle neuer Bilder; Symbole nicht),
              `start_tool` (Reiter beim Start: START_TOOLS = „last“ + Werkzeug-Schlüssel, gleich mit gui/tools.py TOOLS – Test)/
              `last_tool` (zuletzt benutzter Reiter: GUI merkt ihn im Speicher, schreibt beim Schließen; ungültig → "" ohne Hinweis, QUIET_KEYS),
              `hidden_tools` (ausgeblendete Reiter, nur HIDEABLE_TOOLS = alle außer file/paper; Rest still verworfen, QUIET_KEYS),
              `symbols_recent` (höchstens 24)/`symbols_favorites` (Symbol-ids), `recent_files` (höchstens 10)/`start_favorite`
              (der Einstellungsdialog reicht sie durch); Drucker: `printer` (gewählte URI, "" = automatisch), `printer_model`
              (Ersatz), `last_model` (zuletzt erkannt), `network_printers` ({name, host, model}; valid_host: IPv4/Name ohne
              Port/Schema/Steuerzeichen; Modell auch zpl:…), network_entries(settings); `printer_options` (Modell →
              Druck-Optionen: CUPS-Schnitt-Optionen, Zebra-Modus; je Eintrag geprüft, leerer Wert erlaubt), `zebra_dpi`
              (0 = erkannt), `cups_all` (auch CUPS-Bürodrucker im Druckermenü/`labelwerk printers`; Dialog → Drucker),
              `fonts_all` (alle Schriften in den Auswahlen, sofort), `language` ("" = System); `system_file_dialog` (Dateiauswahl des Systems); RESTART_KEYS (language, start_zoom, start_tool,
              system_file_dialog), start_tool_for (ausgeblendeter Start-Reiter = PAPIER, so verglichen und
              gespeichert), started_values/restart_pending(values, started) (wirksamer Vergleich mit dem
              Start), configured_language/configured_file_dialog (vor allem anderen gelesen);
              load_settings(path, model=None): Etikett muss nur ein bekanntes Etikett sein (auch
              „BxHmm@dpi“; ob es zum Drucker passt, prüfen GUI und CLI); save_settings schreibt alles,
              update_settings(path, base, **felder) nur diese Felder in die neu gelesene Datei (Rest bleibt wie dort,
              auch Unbekanntes; fehlt/kaputt: base; bereinigt dabei: font_size → font_size_pt, ungültige Werte →
              Wert aus base, teilweise ungültige Listen → bereinigt) – stilles Speichern der GUI (MainWindow._save_settings(*keys))
  storage.py  Etiketten als Datei (*.labelwerk, JSON versioniert, Bilder Base64): to_dict/from_dict, save (atomar), load;
              Schemata SPAN/PARAGRAPH/TEXT/IMAGE/BARCODE/DOCUMENT (jedes Dataclass-Feld, Test hält gleich); Dateien sind fremde Eingabe:
              Prüfung je Feld nach Art, Wertebereich (endlich, Grenzen) und Struktur → StorageError (übersetzt, mit Dateiname),
              Bilddaten nur PNG (ganz dekodiert, höchstens MAX_PIXELS), Rahmen als eigener Eintrag „frame“ (Schema FRAME, null = keiner), Serie „series“ (SERIES/NUMBERING,
              genau Tabelle oder Nummerierung; Tabelle im Ordner der Datei wird relativ gespeichert: to_dict/from_dict(base)), Etikett bekannt; Grenzen: Datei ≤ 32 MB und regulär (kein FIFO),
              ≤ 500 Objekte, Rahmenflächen ≤ 100 Mio. Druckpunkte (Barcodes: echte Größe, mit Platzhalter/ungültig barcodes.max_size;
              Barcode-Inhalte zusammen ≤ MAX_BARCODE_TOTAL Zeichen; sonst „Etikett zu groß“), Lage ±MAX_POSITION_MM (document.py, wie die
              GUI-Positionsfelder), font_path nur für vorhandene reguläre Datei; exists() (wirft nie); unbekannte Felder übergangen,
              fehlende = Standard; save atomar (Symlink verfolgt, Rechte bleiben/umask, fsync); add_recent_file
  series.py   Serien ohne Qt: load_table(path, sheet) -> Table(columns, rows) (CSV: Kodierung inkl. UTF-16, Trennzeichen aus den
              ersten 20 Zeilen; XLSX über openpyxl + defusedxml aus einmal gelesenen Bytes, nur Arbeitsblätter, erstes sichtbares,
              Zahlenformate 000/%/0,00; fremde Eingabe: Größe, ausgepackte Größe, Zeilen/Spalten/Zelllänge begrenzt, gestreamt,
              leere Zeilen und leere Zellen am Zeilenende entfallen → SeriesError übersetzt), sheet_names, numbering_table
              (Spalte „Nummer“), check, table_for(series, base); Endungen .csv/.tsv/.txt bzw. .xlsx/.xlsm; Excel höchstens
              MAX_RAW_ROWS Zeilen samt leeren; Table.sheet/sheets (gelesenes Blatt, alle Arbeitsblätter);
              Platzhalter {Spalte} in Text und Barcode-Inhalt (Leerzeichen in den Klammern egal):
              placeholders, missing, fill(doc, columns, row, keep) – nur zum Lesen: unveränderte Objekte bleiben dieselben;
              load_table(…, limit=n): nur die ersten n Zeilen (Vorschau), Table.more = es folgen weitere
  favorites.py Favoriten = *.labelwerk in $XDG_DATA_HOME/labelwerk/favoriten: favorites, find, add (overwrite), rename, remove
  clipart.py  Symbol-Bibliothek ohne Qt: catalog() aus clipart_data/clipart.zip (catalog.json + SVGs, einmal ganz gelesen;
              Einträge mit names/subgroups {de, en} – Anzeige in der Sprache, je Sprache gecacht, Suche über beide;
              englische Namen in tools/clipart/en.json, Pflicht für jedes Zeichen;
              erzeugt von tools/fetch_clipart.py: Tabler Icons MIT ohne Marken (Kategorien Brand und Laundry/Pflegesymbole + Sperrliste tabler_skip, u. a. Michelin),
              ISO 7000/7010 von Wikimedia Commons nur gemeinfrei/CC0 ohne Einschränkungen (Stand fest: tools/clipart/commons.lock.json,
              --update), eigene Zeichnungen tools/clipart/eigene (CC0); deutsche Namen/Synonyme tools/clipart/de.json;
              Lizenzen clipart_data/LICENSES.md, auch in pyproject license-files) – im Zweifel weglassen (Lizenz, Marke),
              GROUPS (elektro, versand, sicherheit, allgemein, eigene), symbols(group), search(text, group) (Teilwort, ä=ae;
              Rang: genaues Wort/Kürzel › Namenswort beginnt › Suchbegriff beginnt › im Namen › sonst), find/resolve(ids), data, is_vector, own_dir/own_symbols ($XDG_DATA_HOME/labelwerk/symbole,
              SVG/PNG, ohne versteckte), add_recent; Archiv fehlt/defekt: OSError/BadZipFile/KeyError/ValueError (GUI: Meldung „Symbol-Bibliothek nicht lesbar“)
  media.py    Medium prüfen: Statusabfrage ESC i S (nicht blockierend, 2 s), Media, label_for_media
  parcel.py   Paketmarken ohne Qt: Katalog parcel_data/catalog.json (Länder → Dienste → Typen; Format/Herkunft/
              eigene Typen/„Neuen Typ beisteuern“ in parcel_data/README.md, gepflegt mit tools/parcel/ – Arbeitsordner
              außerhalb des Repos Pflicht, workdir.py) – countries, carriers, types(country) (+ eigene), find;
              ParcelType (names {de,en} → name, source_sizes – erste = Seitenfläche, raster-Regel für Bildmarken {dpi,
              x_mm, y_mm, px}, detect all/any/none, layouts "62"/"100x150" → Sheet(size_mm, pieces), verified, own),
              Piece(page, src mm, rotation im Uhrzeigersinn, dst-Rechteck mm, kind barcode|text), all_pieces;
              load(path) → Source (PDF: Größen + Text; Bild über files.load_image, Pixel vor dem Dekodieren begrenzt,
              dpi < 50/> 1200 = keine Angabe; page(n, dpi, type) in der Seitenfläche des Typs, außen weiß, ≤
              MAX_PAGE_PIXELS); placement(source, type, n) → Placement(frame, content, rotation, offset): passende
              Größe wie sie ist (Letter oben links auf A4), quer → gedreht (_turn: mehr Tinte in den Bereichen,
              sonst Fehler), Bild: Regel bzw. Seitenverhältnis ±3 % gestreckt, sonst ParcelError; detect(source,
              country, label_id, own) (_fits, all muss vorkommen; Gleichstand: geprüft, passendes Layout,
              Katalogreihenfolge), ambiguous(found) (Gleichstand ohne geprüften Sieger → fragen); snap (Kante bis
              weiß, ≤ 3 mm, nur ungeprüfte Typen, _alone: nie in andere Stücke); convert(source, type, label_id,
              model) → Conversion(documents, notes, layout "62"/"100x150"/"arranged"/"own", scale) (Seitenlage
              geprüft, je Ausgabe-Etikett ein Document mit ImageObjects, Rand 0, spätere Stücke maskieren frühere
              weiß – _mask_covered, Ausschnitte außerhalb weiß – _crop_white; endlos: Länge = Inhalt + Vorschub,
              Breite füllt das Band; fest: passt hinein, bessere Lage; fehlt das Layout fürs Format: arrange;
              Hinweis bei Barcodes < 97 %; rund → Fehler); arrange (Spalten längs des Bands, Barcodes 1:1);
              own_dir/own_types/own_warnings (beschädigt …)/own_from_dict (geprüft, Kanten ≥ 1 mm in der Seite)/
              own_to_dict/save_own/remove_own
  layout.py   Platzier-Logik ohne Qt (mm-Rechtecke): snap, align, match_size, maximize, scale_text, outside_indices/objects_outside,
              growing_axis (Endlosband wächst mit; align_objects am Papier: Anfang des Bereichs, auf Mindestlänge mittig –
              min_length –, nur wenn auch mit den übrigen Objekten (others) das Etikett dort klemmt), to_grid (0,1 mm nach Ziehen), Objekte: move/resize/set_frame/rotate/*_objects
              Schreibmodus: to_object/from_object (Etikett ↔ ungedrehtes Objekt, Druckpunkte), anchor_after_edit/anchor_align
              Bilder wie Text mit fester Rahmengröße; keep_aspect (Anfasser mit keep_ratio); Schrift-Funktionen: TypeError bei Bildern
              Bild einfügen/einstellen: insert_frame (Mitte bzw. Ablagepunkt, zu groß → proportional eingepasst, Endlosband
              nur quer), set_crop (Maßstab und Lage des Inhalts bleiben), original_size, set_keep_ratio, proportional
              frame_area(doc, model, size) -> Rect | None (Innenraum des Zierrahmens in mm); snap(..., inner=) rastet auch daran ein
              Barcodes: _barcode_frame (Breite → Modul gerundet, maximieren abgerundet; QR: stärker geändertes
              Maß), barcode_rect, _resize_barcode (QR quadratisch, fest bleibt, was der Anfasser sagt), new_barcode
              (Beispielinhalt, insert_placement, zu groß → kleineres Modul/Höhe)
              fill_anchored(doc, columns, row, model, keep): series.fill, frei platzierte Texte ohne feste Rahmengröße behalten
              den Punkt ihrer Textposition (mittig/rechts gelten für jede Zeile) – Vorschau und Druck der Serie
  shortcuts.py Tastenkürzel-Verzeichnis ohne Qt: ACTIONS (id, Name, Standard, Bereich global/canvas/edit, fest), effective, conflicts,
              without_conflicts, validate; Bereich edit = Schreibmodus (Esc fest, B/I/U), kollidiert nur mit global
  desktop.py  .desktop-Eintrag (Exec … %f, MimeType) + Icon + Dateityp application/x-labelwerk (*.labelwerk, mime/packages,
              Icon) installieren/entfernen (XDG_DATA_HOME), Exec-Pfad gequotet; update_databases (update-mime-/-desktop-database, gescheiterte → Hinweis)
              (which/run ersetzbar – Tests starten keine Programme); APP_ID
  gui/        PySide6-Oberfläche, nur Anzeige/Bearbeitung:
    main_window.py  Hauptfenster, Werkzeug- und Bearbeitungsleiste, Statusleiste; Aktionen auf der Auswahl, Druck-Rückfragen;
                    Drucker: printer_status (Knopf mit printer_menu: Automatisch, gefundene, Netzwerkdrucker eintragen),
                    refresh_printer (alle 2 s: usb_printers + Netzwerk, choose, last_model speichern, Wechsel vergisst die
                    Rolle), choose_printer(uri), set_model (Papier, Arbeitsfläche, Schnitt, _fit_label: neues unberührtes
                    Etikett nimmt ein passendes – ohne Rückgängig-Schritt –, sonst Hinweis), _can_print (gewählter Drucker
                    da, Etikett passt), Serie hält Modell und Drucker vom Start fest; Netzwerk: ein Auftrag, kein
                    ABBRECHEN, „Gesendet ✓“; cancel_print (ABBRECHEN), set_color_selected (Reiter Layout);
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
                    print_document(doc) (anderes Etikett drucken, gleiche Rückfragen); closeEvent fragt bei Änderungen;
                    apply_hidden_tools(fall_back) (Knöpfe ausgeblendeter Reiter unsichtbar – SERIE bleibt, solange Serie
                    oder Schnitt-Optionen des Druckers: _tool_needed, bzw. solange ihr Panel zu sehen ist: _tool_visible; nach SPEICHERN nur bei geänderten hidden_tools und
                    Panel nicht für Auswahl/Schreibmodus → zuletzt benutzter sichtbarer bzw. PAPIER; leere Auswahl ebenso;
                    Start-Reiter und last_tool überspringen ausgeblendete)
    panels/barcode.py Reiter Barcode: Art (für den gewählten bzw. nächsten), BARCODE EINFÜGEN (Aktion barcode.insert),
                    Inhalt (textEdited live, erster Anschlag/editingFinished = ein Schritt), Prüfhinweis, Modul (ModuleSpin:
                    Punkte, angezeigt in mm), Höhe/Klartext bzw. Fehlerkorrektur, Ruhezone, Drehen, Position; focus_data
    panels/series.py Reiter Serie: Quelle (TABELLE …/NUMMERIERUNG/ENTFERNEN, Blatt, Start/Schritt/Anzahl/Stellen – ungültig: nicht
                    übernommen), Spalten (itemActivated → insert_column), Zeilen mit Häkchen (checked_rows), Vorschau-Zeile (preview,
                    current_row), Schnitt (Brother: set_cutter; CUPS/Zebra: set_driver_cuts mit den Optionen des Treibers bzw.
                    dem Modus, Signal driver_cut_chosen → Einstellungen je Modell); liest nur bei geänderter Quelle/Blatt/Nummerierung, check_file (Datei geändert, vor dem
                    Drucken), reload (Öffnen); Fehler und unbekannte Platzhalter als Hinweis
    tools.py        Werkzeug-Registry (Datei, Papier, Text, Bild, Barcode, Layout, Serie; neue Werkzeuge als Eintrag; START_TOOL = Papier)
    file_session.py FileSession: Neu/Öffnen/Speichern, modified/update_title („•“), maybe_save (Rückfrage), Dokument an Ort und
                    Stelle ersetzen (Verlauf neu), Etikett muss zum Drucker passen, origin new|file|favorite (nur „new“ folgt
                    der geprüften Rolle, may_follow_roll; Speichern macht daraus „file“; modified() ohne leere Textrahmen; Neu nimmt die eingelegte Rolle), Favoriten (Vorlage öffnen, drucken über
                    MainWindow.print_document, andere Rolle → Rückfrage, umbenennen/löschen/Start), Zuletzt geöffnet (Pfade
                    aufgelöst); Dialoge ask_* ersetzbar (Speichern-Dialog ergänzt die Endung selbst)
    panels/file.py  Reiter Datei: Knöpfe (Aktionen file.*), Favoriten mit Vorschau und ⎙ je Zeile, Kontextmenü, Zuletzt geöffnet
    panels/         Eigenschaften-Panels je Werkzeug (paper, text, image und barcode mit Bereich Position)
    panels/paper.py Reiter Papier: Etikett, Länge, Ausrichtung, Ränder, Rahmen (Arten mit Vorschau aus dem Kern: frame_icon;
                    Felder ohne Tastatur-Mitlauf = ein Schritt, Werte bleiben bei „Kein“ stehen; rund: ohne „Nur Ecken“/abgerundet)
    symbol_dialog.py Fenster „Symbol einfügen“ (SymbolDialog, Werkzeugfenster, nicht modal; Enter/Esc/Kontextmenü): Suche, Gruppen + Untergruppe, Raster über
                    SymbolModel (Vorschau erst bei Bedarf gerastert), Ziehen (MIME_SYMBOL = id), ★ Favorit, Ordner öffnen (open_url ersetzbar)
    panels/image.py Reiter Bild: Aus Datei/Aus Zwischenablage/Bildschirmfoto/Symbol, Quelle, Strich/Foto, Schwelle (Regler = ein Schritt), Umkehren,
                    Zuschnitt (Symbole: Tintenbox, sonst Schnittmarken-Erkennung; Fallback ohne Inhalt: ganzes Bild + Hinweis), Originalgröße 1:1, Seitenverhältnis, Drehen (Aktionen), Position;
                    ohne Auswahl Standard für neue Bilder (set_defaults aus den Einstellungen)
    image_import.py Bilder beschaffen: rasterize_svg (Raster-Funktion für Vektorbilder); load (SVG per QSvgRenderer bei 300 dpi, Maße mit Einheit selbst gelesen: svg_size; sonst files.load_image), load_symbol (Symbol: Vorschau 600 dpi bei SYMBOL_MM,
                    auf die Tinte zugeschnitten, SVG-Bytes), SYMBOL_SOURCE/is_symbol_source (Panel schneidet Symbole mit files.ink_box zu), MIME_SYMBOL; load_screenshot (Bildschirmfoto: 300 dpi, Dateiangabe gilt nicht;
                    Quelle SCREENSHOT), page_count,
                    mime_image/mime_files/mime_text (Zwischenablage, Ablegen; ohne Auflösung 300 dpi), MIME_OBJECTS
    screenshot.py   Bildschirmfoto über das XDG-Portal (QtDBus, interaktiv): ScreenshotPortal (available, take, Signal
                    finished(Pfad | None, Fehler | None); Empfänger je Aufnahme, veraltete Antworten zählen nicht), request_path,
                    parse_response, error_text; GUI-Tests: Sitzungsbus-Adresse ins Leere + session_bus ersetzt (conftest);
                    Tests gegen tests/gui/fake_portal.py auf privatem dbus-daemon mit eigener Config ohne servicedir
    panels/position.py PositionSection: Bereich Position (X/Y/B/H in mm), show_frame(rect, editable_size), Signal edited(key, wert)
    panels/layout.py Reiter Layout: Ausrichten, Größe angleichen, Drehen, Reihenfolge (Knöpfe = Aktionen), Farbe (SCHWARZ immer,
                    ROT nur 62red auf einem Zweifarb-Modell: set_red_available; Signal color_chosen)
    canvas.py       Etikett in echter Größe (Endlosband: Stück mit Vorschub, Länge ziehen = Stück), unbedruckbare Streifen
                    hellgrau (unprintable, keine Klicks), Objekte (Auswahl, Ziehen, Einrasten, Anfasser), Lineale, Zug-Anfasser, Zoom;
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
    widgets.py      SpinBox/DoubleSpinBox (Dezimaltrenner der Sprache), FontCombo (Schriftauswahl aus fonts.families,
                    jede Schrift in ihrer Schrift, fremde Schrift bleibt oben gewählt, None = leer bei gemischten Schriften;
                    Breite unabhängig von den Namen; Signal family_chosen) – Reiter Text
                    und Einstellungen
    file_dialog.py  Öffnen-Dialoge: ask_open(parent, title, folder, filters, system, pages, model) -> Chosen | None
                    (Chosen = Pfad als str mit .page: im Dialog gewählte PDF-Seite); PreviewFileDialog (nicht nativ,
                    Vorschau rechts: PreviewPane, ◀ n/N ▶ bei PDF mit pages; Platz: Orte ≥ 160 px, Name dehnt sich,
                    ohne Typ; ≤ 90 % Bildschirm), make_preview(path, page, size, model) -> Preview (Bild verkleinert
                    gelesen samt EXIF-Lage, Pixelgrenze vor dem Dekodieren außer JPEG, SVG, PDF, *.labelwerk, Tabellen
                    nur der Anfang; Fehler → „Keine Vorschau“) – im Hintergrund-Thread (Generation, veraltete
                    verfallen), PDF im GUI-Thread (PDFium); system: QFileDialog des Systems; system_dialog_available
                    (Qt-Plugin platformthemes/*xdgdesktopportal*); exec_dialog in Tests ersetzt;
                    MainWindow.system_dialog = Weg vom Start (Einstellung beim Start und Plugin), auch „Speichern unter“
                    (dann eigene Ersetzen-Rückfrage); app.qt_arguments: „-platformtheme xdgdesktopportal“ beim Start
    symbols.py      Liniensymbole (gui/icons) je Design, weiß beim Darüberfahren in RawBlock
    print_worker.py Drucken im Hintergrund-Thread (cancel(): threading.Event; Signale progress, cancelled)
    media_worker.py  Medium prüfen im Hintergrund (MediaWorker(model, printer): URI des gewählten USB-Druckers; Ergebnis eines
                    inzwischen gewechselten Druckers zählt nicht)
    settings_dialog.py Einstellungen: Reiter Allgemein (rollt; inkl. Design, sofort wirksam über app.apply_theme; Drucker:
                    Druckermodell als Ersatz, Zebra-Auflösung, Netzwerkdrucker-Tabelle mit Prüfung der Adresse und Modell
                    Brother/Zebra, „Alle CUPS-Drucker zeigen“; Etikett eines anderen Druckers bleibt; Neues Etikett: …,
                    Schriftart (FontCombo) mit „Alle Schriften zeigen“ darunter (sofort); Bilder einfügen: Zuschnitt, Drehen,
                    Umwandlung Strich/Foto, Schwelle; Ansicht: Start-Zoom, Reiter beim Start, Reiter in der Leiste (tool_boxes, sperren
                    ausgeblendete im Start-Reiter; tools_note),
                    Design, Dateiauswahl des Systems, Sprache) und
                    Tastenkürzel (Konflikte sperren Speichern); restart_hint neben SPEICHERN (Stand beim Start: started)
    theme/          QSS-Stylesheet (rawblock.qss)
    icons/          labelwerk.svg (App-Icon: Starter, Fenster; ab 16 px erkennbar), labelwerk-v2.svg (mit Schnittmarken, nur groß: README/Über-Dialog)
  cli.py      labelwerk labels | labelwerk media | labelwerk printers [--all] (Bürodrucker; sonst Zeile „n ausgeblendet“) | labelwerk fonts [--all] | labelwerk parcel DATEI [--type ID|auto] [--country DE] [--preview A.png] /
              parcel --list | -m auto (Modell des Zieldruckers:
              -p bzw. gewählter/erster) | -l auto (Rolle des Zieldruckers per USB) | Etikett muss zum Modell passen | labelwerk print "Text\nZeile 2" -l 62 [--preview out.png] [--orientation horizontal|vertical] [--margin MM] | labelwerk print-file DATEI -l 62 [--rotate auto|0|90|180|270] [--fit] [--page N]
```
Die Kernlogik ist UI-unabhängig. Jede UI (GUI, später evtl. Web) setzt nur auf `render`, `files`, `labels`, `printer`, `printers`, `detect`, `settings`, `media` auf – keine Drucklogik in der UI.

Abhängigkeiten: `brother_ql-inventree>=1.3,<1.4` (GPLv3+, Import als `brother_ql`; Referenztests hashen die
Rasterdaten – neue Version erst nach `tools/golden.py`), `pillow>=10.1`, `pypdfium2>=4`,
`openpyxl>=3.1` (MIT, Excel), `defusedxml>=0.7` (PSF, sicheres XML für openpyxl), `segno>=1.5` (BSD-3-Clause, QR);
nur Entwicklung: `zxing-cpp` (Apache-2.0, liest Barcodes in Tests; ab Python 3.12). Build: hatchling, src-Layout.

## Konventionen
- **TDD**: erst fehlschlagenden Test schreiben, dann implementieren. Tests laufen **ohne Drucker** (Rasterdaten prüfen, sysfs per `tmp_path` faken, Druckfunktionen per `monkeypatch` ersetzen). Kein Test darf echte Hardware ansprechen.
- Benutzer-Meldungen **englisch mit `_()`** (benannte Platzhalter, Tabellen mit `N_` und `_()` beim Anzeigen),
  Deutsch in `po/de.po` (`python tools/i18n.py update`, dann übersetzen); Tests laufen auf Deutsch (conftest).
  Kommentare und Docstrings vorerst deutsch (vor Veröffentlichung ggf. auf Englisch umstellen).
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

Nächste Schritte: Paketierung (8).

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
0. Etappen P-touch-Übernahme: 1 Papier komplett (erledigt) · 2 Verwendungsart – **zurückgestellt** (P-touch-Vorlagen wie Kabelfahne/Kabelwickel/Patchfeld; erst klären, welche Arten der P-touch Editor beim QL-600 anbietet – Screenshot der Liste) · 3a/3b Text-Formatierung (erledigt) · 3d-1 Freies Platzieren (erledigt, Spec 2026-10-17-freies-platzieren) · 3d-1b Direkt auf dem Etikett schreiben (erledigt, Spec 2026-10-17-direkt-schreiben) · 3d-2a Bild (erledigt, Spec 2026-10-17-bild-objekt) · 3d-2b Bildschirmfoto (erledigt, Spec 2026-10-18-bildschirmfoto) · 3d-2c Symbole/ClipArt (erledigt, Spec 2026-10-18-symbole) · 3c Neu/Öffnen/Speichern + Favoriten (erledigt, Spec 2026-10-18-dateien-favoriten) · Zierrahmen ums Etikett (erledigt, Spec 2026-10-18-zierrahmen) · 3e Serien aus CSV/Excel und Nummerierung (erledigt, Spec 2026-10-18-serien) · Barcodes/QR (erledigt, Spec 2026-10-19-barcodes) · Abnahme-Korrekturen (erledigt, Spec 2026-10-19-abnahme-korrekturen) · Oberfläche (erledigt, Spec 2026-10-19-oberflaeche).
1. ~~Text 90° drehen (Text längs zum Endlosband, wichtig für 12–29 mm)~~ erledigt in Etappe 1
2. Eingelegte Rolle automatisch aus dem Druckerstatus auslesen → teilweise erledigt in Etappe 1 (GUI-Vorauswahl, `labelwerk media`); `-l auto` in der CLI fehlt noch
3. ~~Barcodes und QR-Codes~~ erledigt (QR, Code 128, Code 39, EAN-13/8; später ggf. DataMatrix, ITF, GS1-128)
4. Vorlagen (YAML/JSON) und Serien aus CSV/Excel (.xlsx) (z. B. Klemmen-/Betriebsmittelkennzeichnung)
5. Importe:
   - Bilder (PNG/JPG/SVG) als Objekt aufs Etikett, Umwandlung in Schwarz/Weiß
   - Fertiges Bild/PDF 1:1 drucken, ohne Editor (auch per CLI)
   - P-touch-Etiketten (.lbx = ZIP mit XML): Text, Rahmen, Barcodes, Bilder übernehmen
6. Drucker-Kompatibilität (vor Veröffentlichung, QL-Familie) – umgesetzt (Spec 2026-10-19-drucker-kompatibilitaet;
   ungeprüft bis auf QL-600, Rückmeldungen sammeln):
   - Modell automatisch erkennen (IEEE-1284-Kennung, USB-Produktname, Produkt-ID, z. B. `20c0` → QL-600) + Modell-Feld in den Einstellungen als Rückfallebene; alle festen „QL-600“-Annahmen (GUI, Einstellungen, Etikettenliste, Medium prüfen, `DEFAULT_MODEL`) lesen das Modell aus einer Quelle.
   - Fähigkeiten statt Modellnamen: Etiketten, Breite, Abschneider, Zweifarbdruck, Mindestlänge aus `brother_ql` (`ModelsManager`, `LabelsManager`).
   - Golden-Tests je Modell: Testetikett → Rasterdaten mit Referenz vergleichen (beweist, was gesendet wird – nicht, was gedruckt wird).
   - README: Kompatibilitätstabelle *geprüft* (QL-600 + DK-22205) / *sollte funktionieren* (62-mm-QL ohne Rot: QL-570/580N/700/710W/720NW …) / *nicht unterstützt*; nach Veröffentlichung Vorlage „Druckerbericht“ für Rückmeldungen.
   - Netzwerkdrucker (`tcp://IP`) in der GUI wählbar.
   - Später, nur mit Testgerät: breite QL-1050/1100 (102 mm), Zweifarbdruck QL-8xx (Objektfarbe), P-touch-Bandgeräte PT-… (TZe-Bänder).
7. Übersetzungen – umgesetzt (Spec 2026-10-19-uebersetzungen; gettext überall statt Qt-.ts). Ursprüngliche Notiz:
   - GUI: Qt-Übersetzungen (`self.tr(...)`/`QCoreApplication.translate`, `pyside6-lupdate` → `.ts`, `pyside6-lrelease` → `.qm`, `QTranslator` beim Start; Sprache aus dem System, wählbar in den Einstellungen).
   - Kern und CLI: `gettext` (Meldungen wie `TextTooLarge`, Druckerfehler, CLI-Hilfe), gemeinsame Sprachwahl mit der GUI.
   - Quellsprache festlegen (Deutsch beibehalten oder auf Englisch umstellen) – zusammen mit Punkt 9 (README/Kommentare auf Englisch) entscheiden.
   - Tests: jede Meldung übersetzt (keine fehlenden Einträge), Layout hält längere Texte aus (Panels, Knöpfe).
6b. Drucker anderer Hersteller – umgesetzt (Spec 2026-10-19-fremdhersteller, alles ungeprüft): CUPS und Zebra direkt.
   Ursprüngliche Notiz (Grundlage: Drucker-Schnittstelle aus 6 – Brother ist eine Umsetzung):
   allgemein über CUPS (fertiges Bild an eingerichteten Etikettendrucker: Dymo LabelWriter, Zebra mit Linux-Treiber),
   Zebra direkt (ZPL), später Bluetooth-Geräte (Niimbot, Phomemo – Protokolle nur von der Community, erst mit Testgerät);
   ohne Testgerät „ungetestet“; Dymo LabelWriter 550 nimmt nur Original-Etiketten mit Chip.
8. Paketierung: AppImage und/oder Flatpak (USB-Zugriff bei Flatpak beachten)
9. Vor Veröffentlichung: README/Kommentare auf Englisch, LICENSE (GPLv3) prüfen, Repo öffentlich schalten.
   **Namen vorher festlegen** (danach teuer: PyPI-Name, Flatpak-ID `io.github.siN161.<name>`, Repo-Links). Kein „Brother“/„P-touch“/„QL“ im Produktnamen.
   Umbenennen – Checkliste:
   - Nur Anzeigename: `APP_NAME` in `src/labelwerk/desktop.py` (Fenster, Starter, CLI-Hilfe).
   - Technischer Name: `APP_ID` (desktop.py), Paketordner `src/labelwerk/` + alle Importe (`git grep labelwerk`), `pyproject.toml` (`name`, `[project.scripts]`, `packages`), Icon-Dateiname `gui/icons/<id>.svg`, README/CLAUDE.md, GitHub-Repo.
   - Danach: alten Starter mit `labelwerk install-desktop --remove` entfernen, neu installieren (`pip install -e ".[gui]"`, `<name> install-desktop`).
