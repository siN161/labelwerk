#!/bin/bash
# AppImage of labelwerk: packaging/appimage/build.sh [OUT]  (needs Docker; downloads the Python
# AppImage of python-appimage and appimagetool)
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
out="$(realpath "${1:-$repo/dist}")"
mkdir -p "$out"
docker run --rm -v "$repo:/src:ro" -v "$out:/out" quay.io/pypa/manylinux_2_28_x86_64 \
  bash /src/packaging/appimage/build-in-container.sh
