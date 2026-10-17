from labelwerk.detect import find_brother_lp


def _fake_lp(sys_root, devices, name, vendor):
    usb_dev = devices / f"usb-{name}"
    iface = usb_dev / "1-1:1.0"
    iface.mkdir(parents=True)
    (usb_dev / "idVendor").write_text(vendor + "\n")
    (sys_root / name).mkdir(parents=True)
    (sys_root / name / "device").symlink_to(iface)


def test_finds_brother_printer_among_lp_devices(tmp_path):
    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
    _fake_lp(sys_root, devices, "lp0", "03f0")   # z. B. HP
    _fake_lp(sys_root, devices, "lp1", "04f9")   # Brother
    assert find_brother_lp(sys_root, "/dev/usb") == "file:///dev/usb/lp1"


def test_returns_none_without_brother_printer(tmp_path):
    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
    _fake_lp(sys_root, devices, "lp0", "03f0")
    assert find_brother_lp(sys_root, "/dev/usb") is None
