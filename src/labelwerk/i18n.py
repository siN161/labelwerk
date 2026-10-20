"""Translations without Qt and without an extra library: texts in the code are English, per language
one ``po/<code>.po`` in the package (read at startup – no ``.mo`` files, no build step).

``_("Text")`` translates, ``ngettext`` with plural, ``pgettext`` with context (same word,
different meaning), ``N_`` marks texts in module-level tables (translated only when
displayed). Placeholders are named (``_("… {label} …").format(label=…)``) so that each language
can choose its order. ``set_language`` applies to everything after it (CLI and GUI set it first).
"""
from __future__ import annotations

import gettext
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PO_DIR = Path(__file__).resolve().parent / "po"
SOURCE = "en"                               # language of the texts in the code
NAMES = {"de": "Deutsch", "en": "English"}  # name of a language in itself
DECIMAL = {"de": ","}                       # decimal separator (otherwise dot)
# Regions with decimal comma (language part of LC_NUMERIC/LANG) – for numbers in label content
COMMA_REGIONS = frozenset({"de", "fr", "es", "it", "nl", "pt", "pl", "cs", "sk", "da", "sv", "nb",
                           "nn", "fi", "ru", "uk", "tr", "hu", "ro", "hr", "sl", "el", "bg", "lt",
                           "lv", "et", "id", "vi"})


@dataclass
class Catalog:
    """Translations of a language: (context, text) → translation or plural forms."""
    language: str
    messages: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    plural: str = "n != 1"

    def plural_index(self, n: int) -> int:
        try:
            return int(gettext.c2py(self.plural)(n))
        except (ValueError, SyntaxError):
            raise PoError(f"Plural-Forms: {self.plural!r}") from None


class PoError(ValueError):
    """``.po`` file not readable."""


_ESCAPE = re.compile(r'\\(?:([ntrabfv"\\?\'])|([0-7]{1,3})|x([0-9a-fA-F]+))')
_SIMPLE = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", '"': '"',
           "\\": "\\", "?": "?", "'": "'"}


def unquote(text: str, where: str) -> str:
    """Text in quotes of a ``.po`` line with the escapes of C (``\\n``, ``\\"``,
    octal, ``\\x``) – without evaluating Python syntax."""
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
    """Content of a ``.po`` file; empty, uncertain (``#, fuzzy``) and obsolete (``#~``)
    translations do not count."""
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
                    catalog.plural_index(1)          # check the expression
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
    """Languages labelwerk supports: English and every one with a ``.po``."""
    return sorted({SOURCE, *(p.stem for p in PO_DIR.glob("*.po"))})


def system_language(environ=None) -> str:
    """System language as with GNU gettext: locale from ``LC_ALL`` › ``LC_MESSAGES`` ›
    ``LANG``; if it is “C”/“POSIX” (or missing), English – otherwise first the list ``LANGUAGE``
    (“de_AT:de:en”), then the locale; what labelwerk does not support becomes English."""
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
    """Set the language ("" = system language); unknown or ``.po`` broken → English (note on
    stderr). Returns the valid language."""
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
    """A text in every language labelwerk supports (original first) – for names that in every
    language should apply (placeholder ``{Nummer}``/``{Number}``)."""
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
    """Like ``N_`` with context (translated with ``pgettext(context, text)``)."""
    return text


def N_(text: str) -> str:
    """Only mark (for ``tools/i18n.py``); translated when displayed with ``_``."""
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
    """Decimal separator of the language: “,” or “.”."""
    return DECIMAL.get(_language, ".")


def thousands(value: int) -> str:
    """Integer with the language's thousands separator: “1.000.000” or “1,000,000”."""
    return f"{value:,}".replace(",", "." if decimal() == "," else ",")


def parse_number(text: str) -> float:
    """Number as typed: comma and dot both count as decimal separator (otherwise ValueError)."""
    return float(text.strip().replace(",", "."))


def content_decimal(environ=None) -> str:
    """Decimal separator for numbers in label content (Excel cells of a series): like the
    system's regional setting (``LC_ALL`` › ``LC_NUMERIC`` › ``LANG``), not the language of the
    interface – the same file prints with a comma in Germany whichever language labelwerk shows."""
    env = os.environ if environ is None else environ
    for name in ("LC_ALL", "LC_NUMERIC", "LANG"):
        value = env.get(name, "")
        if value:
            code = value.split(".")[0].split("@")[0].split("_")[0].lower()
            return "," if code in COMMA_REGIONS else "."
    return "."


def number(value: float, digits: int | None = None) -> str:
    """Number for messages: ``digits`` decimal places (None: as short as possible, “:g”), with the
    language's decimal separator."""
    text = f"{value:g}" if digits is None else f"{value:.{digits}f}"
    return text.replace(".", decimal())
