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

ARCHIVE = Path(__file__).with_name("clipart_data") / "clipart.zip"
LICENSES = ARCHIVE.with_name("LICENSES.md")
GROUPS = (("elektro", "Elektro"), ("versand", "Versand"), ("sicherheit", "Sicherheit"),
          ("allgemein", "Allgemein"), ("eigene", "Eigene"))
ALLOWED_LICENSES = frozenset({"MIT", "Public domain", "CC0"})
OWN_SUFFIXES = (".svg", ".png")
OWN_LICENSE = "eigene Datei"
RECENT_LIMIT = 24
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Symbol:
    id: str              # „labelwerk/erde“, „iso7010/W012“, „tabler/outline/home“, „ordner/Datei.svg“
    group: str           # Schlüssel aus GROUPS
    subgroup: str        # z. B. „Warnzeichen“, „Gebäude“
    name: str            # deutscher Anzeigename
    keywords: tuple[str, ...]
    file: str            # Pfad im Archiv bzw. im eigenen Ordner
    source: str
    url: str
    author: str
    license: str


def _fold(text: str) -> str:
    """Für die Suche: klein, Umlaute als ae/oe/ue/ss."""
    return text.casefold().translate(_UMLAUTS)


@lru_cache(maxsize=1)
def _files() -> dict[str, bytes]:
    """Inhalt des Archivs (einmal gelesen: jedes Öffnen parst sonst über 6000 Einträge)."""
    with zipfile.ZipFile(ARCHIVE) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@lru_cache(maxsize=1)
def catalog() -> tuple[Symbol, ...]:
    """Alle mitgelieferten Symbole (einmal gelesen)."""
    entries = json.loads(_files()["catalog.json"])["symbols"]
    return tuple(Symbol(id=e["id"], group=e["group"], subgroup=e["subgroup"], name=e["name"],
                        keywords=tuple(e["keywords"]), file=e["file"], source=e["source"],
                        url=e["url"], author=e["author"], license=e["license"])
                 for e in entries)


@dataclass(frozen=True)
class _Entry:
    """Gefaltete Suchtexte eines Symbols."""
    name: str                     # ganzer Name
    words: tuple[str, ...]        # Wörter des Namens
    keywords: tuple[str, ...]     # Suchbegriffe
    text: str                     # alles zusammen (Teilwortsuche)


def _entry(s: Symbol) -> _Entry:
    name = _fold(s.name)
    keywords = tuple(_fold(k) for k in s.keywords)
    return _Entry(name, tuple(_WORD.findall(name)), keywords,
                  " ".join((name, _fold(s.subgroup), *keywords)))


@lru_cache(maxsize=1)
def _index() -> dict[str, tuple[Symbol, _Entry]]:
    return {s.id: (s, _entry(s)) for s in catalog()}


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
    return [Symbol(id=f"ordner/{p.name}", group="eigene", subgroup="Eigene", name=p.stem,
                   keywords=(), file=str(p), source=p.name, url="", author="",
                   license=OWN_LICENSE) for p in paths]


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
    return [symbol for _, _, symbol in sorted(ranked, key=lambda r: r[:2])]


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
