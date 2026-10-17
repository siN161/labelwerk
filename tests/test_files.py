import pytest
from PIL import Image

from labelwerk.files import crop, load_file


def _page(w=600, h=300):
    img = Image.new("L", (w, h), 255)
    img.paste(0, (100, 100, 200, 200))
    return img


def test_pdf_is_rendered_at_300_dpi(tmp_path):
    path = tmp_path / "seite.pdf"
    _page().save(path, "PDF", resolution=300)
    img = load_file(path)
    assert img.mode == "L"
    assert abs(img.width - 600) <= 1 and abs(img.height - 300) <= 1


def test_pdf_page_out_of_range(tmp_path):
    path = tmp_path / "seite.pdf"
    _page().save(path, "PDF", resolution=300)
    with pytest.raises(ValueError, match="nur 1 Seite"):
        load_file(path, page=2)


def test_png_with_600_dpi_keeps_size_in_mm(tmp_path):
    path = tmp_path / "bild.png"
    _page().save(path, dpi=(600, 600))
    assert load_file(path).size == (300, 150)


def test_png_without_dpi_counts_as_300_dpi(tmp_path):
    path = tmp_path / "bild.png"
    _page().save(path)
    assert load_file(path).size == (600, 300)


def test_transparency_becomes_white(tmp_path):
    path = tmp_path / "leer.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
    assert load_file(path).getextrema() == (255, 255)


def test_unsupported_file_type(tmp_path):
    with pytest.raises(ValueError, match="nicht unterstützt"):
        load_file(tmp_path / "notiz.txt")


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="nicht gefunden"):
        load_file(tmp_path / "fehlt.pdf")


from PIL import ImageDraw

RECT = (100, 80, 1163, 635)   # Kreuzungspunkte der Marken (90 × 47 mm)


def _with_marks(corners=("tl", "tr", "bl", "br"), dotted=False):
    img = Image.new("L", (1300, 750), 255)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = RECT
    points = {"tl": (x0, y0), "tr": (x1, y0), "bl": (x0, y1), "br": (x1, y1)}
    for name in corners:
        x, y = points[name]
        for i in range(-30, 31):
            if dotted and i % 4 >= 2:
                continue
            d.point((x + i, y), 0)
            d.point((x, y + i), 0)
    d.rectangle((300, 300, 700, 400), fill=0)   # Inhalt
    return img


def test_crop_to_solid_marks():
    w, h = crop(_with_marks()).size
    assert abs(w - (RECT[2] - RECT[0])) <= 4
    assert abs(h - (RECT[3] - RECT[1])) <= 4


def test_crop_to_dotted_marks():
    w, h = crop(_with_marks(dotted=True)).size
    assert abs(w - (RECT[2] - RECT[0])) <= 4
    assert abs(h - (RECT[3] - RECT[1])) <= 4


def test_crop_removes_marks_completely():
    cropped = crop(_with_marks())
    border = [cropped.crop(b) for b in ((0, 0, cropped.width, 1), (0, 0, 1, cropped.height))]
    assert all(b.getextrema()[0] == 255 for b in border)


def test_without_all_four_marks_crops_to_content():
    img = _with_marks(corners=("tl", "tr", "bl"))
    bbox = img.point(lambda v: 255 if v < 128 else 0).getbbox()
    assert crop(img).size == (bbox[2] - bbox[0], bbox[3] - bbox[1])


def test_logo_in_corner_is_not_a_mark():
    img = Image.new("L", (800, 500), 255)
    d = ImageDraw.Draw(img)
    for x, y in ((50, 50), (650, 50), (50, 350), (650, 350)):
        d.rectangle((x, y, x + 99, y + 99), fill=0)   # dicke Blöcke in allen Ecken
    assert crop(img).size == (700, 400)


def test_crop_empty_page():
    with pytest.raises(ValueError, match="keinen druckbaren Inhalt"):
        crop(Image.new("L", (100, 100), 255))
