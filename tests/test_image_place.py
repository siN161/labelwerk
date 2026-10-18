"""Bild-Objekt einfügen und einstellen (Etappe 3d-2a, ohne Qt): Größe 1:1, Platz beim
Einfügen, Zuschnitt umschalten, Seitenverhältnis."""
import pytest
from PIL import Image

from labelwerk import files, layout
from labelwerk.document import Document, ImageObject
from labelwerk.imaging import MAX_PIXELS
from labelwerk.layout import Rect


def _image(w=600, h=300, dpi=300, crop=None, **kw) -> ImageObject:
    obj = ImageObject.from_image(Image.new("RGB", (w, h), "white"), dpi, "a.png", crop=crop)
    for key, value in kw.items():
        setattr(obj, key, value)
    return obj


# --- Modell: Auflösung, Ausschnitt, Größe 1:1 -----------------------------------------
def test_from_image_keeps_dpi_for_one_to_one():
    obj = _image(dpi=150)
    assert obj.dpi == 150
    assert obj.box() == (0, 0, 600, 300)
    assert obj.natural_mm() == pytest.approx((101.6, 50.8))


def test_natural_size_follows_crop():
    obj = _image(crop=(60, 30, 360, 180))
    assert obj.box() == (60, 30, 360, 180)
    assert obj.natural_mm() == pytest.approx((25.4, 12.7))


def test_limited_image_keeps_its_print_size():
    big = ImageObject.from_image(Image.new("RGB", (2 * MAX_PIXELS, 100), "white"), 300, "a.png")
    assert big.dpi == pytest.approx(150)
    assert big.natural_mm() == pytest.approx((big.w_mm, big.h_mm))


def test_page_count_of_pdf(tmp_path):
    path = tmp_path / "zwei.pdf"
    pages = [Image.new("RGB", (100, 100), "white") for _ in range(2)]
    pages[0].save(path, save_all=True, append_images=pages[1:], resolution=72)
    assert files.page_count(path) == 2


def test_page_count_of_unreadable_pdf_is_a_clear_error(tmp_path):
    path = tmp_path / "kaputt.pdf"
    path.write_bytes(b"kein pdf")
    with pytest.raises(ValueError, match="kann nicht gelesen werden"):
        files.page_count(path)


# --- Einfügen: Platz und Größe -------------------------------------------------------
AREA = Rect(1.5, 1.0, 59.0, 38.0)          # z. B. 62 mm × 40 mm, feste Länge


def test_insert_frame_centres_image_one_to_one():
    rect, factor = layout.insert_frame(Document("62", length_mm=40), "QL-600", AREA, (20, 10))
    assert factor == 1
    assert (rect.w, rect.h) == (20, 10)
    assert (rect.cx, rect.cy) == pytest.approx((AREA.cx, AREA.cy))


def test_insert_frame_shrinks_large_images_proportionally():
    rect, factor = layout.insert_frame(Document("62", length_mm=40), "QL-600", AREA, (118, 19))
    assert factor == pytest.approx(0.5)
    assert (rect.w, rect.h) == pytest.approx((59, 9.5))
    assert (rect.x, rect.cy) == pytest.approx((AREA.x, AREA.cy))


def test_insert_frame_at_point_stays_inside_area():
    doc = Document("62", length_mm=40)
    rect, _ = layout.insert_frame(doc, "QL-600", AREA, (20, 10), at=(30, 20))
    assert (rect.cx, rect.cy) == pytest.approx((30, 20))
    rect, _ = layout.insert_frame(doc, "QL-600", AREA, (20, 10), at=(58, 0))
    assert (rect.right, rect.y) == pytest.approx((AREA.right, AREA.y))


def test_insert_frame_on_growing_tape_only_limits_across():
    doc = Document("62", length_mm=None)                     # Endlos, automatische Länge
    area = Rect(1.5, 1.0, 59.0, 10.0)
    rect, factor = layout.insert_frame(doc, "QL-600", area, (40, 80))
    assert factor == 1 and (rect.w, rect.h) == (40, 80)
    assert rect.y == pytest.approx(area.y)                   # nicht vor den Anfang
    assert rect.cx == pytest.approx(area.cx)
    rect, factor = layout.insert_frame(doc, "QL-600", area, (40, 5000))
    assert factor < 1 and rect.h < 1000                      # höchstens die größte Länge


# --- Einfügen: lieber drehen als verkleinern (wie print-file --rotate auto) --------------
def test_insert_placement_keeps_fitting_image_unturned():
    rect, rotation, factor = layout.insert_placement(Document("62", length_mm=40), "QL-600",
                                                     AREA, (20, 10))
    assert (rotation, factor) == (0, 1)
    assert (rect.w, rect.h) == (20, 10)
    assert (rect.cx, rect.cy) == pytest.approx((AREA.cx, AREA.cy))


def test_insert_placement_turns_image_that_fits_only_turned():
    doc = Document("62", length_mm=70)                       # 59 × 68 mm bedruckbar
    area = Rect(1.5, 1.0, 59.0, 68.0)
    rect, rotation, factor = layout.insert_placement(doc, "QL-600", area, (66, 34))
    assert (rotation, factor) == (90, 1)
    assert (rect.w, rect.h) == (34, 66)                      # Rahmen auf dem Etikett (gedreht)
    assert (rect.cx, rect.cy) == pytest.approx((area.cx, area.cy))


def test_insert_placement_shrinks_only_when_neither_fits():
    rect, rotation, factor = layout.insert_placement(Document("62", length_mm=40), "QL-600",
                                                     AREA, (118, 19))
    assert rotation == 0 and factor == pytest.approx(0.5)
    assert (rect.w, rect.h) == pytest.approx((59, 9.5))


def test_insert_placement_without_rotate_shrinks_instead_of_turning():
    """Einstellung „nicht drehen“: die Internetmarke kommt quer und verkleinert (spart Band)."""
    doc = Document("62", length_mm=None)
    area = Rect(1.5, 1.0, 59.0, 10.0)
    rect, rotation, factor = layout.insert_placement(doc, "QL-600", area, (70, 34),
                                                     rotate=False)
    assert rotation == 0 and factor == pytest.approx(59 / 70)
    assert (rect.w, rect.h) == pytest.approx((59, 34 * 59 / 70), abs=0.01)


def test_insert_placement_on_growing_tape_vertical_turns_wide_image():
    """Endlosband, automatische Länge, senkrecht: quer begrenzt die Bandbreite, längs nur
    die größte Etikettlänge – eine Internetmarke (70 × 34 mm) passt gedreht 1:1."""
    doc = Document("62", length_mm=None)
    area = Rect(1.5, 1.0, 59.0, 10.0)
    rect, rotation, factor = layout.insert_placement(doc, "QL-600", area, (70, 34))
    assert (rotation, factor) == (90, 1)
    assert (rect.w, rect.h) == (34, 70)
    assert rect.y == pytest.approx(area.y) and rect.cx == pytest.approx(area.cx)


def test_insert_placement_on_growing_tape_horizontal_keeps_wide_image():
    doc = Document("62", length_mm=None, orientation="horizontal")
    area = Rect(1.0, 1.5, 10.0, 59.0)
    rect, rotation, factor = layout.insert_placement(doc, "QL-600", area, (70, 34))
    assert (rotation, factor) == (0, 1)
    assert (rect.w, rect.h) == (70, 34)
    assert rect.x == pytest.approx(area.x) and rect.cy == pytest.approx(area.cy)
    rect, rotation, factor = layout.insert_placement(doc, "QL-600", area, (34, 70))
    assert (rotation, factor) == (90, 1) and (rect.w, rect.h) == (70, 34)


# --- Endlosband: hinter vorhandene Objekte statt darüber ---------------------------------
def test_insert_placement_without_overlap_stays_unchanged():
    doc = Document("62", length_mm=None)
    area = Rect(1.5, 1.0, 59.0, 10.0)
    other = Rect(1.5, 40.0, 20.0, 5.0)
    assert (layout.insert_placement(doc, "QL-600", area, (30, 20), None, [other])
            == layout.insert_placement(doc, "QL-600", area, (30, 20)))


def test_insert_placement_vertical_overlap_goes_below_last_object():
    doc = Document("62", length_mm=None)
    area = Rect(1.5, 1.0, 59.0, 10.0)
    others = [Rect(1.5, 1.0, 20.0, 8.0), Rect(1.5, 10.0, 20.0, 5.0)]
    rect, rotation, factor = layout.insert_placement(doc, "QL-600", area, (30, 20), None, others)
    assert (rotation, factor) == (0, 1)
    assert rect.y == pytest.approx(17.0) and rect.cx == pytest.approx(area.cx)


def test_insert_placement_horizontal_overlap_goes_right_of_last_object():
    doc = Document("62", length_mm=None, orientation="horizontal")
    area = Rect(1.0, 1.5, 10.0, 59.0)
    others = [Rect(1.0, 1.5, 12.0, 59.0)]
    rect, _, _ = layout.insert_placement(doc, "QL-600", area, (30, 20), None, others)
    assert rect.x == pytest.approx(15.0) and rect.cy == pytest.approx(area.cy)


def test_insert_placement_explicit_point_and_fixed_length_ignore_others():
    others = [Rect(1.5, 1.0, 59.0, 38.0)]
    grow = Document("62", length_mm=None)
    area = Rect(1.5, 1.0, 59.0, 10.0)
    assert (layout.insert_placement(grow, "QL-600", area, (30, 20), (30, 20), others)
            == layout.insert_placement(grow, "QL-600", area, (30, 20), (30, 20)))
    fixed = Document("62", length_mm=40)
    assert (layout.insert_placement(fixed, "QL-600", AREA, (20, 10), None, others)
            == layout.insert_placement(fixed, "QL-600", AREA, (20, 10)))


# --- Zuschnitt umschalten: Maßstab und Lage des Inhalts bleiben ------------------------
def test_set_crop_keeps_scale_and_content_in_place():
    obj = _image(x_mm=10, y_mm=5)                            # 50,8 × 25,4 mm
    cropped = layout.set_crop(obj, (60, 30, 360, 180))
    assert cropped.crop == (60, 30, 360, 180)
    assert (cropped.w_mm, cropped.h_mm) == pytest.approx((25.4, 12.7))
    assert (cropped.x_mm, cropped.y_mm) == pytest.approx((15.08, 7.54))
    back = layout.set_crop(cropped, None)
    assert back.crop is None
    assert (back.x_mm, back.y_mm, back.w_mm, back.h_mm) == pytest.approx((10, 5, 50.8, 25.4))
    assert obj.crop is None                                  # Original bleibt


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_set_crop_of_rotated_image_keeps_content_in_place(rotation):
    obj = _image(x_mm=10, y_mm=5, rotation=rotation)
    back = layout.set_crop(layout.set_crop(obj, (60, 30, 360, 180)), None)
    assert (back.x_mm, back.y_mm) == pytest.approx((10, 5))
    cropped = layout.set_crop(obj, (0, 0, 300, 150))         # linke obere Hälfte
    w, h = 25.4, 12.7
    # wo die linke obere Ecke des Bilds nach dem Drehen liegt, bleibt der Ausschnitt
    expected = {90: (10 + 25.4 - h, 5), 180: (10 + 50.8 - w, 5 + 25.4 - h),
                270: (10, 5 + 50.8 - w)}[rotation]
    assert (cropped.x_mm, cropped.y_mm) == pytest.approx(expected)


# --- Originalgröße, Seitenverhältnis, Größe im Panel ---------------------------------
def test_original_size_is_one_to_one_and_keeps_corner():
    obj = _image(x_mm=3, y_mm=4, w_mm=10, h_mm=30, crop=(0, 0, 300, 300))
    original = layout.original_size(obj)
    assert (original.x_mm, original.y_mm, original.w_mm, original.h_mm) == \
        pytest.approx((3, 4, 25.4, 25.4))


def test_keep_ratio_on_restores_ratio_from_width():
    obj = _image(w_mm=40, h_mm=40, keep_ratio=False)          # verzerrt (2:1-Bild)
    kept = layout.set_keep_ratio(obj, True)
    assert kept.keep_ratio and (kept.w_mm, kept.h_mm) == pytest.approx((40, 20))
    free = layout.set_keep_ratio(kept, False)
    assert not free.keep_ratio and (free.w_mm, free.h_mm) == (kept.w_mm, kept.h_mm)


@pytest.mark.parametrize("key, value, expected", [("w", 20, (2, 3, 20, 5)),
                                                  ("h", 20, (2, 3, 80, 20))])
def test_proportional_keeps_corner_and_ratio(key, value, expected):
    assert layout.proportional(Rect(2, 3, 40, 10), key, value) == Rect(*expected)
