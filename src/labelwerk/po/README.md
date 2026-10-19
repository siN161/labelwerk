# Übersetzungen

labelwerk ist auf Englisch geschrieben; jede andere Sprache ist eine Datei `<code>.po` in diesem Ordner
(gettext-Format, UTF-8). `labelwerk.pot` ist die Vorlage mit allen Texten – sie wird erzeugt, nicht von Hand
bearbeitet.

## Eine neue Sprache beisteuern

1. `labelwerk.pot` nach `<code>.po` kopieren (z. B. `fr.po`) und im Kopf `Language: fr` sowie die
   `Plural-Forms` der Sprache eintragen (Liste: GNU gettext, „Plural forms“).
2. Jedes `msgstr` übersetzen – mit Poedit, Weblate oder einem Texteditor. Platzhalter in geschweiften
   Klammern (`{label}`, `{count}` …) unverändert übernehmen; ihre Reihenfolge darf sich ändern.
3. In `src/labelwerk/i18n.py` den Namen der Sprache in ihr selbst (`NAMES`, z. B. `"fr": "Français"`) und, falls
   sie ein Dezimalkomma hat, `DECIMAL` ergänzen.
4. Prüfen: `python tools/i18n.py check` (fehlende Übersetzungen, falsche Platzhalter, Zahl der Mehrzahlformen).
   Die Sprache erscheint in Einstellungen → Ansicht → Sprache und bei `labelwerk --lang <code>`, sobald die
   Datei da ist – auch unvollständig (fehlende Texte bleiben englisch).

Hinweise für Übersetzer stehen als `#.`-Kommentar über dem Text (z. B. was `{where}` enthält); eigene Notizen
als `# …` und unsichere Übersetzungen (`#, fuzzy`) bleiben bei `tools/i18n.py update` erhalten.

## Für Entwickler

- Texte für Nutzer immer englisch und mit `_("…")` (bzw. `ngettext`, `pgettext`; Tabellen auf Modulebene mit
  `N_` markieren und beim Anzeigen `_()`), Platzhalter benannt: `_("… {name} …").format(name=…)`.
- Nach Textänderungen: `python tools/i18n.py update` (Vorlage neu, neue Texte in jede `.po`), dann die
  deutschen Übersetzungen in `de.po` ergänzen. Der Test `test_every_text_is_translated` hält alles vollständig,
  `test_no_german_text_outside_the_translation` findet deutsche Texte, die nicht übersetzt werden.
