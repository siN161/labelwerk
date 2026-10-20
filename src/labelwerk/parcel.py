"""Convert parcel labels without Qt: label types per country, loading, detecting, converting.

A parcel label (DHL, Hermes …) arrives as an A4/A5/100×150 PDF or as an image. Each label type cuts out
fixed areas (``Piece.src`` in mm on the label), rotates them (clockwise) and places them on an output
label (``Piece.dst`` in mm, rectangle after rotation) – barcodes at original size, addresses and info
texts smaller. The bundled types are in ``parcel_data/catalog.json`` (origin: ``parcel_data/README.md``),
custom types in ``$XDG_DATA_HOME/labelwerk/paketmarken`` (areas only; ``arrange`` lays them out on the
tape).

Untested types (areas taken only from test sheets) move their edges on the real label out to the
nearest white margin (``snap``), tested ones do not – their edges are exact.

``convert`` turns this into ordinary labels (``Document`` with one ``ImageObject`` per piece): the
layout is scaled to the printable width of the label (wider tape → larger), and for fixed labels
reduced just enough to fit.
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from PIL import Image

from . import i18n
from .document import Document, ImageObject
from .files import PDFIUM_LOCK, _checked, _readable, load_image
from .i18n import N_, _, number as number_text
from .labels import get_label, length_limits
from .render import label_size

CATALOG = Path(__file__).with_name("parcel_data") / "catalog.json"
LAYOUTS = ("62", "100x150")        # Reference layouts: 62 mm continuous (across = page height), 100 × 150 mm
KINDS = ("barcode", "text")        # Barcodes are never arranged scaled down
SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif")
_IMAGE_FORMATS = ["PNG", "JPEG", "GIF"]
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_PAGES = 20
MAX_DPI = 600
MIN_PIECE_MM = 1.0                 # custom areas: edges at least this long
EDGE_TOLERANCE_MM = 0.5            # custom areas may extend this far beyond the page edge (rounding)
MAX_SPACE_MM = 500.0               # space after an area at most this long
SNAP_MM = 3.0                      # edge moved outwards at most this far to the white margin
SIZE_TOLERANCE_MM = 4.0
WIDE_MM = 95.0                     # from this printable width on a 100×150 layout applies
BARCODE_MIN = 0.94                 # below this a note: barcodes scaled down (62 mm high layouts on
                                   # 58.9 mm printable = 95 % – paketikett.de prints them that way too)
WHITE = 200                        # gray value from which a pixel counts as white (adjusting edges)
MAX_PAGE_PIXELS = 80_000_000       # page rendered at most this large (A4 at 600 dpi: 35 million)
MAX_IMAGE_PIXELS = 50_000_000      # image label at most this large (checked before decoding)
DPI_PLAUSIBLE = (50, 1200)         # other values in images count as missing
ALIGN_MM = 0.5                     # pieces of a column: targets measured this close are the same
ASPECT_TOLERANCE = 0.03            # image fits the page/rule if the aspect ratio is within ±3 %
TURN_MARGIN = 1.15                 # label lying across: the better rotation must hit this much more ink
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_own_warnings: list[str] = []


class ParcelError(ValueError):
    """Parcel label or label type unusable (message for users, translated)."""


@dataclass(frozen=True)
class Piece:
    """A piece of the label: ``src`` (x0, y0, x1, y1) in mm on page ``page``, rotated clockwise by
    ``rotation`` and placed on ``dst`` (x0, y0, x1, y1) in mm of the output label."""
    page: int
    src: tuple[float, float, float, float]
    rotation: int
    dst: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    kind: str = "text"
    space_after: float = 0.0          # custom types: space after it in mm (empty tape, 0 = none)

    def turned_mm(self) -> tuple[float, float]:
        """Size of the area after rotation (width, height) in mm."""
        w, h = self.src[2] - self.src[0], self.src[3] - self.src[1]
        return (h, w) if self.rotation in (90, 270) else (w, h)

    def scale(self) -> float:
        """Scale from the area to the target (mean of both axes)."""
        w, h = self.turned_mm()
        return ((self.dst[2] - self.dst[0]) / w + (self.dst[3] - self.dst[1]) / h) / 2


@dataclass(frozen=True)
class Sheet:
    """An output label of a layout: size (width, height) in mm and pieces in painting order."""
    size_mm: tuple[float, float]
    pieces: tuple[Piece, ...]


@dataclass(frozen=True)
class ParcelType:
    id: str
    names: dict = field(compare=False)                 # {language: name}
    country: str = ""
    carrier: str = ""
    source_sizes: tuple[tuple[float, float], ...] = ()  # possible page sizes of the label in mm
    raster: dict | None = field(default=None, compare=False)   # image label: {"dpi", "x_mm", "y_mm"}
    detect: dict = field(default_factory=dict, compare=False)  # {"all", "any", "none"}: terms
    layouts: dict = field(default_factory=dict, compare=False)  # "62"/"100x150" → (Sheet, …)
    pieces: tuple[Piece, ...] = ()                      # custom types: areas only (arrange)
    verified: bool = False
    own: bool = False
    page_sizes: tuple[tuple[float, float], ...] = ()    # custom types: size per page (mm)

    @property
    def name(self) -> str:
        """Name in the language of labelwerk (otherwise English, otherwise the first)."""
        return (self.names.get(i18n.language()) or self.names.get("en")
                or next(iter(self.names.values()), self.id))


# --- Catalogue -------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _builtin() -> tuple[ParcelType, ...]:
    return tuple(_type(entry) for entry in _catalog()["types"])


def _type(entry: dict, own: bool = False) -> ParcelType:
    layouts = {key: tuple(Sheet(tuple(s["size_mm"]), _aligned([_piece(p) for p in s["pieces"]]))
                          for s in sheets) for key, sheets in entry.get("layouts", {}).items()}
    source = entry.get("source", {})
    return ParcelType(entry["id"], dict(entry["names"]), entry.get("country", ""),
                      entry.get("carrier", ""), tuple(tuple(s) for s in source.get("sizes_mm", ())),
                      source.get("raster"), dict(entry.get("detect", {})), layouts,
                      tuple(_piece(p) for p in entry.get("pieces", ())),
                      bool(entry.get("verified", False)), own)


def _piece(p: dict) -> Piece:
    return Piece(int(p.get("page", 1)), tuple(float(v) for v in p["src"]), int(p["rotation"]),
                 tuple(float(v) for v in p.get("dst", (0, 0, 0, 0))), p.get("kind", "text"))


def _span_sides(piece: Piece, axis: int) -> tuple[int, int]:
    """Edges of the area (index in ``src``) that fall on label x (0) or y (1)."""
    return (0, 2) if (piece.rotation in (0, 180)) == (axis == 0) else (1, 3)


def _column_key(piece: Piece, axis: int):
    a, b = _span_sides(piece, axis)
    return piece.page, piece.rotation, piece.src[a], piece.src[b]


def _aligned(pieces) -> tuple[Piece, ...]:
    """Layouts cut the middle out of long bars and join the parts. Pieces with the same span in the
    area whose targets agree within ``ALIGN_MM`` (measuring accuracy) get exactly the same target
    (mean) – otherwise the bars kink at the seam."""
    pieces = list(pieces)
    for axis in (0, 1):
        done = set()
        for n, piece in enumerate(pieces):
            if n in done:
                continue
            start, end = piece.dst[axis], piece.dst[axis + 2]
            group = [m for m, other in enumerate(pieces)
                     if _column_key(other, axis) == _column_key(piece, axis)
                     and abs(other.dst[axis] - start) <= ALIGN_MM
                     and abs(other.dst[axis + 2] - end) <= ALIGN_MM]
            done.update(group)
            if len(group) < 2:
                continue
            start = sum(pieces[m].dst[axis] for m in group) / len(group)
            end = sum(pieces[m].dst[axis + 2] for m in group) / len(group)
            for m in group:
                dst = list(pieces[m].dst)
                dst[axis], dst[axis + 2] = start, end
                pieces[m] = replace(pieces[m], dst=tuple(dst))
    return tuple(pieces)


def countries() -> list[tuple[str, str]]:
    """Countries with bundled types: (code, name in the language)."""
    return [(code, _local(entry["names"])) for code, entry in _catalog()["countries"].items()]


def carriers(country: str) -> list[tuple[str, str]]:
    """Services of a country: (key, name)."""
    entry = _catalog()["countries"].get(country, {})
    return [(key, _local(names)) for key, names in entry.get("carriers", {}).items()]


def _local(names: dict) -> str:
    return names.get(i18n.language()) or names.get("en") or next(iter(names.values()), "")


def types(country: str | None = None) -> list[ParcelType]:
    """Bundled types (of a country) followed by the custom ones."""
    return [t for t in _builtin() if country is None or t.country == country] + own_types()


def find(type_id: str) -> ParcelType:
    for ptype in (*_builtin(), *own_types()):
        if ptype.id == type_id:
            return ptype
    raise ParcelError(_("Unknown parcel label type: {id}").format(id=type_id))


def default_country() -> str:
    """Country of the region (locale ``LC_ALL`` › ``LC_MESSAGES`` › ``LANG``, e.g. “de_DE” → DE) if
    there are types for it – otherwise the first country of the catalogue."""
    codes = [code for code, _name in countries()]
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key, "")
        if value:
            region = value.split(".")[0].split("@")[0].partition("_")[2].upper()
            if region in codes:
                return region
            break                                     # set, but without a matching country
    return codes[0] if codes else ""


_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def own_id(name: str, taken) -> str:
    """Identifier for a new custom type from its name (“eigen-…”, free, valid)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold().translate(_UMLAUTS)).strip("-")
    base = ("eigen-" + (slug or "typ"))[:58].rstrip("-")
    candidate, number = base, 2
    while candidate in taken or candidate in {t.id for t in _builtin()}:
        candidate, number = f"{base}-{number}", number + 1
    return candidate


# --- Custom types ----------------------------------------------------------------------
def own_dir() -> Path:
    """Folder of the custom label types (``$XDG_DATA_HOME/labelwerk/paketmarken``)."""
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "labelwerk" / "paketmarken"


def own_types() -> list[ParcelType]:
    """Custom types from ``own_dir`` (each file checked on its own; broken ones skipped, note in
    ``own_warnings``)."""
    _own_warnings.clear()
    found = []
    folder = own_dir()
    if not folder.is_dir():
        return found
    seen = set()
    for path in sorted(folder.glob("*.json")):
        def skip(reason):
            _own_warnings.append(_("Own parcel label type {name} not readable: {reason}").format(
                name=path.name, reason=reason))
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ParcelError(_("file too large"))
            ptype = own_from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, RecursionError, UnicodeDecodeError):
            skip(_("damaged"))
            continue
        except (OSError, ValueError) as e:              # ParcelError is a ValueError
            skip(e)
            continue
        if path.stem != ptype.id:                         # file is named like its type (saving, deleting)
            skip(_("file name does not match the identifier {id}").format(id=ptype.id))
        elif ptype.id in seen:
            skip(_("identifier {id} appears twice").format(id=ptype.id))
        else:
            seen.add(ptype.id)
            found.append(ptype)
    return found


def own_warnings() -> list[str]:
    """Notes on custom types that ``own_types`` skipped."""
    return list(_own_warnings)


def own_from_dict(data) -> ParcelType:
    """Check and create a custom type from JSON data (foreign input → ``ParcelError``)."""
    def bad(what):
        return ParcelError(_("Invalid parcel label type: {what}").format(what=_(what)))
    if not isinstance(data, dict):
        raise bad(N_("data"))
    type_id = data.get("id")
    if not isinstance(type_id, str) or not _ID.fullmatch(type_id) \
            or type_id in {t.id for t in _builtin()}:
        raise bad(N_("identifier"))
    names = data.get("names")
    if not isinstance(names, dict) or not names or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip() and len(v) <= 200
            for k, v in names.items()):
        raise bad(N_("names"))
    sizes = data.get("source", {}).get("sizes_mm") if isinstance(data.get("source"), dict) else None
    if not isinstance(sizes, list) or not sizes or not all(_numbers(s, 2, 5, 2000) for s in sizes):
        raise bad(N_("page sizes"))
    detect = data.get("detect", {})
    if not isinstance(detect, dict) or not all(
            k in ("all", "any", "none") and isinstance(v, list) and len(v) <= 20
            and all(isinstance(w, str) and 0 < len(w) <= 100 for w in v) for k, v in detect.items()):
        raise bad(N_("recognition words"))
    pages = data["source"].get("pages_mm", [])
    if not isinstance(pages, list) or len(pages) > MAX_PAGES or not all(
            _numbers(s, 2, 5, 2000) for s in pages):
        raise bad(N_("page sizes"))
    raw = data.get("pieces")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 30:
        raise bad(N_("areas"))
    pieces = []
    for number, p in enumerate(raw, start=1):
        if not isinstance(p, dict) or p.get("rotation") not in (0, 90, 180, 270) \
                or p.get("kind", "text") not in KINDS or not isinstance(p.get("page", 1), int) \
                or isinstance(p.get("page", 1), bool) or not 1 <= p.get("page", 1) <= MAX_PAGES \
                or (pages and p.get("page", 1) > len(pages)) \
                or not _numbers(p.get("src"), 4, 0, 2001) \
                or not _numbers([p.get("space_after_mm", 0)], 1, 0, MAX_SPACE_MM):
            raise bad(N_("areas"))
        # Areas against their page (without a size per page: against the largest page size)
        width, height = (pages[p.get("page", 1) - 1] if pages else
                         (max(s[0] for s in sizes), max(s[1] for s in sizes)))
        x0, y0, x1, y1 = p["src"]
        if x1 > width + EDGE_TOLERANCE_MM or y1 > height + EDGE_TOLERANCE_MM:
            raise ParcelError(_("Invalid parcel label type: area {number} reaches beyond the "
                                "page.").format(number=number))
        x1, y1 = min(x1, width), min(y1, height)          # rounding at the edge: onto the page
        if not (x1 - x0 >= MIN_PIECE_MM and y1 - y0 >= MIN_PIECE_MM):
            raise ParcelError(_("Invalid parcel label type: area {number} is too small (at least "
                                "{size} mm).").format(number=number,
                                                      size=number_text(MIN_PIECE_MM)))
        pieces.append(Piece(p.get("page", 1), (float(x0), float(y0), float(x1), float(y1)),
                            p["rotation"], kind=p.get("kind", "text"),
                            space_after=float(p.get("space_after_mm", 0))))
    return ParcelType(type_id, dict(names), "", "own", tuple(tuple(map(float, s)) for s in sizes),
                      None, {k: list(v) for k, v in detect.items()}, {}, tuple(pieces), False, True,
                      tuple(tuple(map(float, s)) for s in pages))


def _numbers(value, count: int, low: float, high: float) -> bool:
    return (isinstance(value, list) and len(value) == count
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and low <= v <= high
                    for v in value))


def own_to_dict(ptype: ParcelType) -> dict:
    return {"version": 1, "id": ptype.id, "names": dict(ptype.names),
            "source": {"sizes_mm": [list(s) for s in ptype.source_sizes],
                       **({"pages_mm": [list(s) for s in ptype.page_sizes]} if ptype.page_sizes else {})},
            "detect": {k: list(v) for k, v in ptype.detect.items() if v},
            "pieces": [{"page": p.page, "src": list(p.src), "rotation": p.rotation, "kind": p.kind,
                        **({"space_after_mm": p.space_after} if p.space_after else {})}
                       for p in ptype.pieces]}


def spaces(ptype: ParcelType) -> list[tuple[int, float]]:
    """Effective spaces of a custom type: (index of the preceding piece, length in mm) – one after
    the last piece does not count (only between the parts)."""
    return [(n, p.space_after) for n, p in enumerate(ptype.pieces[:-1]) if p.space_after > 0]


def with_spaces(ptype: ParcelType, lengths) -> ParcelType:
    """Type with different lengths for the spaces from ``spaces`` (same order; not
    saved – PARCEL tab, per label)."""
    pieces = list(ptype.pieces)
    for (n, _length), length in zip(spaces(ptype), lengths):
        pieces[n] = replace(pieces[n], space_after=min(MAX_SPACE_MM, max(0.0, float(length))))
    return replace(ptype, pieces=tuple(pieces))


def save_own(ptype: ParcelType) -> Path:
    """Save a custom type (overwrites one of the same name)."""
    own_from_dict(own_to_dict(ptype))                   # only valid data reaches the disk
    folder = own_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ptype.id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(own_to_dict(ptype), ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def remove_own(type_id: str) -> None:
    if not _ID.fullmatch(type_id or ""):
        raise ParcelError(_("Unknown parcel label type: {id}").format(id=type_id))
    (own_dir() / f"{type_id}.json").unlink(missing_ok=True)


# --- Loading -----------------------------------------------------------------------------
@dataclass
class Source:
    """Loaded label: page sizes in mm, text per page; page images on demand (``page``)."""
    path: Path
    sizes_mm: list[tuple[float, float]]
    texts: list[str]
    image: Image.Image | None = None      # image label (one page, grayscale)
    image_dpi: float | None = None        # resolution from the file (None = no/implausible value)
    _cache: dict = field(default_factory=dict, repr=False)
    _places: dict = field(default_factory=dict, repr=False)

    @property
    def page_count(self) -> int:
        return len(self.sizes_mm)

    @property
    def raster(self) -> bool:
        return self.image is not None

    def page(self, number: int, dpi: float, ptype: ParcelType | None = None) -> Image.Image:
        """Page ``number`` as a grayscale image at ``dpi`` – with ``ptype`` in its page area
        (``placement``): matching page as it is, a page lying across rotated, another size (Letter on
        A4) at the top left on a white area; an image label by the image rule of the type or stretched
        to its page size. Outside the label everything is white."""
        if not 1 <= number <= self.page_count:
            raise ParcelError(_("The parcel label has no page {page}.").format(page=number))
        place_key = (number, ptype.id if ptype is not None else None)
        if place_key not in self._places:
            self._places[place_key] = placement(self, ptype, number)
        place = self._places[place_key]
        key = (number, round(dpi, 3), place)
        if key not in self._cache:
            w_mm, h_mm = place.frame_mm
            if w_mm * h_mm * (dpi / 25.4) ** 2 > MAX_PAGE_PIXELS:
                raise ParcelError(_("Parcel label page too large: {name}").format(name=self.path.name))
            self._cache.clear()                           # only one page in memory
            self._cache[key] = self._render(number, dpi, place)
        return self._cache[key]

    def _render(self, number: int, dpi: float, place: "Placement") -> Image.Image:
        k = dpi / 25.4
        w_mm, h_mm = place.content_mm                     # content before rotating
        if self.raster:
            content = self.image.resize((max(1, round(w_mm * k)), max(1, round(h_mm * k))),
                                        Image.LANCZOS)
        else:
            content = _render_pdf(self.path, number, dpi)
        if place.rotation:
            content = content.rotate(-place.rotation, expand=True)   # clockwise
        frame = Image.new("L", (round(place.frame_mm[0] * k), round(place.frame_mm[1] * k)), 255)
        frame.paste(content, (round(place.offset_mm[0] * k), round(place.offset_mm[1] * k)))
        return frame


@dataclass(frozen=True)
class Placement:
    """How a page lies in the area of a type: area, content (mm before rotating), clockwise
    rotation, position of the top left corner (mm, after rotating)."""
    frame_mm: tuple[float, float]
    content_mm: tuple[float, float]
    rotation: int = 0
    offset_mm: tuple[float, float] = (0.0, 0.0)


def placement(source: Source, ptype: ParcelType | None, number: int = 1) -> Placement:
    """Position of page ``number`` in the page area of ``ptype`` (without a type: as it is) – if it
    does not fit, ``ParcelError`` (e.g. wrong type chosen by hand)."""
    size = source.sizes_mm[number - 1]
    if ptype is None or not ptype.source_sizes:
        return Placement(size, size)
    if source.raster:
        return _raster_placement(source, ptype, ptype.source_sizes[0])
    sizes = ptype.source_sizes
    if ptype.page_sizes and number <= len(ptype.page_sizes):
        sizes = (ptype.page_sizes[number - 1],)           # custom type: size of this page
    for a, b in sizes:
        if abs(size[0] - a) <= SIZE_TOLERANCE_MM and abs(size[1] - b) <= SIZE_TOLERANCE_MM:
            return Placement((a, b), size)                # fits (Letter: top left, rest white)
    for a, b in sizes:
        if abs(size[0] - b) <= SIZE_TOLERANCE_MM and abs(size[1] - a) <= SIZE_TOLERANCE_MM:
            return Placement((a, b), size, _turn(source, ptype, number, (a, b)))
    raise ParcelError(_("The parcel label ({width} × {height} mm) does not fit the type {name}.")
                      .format(width=round(size[0]), height=round(size[1]), name=ptype.name))


def _raster_placement(source: Source, ptype: ParcelType, frame) -> Placement:
    img = source.image
    rule = ptype.raster
    if rule is not None:                                  # e.g. Amazon GIF: fixed position
        px = rule.get("px")
        if px and not _aspect_fits(img.size, px):
            raise ParcelError(_("The image does not fit the type {name}.").format(name=ptype.name))
        dpi = float(rule.get("dpi", 300)) * (img.width / px[0] if px else 1.0)
        content = (img.width * 25.4 / dpi, img.height * 25.4 / dpi)
        return Placement(frame, content, 0, (float(rule.get("x_mm", 0)), float(rule.get("y_mm", 0))))
    for a, b in ptype.source_sizes:                       # image of a whole page: stretched
        if _aspect_fits(img.size, (a, b)):
            return Placement(frame, (a, b))
        if _aspect_fits(img.size, (b, a)):
            return Placement(frame, (b, a), _turn(source, ptype, 1, frame))
    raise ParcelError(_("The image does not fit the type {name}.").format(name=ptype.name))


def _aspect_fits(size, ref) -> bool:
    return abs(size[0] / size[1] - ref[0] / ref[1]) <= ASPECT_TOLERANCE * ref[0] / ref[1]


def _turn(source: Source, ptype: ParcelType, number: int, frame) -> int:
    """Label lying across: rotation (90 or 270) with more ink in the areas of the type; if both
    are equal, the direction is ambiguous → ``ParcelError``."""
    pieces = [p for p in all_pieces(ptype) if p.page == number]
    dpi = 40.0
    scores = {}
    for rotation in (90, 270):
        place = Placement(tuple(frame),
                          source.sizes_mm[number - 1] if not source.raster
                          else (frame[1], frame[0]), rotation)
        page = source._render(number, dpi, place)
        k = dpi / 25.4
        ink = 0
        for piece in pieces:
            box = tuple(round(v * k) for v in piece.src)
            ink += sum(page.crop(box).point(lambda v: 255 if v < WHITE else 0).histogram()[255:])
        scores[rotation] = ink
    best = max(scores, key=scores.get)
    other = scores[270 if best == 90 else 90]
    if scores[best] <= other * TURN_MARGIN:
        raise ParcelError(_("The parcel label is in landscape and its direction is unclear – save it "
                            "in portrait first."))
    return best


def _render_pdf(path: Path, number: int, dpi: float) -> Image.Image:
    """Render the page; the file may have been deleted, moved or replaced since loading →
    ``ParcelError`` (translated)."""
    import pypdfium2 as pdfium
    try:
        with _readable(path), PDFIUM_LOCK:
            pdf = pdfium.PdfDocument(path)
            try:
                return pdf[number - 1].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
            finally:
                pdf.close()
    except (ValueError, FileNotFoundError, IndexError) as e:
        reason = (_("page {page} is missing").format(page=number) if isinstance(e, IndexError)
                  else str(e))
        raise ParcelError(_("The parcel label can no longer be read ({reason}) – open it "
                            "again.").format(reason=reason)) from e


def all_pieces(ptype: ParcelType) -> tuple[Piece, ...]:
    """All areas of a type (custom: ``pieces``, otherwise those of the first layout)."""
    if ptype.pieces:
        return ptype.pieces
    sheets = next(iter(ptype.layouts.values()), ())
    return tuple(p for sheet in sheets for p in sheet.pieces)


def load(path: str | Path) -> Source:
    """Load a label: PDF (page sizes, text) or image (PNG/JPG/GIF, one page – read like image objects:
    transparency white, 16 bit, EXIF orientation, size limited); foreign input checked (extension,
    file size, pixels, page count) – errors as ``ParcelError``."""
    path = Path(path)
    try:
        path = _checked(path, SUFFIXES[1:], "PDF, PNG, JPG, GIF", 1)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ParcelError(_("Parcel label file too large: {name}").format(name=path.name))
        with _readable(path):
            if path.suffix.lower() == ".pdf":
                return _load_pdf(path)
            with Image.open(path, formats=_IMAGE_FORMATS) as head:   # only the header: size, dpi
                pixels = head.width * head.height
                dpi = head.info.get("dpi")
            if pixels > MAX_IMAGE_PIXELS:
                raise ParcelError(_("Parcel label image has too many pixels: {name}").format(
                    name=path.name))
            dpi = float(dpi[0]) if dpi and dpi[0] else None
            if dpi is not None and not DPI_PLAUSIBLE[0] <= dpi <= DPI_PLAUSIBLE[1]:
                dpi = None                                # value unusable: as without
            img, used = load_image(path, dpi=dpi or 300.0)
            img = img.convert("L")
            size = (img.width * 25.4 / used, img.height * 25.4 / used)
            return Source(path, [size], [""], img, dpi)
    except ParcelError:
        raise
    except (ValueError, FileNotFoundError) as e:
        raise ParcelError(str(e)) from e


def _load_pdf(path: Path) -> Source:
    import pypdfium2 as pdfium
    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(path)
        try:
            if len(pdf) < 1:
                raise ParcelError(_("The PDF has no pages: {name}").format(name=path.name))
            if len(pdf) > MAX_PAGES:
                raise ParcelError(_("Parcel label has too many pages: {name}").format(name=path.name))
            sizes, texts = [], []
            for page in pdf:
                w, h = page.get_size()
                sizes.append((w * 25.4 / 72, h * 25.4 / 72))
                texts.append(page.get_textpage().get_text_range())
            return Source(path, sizes, texts)
        finally:
            pdf.close()


# --- Detecting ---------------------------------------------------------------------------
def detect(source: Source, country: str | None = None, label_id: str | None = None,
           own: list[ParcelType] | None = None) -> list[tuple[ParcelType, float]]:
    """Matching types with score, best first: page size must fit (image labels: type with an
    image rule), all terms from ``all`` in the text, ``any`` counts for it, ``none`` counts against;
    with ``label_id`` the type with a layout for this label wins a tie."""
    candidates = [t for t in _builtin() if country is None or t.country == country]
    candidates += own_types() if own is None else own
    text = " ".join(source.texts).casefold()
    wide = _wide(label_id) if label_id else False
    found = []
    for order, ptype in enumerate(candidates):
        if not _fits(source, ptype):
            continue
        score = 3.0
        words = ptype.detect
        if any(w.casefold() not in text for w in words.get("all", ())):
            continue
        score += 2 * len(words.get("all", ()))
        score += sum(1 for w in words.get("any", ()) if w.casefold() in text)
        score -= 4 * sum(1 for w in words.get("none", ()) if w.casefold() in text)
        if ptype.own:
            score += 0.5                                  # custom type: more precisely meant
        if label_id is not None and ptype.layouts:
            score += 0.25 if ("100x150" in ptype.layouts) == wide else 0.0
        if score >= 3:
            found.append((ptype, score, order))
    found.sort(key=lambda f: (-f[1], not f[0].verified, f[2]))
    return [(ptype, score) for ptype, score, _ in found]


def ambiguous(found: list[tuple[ParcelType, float]]) -> list[ParcelType]:
    """Tie at the top of ``detect`` that no tested template decides: the types that are
    level (then do not choose yourself but ask); otherwise []."""
    if len(found) < 2 or found[0][0].verified or found[1][1] < found[0][1]:
        return []
    return [ptype for ptype, score in found if score == found[0][1]]


def _fits(source: Source, ptype: ParcelType) -> bool:
    """Does the label fit the type? PDF: page size (also across); image: image rule (aspect ratio of the
    expected pixels) or the aspect ratio of a page size."""
    if source.raster:
        if ptype.raster is not None:
            px = ptype.raster.get("px")
            return not px or _aspect_fits(source.image.size, px)
        return any(_aspect_fits(source.image.size, s) or _aspect_fits(source.image.size, s[::-1])
                   for s in ptype.source_sizes)
    return ptype.raster is None and _size_fits(source.sizes_mm[0], ptype.source_sizes)


def _size_fits(size: tuple[float, float], sizes) -> bool:
    w, h = size
    return any(abs(w - a) <= SIZE_TOLERANCE_MM and abs(h - b) <= SIZE_TOLERANCE_MM
               or abs(w - b) <= SIZE_TOLERANCE_MM and abs(h - a) <= SIZE_TOLERANCE_MM
               for a, b in sizes)


def _wide(label_id: str) -> bool:
    label = get_label(label_id)
    return label.width * 25.4 / label.dpi >= WIDE_MM


# --- Adjusting edges --------------------------------------------------------------------
def snap(img: Image.Image, box_mm, dpi: float, limit_mm: float = SNAP_MM):
    """Move the edges of an area (mm) outwards to the first completely white row/column if
    they cut through content – at most ``limit_mm``; without a white line in reach the edge
    stays. White edges stay as they are."""
    k = dpi / 25.4
    x0, y0, x1, y1 = (round(v * k) for v in box_mm)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return tuple(box_mm)
    gray = img.convert("L")
    reach = round(limit_mm * k)

    def white(a0, b0, a1, b1):
        if a0 < 0 or b0 < 0 or a1 > img.width or b1 > img.height:
            return True                                   # page edge counts as white
        return gray.crop((a0, b0, a1, b1)).getextrema()[0] >= WHITE

    edges = list(box_mm)
    # left, top, right, bottom: line directly inside the edge, then step by step outwards
    for side in range(4):
        def line(n):
            if side == 0:
                return white(x0 - 1 - n, y0, x0 - n, y1)
            if side == 1:
                return white(x0, y0 - 1 - n, x1, y0 - n)
            if side == 2:
                return white(x1 + n, y0, x1 + n + 1, y1)
            return white(x0, y1 + n, x1, y1 + n + 1)
        if line(-1) or line(0):                           # edge cuts no content
            continue
        for n in range(1, reach + 1):
            if line(n):                                   # first white line outside
                edges[side] += -n / k if side < 2 else n / k
                break
    return tuple(edges)


# --- Arranging (custom types) ---------------------------------------------------------------
def arrange(pieces, across_mm: float, gap_mm: float = 1.0) -> Sheet:
    """Pieces one after another in columns along the tape, each column up to the width ``across_mm``:
    barcodes 1:1 (smaller only if they do not fit across), texts scaled down at most so that they fit
    across. After a piece with space (``space_after``) a new column begins at that
    distance (instead of ``gap_mm``); after the last piece it does not count."""
    placed, x, y, column, space = [], 0.0, 0.0, 0.0, 0.0
    for piece in pieces:
        w, h = piece.turned_mm()
        s = min(1.0, across_mm / h)
        w, h = w * s, h * s
        if space > 0 or (y > 0 and y + h > across_mm + 1e-6):   # new column
            x, y, column = x + column + max(gap_mm, space), 0.0, 0.0
        placed.append(replace(piece, dst=(x, y, x + w, y + h)))
        y += h + gap_mm
        column = max(column, w)
        space = piece.space_after
    return Sheet((x + column, across_mm), tuple(placed))


# --- Converting ----------------------------------------------------------------------------
@dataclass
class Conversion:
    documents: list[Document]
    notes: list[str]
    layout: str                 # "62", "100x150", "arranged" (pieces rearranged) or "own"
    scale: float                # factor from the layout to the label


def convert(source: Source, ptype: ParcelType, label_id: str, model: str = "QL-600") -> Conversion:
    """Convert label ``source`` by type ``ptype`` into labels for ``label_id`` (one ``Document`` per
    output label with one image object per piece, line/threshold 128). If the label does not fit
    the type (page size, image), ``ParcelError``.

    Layout: from ``WIDE_MM`` printable width the 100×150 layout, otherwise the 62 mm layout; if the
    matching one is missing (e.g. 1a on 62 mm), ``arrange`` rearranges the pieces of the existing one
    (“arranged”), custom types always (“own”) – only after adjusting the edges. One scale for all labels
    of a conversion: reference layouts by their label height (60/62 mm like paketikett.de), across
    to the printable width (wider tape → larger), fixed labels so that everything fits."""
    label = get_label(label_id)
    if label.shape == "round":
        raise ParcelError(_("Round labels are not suitable for parcel labels."))
    for number in sorted({p.page for p in all_pieces(ptype)}):
        if number > source.page_count:
            raise ParcelError(_("The parcel label has no page {page}.").format(page=number))
        placement(source, ptype, number)                  # does the label fit? otherwise message
    k = label.dpi / 25.4
    across = label.width / k
    along = None if label.height is None else label.height / k
    max_len = length_limits(model)[1] / k if label.height is None else None
    if not ptype.layouts:
        key, groups = "own", [ptype.pieces]
    elif across >= WIDE_MM and "100x150" in ptype.layouts:
        key, groups = "100x150", None
    elif "62" in ptype.layouts:
        key, groups = "62", None
    else:                                                 # only 100×150, but narrow tape
        key, groups = "arranged", [sheet.pieces for sheet in next(iter(ptype.layouts.values()))]
    reference = groups is None
    # Resolution for rendering: from the scale before adjusting the edges (page ≤ MAX_PAGE_PIXELS)
    sheets = (ptype.layouts[key] if reference else [arrange(g, across) for g in groups])
    f0, _h = _common_fit(sheets, reference, across, along, max_len)
    frame_w, frame_h = max(ptype.source_sizes or source.sizes_mm, key=lambda s: s[0] * s[1])
    dpi = min(MAX_DPI, label.dpi * max(1.0, max(p.scale() for s in sheets for p in s.pieces) * f0),
              25.4 * (MAX_PAGE_PIXELS / (frame_w * frame_h)) ** 0.5 * 0.99)
    if reference:
        sheets = [Sheet(s.size_mm, _adjusted(source, ptype, s.pieces, dpi, grow=True))
                  for s in sheets]
    else:                                                 # first adjust, then arrange
        sheets = [arrange(_adjusted(source, ptype, g, dpi, grow=False), across) for g in groups]
    f, horizontal = _common_fit(sheets, reference, across, along, max_len)
    documents = [_sheet_document(source, ptype, sheet, f, horizontal, reference, label_id, model,
                                 dpi, across, along) for sheet in sheets]
    notes = []
    shrunk = min((p.scale() * f for s in sheets for p in s.pieces if p.kind == "barcode"),
                 default=1.0)
    if shrunk < BARCODE_MIN:
        notes.append(_("Barcodes shrunk to {percent} % – check before shipping that they can be "
                       "read.").format(percent=round(shrunk * 100)))
    return Conversion(documents, notes, key, f)


def _adjusted(source, ptype, pieces, dpi, grow: bool) -> tuple[Piece, ...]:
    """Untested types: edges on the label out to the white margin (``snap``, never into other pieces);
    ``grow``: the target grows by the same scale (reference layouts), otherwise only the area
    (``arrange`` then lays it out)."""
    if ptype.verified:                                    # tested types have exact edges
        return tuple(pieces)
    srcs = [list(_alone(piece, snap(source.page(piece.page, dpi, ptype), piece.src, dpi), pieces))
            for piece in pieces]
    if grow:                                              # pieces of a column (``_aligned``):
        for axis in (0, 1):                               # move a shared edge only together
            for piece in pieces:
                group = [n for n, other in enumerate(pieces)
                         if _column_key(other, axis) == _column_key(piece, axis)
                         and (other.dst[axis], other.dst[axis + 2])
                         == (piece.dst[axis], piece.dst[axis + 2])]
                for side in _span_sides(piece, axis):
                    if len({srcs[n][side] for n in group}) > 1:
                        for n in group:
                            srcs[n][side] = pieces[n].src[side]
    return tuple(_grow(piece, src) if grow else replace(piece, src=tuple(src))
                 for piece, src in zip(pieces, srcs))


def _frame(sheet: Sheet, reference: bool):
    """Area that goes onto the label: reference layouts across in their whole height (like the
    output label of paketikett.de), along only the content; otherwise the content."""
    bx0, by0, bx1, by1 = _bbox(sheet.pieces)
    if not reference:
        return (bx0, by0, bx1, by1), (bx0, by0, bx1, by1)
    w, h = sheet.size_mm
    return (bx0, by0, bx1, by1), (min(0.0, bx0), min(0.0, by0), max(w, bx1), max(h, by1))


def _common_fit(sheets, reference: bool, across, along, max_len):
    """One scale and one orientation for all labels (True = label x along the tape): across the
    area (``_frame``) to the printable width (reference layouts also larger, otherwise at most
    1:1), along at most the label or the maximum length; for fixed labels the orientation with
    the larger scale wins (on a tie the natural one: long side along)."""
    first = sheets[0].size_mm
    natural = first[0] >= first[1]
    options = []
    for horizontal in (natural, not natural):
        f = None
        for sheet in sheets:
            box, frame = _frame(sheet, reference)
            if horizontal:
                across_ext, along_ext = frame[3] - frame[1], box[2] - box[0]
            else:
                across_ext, along_ext = frame[2] - frame[0], box[3] - box[1]
            fs = across / across_ext
            if not reference:
                fs = min(1.0, fs)
            limit = along if along is not None else max_len
            if limit is not None:
                fs = min(fs, limit / along_ext)
            f = fs if f is None else min(f, fs)
        options.append((f, horizontal))
        if along is None:
            break                                          # continuous tape: natural orientation
    return max(options, key=lambda o: o[0])


def _sheet_document(source, ptype, sheet, f, horizontal, reference, label_id, model, dpi, across,
                    along):
    label = get_label(label_id)
    (bx0, by0, bx1, by1), (fx0, fy0, fx1, fy1) = _frame(sheet, reference)
    if horizontal:                                         # label x along the tape
        ox, oy = bx0, fy0
        off_x = 0.0 if along is None else (along - (bx1 - bx0) * f) / 2
        off_y = (across - (fy1 - fy0) * f) / 2
        along_content = (bx1 - bx0) * f
    else:
        ox, oy = fx0, by0
        off_x = (across - (fx1 - fx0) * f) / 2
        off_y = 0.0 if along is None else (along - (by1 - by0) * f) / 2
        along_content = (by1 - by0) * f
    objects = []
    k = dpi / 25.4
    for n, piece in enumerate(sheet.pieces):
        page = source.page(piece.page, dpi, ptype)
        img = _crop_white(page, tuple(round(v * k) for v in piece.src))
        if piece.rotation:
            img = img.rotate(-piece.rotation, expand=True, fillcolor=255)   # clockwise
        img = _mask_covered(img, piece.dst, [p.dst for p in sheet.pieces[n + 1:]])
        obj = ImageObject.from_image(img, dpi, source.path.name, piece.page)
        dx0, dy0, dx1, dy1 = piece.dst
        objects.append(replace(obj, x_mm=(dx0 - ox) * f + off_x, y_mm=(dy0 - oy) * f + off_y,
                               w_mm=(dx1 - dx0) * f, h_mm=(dy1 - dy0) * f, keep_ratio=False,
                               mode="line", threshold=128))
    length = None
    if along is None:                                      # whole dots + feed
        lk = label.dpi / 25.4
        length = (math.ceil(along_content * lk - 1e-6) + 2 * label.feed_margin) / lk
    doc = Document(label_id, length_mm=length, orientation="horizontal" if horizontal else "vertical",
                   margin_mm=0.0, objects=objects)
    return _inside(doc, model)


def _inside(doc: Document, model: str) -> Document:
    """Rounding: no frame protrudes beyond the label by a dot (the “sticks out” prompt
    would otherwise appear for no reason)."""
    width, height = label_size(doc, model)
    dpi = get_label(doc.label_id).dpi
    k = dpi / 25.4
    fixed = []
    for obj in doc.objects:
        x, y = max(0.0, obj.x_mm), max(0.0, obj.y_mm)
        w, h = obj.w_mm, obj.h_mm
        if round(x * k) + round(w * k) > width:
            w = (width - round(x * k)) / k
        if round(y * k) + round(h * k) > height:
            h = (height - round(y * k)) / k
        fixed.append(replace(obj, x_mm=x, y_mm=y, w_mm=w, h_mm=h))
    return replace(doc, objects=fixed)


def _crop_white(page: Image.Image, box) -> Image.Image:
    """Area; what lies outside the page is white (Pillow filled with black)."""
    x0, y0, x1, y1 = box
    out = Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)), 255)
    l, t, r, b = max(0, x0), max(0, y0), min(page.width, x1), min(page.height, y1)
    if l < r and t < b:                                    # otherwise entirely outside: white
        out.paste(page.crop((l, t, r, b)), (l - x0, t - y0))
    return out


def _mask_covered(img: Image.Image, dst, later) -> Image.Image:
    """Where later pieces (painting order) lie, this piece becomes white – otherwise its white
    would cover nothing, but its ink would cover the barcode above it."""
    x0, y0, x1, y1 = dst
    fx, fy = img.width / (x1 - x0), img.height / (y1 - y0)
    boxes = []
    for a0, b0, a1, b1 in later:
        l, t, r, b = max(x0, a0), max(y0, b0), min(x1, a1), min(y1, b1)
        if l < r and t < b:
            boxes.append((round((l - x0) * fx), round((t - y0) * fy),
                          round((r - x0) * fx), round((b - y0) * fy)))
    if boxes:
        img = img.copy()
        for box in boxes:
            img.paste(255, box)
    return img


def _alone(piece: Piece, src, pieces):
    """Adjusted edges only where they do not newly reach into the area of another piece
    (otherwise its content would appear twice on the label) – such edges stay as they were."""
    def hits(box, other):
        return box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]
    others = [p.src for p in pieces if p is not piece and p.page == piece.page]
    result = list(piece.src)
    for side in range(4):
        trial = list(result)
        trial[side] = src[side]
        if not any(hits(trial, o) and not hits(piece.src, o) for o in others):
            result = trial
    return tuple(result)


def _bbox(pieces):
    return (min(p.dst[0] for p in pieces), min(p.dst[1] for p in pieces),
            max(p.dst[2] for p in pieces), max(p.dst[3] for p in pieces))


def _grow(piece: Piece, src) -> Piece:
    """Piece with adjusted area: the target grows by the same scale (edges rotated)."""
    if tuple(src) == tuple(piece.src):
        return piece
    w, h = piece.turned_mm()
    sx, sy = (piece.dst[2] - piece.dst[0]) / w, (piece.dst[3] - piece.dst[1]) / h
    dl, dt = piece.src[0] - src[0], piece.src[1] - src[1]       # positive outwards
    dr, db = src[2] - piece.src[2], src[3] - piece.src[3]
    # source left/top/right/bottom → target left/top/right/bottom after clockwise rotation
    left, top, right, bottom = {0: (dl, dt, dr, db), 90: (db, dl, dt, dr),
                                180: (dr, db, dl, dt), 270: (dt, dr, db, dl)}[piece.rotation]
    x0, y0, x1, y1 = piece.dst
    return replace(piece, src=tuple(src),
                   dst=(x0 - left * sx, y0 - top * sy, x1 + right * sx, y1 + bottom * sy))
