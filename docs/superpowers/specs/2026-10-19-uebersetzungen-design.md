# Übersetzungen (Roadmap 7) – Design

Stand: 2026-10-19 · Status: Antworten des Nutzers 1a, 2a, 3b, 4b, 5a (+ Neustart-Hinweis allgemein), 6a, 7a, 8a, 9a;
Spec danach ohne eigene Freigabe geschrieben – zur Prüfung mit der Abnahme.

## Ziel

labelwerk spricht Deutsch und Englisch – Oberfläche, Kommandozeile und Meldungen des Kerns –, wählt die Sprache des
Systems und lässt sie in den Einstellungen umstellen. Weitere Sprachen kann später jeder beisteuern: eine `.po`-Datei
je Sprache, ohne Programmierkenntnisse (Weblate o. Ä.).

## Entscheidungen (Antworten)

1. **Deutsch und Englisch**, dazu der Aufbau für weitere Sprachen.
2. **Quellsprache Englisch**: Texte im Code sind englisch, Deutsch ist eine Übersetzung (`po/de.po`).
3. **Kommentare, Docstrings, README, CLAUDE.md bleiben vorerst deutsch** (Umstellung kurz vor der Veröffentlichung).
4. **gettext überall** (Kern, Kommandozeile, Oberfläche) – eine Datei je Sprache.
5. **Sprache aus dem System, umschaltbar in den Einstellungen, wirksam nach Neustart**; dazu allgemein: jede Einstellung,
   die erst nach einem Neustart wirkt, zeigt eine **farbige Meldung „Änderungen erst nach Neustart aktiv“** (kein
   Fenster).
6. **Symbole zweisprachig**: englische und deutsche Namen, die Suche findet beide.
7. **Zahlen je Sprache**: Deutsch mit Komma, Englisch mit Punkt; eingeben lässt sich immer beides.
8. **Platzhalter der Nummerierung je Sprache** (`{Nummer}` / `{Number}`), beide gelten immer; alte Dateien bleiben gültig.
9. **Tests**: jede Meldung übersetzt (sonst rot); Layout-Test mit den längeren Texten (Knöpfe, Panels; Bildschirmfotos
   zum Ansehen).

## Nicht enthalten

Weitere Sprachen als Deutsch/Englisch, Umstellen ohne Neustart, Übersetzung der Kommentare/Docstrings/README
(Roadmap 9), Rechts-nach-links-Sprachen, übersetzte Dateiformate (Schlüssel in `*.labelwerk` und `settings.json` bleiben
englisch wie bisher).

## 1 – Kern: `i18n.py` (ohne Qt, ohne neue Abhängigkeit)

- **Laden:** `po/<sprache>.po` liegt im Paket (`src/labelwerk/po/`), wird beim Start gelesen (eigener kleiner `.po`-Leser:
  `msgctxt`, `msgid`, `msgid_plural`, `msgstr[n]`, `Plural-Forms` für de/en, Fortsetzungszeilen, Escapes) – keine `.mo`-
  Dateien, kein Build-Schritt. Fehlerhafte/fehlende Datei → Englisch (Meldung auf stderr, kein Absturz).
- **API:** `_(text)`, `ngettext(einzahl, mehrzahl, n)`, `pgettext(kontext, text)` (gleiches Wort, andere Bedeutung,
  z. B. „Cut“ Schnitt/Ausschneiden); `N_(text)` markiert Texte in Tabellen (Übersetzung beim Anzeigen).
  `set_language(code)`, `language()`, `system_language()` (aus `LANGUAGE`/`LC_ALL`/`LC_MESSAGES`/`LANG`; nicht
  unterstützt → Englisch), `available()` (Sprachen mit `.po`, Name in eigener Sprache: „Deutsch“, „English“).
- **Zahlen:** `decimal()` (Komma bzw. Punkt), `number(wert, stellen)` für Meldungen („3,5 mm“ / „3.5 mm“); alle bisher
  fest mit Komma formatierten Maße (`labels.format_mm`, `mm_text`, Beschreibungen) gehen darüber.
- **Platzhalter in Texten:** benannt (`_("Label {label} does not fit the printer ({model}).").format(...)`), damit die
  Reihenfolge je Sprache frei ist; f-Strings werden dafür umgeschrieben.
- **Wann gilt die Sprache:** `cli.main` und `gui.app` setzen sie zuerst (Einstellung `language`, "" = System); Texte auf
  Modulebene (Tabellen wie `shortcuts.ACTIONS`, `MODES`, `TITLES`) sind mit `N_` markiert und werden beim Anzeigen
  übersetzt, nicht beim Import.

## 2 – Texte umstellen

- Jeder Text für Nutzer (Meldungen, Ausnahmen mit deutscher Meldung, CLI-Hilfe und -Ausgaben, GUI-Beschriftungen,
  Tooltips, Statusleiste, Dialoge, Tastenkürzel-Namen, Etikett-Beschreibungen, Rahmenarten, Barcode-Arten …) wird
  englisch und mit `_()` markiert; die heutigen deutschen Texte werden **wörtlich** zu `po/de.po` (Deutsch bleibt, wie es
  ist).
- **Werkzeug** `tools/i18n.py`: `extract` (AST: `_`, `N_`, `ngettext`, `pgettext` → `po/labelwerk.pot`, sortiert, mit
  Fundstellen), `update` (neue Texte in jede `.po` übernehmen, entfallene als veraltet kennzeichnen), `check` (wie der
  Test). Anleitung „Neue Sprache beisteuern“ in `po/README.md` (deutsch, vor Veröffentlichung englisch).
- **Qt-eigene Texte** (Standardknöpfe, Kontextmenü der Eingabefelder, Dateidialog): Qt-Übersetzung `qtbase_<sprache>`
  aus `QLibraryInfo` per `QTranslator`, wenn vorhanden.
- **argparse-eigene Texte** („usage:“, „error:“ …) übersetzt labelwerk selbst (`cli.ARGPARSE_TEXTS`, Kontext
  „argparse“); was eine andere Python-Version anders formuliert, bleibt englisch.
- **Zahlen im Etikett-Inhalt** (Excel-Zellen einer Serie) folgen der Region des Systems (`LC_NUMERIC`), nicht der
  Sprache der Oberfläche – dieselbe Datei druckt gleich, egal welche Sprache labelwerk zeigt (zur Abnahme).

## 3 – Sprachwahl und Neustart-Hinweis

- **Einstellung** `language` ("" = Sprache des Systems, "de", "en"); Einstellungen → Allgemein → „Sprache“ (Automatisch
  (Systemsprache: Deutsch) / Deutsch / English). CLI: `--lang de|en` (sonst Einstellung, sonst System).
- **Neustart-Hinweis allgemein:** Einstellungen, die erst nach einem Neustart wirken (`settings.RESTART_KEYS`:
  `language`, `start_zoom`): wirkt eine davon nach einem Neustart anders als jetzt (verglichen mit dem Stand beim
  Start, Sprache wirksam: „Automatisch“ = Systemsprache), steht unten im Einstellungsfenster neben SPEICHERN in Orange
  „Änderungen erst nach Neustart aktiv“ – in jedem Reiter sichtbar, auch beim erneuten Öffnen vor dem Neustart;
  zurückgestellt → verschwindet. (Nutzerwunsch: im Einstellungsfenster, nicht in der Statusleiste.)

## 4 – Zahlen, Platzhalter, Symbole

- **Zahlenfelder** (mm, pt, Modulbreite, Rahmen …): Anzeige mit dem Dezimaltrenner der Sprache (`QLocale` je Sprache),
  Eingabe von Komma und Punkt immer erlaubt (heutige Felder akzeptieren beides schon – vereinheitlichen).
- **Nummerierung:** Spalte heißt je Sprache „Nummer“ bzw. „Number“; `series.fill`/`missing` kennen beide Namen
  (`{Nummer}` und `{Number}` füllen dasselbe; `i18n.all_translations`), ebenso Spalten ohne Namen in der Kopfzeile
  („Spalte 3“ = „Column 3“). Benannte Spalten aus Dateien bleiben unverändert.
- **Symbole:** Katalog mit `names` {de, en} (Tabler: englischer Name aus dem Paket + deutsche Übersetzung der Kategorie/
  Synonyme wie bisher; ISO: deutscher Name aus `de.json`, englischer aus `tools/clipart/en.json` – die englischen
  Commons-Beschreibungen sind zu uneinheitlich, die Namen sind offizielle ISO-7010-Titel bzw. Übersetzungen der
  deutschen; eigene Zeichnungen und ISO 7000 ebenso in `en.json`), Gruppen/Untergruppen übersetzt, Anzeige in der eingestellten Sprache, Suche über beide Sprachen samt
  Synonymen; ältere Kataloge ohne `names` gehen weiter (Name gilt für beide). Neu erzeugt mit `tools/fetch_clipart.py`
  aus dem lokalen Zwischenspeicher (kein neuer Download nötig, Stand bleibt `commons.lock.json`).

## Nebenbei

- Überschrift „Vergrößern/Verkleinern“ im Reiter Layout war in der Standardbreite abgeschnitten (vom Layout-Test
  gefunden) → „Größe ändern“ / „Resize“; Abschnittstitel brechen an Leerzeichen um.

## Tests

- `i18n`: `.po`-Leser (Mehrzahl, Kontext, Escapes, defekte Datei), Sprachwahl (Umgebung, Einstellung, unbekannt →
  Englisch), Zahlenformat.
- **Vollständigkeit:** `labelwerk.pot` entspricht dem Code (`tools/i18n.py check`); jede `msgid` hat in `de.po` eine
  Übersetzung; Platzhalter `{name}` und `%`-Angaben sind in Übersetzung und Original gleich; kein deutscher Text mehr
  außerhalb von `_()` in Meldungen (Prüfung auf Umlaute/typische Wörter in String-Konstanten mit Ausnahmeliste).
- **Bestehende Tests** laufen auf Deutsch (conftest setzt `de`) – ihre Erwartungen bleiben wörtlich; neue Tests prüfen
  Stichproben auf Englisch (CLI-Fehler, Statusleiste, Panels).
- **Layout:** jedes Panel, die Statusleiste und die Dialoge in Englisch und Deutsch bei Standardbreite: kein Knopf/Label
  abgeschnitten (Textbreite ≤ verfügbare Breite), Bildschirmfotos für die Abnahme.
- Platzhalter `{Number}`/`{Nummer}`, Symbolsuche in beiden Sprachen, Neustart-Hinweis (erscheint, verschwindet).
