"""Findet Brother-Drucker unter /dev/usb/lp* anhand der USB-Vendor-ID."""
from __future__ import annotations

from pathlib import Path

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
