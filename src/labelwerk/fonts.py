"""Find and load fonts (fontconfig) – independent of the UI.

Without fontconfig (fc-list/fc-match) it falls back to DejaVu Sans.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from .i18n import _

DEFAULT_FAMILY = "DejaVu Sans"
_DEJAVU_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/TTF",
                "/usr/share/fonts/dejavu-sans-fonts")


@dataclass(frozen=True)
class FontMatch:
    path: str
    family: str          # family actually found
    bold: bool           # file really is bold
    italic: bool         # file really is italic/oblique


def _run(*args: str) -> str | None:
    if shutil.which(args[0]) is None:
        return None
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10,
                              check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


# Short list: no copies (Powerline/Nerd Fonts are patched programming fonts), no pure symbol fonts
# (characters in Latin positions), no regional variants of the CJK fonts (identical for German text)
_HIDDEN = re.compile(
    r"powerline|nerd font"
    r"|^(d050000l|standard symbols (ps|l)|dingbats|symbol|opensymbol|symbola|webdings"
    r"|wingdings( \d)?|font awesome.*|material (icons|symbols).*|noto sans symbols.*)$"
    r"|\b(cjk|ukai|uming)\b.*\b(cn|hk|tw|jp|kr|sc|tc|mbe)$", re.IGNORECASE)


def families(all: bool = False) -> list[str]:
    """Installed font families, sorted. By default the short list: only fonts with all German
    characters (fontconfig ``:lang=de``), without colour/emoji fonts, copies, symbol fonts and
    CJK regional variants; ``all``: every family. Cached (once per list, as called; tests clear
    ``_families.cache_clear()``)."""
    return list(_families(bool(all)))


@lru_cache(maxsize=None)
def _families(all: bool) -> tuple[str, ...]:
    # %{family[0]}: first family name per font, without fontconfig escaping
    if all:
        out = _run("fc-list", "-f", "%{family[0]}\\n", ":")
        names = {line.strip() for line in (out or "").splitlines() if line.strip()}
    else:
        out = _run("fc-list", "-f", "%{family[0]}|%{color}\\n", ":lang=de")
        rows = [line.rsplit("|", 1) for line in (out or "").splitlines() if "|" in line]
        color = {name.strip() for name, flag in rows if flag.strip() == "True"}
        names = {name.strip() for name, __ in rows if name.strip()} - color
        names = {name for name in names if not _HIDDEN.search(name)}
    if not names:
        return (DEFAULT_FAMILY,)
    return tuple(sorted(names, key=str.casefold))


# Qt (QFontComboBox) named fonts of the same name “Name [Foundry]” – this is how older files,
# favourites and settings store them
_FOUNDRY = re.compile(r"(.+?) \[[^\[\]]+\]")


def canonical(family: str | None) -> str | None:
    """Family name without Qt's foundry suffix (“C059 [UKWN]” → “C059”) if the family exists that
    way (and is not really named with brackets); otherwise unchanged – also Qt collective names
    such as “Sans Serif” (they stay foreign and are replaced)."""
    m = _FOUNDRY.fullmatch(family) if family else None
    if m is None:
        return family
    installed = families(all=True)
    return m[1] if m[1] in installed and family not in installed else family


def _escape(name: str) -> str:
    """Escape special characters of the fontconfig pattern with a backslash."""
    return "".join("\\" + c if c in "\\-:,=" else c for c in name)


@lru_cache(maxsize=256)
def resolve(family: str | None, bold: bool, italic: bool) -> FontMatch:
    """File for family + bold/italic; fontconfig replaces what is missing with something similar."""
    family = canonical(family) or DEFAULT_FAMILY
    # escaped; a leading "-" becomes "\\-" and so is not an option
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
    return FontMatch("", DEFAULT_FAMILY, bold=False, italic=False)   # PIL default font


class FontLoadError(ValueError):
    """Font file cannot be loaded (broken, not a font, unusable size)."""


@lru_cache(maxsize=512)
def load(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font in dots (cached; errors are not cached)."""

    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError as e:
            raise FontLoadError(_("Cannot load font “{path}” ({error}).").format(path=path, error=e)) from e
    return ImageFont.load_default(size=size)
