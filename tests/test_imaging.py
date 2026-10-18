"""Bilder für den Druck: Schwarz/Weiß-Umwandlung und Größenbegrenzung (``imaging``)."""
import struct

import pytest
from PIL import Image

from labelwerk.imaging import MAX_DPI, MAX_PIXELS, limit_size, on_white, to_8bit, to_layers


def _pixels(img: Image.Image) -> list:
    """Pixel einer Zeile von links nach rechts."""
    return [img.getpixel((x, 0)) for x in range(img.width)]


def _gradient() -> Image.Image:
    """Graustufen 0–255 nebeneinander (eine Zeile)."""
    img = Image.new("L", (256, 1))
    img.putdata(list(range(256)))
    return img


def _ink(layer: Image.Image) -> int:
    """Anzahl bedruckter (schwarzer) Punkte einer Ebene."""
    return layer.histogram()[0]


def test_line_mode_is_a_hard_threshold():
    layers = to_layers(_gradient(), "line", 128, False)
    assert list(layers) == ["black"]
    black = layers["black"]
    assert black.mode == "1" and black.size == (256, 1)
    assert [black.getpixel((x, 0)) for x in (0, 127, 128, 255)] == [0, 0, 255, 255]


@pytest.mark.parametrize("threshold, ink", [(0, 0), (1, 1), (128, 128), (200, 200), (255, 255)])
def test_higher_threshold_prints_more(threshold, ink):
    assert _ink(to_layers(_gradient(), "line", threshold, False)["black"]) == ink


def test_invert_swaps_ink_and_paper():
    normal = to_layers(_gradient(), "line", 100, False)["black"]
    inverted = to_layers(_gradient(), "line", 100, True)["black"]
    assert _ink(inverted) == 256 - _ink(normal)
    assert inverted.getpixel((0, 0)) == 255 and inverted.getpixel((255, 0)) == 0


def test_colour_counts_by_brightness():
    img = Image.new("RGB", (2, 1))
    img.putdata([(255, 0, 0), (255, 255, 0)])            # Rot dunkel, Gelb hell
    black = to_layers(img, "line", 128, False)["black"]
    assert [black.getpixel((x, 0)) for x in (0, 1)] == [0, 255]


@pytest.mark.parametrize("gray, low, high", [(128, 0.4, 0.6), (64, 0.7, 0.8), (192, 0.2, 0.3)])
def test_photo_mode_dithers_gray_into_dots(gray, low, high):
    black = to_layers(Image.new("L", (100, 100), gray), "photo", 128, False)["black"]
    assert black.mode == "1"
    assert low <= _ink(black) / 10000 <= high


def test_photo_threshold_darkens_mid_grey_monotonically():
    img = Image.new("L", (100, 100), 128)
    inks = [_ink(to_layers(img, "photo", t, False)["black"]) for t in (0, 64, 128, 192, 255)]
    assert inks == sorted(inks) and len(set(inks)) == len(inks)
    assert inks[0] < 2000 and inks[-1] > 8000


def test_photo_threshold_128_is_plain_dithering():
    img = _gradient().resize((256, 40))
    black = to_layers(img, "photo", 128, False)["black"]
    assert black.tobytes() == img.convert("1", dither=Image.Dither.FLOYDSTEINBERG).tobytes()


@pytest.mark.parametrize("threshold", [0, 1, 64, 128, 192, 254, 255])
def test_photo_keeps_white_and_black(threshold):
    """Weißes Papier bekommt nie Punkte, Schwarz bleibt voll – bei jeder Schwelle."""
    white, black = Image.new("L", (20, 20), 255), Image.new("L", (20, 20), 0)
    assert _ink(to_layers(white, "photo", threshold, False)["black"]) == 0
    assert _ink(to_layers(black, "photo", threshold, False)["black"]) == 400
    assert _ink(to_layers(white, "photo", threshold, True)["black"]) == 400


@pytest.mark.parametrize("mode, threshold, message", [
    ("grau", 128, "Umwandlung"), ("line", -1, "Schwelle"), ("photo", 256, "Schwelle"),
    ("line", 12.5, "Schwelle"), ("line", True, "Schwelle")])
def test_invalid_settings_raise(mode, threshold, message):
    with pytest.raises(ValueError, match=message):
        to_layers(_gradient(), mode, threshold, False)


def test_on_white_flattens_transparency():
    img = Image.new("RGBA", (2, 1))
    img.putdata([(0, 0, 0, 0), (255, 0, 0, 255)])
    flat = on_white(img)
    assert flat.mode == "RGB"
    assert _pixels(flat) == [(255, 255, 255), (255, 0, 0)]


def test_on_white_palette_with_transparency_and_gray():
    pal = Image.new("P", (2, 1))
    pal.putpalette([0, 0, 0, 0, 0, 255])
    pal.putdata([0, 1])
    pal.info["transparency"] = 0
    assert _pixels(on_white(pal)) == [(255, 255, 255), (0, 0, 255)]
    assert on_white(Image.new("L", (1, 1), 7)).getpixel((0, 0)) == (7, 7, 7)
    assert on_white(Image.new("LA", (1, 1), (0, 0))).getpixel((0, 0)) == (255, 255, 255)


def _gray16(mode: str) -> Image.Image:
    """Verlauf 0–65535 in 16 Bit (wie ein 16-Bit-PNG) bzw. 32 Bit (``"I"``)."""
    values = [v * 257 for v in range(256)]
    if mode == "I":
        img = Image.new("I", (256, 1))
        img.putdata(values)
        return img
    order = ">" if mode == "I;16B" else "<"
    return Image.frombytes(mode, (256, 1), struct.pack(f"{order}256H", *values))


@pytest.mark.parametrize("mode", ["I;16", "I;16B", "I"])
def test_16_bit_gray_is_scaled_not_clipped(mode):
    img = _gray16(mode)
    assert _pixels(to_8bit(img)) == list(range(256))
    assert to_8bit(img).mode == "L"
    assert _pixels(on_white(img)) == [(v, v, v) for v in range(256)]


def test_to_8bit_leaves_other_modes_alone():
    img = Image.new("RGB", (2, 2))
    assert to_8bit(img) is img


def test_limit_size_leaves_normal_images_alone():
    img = Image.new("RGB", (600, 300))
    assert limit_size(img, 300) == (img, 300)


def test_limit_size_caps_resolution_keeping_print_size():
    img, dpi = limit_size(Image.new("RGB", (2400, 1200)), 1200)
    assert (img.size, dpi) == ((1200, 600), MAX_DPI)


def test_limit_size_caps_longest_side_keeping_print_size():
    img, dpi = limit_size(Image.new("RGB", (100, MAX_PIXELS + 1000)), 300)
    assert img.height == MAX_PIXELS
    assert img.height / dpi == pytest.approx((MAX_PIXELS + 1000) / 300, rel=1e-3)
    assert img.width / dpi == pytest.approx(100 / 300, rel=0.02)
