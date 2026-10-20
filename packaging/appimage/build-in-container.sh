#!/bin/bash
# Runs in quay.io/pypa/manylinux_2_28_x86_64 (glibc 2.28: the AppImage runs on every distribution
# with at least that) – called by packaging/appimage/build.sh. /src = repository (read only),
# /out = output folder.
set -euo pipefail
PY_APPIMAGE=python3.12.15-cp312-cp312-manylinux_2_28_x86_64.AppImage
work=/tmp/build && mkdir -p "$work" && cd "$work"
curl -sSLf -o python.AppImage \
  "https://github.com/niess/python-appimage/releases/download/python3.12/$PY_APPIMAGE"
curl -sSLf -o appimagetool.AppImage \
  "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
chmod +x python.AppImage appimagetool.AppImage
./python.AppImage --appimage-extract >/dev/null
mv squashfs-root AppDir
# labelwerk with the GUI into the Python of the AppImage (wheel built from /src)
mkdir -p /tmp/src && (cd /src && tar --exclude=./.venv --exclude=./dist --exclude=./build \
  --exclude=./.git -cf - .) | tar -xf - -C /tmp/src
AppDir/usr/bin/python3.12 -m pip install --no-cache-dir --no-warn-script-location -q "/tmp/src[gui]"
version=$(AppDir/usr/bin/python3.12 -c "import labelwerk; print(labelwerk.__version__)")
# Launcher, icon, file type, AppStream: the same as `labelwerk install-desktop` writes
rm -f AppDir/*.desktop AppDir/*.png AppDir/*.svg AppDir/.DirIcon AppDir/usr/share/metainfo/*.xml
AppDir/usr/bin/python3.12 /src/packaging/make_files.py AppDir/usr labelwerk >/dev/null
cp AppDir/usr/share/applications/io.github.siN161.labelwerk.desktop AppDir/
cp AppDir/usr/share/icons/hicolor/scalable/apps/io.github.siN161.labelwerk.svg AppDir/
ln -sf io.github.siN161.labelwerk.svg AppDir/.DirIcon
install -m 755 /src/packaging/appimage/AppRun AppDir/AppRun
ARCH=x86_64 ./appimagetool.AppImage --appimage-extract-and-run --no-appstream AppDir \
  "/out/labelwerk-$version-x86_64.AppImage" >/dev/null
chown "${HOST_UID:-0}:${HOST_GID:-0}" "/out/labelwerk-$version-x86_64.AppImage"   # yours, not root's
echo "/out/labelwerk-$version-x86_64.AppImage"
