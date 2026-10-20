"""Favourites: saved labels in the folder ``$XDG_DATA_HOME/labelwerk/favoriten`` (without Qt).

A favourite is a ``*.labelwerk`` file; its name is the file name without extension. The GUI
opens it as a new, unnamed label (template) – the original stays unchanged.
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .document import Document
from .i18n import N_, _
from .storage import SUFFIX, save

MAX_NAME_BYTES = 200        # file name at most 255 bytes (extension, reserve)
_EXISTS = N_("Favorite “{name}” already exists")


@dataclass(frozen=True)
class Favorite:
    name: str
    path: Path


def favorites_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "labelwerk" / "favoriten"


def favorites() -> list[Favorite]:
    """All favourites, sorted case-insensitively; none if the folder is missing."""
    try:
        paths = [p for p in favorites_dir().iterdir()
                 if p.is_file() and p.suffix == SUFFIX and not p.name.startswith(".")]
    except OSError:
        return []
    return [Favorite(p.stem, p) for p in sorted(paths, key=lambda p: (p.stem.casefold(), p.stem))]


def find(name: str) -> Favorite | None:
    return next((f for f in favorites() if f.name == name), None)


def _checked(name: str) -> str:
    """Name as file name: NFC (names that look alike are equal), trimmed, not empty, without
    path and control characters, not hidden, not too long (in bytes)."""
    name = unicodedata.normalize("NFC", name.strip())
    if (not name or len(name.encode("utf-8")) > MAX_NAME_BYTES or name.startswith(".")
            or any(c in "/\\" or unicodedata.category(c) == "Cc" for c in name)):
        raise ValueError(_("Invalid name for the favorite: “{name}” (not empty, not too long, "
                           "without / and \\ and control characters, not starting with a dot)")
                         .format(name=name))
    return name


def add(doc: Document, name: str, overwrite: bool = False) -> Favorite:
    """Save a label as favourite; an existing name without ``overwrite``: ``FileExistsError``."""
    name = _checked(name)
    path = favorites_dir() / f"{name}{SUFFIX}"
    if path.exists() and not overwrite:
        raise FileExistsError(_(_EXISTS).format(name=name))
    path.parent.mkdir(parents=True, exist_ok=True)
    save(doc, path)
    return Favorite(name, path)


def rename(favorite: Favorite, name: str) -> Favorite:
    name = _checked(name)
    path = favorite.path.with_name(f"{name}{SUFFIX}")
    if not favorite.path.exists():
        raise FileNotFoundError(_("Favorite “{name}” not found").format(name=favorite.name))
    if path.exists() and not path.samefile(favorite.path):     # case-insensitive file systems
        raise FileExistsError(_(_EXISTS).format(name=name))
    favorite.path.rename(path)
    return Favorite(name, path)


def remove(favorite: Favorite) -> None:
    favorite.path.unlink(missing_ok=True)
