"""Barcodes without Qt: linear codes (Code 128, Code 39, EAN-13, EAN-8) encoded here (tables from
the standards), QR codes via ``segno``.

Drawing uses whole dots: one module (narrowest bar or QR square) is ``module`` dots wide – no
scaling, no anti-aliasing in the bars, so the code stays readable at 300 dpi. Errors (content,
settings) → ``BarcodeError`` with a translated message.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import segno
from PIL import Image, ImageDraw

from . import fonts
from .document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, MAX_MODULE, MODULE_LIMIT, QR_LEVELS,
                       ROTATIONS, BarcodeObject)
from . import i18n
from .i18n import N_, _
from .labels import DPI

TITLES = {"qr": N_("QR code"), "code128": "Code 128", "code39": "Code 39", "ean13": "EAN-13",
          "ean8": "EAN-8"}
SAMPLES = {"qr": "labelwerk", "code128": "ABC-123", "code39": "ABC-123", "ean13": "590123412345",
           "ean8": "9638507"}                 # sample content when inserting
INSERT_MODULE = {"qr": 6}    # module width when inserting at 300 dpi (otherwise 3 dots = 0.25 mm)
MAX_LINEAR = 80              # characters per linear code
# quiet zone in modules outside the frame (otherwise 10) – EAN-13 left 11, 7 of them for the first digit
QUIET = {"qr": 4, "ean13": 11, "ean8": 7}
MIN_BARS_MM = 1.0            # shortest bar height
TEXT_MODULES = 9             # human-readable text: font size in modules …
MIN_TEXT_DOTS = 25           # … at least 6 pt …
TEXT_SHARE = 0.4             # … at most 40 % of the height …
MIN_FIT_DOTS = 8             # … when fitting (width, height) shrunk at most this far
WIDE = 3                     # Code 39: wide = 3 × narrow


class BarcodeError(ValueError):
    """Content or setting cannot be shown as a barcode."""


@dataclass(frozen=True)
class Code:
    """Encoded content.

    ``rows``: QR – rows of the matrix, linear code – one row; per module "1" (dark) or "0".
    ``text``: human-readable groups (text, first module, end) relative to the start of the code;
    ``guards``: modules of the extended guard bars (EAN); ``lead``: modules left of the code for the
    first EAN-13 digit; ``glyphs``: all characters that can appear in the human-readable text of the
    kind (their height and descender determine the space – the same for any content, also in a series);
    ``readable``: the whole content as encoded (EAN with check digit).
    """
    rows: tuple[str, ...]
    matrix: bool = False
    text: tuple[tuple[str, int, int], ...] = ()
    guards: frozenset[int] = frozenset()
    lead: int = 0
    glyphs: str = "0123456789"
    readable: str = ""


# --- Encoding --------------------------------------------------------------------------------
def encode(kind: str, data: str, error: str = "M") -> Code:
    """Encode the content (``error``: QR error correction, irrelevant otherwise)."""
    if not isinstance(kind, str) or kind not in BARCODE_KINDS:
        raise BarcodeError(_("Unknown barcode type {kind!r}").format(kind=kind))
    if not isinstance(data, str):
        raise BarcodeError(_("Content must be text, not {type}").format(type=type(data).__name__))
    if not isinstance(error, str):
        raise BarcodeError(_("Unknown error correction {error!r} – allowed: L, M, Q, H").format(error=error))
    return _encode(kind, data, error)


@lru_cache(maxsize=256)
def _encode(kind: str, data: str, error: str) -> Code:
    if not data:
        raise BarcodeError(_("Barcode without content"))
    if len(data) > MAX_BARCODE_DATA:
        raise BarcodeError(_("Content too long ({count} characters, at most {limit})").format(
            count=len(data), limit=MAX_BARCODE_DATA))
    if kind == "qr":
        return _qr(data, error)
    if len(data) > MAX_LINEAR:
        raise BarcodeError(_("{title}: content too long ({count} characters, at most {limit})").format(
            title=_(TITLES[kind]), count=len(data), limit=MAX_LINEAR))
    return {"code128": _code128, "code39": _code39, "ean13": _ean13, "ean8": _ean8}[kind](data)


def _qr(data: str, error: str) -> Code:
    if error not in QR_LEVELS:
        raise BarcodeError(_("Unknown error correction {error!r} – allowed: L, M, Q, H").format(error=error))
    try:
        qr = segno.make_qr(data, error=error, boost_error=False)
    except segno.DataOverflowError as e:
        raise BarcodeError(_("Content too long for a QR code (error correction {error})").format(
            error=error)) from e
    rows = tuple("".join("1" if v else "0" for v in row) for row in qr.matrix)
    return Code(rows, matrix=True, readable=data)


def _bars(pattern: str) -> str:
    """Alternating bar/space widths ("212222") → modules ("11011001100")."""
    return "".join(("1" if i % 2 == 0 else "0") * int(w) for i, w in enumerate(pattern))


# Code 128 (ISO/IEC 15417): values 0–105 as bar/space widths/…, 11 modules each; stop 13
_C128 = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212",
    "221213", "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221",
    "223211", "221132", "221231", "213212", "223112", "312131", "311222", "321122", "321221",
    "312212", "322112", "322211", "212123", "212321", "232121", "111323", "131123", "131321",
    "112313", "132113", "132311", "211313", "231113", "231311", "112133", "112331", "132131",
    "113123", "113321", "133121", "313121", "211331", "231131", "213113", "213311", "213131",
    "311123", "311321", "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111", "111242",
    "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311",
    "113141", "114131", "311141", "411131", "211412", "211214", "211232")
_C128_STOP = "2331112"
_CODE_C, _CODE_B, _START_B, _START_C = 99, 100, 104, 105
_DIGITS = frozenset("0123456789")
_ASCII = "".join(chr(c) for c in range(32, 127))


def _code128(data: str) -> Code:
    for c in data:
        if not 32 <= ord(c) <= 126:
            raise BarcodeError(_("Code 128 cannot encode “{char}” (ASCII only, no umlauts)").format(
                char=c))
    values = _code128_values(data)
    check = (values[0] + sum(i * v for i, v in enumerate(values[1:], start=1))) % 103
    bars = "".join(_bars(_C128[v]) for v in [*values, check]) + _bars(_C128_STOP)
    return Code((bars,), text=((data, 0, len(bars)),), glyphs=_ASCII, readable=data)


def _code128_values(data: str) -> list[int]:
    """Values including the start character with the fewest characters: code set B (one character per
    value) and C (two digits per value), switching costs one value – shortest path over all positions."""
    n = len(data)
    inf = n * 4 + 8
    cost = [[inf, inf] for __ in range(n + 1)]   # [B, C]: values until position i is encoded
    prev: list[list[tuple[int, int] | None]] = [[None, None] for __ in range(n + 1)]
    cost[0] = [1, 1]                            # start character B or C
    for i in range(n + 1):
        for s in (0, 1):                        # switch at this point
            if cost[i][1 - s] + 1 < cost[i][s]:
                cost[i][s], prev[i][s] = cost[i][1 - s] + 1, (i, 1 - s)
        if i == n:
            break
        if cost[i][0] + 1 < cost[i + 1][0]:
            cost[i + 1][0], prev[i + 1][0] = cost[i][0] + 1, (i, 0)
        if i + 2 <= n and data[i] in _DIGITS and data[i + 1] in _DIGITS \
                and cost[i][1] + 1 < cost[i + 2][1]:
            cost[i + 2][1], prev[i + 2][1] = cost[i][1] + 1, (i, 1)
    i, s = n, 0 if cost[n][0] <= cost[n][1] else 1
    values = []
    while prev[i][s] is not None:
        pi, ps = prev[i][s]
        if pi == i:
            values.append(_CODE_C if s == 1 else _CODE_B)
        elif s == 0:
            values.append(ord(data[pi]) - 32)
        else:
            values.append(int(data[pi:pi + 2]))
        i, s = pi, ps
    values.append(_START_C if s == 1 else _START_B)
    return values[::-1]


# Code 39 (ISO/IEC 16388): 9 elements bar/space/…, "1" = wide (three of nine)
_C39 = {
    "0": "000110100", "1": "100100001", "2": "001100001", "3": "101100000", "4": "000110001",
    "5": "100110000", "6": "001110000", "7": "000100101", "8": "100100100", "9": "001100100",
    "A": "100001001", "B": "001001001", "C": "101001000", "D": "000011001", "E": "100011000",
    "F": "001011000", "G": "000001101", "H": "100001100", "I": "001001100", "J": "000011100",
    "K": "100000011", "L": "001000011", "M": "101000010", "N": "000010011", "O": "100010010",
    "P": "001010010", "Q": "000000111", "R": "100000110", "S": "001000110", "T": "000010110",
    "U": "110000001", "V": "011000001", "W": "111000000", "X": "010010001", "Y": "110010000",
    "Z": "011010000", "-": "010000101", ".": "110000100", " ": "011000100", "$": "010101000",
    "/": "010100010", "+": "010001010", "%": "000101010", "*": "010010100"}


def _code39(data: str) -> Code:
    text = ""
    for c in data:
        upper = c.upper() if "a" <= c <= "z" else c    # lowercase letters are printed as capitals
        if upper not in _C39 or upper == "*":
            raise BarcodeError(_("Code 39 cannot encode “{char}” (allowed: 0–9, A–Z, space and "
                                 "- . $ / + %)").format(char=c))
        text += upper
    parts = ["".join(("1" if k % 2 == 0 else "0") * (WIDE if w == "1" else 1)
                     for k, w in enumerate(_C39[c])) for c in f"*{text}*"]
    bars = "0".join(parts)                      # narrow space between the characters
    return Code((bars,), text=((text, 0, len(bars)),), glyphs="".join(_C39), readable=text)


# EAN (ISO/IEC 15420): character sets L/G (left) and R (right); parity of the left half
# of EAN-13 from the first digit
_L = ("0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011",
      "0110111", "0001011")
_R = tuple("".join("1" if b == "0" else "0" for b in code) for code in _L)
_G = tuple(code[::-1] for code in _R)
_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG",
           "LGLGGL", "LGGLGL")


def check_digit(digits: str) -> int:
    """EAN check digit for the digits before it (from the right alternately × 3, × 1)."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def _ean_digits(kind: str, data: str) -> str:
    title, length = _(TITLES[kind]), 13 if kind == "ean13" else 8
    digits = "".join(data.split())              # spaces do not count
    for c in digits:
        if c not in _DIGITS:
            raise BarcodeError(_("{title} can only encode digits, not “{char}”").format(title=title,
                                                                                    char=c))
    if len(digits) == length - 1:
        return digits + str(check_digit(digits))
    if len(digits) != length:
        raise BarcodeError(_("{title} needs {short} or {length} digits ({count} entered)").format(
            title=title, short=length - 1, length=length, count=len(digits)))
    right = check_digit(digits[:-1])
    if int(digits[-1]) != right:
        raise BarcodeError(_("{title}: wrong check digit – it should be {right}").format(
            title=title, right=right))
    return digits


def _ean13(data: str) -> Code:
    d = _ean_digits("ean13", data)
    left = "".join((_L if p == "L" else _G)[int(c)] for p, c in zip(_PARITY[int(d[0])], d[1:7]))
    bars = "101" + left + "01010" + "".join(_R[int(c)] for c in d[7:]) + "101"
    guards = frozenset((*range(0, 3), *range(45, 50), *range(92, 95)))
    return Code((bars,), text=((d[0], -7, 0), (d[1:7], 3, 45), (d[7:], 50, 92)), guards=guards,
                lead=7, readable=d)


def _ean8(data: str) -> Code:
    d = _ean_digits("ean8", data)
    bars = ("101" + "".join(_L[int(c)] for c in d[:4]) + "01010"
            + "".join(_R[int(c)] for c in d[4:]) + "101")
    guards = frozenset((*range(0, 3), *range(31, 36), *range(64, 67)))
    return Code((bars,), text=((d[:4], 3, 31), (d[4:], 36, 64)), guards=guards, readable=d)


# --- Dimensions and drawing -----------------------------------------------------------------
def _dots(mm: float, dpi: int = DPI) -> int:
    return round(mm * dpi / 25.4)


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check(obj: BarcodeObject) -> Code:
    """Check the settings and encode the content."""
    if obj.rotation not in ROTATIONS:
        raise BarcodeError(_("Unknown rotation {rotation!r} – allowed: 0, 90, 180, 270 degrees").format(
            rotation=obj.rotation))
    if not isinstance(obj.module, int) or isinstance(obj.module, bool) \
            or not 1 <= obj.module <= MODULE_LIMIT:
        raise BarcodeError(_("Module width {module!r} invalid – allowed: 1–{limit} dots").format(
            module=obj.module, limit=MODULE_LIMIT))
    if not isinstance(obj.text, bool):
        raise BarcodeError(_("Human-readable text must be on or off, not {text!r}").format(
            text=obj.text))
    if obj.error not in QR_LEVELS:
        raise BarcodeError(_("Unknown error correction {error!r} – allowed: L, M, Q, H").format(
            error=obj.error))
    if obj.kind != "qr" and not (_number(obj.h_mm) and BARCODE_MM[0] <= obj.h_mm <= BARCODE_MM[1]):
        raise BarcodeError(_("Height {height!r} mm invalid – allowed: {low}–{high} mm").format(
            height=obj.h_mm, low=i18n.number(BARCODE_MM[0]), high=i18n.number(BARCODE_MM[1])))
    return encode(obj.kind, obj.data, obj.error if obj.kind == "qr" else "M")


def modules(obj: BarcodeObject) -> int:
    """Modules in the width (unrotated) – EAN-13 with text including space for the first digit."""
    code = check(obj)
    return len(code.rows) if code.matrix else len(code.rows[0]) + (code.lead if obj.text else 0)


def quiet_mm(obj: BarcodeObject, dpi: int = DPI) -> float:
    """Quiet zone left and right (mm) outside the frame that should stay free."""
    modules = 7 if obj.kind == "ean13" and obj.text else QUIET.get(obj.kind, 10)
    return modules * obj.module * 25.4 / dpi


# at most this many modules wide (QR: version 40; Code 128 entirely in B; Code 39 with spaces)
MAX_MODULES = {"qr": 177, "code128": 11 * (MAX_LINEAR + 2) + 13, "code39": 16 * (MAX_LINEAR + 2),
               "ean13": 102, "ean8": 67}


def max_size(obj: BarcodeObject, dpi: int = DPI) -> tuple[int, int]:
    """Upper bound of the size (dots, unrotated) without encoding – for the limits of foreign
    files, even when only the series fills in the content."""
    side = MAX_MODULES.get(obj.kind, 0) * obj.module
    return (side, side) if obj.kind == "qr" else (side, _dots(obj.h_mm, dpi))


@dataclass(frozen=True)
class _Layout:
    width: int
    height: int
    bars: int                   # height of the bars
    guards: int                 # height of the extended guard bars
    font: object = None         # human-readable text (None = none)
    baseline: int = 0


def size(obj: BarcodeObject, dpi: int = DPI) -> tuple[int, int]:
    """Size (width, height) in dots at ``dpi``, unrotated."""
    layout = _layout(obj, check(obj), dpi)
    return layout.width, layout.height


def _layout(obj: BarcodeObject, code: Code, dpi: int = DPI) -> _Layout:
    m = obj.module
    if code.matrix:
        side = len(code.rows) * m
        return _Layout(side, side, side, side)
    width = (len(code.rows[0]) + (code.lead if obj.text else 0)) * m
    height = _dots(obj.h_mm, dpi)
    if not obj.text:
        return _Layout(width, height, height, height)
    font, top, bottom, gap = _text_font(code, m, height, dpi)
    bars = height - gap - top - bottom
    if bars < _dots(MIN_BARS_MM, dpi):
        raise BarcodeError(_("Barcode too short for the human-readable text – make it taller or "
                             "turn the text off"))
    return _Layout(width, height, bars, bars + (gap + top) // 2, font, bars + gap + top)


@lru_cache(maxsize=1)
def _font_path() -> str:
    return fonts.resolve(None, False, False).path


def scaled(dots: int, dpi: int) -> int:
    """Dots at 300 dpi in the resolution ``dpi`` (same size in mm, at least 1)."""
    return dots if dpi == DPI else max(1, round(dots * dpi / DPI))


def insert_module(kind: str, dpi: int = DPI) -> int:
    """Module width when inserting, in dots at ``dpi`` (same mm as at 300 dpi)."""
    return scaled(INSERT_MODULE.get(kind, 3), dpi)


def max_module(dpi: int = DPI) -> int:
    """Largest module width that fitting and input allow at ``dpi`` (1.7 mm)."""
    return min(scaled(MAX_MODULE, dpi), MODULE_LIMIT)


def _text_font(code: Code, m: int, height: int, dpi: int = DPI):
    """Human-readable font and its space (font, above and below the baseline, distance to the
    bars): about ``TEXT_MODULES`` modules large (at least 6 pt), shrunk until each group fits its
    width and the text needs at most ``TEXT_SHARE`` of the height."""
    dots = max(TEXT_MODULES * m, scaled(MIN_TEXT_DOTS, dpi))
    path = _font_path()
    while True:
        font = fonts.load(path, dots)
        __, top, __, bottom = font.getbbox(code.glyphs, anchor="ls")
        top, bottom, gap = -top, max(0, bottom), max(2, dots // 8)
        over = max(font.getlength(text) / ((end - start) * m) for text, start, end in code.text)
        over = max(over, (gap + top + bottom) / (TEXT_SHARE * height))
        if over <= 1 or dots <= scaled(MIN_FIT_DOTS, dpi):
            return font, top, bottom, gap
        dots = max(MIN_FIT_DOTS, min(dots - 1, math.floor(dots / over)))


def draw(obj: BarcodeObject, dpi: int = DPI) -> Image.Image:
    """Barcode as a greyscale image (L, white background, black ink) in ``size(obj)``, unrotated."""
    code = check(obj)
    layout = _layout(obj, code, dpi)
    img = Image.new("L", (layout.width, layout.height), 255)
    pen = ImageDraw.Draw(img)
    m = obj.module
    if code.matrix:
        for y, row in enumerate(code.rows):
            for start, end in _runs(row):
                pen.rectangle((start * m, y * m, end * m - 1, (y + 1) * m - 1), fill=0)
        return img
    x0 = (code.lead if obj.text else 0) * m
    for start, end in _runs(code.rows[0]):
        bottom = layout.guards if start in code.guards else layout.bars
        pen.rectangle((x0 + start * m, 0, x0 + end * m - 1, bottom - 1), fill=0)
    if layout.font is not None:
        for text, start, end in code.text:
            pen.text((x0 + (start + end) * m / 2, layout.baseline), text, fill=0,
                     font=layout.font, anchor="ms")
    return img


def placeholder_size(obj: BarcodeObject, dpi: int = DPI) -> tuple[int, int]:
    """Size (dots, unrotated) for a barcode that cannot be encoded – about as large as it would
    be with this content (canvas: stays visible and selectable)."""
    m = (obj.module if isinstance(obj.module, int) and 1 <= obj.module <= MODULE_LIMIT
         else scaled(3, dpi))
    n = len(obj.data) if isinstance(obj.data, str) else 1
    if obj.kind == "qr":
        side = (21 + 4 * min(39, n // 20)) * m
        return side, side
    n = min(n, MAX_LINEAR)
    count = {"ean13": 102 if obj.text is True else 95, "ean8": 67,
             "code39": 16 * (n + 2)}.get(obj.kind, 11 * (n + 3) + 13)
    h = obj.h_mm if _number(obj.h_mm) and BARCODE_MM[0] <= obj.h_mm <= BARCODE_MM[1] else 10.0
    return count * m, _dots(h, dpi)


def placeholder(width: int, height: int) -> Image.Image:
    """Hatched box (L) instead of a barcode that cannot be encoded."""
    img = Image.new("L", (width, height), 255)
    pen = ImageDraw.Draw(img)
    for x in range(-height, width, 12):
        pen.line((x, height, x + height, 0), fill=170, width=2)
    pen.rectangle((0, 0, width - 1, height - 1), outline=110, width=2)
    return img


def _runs(row: str) -> list[tuple[int, int]]:
    """Runs of dark modules (start, end) of a row."""
    runs, start = [], None
    for i, v in enumerate(row + "0"):
        if v == "1" and start is None:
            start = i
        elif v == "0" and start is not None:
            runs.append((start, i))
            start = None
    return runs
