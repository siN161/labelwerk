#!/bin/bash
# Flatpak bundle of labelwerk: packaging/flatpak/build.sh [OUT]
# Needs: flatpak install --user flathub org.flatpak.Builder org.freedesktop.Sdk//25.08
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
out="$(realpath "${1:-$repo/dist}")"
work="${FLATPAK_WORK:-$out/flatpak-work}"
mkdir -p "$out" "$work"
version=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$repo/src/labelwerk/__init__.py")
flatpak run org.flatpak.Builder --user --force-clean --disable-rofiles-fuse \
  --state-dir="$work/state" --repo="$work/repo" "$work/build" "$here/io.github.siN161.labelwerk.yml"
flatpak build-bundle "$work/repo" "$out/labelwerk-$version-x86_64.flatpak" io.github.siN161.labelwerk
echo "$out/labelwerk-$version-x86_64.flatpak"
