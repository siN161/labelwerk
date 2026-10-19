# Korrekturen aus der Abnahme – Design

Stand: 2026-10-19 · Status: Antworten des Nutzers 1a, 2a, 3b, 4b, 5b, 6a; Spec danach ohne eigene Freigabe
geschrieben – zur Prüfung mit der Abnahme.

## Anlass (Abnahme 2026-10-19)

- Rand auf 62 mm endlos: 1 mm ergibt quer 1 mm, längs 4 mm; 3 mm ergibt 3 mm bzw. 6 mm. Der QL-600 lässt längs zum
  Band an Anfang und Ende je ~3 mm frei (brother_ql `feed_margin` = 35 Punkte, ESC i d) – labelwerk rechnet seinen Rand
  bisher obendrauf. Dasselbe verlängert ein Etikett fester Länge um ~6 mm.
- Schriftliste (QFontComboBox): über 300 Einträge, viele Kopien („… for Powerline“), Schriften ohne deutsche Zeichen;
  „Sans Serif“ ist ein Sammelname von Qt, keine Schrift → „nicht gefunden – ersetzt durch Noto Sans“.
- Wünsche: Reiter beim Programmstart wählbar; Standard für Bilder (Schwelle) in den Einstellungen.
- Druckermenü: Bürodrucker (Canon TS6300, zwei CUPS-Warteschlangen) erscheinen neben dem Etikettendrucker; Druck
  darauf scheitert (erwartbar).

## Entscheidungen (Antworten)

1. **a – Rand längs wie quer:** der Streifen, den der Drucker längs freilässt, zählt mit. Ein Rand unter diesem Maß
   geht längs nicht; das Feld sagt es dazu.
2. **a – Schriftliste:** nur Schriften mit deutschen Zeichen, ohne Kopien, ohne reine Symbol-/Emoji-Schriften;
   Einstellung „Alle Schriften zeigen“.
3. **b – Reiter beim Start:** fester Reiter wählbar oder „Zuletzt benutzter“.
4. **b – Standard für Bilder:** Schwelle (0–255) und Strich/Foto für neue Bilder.
5. **b – Bürodrucker ausblenden:** CUPS-Warteschlangen ohne Etikett-Formate erscheinen nicht; Einstellung „alle
   zeigen“.
6. **a – Reihenfolge:** diese Etappe obendrauf (Branch `abnahme` auf `i18n`), danach compat → vendors → i18n →
   abnahme nach main, hochladen, CI prüfen.

## Nicht enthalten

Kleinerer Vorschub als der des Druckers (Antwort 1b verworfen), doppelte Warteschlangen zusammenfassen (5c),
Schriftvorschau-Gruppen/„Zuletzt verwendet“ (2b), `print-file`-Ränder (1:1-Druck bleibt wie er ist).

## 1 – Rand und Länge längs zum Band

- **Kern (`labels.py`):** `Label.feed_margin` (Punkte, Brother-Endlosband aus brother_ql `feed_margin`: 35, „18“: 14;
  gestanzt/rund und andere Hersteller 0).
- **`render._sheet`:** Rand längs = max(0, Rand − feed_margin) (wie quer: der unbedruckte Streifen zählt mit).
  Feste Länge `length_mm` ist die **Länge des abgeschnittenen Stücks**: Druckbild = Länge − 2 × feed_margin, in den
  Grenzen des Modells (`length_limits` gelten für das Druckbild). Automatische Länge: Druckbild wie bisher aus Inhalt
  + Rand.
- **Arbeitsfläche:** Endlosband zeigt das ganze Stück: Druckbild mittig, davor und dahinter der Streifen des Druckers
  (wie quer `total_width`); Länge ziehen, Größenangabe beim Ziehen und Feld „Länge“ meinen das Stück. Grenzen des
  Felds/Ziehens = Modellgrenzen + 2 × feed_margin.
- **Reiter PAPIER:** unter „Rand“ ein Hinweis, sichtbar bei Endlosband mit Rand unter dem Streifen des Druckers:
  „Längs zum Band lässt der Drucker {mm} mm frei – weniger geht nicht.“ (Wert aus `feed_margin`, mit Komma je Sprache.)
  Tooltip des Felds nennt beide Streifen.
- **Dateien:** `length_mm` alter Dateien bedeutet jetzt das Stück (Druck ~6 mm kürzer als vorher, dafür wie
  eingestellt) – kein Umrechnen, Hinweis in der Doku.
- **Tests:** Rand längs/quer in Druckpunkten (1 mm → 0 + Drucker, 5 mm → 5 mm − Streifen), feste Länge → Druckbild
  um 2 × 35 Punkte kürzer, Grenzen; Golden-Referenzen neu (`tools/golden.py`), Arbeitsfläche (Stückhöhe, Ziehen,
  Größenangabe), Hinweis im Panel.

## 2 – Schriftliste

- **Kern (`fonts.py`):** `families(all=False)`: kurze Liste = fontconfig `:lang=de` (deutsche Zeichen), ohne
  Farbschriften (`color`), ohne Kopien (Name enthält „Powerline“), ohne reine Symbolschriften (Liste: D050000L,
  Standard Symbols PS, Dingbats, Symbol, OpenSymbol, Webdings, Wingdings …), ohne regionale CJK-Varianten (Namen auf
  CJK/UKai/UMing mit Regionskürzel). `all=True`: alle Familien wie bisher. Ohne fontconfig: `[DEFAULT_FAMILY]`.
- **Einstellung** `fonts_all: bool = False` – Einstellungen → Ansicht „Alle Schriften zeigen“, sofort wirksam.
- **Oberfläche:** eigene Auswahl `FontCombo` (QComboBox) statt QFontComboBox im Reiter TEXT und in den Einstellungen
  (Standardschrift): Einträge aus `fonts.families`, jeder in seiner Schrift dargestellt; eine Schrift aus Datei oder
  Einstellung, die nicht in der Liste steht, erscheint trotzdem (oben, gewählt) – nichts geht verloren. Keine
  Qt-Sammelnamen mehr.
- **CLI:** `labelwerk fonts` zeigt die kurze Liste, `labelwerk fonts --all` alle.
- **Tests:** Filter mit gefälschter fc-list-Ausgabe, FontCombo (Signal, fremde Schrift bleibt), Einstellung.

## 3 – Reiter beim Start

- **Einstellungen:** `start_tool: str = "paper"` (Werkzeug-Schlüssel oder „last“; Standard wie bisher Papier), `last_tool: str = ""` (still
  gespeichert beim Reiterwechsel, wie `symbols_recent`). Dialog → Ansicht „Reiter beim Start“: Zuletzt benutzter,
  Datei, Papier, Text, Bild, Barcode, Layout, Serie. Teil von `RESTART_KEYS` (Hinweis neben SPEICHERN).
- **Start:** gewählter Reiter; „Zuletzt benutzter“ ohne gültigen Wert → `START_TOOL` (Papier). Unbekannte Schlüssel
  in der Datei → Standard (wie andere Felder).

## 4 – Standard für Bilder

- **Einstellungen:** `image_mode: "line" | "photo" = "line"`, `image_threshold: int = 128` (0–255); Dialog →
  Bereich „Bilder einfügen“: Darstellung Strich/Foto, Schwelle.
- **Wirkung:** neue Bilder aus Datei, Zwischenablage, Ablegen, Bildschirmfoto bekommen Art und Schwelle aus den
  Einstellungen (Symbole bleiben Strich/128); Reiter BILD ohne Auswahl zeigt den Standard.
- **Tests:** eingefügtes Bild trägt die Werte, Panel ohne Auswahl, Einstellungen lesen/prüfen.

## 5 – Bürodrucker ausblenden

- **Kern (`cups.py`):** beim Lesen der Warteschlangen (Hintergrund-Thread) je Warteschlange `lpoptions -p NAME -l`
  (gemerkt `INFO_MAX_AGE_S`): **Bürodrucker**, wenn die Papiergrößen A3/A4/A5/B5, Letter, Legal, Executive, Tabloid
  bzw. ihre IPP-Namen (`iso_a4_…`, `na_letter_…`) enthalten. Keine Antwort → unbekannt → angezeigt. `Queue.office`.
- **`printers.cups_printers(…, office=False)`:** Bürodrucker nur mit `office=True`; die gewählte Warteschlange bleibt
  immer sichtbar (`keep`).
- **Einstellung** `cups_all: bool = False` – Einstellungen → Drucker „Alle CUPS-Drucker zeigen (auch Bürodrucker)“.
  GUI-Menü und `labelwerk printers` folgen ihr; `-p cups:NAME` geht immer.
- **Tests:** Erkennung mit gefälschtem `_run`, Liste mit/ohne Einstellung, gewählter Bürodrucker bleibt.

## Abschluss

po/de.po ergänzt, Layout-Test hält die neuen Felder aus, CLAUDE.md/README aktualisiert, Python-3.10-Prüfung (Docker).
