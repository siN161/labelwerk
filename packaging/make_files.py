"""Write launcher entry, icon, file type and AppStream metadata for a package (Flatpak, AppImage)
from the same sources as ``labelwerk install-desktop``.

make_files.py TARGET [EXEC]   → TARGET/share/{applications,icons,mime,metainfo}/…
"""
import shutil
import sys
from pathlib import Path

from labelwerk import desktop

HERE = Path(__file__).resolve().parent


def main() -> None:
    target = Path(sys.argv[1])
    command = sys.argv[2] if len(sys.argv) > 2 else "labelwerk-gui"
    share = target / "share"
    entry = desktop.desktop_entry(Path(command)).replace(
        desktop._exec_arg(Path(command)), command)            # plain command, found in PATH
    files = {
        share / "applications" / f"{desktop.APP_ID}.desktop": entry,
        share / "icons" / "hicolor" / "scalable" / "apps" / f"{desktop.APP_ID}.svg": desktop.icon_svg(),
        share / "mime" / "packages" / f"{desktop.APP_ID}.xml": desktop.mime_xml(),
        share / "icons" / "hicolor" / "scalable" / "mimetypes" / f"{desktop.MIME_ICON}.svg":
            desktop.icon_svg(),
    }
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(path)
    metainfo = share / "metainfo" / f"{desktop.APP_ID}.metainfo.xml"
    metainfo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / f"{desktop.APP_ID}.metainfo.xml", metainfo)
    print(metainfo)


if __name__ == "__main__":
    main()
