"""Findet Brother-Drucker unter /dev/usb/lp* bzw. per pyusb anhand der USB-Vendor-ID."""
from __future__ import annotations

from pathlib import Path

from brother_ql.backends.helpers import discover as _discover

BROTHER_VENDOR_ID = "04f9"


def find_brother_lp(sys_root: str | Path = "/sys/class/usbmisc",
                    dev_root: str = "/dev/usb") -> str | None:
    for entry in sorted(Path(sys_root).glob("lp*")):
        iface = (entry / "device").resolve()
        for node in (iface, *iface.parents):
            vendor = node / "idVendor"
            if vendor.exists():
                if vendor.read_text().strip() == BROTHER_VENDOR_ID:
                    return f"file://{dev_root}/{entry.name}"
                break
    return None


def find_brother_usb(discover=_discover) -> str | None:
    """Erster Brother-Drucker laut pyusb, z. B. "usb://0x04f9:0x20c0/SERIAL"."""
    try:
        devices = discover("pyusb")
    except Exception:  # pyusb/libusb fehlt oder kein Zugriff auf den USB-Bus
        return None
    return devices[0]["identifier"] if devices else None
