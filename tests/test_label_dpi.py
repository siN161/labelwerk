"""Resolution per label (printers of other manufacturers): labels "BxHmm@dpi", rendering, layout and
barcodes in the resolution of the printer – the same label has the same size at 203 and 300 dpi."""
import pytest
from PIL import Image

from labelwerk import barcodes, layout, storage
from labelwerk.document import BarcodeObject, Document, Frame, ImageObject, TextObject
from labelwerk.files import fit_to_label
from labelwerk.labels import get_label, sized_id, sized_label
from labelwerk.render import Renderer, render_document, render_object

L203, L300 = "57x32mm@203", "57x32mm@300"


def _ink(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


# --- Labels -------------------------------------------------------------------------------------
def test_sized_labels():
    label = get_label("54x25mm@300")
    assert (label.width, label.height, label.dpi, label.shape) == (638, 295, 300, "die_cut")
    assert label.description == "54 × 25 mm · 300 dpi"
    assert get_label(L203).width == round(57 * 203 / 25.4) == 456
    assert get_label("101.6x152.4mm@203").description == "101,6 × 152,4 mm · 203 dpi"
    assert get_label("62").dpi == 300                         # Brother as before
    assert sized_id(101.6, 50.8, 203) == "101.6x50.8mm@203" and sized_id(54, 25, 300) == "54x25mm@300"


@pytest.mark.parametrize("label_id", ["54x25mm@50", "54x25mm@900", "400x25mm@300", "54x25@300",
                                      "1x25mm@300", "54x25mm@300 ", "54x25mm"])
def test_invalid_sized_labels(label_id):
    assert sized_label(label_id) is None
    with pytest.raises(ValueError, match="Unbekanntes Etikett"):
        get_label(label_id)


def test_sized_label_is_saved_and_opened():
    doc = Document(L203, objects=[TextObject("A")])
    assert storage.from_dict(storage.to_dict(doc)).label_id == L203


# --- Rendering ----------------------------------------------------------------------------------
def test_label_image_has_the_printer_resolution():
    assert render_document(Document(L203, objects=[TextObject("A")])).size == (456, 256)
    assert render_document(Document(L300, objects=[TextObject("A")])).size == (673, 378)


def test_text_has_the_same_size_at_every_resolution():
    def height_mm(label_id):
        img = render_document(Document(label_id, objects=[TextObject("Hg", size_pt=20)]))
        l, t, r, b = _ink(img)
        return (b - t) * 25.4 / get_label(label_id).dpi
    assert height_mm(L203) == pytest.approx(height_mm(L300), abs=0.3)


def test_positions_and_frames_in_millimetres():
    obj = TextObject("A", size_pt=12, x_mm=10, y_mm=5)
    r = render_object(obj, Document(L203, objects=[obj]))
    assert (r.x, r.y, r.dpi) == (round(10 * 203 / 25.4), round(5 * 203 / 25.4), 203)
    assert layout.object_rect(r).x == pytest.approx(10, abs=0.13)
    image = ImageObject.from_image(Image.new("RGB", (236, 118), "black"), 300, "x")  # 20 × 10 mm
    rendered = render_object(image, Document(L203, objects=[image]))
    assert (rendered.w, rendered.h) == (160, 80)
    framed = render_document(Document(L203, frame=Frame("single", line_mm=1), margin_mm=0))
    assert framed.getpixel((7, 100))[0] == 0 and framed.getpixel((8, 100))[0] == 255   # 1 mm = 8


def test_too_large_message_uses_the_resolution():
    from labelwerk.render import TextTooLarge
    obj = TextObject("WWWWWWWWWWWW", size_pt=40)
    with pytest.raises(TextTooLarge) as small:
        render_document(Document(L203, objects=[obj]))
    with pytest.raises(TextTooLarge) as large:
        render_document(Document(L300, objects=[obj]))
    assert abs(small.value.max_pt - large.value.max_pt) <= 1


def test_renderer_and_layout_rects_carry_the_resolution():
    doc = Document(L203, objects=[TextObject("A", size_pt=12, x_mm=3, y_mm=3)])
    result = Renderer().render(doc)
    assert result.objects[0].dpi == 203
    area = layout.printable_area(doc)
    assert (area.w, area.h) == (pytest.approx(57 - 2, abs=0.15), pytest.approx(32 - 2, abs=0.15))


# --- Barcodes and layout ------------------------------------------------------------------------
def test_barcode_modules_are_printer_dots():
    obj = BarcodeObject(kind="code128", data="AB", module=2, h_mm=10, x_mm=2, y_mm=2)
    r = render_object(obj, Document(L203, objects=[obj]))
    assert r.w == barcodes.modules(obj) * 2 and r.h == round(10 * 203 / 25.4)
    assert layout.barcode_rect(obj, 203).w == pytest.approx(barcodes.modules(obj) * 2 * 25.4 / 203)
    wider = layout.set_frame(obj, layout.Rect(2, 2, layout.barcode_rect(obj, 203).w * 1.5, 10), r)
    assert wider.module == 3                                  # 1.5 × 2 dots at 203 dpi


def test_fixed_size_text_keeps_its_look_at_203():
    obj = TextObject("Hallo")
    doc = Document(L203, objects=[obj])
    r = render_object(obj, doc)
    moved = layout.move(obj, layout.object_rect(r).moved(1, 1), r)
    again = render_object(moved, Document(L203, objects=[moved]))
    assert (again.w, again.h) == (r.w, r.h)


def test_new_barcode_on_a_203_label():
    doc = Document(L203)
    area = layout.printable_area(doc)
    obj = layout.new_barcode(doc, "QL-600", area, "qr")
    rect = layout.barcode_rect(obj, 203)
    assert rect.x >= area.x - 1e-6 and rect.right <= area.right + 1e-6


def test_print_file_scales_to_the_resolution():
    img = Image.new("L", (300, 150), 0)                     # 25.4 × 12.7 mm at 300 dpi
    out = fit_to_label(img, L203)
    assert out.size == (456, 256)
    assert _ink(out.convert("RGB"))[2] - _ink(out.convert("RGB"))[0] == 203


# --- After the check: dimensions in mm instead of fixed dots -----------------------------------
@pytest.mark.parametrize("label_id", ["057x32mm@203", "57.0x32mm@203", "57x32mm@0203"])
def test_only_one_spelling_per_label(label_id):
    assert sized_label(label_id) is None
    assert sized_id(57, 32, 203.6) == "57x32mm@204"


def test_inserted_barcodes_have_the_same_millimetres():
    for dpi, ean, qr in ((203, 2, 4), (300, 3, 6), (600, 6, 12)):
        assert (barcodes.insert_module("ean13", dpi), barcodes.insert_module("qr", dpi)) == (ean, qr)
    assert (barcodes.max_module(203), barcodes.max_module(300), barcodes.max_module(600)) == (14, 20, 40)
    doc = Document("57x32mm@600")
    obj = layout.new_barcode(doc, "QL-600", layout.printable_area(doc), "ean13")
    assert obj.module * 25.4 / 600 >= 0.25


def test_barcode_text_has_the_same_size_at_every_resolution():
    def text_mm(dpi):
        obj = BarcodeObject(kind="ean13", data="590123412345",
                            module=barcodes.scaled(3, dpi), h_mm=15)
        return barcodes._layout(obj, barcodes.check(obj), dpi).font.size * 25.4 / dpi
    assert text_mm(203) == pytest.approx(text_mm(300), rel=0.1)
    assert text_mm(600) == pytest.approx(text_mm(300), rel=0.1)


def test_storage_limit_counts_printer_dots():
    from labelwerk.storage import StorageError
    big = ImageObject.from_image(Image.new("RGB", (8, 8), "black"), 300, "x")
    big.w_mm = big.h_mm = 290
    data = storage.to_dict(Document("300x300mm@300", objects=[big]))
    storage.from_dict(data)                                   # 11.7 million dots: works
    many = storage.to_dict(Document("300x300mm@600", objects=[big] * 3))
    with pytest.raises(StorageError, match="Etikett zu groß"):
        storage.from_dict(many)                               # 3 × 46.9 million dots at 600 dpi


def test_sizes_are_shown_with_a_comma():
    from labelwerk.labels import mm_text
    assert (mm_text(101.6), mm_text(57.0), mm_text(62)) == ("101,6", "57", "62")


def test_pdf_is_loaded_in_the_printer_resolution(tmp_path):
    from labelwerk.files import load_file
    path = tmp_path / "a.png"
    Image.new("L", (300, 300), 0).save(path, dpi=(300, 300))   # 25.4 mm
    assert load_file(path, dpi=203).size == (203, 203)
    sharp = fit_to_label(load_file(path, dpi=203), L203, dpi=203)
    assert _ink(sharp.convert("RGB"))[2] - _ink(sharp.convert("RGB"))[0] == 203


def test_changing_the_label_keeps_barcode_millimetres():
    doc = Document("57x32mm@300", objects=[BarcodeObject(kind="qr", data="x", module=6),
                                           TextObject("A")])
    layout.change_label(doc, "57x32mm@203")
    assert doc.label_id == "57x32mm@203" and doc.objects[0].module == 4
    layout.change_label(doc, "62x29")
    assert doc.objects[0].module == 6
