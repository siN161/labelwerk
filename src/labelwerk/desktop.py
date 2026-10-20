"""Launcher entry (.desktop), icon and file type *.labelwerk for the desktop environment (XDG,
e.g. COSMIC/GNOME): double-clicking a label file opens it in labelwerk."""
from __future__ import annotations

import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from xml.sax.saxutils import escape

from . import i18n
from .i18n import N_, _

APP_NAME = "labelwerk"  # displayed name (window, launcher, help) – renaming: CLAUDE.md, roadmap 7
APP_ID = "io.github.siN161.labelwerk"   # technical ID (Flatpak, launcher, Wayland app id); must
                                         # match QGuiApplication.setDesktopFileName
OLD_IDS = ("labelwerk",)                 # IDs of older versions: their launcher files are removed
ICON_FILE = "labelwerk.svg"              # app icon in the package (gui/icons)
MIME_TYPE = "application/x-labelwerk"      # label file *.labelwerk
MIME_ICON = MIME_TYPE.replace("/", "-")    # icon name per XDG (shared-mime-info derives it)
# Texts for launcher and file type: English, plus each translation as its own entry (the files
# apply to every language of the session, not just labelwerk's own)
MIME_COMMENT = N_("{app} label")
GENERIC_NAME = N_("Label printing")
COMMENT = N_("Design and print labels (Brother QL)")
KEYWORDS = N_("Label;Brother;QL;Printer;P-touch;")


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _targets(data: Path) -> tuple[Path, Path, Path, Path]:
    """Launcher entry, app icon, file type (shared-mime-info), icon of the file type."""
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
    """``text`` in English ("") and in every language with a translation: [(language, text), …]."""
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
    """Key of a launcher entry with translations: ``Key=…``, ``Key[de]=…``."""
    return "".join(f"{key}{f'[{code}]' if code else ''}={value}\n"
                   for code, value in _localized(text))


def icon_svg() -> str:
    return (resources.files("labelwerk.gui") / "icons" / ICON_FILE).read_text(encoding="utf-8")


def _exec_arg(path: Path) -> str:
    """Path as argument for ``Exec=`` (Desktop Entry specification): in quotation marks,
    \\ " ` $ escaped with a backslash, then every backslash doubled once more for the file's
    string; % as %% (otherwise a field code)."""
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
    """Refresh the desktop environment's databases (if the tools are there); returns the
    failed tools – the entry applies after the next login at the latest anyway.
    ``which``/``run`` are resolved only here (replaceable in tests, also via the module)."""
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
    """Write launcher entry, icon and file type; existing ones are overwritten. Then refresh
    the databases (``update``, ``update_databases``). Write errors: ``OSError``."""
    gui_exe = Path(gui_exe)
    if not gui_exe.exists():
        raise ValueError(_("labelwerk-gui not found ({path}) – GUI installed? "
                           "pip install -e \".[gui]\"").format(path=gui_exe))
    data = data or data_home()
    _remove_old(data)
    entry, icon, mime, mime_icon = _targets(data)
    contents = {entry: desktop_entry(gui_exe.resolve()), icon: icon_svg(), mime: mime_xml(),
                mime_icon: icon_svg()}
    for path, text in contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if update:
        update_databases(data, which, run)
    return list(contents)


def _remove_old(data: Path) -> list[Path]:
    """Launcher entry, icon and file type of older versions (other ID) – otherwise twice."""
    removed = []
    icons = data / "icons" / "hicolor" / "scalable" / "apps"
    for old in OLD_IDS:
        for path in (data / "applications" / f"{old}.desktop", icons / f"{old}.svg",
                     data / "mime" / "packages" / f"{old}.xml"):
            if path.exists():
                path.unlink()
                removed.append(path)
    return removed


def uninstall(data: Path | None = None, which=None, run=None, update: bool = True) -> list[Path]:
    """Remove launcher entry, icon and file type (also those of older versions); returns the
    removed files."""
    data = data or data_home()
    removed = _remove_old(data)
    for path in _targets(data):
        if path.exists():
            path.unlink()
            removed.append(path)
    if removed and update:
        update_databases(data, which, run)
    return removed
