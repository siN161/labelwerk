# Translations

labelwerk is written in English; every other language is a file `<code>.po` in this folder (gettext format,
UTF-8). `labelwerk.pot` is the template with all texts – it is generated, not edited by hand.

## Contributing a new language

1. Copy `labelwerk.pot` to `<code>.po` (e.g. `fr.po`) and enter `Language: fr` and the `Plural-Forms` of the
   language in the header (list: GNU gettext, "Plural forms").
2. Translate every `msgstr` – with Poedit, Weblate or a text editor. Keep placeholders in curly braces
   (`{label}`, `{count}` …) unchanged; their order may change.
3. In `src/labelwerk/i18n.py` add the name of the language in itself (`NAMES`, e.g. `"fr": "Français"`) and, if it
   uses a decimal comma, `DECIMAL`.
4. Check: `python tools/i18n.py check` (missing translations, wrong placeholders, number of plural forms).
   The language appears in Settings → View → Language and with `labelwerk --lang <code>` as soon as the file
   exists – even when incomplete (missing texts stay English).

Notes for translators are `#.` comments above the text (e.g. what `{where}` contains); your own notes as `# …`
and uncertain translations (`#, fuzzy`) are kept by `tools/i18n.py update`.

## For developers

- Texts for users always in English and with `_("…")` (or `ngettext`, `pgettext`; mark tables at module level
  with `N_` and call `_()` when displaying), named placeholders: `_("… {name} …").format(name=…)`.
- After changing texts: `python tools/i18n.py update` (new template, new texts in every `.po`), then add the
  German translations in `de.po`. The test `test_every_text_is_translated` keeps everything complete,
  `test_no_german_text_outside_the_translation` finds German texts that are not translated.
