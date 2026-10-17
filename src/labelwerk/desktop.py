"""Starter-Eintrag (.desktop) und Icon für die Desktop-Umgebung (XDG, z. B. COSMIC/GNOME)."""
from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

APP_ID = "labelwerk"   # muss zu QGuiApplication.setDesktopFileName passen


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _targets(data: Path) -> tuple[Path, Path]:
    return (data / "applications" / f"{APP_ID}.desktop",
            data / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg")


def icon_svg() -> str:
    return (resources.files("labelwerk.gui") / "icons" / f"{APP_ID}.svg").read_text(encoding="utf-8")


def desktop_entry(gui_exe: Path) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=labelwerk\n"
        "GenericName=Etikettendruck\n"
        "Comment=Etiketten gestalten und drucken (Brother QL)\n"
        f"Exec={gui_exe}\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "Categories=Office;Graphics;\n"
        "Keywords=Etikett;Label;Brother;QL;Drucker;P-touch;\n"
        f"StartupWMClass={APP_ID}\n"
    )


def install(gui_exe: Path, data: Path | None = None) -> list[Path]:
    """Starter-Eintrag und Icon schreiben; vorhandene werden überschrieben."""
    gui_exe = Path(gui_exe)
    if not gui_exe.exists():
        raise ValueError(f"labelwerk-gui nicht gefunden ({gui_exe}) – "
                         "GUI installiert? pip install -e \".[gui]\"")
    entry, icon = _targets(data or data_home())
    for path in (entry, icon):
        path.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(desktop_entry(gui_exe.resolve()), encoding="utf-8")
    icon.write_text(icon_svg(), encoding="utf-8")
    return [entry, icon]


def uninstall(data: Path | None = None) -> list[Path]:
    """Starter-Eintrag und Icon entfernen; gibt die entfernten Dateien zurück."""
    removed = []
    for path in _targets(data or data_home()):
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed
