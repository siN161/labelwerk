"""Favoriten: gespeicherte Etiketten im Ordner ``$XDG_DATA_HOME/labelwerk/favoriten`` (ohne Qt).

Ein Favorit ist eine ``*.labelwerk``-Datei; sein Name ist der Dateiname ohne Endung. Die GUI
öffnet ihn als neues, unbenanntes Etikett (Vorlage) – das Original bleibt unverändert.
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .document import Document
from .storage import SUFFIX, save

MAX_NAME_BYTES = 200        # Dateiname höchstens 255 Bytes (Endung, Reserve)


@dataclass(frozen=True)
class Favorite:
    name: str
    path: Path


def favorites_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "labelwerk" / "favoriten"


def favorites() -> list[Favorite]:
    """Alle Favoriten, sortiert ohne Groß/Klein; fehlt der Ordner, keine."""
    try:
        paths = [p for p in favorites_dir().iterdir()
                 if p.is_file() and p.suffix == SUFFIX and not p.name.startswith(".")]
    except OSError:
        return []
    return [Favorite(p.stem, p) for p in sorted(paths, key=lambda p: (p.stem.casefold(), p.stem))]


def find(name: str) -> Favorite | None:
    return next((f for f in favorites() if f.name == name), None)


def _checked(name: str) -> str:
    """Name als Dateiname: NFC (gleich aussehende Namen sind gleich), getrimmt, nicht leer, ohne
    Pfad- und Steuerzeichen, nicht versteckt, nicht zu lang (in Bytes)."""
    name = unicodedata.normalize("NFC", name.strip())
    if (not name or len(name.encode("utf-8")) > MAX_NAME_BYTES or name.startswith(".")
            or any(c in "/\\" or unicodedata.category(c) == "Cc" for c in name)):
        raise ValueError(f"Name für den Favoriten ungültig: „{name}“ (nicht leer, nicht zu lang, "
                         f"ohne / und \\ und Steuerzeichen, nicht mit Punkt beginnend)")
    return name


def add(doc: Document, name: str, overwrite: bool = False) -> Favorite:
    """Etikett als Favorit speichern; vorhandener Name ohne ``overwrite``: ``FileExistsError``."""
    name = _checked(name)
    path = favorites_dir() / f"{name}{SUFFIX}"
    if path.exists() and not overwrite:
        raise FileExistsError(f"Favorit „{name}“ gibt es schon")
    path.parent.mkdir(parents=True, exist_ok=True)
    save(doc, path)
    return Favorite(name, path)


def rename(favorite: Favorite, name: str) -> Favorite:
    name = _checked(name)
    path = favorite.path.with_name(f"{name}{SUFFIX}")
    if not favorite.path.exists():
        raise FileNotFoundError(f"Favorit „{favorite.name}“ nicht gefunden")
    if path.exists() and not path.samefile(favorite.path):     # Groß/Klein-Dateisysteme
        raise FileExistsError(f"Favorit „{name}“ gibt es schon")
    favorite.path.rename(path)
    return Favorite(name, path)


def remove(favorite: Favorite) -> None:
    favorite.path.unlink(missing_ok=True)
