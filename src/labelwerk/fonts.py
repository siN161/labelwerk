"""Schriften finden (fontconfig) und laden – UI-unabhängig.

Ohne fontconfig (fc-list/fc-match) wird auf DejaVu Sans zurückgefallen.
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


# Kurze Liste: keine Kopien (Powerline/Nerd Fonts sind nachgerüstete Programmierschriften), keine
# reinen Symbolschriften (Zeichen auf lateinischen Plätzen), keine Regionsvarianten der CJK-Schriften
# (für deutschen Text gleich)
_HIDDEN = re.compile(
    r"powerline|nerd font"
    r"|^(d050000l|standard symbols (ps|l)|dingbats|symbol|opensymbol|symbola|webdings"
    r"|wingdings( \d)?|font awesome.*|material (icons|symbols).*|noto sans symbols.*)$"
    r"|\b(cjk|ukai|uming)\b.*\b(cn|hk|tw|jp|kr|sc|tc|mbe)$", re.IGNORECASE)


def families(all: bool = False) -> list[str]:
    """Installierte Schriftfamilien, sortiert. Standard ist die kurze Liste: nur Schriften mit
    allen deutschen Zeichen (fontconfig ``:lang=de``), ohne Farb-/Emoji-Schriften, Kopien,
    Symbolschriften und CJK-Regionsvarianten; ``all``: jede Familie. Gemerkt (je Liste einmal,
    gleich wie aufgerufen; Tests leeren ``_families.cache_clear()``)."""
    return list(_families(bool(all)))


@lru_cache(maxsize=None)
def _families(all: bool) -> tuple[str, ...]:
    # %{family[0]}: erster Familienname je Schrift, ohne fontconfig-Maskierung
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


# Qt (QFontComboBox) nannte gleichnamige Schriften „Name [Hersteller]“ – so steht es in älteren
# Dateien, Favoriten und Einstellungen
_FOUNDRY = re.compile(r"(.+?) \[[^\[\]]+\]")


def canonical(family: str | None) -> str | None:
    """Familienname ohne Qts Herstellerzusatz („C059 [UKWN]“ → „C059“), wenn es die Familie so
    gibt (und nicht wirklich mit Klammer heißt); sonst unverändert – auch Qt-Sammelnamen wie
    „Sans Serif“ (die bleiben fremd und werden ersetzt)."""
    m = _FOUNDRY.fullmatch(family) if family else None
    if m is None:
        return family
    installed = families(all=True)
    return m[1] if m[1] in installed and family not in installed else family


def _escape(name: str) -> str:
    """Sonderzeichen des fontconfig-Musters mit Backslash maskieren."""
    return "".join("\\" + c if c in "\\-:,=" else c for c in name)


@lru_cache(maxsize=256)
def resolve(family: str | None, bold: bool, italic: bool) -> FontMatch:
    """Datei zu Familie + fett/kursiv; fontconfig ersetzt Fehlendes durch Ähnliches."""
    family = canonical(family) or DEFAULT_FAMILY
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


class FontLoadError(ValueError):
    """Schriftdatei lässt sich nicht laden (kaputt, keine Schrift, unbrauchbare Größe)."""


@lru_cache(maxsize=512)
def load(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Schrift in Druckpunkten laden (gecacht; Fehler werden nicht gecacht)."""
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError as e:
            raise FontLoadError(_("Cannot load font “{path}” ({error}).").format(path=path, error=e)) from e
    return ImageFont.load_default(size=size)
