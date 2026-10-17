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
