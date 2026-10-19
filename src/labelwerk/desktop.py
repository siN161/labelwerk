"""Starter-Eintrag (.desktop), Icon und Dateityp *.labelwerk für die Desktop-Umgebung (XDG,
z. B. COSMIC/GNOME): Doppelklick auf eine Etikett-Datei öffnet sie in labelwerk."""
from __future__ import annotations

import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from xml.sax.saxutils import escape

from . import i18n
from .i18n import N_, _

APP_NAME = "labelwerk"  # angezeigter Name (Fenster, Starter, Hilfe) – Umbenennen: CLAUDE.md, Roadmap 7
APP_ID = "labelwerk"    # technische ID; muss zu QGuiApplication.setDesktopFileName passen
MIME_TYPE = "application/x-labelwerk"      # Etikett-Datei *.labelwerk
MIME_ICON = MIME_TYPE.replace("/", "-")    # Icon-Name nach XDG (shared-mime-info leitet ihn ab)
# Texte für Starter und Dateityp: englisch, dazu jede Übersetzung als eigener Eintrag (die Dateien
# gelten für jede Sprache der Sitzung, nicht nur die von labelwerk)
MIME_COMMENT = N_("{app} label")
GENERIC_NAME = N_("Label printing")
COMMENT = N_("Design and print labels (Brother QL)")
KEYWORDS = N_("Label;Brother;QL;Printer;P-touch;")


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _targets(data: Path) -> tuple[Path, Path, Path, Path]:
    """Starter-Eintrag, App-Icon, Dateityp (shared-mime-info), Icon des Dateityps."""
    icons = data / "icons" / "hicolor" / "scalable"
    return (data / "applications" / f"{APP_ID}.desktop", icons / "apps" / f"{APP_ID}.svg",
            data / "mime" / "packages" / f"{APP_ID}.xml", icons / "mimetypes" / f"{MIME_ICON}.svg")


def mime_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
        f'  <mime-type type="{MIME_TYPE}">\n'
        + "".join("    <comment" + (f' xml:lang="{code}"' if code else "") + ">"
                  + escape(text.format(app=APP_NAME)) + "</comment>\n"
                  for code, text in _localized(MIME_COMMENT)) +
        '    <sub-class-of type="application/json"/>\n'
        '    <glob pattern="*.labelwerk"/>\n'
        "  </mime-type>\n"
        "</mime-info>\n")


def _localized(text: str) -> list[tuple[str, str]]:
    """``text`` englisch ("") und in jeder Sprache mit Übersetzung: [(Sprache, Text), …]."""
    found = [("", text)]
    for code in i18n.available():
        if code == i18n.SOURCE:
            continue
        try:
            catalog = i18n.parse_po((i18n.PO_DIR / f"{code}.po").read_text(encoding="utf-8-sig"), code)
        except (OSError, ValueError):
            continue
        forms = catalog.messages.get(("", text))
        if forms and forms[0] != text:
            found.append((code, forms[0]))
    return found


def _entries(key: str, text: str) -> str:
    """Schlüssel eines Starter-Eintrags mit Übersetzungen: ``Key=…``, ``Key[de]=…``."""
    return "".join(f"{key}{f'[{code}]' if code else ''}={value}\n"
                   for code, value in _localized(text))


def icon_svg() -> str:
    return (resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg").read_text(encoding="utf-8")


def _exec_arg(path: Path) -> str:
    """Pfad als Argument für ``Exec=`` (Desktop-Entry-Spezifikation): in Anführungszeichen,
    \\ " ` $ mit Backslash maskiert, dann jeder Backslash für die Zeichenkette der Datei noch
    einmal verdoppelt; % als %% (sonst ein Feldcode)."""
    text = str(path)
    for char in ("\\", '"', "`", "$"):
        text = text.replace(char, "\\" + char)
    return '"' + text.replace("\\", "\\\\").replace("%", "%%") + '"'


def desktop_entry(gui_exe: Path) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        + _entries("GenericName", GENERIC_NAME) + _entries("Comment", COMMENT) +
        f"Exec={_exec_arg(gui_exe)} %f\n"
        f"Icon={APP_ID}\n"
        f"MimeType={MIME_TYPE};\n"
        "Terminal=false\n"
        "Categories=Office;\n"
        + _entries("Keywords", KEYWORDS) +
        f"StartupWMClass={APP_ID}\n"
    )


UPDATE_TIMEOUT_S = 20


def update_databases(data: Path, which=None, run=None) -> list[str]:
    """Datenbanken der Desktop-Umgebung auffrischen (falls die Werkzeuge da sind); gibt die
    gescheiterten Werkzeuge zurück – spätestens nach neuer Anmeldung gilt der Eintrag trotzdem.
    ``which``/``run`` erst hier aufgelöst (in Tests ersetzbar, auch über das Modul)."""
    which, run = which or shutil.which, run or subprocess.run
    failed = []
    for tool, folder in (("update-mime-database", data / "mime"),
                         ("update-desktop-database", data / "applications")):
        exe = which(tool)
        if exe is None or not folder.is_dir():
            continue
        try:
            run([exe, str(folder)], check=True, capture_output=True, timeout=UPDATE_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError):
            failed.append(tool)
    return failed


def install(gui_exe: Path, data: Path | None = None, which=None, run=None,
            update: bool = True) -> list[Path]:
    """Starter-Eintrag, Icon und Dateityp schreiben; vorhandene werden überschrieben. Danach
    (``update``) die Datenbanken auffrischen (``update_databases``). Schreibfehler: ``OSError``."""
    gui_exe = Path(gui_exe)
    if not gui_exe.exists():
        raise ValueError(_("labelwerk-gui not found ({path}) – GUI installed? "
                           "pip install -e \".[gui]\"").format(path=gui_exe))
    data = data or data_home()
    entry, icon, mime, mime_icon = _targets(data)
    contents = {entry: desktop_entry(gui_exe.resolve()), icon: icon_svg(), mime: mime_xml(),
                mime_icon: icon_svg()}
    for path, text in contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if update:
        update_databases(data, which, run)
    return list(contents)


def uninstall(data: Path | None = None, which=None, run=None, update: bool = True) -> list[Path]:
    """Starter-Eintrag, Icon und Dateityp entfernen; gibt die entfernten Dateien zurück."""
    data = data or data_home()
    removed = []
    for path in _targets(data):
        if path.exists():
            path.unlink()
            removed.append(path)
    if removed and update:
        update_databases(data, which, run)
    return removed
