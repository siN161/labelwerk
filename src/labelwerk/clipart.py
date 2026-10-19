"""Symbol-Bibliothek (ClipArt) ohne Qt: Katalog, Suche, eigener Ordner, Zuletzt verwendet.

Die mitgelieferten Symbole liegen in ``clipart_data/clipart.zip`` (Katalog ``catalog.json`` und
SVG-Dateien; erzeugt von ``tools/fetch_clipart.py``, Lizenzen in ``clipart_data/LICENSES.md``);
das Archiv wird beim ersten Gebrauch einmal ganz gelesen (ca. 6 MB).
Eigene Symbole (SVG/PNG) liest ``own_symbols`` aus ``$XDG_DATA_HOME/labelwerk/symbole`` –
bei jedem Aufruf neu, damit neu abgelegte Dateien gleich erscheinen.
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import i18n
from .i18n import N_, _

ARCHIVE = Path(__file__).with_name("clipart_data") / "clipart.zip"
LICENSES = ARCHIVE.with_name("LICENSES.md")
# Anzeigenamen mit N_ markiert: beim Anzeigen ``_(name)``
GROUPS = (("elektro", N_("Electrical")), ("versand", N_("Shipping")), ("sicherheit", N_("Safety")),
          ("allgemein", N_("General")), ("eigene", N_("My symbols")))
ALLOWED_LICENSES = frozenset({"MIT", "Public domain", "CC0"})
OWN_SUFFIXES = (".svg", ".png")
OWN_LICENSE = N_("your own file")       # übersetzt in ``own_symbols``
OWN_SUBGROUP = N_("My symbols")
RECENT_LIMIT = 24
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Symbol:
    id: str              # „labelwerk/erde“, „iso7010/W012“, „tabler/outline/home“, „ordner/Datei.svg“
    group: str           # Schlüssel aus GROUPS
    subgroup: str        # z. B. „Warnzeichen“, „Gebäude“ (in der Sprache von labelwerk)
    name: str            # Anzeigename in der Sprache von labelwerk
    keywords: tuple[str, ...]
    file: str            # Pfad im Archiv bzw. im eigenen Ordner
    source: str
    url: str
    author: str
    license: str
    names: tuple[str, ...] = ()   # Name in jeder Sprache (Suche findet alle)
    subgroups: tuple[str, ...] = ()   # Untergruppe in jeder Sprache (ebenso)


def _fold(text: str) -> str:
    """Für die Suche: klein, Umlaute als ae/oe/ue/ss."""
    return text.casefold().translate(_UMLAUTS)


@lru_cache(maxsize=1)
def _files() -> dict[str, bytes]:
    """Inhalt des Archivs (einmal gelesen: jedes Öffnen parst sonst über 6000 Einträge)."""
    with zipfile.ZipFile(ARCHIVE) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def catalog() -> tuple[Symbol, ...]:
    """Alle mitgelieferten Symbole, Namen und Untergruppen in der Sprache von labelwerk (je Sprache
    einmal gelesen)."""
    return _catalog(i18n.language())


@lru_cache(maxsize=4)
def _catalog(language: str) -> tuple[Symbol, ...]:
    entries = json.loads(_files()["catalog.json"])["symbols"]

    def pick(entry: dict, key: str) -> str:   # ältere Kataloge: nur der deutsche Name
        return entry.get(key + "s", {}).get(language) or entry[key]
    return tuple(Symbol(id=e["id"], group=e["group"], subgroup=pick(e, "subgroup"),
                        name=pick(e, "name"), keywords=tuple(e["keywords"]), file=e["file"],
                        source=e["source"], url=e["url"], author=e["author"], license=e["license"],
                        names=tuple(dict.fromkeys([*e.get("names", {}).values(), e["name"]])),
                        subgroups=tuple(dict.fromkeys([*e.get("subgroups", {}).values(),
                                                       e["subgroup"]])))
                 for e in entries)


@dataclass(frozen=True)
class _Entry:
    """Gefaltete Suchtexte eines Symbols."""
    name: str                     # ganzer Name
    words: tuple[str, ...]        # Wörter des Namens
    keywords: tuple[str, ...]     # Suchbegriffe
    text: str                     # alles zusammen (Teilwortsuche)


def _entry(s: Symbol) -> _Entry:
    """Suchtexte: Name in jeder Sprache (Anzeigename zuerst), Untergruppe, Suchbegriffe."""
    names = [_fold(n) for n in dict.fromkeys([s.name, *s.names])]
    keywords = tuple(_fold(k) for k in s.keywords)
    return _Entry(" / ".join(names), tuple(w for n in names for w in _WORD.findall(n)), keywords,
                  " ".join((*names, *(_fold(g) for g in dict.fromkeys([s.subgroup, *s.subgroups])),
                            *keywords)))


def _index() -> dict[str, tuple[Symbol, _Entry]]:
    return _index_for(i18n.language())


@lru_cache(maxsize=4)
def _index_for(language: str) -> dict[str, tuple[Symbol, _Entry]]:
    return {s.id: (s, _entry(s)) for s in _catalog(language)}


def own_dir() -> Path:
    """Ordner für eigene Symbole (``$XDG_DATA_HOME/labelwerk/symbole``)."""
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "labelwerk" / "symbole"


def own_symbols(directory: Path | None = None) -> list[Symbol]:
    """SVG- und PNG-Dateien im eigenen Ordner (Name = Dateiname ohne Endung); fehlt der
    Ordner, keine."""
    directory = Path(directory) if directory is not None else own_dir()
    try:
        paths = sorted((p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")
                        and p.suffix.lower() in OWN_SUFFIXES), key=lambda p: p.name.casefold())
    except OSError:
        return []
    return [Symbol(id=f"ordner/{p.name}", group="eigene", subgroup=_(OWN_SUBGROUP), name=p.stem,
                   keywords=(), file=str(p), source=p.name, url="", author="",
                   license=_(OWN_LICENSE)) for p in paths]


def symbols(group: str | None = None) -> list[Symbol]:
    """Symbole einer Gruppe (None = alle, eigene zuletzt)."""
    everything = [*catalog(), *own_symbols()] if group in (None, "eigene") else catalog()
    return [s for s in everything if group is None or s.group == group]


def find(symbol_id: str) -> Symbol | None:
    if symbol_id.startswith("ordner/"):
        return next((s for s in own_symbols() if s.id == symbol_id), None)
    entry = _index().get(symbol_id)
    return entry[0] if entry else None


def resolve(ids: list[str]) -> list[Symbol]:
    """Symbole zu ids (Zuletzt verwendet, Favoriten); unbekannte werden übergangen."""
    return [s for s in map(find, ids) if s is not None]


def _rank(entry: _Entry, word: str) -> int:
    """Wie gut ``word`` passt: 0 genau ein Namenswort oder Suchbegriff (Fachkürzel „PE“),
    1 ein Namenswort beginnt damit, 2 ein Suchbegriff beginnt damit, 3 Teil des Namens,
    4 sonst (Teil von Suchbegriff oder Untergruppe)."""
    if word in entry.words or word in entry.keywords:
        return 0
    if any(w.startswith(word) for w in entry.words):
        return 1
    if any(k.startswith(word) for k in entry.keywords):
        return 2
    return 3 if word in entry.name else 4


def search(text: str, group: str | None = None) -> list[Symbol]:
    """Alle Wörter von ``text`` müssen als Teilwort vorkommen (Name, Untergruppe,
    Suchbegriffe; ohne Groß/Klein, ä = ae). Reihenfolge nach ``_rank`` des ersten Worts,
    sonst wie im Katalog. Leer: die ganze Gruppe."""
    words = _fold(text).split()
    pool = symbols(group)
    if not words:
        return pool
    index = _index()
    ranked = []
    for position, symbol in enumerate(pool):
        entry = index[symbol.id][1] if symbol.id in index else _entry(symbol)
        if all(word in entry.text for word in words):
            ranked.append((_rank(entry, words[0]), position, symbol))
    return [symbol for __, __, symbol in sorted(ranked, key=lambda r: r[:2])]


def data(symbol: Symbol) -> bytes:
    """Die Datei des Symbols (SVG bzw. bei eigenen auch PNG)."""
    if symbol.group == "eigene":
        return Path(symbol.file).read_bytes()
    return _files()[symbol.file]


def is_vector(symbol: Symbol) -> bool:
    return symbol.file.lower().endswith(".svg")


def add_recent(recent: list[str], symbol_id: str, limit: int = RECENT_LIMIT) -> list[str]:
    """„Zuletzt verwendet“: ``symbol_id`` nach vorn, ohne Doppelte, höchstens ``limit``."""
    return [symbol_id, *(i for i in recent if i != symbol_id)][:limit]
