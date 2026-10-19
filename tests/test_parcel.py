"""Paketmarken umwandeln (Kern): Katalog, Laden, Erkennen, Kanten anpassen, Umwandeln, eigene Typen.

Nur erzeugte Test-Marken (tests/parcelmark.py) – nie echte Marken mit Adressen."""
import json

import pytest
from PIL import Image, ImageDraw

from labelwerk import i18n, parcel
from labelwerk.document import BarcodeObject, ImageObject
from labelwerk.labels import get_label
from labelwerk.render import label_size, render_document
from parcelmark import make_pdf

MM = 300 / 25.4


# --- Katalog -------------------------------------------------------------------------
def test_catalog_has_the_german_types():
    ids = {t.id for t in parcel.types("DE")}
    assert {"dhl-privat-1", "dhl-privat-1a", "dhl-privat-2", "dhl-privat-3", "dhl-privat-4",
            "dhl-privat-4a", "dhl-privat-4b", "dhl-business-1", "dhl-business-5", "dhl-retour-1",
            "dhl-retour-4", "hermes-1", "hermes-2", "hermes-3"} <= ids
    assert parcel.find("dhl-privat-1").verified and not parcel.find("hermes-2").verified
    assert [code for code, _ in parcel.countries()] == ["DE"]
    assert dict(parcel.carriers("DE")) == {"dhl": "DHL", "hermes": "Hermes"}


@pytest.mark.parametrize("ptype", parcel.types("DE"), ids=lambda t: t.id)
def test_every_type_is_consistent(ptype):
    assert ptype.names["de"] and ptype.names["en"]
    assert ptype.layouts, "jeder mitgelieferte Typ hat ein Layout"
    w, h = max(s[0] for s in ptype.source_sizes), max(s[1] for s in ptype.source_sizes)
    for key, sheets in ptype.layouts.items():
        assert key in parcel.LAYOUTS
        for sheet in sheets:
            assert sheet.pieces
            for piece in sheet.pieces:
                x0, y0, x1, y1 = piece.src
                assert 0 <= x0 < x1 <= w + 1 and 0 <= y0 < y1 <= h + 1, piece
                dx0, dy0, dx1, dy1 = piece.dst
                assert -1 <= dx0 < dx1 <= sheet.size_mm[0] + 1, piece
                assert -1 <= dy0 < dy1 <= sheet.size_mm[1] + 1, piece
                assert piece.rotation in (0, 90, 180, 270) and piece.kind in parcel.KINDS


def test_names_follow_the_language():
    ptype = parcel.find("dhl-privat-3")
    assert ptype.name == "DHL Warenpost national"
    i18n.set_language("en")
    assert ptype.name == "DHL Warenpost domestic"


def test_unknown_type_is_a_friendly_error():
    with pytest.raises(parcel.ParcelError, match="Unbekannter Markentyp"):
        parcel.find("dpd-1")


# --- Laden und Erkennen --------------------------------------------------------------
def test_load_reads_size_and_text(tmp_path):
    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung")])
    source = parcel.load(path)
    assert source.page_count == 1
    assert source.sizes_mm[0] == pytest.approx((210, 297), abs=0.2)
    assert "DHL Online Frankierung" in source.texts[0]
    page = source.page(1, 150)
    assert page.size == pytest.approx((210 * 150 / 25.4, 297 * 150 / 25.4), abs=1)


def test_load_rejects_other_files(tmp_path):
    (tmp_path / "x.txt").write_text("hallo")
    with pytest.raises(parcel.ParcelError):
        parcel.load(tmp_path / "x.txt")
    (tmp_path / "kaputt.pdf").write_bytes(b"%PDF-1.4 nix")
    with pytest.raises(parcel.ParcelError):
        parcel.load(tmp_path / "kaputt.pdf")
    with pytest.raises(parcel.ParcelError):
        parcel.load(tmp_path / "fehlt.pdf")


def test_detect_dhl_domestic(tmp_path):
    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung"),
                                                (20, 30, "Sendungsnummer")])
    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE")]
    assert found[0] == "dhl-privat-1"
    assert "dhl-privat-1a" in found and "hermes-2" not in found


def test_detect_prefers_the_100x150_layout_on_wide_labels(tmp_path):
    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung")])
    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE", label_id="102")]
    assert found[0] == "dhl-privat-1a"


def test_detect_warenpost_with_customs(tmp_path):
    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Warenpost International"),
                                                (20, 30, "CN 23")])
    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE")]
    assert set(found[:2]) == {"dhl-privat-4a", "dhl-privat-4b"}
    assert "dhl-privat-3" not in found


def test_detect_by_page_size(tmp_path):
    path = make_pdf(tmp_path / "m.pdf", size_mm=(105, 203), texts=[(10, 10, "DHL PAKET")])
    assert parcel.detect(parcel.load(path), "DE")[0][0].id == "dhl-business-2"


def test_detect_hermes(tmp_path):
    path = make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Hermes Paketschein")])
    found = [t.id for t, _ in parcel.detect(parcel.load(path), "DE")]
    assert set(found[:2]) == {"hermes-2", "hermes-3"}


def test_detect_raster_label(tmp_path):
    Image.new("RGB", (1800, 1200), "white").save(tmp_path / "m.gif")
    found = [t.id for t, _ in parcel.detect(parcel.load(tmp_path / "m.gif"), "DE")]
    assert found[0] == "dhl-retour-3"


def test_detect_nothing(tmp_path):
    path = make_pdf(tmp_path / "m.pdf", size_mm=(50, 50), texts=[(5, 5, "Hallo")])
    assert parcel.detect(parcel.load(path), "DE") == []


# --- Kanten an die Marke anpassen -----------------------------------------------------
def _page(*rects):
    img = Image.new("L", (round(100 * MM), round(100 * MM)), 255)
    draw = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in rects:
        draw.rectangle([round(x0 * MM), round(y0 * MM), round(x1 * MM) - 1, round(y1 * MM) - 1], 0)
    return img


def test_snap_moves_a_cut_edge_out_to_white():
    img = _page((20, 20, 41, 40))                     # Fläche ragt 1 mm über die rechte Kante
    box = parcel.snap(img, (20, 20, 40, 40), 300)
    assert box[2] == pytest.approx(41, abs=0.2) and box[:2] == pytest.approx((20, 20), abs=0.01)


def test_snap_keeps_white_edges_and_long_overhangs():
    img = _page((20, 20, 50, 40))                     # ragt 10 mm hinaus: keine weiße Linie nah
    assert parcel.snap(img, (20, 20, 40, 40), 300) == pytest.approx((20, 20, 40, 40))
    img = _page((22, 22, 38, 38))                     # Kanten schon weiß
    assert parcel.snap(img, (20, 20, 40, 40), 300) == pytest.approx((20, 20, 40, 40))


# --- Umwandeln ----------------------------------------------------------------------
def _barcode_page(tmp_path, ptype_id="dhl-privat-1"):
    """Testmarke mit einem Code 128 im ersten Barcode-Stück des Typs (quer wie auf der Marke)."""
    from labelwerk import barcodes
    piece = max((p for p in parcel.find(ptype_id).layouts["62"][0].pieces if p.kind == "barcode"),
                key=lambda p: (p.src[2] - p.src[0]) * (p.src[3] - p.src[1]))     # größtes Barcode-Stück
    code = barcodes.draw(BarcodeObject(kind="code128", data="LW123456", module=4, h_mm=18))
    if piece.src[3] - piece.src[1] > piece.src[2] - piece.src[0]:
        code = code.rotate(90, expand=True)                    # hochkant wie auf der Marke
    x = piece.src[0] + 2
    y = piece.src[1] + 2
    return make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL Online Frankierung")],
                    rects=[(10, 30, 30, 40)], images=[(x, y, code, 300)])


def test_convert_dhl_domestic_for_62_mm(tmp_path):
    source = parcel.load(_barcode_page(tmp_path))
    result = parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
    assert result.layout == "62" and len(result.documents) == 1
    doc = result.documents[0]
    assert doc.label_id == "62" and doc.orientation == "horizontal"
    assert len(doc.objects) == 7 and all(isinstance(o, ImageObject) for o in doc.objects)
    assert all(o.mode == "line" and not o.keep_ratio for o in doc.objects)
    width, height = label_size(doc, "QL-600")
    assert height == get_label("62").width                   # quer: ganzes Band
    assert result.scale == pytest.approx(58.93 / 59.58, abs=0.02)
    assert result.notes == []                                # Barcodes ≥ 97 %
    assert 160 < doc.length_mm < 190
    for obj in doc.objects:                                  # alles auf dem Etikett
        assert obj.x_mm >= -0.01 and obj.y_mm >= -0.01
        assert obj.y_mm + obj.h_mm <= 58.95
        assert obj.x_mm + obj.w_mm <= doc.length_mm - 5.9


def test_converted_barcode_is_readable(tmp_path):
    zxingcpp = pytest.importorskip("zxingcpp", reason="zxing-cpp fehlt (Wheels erst ab Python 3.12)")
    source = parcel.load(_barcode_page(tmp_path))
    doc = parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600").documents[0]
    img = render_document(doc, "QL-600").convert("L")
    texts = [r.text for r in zxingcpp.read_barcodes(img)]
    assert "LW123456" in texts


def test_wider_tape_makes_it_larger(tmp_path):
    source = parcel.load(_barcode_page(tmp_path))
    narrow = parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
    wide = parcel.convert(source, parcel.find("dhl-privat-1"), "102", "QL-1100")
    assert wide.scale > 1.5 * narrow.scale
    assert wide.documents[0].length_mm > 1.5 * narrow.documents[0].length_mm


def test_wide_label_uses_the_100x150_layout(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
    result = parcel.convert(source, parcel.find("dhl-privat-1a"), "104x150mm@300", "zpl:300")
    assert result.layout == "100x150"
    assert result.documents[0].orientation == "vertical"
    assert result.notes == []


def test_short_die_cut_label_shrinks_with_a_note(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
    result = parcel.convert(source, parcel.find("dhl-privat-1"), "62x100", "QL-600")
    assert result.scale < 0.6
    assert any("Barcodes verkleinert" in n for n in result.notes)
    doc = result.documents[0]
    w, h = label_size(doc, "QL-600")
    for obj in doc.objects:
        assert obj.x_mm + obj.w_mm <= w / MM + 0.05 and obj.y_mm + obj.h_mm <= h / MM + 0.05


def test_two_labels_for_a_return(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Amazon Rücksendung")]))
    result = parcel.convert(source, parcel.find("dhl-retour-4"), "62", "QL-600")
    assert len(result.documents) == 2


def test_raster_label_is_placed_where_the_type_says(tmp_path):
    img = Image.new("RGB", (1800, 1200), "white")
    ImageDraw.Draw(img).rectangle([0, 0, 1799, 1199], outline="black", width=30)
    img.save(tmp_path / "m.gif")
    source = parcel.load(tmp_path / "m.gif")
    ptype = parcel.find("dhl-retour-3")
    page = source.page(1, 100, ptype)
    assert page.size == pytest.approx((210 * 100 / 25.4, 297 * 100 / 25.4), abs=1)
    k = 100 / 25.4                                            # Lage aus der Regel: 189,4 mm von oben
    assert page.getpixel((round(50 * k), round((189.4 + 101.6 - 1) * k))) < 128   # Rahmen unten
    assert page.getpixel((round(50 * k), round(150 * k))) == 255
    assert page.getpixel((2, 2)) == 255
    result = parcel.convert(source, ptype, "62", "QL-600")
    assert result.documents and render_document(result.documents[0], "QL-600")


def test_round_labels_are_refused(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
    with pytest.raises(parcel.ParcelError):
        parcel.convert(source, parcel.find("dhl-privat-1"), "d24", "QL-600")


# --- Eigene Typen -------------------------------------------------------------------
def _own(**changes):
    data = {"id": "own-test", "names": {"de": "Meine Marke", "en": "My label"},
            "source": {"sizes_mm": [[210, 297]]}, "detect": {"all": ["Meine Firma"]},
            "pieces": [{"page": 1, "src": [10, 10, 110, 60], "rotation": 0, "kind": "text"},
                       {"page": 1, "src": [10, 100, 60, 130], "rotation": 0, "kind": "barcode"},
                       {"page": 1, "src": [100, 100, 130, 200], "rotation": 90, "kind": "text"}]}
    data.update(changes)
    return data


def test_own_types_round_trip():
    ptype = parcel.own_from_dict(_own())
    parcel.save_own(ptype)
    assert [t.id for t in parcel.own_types()] == ["own-test"]
    assert parcel.find("own-test").own and parcel.find("own-test").name == "Meine Marke"
    assert "own-test" in {t.id for t in parcel.types("DE")}       # eigene in jedem Land
    parcel.remove_own("own-test")
    assert parcel.own_types() == []


@pytest.mark.parametrize("change", [{"pieces": []}, {"id": "../x"}, {"names": {"de": ""}},
                                    {"pieces": [{"page": 1, "src": [10, 10, 5, 5], "rotation": 0,
                                                 "kind": "text"}]},
                                    {"pieces": [{"page": 1, "src": [0, 0, 10, 10], "rotation": 45,
                                                 "kind": "text"}]},
                                    {"pieces": [{"page": 1, "src": [0, 0, 10, 10], "rotation": 0,
                                                 "kind": "foto"}]}])
def test_own_types_are_checked(change):
    with pytest.raises(parcel.ParcelError):
        parcel.own_from_dict(_own(**change))


def test_broken_own_file_is_skipped_with_a_note():
    parcel.own_dir().mkdir(parents=True)
    (parcel.own_dir() / "kaputt.json").write_text("{nicht json")
    (parcel.own_dir() / "gut.json").write_text(json.dumps(_own(id="own-gut")))
    assert [t.id for t in parcel.own_types()] == ["own-gut"]
    assert any("kaputt.json" in w for w in parcel.own_warnings())


def test_arrange_fills_columns_along_the_tape():
    ptype = parcel.own_from_dict(_own())
    sheet = parcel.arrange(ptype.pieces, 58.9)
    assert sheet.size_mm[1] == pytest.approx(58.9)
    text, code, turned = sheet.pieces
    assert code.dst[2] - code.dst[0] == pytest.approx(50)                # Barcode 1:1
    assert text.dst[2] - text.dst[0] == pytest.approx(100)              # passt quer: 1:1
    assert turned.dst[3] - turned.dst[1] == pytest.approx(30)           # gedreht: 100 lang → längs
    for piece in sheet.pieces:
        assert piece.dst[3] <= 58.9 + 1e-6


def test_own_type_converts(tmp_path):
    ptype = parcel.own_from_dict(_own())
    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "Meine Firma")]))
    assert parcel.detect(source, "DE", own=[ptype])[0][0].id == "own-test"
    result = parcel.convert(source, ptype, "62", "QL-600")
    assert len(result.documents[0].objects) == 3 and result.layout == "own"


def test_snap_only_for_untested_types_and_not_into_other_pieces(tmp_path, monkeypatch):
    calls = []
    real = parcel.snap

    def spy(img, box, dpi, limit_mm=3.0):
        calls.append(box)
        return real(img, box, dpi, limit_mm)
    monkeypatch.setattr(parcel, "snap", spy)
    source = parcel.load(make_pdf(tmp_path / "m.pdf", texts=[(20, 20, "DHL")]))
    parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
    assert calls == []                                       # geprüft: Kanten genau
    parcel.convert(source, parcel.find("dhl-privat-2"), "62", "QL-600")
    assert calls
    a = parcel.Piece(1, (10, 10, 20, 20), 0)
    b = parcel.Piece(1, (21, 10, 30, 20), 0)
    assert parcel._alone(a, (9, 10, 22, 20), [a, b]) == (9, 10, 20, 20)   # nicht in b hinein


# --- Lage, Drehung und Malreihenfolge je Typ -------------------------------------------
def _marked_sheet(ptype, size_mm=None, k=300 / 25.4):
    """Marke (Bild bei 300 dpi) mit einem schwarzen Quadrat oben links in jedem Bereich – zeigt
    nach dem Umwandeln, ob Lage und Drehung stimmen."""
    w, h = size_mm or ptype.source_sizes[0]
    img = Image.new("L", (round(w * k), round(h * k)), 255)
    draw = ImageDraw.Draw(img)
    for piece in parcel.all_pieces(ptype):
        x0, y0, x1, y1 = piece.src
        draw.rectangle([round((x0 + 0.18 * (x1 - x0)) * k), round((y0 + 0.18 * (y1 - y0)) * k),
                        round((x0 + 0.32 * (x1 - x0)) * k), round((y0 + 0.32 * (y1 - y0)) * k)], 0)
    return img


_ROTATED = {0: lambda u, v: (u, v), 90: lambda u, v: (1 - v, u), 180: lambda u, v: (1 - u, 1 - v),
            270: lambda u, v: (v, 1 - u)}


def _covered(dst, later):
    x0, y0, x1, y1 = dst
    area = 0.0
    for a0, b0, a1, b1 in later:
        area += max(0, min(x1, a1) - max(x0, a0)) * max(0, min(y1, b1) - max(y0, b0))
    return area / ((x1 - x0) * (y1 - y0))


@pytest.mark.parametrize("ptype", [t for t in parcel.types("DE")], ids=lambda t: t.id)
def test_every_piece_lands_where_and_how_the_type_says(ptype, tmp_path):
    marked = _marked_sheet(ptype)
    if ptype.raster:                                      # Bildmarke: nur ihr Ausschnitt der Seite
        k = 300 / 25.4
        x, y = ptype.raster["x_mm"] * k, ptype.raster["y_mm"] * k
        marked.crop((round(x), round(y), round(x) + 1800, round(y) + 1200)).save(tmp_path / "m.png")
        source = parcel.load(tmp_path / "m.png")
    else:
        source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=ptype.source_sizes[0],
                                      images=[(0, 0, marked, 300)]))
    label = "102x152" if "62" not in ptype.layouts else "62"
    result = parcel.convert(source, ptype, label, "QL-1100")
    sheets = ptype.layouts["62" if "62" in ptype.layouts else "100x150"]
    checked = 0
    for doc, sheet in zip(result.documents, sheets):
        for n, (obj, piece) in enumerate(zip(doc.objects, sheet.pieces)):
            if _covered(piece.dst, [p.dst for p in sheet.pieces[n + 1:]]) > 0.05:
                continue                                  # verdeckt: Malreihenfolge-Test unten
            img = obj.image().convert("L")
            u, v = _ROTATED[piece.rotation](0.25, 0.25)
            pixel = img.getpixel((min(img.width - 1, round(u * img.width)),
                                  min(img.height - 1, round(v * img.height))))
            assert pixel < 128, (ptype.id, n, piece)
            checked += 1
    assert checked >= 1


def test_later_pieces_cover_earlier_ones_cleanly(tmp_path):
    """DHL national: das Leitcode-Quadrat liegt auf dem Kopfstreifen – dessen Tinte darf darunter
    nicht durchscheinen."""
    ptype = parcel.find("dhl-privat-1")
    pieces = ptype.layouts["62"][0].pieces
    head, square = pieces[0], pieces[3]
    assert _covered(head.dst, [square.dst]) > 0
    k = 300 / 25.4
    img = Image.new("L", (round(210 * k), round(297 * k)), 255)
    x0, y0, x1, y1 = head.src
    ImageDraw.Draw(img).rectangle([round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)], 0)
    x0, y0, x1, y1 = square.src
    ImageDraw.Draw(img).rectangle([round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)], 255)
    source = parcel.load(make_pdf(tmp_path / "m.pdf", images=[(0, 0, img, 300)]))
    doc = parcel.convert(source, ptype, "62", "QL-600").documents[0]
    reading = render_document(doc, "QL-600").convert("L").rotate(90, expand=True)
    obj = doc.objects[3]
    centre = (round((obj.x_mm + obj.w_mm / 2) * k), round((obj.y_mm + obj.h_mm / 2) * k))
    assert reading.getpixel(centre) == 255                # weißes Quadrat bleibt weiß


def test_crop_outside_the_page_is_white():
    page = Image.new("L", (100, 100), 0)
    out = parcel._crop_white(page, (-10, -10, 50, 50))
    assert out.size == (60, 60) and out.getpixel((2, 2)) == 255 and out.getpixel((30, 30)) == 0


# --- Seitenlage: quer, andere Größe, Bild ------------------------------------------------
def test_landscape_page_is_turned_upright(tmp_path):
    ptype = parcel.find("dhl-privat-1")
    landscape = _marked_sheet(ptype).rotate(90, expand=True)     # Marke quer (gegen den Uhrzeiger)
    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(297, 210),
                                  images=[(0, 0, landscape, 300)]))
    assert parcel.placement(source, ptype).rotation == 90
    page = source.page(1, 300 / 25.4 * 25.4 / 1, ptype)
    assert page.size == pytest.approx((210 * 300 / 25.4, 297 * 300 / 25.4), abs=2)
    doc = parcel.convert(source, ptype, "62", "QL-600").documents[0]
    img = doc.objects[2].image().convert("L")               # Stück ohne Drehung
    assert img.getpixel((round(0.25 * img.width), round(0.25 * img.height))) < 128


def test_landscape_page_with_unclear_direction_is_refused(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(297, 210)))
    with pytest.raises(parcel.ParcelError, match="quer"):
        parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")


def test_letter_page_sits_top_left_on_a4(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(215.9, 279.4),
                                  rects=[(0, 0, 215.9, 279.4)]))
    ptype = parcel.find("dhl-retour-4")
    page = source.page(1, 50, ptype)
    k = 50 / 25.4
    assert page.size == pytest.approx((210 * k, 297 * k), abs=1)
    assert page.getpixel((round(100 * k), round(270 * k))) == 0          # Letter-Inhalt
    assert page.getpixel((round(100 * k), round(290 * k))) == 255        # darunter weiß


@pytest.mark.parametrize("ptype", [t for t in parcel.types("DE")], ids=lambda t: t.id)
def test_every_listed_page_size_is_accepted(ptype, tmp_path):
    for size in ptype.source_sizes:
        if ptype.raster:
            continue
        source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=size))
        place = parcel.placement(source, ptype)
        assert place.frame_mm == ptype.source_sizes[0] and place.rotation == 0


def test_wrong_page_size_is_a_friendly_error(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(2000, 2000)))
    with pytest.raises(parcel.ParcelError, match="passt nicht"):
        parcel.convert(source, parcel.find("dhl-privat-1"), "62", "QL-600")
    with pytest.raises(parcel.ParcelError, match="zu groß"):
        parcel.load(make_pdf(tmp_path / "a4.pdf")).page(1, 2000)


def test_image_of_another_shape_is_not_recognized(tmp_path):
    Image.new("RGB", (1000, 1000), "white").save(tmp_path / "q.gif")
    assert parcel.detect(parcel.load(tmp_path / "q.gif"), "DE") == []


def test_full_page_image_is_stretched_to_the_page_of_the_type(tmp_path):
    ptype = parcel.find("dhl-privat-1")
    _marked_sheet(ptype, k=100 / 25.4).save(tmp_path / "seite.png")   # 100 dpi, keine Angabe
    source = parcel.load(tmp_path / "seite.png")
    doc = parcel.convert(source, ptype, "62", "QL-600").documents[0]
    img = doc.objects[2].image().convert("L")
    assert img.getpixel((round(0.25 * img.width), round(0.25 * img.height))) < 128


def test_huge_images_are_refused_before_decoding(tmp_path):
    Image.new("1", (9400, 9400), 1).save(tmp_path / "riesig.png")
    with pytest.raises(parcel.ParcelError, match="zu viele Pixel"):
        parcel.load(tmp_path / "riesig.png")


@pytest.mark.parametrize("dpi, expected", [(2, None), (72, 72.0), (5000, None)])
def test_implausible_image_resolution_counts_as_missing(tmp_path, dpi, expected):
    Image.new("RGB", (600, 400), "white").save(tmp_path / "m.png", dpi=(dpi, dpi))
    source = parcel.load(tmp_path / "m.png")
    assert source.image_dpi == (pytest.approx(expected, abs=0.5) if expected else None)


def test_16_bit_gray_image_keeps_its_ink(tmp_path):
    img = Image.new("I;16", (300, 200), 65535)
    img.paste(0, (0, 0, 100, 100))
    img.save(tmp_path / "m.png")
    page = parcel.load(tmp_path / "m.png").image
    assert page.getpixel((10, 10)) < 64 and page.getpixel((250, 150)) > 192


def test_pdf_without_pages_has_its_own_message(tmp_path):
    body = (b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n")
    xref = len(body)
    body += (b"xref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
             b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref)
    (tmp_path / "leer.pdf").write_bytes(body)
    with pytest.raises(parcel.ParcelError, match="keine Seiten|nicht"):
        parcel.load(tmp_path / "leer.pdf")


# --- Layout fehlt fürs Format, Gleichstand, eigene Typen --------------------------------
def test_missing_layout_is_arranged_from_the_pieces(tmp_path):
    ptype = parcel.find("dhl-privat-1a-100x150")
    source = parcel.load(make_pdf(tmp_path / "m.pdf", size_mm=(100, 150)))
    result = parcel.convert(source, ptype, "62", "QL-600")
    assert result.layout == "arranged"
    doc = result.documents[0]
    for obj, piece in zip(doc.objects, ptype.layouts["100x150"][0].pieces):
        w, h = piece.turned_mm()
        if piece.kind == "barcode" and h <= 58.9:
            assert (obj.w_mm, obj.h_mm) == pytest.approx((w, h), abs=0.05)   # Barcodes 1:1
        assert obj.y_mm + obj.h_mm <= 58.95


def test_ambiguous_marks_ties_without_a_tested_winner(tmp_path):
    hermes = parcel.load(make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein")]))
    assert {t.id for t in parcel.ambiguous(parcel.detect(hermes, "DE"))} == {"hermes-2", "hermes-3"}
    dhl = parcel.load(make_pdf(tmp_path / "d.pdf", texts=[(20, 20, "DHL Online Frankierung")]))
    assert parcel.ambiguous(parcel.detect(dhl, "DE")) == []


@pytest.mark.parametrize("src", [[10, 10, 10.5, 50], [10, 10, 50, 10.5], [10, 10, 211, 50],
                                 [10, 10, 50, 298]])
def test_own_areas_need_size_and_must_lie_on_the_page(src):
    with pytest.raises(parcel.ParcelError, match="Bereiche"):
        parcel.own_from_dict(_own(pieces=[{"page": 1, "src": src, "rotation": 0, "kind": "text"}]))


def test_damaged_own_file_says_so():
    parcel.own_dir().mkdir(parents=True)
    (parcel.own_dir() / "kaputt.json").write_text("{nicht json")
    parcel.own_types()
    assert any("beschädigt" in w for w in parcel.own_warnings())


def test_version_mark_decides_between_hermes_labels(tmp_path):
    source = parcel.load(make_pdf(tmp_path / "h.pdf", texts=[(20, 20, "Hermes Paketschein V4.2.000")]))
    found = parcel.detect(source, "DE")
    assert found[0][0].id == "hermes-2" and parcel.ambiguous(found) == []


# --- Hilfen für die Oberfläche ----------------------------------------------------------
@pytest.mark.parametrize("env, expected", [
    ({"LC_ALL": "de_DE.UTF-8"}, "DE"), ({"LANG": "de_AT.UTF-8"}, "DE"),
    ({"LC_ALL": "", "LC_MESSAGES": "", "LANG": "C"}, "DE"), ({"LANG": "fr_FR.UTF-8"}, "DE")])
def test_default_country_follows_the_region_or_takes_the_first(monkeypatch, env, expected):
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert parcel.default_country() == expected     # nur DE im Katalog: sonst das erste Land


def test_default_country_prefers_a_matching_region(monkeypatch):
    monkeypatch.setattr(parcel, "countries", lambda: [("AT", "Österreich"), ("DE", "Deutschland")])
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    assert parcel.default_country() == "DE"
    monkeypatch.setenv("LC_ALL", "C")
    monkeypatch.setenv("LANG", "")
    assert parcel.default_country() == "AT"


def test_own_id_is_a_free_slug():
    assert parcel.own_id("Mein Lager – Retoure", set()) == "eigen-mein-lager-retoure"
    assert parcel.own_id("Mein Lager – Retoure", {"eigen-mein-lager-retoure"}) \
        == "eigen-mein-lager-retoure-2"
    assert parcel.own_id("äöü ß", set()) == "eigen-aeoeue-ss"
    assert parcel.own_id("!!!", set()) == "eigen-typ"
    slug = parcel.own_id("x" * 200, set())
    assert len(slug) <= 64 and parcel.own_from_dict(_own(id=slug)).id == slug
