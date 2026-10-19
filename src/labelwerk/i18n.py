"""Übersetzungen ohne Qt und ohne zusätzliche Bibliothek: Texte im Code sind englisch, je Sprache
eine ``po/<code>.po`` im Paket (gelesen beim Start – keine ``.mo``-Dateien, kein Build-Schritt).

``_("Text")`` übersetzt, ``ngettext`` mit Mehrzahl, ``pgettext`` mit Kontext (gleiches Wort,
andere Bedeutung), ``N_`` markiert Texte in Tabellen auf Modulebene (übersetzt wird erst beim
Anzeigen). Platzhalter sind benannt (``_("… {label} …").format(label=…)``), damit jede Sprache ihre
Reihenfolge wählen kann. ``set_language`` gilt für alles danach (CLI und GUI setzen sie zuerst).
"""
from __future__ import annotations

import gettext
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PO_DIR = Path(__file__).resolve().parent / "po"
SOURCE = "en"                               # Sprache der Texte im Code
NAMES = {"de": "Deutsch", "en": "English"}  # Name einer Sprache in ihr selbst
DECIMAL = {"de": ","}                       # Dezimaltrenner (sonst Punkt)
# Regionen mit Dezimalkomma (Sprachteil von LC_NUMERIC/LANG) – für Zahlen im Etikett-Inhalt
COMMA_REGIONS = frozenset({"de", "fr", "es", "it", "nl", "pt", "pl", "cs", "sk", "da", "sv", "nb",
                           "nn", "fi", "ru", "uk", "tr", "hu", "ro", "hr", "sl", "el", "bg", "lt",
                           "lv", "et", "id", "vi"})


@dataclass
class Catalog:
    """Übersetzungen einer Sprache: (Kontext, Text) → Übersetzung bzw. Mehrzahlformen."""
    language: str
    messages: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    plural: str = "n != 1"

    def plural_index(self, n: int) -> int:
        try:
            return int(gettext.c2py(self.plural)(n))
        except (ValueError, SyntaxError):
            raise PoError(f"Plural-Forms: {self.plural!r}") from None


class PoError(ValueError):
    """``.po``-Datei nicht lesbar."""


_ESCAPE = re.compile(r'\\(?:([ntrabfv"\\?\'])|([0-7]{1,3})|x([0-9a-fA-F]+))')
_SIMPLE = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", '"': '"',
           "\\": "\\", "?": "?", "'": "'"}


def unquote(text: str, where: str) -> str:
    """Text in Anführungszeichen einer ``.po``-Zeile mit den Escapes von C (``\\n``, ``\\"``,
    oktal, ``\\x``) – ohne Python-Syntax auszuwerten."""
    text = text.strip()
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        raise PoError(f"{where}: quoted text expected")
    body = text[1:-1]
    if re.search(r'(?<!\\)(?:\\\\)*"', body):
        raise PoError(f"{where}: unescaped quote")
    rest = _ESCAPE.sub("", body)
    if "\\" in rest:
        raise PoError(f"{where}: invalid escape")
    return _ESCAPE.sub(lambda m: _SIMPLE[m[1]] if m[1] else chr(int(m[2], 8)) if m[2]
                       else chr(int(m[3], 16)), body)


def parse_po(text: str, language: str = "") -> Catalog:
    """Inhalt einer ``.po``-Datei; leere, unsichere (``#, fuzzy``) und veraltete (``#~``)
    Übersetzungen zählen nicht."""
    catalog = Catalog(language)
    entry: dict[str, str] = {}
    fuzzy = next_fuzzy = False
    key = None

    def finish():
        nonlocal entry, fuzzy
        if "msgid" in entry:
            forms = [entry[k] for k in sorted(entry, key=_form_order) if k.startswith("msgstr")]
            if entry["msgid"] == "" and "msgctxt" not in entry:
                m = re.search(r"plural=([^;\n]+)", forms[0] if forms else "")
                if m:
                    catalog.plural = m[1].strip()
                    catalog.plural_index(1)          # Ausdruck prüfen
            elif forms and all(forms) and not fuzzy:
                catalog.messages[(entry.get("msgctxt", ""), entry["msgid"])] = forms
        entry, fuzzy = {}, False

    for number, line in enumerate(text.splitlines(), start=1):
        where = f"line {number}"
        line = line.strip()
        if line.startswith("#,") and "fuzzy" in line:
            next_fuzzy = True
        if not line or line.startswith("#"):
            continue
        if line.startswith('"'):
            if key is None:
                raise PoError(f"{where}: continuation without entry")
            entry[key] += unquote(line, where)
            continue
        m = re.match(r"(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+(.*)$", line)
        if m is None:
            raise PoError(f"{where}: unknown line")
        key = m[1]
        if key in ("msgctxt", "msgid") and (any(k.startswith("msgstr") for k in entry)
                                           or key == "msgctxt" and "msgid" in entry):
            finish()
        if key in ("msgctxt", "msgid") and not entry:
            fuzzy, next_fuzzy = next_fuzzy, False
        entry[key] = unquote(m[2], where)
    finish()
    return catalog


def _form_order(key: str) -> int:
    m = re.search(r"\[(\d+)\]", key)
    return int(m[1]) if m else 0


_catalog: Catalog | None = None
_language = SOURCE


def available() -> list[str]:
    """Sprachen, die labelwerk kann: Englisch und jede mit ``.po``."""
    return sorted({SOURCE, *(p.stem for p in PO_DIR.glob("*.po"))})


def system_language(environ=None) -> str:
    """Sprache des Systems wie bei GNU gettext: Gebietsschema aus ``LC_ALL`` › ``LC_MESSAGES`` ›
    ``LANG``; ist es „C“/„POSIX“ (oder fehlt), Englisch – sonst zuerst die Liste ``LANGUAGE``
    („de_AT:de:en“), dann das Gebietsschema; was labelwerk nicht kann, wird Englisch."""
    env = os.environ if environ is None else environ
    known = available()

    def code(value: str) -> str:
        return value.split(".")[0].split("@")[0].split("_")[0].lower()
    locale = next((env[n] for n in ("LC_ALL", "LC_MESSAGES", "LANG") if env.get(n)), "")
    if code(locale) in ("", "c", "posix"):
        return SOURCE
    for part in [*env.get("LANGUAGE", "").split(":"), locale]:
        if code(part) in known:
            return code(part)
    return SOURCE


def set_language(code: str = "") -> str:
    """Sprache setzen ("" = Systemsprache); unbekannt oder ``.po`` defekt → Englisch (Hinweis auf
    stderr). Zurück kommt die gültige Sprache."""
    global _catalog, _language
    code = code or system_language()
    if code not in available():
        code = SOURCE
    _catalog, _language = None, code
    if code != SOURCE:
        try:
            _catalog = parse_po((PO_DIR / f"{code}.po").read_text(encoding="utf-8-sig"), code)
        except (OSError, PoError, UnicodeDecodeError) as e:
            print(f"labelwerk: translation {code} unreadable ({e}) – using English", file=sys.stderr)
            _language = SOURCE
    return _language


_all_cache: dict[tuple[str, str], tuple[str, ...]] = {}


def all_translations(context: str, text: str) -> tuple[str, ...]:
    """Ein Text in jeder Sprache, die labelwerk kann (Original zuerst) – für Namen, die in jeder
    Sprache gelten sollen (Platzhalter ``{Nummer}``/``{Number}``)."""
    key = (context, text)
    if key not in _all_cache:
        found = [text]
        for code in available():
            if code == SOURCE:
                continue
            try:
                catalog = parse_po((PO_DIR / f"{code}.po").read_text(encoding="utf-8-sig"), code)
            except (OSError, PoError, UnicodeDecodeError):
                continue
            for form in catalog.messages.get(key, []):
                if form not in found:
                    found.append(form)
        _all_cache[key] = tuple(found)
    return _all_cache[key]


def language() -> str:
    return _language


def _(text: str) -> str:
    return pgettext("", text)


def NP_(context: str, text: str) -> str:
    """Wie ``N_`` mit Kontext (übersetzt wird mit ``pgettext(context, text)``)."""
    return text


def N_(text: str) -> str:
    """Nur markieren (für ``tools/i18n.py``); übersetzt wird beim Anzeigen mit ``_``."""
    return text


def pgettext(context: str, text: str) -> str:
    if _catalog is None:
        return text
    forms = _catalog.messages.get((context, text))
    return forms[0] if forms else text


def ngettext(singular: str, plural: str, n: int) -> str:
    if _catalog is not None:
        forms = _catalog.messages.get(("", singular))
        if forms:
            index = _catalog.plural_index(n)
            return forms[min(index, len(forms) - 1)]
    return singular if n == 1 else plural


def decimal() -> str:
    """Dezimaltrenner der Sprache: „,“ bzw. „.“."""
    return DECIMAL.get(_language, ".")


def thousands(value: int) -> str:
    """Ganze Zahl mit Tausendertrennung der Sprache: „1.000.000“ bzw. „1,000,000“."""
    return f"{value:,}".replace(",", "." if decimal() == "," else ",")


def parse_number(text: str) -> float:
    """Zahl, wie getippt: Komma und Punkt gelten als Dezimaltrenner (ValueError sonst)."""
    return float(text.strip().replace(",", "."))


def content_decimal(environ=None) -> str:
    """Dezimaltrenner für Zahlen im Etikett-Inhalt (Excel-Zellen einer Serie): wie die
    Regionaleinstellung des Systems (``LC_ALL`` › ``LC_NUMERIC`` › ``LANG``), nicht die Sprache der
    Oberfläche – dieselbe Datei druckt in Deutschland mit Komma, egal welche Sprache labelwerk zeigt."""
    env = os.environ if environ is None else environ
    for name in ("LC_ALL", "LC_NUMERIC", "LANG"):
        value = env.get(name, "")
        if value:
            code = value.split(".")[0].split("@")[0].split("_")[0].lower()
            return "," if code in COMMA_REGIONS else "."
    return "."


def number(value: float, digits: int | None = None) -> str:
    """Zahl für Meldungen: ``digits`` Nachkommastellen (None: so kurz wie möglich, „:g“), mit dem
    Dezimaltrenner der Sprache."""
    text = f"{value:g}" if digits is None else f"{value:.{digits}f}"
    return text.replace(".", decimal())
