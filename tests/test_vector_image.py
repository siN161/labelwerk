"""Vector images (stage 3d-2c): image objects with SVG are rasterised at frame size –
sharp at any size. The core does not rasterise itself (Qt-free); here a substitute function."""
import pytest
from PIL import Image, ImageDraw

from labelwerk import render
from labelwerk.document import Document, ImageObject
from labelwerk.labels import DPI
from labelwerk.render import Renderer, render_document, render_object

SVG = b"<svg xmlns='http://www.w3.org/2000/svg' width='100' height='50'/>"


def _dots(mm):
    return round(mm * DPI / 25.4)


class LineRasterizer:
    """Substitute: white sheet of size ``size`` with a 1-pixel-thin black line across
    the middle; returns the section ``region`` and records the calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, svg, size, region):
        self.calls.append((svg, size, region))
        w, h = size
        sheet = Image.new("RGB", size, "white")
        ImageDraw.Draw(sheet).line((0, h // 2, w - 1, h // 2), fill="black")
        x, y, rw, rh = region
        return sheet.crop((x, y, x + rw, y + rh))


@pytest.fixture
def rasterizer():
    fake = LineRasterizer()
    render.set_svg_rasterizer(fake)
    yield fake
    render.set_svg_rasterizer(None)


def _preview(w=100, h=50):
    """Preview PNG as the raster function delivers it, small."""
    img = Image.new("RGB", (w, h), "white")
    ImageDraw.Draw(img).line((0, h // 2, w - 1, h // 2), fill="black")
    return img


def _vector(w_mm, h_mm, crop=None, **kw):
    obj = ImageObject.from_image(_preview(), 300, "Symbol: Linie", crop=crop, svg=SVG)
    obj.w_mm, obj.h_mm = w_mm, h_mm
    for key, value in kw.items():
        setattr(obj, key, value)
    return obj


def _ink_rows(img):
    """Rows with ink (image "L"/"1": 0 = black)."""
    gray = img.convert("L")
    return [y for y in range(gray.height) if gray.crop((0, y, gray.width, y + 1)).getextrema()[0] < 128]


def test_from_image_keeps_svg_out_of_repr():
    obj = _vector(10, 5)
    assert obj.svg == SVG and "svg" not in repr(obj)


def test_image_without_svg_has_none():
    assert ImageObject.from_image(_preview(), 300, "x.png").svg is None


@pytest.mark.parametrize("w_mm", [8, 25, 55])
def test_vector_stays_one_dot_thin_in_every_size(rasterizer, w_mm):
    """A pixel image would smear when enlarged – the vector image is rasterised anew."""
    obj = _vector(w_mm, w_mm / 2)
    rendered = render_object(obj, Document("62", length_mm=60, objects=[obj]))
    w, h = _dots(w_mm), _dots(w_mm / 2)
    assert rendered.image.size == (w, h)
    assert _ink_rows(rendered.image) == [h // 2]
    svg, size, region = rasterizer.calls[-1]
    assert svg == SVG and size == (w, h) and region == (0, 0, w, h)


def test_crop_rasterizes_only_the_region(rasterizer):
    """Section in the middle: the whole sheet at the size at which the section fills
    the frame – only the section is delivered."""
    obj = _vector(20, 10, crop=(25, 0, 75, 50), keep_ratio=False)
    render_object(obj, Document("62", length_mm=60, objects=[obj]))
    w, h = _dots(20), _dots(10)
    _, size, region = rasterizer.calls[-1]
    assert size == (round(100 * w / 50), round(50 * h / 50))
    assert region == (round(25 * w / 50), 0, w, h)


def test_keep_ratio_fits_vector_into_wrong_frame(rasterizer):
    obj = _vector(20, 20)                        # preview 2:1, frame square
    rendered = render_object(obj, Document("62", length_mm=60, objects=[obj]))
    w = _dots(20)
    _, size, region = rasterizer.calls[-1]
    assert size == (w, round(w / 2)) and region == (0, 0, w, round(w / 2))
    assert rendered.image.size == (w, w)
    assert _ink_rows(rendered.image) == [(w - round(w / 2)) // 2 + round(w / 2) // 2]


def test_vector_rotates_like_images(rasterizer):
    obj = _vector(20, 10, rotation=90)
    rendered = render_object(obj, Document("62", length_mm=60, objects=[obj]))
    assert rendered.image.size == (_dots(10), _dots(20))


def test_without_rasterizer_the_preview_png_is_used():
    obj = _vector(10, 5)
    with_png = render_object(obj, Document("62", length_mm=60, objects=[obj])).image
    plain = ImageObject.from_image(_preview(), 300, "x.png")
    plain.w_mm, plain.h_mm = 10, 5
    assert with_png.tobytes() == render_object(
        plain, Document("62", length_mm=60, objects=[plain])).image.tobytes()


def test_changing_the_rasterizer_drops_cached_results(rasterizer):
    obj = _vector(10, 5)
    doc = Document("62", length_mm=60, objects=[obj])
    render_object(obj, doc)
    render.set_svg_rasterizer(lambda svg, size, region: Image.new("RGB", region[2:], "black"))
    assert _ink_rows(render_object(obj, doc).image) == list(range(_dots(5)))


def test_preview_equals_print_for_vectors(rasterizer):
    obj = _vector(30, 15, x_mm=5, y_mm=5)
    doc = Document("62", length_mm=60, objects=[obj])
    assert Renderer().render(doc, "QL-600").image.tobytes() == render_document(doc).tobytes()


def test_rasterizer_result_of_wrong_size_is_an_error(rasterizer):
    render.set_svg_rasterizer(lambda svg, size, region: Image.new("RGB", (3, 3), "white"))
    obj = _vector(10, 5)
    with pytest.raises(ValueError, match="Vektorbild"):
        render_object(obj, Document("62", length_mm=60, objects=[obj]))


@pytest.mark.parametrize("crop", [(10, 0, 10, 50), (50, 0, 150, 50), (-5, 0, 50, 50)])
def test_invalid_crop_of_a_vector_is_a_clear_error(rasterizer, crop):
    """As in the pixel path: understandable error instead of division by zero or a white image."""
    obj = _vector(10, 5, crop=crop, keep_ratio=False)
    with pytest.raises(ValueError, match="Ausschnitt"):
        render_object(obj, Document("62", length_mm=60, objects=[obj]))


def test_crop_with_keep_ratio_rasterizes_the_fitted_region(rasterizer):
    obj = _vector(20, 10, crop=(25, 0, 75, 50))  # square section in a wide frame
    rendered = render_object(obj, Document("62", length_mm=60, objects=[obj]))
    side = _dots(10)
    _, size, region = rasterizer.calls[-1]
    assert size == (2 * side, side) and region == (round(25 * side / 50), 0, side, side)
    assert rendered.image.size == (_dots(20), side)


def test_limit_resolution_leaves_vectors_alone():
    """The preview is only a scale – shrunk, the section would get coarser (offset)."""
    obj = _vector(1, 0.5)
    assert obj.limit_resolution() is obj


def test_renderer_notices_a_new_rasterizer(rasterizer):
    obj = _vector(10, 5, x_mm=2, y_mm=2)
    doc = Document("62", length_mm=60, objects=[obj])
    renderer = Renderer()
    before = renderer.render(doc, "QL-600").image.tobytes()
    render.set_svg_rasterizer(lambda svg, size, region: Image.new("RGB", region[2:], "black"))
    assert renderer.render(doc, "QL-600").image.tobytes() != before


def test_extreme_enlargement_of_a_tiny_crop_is_refused(rasterizer):
    """Qt would silently drop shapes of a huge sheet – better a clear message."""
    obj = ImageObject.from_image(Image.new("RGB", (1000, 10), "black"), 300, "x.svg",
                                 crop=(0, 0, 1, 1), svg=SVG)
    obj.w_mm = obj.h_mm = 400
    with pytest.raises(ValueError, match="zu stark vergrößert"):
        render_object(obj, Document("62", length_mm=None, objects=[obj]))
    assert not rasterizer.calls
