"""Paketmarken umwandeln ohne Qt: Markentypen je Land, Laden, Erkennen, Umwandeln für den Etikettendrucker.

Eine Paketmarke (DHL, Hermes …) kommt als A4/A5/100×150-PDF oder als Bild. Jeder Markentyp schneidet
feste Bereiche aus (``Piece.src`` in mm auf der Marke), dreht sie (im Uhrzeigersinn) und setzt sie auf
ein Ausgabe-Etikett (``Piece.dst`` in mm, Rechteck nach dem Drehen) – Barcodes in Originalgröße,
Adressen und Infotexte kleiner. Die mitgelieferten Typen stehen in ``parcel_data/catalog.json``
(Herkunft: ``parcel_data/README.md``), eigene Typen in ``$XDG_DATA_HOME/labelwerk/paketmarken``
(nur die Bereiche; ``arrange`` ordnet sie auf dem Band an).

Ungeprüfte Typen (Bereiche nur aus Testblättern) rücken ihre Kanten an der echten Marke bis zum
nächsten weißen Rand (``snap``), geprüfte nicht – ihre Kanten sind genau.

``convert`` macht daraus gewöhnliche Etiketten (``Document`` mit einem ``ImageObject`` je Stück):
das Layout wird auf die bedruckbare Breite des Etiketts skaliert (breiteres Band → größer), bei
festen Etiketten so weit verkleinert, dass es passt.
"""
from __future__ import annotations

import json
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

CATALOG = Path(__file__).with_name("parcel_data") / "catalog.json"
LAYOUTS = ("62", "100x150")        # Referenz-Layouts: 62 mm endlos (quer = Seitenhöhe), 100 × 150 mm
KINDS = ("barcode", "text")        # Barcodes werden nie verkleinert angeordnet
SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif")
_IMAGE_FORMATS = ["PNG", "JPEG", "GIF"]
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_PAGES = 20
MAX_DPI = 600
MIN_PIECE_MM = 1.0                 # eigene Bereiche: Kanten mindestens so lang
EDGE_TOLERANCE_MM = 0.5            # eigene Bereiche dürfen so weit über den Seitenrand (Rundung)
SNAP_MM = 3.0                      # Kante höchstens so weit nach außen bis zum weißen Rand
SIZE_TOLERANCE_MM = 4.0
WIDE_MM = 95.0                     # ab dieser bedruckbaren Breite gilt ein 100×150-Layout
BARCODE_MIN = 0.97                 # darunter Hinweis: Barcodes verkleinert
WHITE = 200                        # Grauwert ab dem ein Pixel als weiß gilt (Kanten anpassen)
MAX_PAGE_PIXELS = 80_000_000       # Seite gerendert höchstens (A4 bei 600 dpi: 35 Mio.)
MAX_IMAGE_PIXELS = 50_000_000      # Bildmarke höchstens (vor dem Dekodieren geprüft)
DPI_PLAUSIBLE = (50, 1200)         # andere Angaben in Bildern gelten als fehlend
ASPECT_TOLERANCE = 0.03            # Bild passt zur Seite/Regel, wenn das Seitenverhältnis ±3 % stimmt
TURN_MARGIN = 1.15                 # quer liegende Marke: bessere Drehung muss so viel mehr Tinte treffen
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_own_warnings: list[str] = []


class ParcelError(ValueError):
    """Paketmarke oder Markentyp unbrauchbar (Meldung für Nutzer, übersetzt)."""


@dataclass(frozen=True)
class Piece:
    """Ein Stück der Marke: ``src`` (x0, y0, x1, y1) in mm auf Seite ``page``, im Uhrzeigersinn um
    ``rotation`` gedreht auf ``dst`` (x0, y0, x1, y1) in mm des Ausgabe-Etiketts gesetzt."""
    page: int
    src: tuple[float, float, float, float]
    rotation: int
    dst: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    kind: str = "text"

    def turned_mm(self) -> tuple[float, float]:
        """Größe des Ausschnitts nach dem Drehen (Breite, Höhe) in mm."""
        w, h = self.src[2] - self.src[0], self.src[3] - self.src[1]
        return (h, w) if self.rotation in (90, 270) else (w, h)

    def scale(self) -> float:
        """Maßstab vom Ausschnitt zum Ziel (Mittel aus beiden Achsen)."""
        w, h = self.turned_mm()
        return ((self.dst[2] - self.dst[0]) / w + (self.dst[3] - self.dst[1]) / h) / 2


@dataclass(frozen=True)
class Sheet:
    """Ein Ausgabe-Etikett eines Layouts: Größe (Breite, Höhe) in mm und Stücke in Malreihenfolge."""
    size_mm: tuple[float, float]
    pieces: tuple[Piece, ...]


@dataclass(frozen=True)
class ParcelType:
    id: str
    names: dict = field(compare=False)                 # {Sprache: Name}
    country: str = ""
    carrier: str = ""
    source_sizes: tuple[tuple[float, float], ...] = ()  # mögliche Seitengrößen der Marke in mm
    raster: dict | None = field(default=None, compare=False)   # Bildmarke: {"dpi", "x_mm", "y_mm"}
    detect: dict = field(default_factory=dict, compare=False)  # {"all", "any", "none"}: Begriffe
    layouts: dict = field(default_factory=dict, compare=False)  # "62"/"100x150" → (Sheet, …)
    pieces: tuple[Piece, ...] = ()                      # eigene Typen: nur Bereiche (arrange)
    verified: bool = False
    own: bool = False

    @property
    def name(self) -> str:
        """Name in der Sprache von labelwerk (sonst Englisch, sonst der erste)."""
        return (self.names.get(i18n.language()) or self.names.get("en")
                or next(iter(self.names.values()), self.id))


# --- Katalog ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _builtin() -> tuple[ParcelType, ...]:
    return tuple(_type(entry) for entry in _catalog()["types"])


def _type(entry: dict, own: bool = False) -> ParcelType:
    layouts = {key: tuple(Sheet(tuple(s["size_mm"]), tuple(_piece(p) for p in s["pieces"]))
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


def countries() -> list[tuple[str, str]]:
    """Länder mit mitgelieferten Typen: (Kürzel, Name in der Sprache)."""
    return [(code, _local(entry["names"])) for code, entry in _catalog()["countries"].items()]


def carriers(country: str) -> list[tuple[str, str]]:
    """Dienste eines Lands: (Schlüssel, Name)."""
    entry = _catalog()["countries"].get(country, {})
    return [(key, _local(names)) for key, names in entry.get("carriers", {}).items()]


def _local(names: dict) -> str:
    return names.get(i18n.language()) or names.get("en") or next(iter(names.values()), "")


def types(country: str | None = None) -> list[ParcelType]:
    """Mitgelieferte Typen (eines Lands) und danach die eigenen."""
    return [t for t in _builtin() if country is None or t.country == country] + own_types()


def find(type_id: str) -> ParcelType:
    for ptype in (*_builtin(), *own_types()):
        if ptype.id == type_id:
            return ptype
    raise ParcelError(_("Unknown parcel label type: {id}").format(id=type_id))


def default_country() -> str:
    """Land der Region (Gebietsschema ``LC_ALL`` › ``LC_MESSAGES`` › ``LANG``, z. B. „de_DE“ → DE),
    wenn es Typen dafür gibt – sonst das erste Land des Katalogs."""
    codes = [code for code, _name in countries()]
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key, "")
        if value:
            region = value.split(".")[0].split("@")[0].partition("_")[2].upper()
            if region in codes:
                return region
            break                                     # gesetzt, aber ohne passendes Land
    return codes[0] if codes else ""


_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def own_id(name: str, taken) -> str:
    """Kennung für einen neuen eigenen Typ aus seinem Namen („eigen-…“, frei, gültig)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold().translate(_UMLAUTS)).strip("-")
    base = ("eigen-" + (slug or "typ"))[:58].rstrip("-")
    candidate, number = base, 2
    while candidate in taken or candidate in {t.id for t in _builtin()}:
        candidate, number = f"{base}-{number}", number + 1
    return candidate


# --- Eigene Typen ----------------------------------------------------------------------
def own_dir() -> Path:
    """Ordner der eigenen Markentypen (``$XDG_DATA_HOME/labelwerk/paketmarken``)."""
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "labelwerk" / "paketmarken"


def own_types() -> list[ParcelType]:
    """Eigene Typen aus ``own_dir`` (jede Datei für sich geprüft; kaputte übergangen, Hinweis in
    ``own_warnings``)."""
    _own_warnings.clear()
    found = []
    folder = own_dir()
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.json")):
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ParcelError(_("file too large"))
            found.append(own_from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError:
            _own_warnings.append(_("Own parcel label type {name} not readable: {reason}").format(
                name=path.name, reason=_("damaged")))
        except (OSError, ValueError) as e:              # ParcelError ist ValueError
            _own_warnings.append(_("Own parcel label type {name} not readable: {reason}").format(
                name=path.name, reason=e))
    return found


def own_warnings() -> list[str]:
    """Hinweise zu eigenen Typen, die ``own_types`` übergangen hat."""
    return list(_own_warnings)


def own_from_dict(data) -> ParcelType:
    """Eigenen Typ aus JSON-Daten prüfen und anlegen (fremde Eingabe → ``ParcelError``)."""
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
    raw = data.get("pieces")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 30:
        raise bad(N_("areas"))
    width, height = max(s[0] for s in sizes), max(s[1] for s in sizes)
    pieces = []
    for number, p in enumerate(raw, start=1):
        if not isinstance(p, dict) or p.get("rotation") not in (0, 90, 180, 270) \
                or p.get("kind", "text") not in KINDS or not isinstance(p.get("page", 1), int) \
                or isinstance(p.get("page", 1), bool) or not 1 <= p.get("page", 1) <= MAX_PAGES \
                or not _numbers(p.get("src"), 4, 0, max(width, height) + 1):
            raise bad(N_("areas"))
        x0, y0, x1, y1 = p["src"]
        if x1 > width + EDGE_TOLERANCE_MM or y1 > height + EDGE_TOLERANCE_MM:
            raise ParcelError(_("Invalid parcel label type: area {number} reaches beyond the "
                                "page.").format(number=number))
        x1, y1 = min(x1, width), min(y1, height)          # Rundung am Rand: auf die Seite
        if not (x1 - x0 >= MIN_PIECE_MM and y1 - y0 >= MIN_PIECE_MM):
            raise ParcelError(_("Invalid parcel label type: area {number} is too small (at least "
                                "{size} mm).").format(number=number,
                                                      size=number_text(MIN_PIECE_MM)))
        pieces.append(Piece(p.get("page", 1), (float(x0), float(y0), float(x1), float(y1)),
                            p["rotation"], kind=p.get("kind", "text")))
    return ParcelType(type_id, dict(names), "", "own", tuple(tuple(map(float, s)) for s in sizes),
                      None, {k: list(v) for k, v in detect.items()}, {}, tuple(pieces), False, True)


def _numbers(value, count: int, low: float, high: float) -> bool:
    return (isinstance(value, list) and len(value) == count
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and low <= v <= high
                    for v in value))


def own_to_dict(ptype: ParcelType) -> dict:
    return {"version": 1, "id": ptype.id, "names": dict(ptype.names),
            "source": {"sizes_mm": [list(s) for s in ptype.source_sizes]},
            "detect": {k: list(v) for k, v in ptype.detect.items() if v},
            "pieces": [{"page": p.page, "src": list(p.src), "rotation": p.rotation, "kind": p.kind}
                       for p in ptype.pieces]}


def save_own(ptype: ParcelType) -> Path:
    """Eigenen Typ speichern (überschreibt einen gleichnamigen)."""
    own_from_dict(own_to_dict(ptype))                   # nur Gültiges kommt auf die Platte
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


# --- Laden -------------------------------------------------------------------------------
@dataclass
class Source:
    """Geladene Marke: Seitengrößen in mm, Text je Seite; Seitenbilder bei Bedarf (``page``)."""
    path: Path
    sizes_mm: list[tuple[float, float]]
    texts: list[str]
    image: Image.Image | None = None      # Bildmarke (eine Seite, Graustufen)
    image_dpi: float | None = None        # Auflösung aus der Datei (None = keine/unplausible Angabe)
    _cache: dict = field(default_factory=dict, repr=False)
    _places: dict = field(default_factory=dict, repr=False)

    @property
    def page_count(self) -> int:
        return len(self.sizes_mm)

    @property
    def raster(self) -> bool:
        return self.image is not None

    def page(self, number: int, dpi: float, ptype: ParcelType | None = None) -> Image.Image:
        """Seite ``number`` als Graustufenbild bei ``dpi`` – mit ``ptype`` in dessen Seitenfläche
        (``placement``): passende Seite wie sie ist, quer liegende gedreht, andere Größe (Letter auf
        A4) oben links auf weißer Fläche; eine Bildmarke nach der Bild-Regel des Typs bzw. auf seine
        Seitengröße gestreckt. Außerhalb der Marke ist alles weiß."""
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
            self._cache.clear()                           # nur eine Seite im Speicher
            self._cache[key] = self._render(number, dpi, place)
        return self._cache[key]

    def _render(self, number: int, dpi: float, place: "Placement") -> Image.Image:
        k = dpi / 25.4
        w_mm, h_mm = place.content_mm                     # Inhalt vor dem Drehen
        if self.raster:
            content = self.image.resize((max(1, round(w_mm * k)), max(1, round(h_mm * k))),
                                        Image.LANCZOS)
        else:
            content = _render_pdf(self.path, number, dpi)
        if place.rotation:
            content = content.rotate(-place.rotation, expand=True)   # im Uhrzeigersinn
        frame = Image.new("L", (round(place.frame_mm[0] * k), round(place.frame_mm[1] * k)), 255)
        frame.paste(content, (round(place.offset_mm[0] * k), round(place.offset_mm[1] * k)))
        return frame


@dataclass(frozen=True)
class Placement:
    """Wie eine Seite in der Fläche eines Typs liegt: Fläche, Inhalt (mm vor dem Drehen), Drehung
    im Uhrzeigersinn, Lage der linken oberen Ecke (mm, nach dem Drehen)."""
    frame_mm: tuple[float, float]
    content_mm: tuple[float, float]
    rotation: int = 0
    offset_mm: tuple[float, float] = (0.0, 0.0)


def placement(source: Source, ptype: ParcelType | None, number: int = 1) -> Placement:
    """Lage der Seite ``number`` in der Seitenfläche von ``ptype`` (ohne Typ: wie sie ist) – passt sie
    nicht, ``ParcelError`` (z. B. falscher Typ von Hand gewählt)."""
    size = source.sizes_mm[number - 1]
    if ptype is None or not ptype.source_sizes:
        return Placement(size, size)
    frame = ptype.source_sizes[0]
    if source.raster:
        return _raster_placement(source, ptype, frame)
    for a, b in ptype.source_sizes:
        if abs(size[0] - a) <= SIZE_TOLERANCE_MM and abs(size[1] - b) <= SIZE_TOLERANCE_MM:
            return Placement(frame, size)                 # passt (Letter: oben links auf A4)
    for a, b in ptype.source_sizes:
        if abs(size[0] - b) <= SIZE_TOLERANCE_MM and abs(size[1] - a) <= SIZE_TOLERANCE_MM:
            return Placement(frame, size, _turn(source, ptype, number))
    raise ParcelError(_("The parcel label ({width} × {height} mm) does not fit the type {name}.")
                      .format(width=round(size[0]), height=round(size[1]), name=ptype.name))


def _raster_placement(source: Source, ptype: ParcelType, frame) -> Placement:
    img = source.image
    rule = ptype.raster
    if rule is not None:                                  # z. B. Amazon-GIF: feste Lage
        px = rule.get("px")
        if px and not _aspect_fits(img.size, px):
            raise ParcelError(_("The image does not fit the type {name}.").format(name=ptype.name))
        dpi = float(rule.get("dpi", 300)) * (img.width / px[0] if px else 1.0)
        content = (img.width * 25.4 / dpi, img.height * 25.4 / dpi)
        return Placement(frame, content, 0, (float(rule.get("x_mm", 0)), float(rule.get("y_mm", 0))))
    for a, b in ptype.source_sizes:                       # Bild einer ganzen Seite: gestreckt
        if _aspect_fits(img.size, (a, b)):
            return Placement(frame, (a, b))
        if _aspect_fits(img.size, (b, a)):
            return Placement(frame, (b, a), _turn(source, ptype, 1))
    raise ParcelError(_("The image does not fit the type {name}.").format(name=ptype.name))


def _aspect_fits(size, ref) -> bool:
    return abs(size[0] / size[1] - ref[0] / ref[1]) <= ASPECT_TOLERANCE * ref[0] / ref[1]


def _turn(source: Source, ptype: ParcelType, number: int) -> int:
    """Quer liegende Marke: Drehung (90 oder 270) mit mehr Tinte in den Bereichen des Typs; liegen
    beide gleich auf, ist die Richtung nicht eindeutig → ``ParcelError``."""
    pieces = [p for p in all_pieces(ptype) if p.page == number]
    dpi = 40.0
    scores = {}
    for rotation in (90, 270):
        place = Placement(ptype.source_sizes[0],
                          source.sizes_mm[number - 1] if not source.raster
                          else (ptype.source_sizes[0][1], ptype.source_sizes[0][0]), rotation)
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
    """Seite rendern; die Datei kann seit dem Laden gelöscht, verschoben oder ersetzt sein →
    ``ParcelError`` (übersetzt)."""
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
    """Alle Bereiche eines Typs (eigene: ``pieces``, sonst die des ersten Layouts)."""
    if ptype.pieces:
        return ptype.pieces
    sheets = next(iter(ptype.layouts.values()), ())
    return tuple(p for sheet in sheets for p in sheet.pieces)


def load(path: str | Path) -> Source:
    """Marke laden: PDF (Seitengrößen, Text) oder Bild (PNG/JPG/GIF, eine Seite – wie Bild-Objekte
    gelesen: Transparenz weiß, 16 Bit, EXIF-Lage, Größe begrenzt); fremde Eingabe geprüft (Endung,
    Dateigröße, Pixel, Seitenzahl) – Fehler als ``ParcelError``."""
    path = Path(path)
    try:
        path = _checked(path, SUFFIXES[1:], "PDF, PNG, JPG, GIF", 1)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ParcelError(_("Parcel label file too large: {name}").format(name=path.name))
        with _readable(path):
            if path.suffix.lower() == ".pdf":
                return _load_pdf(path)
            with Image.open(path, formats=_IMAGE_FORMATS) as head:   # nur der Kopf: Größe, dpi
                pixels = head.width * head.height
                dpi = head.info.get("dpi")
            if pixels > MAX_IMAGE_PIXELS:
                raise ParcelError(_("Parcel label image has too many pixels: {name}").format(
                    name=path.name))
            dpi = float(dpi[0]) if dpi and dpi[0] else None
            if dpi is not None and not DPI_PLAUSIBLE[0] <= dpi <= DPI_PLAUSIBLE[1]:
                dpi = None                                # Angabe unbrauchbar: wie ohne
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


# --- Erkennen ---------------------------------------------------------------------------
def detect(source: Source, country: str | None = None, label_id: str | None = None,
           own: list[ParcelType] | None = None) -> list[tuple[ParcelType, float]]:
    """Passende Typen mit Punktzahl, bester zuerst: Seitengröße muss passen (Bildmarken: Typ mit
    Bild-Regel), alle Begriffe aus ``all`` im Text, ``any`` zählt mit, ``none`` zählt dagegen; mit
    ``label_id`` gewinnt bei Gleichstand der Typ mit einem Layout für dieses Etikett."""
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
            score += 0.5                                  # eigener Typ: genauer gemeint
        if label_id is not None and ptype.layouts:
            score += 0.25 if ("100x150" in ptype.layouts) == wide else 0.0
        if score >= 3:
            found.append((ptype, score, order))
    found.sort(key=lambda f: (-f[1], not f[0].verified, f[2]))
    return [(ptype, score) for ptype, score, _ in found]


def ambiguous(found: list[tuple[ParcelType, float]]) -> list[ParcelType]:
    """Gleichstand an der Spitze von ``detect``, den keine geprüfte Vorlage entscheidet: die
    gleichauf liegenden Typen (dann nicht selbst wählen, sondern fragen); sonst []."""
    if len(found) < 2 or found[0][0].verified or found[1][1] < found[0][1]:
        return []
    return [ptype for ptype, score in found if score == found[0][1]]


def _fits(source: Source, ptype: ParcelType) -> bool:
    """Passt die Marke zum Typ? PDF: Seitengröße (auch quer); Bild: Bild-Regel (Seitenverhältnis der
    erwarteten Pixel) bzw. Seitenverhältnis einer Seitengröße."""
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


# --- Kanten anpassen --------------------------------------------------------------------
def snap(img: Image.Image, box_mm, dpi: float, limit_mm: float = SNAP_MM):
    """Kanten eines Ausschnitts (mm) nach außen bis zur ersten ganz weißen Zeile/Spalte rücken,
    wenn sie Inhalt durchschneiden – höchstens ``limit_mm``; ohne weiße Linie in Reichweite bleibt
    die Kante. Weiße Kanten bleiben, wie sie sind."""
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
            return True                                   # Seitenrand gilt als weiß
        return gray.crop((a0, b0, a1, b1)).getextrema()[0] >= WHITE

    edges = list(box_mm)
    # links, oben, rechts, unten: Linie direkt innerhalb der Kante, dann Schritt für Schritt hinaus
    for side in range(4):
        def line(n):
            if side == 0:
                return white(x0 - 1 - n, y0, x0 - n, y1)
            if side == 1:
                return white(x0, y0 - 1 - n, x1, y0 - n)
            if side == 2:
                return white(x1 + n, y0, x1 + n + 1, y1)
            return white(x0, y1 + n, x1, y1 + n + 1)
        if line(-1) or line(0):                           # Kante schneidet keinen Inhalt
            continue
        for n in range(1, reach + 1):
            if line(n):                                   # erste weiße Linie außerhalb
                edges[side] += -n / k if side < 2 else n / k
                break
    return tuple(edges)


# --- Anordnen (eigene Typen) ---------------------------------------------------------------
def arrange(pieces, across_mm: float, gap_mm: float = 1.0) -> Sheet:
    """Stücke nacheinander in Spalten längs des Bands, je Spalte bis zur Breite ``across_mm``:
    Barcodes 1:1 (nur wenn sie quer nicht passen, kleiner), Texte höchstens so verkleinert, dass sie
    quer passen."""
    placed, x, y, column = [], 0.0, 0.0, 0.0
    for piece in pieces:
        w, h = piece.turned_mm()
        s = min(1.0, across_mm / h)
        w, h = w * s, h * s
        if y > 0 and y + h > across_mm + 1e-6:            # neue Spalte
            x, y, column = x + column + gap_mm, 0.0, 0.0
        placed.append(replace(piece, dst=(x, y, x + w, y + h)))
        y += h + gap_mm
        column = max(column, w)
    return Sheet((x + column, across_mm), tuple(placed))


# --- Umwandeln ----------------------------------------------------------------------------
@dataclass
class Conversion:
    documents: list[Document]
    notes: list[str]
    layout: str                 # "62", "100x150", "arranged" (Stücke neu angeordnet) oder "own"
    scale: float                # Faktor vom Layout aufs Etikett


def convert(source: Source, ptype: ParcelType, label_id: str, model: str = "QL-600") -> Conversion:
    """Marke ``source`` nach Typ ``ptype`` in Etiketten für ``label_id`` umwandeln (je Ausgabe-
    Etikett ein ``Document`` mit einem Bild-Objekt je Stück, Strich/Schwelle 128). Passt die Marke
    nicht zum Typ (Seitengröße, Bild), ``ParcelError``.

    Layout: ab ``WIDE_MM`` bedruckbarer Breite das 100×150-Layout, sonst das 62-mm-Layout; fehlt das
    passende (z. B. 1a auf 62 mm), ordnet ``arrange`` die Stücke des vorhandenen neu an („arranged“),
    eigene Typen immer („own“)."""
    label = get_label(label_id)
    if label.shape == "round":
        raise ParcelError(_("Round labels are not suitable for parcel labels."))
    for number in sorted({p.page for p in all_pieces(ptype)}):
        if number > source.page_count:
            raise ParcelError(_("The parcel label has no page {page}.").format(page=number))
        placement(source, ptype, number)                  # passt die Marke? sonst Meldung
    k = label.dpi / 25.4
    across = label.width / k
    along = None if label.height is None else label.height / k
    wide = across >= WIDE_MM
    if not ptype.layouts:
        key, sheets = "own", (arrange(ptype.pieces, across),)
    elif wide and "100x150" in ptype.layouts:
        key, sheets = "100x150", ptype.layouts["100x150"]
    elif "62" in ptype.layouts:
        key, sheets = "62", ptype.layouts["62"]
    else:                                                 # nur 100×150, aber schmales Band
        key = "arranged"
        sheets = tuple(arrange(sheet.pieces, across) for sheet in next(iter(ptype.layouts.values())))
    feed = label.feed_margin / k
    max_len = length_limits(model)[1] / k if label.height is None else None
    documents, notes, scales, shrunk = [], [], [], 1.0
    for sheet in sheets:
        doc, f, small = _sheet_document(source, ptype, sheet, label_id, across, along, feed, max_len,
                                        grow=key in LAYOUTS)
        documents.append(doc)
        scales.append(f)
        shrunk = min(shrunk, small)
    if shrunk < BARCODE_MIN:
        notes.append(_("Barcodes shrunk to {percent} % – check before shipping that they can be "
                       "read.").format(percent=round(shrunk * 100)))
    return Conversion(documents, notes, key, min(scales))


def _sheet_document(source, ptype, sheet, label_id, across, along, feed, max_len, grow):
    label = get_label(label_id)
    pieces = sheet.pieces
    # erste Schätzung des Maßstabs → Auflösung zum Rendern der Marke (Seite höchstens MAX_PAGE_PIXELS)
    f0, _o = _fit(_bbox(pieces), sheet, across, along, max_len, grow)
    frame_w, frame_h = ptype.source_sizes[0] if ptype.source_sizes else source.sizes_mm[0]
    dpi = min(MAX_DPI, label.dpi * max(1.0, max(p.scale() for p in pieces) * f0),
              25.4 * (MAX_PAGE_PIXELS / (frame_w * frame_h)) ** 0.5 * 0.99)
    snapped = []
    for piece in pieces:
        src = piece.src
        if not ptype.verified:                            # geprüfte Typen haben genaue Kanten
            page = source.page(piece.page, dpi, ptype)
            src = _alone(piece, snap(page, piece.src, dpi), pieces)
        snapped.append(_grow(piece, src))
    box = _bbox(snapped)
    f, horizontal = _fit(box, sheet, across, along, max_len, grow)
    bx0, by0, bx1, by1 = box
    content_w, content_h = (bx1 - bx0) * f, (by1 - by0) * f
    if horizontal:                                         # Seite x längs des Bands
        off_x = 0.0 if along is None else (along - content_w) / 2
        off_y = (across - content_h) / 2
    else:
        off_x = (across - content_w) / 2
        off_y = 0.0 if along is None else (along - content_h) / 2
    objects = []
    k = dpi / 25.4
    for n, piece in enumerate(snapped):
        page = source.page(piece.page, dpi, ptype)
        img = _crop_white(page, tuple(round(v * k) for v in piece.src))
        if piece.rotation:
            img = img.rotate(-piece.rotation, expand=True, fillcolor=255)   # im Uhrzeigersinn
        img = _mask_covered(img, piece.dst, [p.dst for p in snapped[n + 1:]])
        obj = ImageObject.from_image(img, dpi, source.path.name, piece.page)
        dx0, dy0, dx1, dy1 = piece.dst
        objects.append(replace(obj, x_mm=(dx0 - bx0) * f + off_x, y_mm=(dy0 - by0) * f + off_y,
                               w_mm=(dx1 - dx0) * f, h_mm=(dy1 - dy0) * f, keep_ratio=False,
                               mode="line", threshold=128))
    length = None
    if along is None:
        length = (content_w if horizontal else content_h) + 2 * feed
    doc = Document(label_id, length_mm=length, orientation="horizontal" if horizontal else "vertical",
                   margin_mm=0.0, objects=objects)
    barcodes = [p.scale() * f for p in snapped if p.kind == "barcode"]
    return doc, f, min(barcodes, default=1.0)


def _crop_white(page: Image.Image, box) -> Image.Image:
    """Ausschnitt; was außerhalb der Seite liegt, ist weiß (Pillow füllte schwarz)."""
    x0, y0, x1, y1 = box
    out = Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)), 255)
    out.paste(page.crop((max(0, x0), max(0, y0), min(page.width, x1), min(page.height, y1))),
              (max(0, -x0), max(0, -y0)))
    return out


def _mask_covered(img: Image.Image, dst, later) -> Image.Image:
    """Wo spätere Stücke (Malreihenfolge) liegen, wird dieses Stück weiß – sonst verdeckte sein
    Weiß nichts, seine Tinte aber den Barcode darüber."""
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
    """Angepasste Kanten nur, wo sie nicht neu in den Ausschnitt eines anderen Stücks reichen
    (sonst käme dessen Inhalt doppelt aufs Etikett) – solche Kanten bleiben, wie sie waren."""
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


def _fit(box, sheet, across, along, max_len, grow):
    """Maßstab und Lage (True = Seite x längs des Bands): Endlosband – Breite füllt das Band
    (``grow``: auch größer), höchstens ``max_len`` lang; festes Etikett – passt hinein, die Lage
    mit dem größeren Maßstab gewinnt (bei Gleichstand die natürliche: lange Seite längs)."""
    w, h = box[2] - box[0], box[3] - box[1]
    natural = sheet.size_mm[0] >= sheet.size_mm[1]
    options = []
    for horizontal in (natural, not natural):
        long_, short = (w, h) if horizontal else (h, w)
        f = across / short
        if not grow:
            f = min(1.0, f)
        limit = along if along is not None else max_len
        if limit is not None:
            f = min(f, limit / long_)
        options.append((f, horizontal))
        if along is None:
            break                                          # Endlosband: natürliche Lage
    return max(options, key=lambda o: o[0])


def _grow(piece: Piece, src) -> Piece:
    """Stück mit angepasstem Ausschnitt: das Ziel wächst im selben Maßstab mit (Kanten gedreht)."""
    if tuple(src) == tuple(piece.src):
        return piece
    w, h = piece.turned_mm()
    sx, sy = (piece.dst[2] - piece.dst[0]) / w, (piece.dst[3] - piece.dst[1]) / h
    dl, dt = piece.src[0] - src[0], piece.src[1] - src[1]       # nach außen positiv
    dr, db = src[2] - piece.src[2], src[3] - piece.src[3]
    # Quelle links/oben/rechts/unten → Ziel links/oben/rechts/unten nach Drehung im Uhrzeigersinn
    left, top, right, bottom = {0: (dl, dt, dr, db), 90: (db, dl, dt, dr),
                                180: (dr, db, dl, dt), 270: (dt, dr, db, dl)}[piece.rotation]
    x0, y0, x1, y1 = piece.dst
    return replace(piece, src=tuple(src),
                   dst=(x0 - left * sx, y0 - top * sy, x1 + right * sx, y1 + bottom * sy))
