import pytest
from PIL import Image

from labelwerk.files import load_file


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
