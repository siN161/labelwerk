"""Vector images in the GUI (stage 3d-2c): Qt rasterises SVG at frame size – SVG files
from FROM FILE … also stay sharp when enlarged."""
import pytest
from PIL import Image

from labelwerk import render
from labelwerk.document import Document, TextObject
from labelwerk.gui import image_import
from labelwerk.gui.image_import import rasterize_svg
from labelwerk.gui.main_window import MainWindow
from labelwerk.settings import Settings

# line 1 unit thick straight across the middle of a 100 × 50 sheet
LINE = (b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50">'
        b'<rect x="0" y="24.5" width="100" height="1" fill="black"/></svg>')


@pytest.fixture
def window(qtbot):
    win = MainWindow(doc=Document("62", length_mm=60, objects=[TextObject("Eins", x_mm=2, y_mm=2)]),
                     settings=Settings(check_media_on_start=False))
    qtbot.addWidget(win)
    win.show()
    return win


def _gray_rows(img: Image.Image) -> list[int]:
    """Rows that are darker than white anywhere."""
    gray = img.convert("L")
    return [y for y in range(gray.height)
            if gray.crop((0, y, gray.width, y + 1)).getextrema()[0] < 250]


def test_rasterize_svg_renders_the_whole_sheet_scaled(qapp):
    img = rasterize_svg(LINE, (1000, 500), (0, 0, 1000, 500))
    assert img.mode == "RGB" and img.size == (1000, 500)
    assert _gray_rows(img) == list(range(245, 255))          # 10 pixels thick, sharp


def test_rasterize_svg_region_equals_crop_of_the_sheet(qapp):
    whole = rasterize_svg(LINE, (400, 200), (0, 0, 400, 200))
    part = rasterize_svg(LINE, (400, 200), (100, 80, 150, 60))
    assert part.tobytes() == whole.crop((100, 80, 250, 140)).tobytes()


def test_rasterize_svg_rejects_broken_svg(qapp):
    with pytest.raises(ValueError, match="Vektorbild"):
        rasterize_svg(b"<svg", (10, 10), (0, 0, 10, 10))


def test_rasterize_svg_rejects_links_to_other_files(qapp):
    linked = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
              b'width="10" height="10"><image xlink:href="bild.png" width="10" height="10"/></svg>')
    with pytest.raises(ValueError, match="andere Dateien"):
        rasterize_svg(linked, (10, 10), (0, 0, 10, 10))


def test_window_registers_the_qt_rasterizer(window):
    assert render._svg_rasterizer is image_import.rasterize_svg


def test_svg_file_becomes_a_vector_image(window, tmp_path):
    path = tmp_path / "linie.svg"
    path.write_bytes(LINE)
    window.ask_image_file = lambda: str(path)
    window.panel("image").from_file.click()
    obj = window.doc.objects[1]
    assert obj.svg == LINE
    assert obj.image().size == (round(100 * 300 / 96), round(50 * 300 / 96))   # preview 300 dpi


BARS = (b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50">'
        b'<rect x="0" y="10.3" width="100" height="9.4" fill="black"/>'
        b'<rect x="0" y="30.3" width="100" height="9.4" fill="black"/></svg>')


def _soft_rows(img: Image.Image) -> int:
    """Rows with greys (edge fringe) in the middle of the image."""
    gray = img.convert("L")
    column = [gray.getpixel((gray.width // 2, y)) for y in range(gray.height)]
    return sum(30 < v < 225 for v in column)


def test_enlarged_svg_stays_sharp(window, tmp_path):
    """4× as large: the vector image is rasterised anew – at each of the four edges at most one
    grey row; the upscaled preview would have a wide fringe."""
    path = tmp_path / "balken.svg"
    path.write_bytes(BARS)
    window.ask_image_file = lambda: str(path)
    window.panel("image").from_file.click()
    obj = window.doc.objects[1]
    size = (round(obj.w_mm * 4 * 300 / 25.4), round(obj.h_mm * 4 * 300 / 25.4))
    crop = tuple(obj.crop)
    vector = render._vector_source(obj.svg, obj.png, crop, size, obj.keep_ratio)
    scaled = render._scaled_source(obj.png, crop, size, obj.keep_ratio)
    assert _soft_rows(vector) <= 4 < _soft_rows(scaled)


def test_window_renders_vectors_in_frame_size(window, tmp_path):
    """The canvas takes the vector path: after enlarging, it is rasterised at frame size."""
    path = tmp_path / "balken.svg"
    path.write_bytes(BARS)
    window.ask_image_file = lambda: str(path)
    window.panel("image").from_file.click()
    calls = []

    def spy(svg, size, region):
        calls.append(region[2:])
        return rasterize_svg(svg, size, region)
    render.set_svg_rasterizer(spy)
    obj = window.doc.objects[1]
    obj.w_mm, obj.h_mm = obj.w_mm * 4, obj.h_mm * 4
    window.render_now()
    assert calls[-1] == (round(obj.w_mm * 300 / 25.4), round(obj.h_mm * 300 / 25.4))


def test_svg_preview_is_the_same_raster_as_the_vector(window, tmp_path):
    """Preview PNG and raster come from the same bytes – crop and print match."""
    path = tmp_path / "balken.svg"
    path.write_bytes(BARS)
    image, _ = image_import.load(path)
    assert image.tobytes() == rasterize_svg(BARS, image.size, (0, 0, *image.size)).tobytes()


def test_svg_with_linked_file_is_inserted_as_pixel_image(window, tmp_path):
    """References to other files apply only next to the SVG – as a pixel image the image stays in."""
    Image.new("RGB", (40, 40), "black").save(tmp_path / "bild.png")
    path = tmp_path / "mit-bild.svg"
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" '
                    'xmlns:xlink="http://www.w3.org/1999/xlink" width="96" height="96">'
                    '<image xlink:href="bild.png" x="0" y="0" width="96" height="96"/></svg>')
    window.ask_image_file = lambda: str(path)
    window.panel("image").from_file.click()
    obj = window.doc.objects[1]
    assert obj.svg is None
    assert obj.image().convert("L").getextrema()[0] == 0      # the linked image is in


@pytest.mark.parametrize("href", ["#teil", "data:image/png;base64,iVBORw0KGgo="])
def test_internal_references_stay_vector(tmp_path, href):
    path = tmp_path / "intern.svg"
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" '
                    f'xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="{href}"/></svg>')
    assert image_import.load_vector(path) == path.read_bytes()


def test_load_vector_only_for_svg(tmp_path):
    path = tmp_path / "bild.png"
    Image.new("RGB", (4, 4)).save(path)
    assert image_import.load_vector(path) is None


def test_copy_paste_and_undo_keep_the_vector(window):
    from labelwerk.document import ImageObject
    obj = ImageObject.from_image(Image.new("RGB", (100, 50), "black"), 96, "Test", svg=LINE)
    window._insert_images([obj], None, [])
    window.copy_selected()
    window.paste()
    assert [o.svg for o in window.doc.objects[1:]] == [LINE, LINE]
    window.undo()
    assert [o.svg for o in window.doc.objects[1:]] == [LINE]
    window.redo()
    assert [o.svg for o in window.doc.objects[1:]] == [LINE, LINE]
