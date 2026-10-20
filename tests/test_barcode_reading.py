"""Are barcodes readable? zxing-cpp (independent reader, development only) reads what would be printed –
every kind, rotated, with and without plain text, every Code 128 value, every Code 39 character."""
import pytest
from PIL import ImageOps

from labelwerk import barcodes
from labelwerk.document import BarcodeObject, Document
from labelwerk.render import render_document

zxingcpp = pytest.importorskip("zxingcpp", reason="zxing-cpp fehlt (Wheels erst ab Python 3.12)")


def _bar(**kw) -> BarcodeObject:
    return BarcodeObject(**kw)


def _read(img) -> list[str]:
    return [r.text for r in zxingcpp.read_barcodes(ImageOps.expand(img.convert("L"), 40, 255))]


@pytest.mark.parametrize("kind, data, expected", [
    ("qr", "https://example.org/x?y=1", "https://example.org/x?y=1"),
    ("qr", "Grüße aus Köln – 24 V", "Grüße aus Köln – 24 V"),
    ("code128", "X1-K3 24V", "X1-K3 24V"), ("code128", "0123456789", "0123456789"),
    ("code39", "x1-k3", "X1-K3"), ("ean13", "590123412345", "5901234123457"),
    ("ean8", "9638507", "96385074")])
@pytest.mark.parametrize("module", [2, 3])
@pytest.mark.parametrize("text", [True, False])
def test_zxing_reads_every_kind(kind, data, expected, module, text):
    assert _read(barcodes.draw(_bar(kind=kind, data=data, module=module, h_mm=10,
                                    text=text))) == [expected]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_zxing_reads_the_printed_label(rotation):
    objs = [_bar(kind="qr", data="Etikett 1", module=4, x_mm=2, y_mm=2, rotation=rotation),
            _bar(kind="code128", data="K-24", module=2, x_mm=30, y_mm=4, h_mm=8,
                 rotation=rotation)]
    found = _read(render_document(Document("62x29", objects=objs)))
    assert sorted(found) == ["Etikett 1", "K-24"]


def test_zxing_reads_every_code128_value():
    pairs = "".join(f"{i:02d}" for i in range(100))          # character set C: values 0–99
    for start in range(0, 200, 80):
        assert _read(barcodes.draw(_bar(kind="code128", data=pairs[start:start + 80]))) \
            == [pairs[start:start + 80]]
    ascii_ = "".join(chr(c) for c in range(32, 127))        # character set B: values 0–94
    for start in range(0, 95, 50):
        part = ascii_[start:start + 50]
        assert _read(barcodes.draw(_bar(kind="code128", data=part, text=False))) == [part]
    for data in ("a1234b", "12345", "X12345678", "1a2"):  # switch B ↔ C
        assert _read(barcodes.draw(_bar(kind="code128", data=data))) == [data]


def test_zxing_reads_every_code39_character():
    data = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%"
    assert _read(barcodes.draw(_bar(kind="code39", data=data, text=False))) == [data]


@pytest.mark.parametrize("level", ["L", "M", "Q", "H"])
def test_zxing_reads_every_qr_level(level):
    assert _read(barcodes.draw(_bar(kind="qr", data="Level", error=level, module=3))) == ["Level"]


def test_zxing_reads_one_dot_modules():
    assert _read(barcodes.draw(_bar(kind="ean13", data="400638133393", module=1, h_mm=8))) \
        == ["4006381333931"]


def test_zxing_reads_barcodes_on_a_203_dpi_label():
    """Other printers: modules in whole dots at 203 dpi stay readable."""
    objs = [_bar(kind="qr", data="Zebra 203", module=3, x_mm=2, y_mm=2),
            _bar(kind="code128", data="Z-203", module=2, x_mm=22, y_mm=4, h_mm=10)]
    found = _read(render_document(Document("57x32mm@203", objects=objs)))
    assert sorted(found) == ["Z-203", "Zebra 203"]
