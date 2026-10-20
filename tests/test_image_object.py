"""Image object (stage 3d-2a): model and rendering."""
import io
import random

import pytest
from PIL import Image

from labelwerk.document import Document, ImageObject, TextObject
from labelwerk.imaging import MAX_PIXELS
from labelwerk.labels import DPI
from labelwerk.render import (MARGIN, Renderer, font_warnings, label_size, render_document,
                              render_object, text_layout)


def _dots(mm):
    return round(mm * DPI / 25.4)


def _source(w=600, h=300) -> Image.Image:
    """White image with a black square at the top left (one tenth of the width)."""
    img = Image.new("RGB", (w, h), "white")
    img.paste((0, 0, 0), (0, 0, w // 10, w // 10))
    return img


def _image(**kw) -> ImageObject:
    obj = ImageObject.from_image(_source(), 300, "test.png")
    for key, value in kw.items():
        setattr(obj, key, value)
    return obj


def _decoded(obj: ImageObject) -> Image.Image:
    return Image.open(io.BytesIO(obj.png))


# --- Model --------------------------------------------------------------------------
def test_defaults():
    obj = _image()
    assert (obj.mode, obj.threshold, obj.invert, obj.keep_ratio, obj.rotation) == \
        ("line", 128, False, True, 0)
    assert (obj.source, obj.page, obj.crop, obj.x_mm, obj.y_mm) == ("test.png", None, None, 0, 0)
    assert not obj.is_empty() and obj.positioned


def test_from_image_is_one_to_one_from_dpi():
    obj = ImageObject.from_image(_source(), 300, "a.png")
    assert (obj.w_mm, obj.h_mm) == pytest.approx((50.8, 25.4))
    half = ImageObject.from_image(_source(), 600, "a.png")
    assert (half.w_mm, half.h_mm) == pytest.approx((25.4, 12.7))


def test_from_image_stores_colour_original_as_png():
    src = _source()
    src.putpixel((300, 150), (255, 0, 0))
    obj = ImageObject.from_image(src, 300, "a.png")
    assert _decoded(obj).format == "PNG"
    assert obj.image().mode == "RGB" and obj.image().tobytes() == src.tobytes()


def test_from_image_flattens_transparency():
    src = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    obj = ImageObject.from_image(src, 300, "Zwischenablage")
    assert _decoded(obj).getextrema() == ((255, 255),) * 3


def test_from_image_size_comes_from_crop():
    obj = ImageObject.from_image(_source(), 300, "marke.pdf", page=2, crop=[0, 0, 60, 30])
    assert obj.crop == (0, 0, 60, 30) and obj.page == 2
    assert (obj.w_mm, obj.h_mm) == pytest.approx((5.08, 2.54))
    assert _decoded(obj).size == (600, 300)                # original stays whole


def test_from_image_caps_huge_images_and_their_crop():
    src = Image.new("RGB", (MAX_PIXELS * 2, 20), "white")
    obj = ImageObject.from_image(src, 300, "lang.png", crop=(100, 0, 2100, 20))
    assert _decoded(obj).size == (MAX_PIXELS, 10)
    assert obj.crop == (50, 0, 1050, 10)
    assert obj.w_mm == pytest.approx(2000 / 300 * 25.4)    # print size stays


def test_repr_leaves_out_png_bytes():
    assert "png=" not in repr(_image()) and "test.png" in repr(_image())


def test_limit_resolution_after_shrinking_keeps_natural_size_and_crop():
    obj = ImageObject.from_image(_source(1200, 600), 300, "foto.jpg", crop=(0, 0, 600, 600))
    natural = obj.natural_mm()
    obj.w_mm, obj.h_mm = obj.w_mm / 4, obj.h_mm / 4          # fitted: 1200 dpi
    limited = obj.limit_resolution()
    assert _decoded(limited).size == (600, 300)               # at most 600 dpi
    assert limited.crop == (0, 0, 300, 300) and limited.dpi == pytest.approx(150)
    assert limited.natural_mm() == pytest.approx(natural)     # “original size” stays 1:1
    assert (limited.w_mm, limited.h_mm) == (obj.w_mm, obj.h_mm)
    assert obj.limit_resolution().limit_resolution().png == limited.png


def test_limit_resolution_leaves_fine_images_alone():
    obj = _image(w_mm=25.4, h_mm=12.7)                        # 600 dpi: still within limits
    assert obj.limit_resolution() is obj


def test_document_holds_text_and_images():
    doc = Document("62", objects=[TextObject(""), _image()])
    assert not doc.is_empty()


# --- Rendering ----------------------------------------------------------------------
def _doc(*objects, **kw) -> Document:
    return Document("62", length_mm=80, objects=list(objects), **kw)


def test_render_places_frame_one_to_one():
    obj = _image(x_mm=2, y_mm=3)
    r = render_object(obj, _doc(obj))
    assert (r.x, r.y, r.w, r.h) == (_dots(2), _dots(3), 600, 300)
    assert (r.image_dx, r.image_dy, r.layout) == (0, 0, None)
    assert r.image.mode == "L" and r.image.size == (600, 300)
    assert r.image.getpixel((5, 5)) == 0 and r.image.getpixel((300, 150)) == 255


@pytest.mark.parametrize("rotation, corner", [(90, (295, 5)), (180, (595, 295)),
                                              (270, (5, 595))])
def test_render_rotation_turns_clockwise(rotation, corner):
    obj = _image(rotation=rotation)
    r = render_object(obj, _doc(obj))
    size = (300, 600) if rotation in (90, 270) else (600, 300)
    assert (r.w, r.h) == size and r.image.size == size
    assert r.image.getpixel(corner) == 0                   # square at the top left, rotated
    assert r.image.getpixel((5, 5)) == 255


def test_keep_ratio_fits_into_wrong_frame_and_centres():
    obj = _image(w_mm=50.8, h_mm=50.8)                      # frame square, image 2:1
    r = render_object(obj, _doc(obj))
    assert r.image.size == (600, 600)
    assert r.image.getpixel((5, 5)) == 255                 # top 150 dots free
    assert r.image.getpixel((5, 155)) == 0                 # square begins at 150
    assert r.image.getpixel((5, 215)) == 255               # 60 high
    obj.keep_ratio = False                                  # distorted: square twice as tall
    r = render_object(obj, _doc(obj))
    assert r.image.getpixel((5, 5)) == 0 and r.image.getpixel((5, 110)) == 0
    assert r.image.getpixel((5, 125)) == 255


def test_render_scales_to_frame():
    obj = _image(w_mm=25.4, h_mm=12.7)
    r = render_object(obj, _doc(obj))
    assert r.image.size == (300, 150)
    assert r.image.getpixel((25, 25)) == 0 and r.image.getpixel((35, 35)) == 255


def test_render_uses_crop():
    obj = _image(crop=(0, 0, 60, 60), w_mm=5.08, h_mm=5.08)
    r = render_object(obj, _doc(obj))
    assert r.image.size == (60, 60) and r.image.getextrema() == (0, 0)


def test_render_threshold_invert_and_photo():
    src = Image.new("RGB", (100, 100), (150, 150, 150))
    obj = ImageObject.from_image(src, 300, "grau.png")
    doc = _doc(obj)
    assert render_object(obj, doc).image.getextrema() == (255, 255)    # lighter than 128
    obj.threshold = 160
    assert render_object(obj, doc).image.getextrema() == (0, 0)
    obj.invert = True
    assert render_object(obj, doc).image.getextrema() == (255, 255)
    obj.invert, obj.mode, obj.threshold = False, "photo", 128
    assert render_object(obj, doc).image.getextrema() == (0, 255)      # dots scattered


def _modules(module_px: int, n: int = 21, seed: int = 3) -> tuple[Image.Image, list]:
    """Random pattern of ``n`` × ``n`` modules (like a QR code), ``module_px`` pixels each."""
    rng = random.Random(seed)
    cells = [[rng.random() < 0.5 for _ in range(n)] for _ in range(n)]
    img = Image.new("RGB", (n * module_px, n * module_px), "white")
    for y, row in enumerate(cells):
        for x, dark in enumerate(row):
            if dark:
                img.paste((0, 0, 0), (x * module_px, y * module_px,
                                      (x + 1) * module_px, (y + 1) * module_px))
    return img, cells


@pytest.mark.parametrize("module_px, dpi", [(4, 300), (2, 150)])       # 1:1 and enlarged 2×
def test_codes_stay_bit_exact_at_one_to_one_and_double_size(module_px, dpi):
    img, _ = _modules(module_px)
    obj = ImageObject.from_image(img, dpi, "qr.png")
    r = render_object(obj, _doc(obj))
    ideal = img.convert("L").resize(r.image.size, Image.Resampling.NEAREST)
    assert r.image.tobytes() == ideal.tobytes()


def test_large_image_is_reduced_before_lanczos():
    """Strongly reduced: first reduce by integer factors, then Lanczos (``reducing_gap=2``)."""
    from labelwerk import render
    src = Image.radial_gradient("L").convert("RGB").resize((1800, 1200))
    obj = ImageObject.from_image(src, 600, "gross.png")
    obj.w_mm, obj.h_mm = 25.4, 25.4 * 2 / 3                # 300 × 200 dots
    render._scaled_source.cache_clear()
    picture = render._scaled_source(obj.png, None, (300, 200), True)
    expected = src.resize((300, 200), Image.Resampling.LANCZOS, reducing_gap=2.0)
    assert picture.tobytes() == expected.tobytes()


@pytest.mark.parametrize("field, value, message", [
    ("mode", "farbe", "Umwandlung"), ("threshold", 300, "Schwelle"),
    ("rotation", 45, "Drehung"), ("crop", (0, 0, 700, 10), "Ausschnitt"),
    ("crop", (10, 10, 10, 20), "Ausschnitt"), ("w_mm", 0, "Größe")])
def test_invalid_image_settings_raise_at_render(field, value, message):
    obj = _image(**{field: value})
    with pytest.raises(ValueError, match=message):
        render_object(obj, _doc(obj))


def test_image_grows_auto_length():
    obj = _image(x_mm=1, y_mm=10)
    doc = Document("62", objects=[obj])
    assert label_size(doc) == (696, _dots(10) + 300)    # 1 mm margin lies in the printer's feed


def test_preview_equals_print_with_text_and_images():
    for orientation in ("vertical", "horizontal"):
        doc = _doc(TextObject("Absender", size_pt=12, x_mm=2, y_mm=2),
                   _image(x_mm=10, y_mm=10, rotation=90),
                   _image(x_mm=30, y_mm=5, mode="photo", invert=True),
                   orientation=orientation)
        printed = render_document(doc)
        assert Renderer().render(doc).image.tobytes() == printed.tobytes()
        assert printed.size == ((label_size(doc)[::-1]) if orientation == "horizontal"
                                else label_size(doc))


def test_image_ink_lands_on_the_label():
    obj = _image(x_mm=2, y_mm=3)
    img = render_document(_doc(obj))
    x, y = _dots(2), _dots(3)
    assert img.getpixel((x + 5, y + 5)) == (0, 0, 0)
    assert img.getpixel((x + 300, y + 150)) == (255, 255, 255)
    assert img.getpixel((MARGIN, MARGIN)) == (255, 255, 255)


def test_text_helpers_skip_or_refuse_images():
    obj = _image()
    assert font_warnings(_doc(obj)) == []
    with pytest.raises(TypeError, match="Text"):
        text_layout(obj, _doc(obj))
