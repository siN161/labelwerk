"""Findet Brother-Drucker unter /dev/usb/lp* bzw. per pyusb anhand der USB-Vendor-ID."""
from __future__ import annotations

from pathlib import Path

from brother_ql.backends.helpers import discover as _discover

from .i18n import N_

BROTHER_VENDOR_ID = "04f9"

# Meldungen für CLI und GUI – nur markiert, beim Anzeigen mit ``_()`` übersetzen
PRINTER_NOT_FOUND = N_("Brother printer not found under /dev/usb/lp*.\n"
                       "Check: switched on, Editor Lite LED off, 'lsusb', 'lsmod | grep usblp'.")
BUSY_MESSAGE = N_("Brother printer is connected via USB but in use by another program\n"
                  "(e.g. a VM with USB passthrough). Release it there and switch the printer\n"
                  "off and on again.")


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


def brother_busy(devices_root: str | Path = "/sys/bus/usb/devices") -> bool:
    """True, wenn ein Brother-Drucker angeschlossen ist, aber ein anderes Programm sein
    Druckerinterface direkt belegt (Treiber usbfs, z. B. VM mit USB-Durchreichung)."""
    try:
        for dev in Path(devices_root).iterdir():
            vendor = dev / "idVendor"
            if not vendor.exists() or vendor.read_text().strip() != BROTHER_VENDOR_ID:
                continue
            for iface in dev.glob(f"{dev.name}:*"):
                cls = iface / "bInterfaceClass"
                driver = iface / "driver"
                if (cls.exists() and cls.read_text().strip() == "07"
                        and driver.exists() and driver.resolve().name == "usbfs"):
                    return True
    except OSError:  # sysfs fehlt oder nicht lesbar: nicht als belegt melden
        return False
    return False
