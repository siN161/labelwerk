"""Barcodes ohne Qt: Strichcodes (Code 128, Code 39, EAN-13, EAN-8) selbst kodiert (Tabellen aus
den Normen), QR-Codes über ``segno``.

Gezeichnet wird in ganzen Druckpunkten: Ein Modul (schmalster Strich bzw. QR-Quadrat) ist
``module`` Punkte breit – kein Skalieren, keine Kantenglättung in den Strichen, so bleibt der Code
bei 300 dpi lesbar. Fehler (Inhalt, Einstellungen) → ``BarcodeError`` mit deutscher Meldung.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import segno
from PIL import Image, ImageDraw

from . import fonts
from .document import (BARCODE_KINDS, BARCODE_MM, MAX_BARCODE_DATA, MAX_MODULE, QR_LEVELS,
                       ROTATIONS, BarcodeObject)
from .labels import DPI

TITLES = {"qr": "QR-Code", "code128": "Code 128", "code39": "Code 39", "ean13": "EAN-13",
          "ean8": "EAN-8"}
SAMPLES = {"qr": "labelwerk", "code128": "ABC-123", "code39": "ABC-123", "ean13": "590123412345",
           "ean8": "9638507"}                 # Beispielinhalt beim Einfügen
INSERT_MODULE = {"qr": 6}    # Modulbreite beim Einfügen (sonst 3 Druckpunkte = 0,25 mm)
MAX_LINEAR = 80              # Zeichen je Strichcode
# Ruhezone in Modulen außerhalb des Rahmens (sonst 10) – EAN-13 links 11, davon 7 für die erste Ziffer
QUIET = {"qr": 4, "ean13": 11, "ean8": 7}
MIN_BARS_MM = 1.0            # kürzeste Strichhöhe
TEXT_MODULES = 9             # Klartext: Schriftgröße in Modulen …
MIN_TEXT_DOTS = 25           # … mindestens 6 pt …
TEXT_SHARE = 0.4             # … höchstens 40 % der Höhe …
MIN_FIT_DOTS = 8             # … beim Einpassen (Breite, Höhe) höchstens bis hierher verkleinert
WIDE = 3                     # Code 39: breit = 3 × schmal


class BarcodeError(ValueError):
    """Inhalt oder Einstellung lässt sich nicht als Barcode darstellen."""


@dataclass(frozen=True)
class Code:
    """Kodierter Inhalt.

    ``rows``: QR – Zeilen der Matrix, Strichcode – eine Zeile; je Modul „1“ (dunkel) oder „0“.
    ``text``: Klartext-Gruppen (Text, erstes Modul, Ende) relativ zum Codeanfang; ``guards``:
    Module der verlängerten Randzeichen (EAN); ``lead``: Module links vor dem Code für die erste
    EAN-13-Ziffer; ``glyphs``: alle Zeichen, die im Klartext der Art vorkommen können (ihre Höhe
    und Unterlänge bestimmen den Platz – gleich für jeden Inhalt, auch in einer Serie);
    ``readable``: der ganze Inhalt, wie er kodiert ist (EAN mit Prüfziffer).
    """
    rows: tuple[str, ...]
    matrix: bool = False
    text: tuple[tuple[str, int, int], ...] = ()
    guards: frozenset[int] = frozenset()
    lead: int = 0
    glyphs: str = "0123456789"
    readable: str = ""


# --- Kodieren --------------------------------------------------------------------------------
def encode(kind: str, data: str, error: str = "M") -> Code:
    """Inhalt kodieren (``error``: QR-Fehlerkorrektur, sonst ohne Bedeutung)."""
    if not isinstance(kind, str) or kind not in BARCODE_KINDS:
        raise BarcodeError(f"Unbekannte Barcode-Art {kind!r}")
    if not isinstance(data, str):
        raise BarcodeError(f"Inhalt muss Text sein, nicht {type(data).__name__}")
    if not isinstance(error, str):
        raise BarcodeError(f"Unbekannte Fehlerkorrektur {error!r} – erlaubt: L, M, Q, H")
    return _encode(kind, data, error)


@lru_cache(maxsize=256)
def _encode(kind: str, data: str, error: str) -> Code:
    if not data:
        raise BarcodeError("Barcode ohne Inhalt")
    if len(data) > MAX_BARCODE_DATA:
        raise BarcodeError(f"Inhalt zu lang ({len(data)} Zeichen, höchstens {MAX_BARCODE_DATA})")
    if kind == "qr":
        return _qr(data, error)
    if len(data) > MAX_LINEAR:
        raise BarcodeError(f"{TITLES[kind]}: Inhalt zu lang ({len(data)} Zeichen, höchstens "
                           f"{MAX_LINEAR})")
    return {"code128": _code128, "code39": _code39, "ean13": _ean13, "ean8": _ean8}[kind](data)


def _qr(data: str, error: str) -> Code:
    if error not in QR_LEVELS:
        raise BarcodeError(f"Unbekannte Fehlerkorrektur {error!r} – erlaubt: L, M, Q, H")
    try:
        qr = segno.make_qr(data, error=error, boost_error=False)
    except segno.DataOverflowError as e:
        raise BarcodeError(f"Inhalt zu lang für einen QR-Code (Fehlerkorrektur {error})") from e
    rows = tuple("".join("1" if v else "0" for v in row) for row in qr.matrix)
    return Code(rows, matrix=True, readable=data)


def _bars(pattern: str) -> str:
    """Breiten abwechselnd Strich/Lücke („212222“) → Module („11011001100“)."""
    return "".join(("1" if i % 2 == 0 else "0") * int(w) for i, w in enumerate(pattern))


# Code 128 (ISO/IEC 15417): Werte 0–105 als Breiten Strich/Lücke/…, je 11 Module; Stopp 13
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
            raise BarcodeError(f"Code 128 kann „{c}“ nicht darstellen (nur ASCII ohne Umlaute)")
    values = _code128_values(data)
    check = (values[0] + sum(i * v for i, v in enumerate(values[1:], start=1))) % 103
    bars = "".join(_bars(_C128[v]) for v in [*values, check]) + _bars(_C128_STOP)
    return Code((bars,), text=((data, 0, len(bars)),), glyphs=_ASCII, readable=data)


def _code128_values(data: str) -> list[int]:
    """Werte samt Startzeichen mit den wenigsten Zeichen: Zeichensatz B (ein Zeichen je Wert) und
    C (zwei Ziffern je Wert), Wechsel kostet einen Wert – kürzester Weg über alle Positionen."""
    n = len(data)
    inf = n * 4 + 8
    cost = [[inf, inf] for _ in range(n + 1)]   # [B, C]: Werte, bis Position i kodiert ist
    prev: list[list[tuple[int, int] | None]] = [[None, None] for _ in range(n + 1)]
    cost[0] = [1, 1]                            # Startzeichen B bzw. C
    for i in range(n + 1):
        for s in (0, 1):                        # Wechsel an dieser Stelle
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


# Code 39 (ISO/IEC 16388): 9 Elemente Strich/Lücke/…, „1“ = breit (drei von neun)
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
        upper = c.upper() if "a" <= c <= "z" else c    # Kleinbuchstaben werden groß gedruckt
        if upper not in _C39 or upper == "*":
            raise BarcodeError(f"Code 39 kann „{c}“ nicht darstellen (erlaubt: 0–9, A–Z, "
                               f"Leerzeichen und - . $ / + %)")
        text += upper
    parts = ["".join(("1" if k % 2 == 0 else "0") * (WIDE if w == "1" else 1)
                     for k, w in enumerate(_C39[c])) for c in f"*{text}*"]
    bars = "0".join(parts)                      # schmale Lücke zwischen den Zeichen
    return Code((bars,), text=((text, 0, len(bars)),), glyphs="".join(_C39), readable=text)


# EAN (ISO/IEC 15420): Zeichensätze L/G (links) und R (rechts); Parität der linken Hälfte
# von EAN-13 aus der ersten Ziffer
_L = ("0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011",
      "0110111", "0001011")
_R = tuple("".join("1" if b == "0" else "0" for b in code) for code in _L)
_G = tuple(code[::-1] for code in _R)
_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG",
           "LGLGGL", "LGGLGL")


def check_digit(digits: str) -> int:
    """EAN-Prüfziffer zu den Ziffern davor (von rechts abwechselnd × 3, × 1)."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def _ean_digits(kind: str, data: str) -> str:
    title, length = TITLES[kind], 13 if kind == "ean13" else 8
    digits = "".join(data.split())              # Leerzeichen zählen nicht
    for c in digits:
        if c not in _DIGITS:
            raise BarcodeError(f"{title} kann nur Ziffern darstellen, nicht „{c}“")
    if len(digits) == length - 1:
        return digits + str(check_digit(digits))
    if len(digits) != length:
        raise BarcodeError(f"{title} braucht {length - 1} oder {length} Ziffern "
                           f"({len(digits)} eingegeben)")
    right = check_digit(digits[:-1])
    if int(digits[-1]) != right:
        raise BarcodeError(f"{title}: Prüfziffer falsch – richtig wäre {right}")
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


# --- Maße und Zeichnen -----------------------------------------------------------------------
def _dots(mm: float) -> int:
    return round(mm * DPI / 25.4)


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check(obj: BarcodeObject) -> Code:
    """Einstellungen prüfen und den Inhalt kodieren."""
    if obj.rotation not in ROTATIONS:
        raise BarcodeError(f"Unbekannte Drehung {obj.rotation!r} – erlaubt: 0, 90, 180, 270 Grad")
    if not isinstance(obj.module, int) or isinstance(obj.module, bool) \
            or not 1 <= obj.module <= MAX_MODULE:
        raise BarcodeError(f"Modulbreite {obj.module!r} ungültig – erlaubt: 1–{MAX_MODULE} "
                           f"Druckpunkte")
    if not isinstance(obj.text, bool):
        raise BarcodeError(f"Klartext muss an oder aus sein, nicht {obj.text!r}")
    if obj.error not in QR_LEVELS:
        raise BarcodeError(f"Unbekannte Fehlerkorrektur {obj.error!r} – erlaubt: L, M, Q, H")
    if obj.kind != "qr" and not (_number(obj.h_mm) and BARCODE_MM[0] <= obj.h_mm <= BARCODE_MM[1]):
        raise BarcodeError(f"Höhe {obj.h_mm!r} mm ungültig – erlaubt: {BARCODE_MM[0]:g}–"
                           f"{BARCODE_MM[1]:g} mm")
    return encode(obj.kind, obj.data, obj.error if obj.kind == "qr" else "M")


def modules(obj: BarcodeObject) -> int:
    """Module in der Breite (ungedreht) – EAN-13 mit Klartext samt Platz für die erste Ziffer."""
    code = check(obj)
    return len(code.rows) if code.matrix else len(code.rows[0]) + (code.lead if obj.text else 0)


def quiet_mm(obj: BarcodeObject) -> float:
    """Ruhezone links und rechts (mm) außerhalb des Rahmens, die frei bleiben sollte."""
    modules = 7 if obj.kind == "ean13" and obj.text else QUIET.get(obj.kind, 10)
    return modules * obj.module * 25.4 / DPI


# höchstens so viele Module breit (QR: Version 40; Code 128 ganz in B; Code 39 mit Lücken)
MAX_MODULES = {"qr": 177, "code128": 11 * (MAX_LINEAR + 2) + 13, "code39": 16 * (MAX_LINEAR + 2),
               "ean13": 102, "ean8": 67}


def max_size(obj: BarcodeObject) -> tuple[int, int]:
    """Obere Schranke der Größe (Druckpunkte, ungedreht) ohne Kodieren – für die Grenzen fremder
    Dateien, auch wenn erst die Serie den Inhalt füllt."""
    side = MAX_MODULES.get(obj.kind, 0) * obj.module
    return (side, side) if obj.kind == "qr" else (side, _dots(obj.h_mm))


@dataclass(frozen=True)
class _Layout:
    width: int
    height: int
    bars: int                   # Höhe der Striche
    guards: int                 # Höhe der verlängerten Randzeichen
    font: object = None         # Klartext (None = keiner)
    baseline: int = 0


def size(obj: BarcodeObject) -> tuple[int, int]:
    """Größe (Breite, Höhe) in Druckpunkten, ungedreht."""
    layout = _layout(obj, check(obj))
    return layout.width, layout.height


def _layout(obj: BarcodeObject, code: Code) -> _Layout:
    m = obj.module
    if code.matrix:
        side = len(code.rows) * m
        return _Layout(side, side, side, side)
    width = (len(code.rows[0]) + (code.lead if obj.text else 0)) * m
    height = _dots(obj.h_mm)
    if not obj.text:
        return _Layout(width, height, height, height)
    font, top, bottom, gap = _text_font(code, m, height)
    bars = height - gap - top - bottom
    if bars < _dots(MIN_BARS_MM):
        raise BarcodeError("Barcode zu niedrig für den Klartext – höher ziehen oder Klartext aus")
    return _Layout(width, height, bars, bars + (gap + top) // 2, font, bars + gap + top)


@lru_cache(maxsize=1)
def _font_path() -> str:
    return fonts.resolve(None, False, False).path


def _text_font(code: Code, m: int, height: int):
    """Klartext-Schrift und ihr Platz (Schrift, über und unter der Grundlinie, Abstand zu den
    Strichen): rund ``TEXT_MODULES`` Module groß (mindestens 6 pt), verkleinert, bis jede Gruppe in
    ihre Breite passt und der Klartext höchstens ``TEXT_SHARE`` der Höhe braucht."""
    dots = max(TEXT_MODULES * m, MIN_TEXT_DOTS)
    path = _font_path()
    while True:
        font = fonts.load(path, dots)
        _, top, _, bottom = font.getbbox(code.glyphs, anchor="ls")
        top, bottom, gap = -top, max(0, bottom), max(2, dots // 8)
        over = max(font.getlength(text) / ((end - start) * m) for text, start, end in code.text)
        over = max(over, (gap + top + bottom) / (TEXT_SHARE * height))
        if over <= 1 or dots <= MIN_FIT_DOTS:
            return font, top, bottom, gap
        dots = max(MIN_FIT_DOTS, min(dots - 1, math.floor(dots / over)))


def draw(obj: BarcodeObject) -> Image.Image:
    """Barcode als Graustufenbild (L, weißer Grund, Tinte schwarz) in ``size(obj)``, ungedreht."""
    code = check(obj)
    layout = _layout(obj, code)
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


def _runs(row: str) -> list[tuple[int, int]]:
    """Abschnitte dunkler Module (Anfang, Ende) einer Zeile."""
    runs, start = [], None
    for i, v in enumerate(row + "0"):
        if v == "1" and start is None:
            start = i
        elif v == "0" and start is not None:
            runs.append((start, i))
            start = None
    return runs
