"""Labels as files (stage 3c): *.labelwerk format, round trip, errors."""
import base64
import json

import pytest
from PIL import Image, ImageDraw

from labelwerk import storage
from labelwerk.document import (BarcodeObject, Document, Frame, ImageObject, Numbering, Paragraph,
                                Series, Span, TextObject)
from labelwerk.render import render_document
from labelwerk.storage import StorageError, load, save

SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
       b'<rect width="40" height="20" fill="black"/></svg>')


def _picture():
    img = Image.new("RGB", (120, 60), "white")
    ImageDraw.Draw(img).rectangle((10, 10, 109, 49), fill=(200, 30, 30))
    return img


def _document():
    text = TextObject([Paragraph([Span("Absender ", family="DejaVu Serif", size_pt=12),
                                  Span("fett", bold=True, italic=True, underline=True)], "left"),
                       Paragraph([Span("Zeile 2", bold=False)], "right")],
                      size_pt=10, fit=True, x_mm=2.5, y_mm=3, w_mm=40, h_mm=12, rotation=90)
    centred = TextObject("mittig")                       # position None = centred
    image = ImageObject.from_image(_picture(), 300, "bild.png", crop=(10, 10, 110, 50))
    image.x_mm, image.y_mm, image.rotation = 30, 4, 180
    image.mode, image.threshold, image.invert, image.keep_ratio = "photo", 90, True, False
    vector = ImageObject.from_image(Image.new("RGB", (40, 20), "black"), 96, "Symbol: Erde",
                                    svg=SVG)
    vector.x_mm, vector.y_mm = 5, 20
    return Document("62", length_mm=45, orientation="horizontal", margin_mm=2,
                    objects=[text, centred, image, vector],
                    frame=Frame("thick_thin", rounded=True, line_mm=0.4, inset_mm=1.5,
                                padding_mm=2))


def test_roundtrip_gives_the_same_document(tmp_path):
    doc = _document()
    path = tmp_path / "etikett.labelwerk"
    save(doc, path)
    assert load(path) == doc


def test_roundtrip_gives_the_same_print_image(tmp_path):
    doc = _document()
    path = tmp_path / "etikett.labelwerk"
    save(doc, path)
    assert render_document(load(path)).tobytes() == render_document(doc).tobytes()


def test_file_is_versioned_readable_json(tmp_path):
    path = tmp_path / "e.labelwerk"
    save(_document(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert (data["format"], data["version"]) == ("labelwerk", 1)
    objects = data["document"]["objects"]
    assert [o["type"] for o in objects] == ["text", "text", "image", "image"]
    assert objects[0]["paragraphs"][0]["spans"][0]["text"] == "Absender "
    assert base64.b64decode(objects[3]["svg"]) == SVG and objects[2]["svg"] is None
    assert "Absender" in path.read_text(encoding="utf-8")   # umlauts/text readable, not escaped


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path, monkeypatch):
    path = tmp_path / "e.labelwerk"
    save(Document("62", objects=[TextObject("alt")]), path)
    before = path.read_bytes()

    def broken(*args, **kwargs):
        raise OSError(28, "Kein Platz")
    monkeypatch.setattr(storage.os, "replace", broken)
    with pytest.raises(OSError, match="nicht gespeichert"):
        save(Document("62", objects=[TextObject("neu")]), path)
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["e.labelwerk"]


def test_unknown_fields_are_ignored_and_missing_get_defaults(tmp_path):
    data = storage.to_dict(Document("62", objects=[TextObject("x")]))
    data["document"]["zukunft"] = 1
    data["document"]["objects"][0]["schatten"] = True
    del data["document"]["objects"][0]["rotation"]
    del data["document"]["margin_mm"]
    doc = storage.from_dict(data)
    assert doc.objects[0].rotation == 0 and doc.margin_mm == 1.0 and doc.objects[0].text == "x"


# --- Errors ---------------------------------------------------------------------------
def _write(tmp_path, content):
    path = tmp_path / "kaputt.labelwerk"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def _valid():
    return storage.to_dict(_document())


def test_missing_file(tmp_path):
    with pytest.raises(StorageError, match="nicht gefunden"):
        load(tmp_path / "fehlt.labelwerk")


def test_not_json(tmp_path):
    with pytest.raises(StorageError, match="keine labelwerk-Datei"):
        load(_write(tmp_path, "{kein json"))


def test_foreign_json(tmp_path):
    with pytest.raises(StorageError, match="keine labelwerk-Datei"):
        load(_write(tmp_path, {"format": "anderes", "version": 1}))


def test_newer_version(tmp_path):
    data = _valid()
    data["version"] = 2
    with pytest.raises(StorageError, match="neueren labelwerk"):
        load(_write(tmp_path, data))


@pytest.mark.parametrize("change, message", [
    (lambda d: d["document"].update(orientation="schräg"), "orientation"),
    (lambda d: d["document"].update(margin_mm="viel"), "margin_mm"),
    (lambda d: d["document"].update(objects={}), "objects"),
    (lambda d: d["document"]["objects"][0].update(type="kreis"), "Objektart"),
    (lambda d: d["document"]["objects"][0].update(rotation=45), "rotation"),
    (lambda d: d["document"]["objects"][0].update(x_mm=True), "x_mm"),
    (lambda d: d["document"]["objects"][0]["paragraphs"][0].update(align="mitte"), "align"),
    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text=3), "text"),
    (lambda d: d["document"]["objects"][2].update(mode="bunt"), "mode"),
    (lambda d: d["document"]["objects"][2].update(crop=[1, 2, 3]), "crop"),
    (lambda d: d["document"]["objects"][2].update(png="kein base64!"), "Bilddaten"),
    (lambda d: d["document"]["objects"][2].update(png=base64.b64encode(b"kein png").decode()),
     "Bilddaten"),
])
def test_invalid_values_give_german_error_naming_the_field(tmp_path, change, message):
    data = _valid()
    change(data)
    with pytest.raises(StorageError, match=message):
        load(_write(tmp_path, data))


def test_error_names_the_file(tmp_path):
    with pytest.raises(StorageError, match="kaputt.labelwerk"):
        load(_write(tmp_path, "nicht json"))


# --- Recently opened -------------------------------------------------------------------
def test_add_recent_file_newest_first_without_duplicates_and_limit():
    recent = [f"/a/{i}.labelwerk" for i in range(10)]
    assert storage.add_recent_file(recent, "/a/3.labelwerk")[:2] == ["/a/3.labelwerk", "/a/0.labelwerk"]
    new = storage.add_recent_file(recent, "/neu.labelwerk")
    assert len(new) == 10 and new[0] == "/neu.labelwerk" and "/a/9.labelwerk" not in new


def test_schemas_cover_every_dataclass_field():
    """New fields must go into the schema – otherwise they would be silently lost on saving."""
    from dataclasses import fields
    for cls, schema, extra in ((Span, storage.SPAN, set()), (Paragraph, storage.PARAGRAPH, {"spans"}),
                               (TextObject, storage.TEXT, {"paragraphs"}),
                               (ImageObject, storage.IMAGE, set()),
                               (BarcodeObject, storage.BARCODE, set()),
                               (Frame, storage.FRAME, set()),
                               (Series, storage.SERIES, {"numbering"}),
                               (Numbering, storage.NUMBERING, set()),
                               (Document, storage.DOCUMENT, {"objects", "frame", "series"})):
        assert {f.name for f in fields(cls)} == set(schema) | extra, cls.__name__


# --- Refinements: foreign and broken files ---------------------------------------
EPS = (b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 30 30\n"
       b"newpath 0 0 moveto 30 30 lineto stroke showpage\n%%EOF\n")


@pytest.fixture
def no_subprocess(monkeypatch):
    """No external program (Ghostscript) may start while loading or rendering."""
    import subprocess

    def blocked(*args, **kwargs):
        raise AssertionError(f"externes Programm gestartet: {args[:1]}")
    for name in ("Popen", "call", "check_call", "check_output", "run"):
        monkeypatch.setattr(subprocess, name, blocked)


def _image_with(png_bytes):
    data = _valid()
    data["document"]["objects"][2]["png"] = base64.b64encode(png_bytes).decode()
    data["document"]["objects"][2]["crop"] = None
    return data


def test_postscript_in_image_data_is_refused_without_ghostscript(tmp_path, no_subprocess):
    with pytest.raises(StorageError, match="Bilddaten"):
        load(_write(tmp_path, _image_with(EPS)))


@pytest.mark.parametrize("fmt", ["JPEG", "TIFF", "BMP", "GIF"])
def test_only_png_is_accepted_as_image_data(tmp_path, fmt):
    import io
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, fmt)
    with pytest.raises(StorageError, match="Bilddaten"):
        load(_write(tmp_path, _image_with(buffer.getvalue())))


def test_damaged_png_stream_is_refused_when_loading(tmp_path):
    import io, zlib, struct
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "red").save(buffer, "PNG")
    raw = bytearray(buffer.getvalue())
    start = raw.index(b"IDAT")                                  # data broken, CRC matching
    length = struct.unpack(">I", raw[start - 4:start])[0]
    raw[start + 4:start + 4 + length] = b"\x00" * length
    raw[start + 4 + length:start + 8 + length] = struct.pack(
        ">I", zlib.crc32(bytes(raw[start:start + 4 + length])))
    with pytest.raises(StorageError, match="Bilddaten"):
        load(_write(tmp_path, _image_with(bytes(raw))))


def test_huge_image_is_refused(tmp_path):
    import io
    buffer = io.BytesIO()
    Image.new("1", (7000, 10)).save(buffer, "PNG")
    with pytest.raises(StorageError, match="zu groß"):
        load(_write(tmp_path, _image_with(buffer.getvalue())))


def test_crop_outside_the_image_is_refused(tmp_path):
    data = _valid()
    data["document"]["objects"][2]["crop"] = [0, 0, 9999, 10]
    with pytest.raises(StorageError, match="crop"):
        load(_write(tmp_path, data))


@pytest.mark.parametrize("raw", [
    '{"format": "labelwerk", "version": 1, "document": {"margin_mm": NaN}}',
    '{"format": "labelwerk", "version": 1, "document": {"margin_mm": Infinity}}',
    '{"format": "labelwerk", "version": 1, "document": {"length_mm": 1e400}}',
])
def test_non_finite_numbers_are_refused(tmp_path, raw):
    with pytest.raises(StorageError):
        load(_write(tmp_path, raw))


def test_deeply_nested_json_is_refused(tmp_path):
    with pytest.raises(StorageError, match="beschädigt"):
        load(_write(tmp_path, "[" * 200000))


@pytest.mark.parametrize("change, message", [
    (lambda d: d["document"]["objects"][0].update(paragraphs=["abc"]), "Objekt 1"),
    (lambda d: d["document"]["objects"][0]["paragraphs"][0].update(spans=["abc"]), "Objekt 1"),
    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].pop("text"), "text"),
    (lambda d: d["document"]["objects"][0].update(size_pt=1e308), "size_pt"),
    (lambda d: d["document"]["objects"][0].update(size_pt=0), "size_pt"),
    (lambda d: d["document"]["objects"][0].update(x_mm=1e9), "x_mm"),
    (lambda d: d["document"]["objects"][0].update(w_mm=-5), "w_mm"),
    (lambda d: d["document"]["objects"][0].update(rotation=90.0), "rotation"),
    (lambda d: d["document"]["objects"][2].update(w_mm=1e6), "w_mm"),
    (lambda d: d["document"]["objects"][2].update(dpi=0), "dpi"),
    (lambda d: d["document"]["objects"][2].update(threshold=300), "threshold"),
    (lambda d: d["document"]["objects"][2].update(page=0), "page"),
    (lambda d: d["document"].update(length_mm=0), "length_mm"),
    (lambda d: d["document"].update(margin_mm=99), "margin_mm"),
    (lambda d: d["document"].update(label_id="999"), "Etikett"),
    (lambda d: d["document"].update(frame="dick"), "Rahmen"),
    (lambda d: d["document"]["frame"].update(style="welle"), "style"),
    (lambda d: d["document"]["frame"].update(line_mm=5), "line_mm"),
    (lambda d: d["document"]["frame"].update(line_mm=0), "line_mm"),
    (lambda d: d["document"]["frame"].update(inset_mm=-1), "inset_mm"),
    (lambda d: d["document"]["frame"].update(padding_mm=10.5), "padding_mm"),
    (lambda d: d["document"]["frame"].update(rounded="ja"), "rounded"),
    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="a\nb"),
     "Zeilenumbruch"),
    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="a b"),
     "Zeilenumbruch"),
    (lambda d: d["document"]["objects"][0]["paragraphs"][0]["spans"][0].update(text="\ud800"),
     "text"),
])
def test_structure_and_bounds_are_checked(tmp_path, change, message):
    data = _valid()
    change(data)
    with pytest.raises(StorageError, match=message):
        load(_write(tmp_path, data))


def test_loaded_documents_render_without_unexpected_errors(tmp_path):
    """What ``load`` accepts fails at most with ``ValueError`` when rendering."""
    data = _valid()
    data["document"]["objects"][0].update(size_pt=1000, x_mm=-999, w_mm=300, h_mm=300)
    doc = load(_write(tmp_path, data))
    try:
        render_document(doc)
    except ValueError:
        pass


def test_empty_paragraphs_become_one_empty_line(tmp_path):
    data = _valid()
    data["document"]["objects"][1]["paragraphs"] = []
    doc = load(_write(tmp_path, data))
    assert doc.objects[1].text == "" and len(doc.objects[1].paragraphs) == 1


def test_utf8_with_bom_is_read(tmp_path):
    path = tmp_path / "bom.labelwerk"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(_valid()).encode())
    assert load(path) == _document()


def test_messages_are_german(tmp_path):
    folder = tmp_path / "ordner.labelwerk"
    folder.mkdir()
    with pytest.raises(StorageError, match="ist ein Ordner"):
        load(folder)
    with pytest.raises(OSError, match="Ordner fehlt"):
        save(_document(), tmp_path / "fehlt" / "x.labelwerk")


def test_save_keeps_permissions_and_follows_symlinks(tmp_path):
    import os, stat
    target = tmp_path / "echt.labelwerk"
    save(_document(), target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o666 & ~_umask()
    os.chmod(target, 0o640)
    link = tmp_path / "link.labelwerk"
    link.symlink_to(target)
    save(Document("62", objects=[TextObject("neu")]), link)
    assert link.is_symlink() and load(target).objects[0].text == "neu"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def _umask():
    import os
    mask = os.umask(0)
    os.umask(mask)
    return mask


def test_long_file_name_can_be_saved(tmp_path):
    path = tmp_path / ("x" * 240 + ".labelwerk")
    save(_document(), path)
    assert load(path) == _document()


# --- Limits for foreign files (final review 3c) -----------------------------------------
def _image_object(w_mm, h_mm):
    return {"type": "image", "png": _valid()["document"]["objects"][2]["png"],
            "w_mm": w_mm, "h_mm": h_mm}


def test_pixel_budget_refuses_huge_frames(tmp_path):
    data = _valid()
    data["document"]["objects"] = [_image_object(1000, 1000) for _ in range(3)]
    with pytest.raises(StorageError, match="Etikett zu groß"):
        load(_write(tmp_path, data))


def test_pixel_budget_sums_up_all_frames(tmp_path):
    data = _valid()      # 600 × 600 mm each ≈ 50 million dots, 200 million together
    data["document"]["objects"] = [_image_object(600, 600) for _ in range(4)]
    with pytest.raises(StorageError, match="Etikett zu groß"):
        load(_write(tmp_path, data))


def test_object_count_is_limited(tmp_path):
    data = _valid()
    data["document"]["objects"] = [{"type": "text"}] * (storage.MAX_OBJECTS + 1)
    with pytest.raises(StorageError, match="Etikett zu groß"):
        load(_write(tmp_path, data))


def test_normal_documents_are_within_the_limits(tmp_path):
    path = tmp_path / "ok.labelwerk"
    save(_document(), path)
    assert load(path) == _document()


def test_file_size_limit_is_moderate():
    assert storage.MAX_FILE_BYTES <= 32 * 1024 * 1024


def test_surrogate_text_cannot_be_saved_but_gives_a_german_oserror(tmp_path):
    with pytest.raises(OSError, match="nicht gespeichert"):
        save(Document("62", objects=[TextObject("\ud800")]), tmp_path / "x.labelwerk")
    assert list(tmp_path.iterdir()) == []


def test_font_path_is_only_taken_from_a_regular_file(tmp_path):
    font = tmp_path / "font.ttf"
    font.write_bytes(b"x")
    for given, expected in ((str(font), str(font)), (str(tmp_path / "fehlt.ttf"), None),
                            (str(tmp_path), None)):
        data = _valid()
        data["document"]["objects"][0]["font_path"] = given
        assert load(_write(tmp_path, data)).objects[0].font_path == expected


def test_a_fifo_is_not_read(tmp_path):
    import os
    fifo = tmp_path / "rohr.labelwerk"
    os.mkfifo(fifo)
    with pytest.raises(StorageError, match="keine Datei"):
        load(fifo)


def test_position_limit_is_the_one_of_the_position_fields():
    from labelwerk.document import MAX_POSITION_MM
    from labelwerk.gui.panels.position import POSITION_MM
    assert storage.MAX_POSITION_MM == MAX_POSITION_MM and POSITION_MM == (-MAX_POSITION_MM,
                                                                          MAX_POSITION_MM)
    data = _valid()
    data["document"]["objects"][0]["x_mm"] = MAX_POSITION_MM + 0.1
    with pytest.raises(StorageError, match="x_mm"):
        storage.from_dict(data)


# --- Decorative frame ---------------------------------------------------------------------
def test_frame_is_saved_as_its_own_entry(tmp_path):
    path = save(_document(), tmp_path / "r.labelwerk")
    frame = json.loads(path.read_text())["document"]["frame"]
    assert frame == {"style": "thick_thin", "rounded": True, "line_mm": 0.4, "inset_mm": 1.5,
                     "padding_mm": 2}


@pytest.mark.parametrize("value", ["missing", None])
def test_without_frame_entry_there_is_no_frame(tmp_path, value):
    data = _valid()
    if value == "missing":
        data["document"].pop("frame", None)
    else:
        data["document"]["frame"] = None
    assert load(_write(tmp_path, data)).frame is None


def test_frame_fields_missing_get_defaults(tmp_path):
    data = _valid()
    data["document"]["frame"] = {"style": "dotted"}
    assert load(_write(tmp_path, data)).frame == Frame("dotted")


def test_document_without_frame_saves_null(tmp_path):
    path = save(Document("62"), tmp_path / "leer.labelwerk")
    assert json.loads(path.read_text())["document"]["frame"] is None
    assert load(path).frame is None
