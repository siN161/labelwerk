from labelwerk.detect import brother_busy, find_brother_lp, find_brother_usb


def _fake_lp(sys_root, devices, name, vendor):
    usb_dev = devices / f"usb-{name}"
    iface = usb_dev / "1-1:1.0"
    iface.mkdir(parents=True)
    (usb_dev / "idVendor").write_text(vendor + "\n")
    (sys_root / name).mkdir(parents=True)
    (sys_root / name / "device").symlink_to(iface)


def test_finds_brother_printer_among_lp_devices(tmp_path):
    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
    _fake_lp(sys_root, devices, "lp0", "03f0")   # e.g. HP
    _fake_lp(sys_root, devices, "lp1", "04f9")   # Brother
    assert find_brother_lp(sys_root, "/dev/usb") == "file:///dev/usb/lp1"


def test_returns_none_without_brother_printer(tmp_path):
    sys_root, devices = tmp_path / "usbmisc", tmp_path / "devices"
    _fake_lp(sys_root, devices, "lp0", "03f0")
    assert find_brother_lp(sys_root, "/dev/usb") is None


def test_finds_brother_printer_via_pyusb():
    devices = [{"identifier": "usb://0x04f9:0x20c0/A1B2", "instance": object()}]
    assert find_brother_usb(discover=lambda backend: devices) == "usb://0x04f9:0x20c0/A1B2"


def test_pyusb_without_printer_returns_none():
    assert find_brother_usb(discover=lambda backend: []) is None


def test_pyusb_without_libusb_returns_none():
    def broken(backend):
        raise RuntimeError("No backend available")
    assert find_brother_usb(discover=broken) is None


def _fake_usb_device(root, name, vendor, driver):
    dev = root / "devices" / name
    iface = dev / f"{name}:1.0"
    iface.mkdir(parents=True)
    (dev / "idVendor").write_text(vendor + "\n")
    (iface / "bInterfaceClass").write_text("07\n")   # printer
    if driver:
        drv = root / "drivers" / driver
        drv.mkdir(parents=True, exist_ok=True)
        (iface / "driver").symlink_to(drv)
    return root / "devices"


def test_brother_claimed_by_other_program(tmp_path):
    devices = _fake_usb_device(tmp_path, "1-5", "04f9", "usbfs")
    assert brother_busy(devices) is True


def test_brother_with_usblp_is_not_busy(tmp_path):
    devices = _fake_usb_device(tmp_path, "1-5", "04f9", "usblp")
    assert brother_busy(devices) is False


def test_other_vendor_on_usbfs_is_ignored(tmp_path):
    devices = _fake_usb_device(tmp_path, "1-6", "03f0", "usbfs")
    assert brother_busy(devices) is False


def test_busy_check_without_sysfs_returns_false(tmp_path):
    assert brother_busy(tmp_path / "fehlt") is False
