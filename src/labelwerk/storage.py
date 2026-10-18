"""Etiketten als Datei (*.labelwerk): JSON, versioniert, ohne Qt.

``{"format": "labelwerk", "version": 1, "document": {…}}`` – Objekte mit ``"type"`` (``text`` |
``image``) und ihren Feldern; Bilddaten (PNG, SVG) Base64. Eine Datei kann von irgendwoher
stammen: beim Laden wird jedes Feld nach Art, Wertebereich und Struktur geprüft (``StorageError``
mit deutscher Meldung statt Traceback; was angenommen wird, scheitert beim Rendern höchstens
verständlich). Bilddaten müssen PNG sein (Pillow erkennt Formate am Inhalt – EPS liefe sonst
durch Ghostscript) und werden ganz dekodiert. Unbekannte Felder werden übergangen, fehlende
bekommen den Standardwert. Die Schemata nennen jedes Feld der Dataclasses (ein Test hält sie
gleich).
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

from .document import (ALIGNMENTS, CUTS, FRAME_LINE_MM, FRAME_STYLES, MAX_DIGITS, MAX_FRAME_MM,
                       MAX_MARGIN_MM, MAX_NUMBER, MAX_POSITION_MM, MAX_SERIES_ROWS, ORIENTATIONS,
                       ROTATIONS, Document, Frame, ImageObject, Numbering, Paragraph, Series, Span,
                       TextObject)
from .imaging import MAX_PIXELS, MODES
from .labels import get_label

FORMAT = "labelwerk"
VERSION = 1
SUFFIX = ".labelwerk"
RECENT_FILES = 10
MAX_FILE_BYTES = 32 * 1024 * 1024     # größere Dateien werden nicht gelesen
MAX_OBJECTS = 500                     # Objekte je Etikett
MAX_FRAME_DOTS = 100_000_000          # Summe der Rahmenflächen in Druckpunkten (300 dpi)
DOTS_PER_MM = 300 / 25.4
MAX_SIZE_MM = 1_000.0                 # Rahmen, Etikettlänge (QL: höchstens 1 m)
MAX_SIZE_PT = 1_000.0                 # Schriftgröße (über MAX_PT hinaus, wie scale_text es lässt)
LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85  "   # gehören zwischen Absätze, nicht in Stücke
_TMP_PREFIX = ".labelwerk-"

# Feld → Art (siehe ``_KINDS``)
SPAN = {"text": "span_text", "family": "str?", "size_pt": "pt?", "bold": "bool", "italic": "bool",
        "underline": "bool"}
PARAGRAPH = {"align": "align"}                                    # dazu „spans“
TEXT = {"size_pt": "pt?", "font_path": "str?", "fit": "bool", "x_mm": "pos?", "y_mm": "pos?",
        "w_mm": "size?", "h_mm": "size?", "rotation": "rotation"}  # dazu „paragraphs“
IMAGE = {"png": "bytes", "source": "str", "page": "page?", "crop": "crop", "x_mm": "pos",
         "y_mm": "pos", "w_mm": "size", "h_mm": "size", "rotation": "rotation", "mode": "mode",
         "threshold": "threshold", "invert": "bool", "keep_ratio": "bool", "dpi": "dpi",
         "svg": "bytes?"}
FRAME = {"style": "frame_style", "rounded": "bool", "line_mm": "frame_line",
         "inset_mm": "frame_mm", "padding_mm": "frame_mm"}
NUMBERING = {"start": "number", "step": "step", "count": "count", "digits": "digits"}
SERIES = {"source": "path?", "sheet": "str?", "cut": "cut"}       # dazu „numbering“
DOCUMENT = {"label_id": "label", "length_mm": "size?", "orientation": "orientation",
            "margin_mm": "margin"}                                # dazu „objects“, „frame“, „series“


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _text(v) -> bool:
    """Text, der sich als UTF-8 schreiben lässt (keine einzelnen Surrogates)."""
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
    "path": lambda v: _text(v) and v != "" and "\x00" not in v,
    "crop": lambda v: v is None or (isinstance(v, list) and len(v) == 4 and all(map(_int, v))),
}


class StorageError(ValueError):
    """Datei lässt sich nicht als Etikett lesen (Meldung auf Deutsch, mit Dateiname)."""


def os_reason(error: OSError) -> str:
    """Grund eines Datei-Fehlers auf Deutsch (statt englischem Text des Betriebssystems)."""
    if isinstance(error, FileNotFoundError):
        return "Ordner fehlt"
    if isinstance(error, IsADirectoryError):
        return "ist ein Ordner"
    if isinstance(error, PermissionError):
        return "keine Berechtigung"
    if getattr(error, "errno", None) == 36:     # ENAMETOOLONG
        return "Name zu lang"
    if getattr(error, "errno", None) == 28:     # ENOSPC
        return "kein Platz auf dem Datenträger"
    return "Fehler beim Zugriff"


def exists(path: str | Path) -> bool:
    """Gibt es den Pfad? Auch ein unerreichbarer (EACCES, ENOTCONN, EIO …) wirft nicht."""
    try:
        return Path(path).exists()
    except OSError:
        return False


# --- Schreiben ---------------------------------------------------------------------------
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
    """``base``: Ordner der Datei – eine Tabelle darin oder darunter wird relativ gespeichert
    (kein Benutzername in weitergegebenen Etiketten, Ordner mitsamt Tabelle verschiebbar)."""
    objects = []
    for obj in doc.objects:
        if isinstance(obj, TextObject):
            objects.append({"type": "text", **_dump(obj, TEXT), "paragraphs": [
                {**_dump(p, PARAGRAPH), "spans": [_dump(s, SPAN) for s in p.spans]}
                for p in obj.paragraphs]})
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
    """Atomar speichern (temporäre Datei im selben Ordner, dann ersetzen): ein Abbruch
    hinterlässt die alte Datei. Ein Symlink wird verfolgt (das Ziel ändert sich), Rechte einer
    vorhandenen Datei bleiben, neue Dateien bekommen die Rechte nach umask. Fehler:
    ``OSError`` mit deutscher Meldung."""
    path = Path(path)
    target = Path(os.path.realpath(path))
    try:
        text = json.dumps(to_dict(doc, target.parent), ensure_ascii=False, indent=1,
                          allow_nan=False) + "\n"
        text.encode("utf-8")                # einzelne Surrogates lassen sich nicht schreiben
    except UnicodeEncodeError as e:
        raise OSError(f"{path.name} wurde nicht gespeichert: ungültige Zeichen im Text") from e
    except ValueError as e:
        raise OSError(f"{path.name} wurde nicht gespeichert: ungültige Zahlen im Etikett") from e
    tmp = None
    try:
        for attempt in range(100):          # freier Name für die temporäre Datei
            tmp = target.with_name(f"{_TMP_PREFIX}{os.getpid()}-{attempt}.tmp")
            try:
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)   # umask gilt
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
        raise OSError(f"{path.name} wurde nicht gespeichert ({os_reason(e)})") from e
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)
    return path


# --- Lesen -------------------------------------------------------------------------------
def _check(value, kind: str, key: str, where: str):
    """Wert prüfen und umwandeln (Base64 → bytes); ungültig → StorageError."""
    optional = kind.endswith("?")
    kind = kind.rstrip("?")
    if value is None and optional:
        return None
    if not _KINDS[kind](value):
        if kind == "label":
            raise StorageError(f"Etikett{where} unbekannt: {reprlib.repr(value)}")
        raise StorageError(f"Wert für „{key}“{where} ungültig: {reprlib.repr(value)}")
    if kind == "span_text" and any(c in value for c in LINE_BREAKS):
        raise StorageError(f"Zeilenumbruch in „{key}“{where} – Zeilen sind eigene Absätze")
    if kind == "bytes":
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as e:
            raise StorageError(f"Bilddaten „{key}“{where} nicht lesbar") from e
    return value


def _load(data, schema: dict, where: str, required: tuple[str, ...] = ()) -> dict:
    if not isinstance(data, dict):
        raise StorageError(f"Eintrag{where} ist kein Objekt")
    for key in required:
        if key not in data:
            raise StorageError(f"„{key}“{where} fehlt")
    return {key: _check(data[key], kind, key, where) for key, kind in schema.items() if key in data}


def _list(data: dict, key: str, where: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise StorageError(f"Wert für „{key}“{where} ungültig: {reprlib.repr(value)}")
    return value


def _image(data: dict, where: str) -> ImageObject:
    values = _load(data, IMAGE, where, required=("png", "w_mm", "h_mm"))
    try:
        with Image.open(io.BytesIO(values["png"]), formats=["PNG"]) as img:
            size = img.size
            if max(size) > MAX_PIXELS:
                raise StorageError(f"Bild{where} zu groß ({size[0]} × {size[1]} Pixel, "
                                   f"höchstens {MAX_PIXELS})")
            img.load()                      # ganz dekodieren: kaputte Daten fallen jetzt auf
    except StorageError:
        raise
    except Exception as e:  # Pillow wirft je nach Schaden verschiedene Fehler
        raise StorageError(f"Bilddaten{where} nicht lesbar (nur PNG)") from e
    crop = values.get("crop")
    if crop is not None and not (0 <= crop[0] < crop[2] <= size[0]
                                 and 0 <= crop[1] < crop[3] <= size[1]):
        raise StorageError(f"Wert für „crop“{where} liegt nicht im Bild: {crop}")
    return ImageObject(**values)


def _series(data) -> Series:
    values = _load(data, SERIES, " in der Serie")
    numbering = data.get("numbering")
    if numbering is not None:
        values["numbering"] = Numbering(**_load(numbering, NUMBERING, " in der Nummerierung"))
    if (values.get("source") is None) == (numbering is None):
        raise StorageError("Serie braucht genau eins: Tabelle oder Nummerierung")
    return Series(**values)


def _is_file(path: str) -> bool:
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except (OSError, ValueError):       # ValueError: Pfad mit NUL-Zeichen
        return False


def _text_object(item: dict, where: str) -> TextObject:
    values = _load(item, TEXT, where)
    if values.get("font_path") is not None and not _is_file(values["font_path"]):
        values["font_path"] = None      # nur eine vorhandene, reguläre Datei geht an FreeType
    paragraphs = []
    for p in _list(item, "paragraphs", where):
        align = _load(p, PARAGRAPH, where)
        spans = [Span(**_load(s, SPAN, where, required=("text",)))
                 for s in _list(p, "spans", where)]
        paragraphs.append(Paragraph(spans, **align))
    return TextObject(paragraphs or [Paragraph([Span("")])], **values)   # leer = eine Zeile


def _relative(source: str, base: str | Path) -> str:
    """Pfad relativ zu ``base`` (mit „/“), wenn er darin liegt – sonst wie er ist."""
    try:
        return Path(source).relative_to(Path(os.path.realpath(base))).as_posix()
    except ValueError:
        return source


def from_dict(data, base: str | Path | None = None) -> Document:
    """``base``: Ordner der Datei – relative Tabellenpfade gelten von dort aus."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise StorageError("keine labelwerk-Datei")
    version = data.get("version")
    if not _int(version) or version < 1:
        raise StorageError(f"keine labelwerk-Datei (Format-Version {reprlib.repr(version)})")
    if version > VERSION:
        raise StorageError(f"mit einem neueren labelwerk gespeichert (Format-Version {version}) "
                           f"– bitte labelwerk aktualisieren")
    document = data.get("document")
    values = _load(document, DOCUMENT, "")
    frame = document.get("frame")
    if frame is not None:                   # fehlt oder null: kein Rahmen
        values["frame"] = Frame(**_load(frame, FRAME, " im Rahmen"))
    if document.get("series") is not None:  # fehlt oder null: keine Serie
        values["series"] = _series(document["series"])
        source = values["series"].source
        if base is not None and source is not None and not Path(source).is_absolute():
            values["series"] = replace(values["series"],
                                       source=str(Path(os.path.realpath(base)) / source))
    items = _list(document, "objects", "")
    if len(items) > MAX_OBJECTS:
        raise StorageError(f"Etikett zu groß ({len(items)} Objekte, höchstens {MAX_OBJECTS})")
    objects = []
    for number, item in enumerate(items, start=1):
        where = f" in Objekt {number}"
        kind = item.get("type") if isinstance(item, dict) else None
        if kind == "text":
            objects.append(_text_object(item, where))
        elif kind == "image":
            objects.append(_image(item, where))
        else:
            raise StorageError(f"Objektart{where} unbekannt: {reprlib.repr(kind)}")
    dots = sum(o.w_mm * o.h_mm for o in objects if o.w_mm and o.h_mm) * DOTS_PER_MM ** 2
    if dots > MAX_FRAME_DOTS:
        raise StorageError(f"Etikett zu groß (Objekte zusammen {dots / 1e6:.0f} Mio. Druckpunkte, "
                           f"höchstens {MAX_FRAME_DOTS // 1_000_000})")
    return Document(**values, objects=objects)


def _reject_constant(name: str):
    raise ValueError(f"{name} ist keine Zahl")


def load(path: str | Path) -> Document:
    """Etikett aus einer Datei; jeder Fehler als ``StorageError`` mit Dateiname."""
    path = Path(path)
    try:
        info = path.stat()
        if stat.S_ISDIR(info.st_mode):
            raise IsADirectoryError(path)
        if not stat.S_ISREG(info.st_mode):      # ein FIFO o. Ä. würde beim Lesen hängen
            raise StorageError(f"{path.name}: keine Datei")
        if info.st_size > MAX_FILE_BYTES:
            raise StorageError(f"{path.name}: Datei zu groß")
        text = path.read_text(encoding="utf-8-sig")       # auch mit BOM (Windows-Editoren)
    except FileNotFoundError as e:
        raise StorageError(f"Datei nicht gefunden: {path}") from e
    except OSError as e:
        raise StorageError(f"{path.name} kann nicht gelesen werden ({os_reason(e)})") from e
    except UnicodeDecodeError as e:
        raise StorageError(f"{path.name}: keine labelwerk-Datei (kein UTF-8-Text)") from e
    try:
        data = json.loads(text, parse_constant=_reject_constant)   # NaN, Infinity
    except RecursionError as e:
        raise StorageError(f"{path.name}: Datei beschädigt (zu tief verschachtelt)") from e
    except ValueError as e:
        raise StorageError(f"{path.name}: keine labelwerk-Datei oder beschädigt") from e
    try:
        return from_dict(data, path.parent)
    except StorageError as e:
        raise StorageError(f"{path.name}: {e}") from e
    except (TypeError, AttributeError, KeyError, RecursionError, OverflowError) as e:
        raise StorageError(f"{path.name}: Datei beschädigt") from e   # Sicherheitsnetz


def add_recent_file(recent: list[str], path: str, limit: int = RECENT_FILES) -> list[str]:
    """„Zuletzt geöffnet“: ``path`` nach vorn, ohne Doppelte, höchstens ``limit``."""
    return [path, *(p for p in recent if p != path)][:limit]
