"""Zebra direkt (ZPL): Aufbau, Kompression (zurückgelesen mit einem eigenen Decoder), Erkennung
per sysfs, Senden (Gerät/Socket ersetzt) – kein Test spricht einen Drucker oder das Netz an."""
import random
import re

import pytest
from PIL import Image, ImageDraw

from labelwerk import printers, zpl
from labelwerk.labels import get_label, labels_for_model
from labelwerk.printer import PrintError, print_image


def decode(text: str) -> Image.Image:
    """``^GFA,total,total,je_zeile,daten`` → Bild (schwarz = Punkt), Kompression nach Zebra
    zeichenweise zurückgelesen (für die Tests)."""
    m = re.search(r"\^GFA,(\d+),(\d+),(\d+),([^^]*)", text)
    total, row_bytes, data = int(m[1]), int(m[3]), m[4]
    width = row_bytes * 2
    rows, row, count = [], "", 0

    def finish(fill=""):
        nonlocal row
        rows.append(row + fill * (width - len(row)))
        row = ""
    for ch in data:
        if "G" <= ch <= "Y":
            count += ord(ch) - ord("F")
        elif "g" <= ch <= "z":
            count += (ord(ch) - ord("f")) * 20
        elif ch in ",!":
            finish("0" if ch == "," else "F")
        elif ch == ":":
            assert row == ""
            rows.append(rows[-1])
        else:
            row += ch * max(count, 1)
            count = 0
            assert len(row) <= width
            if len(row) == width:
                finish()
    assert row == "" and all(len(r) == width for r in rows)
    raw = bytes.fromhex("".join(rows))
    assert len(raw) == total
    return Image.frombytes("1", (row_bytes * 8, total // row_bytes), bytes(b ^ 0xFF for b in raw))


def _picture(w, h, seed=1):
    rnd = random.Random(seed)
    img = Image.new("1", (w, h), 1)
    pen = ImageDraw.Draw(img)
    for _ in range(40):
        x, y = rnd.randrange(w), rnd.randrange(h)
        pen.rectangle((x, y, x + rnd.randrange(1, 60), y + rnd.randrange(1, 9)), fill=0)
    for x in range(0, w, 7):                                 # Muster: keine Wiederholungen
        img.putpixel((x, h // 2), 0)
    return img


# --- Kompression --------------------------------------------------------------------------------
@pytest.mark.parametrize("n, code", [(2, "H"), (19, "Y"), (20, "g"), (21, "gG"), (400, "z"),
                                     (419, "zY")])
def test_repeat_counts(n, code):
    assert zpl._count(n) == code


def test_rows():
    assert zpl._compress_row("FFFF0000") == "JF,"
    assert zpl._compress_row("0000") == ","
    assert zpl._compress_row("A1B2") == "A1B2"
    assert zpl._compress_row("F" * 500) == "zYF" + "jGF"     # 419 + 81


@pytest.mark.parametrize("size", [(456, 256), (813, 1218), (9, 3), (1, 1), (684, 40)])
def test_graphic_reads_back_exactly(size):
    img = _picture(*size)
    back = decode(zpl.graphic(img))
    assert back.crop((0, 0, *size)).tobytes() == img.tobytes()
    if back.width > size[0]:                                  # Füllbits am Zeilenende: weiß
        assert back.crop((size[0], 0, back.width, size[1])).getextrema() == (255, 255)


def test_white_image_has_no_dots():
    assert zpl.graphic(Image.new("1", (673, 3), 1)) == "^GFA,255,255,85,,::"


def test_fixed_reference_rows():
    assert zpl._compress_row("B" * 327 + "0" * 3) == "vMB,"      # 327 = v (320) + M (7)
    assert zpl._compress_row("0F" * 3) == "0F0F0F"


def test_large_images_go_in_bands():
    img = Image.new("1", (1224, 1830), 1)                     # 102 × 152 mm bei 12 Punkten/mm
    text = zpl.fields(img)
    sizes = [int(n) for n in re.findall(r"\^GFA,(\d+),", text)]
    assert max(sizes) <= zpl.MAX_GRAPHIC and sum(sizes) == 153 * 1830
    assert text.startswith("^FO0,0^GFA") and "^FO0,653^GFA" in text


def test_same_rows_become_a_colon():
    img = Image.new("1", (16, 5), 1)
    ImageDraw.Draw(img).rectangle((0, 0, 7, 4), fill=0)
    assert zpl.graphic(img) == "^GFA,10,10,2,HF,::::"


def test_build_one_stream_per_series():
    label = get_label("57x32mm@203")
    img = Image.new("1", (label.width, label.height), 1)
    data = zpl.build([img, img], "C").decode()
    assert data.count("^XA^MMC^PW456^LL256^LH0,0^FO0,0^GFA,") == 2 and data.count("^XZ") == 2
    assert zpl.build([img]).startswith(b"^XA^PW456")          # Standard: kein ^MM
    with pytest.raises(ValueError, match="Modus"):
        zpl.build([img], "X")


# --- Modelle und Erkennung ----------------------------------------------------------------------
def test_zebra_models_and_labels():
    assert zpl.is_model("zpl:203") and not zpl.is_model("zpl:250") and not zpl.is_model(None)
    assert printers.is_model("zpl:300")
    caps = printers.capabilities("zpl:203")             # Schneiden: Modus im Reiter SERIE
    assert not caps.cutter and not caps.two_color and not caps.tested
    labels = labels_for_model("zpl:300")                   # 12 Punkte/mm = 304,8 dpi
    assert labels[0].id == "51x25mm@305" and labels[0].dpi == 305 and len(labels) == len(zpl.MEDIA)
    assert labels_for_model("zpl:600")[0].id == "51x25mm@610"
    assert get_label("102x152mm@305").width == 1225             # 102 mm × 12 = 1224 (305 statt 304,8)


def _sys_printer(root, name, vendor, ieee="", product=""):
    dev = root / "devices" / name
    (dev / "iface").mkdir(parents=True)
    (dev / "idVendor").write_text(vendor)
    (dev / "idProduct").write_text("0001")
    (dev / "product").write_text(product)
    (dev / "iface" / "ieee1284_id").write_text(ieee)
    entry = root / "usbmisc" / name
    entry.mkdir(parents=True)
    (entry / "device").symlink_to(dev / "iface")


@pytest.mark.parametrize("ieee, zpl_ok", [("MFG:Zebra Technologies;CMD:ZPL;MDL:ZD420;", True),
                                           ("MFG:Zebra;COMMAND SET:EPL2,ZPL;MDL:GK420d;", True),
                                           ("MFG:Zebra;CMD:EPL2;MDL:LP2844;", False),
                                           ("MDL:ZXP Series 3;CMD:ZMOTIF;", False), ("", True)])
def test_only_zpl_printers(ieee, zpl_ok):
    assert zpl.speaks_zpl(ieee) == zpl_ok


def test_zebra_on_usb_is_found_with_its_resolution(tmp_path):
    _sys_printer(tmp_path, "lp1", "04f9", "MDL:QL-600;")
    _sys_printer(tmp_path, "lp2", "0a5f", "MFG:Zebra Technologies;MDL:ZTC ZD420-300dpi ZPL;")
    _sys_printer(tmp_path, "lp3", "0a5f", "", "ZTC GK420d")
    found = printers.zebra_printers(tmp_path / "usbmisc")
    assert [(p.uri, p.model, p.name, p.source) for p in found] == [
        ("zpl+file:///dev/usb/lp2", "zpl:300", "ZTC ZD420-300dpi ZPL · lp2", "zebra"),
        ("zpl+file:///dev/usb/lp3", "zpl:203", "ZTC GK420d · lp3", "zebra")]
    assert [p.uri for p in printers.usb_printers(tmp_path / "usbmisc")] == ["file:///dev/usb/lp1"]
    _sys_printer(tmp_path, "lp4", "0a5f", "MFG:Zebra;CMD:EPL2;MDL:LP2844;")     # nur EPL: nicht
    assert len(printers.zebra_printers(tmp_path / "usbmisc")) == 2
    forced = printers.zebra_printers(tmp_path / "usbmisc", dpi=600)       # Einstellung gilt
    assert [p.model for p in forced] == ["zpl:600", "zpl:600"]


def test_network_zebra_and_given_uris():
    entries = [printers.NetworkEntry("Lager", "10.0.0.8", "zpl:203"),
               printers.NetworkEntry("Büro", "10.0.0.5", "QL-720NW")]
    zebra, brother = printers.network_printers(entries)
    assert (zebra.uri, zebra.model, zebra.source) == ("zpl+tcp://10.0.0.8:9100", "zpl:203", "zebra")
    assert brother.uri == "tcp://10.0.0.5:9100"
    given = printers.printer_for("zpl+tcp://10.0.0.9", [])
    assert (given.model, given.source) == ("zpl:203", "zebra")
    assert printers.backend_for("zpl+file:///dev/usb/lp2") == "zpl"


# --- Drucken ------------------------------------------------------------------------------------
@pytest.fixture
def any_file(monkeypatch):
    """Eine Datei gilt als Druckergerät (Tests schreiben nie an /dev/usb)."""
    monkeypatch.setattr(zpl, "_is_device", lambda info: True)


def test_print_writes_zpl_to_the_device(tmp_path, any_file):
    device = tmp_path / "lp2"
    device.write_bytes(b"")
    label = get_label("57x32mm@203")
    img = Image.new("1", (label.width, label.height), 1)
    status = print_image([img] * 3, label.id, model="zpl:203", printer=f"zpl+file://{device}",
                         options={"mode": "C"})
    assert status == {"outcome": "sent", "did_print": False}
    assert device.read_bytes().count(b"^XA^MMC^PW456^LL256") == 3


def test_print_over_the_network(monkeypatch):
    sent = {}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def settimeout(self, value):
            sent["write_timeout"] = value

        def send(self, data):
            sent["data"] = sent.get("data", b"") + bytes(data[:1000])     # langsamer Drucker
            return min(len(data), 1000)

    def connect(address, timeout):
        sent["address"], sent["timeout"] = address, timeout
        return Conn()
    monkeypatch.setattr(zpl.socket, "create_connection", connect)
    label = get_label("51x25mm@203")
    print_image(Image.new("1", (label.width, label.height), 1), label.id, model="zpl:203",
                printer="zpl+tcp://10.0.0.8:9100")
    assert sent["address"] == ("10.0.0.8", 9100) and sent["timeout"] == zpl.TIMEOUT_S
    assert sent["write_timeout"] == zpl.WRITE_TIMEOUT_S          # je Block, nicht für alles
    assert sent["data"].startswith(b"^XA^PW408^LL200") and sent["data"].endswith(b"^XZ\n")


def test_send_errors_are_readable(tmp_path, monkeypatch):
    label = get_label("57x32mm@203")
    img = Image.new("1", (label.width, label.height), 1)
    with pytest.raises(PrintError, match="nicht gefunden"):
        print_image(img, label.id, model="zpl:203", printer=f"zpl+file://{tmp_path}/fehlt")
    (tmp_path / "datei").write_bytes(b"")
    with pytest.raises(PrintError, match="kein Druckergerät"):
        print_image(img, label.id, model="zpl:203", printer=f"zpl+file://{tmp_path}/datei")
    assert not (tmp_path / "fehlt").exists()                   # nie eine Datei angelegt

    def refuse(address, timeout):
        raise ConnectionRefusedError(111, "Connection refused")
    monkeypatch.setattr(zpl.socket, "create_connection", refuse)
    with pytest.raises(PrintError, match="Zebra-Drucker 10.0.0.8 nicht erreichbar"):
        print_image(img, label.id, model="zpl:203", printer="zpl+tcp://10.0.0.8")
    with pytest.raises(PrintError, match="Ungültige Adresse"):
        print_image(img, label.id, model="zpl:203", printer="zpl+tcp://10.0.0.8:x")


def test_brother_label_does_not_fit_a_zebra(tmp_path):
    with pytest.raises(PrintError, match="passt nicht"):
        print_image(Image.new("1", (10, 10), 1), "62", model="zpl:203",
                    printer=f"zpl+file://{tmp_path}/lp2")


def test_device_that_takes_no_data_times_out(tmp_path, any_file, monkeypatch):
    class Stuck:
        def register(self, fd, events):
            pass

        def poll(self, timeout):
            return []
    monkeypatch.setattr(zpl.select, "poll", Stuck)
    (tmp_path / "lp2").write_bytes(b"")
    with pytest.raises(zpl.ZplError, match="nimmt keine Daten an"):
        zpl.send(b"^XA^XZ", f"zpl+file://{tmp_path}/lp2")


def test_series_is_streamed_label_by_label(tmp_path, any_file):
    label = get_label("51x25mm@203")
    made = []

    def images():
        for n in range(3):
            made.append(n)
            yield Image.new("1", (label.width, label.height), 1)
    chunks = zpl.stream(images())
    assert made == []                                          # erst beim Senden erzeugt
    zpl.send(chunks, f"zpl+file://{tmp_path}/lp2") if (tmp_path / "lp2").write_bytes(b"") == 0 \
        else None
    assert made == [0, 1, 2] and (tmp_path / "lp2").read_bytes().count(b"^XZ") == 3
