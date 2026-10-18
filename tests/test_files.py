import pytest
from PIL import Image, ImageDraw

from labelwerk.files import (NOT_WHITE, crop, crop_box, fit_to_label, ink_box, load_file,
                             load_image)
from labelwerk.imaging import MAX_PIXELS


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


def test_crop_to_solid_marks_trims_dead_space():
    cropped = crop(_with_marks())
    assert cropped.size == (401, 101)            # nur der Inhalt, ohne Marken und Leerraum
    assert cropped.getextrema() == (0, 0)


def test_crop_to_dotted_marks_trims_dead_space():
    cropped = crop(_with_marks(dotted=True))
    assert cropped.size == (401, 101)
    assert cropped.getextrema() == (0, 0)


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


def _motif(w_mm, h_mm):
    img = Image.new("L", (round(w_mm * 300 / 25.4), round(h_mm * 300 / 25.4)), 0)
    return img


def test_wide_motif_is_rotated_onto_endless_tape():
    out = fit_to_label(_motif(90, 47), "62")
    assert out.size == (696, 1063 + 2 * 12)


def test_small_motif_is_not_rotated():
    out = fit_to_label(_motif(40, 20), "62")
    assert out.size == (696, 236 + 2 * 12)


def test_motif_is_centered_and_not_scaled():
    out = fit_to_label(_motif(40, 20), "62")
    bbox = out.point(lambda v: 255 if v < 128 else 0).getbbox()
    assert (bbox[2] - bbox[0], bbox[3] - bbox[1]) == (472, 236)
    assert bbox[0] == (696 - 472) // 2


def test_short_motif_gets_minimum_length():
    assert fit_to_label(_motif(40, 2), "62").height == 150


def test_too_large_motif_raises_with_mm():
    with pytest.raises(ValueError, match=r"120,0 × 70,0 mm.*--fit"):
        fit_to_label(_motif(120, 70), "62")


def test_fit_shrinks_and_keeps_aspect_ratio():
    out = fit_to_label(_motif(120, 70), "62", fit=True)
    bbox = out.point(lambda v: 255 if v < 128 else 0).getbbox()
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    assert out.width == 696 and w == 696
    assert abs(h / w - 120 / 70) < 0.01          # gedreht, da so größer


def test_die_cut_label_has_exact_size():
    assert fit_to_label(_motif(40, 20), "62x29").size == (696, 271)


def test_result_is_accepted_by_printer_driver():
    from labelwerk.printer import build_instructions
    data = build_instructions(fit_to_label(_motif(90, 47), "62"), "62")
    assert data.endswith(b"\x1a")


def test_corrupt_pdf_gives_clear_error(tmp_path):
    path = tmp_path / "kaputt.pdf"
    path.write_bytes(b"kein pdf")
    with pytest.raises(ValueError, match="kann nicht gelesen werden"):
        load_file(path)


def test_corrupt_png_gives_clear_error(tmp_path):
    path = tmp_path / "kaputt.png"
    path.write_bytes(b"kein png")
    with pytest.raises(ValueError, match="kann nicht gelesen werden"):
        load_file(path)


@pytest.mark.parametrize("load", [load_file, load_image])
def test_read_errors_have_german_reasons(tmp_path, load):
    """Kein englischer Fehlertext (Errno, PDFium, Pillow) in der Meldung."""
    (tmp_path / "ordner.png").mkdir()
    (tmp_path / "kaputt.pdf").write_bytes(b"%PDF-1.4 kaputt")
    (tmp_path / "kaputt.png").write_bytes(b"kein png")
    cases = [("ordner.png", "ist ein Ordner"), ("kaputt.pdf", "keine gültige PDF-Datei"),
             ("kaputt.png", "kein lesbares Bild")]
    for name, reason in cases:
        with pytest.raises(ValueError) as info:
            load(tmp_path / name)
        message = str(info.value)
        assert message == f"Datei kann nicht gelesen werden: {name} ({reason})"


def test_unreadable_file_without_permission(tmp_path, monkeypatch):
    path = tmp_path / "gesperrt.png"
    _page().save(path)

    def denied(*args, **kwargs):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(Image, "open", denied)
    with pytest.raises(ValueError, match=r"gesperrt.png \(keine Leserechte\)$"):
        load_image(path)
    with pytest.raises(ValueError, match=r"gesperrt.png \(keine Leserechte\)$"):
        load_file(path)


def test_truncated_image_has_german_reason(tmp_path):
    import io
    buffer = io.BytesIO()
    Image.effect_noise((200, 200), 50).convert("RGB").save(buffer, "JPEG")
    path = tmp_path / "halb.jpg"
    path.write_bytes(buffer.getvalue()[:2000])
    with pytest.raises(ValueError, match=r"halb.jpg \(Datei ist beschädigt oder unvollständig\)$"):
        load_image(path)


def test_broken_image_data_has_german_reason(tmp_path):
    import io
    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), "red").save(buffer, "PNG")
    data = bytearray(buffer.getvalue())
    data[60:80] = b"\xff" * 20                            # Bilddaten im IDAT zerstört
    path = tmp_path / "kaputt2.png"
    path.write_bytes(bytes(data))
    with pytest.raises(ValueError, match=r"kaputt2.png \(Datei ist beschädigt oder unvollständig\)$"):
        load_image(path)


def test_encrypted_pdf_has_own_reason(tmp_path, monkeypatch):
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    path = tmp_path / "geheim.pdf"
    _page().save(path, "PDF", resolution=300)

    def locked(*args, **kwargs):
        raise pdfium.PdfiumError("Failed to load document (PDFium: Incorrect password error).",
                                 raw.FPDF_ERR_PASSWORD)
    monkeypatch.setattr(pdfium, "PdfDocument", locked)
    for load in (load_file, load_image):
        with pytest.raises(ValueError, match=r"geheim.pdf \(PDF ist verschlüsselt\)$"):
            load(path)


def test_page_below_one_has_own_message(tmp_path):
    path = tmp_path / "seite.pdf"
    _page().save(path, "PDF", resolution=300)
    with pytest.raises(ValueError, match="mindestens 1"):
        load_file(path, page=0)


def _corner_motif(w_mm, h_mm):
    """Weißes Motiv mit schwarzem Block oben links – zeigt die Drehrichtung."""
    img = Image.new("L", (round(w_mm * 300 / 25.4), round(h_mm * 300 / 25.4)), 255)
    img.paste(0, (0, 0, 50, 50))
    return img


def _ink_box(img):
    return img.point(lambda v: 255 if v < 128 else 0).getbbox()


def test_auto_rotation_is_counterclockwise():
    box = _ink_box(fit_to_label(_corner_motif(90, 47), "62"))
    assert box[0] < 348 and box[1] > 500         # oben links -> unten links


def test_rotate_90_is_clockwise():
    box = _ink_box(fit_to_label(_corner_motif(90, 47), "62", rotate=90))
    assert box[0] > 348 and box[1] < 100         # oben links -> oben rechts


def test_rotate_180_turns_upside_down():
    box = _ink_box(fit_to_label(_corner_motif(40, 20), "62", rotate=180))
    assert box[0] > 348 and box[1] > 130         # oben links -> unten rechts


def test_rotate_0_too_wide_suggests_fit():
    with pytest.raises(ValueError, match="--fit"):
        fit_to_label(_motif(90, 47), "62", rotate=0)


def test_rotate_0_with_fit_keeps_orientation():
    out = fit_to_label(_motif(90, 47), "62", rotate=0, fit=True)
    box = _ink_box(out)
    w, h = box[2] - box[0], box[3] - box[1]
    assert w == 696
    assert abs(h / w - 47 / 90) < 0.01           # quer wie im PDF, nur verkleinert


def test_invalid_rotation():
    with pytest.raises(ValueError, match="Drehung"):
        fit_to_label(_motif(40, 20), "62", rotate=45)


# --- Bilder als Objekt (load_image, crop_box) -----------------------------------------
def _pixels(img: Image.Image) -> list:
    """Pixel einer Zeile von links nach rechts."""
    return [img.getpixel((x, 0)) for x in range(img.width)]


def _colour(w=60, h=30):
    """Farbbild: links rot, rechts weiß, schwarzer Punkt oben links."""
    img = Image.new("RGB", (w, h), "white")
    img.paste((255, 0, 0), (0, 0, w // 2, h))
    img.putpixel((0, 0), (0, 0, 0))
    return img


@pytest.mark.parametrize("suffix, kwargs, expected_dpi", [
    (".png", {}, 300), (".gif", {}, 300), (".webp", {"lossless": True}, 300),
    (".jpg", {"quality": 100}, 300),
    (".bmp", {}, 96)])                                    # BMP hat immer eine Angabe (Pillow: 96)
def test_load_image_keeps_colour_and_size(tmp_path, suffix, kwargs, expected_dpi):
    path = tmp_path / f"bild{suffix}"
    _colour().save(path, **kwargs)
    img, dpi = load_image(path)
    assert img.mode == "RGB" and img.size == (60, 30)
    assert dpi == pytest.approx(expected_dpi, abs=0.1)    # ohne Angabe 300 dpi
    r, g, b = img.getpixel((40, 15))
    assert min(r, g, b) > 240                             # weiß bleibt weiß
    r, g, b = img.getpixel((10, 15))
    assert r > 200 and g < 60 and b < 60                  # rot bleibt rot


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".bmp"])
def test_load_image_reports_dpi_without_resampling(tmp_path, suffix):
    path = tmp_path / f"bild{suffix}"
    _colour().save(path, dpi=(600, 600))
    img, dpi = load_image(path)
    assert img.size == (60, 30)
    assert dpi == pytest.approx(600, abs=0.5)


def test_load_image_with_dpi_ignores_the_file_resolution(tmp_path):
    """Ungleiche Dateiauflösung (72 × 144) streckt nicht, hohe (1200) verkleinert nicht."""
    path = tmp_path / "bild.png"
    Image.new("RGB", (200, 100), "white").save(path, dpi=(72, 144))
    img, dpi = load_image(path, dpi=300)
    assert img.size == (200, 100) and dpi == pytest.approx(300)
    Image.new("RGB", (200, 100), "white").save(path, dpi=(1200, 1200))
    img, dpi = load_image(path, dpi=300)
    assert img.size == (200, 100) and dpi == pytest.approx(300)


def test_load_image_with_dpi_still_limits_huge_images(tmp_path):
    path = tmp_path / "riesig.png"
    Image.new("RGB", (MAX_PIXELS * 2, 40), "white").save(path, dpi=(72, 144))
    img, dpi = load_image(path, dpi=300)
    assert img.size == (MAX_PIXELS, 20) and dpi == pytest.approx(150)


def test_load_image_follows_exif_orientation(tmp_path):
    path = tmp_path / "handy.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6                                      # Kamera hochkant: 90° drehen
    _colour().save(path, exif=exif)
    img, _ = load_image(path)
    assert img.size == (30, 60)


def test_load_image_gif_uses_first_frame(tmp_path):
    path = tmp_path / "animiert.gif"
    frames = [Image.new("RGB", (8, 8), c) for c in ("black", "white", "white")]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    img, _ = load_image(path)
    assert img.getpixel((4, 4)) == (0, 0, 0)


def test_load_image_transparency_becomes_white(tmp_path):
    path = tmp_path / "frei.png"
    img = Image.new("RGBA", (4, 1), (0, 0, 0, 0))
    img.putpixel((3, 0), (0, 0, 255, 255))
    img.save(path)
    loaded, _ = load_image(path)
    assert _pixels(loaded) == [(255, 255, 255)] * 3 + [(0, 0, 255)]


def _pdf(path, pages):
    """PDF aus Pillow, 300 dpi; Seite i hat einen schwarzen Block bei x = 100 · i."""
    imgs = []
    for i in range(pages):
        img = Image.new("RGB", (600, 300), "white")
        img.paste((0, 0, 0), (100 * i, 0, 100 * i + 50, 50))
        imgs.append(img)
    imgs[0].save(path, "PDF", resolution=300, save_all=True, append_images=imgs[1:])


def test_load_image_pdf_page_selection(tmp_path):
    path = tmp_path / "zwei.pdf"
    _pdf(path, 2)
    first, dpi = load_image(path)
    second, _ = load_image(path, page=2)
    assert dpi == 300 and first.mode == "RGB"
    assert abs(first.width - 600) <= 1 and abs(first.height - 300) <= 1
    assert first.getpixel((25, 25)) == (0, 0, 0) and first.getpixel((125, 25)) != (0, 0, 0)
    assert second.getpixel((125, 25)) == (0, 0, 0) and second.getpixel((25, 25)) != (0, 0, 0)


@pytest.mark.parametrize("page, message", [(3, "nur 2 Seite"), (0, "mindestens 1")])
def test_load_image_pdf_missing_page(tmp_path, page, message):
    path = tmp_path / "zwei.pdf"
    _pdf(path, 2)
    with pytest.raises(ValueError, match=message):
        load_image(path, page=page)


def test_load_image_huge_pdf_page_is_capped(tmp_path):
    path = tmp_path / "plakat.pdf"
    Image.new("RGB", (100, 50), "white").save(path, "PDF", resolution=2)   # 50 × 25 Zoll
    img, dpi = load_image(path)
    assert max(img.size) <= MAX_PIXELS
    assert img.width / dpi == pytest.approx(50, rel=0.01)                  # Druckgröße bleibt


def test_load_image_huge_raster_is_capped(tmp_path):
    path = tmp_path / "lang.png"
    Image.new("RGB", (MAX_PIXELS * 2, 10), "white").save(path)
    img, dpi = load_image(path)
    assert img.width == MAX_PIXELS and dpi == pytest.approx(150)


@pytest.mark.parametrize("name", ["logo.svg", "notiz.txt", "ohne"])
def test_load_image_unsupported_type(tmp_path, name):
    (tmp_path / name).write_text("x")
    with pytest.raises(ValueError, match="nicht unterstützt"):
        load_image(tmp_path / name)


def test_load_image_missing_and_broken(tmp_path):
    with pytest.raises(FileNotFoundError, match="nicht gefunden"):
        load_image(tmp_path / "fehlt.png")
    (tmp_path / "kaputt.png").write_bytes(b"kein Bild")
    with pytest.raises(ValueError, match="kann nicht gelesen werden"):
        load_image(tmp_path / "kaputt.png")


@pytest.mark.parametrize("img", [
    _with_marks(), _with_marks(dotted=True), _with_marks(corners=("tl", "tr", "bl")),
    _page()], ids=["Marken", "gepunktet", "drei Marken", "Inhalt"])
def test_crop_box_is_what_crop_cuts(img):
    box = crop_box(img)
    assert img.crop(box).tobytes() == crop(img).tobytes()
    assert crop_box(img.convert("RGB")) == box            # Farbe: dieselbe Logik


def test_crop_box_scales_marks_with_resolution():
    img = _with_marks()
    big = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    l, t, r, b = crop_box(img)
    assert crop_box(big, dpi=600) == pytest.approx((2 * l, 2 * t, 2 * r, 2 * b), abs=2)


def test_crop_box_without_content_is_none():
    assert crop_box(Image.new("RGB", (10, 10), "white")) is None
    assert crop_box(Image.new("RGB", (10, 10), "white"), ink=NOT_WHITE) is None
    assert crop_box(Image.new("RGB", (10, 10), (250, 250, 250)), ink=NOT_WHITE) is None
    with pytest.raises(ValueError, match="keinen druckbaren Inhalt"):
        crop(Image.new("L", (10, 10), 255))                # print-file: Meldung wie bisher


def test_crop_box_not_white_keeps_light_photo_nearly_whole():
    photo = Image.new("RGB", (300, 200), (200, 200, 200))   # hell, ohne Weiß
    photo.paste((0, 0, 0), (140, 90, 160, 110))
    assert crop_box(photo) == (140, 90, 160, 110)         # Schwelle 128: nur der Punkt
    assert crop_box(photo, ink=NOT_WHITE) == (0, 0, 300, 200)


def test_crop_box_not_white_finds_yellow_logo():
    logo = Image.new("RGB", (300, 300), "white")
    logo.paste((255, 220, 0), (50, 60, 250, 240))
    assert crop_box(logo) is None                         # Gelb ist heller als 128
    assert crop_box(logo, ink=NOT_WHITE) == (50, 60, 250, 240)


def test_crop_box_not_white_finds_marks_despite_light_elements():
    """A4-Seite (wie eine Internetmarke): Marken um den Code, weiter unten eine hellgraue
    Textzeile – die Marken liegen trotzdem außen (gesucht auf der Maske mit ``INK``)."""
    page = Image.new("RGB", (2480, 3508), "white")
    d = ImageDraw.Draw(page)
    x0, y0, x1, y1 = (300, 400, 1363, 955)                 # 90 × 47 mm
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        d.line((x - 30, y, x + 30, y), fill="black")
        d.line((x, y - 30, x, y + 30), fill="black")
    for row in range(10):                                  # Code (Schachbrett)
        for col in range(10):
            if (row + col) % 2 == 0:
                d.rectangle((500 + 20 * col, 600 + 20 * row, 519 + 20 * col, 619 + 20 * row),
                            fill="black")
    d.rectangle((300, 2000, 1800, 2030), fill=(200, 200, 200))   # hellgraue Textzeile
    code = (500, 600, 700, 800)
    assert crop_box(page) == code
    assert crop_box(page, ink=NOT_WHITE) == code


def test_crop_box_not_white_keeps_light_parts_between_marks():
    img = _with_marks().convert("RGB")
    ImageDraw.Draw(img).rectangle((200, 500, 249, 549), fill=(220, 220, 220))   # hell, innen
    assert crop_box(img) == (300, 300, 701, 401)
    assert crop_box(img, ink=NOT_WHITE) == (200, 300, 701, 550)


@pytest.mark.parametrize("ink", [128, NOT_WHITE])
def test_crop_box_flattens_transparency_first(ink):
    rgba = Image.new("RGBA", (100, 100), (0, 0, 0, 0))     # durchsichtiges Schwarz
    rgba.paste((0, 0, 0, 255), (40, 30, 60, 70))
    assert crop_box(rgba, ink=ink) == (40, 30, 60, 70)
    pal = rgba.convert("P")
    pal.info["transparency"] = pal.getpixel((0, 0))
    assert crop_box(pal, ink=ink) == (40, 30, 60, 70)


def _png16(path, dpi=None):
    """16-Bit-Graustufen-PNG mit Verlauf 0–65535 (256 × 1)."""
    img = Image.new("I;16", (256, 1))
    img.putdata([v * 257 for v in range(256)])
    img.save(path, **({"dpi": dpi} if dpi else {}))


def test_load_image_scales_16_bit_gray(tmp_path):
    _png16(tmp_path / "tief.png")
    img, _ = load_image(tmp_path / "tief.png")
    assert _pixels(img) == [(v, v, v) for v in range(256)]


def test_load_file_scales_16_bit_gray(tmp_path):
    _png16(tmp_path / "tief.png")
    assert _pixels(load_file(tmp_path / "tief.png")) == list(range(256))


def test_load_image_rounds_dpi_from_file(tmp_path):
    path = tmp_path / "bild.png"
    _colour().save(path, dpi=(300, 300))                  # PNG speichert Punkte je Meter
    assert Image.open(path).info["dpi"][0] != 300
    assert load_image(path)[1] == 300


def test_load_image_anisotropic_dpi_keeps_print_size(tmp_path):
    path = tmp_path / "fax.png"
    Image.new("RGB", (204, 98), "white").save(path, dpi=(204, 98))   # 1 × 1 Zoll
    img, dpi = load_image(path)
    assert dpi == pytest.approx(204, abs=0.02) and img.size == (204, 204)


def test_load_image_anisotropic_dpi_limits_before_resizing(tmp_path, monkeypatch):
    path = tmp_path / "gross.png"
    Image.new("RGB", (2400, 600), "white").save(path, dpi=(1200, 300))   # 2 × 2 Zoll
    sizes = []
    original = Image.Image.resize

    def spy(self, size, *args, **kwargs):
        sizes.append(tuple(size))
        return original(self, size, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "resize", spy)
    img, dpi = load_image(path)
    assert img.size == (1200, 1200) and dpi == 600
    assert all(w <= 1200 and h <= 1200 for w, h in sizes)      # nie erst auf 2400 × 2400 hoch


def test_load_image_anisotropic_dpi_follows_exif_rotation(tmp_path):
    path = tmp_path / "handy.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6                                      # hochkant: 90° drehen
    Image.new("RGB", (100, 200), "white").save(path, exif=exif, dpi=(100, 200))  # 1 × 1 Zoll
    img, dpi = load_image(path)
    assert dpi == 200 and img.size == (200, 200)


def test_ink_box_is_everything_not_white_without_mark_detection():
    img = Image.new("L", (200, 100), 255)
    img.paste(0, (10, 10, 12, 12))             # vier Ecken wie Schnittmarken …
    img.paste(0, (188, 10, 190, 12))
    img.paste(0, (10, 88, 12, 90))
    img.paste(0, (188, 88, 190, 90))
    assert ink_box(img) == (10, 10, 190, 90)    # … zählen hier als Inhalt (crop_box schnitte innen)


def test_ink_box_threshold_and_empty():
    img = Image.new("RGB", (50, 50), "white")
    assert ink_box(img) is None
    img.paste((251, 251, 251), (5, 5, 20, 20))   # fast weiß: Papier
    assert ink_box(img) is None
    img.paste((249, 249, 249), (5, 5, 20, 20))
    assert ink_box(img) == (5, 5, 20, 20)


def test_postscript_disguised_as_png_is_refused_without_ghostscript(tmp_path, monkeypatch):
    """Pillow erkennt das Format am Inhalt – EPS liefe sonst durch Ghostscript."""
    import subprocess
    for name in ("Popen", "call", "check_call", "check_output", "run"):
        monkeypatch.setattr(subprocess, name, lambda *a, **k: pytest.fail("Ghostscript gestartet"))
    path = tmp_path / "bild.png"
    path.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 30 30\nshowpage\n%%EOF\n")
    with pytest.raises(ValueError, match="kein lesbares Bild"):
        load_image(path)
    with pytest.raises(ValueError, match="kein lesbares Bild"):
        load_file(path)
