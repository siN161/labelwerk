"""Printer compatibility: detection (sysfs), capabilities per model, labels, choice, network,
cutter, red/black, settings."""
import pytest
from PIL import Image, ImageDraw

from labelwerk import printers
from labelwerk.document import Document, ImageObject, TextObject
from labelwerk.labels import labels_for_model
from labelwerk.printer import PrintError, build_instructions, print_image, to_print_mode
from labelwerk.printers import (Capabilities, NetworkEntry, Printer, backend_for, capabilities,
                                choose, effective_model, known_model, network_printers,
                                usb_printers)
from labelwerk.render import render_document
from labelwerk.settings import load_settings, network_entries, save_settings, Settings


def _fake_lp(sys_root, devices, name, vendor="04f9", product_id="", product="", ieee=""):
    usb_dev = devices / f"usb-{name}"
    iface = usb_dev / "1-1:1.0"
    iface.mkdir(parents=True)
    (usb_dev / "idVendor").write_text(vendor + "\n")
    if product_id:
        (usb_dev / "idProduct").write_text(product_id + "\n")
    if product:
        (usb_dev / "product").write_text(product + "\n")
    if ieee:
        (iface / "ieee1284_id").write_text(ieee)
    (sys_root / name).mkdir(parents=True)
    (sys_root / name / "device").symlink_to(iface)


# --- Detection -------------------------------------------------------------------------------
def test_model_from_the_ieee1284_id_first(tmp_path):
    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
    _fake_lp(sys_root, devices, "lp1", product_id="2042", product="QL-700",
             ieee="MFG:Brother;CMD:PT-CBP;MDL:QL-600;CLS:PRINTER;")
    assert usb_printers(sys_root) == [Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")]


def test_model_from_the_product_name_then_the_product_id(tmp_path):
    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
    _fake_lp(sys_root, devices, "lp0", product_id="2042", product="QL-720NW")
    _fake_lp(sys_root, devices, "lp1", product_id="2042")
    _fake_lp(sys_root, devices, "lp2", product_id="ffff")
    _fake_lp(sys_root, devices, "lp3", vendor="03f0", product="LaserJet")   # other manufacturer
    found = usb_printers(sys_root)
    assert [(p.uri, p.model, p.name) for p in found] == [
        ("file:///dev/usb/lp0", "QL-720NW", "QL-720NW · lp0"),
        ("file:///dev/usb/lp1", "QL-700", "QL-700 · lp1"),
        ("file:///dev/usb/lp2", None, "Brother-Drucker · lp2")]


def test_no_printers_without_sysfs(tmp_path):
    assert usb_printers(tmp_path / "fehlt") == []


def test_default_sysfs_is_isolated_in_tests():
    assert usb_printers() == []


@pytest.mark.parametrize("name, model", [
    ("QL-600", "QL-600"), ("QL-600G", "QL-600"), ("Brother QL-820NWB", "QL-820NWB"),
    ("ql-1110nwb", "QL-1110NWB"), ("QL-1100", "QL-1100"), ("PT-P700", None), ("", None),
    (None, None), ("QL-9999", None)])
def test_known_model(name, model):
    assert known_model(name) == model


# --- Capabilities and labels ---------------------------------------------------------------------
def test_capabilities_from_brother_ql():
    assert capabilities("QL-600") == Capabilities("QL-600", True, False, 62, (150, 11811), True)
    assert not capabilities("QL-500").cutter
    assert capabilities("QL-820NWB").two_color and not capabilities("QL-820NWB").tested
    assert capabilities("QL-1100").max_tape_mm == 104
    with pytest.raises(ValueError, match="Unbekanntes Druckermodell"):
        capabilities("PT-P700")


def test_supported_models_are_the_ql_series():
    assert "QL-600" in printers.SUPPORTED_MODELS and "QL-1115NWB" in printers.SUPPORTED_MODELS
    assert not any(m.startswith("PT") for m in printers.SUPPORTED_MODELS)


def _ids(model):
    return {label.id for label in labels_for_model(model)}


def test_labels_follow_the_model():
    assert "62red" not in _ids("QL-600") and "102" not in _ids("QL-600")
    assert "62red" in _ids("QL-820NWB")
    assert {"102", "103", "104", "102x51", "62"} <= _ids("QL-1100")
    assert "102" in _ids("QL-1050") and "103" not in _ids("QL-1050")
    assert not any(i.startswith("pt") for i in _ids("QL-1100"))
    with pytest.raises(ValueError, match="Unbekanntes Druckermodell"):
        labels_for_model("PT-P700")


# --- Choice and model ---------------------------------------------------------------------------
USB = Printer("file:///dev/usb/lp1", "QL-600", "QL-600 · lp1")
NET = Printer("tcp://10.0.0.5:9100", "QL-720NW", "Büro · Netzwerk", "network")


def test_choose_the_wanted_printer_else_the_first_usb():
    assert choose([NET, USB]) == USB
    assert choose([NET, USB], NET.uri) == NET
    assert choose([NET, USB], "file:///dev/usb/lp9") is None        # selected one is missing: none
    assert choose([NET]) == NET and choose([]) is None


def test_effective_model():
    assert effective_model(USB, "QL-700", "QL-800") == "QL-600"
    unknown = Printer("file:///dev/usb/lp0", None, "Brother-Drucker · lp0")
    assert effective_model(unknown, "QL-700", "QL-800") == "QL-700"
    assert effective_model(None, "", "QL-800") == "QL-800"
    assert effective_model(None) == "QL-600"
    assert effective_model(None, "PT-P700", "kaputt") == "QL-600"


def test_network_printers_and_backends():
    assert network_printers([NetworkEntry("Büro", "10.0.0.5", "QL-720NW")]) == [NET]
    assert network_printers([NetworkEntry("", "drucker.lan", "QL-710W")])[0].name == \
        "drucker.lan · Netzwerk"
    assert backend_for("tcp://10.0.0.5:9100") == "network"
    assert backend_for("usb://0x04f9:0x20c0") == "pyusb"
    assert backend_for("file:///dev/usb/lp1") == "linux_kernel"


# --- Printing -----------------------------------------------------------------------------------
def _image(red=False):
    img = Image.new("RGB", (696, 120), "white")
    ImageDraw.Draw(img).rectangle((10, 10, 100, 100), fill=(255, 0, 0) if red else (0, 0, 0))
    return img


def test_without_cutter_nothing_is_cut():
    assert build_instructions(_image(), "62", "QL-500", cut=True) == \
        build_instructions(_image(), "62", "QL-500", cut=False)
    assert build_instructions(_image(), "62", "QL-600", cut=True) != \
        build_instructions(_image(), "62", "QL-600", cut=False)


def _plane_ink(data: bytes, plane: int) -> int:
    """Set bytes in the raster lines of a plane (w 01 black, w 02 red)."""
    marker, total, start = b"w" + bytes([plane]), 0, 0
    while (i := data.find(marker, start)) >= 0:
        size = data[i + 2]
        total += sum(1 for b in data[i + 3:i + 3 + size] if b)
        start = i + 3 + size
    return total


def test_red_labels_get_a_red_plane():
    red = build_instructions(_image(red=True), "62red", "QL-820NWB")
    black = build_instructions(_image(), "62red", "QL-820NWB")
    assert _plane_ink(red, 2) > 0 and _plane_ink(red, 1) == 0
    assert _plane_ink(black, 1) > 0 and _plane_ink(black, 2) == 0


def test_print_mode_keeps_red():
    img = _image(red=True)
    assert to_print_mode(img, red=True).getpixel((50, 50)) == (255, 0, 0)
    assert to_print_mode(img).mode == "1"


class _Socket:
    def close(self):
        pass


def test_network_printer_uses_the_network_backend(monkeypatch):
    seen = {}
    monkeypatch.setattr("labelwerk.printer.socket.create_connection",
                        lambda address, timeout: seen.update(probe=(address, timeout)) or _Socket())

    def send(instructions, printer_identifier, backend_identifier, blocking):
        seen.update(printer=printer_identifier, backend=backend_identifier)
        return {"outcome": "sent", "did_print": False}
    monkeypatch.setattr("labelwerk.printer.send", send)
    print_image(_image(), "62", model="QL-720NW", printer="tcp://10.0.0.5:9100")
    assert seen == {"printer": "tcp://10.0.0.5:9100", "backend": "network",
                    "probe": (("10.0.0.5", 9100), 5)}


@pytest.mark.parametrize("error, reason", [
    (ConnectionRefusedError(111, "Connection refused"), "Connection refused"),
    (TimeoutError("timed out"), "keine Antwort")])
def test_unreachable_network_printer_is_a_print_error(monkeypatch, error, reason):
    def connect(address, timeout):
        raise error
    monkeypatch.setattr("labelwerk.printer.socket.create_connection", connect)
    with pytest.raises(PrintError, match=rf"Netzwerkdrucker tcp://10.0.0.5:9100 nicht erreichbar "
                                         rf"\({reason}\)"):
        print_image(_image(), "62", model="QL-720NW", printer="tcp://10.0.0.5:9100")


# --- Colour -------------------------------------------------------------------------------------
def test_red_objects_print_red_only_on_red_labels():
    obj = TextObject.plain("Achtung", size_pt=20)
    obj.color = "red"
    img = render_document(Document("62red", objects=[obj]), "QL-820NWB")
    colors = {c for _, c in img.getcolors(1 << 20)}
    assert (255, 0, 0) in colors and (0, 0, 0) not in colors
    plain = render_document(Document("62", objects=[obj]), "QL-820NWB")
    assert (255, 0, 0) not in {c for _, c in plain.getcolors(1 << 20)}     # preview = print
    single = render_document(Document("62red", objects=[obj]), "QL-600")  # model without red
    assert (255, 0, 0) not in {c for _, c in single.getcolors(1 << 20)}


def test_images_and_barcodes_can_be_red():
    from labelwerk.document import BarcodeObject
    image = ImageObject.from_image(Image.new("RGB", (60, 60), "black"), 300, "x")
    image.color = "red"
    code = BarcodeObject(kind="qr", data="x", x_mm=20, color="red")
    img = render_document(Document("62red", objects=[image, code]), "QL-820NWB")
    assert img.getpixel((10, 10)) == (255, 0, 0)
    assert img.getpixel((round(20 * 300 / 25.4) + 2, 2)) == (255, 0, 0)


def test_unknown_color_is_a_render_error():
    obj = TextObject("A")
    obj.color = "blau"
    with pytest.raises(ValueError, match="Unbekannte Farbe"):
        render_document(Document("62", objects=[obj]))


def test_color_is_saved():
    from labelwerk import storage
    obj = TextObject("A")
    obj.color = "red"
    data = storage.to_dict(Document("62red", objects=[obj]))
    assert storage.from_dict(data).objects[0].color == "red"
    data["document"]["objects"][0]["color"] = "blau"
    with pytest.raises(storage.StorageError, match="„color“"):
        storage.from_dict(data)


# --- Settings -----------------------------------------------------------------------------------
def test_printer_settings_round_trip(tmp_path):
    path = tmp_path / "s.json"
    settings = Settings(printer="tcp://10.0.0.5:9100", printer_model="",
                        last_model="QL-1100", label_id="102",
                        network_printers=[{"name": "Büro", "host": "10.0.0.5",
                                           "model": "QL-720NW"}])
    save_settings(settings, path)
    loaded = load_settings(path)                    # label 102 applies to the last model
    assert (loaded.printer, loaded.printer_model, loaded.last_model, loaded.label_id) == (
        "tcp://10.0.0.5:9100", "", "QL-1100", "102")
    assert network_entries(loaded) == [NetworkEntry("Büro", "10.0.0.5", "QL-720NW")]
    assert loaded.warnings == []


def test_invalid_printer_settings_fall_back(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('{"printer": "ftp://x", "printer_model": "PT-P700", "last_model": 5, '
                    '"network_printers": [{"name": "ok", "host": "10.0.0.5", "model": "QL-710W"},'
                    ' {"host": "a b", "model": "QL-710W"}, {"host": "tcp://x", "model": "QL-710W"},'
                    ' {"host": "x", "model": "PT-P700"}, "kaputt"]}')
    loaded = load_settings(path)
    assert (loaded.printer, loaded.printer_model, loaded.last_model) == ("", "", "")
    assert loaded.network_printers == [{"name": "ok", "host": "10.0.0.5", "model": "QL-710W"}]
    assert len(loaded.warnings) == 4


def test_saved_label_survives_another_model(tmp_path):
    """Whoever alternates between two printers keeps their label – whether it fits is checked by GUI/CLI."""
    path = tmp_path / "s.json"
    save_settings(Settings(printer_model="QL-700", last_model="QL-600", label_id="102"), path)
    loaded = load_settings(path)
    assert loaded.label_id == "102" and loaded.warnings == []
    path.write_text('{"label_id": "pt12"}')
    assert load_settings(path).label_id == "62"         # P-touch tape: no QL label


# --- Fixes after the review -----------------------------------------------------------------------
def test_choose_prefers_a_recognised_model():
    laser = Printer("file:///dev/usb/lp0", None, "Brother-Drucker · lp0")
    assert choose([laser, USB]) == USB
    assert choose([laser]) == laser


def test_printer_for_a_given_uri():
    from labelwerk.printers import printer_for
    assert printer_for(USB.uri, [NET, USB]) is USB
    assert printer_for("usb://0x04f9:0x20a7/ABC", []).model == "QL-1100"
    assert printer_for("usb://0x04f9:0x9999", []).model is None
    assert printer_for("tcp://1.2.3.4:9100", []).source == "network"


def test_label_must_fit_the_model():
    with pytest.raises(ValueError, match="Etikett '62red' passt nicht zum QL-600"):
        build_instructions(_image(red=True), "62red", "QL-600")
    with pytest.raises(PrintError, match="passt nicht zum Drucker"):
        print_image(_image(), "102", model="QL-600")


def test_red_labels_use_the_same_threshold_as_black_and_white():
    """Anti-aliasing greys become just as black on 62red as on 62 (preview = print)."""
    text = TextObject.plain("Grauer Rand 8 pt", size_pt=8)
    plain = to_print_mode(render_document(Document("62", objects=[text]), "QL-820NWB"))
    red = to_print_mode(render_document(Document("62red", objects=[text]), "QL-820NWB"), red=True)
    assert plain.histogram()[0] == sum(1 for c in red.getdata() if c == (0, 0, 0))
    from labelwerk.printer import pure_colors
    edge = Image.new("RGB", (5, 1))
    for x, color in enumerate([(179, 179, 179), (180, 180, 180), (255, 179, 179),
                               (255, 180, 180), (100, 20, 20)]):
        edge.putpixel((x, 0), color)
    assert list(pure_colors(edge).getdata()) == [(0, 0, 0), (255, 255, 255), (255, 0, 0),
                                                 (255, 255, 255), (0, 0, 0)]


def test_busy_usb_device_is_a_print_error(monkeypatch):
    def send(**kw):
        raise OSError(16, "Device or resource busy")
    monkeypatch.setattr("labelwerk.printer.send", send)
    with pytest.raises(PrintError, match=r"nicht bereit \(Device or resource busy\)"):
        print_image(_image(), "62", printer="file:///dev/usb/lp0")


def test_host_without_control_characters():
    from labelwerk.settings import valid_host
    assert valid_host("drucker.lan") and valid_host(" 10.0.0.5 ")
    assert not any(valid_host(h) for h in ("a\x00b", "fe80::1", "tcp://x", "a b", "", "x/y"))
