# Parcel label types (`catalog.json`)

Which areas of a parcel label (DHL, Hermes …) go onto the label and where is stored here as data – labelwerk
(`parcel.py`) only reads this file. New countries, carriers and types need no code.

## Origin

The areas (`src`) are measured facts about the parcel labels; the arrangement (`dst`) is measured after the
example of paketikett.de. Both were determined with test sheets (`tools/parcel/make_sheets.py`: 10 mm grid, a QR
code with its position in every cell) that a conversion service (paketikett.de) processed like a parcel label;
`tools/parcel/analyze.py` and `extract.py` read from the result which area went where, with which rotation and
scale. No code of the service was taken over. `verified: true` means: checked against a real parcel label
(original and result); all other types are "untested" – labelwerk moves their edges on the real label out to
the next white margin (at most 3 mm).

## Format

```json
{"version": 1,
 "countries": {"DE": {"names": {"de": "Deutschland", "en": "Germany"},
                      "carriers": {"dhl": {"de": "DHL", "en": "DHL"}}}},
 "types": [{
   "id": "dhl-privat-1", "country": "DE", "carrier": "dhl",
   "names": {"de": "…", "en": "…"}, "verified": true,
   "source": {"sizes_mm": [[210, 297]], "raster": {"dpi": 300, "x_mm": 0, "y_mm": 0, "px": [1800, 1200]}},
   "detect": {"all": ["DHL"], "any": ["Online Frankierung"], "none": ["Warenpost"]},
   "layouts": {"62": [{"size_mm": [180, 62], "pieces": [
       {"page": 1, "src": [x0, y0, x1, y1], "rotation": 90, "dst": [x0, y0, x1, y1], "kind": "barcode"}]}]}
 }]}
```

- **source**: possible page sizes of the parcel label in mm (± 4 mm, also landscape); `raster` only for labels
  that come as an image (e.g. GIF): placed at this resolution (`dpi`) at this position of the page (`x_mm`,
  `y_mm`); `px` is the expected pixel size (width, height) – only images with this aspect ratio count as this type.
- **detect**: terms in the text of the PDF – `all` must occur, `any` count in favour, `none` against.
- **layouts**: `"62"` = reference 62 mm continuous (page landscape: x along the tape, y across), `"100x150"` =
  label 100 × 150 mm (portrait). One or more output labels per layout (returns: two).
- **pieces** (paint order = list order, later ones lie on top): `src` rectangle on the parcel label in mm (origin
  top left), `rotation` clockwise, `dst` rectangle after rotating on the output label in mm (the piece is scaled
  exactly onto it), `kind` `barcode` (meant not to be shrunk) or `text`. Pieces with the same `src` span whose
  `dst` agree within 0.5 mm are one column (parts of a long barcode with its middle cut out) – labelwerk gives
  them exactly the same `dst` span so the bars do not kink at the seam.

labelwerk scales the layout to the printable width of the label (wider tape → larger) or fits it into a fixed-size
label – one scale for all labels of a conversion, reference layouts by their label height (60/62 mm like
paketikett.de, so 95–98 % on 58.9 mm printable); barcodes below 94 % give a note.

## Contributing a new type

Work folder outside the repository, e.g. `export LABELWERK_PARCEL_DIR=~/parcel-maintenance`:

1. Create test sheets: `QT_QPA_PLATFORM=offscreen python tools/parcel/make_sheets.py`.
2. Convert the matching sheet with the service as a label of this type, put the result into the work folder.
3. Add the type to `TYPES` in `tools/parcel/extract.py`, then run `python tools/parcel/extract.py TYPEID` and
   `python tools/parcel/assemble.py` (needs numpy, scipy, zxing-cpp – only for maintenance, not for labelwerk).
4. `python tools/parcel/catalog.py "$LABELWERK_PARCEL_DIR/templates.json" src/labelwerk/parcel_data/catalog.json`
   (add the recognition terms there), look at the comparison images in `check/`, run the tests.

## Own types

Types created in labelwerk are stored as `$XDG_DATA_HOME/labelwerk/paketmarken/<id>.json` – areas only, labelwerk
arranges them itself (columns along the tape, barcodes 1:1, texts shrunk at most to the tape width):

```json
{"version": 1, "id": "my-label", "names": {"en": "My label"},
 "source": {"sizes_mm": [[210, 297]], "pages_mm": [[210, 297]]}, "detect": {"all": ["My company"]},
 "pieces": [{"page": 1, "src": [10, 10, 110, 60], "rotation": 0, "kind": "text", "space_after_mm": 10},
            {"page": 1, "src": [10, 100, 60, 130], "rotation": 0, "kind": "barcode"}]}
```

`sizes_mm`: page sizes for recognition; `pages_mm` (optional): size per page – areas are checked against their
page and placed that way (labels with pages of different sizes). `space_after_mm` (optional, 0–500): blank tape
after this area – the next area starts a new column at this distance; after the last area it does not count.
The file name is the identifier (`<id>.json`). Checked when reading: identifier (lower-case letters, digits,
hyphen; not a bundled one), names, page sizes (5–2000 mm), terms, 1–30 areas with edges ≥ 1 mm inside the page,
rotation 0/90/180/270, kind `barcode`/`text`, space. Broken files are skipped (with a note).

Real parcel labels contain names and addresses – they never belong in the repository.
