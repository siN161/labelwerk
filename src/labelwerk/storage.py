"""Labels as a file (*.labelwerk): JSON, versioned, without Qt.

``{"format": "labelwerk", "version": 1, "document": {…}}`` – objects with ``"type"`` (``text`` |
``image`` | ``barcode``) and their fields; image data (PNG, SVG) Base64. A file can come from
anywhere: on loading every field is checked by kind, value range and structure (``StorageError``
with a translated message instead of a traceback; what is accepted fails at most
comprehensibly when rendering). Image data must be PNG (Pillow detects formats by content – EPS would
otherwise run through Ghostscript) and is decoded completely. Unknown fields are skipped, missing
ones get the default value. The schemas name every field of the dataclasses (a test keeps them
in sync).
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import math
import os
import reprlib
import stat
from dataclasses import replace
from pathlib import Path

from PIL import Image

from . import barcodes
from .document import (ALIGNMENTS, BARCODE_KINDS, BARCODE_MM, COLORS, CUTS, FRAME_LINE_MM,
                       FRAME_STYLES, MAX_BARCODE_DATA, MAX_DIGITS, MAX_FRAME_MM, MAX_MARGIN_MM,
                       MAX_NUMBER, MODULE_LIMIT, MAX_POSITION_MM, MAX_SERIES_ROWS, ORIENTATIONS,
                       QR_LEVELS, ROTATIONS, BarcodeObject, Document, Frame, ImageObject, Numbering,
                       Paragraph, Series, Span, TextObject)
from .i18n import _
from .imaging import MAX_PIXELS, MODES
from .labels import get_label

FORMAT = "labelwerk"
VERSION = 1
SUFFIX = ".labelwerk"
RECENT_FILES = 10
MAX_FILE_BYTES = 32 * 1024 * 1024     # larger files are not read
MAX_OBJECTS = 500                     # objects per label
MAX_FRAME_DOTS = 100_000_000          # sum of the frame areas in dots (at label dpi)
MAX_BARCODE_TOTAL = 20_000            # characters of all barcode contents (encoding on loading stays cheap)
MAX_SIZE_MM = 1_000.0                 # frame, label length (QL: at most 1 m)
MAX_SIZE_PT = 1_000.0                 # font size (beyond MAX_PT, as scale_text allows)
LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85  "   # belong between paragraphs, not inside pieces
_TMP_PREFIX = ".labelwerk-"

# Field → kind (see ``_KINDS``)
SPAN = {"text": "span_text", "family": "str?", "size_pt": "pt?", "bold": "bool", "italic": "bool",
        "underline": "bool"}
PARAGRAPH = {"align": "align"}                                    # plus “spans”
TEXT = {"size_pt": "pt?", "font_path": "str?", "fit": "bool", "x_mm": "pos?", "y_mm": "pos?",
        "w_mm": "size?", "h_mm": "size?", "rotation": "rotation", "color": "color"}  # plus “paragraphs”
IMAGE = {"png": "bytes", "source": "str", "page": "page?", "crop": "crop", "x_mm": "pos",
         "y_mm": "pos", "w_mm": "size", "h_mm": "size", "rotation": "rotation", "mode": "mode",
         "threshold": "threshold", "invert": "bool", "keep_ratio": "bool", "dpi": "dpi",
         "svg": "bytes?", "color": "color"}
BARCODE = {"kind": "barcode_kind", "data": "barcode_data", "x_mm": "pos", "y_mm": "pos",
           "module": "module", "h_mm": "barcode_mm", "rotation": "rotation", "text": "bool",
           "error": "qr_level", "color": "color"}
FRAME = {"style": "frame_style", "rounded": "bool", "line_mm": "frame_line",
         "inset_mm": "frame_mm", "padding_mm": "frame_mm"}
NUMBERING = {"start": "number", "step": "step", "count": "count", "digits": "digits"}
SERIES = {"source": "path?", "sheet": "str?", "cut": "cut"}       # plus “numbering”
DOCUMENT = {"label_id": "label", "length_mm": "size?", "orientation": "orientation",
            "margin_mm": "margin"}                                # plus “objects”, “frame”, “series”


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _text(v) -> bool:
    """Text that can be written as UTF-8 (no lone surrogates)."""
    if not isinstance(v, str):
        return False
    try:
        v.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _label(v) -> bool:
    try:
        get_label(v)
    except (ValueError, TypeError):
        return False
    return True


_KINDS = {
    "str": _text, "bool": lambda v: isinstance(v, bool), "bytes": lambda v: isinstance(v, str),
    "span_text": _text,
    "pos": lambda v: _num(v) and abs(v) <= MAX_POSITION_MM,
    "size": lambda v: _num(v) and 0 < v <= MAX_SIZE_MM,
    "pt": lambda v: _num(v) and 0 < v <= MAX_SIZE_PT,
    "margin": lambda v: _num(v) and 0 <= v <= MAX_MARGIN_MM,
    "dpi": lambda v: _num(v) and 0 < v <= 1_000_000,
    "threshold": lambda v: _int(v) and 0 <= v <= 255,
    "page": lambda v: _int(v) and v >= 1,
    "align": lambda v: v in ALIGNMENTS, "orientation": lambda v: v in ORIENTATIONS,
    "rotation": lambda v: _int(v) and v in ROTATIONS,
    "mode": lambda v: v in MODES, "label": _label,
    "frame_style": lambda v: v in FRAME_STYLES,
    "frame_line": lambda v: _num(v) and FRAME_LINE_MM[0] <= v <= FRAME_LINE_MM[1],
    "frame_mm": lambda v: _num(v) and 0 <= v <= MAX_FRAME_MM,
    "number": lambda v: _int(v) and abs(v) <= MAX_NUMBER,
    "step": lambda v: _int(v) and v != 0 and abs(v) <= MAX_NUMBER,
    "count": lambda v: _int(v) and 1 <= v <= MAX_SERIES_ROWS,
    "digits": lambda v: _int(v) and 0 <= v <= MAX_DIGITS,
    "cut": lambda v: v in CUTS,
    "barcode_kind": lambda v: v in BARCODE_KINDS,
    "barcode_data": lambda v: _text(v) and len(v) <= MAX_BARCODE_DATA,
    "module": lambda v: _int(v) and 1 <= v <= MODULE_LIMIT,
    "barcode_mm": lambda v: _num(v) and BARCODE_MM[0] <= v <= BARCODE_MM[1],
    "qr_level": lambda v: v in QR_LEVELS,
    "color": lambda v: v in COLORS,
    "path": lambda v: _text(v) and v != "" and "\x00" not in v,
    "crop": lambda v: v is None or (isinstance(v, list) and len(v) == 4 and all(map(_int, v))),
}


class StorageError(ValueError):
    """File cannot be read as a label (translated message, with file name)."""


def os_reason(error: OSError) -> str:
    """Reason for a file error in the current language (not the operating system's English text)."""
    if isinstance(error, FileNotFoundError):
        return _("folder missing")
    if isinstance(error, IsADirectoryError):
        return _("is a folder")
    if isinstance(error, PermissionError):
        return _("no permission")
    if getattr(error, "errno", None) == 36:     # ENAMETOOLONG
        return _("name too long")
    if getattr(error, "errno", None) == 28:     # ENOSPC
        return _("no space left on the disk")
    return _("access error")


def exists(path: str | Path) -> bool:
    """Does the path exist? Even an unreachable one (EACCES, ENOTCONN, EIO …) does not raise."""
    try:
        return Path(path).exists()
    except OSError:
        return False


# --- Writing -----------------------------------------------------------------------------
def _dump(obj, schema: dict) -> dict:
    out = {}
    for key, kind in schema.items():
        value = getattr(obj, key)
        if kind.startswith("bytes") and value is not None:
            value = base64.b64encode(value).decode("ascii")
        elif isinstance(value, tuple):
            value = list(value)
        out[key] = value
    return out


def to_dict(doc: Document, base: str | Path | None = None) -> dict:
    """``base``: folder of the file – a table in or below it is saved relative
    (no user name in forwarded labels, folder movable together with the table)."""
    objects = []
    for obj in doc.objects:
        if isinstance(obj, TextObject):
            objects.append({"type": "text", **_dump(obj, TEXT), "paragraphs": [
                {**_dump(p, PARAGRAPH), "spans": [_dump(s, SPAN) for s in p.spans]}
                for p in obj.paragraphs]})
        elif isinstance(obj, BarcodeObject):
            objects.append({"type": "barcode", **_dump(obj, BARCODE)})
        else:
            objects.append({"type": "image", **_dump(obj, IMAGE)})
    frame = None if doc.frame is None else _dump(doc.frame, FRAME)
    series = None
    if doc.series is not None:
        numbering = doc.series.numbering
        series = {**_dump(doc.series, SERIES),
                  "numbering": None if numbering is None else _dump(numbering, NUMBERING)}
        if base is not None and doc.series.source is not None:
            series["source"] = _relative(doc.series.source, base)
    return {"format": FORMAT, "version": VERSION,
            "document": {**_dump(doc, DOCUMENT), "objects": objects, "frame": frame,
                         "series": series}}


def save(doc: Document, path: str | Path) -> Path:
    """Save atomically (temporary file in the same folder, then replace): an abort
    leaves the old file. A symlink is followed (the target changes), permissions of an
    existing file stay, new files get the permissions per umask. Errors:
    ``OSError`` with a translated message."""
    path = Path(path)
    target = Path(os.path.realpath(path))
    try:
        text = json.dumps(to_dict(doc, target.parent), ensure_ascii=False, indent=1,
                          allow_nan=False) + "\n"
        text.encode("utf-8")                # single surrogates cannot be written
    except UnicodeEncodeError as e:
        raise OSError(_("{name} was not saved: invalid characters in the text").format(
            name=path.name)) from e
    except ValueError as e:
        raise OSError(_("{name} was not saved: invalid numbers in the label").format(
            name=path.name)) from e
    tmp = None
    try:
        for attempt in range(100):          # free name for the temporary file
            tmp = target.with_name(f"{_TMP_PREFIX}{os.getpid()}-{attempt}.tmp")
            try:
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)   # umask applies
                break
            except FileExistsError:
                continue
        else:
            raise FileExistsError(tmp)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if target.exists():
            os.chmod(tmp, stat.S_IMODE(target.stat().st_mode))
        os.replace(tmp, target)
        tmp = None
    except OSError as e:
        raise OSError(_("{name} was not saved ({reason})").format(name=path.name,
                                                              reason=os_reason(e))) from e
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)
    return path


# --- Reading -----------------------------------------------------------------------------
def _check(value, kind: str, key: str, where: str):
    """Check and convert a value (Base64 → bytes); invalid → StorageError."""
    optional = kind.endswith("?")
    kind = kind.rstrip("?")
    if value is None and optional:
        return None
    if not _KINDS[kind](value):
        if kind == "label":
            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
            raise StorageError(_("Unknown label{where}: {value}").format(where=where,
                                                                      value=reprlib.repr(value)))
        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
        raise StorageError(_("Invalid value for “{key}”{where}: {value}").format(
            key=key, where=where, value=reprlib.repr(value)))
    if kind == "span_text" and any(c in value for c in LINE_BREAKS):
        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
        raise StorageError(_("Line break in “{key}”{where} – lines are separate paragraphs").format(
            key=key, where=where))
    if kind == "bytes":
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as e:
            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
            raise StorageError(_("Image data “{key}”{where} not readable").format(
                key=key, where=where)) from e
    return value


def _load(data, schema: dict, where: str, required: tuple[str, ...] = ()) -> dict:
    if not isinstance(data, dict):
        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
        raise StorageError(_("Entry{where} is not an object").format(where=where))
    for key in required:
        if key not in data:
            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
            raise StorageError(_("“{key}”{where} missing").format(key=key, where=where))
    return {key: _check(data[key], kind, key, where) for key, kind in schema.items() if key in data}


def _list(data: dict, key: str, where: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
        raise StorageError(_("Invalid value for “{key}”{where}: {value}").format(
            key=key, where=where, value=reprlib.repr(value)))
    return value


def _image(data: dict, where: str) -> ImageObject:
    values = _load(data, IMAGE, where, required=("png", "w_mm", "h_mm"))
    try:
        with Image.open(io.BytesIO(values["png"]), formats=["PNG"]) as img:
            size = img.size
            if max(size) > MAX_PIXELS:
                # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
                raise StorageError(_("Image{where} too large ({width} × {height} pixels, at most "
                                     "{limit})").format(where=where, width=size[0], height=size[1],
                                                        limit=MAX_PIXELS))
            img.load()                      # decode completely: broken data shows up now
    except StorageError:
        raise
    except Exception as e:  # Pillow raises different errors depending on the damage
        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
        raise StorageError(_("Image data{where} not readable (PNG only)").format(where=where)) from e
    crop = values.get("crop")
    if crop is not None and not (0 <= crop[0] < crop[2] <= size[0]
                                 and 0 <= crop[1] < crop[3] <= size[1]):
        # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
        raise StorageError(_("Value for “crop”{where} is not inside the image: {crop}").format(
            where=where, crop=crop))
    return ImageObject(**values)


def _series(data) -> Series:
    # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
    values = _load(data, SERIES, _(" in the series"))
    numbering = data.get("numbering")
    if numbering is not None:
        # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
        values["numbering"] = Numbering(**_load(numbering, NUMBERING, _(" in the numbering")))
    if (values.get("source") is None) == (numbering is None):
        raise StorageError(_("A series needs exactly one: table or numbering"))
    return Series(**values)


def _is_file(path: str) -> bool:
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except (OSError, ValueError):       # ValueError: path with NUL character
        return False


def _text_object(item: dict, where: str) -> TextObject:
    values = _load(item, TEXT, where)
    if values.get("font_path") is not None and not _is_file(values["font_path"]):
        values["font_path"] = None      # only an existing, regular file goes to FreeType
    paragraphs = []
    for p in _list(item, "paragraphs", where):
        align = _load(p, PARAGRAPH, where)
        spans = [Span(**_load(s, SPAN, where, required=("text",)))
                 for s in _list(p, "spans", where)]
        paragraphs.append(Paragraph(spans, **align))
    return TextObject(paragraphs or [Paragraph([Span("")])], **values)   # empty = one line


def _relative(source: str, base: str | Path) -> str:
    """Path relative to ``base`` (with “/”) if it lies within it – otherwise as it is."""
    try:
        return Path(source).relative_to(Path(os.path.realpath(base))).as_posix()
    except ValueError:
        return source


def from_dict(data, base: str | Path | None = None) -> Document:
    """``base``: folder of the file – relative table paths apply from there."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise StorageError(_("not a labelwerk file"))
    version = data.get("version")
    if not _int(version) or version < 1:
        raise StorageError(_("not a labelwerk file (format version {version})").format(
            version=reprlib.repr(version)))
    if version > VERSION:
        raise StorageError(_("saved with a newer labelwerk (format version {version}) – please "
                             "update labelwerk").format(version=version))
    document = data.get("document")
    values = _load(document, DOCUMENT, "")
    frame = document.get("frame")
    if frame is not None:                   # missing or null: no frame
        # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
        values["frame"] = Frame(**_load(frame, FRAME, _(" in the border")))
    if document.get("series") is not None:  # missing or null: no series
        values["series"] = _series(document["series"])
        source = values["series"].source
        if base is not None and source is not None and not Path(source).is_absolute():
            values["series"] = replace(values["series"],
                                       source=str(Path(os.path.realpath(base)) / source))
    items = _list(document, "objects", "")
    if len(items) > MAX_OBJECTS:
        raise StorageError(_("Label too large ({count} objects, at most {limit})").format(
            count=len(items), limit=MAX_OBJECTS))
    objects = []
    for number, item in enumerate(items, start=1):
        # Translators: location inserted into file error messages (leading space): "Invalid value for \"x\" in object 3"
        where = _(" in object {number}").format(number=number)
        kind = item.get("type") if isinstance(item, dict) else None
        if kind == "text":
            objects.append(_text_object(item, where))
        elif kind == "image":
            objects.append(_image(item, where))
        elif kind == "barcode":
            objects.append(BarcodeObject(**_load(item, BARCODE, where, required=("kind", "data"))))
        else:
            # Translators: {where} is a location with a leading space, e.g. " in object 3" (or empty)
            raise StorageError(_("Unknown object type{where}: {kind}").format(where=where,
                                                                               kind=reprlib.repr(kind)))
    total = sum(len(o.data) for o in objects if isinstance(o, BarcodeObject))
    if total > MAX_BARCODE_TOTAL:
        raise StorageError(_("Label too large (barcode contents together {total} characters, at "
                             "most {limit})").format(total=total, limit=MAX_BARCODE_TOTAL))
    dpi = get_label(values.get("label_id", Document().label_id)).dpi
    dots = sum(_dots(o, dpi) for o in objects)
    if dots > MAX_FRAME_DOTS:
        raise StorageError(_("Label too large (objects together {dots:.0f} million dots, at most "
                             "{limit})").format(dots=dots / 1e6, limit=MAX_FRAME_DOTS // 1_000_000))
    return Document(**values, objects=objects)


def _dots(obj, dpi: int) -> float:
    """Frame area in dots (limit “Label too large”); barcodes with their real area,
    with series placeholders or invalid content with the largest possible one
    (``barcodes.max_size``) – what was saved can be opened again."""
    if isinstance(obj, BarcodeObject):
        from .series import placeholders            # series reads storage – only here
        w, h = barcodes.max_size(obj, dpi)
        if not placeholders(Document(objects=[obj])):
            try:
                w, h = barcodes.size(obj, dpi)
            except barcodes.BarcodeError:
                pass
        return w * h
    return obj.w_mm * obj.h_mm * (dpi / 25.4) ** 2 if obj.w_mm and obj.h_mm else 0


def _reject_constant(name: str):
    raise ValueError(f"{name} is not a number")      # only internal (json)


def load(path: str | Path) -> Document:
    """Label from a file; every error as ``StorageError`` with file name."""
    path = Path(path)
    try:
        info = path.stat()
        if stat.S_ISDIR(info.st_mode):
            raise IsADirectoryError(path)
        if not stat.S_ISREG(info.st_mode):      # a FIFO or similar would hang on reading
            raise StorageError(_("{name}: not a file").format(name=path.name))
        if info.st_size > MAX_FILE_BYTES:
            raise StorageError(_("{name}: file too large").format(name=path.name))
        text = path.read_text(encoding="utf-8-sig")       # also with BOM (Windows editors)
    except FileNotFoundError as e:
        raise StorageError(_("File not found: {path}").format(path=path)) from e
    except OSError as e:
        raise StorageError(_("{name} cannot be read ({reason})").format(
            name=path.name, reason=os_reason(e))) from e
    except UnicodeDecodeError as e:
        raise StorageError(_("{name}: not a labelwerk file (not UTF-8 text)").format(
            name=path.name)) from e
    try:
        data = json.loads(text, parse_constant=_reject_constant)   # NaN, Infinity
    except RecursionError as e:
        raise StorageError(_("{name}: file damaged (nested too deeply)").format(
            name=path.name)) from e
    except ValueError as e:
        raise StorageError(_("{name}: not a labelwerk file or damaged").format(name=path.name)) from e
    try:
        return from_dict(data, path.parent)
    except StorageError as e:
        raise StorageError(f"{path.name}: {e}") from e
    except (TypeError, AttributeError, KeyError, RecursionError, OverflowError) as e:
        raise StorageError(_("{name}: file damaged").format(name=path.name)) from e   # safety net


def add_recent_file(recent: list[str], path: str, limit: int = RECENT_FILES) -> list[str]:
    """“Recently opened”: ``path`` to the front, without duplicates, at most ``limit``."""
    return [path, *(p for p in recent if p != path)][:limit]
