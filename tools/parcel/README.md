# Tools: maintaining parcel label types

Only for maintaining `src/labelwerk/parcel_data/catalog.json` – labelwerk itself does not need them.
Requires numpy, scipy, zxing-cpp, pypdfium2, Pillow, segno and (for `make_sheets.py`) PySide6.

| Script | Purpose |
|---|---|
| `make_sheets.py [FOLDER]` | test sheets (A4/A5 portrait/landscape, 100×150, 105×203, 103×199) with a QR grid |
| `analyze.py RESULT.pdf …` | QR codes in the converted result → areas per piece (`analyse.json`) |
| `extract.py [TYPEID …]` | exact areas per type (missing pieces, sharpened edges) → `result/`, `check/` |
| `assemble.py` | `result/*.json` → `templates.json` + report |
| `workdir.py` | checks the work folder (outside the repository) |
| `catalog.py templates.json catalog.json` | data for labelwerk (recognition, page sizes, image rules) |

A work folder is required: `LABELWERK_PARCEL_DIR=folder` (for `make_sheets.py` also as an argument) – it holds the
test sheets, converted results and all outputs (`analyse/`, `check/`, `result/`, `templates.json`). If the folder
is inside the repository, the tools stop (`workdir.py`); `.gitignore` also covers the outputs. Workflow and format:
`src/labelwerk/parcel_data/README.md`. Real parcel labels (cross-check) only locally in `Original/` with
`Original/originale.json` – never in the repository.
