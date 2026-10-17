"""Schriften finden (fontconfig) und laden – UI-unabhängig.

Ohne fontconfig (fc-list/fc-match) wird auf DejaVu Sans zurückgefallen.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

DEFAULT_FAMILY = "DejaVu Sans"
_DEJAVU_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF",
                "/usr/share/fonts/dejavu-sans-fonts")


@dataclass(frozen=True)
class FontMatch:
    path: str
    family: str          # tatsächlich gefundene Familie
    bold: bool           # Datei ist wirklich fett
    italic: bool         # Datei ist wirklich kursiv/schräg


def _run(*args: str) -> str | None:
    if shutil.which(args[0]) is None:
        return None
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10,
                              check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


@lru_cache(maxsize=1)
def families() -> list[str]:
    """Installierte Schriftfamilien, sortiert."""
    # %{family[0]}: erster Familienname je Schrift, ohne fontconfig-Maskierung
    out = _run("fc-list", "-f", "%{family[0]}\\n", ":")
    if not out:
        return [DEFAULT_FAMILY]
    names = {line.strip() for line in out.splitlines() if line.strip()}
    return sorted(names, key=str.casefold)


def _escape(name: str) -> str:
    """Sonderzeichen des fontconfig-Musters mit Backslash maskieren."""
    return "".join("\\" + c if c in "\\-:,=" else c for c in name)


@lru_cache(maxsize=256)
def resolve(family: str | None, bold: bool, italic: bool) -> FontMatch:
    """Datei zu Familie + fett/kursiv; fontconfig ersetzt Fehlendes durch Ähnliches."""
    family = family or DEFAULT_FAMILY
    # maskiert; ein führendes "-" wird zu "\\-" und ist so keine Option
    pattern = _escape(family) + (":bold" if bold else ":weight=regular") + (":italic" if italic else ":roman")
    out = _run("fc-match", "-f", "%{file}|%{family}|%{style}", pattern)
    if out and out.count("|") >= 2:
        path, found, style = out.split("|", 2)
        found = found.split(",")[0]
        style = style.casefold()
        return FontMatch(path, found, bold=any(w in style for w in ("bold", "black", "heavy")),
                         italic=any(w in style for w in ("italic", "oblique")))
    return _dejavu_fallback(bold)


def _dejavu_fallback(bold: bool) -> FontMatch:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for folder in _DEJAVU_DIRS:
        path = Path(folder) / name
        if path.exists():
            return FontMatch(str(path), DEFAULT_FAMILY, bold=bold, italic=False)
    return FontMatch("", DEFAULT_FAMILY, bold=False, italic=False)   # PIL-Standardschrift


@lru_cache(maxsize=512)
def load(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Schrift in Druckpunkten laden (gecacht)."""
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)
