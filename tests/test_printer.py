import pytest

from labelwerk.render import render_text
from labelwerk.printer import PrintError, build_instructions, print_image


def test_build_instructions_produces_brother_raster_data():
    data = build_instructions(render_text("Test", "62"), "62", model="QL-600")
    assert isinstance(data, bytes)
    assert b"\x1b@" in data          # ESC @ = Initialisieren
    assert data.endswith(b"\x1a")    # Drucken mit Vorschub


def _send_returning(status):
    return lambda **kw: status


def _send_raising(exc):
    def send(**kw):
        raise exc
    return send


def _print(monkeypatch, send):
    monkeypatch.setattr("labelwerk.printer.send", send)
    return print_image(render_text("Test", "62"), "62", printer="file:///dev/usb/lp0")


def test_successful_print_returns_status(monkeypatch):
    status = {"outcome": "printed", "did_print": True}
    assert _print(monkeypatch, _send_returning(status)) == status


def test_wrong_roll_raises_friendly_error(monkeypatch):
    status = {"outcome": "error", "did_print": False,
              "printer_state": {"errors": ["Replace media error"]}}
    with pytest.raises(PrintError, match="Rolle passt nicht"):
        _print(monkeypatch, _send_returning(status))


def test_unknown_printer_error_is_passed_through(monkeypatch):
    status = {"outcome": "error", "did_print": False,
              "printer_state": {"errors": ["System error"]}}
    with pytest.raises(PrintError, match="System error"):
        _print(monkeypatch, _send_returning(status))


def test_missing_device_raises_friendly_error(monkeypatch):
    with pytest.raises(PrintError, match="nicht gefunden"):
        _print(monkeypatch, _send_raising(FileNotFoundError(2, "No such file")))


def test_missing_pyusb_device_raises_friendly_error(monkeypatch):
    with pytest.raises(PrintError, match="nicht gefunden"):
        _print(monkeypatch, _send_raising(ValueError("Device not found")))


def test_missing_permission_raises_friendly_error(monkeypatch):
    with pytest.raises(PrintError, match="Gruppe 'lp'"):
        _print(monkeypatch, _send_raising(PermissionError(13, "Permission denied")))


# --- Serien: mehrere Etiketten in einem Auftrag -------------------------------------------------
from PIL import Image  # noqa: E402

from labelwerk.printer import cut_interval  # noqa: E402

AUTOCUT = b"\x1biM\x40"          # ESC i M: automatisch schneiden


def _blank(n):
    """Leere Etiketten – ihre Rasterdaten enthalten keine Befehlsbytes."""
    return [Image.new("RGB", (696, 300), "white") for _ in range(n)]


def _cut_every(data):
    """Werte n aus ESC i A n (schneiden alle n Etiketten), je Seite einer."""
    out, start = [], 0
    while (i := data.find(b"\x1biA", start)) >= 0:
        out.append(data[i + 3])
        start = i + 4
    return out


def test_several_labels_are_one_job_cut_after_each():
    data = build_instructions(_blank(3), "62", cut_every=1)
    assert data.count(b"\x1b@") == 1                    # ein Auftrag
    assert data.count(AUTOCUT) == 3 and _cut_every(data) == [1, 1, 1]
    assert data.count(b"\x1biK\x08") == 3               # am Ende schneiden
    assert data.endswith(b"\x1a") and data.count(b"\x0c") >= 2


def test_cut_only_at_the_end():
    data = build_instructions(_blank(3), "62", cut_every=cut_interval("end", 3))
    assert _cut_every(data) == [3, 3, 3]
    assert data.count(b"\x1biK\x08") == 3


def test_no_cut_at_all():
    data = build_instructions(_blank(2), "62", cut=False)
    assert AUTOCUT not in data and _cut_every(data) == []
    assert data.count(b"\x1biK\x00") == 2


def test_single_image_still_works_like_before():
    one = build_instructions(_blank(1)[0], "62")
    assert one == build_instructions(_blank(1), "62")
    assert _cut_every(one) == [1]


@pytest.mark.parametrize("mode, count, expected", [("each", 5, 1), ("end", 5, 5), ("end", 1, 1),
                                                   ("end", 300, 255)])
def test_cut_interval(mode, count, expected):
    assert cut_interval(mode, count) == expected


def test_cut_interval_rejects_unknown_modes():
    with pytest.raises(ValueError):
        cut_interval("nie", 3)


def test_empty_list_is_refused():
    with pytest.raises(ValueError, match="Keine Etiketten"):
        build_instructions([], "62")


def test_print_image_sends_all_labels(monkeypatch):
    sent = {}

    def send(instructions, **kw):
        sent["data"] = instructions
        return {"outcome": "printed", "did_print": True}
    monkeypatch.setattr("labelwerk.printer.send", send)
    print_image(_blank(4), "62", printer="file:///dev/usb/lp0", cut_every=4)
    assert _cut_every(sent["data"]) == [4, 4, 4, 4]


# --- Nachbesserungen nach dem Review ------------------------------------------------------------
from labelwerk.printer import MAX_JOB_EACH, _Raster  # noqa: E402


def _pages(data):
    """Byte n9 (Startseite 0, weitere 1) aus jedem ESC i z."""
    out, start = [], 0
    while (i := data.find(b"\x1biz", start)) >= 0:
        out.append(data[i + 3 + 8])
        start = i + 3
    return out


def test_one_job_has_exactly_its_page_ends():
    data = build_instructions(_blank(3), "62")
    assert data.count(b"\x0c") == 2 and data.count(b"\x1a") == 1


def test_later_pages_are_marked_as_such():
    assert _pages(build_instructions(_blank(3), "62")) == [0, 1, 1]
    assert _pages(build_instructions(_blank(1), "62")) == [0]


def test_raster_data_grows_without_copying():
    """bytes += kopiert bei jedem Befehl alles – lange Serien würden quadratisch langsam."""
    raster = _Raster("QL-600", 1)
    assert isinstance(raster.data, bytearray)
    assert isinstance(build_instructions(_blank(2), "62"), bytes)


def test_die_cut_labels_in_one_job():
    images = [Image.new("RGB", (696, 271), "white") for _ in range(2)]
    data = build_instructions(images, "62x29", cut_every=2)
    assert _cut_every(data) == [2, 2] and data.count(b"\x1a") == 1


def test_printer_without_cutter_gets_no_cut_commands():
    data = build_instructions([Image.new("RGB", (696, 300), "white")] * 2, "62", model="QL-500")
    assert AUTOCUT not in data and _cut_every(data) == []


@pytest.mark.parametrize("value", [0, -1, 1.5, "2"])
def test_cut_every_must_be_a_positive_whole_number(value):
    with pytest.raises(ValueError, match="alle n Etiketten"):
        build_instructions(_blank(1), "62", cut_every=value)


def test_cut_every_above_the_printer_limit_is_capped():
    assert _cut_every(build_instructions(_blank(1), "62", cut_every=300)) == [255]


@pytest.mark.parametrize("count, expected", [(255, 255), (256, 255)])
def test_cut_interval_at_the_limit(count, expected):
    assert cut_interval("end", count) == expected


def _sender(statuses, sent):
    def send(instructions, **kw):
        sent.append(instructions)
        return statuses.pop(0) if statuses else {"outcome": "printed", "did_print": True}
    return send


def test_long_series_are_sent_in_parts_each_checked(monkeypatch):
    sent = []
    monkeypatch.setattr("labelwerk.printer.send", _sender([], sent))
    print_image(_blank(MAX_JOB_EACH + 3), "62", printer="file:///dev/usb/lp0")
    assert [len(_pages(job)) for job in sent] == [MAX_JOB_EACH, 3]


def test_cut_at_the_end_keeps_parts_of_its_interval(monkeypatch):
    sent = []
    monkeypatch.setattr("labelwerk.printer.send", _sender([], sent))
    print_image(_blank(7), "62", printer="file:///dev/usb/lp0", cut_every=3)
    assert [len(_pages(job)) for job in sent] == [3, 3, 1]


def test_error_in_a_part_stops_and_names_the_labels(monkeypatch):
    sent = []
    failing = {"outcome": "error", "did_print": False,
               "printer_state": {"errors": ["No media when printing"]}}
    monkeypatch.setattr("labelwerk.printer.send",
                        _sender([{"outcome": "printed", "did_print": True}, failing], sent))
    with pytest.raises(PrintError, match=rf"Etikett {MAX_JOB_EACH + 1}–{MAX_JOB_EACH + 2} von "
                                         rf"{MAX_JOB_EACH + 2}.*davor.*Keine Rolle"):
        print_image(_blank(MAX_JOB_EACH + 2), "62", printer="file:///dev/usb/lp0")
    assert len(sent) == 2


def test_print_mode_images_print_exactly_the_same():
    """1-Bit-Bilder (Serien: wenig Speicher) ergeben dieselben Rasterdaten wie das Druckbild."""
    from PIL import ImageDraw
    from labelwerk.printer import to_print_mode
    img = Image.new("RGB", (696, 120), "white")
    draw = ImageDraw.Draw(img)
    for x in range(0, 256):
        draw.line((x * 2, 0, x * 2, 119), fill=(x, x, x))        # alle Grautöne
    small = to_print_mode(img)
    assert small.mode == "1"
    assert build_instructions(small, "62") == build_instructions(img, "62")


def test_single_label_is_byte_identical_to_plain_brother_ql():
    """Golden: ein Etikett wie vor den Serien (BrotherQLRaster + convert) – _Raster ändert nur
    Serien."""
    from brother_ql.conversion import convert
    from brother_ql.raster import BrotherQLRaster
    image = render_text("Test", "62")
    plain = BrotherQLRaster("QL-600")
    plain.exception_on_warning = True
    expected = convert(qlr=plain, images=[image], label="62", rotate="0", threshold=70.0,
                       dither=False, compress=False, red=False, dpi_600=False, hq=True, cut=True)
    assert build_instructions(image, "62") == bytes(expected)
