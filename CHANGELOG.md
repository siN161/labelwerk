# Changelog

## 0.9.0 – 2026-10-20

First public release. Everything works on the QL-600 with 62 mm continuous tape; other printers are
supported but untested – feedback is welcome before 1.0.

- **Label editor:** text with per-character formatting (written directly on the label), images
  (PNG, JPG, GIF, BMP, WebP, SVG, PDF pages, screenshots, clipboard), symbol library (ISO 7000/7010,
  Tabler icons, own symbols), barcodes and QR codes (Code 128, Code 39, EAN-13/8, QR), decorative
  frames; free placement with snapping, alignment, rotation, undo, configurable shortcuts.
- **Series:** placeholders `{column}` filled from CSV/Excel tables or numbering, printed in one job.
- **Files:** `*.labelwerk` files, favourites, recently opened, file dialog with preview.
- **Parcel labels:** 20 German label types (DHL, Hermes, Amazon returns) converted for 62 mm tape or
  100 × 150 mm labels; own types drawn on any label (areas, rotation, barcodes kept 1:1, space
  between the pieces, order).
- **Printers:** Brother QL family detected automatically (USB and network), roll detection on
  USB; Zebra printers via ZPL; any label printer set up in CUPS.
- **Command line:** `labelwerk print`, `print-file`, `parcel`, `labels`, `printers`, `media`,
  `fonts`.
- English and German user interface; designs BlackWerk and System; dockable side bar.
- Packages: AppImage, Flatpak, PyPI (`pip install "labelwerk[gui]"`).
