"""Barcodes: Kodieren (Code 128, Code 39, EAN, QR), Maße, Zeichnen in ganzen Druckpunkten,
Rendern auf dem Etikett – und Lesbarkeit mit einem unabhängigen Leser (zxing-cpp)."""
import re

import pytest
from PIL import Image
from labelwerk import barcodes
from labelwerk.barcodes import BarcodeError, check_digit, encode
from labelwerk.document import BarcodeObject, Document
from labelwerk.render import Renderer, render_document, render_object


def _bar(**kw) -> BarcodeObject:
    return BarcodeObject(**kw)


def _runs(row: str) -> list[int]:
    """Breiten der Abschnitte gleicher Module."""
    widths, last = [], None
    for v in row:
        if v == last:
            widths[-1] += 1
        else:
            widths.append(1)
            last = v
    return widths


# --- Code 128 ----------------------------------------------------------------------------------
def test_code128_table_has_distinct_patterns_of_eleven_modules():
    assert len(barcodes._C128) == 106
    assert len(set(barcodes._C128)) == 106
    for pattern in barcodes._C128:
        assert len(pattern) == 6 and sum(map(int, pattern)) == 11
        assert all(1 <= int(w) <= 4 for w in pattern)
    assert sum(map(int, barcodes._C128_STOP)) == 13


def test_code128_uses_set_c_for_digit_runs():
    assert barcodes._code128_values("123456") == [105, 12, 34, 56]
    # ungerade Ziffern: die letzte in B
    assert barcodes._code128_values("12345") == [105, 12, 34, 100, 21]
    # „X“ in B, dann acht Ziffern in C: 7 Werte statt 10
    assert barcodes._code128_values("X12345678") == [104, 56, 99, 12, 34, 56, 78]
    # kurze Ziffernfolgen lohnen den Wechsel nicht
    assert barcodes._code128_values("A12B") == [104, 33, 17, 18, 34]


def test_code128_has_check_value_and_stop():
    code = encode("code128", "AB")
    values = [104, 33, 34]
    check = (104 + 1 * 33 + 2 * 34) % 103
    expected = "".join(barcodes._bars(barcodes._C128[v]) for v in [*values, check])
    assert code.rows == (expected + barcodes._bars(barcodes._C128_STOP),)
    assert code.text == (("AB", 0, len(code.rows[0])),)
    assert code.glyphs == "".join(chr(c) for c in range(32, 127)) and code.readable == "AB"


@pytest.mark.parametrize("char", ["ä", "€", "\t", "\x7f"])
def test_code128_rejects_characters_outside_ascii(char):
    with pytest.raises(BarcodeError, match=f"Code 128 kann „{char}“ nicht darstellen"):
        encode("code128", f"A{char}")


# --- Code 39 -----------------------------------------------------------------------------------
def test_code39_patterns_have_three_wide_of_nine():
    assert len(barcodes._C39) == 44
    for pattern in barcodes._C39.values():
        assert len(pattern) == 9 and pattern.count("1") == 3


def test_code39_adds_start_stop_and_narrow_gaps():
    code = encode("code39", "A")
    # *A* – je Zeichen 3 breite (3 Module) und 6 schmale Elemente = 15, zwei Lücken
    assert len(code.rows[0]) == 3 * 15 + 2
    assert _runs(code.rows[0])[:9] == [1, 3, 1, 1, 3, 1, 3, 1, 1]     # „*“ = 010010100
    assert code.text == (("A", 0, 47),)


def test_code39_prints_lowercase_as_uppercase():
    assert encode("code39", "x1-k3").readable == "X1-K3"
    assert encode("code39", "x1-k3").rows == encode("code39", "X1-K3").rows


@pytest.mark.parametrize("char", ["*", "ß", "ä", "#", "_", "ı", "ſ"])
def test_code39_rejects_other_characters(char):
    with pytest.raises(BarcodeError, match=re.escape(f"Code 39 kann „{char}“ nicht darstellen")):
        encode("code39", f"A{char}")


# --- EAN ---------------------------------------------------------------------------------------
def test_ean_check_digit():
    assert check_digit("590123412345") == 7
    assert check_digit("400638133393") == 1
    assert check_digit("9638507") == 4
    assert check_digit("000000000000") == 0


def test_ean13_completes_the_check_digit():
    code = encode("ean13", "590123412345")
    assert code.readable == "5901234123457"
    assert encode("ean13", "5901234123457").rows == code.rows
    assert len(code.rows[0]) == 95
    assert code.rows[0][:3] == "101" and code.rows[0][45:50] == "01010" and code.rows[0][-3:] == "101"
    assert code.text == (("5", -7, 0), ("901234", 3, 45), ("123457", 50, 92))
    assert code.lead == 7


def test_ean13_first_digit_selects_the_parity_of_the_left_half():
    # erste Ziffer 0: alle links in L (ungerade Zahl dunkler Module je Ziffer)
    code = encode("ean13", "000000000000")
    for k in range(6):
        assert code.rows[0][3 + 7 * k:10 + 7 * k] == barcodes._L[0]
    code = encode("ean13", "100000000000")       # LLGLGG
    digits = [code.rows[0][3 + 7 * k:10 + 7 * k] for k in range(6)]
    assert digits == [barcodes._L[0], barcodes._L[0], barcodes._G[0], barcodes._L[0],
                      barcodes._G[0], barcodes._G[0]]


def test_ean8_layout():
    code = encode("ean8", "9638507")
    assert code.readable == "96385074"
    assert len(code.rows[0]) == 67
    assert code.text == (("9638", 3, 31), ("5074", 36, 64)) and code.lead == 0


def test_ean_ignores_spaces():
    assert encode("ean13", "5 901234 123457").readable == "5901234123457"


def test_ean_reports_a_wrong_check_digit():
    with pytest.raises(BarcodeError, match="EAN-13: Prüfziffer falsch – richtig wäre 7"):
        encode("ean13", "5901234123450")
    with pytest.raises(BarcodeError, match="EAN-8: Prüfziffer falsch – richtig wäre 4"):
        encode("ean8", "96385070")


def test_ean_reports_length_and_letters():
    with pytest.raises(BarcodeError, match=r"EAN-13 braucht 12 oder 13 Ziffern \(4 eingegeben\)"):
        encode("ean13", "4006")
    with pytest.raises(BarcodeError, match=r"EAN-8 braucht 7 oder 8 Ziffern \(9 eingegeben\)"):
        encode("ean8", "123456789")
    with pytest.raises(BarcodeError, match="EAN-13 kann nur Ziffern darstellen, nicht „A“"):
        encode("ean13", "59012341234A")
    with pytest.raises(BarcodeError, match="nicht „²“"):       # Unicode-Ziffer, kein ASCII
        encode("ean8", "963850²")


# --- QR ----------------------------------------------------------------------------------------
def test_qr_matrix_and_error_level():
    code = encode("qr", "labelwerk", "M")
    assert code.matrix and len(code.rows) == 21 and all(len(r) == 21 for r in code.rows)
    assert code.rows[0][:7] == "1111111"                      # Suchmuster
    long = "https://example.org/" + "x" * 40
    assert len(encode("qr", long, "H").rows) > len(encode("qr", long, "L").rows)


def test_qr_too_long_for_the_level():
    data = "x" * 2000
    assert encode("qr", data, "L").matrix
    with pytest.raises(BarcodeError, match=r"Inhalt zu lang für einen QR-Code \(Fehlerkorrektur H\)"):
        encode("qr", data, "H")


def test_qr_rejects_unknown_level():
    with pytest.raises(BarcodeError, match="Fehlerkorrektur"):
        encode("qr", "x", "X")


# --- allgemeine Prüfungen ------------------------------------------------------------------------
def test_empty_and_too_long_content():
    with pytest.raises(BarcodeError, match="Barcode ohne Inhalt"):
        encode("code128", "")
    with pytest.raises(BarcodeError, match=r"Code 128: Inhalt zu lang \(81 Zeichen, höchstens 80\)"):
        encode("code128", "x" * 81)
    with pytest.raises(BarcodeError, match=r"Inhalt zu lang \(2001 Zeichen, höchstens 2000\)"):
        encode("qr", "x" * 2001)
    with pytest.raises(BarcodeError, match="Unbekannte Barcode-Art"):
        encode("pdf417", "x")
    with pytest.raises(BarcodeError, match="Inhalt muss Text sein"):
        encode("qr", 5)


@pytest.mark.parametrize("field, value, message", [
    ("module", 0, "Modulbreite"), ("module", 21, "Modulbreite"), ("module", True, "Modulbreite"),
    ("module", 2.0, "Modulbreite"), ("h_mm", 1.9, "Höhe"), ("h_mm", 100.5, "Höhe"),
    ("h_mm", float("nan"), "Höhe"), ("h_mm", True, "Höhe"), ("text", 1, "Klartext"),
    ("error", "m", "Fehlerkorrektur"), ("rotation", 45, "Drehung")])
def test_check_rejects_invalid_settings(field, value, message):
    with pytest.raises(BarcodeError, match=message):
        barcodes.check(_bar(kind="code128", data="A", **{field: value}))


def test_qr_ignores_the_height():
    barcodes.check(_bar(kind="qr", data="A", h_mm=0.5))


def test_errors_are_value_errors():
    assert issubclass(BarcodeError, ValueError)        # Renderfehler wie TextTooLarge


# --- Maße und Zeichnen ---------------------------------------------------------------------------
def test_size_follows_modules_and_height():
    assert barcodes.size(_bar(kind="qr", data="labelwerk", module=4)) == (84, 84)
    code = encode("code128", "ABC")
    assert barcodes.size(_bar(kind="code128", data="ABC", module=3, h_mm=10)) == (
        3 * len(code.rows[0]), 118)
    # EAN-13 mit Klartext: 7 Module links für die erste Ziffer
    assert barcodes.size(_bar(kind="ean13", data="590123412345", module=2)) == (2 * 102, 118)
    assert barcodes.size(_bar(kind="ean13", data="590123412345", module=2, text=False)) == (190, 118)
    assert barcodes.modules(_bar(kind="ean13", data="590123412345")) == 102
    assert barcodes.modules(_bar(kind="qr", data="labelwerk")) == 21


def test_draw_has_the_size_and_only_black_and_white_bars():
    obj = _bar(kind="code128", data="X1-K3", module=3, h_mm=10)
    img = barcodes.draw(obj)
    assert img.mode == "L" and img.size == barcodes.size(obj)
    layout = barcodes._layout(obj, encode("code128", "X1-K3"))
    bars = img.crop((0, 0, img.width, layout.bars))
    assert set(bars.tobytes()) == {0, 255}                  # keine Kantenglättung
    row = "".join("1" if bars.getpixel((x, 0)) == 0 else "0" for x in range(0, img.width, 3))
    assert row == encode("code128", "X1-K3").rows[0]
    assert all(w % 3 == 0 for w in _runs(
        "".join("1" if bars.getpixel((x, 0)) == 0 else "0" for x in range(img.width))))


def test_draw_qr_modules():
    obj = _bar(kind="qr", data="labelwerk", module=5)
    img = barcodes.draw(obj)
    rows = encode("qr", "labelwerk").rows
    for y in (0, 7, 20):
        for x in range(21):
            for dx, dy in ((0, 0), (4, 4)):
                assert (img.getpixel((5 * x + dx, 5 * y + dy)) == 0) == (rows[y][x] == "1")


def test_text_lies_below_the_bars():
    obj = _bar(kind="code128", data="ABC", module=3, h_mm=10)
    img = barcodes.draw(obj)
    layout = barcodes._layout(obj, encode("code128", "ABC"))
    text = img.crop((0, layout.bars, img.width, img.height))
    assert text.getextrema()[0] == 0                       # Tinte im Klartext
    plain = barcodes.draw(_bar(kind="code128", data="ABC", module=3, h_mm=10, text=False))
    assert plain.size == img.size
    assert plain.crop((0, layout.bars, img.width, img.height)).getextrema()[0] == 0   # Striche


def test_ean_guards_reach_into_the_text():
    obj = _bar(kind="ean13", data="590123412345", module=3, h_mm=12)
    img = barcodes.draw(obj)
    layout = barcodes._layout(obj, encode("ean13", "590123412345"))
    assert layout.guards > layout.bars
    x_guard, x_digit = 3 * 7, 3 * (7 + 3)                  # erstes Randzeichen, erste Ziffer
    assert img.getpixel((x_guard, layout.guards - 1)) == 0
    assert img.getpixel((x_guard, layout.guards)) == 255
    assert img.getpixel((x_digit + 1, layout.bars)) == 255           # Lücke über den Ziffern


def test_text_shrinks_to_fit_the_width():
    obj = _bar(kind="code128", data="WWWWWWWWWW", module=1, h_mm=8)
    layout = barcodes._layout(obj, encode("code128", "WWWWWWWWWW"))
    assert layout.font.getlength("WWWWWWWWWW") <= barcodes.size(obj)[0]
    big = barcodes._layout(_bar(kind="code128", data="1", module=4, h_mm=10),
                           encode("code128", "1"))
    assert big.font.size == 36                                # 9 Module


@pytest.mark.parametrize("kind, data", [("code128", "Ag"), ("code39", "A"), ("ean13", "590123412345"),
                                        ("ean8", "9638507")])
@pytest.mark.parametrize("module", [1, 4, 11, 20])
def test_low_bar_codes_get_smaller_text(kind, data, module):
    """Jede Höhe ab 2 mm lässt sich rendern: der Klartext wird kleiner (höchstens 40 % der
    Höhe, solange die kleinste Schrift das zulässt), die Striche bleiben mindestens 1 mm."""
    obj = _bar(kind=kind, data=data, module=module, h_mm=2)
    layout = barcodes._layout(obj, encode(kind, data))
    assert layout.bars >= 12
    tall = barcodes._layout(_bar(kind=kind, data=data, module=module, h_mm=20),
                            encode(kind, data))
    assert layout.font.size <= tall.font.size and layout.font.size < max(9 * module, 25)
    assert barcodes.draw(obj).size == barcodes.size(obj)


def test_text_height_is_the_same_for_every_content():
    """Platz für den Klartext aus allen Zeichen der Art – in einer Serie bleiben die Striche
    gleich hoch."""
    low = barcodes._layout(_bar(kind="code128", data="aaa"), encode("code128", "aaa"))
    deep = barcodes._layout(_bar(kind="code128", data="gjp"), encode("code128", "gjp"))
    assert low.bars == deep.bars


@pytest.mark.parametrize("kind, data", [("code39", "JQ$/"), ("code128", "gjpqy|()"),
                                        ("ean13", "590123412345"), ("ean8", "9638507")])
def test_text_is_not_cut_off(kind, data):
    from PIL import Image, ImageDraw
    obj = _bar(kind=kind, data=data, module=3, h_mm=12)
    code = encode(kind, data)
    layout = barcodes._layout(obj, code)
    img = barcodes.draw(obj)
    text = img.crop((0, layout.guards, img.width, img.height))       # unter den Randzeichen
    big = Image.new("L", (img.width + 200, img.height + 200), 255)
    pen = ImageDraw.Draw(big)
    x0 = (code.lead if obj.text else 0) * 3 + 100
    for part, start, end in code.text:
        pen.text((x0 + (start + end) * 3 / 2, layout.baseline + 100), part, fill=0,
                 font=layout.font, anchor="ms")
    whole = big.crop((0, layout.guards + 100, big.width, big.height))
    assert text.histogram()[0] == whole.histogram()[0] > 0           # keine Tinte abgeschnitten


def test_quiet_zone():
    assert barcodes.quiet_mm(_bar(kind="code128", data="A", module=3)) == pytest.approx(2.54)
    assert barcodes.quiet_mm(_bar(kind="qr", data="A", module=6)) == pytest.approx(2.032)
    # EAN-13: links 11 Module, die erste Ziffer (7) liegt mit Klartext schon im Rahmen
    assert barcodes.quiet_mm(_bar(kind="ean13", data="1", module=3)) == pytest.approx(7 * 0.254)
    assert barcodes.quiet_mm(_bar(kind="ean13", data="1", module=3, text=False)) == \
        pytest.approx(11 * 0.254)


def test_max_size_bounds_every_content():
    """Obere Schranke ohne Kodieren (Grenzen fremder Dateien) – auch für Platzhalter."""
    for kind, data in (("qr", "x" * 2000), ("code128", "\x7e" * 80), ("code39", "W" * 80),
                       ("ean13", "590123412345"), ("ean8", "9638507"), ("code128", "1" * 80)):
        for text in (True, False):
            obj = _bar(kind=kind, data=data, module=3, h_mm=10, error="L", text=text)
            w, h = barcodes.size(obj)
            mw, mh = barcodes.max_size(obj)
            assert w <= mw and h <= mh, (kind, w, mw)


def test_unhashable_settings_are_barcode_errors():
    with pytest.raises(BarcodeError):
        encode(["qr"], "x")
    with pytest.raises(BarcodeError):
        encode("qr", ["x"])
    with pytest.raises(BarcodeError):
        barcodes.check(_bar(kind="qr", data="x", error=["M"]))


# --- Rendern -----------------------------------------------------------------------------------
def test_render_places_the_barcode_at_its_position():
    obj = _bar(kind="qr", data="labelwerk", module=4, x_mm=5, y_mm=3)
    r = render_object(obj, Document("62x29", objects=[obj]))
    assert (r.x, r.y, r.w, r.h, r.base_pt) == (59, 35, 84, 84, 0.0)
    img = render_document(Document("62x29", objects=[obj]))
    assert img.getpixel((59, 35))[0] == 0 and img.getpixel((58, 35))[0] == 255


def test_render_turns_the_barcode():
    obj = _bar(kind="code128", data="AB", module=2, h_mm=5, rotation=90)
    w, h = barcodes.size(obj)
    r = render_object(obj, Document("62x29", objects=[obj]))
    assert (r.w, r.h) == (h, w) and r.image.size == (h, w)
    straight = barcodes.draw(obj)
    assert r.image.tobytes() == straight.transpose(Image.Transpose.ROTATE_270).tobytes()


def test_invalid_barcode_is_a_render_error():
    obj = _bar(kind="ean13", data="123")
    with pytest.raises(BarcodeError, match="EAN-13 braucht"):
        render_document(Document("62x29", objects=[obj]))
    with pytest.raises(BarcodeError):
        Renderer().render(Document("62x29", objects=[obj]))


def test_endless_label_grows_with_the_barcode():
    obj = _bar(kind="code128", data="ABCDEFGHIJ", module=4, x_mm=2, y_mm=2, h_mm=8)
    img = render_document(Document("62", orientation="horizontal", objects=[obj]))
    w, _ = barcodes.size(obj)
    assert img.height >= round(2 * 300 / 25.4) + w            # gedreht: Länge = Bildhöhe


def test_renderer_cache_keeps_an_unchanged_barcode():
    obj = _bar(kind="qr", data="x", module=4)
    doc = Document("62x29", objects=[obj])
    renderer = Renderer()
    first = renderer.render(doc).objects[0]
    assert renderer.render(doc).objects[0] is first
    obj.data = "y"
    assert renderer.render(doc).objects[0] is not first

